"""
Wave 2 Lane S1 regression tests for fleet-level parallelism, dynamic concurrency scaling,
and stat-validated drift/dist-lock caching.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest


def _write_temp_truth_pack(packs_dir: Path, pid: str) -> None:
    from pseofactory.pricing import get_tier_pricing

    packs_dir.mkdir(parents=True, exist_ok=True)
    tp_payload = {
        "schema_version": "2.0",
        "property_id": pid,
        "brand_name": pid.capitalize(),
        "canonical_domain": f"https://{pid}.com",
        "audience_tier": "business",
        "pricing_tiers": {
            "free": {"tier_kind": "free", "label": "Free", "price_usd": 0.0, "price_cents": 0},
            **get_tier_pricing("business"),
        },
        "entries": {},
        "formulas": {
            "sample_calc": {
                "formula_id": "sample_calc",
                "model_name": "Sample Sum Model",
                "expression": "a + b",
                "variables": {"a": 10.0, "b": 20.0},
                "expected_baseline_output": 30.0,
                "tolerance": 0.01,
                "test_vectors": [
                    {"label": "baseline", "inputs": {"a": 10.0, "b": 20.0}, "expected": 30.0},
                    {"label": "scaled", "inputs": {"a": 15.0, "b": 25.0}, "expected": 40.0},
                ],
                "citation_keys": [],
                "allowed_slug_patterns": ["sample-calc"],
                "forbidden_slug_patterns": [],
                "output_selectors": [".output-value"],
            }
        },
        "citations_allowlist": {},
        "disclosures": [],
        "banned_claims": [],
        "cross_tenant_brand_tokens": [],
        "allowed_shared_legal_tokens": [],
    }
    (packs_dir / f"{pid}.json").write_text(json.dumps(tp_payload, indent=2), encoding="utf-8")


def _make_handoff_tenant(ws_root: Path, pid: str) -> Path:
    repo = ws_root / ("profithelm-platform" if pid == "profithelm" else pid)
    dist = repo / "dist"
    (dist / "tools" / "sample-calc").mkdir(parents=True, exist_ok=True)
    (dist / "index.html").write_text(
        f'<!DOCTYPE html><html lang="en"><head><title>{pid.capitalize()}</title>'
        f'<link rel="canonical" href="https://{pid}.com/"></head><body><h1>{pid.capitalize()}</h1></body></html>',
        encoding="utf-8",
    )
    (dist / "tools" / "sample-calc" / "index.html").write_text(
        f'<!DOCTYPE html><html lang="en"><head><title>Sample Calc | {pid.capitalize()}</title>'
        f'<link rel="canonical" href="https://{pid}.com/tools/sample-calc/">'
        f'<script type="application/ld+json">{{"@context":"https://schema.org","@type":"SoftwareApplication","name":"Sample Calc"}}</script>'
        f'<script id="calculation-manifest" type="application/json">'
        f'{{"formula":"a + b","inputs":{{"a":10,"b":20}},"published_output":30.0}}'
        f'</script></head><body>'
        f'<h1>Sample Calc</h1>'
        f'<form class="calculator-form">'
        f'<input id="input-a" name="a" value="10">'
        f'<input id="input-b" name="b" value="20">'
        f'<span class="output-value">30</span>'
        f'</form>'
        f'<script>'
        f'function recompute(){{var a=Number(document.getElementById("input-a").value||0);var b=Number(document.getElementById("input-b").value||0);document.querySelector(".output-value").textContent=String(a+b);}}'
        f'document.querySelector("form").addEventListener("input",recompute);'
        f'document.addEventListener("DOMContentLoaded",recompute);'
        f'</script></body></html>',
        encoding="utf-8",
    )
    (repo / ".pseofactory.json").write_text(
        json.dumps(
            {
                "property_id": pid,
                "domain": f"{pid}.com",
                "canonical_base": f"https://{pid}.com",
                "brand_name": pid.capitalize(),
                "dist_dir": "dist",
            }
        ),
        encoding="utf-8",
    )
    return repo


def test_handoff_stages_3_to_6_parallel_deterministic_order_and_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Verifies DepartmentHandoffChainVerifier Stages 3..6 run tenants concurrently via
    _map_tenants_ordered, preserve deterministic tenant ordering even when earlier
    tenants take longer, and fail closed when any tenant reports an error or lacks a Truth Pack.
    """
    import pseofactory.maintenance as maint_mod
    import pseofactory.supervisor as sup_mod
    import pseofactory.truth_pack as tp_mod
    from pseofactory.maintenance import ConfigurablePropertyAdapter
    from pseofactory.supervisor import DepartmentHandoffChainVerifier

    tenants = ["alpha", "beta", "gamma", "delta"]
    tmp_packs = tmp_path / "truth_packs"
    for pid in tenants:
        _write_temp_truth_pack(tmp_packs, pid)
    monkeypatch.setattr(tp_mod, "DEFAULT_TRUTH_PACKS_DIR", tmp_packs)

    ws = tmp_path / "ws"
    adapters: Dict[str, ConfigurablePropertyAdapter] = {}
    for pid in tenants:
        repo = _make_handoff_tenant(ws, pid)
        adapters[pid] = ConfigurablePropertyAdapter(
            property_id=pid,
            brand_name=pid.capitalize(),
            domain=f"{pid}.com",
            canonical_base=f"https://{pid}.com",
            dist_dir=repo / "dist",
            repo_path=repo,
        )

    verifier = DepartmentHandoffChainVerifier(workspace_root=ws, property_ids=tenants)

    # 1. Verify _map_tenants_ordered runs concurrently and preserves input order
    active = 0
    max_active = 0
    lock = threading.Lock()
    delays = {"alpha": 0.12, "beta": 0.02, "gamma": 0.08, "delta": 0.01}

    def _probe(pid: str) -> str:
        nonlocal active, max_active
        with lock:
            active += 1
            if active > max_active:
                max_active = active
        time.sleep(delays[pid])
        with lock:
            active -= 1
        return f"res-{pid}"

    ordered = verifier._map_tenants_ordered(tenants, _probe)
    assert [pid for pid, _ in ordered] == tenants
    assert [val for _, val in ordered] == [f"res-{pid}" for pid in tenants]
    assert max_active >= 2, f"Expected parallel execution across tenants, got max_active={max_active}"

    # 2. Verify Stage 4 (_run_verification_stage) executes tenants concurrently and fails closed
    verif_active = 0
    verif_max_active = 0
    verif_lock = threading.Lock()

    class _FakeReport:
        def __init__(self, fail: bool) -> None:
            self.status = "FAIL" if fail else "PASS"
            self.total_assets_checked = 2
            self.compliant_assets_count = 1 if fail else 2
            self.drifted_assets_count = 1 if fail else 0
            self.drifted_assets: List[Any] = []

    def _fake_audit_all(self: Any, adapter: Any, **kwargs: Any) -> _FakeReport:
        nonlocal verif_active, verif_max_active
        with verif_lock:
            verif_active += 1
            if verif_active > verif_max_active:
                verif_max_active = verif_active
        time.sleep(0.06 if adapter.property_id == "alpha" else 0.02)
        with verif_lock:
            verif_active -= 1
        return _FakeReport(fail=(adapter.property_id == "gamma"))

    monkeypatch.setattr(maint_mod.AssetIntegrityEvaluator, "audit_all", _fake_audit_all)
    monkeypatch.setattr(
        maint_mod.RetroReflectionEngine,
        "audit_estate",
        classmethod(lambda cls, d, p: {"status": "PASS", "pages_scanned": 2, "stale_count": 0}),
    )
    import pseofactory.verifier as ver_mod

    monkeypatch.setattr(
        ver_mod,
        "audit_aeo_geo_three_plane_readiness",
        lambda dist_dir, property_id: {"status": "PASS", "passed": True, "issues": []},
    )
    import pseofactory.tenant_facts as tf_mod

    monkeypatch.setattr(
        tf_mod.TenantFactStore,
        "assert_tenant_isolation",
        lambda self, pid, text: None,
    )

    ok4, out4, sum4, errs4 = verifier._run_verification_stage(
        {
            "discovered_tenants": tenants,
            "tenant_adapters": adapters,
            "engine_hash": "a" * 64,
            "compiler_smoke_by_tenant": {p: {"query": f"{p} calc"} for p in tenants},
        }
    )
    assert verif_max_active >= 2, f"Stage 4 did not run concurrently (max_active={verif_max_active})"
    assert ok4 is False
    assert out4["zero_drift_verified"] is False
    assert list(sum4["per_tenant"].keys()) == tenants
    assert sum4["per_tenant"]["gamma"]["status"] == "FAIL"
    assert sum4["per_tenant"]["alpha"]["status"] == "PASS"
    assert any("VERIFICATION[gamma]:" in e for e in errs4)

    # 2b. Verify missing TruthPack fails closed in Stage 4 (no silent fallback)
    missing_repo = _make_handoff_tenant(ws, "no_pack_site")
    missing_adapter = ConfigurablePropertyAdapter(
        property_id="no_pack_site",
        brand_name="NoPackSite",
        domain="no-pack-site.com",
        canonical_base="https://no-pack-site.com",
        dist_dir=missing_repo / "dist",
        repo_path=missing_repo,
    )
    ok_missing, _, sum_missing, errs_missing = verifier._run_verification_stage(
        {
            "discovered_tenants": ["no_pack_site"],
            "tenant_adapters": {"no_pack_site": missing_adapter},
            "engine_hash": "a" * 64,
            "compiler_smoke_by_tenant": {"no_pack_site": {"query": "no_pack_site calc"}},
        }
    )
    assert ok_missing is False
    assert sum_missing["per_tenant"]["no_pack_site"]["status"] == "FAIL"
    assert any("TRUTH_PACK_MISSING" in e for e in errs_missing)

    # 3. Verify Stage 5 (_run_syndication_stage) runs concurrently and preserves order
    import pseofactory.indexing.preflight as pre_mod

    syn_active = 0
    syn_max_active = 0
    syn_lock = threading.Lock()

    class _FakePreRep:
        is_gate_passed = True
        passed_count = 2
        blocked_count = 0

    def _fake_inspect(self: Any) -> _FakePreRep:
        nonlocal syn_active, syn_max_active
        with syn_lock:
            syn_active += 1
            if syn_active > syn_max_active:
                syn_max_active = syn_active
        time.sleep(0.05)
        with syn_lock:
            syn_active -= 1
        return _FakePreRep()

    monkeypatch.setattr(pre_mod.IndexingPreflightEngine, "inspect_dist", _fake_inspect)
    monkeypatch.setattr(
        maint_mod,
        "_has_pending_downstream_work",
        lambda *a, **k: False,
    )
    ok5, out5, sum5, errs5 = verifier._run_syndication_stage(
        {
            "discovered_tenants": tenants,
            "tenant_adapters": adapters,
        }
    )
    assert syn_max_active >= 2, f"Stage 5 did not run concurrently (max_active={syn_max_active})"
    assert ok5 is False  # Missing root discovery files / videos / ledgers must fail closed
    assert list(sum5["per_tenant"].keys()) == tenants
    assert list(out5["indexing_preflight_by_tenant"].keys()) == tenants
    assert any("SYNDICATION[alpha]:" in e for e in errs5)


def test_dynamic_concurrency_scaling_and_ram_safe_chrome_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Verifies DEFAULT_CONCURRENCY_CEILING / compute_default_concurrency_ceiling and
    cli.compute_audit_tenant_workers scale to 4 on a 10-core host, clamp safely on
    low-RAM or low-CPU hosts, honor env overrides, and cap Chrome worker budgets.
    """
    import pseofactory.cli as cli_mod
    import pseofactory.supervisor as sup_mod

    # Clean env overrides
    for k in (
        "PSEUFACTORY_CONCURRENCY_CEILING",
        "PSEOFACTORY_CONCURRENCY_CEILING",
        "PSEUFACTORY_AUDIT_TENANT_WORKERS",
        "PSEOFACTORY_AUDIT_TENANT_WORKERS",
    ):
        monkeypatch.delenv(k, raising=False)

    # 10 cores, 12 GiB RAM -> ceiling=4
    monkeypatch.setattr(os, "cpu_count", lambda: 10)
    monkeypatch.setattr(sup_mod, "_get_available_ram_gb", lambda: 12.0)
    monkeypatch.setattr(cli_mod, "_get_available_ram_gb", lambda: 12.0)

    assert sup_mod.compute_default_concurrency_ceiling() == 4
    assert sup_mod.compute_default_concurrency_ceiling(tenant_count=50) == 4
    assert sup_mod.compute_default_concurrency_ceiling(tenant_count=2) == 2
    assert cli_mod.compute_audit_tenant_workers(4, use_parallel=True, run_browser=True) == 4
    assert cli_mod.compute_audit_tenant_workers(50, use_parallel=True, run_browser=True) == 4
    assert cli_mod.compute_audit_tenant_workers(4, use_parallel=False, run_browser=True) == 1

    # Explicit env override preserved
    monkeypatch.setenv("PSEUFACTORY_CONCURRENCY_CEILING", "3")
    assert sup_mod.compute_default_concurrency_ceiling() == 3
    coord = sup_mod.AsyncFleetCoordinator(registry=sup_mod.TenantRegistry())
    assert coord.concurrency_ceiling == 3

    monkeypatch.setenv("PSEUFACTORY_AUDIT_TENANT_WORKERS", "3")
    assert cli_mod.compute_audit_tenant_workers(4, use_parallel=True, run_browser=True) == 3

    # Low RAM (4 GiB) clamps RAM-safe ceiling to 2 even on 10 cores
    monkeypatch.delenv("PSEUFACTORY_CONCURRENCY_CEILING", raising=False)
    monkeypatch.delenv("PSEUFACTORY_AUDIT_TENANT_WORKERS", raising=False)
    monkeypatch.setattr(sup_mod, "_get_available_ram_gb", lambda: 4.0)
    monkeypatch.setattr(cli_mod, "_get_available_ram_gb", lambda: 4.0)
    assert sup_mod.compute_default_concurrency_ceiling() == 2
    assert cli_mod.compute_audit_tenant_workers(4, use_parallel=True, run_browser=True) == 2

    # Explicit concurrency_ceiling=2 still honored
    coord2 = sup_mod.AsyncFleetCoordinator(registry=sup_mod.TenantRegistry(), concurrency_ceiling=2)
    assert coord2.concurrency_ceiling == 2


def test_drift_stat_validated_caches_never_return_stale_hashes(tmp_path: Path) -> None:
    """
    Verifies compute_dist_lock_metrics, list_dist_lock_and_all_files, and
    compute_engine_hash return identical deterministic digests on cache hit and
    invalidate immediately on file modification (even same byte length), addition,
    or deletion.
    """
    import pseofactory.drift as drift_mod
    from pseofactory.drift import (
        clear_engine_hash_cache,
        compute_dist_lock_metrics,
        compute_engine_hash,
        list_dist_lock_and_all_files,
    )

    clear_engine_hash_cache()

    dist_dir = tmp_path / "tenant" / "dist"
    (dist_dir / "tools" / "calc-a").mkdir(parents=True, exist_ok=True)
    index_f = dist_dir / "index.html"
    calc_f = dist_dir / "tools" / "calc-a" / "index.html"
    index_f.write_text("<html><body>AAAA</body></html>", encoding="utf-8")
    calc_f.write_text("<html><body>Calc 1</body></html>", encoding="utf-8")

    # Excluded syndication directory must be ignored by compute_dist_lock_metrics
    syn_dir = dist_dir / "syndication"
    syn_dir.mkdir(parents=True, exist_ok=True)
    (syn_dir / "ignored.json").write_text('{"x":1}', encoding="utf-8")

    fp1, tot1 = compute_dist_lock_metrics(dist_dir)
    assert tot1 == 2
    fp1_cached, tot1_cached = compute_dist_lock_metrics(dist_dir)
    assert (fp1_cached, tot1_cached) == (fp1, tot1)

    lock_list, all_list = list_dist_lock_and_all_files(dist_dir, exclude_syndication=True)
    assert lock_list == ["dist/index.html", "dist/tools/calc-a/index.html"]
    assert all_list == lock_list

    # Same-length in-place modification must invalidate cache immediately
    time.sleep(0.01)
    index_f.write_text("<html><body>BBBB</body></html>", encoding="utf-8")
    fp2, tot2 = compute_dist_lock_metrics(dist_dir)
    assert tot2 == 2
    assert fp2 != fp1

    # Adding a new file must invalidate cache immediately
    extra_f = dist_dir / "sitemap.xml"
    extra_f.write_text("<urlset/>", encoding="utf-8")
    fp3, tot3 = compute_dist_lock_metrics(dist_dir)
    assert tot3 == 3
    assert fp3 != fp2

    # Deleting a file must invalidate cache immediately
    extra_f.unlink()
    fp4, tot4 = compute_dist_lock_metrics(dist_dir)
    assert tot4 == 2
    assert fp4 == fp2

    # Verify compute_engine_hash invalidates when an included file is added or removed
    inc_dir = tmp_path / "inc_pkg"
    inc_dir.mkdir(parents=True, exist_ok=True)
    f_a = inc_dir / "mod_a.py"
    f_a.write_text("X = 1\n", encoding="utf-8")
    eh1 = compute_engine_hash(include_paths=[inc_dir])
    assert compute_engine_hash(include_paths=[inc_dir]) == eh1

    time.sleep(0.01)
    f_a.write_text("X = 2\n", encoding="utf-8")
    eh2 = compute_engine_hash(include_paths=[inc_dir])
    assert eh2 != eh1

    f_b = inc_dir / "mod_b.py"
    f_b.write_text("Y = 1\n", encoding="utf-8")
    eh3 = compute_engine_hash(include_paths=[inc_dir])
    assert eh3 != eh2

    f_b.unlink()
    eh4 = compute_engine_hash(include_paths=[inc_dir])
    assert eh4 == eh2
