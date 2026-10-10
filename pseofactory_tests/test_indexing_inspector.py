"""
Test Suite: pseofactory Daily Indexing Inspector (Loop 3)
Verifies GSC rollover queue audit, HTTP 429 quota exhaustion detection,
airlock quarantine categorization, velocity ledger stagnation detection,
search traffic rolling average drop alerts, and metric recovery ledger atomic persistence.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest

from pseofactory.indexing_inspector import DailyIndexingInspector
from pseofactory.telemetry import AtomicTelemetryLogger, TelemetryEvent
from pseofactory.trends.models import GSCDailyMetricRecord
from pseofactory.supervisor import AtomicStateLedger


def test_gsc_rollover_queue_backlog_and_quota(tmp_path):
    """
    Verifies rollover queue detects backlogs exceeding 200 URLs
    and detects HTTP 429 quota exhaustion from telemetry events.
    """
    telemetry_path = tmp_path / "telemetry.jsonl"
    logger = AtomicTelemetryLogger(log_path=telemetry_path)
    rollover_path = tmp_path / "gsc_rollover_queue.json"

    # 1. Normal queue under 200: PASS
    normal_urls = [f"https://profithelm.com/tools/tax-{i}/" for i in range(50)]
    rollover_path.write_text(json.dumps(normal_urls), encoding="utf-8")

    inspector = DailyIndexingInspector(
        tenant_id="profithelm",
        rollover_queue_path=rollover_path,
        telemetry_logger=logger,
    )
    res = inspector.audit_gsc_rollover_queue()
    assert res["status"] == "PASS"
    assert res["queue_size"] == 50
    assert res["backlog_exceeded"] is False
    assert res["quota_exhausted"] is False

    # 2. Backlog exceeding 200 URLs: FAIL
    large_urls = [f"https://profithelm.com/tools/tax-{i}/" for i in range(250)]
    rollover_path.write_text(json.dumps(large_urls), encoding="utf-8")
    res_large = inspector.audit_gsc_rollover_queue()
    assert res_large["status"] == "FAIL"
    assert res_large["queue_size"] == 250
    assert res_large["backlog_exceeded"] is True

    # 3. HTTP 429 quota exhaustion in telemetry: FAIL
    logger.record(
        event_type="SUBPROCESS_CRASH",
        tenant_id="profithelm",
        error_type="GoogleIndexingQuotaExhausted",
        error_message="HTTP 429: Daily quota of 200 submissions reached",
        exit_code=1,
    )
    res_quota = inspector.audit_gsc_rollover_queue()
    assert res_quota["status"] == "FAIL"
    assert res_quota["quota_exhausted"] is True


def test_airlock_quarantine_categorization(tmp_path):
    """
    Verifies airlock quarantine anomalies are grouped into HTTP 404,
    thin content, robots disallow, redirect, and canonical mismatch.
    """
    quarantine_path = tmp_path / "indexing_quarantine_ledger.json"
    data = {
        "https://profithelm.com/tools/missing/": {
            "url": "https://profithelm.com/tools/missing/",
            "code": "QUARANTINE_HTTP_ERROR",
            "reason": "Target route '/tools/missing/' not found in compiled dist artifacts (HTTP 404)",
            "timestamp": "2026-10-09T00:00:00Z",
        },
        "https://profithelm.com/tools/mismatch/": {
            "url": "https://profithelm.com/tools/mismatch/",
            "code": "QUARANTINE_UNINDEXABLE_META",
            "reason": "Canonical mismatch: points to https://example.com/other",
            "timestamp": "2026-10-09T00:00:00Z",
        },
        "https://profithelm.com/tools/blocked/": {
            "url": "https://profithelm.com/tools/blocked/",
            "code": "QUARANTINE_ROBOTS_DISALLOW",
            "reason": "Disallowed by robots.txt rule",
            "timestamp": "2026-10-09T00:00:00Z",
        },
    }
    quarantine_path.write_text(json.dumps(data), encoding="utf-8")

    inspector = DailyIndexingInspector(
        tenant_id="profithelm",
        quarantine_ledger_path=quarantine_path,
    )
    res = inspector.audit_airlock_quarantine()
    assert res["total_quarantined"] == 3
    breakdown = res["breakdown"]
    assert breakdown["HTTP_404"] == 1
    assert breakdown["CANONICAL_MISMATCH"] == 1
    assert breakdown["ROBOTS_DISALLOW"] == 1


def test_velocity_stagnation_detection(tmp_path):
    """
    Verifies routes where time-to-first-crawl exceeds 336.0 hours (14 days)
    are flagged as stalled routes.
    """
    velocity_path = tmp_path / "indexing_velocity_ledger.json"
    data = {
        "status": "SUCCESS",
        "routes": [
            {
                "slug": "fast-tool",
                "domain_url": "https://profithelm.com/tools/fast-tool/",
                "ttfc_domain_hours": 72.0,
                "differential_hours": 68.0,
                "stalled": False,
            },
            {
                "slug": "stalled-tool",
                "domain_url": "https://profithelm.com/tools/stalled-tool/",
                "ttfc_domain_hours": 360.0,
                "differential_hours": 350.0,
                "stalled": False,
            },
        ],
    }
    velocity_path.write_text(json.dumps(data), encoding="utf-8")

    inspector = DailyIndexingInspector(
        tenant_id="profithelm",
        velocity_ledger_path=velocity_path,
    )
    res = inspector.audit_velocity_stagnation(stagnation_threshold_hours=336.0)
    assert res["routes_monitored"] == 2
    assert res["stalled_routes_count"] == 1
    assert res["stalled_routes"][0]["slug"] == "stalled-tool"
    assert res["status"] == "WARN"


def test_search_traffic_drop_detection():
    """
    Verifies 7-day rolling average (RMA_7) drop exceeding 15% past dynamic floor
    triggers FAIL status and flags traffic drop.
    """
    inspector = DailyIndexingInspector(tenant_id="profithelm")

    base_dt = datetime(2026, 9, 1, tzinfo=timezone.utc)
    records = []
    # Week 1: healthy traffic (100 impressions/day)
    for i in range(7):
        records.append(GSCDailyMetricRecord("profithelm", (base_dt + timedelta(days=i)).date().isoformat(), clicks=10, impressions=100.0, position=5.0))
    # Week 2: dropped traffic (70 impressions/day -> 30% drop)
    for i in range(7, 14):
        records.append(GSCDailyMetricRecord("profithelm", (base_dt + timedelta(days=i)).date().isoformat(), clicks=5, impressions=70.0, position=8.0))

    res = inspector.audit_search_traffic(gsc_records=records, drop_threshold=0.15, min_impressions_floor=20.0)
    assert res["traffic_drop_detected"] is True
    assert res["status"] == "FAIL"
    assert res["drop_percentage"] < -15.0


def test_remediation_prompt_synthesis():
    """Verifies synthesis of grounded agy /goal prompt suggestions for detected anomalies."""
    inspector = DailyIndexingInspector(tenant_id="profithelm")
    audit_summary = {
        "gsc_rollover": {"quota_exhausted": True, "queue_size": 220},
        "quarantine": {"breakdown": {"HTTP_404": 3, "CANONICAL_MISMATCH": 2}},
        "velocity": {"stalled_routes_count": 2, "stalled_routes": [{"slug": "irs-calc"}, {"slug": "loan-calc"}]},
        "traffic": {"traffic_drop_detected": True, "drop_percentage": -22.5},
    }
    prompts = inspector.synthesize_remediation_prompts(audit_summary)
    assert len(prompts) == 5
    assert any("429" in p for p in prompts)
    assert any("HTTP 404" in p for p in prompts)
    assert any("Unstall" in p for p in prompts)
    assert any("22.5%" in p for p in prompts)
    for p in prompts:
        assert p.startswith('agy /goal "')


def test_recovery_ledger_atomic_persistence(tmp_path):
    """
    Verifies complete inspection cycle persists structured report atomically
    to metric_recovery_ledger.json via AtomicStateLedger and emits telemetry.
    """
    recovery_path = tmp_path / "metric_recovery_ledger.json"
    telemetry_path = tmp_path / "telemetry.jsonl"
    rollover_path = tmp_path / "rollover.json"
    quarantine_path = tmp_path / "quarantine.json"
    velocity_path = tmp_path / "velocity.json"

    rollover_path.write_text(json.dumps(["https://profithelm.com/tools/t1/"]), encoding="utf-8")
    quarantine_path.write_text(json.dumps({}), encoding="utf-8")
    velocity_path.write_text(json.dumps({"routes": []}), encoding="utf-8")

    logger = AtomicTelemetryLogger(log_path=telemetry_path)
    inspector = DailyIndexingInspector(
        tenant_id="profithelm",
        recovery_ledger_path=recovery_path,
        quarantine_ledger_path=quarantine_path,
        velocity_ledger_path=velocity_path,
        rollover_queue_path=rollover_path,
        telemetry_logger=logger,
    )

    report = inspector.run_inspection(dry_run=False)
    assert report["audit_status"] == "PASS"
    assert recovery_path.exists()

    saved_data = AtomicStateLedger.load_json(recovery_path)
    assert "profithelm" in saved_data
    assert saved_data["profithelm"]["audit_status"] == "PASS"
    assert "last_inspected" in saved_data
