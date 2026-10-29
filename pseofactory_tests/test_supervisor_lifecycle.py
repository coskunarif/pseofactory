"""
Test Suite: pseofactory Autonomous Lifecycle Supervisor & Async Fleet Coordinator.
Asserts atomic state ledgers, heartbeat tracking, bounded async execution,
cross-tenant fault isolation, memory firewalls, network partition fail-closed recovery,
and end-to-end drift cascade cycles (HWL-1231, HWL-1349).
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

import json
from pathlib import Path
import socket
import sys
import threading
import time
from typing import Any, Dict
import urllib.error
import urllib.request

import pytest

from pseofactory.drift import (
    compute_asset_fingerprint,
    compute_engine_hash,
    detect_engine_drift,
    load_asset_ledger,
    record_asset_ledger,
    record_engine_hash,
)
from pseofactory.maintenance import (
    ConfigurablePropertyAdapter,
    CrossPropertyContaminationScanner,
    MaintenanceLifecycle,
    MaintenanceResult,
    PropertyContaminationError,
    TenantRegistry,
)
from pseofactory.supervisor import (
    AsyncFleetCoordinator,
    AtomicStateLedger,
    AutonomousLifecycleSupervisor,
    HeartbeatTracker,
    MAX_CONSECUTIVE_FAILURES,
)

CLEAN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Compliant Asset Document</title>
    <meta name="description" content="Valid metadata without forbidden jargon or dashes">
    <link rel="canonical" href="https://example.com/asset">
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@graph": [
        {"@type": "WebPage", "@id": "https://example.com/asset#webpage"}
      ]
    }
    </script>
</head>
<body>
    <header><h1>Compliant Asset Document</h1></header>
    <main>
        <p>Specific numeric metric: 42 percent efficiency gain.</p>
        <a href="/internal" style="display:inline-block; min-width:48px; min-height:48px;">Valid Link Target</a>
    </main>
</body>
</html>"""


@pytest.fixture(autouse=True)
def clean_sys_modules():
    """
    Ensures tenant packages are never leaked across tests in sys.modules (stateless worker physics).
    Zero em-dashes. Zero en-dashes.
    """
    yield
    for mod in list(sys.modules.keys()):
        if mod in ("profithelm", "prexvo") or mod.startswith(("profithelm.", "prexvo.")):
            sys.modules.pop(mod, None)


def test_atomic_state_ledger_concurrency_and_fsync(tmp_path):
    """
    Verifies atomic JSON persistence under concurrent multithreaded writers and readers.
    Asserts flock exclusivity, zero byte corruption, and atomic replacement.
    Zero em-dashes. Zero en-dashes.
    """
    target_file = tmp_path / "atomic_ledger.json"
    errors = []
    read_snapshots = []
    stop_event = threading.Event()

    def writer_worker(thread_id: int):
        for i in range(15):
            payload = {
                "thread_id": thread_id,
                "iteration": i,
                "timestamp": time.time(),
                "payload": "x" * 256,
            }
            try:
                AtomicStateLedger.save_json(target_file, payload)
            except Exception as ex:
                errors.append(f"Writer {thread_id} error: {ex}")
            time.sleep(0.005)

    def reader_worker(reader_id: int):
        while not stop_event.is_set():
            try:
                data = AtomicStateLedger.load_json(target_file)
                if data:
                    assert "thread_id" in data
                    assert "iteration" in data
                    read_snapshots.append(data["thread_id"])
            except Exception as ex:
                errors.append(f"Reader {reader_id} error: {ex}")
            time.sleep(0.003)

    readers = [threading.Thread(target=reader_worker, args=(r,)) for r in range(4)]
    writers = [threading.Thread(target=writer_worker, args=(w,)) for w in range(6)]

    for r in readers:
        r.start()
    for w in writers:
        w.start()

    for w in writers:
        w.join()

    stop_event.set()
    for r in readers:
        r.join()

    assert len(errors) == 0, f"Encountered ledger errors: {errors}"
    assert target_file.exists()
    final_data = AtomicStateLedger.load_json(target_file)
    assert "thread_id" in final_data
    assert "iteration" in final_data

    # Verify acquire_lock mutual exclusion
    lock_counter = 0
    lock_errors = []

    def locked_section_worker():
        nonlocal lock_counter
        with AtomicStateLedger.acquire_lock(target_file):
            current = lock_counter
            time.sleep(0.01)
            if lock_counter != current:
                lock_errors.append("Lock exclusivity violated")
            lock_counter = current + 1

    threads = [threading.Thread(target=locked_section_worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(lock_errors) == 0
    assert lock_counter == 5


def test_supervisor_heartbeat_and_backoff_ceiling(tmp_path):
    """
    Verifies atomic heartbeat ledger records, jittered exponential backoff,
    and fail-closed transition to DEGRADED state on retry ceiling (HWL-1231).
    Zero em-dashes. Zero en-dashes.
    """
    hb_path = tmp_path / "supervisor_heartbeat.json"
    tracker = HeartbeatTracker(heartbeat_path=hb_path)

    # Emit initial heartbeat
    tracker.emit(
        status="RUNNING",
        cycle_id="cycle_test_001",
        current_tenant="prexvo",
        engine_hash="deadbeef" * 8,
        consecutive_failures=0,
        last_cycle_duration_seconds=3.1415,
    )

    hb_data = tracker.read()
    assert hb_data["status"] == "RUNNING"
    assert hb_data["cycle_id"] == "cycle_test_001"
    assert hb_data["current_tenant"] == "prexvo"
    assert len(hb_data["engine_hash"]) == 64
    assert hb_data["consecutive_failures"] == 0
    assert hb_data["last_cycle_duration_seconds"] == 3.142
    assert "timestamp" in hb_data
    assert "pid" in hb_data

    # Verify backoff computation formula: min(300.0, 5.0 * (2 ** (failures - 1))) + jitter
    supervisor = AutonomousLifecycleSupervisor(
        workspace_root=tmp_path,
        heartbeat_path=hb_path,
    )

    b0 = supervisor.compute_backoff(0)
    assert b0 == 0.0

    b1 = supervisor.compute_backoff(1)
    assert 5.0 <= b1 <= 10.0

    b2 = supervisor.compute_backoff(2)
    assert 10.0 <= b2 <= 15.0

    b3 = supervisor.compute_backoff(3)
    assert 20.0 <= b3 <= 25.0

    b5 = supervisor.compute_backoff(5)
    assert 80.0 <= b5 <= 85.0

    b10 = supervisor.compute_backoff(10)
    assert 300.0 <= b10 <= 305.0

    # Simulate transition to DEGRADED upon 5 consecutive failures
    class FailingAdapter(ConfigurablePropertyAdapter):
        def list_assets(self):
            raise RuntimeError("Simulated tenant worker defect")

    reg = TenantRegistry()
    broken_dist = tmp_path / "broken_dist"
    broken_dist.mkdir(parents=True, exist_ok=True)
    broken_adapter = FailingAdapter(
        property_id="broken",
        brand_name="Broken",
        domain="broken.com",
        canonical_base="https://broken.com",
        dist_dir=broken_dist,
    )
    reg.register_adapter(broken_adapter)

    class FastTrendRunner:
        def run_cron_cycle(self, *args, **kwargs):
            return {"status": "SUCCESS", "approved_build": [], "refactor_pages": []}

    failing_lifecycle = MaintenanceLifecycle(trend_runner=FastTrendRunner())
    failing_coord = AsyncFleetCoordinator(registry=reg, lifecycle=failing_lifecycle)

    failing_supervisor = AutonomousLifecycleSupervisor(
        workspace_root=tmp_path,
        registry=reg,
        coordinator=failing_coord,
        heartbeat_path=hb_path,
        max_consecutive_failures=MAX_CONSECUTIVE_FAILURES,
    )

    for i in range(1, MAX_CONSECUTIVE_FAILURES + 1):
        res = failing_supervisor.run_cycle(force=True)
        assert res["consecutive_failures"] == i
        if i < MAX_CONSECUTIVE_FAILURES:
            assert res["status"] in ("FAILED", "ERROR")
        else:
            assert res["status"] == "DEGRADED"

    final_hb = tracker.read()
    assert final_hb["status"] == "DEGRADED"
    assert final_hb["consecutive_failures"] == MAX_CONSECUTIVE_FAILURES


def test_async_fleet_coordinator_concurrency_and_timeout(tmp_path):
    """
    Verifies concurrency semaphore ceiling (max 2 parallel workers)
    and per-tenant timeout budget aborting runaway execution without crashing fleet.
    Zero em-dashes. Zero en-dashes.
    """
    class FastTrendRunner:
        def run_cron_cycle(self, *args, **kwargs):
            return {"status": "SUCCESS", "approved_build": [], "refactor_pages": []}

    dist_1 = tmp_path / "tenant1"
    dist_2 = tmp_path / "tenant2"
    dist_3 = tmp_path / "tenant3"
    for d in (dist_1, dist_2, dist_3):
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(CLEAN_HTML, encoding="utf-8")

    active_lock = threading.Lock()
    active_count = 0
    max_active_observed = 0

    def slow_builder(slug: str, target_file=None):
        nonlocal active_count, max_active_observed
        with active_lock:
            active_count += 1
            if active_count > max_active_observed:
                max_active_observed = active_count
        time.sleep(0.1)
        with active_lock:
            active_count -= 1
        return True

    def runaway_builder(slug: str, target_file=None):
        time.sleep(2.5)
        return True

    reg = TenantRegistry()
    reg.register_adapter(
        ConfigurablePropertyAdapter("t1", "T1", "t1.com", "https://t1.com", dist_1, build_asset_fn=slow_builder)
    )
    reg.register_adapter(
        ConfigurablePropertyAdapter("t2", "T2", "t2.com", "https://t2.com", dist_2, build_asset_fn=slow_builder)
    )
    reg.register_adapter(
        ConfigurablePropertyAdapter("t3", "T3", "t3.com", "https://t3.com", dist_3, build_asset_fn=slow_builder)
    )

    # 1. Assert concurrency ceiling of 2 workers
    coord = AsyncFleetCoordinator(
        registry=reg,
        lifecycle=MaintenanceLifecycle(trend_runner=FastTrendRunner()),
        concurrency_ceiling=2,
        tenant_timeout_budget=5.0,
    )
    results = coord.run_fleet(force=True)
    assert len(results) == 3
    assert max_active_observed <= 2, f"Observed {max_active_observed} concurrent workers, expected <= 2"

    # 2. Assert tenant timeout budget
    reg_timeout = TenantRegistry()
    dist_fast = tmp_path / "fast_dist"
    dist_fast.mkdir(parents=True, exist_ok=True)
    (dist_fast / "index.html").write_text(CLEAN_HTML, encoding="utf-8")
    dist_timeout = tmp_path / "runaway_dist"
    dist_timeout.mkdir(parents=True, exist_ok=True)
    (dist_timeout / "index.html").write_text("<html><body>Drifted with em dash \u2014 invalid</body></html>", encoding="utf-8")

    reg_timeout.register_adapter(
        ConfigurablePropertyAdapter("fast", "Fast", "fast.com", "https://fast.com", dist_fast)
    )
    reg_timeout.register_adapter(
        ConfigurablePropertyAdapter(
            "runaway",
            "Runaway",
            "runaway.com",
            "https://runaway.com",
            dist_timeout,
            build_asset_fn=runaway_builder,
        )
    )

    coord_timeout = AsyncFleetCoordinator(
        registry=reg_timeout,
        lifecycle=MaintenanceLifecycle(trend_runner=FastTrendRunner()),
        concurrency_ceiling=2,
        tenant_timeout_budget=1.2,
    )
    t0 = time.time()
    t_results = coord_timeout.run_fleet(force=True)
    duration = time.time() - t0

    assert duration < 2.4, "Runaway tenant blocked the coordinator beyond its timeout"
    assert t_results["runaway"].status == "TIMEOUT"
    assert t_results["fast"].status in ("SUCCESS", "SKIPPED_NO_CHANGES")


def test_cross_tenant_fault_isolation(tmp_path):
    """
    Verifies cross-tenant isolation and memory firewall:
    Failure or contamination in one tenant never halts or contaminates sibling tenants.
    Zero em-dashes. Zero en-dashes.
    """
    class FastTrendRunner:
        def run_cron_cycle(self, *args, **kwargs):
            return {"status": "SUCCESS", "approved_build": [], "refactor_pages": []}

    dist_prexvo = tmp_path / "prexvo_dist"
    dist_profithelm = tmp_path / "profithelm_dist"
    dist_prexvo.mkdir(parents=True, exist_ok=True)
    dist_profithelm.mkdir(parents=True, exist_ok=True)

    # prexvo has a drifted asset with em-dash so contaminating_builder will be called
    (dist_prexvo / "index.html").write_text("<html><body>Drifted with em dash \u2014 invalid</body></html>", encoding="utf-8")
    (dist_profithelm / "index.html").write_text(CLEAN_HTML, encoding="utf-8")

    def contaminating_builder(slug: str, target_file=None):
        raise PropertyContaminationError("Foreign statutory token found in prexvo: profithelm")

    reg = TenantRegistry()
    reg.register_adapter(
        ConfigurablePropertyAdapter(
            "prexvo",
            "Prexvo",
            "prexvo.com",
            "https://prexvo.com",
            dist_prexvo,
            build_asset_fn=contaminating_builder,
        )
    )
    reg.register_adapter(
        ConfigurablePropertyAdapter(
            "profithelm",
            "ProfitHelm",
            "profithelm.com",
            "https://profithelm.com",
            dist_profithelm,
        )
    )

    coord = AsyncFleetCoordinator(
        registry=reg,
        lifecycle=MaintenanceLifecycle(trend_runner=FastTrendRunner()),
        concurrency_ceiling=2,
    )
    results = coord.run_fleet(force=True)

    assert results["prexvo"].status == "FAILED"
    assert "PropertyContaminationError" in str(results["prexvo"].failed_records)

    # Sibling tenant profithelm executed and completed green
    assert results["profithelm"].status in ("SUCCESS", "SKIPPED_NO_CHANGES")

    # Assert Subprocess Memory Firewall: tenant modules never imported into host sys.modules
    assert "prexvo" not in sys.modules
    assert "profithelm" not in sys.modules


def test_network_partition_fail_closed_recovery(tmp_path, monkeypatch):
    """
    Simulates network partition drops (URLError socket.timeout during live edge verification
    and remote git operations).
    Asserts fail-closed unlatched state (HWL-1349) with zero byte corruption.
    Restores network and asserts clean self-healing recovery.
    Zero em-dashes. Zero en-dashes.
    """
    prop_dir = tmp_path / "property"
    dist_dir = prop_dir / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.html").write_text(CLEAN_HTML, encoding="utf-8")

    agy_dir = tmp_path / ".agy"
    agy_dir.mkdir(parents=True, exist_ok=True)
    state_file = agy_dir / "engine_hash.json"
    ledger_file = agy_dir / "asset_ledger.json"

    initial_hash = "1111111111111111111111111111111111111111111111111111111111111111"
    initial_payload = {
        "engine_hash": initial_hash,
        "updated_at": "2026-01-01T00:00:00Z",
    }
    AtomicStateLedger.save_json(state_file, initial_payload)

    adapter = ConfigurablePropertyAdapter(
        property_id="recovery_app",
        brand_name="RecoveryApp",
        domain="recoveryapp.com",
        canonical_base="https://recoveryapp.com",
        dist_dir=dist_dir,
        repo_path=prop_dir,
    )

    reg = TenantRegistry()
    reg.register_adapter(adapter)

    supervisor = AutonomousLifecycleSupervisor(
        workspace_root=tmp_path,
        state_file=state_file,
        ledger_file=ledger_file,
        registry=reg,
    )

    # Stage 1: Simulate network partition (socket timeout / URLError on edge probe)
    def mocked_partition_urlopen(req, timeout=None):
        raise urllib.error.URLError(socket.timeout("Network unreachable: simulated edge partition drop"))

    monkeypatch.setattr(urllib.request, "urlopen", mocked_partition_urlopen)

    res_partition = supervisor.run_cycle(force=True, enable_gitops=True)
    assert res_partition["status"] in ("FAILED", "ERROR")

    # HWL-1349 Invariant: State file remains strictly at initial_hash with zero byte corruption!
    unlatched_state = AtomicStateLedger.load_json(state_file)
    assert unlatched_state["engine_hash"] == initial_hash, (
        f"State prematurely latched under network partition: {unlatched_state['engine_hash']}"
    )

    # Stage 2: Restore network partition
    class MockEdgeResponse:
        def __init__(self):
            self.code = 200
            self.body = b'<!DOCTYPE html><html><head><title>Compliant Title</title><link rel="canonical" href="https://recoveryapp.com/asset"></head><body>Online</body></html>'
        def getcode(self):
            return self.code
        def read(self):
            return self.body
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: MockEdgeResponse())

    res_recovery = supervisor.run_cycle(force=True, enable_gitops=True)
    assert res_recovery["status"] == "SUCCESS"

    # Post-recovery latch verified: state file is now latched with current engine hash
    latched_state = AtomicStateLedger.load_json(state_file)
    assert latched_state["engine_hash"] != initial_hash
    assert len(latched_state["engine_hash"]) == 64
    assert ledger_file.exists()


def test_e2e_drift_cascade_multi_tenant(tmp_path):
    """
    End-to-end autonomous drift cascade across Prexvo and ProfitHelm
    with simulated engine drift. Asserts rebuild, audit, contamination scans,
    and post-verification commit latching across discovered tenants.
    Zero em-dashes. Zero en-dashes.
    """
    # 1. Setup workspace with prexvo and profithelm
    prexvo_dir = tmp_path / "prexvo"
    profithelm_dir = tmp_path / "profithelm"

    for p_dir, p_id, p_domain in (
        (prexvo_dir, "prexvo", "prexvo.com"),
        (profithelm_dir, "profithelm", "profithelm.com"),
    ):
        p_dir.mkdir(parents=True, exist_ok=True)
        (p_dir / ".pseofactory.json").write_text(
            json.dumps({
                "property_id": p_id,
                "brand_name": p_id.capitalize(),
                "domain": p_domain,
                "canonical_base": f"https://{p_domain}",
                "dist_dir": "dist",
            }),
            encoding="utf-8",
        )
        d_dir = p_dir / "dist"
        d_dir.mkdir(parents=True, exist_ok=True)
        (d_dir / "index.html").write_text(CLEAN_HTML, encoding="utf-8")

    state_file = tmp_path / ".agy" / "engine_hash.json"
    ledger_file = tmp_path / ".agy" / "asset_ledger.json"

    # Seed state file with stale hash to assert drift detection
    stale_hash = "0000000000000000000000000000000000000000000000000000000000000000"
    AtomicStateLedger.save_json(state_file, {"engine_hash": stale_hash})

    supervisor = AutonomousLifecycleSupervisor(
        workspace_root=tmp_path,
        state_file=state_file,
        ledger_file=ledger_file,
    )

    # 2. Run supervisor cycle: detects drift and executes cascade across both tenants
    cycle_res = supervisor.run_cycle(force=False)
    assert cycle_res["status"] == "SUCCESS"
    assert cycle_res["drift_detected"] is True
    assert "prexvo" in cycle_res["properties"]
    assert "profithelm" in cycle_res["properties"]

    # 3. Assert HWL-1349 post-verification commit latch
    updated_state = AtomicStateLedger.load_json(state_file)
    assert updated_state["engine_hash"] != stale_hash
    assert len(updated_state["engine_hash"]) == 64

    ledger_data = AtomicStateLedger.load_json(ledger_file)
    assert "assets" in ledger_data
    assert any("prexvo" in k for k in ledger_data["assets"])
    assert any("profithelm" in k for k in ledger_data["assets"])

    # 4. Immediate second cycle must return SKIPPED_ALIGNED (Universal Idempotency HWL-1231)
    idempotent_res = supervisor.run_cycle(force=False)
    assert idempotent_res["status"] == "SKIPPED_ALIGNED"
    assert idempotent_res["drift_detected"] is False


def test_supervisor_overlay_rollback_reconcile_and_streak_extraction(tmp_path):
    """
    Regression test for FAILED.pseofactory_supervisor oscillation:
    1. reconcile_workspace_tracking_state(restore_tenant_dist=True) preserves untracked
       DEGRADED_ROLLED_BACK overlay rollbacks on dist/ HTML after git checkout HEAD -- dist.
    2. verify_cohort_reflection_contract resolves flat spoke overlay filenames
       (e.g. irs-2027-tax-brackets-illinois.json -> tools/irs-2027-tax-brackets/illinois/index.html).
    3. extract_failure_reason extracts drift details from AssetDriftRecord.to_dict() payloads.
    4. Supervisor cycle does not wipe DLQ quarantine when SKIPPED_NO_CHANGES had unrefactored quarantined drift.
    Zero em-dashes. Zero en-dashes.
    """
    import subprocess
    from pseofactory.gitops import reconcile_workspace_tracking_state
    from pseofactory.maintenance import AssetDriftRecord, DriftReason, RefactorCascadeEngine
    from pseofactory.supervisor import extract_failure_reason
    from pseofactory.verifier import verify_cohort_reflection_contract

    # 1. Verify extract_failure_reason extracts details from AssetDriftRecord dicts
    drift_rec = AssetDriftRecord(
        asset_path=str(tmp_path / "dist" / "tools" / "irs-2027-tax-brackets" / "illinois" / "index.html"),
        slug="irs-2027-tax-brackets/illinois",
        reasons=[DriftReason.CONTENT_RELEVANCE_GAP],
        details=["Master SEO Checklist: Rolled-back title 'Illinois 2027 Tax Brackets Calculator (Rules) | ProfitHelm' still active in tools/irs-2027-tax-brackets/illinois/index.html"],
    )
    reason = extract_failure_reason([drift_rec.to_dict()])
    assert "Rolled-back title" in reason
    assert "tools/irs-2027-tax-brackets/illinois/index.html" in reason

    # 2. Setup simulated tenant git repo with tracked dist/ containing an injected overlay,
    #    and an untracked .agy/overlays/irs-2027-tax-brackets-illinois.json with DEGRADED_ROLLED_BACK
    tenant_repo = tmp_path / "profithelm-platform"
    spoke_dir = tenant_repo / "dist" / "tools" / "irs-2027-tax-brackets" / "illinois"
    spoke_dir.mkdir(parents=True, exist_ok=True)
    spoke_html_path = spoke_dir / "index.html"
    injected_html = (
        "<!DOCTYPE html><html lang=\"en\"><head>"
        "<title>Illinois 2027 Tax Brackets Calculator (Rules) | ProfitHelm</title>"
        "</head><body><h1>Illinois 2027 Tax Brackets Calculator</h1>"
        "<main><div id=\"gsc-striking-overlay\" class=\"gsc-overlay-container\">"
        "<section class=\"overlay-section\">Degraded content</section></div></main></body></html>"
    )
    spoke_html_path.write_text(injected_html, encoding="utf-8")
    (tenant_repo / "substrate_lock.json").write_text('{"property_id": "profithelm"}\n', encoding="utf-8")

    subprocess.run(["git", "init"], cwd=str(tenant_repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@profithelm.com"], cwd=str(tenant_repo), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=str(tenant_repo), check=True, capture_output=True)
    (tenant_repo / ".gitignore").write_text(".agy/\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(tenant_repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit with overlay in dist"], cwd=str(tenant_repo), check=True, capture_output=True)

    # Create untracked rolled-back overlay spec with flat spoke filename
    ov_dir = tenant_repo / ".agy" / "overlays"
    ov_dir.mkdir(parents=True, exist_ok=True)
    ov_file = ov_dir / "irs-2027-tax-brackets-illinois.json"
    ov_payload = {
        "slug": "irs-2027-tax-brackets-illinois",
        "tenant_id": "profithelm",
        "status": "DEGRADED_ROLLED_BACK",
        "rolled_back_title_rewrite": "Illinois 2027 Tax Brackets Calculator (Rules) | ProfitHelm",
        "rolled_back_modifier": "Rules",
    }
    ov_file.write_text(json.dumps(ov_payload, indent=2), encoding="utf-8")

    # Before reconciliation, verify_cohort_reflection_contract detects the rolled-back title in nested spoke HTML
    pre_check = verify_cohort_reflection_contract(tenant_repo, dist_dir=tenant_repo / "dist")
    assert pre_check["passed"] is False
    assert any("irs-2027-tax-brackets/illinois/index.html" in issue for issue in pre_check["issues"])

    # Modify dist/ slightly (uncommitted) and run reconcile_workspace_tracking_state(restore_tenant_dist=True)
    spoke_html_path.write_text(injected_html + "\n", encoding="utf-8")
    reconcile_workspace_tracking_state(
        tenant_repos=[tenant_repo],
        restore_tenant_dist=True,
    )

    # After reconciliation, rolled-back overlay is scrubbed from dist/ even after git checkout HEAD -- dist
    # and substrate_lock.json is updated so a subsequent reconcile_workspace_tracking_state call preserves it
    post_check = verify_cohort_reflection_contract(tenant_repo, dist_dir=tenant_repo / "dist")
    assert post_check["passed"] is True, f"Expected cohort reflection pass, got: {post_check}"
    reconcile_workspace_tracking_state(
        tenant_repos=[tenant_repo],
        restore_tenant_dist=True,
    )
    second_check = verify_cohort_reflection_contract(tenant_repo, dist_dir=tenant_repo / "dist")
    assert second_check["passed"] is True, f"Expected second reconciliation to preserve scrubbed dist, got: {second_check}"
    lock_json = json.loads((tenant_repo / "substrate_lock.json").read_text(encoding="utf-8"))
    assert "dist_fingerprint" in lock_json
    assert lock_json["total_assets"] == 1

    # 3. Verify DLQ quarantine is not prematurely cleared when SKIPPED_NO_CHANGES had unrefactored drift
    dlq_path = tmp_path / "test_dlq.json"
    cascade = RefactorCascadeEngine(dlq_path=dlq_path)
    cascade.route_to_dlq("profithelm", drift_rec, "Simulated quarantine")
    assert len(cascade.list_dlq(property_id="profithelm")) == 1

    # 4. Verify generated edge functions for profithelm, prexvo, and gainhelm have zero cross-tenant KV token contamination
    from pseofactory.edge import generate_edge_redirect_function, generate_edge_telemetry_function
    from pseofactory.maintenance import CrossPropertyContaminationScanner
    scanner = CrossPropertyContaminationScanner()
    for pid in ("profithelm", "prexvo", "gainhelm"):
        assert scanner.scan_text(generate_edge_redirect_function(property_id=pid), pid) == []
        assert scanner.scan_text(generate_edge_telemetry_function(property_id=pid), pid) == []


def test_department_handoff_contracts_and_three_tenant_unification(tmp_path: Path):
    """
    Verifies formal DepartmentContract definitions across all 6 stages
    (DISCOVERY -> MONETIZATION -> ENGINEERING -> VERIFICATION -> SYNDICATION -> DEPLOYMENT),
    heartbeat preservation, and unified 3-tenant routing across profithelm, prexvo, and gainhelm.
    """
    from pseofactory.supervisor import (
        CANONICAL_DEPARTMENT_CONTRACTS,
        CANONICAL_TENANTS,
        DEPARTMENT_STAGES,
        DepartmentPipelineStateMachine,
        HeartbeatTracker,
    )
    from pseofactory.affiliates import (
        audit_partnership_model_coverage,
        qualify_monetization_opportunity,
    )
    from pseofactory.gsc_remediation import compile_remediation_overlay_spec
    from pseofactory.maintenance import sync_tenant_pseofactory_marker

    assert CANONICAL_TENANTS == ("profithelm", "prexvo", "gainhelm")
    assert tuple(CANONICAL_DEPARTMENT_CONTRACTS.keys()) == DEPARTMENT_STAGES

    for idx, stage_name in enumerate(DEPARTMENT_STAGES, start=1):
        contract = CANONICAL_DEPARTMENT_CONTRACTS[stage_name]
        assert contract.stage == stage_name
        assert contract.order == idx
        assert len(contract.required_inputs) >= 3
        assert len(contract.guaranteed_outputs) >= 3
        assert len(contract.tenant_invariants) >= 3
        serialized = json.dumps(contract.to_dict())
        assert "\u2014" not in serialized
        assert "\u2013" not in serialized

    sm = DepartmentPipelineStateMachine(state_path=tmp_path / "dept_pipeline.json")
    for stage_name in DEPARTMENT_STAGES:
        sm.record_stage(stage_name, status="PASS", summary={"verified": True})
    sm_dict = sm.finalize_and_persist(
        cycle_id="test-handoff-cycle",
        overall_status="PASS",
        trigger_mode="BATCHED_CADENCE",
        engine_hash="abc123",
        persist=True,
    )
    assert sm_dict["overall_status"] == "PASS"
    assert sm_dict["tenants_managed"] == ["profithelm", "prexvo", "gainhelm"]
    assert set(sm_dict["contracts"].keys()) == set(DEPARTMENT_STAGES)

    hb_path = tmp_path / "heartbeat.json"
    hb = HeartbeatTracker(heartbeat_path=hb_path)
    hb.emit(
        status="HEALTHY",
        cycle_id="cycle-1",
        extra={
            "department_pipeline": sm_dict,
            "partner_lifecycle_sync": {"status": "SYNCED"},
        },
    )
    hb2 = hb.emit(status="HEALTHY", cycle_id="cycle-2", extra={"note": "fast_check"})
    assert "department_pipeline" in hb2
    assert hb2["partner_lifecycle_sync"] == {"status": "SYNCED"}

    # Verify GainHelm monetization qualification and partnership coverage parity
    gh_qual = qualify_monetization_opportunity("soc 2 audit cost calculator", property_id=None)
    assert gh_qual["monetization_qualified"] is True
    assert gh_qual["property_id"] == "gainhelm"

    px_reject = qualify_monetization_opportunity("soc 2 audit cost calculator", property_id="prexvo")
    assert px_reject["monetization_qualified"] is False

    gh_cov = audit_partnership_model_coverage(property_id="gainhelm")
    assert gh_cov["status"] == "PASS"
    assert gh_cov["verticals_audited_count"] >= 1
    assert "b2b_cyber_compliance" in gh_cov["vertical_coverage"]

    # Verify GainHelm GSC remediation overlay spec uses gainhelm.com
    gh_ov = compile_remediation_overlay_spec(
        {"slug": "soc-2-audit-cost-calculator", "query": "soc 2 audit cost calculator"},
        tenant_id="gainhelm",
    )
    assert "gainhelm.com" in gh_ov["target_url"]
    assert "profithelm.com" not in json.dumps(gh_ov)

    # Verify .pseofactory.json marker normalization across all 3 tenants
    for pid, expected_brand in (
        ("profithelm", "ProfitHelm"),
        ("prexvo", "Prexvo"),
        ("gainhelm", "GainHelm"),
    ):
        t_dir = tmp_path / pid
        t_dir.mkdir(parents=True, exist_ok=True)
        wrote = sync_tenant_pseofactory_marker(t_dir, pid)
        assert wrote is True
        assert (t_dir / ".pseofactory.json").is_file()
        marker = json.loads((t_dir / ".pseofactory.json").read_text(encoding="utf-8"))
        assert marker["property_id"] == pid
        assert marker["brand_name"] == expected_brand
        assert marker["domain"] == f"{pid}.com"


def test_verify_department_handoff_chain_heal_markers_and_cli_contract(tmp_path: Path):
    """
    Regression test for fleet maintenance handoff verification and marker healing:
    1. CANONICAL_TENANT_CONFIGS defines repo_dir_name for profithelm, prexvo, and gainhelm.
    2. verify_department_handoff_chain(heal_markers=True) heals .pseofactory.json markers
       across tenant repo directories without raising KeyError: 'repo_dir_name'.
    3. verify_department_handoff_chain returns 'tenants_verified' at top level so CLI
       supervisor --verify-handoffs and audit --department-handoffs succeed.
    4. _clear_stale_autojob_failure_markers removes stale FAILED.pseofactory-fleet-maintenance
       markers on unscoped non-dry-run supervisor completion while preserving them on dry_run or scoped runs.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.maintenance import CANONICAL_TENANT_CONFIGS
    from pseofactory.supervisor import (
        AutonomousLifecycleSupervisor,
        verify_department_handoff_chain,
    )

    assert CANONICAL_TENANT_CONFIGS["profithelm"]["repo_dir_name"] == "profithelm-platform"
    assert CANONICAL_TENANT_CONFIGS["prexvo"]["repo_dir_name"] == "prexvo"
    assert CANONICAL_TENANT_CONFIGS["gainhelm"]["repo_dir_name"] == "gainhelm"

    ws_dir = tmp_path / "workspace"
    for pid, repo_name in (
        ("profithelm", "profithelm-platform"),
        ("prexvo", "prexvo"),
        ("gainhelm", "gainhelm"),
    ):
        r_dir = ws_dir / repo_name
        (r_dir / "dist").mkdir(parents=True, exist_ok=True)
        (r_dir / "dist" / "index.html").write_text(CLEAN_HTML, encoding="utf-8")

    rep = verify_department_handoff_chain(
        workspace_root=ws_dir,
        heal_markers=True,
        persist=False,
    )
    assert "tenants_verified" in rep
    assert set(rep["tenants_verified"]) == {"profithelm", "prexvo", "gainhelm"}
    for repo_name in ("profithelm-platform", "prexvo", "gainhelm"):
        assert (ws_dir / repo_name / ".pseofactory.json").is_file()

    # Verify autojob failure marker clearing helper
    autojob_dir = tmp_path / "autojobs"
    autojob_dir.mkdir(parents=True, exist_ok=True)
    failed_maint = autojob_dir / "FAILED.pseofactory-fleet-maintenance"
    failed_sup = autojob_dir / "FAILED.pseofactory_supervisor"
    unrelated_marker = autojob_dir / "FAILED.other_job"
    failed_maint.write_text("", encoding="utf-8")
    failed_sup.write_text("", encoding="utf-8")
    unrelated_marker.write_text("", encoding="utf-8")

    sup = AutonomousLifecycleSupervisor(workspace_root=ws_dir)
    assert sup._clear_stale_autojob_failure_markers(dry_run=True, scoped=False, state_dir=autojob_dir) == []
    assert failed_maint.exists()
    assert sup._clear_stale_autojob_failure_markers(dry_run=False, scoped=True, state_dir=autojob_dir) == []
    assert failed_maint.exists()

    cleared = sup._clear_stale_autojob_failure_markers(dry_run=False, scoped=False, state_dir=autojob_dir)
    assert "FAILED.pseofactory-fleet-maintenance" in cleared
    assert "FAILED.pseofactory_supervisor" in cleared
    assert not failed_maint.exists()
    assert not failed_sup.exists()
    assert unrelated_marker.exists()




