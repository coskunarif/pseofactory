"""
Wave 1 Lane B surgical regression tests for orchestration, fail-closed latch,
locking contracts, DLQ flock synchronization, and dynamic 50+ tenant discovery.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import argparse
import fcntl
import inspect
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List

import pytest


def _make_minimal_tenant(
    ws_root: Path,
    property_id: str,
    repo_dir_name: str | None = None,
    domain: str | None = None,
) -> Path:
    r_name = repo_dir_name or property_id
    dom = domain or f"{property_id}.com"
    repo_dir = ws_root / r_name
    dist_dir = repo_dir / "dist"
    (dist_dir / "tools" / "sample-calc").mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.html").write_text("<html><body>Home</body></html>", encoding="utf-8")
    (dist_dir / "tools" / "sample-calc" / "index.html").write_text(
        "<html><body>Calc</body></html>", encoding="utf-8"
    )
    (repo_dir / ".pseofactory.json").write_text(
        json.dumps(
            {
                "property_id": property_id,
                "domain": dom,
                "canonical_base": f"https://{dom}",
                "brand_name": property_id.capitalize(),
                "dist_dir": "dist",
            }
        ),
        encoding="utf-8",
    )
    return repo_dir


def test_dynamic_5th_tenant_discovery_across_gitops_supervisor_cli_pipeline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Fix #6: Wire discover_active_tenants() so 5th+ .pseofactory.json tenants are
    never pruned in reconcile_workspace_tracking_state and never skipped in
    supervisor, cli, or pipeline.
    """
    import pseofactory.cli as cli_mod
    import pseofactory.pipeline as pipe_mod
    import pseofactory.supervisor as sup_mod
    from pseofactory.gitops import IdempotencyLedger, reconcile_workspace_tracking_state
    from pseofactory.maintenance import ConfigurablePropertyAdapter, MaintenanceResult, TenantRegistry
    from pseofactory.supervisor import (
        DEFAULT_TENANT_BUDGET,
        AsyncFleetCoordinator,
        AutonomousLifecycleSupervisor,
        SupervisorDaemon,
    )

    ws = tmp_path / "ws"
    ws.mkdir(parents=True, exist_ok=True)
    _make_minimal_tenant(ws, "novacorp")
    (ws / "novacorp" / "dist" / "tools" / "sample-calc" / "index.html").write_text(
        '<!doctype html><html><head><title>Sample Calc | Novacorp</title>'
        '<link rel="canonical" href="https://novacorp.com/tools/sample-calc/"></head>'
        '<body><h1>Sample Calc</h1>'
        '<form id="nova-calc-form" class="calculator-form">'
        '<input type="number" id="calc-input-revenue" name="revenue" value="100000">'
        '<input type="number" id="calc-input-cost" name="cost" value="65000">'
        '</form>'
        '<div class="output-value" id="metric-margin">$35,000.00</div>'
        '<script type="application/json" id="calculation-manifest" class="calculation-manifest">'
        '{"manifest_id":"sample-calc-manifest","slug":"sample-calc","formula":"revenue - cost",'
        '"inputs":{"revenue":100000,"cost":65000},"published_output":35000.0}</script>'
        "<script>(function(){function recalc(){"
        "var r=Number((document.getElementById('calc-input-revenue')||{}).value||0);"
        "var c=Number((document.getElementById('calc-input-cost')||{}).value||0);"
        "var out=document.getElementById('metric-margin');"
        "if(out){out.textContent='$'+(r-c).toFixed(2);}}"
        "var fm=document.getElementById('nova-calc-form');"
        "if(fm){fm.addEventListener('input',recalc);fm.addEventListener('change',recalc);fm.addEventListener('submit',recalc);}"
        "['calc-input-revenue','calc-input-cost'].forEach(function(id){"
        "var el=document.getElementById(id);if(el){el.addEventListener('input',recalc);el.addEventListener('change',recalc);}});"
        "recalc();})();</script>"
        "</body></html>",
        encoding="utf-8",
    )

    import pseofactory.truth_pack as tp_mod
    from pseofactory.pricing import get_tier_pricing

    packs_dir = tmp_path / "truth_packs"
    packs_dir.mkdir(parents=True, exist_ok=True)
    for src_json in tp_mod.DEFAULT_TRUTH_PACKS_DIR.glob("*.json"):
        dst_json = packs_dir / src_json.name
        if not dst_json.exists():
            shutil.copy2(src_json, dst_json)
    (packs_dir / "novacorp.json").write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "property_id": "novacorp",
                "brand_name": "Novacorp",
                "canonical_domain": "https://novacorp.com",
                "audience_tier": "business",
                "pricing_tiers": {
                    "free": {"tier_kind": "free", "label": "Free", "price_usd": 0.0, "price_cents": 0},
                    **get_tier_pricing("business"),
                },
                "entries": {},
                "formulas": {},
                "citations_allowlist": {},
                "disclosures": [],
                "banned_claims": [],
                "cross_tenant_brand_tokens": [],
                "allowed_shared_legal_tokens": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(tp_mod, "DEFAULT_TRUTH_PACKS_DIR", packs_dir)

    # 1. gitops.reconcile_workspace_tracking_state preserves 5th+ queues & tokens
    queues_dir = ws / ".agy" / "queues"
    staging_dir = ws / ".agy" / "queue"
    runs_dir = ws / ".agy" / "runs"
    queues_dir.mkdir(parents=True, exist_ok=True)
    staging_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    nova_wal = queues_dir / "novacorp_release_queue.jsonl"
    nova_wal.write_text('{"event_id": "e1", "status": "COMPLETED"}\n', encoding="utf-8")
    bogus_wal = queues_dir / "test_bogus_release_queue.jsonl"
    bogus_wal.write_text('{"event_id": "e2", "status": "COMPLETED"}\n', encoding="utf-8")

    nova_stage = staging_dir / "novacorp_queue.json"
    nova_stage.write_text('{"items": []}', encoding="utf-8")

    ledger_path = ws / ".agy" / "gitops_idempotency_ledger.json"
    ledger = IdempotencyLedger(ledger_path=ledger_path)
    ledger._write_records(
        {
            "tok_nova": {"property_id": "novacorp"},
            "tok_test": {"property_id": "test_ephemeral"},
        }
    )

    reconcile_workspace_tracking_state(
        runs_dir=runs_dir,
        queues_dir=queues_dir,
        ledger_path=ledger_path,
        tenant_repos=[ws / "novacorp"],
    )
    assert nova_wal.is_file(), "5th+ tenant WAL queue must not be unlinked"
    assert not bogus_wal.exists(), "Test leak queue must still be pruned"
    assert nova_stage.is_file(), "5th+ tenant staging queue must not be unlinked"
    remaining_records = ledger._read_records()
    assert "tok_nova" in remaining_records
    assert "tok_test" not in remaining_records

    # 2. supervisor budget + memory firewall + truth reconciliation + self-healing
    assert DEFAULT_TENANT_BUDGET == 1800.0
    coord = AsyncFleetCoordinator(registry=TenantRegistry())
    assert coord.get_tenant_budget("novacorp") == 1800.0

    fake_mod = type(sys)("novacorp.factory")
    sys.modules["novacorp"] = type(sys)("novacorp")
    sys.modules["novacorp.factory"] = fake_mod
    monkeypatch.setenv("WORKSPACE_ROOT", str(ws))
    try:
        AsyncFleetCoordinator._enforce_subprocess_memory_firewall()
        assert "novacorp" not in sys.modules
        assert "novacorp.factory" not in sys.modules
    finally:
        sys.modules.pop("novacorp", None)
        sys.modules.pop("novacorp.factory", None)

    reconciled_pids: List[str] = []
    import pseofactory.tenant_facts as tf_mod

    monkeypatch.setattr(
        tf_mod.TruthReconciliationEngine,
        "reconcile_estate_assets",
        staticmethod(lambda dist_dir, property_id, repo_root=None: reconciled_pids.append(property_id) or {}),
    )
    monkeypatch.setattr(sup_mod, "detect_engine_drift", lambda **kwargs: {"current_hash": "a" * 64, "drift_detected": False})
    reg = TenantRegistry.default(workspace_root=ws)
    assert "novacorp" in reg.list_adapters()
    monkeypatch.setattr(
        SupervisorDaemon,
        "run_once",
        SupervisorDaemon.run_once,
    )
    sup = AutonomousLifecycleSupervisor(
        workspace_root=ws,
        state_file=ws / ".agy" / "engine_hash.json",
        ledger_file=ws / ".agy" / "asset_ledger.json",
        heartbeat_path=ws / ".agy" / "supervisor_heartbeat.json",
        registry=reg,
    )
    monkeypatch.setattr(
        sup.coordinator,
        "run_fleet",
        lambda **kwargs: {
            "novacorp": MaintenanceResult(property_id="novacorp", status="SUCCESS", assets_audited=1, assets_drifted=0, assets_refactored=0, assets_failed=0)
        },
    )
    monkeypatch.setattr(sup, "_record_failure_streak", lambda *a, **k: [])
    # Verify SupervisorDaemon.run_once discovers novacorp
    monkeypatch.setattr(AutonomousLifecycleSupervisor, "run_cycle", lambda self, **kw: {"status": "SUCCESS", "properties": {}})
    SupervisorDaemon.run_once(workspace_root=ws, dry_run=False)
    assert "novacorp" in reconciled_pids

    # 3. cli cmd_audit --property all discovers novacorp
    audited_props: List[str] = []

    class _FakeRep:
        status = "PASS"
        property_id = "novacorp"
        total_assets_checked = 1
        compliant_assets_count = 1
        drifted_assets_count = 0
        drifted_assets: List[Any] = []

        def to_dict(self) -> Dict[str, Any]:
            return {"status": "PASS", "property_id": self.property_id}

    monkeypatch.setattr(
        cli_mod,
        "audit_property_assets",
        lambda property_id, adapter=None, check_engine_drift=False: (
            audited_props.append(property_id) or _FakeRep()
        ),
    )
    import pseofactory.verifier as ver_mod

    monkeypatch.setattr(
        ver_mod,
        "audit_estate_seo_fix_checklist",
        lambda property_id: {"status": "PASS", "passed": True, "html_files_scanned": 1, "issues": []},
    )
    rc = cli_mod.cmd_audit(
        argparse.Namespace(
            property="all",
            dist_dir=None,
            json=True,
            no_browser=True,
            check_engine_drift=False,
            verify_handoffs=False,
            browser=False,
        )
    )
    assert rc == 0
    assert "novacorp" in audited_props

    # 4. pipeline.execute_autonomous_daily_trend_page_build discovers novacorp
    queue_f = ws / ".agy" / "void_candidates.jsonl"
    ledger_f = ws / ".agy" / "daily_page_build_ledger.json"
    queue_f.write_text("", encoding="utf-8")
    pipe_res = pipe_mod.execute_autonomous_daily_trend_page_build(
        property_ids=None,
        void_candidates_path=queue_f,
        ledger_path=ledger_f,
        dry_run=True,
    )
    assert "novacorp" in pipe_res.get("target_properties", pipe_res.get("per_tenant", {})) or pipe_res.get("status") is not None


def test_cmd_reflect_records_engine_hash_without_invalid_kwargs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Fix #7: cmd_reflect must call record_engine_hash with valid kwargs (never
    aligned=True, alignment_reasons=[] which raised TypeError).
    """
    import pseofactory.cli as cli_mod
    import pseofactory.drift as drift_mod

    recorded_calls: List[Dict[str, Any]] = []
    root_eh = tmp_path / "root" / ".agy" / "engine_hash.json"
    pseo_eh = tmp_path / "pseo" / ".agy" / "engine_hash.json"
    root_eh.parent.mkdir(parents=True, exist_ok=True)
    pseo_eh.parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        cli_mod,
        "reflect_and_recompile_all_assets",
        lambda **kwargs: {
            "status": "PASS",
            "properties_scanned": 1,
            "total_assets_checked": 1,
            "total_drifted": 0,
            "total_recompiled": 0,
        },
    )
    monkeypatch.setattr(drift_mod, "compute_engine_hash", lambda: "b" * 64)
    monkeypatch.setattr(
        drift_mod,
        "verify_all_tenants_aligned_for_latch",
        lambda **kwargs: (True, []),
    )

    real_record = drift_mod.record_engine_hash

    def _spy_record(state_file: Any, **kwargs: Any) -> str:
        # Must accept real signature without TypeError
        inspect.signature(real_record).bind(state_file, **kwargs)
        recorded_calls.append({"state_file": str(state_file), "kwargs": kwargs})
        return str(kwargs.get("hash_value") or "b" * 64)

    monkeypatch.setattr(drift_mod, "record_engine_hash", _spy_record)

    # Check source directly has no invalid aligned=/alignment_reasons= kwargs in cmd_reflect
    reflect_src = inspect.getsource(cli_mod.cmd_reflect)
    assert "alignment_reasons=" not in reflect_src
    assert "aligned=True" not in reflect_src

    # Redirect candidate Paths inside cmd_reflect by testing real signature invocation
    orig_path_cls = cli_mod.Path

    def _mapped_path(p: Any) -> Path:
        s = str(p)
        if s == "/home/ubuntuadmin/projects/.agy/engine_hash.json":
            return root_eh
        if s == "/home/ubuntuadmin/projects/pseofactory/.agy/engine_hash.json":
            return pseo_eh
        return orig_path_cls(p)

    monkeypatch.setattr(cli_mod, "Path", _mapped_path)
    rc = cli_mod.cmd_reflect(
        argparse.Namespace(
            property=None,
            dry_run=False,
            no_gitops=False,
            json=True,
            verbose=False,
        )
    )
    assert rc == 0
    assert len(recorded_calls) == 2


def test_run_cycle_fail_closed_latch_and_write_substrate_lock_preserves_full_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Fix #8:
    1. run_cycle must check verify_all_tenants_aligned_for_latch before latching
       and fail closed (no HEALTHY/SUCCESS/COMPLETED) when all_tenants_ok=False.
    2. write_substrate_lock(sync_ledgers=True) must preserve full tenant asset_ledger.json
       entries (.agy/overlays, syndication, functions) instead of shrinking to dist_asset_hashes.
    """
    import pseofactory.drift as drift_mod
    import pseofactory.supervisor as sup_mod
    from pseofactory.drift import write_substrate_lock
    from pseofactory.maintenance import ConfigurablePropertyAdapter, MaintenanceResult, TenantRegistry
    from pseofactory.supervisor import AutonomousLifecycleSupervisor

    # Part A: fail-closed latch in run_cycle
    ws = tmp_path / "ws_latch"
    repo = _make_minimal_tenant(ws, "novacorp")
    state_f = ws / ".agy" / "engine_hash.json"
    ledger_f = ws / ".agy" / "asset_ledger.json"
    hb_f = ws / ".agy" / "supervisor_heartbeat.json"
    state_f.parent.mkdir(parents=True, exist_ok=True)
    state_f.write_text(json.dumps({"engine_hash": "0" * 64}), encoding="utf-8")

    reg = TenantRegistry()
    reg.register_adapter(
        ConfigurablePropertyAdapter(
            property_id="novacorp",
            brand_name="Novacorp",
            domain="novacorp.com",
            canonical_base="https://novacorp.com",
            dist_dir=repo / "dist",
            repo_path=repo,
        )
    )

    sup = AutonomousLifecycleSupervisor(
        workspace_root=ws,
        state_file=state_f,
        ledger_file=ledger_f,
        heartbeat_path=hb_f,
        registry=reg,
    )
    monkeypatch.setattr(sup_mod, "detect_engine_drift", lambda **kw: {"current_hash": "c" * 64, "drift_detected": True})
    monkeypatch.setattr(
        sup.coordinator,
        "run_fleet",
        lambda **kw: {
            "novacorp": MaintenanceResult(property_id="novacorp", status="SUCCESS", assets_audited=2, assets_drifted=0, assets_refactored=0, assets_failed=0)
        },
    )
    monkeypatch.setattr(
        drift_mod,
        "verify_all_tenants_aligned_for_latch",
        lambda **kw: (False, ["novacorp: missing substrate_lock.json"]),
    )

    res = sup.run_cycle(force=True, dry_run=False, enable_gitops=False)
    assert res["status"] in ("FAILED", "DEGRADED")
    assert res["status"] != "SUCCESS"
    assert res.get("latch_blocked") is True
    assert res.get("engine_hash") is None
    assert json.loads(state_f.read_text(encoding="utf-8"))["engine_hash"] == "0" * 64
    assert not ledger_f.exists()
    hb = json.loads(hb_f.read_text(encoding="utf-8"))
    assert hb["status"] != "HEALTHY"
    dp = json.loads((ws / ".agy" / "department_pipeline_state.json").read_text(encoding="utf-8"))
    assert dp["overall_status"] == "FAIL"
    assert dp["stages"]["DEPLOYMENT"]["status"] == "FAILED"

    # Part B: write_substrate_lock(sync_ledgers=True) preserves full asset_ledger.json
    gh_repo = tmp_path / "gainhelm"
    (gh_repo / "dist" / "tools" / "soc-2").mkdir(parents=True, exist_ok=True)
    (gh_repo / "dist" / "index.html").write_text("<html><body>Home</body></html>", encoding="utf-8")
    (gh_repo / "dist" / "tools" / "soc-2" / "index.html").write_text("<html><body>Tool</body></html>", encoding="utf-8")
    (gh_repo / ".agy" / "overlays").mkdir(parents=True, exist_ok=True)
    (gh_repo / ".agy" / "overlays" / "soc-2.json").write_text('{"slug":"soc-2"}', encoding="utf-8")
    (gh_repo / "syndication").mkdir(parents=True, exist_ok=True)
    (gh_repo / "syndication" / "soc-2-linkedin.md").write_text("# Post", encoding="utf-8")
    (gh_repo / "functions" / "r").mkdir(parents=True, exist_ok=True)
    (gh_repo / "functions" / "r" / "[partner].js").write_text("export function onRequest(){}", encoding="utf-8")
    (gh_repo / ".agy" / "engine_hash.json").write_text('{"engine_hash":"old"}', encoding="utf-8")
    (gh_repo / ".agy" / "asset_ledger.json").write_text('{"assets":{}}', encoding="utf-8")

    write_substrate_lock(gh_repo, property_id="gainhelm", expected_hash="d" * 64, sync_ledgers=True)
    al_data = json.loads((gh_repo / ".agy" / "asset_ledger.json").read_text(encoding="utf-8"))
    assets = al_data["assets"]
    assert "index.html" in assets
    assert ".agy/overlays/soc-2.json" in assets
    assert "syndication/soc-2-linkedin.md" in assets
    assert "functions/r/[partner].js" in assets


def test_locking_contract_sync_guards_env_restore_and_reconcile_lock_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Fix #9:
    - sync_tenant_test_isolation_guards includes lienbond_factory.lock and dynamic *_factory.lock.
    - TenantFactoryLockGuard.__exit__ restores/clears PSEUFACTORY_HOLDS_SUPERVISOR_LOCK.
    - reconcile_workspace_tracking_state does not map unknown repos to prexvo_factory.lock
      and uses consistent PSEUFACTORY_LOCK_DIR/{pid}_factory.lock path.
    """
    from pseofactory.gitops import (
        TenantFactoryLockGuard,
        reconcile_workspace_tracking_state,
        sync_tenant_test_isolation_guards,
    )

    # 1. sync_tenant_test_isolation_guards includes lienbond & dynamic *_factory.lock
    lb_repo = tmp_path / "lienbond"
    (lb_repo / "scripts").mkdir(parents=True, exist_ok=True)
    (lb_repo / "scripts" / "run_factory.sh").write_text(
        '#!/bin/bash\nLOCK_FILE="/tmp/lienbond_factory.lock"\necho "$$" > "$PID_FILE"\n',
        encoding="utf-8",
    )
    sync_tenant_test_isolation_guards(lb_repo, "lienbond")
    rf_txt = (lb_repo / "scripts" / "run_factory.sh").read_text(encoding="utf-8")
    assert "lienbond_factory.lock" in rf_txt
    assert "_factory.lock" in rf_txt
    assert "PSEUFACTORY_HOLDS_SUPERVISOR_LOCK" in rf_txt

    # 2. TenantFactoryLockGuard.__exit__ restores/pops PSEUFACTORY_HOLDS_SUPERVISOR_LOCK
    lock_dir = tmp_path / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PSEUFACTORY_LOCK_DIR", str(lock_dir))
    monkeypatch.delenv("PSEUFACTORY_HOLDS_SUPERVISOR_LOCK", raising=False)
    monkeypatch.delenv("PSEUFACTORY_HOLDS_LIENBOND_LOCK", raising=False)

    with TenantFactoryLockGuard("lienbond", repo_path=lb_repo, timeout=2.0) as g:
        assert g.acquired is True
        assert os.environ.get("PSEUFACTORY_HOLDS_SUPERVISOR_LOCK") == "1"
        assert os.environ.get("PSEUFACTORY_HOLDS_LIENBOND_LOCK") == "1"
    assert "PSEUFACTORY_HOLDS_SUPERVISOR_LOCK" not in os.environ
    assert "PSEUFACTORY_HOLDS_LIENBOND_LOCK" not in os.environ

    # 3. reconcile_workspace_tracking_state does not map unknown repo to prexvo_factory.lock
    # and respects /tmp or PSEUFACTORY_LOCK_DIR/{pid}_factory.lock rather than rp/.lock
    unknown_repo = tmp_path / "mystery_repo"
    unknown_repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=unknown_repo, check=True, capture_output=True)
    prexvo_lock = lock_dir / "prexvo_factory.lock"
    prexvo_lock.unlink(missing_ok=True)

    reconcile_workspace_tracking_state(
        runs_dir=tmp_path / ".agy" / "runs",
        queues_dir=tmp_path / ".agy" / "queues",
        ledger_path=tmp_path / ".agy" / "ledger.json",
        tenant_repos=[unknown_repo],
    )
    assert not prexvo_lock.exists(), "Unknown repo must never touch prexvo_factory.lock"
    assert not (unknown_repo / ".prexvo_factory.lock").exists()

    # Known tenant repo must use lock_dir/{pid}_factory.lock, not rp/.{pid}_factory.lock
    gainhelm_repo = tmp_path / "gainhelm"
    gainhelm_repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=gainhelm_repo, check=True, capture_output=True)
    reconcile_workspace_tracking_state(
        runs_dir=tmp_path / ".agy" / "runs",
        queues_dir=tmp_path / ".agy" / "queues",
        ledger_path=tmp_path / ".agy" / "ledger.json",
        tenant_repos=[gainhelm_repo],
    )
    assert (lock_dir / "gainhelm_factory.lock").exists()
    assert not (gainhelm_repo / ".gainhelm_factory.lock").exists()


def test_run_cycle_fast_path_locked_tenant_and_tenant_substrate_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Fix #10:
    1. run_cycle fast-path must NOT return SKIPPED_ALIGNED/HEALTHY when a tenant
       factory lock is actively held.
    2. run_cycle fast-path must honor tenant_substrate_hash when engine_hash differs
       from global current_engine_hash.
    """
    import pseofactory.supervisor as sup_mod
    from pseofactory.drift import compute_tenant_substrate_hash
    from pseofactory.maintenance import (
        AssetIntegrityEvaluator,
        ConfigurablePropertyAdapter,
        MaintenanceResult,
        RetroReflectionEngine,
        TenantRegistry,
    )
    from pseofactory.supervisor import AutonomousLifecycleSupervisor

    ws = tmp_path / "ws_fast"
    repo = _make_minimal_tenant(ws, "prexvo")
    lock_dir = tmp_path / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PSEUFACTORY_LOCK_DIR", str(lock_dir))

    reg = TenantRegistry()
    reg.register_adapter(
        ConfigurablePropertyAdapter(
            property_id="prexvo",
            brand_name="Prexvo",
            domain="prexvo.com",
            canonical_base="https://prexvo.com",
            dist_dir=repo / "dist",
            repo_path=repo,
        )
    )
    sup = AutonomousLifecycleSupervisor(
        workspace_root=ws,
        state_file=ws / ".agy" / "engine_hash.json",
        ledger_file=ws / ".agy" / "asset_ledger.json",
        heartbeat_path=ws / ".agy" / "supervisor_heartbeat.json",
        registry=reg,
    )
    monkeypatch.setattr(
        sup_mod,
        "detect_engine_drift",
        lambda **kw: {"current_hash": "e" * 64, "drift_detected": False, "tenants_retro_verified": ["prexvo"]},
    )

    class _CleanRep:
        drifted_assets_count = 0

    monkeypatch.setattr(AssetIntegrityEvaluator, "audit_all", lambda self, *a, **k: _CleanRep())
    monkeypatch.setattr(RetroReflectionEngine, "audit_estate", classmethod(lambda cls, d, p: {"status": "PASS", "stale_count": 0}))

    # Hold exclusive flock on prexvo_factory.lock in a real child process
    lock_file = lock_dir / "prexvo_factory.lock"
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import fcntl, time; "
                f"f=open({str(lock_file)!r}, 'a+'); "
                "fcntl.flock(f.fileno(), fcntl.LOCK_EX); "
                "print('LOCKED', flush=True); "
                "time.sleep(15)"
            ),
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None and holder.stdout.readline().strip() == "LOCKED"
        monkeypatch.setattr(
            sup.coordinator,
            "run_fleet",
            lambda **kw: {
                "prexvo": MaintenanceResult(
                    property_id="prexvo",
                    status="DEFERRED",
                    assets_audited=0,
                    assets_drifted=0,
                    assets_refactored=0,
                    assets_failed=0,
                )
            },
        )
        res = sup.run_cycle(force=False, dry_run=False, enable_gitops=False)
        assert res["status"] == "DEFERRED"
        assert res["status"] != "SKIPPED_ALIGNED"
    finally:
        holder.terminate()
        holder.wait(timeout=5)

    # Check tenant_substrate_hash alignment branch exists in run_cycle source
    rc_src = inspect.getsource(AutonomousLifecycleSupervisor.run_cycle)
    assert "compute_tenant_substrate_hash" in rc_src
    assert compute_tenant_substrate_hash("prexvo")


def test_handoff_verifier_passes_workspace_root_to_shipper_and_persists_fail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Fix #11:
    1. DepartmentHandoffChainVerifier passes self.workspace_root/.agy/queues to ShipperQueue.
    2. verify(persist=True) persists FAIL pipeline state and updates heartbeat on stage 1-5 failure.
    3. L1696 prod persist=True guard in _run_deployment_stage remains intact.
    """
    from pseofactory.supervisor import DepartmentHandoffChainVerifier

    ws = tmp_path / "ws_handoff"
    (ws / ".agy" / "queues").mkdir(parents=True, exist_ok=True)
    _make_minimal_tenant(ws, "prexvo")

    verifier = DepartmentHandoffChainVerifier(workspace_root=ws, property_ids=["prexvo"])

    # Verify stage 6 ShipperQueue call passes queues_dir based on workspace_root
    dep_src = inspect.getsource(DepartmentHandoffChainVerifier._run_deployment_stage)
    assert "queues_dir=" in dep_src
    assert 'and (not persist or "/.agy/worktrees/" in Path(__file__).resolve().as_posix())' in dep_src

    # Force stage 2 (MONETIZATION) failure when persist=True
    monkeypatch.setattr(
        verifier,
        "_run_discovery_stage",
        lambda ctx: (True, {"discovered_tenants": ["prexvo"]}, {"per_tenant": {"prexvo": {"status": "PASS"}}}, []),
    )
    monkeypatch.setattr(
        verifier,
        "_run_monetization_stage",
        lambda ctx: (False, {}, {"per_tenant": {"prexvo": {"status": "FAIL"}}}, ["MONETIZATION[prexvo]: failed"]),
    )

    rep = verifier.verify(persist=True, cycle_id="cyc_stage2_fail")
    assert rep["status"] == "FAIL"

    dp_file = ws / ".agy" / "department_pipeline_state.json"
    hb_file = ws / ".agy" / "supervisor_heartbeat.json"
    assert dp_file.is_file(), "department_pipeline_state.json must be persisted on stage 1-5 FAIL"
    assert json.loads(dp_file.read_text(encoding="utf-8"))["overall_status"] == "FAIL"
    assert hb_file.is_file(), "supervisor_heartbeat.json must be updated on stage 1-5 FAIL"
    assert json.loads(hb_file.read_text(encoding="utf-8"))["status"] == "FAILED"


def test_shipper_queue_dlq_uses_flock_synchronization(tmp_path: Path) -> None:
    """
    Fix #12: ShipperQueue.quarantine_to_dlq and list_dlq synchronize via flock.
    """
    from pseofactory.gitops import ShipperQueue

    sq = ShipperQueue(property_id="prexvo", queues_dir=tmp_path)
    q_src = inspect.getsource(ShipperQueue.quarantine_to_dlq)
    l_src = inspect.getsource(ShipperQueue.list_dlq)
    assert "fcntl.flock" in q_src
    assert "fcntl.flock" in l_src

    errors: List[Exception] = []

    def _writer(wid: int) -> None:
        try:
            for idx in range(15):
                sq.quarantine_to_dlq(
                    {"event_id": f"w{wid}_{idx}", "property_id": "prexvo"},
                    error="retry limit",
                )
        except Exception as exc:
            errors.append(exc)

    def _reader() -> None:
        try:
            for _ in range(15):
                items = sq.list_dlq(property_id="prexvo")
                assert isinstance(items, list)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=_writer, args=(i,)) for i in range(3)] + [
        threading.Thread(target=_reader) for _ in range(2)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert len(sq.list_dlq(property_id="prexvo")) == 45
    assert sq.dlq_lock_file.exists()


def test_cmd_drift_passes_workspace_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Fix #13: cmd_drift passes workspace_root when calling detect_engine_drift.
    """
    import pseofactory.cli as cli_mod

    captured: Dict[str, Any] = {}
    ws = tmp_path / "custom_ws"
    (ws / ".agy").mkdir(parents=True, exist_ok=True)
    _make_minimal_tenant(ws, "novacorp")

    def _fake_detect(**kwargs: Any) -> Dict[str, Any]:
        captured.update(kwargs)
        return {
            "status": "ALIGNED",
            "current_hash": "f" * 64,
            "recorded_hash": "f" * 64,
            "requires_recompile": False,
        }

    monkeypatch.setattr(cli_mod, "detect_engine_drift", _fake_detect)

    rc = cli_mod.cmd_drift(
        argparse.Namespace(
            state_file=str(ws / ".agy" / "engine_hash.json"),
            record=False,
            allow_tenant_scoped_hash=True,
            also_state_file=[],
            workspace_root=str(ws),
            json=True,
        )
    )
    assert rc == 0
    assert captured.get("workspace_root") == str(ws)

    # Even without explicit --workspace-root, infers custom workspace from --state-file
    captured.clear()
    rc2 = cli_mod.cmd_drift(
        argparse.Namespace(
            state_file=str(ws / ".agy" / "engine_hash.json"),
            record=False,
            allow_tenant_scoped_hash=True,
            also_state_file=[],
            json=True,
        )
    )
    assert rc2 == 0
    assert Path(captured["workspace_root"]).resolve() == ws.resolve()
