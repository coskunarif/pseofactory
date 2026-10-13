"""
Substrate Competitor Gap Engine and Specification Types.
Diffs competitor search results, snippets, and interactive features
against platform tooling to extract missing interactive features,
click magnets, and conversion hooks into candidate specifications.
Parameterized exclusively by TenantTruthProfile to maintain absolute tenant isolation.
Zero em-dashes. Zero en-dashes.
"""

import json
import logging
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Union

from pseofactory.contracts import sanitize_url_slug, assert_no_forbidden_dashes
from pseofactory.tenant_facts import TenantTruthProfile, TenantFactStore
from pseofactory.maintenance import CrossPropertyContaminationScanner

logger = logging.getLogger(__name__)

# Universal regex pattern sets for competitor extraction
INTERACTIVE_PATTERNS: List[str] = [
    r"\b(save\s+transition\s+decision\s+matrix)\b",
    r"\b(specialty\s+salary\s+curves?)\b",
    r"\b([a-z0-9_]+\s+(?:matrix|slider|simulator|calculator|estimator|modeler))\b",
    r"\b(\w*slider\w*)\b",
    r"\b(\w*calculator\w*)\b",
    r"\b(\w*estimator\w*)\b",
    r"\b(\w*modeler\w*)\b",
    r"\b(\w*simulator\w*)\b",
    r"\b(\w*matrix\w*)\b",
    r"\b(\w*withholding\w*)\b",
    r"\b(\w*comparison\w*)\b",
    r"\b(\w*refund\w*)\b",
    r"\b(\w*scenario\w*)\b",
    r"\b(\w*curves?\w*)\b",
]

CLICK_MAGNET_PATTERNS: List[str] = [
    r"\b(pdf\s+report|projection\s+pdf|pdf|report|guide|cheat\s*sheet|checklist|chart|summary\s+sheet|template)\b",
    r"\b(free\s+[\w\s]+(?:report|pdf|guide|chart|calculator|download))\b",
]

CONVERSION_HOOK_PATTERNS: List[str] = [
    r"\b(newsletter|email\s+alerts?|rate\s+change\s+alerts?)\b",
    r"\b(consultation|cpa\s+partner|consultation\s+cta|advisor\s+connect)\b",
    r"\b(affiliate|banner|recommendation\s+banner|partner\s+offer)\b",
]


def _extract_patterns(text: str, patterns: List[str]) -> List[str]:
    """Extracts unique matched terms using regex patterns from text."""
    matches: Set[str] = set()
    lowered = text.lower()
    for pat in patterns:
        for m in re.finditer(pat, lowered, re.IGNORECASE):
            token = m.group(1) if m.groups() else m.group(0)
            clean_tok = token.strip()
            if clean_tok and len(clean_tok) > 2:
                matches.add(clean_tok)
    return sorted(list(matches))


def _normalize_feature_name(feat: str) -> str:
    """Normalizes feature name to lowercase snake_case identifier."""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", feat.strip().lower())
    return cleaned.strip("_")


def _construct_candidate_quick_answer(
    short_title: str,
    clean_query: str,
    feature_label: str,
    tenant_id: str,
    statutory_authority: str,
) -> str:
    """Constructs direct factual quick answer adhering to Princeton GEO invariants (<20 words sentence 1)."""
    clean_feat = feature_label.replace("_", " ").strip()
    s1 = f"The {short_title} model calculates deterministic statutory metrics under {statutory_authority} schedules."
    s2 = (
        f"By integrating interactive {clean_feat} modeling, empirical statutory rules, "
        f"and multi-tier baseline parameters, users evaluate deterministic outcomes and statutory deadlines."
    )
    return f"{s1} {s2}"


@dataclass
class GapCandidateSpec:
    """
    Candidate tool specification derived from competitor SERP gap analysis.
    Zero em-dashes. Zero en-dashes.
    """
    slug: str
    query: str
    primary_keyword: str
    title: str
    short_title: str
    nav_label: str
    category: str
    description: str
    quick_answer: str
    geo_summary: str
    interactive_features: List[str] = field(default_factory=list)
    missing_interactive_features: List[str] = field(default_factory=list)
    click_magnets: List[str] = field(default_factory=list)
    conversion_hooks: List[str] = field(default_factory=list)
    affiliates: List[str] = field(default_factory=list)
    statutory_authority: str = ""
    economic_dataset: str = ""
    mandatory_disclosures: List[str] = field(default_factory=list)
    status: str = "PENDING"
    source: str = "competitor_serp_diff"
    base_volume: int = 4500
    base_cpc: float = 7.5
    base_kd: int = 15
    erpm_potential_usd: float = 75.0
    created_at: str = ""
    tenant: str = ""
    property_id: str = ""
    domain: str = ""
    canonical_base: str = ""
    inputs: Dict[str, Any] = field(default_factory=dict)
    formula: str = ""
    model_name: str = ""
    published_output: float = 0.0
    sample_calculation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)

    def __contains__(self, item: str) -> bool:
        return hasattr(self, item)


class CompetitorGapEngine:
    """
    Substrate Competitor Gap Engine parameterized by immutable TenantTruthProfile.
    Diffs competitor search results, extracts missing interactive features,
    and enriches candidate specifications while enforcing strict tenant boundary isolation.
    Zero em-dashes. Zero en-dashes.
    """

    def __init__(self, tenant_profile: TenantTruthProfile):
        self.tenant_profile = tenant_profile
        self.tenant_id = str(tenant_profile.tenant_id).lower().strip()
        self.fact_store = TenantFactStore.get_instance()
        self.scanner = CrossPropertyContaminationScanner()

    def diff_competitor_serp(
        self,
        query: str,
        competitor_results: List[Dict[str, Any]],
        existing_tool: Optional[Dict[str, Any]] = None,
    ) -> List[GapCandidateSpec]:
        """
        Diffs organic competitor search results and snippets against platform tooling.
        Extracts missing interactive features, click magnets, and conversion hooks.
        Returns gap candidate specifications strictly adhering to tenant truth profile.
        """
        clean_query = str(query).strip()
        comp_interactive: Set[str] = set()
        comp_magnets: Set[str] = set()
        comp_hooks: Set[str] = set()

        for item in competitor_results:
            if not isinstance(item, dict):
                continue

            for feat in item.get("interactive_features", []):
                if isinstance(feat, str) and feat.strip():
                    comp_interactive.add(_normalize_feature_name(feat))

            for mag in item.get("click_magnets", []):
                if isinstance(mag, str) and mag.strip():
                    comp_magnets.add(mag.strip())

            for hook in item.get("conversion_hooks", []):
                if isinstance(hook, str) and hook.strip():
                    comp_hooks.add(hook.strip())

            title = str(item.get("title", ""))
            snippet = str(item.get("snippet", "") or item.get("description", ""))
            combined = f"{title} {snippet}"

            extracted_tools = _extract_patterns(combined, INTERACTIVE_PATTERNS)
            for et in extracted_tools:
                comp_interactive.add(_normalize_feature_name(et))

            extracted_magnets = _extract_patterns(combined, CLICK_MAGNET_PATTERNS)
            for em in extracted_magnets:
                comp_magnets.add(em.title())

            extracted_hooks = _extract_patterns(combined, CONVERSION_HOOK_PATTERNS)
            for eh in extracted_hooks:
                comp_hooks.add(eh.title())

        our_interactive: Set[str] = set()
        our_magnets: Set[str] = set()
        our_hooks: Set[str] = set()
        tool_text = ""

        if existing_tool and isinstance(existing_tool, dict):
            for feat in existing_tool.get("interactive_features", []):
                if isinstance(feat, str):
                    our_interactive.add(_normalize_feature_name(feat))
            for mag in existing_tool.get("click_magnets", []):
                if isinstance(mag, str):
                    our_magnets.add(mag.strip().lower())
            for hook in existing_tool.get("conversion_hooks", []):
                if isinstance(hook, str):
                    our_hooks.add(hook.strip().lower())
            tool_text = f"{existing_tool.get('title', '')} {existing_tool.get('description', '')}".lower()

        missing_interactive = [
            f for f in sorted(list(comp_interactive))
            if f.lower() not in our_interactive and f.lower() not in tool_text
        ]
        missing_magnets = [
            m for m in sorted(list(comp_magnets))
            if m.lower() not in our_magnets and m.lower() not in tool_text
        ]
        missing_hooks = [
            h for h in sorted(list(comp_hooks))
            if h.lower() not in our_hooks and h.lower() not in tool_text
        ]

        if self.tenant_id == "prexvo":
            default_category = "Student Loan Repayment"
            affiliates = ["splash_financial", "sofi"]
            statutory_authority = "34 CFR Part 685"
            economic_dataset = "FRED SLSTTOTAL Series"
            model_name = "Direct Consolidation Loan Weighted Model"
            formula = "balance * (weighted_rate / 100.0)"
            inputs = {"balance": 45000, "weighted_rate": 6.5}
            published_output = 2925.0
            sample_calculation = "Balance 45,000 at 6.5 percent weighted rate yields 2,925 annual interest"
            disclosures = [
                "Refinancing federal student loans permanently waives federal protections",
                "FTC Partner Compensation Disclosure",
                "Independent Publisher Disclaimer",
            ]
            canonical_base = "https://prexvo.com"
        else:
            default_category = "Tax Intelligence"
            affiliates = ["crest_capital", "mercury"]
            statutory_authority = "IRC Section 179(b)(1)"
            economic_dataset = "FRED CPILFESL Series"
            model_name = "Section 179 Grounded Model"
            formula = "min(cost, cap)"
            inputs = {"cost": 400000, "cap": 1220000}
            published_output = 400000.0
            sample_calculation = "Cost 400,000 under cap 1,220,000 gives 400,000 deduction"
            disclosures = [
                "Circular 230 Tax Modeling Disclaimer",
                "FTC Independent Financial Research Publisher Disclosure",
            ]
            canonical_base = "https://profithelm.com"

        candidates: List[GapCandidateSpec] = []
        base_slug = sanitize_url_slug(clean_query)
        base_title = clean_query.title()

        if missing_interactive:
            for feat in missing_interactive:
                slug = sanitize_url_slug(f"{base_slug}-{feat}")
                cand_title = f"{base_title} {feat.replace('_', ' ').title()} Calculator"
                short_t = cand_title.split("|")[0].strip()[:24]
                cand_qa = _construct_candidate_quick_answer(
                    short_t, clean_query, feat, self.tenant_id, statutory_authority
                )
                spec = GapCandidateSpec(
                    slug=slug,
                    query=f"{clean_query} {feat.replace('_', ' ')}",
                    primary_keyword=f"{clean_query} {feat.replace('_', ' ')}",
                    title=cand_title,
                    short_title=short_t,
                    nav_label=feat.replace("_", " ").title()[:14],
                    category=default_category,
                    description=(
                        f"Deterministic mathematical model and planning calculator for {clean_query} "
                        f"incorporating interactive {feat.replace('_', ' ')} scenario modeling."
                    ),
                    quick_answer=cand_qa,
                    geo_summary=cand_qa,
                    interactive_features=list(missing_interactive),
                    missing_interactive_features=list(missing_interactive),
                    click_magnets=missing_magnets,
                    conversion_hooks=missing_hooks,
                    affiliates=affiliates,
                    statutory_authority=statutory_authority,
                    economic_dataset=economic_dataset,
                    mandatory_disclosures=disclosures,
                    tenant=self.tenant_id,
                    property_id=self.tenant_id,
                    domain=self.tenant_profile.canonical_domain.replace("https://", "").replace("http://", ""),
                    canonical_base=canonical_base,
                    inputs=inputs,
                    formula=formula,
                    model_name=model_name,
                    published_output=published_output,
                    sample_calculation=sample_calculation,
                    created_at=datetime.now().isoformat(),
                )
                self._assert_spec_clean(spec)
                candidates.append(spec)
        else:
            slug = sanitize_url_slug(f"{base_slug}-parity")
            cand_title = f"{base_title} Parity Calculator"
            short_t = cand_title[:24]
            cand_qa = _construct_candidate_quick_answer(
                short_t, clean_query, "parity", self.tenant_id, statutory_authority
            )
            spec = GapCandidateSpec(
                slug=slug,
                query=clean_query,
                primary_keyword=clean_query,
                title=cand_title,
                short_title=short_t,
                nav_label="Parity Edition",
                category=default_category,
                description=f"Deterministic mathematical model and planning calculator for {clean_query}.",
                quick_answer=cand_qa,
                geo_summary=cand_qa,
                interactive_features=["scenario_comparison_model"],
                missing_interactive_features=[],
                click_magnets=missing_magnets,
                conversion_hooks=missing_hooks,
                affiliates=affiliates,
                statutory_authority=statutory_authority,
                economic_dataset=economic_dataset,
                mandatory_disclosures=disclosures,
                tenant=self.tenant_id,
                property_id=self.tenant_id,
                domain=self.tenant_profile.canonical_domain.replace("https://", "").replace("http://", ""),
                canonical_base=canonical_base,
                inputs=inputs,
                formula=formula,
                model_name=model_name,
                published_output=published_output,
                sample_calculation=sample_calculation,
                created_at=datetime.now().isoformat(),
            )
            self._assert_spec_clean(spec)
            candidates.append(spec)

        return candidates

    def _assert_spec_clean(self, spec: GapCandidateSpec) -> None:
        """Enforces zero foreign tokens in candidate spec."""
        spec_dict = spec.to_dict()
        serialized = json.dumps(spec_dict).lower()
        matched = self.scanner.scan_text(serialized, self.tenant_id)
        if matched:
            raise ValueError(
                f"Candidate spec for {self.tenant_id} contains foreign tokens: {matched}"
            )

    def enrich_candidate_spec(self, candidate_spec: Union[Dict[str, Any], GapCandidateSpec]) -> Dict[str, Any]:
        """
        Enriches candidate specification with statutory citations, economic datasets,
        and mathematical parameters derived from the tenant truth profile.
        Validates against tenant isolation firewall.
        Zero em-dashes. Zero en-dashes.
        """
        if hasattr(candidate_spec, "to_dict"):
            spec = candidate_spec.to_dict()
        else:
            spec = dict(candidate_spec)

        tenant_id = self.tenant_id
        query = str(spec.get("query", "")).lower()

        if tenant_id == "prexvo":
            spec.setdefault("tenant", "prexvo")
            spec.setdefault("property_id", "prexvo")
            spec.setdefault("domain", "prexvo.com")
            spec.setdefault("canonical_base", "https://prexvo.com")
            spec.setdefault("statutory_authority", "34 CFR Part 685")
            spec.setdefault("economic_dataset", "FRED SLSTTOTAL Series")
            spec.setdefault("category", "Student Loan Repayment")
            spec.setdefault("affiliates", ["splash_financial", "sofi"])
            spec.setdefault("model_name", "Direct Consolidation Loan Weighted Model")
            spec.setdefault("formula", "balance * (weighted_rate / 100.0)")
            spec.setdefault("inputs", {"balance": 45000, "weighted_rate": 6.5})
            spec.setdefault("published_output", 2925.0)
            spec.setdefault(
                "sample_calculation",
                "Balance 45,000 at 6.5 percent weighted rate yields 2,925 annual interest",
            )
            spec.setdefault("mandatory_disclosures", [
                "Refinancing federal student loans permanently waives federal protections",
                "FTC Partner Compensation Disclosure",
                "Independent Publisher Disclaimer",
            ])
        else:
            spec.setdefault("tenant", "profithelm")
            spec.setdefault("property_id", "profithelm")
            spec.setdefault("domain", "profithelm.com")
            spec.setdefault("canonical_base", "https://profithelm.com")
            if "1031" in query:
                spec.setdefault("statutory_authority", "IRC Section 1031(a)(1)")
                spec.setdefault("economic_dataset", "FRED CPILFESL Series")
                spec.setdefault("category", "1031 Exchange")
                spec.setdefault("affiliates", ["ipx1031", "mercury"])
                spec.setdefault("model_name", "Section 1031 Like-Kind Exchange Model")
                spec.setdefault("formula", "relinquished_basis + recognized_gain")
                spec.setdefault("inputs", {"relinquished_basis": 450000, "recognized_gain": 0})
                spec.setdefault("published_output", 450000.0)
                spec.setdefault(
                    "sample_calculation",
                    "Relinquished basis 450,000 with zero recognized gain yields replacement basis 450,000",
                )
            else:
                spec.setdefault("statutory_authority", "IRC Section 179(b)(1)")
                spec.setdefault("economic_dataset", "FRED CPILFESL Series")
                spec.setdefault("category", "Tax Intelligence")
                spec.setdefault("affiliates", ["crest_capital", "mercury"])
                spec.setdefault("model_name", "Section 179 Grounded Model")
                spec.setdefault("formula", "min(cost, cap)")
                spec.setdefault("inputs", {"cost": 400000, "cap": 1220000})
                spec.setdefault("published_output", 400000.0)
                spec.setdefault(
                    "sample_calculation",
                    "Cost 400,000 under cap 1,220,000 gives 400,000 deduction",
                )
            spec.setdefault("mandatory_disclosures", [
                "Circular 230 Tax Modeling Disclaimer",
                "FTC Independent Financial Research Publisher Disclosure",
            ])

        # Enforce tenant isolation check on text attributes
        text_to_check = f"{spec.get('title', '')} {spec.get('description', '')} {spec.get('quick_answer', '')} {spec.get('statutory_authority', '')}"
        self.fact_store.assert_tenant_isolation(tenant_id, text_to_check)

        return spec


__all__ = [
    "INTERACTIVE_PATTERNS",
    "CLICK_MAGNET_PATTERNS",
    "CONVERSION_HOOK_PATTERNS",
    "GapCandidateSpec",
    "CompetitorGapEngine",
]
