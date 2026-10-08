"""
pseofactory Autonomous Daily Cron Loop Trend Runner
Coordinates multi-source crawler ingestion, noise suppression, treg cross-checking,
property token isolation firewalls, Jev decision scoring, longitudinal history persistence,
and multi-cycle niche durability gating.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Union

from pseofactory.contracts import (
    assert_no_forbidden_dashes,
    assert_url_safe_slug,
    sanitize_url_slug,
)
from pseofactory.maintenance import CrossPropertyContaminationScanner, TenantRegistry
from pseofactory.qualification import check_search_intent_cannibalization
from pseofactory.trends.models import (
    FeedSpike,
    TrendCandidate,
    TregDurabilityResult,
    JevDecisionResult,
    CrawlCycleRecord,
    RawObservationRecord,
    LongitudinalKeywordRecord,
    PropertyAssignmentRecord,
    TregSnapshotRecord,
    JevEvaluationRecord,
    NicheClusterProposal,
)
from pseofactory.trends.collectors import MultiSourceCollector, generate_spike_id
from pseofactory.trends.filters import NoiseFilter
from pseofactory.trends.treg_checker import TregChecker
from pseofactory.trends.jev_engine import (
    JevEngine,
    determine_target_asset_type,
    MIN_JEV_SCORE,
    MIN_DURABLE_PROB,
)
from pseofactory.trends.db import TrendHistoryDB, DEFAULT_DB_PATH


# Authoritative tenant statutory keywords
PREXVO_STATUTORY_TOKENS: List[str] = [
    "title iv",
    "34 cfr",
    "student loan",
    "student loans",
    "repayment assistance plan",
    "pslf",
    "direct consolidation loan",
    "save plan",
    "idr waiver",
    "student loan forgiveness",
]

PROFITHELM_STATUTORY_TOKENS: List[str] = [
    "section 1031",
    "1031 exchange",
    "section 179",
    "bonus depreciation",
    "tcja",
    "commercial clean energy 179d",
    "commercial clean energy",
    "clean energy 179d",
    "cost segregation",
    "capital gains tax",
]

DEFAULT_CRON_SEEDS = "calculator,tax deduction,compliance,student loan,amortization"


class TrendCronRunner:
    """
    Autonomous coordinator executing daily cron cycles.
    Adheres strictly to stateless worker physics; all state persists in TrendHistoryDB.
    """

    def __init__(
        self,
        db_path: Optional[Union[str, Path]] = None,
        min_yield: float = 60.0,
        treg_checker: Optional[TregChecker] = None,
        jev_engine: Optional[JevEngine] = None,
        noise_filter: Optional[NoiseFilter] = None,
        scanner: Optional[CrossPropertyContaminationScanner] = None,
    ):
        self.db_path = Path(db_path or DEFAULT_DB_PATH).resolve()
        self.min_yield = float(min_yield)
        self.treg_checker = treg_checker or TregChecker()
        self.jev_engine = jev_engine or JevEngine(min_build_yield=self.min_yield)
        self.noise_filter = noise_filter or NoiseFilter()
        self.scanner = scanner or CrossPropertyContaminationScanner()

    def determine_property_assignment(self, query: str) -> Dict[str, Any]:
        """
        Routes query to property tenant: prexvo, profithelm, or unassigned.
        Scans for cross-property token contamination.
        Zero em-dashes. Zero en-dashes.
        """
        assert_no_forbidden_dashes(query, "determine_property_assignment.query")
        q_lower = query.lower().strip()

        is_prexvo = any(tok in q_lower for tok in PREXVO_STATUTORY_TOKENS)
        is_profithelm = any(tok in q_lower for tok in PROFITHELM_STATUTORY_TOKENS)

        if is_prexvo and not is_profithelm:
            foreign = self.scanner.scan_text(query, "prexvo")
            if foreign:
                return {
                    "property_id": "prexvo",
                    "basis": "statutory_token",
                    "contamination_scan_passed": 0,
                    "foreign_tokens": foreign,
                }
            return {
                "property_id": "prexvo",
                "basis": "statutory_token",
                "contamination_scan_passed": 1,
                "foreign_tokens": [],
            }

        if is_profithelm and not is_prexvo:
            foreign = self.scanner.scan_text(query, "profithelm")
            if foreign:
                return {
                    "property_id": "profithelm",
                    "basis": "statutory_token",
                    "contamination_scan_passed": 0,
                    "foreign_tokens": foreign,
                }
            return {
                "property_id": "profithelm",
                "basis": "statutory_token",
                "contamination_scan_passed": 1,
                "foreign_tokens": [],
            }

        if is_prexvo and is_profithelm:
            # Both matched: ambiguous and contaminated
            return {
                "property_id": "unassigned",
                "basis": "cross_contaminated",
                "contamination_scan_passed": 0,
                "foreign_tokens": ["cross_tenant_overlap"],
            }

        # Unassigned greenfield niche cluster
        return {
            "property_id": "unassigned",
            "basis": "unassigned_cluster",
            "contamination_scan_passed": 1,
            "foreign_tokens": [],
        }

    def load_fixture(self, fixture_path: Union[str, Path]) -> List[FeedSpike]:
        """Loads feed spikes and registers mock metrics from a JSON fixture file."""
        p = Path(fixture_path).resolve()
        if not p.is_file():
            raise FileNotFoundError(f"Fixture file not found: {fixture_path}")

        content = p.read_text(encoding="utf-8")
        data = json.loads(content)

        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            if "records" in data:
                items = data["records"]
            elif "payloads" in data:
                items = data["payloads"]
            elif "spikes" in data:
                items = data["spikes"]
            else:
                items = [data]
        else:
            items = []

        spikes: List[FeedSpike] = []
        now = datetime.now(timezone.utc).isoformat()

        for idx, item in enumerate(items):
            q = str(item.get("query", "")).strip()
            if not q:
                continue
            src = str(item.get("source", "fixture"))
            spike_id = str(item.get("id") or generate_spike_id(src, q, now))

            # Register treg mock if present in fixture item
            if "treg_mock" in item:
                self.treg_checker.register_mock(q, item["treg_mock"])
            elif "search_volume" in item:
                mock_metrics = {
                    "search_volume": int(item.get("search_volume", 1000)),
                    "cpc_usd": float(item.get("cpc_usd", 1.50)),
                    "keyword_difficulty": float(item.get("keyword_difficulty", 20.0)),
                    "position_zero_vacant": item.get("position_zero_vacant", True),
                    "historical_stability": float(item.get("historical_stability", 0.85)),
                }
                self.treg_checker.register_mock(q, mock_metrics)

            sp = FeedSpike(
                id=spike_id,
                query=q,
                source=src,
                detected_at=str(item.get("detected_at") or now),
                sample_count=int(item.get("sample_count", 1)),
                velocity=float(item.get("velocity", 50.0)),
                acceleration=float(item.get("acceleration", 10.0)),
                z_score=float(item.get("z_score", 3.0)),
                baseline_mean=float(item.get("baseline_mean", 10.0)),
                baseline_std=float(item.get("baseline_std", 2.0)),
                raw_payload=item,
            )
            spikes.append(sp)

        return spikes

    def run_cycle(
        self,
        cycle_id: Optional[str] = None,
        fixture_path: Optional[Union[str, Path]] = None,
        seeds: Optional[Union[str, List[str]]] = None,
        property_filter: Optional[str] = None,
        dry_run: bool = False,
        total_site_impressions: int = 500,
    ) -> Dict[str, Any]:
        """
        Executes complete daily cron monitoring cycle.
        Returns machine-readable summary dictionary.
        Zero em-dashes. Zero en-dashes.
        """
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        if not cycle_id:
            short_hash = hashlib.sha256(now_iso.encode()).hexdigest()[:8]
            cycle_id = f"cycle_{now.strftime('%Y%m%d_%H%M%S')}_{short_hash}"

        assert_no_forbidden_dashes(cycle_id, "run_cycle.cycle_id")

        if seeds is None:
            seed_list = [s.strip() for s in DEFAULT_CRON_SEEDS.split(",") if s.strip()]
        elif isinstance(seeds, str):
            seed_list = [s.strip() for s in seeds.split(",") if s.strip()]
        else:
            seed_list = list(seeds)

        db = TrendHistoryDB(self.db_path)

        # Acquire atomic advisory lock on <db_path>.lock
        with db.acquire_lock(non_blocking=True):
            # 1. Start cycle in DB
            sources_crawled = ["google_suggest", "youtube_suggest", "reddit_autocomplete", "hn_search", "google_trends_rss"]
            if fixture_path:
                sources_crawled = ["fixture"]

            if not dry_run:
                db.start_cycle(cycle_id=cycle_id, seeds=seed_list, sources=sources_crawled)

            # 2. Ingest raw spikes
            if fixture_path:
                spikes = self.load_fixture(fixture_path)
            else:
                collector = MultiSourceCollector()
                spikes = collector.harvest(seed_list)

            # 3. Preload existing tools for cannibalization checks
            existing_tools_map: Dict[str, List[Dict[str, Any]]] = {}
            try:
                reg = TenantRegistry.default()
                for p_id in ("prexvo", "profithelm"):
                    try:
                        adapter = reg.get_adapter(p_id)
                        existing_tools_map[p_id] = getattr(adapter, "tools", []) or []
                    except Exception:
                        existing_tools_map[p_id] = []
            except Exception:
                existing_tools_map = {"prexvo": [], "profithelm": []}

            obs_records: List[RawObservationRecord] = []
            eval_records: List[JevEvaluationRecord] = []
            assignment_records: List[PropertyAssignmentRecord] = []
            snapshot_records: List[TregSnapshotRecord] = []
            proposals_created: List[NicheClusterProposal] = []
            keyword_rollups: List[LongitudinalKeywordRecord] = []

            approved_build: List[Dict[str, Any]] = []
            refactor_pages: List[Dict[str, Any]] = []
            monitored: List[Dict[str, Any]] = []
            rejected: List[Dict[str, Any]] = []
            all_rankings: List[Dict[str, Any]] = []
            filtered_noise_count = 0

            # 4. Process each spike
            for rank_idx, spike in enumerate(spikes):
                clean_q = spike.query.strip()
                slug = sanitize_url_slug(clean_q)
                norm_q = " ".join(clean_q.lower().split())
                raw_meta = dict(spike.raw_payload or {})

                # Generate deterministic observation ID
                obs_id = hashlib.sha256(f"{cycle_id}:{spike.source}:{norm_q}".encode()).hexdigest()[:16]

                raw_obs = RawObservationRecord(
                    observation_id=obs_id,
                    cycle_id=cycle_id,
                    source=spike.source,
                    query=clean_q,
                    normalized_query=norm_q,
                    rank_position=rank_idx,
                    observed_velocity=spike.velocity,
                    observed_acceleration=spike.acceleration,
                    observed_z_score=spike.z_score,
                    observed_at=spike.detected_at,
                    raw_payload=spike.raw_payload,
                )
                obs_records.append(raw_obs)

                # Check hint search volume from treg mock if present
                treg_hint = 0
                if "treg_mock" in raw_meta:
                    treg_hint = int(raw_meta["treg_mock"].get("search_volume", 0))
                elif "search_volume" in raw_meta:
                    treg_hint = int(raw_meta.get("search_volume", 0))

                # Step 4A: Noise filter & acceleration gating
                passes, reason, cand = self.noise_filter.evaluate_spike(spike, search_volume=treg_hint)
                if not passes or cand.is_transient_noise:
                    filtered_noise_count += 1
                    rej_eval = JevEvaluationRecord(
                        evaluation_id=f"eval_{slug}_{cycle_id}",
                        query_slug=slug,
                        cycle_id=cycle_id,
                        property_id="unassigned",
                        jev_score=0.10,
                        durable_prob=0.05,
                        composite_profit_yield=0.0,
                        cannibalization_risk=0.0,
                        action="REJECT",
                        target_asset_type="none",
                        passed_thresholds=0,
                        decision_reason=reason,
                        spec_payload=None,
                        evaluated_at=cand.discovered_at,
                    )
                    eval_records.append(rej_eval)
                    rejected.append({
                        "query": clean_q,
                        "slug": slug,
                        "property_id": "unassigned",
                        "reason": reason,
                        "action": "REJECT",
                        "composite_profit_yield": 0.0,
                    })

                    if not dry_run:
                        rollup = db.upsert_keyword_history(
                            query_slug=slug,
                            query=clean_q,
                            cycle_id=cycle_id,
                            observed_velocity=spike.velocity,
                            intent_cluster=cand.intent_cluster,
                            property_id="unassigned",
                            status="rejected",
                            observed_at=cand.discovered_at,
                            override_acceleration=spike.acceleration,
                        )
                        keyword_rollups.append(rollup)
                    continue

                # Step 4B: Property tenant routing & cross-tenant contamination scan
                prop_info = self.determine_property_assignment(clean_q)
                assigned_property = prop_info["property_id"]
                assign_basis = prop_info["basis"]
                scan_passed = prop_info["contamination_scan_passed"]

                # Apply CLI property filter if configured
                if property_filter and assigned_property != property_filter:
                    continue

                assign_rec = PropertyAssignmentRecord(
                    assignment_id=f"asgn_{slug}_{cycle_id}",
                    query_slug=slug,
                    cycle_id=cycle_id,
                    property_id=assigned_property,
                    assignment_basis=assign_basis,
                    matched_existing_slug=None,
                    cannibalization_score=0.0,
                    current_position=100.0,
                    contamination_scan_passed=scan_passed,
                    assigned_at=now_iso,
                )

                # If contamination scan failed: fail closed, quarantine to REJECT
                if scan_passed == 0:
                    foreign_joined = ", ".join(prop_info.get("foreign_tokens", []))
                    rej_reason = f"Cross-tenant token contamination detected: {foreign_joined}"
                    rej_eval = JevEvaluationRecord(
                        evaluation_id=f"eval_{slug}_{cycle_id}",
                        query_slug=slug,
                        cycle_id=cycle_id,
                        property_id=assigned_property,
                        jev_score=0.10,
                        durable_prob=0.05,
                        composite_profit_yield=0.0,
                        cannibalization_risk=1.0,
                        action="REJECT",
                        target_asset_type="none",
                        passed_thresholds=0,
                        decision_reason=rej_reason,
                        spec_payload=None,
                        evaluated_at=now_iso,
                    )
                    eval_records.append(rej_eval)
                    assignment_records.append(assign_rec)
                    rejected.append({
                        "query": clean_q,
                        "slug": slug,
                        "property_id": assigned_property,
                        "reason": rej_reason,
                        "action": "REJECT",
                        "composite_profit_yield": 0.0,
                    })
                    if not dry_run:
                        rollup = db.upsert_keyword_history(
                            query_slug=slug,
                            query=clean_q,
                            cycle_id=cycle_id,
                            observed_velocity=spike.velocity,
                            intent_cluster=cand.intent_cluster,
                            property_id=assigned_property,
                            status="rejected",
                            observed_at=now_iso,
                            override_acceleration=spike.acceleration,
                        )
                        keyword_rollups.append(rollup)
                    continue

                # Step 4C: Treg demand cross-check
                mock_treg = raw_meta.get("treg_mock")
                treg_res = self.treg_checker.check_query(clean_q, mock_override=mock_treg)

                snap_rec = TregSnapshotRecord(
                    snapshot_id=f"treg_{slug}_{cycle_id}",
                    query_slug=slug,
                    cycle_id=cycle_id,
                    search_volume=treg_res.search_volume,
                    cpc_usd=treg_res.cpc_usd,
                    competition_index=treg_res.competition_index,
                    keyword_difficulty=treg_res.keyword_difficulty,
                    position_zero_vacant=1 if treg_res.position_zero_vacant else 0,
                    historical_stability=treg_res.historical_stability,
                    checked_at=now_iso,
                )
                snapshot_records.append(snap_rec)

                # Step 4D: Cannibalization check against tenant existing tools
                tenant_tools = existing_tools_map.get(assigned_property, [])
                cannibal_info = check_search_intent_cannibalization(clean_q, existing_tools=tenant_tools)

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
                else:
                    if "matching_tool" in raw_meta:
                        matching_tool = str(raw_meta["matching_tool"])
                        if cann_score < 0.50:
                            cann_score = 0.85
                    if "current_position" in raw_meta:
                        pos = float(raw_meta["current_position"])
                    elif "position" in raw_meta:
                        pos = float(raw_meta["position"])
                    if "cannibalization_score" in raw_meta:
                        cann_score = float(raw_meta["cannibalization_score"])

                assign_rec.matched_existing_slug = matching_tool
                assign_rec.cannibalization_score = cann_score
                assign_rec.current_position = pos
                assignment_records.append(assign_rec)

                cann_ctx = {
                    "cannibalization_score": cann_score,
                    "matches_existing_slug": matching_tool,
                    "current_position": pos,
                }

                # Step 4E: Evaluate Jev decision
                mock_jev = raw_meta.get("jev_mock")
                decision = self.jev_engine.evaluate(
                    candidate=cand,
                    treg_result=treg_res,
                    cannibalization_context=cann_ctx,
                    jev_mock=mock_jev,
                    position=pos,
                    total_site_impressions=total_site_impressions,
                )

                # Update keyword history rollup to obtain consecutive streak
                consecutive_streak = 1
                if not dry_run:
                    rollup = db.upsert_keyword_history(
                        query_slug=slug,
                        query=clean_q,
                        cycle_id=cycle_id,
                        observed_velocity=spike.velocity,
                        intent_cluster=cand.intent_cluster,
                        property_id=assigned_property,
                        observed_at=now_iso,
                        override_acceleration=spike.acceleration,
                    )
                    keyword_rollups.append(rollup)
                    consecutive_streak = rollup.consecutive_cycles_count
                else:
                    consecutive_streak = 1

                # Step 4F: Multi-Cycle Durability Gating & Tenant Action Triage
                action_to_record = decision.action
                spec_payload = None
                target_asset = decision.target_asset_type

                if assigned_property in ("prexvo", "profithelm"):
                    # Existing tenant: qualify improvements directly
                    if decision.action == "BUILD_PAGE":
                        spec_payload = decision.candidate_spec
                        approved_build.append({
                            "query": clean_q,
                            "slug": slug,
                            "property_id": assigned_property,
                            "composite_profit_yield": decision.composite_profit_yield,
                            "target_asset_type": target_asset,
                            "consecutive_cycles": consecutive_streak,
                            "candidate_spec": spec_payload,
                        })
                    elif decision.action == "REFACTOR_PAGE":
                        # Ensure 28-day lock per HWL-1354
                        lock_until = (now + timedelta(days=28)).strftime("%Y-%m-%dT%H:%M:%SZ")
                        overlay_spec = decision.overlay_spec or {
                            "slug": matching_tool or slug,
                            "measurement_lock_days": 28,
                            "locked_until": lock_until,
                            "target_injections": [clean_q],
                        }
                        spec_payload = overlay_spec
                        refactor_pages.append({
                            "query": clean_q,
                            "slug": slug,
                            "property_id": assigned_property,
                            "matching_tool": matching_tool or slug,
                            "composite_profit_yield": decision.composite_profit_yield,
                            "overlay_spec": overlay_spec,
                            "locked_until": lock_until,
                        })
                    elif decision.action == "MONITOR":
                        monitored.append({
                            "query": clean_q,
                            "slug": slug,
                            "property_id": assigned_property,
                            "composite_profit_yield": decision.composite_profit_yield,
                            "reason": decision.decision_reason,
                        })
                    else:
                        rejected.append({
                            "query": clean_q,
                            "slug": slug,
                            "property_id": assigned_property,
                            "composite_profit_yield": decision.composite_profit_yield,
                            "reason": decision.decision_reason,
                        })

                else:
                    # Assigned property: 'unassigned' (greenfield niche cluster)
                    # Gating Rule: Consecutive cycles < 3 strictly holds in MONITOR
                    if consecutive_streak < 3:
                        action_to_record = "MONITOR"
                        gated_reason = (
                            f"Unassigned niche held in MONITOR (consecutive cycles {consecutive_streak} < 3); "
                            f"new app proposals strictly prohibited until sustained across 3+ daily cycles"
                        )
                        monitored.append({
                            "query": clean_q,
                            "slug": slug,
                            "property_id": "unassigned",
                            "composite_profit_yield": decision.composite_profit_yield,
                            "consecutive_cycles": consecutive_streak,
                            "status": "candidate" if consecutive_streak == 1 else "observed",
                            "reason": gated_reason,
                        })
                    else:
                        # Consecutive cycles >= 3: verify durability invariants
                        yield_qualifies = decision.composite_profit_yield >= 70.0
                        stability_qualifies = treg_res.historical_stability >= 0.80
                        jev_qualifies = decision.jev_score >= MIN_JEV_SCORE and decision.durable_prob >= MIN_DURABLE_PROB
                        volume_qualifies = treg_res.search_volume >= 500
                        pos0_qualifies = treg_res.position_zero_vacant or treg_res.keyword_difficulty <= 35.0

                        if yield_qualifies and stability_qualifies and jev_qualifies and volume_qualifies and pos0_qualifies:
                            action_to_record = "PROPOSE_NEW_APP"
                            proposal_id = f"prop_{slug}_{cycle_id}"
                            cluster_title = clean_q.title()

                            proposal_spec = {
                                "cluster_slug": slug,
                                "cluster_title": cluster_title,
                                "primary_queries": [clean_q],
                                "primary_keyword": clean_q.lower(),
                                "target_asset_type": determine_target_asset_type(clean_q, cand.intent_cluster),
                                "composite_profit_yield": round(decision.composite_profit_yield, 2),
                                "search_volume": treg_res.search_volume,
                                "cpc_usd": treg_res.cpc_usd,
                                "keyword_difficulty": treg_res.keyword_difficulty,
                                "treg_stability": treg_res.historical_stability,
                                "jev_score": decision.jev_score,
                                "durable_prob": decision.durable_prob,
                                "consecutive_cycles_sustained": consecutive_streak,
                                "affiliate_fit": cand.intent_cluster,
                                "blueprint": {
                                    "archetype": "standalone_factory",
                                    "scaffold_recommended": True,
                                    "proposed_at": now_iso,
                                },
                            }

                            proposal = NicheClusterProposal(
                                proposal_id=proposal_id,
                                cluster_slug=slug,
                                cluster_title=cluster_title,
                                first_observed_cycle_id=cycle_id,
                                confirmed_cycle_id=cycle_id,
                                consecutive_cycles_sustained=consecutive_streak,
                                mean_composite_yield=round(decision.composite_profit_yield, 2),
                                aggregate_search_volume=treg_res.search_volume,
                                mean_cpc_usd=round(treg_res.cpc_usd, 2),
                                treg_stability_index=round(treg_res.historical_stability, 2),
                                primary_queries=[clean_q],
                                recommended_domain_archetype="standalone_factory",
                                status="PROPOSED",
                                proposal_spec=proposal_spec,
                                created_at=now_iso,
                                updated_at=now_iso,
                            )
                            proposals_created.append(proposal)
                            spec_payload = proposal_spec

                            # Promote status in keyword history to action_ready
                            if not dry_run:
                                db.upsert_keyword_history(
                                    query_slug=slug,
                                    query=clean_q,
                                    cycle_id=cycle_id,
                                    observed_velocity=spike.velocity,
                                    intent_cluster=cand.intent_cluster,
                                    property_id="unassigned",
                                    status="action_ready",
                                    observed_at=now_iso,
                                    override_acceleration=spike.acceleration,
                                )
                        else:
                            action_to_record = "MONITOR"
                            monitored.append({
                                "query": clean_q,
                                "slug": slug,
                                "property_id": "unassigned",
                                "composite_profit_yield": decision.composite_profit_yield,
                                "consecutive_cycles": consecutive_streak,
                                "status": "stabilized",
                                "reason": "Sustained unassigned trend below threshold for new app proposal",
                            })

                eval_rec = JevEvaluationRecord(
                    evaluation_id=f"eval_{slug}_{cycle_id}",
                    query_slug=slug,
                    cycle_id=cycle_id,
                    property_id=assigned_property,
                    jev_score=decision.jev_score,
                    durable_prob=decision.durable_prob,
                    composite_profit_yield=decision.composite_profit_yield,
                    cannibalization_risk=decision.cannibalization_risk,
                    action=action_to_record,
                    target_asset_type=target_asset,
                    passed_thresholds=1 if action_to_record in ("BUILD_PAGE", "REFACTOR_PAGE", "PROPOSE_NEW_APP") else 0,
                    decision_reason=decision.decision_reason,
                    spec_payload=spec_payload,
                    evaluated_at=now_iso,
                )
                eval_records.append(eval_rec)

                all_rankings.append({
                    "query": clean_q,
                    "slug": slug,
                    "property_id": assigned_property,
                    "action": action_to_record,
                    "composite_profit_yield": decision.composite_profit_yield,
                    "consecutive_cycles": consecutive_streak,
                    "target_asset_type": target_asset,
                })

            # Sort rankings by composite profit yield descending
            all_rankings.sort(key=lambda r: r["composite_profit_yield"], reverse=True)

            # 5. Commit all records atomically to SQLite
            if not dry_run:
                with db.transaction():
                    db.record_observations(obs_records)
                    for asgn in assignment_records:
                        db.record_property_assignment(asgn)
                    for snap in snapshot_records:
                        db.record_treg_snapshot(snap)
                    for ev in eval_records:
                        db.record_jev_evaluation(ev)
                    for prop in proposals_created:
                        db.create_niche_proposal(prop)
                    db.complete_cycle(
                        cycle_id=cycle_id,
                        total_raw_observations=len(obs_records),
                        unique_queries_count=len(spikes),
                        status="COMPLETED",
                        metadata={
                            "approved_build_count": len(approved_build),
                            "refactor_pages_count": len(refactor_pages),
                            "monitored_count": len(monitored),
                            "rejected_count": len(rejected),
                            "proposals_count": len(proposals_created),
                        },
                    )

            return {
                "cycle_id": cycle_id,
                "executed_at": now_iso,
                "status": "COMPLETED",
                "total_raw_observations": len(obs_records),
                "unique_queries_count": len(spikes),
                "filtered_noise_count": filtered_noise_count,
                "approved_build": approved_build,
                "refactor_pages": refactor_pages,
                "monitored": monitored,
                "rejected": rejected,
                "proposals": [p.to_dict() for p in proposals_created],
                "rankings": all_rankings,
                "dry_run": dry_run,
            }
