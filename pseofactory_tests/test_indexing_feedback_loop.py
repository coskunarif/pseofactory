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


def test_autonomous_closed_loop_defect_to_html_reflection_preflight_gitops_and_republication(tmp_path):
    """
    End-to-end closed-loop validation:
    1. Unindexed page defects (wrong canonical, accidental noindex, missing answer box, 404 dead route in sitemap)
       are diagnosed automatically.
    2. Dead 404 URLs are pruned from sitemap.xml and quarantined.
    3. Defective HTML asset in dist/ is automatically reflected with corrected canonical, removed noindex,
       injected <aside id="quick-answer"> and #gsc-striking-overlay, plus persisted overlay JSON.
    4. Repaired asset passes IndexingPreflightEngine 6-stage gate.
    5. GitOpsCoordinator ships before PushIndexer dispatches multi-engine republication.
    """
    from pseofactory.indexing.preflight import IndexingPreflightEngine

    dist_dir = tmp_path / "dist"
    tool_dir = dist_dir / "tools" / "burn-rate-calculator"
    tool_dir.mkdir(parents=True, exist_ok=True)
    html_file = tool_dir / "index.html"

    body_words = " ".join(["Statutory financial burn rate analysis and runway modeling metric."] * 35)
    defective_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Burn Rate Calculator</title>
  <meta name="robots" content="noindex, nofollow">
  <link rel="canonical" href="https://wrong-domain.example.com/tools/burn-rate-calculator/">
  <script type="application/ld+json">{{"@context": "https://schema.org", "@type": "SoftwareApplication", "name": "Burn Rate Calculator"}}</script>
</head>
<body>
  <main>
    <p>{body_words}</p>
    <form><input type="number" name="cash" value="100000"></form>
    <a href="https://profithelm.com/">Home</a>
  </main>
</body>
</html>"""
    html_file.write_text(defective_html, encoding="utf-8")

    sitemap_path = dist_dir / "sitemap.xml"
    sitemap_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://profithelm.com/tools/burn-rate-calculator/</loc></url>
  <url><loc>https://profithelm.com/tools/deleted-404-tool/</loc></url>
</urlset>""",
        encoding="utf-8",
    )

    indexer = PushIndexer(
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        base_dir=tmp_path,
        dist_dir=dist_dir,
        ledger_path=tmp_path / ".agy" / "index_push_ledger.json",
        rollover_queue_path=tmp_path / ".agy" / "gsc_rollover_queue.json",
        tenant_id="profithelm",
    )
    preflight = IndexingPreflightEngine(
        property_id="profithelm",
        domain="profithelm.com",
        dist_dir=dist_dir,
    )
    mock_gitops = MagicMock()
    mock_gitops.commit_and_push_atomic.return_value = {
        "status": "COMMITTED_AND_PUSHED",
        "commit_sha": "abc1234",
    }

    loop = IndexingFeedbackLoop(
        property_id="profithelm",
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        base_dir=tmp_path,
        dist_dir=dist_dir,
        indexer=indexer,
        preflight_engine=preflight,
        gitops_coordinator=mock_gitops,
    )

    unindexed_records = [
        {
            "url": "https://profithelm.com/tools/burn-rate-calculator/",
            "coverageState": "Crawled - currently not indexed",
            "slug": "burn-rate-calculator",
        },
        {
            "url": "https://profithelm.com/tools/deleted-404-tool/",
            "status_code": 404,
            "error": "quarantine_http_error",
        },
    ]

    with patch.object(indexer, "submit_indexnow_batch", return_value={"status": "ACCEPTED"}), \
         patch.object(indexer, "submit_gsc_indexing", return_value={"status": "ACCEPTED"}), \
         patch.object(indexer, "ping_websub_hub", return_value={"status": "ACCEPTED"}), \
         patch.object(indexer, "ping_pingomatic", return_value={"status": "ACCEPTED"}):
        report = loop.run_feedback_cycle(
            unindexed_records=unindexed_records,
            force=False,
            dry_run=False,
            skip_recompile=True,
        )

    # 1. Verify sitemap pruned 404 dead route but kept valid route
    updated_sitemap = sitemap_path.read_text(encoding="utf-8")
    assert "deleted-404-tool" not in updated_sitemap
    assert "burn-rate-calculator" in updated_sitemap

    # 2. Verify HTML asset was reflected & repaired automatically
    repaired_html = html_file.read_text(encoding="utf-8")
    assert 'href="https://profithelm.com/tools/burn-rate-calculator/' in repaired_html
    assert "noindex" not in repaired_html.lower()
    assert 'id="quick-answer"' in repaired_html
    assert 'id="gsc-striking-overlay"' in repaired_html
    assert "<h1>" in repaired_html.lower()
    assert (tmp_path / "content" / "overlays" / "burn-rate-calculator.json").is_file()

    # 3. Verify preflight passed after reflection repair
    assert report["preflight_summary"]["status"] == "READY_FOR_INDEXING"
    assert any("burn-rate-calculator" in u for u in report["preflight_summary"]["eligible_urls"])

    # 4. Verify GitOps shipping executed before search dispatch
    assert mock_gitops.commit_and_push_atomic.called
    assert report["gitops_summary"]["status"] == "COMMITTED_AND_PUSHED"
    assert report["push_summary"]["status"] in ("SUCCESS", "DISPATCHED")
    assert report["push_summary"]["urls_pushed"] >= 1


def test_feedback_loop_blocks_search_dispatch_when_gitops_fails(tmp_path):
    """
    Verifies that if GitOps release shipping fails after preflight, search engine
    dispatch is aborted (status='SKIPPED_GITOPS_FAILED') so unshipped local repairs
    are never pushed to search engines.
    """
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    mock_indexer = MagicMock()
    mock_indexer.load_gsc_rollover_queue.return_value = []
    mock_preflight = MagicMock()
    mock_preflight.inspect_dist.return_value = MagicMock(
        total_inspected=1,
        passed_count=1,
        blocked_count=0,
        push_eligible_urls=["https://profithelm.com/tools/calc/"],
        sitemap_eligible_urls=["https://profithelm.com/tools/calc/"],
        blocked_urls={},
    )
    mock_gitops = MagicMock()
    mock_gitops.commit_and_push_atomic.return_value = {
        "status": "FAILED",
        "reason": "git_push_failed",
    }

    loop = IndexingFeedbackLoop(
        property_id="profithelm",
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        base_dir=tmp_path,
        dist_dir=dist_dir,
        indexer=mock_indexer,
        preflight_engine=mock_preflight,
        gitops_coordinator=mock_gitops,
    )

    with patch.object(loop, "execute_engine_repairs", return_value={
        "recompiled_assets_count": 1,
        "html_files_repaired": 1,
        "dead_routes_quarantined": 0,
        "sitemaps_pruned": 0,
        "overlays_written": ["calc"],
    }):
        report = loop.run_feedback_cycle(
            unindexed_records=[{
                "url": "https://profithelm.com/tools/calc/",
                "coverageState": "Crawled - currently not indexed",
            }],
            dry_run=False,
        )

    assert report["gitops_summary"]["status"] == "FAILED"
    assert report["push_summary"]["status"] == "SKIPPED_GITOPS_FAILED"
    assert report["status"] == "PARTIAL"
    assert not mock_indexer.submit_indexnow_batch.called


def test_unverified_foreign_domain_quota_guard_and_429_circuit_breaker(tmp_path):
    """
    Verifies PushIndexer blocks unverified foreign domains before calling gsccli
    and trips the 429 quota circuit breaker during inspection loops.
    """
    indexer = PushIndexer(
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        base_dir=tmp_path,
        dist_dir=tmp_path / "dist",
        tenant_id="profithelm",
    )

    with patch("subprocess.run") as mock_subproc:
        foreign_res = indexer.inspect_gsc_url("https://unverified-competitor.example.org/tool")
        assert foreign_res["status"] == "BLOCKED_UNVERIFIED_DOMAIN"
        assert not mock_subproc.called

    # Verify 429 circuit breaker halts verify_gsc_indexation_loop immediately
    inspect_calls = []

    def fake_inspect(url, site=None, timeout=15):
        inspect_calls.append(url)
        return {
            "url": url,
            "status": "QUOTA_EXHAUSTED",
            "quota_exhausted": True,
            "stderr": "HTTP 429 Too Many Requests",
        }

    with patch.object(indexer, "preflight_airlock", side_effect=lambda urls: (list(urls), [])), \
         patch.object(indexer, "inspect_gsc_url", side_effect=fake_inspect):
        loop_res = indexer.verify_gsc_indexation_loop(
            urls=[
                "https://profithelm.com/tools/one/",
                "https://profithelm.com/tools/two/",
                "https://profithelm.com/tools/three/",
            ],
            live=True,
        )
        assert len(inspect_calls) == 1
        assert loop_res["quota_circuit_breaker_tripped"] is True


def test_refactor_cascade_preserves_active_remediation_overlay(tmp_path):
    """
    Verifies RefactorCascadeEngine._reapply_active_overlay preserves active
    content/overlays/{slug}.json overlays when an asset is rebuilt from template.
    """
    from pseofactory.maintenance import AssetDriftRecord, DriftReason, RefactorCascadeEngine

    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    asset_file = dist_dir / "tax-calc.html"
    asset_file.write_text("<html><body><main><h1>Tax Calc</h1></main></body></html>", encoding="utf-8")

    overlay_dir = tmp_path / "content" / "overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    overlay_file = overlay_dir / "tax-calc.json"
    overlay_file.write_text(
        json.dumps({
            "slug": "tax-calc",
            "status": "ACTIVE_MEASUREMENT_LOCK",
            "h2_blocks": [{"heading": "2026 Tax Deduction Rules", "intent": "explain deduction rules"}],
            "faq_items": [{"question": "How is it calculated?", "answer": "Using IRS statutory brackets."}],
        }),
        encoding="utf-8",
    )

    def rebuild_fn(slug, target_file=None):
        out = target_file or asset_file
        out.write_text("<html><body><main><h1>Tax Calc Rebuilt</h1></main></body></html>", encoding="utf-8")
        return True

    adapter = ConfigurablePropertyAdapter(
        property_id="profithelm",
        brand_name="ProfitHelm",
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        dist_dir=dist_dir,
        repo_path=tmp_path,
        build_asset_fn=rebuild_fn,
    )
    evaluator = MagicMock()
    evaluator.audit_asset.return_value = None
    engine = RefactorCascadeEngine(evaluator=evaluator, dlq_path=tmp_path / ".agy" / "dlq.json")

    record = AssetDriftRecord(
        asset_path=str(asset_file),
        slug="tax-calc",
        reasons=[DriftReason.ENGINE_HASH_DRIFT],
    )
    ok = engine.refactor_asset(record, adapter, force=True, dry_run=False)
    assert ok is True
    final_html = asset_file.read_text(encoding="utf-8")
    assert "Tax Calc Rebuilt" in final_html
    assert 'id="gsc-striking-overlay"' in final_html
    assert "2026 Tax Deduction Rules" in final_html


def test_telemetry_monetization_loop_spots_conversion_and_distribution_gaps_and_prioritizes_calculators_and_guides(tmp_path):
    """
    Verifies the closed loop between search ranking telemetry and monetization/distribution:
    1. Spots impression-gaining pages lacking strong conversion paths or external distribution.
    2. Prioritizes high-intent calculators and guides ahead of low-intent general pages.
    3. Automatically sharpens content, injects vertical-clustered internal links and compliant
       partner offer placements into HTML, and generates missing external syndication files.
    """
    from pseofactory.action_bus import HumanActionBus

    dist_dir = tmp_path / "dist"
    calc_dir = dist_dir / "tools" / "landed-cost-calculator"
    guide_dir = dist_dir / "tools" / "section-301-tariff-audit-guide"
    about_dir = dist_dir / "about"
    for d in (calc_dir, guide_dir, about_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Create bare HTML pages that lack conversion paths (no partner CTA, no preset scenarios, no internal hub links)
    bare_html_tpl = (
        "<!DOCTYPE html><html><head><title>{title}</title>"
        '<meta name="description" content="Short description.">'
        "</head><body><main><h1>{title}</h1><p>Initial statutory content.</p></main></body></html>"
    )
    (calc_dir / "index.html").write_text(bare_html_tpl.format(title="Landed Cost Calculator"), encoding="utf-8")
    (guide_dir / "index.html").write_text(bare_html_tpl.format(title="Section 301 Tariff Audit Guide"), encoding="utf-8")
    (about_dir / "index.html").write_text(bare_html_tpl.format(title="About ProfitHelm"), encoding="utf-8")

    mock_indexer = MagicMock()
    mock_indexer.filter_unchanged_push_urls.side_effect = lambda urls, **kw: (list(urls), [])
    mock_indexer.dispatch_automated_indexing.return_value = {"status": "SUCCESS"}
    mock_indexer.load_gsc_rollover_queue.return_value = []

    mock_preflight = MagicMock()
    mock_report = MagicMock()
    mock_report.passed_count = 2
    mock_report.blocked_count = 0
    mock_report.total_inspected = 2
    mock_report.blocked_urls = []
    mock_report.push_eligible_urls = [
        "https://profithelm.com/tools/landed-cost-calculator/",
        "https://profithelm.com/tools/section-301-tariff-audit-guide/",
    ]
    mock_report.sitemap_eligible_urls = []
    mock_preflight.inspect_dist.return_value = mock_report

    bus = HumanActionBus(ledger_path=tmp_path / ".agy" / "human_action_bus.json")
    loop = IndexingFeedbackLoop(
        property_id="profithelm",
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        base_dir=tmp_path,
        dist_dir=dist_dir,
        indexer=mock_indexer,
        inspector=MagicMock(),
        preflight_engine=mock_preflight,
        milestone_tracker=MagicMock(event_log=[]),
        telemetry_logger=MagicMock(),
        action_bus=bus,
    )

    # Give all 3 pages identical search impressions/position/CTR to verify intent + gap prioritization
    query_records = [
        {
            "slug": "about",
            "target_url": "https://profithelm.com/about/",
            "query": "about profithelm company overview",
            "impressions": 300,
            "clicks": 6,
            "ctr": 0.02,
            "position": 8.0,
        },
        {
            "slug": "section-301-tariff-audit-guide",
            "target_url": "https://profithelm.com/tools/section-301-tariff-audit-guide/",
            "query": "section 301 tariff audit compliance guide",
            "impressions": 300,
            "clicks": 6,
            "ctr": 0.02,
            "position": 8.0,
        },
        {
            "slug": "landed-cost-calculator",
            "target_url": "https://profithelm.com/tools/landed-cost-calculator/",
            "query": "landed cost import duty calculator",
            "impressions": 300,
            "clicks": 6,
            "ctr": 0.02,
            "position": 8.0,
        },
    ]

    res = loop.run_feedback_cycle(
        unindexed_urls=[],
        query_records=query_records,
        skip_recompile=True,
    )

    assert res["status"] == "SUCCESS"
    prioritized = res["prioritized_candidates"]
    assert len(prioritized) == 3

    # Calculator and Guide must outrank the general 'about' page
    assert prioritized[0]["slug"] == "landed-cost-calculator"
    assert prioritized[0]["intent_class"] == "calculator"
    assert prioritized[0]["is_high_intent_calculator_or_guide"] is True
    assert prioritized[0]["conversion_gap_detected"] is True
    assert prioritized[0]["distribution_gap_detected"] is True

    assert prioritized[1]["slug"] == "section-301-tariff-audit-guide"
    assert prioritized[1]["intent_class"] == "guide"
    assert prioritized[1]["is_high_intent_calculator_or_guide"] is True

    assert prioritized[2]["slug"] == "about"
    assert prioritized[2]["intent_class"] == "general"
    assert prioritized[2]["is_high_intent_calculator_or_guide"] is False

    # Verify conversion gaps and distribution gaps were closed for calculator and guide
    assert "landed-cost-calculator" in res["conversion_gaps_closed"]
    assert "section-301-tariff-audit-guide" in res["conversion_gaps_closed"]
    assert "landed-cost-calculator" in res["distribution_gaps_closed"]
    assert "section-301-tariff-audit-guide" in res["distribution_gaps_closed"]

    # Inspect sharpened HTML on landed-cost-calculator
    calc_html = (calc_dir / "index.html").read_text(encoding="utf-8")
    assert 'class="quick-answer' in calc_html
    assert "data-calc-preset=" in calc_html
    assert 'class="overlay-section overlay-hub-links"' in calc_html
    assert "/tools/section-301-tariff-landed-cost-calculator/" in calc_html
    assert 'class="overlay-section overlay-partner-offer affiliate-cta-section card"' in calc_html
    assert 'data-partner="flexport"' in calc_html
    assert 'rel="noopener sponsored nofollow"' in calc_html
    assert "\u2014" not in calc_html
    assert "\u2013" not in calc_html

    # Inspect generated external syndication files
    synd_dir = tmp_path / "syndication"
    assert (synd_dir / "landed-cost-calculator-linkedin.md").is_file()
    assert (synd_dir / "landed-cost-calculator-newsletter.md").is_file()
    assert (synd_dir / "landed-cost-calculator-Substack Notes-post.txt").is_file()


def test_prexvo_feedback_loop_enforces_ymyl_guardrail_and_places_commercial_refi_offers(tmp_path):
    """
    Verifies that on Prexvo:
    1. Public-service pages gaining impressions (pslf-qualifying-payment-simulator) receive
       sharpened content, internal links, and external syndication, but strictly suppress
       commercial private refinance offers (restricted_public_service=True).
    2. Commercial calculators gaining impressions (student-loan-refinance-break-even-calculator)
       receive live compliant partner offer placements.
    """
    dist_dir = tmp_path / "dist"
    pslf_dir = dist_dir / "tools" / "pslf-qualifying-payment-simulator"
    refi_dir = dist_dir / "tools" / "student-loan-refinance-break-even-calculator"
    pslf_dir.mkdir(parents=True, exist_ok=True)
    refi_dir.mkdir(parents=True, exist_ok=True)

    bare_html = "<!DOCTYPE html><html><head><title>Tool</title></head><body><main><h1>Tool</h1></main></body></html>"
    (pslf_dir / "index.html").write_text(bare_html, encoding="utf-8")
    (refi_dir / "index.html").write_text(bare_html, encoding="utf-8")

    mock_indexer = MagicMock()
    mock_indexer.filter_unchanged_push_urls.side_effect = lambda urls, **kw: (list(urls), [])
    mock_indexer.dispatch_automated_indexing.return_value = {"status": "SUCCESS"}
    mock_indexer.load_gsc_rollover_queue.return_value = []

    mock_preflight = MagicMock()
    mock_report = MagicMock(
        passed_count=2,
        blocked_count=0,
        total_inspected=2,
        blocked_urls=[],
        push_eligible_urls=[
            "https://prexvo.com/tools/pslf-qualifying-payment-simulator/",
            "https://prexvo.com/tools/student-loan-refinance-break-even-calculator/",
        ],
        sitemap_eligible_urls=[],
    )
    mock_preflight.inspect_dist.return_value = mock_report

    loop = IndexingFeedbackLoop(
        property_id="prexvo",
        domain="prexvo.com",
        canonical_base="https://prexvo.com",
        base_dir=tmp_path,
        dist_dir=dist_dir,
        indexer=mock_indexer,
        inspector=MagicMock(),
        preflight_engine=mock_preflight,
        milestone_tracker=MagicMock(event_log=[]),
        telemetry_logger=MagicMock(),
    )

    res = loop.run_feedback_cycle(
        unindexed_urls=[],
        query_records=[
            {
                "slug": "pslf-qualifying-payment-simulator",
                "target_url": "https://prexvo.com/tools/pslf-qualifying-payment-simulator/",
                "query": "pslf qualifying payment buyback simulator",
                "impressions": 420,
                "clicks": 9,
                "ctr": 0.021,
                "position": 6.5,
            },
            {
                "slug": "student-loan-refinance-break-even-calculator",
                "target_url": "https://prexvo.com/tools/student-loan-refinance-break-even-calculator/",
                "query": "student loan refinance rate break even calculator",
                "impressions": 380,
                "clicks": 8,
                "ctr": 0.021,
                "position": 7.2,
            },
        ],
        skip_recompile=True,
    )

    assert res["status"] == "SUCCESS"
    pslf_html = (pslf_dir / "index.html").read_text(encoding="utf-8")
    assert 'data-restricted-public-service="true"' in pslf_html
    assert 'data-commercial-offers="none"' in pslf_html
    assert "affiliate-cta-link" not in pslf_html

    refi_html = (refi_dir / "index.html").read_text(encoding="utf-8")
    assert 'class="overlay-section overlay-partner-offer affiliate-cta-section card"' in refi_html
    assert 'rel="noopener sponsored nofollow"' in refi_html
    assert "sofi.com" in refi_html


def test_manual_partner_or_platform_dependency_routes_single_clean_alert_without_interrupting_growth_loop(tmp_path):
    """
    Verifies that when multiple impression-gaining assets hit the same manual partner or
    platform requirement, a single clean deduplicated alert is routed onto HumanActionBus
    while all other autonomous sharpening, fallback partner placement, syndication, and
    search push stages complete uninterrupted.
    """
    from pseofactory.action_bus import HumanActionBus

    dist_dir = tmp_path / "dist"
    bond1_dir = dist_dir / "tools" / "customs-bond-sufficiency-calculator"
    bond2_dir = dist_dir / "tools" / "continuous-customs-bond-cost-estimator"
    saas_dir = dist_dir / "tools" / "saas-burn-multiple-runway-calculator"
    for d in (bond1_dir, bond2_dir, saas_dir):
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(
            "<!DOCTYPE html><html><head><title>Tool</title></head><body><main><h1>Tool</h1></main></body></html>",
            encoding="utf-8",
        )

    bus = HumanActionBus(ledger_path=tmp_path / ".agy" / "human_action_bus.json")
    mock_indexer = MagicMock()
    mock_indexer.filter_unchanged_push_urls.side_effect = lambda urls, **kw: (list(urls), [])
    mock_indexer.dispatch_automated_indexing.return_value = {"status": "SUCCESS"}
    mock_indexer.load_gsc_rollover_queue.return_value = []

    mock_preflight = MagicMock()
    mock_preflight.inspect_dist.return_value = MagicMock(
        passed_count=3,
        blocked_count=0,
        total_inspected=3,
        blocked_urls=[],
        push_eligible_urls=[
            "https://profithelm.com/tools/customs-bond-sufficiency-calculator/",
            "https://profithelm.com/tools/continuous-customs-bond-cost-estimator/",
            "https://profithelm.com/tools/saas-burn-multiple-runway-calculator/",
        ],
        sitemap_eligible_urls=[],
    )

    loop = IndexingFeedbackLoop(
        property_id="profithelm",
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        base_dir=tmp_path,
        dist_dir=dist_dir,
        indexer=mock_indexer,
        inspector=MagicMock(),
        preflight_engine=mock_preflight,
        milestone_tracker=MagicMock(event_log=[]),
        telemetry_logger=MagicMock(),
        action_bus=bus,
    )

    # Both customs bond calculators hit the suretybonds_direct manual partner gate
    res = loop.run_feedback_cycle(
        unindexed_urls=[],
        query_records=[
            {
                "slug": "customs-bond-sufficiency-calculator",
                "target_url": "https://profithelm.com/tools/customs-bond-sufficiency-calculator/",
                "query": "customs bond sufficiency calculator",
                "impressions": 510,
                "clicks": 11,
                "ctr": 0.021,
                "position": 5.8,
            },
            {
                "slug": "continuous-customs-bond-cost-estimator",
                "target_url": "https://profithelm.com/tools/continuous-customs-bond-cost-estimator/",
                "query": "continuous customs bond cost estimator",
                "impressions": 440,
                "clicks": 9,
                "ctr": 0.020,
                "position": 6.4,
            },
            {
                "slug": "saas-burn-multiple-runway-calculator",
                "target_url": "https://profithelm.com/tools/saas-burn-multiple-runway-calculator/",
                "query": "saas burn multiple cash runway calculator",
                "impressions": 390,
                "clicks": 8,
                "ctr": 0.020,
                "position": 7.1,
            },
        ],
        skip_recompile=True,
    )

    assert res["status"] == "SUCCESS"
    # Exactly ONE clean deduplicated alert routed for suretybonds_direct across both customs bond calculators
    pending_alerts = bus.get_pending_items("profithelm")
    assert len(pending_alerts) == 1
    alert = pending_alerts[0]
    assert alert.partner_key == "suretybonds_direct"
    assert any("customs-bond-sufficiency-calculator" in r for r in alert.missing_requirements)
    assert any("continuous-customs-bond-cost-estimator" in r for r in alert.missing_requirements)

    # Meanwhile, all 3 calculators completed HTML sharpening, live fallback partner placement, and syndication
    assert len(res["conversion_gaps_closed"]) == 3
    assert len(res["distribution_gaps_closed"]) == 3
    assert (bond1_dir / "index.html").read_text(encoding="utf-8").count('data-partner="flexport"') >= 1
    assert (saas_dir / "index.html").read_text(encoding="utf-8").count('data-partner="ramp"') >= 1
    assert (tmp_path / "syndication" / "saas-burn-multiple-runway-calculator-linkedin.md").is_file()


def test_outbound_engagement_telemetry_promotes_higher_converting_partner_offers_on_top_traffic_pages(tmp_path):
    """
    Verifies that the monetization loop extends beyond initial offer placement:
    1. Tracks calculator CTA slots and outbound partner clicks per slug and per partner.
    2. Detects when a top traffic page's current partner offer lags a higher-converting
       partner in the same vertical (yield_optimization_needed=True).
    3. Automatically promotes higher-converting partner offers in-place on both
       ProfitHelm (e.g., promoting brex over ramp and koinly over coinledger) and
       Prexvo (promoting earnest over sofi_refi while preserving YMYL PSLF suppression).
    """
    from pseofactory.action_bus import HumanActionBus

    # --- 1. ProfitHelm Tenant Verification ---
    ph_base = tmp_path / "profithelm"
    ph_dist = ph_base / "dist"
    saas_dir = ph_dist / "tools" / "saas-burn-multiple-runway-calculator"
    crypto_dir = ph_dist / "tools" / "crypto-tax-liability-calculator-2027"
    saas_dir.mkdir(parents=True, exist_ok=True)
    crypto_dir.mkdir(parents=True, exist_ok=True)

    # Initial pages already have baseline offers (ramp and coinledger), presets, quick-answer, and internal links
    initial_saas_html = (
        '<!DOCTYPE html><html><head><title>SaaS Burn Multiple Calculator</title></head><body><main>'
        '<h1>SaaS Burn Multiple Calculator</h1>'
        '<div class="quick-answer"><p>Calculate SaaS burn multiple and cash runway.</p></div>'
        '<button data-calc-preset="baseline">Baseline</button>'
        '<a href="/tools/saas-cac-payback-period-calculator/">CAC Payback</a>'
        '<a href="/tools/inventory-carrying-cost-calculator/">Inventory Cost</a>'
        '<section class="overlay-section overlay-partner-offer affiliate-cta-section card" data-partner="ramp">'
        '<a href="https://ramp.com/?ref=profithelm" class="overlay-partner-btn affiliate-cta-link" '
        'data-partner="ramp" rel="noopener sponsored nofollow">Compare Ramp Corporate Cards</a>'
        '</section></main></body></html>'
    )
    initial_crypto_html = (
        '<!DOCTYPE html><html><head><title>Crypto Tax Calculator 2027</title></head><body><main>'
        '<h1>Crypto Tax Calculator 2027</h1>'
        '<div class="quick-answer"><p>Calculate Form 1099-DA crypto capital gains tax.</p></div>'
        '<button data-calc-preset="baseline">Baseline</button>'
        '<a href="/tools/irs-2027-tax-brackets/">2027 Tax Brackets</a>'
        '<a href="/tools/capital-gains-tax-calculator-2027/">Capital Gains</a>'
        '<section class="overlay-section overlay-partner-offer affiliate-cta-section card" data-partner="coinledger">'
        '<a href="https://coinledger.io/?fpr=lv44v" class="overlay-partner-btn affiliate-cta-link" '
        'data-partner="coinledger" rel="noopener sponsored nofollow">Import 1099-DA Trades into CoinLedger</a>'
        '</section></main></body></html>'
    )
    (saas_dir / "index.html").write_text(initial_saas_html, encoding="utf-8")
    (crypto_dir / "index.html").write_text(initial_crypto_html, encoding="utf-8")

    # Pre-create syndication files so distribution is already complete; only yield optimization is needed
    ph_synd = ph_base / "syndication"
    ph_synd.mkdir(parents=True, exist_ok=True)
    for slug in ("saas-burn-multiple-runway-calculator", "crypto-tax-liability-calculator-2027"):
        (ph_synd / f"{slug}-linkedin.md").write_text("LinkedIn copy", encoding="utf-8")
        (ph_synd / f"{slug}-newsletter.md").write_text("Newsletter copy", encoding="utf-8")
        (ph_synd / f"{slug}-Substack Notes-post.txt").write_text("Substack copy", encoding="utf-8")

    mock_indexer = MagicMock()
    mock_indexer.filter_unchanged_push_urls.side_effect = lambda urls, **kw: (list(urls), [])
    mock_indexer.dispatch_automated_indexing.return_value = {"status": "SUCCESS"}
    mock_indexer.load_gsc_rollover_queue.return_value = []

    mock_preflight = MagicMock()
    mock_preflight.inspect_dist.return_value = MagicMock(
        passed_count=2,
        blocked_count=0,
        total_inspected=2,
        blocked_urls=[],
        push_eligible_urls=[
            "https://profithelm.com/tools/saas-burn-multiple-runway-calculator/",
            "https://profithelm.com/tools/crypto-tax-liability-calculator-2027/",
        ],
        sitemap_eligible_urls=[],
    )

    ph_bus = HumanActionBus(ledger_path=ph_base / ".agy" / "human_action_bus.json")
    ph_loop = IndexingFeedbackLoop(
        property_id="profithelm",
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        base_dir=ph_base,
        dist_dir=ph_dist,
        indexer=mock_indexer,
        inspector=MagicMock(),
        preflight_engine=mock_preflight,
        milestone_tracker=MagicMock(event_log=[]),
        telemetry_logger=MagicMock(),
        action_bus=ph_bus,
    )

    # Outbound telemetry shows Brex out-converts Ramp on SaaS runway calculator,
    # and Koinly out-converts CoinLedger on Crypto tax calculator
    ph_engagement_events = [
        {"event_type": "page_view", "slug": "saas-burn-multiple-runway-calculator"},
        {"event_type": "calculation", "slug": "saas-burn-multiple-runway-calculator"},
        {"event_type": "select_preset", "slug": "saas-burn-multiple-runway-calculator", "cta_slot": "preset_scenario_cta"},
        {
            "event_type": "affiliate_click",
            "slug": "saas-burn-multiple-runway-calculator",
            "partner_key": "ramp",
            "cta_slot": "calculator_primary_cta",
            "payout_usd": 35.0,
        },
        {
            "event_type": "affiliate_click",
            "slug": "saas-burn-multiple-runway-calculator",
            "partner_key": "brex",
            "cta_slot": "preset_scenario_cta",
            "payout_usd": 250.0,
        },
        {
            "event_type": "affiliate_click",
            "slug": "saas-burn-multiple-runway-calculator",
            "partner_key": "brex",
            "cta_slot": "preset_scenario_cta",
            "payout_usd": 250.0,
        },
        {"event_type": "page_view", "slug": "crypto-tax-liability-calculator-2027"},
        {"event_type": "calculation", "slug": "crypto-tax-liability-calculator-2027"},
        {
            "event_type": "affiliate_click",
            "slug": "crypto-tax-liability-calculator-2027",
            "partner_key": "coinledger",
            "cta_slot": "calculator_primary_cta",
            "payout_usd": 35.0,
        },
        {
            "event_type": "affiliate_click",
            "slug": "crypto-tax-liability-calculator-2027",
            "partner_key": "koinly",
            "cta_slot": "calculator_primary_cta",
            "payout_usd": 85.0,
        },
        {
            "event_type": "affiliate_click",
            "slug": "crypto-tax-liability-calculator-2027",
            "partner_key": "koinly",
            "cta_slot": "calculator_primary_cta",
            "payout_usd": 85.0,
        },
    ]

    ph_res = ph_loop.run_feedback_cycle(
        unindexed_urls=[],
        query_records=[
            {
                "slug": "saas-burn-multiple-runway-calculator",
                "target_url": "https://profithelm.com/tools/saas-burn-multiple-runway-calculator/",
                "query": "saas burn multiple cash runway calculator",
                "impressions": 680,
                "clicks": 22,
                "ctr": 0.032,
                "position": 5.4,
            },
            {
                "slug": "crypto-tax-liability-calculator-2027",
                "target_url": "https://profithelm.com/tools/crypto-tax-liability-calculator-2027/",
                "query": "crypto tax form 1099 da capital gains calculator",
                "impressions": 540,
                "clicks": 18,
                "ctr": 0.033,
                "position": 6.1,
            },
        ],
        outbound_engagement_events=ph_engagement_events,
        skip_recompile=True,
    )

    assert ph_res["status"] == "SUCCESS"
    assert "saas-burn-multiple-runway-calculator" in ph_res["yield_optimized_slugs"]
    assert "crypto-tax-liability-calculator-2027" in ph_res["yield_optimized_slugs"]

    # Check telemetry summary captured top converting partners and CTA slots
    eng_sum = ph_res["outbound_engagement_summary"]
    assert eng_sum["total_outbound_clicks"] == 6
    assert eng_sum["by_slug"]["saas-burn-multiple-runway-calculator"]["top_converting_partner"] == "brex"
    assert eng_sum["by_slug"]["saas-burn-multiple-runway-calculator"]["top_converting_cta_slot"] == "preset_scenario_cta"
    assert eng_sum["by_slug"]["crypto-tax-liability-calculator-2027"]["top_converting_partner"] == "koinly"

    # Check HTML was upgraded in-place to the higher-converting partner offers
    updated_saas_html = (saas_dir / "index.html").read_text(encoding="utf-8")
    assert 'data-partner="brex"' in updated_saas_html
    assert 'data-optimization-status="YIELD_OPTIMIZED_PROMOTED"' in updated_saas_html
    assert 'data-cta-slot="preset_scenario_cta"' in updated_saas_html
    assert "\u2014" not in updated_saas_html
    assert "\u2013" not in updated_saas_html

    updated_crypto_html = (crypto_dir / "index.html").read_text(encoding="utf-8")
    assert 'data-partner="koinly"' in updated_crypto_html
    assert 'data-optimization-status="YIELD_OPTIMIZED_PROMOTED"' in updated_crypto_html
    assert "koinly.io" in updated_crypto_html

    # --- 2. Prexvo Tenant Verification ---
    px_base = tmp_path / "prexvo"
    px_dist = px_base / "dist"
    refi_dir = px_dist / "tools" / "student-loan-refinance-break-even-calculator"
    pslf_dir = px_dist / "tools" / "pslf-qualifying-payment-simulator"
    refi_dir.mkdir(parents=True, exist_ok=True)
    pslf_dir.mkdir(parents=True, exist_ok=True)

    initial_refi_html = (
        '<!DOCTYPE html><html><head><title>Student Loan Refinance Calculator</title></head><body><main>'
        '<h1>Student Loan Refinance Calculator</h1>'
        '<div class="quick-answer"><p>Compare private refinance savings against Title IV plans.</p></div>'
        '<button data-calc-preset="baseline">Baseline</button>'
        '<a href="/tools/rap-vs-ibr-calculator/">RAP vs IBR</a>'
        '<a href="/tools/tiered-standard-calculator/">Tiered Standard</a>'
        '<section class="overlay-section overlay-partner-offer affiliate-cta-section card" data-partner="sofi_refi">'
        '<a href="https://www.sofi.com/refinance-student-loan/?ref=prexvo" class="overlay-partner-btn affiliate-cta-link" '
        'data-partner="sofi_refi" rel="noopener sponsored nofollow">Check SoFi Refinance Rates</a>'
        '</section></main></body></html>'
    )
    (refi_dir / "index.html").write_text(initial_refi_html, encoding="utf-8")
    (pslf_dir / "index.html").write_text(
        "<!DOCTYPE html><html><head><title>PSLF Simulator</title></head><body><main><h1>PSLF Simulator</h1></main></body></html>",
        encoding="utf-8",
    )

    px_loop = IndexingFeedbackLoop(
        property_id="prexvo",
        domain="prexvo.com",
        canonical_base="https://prexvo.com",
        base_dir=px_base,
        dist_dir=px_dist,
        indexer=mock_indexer,
        inspector=MagicMock(),
        preflight_engine=mock_preflight,
        milestone_tracker=MagicMock(event_log=[]),
        telemetry_logger=MagicMock(),
        action_bus=HumanActionBus(ledger_path=px_base / ".agy" / "human_action_bus.json"),
    )

    px_engagement_events = [
        {"event_type": "page_view", "slug": "student-loan-refinance-break-even-calculator", "property_id": "prexvo"},
        {"event_type": "calculation", "slug": "student-loan-refinance-break-even-calculator", "property_id": "prexvo"},
        {
            "event_type": "affiliate_click",
            "slug": "student-loan-refinance-break-even-calculator",
            "partner_key": "sofi_refi",
            "cta_slot": "calculator_primary_cta",
            "payout_usd": 100.0,
            "property_id": "prexvo",
        },
        {
            "event_type": "affiliate_click",
            "slug": "student-loan-refinance-break-even-calculator",
            "partner_key": "earnest",
            "cta_slot": "calculator_primary_cta",
            "payout_usd": 150.0,
            "property_id": "prexvo",
        },
        {
            "event_type": "affiliate_click",
            "slug": "student-loan-refinance-break-even-calculator",
            "partner_key": "earnest",
            "cta_slot": "calculator_primary_cta",
            "payout_usd": 150.0,
            "property_id": "prexvo",
        },
    ]

    px_res = px_loop.run_feedback_cycle(
        unindexed_urls=[],
        query_records=[
            {
                "slug": "student-loan-refinance-break-even-calculator",
                "target_url": "https://prexvo.com/tools/student-loan-refinance-break-even-calculator/",
                "query": "student loan refinance rate break even calculator",
                "impressions": 490,
                "clicks": 16,
                "ctr": 0.032,
                "position": 5.9,
            },
            {
                "slug": "pslf-qualifying-payment-simulator",
                "target_url": "https://prexvo.com/tools/pslf-qualifying-payment-simulator/",
                "query": "pslf qualifying payment simulator",
                "impressions": 520,
                "clicks": 19,
                "ctr": 0.036,
                "position": 5.2,
            },
        ],
        outbound_engagement_events=px_engagement_events,
        skip_recompile=True,
    )

    assert px_res["status"] == "SUCCESS"
    assert "student-loan-refinance-break-even-calculator" in px_res["yield_optimized_slugs"]

    updated_refi_html = (refi_dir / "index.html").read_text(encoding="utf-8")
    assert 'data-partner="earnest"' in updated_refi_html
    assert 'data-optimization-status="YIELD_OPTIMIZED_PROMOTED"' in updated_refi_html
    assert "earnest.com" in updated_refi_html

    # Restricted public-service page must remain 100% free of commercial offers
    updated_pslf_html = (pslf_dir / "index.html").read_text(encoding="utf-8")
    assert 'data-restricted-public-service="true"' in updated_pslf_html
    assert 'data-commercial-offers="none"' in updated_pslf_html
    assert "affiliate-cta-link" not in updated_pslf_html


def test_pending_manual_partner_approvals_ranked_by_estimated_revenue_impact(tmp_path):
    """
    Verifies that when multiple pending manual partner approvals are routed onto HumanActionBus,
    they are automatically enriched with estimated monthly revenue impact and ranked in descending
    order of estimated revenue yield for human review.
    """
    from pseofactory.action_bus import HumanActionBus

    dist_dir = tmp_path / "dist"
    bond_dir = dist_dir / "tools" / "customs-bond-sufficiency-calculator"
    tax_dir = dist_dir / "tools" / "sales-tax-economic-nexus-calculator"
    payroll_dir = dist_dir / "tools" / "payroll-fica-tax-withholding-calculator"
    for d in (bond_dir, tax_dir, payroll_dir):
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(
            "<!DOCTYPE html><html><head><title>Tool</title></head><body><main><h1>Tool</h1></main></body></html>",
            encoding="utf-8",
        )

    bus = HumanActionBus(ledger_path=tmp_path / ".agy" / "human_action_bus.json")
    mock_indexer = MagicMock()
    mock_indexer.filter_unchanged_push_urls.side_effect = lambda urls, **kw: (list(urls), [])
    mock_indexer.dispatch_automated_indexing.return_value = {"status": "SUCCESS"}
    mock_indexer.load_gsc_rollover_queue.return_value = []

    mock_preflight = MagicMock()
    mock_preflight.inspect_dist.return_value = MagicMock(
        passed_count=3,
        blocked_count=0,
        total_inspected=3,
        blocked_urls=[],
        push_eligible_urls=[
            "https://profithelm.com/tools/customs-bond-sufficiency-calculator/",
            "https://profithelm.com/tools/sales-tax-economic-nexus-calculator/",
            "https://profithelm.com/tools/payroll-fica-tax-withholding-calculator/",
        ],
        sitemap_eligible_urls=[],
    )

    loop = IndexingFeedbackLoop(
        property_id="profithelm",
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        base_dir=tmp_path,
        dist_dir=dist_dir,
        indexer=mock_indexer,
        inspector=MagicMock(),
        preflight_engine=mock_preflight,
        milestone_tracker=MagicMock(event_log=[]),
        telemetry_logger=MagicMock(),
        action_bus=bus,
    )

    # Give sales-tax-economic-nexus-calculator (avalara: $250 bounty, 1800 impressions, 12 CTA clicks)
    # much higher traffic + CTA intent than payroll (gusto: $150 bounty, 500 impressions, 4 CTA clicks)
    # and customs bond (suretybonds_direct: $95 bounty, 200 impressions, 1 CTA click).
    engagement_events = [
        {"event_type": "affiliate_click", "slug": "sales-tax-economic-nexus-calculator", "partner_key": "stripe_tax", "payout_usd": 120.0}
        for _ in range(12)
    ] + [
        {"event_type": "affiliate_click", "slug": "payroll-fica-tax-withholding-calculator", "partner_key": "rippling", "payout_usd": 175.0}
        for _ in range(4)
    ] + [
        {"event_type": "affiliate_click", "slug": "customs-bond-sufficiency-calculator", "partner_key": "flexport", "payout_usd": 180.0}
    ]

    res = loop.run_feedback_cycle(
        unindexed_urls=[],
        query_records=[
            {
                "slug": "customs-bond-sufficiency-calculator",
                "target_url": "https://profithelm.com/tools/customs-bond-sufficiency-calculator/",
                "query": "customs bond sufficiency calculator",
                "impressions": 200,
                "clicks": 4,
                "ctr": 0.02,
                "position": 7.5,
            },
            {
                "slug": "payroll-fica-tax-withholding-calculator",
                "target_url": "https://profithelm.com/tools/payroll-fica-tax-withholding-calculator/",
                "query": "payroll fica tax withholding calculator",
                "impressions": 500,
                "clicks": 12,
                "ctr": 0.024,
                "position": 6.2,
            },
            {
                "slug": "sales-tax-economic-nexus-calculator",
                "target_url": "https://profithelm.com/tools/sales-tax-economic-nexus-calculator/",
                "query": "sales tax economic nexus threshold calculator",
                "impressions": 1800,
                "clicks": 45,
                "ctr": 0.025,
                "position": 5.1,
            },
        ],
        outbound_engagement_events=engagement_events,
        skip_recompile=True,
    )

    assert res["status"] == "SUCCESS"
    ranked = res["ranked_pending_partner_approvals"]
    assert len(ranked) == 3

    # Verify descending order by estimated_monthly_revenue_impact_usd: avalara (#1) > gusto (#2) > suretybonds_direct (#3)
    assert ranked[0]["partner_key"] == "avalara"
    assert ranked[0]["revenue_priority_rank"] == 1
    assert ranked[1]["partner_key"] == "gusto"
    assert ranked[1]["revenue_priority_rank"] == 2
    assert ranked[2]["partner_key"] == "suretybonds_direct"
    assert ranked[2]["revenue_priority_rank"] == 3

    assert ranked[0]["estimated_monthly_revenue_impact_usd"] > ranked[1]["estimated_monthly_revenue_impact_usd"]
    assert ranked[1]["estimated_monthly_revenue_impact_usd"] > ranked[2]["estimated_monthly_revenue_impact_usd"]
    assert ranked[0]["affected_traffic_impressions"] == 1800
    assert ranked[0]["outbound_cta_intent_clicks"] == 12


def test_semantic_quarantine_triage_and_unquarantine_passing_routes(tmp_path):
    """
    Verifies GSCRootCauseClassifier resolves cov='', err='OTHER' / status='QUARANTINED'
    records into CONTENT_QUALITY_OR_ANSWER_DEFICIENCY and prunes repaired passing routes
    from indexing_quarantine_ledger.json.
    """
    diag = GSCRootCauseClassifier.classify({
        "url": "https://profithelm.com/tools/section-1031-calculator/alaska/",
        "coverageState": "",
        "error": "OTHER",
        "status": "QUARANTINED",
        "stage": "PREFLIGHT",
    })
    assert diag.classification == RootCauseClassification.CONTENT_QUALITY_OR_ANSWER_DEFICIENCY.value
    assert "triage_source" in diag.metadata

    agy_dir = tmp_path / ".agy"
    agy_dir.mkdir(parents=True, exist_ok=True)
    q_path = agy_dir / "indexing_quarantine_ledger.json"
    q_path.write_text(
        json.dumps([
            {
                "property_id": "profithelm",
                "domain": "profithelm.com",
                "url": "https://profithelm.com/tools/section-1031-calculator/alaska/",
                "status": "BLOCKED",
                "stage": "PREFLIGHT",
                "error": "Failed preflight indexing airlock criteria",
            }
        ]),
        encoding="utf-8",
    )
    mock_preflight = MagicMock()
    mock_preflight.inspect_url.return_value = MagicMock(status="PASS")
    loop = IndexingFeedbackLoop(
        property_id="profithelm",
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        base_dir=tmp_path,
        dist_dir=tmp_path / "dist",
        preflight_engine=mock_preflight,
    )
    cleared = loop._prune_repaired_urls_from_quarantine_ledger([diag], dry_run=False)
    assert cleared == ["https://profithelm.com/tools/section-1031-calculator/alaska/"]
    assert json.loads(q_path.read_text(encoding="utf-8")) == []


def test_gsc_unknown_url_and_sitemap_data_schema_and_indexnow_hygiene(tmp_path):
    """
    Verifies:
    1. 'URL is unknown to Google' classifies as CRAWL_BUDGET_SIGNAL_LAG for valid routes
       and DEAD_ROUTE_IN_SITEMAP when HTTP 404.
    2. PushIndexer.fetch_gsc_sitemaps parses gsccli 'data' array with string 'errors'/'warnings'
       and supports live=False.
    3. PushIndexer.submit_indexnow_batch strips URL #fragments and rejects >2000-char URLs.
    """
    diag_live = GSCRootCauseClassifier.classify({
        "url": "https://profithelm.com/about/",
        "coverageState": "URL is unknown to Google",
        "verdict": "NEUTRAL",
    })
    assert diag_live.classification == RootCauseClassification.CRAWL_BUDGET_SIGNAL_LAG.value

    diag_dead = GSCRootCauseClassifier.classify({
        "url": "https://profithelm.com/tools/retired-calc/",
        "coverageState": "URL is unknown to Google",
        "status_code": 404,
    })
    assert diag_dead.classification == RootCauseClassification.DEAD_ROUTE_IN_SITEMAP.value

    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.html").write_text(
        '<!DOCTYPE html><html><head><title>Home</title><link rel="canonical" href="https://profithelm.com/"></head><body><h1>Home</h1></body></html>',
        encoding="utf-8",
    )

    indexer = PushIndexer(
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        base_dir=tmp_path,
        dist_dir=dist_dir,
        ledger_path=tmp_path / ".agy" / "index_push_ledger.json",
        tenant_id="profithelm",
    )

    sim_sm = indexer.fetch_gsc_sitemaps(live=False)
    assert sim_sm["status"] == "SIMULATED"

    fake_gsc_json = json.dumps({
        "rowCount": 2,
        "data": [
            {"path": "https://profithelm.com/sitemap.xml", "errors": "0", "warnings": "0"},
            {"path": "https://profithelm.com/sitemap-old.xml", "errors": "2", "warnings": "0"},
        ],
    })
    with patch("shutil.which", return_value="/mock/bin/gsccli"), \
         patch("pathlib.Path.is_file", return_value=True), \
         patch("subprocess.run", return_value=subprocess.CompletedProcess(["gsccli"], 0, stdout=fake_gsc_json)):
        live_sm = indexer.fetch_gsc_sitemaps(live=True, site="sc-domain:profithelm.com")
        assert live_sm["status"] == "OK"
        assert live_sm["row_count"] == 2
        assert live_sm["errors_detected"] == 1

    res_in = indexer.submit_indexnow_batch(
        urls=[
            "https://profithelm.com/#section-anchor",
            "https://profithelm.com/" + ("a" * 2050),
        ],
        dry_run=True,
    )
    assert res_in["urls_submitted"] == 1


def test_domain_health_pacing_and_unindexed_first_submission_governance(tmp_path):
    """
    Verifies PushIndexer.evaluate_domain_health_pacing and submit_gsc_indexing:
    1. Computes real indexation ratio from GSC URL inspection telemetry across domain health tiers
       (CONSERVATIVE_RECOVERY < 70%, GRADUATED_GROWTH 70-90%, HEALTHY_AUTHORITY >= 90%).
    2. Prioritizes unindexed GSC URLs ahead of already-indexed URLs in submit_gsc_indexing.
    3. Throttles outbound GSC batch size according to domain health tier and only rolls over
       unindexed overflow URLs (never dumping already-indexed PASS URLs into gsc_rollover_queue.json).
    """
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    agy_dir = tmp_path / ".agy"
    agy_dir.mkdir(parents=True, exist_ok=True)

    urls = [f"https://gainhelm.com/tools/calc-{i}/" for i in range(15)]
    url_states = {}
    # 6 indexed, 6 unindexed -> 50% indexation ratio -> CONSERVATIVE_RECOVERY (batch cap = 10)
    for i in range(6):
        url_states[urls[i]] = {
            "verdict": "PASS",
            "coverageState": "Submitted and indexed",
            "pageFetchState": "SUCCESSFUL",
        }
    for i in range(6, 12):
        url_states[urls[i]] = {
            "verdict": "NEUTRAL",
            "coverageState": "Discovered - currently not indexed",
            "pageFetchState": "PAGE_FETCH_STATE_UNSPECIFIED",
        }

    (agy_dir / "gsc_lifecycle_telemetry.json").write_text(
        json.dumps({"url_states": url_states}),
        encoding="utf-8",
    )

    indexer = PushIndexer(
        domain="gainhelm.com",
        canonical_base="https://gainhelm.com",
        base_dir=tmp_path,
        dist_dir=dist_dir,
        ledger_path=agy_dir / "index_push_ledger.json",
        rollover_queue_path=agy_dir / "gsc_rollover_queue.json",
        tenant_id="gainhelm",
    )

    health = indexer.evaluate_domain_health_pacing(candidate_urls=urls)
    assert health["domain_health_tier"] == "CONSERVATIVE_RECOVERY"
    assert health["inspected_count"] == 12
    assert health["indexed_count"] == 6
    assert health["unindexed_count"] == 6
    assert health["indexed_ratio"] == 0.5
    assert health["paced_gsc_batch_cap"] == 10
    assert health["sitemap_exposure_cap"] == 50

    with patch("shutil.which", return_value="/mock/bin/gsccli"), \
         patch("subprocess.run", return_value=subprocess.CompletedProcess(["gsccli"], 0, stdout="ACCEPTED")):
        sub_res = indexer.submit_gsc_indexing(urls=urls, live=True, hubs_only=True, drain_rollover=False)
    assert sub_res["urls_submitted"] == 10
    assert sub_res["domain_health_pacing"]["domain_health_tier"] == "CONSERVATIVE_RECOVERY"
    # First 6 submitted must be the 6 unindexed URLs (calc-6 through calc-11)
    submitted_first_6 = sub_res["submitted_urls"][:6]
    assert set(submitted_first_6) == set(urls[6:12])
    # Overflow (5 URLs) contains 1 uninspected URL (calc-14) and 4 already-indexed PASS URLs;
    # only the uninspected/unindexed URL may enter rollover queue (already-indexed PASS URLs are not queued)
    rollover_saved = indexer.load_gsc_rollover_queue()
    for r_u in rollover_saved:
        assert r_u not in set(urls[:6])


def test_exact_gsc_signals_embedded_in_ai_repair_prompt_and_merged_into_locked_overlay(tmp_path):
    """
    Verifies:
    1. GSCRootCauseClassifier.classify synthesizes a clear, unambiguous ai_repair_prompt
       containing exact Search Console exclusion signals (coverage_state, verdict, page_fetch_state,
       user_canonical, google_canonical, last_crawl_time, word_count) and tenant-specific statutory
       citations across profithelm, prexvo, and gainhelm with zero forbidden dashes.
    2. When an existing overlay is locked for a striking-distance query, diagnosing an unindexed
       GSC exclusion on that same route merges ai_repair_prompt and gsc_exclusion_context into the
       locked overlay without resetting created_at, locked_until, or baseline_position.
    """
    from datetime import datetime, timezone, timedelta
    from pseofactory.contracts import assert_no_forbidden_dashes
    from pseofactory.gsc_remediation import (
        compile_remediation_overlay_spec,
        persist_overlay_respecting_lock,
    )

    diag_gainhelm = GSCRootCauseClassifier.classify({
        "url": "https://gainhelm.com/tools/soc-2-audit-cost-calculator/",
        "coverageState": "Discovered - currently not indexed",
        "verdict": "NEUTRAL",
        "pageFetchState": "PAGE_FETCH_STATE_UNSPECIFIED",
        "indexingState": "INDEXING_STATE_UNSPECIFIED",
        "userCanonical": "https://gainhelm.com/tools/soc-2-audit-cost-calculator/",
        "googleCanonical": "",
        "sitemaps": ["https://gainhelm.com/sitemap-hubs.xml"],
    })
    assert diag_gainhelm.classification == RootCauseClassification.CRAWL_BUDGET_SIGNAL_LAG.value
    assert "Discovered - currently not indexed" in diag_gainhelm.ai_repair_prompt
    assert "PAGE_FETCH_STATE_UNSPECIFIED" in diag_gainhelm.ai_repair_prompt
    assert "AICPA SSAE 18" in diag_gainhelm.ai_repair_prompt
    assert "CRAWL_BUDGET_SIGNAL_LAG" in diag_gainhelm.ai_repair_prompt
    assert_no_forbidden_dashes(diag_gainhelm.ai_repair_prompt, "gainhelm ai_repair_prompt")

    diag_prexvo = GSCRootCauseClassifier.classify({
        "url": "https://prexvo.com/tools/tiered-standard-calculator/",
        "coverageState": "Crawled - currently not indexed",
        "verdict": "NEUTRAL",
        "pageFetchState": "SUCCESSFUL",
        "lastCrawlTime": "2026-10-25T10:00:00Z",
        "word_count": 410,
    })
    assert diag_prexvo.classification == RootCauseClassification.CONTENT_QUALITY_OR_ANSWER_DEFICIENCY.value
    assert "Crawled - currently not indexed" in diag_prexvo.ai_repair_prompt
    assert "34 CFR Part 685" in diag_prexvo.ai_repair_prompt
    assert "2026-10-25T10:00:00Z" in diag_prexvo.ai_repair_prompt
    assert_no_forbidden_dashes(diag_prexvo.ai_repair_prompt, "prexvo ai_repair_prompt")

    # Verify locked overlay preserves lock while merging GSC exclusion context and ai_repair_prompt
    ov_file = tmp_path / "soc-2-audit-cost-calculator.json"
    future_lock = (datetime.now(timezone.utc) + timedelta(days=25)).isoformat()
    initial_spec = compile_remediation_overlay_spec(
        {
            "tenant_id": "gainhelm",
            "slug": "soc-2-audit-cost-calculator",
            "target_url": "https://gainhelm.com/tools/soc-2-audit-cost-calculator/",
            "query": "soc 2 audit cost calculator",
            "anomaly_type": "STRIKING_DISTANCE_QUERY",
            "position": 9.4,
            "impressions": 120,
        },
        tenant_id="gainhelm",
    )
    initial_spec["created_at"] = "2026-10-01T00:00:00+00:00"
    initial_spec["locked_until"] = future_lock
    initial_spec["lock_until"] = future_lock
    eff1, written1 = persist_overlay_respecting_lock(ov_file, initial_spec)
    assert written1 is True
    assert "ai_repair_prompt" not in eff1

    exclusion_spec = compile_remediation_overlay_spec(
        {
            "tenant_id": "gainhelm",
            "slug": "soc-2-audit-cost-calculator",
            "target_url": "https://gainhelm.com/tools/soc-2-audit-cost-calculator/",
            "anomaly_type": diag_gainhelm.classification,
            "reason": diag_gainhelm.reason,
            "remediation_action": diag_gainhelm.remediation_action,
            "ai_repair_prompt": diag_gainhelm.ai_repair_prompt,
            "coverage_state": "Discovered - currently not indexed",
            "verdict": "NEUTRAL",
            "page_fetch_state": "PAGE_FETCH_STATE_UNSPECIFIED",
        },
        tenant_id="gainhelm",
    )
    eff2, written2 = persist_overlay_respecting_lock(ov_file, exclusion_spec)
    assert written2 is True
    assert eff2["created_at"] == "2026-10-01T00:00:00+00:00"
    assert eff2["locked_until"] == future_lock
    assert eff2["baseline_position"] == 9.4
    assert eff2["ai_repair_prompt"] == diag_gainhelm.ai_repair_prompt
    assert eff2["gsc_exclusion_context"]["coverage_state"] == "Discovered - currently not indexed"
    assert eff2["gsc_exclusion_context"]["anomaly_type"] == RootCauseClassification.CRAWL_BUDGET_SIGNAL_LAG.value

    # Re-submitting identical exclusion_spec on the next tick is a strict no-op
    eff3, written3 = persist_overlay_respecting_lock(ov_file, exclusion_spec)
    assert written3 is False






