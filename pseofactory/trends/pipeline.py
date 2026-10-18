"""
pseofactory End-to-End Trend Ingestion & Jev Decision Pipeline
Orchestrates multi-source breakout spikes, noise suppression, treg cross-checking,
cannibalization qualification, and Jev decision rankings with atomic flock persistence (HWL-1253).
Zero em-dashes. Zero en-dashes.
"""

import os
import time
import json
import fcntl
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Set

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


def compute_trend_idempotency_key(record: Dict[str, Any]) -> str:
    """
    Computes composite idempotency key (tenant_id:slug:action:payload_hash)
    to prevent duplicate delivery churn in void_candidates.jsonl across cron cycles.
    Zero em-dashes. Zero en-dashes.
    """
    existing = str(record.get("idempotency_key") or "").strip()
    if existing:
        return existing
    cand_spec = record.get("candidate_spec") if isinstance(record.get("candidate_spec"), dict) else {}
    tenant_id = str(
        record.get("tenant_id")
        or record.get("property_id")
        or cand_spec.get("property_id")
        or "unassigned"
    ).strip().lower()
    slug = str(record.get("slug") or "").strip().lower()
    action = str(record.get("action") or "").strip().upper()
    query = " ".join(str(record.get("query") or "").strip().lower().split())
    target_asset = str(record.get("target_asset_type") or "none").strip().lower()
    payload_hash = hashlib.sha256(f"{query}:{action}:{target_asset}".encode("utf-8")).hexdigest()[:16]
    return f"{tenant_id}:{slug}:{action}:{payload_hash}"


# Engine triage actions that tenants may act on. Every other verdict (MONITOR, REJECT)
# is persisted as REJECTED so tenant consumers that default a missing status to
# PENDING never synthesize assets the engine already declined.
ACTIONABLE_ENGINE_ACTIONS = frozenset({"BUILD_PAGE", "REFACTOR_PAGE"})


def stamp_engine_verdict_status(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stamps the shared void_candidates lifecycle status from the Jev engine verdict,
    while blocking resurrection of consolidated/retired clones or synthetic test fixtures.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.qualification import (
        CANNIBALIZING_CLONE_CONSOLIDATION_MAP,
        PREXVO_CANNIBALIZING_CLONE_CONSOLIDATION_MAP,
        is_synthetic_test_candidate,
    )

    raw_slug = str(record.get("slug") or "").strip().lower()
    raw_query = str(record.get("query") or record.get("primary_keyword") or "").strip().lower()
    slug_from_query = sanitize_url_slug(raw_query) if raw_query else ""
    eff_slug = raw_slug or slug_from_query

    if is_synthetic_test_candidate(eff_slug or raw_query, record):
        record["status"] = "REJECTED"
        record["action"] = "REJECT"
        record["status_reason"] = "Rejected synthetic or off-topic candidate"
        return record

    all_clone_maps = {**PREXVO_CANNIBALIZING_CLONE_CONSOLIDATION_MAP, **CANNIBALIZING_CLONE_CONSOLIDATION_MAP}
    matched_clone = eff_slug if eff_slug in all_clone_maps else (slug_from_query if slug_from_query in all_clone_maps else "")
    if matched_clone:
        info = all_clone_maps[matched_clone]
        record["status"] = "REJECTED"
        record["action"] = "REFACTOR_PAGE"
        record["consolidation_status"] = "CONSOLIDATED_REDIRECT"
        record["canonical_slug"] = info["canonical_slug"]
        record["redirect_target"] = info["redirect_target"]
        record["status_reason"] = f"Consolidated into canonical hub {info['canonical_slug']} ({info['redirect_target']})"
        return record

    if record.get("status"):
        return record
    action = str(record.get("action") or "").strip().upper()
    if action in ACTIONABLE_ENGINE_ACTIONS:
        record["status"] = "PENDING"
    else:
        record["status"] = "REJECTED"
        record["status_reason"] = f"Engine verdict {action or 'UNKNOWN'}: {record.get('decision_reason') or 'not actionable'}"
    return record


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
        batch_size: int = 15,
        cycle_budget: float = 240.0,
        db: Optional[Any] = None,
    ):
        self.noise_filter = noise_filter or NoiseFilter()
        if treg_checker is not None:
            self.treg_checker = treg_checker
        else:
            self.treg_checker = TregChecker(db=db)
        self.jev_engine = jev_engine or JevEngine()
        self.batch_size = batch_size
        self.cycle_budget = cycle_budget
        self.db = db

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
        start_time = time.monotonic()
        spikes: List[FeedSpike] = []
        for s in raw_spikes:
            if isinstance(s, FeedSpike):
                spikes.append(s)
            elif isinstance(s, dict):
                spikes.append(FeedSpike.from_dict(s))

        total_spikes = len(spikes)
        if total_spikes == 0:
            return {
                "status": "NO_OP_EMPTY_QUEUE",
                "total_spikes": 0,
                "filtered_noise_count": 0,
                "evaluated_candidates_count": 0,
                "deduplicated_sink_count": 0,
                "approved_build": [],
                "refactor_pages": [],
                "monitored": [],
                "rejected": [],
                "rankings": [],
            }

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

        # 2. Batch deduplication by normalized query string
        seen_queries: Set[str] = set()
        unique_candidates: List[TrendCandidate] = []
        duplicate_candidates: List[TrendCandidate] = []
        for cand in candidates_to_eval:
            norm_q = " ".join(cand.query.strip().lower().split())
            if norm_q not in seen_queries:
                seen_queries.add(norm_q)
                unique_candidates.append(cand)
            else:
                duplicate_candidates.append(cand)

        eval_batch = unique_candidates[: self.batch_size]
        primary_decisions: Dict[str, JevDecisionResult] = {}

        for cand in eval_batch:
            norm_q = " ".join(cand.query.strip().lower().split())
            elapsed = time.monotonic() - start_time
            remaining_budget = max(0.0, self.cycle_budget - elapsed)

            raw_meta = cand.metadata or {}

            # Upfront search intent cannibalization screening against existing catalog
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
                if "matched_tool" in cannibal_info and isinstance(cannibal_info["matched_tool"], dict):
                    if "position" in cannibal_info["matched_tool"]:
                        pos = float(cannibal_info["matched_tool"]["position"])

            # Check if cannibalization context was pre-supplied (e.g. from evaluation fixtures)
            if "cannibalization_context" in raw_meta:
                cc = raw_meta["cannibalization_context"]
                cann_score = float(cc.get("cannibalization_score", cann_score))
                if cc.get("matches_existing_slug"):
                    matching_tool = str(cc["matches_existing_slug"])
                pos = float(cc.get("current_position", pos))

            if matching_tool and existing_tools and pos == 100.0:
                for tool in existing_tools:
                    if tool.get("slug") == matching_tool and "position" in tool:
                        pos = float(tool["position"])
                        break

            cann_ctx = {
                "cannibalization_score": cann_score,
                "matches_existing_slug": matching_tool,
                "current_position": pos,
            }

            is_striking = (4.0 <= pos <= 20.0)
            is_collision = (cann_score >= 0.50 or cannibal_info.get("is_cannibalizing", False))

            # Prune / reject cannibalizing queries outside striking distance upfront (zero external Treg lookups)
            if is_collision and not is_striking:
                tool_slug = matching_tool or "existing-tool"
                reason = f"Position {pos:.1f} matches existing tool '{tool_slug}'; preserve existing authority and prevent URL bloat"
                decision = JevDecisionResult(
                    query=cand.query,
                    slug=cand.slug or sanitize_url_slug(cand.query),
                    action="MONITOR",
                    jev_score=0.10,
                    durable_prob=0.05,
                    composite_profit_yield=0.0,
                    cannibalization_risk=cann_score,
                    target_asset_type="none",
                    decision_reason=reason,
                    passed_thresholds=False,
                    evaluated_at=cand.discovered_at,
                    matching_tool=tool_slug,
                )
            else:
                # Treg demand cross-check ONLY for non-cannibalized or striking distance candidates
                mock_treg = None
                if "treg_mock" in raw_meta:
                    mock_treg = raw_meta["treg_mock"]

                treg_res = self.treg_checker.check_query(
                    cand.query,
                    mock_override=mock_treg,
                    remaining_budget=remaining_budget,
                )

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

            primary_decisions[norm_q] = decision
            results.append(decision)

        # Duplicate candidates inherit primary decision without redundant lookups
        for dup in duplicate_candidates:
            norm_q = " ".join(dup.query.strip().lower().split())
            if norm_q in primary_decisions:
                prim = primary_decisions[norm_q]
                dup_decision = JevDecisionResult(
                    query=dup.query,
                    slug=dup.slug or prim.slug,
                    action=prim.action,
                    jev_score=prim.jev_score,
                    durable_prob=prim.durable_prob,
                    composite_profit_yield=prim.composite_profit_yield,
                    cannibalization_risk=prim.cannibalization_risk,
                    target_asset_type=prim.target_asset_type,
                    decision_reason=prim.decision_reason,
                    passed_thresholds=prim.passed_thresholds,
                    evaluated_at=dup.discovered_at,
                    matching_tool=prim.matching_tool,
                    candidate_spec=prim.candidate_spec,
                    overlay_spec=prim.overlay_spec,
                )
                results.append(dup_decision)

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

        def _enrich_record(dec: JevDecisionResult) -> Dict[str, Any]:
            rec = dec.to_dict()
            cand_spec = rec.get("candidate_spec") if isinstance(rec.get("candidate_spec"), dict) else {}
            ov_spec = rec.get("overlay_spec") if isinstance(rec.get("overlay_spec"), dict) else {}
            if not rec.get("property_id"):
                prop_id = cand_spec.get("property_id") or ov_spec.get("property_id") or ""
                if not prop_id:
                    from pseofactory.affiliates import qualify_monetization_opportunity
                    prop_id = qualify_monetization_opportunity(
                        query=dec.query,
                        slug=dec.slug,
                    ).get("property_id", "unassigned")
                rec["property_id"] = prop_id
            rec["idempotency_key"] = compute_trend_idempotency_key(rec)
            return rec

        enriched_rankings = [_enrich_record(d) for d in rankings]
        deduplicated_sink_count = 0

        # 5. HWL-1253: Atomic file sink persistence under flock lock with composite idempotency deduplication
        if sink_path:
            deduplicated_sink_count = sink_records_to_jsonl(enriched_rankings, sink_path)

        return {
            "status": "COMPLETED",
            "total_spikes": total_spikes,
            "filtered_noise_count": len(filtered_noise),
            "evaluated_candidates_count": len(eval_batch),
            "deduplicated_sink_count": deduplicated_sink_count,
            "approved_build": [_enrich_record(d) for d in approved_build],
            "refactor_pages": [_enrich_record(d) for d in refactor_pages],
            "monitored": [_enrich_record(d) for d in monitored],
            "rejected": [_enrich_record(d) for d in rejected],
            "rankings": enriched_rankings,
        }


def sink_records_to_jsonl(
    records: List[Dict[str, Any]],
    sink_path: Union[str, Path],
) -> int:
    """
    Atomically appends evaluated trend decision records to a JSONL sink under
    fcntl.flock, enforcing composite idempotency deduplication and stamping
    engine verdict statuses (PENDING for actionable, REJECTED for declined).
    Returns the number of deduplicated (skipped) records.
    Zero em-dashes. Zero en-dashes.
    """
    sink_file = Path(sink_path).expanduser().resolve()
    sink_file.parent.mkdir(parents=True, exist_ok=True)
    deduplicated_sink_count = 0
    with open(sink_file, "a+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            existing_keys: Set[str] = set()
            for raw_line in f:
                line_str = raw_line.strip()
                if not line_str:
                    continue
                try:
                    existing_rec = json.loads(line_str)
                    if isinstance(existing_rec, dict):
                        existing_keys.add(compute_trend_idempotency_key(existing_rec))
                except Exception:
                    continue
            f.seek(0, os.SEEK_END)
            for raw_rec in records:
                if not isinstance(raw_rec, dict):
                    continue
                rec_copy = dict(raw_rec)
                rec_copy["idempotency_key"] = compute_trend_idempotency_key(rec_copy)
                record = stamp_engine_verdict_status(rec_copy)
                idem_key = record["idempotency_key"]
                if idem_key in existing_keys:
                    deduplicated_sink_count += 1
                    continue
                existing_keys.add(idem_key)
                f.write(json.dumps(record) + "\n")
            f.flush()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    return deduplicated_sink_count


def run_trend_pipeline(
    spikes: List[Union[FeedSpike, Dict[str, Any]]],
    existing_tools: Optional[List[Dict[str, Any]]] = None,
    sitemap_urls: Optional[List[str]] = None,
    sink_path: Optional[Union[str, Path]] = None,
    total_site_impressions: int = 500,
    noise_filter: Optional[NoiseFilter] = None,
    treg_checker: Optional[TregChecker] = None,
    jev_engine: Optional[JevEngine] = None,
    batch_size: int = 15,
    cycle_budget: float = 240.0,
    db: Optional[Any] = None,
) -> Dict[str, Any]:
    """Convenience helper to run the complete trend pipeline."""
    pipe = TrendPipeline(
        noise_filter=noise_filter,
        treg_checker=treg_checker,
        jev_engine=jev_engine,
        batch_size=batch_size,
        cycle_budget=cycle_budget,
        db=db,
    )
    return pipe.process_spikes(
        raw_spikes=spikes,
        existing_tools=existing_tools,
        sitemap_urls=sitemap_urls,
        sink_path=sink_path,
        total_site_impressions=total_site_impressions,
    )
