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


def test_empirical_cohort_truth_emergency_rollback_consolidation_and_probe_filtering(tmp_path: Path) -> None:
    """
    Verifies the 3 owner-approved empirical cohort truth & portfolio hygiene contracts:
      A1: Immediate emergency rollback during active locks for Page-1 dropouts and severe
          rank/impression regressions (pos_delta >= +10 or impr_drop <= -50%), stripping
          synthetic 160-impression (CRAWL_BUDGET_SIGNAL_LAG) and parent-hub (378-impr)
          fallbacks so zero-impression spokes are never marked WINNING_ACCRETIVE.
      A2: Executing noindex/301 hub consolidation on aged zero-impression spokes (>= 60d),
          freezing new cluster expansion when pre-consolidation coverage < threshold, and
          evaluating North Star indexed coverage against active indexable routes.
      A3: Filtering synthetic probe subIDs (*_oct19, *_card_*, *_edge) from cohort
          conversion slot weights and canonicalizing legacy Prexvo/ProfitHelm click slugs.
    """
    from pseofactory.gsc_remediation import inject_overlay_into_html
    from pseofactory.seo_growth_loops import (
        evaluate_closed_loop_cohort_reflection,
        evaluate_content_portfolio_decisions,
        evaluate_north_star_targets,
    )
    from pseofactory.verifier import verify_cohort_reflection_contract

    repo_root = _seed_tenant_fixture(tmp_path / "empirical_truth_tenant")
    agy_dir = repo_root / ".agy"
    overlays_dir = agy_dir / "overlays"
    overlays_dir.mkdir(parents=True, exist_ok=True)
    active_lock_future = "2099-12-31T00:00:00+00:00"

    # 1. Seed a Page-1 dropout overlay still under active lock (pos 7.0 -> 14.0, impr 41 -> 12)
    dropout_dir = repo_root / "dist" / "tools" / "llc-vs-s-corp-calculator"
    dropout_dir.mkdir(parents=True, exist_ok=True)
    dropout_spec = {
        "slug": "llc-vs-s-corp-calculator",
        "query": "llc vs s corp tax calculator",
        "target_url": "https://profithelm.com/tools/llc-vs-s-corp-calculator/",
        "baseline_impressions": 41,
        "baseline_clicks": 0,
        "baseline_ctr": 0.0,
        "baseline_position": 7.0,
        "locked_until": active_lock_future,
        "status": "ACTIVE_LOCKED",
        "title_rewrite": "LLC vs S-Corp Tax Calculator (2026 Savings) | ProfitHelm",
        "secondary_title_modifier": "(2026 Savings)",
        "quick_answer": "Compare LLC and S-Corp self-employment tax savings.",
        "autonomous_citation_assertions": ["A1", "A2", "A3"],
    }
    (dropout_dir / "index.html").write_text(
        inject_overlay_into_html(
            "<html><head><title>LLC vs S-Corp Calculator | ProfitHelm</title></head>"
            "<body><main><h1>LLC vs S-Corp Calculator</h1><aside class='quick-answer'><p>Base</p></aside></main></body></html>",
            dropout_spec,
        ),
        encoding="utf-8",
    )
    (overlays_dir / "llc-vs-s-corp-calculator.json").write_text(
        json.dumps(dropout_spec, indent=2), encoding="utf-8"
    )

    # 2. Seed a synthetic 160-impression CRAWL_BUDGET_SIGNAL_LAG overlay with 0 empirical impressions
    synth_dir = repo_root / "dist" / "tools" / "self-employment-tax-calculator"
    synth_dir.mkdir(parents=True, exist_ok=True)
    (synth_dir / "index.html").write_text(
        "<html><head><title>Self Employment Tax Calculator | ProfitHelm</title></head>"
        "<body><main><h1>Self Employment Tax Calculator</h1></main></body></html>",
        encoding="utf-8",
    )
    (overlays_dir / "self-employment-tax-calculator.json").write_text(
        json.dumps(
            {
                "slug": "self-employment-tax-calculator",
                "query": "self employment tax calculator",
                "target_url": "https://profithelm.com/tools/self-employment-tax-calculator/",
                "baseline_impressions": 160,
                "baseline_clicks": 0,
                "baseline_ctr": 0.0,
                "baseline_position": 10.0,
                "baseline_source": "CRAWL_BUDGET_SIGNAL_LAG",
                "locked_until": active_lock_future,
                "status": "ACTIVE_LOCKED",
                "title_rewrite": "Self-Employment Tax Calculator (2026 SECA) | ProfitHelm",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # 3. Seed a zero-impression child spoke under irs-2027-tax-brackets (parent hub has 378 impr)
    zero_spoke_dir = repo_root / "dist" / "tools" / "irs-2027-tax-brackets" / "wyoming"
    zero_spoke_dir.mkdir(parents=True, exist_ok=True)
    wy_html_file = zero_spoke_dir / "index.html"
    wy_html_file.write_text(
        "<html><head><title>Wyoming 2027 Tax Brackets | ProfitHelm</title></head>"
        "<body><main><h1>Wyoming 2027 Tax Brackets</h1></main></body></html>",
        encoding="utf-8",
    )
    old_ts = (datetime.now(timezone.utc) - timedelta(days=90)).timestamp()
    os.utime(wy_html_file, (old_ts, old_ts))
    (overlays_dir / "irs-2027-tax-brackets-wyoming.json").write_text(
        json.dumps(
            {
                "slug": "irs-2027-tax-brackets/wyoming",
                "query": "wyoming tax brackets 2027",
                "target_url": "https://profithelm.com/tools/irs-2027-tax-brackets/wyoming/",
                "baseline_impressions": 378,
                "baseline_clicks": 0,
                "baseline_ctr": 0.0,
                "baseline_position": 12.0,
                "locked_until": active_lock_future,
                "status": "ACTIVE_LOCKED",
                "title_rewrite": "Wyoming 2027 Tax Brackets (2026 Brackets) | ProfitHelm",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # 4. Seed partner engagement with legacy slug and synthetic probe subIDs
    refi_dir = repo_root / "dist" / "tools" / "student-loan-refinance-break-even-calculator"
    refi_dir.mkdir(parents=True, exist_ok=True)
    (refi_dir / "index.html").write_text(
        "<html><head><title>Student Loan Refinance Break-Even Calculator | ProfitHelm</title></head>"
        "<body><main><h1>Student Loan Refinance Break-Even Calculator</h1></main></body></html>",
        encoding="utf-8",
    )
    (agy_dir / "outbound_partner_clicks.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event_type": "outbound_partner_click",
                        "property_id": "profithelm",
                        "slug": "student-loan-refinance-savings-calculator",
                        "partner_key": "splash_financial",
                        "cta_slot": "post_calculation_verdict",
                        "sub_id": "px_refi_card_1",
                        "clicks": 1,
                        "estimated_revenue_yield_usd": 145.0,
                    }
                ),
                json.dumps(
                    {
                        "event_type": "outbound_partner_click",
                        "property_id": "profithelm",
                        "slug": "student-loan-refinance-savings-calculator",
                        "partner_key": "splash_financial",
                        "cta_slot": "post_calculation_verdict",
                        "sub_id": "px_ibr_oct19",
                        "clicks": 1,
                        "estimated_revenue_yield_usd": 145.0,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (agy_dir / "outbound_partner_engagement.json").write_text(
        json.dumps(
            {
                "property_id": "profithelm",
                "total_events_processed": 2,
                "total_outbound_clicks": 2,
                "total_calculator_interactions": 1,
                "total_estimated_revenue_yield_usd": 290.0,
                "by_slug": {
                    "student-loan-refinance-savings-calculator": {
                        "outbound_clicks": 2,
                        "calculator_interactions": 1,
                        "estimated_revenue_yield_usd": 290.0,
                        "partners": {"splash_financial": 2},
                        "cta_slots": {"post_calculation_verdict": 2},
                    }
                },
                "by_partner": {"splash_financial": {"clicks": 2, "estimated_yield_usd": 290.0}},
                "by_cta_slot": {"post_calculation_verdict": {"outbound_clicks": 2, "estimated_revenue_yield_usd": 290.0}},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    consolidated_gsc = {
        "baseline_rows": [
            {
                "query": "llc vs s corp tax calculator",
                "canonical_path": "/tools/llc-vs-s-corp-calculator",
                "canonical_slug": "llc-vs-s-corp-calculator",
                "impressions": 41,
                "clicks": 0,
                "ctr": 0.0,
                "position": 7.0,
            },
            {
                "query": "irs 2027 tax brackets",
                "canonical_path": "/tools/irs-2027-tax-brackets",
                "canonical_slug": "irs-2027-tax-brackets",
                "impressions": 300,
                "clicks": 1,
                "ctr": 0.0033,
                "position": 18.0,
            },
        ],
        "current_rows": [
            {
                "query": "llc vs s corp tax calculator",
                "canonical_path": "/tools/llc-vs-s-corp-calculator",
                "canonical_slug": "llc-vs-s-corp-calculator",
                "impressions": 12,
                "clicks": 0,
                "ctr": 0.0,
                "position": 14.0,
            },
            {
                "query": "irs 2027 tax brackets",
                "canonical_path": "/tools/irs-2027-tax-brackets",
                "canonical_slug": "irs-2027-tax-brackets",
                "impressions": 378,
                "clicks": 2,
                "ctr": 0.0053,
                "position": 15.0,
            },
        ],
        "impressions_by_path": {
            "/tools/llc-vs-s-corp-calculator": 12,
            "/tools/irs-2027-tax-brackets": 378,
            "/tools/irs-2027-tax-brackets/california": 45,
            "/tools/section-179-calculator": 120,
            "/tools/section-1031-calculator/texas": 25,
        },
        "clicks_by_path": {"/tools/irs-2027-tax-brackets": 2, "/tools/section-179-calculator": 3},
    }

    cr_rep = evaluate_closed_loop_cohort_reflection(
        property_id="profithelm",
        repo_root=repo_root,
        dist_dir=repo_root / "dist",
        consolidated_gsc=consolidated_gsc,
        propagate_winning_patterns=True,
        enforce_rollback_contracts=True,
        persist=True,
    )

    # A1: Page-1 dropout rolled back immediately despite active lock
    assert "llc-vs-s-corp-calculator" in cr_rep["rollback_and_flag_actions"]["rolled_back_slugs"]
    rb_html = (dropout_dir / "index.html").read_text(encoding="utf-8")
    assert 'id="gsc-striking-overlay"' not in rb_html
    assert "(2026 Savings)" not in rb_html

    # A1: Synthetic 160-impression fallback and zero-impression child spoke stripped and not WINNING_ACCRETIVE
    c1_by_slug = {r["slug"]: r for r in cr_rep["cohorts"]["1_title_remediation"]["records"]}
    assert c1_by_slug["self-employment-tax-calculator"]["baseline_impressions"] == 0
    assert c1_by_slug["self-employment-tax-calculator"]["cohort_outcome"] != "WINNING_ACCRETIVE"
    assert c1_by_slug["irs-2027-tax-brackets/wyoming"]["current_impressions"] == 0
    assert c1_by_slug["irs-2027-tax-brackets/wyoming"]["cohort_outcome"] != "WINNING_ACCRETIVE"

    # A3: Legacy partner click slug canonicalized and synthetic probe subIDs filtered from slot weights
    c4 = cr_rep["cohorts"]["4_sponsor_slot_update"]
    assert c4["synthetic_probe_clicks_filtered"] == 2
    assert c4["verified_non_probe_outbound_clicks"] == 0
    assert (
        c4["canonicalized_legacy_slugs"].get("student-loan-refinance-savings-calculator")
        == "student-loan-refinance-break-even-calculator"
    )
    slot_weights = {s["cta_slot"]: s["empirical_weight"] for s in c4["by_cta_slot"]}
    assert slot_weights.get("post_calculation_verdict") == 1.0

    # A2: Portfolio consolidation and North Star active coverage
    os.utime(wy_html_file, (old_ts, old_ts))
    port_rep = evaluate_content_portfolio_decisions(
        property_id="profithelm",
        repo_root=repo_root,
        dist_dir=repo_root / "dist",
        consolidated_gsc=consolidated_gsc,
        max_age_days=30.0,
        persist=True,
    )
    assert port_rep["cluster_expansion_frozen"] is True
    wy_cand = next(
        (c for c in port_rep["zero_impression_candidates"] if c["url_path"] == "/tools/irs-2027-tax-brackets/wyoming"),
        None,
    )
    assert wy_cand is not None
    assert wy_cand["status"] == "CONSOLIDATED_NOINDEX_301"
    assert wy_cand["recommended_consolidation_target"] == "/tools/irs-2027-tax-brackets/"
    assert wy_cand["noindex_applied"] is True

    ns_rep = evaluate_north_star_targets(
        property_id="profithelm",
        repo_root=repo_root,
        dist_dir=repo_root / "dist",
        consolidated_gsc=consolidated_gsc,
        portfolio_report=port_rep,
        persist=True,
    )
    p2 = ns_rep["pillars"]["2_indexed_coverage_and_hygiene"]
    assert p2["cluster_expansion_frozen"] is True
    assert p2["indexed_impression_ratio_pct"] >= p2["pre_consolidation_indexed_coverage_pct"]
    assert verify_cohort_reflection_contract(cr_rep, repo_root=repo_root)["status"] == "PASS"


def test_search_mechanics_heuristics_contextual_links_impression_split_and_crawl_staleness(tmp_path: Path) -> None:
    """
    Verifies the 3 surgical search mechanics heuristics derived from ian.is/tools comparison:
      1. Contextual body link vs <nav>/<header>/<footer> boilerplate link separation, <3 contextual
         in-degree boost (+15.0), and generic anchor text ('click here', 'read more') detection.
      2. 10%-80% impression-share split & dominance ratio cannibalization triage (suppressing
         false-positive consolidation when a single winner holds >80% share and secondary URLs
         are <10% noise or 301-redirected, while flagging true 60%/40% splits).
      3. 90-day stale crawl / 130-day index drop risk, sitemap <lastmod> uniformity/future-date
         detection, and reverse-orphan sitemap check.
    """
    from pseofactory.indexing_inspector import DailyIndexingInspector
    from pseofactory.qualification import evaluate_query_impression_split, qualify_search_intent
    from pseofactory.seo_growth_loops import (
        audit_gsc_cannibalization_splits,
        discover_internal_linking_opportunities,
    )

    # 1. Contextual body links vs <nav>/<footer> boilerplate + generic anchors
    repo_root = tmp_path / "profithelm-platform"
    dist_dir = repo_root / "dist"
    for p in ("", "tools", "tools/nav-only-spoke", "tools/contextual-winner"):
        d = dist_dir / p if p else dist_dir
        d.mkdir(parents=True, exist_ok=True)

    # Nav links to /tools/nav-only-spoke/ from every page, but 0 body links point to it.
    # Meanwhile /tools/contextual-winner/ has a body link with a generic anchor 'click here'.
    nav_html = "<nav><a href='/tools/'>Tools</a><a href='/tools/nav-only-spoke/'>Nav Spoke</a></nav>"
    (dist_dir / "index.html").write_text(
        f"<html><head><title>Home | ProfitHelm</title></head><body>{nav_html}"
        "<main><p>For S-Corp savings, <a href='/tools/contextual-winner/'>click here</a>.</p></main></body></html>",
        encoding="utf-8",
    )
    (dist_dir / "tools" / "index.html").write_text(
        f"<html><head><title>Tools Hub | ProfitHelm</title></head><body>{nav_html}"
        "<main><p><a href='/tools/contextual-winner/'>Contextual Winner Calculator</a></p></main></body></html>",
        encoding="utf-8",
    )
    (dist_dir / "tools" / "nav-only-spoke" / "index.html").write_text(
        f"<html><head><title>Nav Only Spoke | ProfitHelm</title></head><body>{nav_html}"
        "<main><h1>Nav Only Spoke</h1></main></body></html>",
        encoding="utf-8",
    )
    (dist_dir / "tools" / "contextual-winner" / "index.html").write_text(
        f"<html><head><title>Contextual Winner | ProfitHelm</title></head><body>{nav_html}"
        "<main><h1>Contextual Winner</h1></main></body></html>",
        encoding="utf-8",
    )

    gsc_mock = {
        "current_rows": [
            {
                "query": "nav only spoke calculator",
                "canonical_path": "/tools/nav-only-spoke",
                "canonical_url": "https://profithelm.com/tools/nav-only-spoke/",
                "impressions": 40,
                "clicks": 1,
                "position": 11.0,
            },
            {
                "query": "s corp tax calculator",
                "canonical_path": "/tools/contextual-winner",
                "canonical_url": "https://profithelm.com/tools/contextual-winner/",
                "impressions": 92,
                "clicks": 4,
                "position": 6.0,
            },
            {
                "query": "s corp tax calculator",
                "canonical_path": "/tools/nav-only-spoke",
                "canonical_url": "https://profithelm.com/tools/nav-only-spoke/",
                "impressions": 5,
                "clicks": 0,
                "position": 19.0,
            },
            {
                "query": "section 179 bonus depreciation",
                "canonical_path": "/tools/contextual-winner",
                "canonical_url": "https://profithelm.com/tools/contextual-winner/",
                "impressions": 55,
                "clicks": 2,
                "position": 8.0,
            },
            {
                "query": "section 179 bonus depreciation",
                "canonical_path": "/tools/nav-only-spoke",
                "canonical_url": "https://profithelm.com/tools/nav-only-spoke/",
                "impressions": 45,
                "clicks": 1,
                "position": 9.5,
            },
        ],
        "impressions_by_path": {
            "/tools/nav-only-spoke": 40,
            "/tools/contextual-winner": 92,
        },
        "clicks_by_path": {
            "/tools/nav-only-spoke": 1,
            "/tools/contextual-winner": 4,
        },
    }

    link_res = discover_internal_linking_opportunities(
        property_id="profithelm",
        repo_root=repo_root,
        dist_dir=dist_dir,
        consolidated_gsc=gsc_mock,
        persist=False,
    )
    assert "/tools/nav-only-spoke" in link_res["contextual_orphans"]
    assert link_res["generic_anchor_instances_count"] == 1
    opp_by_path = {o["target_path"]: o for o in link_res["opportunities"]}
    nav_opp = opp_by_path["/tools/nav-only-spoke/"]
    assert nav_opp["in_degree"] == 3  # linked in <nav> from 3 other pages
    assert nav_opp["contextual_in_degree"] == 0
    assert nav_opp["boilerplate_only_inbound"] is True
    assert nav_opp["under_three_contextual_links"] is True

    winner_opp = opp_by_path["/tools/contextual-winner/"]
    assert winner_opp["contextual_in_degree"] == 2
    assert winner_opp["generic_inbound_anchors_count"] == 1

    # 2. 10%-80% Impression-Share Split & Dominance Ratio Cannibalization Triage
    split_audit = audit_gsc_cannibalization_splits(
        property_id="profithelm",
        repo_root=repo_root,
        consolidated_gsc=gsc_mock,
    )
    assert split_audit["multi_url_queries_evaluated"] == 2
    assert split_audit["true_cannibalization_splits_count"] == 1
    assert split_audit["dominant_winner_noise_suppressed_count"] == 1
    assert split_audit["true_cannibalization_splits"][0]["query"] == "section 179 bonus depreciation"
    assert split_audit["dominant_winner_suppressed"][0]["query"] == "s corp tax calculator"

    # Verify qualify_search_intent preserves plain URL list behavior while suppressing >80% dominant noise when telemetry is present
    plain_verdict = qualify_search_intent(
        query="s corp tax calculator",
        impressions=100,
        position=8.0,
        competing_pages=["/tools/contextual-winner/", "/tools/nav-only-spoke/"],
    )
    assert plain_verdict["action"] == "CONSOLIDATE_PAGES"

    weighted_dominant_verdict = qualify_search_intent(
        query="s corp tax calculator",
        impressions=97,
        position=6.0,
        matching_tool="contextual-winner",
        competing_pages=[
            {"url": "/tools/contextual-winner/", "impressions": 92, "position": 6.0},
            {"url": "/tools/nav-only-spoke/", "impressions": 5, "position": 19.0},
        ],
    )
    assert weighted_dominant_verdict["action"] == "REFACTOR_PAGE"

    # 3. 90d/130d Crawl Staleness & Sitemap <lastmod> Uniformity / Reverse-Orphan Check
    agy_dir = repo_root / ".agy"
    agy_dir.mkdir(parents=True, exist_ok=True)
    now_ts = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc).timestamp()
    stale_100d_iso = datetime.fromtimestamp(now_ts - 100 * 86400, tz=timezone.utc).isoformat()
    drop_140d_iso = datetime.fromtimestamp(now_ts - 140 * 86400, tz=timezone.utc).isoformat()
    (agy_dir / "index_push_ledger.json").write_text(
        json.dumps(
            {
                "https://profithelm.com/tools/contextual-winner/": {
                    "url": "https://profithelm.com/tools/contextual-winner/",
                    "last_pushed": stale_100d_iso,
                },
                "https://profithelm.com/tools/nav-only-spoke/": {
                    "url": "https://profithelm.com/tools/nav-only-spoke/",
                    "last_pushed": drop_140d_iso,
                },
            }
        ),
        encoding="utf-8",
    )
    # Write a sitemap with 5 uniform timestamped <lastmod> entries and omitting /tools/nav-only-spoke/ (reverse orphan)
    uniform_ts = "2026-10-20T08:00:00Z"
    (dist_dir / "sitemap.xml").write_text(
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"
        f"<url><loc>https://profithelm.com/</loc><lastmod>{uniform_ts}</lastmod></url>"
        f"<url><loc>https://profithelm.com/tools/</loc><lastmod>{uniform_ts}</lastmod></url>"
        f"<url><loc>https://profithelm.com/tools/contextual-winner/</loc><lastmod>{uniform_ts}</lastmod></url>"
        f"<url><loc>https://profithelm.com/tools/a/</loc><lastmod>{uniform_ts}</lastmod></url>"
        f"<url><loc>https://profithelm.com/tools/b/</loc><lastmod>{uniform_ts}</lastmod></url>"
        "</urlset>",
        encoding="utf-8",
    )
    inspector = DailyIndexingInspector(tenant_id="profithelm", base_dir=repo_root, agy_dir=agy_dir)
    cs_audit = inspector.audit_crawl_staleness_and_sitemap_health(dist_dir=dist_dir, now_ts=now_ts)
    assert cs_audit["stale_crawl_90d_count"] == 2
    assert cs_audit["index_drop_risk_130d_count"] == 1
    assert cs_audit["sitemap_health"]["lastmod_uniform_build_timestamp_flagged"] is True
    assert "https://profithelm.com/tools/nav-only-spoke/" in cs_audit["sitemap_health"]["reverse_orphan_urls"]


def test_evaluate_expired_overlays_rolled_back_recovery_heals_spec_and_injects_html(tmp_path: Path) -> None:
    """
    Verifies that evaluate_expired_overlays:
      1. Keeps a DEGRADED_ROLLED_BACK overlay rolled back when it remains degraded (even if below emergency_rollback).
      2. When a DEGRADED_ROLLED_BACK overlay recovers during its lock window, restores popped overlay content keys
         (quick_answer, preset_scenarios, h2_headings, faq_entries) and re-injects id='gsc-striking-overlay' into dist HTML.
    """
    from pseofactory.gsc_remediation import evaluate_expired_overlays

    repo_root = tmp_path / "profithelm-platform"
    overlays_dir = repo_root / ".agy" / "overlays"
    overlays_dir.mkdir(parents=True, exist_ok=True)
    future_lock = "2099-12-31T00:00:00+00:00"

    # Case 1: DEGRADED_ROLLED_BACK overlay still experiencing >25% impression drop (is_degraded=True, emergency_rollback=False)
    utah_dir = repo_root / "dist" / "tools" / "irs-2027-tax-brackets" / "utah"
    utah_dir.mkdir(parents=True, exist_ok=True)
    (utah_dir / "index.html").write_text(
        "<html><head><title>Utah 2027 Tax Brackets | ProfitHelm</title></head>"
        "<body><main><h1>Utah 2027 Tax Brackets</h1></main></body></html>",
        encoding="utf-8",
    )
    (overlays_dir / "irs-2027-tax-brackets-utah.json").write_text(
        json.dumps(
            {
                "slug": "irs-2027-tax-brackets/utah",
                "query": "utah 2027 tax brackets",
                "target_url": "https://profithelm.com/tools/irs-2027-tax-brackets/utah/",
                "status": "DEGRADED_ROLLED_BACK",
                "locked_until": future_lock,
                "baseline_impressions": 36,
                "baseline_position": 86.53,
                "baseline_clicks": 0,
                "baseline_ctr": 0.0,
                "baseline_source": "GSC_EMPIRICAL_ROLLUP",
                "rolled_back_title_rewrite": "Utah 2027 Tax Brackets Calculator (IRS Table) | ProfitHelm",
            }
        ),
        encoding="utf-8",
    )

    # Case 2: DEGRADED_ROLLED_BACK overlay that genuinely recovered (impressions and rank improved)
    tx_dir = repo_root / "dist" / "tools" / "section-1031-calculator" / "texas"
    tx_dir.mkdir(parents=True, exist_ok=True)
    (tx_dir / "index.html").write_text(
        "<html><head><title>Texas Section 1031 Calculator | ProfitHelm</title></head>"
        "<body><main><h1>Texas Section 1031 Calculator</h1></main></body></html>",
        encoding="utf-8",
    )
    (overlays_dir / "section-1031-calculator-texas.json").write_text(
        json.dumps(
            {
                "slug": "section-1031-calculator/texas",
                "query": "texas section 1031 exchange",
                "target_url": "https://profithelm.com/tools/section-1031-calculator/texas/",
                "status": "DEGRADED_ROLLED_BACK",
                "locked_until": future_lock,
                "baseline_impressions": 20,
                "baseline_position": 15.0,
                "baseline_clicks": 0,
                "baseline_ctr": 0.0,
                "baseline_source": "GSC_EMPIRICAL_ROLLUP",
                "rolled_back_title_rewrite": "Texas Section 1031 Exchange Calculator (Form 8824) | ProfitHelm",
            }
        ),
        encoding="utf-8",
    )

    eval_res = evaluate_expired_overlays(
        site_url="sc-domain:profithelm.com",
        base_dir=repo_root,
        live_queries=[
            {
                "query": "utah 2027 tax brackets",
                "canonical_path": "/tools/irs-2027-tax-brackets/utah",
                "impressions": 18,
                "clicks": 0,
                "ctr": 0.0,
                "position": 85.0,
            },
            {
                "query": "texas section 1031 exchange",
                "canonical_path": "/tools/section-1031-calculator/texas",
                "impressions": 25,
                "clicks": 1,
                "ctr": 0.04,
                "position": 11.5,
            },
        ],
        persist=True,
    )

    rb_slugs = {item["slug"] for item in eval_res["degraded_rolled_back"]}
    mon_slugs = {item["slug"] for item in eval_res["monitoring"]}
    assert "irs-2027-tax-brackets/utah" in rb_slugs
    assert "section-1031-calculator/texas" in mon_slugs

    utah_after = json.loads((overlays_dir / "irs-2027-tax-brackets-utah.json").read_text(encoding="utf-8"))
    assert utah_after["status"] == "DEGRADED_ROLLED_BACK"

    tx_after = json.loads((overlays_dir / "section-1031-calculator-texas.json").read_text(encoding="utf-8"))
    assert tx_after["status"] == "ACTIVE_LOCKED"
    assert tx_after.get("quick_answer")
    assert tx_after.get("preset_scenarios")
    assert tx_after.get("h2_headings")
    assert tx_after.get("faq_entries")
    tx_html_after = (tx_dir / "index.html").read_text(encoding="utf-8")
    assert 'id="gsc-striking-overlay"' in tx_html_after


def test_quantitative_revenue_forecast_and_competitive_incumbent_upgrades(tmp_path: Path) -> None:
    """
    Verifies:
      1. Quantitative revenue forecast separates qualified commercial queries from vanity
         retail queries ('cadillac escalade for sale', 'taxi driver'), joins URL inspection
         states and partner EPC readiness, and enforces $0.00 commercial revenue on Prexvo
         restricted public-service YMYL calculators.
      2. Live SERP competitive incumbent profiles and bespoke vs systemic upgrade trade-offs
         expose all 5 required dissection dimensions and rejected cosmetic changes.
      3. RetroReflectionEngine heals robotic titles ('Model Tool Guide'), duplicate H1 years,
         defective meta descriptions ('Calculate X Calculator', 'Break under', 'clawb.'),
         injects Dataset + HowTo JSON-LD into @graph blocks missing them, adds rel=nofollow
         to .scenario-preset-link anchors, and expands Prexvo refinance internal links.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.competitor import (
        COMPETITIVE_INCUMBENT_PROFILES,
        REJECTED_COSMETIC_CHANGES,
        evaluate_bespoke_vs_systemic_upgrades,
        get_competitive_incumbent_profile,
    )
    from pseofactory.indexer import PushIndexer
    from pseofactory.maintenance import RetroReflectionEngine
    from pseofactory.seo_growth_loops import (
        compile_quantitative_revenue_forecast,
        is_vanity_or_off_intent_query,
    )

    assert is_vanity_or_off_intent_query("cadillac escalade for sale", slug="section-179-calculator/cadillac-escalade") is True
    assert is_vanity_or_off_intent_query("chevy tahoe deals near me", slug="section-179-calculator/chevy-tahoe") is True
    assert is_vanity_or_off_intent_query("taxi driver", slug="irs-2027-tax-brackets/california") is True
    assert is_vanity_or_off_intent_query("section 1031 exchange calculator", slug="section-1031-calculator") is False
    assert is_vanity_or_off_intent_query("ford f250 section 179 deduction", slug="section-179-calculator/ford-super-duty-f250") is False

    # Verify competitive incumbent profiles and trade-off evaluation
    assert len(COMPETITIVE_INCUMBENT_PROFILES) >= 7
    assert len(REJECTED_COSMETIC_CHANGES) >= 3
    prof_1031 = get_competitive_incumbent_profile("section-1031-calculator")
    assert any("ipx1031.com" in u for u in prof_1031["incumbent_urls"])
    for dim in ("calculator_interactivity", "visual_hierarchy", "content_effort", "trust_signals", "seo_structure"):
        assert dim in prof_1031

    eval_ph = evaluate_bespoke_vs_systemic_upgrades(property_id="profithelm")
    assert eval_ph["incumbent_profiles_count"] >= 4
    assert len(eval_ph["upgrade_tradeoff_matrix"]) >= 4

    # Build ProfitHelm revenue forecast fixture with commercial vs vanity queries
    ph_root = _seed_tenant_fixture(tmp_path / "ph_forecast_tenant")
    escalade_dir = ph_root / "dist" / "tools" / "section-179-calculator" / "cadillac-escalade"
    escalade_dir.mkdir(parents=True, exist_ok=True)
    (escalade_dir / "index.html").write_text(
        "<html><head><title>Cadillac Escalade Section 179 Calculator | ProfitHelm</title></head>"
        "<body><main><h1>Cadillac Escalade Section 179 Calculator</h1></main></body></html>",
        encoding="utf-8",
    )
    scorp_dir = ph_root / "dist" / "tools" / "s-corp-reasonable-salary-tax-calculator"
    scorp_dir.mkdir(parents=True, exist_ok=True)
    (scorp_dir / "index.html").write_text(
        '<!DOCTYPE html><html><head>'
        '<title>S-Corp Reasonable Salary Tax Calculator Model Tool Guide | ProfitHelm</title>'
        '<meta name="description" content="Calculate S-Corp Reasonable Salary Tax Calculator">'
        '<link rel="canonical" href="https://profithelm.com/tools/s-corp-reasonable-salary-tax-calculator/">'
        '<script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"WebPage","name":"S-Corp"},{"@type":"SoftwareApplication","name":"S-Corp","offers":{"@type":"Offer","price":"0","priceCurrency":"USD"}}]}</script>'
        '</head><body><main>'
        '<h1>IRS 2027 S-Corp Reasonable Salary Tax Calculator 2027</h1>'
        '<a href="?gross_amount=80000&amp;effective_rate=0.19" data-preset="baseline" class="touch-target scenario-preset-link">Baseline</a>'
        '</main></body></html>',
        encoding="utf-8",
    )

    # Verify RetroReflectionEngine heals title, H1, meta description, Dataset/HowTo schema, and nofollow preset links
    healed_html, repaired = RetroReflectionEngine.retrofit_html(
        (scorp_dir / "index.html").read_text(encoding="utf-8"),
        property_id="profithelm",
        slug="s-corp-reasonable-salary-tax-calculator",
        dist_dir=ph_root / "dist",
    )
    (scorp_dir / "index.html").write_text(healed_html, encoding="utf-8")
    assert "Model Tool" not in healed_html
    assert "Tool Guide" not in healed_html
    assert "Calculate S-Corp Reasonable Salary Tax Calculator" not in healed_html
    assert 'rel="nofollow" class="touch-target scenario-preset-link"' in healed_html
    assert '"@type": "Dataset"' in healed_html
    assert '"@type": "HowTo"' in healed_html

    ph_forecast = compile_quantitative_revenue_forecast(
        property_id="profithelm",
        repo_root=ph_root,
        dist_dir=ph_root / "dist",
        consolidated_gsc={
            "current_rows": [
                {
                    "query": "cadillac escalade for sale",
                    "page": "https://profithelm.com/tools/section-179-calculator/cadillac-escalade/",
                    "impressions": 450,
                    "clicks": 0,
                    "position": 54.0,
                },
                {
                    "query": "section 1031 exchange calculator",
                    "page": "https://profithelm.com/tools/section-1031-calculator/",
                    "impressions": 110,
                    "clicks": 2,
                    "position": 9.2,
                },
                {
                    "query": "s corp reasonable salary calculator",
                    "page": "https://profithelm.com/tools/s-corp-reasonable-salary-tax-calculator/",
                    "impressions": 65,
                    "clicks": 1,
                    "position": 11.4,
                },
            ]
        },
        persist=True,
    )
    assert (ph_root / ".agy" / "quantitative_revenue_forecast.json").is_file()
    assert (ph_root / ".agy" / "competitive_incumbent_profiles.json").is_file()
    by_slug = {a["slug"]: a for a in ph_forecast["ranked_assets"]}
    assert by_slug["section-179-calculator/cadillac-escalade"]["vanity_impressions"] == 450
    assert by_slug["section-179-calculator/cadillac-escalade"]["qualified_commercial_impressions"] == 0
    assert (
        by_slug["s-corp-reasonable-salary-tax-calculator"]["monetization_rank"]
        < by_slug["section-179-calculator/cadillac-escalade"]["monetization_rank"]
    )

    # Verify PushIndexer prioritizes top revenue-forecasted URLs ahead of alphabetical spokes
    indexer = PushIndexer(domain="profithelm.com", dist_dir=ph_root / "dist")
    candidate_urls = [
        "https://profithelm.com/tools/irs-2027-tax-brackets/alabama/",
        "https://profithelm.com/tools/s-corp-reasonable-salary-tax-calculator/",
        "https://profithelm.com/tools/section-1031-calculator/",
    ]
    prioritized = indexer.prioritize_urls_for_indexing_allocation(candidate_urls)
    assert prioritized[-1] == "https://profithelm.com/tools/irs-2027-tax-brackets/alabama/"

    # Verify Prexvo YMYL zero-commercial enforcement and refinance break-even ranking
    px_root = tmp_path / "px_forecast_tenant"
    for px_slug in ("pslf-qualifying-payment-simulator", "student-loan-refinance-break-even-calculator"):
        d_p = px_root / "dist" / "tools" / px_slug
        d_p.mkdir(parents=True, exist_ok=True)
        (d_p / "index.html").write_text(
            f"<html><head><title>{px_slug} | Prexvo</title></head><body><main><h1>{px_slug}</h1></main></body></html>",
            encoding="utf-8",
        )
    px_forecast = compile_quantitative_revenue_forecast(
        property_id="prexvo",
        repo_root=px_root,
        dist_dir=px_root / "dist",
        consolidated_gsc={
            "current_rows": [
                {
                    "query": "pslf qualifying payment calculator",
                    "page": "https://prexvo.com/tools/pslf-qualifying-payment-simulator/",
                    "impressions": 220,
                    "clicks": 3,
                    "position": 8.5,
                },
                {
                    "query": "student loan refinance break even calculator",
                    "page": "https://prexvo.com/tools/student-loan-refinance-break-even-calculator/",
                    "impressions": 40,
                    "clicks": 1,
                    "position": 12.0,
                },
            ]
        },
        persist=True,
    )
    px_by_slug = {a["slug"]: a for a in px_forecast["ranked_assets"]}
    assert px_by_slug["pslf-qualifying-payment-simulator"]["partner_epc_readiness"]["restricted_public_service"] is True
    assert px_by_slug["pslf-qualifying-payment-simulator"]["partner_epc_readiness"]["effective_epc_usd"] == 0.0
    assert px_by_slug["pslf-qualifying-payment-simulator"]["forecasted_90d_revenue_usd"] == 0.0
    assert px_by_slug["student-loan-refinance-break-even-calculator"]["forecasted_90d_revenue_usd"] > 0.0
    assert (
        px_by_slug["student-loan-refinance-break-even-calculator"]["monetization_rank"]
        < px_by_slug["pslf-qualifying-payment-simulator"]["monetization_rank"]
    )


def test_zero_income_tax_state_spoke_reangling_and_portfolio_unfreeze(tmp_path: Path) -> None:
    """
    Verifies that the 8 zero-income-tax state spokes (Alaska, Florida, Nevada, South Dakota,
    Tennessee, Texas, Washington, Wyoming) are re-angled toward 0% state income tax + federal
    IRC Section 1(j) take-home pay with 50-60 char titles, 120-155 char meta descriptions,
    and 40-60 word 2-sentence quick answers using each state's exact SSR Census median income,
    while evaluate_content_portfolio_decisions exempts re-angled zero-tax spokes from the
    zero-impression prune queue and unfreezes cluster expansion above the 55.0% threshold.
    """
    from pseofactory.contracts import count_quick_answer_sentences
    from pseofactory.gsc_remediation import (
        ZERO_INCOME_TAX_STATES,
        build_zero_tax_state_spoke_copy,
    )
    from pseofactory.maintenance import RetroReflectionEngine

    assert len(ZERO_INCOME_TAX_STATES) == 8
    for st in ZERO_INCOME_TAX_STATES:
        cp = build_zero_tax_state_spoke_copy(
            st,
            inc_val="$73,035",
            tot_val="$10,539",
            eff_val="14.4%",
            th_val="$62,496",
        )
        assert 50 <= len(cp["title"]) <= 60
        assert "0% State" in cp["title"]
        assert cp["title"].endswith("| ProfitHelm")
        assert 120 <= len(cp["meta_description"]) <= 155
        assert "0% state income tax" in cp["meta_description"]
        assert "IRC Section 1(j)" in cp["meta_description"]
        qa_words = len(cp["quick_answer"].split())
        assert 40 <= qa_words <= 60
        assert 1 <= count_quick_answer_sentences(cp["quick_answer"]) <= 2
        assert "0% state individual income tax" in cp["quick_answer"]

    # Verify RetroReflectionEngine.retrofit_html extracts id="tax-income" and re-angles zero-tax state HTML
    tx_raw = (
        '<!DOCTYPE html><html lang="en"><head>'
        "<title>Texas 2027 Tax Brackets (2026 Brackets) | ProfitHelm</title>"
        '<meta name="description" content="Calculate Texas 2026-2027 state and federal tax brackets.">'
        '<meta property="og:title" content="Texas 2027 Tax Brackets">'
        '<meta property="og:description" content="Calculate Texas 2026-2027 state and federal tax brackets.">'
        '<meta name="twitter:title" content="Texas 2027 Tax Brackets">'
        '<meta name="twitter:description" content="Calculate Texas 2026-2027 state and federal tax brackets.">'
        '<link rel="canonical" href="https://profithelm.com/tools/irs-2027-tax-brackets/texas/">'
        "</head><body><main>"
        "<h1>Texas 2027 Tax Brackets &amp; Calculator</h1>"
        '<p class="hero-subtitle">Interactive 2026-2027 federal and Texas statutory tax bracket calculator.</p>'
        '<aside class="quick-answer"><div class="quick-answer-title">Key Finding</div>'
        '<div class="quick-answer-body"><p>Old generic quick answer.</p></div></aside>'
        '<input id="tax-income" value="73035">'
        '<div id="res-total-tax">$10,539</div>'
        '<div id="res-effective-rate">14.4%</div>'
        '<div id="res-take-home">$62,496</div>'
        "</main></body></html>"
    )
    tx_retro, _ = RetroReflectionEngine.retrofit_html(
        tx_raw,
        property_id="profithelm",
        slug="irs-2027-tax-brackets/texas",
    )
    assert "<title>Texas 2027 Tax Calculator (0% State Tax) | ProfitHelm</title>" in tx_retro
    assert "0% state individual income tax ($0 state tax)" in tx_retro
    assert "$73,035 median wage benchmark" in tx_retro

    # Seed a portfolio with 8 re-angled zero-tax state spokes + 2 low-demand income-tax spokes
    repo_root = tmp_path / "profithelm_zt"
    old_ts = (datetime.now(timezone.utc) - timedelta(days=90)).timestamp()
    for st in ZERO_INCOME_TAX_STATES:
        st_dir = repo_root / "dist" / "tools" / "irs-2027-tax-brackets" / st
        st_dir.mkdir(parents=True, exist_ok=True)
        hf = st_dir / "index.html"
        hf.write_text(tx_retro.replace("/texas/", f"/{st}/"), encoding="utf-8")
        os.utime(hf, (old_ts, old_ts))

    for low_st in ("alabama", "wyoming-non-reangled"):
        st_dir = repo_root / "dist" / "tools" / "irs-2027-tax-brackets" / low_st
        st_dir.mkdir(parents=True, exist_ok=True)
        hf = st_dir / "index.html"
        hf.write_text(
            f"<html><head><title>{low_st.title()} 2027 Tax Brackets | ProfitHelm</title></head>"
            f"<body><main><h1>{low_st.title()} 2027 Tax Brackets</h1></main></body></html>",
            encoding="utf-8",
        )
        os.utime(hf, (old_ts, old_ts))

    port_rep = evaluate_content_portfolio_decisions(
        property_id="profithelm",
        repo_root=repo_root,
        dist_dir=repo_root / "dist",
        consolidated_gsc={
            "current_rows": [
                {
                    "query": "tax brackets in texas",
                    "canonical_path": "/tools/irs-2027-tax-brackets/texas",
                    "impressions": 4,
                    "clicks": 0,
                    "position": 6.0,
                }
            ],
            "impressions_by_path": {"/tools/irs-2027-tax-brackets/texas": 4},
            "clicks_by_path": {},
        },
        max_age_days=30.0,
        persist=True,
    )
    assert port_rep["zero_tax_reangled_spokes_count"] == 8
    assert port_rep["flagged_count"] == 2
    assert port_rep["pre_consolidation_indexed_coverage_pct"] == 80.0
    assert port_rep["post_consolidation_indexed_coverage_pct"] == 100.0
    assert port_rep["cluster_expansion_frozen"] is False
    by_path = {d["url_path"]: d for d in port_rep["decisions"]}
    for st in ZERO_INCOME_TAX_STATES:
        assert by_path[f"/tools/irs-2027-tax-brackets/{st}"]["portfolio_action"] == "OPTIMIZE_STRIKING_DISTANCE"
        assert by_path[f"/tools/irs-2027-tax-brackets/{st}"]["decision"] == "REANGLE_ZERO_TAX_FEDERAL_TAKE_HOME"
    assert by_path["/tools/irs-2027-tax-brackets/alabama"]["portfolio_action"] == "PRUNE_NOINDEX"


def test_zero_click_crawl_budget_triage_404_noindex_and_schema_breadcrumb_hierarchy(tmp_path: Path) -> None:
    """
    Verifies the crawl-budget & zero-click indexed URL triage upgrades (x-like:2109684114173641151):
      1. evaluate_content_portfolio_decisions excludes 404.html, /signal, and noindex utility pages,
         triages aged zero-click deep-rank pages (impressions > 0, clicks == 0, pos > 30, age >= max_age)
         into REANGLE_OR_CONSOLIDATE_HUB under zero_click_triage, and computes ctr_position_dilution_diagnostics.
      2. RetroReflectionEngine.retrofit_html heals 404.html 'index, follow' to 'noindex, follow',
         upgrades 3-item nested spoke BreadcrumbList to 4-item (Home -> Tools -> Parent Hub -> Spoke),
         and injects /tools/parent-plus-double-consolidation-loophole-2026-calculator/ into Prexvo's
         id='topic-cluster-hub'.
      3. compile_high_effort_page emits unified @graph JSON-LD with Organization, WebPage, WebApplication,
         Dataset, HowTo, FAQPage, and 4-item BreadcrumbList on nested spokes.
      4. PushIndexer.prioritize_urls_for_indexing_allocation promotes high-impression zero-click striking-distance
         rescue pages to Tier 1 and demotes aged zero-click deep-rank bleeders and prune-queued URLs to Tier 7.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.compiler import compile_high_effort_page
    from pseofactory.indexer import PushIndexer
    from pseofactory.maintenance import RetroReflectionEngine

    repo_root = tmp_path / "profithelm_cb"
    dist_dir = repo_root / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    old_ts = (datetime.now(timezone.utc) - timedelta(days=120)).timestamp()

    # Non-indexable utility routes that must be excluded from pages_audited
    (dist_dir / "404.html").write_text(
        '<!DOCTYPE html><html><head><title>404 Not Found | ProfitHelm</title>'
        '<meta name="robots" content="index, follow, max-snippet:-1">'
        '<link rel="canonical" href="https://profithelm.com/404.html">'
        '</head><body><main><h1>404</h1></main></body></html>',
        encoding="utf-8",
    )
    sig_dir = dist_dir / "signal"
    sig_dir.mkdir(parents=True, exist_ok=True)
    (sig_dir / "index.html").write_text("<html><head><title>Signal</title></head><body></body></html>", encoding="utf-8")

    # 1. Striking-distance zero-click CTR rescue page (pos 8.5, 25 impr, 0 clicks)
    rescue_dir = dist_dir / "tools" / "section-1031-calculator"
    rescue_dir.mkdir(parents=True, exist_ok=True)
    rescue_hf = rescue_dir / "index.html"
    rescue_hf.write_text(
        "<html><head><title>Section 1031 Calculator | ProfitHelm</title></head>"
        "<body><main><h1>Section 1031 Calculator</h1></main></body></html>",
        encoding="utf-8",
    )
    os.utime(rescue_hf, (old_ts, old_ts))

    # 2. Aged deep-rank zero-click bleeder (pos 75.0, 3 impr, 0 clicks, age 120d)
    bleeder_dir = dist_dir / "tools" / "irs-2027-tax-brackets" / "arizona"
    bleeder_dir.mkdir(parents=True, exist_ok=True)
    bleeder_hf = bleeder_dir / "index.html"
    bleeder_hf.write_text(
        '<!DOCTYPE html><html><head><title>Arizona 2027 Tax Brackets | ProfitHelm</title>'
        '<link rel="canonical" href="https://profithelm.com/tools/irs-2027-tax-brackets/arizona/">'
        '<script type="application/ld+json">{"@context":"https://schema.org","@graph":['
        '{"@type":"WebPage","name":"Arizona"},'
        '{"@type":"Dataset","name":"Arizona Dataset"},'
        '{"@type":"HowTo","name":"Arizona HowTo"},'
        '{"@type":"BreadcrumbList","itemListElement":['
        '{"@type":"ListItem","position":1,"name":"Home","item":"https://profithelm.com/"},'
        '{"@type":"ListItem","position":2,"name":"IRS 2027 Tax Brackets","item":"https://profithelm.com/tools/irs-2027-tax-brackets/"},'
        '{"@type":"ListItem","position":3,"name":"Arizona","item":"https://profithelm.com/tools/irs-2027-tax-brackets/arizona/"}'
        ']}]}</script>'
        "</head><body><main><h1>Arizona 2027 Tax Brackets</h1></main></body></html>",
        encoding="utf-8",
    )
    os.utime(bleeder_hf, (old_ts, old_ts))

    # 3. Aged zero-impression prune candidate (0 impr, 0 clicks, age 120d)
    prune_dir = dist_dir / "tools" / "section-179-calculator" / "low-demand-spoke"
    prune_dir.mkdir(parents=True, exist_ok=True)
    prune_hf = prune_dir / "index.html"
    prune_hf.write_text(
        "<html><head><title>Low Demand Spoke | ProfitHelm</title></head>"
        "<body><main><h1>Low Demand Spoke</h1></main></body></html>",
        encoding="utf-8",
    )
    os.utime(prune_hf, (old_ts, old_ts))

    gsc_bundle = {
        "current_rows": [
            {
                "query": "section 1031 exchange calculator",
                "canonical_path": "/tools/section-1031-calculator",
                "impressions": 25,
                "clicks": 0,
                "position": 8.5,
            },
            {
                "query": "arizona 2027 tax brackets",
                "canonical_path": "/tools/irs-2027-tax-brackets/arizona",
                "impressions": 3,
                "clicks": 0,
                "position": 75.0,
            },
        ],
        "baseline_rows": [
            {
                "query": "section 1031 exchange calculator",
                "canonical_path": "/tools/section-1031-calculator",
                "impressions": 15,
                "clicks": 1,
                "position": 7.0,
            },
        ],
        "impressions_by_path": {
            "/tools/section-1031-calculator": 25,
            "/tools/irs-2027-tax-brackets/arizona": 3,
        },
        "clicks_by_path": {
            "/tools/section-1031-calculator": 0,
            "/tools/irs-2027-tax-brackets/arizona": 0,
        },
    }

    port_rep = evaluate_content_portfolio_decisions(
        property_id="profithelm",
        repo_root=repo_root,
        dist_dir=dist_dir,
        consolidated_gsc=gsc_bundle,
        max_age_days=90.0,
        persist=True,
    )
    assert port_rep["pages_audited"] == 3
    triage_sum = port_rep["zero_click_indexed_triage_summary"]
    assert triage_sum["zero_click_indexed_routes_count"] == 2
    assert triage_sum["striking_distance_ctr_rescue_count"] == 1
    assert triage_sum["aged_deep_rank_bleeders_count"] == 1
    assert triage_sum["aged_zero_impression_prune_count"] == 1
    assert triage_sum["aged_deep_rank_bleeder_candidates"][0]["url_path"] == "/tools/irs-2027-tax-brackets/arizona"
    assert (
        triage_sum["aged_deep_rank_bleeder_candidates"][0]["recommended_consolidation_target"]
        == "/tools/irs-2027-tax-brackets/"
    )

    dilution = port_rep["ctr_position_dilution_diagnostics"]
    assert dilution["current_impressions"] == 28
    assert dilution["baseline_impressions"] == 15
    assert dilution["ctr_dilution_detected"] is True
    assert dilution["position_dilution_detected"] is True

    # Verify RetroReflectionEngine heals 404.html robots and upgrades 3-item spoke BreadcrumbList to 4-item
    healed_404, changed_404 = RetroReflectionEngine.retrofit_html(
        (dist_dir / "404.html").read_text(encoding="utf-8"),
        property_id="profithelm",
        slug="404",
        dist_dir=dist_dir,
    )
    assert bool(changed_404)
    assert '<meta name="robots" content="noindex, follow">' in healed_404

    healed_az, changed_az = RetroReflectionEngine.retrofit_html(
        bleeder_hf.read_text(encoding="utf-8"),
        property_id="profithelm",
        slug="irs-2027-tax-brackets/arizona",
        dist_dir=dist_dir,
    )
    assert bool(changed_az)
    assert '"https://profithelm.com/tools/"' in healed_az
    assert '"position": 4' in healed_az

    # Verify Prexvo topic-cluster-hub gets parent-plus-double-consolidation-loophole-2026-calculator injected
    px_html_raw = (
        '<!DOCTYPE html><html><head><title>SAVE Plan Forbearance Interest Calculator | Prexvo</title>'
        '<link rel="canonical" href="https://prexvo.com/tools/save-plan-forbearance-interest-calculator/">'
        '</head><body><main><h1>SAVE Plan Forbearance Interest Calculator</h1>'
        '<section id="topic-cluster-hub"><ul>'
        '<li><a href="https://prexvo.com/tools/pslf-qualifying-payment-simulator/">PSLF</a></li>'
        '</ul></section></main></body></html>'
    )
    healed_px, changed_px = RetroReflectionEngine.retrofit_html(
        px_html_raw,
        property_id="prexvo",
        slug="save-plan-forbearance-interest-calculator",
    )
    assert bool(changed_px)
    assert "/tools/parent-plus-double-consolidation-loophole-2026-calculator/" in healed_px

    # Verify compile_high_effort_page emits @graph with Dataset, HowTo, and 4-item BreadcrumbList on nested spokes
    compiled_spoke_res = compile_high_effort_page(
        {
            "query": "arizona 2027 tax brackets calculator",
            "slug": "irs-2027-tax-brackets/arizona",
            "title": "Arizona 2027 Tax Brackets & Calculator",
            "model_name": "Arizona Statutory Tax Bracket Model",
            "formula": "gross_amount * effective_rate",
            "inputs": {"gross_amount": 85000.0, "effective_rate": 0.165},
            "sample_calculation": "85000.0 * 0.165 = 14025.00",
            "statutory_authority": "26 U.S.C. Section 1(j); IRS Rev. Proc. 2025-32",
            "economic_dataset": "BLS CPI-U CUUR0000SA0; FRED M2SL",
        }
    )
    compiled_spoke = compiled_spoke_res["html"]
    assert '"@graph"' in compiled_spoke
    assert '"@type": "Dataset"' in compiled_spoke
    assert '"@type": "HowTo"' in compiled_spoke
    assert '"@type": "BreadcrumbList"' in compiled_spoke
    assert '"https://profithelm.com/tools/irs-2027-tax-brackets/"' in compiled_spoke

    # Verify PushIndexer promotes striking-distance rescue URL to Tier 1 and demotes bleeders/prune candidates to Tier 7
    indexer = PushIndexer(domain="profithelm.com", dist_dir=dist_dir)
    sorted_urls = indexer.prioritize_urls_for_indexing_allocation(
        [
            "https://profithelm.com/tools/irs-2027-tax-brackets/arizona/",
            "https://profithelm.com/tools/section-179-calculator/low-demand-spoke/",
            "https://profithelm.com/tools/s-corp-reasonable-salary-tax-calculator/",
            "https://profithelm.com/tools/section-1031-calculator/",
        ]
    )
    assert sorted_urls[0] == "https://profithelm.com/tools/section-1031-calculator/"
    assert sorted_urls[1] == "https://profithelm.com/tools/s-corp-reasonable-salary-tax-calculator/"
    assert set(sorted_urls[2:]) == {
        "https://profithelm.com/tools/irs-2027-tax-brackets/arizona/",
        "https://profithelm.com/tools/section-179-calculator/low-demand-spoke/",
    }







