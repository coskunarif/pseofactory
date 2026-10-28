"""
Regression suite for x-like:2102328294410461564 (@JespernissenSEO / Jesper Nissen:
"How to find Parasite SEO keywords" - https://youtu.be/MYEqgkuiObw, someposter.ai,
yacss.site, schemawriter.ai).

Validates:
1. Differential capability matrix (X_LIKE_2102328294410461564_CAPABILITY_MATRIX) and live
   multi-tenant evaluation across ProfitHelm, Prexvo, and GainHelm.
2. Dual-stream commercial + conversational question keyword expansion and high-KD
   question-dominant ratio shift (content_angles.expand_commercial_and_question_keywords),
   plus off-vertical local geo-doorway seed rejection ("flat roof repair Austin").
3. Multi-platform social/video SERP vulnerability scanning and off-topic partial-token
   collision detection ("Austin Haye" LinkedIn post matching city token "Austin").
4. Gate S5 anti-parasite link-wheel enforcement (blocking "Target Post" Facebook/YACSS
   daisy-chaining) and YouTube human-readable title verification across all tenants.
5. Workflow 4 (compile_search_opportunity_briefs) integration of commercial_vs_question_keyword_mix
   and serp_social_vulnerability.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import copy

from pseofactory.audit import (
    X_LIKE_2102328294410461564_CAPABILITY_MATRIX,
    audit_code_slop_ratchet,
    audit_syndication_asset_against_truth_store,
    evaluate_x_like_2102328294410461564_capability_matrix,
)
from pseofactory.content_angles import (
    analyze_serp_social_vulnerability,
    classify_serp_incumbent,
    detect_off_topic_token_collision,
    expand_commercial_and_question_keywords,
)
from pseofactory.contracts import assert_no_forbidden_dashes
from pseofactory.distributor import generate_all_distribution_assets
from pseofactory.seo_growth_loops import compile_search_opportunity_briefs


def test_x_like_2102328294410461564_capability_matrix_and_live_estate() -> None:
    assert len(X_LIKE_2102328294410461564_CAPABILITY_MATRIX) == 8
    valid_dispositions = {
        "INTEGRATED_COMPOUNDING_UPGRADE",
        "INTEGRATED_DETERMINISTIC_GATE",
        "ALREADY_SOLVED_IN_SUBSTRATE",
        "REJECTED_BLOAT_OR_OFF_VERTICAL",
    }
    for entry in X_LIKE_2102328294410461564_CAPABILITY_MATRIX:
        assert entry["disposition"] in valid_dispositions
        assert entry.get("claim_name")
        assert entry.get("video_chapter")
        assert entry.get("pseofactory_stage")
        assert entry.get("vault_surface")
        assert len(entry.get("case_for", "")) >= 30
        assert len(entry.get("case_against", "")) >= 30
        assert_no_forbidden_dashes(str(entry), context=f"claim_{entry['claim_id']}")

    report = evaluate_x_like_2102328294410461564_capability_matrix(include_live_audit=True)
    assert report["pointer"] == "x-like:2102328294410461564"
    assert report["author_handle"] == "JespernissenSEO"
    assert report["youtube_url"] == "https://youtu.be/MYEqgkuiObw"
    assert report["integrated_compounding_upgrades_count"] == 4
    assert report["integrated_deterministic_gates_count"] == 1
    assert report["already_solved_in_substrate_count"] == 1
    assert report["rejected_bloat_or_off_vertical_count"] == 2
    assert report["passed"] is True
    assert report["status"] == "PASS"

    for tenant in ("profithelm", "prexvo"):
        t_sum = report["tenant_summaries"][tenant]
        assert t_sum["status"] == "PASS"
        assert t_sum["estate_issues_count"] == 0
        assert t_sum["syndication_failures"] == []
        assert t_sum["youtube_slug_title_leaks"] == []


def test_dual_stream_commercial_and_question_keyword_expansion_and_kd_shift() -> None:
    for tenant, seed in (
        ("profithelm", "section 179 calculator"),
        ("prexvo", "rap payment calculator"),
        ("gainhelm", "cmmc 2.0 compliance cost calculator"),
    ):
        balanced = expand_commercial_and_question_keywords(
            seed_query=seed,
            property_id=tenant,
            keyword_difficulty=40.0,
            total_keywords=20,
        )
        assert balanced["status"] == "PASS"
        assert balanced["mode"] == "BALANCED_COMMERCIAL_AND_QUESTION"
        assert balanced["commercial_count"] == 10
        assert balanced["question_count"] == 10
        assert balanced["commercial_ratio"] == 0.5
        assert balanced["question_ratio"] == 0.5
        assert len(balanced["all_keywords"]) == 20
        assert any(
            q.startswith(("how ", "should ", "does ", "when ", "what ", "why ", "who ", "can ", "is "))
            for q in balanced["question_keywords"]
        )

        high_kd = expand_commercial_and_question_keywords(
            seed_query=seed,
            property_id=tenant,
            keyword_difficulty=72.0,
            total_keywords=20,
        )
        assert high_kd["status"] == "PASS"
        assert high_kd["mode"] == "HIGH_KD_QUESTION_DOMINANT"
        assert high_kd["commercial_count"] == 0
        assert high_kd["question_count"] == 20
        assert high_kd["commercial_ratio"] == 0.0
        assert high_kd["question_ratio"] == 1.0

    # Off-vertical local geo-doorway seeds from the video must be rejected deterministically
    for doorway_seed in ("flat roof repair Austin", "roofing companies Austin Texas"):
        rejected = expand_commercial_and_question_keywords(
            seed_query=doorway_seed,
            property_id="profithelm",
            keyword_difficulty=35.0,
        )
        assert rejected["status"] == "REJECTED_OFF_VERTICAL_DOORWAY"
        assert rejected["mode"] == "REJECTED"
        assert rejected["all_keywords"] == []


def test_off_topic_token_collision_and_serp_social_vulnerability() -> None:
    # Exact pattern from x-like:2102328294410461564 (3:12 - 3:47):
    # LinkedIn post for "Austin Haye - Applied AI Growth System and Ops" ranking for a query
    # containing city token "Austin" while missing all core problem tokens.
    off_topic_item = {
        "rank": 4,
        "domain": "www.linkedin.com",
        "url": "https://www.linkedin.com/posts/austin-haye-applied-ai-growth-system",
        "title": "Austin Haye - Applied AI Growth System and Ops",
        "snippet": "Building RevOps and GTM automation pipelines for agencies.",
    }
    collision = detect_off_topic_token_collision(
        off_topic_item,
        target_query="section 1031 exchange Austin",
    )
    assert collision["is_off_topic_collision"] is True
    assert collision["weakness_category"] == "AUDIENCE_MISMATCH"
    assert "austin" in collision["matched_ambiguous_tokens"]
    assert "1031" in collision["missing_core_problem_tokens"]

    incumbent = classify_serp_incumbent(off_topic_item, target_query="section 1031 exchange Austin")
    assert incumbent.weakness_category == "AUDIENCE_MISMATCH"
    assert "Off-topic token collision" in incumbent.weakness_detail

    # Genuine relevant result must NOT be flagged as an off-topic token collision
    on_topic_item = {
        "rank": 2,
        "domain": "www.linkedin.com",
        "url": "https://www.linkedin.com/pulse/section-1031-exchange-austin-tax-deferral",
        "title": "IRC Section 1031 Exchange Tax Deferral Rules in Austin",
        "snippet": "Calculating boot and 45-day identification rules for Austin commercial real estate.",
    }
    no_collision = detect_off_topic_token_collision(
        on_topic_item,
        target_query="section 1031 exchange Austin",
    )
    assert no_collision["is_off_topic_collision"] is False

    serp_sample = [
        {"rank": 1, "domain": "youtube.com", "title": "Should I use Section 1031 or pay capital gains in Austin?"},
        {"rank": 2, "domain": "reddit.com", "title": "r/realestateinvesting - 1031 exchange timeline question"},
        {"rank": 3, "domain": "facebook.com", "title": "Texas Commercial Investors Group - 1031 exchange rules"},
        off_topic_item,
        {"rank": 5, "domain": "irs.gov", "title": "Like-Kind Exchanges Under IRC Section 1031"},
    ]
    vuln = analyze_serp_social_vulnerability(serp_sample, target_query="section 1031 exchange Austin")
    assert vuln["total_social_slots"] == 4
    assert vuln["platform_counts"]["youtube"] == 1
    assert vuln["platform_counts"]["reddit"] == 1
    assert vuln["platform_counts"]["facebook"] == 1
    assert vuln["platform_counts"]["linkedin"] == 1
    assert vuln["off_topic_collisions_count"] == 1
    assert vuln["vulnerability_tier"] == "HIGH_MULTI_SURFACE_OPENING"
    assert "reddit" in vuln["prohibited_channels"]
    assert "youtube" in vuln["authorized_displacement_channels"]


def test_anti_parasite_link_wheel_gate_and_gainhelm_youtube_titles() -> None:
    gainhelm_assets = generate_all_distribution_assets(property_id="gainhelm")
    assert "cmmc-2-0-compliance-cost-calculator" in gainhelm_assets
    cmmc_pack = gainhelm_assets["cmmc-2-0-compliance-cost-calculator"]

    # Verify GainHelm YouTube title is clean and human-readable (not raw slug)
    yt_title = cmmc_pack["youtube"]["title"]
    assert not yt_title.lower().startswith("cmmc-2-0-compliance-cost-calculator")
    assert "CMMC 2.0" in yt_title
    assert "keyword_intent_matrix" in cmmc_pack
    assert len(cmmc_pack["keyword_intent_matrix"]["question_keywords"]) == 5
    assert len(cmmc_pack["keyword_intent_matrix"]["commercial_keywords"]) == 5

    clean_audit = audit_syndication_asset_against_truth_store(cmmc_pack, property_id="gainhelm")
    assert clean_audit["passed"] is True

    # Mutate LinkedIn target_url to a Facebook "Target Post" link-wheel intermediary (Tactic 8 in video)
    daisy_chained = copy.deepcopy(cmmc_pack)
    daisy_chained["linkedin"]["target_url"] = "https://www.facebook.com/someposter/posts/99887766?ref=target_post"
    wheel_audit = audit_syndication_asset_against_truth_store(daisy_chained, property_id="gainhelm")
    assert wheel_audit["passed"] is False
    assert any("PARASITE_LINK_WHEEL_INTERMEDIARY_DETECTED" in v for v in wheel_audit["violations"])

    # Mutate X first_comment to point to a YACSS cloud bucket link wheel
    yacss_chained = copy.deepcopy(cmmc_pack)
    yacss_chained["x"]["first_comment"] = "Run your numbers here: https://yacss.site/cmmc-wheel/index.html?tier=2"
    yacss_audit = audit_syndication_asset_against_truth_store(yacss_chained, property_id="gainhelm")
    assert yacss_audit["passed"] is False
    assert any("PARASITE_LINK_WHEEL_INTERMEDIARY_DETECTED" in v for v in yacss_audit["violations"])


def test_workflow_4_briefs_include_commercial_question_mix_and_slop_ratchet() -> None:
    briefs_rep = compile_search_opportunity_briefs(
        property_id="profithelm",
        apply_overlays=False,
        persist=False,
    )
    assert briefs_rep["status"] == "PASS"
    assert len(briefs_rep["briefs"]) > 0
    first_brief = briefs_rep["briefs"][0]
    assert "commercial_vs_question_keyword_mix" in first_brief
    mix = first_brief["commercial_vs_question_keyword_mix"]
    assert mix["mode"] in ("BALANCED_COMMERCIAL_AND_QUESTION", "HIGH_KD_QUESTION_DOMINANT")
    assert len(mix["question_keywords"]) > 0
    assert "serp_social_vulnerability" in first_brief
    assert "reddit" in first_brief["serp_social_vulnerability"]["prohibited_channels"]

    ratchet = audit_code_slop_ratchet()
    assert ratchet["passed"] is True, f"Slop ratchet failed: {ratchet}"
