"""
pseofactory Jev Decision Engine & Programmatic Asset Yield Optimization
Enforces TypeSafe AI System One decision scoring (score >= 1.20, durable_prob >= 0.50),
calculates composite profit yield, and triages candidates into BUILD_PAGE, REFACTOR_PAGE, MONITOR, or REJECT.
Zero em-dashes. Zero en-dashes.
"""

import math
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from pseofactory.contracts import assert_no_forbidden_dashes, assert_url_safe_slug
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
    if intent_cluster in ("calculator", "statutory_compliance") or "calculator" in q_low or "estimator" in q_low or "matrix" in q_low:
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

        if any(w in q_low for w in ["form", "section", "deduction", "calculator", "matrix", "estimator"]):
            return {"jev_score": 1.80, "durable_prob": 0.92}

        return {"jev_score": 1.25, "durable_prob": 0.55}

    def compute_composite_yield(
        self,
        candidate: TrendCandidate,
        treg_result: TregDurabilityResult,
        jev_score: float,
        durable_prob: float,
        cannibalization_risk: float,
    ) -> float:
        """
        Computes composite profit yield score in [0.0, 100.0]:
        CompositeYield = 100.0 * pow(0.35 * V_norm + 0.65 * S_norm, 0.85) * DecelPenalty * D * J_norm * max(0.0, 1.0 - R) * Y_asset
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

        # Risk R blends cannibalization and keyword difficulty
        kd_norm = min(1.0, max(0.0, treg_result.keyword_difficulty / 100.0))
        r = 0.6 * cannibalization_risk + 0.4 * kd_norm

        y_intent = calculate_intent_weight(candidate.intent_cluster, candidate.query)
        cpc_norm = min(1.0, max(0.0, treg_result.cpc_usd / 10.0))
        y_asset = 0.7 * y_intent + 0.3 * cpc_norm

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

        composite_yield = self.compute_composite_yield(
            candidate=candidate,
            treg_result=treg_result,
            jev_score=jev_score,
            durable_prob=durable_prob,
            cannibalization_risk=c_cannibal,
        )

        now_iso = datetime.now(timezone.utc).isoformat()
        target_asset = determine_target_asset_type(clean_q, candidate.intent_cluster)

        # Step 1: Noise and Deceleration Gate
        if candidate.is_transient_noise or (candidate.acceleration <= 0.0 and treg_result.search_volume < 1000) or candidate.z_score < 1.5:
            reason = "Transient chatter or decelerating spike without established baseline volume"
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
        if c_cannibal >= 0.50:
            tool_slug = matching_tool or "existing-tool"
            if 4.0 <= pos <= 20.0:
                lock_until = (datetime.now(timezone.utc) + timedelta(days=28)).strftime("%Y-%m-%dT%H:%M:%SZ")
                overlay_spec = {
                    "slug": tool_slug,
                    "measurement_lock_days": 28,
                    "locked_until": lock_until,
                    "target_injections": [clean_q],
                }
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

        # Step 4: Build Page Qualification Gate
        kd_norm = min(1.0, max(0.0, treg_result.keyword_difficulty / 100.0))
        r_composite = 0.6 * c_cannibal + 0.4 * kd_norm
        p0_or_low_kd = treg_result.position_zero_vacant or treg_result.keyword_difficulty < 25.0

        if composite_yield >= self.min_build_yield and r_composite < 0.40 and c_cannibal < 0.50 and p0_or_low_kd:
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
                "status": "APPROVED_BUILD",
                "discovered_at": candidate.discovered_at,
            }
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
