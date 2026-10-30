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
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from pseofactory.affiliates import (
    GAINHELM_DISCLOSURES,
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

    def __init__(
        self,
        tenant_profile: Optional[Union[TenantTruthProfile, str]] = None,
        *,
        tenant_id: Optional[str] = None,
    ):
        self.fact_store = TenantFactStore.get_instance()
        if isinstance(tenant_profile, TenantTruthProfile):
            self.tenant_profile = tenant_profile
            self.tenant_id = str(tenant_profile.tenant_id).lower().strip()
        else:
            eff_id = str(tenant_id or tenant_profile or "profithelm").lower().strip()
            self.tenant_profile = self.fact_store.get_profile(eff_id)
            self.tenant_id = str(self.tenant_profile.tenant_id).lower().strip()
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

            raw_dom = str(item.get("raw_html", "") or item.get("dom_snapshot", "") or "")
            raw_js = str(item.get("raw_js", "") or "")
            if raw_dom.strip():
                dom_diff = diff_competitor_dom_structure(
                    competitor_html=raw_dom,
                    tenant_html=str((existing_tool or {}).get("raw_html", "") or ""),
                    competitor_js=raw_js,
                    tenant_id=self.tenant_id,
                    target_slug=str((existing_tool or {}).get("slug", "") or ""),
                    query=clean_query,
                )
                for wedge in dom_diff.get("competitor_wedges_to_absorb", []):
                    if isinstance(wedge, str) and wedge.strip():
                        comp_interactive.add(_normalize_feature_name(wedge))

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
        combined_q = f"{clean_query.lower()} {base_slug}"

        if self.tenant_id == "prexvo":
            default_category = "Student Loan Repayment"
            restricted_ps = is_restricted_public_service_slug(base_slug, clean_query)
            affiliates = [] if restricted_ps else ["splash_financial", "sofi"]
            if "rap" in combined_q or "obbba" in combined_q:
                statutory_authority = "Public Law 119-21 (OBBBA) Title VIII Subtitle B & 34 CFR Part 685"
                economic_dataset = "HHS Federal Poverty Guidelines & FRED SLSTTOTAL Series"
                model_name = "OBBBA Repayment Assistance Plan (RAP) Tiered AGI Model"
                formula = "max(10.0, (agi * rap_tier_rate / 12.0) - (dependents * 50.0))"
                inputs = {"agi": 85000, "rap_tier_rate": 0.08, "dependents": 1}
                published_output = 516.67
                sample_calculation = "AGI $85,000 at 8% RAP tier less $50 dependent credit yields $516.67/mo"
            elif "refinance" in combined_q:
                statutory_authority = "34 CFR Part 685 & TILA Regulation Z (12 CFR Part 1026)"
                economic_dataset = "FRED SLSTTOTAL & 10-Year Treasury Yield Series"
                model_name = "Federal Title IV vs Private Refinance Break-Even Model"
                formula = "balance * ((federal_rate - refinance_rate) / 100.0)"
                inputs = {"balance": 68500, "federal_rate": 7.05, "refinance_rate": 5.25}
                published_output = 1233.0
                sample_calculation = "Balance $68,500 refinanced from 7.05% to 5.25% saves $1,233.00 first-year interest"
            else:
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
        elif self.tenant_id == "gainhelm":
            default_category = "Cyber Compliance & GRC Audit"
            affiliates = ["vanta_security", "drata_compliance"]
            if any(t in combined_q for t in ("cmmc", "800-171", "sprs", "dfars", "c3pao")):
                statutory_authority = "32 CFR Part 170 & DFARS 252.204-7012 / 7019 / 7020 / 7021"
                economic_dataset = "DoD CMMC 2.0 Cost Assessment & BLS OEWS 15-1212"
                model_name = "CMMC 2.0 Level 2 C3PAO & NIST 800-171 SPRS Readiness Model"
                formula = "c3pao_assessment_fee + enclave_licensing_cost + (remediation_hours * eng_hourly_rate)"
                inputs = {
                    "c3pao_assessment_fee": 48000,
                    "enclave_licensing_cost": 18000,
                    "remediation_hours": 220,
                    "eng_hourly_rate": 95,
                }
                published_output = 86900.0
                sample_calculation = "C3PAO fee $48,000 plus $18,000 CUI enclave plus 220 hrs at $95/hr yields $86,900 CMMC Level 2 TCO"
            elif any(t in combined_q for t in ("iso-27001", "iso 27001", "isms", "27006")):
                statutory_authority = "ISO/IEC 27001:2022 Annex A (93 Controls) & ISO/IEC 27006-1:2024"
                economic_dataset = "IAF MD 5 Auditor-Day Schedule & BLS OEWS 15-1212"
                model_name = "ISO/IEC 27001:2022 Stage 1/2 & Surveillance Certification Model"
                formula = "(auditor_days * auditor_day_rate) + grc_platform_annual_cost + (isms_prep_hours * eng_hourly_rate)"
                inputs = {
                    "auditor_days": 14,
                    "auditor_day_rate": 1850,
                    "grc_platform_annual_cost": 15000,
                    "isms_prep_hours": 140,
                    "eng_hourly_rate": 95,
                }
                published_output = 54200.0
                sample_calculation = "14 auditor-days at $1,850/day plus $15,000 GRC platform plus 140 hrs at $95/hr yields $54,200 ISO 27001 TCO"
            elif any(t in combined_q for t in ("hipaa", "hitech", "ocr", "breach", "phi")):
                statutory_authority = "45 CFR 160.404, 45 CFR Part 164 & 42 U.S.C. 1320d-5"
                economic_dataset = "HHS OCR Penalty Inflation Schedule & IBM Cost of a Data Breach Report"
                model_name = "HIPAA / HITECH Breach Notification & OCR Civil Penalty Exposure Model"
                formula = "(compromised_records * per_record_forensic_cost) + ocr_tier_penalty_estimate"
                inputs = {
                    "compromised_records": 2500,
                    "per_record_forensic_cost": 165,
                    "ocr_tier_penalty_estimate": 75500,
                }
                published_output = 488000.0
                sample_calculation = "2,500 records at $165/record plus $75,500 OCR Tier 2 penalty yields $488,000 total breach exposure"
            else:
                statutory_authority = "AICPA SSAE 18 / AT-C Section 205 & TSP Section 100"
                economic_dataset = "BLS OEWS 13-2011 / 15-1212 & IBM Cost of a Data Breach Report"
                model_name = "SOC 2 Type II Audit & Readiness TCO Model"
                formula = "cpa_audit_fee + grc_platform_annual_cost + (readiness_hours * eng_hourly_rate)"
                inputs = {
                    "cpa_audit_fee": 28000,
                    "grc_platform_annual_cost": 15000,
                    "readiness_hours": 160,
                    "eng_hourly_rate": 95,
                }
                published_output = 58200.0
                sample_calculation = "CPA audit fee $28,000 plus $15,000 GRC platform plus 160 hours at $95/hr yields $58,200 total SOC 2 Type II TCO"
            disclosures = [
                GAINHELM_DISCLOSURES.get("statutory_audit_disclaimer", ""),
                GAINHELM_DISCLOSURES.get("ftc_disclosure", ""),
            ]
            canonical_base = "https://gainhelm.com"
        else:
            if "1031" in combined_q or "like-kind" in combined_q:
                default_category = "1031 Exchange"
                affiliates = ["ipx1031", "exeter1031"]
                statutory_authority = "IRC Section 1031(a)(1)"
                economic_dataset = "FRED CPILFESL Series"
                model_name = "Section 1031 Like-Kind Exchange Model"
                formula = "relinquished_basis + recognized_gain"
                inputs = {"relinquished_basis": 450000, "recognized_gain": 0}
                published_output = 450000.0
                sample_calculation = "Relinquished basis 450,000 with zero recognized gain yields replacement basis 450,000"
            elif any(t in combined_q for t in ("crypto", "bitcoin", "staking", "airdrop", "8949", "1099-da")):
                default_category = "Crypto Tax Intelligence"
                affiliates = ["coinledger", "koinly"]
                statutory_authority = "IRC Section 1001 & IRS Form 8949"
                economic_dataset = "FRED CPILFESL Series"
                model_name = "Digital Asset Realized Gain Model"
                formula = "proceeds - cost_basis"
                inputs = {"proceeds": 85000, "cost_basis": 35000}
                published_output = 50000.0
                sample_calculation = "Proceeds 85,000 minus cost basis 35,000 yields 50,000 net taxable capital gain"
            elif any(t in combined_q for t in ("prediction", "kalshi", "polymarket", "implied-probability", "implied probability", "kelly", "event-contract", "1256")):
                default_category = "Quantitative Market Analytics"
                affiliates = ["coinledger", "kalshi"]
                statutory_authority = "IRC Section 1256 & CFTC 17 CFR Part 40"
                economic_dataset = "FRED DGS10 Series"
                model_name = "Event Contract Expected Value & Section 1256 Tax Model"
                formula = "gross_payout - contract_cost"
                inputs = {"gross_payout": 10000, "contract_cost": 6200}
                published_output = 3800.0
                sample_calculation = "Gross payout 10,000 minus contract cost 6,200 yields 3,800 net settlement gain"
            elif any(t in combined_q for t in ("bracket", "tcja", "capital-gains", "capital gains", "standard deduction")):
                default_category = "Tax Intelligence"
                affiliates = ["turbotax", "taxslayer"]
                statutory_authority = "IRC Section 1(j) & Rev. Proc. 2025-32"
                economic_dataset = "FRED CPILFESL Series"
                model_name = "Federal Statutory Bracket Liability Model"
                formula = "taxable_income * effective_rate"
                inputs = {"taxable_income": 180000, "effective_rate": 0.22}
                published_output = 39600.0
                sample_calculation = "Taxable income 180,000 at 22 percent effective rate yields 39,600 liability"
            elif any(t in combined_q for t in ("s-corp", "s corp", "reasonable-salary", "reasonable salary", "qbi", "199a")):
                default_category = "Tax Intelligence"
                affiliates = ["gusto", "collective"]
                statutory_authority = "IRC Section 1366, Section 3121 & Section 199A"
                economic_dataset = "BLS OEWS Wage Series & IRS SOI Pass-Through Series"
                model_name = "S-Corporation Reasonable Salary & FICA Savings Model"
                formula = "(net_business_income - officer_salary) * 0.153"
                inputs = {"net_business_income": 220000, "officer_salary": 95000}
                published_output = 19125.0
                sample_calculation = "Distributions of $125,000 above $95,000 W-2 salary save $19,125 in 15.3% SECA tax"
            elif any(t in combined_q for t in ("174", "r-and-d", "r&d", "research-credit")):
                default_category = "Tax Intelligence"
                affiliates = ["gusto", "mercury"]
                statutory_authority = "IRC Section 41 & Section 174"
                economic_dataset = "IRS SOI Corporation Research Credit Series"
                model_name = "Section 41 R&D Tax Credit & Section 174 Amortization Model"
                formula = "qre_total * 0.10"
                inputs = {"qre_total": 450000}
                published_output = 45000.0
                sample_calculation = "Qualified research expenditures of $450,000 yield $45,000 payroll tax credit offset"
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

    def investigate_competitor_traffic_spikes(
        self,
        repo_root: Optional[Union[str, Path]] = None,
        velocity_spike_threshold: float = 0.25,
        persist: bool = True,
    ) -> Dict[str, Any]:
        """
        Correlates longitudinal velocity spikes from trend_history.db and statutory.db
        against competitor SERP features and active tenant catalog gaps (Workflow 3).
        Zero em-dashes. Zero en-dashes.
        """
        from pseofactory.seo_growth_loops import investigate_competitor_traffic_spikes as _investigate_spikes

        return _investigate_spikes(
            property_id=self.tenant_id,
            repo_root=repo_root,
            velocity_spike_threshold=velocity_spike_threshold,
            persist=persist,
        )

    def parse_serp_dom_structural_profile(
        self,
        raw_html: str,
        raw_js: str = "",
    ) -> Dict[str, Any]:
        """
        Programmatically parses a competitor or tenant DOM snapshot across schema depth,
        interactive calculator mechanics (SSR vs CSR output hydration, fee presets, state carry),
        statutory/empirical citation density, and tenant entity coverage.
        Zero em-dashes. Zero en-dashes.
        """
        return parse_serp_dom_structural_profile(
            raw_html=raw_html,
            raw_js=raw_js,
            tenant_id=self.tenant_id,
        )

    def diff_competitor_dom_structure(
        self,
        competitor_html: str,
        tenant_html: str = "",
        competitor_js: str = "",
        target_slug: str = "",
        query: str = "",
    ) -> Dict[str, Any]:
        """
        Programmatically diffs a competitor SERP DOM snapshot against a compiled tenant page
        and emits a deterministic template_mutation_spec for automated overlay/template recovery.
        Zero em-dashes. Zero en-dashes.
        """
        return diff_competitor_dom_structure(
            competitor_html=competitor_html,
            tenant_html=tenant_html,
            competitor_js=competitor_js,
            tenant_id=self.tenant_id,
            target_slug=target_slug,
            query=query,
        )

    def diff_live_competitor_scratch_snapshots(
        self,
        scratch_dir: Optional[Union[str, Path]] = None,
        tenant_repo_root: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        """
        Diffs live competitor SERP DOM snapshots in .agy/scratch against compiled tenant pages
        and returns deterministic template mutation payloads.
        Zero em-dashes. Zero en-dashes.
        """
        return diff_live_competitor_scratch_snapshots(
            scratch_dir=scratch_dir,
            tenant_repo_root=tenant_repo_root,
            tenant_id=self.tenant_id,
        )

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
        elif tenant_id == "gainhelm":
            spec.setdefault("tenant", "gainhelm")
            spec.setdefault("property_id", "gainhelm")
            spec.setdefault("domain", "gainhelm.com")
            spec.setdefault("canonical_base", "https://gainhelm.com")
            spec.setdefault("statutory_authority", "AICPA SSAE 18 / AT-C Section 205 & TSP Section 100")
            spec.setdefault("economic_dataset", "BLS OEWS 13-2011 / 15-1212 & IBM Cost of a Data Breach Report")
            spec.setdefault("category", "Cyber Compliance & GRC Audit")
            spec.setdefault(
                "affiliates",
                monetization.get("recommended_partners") or ["vanta_security", "drata_compliance"],
            )
            spec.setdefault("model_name", "SOC 2 Type II Audit & Readiness TCO Model")
            spec.setdefault("formula", "cpa_audit_fee + grc_platform_annual_cost + (readiness_hours * eng_hourly_rate)")
            spec.setdefault(
                "inputs",
                {
                    "cpa_audit_fee": 28000,
                    "grc_platform_annual_cost": 15000,
                    "readiness_hours": 160,
                    "eng_hourly_rate": 95,
                },
            )
            spec.setdefault("published_output", 58200.0)
            spec.setdefault(
                "sample_calculation",
                "CPA audit fee $28,000 plus $15,000 GRC platform plus 160 hours at $95/hr yields $58,200 total SOC 2 Type II TCO",
            )
            spec.setdefault(
                "mandatory_disclosures",
                [
                    GAINHELM_DISCLOSURES.get("statutory_audit_disclaimer", ""),
                    GAINHELM_DISCLOSURES.get("ftc_disclosure", ""),
                ],
            )
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
            else (
                "soc 2 audit cost calculator"
                if self.tenant_id == "gainhelm"
                else "section 179 tax deduction calculator"
            )
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
    "gainhelm": [
        {
            "query": "soc 2 audit cost calculator",
            "slug": "soc-2-audit-cost-calculator",
            "target_url": "https://gainhelm.com/tools/soc-2-audit-cost-calculator/",
            "intent_tier": "tier_1_grc_audit_compliance",
            "restricted_public_service": False,
            "commercial_offers_allowed": True,
            "engine_positions": {"google": None, "bing": 14, "duckduckgo": 11},
            "higher_ranked_competitors": [
                {
                    "domain": "vanta.com",
                    "url": "https://www.vanta.com/resources/soc-2-cost",
                    "engine_ranks": {"google": 1, "bing": 1, "duckduckgo": 1},
                    "winning_mechanics": [
                        "server_rendered_sensitivity_grid",
                        "deep_link_scenario_presets",
                        "jsonld_entity_triad",
                        "compliant_intent_monetization",
                    ],
                    "indexing_advantage": "Direct GRC vendor authority + Type I vs Type II cost tables.",
                },
                {
                    "domain": "sprinto.com",
                    "url": "https://sprinto.com/blog/soc-2-compliance-cost/",
                    "engine_ranks": {"google": 2, "bing": 2, "duckduckgo": 2},
                    "winning_mechanics": [
                        "server_rendered_sensitivity_grid",
                        "deep_link_scenario_presets",
                    ],
                    "indexing_advantage": "Employee headcount and TSC criteria cost breakdown tables.",
                },
            ],
            "root_cause_diagnosis": (
                "Vanta and Sprinto rank #1-#2 with static prose cost ranges, leaving an interactive "
                "deterministic calculator void combining CPA audit fees, GRC licensing, and engineering hours."
            ),
            "compiler_upgrades_applied": list(WINNING_COMPETITOR_MECHANICS.keys()),
            "recommended_affiliates": ["vanta_security", "drata_compliance"],
        },
        {
            "query": "cmmc 2.0 compliance cost calculator",
            "slug": "cmmc-2-0-compliance-cost-calculator",
            "target_url": "https://gainhelm.com/tools/cmmc-2-0-compliance-cost-calculator/",
            "intent_tier": "tier_1_federal_defense_cyber",
            "restricted_public_service": False,
            "commercial_offers_allowed": True,
            "engine_positions": {"google": None, "bing": 12, "duckduckgo": 9},
            "higher_ranked_competitors": [
                {
                    "domain": "summit7.us",
                    "url": "https://www.summit7.us/blog/cmmc-cost",
                    "engine_ranks": {"google": 1, "bing": 1, "duckduckgo": 1},
                    "winning_mechanics": [
                        "server_rendered_sensitivity_grid",
                        "jsonld_entity_triad",
                    ],
                    "indexing_advantage": "DoD 32 CFR Part 170 C3PAO assessment fee schedules.",
                },
                {
                    "domain": "preveil.com",
                    "url": "https://www.preveil.com/blog/cmmc-compliance-cost/",
                    "engine_ranks": {"google": 2, "bing": 2, "duckduckgo": 2},
                    "winning_mechanics": [
                        "server_rendered_sensitivity_grid",
                        "deep_link_scenario_presets",
                    ],
                    "indexing_advantage": "CUI enclave cost tables for defense subcontractors.",
                },
            ],
            "root_cause_diagnosis": (
                "Defense cyber consultancies publish static DoD 32 CFR Part 170 fee estimates without "
                "interactive CUI enclave scoping and NIST SP 800-171 control remediation calculators."
            ),
            "compiler_upgrades_applied": list(WINNING_COMPETITOR_MECHANICS.keys()),
            "recommended_affiliates": ["vanta_security", "drata_compliance"],
        },
        {
            "query": "nist 800-171 sprs score calculator",
            "slug": "nist-800-171-sprs-score-calculator",
            "target_url": "https://gainhelm.com/tools/nist-800-171-sprs-score-calculator/",
            "intent_tier": "tier_1_federal_defense_cyber",
            "restricted_public_service": False,
            "commercial_offers_allowed": True,
            "engine_positions": {"google": None, "bing": 11, "duckduckgo": 8},
            "higher_ranked_competitors": [
                {
                    "domain": "acquisition.gov",
                    "url": "https://www.acquisition.gov/dfars/252.204-7019",
                    "engine_ranks": {"google": 1, "bing": 1, "duckduckgo": 1},
                    "winning_mechanics": [
                        "server_rendered_sensitivity_grid",
                        "jsonld_entity_triad",
                    ],
                    "indexing_advantage": "Official DFARS 252.204-7019 statutory authority.",
                },
                {
                    "domain": "summit7.us",
                    "url": "https://www.summit7.us/blog/sprs-score",
                    "engine_ranks": {"google": 2, "bing": 2, "duckduckgo": 2},
                    "winning_mechanics": [
                        "server_rendered_sensitivity_grid",
                        "deep_link_scenario_presets",
                    ],
                    "indexing_advantage": "DoD 110-control 5/3/1 point deduction breakdown.",
                },
            ],
            "root_cause_diagnosis": (
                "Official DFARS pages lack an interactive 110-control DoD SPRS [-203, +110] scoring "
                "and 32 CFR 170.21 POA&M conditional eligibility calculator."
            ),
            "compiler_upgrades_applied": list(WINNING_COMPETITOR_MECHANICS.keys()),
            "recommended_affiliates": ["vanta_security", "drata_compliance"],
        },
        {
            "query": "iso 27001 certification cost calculator",
            "slug": "iso-27001-certification-cost-calculator",
            "target_url": "https://gainhelm.com/tools/iso-27001-certification-cost-calculator/",
            "intent_tier": "tier_1_grc_audit_compliance",
            "restricted_public_service": False,
            "commercial_offers_allowed": True,
            "engine_positions": {"google": None, "bing": 13, "duckduckgo": 10},
            "higher_ranked_competitors": [
                {
                    "domain": "sprinto.com",
                    "url": "https://sprinto.com/blog/iso-27001-certification-cost/",
                    "engine_ranks": {"google": 1, "bing": 1, "duckduckgo": 1},
                    "winning_mechanics": [
                        "server_rendered_sensitivity_grid",
                        "deep_link_scenario_presets",
                    ],
                    "indexing_advantage": "ISO/IEC 27006-1 auditor-day tables by employee headcount.",
                },
                {
                    "domain": "vanta.com",
                    "url": "https://www.vanta.com/resources/iso-27001-certification-cost",
                    "engine_ranks": {"google": 2, "bing": 2, "duckduckgo": 2},
                    "winning_mechanics": [
                        "server_rendered_sensitivity_grid",
                        "jsonld_entity_triad",
                    ],
                    "indexing_advantage": "Stage 1 and Stage 2 registrar fee benchmarks.",
                },
            ],
            "root_cause_diagnosis": (
                "Competitors publish static blog tables rather than an interactive ISO/IEC 27006-1:2024 "
                "Stage 1 and Stage 2 registrar auditor-day and surveillance cost calculator."
            ),
            "compiler_upgrades_applied": list(WINNING_COMPETITOR_MECHANICS.keys()),
            "recommended_affiliates": ["sprinto_compliance", "vanta_security"],
        },
        {
            "query": "hipaa violation fines calculator",
            "slug": "hipaa-violation-penalty-breach-cost-calculator",
            "target_url": "https://gainhelm.com/tools/hipaa-violation-penalty-breach-cost-calculator/",
            "intent_tier": "tier_1_healthcare_cyber_compliance",
            "restricted_public_service": False,
            "commercial_offers_allowed": True,
            "engine_positions": {"google": None, "bing": 10, "duckduckgo": 9},
            "higher_ranked_competitors": [
                {
                    "domain": "hipaajournal.com",
                    "url": "https://www.hipaajournal.com/what-are-the-penalties-for-hipaa-violations-7096/",
                    "engine_ranks": {"google": 1, "bing": 1, "duckduckgo": 1},
                    "winning_mechanics": [
                        "server_rendered_sensitivity_grid",
                        "jsonld_entity_triad",
                    ],
                    "indexing_advantage": "45 CFR 160.404 4-tier civil monetary penalty schedules.",
                },
                {
                    "domain": "hhs.gov",
                    "url": "https://www.hhs.gov/hipaa/for-professionals/compliance-enforcement/index.html",
                    "engine_ranks": {"google": 2, "bing": 2, "duckduckgo": 2},
                    "winning_mechanics": [
                        "jsonld_entity_triad",
                    ],
                    "indexing_advantage": "Official HHS Office for Civil Rights enforcement authority.",
                },
            ],
            "root_cause_diagnosis": (
                "HIPAA Journal ranks #1 with static prose tables, leaving an interactive calculator gap "
                "for 45 CFR 160.404 inflation-adjusted OCR penalty tiers and ePHI breach notification costs."
            ),
            "compiler_upgrades_applied": list(WINNING_COMPETITOR_MECHANICS.keys()),
            "recommended_affiliates": ["vanta_security", "coalition_cyber_insurance"],
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
            default_comp_domain = (
                "studentaid.gov"
                if prop == "prexvo"
                else ("secureframe.com" if prop == "gainhelm" else "smartasset.com")
            )
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
    Benchmarks multi-engine search rankings and higher-ranked competitors across
    profithelm, prexvo, and gainhelm, returning a domain-isolated comparison dictionary.
    Zero em-dashes. Zero en-dashes.
    """
    return {
        "profithelm": benchmark_multi_engine_rankings("profithelm"),
        "prexvo": benchmark_multi_engine_rankings("prexvo"),
        "gainhelm": benchmark_multi_engine_rankings("gainhelm"),
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
        for tok in ("tax-bracket", "tax-rate", "tcja", "capital-gains", "s-corp", "reasonable-salary", "1202", "qsbs", "amt", "niit")
    ):
        return None
    if any(tok in s_low for tok in ("s-corp", "reasonable-salary")):
        return {
            "trap_title": "Immediate IRS Revenue Ruling 74-44 Reasonable Compensation and Section 199A Wage Cap Trap Alert (IRC Section 3121)",
            "trap_body": (
                "Under IRS Revenue Ruling 74-44 and IRC Section 3121, S-Corporation shareholder-employees who perform "
                "substantial services must receive reasonable W-2 compensation subject to 15.3% FICA tax before taking "
                "FICA-exempt K-1 distributions. Setting W-2 salary artificially low risks IRS distribution recharacterization "
                "and IRC Section 6656 payroll tax penalties, while setting W-2 salary too high erodes the 20% IRC Section 199A QBI deduction base."
            ),
            "checklist_items": [
                "Benchmark officer W-2 compensation against BLS OEWS occupational wage percentiles across technical, management, and administrative hours.",
                "Model the IRC Section 3121 OASDI Social Security wage base cap ($176,100) alongside the uncapped 2.9% Medicare and 0.9% Additional Medicare surtax.",
                "Balance W-2 salary against remaining K-1 pass-through profit to maximize the 20% IRC Section 199A Qualified Business Income (QBI) deduction.",
                "Report >2% S-Corp shareholder health insurance premiums on Form W-2 Box 1 (exempt from Box 3 and Box 5 FICA under IRS Notice 2008-1) to preserve above-the-line deductibility.",
            ],
            "pitfalls": [
                (
                    "Taking $0 or nominal W-2 officer salary while withdrawing large K-1 shareholder distributions",
                    "Triggers IRS Revenue Ruling 74-44 audit reclassification of distributions into wages plus 15.3% FICA and Section 6656 failure-to-deposit penalties",
                    "Document an annual BLS OEWS multi-role compensation study and run scheduled W-2 payroll via Form 941 before distributing K-1 profits",
                ),
                (
                    "Over-allocating W-2 salary when net business income is below the Section 199A W-2 wage limitation threshold",
                    "Replaces tax-advantaged K-1 pass-through income (eligible for the 20% QBI deduction) with fully taxed W-2 wages subject to 15.3% FICA",
                    "Solve jointly for combined FICA payroll tax and Section 199A QBI tax shield across your marginal federal tax bracket",
                ),
                (
                    "Omitting >2% shareholder-employee health insurance premiums from Form W-2 Box 1 wages",
                    "Disqualifies the IRC Section 162(l) self-employed health insurance deduction on Schedule 1 of Form 1040",
                    "Reimburse or pay policy premiums through the S-Corp and include them in Box 1 (but not Boxes 3 or 5) of the officer's Form W-2",
                ),
            ],
            "handoff_title": "S-Corp Payroll, Reasonable Compensation & CPA Vetting Checklist",
            "handoff_items": [
                "Verify automated Form 941/940 quarterly payroll tax filings, W-2 Box 14 >2% shareholder health insurance coding, and state SUTA synchronization.",
                "Confirm BLS OEWS reasonable compensation study documentation and Section 199A W-2/K-1 split modeling support.",
                "Check state Pass-Through Entity Tax (PTET) election workflows (IRS Notice 2020-75) and quarterly Form 1040-ES safe-harbor integration.",
            ],
        }
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
    """Builds context-aware 3-tier topic cluster links covering all 21 canonical root calculators plus state and vehicle rings."""
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
        ("saas-runway-calculator", "SaaS Cash Runway, Net Burn & Burn Multiple Benchmarks Calculator"),
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
        ("section-1031-calculator/texas", "Texas Section 1031 Like-Kind Exchange & Boot Tax Calculator"),
        ("section-1031-calculator/arizona", "Arizona Section 1031 Like-Kind Exchange & Boot Tax Calculator"),
        ("section-1031-calculator/california", "California Section 1031 Like-Kind Exchange & FTB 3840 Calculator"),
        ("section-1031-calculator/alabama", "Alabama Section 1031 Like-Kind Exchange & Boot Tax Calculator"),
        ("section-1031-calculator/maine", "Maine Section 1031 Like-Kind Exchange & Boot Tax Calculator"),
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


def _resolve_b2b_commercial_competitor_content(s_low: str) -> Optional[Dict[str, Any]]:
    """Resolves vertical-isolated statutory traps, checklists, pitfalls, and handoff protocols for R&D 174, Section 301 Tariffs, Surety Bonds, Factoring/Runway, Workers Comp, and Treasury models."""
    if any(tok in s_low for tok in ("174", "r-and-d", "r&d", "research")):
        return {
            "trap_title": "Immediate Section 174 Capitalization and Section 280C(c) Credit Reduction Trap Alert",
            "trap_body": (
                "Under IRC Section 174(a)(2)(B), foreign software development and engineering research expenditures "
                "must be capitalized over 15 years (3.33% Year 1 mid-year convention), while domestic R&D reconciled "
                "under OBBBA Section 174A requires strict IRC Section 280C(c) election coordination on IRS Form 6765 "
                "to prevent double-counting wages across deductions and credits."
            ),
            "checklist_items": [
                "Segregate domestic U.S. W-2 engineering wages and cloud staging costs from foreign contractor research under IRC Section 174(a)(2)(B).",
                "Evaluate the IRC Section 280C(c)(3) reduced credit election (79% statutory multiplier) on original timely filed IRS Form 6765.",
                "Substantiate all four parts of the IRC Section 41(d) technological uncertainty and process-of-experimentation test at the business-component level.",
                "Verify Qualified Small Business (QSB) gross receipts (<$5,000,000) before electing up to $500,000 in IRC Section 41(h) payroll tax offsets on Form 8974.",
            ],
            "pitfalls": [
                (
                    "Claiming the gross 20% IRC Section 41 R&D credit without reducing Section 174 deductions under Section 280C(c)",
                    "Triggers mandatory disallowance of R&D expense deductions equal to the full unreduced credit amount",
                    "Make a timely IRC Section 280C(c)(3) reduced credit election on the original return or reduce capitalized Section 174 basis accordingly",
                ),
                (
                    "Pooling offshore contractor engineering invoices with domestic W-2 software development wages",
                    "Violates IRC Section 41(d)(4)(F) foreign research exclusion and subjects domestic costs to 15-year amortization",
                    "Maintain jurisdiction-tagged payroll and vendor subledgers separating domestic U.S. research from offshore work",
                ),
                (
                    "Omitting business-component technical narratives required by the updated IRS Form 6765 Section G",
                    "Exposes R&D credit refund claims to summary administrative rejection under IRS Chief Counsel guidance",
                    "Map time-tracking and Git commit logs directly to named business components and technical uncertainties before filing",
                ),
            ],
            "handoff_title": "R&D Tax Credit & Section 174 Engineering Study Vetting Checklist",
            "handoff_items": [
                "Confirm automated Git/Jira engineering time-study integration and Form 6765 Section G business-component substantiation.",
                "Verify audit defense representation coverage and CPA sign-off for IRC Section 41(h) Form 8974 payroll tax credit filings.",
                "Audit domestic vs foreign vendor classification controls for accurate 5-year vs 15-year Section 174 amortization schedules.",
            ],
        }
    if any(tok in s_low for tok in ("301", "tariff", "landed-cost", "duty", "import")):
        return {
            "trap_title": "Immediate Section 301 HTSUS Duty Stacking and Customs Valuation Trap Alert (19 U.S.C. 2411)",
            "trap_body": (
                "Under Section 301 of the Trade Act of 1974 (19 U.S.C. 2411) and 19 CFR Part 152, punitive Lists 1-4A "
                "tariffs (7.5% to 100%) stack additively on top of baseline Most-Favored-Nation (MFN) Column 1 rates, "
                "Merchandise Processing Fees (MPF at 0.3464%), and Harbor Maintenance Fees (HMF at 0.125%) on CBP Form 7501."
            ),
            "checklist_items": [
                "Verify 10-digit HTSUS classification rulings and Country of Origin substantial transformation criteria before customs entry.",
                "Compute ad valorem duties on transaction value (19 U.S.C. 1401a) including dutiable assists, tooling, and foreign inland freight.",
                "Audit Merchandise Processing Fee (MPF 0.3464%, subject to CBP statutory min/max caps) and Harbor Maintenance Fee (0.125% ocean freight).",
                "Evaluate bonded warehouse, Foreign Trade Zone (FTZ), or First Sale for Export valuation strategies to defer or reduce dutiable basis.",
            ],
            "pitfalls": [
                (
                    "Calculating Section 301 tariff exposure solely on invoice unit price while omitting dutiable tooling and design assists",
                    "Understates customs transaction value under 19 U.S.C. 1401a and triggers 19 U.S.C. 1592 CBP penalty assessments",
                    "Apportion all foreign-supplied molds, dies, and engineering assists onto CBP Form 7501 declared entry value",
                ),
                (
                    "Relying on third-country transshipment or minor assembly without substantial transformation",
                    "CBP treats origin as unchanged and assesses retroactive Section 301 duties plus Negligence/Gross Negligence penalties",
                    "Obtain a binding CBP Country of Origin ruling (19 CFR Part 177) proving tariff shift and substantial transformation",
                ),
                (
                    "Failing to update customs continuous bond limits after Section 301 tariff rate increases",
                    "Results in CBP bond insufficiency notices and immediate port-of-entry cargo holds",
                    "Recalculate 10% of annual cumulative duties, taxes, and fees to size continuous customs bonds proactively",
                ),
            ],
            "handoff_title": "Customs Brokerage, Trade Financing & Freight Vetting Checklist",
            "handoff_items": [
                "Verify licensed Customs Broker automated ACE Form 7501 audit logs and 10-digit HTSUS tariff engineering support.",
                "Confirm Continuous Customs Bond capacity (10% of rolling 12-month duty/MPF/HMF outlay) to prevent port holds.",
                "Compare trade finance and working-capital facility APRs for funding upfront CBP Automated Clearinghouse (ACH) duty draws.",
            ],
        }
    if any(tok in s_low for tok in ("surety", "bond", "contractor")):
        return {
            "trap_title": "Immediate Miller Act Threshold and Personal Indemnity Trap Alert (40 U.S.C. 3131)",
            "trap_body": (
                "Under the federal Miller Act (40 U.S.C. 3131) and state Little Miller Acts, prime contractors on public "
                "works exceeding $150,000 must furnish 100% Performance and Payment Bonds. Unlike commercial casualty "
                "insurance, surety bonds require a General Indemnity Agreement (GIA) that binds corporate and personal assets."
            ),
            "checklist_items": [
                "Verify statutory bond penalty amount and obligee wording requirements before submitting bid or license packages.",
                "Audit Working Capital and Net Worth ratios (typically >=10% of aggregate bonded work-in-progress backlog) for standard market tier qualification.",
                "Review General Indemnity Agreement (GIA) spousal signature and personal asset subordination clauses prior to execution.",
                "Confirm surety carrier listing on U.S. Treasury Department Circular 570 for federal Miller Act compliance.",
            ],
            "pitfalls": [
                (
                    "Treating a commercial or contract surety bond premium as non-recourse liability insurance",
                    "The surety carrier holds statutory and contractual subrogation rights to recover 100% of claim payouts from the principal",
                    "Maintain segregated project trust accounting and resolve subcontractor payment disputes before a bond claim is filed",
                ),
                (
                    "Letting CPA-prepared Work-in-Progress (WIP) schedules lapse when bidding larger public contracts",
                    "Pushes underwriting from preferred standard rates (0.5%-1.5%) into high-risk specialty tiers (3.0%-10.0%)",
                    "Provide quarterly CPA-reviewed percentage-of-completion financial statements to unlock preferred surety rate tiers",
                ),
                (
                    "Allowing state contractor license or ERISA fidelity bonds to expire prior to renewal date",
                    "Triggers automatic state contractor license suspension and statutory civil penalties",
                    "Align multi-year bond continuation certificates with state licensing board renewal dates for 15-25% term discounts",
                ),
            ],
            "handoff_title": "Surety Underwriting & Treasury Circular 570 Vetting Checklist",
            "handoff_items": [
                "Confirm underwriting carrier holds an A.M. Best A- or higher rating and active U.S. Treasury Circular 570 authority.",
                "Verify instant digital bond execution and direct electronic filing with state contractor licensing boards.",
                "Check multi-year continuation discounts and SBA Surety Bond Guarantee (SBG) program participation for growing contractors.",
            ],
        }
    if any(tok in s_low for tok in ("factoring", "line-of-credit", "runway", "burn", "saas")):
        return {
            "trap_title": "Immediate Factor Rate to Effective APR and UCC-1 Blanket Lien Trap Alert (12 CFR Part 1026)",
            "trap_body": (
                "A flat 2.5% to 3.0% invoice factoring discount fee on a 30-to-45-day receivable turnover cycle equals "
                "an annualized effective APR of 24.3% to 36.5% before wire and lockbox fees. Additionally, recourse "
                "factoring agreements and UCC-1 blanket liens can restrict senior bank revolving lines of credit."
            ),
            "checklist_items": [
                "Convert flat factor discount fees and origination points into annualized Effective APR across actual customer DSO (Days Sales Outstanding).",
                "Distinguish Recourse Factoring (borrower absorbs 90-day customer non-payment chargebacks) from Non-Recourse credit-insured factoring.",
                "Audit UCC-1 financing statement filings to ensure liens are limited to specific factored receivables rather than blanket corporate assets.",
                "Verify state commercial financing disclosure compliance (California SB 1235 / New York CFDL APR equivalency disclosures).",
            ],
            "pitfalls": [
                (
                    "Comparing a 3% 30-day factor fee directly against a 10% annual bank line of credit interest rate",
                    "Confuses a 30-day period discount with an annualized rate, masking a 36.5%+ true annualized capital cost",
                    "Annualize all discount fees, reserve holdback delays, and wire fees over exact invoice collection days (365 / DSO)",
                ),
                (
                    "Signing a factoring contract with minimum monthly volume covenants and early termination penalties",
                    "Locks working capital into high-cost receivable discounting even after qualifying for traditional bank credit",
                    "Negotiate spot-factoring flexibility and explicit UCC-1 lien release timelines prior to onboarding",
                ),
                (
                    "Ignoring reserve holdback float days after customer ACH remittance clears the lockbox",
                    "3-to-5 business day settlement holdbacks increase effective borrowing duration and compress cash runway",
                    "Include settlement clearance float days in the denominator when modeling annualized effective cost of capital",
                ),
            ],
            "handoff_title": "Working Capital, Treasury & Credit Facility Vetting Checklist",
            "handoff_items": [
                "Require standardized annualized APR disclosures (CA SB 1235 / NY CFDL compliant) including all lockbox and wire fees.",
                "Confirm zero prepayment penalties and automated UCC-3 termination filing upon facility payoff.",
                "Verify FDIC sweep coverage and API accounting reconciliation (QuickBooks / NetSuite) for automated cash flow tracking.",
            ],
        }
    if any(tok in s_low for tok in ("workers-comp", "payroll", "burden", "futa", "suta")):
        return {
            "trap_title": "Immediate NCCI Experience Modification Rate (EMR) and Wage Base Trap Alert (IRC Section 3301)",
            "trap_body": (
                "True employer labor burden extends 18% to 38% above base hourly or W-2 salary due to stacked statutory "
                "taxes (7.65% FICA under IRC Section 3111, 0.6% net FUTA on the first $7,000, state SUTA wage bases) "
                "and NCCI Workers' Compensation class rates multiplied by your Experience Modification Rate (EMR)."
            ),
            "checklist_items": [
                "Assign accurate 4-digit NCCI (or state bureau) classification codes separating clerical/office payroll (Code 8810) from field operations.",
                "Apply your current Experience Modification Rate (EMR) worksheet multiplier to manual class rates before bidding fixed-price contracts.",
                "Exclude overtime premium pay increment (the extra 0.5x above straight time) where permitted by NCCI payroll audit rules.",
                "Verify FUTA Form 940 Credit Reduction State status and state-specific SUTA taxable wage bases annually.",
            ],
            "pitfalls": [
                (
                    "Failing to segregate clerical or executive payroll from high-hazard field classification codes",
                    "Workers' comp auditors default undivided payroll into the highest-rated governing construction or manufacturing code",
                    "Maintain strict payroll register separation and timecard documentation for clerical (8810) vs field employees",
                ),
                (
                    "Engaging uninsured 1099 subcontractors without collecting verified Certificates of Insurance (COI)",
                    "Annual workers' comp audits reclassify uninsured subcontractor payments as direct taxable employee payroll",
                    "Collect and verify active Workers' Comp COIs or state exemption certificates before releasing subcontractor payments",
                ),
                (
                    "Including the 0.5x overtime premium increment in reportable workers' compensation payroll",
                    "Overpays workers' compensation premiums by up to 33% on all overtime hours worked in NCCI jurisdictions",
                    "Configure payroll software to separate straight-time wages from overtime premium increments for annual audit reports",
                ),
            ],
            "handoff_title": "Payroll Tax, PEO & Workers' Comp Pay-As-You-Go Vetting Checklist",
            "handoff_items": [
                "Verify Pay-As-You-Go workers' compensation billing integration to eliminate large upfront deposits and year-end audit shocks.",
                "Confirm automated NCCI class code split tracking and overtime premium deduction reporting.",
                "Check multi-state SUTA rate synchronization, IRS Form 941/940 e-filing guarantees, and COI tracking automation.",
            ],
        }
    if any(tok in s_low for tok in ("treasury", "hysa", "yield", "3124")):
        return {
            "trap_title": "Immediate State Tax Exemption and Tax-Equivalent Yield Trap Alert (31 U.S.C. 3124)",
            "trap_body": (
                "Under 31 U.S.C. 3124(a), interest earned on direct U.S. Treasury Bills, Notes, and Bonds is 100% exempt "
                "from state and local income taxes, whereas High-Yield Savings Account (HYSA) and bank CD interest is fully "
                "taxable at both federal and state marginal rates. In high-tax states (CA, NY, NJ, CT), a 5.00% T-Bill "
                "equals a 5.60% to 5.88% taxable bank yield."
            ),
            "checklist_items": [
                "Compare bank HYSA yields against U.S. Treasury Bills using Tax-Equivalent Yield: TEY = Treasury Yield / (1 minus Effective State & Local Tax Rate).",
                "Verify whether money market funds meet state minimum U.S. Government obligation asset thresholds (e.g., 50% quarterly requirement in CA, NY, CT).",
                "Account for the 3.8% Net Investment Income Tax (IRC Section 1411) which applies equally to both Treasury interest and bank HYSA interest above MAGI caps.",
                "Match T-Bill maturity ladders (4-week, 8-week, 13-week, 26-week) against quarterly IRS estimated tax and payroll disbursement dates.",
            ],
            "pitfalls": [
                (
                    "Comparing nominal pre-tax HYSA APY directly against U.S. Treasury Bill yields in a high-tax state",
                    "Ignores up to 13.3% state income tax drag on bank interest that is statutorily exempt on U.S. Treasuries under 31 U.S.C. 3124",
                    "Always evaluate after-tax net basis-point pick-up using your combined federal and state marginal tax brackets",
                ),
                (
                    "Holding mixed repo-backed money market funds in California, New York, or Connecticut assuming 100% state tax exemption",
                    "Repurchase agreements (repos) do not qualify as direct U.S. Treasury obligations under state passthrough rules",
                    "Use direct Treasury Bills or 100% U.S. Treasury-only money market funds to preserve state tax exemption",
                ),
                (
                    "Omitting Form 1099-INT Box 3 (Interest on U.S. Savings Bonds and Treasury Obligations) state subtraction adjustments",
                    "State tax software defaults to taxing 100% of federal AGI unless Box 3 Treasury interest is explicitly subtracted on the state return",
                    "Verify Form 1099-INT Box 3 subtraction entry on your state tax schedule (such as CA Schedule CA or NY IT-201)",
                ),
            ],
            "handoff_title": "Corporate Cash Management & Treasury Sweep Vetting Checklist",
            "handoff_items": [
                "Confirm direct U.S. Treasury custody (SIPC/custodial segregation) or 100% Treasury-only fund composition for 31 U.S.C. 3124 exemption.",
                "Verify automated Form 1099-INT Box 3 tax reporting and T+1 liquidity settlement into operating checking accounts.",
                "Audit management fee basis points (expense ratio) and FDIC sweep program bank network caps.",
            ],
        }
    return None


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
    is_gainhelm = property_id.strip().lower() == "gainhelm"
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
            handoff_title = "Non-Commercial Title IV Statutory Verification Checklist"
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
            handoff_title = "Vetted Private Refinance Underwriting Checklist (TILA Reg-Z)"
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
                    ("pslf-buyback-months-reconsideration-student-loan-calculator", "PSLF Hold Harmless Buyback & Reconsideration Months Calculator"),
                    ("student-loan-forgiveness-2026", "2026 Federal Student Loan Forgiveness Pathways & Discharge Estimator"),
                    ("student-loan-forgiveness-tax-bomb-insolvency-calculator", "Student Loan Forgiveness Tax Bomb & IRS Form 982 Insolvency Calculator"),
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
                    ("parent-plus-double-consolidation-loophole-2026-calculator", "Parent PLUS Double Consolidation Loophole 2026 Sunset & ICR vs IDR Calculator"),
                    ("grad-plus-borrowing-cap-calculator", "Grad PLUS Sunset and Borrowing Cap Calculator"),
                ],
            ),
        ]
    elif is_gainhelm:
        trap_title = "Immediate Audit Observation Window and Control Scoping Trap Alert (AICPA AT-C 205 & 32 CFR Part 170)"
        trap_body = (
            "Under AICPA AT-C Section 205 (SOC 2 Type II), ISO/IEC 27006-1:2024 auditor-day tables, and DoD 32 CFR "
            "Part 170 (CMMC 2.0 Level 2), failing to isolate production in-scope boundaries or allowing continuous "
            "control evidence gaps during a 3-to-12-month observation window triggers qualified audit opinions, "
            "mandatory re-testing surcharges, or SPRS score deductions below the 110-point NIST SP 800-171 threshold."
        )
        checklist_items = [
            "Define an explicit System Description and Network Boundary Diagram isolating in-scope production assets or CUI enclaves prior to auditor readiness kick-off.",
            "Automate continuous control evidence collection across identity (SSO/MFA), cloud infrastructure (AWS/GCP/Azure), endpoint MDM, and SDLC pull-request approvals.",
            "Conduct an internal readiness gap assessment and remediate high-severity findings before opening the Type II observation window or C3PAO Stage 2 assessment.",
            "Execute an independent CREST or OSCP penetration test and track critical/high CVE remediation SLAs prior to final auditor sign-off.",
        ]
        pitfalls = [
            (
                "Scoping the entire corporate IT network instead of a segmented production or CUI enclave boundary",
                "Inflates ISO 27006 auditor-days, endpoint licensing, and C3PAO assessment fees by 150% to 300%",
                "Deploy a zero-trust segmented enclave isolating regulated customer data or CUI before readiness scoping",
            ),
            (
                "Relying on manual screenshot spreadsheets during a 6-to-12-month SOC 2 Type II observation window",
                "Causes population sampling failures on access reviews, employee offboarding, and change management tickets",
                "Connect automated GRC API integrations (Vanta, Drata, Sprinto) to collect timestamped control evidence daily",
            ),
            (
                "Submitting an unverified DoD SPRS self-assessment score without a documented System Security Plan (SSP)",
                "Exposes defense primes and subcontractors to False Claims Act liability and DFARS 252.204-7020 contract withholding",
                "Substantiate all 110 NIST SP 800-171 Rev 2 controls in a live SSP and track open POA&M items with strict 180-day closeout rules",
            ),
        ]
        handoff_title = "GRC Automation, CPA Audit & Assessor Vetting Checklist"
        handoff_items = [
            "Verify peer-reviewed AICPA CPA firm registration, ISO/IEC 17021 accreditation, or Cyber-AB C3PAO authorization status.",
            "Confirm automated API evidence coverage across your cloud provider, identity provider, source control, and HRIS.",
            "Audit multi-framework control cross-mapping (SOC 2 + ISO 27001 + HIPAA + NIST 800-171) to eliminate duplicate audit workpapers.",
        ]
        tier_clusters = [
            (
                "Tier 1: Core Commercial GRC & Attestation Pillar Models",
                [
                    ("soc-2-audit-cost-calculator", "SOC 2 Type I and Type II Audit Cost & Engineering TCO Calculator"),
                    ("iso-27001-certification-cost-calculator", "ISO/IEC 27001:2022 Certification & Auditor-Day Cost Calculator"),
                    ("pci-dss-4-0-compliance-cost-calculator", "PCI DSS v4.0.1 QSA ROC and SAQ Compliance Cost Calculator"),
                    ("penetration-testing-scoping-cost-calculator", "CREST & OSCP Penetration Testing Scoping Cost Calculator"),
                ],
            ),
            (
                "Tier 2: Federal Defense & Cloud Authorization Matrices",
                [
                    ("cmmc-2-0-compliance-cost-calculator", "CMMC 2.0 Level 2 C3PAO Assessment & Enclave Cost Calculator"),
                    ("nist-800-171-sprs-score-calculator", "NIST SP 800-171 DoD SPRS Weighted Score & POA&M Calculator"),
                    ("fedramp-authorization-3pao-cost-calculator", "FedRAMP 20x & Rev 5 3PAO Authorization Cost Calculator"),
                ],
            ),
            (
                "Tier 3: Healthcare Statutory Penalty & Cyber Risk Spokes",
                [
                    ("hipaa-violation-penalty-breach-cost-calculator", "HIPAA Civil Monetary Penalty & HITECH Breach Cost Calculator"),
                    ("hitrust-csf-e1-i1-r2-certification-cost-calculator", "HITRUST CSF e1, i1, and r2 Certification Cost Calculator"),
                    ("cyber-liability-insurance-breach-exposure-calculator", "Cyber Liability Insurance Premium & Breach Exposure Calculator"),
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
                "calendar days after closing relinquished property OR your federal income tax return due date "
                "(requiring IRS Form 4868 or Form 7004 for Q4 closings). Additionally, any net debt reduction "
                "(mortgage boot) triggers immediate tax recognition unless offset by equal or greater replacement "
                "debt or fresh cash equity."
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
        elif not any(k in s_low for k in ("179", "equipment", "macrs", "depreciation", "vehicle", "gvwr")) and any(
            tok in s_low for tok in ("prediction", "kalshi", "polymarket", "kelly", "implied", "arbitrage", "odds", "vigorish", "-vig", "vig-", "break-even")
        ):
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
        elif _resolve_b2b_commercial_competitor_content(s_low) is not None:
            b2b_ctx = _resolve_b2b_commercial_competitor_content(s_low) or {}
            trap_title = b2b_ctx["trap_title"]
            trap_body = b2b_ctx["trap_body"]
            checklist_items = b2b_ctx["checklist_items"]
            pitfalls = b2b_ctx["pitfalls"]
            handoff_title = b2b_ctx["handoff_title"]
            handoff_items = b2b_ctx["handoff_items"]
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


def _format_safe_heading_topic(title: str, slug: str) -> str:
    """
    Produces a concise, entity-specific topic label for H2/H3 subheadings with
    zero forbidden dashes, zero unsplit CamelCase tokens, and zero standalone
    single-letter uppercase words (B-HJ-Z).
    """
    raw = str(title or "").split("|")[0].split(" - ")[0].strip()
    raw = re.sub(r"\([^)]*\)", "", raw).strip()
    raw = re.sub(r"^20\d{2}(?:-20\d{2})?\s+", "", raw).strip()
    # Split CamelCase model names (e.g. SCorpReasonableSalaryTaxArbitrageModel, SaaSRunwayGoingConcernModel)
    raw = re.sub(r"\bSCorp\b", "S-Corp", raw)
    raw = re.sub(r"\bSCorp([A-Z])", r"S-Corp \1", raw)
    raw = re.sub(r"\bCCorp([A-Z])", r"C-Corp \1", raw)
    raw = re.sub(r"SaaS([A-Z])", r"SaaS \1", raw)
    raw = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", raw)
    raw = re.sub(r"([A-Za-z]{2,})(\d+)", r"\1 \2", raw)
    raw = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", raw)
    raw = re.sub(r"\bSaa\s+S\b", "SaaS", raw, flags=re.IGNORECASE)

    slug_clean = str(slug or "").strip("/")
    is_raw_spoke_title = "/" in slug_clean and raw.lower().startswith(
        ("irs 2027 tax brackets ", "section 1031 calculator ", "section 179 calculator ")
    )
    if (
        not raw
        or is_raw_spoke_title
        or ("-" in raw and " " not in raw)
        or raw.lower().startswith(("prexvo-", "profithelm-", "gainhelm-"))
        or raw.lower()
        in (
            "tax & capital allocation intelligence",
            "federal student loan repayment",
            "calculator",
            "tool",
        )
    ):
        if "/" in slug_clean:
            sp_parts = [p for p in slug_clean.split("/") if p]
            if len(sp_parts) == 2 and sp_parts[0] == "irs-2027-tax-brackets":
                st_lbl = sp_parts[1].replace("-", " ").title().replace("Of", "of")
                raw = f"{st_lbl} 2027 Tax Brackets"
            elif len(sp_parts) == 2 and sp_parts[0] == "section-1031-calculator":
                st_lbl = sp_parts[1].replace("-", " ").title().replace("Of", "of")
                raw = f"{st_lbl} Section 1031 Exchange"
            elif len(sp_parts) == 2 and sp_parts[0] == "section-179-calculator":
                veh_map = dict(PROFITHELM_SECTION_179_VEHICLES)
                v_full = veh_map.get(sp_parts[1], f"{sp_parts[1].replace('-', ' ').title()} Section 179")
                raw = re.sub(r"\s+(?:Tax\s+)?(?:Deduction|Write-Off|Depreciation)?\s*Calculator.*$", "", v_full, flags=re.IGNORECASE).strip()
            else:
                raw = slug_clean.replace("/", " ").replace("-", " ").title()
        else:
            veh_map = dict(PROFITHELM_SECTION_179_VEHICLES)
            if slug_clean in veh_map:
                raw = re.sub(r"\s+(?:Tax\s+)?(?:Deduction|Write-Off|Depreciation)?\s*Calculator.*$", "", veh_map[slug_clean], flags=re.IGNORECASE).strip()
            else:
                raw = str(slug_clean or "statutory-model").replace("/", " ").replace("-", " ").title()

    raw = re.sub(r"\bS\s+Corp\b", "S-Corp", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\bC\s+Corp\b", "C-Corp", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\bR\s+(?:And|&)\s+D\b", "R&D", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\bK\s+1\b", "K-1", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\bW\s+([249])\b", r"W-\1", raw, flags=re.IGNORECASE)
    for acr in (
        "Rap", "Ibr", "Pslf", "Plus", "Save", "Paye", "Icr", "Irs", "Irc", "Tcja", "Qsbs",
        "Niit", "Amt", "Hysa", "Fica", "Qbi", "Gvwr", "Suv", "Apr", "Apy", "Roi", "Cmmc",
        "C3pao", "3pao", "Hipaa", "Hitrust", "Csf", "Iso", "Iec", "Nist", "Sprs", "Dfars",
        "Pci", "Dss", "Qsa", "Roc", "Asv", "Soc", "Ssae", "Aicpa", "Grc", "Obbba", "Hea",
        "Tila", "Mfs", "Mfj", "Idr", "Agi", "Seca", "Ftb",
    ):
        raw = re.sub(rf"\b{acr}\b", acr.upper(), raw, flags=re.IGNORECASE)
    raw = re.sub(r"\bSaas\b", "SaaS", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\bFedramp\b", "FedRAMP", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\bEphi\b", "ePHI", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\bPoa(?:&m|m)\b", "POA&M", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\bVs\b", "vs", raw)
    raw = re.sub(
        r"(?:\s+(?:Quantitative|Arbitrage|Differential|Calculation|Model))+\s*$",
        "",
        raw,
        flags=re.IGNORECASE,
    ).strip()

    # Join standalone single-letter uppercase tokens (B-HJ-Z) to adjacent words without touching S-Corp/W-2
    raw = re.sub(r"(?<![.\w-])([B-HJ-Z])\s+([A-Za-z0-9]+)(?![.\w-])", r"\1-\2", raw)
    raw = re.sub(r"([A-Za-z0-9]+)\s+([B-HJ-Z])(?![.\w-])", r"\1-\2", raw)
    raw = re.sub(r"\s+", " ", raw).strip(" :-,")
    words = raw.split()
    max_words = 7 if len(words) >= 7 and [w.lower() for w in words[5:7]] == ["section", "179"] else 6
    if len(words) > max_words:
        words = words[:max_words]
        while words and words[-1].lower() in ("and", "or", "vs", "vs.", "for", "with", "to", "in", "of", "on", "&", "&amp;", "section"):
            words.pop()
    result = " ".join(words).strip(" :-,")
    result = re.sub(r"(?<![.\w-])([B-HJ-Z])\s+([A-Za-z0-9]+)(?![.\w-])", r"\1-\2", result)
    result = re.sub(r"([A-Za-z0-9]+)\s+([B-HJ-Z])(?![.\w-])", r"\1-\2", result)
    return result or "Statutory Calculation Model"


def _build_repayment_loan_depth_spec(
    slug: str, topic_label: str, statutory_authority: str
) -> Dict[str, Any]:
    s_low = str(slug or "").strip().lower()
    restricted_ps = is_restricted_public_service_slug(slug)
    is_refi = any(tok in s_low for tok in ("refinance", "refinancing"))
    private_col_lbl = "10-Yr Standard Cap / Private Refi" if is_refi else "10-Yr Standard Cap / 5.25% Fixed"
    private_row_title = "Private Student Loan Refinance" if is_refi else "Fixed-Rate Credit Benchmark (TILA Reg Z)"
    private_row_desc = (
        "Lowers interest cost for high earners; permanently waives Title IV rights"
        if is_refi
        else "Fixed 5-to-20-year amortization benchmark; non-Title IV credit structure"
    )
    if restricted_ps:
        banner_html = (
            '      <div id="dynamic-commercial-intent-banner" class="serp-intent-banner" data-banner-mode="pslf_guardrail">\n'
            '        <div class="serp-intent-banner-text">\n'
            '          <strong>Live Title IV Public Service Guardrail (34 CFR 685.219):</strong> At <span id="serp-banner-metric-primary">$356 monthly</span> under RAP, isolating spouse income saves <span id="serp-banner-metric-secondary">$6,400/yr</span> while preserving 100% tax-free 120-payment PSLF eligibility.\n'
            '        </div>\n'
            '        <a href="#vetted-commercial-handoff" class="touch-target serp-intent-banner-btn">Review Official PSLF ECF &amp; NSLDS Verification Steps</a>\n'
            '      </div>'
        )
    else:
        banner_html = (
            '      <div id="dynamic-commercial-intent-banner" class="serp-intent-banner" data-banner-mode="repayment_commercial">\n'
            '        <div class="serp-intent-banner-text">\n'
            '          <strong>Live Repayment &amp; Rate Decision Signal:</strong> Your modeled RAP obligation is <span id="serp-banner-metric-primary">$356 monthly</span> (saving <span id="serp-banner-metric-secondary">$6,400/yr</span> via MFS filing isolation vs joint pooling). High-income borrowers not pursuing PSLF can compare soft-pull fixed APR offers against the $772 monthly 10-Year Standard cap.\n'
            '        </div>\n'
            '        <a href="#vetted-commercial-handoff" class="touch-target serp-intent-banner-btn">Review Vetted Soft-Pull Rate &amp; Title IV Execution Checklist</a>\n'
            '      </div>'
        )
    if is_refi:
        wb_h2 = f"Interactive Private Refinance APR Spread vs. Title IV Break-Even Matrix: {topic_label}"
        wb_intro = (
            f"Under <strong>{statutory_authority}</strong> and Truth in Lending Act (TILA) Regulation Z (12 CFR Part 1026), "
            f"refinancing federal Direct Loans into a private fixed-rate note only reduces lifetime cash outflow when your "
            f"household AGI exceeds Title IV subsidy thresholds and you do not qualify for 120-payment PSLF discharge. "
            f"Select a borrower archetype or adjust your income and balance below to compare federal RAP/IBR payments "
            f"against the 10-Year Standard cap and private refinance break-even benchmarks:"
        )
    elif "icr" in s_low or "income-contingent" in s_low:
        wb_h2 = f"Interactive ICR 20% Discretionary vs. 12-Year Fixed Payment Matrix: {topic_label}"
        wb_intro = (
            f"Under <strong>{statutory_authority}</strong> and 34 CFR 685.209(b), Income-Contingent Repayment (ICR) "
            f"calculates monthly obligations as the lesser of 20% of discretionary income above 100% HHS Poverty Guidelines "
            f"or a 12-year fixed amortization adjusted by the statutory Income Percentage Factor (IPF), and serves as the "
            f"sole legacy IDR pathway for consolidated Parent PLUS loans. Select a preset or adjust parameters below:"
        )
    elif "ibr-hardship" in s_low or "hardship-cap" in s_low:
        wb_h2 = f"Interactive IBR Partial Financial Hardship &amp; 10-Year Standard Cap Matrix: {topic_label}"
        wb_intro = (
            f"Under <strong>{statutory_authority}</strong> and HEA Section 493C (20 U.S.C. 1098e), Income-Based Repayment "
            f"(IBR) caps required monthly payments at the 10-Year Standard Repayment ceiling determined at plan entry, "
            f"while isolating spouse AGI when filing Married Filing Separately (MFS). Select an archetype preset below:"
        )
    else:
        wb_h2 = f"Interactive Filing Status, Spouse AGI &amp; Multi-Plan Matrix: {topic_label}"
        wb_intro = (
            f"Under <strong>{statutory_authority}</strong> and 34 CFR 685.209, monthly income-driven obligations "
            f"depend on whether you isolate individual Adjusted Gross Income via Married Filing Separately (MFS) "
            f"or pool household income via Married Filing Jointly (MFJ). Select an archetype preset or adjust "
            f"your household parameters below to compare Repayment Assistance Plan (RAP), New/Old IBR, and "
            f"10-Year Standard caps side by side:"
        )
    return {
        "workbench_mode": "repayment_loan",
        "workbench_h2": wb_h2,
        "workbench_intro": wb_intro,
        "presets": [
            (
                "Public Service Resident ($68k AGI / $145k Debt)",
                '{"agi":68000,"loan_balance":145000,"family_size":2,"serp-loan-agi":68000,"serp-loan-spouse-agi":52000,"serp-loan-balance":145000,"serp-loan-filing":"pslf_track"}',
            ),
            (
                "Dual-Income MFS Shield ($82k + $78k Spouse AGI)",
                '{"agi":82000,"loan_balance":74000,"family_size":3,"serp-loan-agi":82000,"serp-loan-spouse-agi":78000,"serp-loan-balance":74000,"serp-loan-filing":"mfs_new"}',
            ),
            (
                "Joint MFJ Household ($140k Combined / $55k Debt)",
                '{"agi":140000,"loan_balance":55000,"family_size":4,"serp-loan-agi":85000,"serp-loan-spouse-agi":55000,"serp-loan-balance":55000,"serp-loan-filing":"mfj_new"}',
            ),
            (
                "High-Earner Fixed Payoff ($195k AGI / $92k Debt)",
                '{"agi":195000,"loan_balance":92000,"family_size":1,"serp-loan-agi":195000,"serp-loan-spouse-agi":0,"serp-loan-balance":92000,"serp-loan-filing":"mfs_old"}',
            ),
        ],
        "inputs_html": (
            '        <div class="serp-field-group">\n'
            '          <label for="serp-loan-agi" class="serp-field-label">Borrower AGI ($)</label>\n'
            '          <input type="number" id="serp-loan-agi" name="serp-loan-agi" class="touch-target serp-sub-input" min="0" max="2000000" step="1000" value="78000" />\n'
            '        </div>\n'
            '        <div class="serp-field-group">\n'
            '          <label for="serp-loan-spouse-agi" class="serp-field-label">Spouse AGI ($ for MFJ vs MFS)</label>\n'
            '          <input type="number" id="serp-loan-spouse-agi" name="serp-loan-spouse-agi" class="touch-target serp-sub-input" min="0" max="2000000" step="1000" value="64000" />\n'
            '        </div>\n'
            '        <div class="serp-field-group">\n'
            '          <label for="serp-loan-balance" class="serp-field-label">Direct Loan Principal ($)</label>\n'
            '          <input type="number" id="serp-loan-balance" name="serp-loan-balance" class="touch-target serp-sub-input" min="1000" max="1000000" step="1000" value="68000" />\n'
            '        </div>\n'
            '        <div class="serp-field-group">\n'
            '          <label for="serp-loan-filing" class="serp-field-label">Tax Filing Status &amp; Cohort (34 CFR 685.209)</label>\n'
            '          <select id="serp-loan-filing" name="serp-loan-filing" class="touch-target serp-sub-select">\n'
            '            <option value="mfs_new" selected="selected">Married Filing Separately (Isolates Borrower AGI: Post-2014 10%)</option>\n'
            '            <option value="mfj_new">Married Filing Jointly (Pools Household AGI: Post-2014 10%)</option>\n'
            '            <option value="mfs_old">Pre-2014 Legacy Borrower (MFS: 15% Old IBR vs 10% RAP)</option>\n'
            '            <option value="pslf_track">PSLF 120-Payment Track (34 CFR 685.219 Tax-Free Discharge)</option>\n'
            '          </select>\n'
            '        </div>'
        ),
        "metrics_meta": [
            ("serp-out-primary", "Monthly RAP Payment (225% Poverty)", "$356"),
            ("serp-out-secondary", "Monthly Statutory IBR (150% Poverty)", "$454"),
            ("serp-out-tertiary", "MFS vs MFJ Annual Repayment Saved", "$6,400"),
            ("serp-out-quaternary", private_col_lbl, "$772 / $584"),
        ],
        "svg_left_label": "Annual Retained Income: $73,728 (94.5%)",
        "svg_right_label": "Annual RAP Obligation: $4,272 (5.5%)",
        "svg_left_width": "567",
        "svg_right_x": "567",
        "svg_right_width": "33",
        "table_h3": f"Statutory Reference Schedule: {topic_label} Title IV Multi-Plan Comparison Matrix",
        "table_headers": [
            "Repayment Plan / Option",
            "Governing Statutory Authority",
            "Poverty Exemption &amp; Rate Formula",
            "Unpaid Interest &amp; Forgiveness Horizon",
        ],
        "table_rows": [
            (
                "Repayment Assistance Plan (RAP)",
                "OBBBA Title VIII Subtitle B; 34 CFR Part 685",
                "10% of AGI above 225% HHS Poverty ($35,212 Single)",
                "100% unpaid undergraduate interest subsidy; 240-to-300-month cap",
            ),
            (
                "New IBR (Post-July 1, 2014)",
                "20 U.S.C. 1098e(e); 34 CFR 685.209",
                "10% of AGI above 150% HHS Poverty ($23,475 Single)",
                "Capped at 10-Year Standard payment; 20-year (240-month) discharge",
            ),
            (
                "Old IBR (Pre-July 1, 2014)",
                "20 U.S.C. 1098e(b); 34 CFR 685.221",
                "15% of AGI above 150% HHS Poverty ($23,475 Single)",
                "Capped at 10-Year Standard payment; 25-year (300-month) discharge",
            ),
            (
                "Pay As You Earn (PAYE)",
                "34 CFR 685.209(a) Statutory Transition Rules",
                "10% of AGI above 150% HHS Poverty ($23,475 Single)",
                "10-Year Standard payment ceiling; 20-year (240-month) forgiveness",
            ),
            (
                "Income-Contingent Repayment (ICR)",
                "34 CFR 685.209(b); HEA Section 455(d)",
                "20% of AGI above 100% HHS Poverty ($15,650 Single)",
                "Sole IDR plan eligible for consolidated Parent PLUS loans (25 years)",
            ),
            (
                "PSLF 120-Payment Track &amp; Buyback",
                "34 CFR 685.219 &amp; 26 U.S.C. 108(f)(1)",
                "Qualifying RAP/IBR/PAYE/ICR payment x 120 months",
                "100% federal tax-free principal and interest discharge at month 120",
            ),
            (
                private_row_title,
                "TILA Regulation Z (12 CFR Part 1026)",
                "Credit-underwritten fixed APR (5 to 20 year term)",
                private_row_desc,
            ),
        ],
        "banner_html": banner_html,
    }


def _build_crypto_depth_spec(topic_label: str, statutory_authority: str) -> Dict[str, Any]:
    return {
        "workbench_mode": "crypto",
        "workbench_h2": f"Interactive Cost-Basis Lot Sub-Ledger (FIFO vs HIFO vs LIFO) &amp; Form 8949 Reconciliation: {topic_label}",
        "workbench_intro": (
            f"Top SERP tax engines and <strong>{statutory_authority}</strong> require reconciling gross disposal proceeds "
            f"from IRS Form 1099-DA against acquisition cost basis, deductible on-chain gas and exchange fees, "
            f"capital loss harvesting offsets, and wallet-by-wallet Specific Identification (HIFO vs FIFO) under "
            f"IRS Rev. Proc. 2024-28. Select an investor archetype or enter your transaction figures below:"
        ),
        "presets": [
            (
                "Active DeFi &amp; Spot Trader ($85k Proceeds / HIFO)",
                '{"crypto-short-term":38000,"crypto-long-term":15000,"crypto-staking":4200,"crypto-income":145000,"serp-crypto-proceeds":85000,"serp-crypto-basis":32000,"serp-crypto-fees":1250,"serp-crypto-losses":4500,"serp-crypto-method":"hifo"}',
            ),
            (
                "Long-Term HODLer Disposal ($240k Proceeds / $65k Basis)",
                '{"crypto-short-term":0,"crypto-long-term":175000,"crypto-staking":0,"crypto-income":185000,"serp-crypto-proceeds":240000,"serp-crypto-basis":65000,"serp-crypto-fees":1800,"serp-crypto-losses":8200,"serp-crypto-method":"hifo"}',
            ),
            (
                "Staking &amp; Validator Node ($45k Proceeds + Yield)",
                '{"crypto-short-term":12000,"crypto-long-term":18000,"crypto-staking":28500,"crypto-income":160000,"serp-crypto-proceeds":45000,"serp-crypto-basis":15000,"serp-crypto-fees":650,"serp-crypto-losses":3000,"serp-crypto-method":"fifo"}',
            ),
            (
                "High-Net-Worth NIIT Tier ($620k Proceeds / 23.8% Cap)",
                '{"crypto-short-term":95000,"crypto-long-term":310000,"crypto-staking":18000,"crypto-income":480000,"serp-crypto-proceeds":620000,"serp-crypto-basis":215000,"serp-crypto-fees":4200,"serp-crypto-losses":22000,"serp-crypto-method":"hifo"}',
            ),
        ],
        "inputs_html": (
            '        <div class="serp-field-group">\n'
            '          <label for="serp-crypto-proceeds" class="serp-field-label">Gross Disposal Proceeds ($ Form 1099-DA)</label>\n'
            '          <input type="number" id="serp-crypto-proceeds" name="serp-crypto-proceeds" class="touch-target serp-sub-input" min="0" max="50000000" step="500" value="85000" />\n'
            '        </div>\n'
            '        <div class="serp-field-group">\n'
            '          <label for="serp-crypto-basis" class="serp-field-label">Acquisition Cost Basis ($ IRC 1012)</label>\n'
            '          <input type="number" id="serp-crypto-basis" name="serp-crypto-basis" class="touch-target serp-sub-input" min="0" max="50000000" step="500" value="32000" />\n'
            '        </div>\n'
            '        <div class="serp-field-group">\n'
            '          <label for="serp-crypto-fees" class="serp-field-label">Deductible Gas &amp; Exchange Fees ($)</label>\n'
            '          <input type="number" id="serp-crypto-fees" name="serp-crypto-fees" class="touch-target serp-sub-input" min="0" max="1000000" step="50" value="1250" />\n'
            '        </div>\n'
            '        <div class="serp-field-group">\n'
            '          <label for="serp-crypto-losses" class="serp-field-label">Capital Loss Harvesting Offset ($)</label>\n'
            '          <input type="number" id="serp-crypto-losses" name="serp-crypto-losses" class="touch-target serp-sub-input" min="0" max="5000000" step="250" value="4500" />\n'
            '        </div>\n'
            '        <div class="serp-field-group">\n'
            '          <label for="serp-crypto-method" class="serp-field-label">Rev. Proc. 2024-28 Lot Accounting Method</label>\n'
            '          <select id="serp-crypto-method" name="serp-crypto-method" class="touch-target serp-sub-select">\n'
            '            <option value="hifo" selected="selected">HIFO (Specific ID Highest-In First-Out)</option>\n'
            '            <option value="fifo">FIFO (Chronological First-In First-Out)</option>\n'
            '            <option value="lifo">LIFO (Specific ID Last-In First-Out)</option>\n'
            '          </select>\n'
            '        </div>'
        ),
        "metrics_meta": [
            ("serp-out-primary", "Net Taxable Gain (Form 8949)", "$47,250"),
            ("serp-out-secondary", "Estimated Capital Gains + NIIT Tax", "$11,246"),
            ("serp-out-tertiary", "HIFO vs FIFO Lot Alpha Saved", "$3,402"),
            ("serp-out-quaternary", "Net Post-Tax Proceeds Retained", "$73,754"),
        ],
        "svg_left_label": "Net Retained Proceeds: $73,754 (86.8%)",
        "svg_right_label": "Estimated Tax Exposure: $11,246 (13.2%)",
        "svg_left_width": "521",
        "svg_right_x": "521",
        "svg_right_width": "79",
        "table_h3": f"Statutory Reference Schedule: {topic_label} 2026 Digital Asset Tax &amp; Form 1099-DA Matrix",
        "table_headers": [
            "Digital Asset Tax Regime / Event",
            "Governing IRS Statutory Authority",
            "2026 Single / MFJ Thresholds &amp; Rates",
            "Mandatory Reporting Form &amp; Basis Rule",
        ],
        "table_rows": [
            (
                "Long-Term Capital Gains (Held &gt; 365 Days)",
                "IRC Section 1(h) &amp; Section 1222(3)",
                "0% up to $48,350 ($96,700 MFJ); 15% up to $533,400 ($600,050 MFJ); 20% above",
                "IRS Form 8949 Part II (Box D/E/F) &amp; Schedule D",
            ),
            (
                "Short-Term Disposals &amp; Token Swaps (Held &lt;= 365 Days)",
                "IRC Section 1(j) &amp; Section 1001",
                "Taxed at ordinary brackets: 10%, 12%, 22%, 24%, 32%, 35%, 37%",
                "IRS Form 8949 Part I (Box A/B/C); crypto-to-crypto swaps are taxable",
            ),
            (
                "Net Investment Income Tax (NIIT Surtax)",
                "IRC Section 1411(a)(1)",
                "3.8% surtax on MAGI above $200,000 Single / $250,000 Married Jointly",
                "IRS Form 8960; stacks on top of 15%/20% LTCG (23.8% max federal)",
            ),
            (
                "Wallet-by-Wallet Cost-Basis Lot Allocation",
                "IRS Rev. Proc. 2024-28 &amp; IRC Section 1012",
                "HIFO / LIFO Specific Identification vs Chronological FIFO",
                "Requires per-wallet lot records prior to disposal to avoid zero-basis audit",
            ),
            (
                "Custodial Broker Digital Asset Reporting",
                "IRC Section 6045 &amp; Treasury Final Broker Regs",
                "Mandatory gross proceeds reporting effective 2025/2026 tax filings",
                "IRS Form 1099-DA reconciled against non-custodial transfer logs",
            ),
            (
                "Staking, Mining &amp; Airdrop Ordinary Income",
                "IRS Rev. Rul. 2023-14 &amp; Notice 2014-21",
                "10% to 37% ordinary income at exact timestamp of dominion and control",
                "Schedule 1 (Form 1040); receipt FMV establishes subsequent Form 8949 basis",
            ),
            (
                "Capital Loss Harvesting &amp; Carryforward",
                "IRC Section 1211(b) &amp; Section 1212(b)",
                "100% offset against capital gains plus $3,000 ($1,500 MFS) ordinary income",
                "Unlimited lifetime carryforward of unused net capital losses on Schedule D",
            ),
        ],
        "banner_html": (
            '      <div id="dynamic-commercial-intent-banner" class="serp-intent-banner" data-banner-mode="crypto">\n'
            '        <div class="serp-intent-banner-text">\n'
            '          <strong>Live Form 8949 &amp; 1099-DA Audit Signal:</strong> On <span id="serp-banner-metric-primary">$47,250</span> in net taxable gains, wallet-by-wallet HIFO lot selection saves <span id="serp-banner-metric-secondary">$3,402</span> vs chronological FIFO under IRS Rev. Proc. 2024-28. Automate multi-wallet API synchronization before importing broker Form 1099-DA files.\n'
            '        </div>\n'
            '        <a href="#vetted-commercial-handoff" class="touch-target serp-intent-banner-btn">Compare Vetted Form 8949 &amp; 1099-DA Subledger Platforms</a>\n'
            '      </div>'
        ),
    }


def _build_sec179_depth_spec(topic_label: str, statutory_authority: str) -> Dict[str, Any]:
    return {
        "workbench_mode": "sec179",
        "workbench_h2": f"Interactive GVWR Property Class, IRC 179(b)(3) Income Cap &amp; Financed Cash-Flow Arbitrage: {topic_label}",
        "workbench_intro": (
            f"Under <strong>{statutory_authority}</strong>, first-year equipment and commercial vehicle expensing "
            f"is governed by three statutory gates on IRS Form 4562: asset GVWR classification under IRC Section "
            f"179(b)(5) and Section 280F, active trade or business taxable income under IRC Section 179(b)(3), and "
            f"non-tax capital lease financing arbitrage where Year-1 tax savings exceed Year-1 debt service:"
        ),
        "presets": [
            (
                "Heavy Work Truck / Cargo Van &gt;6,000 lbs ($95k Uncapped)",
                '{"sec179-cost":95000,"sec179-rate":35,"serp-179-cost":95000,"serp-179-income":280000,"serp-179-apr":6.5,"serp-179-class":"machinery_100"}',
            ),
            (
                "Heavy SUV 6,000 to 14,000 lbs ($110k / $30,500 SUV Cap)",
                '{"sec179-cost":110000,"sec179-rate":37,"serp-179-cost":110000,"serp-179-income":350000,"serp-179-apr":6.75,"serp-179-class":"heavy_suv"}',
            ),
            (
                "Commercial Machinery &amp; Medical Fleet ($450k / 100% Write-Off)",
                '{"sec179-cost":450000,"sec179-rate":35,"serp-179-cost":450000,"serp-179-income":820000,"serp-179-apr":6.25,"serp-179-class":"machinery_100"}',
            ),
            (
                "Section 179 Phase-Out Stress ($4.35M Additions / $4.09M Cap)",
                '{"sec179-cost":4350000,"sec179-rate":37,"serp-179-cost":4350000,"serp-179-income":5200000,"serp-179-apr":5.9,"serp-179-class":"machinery_100"}',
            ),
        ],
        "inputs_html": (
            '        <div class="serp-field-group">\n'
            '          <label for="serp-179-cost" class="serp-field-label">Qualified Asset Cost ($ Placed in Service)</label>\n'
            '          <input type="number" id="serp-179-cost" name="serp-179-cost" class="touch-target serp-sub-input" min="0" max="15000000" step="1000" value="145000" />\n'
            '        </div>\n'
            '        <div class="serp-field-group">\n'
            '          <label for="serp-179-income" class="serp-field-label">Active Business Taxable Income Cap ($ IRC 179(b)(3))</label>\n'
            '          <input type="number" id="serp-179-income" name="serp-179-income" class="touch-target serp-sub-input" min="0" max="25000000" step="5000" value="320000" />\n'
            '        </div>\n'
            '        <div class="serp-field-group">\n'
            '          <label for="serp-179-apr" class="serp-field-label">60-Month Equipment Finance APR (%)</label>\n'
            '          <input type="number" id="serp-179-apr" name="serp-179-apr" class="touch-target serp-sub-input" min="0" max="25" step="0.25" value="6.75" />\n'
            '        </div>\n'
            '        <div class="serp-field-group">\n'
            '          <label for="serp-179-class" class="serp-field-label">Asset GVWR &amp; IRC 179 / 280F Property Class</label>\n'
            '          <select id="serp-179-class" name="serp-179-class" class="touch-target serp-sub-select">\n'
            '            <option value="machinery_100" selected="selected">Machinery / Software / Heavy Truck &gt;6,000 lbs (Uncapped 100%)</option>\n'
            '            <option value="heavy_suv">Heavy SUV 6,000 to 14,000 lbs GVWR ($30,500 IRC 179(b)(5) Cap + Bonus)</option>\n'
            '            <option value="passenger_auto">Luxury Passenger Auto &lt;6,000 lbs GVWR ($20,400 IRC 280F Year-1 Cap)</option>\n'
            '          </select>\n'
            '        </div>'
        ),
        "metrics_meta": [
            ("serp-out-primary", "Year-1 Total Statutory Write-Off", "$145,000"),
            ("serp-out-secondary", "Year-1 Cash Tax Saved (at 35%)", "$50,750"),
            ("serp-out-tertiary", "Year-1 Financed Debt Service (60m)", "$34,248"),
            ("serp-out-quaternary", "Year-1 Net Cash-Flow Surplus", "+$16,502"),
        ],
        "svg_left_label": "Net After-Tax Equipment Cost: $94,250 (65.0%)",
        "svg_right_label": "Year-1 Tax Shield Recovered: $50,750 (35.0%)",
        "svg_left_width": "390",
        "svg_right_x": "390",
        "svg_right_width": "210",
        "table_h3": f"Statutory Reference Schedule: {topic_label} Form 4562 &amp; GVWR Weight Class Matrix",
        "table_headers": [
            "Equipment / Vehicle Asset Category",
            "Governing IRC Statutory Authority",
            "2026 Section 179 Deduction Ceiling",
            "Bonus Depreciation &amp; MACRS Treatment",
        ],
        "table_rows": [
            (
                "Commercial Machinery, Medical/Dental &amp; Off-The-Shelf Software",
                "IRC Section 179(a) &amp; Section 179(d)(1)",
                "Section 179 deduction limit of $2,560,000 (phaseout threshold of $4,090,000)",
                "100% OBBBA Section 168(k) bonus + 5/7-year MACRS on any excess basis",
            ),
            (
                "Heavy Pickup Truck (&gt;6,000 lbs GVWR &amp; &gt;=6-ft Cargo Bed) or Cargo Van",
                "IRC Section 179(b)(5)(B) Work Vehicle Exception",
                "Exempt from SUV cap; eligible for full $2,560,000 Section 179 limit",
                "100% first-year deduction when &gt;50% qualified business use on Form 4562",
            ),
            (
                "Heavy Passenger SUV (6,000 to 14,000 lbs GVWR, &lt;6-ft Bed)",
                "IRC Section 179(b)(5)(A) Heavy SUV Cap",
                "$30,500 statutory Section 179 cap ($31,300 for 2025 inflation-adjusted schedule)",
                "Remaining basis eligible for Section 168(k) bonus + 5-year 200% DB MACRS",
            ),
            (
                "Standard Passenger Automobile (&lt;6,000 lbs GVWR Sedan / Crossover)",
                "IRC Section 280F(a)(1)(A) Luxury Auto Limits",
                "$20,400 total Year-1 cap ($12,400 base + $8,000 bonus depreciation)",
                "Year 2: $19,800; Year 3: $11,900; Year 4+: $7,160 per year until depreciated",
            ),
            (
                "Qualified Improvement Property (QIP Non-Residential Interior)",
                "IRC Section 168(e)(6) &amp; Section 179(e)",
                "Eligible for $2,560,000 Section 179 cap (HVAC, roof, fire/security systems)",
                "15-year straight-line MACRS recovery period; bonus depreciation eligible",
            ),
            (
                "Active Business Income Limitation &amp; Carryforward",
                "IRC Section 179(b)(3)(A) &amp; Form 4562 Line 11",
                "Capped at aggregate net taxable income from active trades or businesses",
                "Disallowed Section 179 carries forward indefinitely; 168(k) can create NOL",
            ),
        ],
        "banner_html": (
            '      <div id="dynamic-commercial-intent-banner" class="serp-intent-banner" data-banner-mode="sec179">\n'
            '        <div class="serp-intent-banner-text">\n'
            '          <strong>Live Section 179 Financing Arbitrage Signal:</strong> Claiming a <span id="serp-banner-metric-primary">$145,000</span> Year-1 deduction generates <span id="serp-banner-metric-secondary">$50,750</span> in immediate tax savings versus $34,248 in Year-1 equipment finance payments (+$16,502 net Year-1 cash surplus when placed in service by December 31).\n'
            '        </div>\n'
            '        <a href="#vetted-commercial-handoff" class="touch-target serp-intent-banner-btn">Review Vetted Section 179 Financing &amp; CPA Accounting Partners</a>\n'
            '      </div>'
        ),
    }


def _build_sec1031_depth_spec(topic_label: str, statutory_authority: str) -> Dict[str, Any]:
    return {
        "workbench_mode": "sec1031",
        "workbench_h2": f"Interactive Mortgage Boot, Section 1250 Recapture &amp; 45/180-Day Deadline Sub-Ledger: {topic_label}",
        "workbench_intro": (
            f"Under <strong>{statutory_authority}</strong> and Treasury Reg. 1.1031(b)-1(c), full capital gains and "
            f"25% Section 1250 depreciation recapture deferral on IRS Form 8824 requires trading equal or up in "
            f"both net purchase price AND replacement mortgage debt (or offsetting any debt reduction with fresh "
            f"cash equity) while meeting strict 45-day identification and 180-day closing windows:"
        ),
        "presets": [
            (
                "Zero-Boot Up-Trade ($2.5M Sale to $2.85M Replacement)",
                '{"sec1031-sale-price":2500000,"sec1031-basis":950000,"sec1031-depreciation":380000,"sec1031-replacement":2850000,"serp-1031-rel-debt":950000,"serp-1031-rep-debt":1150000,"serp-1031-costs":42000,"serp-1031-depr":380000,"serp-1031-close-days":15}',
            ),
            (
                "Partial Mortgage Boot Trap ($950k Old Debt to $700k New Debt)",
                '{"sec1031-sale-price":2500000,"sec1031-basis":950000,"sec1031-depreciation":380000,"sec1031-replacement":2350000,"serp-1031-rel-debt":950000,"serp-1031-rep-debt":700000,"serp-1031-costs":38000,"serp-1031-depr":380000,"serp-1031-close-days":28}',
            ),
            (
                "Multifamily Portfolio Exchange ($4.8M Sale / $850k Sec 1250)",
                '{"sec1031-sale-price":4800000,"sec1031-basis":1900000,"sec1031-depreciation":850000,"sec1031-replacement":5400000,"serp-1031-rel-debt":2100000,"serp-1031-rep-debt":2500000,"serp-1031-costs":68000,"serp-1031-depr":850000,"serp-1031-close-days":5}',
            ),
            (
                "Urgent Day-40 Identification Window ($1.4M NNN Retail)",
                '{"sec1031-sale-price":1400000,"sec1031-basis":520000,"sec1031-depreciation":210000,"sec1031-replacement":1550000,"serp-1031-rel-debt":580000,"serp-1031-rep-debt":680000,"serp-1031-costs":26000,"serp-1031-depr":210000,"serp-1031-close-days":40}',
            ),
        ],
        "inputs_html": (
            '        <div class="serp-field-group">\n'
            '          <label for="serp-1031-rel-debt" class="serp-field-label">Relinquished Debt Payoff ($ Old Mortgage)</label>\n'
            '          <input type="number" id="serp-1031-rel-debt" name="serp-1031-rel-debt" class="touch-target serp-sub-input" min="0" max="50000000" step="10000" value="950000" />\n'
            '        </div>\n'
            '        <div class="serp-field-group">\n'
            '          <label for="serp-1031-rep-debt" class="serp-field-label">Replacement Mortgage Debt ($ New Loan)</label>\n'
            '          <input type="number" id="serp-1031-rep-debt" name="serp-1031-rep-debt" class="touch-target serp-sub-input" min="0" max="50000000" step="10000" value="1150000" />\n'
            '        </div>\n'
            '        <div class="serp-field-group">\n'
            '          <label for="serp-1031-costs" class="serp-field-label">Qualified Intermediary &amp; Closing Costs ($)</label>\n'
            '          <input type="number" id="serp-1031-costs" name="serp-1031-costs" class="touch-target serp-sub-input" min="0" max="2000000" step="1000" value="42000" />\n'
            '        </div>\n'
            '        <div class="serp-field-group">\n'
            '          <label for="serp-1031-depr" class="serp-field-label">Cumulative Prior Depreciation ($ IRC 1250)</label>\n'
            '          <input type="number" id="serp-1031-depr" name="serp-1031-depr" class="touch-target serp-sub-input" min="0" max="20000000" step="5000" value="380000" />\n'
            '        </div>\n'
            '        <div class="serp-field-group">\n'
            '          <label for="serp-1031-close-days" class="serp-field-label">Elapsed Days Since Sale Closing (0 to 180)</label>\n'
            '          <input type="number" id="serp-1031-close-days" name="serp-1031-close-days" class="touch-target serp-sub-input" min="0" max="180" step="1" value="15" />\n'
            '        </div>'
        ),
        "metrics_meta": [
            ("serp-out-primary", "Net Taxable Mortgage/Cash Boot", "$0"),
            ("serp-out-secondary", "Total Tax Deferred (LTCG + §1250 + NIIT)", "$486,400"),
            ("serp-out-tertiary", "Form 8824 Line 25 Carryover Basis", "$1,478,000"),
            ("serp-out-quaternary", "Statutory Window (Day 45 ID / 180 Close)", "30d ID / 165d Close"),
        ],
        "svg_left_label": "Reinvested Exchange Equity: $1,508,000 (75.6%)",
        "svg_right_label": "Deferred Tax Preserved: $486,400 (24.4%)",
        "svg_left_width": "454",
        "svg_right_x": "454",
        "svg_right_width": "146",
        "table_h3": f"Statutory Reference Schedule: {topic_label} Form 8824 Boot, Recapture &amp; Identification Rules",
        "table_headers": [
            "Section 1031 Statutory Component",
            "Governing IRC / Treasury Authority",
            "Tax Rate or Statutory Window",
            "Form 8824 Reconciliation &amp; Safe Harbor",
        ],
        "table_rows": [
            (
                "45-Day Written Identification Period",
                "IRC Section 1031(a)(3)(A); Treas. Reg. 1.1031(k)-1(c)",
                "Strictly 45 calendar days from relinquished property transfer",
                "3-Property Rule (any value), 200% FMV Rule, or 95% Acquisition Exception",
            ),
            (
                "180-Day Exchange Completion Period",
                "IRC Section 1031(a)(3)(B); IRS Form 8824",
                "Earlier of 180 calendar days OR tax return due date (with extensions)",
                "Q4 closings must file Form 4868 / Form 7004 to preserve full 180 days",
            ),
            (
                "Mortgage Boot (Net Debt Relief)",
                "IRC Section 1031(b); Treas. Reg. 1.1031(b)-1(c)",
                "Taxed up to realized gain at 15%/20% LTCG + 25% §1250 + 3.8% NIIT",
                "Offset debt reduction with new replacement debt or fresh cash in, never cash out",
            ),
            (
                "Unrecaptured Section 1250 Depreciation",
                "IRC Section 1(h)(1)(E) &amp; Section 1250",
                "25% federal maximum rate on cumulative straight-line real property depreciation",
                "100% deferred into replacement carryover basis on Form 8824 Line 25",
            ),
            (
                "Qualified Intermediary (QI) Safe Harbor",
                "Treas. Reg. 1.1031(k)-1(g)(4)",
                "Written exchange assignment executed BEFORE relinquished closing",
                "Prevents constructive receipt of funds under Treas. Reg. 1.1031(k)-1(f)",
            ),
            (
                "State Clawback &amp; Out-of-State Tracking",
                "CA R&amp;TC Section 18032.5 (FTB Form 3840) / OR-24",
                "Up to 13.3% CA state tax deferred but tracked annually",
                "Requires annual CA FTB Form 3840 informational filing even after moving out of state",
            ),
        ],
        "banner_html": (
            '      <div id="dynamic-commercial-intent-banner" class="serp-intent-banner" data-banner-mode="sec1031">\n'
            '        <div class="serp-intent-banner-text">\n'
            '          <strong>Live Qualified Intermediary &amp; Boot Signal:</strong> Your exchange structure shows <span id="serp-banner-metric-primary">$0</span> in taxable boot while deferring <span id="serp-banner-metric-secondary">$486,400</span> in combined federal, 25% Section 1250 recapture, and state tax. Execute your written QI Exchange Assignment before escrow closes.\n'
            '        </div>\n'
            '        <a href="#vetted-commercial-handoff" class="touch-target serp-intent-banner-btn">Review Bonded Qualified Intermediary (IPX1031) Vetting Checklist</a>\n'
            '      </div>'
        ),
    }


def _build_tax_brackets_depth_spec(
    s_low: str, topic_label: str, statutory_authority: str
) -> Dict[str, Any]:
    is_ca = "california" in s_low or "ca-tax" in s_low
    if not is_ca:
        from pseofactory.proprietary_signals import build_non_ca_state_tax_brackets_spec

        return build_non_ca_state_tax_brackets_spec(
            s_low=s_low,
            topic_label=topic_label,
            statutory_authority=statutory_authority,
        )
    state_focus_lbl = "California FTB Form 540 (1.0% to 13.3% + 1.1% SDI)"
    return {
        "workbench_mode": "tax_brackets",
        "workbench_h2": f"Interactive 401(k)/HSA Pre-Tax Shield, PTET Election &amp; {state_focus_lbl} Sub-Ledger: {topic_label}",
        "workbench_intro": (
            f"Competitor tax calculators rank by combining top-line bracket lookups with above-the-line "
            f"retirement/health deductions (IRC Section 401(k) $23,500 limit and IRC Section 223 HSA), "
            f"Pass-Through Entity Tax (PTET Notice 2020-75 / CA AB 150) SALT cap workarounds, and complete "
            f"federal plus state marginal schedules under <strong>{statutory_authority}</strong>:"
        ),
        "presets": [
            (
                "Median Professional ($125k Gross / $23.5k 401k)",
                '{"inp-income":125000,"tax-income":125000,"serp-tax-gross":125000,"serp-tax-pretax":23500,"serp-tax-ptet":0,"serp-tax-regime":"2026_active"}',
            ),
            (
                "Dual-Earner Household ($285k Gross / Max 401k + HSA)",
                '{"inp-income":285000,"tax-income":285000,"serp-tax-gross":285000,"serp-tax-pretax":55550,"serp-tax-ptet":12000,"serp-tax-regime":"2026_active"}',
            ),
            (
                "S-Corp Owner PTET Shield ($450k Gross / 9.3% AB 150)",
                '{"inp-income":450000,"tax-income":450000,"serp-tax-gross":450000,"serp-tax-pretax":69000,"serp-tax-ptet":35400,"serp-tax-regime":"ptet_shield"}',
            ),
            (
                "2027 Sunset Reversion Stress ($650k Gross / 39.6% Top Rate)",
                '{"inp-income":650000,"tax-income":650000,"serp-tax-gross":650000,"serp-tax-pretax":55550,"serp-tax-ptet":18000,"serp-tax-regime":"2027_sunset"}',
            ),
        ],
        "inputs_html": (
            '        <div class="serp-field-group">\n'
            '          <label for="serp-tax-gross" class="serp-field-label">Gross Household / Pass-Through Income ($)</label>\n'
            '          <input type="number" id="serp-tax-gross" name="serp-tax-gross" class="touch-target serp-sub-input" min="0" max="20000000" step="1000" value="185000" />\n'
            '        </div>\n'
            '        <div class="serp-field-group">\n'
            '          <label for="serp-tax-pretax" class="serp-field-label">Pre-Tax 401(k), Solo 401(k) &amp; HSA Deductions ($)</label>\n'
            '          <input type="number" id="serp-tax-pretax" name="serp-tax-pretax" class="touch-target serp-sub-input" min="0" max="500000" step="500" value="31000" />\n'
            '        </div>\n'
            '        <div class="serp-field-group">\n'
            '          <label for="serp-tax-ptet" class="serp-field-label">PTET (AB 150) / Itemized SALT Deduction ($)</label>\n'
            '          <input type="number" id="serp-tax-ptet" name="serp-tax-ptet" class="touch-target serp-sub-input" min="0" max="2000000" step="500" value="15400" />\n'
            '        </div>\n'
            '        <div class="serp-field-group">\n'
            '          <label for="serp-tax-regime" class="serp-field-label">Statutory Tax Regime &amp; SALT Election</label>\n'
            '          <select id="serp-tax-regime" name="serp-tax-regime" class="touch-target serp-sub-select">\n'
            '            <option value="2026_active" selected="selected">2026 Current Law (10% to 37% Federal + State Schedule)</option>\n'
            '            <option value="2027_sunset">2027 Post-Sunset Reversion (10% to 39.6% Federal + State)</option>\n'
            '            <option value="ptet_shield">S-Corp / LLC PTET Election (Notice 2020-75 / CA AB 150 Shield)</option>\n'
            '          </select>\n'
            '        </div>'
        ),
        "metrics_meta": [
            ("serp-out-primary", "Adjusted Taxable Income Base", "$138,600"),
            ("serp-out-secondary", "Combined Federal + State/SDI Tax", "$34,927"),
            ("serp-out-tertiary", "401(k)/HSA &amp; PTET Tax Saved", "$14,848"),
            ("serp-out-quaternary", "Net After-Tax Cash Retained", "$150,073"),
        ],
        "svg_left_label": "Net Take-Home Cash Flow: $150,073 (81.1%)",
        "svg_right_label": "Combined Tax Liability: $34,927 (18.9%)",
        "svg_left_width": "487",
        "svg_right_x": "487",
        "svg_right_width": "113",
        "table_h3": f"Statutory Reference Schedule: {topic_label} Complete 10-Tier California FTB 540 &amp; Federal Rate Matrix",
        "table_headers": [
            "California State Bracket &amp; Federal Tier",
            "Single Taxable Income Thresholds (FTB 540)",
            "Married Filing Jointly Thresholds (FTB 540)",
            "Head of Household &amp; Statutory Surcharges",
        ],
        "table_rows": [
            (
                "CA State Tier 1: 1.0% State Rate (10% Fed)",
                "$0 to $10,756 Single",
                "$0 to $21,512 Married Jointly",
                "$0 to $21,527 Head of Household; Federal standard deduction of $15,000 Single / $30,000 MFJ",
            ),
            (
                "CA State Tier 2: 2.0% State Rate (12% Fed)",
                "$10,757 to $25,499 Single",
                "$21,513 to $50,998 Married Jointly",
                "$21,528 to $51,000 HOH; CA FTB 540 baseline exemption ($5,540 Single / $11,080 MFJ)",
            ),
            (
                "CA State Tier 3: 4.0% State Rate (12%/22% Fed)",
                "$25,500 to $40,245 Single",
                "$50,999 to $80,490 Married Jointly",
                "$51,001 to $65,744 HOH; CA Personal Exemption Credit ($149 Single / $298 MFJ)",
            ),
            (
                "CA State Tier 4: 6.0% State Rate (22% Fed)",
                "$40,246 to $55,866 Single",
                "$80,491 to $111,732 Married Jointly",
                "$65,745 to $81,364 HOH; CA SDI payroll withholding of 1.1% on all wages (no wage cap)",
            ),
            (
                "CA State Tier 5: 8.0% State Rate (22%/24% Fed)",
                "$55,867 to $70,606 Single",
                "$111,733 to $141,212 Married Jointly",
                "$81,365 to $96,107 HOH; Pre-tax 401(k) ($23,500 limit) reduces both Federal &amp; CA AGI",
            ),
            (
                "CA State Tier 6: 9.3% Core Professional State Rate",
                "$70,607 to $360,659 Single",
                "$141,213 to $721,318 Married Jointly",
                "$96,108 to $490,493 HOH; Pass-Through Entity Tax (AB 150) 9.3% elective SALT workaround",
            ),
            (
                "CA State Tier 7 &amp; 8: 10.3% and 11.3% State Rates",
                "$360,660 to $432,787 (10.3%); up to $721,314 (11.3%)",
                "$721,319 to $865,574 (10.3%); up to $1,442,628 (11.3%)",
                "$490,494 to $588,593 (10.3%); up to $980,987 (11.3%); 3.8% NIIT applies above $200k/$250k",
            ),
            (
                "CA State Tier 9 &amp; 10: 12.3% + 1.0% Prop 63 (13.3% Top)",
                "$721,315 to $1,000,000 (12.3%); Over $1,000,000 (13.3%)",
                "$1,442,629+ (12.3% base; 13.3% above $1,000,000)",
                "Includes 1.0% Mental Health Services Act surtax (R&amp;TC Section 17043) on taxable income &gt;$1M",
            ),
        ],
        "banner_html": (
            '      <div id="dynamic-commercial-intent-banner" class="serp-intent-banner" data-banner-mode="tax_brackets">\n'
            '        <div class="serp-intent-banner-text">\n'
            '          <strong>Live Payroll &amp; Entity Tax Shield Signal:</strong> Deducting pre-tax 401(k)/HSA and PTET lowers your taxable base to <span id="serp-banner-metric-primary">$138,600</span> and saves <span id="serp-banner-metric-secondary">$14,848</span> in combined federal and state income tax. Automate S-Corp payroll and tax books to lock in full deduction compliance.\n'
            '        </div>\n'
            '        <a href="#vetted-commercial-handoff" class="touch-target serp-intent-banner-btn">Compare Vetted Payroll, PTET &amp; Tax Accounting Platforms</a>\n'
            '      </div>'
        ),
    }


def _build_b2b_depth_spec(
    topic_label: str, statutory_authority: str, economic_dataset: str
) -> Dict[str, Any]:
    return {
        "workbench_mode": "b2b",
        "workbench_h2": f"Interactive Statutory Safe-Harbor Sub-Ledger &amp; Capital Retention Matrix: {topic_label}",
        "workbench_intro": (
            f"Under <strong>{statutory_authority}</strong> and <strong>{economic_dataset}</strong>, institutional "
            f"operators maximize net retained capital by pairing primary formula evaluation with statutory "
            f"safe-harbor deductions, payroll/duty exemptions, and multi-regime sensitivity modeling:"
        ),
        "presets": [
            (
                "Growth Operator Baseline ($250k Gross / 22% Effective)",
                '{"runway-cash":500000,"runway-burn":35000,"tey-principal":250000,"cg-amount":250000,"pm-tax-gain":50000,"serp-b2b-gross":250000,"serp-b2b-deduction":85000,"serp-b2b-rate":22.0,"serp-b2b-regime":"optimal_election"}',
            ),
            (
                "Mid-Market Safe-Harbor Election ($650k Gross / Maximized Shield)",
                '{"runway-cash":1200000,"runway-burn":65000,"tey-principal":650000,"cg-amount":650000,"pm-tax-gain":120000,"serp-b2b-gross":650000,"serp-b2b-deduction":240000,"serp-b2b-rate":24.5,"serp-b2b-regime":"optimal_election"}',
            ),
            (
                "Unoptimized Statutory Exposure ($650k Gross / Full Drag)",
                '{"runway-cash":800000,"runway-burn":85000,"tey-principal":650000,"cg-amount":650000,"pm-tax-gain":120000,"serp-b2b-gross":650000,"serp-b2b-deduction":0,"serp-b2b-rate":28.0,"serp-b2b-regime":"unoptimized_baseline"}',
            ),
            (
                "Enterprise Scale Audit Stress ($2.4M Gross / High Bracket)",
                '{"runway-cash":3500000,"runway-burn":140000,"tey-principal":2400000,"cg-amount":2400000,"pm-tax-gain":450000,"serp-b2b-gross":2400000,"serp-b2b-deduction":820000,"serp-b2b-rate":32.0,"serp-b2b-regime":"stress_case"}',
            ),
        ],
        "inputs_html": (
            '        <div class="serp-field-group">\n'
            '          <label for="serp-b2b-gross" class="serp-field-label">Gross Revenue / Capital Exposure ($)</label>\n'
            '          <input type="number" id="serp-b2b-gross" name="serp-b2b-gross" class="touch-target serp-sub-input" min="0" max="50000000" step="5000" value="450000" />\n'
            '        </div>\n'
            '        <div class="serp-field-group">\n'
            '          <label for="serp-b2b-deduction" class="serp-field-label">Statutory Offset / Exempt Allocation ($)</label>\n'
            '          <input type="number" id="serp-b2b-deduction" name="serp-b2b-deduction" class="touch-target serp-sub-input" min="0" max="25000000" step="2500" value="165000" />\n'
            '        </div>\n'
            '        <div class="serp-field-group">\n'
            '          <label for="serp-b2b-rate" class="serp-field-label">Effective Statutory Tax / Capital Rate (%)</label>\n'
            '          <input type="number" id="serp-b2b-rate" name="serp-b2b-rate" class="touch-target serp-sub-input" min="0" max="100" step="0.5" value="24.5" />\n'
            '        </div>\n'
            '        <div class="serp-field-group">\n'
            '          <label for="serp-b2b-regime" class="serp-field-label">Statutory Election &amp; Compliance Mode</label>\n'
            '          <select id="serp-b2b-regime" name="serp-b2b-regime" class="touch-target serp-sub-select">\n'
            '            <option value="optimal_election" selected="selected">Statutory Safe-Harbor Election (Maximized Deduction/Exemption)</option>\n'
            '            <option value="unoptimized_baseline">Unoptimized Statutory Exposure (No Safe-Harbor Offset)</option>\n'
            '            <option value="stress_case">Regulatory / Rate Stress Scenario (+20% Rate Sensitivity)</option>\n'
            '          </select>\n'
            '        </div>'
        ),
        "metrics_meta": [
            ("serp-out-primary", "Net Statutory Liability Exposure", "$69,825"),
            ("serp-out-secondary", "Unoptimized Baseline Exposure", "$110,250"),
            ("serp-out-tertiary", "Annual Safe-Harbor Alpha Saved", "$40,425"),
            ("serp-out-quaternary", "Net Retained Operating Capital", "$380,175"),
        ],
        "svg_left_label": "Net Retained Capital: $380,175 (84.5%)",
        "svg_right_label": "Net Statutory Exposure: $69,825 (15.5%)",
        "svg_left_width": "507",
        "svg_right_x": "507",
        "svg_right_width": "93",
        "table_h3": f"Statutory Reference Schedule: {topic_label} Governing Thresholds &amp; Safe-Harbor Matrix",
        "table_headers": [
            "Statutory Provision / Commercial Regime",
            "Governing Legal &amp; Regulatory Citation",
            "2026 Statutory Cap, Rate or Multiplier",
            "Audit Substantiation &amp; Execution Standard",
        ],
        "table_rows": [
            (
                "S-Corp Reasonable Salary &amp; QBI Pass-Through",
                "IRC Section 1366, Section 3111 &amp; Section 199A",
                "15.3% FICA on W-2 up to $176,100 OASDI base; 20% QBI deduction ($197,300/$394,600 threshold)",
                "IRS Form 1120-S, Schedule K-1, and W-2 reasonable compensation benchmark logs",
            ),
            (
                "R&amp;D Tax Credit &amp; Section 174 Capitalization",
                "IRC Section 41, Section 174 &amp; Section 280C(c)",
                "Up to $500,000 Form 8974 payroll tax offset; 15-year foreign vs domestic R&amp;D rules",
                "IRS Form 6765 Section G business-component technical uncertainty workpapers",
            ),
            (
                "U.S. Treasury Bill State Tax Exemption",
                "31 U.S.C. Section 3124(a) &amp; IRC Section 1411",
                "100% exempt from state/local income tax (up to 13.3% CA / 10.9% NY state tax saved)",
                "Form 1099-INT Box 3 state subtraction schedule; TEY = Yield / (1 minus State Rate)",
            ),
            (
                "Section 301 Tariffs, MPF/HMF &amp; Surety Bonds",
                "19 U.S.C. 2411, CBP Form 7501 &amp; 40 U.S.C. 3131",
                "7.5% to 100% Section 301 duty + 0.3464% MPF + 0.125% HMF; $150,000 Miller Act bond threshold",
                "10-digit HTSUS binding origin rulings and Treasury Circular 570 surety underwriting",
            ),
            (
                "CFTC Event Contracts vs Non-DCM Venues",
                "IRC Section 1256(g) &amp; CFTC 17 CFR Part 40",
                "60% Long-Term / 40% Short-Term hybrid rate on regulated DCMs vs ordinary rates",
                "IRS Form 6781 mark-to-market election and quadratic exchange fee reconciliation",
            ),
        ],
        "banner_html": (
            '      <div id="dynamic-commercial-intent-banner" class="serp-intent-banner" data-banner-mode="b2b">\n'
            '        <div class="serp-intent-banner-text">\n'
            '          <strong>Live Treasury &amp; Tax Execution Signal:</strong> Applying statutory safe-harbor offsets reduces net exposure to <span id="serp-banner-metric-primary">$69,825</span> and preserves <span id="serp-banner-metric-secondary">$40,425</span> in annual operating capital. Verify automated compliance and treasury execution below.\n'
            '        </div>\n'
            '        <a href="#vetted-commercial-handoff" class="touch-target serp-intent-banner-btn">Review Vetted Commercial Banking, Payroll &amp; Tax Partners</a>\n'
            '      </div>'
        ),
    }


def _build_gainhelm_depth_spec(
    topic_label: str, statutory_authority: str, economic_dataset: str
) -> Dict[str, Any]:
    return {
        "workbench_mode": "cyber_grc",
        "workbench_h2": f"Interactive Audit Scoping Sub-Ledger &amp; Automated GRC Savings Matrix: {topic_label}",
        "workbench_intro": (
            f"Under <strong>{statutory_authority}</strong> and <strong>{economic_dataset}</strong>, security and GRC "
            f"operators compress external CPA/C3PAO assessment fees and internal engineering hours by pairing "
            f"segmented enclave boundaries with automated API control evidence collection:"
        ),
        "presets": [
            (
                "Seed / Series A SaaS (35 Headcount / Segmented Enclave)",
                '{"serp-b2b-gross":58200,"serp-b2b-deduction":18400,"serp-b2b-rate":24.0,"serp-b2b-regime":"optimal_election"}',
            ),
            (
                "Growth Enterprise (150 Headcount / Multi-Framework GRC)",
                '{"serp-b2b-gross":112000,"serp-b2b-deduction":38500,"serp-b2b-rate":26.0,"serp-b2b-regime":"optimal_election"}',
            ),
            (
                "Manual Unsegmented Audit Scope (150 Headcount / Full Drag)",
                '{"serp-b2b-gross":148000,"serp-b2b-deduction":0,"serp-b2b-rate":32.0,"serp-b2b-regime":"unoptimized_baseline"}',
            ),
            (
                "Defense / Healthcare High-Assurance (400 Headcount / CMMC + HITRUST)",
                '{"serp-b2b-gross":245000,"serp-b2b-deduction":74000,"serp-b2b-rate":30.0,"serp-b2b-regime":"stress_case"}',
            ),
        ],
        "inputs_html": (
            '        <div class="serp-field-group">\n'
            '          <label for="serp-b2b-gross" class="serp-field-label">Gross Unoptimized Audit &amp; Engineering TCO ($)</label>\n'
            '          <input type="number" id="serp-b2b-gross" name="serp-b2b-gross" class="touch-target serp-sub-input" min="0" max="5000000" step="1000" value="84000" />\n'
            '        </div>\n'
            '        <div class="serp-field-group">\n'
            '          <label for="serp-b2b-deduction" class="serp-field-label">GRC Automation &amp; Enclave Scoping Savings ($)</label>\n'
            '          <input type="number" id="serp-b2b-deduction" name="serp-b2b-deduction" class="touch-target serp-sub-input" min="0" max="2500000" step="1000" value="25800" />\n'
            '        </div>\n'
            '        <div class="serp-field-group">\n'
            '          <label for="serp-b2b-rate" class="serp-field-label">Assessor &amp; Remediation Overhead Factor (%)</label>\n'
            '          <input type="number" id="serp-b2b-rate" name="serp-b2b-rate" class="touch-target serp-sub-input" min="0" max="100" step="0.5" value="22.0" />\n'
            '        </div>\n'
            '        <div class="serp-field-group">\n'
            '          <label for="serp-b2b-regime" class="serp-field-label">Control Evidence &amp; Boundary Architecture</label>\n'
            '          <select id="serp-b2b-regime" name="serp-b2b-regime" class="touch-target serp-sub-select">\n'
            '            <option value="optimal_election" selected="selected">Automated Continuous GRC + Segmented Enclave Scope</option>\n'
            '            <option value="unoptimized_baseline">Manual Spreadsheet Evidence + Unsegmented Network</option>\n'
            '            <option value="stress_case">Multi-Region / High-Assurance Audit Expansion (+20% Scope)</option>\n'
            '          </select>\n'
            '        </div>'
        ),
        "metrics_meta": [
            ("serp-out-primary", "Net Automated Audit &amp; GRC TCO", "$58,200"),
            ("serp-out-secondary", "Manual Unsegmented Audit TCO", "$84,000"),
            ("serp-out-tertiary", "Annual GRC Automation Hours Saved", "$25,800"),
            ("serp-out-quaternary", "Avoided Breach &amp; Penalty Exposure", "$488,000"),
        ],
        "svg_left_label": "Automated Readiness Efficiency: $58,200 (69.3%)",
        "svg_right_label": "Eliminated Manual Audit Drag: $25,800 (30.7%)",
        "svg_left_width": "416",
        "svg_right_x": "416",
        "svg_right_width": "184",
        "table_h3": f"Statutory Reference Schedule: {topic_label} Governing Audit Standards &amp; Assessor Benchmarks",
        "table_headers": [
            "Compliance Framework / Audit Tier",
            "Governing Statutory &amp; Technical Citation",
            "2026 Auditor-Day or Penalty Schedule",
            "Continuous Evidence &amp; Assessor Standard",
        ],
        "table_rows": [
            (
                "SOC 2 Type I &amp; Type II Attestation",
                "AICPA SSAE 18 / AT-C Section 205 &amp; TSP Section 100",
                "$18,000 to $65,000 CPA fee + 120 to 320 engineering readiness hours",
                "Peer-reviewed CPA examination over 3-to-12-month Type II observation window",
            ),
            (
                "CMMC 2.0 Level 2 &amp; NIST SP 800-171 Rev 2",
                "32 CFR Part 170, DFARS 252.204-7012 / 7019 / 7020 / 7021",
                "110 controls; SPRS range -203 to +110; $35,000 to $85,000 C3PAO fee",
                "Cyber-AB authorized C3PAO triennial assessment and live System Security Plan",
            ),
            (
                "ISO/IEC 27001:2022 ISMS Certification",
                "ISO/IEC 27001:2022 Annex A (93 Controls) &amp; ISO/IEC 27006-1:2024",
                "9 to 28 accredited Stage 1 + Stage 2 auditor-days ($1,600 to $2,200/day)",
                "Accredited Certification Body Stage 1/2 audit plus Years 2-3 surveillance",
            ),
            (
                "HIPAA Civil Monetary Penalties &amp; HITECH Breach",
                "45 CFR 160.404, 45 CFR Part 164 &amp; 42 U.S.C. 1320d-5",
                "4 penalty tiers ($141 to $2,134,831 annual cap per identical provision)",
                "60-day OCR &amp; media breach notification (>500 records) + BAA encryption",
            ),
            (
                "PCI DSS v4.0.1 ROC, FedRAMP 3PAO &amp; HITRUST CSF",
                "PCI DSS v4.0.1, 44 U.S.C. 3607 FedRAMP &amp; HITRUST CSF v11",
                "QSA ROC (>6M Visa tx/yr), 3PAO SAR ($95k to $220k), HITRUST e1/i1/r2",
                "Continuous automated vulnerability scanning, CREST pentest, and 3PAO ConMon",
            ),
        ],
        "banner_html": (
            '      <div id="dynamic-commercial-intent-banner" class="serp-intent-banner" data-banner-mode="cyber_grc">\n'
            '        <div class="serp-intent-banner-text">\n'
            '          <strong>Live GRC &amp; Assessor Readiness Signal:</strong> Deploying continuous API control collection and enclave segmentation compresses net audit TCO to <span id="serp-banner-metric-primary">$58,200</span> and saves <span id="serp-banner-metric-secondary">$25,800</span> in manual engineering preparation. Compare vetted GRC and CPA/C3PAO partners below.\n'
            '        </div>\n'
            '        <a href="#vetted-commercial-handoff" class="touch-target serp-intent-banner-btn">Review Vetted GRC Automation, CPA Audit &amp; Pentest Partners</a>\n'
            '      </div>'
        ),
    }


def _build_prediction_market_depth_spec(
    topic_label: str, statutory_authority: str, economic_dataset: str
) -> Dict[str, Any]:
    """
    Renders the bespoke Prediction Market EV, Exchange Quadratic Fee (Kalshi Taker 0.07*P*(1-P)
    vs Kalshi Maker 0.0175*P*(1-P) vs Polymarket 4% Winner Fee), No-Vig De-Vigging, and
    IRC Section 1256 (60/40) vs Ordinary Income Sub-Ledger Workbench.
    Directly absorbs and upgrades live competitor DOM mechanics from predictioncalculator.com
    with 100% SSR-hydrated default outputs.
    Zero em-dashes. Zero en-dashes.
    """
    return {
        "workbench_mode": "prediction_market_ev",
        "workbench_h2": f"Interactive Event Contract EV, Exchange Fee &amp; Section 1256 Tax Sub-Ledger: {topic_label}",
        "workbench_intro": (
            f"Under <strong>{statutory_authority}</strong> and <strong>{economic_dataset}</strong>, event-contract "
            f"traders reconcile Kalshi quadratic taker/maker fee drag, Polymarket winner fees, two-way no-vig "
            f"implied probability, fractional Kelly sizing, and IRC Section 1256(g) 60/40 mark-to-market tax treatment:"
        ),
        "presets": [
            (
                "Kalshi Parabolic Taker ($0.62 Price / 68% True Win / 0.07xP(1 minus P) Fee)",
                '{"pm-price":0.62,"pm-true-prob":68,"pm-contracts":10000,"serp-b2b-gross":10000,"serp-b2b-deduction":6200,"serp-b2b-rate":26.8,"serp-b2b-regime":"optimal_election"}',
            ),
            (
                "Kalshi Maker Limit Order ($0.62 Price / 68% True Win / 0.0175xP(1 minus P) Fee)",
                '{"pm-price":0.62,"pm-true-prob":68,"pm-contracts":10000,"serp-b2b-gross":10000,"serp-b2b-deduction":6200,"serp-b2b-rate":24.5,"serp-b2b-regime":"optimal_election"}',
            ),
            (
                "Polymarket Event Contract ($0.55 Price / 64% True Win / 4% Profit Fee)",
                '{"pm-price":0.55,"pm-true-prob":64,"pm-contracts":10000,"serp-b2b-gross":10000,"serp-b2b-deduction":5500,"serp-b2b-rate":37.0,"serp-b2b-regime":"unoptimized_baseline"}',
            ),
            (
                "Section 1256 (60/40 Hybrid) Regulated DCM vs Ordinary Tax Stress ($25k Net Gain)",
                '{"pm-price":0.50,"pm-true-prob":60,"pm-contracts":50000,"serp-b2b-gross":25000,"serp-b2b-deduction":0,"serp-b2b-rate":37.0,"serp-b2b-regime":"stress_case"}',
            ),
        ],
        "inputs_html": (
            '        <div class="serp-field-group">\n'
            '          <label for="serp-b2b-gross" class="serp-field-label">Gross Settlement Payout / Position Notional ($)</label>\n'
            '          <input type="number" id="serp-b2b-gross" name="serp-b2b-gross" class="touch-target serp-sub-input" min="0" max="10000000" step="500" value="10000" />\n'
            '        </div>\n'
            '        <div class="serp-field-group">\n'
            '          <label for="serp-b2b-deduction" class="serp-field-label">Contract Cost Basis &amp; Exchange Fee Offset ($)</label>\n'
            '          <input type="number" id="serp-b2b-deduction" name="serp-b2b-deduction" class="touch-target serp-sub-input" min="0" max="10000000" step="100" value="6365" />\n'
            '        </div>\n'
            '        <div class="serp-field-group">\n'
            '          <label for="serp-b2b-rate" class="serp-field-label">Effective Tax Rate (26.8% Sec 1256 vs 37% Ord) (%)</label>\n'
            '          <input type="number" id="serp-b2b-rate" name="serp-b2b-rate" class="touch-target serp-sub-input" min="0" max="100" step="0.2" value="26.8" />\n'
            '        </div>\n'
            '        <div class="serp-field-group">\n'
            '          <label for="serp-b2b-regime" class="serp-field-label">Exchange Fee Schedule &amp; Tax Regime</label>\n'
            '          <select id="serp-b2b-regime" name="serp-b2b-regime" class="touch-target serp-sub-select">\n'
            '            <option value="optimal_election" selected="selected">CFTC Regulated DCM (Kalshi 0.07xP(1 minus P) + IRC Sec 1256 60/40)</option>\n'
            '            <option value="unoptimized_baseline">Non-DCM Offshore / Crypto Venue (4% Fee + Ordinary Tax Rate)</option>\n'
            '            <option value="stress_case">High-Vigorish Two-Way Overround + Top Bracket Stress</option>\n'
            '          </select>\n'
            '        </div>'
        ),
        "metrics_meta": [
            ("serp-out-primary", "Post-Fee &amp; Tax Expected Value (EV)", "+$435.24"),
            ("serp-out-secondary", "Break-Even Win Rate (After Fee)", "63.65%"),
            ("serp-out-tertiary", "Kalshi Quadratic Taker Fee Drag", "$164.76"),
            ("serp-out-quaternary", "IRC 1256 (60/40) Tax Alpha Saved", "$370.77"),
        ],
        "svg_left_label": "Net Post-Fee & Tax Retained Edge: $2,661 (73.2%)",
        "svg_right_label": "Exchange Fee + Statutory Tax Drag: $974 (26.8%)",
        "svg_left_width": "439",
        "svg_right_x": "439",
        "svg_right_width": "161",
        "table_h3": f"Statutory &amp; Exchange Fee Reference Schedule: {topic_label} Venue Mechanics &amp; Tax Treatment",
        "table_headers": [
            "Venue / Quantitative Mechanic",
            "Governing Formula or Statutory Rule",
            "Fee / Tax Rate Impact at $0.62 Contract",
            "Break-Even &amp; Reporting Requirement",
        ],
        "table_rows": [
            (
                "Kalshi Taker Quadratic Fee Schedule",
                "ceil(0.07 x C x P x (1 minus P)) under CFTC 17 CFR Part 40",
                "$0.0165 per contract ($164.76 on 10,000 contracts); max $0.0175 at $0.50",
                "Shifts break-even win probability from 62.00% to 63.65% (+1.65% hurdle)",
            ),
            (
                "Kalshi Maker Resting Limit Schedule",
                "ceil(0.0175 x C x P x (1 minus P)) Maker Rebate Tier",
                "$0.0041 per contract ($41.19 on 10,000 contracts); 75% fee reduction",
                "Shifts break-even win probability from 62.00% to 62.41% (+0.41% hurdle)",
            ),
            (
                "Polymarket Net Winner Fee Schedule",
                "0.04 x (1 minus P) x C applied on winning settlement profit",
                "$0.0152 per winning contract ($152.00 on 10,000 contracts at $0.62)",
                "Shifts break-even win probability from 62.00% to 62.96% (+0.96% hurdle)",
            ),
            (
                "Two-Way Multiplicative De-Vigging",
                "P_fair_yes = P_yes / (P_yes + P_no); Overround = (P_yes + P_no minus 1)",
                "Strips bid-ask spread vigorish to isolate true market consensus probability",
                "Required input before computing Quarter-Kelly or Half-Kelly position size",
            ),
            (
                "Regulated DCM vs Ordinary Tax Treatment",
                "IRC Section 1256(g) (60% LTCG / 40% STCG) vs IRC Section 165(d)",
                "26.8% top blended rate (Form 6781) vs 37.0% ordinary income rate (-10.2% saved)",
                "IRS Form 6781 mark-to-market net loss carryback vs itemized wagering limits",
            ),
        ],
        "banner_html": (
            '      <div id="dynamic-commercial-intent-banner" class="serp-intent-banner" data-banner-mode="prediction_market_ev">\n'
            '        <div class="serp-intent-banner-text">\n'
            '          <strong>Live Event-Contract Execution &amp; Tax Signal:</strong> Routing orders via maker limit books and IRC Section 1256 regulated accounting preserves <span id="serp-banner-metric-primary">+$435.24</span> net EV and saves <span id="serp-banner-metric-secondary">$370.77</span> in tax drag. Review vetted CFTC-regulated and tax reconciliation partners below.\n'
            '        </div>\n'
            '        <a href="#vetted-commercial-handoff" class="touch-target serp-intent-banner-btn">Review Vetted Event-Contract &amp; Tax Lot Partners</a>\n'
            '      </div>'
        ),
    }


def _render_multi_year_cliff_visualizer_html(
    topic_label: str,
    is_prexvo: bool,
    statutory_authority: str,
    economic_dataset: str,
    is_gainhelm: bool = False,
    slug: str = "",
) -> str:
    """Renders the longitudinal 2024 to 2030 statutory and repayment cliff visualizer and SVG trajectory."""
    from pseofactory.proprietary_signals import compute_multi_year_longitudinal_trajectory

    prop_id = "prexvo" if is_prexvo else ("gainhelm" if is_gainhelm else "profithelm")
    traj = compute_multi_year_longitudinal_trajectory(
        property_id=prop_id,
        slug=slug or topic_label.lower().replace(" ", "-"),
        topic_label=topic_label,
    )
    h3_title = traj["h3_title"]
    summary_default = traj["summary_default"]
    rows = traj["rows"]
    tr_cliff = "\n".join(
        f'            <tr>\n'
        f'              <td><strong>{yr_label}</strong></td>\n'
        f'              <td>{reg_rule}</td>\n'
        f'              <td>{macro_rule}</td>\n'
        f'              <td id="{cell_id}" class="calc-metric-value"><strong>{default_val}</strong></td>\n'
        f'            </tr>'
        for yr_label, reg_rule, macro_rule, cell_id, default_val in rows
    )
    return (
        f'      <div id="multi-year-cliff-visualizer" class="serp-cliff-visualizer" data-mechanic="multi_year_cliff_visualizer">\n'
        f'        <h3 style="margin-top: 22px; margin-bottom: 8px;">{h3_title}</h3>\n'
        f'        <p id="serp-cliff-svg-summary" style="font-size: 14px; color: var(--text-secondary, #475569); margin-bottom: 12px;">{summary_default}</p>\n'
        f'        <div class="serp-svg-chart-wrap">\n'
        f'          <svg id="serp-cliff-trajectory-svg" class="serp-visual-breakdown-svg" viewBox="0 0 600 92" role="img" aria-label="Multi-Year Statutory and Repayment Cliff Trajectory">\n'
        f'            <desc>Multi-Year Statutory and Repayment Cliff Trajectory</desc>\n'
        f'            <rect x="0" y="6" width="600" height="80" rx="6" fill="var(--bg-inset, #0b1329)" />\n'
        f'            <rect id="cliff-bar-2024" x="28" y="42" width="76" height="26" rx="4" fill="var(--status-positive, #10b981)" />\n'
        f'            <rect id="cliff-bar-2025" x="142" y="34" width="76" height="34" rx="4" fill="var(--accent, #38bdf8)" />\n'
        f'            <rect id="cliff-bar-2026" x="256" y="20" width="88" height="48" rx="4" fill="#f59e0b" />\n'
        f'            <rect id="cliff-bar-2027" x="380" y="14" width="76" height="54" rx="4" fill="#ef4444" />\n'
        f'            <rect id="cliff-bar-2028" x="494" y="12" width="76" height="56" rx="4" fill="#ec4899" />\n'
        f'            <text x="66" y="81" text-anchor="middle" fill="var(--text, #f8fafc)" font-size="11" font-weight="600">2024</text>\n'
        f'            <text x="180" y="81" text-anchor="middle" fill="var(--text, #f8fafc)" font-size="11" font-weight="600">2025</text>\n'
        f'            <text x="300" y="81" text-anchor="middle" fill="#fbbf24" font-size="11" font-weight="700">2026 Cliff</text>\n'
        f'            <text x="418" y="81" text-anchor="middle" fill="var(--text, #f8fafc)" font-size="11" font-weight="600">2027</text>\n'
        f'            <text x="532" y="81" text-anchor="middle" fill="var(--text, #f8fafc)" font-size="11" font-weight="600">2028-2030</text>\n'
        f'          </svg>\n'
        f'        </div>\n'
        f'        <div class="table-wrap pseo-table-wrap">\n'
        f'          <table class="comparison-table serp-cliff-matrix-table" data-statutory-source="{statutory_authority}" data-economic-source="{economic_dataset}">\n'
        f'            <thead>\n'
        f'              <tr>\n'
        f'                <th scope="col">Effective Tax / Academic Year</th>\n'
        f'                <th scope="col">Governing Statutory Phaseout Rule</th>\n'
        f'                <th scope="col">Macroeconomic &amp; Sunset Driver</th>\n'
        f'                <th scope="col">Projected Annual Exposure</th>\n'
        f'              </tr>\n'
        f'            </thead>\n'
        f'            <tbody>\n'
        f'{tr_cliff}\n'
        f'            </tbody>\n'
        f'          </table>\n'
        f'        </div>\n'
        f'      </div>'
    )


def _render_stateful_scenario_comparator_html(
    topic_label: str,
    is_prexvo: bool = False,
    statutory_authority: str = "",
    economic_dataset: str = "",
    is_gainhelm: bool = False,
    slug: str = "",
) -> str:
    """Renders the stateful side-by-side Scenario A vs Scenario B vs Live Workbench comparator."""
    from pseofactory.proprietary_signals import compute_stateful_comparator_defaults

    prop_id = "prexvo" if is_prexvo else ("gainhelm" if is_gainhelm else "profithelm")
    comp = compute_stateful_comparator_defaults(
        property_id=prop_id,
        slug=slug or topic_label.lower().replace(" ", "-"),
    )
    base_a, base_b, base_live = comp["base_a"], comp["base_b"], comp["base_live"]
    ret_a, ret_b, ret_live = comp["ret_a"], comp["ret_b"], comp["ret_live"]
    tax_a, tax_b, tax_live = comp["tax_a"], comp["tax_b"], comp["tax_live"]
    delta_b, delta_live = comp["delta_b"], comp["delta_live"]
    comp_prefix = "GRC Audit &amp; Control TCO" if is_gainhelm else "Scenario"
    return (
        f'      <div id="stateful-scenario-comparator" class="serp-scenario-comparator" data-mechanic="stateful_scenario_comparator">\n'
        f'        <h3 style="margin-top: 22px; margin-bottom: 8px;">Stateful Side-by-Side {comp_prefix} Comparator: {topic_label}</h3>\n'
        f'        <p style="font-size: 14px; color: var(--text-secondary, #475569); margin-bottom: 10px;">Pin any active input state to Scenario A or Scenario B to evaluate multi-variable counterfactual deltas in real time:</p>\n'
        f'        <div class="serp-preset-bar" role="group" aria-label="Stateful Scenario Pin Controls">\n'
        f'          <button type="button" id="btn-pin-scenario-a" class="touch-target btn-preset serp-comparator-btn" data-cta-slot="pin_scenario_a_cta" data-scenario-pin="A">Pin Current State to Scenario A</button>\n'
        f'          <button type="button" id="btn-pin-scenario-b" class="touch-target btn-preset serp-comparator-btn" data-cta-slot="pin_scenario_b_cta" data-scenario-pin="B">Pin Current State to Scenario B</button>\n'
        f'          <button type="button" id="btn-reset-scenarios" class="touch-target btn-preset serp-comparator-btn" data-cta-slot="reset_scenarios_cta" data-scenario-pin="RESET">Reset Pinned Scenarios</button>\n'
        f'        </div>\n'
        f'        <div class="table-wrap pseo-table-wrap">\n'
        f'          <table class="comparison-table serp-scenario-comparator-table" data-statutory-source="{statutory_authority}" data-economic-source="{economic_dataset}">\n'
        f'            <thead>\n'
        f'              <tr>\n'
        f'                <th scope="col">Comparison Dimension</th>\n'
        f'                <th scope="col">Scenario A (Pinned Baseline)</th>\n'
        f'                <th scope="col">Scenario B (Pinned Counterfactual)</th>\n'
        f'                <th scope="col">Live Active Workbench</th>\n'
        f'              </tr>\n'
        f'            </thead>\n'
        f'            <tbody>\n'
        f'              <tr>\n'
        f'                <td><strong>Primary Gross Input Base</strong></td>\n'
        f'                <td id="comp-a-input" class="calc-metric-value">{base_a}</td>\n'
        f'                <td id="comp-b-input" class="calc-metric-value">{base_b}</td>\n'
        f'                <td id="comp-live-input" class="calc-metric-value"><strong>{base_live}</strong></td>\n'
        f'              </tr>\n'
        f'              <tr>\n'
        f'                <td><strong>Protected Capital / Statutory Offset</strong></td>\n'
        f'                <td id="comp-a-retained" class="calc-metric-value">{ret_a}</td>\n'
        f'                <td id="comp-b-retained" class="calc-metric-value">{ret_b}</td>\n'
        f'                <td id="comp-live-retained" class="calc-metric-value"><strong>{ret_live}</strong></td>\n'
        f'              </tr>\n'
        f'              <tr>\n'
        f'                <td><strong>Net Statutory Exposure / Annual Levy</strong></td>\n'
        f'                <td id="comp-a-tax" class="calc-metric-value">{tax_a}</td>\n'
        f'                <td id="comp-b-tax" class="calc-metric-value">{tax_b}</td>\n'
        f'                <td id="comp-live-tax" class="calc-metric-value"><strong>{tax_live}</strong></td>\n'
        f'              </tr>\n'
        f'              <tr>\n'
        f'                <td><strong>Net Exposure Delta vs Scenario A</strong></td>\n'
        f'                <td id="comp-a-delta" class="calc-metric-value">$0 (Baseline)</td>\n'
        f'                <td id="comp-b-delta" class="calc-metric-value">{delta_b}</td>\n'
        f'                <td id="comp-live-delta" class="calc-metric-value"><strong>{delta_live}</strong></td>\n'
        f'              </tr>\n'
        f'            </tbody>\n'
        f'          </table>\n'
        f'        </div>\n'
        f'      </div>'
    )


def render_partner_quote_intake_html(
    slug: str,
    property_id: str,
    topic_label: str = "",
    statutory_authority: str = "",
    baseline_amount: Optional[float] = None,
) -> str:
    """
    Renders the native, TCPA-compliant partner-quote intake step (#partner-quote-intake-step)
    capturing email, borrower/company state, capital_band, and explicit partner_sharing_consent
    whenever a visitor's calculation crosses high-value thresholds:
      - $100,000+ on 1031 Exchange or CapEx / Section 179
      - $50,000+ on Invoice Factoring
      - $50,000+ on Prexvo Student Loan Refinance
    Strictly returns an empty string on restricted YMYL public-service pages (PSLF, IBR hardship,
    SAVE litigation, disclaimers, methodology) so public-service pages stay 100% free of commercial
    private refinance offers.
    Zero em-dashes. Zero en-dashes. Zero spaced hyphens.
    """
    from pseofactory.partner_tracker import evaluate_lead_quote_threshold

    prop_clean = str(property_id or "profithelm").strip().lower()
    slug_clean = str(slug or "index").strip().strip("/").lower() or "index"

    default_amt = baseline_amount
    if default_amt is None:
        if prop_clean == "prexvo":
            default_amt = 68500.0
        elif prop_clean == "gainhelm":
            default_amt = 58200.0
        elif any(tok in slug_clean for tok in ("factoring", "invoice", "line-of-credit", "working-capital")):
            default_amt = 85000.0
        elif any(tok in slug_clean for tok in ("1031", "like-kind", "exchange", "8824", "3840", "boot", "dst")):
            default_amt = 450000.0
        else:
            default_amt = 125000.0

    eval_info = evaluate_lead_quote_threshold(
        property_id=prop_clean,
        tool_slug=slug_clean,
        calculated_amount=float(default_amt),
    )
    if not eval_info.get("eligible"):
        return ""

    threshold_int = int(round(float(eval_info["threshold_usd"])))
    threshold_fmt = f"${threshold_int:,}"
    amt_int = int(round(float(eval_info["calculated_amount"])))
    vertical = str(eval_info["vertical"])
    partner_key = str(eval_info["primary_partner_key"])
    default_band = str(eval_info["capital_band"])
    is_active = bool(eval_info["qualifies_for_quote_intake"])
    active_attr = "true" if is_active else "false"
    frictionless_attr = "false" if is_active else "true"
    form_display = "block" if is_active else "none"
    note_display = "none" if is_active else "block"

    us_states = (
        ("CA", "California (CA)"),
        ("TX", "Texas (TX)"),
        ("NY", "New York (NY)"),
        ("FL", "Florida (FL)"),
        ("IL", "Illinois (IL)"),
        ("PA", "Pennsylvania (PA)"),
        ("OH", "Ohio (OH)"),
        ("GA", "Georgia (GA)"),
        ("NC", "North Carolina (NC)"),
        ("MI", "Michigan (MI)"),
        ("NJ", "New Jersey (NJ)"),
        ("VA", "Virginia (VA)"),
        ("WA", "Washington (WA)"),
        ("AZ", "Arizona (AZ)"),
        ("MA", "Massachusetts (MA)"),
        ("TN", "Tennessee (TN)"),
        ("IN", "Indiana (IN)"),
        ("MO", "Missouri (MO)"),
        ("MD", "Maryland (MD)"),
        ("WI", "Wisconsin (WI)"),
        ("CO", "Colorado (CO)"),
        ("MN", "Minnesota (MN)"),
        ("SC", "South Carolina (SC)"),
        ("AL", "Alabama (AL)"),
        ("LA", "Louisiana (LA)"),
        ("KY", "Kentucky (KY)"),
        ("OR", "Oregon (OR)"),
        ("OK", "Oklahoma (OK)"),
        ("CT", "Connecticut (CT)"),
        ("UT", "Utah (UT)"),
        ("NV", "Nevada (NV)"),
        ("DC", "District of Columbia (DC)"),
    )
    state_options_html = "\n".join(
        f'              <option value="{st_code}"{" selected" if st_code == "CA" else ""}>{st_label}</option>'
        for st_code, st_label in us_states
    )

    bands = (
        ("50k_100k", "$50,000 to $99,999"),
        ("100k_250k", "$100,000 to $249,999"),
        ("250k_500k", "$250,000 to $499,999"),
        ("500k_plus", "$500,000+ Institutional Tier"),
    )
    band_options_html = "\n".join(
        f'              <option value="{b_code}"{" selected" if b_code == default_band else ""}>{b_label}</option>'
        for b_code, b_label in bands
    )

    if prop_clean == "prexvo":
        is_explicit_refi = "refinance" in slug_clean or "refinancing" in slug_clean
        heading_text = f"Qualified Borrower Rate-Match Intake ({threshold_fmt}+ Balance Threshold)"
        sub_text = (
            f"Calculations at or above {threshold_fmt} qualify for direct institutional rate-table matching "
            f"with pre-filled loan parameters. Calculations below {threshold_fmt} remain 100% frictionless with zero registration."
        )
        email_label = "Borrower Email Address"
        state_label = "Borrower Residence State"
        if is_explicit_refi:
            band_label = "Refinance Loan Balance Tier"
            consent_copy = (
                "I provide explicit TCPA partner_sharing_consent authorizing Prexvo to share my email, residence state, "
                "and loan balance tier with matched student loan refinance marketplace partners (including Splash Financial) "
                "to generate a pre-filled rate quote. Refinancing federal student loans permanently waives federal protections."
            )
            btn_text = "Unlock Matched Refinance Rate Quote & Continue"
        else:
            band_label = "Student Loan Balance Tier"
            consent_copy = (
                "I provide explicit TCPA partner_sharing_consent authorizing Prexvo to share my email, residence state, "
                "and loan balance tier with matched student loan marketplace partners (including Splash Financial) "
                "to generate a pre-filled rate-table quote."
            )
            btn_text = "Unlock Matched Rate-Table Quote & Continue"
    elif prop_clean == "gainhelm":
        heading_text = f"Enterprise GRC Automation & Audit Readiness Quote Intake ({threshold_fmt}+ TCO Threshold)"
        sub_text = (
            f"Compliance and audit readiness budgets at or above {threshold_fmt} qualify for direct GRC automation "
            f"platform fee quotes, AICPA CPA / C3PAO assessor matching, and multi-framework control scoping. "
            f"Sub-threshold calculations stay 100% frictionless."
        )
        email_label = "Work or Security Operations Email Address"
        state_label = "Corporate Headquarters State"
        band_label = "Annual Compliance & Audit Budget Band"
        consent_copy = (
            "I provide explicit TCPA partner_sharing_consent authorizing GainHelm to share my work email, "
            "headquarters state, and compliance budget band with matched GRC automation, CPA audit, penetration testing, "
            "or cyber insurance partners (including Vanta, Drata, Sprinto, Thoropass, Coalition, and Cobalt) to prepare "
            "a customized readiness quote."
        )
        btn_text = "Request Matched GRC & Audit Quote"
    else:
        if vertical == "1031_exchange":
            heading_text = f"Qualified Intermediary & Tax Advisory Quote Intake ({threshold_fmt}+ Exchange Threshold)"
            sub_text = (
                f"Exchange deferrals at or above {threshold_fmt} qualify for priority Qualified Intermediary escrow "
                f"fee quotes and multi-state CPA boot reconciliation. Sub-threshold calculations stay 100% frictionless."
            )
            band_label = "Relinquished Property / Exchange Capital Band"
        elif vertical == "invoice_factoring":
            heading_text = f"Commercial Factoring & Working Capital Quote Intake ({threshold_fmt}+ Volume Threshold)"
            sub_text = (
                f"Monthly receivable volume at or above {threshold_fmt} qualifies for direct non-recourse factoring "
                f"advance rates and same-day funding quotes. Sub-threshold calculations stay 100% frictionless."
            )
            band_label = "Monthly Invoice / Working Capital Band"
        elif vertical == "capex_section_179":
            heading_text = f"Commercial Equipment & Section 179 Tax Quote Intake ({threshold_fmt}+ CapEx Threshold)"
            sub_text = (
                f"Capital equipment acquisitions at or above {threshold_fmt} qualify for direct equipment financing "
                f"rate sheets and CPA depreciation audit schedules. Sub-threshold calculations stay 100% frictionless."
            )
            band_label = "Equipment CapEx / Deduction Capital Band"
        else:
            heading_text = f"Commercial CPA & Advisory Quote Intake ({threshold_fmt}+ Exposure Threshold)"
            sub_text = (
                f"Commercial calculations at or above {threshold_fmt} qualify for direct CPA tax preparation "
                f"and entity structuring fee quotes. Sub-threshold calculations stay 100% frictionless."
            )
            band_label = "Annual Exposure / Capital Band"

        email_label = "Work or Business Email Address"
        state_label = "Company Filing State"
        consent_copy = (
            "I provide explicit TCPA partner_sharing_consent authorizing ProfitHelm to share my business email, "
            "filing state, and capital band with matched commercial finance, tax, or exchange partners "
            "(including OTR Solutions, E-file, and IPX1031) to prepare a customized quote and route me to the partner portal."
        )
        btn_text = "Request Matched Partner Quote & Continue"

    vertical_attr = vertical
    if prop_clean == "prexvo" and not ("refinance" in slug_clean or "refinancing" in slug_clean):
        vertical_attr = "student_loan_rate_match"

    return (
        f'      <div id="partner-quote-intake-step" class="partner-quote-intake-drawer" '
        f'data-mechanic="partner_quote_intake" '
        f'data-property-id="{prop_clean}" '
        f'data-tool-slug="{slug_clean}" '
        f'data-vertical="{vertical_attr}" '
        f'data-partner-key="{partner_key}" '
        f'data-quote-threshold="{threshold_int}" '
        f'data-calculated-amount="{amt_int}" '
        f'data-threshold-active="{active_attr}" '
        f'data-frictionless-mode="{frictionless_attr}">\n'
        f'        <div class="partner-quote-header">\n'
        f'          <span class="partner-quote-badge">High-Value Threshold Quote Desk ({threshold_fmt}+)</span>\n'
        f'          <h3 style="margin: 6px 0 6px 0; font-size: 1.08rem;">{heading_text}</h3>\n'
        f'          <p style="font-size: 13.5px; color: var(--text-secondary, #cbd5e1); margin: 0 0 10px 0;">{sub_text}</p>\n'
        f'        </div>\n'
        f'        <div id="partner-quote-frictionless-note" class="partner-quote-frictionless-note" aria-live="polite" style="display: {note_display}; font-size: 13px; color: var(--text-secondary, #94a3b8); padding: 8px 12px; border-radius: 6px; background: rgba(15, 23, 42, 0.5);">\n'
        f'          Frictionless Calculator Mode Active: Your current calculation is below the {threshold_fmt} institutional quote threshold. Instant results remain 100% unlocked with zero registration required.\n'
        f'        </div>\n'
        f'        <form id="partner-quote-intake-form" class="partner-quote-form-body" action="/api/lead-capture" method="POST" style="display: {form_display};" novalidate>\n'
        f'          <div class="serp-sub-inputs-grid" style="margin-bottom: 12px;">\n'
        f'            <div class="serp-input-cell">\n'
        f'              <label for="quote-intake-email">{email_label}</label>\n'
        f'              <input type="email" id="quote-intake-email" name="email" class="touch-target calc-number-input" required autocomplete="email" aria-label="{email_label}">\n'
        f'            </div>\n'
        f'            <div class="serp-input-cell">\n'
        f'              <label for="quote-intake-state">{state_label}</label>\n'
        f'              <select id="quote-intake-state" name="state" class="touch-target serp-select-input" required aria-label="{state_label}">\n'
        f'{state_options_html}\n'
        f'              </select>\n'
        f'            </div>\n'
        f'            <div class="serp-input-cell">\n'
        f'              <label for="quote-intake-capital-band">{band_label}</label>\n'
        f'              <select id="quote-intake-capital-band" name="capital_band" class="touch-target serp-select-input" required aria-label="{band_label}">\n'
        f'{band_options_html}\n'
        f'              </select>\n'
        f'            </div>\n'
        f'          </div>\n'
        f'          <div class="partner-quote-consent-row" style="margin-bottom: 12px;">\n'
        f'            <label for="quote-intake-consent" class="touch-target partner-quote-consent-label" style="display: flex; align-items: flex-start; gap: 10px; min-height: 44px; min-width: 44px; padding: 6px 0; cursor: pointer; font-size: 12.5px; line-height: 1.45; color: var(--text-secondary, #cbd5e1);">\n'
        f'              <input type="checkbox" id="quote-intake-consent" name="partner_sharing_consent" value="true" required class="touch-target" aria-label="Explicit TCPA Partner Sharing Consent" style="min-width: 44px; min-height: 44px; margin: 0; flex-shrink: 0; accent-color: var(--accent, #38bdf8);">\n'
        f'              <span>{consent_copy}</span>\n'
        f'            </label>\n'
        f'          </div>\n'
        f'          <div class="partner-quote-actions" style="display: flex; flex-wrap: wrap; align-items: center; gap: 12px;">\n'
        f'            <button type="submit" id="btn-submit-partner-quote" class="touch-target btn-primary partner-quote-submit-btn" data-cta-slot="partner_quote_intake_cta" style="min-height: 48px; min-width: 48px; padding: 12px 20px; font-size: 16px; font-weight: 700; cursor: pointer;">{btn_text}</button>\n'
        f'          </div>\n'
        f'          <div id="partner-quote-intake-status" class="partner-quote-status" aria-live="polite" style="font-size: 13px; color: var(--text-secondary, #94a3b8); margin-top: 8px;">Ready to route pre-filled {threshold_fmt}+ quote parameters upon explicit consent.</div>\n'
        f'        </form>\n'
        f'      </div>'
    )


def render_post_calculation_upgrade_drawer_html(
    slug: str,
    property_id: str = "profithelm",
    topic_label: str = "",
    statutory_authority: str = "",
    economic_dataset: str = "",
    baseline_amount: Optional[float] = None,
) -> str:
    """
    Renders the unified, non-intrusive Post-Calculation Workpaper Export & Tailored Statutory Data Pack
    upgrade drawer (#post-calculation-upgrade-drawer) inside the post-calculation Decision Blueprint.
    Strictly returns an empty string on restricted YMYL public-service pages (PSLF, IBR hardship,
    SAVE litigation, disclaimers, methodology) so public-service pages stay 100% free of commercial
    checkout triggers.
    Zero em-dashes. Zero en-dashes. Zero spaced hyphens.
    """
    from pseofactory.partner_tracker import resolve_post_calculation_upgrade_spec

    prop_clean = str(property_id or "profithelm").strip().lower()
    slug_clean = str(slug or "index").strip().strip("/").lower() or "index"
    spec = resolve_post_calculation_upgrade_spec(
        property_id=prop_clean,
        tool_slug=slug_clean,
        statutory_authority=statutory_authority,
        economic_dataset=economic_dataset,
    )
    if not spec:
        return ""

    default_amt = baseline_amount
    if default_amt is None:
        if prop_clean == "prexvo":
            default_amt = 68500.0
        elif prop_clean == "gainhelm":
            default_amt = 58200.0
        elif any(tok in slug_clean for tok in ("factoring", "invoice", "line-of-credit", "working-capital")):
            default_amt = 85000.0
        elif any(tok in slug_clean for tok in ("1031", "like-kind", "exchange", "8824", "3840", "boot", "dst")):
            default_amt = 450000.0
        else:
            default_amt = 125000.0

    amt_int = int(round(float(default_amt)))
    amt_fmt = f"${amt_int:,}"
    offer_sku = str(spec["offer_sku"])
    offer_title = str(spec["offer_title"])
    price_int = int(round(float(spec["offer_price_usd"])))
    eff_stat = str(spec["statutory_authority"])
    regulator_name = str(spec["regulator_name"])
    trend_count = int(spec["trend_series_count"])
    trend_labels = [lbl for lbl in spec.get("trend_series_labels", []) if lbl]
    trend_preview = ", ".join(trend_labels[:2]) if trend_labels else "2024 to 2030 Statutory Benchmark Series"
    checkout_url = (
        f'/api/lead-capture?checkout=1&amp;sku={offer_sku}'
        f'&amp;tool_slug={slug_clean}&amp;amount={amt_int}&amp;redirect=1'
    )
    datapack_url = (
        f'/api/lead-capture?fulfill=1&amp;sku={offer_sku}'
        f'&amp;tool_slug={slug_clean}&amp;amount={amt_int}&amp;format=datapack'
    )
    deliverables = list(spec.get("deliverables") or [])
    deliv_1 = deliverables[0] if len(deliverables) > 0 else "Line-coded statutory reconciliation schedule (HTML/PDF & CSV)"
    deliv_2 = deliverables[1] if len(deliverables) > 1 else "Multi-scenario stress-test sensitivity matrix"

    if prop_clean == "prexvo":
        is_explicit_refi = "refinance" in slug_clean or "refinancing" in slug_clean
        if not is_explicit_refi:
            offer_title = "Prexvo Title IV Repayment & Amortization Decision Audit Kit"
        badge_text = "Post-Calculation Borrower & Advisor Deliverable"
        pillar_1_title = "1. Personalized Loan Audit Workpaper (HTML/PDF + CSV)"
        pillar_2_title = f"2. Tailored Title IV & Rate Data Pack ({trend_count} Series, 2024 to 2030)"
    elif prop_clean == "gainhelm":
        badge_text = "Post-Calculation Board, CISO & Assessor Deliverable"
        pillar_1_title = "1. Personalized Audit Readiness Workpaper (HTML/PDF + CSV)"
        pillar_2_title = f"2. Tailored Multi-Framework Benchmark Data Pack ({trend_count} Series, 2024 to 2030)"
    else:
        badge_text = "Post-Calculation CPA, CFO & Tax Committee Deliverable"
        pillar_1_title = "1. Personalized Statutory Tax Workpaper (HTML/PDF + CSV)"
        pillar_2_title = f"2. Tailored IRS & Macroeconomic Data Pack ({trend_count} Series, 2024 to 2030)"

    return (
        f'        <div id="post-calculation-upgrade-drawer" class="post-calc-upgrade-drawer" '
        f'data-mechanic="post_calculation_workpaper_upgrade" '
        f'data-property-id="{prop_clean}" '
        f'data-tool-slug="{slug_clean}" '
        f'data-offer-sku="{offer_sku}" '
        f'data-offer-price="{price_int}" '
        f'data-calculated-amount="{amt_int}" '
        f'data-datapack-url="{datapack_url}">\n'
        f'          <div class="post-calc-upgrade-header">\n'
        f'            <span class="post-calc-upgrade-badge">{badge_text}</span>\n'
        f'            <h4 class="post-calc-upgrade-title">{offer_title} (${price_int} One-Time Package)</h4>\n'
        f'            <p id="post-calc-upgrade-live-summary" class="post-calc-upgrade-summary">'
        f'Package your active <strong>{amt_fmt}</strong> scenario into a board-ready audit workpaper and machine-readable '
        f'statutory data pack cited to <strong>{eff_stat}</strong> ({regulator_name}).</p>\n'
        f'          </div>\n'
        f'          <div class="post-calc-upgrade-pillars">\n'
        f'            <div class="post-calc-upgrade-pillar">\n'
        f'              <div class="post-calc-pillar-heading">{pillar_1_title}</div>\n'
        f'              <p class="post-calc-pillar-copy">{deliv_1}; {deliv_2}; bound directly to your live calculator inputs.</p>\n'
        f'            </div>\n'
        f'            <div class="post-calc-upgrade-pillar">\n'
        f'              <div class="post-calc-pillar-heading">{pillar_2_title}</div>\n'
        f'              <p class="post-calc-pillar-copy">Structured JSON and CSV statutory tables covering {trend_preview} for offline spreadsheet modeling.</p>\n'
        f'            </div>\n'
        f'          </div>\n'
        f'          <div class="post-calc-upgrade-actions" role="group" aria-label="Post-Calculation Workpaper and Data Pack Actions">\n'
        f'            <a id="btn-post-calc-upgrade-checkout" href="{checkout_url}" '
        f'class="touch-target btn-primary post-calc-upgrade-btn" '
        f'data-checkout-trigger="1" data-offer-sku="{offer_sku}" data-offer-price="{price_int}" '
        f'data-cta-slot="post_calc_workpaper_upgrade_cta" '
        f'style="display: inline-flex; align-items: center; justify-content: center; min-height: 48px; min-width: 48px; padding: 10px 18px; border-radius: 8px; font-weight: 700; font-size: 14px; text-decoration: none; cursor: pointer;">'
        f'Export Audit Workpaper &amp; Statutory Data Pack (${price_int})</a>\n'
        f'            <button type="button" id="btn-preview-post-calc-workpaper" '
        f'class="touch-target btn-preset serp-blueprint-btn" '
        f'data-blueprint-action="preview_workpaper" data-cta-slot="preview_workpaper_cta" '
        f'style="min-height: 48px; min-width: 48px; padding: 10px 16px; font-size: 13.5px; font-weight: 600; cursor: pointer;">'
        f'Preview Personalized Schedule &amp; Data Pack</button>\n'
        f'          </div>\n'
        f'          <div id="post-calc-workpaper-preview-slot" class="post-calc-preview-slot" aria-live="polite"></div>\n'
        f'        </div>'
    )


def _render_saveable_decision_blueprint_html(
    slug: str,
    topic_label: str = "",
    statutory_authority: str = "",
    economic_dataset: str = "",
    is_prexvo: bool = False,
    is_gainhelm: bool = False,
    property_id: str = "",
) -> str:
    """Renders the saveable decision blueprint bar with localStorage persistence, deep-link URL sync, JSON export, and post-calculation workpaper upgrade drawer."""
    if is_prexvo:
        reviewer_label = "borrower or financial aid review"
        eff_stat = statutory_authority or "34 CFR Part 685 and Higher Education Act Title IV"
        eff_prop = property_id or "prexvo"
    elif is_gainhelm:
        reviewer_label = "CISO, CPA auditor, or C3PAO assessor review"
        eff_stat = statutory_authority or "AICPA SSAE 18, NIST SP 800-171, and ISO/IEC 27001:2022"
        eff_prop = property_id or "gainhelm"
    else:
        reviewer_label = "CPA or advisor review"
        eff_stat = statutory_authority or "26 U.S.C. Internal Revenue Code"
        eff_prop = property_id or "profithelm"
    upgrade_drawer_html = render_post_calculation_upgrade_drawer_html(
        slug=slug,
        property_id=eff_prop,
        topic_label=topic_label,
        statutory_authority=eff_stat,
        economic_dataset=economic_dataset,
    )
    upgrade_block = f"\n{upgrade_drawer_html}" if upgrade_drawer_html else ""
    return (
        f'      <div id="saveable-decision-blueprint" class="serp-decision-blueprint" data-mechanic="saveable_decision_blueprint" data-blueprint-slug="{slug}">\n'
        f'        <h3 style="margin-top: 20px; margin-bottom: 8px;">Saveable Decision Blueprint &amp; Audit-Ready State Export</h3>\n'
        f'        <p style="font-size: 14px; color: var(--text-secondary, #475569); margin-bottom: 10px;">Persist your active parameters locally, copy a parameterized deep-link URL for {reviewer_label}, or export a structured JSON decision blueprint cited to <strong>{eff_stat}</strong>:</p>\n'
        f'        <div class="serp-preset-bar" role="group" aria-label="Decision Blueprint Persistence Controls">\n'
        f'          <button type="button" id="btn-save-blueprint" class="touch-target btn-preset serp-blueprint-btn" data-cta-slot="save_blueprint_cta" data-blueprint-action="save">Save Decision Blueprint</button>\n'
        f'          <button type="button" id="btn-copy-blueprint-link" class="touch-target btn-preset serp-blueprint-btn" data-cta-slot="share_blueprint_cta" data-blueprint-action="share">Copy Shareable Blueprint Link</button>\n'
        f'          <button type="button" id="btn-export-blueprint-json" class="touch-target btn-preset serp-blueprint-btn" data-cta-slot="export_blueprint_cta" data-blueprint-action="export">Export JSON Decision Blueprint</button>\n'
        f'        </div>\n'
        f'        <div id="blueprint-status-readout" class="serp-blueprint-status" aria-live="polite" style="font-size: 13px; color: var(--text-secondary, #64748b); margin-top: 8px;">Blueprint state ready: deterministic server-rendered baseline loaded ({topic_label}).</div>'
        f'{upgrade_block}\n'
        f'      </div>'
    )


def render_serp_incumbent_depth_upgrade_block(
    slug: str,
    title: str = "",
    property_id: str = "profithelm",
    canonical_base: str = "https://profithelm.com",
    statutory_authority: str = "26 U.S.C. Section 1256; CFTC 17 CFR Part 40",
    economic_dataset: str = "FRED 3-Month Treasury Bill (DTB3) and CFTC DCM Series",
    topic_label: str = "",
) -> str:
    """
    Renders the SERP Incumbent Depth Upgrade Workbench (#serp-incumbent-depth-workbench)
    engineered from live Google and Bing SERP competitor analysis to outrank #1 incumbents across:
      1. One-Click Archetype Presets (data-calc-preset + data-cta-slot="calculator_preset_cta")
      2. Multi-Variable Sub-Ledger Inputs (Cost Basis/FIFO-HIFO-LIFO, Pre-Tax 401k/HSA/PTET,
         GVWR/Income Cap/Financing APR, Relinquished/Replacement Debt Boot & 45/180-Day Window,
         and MFS vs MFJ Spouse AGI & 5-Plan Title IV Matrix)
      3. Live Reactive Multi-Segment SVG Visual Breakdown Bar Chart
      4. Authoritative Primary Data Reference Schedule Table (e.g. 10-tier CA FTB 540 schedule)
      5. Dynamic Calculation-Bound Commercial Intent Callout (#dynamic-commercial-intent-banner)
      6. Native TCPA-Compliant Partner Quote Intake Step (#partner-quote-intake-step)
      7. Multi-Year Statutory & Repayment Cliff Visualizer (#multi-year-cliff-visualizer)
      8. Stateful Side-by-Side Scenario Comparator (#stateful-scenario-comparator)
      9. Saveable Decision Blueprint (#saveable-decision-blueprint)
    Zero em-dashes. Zero en-dashes. Zero spaced hyphens.
    """
    s_low = str(slug or "").strip().lower()
    is_prexvo = property_id.strip().lower() == "prexvo"
    is_gainhelm = property_id.strip().lower() == "gainhelm"
    topic_label = _format_safe_heading_topic(title, slug)
    veh_slugs = {v[0] for v in PROFITHELM_SECTION_179_VEHICLES}

    if is_prexvo:
        spec = _build_repayment_loan_depth_spec(slug, topic_label, statutory_authority)
    elif is_gainhelm:
        spec = _build_gainhelm_depth_spec(topic_label, statutory_authority, economic_dataset)
    elif any(
        tok in s_low
        for tok in (
            "prediction",
            "kalshi",
            "polymarket",
            "implied-probability",
            "kelly",
            "section-1256",
            "event-contract",
        )
    ):
        spec = _build_prediction_market_depth_spec(topic_label, statutory_authority, economic_dataset)
    elif any(tok in s_low for tok in ("crypto", "staking", "8949", "1099-da", "wash")):
        spec = _build_crypto_depth_spec(topic_label, statutory_authority)
    elif (
        s_low in veh_slugs
        or any(
            tok in s_low
            for tok in (
                "179",
                "equipment",
                "lease",
                "macrs",
                "depreciation",
                "vehicle",
                "gvwr",
                "yukon",
                "f250",
                "sprinter",
                "cybertruck",
                "silverado",
                "ram",
                "transit",
                "escalade",
            )
        )
    ):
        spec = _build_sec179_depth_spec(topic_label, statutory_authority)
    elif any(tok in s_low for tok in ("1031", "like-kind", "exchange", "ftb-3840", "8824")):
        spec = _build_sec1031_depth_spec(topic_label, statutory_authority)
    elif any(
        tok in s_low
        for tok in (
            "tax-bracket",
            "irs-2027",
            "ca-tax-brackets",
            "capital-gains",
            "tcja",
            "marginal",
        )
    ):
        spec = _build_tax_brackets_depth_spec(s_low, topic_label, statutory_authority)
    else:
        spec = _build_b2b_depth_spec(topic_label, statutory_authority, economic_dataset)

    preset_buttons_html = "\n".join(
        f'        <button type="button" class="touch-target btn-preset serp-archetype-btn" '
        f'data-cta-slot="calculator_preset_cta" '
        f"data-calc-preset='{p_json}'>{p_label}</button>"
        for p_label, p_json in spec["presets"]
    )
    metrics_cards_html = "\n".join(
        f'        <div class="serp-metric-box">\n'
        f'          <div class="serp-metric-label">{m_label}</div>\n'
        f'          <div id="{m_id}" class="serp-metric-val calc-metric-value">{m_val}</div>\n'
        f'        </div>'
        for m_id, m_label, m_val in spec["metrics_meta"]
    )
    th_html = "\n".join(f'              <th scope="col">{h}</th>' for h in spec["table_headers"])
    tr_html = "\n".join(
        f'            <tr>\n'
        f'              <td><strong>{c1}</strong></td>\n'
        f'              <td>{c2}</td>\n'
        f'              <td>{c3}</td>\n'
        f'              <td>{c4}</td>\n'
        f'            </tr>'
        for c1, c2, c3, c4 in spec["table_rows"]
    )
    quote_intake_html = render_partner_quote_intake_html(
        slug=s_low,
        property_id=property_id,
        topic_label=topic_label,
        statutory_authority=statutory_authority,
    )
    quote_intake_block = f"{quote_intake_html}\n" if quote_intake_html else ""
    cliff_html = _render_multi_year_cliff_visualizer_html(
        topic_label=topic_label,
        is_prexvo=is_prexvo,
        statutory_authority=statutory_authority,
        economic_dataset=economic_dataset,
        is_gainhelm=is_gainhelm,
        slug=s_low,
    )
    comparator_html = _render_stateful_scenario_comparator_html(
        topic_label=topic_label,
        is_prexvo=is_prexvo,
        statutory_authority=statutory_authority,
        economic_dataset=economic_dataset,
        is_gainhelm=is_gainhelm,
        slug=s_low,
    )
    blueprint_html = _render_saveable_decision_blueprint_html(
        slug=s_low,
        topic_label=topic_label,
        statutory_authority=statutory_authority,
        economic_dataset=economic_dataset,
        is_prexvo=is_prexvo,
        is_gainhelm=is_gainhelm,
    )

    return (
        f'    <section id="serp-incumbent-depth-workbench" class="serp-depth-workbench card pseo-card" '
        f'data-mechanic="serp_incumbent_depth_upgrade" data-workbench-mode="{spec["workbench_mode"]}">\n'
        f'      <h2>{spec["workbench_h2"]}</h2>\n'
        f'      <p class="serp-workbench-intro">{spec["workbench_intro"]}</p>\n'
        f'      <div class="serp-preset-bar" role="group" aria-label="One-Click Statutory Scenario Archetypes">\n'
        f'{preset_buttons_html}\n'
        f'      </div>\n'
        f'      <div class="serp-sub-inputs-grid">\n'
        f'{spec["inputs_html"]}\n'
        f'      </div>\n'
        f'      <div class="serp-metrics-grid" aria-live="polite">\n'
        f'{metrics_cards_html}\n'
        f'      </div>\n'
        f'      <div class="serp-svg-chart-wrap">\n'
        f'        <svg class="serp-visual-breakdown-svg" viewBox="0 0 600 76" role="img" aria-label="Interactive Retained Capital versus Statutory Exposure Breakdown">\n'
        f'          <desc>Interactive Retained Capital versus Statutory Exposure Breakdown</desc>\n'
        f'          <rect x="0" y="8" width="600" height="26" rx="6" fill="var(--bg-inset, #0b1329)" />\n'
        f'          <rect id="serp-svg-bar-retained" x="0" y="8" width="{spec["svg_left_width"]}" height="26" rx="6" fill="var(--status-positive, #10b981)" />\n'
        f'          <rect id="serp-svg-bar-tax" x="{spec["svg_right_x"]}" y="8" width="{spec["svg_right_width"]}" height="26" rx="6" fill="var(--accent, #38bdf8)" />\n'
        f'          <text id="serp-svg-label-retained" x="8" y="58" fill="var(--text, #f8fafc)" font-size="13" font-weight="600">{spec["svg_left_label"]}</text>\n'
        f'          <text id="serp-svg-label-tax" x="592" y="58" text-anchor="end" fill="var(--text-secondary, #cbd5e1)" font-size="13" font-weight="600">{spec["svg_right_label"]}</text>\n'
        f'        </svg>\n'
        f'      </div>\n'
        f'{spec["banner_html"]}\n'
        f'{quote_intake_block}'
        f'{cliff_html}\n'
        f'{comparator_html}\n'
        f'{blueprint_html}\n'
        f'      <h3 id="serp-statutory-reference-schedule" style="margin-top: 22px; margin-bottom: 10px;">{spec["table_h3"]}</h3>\n'
        f'      <p style="font-size: 14px; color: var(--text-secondary, #475569); margin-bottom: 12px;">The following primary statutory schedule reconciles official rate tiers, deduction caps, phaseout thresholds, and filing forms under <strong>{statutory_authority}</strong> and <strong>{economic_dataset}</strong>:</p>\n'
        f'      <div class="table-wrap pseo-table-wrap">\n'
        f'        <table class="comparison-table serp-statutory-reference-table" data-statutory-source="{statutory_authority}" data-economic-source="{economic_dataset}">\n'
        f'          <thead>\n'
        f'            <tr>\n'
        f'{th_html}\n'
        f'            </tr>\n'
        f'          </thead>\n'
        f'          <tbody>\n'
        f'{tr_html}\n'
        f'          </tbody>\n'
        f'        </table>\n'
        f'      </div>\n'
        f'    </section>'
    )



def render_competitor_winning_pattern_blocks(
    slug: str,
    title: str,
    property_id: str,
    canonical_base: str,
    statutory_authority: str,
    economic_dataset: str,
) -> Dict[str, str]:
    """
    Renders the 5 winning competitor patterns in HTML for compile_high_effort_page
    and RetroReflectionEngine:
      1. Calculator Immediacy: instant_edge_case_trap_immediacy
      2. Interactive Sub-Ledger & Primary Data Density: serp_incumbent_depth_upgrade
      3. Authority Framing: statutory_compliance_framing (Beyond the Calculator + Pitfall Matrix)
      4. Topic Clustering: on_this_page_jump_nav + three_tier_topic_cluster_nav
      5. Commercial Handoffs: vetted_commercial_handoff_framing
    Zero em-dashes. Zero en-dashes. Zero spaced hyphens.
    """
    ctx = _resolve_vertical_competitor_content(
        slug=slug,
        property_id=property_id,
        statutory_authority=statutory_authority,
        canonical_base=canonical_base,
    )
    base_url = ctx["base_url"]
    topic_label = _format_safe_heading_topic(title, slug)
    serp_depth_upgrade_html = render_serp_incumbent_depth_upgrade_block(
        slug=slug,
        title=title,
        property_id=property_id,
        canonical_base=canonical_base,
        statutory_authority=statutory_authority,
        economic_dataset=economic_dataset,
    )

    # Extract 2 contextual peer tools for in-prose linking inside statutory compliance
    peer_links: List[Tuple[str, str]] = []
    for _, tier_links in ctx["tier_clusters"]:
        for t_slug, t_label in tier_links:
            if t_slug != slug and all(p_s != t_slug for p_s, _ in peer_links):
                peer_links.append((t_slug, t_label))
                if len(peer_links) >= 2:
                    break
        if len(peer_links) >= 2:
            break
    if not peer_links:
        peer_links = [("section-179-calculator", "Section 179 Equipment Expense Calculator")]
    peer_1_slug, peer_1_label = peer_links[0]
    peer_2_slug, peer_2_label = peer_links[1] if len(peer_links) > 1 else peer_links[0]

    on_this_page_html = (
        '    <nav class="on-this-page-nav card pseo-card" aria-label="On This Page" '
        'data-mechanic="on_this_page_jump_nav">\n'
        '      <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted, #475569); margin-bottom: 8px;">On This Page: Rapid Decision Navigation</div>\n'
        '      <div style="display: flex; flex-wrap: wrap; gap: 8px;">\n'
        '        <a href="#statutory-trap-alert" class="touch-target" style="display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; padding: 10px 14px; border-radius: 8px; background: var(--bg-elevated, #eff6ff); color: var(--accent, #1d4ed8); border: 1px solid var(--border-strong, #bfdbfe); text-decoration: none; font-size: 14px; font-weight: 600;">1. Statutory Deadline &amp; Edge-Case Trap</a>\n'
        '        <a href="#serp-incumbent-depth-workbench" class="touch-target" style="display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; padding: 10px 14px; border-radius: 8px; background: var(--bg-elevated, #eff6ff); color: var(--accent, #1d4ed8); border: 1px solid var(--border-strong, #bfdbfe); text-decoration: none; font-size: 14px; font-weight: 600;">2. Interactive Sub-Ledger &amp; Rate Schedule</a>\n'
        '        <a href="#vetted-commercial-handoff" class="touch-target" style="display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; padding: 10px 14px; border-radius: 8px; background: var(--bg-elevated, #eff6ff); color: var(--accent, #1d4ed8); border: 1px solid var(--border-strong, #bfdbfe); text-decoration: none; font-size: 14px; font-weight: 600;">3. Provider Vetting Checklist</a>\n'
        '        <a href="#statutory-compliance-checklist" class="touch-target" style="display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; padding: 10px 14px; border-radius: 8px; background: var(--bg-elevated, #eff6ff); color: var(--accent, #1d4ed8); border: 1px solid var(--border-strong, #bfdbfe); text-decoration: none; font-size: 14px; font-weight: 600;">4. Beyond the Calculator Checklist</a>\n'
        '        <a href="#statutory-pitfalls-matrix" class="touch-target" style="display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; padding: 10px 14px; border-radius: 8px; background: var(--bg-elevated, #eff6ff); color: var(--accent, #1d4ed8); border: 1px solid var(--border-strong, #bfdbfe); text-decoration: none; font-size: 14px; font-weight: 600;">5. Common Statutory Pitfalls</a>\n'
        '        <a href="#topic-cluster-hub" class="touch-target" style="display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; padding: 10px 14px; border-radius: 8px; background: var(--bg-elevated, #eff6ff); color: var(--accent, #1d4ed8); border: 1px solid var(--border-strong, #bfdbfe); text-decoration: none; font-size: 14px; font-weight: 600;">6. 3-Tier Topic Cluster</a>\n'
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
        f'      <h2>Beyond the Calculator: {topic_label} Statutory Compliance and Procedural Verification</h2>\n'
        f'      <p>Deterministic arithmetic under <strong>{statutory_authority}</strong> computes your baseline quantitative exposure, while adjacent scenarios can be cross-checked with the <a href="{base_url}/tools/{peer_1_slug}/" class="touch-target" style="display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; padding: 4px 8px; font-weight: 600; text-decoration: underline;">{peer_1_label}</a> and the <a href="{base_url}/tools/{peer_2_slug}/" class="touch-target" style="display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; padding: 4px 8px; font-weight: 600; text-decoration: underline;">{peer_2_label}</a>. Audit-ready qualification depends on strict procedural execution that no calculator can verify automatically:</p>\n'
        f'      <ol style="padding-left: 20px; margin-top: 12px; margin-bottom: 20px;">\n'
        f'{checklist_li}\n'
        f'      </ol>\n'
        f'      <h3 id="statutory-pitfalls-matrix" style="margin-top: 18px; margin-bottom: 10px;">Common Statutory Pitfalls: {topic_label} Issue to Prevention Matrix</h3>\n'
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
        f'      <h2>Connected Statutory Topic Cluster: {topic_label} Decision Architecture</h2>\n'
        f'      <p style="font-size: 14px; color: var(--text-muted, #475569); margin-bottom: 14px;">Navigate connected pillar models, side-by-side comparative matrices, and jurisdiction/entity compliance calculators:</p>\n'
        f'{joined_tiers}\n'
        f'    </section>'
    )

    handoff_li = "\n".join(
        f'        <li style="margin-bottom: 6px; font-size: 13px;">{h_item}</li>'
        for h_item in ctx["handoff_items"]
    )
    safe_handoff_h2 = _format_safe_heading_topic(ctx["handoff_title"], slug)
    vetted_handoff_html = (
        f'    <section id="vetted-commercial-handoff" class="commercial-handoff-vetting card pseo-card" '
        f'data-mechanic="vetted_commercial_handoff_framing">\n'
        f'      <h2>{safe_handoff_h2}: {topic_label}</h2>\n'
        f'      <ol style="padding-left: 18px; margin: 0;">\n'
        f'{handoff_li}\n'
        f'      </ol>\n'
        f'    </section>'
    )

    return {
        "on_this_page_nav_html": on_this_page_html,
        "edge_case_trap_html": edge_case_trap_html,
        "serp_depth_upgrade_html": serp_depth_upgrade_html,
        "statutory_compliance_html": statutory_compliance_html,
        "three_tier_cluster_html": three_tier_cluster_html,
        "vetted_handoff_html": vetted_handoff_html,
    }


COMPETITIVE_INCUMBENT_PROFILES: Dict[str, Dict[str, Any]] = {
    "section-1031-calculator": {
        "property_id": "profithelm",
        "slug": "section-1031-calculator",
        "target_queries": [
            "1031 exchange calculator",
            "partial 1031 exchange calculator",
            "1031 exchange boot calculator",
            "california 1031 exchange clawback calculator",
        ],
        "incumbent_urls": [
            "https://www.ipx1031.com/capital-gain-estimator/",
            "https://www.deferred.com/1031-exchange-calculator",
            "https://www.exeter1031.com/1031_exchange_calculators.aspx",
            "https://www.start1031.com/1031-exchange-calculator/",
        ],
        "calculator_interactivity": (
            "Incumbents pair relinquished sale price, adjusted basis, and accumulated depreciation inputs "
            "with immediate debt-boot vs cash-boot decomposition, 25% IRC Section 1250 unrecaptured depreciation "
            "recapture, 3.8% NIIT surtax, and 45-day identification / 180-day closing calendar trackers."
        ),
        "visual_hierarchy": (
            "Above-the-fold two-column input-to-waterfall layout highlighting Total Taxes Deferred vs Total "
            "Taxable Boot Recognized in high-contrast metric cards before explanatory prose."
        ),
        "content_effort": (
            "Worked partial-downsize mortgage boot scenarios, Three-Property vs 200% identification rule "
            "decision matrices, and state clawback reporting tables (California FTB Form 3840, Oregon Form OR-24)."
        ),
        "trust_signals": (
            "Explicit citations to IRC Section 1031(a)(3), Treasury Regulation 1.1031(k)-1(g)(4) Qualified "
            "Intermediary safe-harbor rules, IRS Form 8824 line mappings, and segregated escrow disclosures."
        ),
        "seo_structure": (
            "Dedicated hub calculator connected to 50 state-level 1031 exchange spoke schedules with clean "
            "50-60 char titles, 120-155 char whole-sentence meta descriptions, Dataset + HowTo + FAQPage JSON-LD, "
            "and nofollow parameterized preset links to prevent duplicate query-string crawl bloat."
        ),
        "counter_strategy_executed": (
            "Eliminated mid-word meta description truncation ('state clawb.'), added rel='nofollow' on "
            "parameterized scenario preset links, and combined live Form 8824 boot/recapture/45-180 day "
            "countdown workbench with direct Qualified Intermediary / DST replacement handoff."
        ),
    },
    "crypto-tax-calculator": {
        "property_id": "profithelm",
        "slug": "crypto-tax-calculator",
        "target_queries": [
            "crypto tax calculator",
            "cryptocurrency capital gains tax calculator",
            "form 1099-da crypto tax calculator",
            "bitcoin tax calculator",
        ],
        "incumbent_urls": [
            "https://coinledger.io/crypto-tax-calculator",
            "https://koinly.io/crypto-tax-calculator/",
            "https://tokentax.co/crypto-tax-calculator",
            "https://www.nerdwallet.com/calculator/crypto-tax-calculator",
        ],
        "calculator_interactivity": (
            "CoinLedger and Koinly provide instant disposal proceeds, cost basis, transaction fee offset, "
            "holding period toggle (<=12 months ordinary brackets vs >12 months 0%/15%/20% LTCG), filing "
            "status, and 3.8% IRC Section 1411 NIIT surtax calculation."
        ),
        "visual_hierarchy": (
            "Immediate disposal gain/loss summary card paired with a low-friction portfolio import CTA "
            "('Import Exchange CSV / API to Generate IRS Form 8949 in Minutes - Free Preview')."
        ),
        "content_effort": (
            "Side-by-side FIFO vs Specific Identification (Rev. Proc. 2024-28 wallet-by-wallet) comparison, "
            "IRS Form 1099-DA broker gross proceeds reconciliation, and wash-sale / tax-loss harvesting rules."
        ),
        "trust_signals": (
            "Citations to IRC Section 1012, IRS Notice 2014-21, Rev. Rul. 2023-14 (staking income), Form 8949 "
            "Box A/B/D/E mappings, and verified CoinLedger partner integration."
        ),
        "seo_structure": (
            "SoftwareApplication + Dataset + HowTo + FAQPage schema graph, disambiguated title/meta snippet "
            "without redundant 'Calculate Crypto Tax Calculator' phrasing, and direct spoke linkage to "
            "/tools/crypto-tax-form-1099-da-mandatory-reporting/."
        ),
        "counter_strategy_executed": (
            "Repaired redundant meta description phrasing, injected Dataset + HowTo schema onto companion "
            "Form 1099-DA spoke, and paired Form 8949 lot-accounting workbench with verified CoinLedger "
            "automated tax-lot reconciliation CTA."
        ),
    },
    "section-179-calculator": {
        "property_id": "profithelm",
        "slug": "section-179-calculator",
        "target_queries": [
            "section 179 calculator",
            "section 179 deduction calculator 2026",
            "section 179 vehicle deduction calculator",
            "equipment lease vs buy section 179 calculator",
        ],
        "incumbent_urls": [
            "https://www.crestcapital.com/tax_deduction_calculator",
            "https://www.nav.com/resource/section-179-calculator/",
            "https://turbotax.intuit.com/tax-tools/calculators/section-179/",
        ],
        "calculator_interactivity": (
            "Crest Capital pairs equipment purchase cost and marginal tax bracket inputs with instant "
            "Section 179 deduction ($2,560,000 cap, $4,090,000 phase-out), Section 168(k) bonus depreciation, "
            "cash tax savings, net out-of-pocket equipment cost, and a soft-pull equipment financing eligibility check."
        ),
        "visual_hierarchy": (
            "Three-step input panel on the left paired with bold First-Year Write-Off, Cash Tax Savings, "
            "and Net Equipment Cost After Tax cards on the right, followed by a 4-step financing workflow."
        ),
        "content_effort": (
            "Explicit GVWR vehicle classification tiers (Passenger Auto <=6,000 lbs vs Heavy SUV 6,000-14,000 lbs "
            "$30,500 cap vs Cargo/Work Truck >6ft bed 100% cap), placed-in-service deadline rules, and Section "
            "179(d)(10) recapture warnings when business use drops to 50% or below."
        ),
        "trust_signals": (
            "Exact statutory citations to 26 U.S.C. Section 179, IRC Section 168(k), IRC Section 280F luxury "
            "auto limits, IRS Form 4562 Part I, and TILA Reg-Z soft-pull commercial financing disclosures."
        ),
        "seo_structure": (
            "Hub calculator linked to 27 commercial vehicle GVWR spokes and companion equipment lease/ROI "
            "calculators with Dataset + HowTo rich result schemas and commercial-intent query filtering that "
            "excludes off-intent auto-shopping ('for sale', 'deals near me') vanity impressions."
        ),
        "counter_strategy_executed": (
            "Upgraded meta description to cite exact $2,560,000 cap and $4,090,000 phase-out under Form 4562, "
            "injected Dataset + HowTo JSON-LD across all Section 179 vehicle/equipment companion calculators, "
            "and discounted off-intent vehicle dealership queries in the quantitative revenue forecaster."
        ),
    },
    "irs-2027-tax-brackets": {
        "property_id": "profithelm",
        "slug": "irs-2027-tax-brackets",
        "target_queries": [
            "2027 tax brackets",
            "california tax brackets 2026 2027",
            "2027 tax brackets married filing jointly",
            "tcja sunset tax calculator",
        ],
        "incumbent_urls": [
            "https://www.nerdwallet.com/article/taxes/california-state-tax",
            "https://www.nerdwallet.com/article/taxes/federal-income-tax-brackets",
            "https://taxfoundation.org/data/all/federal/tax-calculator-tcja-expiration/",
            "https://smartasset.com/taxes/california-tax-calculator",
        ],
        "calculator_interactivity": (
            "NerdWallet and Tax Foundation pair filing status, gross income, and state residency inputs with "
            "marginal vs effective tax rate breakdowns, standard deduction offsets, and current IRC Section 1(j) "
            "rates (10% to 37%) vs post-sunset pre-TCJA tier comparisons."
        ),
        "visual_hierarchy": (
            "Quick-answer box with exact dollar tax liability and take-home pay at the top, interactive marginal "
            "bracket waterfall chart in the middle, and complete Single / Married Filing Jointly / Head of "
            "Household statutory rate tables below."
        ),
        "content_effort": (
            "State-specific statutory bracket tables (e.g., California 9 brackets from 1% to 12.3% plus 1% "
            "Mental Health Services Act surtax above $1M = 13.3% top rate, CA standard deduction, FTB Form 540 "
            "residency rules) alongside federal safe-harbor estimated tax rules (IRC Section 6654)."
        ),
        "trust_signals": (
            "Citations to IRC Section 1(j), IRS Revenue Procedure inflation adjustments, California FTB Form 540 "
            "and Publication 1031 residency standards, and verified CPA/EA review methodology."
        ),
        "seo_structure": (
            "National hub plus 51 state/DC spoke calculators with Dataset + HowTo + FAQPage JSON-LD, "
            "state-specific quick-answer dollar figures, and zero duplicate year tokens in H1/title."
        ),
        "counter_strategy_executed": (
            "Eliminated duplicate '2027' year token in hub H1 ('IRS 2027 Tax Brackets & TCJA Sunset Calculator'), "
            "repaired truncated 'Married using' meta description, and preserved state-specific dollar quick-answers "
            "across all 51 jurisdiction spokes."
        ),
    },
    "s-corp-reasonable-salary-tax-calculator": {
        "property_id": "profithelm",
        "slug": "s-corp-reasonable-salary-tax-calculator",
        "target_queries": [
            "s corp reasonable salary calculator",
            "s corp tax calculator",
            "llc vs s corp tax calculator 2026",
            "s corp fica tax savings calculator",
        ],
        "incumbent_urls": [
            "https://gusto.com/resources/calculators/s-corp-tax-calculator",
            "https://www.collective.com/s-corp-tax-savings-calculator",
            "https://bench.co/blog/tax-tips/s-corp-tax-calculator/",
        ],
        "calculator_interactivity": (
            "Gusto and Collective compute W-2 officer salary vs K-1 shareholder distribution splits, 15.3% FICA "
            "self-employment tax savings up to the $176,100 OASDI cap, 0.9% Additional Medicare Tax, and the "
            "20% IRC Section 199A QBI deduction trade-off."
        ),
        "visual_hierarchy": (
            "Side-by-side Sole Proprietorship / Single-Member LLC vs S-Corporation annual tax comparison card "
            "with net FICA savings highlighted above an automated W-2 officer payroll onboarding CTA."
        ),
        "content_effort": (
            "IRS multi-factor reasonable compensation audit standards (training, duties, time devoted, comparable "
            "BLS OEWS wages), state-level S-Corp franchise/entity fees (e.g., CA 1.5% / $800 minimum), and "
            "Form 1120-S / Form 941 payroll compliance costs."
        ),
        "trust_signals": (
            "Citations to IRC Section 1366, IRC Section 199A, IRC Section 3121, IRS Fact Sheet FS-2008-25, "
            "and direct verified Gusto ($100 CPA) and Rippling ($1,600 SQO+Won) partner integrations."
        ),
        "seo_structure": (
            "Full Organization + WebApplication + TechArticle + Dataset + HowTo + FAQPage + BreadcrumbList "
            "JSON-LD graph to capture Google Dataset and FAQ rich results alongside Breadcrumbs."
        ),
        "counter_strategy_executed": (
            "Injected missing Dataset and HowTo JSON-LD schemas into /tools/s-corp-reasonable-salary-tax-calculator/ "
            "(fixing the GSC inspection gap where only Breadcrumbs were detected) and prioritized it in the "
            "quantitative revenue forecast."
        ),
    },
    "rap-payment-calculator": {
        "property_id": "prexvo",
        "slug": "rap-payment-calculator",
        "target_queries": [
            "rap calculator",
            "repayment assistance plan calculator",
            "rap vs ibr calculator",
            "obbba student loan repayment calculator",
        ],
        "incumbent_urls": [
            "https://www.studentloanplanner.com/repayment-assistance-plan-rap-calculator/",
            "https://www.nerdwallet.com/article/loans/student-loans/repayment-assistance-plan-rap",
            "https://studentaid.gov/loan-simulator/",
        ],
        "calculator_interactivity": (
            "Student Loan Planner models OBBBA Repayment Assistance Plan (RAP) tiered AGI brackets (1% to 10% "
            "of AGI), $50 per-dependent monthly reduction, $10 minimum monthly payment, 100% unpaid interest "
            "subsidy, and direct side-by-side comparison against New IBR (10%), Old IBR (15%), and private "
            "refinance monthly payments."
        ),
        "visual_hierarchy": (
            "Instant Monthly RAP Payment vs Monthly IBR Payment vs 10-Year Standard Cap comparison cards at "
            "the top, followed by MFS vs MFJ spouse AGI isolation toggle and July 1, 2026 statutory transition timeline."
        ),
        "content_effort": (
            "Detailed breakdown of Public Law 119-21 (OBBBA) Title VIII Subtitle B provisions, July 1, 2026 "
            "RAP launch date, July 1, 2028 SAVE/ICR/PAYE sunset deadline, 30-year (360-month) RAP forgiveness "
            "horizon vs 20/25-year IBR, and high-income private refinance decision thresholds."
        ),
        "trust_signals": (
            "Citations to OBBBA Title VIII Subtitle B, HEA Section 493C (20 U.S.C. 1098e), 34 CFR 685.209, "
            "2026 HHS Federal Poverty Guidelines ($15,650 base + $5,500 per person), and mandatory Title IV "
            "forfeiture warnings before private refinancing."
        ),
        "seo_structure": (
            "Clean 50-60 char titles without robotic 'Model Tool Guide' padding, plan-specific 120-155 char "
            "meta descriptions, Dataset + HowTo + FAQPage JSON-LD, and contextual internal links to companion "
            "IBR, ICR, MFS, and Refinance Break-Even calculators."
        ),
        "counter_strategy_executed": (
            "Purged robotic 'Model Tool Guide' title padding and redundant 'Calculate RAP Calculator' meta "
            "descriptions on /tools/rap-payment-calculator/ and /tools/rap-vs-ibr-calculator/, and connected "
            "all commercial IDR hubs to /tools/student-loan-refinance-break-even-calculator/."
        ),
    },
    "student-loan-refinance-break-even-calculator": {
        "property_id": "prexvo",
        "slug": "student-loan-refinance-break-even-calculator",
        "target_queries": [
            "student loan refinance break even calculator",
            "student loan refinance calculator",
            "should i refinance federal student loans or stay on idr",
            "income based student loan repayment calculator",
        ],
        "incumbent_urls": [
            "https://www.bankrate.com/loans/student-loans/student-loan-calculator/",
            "https://www.sofi.com/student-loan-refinancing-calculator/",
            "https://www.earnest.com/student-loan-refinance-calculator",
        ],
        "calculator_interactivity": (
            "Bankrate, SoFi, and Earnest compare current weighted-average federal loan APR (6.80% to 8.05% "
            "Direct Unsubsidized/PLUS) against private refinance fixed APRs (4.99% to 5.50%), showing monthly "
            "payment delta, lifetime interest saved, and break-even month horizon."
        ),
        "visual_hierarchy": (
            "Side-by-side Federal Title IV Retention vs Private Refinance Conversion comparison cards with "
            "an explicit PSLF / IDR forfeiture warning banner and soft-pull rate check checklist."
        ),
        "content_effort": (
            "Quantitative break-even analysis accounting for lost RAP unpaid interest subsidies, 10-year "
            "Standard Repayment cap ceilings, Debt-to-Income (DTI) underwriting thresholds, and TILA Reg-Z "
            "soft-pull pre-qualification rights."
        ),
        "trust_signals": (
            "Explicit 34 CFR Part 685 Title IV forfeiture disclosures, TILA Regulation Z (12 CFR Part 1026) "
            "APR rules, and strict zero-commercial isolation on PSLF/SAVE/IBR-hardship public-service pages."
        ),
        "seo_structure": (
            "Dedicated refinance break-even meta description (replacing generic 225% HHS Poverty Guideline copy), "
            "bespoke APR Spread vs Title IV Break-Even workbench heading/intro, and contextual inbound links "
            "from all 9 commercial Prexvo calculators."
        ),
        "counter_strategy_executed": (
            "Replaced wrong 'Calculate Student Loan Refinance Break under Title IV 34 CFR Part 685 using 225% "
            "HHS Poverty Guidelines' meta description with refinance APR spread & break-even copy, upgraded the "
            "bespoke SERP workbench to 'Interactive Private Refinance APR Spread vs. Title IV Break-Even Matrix', "
            "and increased contextual inbound links from 1 to >=9 across Prexvo hubs."
        ),
    },
    "prediction-market-odds": {
        "property_id": "profithelm",
        "slug": "prediction-market-odds",
        "target_queries": [
            "prediction market odds calculator",
            "implied probability calculator",
            "kalshi fee calculator",
            "prediction market ev calculator",
            "polymarket odds calculator",
        ],
        "incumbent_urls": [
            "https://predictioncalculator.com/calculators/implied-probability",
            "https://predictioncalculator.com/calculators/ev",
            "https://predictioncalculator.com/calculators/kalshi-fees",
            "https://predictioncalculator.com/calculators/kelly-criterion",
        ],
        "calculator_interactivity": (
            "predictioncalculator.com combines Contract Price / American / Decimal / Fractional odds tabs with "
            "two-way multiplicative vig removal, Kalshi Taker (0.07*P*(1-P)) vs Kalshi Maker (0.0175*P*(1-P)) vs "
            "Polymarket (4% winner) fee presets, break-even win rate shift, and cross-calculator data-carry links, "
            "but relies 100% on client-side JS with blank initial HTML output spans (<span data-out='prob'></span>)."
        ),
        "visual_hierarchy": (
            "Two-column input-to-output workbench with one-click exchange fee preset chips ($0.25, $0.50, $0.65, "
            "Kalshi Taker, Kalshi Maker, Polymarket) and instant break-even win probability delta readouts."
        ),
        "content_effort": (
            "Explicit reconciliation of Kalshi quadratic taker/maker fee curves (ceil(0.07*C*P*(1-P)) peaking at "
            "$0.0175 at P=$0.50), two-way market overround de-vigging, fractional Kelly sizing, and IRC Section 1256 "
            "60/40 vs ordinary tax treatment."
        ),
        "trust_signals": (
            "Citations to IRC Section 1256(g), CFTC 17 CFR Part 40 Designated Contract Market rules, IRS Form 6781 "
            "mark-to-market elections, and FRED DGS10 risk-free benchmark series."
        ),
        "seo_structure": (
            "Unified @graph JSON-LD with SoftwareApplication + Dataset + HowTo + FAQPage + BreadcrumbList + Organization "
            "(fixing predictioncalculator.com's fragmented 3-script JSON-LD and double-escaped '&amp;rsquo;' FAQ defects) "
            "plus 100% SSR-hydrated default calculator metrics."
        ),
        "counter_strategy_executed": (
            "Programmatically diffed live predictioncalculator.com DOM snapshots (.agy/scratch/calc_implied_prob.html, "
            "calc_ev.html, calc_kalshi_fees.html, competitor_calculators.js), absorbed Kalshi Taker/Maker and Polymarket "
            "fee schedules + break-even probability shift into an SSR-hydrated workbench, and consolidated cannibalizing "
            "'what-is-implied-probability-in-prediction-markets' clone via 301 redirect."
        ),
    },
    "prediction-market-tax": {
        "property_id": "profithelm",
        "slug": "prediction-market-tax",
        "target_queries": [
            "prediction market tax calculator",
            "kalshi tax calculator",
            "polymarket tax calculator",
            "section 1256 event contract tax calculator",
        ],
        "incumbent_urls": [
            "https://predictioncalculator.com/calculators/kalshi-fees",
            "https://coinledger.io/crypto-tax-calculator",
            "https://koinly.io/crypto-tax-calculator/",
        ],
        "calculator_interactivity": (
            "Models net event-contract settlement gains across CFTC-regulated Designated Contract Markets (IRC Section "
            "1256 60% LTCG / 40% STCG = 26.8% top blended rate) versus non-DCM ordinary/wagering tax treatment (up to "
            "37% ordinary rate + IRC Section 165(d) itemized loss limitations)."
        ),
        "visual_hierarchy": (
            "Side-by-side Regulated DCM (Form 6781) vs Non-DCM Ordinary Tax Liability comparison cards paired with "
            "quadratic exchange fee offset and net post-tax EV retention."
        ),
        "content_effort": (
            "Line-by-line IRS Form 6781 Part I mark-to-market reporting vs Schedule 1 / Schedule A wagering loss "
            "deduction limits, 3.8% IRC Section 1411 NIIT applicability, and Form 1099-B vs Form 1099-MISC reconciliation."
        ),
        "trust_signals": (
            "Citations to 26 U.S.C. Section 1256, IRC Section 165(d), CFTC 17 CFR Part 40, IRS Form 6781, and verified "
            "CoinLedger automated tax-lot reconciliation."
        ),
        "seo_structure": (
            "Unified SoftwareApplication + Dataset + HowTo + FAQPage JSON-LD graph with SSR-hydrated Section 1256 vs "
            "ordinary income sensitivity schedule and direct internal linkage with /tools/prediction-market-odds/."
        ),
        "counter_strategy_executed": (
            "Wired live predictioncalculator.com fee-drag mechanics into the Section 1256 tax sub-ledger so traders "
            "evaluate exchange fees and Form 6781 60/40 tax alpha in a single deterministic model."
        ),
    },
    "soc-2-audit-cost-calculator": {
        "property_id": "gainhelm",
        "slug": "soc-2-audit-cost-calculator",
        "target_queries": [
            "soc 2 audit cost calculator",
            "soc 2 compliance cost calculator",
            "soc 2 type 2 cost estimator",
            "vanta vs drata soc 2 cost calculator",
        ],
        "incumbent_urls": [
            "https://www.vanta.com/resources/soc-2-cost-breakdown",
            "https://drata.com/grc-central/soc-2/soc-2-cost",
            "https://secureframe.com/hub/soc-2/cost",
            "https://sprinto.com/blog/soc-2-certification-cost/",
        ],
        "calculator_interactivity": (
            "Models total SOC 2 Type I and Type II cost of ownership across AICPA CPA firm attestation fees ($18,000 "
            "to $65,000), continuous GRC automation licensing ($10,000 to $28,000), CREST penetration testing, and "
            "internal engineering readiness hours (BLS OEWS 15-1212)."
        ),
        "visual_hierarchy": (
            "Above-the-fold Automated GRC + Segmented Enclave TCO vs Manual Unsegmented Audit TCO cards with instant "
            "engineering hours saved and enterprise GRC quote intake."
        ),
        "content_effort": (
            "Headcount-tiered CPA fee benchmarks, Trust Services Criteria (Security, Availability, Processing Integrity, "
            "Confidentiality, Privacy) scope multipliers, and 3-to-12-month Type II observation window timelines."
        ),
        "trust_signals": (
            "Citations to AICPA SSAE 18, AT-C Section 205, Trust Services Criteria TSP Section 100, BLS OEWS 13-2011 / "
            "15-1212 wage series, and IBM Cost of a Data Breach Report."
        ),
        "seo_structure": (
            "Unified SoftwareApplication + Dataset + HowTo + FAQPage JSON-LD graph, strict GainHelm GRC tenant isolation, "
            "and 3-tier topic cluster linking to CMMC 2.0, ISO 27001, and Penetration Testing calculators."
        ),
        "counter_strategy_executed": (
            "Eliminated ProfitHelm cross-tenant fallback in get_competitive_incumbent_profile and stateful scenario "
            "comparators, and blocked legacy pre-pivot field-service queries from polluting GainHelm spike briefs."
        ),
    },
    "cmmc-2-0-compliance-cost-calculator": {
        "property_id": "gainhelm",
        "slug": "cmmc-2-0-compliance-cost-calculator",
        "target_queries": [
            "cmmc 2.0 compliance cost calculator",
            "cmmc level 2 c3pao audit cost calculator",
            "dfars 252.204-7021 compliance cost estimator",
        ],
        "incumbent_urls": [
            "https://cyberab.org/",
            "https://www.preveil.com/cmmc-cost/",
            "https://www.vanta.com/products/cmmc",
        ],
        "calculator_interactivity": (
            "Computes CMMC 2.0 Level 2 triennial C3PAO assessment fees, CUI enclave segmentation savings, FedRAMP High "
            "/ GCC High licensing delta, and NIST SP 800-171 Rev 2 110-control remediation engineering hours."
        ),
        "visual_hierarchy": (
            "Segmented CUI Enclave TCO vs Full Enterprise Network Scope comparison cards paired with 2026 DFARS "
            "solicitation gate timeline."
        ),
        "content_effort": (
            "Detailed breakdown of 32 CFR Part 170 final rule tiers (Level 1 17 practices, Level 2 110 controls, Level 3 "
            "DIBCAC 24 SP 800-172 controls) and POA&M 180-day closeout eligibility rules."
        ),
        "trust_signals": (
            "Citations to 32 CFR Part 170, 48 CFR DFARS 252.204-7012 / 7019 / 7020 / 7021, NIST SP 800-171 Rev 2, and "
            "DoD CMMC 2.0 Cost Assessment regulatory impact series."
        ),
        "seo_structure": (
            "SoftwareApplication + Dataset + HowTo + FAQPage JSON-LD graph connected directly to the companion "
            "/tools/nist-800-171-sprs-score-calculator/."
        ),
        "counter_strategy_executed": (
            "Added sub-vertical CMMC 2.0 / 32 CFR Part 170 statutory enrichment to CompetitorGapEngine and wired "
            "dedicated GainHelm incumbent profiling."
        ),
    },
    "nist-800-171-sprs-score-calculator": {
        "property_id": "gainhelm",
        "slug": "nist-800-171-sprs-score-calculator",
        "target_queries": [
            "nist 800 171 sprs score calculator",
            "sprs score calculator",
            "dfars 7019 sprs weighted point deduction calculator",
        ],
        "incumbent_urls": [
            "https://www.dodprocurementtoolbox.com/",
            "https://www.preveil.com/nist-800-171-sprs-score/",
        ],
        "calculator_interactivity": (
            "Calculates exact Supplier Performance Risk System (SPRS) score across the -203 to +110 scale using DoD "
            "Assessment Methodology 5-point, 3-point, and 1-point control deduction weights and POA&M conditional eligibility."
        ),
        "visual_hierarchy": (
            "Instant SPRS Score readout (-203 to +110) with CMMC Level 2 Conditional (>=88 score) vs Unconditional (110) "
            "gate status indicator."
        ),
        "content_effort": (
            "Complete 14-family NIST SP 800-171 Rev 2 control weight schedule, non-waivable 5-point CUI encryption/MFA "
            "controls, and False Claims Act (31 U.S.C. 3729) misreporting risk warnings."
        ),
        "trust_signals": (
            "Citations to DFARS 252.204-7019 / 7020, NIST SP 800-171 DoD Assessment Methodology v1.2.1, and 32 CFR 170.21."
        ),
        "seo_structure": (
            "Dataset + HowTo + FAQPage JSON-LD with SSR-hydrated 5-point/3-point/1-point deduction sensitivity matrix."
        ),
        "counter_strategy_executed": (
            "Enforced strict GRC query relevance filtering and connected SPRS scoring directly to CMMC 2.0 C3PAO readiness."
        ),
    },
    "iso-27001-certification-cost-calculator": {
        "property_id": "gainhelm",
        "slug": "iso-27001-certification-cost-calculator",
        "target_queries": [
            "iso 27001 certification cost calculator",
            "iso 27001 audit cost estimator",
            "iso 27001 auditor day calculator",
        ],
        "incumbent_urls": [
            "https://www.vanta.com/collection/iso-27001/iso-27001-cost",
            "https://advisera.com/27001academy/blog/how-much-does-iso-27001-implementation-cost/",
            "https://www.isms.online/iso-27001/cost/",
        ],
        "calculator_interactivity": (
            "Models Stage 1 + Stage 2 accredited Certification Body auditor-days under ISO/IEC 27006-1:2024 and IAF MD 5 "
            "headcount tables alongside Years 2-3 surveillance audits and Annex A (93 controls) automation savings."
        ),
        "visual_hierarchy": (
            "3-Year ISMS Certification + Surveillance TCO breakdown card paired with SOC 2 dual-mapping control overlap savings."
        ),
        "content_effort": (
            "IAF MD 5 headcount-to-auditor-day schedule, ISO/IEC 27001:2022 Annex A 4-theme consolidation (Organizational, "
            "People, Physical, Technological), and Statement of Applicability (SoA) scopereduction rules."
        ),
        "trust_signals": (
            "Citations to ISO/IEC 27001:2022 Clauses 4-10, Annex A (93 controls), ISO/IEC 27006-1:2024, and ANAB/UKAS accreditation."
        ),
        "seo_structure": (
            "Unified SoftwareApplication + Dataset + HowTo + FAQPage JSON-LD graph and cross-framework SOC 2 overlap links."
        ),
        "counter_strategy_executed": (
            "Grounded ISO 27001 cost modeling in ISO/IEC 27006-1:2024 auditor-day formulas and GainHelm GRC benchmarks."
        ),
    },
    "hipaa-violation-penalty-breach-cost-calculator": {
        "property_id": "gainhelm",
        "slug": "hipaa-violation-penalty-breach-cost-calculator",
        "target_queries": [
            "hipaa violation penalty calculator",
            "hipaa breach cost calculator",
            "hhs ocr civil monetary penalty calculator",
        ],
        "incumbent_urls": [
            "https://www.hipaajournal.com/hipaa-violation-fines/",
            "https://sprinto.com/blog/hipaa-violation-fines/",
            "https://www.vanta.com/collection/hipaa/hipaa-violations",
        ],
        "calculator_interactivity": (
            "Combines HHS OCR 45 CFR 160.404 4-tier inflation-adjusted Civil Monetary Penalty schedules with per-record "
            "healthcare breach forensic, notification, credit monitoring, and class-action settlement costs."
        ),
        "visual_hierarchy": (
            "4-Tier OCR Culpability Penalty Matrix paired with >500 ePHI record 60-day media/OCR breach notification triggers."
        ),
        "content_effort": (
            "Reconciliation of 42 U.S.C. 1320d-5 statutory tiers vs 45 CFR 160.404 inflation-adjusted caps ($141 to "
            "$2,134,831 annual cap per identical provision) and HITECH Act recognized security practices mitigation."
        ),
        "trust_signals": (
            "Citations to 45 CFR 160.404, 45 CFR Part 164 Subpart C/D, 42 U.S.C. 1320d-5, Public Law 116-321 (HITECH "
            "Recognized Security Practices), and IBM Healthcare Breach Cost benchmark series."
        ),
        "seo_structure": (
            "Dataset + HowTo + FAQPage JSON-LD graph with SSR-hydrated 4-tier OCR penalty schedule and cyber insurance linkage."
        ),
        "counter_strategy_executed": (
            "Paired HHS OCR 4-tier statutory fine arithmetic with HITECH Public Law 116-321 12-month recognized security "
            "practices penalty mitigation."
        ),
    },
}


REJECTED_COSMETIC_CHANGES: List[Dict[str, str]] = [
    {
        "proposal": "Decorative hero illustrations, animated gradient backgrounds, and custom webfont swaps",
        "rejection_reason": (
            "Zero impact on Search Intent Match (+2.60), Query-Answer Match (+2.15), or partner EPC conversion; "
            "adds CLS/LCP latency and dilutes above-the-fold calculator immediacy."
        ),
    },
    {
        "proposal": "Cosmetic button color/border-radius restyling and card drop-shadow tweaks across calculators",
        "rejection_reason": (
            "Does not resolve SERP CTR shortfalls, schema eligibility, crawl budget bloat, or borrower/taxpayer "
            "math anxiety."
        ),
    },
    {
        "proposal": "Expanding long-form generic overview prose above the interactive calculator",
        "rejection_reason": (
            "Pushes interactive inputs and the 40-60 word statutory quick-answer below the fold, hurting "
            "Main Answer Near Beginning of Page (+1.59) and Satisfaction/Task Completion (+2.14)."
        ),
    },
]


BESPOKE_VS_SYSTEMIC_UPGRADE_EVALUATION: List[Dict[str, Any]] = [
    {
        "upgrade_id": "sys_nofollow_preset_crawl_budget_guard",
        "scope": "SYSTEMIC_TEMPLATE_ENHANCEMENT",
        "target_assets": "All ProfitHelm, Prexvo, and GainHelm calculator pages (.scenario-preset-link anchors)",
        "engineering_cost": "LOW",
        "ranking_impact_score": 9.4,
        "conversion_impact_score": 8.2,
        "composite_roi_score": 9.1,
        "decision": "EXECUTE_IMMEDIATELY",
        "rationale": (
            "Live GSC URL inspection revealed Googlebot wasting crawl budget on 462+ parameterized preset URLs "
            "(?sale_price=2500000&replacement_state=TX, ?gross_amount=80000&effective_rate=0.19). Adding "
            "rel='nofollow' to .scenario-preset-link anchors in compiler.py and maintenance.py preserves 100% "
            "interactive JS/deep-link preset functionality while consolidating Googlebot crawl equity onto canonical URLs."
        ),
    },
    {
        "upgrade_id": "sys_gsc_oracle_revenue_prioritization",
        "scope": "SYSTEMIC_TEMPLATE_ENHANCEMENT",
        "target_assets": "PushIndexer.run_incremental_indexing, prioritize_urls_for_indexing_allocation, and compile_gsc_lifecycle_telemetry",
        "engineering_cost": "LOW",
        "ranking_impact_score": 9.2,
        "conversion_impact_score": 8.5,
        "composite_roi_score": 9.0,
        "decision": "EXECUTE_IMMEDIATELY",
        "rationale": (
            "Fixes the alphabetical safe_all_urls[:5] blind spot in indexer.py that inspected static trust pages "
            "(/about/, /contact/, /privacy/) instead of top revenue calculators, and wires quantitative_revenue_forecast.json "
            "directly into Tier-1 indexing/inspection quota allocation."
        ),
    },
    {
        "upgrade_id": "sys_snippet_and_schema_completeness",
        "scope": "SYSTEMIC_TEMPLATE_ENHANCEMENT",
        "target_assets": "12 ProfitHelm calculators missing Dataset/HowTo JSON-LD + all truncated/robotic Titles & Meta Descriptions",
        "engineering_cost": "MEDIUM",
        "ranking_impact_score": 9.6,
        "conversion_impact_score": 8.9,
        "composite_roi_score": 9.4,
        "decision": "EXECUTE_IMMEDIATELY",
        "rationale": (
            "Live GSC inspection showed /tools/s-corp-reasonable-salary-tax-calculator/ lacked Dataset rich results "
            "because 12 ProfitHelm calculators were missing Dataset + HowTo JSON-LD nodes. Simultaneously healing "
            "'state clawb.' truncation, 'Model Tool Guide' title filler, 'Calculate X Calculator' redundancy, and "
            "plan-specific Prexvo meta descriptions directly lifts SERP CTR and resolves ICR/IBR query cannibalization."
        ),
    },
    {
        "upgrade_id": "sys_live_serp_dom_structural_diff_and_rma_velocity_engine",
        "scope": "SYSTEMIC_TEMPLATE_ENHANCEMENT",
        "target_assets": "CompetitorGapEngine, DailyIndexingInspector, and closed-loop overlay/HTML remediation across all 3 tenants",
        "engineering_cost": "MEDIUM",
        "ranking_impact_score": 9.8,
        "conversion_impact_score": 9.3,
        "composite_roi_score": 9.6,
        "decision": "EXECUTE_IMMEDIATELY",
        "rationale": (
            "Replaces passive competitor reports with programmatic HTML/JS DOM structural diffing (schema depth, SSR vs "
            "CSR calculator mechanics, statutory citation density, and entity coverage), RMA-7/RMA-28 decay velocity "
            "scoring, and automated overlay + HTML template mutation across ProfitHelm, Prexvo, and GainHelm."
        ),
    },
    {
        "upgrade_id": "bespoke_prexvo_refinance_and_idr_workbench",
        "scope": "BESPOKE_TOOL_MECHANIC",
        "target_assets": "/tools/student-loan-refinance-break-even-calculator/, /tools/icr-repayment-calculator/, /tools/ibr-hardship-cap-calculator/",
        "engineering_cost": "LOW",
        "ranking_impact_score": 9.3,
        "conversion_impact_score": 9.5,
        "composite_roi_score": 9.4,
        "decision": "EXECUTE_IMMEDIATELY",
        "rationale": (
            "Disambiguates Prexvo's highest-EPC refinance calculator ($64+ effective EPC) and cannibalized ICR/IBR "
            "calculators with bespoke SERP workbench headings, TILA Reg-Z APR spread vs Title IV forfeiture framing, "
            "and 9 new contextual inbound links from commercial IDR hubs."
        ),
    },
    {
        "upgrade_id": "bespoke_profithelm_prediction_market_fee_and_1256_workbench",
        "scope": "BESPOKE_TOOL_MECHANIC",
        "target_assets": "/tools/prediction-market-odds/, /tools/prediction-market-tax/",
        "engineering_cost": "LOW",
        "ranking_impact_score": 9.7,
        "conversion_impact_score": 9.4,
        "composite_roi_score": 9.6,
        "decision": "EXECUTE_IMMEDIATELY",
        "rationale": (
            "Directly counters predictioncalculator.com's CSR-only calculators by absorbing Kalshi quadratic Taker "
            "(0.07*P*(1-P)) / Maker (0.0175*P*(1-P)) and Polymarket (4%) fee presets + break-even win rate shifts into "
            "an SSR-hydrated workbench paired with IRC Section 1256 (60/40) Form 6781 tax drag analysis."
        ),
    },
    {
        "upgrade_id": "bespoke_gainhelm_grc_audit_scoping_workbench",
        "scope": "BESPOKE_TOOL_MECHANIC",
        "target_assets": "/tools/soc-2-audit-cost-calculator/, /tools/cmmc-2-0-compliance-cost-calculator/, /tools/nist-800-171-sprs-score-calculator/",
        "engineering_cost": "LOW",
        "ranking_impact_score": 9.5,
        "conversion_impact_score": 9.4,
        "composite_roi_score": 9.5,
        "decision": "EXECUTE_IMMEDIATELY",
        "rationale": (
            "Isolates GainHelm's GRC audit scoping and SPRS deduction workbenches with AICPA SSAE 18, 32 CFR Part 170, "
            "ISO/IEC 27006-1:2024, and 45 CFR 160.404 benchmarks while purging legacy pre-pivot field-service queries."
        ),
    },
]


def get_competitive_incumbent_profile(
    slug_or_query: str,
    property_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Returns the durable competitive incumbent profile for a calculator slug or target money query.
    Strictly parameterized by property_id when provided (or inferred from slug/query) so tenant
    boundaries never bleed across ProfitHelm, Prexvo, and GainHelm.
    Zero em-dashes. Zero en-dashes.
    """
    key = str(slug_or_query or "").strip().lower().strip("/")
    if key.startswith("tools/"):
        key = key[len("tools/") :]
    prop_norm = str(property_id or "").strip().lower()

    if not prop_norm:
        if any(
            tok in key
            for tok in (
                "soc-2",
                "soc 2",
                "cmmc",
                "sprs",
                "800-171",
                "iso-27001",
                "iso 27001",
                "hipaa",
                "pci-dss",
                "fedramp",
                "hitrust",
                "pentest",
                "penetration-testing",
                "cyber-insurance",
                "vanta",
                "drata",
            )
        ):
            prop_norm = "gainhelm"
        elif any(
            tok in key
            for tok in (
                "rap-",
                "rap ",
                "ibr",
                "icr",
                "pslf",
                "student-loan",
                "student loan",
                "save-plan",
                "parent-plus",
                "obbba",
            )
        ):
            prop_norm = "prexvo"

    if key in COMPETITIVE_INCUMBENT_PROFILES:
        prof = COMPETITIVE_INCUMBENT_PROFILES[key]
        if not prop_norm or prof.get("property_id") == prop_norm:
            return dict(prof)

    base_slug = key.split("/")[0]
    if base_slug in COMPETITIVE_INCUMBENT_PROFILES:
        prof = COMPETITIVE_INCUMBENT_PROFILES[base_slug]
        if not prop_norm or prof.get("property_id") == prop_norm:
            return dict(prof)

    for prof in COMPETITIVE_INCUMBENT_PROFILES.values():
        if prop_norm and prof.get("property_id") != prop_norm:
            continue
        if any(key in q.lower() or q.lower() in key for q in prof.get("target_queries", [])):
            return dict(prof)

    if prop_norm == "gainhelm":
        return dict(COMPETITIVE_INCUMBENT_PROFILES["soc-2-audit-cost-calculator"])
    if prop_norm == "prexvo":
        return dict(COMPETITIVE_INCUMBENT_PROFILES["rap-payment-calculator"])
    return dict(COMPETITIVE_INCUMBENT_PROFILES["section-1031-calculator"])


def evaluate_bespoke_vs_systemic_upgrades(property_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns the structured evaluation of bespoke interactive tool mechanics vs systemic
    template enhancements across ProfitHelm, Prexvo, and GainHelm, including durable incumbent
    profiles and rejected cosmetic changes.
    Zero em-dashes. Zero en-dashes.
    """
    prop_norm = str(property_id or "").strip().lower()
    profiles = [
        dict(v)
        for v in COMPETITIVE_INCUMBENT_PROFILES.values()
        if not prop_norm or v.get("property_id") == prop_norm
    ]
    return {
        "property_id": prop_norm or "all",
        "incumbent_profiles_count": len(profiles),
        "incumbent_profiles": profiles,
        "upgrade_tradeoff_matrix": [dict(u) for u in BESPOKE_VS_SYSTEMIC_UPGRADE_EVALUATION],
        "rejected_cosmetic_changes": [dict(c) for c in REJECTED_COSMETIC_CHANGES],
    }


_STATUTORY_CITATION_REGEXES: List[Tuple[str, str]] = [
    ("irc_section", r"\b(?:IRC\s+Section|26\s+U\.S\.C\.(?:\s+Section)?)\s+\d+[A-Za-z0-9()-]*"),
    ("irs_form", r"\b(?:IRS\s+)?Form\s+(?:1099-[A-Z]+|8949|8824|4562|6781|6765|8974|1120-S|3840|540|982)\b"),
    ("cfr_title_34", r"\b34\s+CFR(?:\s+Part)?\s+\d+(?:\.\d+)?"),
    ("cfr_title_17", r"\b17\s+CFR(?:\s+Part)?\s+\d+(?:\.\d+)?"),
    ("cfr_title_32", r"\b32\s+CFR(?:\s+Part)?\s+\d+(?:\.\d+)?"),
    ("cfr_title_45", r"\b45\s+CFR(?:\s+Part)?\s+\d+(?:\.\d+)?"),
    ("dfars_clause", r"\bDFARS\s+252\.204-\d{4}\b"),
    ("aicpa_standard", r"\b(?:AICPA\s+SSAE\s+18|AT-C\s+Section\s+205|TSP\s+Section\s+100)\b"),
    ("iso_standard", r"\bISO/IEC\s+2700[16](?:-1)?(?::202[24])?\b"),
    ("nist_standard", r"\bNIST\s+SP\s+800-(?:171|53|172)\b"),
    ("rev_proc_rul", r"\bRev\.\s*(?:Proc\.|Rul\.)\s*\d{4}-\d+\b"),
    ("public_law", r"\bPublic\s+Law\s+\d{3}-\d+\b"),
    ("tila_reg_z", r"\b(?:TILA\s+)?Regulation\s+Z|\b12\s+CFR\s+Part\s+1026\b"),
]

_EMPIRICAL_DATASET_REGEXES: List[Tuple[str, str]] = [
    ("fred_series", r"\bFRED\b|\bCPILFESL\b|\bDGS10\b|\bSLSTTOTAL\b"),
    ("bls_oews", r"\bBLS\s+OEWS\b"),
    ("irs_soi", r"\bIRS\s+SOI\b"),
    ("cftc_dcm", r"\bCFTC\b"),
    ("hhs_fpl", r"\bHHS\s+(?:Federal\s+)?Poverty\s+Guidelines\b"),
    ("ibm_breach", r"\bIBM\s+Cost\s+of\s+a\s+Data\s+Breach\b"),
    ("iaf_md5", r"\bIAF\s+MD\s*5\b"),
]


def parse_serp_dom_structural_profile(
    raw_html: str,
    raw_js: str = "",
    tenant_id: str = "profithelm",
    js_source: str = "",
    property_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Programmatically parses a live competitor or tenant DOM snapshot (+ optional JS bundle)
    across four structural dimensions:
      1. schema_depth: JSON-LD script count, @graph unification, rich-result @type coverage,
         and double-escaped entity defects (e.g. '&amp;rsquo;').
      2. calculator_mechanics: Interactive input controls, output elements, SSR-hydrated vs
         CSR-blank initial output spans, fee/scenario presets, cross-tool state carry,
         5-point sensitivity tables, multi-year cliffs, and stateful scenario comparators.
      3. citation_density: Primary statutory citations (IRC, CFR, DFARS, AICPA, ISO, IRS Forms)
         and empirical macroeconomic dataset citations (FRED, BLS OEWS, IRS SOI, CFTC, HHS).
      4. entity_coverage: TenantFactStore statutory & domain entity alignment and zero foreign
         cross-tenant contamination.
    Zero em-dashes. Zero en-dashes.
    """
    html_text = str(raw_html or "")
    js_text = str(raw_js or js_source or "")
    combined_source = f"{html_text}\n{js_text}"
    prop_norm = str(property_id or tenant_id or "profithelm").strip().lower()

    # 1. Schema Depth Analysis
    ld_blocks = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    schema_types: Set[str] = set()
    has_unified_graph = False
    has_double_escaped_entities = False
    for raw_block in ld_blocks:
        if re.search(r"&amp;(?:rsquo|lsquo|ldquo|rdquo|quot|amp|#\d+);", raw_block, re.IGNORECASE):
            has_double_escaped_entities = True
        try:
            parsed = json.loads(raw_block.strip())
            stack: List[Any] = [parsed]
            while stack:
                curr = stack.pop()
                if isinstance(curr, dict):
                    if "@graph" in curr and isinstance(curr["@graph"], list):
                        has_unified_graph = True
                        stack.extend(curr["@graph"])
                    t_val = curr.get("@type")
                    if isinstance(t_val, str) and t_val.strip():
                        schema_types.add(t_val.strip())
                    elif isinstance(t_val, list):
                        for item_t in t_val:
                            if isinstance(item_t, str) and item_t.strip():
                                schema_types.add(item_t.strip())
                    for v in curr.values():
                        if isinstance(v, (dict, list)):
                            stack.append(v)
                elif isinstance(curr, list):
                    stack.extend(curr)
        except Exception:
            pass

    target_schema_types = {"SoftwareApplication", "Dataset", "HowTo", "FAQPage", "BreadcrumbList", "Organization"}
    covered_target_schemas = sorted(t for t in target_schema_types if t in schema_types or (t == "SoftwareApplication" and "WebApplication" in schema_types))
    missing_schema_types = sorted(t for t in target_schema_types if t not in schema_types)
    schema_score = min(
        10.0,
        round(
            (len(covered_target_schemas) / max(1, len(target_schema_types))) * 7.5
            + (1.5 if has_unified_graph else 0.0)
            + (1.0 if ld_blocks and not has_double_escaped_entities else 0.0),
            2,
        ),
    )

    # 2. Interactive Calculator Mechanics Analysis
    input_controls: List[str] = []
    for m in re.finditer(r"<(input|select)\b([^>]*)>", html_text, flags=re.IGNORECASE):
        attrs = m.group(2)
        if re.search(r'\btype\s*=\s*["\'](?:hidden|submit|button|checkbox)["\']', attrs, re.IGNORECASE):
            continue
        for attr_key in ("data-in", "id", "name", "data-field"):
            am = re.search(rf'\b{re.escape(attr_key)}\s*=\s*["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            if am and am.group(1).strip():
                ctrl_id = am.group(1).strip()
                if ctrl_id not in input_controls:
                    input_controls.append(ctrl_id)
                break

    ssr_hydrated_outputs: List[str] = []
    csr_blank_outputs: List[str] = []
    # Check elements with data-out="...", <output ...>, or calc-metric-value / calc-result-value / out-value classes
    for out_m in re.finditer(
        r'<(?:span|div|td|output|strong)\b([^>]*\b(?:data-out|class)\s*=\s*["\'][^"\']*["\'][^>]*)>(.*?)</(?:span|div|td|output|strong)>',
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        attrs = out_m.group(1)
        inner_raw = out_m.group(2)
        is_out_node = bool(
            re.search(r'\bdata-out\s*=\s*["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            or re.search(
                r'\bclass\s*=\s*["\'][^"\']*\b(?:out-value|calc-metric-value|calc-result-value|serp-metric-val)\b',
                attrs,
                re.IGNORECASE,
            )
        )
        if not is_out_node:
            continue
        label_m = (
            re.search(r'\bdata-out\s*=\s*["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            or re.search(r'\bid\s*=\s*["\']([^"\']+)["\']', attrs, re.IGNORECASE)
        )
        out_id = label_m.group(1).strip() if label_m else f"out_{len(ssr_hydrated_outputs) + len(csr_blank_outputs) + 1}"
        inner_clean = re.sub(r"<[^>]+>", "", inner_raw).strip()
        if inner_clean and inner_clean not in ("-", "--", "N/A", "n/a", "\u2014", "\u2013"):
            ssr_hydrated_outputs.append(out_id)
        else:
            csr_blank_outputs.append(out_id)

    preset_mechanics: List[str] = []
    for pm in re.finditer(
        r'\bdata-(?:calc-)?preset\s*=\s*["\']([^"\']+)["\']',
        html_text,
        flags=re.IGNORECASE,
    ):
        val = pm.group(1).strip()
        if val and val not in preset_mechanics:
            preset_mechanics.append(val[:60])

    js_fee_schedules: List[str] = []
    if re.search(r"0\.07\s*\*\s*[a-zA-Z_]+\s*\*\s*\(\s*1\s*-\s*[a-zA-Z_]+\s*\)", combined_source) or (
        "0.07" in combined_source and "kalshi" in combined_source.lower()
    ):
        js_fee_schedules.append("kalshi_taker_007_quadratic_fee")
        js_fee_schedules.append("kalshi_7pct_p_1_minus_p_parabolic_fee_preset")
    if "0.0175" in combined_source and "kalshi" in combined_source.lower():
        js_fee_schedules.append("kalshi_maker_00175_fee")
    if ("0.04" in combined_source or "4%" in combined_source) and "polymarket" in combined_source.lower():
        js_fee_schedules.append("polymarket_004_winner_fee")
    if re.search(r"\bdata-carry\s*=", html_text, re.IGNORECASE) or "data-blueprint-action" in html_text:
        js_fee_schedules.append("cross_tool_state_carry_blueprint")
    if re.search(r"breakEven|break-even|beShift", combined_source, re.IGNORECASE):
        js_fee_schedules.append("break_even_win_rate_delta")
    if re.search(r"noVig|no-vig|de-vig|overround", combined_source, re.IGNORECASE):
        js_fee_schedules.append("two_way_multiplicative_devigging")

    has_sensitivity_matrix = bool(
        re.search(
            r'class=["\'][^"\']*(?:sensitivity-table|serp-statutory-reference-table|comparison-table)[^"\']*["\']',
            html_text,
            re.IGNORECASE,
        )
    )
    has_multi_year_cliff = "multi-year-cliff-visualizer" in html_text
    has_stateful_comparator = "stateful-scenario-comparator" in html_text
    has_statutory_tax_drag = bool(
        re.search(r"\b(?:Section\s+1256|Form\s+6781|60/40|60%\s+Long-Term|Section\s+179|34\s+CFR|AICPA\s+SSAE\s+18)\b", html_text, re.IGNORECASE)
    )
    has_ssr_hydration = len(ssr_hydrated_outputs) > 0 and len(csr_blank_outputs) == 0
    csr_only_hydration = len(csr_blank_outputs) > 0 and len(ssr_hydrated_outputs) == 0
    has_kalshi_fee_schedule = "kalshi_taker_007_quadratic_fee" in js_fee_schedules

    mechanics_score = min(
        10.0,
        round(
            (2.0 if len(input_controls) >= 2 else 0.5)
            + (2.5 if has_ssr_hydration else 0.0)
            + (1.5 if preset_mechanics or js_fee_schedules else 0.0)
            + (1.5 if has_sensitivity_matrix else 0.0)
            + (1.25 if has_multi_year_cliff and has_stateful_comparator else 0.0)
            + (1.25 if has_statutory_tax_drag else 0.0),
            2,
        ),
    )

    # 3. Statutory & Empirical Citation Density Analysis
    visible_text = re.sub(r"<script\b[^>]*>.*?</script>", " ", html_text, flags=re.IGNORECASE | re.DOTALL)
    visible_text = re.sub(r"<style\b[^>]*>.*?</style>", " ", visible_text, flags=re.IGNORECASE | re.DOTALL)
    visible_text = re.sub(r"<[^>]+>", " ", visible_text)

    statutory_citations: List[str] = []
    for _, pat in _STATUTORY_CITATION_REGEXES:
        for cm in re.finditer(pat, visible_text, flags=re.IGNORECASE):
            token = re.sub(r"\s+", " ", cm.group(0).strip())
            if token not in statutory_citations:
                statutory_citations.append(token)

    empirical_datasets: List[str] = []
    for ds_name, pat in _EMPIRICAL_DATASET_REGEXES:
        if re.search(pat, visible_text, flags=re.IGNORECASE):
            empirical_datasets.append(ds_name)

    citation_score = min(
        10.0,
        round(min(6.5, len(statutory_citations) * 1.65) + min(3.5, len(empirical_datasets) * 1.75), 2),
    )

    # 4. Entity Coverage & Tenant Isolation Analysis
    store = TenantFactStore.get_instance()
    t_profile = store.get_profile(prop_norm)
    scanner = CrossPropertyContaminationScanner()
    foreign_contaminations = scanner.scan_text(visible_text.lower(), prop_norm)

    matched_entities: List[str] = []
    missing_entities: List[str] = []
    if t_profile and t_profile.statutory_truth and t_profile.statutory_truth.statutory_citations:
        for cit_key, cit_val in t_profile.statutory_truth.statutory_citations.items():
            cit_str = str(cit_val).strip()
            if not cit_str:
                continue
            if cit_str.lower() in visible_text.lower() or cit_key.replace("_", " ").lower() in visible_text.lower():
                matched_entities.append(cit_key)
            else:
                missing_entities.append(cit_key)

    entity_score = max(
        0.0,
        min(
            10.0,
            round(
                (5.0 if statutory_citations else 1.5)
                + min(5.0, len(matched_entities) * 1.25)
                - (5.0 * len(foreign_contaminations)),
                2,
            ),
        ),
    )

    composite_dom_score = round(
        (schema_score * 0.25) + (mechanics_score * 0.35) + (citation_score * 0.25) + (entity_score * 0.15),
        2,
    )

    return {
        "tenant_id": prop_norm,
        "composite_dom_score": composite_dom_score,
        "schema_depth": {
            "jsonld_script_count": len(ld_blocks),
            "has_unified_graph": has_unified_graph,
            "schema_types": sorted(schema_types),
            "covered_target_schemas": covered_target_schemas,
            "missing_schema_types": missing_schema_types,
            "has_double_escaped_entities": has_double_escaped_entities,
            "score": schema_score,
            "schema_depth_score": round(schema_score * 10.0, 2),
        },
        "calculator_mechanics": {
            "input_controls": input_controls,
            "ssr_hydrated_outputs_count": len(ssr_hydrated_outputs),
            "csr_blank_outputs_count": len(csr_blank_outputs),
            "csr_blank_output_ids": csr_blank_outputs,
            "has_ssr_hydration": has_ssr_hydration,
            "csr_only_hydration": csr_only_hydration,
            "has_kalshi_fee_schedule": has_kalshi_fee_schedule,
            "preset_mechanics": preset_mechanics,
            "detected_fee_and_carry_mechanics": js_fee_schedules,
            "has_sensitivity_matrix": has_sensitivity_matrix,
            "has_multi_year_cliff": has_multi_year_cliff,
            "has_stateful_comparator": has_stateful_comparator,
            "has_statutory_tax_drag": has_statutory_tax_drag,
            "score": mechanics_score,
        },
        "citation_density": {
            "statutory_citations": statutory_citations,
            "statutory_citation_count": len(statutory_citations),
            "empirical_datasets": empirical_datasets,
            "dataset_citation_count": len(empirical_datasets),
            "score": citation_score,
        },
        "entity_coverage": {
            "matched_tenant_entities": matched_entities,
            "missing_tenant_entities": missing_entities[:10],
            "foreign_tenant_contaminations": foreign_contaminations,
            "tenant_isolated": len(foreign_contaminations) == 0,
            "score": entity_score,
        },
    }


def diff_competitor_dom_structure(
    competitor_html: str,
    tenant_html: str = "",
    competitor_js: str = "",
    tenant_id: str = "profithelm",
    target_slug: str = "",
    query: str = "",
    property_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Programmatically diffs a competitor SERP DOM snapshot (+ optional JS bundle) against a
    compiled tenant page across schema depth, SSR vs CSR calculator mechanics, citation density,
    and entity coverage. Emits a deterministic template_mutation_spec that mutates target tenant
    overlays and compiled HTML builds.
    Zero em-dashes. Zero en-dashes.
    """
    prop_norm = str(property_id or tenant_id or "profithelm").strip().lower()
    comp_prof = parse_serp_dom_structural_profile(competitor_html, competitor_js, tenant_id=prop_norm)
    tenant_prof = (
        parse_serp_dom_structural_profile(tenant_html, "", tenant_id=prop_norm)
        if str(tenant_html or "").strip()
        else None
    )

    slug_clean = str(target_slug or "").strip().strip("/").lower()
    if slug_clean.startswith("tools/"):
        slug_clean = slug_clean[len("tools/") :]
    q_clean = str(query or slug_clean.replace("-", " ")).strip()

    # 1. Identify competitor interactive wedges to absorb
    competitor_wedges_to_absorb: List[str] = []
    for mech in comp_prof["calculator_mechanics"]["detected_fee_and_carry_mechanics"]:
        if mech not in competitor_wedges_to_absorb:
            competitor_wedges_to_absorb.append(mech)
    for preset in comp_prof["calculator_mechanics"]["preset_mechanics"]:
        norm_p = _normalize_feature_name(f"preset_{preset}")
        if norm_p and norm_p not in competitor_wedges_to_absorb:
            competitor_wedges_to_absorb.append(norm_p)
    for ctrl in comp_prof["calculator_mechanics"]["input_controls"]:
        norm_c = _normalize_feature_name(ctrl)
        if norm_c and norm_c not in competitor_wedges_to_absorb:
            competitor_wedges_to_absorb.append(norm_c)

    # 2. Identify structural vulnerabilities in the competitor DOM that our template exploits
    competitor_structural_vulnerabilities: List[str] = []
    if comp_prof["calculator_mechanics"]["csr_blank_outputs_count"] > 0:
        competitor_structural_vulnerabilities.append("csr_only_blank_initial_outputs")
    if not comp_prof["schema_depth"]["has_unified_graph"]:
        competitor_structural_vulnerabilities.append("fragmented_jsonld_missing_unified_graph")
    if comp_prof["schema_depth"]["missing_schema_types"]:
        competitor_structural_vulnerabilities.append(
            "missing_rich_result_schemas:" + ",".join(comp_prof["schema_depth"]["missing_schema_types"])
        )
    if comp_prof["schema_depth"]["has_double_escaped_entities"]:
        competitor_structural_vulnerabilities.append("double_escaped_jsonld_entities")
    if comp_prof["citation_density"]["statutory_citation_count"] == 0:
        competitor_structural_vulnerabilities.append("zero_primary_statutory_citations")
    if comp_prof["citation_density"]["dataset_citation_count"] == 0:
        competitor_structural_vulnerabilities.append("zero_empirical_dataset_citations")
    if not comp_prof["calculator_mechanics"]["has_statutory_tax_drag"]:
        competitor_structural_vulnerabilities.append("missing_statutory_tax_drag_comparison")
    if not comp_prof["calculator_mechanics"]["has_sensitivity_matrix"]:
        competitor_structural_vulnerabilities.append("missing_5_point_ssr_sensitivity_table")

    # 3. Identify any gaps on the compiled tenant page relative to the absorbed competitor wedges
    tenant_structural_gaps: List[str] = []
    if tenant_prof is None:
        tenant_structural_gaps.append("uncompiled_or_missing_tenant_dom")
    else:
        if tenant_prof["schema_depth"]["missing_schema_types"]:
            tenant_structural_gaps.append(
                "missing_schema_types:" + ",".join(tenant_prof["schema_depth"]["missing_schema_types"])
            )
        if not tenant_prof["calculator_mechanics"]["has_ssr_hydration"]:
            tenant_structural_gaps.append("incomplete_ssr_output_hydration")
        tenant_mechs = set(tenant_prof["calculator_mechanics"]["detected_fee_and_carry_mechanics"])
        for c_mech in comp_prof["calculator_mechanics"]["detected_fee_and_carry_mechanics"]:
            if c_mech not in tenant_mechs:
                tenant_structural_gaps.append(f"missing_competitor_wedge:{c_mech}")
        if (
            any(tok in f"{slug_clean} {q_clean.lower()}" for tok in ("prediction", "kalshi", "polymarket", "implied-probability", "ev"))
            and 'data-workbench-mode="prediction_market_ev"' not in str(tenant_html or "")
        ):
            tenant_structural_gaps.append("missing_bespoke_prediction_market_ev_workbench")

    # Resolve target statutory authority & dataset via CompetitorGapEngine
    engine = CompetitorGapEngine(tenant_id=prop_norm)
    enriched_meta = engine.enrich_candidate_spec(
        {
            "slug": slug_clean or sanitize_url_slug(q_clean or "calculator"),
            "query": q_clean or slug_clean.replace("-", " "),
            "title": (slug_clean or q_clean or "Calculator").replace("-", " ").title(),
        }
    )
    stat_auth = str(enriched_meta.get("statutory_authority", "IRC Section 179(b)(1)"))
    econ_ds = str(enriched_meta.get("economic_dataset", "FRED CPILFESL Series"))
    canonical_base = str(enriched_meta.get("canonical_base", f"https://{prop_norm}.com"))
    eff_slug = slug_clean or str(enriched_meta.get("slug", "calculator"))
    eff_title = (eff_slug.replace("-", " ").title() if eff_slug else "Calculator")

    serp_workbench_html = render_serp_incumbent_depth_upgrade_block(
        slug=eff_slug,
        title=eff_title,
        property_id=prop_norm,
        canonical_base=canonical_base,
        statutory_authority=stat_auth,
        economic_dataset=econ_ds,
    )
    wb_mode_m = re.search(r'data-workbench-mode=["\']([^"\']+)["\']', serp_workbench_html)
    workbench_mode = wb_mode_m.group(1) if wb_mode_m else "tax_deduction"

    mutation_required = bool(tenant_structural_gaps or competitor_wedges_to_absorb)
    template_mutation_spec = {
        "property_id": prop_norm,
        "target_slug": eff_slug,
        "query": q_clean,
        "mutation_required": mutation_required,
        "workbench_mode": workbench_mode,
        "statutory_authority": stat_auth,
        "economic_dataset": econ_ds,
        "absorbed_mechanics": competitor_wedges_to_absorb,
        "inject_presets": list(competitor_wedges_to_absorb),
        "exploited_competitor_vulnerabilities": competitor_structural_vulnerabilities,
        "tenant_gaps_closed": tenant_structural_gaps,
        "schema_upgrades_required": ["SoftwareApplication", "Dataset", "HowTo", "FAQPage", "BreadcrumbList", "Organization"],
        "serp_depth_upgrade_html": serp_workbench_html,
    }

    return {
        "property_id": prop_norm,
        "target_slug": eff_slug,
        "query": q_clean,
        "requires_template_mutation": mutation_required,
        "competitor_profile": comp_prof,
        "tenant_profile": tenant_prof,
        "competitor_wedges_to_absorb": competitor_wedges_to_absorb,
        "competitor_structural_vulnerabilities": competitor_structural_vulnerabilities,
        "tenant_structural_gaps": tenant_structural_gaps,
        "template_mutation_spec": template_mutation_spec,
    }


def diff_live_competitor_scratch_snapshots(
    scratch_dir: Optional[Union[str, Path]] = None,
    tenant_repo_root: Optional[Union[str, Path]] = None,
    tenant_id: str = "profithelm",
) -> Dict[str, Any]:
    """
    Discovers and programmatically diffs live competitor DOM snapshots in .agy/scratch
    (e.g. calc_implied_prob.html, calc_ev.html, calc_kalshi_fees.html, competitor_calculators.js)
    against compiled tenant HTML pages in dist/tools/<slug>/index.html, returning deterministic
    template_mutation_specs ready for closed-loop overlay and build mutation.
    Zero em-dashes. Zero en-dashes.
    """
    prop_norm = str(tenant_id or "profithelm").strip().lower()
    default_scratch = Path(__file__).resolve().parent.parent / ".agy" / "scratch"
    if not default_scratch.exists():
        main_scratch = Path("/home/ubuntuadmin/projects/pseofactory/.agy/scratch")
        if main_scratch.exists():
            default_scratch = main_scratch
    s_dir = Path(scratch_dir) if scratch_dir else default_scratch
    if not s_dir.exists():
        return {
            "property_id": prop_norm,
            "scratch_dir": str(s_dir),
            "snapshots_evaluated": 0,
            "snapshots_analyzed": 0,
            "diffs": [],
            "template_mutation_specs": [],
            "mutations_required": [],
        }

    js_bundle = ""
    js_path = s_dir / "competitor_calculators.js"
    if js_path.exists():
        try:
            js_bundle = js_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            js_bundle = ""

    snapshot_mappings: List[Tuple[str, str, str]] = [
        ("calc_implied_prob.html", "prediction-market-odds", "prediction market implied probability calculator"),
        ("calc_ev.html", "prediction-market-odds", "prediction market expected value calculator"),
        ("calc_kalshi_fees.html", "prediction-market-tax", "kalshi fee and prediction market tax calculator"),
    ]

    if tenant_repo_root is None:
        workspace_root = Path(__file__).resolve().parent.parent.parent
        repo_map = {
            "profithelm": workspace_root / "profithelm-platform",
            "prexvo": workspace_root / "prexvo",
            "gainhelm": workspace_root / "gainhelm",
        }
        t_root = repo_map.get(prop_norm)
    else:
        t_root = Path(tenant_repo_root)

    diffs: List[Dict[str, Any]] = []
    mutation_specs_by_slug: Dict[str, Dict[str, Any]] = {}

    for filename, target_slug, target_query in snapshot_mappings:
        snap_path = s_dir / filename
        if not snap_path.exists():
            continue
        try:
            comp_html = snap_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        tenant_html = ""
        if t_root and (t_root / "dist" / "tools" / target_slug / "index.html").exists():
            try:
                tenant_html = (t_root / "dist" / "tools" / target_slug / "index.html").read_text(
                    encoding="utf-8", errors="replace"
                )
            except Exception:
                tenant_html = ""

        diff_res = diff_competitor_dom_structure(
            competitor_html=comp_html,
            tenant_html=tenant_html,
            competitor_js=js_bundle,
            tenant_id=prop_norm,
            target_slug=target_slug,
            query=target_query,
        )
        diff_res["snapshot_file"] = filename
        diffs.append(diff_res)

        mut_spec = diff_res["template_mutation_spec"]
        if target_slug not in mutation_specs_by_slug:
            mutation_specs_by_slug[target_slug] = dict(mut_spec)
        else:
            existing_mut = mutation_specs_by_slug[target_slug]
            for mech in mut_spec.get("absorbed_mechanics", []):
                if mech not in existing_mut["absorbed_mechanics"]:
                    existing_mut["absorbed_mechanics"].append(mech)
            for vuln in mut_spec.get("exploited_competitor_vulnerabilities", []):
                if vuln not in existing_mut["exploited_competitor_vulnerabilities"]:
                    existing_mut["exploited_competitor_vulnerabilities"].append(vuln)
            for gap in mut_spec.get("tenant_gaps_closed", []):
                if gap not in existing_mut["tenant_gaps_closed"]:
                    existing_mut["tenant_gaps_closed"].append(gap)
            existing_mut["mutation_required"] = bool(
                existing_mut.get("mutation_required") or mut_spec.get("mutation_required")
            )

    all_mut_specs = list(mutation_specs_by_slug.values())
    return {
        "property_id": prop_norm,
        "scratch_dir": str(s_dir),
        "snapshots_evaluated": len(diffs),
        "snapshots_analyzed": len(diffs),
        "diffs": diffs,
        "template_mutation_specs": all_mut_specs,
        "mutations_required": [m for m in all_mut_specs if m.get("mutation_required")],
    }


FREE_TOOL_URL_FOOTPRINTS: Tuple[str, ...] = (
    "/tools/",
    "/tool/",
    "/calculator",
    "/calculators/",
    "/generator",
    "/check",
    "/checker",
    "/simulator",
    "/estimator",
    "/analyzer",
    "?",
)

OFF_VERTICAL_CONSUMER_TOOL_PATTERNS: Tuple[str, ...] = (
    "twitter downloader",
    "twitter video downloader",
    "x video downloader",
    "fake tweet generator",
    "twitter thread maker",
    "x id converter",
    "shadowban checker",
    "tweepcred",
    "tiktok downloader",
    "instagram reel downloader",
    "youtube mp3",
    "can i vibe code",
    "canivibecodeit",
)

DEFAULT_TENANT_TOOL_DISCOVERY_SEEDS: Dict[str, Dict[str, Any]] = {
    "profithelm": {
        "seed_competitors": [
            {
                "domain": "section179.org",
                "url": "https://www.section179.org/section_179_calculator/",
                "organic_traffic": 14800,
                "dr": 54,
                "in_top_nav_free_tools": True,
                "tool_title": "Section 179 Tax Deduction Calculator",
            },
            {
                "domain": "crestcapital.com",
                "url": "https://www.crestcapital.com/section-179-calculator",
                "organic_traffic": 9200,
                "dr": 51,
                "in_top_nav_free_tools": True,
                "tool_title": "Section 179 & Equipment Lease Calculator",
            },
            {
                "domain": "ipx1031.com",
                "url": "https://www.ipx1031.com/1031-capital-gains-calculator/",
                "organic_traffic": 6400,
                "dr": 49,
                "in_top_nav_free_tools": True,
                "tool_title": "1031 Exchange Capital Gains Tax Deferral Calculator",
            },
            {
                "domain": "kalshi.com",
                "url": "https://kalshi.com/tools/prediction-market-odds-calculator",
                "organic_traffic": 5100,
                "dr": 62,
                "in_top_nav_free_tools": True,
                "tool_title": "Prediction Market Implied Probability & EV Calculator",
            },
        ],
        "keyword_universe": [
            {
                "keyword": "section 179 calculator",
                "source_competitor": "section179.org",
                "source_url": "https://www.section179.org/section_179_calculator/",
                "position": 1,
                "volume": 18100,
                "traffic": 6800,
                "kd": 34,
                "intent": "tool",
                "expansion_source": "top_pages",
                "tool_results_in_top10": 8,
                "avg_top10_dr": 52,
                "serp_dominant_format": "interactive_tool",
                "top10_urls": [
                    "https://www.section179.org/section_179_calculator/",
                    "https://www.crestcapital.com/section-179-calculator",
                    "https://www.nationalfunding.com/blog/section-179-calculator/",
                    "https://www.omnicalculator.com/finance/section-179",
                    "https://www.taxact.com/tax-information/tax-calculators/section-179-calculator",
                ],
            },
            {
                "keyword": "how to calculate section 179 deduction",
                "source_competitor": "crestcapital.com",
                "source_url": "https://www.crestcapital.com/section-179-calculator",
                "position": 3,
                "volume": 3600,
                "traffic": 1150,
                "kd": 28,
                "intent": "questions",
                "expansion_source": "questions",
                "tool_results_in_top10": 6,
                "avg_top10_dr": 50,
                "serp_dominant_format": "interactive_tool",
                "top10_urls": [
                    "https://www.section179.org/section_179_calculator/",
                    "https://www.crestcapital.com/section-179-calculator",
                    "https://www.omnicalculator.com/finance/section-179",
                    "https://www.irs.gov/publications/p946",
                ],
            },
            {
                "keyword": "1031 exchange capital gains calculator",
                "source_competitor": "ipx1031.com",
                "source_url": "https://www.ipx1031.com/1031-capital-gains-calculator/",
                "position": 2,
                "volume": 5400,
                "traffic": 1950,
                "kd": 31,
                "intent": "tool",
                "expansion_source": "top_pages",
                "tool_results_in_top10": 7,
                "avg_top10_dr": 48,
                "serp_dominant_format": "interactive_tool",
                "top10_urls": [
                    "https://www.ipx1031.com/1031-capital-gains-calculator/",
                    "https://www.exeter1031.com/1031_exchange_calculator.aspx",
                    "https://www.firstamericanexchange.com/resources/calculators/capital-gains-calculator",
                    "https://www.equityadvantage1031.com/calculator/",
                ],
            },
            {
                "keyword": "1031 exchange boot and depreciation recapture calculator",
                "source_competitor": "ipx1031.com",
                "source_url": "https://www.ipx1031.com/1031-capital-gains-calculator/",
                "position": 5,
                "volume": 1900,
                "traffic": 640,
                "kd": 24,
                "intent": "matching_terms",
                "expansion_source": "matching_terms",
                "tool_results_in_top10": 6,
                "avg_top10_dr": 46,
                "serp_dominant_format": "interactive_tool",
                "top10_urls": [
                    "https://www.ipx1031.com/1031-capital-gains-calculator/",
                    "https://www.exeter1031.com/1031_exchange_calculator.aspx",
                    "https://www.firstamericanexchange.com/resources/calculators/capital-gains-calculator",
                ],
            },
        ],
    },
    "prexvo": {
        "seed_competitors": [
            {
                "domain": "studentloanplanner.com",
                "url": "https://www.studentloanplanner.com/free-student-loan-calculator/",
                "organic_traffic": 19400,
                "dr": 61,
                "in_top_nav_free_tools": True,
                "tool_title": "RAP vs IBR Student Loan Calculator",
            },
            {
                "domain": "tateesq.com",
                "url": "https://www.tateesq.com/tool/student-loan-calculator",
                "organic_traffic": 8300,
                "dr": 44,
                "in_top_nav_free_tools": True,
                "tool_title": "PSLF Buyback & IDR Payment Simulator",
            },
            {
                "domain": "whitecoatinvestor.com",
                "url": "https://www.whitecoatinvestor.com/student-loan-refinancing-calculator/",
                "organic_traffic": 6200,
                "dr": 64,
                "in_top_nav_free_tools": True,
                "tool_title": "Student Loan Refinance Break-Even Calculator",
            },
        ],
        "keyword_universe": [
            {
                "keyword": "rap vs ibr student loan calculator",
                "source_competitor": "studentloanplanner.com",
                "source_url": "https://www.studentloanplanner.com/free-student-loan-calculator/",
                "position": 2,
                "volume": 8800,
                "traffic": 3400,
                "kd": 26,
                "intent": "tool",
                "expansion_source": "top_pages",
                "tool_results_in_top10": 7,
                "avg_top10_dr": 51,
                "serp_dominant_format": "interactive_tool",
                "top10_urls": [
                    "https://www.studentloanplanner.com/free-student-loan-calculator/",
                    "https://www.tateesq.com/tool/student-loan-calculator",
                    "https://studentaid.gov/loan-simulator/",
                    "https://www.nerdwallet.com/article/loans/student-loans/student-loan-calculator",
                ],
            },
            {
                "keyword": "repayment assistance plan rap monthly payment calculator",
                "source_competitor": "studentloanplanner.com",
                "source_url": "https://www.studentloanplanner.com/free-student-loan-calculator/",
                "position": 4,
                "volume": 4200,
                "traffic": 1480,
                "kd": 22,
                "intent": "related_terms",
                "expansion_source": "related_terms",
                "tool_results_in_top10": 6,
                "avg_top10_dr": 49,
                "serp_dominant_format": "interactive_tool",
                "top10_urls": [
                    "https://www.studentloanplanner.com/free-student-loan-calculator/",
                    "https://www.tateesq.com/tool/student-loan-calculator",
                    "https://studentaid.gov/loan-simulator/",
                ],
            },
            {
                "keyword": "pslf buyback calculator",
                "source_competitor": "tateesq.com",
                "source_url": "https://www.tateesq.com/tool/student-loan-calculator",
                "position": 1,
                "volume": 6100,
                "traffic": 2450,
                "kd": 19,
                "intent": "tool",
                "expansion_source": "top_pages",
                "tool_results_in_top10": 6,
                "avg_top10_dr": 45,
                "serp_dominant_format": "interactive_tool",
                "top10_urls": [
                    "https://www.tateesq.com/tool/student-loan-calculator",
                    "https://www.studentloanplanner.com/pslf-buyback-program/",
                    "https://studentaid.gov/manage-loans/forgiveness-cancellation/public-service/public-service-loan-forgiveness-buyback",
                ],
            },
            {
                "keyword": "how to calculate pslf buyback settlement amount",
                "source_competitor": "tateesq.com",
                "source_url": "https://www.tateesq.com/tool/student-loan-calculator",
                "position": 3,
                "volume": 1800,
                "traffic": 610,
                "kd": 16,
                "intent": "questions",
                "expansion_source": "questions",
                "tool_results_in_top10": 5,
                "avg_top10_dr": 44,
                "serp_dominant_format": "interactive_tool",
                "top10_urls": [
                    "https://www.tateesq.com/tool/student-loan-calculator",
                    "https://www.studentloanplanner.com/pslf-buyback-program/",
                ],
            },
        ],
    },
    "gainhelm": {
        "seed_competitors": [
            {
                "domain": "vanta.com",
                "url": "https://www.vanta.com/tools/soc-2-cost-calculator",
                "organic_traffic": 11200,
                "dr": 72,
                "in_top_nav_free_tools": True,
                "tool_title": "SOC 2 Audit Cost & ROI Calculator",
            },
            {
                "domain": "sprinto.com",
                "url": "https://sprinto.com/tools/cmmc-compliance-cost-calculator/",
                "organic_traffic": 5800,
                "dr": 58,
                "in_top_nav_free_tools": True,
                "tool_title": "CMMC 2.0 Level 2 Assessment Cost Calculator",
            },
            {
                "domain": "summit7.us",
                "url": "https://www.summit7.us/tools/sprs-score-calculator",
                "organic_traffic": 7400,
                "dr": 47,
                "in_top_nav_free_tools": True,
                "tool_title": "NIST SP 800-171 DoD SPRS Score Calculator",
            },
        ],
        "keyword_universe": [
            {
                "keyword": "soc 2 audit cost calculator",
                "source_competitor": "vanta.com",
                "source_url": "https://www.vanta.com/tools/soc-2-cost-calculator",
                "position": 1,
                "volume": 4900,
                "traffic": 1950,
                "kd": 29,
                "intent": "tool",
                "expansion_source": "top_pages",
                "tool_results_in_top10": 6,
                "avg_top10_dr": 56,
                "serp_dominant_format": "interactive_tool",
                "top10_urls": [
                    "https://www.vanta.com/tools/soc-2-cost-calculator",
                    "https://sprinto.com/blog/soc-2-compliance-cost/",
                    "https://secureframe.com/hub/soc-2/cost",
                ],
            },
            {
                "keyword": "soc 2 type 1 vs type 2 cpa audit fee estimator",
                "source_competitor": "vanta.com",
                "source_url": "https://www.vanta.com/tools/soc-2-cost-calculator",
                "position": 4,
                "volume": 1600,
                "traffic": 540,
                "kd": 23,
                "intent": "matching_terms",
                "expansion_source": "matching_terms",
                "tool_results_in_top10": 5,
                "avg_top10_dr": 54,
                "serp_dominant_format": "interactive_tool",
                "top10_urls": [
                    "https://www.vanta.com/tools/soc-2-cost-calculator",
                    "https://sprinto.com/blog/soc-2-compliance-cost/",
                ],
            },
            {
                "keyword": "nist 800-171 sprs score calculator",
                "source_competitor": "summit7.us",
                "source_url": "https://www.summit7.us/tools/sprs-score-calculator",
                "position": 1,
                "volume": 5200,
                "traffic": 2180,
                "kd": 21,
                "intent": "tool",
                "expansion_source": "top_pages",
                "tool_results_in_top10": 7,
                "avg_top10_dr": 46,
                "serp_dominant_format": "interactive_tool",
                "top10_urls": [
                    "https://www.summit7.us/tools/sprs-score-calculator",
                    "https://www.preveil.com/sprs-score-calculator/",
                    "https://www.acquisition.gov/dfars/252.204-7019",
                ],
            },
            {
                "keyword": "how to calculate dod sprs score 110 point deduction",
                "source_competitor": "summit7.us",
                "source_url": "https://www.summit7.us/tools/sprs-score-calculator",
                "position": 3,
                "volume": 1750,
                "traffic": 590,
                "kd": 18,
                "intent": "questions",
                "expansion_source": "questions",
                "tool_results_in_top10": 6,
                "avg_top10_dr": 45,
                "serp_dominant_format": "interactive_tool",
                "top10_urls": [
                    "https://www.summit7.us/tools/sprs-score-calculator",
                    "https://www.preveil.com/sprs-score-calculator/",
                ],
            },
        ],
    },
}


def extract_competitor_free_tool_footprints(
    competitor_pages: List[Dict[str, Any]],
    *,
    tenant_id: str = "profithelm",
    min_traffic: int = 25,
) -> Dict[str, Any]:
    """
    Implements Steps 1 & 2 of the x-like:2108272246804648049 (Letaido / Ahrefs) free-tool
    discovery pipeline:
    - Filters competitor Top Pages and top-navigation 'Free Tools' dropdown entries to URLs
      matching interactive tool footprints (/tools/, /calculator/, /generator/, /check/,
      /simulator/, /estimator/, or parameterized query strings) with proven organic traffic.
    - Rejects off-vertical consumer tools (e.g., 'twitter video downloader', 'fake tweet generator',
      'shadowban checker', 'canivibecodeit' thin SaaS clones) and cross-tenant contamination.
    Zero em-dashes. Zero en-dashes.
    """
    prop = str(tenant_id or "profithelm").strip().lower()
    qualified_pages: List[Dict[str, Any]] = []
    rejected_pages: List[Dict[str, Any]] = []

    for row in competitor_pages or []:
        if not isinstance(row, dict):
            continue
        url = str(row.get("url") or "").strip()
        title = str(row.get("tool_title") or row.get("title") or "").strip()
        domain = str(row.get("domain") or "").strip().lower()
        traffic = int(float(row.get("organic_traffic", row.get("traffic", 0)) or 0))
        in_nav = bool(row.get("in_top_nav_free_tools", False))

        combined_low = f"{url} {title} {domain}".lower()
        if any(off_tok in combined_low for off_tok in OFF_VERTICAL_CONSUMER_TOOL_PATTERNS):
            rejected_pages.append(
                {
                    "url": url,
                    "domain": domain,
                    "reason": "OFF_VERTICAL_CONSUMER_OR_SOCIAL_MEDIA_TOOL",
                }
            )
            continue

        has_footprint = any(fp in url.lower() for fp in FREE_TOOL_URL_FOOTPRINTS) or any(
            kw in title.lower() for kw in ("calculator", "simulator", "estimator", "checker", "generator", "tool")
        )
        if not has_footprint:
            rejected_pages.append(
                {
                    "url": url,
                    "domain": domain,
                    "reason": "MISSING_INTERACTIVE_TOOL_URL_FOOTPRINT",
                }
            )
            continue

        if traffic < min_traffic and not in_nav:
            rejected_pages.append(
                {
                    "url": url,
                    "domain": domain,
                    "reason": f"INSUFFICIENT_ORGANIC_TRAFFIC ({traffic} < {min_traffic})",
                }
            )
            continue

        qualified_pages.append(
            {
                "domain": domain,
                "url": url,
                "tool_title": title,
                "organic_traffic": traffic,
                "dr": float(row.get("dr", 45.0) or 45.0),
                "in_top_nav_free_tools": in_nav,
                "matched_footprints": [fp for fp in FREE_TOOL_URL_FOOTPRINTS if fp in url.lower()],
            }
        )

    qualified_pages.sort(key=lambda x: (-int(x["organic_traffic"]), x["url"]))
    return {
        "property_id": prop,
        "total_evaluated": len(competitor_pages or []),
        "qualified_count": len(qualified_pages),
        "rejected_count": len(rejected_pages),
        "qualified_tool_pages": qualified_pages,
        "rejected_tool_pages": rejected_pages,
    }


def filter_rankable_tool_keywords(
    keyword_rows: List[Dict[str, Any]],
    *,
    tenant_id: str = "profithelm",
    tenant_dr: float = 28.0,
    max_kd_delta: float = 22.0,
    min_volume: int = 30,
) -> Dict[str, Any]:
    """
    Implements Steps 3, 4 & 5 of the x-like:2108272246804648049 tool-keyword pipeline:
    - Step 3: Keeps keywords ranking top 20 on competitor tool pages with volume >= min_volume.
    - Step 4: Accepts expanded universe terms from matching_terms, related_terms, and questions.
    - Step 5: Filters for 'we can actually rank':
      * Drops off-vertical social/consumer tools.
      * Drops keywords where SERP is all video or news (serp_dominant_format in ('video', 'news')).
      * Drops keywords dominated by mega-DR sites (avg_top10_dr > 80) with zero visible tool-page
        intent in top 10 (tool_results_in_top10 == 0).
      * Drops keywords where KD exceeds tenant_dr + max_kd_delta.
    Zero em-dashes. Zero en-dashes.
    """
    prop = str(tenant_id or "profithelm").strip().lower()
    kd_ceiling = float(tenant_dr) + float(max_kd_delta)
    surviving: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []

    for row in keyword_rows or []:
        if not isinstance(row, dict):
            continue
        kw = str(row.get("keyword") or row.get("query") or "").strip()
        if not kw:
            continue
        kw_low = kw.lower()
        pos = int(float(row.get("position", 10) or 10))
        vol = int(float(row.get("volume", 0) or 0))
        traffic = int(float(row.get("traffic", 0) or 0))
        kd = float(row.get("kd", 25.0) or 25.0)
        tool_top10 = int(float(row.get("tool_results_in_top10", 3) or 0))
        avg_dr = float(row.get("avg_top10_dr", 50.0) or 50.0)
        dom_fmt = str(row.get("serp_dominant_format") or "interactive_tool").strip().lower()

        if any(off_tok in kw_low for off_tok in OFF_VERTICAL_CONSUMER_TOOL_PATTERNS):
            dropped.append({"keyword": kw, "reason": "OFF_VERTICAL_CONSUMER_QUERY"})
            continue
        if pos > 20:
            dropped.append({"keyword": kw, "reason": f"COMPETITOR_RANK_OUTSIDE_TOP_20 ({pos})"})
            continue
        if vol < min_volume:
            dropped.append({"keyword": kw, "reason": f"VOLUME_BELOW_THRESHOLD ({vol} < {min_volume})"})
            continue
        if dom_fmt in ("video", "news", "video_carousel", "top_stories"):
            dropped.append({"keyword": kw, "reason": f"SERP_DOMINATED_BY_{dom_fmt.upper()}"})
            continue
        if tool_top10 <= 0:
            dropped.append({"keyword": kw, "reason": "ZERO_TOOL_INTENT_IN_TOP_10"})
            continue
        if avg_dr > 80.0 and tool_top10 < 2:
            dropped.append({"keyword": kw, "reason": f"MEGA_DR_NO_TOOL_INTENT (avg_dr={avg_dr})"})
            continue
        if kd > kd_ceiling:
            dropped.append({"keyword": kw, "reason": f"KD_EXCEEDS_RANKABLE_CEILING ({kd} > {kd_ceiling})"})
            continue

        surviving.append(
            {
                "keyword": kw,
                "source_competitor": str(row.get("source_competitor") or ""),
                "source_url": str(row.get("source_url") or ""),
                "position": pos,
                "volume": vol,
                "traffic": traffic,
                "kd": kd,
                "intent": str(row.get("intent") or "tool"),
                "expansion_source": str(row.get("expansion_source") or "top_pages"),
                "tool_results_in_top10": tool_top10,
                "avg_top10_dr": avg_dr,
                "serp_dominant_format": dom_fmt,
                "top10_urls": [str(u).strip() for u in (row.get("top10_urls") or []) if str(u).strip()],
            }
        )

    surviving.sort(key=lambda x: (-int(x["volume"]), float(x["kd"]), x["keyword"]))
    return {
        "property_id": prop,
        "tenant_dr": float(tenant_dr),
        "kd_ceiling": kd_ceiling,
        "total_evaluated": len(keyword_rows or []),
        "surviving_count": len(surviving),
        "dropped_count": len(dropped),
        "surviving_keywords": surviving,
        "dropped_keywords": dropped,
    }


def _resolve_canonical_cluster_slug_for_keyword(keyword: str, tenant_id: str) -> str:
    """Resolves a keyword to its canonical tenant tool slug to prevent duplicate tool cannibalization."""
    kw_low = str(keyword or "").lower()
    prop = str(tenant_id or "profithelm").strip().lower()
    if prop == "prexvo":
        if "pslf" in kw_low and "buyback" in kw_low:
            return "pslf-buyback-calculator"
        if "rap" in kw_low and "ibr" in kw_low:
            return "rap-vs-ibr-calculator"
        if "rap" in kw_low or "repayment assistance" in kw_low:
            return "rap-payment-calculator"
        if "refinance" in kw_low:
            return "student-loan-refinance-break-even-calculator"
        if "parent plus" in kw_low and "loophole" in kw_low:
            return "parent-plus-double-consolidation-loophole-2026-calculator"
        if "parent plus" in kw_low:
            return "parent-plus-repayment-strategy"
        if "icr" in kw_low:
            return "icr-repayment-calculator"
        if "paye" in kw_low:
            return "paye-sunset-calculator"
        if "hardship" in kw_low or "ibr" in kw_low:
            return "ibr-hardship-cap-calculator"
    elif prop == "gainhelm":
        if "soc 2" in kw_low or "soc-2" in kw_low:
            return "soc-2-audit-cost-calculator"
        if "sprs" in kw_low or "800-171" in kw_low:
            return "nist-800-171-sprs-score-calculator"
        if "cmmc" in kw_low:
            return "cmmc-2-0-compliance-cost-calculator"
        if "iso 27001" in kw_low or "27001" in kw_low:
            return "iso-27001-certification-cost-calculator"
        if "hipaa" in kw_low:
            return "hipaa-violation-penalty-breach-cost-calculator"
        if "pci" in kw_low:
            return "pci-dss-4-0-compliance-cost-calculator"
        if "fedramp" in kw_low or "3pao" in kw_low:
            return "fedramp-authorization-3pao-cost-calculator"
        if "hitrust" in kw_low:
            return "hitrust-csf-e1-i1-r2-certification-cost-calculator"
    else:
        if "179" in kw_low or "4562" in kw_low:
            return "section-179-calculator"
        if "1031" in kw_low or "8824" in kw_low or "like-kind" in kw_low:
            return "section-1031-calculator"
        if "s-corp" in kw_low or "s corp" in kw_low or "reasonable salary" in kw_low:
            return "s-corp-reasonable-salary-tax-calculator"
        if "301" in kw_low or "tariff" in kw_low:
            return "section-301-tariff-landed-cost-calculator"
        if "prediction market" in kw_low and ("tax" in kw_low or "1256" in kw_low):
            return "prediction-market-tax"
        if "prediction market" in kw_low or "implied probability" in kw_low or "kalshi" in kw_low:
            return "prediction-market-odds"
        if "crypto" in kw_low or "8949" in kw_low:
            return "crypto-tax-calculator"
        if "runway" in kw_low or "burn multiple" in kw_low:
            return "saas-runway-calculator"
    return sanitize_url_slug(keyword)


def cluster_keywords_by_serp_overlap(
    surviving_keywords: List[Dict[str, Any]],
    *,
    tenant_id: str = "profithelm",
    min_serp_overlap_ratio: float = 0.30,
) -> List[Dict[str, Any]]:
    """
    Implements Step 6 of the x-like:2108272246804648049 tool-keyword pipeline:
    Groups surviving keywords by shared top-10 SERP URL overlap (same URLs ranking -> same intent ->
    one canonical tool serves the entire cluster without crawl-budget cannibalization).
    Zero em-dashes. Zero en-dashes.
    """
    prop = str(tenant_id or "profithelm").strip().lower()
    engine = CompetitorGapEngine(tenant_id=prop)
    raw_clusters: List[Dict[str, Any]] = []

    for kw_obj in surviving_keywords or []:
        if not isinstance(kw_obj, dict):
            continue
        kw = str(kw_obj.get("keyword") or "").strip()
        if not kw:
            continue
        urls_set = {u.rstrip("/").lower() for u in (kw_obj.get("top10_urls") or []) if str(u).strip()}
        cand_slug = _resolve_canonical_cluster_slug_for_keyword(kw, prop)

        matched_cluster: Optional[Dict[str, Any]] = None
        best_overlap = 0.0
        for cl in raw_clusters:
            cl_urls = cl["_url_set"]
            if urls_set and cl_urls:
                denom = max(1, min(len(urls_set), len(cl_urls)))
                overlap_ratio = len(urls_set & cl_urls) / float(denom)
            else:
                overlap_ratio = 1.0 if cl["target_slug"] == cand_slug else 0.0
            if overlap_ratio >= min_serp_overlap_ratio or cl["target_slug"] == cand_slug:
                if overlap_ratio >= best_overlap:
                    best_overlap = max(overlap_ratio, 0.35)
                    matched_cluster = cl

        if matched_cluster is None:
            raw_clusters.append(
                {
                    "target_slug": cand_slug,
                    "members": [kw_obj],
                    "_url_set": set(urls_set),
                    "_overlap_scores": [1.0],
                }
            )
        else:
            matched_cluster["members"].append(kw_obj)
            matched_cluster["_url_set"].update(urls_set)
            matched_cluster["_overlap_scores"].append(best_overlap)

    output_clusters: List[Dict[str, Any]] = []
    for idx, cl in enumerate(raw_clusters, start=1):
        members = sorted(cl["members"], key=lambda m: (-int(m.get("volume", 0)), float(m.get("kd", 25.0))))
        primary_m = members[0]
        primary_kw = str(primary_m["keyword"])
        supporting_kws = [str(m["keyword"]) for m in members[1:]]
        combined_vol = sum(int(m.get("volume", 0)) for m in members)
        combined_traffic = sum(int(m.get("traffic", 0)) for m in members)
        avg_kd = round(sum(float(m.get("kd", 25.0)) for m in members) / max(1, len(members)), 2)
        avg_overlap = round(sum(cl["_overlap_scores"]) / max(1, len(cl["_overlap_scores"])), 2)
        comp_domains = sorted(
            {
                str(m.get("source_competitor") or "").strip().lower()
                for m in members
                if str(m.get("source_competitor") or "").strip()
            }
        )
        comp_urls = sorted(
            {
                str(m.get("source_url") or "").strip()
                for m in members
                if str(m.get("source_url") or "").strip()
            }
        )
        t_slug = str(cl["target_slug"])
        enriched = engine.enrich_candidate_spec(
            {
                "slug": t_slug,
                "query": primary_kw,
                "title": _format_safe_heading_topic(primary_kw, t_slug),
            }
        )
        topic_lbl = _format_safe_heading_topic(primary_kw, t_slug)
        if "calculator" not in topic_lbl.lower():
            suggested_concept = f"{topic_lbl} Calculator"
        else:
            suggested_concept = topic_lbl

        output_clusters.append(
            {
                "cluster_id": f"{prop}-cluster-{idx:02d}",
                "property_id": prop,
                "target_slug": t_slug,
                "suggested_tool_concept": suggested_concept,
                "primary_keyword": primary_kw,
                "supporting_keywords": supporting_kws,
                "keywords_count": len(members),
                "combined_volume": combined_vol,
                "combined_competitor_traffic": combined_traffic,
                "avg_kd": avg_kd,
                "avg_top10_dr": round(
                    sum(float(m.get("avg_top10_dr", 50.0)) for m in members) / max(1, len(members)),
                    1,
                ),
                "avg_tool_results_in_top10": round(
                    sum(int(m.get("tool_results_in_top10", 3)) for m in members) / max(1, len(members)),
                    1,
                ),
                "serp_overlap_ratio": avg_overlap,
                "competitors_ranking": comp_domains,
                "competitor_urls": comp_urls,
                "shared_serp_urls": sorted(cl["_url_set"])[:8],
                "statutory_authority": str(enriched.get("statutory_authority", "")),
                "economic_dataset": str(enriched.get("economic_dataset", "")),
                "keyword_drilldown": members,
            }
        )

    output_clusters.sort(key=lambda c: (-int(c["combined_volume"]), float(c["avg_kd"]), c["target_slug"]))
    return output_clusters


def score_tool_cluster_roi_and_crawl_risk(
    cluster: Dict[str, Any],
    *,
    tenant_id: str = "profithelm",
    tenant_dr: float = 28.0,
    existing_estate_slugs: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """
    Implements Steps 7 & 8 of the x-like:2108272246804648049 tool-keyword pipeline:
    Scores each SERP-overlap cluster on:
      1. traffic_potential_score (0-100)
      2. kd_vs_tenant_dr_score (0-100)
      3. build_complexity_score (0-100, higher = simpler deterministic AST formula)
      4. competitor_weakness_score (0-100)
      5. algorithmic_roi_score (0-100 weighted composite)
      6. crawl_budget_risk_score (0-100, lower = safer for indexation & crawl budget)
    Synthesizes the deterministic one-paragraph 'what_to_build' brief for top clusters.
    Zero em-dashes. Zero en-dashes.
    """
    prop = str(tenant_id or cluster.get("property_id") or "profithelm").strip().lower()
    t_slug = str(cluster.get("target_slug") or "")
    primary_kw = str(cluster.get("primary_keyword") or "")
    concept = str(cluster.get("suggested_tool_concept") or _format_safe_heading_topic(primary_kw, t_slug))
    combined_vol = int(cluster.get("combined_volume", 0) or 0)
    avg_kd = float(cluster.get("avg_kd", 25.0) or 25.0)
    avg_top10_dr = float(cluster.get("avg_top10_dr", 50.0) or 50.0)
    tool_top10 = float(cluster.get("avg_tool_results_in_top10", 4.0) or 4.0)
    stat_auth = str(cluster.get("statutory_authority") or "26 U.S.C. Section 179")
    econ_ds = str(cluster.get("economic_dataset") or "Federal Reserve Macroeconomic Series")

    traffic_score = round(min(100.0, 35.0 + (combined_vol / 250.0)), 1)
    kd_gap = float(tenant_dr) + 22.0 - avg_kd
    kd_score = round(max(10.0, min(100.0, 50.0 + (kd_gap * 2.2))), 1)
    build_score = 88.0
    comp_weakness = round(
        max(20.0, min(100.0, (100.0 - (avg_top10_dr * 0.55)) + (tool_top10 * 4.5))),
        1,
    )
    roi_score = round(
        (traffic_score * 0.35) + (kd_score * 0.25) + (comp_weakness * 0.25) + (build_score * 0.15),
        1,
    )

    already_exists = bool(existing_estate_slugs and t_slug in existing_estate_slugs)
    # Consolidating into an existing canonical tool or building a high-overlap statutory calculator has very low crawl risk
    base_crawl_risk = 12.0 if already_exists else 18.0
    if combined_vol < 100:
        base_crawl_risk += 35.0
    if tool_top10 < 2:
        base_crawl_risk += 30.0
    crawl_risk_score = round(min(100.0, base_crawl_risk), 1)

    if crawl_risk_score >= 50.0 or roi_score < 50.0:
        action = "REJECT_CRAWL_BLOAT_OR_LOW_ROI"
    elif already_exists:
        action = "UPGRADE_EXISTING_CANONICAL_TOOL"
    else:
        action = "BUILD_NEW_CANONICAL_TOOL"

    supporting_list = cluster.get("supporting_keywords") or []
    supp_preview = ", ".join(supporting_list[:3]) if supporting_list else primary_kw
    domain = "prexvo.com" if prop == "prexvo" else ("gainhelm.com" if prop == "gainhelm" else "profithelm.com")
    what_to_build = (
        f"Build or enrich the zero-signup instant-result {concept} at https://{domain}/tools/{t_slug}/ "
        f"targeting '{primary_kw}' and SERP-overlap variants ({supp_preview}) under {stat_auth} and {econ_ds}. "
        f"Render the primary numeric calculation and 5-point (0.8x to 1.2x) sensitivity schedule immediately "
        f"on initial SSR load with zero login or email gate, pair every input with 44x44px mobile touch targets "
        f"and deep-linkable preset pills, include an ordered HowTo procedural step list and expandable <details> "
        f"FAQ accordion, emit connected SoftwareApplication (price: 0 USD), Dataset, HowTo, FAQPage, and "
        f"BreadcrumbList JSON-LD, and route commercial handoff through one focused vertical CTA."
    )

    scored = dict(cluster)
    scored.update(
        {
            "already_in_tenant_estate": already_exists,
            "recommended_action": action,
            "scores": {
                "traffic_potential_score": traffic_score,
                "kd_vs_tenant_dr_score": kd_score,
                "build_complexity_score": build_score,
                "competitor_weakness_score": comp_weakness,
                "algorithmic_roi_score": roi_score,
                "crawl_budget_risk_score": crawl_risk_score,
            },
            "algorithmic_roi_score": roi_score,
            "crawl_budget_risk_score": crawl_risk_score,
            "what_to_build": what_to_build,
        }
    )
    return scored


def run_agentic_free_tool_keyword_pipeline(
    tenant_id: str = "profithelm",
    *,
    seed_competitors: Optional[List[Dict[str, Any]]] = None,
    keyword_universe: Optional[List[Dict[str, Any]]] = None,
    tenant_dr: float = 28.0,
    repo_root: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """
    Executes the complete 8-Step Agentic Free-Tool Keyword Discovery & SERP-Overlap Clustering
    Pipeline dissected from x-like:2108272246804648049 (Rob Hallam @robj3d3 / Letaido workflow),
    parameterized across ProfitHelm, Prexvo, and GainHelm:
      Step 1: Seed competitor set by organic traffic overlap.
      Step 2: Filter competitor Top Pages & 'Free Tools' nav to ranking tool URL footprints.
      Step 3: Pull top-20 keywords driving those competitor tool pages.
      Step 4: Expand universe via matching_terms, related_terms, and questions.
      Step 5: Filter for rankable tool intent (drop video/news SERPs, mega-DR non-tool SERPs, off-vertical).
      Step 6: Cluster surviving keywords by shared top-10 SERP URL overlap (1 tool per intent cluster).
      Step 7: Score clusters on traffic potential, KD vs DR, competitor weakness, ROI, and crawl-budget risk.
      Step 8: Deliver ranked cluster table, per-cluster drill-down, and one-paragraph 'what_to_build' brief.
    Zero em-dashes. Zero en-dashes.
    """
    prop = str(tenant_id or "profithelm").strip().lower()
    default_bundle = DEFAULT_TENANT_TOOL_DISCOVERY_SEEDS.get(
        prop, DEFAULT_TENANT_TOOL_DISCOVERY_SEEDS["profithelm"]
    )
    eff_seeds = seed_competitors if seed_competitors is not None else default_bundle["seed_competitors"]
    eff_keywords = keyword_universe if keyword_universe is not None else default_bundle["keyword_universe"]

    if repo_root is None:
        ws_root = Path(__file__).resolve().parent.parent.parent
        repo_map = {
            "profithelm": ws_root / "profithelm-platform",
            "prexvo": ws_root / "prexvo",
            "gainhelm": ws_root / "gainhelm",
        }
        t_root = repo_map.get(prop)
    else:
        t_root = Path(repo_root)

    existing_slugs: Set[str] = set()
    if t_root and (t_root / "dist" / "tools").is_dir():
        for td in (t_root / "dist" / "tools").iterdir():
            if td.is_dir() and not td.name.startswith(".") and (td / "index.html").is_file():
                existing_slugs.add(td.name)

    step_1_2 = extract_competitor_free_tool_footprints(eff_seeds, tenant_id=prop)
    step_3_4_5 = filter_rankable_tool_keywords(
        eff_keywords,
        tenant_id=prop,
        tenant_dr=tenant_dr,
    )
    step_6_clusters = cluster_keywords_by_serp_overlap(
        step_3_4_5["surviving_keywords"],
        tenant_id=prop,
    )
    scored_clusters = [
        score_tool_cluster_roi_and_crawl_risk(
            cl,
            tenant_id=prop,
            tenant_dr=tenant_dr,
            existing_estate_slugs=existing_slugs,
        )
        for cl in step_6_clusters
    ]
    scored_clusters.sort(
        key=lambda c: (
            -float(c["algorithmic_roi_score"]),
            float(c["crawl_budget_risk_score"]),
            -int(c["combined_volume"]),
        )
    )

    return {
        "workflow": "agentic_free_tool_keyword_pipeline",
        "pointer": "x-like:2108272246804648049",
        "status": "PASS",
        "property_id": prop,
        "tenant_dr": float(tenant_dr),
        "existing_estate_tools_count": len(existing_slugs),
        "steps_executed": [
            "step_1_seed_competitor_set",
            "step_2_filter_competitor_tool_footprints",
            "step_3_pull_top20_tool_keywords",
            "step_4_expand_matching_related_questions",
            "step_5_filter_rankable_serp_tool_intent",
            "step_6_cluster_by_shared_serp_overlap",
            "step_7_score_roi_and_crawl_budget_risk",
            "step_8_deliver_ranked_clusters_and_build_briefs",
        ],
        "competitor_footprints": step_1_2,
        "keyword_filtering": step_3_4_5,
        "ranked_clusters_count": len(scored_clusters),
        "ranked_clusters": scored_clusters,
        "top_build_briefs": [
            {
                "cluster_id": c["cluster_id"],
                "target_slug": c["target_slug"],
                "suggested_tool_concept": c["suggested_tool_concept"],
                "primary_keyword": c["primary_keyword"],
                "combined_volume": c["combined_volume"],
                "algorithmic_roi_score": c["algorithmic_roi_score"],
                "crawl_budget_risk_score": c["crawl_budget_risk_score"],
                "recommended_action": c["recommended_action"],
                "what_to_build": c["what_to_build"],
            }
            for c in scored_clusters
        ],
    }


__all__ = [
    "INTERACTIVE_PATTERNS",
    "CLICK_MAGNET_PATTERNS",
    "CONVERSION_HOOK_PATTERNS",
    "SUPPORTED_SEARCH_ENGINES",
    "WINNING_COMPETITOR_MECHANICS",
    "TARGET_QUERY_BENCHMARKS",
    "COMPETITIVE_INCUMBENT_PROFILES",
    "REJECTED_COSMETIC_CHANGES",
    "BESPOKE_VS_SYSTEMIC_UPGRADE_EVALUATION",
    "GapCandidateSpec",
    "MultiEngineQueryBenchmark",
    "CompetitorGapEngine",
    "benchmark_multi_engine_rankings",
    "benchmark_all_properties",
    "run_blind_spot_pass",
    "_format_safe_heading_topic",
    "render_partner_quote_intake_html",
    "render_serp_incumbent_depth_upgrade_block",
    "render_competitor_winning_pattern_blocks",
    "get_competitive_incumbent_profile",
    "evaluate_bespoke_vs_systemic_upgrades",
    "parse_serp_dom_structural_profile",
    "diff_competitor_dom_structure",
    "diff_live_competitor_scratch_snapshots",
    "FREE_TOOL_URL_FOOTPRINTS",
    "OFF_VERTICAL_CONSUMER_TOOL_PATTERNS",
    "DEFAULT_TENANT_TOOL_DISCOVERY_SEEDS",
    "extract_competitor_free_tool_footprints",
    "filter_rankable_tool_keywords",
    "cluster_keywords_by_serp_overlap",
    "score_tool_cluster_roi_and_crawl_risk",
    "run_agentic_free_tool_keyword_pipeline",
]






