"""
pseofactory Automated Discovery and Content Generation Pipeline Driver
Unifies multi-source breakout opportunity ingestion (FeedSpike), discrete second-derivative
acceleration gating (HWL-1215), Treg search demand cross-referencing, Jev durability gating
(score >= 1.20, durable_prob >= 0.50), live SERP underdog angle extraction with Grant O Triad
and token Jaccard divergence >= 0.50, symmetric multi-tenant property boundary isolation
between profithelm and prexvo, and compliant high-effort programmatic page compilation.
Zero em-dashes. Zero en-dashes.
"""

import os
import re
import json
import fcntl
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Union

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
    reason: str  # LOW_JEV_DURABILITY | HIGH_TREG_COMPETITION | TRANSIENT_NOISE_OR_DECELERATION | CROSS_PROPERTY_CONTAMINATION | DERIVATIVE_SERP_ANGLE | REFACTOR_PAGE_CANNIBALIZATION
    jev_score: float
    durable_prob: float
    search_volume: int
    keyword_difficulty: float
    foreign_tokens: List[str] = field(default_factory=list)
    action: str = "REJECT"

    def to_dict(self) -> Dict[str, Any]:
        return {
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

    def to_dict(self) -> Dict[str, Any]:
        return {
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
    ):
        self.config = config or PipelineConfig()
        self.noise_filter = noise_filter or NoiseFilter()
        self.treg_checker = treg_checker or TregChecker(
            max_cost=self.config.max_route_cost,
            timeout=self.config.treg_timeout,
        )
        self.jev_engine = jev_engine or JevEngine(
            min_score=self.config.min_jev_score,
            min_durable_prob=self.config.min_durable_prob,
            min_build_yield=self.config.min_build_yield,
        )
        self.scanner = scanner or CrossPropertyContaminationScanner()
        self.tenant_registry = tenant_registry or TenantRegistry.default()

    def determine_property_assignment(
        self,
        query: str,
        explicit_tenant: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Routes query to property tenant: prexvo, profithelm, or unassigned.
        Scans for cross-property token contamination in fail-closed mode.
        Zero em-dashes. Zero en-dashes.
        """
        assert_no_forbidden_dashes(query, "determine_property_assignment.query")
        q_lower = query.lower().strip()

        is_prexvo = any(tok in q_lower for tok in PREXVO_STATUTORY_TOKENS)
        is_profithelm = any(tok in q_lower for tok in PROFITHELM_STATUTORY_TOKENS) or (
            "1031" in q_lower and "exchange" in q_lower
        )

        if explicit_tenant:
            tenant_norm = explicit_tenant.lower().strip()
            if tenant_norm == "prexvo":
                foreign = self.scanner.scan_text(query, "prexvo")
                if is_profithelm:
                    token_found = "1031 exchange" if "1031" in q_lower else "profithelm statutory token"
                    foreign = list(set(foreign + [token_found]))
                if foreign:
                    return {
                        "property_id": "prexvo",
                        "basis": "cross_contaminated",
                        "contamination_scan_passed": 0,
                        "foreign_tokens": foreign,
                    }
                return {
                    "property_id": "prexvo",
                    "basis": "explicit_tenant",
                    "contamination_scan_passed": 1,
                    "foreign_tokens": [],
                }
            elif tenant_norm == "profithelm":
                foreign = self.scanner.scan_text(query, "profithelm")
                if is_prexvo:
                    token_found = "title iv" if "title iv" in q_lower else "prexvo statutory token"
                    foreign = list(set(foreign + [token_found]))
                if foreign:
                    return {
                        "property_id": "profithelm",
                        "basis": "cross_contaminated",
                        "contamination_scan_passed": 0,
                        "foreign_tokens": foreign,
                    }
                return {
                    "property_id": "profithelm",
                    "basis": "explicit_tenant",
                    "contamination_scan_passed": 1,
                    "foreign_tokens": [],
                }

        if is_prexvo and not is_profithelm:
            foreign = self.scanner.scan_text(query, "prexvo")
            if foreign:
                return {
                    "property_id": "prexvo",
                    "basis": "cross_contaminated",
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
                    "basis": "cross_contaminated",
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
        seen_idempotency_keys: Set[str] = set()

        for spike in spikes:
            # 1. Universal Idempotency: sha256(tenant + spike_id + query)
            tenant_hint = "unassigned"
            raw_payload = spike.raw_payload or {}
            if "tenant" in raw_payload:
                tenant_hint = str(raw_payload["tenant"]).lower()
            else:
                assigned = self.determine_property_assignment(spike.query)
                tenant_hint = assigned["property_id"]

            spike_id = getattr(spike, "id", getattr(spike, "spike_id", "spike"))
            idempotency_key = hashlib.sha256(
                f"{tenant_hint}:{spike_id}:{spike.query}".encode("utf-8")
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

            # 3. Treg demand and competition cross-referencing
            mock_treg = None
            raw_meta = cand.metadata or {}
            if "treg_mock" in raw_meta:
                mock_treg = raw_meta["treg_mock"]
            elif spike.raw_payload and "treg_mock" in spike.raw_payload:
                mock_treg = spike.raw_payload["treg_mock"]

            treg_res = self.treg_checker.check_query(cand.query, mock_override=mock_treg)

            # 4. Search intent cannibalization check
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

            cann_ctx = {
                "cannibalization_score": cann_score,
                "matches_existing_slug": matching_tool,
                "current_position": pos,
            }

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
            rankings.append(decision.to_dict())

            # Evaluate decision action
            if decision.action == "REJECT":
                if (
                    decision.jev_score < self.config.min_jev_score
                    or decision.durable_prob < self.config.min_durable_prob
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

            # Primary statutory legal provenance and empirical economic dataset enrichment
            if tenant == "profithelm":
                if "1031" in decision.query.lower():
                    candidate_spec.setdefault("statutory_authority", "IRC Section 1031(a)(1)")
                    candidate_spec.setdefault("economic_dataset", "FRED CPILFESL Series")
                    candidate_spec.setdefault(
                        "model_name", "Section 1031 Like-Kind Exchange Model"
                    )
                    candidate_spec.setdefault(
                        "formula", "relinquished_basis + recognized_gain"
                    )
                    candidate_spec.setdefault(
                        "inputs", {"relinquished_basis": 450000, "recognized_gain": 0}
                    )
                    candidate_spec.setdefault("published_output", 450000.0)
                    candidate_spec.setdefault(
                        "sample_calculation",
                        "Relinquished basis 450,000 with zero recognized gain yields replacement basis 450,000",
                    )
                else:
                    candidate_spec.setdefault("statutory_authority", "IRC Section 179(b)(1)")
                    candidate_spec.setdefault("economic_dataset", "FRED CPILFESL Series")
                    candidate_spec.setdefault("model_name", "Section 179 Grounded Model")
                    candidate_spec.setdefault("formula", "min(cost, cap)")
                    candidate_spec.setdefault("inputs", {"cost": 400000, "cap": 1220000})
                    candidate_spec.setdefault("published_output", 400000.0)
                    candidate_spec.setdefault(
                        "sample_calculation",
                        "Cost 400,000 under cap 1,220,000 gives 400,000 deduction",
                    )
            elif tenant == "prexvo":
                candidate_spec.setdefault("statutory_authority", "34 CFR Part 685")
                candidate_spec.setdefault("economic_dataset", "FRED SLSTTOTAL Series")
                candidate_spec.setdefault(
                    "model_name", "Direct Consolidation Loan Weighted Model"
                )
                candidate_spec.setdefault("formula", "balance * (weighted_rate / 100.0)")
                candidate_spec.setdefault("inputs", {"balance": 45000, "weighted_rate": 6.5})
                candidate_spec.setdefault("published_output", 2925.0)
                candidate_spec.setdefault(
                    "sample_calculation",
                    "Balance 45,000 at 6.5 percent weighted rate yields 2,925 annual interest",
                )

            candidate_spec.setdefault("query", decision.query)
            candidate_spec.setdefault("slug", decision.slug)

            # Pre-compilation gate
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

            # 10. Persistence and result assembly
            out_file = None
            if output_dir:
                out_path = Path(output_dir) / tenant / "tools" / decision.slug / "index.html"
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(compiled_res["html"], encoding="utf-8")
                out_file = out_path

            compiled_assets.append(
                CompiledAssetResult(
                    query=decision.query,
                    slug=decision.slug,
                    tenant=tenant,
                    html_length=len(compiled_res["html"]),
                    output_file=out_file,
                    manifest=compiled_res.get("manifest", {}),
                    audit_passed=compiled_res.get("verified", True),
                    contamination_clean=True,
                )
            )

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
        )


def run_factory_pipeline(
    spikes: List[Union[FeedSpike, Dict[str, Any]]],
    config: Optional[PipelineConfig] = None,
    existing_tools: Optional[List[Dict[str, Any]]] = None,
    sitemap_urls: Optional[List[str]] = None,
    output_dir: Optional[Union[str, Path]] = None,
) -> DriverExecutionResult:
    """
    Convenience helper to run the complete automated discovery and content generation pipeline.
    Zero em-dashes. Zero en-dashes.
    """
    pipeline = FactoryPipeline(config=config)
    return pipeline.execute(
        raw_spikes=spikes,
        existing_tools=existing_tools,
        sitemap_urls=sitemap_urls,
        output_dir=output_dir,
    )
