"""
Comprehensive tests for multi-dimensional Google Search Console lifecycle telemetry
across Discovery, Qualification, Compilation, Auditing/Verification, Monetization,
and Tenant Reflection.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import json
from pathlib import Path

from pseofactory.affiliates import (
    run_gsc_affiliate_placement_feedback_pass,
    select_conversion_slot_plan,
)
from pseofactory.compiler import compile_high_effort_page
from pseofactory.gsc_remediation import (
    calculate_candidate_roi,
    compile_remediation_overlay_spec,
)
from pseofactory.indexing.feedback_loop import (
    GSCRootCauseClassifier,
    RootCauseClassification,
)
from pseofactory.maintenance import RetroReflectionEngine
from pseofactory.qualification import (
    evaluate_query_impression_split,
    qualify_search_intent,
)
from pseofactory.seo_growth_loops import (
    audit_gsc_cannibalization_splits,
    harvest_and_sync_gsc_multidimensional_telemetry,
    identify_content_decay,
    load_consolidated_gsc_query_rows,
)
from pseofactory.trends.collectors import GSCSearchConsoleCollector
from pseofactory.trends.db import TrendHistoryDB
from pseofactory.trends.jev_engine import JevEngine
from pseofactory.trends.models import (
    GSCDeviceMetricRecord,
    GSCQueryPageWindowRecord,
    GSCSearchAppearanceRecord,
    GSCUrlInspectionRecord,
    TregDurabilityResult,
    TrendCandidate,
)
from pseofactory.verifier import verify_gsc_lifecycle_telemetry_contract


def test_trend_history_db_multidimensional_gsc_tables(tmp_path: Path) -> None:
    """Verifies idempotent persistence and retrieval of all 4 multi-dimensional GSC tables in TrendHistoryDB."""
    db_file = tmp_path / "trend_history.db"
    with TrendHistoryDB(db_file) as db:
        dev_count = db.upsert_gsc_device_metrics(
            [
                GSCDeviceMetricRecord(
                    property_id="profithelm",
                    device="MOBILE",
                    page="https://profithelm.com/tools/irs-2027-tax-brackets/california/",
                    query="ca tax brackets 2027",
                    window_key="recent_90d",
                    clicks=2,
                    impressions=40,
                    ctr=0.05,
                    position=3.2,
                ),
                GSCDeviceMetricRecord(
                    property_id="profithelm",
                    device="DESKTOP",
                    page="https://profithelm.com/tools/irs-2027-tax-brackets/california/",
                    query="ca tax brackets 2027",
                    window_key="recent_90d",
                    clicks=5,
                    impressions=50,
                    ctr=0.10,
                    position=6.29,
                ),
            ]
        )
        assert dev_count == 2
        fetched_dev = db.get_gsc_device_metrics("profithelm", window_key="recent_90d")
        assert len(fetched_dev) == 2

        sa_count = db.upsert_gsc_search_appearance_metrics(
            [
                GSCSearchAppearanceRecord(
                    property_id="prexvo",
                    search_appearance="PRODUCT_SNIPPETS",
                    window_key="recent_90d",
                    clicks=1,
                    impressions=5,
                    ctr=0.20,
                    position=6.8,
                ),
                GSCSearchAppearanceRecord(
                    property_id="prexvo",
                    search_appearance="REVIEW_SNIPPET",
                    window_key="recent_90d",
                    clicks=0,
                    impressions=3,
                    ctr=0.0,
                    position=9.0,
                ),
            ]
        )
        assert sa_count == 2
        fetched_sa = db.get_gsc_search_appearance_metrics("prexvo", window_key="recent_90d")
        assert [r.search_appearance for r in fetched_sa] == ["PRODUCT_SNIPPETS", "REVIEW_SNIPPET"]

        win_count = db.upsert_gsc_query_page_windows(
            [
                GSCQueryPageWindowRecord(
                    property_id="prexvo",
                    window_key="recent_28d",
                    query="title iv repayment calculator",
                    page="https://prexvo.com/tools/rap-payment-calculator/",
                    clicks=2,
                    impressions=28,
                    ctr=0.0714,
                    position=11.4,
                ),
                GSCQueryPageWindowRecord(
                    property_id="prexvo",
                    window_key="prior_28d_baseline",
                    query="title iv repayment calculator",
                    page="https://prexvo.com/tools/rap-payment-calculator/",
                    clicks=3,
                    impressions=20,
                    ctr=0.15,
                    position=8.2,
                ),
            ]
        )
        assert win_count == 2
        fetched_win = db.get_gsc_query_page_windows("prexvo", window_key="recent_28d")
        assert len(fetched_win) == 1
        assert fetched_win[0].impressions == 28

        insp_count = db.upsert_gsc_url_inspection_states(
            [
                GSCUrlInspectionRecord(
                    property_id="profithelm",
                    page_url="https://profithelm.com/tools/section-179-calculator/",
                    verdict="PASS",
                    coverage_state="Submitted and indexed",
                    indexing_state="INDEXING_ALLOWED",
                    page_fetch_state="SUCCESSFUL",
                    robots_txt_state="ALLOWED",
                    user_canonical="https://profithelm.com/tools/section-179-calculator/",
                    google_canonical="https://profithelm.com/tools/section-179-calculator/",
                    rich_results_verdict="PASS",
                    rich_results_types=["FAQ", "SoftwareApplication"],
                    mobile_usability_verdict="PASS",
                )
            ]
        )
        assert insp_count == 1
        fetched_insp = db.get_gsc_url_inspection_states("profithelm")
        assert len(fetched_insp) == 1
        assert fetched_insp[0].coverage_state == "Submitted and indexed"


def test_multidimensional_harvest_enriches_consolidated_rows_decay_and_cannibalization(tmp_path: Path) -> None:
    """
    Verifies harvest_and_sync_gsc_multidimensional_telemetry persists all 4 dimensions,
    passes verify_gsc_lifecycle_telemetry_contract, enriches load_consolidated_gsc_query_rows,
    drives time-window + mobile CTR decay in identify_content_decay, and detects
    cross-device cannibalization splits in audit_gsc_cannibalization_splits.
    """
    repo_root = tmp_path / "profithelm-platform"
    (repo_root / ".agy").mkdir(parents=True, exist_ok=True)
    db_file = tmp_path / "trend_history.db"

    fixture_payload = {
        "device_metrics": [
            {
                "device": "DESKTOP",
                "page": "",
                "query": "",
                "clicks": 93,
                "impressions": 3409,
                "ctr": 0.0273,
                "position": 25.71,
            },
            {
                "device": "MOBILE",
                "page": "",
                "query": "",
                "clicks": 34,
                "impressions": 1253,
                "ctr": 0.0271,
                "position": 12.50,
            },
            {
                "device": "MOBILE",
                "page": "https://profithelm.com/tools/irs-2027-tax-brackets/california/",
                "query": "ca tax brackets 2027",
                "clicks": 1,
                "impressions": 30,
                "ctr": 0.0333,
                "position": 3.2,
            },
            {
                "device": "DESKTOP",
                "page": "https://profithelm.com/tools/irs-2027-tax-brackets/california/",
                "query": "ca tax brackets 2027",
                "clicks": 4,
                "impressions": 40,
                "ctr": 0.10,
                "position": 6.5,
            },
            {
                "device": "DESKTOP",
                "page": "https://profithelm.com/tools/irs-2027-tax-brackets/",
                "query": "ca tax brackets 2027",
                "clicks": 5,
                "impressions": 80,
                "ctr": 0.0625,
                "position": 5.8,
            },
        ],
        "search_appearances": [
            {
                "search_appearance": "PRODUCT_SNIPPETS",
                "clicks": 2,
                "impressions": 18,
                "ctr": 0.1111,
                "position": 6.4,
            },
            {
                "search_appearance": "REVIEW_SNIPPET",
                "clicks": 1,
                "impressions": 9,
                "ctr": 0.1111,
                "position": 8.1,
            },
        ],
        "query_page_windows": [
            {
                "window_key": "recent_28d",
                "query": "ca tax brackets 2027",
                "page": "https://profithelm.com/tools/irs-2027-tax-brackets/california/",
                "clicks": 5,
                "impressions": 70,
                "ctr": 0.0714,
                "position": 9.8,
            },
            {
                "window_key": "prior_28d_baseline",
                "query": "ca tax brackets 2027",
                "page": "https://profithelm.com/tools/irs-2027-tax-brackets/california/",
                "clicks": 8,
                "impressions": 65,
                "ctr": 0.1231,
                "position": 6.2,
            },
        ],
        "url_inspections": [
            {
                "page_url": "https://profithelm.com/tools/irs-2027-tax-brackets/california/",
                "verdict": "PASS",
                "coverage_state": "Submitted and indexed",
                "user_canonical": "https://profithelm.com/tools/irs-2027-tax-brackets/california/",
                "google_canonical": "https://profithelm.com/tools/irs-2027-tax-brackets/california/",
            }
        ],
    }

    synced = harvest_and_sync_gsc_multidimensional_telemetry(
        property_id="profithelm",
        repo_root=repo_root,
        db_path=db_file,
        fixture_payload=fixture_payload,
        live_gsc=False,
        persist=True,
    )
    assert synced["status"] == "PASS"
    assert synced["has_product_snippets_signal"] is True
    assert synced["has_review_snippet_signal"] is True

    contract_res = verify_gsc_lifecycle_telemetry_contract(repo_root, property_id="profithelm")
    assert contract_res["passed"] is True

    # Verify GSCSearchConsoleCollector surfaces spikes from persisted TrendHistoryDB
    gsc_collector = GSCSearchConsoleCollector(db_path=db_file, properties=["profithelm"])
    spikes = gsc_collector.harvest_gsc_spikes()
    assert len(spikes) == 1
    assert spikes[0].query == "ca tax brackets 2027"
    assert spikes[0].raw_payload["gsc_telemetry"]["mobile_ctr_gap"] > 0.05

    # Verify load_consolidated_gsc_query_rows enriches rows with device splits, search appearances, and window deltas
    consolidated = load_consolidated_gsc_query_rows(
        property_id="profithelm",
        repo_root=repo_root,
        live_queries=[
            {
                "query": "ca tax brackets 2027",
                "page": "https://profithelm.com/tools/irs-2027-tax-brackets/california/",
                "impressions": 70,
                "clicks": 5,
                "ctr": 0.0714,
                "position": 9.8,
            },
            {
                "query": "ca tax brackets 2027",
                "page": "https://profithelm.com/tools/irs-2027-tax-brackets/",
                "impressions": 80,
                "clicks": 5,
                "ctr": 0.0625,
                "position": 5.8,
            },
        ],
        live_gsc=False,
    )
    rows = consolidated["current_rows"]
    ca_row = next(r for r in rows if "irs-2027-tax-brackets/california" in r["canonical_path"])
    assert ca_row["mobile_impressions"] == 30
    assert ca_row["desktop_impressions"] == 40
    assert ca_row["mobile_ctr_gap"] > 0.05
    assert "PRODUCT_SNIPPETS" in ca_row["search_appearances"]
    assert ca_row["time_window_delta"]["trajectory_state"] == "DECAYING"

    # Verify identify_content_decay uses time-window delta and captures mobile CTR gap
    decay_rep = identify_content_decay(
        property_id="profithelm",
        repo_root=repo_root,
        consolidated_gsc=consolidated,
        daily_records=[],
        persist=False,
    )
    assert decay_rep["total_decaying_queries"] >= 1
    dc = decay_rep["decay_candidates"][0]
    assert dc["mobile_impressions"] == 30
    assert dc["mobile_ctr_gap"] > 0.05
    assert dc["time_window_trajectory"] == "DECAYING"

    # Verify cross-device cannibalization split detection (URL A leads MOBILE, URL B leads DESKTOP)
    cann_audit = audit_gsc_cannibalization_splits(
        property_id="profithelm",
        repo_root=repo_root,
        consolidated_gsc=consolidated,
    )
    assert cann_audit["true_cannibalization_splits_count"] == 1
    assert cann_audit["cross_device_splits_count"] == 1
    split_item = cann_audit["cross_device_splits"][0]
    assert split_item["cross_device_split_detected"] is True
    assert "irs-2027-tax-brackets/california" in split_item["mobile_leader_url"]
    assert split_item["desktop_leader_url"].rstrip("/").endswith("/tools/irs-2027-tax-brackets")


def test_cross_device_cannibalization_split_even_above_aggregate_dominance_threshold() -> None:
    """
    Verifies evaluate_query_impression_split flags a CROSS_DEVICE_CANNIBALIZATION_SPLIT
    when URL B holds >80% of desktop impressions while URL A dominates mobile impressions.
    """
    res = evaluate_query_impression_split(
        [
            {
                "url": "https://profithelm.com/tools/california-tax-brackets-2027/",
                "impressions": 85,
                "clicks": 6,
                "position": 5.5,
                "mobile_impressions": 2,
                "desktop_impressions": 83,
                "mobile_position": 9.0,
                "desktop_position": 5.2,
            },
            {
                "url": "https://profithelm.com/tools/irs-2027-tax-brackets/california/",
                "impressions": 15,
                "clicks": 2,
                "position": 3.2,
                "mobile_impressions": 14,
                "desktop_impressions": 1,
                "mobile_position": 3.1,
                "desktop_position": 11.0,
            },
        ]
    )
    assert res["is_true_cannibalization_split"] is True
    assert res["cross_device_split_detected"] is True
    assert res["classification"] == "CROSS_DEVICE_CANNIBALIZATION_SPLIT"
    assert res["mobile_leader_url"].endswith("/tools/irs-2027-tax-brackets/california/")
    assert res["desktop_leader_url"].endswith("/tools/california-tax-brackets-2027/")


def test_stage_1_jev_engine_and_qualify_search_intent_wire_gsc_signals() -> None:
    """Verifies JevEngine and qualify_search_intent propagate multi-dimensional GSC signals and ceiling guards."""
    engine = JevEngine()
    cand_base = TrendCandidate(
        id="cand_base_179",
        query="section 179 bonus depreciation calculator",
        slug="section-179-bonus-depreciation-calculator",
        source="gsc_search_console",
        intent_cluster="tax",
        velocity=95.0,
        acceleration=18.0,
        z_score=3.8,
        metadata={"property_id": "profithelm"},
    )
    treg = TregDurabilityResult(
        query="section 179 bonus depreciation calculator",
        search_volume=2400,
        cpc_usd=12.5,
        competition_index=0.45,
        keyword_difficulty=18.0,
        position_zero_vacant=True,
        historical_stability=0.92,
    )
    base_yield = engine.compute_composite_yield(
        candidate=cand_base,
        treg_result=treg,
        jev_score=1.80,
        durable_prob=0.92,
        cannibalization_risk=0.0,
    )

    cand_gsc = TrendCandidate(
        id="cand_gsc_179",
        query="section 179 bonus depreciation calculator",
        slug="section-179-bonus-depreciation-calculator",
        source="gsc_search_console",
        intent_cluster="tax",
        velocity=95.0,
        acceleration=18.0,
        z_score=3.8,
        metadata={
            "property_id": "profithelm",
            "gsc_telemetry": {
                "mobile_ctr_gap": 0.03,
                "device_focus": "MOBILE_CTR_DEFICIT",
                "search_appearances": ["PRODUCT_SNIPPETS", "REVIEW_SNIPPET"],
                "time_window_trajectory": "ACCELERATING",
            },
        },
    )
    boosted_yield = engine.compute_composite_yield(
        candidate=cand_gsc,
        treg_result=treg,
        jev_score=1.80,
        durable_prob=0.92,
        cannibalization_risk=0.0,
    )
    assert boosted_yield > base_yield

    # Verify ceiling freeze guard in JevEngine.evaluate
    cand_frozen = TrendCandidate(
        id="cand_frozen_179",
        query="section 179 bonus depreciation calculator",
        slug="section-179-bonus-depreciation-calculator",
        source="gsc_search_console",
        intent_cluster="tax",
        velocity=95.0,
        acceleration=18.0,
        z_score=3.8,
        metadata={
            "property_id": "profithelm",
            "ceiling_status": {
                "ceiling_detected": True,
                "ceiling_dampening_score": 0.62,
                "recommendation": "FREEZE_EXPANSION",
            },
        },
    )
    frozen_dec = engine.evaluate(candidate=cand_frozen, treg_result=treg)
    assert frozen_dec.action == "MONITOR"
    assert "Algorithmic ceiling active" in frozen_dec.decision_reason

    # Verify qualify_search_intent propagates device_focus and search_appearances into overlay_spec
    verdict = qualify_search_intent(
        {
            "query": "section 179 suv deduction limit 2026",
            "position": 8.4,
            "impressions": 45,
            "matching_tool": "section-179-calculator",
            "device_focus": "MOBILE_CTR_DEFICIT",
            "mobile_ctr": 0.02,
            "desktop_ctr": 0.06,
            "mobile_ctr_gap": 0.04,
            "search_appearances": ["PRODUCT_SNIPPETS"],
            "time_window_trajectory": "DECAYING",
        }
    )
    assert verdict["action"] == "REFACTOR_PAGE"
    assert verdict["overlay_spec"]["device_focus"] == "MOBILE_CTR_DEFICIT"
    assert verdict["overlay_spec"]["search_appearances"] == ["PRODUCT_SNIPPETS"]
    assert verdict["overlay_spec"]["time_window_trajectory"] == "DECAYING"


def test_stage_2_and_4_compiler_remediation_and_affiliate_slot_wiring(tmp_path: Path) -> None:
    """
    Verifies device CTR splits, rich-result searchAppearances, time-window decay,
    and URL inspection coverage states flow into:
      - select_conversion_slot_plan & run_gsc_affiliate_placement_feedback_pass
      - calculate_candidate_roi & compile_remediation_overlay_spec
      - compile_high_effort_page HTML attributes, JSON-LD featureList, and #calculation-manifest
      - RetroReflectionEngine.retrofit_estate
    """
    # 1. Affiliate slot plan promotes mobile touch CTA on MOBILE_CTR_DEFICIT
    roster = [
        {
            "partner_key": "xendoo",
            "name": "Xendoo Accounting",
            "company_brand": "Xendoo",
            "partnership_model": "HYBRID_CPA_REVSHARE",
            "yield_score": 82.0,
        },
        {
            "partner_key": "ramp",
            "name": "Ramp Corporate Card",
            "company_brand": "Ramp",
            "partnership_model": "CPA_BOUNTY",
            "yield_score": 88.0,
        },
        {
            "partner_key": "gusto",
            "name": "Gusto Payroll",
            "company_brand": "Gusto",
            "partnership_model": "CPA_BOUNTY",
            "yield_score": 76.0,
        },
    ]
    slot_plan = select_conversion_slot_plan(
        property_id="profithelm",
        slug="irs-2027-tax-brackets/california",
        roster_offers=roster,
        gsc_metrics={
            "impressions": 30,
            "clicks": 1,
            "ctr": 0.0333,
            "position": 3.2,
            "mobile_impressions": 22,
            "desktop_impressions": 8,
            "mobile_ctr": 0.015,
            "desktop_ctr": 0.065,
            "mobile_ctr_gap": 0.05,
            "device_focus": "MOBILE_CTR_DEFICIT",
            "search_appearances": ["PRODUCT_SNIPPETS"],
        },
    )
    assert slot_plan["gsc_repositioned"] is True
    assert slot_plan["gsc_opportunity_tier"] == "MOBILE_CTR_DEFICIT_PROMOTION"
    assert slot_plan["promoted_partner_key"] == "ramp"
    assert slot_plan["gsc_device_focus"] == "MOBILE_CTR_DEFICIT"
    assert slot_plan["gsc_search_appearances"] == ["PRODUCT_SNIPPETS"]

    # 2. Remediation ROI & overlay spec incorporate multi-dimensional GSC signals
    roi_base = calculate_candidate_roi(
        {
            "query": "section 179 deduction calculator",
            "target_url": "https://profithelm.com/tools/section-179-calculator/",
            "impressions": 80,
            "clicks": 2,
            "position": 7.5,
        },
        tenant_id="profithelm",
    )
    roi_multidim = calculate_candidate_roi(
        {
            "query": "section 179 deduction calculator",
            "target_url": "https://profithelm.com/tools/section-179-calculator/",
            "impressions": 80,
            "clicks": 2,
            "position": 7.5,
            "mobile_impressions": 45,
            "desktop_impressions": 35,
            "mobile_ctr": 0.01,
            "desktop_ctr": 0.05,
            "mobile_ctr_gap": 0.04,
            "device_focus": "MOBILE_CTR_DEFICIT",
            "search_appearances": ["PRODUCT_SNIPPETS", "REVIEW_SNIPPET"],
            "time_window_trajectory": "DECAYING",
            "coverage_state": "Submitted and indexed",
        },
        tenant_id="profithelm",
    )
    assert roi_multidim["roi_score"] > roi_base["roi_score"]
    assert roi_multidim["device_focus"] == "MOBILE_CTR_DEFICIT"
    assert roi_multidim["time_window_trajectory"] == "DECAYING"

    ov_spec = compile_remediation_overlay_spec(
        {
            "slug": "section-179-calculator",
            "query": "section 179 deduction calculator",
            "impressions": 80,
            "position": 7.5,
            "device_focus": "MOBILE_CTR_DEFICIT",
            "mobile_ctr_gap": 0.04,
            "search_appearances": ["PRODUCT_SNIPPETS"],
            "time_window_trajectory": "DECAYING",
            "coverage_state": "Submitted and indexed",
        },
        tenant_id="profithelm",
    )
    assert ov_spec["device_focus"] == "MOBILE_CTR_DEFICIT"
    assert ov_spec["search_appearances"] == ["PRODUCT_SNIPPETS"]
    assert ov_spec["time_window_trajectory"] == "DECAYING"

    # 3. Native compilation in compile_high_effort_page wires GSC telemetry into HTML, manifest, and JSON-LD
    compiled = compile_high_effort_page(
        {
            "property_id": "profithelm",
            "slug": "section-179-equipment-deduction-calculator",
            "query": "section 179 equipment deduction calculator",
            "title": "Section 179 Equipment Deduction Calculator and Statutory Analysis",
            "model_name": "Section 179 Statutory Deduction Engine",
            "formula": "min(equipment_cost, statutory_cap) * business_use_ratio",
            "inputs": {
                "equipment_cost": 150000,
                "statutory_cap": 1220000,
                "business_use_ratio": 1.0,
            },
            "published_output": 150000.0,
            "sample_calculation": "min(150000, 1220000) * 1.0 = 150000",
            "statutory_authority": "26 U.S.C. IRC Section 179 and IRS Publication 946",
            "economic_dataset": "BLS Producer Price Index for Machinery and Equipment (WPU11)",
            "device_focus": "MOBILE_CTR_DEFICIT",
            "mobile_impressions": 32,
            "desktop_impressions": 18,
            "mobile_ctr": 0.015,
            "desktop_ctr": 0.06,
            "mobile_ctr_gap": 0.045,
            "search_appearances": ["PRODUCT_SNIPPETS", "REVIEW_SNIPPET"],
            "time_window_trajectory": "ACCELERATING",
            "coverage_state": "Submitted and indexed",
        }
    )
    html_out = compiled["html"]
    assert 'data-gsc-device-focus="MOBILE_CTR_DEFICIT"' in html_out
    assert 'data-gsc-search-appearance="PRODUCT_SNIPPETS,REVIEW_SNIPPET"' in html_out
    assert 'data-gsc-trajectory="ACCELERATING"' in html_out
    assert 'data-gsc-coverage-state="Submitted and indexed"' in html_out
    assert '"featureList"' in html_out
    assert compiled["manifest"]["gsc_lifecycle_signals"]["device_focus"] == "MOBILE_CTR_DEFICIT"
    assert compiled["slot_plan"]["gsc_opportunity_tier"] == "MOBILE_CTR_DEFICIT_PROMOTION"

    # 4. Verify RetroReflectionEngine.retrofit_estate stamps GSC lifecycle attributes onto existing tenant dist HTML
    tenant_root = tmp_path / "tenant_repo"
    dist_dir = tenant_root / "dist"
    tool_dir = dist_dir / "tools" / "section-179-equipment-deduction-calculator"
    tool_dir.mkdir(parents=True, exist_ok=True)
    agy_dir = tenant_root / ".agy"
    agy_dir.mkdir(parents=True, exist_ok=True)
    (agy_dir / "gsc_lifecycle_telemetry.json").write_text(
        json.dumps(
            {
                "status": "PASS",
                "property_id": "profithelm",
                "dimensions_synced": {
                    "device_records_count": 2,
                    "search_appearance_records_count": 1,
                    "query_page_window_records_count": 2,
                    "url_inspection_records_count": 1,
                },
                "property_device_summary": {},
                "page_device_diagnostics": {
                    "/tools/section-179-equipment-deduction-calculator": {
                        "device_focus": "MOBILE_DOMINANT",
                    }
                },
                "search_appearances": {"PRODUCT_SNIPPETS": {"impressions": 5}},
                "time_window_velocity": {
                    "page_window_velocity": {
                        "/tools/section-179-equipment-deduction-calculator": {
                            "trajectory_state": "ACCELERATING",
                        }
                    }
                },
                "url_inspection_summary": {
                    "inspection_by_path": {
                        "/tools/section-179-equipment-deduction-calculator": {
                            "coverage_state": "Submitted and indexed",
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    # Strip the attributes first to prove retrofit_estate stamps them from .agy/gsc_lifecycle_telemetry.json
    unstamped_html = html_out.replace(
        'id="calculator-workspace-anchor" class="calculation-container card" data-gsc-device-focus="MOBILE_CTR_DEFICIT" data-gsc-search-appearance="PRODUCT_SNIPPETS,REVIEW_SNIPPET" data-gsc-trajectory="ACCELERATING" data-gsc-coverage-state="Submitted and indexed"',
        'id="calculator-workspace-anchor" class="calculation-container card"',
    )
    (tool_dir / "index.html").write_text(unstamped_html, encoding="utf-8")

    retro_res = RetroReflectionEngine.retrofit_estate(dist_dir, property_id="profithelm")
    assert retro_res["status"] == "PASS"
    retro_html = (tool_dir / "index.html").read_text(encoding="utf-8")
    assert 'data-gsc-device-focus="MOBILE_DOMINANT"' in retro_html
    assert 'data-gsc-search-appearance="PRODUCT_SNIPPETS"' in retro_html
    assert 'data-gsc-trajectory="ACCELERATING"' in retro_html

    fb_res = run_gsc_affiliate_placement_feedback_pass(
        property_id="profithelm",
        dist_dir=dist_dir,
        repo_root=tenant_root,
        gsc_rows=[
            {
                "slug": "section-179-equipment-deduction-calculator",
                "query": "section 179 equipment deduction calculator",
                "impressions": 40,
                "clicks": 2,
                "position": 4.5,
                "mobile_impressions": 28,
                "desktop_impressions": 12,
                "mobile_ctr": 0.015,
                "desktop_ctr": 0.065,
                "search_appearances": ["PRODUCT_SNIPPETS"],
            }
        ],
        dry_run=False,
    )
    assert fb_res["gsc_signal_slugs_count"] == 1
    assert (agy_dir / "gsc_affiliate_placement_ledger.json").is_file()


def test_stage_3_granular_url_inspection_classifications() -> None:
    """Verifies GSCRootCauseClassifier classifies all granular GSC URL Inspection states accurately."""
    classifier = GSCRootCauseClassifier()

    c_healthy = classifier.classify(
        url="https://prexvo.com/tools/rap-payment-calculator/",
        coverage_state="Submitted and indexed",
        verdict="PASS",
    )
    assert c_healthy.classification == RootCauseClassification.INDEXED_HEALTHY.value

    c_rich_defect = classifier.classify(
        url="https://prexvo.com/tools/rap-payment-calculator/",
        coverage_state="Submitted and indexed",
        rich_results_verdict="FAIL",
    )
    assert c_rich_defect.classification == RootCauseClassification.RICH_RESULT_OR_MOBILE_USABILITY_DEFECT.value

    c_noindex = classifier.classify(
        url="https://profithelm.com/tools/archived-calc/",
        coverage_state="Excluded by 'noindex' tag",
    )
    assert c_noindex.classification == RootCauseClassification.ROBOTS_OR_NOINDEX_EXCLUSION.value

    c_dup = classifier.classify(
        url="https://profithelm.com/tools/california-tax-brackets-2027/",
        coverage_state="Duplicate without user-selected canonical",
        user_canonical="https://profithelm.com/tools/california-tax-brackets-2027/",
        google_canonical="https://profithelm.com/tools/irs-2027-tax-brackets/california/",
    )
    assert c_dup.classification == RootCauseClassification.CANONICAL_TEMPLATE_DEFECT.value
    assert c_dup.metadata["google_canonical"].endswith("/tools/irs-2027-tax-brackets/california")
