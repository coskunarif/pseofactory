"""
pseofactory End-to-End Trend Ingestion & Jev Decision Pipeline
Orchestrates multi-source breakout spikes, noise suppression, treg cross-checking,
cannibalization qualification, and Jev decision rankings with atomic flock persistence (HWL-1253).
Zero em-dashes. Zero en-dashes.
"""

import os
import json
import fcntl
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

from pseofactory.contracts import (
    assert_no_forbidden_dashes,
    assert_no_prompt_leakage,
    assert_url_safe_slug,
    sanitize_url_slug,
)
from pseofactory.qualification import check_search_intent_cannibalization
from pseofactory.trends.models import (
    FeedSpike,
    TrendCandidate,
    TregDurabilityResult,
    JevDecisionResult,
)
from pseofactory.trends.filters import NoiseFilter
from pseofactory.trends.treg_checker import TregChecker
from pseofactory.trends.jev_engine import JevEngine


class TrendPipeline:
    """
    Autonomous pipeline taking raw breakout spikes to validated programmatic assets.
    Enforces HWL-1215 discrete acceleration gating, treg volume checks, and Jev thresholding.
    """

    def __init__(
        self,
        noise_filter: Optional[NoiseFilter] = None,
        treg_checker: Optional[TregChecker] = None,
        jev_engine: Optional[JevEngine] = None,
    ):
        self.noise_filter = noise_filter or NoiseFilter()
        self.treg_checker = treg_checker or TregChecker()
        self.jev_engine = jev_engine or JevEngine()

    def process_spikes(
        self,
        raw_spikes: List[Union[FeedSpike, Dict[str, Any]]],
        existing_tools: Optional[List[Dict[str, Any]]] = None,
        sitemap_urls: Optional[List[str]] = None,
        sink_path: Optional[Union[str, Path]] = None,
        total_site_impressions: int = 500,
    ) -> Dict[str, Any]:
        """
        Executes end-to-end processing across raw breakout spikes.
        Zero em-dashes. Zero en-dashes.
        """
        spikes: List[FeedSpike] = []
        for s in raw_spikes:
            if isinstance(s, FeedSpike):
                spikes.append(s)
            elif isinstance(s, dict):
                spikes.append(FeedSpike.from_dict(s))

        total_spikes = len(spikes)
        filtered_noise: List[TrendCandidate] = []
        candidates_to_eval: List[TrendCandidate] = []
        results: List[JevDecisionResult] = []

        # 1. Noise suppression & HWL-1215 acceleration filtering
        for spike in spikes:
            # Check for embedded treg mock in raw spike payload or metadata to inform acceleration gate
            treg_hint_vol = 0
            if spike.raw_payload and "treg_mock" in spike.raw_payload:
                treg_hint_vol = int(spike.raw_payload["treg_mock"].get("search_volume", 0))

            passes, reason, cand = self.noise_filter.evaluate_spike(spike, search_volume=treg_hint_vol)
            if not passes or cand.is_transient_noise:
                filtered_noise.append(cand)
                # HWL-1252: Transition rejected items out of PENDING
                rej_decision = JevDecisionResult(
                    query=cand.query,
                    slug=cand.slug,
                    action="REJECT",
                    jev_score=0.10,
                    durable_prob=0.05,
                    composite_profit_yield=0.0,
                    cannibalization_risk=0.0,
                    target_asset_type="none",
                    decision_reason=reason,
                    passed_thresholds=False,
                    evaluated_at=cand.discovered_at,
                )
                results.append(rej_decision)
            else:
                candidates_to_eval.append(cand)

        # 2. Process viable candidates surviving noise filter
        for cand in candidates_to_eval:
            # Treg demand cross-check
            mock_treg = None
            raw_meta = cand.metadata or {}
            if "treg_mock" in raw_meta:
                mock_treg = raw_meta["treg_mock"]

            treg_res = self.treg_checker.check_query(cand.query, mock_override=mock_treg)

            # Check search intent cannibalization against existing catalog
            cannibal_info = check_search_intent_cannibalization(
                cand.query,
                existing_tools=existing_tools,
                sitemap_urls=sitemap_urls,
            )

            cann_score = 0.0
            matching_tool = None
            pos = 100.0

            if cannibal_info.get("is_cannibalizing"):
                cann_score = 0.85
                matching_tool = cannibal_info.get("parent_slug")

            # Check if cannibalization context was pre-supplied (e.g. from evaluation fixtures)
            if "cannibalization_context" in raw_meta:
                cc = raw_meta["cannibalization_context"]
                cann_score = float(cc.get("cannibalization_score", cann_score))
                if cc.get("matches_existing_slug"):
                    matching_tool = str(cc["matches_existing_slug"])
                pos = float(cc.get("current_position", pos))

            cann_ctx = {
                "cannibalization_score": cann_score,
                "matches_existing_slug": matching_tool,
                "current_position": pos,
            }

            mock_jev = raw_meta.get("jev_mock")

            # Jev decision scoring and strategic triage
            decision = self.jev_engine.evaluate(
                candidate=cand,
                treg_result=treg_res,
                cannibalization_context=cann_ctx,
                jev_mock=mock_jev,
                position=pos,
                total_site_impressions=total_site_impressions,
            )
            results.append(decision)

        # 3. Content invariant assertions on all generated decisions
        for dec in results:
            assert_no_forbidden_dashes(dec.query, "pipeline.dec.query")
            assert_no_forbidden_dashes(dec.slug, "pipeline.dec.slug")
            assert_no_forbidden_dashes(dec.decision_reason, "pipeline.dec.decision_reason")
            assert_no_prompt_leakage(dec.decision_reason, "pipeline.dec.decision_reason")
            if dec.slug:
                assert_url_safe_slug(dec.slug)

        # 4. Partition by triage action
        approved_build = [d for d in results if d.action == "BUILD_PAGE"]
        refactor_pages = [d for d in results if d.action == "REFACTOR_PAGE"]
        monitored = [d for d in results if d.action == "MONITOR"]
        rejected = [d for d in results if d.action == "REJECT"]

        # Sort all results by composite profit yield descending
        rankings = sorted(results, key=lambda d: d.composite_profit_yield, reverse=True)

        # 5. HWL-1253: Atomic file sink persistence under flock lock
        if sink_path:
            sink_file = Path(sink_path).resolve()
            sink_file.parent.mkdir(parents=True, exist_ok=True)
            with open(sink_file, "a", encoding="utf-8") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    for d in rankings:
                        record = d.to_dict()
                        f.write(json.dumps(record) + "\n")
                    f.flush()
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)

        return {
            "total_spikes": total_spikes,
            "filtered_noise_count": len(filtered_noise),
            "evaluated_candidates_count": len(candidates_to_eval),
            "approved_build": [d.to_dict() for d in approved_build],
            "refactor_pages": [d.to_dict() for d in refactor_pages],
            "monitored": [d.to_dict() for d in monitored],
            "rejected": [d.to_dict() for d in rejected],
            "rankings": [d.to_dict() for d in rankings],
        }


def run_trend_pipeline(
    spikes: List[Union[FeedSpike, Dict[str, Any]]],
    existing_tools: Optional[List[Dict[str, Any]]] = None,
    sitemap_urls: Optional[List[str]] = None,
    sink_path: Optional[Union[str, Path]] = None,
    total_site_impressions: int = 500,
    noise_filter: Optional[NoiseFilter] = None,
    treg_checker: Optional[TregChecker] = None,
    jev_engine: Optional[JevEngine] = None,
) -> Dict[str, Any]:
    """Convenience helper to run the complete trend pipeline."""
    pipe = TrendPipeline(
        noise_filter=noise_filter,
        treg_checker=treg_checker,
        jev_engine=jev_engine,
    )
    return pipe.process_spikes(
        raw_spikes=spikes,
        existing_tools=existing_tools,
        sitemap_urls=sitemap_urls,
        sink_path=sink_path,
        total_site_impressions=total_site_impressions,
    )
