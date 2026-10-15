"""
Regression replays of autonomous-run failure modes observed in production logs (2026-10-09..15).
Each test reproduces a recorded failure and asserts the engine now catches or resolves it.
Zero em-dashes. Zero en-dashes.
"""

import json
from datetime import datetime, timedelta, timezone

from pseofactory.gsc_remediation import is_overlay_locked, persist_overlay_respecting_lock
from pseofactory.maintenance import (
    ConfigurablePropertyAdapter,
    MaintenanceLifecycle,
    SubprocessCrashError,
    TenantRegistry,
)
from pseofactory.supervisor import (
    REPEATED_FAILURE_ESCALATION_THRESHOLD,
    AsyncFleetCoordinator,
    AutonomousLifecycleSupervisor,
    extract_failure_reason,
)
from pseofactory.telemetry import AtomicTelemetryLogger, handle_cli as telemetry_cli
from pseofactory.trends.pipeline import stamp_engine_verdict_status

# Verbatim queue record from ~/.local/share/vault/void_candidates.jsonl line 806 as the
# trend-intake sink wrote it on 2026-10-15T08:10Z, before any tenant touched it.
LOANS_ENGINE_RECORD = {
    "query": "loans",
    "slug": "loans",
    "action": "REJECT",
    "jev_score": 0.1,
    "durable_prob": 0.05,
    "composite_profit_yield": 0.0,
    "cannibalization_risk": 0.0,
    "target_asset_type": "none",
    "decision_reason": "Token count (1) below minimum threshold (2)",
    "passed_thresholds": False,
    "evaluated_at": "2026-10-15T08:10:34.230414+00:00",
    "matching_tool": None,
    "overlay_spec": None,
    "candidate_spec": None,
    "idempotency_key": "unassigned:loans:REJECT:3a9464227cf46f0a",
}

# Verbatim prexvo run_factory.sh output captured by the supervisor on 2026-10-15T22:00Z.
PREXVO_STDOUT_TAIL = (
    "[Stage 3/9] Compiling production static distribution into dist/...\n"
    "Build failed: SEO checklist verification failed with 3 issues: Title length (32 chars) "
    "outside 50-60 range in tools/loans/index.html: 'Loans Calculator | Prexvo Engine'\n"
)
PREXVO_STDERR_TAIL = "Prexvo factory error encountered at line 105 with exit code 1\n"


def test_engine_reject_verdict_is_stamped_rejected_for_tenants():
    """Failure mode: engine REJECT records entered the shared queue status-less and tenants built them."""
    rec = stamp_engine_verdict_status(dict(LOANS_ENGINE_RECORD))
    assert rec["status"] == "REJECTED"
    assert "Token count (1)" in rec["status_reason"]

    monitor = stamp_engine_verdict_status({"slug": "cardi-b", "action": "MONITOR"})
    assert monitor["status"] == "REJECTED"

    build = stamp_engine_verdict_status({"slug": "rap-forgiveness-timeline", "action": "BUILD_PAGE"})
    assert build["status"] == "PENDING"

    # Tenant-owned lifecycle states are never overwritten by the sink
    built = stamp_engine_verdict_status({"slug": "x", "action": "REJECT", "status": "BUILT"})
    assert built["status"] == "BUILT"


def test_failure_reason_surfaces_tenant_stdout_cause_not_trap_line():
    """Failure mode: supervisor.log showed status=FAILED with no cause for 13 consecutive hours."""
    reason = extract_failure_reason([{
        "error": "Factory runner 'run_factory.sh' failed with exit 1 for 'prexvo'",
        "stderr_tail": PREXVO_STDERR_TAIL,
        "stdout_tail": PREXVO_STDOUT_TAIL,
    }])
    assert reason.startswith("Build failed: SEO checklist verification failed")
    assert "tools/loans/index.html" in reason


def _crashing_registry(tmp_path):
    class CrashingPrexvoAdapter(ConfigurablePropertyAdapter):
        def list_assets(self):
            raise SubprocessCrashError(
                "Factory runner 'run_factory.sh' failed with exit 1 for 'prexvo'",
                returncode=1,
                stderr_tail=PREXVO_STDERR_TAIL,
                stdout_tail=PREXVO_STDOUT_TAIL,
                property_id="prexvo",
            )

    dist = tmp_path / "prexvo_dist"
    dist.mkdir(parents=True, exist_ok=True)
    reg = TenantRegistry()
    reg.register_adapter(CrashingPrexvoAdapter(
        property_id="prexvo",
        brand_name="Prexvo",
        domain="prexvo.com",
        canonical_base="https://prexvo.com",
        dist_dir=dist,
    ))
    return reg


def test_failure_streak_persists_across_run_once_processes_and_escalates(tmp_path, monkeypatch):
    """
    Failure mode: hourly systemd --run-once cycles reset consecutive_failures to 0 each
    process, so 13 identical prexvo failures never reached DEGRADED or escalated.
    """
    telemetry_path = tmp_path / "telemetry.jsonl"
    monkeypatch.setenv("FACTORY_TELEMETRY_PATH", str(telemetry_path))
    reg = _crashing_registry(tmp_path)

    class FastTrendRunner:
        def run_cron_cycle(self, *args, **kwargs):
            return {"status": "SUCCESS", "approved_build": [], "refactor_pages": []}

    results = []
    for _ in range(5):
        # Fresh supervisor per cycle mirrors one systemd --run-once process per hour
        sup = AutonomousLifecycleSupervisor(
            workspace_root=tmp_path,
            registry=reg,
            coordinator=AsyncFleetCoordinator(
                registry=reg, lifecycle=MaintenanceLifecycle(trend_runner=FastTrendRunner())
            ),
            heartbeat_path=tmp_path / "hb.json",
            max_consecutive_failures=5,
        )
        results.append(sup.run_cycle(force=True))

    assert [r["consecutive_failures"] for r in results] == [1, 2, 3, 4, 5]
    assert results[-1]["status"] == "DEGRADED"

    escalated_cycles = [i for i, r in enumerate(results) if r.get("escalations")]
    assert escalated_cycles == [REPEATED_FAILURE_ESCALATION_THRESHOLD - 1]
    esc = results[REPEATED_FAILURE_ESCALATION_THRESHOLD - 1]["escalations"][0]
    assert esc["tenant_id"] == "prexvo"
    assert "tools/loans/index.html" in esc["reason"]

    events = AtomicTelemetryLogger(log_path=telemetry_path).read_recent(limit=50)
    repeated = [e for e in events if e.event_type == "SUPERVISOR_REPEATED_FAILURE"]
    assert len(repeated) == 1 and repeated[0].tenant_id == "prexvo"
    crash = [e for e in events if e.event_type == "SUBPROCESS_CRASH"]
    assert crash and "Build failed: SEO checklist" in (crash[0].error_message or "")

    streak = json.loads((tmp_path / ".agy" / "supervisor_failure_streak.json").read_text())
    assert streak["consecutive_failures"] == 5
    assert streak["tenants"]["prexvo"]["streak"] == 5


def test_locked_overlay_is_not_rewritten_by_repair_loop(tmp_path):
    """
    Failure mode: 'scheduled GSC repair loop sync' commits rewrote ACTIVE_LOCKED overlays,
    resetting created_at/locked_until each iteration so no outcome was ever evaluated.
    """
    now = datetime.now(timezone.utc)
    overlay = tmp_path / "rap-vs-ibr-calculator.json"
    locked = {
        "slug": "rap-vs-ibr-calculator",
        "status": "ACTIVE_LOCKED",
        "created_at": (now - timedelta(days=3)).isoformat(),
        "locked_until": (now + timedelta(days=11)).isoformat(),
        "baseline_position": 10.0,
    }
    overlay.write_text(json.dumps(locked), encoding="utf-8")

    regenerated = dict(locked, created_at=now.isoformat(), locked_until=(now + timedelta(days=14)).isoformat())
    effective, written = persist_overlay_respecting_lock(overlay, regenerated)
    assert written is False
    assert effective["created_at"] == locked["created_at"]
    assert json.loads(overlay.read_text())["locked_until"] == locked["locked_until"]

    # Once the window matures a new remediation may be written
    expired = dict(locked, locked_until=(now - timedelta(days=1)).isoformat())
    overlay.write_text(json.dumps(expired), encoding="utf-8")
    assert not is_overlay_locked(expired)
    _, written = persist_overlay_respecting_lock(overlay, regenerated)
    assert written is True
    assert json.loads(overlay.read_text())["created_at"] == regenerated["created_at"]


def test_systemd_stop_post_with_success_result_records_no_failure(tmp_path):
    """Failure mode: ExecStopPost logged 'failed with result=success' SYSTEMD_FAILURE events."""
    log_file = tmp_path / "telemetry.jsonl"
    rc = telemetry_cli([
        "emit-failure",
        "--service", "prexvo-factory.service",
        "--result", "success",
        "--exit-status", "0",
        "--log-path", str(log_file),
    ])
    assert rc == 0
    assert AtomicTelemetryLogger(log_path=log_file).read_recent(limit=5) == []


def test_scoped_success_does_not_clear_other_tenant_streaks(tmp_path):
    """Grader finding: a --property scoped success must not wipe another tenant's failure streak."""
    from pseofactory.supervisor import SupervisorFailureStreak

    ledger = SupervisorFailureStreak(tmp_path / "streak.json")
    failing = {"prexvo": {"status": "FAILED", "failed_records": [{"error": "x", "stdout_tail": "Build failed: y"}]}}
    ledger.record_cycle(False, 1, failing)
    ledger.record_cycle(True, 0, {"profithelm": {"status": "SUCCESS"}}, scoped=True)
    assert ledger.load()["tenants"]["prexvo"]["streak"] == 1
    ledger.record_cycle(True, 0, {"prexvo": {"status": "SUCCESS"}, "profithelm": {"status": "SUCCESS"}})
    assert ledger.load()["tenants"] == {}


def test_rolled_back_overlay_is_not_reapplied_during_cooldown(tmp_path):
    """Grader finding: a DEGRADED_ROLLED_BACK overlay was immediately rewritable by the repair loop."""
    now = datetime.now(timezone.utc)
    overlay = tmp_path / "student-loan-repayment-calculator.json"
    rolled = {
        "status": "DEGRADED_ROLLED_BACK",
        "locked_until": (now - timedelta(days=1)).isoformat(),
        "rolled_back_at": (now - timedelta(days=2)).isoformat(),
        "measurement_lock_days": 14,
    }
    overlay.write_text(json.dumps(rolled), encoding="utf-8")
    _, written = persist_overlay_respecting_lock(overlay, {"status": "ACTIVE_LOCKED", "title_rewrite": "again"})
    assert written is False

    rolled["rolled_back_at"] = (now - timedelta(days=20)).isoformat()
    overlay.write_text(json.dumps(rolled), encoding="utf-8")
    _, written = persist_overlay_respecting_lock(overlay, {"status": "ACTIVE_LOCKED", "title_rewrite": "again"})
    assert written is True
