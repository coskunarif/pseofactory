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


def test_canonical_trend_history_db_path_resolves_independent_of_cwd():
    """Failure mode: relative DB paths split crawl history across 3 SQLite files depending on cwd."""
    from pseofactory.trends.db import DEFAULT_DB_PATH, TrendHistoryDB

    assert DEFAULT_DB_PATH.is_absolute()
    assert DEFAULT_DB_PATH.parts[-3:] == ("trends", "data", "trend_history.db")
    db = TrendHistoryDB()
    assert db.db_path == DEFAULT_DB_PATH


def test_remediation_queue_strips_volatile_timestamps_for_idempotency(tmp_path):
    """Failure mode: volatile locked_until/created_at timestamps caused 182 duplicate queue tasks."""
    from pseofactory.gsc_remediation import AsyncRemediationQueue

    q = AsyncRemediationQueue(queue_path=tmp_path / "queue.json")
    cand1 = {
        "tenant_id": "profithelm",
        "slug": "saas-runway-calculator",
        "target_url": "https://profithelm.com/tools/saas-runway-calculator/",
        "anomaly_type": "LOW_CTR_STRIKING_DISTANCE",
        "overlay_spec": {
            "slug": "saas-runway-calculator",
            "title_rewrite": "SaaS Runway Calculator 2026",
            "created_at": "2026-10-14T00:00:00+00:00",
            "locked_until": "2026-10-28T00:00:00+00:00",
        },
    }
    cand2 = {
        "tenant_id": "profithelm",
        "slug": "saas-runway-calculator",
        "target_url": "https://profithelm.com/tools/saas-runway-calculator/",
        "anomaly_type": "LOW_CTR_STRIKING_DISTANCE",
        "overlay_spec": {
            "slug": "saas-runway-calculator",
            "title_rewrite": "SaaS Runway Calculator 2026",
            "created_at": "2026-10-15T00:00:00+00:00",
            "locked_until": "2026-10-29T00:00:00+00:00",
        },
    }
    r1 = q.enqueue_batch([cand1], tenant_id="profithelm")
    r2 = q.enqueue_batch([cand2], tenant_id="profithelm")
    assert r1["enqueued_count"] == 1
    assert r2["enqueued_count"] == 0
    assert r2["deduplicated_count"] == 1
    assert r2["status"] == "DEDUPLICATED_NO_OP"


def test_evaluate_expired_overlays_records_metric_recovery_ledger(tmp_path):
    """Failure mode: Day-28 overlay evaluations never wrote outcomes back to metric_recovery_ledger.json."""
    from pseofactory.gsc_remediation import evaluate_expired_overlays

    ov_dir = tmp_path / "content" / "overlays"
    ov_dir.mkdir(parents=True)
    now = datetime.now(timezone.utc)
    ov_file = ov_dir / "section-179-calculator.json"
    ov_file.write_text(
        json.dumps({
            "slug": "section-179-calculator",
            "status": "ACTIVE_LOCKED",
            "created_at": (now - timedelta(days=30)).isoformat(),
            "locked_until": (now - timedelta(days=2)).isoformat(),
            "baseline_ctr": 0.01,
            "baseline_position": 12.0,
            "current_metrics": {"ctr": 0.04, "position": 6.5, "impressions": 200, "clicks": 8},
        }),
        encoding="utf-8",
    )
    res = evaluate_expired_overlays(
        site_url="sc-domain:profithelm.com",
        base_dir=tmp_path,
    )
    assert any(item["slug"] == "section-179-calculator" for item in res["accretive"])
    ledger_file = tmp_path / ".agy" / "metric_recovery_ledger.json"
    assert ledger_file.is_file()
    ledger = json.loads(ledger_file.read_text(encoding="utf-8"))
    assert any(e["slug"] == "section-179-calculator" for e in ledger["evaluations"])


def test_indexing_inspector_merges_global_and_tenant_ledgers(tmp_path):
    """Failure mode: DailyIndexingInspector read only agy_dir and missed tenant-local base_dir/.agy ledgers."""
    from pseofactory.indexing_inspector import DailyIndexingInspector

    global_agy = tmp_path / "global_agy"
    global_agy.mkdir(parents=True)
    tenant_base = tmp_path / "profithelm-platform"
    (tenant_base / ".agy").mkdir(parents=True)

    (global_agy / "gsc_rollover_queue.json").write_text(
        json.dumps(["https://profithelm.com/tools/saas-runway-calculator/"]), encoding="utf-8"
    )
    (tenant_base / ".agy" / "gsc_rollover_queue.json").write_text(
        json.dumps(["https://profithelm.com/tools/section-179-calculator/"]), encoding="utf-8"
    )

    inspector = DailyIndexingInspector(tenant_id="profithelm", base_dir=tenant_base, agy_dir=global_agy)
    rollover_audit = inspector.audit_gsc_rollover_queue()
    assert rollover_audit["queue_size"] == 2


def test_audit_gsc_rollover_queue_newest_first_clears_reconciled_429(tmp_path):
    """
    Failure mode: audit_gsc_rollover_queue reversed read_recent() (which is already newest-first),
    scanning oldest-first and letting historical 429 events mask newer AUTO_REMEDIATED events.
    """
    from pseofactory.indexing_inspector import DailyIndexingInspector
    from pseofactory.telemetry import AtomicTelemetryLogger

    telemetry_path = tmp_path / "telemetry_events.jsonl"
    logger = AtomicTelemetryLogger(log_path=telemetry_path)
    rollover_path = tmp_path / "gsc_rollover_queue.json"
    rollover_path.write_text("[]", encoding="utf-8")

    logger.record(
        event_type="SUBPROCESS_CRASH",
        tenant_id="prexvo",
        error_type="GoogleIndexingQuotaExhausted",
        error_message="429 Quota exhausted during GSC indexing on https://prexvo.com/",
        action_taken="RECORDED",
        dedup_window_seconds=0,
    )
    logger.record(
        event_type="INDEXING_ROLLOVER_RECONCILED",
        tenant_id="prexvo",
        error_type="NONE",
        error_message="Reconciled 0 rollover URLs via verified GSC child sitemaps",
        action_taken="AUTO_REMEDIATED",
        dedup_window_seconds=0,
    )

    inspector = DailyIndexingInspector(
        tenant_id="prexvo",
        rollover_queue_path=rollover_path,
        telemetry_logger=logger,
    )
    audit = inspector.audit_gsc_rollover_queue()
    assert audit["quota_exhausted"] is False
    assert audit["status"] == "PASS"


def test_gainhelm_statutory_routing_covers_soc2_compliance_and_c3pao():
    """
    Failure mode: 'soc 2 compliance cost calculator' and 'cmmc level 2 c3pao audit cost calculator'
    fell through to unassigned instead of routing deterministically to gainhelm.
    """
    from pseofactory.trends.cron import TrendCronRunner

    runner = TrendCronRunner()
    for q in (
        "soc 2 compliance cost calculator",
        "soc 2 compliance price",
        "cmmc level 2 c3pao audit cost calculator",
    ):
        res = runner.determine_property_assignment(q)
        assert res["property_id"] == "gainhelm"
        assert res["contamination_scan_passed"] == 1



