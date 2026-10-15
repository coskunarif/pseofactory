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


