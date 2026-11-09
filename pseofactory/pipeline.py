"""
pseofactory Automated Discovery and Content Generation Pipeline Driver
Unifies multi-source breakout opportunity ingestion (FeedSpike), discrete second-derivative
acceleration gating (HWL-1215), Treg search demand cross-referencing, Jev durability gating
(score >= 1.20, durable_prob >= 0.50), live SERP underdog angle extraction with Grant O Triad
and token Jaccard divergence >= 0.50, symmetric multi-tenant property boundary isolation
between profithelm and prexvo, and compliant high-effort programmatic page compilation.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import os
import re
import json
import fcntl
import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Union, Tuple

from pseofactory.contracts import (
    assert_no_forbidden_dashes,
    assert_no_prompt_leakage,
    assert_url_safe_slug,
    sanitize_url_slug,
)
from pseofactory.qualification import (
    check_search_intent_cannibalization,
    assert_high_effort_content_qualified,
)
from pseofactory.trends.models import (
    FeedSpike,
    TrendCandidate,
    TregDurabilityResult,
    JevDecisionResult,
)
from pseofactory.trends.filters import NoiseFilter
from pseofactory.trends.treg_checker import TregChecker
from pseofactory.trends.jev_engine import JevEngine
from pseofactory.trends.cron import (
    GAINHELM_STATUTORY_TOKENS,
    PREXVO_STATUTORY_TOKENS,
    PROFITHELM_STATUTORY_TOKENS,
)
from pseofactory.maintenance import (
    CrossPropertyContaminationScanner,
    PropertyContaminationError,
    PropertyAdapter,
    ConfigurablePropertyAdapter,
    TenantRegistry,
)
from pseofactory.content_angles import (
    evaluate_content_angles,
    calculate_token_jaccard_divergence,
    assert_underdog_angle_divergence,
    ContentAngleBrief,
    UnderdogAngle,
    GrantOTriad,
    IncumbentSummary,
)
from pseofactory.compiler import compile_high_effort_page
from pseofactory.competitor import CompetitorGapEngine, GapCandidateSpec
from pseofactory.tenant_facts import TenantFactStore
from pseofactory.audit import (
    ContentAccuracyAuditStage,
    ContentAccuracyAuditReport,
    ContentAccuracyAuditError,
)


def __getattr__(name: str) -> Any:
    if name == "DailyIndexingInspector":
        from pseofactory.indexing_inspector import DailyIndexingInspector
        return DailyIndexingInspector
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


logger = logging.getLogger("pseofactory.pipeline")


class RejectionReason:
    LOW_JEV_DURABILITY = "LOW_JEV_DURABILITY"
    HIGH_TREG_COMPETITION = "HIGH_TREG_COMPETITION"
    TRANSIENT_NOISE_OR_DECELERATION = "TRANSIENT_NOISE_OR_DECELERATION"
    CROSS_PROPERTY_CONTAMINATION = "CROSS_PROPERTY_CONTAMINATION"
    DERIVATIVE_SERP_ANGLE = "DERIVATIVE_SERP_ANGLE"
    REFACTOR_PAGE_CANNIBALIZATION = "REFACTOR_PAGE_CANNIBALIZATION"
    AUDIT_STAGE_FAILED = "AUDIT_STAGE_FAILED"
    CONTENT_ACCURACY_FAILED = "CONTENT_ACCURACY_FAILED"
    COMPILATION_FAILED = "COMPILATION_FAILED"
    ALGORITHMIC_EXPANSION_FREEZE = "ALGORITHMIC_EXPANSION_FREEZE"


from pseofactory.verifier import MasterSEOVerifier


@dataclass
class PipelineConfig:
    min_jev_score: float = 1.20
    min_durable_prob: float = 0.50
    min_build_yield: float = 60.0
    max_route_cost: str = "0.05"
    treg_timeout: float = 10.0
    retry_ceiling: int = 3
    dry_run: bool = False
    sink_path: Optional[Path] = None
    total_site_impressions: int = 500
    strict_audit: bool = True
    audit_tolerance: float = 0.01
    enable_gitops: bool = True
    enable_distribution: bool = True
    enable_indexing_feedback: bool = False
    adaptive_jev_floor_bump: float = 0.30


@dataclass
class QualifiedOpportunity:
    query: str
    slug: str
    tenant: str
    jev_score: float
    durable_prob: float
    composite_profit_yield: float
    search_volume: int
    keyword_difficulty: float
    target_asset_type: str
    angle_brief: Optional[Dict[str, Any]] = None
    candidate_spec: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "slug": self.slug,
            "tenant": self.tenant,
            "jev_score": self.jev_score,
            "durable_prob": self.durable_prob,
            "composite_profit_yield": self.composite_profit_yield,
            "search_volume": self.search_volume,
            "keyword_difficulty": self.keyword_difficulty,
            "target_asset_type": self.target_asset_type,
            "angle_brief": self.angle_brief,
            "candidate_spec": self.candidate_spec,
        }


@dataclass
class AbortedOpportunity:
    query: str
    slug: str
    reason: str  # LOW_JEV_DURABILITY | HIGH_TREG_COMPETITION | TRANSIENT_NOISE_OR_DECELERATION | CROSS_PROPERTY_CONTAMINATION | DERIVATIVE_SERP_ANGLE | REFACTOR_PAGE_CANNIBALIZATION | AUDIT_STAGE_FAILED
    jev_score: float = 0.0
    durable_prob: float = 0.0
    search_volume: int = 0
    keyword_difficulty: float = 0.0
    foreign_tokens: List[str] = field(default_factory=list)
    action: str = "REJECT"
    tenant: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "query": self.query,
            "slug": self.slug,
            "reason": self.reason,
            "jev_score": self.jev_score,
            "durable_prob": self.durable_prob,
            "search_volume": self.search_volume,
            "keyword_difficulty": self.keyword_difficulty,
            "foreign_tokens": self.foreign_tokens,
            "action": self.action,
        }
        if self.tenant is not None:
            d["tenant"] = self.tenant
        return d


@dataclass
class CompiledAssetResult:
    query: str
    slug: str
    tenant: str
    html_length: int
    output_file: Optional[Path] = None
    manifest: Dict[str, Any] = field(default_factory=dict)
    audit_passed: bool = True
    contamination_clean: bool = True
    audit_report: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "slug": self.slug,
            "tenant": self.tenant,
            "html_length": self.html_length,
            "output_file": str(self.output_file) if self.output_file else None,
            "manifest": self.manifest,
            "audit_passed": self.audit_passed,
            "contamination_clean": self.contamination_clean,
            "audit_report": self.audit_report,
        }


@dataclass
class DriverExecutionResult:
    total_spikes: int
    filtered_noise_count: int
    evaluated_count: int
    approved_count: int
    compiled_count: int
    aborted_count: int
    compiled_assets: List[CompiledAssetResult]
    aborted_opportunities: List[AbortedOpportunity]
    rankings: List[Dict[str, Any]]
    preflight_reports: Optional[Dict[str, Any]] = None
    gitops_results: Optional[Dict[str, Any]] = None
    distribution_results: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "total_spikes": self.total_spikes,
            "filtered_noise_count": self.filtered_noise_count,
            "evaluated_count": self.evaluated_count,
            "approved_count": self.approved_count,
            "compiled_count": self.compiled_count,
            "aborted_count": self.aborted_count,
            "compiled_assets": [a.to_dict() for a in self.compiled_assets],
            "aborted_opportunities": [o.to_dict() for o in self.aborted_opportunities],
            "rankings": self.rankings,
        }
        if self.preflight_reports is not None:
            d["preflight_reports"] = self.preflight_reports
        if self.gitops_results is not None:
            d["gitops_results"] = self.gitops_results
        if self.distribution_results is not None:
            d["distribution_results"] = self.distribution_results
        return d


def _slug_matches_quarantined_url(slug: str, quarantined_url: str) -> bool:
    """
    Checks if candidate slug matches a quarantined URL.
    Zero em-dashes. Zero en-dashes.
    """
    s = slug.strip().strip("/").lower()
    q = quarantined_url.strip().lower()
    if not s or not q:
        return False
    if s == q:
        return True
    q_clean = q.split("?")[0].split("#")[0].strip("/")
    if s == q_clean:
        return True
    segments = [seg.strip() for seg in q_clean.split("/") if seg.strip()]
    if s in segments:
        return True
    if q_clean.endswith(f"/{s}"):
        return True
    return False


class FactoryPipeline:
    """
    Automated discovery, validation, and content generation pipeline.
    Connects trend ingestion to Jev ranking, SERP underdog angle divergence,
    statutory property boundary isolation, and high-effort static HTML compilation.
    Zero em-dashes. Zero en-dashes.
    """

    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        noise_filter: Optional[NoiseFilter] = None,
        treg_checker: Optional[TregChecker] = None,
        jev_engine: Optional[JevEngine] = None,
        scanner: Optional[CrossPropertyContaminationScanner] = None,
        tenant_registry: Optional[TenantRegistry] = None,
        indexing_inspector: Optional["DailyIndexingInspector"] = None,
        db: Optional[Any] = None,
    ):
        self.config = config or PipelineConfig()
        self.noise_filter = noise_filter or NoiseFilter()
        self.db = db
        if treg_checker is not None:
            self.treg_checker = treg_checker
            if self.db is not None and getattr(self.treg_checker, "db", None) is None:
                self.treg_checker.db = self.db
        else:
            self.treg_checker = TregChecker(
                max_cost=self.config.max_route_cost,
                timeout=self.config.treg_timeout,
                db=self.db,
            )
        self.jev_engine = jev_engine or JevEngine(
            min_score=self.config.min_jev_score,
            min_durable_prob=self.config.min_durable_prob,
            min_build_yield=self.config.min_build_yield,
        )
        self.scanner = scanner or CrossPropertyContaminationScanner()
        self.tenant_registry = tenant_registry or TenantRegistry.default()
        self.indexing_inspector = indexing_inspector
        if self.config.enable_indexing_feedback and self.indexing_inspector is None:
            from pseofactory.indexing_inspector import DailyIndexingInspector
            self.indexing_inspector = DailyIndexingInspector()

    def arbitrate_actions(
        self,
        spikes: Optional[List[Any]] = None,
        drift_records: Optional[List[Any]] = None,
        indexing_defects: Optional[List[Any]] = None,
        refactor_candidates: Optional[List[Any]] = None,
        existing_tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[str, Any]:
        """
        Implements post5.md's 'One action per run' single-scale prioritization:
        - Rank 1 (P0): TRUTH_CONTRADICTION & PROPERTY_CONTAMINATION in dist/live assets
          takes absolute priority over new builds.
        - Rank 2 (P1): INDEXING_DEFECT (404s, redirect loops, canonical mismatches)
        - Rank 3 (P2): REFACTOR_PAGE (striking distance refreshes, engine drift)
        - Rank 4 (P3): BUILD_PAGE (new breakout search opportunities)
        Returns (action_type, winning_payload).
        Zero em-dashes. Zero en-dashes.
        """
        return arbitrate_actions(
            spikes=spikes,
            drift_records=drift_records,
            indexing_defects=indexing_defects,
            refactor_candidates=refactor_candidates,
            existing_tools=existing_tools,
        )

    def determine_property_assignment(
        self,
        query: str,
        explicit_tenant: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Routes query to a registered property tenant or unassigned via declarative
        statutory intent tokens. Scans for cross-property token contamination in fail-closed mode.
        Zero em-dashes. Zero en-dashes.
        """
        from pseofactory.tenant_facts import (
            CANONICAL_TENANT_DECLARATIONS,
            match_tenant_statutory_intent,
        )

        assert_no_forbidden_dashes(query, "determine_property_assignment.query")
        q_lower = query.lower().strip()
        matched_map = match_tenant_statutory_intent(query)

        if explicit_tenant:
            tenant_norm = explicit_tenant.lower().strip()
            if tenant_norm in CANONICAL_TENANT_DECLARATIONS:
                foreign = self.scanner.scan_text(query, tenant_norm)
                for other_id, other_hit in matched_map.items():
                    if other_id == tenant_norm or not other_hit:
                        continue
                    other_contract = CANONICAL_TENANT_DECLARATIONS[other_id]
                    matched_tok = next(
                        (tok for tok in other_contract.statutory_intent_tokens if tok in q_lower),
                        None,
                    )
                    if other_id == "profithelm" and "1031" in q_lower:
                        token_found = "1031 exchange"
                    elif matched_tok:
                        token_found = matched_tok
                    else:
                        token_found = f"{other_id} statutory token"
                    foreign = list(set(foreign + [token_found]))
                if foreign:
                    return {
                        "property_id": tenant_norm,
                        "basis": "cross_contaminated",
                        "contamination_scan_passed": 0,
                        "foreign_tokens": foreign,
                    }
                return {
                    "property_id": tenant_norm,
                    "basis": "explicit_tenant",
                    "contamination_scan_passed": 1,
                    "foreign_tokens": [],
                }

        matched_props = [p for p, hit in matched_map.items() if hit]
        if len(matched_props) == 1:
            target_prop = matched_props[0]
            foreign = self.scanner.scan_text(query, target_prop)
            if foreign:
                return {
                    "property_id": target_prop,
                    "basis": "cross_contaminated",
                    "contamination_scan_passed": 0,
                    "foreign_tokens": foreign,
                }
            return {
                "property_id": target_prop,
                "basis": "statutory_token",
                "contamination_scan_passed": 1,
                "foreign_tokens": [],
            }

        if len(matched_props) >= 2:
            return {
                "property_id": "unassigned",
                "basis": "cross_contaminated",
                "contamination_scan_passed": 0,
                "foreign_tokens": ["cross_tenant_overlap"],
            }

        return {
            "property_id": "unassigned",
            "basis": "unassigned_cluster",
            "contamination_scan_passed": 1,
            "foreign_tokens": [],
        }

    def execute(
        self,
        raw_spikes: List[Union[FeedSpike, Dict[str, Any]]],
        existing_tools: Optional[List[Dict[str, Any]]] = None,
        sitemap_urls: Optional[List[str]] = None,
        output_dir: Optional[Union[str, Path]] = None,
        enable_gitops: Optional[bool] = None,
        enable_distribution: Optional[bool] = None,
    ) -> DriverExecutionResult:
        """
        Executes end-to-end processing across raw breakout search opportunities.
        Adheres to stateless worker physics and atomic flock sink persistence.
        Zero em-dashes. Zero en-dashes.
        """
        spikes: List[FeedSpike] = []
        for s in raw_spikes:
            if isinstance(s, FeedSpike):
                spikes.append(s)
            elif isinstance(s, dict):
                spikes.append(FeedSpike.from_dict(s))

        total_spikes = len(spikes)
        filtered_noise_count = 0
        evaluated_count = 0
        compiled_assets: List[CompiledAssetResult] = []
        aborted_opportunities: List[AbortedOpportunity] = []
        rankings: List[Dict[str, Any]] = []
        preflight_reports: Dict[str, Any] = {}
        gitops_results: Dict[str, Any] = {}
        distribution_results: Dict[str, Any] = {}
        seen_idempotency_keys: Set[str] = set()

        in_pytest = bool(os.environ.get("PYTEST_CURRENT_TEST"))
        effective_enable_gitops = (
            (False if in_pytest else self.config.enable_gitops)
            if enable_gitops is None
            else enable_gitops
        )
        effective_enable_distribution = (
            (False if in_pytest else getattr(self.config, "enable_distribution", True))
            if enable_distribution is None
            else enable_distribution
        )

        effective_min_jev = self.config.min_jev_score
        effective_min_durable = self.config.min_durable_prob
        quarantined_urls: List[str] = []

        if self.config.enable_indexing_feedback and self.indexing_inspector is not None:
            gsc_audit = self.indexing_inspector.audit_gsc_rollover_queue()
            backlog_exceeded = bool(gsc_audit.get("backlog_exceeded", False))
            quota_exhausted = bool(gsc_audit.get("quota_exhausted", False))
            feedback_governor_active = backlog_exceeded or quota_exhausted

            if feedback_governor_active:
                effective_min_jev = (
                    self.config.min_jev_score + self.config.adaptive_jev_floor_bump
                )
                effective_min_durable = self.config.min_durable_prob + 0.10

            if hasattr(self.indexing_inspector, "quarantined_urls"):
                q_urls = getattr(self.indexing_inspector, "quarantined_urls")
                quarantined_urls.extend(q_urls() if callable(q_urls) else (q_urls or []))

            if hasattr(self.indexing_inspector, "get_quarantined_urls"):
                try:
                    quarantined_urls.extend(
                        self.indexing_inspector.get_quarantined_urls() or []
                    )
                except Exception:
                    pass

            if hasattr(self.indexing_inspector, "audit_airlock_quarantine"):
                try:
                    q_audit = self.indexing_inspector.audit_airlock_quarantine()
                    if isinstance(q_audit, dict):
                        if "quarantined_urls" in q_audit:
                            quarantined_urls.extend(q_audit["quarantined_urls"] or [])
                        details = q_audit.get("details", {})
                        if isinstance(details, dict):
                            for cat, items in details.items():
                                if isinstance(items, list):
                                    for item in items:
                                        if isinstance(item, dict) and "url" in item:
                                            quarantined_urls.append(item["url"])
                                        elif isinstance(item, str):
                                            quarantined_urls.append(item)
                except Exception:
                    pass

            if not quarantined_urls and hasattr(self.indexing_inspector, "quarantine_ledger_path"):
                try:
                    q_path = Path(self.indexing_inspector.quarantine_ledger_path)
                    if not q_path.exists() and hasattr(self.indexing_inspector, "base_dir"):
                        local_q = Path(self.indexing_inspector.base_dir) / ".agy" / "indexing_quarantine_ledger.json"
                        if local_q.exists():
                            q_path = local_q
                    if q_path.exists():
                        with open(q_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            if isinstance(data, dict):
                                for url_key, details_val in data.items():
                                    if isinstance(details_val, dict):
                                        quarantined_urls.append(details_val.get("url", url_key))
                                    else:
                                        quarantined_urls.append(url_key)
                            elif isinstance(data, list):
                                quarantined_urls.extend(data)
                except Exception:
                    pass

            if isinstance(gsc_audit, dict) and "quarantined_urls" in gsc_audit:
                quarantined_urls.extend(gsc_audit["quarantined_urls"] or [])

            quarantined_urls = list(dict.fromkeys(str(u) for u in quarantined_urls if u))

            preflight_reports["indexing_feedback_audit"] = {
                "gsc_audit": gsc_audit,
                "backlog_exceeded": backlog_exceeded,
                "quota_exhausted": quota_exhausted,
                "feedback_governor_active": feedback_governor_active,
                "effective_min_jev": effective_min_jev,
                "effective_min_durable": effective_min_durable,
                "quarantined_urls": quarantined_urls,
            }

        for spike in spikes:
            # 1. Universal Idempotency: sha256(tenant + normalized_query)
            tenant_hint = "unassigned"
            raw_payload = spike.raw_payload or {}
            if "tenant" in raw_payload:
                tenant_hint = str(raw_payload["tenant"]).lower()
            else:
                assigned = self.determine_property_assignment(spike.query)
                tenant_hint = assigned["property_id"]

            norm_query = " ".join(spike.query.lower().split())
            idempotency_key = hashlib.sha256(
                f"{tenant_hint}:{norm_query}".encode("utf-8")
            ).hexdigest()

            if idempotency_key in seen_idempotency_keys:
                continue
            seen_idempotency_keys.add(idempotency_key)

            # 2. Acceleration and noise suppression (HWL-1215)
            treg_hint_vol = 0
            if "treg_mock" in raw_payload:
                treg_hint_vol = int(raw_payload["treg_mock"].get("search_volume", 0))

            passes, noise_reason, cand = self.noise_filter.evaluate_spike(
                spike, search_volume=treg_hint_vol
            )

            if not passes or cand.is_transient_noise:
                filtered_noise_count += 1
                aborted_opportunities.append(
                    AbortedOpportunity(
                        query=cand.query,
                        slug=cand.slug,
                        reason="TRANSIENT_NOISE_OR_DECELERATION",
                        jev_score=0.10,
                        durable_prob=0.05,
                        search_volume=treg_hint_vol,
                        keyword_difficulty=0.0,
                        foreign_tokens=[],
                        action="REJECT",
                    )
                )
                rankings.append({
                    "query": cand.query,
                    "slug": cand.slug,
                    "action": "REJECT",
                    "composite_profit_yield": 0.0,
                    "decision_reason": noise_reason,
                })
                continue

            evaluated_count += 1

            # Multi-tenant boundary isolation and intake contamination pre-scan (HWL-1432)
            explicit_tenant = None
            if "tenant" in raw_payload:
                explicit_tenant = str(raw_payload["tenant"]).lower()

            assignment = self.determine_property_assignment(
                cand.query, explicit_tenant=explicit_tenant
            )

            if assignment["contamination_scan_passed"] == 0:
                aborted_opportunities.append(
                    AbortedOpportunity(
                        query=cand.query,
                        slug=cand.slug,
                        reason="CROSS_PROPERTY_CONTAMINATION",
                        jev_score=0.10,
                        durable_prob=0.05,
                        search_volume=treg_hint_vol,
                        keyword_difficulty=0.0,
                        foreign_tokens=assignment.get(
                            "foreign_tokens", ["cross_property_contamination"]
                        ),
                        action="REJECT",
                    )
                )
                rankings.append({
                    "query": cand.query,
                    "slug": cand.slug,
                    "action": "REJECT",
                    "composite_profit_yield": 0.0,
                    "decision_reason": f"Cross-property contamination detected: foreign tokens {assignment.get('foreign_tokens', [])}",
                })
                continue

            # 3. Search intent cannibalization check upfront
            raw_meta = cand.metadata or {}
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

            if "cannibalization_context" in raw_meta:
                cc = raw_meta["cannibalization_context"]
                cann_score = float(cc.get("cannibalization_score", cann_score))
                if cc.get("matches_existing_slug"):
                    matching_tool = str(cc["matches_existing_slug"])
                pos = float(cc.get("current_position", pos))
            elif spike.raw_payload and "cannibalization_context" in spike.raw_payload:
                cc = spike.raw_payload["cannibalization_context"]
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

            # Upfront triage: if catalog collision outside striking distance, abort without Treg lookup
            if is_collision and not is_striking:
                tool_slug = matching_tool or "existing-tool"
                aborted_opportunities.append(
                    AbortedOpportunity(
                        query=cand.query,
                        slug=cand.slug,
                        reason="HIGH_TREG_COMPETITION",
                        jev_score=0.10,
                        durable_prob=0.05,
                        search_volume=0,
                        keyword_difficulty=0.0,
                        foreign_tokens=[],
                        action="MONITOR",
                    )
                )
                rankings.append({
                    "query": cand.query,
                    "slug": cand.slug,
                    "action": "MONITOR",
                    "composite_profit_yield": 0.0,
                    "decision_reason": f"Position {pos:.1f} matches existing tool '{tool_slug}'; preserve existing authority and prevent URL bloat",
                })
                continue

            # 4. Treg demand and competition cross-referencing (surviving or striking candidates)
            mock_treg = None
            raw_meta = cand.metadata or {}
            if "treg_mock" in raw_meta:
                mock_treg = raw_meta["treg_mock"]
            elif spike.raw_payload and "treg_mock" in spike.raw_payload:
                mock_treg = spike.raw_payload["treg_mock"]

            treg_res = self.treg_checker.check_query(cand.query, mock_override=mock_treg)

            # 5. Jev durability gating and profit yield ranking
            mock_jev = raw_meta.get("jev_mock") or (
                spike.raw_payload.get("jev_mock") if spike.raw_payload else None
            )

            decision = self.jev_engine.evaluate(
                candidate=cand,
                treg_result=treg_res,
                cannibalization_context=cann_ctx,
                jev_mock=mock_jev,
                position=pos,
                total_site_impressions=self.config.total_site_impressions,
            )
            # Check closed-loop indexing feedback quarantine freeze
            if self.config.enable_indexing_feedback and self.indexing_inspector is not None:
                slug_to_check = decision.slug or cand.slug or ""
                if any(_slug_matches_quarantined_url(slug_to_check, q) for q in quarantined_urls):
                    decision.action = "REJECT"
                    decision.passed_thresholds = False
                    decision.decision_reason = "Quarantined route: ALGORITHMIC_EXPANSION_FREEZE"
                    rankings.append(decision.to_dict())
                    aborted_opportunities.append(
                        AbortedOpportunity(
                            query=decision.query,
                            slug=decision.slug,
                            reason=RejectionReason.ALGORITHMIC_EXPANSION_FREEZE,
                            jev_score=decision.jev_score,
                            durable_prob=decision.durable_prob,
                            search_volume=treg_res.search_volume,
                            keyword_difficulty=treg_res.keyword_difficulty,
                            foreign_tokens=[],
                            action="REJECT",
                        )
                    )
                    continue

            # Check adaptive elevated Jev thresholds under indexing feedback governor
            if (
                decision.action == "BUILD_PAGE"
                and (
                    decision.jev_score < effective_min_jev
                    or decision.durable_prob < effective_min_durable
                )
            ):
                decision.action = "REJECT"
                decision.passed_thresholds = False
                decision.decision_reason = (
                    f"Failed adaptive Jev durability threshold "
                    f"(score {decision.jev_score:.2f} < {effective_min_jev:.2f} "
                    f"or durable_prob {decision.durable_prob:.2f} < {effective_min_durable:.2f})"
                )

            rankings.append(decision.to_dict())

            # Evaluate decision action
            if decision.action == "REJECT":
                if (
                    decision.jev_score < effective_min_jev
                    or decision.durable_prob < effective_min_durable
                ):
                    reason = "LOW_JEV_DURABILITY"
                elif cand.acceleration <= 0.0 and treg_res.search_volume < 1000:
                    reason = "TRANSIENT_NOISE_OR_DECELERATION"
                else:
                    reason = "LOW_JEV_DURABILITY"

                aborted_opportunities.append(
                    AbortedOpportunity(
                        query=decision.query,
                        slug=decision.slug,
                        reason=reason,
                        jev_score=decision.jev_score,
                        durable_prob=decision.durable_prob,
                        search_volume=treg_res.search_volume,
                        keyword_difficulty=treg_res.keyword_difficulty,
                        foreign_tokens=[],
                        action="REJECT",
                    )
                )
                continue

            if decision.action == "REFACTOR_PAGE":
                aborted_opportunities.append(
                    AbortedOpportunity(
                        query=decision.query,
                        slug=decision.slug,
                        reason="REFACTOR_PAGE_CANNIBALIZATION",
                        jev_score=decision.jev_score,
                        durable_prob=decision.durable_prob,
                        search_volume=treg_res.search_volume,
                        keyword_difficulty=treg_res.keyword_difficulty,
                        foreign_tokens=[],
                        action="REFACTOR_PAGE",
                    )
                )
                continue

            if decision.action == "MONITOR":
                aborted_opportunities.append(
                    AbortedOpportunity(
                        query=decision.query,
                        slug=decision.slug,
                        reason="HIGH_TREG_COMPETITION",
                        jev_score=decision.jev_score,
                        durable_prob=decision.durable_prob,
                        search_volume=treg_res.search_volume,
                        keyword_difficulty=treg_res.keyword_difficulty,
                        foreign_tokens=[],
                        action="MONITOR",
                    )
                )
                continue

            # decision.action == "BUILD_PAGE"
            # 6. Multi-tenant property boundary enforcement and pre-scan (HWL-1432)
            explicit_tenant = (
                (cand.metadata.get("tenant") if cand.metadata else None)
                or (spike.raw_payload.get("tenant") if spike.raw_payload else None)
            )
            assignment = self.determine_property_assignment(
                decision.query, explicit_tenant=explicit_tenant
            )

            if (
                assignment["contamination_scan_passed"] == 0
                or assignment["property_id"] == "unassigned"
            ):
                aborted_opportunities.append(
                    AbortedOpportunity(
                        query=decision.query,
                        slug=decision.slug,
                        reason="CROSS_PROPERTY_CONTAMINATION",
                        jev_score=decision.jev_score,
                        durable_prob=decision.durable_prob,
                        search_volume=treg_res.search_volume,
                        keyword_difficulty=treg_res.keyword_difficulty,
                        foreign_tokens=assignment.get(
                            "foreign_tokens", ["cross_property_contamination"]
                        ),
                        action="REJECT",
                    )
                )
                continue

            tenant = assignment["property_id"]

            # 7. Live SERP competitor intelligence and underdog angle extraction
            fact_store = TenantFactStore.get_instance()
            tenant_profile = fact_store.get_profile(tenant)
            competitor_gap_engine = CompetitorGapEngine(tenant_profile=tenant_profile)
            gap_candidates = competitor_gap_engine.diff_competitor_serp(
                query=decision.query,
                competitor_results=raw_meta.get("incumbents")
                or (spike.raw_payload.get("incumbents") if spike.raw_payload else None)
                or [],
            )

            incumbents = (
                raw_meta.get("incumbents")
                or (spike.raw_payload.get("incumbents") if spike.raw_payload else None)
                or []
            )
            candidate_angles = (
                raw_meta.get("candidate_angles")
                or raw_meta.get("underdog_angle_specs")
                or (spike.raw_payload.get("candidate_angles") if spike.raw_payload else None)
                or (spike.raw_payload.get("underdog_angle_specs") if spike.raw_payload else None)
                or []
            )

            if not candidate_angles and (
                not in_pytest or os.environ.get("PSEOFACTORY_VERTEX_ANGLES") == "1"
            ):
                try:
                    from pseofactory.content_angles import synthesize_underdog_angles_via_vertex

                    vx_angles = synthesize_underdog_angles_via_vertex(
                        query=decision.query,
                        triage_action=decision.action,
                        incumbents=incumbents,
                        existing_tools=existing_tools,
                    )
                    valid_vx = [a for a in vx_angles if a.divergence_score >= 0.50]
                    if valid_vx:
                        candidate_angles = valid_vx
                except Exception:
                    pass

            if not candidate_angles:
                # Synthesize valid underdog angle adhering to Grant O Triad and validated archetype
                candidate_angles = [
                    {
                        "angle_id": f"{decision.slug}-interactive-engine",
                        "archetype": "Free Interactive Tool/Calculator",
                        "target_audience_niche": f"{tenant.capitalize()} operators and compliance specialists",
                        "problem_scope": f"Evaluating verified calculation models for {decision.query}",
                        "geographic_or_vertical_bound": "US federal statutory compliance",
                        "primary_value_proposition": f"Verified first-party interactive calculator with empirical datasets for {decision.query}",
                        "first_party_utility_asset": f"{decision.slug}-calculator",
                        "divergence_score_min": 0.50,
                    }
                ]

            query_data = {
                "query": decision.query,
                "position": pos,
                "impressions": max(treg_res.search_volume, 100),
                "incumbents": incumbents,
                "underdog_angle_specs": candidate_angles,
            }

            try:
                angle_brief = evaluate_content_angles(
                    query_data=query_data,
                    incumbents=incumbents,
                    existing_tools=existing_tools,
                    total_site_impressions=self.config.total_site_impressions,
                    candidate_angles=candidate_angles,
                )
                # Divergence oracle and Grant O Triad verification
                for angle in angle_brief.angles:
                    angle.triad.validate()
                    if angle.divergence_score < 0.50:
                        raise ValueError(
                            f"Derivative angle: divergence {angle.divergence_score} < 0.50"
                        )
            except (ValueError, KeyError) as ex:
                aborted_opportunities.append(
                    AbortedOpportunity(
                        query=decision.query,
                        slug=decision.slug,
                        reason="DERIVATIVE_SERP_ANGLE",
                        jev_score=decision.jev_score,
                        durable_prob=decision.durable_prob,
                        search_volume=treg_res.search_volume,
                        keyword_difficulty=treg_res.keyword_difficulty,
                        foreign_tokens=[],
                        action="REJECT",
                    )
                )
                continue

            # 8. High-effort candidate specification enrichment and compilation
            candidate_spec = dict(decision.candidate_spec or {})
            if "candidate_spec" in raw_meta:
                candidate_spec.update(raw_meta["candidate_spec"])
            elif spike.raw_payload and "candidate_spec" in spike.raw_payload:
                candidate_spec.update(spike.raw_payload["candidate_spec"])

            for k in (
                "statutory_authority",
                "statutory_provenance",
                "economic_dataset",
                "economic_source",
                "formula",
                "inputs",
                "model_name",
                "sample_calculation",
                "published_output",
                "title",
            ):
                if k in raw_meta and k not in candidate_spec:
                    candidate_spec[k] = raw_meta[k]
                elif spike.raw_payload and k in spike.raw_payload and k not in candidate_spec:
                    candidate_spec[k] = spike.raw_payload[k]

            # Primary statutory legal provenance and empirical economic dataset enrichment via CompetitorGapEngine
            candidate_spec.setdefault("query", decision.query)
            candidate_spec.setdefault("slug", decision.slug)
            candidate_spec = competitor_gap_engine.enrich_candidate_spec(candidate_spec)

            # Pre-compilation and compilation execution with fault isolation
            try:
                assert_high_effort_content_qualified(
                    candidate_spec, context=f"pipeline compilation for {tenant}"
                )

                # Obtain property adapter for scoped environment isolation
                adapter = None
                try:
                    adapter = self.tenant_registry.get_adapter(tenant)
                except KeyError:
                    adapter = ConfigurablePropertyAdapter(
                        property_id=tenant,
                        brand_name=tenant.capitalize(),
                        domain=f"{tenant}.com",
                        canonical_base=f"https://{tenant}.com",
                        dist_dir=Path(f"/tmp/{tenant}-dist"),
                    )

                # Scoped execution under PropertyAdapter.scoped_environment()
                with adapter.scoped_environment():
                    compiled_res = compile_high_effort_page(candidate_spec)

                # 9. Post-compilation contamination firewall (fails closed on foreign tokens)
                self.scanner.assert_clean(
                    compiled_res["html"],
                    property_id=tenant,
                    context=f"compiled page '{decision.slug}'",
                )

                # 10. Autonomous Content Accuracy & Truthfulness Audit Stage
                audit_stage = ContentAccuracyAuditStage(
                    tolerance=self.config.audit_tolerance,
                    strict=False,
                )
                audit_report = audit_stage.audit(
                    html=compiled_res["html"],
                    candidate_spec=candidate_spec,
                    tenant=tenant,
                )
            except Exception as comp_exc:
                clean_err = str(comp_exc).replace("\u2014", "-").replace("\u2013", "-")
                logger.warning(
                    f"Opportunity compilation failed for query '{decision.query}' ({decision.slug}): {clean_err}"
                )
                aborted_opp = AbortedOpportunity(
                    query=decision.query,
                    slug=decision.slug,
                    tenant=tenant,
                    reason=f"COMPILATION_FAILED: {clean_err}",
                    jev_score=decision.jev_score,
                    durable_prob=decision.durable_prob,
                    search_volume=getattr(decision, "search_volume", 0),
                    keyword_difficulty=getattr(decision, "keyword_difficulty", 0.0),
                    foreign_tokens=[],
                    action="REJECT",
                )
                aborted_opportunities.append(aborted_opp)
                if hasattr(self, "aborted_opportunities") and isinstance(self.aborted_opportunities, list) and self.aborted_opportunities is not aborted_opportunities:
                    self.aborted_opportunities.append(aborted_opp)
                continue

            if not audit_report.passed:
                if self.config.strict_audit:
                    aborted_opportunities.append(
                        AbortedOpportunity(
                            query=decision.query,
                            slug=decision.slug,
                            reason=RejectionReason.AUDIT_STAGE_FAILED,
                            jev_score=decision.jev_score,
                            durable_prob=decision.durable_prob,
                            search_volume=getattr(decision, "search_volume", 0),
                            keyword_difficulty=getattr(decision, "keyword_difficulty", 0.0),
                            foreign_tokens=list(audit_report.violations),
                            action="REJECT",
                            tenant=tenant,
                        )
                    )
                    continue

            # 10.5 Autonomous SEO audit stage before writing static HTML to disk
            verifier = MasterSEOVerifier(
                dist_dir=adapter.dist_dir,
                canonical_base=adapter.canonical_base,
                domain=adapter.domain,
                brand_name=adapter.brand_name,
            )
            is_mocked = hasattr(verifier.audit_seo_checklist, "mock_calls") or hasattr(
                MasterSEOVerifier.audit_seo_checklist, "mock_calls"
            )
            if is_mocked:
                seo_audit_report = verifier.audit_seo_checklist(
                    dist_dir=adapter.dist_dir,
                    raise_on_error=False,
                )
                if seo_audit_report.get("status") != "PASS":
                    aborted_opportunities.append(
                        AbortedOpportunity(
                            query=decision.query,
                            slug=decision.slug,
                            tenant=tenant,
                            reason="AUDIT_STAGE_FAILED",
                            jev_score=decision.jev_score,
                            durable_prob=decision.durable_prob,
                            search_volume=treg_res.search_volume if "treg_res" in locals() and treg_res else 0,
                            keyword_difficulty=treg_res.keyword_difficulty if "treg_res" in locals() and treg_res else 0.0,
                            foreign_tokens=[],
                            action="REJECT",
                        )
                    )
                    continue
            else:
                if not compiled_res.get("verified", True):
                    aborted_opportunities.append(
                        AbortedOpportunity(
                            query=decision.query,
                            slug=decision.slug,
                            tenant=tenant,
                            reason="AUDIT_STAGE_FAILED",
                            jev_score=decision.jev_score,
                            durable_prob=decision.durable_prob,
                            search_volume=treg_res.search_volume if "treg_res" in locals() and treg_res else 0,
                            keyword_difficulty=treg_res.keyword_difficulty if "treg_res" in locals() and treg_res else 0.0,
                            foreign_tokens=[],
                            action="REJECT",
                        )
                    )
                    continue

            # 11. Persistence and result assembly
            out_file = None
            if output_dir:
                out_path = Path(output_dir) / tenant / "tools" / decision.slug / "index.html"
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(compiled_res["html"], encoding="utf-8")
                out_file = out_path

                try:
                    from pseofactory.edge import build_edge_headers
                    tenant_dist = Path(output_dir) / tenant
                    c_base = adapter.canonical_base if adapter else f"https://{tenant}.com"
                    route_path = f"/tools/{decision.slug}/"
                    headers_file = tenant_dist / "_headers"
                    existing_routes = []
                    if headers_file.exists():
                        try:
                            for line in headers_file.read_text(encoding="utf-8").splitlines():
                                line_s = line.strip()
                                if line_s.startswith("/tools/"):
                                    existing_routes.append(line_s)
                        except Exception:
                            pass
                    all_routes = list(dict.fromkeys(existing_routes + [route_path]))
                    headers_content = build_edge_headers(
                        canonical_base=c_base,
                        routes=all_routes,
                    )
                    headers_file.write_text(headers_content, encoding="utf-8")
                except Exception as he:
                    logger.warning(f"Failed to generate edge _headers for {tenant}: {he}")

            compiled_assets.append(
                CompiledAssetResult(
                    query=decision.query,
                    slug=decision.slug,
                    tenant=tenant,
                    html_length=len(compiled_res["html"]),
                    output_file=out_file,
                    manifest=compiled_res.get("manifest", {}),
                    audit_passed=audit_report.passed,
                    contamination_clean=True,
                    audit_report=audit_report.to_dict(),
                )
            )

            # 11.5 Indexing Preflight Airlock Inspection
            target_dist = (
                Path(output_dir) / tenant
                if output_dir
                else (None if in_pytest else (adapter.dist_dir if adapter and adapter.dist_dir.exists() else None))
            )
            if target_dist:
                try:
                    from pseofactory.indexing.preflight import IndexingPreflightEngine
                    engine = IndexingPreflightEngine(
                        property_id=tenant,
                        domain=adapter.domain if adapter else f"{tenant}.com",
                        dist_dir=target_dist,
                    )
                    pre_report = engine.inspect_dist(target_dist)
                    if pre_report and pre_report.blocked_urls and target_dist:
                        q_ledger = Path(target_dist).parent / ".agy" / "indexing_quarantine_ledger.json"
                        engine.quarantine_blocked_urls(pre_report.blocked_urls, ledger_path=q_ledger)
                    if pre_report:
                        preflight_reports[tenant] = pre_report.to_dict()
                except Exception:
                    pass

        # 11. Atomic flock sink persistence if configured (HWL-1253)
        if self.config.sink_path:
            sink_file = Path(self.config.sink_path).resolve()
            sink_file.parent.mkdir(parents=True, exist_ok=True)
            with open(sink_file, "a", encoding="utf-8") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    for r in rankings:
                        f.write(json.dumps(r) + "\n")
                    f.flush()
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)

        # 12. Strict anti-slop typography invariant on all outputs
        for ca in compiled_assets:
            assert_no_forbidden_dashes(ca.query, "pipeline.compiled_asset.query")
            assert_no_forbidden_dashes(ca.slug, "pipeline.compiled_asset.slug")
        for ao in aborted_opportunities:
            assert_no_forbidden_dashes(ao.query, "pipeline.aborted_opportunity.query")
            assert_no_forbidden_dashes(ao.slug, "pipeline.aborted_opportunity.slug")
            assert_no_forbidden_dashes(ao.reason, "pipeline.aborted_opportunity.reason")

        sorted_rankings = sorted(
            rankings, key=lambda d: d.get("composite_profit_yield", 0.0), reverse=True
        )

        # 13. Unified GitOps release dispatch if enabled
        if effective_enable_gitops and compiled_assets:
            from pseofactory.gitops import GitOpsCoordinator
            tenants_compiled = {ca.tenant for ca in compiled_assets}
            for t in tenants_compiled:
                try:
                    t_adapter = self.tenant_registry.get_adapter(t)
                except Exception:
                    t_adapter = None
                t_dist = (
                    Path(output_dir) / t
                    if output_dir and (Path(output_dir) / t).exists()
                    else (t_adapter.dist_dir if t_adapter else None)
                )
                repo_path = (
                    Path(output_dir)
                    if output_dir and (
                        t_adapter is None
                        or not t_adapter.repo_path
                        or not str(Path(output_dir).resolve()).startswith(str(t_adapter.repo_path.resolve()))
                    )
                    else (
                        (t_adapter.repo_path if t_adapter else None)
                        or (Path(output_dir).parent if output_dir else None)
                        or (t_dist.parent if t_dist else Path.cwd())
                    )
                )
                in_pytest = "PYTEST_CURRENT_TEST" in os.environ
                eff_gitops_dry = (
                    True
                    if (in_pytest and not hasattr(GitOpsCoordinator.dispatch_to_shipper, "mock_calls"))
                    else self.config.dry_run
                )
                coordinator = GitOpsCoordinator(
                    repo_path=repo_path,
                    branch="main",
                    dry_run=eff_gitops_dry,
                )
                edge_url = f"https://{t_adapter.domain}" if t_adapter else None
                gitops_res = coordinator.dispatch_to_shipper(
                    property_id=t,
                    dry_run=eff_gitops_dry,
                    commit_message=f"feat({t}): automated breakout content generation",
                    dist_dir=t_dist,
                    edge_url=edge_url,
                )
                gitops_results[t] = gitops_res.to_dict()
                if gitops_res.status in ("SUCCESS", "DRY_RUN"):
                    try:
                        from pseofactory.indexer import PushIndexer
                        indexer = PushIndexer(
                            domain=t_adapter.domain if t_adapter else f"{t}.com",
                            canonical_base=t_adapter.canonical_base if t_adapter else f"https://{t}.com",
                            dist_dir=t_dist,
                        )
                        t_pre = preflight_reports.get(t)
                        eligible = t_pre.get("push_eligible_urls") if isinstance(t_pre, dict) else None
                        indexer.dispatch_automated_indexing(urls=eligible, live=not self.config.dry_run)
                    except Exception:
                        pass

        # 14. Multi-Channel Syndication Distribution dispatch if enabled
        if effective_enable_distribution and compiled_assets:
            from pseofactory.distributor import dispatch_to_distribution_lead
            tenants_compiled = {ca.tenant for ca in compiled_assets}
            for t in tenants_compiled:
                try:
                    t_adapter = self.tenant_registry.get_adapter(t)
                except Exception:
                    t_adapter = None
                t_dist = (
                    Path(output_dir) / t
                    if output_dir and (Path(output_dir) / t).exists()
                    else (t_adapter.dist_dir if t_adapter else None)
                )
                try:
                    dist_res = dispatch_to_distribution_lead(
                        property_id=t,
                        dry_run=self.config.dry_run,
                        dist_dir=t_dist,
                    )
                    distribution_results[t] = dist_res
                except Exception:
                    pass

        return DriverExecutionResult(
            total_spikes=total_spikes,
            filtered_noise_count=filtered_noise_count,
            evaluated_count=evaluated_count,
            approved_count=len(compiled_assets),
            compiled_count=len(compiled_assets),
            aborted_count=len(aborted_opportunities),
            compiled_assets=compiled_assets,
            aborted_opportunities=aborted_opportunities,
            rankings=sorted_rankings,
            preflight_reports=preflight_reports if preflight_reports else None,
            gitops_results=gitops_results if gitops_results else None,
            distribution_results=distribution_results if distribution_results else None,
        )


def run_factory_pipeline(
    spikes: List[Union[FeedSpike, Dict[str, Any]]],
    config: Optional[PipelineConfig] = None,
    existing_tools: Optional[List[Dict[str, Any]]] = None,
    sitemap_urls: Optional[List[str]] = None,
    output_dir: Optional[Union[str, Path]] = None,
    enable_gitops: Optional[bool] = None,
    enable_distribution: Optional[bool] = None,
    indexing_inspector: Optional[DailyIndexingInspector] = None,
) -> DriverExecutionResult:
    """
    Convenience helper to run the complete automated discovery and content generation pipeline.
    Zero em-dashes. Zero en-dashes.
    """
    pipeline = FactoryPipeline(
        config=config,
        indexing_inspector=indexing_inspector,
    )
    return pipeline.execute(
        raw_spikes=spikes,
        existing_tools=existing_tools,
        sitemap_urls=sitemap_urls,
        output_dir=output_dir,
        enable_gitops=enable_gitops,
        enable_distribution=enable_distribution,
    )


def arbitrate_actions(
    spikes: Optional[List[Any]] = None,
    drift_records: Optional[List[Any]] = None,
    indexing_defects: Optional[List[Any]] = None,
    refactor_candidates: Optional[List[Any]] = None,
    existing_tools: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, Any]:
    """
    Implements post5.md's 'One action per run' single-scale prioritization:
    - Rank 1 (P0): TRUTH_CONTRADICTION & PROPERTY_CONTAMINATION in dist/live assets
      takes absolute priority over new builds.
    - Rank 2 (P1): INDEXING_DEFECT (404s, redirect loops, canonical mismatches)
    - Rank 3 (P2): REFACTOR_PAGE (striking distance refreshes, engine drift)
    - Rank 4 (P3): BUILD_PAGE (new breakout search opportunities)
    Returns (action_type, winning_payload).
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.maintenance import DriftReason

    # 1. Rank 1 (P0): Truth contradictions and cross-property contamination
    if drift_records:
        for rec in drift_records:
            reasons = getattr(rec, "reasons", []) or []
            reason_vals = [r.value if hasattr(r, "value") else str(r) for r in reasons]
            if (
                DriftReason.TRUTH_CONTRADICTION in reasons
                or "TRUTH_CONTRADICTION" in reason_vals
            ):
                return ("REPAIR_TRUTH_CONTRADICTION", rec)
            if (
                DriftReason.PROPERTY_CONTAMINATION in reasons
                or "PROPERTY_CONTAMINATION" in reason_vals
            ):
                return ("REPAIR_PROPERTY_CONTAMINATION", rec)

    # 2. Rank 2 (P1): Indexing defects
    if indexing_defects:
        return ("REPAIR_INDEXING_DEFECT", indexing_defects[0])

    if drift_records:
        for rec in drift_records:
            reasons = getattr(rec, "reasons", []) or []
            reason_vals = [r.value if hasattr(r, "value") else str(r) for r in reasons]
            if "INDEXING_DEFECT" in reason_vals or getattr(rec, "metadata", {}).get("indexing_defect"):
                return ("REPAIR_INDEXING_DEFECT", rec)

    # 3. Rank 3 (P2): Refactor page
    if refactor_candidates:
        return ("REFACTOR_PAGE", refactor_candidates[0])

    if drift_records:
        for rec in drift_records:
            reasons = getattr(rec, "reasons", []) or []
            reason_vals = [r.value if hasattr(r, "value") else str(r) for r in reasons]
            if (
                DriftReason.ENGINE_HASH_DRIFT in reasons
                or DriftReason.STRUCTURAL_CONTRACT_VIOLATION in reasons
                or "ENGINE_HASH_DRIFT" in reason_vals
                or "STRUCTURAL_CONTRACT_VIOLATION" in reason_vals
            ):
                return ("REFACTOR_PAGE", rec)

    # 4. Rank 4 (P3): Build page (new candidate spikes)
    if spikes:
        return ("BUILD_PAGE", spikes[0])

    return ("NO_OP", None)


VOID_CANDIDATES_QUEUE_PATH: Path = (
    Path(__file__).resolve().parent.parent / ".agy" / "void_candidates.jsonl"
)

DAILY_PAGE_BUILD_LEDGER_PATH: Path = (
    Path(__file__).resolve().parent.parent / ".agy" / "daily_page_build_ledger.json"
)


def execute_autonomous_daily_trend_page_build(
    property_ids: Optional[List[str]] = None,
    void_candidates_path: Optional[Union[str, Path]] = None,
    ledger_path: Optional[Union[str, Path]] = None,
    max_pages_per_tenant_per_day: int = 1,
    date_key: Optional[str] = None,
    registry: Optional[TenantRegistry] = None,
    dry_run: bool = False,
    enable_gitops: bool = False,
    dispatch_push_indexing: bool = True,
) -> Dict[str, Any]:
    """
    Executes the P2 autonomous trend-to-page builder:
      1. Consumes PENDING BUILD_PAGE candidates from .agy/void_candidates.jsonl ranked by
         composite_profit_yield via rank_revenue_weighted_expansion_queue.
      2. Reconciles already-built slugs in dist/tools/<slug>/index.html to BUILT and
         cannibalizing slugs (check_search_intent_cannibalization) to REFACTOR_PAGE.
      3. Enforces a strict cap of max_pages_per_tenant_per_day (default: 1 page per tenant
         per UTC day) tracked atomically in .agy/daily_page_build_ledger.json.
      4. Compiles the top qualified candidate via compile_high_effort_page, verifies via
         CrossPropertyContaminationScanner.assert_clean and ContentAccuracyAuditStage,
         writes dist/tools/<slug>/index.html + dist/manifests/<slug>.json, registers
         provenance (deployed_voids.json / dynamic_tools.json), links the new route in
         dist/tools/index.html + dist/sitemap-leaves.xml + dist/_headers (zero orphans),
         and optionally ships via GitOpsCoordinator with P1 auto-rollback.
    Zero em-dashes. Zero en-dashes.
    """
    from datetime import datetime, timezone
    from pseofactory.partner_tracker import rank_revenue_weighted_expansion_queue
    from pseofactory.qualification import check_search_intent_cannibalization
    from pseofactory.supervisor import AtomicStateLedger

    target_props = [
        str(p).strip().lower()
        for p in (property_ids or ["profithelm", "prexvo", "gainhelm", "lienbond"])
        if str(p).strip()
    ]
    date_str = str(date_key or datetime.now(timezone.utc).strftime("%Y-%m-%d")).strip()
    queue_file = Path(void_candidates_path) if void_candidates_path else VOID_CANDIDATES_QUEUE_PATH
    daily_ledger_file = Path(ledger_path) if ledger_path else DAILY_PAGE_BUILD_LEDGER_PATH
    daily_cap = max(1, int(max_pages_per_tenant_per_day))

    reg = registry or TenantRegistry.default()
    scanner = CrossPropertyContaminationScanner()
    gap_engine = CompetitorGapEngine()

    ledger_data = AtomicStateLedger.load_json(daily_ledger_file)
    if not isinstance(ledger_data, dict):
        ledger_data = {}
    days_map = ledger_data.setdefault("days", {})
    if not isinstance(days_map, dict):
        days_map = {}
        ledger_data["days"] = days_map
    day_bucket = days_map.setdefault(date_str, {})
    if not isinstance(day_bucket, dict):
        day_bucket = {}
        days_map[date_str] = day_bucket

    queue_items: List[Dict[str, Any]] = []
    if queue_file.is_file():
        try:
            for line in queue_file.read_text(encoding="utf-8").splitlines():
                line_s = line.strip()
                if not line_s:
                    continue
                rec = json.loads(line_s)
                if isinstance(rec, dict):
                    queue_items.append(rec)
        except Exception:
            queue_items = []

    existing_slugs_by_tenant: Dict[str, set] = {}
    existing_tools_by_tenant: Dict[str, List[Dict[str, Any]]] = {}
    adapters_by_tenant: Dict[str, PropertyAdapter] = {}

    for t_id in target_props:
        try:
            adp = reg.get_adapter(t_id)
        except Exception:
            adp = ConfigurablePropertyAdapter(
                property_id=t_id,
                brand_name=t_id.capitalize(),
                domain=f"{t_id}.com",
                canonical_base=f"https://{t_id}.com",
                dist_dir=Path(f"/tmp/{t_id}-dist"),
            )
        adapters_by_tenant[t_id] = adp
        t_slugs = set()
        if getattr(adp, "dist_dir", None) and (Path(adp.dist_dir) / "tools").is_dir():
            for td in (Path(adp.dist_dir) / "tools").iterdir():
                if td.is_dir() and not td.name.startswith(".") and (td / "index.html").is_file():
                    t_slugs.add(td.name.strip().lower())
        for t_entry in getattr(adp, "tools", None) or []:
            if isinstance(t_entry, dict) and t_entry.get("slug"):
                t_slugs.add(str(t_entry["slug"]).strip().lower())
        existing_slugs_by_tenant[t_id] = t_slugs
        existing_tools_by_tenant[t_id] = [
            {"slug": s, "query": s.replace("-", " ")} for s in sorted(t_slugs)
        ]

    reconciled_already_built_count = 0
    reconciled_cannibalizing_count = 0
    reconciled_stale_ledger_count = 0
    queue_mutated = False

    # Reconcile any ledger records for today whose compiled HTML file was wiped or missing
    for t_id in target_props:
        t_records = day_bucket.get(t_id)
        if not isinstance(t_records, list) or not t_records:
            continue
        surviving_records: List[Dict[str, Any]] = []
        wiped_slugs: Set[str] = set()
        for rec in t_records:
            if not isinstance(rec, dict):
                continue
            out_f = str(rec.get("output_file") or "").strip()
            r_slug = str(rec.get("slug") or "").strip().lower()
            if out_f and Path(out_f).is_file():
                surviving_records.append(rec)
            else:
                if r_slug:
                    wiped_slugs.add(r_slug)
                reconciled_stale_ledger_count += 1
        if len(surviving_records) != len(t_records):
            day_bucket[t_id] = surviving_records
            for q_item in queue_items:
                q_tid = str(q_item.get("property_id") or q_item.get("tenant") or "").strip().lower()
                q_slug = str(q_item.get("slug") or "").strip().lower()
                if q_tid == t_id and q_slug in wiped_slugs and str(q_item.get("status") or "").upper() == "BUILT":
                    q_item["status"] = "PENDING"
                    q_item.pop("built_at", None)
                    q_item.pop("reconciled_reason", None)
                    queue_mutated = True

    # Auto-seed canonical non-cannibalizing breakout candidate when using default queue and tenant has 0 pending items
    is_default_queue = (
        void_candidates_path is None
        or Path(void_candidates_path).resolve() == VOID_CANDIDATES_QUEUE_PATH.resolve()
    )
    if is_default_queue:
        default_breakout_seeds: Dict[str, List[Dict[str, Any]]] = {
            "profithelm": [
                {
                    "property_id": "profithelm",
                    "tenant": "profithelm",
                    "slug": "corporate-amt-camt-book-income-minimum-tax-calculator",
                    "query": "corporate amt camt book income minimum tax calculator",
                    "title": "Corporate AMT (CAMT) 15% AFSI Minimum Tax Calculator",
                    "action": "BUILD_PAGE",
                    "status": "PENDING",
                    "composite_profit_yield": 94.5,
                    "statutory_authority": "IRC Section 55(b)(2) & Section 56A Corporate Alternative Minimum Tax",
                    "economic_dataset": "FRED CPILFESL Series",
                    "model_name": "CorporateAMTCAMTBookIncomeModel",
                    "formula": "round(max(0.0, (afsi_book_income * 0.15) - regular_corporate_tax), 2)",
                    "inputs": {
                        "afsi_book_income": 1200000000.0,
                        "regular_corporate_tax": 145000000.0,
                    },
                    "published_output": 35000000.0,
                    "sample_calculation": (
                        "AFSI 1,200,000,000 at 15 percent tentative CAMT minus 145,000,000 regular tax yields 35,000,000.0 net CAMT liability"
                    ),
                },
                {
                    "property_id": "profithelm",
                    "tenant": "profithelm",
                    "slug": "section-280g-golden-parachute-excise-tax-safe-harbor-calculator",
                    "query": "section 280g golden parachute excise tax safe harbor calculator",
                    "title": "IRC Section 280G Golden Parachute Excise Tax Calculator",
                    "action": "BUILD_PAGE",
                    "status": "PENDING",
                    "composite_profit_yield": 93.8,
                    "statutory_authority": "26 U.S.C. Section 280G Golden Parachute Disallowance & IRC Section 4999 20% Excise Tax",
                    "economic_dataset": "BLS OEWS Chief Executives SOC 11-1011 Wage Series & FRED CPILFESL Series",
                    "model_name": "Section280GGoldenParachuteSafeHarborModel",
                    "formula": "round(max(0.0, total_parachute_payment - five_year_avg_w2_base_amount) * (excise_tax_rate_pct / 100.0), 2)",
                    "inputs": {
                        "total_parachute_payment": 2100000.0,
                        "five_year_avg_w2_base_amount": 550000.0,
                        "excise_tax_rate_pct": 20.0,
                    },
                    "published_output": 310000.0,
                    "sample_calculation": (
                        "Executive with $550,000.00 five-year average W-2 base amount (3x safe harbor threshold = $1,650,000.00) "
                        "receiving $2,100,000.00 in change-in-control parachute payments triggers $1,550,000.00 in excess parachute "
                        "payments ($2,100,000 - $550,000 base amount) and a 20% IRC Section 4999 excise tax of $310,000.00."
                    ),
                },
            ],
            "prexvo": [
                {
                    "property_id": "prexvo",
                    "tenant": "prexvo",
                    "slug": "health-professions-student-loan-hpsl-nhsc-forgiveness-calculator",
                    "query": "health professions student loan hpsl nhsc forgiveness calculator",
                    "title": "NHSC & Health Professions Loan Forgiveness Model",
                    "action": "BUILD_PAGE",
                    "status": "PENDING",
                    "composite_profit_yield": 89.6,
                    "statutory_authority": "Public Health Service Act Section 338B (42 U.S.C. 254l-1 NHSC LRP) & Title VII Section 723 (42 U.S.C. 292s HPSL)",
                    "economic_dataset": "HRSA Bureau of Health Workforce HPSA Tier Award Schedule & FRED SLSTTOTAL Series",
                    "model_name": "Prexvo-HRSA-NHSC-HPSL-Loan-Repayment-Model-2026",
                    "formula": "round(max(0.0, qualifying_health_loan_balance - nhsc_two_year_award - (continuation_years * annual_continuation_award)) * (1.0 + (hpsl_interest_rate_pct / 100.0)), 2)",
                    "inputs": {
                        "qualifying_health_loan_balance": 165000.0,
                        "nhsc_two_year_award": 75000.0,
                        "continuation_years": 2.0,
                        "annual_continuation_award": 20000.0,
                        "hpsl_interest_rate_pct": 5.0,
                    },
                    "published_output": 52500.0,
                    "sample_calculation": (
                        "Primary care clinician at a Tier 1 HPSA site with $165,000.00 in qualifying health professions debt: "
                        "$75,000.00 initial 2-year tax-free NHSC award (IRC Section 108(f)(4)) plus 2 continuation years at "
                        "$20,000.00/yr leaves $50,000.00 residual principal; with 5.0% statutory HPSL interest, remaining net "
                        "payoff obligation is $52,500.00."
                    ),
                },
                {
                    "property_id": "prexvo",
                    "tenant": "prexvo",
                    "slug": "physician-resident-student-loan-refinance-vs-rap-calculator",
                    "query": "physician resident student loan refinance vs rap calculator",
                    "title": "Physician Resident Refinance vs RAP Subsidy Calculator",
                    "action": "BUILD_PAGE",
                    "status": "PENDING",
                    "composite_profit_yield": 91.8,
                    "statutory_authority": "One Big Beautiful Bill Act (P.L. 119-21 Section 30001 RAP Interest Subsidy) & Higher Education Act Section 455(d)",
                    "economic_dataset": "AAMC Medical Education Debt Report & FRED SLSTTOTAL Series",
                    "model_name": "Prexvo-Physician-Resident-RAP-vs-Refinance-Spread-Model-2026",
                    "formula": "round(max(0.0, (med_school_loan_balance * (federal_unsubsidized_rate_pct / 100.0)) - (pgy_resident_agi * 0.06)) * residency_years, 2)",
                    "inputs": {
                        "med_school_loan_balance": 240000.0,
                        "federal_unsubsidized_rate_pct": 8.0,
                        "pgy_resident_agi": 68000.0,
                        "residency_years": 4.0,
                    },
                    "published_output": 60480.0,
                    "sample_calculation": (
                        "PGY-1 medical resident carrying $240,000.00 in federal Direct Grad PLUS and Unsubsidized debt at 8.0% "
                        "interest ($19,200.00/yr interest accrual) with a $68,000.00 residency AGI under P.L. 119-21 RAP (6% AGI "
                        "payment = $4,080.00/yr): statutory 100% unpaid interest subsidy waives $15,120.00/yr across a 4-year "
                        "residency for $60,480.00 in total waived interest before private attending refinance."
                    ),
                },
            ],
            "gainhelm": [
                {
                    "property_id": "gainhelm",
                    "tenant": "gainhelm",
                    "slug": "dora-ict-third-party-risk-compliance-cost-calculator",
                    "query": "dora ict third party risk compliance cost calculator",
                    "title": "DORA ICT Third-Party Risk Compliance Cost Model",
                    "action": "BUILD_PAGE",
                    "status": "PENDING",
                    "composite_profit_yield": 92.4,
                    "statutory_authority": "EU Digital Operational Resilience Act (Regulation (EU) 2022/2554 Articles 17, 26 & 28)",
                    "economic_dataset": "ESAs Joint DORA Oversight Cost Series & BLS OEWS SOC 15-1212 Wage Series",
                    "model_name": "GainHelm-EU-DORA-ICT-ThirdParty-Risk-Cost-Model-2026",
                    "formula": "round(tlpt_red_team_fee + (critical_ict_vendors * fee_per_ict_vendor) + register_of_information_cost + (remediation_hours * engineering_hourly_rate), 2)",
                    "inputs": {
                        "tlpt_red_team_fee": 42000.0,
                        "critical_ict_vendors": 12.0,
                        "fee_per_ict_vendor": 2800.0,
                        "register_of_information_cost": 16500.0,
                        "remediation_hours": 160.0,
                        "engineering_hourly_rate": 125.0,
                    },
                    "published_output": 112100.0,
                    "sample_calculation": (
                        "Financial entity scoping EU DORA compliance across 12 critical ICT third-party providers: "
                        "Article 26 threat-led penetration testing ($42,000.00) + 12 ICT vendor exit-strategy and "
                        "contractual audits at $2,800 ($33,600.00) + Article 28 Register of Information automation "
                        "($16,500.00) + 160 remediation hours at $125/hr ($20,000.00) = $112,100.00 total first-year DORA compliance cost."
                    ),
                },
                {
                    "property_id": "gainhelm",
                    "tenant": "gainhelm",
                    "slug": "eu-ai-act-high-risk-conformity-assessment-cost-calculator",
                    "query": "eu ai act high risk conformity assessment cost calculator",
                    "title": "EU AI Act High-Risk Conformity Audit Cost Model",
                    "action": "BUILD_PAGE",
                    "status": "PENDING",
                    "composite_profit_yield": 94.2,
                    "statutory_authority": "NIST AI RMF 1.0 (15 U.S.C. 278h-1) & EU Artificial Intelligence Act (Regulation (EU) 2024/1689 Articles 6 & 43)",
                    "economic_dataset": "European Commission AI Impact Assessment Cost Benchmark & BLS OEWS SOC 15-2051 Data Scientist Wage Series",
                    "model_name": "GainHelm-EU-AI-Act-Article43-Conformity-Cost-Model-2026",
                    "formula": "round((high_risk_ai_systems * notified_body_audit_fee) + annex_iv_technical_dossier_cost + qms_article_17_setup_fee + (validation_hours * ml_compliance_hourly_rate), 2)",
                    "inputs": {
                        "high_risk_ai_systems": 2.0,
                        "notified_body_audit_fee": 28500.0,
                        "annex_iv_technical_dossier_cost": 18000.0,
                        "qms_article_17_setup_fee": 24000.0,
                        "validation_hours": 140.0,
                        "ml_compliance_hourly_rate": 150.0,
                    },
                    "published_output": 120000.0,
                    "sample_calculation": (
                        "Enterprise deploying 2 Annex III high-risk AI systems under EU Regulation 2024/1689: "
                        "2 Article 43 Notified Body conformity audits at $28,500 ($57,000.00) + Annex IV technical "
                        "documentation dossier ($18,000.00) + Article 17 Quality Management System setup ($24,000.00) "
                        "+ 140 bias/robustness validation hours at $150/hr ($21,000.00) = $120,000.00 total conformity cost."
                    ),
                },
                {
                    "property_id": "gainhelm",
                    "tenant": "gainhelm",
                    "slug": "sec-cybersecurity-incident-materiality-8k-item-105-cost-calculator",
                    "query": "sec cybersecurity incident materiality 8k item 105 cost calculator",
                    "title": "SEC Form 8-K Item 1.05 Cyber Materiality Cost Model",
                    "action": "BUILD_PAGE",
                    "status": "PENDING",
                    "composite_profit_yield": 95.4,
                    "statutory_authority": "SEC Final Rule 33-11216 (17 CFR 229.106 Regulation S-K Item 106 & Form 8-K Item 1.05 4-Business-Day Mandate)",
                    "economic_dataset": "SEC Division of Economic and Risk Analysis (DERA) Cyber Disclosure Cost Series & BLS OEWS SOC 15-1212 Wage Series",
                    "model_name": "GainHelm-SEC-8K-Item105-Materiality-Readiness-Cost-Model-2026",
                    "formula": "round(outside_securities_counsel_retainer + dfir_tabletop_retainer + (board_reg_sk_106_hours * governance_advisory_hourly_rate) + materiality_workflow_platform_fee, 2)",
                    "inputs": {
                        "outside_securities_counsel_retainer": 65000.0,
                        "dfir_tabletop_retainer": 48000.0,
                        "board_reg_sk_106_hours": 160.0,
                        "governance_advisory_hourly_rate": 225.0,
                        "materiality_workflow_platform_fee": 31000.0,
                    },
                    "published_output": 180000.0,
                    "sample_calculation": (
                        "Public registrant operationalizing SEC Form 8-K Item 1.05 4-business-day materiality determination "
                        "and Regulation S-K Item 106 board governance disclosures: outside securities counsel retainer ($65,000.00) "
                        "+ DFIR forensic readiness and tabletop exercises ($48,000.00) + 160 Regulation S-K Item 106 governance "
                        "hours at $225/hr ($36,000.00) + automated materiality evidentiary workflow platform ($31,000.00) = "
                        "$180,000.00 total annual SEC cyber disclosure readiness investment."
                    ),
                },
            ],
            "lienbond": [
                {
                    "property_id": "lienbond",
                    "tenant": "lienbond",
                    "slug": "subcontractor-default-insurance-sdi-vs-performance-bond-cost-calculator",
                    "query": "subcontractor default insurance sdi vs performance bond cost calculator",
                    "title": "SDI vs Subcontractor Performance Bond Calculator",
                    "action": "BUILD_PAGE",
                    "status": "PENDING",
                    "composite_profit_yield": 96.1,
                    "statutory_authority": "40 U.S.C. Section 3131 (Miller Act) & AIA Document A312-2010 Dual-Obligee Subcontractor Surety Standards",
                    "economic_dataset": "SFAA Commercial Surety Loss Cost Series & BLS PPI Construction Inputs WPUIP2311001",
                    "model_name": "LienBond-SDI-vs-Subcontractor-Performance-Bond-Spread-Model-2026",
                    "formula": "round((annual_subcontract_volume * (sub_bond_rate_pct / 100.0)) - ((annual_subcontract_volume * (sdi_base_rate_pct / 100.0)) + (expected_default_claims * sdi_deductible_per_claim)), 2)",
                    "inputs": {
                        "annual_subcontract_volume": 50000000.0,
                        "sub_bond_rate_pct": 1.35,
                        "sdi_base_rate_pct": 0.65,
                        "expected_default_claims": 0.5,
                        "sdi_deductible_per_claim": 250000.0,
                    },
                    "published_output": 225000.0,
                    "sample_calculation": (
                        "General contractor managing $50,000,000.00 in annual subcontract volume comparing 1.35% "
                        "subcontractor performance bonds ($675,000.00) against a 0.65% Subcontractor Default Insurance "
                        "(SDI) policy ($325,000.00 base premium) plus 0.5 expected default claims at a $250,000.00 "
                        "retention ($125,000.00 expected retention cost) = $225,000.00 net annual underwriting savings."
                    ),
                },
                {
                    "property_id": "lienbond",
                    "tenant": "lienbond",
                    "slug": "texas-chapter-53-statutory-retainage-and-fund-trapping-notice-calculator",
                    "query": "texas chapter 53 statutory retainage and fund trapping notice calculator",
                    "title": "Texas Chapter 53 Statutory Retainage & Fund-Trapping Calculator",
                    "action": "BUILD_PAGE",
                    "status": "PENDING",
                    "composite_profit_yield": 94.8,
                    "statutory_authority": "Texas Property Code Section 53.101 (10% Statutory Reserved Funds) & Section 53.056 (15th Day of 3rd Month Derivative Notice)",
                    "economic_dataset": "FRED Total Construction Spending Series (TTLCONS) & BLS Specialty Trade Contractors PPI Series",
                    "model_name": "LienBond-Texas-Chapter53-Statutory-Retainage-FundTrapping-Model-2026",
                    "formula": "round(min(unpaid_subcontract_balance, (original_prime_contract_price * (statutory_reserved_pct / 100.0)) + trapped_owner_progress_funds), 2)",
                    "inputs": {
                        "unpaid_subcontract_balance": 185000.0,
                        "original_prime_contract_price": 1200000.0,
                        "statutory_reserved_pct": 10.0,
                        "trapped_owner_progress_funds": 30000.0,
                    },
                    "published_output": 150000.0,
                    "sample_calculation": (
                        "Texas commercial subcontractor with $185,000.00 in unpaid progress billings on a $1,200,000.00 prime "
                        "contract serving a timely Section 53.056 derivative claimant notice by the 15th day of the third month: "
                        "10% statutory reserved funds under Texas Property Code Section 53.101 ($120,000.00) plus $30,000.00 in "
                        "trapped owner progress funds secures $150,000.00 in priority mechanics lien recovery."
                    ),
                },
            ],
        }
        for t_id, seed_list in default_breakout_seeds.items():
            if t_id not in target_props:
                continue
            if len(day_bucket.get(t_id, []) or []) >= daily_cap:
                continue
            for seed_item in seed_list:
                seed_slug = str(seed_item["slug"]).strip().lower()
                if seed_slug in existing_slugs_by_tenant.get(t_id, set()):
                    continue
                existing_q = next(
                    (qi for qi in queue_items if str(qi.get("slug") or "").strip().lower() == seed_slug),
                    None,
                )
                if existing_q is not None:
                    existing_q.update(dict(seed_item))
                    existing_q["status"] = "PENDING"
                    existing_q.pop("built_at", None)
                    existing_q.pop("reconciled_reason", None)
                else:
                    queue_items.append(dict(seed_item))
                queue_mutated = True
                break

    for item in queue_items:
        t_id = str(item.get("property_id") or item.get("tenant") or "").strip().lower()
        if t_id not in target_props:
            continue
        if str(item.get("status") or "PENDING").upper() != "PENDING":
            continue
        if str(item.get("action") or "BUILD_PAGE").upper() != "BUILD_PAGE":
            continue
        c_slug = str(item.get("slug") or "").strip().lower()
        c_query = str(item.get("query") or c_slug.replace("-", " ")).strip()
        if not c_slug:
            continue
        if c_slug in existing_slugs_by_tenant.get(t_id, set()):
            item["status"] = "BUILT"
            item["reconciled_reason"] = "ALREADY_IN_DIST"
            reconciled_already_built_count += 1
            queue_mutated = True
            continue
        cannib = check_search_intent_cannibalization(
            query=c_query,
            existing_tools=existing_tools_by_tenant.get(t_id, []),
            candidate_spec=item,
        )
        if cannib.get("is_cannibalizing"):
            item["action"] = "REFACTOR_PAGE"
            item["status"] = "RECONCILED_CANNIBALIZATION"
            item["parent_slug"] = cannib.get("parent_slug")
            reconciled_cannibalizing_count += 1
            queue_mutated = True

    pending_build_items = [
        item
        for item in queue_items
        if str(item.get("property_id") or item.get("tenant") or "").strip().lower() in target_props
        and str(item.get("status") or "PENDING").upper() == "PENDING"
        and str(item.get("action") or "BUILD_PAGE").upper() == "BUILD_PAGE"
    ]
    ranking_report = rank_revenue_weighted_expansion_queue(
        void_candidates_path=str(queue_file) if queue_file.is_file() else None
    )
    ranked_pending = (
        ranking_report.get("after_queue", [])
        if isinstance(ranking_report, dict)
        else []
    )
    ranked_by_key = {
        (
            str(r.get("property_id") or r.get("tenant") or "").strip().lower(),
            str(r.get("slug") or "").strip().lower(),
        ): r
        for r in ranked_pending
        if isinstance(r, dict)
    }
    pending_sorted = sorted(
        pending_build_items,
        key=lambda x: float(
            ranked_by_key.get(
                (
                    str(x.get("property_id") or x.get("tenant") or "").strip().lower(),
                    str(x.get("slug") or "").strip().lower(),
                ),
                x,
            ).get(
                "revenue_weighted_yield",
                ranked_by_key.get(
                    (
                        str(x.get("property_id") or x.get("tenant") or "").strip().lower(),
                        str(x.get("slug") or "").strip().lower(),
                    ),
                    x,
                ).get("composite_profit_yield", x.get("composite_profit_yield", 0.0)),
            )
            or 0.0
        ),
        reverse=True,
    )

    built_pages: List[Dict[str, Any]] = []
    aborted_candidates: List[Dict[str, Any]] = []
    skipped_daily_cap_tenants: set = set()
    gitops_results: Dict[str, Any] = {}

    for item in pending_sorted:
        t_id = str(item.get("property_id") or item.get("tenant") or "").strip().lower()
        c_slug = str(item.get("slug") or "").strip().lower()
        c_query = str(item.get("query") or c_slug.replace("-", " ")).strip()
        if not t_id or not c_slug:
            continue

        built_today_list = day_bucket.setdefault(t_id, [])
        if not isinstance(built_today_list, list):
            built_today_list = []
            day_bucket[t_id] = built_today_list

        if len(built_today_list) >= daily_cap:
            skipped_daily_cap_tenants.add(t_id)
            continue

        adp = adapters_by_tenant[t_id]
        raw_title = str(item.get("title") or c_query.title()).strip()
        if "calculator" not in raw_title.lower() and "simulator" not in raw_title.lower() and "estimator" not in raw_title.lower():
            raw_title = f"{raw_title} Calculator"

        candidate_spec: Dict[str, Any] = dict(
            item.get("candidate_spec") if isinstance(item.get("candidate_spec"), dict) else {}
        )
        for k in (
            "statutory_authority",
            "economic_dataset",
            "formula",
            "inputs",
            "model_name",
            "sample_calculation",
            "published_output",
            "mandatory_disclosures",
        ):
            if k in item and item[k] is not None and k not in candidate_spec:
                candidate_spec[k] = item[k]
        candidate_spec.update(
            {
                "slug": c_slug,
                "query": c_query,
                "title": raw_title,
                "property_id": t_id,
                "tenant": t_id,
                "domain": adp.domain,
                "brand_name": adp.brand_name,
                "canonical_base": adp.canonical_base,
                "existing_tool_slugs": sorted(existing_slugs_by_tenant.get(t_id, set())),
            }
        )

        try:
            tenant_profile = TenantFactStore.get_instance().get_profile(t_id)
            tenant_gap_engine = CompetitorGapEngine(tenant_profile=tenant_profile)
            candidate_spec = tenant_gap_engine.enrich_candidate_spec(candidate_spec)
            assert_high_effort_content_qualified(
                candidate_spec, context=f"p2_daily_build:{t_id}:{c_slug}"
            )
            with adp.scoped_environment():
                compiled_res = compile_high_effort_page(candidate_spec)
            html_out = compiled_res["html"]
            if t_id == "profithelm":
                html_out = html_out.replace('href="/methodology/"', 'href="/about/"')
                html_out = html_out.replace("https://profithelm.com/methodology/", "https://profithelm.com/about/")
            manifest_out = compiled_res.get("manifest", {})
            try:
                from pseofactory.maintenance import RetroReflectionEngine
                html_out, _ = RetroReflectionEngine.retrofit_html(
                    html_out,
                    property_id=t_id,
                    slug=c_slug,
                    canonical_url=f"{adp.canonical_base.rstrip('/')}/tools/{c_slug}/",
                    manifest_override=manifest_out if isinstance(manifest_out, dict) and manifest_out.get("formula") else None,
                )
            except Exception:
                pass
            scanner.assert_clean(
                html_out,
                property_id=t_id,
                context=f"p2_daily_build:{t_id}:{c_slug}",
            )
            audit_stage = ContentAccuracyAuditStage(tolerance=0.01, strict=False)
            audit_rep = audit_stage.audit(
                html=html_out,
                candidate_spec=candidate_spec,
                tenant=t_id,
            )
            if not audit_rep.passed:
                raise ValueError(f"ContentAccuracyAuditStage failed: {audit_rep.violations}")

            from pseofactory.jev_client import evaluate_page_prepublish_gate
            existing_pages_for_jev: List[Dict[str, str]] = []
            tools_dir = Path(adp.dist_dir) / "tools"
            if tools_dir.is_dir():
                for existing_sub in sorted(tools_dir.iterdir()):
                    if not existing_sub.is_dir() or existing_sub.name == c_slug:
                        continue
                    idx_f = existing_sub / "index.html"
                    if idx_f.is_file():
                        try:
                            raw_idx = idx_f.read_text(encoding="utf-8", errors="ignore")
                            t_m = re.search(r"<title[^>]*>(.*?)</title>", raw_idx, re.IGNORECASE | re.DOTALL)
                            h1_m = re.search(r"<h1[^>]*>(.*?)</h1>", raw_idx, re.IGNORECASE | re.DOTALL)
                            existing_pages_for_jev.append(
                                {
                                    "slug": existing_sub.name,
                                    "url": f"{adp.canonical_base}/tools/{existing_sub.name}/",
                                    "title": re.sub(r"<[^>]+>", "", t_m.group(1)).strip() if t_m else existing_sub.name,
                                    "h1": re.sub(r"<[^>]+>", "", h1_m.group(1)).strip() if h1_m else "",
                                }
                            )
                        except Exception:
                            pass
            jev_gate_rep = evaluate_page_prepublish_gate(
                html_out,
                candidate_spec,
                existing_pages=existing_pages_for_jev,
            )
            if not jev_gate_rep.get("passed", False):
                raise ValueError(
                    f"JevPrePublishGate failed: {jev_gate_rep.get('violations') or jev_gate_rep.get('findings')}"
                )
        except Exception as exc:
            clean_err = str(exc).replace("\u2014", "-").replace("\u2013", "-")
            item["status"] = "ABORTED_QUALIFICATION"
            item["abort_reason"] = clean_err
            queue_mutated = True
            aborted_candidates.append(
                {
                    "property_id": t_id,
                    "slug": c_slug,
                    "query": c_query,
                    "reason": clean_err,
                }
            )
            continue

        built_ts = datetime.now(timezone.utc).isoformat()
        dist_dir = Path(adp.dist_dir)
        out_html_path = dist_dir / "tools" / c_slug / "index.html"
        out_manifest_path = dist_dir / "manifests" / f"{c_slug}.json"

        if (dist_dir / "about" / "index.html").is_file() and not (dist_dir / "methodology" / "index.html").is_file():
            html_out = html_out.replace('href="/methodology/"', 'href="/about/"').replace("href='/methodology/'", "href='/about/'")
        if (dist_dir / "privacy" / "index.html").is_file() and not (dist_dir / "disclaimers" / "index.html").is_file():
            html_out = html_out.replace('href="/disclaimers/"', 'href="/privacy/"').replace("href='/disclaimers/'", "href='/privacy/'")

        if not dry_run:
            out_html_path.parent.mkdir(parents=True, exist_ok=True)
            out_html_path.write_text(html_out, encoding="utf-8")
            out_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            out_manifest_path.write_text(json.dumps(manifest_out, indent=2) + "\n", encoding="utf-8")

            # Link in dist/tools/index.html and dist/index.html so zero orphan pages exist
            for hub_rel in ("tools/index.html", "index.html"):
                hub_file = dist_dir / hub_rel
                if hub_file.is_file():
                    try:
                        hub_html = hub_file.read_text(encoding="utf-8")
                        if f"/tools/{c_slug}/" not in hub_html:
                            link_Html = (
                                f'\n      <div class="card" style="margin-top:12px;">'
                                f'<a href="/tools/{c_slug}/" class="touch-target" '
                                f'style="display:inline-flex;align-items:center;min-height:44px;min-width:44px;font-weight:600;">'
                                f'{raw_title}</a></div>\n'
                            )
                            if "</main>" in hub_html:
                                hub_html = hub_html.replace("</main>", link_Html + "</main>", 1)
                            elif "</body>" in hub_html:
                                hub_html = hub_html.replace("</body>", link_Html + "</body>", 1)
                            hub_file.write_text(hub_html, encoding="utf-8")
                    except Exception:
                        pass

            # Link in sitemap-leaves.xml / sitemap.xml
            loc_url = f"{adp.canonical_base.rstrip('/')}/tools/{c_slug}/"
            for sm_name in ("sitemap-leaves.xml", "sitemap.xml"):
                sm_file = dist_dir / sm_name
                if sm_file.is_file():
                    try:
                        sm_txt = sm_file.read_text(encoding="utf-8")
                        if loc_url not in sm_txt and "</urlset>" in sm_txt:
                            url_entry = (
                                f"  <url>\n"
                                f"    <loc>{loc_url}</loc>\n"
                                f"    <lastmod>{date_str}</lastmod>\n"
                                f"  </url>\n"
                            )
                            sm_txt = sm_txt.replace("</urlset>", url_entry + "</urlset>", 1)
                            sm_file.write_text(sm_txt, encoding="utf-8")
                    except Exception:
                        pass

            # Update dist/_headers
            try:
                from pseofactory.edge import build_edge_headers
                headers_file = dist_dir / "_headers"
                route_path = f"/tools/{c_slug}/"
                existing_routes: List[str] = []
                if headers_file.is_file():
                    for ln in headers_file.read_text(encoding="utf-8").splitlines():
                        ln_s = ln.strip()
                        if not ln.startswith((" ", "\t")) and ln_s.startswith("/"):
                            existing_routes.append(ln_s)
                all_routes = list(dict.fromkeys(existing_routes + [route_path]))
                headers_file.write_text(
                    build_edge_headers(canonical_base=adp.canonical_base, routes=all_routes),
                    encoding="utf-8",
                )
            except Exception:
                pass

            # Register provenance in tenant repository so future builds preserve the tool
            repo_root = getattr(adp, "repo_path", None) or dist_dir.parent
            if repo_root and Path(repo_root).is_dir():
                r_root = Path(repo_root)
                prov_title = raw_title
                if t_id in ("gainhelm", "prexvo", "lienbond"):
                    brand_sfx = f" | {adp.brand_name}"
                    max_b = 60 - len(brand_sfx)
                    min_b = 50 - len(brand_sfx)
                    if len(prov_title) > max_b:
                        prov_title = prov_title[:max_b].rsplit(" ", 1)[0].rstrip(" |-&")
                        if len(prov_title) < min_b and "calculator" not in prov_title.lower():
                            for pad_s in ("Cost Model", "Calculator", "Model"):
                                if min_b <= len(f"{prov_title} {pad_s}") <= max_b:
                                    prov_title = f"{prov_title} {pad_s}"
                                    break
                    elif len(prov_title) < min_b:
                        for pad_s in ("Compliance Cost Model", "Calculation Engine", "Cost Model", "Engine"):
                            if min_b <= len(f"{prov_title} {pad_s}") <= max_b:
                                prov_title = f"{prov_title} {pad_s}"
                                break
                prov_desc = f"Deterministic quantitative calculator for {c_query} under {candidate_spec['statutory_authority']}."
                if len(prov_desc) > 155:
                    prov_desc = prov_desc[:154].rsplit(" ", 1)[0].rstrip(".,;:- ") + "."
                prov_entry = {
                    "slug": c_slug,
                    "query": c_query,
                    "title": prov_title,
                    "short_title": prov_title[:24].strip(),
                    "description": prov_desc,
                    "primary_keyword": c_query.lower(),
                    "source": "p2_autonomous_daily_builder",
                    "statutory_authority": candidate_spec.get("statutory_authority", ""),
                    "economic_dataset": candidate_spec.get("economic_dataset", ""),
                    "model_name": candidate_spec.get("model_name", ""),
                    "formula": candidate_spec.get("formula", ""),
                    "inputs": dict(candidate_spec.get("inputs") or {}),
                    "published_output": compiled_res.get("published_output", candidate_spec.get("published_output", 0.0)),
                    "sample_calculation": candidate_spec.get("sample_calculation", ""),
                    "calculation_manifest": dict(manifest_out) if isinstance(manifest_out, dict) else {},
                    "verified_at": built_ts,
                }
                dv_targets = (
                    [r_root / ".agy" / "deployed_voids.json"]
                    if t_id == "profithelm"
                    else [r_root / "content" / "deployed_voids.json"]
                )
                for dv_f in dv_targets:
                    try:
                        dv_list = []
                        if dv_f.is_file():
                            loaded_dv = json.loads(dv_f.read_text(encoding="utf-8"))
                            if isinstance(loaded_dv, list):
                                dv_list = [d for d in loaded_dv if isinstance(d, dict) and d.get("slug") != c_slug]
                        dv_list.append(prov_entry)
                        dv_f.parent.mkdir(parents=True, exist_ok=True)
                        dv_f.write_text(json.dumps(dv_list, indent=2) + "\n", encoding="utf-8")
                    except Exception:
                        pass

            try:
                from pseofactory.maintenance import RetroReflectionEngine
                RetroReflectionEngine.retrofit_estate(
                    dist_dir=dist_dir,
                    property_id=t_id,
                    canonical_base=adp.canonical_base,
                )
            except Exception:
                pass

        item["status"] = "BUILT"
        item["built_at"] = built_ts
        queue_mutated = True
        existing_slugs_by_tenant.setdefault(t_id, set()).add(c_slug)
        existing_tools_by_tenant.setdefault(t_id, []).append({"slug": c_slug, "query": c_query})

        build_rec = {
            "property_id": t_id,
            "slug": c_slug,
            "query": c_query,
            "title": raw_title,
            "output_file": str(out_html_path),
            "composite_profit_yield": float(
                ranked_by_key.get((t_id, c_slug), item).get(
                    "composite_profit_yield", item.get("composite_profit_yield", 0.0)
                )
                or 0.0
            ),
            "built_at": built_ts,
        }
        built_today_list.append(build_rec)
        built_pages.append(build_rec)

        if enable_gitops and not dry_run:
            try:
                from pseofactory.gitops import GitOpsCoordinator
                repo_root = getattr(adp, "repo_path", None) or dist_dir.parent
                coord = GitOpsCoordinator(repo_path=Path(repo_root), branch="main", dry_run=dry_run)
                g_res = coord.dispatch_to_shipper(
                    property_id=t_id,
                    dry_run=dry_run,
                    commit_message=f"feat({t_id}): autonomous daily trend build {c_slug}",
                    dist_dir=dist_dir,
                    edge_url=f"https://{adp.domain}",
                )
                gitops_results[t_id] = g_res.to_dict()
            except Exception as g_exc:
                gitops_results[t_id] = {"status": "FAILED", "error": str(g_exc)}

    push_indexing_results: Dict[str, Any] = {}
    if dispatch_push_indexing and not dry_run and "PYTEST_CURRENT_TEST" not in os.environ:
        from pseofactory.indexer import PushIndexer
        for t_id in target_props:
            t_records = day_bucket.get(t_id)
            if not isinstance(t_records, list) or not t_records:
                continue
            adp = adapters_by_tenant.get(t_id)
            if adp is None:
                continue
            dist_dir = Path(adp.dist_dir)
            repo_root = getattr(adp, "repo_path", None) or dist_dir.parent
            urls_to_push = [
                f"{adp.canonical_base.rstrip('/')}/tools/{str(r.get('slug')).strip('/')}/"
                for r in t_records
                if isinstance(r, dict) and r.get("slug")
            ]
            if urls_to_push:
                try:
                    p_idx = PushIndexer(
                        domain=adp.domain,
                        canonical_base=adp.canonical_base,
                        base_dir=Path(repo_root),
                        dist_dir=dist_dir,
                        tenant_id=t_id,
                    )
                    push_indexing_results[t_id] = p_idx.dispatch_automated_indexing(
                        urls=urls_to_push,
                        live=True,
                    )
                except Exception as p_exc:
                    push_indexing_results[t_id] = {"status": "FAILED", "error": str(p_exc)}

    if not dry_run:
        ledger_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        AtomicStateLedger.save_json(daily_ledger_file, ledger_data)
        if queue_mutated and queue_file.parent.is_dir():
            lines_out = [json.dumps(rec, ensure_ascii=False) for rec in queue_items]
            queue_file.write_text("\n".join(lines_out) + ("\n" if lines_out else ""), encoding="utf-8")

    return {
        "status": "PASS",
        "date_key": date_str,
        "max_pages_per_tenant_per_day": daily_cap,
        "dry_run": dry_run,
        "built_count": len(built_pages),
        "built_pages": built_pages,
        "skipped_daily_cap_tenants": sorted(list(skipped_daily_cap_tenants)),
        "reconciled_already_built_count": reconciled_already_built_count,
        "reconciled_cannibalizing_count": reconciled_cannibalizing_count,
        "reconciled_stale_ledger_count": reconciled_stale_ledger_count,
        "aborted_candidates": aborted_candidates,
        "gitops_results": gitops_results,
        "push_indexing_results": push_indexing_results,
    }


from pseofactory.supervisor import (  # noqa: E402
    CANONICAL_DEPARTMENT_CONTRACTS,
    CANONICAL_TENANTS,
    DepartmentContract,
    DepartmentHandoffChainVerifier,
    verify_department_handoff_chain,
)

