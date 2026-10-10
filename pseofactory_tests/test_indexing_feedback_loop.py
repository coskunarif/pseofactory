"""
pseofactory Autonomous Closed-Loop Indexing Feedback Coordinator Tests
Validates root-cause diagnosis, reflection repair trigger, composite push idempotency,
429/network partition rollover queue preservation (HWL-1349), Stage 10 error propagation,
and CLI execution.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pseofactory.indexing.feedback_loop import (
    ALGORITHMIC_EXPANSION_FREEZE,
    CANONICAL_TEMPLATE_DEFECT,
    CONTENT_DEPTH_DEFICIT,
    CONTENT_QUALITY_OR_ANSWER_DEFICIENCY,
    CRAWL_BUDGET_SIGNAL_LAG,
    DEAD_ROUTE_IN_SITEMAP,
    UNKNOWN_OR_UNCLASSIFIED,
    DiagnosisResult,
    GSCRootCauseClassifier,
    IndexingFeedbackLoop,
    RootCauseClassification,
)
from pseofactory.indexer import PushIndexer
from pseofactory.indexing.milestones import MilestoneTracker
from pseofactory.maintenance import MaintenanceLifecycle, ConfigurablePropertyAdapter, SubprocessPropertyAdapter
from pseofactory.telemetry import AtomicTelemetryLogger, TelemetryEvent


def test_feedback_loop_defect_diagnosis_and_root_cause_classification():
    """
    Verifies GSCRootCauseClassifier deterministically categorizes GSC anomalies
    into structured classifications and actionable remediation plans.
    """
    classifier = GSCRootCauseClassifier()

    # 1. Crawled - currently not indexed
    r1 = classifier.classify({
        "url": "https://profithelm.com/tools/mortgage-calculator/",
        "coverageState": "Crawled - currently not indexed",
    })
    assert r1.classification == RootCauseClassification.CONTENT_QUALITY_OR_ANSWER_DEFICIENCY.value
    assert "quality or answer deficiency" in r1.reason.lower()

    # 2. Discovered - currently not indexed
    r2 = classifier.classify({
        "url": "https://profithelm.com/tools/loan-amortization/",
        "coverage_state": "Discovered - currently not indexed",
    })
    assert r2.classification == RootCauseClassification.CRAWL_BUDGET_SIGNAL_LAG.value
    assert "signal lag" in r2.reason.lower()

    # 3. HTTP 404 / Dead Route
    r3 = classifier.classify({
        "url": "https://profithelm.com/tools/deleted-route/",
        "status_code": 404,
        "error": "quarantine_http_error",
    })
    assert r3.classification == RootCauseClassification.DEAD_ROUTE_IN_SITEMAP.value
    assert "404" in r3.reason

    # 4. Canonical Mismatch
    r4 = classifier.classify({
        "url": "https://profithelm.com/tools/tax-estimator/",
        "error": "canonical_mismatch: points to https://other.com",
    })
    assert r4.classification == RootCauseClassification.CANONICAL_TEMPLATE_DEFECT.value
    assert "canonical" in r4.reason.lower()

    # 5. Thin Content (<150 words)
    r5 = classifier.classify({
        "url": "https://profithelm.com/tools/quick-calc/",
        "word_count": 82,
    })
    assert r5.classification == RootCauseClassification.CONTENT_DEPTH_DEFICIT.value
    assert "82 words" in r5.reason

    # 6. Algorithmic Ceiling Freeze
    r6 = classifier.classify({
        "url": "https://profithelm.com/tools/crypto-arbitrage/",
        "error": "freeze_expansion: ceiling threshold reached",
        "algorithmic_ceiling": True,
    })
    assert r6.classification == RootCauseClassification.ALGORITHMIC_EXPANSION_FREEZE.value

    # 7. Unclassified Fallback
    r7 = classifier.classify({
        "url": "https://profithelm.com/tools/unknown-error/",
        "coverageState": "Some exotic search console status",
    })
    assert r7.classification == RootCauseClassification.UNKNOWN_OR_UNCLASSIFIED.value


def test_feedback_loop_reflect_and_recompile_repairs(tmp_path):
    """
    Verifies execute_engine_repairs triggers reflect_and_recompile_all_assets
    when template/quality defects are diagnosed, and quarantines dead routes.
    """
    mock_indexer = MagicMock()
    mock_inspector = MagicMock()
    mock_preflight = MagicMock()
    mock_tracker = MagicMock()
    mock_telemetry = MagicMock()

    loop = IndexingFeedbackLoop(
        property_id="profithelm",
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        base_dir=tmp_path,
        dist_dir=tmp_path / "dist",
        indexer=mock_indexer,
        inspector=mock_inspector,
        preflight_engine=mock_preflight,
        milestone_tracker=mock_tracker,
        telemetry_logger=mock_telemetry,
    )

    diagnoses = [
        DiagnosisResult(
            url="https://profithelm.com/tools/dead-route/",
            classification=RootCauseClassification.DEAD_ROUTE_IN_SITEMAP.value,
            reason="HTTP 404",
            remediation_action="Quarantine",
            reflection_path="N/A",
        ),
        DiagnosisResult(
            url="https://profithelm.com/tools/answer-box-defect/",
            classification=RootCauseClassification.CONTENT_QUALITY_OR_ANSWER_DEFICIENCY.value,
            reason="Crawled not indexed",
            remediation_action="Add early answer box",
            reflection_path="reflect",
        ),
    ]

    with patch(
        "pseofactory.indexing.feedback_loop.reflect_and_recompile_all_assets",
        return_value={"status": "SUCCESS", "total_recompiled": 2},
    ) as mock_reflect:
        res = loop.execute_engine_repairs(diagnoses, force=False, dry_run=False)

        assert mock_preflight.quarantine_blocked_urls.called
        assert mock_reflect.called
        assert res["dead_routes_quarantined"] == 1
        assert res["recompiled_assets_count"] == 2
        assert res["reflection"]["status"] == "SUCCESS"


def test_feedback_loop_multi_engine_push_idempotency(tmp_path):
    """
    Verifies filter_unchanged_push_urls and dispatch_multi_engine_push
    enforce composite idempotency: (tenant_id, target_url, engine, content_sha256).
    Identical content on second submission returns IDEMPOTENT_NO_OP.
    """
    dist_dir = tmp_path / "dist"
    tool_dir = dist_dir / "tools" / "test-calc"
    tool_dir.mkdir(parents=True, exist_ok=True)
    html_file = tool_dir / "index.html"
    html_file.write_text("<html><body><h1>Test Calculator</h1></body></html>", encoding="utf-8")

    ledger_path = tmp_path / ".agy" / "index_push_ledger.json"
    rollover_path = tmp_path / ".agy" / "gsc_rollover_queue.json"

    indexer = PushIndexer(
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        base_dir=tmp_path,
        dist_dir=dist_dir,
        ledger_path=ledger_path,
        rollover_queue_path=rollover_path,
        tenant_id="profithelm",
    )

    url = "https://profithelm.com/tools/test-calc/"

    # First run: empty ledger -> to_push=1, skipped=0
    to_push, skipped = indexer.filter_unchanged_push_urls([url], tenant_id="profithelm")
    assert to_push == [url]
    assert skipped == []

    # Record push
    indexer.record_pushed_urls(to_push, tenant_id="profithelm")

    # Second run: same content hash -> to_push=0, skipped=1
    to_push2, skipped2 = indexer.filter_unchanged_push_urls([url], tenant_id="profithelm")
    assert to_push2 == []
    assert skipped2 == [url]

    # Feedback loop dispatch returns IDEMPOTENT_NO_OP
    loop = IndexingFeedbackLoop(
        property_id="profithelm",
        base_dir=tmp_path,
        dist_dir=dist_dir,
        indexer=indexer,
    )
    res = loop.dispatch_multi_engine_push([url])
    assert res["status"] == "IDEMPOTENT_NO_OP"
    assert res["urls_pushed"] == 0
    assert res["urls_skipped"] == 1


def test_feedback_loop_network_partition_preserves_rollover_queue(tmp_path):
    """
    Verifies HWL-1349 resilience: simulated HTTP 429 quota exhaustion or network timeout
    breaks the outbound batch, preserves pending URLs in gsc_rollover_queue.json without
    dropped batches, and logs INDEXING_ANOMALY telemetry.
    """
    rollover_path = tmp_path / ".agy" / "gsc_rollover_queue.json"
    ledger_path = tmp_path / ".agy" / "index_push_ledger.json"
    telemetry_path = tmp_path / ".agy" / "telemetry_events.jsonl"

    indexer = PushIndexer(
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        base_dir=tmp_path,
        dist_dir=tmp_path / "dist",
        ledger_path=ledger_path,
        rollover_queue_path=rollover_path,
        tenant_id="profithelm",
    )

    urls = [
        "https://profithelm.com/tools/alpha/",
        "https://profithelm.com/tools/beta/",
        "https://profithelm.com/tools/gamma/",
    ]

    call_count = 0

    def mock_subprocess_run(cmd, *args, **kwargs):
        nonlocal call_count
        cmd_str = " ".join(cmd)
        if "fast-index" in cmd_str:
            return subprocess.CompletedProcess(cmd, 0, stdout='{"actions": ["fast-index ok"]}')
        if "gsccli" in cmd_str and "publish" in cmd_str:
            call_count += 1
            if call_count == 1:
                return subprocess.CompletedProcess(cmd, 0, stdout="ACCEPTED")
            # Second URL encounters HTTP 429 quota limit
            return subprocess.CompletedProcess(
                cmd, 1, stderr="HTTP 429 Quota exceeded for quota metric 'Indexing requests'"
            )
        return subprocess.CompletedProcess(cmd, 0, stdout="")

    with patch("shutil.which", return_value="/mock/bin/gsccli"), \
         patch("pathlib.Path.is_file", return_value=True), \
         patch("subprocess.run", side_effect=mock_subprocess_run), \
         patch.dict("os.environ", {"FACTORY_TELEMETRY_PATH": str(telemetry_path)}):

        res = indexer.submit_gsc_indexing(urls=urls, live=True, drain_rollover=False)

        # First URL succeeded, second failed with 429, third never executed
        assert call_count == 2

        # Preserved in rollover queue: beta (failed with 429) + gamma (untried)
        pending_rollover = indexer.load_gsc_rollover_queue()
        assert "https://profithelm.com/tools/beta/" in pending_rollover
        assert "https://profithelm.com/tools/gamma/" in pending_rollover
        assert "https://profithelm.com/tools/alpha/" not in pending_rollover

        # Verify telemetry event recorded
        assert telemetry_path.exists()
        lines = [json.loads(l) for l in telemetry_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        anomaly_events = [e for e in lines if e.get("event_type") == "INDEXING_ANOMALY"]
        assert len(anomaly_events) >= 1
        assert anomaly_events[0]["action_taken"] == "PRESERVED_ROLLOVER"


def test_maintenance_stage_10_does_not_swallow_errors(tmp_path):
    """
    Verifies MaintenanceLifecycle Stage 10 does not swallow unhandled indexing dispatch errors:
    records indexing_status='FAILED', status='PARTIAL', and emits INDEXING_DISPATCH_FAILURE telemetry.
    """
    telemetry_path = tmp_path / ".agy" / "telemetry_events.jsonl"

    failing_indexer = MagicMock()
    failing_indexer.dispatch_automated_indexing.side_effect = RuntimeError(
        "Network partition during multi-engine dispatch"
    )

    adapter = ConfigurablePropertyAdapter(
        property_id="profithelm",
        brand_name="ProfitHelm",
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        dist_dir=tmp_path / "dist",
    )
    (tmp_path / "dist").mkdir(parents=True, exist_ok=True)
    (tmp_path / "dist" / "index.html").write_text("<html><body>Root</body></html>", encoding="utf-8")

    lifecycle = MaintenanceLifecycle(indexer=failing_indexer)

    with patch.dict("os.environ", {"FACTORY_TELEMETRY_PATH": str(telemetry_path)}):
        result = lifecycle.run(
            adapter,
            force=True,
            dry_run=False,
        )

        assert result.indexing_status == "FAILED"
        assert result.status == "PARTIAL"

        assert telemetry_path.exists()
        events = [json.loads(l) for l in telemetry_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        dispatch_failures = [e for e in events if e.get("event_type") == "INDEXING_DISPATCH_FAILURE"]
        assert len(dispatch_failures) >= 1
        assert "Network partition" in dispatch_failures[0]["error_message"]


def test_indexing_feedback_loop_cli(capsys):
    """
    Verifies pseofactory CLI indexing-feedback-loop subcommand executes
    and emits structured JSON with diagnosis and preflight summaries.
    """
    from pseofactory.cli import build_parser, cmd_indexing_feedback_loop

    parser = build_parser()
    args = parser.parse_args(["indexing-feedback-loop", "--property", "profithelm", "--dry-run", "--json"])

    exit_code = cmd_indexing_feedback_loop(args)
    captured = capsys.readouterr()

    assert exit_code == 0
    parsed = json.loads(captured.out)
    assert parsed["property_id"] == "profithelm"
    assert parsed["status"] in ("SUCCESS", "PARTIAL")
    assert parsed["dry_run"] is True
    assert "preflight_summary" in parsed
    assert "push_summary" in parsed
    assert "diagnosed_defects" in parsed
