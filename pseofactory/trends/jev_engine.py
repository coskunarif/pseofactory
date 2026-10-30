"""
pseofactory Jev Decision Engine & Programmatic Asset Yield Optimization
Enforces TypeSafe AI System One decision scoring (score >= 1.20, durable_prob >= 0.50),
calculates composite profit yield, and triages candidates into BUILD_PAGE, REFACTOR_PAGE, MONITOR, or REJECT.
Zero em-dashes. Zero en-dashes.
"""

import math
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from pseofactory.affiliates import qualify_monetization_opportunity
from pseofactory.contracts import assert_no_forbidden_dashes, assert_url_safe_slug
from pseofactory.trends.filters import classify_longitudinal_trajectory
from pseofactory.trends.models import TrendCandidate, TregDurabilityResult, JevDecisionResult


MIN_JEV_SCORE = 1.20
MIN_DURABLE_PROB = 0.50
MIN_BUILD_YIELD = 60.0


def calculate_normalized_velocity(z_score: float) -> float:
    """Normalizes z-score into [0.0, 1.0]. Saturated at z=5.0."""
    if z_score < 1.5:
        return 0.0
    return min(1.0, max(0.0, (z_score - 1.5) / 3.5))


def calculate_normalized_volume(search_volume: int) -> float:
    """Log-scales monthly volume from 1 to 100,000 queries into [0.0, 1.0]."""
    vol = max(1, search_volume)
    return min(1.0, max(0.0, math.log10(vol) / 5.0))


def calculate_intent_weight(intent_cluster: str, query: str) -> float:
    """Assigns programmatic monetization multiplier based on HWL-1080 3-Tier Indie Funnel."""
    q_low = query.lower()
    if any(w in q_low for w in ["meme", "remix", "soundboard", "dress", "gossip", "scrubbed", "leak"]):
        return 0.05
    if intent_cluster in ("calculator", "statutory_compliance") or any(
        w in q_low
        for w in (
            "calculator",
            "estimator",
            "matrix",
            "amortization",
            "deduction",
            "compliance",
            "forgiveness",
            "repayment",
        )
    ):
        return 1.0
    if intent_cluster == "comparison" or "vs" in q_low or "versus" in q_low or "compare" in q_low:
        return 0.7
    if intent_cluster == "tool":
        return 0.8
    if intent_cluster == "informational":
        return 0.3
    return 0.5


def determine_target_asset_type(query: str, intent_cluster: str) -> str:
    """Selects the highest-yield programmatic asset generator template."""
    q_low = query.lower()
    if "matrix" in q_low or "statutory" in q_low:
        return "statutory_matrix"
    if "calculator" in q_low or "estimator" in q_low or "calc" in q_low or intent_cluster == "calculator":
        return "interactive_calculator"
    if "vs" in q_low or "versus" in q_low or "comparison" in q_low or intent_cluster == "comparison":
        return "comparison_engine"
    if "tool" in q_low or intent_cluster == "tool":
        return "interactive_calculator"
    return "void_documentation"


class JevEngine:
    """
    Evaluates candidate topics against Jev durability invariant and computes composite profit yield.
    Applies Search Intent Doctrine triage (BUILD_PAGE, REFACTOR_PAGE, MONITOR, REJECT).
    """

    def __init__(
        self,
        min_score: float = MIN_JEV_SCORE,
        min_durable_prob: float = MIN_DURABLE_PROB,
        min_build_yield: float = MIN_BUILD_YIELD,
    ):
        self.min_score = min_score
        self.min_durable_prob = min_durable_prob
        self.min_build_yield = min_build_yield

    def resolve_jev_metrics(
        self,
        candidate: TrendCandidate,
        jev_mock: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, float]:
        """Resolves Jev score and durability probability from mock, client, or surrogate heuristics."""
        if jev_mock:
            return {
                "jev_score": float(jev_mock.get("jev_score", 0.0)),
                "durable_prob": float(jev_mock.get("durable_prob", 0.0)),
            }

        meta = candidate.metadata or {}
        if "jev_mock" in meta:
            m = meta["jev_mock"]
            return {
                "jev_score": float(m.get("jev_score", 0.0)),
                "durable_prob": float(m.get("durable_prob", 0.0)),
            }

        # Query heuristic fallback
        q_low = candidate.query.lower()
        if candidate.is_transient_noise:
            return {"jev_score": 0.15, "durable_prob": 0.05}

        if any(
            w in q_low
            for w in [
                "form",
                "section",
                "deduction",
                "calculator",
                "matrix",
                "estimator",
                "amortization",
                "compliance",
                "forgiveness",
                "1031",
                "179",
                "depreciation",
                "pslf",
                "repayment",
                "tariff",
                "hts",
                "nmfc",
                "surety",
                "bond",
                "workers comp",
                "lien",
                "retainage",
                "davis bacon",
                "cmmc",
                "sprs",
                "soc 2",
                "soc2",
                "hipaa",
                "nem 3.0",
                "demand charge",
                "srec",
                "wrvu",
                "rvu",
                "cpt",
                "cbct",
            ]
        ):
            return {"jev_score": 1.80, "durable_prob": 0.92}

        return {"jev_score": 1.25, "durable_prob": 0.55}

    def compute_composite_yield(
        self,
        candidate: TrendCandidate,
        treg_result: TregDurabilityResult,
        jev_score: float,
        durable_prob: float,
        cannibalization_risk: float,
        serp_weakness_count: int = 0,
    ) -> float:
        """
        Computes composite profit yield score in [0.0, 100.0]:
        CompositeYield = 100.0 * pow(0.35 * V_norm + 0.65 * S_norm, 0.85) * DecelPenalty * D * J_norm * max(0.0, 1.0 - R) * Y_asset
        Discounts risk R when serp_weakness_count >= 1 or position_zero_vacant is True.
        Untangles commercial B2B, consumer financial, student loan YMYL, and prospective niche expansion yields via qualify_monetization_opportunity.
        """
        v_norm = calculate_normalized_velocity(candidate.z_score)
        s_norm = calculate_normalized_volume(treg_result.search_volume)

        # Acceleration penalty per HWL-1215: 1.0 if A_t > 0 else (0.4 if volume >= 1000 else 0.0)
        if candidate.acceleration > 0.0:
            decel_penalty = 1.0
        elif treg_result.search_volume >= 1000:
            decel_penalty = 0.4
        else:
            decel_penalty = 0.0

        d = durable_prob
        j_norm = min(1.0, max(0.0, jev_score / 2.0))

        weakness_count = serp_weakness_count
        if weakness_count <= 0 and candidate.metadata:
            weakness_count = int(candidate.metadata.get("serp_weakness_count", 0))

        # Risk R blends cannibalization and keyword difficulty
        kd_norm = min(1.0, max(0.0, treg_result.keyword_difficulty / 100.0))
        r = 0.6 * cannibalization_risk + 0.4 * kd_norm

        # When serp_weakness_count >= 1, position_zero_vacant, or ai_citation_vacant, discount risk r
        ai_vacant = bool(getattr(treg_result, "ai_citation_vacant", False))
        if weakness_count >= 1 or treg_result.position_zero_vacant or ai_vacant:
            effective_weakness = max(1, weakness_count) if treg_result.position_zero_vacant else weakness_count
            if ai_vacant:
                effective_weakness += 1
            r_discount = max(0.60, 1.0 - 0.10 * min(effective_weakness, 4))
            r = r * r_discount

        monetization = qualify_monetization_opportunity(
            query=candidate.query,
            slug=candidate.slug,
            property_id=(candidate.metadata or {}).get("property_id"),
            search_volume=treg_result.search_volume,
            cpc_usd=treg_result.cpc_usd,
            jev_score=jev_score,
            durable_prob=durable_prob,
        )
        intent_tier = monetization.get("intent_tier", "")
        if intent_tier in ("cross_tenant_contamination", "out_of_scope_prexvo"):
            return 0.0

        y_intent = calculate_intent_weight(candidate.intent_cluster, candidate.query)
        cpc_norm = min(1.0, max(0.0, treg_result.cpc_usd / 10.0))
        base_y_asset = 0.7 * y_intent + 0.3 * cpc_norm

        tier_multiplier = 1.0
        if intent_tier == "commercial_b2b":
            tier_multiplier = 1.15
        elif intent_tier == "student_loan_ymyl":
            tier_multiplier = 1.08
        elif intent_tier == "prospective_niche_expansion":
            if int(monetization.get("active_offers_count", 0)) >= 2:
                tier_multiplier = 1.08
            else:
                tier_multiplier = 1.02
        elif intent_tier == "unmonetizable_noise":
            tier_multiplier = 0.15

        y_asset = base_y_asset * tier_multiplier

        gsc_meta = (candidate.metadata or {}).get("gsc_telemetry")
        if isinstance(gsc_meta, dict) and gsc_meta:
            gsc_mult = 1.0
            mob_gap = float(gsc_meta.get("mobile_ctr_gap", 0.0) or 0.0)
            if mob_gap >= 0.01:
                gsc_mult += min(0.04, mob_gap * 1.5)
            sa_list = gsc_meta.get("search_appearances") or []
            if any(sa in ("REVIEW_SNIPPET", "PRODUCT_SNIPPETS") for sa in sa_list):
                gsc_mult += 0.03
            traj = str(gsc_meta.get("time_window_trajectory") or "").upper()
            if traj in ("ACCELERATING", "BREAKOUT_NEW"):
                gsc_mult += 0.03
            elif traj == "DECAYING":
                gsc_mult += 0.02
            y_asset = y_asset * min(1.10, gsc_mult)

        meta_dict = candidate.metadata or {}
        source_cnt = int(meta_dict.get("source_count", 1) or 1)
        if source_cnt >= 2:
            corrob_mult = min(1.12, 1.0 + 0.04 * (source_cnt - 1))
            eff_partner_yield = float(monetization.get("effective_partner_yield", 0.0) or 0.0)
            if eff_partner_yield >= 25.0:
                corrob_mult = min(1.16, corrob_mult + 0.04)
            y_asset = y_asset * corrob_mult

        closed_loop = meta_dict.get("closed_loop_feedback")
        if isinstance(closed_loop, dict) and closed_loop:
            cl_mult = 1.0
            c_impr = int(closed_loop.get("gsc_cluster_impressions", 0) or 0)
            c_clicks = int(closed_loop.get("gsc_cluster_clicks", 0) or 0)
            wb_inter = int(closed_loop.get("workbench_interactions", 0) or 0)
            sc_pins = int(closed_loop.get("scenario_pins", 0) or 0)
            bp_saves = int(closed_loop.get("blueprint_saves", 0) or 0)
            ver_clicks = int(closed_loop.get("verified_outbound_clicks", 0) or 0)
            consec_cycles = int(closed_loop.get("consecutive_cycles", 1) or 1)
            deliv_reqs = int(closed_loop.get("deliverable_requests", 0) or 0)
            settled_upgs = int(closed_loop.get("settled_upgrades", 0) or 0)
            attr_rev_usd = float(closed_loop.get("attributed_revenue_usd", 0.0) or 0.0)
            if c_impr >= 10:
                cl_mult += min(0.11, math.log10(max(1, c_impr)) * 0.032)
            if c_clicks >= 1:
                cl_mult += min(0.08, c_clicks * 0.015)
            if wb_inter >= 1 or sc_pins >= 1 or bp_saves >= 1:
                cl_mult += min(0.12, wb_inter * 0.03 + sc_pins * 0.04 + bp_saves * 0.04)
            if ver_clicks >= 1:
                cl_mult += min(0.08, ver_clicks * 0.015)
            if consec_cycles >= 3:
                cl_mult += min(0.09, (consec_cycles - 2) * 0.035)
            has_realized_rev = bool(deliv_reqs >= 1 or settled_upgs >= 1 or attr_rev_usd > 0.0)
            if has_realized_rev:
                cl_mult += min(
                    0.22,
                    (attr_rev_usd / 400.0) * 0.12 + (settled_upgs * 0.025) + (deliv_reqs * 0.012),
                )
            max_cl = 1.48 if has_realized_rev else 1.34
            y_asset = y_asset * min(max_cl, cl_mult)

        momentum_core = 0.35 * v_norm + 0.65 * s_norm
        momentum_factor = math.pow(momentum_core, 0.85) if momentum_core > 0.0 else 0.0

        risk_discount = max(0.0, 1.0 - r)
        raw_yield = momentum_factor * decel_penalty * d * j_norm * risk_discount * y_asset
        yield_score = 100.0 * min(1.0, 1.50 * raw_yield)
        return max(0.0, min(100.0, yield_score))

    def evaluate(
        self,
        candidate: TrendCandidate,
        treg_result: TregDurabilityResult,
        cannibalization_context: Optional[Dict[str, Any]] = None,
        jev_mock: Optional[Dict[str, Any]] = None,
        position: float = 100.0,
        total_site_impressions: int = 500,
        serp_weakness_count: Optional[int] = None,
    ) -> JevDecisionResult:
        """
        Evaluates candidate against 5-step triage decision framework.
        Returns JevDecisionResult.
        Zero em-dashes. Zero en-dashes.
        """
        assert_no_forbidden_dashes(candidate.query, "JevEngine.evaluate.query")
        clean_q = candidate.query.strip()
        slug = candidate.slug or clean_q.replace(" ", "-").lower()
        assert_url_safe_slug(slug)

        jev_metrics = self.resolve_jev_metrics(candidate, jev_mock=jev_mock)
        jev_score = jev_metrics["jev_score"]
        durable_prob = jev_metrics["durable_prob"]

        cann_ctx = cannibalization_context or {}
        c_cannibal = float(cann_ctx.get("cannibalization_score", 0.0))
        matching_tool = cann_ctx.get("matches_existing_slug")
        pos = float(cann_ctx.get("current_position", position))

        weakness_cnt = (
            serp_weakness_count
            if serp_weakness_count is not None
            else int((candidate.metadata or {}).get("serp_weakness_count", 0))
        )

        monetization = qualify_monetization_opportunity(
            query=clean_q,
            slug=slug,
            property_id=(candidate.metadata or {}).get("property_id"),
            search_volume=treg_result.search_volume,
            cpc_usd=treg_result.cpc_usd,
            jev_score=jev_score,
            durable_prob=durable_prob,
        )

        composite_yield = self.compute_composite_yield(
            candidate=candidate,
            treg_result=treg_result,
            jev_score=jev_score,
            durable_prob=durable_prob,
            cannibalization_risk=c_cannibal,
            serp_weakness_count=weakness_cnt,
        )

        now_iso = datetime.now(timezone.utc).isoformat()
        target_asset = determine_target_asset_type(clean_q, candidate.intent_cluster)

        # Step 0: Cross-Tenant Isolation & Unmonetizable Signal Gate
        if monetization.get("intent_tier") in ("cross_tenant_contamination", "out_of_scope_prexvo"):
            return JevDecisionResult(
                query=clean_q,
                slug=slug,
                action="REJECT",
                jev_score=jev_score,
                durable_prob=durable_prob,
                composite_profit_yield=0.0,
                cannibalization_risk=c_cannibal,
                target_asset_type="none",
                decision_reason=monetization.get("rejection_reason", "Cross-tenant isolation rejection"),
                passed_thresholds=False,
                evaluated_at=now_iso,
            )

        # Step 1: Noise and Deceleration Gate
        q_low_clean = clean_q.lower()
        is_search_operator_noise = any(
            op in q_low_clean or op in slug
            for op in ("site:", "filetype:", "inurl:", "intitle:", "site-irs-gov")
        )
        if (
            candidate.is_transient_noise
            or is_search_operator_noise
            or (candidate.acceleration <= 0.0 and treg_result.search_volume < 1000)
            or candidate.z_score < 1.5
        ):
            reason = (
                "Search operator syntax rejected from autonomous build pipeline"
                if is_search_operator_noise
                else "Transient chatter or decelerating spike without established baseline volume"
            )
            return JevDecisionResult(
                query=clean_q,
                slug=slug,
                action="REJECT",
                jev_score=jev_score,
                durable_prob=durable_prob,
                composite_profit_yield=composite_yield,
                cannibalization_risk=c_cannibal,
                target_asset_type="none",
                decision_reason=reason,
                passed_thresholds=False,
                evaluated_at=now_iso,
            )

        # Step 1.5: Multi-Horizon 5-Year Trajectory & Breakout Low-Baseline Trap Gate (x-like:2098466289282842729)
        cand_meta = candidate.metadata or {}
        raw_series = cand_meta.get("longitudinal_series") or cand_meta.get("five_year_series")
        traj_eval = classify_longitudinal_trajectory(
            query=clean_q,
            series=raw_series if isinstance(raw_series, list) else None,
            velocity=candidate.velocity,
            acceleration=candidate.acceleration,
            search_volume=treg_result.search_volume,
            growth_pct=cand_meta.get("growth_pct"),
            is_breakout=bool(cand_meta.get("is_breakout", False)),
            cpc_usd=treg_result.cpc_usd,
            intent_cluster=candidate.intent_cluster,
            relative_index_0_100=cand_meta.get("relative_index_0_100"),
        )
        if traj_eval["classification"] == "POST_SPIKE_DECAY":
            return JevDecisionResult(
                query=clean_q,
                slug=slug,
                action="REJECT",
                jev_score=jev_score,
                durable_prob=durable_prob,
                composite_profit_yield=0.0,
                cannibalization_risk=c_cannibal,
                target_asset_type="none",
                decision_reason=str(traj_eval["reason"]),
                passed_thresholds=False,
                evaluated_at=now_iso,
            )
        if traj_eval["classification"] == "BREAKOUT_LOW_BASELINE_TRAP":
            return JevDecisionResult(
                query=clean_q,
                slug=slug,
                action="MONITOR",
                jev_score=jev_score,
                durable_prob=durable_prob,
                composite_profit_yield=composite_yield,
                cannibalization_risk=c_cannibal,
                target_asset_type="none",
                decision_reason=str(traj_eval["reason"]),
                passed_thresholds=False,
                evaluated_at=now_iso,
            )

        # Step 2: Jev Durability Threshold Gate
        if durable_prob < self.min_durable_prob or jev_score < self.min_score:
            reason = f"Failed Jev durability invariant threshold (score {jev_score:.2f} < {self.min_score:.2f} or durable_prob {durable_prob:.2f} < {self.min_durable_prob:.2f})"
            return JevDecisionResult(
                query=clean_q,
                slug=slug,
                action="REJECT",
                jev_score=jev_score,
                durable_prob=durable_prob,
                composite_profit_yield=composite_yield,
                cannibalization_risk=c_cannibal,
                target_asset_type="none",
                decision_reason=reason,
                passed_thresholds=False,
                evaluated_at=now_iso,
            )

        # Step 3: Cannibalization Triage Gate
        gsc_meta = cand_meta.get("gsc_telemetry")
        stat_matrix = cand_meta.get("statutory_economic_matrix")
        corrob_sources = list(cand_meta.get("corroborating_sources") or [])
        closed_loop_fb = cand_meta.get("closed_loop_feedback")
        if c_cannibal >= 0.50:
            tool_slug = matching_tool or "existing-tool"
            if 4.0 <= pos <= 20.0:
                lock_until = (datetime.now(timezone.utc) + timedelta(days=28)).strftime("%Y-%m-%dT%H:%M:%SZ")
                overlay_spec = {
                    "slug": tool_slug,
                    "measurement_lock_days": 28,
                    "locked_until": lock_until,
                    "target_injections": [clean_q],
                    "property_id": monetization.get("property_id", ""),
                    "intent_tier": monetization.get("intent_tier", ""),
                    "recommended_partners": monetization.get("recommended_partners", []),
                    "trajectory_classification": traj_eval,
                }
                if isinstance(gsc_meta, dict) and gsc_meta:
                    overlay_spec["gsc_telemetry"] = dict(gsc_meta)
                    overlay_spec["device_focus"] = str(gsc_meta.get("device_focus") or ("MOBILE_CTR_DEFICIT" if float(gsc_meta.get("mobile_ctr_gap", 0.0) or 0.0) >= 0.01 else "BALANCED"))
                    overlay_spec["search_appearances"] = list(gsc_meta.get("search_appearances") or [])
                if isinstance(stat_matrix, dict) and stat_matrix:
                    overlay_spec["statutory_economic_matrix"] = stat_matrix
                if corrob_sources:
                    overlay_spec["corroborating_sources"] = corrob_sources
                if isinstance(closed_loop_fb, dict) and closed_loop_fb:
                    overlay_spec["closed_loop_feedback"] = dict(closed_loop_fb)
                if getattr(treg_result, "ai_citation_checked", False):
                    overlay_spec["ai_citation_vacant"] = bool(treg_result.ai_citation_vacant)
                    overlay_spec["ai_cited_domains"] = list(treg_result.ai_cited_domains or [])
                reason = f"Striking distance query (pos {pos:.1f}) matches existing tool '{tool_slug}'; issue overlay spec with 28-day measurement lock per Search Intent Doctrine"
                return JevDecisionResult(
                    query=clean_q,
                    slug=slug,
                    action="REFACTOR_PAGE",
                    jev_score=jev_score,
                    durable_prob=durable_prob,
                    composite_profit_yield=composite_yield,
                    cannibalization_risk=c_cannibal,
                    target_asset_type=target_asset,
                    decision_reason=reason,
                    passed_thresholds=True,
                    evaluated_at=now_iso,
                    matching_tool=tool_slug,
                    overlay_spec=overlay_spec,
                )
            else:
                reason = f"Position {pos:.1f} matches existing tool '{tool_slug}'; preserve existing authority and prevent URL bloat"
                return JevDecisionResult(
                    query=clean_q,
                    slug=slug,
                    action="MONITOR",
                    jev_score=jev_score,
                    durable_prob=durable_prob,
                    composite_profit_yield=composite_yield,
                    cannibalization_risk=c_cannibal,
                    target_asset_type="none",
                    decision_reason=reason,
                    passed_thresholds=False,
                    evaluated_at=now_iso,
                    matching_tool=tool_slug,
                )

        # Step 3.5: Algorithmic Ceiling Suppression Guard
        ceiling_status = cand_meta.get("ceiling_status")
        if isinstance(ceiling_status, dict) and ceiling_status.get("ceiling_detected") and ceiling_status.get("recommendation") == "FREEZE_EXPANSION":
            c_score = float(ceiling_status.get("ceiling_dampening_score", 0.0) or 0.0)
            return JevDecisionResult(
                query=clean_q,
                slug=slug,
                action="MONITOR",
                jev_score=jev_score,
                durable_prob=durable_prob,
                composite_profit_yield=composite_yield,
                cannibalization_risk=c_cannibal,
                target_asset_type="none",
                decision_reason=f"Algorithmic ceiling active (dampening score {c_score:.2f}); freeze void expansion until authority recovery",
                passed_thresholds=False,
                evaluated_at=now_iso,
            )

        # Step 4: Build Page Qualification Gate (with Sponsor-Verified Monetization & AI Citation Void)
        kd_norm = min(1.0, max(0.0, treg_result.keyword_difficulty / 100.0))
        r_composite = 0.6 * c_cannibal + 0.4 * kd_norm
        ai_vacant = bool(getattr(treg_result, "ai_citation_vacant", False))
        p0_or_low_kd = (
            treg_result.position_zero_vacant
            or treg_result.keyword_difficulty < 25.0
            or (ai_vacant and treg_result.keyword_difficulty <= 38.0)
        )
        rec_partners = list(monetization.get("recommended_partners") or [])
        is_restricted_ps = bool(monetization.get("restricted_public_service", False))
        prop_id_resolved = str(monetization.get("property_id") or "")
        bounty_est_val = float(monetization.get("expected_bounty_usd", 0.0) or 0.0)
        from pseofactory.tenant_facts import CANONICAL_TENANT_IDS
        sponsor_coverage_verified = bool(
            monetization.get("partner_alignment_verified", True)
            and (
                (len(rec_partners) >= 1 and bounty_est_val >= 25.0)
                or is_restricted_ps
                or prop_id_resolved not in CANONICAL_TENANT_IDS
            )
        )
        is_non_tool_question = (
            target_asset == "void_documentation"
            and q_low_clean.startswith(("can you ", "how do i ", "what is a ", "why does "))
        )

        if (
            composite_yield >= self.min_build_yield
            and r_composite < 0.40
            and c_cannibal < 0.50
            and p0_or_low_kd
            and monetization.get("monetization_qualified", False)
            and sponsor_coverage_verified
            and not is_non_tool_question
        ):
            reason = f"High-yield durable void (yield {composite_yield:.1f} >= {self.min_build_yield:.1f}) with vacant Position 0 and zero cannibalization"
            candidate_spec = {
                "query": clean_q,
                "slug": slug,
                "primary_keyword": clean_q.lower(),
                "target_asset_type": target_asset,
                "composite_profit_yield": round(composite_yield, 2),
                "search_volume": treg_result.search_volume,
                "cpc_usd": treg_result.cpc_usd,
                "keyword_difficulty": treg_result.keyword_difficulty,
                "position_zero_vacant": treg_result.position_zero_vacant,
                "ai_citation_vacant": ai_vacant,
                "ai_cited_domains": list(getattr(treg_result, "ai_cited_domains", None) or []),
                "status": "APPROVED_BUILD",
                "discovered_at": candidate.discovered_at,
                "property_id": prop_id_resolved,
                "intent_tier": monetization.get("intent_tier", ""),
                "monetization_qualified": monetization.get("monetization_qualified", False),
                "monetization_rail_mix": monetization.get("monetization_rail_mix", "unmonetized"),
                "stripe_digital_asset": monetization.get("stripe_digital_asset", {}),
                "b2b_quote_intake": monetization.get("b2b_quote_intake", {}),
                "sponsor_coverage_verified": sponsor_coverage_verified,
                "primary_partner": monetization.get("primary_partner", ""),
                "recommended_partners": rec_partners,
                "expected_bounty_usd": monetization.get("expected_bounty_usd", 0.0),
                "effective_partner_yield": monetization.get("effective_partner_yield", 0.0),
                "estimated_monthly_revenue_usd": monetization.get("estimated_monthly_revenue_usd", 0.0),
                "estimated_stripe_asset_monthly_revenue_usd": monetization.get("estimated_stripe_asset_monthly_revenue_usd", 0.0),
                "total_compounded_monthly_revenue_usd": monetization.get("total_compounded_monthly_revenue_usd", 0.0),
                "partner_alignment_verified": monetization.get("partner_alignment_verified", True),
                "mandatory_disclosures": monetization.get("disclosures_required", {}),
                "monetization_qualification": monetization,
                "trajectory_classification": traj_eval,
            }
            if isinstance(gsc_meta, dict) and gsc_meta:
                candidate_spec["gsc_telemetry"] = dict(gsc_meta)
                candidate_spec["device_focus"] = str(gsc_meta.get("device_focus") or "BALANCED")
                candidate_spec["search_appearances"] = list(gsc_meta.get("search_appearances") or [])
            if isinstance(stat_matrix, dict) and stat_matrix:
                candidate_spec["statutory_economic_matrix"] = stat_matrix
            if corrob_sources:
                candidate_spec["corroborating_sources"] = corrob_sources
            if isinstance(closed_loop_fb, dict) and closed_loop_fb:
                candidate_spec["closed_loop_feedback"] = dict(closed_loop_fb)
            return JevDecisionResult(
                query=clean_q,
                slug=slug,
                action="BUILD_PAGE",
                jev_score=jev_score,
                durable_prob=durable_prob,
                composite_profit_yield=composite_yield,
                cannibalization_risk=c_cannibal,
                target_asset_type=target_asset,
                decision_reason=reason,
                passed_thresholds=True,
                evaluated_at=now_iso,
                candidate_spec=candidate_spec,
            )

        # Step 5: Exploratory Volume Gate
        dynamic_floor = max(2, min(25, int(0.05 * total_site_impressions)))
        reason = f"Early momentum or exploratory volume below qualification floor ({dynamic_floor}); monitor for trend consolidation"
        return JevDecisionResult(
            query=clean_q,
            slug=slug,
            action="MONITOR",
            jev_score=jev_score,
            durable_prob=durable_prob,
            composite_profit_yield=composite_yield,
            cannibalization_risk=c_cannibal,
            target_asset_type="none",
            decision_reason=reason,
            passed_thresholds=False,
            evaluated_at=now_iso,
        )
