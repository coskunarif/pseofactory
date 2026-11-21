"""
Step 4 Verification Suite: Tenant Isolation, Concurrency Locking, Impact Planner,
and Parallel Reflection / Release Cascade Hardening.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest

from pseofactory.action_bus import HumanActionBus
from pseofactory.affiliates_hub import MonetizationHub
from pseofactory.browser_verifier import compute_auto_worker_count
from pseofactory.drift import (
    compute_dist_lock_metrics,
    compute_engine_hash,
    compute_tenant_substrate_hash,
    verify_all_tenants_aligned_for_latch,
    write_substrate_lock,
)
from pseofactory.email_ingest import EmailIngestionEngine
from pseofactory.gitops import IdempotencyLedger
from pseofactory.impact_planner import (
    get_tenant_engine_file_partition,
    plan_tenant_impact,
)
from pseofactory.maintenance import (
    AssetIntegrityEvaluator,
    PropertyAdapter,
)
from pseofactory.trends.db import GSCDailyMetricRecord, TrendHistoryDB


REPO_ROOT = Path(__file__).resolve().parent.parent
RELEASE_PIPELINE_PATH = Path("/home/ubuntuadmin/projects/.agy/release_pipeline.sh")


class _StubPropertyAdapter(PropertyAdapter):
    """Minimal concrete PropertyAdapter for isolated concurrency and cache tests."""

    def __init__(
        self,
        property_id: str,
        domain: str,
        brand_name: str,
        dist_dir: Path,
        repo_path: Path,
    ):
        self._property_id = property_id
        self._domain = domain
        self._brand_name = brand_name
        self._dist_dir = dist_dir
        self._repo_path = repo_path
        self._canonical_base = f"https://{domain}"
        self._linkedin_company_id = f"li-{property_id}"

    @property
    def property_id(self) -> str:
        return self._property_id

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def brand_name(self) -> str:
        return self._brand_name

    @property
    def canonical_base(self) -> str:
        return self._canonical_base

    @property
    def dist_dir(self) -> Path:
        return self._dist_dir

    @property
    def repo_path(self) -> Path:
        return self._repo_path

    @property
    def linkedin_company_id(self) -> str:
        return self._linkedin_company_id

    def build_asset(self, slug: str, target_file: Path | None = None) -> bool:
        return True

    def build_all(self) -> bool:
        return True


def _run_py_worker(code: str, env_extra: Dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        timeout=45,
    )


# ------------------------------------------------------------------------------
# Group 1: scoped_environment 4-thread isolation + same-thread re-entry
# ------------------------------------------------------------------------------


def test_scoped_environment_four_thread_isolation_and_reentry(tmp_path: Path) -> None:
    tenants = [
        ("profithelm", "profithelm.com", "ProfitHelm"),
        ("prexvo", "prexvo.com", "Prexvo"),
        ("gainhelm", "gainhelm.com", "GainHelm"),
        ("lienbond", "lienbond.com", "LienBond"),
    ]
    adapters = [
        _StubPropertyAdapter(
            property_id=pid,
            domain=dom,
            brand_name=brand,
            dist_dir=tmp_path / pid / "dist",
            repo_path=tmp_path / pid,
        )
        for pid, dom, brand in tenants
    ]

    baseline_domain = os.environ.get("FACTORY_DOMAIN")
    baseline_brand = os.environ.get("FACTORY_BRAND_NAME")
    barrier = threading.Barrier(len(adapters))
    bleed_errors: List[str] = []

    def _worker(adp: _StubPropertyAdapter) -> None:
        barrier.wait()
        for _ in range(15):
            with adp.scoped_environment():
                time.sleep(0.002)
                obs_dom = os.environ.get("FACTORY_DOMAIN")
                obs_brand = os.environ.get("FACTORY_BRAND_NAME")
                obs_base = os.environ.get("FACTORY_CANONICAL_BASE")
                obs_dist = os.environ.get("FACTORY_DIST_DIR")
                if obs_dom != adp.domain or obs_brand != adp.brand_name or obs_base != adp.canonical_base or obs_dist != str(adp.dist_dir):
                    bleed_errors.append(
                        f"bleed for {adp.property_id}: dom={obs_dom} brand={obs_brand} base={obs_base}"
                    )

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futs = [pool.submit(_worker, adp) for adp in adapters]
        for fut in futs:
            fut.result()

    assert not bleed_errors, f"Cross-tenant os.environ bleed detected: {bleed_errors[:5]}"
    assert os.environ.get("FACTORY_DOMAIN") == baseline_domain
    assert os.environ.get("FACTORY_BRAND_NAME") == baseline_brand

    # Same-thread nested re-entry via RLock must unwind cleanly
    outer, inner = adapters[0], adapters[2]
    with outer.scoped_environment():
        assert os.environ.get("FACTORY_DOMAIN") == outer.domain
        with inner.scoped_environment():
            assert os.environ.get("FACTORY_DOMAIN") == inner.domain
            assert os.environ.get("FACTORY_BRAND_NAME") == inner.brand_name
        assert os.environ.get("FACTORY_DOMAIN") == outer.domain
        assert os.environ.get("FACTORY_BRAND_NAME") == outer.brand_name
    assert os.environ.get("FACTORY_DOMAIN") == baseline_domain
    assert os.environ.get("FACTORY_BRAND_NAME") == baseline_brand


# ------------------------------------------------------------------------------
# Group 2: IdempotencyLedger 8-subprocess atomicity & zero lost updates
# ------------------------------------------------------------------------------


def test_idempotency_ledger_eight_subprocess_atomicity_and_distinct_tokens(tmp_path: Path) -> None:
    same_ledger = tmp_path / "same_token_ledger.json"
    worker_code_same = f"""
import json
from pseofactory.gitops import IdempotencyLedger
ledger = IdempotencyLedger({str(same_ledger)!r})
dup = ledger.check_and_record("shared-release-token-42", {{"worker": "race"}})
print(json.dumps({{"duplicate": dup}}))
"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        procs = list(pool.map(lambda _: _run_py_worker(worker_code_same), range(8)))

    for p in procs:
        assert p.returncode == 0, f"Worker failed: {p.stderr}"
    results = [json.loads(p.stdout.strip())["duplicate"] for p in procs]
    assert results.count(False) == 1, f"Expected exactly 1 False (winner), got {results}"
    assert results.count(True) == 7, f"Expected exactly 7 True (duplicates), got {results}"
    loaded = json.loads(same_ledger.read_text(encoding="utf-8"))
    assert "shared-release-token-42" in loaded

    distinct_ledger = tmp_path / "distinct_tokens_ledger.json"

    def _run_distinct(idx: int) -> subprocess.CompletedProcess[str]:
        code = f"""
from pseofactory.gitops import IdempotencyLedger
ledger = IdempotencyLedger({str(distinct_ledger)!r})
dup = ledger.check_and_record("distinct-token-{idx}", {{"idx": {idx}}})
assert dup is False
"""
        return _run_py_worker(code)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        d_procs = list(pool.map(_run_distinct, range(8)))

    for p in d_procs:
        assert p.returncode == 0, f"Distinct worker failed: {p.stderr}"
    d_loaded = json.loads(distinct_ledger.read_text(encoding="utf-8"))
    assert len(d_loaded) == 8
    for i in range(8):
        assert f"distinct-token-{i}" in d_loaded


# ------------------------------------------------------------------------------
# Group 3: AssetIntegrityEvaluator per-property memory + disk cache isolation
# ------------------------------------------------------------------------------


def test_asset_integrity_evaluator_per_property_cache_isolation(tmp_path: Path) -> None:
    shared_dist = tmp_path / "shared_dist"
    shared_dist.mkdir(parents=True)
    html_file = shared_dist / "index.html"
    # Contains profithelm.com canonical + content; clean for profithelm, contaminated for gainhelm
    html_file.write_text(
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        "<meta name='description' content='ProfitHelm corporate tax modeling hub for CFOs and business owners.'>"
        "<link rel='canonical' href='https://profithelm.com/'>"
        "<title>Corporate Tax Modeling Hub | ProfitHelm</title></head>"
        "<body><main><h1>ProfitHelm Corporate Tax Hub</h1>"
        "<p>Statutory IRC Section 179 and 1031 exchange tax calculations for ProfitHelm users.</p>"
        "</main></body></html>",
        encoding="utf-8",
    )

    ph_adp = _StubPropertyAdapter("profithelm", "profithelm.com", "ProfitHelm", shared_dist, tmp_path / "ph")
    gh_adp = _StubPropertyAdapter("gainhelm", "gainhelm.com", "GainHelm", shared_dist, tmp_path / "gh")

    evaluator = AssetIntegrityEvaluator(enforce_master_seo=False)
    evaluator._audit_cache.clear()
    evaluator._fingerprint_cache.clear()

    # Seed clean cache entry strictly under profithelm 4-tuple key
    st = html_file.stat()
    ph_key = ("profithelm", str(html_file.resolve()), st.st_mtime, st.st_size)
    gh_key = ("gainhelm", str(html_file.resolve()), st.st_mtime, st.st_size)

    rec_ph = evaluator.audit_asset(html_file, adapter=ph_adp, engine_drifted=False)
    # Audit same file as gainhelm -> MUST NOT get profithelm's cached entry; MUST detect contamination
    rec_gh = evaluator.audit_asset(html_file, adapter=gh_adp, engine_drifted=False)
    assert rec_gh is not None, "GainHelm audit must not reuse ProfitHelm cache entry on same path/mtime/size"
    assert any("profithelm" in d.lower() or "contamination" in d.lower() or "canonical" in d.lower() for d in rec_gh.details)

    with evaluator._AUDIT_CACHE_LOCK:
        assert ph_key in evaluator._audit_cache or rec_ph is not None
        assert gh_key in evaluator._audit_cache
        for k in evaluator._audit_cache:
            assert isinstance(k, tuple) and len(k) == 4


# ------------------------------------------------------------------------------
# Group 4: 4-subprocess parallel writes to shared workspace stores
# ------------------------------------------------------------------------------


def test_four_subprocess_parallel_shared_store_writes(tmp_path: Path) -> None:
    vault_path = tmp_path / "monetization_vault.json"
    bus_path = tmp_path / "human_action_bus.json"
    email_cache = tmp_path / "email_cache.json"
    email_state = tmp_path / "email_sync_state.json"
    trend_db = tmp_path / "trend_history.db"
    streak_file = tmp_path / "supervisor_failure_streak.json"

    # Seed initial streak file with all 4 tenants
    streak_file.write_text(
        json.dumps(
            {
                "consecutive_failures": 4,
                "tenants": {
                    "profithelm": 1,
                    "prexvo": 1,
                    "gainhelm": 1,
                    "lienbond": 1,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    tenants = ["profithelm", "prexvo", "gainhelm", "lienbond"]

    def _run_shared_writer(tid: str) -> subprocess.CompletedProcess[str]:
        code = f"""
import json, os, tempfile
from pathlib import Path
from pseofactory.affiliates_hub import MonetizationHub
from pseofactory.action_bus import HumanActionBus
from pseofactory.email_ingest import EmailIngestionEngine
from pseofactory.trends.db import TrendHistoryDB, GSCDailyMetricRecord
from pseofactory.supervisor import AtomicStateLedger

tid = {tid!r}

# 1. MonetizationHub locked save/load
hub = MonetizationHub(vault_path={str(vault_path)!r})
hub.save_vault()
hub2 = MonetizationHub(vault_path={str(vault_path)!r})
assert isinstance(hub2.vault_data, dict)

# 2. HumanActionBus locked merge-save (distinct key per tenant)
bus = HumanActionBus(bus_path={str(bus_path)!r})
bus.route_stage_exception(
    property_id=tid,
    stage="parallel_test",
    title=f"Parallel stage check for {{tid}}",
    description=f"Concurrent action bus test for {{tid}}",
    missing_requirements=["Verify concurrent merge"],
)

# 3. EmailIngestionEngine locked cache/state save/load
eng = EmailIngestionEngine(cache_path={str(email_cache)!r}, state_path={str(email_state)!r})
st = eng.load_state()
st.setdefault("accounts", {{}})[f"acct_{{tid}}"] = {{"last_polled_ts": 1700000000}}
eng.save_state(st)
ca = eng.load_cache()
ca.setdefault("messages", {{}})[f"msg_{{tid}}"] = {{"subject": f"Hello {{tid}}"}}
eng.save_cache(ca)

# 4. TrendHistoryDB concurrent init_schema + acquire_lock + upsert
with TrendHistoryDB({str(trend_db)!r}) as tdb:
    with tdb.acquire_lock(non_blocking=True, timeout=30.0):
        tdb.upsert_gsc_daily_metrics([
            GSCDailyMetricRecord(
                property_id=tid,
                date="2026-11-01",
                clicks=10,
                impressions=200,
                ctr=0.05,
                position=8.2,
                recorded_at="2026-11-01T00:00:00Z",
            )
        ])

# 5. supervisor_failure_streak.json locked read-modify-write
streak_p = Path({str(streak_file)!r})
with AtomicStateLedger.acquire_lock(streak_p):
    s_data = json.loads(streak_p.read_text(encoding="utf-8"))
    t_map = s_data.get("tenants", {{}})
    t_map.pop(tid, None)
    s_data["tenants"] = t_map
    if not t_map:
        s_data["consecutive_failures"] = 0
    with tempfile.NamedTemporaryFile("w", dir=streak_p.parent, delete=False, encoding="utf-8") as tf:
        json.dump(s_data, tf, indent=2)
        tf.flush()
        os.fsync(tf.fileno())
        tmp_n = tf.name
    os.replace(tmp_n, streak_p)
"""
        return _run_py_worker(code)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        procs = list(pool.map(_run_shared_writer, tenants))

    for p in procs:
        assert p.returncode == 0, f"Parallel shared writer failed:\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"

    # Verify MonetizationHub JSON is valid
    vault_data = json.loads(vault_path.read_text(encoding="utf-8"))
    assert isinstance(vault_data, dict) and "hub_metadata" in vault_data

    # Verify HumanActionBus preserved ALL 4 concurrent actions (zero lost updates!)
    bus_data = json.loads(bus_path.read_text(encoding="utf-8"))
    bus_actions = bus_data.get("actions", {})
    found_props = {v.get("property_id") for v in bus_actions.values()}
    assert found_props == set(tenants), f"Lost updates in HumanActionBus: {found_props}"

    # Verify EmailIngestionEngine JSON files are valid
    assert isinstance(json.loads(email_state.read_text(encoding="utf-8")), dict)
    assert isinstance(json.loads(email_cache.read_text(encoding="utf-8")), dict)

    # Verify TrendHistoryDB persisted ALL 4 tenants' GSC daily rows
    with TrendHistoryDB(trend_db, read_only=True) as tdb_ro:
        for tid in tenants:
            rows = tdb_ro.get_gsc_daily_metrics(tid, days=30)
            assert len(rows) == 1, f"Missing TrendHistoryDB row for {tid}"

    # Verify supervisor_failure_streak.json popped all 4 tenants cleanly
    streak_final = json.loads(streak_file.read_text(encoding="utf-8"))
    assert streak_final["tenants"] == {}
    assert streak_final["consecutive_failures"] == 0


# ------------------------------------------------------------------------------
# Group 5: Impact Planner fail-closed matrix, AST demotion, & scoped latch
# ------------------------------------------------------------------------------


def _create_synthetic_aligned_workspace(ws_root: Path, engine_hash: str) -> Dict[str, Path]:
    repo_dirs = {
        "profithelm": ws_root / "profithelm-platform",
        "prexvo": ws_root / "prexvo",
        "gainhelm": ws_root / "gainhelm",
        "lienbond": ws_root / "lienbond",
    }
    for tid, rdir in repo_dirs.items():
        (rdir / "dist").mkdir(parents=True, exist_ok=True)
        (rdir / ".pseofactory.json").write_text(
            json.dumps({"property_id": tid, "domain": f"{tid}.com", "dist_dir": "dist"}),
            encoding="utf-8",
        )
        (rdir / "dist" / "index.html").write_text(
            f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><title>{tid}</title></head>"
            f"<body><main><h1>{tid}</h1></main></body></html>",
            encoding="utf-8",
        )
        fp, tot = compute_dist_lock_metrics(rdir / "dist")
        (rdir / "substrate_lock.json").write_text(
            json.dumps(
                {
                    "property_id": tid,
                    "engine_hash": engine_hash,
                    "substrate_hash": engine_hash,
                    "tenant_substrate_hash": compute_tenant_substrate_hash(tid),
                    "dist_fingerprint": fp,
                    "total_assets": tot,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return repo_dirs


def test_impact_planner_fail_closed_matrix_and_ast_demotion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. Verify compute_auto_worker_count xdist cap vs explicit override
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw0")
    monkeypatch.delenv("PSEOFACTORY_BROWSER_WORKERS", raising=False)
    assert compute_auto_worker_count(20, requested_workers=None) == 1
    assert compute_auto_worker_count(20, requested_workers=2) == 2

    # 2. Live partition verifies gainhelm_estate.py is exclusive to gainhelm
    live_part = get_tenant_engine_file_partition(REPO_ROOT / "pseofactory")
    assert "pseofactory/gainhelm_estate.py" in live_part["exclusive"]["gainhelm"]
    assert "pseofactory/gainhelm_estate.py" not in live_part["shared"]
    assert "pseofactory/contracts.py" in live_part["shared"]

    # 3. Synthetic AST demotion: if a shared module imports gainhelm_estate at top level, demote to SHARED
    synth_pkg = tmp_path / "synth_pkg"
    synth_pkg.mkdir()
    (synth_pkg / "__init__.py").write_text("", encoding="utf-8")
    (synth_pkg / "gainhelm_estate.py").write_text("X = 1\n", encoding="utf-8")
    (synth_pkg / "shared_mod.py").write_text("from pseofactory.gainhelm_estate import X\n", encoding="utf-8")
    demoted_part = get_tenant_engine_file_partition(synth_pkg)
    assert "pseofactory/gainhelm_estate.py" in demoted_part["shared"]
    assert "pseofactory/gainhelm_estate.py" not in demoted_part["exclusive"]["gainhelm"]

    # 4. Impact planner matrix against a clean synthetic workspace
    ws = tmp_path / "ws"
    cur_eh = compute_engine_hash()
    repos = _create_synthetic_aligned_workspace(ws, engine_hash=cur_eh)

    # NONE on tests/docs/.github/.gitignore
    plan_none = plan_tenant_impact(
        repo_root=REPO_ROOT,
        workspace_root=ws,
        changed_files=[
            "pseofactory_tests/test_example.py",
            "docs/architecture.md",
            "README.md",
            ".github/workflows/ci.yml",
            ".gitignore",
        ],
    )
    assert plan_none["mode"] == "NONE"
    assert plan_none["impacted_tenants"] == []
    assert plan_none["unaffected_tenants"] == ["profithelm", "prexvo", "gainhelm", "lienbond"]

    # SCOPED on gainhelm_estate.py
    plan_gh = plan_tenant_impact(
        repo_root=REPO_ROOT,
        workspace_root=ws,
        changed_files=["pseofactory/gainhelm_estate.py"],
    )
    assert plan_gh["mode"] == "SCOPED"
    assert plan_gh["impacted_tenants"] == ["gainhelm"]
    assert plan_gh["unaffected_tenants"] == ["profithelm", "prexvo", "lienbond"]

    # SCOPED on syndication/<tid>/**
    plan_synd = plan_tenant_impact(
        repo_root=REPO_ROOT,
        workspace_root=ws,
        changed_files=["syndication/prexvo/linkedin_post.txt"],
    )
    assert plan_synd["mode"] == "SCOPED"
    assert plan_synd["impacted_tenants"] == ["prexvo"]

    # ALL on shared engine module contracts.py
    plan_shared = plan_tenant_impact(
        repo_root=REPO_ROOT,
        workspace_root=ws,
        changed_files=["pseofactory/contracts.py"],
    )
    assert plan_shared["mode"] == "ALL"
    assert plan_shared["impacted_tenants"] == ["profithelm", "prexvo", "gainhelm", "lienbond"]

    # ALL (fail-closed) on unknown path
    plan_unknown = plan_tenant_impact(
        repo_root=REPO_ROOT,
        workspace_root=ws,
        changed_files=["mystery_root_config.yaml"],
    )
    assert plan_unknown["mode"] == "ALL"
    assert len(plan_unknown["fail_closed_triggers"]) == 1

    # ALL (fail-closed) on invalid/non-ancestor base_ref
    plan_bad_base = plan_tenant_impact(
        base_ref="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
        repo_root=REPO_ROOT,
        workspace_root=ws,
        changed_files=None,
    )
    assert plan_bad_base["mode"] == "ALL"
    assert any("base_ref" in t for t in plan_bad_base["fail_closed_triggers"])

    # Self-healing union: doc-only diff + stale prexvo tenant_substrate_hash -> SCOPED ["prexvo"]
    px_lock_path = repos["prexvo"] / "substrate_lock.json"
    px_lock = json.loads(px_lock_path.read_text(encoding="utf-8"))
    px_lock["tenant_substrate_hash"] = "0" * 64
    px_lock_path.write_text(json.dumps(px_lock, indent=2), encoding="utf-8")

    plan_heal = plan_tenant_impact(
        repo_root=REPO_ROOT,
        workspace_root=ws,
        changed_files=["README.md"],
    )
    assert plan_heal["mode"] == "SCOPED"
    assert plan_heal["impacted_tenants"] == ["prexvo"]
    assert any("stale tenant_substrate_hash" in r for r in plan_heal["reasons_by_tenant"]["prexvo"])


def test_verify_all_tenants_aligned_for_latch_scoped_hash_modes(tmp_path: Path) -> None:
    ws = tmp_path / "ws_latch"
    cur_eh = compute_engine_hash()
    prev_eh = "a" * 64
    repos = _create_synthetic_aligned_workspace(ws, engine_hash=cur_eh)

    # Simulate a GainHelm-only deploy: profithelm/prexvo/lienbond keep prev_eh in engine_hash
    # while holding current tenant_substrate_hash
    for tid in ("profithelm", "prexvo", "lienbond"):
        lf = repos[tid] / "substrate_lock.json"
        ld = json.loads(lf.read_text(encoding="utf-8"))
        ld["engine_hash"] = prev_eh
        ld["substrate_hash"] = prev_eh
        ld["tenant_substrate_hash"] = compute_tenant_substrate_hash(tid)
        lf.write_text(json.dumps(ld, indent=2), encoding="utf-8")

    # Default allow_tenant_scoped_hash=False MUST fail (legacy strict behavior preserved)
    ok_strict, strict_reasons = verify_all_tenants_aligned_for_latch(
        workspace_root=ws,
        expected_hash=cur_eh,
        require_git_clean_and_pushed=False,
        allow_tenant_scoped_hash=False,
    )
    assert ok_strict is False
    assert len(strict_reasons) >= 3

    # allow_tenant_scoped_hash=True MUST pass when every tenant's tenant_substrate_hash matches
    ok_scoped, scoped_reasons = verify_all_tenants_aligned_for_latch(
        workspace_root=ws,
        expected_hash=cur_eh,
        require_git_clean_and_pushed=False,
        allow_tenant_scoped_hash=True,
    )
    assert ok_scoped is True, f"Expected scoped alignment pass, got {scoped_reasons}"

    # Fail-closed 1: stale tenant_substrate_hash on an unaffected tenant MUST fail
    ph_lf = repos["profithelm"] / "substrate_lock.json"
    ph_ld = json.loads(ph_lf.read_text(encoding="utf-8"))
    ph_ld["tenant_substrate_hash"] = "f" * 64
    ph_lf.write_text(json.dumps(ph_ld, indent=2), encoding="utf-8")
    ok_stale_tsh, _ = verify_all_tenants_aligned_for_latch(
        workspace_root=ws,
        expected_hash=cur_eh,
        require_git_clean_and_pushed=False,
        allow_tenant_scoped_hash=True,
    )
    assert ok_stale_tsh is False

    # Fail-closed 2: missing tenant_substrate_hash with stale engine_hash MUST fail
    ph_ld.pop("tenant_substrate_hash", None)
    ph_lf.write_text(json.dumps(ph_ld, indent=2), encoding="utf-8")
    ok_missing_tsh, _ = verify_all_tenants_aligned_for_latch(
        workspace_root=ws,
        expected_hash=cur_eh,
        require_git_clean_and_pushed=False,
        allow_tenant_scoped_hash=True,
    )
    assert ok_missing_tsh is False

    # Fail-closed 3: restore valid tenant_substrate_hash, tamper dist/index.html -> MUST fail
    ph_ld["tenant_substrate_hash"] = compute_tenant_substrate_hash("profithelm")
    ph_lf.write_text(json.dumps(ph_ld, indent=2), encoding="utf-8")
    (repos["profithelm"] / "dist" / "index.html").write_text("<html><body>tampered</body></html>", encoding="utf-8")
    ok_tampered_dist, reasons_dist = verify_all_tenants_aligned_for_latch(
        workspace_root=ws,
        expected_hash=cur_eh,
        require_git_clean_and_pushed=False,
        allow_tenant_scoped_hash=True,
    )
    assert ok_tampered_dist is False
    assert any("dist_fingerprint" in r for r in reasons_dist)


# ------------------------------------------------------------------------------
# Group 6: Parallel cascade CHILD_RUN_ID uniqueness & fail-closed aggregation
# ------------------------------------------------------------------------------


def _init_dirty_git_repo(repo_dir: Path) -> None:
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.local"], cwd=repo_dir, check=True)
    (repo_dir / "README.md").write_text("v1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo_dir, check=True)
    # Dirty working tree so run_parallel_tenant_cascades picks it up
    (repo_dir / "README.md").write_text("v2-dirty\n", encoding="utf-8")


def _extract_run_parallel_tenant_cascades_fn() -> str:
    txt = RELEASE_PIPELINE_PATH.read_text(encoding="utf-8")
    start = txt.index("run_parallel_tenant_cascades() {")
    end = txt.index("\nPROJECT_INPUT=", start)
    return txt[start:end]


@pytest.mark.host_estate
def test_parallel_tenant_cascades_unique_child_run_ids_and_fail_closed(tmp_path: Path) -> None:
    fn_src = _extract_run_parallel_tenant_cascades_fn()
    runs_base = tmp_path / "runs"
    runs_base.mkdir()
    records_dir = tmp_path / "records"
    records_dir.mkdir()

    t1 = tmp_path / "profithelm-platform"
    t2 = tmp_path / "prexvo"
    t3 = tmp_path / "gainhelm"
    for td in (t1, t2, t3):
        _init_dirty_git_repo(td)

    stub_child = tmp_path / "stub_child_release.sh"
    stub_child.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail
TENANT_DIR="$1"
CHILD_RUN_ID="$2"
BASE="$(basename "$TENANT_DIR")"
FD209_OPEN="0"
if {{ true >&209; }} 2>/dev/null; then
  FD209_OPEN="1"
fi
sleep 0.15
echo "{{\\"tenant\\": \\"$BASE\\", \\"child_run_id\\": \\"$CHILD_RUN_ID\\", \\"fd209_open\\": \\"$FD209_OPEN\\"}}" > "{records_dir}/$BASE.json"
if [[ "${{FAIL_TENANT:-}}" == "$BASE" ]]; then
  echo "SIMULATED_CASCADE_FAILURE:$BASE"
  exit 1
fi
echo "SIMULATED_CASCADE_OK:$BASE:$CHILD_RUN_ID"
exit 0
""",
        encoding="utf-8",
    )
    stub_child.chmod(stub_child.stat().st_mode | stat.S_IXUSR)

    lock_file = tmp_path / "supervisor.lock"

    # Case 1: All 3 succeed in parallel with unique CHILD_RUN_ID and closed FD 209
    driver_ok = f"""#!/usr/bin/env bash
set -euo pipefail
RUNS_BASE={str(runs_base)!r}
RUN_ID="step4test"
TIMEOUT=60
export AGY_CHILD_RELEASE_SCRIPT={str(stub_child)!r}
{fn_src}
(
  flock -x 209
  run_parallel_tenant_cascades "{t1} {t2} {t3}" "prepush"
) 209>{str(lock_file)!r}
"""
    t0 = time.monotonic()
    res_ok = subprocess.run(["bash", "-c", driver_ok], capture_output=True, text=True, timeout=30)
    elapsed_ok = time.monotonic() - t0
    assert res_ok.returncode == 0, f"Parallel cascade failed:\n{res_ok.stdout}\n{res_ok.stderr}"

    child_ids = set()
    for base in ("profithelm-platform", "prexvo", "gainhelm"):
        rec = json.loads((records_dir / f"{base}.json").read_text(encoding="utf-8"))
        assert rec["child_run_id"] == f"step4test-cascade-{base}"
        assert rec["fd209_open"] == "0", f"Child {base} inherited supervisor lock FD 209!"
        child_ids.add(rec["child_run_id"])
    assert len(child_ids) == 3
    assert elapsed_ok < 3.0

    # Case 2: 1 of 3 fails -> waits for ALL 3, logs failed tenant output, returns non-zero (fail-closed)
    for f in records_dir.glob("*.json"):
        f.unlink()
    driver_fail = f"""#!/usr/bin/env bash
set -euo pipefail
RUNS_BASE={str(runs_base)!r}
RUN_ID="step4fail"
TIMEOUT=60
export AGY_CHILD_RELEASE_SCRIPT={str(stub_child)!r}
export FAIL_TENANT="prexvo"
{fn_src}
(
  flock -x 209
  run_parallel_tenant_cascades "{t1} {t2} {t3}" "prepush"
) 209>{str(lock_file)!r}
"""
    res_fail = subprocess.run(["bash", "-c", driver_fail], capture_output=True, text=True, timeout=30)
    assert res_fail.returncode != 0, "Parallel cascade must fail closed when any tenant fails"
    assert "SIMULATED_CASCADE_FAILURE:prexvo" in res_fail.stderr
    # All 3 children completed (none orphaned)
    assert sorted(p.stem for p in records_dir.glob("*.json")) == ["gainhelm", "prexvo", "profithelm-platform"]


# ------------------------------------------------------------------------------
# Group 7: Adversarial Review Regression Tests (Blockers #1, #2, #3, #5)
# ------------------------------------------------------------------------------


def test_trend_history_db_lock_held_gsc_collector_and_reopen_no_deadlock(tmp_path: Path) -> None:
    """
    Blocker #1 regression: holding TrendHistoryDB.acquire_lock() (as cron.py does)
    must NOT self-deadlock when GSCSearchConsoleCollector.harvest_gsc_spikes() or a
    second TrendHistoryDB(db_path) opens the already-initialized DB.
    """
    from pseofactory.trends.collectors import GSCSearchConsoleCollector
    from pseofactory.trends.models import GSCQueryPageWindowRecord

    db_path = tmp_path / "trends.db"
    with TrendHistoryDB(db_path) as db:
        db.upsert_gsc_query_page_windows(
            [
                GSCQueryPageWindowRecord(
                    property_id="profithelm",
                    window_key="recent_28d",
                    page="https://profithelm.com/tools/section-179-calculator/",
                    query="section 179 deduction limit 2026",
                    clicks=12,
                    impressions=85,
                    ctr=0.141,
                    position=9.5,
                    recorded_at="2026-11-20T00:00:00Z",
                )
            ]
        )

        with db.acquire_lock(non_blocking=True, timeout=5.0):
            t0 = time.monotonic()
            collector = GSCSearchConsoleCollector(db_path=str(db_path), properties=["profithelm"])
            spikes = collector.harvest_gsc_spikes()
            with TrendHistoryDB(db_path) as db_reopened:
                reopen_rows = db_reopened.get_gsc_query_page_windows("profithelm", window_key="recent_28d")
            elapsed = time.monotonic() - t0

    assert elapsed < 1.5, f"Expected <1.5s without self-deadlock, took {elapsed:.2f}s"
    assert len(spikes) == 1, f"Expected 1 real GSC spike, got {spikes}"
    assert spikes[0].query == "section 179 deduction limit 2026"
    assert len(reopen_rows) == 1


def test_post_scoped_deploy_unaffected_tenant_audit_and_drift_pass(tmp_path: Path) -> None:
    """
    Blocker #2 regression: after a scoped deploy (e.g. gainhelm_estate.py), an unaffected
    tenant holding old global engine_hash in .agy/engine_hash.json + matching
    tenant_substrate_hash in substrate_lock.json must pass AssetIntegrityEvaluator.audit_all
    and cli drift with 0 ENGINE_HASH_DRIFT, while failing closed if ledgers disagree.
    """
    import pseofactory.cli as pseo_cli
    from pseofactory.drift import detect_engine_drift
    from pseofactory.maintenance import DriftReason

    repo = tmp_path / "profithelm-platform"
    dist = repo / "dist"
    agy = repo / ".agy"
    dist.mkdir(parents=True)
    agy.mkdir(parents=True)

    (dist / "index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        "<meta name='description' content='ProfitHelm corporate tax modeling hub for business owners.'>"
        "<link rel='canonical' href='https://profithelm.com/'>"
        "<title>Corporate Tax Modeling Hub | ProfitHelm</title></head>"
        "<body><main><h1>ProfitHelm Corporate Tax Hub</h1>"
        "<p>Statutory IRC Section 179 calculations for ProfitHelm users.</p>"
        "</main></body></html>",
        encoding="utf-8",
    )
    fp, tot = compute_dist_lock_metrics(dist)
    old_eh = "b" * 64
    eh_file = agy / "engine_hash.json"
    eh_file.write_text(
        json.dumps({"engine_hash": old_eh, "substrate_hash": old_eh}, indent=2),
        encoding="utf-8",
    )
    lock_file = repo / "substrate_lock.json"
    lock_file.write_text(
        json.dumps(
            {
                "property_id": "profithelm",
                "engine_hash": old_eh,
                "substrate_hash": old_eh,
                "tenant_substrate_hash": compute_tenant_substrate_hash("profithelm"),
                "dist_fingerprint": fp,
                "total_assets": tot,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    adp = _StubPropertyAdapter("profithelm", "profithelm.com", "ProfitHelm", dist, repo)
    evaluator = AssetIntegrityEvaluator(enforce_master_seo=False)
    evaluator._audit_cache.clear()
    evaluator._fingerprint_cache.clear()
    rep = evaluator.audit_all(adp, check_engine_drift=True, check_ledger=False)
    eng_drift_recs = [r for r in rep.drifted_assets if DriftReason.ENGINE_HASH_DRIFT in r.reasons]
    assert eng_drift_recs == [], f"Unexpected ENGINE_HASH_DRIFT on unaffected scoped tenant: {eng_drift_recs}"

    drift_res = detect_engine_drift(state_file=eh_file, allow_tenant_scoped_hash=True)
    assert drift_res["status"] == "ALIGNED"
    assert drift_res["drift_detected"] is False
    assert pseo_cli.main(["drift", "--state-file", str(eh_file)]) == 0

    # Fail-closed: mismatched .agy/engine_hash.json vs substrate_lock.json must still flag DRIFT
    eh_file.write_text(
        json.dumps({"engine_hash": "c" * 64, "substrate_hash": "c" * 64}, indent=2),
        encoding="utf-8",
    )
    drift_bad = detect_engine_drift(state_file=eh_file, allow_tenant_scoped_hash=True)
    assert drift_bad["drift_detected"] is True
    evaluator._audit_cache.clear()
    evaluator._fingerprint_cache.clear()
    rep_bad = evaluator.audit_all(adp, check_engine_drift=True, check_ledger=False)
    assert any(DriftReason.ENGINE_HASH_DRIFT in r.reasons for r in rep_bad.drifted_assets)


def test_impact_planner_ast_branch_and_boolean_negation_demotion(tmp_path: Path) -> None:
    """
    Blocker #5 regression: elif/else branches, !=, not, and `or other` conditions
    must NEVER qualify as strictly tenant-scoped; all 5 must fail closed by demoting
    gainhelm_estate.py to shared.
    """
    adversarial_cases = [
        ("elif_other", "def f(tid):\n    if tid == 'gainhelm':\n        pass\n    elif tid == 'profithelm':\n        from pseofactory.gainhelm_estate import GAINHELM_X\n"),
        ("else_branch", "def f(tid):\n    if tid == 'gainhelm':\n        pass\n    else:\n        from pseofactory.gainhelm_estate import GAINHELM_X\n"),
        ("neq_guard", "def f(tid):\n    if tid != 'gainhelm':\n        from pseofactory.gainhelm_estate import GAINHELM_X\n"),
        ("not_guard", "def f(tid):\n    if not (tid == 'gainhelm'):\n        from pseofactory.gainhelm_estate import GAINHELM_X\n"),
        ("or_other", "def f(tid, other):\n    if tid == 'gainhelm' or other:\n        from pseofactory.gainhelm_estate import GAINHELM_X\n"),
    ]
    for case_name, shared_src in adversarial_cases:
        pkg = tmp_path / f"pkg_{case_name}"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "gainhelm_estate.py").write_text("GAINHELM_X = 1\n", encoding="utf-8")
        (pkg / "shared_mod.py").write_text(shared_src, encoding="utf-8")
        part = get_tenant_engine_file_partition(pkg)
        assert "pseofactory/gainhelm_estate.py" in part["shared"], f"Case {case_name} failed to demote to shared"
        assert "pseofactory/gainhelm_estate.py" not in part["exclusive"]["gainhelm"]

    # Positive elif case (matching competitor.py) must remain exclusive to gainhelm
    pos_pkg = tmp_path / "pkg_pos_elif"
    pos_pkg.mkdir()
    (pos_pkg / "__init__.py").write_text("", encoding="utf-8")
    (pos_pkg / "gainhelm_estate.py").write_text("GAINHELM_X = 1\n", encoding="utf-8")
    (pos_pkg / "shared_mod.py").write_text(
        "def f(tid):\n    if tid == 'profithelm':\n        pass\n    elif tid == 'gainhelm':\n        from pseofactory.gainhelm_estate import GAINHELM_X\n",
        encoding="utf-8",
    )
    pos_part = get_tenant_engine_file_partition(pos_pkg)
    assert "pseofactory/gainhelm_estate.py" in pos_part["exclusive"]["gainhelm"]
    assert "pseofactory/gainhelm_estate.py" not in pos_part["shared"]


@pytest.mark.host_estate
def test_release_pipeline_receipt_refresh_non_forging_and_happy_path(tmp_path: Path) -> None:
    """
    Blocker #3 regression: refresh_receipt_head_if_prior_matches must:
    (a) refuse to forge a receipt when no prior finalized receipt exists,
    (b) refresh pseofactory_head_sha when a prior finalized receipt matches all unchanged
        engine + 4-tenant dist/HEAD hashes (test/doc-only commit),
    (c) fail closed if any tenant dist byte changes.
    """
    import hashlib

    pipe_txt = RELEASE_PIPELINE_PATH.read_text(encoding="utf-8")
    start = pipe_txt.index("refresh_receipt_head_if_prior_matches() {")
    end = pipe_txt.index("\nrun_parallel_tenant_reflect() {", start)
    fn_src = pipe_txt[start:end]

    ws = tmp_path / "ws"
    ws.mkdir()
    cur_eh = compute_engine_hash()
    repos = _create_synthetic_aligned_workspace(ws, engine_hash=cur_eh)

    # Initialize git in all 4 tenant repos so _git_head succeeds
    tenant_heads: Dict[str, str] = {}
    for tid, rdir in repos.items():
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=rdir, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=rdir, check=True)
        subprocess.run(["git", "config", "user.email", "test@test.local"], cwd=rdir, check=True)
        subprocess.run(["git", "add", "."], cwd=rdir, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=rdir, check=True)
        tenant_heads[tid] = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=rdir, capture_output=True, text=True, check=True
        ).stdout.strip()

    # Fake engine git repo with SHA_1 -> SHA_2 (doc-only commit)
    eng_repo = tmp_path / "eng_git"
    eng_repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=eng_repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=eng_repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.local"], cwd=eng_repo, check=True)
    (eng_repo / "README.md").write_text("v1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=eng_repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "c1"], cwd=eng_repo, check=True)
    sha1 = subprocess.run(["git", "rev-parse", "HEAD"], cwd=eng_repo, capture_output=True, text=True, check=True).stdout.strip()
    (eng_repo / "README.md").write_text("v2 doc only\n", encoding="utf-8")
    subprocess.run(["git", "commit", "-q", "-am", "doc only"], cwd=eng_repo, check=True)
    sha2 = subprocess.run(["git", "rev-parse", "HEAD"], cwd=eng_repo, capture_output=True, text=True, check=True).stdout.strip()
    # Symlink real pseofactory package so PYTHONPATH="$eng_dir" imports pseofactory.drift
    (eng_repo / "pseofactory").symlink_to(REPO_ROOT / "pseofactory")

    receipt_path = tmp_path / "last_full_audit_receipt.json"
    driver = f"""#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR={str(ws)!r}
AUDIT_RECEIPT_PATH={str(receipt_path)!r}
{fn_src}
refresh_receipt_head_if_prior_matches {str(eng_repo)!r} {str(ws)!r}
"""

    # (a) No prior receipt -> must exit non-zero and NEVER forge receipt
    r_missing = subprocess.run(["bash", "-c", driver], capture_output=True, text=True, timeout=60)
    assert r_missing.returncode != 0
    assert not receipt_path.exists()

    # (b) Seed prior finalized receipt at sha1 -> must refresh cleanly to sha2
    tenants_rec: Dict[str, Any] = {}
    for tid, rdir in repos.items():
        dist_dir = rdir / "dist"
        fp, tot = compute_dist_lock_metrics(dist_dir)
        h = hashlib.sha256()
        for f in sorted(p for p in dist_dir.rglob("*") if p.is_file()):
            rel = f.relative_to(dist_dir).as_posix()
            h.update(f"{rel}:{hashlib.sha256(f.read_bytes()).hexdigest()}\n".encode("utf-8"))
        tenants_rec[tid] = {
            "dist_fingerprint": fp,
            "total_assets": tot,
            "substrate_hash": cur_eh,
            "tenant_substrate_hash": compute_tenant_substrate_hash(tid),
            "tenant_head_sha": tenant_heads[tid],
            "full_dist_sha256": h.hexdigest(),
        }
    receipt_path.write_text(
        json.dumps(
            {
                "stage": "3b.1",
                "cascade_finalized": True,
                "engine_hash": cur_eh,
                "pseofactory_head_sha": sha1,
                "tenants": tenants_rec,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    r_ok = subprocess.run(["bash", "-c", driver], capture_output=True, text=True, timeout=60)
    assert r_ok.returncode == 0, f"Expected happy-path refresh pass, stderr={r_ok.stderr}"
    refreshed = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert refreshed["pseofactory_head_sha"] == sha2
    assert refreshed["cascade_finalized"] is True

    # (c) Tamper 1 byte in profithelm dist -> must fail closed (exit non-zero)
    (repos["profithelm"] / "dist" / "index.html").write_text("<html><body>mutated</body></html>", encoding="utf-8")
    r_tamper = subprocess.run(["bash", "-c", driver], capture_output=True, text=True, timeout=60)
    assert r_tamper.returncode != 0

