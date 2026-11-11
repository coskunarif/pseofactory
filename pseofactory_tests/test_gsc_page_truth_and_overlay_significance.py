"""
Falsification and regression tests for Google Search Console page-level truth
(-d page and -d page -d device), 301-source decay isolation vs total portfolio rollup,
statistical floor (MIN_EMPIRICAL_EVAL_IMPRESSIONS = 15), and self-healing recovery of
erroneously rolled-back overlays across active and expired lock windows.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest

import pseofactory.seo_growth_loops as seo_growth_loops
import pseofactory.trends.models as trend_models
from pseofactory.contracts import assert_no_forbidden_dashes
from pseofactory.gsc_remediation import (
    evaluate_expired_overlays,
    inject_overlay_into_html,
    rollback_degraded_overlay_from_html,
)
from pseofactory.seo_growth_loops import (
    compile_quantitative_revenue_forecast,
    discover_internal_linking_opportunities,
    evaluate_closed_loop_cohort_reflection,
    evaluate_content_portfolio_decisions,
    harvest_and_sync_gsc_multidimensional_telemetry,
    load_consolidated_gsc_query_rows,
    monitor_post_release_seo_regressions,
)
from pseofactory.trends.collectors import GSCSearchConsoleCollector
from pseofactory.trends.db import TrendHistoryDB
from pseofactory.trends.models import GSCQueryPageWindowRecord
from pseofactory.verifier import verify_gsc_lifecycle_telemetry_contract


def test_trend_history_db_page_windows_isolated_from_query_spike_harvest(tmp_path: Path) -> None:
    """
    Verifies dedicated gsc_page_windows CRUD in TrendHistoryDB across recent_28d,
    prior_28d_baseline, and recent_90d, and ensures empty-query rows never enter
    gsc_query_page_windows or pollute GSCSearchConsoleCollector.harvest_gsc_spikes().
    """
    page_rec_cls = getattr(trend_models, "GSCPageWindowRecord", None)
    assert page_rec_cls is not None, "Expected GSCPageWindowRecord in pseofactory.trends.models"

    db_file = tmp_path / "trend_history.db"
    with TrendHistoryDB(db_file) as db:
        upsert_fn = getattr(db, "upsert_gsc_page_windows", None)
        get_fn = getattr(db, "get_gsc_page_windows", None)
        assert callable(upsert_fn) and callable(get_fn), "Expected page window CRUD on TrendHistoryDB"

        inserted = upsert_fn(
            [
                page_rec_cls(
                    property_id="profithelm",
                    window_key="recent_28d",
                    page="https://profithelm.com/tools/irs-2027-tax-brackets/california/",
                    clicks=9,
                    impressions=190,
                    ctr=0.0474,
                    position=10.32,
                ),
                page_rec_cls(
                    property_id="profithelm",
                    window_key="prior_28d_baseline",
                    page="https://profithelm.com/tools/irs-2027-tax-brackets/california/",
                    clicks=21,
                    impressions=254,
                    ctr=0.0827,
                    position=9.57,
                ),
                page_rec_cls(
                    property_id="profithelm",
                    window_key="recent_90d",
                    page="https://profithelm.com/tools/irs-2027-tax-brackets/california/",
                    clicks=38,
                    impressions=610,
                    ctr=0.0623,
                    position=9.88,
                ),
            ]
        )
        assert inserted == 3
        assert len(get_fn("profithelm", window_key="recent_28d")) == 1
        assert len(get_fn("profithelm", window_key="prior_28d_baseline")) == 1
        assert len(get_fn("profithelm", window_key="recent_90d")) == 1

        # Verify replace_window=True replaces only the targeted window_key
        upsert_fn(
            [
                page_rec_cls(
                    property_id="profithelm",
                    window_key="recent_28d",
                    page="https://profithelm.com/tools/section-179-calculator/",
                    clicks=14,
                    impressions=210,
                    ctr=0.0667,
                    position=6.4,
                )
            ],
            replace_window=True,
        )
        r28_rows = get_fn("profithelm", window_key="recent_28d")
        assert [r.page for r in r28_rows] == ["https://profithelm.com/tools/section-179-calculator/"]
        assert len(get_fn("profithelm", window_key="prior_28d_baseline")) == 1
        assert len(get_fn("profithelm", window_key="recent_90d")) == 1

        # Empty-query rows must never enter gsc_query_page_windows
        empty_qp_count = db.upsert_gsc_query_page_windows(
            [
                GSCQueryPageWindowRecord(
                    property_id="profithelm",
                    window_key="recent_28d",
                    query="",
                    page="https://profithelm.com/tools/section-179-calculator/",
                    clicks=14,
                    impressions=210,
                    ctr=0.0667,
                    position=6.4,
                ),
                GSCQueryPageWindowRecord(
                    property_id="profithelm",
                    window_key="recent_28d",
                    query="section 179 deduction calculator",
                    page="https://profithelm.com/tools/section-179-calculator/",
                    clicks=2,
                    impressions=35,
                    ctr=0.0571,
                    position=7.1,
                ),
            ]
        )
        assert empty_qp_count == 1
        qp_rows = db.get_gsc_query_page_windows("profithelm", window_key="recent_28d")
        assert [r.query for r in qp_rows] == ["section 179 deduction calculator"]

    collector = GSCSearchConsoleCollector(db_path=db_file, properties=["profithelm"])
    spikes = collector.harvest_gsc_spikes()
    assert all(bool(s.query.strip()) for s in spikes)


def test_live_gsc_page_and_page_device_harvest_rescues_anonymized_pages_and_preserves_4arg_mock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Verifies that live multidimensional harvest:
      1. Preserves backwards compatibility with 4-argument _run_live_gsc_query_cli mocks.
      2. Queries ['page'] across recent_28d, prior_28d_baseline, and recent_90d, plus
         ['page', 'device'] across recent_90d without double-counting device impressions.
      3. Recovers 100% privacy-anonymized clicks, impressions, and positions in
         load_consolidated_gsc_query_rows, evaluate_content_portfolio_decisions,
         discover_internal_linking_opportunities, and compile_quantitative_revenue_forecast.
      4. Rolls spoke impressions up to parent hubs (/tools/<hub>) while keeping zero-traffic
         sibling spokes (/tools/<hub>/<spoke>) at 0 impressions so genuine dead spokes still prune.
    """
    repo_root = tmp_path / "profithelm-platform"
    dist_dir = repo_root / "dist"
    agy_dir = repo_root / ".agy"
    db_file = tmp_path / "trend_history.db"
    dist_dir.mkdir(parents=True, exist_ok=True)
    agy_dir.mkdir(parents=True, exist_ok=True)

    # Seed _redirects so legacy /calculators/bonus-depreciation rolls up into /tools/bonus-depreciation-calculator
    (dist_dir / "_redirects").write_text(
        "/calculators/bonus-depreciation /tools/bonus-depreciation-calculator/ 301\n",
        encoding="utf-8",
    )

    old_ts = (datetime.now(timezone.utc) - timedelta(days=95)).timestamp()
    pages_html = {
        "index.html": (
            "<html><head><title>ProfitHelm Tax Calculators</title></head>"
            "<body><main><a href='/tools/section-179-calculator/'>Section 179</a>"
            "<a href='/tools/irs-2027-tax-brackets/'>2027 Brackets</a></main></body></html>"
        ),
        "tools/section-179-calculator/index.html": (
            "<html><head><title>Section 179 Deduction Calculator | ProfitHelm</title>"
            "<script type='application/ld+json'>{\"datePublished\": \"2026-07-10\"}</script></head>"
            "<body><main><h1>Section 179 Deduction Calculator</h1></main></body></html>"
        ),
        # Anonymized Page-1 click earner (0 rows in query+page, 180 impr & 14 clicks at pos 6.4 in -d page)
        "tools/s-corp-tax-calculator/index.html": (
            "<html><head><title>S-Corp Tax Calculator | ProfitHelm</title>"
            "<script type='application/ld+json'>{\"datePublished\": \"2026-07-10\"}</script></head>"
            "<body><main><h1>S-Corp Tax Savings Calculator</h1></main></body></html>"
        ),
        # Anonymized striking-distance asset (0 rows in query+page, 42 impr & 0 clicks at pos 16.5 in -d page)
        "tools/crypto-tax-calculator/index.html": (
            "<html><head><title>Crypto Tax Calculator | ProfitHelm</title>"
            "<script type='application/ld+json'>{\"datePublished\": \"2026-07-10\"}</script></head>"
            "<body><main><h1>Crypto Capital Gains Tax Calculator</h1></main></body></html>"
        ),
        # Newly consolidated canonical receiving 301 traffic from /calculators/bonus-depreciation
        "tools/bonus-depreciation-calculator/index.html": (
            "<html><head><title>Bonus Depreciation Calculator | ProfitHelm</title>"
            "<script type='application/ld+json'>{\"datePublished\": \"2026-07-10\"}</script></head>"
            "<body><main><h1>Bonus Depreciation Calculator</h1></main></body></html>"
        ),
        # Parent hub + healthy spoke + zero-traffic sibling spoke
        "tools/irs-2027-tax-brackets/index.html": (
            "<html><head><title>IRS 2027 Tax Brackets | ProfitHelm</title>"
            "<script type='application/ld+json'>{\"datePublished\": \"2026-07-10\"}</script></head>"
            "<body><main><a href='/tools/irs-2027-tax-brackets/california/'>CA</a>"
            "<a href='/tools/irs-2027-tax-brackets/montana/'>MT</a></main></body></html>"
        ),
        "tools/irs-2027-tax-brackets/california/index.html": (
            "<html><head><title>California 2027 Tax Brackets | ProfitHelm</title>"
            "<script type='application/ld+json'>{\"datePublished\": \"2026-07-10\"}</script></head>"
            "<body><main><h1>California 2027 Tax Brackets</h1></main></body></html>"
        ),
        "tools/irs-2027-tax-brackets/montana/index.html": (
            "<html><head><title>Montana 2027 Tax Brackets | ProfitHelm</title>"
            "<script type='application/ld+json'>{\"datePublished\": \"2026-07-10\"}</script></head>"
            "<body><main><h1>Montana 2027 Tax Brackets</h1></main></body></html>"
        ),
    }
    for rel_p, body in pages_html.items():
        fp = dist_dir / rel_p
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(body, encoding="utf-8")
        if "r-d-tax-credits" not in rel_p:
            os.utime(fp, (old_ts, old_ts))

    recorded_calls: List[tuple] = []

    # Strictly 4 positional parameters (no row_limit) to guard mock signature compatibility!
    def fake_gsc_cli_4arg(
        site_uri: str, dimensions: List[str], start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
        dims_tuple = tuple(dimensions)
        recorded_calls.append((site_uri, dims_tuple, start_date, end_date))
        if dims_tuple == ("device",):
            return [
                {"keys": ["MOBILE"], "clicks": 22, "impressions": 360, "ctr": 0.0611, "position": 8.4},
                {"keys": ["DESKTOP"], "clicks": 16, "impressions": 240, "ctr": 0.0667, "position": 9.1},
            ]
        if dims_tuple == ("page", "device"):
            return [
                # s-corp has zero query+page+device rows due to GSC query privacy, but clear mobile CTR gap here
                {
                    "keys": ["https://profithelm.com/tools/s-corp-tax-calculator/", "MOBILE"],
                    "clicks": 2,
                    "impressions": 80,
                    "ctr": 0.025,
                    "position": 4.2,
                },
                {
                    "keys": ["https://profithelm.com/tools/s-corp-tax-calculator/", "DESKTOP"],
                    "clicks": 12,
                    "impressions": 100,
                    "ctr": 0.12,
                    "position": 5.8,
                },
                {
                    "keys": ["https://profithelm.com/tools/section-179-calculator/", "MOBILE"],
                    "clicks": 2,
                    "impressions": 30,
                    "ctr": 0.0667,
                    "position": 7.0,
                },
                {
                    "keys": ["https://profithelm.com/tools/section-179-calculator/", "DESKTOP"],
                    "clicks": 2,
                    "impressions": 20,
                    "ctr": 0.10,
                    "position": 7.4,
                },
            ]
        if dims_tuple == ("query", "page", "device"):
            # Only non-anonymized query subset appears here; must NOT double-count section-179-calculator!
            return [
                {
                    "keys": [
                        "section 179 deduction calculator",
                        "https://profithelm.com/tools/section-179-calculator/",
                        "MOBILE",
                    ],
                    "clicks": 1,
                    "impressions": 15,
                    "ctr": 0.0667,
                    "position": 6.8,
                },
                {
                    "keys": [
                        "section 179 deduction calculator",
                        "https://profithelm.com/tools/section-179-calculator/",
                        "DESKTOP",
                    ],
                    "clicks": 1,
                    "impressions": 10,
                    "ctr": 0.10,
                    "position": 7.5,
                },
            ]
        if dims_tuple == ("searchAppearance",):
            return [{"keys": ["PRODUCT_SNIPPETS"], "clicks": 3, "impressions": 40, "ctr": 0.075, "position": 7.2}]
        if dims_tuple == ("query", "page"):
            # Privacy-thresholded query+page returns ONLY section-179-calculator (missing 90% of traffic!)
            return [
                {
                    "keys": [
                        "section 179 deduction calculator",
                        "https://profithelm.com/tools/section-179-calculator/",
                    ],
                    "clicks": 4,
                    "impressions": 50,
                    "ctr": 0.08,
                    "position": 7.2,
                }
            ]
        if dims_tuple == ("page",):
            if start_date == "56daysAgo":
                return [
                    {
                        "keys": ["https://profithelm.com/tools/section-179-calculator/"],
                        "clicks": 3,
                        "impressions": 45,
                        "ctr": 0.0667,
                        "position": 7.5,
                    },
                    {
                        "keys": ["https://profithelm.com/tools/s-corp-tax-calculator/"],
                        "clicks": 11,
                        "impressions": 150,
                        "ctr": 0.0733,
                        "position": 6.9,
                    },
                    {
                        "keys": ["https://profithelm.com/tools/irs-2027-tax-brackets/california/"],
                        "clicks": 21,
                        "impressions": 254,
                        "ctr": 0.0827,
                        "position": 9.57,
                    },
                ]
            # recent_28d and recent_90d
            mult = 2 if start_date == "90daysAgo" else 1
            return [
                {
                    "keys": ["https://profithelm.com/tools/section-179-calculator/"],
                    "clicks": 4 * mult,
                    "impressions": 50 * mult,
                    "ctr": 0.08,
                    "position": 7.2,
                },
                {
                    "keys": ["https://profithelm.com/tools/s-corp-tax-calculator/"],
                    "clicks": 14 * mult,
                    "impressions": 180 * mult,
                    "ctr": 0.0778,
                    "position": 6.4,
                },
                {
                    "keys": ["https://profithelm.com/tools/crypto-tax-calculator/"],
                    "clicks": 0,
                    "impressions": 42 * mult,
                    "ctr": 0.0,
                    "position": 16.5,
                },
                {
                    "keys": ["https://profithelm.com/calculators/bonus-depreciation"],
                    "clicks": 3 * mult,
                    "impressions": 35 * mult,
                    "ctr": 0.0857,
                    "position": 8.8,
                },
                {
                    "keys": ["https://profithelm.com/tools/irs-2027-tax-brackets/california/"],
                    "clicks": 9 * mult,
                    "impressions": 190 * mult,
                    "ctr": 0.0474,
                    "position": 10.32,
                },
            ]
        return []

    monkeypatch.setattr(seo_growth_loops, "_run_live_gsc_query_cli", fake_gsc_cli_4arg)
    getattr(seo_growth_loops, "_LIVE_GSC_MULTIDIM_CACHE", {}).clear()
    getattr(seo_growth_loops, "_LIVE_GSC_CONSOLIDATED_CACHE", {}).clear()

    synced = harvest_and_sync_gsc_multidimensional_telemetry(
        property_id="profithelm",
        repo_root=repo_root,
        db_path=db_file,
        live_gsc=True,
        persist=True,
    )
    assert synced["status"] == "PASS"

    queried_dim_windows = {(dims, s_d, e_d) for _, dims, s_d, e_d in recorded_calls}
    assert (("page",), "28daysAgo", "today") in queried_dim_windows
    assert (("page",), "56daysAgo", "29daysAgo") in queried_dim_windows
    assert (("page",), "90daysAgo", "today") in queried_dim_windows
    assert (("page", "device"), "90daysAgo", "today") in queried_dim_windows

    contract_res = verify_gsc_lifecycle_telemetry_contract(repo_root, property_id="profithelm")
    assert contract_res["passed"] is True
    assert_no_forbidden_dashes(
        (agy_dir / "gsc_lifecycle_telemetry.json").read_text(encoding="utf-8"),
        context="gsc_lifecycle_telemetry.json",
    )

    # Verify -d page -d device surfaced s-corp MOBILE_CTR_DEFICIT without double-counting section-179
    p_dev = synced["page_device_diagnostics"]
    assert p_dev["/tools/s-corp-tax-calculator"]["device_focus"] == "MOBILE_CTR_DEFICIT"
    assert p_dev["/tools/section-179-calculator"]["mobile_impressions"] == 30
    assert p_dev["/tools/section-179-calculator"]["desktop_impressions"] == 20

    # Verify load_consolidated_gsc_query_rows merges -d page + 301 rollup while respecting spoke boundary
    consolidated = load_consolidated_gsc_query_rows(
        property_id="profithelm",
        repo_root=repo_root,
        live_gsc=True,
    )
    impr_by_path = consolidated["impressions_by_path"]
    clicks_by_path = consolidated["clicks_by_path"]

    assert impr_by_path["/tools/s-corp-tax-calculator"] == 360
    assert clicks_by_path["/tools/s-corp-tax-calculator"] == 28
    assert impr_by_path["/tools/crypto-tax-calculator"] == 84
    assert impr_by_path["/tools/bonus-depreciation-calculator"] == 70
    assert clicks_by_path["/tools/bonus-depreciation-calculator"] == 6
    # Parent hub inherits spoke traffic, while sibling spoke montana stays strictly at 0!
    assert impr_by_path["/tools/irs-2027-tax-brackets"] >= 380
    assert impr_by_path.get("/tools/irs-2027-tax-brackets/montana", 0) == 0

    # Verify portfolio decisions rescue anonymized Page-1 / striking-distance pages and prune ONLY montana
    port_rep = evaluate_content_portfolio_decisions(
        property_id="profithelm",
        repo_root=repo_root,
        dist_dir=dist_dir,
        consolidated_gsc=consolidated,
        max_age_days=60.0,
        persist=True,
    )
    decisions_by_path = {d["url_path"]: d for d in port_rep["decisions"]}
    assert decisions_by_path["/tools/s-corp-tax-calculator"]["portfolio_action"] == "SCALE_EXPAND"
    assert decisions_by_path["/tools/s-corp-tax-calculator"]["best_position"] == pytest.approx(6.4, abs=0.05)
    assert decisions_by_path["/tools/bonus-depreciation-calculator"]["portfolio_action"] == "SCALE_EXPAND"
    assert decisions_by_path["/tools/crypto-tax-calculator"]["portfolio_action"] == "OPTIMIZE_STRIKING_DISTANCE"
    assert decisions_by_path["/tools/irs-2027-tax-brackets/california"]["portfolio_action"] == "SCALE_EXPAND"
    assert decisions_by_path["/tools/irs-2027-tax-brackets"]["portfolio_action"] == "SCALE_EXPAND"
    assert decisions_by_path["/tools/irs-2027-tax-brackets/montana"]["portfolio_action"] == "PRUNE_NOINDEX"

    # Verify internal linking opportunities surface orphaned high-impression anonymized pages
    link_rep = discover_internal_linking_opportunities(
        property_id="profithelm",
        repo_root=repo_root,
        dist_dir=dist_dir,
        consolidated_gsc=consolidated,
        persist=True,
    )
    opp_by_target = {o["target_path"].rstrip("/"): o for o in link_rep["opportunities"]}
    assert "/tools/s-corp-tax-calculator" in opp_by_target
    assert opp_by_target["/tools/s-corp-tax-calculator"]["impressions"] >= 180

    # Verify quantitative revenue forecast incorporates -d page impressions rather than query-only sliver
    rev_rep = compile_quantitative_revenue_forecast(
        property_id="profithelm",
        repo_root=repo_root,
        dist_dir=dist_dir,
        consolidated_gsc=consolidated,
        multidim_telemetry=synced,
        link_report=link_rep,
        persist=True,
    )
    ranked_by_slug = {a["slug"]: a for a in rev_rep["ranked_assets"]}
    assert ranked_by_slug["s-corp-tax-calculator"]["raw_impressions"] >= 180
    assert ranked_by_slug["s-corp-tax-calculator"]["raw_clicks"] >= 14
    assert ranked_by_slug["s-corp-tax-calculator"]["qualified_commercial_impressions"] >= 180


def test_stale_telemetry_cache_without_page_windows_triggers_live_resync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Verifies that a fresh pre-fix .agy/gsc_lifecycle_telemetry.json lacking
    page_windows_by_path (or page_window_records_count) does NOT short-circuit
    when live_gsc=True, triggering a fresh live sync instead.
    """
    repo_root = tmp_path / "profithelm-platform"
    agy_dir = repo_root / ".agy"
    agy_dir.mkdir(parents=True, exist_ok=True)
    db_file = tmp_path / "trend_history.db"

    # Seed a fresh-mtime pre-fix telemetry JSON without page_windows_by_path
    stale_payload = {
        "status": "PASS",
        "property_id": "profithelm",
        "dimensions_synced": {
            "device_records_count": 2,
            "search_appearance_records_count": 1,
            "query_page_window_records_count": 1,
            "url_inspection_records_count": 0,
        },
        "property_device_summary": {},
        "page_device_diagnostics": {},
        "search_appearances": {},
        "time_window_velocity": {"page_window_velocity": {}, "query_page_deltas": {}},
        "url_inspection_summary": {"inspection_by_path": {}},
    }
    (agy_dir / "gsc_lifecycle_telemetry.json").write_text(
        json.dumps(stale_payload, indent=2), encoding="utf-8"
    )

    live_cli_invocations = 0

    def fake_live_cli(site_uri: str, dimensions: List[str], start_date: str, end_date: str) -> List[Dict[str, Any]]:
        nonlocal live_cli_invocations
        live_cli_invocations += 1
        if tuple(dimensions) == ("page",) and start_date == "28daysAgo":
            return [
                {
                    "keys": ["https://profithelm.com/tools/s-corp-tax-calculator/"],
                    "clicks": 10,
                    "impressions": 140,
                    "ctr": 0.0714,
                    "position": 6.8,
                }
            ]
        return []

    monkeypatch.setattr(seo_growth_loops, "_run_live_gsc_query_cli", fake_live_cli)
    getattr(seo_growth_loops, "_LIVE_GSC_MULTIDIM_CACHE", {}).clear()
    getattr(seo_growth_loops, "_LIVE_GSC_CONSOLIDATED_CACHE", {}).clear()

    resynced = harvest_and_sync_gsc_multidimensional_telemetry(
        property_id="profithelm",
        repo_root=repo_root,
        db_path=db_file,
        live_gsc=True,
        persist=True,
    )
    assert live_cli_invocations > 0, "Expected stale pre-fix telemetry cache to trigger live CLI resync"
    assert "page_windows_by_path" in resynced
    assert (
        resynced["page_windows_by_path"]["/tools/s-corp-tax-calculator"]["recent_28d"]["direct"]["impressions"]
        == 140
    )
    assert verify_gsc_lifecycle_telemetry_contract(repo_root, property_id="profithelm")["passed"] is True


def test_canonical_direct_vs_301_rolled_up_trajectory_and_holdout_isolation(tmp_path: Path) -> None:
    """
    Proves the core second-order SEO separation:
      1. Canonical URL /tools/irs-2027-tax-brackets/california/ holding steady in direct -d page
         (prior_28d: 254 impr, 21 clicks, pos 9.57 -> recent_28d: 190 impr, 9 clicks, pos 10.32)
         while 301-redirected legacy URLs drop to pos 44.38 (dragging rolled-up pos from 10.87
         to 30.16) MUST evaluate on CANONICAL_DIRECT_PAGE (+0.75 pos delta), stay ACTIVE_LOCKED
         across evaluate_expired_overlays, monitor_post_release_seo_regressions, and
         evaluate_closed_loop_cohort_reflection, while still retaining 455 rolled-up impressions
         in impressions_by_path for portfolio protection.
      2. Conversely, a newly consolidated canonical URL (/tools/newly-consolidated-calculator/)
         with 0 direct baseline impressions and >= 15 301-rolled-up baseline impressions (40 -> 6 impr,
         pos 7.5 -> 22.0) MUST fall back to 301-rolled-up -d page and trigger DEGRADED_ROLLED_BACK.
    """
    repo_root = tmp_path / "profithelm-platform"
    dist_dir = repo_root / "dist"
    agy_dir = repo_root / ".agy"
    overlays_dir = agy_dir / "overlays"
    runs_dir = tmp_path / "runs" / "run_20261101_test"
    db_file = tmp_path / "trend_history.db"
    for d in (dist_dir, overlays_dir, runs_dir):
        d.mkdir(parents=True, exist_ok=True)

    (dist_dir / "_redirects").write_text(
        "/calculators/ca-tax-brackets-2027 /tools/irs-2027-tax-brackets/california/ 301\n"
        "/calculators/old-consolidated-calc /tools/newly-consolidated-calculator/ 301\n",
        encoding="utf-8",
    )
    (runs_dir / "release_manifest.json").write_text(
        json.dumps(
            {
                "run_id": "run_20261101_test",
                "project": "profithelm",
                "timestamp": "2026-11-01T12:00:00Z",
                "head_sha": "deadbeef",
                "overall_status": "RELEASED",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    active_lock = "2099-12-31T00:00:00+00:00"

    # Case A: California brackets canonical page with healthy direct -d page but dying 301 source
    ca_dir = dist_dir / "tools" / "irs-2027-tax-brackets" / "california"
    ca_dir.mkdir(parents=True, exist_ok=True)
    ca_spec = {
        "slug": "irs-2027-tax-brackets/california",
        "query": "ca tax brackets 2027",
        "target_url": "https://profithelm.com/tools/irs-2027-tax-brackets/california/",
        "baseline_impressions": 65,
        "baseline_clicks": 2,
        "baseline_ctr": 0.0308,
        "baseline_position": 8.0,
        "locked_until": active_lock,
        "status": "ACTIVE_LOCKED",
        "title_rewrite": "California 2027 Tax Brackets Calculator (FTB Rates) | ProfitHelm",
        "secondary_title_modifier": "(FTB Rates)",
        "quick_answer": "Compute California marginal and effective income tax brackets.",
        "autonomous_citation_assertions": ["CA 1", "CA 2", "CA 3"],
    }
    (ca_dir / "index.html").write_text(
        inject_overlay_into_html(
            "<html><head><title>California 2027 Tax Brackets | ProfitHelm</title></head>"
            "<body><main><h1>California 2027 Tax Brackets</h1>"
            "<aside class='quick-answer'><p>Base</p></aside></main></body></html>",
            ca_spec,
        ),
        encoding="utf-8",
    )
    (overlays_dir / "irs-2027-tax-brackets-california.json").write_text(
        json.dumps(ca_spec, indent=2), encoding="utf-8"
    )

    # Case B: Newly consolidated canonical with 0 direct baseline impr and 40 rolled-up baseline impr
    nc_dir = dist_dir / "tools" / "newly-consolidated-calculator"
    nc_dir.mkdir(parents=True, exist_ok=True)
    nc_spec = {
        "slug": "newly-consolidated-calculator",
        "query": "newly consolidated tax calculator",
        "target_url": "https://profithelm.com/tools/newly-consolidated-calculator/",
        "baseline_impressions": 40,
        "baseline_clicks": 3,
        "baseline_ctr": 0.075,
        "baseline_position": 7.5,
        "locked_until": active_lock,
        "status": "ACTIVE_LOCKED",
        "title_rewrite": "Newly Consolidated Tax Calculator (2026 Model) | ProfitHelm",
        "secondary_title_modifier": "(2026 Model)",
        "quick_answer": "Consolidated calculator model.",
        "autonomous_citation_assertions": ["NC 1", "NC 2", "NC 3"],
    }
    (nc_dir / "index.html").write_text(
        inject_overlay_into_html(
            "<html><head><title>Newly Consolidated Calculator | ProfitHelm</title></head>"
            "<body><main><h1>Newly Consolidated Calculator</h1>"
            "<aside class='quick-answer'><p>Base</p></aside></main></body></html>",
            nc_spec,
        ),
        encoding="utf-8",
    )
    (overlays_dir / "newly-consolidated-calculator.json").write_text(
        json.dumps(nc_spec, indent=2), encoding="utf-8"
    )

    fixture_payload = {
        "device_metrics": [
            {"device": "DESKTOP", "page": "", "query": "", "clicks": 30, "impressions": 500, "ctr": 0.06, "position": 12.0}
        ],
        "search_appearances": [],
        "query_page_windows": [
            # Anonymized query+page falsely shows tiny/degraded sliver for california!
            {
                "window_key": "recent_28d",
                "query": "ca tax brackets 2027",
                "page": "https://profithelm.com/tools/irs-2027-tax-brackets/california/",
                "clicks": 0,
                "impressions": 12,
                "ctr": 0.0,
                "position": 19.4,
            }
        ],
        "page_windows": [
            # Canonical direct california: healthy (254 -> 190 impr, 21 -> 9 clicks, pos 9.57 -> 10.32)
            {
                "window_key": "prior_28d_baseline",
                "page": "https://profithelm.com/tools/irs-2027-tax-brackets/california/",
                "clicks": 21,
                "impressions": 254,
                "ctr": 0.0827,
                "position": 9.57,
            },
            {
                "window_key": "recent_28d",
                "page": "https://profithelm.com/tools/irs-2027-tax-brackets/california/",
                "clicks": 9,
                "impressions": 190,
                "ctr": 0.0474,
                "position": 10.32,
            },
            # Dying 301 source URL for california: sinks from pos 12.67 to pos 44.38 during deindexing!
            {
                "window_key": "prior_28d_baseline",
                "page": "https://profithelm.com/calculators/ca-tax-brackets-2027",
                "clicks": 0,
                "impressions": 183,
                "ctr": 0.0,
                "position": 12.67,
            },
            {
                "window_key": "recent_28d",
                "page": "https://profithelm.com/calculators/ca-tax-brackets-2027",
                "clicks": 0,
                "impressions": 265,
                "ctr": 0.0,
                "position": 44.38,
            },
            # Newly consolidated calculator: 0 direct baseline impr, 40 rolled-up 301 baseline impr -> collapses to 6 impr @ pos 22
            {
                "window_key": "prior_28d_baseline",
                "page": "https://profithelm.com/calculators/old-consolidated-calc",
                "clicks": 3,
                "impressions": 40,
                "ctr": 0.075,
                "position": 7.5,
            },
            {
                "window_key": "recent_28d",
                "page": "https://profithelm.com/tools/newly-consolidated-calculator/",
                "clicks": 0,
                "impressions": 6,
                "ctr": 0.0,
                "position": 22.0,
            },
        ],
        "url_inspections": [],
    }

    getattr(seo_growth_loops, "_LIVE_GSC_MULTIDIM_CACHE", {}).clear()
    getattr(seo_growth_loops, "_LIVE_GSC_CONSOLIDATED_CACHE", {}).clear()
    synced = harvest_and_sync_gsc_multidimensional_telemetry(
        property_id="profithelm",
        repo_root=repo_root,
        db_path=db_file,
        fixture_payload=fixture_payload,
        live_gsc=False,
        persist=True,
    )
    assert synced["status"] == "PASS"

    # 1. Trajectory uses direct canonical -d page (+0.75 pos delta), NOT 301-rolled-up (+19.29 pos delta)!
    ca_vel = synced["time_window_velocity"]["page_window_velocity"]["/tools/irs-2027-tax-brackets/california"]
    assert ca_vel["metric_basis"] == "direct"
    assert ca_vel["position_delta_28d"] == pytest.approx(0.75, abs=0.05)
    assert ca_vel["trajectory_state"] != "DECAYING"

    # 2. Portfolio rollup retains full 455 (190 direct + 265 redirected) impressions
    consolidated = load_consolidated_gsc_query_rows(
        property_id="profithelm",
        repo_root=repo_root,
        live_gsc=False,
    )
    assert consolidated["impressions_by_path"]["/tools/irs-2027-tax-brackets/california"] == 455

    # 3. Overlay evaluation keeps california ACTIVE_LOCKED while rolling back newly-consolidated-calculator
    eval_res = evaluate_expired_overlays(
        site_url="sc-domain:profithelm.com",
        base_dir=repo_root,
    )
    eval_items = eval_res["monitoring"] + eval_res["degraded_rolled_back"] + eval_res["accretive"]
    eval_by_slug = {r["slug"]: r for r in eval_items}
    assert eval_by_slug["irs-2027-tax-brackets/california"]["status"] == "MONITORING"
    ca_disk_spec = json.loads((overlays_dir / "irs-2027-tax-brackets-california.json").read_text(encoding="utf-8"))
    assert ca_disk_spec["status"] == "ACTIVE_LOCKED"
    assert not eval_by_slug["irs-2027-tax-brackets/california"].get("early_regression_flagged")
    assert 'id="gsc-striking-overlay"' in (ca_dir / "index.html").read_text(encoding="utf-8")

    assert eval_by_slug["newly-consolidated-calculator"]["status"] == "DEGRADED_ROLLED_BACK"
    assert 'id="gsc-striking-overlay"' not in (nc_dir / "index.html").read_text(encoding="utf-8")

    # 4. Internal callers monitor_post_release_seo_regressions and evaluate_closed_loop_cohort_reflection
    #    must ALSO preserve california's -d page truth rather than clobbering it with query+page rows!
    rel_mon = monitor_post_release_seo_regressions(
        property_id="profithelm",
        repo_root=repo_root,
        runs_dir=tmp_path / "runs",
        consolidated_gsc=consolidated,
        persist=True,
    )
    assert rel_mon["status"] == "PASS"
    assert "id=\"gsc-striking-overlay\"" in (ca_dir / "index.html").read_text(encoding="utf-8")

    cr_rep = evaluate_closed_loop_cohort_reflection(
        property_id="profithelm",
        repo_root=repo_root,
        dist_dir=dist_dir,
        consolidated_gsc=consolidated,
        persist=True,
    )
    assert "irs-2027-tax-brackets/california" not in cr_rep["rollback_and_flag_actions"]["rolled_back_slugs"]
    assert "irs-2027-tax-brackets/california" not in cr_rep["rollback_and_flag_actions"]["early_regression_flagged_slugs"]
    assert 'id="gsc-striking-overlay"' in (ca_dir / "index.html").read_text(encoding="utf-8")


def test_statistical_floor_and_self_healing_across_active_and_expired_locks(tmp_path: Path) -> None:
    """
    Mirrors all 8 rolled-back profithelm overlays across both active AND expired lock windows:
      - 5 false-positive rollbacks MUST self-heal (status -> ACTIVE_LOCKED, restore rolled_back_*
        fields, re-inject id="gsc-striking-overlay" + <title> into dist/ HTML):
          1. irs-2027-tax-brackets/california (active lock, healthy canonical direct 254 -> 190 impr, pos 9.57 -> 10.32)
          2. section-1031-calculator/new-hampshire (active lock, sub-significance 2 -> 0 impr)
          3. section-1031-calculator/new-york (expired lock, sub-significance 7 -> 0 impr)
          4. section-1031-calculator/oklahoma (active lock, sub-significance 9 -> 0 impr)
          5. tcja-sunset-capital-gains (expired lock, direct 9 -> 12 impr + 13 dying 301 impr ignored because direct 9 > 0)
      - 3 genuine >= 15 baseline collapses MUST remain DEGRADED_ROLLED_BACK with HTML stripped:
          6. section-1031-calculator/texas (active lock, 28 -> 0 impr)
          7. section-1031-calculator/california (active lock, 25 -> 1 impr, pos 25.76 -> 90.0)
          8. section-1031-calculator/kentucky (expired lock, 17 -> 0 impr)
      - Plus a fresh ACTIVE_LOCKED sub-significance overlay (8 -> 0 impr) must never roll back.
    """
    repo_root = tmp_path / "profithelm-platform"
    dist_dir = repo_root / "dist"
    agy_dir = repo_root / ".agy"
    overlays_dir = agy_dir / "overlays"
    db_file = tmp_path / "trend_history.db"
    dist_dir.mkdir(parents=True, exist_ok=True)
    overlays_dir.mkdir(parents=True, exist_ok=True)

    (dist_dir / "_redirects").write_text(
        "/calculators/ca-brackets-old /tools/irs-2027-tax-brackets/california/ 301\n"
        "/calculators/tcja-old /tools/tcja-sunset-capital-gains/ 301\n",
        encoding="utf-8",
    )

    active_lock = "2099-12-31T00:00:00+00:00"
    expired_lock = "2020-01-01T00:00:00+00:00"

    def _seed_previously_rolled_back_overlay(slug: str, lock_iso: str, base_impr: int, base_pos: float) -> Path:
        html_dir = dist_dir / "tools" / slug
        html_dir.mkdir(parents=True, exist_ok=True)
        base_title = f"{slug.replace('/', ' ').replace('-', ' ').title()} | ProfitHelm"
        rewritten_title = f"{slug.split('/')[-1].replace('-', ' ').title()} (2026 Rules) | ProfitHelm"
        active_spec = {
            "slug": slug,
            "query": slug.replace("/", " ").replace("-", " "),
            "target_url": f"https://profithelm.com/tools/{slug}/",
            "baseline_impressions": base_impr,
            "baseline_clicks": 0,
            "baseline_ctr": 0.0,
            "baseline_position": base_pos,
            "locked_until": lock_iso,
            "status": "ACTIVE_LOCKED",
            "title_rewrite": rewritten_title,
            "secondary_title_modifier": "(2026 Rules)",
            "quick_answer": f"Deterministic statutory calculation for {slug}.",
            "h2_headings": [f"How {slug} Works"],
            "autonomous_citation_assertions": ["Fact 1", "Fact 2", "Fact 3"],
        }
        injected_html = inject_overlay_into_html(
            f"<html><head><title>{base_title}</title></head>"
            f"<body><main><h1>{base_title}</h1><aside class='quick-answer'><p>Base</p></aside></main></body></html>",
            active_spec,
        )
        stripped_html = rollback_degraded_overlay_from_html(injected_html, active_spec)
        assert 'id="gsc-striking-overlay"' not in stripped_html
        html_file = html_dir / "index.html"
        html_file.write_text(stripped_html, encoding="utf-8")

        rolled_spec = dict(active_spec)
        rolled_spec["status"] = "DEGRADED_ROLLED_BACK"
        rolled_spec["rolled_back_title_rewrite"] = rolled_spec.pop("title_rewrite")
        rolled_spec["rolled_back_secondary_title_modifier"] = rolled_spec.pop("secondary_title_modifier")
        rolled_spec["rolled_back_quick_answer"] = rolled_spec.pop("quick_answer")
        rolled_spec["rolled_back_h2_headings"] = rolled_spec.pop("h2_headings")
        rolled_spec["rolled_back_autonomous_citation_assertions"] = rolled_spec.pop("autonomous_citation_assertions")
        flat_name = slug.replace("/", "-") + ".json"
        (overlays_dir / flat_name).write_text(json.dumps(rolled_spec, indent=2), encoding="utf-8")
        return html_file

    html_files = {
        "irs-2027-tax-brackets/california": _seed_previously_rolled_back_overlay(
            "irs-2027-tax-brackets/california", active_lock, 65, 8.0
        ),
        "section-1031-calculator/new-hampshire": _seed_previously_rolled_back_overlay(
            "section-1031-calculator/new-hampshire", active_lock, 2, 18.0
        ),
        "section-1031-calculator/new-york": _seed_previously_rolled_back_overlay(
            "section-1031-calculator/new-york", expired_lock, 7, 15.0
        ),
        "section-1031-calculator/oklahoma": _seed_previously_rolled_back_overlay(
            "section-1031-calculator/oklahoma", active_lock, 9, 14.0
        ),
        "tcja-sunset-capital-gains": _seed_previously_rolled_back_overlay(
            "tcja-sunset-capital-gains", expired_lock, 9, 8.5
        ),
        "section-1031-calculator/texas": _seed_previously_rolled_back_overlay(
            "section-1031-calculator/texas", active_lock, 28, 12.0
        ),
        "section-1031-calculator/california": _seed_previously_rolled_back_overlay(
            "section-1031-calculator/california", active_lock, 25, 25.76
        ),
        "section-1031-calculator/kentucky": _seed_previously_rolled_back_overlay(
            "section-1031-calculator/kentucky", expired_lock, 17, 16.0
        ),
    }

    # Also seed a fresh ACTIVE_LOCKED sub-significance overlay (8 impr -> 0 impr) with expired lock
    vt_dir = dist_dir / "tools" / "section-1031-calculator" / "vermont"
    vt_dir.mkdir(parents=True, exist_ok=True)
    vt_spec = {
        "slug": "section-1031-calculator/vermont",
        "query": "1031 exchange calculator vermont",
        "target_url": "https://profithelm.com/tools/section-1031-calculator/vermont/",
        "baseline_impressions": 8,
        "baseline_clicks": 0,
        "baseline_ctr": 0.0,
        "baseline_position": 9.0,
        "locked_until": expired_lock,
        "status": "ACTIVE_LOCKED",
        "title_rewrite": "Vermont 1031 Exchange Calculator (2026 Rules) | ProfitHelm",
        "quick_answer": "Compute Vermont 1031 deferral.",
        "autonomous_citation_assertions": ["VT 1", "VT 2", "VT 3"],
    }
    (vt_dir / "index.html").write_text(
        inject_overlay_into_html(
            "<html><head><title>Vermont 1031 | ProfitHelm</title></head>"
            "<body><main><h1>Vermont 1031</h1><aside class='quick-answer'><p>Base</p></aside></main></body></html>",
            vt_spec,
        ),
        encoding="utf-8",
    )
    (overlays_dir / "section-1031-calculator-vermont.json").write_text(
        json.dumps(vt_spec, indent=2), encoding="utf-8"
    )

    fixture_payload = {
        "device_metrics": [
            {"device": "DESKTOP", "page": "", "query": "", "clicks": 20, "impressions": 400, "ctr": 0.05, "position": 12.0}
        ],
        "search_appearances": [],
        "query_page_windows": [],
        "page_windows": [
            # 1. irs-2027-tax-brackets/california: healthy direct, dying 301 source
            {
                "window_key": "prior_28d_baseline",
                "page": "https://profithelm.com/tools/irs-2027-tax-brackets/california/",
                "clicks": 21,
                "impressions": 254,
                "ctr": 0.0827,
                "position": 9.57,
            },
            {
                "window_key": "recent_28d",
                "page": "https://profithelm.com/tools/irs-2027-tax-brackets/california/",
                "clicks": 9,
                "impressions": 190,
                "ctr": 0.0474,
                "position": 10.32,
            },
            {
                "window_key": "recent_28d",
                "page": "https://profithelm.com/calculators/ca-brackets-old",
                "clicks": 0,
                "impressions": 265,
                "ctr": 0.0,
                "position": 44.38,
            },
            # 2-4 & vermont: sub-significance baselines (< 15 impr) dropping to 0 in recent_28d
            {
                "window_key": "prior_28d_baseline",
                "page": "https://profithelm.com/tools/section-1031-calculator/new-hampshire/",
                "clicks": 0,
                "impressions": 2,
                "ctr": 0.0,
                "position": 18.0,
            },
            {
                "window_key": "prior_28d_baseline",
                "page": "https://profithelm.com/tools/section-1031-calculator/new-york/",
                "clicks": 0,
                "impressions": 7,
                "ctr": 0.0,
                "position": 15.0,
            },
            {
                "window_key": "prior_28d_baseline",
                "page": "https://profithelm.com/tools/section-1031-calculator/oklahoma/",
                "clicks": 0,
                "impressions": 9,
                "ctr": 0.0,
                "position": 14.0,
            },
            {
                "window_key": "prior_28d_baseline",
                "page": "https://profithelm.com/tools/section-1031-calculator/vermont/",
                "clicks": 0,
                "impressions": 8,
                "ctr": 0.0,
                "position": 9.0,
            },
            # 5. tcja-sunset-capital-gains: 9 direct baseline impr (< 15) + 13 dying 301 source impr
            {
                "window_key": "prior_28d_baseline",
                "page": "https://profithelm.com/tools/tcja-sunset-capital-gains/",
                "clicks": 0,
                "impressions": 9,
                "ctr": 0.0,
                "position": 8.5,
            },
            {
                "window_key": "prior_28d_baseline",
                "page": "https://profithelm.com/calculators/tcja-old",
                "clicks": 0,
                "impressions": 13,
                "ctr": 0.0,
                "position": 42.0,
            },
            {
                "window_key": "recent_28d",
                "page": "https://profithelm.com/tools/tcja-sunset-capital-gains/",
                "clicks": 0,
                "impressions": 12,
                "ctr": 0.0,
                "position": 16.0,
            },
            # 6-8: Genuine >= 15 baseline collapses!
            {
                "window_key": "prior_28d_baseline",
                "page": "https://profithelm.com/tools/section-1031-calculator/texas/",
                "clicks": 1,
                "impressions": 28,
                "ctr": 0.0357,
                "position": 12.0,
            },
            {
                "window_key": "prior_28d_baseline",
                "page": "https://profithelm.com/tools/section-1031-calculator/california/",
                "clicks": 0,
                "impressions": 25,
                "ctr": 0.0,
                "position": 25.76,
            },
            {
                "window_key": "recent_28d",
                "page": "https://profithelm.com/tools/section-1031-calculator/california/",
                "clicks": 0,
                "impressions": 1,
                "ctr": 0.0,
                "position": 90.0,
            },
            {
                "window_key": "prior_28d_baseline",
                "page": "https://profithelm.com/tools/section-1031-calculator/kentucky/",
                "clicks": 0,
                "impressions": 17,
                "ctr": 0.0,
                "position": 16.0,
            },
        ],
        "url_inspections": [],
    }

    getattr(seo_growth_loops, "_LIVE_GSC_MULTIDIM_CACHE", {}).clear()
    getattr(seo_growth_loops, "_LIVE_GSC_CONSOLIDATED_CACHE", {}).clear()
    harvest_and_sync_gsc_multidimensional_telemetry(
        property_id="profithelm",
        repo_root=repo_root,
        db_path=db_file,
        fixture_payload=fixture_payload,
        live_gsc=False,
        persist=True,
    )

    eval_res = evaluate_expired_overlays(
        site_url="sc-domain:profithelm.com",
        base_dir=repo_root,
    )
    all_items = eval_res["monitoring"] + eval_res["degraded_rolled_back"] + eval_res["accretive"]
    by_slug = {r["slug"]: r for r in all_items}

    expected_healed = [
        "irs-2027-tax-brackets/california",
        "section-1031-calculator/new-hampshire",
        "section-1031-calculator/new-york",
        "section-1031-calculator/oklahoma",
        "tcja-sunset-capital-gains",
    ]
    for h_slug in expected_healed:
        assert by_slug[h_slug]["status"] in ("ACTIVE_LOCKED", "MONITORING"), (
            f"Expected {h_slug} to self-heal into active monitoring, got {by_slug[h_slug]}"
        )
        saved_spec = json.loads((overlays_dir / (h_slug.replace("/", "-") + ".json")).read_text(encoding="utf-8"))
        assert saved_spec["status"] == "ACTIVE_LOCKED"
        assert saved_spec.get("title_rewrite"), f"Expected title_rewrite restored on {h_slug}"
        assert "rolled_back_title_rewrite" not in saved_spec
        restored_html = html_files[h_slug].read_text(encoding="utf-8")
        assert 'id="gsc-striking-overlay"' in restored_html, f"Expected HTML overlay re-injected on {h_slug}"
        assert "(2026 Rules)" in restored_html

    expected_still_rolled_back = [
        "section-1031-calculator/texas",
        "section-1031-calculator/california",
        "section-1031-calculator/kentucky",
    ]
    for rb_slug in expected_still_rolled_back:
        assert by_slug[rb_slug]["status"] == "DEGRADED_ROLLED_BACK", f"Expected {rb_slug} to stay DEGRADED_ROLLED_BACK"
        rb_html = html_files[rb_slug].read_text(encoding="utf-8")
        assert 'id="gsc-striking-overlay"' not in rb_html

    # Fresh sub-significance overlay (vermont, 8 -> 0 impr, expired lock) never rolls back or confirms accretive
    assert by_slug["section-1031-calculator/vermont"]["status"] in ("ACTIVE_LOCKED", "MONITORING")
    vt_saved = json.loads((overlays_dir / "section-1031-calculator-vermont.json").read_text(encoding="utf-8"))
    assert vt_saved["status"] == "ACTIVE_LOCKED"
    assert 'id="gsc-striking-overlay"' in (vt_dir / "index.html").read_text(encoding="utf-8")


def test_maintenance_call_graph_3_cycle_zero_oscillation_and_no_baseline_clobber(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Ship-Blocker 1 falsification:
    Executes 3 consecutive cycles of the exact maintenance.py downstream chain:
      harvest_and_sync_gsc_multidimensional_telemetry(live_gsc=True)
      -> cons_res = load_consolidated_gsc_query_rows(live_gsc=True, multidim_telemetry=md)
      -> sync_real_gsc_baselines_to_recovery_ledger(..., consolidated_gsc=cons_res, multidim_telemetry=md)
      -> evaluate_expired_overlays(..., live_queries=None, multidim_telemetry=md, live_gsc=True)
      -> run_all_seo_growth_workflows(..., live_queries=cons_res['current_rows'], live_gsc=True, multidim_telemetry=md)
    Proves:
      1. Passing pre-fetched live_queries=cons_res['current_rows'] alongside multidim_telemetry/live_gsc=True
         does NOT disable -d date -d page truth across Workflows 5/6/8/9/10.
      2. Anonymized Page-1 traffic earners stay SCALE_EXPAND (zero false PRUNE_NOINDEX) after run_all_seo_growth_workflows.
      3. Overlay statuses and baseline_impressions / baseline_source experience ZERO oscillations and ZERO clobbers
         across Cycle 1 -> Cycle 2 -> Cycle 3.
    """
    from pseofactory.seo_growth_loops import (
        run_all_seo_growth_workflows,
        sync_real_gsc_baselines_to_recovery_ledger,
    )

    repo_root = tmp_path / "profithelm-platform"
    dist_dir = repo_root / "dist"
    agy_dir = repo_root / ".agy"
    overlays_dir = agy_dir / "overlays"
    runs_dir = agy_dir / "runs" / "run_20261110_test"
    db_file = repo_root / "pseofactory" / "trends" / "data" / "trend_history.db"
    for d in (dist_dir, overlays_dir, runs_dir, db_file.parent):
        d.mkdir(parents=True, exist_ok=True)

    (runs_dir / "release_manifest.json").write_text(
        json.dumps(
            {
                "run_id": "run_20261110_test",
                "project": "profithelm",
                "timestamp": "2026-11-01T12:00:00Z",
                "head_sha": "abc1234",
                "overall_status": "RELEASED",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    old_ts = (datetime.now(timezone.utc) - timedelta(days=95)).timestamp()
    local_today = datetime.now().date()
    created_dt = local_today - timedelta(days=20)
    active_lock = (datetime.now(timezone.utc) + timedelta(days=8)).isoformat()

    # Anonymized Page-1 asset WITH active overlay: query+page shows degraded/zero sliver, date+page shows healthy clicks
    ca_spec = {
        "slug": "irs-2027-tax-brackets/california",
        "query": "ca tax brackets 2027",
        "target_url": "https://profithelm.com/tools/irs-2027-tax-brackets/california/",
        "created_at": f"{created_dt.isoformat()}T06:00:00+00:00",
        "locked_until": active_lock,
        "status": "ACTIVE_LOCKED",
        "title_rewrite": "California 2027 Tax Brackets Calculator (2026 Rules) | ProfitHelm",
        "secondary_title_modifier": "2026 Rules",
        "quick_answer": "Calculate California 2026 and 2027 statutory tax brackets.",
        "h2_headings": ["California Marginal Tax Schedule"],
        "preset_scenarios": [{"label": "Single $125k", "params": {"income": 125000}}],
        "comparison_rows": [{"scenario": "Single", "baseline": "$8,833", "optimized": "$8,100", "delta": "$733", "authority": "CA R&TC 17041"}],
        "faq_entries": [{"question": "What are CA brackets?", "answer": "1% to 12.3% marginal tiers."}],
        "autonomous_citation_assertions": ["CA Fact 1", "CA Fact 2", "CA Fact 3"],
    }
    (overlays_dir / "irs-2027-tax-brackets-california.json").write_text(
        json.dumps(ca_spec, indent=2), encoding="utf-8"
    )

    pages_html = {
        "index.html": (
            "<html><head><title>ProfitHelm Calculators</title></head>"
            "<body><main><a href='/tools/irs-2027-tax-brackets/california/'>CA</a>"
            "<a href='/tools/s-corp-tax-calculator/'>S-Corp</a></main></body></html>"
        ),
        "tools/irs-2027-tax-brackets/california/index.html": inject_overlay_into_html(
            "<html><head><title>California 2027 Tax Brackets | ProfitHelm</title>"
            "<script type='application/ld+json'>{\"datePublished\": \"2026-07-01\"}</script></head>"
            "<body><main><h1>California 2027 Tax Brackets</h1>"
            "<aside class='quick-answer'><p>Base</p></aside></main></body></html>",
            ca_spec,
        ),
        "tools/s-corp-tax-calculator/index.html": (
            "<html><head><title>S-Corp Tax Calculator | ProfitHelm</title>"
            "<script type='application/ld+json'>{\"datePublished\": \"2026-07-01\"}</script></head>"
            "<body><main><h1>S-Corp Tax Savings Calculator</h1></main></body></html>"
        ),
        "tools/r-d-tax-credits-for-mortgage-banking-calculator/index.html": (
            "<html><head><title>R&D Tax Credits for Mortgage Banking Calculator | ProfitHelm</title>"
            f"<script type='application/ld+json'>{{\"datePublished\": \"{local_today.isoformat()}\"}}</script></head>"
            "<body><main><h1>R&D Tax Credits Calculator</h1></main></body></html>"
        ),
    }
    for rel_p, h_body in pages_html.items():
        fp = dist_dir / rel_p
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(h_body, encoding="utf-8")
        if "r-d-tax-credits" not in rel_p:
            os.utime(fp, (old_ts, old_ts))

    # Build deterministic daily (date, page) series for 60 settled days ending local_today - 3d
    daily_rows: List[Dict[str, Any]] = []
    settled_end = local_today - timedelta(days=3)
    for offset in range(60, -1, -1):
        d_cur = settled_end - timedelta(days=offset)
        d_iso = d_cur.isoformat()
        daily_rows.append(
            {
                "keys": [d_iso, "https://profithelm.com/tools/irs-2027-tax-brackets/california/"],
                "clicks": 1,
                "impressions": 10,
                "ctr": 0.10,
                "position": 9.4,
            }
        )
        daily_rows.append(
            {
                "keys": [d_iso, "https://profithelm.com/tools/s-corp-tax-calculator/"],
                "clicks": 1,
                "impressions": 8,
                "ctr": 0.125,
                "position": 6.2,
            }
        )

    def fake_live_cli(site_uri: str, dimensions: List[str], start_date: str, end_date: str) -> List[Dict[str, Any]]:
        dims_t = tuple(dimensions)
        if dims_t == ("date", "page"):
            return list(daily_rows)
        if dims_t == ("query", "page"):
            # Privacy-thresholded query+page returns degraded sliver for california and NOTHING for s-corp!
            if start_date == "56daysAgo":
                return [
                    {
                        "keys": ["ca tax brackets 2027", "https://profithelm.com/tools/irs-2027-tax-brackets/california/"],
                        "clicks": 2,
                        "impressions": 30,
                        "ctr": 0.0667,
                        "position": 8.2,
                    }
                ]
            return [
                {
                    "keys": ["ca tax brackets 2027", "https://profithelm.com/tools/irs-2027-tax-brackets/california/"],
                    "clicks": 0,
                    "impressions": 4,
                    "ctr": 0.0,
                    "position": 26.0,
                }
            ]
        if dims_t == ("device",):
            return [{"keys": ["DESKTOP"], "clicks": 40, "impressions": 400, "ctr": 0.10, "position": 8.0}]
        return []

    monkeypatch.setattr(seo_growth_loops, "_run_live_gsc_query_cli", fake_live_cli)
    monkeypatch.setattr(
        seo_growth_loops,
        "harvest_and_sync_gsc_daily_timeline",
        lambda *a, **kw: [],
    )

    cycle_snapshots: List[Dict[str, Any]] = []
    for _cycle in range(1, 4):
        getattr(seo_growth_loops, "_LIVE_GSC_MULTIDIM_CACHE", {}).clear()
        getattr(seo_growth_loops, "_LIVE_GSC_CONSOLIDATED_CACHE", {}).clear()
        tel_p = agy_dir / "gsc_lifecycle_telemetry.json"
        if tel_p.is_file():
            old_m = datetime.now(timezone.utc).timestamp() - 600.0
            os.utime(tel_p, (old_m, old_m))

        md = harvest_and_sync_gsc_multidimensional_telemetry(
            property_id="profithelm",
            repo_root=repo_root,
            db_path=db_file,
            live_gsc=True,
            persist=True,
        )
        cons_res = load_consolidated_gsc_query_rows(
            property_id="profithelm",
            repo_root=repo_root,
            live_gsc=True,
            multidim_telemetry=md,
        )
        consolidated_live_queries = list(cons_res.get("current_rows") or [])
        sync_real_gsc_baselines_to_recovery_ledger(
            property_id="profithelm",
            repo_root=repo_root,
            live_queries=consolidated_live_queries,
            consolidated_gsc=cons_res,
            multidim_telemetry=md,
        )
        evaluate_expired_overlays(
            site_url="sc-domain:profithelm.com",
            base_dir=repo_root,
            live_queries=None,
            persist=True,
            multidim_telemetry=md,
            live_gsc=True,
        )
        mid_ov = json.loads((overlays_dir / "irs-2027-tax-brackets-california.json").read_text(encoding="utf-8"))

        wf_bundle = run_all_seo_growth_workflows(
            property_id="profithelm",
            repo_root=repo_root,
            dist_dir=dist_dir,
            live_queries=consolidated_live_queries,
            live_gsc=True,
            multidim_telemetry=md,
            persist=True,
        )
        end_ov = json.loads((overlays_dir / "irs-2027-tax-brackets-california.json").read_text(encoding="utf-8"))
        port_disk = json.loads((agy_dir / "content_portfolio_decisions.json").read_text(encoding="utf-8"))
        port_decisions = {
            d["url_path"]: d["portfolio_action"]
            for d in port_disk["decisions"]
        }
        assert wf_bundle["workflows"]["6_content_portfolio_decisions"]["action_breakdown"].get("PRUNE_NOINDEX", 0) == 0
        assert port_decisions["/tools/s-corp-tax-calculator"] == "SCALE_EXPAND"
        assert port_decisions["/tools/irs-2027-tax-brackets/california"] == "SCALE_EXPAND"
        assert mid_ov["status"] == "ACTIVE_LOCKED"
        assert end_ov["status"] == "ACTIVE_LOCKED"
        assert mid_ov["baseline_impressions"] == end_ov["baseline_impressions"]
        assert mid_ov["baseline_source"] == end_ov["baseline_source"]
        all_overlays_state = {}
        for ov_p in sorted(overlays_dir.glob("*.json")):
            ov_d = json.loads(ov_p.read_text(encoding="utf-8"))
            all_overlays_state[ov_p.name] = {
                "status": ov_d.get("status"),
                "baseline_impressions": ov_d.get("baseline_impressions"),
                "baseline_source": ov_d.get("baseline_source"),
            }
        assert "r-d-tax-credits-for-mortgage-banking-calculator.json" in all_overlays_state
        assert all_overlays_state["r-d-tax-credits-for-mortgage-banking-calculator.json"]["baseline_impressions"] == 0
        assert all_overlays_state["r-d-tax-credits-for-mortgage-banking-calculator.json"]["baseline_source"] == "ZERO_IMPRESSION_EMPIRICAL"
        cycle_snapshots.append(
            {
                "status": end_ov["status"],
                "baseline_impressions": end_ov["baseline_impressions"],
                "baseline_source": end_ov["baseline_source"],
                "all_overlays": all_overlays_state,
                "portfolio": port_decisions,
            }
        )

    assert cycle_snapshots[0] == cycle_snapshots[1] == cycle_snapshots[2]


def test_causal_date_page_slicing_pre_drop_hour1_rescue_day35_anchor_and_tail_strip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Ship-Blocker 2 falsification:
      1. Strips unfinalized tail day when property-wide impressions < 15% of prior-7d mean.
      2. Pre-created_at traffic drop (missouri / porsche-cayenne shape: traffic dropped to 0 two weeks
         BEFORE D_0) has 0 pre-window impressions in matched [D_0 - N_post .. D_0 - 1d] and MUST NOT
         be rolled back for a pre-overlay drop.
      3. Brand-new Hour-1 rescue overlays (N_post < MIN_POST_OVERLAY_MATURE_DAYS = 7) MUST NOT
         emergency-rollback on Hour 1 AND MUST NOT overwrite baseline_* with post-overlay current_perf.
      4. Day-35 extended-monitoring overlays keep baseline_* strictly anchored to [D_0 - 28d .. D_0 - 1d].
    """
    repo_root = tmp_path / "profithelm-platform"
    dist_dir = repo_root / "dist"
    overlays_dir = repo_root / ".agy" / "overlays"
    db_file = tmp_path / "trend_history.db"
    dist_dir.mkdir(parents=True, exist_ok=True)
    overlays_dir.mkdir(parents=True, exist_ok=True)

    local_today = datetime.now().date()
    settled_max = local_today - timedelta(days=2)
    unfinalized_tail = local_today - timedelta(days=1)
    active_lock = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
    expired_lock = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()

    d0_pre_drop = settled_max - timedelta(days=12)  # N_post = 10 mature days
    d0_hour1 = settled_max  # N_post = 0 (< 7 immature)
    d0_day35 = settled_max - timedelta(days=35)  # D_max > D_0 + 30d extended monitoring

    specs = {
        "irs-2027-tax-brackets-missouri.json": {
            "slug": "irs-2027-tax-brackets/missouri",
            "query": "missouri 2027 tax brackets",
            "target_url": "https://profithelm.com/tools/irs-2027-tax-brackets/missouri/",
            "created_at": f"{d0_pre_drop.isoformat()}T08:00:00+00:00",
            "locked_until": active_lock,
            "status": "ACTIVE_LOCKED",
            "title_rewrite": "Missouri 2027 Tax Brackets Calculator (2026 Rules) | ProfitHelm",
            "quick_answer": "Missouri statutory brackets.",
            "h2_headings": ["Missouri Tax Schedule"],
            "preset_scenarios": [{"label": "Base", "params": {"income": 100000}}],
            "faq_entries": [{"question": "Q?", "answer": "A."}],
        },
        "hour1-active-rescue.json": {
            "slug": "hour1-active-rescue",
            "query": "hour1 active rescue calculator",
            "target_url": "https://profithelm.com/tools/hour1-active-rescue/",
            "created_at": f"{d0_hour1.isoformat()}T10:00:00+00:00",
            "locked_until": active_lock,
            "status": "ACTIVE_LOCKED",
            "title_rewrite": "Hour1 Active Rescue Calculator (2026 Rules) | ProfitHelm",
            "quick_answer": "Hour1 rescue.",
            "h2_headings": ["Hour1 Schedule"],
            "preset_scenarios": [{"label": "Base", "params": {"income": 100000}}],
            "faq_entries": [{"question": "Q?", "answer": "A."}],
        },
        "hour1-zero-base-rescue.json": {
            "slug": "hour1-zero-base-rescue",
            "query": "hour1 zero base rescue",
            "target_url": "https://profithelm.com/tools/hour1-zero-base-rescue/",
            "anomaly_type": "CRAWL_BUDGET_SIGNAL_LAG",
            "created_at": f"{d0_hour1.isoformat()}T10:00:00+00:00",
            "locked_until": active_lock,
            "status": "ACTIVE_LOCKED",
            "baseline_impressions": 160,
            "baseline_position": 10.0,
            "baseline_clicks": 0,
            "title_rewrite": "Hour1 Zero Base Calculator (2026 Rules) | ProfitHelm",
            "quick_answer": "Hour1 zero base.",
            "h2_headings": ["Hour1 Zero Schedule"],
            "preset_scenarios": [{"label": "Base", "params": {"income": 100000}}],
            "faq_entries": [{"question": "Q?", "answer": "A."}],
        },
        "day35-anchored-baseline.json": {
            "slug": "day35-anchored-baseline",
            "query": "day35 anchored calculator",
            "target_url": "https://profithelm.com/tools/day35-anchored-baseline/",
            "created_at": f"{d0_day35.isoformat()}T08:00:00+00:00",
            "locked_until": expired_lock,
            "status": "ACTIVE_LOCKED",
            "title_rewrite": "Day35 Anchored Baseline Calculator (2026 Rules) | ProfitHelm",
            "quick_answer": "Day35 anchored.",
            "h2_headings": ["Day35 Schedule"],
            "preset_scenarios": [{"label": "Base", "params": {"income": 100000}}],
            "faq_entries": [{"question": "Q?", "answer": "A."}],
        },
    }
    for fn, sp in specs.items():
        (overlays_dir / fn).write_text(json.dumps(sp, indent=2), encoding="utf-8")

    daily_rows: List[Dict[str, Any]] = []
    # Background property traffic of 100 impr/day across settled days, plus 5 impr (<15%) on unfinalized_tail
    for back_days in range(70, -1, -1):
        dt_c = settled_max - timedelta(days=back_days)
        daily_rows.append(
            {
                "keys": [dt_c.isoformat(), "https://profithelm.com/tools/section-179-calculator/"],
                "clicks": 5,
                "impressions": 100,
                "ctr": 0.05,
                "position": 6.0,
            }
        )
    daily_rows.append(
        {
            "keys": [unfinalized_tail.isoformat(), "https://profithelm.com/tools/section-179-calculator/"],
            "clicks": 0,
            "impressions": 5,
            "ctr": 0.0,
            "position": 6.0,
        }
    )

    # 1. Missouri: had 35 impr 42 days before settled_max (inside fixed 56d..29d!), but dropped to 0 25d BEFORE D_0!
    for off in range(45, 38, -1):
        dt_m = settled_max - timedelta(days=off)
        daily_rows.append(
            {
                "keys": [dt_m.isoformat(), "https://profithelm.com/tools/irs-2027-tax-brackets/missouri/"],
                "clicks": 0,
                "impressions": 5,
                "ctr": 0.0,
                "position": 14.0,
            }
        )

    # 2. Hour1 active rescue: had 40 impr across [D_0 - 20d .. D_0 - 1d], 0 post-D_0 days yet
    for off in range(1, 21):
        dt_h = d0_hour1 - timedelta(days=off)
        daily_rows.append(
            {
                "keys": [dt_h.isoformat(), "https://profithelm.com/tools/hour1-active-rescue/"],
                "clicks": 0,
                "impressions": 2,
                "ctr": 0.0,
                "position": 12.0,
            }
        )

    # 3. Day35 anchored baseline: had strictly 28 impr (1/day) in [D_0 - 28d .. D_0 - 1d],
    #    and 84 impr (3/day) in post-overlay days [D_0 + 3d .. settled_max] (which overlap fixed 56d..29d!).
    for off in range(1, 29):
        dt_pre = d0_day35 - timedelta(days=off)
        daily_rows.append(
            {
                "keys": [dt_pre.isoformat(), "https://profithelm.com/tools/day35-anchored-baseline/"],
                "clicks": 0,
                "impressions": 1,
                "ctr": 0.0,
                "position": 18.0,
            }
        )
    cur_post = d0_day35 + timedelta(days=3)
    while cur_post <= settled_max:
        daily_rows.append(
            {
                "keys": [cur_post.isoformat(), "https://profithelm.com/tools/day35-anchored-baseline/"],
                "clicks": 1,
                "impressions": 3,
                "ctr": 0.3333,
                "position": 9.0,
            }
        )
        cur_post += timedelta(days=1)

    def fake_cli(site_uri: str, dimensions: List[str], start_date: str, end_date: str) -> List[Dict[str, Any]]:
        if tuple(dimensions) == ("date", "page"):
            return list(daily_rows)
        return []

    monkeypatch.setattr(seo_growth_loops, "_run_live_gsc_query_cli", fake_cli)
    getattr(seo_growth_loops, "_LIVE_GSC_MULTIDIM_CACHE", {}).clear()
    getattr(seo_growth_loops, "_LIVE_GSC_CONSOLIDATED_CACHE", {}).clear()

    md = harvest_and_sync_gsc_multidimensional_telemetry(
        property_id="profithelm",
        repo_root=repo_root,
        db_path=db_file,
        live_gsc=True,
        persist=True,
    )
    assert unfinalized_tail.isoformat() in md["page_daily_meta"]["stripped_tail_dates"]
    assert md["page_daily_meta"]["max_date"] == settled_max.isoformat()

    eval_res = evaluate_expired_overlays(
        site_url="sc-domain:profithelm.com",
        base_dir=repo_root,
        multidim_telemetry=md,
        persist=True,
    )
    rb_slugs = {r["slug"] for r in eval_res["degraded_rolled_back"]}
    assert "irs-2027-tax-brackets/missouri" not in rb_slugs
    assert "hour1-active-rescue" not in rb_slugs
    assert "hour1-zero-base-rescue" not in rb_slugs
    assert "day35-anchored-baseline" not in rb_slugs

    h1_saved = json.loads((overlays_dir / "hour1-active-rescue.json").read_text(encoding="utf-8"))
    assert h1_saved["status"] == "ACTIVE_LOCKED"
    assert h1_saved["baseline_impressions"] == 40
    assert h1_saved["baseline_source"] == "GSC_EMPIRICAL_CAUSAL_DIRECT"

    h1_zero = json.loads((overlays_dir / "hour1-zero-base-rescue.json").read_text(encoding="utf-8"))
    assert h1_zero["status"] == "ACTIVE_LOCKED"
    assert h1_zero["baseline_impressions"] == 0
    assert h1_zero["baseline_source"] == "ZERO_IMPRESSION_EMPIRICAL"

    d35_saved = json.loads((overlays_dir / "day35-anchored-baseline.json").read_text(encoding="utf-8"))
    assert d35_saved["baseline_impressions"] == 28
    assert d35_saved["status"] == "ACCRETIVE_CONFIRMED"


def test_simpsons_paradox_query_expansion_rank_jump_and_midlock_click_protection(tmp_path: Path) -> None:
    """
    Ship-Blocker 3 falsification:
      1. Long-tail query expansion (15 -> 50 impr, pos 36.0 -> 70.0, clicks 0 -> 0) is NOT degraded.
      2. Page-1 query expansion (20 -> 122 impr, pos 3.6 -> 6.3, clicks 2 -> 3) confirms ACCRETIVE_CONFIRMED.
      3. Rank-jump CTR curve-step (pos 20.12 -> 4.86, 20 -> 25 impr, 0 -> 1 click, ctr 0.04 < 0.06 curve)
         and broad-tail pruning winner (pos 64.2 -> 2.0, 30 -> 18 impr, clicks 0 -> 1) confirm ACCRETIVE_CONFIRMED.
      4. Mid-lock active click-earner previously emergency-aborted (california shape: emergency_lock_override=True,
         active lock, recent_7d_clicks=4, blended pos 9.5 -> 12.1) self-heals instead of staying rolled back!
    """
    repo_root = tmp_path / "profithelm-platform"
    dist_dir = repo_root / "dist"
    overlays_dir = repo_root / ".agy" / "overlays"
    db_file = tmp_path / "trend_history.db"
    dist_dir.mkdir(parents=True, exist_ok=True)
    overlays_dir.mkdir(parents=True, exist_ok=True)

    local_today = datetime.now().date()
    settled_max = local_today - timedelta(days=3)
    d0 = settled_max - timedelta(days=16)  # N_post = 14 mature days
    expired_lock = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    active_lock = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()

    def _write_ov(fname: str, slug: str, lock_val: str, status: str = "ACTIVE_LOCKED", extra: Dict[str, Any] | None = None) -> None:
        h_dir = dist_dir / "tools" / slug
        h_dir.mkdir(parents=True, exist_ok=True)
        (h_dir / "index.html").write_text(
            f"<html><head><title>{slug} | ProfitHelm</title></head>"
            f"<body><main><h1>{slug}</h1><aside class='quick-answer'><p>Base</p></aside></main></body></html>",
            encoding="utf-8",
        )
        sp: Dict[str, Any] = {
            "slug": slug,
            "query": slug.replace("-", " "),
            "target_url": f"https://profithelm.com/tools/{slug}/",
            "created_at": f"{d0.isoformat()}T06:00:00+00:00",
            "locked_until": lock_val,
            "status": status,
            "title_rewrite": f"{slug.title()} Calculator (2026 Rules) | ProfitHelm",
            "quick_answer": "Statutory calculation.",
            "h2_headings": ["Statutory Rules"],
            "preset_scenarios": [{"label": "Base", "params": {"income": 100000}}],
            "faq_entries": [{"question": "Q?", "answer": "A."}],
        }
        if extra:
            sp.update(extra)
        (overlays_dir / fname).write_text(json.dumps(sp, indent=2), encoding="utf-8")

    _write_ov("tail-expansion.json", "tail-expansion", expired_lock)
    _write_ov("page1-expansion.json", "page1-expansion", expired_lock)
    _write_ov("kansas-rank-jump.json", "kansas-rank-jump", expired_lock)
    _write_ov("broad-tail-prune-winner.json", "broad-tail-prune-winner", expired_lock)
    _write_ov(
        "california-midlock-clicks.json",
        "irs-2027-tax-brackets/california",
        active_lock,
        status="DEGRADED_ROLLED_BACK",
        extra={
            "title_rewrite": "",
            "rolled_back_title_rewrite": "California 2027 Tax Brackets Calculator (2026 Rules) | ProfitHelm",
            "rolled_back_modifier": "2026 Rules",
            "emergency_lock_override": True,
        },
    )

    pre_day = (d0 - timedelta(days=5)).isoformat()
    post_day = (settled_max - timedelta(days=1)).isoformat()
    fixture_payload = {
        "page_daily": [
            # 1. tail-expansion: 15 -> 50 impr, pos 36.0 -> 70.0, 0 clicks
            {"date": pre_day, "page": "https://profithelm.com/tools/tail-expansion/", "clicks": 0, "impressions": 15, "ctr": 0.0, "position": 36.0},
            {"date": post_day, "page": "https://profithelm.com/tools/tail-expansion/", "clicks": 0, "impressions": 50, "ctr": 0.0, "position": 70.0},
            # 2. page1-expansion: 20 -> 122 impr, pos 3.6 -> 6.3, clicks 2 -> 3
            {"date": pre_day, "page": "https://profithelm.com/tools/page1-expansion/", "clicks": 2, "impressions": 20, "ctr": 0.10, "position": 3.6},
            {"date": post_day, "page": "https://profithelm.com/tools/page1-expansion/", "clicks": 3, "impressions": 122, "ctr": 0.0246, "position": 6.3},
            # 3. kansas-rank-jump: 20 -> 25 impr, pos 20.12 -> 4.86, clicks 1 -> 1 (ctr 0.05 -> 0.04 < 0.06 curve)
            {"date": pre_day, "page": "https://profithelm.com/tools/kansas-rank-jump/", "clicks": 1, "impressions": 20, "ctr": 0.05, "position": 20.12},
            {"date": post_day, "page": "https://profithelm.com/tools/kansas-rank-jump/", "clicks": 1, "impressions": 25, "ctr": 0.04, "position": 4.86},
            # 4. broad-tail-prune-winner: 30 -> 18 impr (-40%), pos 64.2 -> 2.0, clicks 0 -> 1
            {"date": pre_day, "page": "https://profithelm.com/tools/broad-tail-prune-winner/", "clicks": 0, "impressions": 30, "ctr": 0.0, "position": 64.2},
            {"date": post_day, "page": "https://profithelm.com/tools/broad-tail-prune-winner/", "clicks": 1, "impressions": 18, "ctr": 0.0556, "position": 2.0},
            # 5. california-midlock-clicks: pre 60 impr, 5 clicks, pos 9.5 -> post 50 impr, 4 clicks in recent 7d, blended pos 12.1
            {"date": pre_day, "page": "https://profithelm.com/tools/irs-2027-tax-brackets/california/", "clicks": 5, "impressions": 60, "ctr": 0.0833, "position": 9.5},
            {"date": post_day, "page": "https://profithelm.com/tools/irs-2027-tax-brackets/california/", "clicks": 4, "impressions": 50, "ctr": 0.08, "position": 12.1},
        ]
    }
    md = harvest_and_sync_gsc_multidimensional_telemetry(
        property_id="profithelm",
        repo_root=repo_root,
        db_path=db_file,
        fixture_payload=fixture_payload,
        live_gsc=False,
        persist=True,
    )
    eval_res = evaluate_expired_overlays(
        site_url="sc-domain:profithelm.com",
        base_dir=repo_root,
        multidim_telemetry=md,
        persist=True,
    )
    by_slug = {
        r["slug"]: r
        for r in (eval_res["monitoring"] + eval_res["degraded_rolled_back"] + eval_res["accretive"])
    }
    assert by_slug["tail-expansion"]["status"] == "MONITORING"
    assert by_slug["page1-expansion"]["status"] == "ACCRETIVE_CONFIRMED"
    assert by_slug["kansas-rank-jump"]["status"] == "ACCRETIVE_CONFIRMED"
    assert by_slug["broad-tail-prune-winner"]["status"] == "ACCRETIVE_CONFIRMED"
    assert by_slug["irs-2027-tax-brackets/california"]["status"] == "MONITORING"

    ca_disk = json.loads((overlays_dir / "california-midlock-clicks.json").read_text(encoding="utf-8"))
    assert ca_disk["status"] == "ACTIVE_LOCKED"
    assert "emergency_lock_override" not in ca_disk
    assert 'id="gsc-striking-overlay"' in (
        dist_dir / "tools" / "irs-2027-tax-brackets" / "california" / "index.html"
    ).read_text(encoding="utf-8")


def test_trend_db_empty_window_cleanup_url_inspection_survival_and_cli_error_vs_zero_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Ship-Blocker 4 falsification:
      1. Valid 0-row JSON ('{"rowCount": 0, "data": []}') from gsccli returns [] immediately without
         spawning google-search-console-cli, deletes stale SQLite Search Analytics rows via
         TrendHistoryDB.transaction() (zero _lock/_get_conn AttributeErrors), does NOT re-hydrate
         deleted stale rows, and STILL persists URL inspection records!
      2. Transient CLI failure (returncode=1) passes --row-limit and --data-state all to cmd_alt
         and PRESERVES existing SQLite Search Analytics rows instead of wiping them!
    """
    import subprocess as sp_mod

    repo_root = tmp_path / "lienbond"
    agy_dir = repo_root / ".agy"
    agy_dir.mkdir(parents=True, exist_ok=True)
    db_file = tmp_path / "trend_history.db"

    # Seed URL inspection report for lienbond
    (agy_dir / "indexing_health_report.json").write_text(
        json.dumps(
            {
                "inspected_urls": [
                    {
                        "page_url": "https://lienbond.com/tools/contractor-surety-bond-cost-calculator/",
                        "verdict": "PASS",
                        "coverage_state": "Submitted and indexed",
                        "indexing_state": "INDEXING_ALLOWED",
                        "page_fetch_state": "SUCCESSFUL",
                    }
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # Pre-seed stale Search Analytics rows in TrendHistoryDB
    page_win_cls = trend_models.GSCPageWindowRecord
    page_daily_cls = trend_models.GSCPageDailyRecord
    with TrendHistoryDB(db_file) as tdb:
        tdb.upsert_gsc_page_daily(
            [
                page_daily_cls(
                    property_id="lienbond",
                    metric_date="2026-10-15",
                    page="https://lienbond.com/tools/stale-page/",
                    clicks=3,
                    impressions=40,
                    ctr=0.075,
                    position=8.0,
                )
            ]
        )
        tdb.upsert_gsc_page_windows(
            [
                page_win_cls(
                    property_id="lienbond",
                    window_key="recent_28d",
                    page="https://lienbond.com/tools/stale-page/",
                    clicks=3,
                    impressions=40,
                    ctr=0.075,
                    position=8.0,
                )
            ]
        )

    spawned_cmds: List[List[str]] = []

    class _FakeProc:
        def __init__(self, returncode: int, stdout: str, stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    # Part A: Valid 0-row JSON response
    def fake_run_zero_rows(cmd: List[str], **kwargs: Any) -> _FakeProc:
        spawned_cmds.append(list(cmd))
        return _FakeProc(0, '{"rowCount": 0, "data": []}')

    monkeypatch.setattr(sp_mod, "run", fake_run_zero_rows)
    getattr(seo_growth_loops, "_LIVE_GSC_MULTIDIM_CACHE", {}).clear()

    synced_zero = harvest_and_sync_gsc_multidimensional_telemetry(
        property_id="lienbond",
        repo_root=repo_root,
        db_path=db_file,
        live_gsc=True,
        persist=True,
    )
    assert synced_zero["status"] == "PASS"
    assert spawned_cmds, "Expected primary gsccli invocations"
    assert all(Path(c[0]).name != "google-search-console-cli" for c in spawned_cmds), (
        f"Valid 0-row gsccli JSON must never spawn google-search-console-cli: {spawned_cmds}"
    )
    assert "/tools/stale-page" not in synced_zero["page_windows_by_path"]
    with TrendHistoryDB(db_file) as tdb_after_zero:
        assert tdb_after_zero.get_gsc_page_daily("lienbond") == []
        assert tdb_after_zero.get_gsc_page_windows("lienbond") == []
        insp_rows = tdb_after_zero.get_gsc_url_inspection_states("lienbond")
        assert len(insp_rows) == 1
        assert "contractor-surety-bond-cost-calculator" in insp_rows[0].page_url

    # Part B: Re-seed SQLite rows, then simulate transient CLI failure (returncode=1)
    with TrendHistoryDB(db_file) as tdb_reseed:
        tdb_reseed.upsert_gsc_page_daily(
            [
                page_daily_cls(
                    property_id="lienbond",
                    metric_date="2026-10-20",
                    page="https://lienbond.com/tools/contractor-surety-bond-cost-calculator/",
                    clicks=2,
                    impressions=25,
                    ctr=0.08,
                    position=7.5,
                )
            ]
        )
        tdb_reseed.upsert_gsc_page_windows(
            [
                page_win_cls(
                    property_id="lienbond",
                    window_key="recent_28d",
                    page="https://lienbond.com/tools/contractor-surety-bond-cost-calculator/",
                    clicks=2,
                    impressions=25,
                    ctr=0.08,
                    position=7.5,
                )
            ]
        )

    failed_cmds: List[List[str]] = []

    def fake_run_cli_error(cmd: List[str], **kwargs: Any) -> _FakeProc:
        failed_cmds.append(list(cmd))
        return _FakeProc(1, "", "HTTP 503 Service Unavailable")

    monkeypatch.setattr(sp_mod, "run", fake_run_cli_error)
    getattr(seo_growth_loops, "_LIVE_GSC_MULTIDIM_CACHE", {}).clear()
    tel_json_file = agy_dir / "gsc_lifecycle_telemetry.json"
    if tel_json_file.is_file():
        stale_mtime = datetime.now(timezone.utc).timestamp() - 600.0
        os.utime(tel_json_file, (stale_mtime, stale_mtime))

    harvest_and_sync_gsc_multidimensional_telemetry(
        property_id="lienbond",
        repo_root=repo_root,
        db_path=db_file,
        live_gsc=True,
        persist=True,
    )
    alt_cmds = [c for c in failed_cmds if Path(c[0]).name == "google-search-console-cli"]
    assert alt_cmds, f"Expected fallback CLI attempt when primary gsccli exits non-zero, got {failed_cmds}"
    assert all("--row-limit" in c and "--data-state" in c for c in alt_cmds)

    with TrendHistoryDB(db_file) as tdb_after_err:
        assert len(tdb_after_err.get_gsc_page_daily("lienbond")) == 1
        assert len(tdb_after_err.get_gsc_page_windows("lienbond")) == 1


def test_sub_15_direct_plus_301_consolidation_catches_collapse_without_false_source_rank_rollback(
    tmp_path: Path,
) -> None:
    """
    Secondary Bug 1 falsification (0 < dir_base_impr < 15 <= rol_base_impr):
      1. Volume collapse (3 direct + 197 redirected = 200 baseline -> 0 total current) MUST roll back!
      2. Healthy consolidation (5 direct @ pos 9.0 + 25 redirected = 30 baseline -> 18 direct @ pos 9.4
         + 10 dying 301 @ pos 72.0 = 28 rolled-up @ blended pos 31.8) MUST NOT roll back for 301 source rank decay!
    """
    repo_root = tmp_path / "profithelm-platform"
    dist_dir = repo_root / "dist"
    overlays_dir = repo_root / ".agy" / "overlays"
    db_file = tmp_path / "trend_history.db"
    dist_dir.mkdir(parents=True, exist_ok=True)
    overlays_dir.mkdir(parents=True, exist_ok=True)

    (dist_dir / "_redirects").write_text(
        "/calculators/collapse-legacy /tools/consolidation-collapse/ 301\n"
        "/calculators/healthy-legacy /tools/consolidation-healthy/ 301\n",
        encoding="utf-8",
    )

    active_lock = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    for slug in ("consolidation-collapse", "consolidation-healthy"):
        h_dir = dist_dir / "tools" / slug
        h_dir.mkdir(parents=True, exist_ok=True)
        sp = {
            "slug": slug,
            "query": slug.replace("-", " "),
            "target_url": f"https://profithelm.com/tools/{slug}/",
            "locked_until": active_lock,
            "status": "ACTIVE_LOCKED",
            "title_rewrite": f"{slug.title()} Calculator (2026 Rules) | ProfitHelm",
            "quick_answer": "Consolidation test.",
            "h2_headings": ["Statutory Rules"],
            "preset_scenarios": [{"label": "Base", "params": {"income": 100000}}],
            "faq_entries": [{"question": "Q?", "answer": "A."}],
        }
        (h_dir / "index.html").write_text(
            inject_overlay_into_html(
                f"<html><head><title>{slug} | ProfitHelm</title></head>"
                f"<body><main><h1>{slug}</h1><aside class='quick-answer'><p>Base</p></aside></main></body></html>",
                sp,
            ),
            encoding="utf-8",
        )
        (overlays_dir / f"{slug}.json").write_text(json.dumps(sp, indent=2), encoding="utf-8")

    fixture_payload = {
        "page_windows": [
            # Case 1: 3 direct + 197 redirected -> 0 total
            {"window_key": "prior_28d_baseline", "page": "https://profithelm.com/tools/consolidation-collapse/", "clicks": 0, "impressions": 3, "ctr": 0.0, "position": 9.0},
            {"window_key": "prior_28d_baseline", "page": "https://profithelm.com/calculators/collapse-legacy", "clicks": 8, "impressions": 197, "ctr": 0.0406, "position": 8.5},
            # Case 2: 5 direct @ 9.0 + 25 redirected @ 10.0 -> 18 direct @ 9.4 + 10 dying redirected @ 72.0
            {"window_key": "prior_28d_baseline", "page": "https://profithelm.com/tools/consolidation-healthy/", "clicks": 0, "impressions": 5, "ctr": 0.0, "position": 9.0},
            {"window_key": "prior_28d_baseline", "page": "https://profithelm.com/calculators/healthy-legacy", "clicks": 1, "impressions": 25, "ctr": 0.04, "position": 10.0},
            {"window_key": "recent_28d", "page": "https://profithelm.com/tools/consolidation-healthy/", "clicks": 2, "impressions": 18, "ctr": 0.1111, "position": 9.4},
            {"window_key": "recent_28d", "page": "https://profithelm.com/calculators/healthy-legacy", "clicks": 0, "impressions": 10, "ctr": 0.0, "position": 72.0},
        ]
    }
    md = harvest_and_sync_gsc_multidimensional_telemetry(
        property_id="profithelm",
        repo_root=repo_root,
        db_path=db_file,
        fixture_payload=fixture_payload,
        live_gsc=False,
        persist=True,
    )
    eval_res = evaluate_expired_overlays(
        site_url="sc-domain:profithelm.com",
        base_dir=repo_root,
        multidim_telemetry=md,
        persist=True,
    )
    by_slug = {
        r["slug"]: r
        for r in (eval_res["monitoring"] + eval_res["degraded_rolled_back"] + eval_res["accretive"])
    }
    assert by_slug["consolidation-collapse"]["status"] == "DEGRADED_ROLLED_BACK"
    assert by_slug["consolidation-healthy"]["status"] == "MONITORING"
    assert not by_slug["consolidation-healthy"].get("early_regression_flagged")


def test_self_heal_resynthesizes_stripped_body_syncs_content_overlays_and_rollback_backs_up_all_fields(
    tmp_path: Path,
) -> None:
    """
    Secondary Bug 2 falsification:
      1. A live 03:09 UTC stripped DEGRADED_ROLLED_BACK JSON (having ONLY rolled_back_title_rewrite
         and rolled_back_modifier, with quick_answer, h2_headings, preset_scenarios, comparison_rows,
         faq_entries, and meta_description all stripped) self-heals on BOTH active and expired locks by:
         - preserving the exact restored title_rewrite,
         - deterministically synthesizing all missing body/meta fields via compile_remediation_overlay_spec,
         - syncing the healed JSON to both .agy/overlays and content/overlays (when present), and
         - re-injecting the full id="gsc-striking-overlay" body sections into dist/ HTML!
      2. A new rollback backs up ALL active body keys into rolled_back_* before popping them.
    """
    repo_root = tmp_path / "profithelm-platform"
    dist_dir = repo_root / "dist"
    agy_overlays = repo_root / ".agy" / "overlays"
    content_overlays = repo_root / "content" / "overlays"
    db_file = tmp_path / "trend_history.db"
    for d in (dist_dir, agy_overlays, content_overlays):
        d.mkdir(parents=True, exist_ok=True)

    expired_lock = "2020-01-01T00:00:00+00:00"
    active_lock = "2099-12-31T00:00:00+00:00"

    # 1. Stripped 03:09 UTC-style overlay on expired lock (only rolled_back_title_rewrite present!)
    nh_dir = dist_dir / "tools" / "section-1031-calculator" / "new-hampshire"
    nh_dir.mkdir(parents=True, exist_ok=True)
    (nh_dir / "index.html").write_text(
        "<html><head><title>New Hampshire 1031 Calculator | ProfitHelm</title>"
        "<meta name='description' content='Base desc'></head>"
        "<body><main><h1>New Hampshire 1031 Calculator</h1>"
        "<aside class='quick-answer'><p>Base quick answer</p></aside></main></body></html>",
        encoding="utf-8",
    )
    stripped_nh = {
        "slug": "section-1031-calculator/new-hampshire",
        "property_id": "profithelm",
        "tenant_id": "profithelm",
        "target_url": "https://profithelm.com/tools/section-1031-calculator/new-hampshire/",
        "query": "1031 exchange calculator new hampshire",
        "locked_until": expired_lock,
        "created_at": "2026-10-22T06:38:00+00:00",
        "status": "DEGRADED_ROLLED_BACK",
        "rolled_back_title_rewrite": "New Hampshire 1031 Exchange Calculator (2026 Rules) | ProfitHelm",
        "rolled_back_modifier": "2026 Rules",
        "emergency_lock_override": True,
    }
    (agy_overlays / "section-1031-calculator-new-hampshire.json").write_text(
        json.dumps(stripped_nh, indent=2), encoding="utf-8"
    )

    # 2. Active overlay that genuinely collapses (30 -> 0 impr) to verify full rolled_back_* backup
    tx_dir = dist_dir / "tools" / "section-1031-calculator" / "texas"
    tx_dir.mkdir(parents=True, exist_ok=True)
    tx_active = {
        "slug": "section-1031-calculator/texas",
        "property_id": "profithelm",
        "tenant_id": "profithelm",
        "target_url": "https://profithelm.com/tools/section-1031-calculator/texas/",
        "query": "1031 exchange calculator texas",
        "locked_until": active_lock,
        "status": "ACTIVE_LOCKED",
        "title_rewrite": "Texas 1031 Exchange Calculator (2026 Rules) | ProfitHelm",
        "secondary_title_modifier": "2026 Rules",
        "meta_description": "Texas 1031 meta description.",
        "quick_answer": "Texas 1031 quick answer.",
        "h2_headings": ["Texas 1031 Deferral Rules"],
        "preset_scenarios": [{"label": "TX $500k", "params": {"sale_price": 500000}}],
        "comparison_rows": [{"scenario": "TX", "baseline": "$100k", "optimized": "$0", "delta": "$100k", "authority": "IRC 1031"}],
        "faq_entries": [{"question": "TX 1031?", "answer": "Deferred under IRC 1031."}],
        "faq_schema": {"@type": "FAQPage", "mainEntity": []},
        "autonomous_citation_assertions": ["TX Fact 1"],
    }
    (tx_dir / "index.html").write_text(
        inject_overlay_into_html(
            "<html><head><title>Texas 1031 | ProfitHelm</title></head>"
            "<body><main><h1>Texas 1031</h1><aside class='quick-answer'><p>Base</p></aside></main></body></html>",
            tx_active,
        ),
        encoding="utf-8",
    )
    (agy_overlays / "section-1031-calculator-texas.json").write_text(
        json.dumps(tx_active, indent=2), encoding="utf-8"
    )

    md = harvest_and_sync_gsc_multidimensional_telemetry(
        property_id="profithelm",
        repo_root=repo_root,
        db_path=db_file,
        fixture_payload={
            "page_windows": [
                {"window_key": "prior_28d_baseline", "page": "https://profithelm.com/tools/section-1031-calculator/new-hampshire/", "clicks": 0, "impressions": 2, "ctr": 0.0, "position": 18.0},
                {"window_key": "prior_28d_baseline", "page": "https://profithelm.com/tools/section-1031-calculator/texas/", "clicks": 1, "impressions": 30, "ctr": 0.0333, "position": 11.0},
            ]
        },
        live_gsc=False,
        persist=True,
    )
    evaluate_expired_overlays(
        site_url="sc-domain:profithelm.com",
        base_dir=repo_root,
        multidim_telemetry=md,
        persist=True,
    )

    healed_agy = json.loads((agy_overlays / "section-1031-calculator-new-hampshire.json").read_text(encoding="utf-8"))
    healed_content = json.loads((content_overlays / "section-1031-calculator-new-hampshire.json").read_text(encoding="utf-8"))
    assert healed_agy == healed_content
    assert healed_agy["status"] == "ACTIVE_LOCKED"
    assert healed_agy["title_rewrite"] == "New Hampshire 1031 Exchange Calculator (2026 Rules) | ProfitHelm"
    for req_k in ("meta_description", "quick_answer", "h2_headings", "preset_scenarios", "comparison_rows", "faq_entries", "faq_schema"):
        assert healed_agy.get(req_k), f"Expected synthesized {req_k} on self-healed stripped overlay"

    nh_html = (nh_dir / "index.html").read_text(encoding="utf-8")
    assert 'id="gsc-striking-overlay"' in nh_html
    assert "overlay-headings" in nh_html
    assert "overlay-scenarios" in nh_html
    assert "overlay-faqs" in nh_html
    assert "New Hampshire 1031 Exchange Calculator (2026 Rules) | ProfitHelm" in nh_html

    tx_rb = json.loads((agy_overlays / "section-1031-calculator-texas.json").read_text(encoding="utf-8"))
    assert tx_rb["status"] == "DEGRADED_ROLLED_BACK"
    for bk_k in (
        "rolled_back_title_rewrite",
        "rolled_back_secondary_title_modifier",
        "rolled_back_meta_description",
        "rolled_back_quick_answer",
        "rolled_back_h2_headings",
        "rolled_back_preset_scenarios",
        "rolled_back_comparison_rows",
        "rolled_back_faq_entries",
        "rolled_back_faq_schema",
    ):
        assert tx_rb.get(bk_k), f"Expected {bk_k} backed up on rollback"


def test_day_63_to_90_horizon_erosion_preserves_persisted_baseline_and_sparse_min_date(
    tmp_path: Path,
) -> None:
    """
    Verifies:
      1. page_daily_meta['query_start_date'] reflects the 90daysAgo query horizon rather than
         min_date of non-zero rows on sparse domains (e.g. lienbond with only 2 recent rows).
      2. Between Day 63 and Day 90 (pre_s_iso < query_start_date <= pre_e_iso), when GSC's
         rolling 90d window clips part of [d0 - 28d .. d0 - 1d], persisted empirical baselines
         (both GSC_EMPIRICAL_CAUSAL_* and ZERO_IMPRESSION_EMPIRICAL with baseline_window_days >= 28)
         are preserved intact without eroding day-by-day.
    """
    repo_root = tmp_path / "profithelm-platform"
    dist_dir = repo_root / "dist"
    overlays_dir = repo_root / ".agy" / "overlays"
    db_file = tmp_path / "trend_history.db"
    dist_dir.mkdir(parents=True, exist_ok=True)
    overlays_dir.mkdir(parents=True, exist_ok=True)

    local_today = datetime.now().date()
    query_start = local_today - timedelta(days=90)
    settled_max = local_today - timedelta(days=2)
    expired_lock = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()

    # Overlay created at Day 72 ago: pre_slice = [today - 100d .. today - 73d], so
    # pre_s < query_start <= pre_e (18 of 28 pre-overlay days remained in 90d window, 10 clipped!)
    d0_day72 = local_today - timedelta(days=72)
    ca_overlay = {
        "slug": "irs-2027-tax-brackets/california",
        "target_url": "https://profithelm.com/tools/irs-2027-tax-brackets/california/",
        "query": "california 2027 tax brackets",
        "created_at": f"{d0_day72.isoformat()}T08:00:00+00:00",
        "locked_until": expired_lock,
        "status": "ACTIVE_LOCKED",
        "baseline_impressions": 280,
        "baseline_clicks": 21,
        "baseline_ctr": 0.075,
        "baseline_position": 9.57,
        "baseline_source": "GSC_EMPIRICAL_CAUSAL_DIRECT",
        "baseline_window_days": 28,
        "title_rewrite": "California 2027 Tax Brackets Calculator (2026 Rules) | ProfitHelm",
        "secondary_title_modifier": "2026 Rules",
    }
    (overlays_dir / "irs-2027-tax-brackets-california.json").write_text(
        json.dumps(ca_overlay, indent=2), encoding="utf-8"
    )

    zero_overlay = {
        "slug": "section-1031-calculator/new-hampshire",
        "target_url": "https://profithelm.com/tools/section-1031-calculator/new-hampshire/",
        "query": "1031 exchange calculator new hampshire",
        "created_at": f"{d0_day72.isoformat()}T08:00:00+00:00",
        "locked_until": expired_lock,
        "status": "ACTIVE_LOCKED",
        "baseline_impressions": 0,
        "baseline_clicks": 0,
        "baseline_ctr": 0.0,
        "baseline_position": 50.0,
        "baseline_source": "ZERO_IMPRESSION_EMPIRICAL",
        "baseline_window_days": 28,
        "title_rewrite": "New Hampshire 1031 Exchange Calculator (2026 Rules) | ProfitHelm",
        "secondary_title_modifier": "2026 Rules",
    }
    (overlays_dir / "section-1031-calculator-new-hampshire.json").write_text(
        json.dumps(zero_overlay, indent=2), encoding="utf-8"
    )

    # Seed daily rows ONLY from query_start (today - 90d) to settled_max:
    # For california, the 18 surviving pre-overlay days sum to only 180 impr (vs true 280 full 28d baseline!)
    daily_fixture = []
    cur_d = query_start
    while cur_d <= settled_max:
        daily_fixture.append(
            {
                "metric_date": cur_d.isoformat(),
                "page": "https://profithelm.com/tools/irs-2027-tax-brackets/california/",
                "clicks": 1,
                "impressions": 10,
                "ctr": 0.10,
                "position": 9.2,
            }
        )
        if cur_d >= d0_day72 + timedelta(days=3):
            daily_fixture.append(
                {
                    "metric_date": cur_d.isoformat(),
                    "page": "https://profithelm.com/tools/section-1031-calculator/new-hampshire/",
                    "clicks": 0,
                    "impressions": 2,
                    "ctr": 0.0,
                    "position": 14.0,
                }
            )
        cur_d += timedelta(days=1)

    md = harvest_and_sync_gsc_multidimensional_telemetry(
        property_id="profithelm",
        repo_root=repo_root,
        db_path=db_file,
        fixture_payload={"page_daily": daily_fixture},
        live_gsc=False,
        persist=True,
    )
    assert md["page_daily_meta"]["query_start_date"] == query_start.isoformat()

    evaluate_expired_overlays(
        site_url="sc-domain:profithelm.com",
        base_dir=repo_root,
        multidim_telemetry=md,
        persist=True,
    )

    ca_after = json.loads((overlays_dir / "irs-2027-tax-brackets-california.json").read_text(encoding="utf-8"))
    assert ca_after["baseline_impressions"] == 280
    assert ca_after["baseline_clicks"] == 21
    assert ca_after["baseline_window_days"] == 28
    assert ca_after["status"] != "DEGRADED_ROLLED_BACK"

    nh_after = json.loads((overlays_dir / "section-1031-calculator-new-hampshire.json").read_text(encoding="utf-8"))
    assert nh_after["baseline_impressions"] == 0
    assert nh_after["baseline_source"] == "ZERO_IMPRESSION_EMPIRICAL"
    assert nh_after["baseline_window_days"] == 28

    # Sparse domain check (lienbond-style: only 2 recent days of rows inside a 90d query):
    # query_start_date MUST still be today - 90d, NOT min_date (settled_max - 1d)!
    sparse_md = harvest_and_sync_gsc_multidimensional_telemetry(
        property_id="lienbond",
        repo_root=tmp_path / "lienbond",
        db_path=tmp_path / "lienbond.db",
        fixture_payload={
            "page_daily": [
                {
                    "metric_date": (settled_max - timedelta(days=1)).isoformat(),
                    "page": "https://lienbond.com/tools/miller-act-bond-calculator/",
                    "clicks": 0,
                    "impressions": 3,
                    "ctr": 0.0,
                    "position": 19.0,
                },
                {
                    "metric_date": settled_max.isoformat(),
                    "page": "https://lienbond.com/tools/miller-act-bond-calculator/",
                    "clicks": 0,
                    "impressions": 4,
                    "ctr": 0.0,
                    "position": 18.0,
                },
            ]
        },
        live_gsc=False,
        persist=False,
    )
    assert sparse_md["page_daily_meta"]["min_date"] == (settled_max - timedelta(days=1)).isoformat()
    assert sparse_md["page_daily_meta"]["query_start_date"] == query_start.isoformat()


def test_poisson_click_noise_at_lock_expiry_vs_significant_ctr_collapse(
    tmp_path: Path,
) -> None:
    """
    Verifies pooled two-proportion z-score significance (z <= -1.645, min_base_clicks >= 3)
    at lock expiry so growing/steady Page-1 overlays do NOT falsely roll back on small-sample
    Poisson click variance (5/44 -> 3/71, 1/41 -> 0/41, 1/32 -> 0/43), while genuine CTR
    collapses (4/18 -> 0/25, z = -2.47) DO roll back.
    """
    from pseofactory import gsc_remediation as gsc_mod

    repo_root = tmp_path / "profithelm-platform"
    dist_dir = repo_root / "dist"
    overlays_dir = repo_root / ".agy" / "overlays"
    db_file = tmp_path / "trend_history.db"
    dist_dir.mkdir(parents=True, exist_ok=True)
    overlays_dir.mkdir(parents=True, exist_ok=True)

    expired_lock = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    specs = [
        ("irs-2027-tax-brackets-new-mexico", "irs-2027-tax-brackets/new-mexico", 4.23, 44, 5, 4.52, 71, 3),
        ("irs-2027-tax-brackets-arkansas", "irs-2027-tax-brackets/arkansas", 7.02, 41, 1, 8.39, 41, 0),
        ("irs-2027-tax-brackets-alabama", "irs-2027-tax-brackets/alabama", 4.94, 32, 1, 8.12, 43, 0),
        ("irs-2027-tax-brackets-vermont", "irs-2027-tax-brackets/vermont", 6.80, 18, 4, 7.20, 25, 0),
    ]
    pw_fixture = []
    for fname, slug, b_pos, b_imp, b_clk, c_pos, c_imp, c_clk in specs:
        (overlays_dir / f"{fname}.json").write_text(
            json.dumps(
                {
                    "slug": slug,
                    "target_url": f"https://profithelm.com/tools/{slug}/",
                    "query": slug.replace("/", " ").replace("-", " "),
                    "locked_until": expired_lock,
                    "status": "ACTIVE_LOCKED",
                    "title_rewrite": f"{slug.title()} | ProfitHelm",
                    "secondary_title_modifier": "2026 Rules",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        pw_fixture.append(
            {
                "window_key": "prior_28d_baseline",
                "page": f"https://profithelm.com/tools/{slug}/",
                "clicks": b_clk,
                "impressions": b_imp,
                "ctr": round(b_clk / float(b_imp), 4),
                "position": b_pos,
            }
        )
        pw_fixture.append(
            {
                "window_key": "recent_28d",
                "page": f"https://profithelm.com/tools/{slug}/",
                "clicks": c_clk,
                "impressions": c_imp,
                "ctr": round(c_clk / float(c_imp), 4),
                "position": c_pos,
            }
        )

    md = harvest_and_sync_gsc_multidimensional_telemetry(
        property_id="profithelm",
        repo_root=repo_root,
        db_path=db_file,
        fixture_payload={"page_windows": pw_fixture},
        live_gsc=False,
        persist=True,
    )
    evaluate_expired_overlays(
        site_url="sc-domain:profithelm.com",
        base_dir=repo_root,
        multidim_telemetry=md,
        persist=True,
    )

    for healthy_fname in (
        "irs-2027-tax-brackets-new-mexico",
        "irs-2027-tax-brackets-arkansas",
        "irs-2027-tax-brackets-alabama",
    ):
        d = json.loads((overlays_dir / f"{healthy_fname}.json").read_text(encoding="utf-8"))
        assert d["status"] != "DEGRADED_ROLLED_BACK", f"{healthy_fname} falsely rolled back on Poisson noise"

    vt_d = json.loads((overlays_dir / "irs-2027-tax-brackets-vermont.json").read_text(encoding="utf-8"))
    assert vt_d["status"] == "DEGRADED_ROLLED_BACK"

    sig_fn = getattr(gsc_mod, "_is_statistically_significant_ctr_drop", None)
    assert sig_fn is not None
    assert sig_fn(5, 44, 3, 71) is False
    assert sig_fn(1, 41, 0, 41) is False
    assert sig_fn(1, 32, 0, 43) is False
    assert sig_fn(4, 18, 0, 25) is True


def test_monitoring_current_metrics_refresh_and_idempotent_confirmed_at(
    tmp_path: Path,
) -> None:
    """
    Verifies:
      1. Active-locked MONITORING overlays refresh stale top-level current_impressions,
         current_clicks, current_ctr, and current_position when causal page metrics update,
         with zero Cycle 1 -> Cycle 2 churn.
      2. ACCRETIVE_CONFIRMED overlays preserve their original confirmed_at timestamp idempotently
         across repeated evaluations.
    """
    repo_root = tmp_path / "profithelm-platform"
    dist_dir = repo_root / "dist"
    overlays_dir = repo_root / ".agy" / "overlays"
    db_file = tmp_path / "trend_history.db"
    dist_dir.mkdir(parents=True, exist_ok=True)
    overlays_dir.mkdir(parents=True, exist_ok=True)

    active_lock = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    expired_lock = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    orig_confirmed_at = "2026-11-05T12:00:00+00:00"

    il_path = overlays_dir / "irs-2027-tax-brackets-illinois.json"
    il_path.write_text(
        json.dumps(
            {
                "slug": "irs-2027-tax-brackets/illinois",
                "target_url": "https://profithelm.com/tools/irs-2027-tax-brackets/illinois/",
                "query": "illinois 2027 tax brackets",
                "locked_until": active_lock,
                "status": "ACTIVE_LOCKED",
                "current_impressions": 1,
                "current_clicks": 0,
                "current_ctr": 0.0,
                "current_position": 24.0,
                "title_rewrite": "Illinois 2027 Tax Brackets Calculator (2026 Rules) | ProfitHelm",
                "secondary_title_modifier": "2026 Rules",
                "meta_description": "Illinois statutory tax brackets calculator.",
                "quick_answer": "Compute Illinois flat tax schedule.",
                "h2_headings": ["Illinois Tax Rate Schedule"],
                "preset_scenarios": [{"label": "Single $100k", "params": {"income": 100000}}],
                "comparison_rows": [{"scenario": "Single", "baseline": "$4,950", "optimized": "$4,700", "delta": "$250", "authority": "35 ILCS 5/201"}],
                "faq_entries": [{"question": "IL tax rate?", "answer": "4.95% flat rate."}],
                "faq_schema": {"@type": "FAQPage", "mainEntity": []},
                "autonomous_citation_assertions": ["IL Fact 1"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    tx_path = overlays_dir / "irs-2027-tax-brackets-texas.json"
    tx_path.write_text(
        json.dumps(
            {
                "slug": "irs-2027-tax-brackets/texas",
                "target_url": "https://profithelm.com/tools/irs-2027-tax-brackets/texas/",
                "query": "texas 2027 tax brackets",
                "locked_until": expired_lock,
                "status": "ACCRETIVE_CONFIRMED",
                "confirmed_at": orig_confirmed_at,
                "title_rewrite": "Texas 2027 Federal Tax Brackets Calculator | ProfitHelm",
                "secondary_title_modifier": "2026 Rules",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    md = harvest_and_sync_gsc_multidimensional_telemetry(
        property_id="profithelm",
        repo_root=repo_root,
        db_path=db_file,
        fixture_payload={
            "page_windows": [
                {"window_key": "prior_28d_baseline", "page": "https://profithelm.com/tools/irs-2027-tax-brackets/illinois/", "clicks": 1, "impressions": 22, "ctr": 0.0455, "position": 9.8},
                {"window_key": "recent_28d", "page": "https://profithelm.com/tools/irs-2027-tax-brackets/illinois/", "clicks": 3, "impressions": 49, "ctr": 0.0612, "position": 8.4},
                {"window_key": "prior_28d_baseline", "page": "https://profithelm.com/tools/irs-2027-tax-brackets/texas/", "clicks": 2, "impressions": 30, "ctr": 0.0667, "position": 8.5},
                {"window_key": "recent_28d", "page": "https://profithelm.com/tools/irs-2027-tax-brackets/texas/", "clicks": 5, "impressions": 48, "ctr": 0.1042, "position": 6.2},
            ]
        },
        live_gsc=False,
        persist=True,
    )

    evaluate_expired_overlays(
        site_url="sc-domain:profithelm.com",
        base_dir=repo_root,
        multidim_telemetry=md,
        persist=True,
    )
    il_c1_raw = il_path.read_text(encoding="utf-8")
    tx_c1_raw = tx_path.read_text(encoding="utf-8")
    il_c1 = json.loads(il_c1_raw)
    tx_c1 = json.loads(tx_c1_raw)

    assert il_c1["current_impressions"] == 49
    assert il_c1["current_clicks"] == 3
    assert il_c1["current_position"] == 8.4
    assert tx_c1["status"] == "ACCRETIVE_CONFIRMED"
    assert tx_c1["confirmed_at"] == orig_confirmed_at

    # Second cycle must produce zero file churn and preserve confirmed_at
    evaluate_expired_overlays(
        site_url="sc-domain:profithelm.com",
        base_dir=repo_root,
        multidim_telemetry=md,
        persist=True,
    )
    assert il_path.read_text(encoding="utf-8") == il_c1_raw
    assert tx_path.read_text(encoding="utf-8") == tx_c1_raw


def test_sync_tenant_test_isolation_guards_aligns_prexvo_and_profithelm_monetization_contracts(
    tmp_path: Path,
) -> None:
    """
    Verifies sync_tenant_test_isolation_guards updates downstream Prexvo and ProfitHelm
    contract files (declined partner suppression, TELEMETRY_EXPORT_SECRET roundtrip, and
    approved Xendoo Section 179 route) idempotently during reflect.
    """
    from pseofactory.gitops import sync_tenant_test_isolation_guards

    px_root = tmp_path / "prexvo"
    (px_root / "prexvo").mkdir(parents=True, exist_ok=True)
    (px_root / "tests").mkdir(parents=True, exist_ok=True)
    (px_root / "prexvo" / "freshness.py").write_text(
        '        if status in ("live", "pending"):\n'
        "            live_partners += 1\n"
        '        elif status == "pending_p2":\n'
        "            suppressed_partners += 1\n",
        encoding="utf-8",
    )
    (px_root / "tests" / "test_affiliate_routes.py").write_text(
        '    assert report["total_partners"] == 5\n'
        '    assert report["live_partners"] == 5\n'
        '    assert report["suppressed_partners"] == 0\n'
        '    assert data["total_partners"] == 5\n'
        '    assert data["live_partners"] == 5\n'
        '    assert data["suppressed_partners"] == 0\n'
        "    for p_key in PREXVO_AFFILIATES.keys():\n"
        "        assert f'/r/{p_key}' in matrix_html\n"
        '    for p_key in list(PREXVO_AFFILIATES.keys()) + ["sofi_refi", "laurel_road", "juno"]:\n'
        "        edge_res = simulate_edge_redirect(p_key)\n"
        '        assert edge_res["status"] == 302\n'
        '        assert edge_res["location"] != EDUCATIONAL_CALCULATOR_URL\n'
        '        assert "prexvo.com" not in edge_res["location"].split("?")[0]\n'
        '        assert "ref=prexvo" in edge_res["location"]\n'
        '        assert edge_res["has_tracking"] is True\n'
        '        assert "noindex, nofollow" in edge_res["headers"]["X-Robots-Tag"]\n'
        '        assert "no-cache" in edge_res["headers"]["Cache-Control"]\n',
        encoding="utf-8",
    )

    ph_root = tmp_path / "profithelm-platform"
    (ph_root / "profithelm").mkdir(parents=True, exist_ok=True)
    (ph_root / "tests").mkdir(parents=True, exist_ok=True)
    (ph_root / "tests" / "test_audit_closed_loop_upgrades.py").write_text(
        "      const env = {\n"
        "        PROFITHELM_TELEMETRY_KV: {\n"
        "          put: async (k, v) => { storedKV[k] = v; },\n"
        "          list: async () => ({ keys: Object.keys(storedKV).map(k => ({ name: k })), list_complete: true }),\n"
        "          get: async (k) => storedKV[k]\n"
        "        }\n"
        "      };\n"
        '      const getReq = new Request("https://profithelm.com/api/telemetry");\n',
        encoding="utf-8",
    )
    (ph_root / "tests" / "test_multi_engine_ranking_benchmark.py").write_text(
        '    assert res["affiliate_route"]["partner_key"] == "crest_capital"\n',
        encoding="utf-8",
    )

    res_px = sync_tenant_test_isolation_guards(px_root, "prexvo")
    res_ph = sync_tenant_test_isolation_guards(ph_root, "profithelm")
    assert res_px["updated_files"] == 2
    assert res_ph["updated_files"] == 2
    assert 'status in ("pending_p2", "declined")' in (px_root / "prexvo" / "freshness.py").read_text(encoding="utf-8")
    assert "suppressed_keys" in (px_root / "tests" / "test_affiliate_routes.py").read_text(encoding="utf-8")
    assert 'TELEMETRY_EXPORT_SECRET: "test_secret_123"' in (
        ph_root / "tests" / "test_audit_closed_loop_upgrades.py"
    ).read_text(encoding="utf-8")
    assert 'Bearer test_secret_123' in (
        ph_root / "tests" / "test_audit_closed_loop_upgrades.py"
    ).read_text(encoding="utf-8")
    assert '== "xendoo"' in (
        ph_root / "tests" / "test_multi_engine_ranking_benchmark.py"
    ).read_text(encoding="utf-8")

    # Idempotency check
    assert sync_tenant_test_isolation_guards(px_root, "prexvo")["updated_files"] == 0
    assert sync_tenant_test_isolation_guards(ph_root, "profithelm")["updated_files"] == 0
