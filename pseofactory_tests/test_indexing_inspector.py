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


def test_inspector_auto_remediate_triggers_closed_loop_feedback(tmp_path):
    """
    Verifies DailyIndexingInspector.run_inspection(auto_remediate=True) automatically
    synthesizes unindexed candidate records from quarantine/velocity/coverage anomalies
    and triggers IndexingFeedbackLoop.run_feedback_cycle with zero human intervention.
    """
    from unittest.mock import patch

    recovery_path = tmp_path / "metric_recovery_ledger.json"
    telemetry_path = tmp_path / "telemetry.jsonl"
    rollover_path = tmp_path / "rollover.json"
    quarantine_path = tmp_path / "quarantine.json"
    velocity_path = tmp_path / "velocity.json"

    rollover_path.write_text(json.dumps([]), encoding="utf-8")
    quarantine_path.write_text(
        json.dumps({
            "https://profithelm.com/tools/broken-canonical/": {
                "stage": "CANONICAL_ALIGNMENT",
                "error": "canonical_mismatch: points to wrong domain",
            }
        }),
        encoding="utf-8",
    )
    velocity_path.write_text(json.dumps({"routes": []}), encoding="utf-8")

    inspector = DailyIndexingInspector(
        tenant_id="profithelm",
        base_dir=tmp_path,
        recovery_ledger_path=recovery_path,
        quarantine_ledger_path=quarantine_path,
        velocity_ledger_path=velocity_path,
        rollover_queue_path=rollover_path,
        telemetry_logger=AtomicTelemetryLogger(log_path=telemetry_path),
    )

    with patch(
        "pseofactory.indexing.feedback_loop.IndexingFeedbackLoop.run_feedback_cycle",
        return_value={"status": "SUCCESS", "repaired": 1},
    ) as mock_cycle:
        report = inspector.run_inspection(
            dry_run=False,
            auto_remediate=True,
            coverage_records=[
                {
                    "url": "https://profithelm.com/tools/unindexed-calc/",
                    "coverageState": "Crawled - currently not indexed",
                    "is_indexed": False,
                }
            ],
        )

    assert mock_cycle.called
    call_kwargs = mock_cycle.call_args.kwargs
    unindexed_passed = call_kwargs.get("unindexed_urls") or []
    passed_urls = [u["url"] for u in unindexed_passed]
    assert "https://profithelm.com/tools/broken-canonical/" in passed_urls
    assert "https://profithelm.com/tools/unindexed-calc/" in passed_urls
    assert "auto_remediation" in report
    assert report["auto_remediation"]["status"] == "SUCCESS"


def test_vertex_anomaly_diagnosis_and_zero_benefit_guard(tmp_path):
    """
    Verifies DailyIndexingInspector.diagnose_anomalies_via_vertex:
    1. Skips Vertex call with status SKIPPED_ZERO_BENEFIT (0 tokens) when no anomalies exist.
    2. Subtracts deterministic quarantine/velocity prompts when omit_auto_remediated=True.
    3. Passes pre-assembled local telemetry context to stateless Vertex caller when anomalies exist
       and sanitizes forbidden dashes in the returned JSON diagnosis.
    """
    from pseofactory.contracts import assert_no_forbidden_dashes

    inspector = DailyIndexingInspector(tenant_id="profithelm", base_dir=tmp_path)

    # 1. Zero-benefit guard when all audits are clean
    clean_summary = {
        "gsc_rollover": {"status": "PASS", "quota_exhausted": False, "backlog_exceeded": False},
        "quarantine": {"status": "PASS", "total_quarantined": 0, "breakdown": {}},
        "velocity": {"status": "PASS", "stalled_routes_count": 0, "stalled_routes": []},
        "traffic": {"status": "PASS", "traffic_drop_detected": False, "drop_percentage": 0.0},
    }
    calls = []

    def fake_vertex(prompt: str, enable_google_search: bool = True):
        calls.append((prompt, enable_google_search))
        return [
            {
                "target": "https://profithelm.com/tools/section-179-calculator/",
                "root_cause": "2026 IRS Section 179 phase-out threshold updated\u2014page table shows prior limit",
                "external_serp_signal": "IRS Rev. Proc. 2025-2026 inflation adjustment\u2013competitors updated statutory caps",
                "recommended_context_update": "Update section_179_max_deduction and phase_out_threshold in statutory_rates.json",
            }
        ]

    res_clean = inspector.diagnose_anomalies_via_vertex(clean_summary, vertex_caller=fake_vertex)
    assert res_clean["status"] == "SKIPPED_ZERO_BENEFIT"
    assert res_clean["tokens_used"] == 0
    assert len(calls) == 0

    # 2. Subtract auto-remediated prompts when omit_auto_remediated=True
    anomaly_summary = {
        "gsc_rollover": {"quota_exhausted": False, "backlog_exceeded": False, "queue_size": 10},
        "quarantine": {"total_quarantined": 2, "breakdown": {"HTTP_404": 1, "CANONICAL_MISMATCH": 1}},
        "velocity": {"stalled_routes_count": 1, "stalled_routes": [{"slug": "irs-calc", "domain_url": "https://profithelm.com/tools/irs-calc/"}]},
        "traffic": {"traffic_drop_detected": True, "drop_percentage": -24.0, "current_rma7": 76.0, "previous_rma7": 100.0},
    }
    reduced_prompts = inspector.synthesize_remediation_prompts(anomaly_summary, omit_auto_remediated=True)
    assert len(reduced_prompts) == 1
    assert "24.0%" in reduced_prompts[0]

    # 3. Stateless Context-In -> Vertex AI -> JSON-Out when anomaly is present
    res_diag = inspector.diagnose_anomalies_via_vertex(
        anomaly_summary,
        unindexed_urls=[{"url": "https://profithelm.com/tools/section-179-calculator/", "coverage_state": "Crawled - currently not indexed"}],
        vertex_caller=fake_vertex,
    )
    assert res_diag["status"] == "SUCCESS"
    assert res_diag["model"] == "gemini-3.8-flash"
    assert len(calls) == 1
    assert "CONTEXT_JSON:" in calls[0][0]
    assert "section-179-calculator" in calls[0][0]
    assert len(res_diag["diagnoses"]) == 1
    diag = res_diag["diagnoses"][0]
    for val in diag.values():
        assert_no_forbidden_dashes(val, "vertex diagnosis field")


def test_inspector_ignores_stale_prior_day_429_quota_events_and_synthesizes_gsc_exclusion_prompts(tmp_path):
    """
    Verifies:
    1. DailyIndexingInspector.audit_gsc_rollover_queue ignores stale HTTP 429 quota events
       from prior UTC calendar days (>24h ago) after Google's daily quota has reset.
    2. synthesize_remediation_prompts includes exact GSC exclusion counts, causes, child sitemaps,
       and sample URLs when child_sitemaps.section_coverage reports unindexed routes.
    """
    telemetry_path = tmp_path / "telemetry.jsonl"
    logger = AtomicTelemetryLogger(log_path=telemetry_path)
    rollover_path = tmp_path / "gsc_rollover_queue.json"
    rollover_path.write_text(json.dumps([]), encoding="utf-8")

    # Log a stale 429 event from 2 days ago
    stale_dt = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    stale_event = TelemetryEvent(
        timestamp=stale_dt,
        event_type="SUBPROCESS_CRASH",
        tenant_id="gainhelm",
        error_type="GoogleIndexingQuotaExhausted",
        error_message="HTTP 429: Daily quota of 200 submissions reached",
        action_taken="RECORDED",
    )
    logger.log(stale_event)

    inspector = DailyIndexingInspector(
        tenant_id="gainhelm",
        rollover_queue_path=rollover_path,
        telemetry_logger=logger,
    )
    res_roll = inspector.audit_gsc_rollover_queue()
    assert res_roll["quota_exhausted"] is False
    assert res_roll["status"] == "PASS"

    audit_summary = {
        "gsc_rollover": res_roll,
        "quarantine": {"breakdown": {}},
        "velocity": {"stalled_routes_count": 0},
        "traffic": {"traffic_drop_detected": False},
        "child_sitemaps": {
            "section_coverage": {
                "unindexed_count": 3,
                "sections": {
                    "products": {
                        "unindexed": 3,
                        "child_sitemap": "sitemap-hubs.xml",
                        "exclusions_by_cause": {"CRAWL_BUDGET_SIGNAL_LAG": 3},
                        "sample_unindexed_urls": [
                            "https://gainhelm.com/tools/soc-2-audit-cost-calculator/",
                            "https://gainhelm.com/tools/cmmc-2-0-compliance-cost-calculator/",
                        ],
                    }
                },
            }
        },
    }
    prompts = inspector.synthesize_remediation_prompts(audit_summary)
    assert len(prompts) == 1
    assert "CRAWL_BUDGET_SIGNAL_LAG:3" in prompts[0]
    assert "sitemap-hubs.xml" in prompts[0]
    assert "https://gainhelm.com/tools/soc-2-audit-cost-calculator/" in prompts[0]



