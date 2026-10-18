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
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from pseofactory.affiliates import (
    PREXVO_DISCLOSURES,
    PROFITHELM_DISCLOSURES,
    is_restricted_public_service_slug,
    qualify_monetization_opportunity,
    verify_partner_domain_alignment,
)
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

        base_slug = sanitize_url_slug(clean_query)
        base_title = clean_query.title()

        if self.tenant_id == "prexvo":
            default_category = "Student Loan Repayment"
            restricted_ps = is_restricted_public_service_slug(base_slug, clean_query)
            affiliates = [] if restricted_ps else ["splash_financial", "sofi"]
            statutory_authority = "34 CFR Part 685"
            economic_dataset = "FRED SLSTTOTAL Series"
            model_name = "Direct Consolidation Loan Weighted Model"
            formula = "balance * (weighted_rate / 100.0)"
            inputs = {"balance": 45000, "weighted_rate": 6.5}
            published_output = 2925.0
            sample_calculation = "Balance 45,000 at 6.5 percent weighted rate yields 2,925 annual interest"
            disclosures = (
                [
                    "Title IV Public Service Statutory Guardrail: Commercial private lender offers are suppressed on public-service and statutory hardship pages",
                    "Independent Publisher Disclaimer",
                ]
                if restricted_ps
                else [
                    "Refinancing federal student loans permanently waives federal protections",
                    "FTC Partner Compensation Disclosure",
                    "Independent Publisher Disclaimer",
                ]
            )
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
        monetization qualification, and mathematical parameters derived from the tenant truth profile.
        Validates against tenant isolation and partner alignment firewalls.
        Zero em-dashes. Zero en-dashes.
        """
        if hasattr(candidate_spec, "to_dict"):
            spec = candidate_spec.to_dict()
        else:
            spec = dict(candidate_spec)

        tenant_id = self.tenant_id
        query = str(spec.get("query", "")).lower()
        slug = str(spec.get("slug", "") or sanitize_url_slug(query or "tool")).lower()
        combined = f"{query} {slug}".strip()

        monetization = qualify_monetization_opportunity(
            query=query or slug,
            slug=slug,
            property_id=tenant_id,
            search_volume=int(spec.get("search_volume", 1500) or 1500),
            cpc_usd=float(spec.get("cpc_usd", 4.5) or 4.5),
        )
        if monetization.get("intent_tier") == "cross_tenant_contamination":
            raise ValueError(monetization.get("rejection_reason", f"Cross-tenant isolation violation for {tenant_id}"))

        if tenant_id == "prexvo":
            restricted_ps = is_restricted_public_service_slug(slug, query)
            spec.setdefault("tenant", "prexvo")
            spec.setdefault("property_id", "prexvo")
            spec.setdefault("domain", "prexvo.com")
            spec.setdefault("canonical_base", "https://prexvo.com")
            spec.setdefault("statutory_authority", "34 CFR Part 685")
            spec.setdefault("economic_dataset", "FRED SLSTTOTAL Series")
            spec.setdefault("category", "Student Loan Repayment")
            spec.setdefault(
                "affiliates",
                [] if restricted_ps else (monetization.get("recommended_partners") or ["splash_financial", "sofi"]),
            )
            spec.setdefault("model_name", "Direct Consolidation Loan Weighted Model")
            spec.setdefault("formula", "balance * (weighted_rate / 100.0)")
            spec.setdefault("inputs", {"balance": 45000, "weighted_rate": 6.5})
            spec.setdefault("published_output", 2925.0)
            spec.setdefault(
                "sample_calculation",
                "Balance 45,000 at 6.5 percent weighted rate yields 2,925 annual interest",
            )
            if restricted_ps:
                spec.setdefault("mandatory_disclosures", [
                    "Title IV Public Service Statutory Guardrail: Commercial private lender offers are suppressed on public-service and statutory hardship pages",
                    "Independent Publisher Disclaimer",
                    PREXVO_DISCLOSURES.get("public_service_non_commercial_notice", ""),
                ])
                spec.setdefault("ymyl_warning", PREXVO_DISCLOSURES.get("public_service_non_commercial_notice", ""))
            else:
                spec.setdefault("mandatory_disclosures", [
                    "Refinancing federal student loans permanently waives federal protections",
                    "FTC Partner Compensation Disclosure",
                    "Independent Publisher Disclaimer",
                    PREXVO_DISCLOSURES.get("ymyl_forfeiture_disclaimer", ""),
                    PREXVO_DISCLOSURES.get("ftc_disclosure", ""),
                ])
                spec.setdefault("ymyl_warning", PREXVO_DISCLOSURES.get("ymyl_forfeiture_disclaimer", ""))
        else:
            spec.setdefault("tenant", "profithelm")
            spec.setdefault("property_id", "profithelm")
            spec.setdefault("domain", "profithelm.com")
            spec.setdefault("canonical_base", "https://profithelm.com")
            if "1031" in combined:
                spec.setdefault("statutory_authority", "IRC Section 1031(a)(1)")
                spec.setdefault("economic_dataset", "FRED CPILFESL Series")
                spec.setdefault("category", "1031 Exchange")
                spec.setdefault("affiliates", ["ipx1031", "exeter1031"])
                spec.setdefault("model_name", "Section 1031 Like-Kind Exchange Model")
                spec.setdefault("formula", "relinquished_basis + recognized_gain")
                spec.setdefault("inputs", {"relinquished_basis": 450000, "recognized_gain": 0})
                spec.setdefault("published_output", 450000.0)
                spec.setdefault(
                    "sample_calculation",
                    "Relinquished basis 450,000 with zero recognized gain yields replacement basis 450,000",
                )
            elif any(t in combined for t in ("crypto", "staking", "airdrop", "8949", "1099-da")):
                spec.setdefault("statutory_authority", "IRC Section 1001 & IRS Form 8949")
                spec.setdefault("economic_dataset", "FRED CPILFESL Series")
                spec.setdefault("category", "Crypto Tax Intelligence")
                spec.setdefault("affiliates", ["coinledger", "koinly"])
                spec.setdefault("model_name", "Digital Asset Realized Gain Model")
                spec.setdefault("formula", "proceeds - cost_basis")
                spec.setdefault("inputs", {"proceeds": 85000, "cost_basis": 35000})
                spec.setdefault("published_output", 50000.0)
                spec.setdefault(
                    "sample_calculation",
                    "Proceeds 85,000 minus cost basis 35,000 yields 50,000 net taxable capital gain",
                )
            elif any(t in combined for t in ("prediction", "kalshi", "polymarket", "implied-probability", "kelly")):
                spec.setdefault("statutory_authority", "IRC Section 1256 & Section 165(d)")
                spec.setdefault("economic_dataset", "FRED DGS10 Series")
                spec.setdefault("category", "Quantitative Market Analytics")
                spec.setdefault("affiliates", monetization.get("recommended_partners") or ["coinledger", "kalshi"])
                spec.setdefault("model_name", "Event Contract Expected Value Model")
                spec.setdefault("formula", "gross_payout - contract_cost")
                spec.setdefault("inputs", {"gross_payout": 10000, "contract_cost": 6200})
                spec.setdefault("published_output", 3800.0)
                spec.setdefault(
                    "sample_calculation",
                    "Gross payout 10,000 minus contract cost 6,200 yields 3,800 net settlement gain",
                )
            elif any(t in combined for t in ("bracket", "tcja", "capital-gains", "capital gains", "standard deduction")):
                spec.setdefault("statutory_authority", "IRC Section 1(j) & Rev. Proc. 2025-32")
                spec.setdefault("economic_dataset", "FRED CPILFESL Series")
                spec.setdefault("category", "Tax Intelligence")
                spec.setdefault("affiliates", monetization.get("recommended_partners") or ["turbotax", "taxslayer"])
                spec.setdefault("model_name", "Federal Statutory Bracket Liability Model")
                spec.setdefault("formula", "taxable_income * effective_rate")
                spec.setdefault("inputs", {"taxable_income": 180000, "effective_rate": 0.22})
                spec.setdefault("published_output", 39600.0)
                spec.setdefault(
                    "sample_calculation",
                    "Taxable income 180,000 at 22 percent effective rate yields 39,600 liability",
                )
            else:
                spec.setdefault("statutory_authority", "IRC Section 179(b)(1)")
                spec.setdefault("economic_dataset", "FRED CPILFESL Series")
                spec.setdefault("category", "Commercial Tax Intelligence")
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
                PROFITHELM_DISCLOSURES.get("ftc_disclosure", ""),
            ])

        spec.setdefault("intent_tier", monetization.get("intent_tier", ""))
        spec.setdefault("monetization_qualified", monetization.get("monetization_qualified", True))
        spec.setdefault("commercial_offers_allowed", monetization.get("commercial_offers_allowed", True))
        spec.setdefault("restricted_public_service", monetization.get("restricted_public_service", False))
        spec.setdefault("expected_bounty_usd", monetization.get("expected_bounty_usd", 0.0))
        spec.setdefault("estimated_monthly_revenue_usd", monetization.get("estimated_monthly_revenue_usd", 0.0))

        # Enforce partner alignment across tenant and intent boundaries
        alignment = verify_partner_domain_alignment(
            property_id=tenant_id,
            slug=slug,
            partners=list(spec.get("affiliates", [])),
        )
        if not alignment["aligned"]:
            raise ValueError(
                f"Partner alignment violation for {tenant_id} ({slug}): {'; '.join(alignment['violations'])}"
            )

        # Enforce tenant isolation check on text attributes
        disclosures_text = " ".join(str(d) for d in spec.get("mandatory_disclosures", []))
        text_to_check = f"{spec.get('title', '')} {spec.get('description', '')} {spec.get('quick_answer', '')} {spec.get('statutory_authority', '')} {disclosures_text}"
        self.fact_store.assert_tenant_isolation(tenant_id, text_to_check)

        return spec

    def run_blind_spot_pass(
        self,
        competitor_htmls: Optional[List[str]] = None,
        competitor_results: Optional[List[Dict[str, Any]]] = None,
        existing_tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a blind-spot discovery pass over raw competitor HTML documents and SERP results.
        Parses <form>, <input>, <select>, <output>, and JSON-LD @type schemas from competitor_htmls
        plus competitor_results, cross-references against TenantFactStore statutory authorities and
        datasets, and returns unknown-unknown interactive features, statutory blind spots, and
        tenant-isolated candidate specs.
        Zero em-dashes. Zero en-dashes.
        """
        profile = self.fact_store.get_profile(self.tenant_id) or self.tenant_profile
        existing_list = list(existing_tools or [])

        known_features: Set[str] = set()
        covered_citations: Set[str] = set()
        existing_corpus_parts: List[str] = []

        for tool in existing_list:
            if not isinstance(tool, dict):
                continue
            for feat in tool.get("interactive_features", []):
                if isinstance(feat, str) and feat.strip():
                    known_features.add(_normalize_feature_name(feat))
            inputs_dict = tool.get("inputs")
            if isinstance(inputs_dict, dict):
                for k in inputs_dict.keys():
                    known_features.add(_normalize_feature_name(str(k)))
            for field_name in ("slug", "title", "description", "statutory_authority", "primary_keyword"):
                val = str(tool.get(field_name, "") or "").strip()
                if val:
                    existing_corpus_parts.append(val.lower())

        existing_corpus = " ".join(existing_corpus_parts)

        discovered_features: List[str] = []
        discovered_set: Set[str] = set()

        def _register_feature(raw_feat: str) -> None:
            norm = _normalize_feature_name(raw_feat)
            if not norm or len(norm) < 3:
                return
            if self.scanner.scan_text(norm.replace("_", " "), self.tenant_id):
                return
            if norm not in known_features and norm not in discovered_set:
                discovered_set.add(norm)
                discovered_features.append(norm)

        # 1. Parse competitor HTML documents for <form>, <input>, <select>, <output>, and JSON-LD @type
        for raw_html in (competitor_htmls or []):
            if not isinstance(raw_html, str) or not raw_html.strip():
                continue
            # Extract form, input, select, output attributes
            for tag_match in re.finditer(
                r"<(form|input|select|output)\b([^>]*)>",
                raw_html,
                re.IGNORECASE,
            ):
                tag_name = tag_match.group(1).lower()
                attrs_str = tag_match.group(2)
                for attr_name in ("name", "id", "aria-label", "placeholder", "data-feature", "data-field"):
                    attr_m = re.search(
                        rf'\b{re.escape(attr_name)}\s*=\s*["\']([^"\']+)["\']',
                        attrs_str,
                        re.IGNORECASE,
                    )
                    if attr_m:
                        attr_val = attr_m.group(1).strip()
                        if attr_val and attr_val.lower() not in ("hidden", "submit", "button", "text", "number"):
                            _register_feature(f"{tag_name}_{attr_val}" if tag_name == "output" else attr_val)

            # Extract JSON-LD @type schemas
            for ld_match in re.finditer(
                r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                raw_html,
                re.IGNORECASE | re.DOTALL,
            ):
                ld_raw = ld_match.group(1).strip()
                try:
                    ld_data = json.loads(ld_raw)
                    ld_items = ld_data if isinstance(ld_data, list) else [ld_data]
                    for ld_item in ld_items:
                        if isinstance(ld_item, dict):
                            ld_type = ld_item.get("@type")
                            if isinstance(ld_type, str):
                                _register_feature(f"schema_{ld_type}")
                            elif isinstance(ld_type, list):
                                for t_item in ld_type:
                                    if isinstance(t_item, str):
                                        _register_feature(f"schema_{t_item}")
                except Exception:
                    pass

            for pat_feat in _extract_patterns(raw_html, INTERACTIVE_PATTERNS):
                _register_feature(pat_feat)

        # 2. Parse competitor SERP results
        for item in (competitor_results or []):
            if not isinstance(item, dict):
                continue
            for feat in item.get("interactive_features", []):
                if isinstance(feat, str) and feat.strip():
                    _register_feature(feat)
            combined_text = f"{item.get('title', '')} {item.get('snippet', '')} {item.get('description', '')}"
            for pat_feat in _extract_patterns(combined_text, INTERACTIVE_PATTERNS):
                _register_feature(pat_feat)

        # 3. Cross-reference against tenant statutory citations & features for statutory blind spots
        statutory_blind_spots: List[str] = []
        if profile and profile.statutory_truth and profile.statutory_truth.statutory_citations:
            for cit_key, cit_val in profile.statutory_truth.statutory_citations.items():
                cit_clean = str(cit_val).strip()
                if not cit_clean:
                    continue
                if self.scanner.scan_text(cit_clean, self.tenant_id):
                    continue
                if cit_clean.lower() not in existing_corpus and cit_key.lower().replace("_", " ") not in existing_corpus:
                    statutory_blind_spots.append(cit_clean)
                else:
                    covered_citations.add(cit_clean)

        if profile and profile.features:
            for feat_key, feat_contract in profile.features.items():
                if not feat_contract.enabled:
                    continue
                norm_fk = _normalize_feature_name(feat_key)
                if norm_fk not in known_features and feat_key.lower() not in existing_corpus:
                    _register_feature(norm_fk)

        # 4. Synthesize candidate specifications for discovered gaps
        candidate_specs: List[Dict[str, Any]] = []
        seed_features = discovered_features[:5]
        if not seed_features and statutory_blind_spots:
            seed_features = [_normalize_feature_name(s) for s in statutory_blind_spots[:3]]

        base_query = (
            "student loan repayment calculator"
            if self.tenant_id == "prexvo"
            else "section 179 tax deduction calculator"
        )
        for idx, feat in enumerate(seed_features):
            authority_override = (
                statutory_blind_spots[idx % len(statutory_blind_spots)]
                if statutory_blind_spots
                else None
            )
            serp_diffs = self.diff_competitor_serp(
                query=f"{base_query} {feat.replace('_', ' ')}",
                competitor_results=[{"interactive_features": [feat]}],
                existing_tool=existing_list[0] if existing_list else None,
            )
            for gap_spec in serp_diffs:
                enriched = self.enrich_candidate_spec(gap_spec)
                if authority_override:
                    enriched["statutory_authority"] = authority_override
                disclosures_str = " ".join(str(d) for d in enriched.get("mandatory_disclosures", []))
                text_to_check = (
                    f"{enriched.get('title', '')} {enriched.get('description', '')} "
                    f"{enriched.get('quick_answer', '')} {enriched.get('statutory_authority', '')} "
                    f"{disclosures_str}"
                )
                self.fact_store.assert_tenant_isolation(self.tenant_id, text_to_check)
                assert_no_forbidden_dashes(json.dumps(enriched), context="blind_spot_candidate_spec")
                candidate_specs.append(enriched)

        return {
            "tenant_id": self.tenant_id,
            "unknown_unknown_features": discovered_features,
            "statutory_blind_spots": statutory_blind_spots,
            "candidate_specs": candidate_specs,
        }

    def benchmark_multi_engine_rankings(
        self,
        queries: Optional[List[str]] = None,
        custom_serp_observations: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Benchmarks target queries for this tenant across Google, Bing, and DuckDuckGo,
        recording current ranking positions, higher-ranked competing apps, root-cause
        indexing/ranking gaps, and codified pseofactory compiler upgrades.
        Enforces strict domain isolation and YMYL public-service guardrails.
        Zero em-dashes. Zero en-dashes.
        """
        return _execute_multi_engine_benchmark(
            tenant_profile=self.tenant_profile,
            fact_store=self.fact_store,
            queries=queries,
            custom_serp_observations=custom_serp_observations,
        )


SUPPORTED_SEARCH_ENGINES = ("google", "bing", "duckduckgo")

WINNING_COMPETITOR_MECHANICS: Dict[str, Dict[str, Any]] = {
    "server_rendered_sensitivity_grid": {
        "mechanic_id": "server_rendered_sensitivity_grid",
        "title": "Server-Rendered 5-Point Sensitivity Matrix",
        "why_competitors_rank_higher": (
            "Competing calculators pre-render multi-row numeric sensitivity tables directly "
            "in initial HTML so Googlebot, Bingbot, and DuckDuckGo index concrete dollar outputs "
            "without executing client JavaScript."
        ),
        "compiler_implementation": (
            "compile_high_effort_page renders a 5-step (0.8x to 1.2x) deterministic HTML table "
            "alongside the interactive calculator and SVG sensitivity chart."
        ),
    },
    "deep_link_scenario_presets": {
        "mechanic_id": "deep_link_scenario_presets",
        "title": "Crawlable URL-Parameterized Scenario Presets",
        "why_competitors_rank_higher": (
            "Top-ranked apps expose 1-click preset scenarios (Conservative, Baseline, Aggressive) "
            "backed by query parameters that increase dwell time and earn long-tail anchor links."
        ),
        "compiler_implementation": (
            "compile_high_effort_page renders touch-compliant preset links (?param=value) "
            "that hydrate URLSearchParams on load and recompute outputs deterministically."
        ),
    },
    "jsonld_entity_triad": {
        "mechanic_id": "jsonld_entity_triad",
        "title": "SoftwareApplication + FAQPage + BreadcrumbList + HowTo Schema Graph",
        "why_competitors_rank_higher": (
            "Incumbent financial portals pair exact H1/Title parity with "
            "complete JSON-LD entity graphs to capture rich snippets and AI answer citations."
        ),
        "compiler_implementation": (
            "compile_high_effort_page emits synchronized SoftwareApplication, FAQPage, "
            "BreadcrumbList, and HowTo JSON-LD with 1:1 title/H1 parity."
        ),
    },
    "compliant_intent_monetization": {
        "mechanic_id": "compliant_intent_monetization",
        "title": "Domain-Isolated Affiliate Routing and Statutory YMYL Guardrails",
        "why_competitors_rank_higher": (
            "High-trust calculators match commercial CTAs strictly to transactional intent "
            "while keeping restricted public-service pages free of commercial lender pitches."
        ),
        "compiler_implementation": (
            "compile_high_effort_page routes domain-verified affiliate partners with "
            "mandatory regulatory disclosures while suppressing commercial offers on "
            "restricted public-service pages."
        ),
    },
    "instant_edge_case_trap_immediacy": {
        "mechanic_id": "instant_edge_case_trap_immediacy",
        "title": "Pre-Hydrated Statutory Deadline and Edge-Case Trap Immediacy",
        "why_competitors_rank_higher": (
            "Niche conversion leaders pre-hydrate realistic statutory scenarios "
            "on load and surface immediate statutory deadline or phaseout traps "
            "inside the calculator workspace before users click submit."
        ),
        "compiler_implementation": (
            "compile_high_effort_page and RetroReflectionEngine render a pre-hydrated statutory "
            "edge-case trap alert (data-mechanic='instant_edge_case_trap_immediacy') directly "
            "inside the interactive calculator workspace."
        ),
    },
    "statutory_compliance_framing": {
        "mechanic_id": "statutory_compliance_framing",
        "title": "Beyond the Calculator Statutory Compliance Checklist and Pitfall Matrix",
        "why_competitors_rank_higher": (
            "Authoritative YMYL tools explicitly separate what arithmetic proves from what requires "
            "legal and procedural verification through compliance checklists and Issue-to-Prevention "
            "statutory pitfall tables."
        ),
        "compiler_implementation": (
            "compile_high_effort_page and RetroReflectionEngine render a structured Beyond the "
            "Calculator compliance checklist and 3-column Statutory Pitfalls matrix "
            "(data-mechanic='statutory_compliance_framing')."
        ),
    },
    "three_tier_topic_cluster_nav": {
        "mechanic_id": "three_tier_topic_cluster_nav",
        "title": "On-This-Page Jump Bar and 3-Tier Hub-and-Spoke Topic Cluster",
        "why_competitors_rank_higher": (
            "Specialist financial hubs pair an accessible On-This-Page anchor bar with a 3-tier "
            "topic cluster (Tier 1 Core Statutory Pillars, Tier 2 Comparative Matrices, Tier 3 "
            "Jurisdiction and Entity Spokes) to concentrate internal PageRank and guide decisions."
        ),
        "compiler_implementation": (
            "compile_high_effort_page and RetroReflectionEngine render an accessible "
            "nav.on-this-page-nav jump bar and a 3-tier topic cluster hub "
            "(data-mechanic='three_tier_topic_cluster_nav')."
        ),
    },
    "vetted_commercial_handoff_framing": {
        "mechanic_id": "vetted_commercial_handoff_framing",
        "title": "Vertical-Matched Commercial Handoff with Provider Vetting Checklist",
        "why_competitors_rank_higher": (
            "High-converting tools never display cross-vertical ads; they pair strictly vertical-matched "
            "execution partners with a Provider Vetting Checklist (fidelity bond, segregated escrow, "
            "or statutory rate-lock verification) that converts calculator intent into trusted action."
        ),
        "compiler_implementation": (
            "compile_high_effort_page and RetroReflectionEngine attach a vertical-matched Provider "
            "Vetting Checklist (data-mechanic='vetted_commercial_handoff_framing') while preserving "
            "strict non-commercial guardrails on restricted public-service pages."
        ),
    },
}

TARGET_QUERY_BENCHMARKS: Dict[str, List[Dict[str, Any]]] = {
    "profithelm": [
        {
            "query": "section 179 deduction calculator",
            "slug": "section-179-deduction-calculator",
            "target_url": "https://profithelm.com/tools/section-179-deduction-calculator/",
            "intent_tier": "tier_1_commercial_b2b",
            "engine_positions": {"google": None, "bing": 18, "duckduckgo": 14},
            "higher_ranked_competitors": [
                {
                    "domain": "section179.org",
                    "url": "https://www.section179.org/section_179_calculator/",
                    "engine_ranks": {"google": 1, "bing": 1, "duckduckgo": 1},
                    "winning_mechanics": [
                        "server_rendered_sensitivity_grid",
                        "deep_link_scenario_presets",
                        "compliant_intent_monetization",
                        "instant_edge_case_trap_immediacy",
                    ],
                    "indexing_advantage": "Pre-rendered statutory cap phaseout table + equipment financing CTA.",
                },
                {
                    "domain": "crestcapital.com",
                    "url": "https://www.crestcapital.com/tax_deduction_calculator",
                    "engine_ranks": {"google": 2, "bing": 2, "duckduckgo": 3},
                    "winning_mechanics": [
                        "server_rendered_sensitivity_grid",
                        "jsonld_entity_triad",
                        "vetted_commercial_handoff_framing",
                    ],
                    "indexing_advantage": "Direct lender authority + immediate equipment lease financing workflow.",
                },
            ],
            "root_cause_diagnosis": (
                "Incumbents section179.org and crestcapital.com rank #1-#2 across Google, Bing, and "
                "DuckDuckGo because they pair IRC Section 179 phaseout tables with immediate equipment "
                "financing CTAs and deep-linked cost presets."
            ),
            "compiler_upgrades_applied": list(WINNING_COMPETITOR_MECHANICS.keys()),
            "recommended_affiliates": ["crest_capital", "mercury"],
        },
        {
            "query": "1031 exchange boot calculator",
            "slug": "1031-exchange-boot-calculator",
            "target_url": "https://profithelm.com/tools/1031-exchange-boot-calculator/",
            "intent_tier": "tier_1_commercial_b2b",
            "engine_positions": {"google": None, "bing": 22, "duckduckgo": 19},
            "higher_ranked_competitors": [
                {
                    "domain": "ipx1031.com",
                    "url": "https://www.ipx1031.com/1031-exchange-calculator/",
                    "engine_ranks": {"google": 1, "bing": 1, "duckduckgo": 2},
                    "winning_mechanics": [
                        "server_rendered_sensitivity_grid",
                        "jsonld_entity_triad",
                        "compliant_intent_monetization",
                    ],
                    "indexing_advantage": "Qualified intermediary domain authority + mortgage boot breakdown table.",
                },
                {
                    "domain": "start1031.com",
                    "url": "https://start1031.com/tools/boot-calculator/",
                    "engine_ranks": {"google": 2, "bing": 2, "duckduckgo": 1},
                    "winning_mechanics": [
                        "instant_edge_case_trap_immediacy",
                        "statutory_compliance_framing",
                        "three_tier_topic_cluster_nav",
                        "vetted_commercial_handoff_framing",
                    ],
                    "indexing_advantage": (
                        "Pre-hydrated mortgage and cash boot inputs, IRC Section 1031(a)(3)(B)(ii) "
                        "tax-return deadline trap alerts, Beyond the Calculator QI compliance framing, "
                        "and 3-tier pillar/tool/state topic clustering."
                    ),
                },
                {
                    "domain": "exeter1031.com",
                    "url": "https://www.exeter1031.com/1031_exchange_calculator.aspx",
                    "engine_ranks": {"google": 3, "bing": 4, "duckduckgo": 4},
                    "winning_mechanics": ["server_rendered_sensitivity_grid"],
                    "indexing_advantage": "Explicit IRC Section 1031(a)(1) boot recognition examples in static HTML.",
                },
            ],
            "root_cause_diagnosis": (
                "Qualified intermediary and specialist 1031 portals (ipx1031.com, start1031.com, exeter1031.com) "
                "dominate top SERP positions and conversion rates by pairing pre-hydrated cash vs mortgage boot "
                "tables with IRC Section 1031(a)(3)(B)(ii) deadline trap alerts, Beyond the Calculator QI "
                "compliance checklists, and 3-tier pillar/tool/state topic clusters."
            ),
            "compiler_upgrades_applied": list(WINNING_COMPETITOR_MECHANICS.keys()),
            "recommended_affiliates": ["ipx1031", "exeter1031"],
        },
        {
            "query": "crypto staking tax calculator",
            "slug": "crypto-staking-tax-calculator",
            "target_url": "https://profithelm.com/tools/crypto-staking-tax-calculator/",
            "intent_tier": "tier_2_crypto_tax",
            "engine_positions": {"google": None, "bing": 16, "duckduckgo": 12},
            "higher_ranked_competitors": [
                {
                    "domain": "coinledger.io",
                    "url": "https://coinledger.io/tools/crypto-tax-calculator",
                    "engine_ranks": {"google": 1, "bing": 2, "duckduckgo": 1},
                    "winning_mechanics": [
                        "deep_link_scenario_presets",
                        "jsonld_entity_triad",
                        "compliant_intent_monetization",
                    ],
                    "indexing_advantage": "Form 8949 + Rev. Rul. 2023-14 FAQ schema + direct 1099-DA import CTA.",
                },
                {
                    "domain": "koinly.io",
                    "url": "https://koinly.io/crypto-tax-calculator/",
                    "engine_ranks": {"google": 2, "bing": 1, "duckduckgo": 2},
                    "winning_mechanics": [
                        "server_rendered_sensitivity_grid",
                        "deep_link_scenario_presets",
                    ],
                    "indexing_advantage": "Preset cost-basis scenarios and multi-bracket capital gains tables.",
                },
            ],
            "root_cause_diagnosis": (
                "CoinLedger and Koinly lead across Google, Bing, and DuckDuckGo by combining IRS Form 8949 "
                "structured FAQ schema with preset portfolio scenarios and direct tax-loss harvesting CTAs."
            ),
            "compiler_upgrades_applied": [
                "server_rendered_sensitivity_grid",
                "deep_link_scenario_presets",
                "jsonld_entity_triad",
                "compliant_intent_monetization",
            ],
            "recommended_affiliates": ["coinledger", "koinly"],
        },
        {
            "query": "kalshi polymarket kelly criterion calculator",
            "slug": "prediction-market-kelly-criterion-calculator",
            "target_url": "https://profithelm.com/tools/prediction-market-kelly-criterion-calculator/",
            "intent_tier": "tier_2_crypto_tax",
            "engine_positions": {"google": 11, "bing": 7, "duckduckgo": 6},
            "higher_ranked_competitors": [
                {
                    "domain": "omnicalculator.com",
                    "url": "https://www.omnicalculator.com/finance/kelly-criterion",
                    "engine_ranks": {"google": 1, "bing": 1, "duckduckgo": 1},
                    "winning_mechanics": [
                        "server_rendered_sensitivity_grid",
                        "deep_link_scenario_presets",
                        "jsonld_entity_triad",
                    ],
                    "indexing_advantage": "Deep-linked bankroll presets and step-by-step HowTo JSON-LD.",
                },
                {
                    "domain": "albionresearch.com",
                    "url": "https://www.albionresearch.com/tools/kelly",
                    "engine_ranks": {"google": 4, "bing": 5, "duckduckgo": 4},
                    "winning_mechanics": ["server_rendered_sensitivity_grid"],
                    "indexing_advantage": "Fractional Kelly drawdown table rendered directly in DOM.",
                },
            ],
            "root_cause_diagnosis": (
                "Generic Kelly calculators rank ahead on broad terms, but lack Kalshi quadratic fee drag "
                "and IRC Section 1256 tax-treatment modeling."
            ),
            "compiler_upgrades_applied": [
                "server_rendered_sensitivity_grid",
                "deep_link_scenario_presets",
                "jsonld_entity_triad",
                "compliant_intent_monetization",
            ],
            "recommended_affiliates": ["coinledger", "kalshi"],
        },
        {
            "query": "federal tax bracket calculator",
            "slug": "federal-tax-bracket-calculator",
            "target_url": "https://profithelm.com/tools/federal-tax-bracket-calculator/",
            "intent_tier": "tier_3_general_tax",
            "engine_positions": {"google": None, "bing": 28, "duckduckgo": 24},
            "higher_ranked_competitors": [
                {
                    "domain": "smartasset.com",
                    "url": "https://smartasset.com/taxes/income-taxes",
                    "engine_ranks": {"google": 1, "bing": 1, "duckduckgo": 2},
                    "winning_mechanics": [
                        "server_rendered_sensitivity_grid",
                        "deep_link_scenario_presets",
                        "jsonld_entity_triad",
                    ],
                    "indexing_advantage": "Pre-rendered marginal vs effective tax tables across income presets.",
                },
                {
                    "domain": "nerdwallet.com",
                    "url": "https://www.nerdwallet.com/calculator/tax-calculator",
                    "engine_ranks": {"google": 2, "bing": 2, "duckduckgo": 1},
                    "winning_mechanics": [
                        "jsonld_entity_triad",
                        "compliant_intent_monetization",
                    ],
                    "indexing_advantage": "Rev. Proc. statutory inflation citations + compliant retail tax filing CTAs.",
                },
            ],
            "root_cause_diagnosis": (
                "SmartAsset and NerdWallet dominate top positions with pre-rendered income bracket sensitivity "
                "tables and retail tax software links."
            ),
            "compiler_upgrades_applied": [
                "server_rendered_sensitivity_grid",
                "deep_link_scenario_presets",
                "jsonld_entity_triad",
                "compliant_intent_monetization",
            ],
            "recommended_affiliates": ["turbotax", "taxslayer"],
        },
    ],
    "prexvo": [
        {
            "query": "repayment assistance plan rap vs ibr calculator",
            "slug": "rap-vs-ibr-calculator",
            "target_url": "https://prexvo.com/tools/rap-vs-ibr-calculator/",
            "intent_tier": "tier_2_federal_repayment",
            "restricted_public_service": False,
            "commercial_offers_allowed": True,
            "engine_positions": {"google": 14, "bing": 9, "duckduckgo": 8},
            "higher_ranked_competitors": [
                {
                    "domain": "studentaid.gov",
                    "url": "https://studentaid.gov/loan-simulator/",
                    "engine_ranks": {"google": 1, "bing": 1, "duckduckgo": 1},
                    "winning_mechanics": [
                        "server_rendered_sensitivity_grid",
                        "jsonld_entity_triad",
                    ],
                    "indexing_advantage": "Official .gov authority + 34 CFR Part 685 statutory citations.",
                },
                {
                    "domain": "studentloanplanner.com",
                    "url": "https://www.studentloanplanner.com/income-driven-repayment-calculator/",
                    "engine_ranks": {"google": 2, "bing": 2, "duckduckgo": 2},
                    "winning_mechanics": [
                        "server_rendered_sensitivity_grid",
                        "deep_link_scenario_presets",
                        "jsonld_entity_triad",
                    ],
                    "indexing_advantage": "Side-by-side AGI sensitivity table and preset borrower profiles.",
                },
            ],
            "root_cause_diagnosis": (
                "StudentAid.gov and StudentLoanPlanner rank #1-#2 via side-by-side AGI sensitivity tables, "
                "34 CFR Part 685 citations, and preset borrower scenarios."
            ),
            "compiler_upgrades_applied": [
                "server_rendered_sensitivity_grid",
                "deep_link_scenario_presets",
                "jsonld_entity_triad",
                "compliant_intent_monetization",
            ],
            "recommended_affiliates": ["splash_financial", "sofi"],
        },
        {
            "query": "pslf qualifying payment simulator",
            "slug": "pslf-qualifying-payment-simulator",
            "target_url": "https://prexvo.com/tools/pslf-qualifying-payment-simulator/",
            "intent_tier": "tier_2_public_service_restricted",
            "restricted_public_service": True,
            "commercial_offers_allowed": False,
            "engine_positions": {"google": None, "bing": 15, "duckduckgo": 11},
            "higher_ranked_competitors": [
                {
                    "domain": "studentaid.gov",
                    "url": "https://studentaid.gov/manage-loans/forgiveness-cancellation/public-service",
                    "engine_ranks": {"google": 1, "bing": 1, "duckduckgo": 1},
                    "winning_mechanics": [
                        "server_rendered_sensitivity_grid",
                        "jsonld_entity_triad",
                        "compliant_intent_monetization",
                    ],
                    "indexing_advantage": "Zero commercial private lender distraction on 120-payment PSLF statutory guidance.",
                },
                {
                    "domain": "tisla.org",
                    "url": "https://freestudentloanadvice.org/loan-forgiveness/public-service-loan-forgiveness/",
                    "engine_ranks": {"google": 3, "bing": 3, "duckduckgo": 2},
                    "winning_mechanics": [
                        "jsonld_entity_triad",
                        "compliant_intent_monetization",
                    ],
                    "indexing_advantage": "Pure non-commercial public-service E-E-A-T alignment under 34 CFR 685.219.",
                },
            ],
            "root_cause_diagnosis": (
                "YMYL search quality raters demote PSLF pages that inject commercial private lender CTAs "
                "because private loan conversion permanently waives federal protections under 34 CFR 685.219."
            ),
            "compiler_upgrades_applied": [
                "server_rendered_sensitivity_grid",
                "deep_link_scenario_presets",
                "jsonld_entity_triad",
                "compliant_intent_monetization",
            ],
            "recommended_affiliates": [],
        },
        {
            "query": "save plan litigation forbearance transition calculator",
            "slug": "save-plan-litigation-transition",
            "target_url": "https://prexvo.com/tools/save-plan-litigation-transition/",
            "intent_tier": "tier_2_public_service_restricted",
            "restricted_public_service": True,
            "commercial_offers_allowed": False,
            "engine_positions": {"google": 12, "bing": 8, "duckduckgo": 7},
            "higher_ranked_competitors": [
                {
                    "domain": "studentaid.gov",
                    "url": "https://studentaid.gov/announcements-events/save-court-actions",
                    "engine_ranks": {"google": 1, "bing": 1, "duckduckgo": 1},
                    "winning_mechanics": [
                        "jsonld_entity_triad",
                        "compliant_intent_monetization",
                    ],
                    "indexing_advantage": "Non-commercial statutory forbearance and buyback guidance.",
                },
                {
                    "domain": "studentloanplanner.com",
                    "url": "https://www.studentloanplanner.com/save-plan-lawsuit-updates/",
                    "engine_ranks": {"google": 2, "bing": 3, "duckduckgo": 2},
                    "winning_mechanics": [
                        "server_rendered_sensitivity_grid",
                        "deep_link_scenario_presets",
                    ],
                    "indexing_advantage": "Pre-rendered SAVE to IBR/RAP payment delta tables across income bands.",
                },
            ],
            "root_cause_diagnosis": (
                "SAVE litigation transition borrowers require non-commercial statutory buyback and IBR migration "
                "tables without private lender offers that waive federal protections."
            ),
            "compiler_upgrades_applied": [
                "server_rendered_sensitivity_grid",
                "deep_link_scenario_presets",
                "jsonld_entity_triad",
                "compliant_intent_monetization",
            ],
            "recommended_affiliates": [],
        },
        {
            "query": "student loan refinance break even calculator",
            "slug": "student-loan-refinance-break-even",
            "target_url": "https://prexvo.com/tools/student-loan-refinance-break-even/",
            "intent_tier": "tier_1_private_refinance",
            "restricted_public_service": False,
            "commercial_offers_allowed": True,
            "engine_positions": {"google": None, "bing": 19, "duckduckgo": 15},
            "higher_ranked_competitors": [
                {
                    "domain": "nerdwallet.com",
                    "url": "https://www.nerdwallet.com/calculator/student-loan-refinance-calculator",
                    "engine_ranks": {"google": 1, "bing": 1, "duckduckgo": 1},
                    "winning_mechanics": [
                        "server_rendered_sensitivity_grid",
                        "deep_link_scenario_presets",
                        "jsonld_entity_triad",
                        "compliant_intent_monetization",
                    ],
                    "indexing_advantage": "Rate-spread sensitivity matrix + explicit Title IV forfeiture warning.",
                },
                {
                    "domain": "sofi.com",
                    "url": "https://www.sofi.com/student-loan-refinancing-calculator/",
                    "engine_ranks": {"google": 2, "bing": 2, "duckduckgo": 2},
                    "winning_mechanics": [
                        "server_rendered_sensitivity_grid",
                        "deep_link_scenario_presets",
                    ],
                    "indexing_advantage": "Instant term-length preset comparisons and clear APR disclosures.",
                },
            ],
            "root_cause_diagnosis": (
                "NerdWallet and SoFi rank at the top by pairing rate-reduction sensitivity tables with "
                "mandatory notices that refinancing federal student loans permanently waives federal protections."
            ),
            "compiler_upgrades_applied": [
                "server_rendered_sensitivity_grid",
                "deep_link_scenario_presets",
                "jsonld_entity_triad",
                "compliant_intent_monetization",
            ],
            "recommended_affiliates": ["splash_financial", "sofi"],
        },
        {
            "query": "physician student loan refinance calculator",
            "slug": "physician-student-loan-repayment-calculator",
            "target_url": "https://prexvo.com/tools/physician-student-loan-repayment-calculator/",
            "intent_tier": "tier_1_private_refinance",
            "restricted_public_service": False,
            "commercial_offers_allowed": True,
            "engine_positions": {"google": 16, "bing": 11, "duckduckgo": 9},
            "higher_ranked_competitors": [
                {
                    "domain": "whitecoatinvestor.com",
                    "url": "https://www.whitecoatinvestor.com/student-loan-refinancing/",
                    "engine_ranks": {"google": 1, "bing": 2, "duckduckgo": 1},
                    "winning_mechanics": [
                        "server_rendered_sensitivity_grid",
                        "compliant_intent_monetization",
                    ],
                    "indexing_advantage": "Residency-to-attending salary curve comparisons + Splash Financial CTA.",
                },
                {
                    "domain": "splashfinancial.com",
                    "url": "https://www.splashfinancial.com/medical-school-loan-refinancing/",
                    "engine_ranks": {"google": 2, "bing": 1, "duckduckgo": 2},
                    "winning_mechanics": [
                        "deep_link_scenario_presets",
                        "jsonld_entity_triad",
                    ],
                    "indexing_advantage": "Specialty debt-to-income presets and Title IV waiver disclosures.",
                },
            ],
            "root_cause_diagnosis": (
                "WhiteCoatInvestor and Splash Financial outrank generic calculators by modeling residency vs "
                "attending income presets while disclosing that refinancing federal student loans permanently waives federal protections."
            ),
            "compiler_upgrades_applied": [
                "server_rendered_sensitivity_grid",
                "deep_link_scenario_presets",
                "jsonld_entity_triad",
                "compliant_intent_monetization",
            ],
            "recommended_affiliates": ["splash_financial", "sofi"],
        },
    ],
}


@dataclass
class MultiEngineQueryBenchmark:
    """
    Structured multi-engine ranking and competitor gap record for a single target query.
    Zero em-dashes. Zero en-dashes.
    """
    property_id: str
    query: str
    slug: str
    target_url: str
    intent_tier: str
    restricted_public_service: bool
    commercial_offers_allowed: bool
    engine_positions: Dict[str, Optional[int]]
    indexed_engines: List[str]
    unindexed_engines: List[str]
    higher_ranked_competitors: List[Dict[str, Any]]
    root_cause_diagnosis: str
    compiler_upgrades_applied: List[str]
    recommended_affiliates: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _execute_multi_engine_benchmark(
    tenant_profile: TenantTruthProfile,
    fact_store: TenantFactStore,
    queries: Optional[List[str]] = None,
    custom_serp_observations: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Internal helper executing multi-engine ranking diagnostics and competitor benchmarking.
    Zero em-dashes. Zero en-dashes.
    """
    prop = tenant_profile.tenant_id.strip().lower()
    if prop not in TARGET_QUERY_BENCHMARKS:
        raise ValueError(f"Unsupported tenant '{prop}' for multi-engine ranking benchmark")

    baseline_entries = {
        entry["query"].lower(): dict(entry)
        for entry in TARGET_QUERY_BENCHMARKS[prop]
    }
    observations = custom_serp_observations or {}

    if queries:
        selected_queries = [q.strip() for q in queries if q and q.strip()]
    else:
        selected_queries = [entry["query"] for entry in TARGET_QUERY_BENCHMARKS[prop]]

    benchmarks: List[MultiEngineQueryBenchmark] = []
    engine_indexed_counts: Dict[str, int] = {eng: 0 for eng in SUPPORTED_SEARCH_ENGINES}
    engine_rank_sums: Dict[str, List[int]] = {eng: [] for eng in SUPPORTED_SEARCH_ENGINES}
    competitor_domain_counts: Dict[str, int] = {}

    for raw_q in selected_queries:
        q_key = raw_q.strip().lower()
        base = dict(baseline_entries.get(q_key, {}))
        obs = dict(observations.get(q_key) or observations.get(raw_q) or {})

        slug = str(obs.get("slug") or base.get("slug") or sanitize_url_slug(raw_q))
        canonical_base = tenant_profile.canonical_domain.rstrip("/")
        target_url = str(obs.get("target_url") or base.get("target_url") or f"{canonical_base}/tools/{slug}/")

        monetization = qualify_monetization_opportunity(
            query=raw_q,
            slug=slug,
            property_id=prop,
            search_volume=int(obs.get("search_volume", 1800) or 1800),
            cpc_usd=float(obs.get("cpc_usd", 5.0) or 5.0),
        )
        if monetization.get("intent_tier") == "cross_tenant_contamination":
            raise ValueError(monetization.get("rejection_reason", f"Cross-tenant query '{raw_q}' rejected for {prop}"))

        restricted_ps = bool(
            prop == "prexvo" and is_restricted_public_service_slug(slug, raw_q)
        )
        commercial_allowed = not restricted_ps
        recommended_affiliates = (
            []
            if restricted_ps
            else list(
                obs.get("recommended_affiliates")
                or base.get("recommended_affiliates")
                or monetization.get("recommended_partners")
                or []
            )
        )

        alignment = verify_partner_domain_alignment(
            property_id=prop,
            slug=slug,
            partners=recommended_affiliates,
        )
        if not alignment["aligned"]:
            raise ValueError(
                f"Multi-engine benchmark affiliate alignment violation for {prop} ({slug}): "
                f"{'; '.join(alignment['violations'])}"
            )

        raw_positions = dict(base.get("engine_positions") or {})
        if "engine_positions" in obs and isinstance(obs["engine_positions"], dict):
            raw_positions.update(obs["engine_positions"])

        engine_positions: Dict[str, Optional[int]] = {}
        indexed_engines: List[str] = []
        unindexed_engines: List[str] = []

        for eng in SUPPORTED_SEARCH_ENGINES:
            pos = raw_positions.get(eng)
            if isinstance(pos, int) and pos > 0:
                engine_positions[eng] = pos
                indexed_engines.append(eng)
                engine_indexed_counts[eng] += 1
                engine_rank_sums[eng].append(pos)
            else:
                engine_positions[eng] = None
                unindexed_engines.append(eng)

        competitors = list(obs.get("higher_ranked_competitors") or base.get("higher_ranked_competitors") or [])
        if not competitors:
            default_comp_domain = "studentaid.gov" if prop == "prexvo" else "smartasset.com"
            competitors = [
                {
                    "domain": default_comp_domain,
                    "url": f"https://{default_comp_domain}/",
                    "engine_ranks": {"google": 1, "bing": 1, "duckduckgo": 1},
                    "winning_mechanics": [
                        "server_rendered_sensitivity_grid",
                        "deep_link_scenario_presets",
                        "jsonld_entity_triad",
                    ],
                    "indexing_advantage": "Server-rendered sensitivity tables and structured schema entities.",
                }
            ]

        for comp in competitors:
            dom = str(comp.get("domain", "")).strip().lower()
            if dom:
                competitor_domain_counts[dom] = competitor_domain_counts.get(dom, 0) + 1

        diagnosis = str(
            obs.get("root_cause_diagnosis")
            or base.get("root_cause_diagnosis")
            or (
                "Competing calculators outrank target URL via pre-rendered sensitivity tables, "
                "URL-parameterized scenario presets, and complete JSON-LD entity graphs."
            )
        )
        upgrades = list(
            obs.get("compiler_upgrades_applied")
            or base.get("compiler_upgrades_applied")
            or list(WINNING_COMPETITOR_MECHANICS.keys())
        )

        record = MultiEngineQueryBenchmark(
            property_id=prop,
            query=raw_q,
            slug=slug,
            target_url=target_url,
            intent_tier=str(base.get("intent_tier") or monetization.get("intent_tier") or ""),
            restricted_public_service=restricted_ps,
            commercial_offers_allowed=commercial_allowed,
            engine_positions=engine_positions,
            indexed_engines=indexed_engines,
            unindexed_engines=unindexed_engines,
            higher_ranked_competitors=competitors,
            root_cause_diagnosis=diagnosis,
            compiler_upgrades_applied=upgrades,
            recommended_affiliates=recommended_affiliates,
        )

        serialized = json.dumps(record.to_dict())
        fact_store.assert_tenant_isolation(prop, serialized)
        assert_no_forbidden_dashes(serialized, context=f"multi_engine_benchmark:{prop}:{slug}")
        benchmarks.append(record)

    total_queries = len(benchmarks)
    engine_summary: Dict[str, Dict[str, Any]] = {}
    for eng in SUPPORTED_SEARCH_ENGINES:
        ranks = engine_rank_sums[eng]
        indexed_ct = engine_indexed_counts[eng]
        engine_summary[eng] = {
            "engine": eng,
            "total_queries": total_queries,
            "indexed_count": indexed_ct,
            "unindexed_count": total_queries - indexed_ct,
            "index_coverage_ratio": round(indexed_ct / total_queries, 4) if total_queries else 0.0,
            "average_rank_when_indexed": round(sum(ranks) / len(ranks), 2) if ranks else None,
            "best_rank": min(ranks) if ranks else None,
        }

    top_competitors = [
        {"domain": dom, "appearances_ahead": count}
        for dom, count in sorted(competitor_domain_counts.items(), key=lambda item: (-item[1], item[0]))
    ]

    report = {
        "property_id": prop,
        "canonical_domain": tenant_profile.canonical_domain,
        "supported_engines": list(SUPPORTED_SEARCH_ENGINES),
        "total_queries_benchmarked": total_queries,
        "engine_summary": engine_summary,
        "top_competing_domains": top_competitors,
        "codified_winning_mechanics": list(WINNING_COMPETITOR_MECHANICS.values()),
        "query_benchmarks": [b.to_dict() for b in benchmarks],
        "isolation_verified": True,
        "ymyl_public_service_guardrails_enforced": True if prop == "prexvo" else False,
    }
    assert_no_forbidden_dashes(json.dumps(report), context=f"multi_engine_report:{prop}")
    return report


def benchmark_multi_engine_rankings(
    tenant_id: Union[str, TenantTruthProfile] = "profithelm",
    queries: Optional[List[str]] = None,
    custom_serp_observations: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Module-level entry point to benchmark target queries across Google, Bing, and DuckDuckGo
    for either profithelm or prexvo under strict domain isolation.
    Zero em-dashes. Zero en-dashes.
    """
    if isinstance(tenant_id, TenantTruthProfile):
        profile = tenant_id
    else:
        store = TenantFactStore.get_instance()
        profile = store.get_profile(str(tenant_id))
        if profile is None:
            raise ValueError(f"Unknown tenant_id '{tenant_id}' for benchmark_multi_engine_rankings")
    engine = CompetitorGapEngine(profile)
    return engine.benchmark_multi_engine_rankings(
        queries=queries,
        custom_serp_observations=custom_serp_observations,
    )


def benchmark_all_properties() -> Dict[str, Dict[str, Any]]:
    """
    Benchmarks multi-engine search rankings and higher-ranked competitors across both
    profithelm and prexvo, returning a domain-isolated comparison dictionary.
    Zero em-dashes. Zero en-dashes.
    """
    return {
        "profithelm": benchmark_multi_engine_rankings("profithelm"),
        "prexvo": benchmark_multi_engine_rankings("prexvo"),
    }


def run_blind_spot_pass(
    tenant_id: Union[str, TenantTruthProfile] = "profithelm",
    competitor_htmls: Optional[List[str]] = None,
    competitor_results: Optional[List[Dict[str, Any]]] = None,
    existing_tools: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Module-level helper to execute CompetitorGapEngine.run_blind_spot_pass for a given tenant.
    Zero em-dashes. Zero en-dashes.
    """
    if isinstance(tenant_id, TenantTruthProfile):
        profile = tenant_id
    else:
        store = TenantFactStore.get_instance()
        profile = store.get_profile(str(tenant_id))
        if profile is None:
            raise ValueError(f"Unknown tenant_id '{tenant_id}' for run_blind_spot_pass")
    engine = CompetitorGapEngine(profile)
    return engine.run_blind_spot_pass(
        competitor_htmls=competitor_htmls,
        competitor_results=competitor_results,
        existing_tools=existing_tools,
    )


def _resolve_tax_bracket_and_entity_competitor_content(s_low: str) -> Optional[Dict[str, Any]]:
    """Resolves vertical-isolated statutory trap, checklist, pitfalls, and handoff content for Tax Brackets, TCJA, Capital Gains, and S-Corp models."""
    if not any(
        tok in s_low
        for tok in ("tax-bracket", "tax-rate", "tcja", "capital-gains", "s-corp", "1202", "qsbs", "amt", "niit")
    ):
        return None
    return {
        "trap_title": "Immediate TCJA Sunset and Marginal vs Effective Tax Rate Trap Alert (IRC Section 1(j) & 199A)",
        "trap_body": (
            "Under IRC Section 1(j), marginal tax brackets apply progressively to each taxable income tier after "
            "subtracting the standard or itemized deduction, not as a flat rate across gross income. Furthermore, "
            "taxpayers in high-tax states (California, New York, New Jersey, Connecticut) face the IRC Section 164(b)(6) "
            "SALT deduction cap, the 3.8% Net Investment Income Tax (IRC Section 1411), and IRC Section 199A QBI "
            "phase-outs that create hidden effective marginal rate spikes."
        ),
        "checklist_items": [
            "Subtract federal standard or itemized deductions and pre-tax 401(k)/HSA contributions from Adjusted Gross Income (AGI) before applying IRC Section 1(j) marginal rate tiers.",
            "Model state-specific income tax brackets alongside the federal IRC Section 164(b)(6) SALT cap and Pass-Through Entity Tax (PTET) election workarounds under IRS Notice 2020-75.",
            "Account for the 3.8% Net Investment Income Tax (IRC Section 1411) and 0.9% Additional Medicare Tax above statutory MAGI thresholds ($200,000 single / $250,000 married filing jointly).",
            "Verify IRC Section 199A Qualified Business Income (QBI) deduction phase-out ranges and W-2 wage or UBIA limitations for pass-through entities.",
        ],
        "pitfalls": [
            (
                "Applying the top marginal tax bracket percentage as a flat rate across total gross income",
                "Overstates federal and state tax liability by ignoring progressive bracket tiers and standard deductions",
                "Compute tax liability piecewise across each statutory IRC Section 1(j) bracket after deductions",
            ),
            (
                "Ignoring state non-conformity and SALT cap interaction in California, New York, Connecticut, or New Jersey",
                "Underestimates combined federal-plus-state effective marginal tax rate by 500 to 1,330 basis points",
                "Model state-level PTET elections (IRS Notice 2020-75) and combined federal/state marginal tax schedules",
            ),
            (
                "Realizing long-term capital gains without checking ordinary income bracket stacking and IRC Section 1411 NIIT",
                "Pushes capital gains across the 15%-to-20% threshold and triggers the 3.8% Net Investment Income Tax surtax",
                "Coordinate capital gain harvesting and Section 1031/installment deferrals against total MAGI thresholds",
            ),
        ],
        "handoff_title": "CPA, Tax Strategy & Payroll Compliance Vetting Checklist",
        "handoff_items": [
            "Verify automated multi-state withholding, quarterly Form 1040-ES safe-harbor calculation (100%/110% prior-year tax under IRC Section 6654), and PTET election support.",
            "Confirm S-Corp reasonable compensation benchmarking and W-2/K-1 payroll split integration for FICA and Section 199A optimization.",
            "Check year-end tax-loss harvesting, capital gains bracket stacking, and state residency domicile audit documentation.",
        ],
    }


PROFITHELM_US_STATES: Tuple[str, ...] = (
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut",
    "delaware", "district-of-columbia", "florida", "georgia", "hawaii", "idaho", "illinois",
    "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine", "maryland",
    "massachusetts", "michigan", "minnesota", "mississippi", "missouri", "montana",
    "nebraska", "nevada", "new-hampshire", "new-jersey", "new-mexico", "new-york",
    "north-carolina", "north-dakota", "ohio", "oklahoma", "oregon", "pennsylvania",
    "rhode-island", "south-carolina", "south-dakota", "tennessee", "texas", "utah",
    "vermont", "virginia", "washington", "west-virginia", "wisconsin", "wyoming",
)

PROFITHELM_SECTION_179_VEHICLES: Tuple[Tuple[str, str], ...] = (
    ("bmw-x5-xdrive40i", "BMW X5 xDrive40i Section 179 & Bonus Depreciation Calculator"),
    ("cadillac-escalade-esv", "Cadillac Escalade ESV Heavy SUV Section 179 Calculator"),
    ("chevrolet-express-cargo", "Chevrolet Express Cargo Van Section 179 Deduction Calculator"),
    ("chevrolet-silverado-1500", "Chevrolet Silverado 1500 Section 179 Tax Deduction Calculator"),
    ("chevrolet-silverado-2500hd", "Chevrolet Silverado 2500HD Heavy Truck Section 179 Calculator"),
    ("chevrolet-suburban-commercial", "Chevrolet Suburban Commercial Fleet Section 179 Calculator"),
    ("ford-f150-lightning", "Ford F-150 Lightning EV Truck Section 179 Deduction Calculator"),
    ("ford-f150-supercrew", "Ford F-150 SuperCrew Section 179 & Bonus Depreciation Calculator"),
    ("ford-super-duty-f250", "Ford Super Duty F-250 100% Section 179 Write-Off Calculator"),
    ("ford-transit-cargo-van", "Ford Transit Cargo Van Section 179 Commercial Write-Off Calculator"),
    ("gmc-sierra-1500", "GMC Sierra 1500 Section 179 & MACRS Depreciation Calculator"),
    ("gmc-sierra-2500hd", "GMC Sierra 2500HD Heavy Duty Section 179 Deduction Calculator"),
    ("gmc-yukon-xl", "GMC Yukon XL Heavy SUV Section 179 & Bonus Depreciation Calculator"),
    ("land-rover-defender-110", "Land Rover Defender 110 6,000+ lb GVWR Section 179 Calculator"),
    ("lincoln-navigator-l", "Lincoln Navigator L Heavy SUV Section 179 Tax Write-Off Calculator"),
    ("mercedes-benz-esprinter", "Mercedes-Benz eSprinter Electric Cargo Van Section 179 Calculator"),
    ("mercedes-benz-sprinter-2500", "Mercedes-Benz Sprinter 2500 Cargo Van Section 179 Calculator"),
    ("nissan-titan-crew-cab", "Nissan Titan Crew Cab Section 179 Commercial Truck Calculator"),
    ("porsche-cayenne", "Porsche Cayenne 6,000+ lb GVWR Section 179 Tax Deduction Calculator"),
    ("ram-1500-crew-cab", "Ram 1500 Crew Cab Section 179 & Bonus Depreciation Calculator"),
    ("ram-2500-heavy-duty", "Ram 2500 Heavy Duty 100% Section 179 Deduction Calculator"),
    ("ram-promaster-cargo-van", "Ram ProMaster Cargo Van Section 179 Commercial Write-Off Calculator"),
    ("rivian-r1t", "Rivian R1T Electric Truck Section 179 & Bonus Depreciation Calculator"),
    ("tesla-cybertruck", "Tesla Cybertruck 6,000+ lb GVWR Section 179 Write-Off Calculator"),
    ("toyota-tundra-crewmax", "Toyota Tundra CrewMax Section 179 & MACRS Depreciation Calculator"),
)


def _resolve_profithelm_tier_clusters(s_low: str) -> List[Tuple[str, List[Tuple[str, str]]]]:
    """Builds context-aware 3-tier topic cluster links covering all 22 root calculators plus state and vehicle rings."""
    tier_1 = [
        ("irs-2027-tax-brackets", "IRS 2027 Statutory Tax Brackets & Marginal Rate Calculator"),
        ("section-179-calculator", "Section 179 Equipment Expense & Phaseout Calculator"),
        ("section-1031-calculator", "Section 1031 Like-Kind Exchange & Boot Tax Calculator"),
        ("s-corp-reasonable-salary-tax-calculator", "S-Corp Reasonable Salary & FICA Tax Savings Calculator"),
        ("tcja-sunset-capital-gains", "TCJA Sunset & Long-Term Capital Gains Tax Calculator"),
        ("crypto-tax-calculator", "Digital Asset Form 8949 & Rev. Proc. 2024-28 Tax Calculator"),
        ("treasury-yield-calculator", "Treasury Bill vs HYSA Tax-Equivalent Yield Calculator (31 U.S.C. 3124)"),
    ]
    tier_2 = [
        ("equipment-lease-vs-buy-section-179-calculator", "Equipment Lease vs Buy Section 179 Cash Flow Matrix"),
        ("equipment-lease-tax-deduction", "Equipment Lease Tax Deduction & Operating vs Capital Lease Calculator"),
        ("invoice-factoring-vs-business-line-of-credit-calculator", "Invoice Factoring vs Business Line of Credit APR Matrix"),
        ("saas-runway-calculator", "SaaS Cash Runway, Net Burn & Zero Cash Date Calculator"),
        ("saas-burn-multiple-benchmarks-2026", "SaaS Burn Multiple & Capital Efficiency Benchmarks Calculator"),
        ("prediction-market-odds", "Prediction Market Implied Probability & Fee Drag Matrix"),
        ("prediction-market-tax", "Prediction Market Section 1256 vs Ordinary Income Tax Calculator"),
        ("r-and-d-tax-credit-section-174-amortization-calculator", "IRC Section 41 R&D Tax Credit & Section 174 Amortization Calculator"),
    ]
    tier_3: List[Tuple[str, str]] = []
    if "/" in s_low:
        parts = [p for p in s_low.split("/") if p]
        if len(parts) == 2 and parts[0] in ("irs-2027-tax-brackets", "section-1031-calculator"):
            state_slug = parts[1]
            state_label = state_slug.replace("-", " ").title()
            tier_3.append(
                (
                    f"irs-2027-tax-brackets/{state_slug}",
                    f"{state_label} 2027 Tax Brackets & Marginal Income Tax Rate Calculator",
                )
            )
            tier_3.append(
                (
                    f"section-1031-calculator/{state_slug}",
                    f"{state_label} Section 1031 Like-Kind Exchange & Boot Tax Calculator",
                )
            )
            if state_slug in PROFITHELM_US_STATES:
                st_idx = PROFITHELM_US_STATES.index(state_slug)
                n_states = len(PROFITHELM_US_STATES)
                for offset in (-2, -1, 1, 2):
                    adj_state = PROFITHELM_US_STATES[(st_idx + offset) % n_states]
                    adj_label = adj_state.replace("-", " ").title()
                    if parts[0] == "irs-2027-tax-brackets":
                        tier_3.append(
                            (
                                f"irs-2027-tax-brackets/{adj_state}",
                                f"{adj_label} 2027 Tax Brackets & Marginal Income Tax Rate Calculator",
                            )
                        )
                    else:
                        tier_3.append(
                            (
                                f"section-1031-calculator/{adj_state}",
                                f"{adj_label} Section 1031 Like-Kind Exchange & Boot Tax Calculator",
                            )
                        )
        elif len(parts) == 2 and parts[0] == "section-179-calculator":
            veh_slug = parts[1]
            veh_map = dict(PROFITHELM_SECTION_179_VEHICLES)
            veh_keys = [k for k, _ in PROFITHELM_SECTION_179_VEHICLES]
            veh_label = veh_map.get(
                veh_slug,
                f"{veh_slug.replace('-', ' ').title()} Section 179 & Bonus Depreciation Calculator",
            )
            tier_3.append((f"section-179-calculator/{veh_slug}", veh_label))
            if veh_slug in veh_keys:
                v_idx = veh_keys.index(veh_slug)
                n_vehs = len(veh_keys)
                for offset in (-3, -2, -1, 1, 2, 3):
                    adj_v = veh_keys[(v_idx + offset) % n_vehs]
                    tier_3.append((f"section-179-calculator/{adj_v}", veh_map[adj_v]))
    striking_state_and_asset_spokes = [
        ("irs-2027-tax-brackets/california", "California 2027 Tax Brackets & Marginal Tax Rate Calculator"),
        ("irs-2027-tax-brackets/connecticut", "Connecticut 2027 Tax Brackets & Marginal Tax Rate Calculator"),
        ("irs-2027-tax-brackets/maine", "Maine 2027 Tax Brackets & Marginal Tax Rate Calculator"),
        ("irs-2027-tax-brackets/new-jersey", "New Jersey 2027 Tax Brackets & Marginal Tax Rate Calculator"),
        ("irs-2027-tax-brackets/new-york", "New York 2027 Tax Brackets & Marginal Tax Rate Calculator"),
        ("section-179-calculator/gmc-yukon-xl", "GMC Yukon XL Heavy SUV Section 179 & Bonus Depreciation Calculator"),
        ("commercial-heavy-vehicle-section-179-weight-calculator", "Commercial Heavy Vehicle 6,000+ lbs GVWR Section 179 Calculator"),
        ("section-179-vehicle-equipment-deduction", "Section 179 Commercial Vehicle & Equipment Deduction Calculator"),
        ("medical-and-dental-equipment-section-179-roi-calculator", "Medical & Dental Equipment Section 179 Tax ROI Calculator"),
        ("crypto-tax-form-1099-da-mandatory-reporting", "IRS Form 1099-DA Digital Asset Broker Basis Reconciliation Calculator"),
        ("workers-comp-and-payroll-burden-calculator", "Workers' Compensation & Employer Payroll Tax Burden Calculator"),
        ("contractor-surety-bond-cost-calculator", "Contractor License & Commercial Surety Bond Cost Calculator"),
        ("section-301-tariff-landed-cost-calculator", "Section 301 Tariff Duty & Import Landed Cost Calculator"),
    ]
    existing_slugs = {slug_key for slug_key, _ in tier_3}
    for sp_slug, sp_label in striking_state_and_asset_spokes:
        if sp_slug not in existing_slugs:
            tier_3.append((sp_slug, sp_label))
            existing_slugs.add(sp_slug)
    return [
        ("Tier 1: Core Statutory Tax & Capital Pillar Hubs", tier_1),
        ("Tier 2: Comparative Financing, Entity & Arbitrage Matrices", tier_2),
        ("Tier 3: Specialized Compliance, Jurisdiction & Asset Spokes", tier_3),
    ]


def _resolve_vertical_competitor_content(
    slug: str,
    property_id: str,
    statutory_authority: str,
    canonical_base: str,
) -> Dict[str, Any]:
    """
    Resolves domain-isolated, vertical-specific statutory edge-case traps,
    Beyond-the-Calculator compliance checklists, pitfall tables, 3-tier topic
    clusters, and commercial/statutory handoff vetting checklists.
    Zero em-dashes. Zero en-dashes. Zero spaced hyphens.
    """
    s_low = slug.lower()
    is_prexvo = property_id.strip().lower() == "prexvo"
    base_url = canonical_base.rstrip("/")

    if is_prexvo:
        restricted_ps = is_restricted_public_service_slug(slug)
        is_refi = any(tok in s_low for tok in ("refinance", "refinancing"))
        if restricted_ps:
            trap_title = "Immediate Title IV Statutory Eligibility and Buyback Trap Alert (34 CFR 685.219)"
            trap_body = (
                "Under 34 CFR 685.219, Public Service Loan Forgiveness requires strictly 120 qualifying "
                "monthly payments while employed full-time by an eligible governmental or 501(c)(3) non-profit "
                "organization. Consolidating Direct Loans after submitting a PSLF hold-harmless buyback request "
                "or converting federal balances into private credit permanently voids qualifying buyback months."
            )
            checklist_items = [
                "Annual Employment Certification Form (ECF) signature verification by an authorized employer official under 34 CFR 685.219(c).",
                "Direct Loan program status audit confirming any legacy FFEL or Perkins loans were consolidated into Direct Loans prior to qualifying service.",
                "NSLDS payment counter reconciliation verifying all 120 qualifying monthly payments occurred during full-time (>=30 hours weekly) public service.",
                "Formal PSLF Buyback eligibility check confirming 120 months of approved employment exist before requesting lump-sum hold-harmless assessment.",
            ]
            pitfalls = [
                (
                    "Consolidating Direct Loans during pending PSLF Buyback review",
                    "Creates a new Direct Consolidation substrate that erases pre-consolidation buyback month eligibility",
                    "Complete PSLF Buyback settlement and receive official discharge determination before any loan consolidation",
                ),
                (
                    "Employer 501(c)(3) revocation or non-qualifying contractor status",
                    "Disqualifies monthly payments made while billed as a 1099 independent contractor rather than a W-2 employee",
                    "Verify EIN eligibility in the official Federal Student Aid PSLF Employer Search database annually",
                ),
                (
                    "Relying on non-qualifying general forbearance without hold-harmless buyback",
                    "Months in discretionary forbearance do not count toward the 120 qualifying monthly payments without buyback",
                    "Track eligible deferment or forbearance periods and submit a formal 34 CFR 685.219(g) buyback request at month 120",
                ),
            ]
            handoff_title = "Non-Commercial Title IV Statutory Verification Protocol"
            handoff_items = [
                "Verify qualifying employer EIN status directly in the official StudentAid.gov PSLF Help Tool.",
                "Download your raw NSLDS loan-level text file to audit cumulative qualifying payment counts across servicers.",
                "Retain signed W-2 wage statements and employer certifications for all 120 qualifying monthly payment periods.",
            ]
        elif is_refi:
            trap_title = "Immediate Title IV Federal Protection Forfeiture Trap Alert (34 CFR Part 685)"
            trap_body = (
                "Refinancing federal student loans into a private credit agreement is irreversible: borrowers "
                "permanently waive federal protections, including Income-Based Repayment (IBR), the Repayment "
                "Assistance Plan (RAP), federal unpaid interest subsidies, and 120-payment Public Service Loan Forgiveness."
            )
            checklist_items = [
                "Confirm zero remaining eligibility or intent for 120-payment Public Service Loan Forgiveness (34 CFR 685.219) before private conversion.",
                "Verify emergency cash reserves cover at least 6 months of fixed private loan obligations since private contracts lack statutory IDR hardship caps.",
                "Audit soft-pull rate pre-qualification disclosures under Truth in Lending Act (TILA) Regulation Z (12 CFR Part 1026) before authorizing a hard inquiry.",
                "Compare fixed vs variable APR amortization schedules alongside autopay discount permanence and cosigner release clauses.",
            ]
            pitfalls = [
                (
                    "Refinancing Direct Loans while employed at a 501(c)(3) hospital or public agency",
                    "Permanently waives federal protections and forfeits tax-free 120-payment PSLF principal discharge",
                    "Isolate only private student loans for refinancing while retaining federal Direct Loans in Title IV IDR plans",
                ),
                (
                    "Comparing nominal interest rate reduction without modeling lost RAP unpaid interest subsidies",
                    "Overstates net savings when federal unpaid interest waivers reduce effective Title IV borrowing cost",
                    "Compare lifetime out-of-pocket cash outflow across both Title IV RAP/IBR and private amortization schedules",
                ),
                (
                    "Triggering multiple uncoordinated hard credit inquiries across private lenders",
                    "Can depress FICO credit scores if applications span outside the bureau rate-shopping window",
                    "Use soft-pull pre-qualification first and batch final applications within a single 14-day underwriting window",
                ),
            ]
            handoff_title = "Vetted Private Refinance Underwriting Checklist (TILA Reg Z)"
            handoff_items = [
                "Confirm 100% soft-credit-pull rate check with zero impact on your FICO score before formal underwriting.",
                "Verify fixed APR terms, zero origination or prepayment fees, and documented disability/death discharge policies.",
                "Review mandatory Title IV forfeiture disclosure confirming refinancing federal student loans permanently waives federal protections.",
            ]
        else:
            trap_title = "Immediate AGI Filing Status and Interest Capitalization Trap Alert (34 CFR 685.209)"
            trap_body = (
                "Under 34 CFR 685.209 and OBBBA Title VIII Subtitle B, Married Filing Jointly (MFJ) pools both "
                "spouses' Adjusted Gross Income when computing RAP and IBR discretionary payments, whereas Married "
                "Filing Separately (MFS) isolates individual borrower AGI. Exiting Income-Based Repayment (IBR) "
                "also triggers statutory capitalization of accrued unpaid interest onto principal."
            )
            checklist_items = [
                "Model Married Filing Jointly (MFJ) vs Married Filing Separately (MFS) tax liability delta against annual Title IV repayment savings.",
                "Verify whether your Direct Loans meet the July 1, 2014 New Borrower threshold (10% vs 15% discretionary income under 34 CFR 685.209).",
                "Confirm annual IRS Data Retrieval Tool (DRT) income recertification deadlines to prevent administrative payment spikes.",
                "Audit accrued unpaid interest balances before switching out of IBR, as statutory exit rules capitalize unpaid interest into principal.",
            ]
            pitfalls = [
                (
                    "Filing joint tax returns (MFJ) when both spouses have disparate income-to-debt ratios",
                    "Combines household AGI and can double or triple monthly RAP/IBR required payments",
                    "Run side-by-side MFS vs MFJ tax and repayment simulations prior to filing annual federal returns",
                ),
                (
                    "Switching out of statutory IBR into another repayment plan with accrued unpaid interest",
                    "Triggers mandatory statutory interest capitalization under 20 U.S.C. 1098e(b)(3), permanently increasing principal",
                    "Evaluate accrued interest balance impact before executing a formal plan migration away from IBR",
                ),
                (
                    "Missing annual IDR income recertification deadline with loan servicer",
                    "Reverts monthly billing to the 10-year Standard Repayment amount and can trigger interest capitalization",
                    "Enable automatic IRS tax data consent or submit recertification documentation 45 days before anniversary date",
                ),
            ]
            handoff_title = "Title IV Repayment Execution and Verification Checklist"
            handoff_items = [
                "Cross-check loan origination dates in StudentAid.gov to confirm pre-2014 vs post-2014 IBR statutory tier.",
                "Compare total 240-to-360-month cumulative repayment cost including potential tax treatment of forgiven balances.",
                "Verify family size and state of residence against current HHS Federal Poverty Guidelines (42 U.S.C. 9902(2)).",
            ]

        tier_clusters = [
            (
                "Tier 1: Core Title IV Statutory Pillar Models",
                [
                    ("student-loan-repayment-calculator", "Income-Based & Income-Driven Student Loan Repayment Calculator (Title IV IBR & RAP)"),
                    ("rap-vs-ibr-calculator", "Repayment Assistance Plan (RAP) vs Income-Based Repayment (IBR) Calculator"),
                    ("rap-payment-calculator", "Repayment Assistance Plan (RAP) Monthly Payment Calculator"),
                    ("tiered-standard-calculator", "Tiered Standard Repayment Plan Amortization Calculator"),
                ],
            ),
            (
                "Tier 2: Forgiveness, Buyback and Litigation Transition Matrices",
                [
                    ("pslf-qualifying-payment-simulator", "PSLF 120 Qualifying Payments Verification Simulator"),
                    ("save-plan-litigation-transition", "SAVE Plan Forbearance to IBR/RAP Transition Calculator"),
                    ("paye-sunset-calculator", "PAYE Sunset & Statutory Repayment Plan Transition Calculator"),
                    ("ibr-hardship-cap-calculator", "IBR Partial Financial Hardship Cap Calculator"),
                ],
            ),
            (
                "Tier 3: Filing Status, Consolidation and Specialty Borrower Spokes",
                [
                    ("married-filing-separately-student-loan-calculator", "Married Filing Separately (MFS) vs Joint Income-Driven Repayment Tax Model"),
                    ("icr-repayment-calculator", "Income-Contingent Repayment (ICR) & Parent PLUS Statutory Calculator"),
                    ("parent-plus-double-consolidation", "Parent PLUS Double Consolidation Statutory Deadlines Model"),
                    ("grad-plus-borrowing-cap-calculator", "Grad PLUS Sunset and Borrowing Cap Calculator"),
                ],
            ),
        ]
    else:
        # ProfitHelm vertical resolution
        tax_bracket_ctx = _resolve_tax_bracket_and_entity_competitor_content(s_low)
        if tax_bracket_ctx is not None:
            trap_title = tax_bracket_ctx["trap_title"]
            trap_body = tax_bracket_ctx["trap_body"]
            checklist_items = tax_bracket_ctx["checklist_items"]
            pitfalls = tax_bracket_ctx["pitfalls"]
            handoff_title = tax_bracket_ctx["handoff_title"]
            handoff_items = tax_bracket_ctx["handoff_items"]
        elif any(tok in s_low for tok in ("1031", "like-kind", "exchange", "ftb-3840")):
            trap_title = "Immediate Statutory Deadline and Mortgage Boot Trap Alert (IRC Section 1031(a)(3)(B)(ii))"
            trap_body = (
                "Under IRC Section 1031(a)(3)(B)(ii), your exchange completion deadline is the EARLIER of 180 "
                "calendar days after closing relinquished property OR the due date (including extensions) of your "
                "federal income tax return for the year of sale. For Q4 closings between October 18 and December 31, "
                "you must file IRS Form 4868 (or Form 7004) before April 15 to preserve the full 180-day window. "
                "Additionally, any net debt reduction (mortgage boot) triggers immediate tax recognition unless offset "
                "by equal or greater replacement debt or fresh cash equity."
            )
            checklist_items = [
                "Execute written Qualified Intermediary (QI) Exchange Agreement and Assignment BEFORE closing relinquished property under Treas. Reg. 1.1031(k)-1(g)(4).",
                "Screen intermediary, escrow, and title agents against Disqualified Person rules under Treas. Reg. 1.1031(k)-1(k) (excluding attorneys, CPAs, or brokers who acted as your agent within 2 years).",
                "Deliver signed written identification of replacement property by midnight on Calendar Day 45 under the Three-Property Rule or 200% Fair Market Value Rule.",
                "Prepare IRS Form 8824 for the year of sale and track mandatory state clawback reporting (such as California FTB Form 3840 or Oregon Form OR-24) annually.",
            ]
            pitfalls = [
                (
                    "Closing relinquished property in Q4 (Nov/Dec) and filing April 15 tax return without extension",
                    "Compresses the 180-day exchange window under IRC Section 1031(a)(3)(B)(ii) and disqualifies post-filing acquisitions",
                    "Always file IRS Form 4868 (individuals) or Form 7004 (entities) before filing the return for a Q4 exchange",
                ),
                (
                    "Acquiring equal replacement value using more cash and less debt than relinquished property",
                    "Taking less replacement debt without adding equivalent cash equity creates taxable Mortgage Boot under Treas. Reg. 1.1031(b)-1(c)",
                    "Match or exceed both total net sales price AND total paid-off debt (or inject equivalent new cash equity at closing)",
                ),
                (
                    "Allowing escrow deposit or net sale proceeds to touch taxpayer's bank account",
                    "Triggers immediate constructive receipt under Treas. Reg. 1.1031(k)-1(f) and voids tax deferral across the entire gain",
                    "Route all sale proceeds and assignment addenda directly through a bonded Qualified Intermediary segregated escrow account",
                ),
            ]
            handoff_title = "Qualified Intermediary (QI) Provider Vetting Checklist"
            handoff_items = [
                "Verify fidelity bond coverage, Errors & Omissions insurance, and segregated qualified escrow/trust account structure.",
                "Confirm pre-closing exchange assignment documentation under Treas. Reg. 1.1031(k)-1(g)(4) before escrow closes.",
                "Audit multi-state clawback compliance support (CA FTB Form 3840 / OR-24) and reverse/improvement EAT structuring capability.",
            ]
        elif any(tok in s_low for tok in ("crypto", "staking", "8949", "1099-da", "wash")):
            trap_title = "Immediate Wallet-by-Wallet Basis and Form 1099-DA Trap Alert (Rev. Proc. 2024-28)"
            trap_body = (
                "Under IRS Rev. Proc. 2024-28 and Treasury final digital asset broker regulations, universal "
                "cross-wallet tax lot pooling is prohibited: taxpayers must maintain wallet-by-wallet or account-by-account "
                "cost-basis allocation and reconcile custodial broker gross proceeds reported on IRS Form 1099-DA "
                "against Specific Identification (HIFO/FIFO) records on IRS Form 8949."
            )
            checklist_items = [
                "Document wallet-by-wallet cost-basis allocation election under IRS Rev. Proc. 2024-28 prior to executing digital asset disposals.",
                "Record contemporaneous Fair Market Value (FMV) at the exact timestamp staking rewards achieve dominion and control under Rev. Rul. 2023-14.",
                "Reconcile custodial exchange IRS Form 1099-DA gross proceeds against non-custodial transfer logs to prevent zero-basis double taxation.",
                "Separate CFTC-regulated Section 1256 contracts (Form 6781) from spot digital asset capital gains and losses (Form 8949 / Schedule D).",
            ]
            pitfalls = [
                (
                    "Applying universal HIFO lot selection across multiple unlinked hardware wallets and exchanges",
                    "Violates Rev. Proc. 2024-28 account-by-account basis tracking rules and risks IRS FIFO recharacterization",
                    "Maintain segregated per-wallet tax lot ledgers and specify lot IDs before or at the time of each transfer",
                ),
                (
                    "Omitting self-custody transfer cost basis when importing Form 1099-DA from a centralized broker",
                    "Causes broker-reported gross proceeds to be taxed at 100% gain with $0 reported cost basis",
                    "Join on-chain transfer hashes with historical acquisition lots to substantiate Form 8949 Column (e) basis",
                ),
                (
                    "Deferring staking reward income recognition until tokens are sold for fiat currency",
                    "Understates ordinary income under Rev. Rul. 2023-14 and triggers accuracy-related penalties under IRC Section 6662",
                    "Report validator/staking rewards as ordinary income at receipt FMV and establish that FMV as the token's cost basis",
                ),
            ]
            handoff_title = "Digital Asset Tax Subledger Vetting Checklist"
            handoff_items = [
                "Confirm native support for IRS Rev. Proc. 2024-28 wallet-by-wallet Specific Identification (HIFO/FIFO) lot accounting.",
                "Verify read-only API key security (SOC 2 Type II) and automated IRS Form 8949, Schedule D, and Form 1099-DA reconciliation.",
                "Check automated detection of DeFi liquidity pool wraps, bridges, and Rev. Rul. 2023-14 staking reward timestamps.",
            ]
        elif any(tok in s_low for tok in ("prediction", "kalshi", "polymarket", "kelly", "implied", "arbitrage", "odds", "vig", "break-even")):
            trap_title = "Immediate Quadratic Fee Drag and Section 1256 Tax Bifurcation Trap Alert"
            trap_body = (
                "Event contract net expected value is compressed by exchange fee schedules that peak at 50-cent "
                "implied probability (Kalshi quadratic fee formula 0.07 * P * (1 minus P) = $0.0175 per contract at P=0.50) "
                "and by tax regime bifurcation between CFTC-regulated Designated Contract Markets (IRC Section 1256 "
                "60/40 capital treatment) and non-DCM venues subject to IRC Section 165(d) loss deduction limits."
            )
            checklist_items = [
                "Deduct exact round-trip maker/taker exchange fees and bid-ask spread slippage before computing Kelly bankroll sizing.",
                "Apply Fractional Kelly (0.25x to 0.50x) multipliers to protect bankroll against parameter estimation variance and correlated event resolution.",
                "Calculate time-to-settlement annualized capital lockup cost against risk-free 3-month U.S. Treasury yields (FRED DTB3).",
                "Verify venue regulatory classification (CFTC DCM under 17 CFR Part 40 vs offshore/non-DCM) for accurate Form 6781 vs Schedule 1 reporting.",
            ]
            pitfalls = [
                (
                    "Sizing binary event positions using full (1.0x) Kelly on unadjusted mid-market probabilities",
                    "Exposes portfolio to severe drawdown risk when true win probability is overestimated by even 200 basis points",
                    "Subtract round-trip fee drag from edge first and cap position sizing at Half-Kelly (0.50x) or Quarter-Kelly (0.25x)",
                ),
                (
                    "Executing cross-platform arbitrage between two venues with divergent oracle resolution rules",
                    "Creates resolution basis risk where both legs settle unfavorably due to differing cutoff timestamps or data sources",
                    "Audit exact contract rulebook settlement criteria and resolution sources on both venues before locking arbitrage capital",
                ),
                (
                    "Netting non-DCM wagering losses against unrelated capital gains without itemizing",
                    "IRC Section 165(d) restricts wagering loss deductions to the extent of wagering gains",
                    "Segregate CFTC-regulated Section 1256 exchange contracts from non-DCM event transactions in tax subledgers",
                ),
            ]
            handoff_title = "Quantitative Execution & Tax Subledger Vetting Checklist"
            handoff_items = [
                "Verify CFTC Designated Contract Market (DCM) regulatory status and automated Form 1099 / Form 6781 tax statement exports.",
                "Audit maker vs taker fee schedules and API order-book depth across probability bands before deploying automated sizing.",
                "Confirm subledger compatibility for reconciling high-frequency binary contract settlements and wash/rollover positions.",
            ]
        else:
            trap_title = "Immediate Placed-in-Service Deadline and Recapture Trap Alert (IRC Section 179 & 168(k))"
            trap_body = (
                "Under IRC Section 179 and Treas. Reg. 1.179-4(e), qualifying equipment or software must be both "
                "purchased AND placed in operational readiness before midnight on December 31 of the tax year. "
                "Furthermore, if qualified business use drops to 50% or below during any subsequent MACRS recovery "
                "year, IRC Section 179(d)(10) triggers mandatory ordinary income recapture on IRS Form 4797."
            )
            checklist_items = [
                "Retain dated delivery receipts, installation logs, and operational commissioning records proving placed-in-service status by December 31.",
                "Verify total annual equipment additions against the IRC Section 179(b)(2) dollar-for-dollar investment phase-out threshold on IRS Form 4562.",
                "Confirm active trade or business taxable income limitation under IRC Section 179(b)(3) (including W-2 wages and S-Corp officer compensation).",
                "Cross-check state-level conformity (such as California state depreciation decoupling and bonus depreciation adjustments) before finalizing quarterly estimates.",
            ]
            pitfalls = [
                (
                    "Signing an equipment purchase contract and paying in December when delivery occurs in January",
                    "Disqualifies the asset from current-year Section 179 and 168(k) expensing under Treas. Reg. 1.179-4(e)",
                    "Require documented physical delivery and operational readiness prior to December 31 midnight cutoff",
                ),
                (
                    "Claiming full Section 179 deduction on a heavy SUV (6,000 to 14,000 lbs GVWR) without applying IRC 179(b)(5)",
                    "Exceeds the statutory heavy SUV Section 179 cap and triggers Form 4562 audit adjustments",
                    "Apply the statutory IRC Section 179(b)(5) SUV cap first, then apply IRC Section 168(k) bonus depreciation to remaining basis",
                ),
                (
                    "Allowing business-use percentage on listed property or vehicles to fall to 50% or below in Year 2-5",
                    "Triggers mandatory IRC Section 179(d)(10) and Section 280F excess depreciation recapture as ordinary income on Form 4797",
                    "Maintain contemporaneous mileage/usage logs substantiating strictly greater than 50% qualified business use every year",
                ),
            ]
            handoff_title = "Commercial Equipment & Tax Execution Vetting Checklist"
            handoff_items = [
                "Confirm non-tax capital lease ($1 Buyout or Equipment Finance Agreement) structure preserves 100% taxpayer title for IRC Section 179.",
                "Verify same-day underwriting approval and dealer funding cutoff dates to guarantee December 31 placed-in-service compliance.",
                "Review UCC-1 equipment-only lien terms, zero-prepayment-penalty clauses, and IRS Form 4562 asset classification schedules.",
            ]

        tier_clusters = _resolve_profithelm_tier_clusters(s_low)

    return {
        "trap_title": trap_title,
        "trap_body": trap_body,
        "checklist_items": checklist_items,
        "pitfalls": pitfalls,
        "handoff_title": handoff_title,
        "handoff_items": handoff_items,
        "tier_clusters": tier_clusters,
        "base_url": base_url,
        "statutory_authority": statutory_authority,
    }


def render_competitor_winning_pattern_blocks(
    slug: str,
    title: str,
    property_id: str,
    canonical_base: str,
    statutory_authority: str,
    economic_dataset: str,
) -> Dict[str, str]:
    """
    Renders the 4 winning competitor patterns in HTML for compile_high_effort_page
    and RetroReflectionEngine:
      1. Calculator Immediacy: instant_edge_case_trap_immediacy
      2. Authority Framing: statutory_compliance_framing (Beyond the Calculator + Pitfall Matrix)
      3. Topic Clustering: on_this_page_jump_nav + three_tier_topic_cluster_nav
      4. Commercial Handoffs: vetted_commercial_handoff_framing
    Zero em-dashes. Zero en-dashes. Zero spaced hyphens.
    """
    ctx = _resolve_vertical_competitor_content(
        slug=slug,
        property_id=property_id,
        statutory_authority=statutory_authority,
        canonical_base=canonical_base,
    )
    base_url = ctx["base_url"]

    on_this_page_html = (
        '    <nav class="on-this-page-nav card pseo-card" aria-label="On This Page" '
        'data-mechanic="on_this_page_jump_nav">\n'
        '      <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted, #475569); margin-bottom: 8px;">On This Page: Rapid Decision Navigation</div>\n'
        '      <div style="display: flex; flex-wrap: wrap; gap: 8px;">\n'
        '        <a href="#statutory-trap-alert" class="touch-target" style="display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; padding: 10px 14px; border-radius: 8px; background: var(--bg-elevated, #eff6ff); color: var(--accent, #1d4ed8); border: 1px solid var(--border-strong, #bfdbfe); text-decoration: none; font-size: 14px; font-weight: 600;">1. Statutory Deadline &amp; Edge-Case Trap</a>\n'
        '        <a href="#vetted-commercial-handoff" class="touch-target" style="display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; padding: 10px 14px; border-radius: 8px; background: var(--bg-elevated, #eff6ff); color: var(--accent, #1d4ed8); border: 1px solid var(--border-strong, #bfdbfe); text-decoration: none; font-size: 14px; font-weight: 600;">2. Provider Vetting Checklist</a>\n'
        '        <a href="#statutory-compliance-checklist" class="touch-target" style="display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; padding: 10px 14px; border-radius: 8px; background: var(--bg-elevated, #eff6ff); color: var(--accent, #1d4ed8); border: 1px solid var(--border-strong, #bfdbfe); text-decoration: none; font-size: 14px; font-weight: 600;">3. Beyond the Calculator Checklist</a>\n'
        '        <a href="#statutory-pitfalls-matrix" class="touch-target" style="display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; padding: 10px 14px; border-radius: 8px; background: var(--bg-elevated, #eff6ff); color: var(--accent, #1d4ed8); border: 1px solid var(--border-strong, #bfdbfe); text-decoration: none; font-size: 14px; font-weight: 600;">4. Common Statutory Pitfalls</a>\n'
        '        <a href="#topic-cluster-hub" class="touch-target" style="display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; padding: 10px 14px; border-radius: 8px; background: var(--bg-elevated, #eff6ff); color: var(--accent, #1d4ed8); border: 1px solid var(--border-strong, #bfdbfe); text-decoration: none; font-size: 14px; font-weight: 600;">5. 3-Tier Topic Cluster</a>\n'
        '      </div>\n'
        '    </nav>'
    )

    edge_case_trap_html = (
        f'    <aside id="statutory-trap-alert" class="statutory-edge-case-trap card pseo-card" '
        f'data-mechanic="instant_edge_case_trap_immediacy" '
        f'style="border-left: 4px solid #f59e0b; background: var(--bg-elevated, #eff6ff);">\n'
        f'      <div style="margin-top: 0; margin-bottom: 6px; font-size: 15px; font-weight: 700;">{ctx["trap_title"]}</div>\n'
        f'      <p style="margin: 0; font-size: 14px; line-height: 1.55;">{ctx["trap_body"]}</p>\n'
        f'    </aside>'
    )

    checklist_li = "\n".join(
        f'        <li style="margin-bottom: 8px;">{item}</li>'
        for item in ctx["checklist_items"]
    )
    pitfall_rows = "\n".join(
        f'            <tr>\n'
        f'              <td><strong>{issue}</strong></td>\n'
        f'              <td>{conseq}</td>\n'
        f'              <td>{prev}</td>\n'
        f'            </tr>'
        for issue, conseq, prev in ctx["pitfalls"]
    )
    statutory_compliance_html = (
        f'    <section id="statutory-compliance-checklist" class="statutory-compliance-section card pseo-card" '
        f'data-mechanic="statutory_compliance_framing">\n'
        f'      <h2>Beyond the Calculator: Statutory Compliance and Procedural Verification</h2>\n'
        f'      <p>Deterministic arithmetic under <strong>{statutory_authority}</strong> computes your baseline quantitative exposure, but statutory qualification depends on strict procedural execution that no calculator can verify automatically:</p>\n'
        f'      <ul style="padding-left: 20px; margin-top: 12px; margin-bottom: 20px;">\n'
        f'{checklist_li}\n'
        f'      </ul>\n'
        f'      <div id="statutory-pitfalls-matrix" style="font-size: 16px; font-weight: 700; margin-top: 18px; margin-bottom: 10px;">Common Statutory Pitfalls: Issue to Prevention Matrix</div>\n'
        f'      <div class="table-wrap pseo-table-wrap">\n'
        f'        <table class="statutory-pitfalls-table" data-statutory-source="{statutory_authority}" data-economic-source="{economic_dataset}">\n'
        f'          <thead>\n'
        f'            <tr>\n'
        f'              <th scope="col">Statutory Pitfall or Edge Case</th>\n'
        f'              <th scope="col">Regulatory Consequence</th>\n'
        f'              <th scope="col">Mandatory Prevention Protocol</th>\n'
        f'            </tr>\n'
        f'          </thead>\n'
        f'          <tbody>\n'
        f'{pitfall_rows}\n'
        f'          </tbody>\n'
        f'        </table>\n'
        f'      </div>\n'
        f'    </section>'
    )

    tier_blocks: List[str] = []
    for tier_heading, tier_links in ctx["tier_clusters"]:
        links_li: List[str] = []
        for t_slug, t_label in tier_links:
            if t_slug == slug:
                continue
            links_li.append(
                f'          <li style="margin-bottom: 8px;">\n'
                f'            <a href="{base_url}/tools/{t_slug}/" class="touch-target cluster-link" '
                f'style="display: flex; align-items: center; min-height: 44px; min-width: 44px; padding: 10px 14px; border-radius: 8px; background: var(--bg-elevated, #eff6ff); color: var(--accent, #1d4ed8); border: 1px solid var(--border-strong, #bfdbfe); text-decoration: none; font-size: 14px; font-weight: 600;">{t_label}</a>\n'
                f'          </li>'
            )
        if links_li:
            joined_li = "\n".join(links_li)
            tier_blocks.append(
                f'      <div class="topic-cluster-tier" style="margin-bottom: 16px;">\n'
                f'        <div style="font-size: 15px; font-weight: 700; margin-bottom: 8px;">{tier_heading}</div>\n'
                f'        <ul style="list-style: none; padding: 0; margin: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 10px;">\n'
                f'{joined_li}\n'
                f'        </ul>\n'
                f'      </div>'
            )
    joined_tiers = "\n".join(tier_blocks)
    three_tier_cluster_html = (
        f'    <section id="topic-cluster-hub" class="three-tier-cluster-section card pseo-card" '
        f'data-mechanic="three_tier_topic_cluster_nav">\n'
        f'      <h2>Connected Statutory Topic Cluster and Decision Architecture</h2>\n'
        f'      <p style="font-size: 14px; color: var(--text-muted, #475569); margin-bottom: 14px;">Navigate connected pillar models, side-by-side comparative matrices, and jurisdiction/entity compliance calculators:</p>\n'
        f'{joined_tiers}\n'
        f'    </section>'
    )

    handoff_li = "\n".join(
        f'        <li style="margin-bottom: 6px; font-size: 13px;">{h_item}</li>'
        for h_item in ctx["handoff_items"]
    )
    vetted_handoff_html = (
        f'    <section id="vetted-commercial-handoff" class="commercial-handoff-vetting card pseo-card" '
        f'data-mechanic="vetted_commercial_handoff_framing">\n'
        f'      <div style="font-size: 16px; font-weight: 700; margin-top: 0; margin-bottom: 8px;">{ctx["handoff_title"]}</div>\n'
        f'      <ul style="padding-left: 18px; margin: 0;">\n'
        f'{handoff_li}\n'
        f'      </ul>\n'
        f'    </section>'
    )

    return {
        "on_this_page_nav_html": on_this_page_html,
        "edge_case_trap_html": edge_case_trap_html,
        "statutory_compliance_html": statutory_compliance_html,
        "three_tier_cluster_html": three_tier_cluster_html,
        "vetted_handoff_html": vetted_handoff_html,
    }


__all__ = [
    "INTERACTIVE_PATTERNS",
    "CLICK_MAGNET_PATTERNS",
    "CONVERSION_HOOK_PATTERNS",
    "SUPPORTED_SEARCH_ENGINES",
    "WINNING_COMPETITOR_MECHANICS",
    "TARGET_QUERY_BENCHMARKS",
    "GapCandidateSpec",
    "MultiEngineQueryBenchmark",
    "CompetitorGapEngine",
    "benchmark_multi_engine_rankings",
    "benchmark_all_properties",
    "run_blind_spot_pass",
    "render_competitor_winning_pattern_blocks",
]



