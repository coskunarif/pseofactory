"""
Comprehensive test suite for the Automated Indexing Preflight and Verification Engine.

Tests all 6 pipeline stages, the GSC 59 unindexed URLs corpus fixture (221 URLs),
MasterSEOVerifier check_indexing_gate, PushIndexer preflight integration,
and CLI subcommand execution.
"""

import json
from pathlib import Path
import pytest

from pseofactory.indexing.preflight import (
    IndexingPreflightEngine,
    PreflightStatus,
    TierClassification,
    PreflightURLRecord,
    PreflightReport,
    run_indexing_preflight,
)
from pseofactory.verifier import MasterSEOVerifier
from pseofactory.indexer import PushIndexer
from pseofactory.cli import main as cli_main


def test_stage_1_syntax_and_normalization():
    """Validates Stage 1: trailing slashes, https scheme, and domain checks."""
    engine = IndexingPreflightEngine(domain="profithelm.com")

    # 1. Missing trailing slash on directory route -> BLOCKED_REDIRECT
    rec_slash = engine.inspect_url("https://profithelm.com/tools/margin-calculator")
    assert rec_slash.status == PreflightStatus.BLOCKED_REDIRECT
    assert rec_slash.redirect_target == "https://profithelm.com/tools/margin-calculator/"
    assert any("trailing slash" in issue.lower() for issue in rec_slash.issues)

    # 2. Non-https protocol -> BLOCKED_REDIRECT
    rec_http = engine.inspect_url("http://profithelm.com/tools/margin-calculator/")
    assert rec_http.status == PreflightStatus.BLOCKED_REDIRECT
    assert rec_http.redirect_target == "https://profithelm.com/tools/margin-calculator/"

    # 3. Clean directory route with trailing slash (without dist/fixture)
    # Without HTML or dist, falls back to syntax checks
    rec_clean = engine.inspect_url("https://profithelm.com/tools/margin-calculator/", fixture_record={
        "url": "https://profithelm.com/tools/margin-calculator/",
        "http_status_code": 200,
        "canonical_url": "https://profithelm.com/tools/margin-calculator/",
        "robots_allowed": True,
        "word_count": 300,
        "has_early_answer": True,
    })
    assert rec_clean.status == PreflightStatus.PASS
    assert rec_clean.redirect_target is None


def test_stage_2_http_transport_redirects_and_404s(tmp_path):
    """Validates Stage 2: 3xx redirects, 404s, 5xx server errors, and offline _redirects."""
    engine = IndexingPreflightEngine(domain="profithelm.com")

    # 1. HTTP 301 / 302
    rec_301 = engine.inspect_url("https://profithelm.com/old/", fixture_record={
        "http_status_code": 301,
        "redirect_target": "https://profithelm.com/new/",
    })
    assert rec_301.status == PreflightStatus.BLOCKED_REDIRECT
    assert rec_301.redirect_target == "https://profithelm.com/new/"

    # 2. HTTP 404 Not Found
    rec_404 = engine.inspect_url("https://profithelm.com/deleted/", fixture_record={
        "http_status_code": 404,
    })
    assert rec_404.status == PreflightStatus.BLOCKED_404

    # 3. HTTP 500 Server Error
    rec_500 = engine.inspect_url("https://profithelm.com/crash/", fixture_record={
        "http_status_code": 500,
    })
    assert rec_500.status == PreflightStatus.BLOCKED_SERVER_ERROR

    # 4. Offline dist with _redirects and missing file
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "_redirects").write_text("/legacy-calc /tools/calc/ 301\n", encoding="utf-8")

    engine_dist = IndexingPreflightEngine(domain="profithelm.com", dist_dir=dist_dir)

    # Matched _redirects rule
    rec_rule = engine_dist.inspect_url("https://profithelm.com/legacy-calc/")
    assert rec_rule.status == PreflightStatus.BLOCKED_REDIRECT

    # Missing file -> 404
    rec_missing = engine_dist.inspect_url("https://profithelm.com/tools/missing/")
    assert rec_missing.status == PreflightStatus.BLOCKED_404


def test_stage_3_canonical_consistency():
    """Validates Stage 3: self-referential canonical tags and edge Link header divergence."""
    engine = IndexingPreflightEngine(domain="profithelm.com")

    # 1. Self-referential matching canonical -> PASS
    rec_pass = engine.inspect_url("https://profithelm.com/tools/calc/", fixture_record={
        "canonical_url": "https://profithelm.com/tools/calc/",
        "canonical_header": "https://profithelm.com/tools/calc/",
        "http_status_code": 200,
        "robots_allowed": True,
        "word_count": 300,
        "has_early_answer": True,
    })
    assert rec_pass.status == PreflightStatus.PASS
    assert rec_pass.canonical_match is True

    # 2. Canonical pointing to parent category
    rec_parent = engine.inspect_url("https://profithelm.com/tools/calc/", fixture_record={
        "canonical_url": "https://profithelm.com/tools/",
        "http_status_code": 200,
        "robots_allowed": True,
        "word_count": 300,
        "has_early_answer": True,
    })
    assert rec_parent.status == PreflightStatus.BLOCKED_CANONICAL_MISMATCH
    assert rec_parent.canonical_match is False

    # 3. Non-https canonical URL
    rec_non_https = engine.inspect_url("https://profithelm.com/tools/calc/", fixture_record={
        "canonical_url": "http://profithelm.com/tools/calc/",
        "http_status_code": 200,
        "robots_allowed": True,
        "word_count": 300,
        "has_early_answer": True,
    })
    assert rec_non_https.status == PreflightStatus.BLOCKED_CANONICAL_MISMATCH

    # 4. Edge HTTP Link header divergence
    rec_diverge = engine.inspect_url("https://profithelm.com/tools/calc/", fixture_record={
        "canonical_url": "https://profithelm.com/tools/calc/",
        "canonical_header": "https://profithelm.com/tools/other/",
        "http_status_code": 200,
        "robots_allowed": True,
        "word_count": 300,
        "has_early_answer": True,
    })
    assert rec_diverge.status == PreflightStatus.BLOCKED_CANONICAL_MISMATCH


def test_stage_4_robots_and_meta_noindex(tmp_path):
    """Validates Stage 4: robots.txt rules, meta robots noindex, and X-Robots-Tag."""
    engine = IndexingPreflightEngine(domain="profithelm.com")

    # 1. robots_allowed = False
    rec_disallow = engine.inspect_url("https://profithelm.com/admin/", fixture_record={
        "robots_allowed": False,
        "canonical_url": "https://profithelm.com/admin/",
        "word_count": 300,
        "has_early_answer": True,
    })
    assert rec_disallow.status == PreflightStatus.BLOCKED_NOINDEX

    # 2. HTML meta robots noindex
    html_noindex = (
        '<!DOCTYPE html><html><head><meta name="robots" content="noindex, nofollow" />'
        '<link rel="canonical" href="https://profithelm.com/tools/test/" /></head>'
        '<body><h1>Test</h1><div class="quick-answer">Answer</div>'
        + ' word' * 200 + '</body></html>'
    )
    rec_meta = engine.inspect_url("https://profithelm.com/tools/test/", html_content=html_noindex)
    assert rec_meta.status == PreflightStatus.BLOCKED_NOINDEX

    # 3. Edge _headers with X-Robots-Tag: noindex
    dist_dir = tmp_path / "dist_robots"
    dist_dir.mkdir(parents=True)
    (dist_dir / "_headers").write_text("/private/*\n  X-Robots-Tag: noindex\n", encoding="utf-8")
    engine_headers = IndexingPreflightEngine(domain="profithelm.com", dist_dir=dist_dir)

    html_clean = (
        '<!DOCTYPE html><html><head><link rel="canonical" href="https://profithelm.com/private/page/" /></head>'
        '<body><h1>Test</h1><div class="quick-answer">Answer</div>'
        + ' word' * 200 + '</body></html>'
    )
    rec_edge = engine_headers.inspect_url("https://profithelm.com/private/page/", html_content=html_clean)
    assert rec_edge.status == PreflightStatus.BLOCKED_NOINDEX


def test_stage_5_content_quality_and_thin_gate():
    """Validates Stage 5: word count >= 150, exactly one H1, and early direct answer presence."""
    engine = IndexingPreflightEngine(domain="profithelm.com", min_words=150)

    # 1. Thin content (<150 words)
    html_thin = (
        '<!DOCTYPE html><html><head><link rel="canonical" href="https://profithelm.com/tools/thin/" /></head>'
        '<body><h1>Title</h1><div class="quick-answer">Answer</div>'
        '<p>Only a few words on this page.</p></body></html>'
    )
    rec_thin = engine.inspect_url("https://profithelm.com/tools/thin/", html_content=html_thin)
    assert rec_thin.status == PreflightStatus.BLOCKED_THIN_CONTENT
    assert rec_thin.word_count < 150

    # 2. Missing early direct answer block (.quick-answer or .answer-box)
    html_no_answer = (
        '<!DOCTYPE html><html><head><link rel="canonical" href="https://profithelm.com/tools/no-ans/" /></head>'
        '<body><h1>Title</h1>'
        + '<p>Words without answer block.</p>' * 30 + '</body></html>'
    )
    rec_no_ans = engine.inspect_url("https://profithelm.com/tools/no-ans/", html_content=html_no_answer)
    assert rec_no_ans.status == PreflightStatus.BLOCKED_THIN_CONTENT
    assert rec_no_ans.has_early_answer is False

    # 3. Missing H1 tag
    html_no_h1 = (
        '<!DOCTYPE html><html><head><link rel="canonical" href="https://profithelm.com/tools/no-h1/" /></head>'
        '<body><div class="quick-answer">Answer</div>'
        + '<p>Content here.</p>' * 30 + '</body></html>'
    )
    rec_no_h1 = engine.inspect_url("https://profithelm.com/tools/no-h1/", html_content=html_no_h1)
    assert rec_no_h1.status == PreflightStatus.BLOCKED_THIN_CONTENT

    # 4. Fully compliant page -> PASS
    html_good = (
        '<!DOCTYPE html><html><head><link rel="canonical" href="https://profithelm.com/tools/good/" /></head>'
        '<body><h1>Valid Page Heading</h1><aside class="quick-answer">Direct definition answer block</aside>'
        + '<p>Thorough technical explanations and data table content.</p>' * 25 + '</body></html>'
    )
    rec_good = engine.inspect_url("https://profithelm.com/tools/good/", html_content=html_good)
    assert rec_good.status == PreflightStatus.PASS
    assert rec_good.has_early_answer is True
    assert rec_good.word_count >= 150


def test_stage_6_tier_partitioning_and_150_cap():
    """Validates Stage 6: path depth tiering and HWL-1076 150 hub cap."""
    engine = IndexingPreflightEngine(domain="profithelm.com", tier1_cap=150)

    # Depth 0, 1, 2 -> TIER_1_HUB
    assert engine._calculate_tier("https://profithelm.com/") == TierClassification.TIER_1_HUB
    assert engine._calculate_tier("https://profithelm.com/tools/") == TierClassification.TIER_1_HUB
    assert engine._calculate_tier("https://profithelm.com/tools/margin-calculator/") == TierClassification.TIER_1_HUB

    # Depth 3, 4 -> TIER_2_LEAF
    assert engine._calculate_tier("https://profithelm.com/tools/calculators/margin/") == TierClassification.TIER_2_LEAF
    assert engine._calculate_tier("https://profithelm.com/tools/saas/metrics/cac/") == TierClassification.TIER_2_LEAF

    # Partitioning 200 hubs: push_eligible_urls capped at 150
    hubs = [f"https://profithelm.com/tools/hub-{i:03d}/" for i in range(1, 201)]
    records = [
        PreflightURLRecord(
            url=u,
            status=PreflightStatus.PASS,
            tier=TierClassification.TIER_1_HUB,
            canonical_match=True,
            robots_allowed=True,
            word_count=300,
            has_early_answer=True,
        )
        for u in hubs
    ]
    push_urls, sitemap_urls, blocked_urls = engine.partition_urls(records)
    assert len(push_urls) == 150
    assert len(sitemap_urls) == 200
    assert len(blocked_urls) == 0


def test_59_unindexed_urls_corpus_fixture():
    """
    Evaluates the complete 221 URL fixture:
    Asserts exactly 162 PASS and 59 BLOCKED with exact breakdown match.
    """
    fixture_path = Path("pseofactory/fixtures/gsc_unindexed_59_urls_fixture.json")
    assert fixture_path.is_file(), "Fixture file must exist"

    report = run_indexing_preflight(fixture_path=fixture_path)

    # Exact summary counts
    assert report.total_inspected == 221
    assert report.passed_count == 162
    assert report.blocked_count == 59
    assert report.tier1_hubs_eligible == 44
    assert report.tier2_leaves_queued == 118
    assert report.is_gate_passed is False

    # Exact breakdown verification
    expected_breakdown = {
        "PASS": 162,
        "BLOCKED_REDIRECT": 14,
        "BLOCKED_404": 12,
        "BLOCKED_CANONICAL_MISMATCH": 15,
        "BLOCKED_SERVER_ERROR": 3,
        "BLOCKED_THIN_CONTENT": 15,
    }
    assert report.breakdown == expected_breakdown

    # Partitioned URLs
    assert len(report.push_eligible_urls) == 44
    assert len(report.sitemap_eligible_urls) == 162
    assert len(report.blocked_urls) == 59


def test_verifier_check_indexing_gate(tmp_path):
    """Validates MasterSEOVerifier check_indexing_gate and audit_seo_checklist."""
    # 1. Dist dir with clean asset
    dist_clean = tmp_path / "dist_clean"
    dist_clean.mkdir(parents=True)
    tool_dir = dist_clean / "tools" / "calculator"
    tool_dir.mkdir(parents=True)

    html_content = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>Free Profit Margin Calculator 2026</title>'
        '<meta name="description" content="Calculate gross margin, net margin, and profit markups." />'
        '<link rel="canonical" href="https://profithelm.com/tools/calculator/" />'
        '</head><body>'
        '<h1>Profit Margin Calculator</h1>'
        '<aside class="quick-answer">Gross profit margin is calculated as (Revenue - COGS) / Revenue.</aside>'
        + '<p>Additional comprehensive calculation guidance details here.</p>' * 25 +
        '</body></html>'
    )
    (tool_dir / "index.html").write_text(html_content, encoding="utf-8")

    verifier = MasterSEOVerifier(dist_dir=dist_clean, domain="profithelm.com")
    gate_res = verifier.check_indexing_gate(dist_clean)

    assert gate_res["gate"] == "Instant Indexing Gate"
    assert gate_res["passed"] is True
    assert gate_res["status"] == "PASS"
    assert gate_res["total"] == 1
    assert gate_res["clean_urls"] == 1
    assert gate_res["blocked"] == 0

    # 2. Dist dir with broken asset (missing trailing slash in canonical or thin content)
    dist_bad = tmp_path / "dist_bad"
    dist_bad.mkdir(parents=True)
    bad_tool = dist_bad / "tools" / "broken"
    bad_tool.mkdir(parents=True)
    bad_html = (
        '<!DOCTYPE html><html><head><link rel="canonical" href="https://profithelm.com/tools/wrong-parent/" /></head>'
        '<body><h1>Broken</h1><p>Thin.</p></body></html>'
    )
    (bad_tool / "index.html").write_text(bad_html, encoding="utf-8")

    gate_bad = verifier.check_indexing_gate(dist_bad)
    assert gate_bad["passed"] is False
    assert gate_bad["status"] == "FAIL"
    assert gate_bad["blocked"] >= 1
    assert len(gate_bad["issues"]) >= 1

    # 3. Check audit_seo_checklist includes check_indexing_gate
    checklist = verifier.audit_seo_checklist(dist_clean, enforce_relevance=False)
    assert "check_indexing_gate" in checklist["gates"]
    assert "indexing_gate" in checklist["gates"]


def test_push_indexer_preflight_integration(tmp_path):
    """Validates that PushIndexer filters out blocked URLs and writes preflight logs."""
    ledger_path = tmp_path / "ledger.json"
    audit_log_path = tmp_path / "audit.json"
    base_dir = tmp_path / "base"
    base_dir.mkdir(parents=True)

    indexer = PushIndexer(
        domain="profithelm.com",
        base_dir=base_dir,
        ledger_path=ledger_path,
        audit_log_path=audit_log_path,
    )

    candidate_urls = [
        "https://profithelm.com/tools/margin-calculator/",  # Clean Hub (depth 2) -> Push
        "https://profithelm.com/tools/broken-redirect",     # Missing slash -> Blocked
        "https://profithelm.com/tools/calculators/margin/",  # Clean Leaf (depth 3) -> Not Push
    ]

    res = indexer.dispatch_automated_indexing(urls=candidate_urls, force=True, live=False)

    assert res["status"] == "SUCCESS"
    assert "preflight" in res
    assert res["preflight"] is not None
    # Only clean Tier-1 hub submitted to push
    assert "https://profithelm.com/tools/margin-calculator/" in res["assets_submitted"]
    # Broken redirect is excluded from push
    assert "https://profithelm.com/tools/broken-redirect" not in res["assets_submitted"]
    assert "https://profithelm.com/tools/broken-redirect" in res["blocked_urls"]

    # Blocked log file written to .agy/indexing_preflight_blocked.json
    blocked_log_file = base_dir / ".agy" / "indexing_preflight_blocked.json"
    assert blocked_log_file.is_file()
    blocked_data = json.loads(blocked_log_file.read_text(encoding="utf-8"))
    assert blocked_data["blocked_count"] == 1
    assert "https://profithelm.com/tools/broken-redirect" in blocked_data["blocked_urls"]


def test_cli_indexing_preflight_execution():
    """Validates CLI subcommand indexing-preflight with strict, dry-run, and json options."""
    fixture = "pseofactory/fixtures/gsc_unindexed_59_urls_fixture.json"

    # 1. Strict mode on fixture with 59 blocked URLs must exit 1
    rc_strict = cli_main(["indexing-preflight", "--fixture", fixture, "--strict"])
    assert rc_strict == 1

    # 2. Dry-run mode on fixture must exit 0
    rc_dry = cli_main(["indexing-preflight", "--fixture", fixture, "--dry-run"])
    assert rc_dry == 0

    # 3. Clean single URL must exit 0 even with --strict
    rc_clean = cli_main([
        "indexing-preflight",
        "--urls", "https://profithelm.com/tools/margin-calculator/",
        "--strict",
        "--json",
    ])
    assert rc_clean == 0

    # 4. Bad configuration without targets must exit 2
    rc_bad = cli_main(["indexing-preflight", "--property", "nonexistent_tenant"])
    assert rc_bad == 2
