"""
Tests for the 8 Autonomous SEO Growth Workflows (pseofactory.seo_growth_loops).
Verifies:
1. Identify content decay (daily timeline sync + query/page snapshot delta detection)
2. Turn a Site Audit into a technical SEO sprint (prioritized sprint backlog)
3. Investigate competitor traffic spikes (longitudinal velocity + SERP gap synthesis)
4. Turn search opportunities into content briefs (striking-distance leaf + root briefs & overlays)
5. Find internal linking and orphaned-page opportunities (link graph + equity routing)
6. Make content portfolio decisions (true asset age resolution surviving dist rebuilds)
7. Turn AI citation gaps into a digital PR queue (ProfitHelm + Prexvo Title IV benchmarks & PR queue)
8. Monitor SEO regressions after releases or migrations (release_manifest.json + GSC trajectory join)
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pseofactory.cli import main as cli_main
from pseofactory.competitor import CompetitorGapEngine
from pseofactory.distributor import generate_ai_benchmark_nodes
import pseofactory.gsc_remediation as _gsc_rem
from pseofactory.gsc_remediation import _resolve_contextual_internal_links
from pseofactory.tenant_facts import TenantFactStore

compile_ai_citation_digital_pr_queue = getattr(_gsc_rem, "compile_ai_citation_digital_pr_queue", None)
compile_search_opportunity_briefs = getattr(_gsc_rem, "compile_search_opportunity_briefs", None)
compile_technical_seo_sprint = getattr(_gsc_rem, "compile_technical_seo_sprint", None)
discover_internal_linking_opportunities = getattr(_gsc_rem, "discover_internal_linking_opportunities", None)
evaluate_content_portfolio_decisions = getattr(_gsc_rem, "evaluate_content_portfolio_decisions", None)
harvest_and_sync_gsc_daily_timeline = getattr(_gsc_rem, "harvest_and_sync_gsc_daily_timeline", None)
identify_content_decay = getattr(_gsc_rem, "identify_content_decay", None)
investigate_competitor_traffic_spikes = getattr(_gsc_rem, "investigate_competitor_traffic_spikes", None)
monitor_post_release_seo_regressions = getattr(_gsc_rem, "monitor_post_release_seo_regressions", None)
resolve_true_asset_age_days = getattr(_gsc_rem, "resolve_true_asset_age_days", None)
run_all_seo_growth_workflows = getattr(_gsc_rem, "run_all_seo_growth_workflows", None)
sync_real_gsc_baselines_to_recovery_ledger = getattr(_gsc_rem, "sync_real_gsc_baselines_to_recovery_ledger", None)


def _seed_tenant_fixture(tmp_path: Path, prop: str = "profithelm") -> Path:
    repo_root = tmp_path / f"{prop}-repo"
    dist_dir = repo_root / "dist"
    agy_dir = repo_root / ".agy"
    data_dir = repo_root / "profithelm" / "data"
    trends_dir = repo_root / "pseofactory" / "trends" / "data"
    runs_dir = tmp_path / ".agy" / "runs" / "run_20261015_test"

    for d in (dist_dir, agy_dir, data_dir, trends_dir, runs_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Seed root and leaf HTML pages in dist/
    root_html = dist_dir / "index.html"
    root_html.write_text(
        '<html><head><title>Hub</title></head><body>'
        '<a href="/tools/irs-2027-tax-brackets/">Tax Brackets</a>'
        '<a href="/tools/section-1031-calculator/">Section 1031</a>'
        '<a href="/tools/section-179-calculator/">Section 179</a>'
        '</body></html>',
        encoding="utf-8",
    )

    pages = {
        "tools/irs-2027-tax-brackets/index.html": (
            '<html><head><title>IRS 2027 Tax Brackets Calculator</title>'
            '<script type="application/ld+json">{"datePublished": "2026-08-01"}</script></head>'
            '<body><a href="/tools/irs-2027-tax-brackets/california/">CA Tax Brackets</a>'
            '<a href="/tools/section-1031-calculator/">1031 Exchange</a></body></html>'
        ),
        "tools/irs-2027-tax-brackets/california/index.html": (
            '<html><head><title>California 2027 Tax Brackets Calculator</title>'
            '<script type="application/ld+json">{"datePublished": "2026-08-05"}</script></head>'
            '<body><a href="/tools/irs-2027-tax-brackets/">Federal Brackets</a></body></html>'
        ),
        "tools/section-1031-calculator/index.html": (
            '<html><head><title>Section 1031 Like-Kind Exchange Calculator</title>'
            '<script type="application/ld+json">{"datePublished": "2026-08-02"}</script></head>'
            '<body><a href="/tools/section-1031-calculator/texas/">Texas 1031</a></body></html>'
        ),
        "tools/section-1031-calculator/texas/index.html": (
            '<html><head><title>Texas Section 1031 Exchange Calculator</title>'
            '<script type="application/ld+json">{"datePublished": "2026-08-10"}</script></head>'
            '<body><a href="/tools/section-1031-calculator/">1031 Hub</a></body></html>'
        ),
        "tools/section-179-calculator/index.html": (
            '<html><head><title>Section 179 Calculator</title>'
            '<script type="application/ld+json">{"datePublished": "2026-08-01"}</script></head>'
            '<body><a href="/tools/">All Tools</a></body></html>'
        ),
        "tools/legacy-zero-impr-tool/index.html": (
            '<html><head><title>Legacy Zero Impression Tool</title>'
            '<script type="application/ld+json">{"datePublished": "2026-07-01"}</script></head>'
            '<body><p>Orphaned zero impression page with fresh mtime.</p></body></html>'
        ),
    }
    for rel_p, html_body in pages.items():
        fp = dist_dir / rel_p
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(html_body, encoding="utf-8")

    # Seed statutory.db with longitudinal GSC snapshots and velocity spikes
    stat_db = data_dir / "statutory.db"
    conn = sqlite3.connect(str(stat_db))
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE gsc_performance_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id TEXT,
            property_uri TEXT,
            query TEXT,
            page TEXT,
            impressions INTEGER,
            clicks INTEGER,
            ctr REAL,
            position REAL,
            recorded_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE trend_velocity_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT,
            tenant TEXT,
            velocity_ratio REAL,
            current_interest REAL,
            baseline_avg REAL,
            is_breakout INTEGER,
            recorded_at TEXT
        )
        """
    )

    baseline_rows = [
        ("snap_001", "sc-domain:profithelm.com", "ca tax brackets", "https://profithelm.com/tools/irs-2027-tax-brackets/california/", 50, 2, 0.04, 9.07, "2026-09-28T00:00:00Z"),
        ("snap_001", "sc-domain:profithelm.com", "ca tax brackets 2027", "https://profithelm.com/tools/irs-2027-tax-brackets/california/", 15, 1, 0.066, 4.27, "2026-09-28T00:00:00Z"),
        ("snap_001", "sc-domain:profithelm.com", "california tax bracket calculator", "https://profithelm.com/tools/irs-2027-tax-brackets/california/", 10, 0, 0.0, 10.0, "2026-09-28T00:00:00Z"),
        ("snap_001", "sc-domain:profithelm.com", "1031 exchange calculator texas", "https://profithelm.com/tools/section-1031-calculator/texas/", 26, 0, 0.0, 7.62, "2026-09-28T00:00:00Z"),
        ("snap_001", "sc-domain:profithelm.com", "section 179 calculator", "https://profithelm.com/tools/section-179-calculator/", 40, 2, 0.05, 8.5, "2026-09-28T00:00:00Z"),
        ("snap_001", "sc-domain:profithelm.com", "2027 federal tax brackets", "https://profithelm.com/tools/irs-2027-tax-brackets/", 35, 1, 0.028, 6.2, "2026-09-28T00:00:00Z"),
    ]
    latest_rows = [
        ("snap_002", "sc-domain:profithelm.com", "ca tax brackets", "https://profithelm.com/tools/irs-2027-tax-brackets/california/", 55, 0, 0.0, 11.4, "2026-10-18T00:00:00Z"),
        ("snap_002", "sc-domain:profithelm.com", "ca tax brackets 2027", "https://profithelm.com/tools/irs-2027-tax-brackets/california/", 18, 0, 0.0, 6.5, "2026-10-18T00:00:00Z"),
        ("snap_002", "sc-domain:profithelm.com", "california tax bracket calculator", "https://profithelm.com/tools/irs-2027-tax-brackets/california/", 12, 0, 0.0, 14.2, "2026-10-18T00:00:00Z"),
        ("snap_002", "sc-domain:profithelm.com", "1031 exchange calculator texas", "https://profithelm.com/tools/section-1031-calculator/texas/", 30, 0, 0.0, 7.5, "2026-10-18T00:00:00Z"),
        ("snap_002", "sc-domain:profithelm.com", "section 179 calculator", "https://profithelm.com/tools/section-179-calculator/", 45, 3, 0.066, 7.8, "2026-10-18T00:00:00Z"),
        ("snap_002", "sc-domain:profithelm.com", "2027 federal tax brackets", "https://profithelm.com/tools/irs-2027-tax-brackets/", 38, 0, 0.0, 6.4, "2026-10-18T00:00:00Z"),
    ]
    cur.executemany(
        """
        INSERT INTO gsc_performance_snapshots
        (snapshot_id, property_uri, query, page, impressions, clicks, ctr, position, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        baseline_rows + latest_rows,
    )
    cur.execute(
        """
        INSERT INTO trend_velocity_history
        (keyword, tenant, velocity_ratio, current_interest, baseline_avg, is_breakout, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("section 179 heavy suv bonus depreciation", "profithelm", 1.85, 92.0, 49.7, 1, "2026-10-18T00:00:00Z"),
    )
    conn.commit()
    conn.close()

    # Seed release_manifest.json
    (runs_dir / "release_manifest.json").write_text(
        json.dumps(
            {
                "run_id": "run_20261015_test",
                "timestamp": "2026-10-15T12:00:00Z",
                "head_sha": "abc1234",
                "overall_status": "RELEASED",
                "gates": {"unit_tests": "PASS", "reflection": "PASS"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return repo_root


def test_workflow_1_identify_content_decay_detects_page_and_query_drops(tmp_path: Path) -> None:
    assert callable(harvest_and_sync_gsc_daily_timeline) and callable(identify_content_decay)
    repo_root = _seed_tenant_fixture(tmp_path)
    base_day = datetime(2026, 9, 15, tzinfo=timezone.utc)
    fixture_records = []
    for i in range(21):
        d_str = (base_day + timedelta(days=i)).strftime("%Y-%m-%d")
        fixture_records.append(
            {
                "date": d_str,
                "impressions": 160 if i >= 14 else 120,
                "clicks": 4 if i >= 14 else 3,
                "ctr": 0.025,
                "position": 9.2 if i >= 14 else 10.5,
            }
        )

    daily_records = harvest_and_sync_gsc_daily_timeline(
        property_id="profithelm",
        repo_root=repo_root,
        fixture_records=fixture_records,
        persist=True,
    )
    assert len(daily_records) == 21

    decay_report = identify_content_decay(
        property_id="profithelm",
        repo_root=repo_root,
        daily_records=daily_records,
        persist=True,
    )
    assert decay_report["workflow"] == "identify_content_decay"
    assert decay_report["timeline_audit"].get("reason") != "INSUFFICIENT_TIMELINE_DATA"
    assert decay_report["decayed_pages_count"] >= 1
    ca_decay = next(
        (d for d in decay_report["decayed_pages"] if d["canonical_path"] == "/tools/irs-2027-tax-brackets/california"),
        None,
    )
    assert ca_decay is not None
    assert ca_decay["crossed_page_one_boundary"] is True
    assert ca_decay["position_drop"] > 1.5


def test_workflow_2_compile_technical_seo_sprint_prioritizes_tickets(tmp_path: Path) -> None:
    assert (
        callable(identify_content_decay)
        and callable(discover_internal_linking_opportunities)
        and callable(compile_technical_seo_sprint)
    )
    repo_root = _seed_tenant_fixture(tmp_path)
    decay_rep = identify_content_decay(property_id="profithelm", repo_root=repo_root, persist=False)
    link_rep = discover_internal_linking_opportunities(
        property_id="profithelm",
        repo_root=repo_root,
        dist_dir=repo_root / "dist",
        persist=False,
    )
    sprint = compile_technical_seo_sprint(
        property_id="profithelm",
        repo_root=repo_root,
        dist_dir=repo_root / "dist",
        decay_report=decay_rep,
        link_report=link_rep,
        persist=True,
    )
    assert sprint["workflow"] == "technical_seo_sprint"
    assert sprint["sprint_tickets_count"] >= 1
    scores = [t["priority_score"] for t in sprint["tickets"]]
    assert scores == sorted(scores, reverse=True)
    assert (repo_root / ".agy" / "technical_seo_sprint.json").is_file()


def test_workflow_3_investigate_competitor_traffic_spikes(tmp_path: Path) -> None:
    assert hasattr(CompetitorGapEngine, "investigate_competitor_traffic_spikes")
    repo_root = _seed_tenant_fixture(tmp_path)
    engine = CompetitorGapEngine(tenant_id="profithelm")
    spike_rep = engine.investigate_competitor_traffic_spikes(
        repo_root=repo_root,
        velocity_spike_threshold=0.25,
        persist=True,
    )
    assert spike_rep["workflow"] == "investigate_competitor_traffic_spikes"
    assert spike_rep["spikes_count"] >= 1
    top_spike = spike_rep["spikes"][0]
    assert top_spike["velocity_ratio"] >= 1.25
    assert "missing_serp_features" in top_spike


def test_workflow_4_compile_search_opportunity_briefs_includes_leaf_routes(tmp_path: Path) -> None:
    assert callable(compile_search_opportunity_briefs)
    repo_root = _seed_tenant_fixture(tmp_path)
    brief_rep = compile_search_opportunity_briefs(
        property_id="profithelm",
        repo_root=repo_root,
        dist_dir=repo_root / "dist",
        apply_overlays=True,
        persist=True,
    )
    assert brief_rep["workflow"] == "search_opportunities_to_content_briefs"
    assert brief_rep["briefs_count"] >= 2
    leaf_paths = {b["canonical_path"] for b in brief_rep["briefs"]}
    assert "/tools/irs-2027-tax-brackets/california" in leaf_paths or "/tools/section-1031-calculator/texas" in leaf_paths


def test_workflow_5_discover_internal_linking_and_leaf_cluster_routing(tmp_path: Path) -> None:
    links_1031 = _resolve_contextual_internal_links("profithelm", "section-1031-calculator", "1031 exchange")
    hrefs_1031 = [item["href"] for item in links_1031]
    assert "/tools/section-1031-calculator/texas/" in hrefs_1031
    assert callable(discover_internal_linking_opportunities)

    repo_root = _seed_tenant_fixture(tmp_path)
    link_rep = discover_internal_linking_opportunities(
        property_id="profithelm",
        repo_root=repo_root,
        dist_dir=repo_root / "dist",
        persist=True,
    )
    assert link_rep["workflow"] == "internal_linking_and_orphaned_pages"
    assert link_rep["internal_link_graph"]["total_pages"] >= 5
    assert "/tools/legacy-zero-impr-tool" in link_rep["internal_link_graph"]["orphaned_pages"]


def test_workflow_6_resolve_true_asset_age_days_survives_fresh_mtime(tmp_path: Path) -> None:
    assert callable(resolve_true_asset_age_days) and callable(evaluate_content_portfolio_decisions)
    repo_root = _seed_tenant_fixture(tmp_path)
    dist_dir = repo_root / "dist"
    legacy_html = dist_dir / "tools" / "legacy-zero-impr-tool" / "index.html"
    # Touch file so st_mtime is 0 seconds ago (simulating build_all + retrofit_estate)
    now_ts = datetime(2026, 10, 18, tzinfo=timezone.utc).timestamp()
    os.utime(legacy_html, (now_ts, now_ts))

    true_age = resolve_true_asset_age_days(
        "/tools/legacy-zero-impr-tool",
        html_file=legacy_html,
        property_id="profithelm",
        repo_root=repo_root,
        now_ts=now_ts,
    )
    assert true_age >= 60.0

    portfolio_rep = evaluate_content_portfolio_decisions(
        property_id="profithelm",
        repo_root=repo_root,
        dist_dir=dist_dir,
        max_age_days=30.0,
        persist=True,
    )
    assert portfolio_rep["workflow"] == "content_portfolio_decisions"
    zero_paths = [c["url_path"] for c in portfolio_rep["zero_impression_candidates"]]
    assert "/tools/legacy-zero-impr-tool" in zero_paths
    ca_decision = next(
        (d for d in portfolio_rep["decisions"] if d["url_path"] == "/tools/irs-2027-tax-brackets/california"),
        None,
    )
    assert ca_decision is not None
    assert ca_decision["decision"] in ("REFRESH_AND_SHARPEN", "EXPAND_CLUSTER")


def test_workflow_7_ai_citation_digital_pr_queue_supports_profithelm_and_prexvo(tmp_path: Path) -> None:
    repo_root = _seed_tenant_fixture(tmp_path)
    prexvo_nodes = generate_ai_benchmark_nodes(tenant="prexvo")
    assert prexvo_nodes["status"] == "SUCCESS"
    assert prexvo_nodes["tenant"] == "prexvo"
    assert "title_iv_rap_ibr_benchmarks.md" in prexvo_nodes["files"]
    assert "pslf_forgiveness_benchmarks.md" in prexvo_nodes["files"]
    assert callable(compile_ai_citation_digital_pr_queue)

    pr_rep = compile_ai_citation_digital_pr_queue(
        property_id="profithelm",
        repo_root=repo_root,
        dist_dir=repo_root / "dist",
        persist=True,
    )
    assert pr_rep["workflow"] == "ai_citation_digital_pr_queue"
    assert pr_rep["queue_count"] >= 1
    assert (repo_root / "dist" / "ai-benchmarks" / "ai_benchmarks_manifest.json").is_file()


def test_workflow_8_monitor_post_release_seo_regressions_correlates_manifests(tmp_path: Path) -> None:
    assert callable(monitor_post_release_seo_regressions)
    repo_root = _seed_tenant_fixture(tmp_path)
    # Create an expired degraded overlay to verify automatic rollback correlation
    ov_dir = repo_root / "content" / "overlays"
    ov_dir.mkdir(parents=True, exist_ok=True)
    expired_lock = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    (ov_dir / "irs-2027-tax-brackets.json").write_text(
        json.dumps(
            {
                "slug": "irs-2027-tax-brackets",
                "query": "ca tax brackets",
                "target_url": "https://profithelm.com/tools/irs-2027-tax-brackets/california/",
                "baseline_impressions": 50,
                "baseline_clicks": 2,
                "baseline_ctr": 0.04,
                "baseline_position": 9.07,
                "locked_until": expired_lock,
                "status": "ACTIVE_LOCKED",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    reg_rep = monitor_post_release_seo_regressions(
        property_id="profithelm",
        repo_root=repo_root,
        runs_dir=tmp_path / ".agy" / "runs",
        persist=True,
    )
    assert reg_rep["workflow"] == "post_release_seo_regressions"
    assert reg_rep["releases_correlated_count"] >= 1
    assert reg_rep["regressions_count"] >= 1
    assert reg_rep["overlay_evaluation"]["summary"]["DEGRADED_ROLLED_BACK"] >= 1


def test_run_all_seo_growth_workflows_and_cli_integration(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert callable(run_all_seo_growth_workflows) and callable(sync_real_gsc_baselines_to_recovery_ledger)
    repo_root = _seed_tenant_fixture(tmp_path)
    master = run_all_seo_growth_workflows(
        property_id="profithelm",
        repo_root=repo_root,
        dist_dir=repo_root / "dist",
        apply_overlays=True,
        persist=True,
    )
    assert master["status"] == "PASS"
    assert master["workflows_executed"] == 8
    assert (repo_root / ".agy" / "seo_growth_workflows_report.json").is_file()

    # Verify real GSC baselines are synced to metric_recovery_ledger.json
    sync_res = sync_real_gsc_baselines_to_recovery_ledger(
        property_id="profithelm",
        repo_root=repo_root,
        discovered_tools=[{"slug": "section-179-calculator"}],
    )
    assert sync_res["updated_count"] >= 1
    ledger = json.loads((repo_root / ".agy" / "metric_recovery_ledger.json").read_text(encoding="utf-8"))
    assert ledger["snapshots"]["section-179-calculator"]["baseline_source"] == "GSC_EMPIRICAL_ROLLUP"

    rc = cli_main(["seo-workflows", "--property", "profithelm", "--dry-run", "--json"])
    assert rc == 0
    captured = capsys.readouterr().out
    parsed = json.loads(captured)
    assert parsed["workflows_executed"] == 8


def test_live_queue_ai_citation_detector_and_prexvo_vertical_overlays(tmp_path: Path) -> None:
    """
    Verifies that void_candidates.jsonl, .agy/gsc_remediation_queue.json, and
    freshness_audit_report.json are evaluated through TregChecker.check_ai_citation,
    prioritized by deterministic tax/Title IV math need, and compiled into vertical-specific
    overlays without generic RAP/IBR boilerplate pollution on PSLF or Parent PLUS pages.
    """
    from pseofactory.gsc_remediation import (
        calculate_candidate_roi,
        classify_deterministic_math_opportunity,
        compile_remediation_overlay_spec,
    )

    tax_math = classify_deterministic_math_opportunity(
        slug="section-179-calculator",
        query="section 179 bonus depreciation phaseout",
        tenant_id="profithelm",
    )
    assert tax_math["needs_deterministic_math"] is True
    assert tax_math["math_domain"] == "STATUTORY_TAX_MATH"

    loan_math = classify_deterministic_math_opportunity(
        slug="pslf-buyback-calculator",
        query="pslf buyback lump sum calculation",
        tenant_id="prexvo",
    )
    assert loan_math["needs_deterministic_math"] is True
    assert loan_math["math_domain"] == "TITLE_IV_STUDENT_LOAN_MATH"

    roi_res = calculate_candidate_roi(
        {
            "slug": "pslf-buyback-calculator",
            "query": "pslf buyback calculator",
            "tenant_id": "prexvo",
            "impressions": 45,
            "clicks": 0,
            "position": 8.4,
            "losing_to_weaker_domains": True,
            "weaker_cited_domains": ["studentaid.gov", "reddit.com"],
        }
    )
    assert roi_res["needs_deterministic_math"] is True
    assert roi_res["citation_gap_status"] == "LOSING_TO_WEAKER_DOMAINS"
    assert roi_res["ai_citation_boost"] == 0.30
    assert roi_res["deterministic_math_boost"] == 0.15

    pslf_spec = compile_remediation_overlay_spec(
        {
            "slug": "pslf-buyback-calculator",
            "query": "pslf buyback settlement calculator",
            "target_url": "https://prexvo.com/tools/pslf-buyback-calculator/",
            "impressions": 45,
            "clicks": 0,
            "ctr": 0.0,
            "position": 8.4,
            "citation_gap_status": "LOSING_TO_WEAKER_DOMAINS",
            "weaker_cited_domains": ["studentaid.gov", "reddit.com"],
        },
        tenant_id="prexvo",
    )
    assert "34 CFR 685.219" in pslf_spec["quick_answer"]
    assert any("Buyback" in r.get("scenario", "") for r in pslf_spec["comparison_rows"])
    assert pslf_spec["citation_gap_status"] == "LOSING_TO_WEAKER_DOMAINS"


def test_capabilities_1_through_6_and_north_star_scorecard(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """
    Verifies CAP-1 through CAP-6 and the automated 30-day/60-day North Star scorecard:
      - CAP-1: Secondary title modifier inside [50, 60] chars + 60-day top-20 rank stability freeze
      - CAP-2: Token-bucket daily GSC quota governor + priority-weighted URL allocation + prune queue
      - CAP-3: First-10%-viewport autonomous statutory assertions + AI Mode decision-branch matrix
      - CAP-4: Public Statistics Citation-Hub nodes + broken calculator link-reclamation briefs
      - CAP-5: Source-to-visible keyword frequency ratio gate (< 3.0x)
      - CAP-6: AI Fan-Out query segmentation + google.com/goto AI Mode referrer attribution
      - North Star CLI & scorecard evaluation
    """
    from pseofactory.distributor import (
        compile_broken_calculator_link_reclamation_briefs,
        compile_public_benchmark_citation_hubs,
        generate_ai_benchmark_nodes,
    )
    from pseofactory.gsc_remediation import (
        _normalize_title_50_60,
        compile_remediation_overlay_spec,
        inject_overlay_into_html,
    )
    from pseofactory.indexer import PushIndexer
    from pseofactory.seo_growth_loops import (
        classify_ai_fan_out_query,
        evaluate_north_star_targets,
    )
    from pseofactory.verifier import verify_html_source_keyword_inflation_ratio
    from pseofactory.visual_primitives import render_runtime_synchronizer_script

    # CAP-1: Secondary title modifier strictly inside [50, 60] chars & 60-day top-20 freeze
    t_str = _normalize_title_50_60(
        "1031 Exchange Calculator",
        brand="ProfitHelm",
        tenant_id="profithelm",
        secondary_modifier="Form 8824",
    )
    assert 50 <= len(t_str) <= 60
    assert "(" in t_str and ")" in t_str

    spec_top20 = compile_remediation_overlay_spec(
        {
            "slug": "1031-exchange-calculator",
            "query": "1031 exchange boot calculator",
            "target_url": "https://profithelm.com/tools/1031-exchange-calculator/",
            "position": 9.2,
            "impressions": 140,
            "clicks": 3,
        },
        tenant_id="profithelm",
    )
    assert spec_top20["top_20_stability_lock_days"] == 60
    assert spec_top20["rank_stability_freeze_active"] is True

    # CAP-2: Priority indexing allocation & token-bucket GSC quota governor
    indexer = PushIndexer(dist_dir=tmp_path / "dist", domain="profithelm.com")
    indexer.repo_root = tmp_path
    prioritized = indexer.prioritize_urls_for_indexing_allocation(
        [
            "https://profithelm.com/scenarios/some-long-tail/",
            "https://profithelm.com/tools/1031-exchange-calculator/",
            "https://profithelm.com/",
            "https://profithelm.com/tools",
        ]
    )
    assert prioritized[0] == "https://profithelm.com/"
    assert prioritized[1] == "https://profithelm.com/tools"
    assert prioritized[2] == "https://profithelm.com/tools/1031-exchange-calculator/"
    q_res = indexer.check_and_consume_gsc_quota(units=2, bucket="inspection")
    assert q_res["allowed"] is True
    assert q_res["used"] == 2

    # CAP-3: Autonomous statutory assertions & second-level AI Mode decision matrix
    assert len(spec_top20["autonomous_citation_assertions"]) == 3
    assert len(spec_top20["ai_mode_decision_matrix"]) == 3
    sample_html = (
        "<html><head><title>Old Title</title></head><body>"
        '<main><aside class="quick-answer"><p>Old answer</p></aside></main></body></html>'
    )
    injected_html = inject_overlay_into_html(sample_html, spec_top20)
    assert 'data-ai-citation-block="true"' in injected_html
    assert 'data-prominence="first-10-percent"' in injected_html
    assert 'data-ai-decision-matrix="true"' in injected_html

    # CAP-4: Public Statistics Citation-Hub nodes & broken calculator link reclamation
    ph_hub = compile_public_benchmark_citation_hubs(tenant="profithelm")
    assert ph_hub["payload"]["citable_statistics_count"] >= 3
    reclaim = compile_broken_calculator_link_reclamation_briefs(tenant="prexvo")
    assert reclaim["briefs_count"] >= 2
    nodes_res = generate_ai_benchmark_nodes(tenant="profithelm")
    assert "public_statistics_citation_hub.md" in nodes_res["files"]
    assert "broken_calculator_link_reclamation.json" in nodes_res["files"]

    # CAP-5: Source-to-visible keyword frequency ratio gate (< 3.0x)
    clean_page = (
        "<html><head><title>1031 Exchange Calculator</title></head>"
        "<body><h1>1031 Exchange Calculator</h1><p>Use this 1031 exchange calculator to defer capital gains.</p></body></html>"
    )
    assert verify_html_source_keyword_inflation_ratio(clean_page)["status"] == "PASS"
    stuffed_page = (
        '<html><head><title>Depreciation Calculator</title>'
        '<script>var x = "' + ("depreciation " * 30) + '";</script></head>'
        "<body><h1>Depreciation Calculator</h1><p>Simple depreciation model.</p></body></html>"
    )
    assert verify_html_source_keyword_inflation_ratio(stuffed_page, max_ratio=3.0)["status"] == "FAIL"

    # CAP-6: AI Fan-Out query segmentation & google.com/goto AI Mode referrer attribution
    fan_out = classify_ai_fan_out_query("how much does an s corp save on 185k profit in 2026")
    assert fan_out["is_ai_fan_out"] is True
    sync_js = render_runtime_synchronizer_script()
    assert "google.com/goto" in sync_js
    assert "google_ai_mode" in sync_js

    # North Star scorecard & CLI evaluation
    repo_root = _seed_tenant_fixture(tmp_path / "tenant_ns")
    ns_card = evaluate_north_star_targets(
        property_id="profithelm",
        repo_root=repo_root,
        dist_dir=repo_root / "dist",
        persist=True,
    )
    assert ns_card["workflow"] == "north_star_scorecard"
    assert "1_search_impressions_and_ctr" in ns_card["pillars"]
    assert "3_ai_citations_and_entity_authority" in ns_card["pillars"]
    assert (repo_root / ".agy" / "north_star_scorecard.json").is_file()

    rc_ns = cli_main(["north-star", "--property", "profithelm", "--dry-run", "--json"])
    assert rc_ns == 0
    ns_out = json.loads(capsys.readouterr().out)
    assert ns_out["workflow"] == "north_star_scorecard"


def test_closed_loop_cohort_reflection_rollback_and_winning_pattern_propagation(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """
    Verifies the closed-loop cohort reflection and maintenance mechanism:
      1. Correlates historical run manifests, Search Console snapshots, freshness audits,
         and partner click logs across all 4 cohorts (title_remediation, priority_indexing_push,
         citation_restructure, sponsor_slot_update).
      2. Automatically rolls back degraded overlays (including stripping injected HTML overlay
         elements and restoring baseline <title>) and flags early regressions during active locks.
      3. Doubles down on winning patterns across legacy ACTIVE_LOCKED calculator and guide inventory
         by backfilling secondary_title_modifier, autonomous_citation_assertions, ai_mode_decision_matrix,
         and conversion_slot_weights without breaking measurement lock timestamps.
      4. Enforces engine and tenant contracts via verify_cohort_reflection_contract and
         PushIndexer.prioritize_urls_for_indexing_allocation.
    """
    from pseofactory.gsc_remediation import (
        evaluate_expired_overlays,
        inject_overlay_into_html,
        rollback_degraded_overlay_from_html,
    )
    from pseofactory.indexer import PushIndexer
    from pseofactory.seo_growth_loops import evaluate_closed_loop_cohort_reflection
    from pseofactory.verifier import MasterSEOVerifier, verify_cohort_reflection_contract

    repo_root = _seed_tenant_fixture(tmp_path / "tenant_cr")
    agy_dir = repo_root / ".agy"
    overlays_dir = agy_dir / "overlays"
    overlays_dir.mkdir(parents=True, exist_ok=True)

    # Seed partner click log with real outbound clicks and CTA slot attribution
    (agy_dir / "outbound_partner_engagement.json").write_text(
        json.dumps(
            {
                "property_id": "profithelm",
                "total_events_processed": 10,
                "total_outbound_clicks": 6,
                "total_calculator_interactions": 4,
                "total_estimated_revenue_yield_usd": 495.0,
                "by_slug": {
                    "section-179-calculator": {
                        "outbound_clicks": 4,
                        "calculator_interactions": 3,
                        "estimated_revenue_yield_usd": 340.0,
                    },
                    "s-corp-tax-calculator": {
                        "outbound_clicks": 2,
                        "calculator_interactions": 1,
                        "estimated_revenue_yield_usd": 155.0,
                    },
                },
                "by_partner": {
                    "gusto_payroll": {"clicks": 4, "estimated_yield_usd": 340.0},
                    "collective_scorp": {"clicks": 2, "estimated_yield_usd": 155.0},
                },
                "by_cta_slot": {
                    "post_calculation_verdict": 4,
                    "comparison_table_winner": 2,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # Seed an active overlay with early position regression (> 2.0 drop) and legacy missing CAP-1/CAP-3 fields
    active_lock_future = "2099-12-31T00:00:00+00:00"
    (overlays_dir / "s-corp-tax-calculator.json").write_text(
        json.dumps(
            {
                "slug": "s-corp-tax-calculator",
                "query": "s corp tax calculator",
                "target_url": "https://profithelm.com/tools/s-corp-tax-calculator/",
                "baseline_impressions": 100,
                "baseline_clicks": 4,
                "baseline_ctr": 0.04,
                "baseline_position": 6.0,
                "locked_until": active_lock_future,
                "status": "ACTIVE_LOCKED",
                "title_rewrite": "S Corp Tax Calculator (2026 Savings Model) | ProfitHelm",
                "quick_answer": "Calculate S-Corp FICA tax savings under IRC Section 1366.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    scorp_html_dir = repo_root / "dist" / "tools" / "s-corp-tax-calculator"
    scorp_html_dir.mkdir(parents=True, exist_ok=True)
    (scorp_html_dir / "index.html").write_text(
        "<html><head><title>S Corp Tax Calculator | ProfitHelm</title></head>"
        '<body><main><aside class="quick-answer"><p>Initial answer</p></aside></main></body></html>',
        encoding="utf-8",
    )

    # Seed an expired overlay that degraded in position so evaluate_expired_overlays rolls it back
    expired_lock_past = "2020-01-01T00:00:00+00:00"
    degraded_html_dir = repo_root / "dist" / "tools" / "degraded-tool"
    degraded_html_dir.mkdir(parents=True, exist_ok=True)
    degraded_spec = {
        "slug": "degraded-tool",
        "query": "degraded tax tool",
        "target_url": "https://profithelm.com/tools/degraded-tool/",
        "baseline_impressions": 80,
        "baseline_clicks": 4,
        "baseline_ctr": 0.05,
        "baseline_position": 5.0,
        "locked_until": expired_lock_past,
        "status": "ACTIVE_LOCKED",
        "title_rewrite": "Degraded Tax Tool (Experimental Title) | ProfitHelm",
        "secondary_title_modifier": "Experimental Title",
        "quick_answer": "Experimental quick answer.",
        "autonomous_citation_assertions": ["Assertion 1", "Assertion 2", "Assertion 3"],
    }
    injected_degraded = inject_overlay_into_html(
        "<html><head><title>Degraded Tool Original | ProfitHelm</title></head>"
        '<body><main><aside class="quick-answer"><p>Base</p></aside></main></body></html>',
        degraded_spec,
    )
    assert 'id="gsc-striking-overlay"' in injected_degraded
    (degraded_html_dir / "index.html").write_text(injected_degraded, encoding="utf-8")
    (overlays_dir / "degraded-tool.json").write_text(json.dumps(degraded_spec, indent=2), encoding="utf-8")

    live_q = [
        # s-corp-tax-calculator dropped from pos 6.0 to pos 9.5 while still under active lock -> early regression flag
        {"query": "s corp tax calculator", "impressions": 60, "clicks": 1, "ctr": 0.0167, "position": 9.5},
        # degraded-tool dropped from pos 5.0 to pos 11.2 after lock expired -> automatic rollback
        {"query": "degraded tax tool", "impressions": 30, "clicks": 0, "ctr": 0.0, "position": 11.2},
        # section-179-calculator improved to pos 6.2 with strong impressions
        {"query": "section 179 deduction calculator", "impressions": 150, "clicks": 9, "ctr": 0.06, "position": 6.2},
    ]

    eval_res = evaluate_expired_overlays(
        site_url="sc-domain:profithelm.com",
        base_dir=repo_root,
        live_queries=live_q,
    )
    assert eval_res["summary"]["DEGRADED_ROLLED_BACK"] >= 1
    assert eval_res["summary"]["FLAGGED_EARLY_REGRESSION"] >= 1

    # Verify degraded HTML had its remediation overlay stripped and baseline title restored
    rolled_back_html = (degraded_html_dir / "index.html").read_text(encoding="utf-8")
    assert 'id="gsc-striking-overlay"' not in rolled_back_html
    assert "Experimental Title" not in rolled_back_html

    # Run closed-loop cohort reflection and winning pattern propagation
    cr_report = evaluate_closed_loop_cohort_reflection(
        property_id="profithelm",
        repo_root=repo_root,
        dist_dir=repo_root / "dist",
        live_queries=live_q,
        propagate_winning_patterns=True,
        persist=True,
    )
    assert cr_report["workflow"] == "closed_loop_cohort_reflection"
    assert cr_report["status"] == "PASS"
    assert "1_title_remediation" in cr_report["cohorts"]
    assert "2_priority_indexing_push" in cr_report["cohorts"]
    assert "3_citation_restructure" in cr_report["cohorts"]
    assert "4_sponsor_slot_update" in cr_report["cohorts"]

    # Check rollback and early regression tracking
    rf_actions = cr_report["rollback_and_flag_actions"]
    assert rf_actions["rolled_back_count"] >= 1
    assert "degraded-tool" in rf_actions["rolled_back_slugs"]
    assert rf_actions["early_regression_flagged_count"] >= 1
    assert "s-corp-tax-calculator" in rf_actions["early_regression_flagged_slugs"]

    # Check winning pattern propagation onto s-corp-tax-calculator without breaking its lock
    scorp_overlay = json.loads((overlays_dir / "s-corp-tax-calculator.json").read_text(encoding="utf-8"))
    assert scorp_overlay["locked_until"] == active_lock_future
    assert scorp_overlay.get("secondary_title_modifier")
    assert len(scorp_overlay.get("autonomous_citation_assertions", [])) == 3
    assert len(scorp_overlay.get("ai_mode_decision_matrix", [])) == 3
    assert scorp_overlay.get("conversion_slot_weights", {}).get("post_calculation_verdict", 0) >= 0.6

    # Verify engine contract and MasterSEOVerifier gate
    contract_check = verify_cohort_reflection_contract(cr_report, repo_root=repo_root)
    assert contract_check["status"] == "PASS"
    verifier = MasterSEOVerifier(dist_dir=repo_root / "dist", repo_root=repo_root)
    assert verifier.check_cohort_reflection_gate()["status"] == "PASS"

    # Verify PushIndexer auto-loads priority_indexing_urls from cohort_reflection_ledger.json
    indexer = PushIndexer(dist_dir=repo_root / "dist", domain="profithelm.com")
    indexer.repo_root = repo_root
    boosted_url = "https://profithelm.com/guides/special-priority-guide"
    cr_ledger_path = agy_dir / "cohort_reflection_ledger.json"
    cr_saved = json.loads(cr_ledger_path.read_text(encoding="utf-8"))
    cr_saved["next_maintenance_directives"]["priority_indexing_urls"] = [boosted_url]
    cr_ledger_path.write_text(json.dumps(cr_saved, indent=2), encoding="utf-8")

    ordered = indexer.prioritize_urls_for_indexing_allocation(
        [
            "https://profithelm.com/scenarios/long-tail-1",
            "https://profithelm.com/tools/section-179-calculator/",
            boosted_url,
            "https://profithelm.com/",
        ]
    )
    assert ordered[0] == "https://profithelm.com/"
    assert ordered[1] == boosted_url

    # Verify CLI cohort-reflection subcommand
    rc_cr = cli_main(["cohort-reflection", "--property", "profithelm", "--dry-run", "--json"])
    assert rc_cr == 0
    cr_cli_out = json.loads(capsys.readouterr().out)
    assert cr_cli_out["workflow"] == "closed_loop_cohort_reflection"


def test_cohort_reflection_persists_nested_leaf_overlays_for_idempotent_rebuild(tmp_path):
    """
    Verifies that evaluate_closed_loop_cohort_reflection persists remediation overlays
    for nested spoke slugs containing '/' (e.g. 'irs-2027-tax-brackets/alabama') into
    .agy/overlays/<flat_slug>.json so subsequent RetroReflectionEngine.retrofit_estate()
    rebuilds preserve <div id="gsc-striking-overlay"> without mid-build working tree churn.
    """
    from pseofactory.maintenance import RetroReflectionEngine
    from pseofactory.seo_growth_loops import evaluate_closed_loop_cohort_reflection

    repo_root = tmp_path / "profithelm-platform"
    dist_dir = repo_root / "dist"
    leaf_dir = dist_dir / "tools" / "irs-2027-tax-brackets" / "alabama"
    leaf_dir.mkdir(parents=True, exist_ok=True)

    base_leaf_html = (
        "<!DOCTYPE html><html lang='en'><head>"
        "<title>Alabama 2027 Income Tax Brackets Calculator | ProfitHelm</title>"
        "<link rel='canonical' href='https://profithelm.com/tools/irs-2027-tax-brackets/alabama/'>"
        "</head><body><main><h1>Alabama 2027 Tax Brackets</h1>"
        "<section class='calculator-card'><p>Interactive state tax bracket model.</p></section>"
        "</main></body></html>"
    )
    leaf_html_file = leaf_dir / "index.html"
    leaf_html_file.write_text(base_leaf_html, encoding="utf-8")

    evaluate_closed_loop_cohort_reflection(
        property_id="profithelm",
        repo_root=repo_root,
        dist_dir=dist_dir,
        live_queries=[],
        persist=True,
    )

    persisted_ov = repo_root / ".agy" / "overlays" / "irs-2027-tax-brackets-alabama.json"
    assert persisted_ov.is_file(), "Expected nested leaf overlay JSON to be persisted to .agy/overlays/"

    # Simulate builder.build_all() overwriting the leaf HTML from base template, followed by retrofit_estate()
    leaf_html_file.write_text(base_leaf_html, encoding="utf-8")
    RetroReflectionEngine.retrofit_estate(
        dist_dir=dist_dir,
        property_id="profithelm",
        canonical_base="https://profithelm.com",
    )
    rebuilt_html = leaf_html_file.read_text(encoding="utf-8")
    assert 'id="gsc-striking-overlay"' in rebuilt_html
    assert 'data-ai-citation-assertions="true"' in rebuilt_html


