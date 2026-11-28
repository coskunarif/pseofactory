"""
pseofactory Centralized Tenant Fact & Statutory Truth Store
Stateless immutable profiles for active tenants with strict tenant boundary isolation.
Enforces:
1. Canonical pricing tier verification via pseofactory.pricing ($0, $15, $29, $299 business; $0, $9, $19, $299 consumer).
2. Grounded feature matrix contract verification.
3. Statutory tax citations (IRS Rev Proc 2024-40) and student loan citations (34 CFR Part 685).
4. Banned marketing claims rejection.
5. Mandatory regulatory disclosures (Circular 230, YMYL forfeiture disclaimer, FTC disclosure).
6. Strict cross-tenant boundary isolation.

Zero em-dashes. Zero en-dashes.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Dict, List, Any, Optional, Set, Tuple, Union

from pseofactory.contracts import assert_no_forbidden_dashes


class PropertyContaminationError(ValueError):
    """
    Raised when foreign cross-property tokens or claims bleed into a tenant.
    Zero em-dashes. Zero en-dashes.
    """
    pass


@dataclass(frozen=True)
class PricingTier:
    """
    Canonical subscription or product pricing tier for a tenant.
    Zero em-dashes. Zero en-dashes.
    """
    name: str
    price_usd: float
    billing_period: str
    features: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "price_usd": self.price_usd,
            "billing_period": self.billing_period,
            "features": list(self.features),
        }


@dataclass(frozen=True)
class FeatureContract:
    """
    Verified feature contract for a tenant.
    Zero em-dashes. Zero en-dashes.
    """
    name: str
    enabled: bool
    tier_availability: List[str] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "tier_availability": list(self.tier_availability),
            "description": self.description,
        }


@dataclass(frozen=True)
class TenantStatutoryTruth:
    """
    Primary statutory citations and empirical limits for a tenant.
    Zero em-dashes. Zero en-dashes.
    """
    tenant_id: str
    statutory_citations: Dict[str, str] = field(default_factory=dict)
    limits_and_thresholds: Dict[str, Any] = field(default_factory=dict)
    regulator_name: str = ""
    controlling_statute: str = ""
    effective_tax_year: str = "2026"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "statutory_citations": dict(self.statutory_citations),
            "limits_and_thresholds": dict(self.limits_and_thresholds),
            "regulator_name": self.regulator_name,
            "controlling_statute": self.controlling_statute,
            "effective_tax_year": self.effective_tax_year,
        }


StatutoryTruthRule = TenantStatutoryTruth


def _load_truth_pack_safe(
    property_id: str,
    workspace_root: Optional[Path] = None,
) -> Optional[Any]:
    """Loads a TruthPack if present without falling back to any other tenant."""
    try:
        from pseofactory.truth_pack import load_truth_pack

        return load_truth_pack(property_id, workspace_root=workspace_root, allow_expired=True)
    except Exception:
        return None


def _tp_entry_value(pack: Optional[Any], key: str, default: Any) -> Any:
    """Reads an entry value from a loaded TruthPack or returns default."""
    if pack is None:
        return default
    entry = getattr(pack, "entries", {}).get(key)
    if entry is None:
        return default
    return entry.value


def _build_statutory_truth_from_truth_pack(pack: Any) -> TenantStatutoryTruth:
    """Synthesizes a TenantStatutoryTruth directly from a TruthPack (for 50+ dynamic sites)."""
    citations: Dict[str, str] = {}
    limits: Dict[str, Any] = {}
    publishers: List[str] = []
    cit_list: List[str] = []
    max_year = 2026

    for key, entry in getattr(pack, "entries", {}).items():
        limits[key] = entry.value
        if entry.citation:
            citations[key] = entry.citation
            if entry.citation not in cit_list:
                cit_list.append(entry.citation)
        if entry.publisher and entry.publisher not in publishers:
            publishers.append(entry.publisher)
        if getattr(entry, "effective_year", 0):
            try:
                yr = int(entry.effective_year)
                if yr > max_year:
                    max_year = yr
            except (TypeError, ValueError):
                pass

    reg_name = ", ".join(publishers[:3]) if publishers else str(getattr(pack, "brand_name", "") or pack.property_id)
    ctrl_stat = "; ".join(cit_list[:4]) if cit_list else str(getattr(pack, "brand_name", "") or pack.property_id)
    eff_yr = "2026" if 2026 in {getattr(e, "effective_year", 0) for e in getattr(pack, "entries", {}).values()} else str(max_year)
    return TenantStatutoryTruth(
        tenant_id=pack.property_id,
        statutory_citations=citations,
        limits_and_thresholds=limits,
        regulator_name=reg_name,
        controlling_statute=ctrl_stat,
        effective_tax_year=eff_yr,
    )


def _build_profile_from_truth_pack(pack: Any) -> "TenantTruthProfile":
    """Builds a TenantTruthProfile dynamically from a TruthPack for 5th+ sites."""
    pricing: Dict[str, PricingTier] = {}
    for tier_key, tier_obj in (getattr(pack, "pricing_tiers", None) or {}).items():
        if isinstance(tier_obj, dict):
            pricing[str(tier_key)] = PricingTier(
                name=str(tier_obj.get("label") or tier_obj.get("name") or tier_key),
                price_usd=float(tier_obj.get("price_usd") or 0.0),
                billing_period="one_time" if str(tier_obj.get("billing_mode") or "") != "free" else "free",
                features=[],
            )
    statutory = _build_statutory_truth_from_truth_pack(pack)
    disclosures = [d.canonical_text for d in (getattr(pack, "disclosures", None) or []) if getattr(d, "canonical_text", "")]
    banned = [
        str(b.get("pattern") or "").strip()
        for b in (getattr(pack, "banned_claims", None) or [])
        if isinstance(b, dict) and b.get("pattern")
    ]
    forbidden_tokens = {str(t).lower() for t in (getattr(pack, "cross_tenant_brand_tokens", None) or []) if str(t).strip()}
    return TenantTruthProfile(
        tenant_id=pack.property_id,
        brand_name=pack.brand_name,
        canonical_domain=pack.canonical_domain,
        pricing_tiers=pricing,
        features={},
        statutory_truth=statutory,
        claims_allowlist=[],
        claims_banned=banned,
        mandatory_disclosures=disclosures,
        cross_tenant_forbidden_tokens=forbidden_tokens,
    )


@dataclass(frozen=True)
class TenantTruthProfile:
    """
    Complete immutable truth profile for a tenant property.
    Zero em-dashes. Zero en-dashes.
    """
    tenant_id: str
    brand_name: str
    canonical_domain: str
    pricing_tiers: Dict[str, PricingTier] = field(default_factory=dict)
    features: Dict[str, FeatureContract] = field(default_factory=dict)
    statutory_truth: TenantStatutoryTruth = field(
        default_factory=lambda: TenantStatutoryTruth(tenant_id="default")
    )
    claims_allowlist: List[str] = field(default_factory=list)
    claims_banned: List[str] = field(default_factory=list)
    mandatory_disclosures: List[str] = field(default_factory=list)
    cross_tenant_forbidden_tokens: Set[str] = field(default_factory=set)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "brand_name": self.brand_name,
            "canonical_domain": self.canonical_domain,
            "pricing_tiers": {k: v.to_dict() for k, v in self.pricing_tiers.items()},
            "features": {k: v.to_dict() for k, v in self.features.items()},
            "statutory_truth": self.statutory_truth.to_dict(),
            "claims_allowlist": list(self.claims_allowlist),
            "claims_banned": list(self.claims_banned),
            "mandatory_disclosures": list(self.mandatory_disclosures),
            "cross_tenant_forbidden_tokens": list(sorted(self.cross_tenant_forbidden_tokens)),
        }


def _build_canonical_pricing_tiers(
    audience_tier: str,
    free_features: List[str],
    quick_features: List[str],
    full_features: List[str],
) -> Dict[str, PricingTier]:
    """Builds canonical TenantTruthProfile pricing_tiers directly from pseofactory.pricing."""
    from pseofactory.pricing import get_tier_pricing

    tp = get_tier_pricing(audience_tier)
    return {
        "free": PricingTier(
            name="Free",
            price_usd=0.0,
            billing_period="one_time",
            features=list(free_features),
        ),
        "quick": PricingTier(
            name="Quick Worksheet",
            price_usd=float(tp["quick"]["price_usd"]),
            billing_period="one_time",
            features=list(quick_features),
        ),
        "full": PricingTier(
            name="Full Workpaper & Data Pack",
            price_usd=float(tp["full"]["price_usd"]),
            billing_period="one_time",
            features=list(full_features),
        ),
        "partner_slot": PricingTier(
            name="Verified Calculator Partner Slot",
            price_usd=float(tp["partner_slot"]["price_usd"]),
            billing_period="one_time",
            features=["Verified Commercial Partner Desk Placement", "State-Filtered Lead Routing"],
        ),
    }


def _build_profithelm_profile() -> TenantTruthProfile:
    """Builds the canonical truth profile for ProfitHelm backed by TruthPack."""
    pack = _load_truth_pack_safe("profithelm")
    pricing = _build_canonical_pricing_tiers(
        audience_tier="business",
        free_features=["Core Calculators", "Section 179 Optimizer"],
        quick_features=[
            "Executive Scenario Workpaper (HTML/PDF)",
            "Formula & Statutory Authority Breakdown",
            "Summary CSV Export",
        ],
        full_features=[
            "Entity Tax Modeling",
            "Section 1031 Exchange Matching",
            "Section 179 Optimizer",
            "QSBS Stacking Analysis",
            "Multi-Row Sensitivity & Projection Schedules (CSV)",
            "Structured Statutory Data Pack (JSON)",
        ],
    )

    features = {
        "Entity Tax Modeling": FeatureContract(
            name="Entity Tax Modeling",
            enabled=True,
            tier_availability=["quick", "full", "partner_slot"],
            description="Comprehensive pass-through and C-corp entity tax scenario modeling.",
        ),
        "Section 1031 Exchange Matching": FeatureContract(
            name="Section 1031 Exchange Matching",
            enabled=True,
            tier_availability=["quick", "full", "partner_slot"],
            description="Section 1031 like-kind exchange identification and timeline tracking.",
        ),
        "Section 179 Optimizer": FeatureContract(
            name="Section 179 Optimizer",
            enabled=True,
            tier_availability=["free", "quick", "full", "partner_slot"],
            description="Asset depreciation and first-year expense deduction maximization.",
        ),
        "QSBS Stacking Analysis": FeatureContract(
            name="QSBS Stacking Analysis",
            enabled=True,
            tier_availability=["quick", "full", "partner_slot"],
            description="Section 1202 Qualified Small Business Stock tax exemption analysis.",
        ),
        "Multi-Entity Consolidation": FeatureContract(
            name="Multi-Entity Consolidation",
            enabled=True,
            tier_availability=["full", "partner_slot"],
            description="Multi-entity corporate structure tax consolidation and reporting.",
        ),
    }

    sec179_2025 = float(_tp_entry_value(pack, "section_179_cap_2025", 2500000.0))
    sec179_phase_2025 = float(_tp_entry_value(pack, "section_179_phaseout_2025", 4000000.0))
    sec179_2026 = float(_tp_entry_value(pack, "section_179_cap_2026", 2560000.0))
    sec179_phase_2026 = float(_tp_entry_value(pack, "section_179_phaseout_2026", 4090000.0))
    suv_2025 = float(_tp_entry_value(pack, "section_179_heavy_suv_cap_2025", 31300.0))
    suv_2026 = float(_tp_entry_value(pack, "section_179_heavy_suv_cap_2026", 32000.0))
    bonus_pct_2026 = float(_tp_entry_value(pack, "bonus_depreciation_pct_2026", 100.0))
    bonus_mult_2026 = bonus_pct_2026 / 100.0 if bonus_pct_2026 > 1.0 else bonus_pct_2026
    std_2026_s = float(_tp_entry_value(pack, "standard_deduction_2026_single", 16100.0))
    std_2026_m = float(_tp_entry_value(pack, "standard_deduction_2026_mfj", 32200.0))
    std_2026_h = float(_tp_entry_value(pack, "standard_deduction_2026_hoh", 24150.0))
    std_2027_s = float(_tp_entry_value(pack, "standard_deduction_2027_single", 16600.0))
    std_2027_m = float(_tp_entry_value(pack, "standard_deduction_2027_mfj", 33200.0))
    std_2027_h = float(_tp_entry_value(pack, "standard_deduction_2027_hoh", 24925.0))
    brackets_2026_s = _tp_entry_value(pack, "tax_brackets_2026_single", [12400, 50400, 105700, 201775, 256225, 640600])
    brackets_2027_s = _tp_entry_value(pack, "tax_brackets_2027_single", [12800, 52025, 109125, 208325, 264550, 661375])
    qsbs_ceiling = float(_tp_entry_value(pack, "qsbs_asset_ceiling_post_obbba", 75000000.0))
    qsbs_excl = float(_tp_entry_value(pack, "qsbs_exclusion_cap_post_obbba", 15000000.0))
    qsbs_tiers = _tp_entry_value(pack, "qsbs_holding_tiers", {"3_yr": 50, "4_yr": 75, "5_yr": 100})
    ret_401k_2026 = float(_tp_entry_value(pack, "retirement_401k_2026", 24500.0))
    oasdi_2026 = float(_tp_entry_value(pack, "oasdi_wage_base_2026", 184500.0))

    statutory = TenantStatutoryTruth(
        tenant_id="profithelm",
        regulator_name="Internal Revenue Service (IRS)",
        controlling_statute="26 U.S.C. 1(j), 168(k), 179, 1031, 1202 (P.L. 119-21 / IRS Rev. Proc. 2025-32 / 2026-35)",
        effective_tax_year="2026",
        statutory_citations={
            "public_law_119_21": "P.L. 119-21 (OBBBA)",
            "irs_rev_proc_2025_32": "IRS Rev. Proc. 2025-32",
            "irs_rev_proc_2026_35": "IRS Rev. Proc. 2026-35 / IR-2026-133",
            "irs_notice_2025_67": "IRS Notice 2025-67",
            "irs_rev_proc_2024_40": "IRS Rev Proc 2024-40",
            "irs_rev_proc_2023_34": "IRS Rev Proc 2023-34",
            "section_179": "IRC Section 179",
            "section_168k": "IRC Section 168(k) (P.L. 119-21 Sec. 70301)",
            "section_1202": "IRC Section 1202 (QSBS, P.L. 119-21 Sec. 70431)",
            "circular_230": "Treasury Department Circular No. 230",
            "section_1031": "IRC Section 1031",
        },
        limits_and_thresholds={
            "section_179_expense_limit_2024": 1220000.0,
            "section_179_expense_limit_2025": sec179_2025,
            "section_179_expense_limit_2026": sec179_2026,
            "section_179_phaseout_threshold_2024": 3050000.0,
            "section_179_phaseout_threshold_2025": sec179_phase_2025,
            "section_179_phaseout_threshold_2026": sec179_phase_2026,
            "section_179_heavy_vehicle_2024": 30500.0,
            "section_179_heavy_vehicle_2025": suv_2025,
            "section_179_heavy_vehicle_2026": suv_2026,
            "bonus_depreciation_pct_2026": bonus_mult_2026,
            "section_1202_qsbs_asset_ceiling": qsbs_ceiling,
            "section_1202_qsbs_exclusion_cap": qsbs_excl,
            "section_1202_qsbs_holding_tiers": dict(qsbs_tiers) if isinstance(qsbs_tiers, dict) else {"3_yr": 50, "4_yr": 75, "5_yr": 100},
            "section_1202_qsbs_legacy_pre_july_4_2025_asset_ceiling": 50000000.0,
            "section_1202_qsbs_legacy_pre_july_4_2025_exclusion_cap": 10000000.0,
            "section_1202_qsbs_exclusion_multiple": 10.0,
            "section_1202_qsbs_holding_period_years": 5,
            "retirement_401k_elective_deferral_2024": 23000.0,
            "retirement_401k_elective_deferral_2025": 23500.0,
            "retirement_401k_elective_deferral_2026": ret_401k_2026,
            "hsa_single_2024": 4150.0,
            "hsa_single_2025": 4300.0,
            "hsa_single_2026": 4400.0,
            "hsa_family_2024": 8300.0,
            "hsa_family_2025": 8550.0,
            "hsa_family_2026": 8750.0,
            "standard_deduction_2025_single": 15000.0,
            "standard_deduction_2025_mfj": 30000.0,
            "standard_deduction_2025_hoh": 22500.0,
            "standard_deduction_2026_single": std_2026_s,
            "standard_deduction_2026_mfj": std_2026_m,
            "standard_deduction_2026_hoh": std_2026_h,
            "tax_brackets_2026_single": brackets_2026_s,
            "standard_deduction_2027_single": std_2027_s,
            "standard_deduction_2027_mfj": std_2027_m,
            "standard_deduction_2027_hoh": std_2027_h,
            "standard_deduction_2027_obbba_single": std_2027_s,
            "standard_deduction_2027_obbba_mfj": std_2027_m,
            "standard_deduction_2027_obbba_hoh": std_2027_h,
            "tax_brackets_2027_single": brackets_2027_s,
            "standard_deduction_2027_repealed_sunset_single": 8600.0,
            "standard_deduction_2027_repealed_sunset_mfj": 17200.0,
            "standard_deduction_2027_repealed_sunset_hoh": 12900.0,
            "tcja_vs_sunset_single_125k_tcja_tax": 19181.0,
            "tcja_vs_sunset_single_125k_sunset_tax": 23530.0,
            "tcja_vs_sunset_single_125k_delta": 4349.0,
            "obbba_2026_single_125k_fed_tax": 18734.0,
            "obbba_2027_single_125k_fed_tax": 18389.50,
            "ca_sdi_rate_2026_pct": 1.3,
            "ca_top_marginal_rate_2026_pct": 14.6,
            "ssa_oasdi_wage_base_2025": 176100.0,
            "ssa_oasdi_wage_base_2026": oasdi_2026,
            "saas_runway_baseline_monthly_revenue": 33000.0,
            "saas_runway_baseline_monthly_burn": 45000.0,
            "saas_runway_baseline_net_monthly_burn": 12000.0,
            "scorp_155k_95k_salary_fica_savings": 7366.0,
            "scorp_220k_95k_salary_fica_savings": 14235.0,
            "section_301_tariff_120k_fob_landed_cost": 160966.0,
            "section_179_heavy_suv_85k_80pct_first_year_deduction": 68000.0,
        },
    )

    claims_allowlist = [
        "Entity Tax Modeling",
        "Section 1031 Exchange Matching",
        "Section 179 Optimizer",
        "QSBS Stacking Analysis",
        "Multi-Entity Consolidation",
    ]

    claims_banned = [
        "automated irs filing",
        "automated irs tax filing",
        "legal representation",
        "guaranteed tax audit immunity",
        "guaranteed tax shelter",
        "splash_financial",
        "sofi",
        "credible",
        "earnest",
        "lendkey",
    ]

    mandatory_disclosures = [
        "Circular 230 tax modeling disclaimer",
    ]

    cross_tenant_forbidden_tokens = {
        "title iv",
        "34 cfr",
        "pslf",
        "paye sunset",
        "student loan",
        "repayment assistance plan",
        "income-contingent repayment",
        "direct consolidation",
        "prexvo.com",
        "prexvo",
        "106482194",
        # Prexvo student loan refinance partner keys
        "splash_financial",
        "sofi",
        "credible",
        "earnest",
        "lendkey",
        # GainHelm cyber compliance & GRC isolation tokens
        "gainhelm.com",
        "gainhelm",
        "106482195",
        "gh_soc2_cmmc_audit_workpapers",
        "gh_hipaa_iso27001_governance_kit",
    }

    return TenantTruthProfile(
        tenant_id="profithelm",
        brand_name="ProfitHelm",
        canonical_domain="https://profithelm.com",
        pricing_tiers=pricing,
        features=features,
        statutory_truth=statutory,
        claims_allowlist=claims_allowlist,
        claims_banned=claims_banned,
        mandatory_disclosures=mandatory_disclosures,
        cross_tenant_forbidden_tokens=cross_tenant_forbidden_tokens,
    )


def _build_prexvo_profile() -> TenantTruthProfile:
    """Builds the canonical truth profile for Prexvo backed by TruthPack."""
    pack = _load_truth_pack_safe("prexvo")
    pricing = _build_canonical_pricing_tiers(
        audience_tier="consumer",
        free_features=["RAP vs IBR Modeling", "Tiered Standard Calculation", "ICR Repayment Modeling"],
        quick_features=[
            "Executive Borrower Worksheet (HTML/PDF)",
            "Amortization Formula & Title IV Compliance Notes",
            "Summary CSV Export",
        ],
        full_features=[
            "RAP vs IBR Modeling",
            "Tiered Standard Calculation",
            "PAYE Sunset Analysis",
            "ICR Repayment Modeling",
            "Multi-Period Amortization & APR Sensitivity Schedules (CSV)",
            "Structured Borrower Data Pack (JSON)",
        ],
    )

    features = {
        "RAP vs IBR Modeling": FeatureContract(
            name="RAP vs IBR Modeling",
            enabled=True,
            tier_availability=["free", "quick", "full", "partner_slot"],
            description="Repayment Assistance Plan vs Income-Based Repayment schedule comparison.",
        ),
        "Tiered Standard Calculation": FeatureContract(
            name="Tiered Standard Calculation",
            enabled=True,
            tier_availability=["free", "quick", "full", "partner_slot"],
            description="Tiered fixed repayment schedule calculation for direct loans.",
        ),
        "PAYE Sunset Analysis": FeatureContract(
            name="PAYE Sunset Analysis",
            enabled=True,
            tier_availability=["quick", "full", "partner_slot"],
            description="Analysis of Pay As You Earn plan phasing out pursuant to 34 CFR 685.209.",
        ),
        "ICR Repayment Modeling": FeatureContract(
            name="ICR Repayment Modeling",
            enabled=True,
            tier_availability=["free", "quick", "full", "partner_slot"],
            description="Income-Contingent Repayment plan calculation and discretionary income modeling.",
        ),
        "PSLF Buyback Estimator": FeatureContract(
            name="PSLF Buyback Estimator",
            enabled=True,
            tier_availability=["quick", "full", "partner_slot"],
            description="Public Service Loan Forgiveness buyback payment estimation under 34 CFR 685.219.",
        ),
    }

    fpl_2026 = float(_tp_entry_value(pack, "hhs_poverty_2026_1person", 15960.0))
    fpl_add_2026 = float(_tp_entry_value(pack, "hhs_poverty_2026_per_additional", 5680.0))
    rap_months = int(_tp_entry_value(pack, "rap_forgiveness_months", 360))
    rap_sub_pct = float(_tp_entry_value(pack, "rap_unpaid_interest_subsidy_pct", 100.0))
    rap_match = float(_tp_entry_value(pack, "rap_principal_match_monthly_cap", 50.0))
    pslf_payments = int(_tp_entry_value(pack, "pslf_qualifying_payments", 120))

    statutory = TenantStatutoryTruth(
        tenant_id="prexvo",
        regulator_name="U.S. Department of Education (Federal Student Aid)",
        controlling_statute="Title IV Higher Education Act; 34 CFR Part 685; P.L. 119-21 Section 82001; 91 FR 1797",
        effective_tax_year="2026",
        statutory_citations={
            "title_iv": "Title IV Higher Education Act",
            "34_cfr_685": "34 CFR Part 685",
            "paye_regulations": "34 CFR 685.209",
            "pslf_regulations": "34 CFR 685.219",
            "rap_statute": "P.L. 119-21 Section 82001 (360-Month RAP Forgiveness)",
            "hhs_poverty_2026": "91 FR 1797 (2026 HHS Poverty Guidelines)",
        },
        limits_and_thresholds={
            "rap_discretionary_percentage": 0.10,
            "rap_poverty_guideline_threshold": 2.25,
            "rap_forgiveness_months": rap_months,
            "rap_unpaid_interest_subsidy_pct": rap_sub_pct,
            "ibr_pre_2014_percentage": 0.15,
            "ibr_post_2014_percentage": 0.10,
            "ibr_poverty_guideline_threshold": 1.50,
            "pslf_qualifying_payments": pslf_payments,
            "poverty_guidelines": {
                2024: {"individual": 15060.0, "additional_person": 5380.0},
                2025: {"individual": 15650.0, "additional_person": 5440.0},
                2026: {"individual": fpl_2026, "additional_person": fpl_add_2026},
            },
            "poverty_guidelines_2026_hhs_contiguous": fpl_2026,
            "poverty_guidelines_2026_hhs_per_additional": fpl_add_2026,
            "rap_exemption_2026_single_contiguous": round(fpl_2026 * 2.25, 2),
            "ibr_exemption_2026_single_contiguous": round(fpl_2026 * 1.50, 2),
            "icr_exemption_2026_single_contiguous": fpl_2026,
            "icr_poverty_guideline_threshold": 1.00,
            "grad_plus_unsubsidized_annual_cap": 20500.00,
            "grad_plus_unsubsidized_aggregate_cap": 138500.00,
            "rap_default_60k_loan_65k_agi_monthly": 248.23,
            "rap_default_60k_loan_65k_agi_rounded_monthly": 248.0,
            "rap_default_60k_loan_65k_agi_subsidy": 76.77,
            "rap_default_60k_loan_95k_agi_monthly": 498.23,
            "ibr_new_default_60k_loan_65k_agi_monthly": 346.04,
            "ibr_legacy_default_60k_loan_65k_agi_monthly": 519.06,
            "std_10yr_60k_6pct8_monthly": 681.29,
            "tiered_std_60k_6pct8_monthly": 379.24,
            "tiered_std_delta_60k_monthly": 302.05,
            "tiered_std_25k_monthly": 168.40,
            "parent_plus_std_10yr_70k_monthly": 822.50,
            "parent_plus_icr_70k_90k_agi_monthly": 651.25,
            "parent_plus_icr_savings_monthly": 171.25,
            "parent_plus_rap_ineligible_monthly": 325.00,
            "mfs_joint_rap_165k_agi_monthly": 989.15,
            "mfs_separate_rap_85k_agi_monthly": 306.56,
            "mfs_joint_ibr_165k_agi_monthly": 847.50,
            "mfs_separate_ibr_85k_agi_monthly": 540.94,
            "mfs_joint_vs_ibr_delta_monthly": 141.65,
            "save_vs_standard_60k_monthly": 1105.73,
            "save_interest_accrual_monthly": 273.23,
            "save_forbearance_accrual_monthly": 666.67,
            "ibr_post2014_45k_loan_65k_agi_monthly": 179.38,
            "ibr_pre2014_45k_loan_65k_agi_monthly": 270.83,
            "ibr_std_cap_45k_loan_monthly": 335.25,
            "paye_45k_loan_60k_agi_monthly": 97.81,
            "paye_75k_loan_85k_agi_monthly": 430.42,
            "paye_75k_loan_85k_agi_rounded_monthly": 430.00,
            "paye_pre2014_75k_loan_85k_agi_monthly": 645.63,
            "paye_std_cap_75k_loan_monthly": 766.25,
            "pslf_rap_55k_agi_monthly": 124.11,
            "pslf_ibr_55k_agi_monthly": 223.23,
            "pslf_monthly_accrual_55k_monthly": 284.17,
            "pslf_subsidy_55k_monthly": 60.94,
            "rap_85k_agi_monthly": 410.84,
            "rap_85k_agi_rounded_monthly": 411.00,
            "ibr_pre2014_85k_agi_monthly": 738.06,
            "ibr_pre2014_85k_agi_rounded_monthly": 738.00,
            "std_10yr_65k_loan_monthly": 636.39,
            "rap_45k_agi_monthly": 44.90,
            "rap_50k_agi_monthly": 82.50,
            "rap_55k_agi_monthly": 164.90,
            "refi_break_even_monthly_savings": 82.50,
            "rap_principal_match_monthly": rap_match,
            "rap_minimum_payment_monthly": 10.0,
        },
    )

    claims_allowlist = [
        "RAP vs IBR Modeling",
        "Tiered Standard Calculation",
        "PAYE Sunset Analysis",
        "ICR Repayment Modeling",
        "PSLF Buyback Estimator",
    ]

    claims_banned = [
        "official federal loan servicer",
        "direct federal student loan consolidation processing",
        "guaranteed debt cancellation",
        "guaranteed debt forgiveness",
        "guaranteed loan forgiveness",
        "b2b corporate tax",
        "1031 exchange",
        "section 179",
        "section 1031",
        "mercury",
        "turbotax",
        "coinledger",
        "crest_capital",
    ]

    mandatory_disclosures = [
        "Refinancing federal student loans permanently waives federal protections",
        "FTC Partner Compensation Disclosure",
        "Independent Publisher Disclaimer",
    ]

    cross_tenant_forbidden_tokens = {
        "section 1031",
        "1031 exchange",
        "exchange 1031",
        "exchange1031",
        "section 179",
        "qsbs",
        "section 1202",
        "corporate tax",
        "pass-through entity",
        "tcja",
        "profithelm.com",
        "profithelm",
        "143884102",
        # ProfitHelm B2B affiliate partner keys
        "coinledger",
        "koinly",
        "mercury",
        "ramp",
        "rho",
        "gusto",
        "rippling",
        "crest_capital",
        "ipx1031",
        "exeter1031",
        "first_american",
        "turbotax",
        "taxslayer",
        "kalshi",
        "interactive_brokers",
        # GainHelm cyber compliance & GRC isolation tokens
        "gainhelm.com",
        "gainhelm",
        "106482195",
        "gh_soc2_cmmc_audit_workpapers",
        "gh_hipaa_iso27001_governance_kit",
    }

    return TenantTruthProfile(
        tenant_id="prexvo",
        brand_name="Prexvo",
        canonical_domain="https://prexvo.com",
        pricing_tiers=pricing,
        features=features,
        statutory_truth=statutory,
        claims_allowlist=claims_allowlist,
        claims_banned=claims_banned,
        mandatory_disclosures=mandatory_disclosures,
        cross_tenant_forbidden_tokens=cross_tenant_forbidden_tokens,
    )


def _build_gainhelm_profile() -> TenantTruthProfile:
    """Builds the canonical truth profile for GainHelm backed by TruthPack."""
    pack = _load_truth_pack_safe("gainhelm")
    pricing = _build_canonical_pricing_tiers(
        audience_tier="business",
        free_features=[
            "SOC 2 Audit Cost & CPA Scoping",
            "DoD CMMC 2.0 & NIST 800-171 SPRS Scoring",
            "HHS OCR HIPAA Penalty Tier Modeling",
        ],
        quick_features=[
            "Executive Compliance Scoping Worksheet (HTML/PDF)",
            "Methodology & Statutory Authority Breakdown",
            "Summary CSV Export",
        ],
        full_features=[
            "SOC 2 Audit Cost & CPA Scoping",
            "DoD CMMC 2.0 & NIST 800-171 SPRS Scoring",
            "ISO 27001 Auditor-Day Calculation",
            "HHS OCR HIPAA Penalty Tier Modeling",
            "PCI DSS 4.0 QSA & ROC Scoping",
            "Multi-Phase Readiness Schedule & Data Pack (CSV/JSON)",
        ],
    )

    features = {
        "SOC 2 Audit Cost & CPA Scoping": FeatureContract(
            name="SOC 2 Audit Cost & CPA Scoping",
            enabled=True,
            tier_availability=["free", "quick", "full", "partner_slot"],
            description="AICPA SSAE 18 (AT-C Section 205) Trust Services Criteria Type I and Type II CPA audit cost and readiness modeling.",
        ),
        "DoD CMMC 2.0 & NIST 800-171 SPRS Scoring": FeatureContract(
            name="DoD CMMC 2.0 & NIST 800-171 SPRS Scoring",
            enabled=True,
            tier_availability=["free", "quick", "full", "partner_slot"],
            description="32 CFR Part 170 and DFARS 252.204-7012 / 7019 / 7020 NIST SP 800-171 Rev 2 110-control SPRS score and C3PAO budget modeling.",
        ),
        "ISO 27001 Auditor-Day Calculation": FeatureContract(
            name="ISO 27001 Auditor-Day Calculation",
            enabled=True,
            tier_availability=["quick", "full", "partner_slot"],
            description="ISO/IEC 27006-1:2024 mandatory Stage 1, Stage 2, and 3-year surveillance auditor-day calculation for ISO/IEC 27001:2022 ISMS.",
        ),
        "HHS OCR HIPAA Penalty Tier Modeling": FeatureContract(
            name="HHS OCR HIPAA Penalty Tier Modeling",
            enabled=True,
            tier_availability=["free", "quick", "full", "partner_slot"],
            description="45 CFR 160.404 and 42 U.S.C. 1320d-5 inflation-adjusted 4-Tier civil money penalty exposure and HITECH breach notification cost modeling.",
        ),
        "PCI DSS 4.0 QSA & ROC Scoping": FeatureContract(
            name="PCI DSS 4.0 QSA & ROC Scoping",
            enabled=True,
            tier_availability=["quick", "full", "partner_slot"],
            description="PCI SSC PCI DSS v4.0.1 Merchant Level 1-4 SAQ vs QSA Report on Compliance (ROC) and ASV scan cost modeling.",
        ),
    }

    hipaa_t4_2026 = float(_tp_entry_value(pack, "hipaa_tier4_annual_cap_2026", 2190294.0))
    sprs_max = int(_tp_entry_value(pack, "sprs_max_score", 110))
    sprs_min = int(_tp_entry_value(pack, "sprs_min_score", -203))
    sprs_ded = int(_tp_entry_value(pack, "sprs_max_deduction", 313))
    sprs_counts = _tp_entry_value(pack, "sprs_control_counts", {"5_pt": 44, "3_pt": 14, "1_pt": 51, "0_pt": 1})
    bls_hourly = float(_tp_entry_value(pack, "bls_infosec_hourly_loaded_2026", 121.67))

    statutory = TenantStatutoryTruth(
        tenant_id="gainhelm",
        regulator_name="AICPA Auditing Standards Board, DoD CIO, and HHS OCR",
        controlling_statute="AICPA SSAE 18; 32 CFR Part 170; NIST SP 800-171; 45 CFR 160.404 (91 FR 3665 / 91 FR 66566)",
        effective_tax_year="2026",
        statutory_citations={
            "aicpa_ssae_18_atc_205": "AICPA SSAE 18 (AT-C Section 205) & TSP Section 100",
            "dod_32_cfr_part_170": "32 CFR Part 170 (DoD CMMC 2.0 Final Rule)",
            "dfars_252_204_7012": "DFARS 252.204-7012 / 252.204-7019 / 252.204-7020",
            "nist_sp_800_171_rev2": "NIST SP 800-171 Rev 2 (110 Security Requirements)",
            "iso_iec_27006_1_2024": "ISO/IEC 27006-1:2024 & ISO/IEC 27001:2022",
            "hipaa_45_cfr_160_404": "45 CFR 160.404 & 42 U.S.C. 1320d-5 (91 FR 3665 / 91 FR 66566)",
            "pci_dss_v4_0_1": "PCI DSS v4.0.1 Merchant & Service Provider Scoping",
            "fedramp_44_usc_3607": "44 U.S.C. 3607 (FedRAMP Authorization Act) & NIST SP 800-53 Rev 5",
            "gdpr_art_83_eu_ai_act_art_99": "GDPR Article 83 (EU 2016/679) & EU AI Act Article 99 (EU 2024/1689)",
        },
        limits_and_thresholds={
            "sprs_max_score": sprs_max,
            "sprs_min_score": sprs_min,
            "sprs_max_deduction": sprs_ded,
            "sprs_control_counts": dict(sprs_counts) if isinstance(sprs_counts, dict) else {"5_pt": 44, "3_pt": 14, "1_pt": 51, "0_pt": 1},
            "sprs_total_controls": 110,
            "cmmc_conditional_min_sprs": 88,
            "cmmc_poam_closeout_days": 180,
            "hipaa_tier1_min_per_violation": 141.0,
            "hipaa_tier2_min_per_violation": 1424.0,
            "hipaa_tier3_min_per_violation": 13795.0,
            "hipaa_tier4_min_per_violation": 71162.0,
            "hipaa_tier4_annual_cap_2026": hipaa_t4_2026,
            "hipaa_statutory_annual_cap_tier4": hipaa_t4_2026,
            "hipaa_ocr_enforcement_discretion_tier1_cap": 25000.0,
            "hipaa_ocr_enforcement_discretion_tier2_cap": 100000.0,
            "hipaa_ocr_enforcement_discretion_tier3_cap": 250000.0,
            "hipaa_ocr_enforcement_discretion_tier4_cap": 1500000.0,
            "hipaa_ocr_breach_portal_threshold_records": 500,
            "hipaa_breach_notification_deadline_days": 60,
            "pci_level1_visa_mastercard_tx_threshold": 6000000,
            "pci_level2_min_tx_threshold": 1000000,
            "pci_level3_min_tx_threshold": 20000,
            "gdpr_tier1_fine_cap_eur": 10000000.0,
            "gdpr_tier1_turnover_pct": 0.02,
            "gdpr_tier2_fine_cap_eur": 20000000.0,
            "gdpr_tier2_turnover_pct": 0.04,
            "eu_ai_act_prohibited_fine_cap_eur": 35000000.0,
            "eu_ai_act_prohibited_turnover_pct": 0.07,
            "eu_ai_act_high_risk_fine_cap_eur": 15000000.0,
            "eu_ai_act_high_risk_turnover_pct": 0.03,
            "sec_form_8k_item_1_05_disclosure_business_days": 4,
            "bls_soc_15_1212_median_annual_wage": 120360.0,
            "bls_soc_15_1212_mean_hourly_loaded_rate": bls_hourly,
            "soc2_baseline_type2_75emp_total_cost": 78100.40,
            "cmmc_level2_baseline_75emp_total_cost": 134534.6,
            "cmmc_level2_baseline_85emp_total_cost": 134534.6,
            "iso27001_baseline_75emp_total_cost": 66350.6,
            "iso27001_baseline_120emp_3yr_tco": 66350.6,
            "hipaa_baseline_1500rec_total_exposure": 2577794.0,
            "pci_dss_baseline_level1_total_cost": 93400.6,
            "fedramp_moderate_baseline_total_cost": 500000.0,
            "hitrust_i1_baseline_total_cost": 115000.0,
            "pentest_baseline_total_cost": 23300.0,
            "cyber_insurance_baseline_total_cost": 40900.0,
        },
    )

    claims_allowlist = [
        "SOC 2 Audit Cost & CPA Scoping",
        "DoD CMMC 2.0 & NIST 800-171 SPRS Scoring",
        "ISO 27001 Auditor-Day Calculation",
        "HHS OCR HIPAA Penalty Tier Modeling",
        "PCI DSS 4.0 QSA & ROC Scoping",
    ]

    claims_banned = [
        "official aicpa licensed cpa firm",
        "accredited c3pao certification body",
        "guaranteed audit pass without remediation",
        "guaranteed immunity from hhs ocr enforcement",
        "official federal loan servicer",
        "automated irs tax filing",
        "section 1031",
        "section 179",
        "splash_financial",
        "sofi",
        "credible",
        "earnest",
        "lendkey",
        "mercury",
        "turbotax",
        "coinledger",
        "crest_capital",
    ]

    mandatory_disclosures = [
        "Statutory Compliance & Audit Scoping Disclaimer (Non-CPA / Non-C3PAO / Non-Legal Attestation)",
        "FTC Partner Compensation Disclosure",
        "Independent Publisher Disclaimer",
    ]

    cross_tenant_forbidden_tokens = {
        "section 1031",
        "1031 exchange",
        "exchange 1031",
        "exchange1031",
        "section 179",
        "qsbs",
        "section 1202",
        "pass-through entity",
        "tcja",
        "profithelm.com",
        "profithelm",
        "143884102",
        "coinledger",
        "koinly",
        "mercury",
        "gusto",
        "rippling",
        "crest_capital",
        "ipx1031",
        "exeter1031",
        "first_american",
        "turbotax",
        "taxslayer",
        "kalshi",
        "interactive_brokers",
        "title iv",
        "34 cfr",
        "pslf",
        "paye sunset",
        "student loan",
        "repayment assistance plan",
        "income-contingent repayment",
        "direct consolidation",
        "prexvo.com",
        "prexvo",
        "106482194",
        "splash_financial",
        "sofi",
        "credible",
        "earnest",
        "lendkey",
    }

    return TenantTruthProfile(
        tenant_id="gainhelm",
        brand_name="GainHelm",
        canonical_domain="https://gainhelm.com",
        pricing_tiers=pricing,
        features=features,
        statutory_truth=statutory,
        claims_allowlist=claims_allowlist,
        claims_banned=claims_banned,
        mandatory_disclosures=mandatory_disclosures,
        cross_tenant_forbidden_tokens=cross_tenant_forbidden_tokens,
    )


def _build_lienbond_profile() -> TenantTruthProfile:
    """Builds the canonical truth profile for LienBond (lienbond.com) backed by TruthPack."""
    pack = _load_truth_pack_safe("lienbond")
    pricing = _build_canonical_pricing_tiers(
        audience_tier="business",
        free_features=[
            "50-State Mechanics Lien Deadline Matrix",
            "Contractor License & Miller Act Bond Premium Calculators",
            "Workers Comp Class Code & EMR Rate Calculator",
        ],
        quick_features=[
            "Executive Contractor Compliance Worksheet (HTML/PDF)",
            "Surety, EMR & State Statutory Deadline Breakdown",
            "Summary CSV Export",
        ],
        full_features=[
            "50-State Statutory Lien Waiver & Preliminary Notice Packet",
            "Contractor Surety Bond & Underwriting Readiness Dossier",
            "NCCI Workers Comp Experience Modification Rate (EMR) Audit Worksheet",
            "Federal Miller Act (40 U.S.C. 3131) Sliding-Scale Bond Schedule",
            "DOL Form WH-347 Davis-Bacon Certified Payroll & Fringe Benefit Packet",
            "Multi-Tier Sensitivity Schedule & Structured Data Pack (CSV/JSON)",
        ],
    )

    features = {
        "50-State Mechanics Lien Deadline Matrix": FeatureContract(
            name="50-State Mechanics Lien Deadline Matrix",
            enabled=True,
            tier_availability=["free", "quick", "full", "partner_slot"],
            description="Statutory preliminary notice, mechanics lien recording, and enforcement deadline calculation under Cal. Civ. Code 8132-8416, Tex. Prop. Code Ch. 53, Fla. Stat. Ch. 713, and N.Y. Lien Law.",
        ),
        "Contractor Surety Bond & Underwriting Readiness Dossier": FeatureContract(
            name="Contractor Surety Bond & Underwriting Readiness Dossier",
            enabled=True,
            tier_availability=["free", "quick", "full", "partner_slot"],
            description="Federal Miller Act (40 U.S.C. 3131), state Little Miller Act, and CSLB contractor license surety bond premium and working-capital capacity modeling.",
        ),
        "NCCI Workers Comp Experience Modification Rate (EMR) Audit Worksheet": FeatureContract(
            name="NCCI Workers Comp Experience Modification Rate (EMR) Audit Worksheet",
            enabled=True,
            tier_availability=["free", "quick", "full", "partner_slot"],
            description="NCCI Basic Manual and state rating bureau trade class code (5403, 5183, 5190, 5551) manual premium and Experience Modification Rate (EMR) split-point calculation.",
        ),
        "DOL Form WH-347 Davis-Bacon Certified Payroll & Fringe Benefit Packet": FeatureContract(
            name="DOL Form WH-347 Davis-Bacon Certified Payroll & Fringe Benefit Packet",
            enabled=True,
            tier_availability=["quick", "full", "partner_slot"],
            description="40 U.S.C. 3141 Davis-Bacon Act and 29 CFR Part 5 prevailing wage, annualized bona fide fringe credit, and WH-347 statement of compliance preparation.",
        ),
    }

    miller_threshold = float(_tp_entry_value(pack, "miller_act_threshold_usd", 150000.0))
    miller_alt_min = float(_tp_entry_value(pack, "miller_act_alt_protection_min_usd", 35000.0))
    bid_bond_range = _tp_entry_value(pack, "bid_bond_penal_sum_pct_range", [5.0, 20.0])
    lic_bond_range = _tp_entry_value(pack, "contractor_license_bond_rate_range_pct", [0.75, 10.0])
    ncci_manual = str(_tp_entry_value(pack, "ncci_workers_comp_emr", "NCCI Experience Rating Plan Manual / Basic Manual"))
    davis_bacon = str(_tp_entry_value(pack, "davis_bacon_wh347", "40 U.S.C. 3141 / 29 CFR 5.5"))

    statutory = TenantStatutoryTruth(
        tenant_id="lienbond",
        regulator_name="U.S. Department of Labor (WHD), U.S. Treasury Circular 570, and State Contractors Boards",
        controlling_statute="40 U.S.C. 3131 (Miller Act); FAR 28.101; 40 U.S.C. 3141; NCCI Experience Rating Plan",
        effective_tax_year="2026",
        statutory_citations={
            "federal_miller_act_40_usc_3131": "40 U.S.C. 3131-3134 (Federal Miller Act) & FAR 28.102-1",
            "far_28_101_bid_bond": "FAR 28.101 (Bid Bond Penal Sum 5%-20%)",
            "davis_bacon_act_40_usc_3141": f"{davis_bacon} (Davis-Bacon Act & WH-347)",
            "erisa_sec_412_29_usc_1112": "29 U.S.C. 1112 (ERISA Section 412) & 29 CFR 2580.412",
            "prompt_payment_act_31_usc_3902": "31 U.S.C. 3902 (Federal Prompt Payment Act) & State Retainage Statutes",
            "ca_mechanics_lien_civ_code_8132_8416": "Cal. Civ. Code Sections 8132-8138, 8200-8216 & 8412-8416",
            "tx_mechanics_lien_prop_code_53": "Tex. Prop. Code Sections 53.052, 53.056, 53.101 & 53.284",
            "fl_construction_lien_stat_713": "Fla. Stat. Sections 713.06, 713.08 & 713.20",
            "ncci_experience_rating_plan": ncci_manual,
        },
        limits_and_thresholds={
            "miller_act_federal_bond_threshold_usd": miller_threshold,
            "miller_act_alternative_payment_protection_min_usd": miller_alt_min,
            "bid_bond_penal_sum_pct_range": list(bid_bond_range) if isinstance(bid_bond_range, (list, tuple)) else [5.0, 20.0],
            "contractor_license_bond_rate_range_pct": list(lic_bond_range) if isinstance(lic_bond_range, (list, tuple)) else [0.75, 10.0],
            "erisa_fidelity_bond_statutory_rate_pct": 10.0,
            "erisa_fidelity_bond_min_floor_usd": 1000.0,
            "erisa_fidelity_bond_standard_cap_usd": 500000.0,
            "erisa_fidelity_bond_employer_securities_cap_usd": 1000000.0,
            "ca_preliminary_notice_window_days": 20,
            "ca_direct_contractor_lien_window_with_noc_days": 60,
            "ca_subcontractor_lien_window_with_noc_days": 30,
            "ca_lien_window_without_noc_days": 90,
            "ca_lien_foreclosure_action_deadline_days": 90,
            "fl_notice_to_owner_window_days": 45,
            "fl_claim_of_lien_window_days": 90,
            "cslb_ca_contractor_license_bond_amount_usd": 25000.0,
        },
    )

    claims_allowlist = [
        "50-State Mechanics Lien Deadline Matrix",
        "Contractor Surety Bond & Underwriting Readiness Dossier",
        "NCCI Workers Comp Experience Modification Rate (EMR) Audit Worksheet",
        "DOL Form WH-347 Davis-Bacon Certified Payroll & Fringe Benefit Packet",
    ]

    claims_banned = [
        "licensed surety underwriter",
        "admitted treasury circular 570 surety carrier",
        "guaranteed mechanics lien foreclosure recovery",
        "formal legal representation",
        "official federal loan servicer",
        "automated irs tax filing",
        "splash_financial",
        "sofi",
        "credible",
        "earnest",
        "lendkey",
        "vanta_security",
        "drata_compliance",
        "sprinto_compliance",
        "thoropass_audit",
    ]

    mandatory_disclosures = [
        "Statutory Surety, Workers Comp & Construction Lien Disclaimer (Non-Attorney / Non-Licensed Producer Modeling Notice)",
        "FTC Partner Compensation Disclosure",
        "Independent Publisher Disclaimer",
    ]

    cross_tenant_forbidden_tokens = {
        "title iv",
        "34 cfr",
        "pslf",
        "paye sunset",
        "student loan",
        "repayment assistance plan",
        "income-contingent repayment",
        "direct consolidation",
        "prexvo.com",
        "prexvo",
        "106482194",
        "splash_financial",
        "sofi",
        "credible",
        "earnest",
        "lendkey",
        "section 1031",
        "1031 exchange",
        "qsbs",
        "section 1202",
        "profithelm.com",
        "profithelm",
        "143884102",
        "coinledger",
        "koinly",
        "turbotax",
        "taxslayer",
        "kalshi",
        "gainhelm.com",
        "gainhelm",
        "106482195",
        "vanta_security",
        "drata_compliance",
        "sprinto_compliance",
        "thoropass_audit",
    }

    return TenantTruthProfile(
        tenant_id="lienbond",
        brand_name="LienBond",
        canonical_domain="https://lienbond.com",
        pricing_tiers=pricing,
        features=features,
        statutory_truth=statutory,
        claims_allowlist=claims_allowlist,
        claims_banned=claims_banned,
        mandatory_disclosures=mandatory_disclosures,
        cross_tenant_forbidden_tokens=cross_tenant_forbidden_tokens,
    )


STAGED_RESERVE_TENANT_DOMAINS: Tuple[str, ...] = ()
DECOMMISSIONED_TENANT_DOMAINS: Tuple[str, ...] = (
    "adspendguardian.com",
    "heyjunto.com",
    "thecoachloop.com",
    "viraljacker.com",
)
PERSONAL_INFRASTRUCTURE_DOMAINS: Tuple[str, ...] = ("arifcoskun.com",)

CLOUDFLARE_ACCOUNT_ID = "8789c54bef2d281d4a8afb4df34f9878"

# Ground-truth Cloudflare Registrar & Zone state attested against
# GET /api/v4/accounts/8789c54bef2d281d4a8afb4df34f9878/registrar/domains/<domain>
CLOUDFLARE_PORTFOLIO_REGISTRAR_LEDGER: Dict[str, Dict[str, Any]] = {
    "profithelm.com": {
        "domain": "profithelm.com",
        "lifecycle_tier": "ACTIVE_TENANT",
        "zone_id": "e0d591326d8e26365edd7867453b604f",
        "registry_object_id": "3029249825_DOMAIN_COM-VRSN",
        "auto_renew": True,
        "locked": True,
        "privacy": True,
        "privacy_mode": "redaction",
        "registry_statuses": "clienttransferprohibited",
        "registered_at": "2025-10-15T10:09:50.367Z",
        "expires_at": "2027-10-15T10:09:50.000Z",
        "payment_expires_at": "2027-10-15T10:09:50.000Z",
        "renewal_fee_usd": 10.46,
        "effective_annual_exposure_usd": 10.46,
        "expected_cname_target": "profithelm.pages.dev",
        "routing_records_allowed": True,
    },
    "prexvo.com": {
        "domain": "prexvo.com",
        "lifecycle_tier": "ACTIVE_TENANT",
        "zone_id": "fdc412697a55e721ddd3ec7d9070daff",
        "registry_object_id": "3058043791_DOMAIN_COM-VRSN",
        "auto_renew": True,
        "locked": True,
        "privacy": True,
        "privacy_mode": "redaction",
        "registry_statuses": "clienttransferprohibited",
        "registered_at": "2026-01-15T21:50:58.513Z",
        "expires_at": "2027-01-15T21:50:58.000Z",
        "payment_expires_at": "2027-01-15T21:50:58.000Z",
        "renewal_fee_usd": 10.46,
        "effective_annual_exposure_usd": 10.46,
        "expected_cname_target": "prexvo.pages.dev",
        "routing_records_allowed": True,
    },
    "gainhelm.com": {
        "domain": "gainhelm.com",
        "lifecycle_tier": "ACTIVE_TENANT",
        "zone_id": "0a03264e19beb2cb17ba01860b701701",
        "registry_object_id": "3041507860_DOMAIN_COM-VRSN",
        "auto_renew": True,
        "locked": True,
        "privacy": True,
        "privacy_mode": "redaction",
        "registry_statuses": "clienttransferprohibited",
        "registered_at": "2025-11-24T00:24:57.459Z",
        "expires_at": "2026-11-24T00:24:57.000Z",
        "payment_expires_at": "2026-11-24T00:24:57.000Z",
        "renewal_fee_usd": 10.46,
        "effective_annual_exposure_usd": 10.46,
        "expected_cname_target": "gainhelm.pages.dev",
        "routing_records_allowed": True,
    },
    "lienbond.com": {
        "domain": "lienbond.com",
        "lifecycle_tier": "ACTIVE_TENANT",
        "zone_id": "47b340339ead09422ed5f28fabe85c4f",
        "registry_object_id": "3165046006_DOMAIN_COM-VRSN",
        "auto_renew": True,
        "locked": True,
        "privacy": True,
        "privacy_mode": "redaction",
        "registry_statuses": "clienttransferprohibited",
        "registered_at": "2026-11-08T00:46:27.000Z",
        "expires_at": "2027-11-08T00:46:27.000Z",
        "payment_expires_at": "2027-11-08T00:46:27.000Z",
        "renewal_fee_usd": 10.46,
        "effective_annual_exposure_usd": 10.46,
        "expected_cname_target": "lienbond.pages.dev",
        "routing_records_allowed": True,
    },
    ("arif" + "coskun.com"): {
        "domain": "arif" + "coskun.com",
        "lifecycle_tier": "PERSONAL_INFRA",
        "zone_id": "23c4be6bf04fcde33b938b8f94907457",
        "registry_object_id": "3132685184_DOMAIN_COM-VRSN",
        "auto_renew": True,
        "locked": True,
        "privacy": True,
        "privacy_mode": "redaction",
        "registry_statuses": "clienttransferprohibited",
        "registered_at": "2026-08-16T00:52:34.325Z",
        "expires_at": "2027-08-16T00:52:34.000Z",
        "payment_expires_at": "2027-08-16T00:52:34.000Z",
        "renewal_fee_usd": 10.46,
        "effective_annual_exposure_usd": 10.46,
        "expected_cname_target": "arif" + "-coskun-platform.pages.dev",
        "routing_records_allowed": True,
    },
    "adspendguardian.com": {
        "domain": "adspendguardian.com",
        "lifecycle_tier": "DECOMMISSIONED",
        "zone_id": "f1191fa18536b4620154ddfa9bc22243",
        "registry_object_id": "3054432776_DOMAIN_COM-VRSN",
        "auto_renew": False,
        "locked": True,
        "privacy": True,
        "privacy_mode": "redaction",
        "registry_statuses": "clienttransferprohibited",
        "registered_at": "2026-01-05T08:53:47.788Z",
        "expires_at": "2027-01-05T08:53:47.000Z",
        "payment_expires_at": "2027-01-05T08:53:47.000Z",
        "renewal_fee_usd": 10.46,
        "effective_annual_exposure_usd": 0.0,
        "expected_cname_target": None,
        "routing_records_allowed": False,
    },
    "heyjunto.com": {
        "domain": "heyjunto.com",
        "lifecycle_tier": "DECOMMISSIONED",
        "zone_id": "29e937133a62c4c27dba08eae5e2ab98",
        "registry_object_id": "3059710310_DOMAIN_COM-VRSN",
        "auto_renew": False,
        "locked": True,
        "privacy": True,
        "privacy_mode": "redaction",
        "registry_statuses": "clienttransferprohibited",
        "registered_at": "2026-01-21T11:08:31.886Z",
        "expires_at": "2027-01-21T11:08:31.000Z",
        "payment_expires_at": "2027-01-21T11:08:31.000Z",
        "renewal_fee_usd": 10.46,
        "effective_annual_exposure_usd": 0.0,
        "expected_cname_target": None,
        "routing_records_allowed": False,
    },
    "thecoachloop.com": {
        "domain": "thecoachloop.com",
        "lifecycle_tier": "DECOMMISSIONED",
        "zone_id": "208830e96c6fec20b0191675ead01282",
        "registry_object_id": "3073188198_DOMAIN_COM-VRSN",
        "auto_renew": False,
        "locked": True,
        "privacy": True,
        "privacy_mode": "redaction",
        "registry_statuses": "clienttransferprohibited",
        "registered_at": "2026-03-02T23:38:14.875Z",
        "expires_at": "2027-03-02T23:38:14.000Z",
        "payment_expires_at": "2027-03-02T23:38:14.000Z",
        "renewal_fee_usd": 10.46,
        "effective_annual_exposure_usd": 0.0,
        "expected_cname_target": None,
        "routing_records_allowed": False,
    },
    "viraljacker.com": {
        "domain": "viraljacker.com",
        "lifecycle_tier": "DECOMMISSIONED",
        "zone_id": "709c55b44b3eeffde93dfa268b2ebf28",
        "registry_object_id": "3109302661_DOMAIN_COM-VRSN",
        "auto_renew": False,
        "locked": True,
        "privacy": True,
        "privacy_mode": "redaction",
        "registry_statuses": "clienttransferprohibited",
        "registered_at": "2026-06-09T21:59:18.991Z",
        "expires_at": "2027-06-09T21:59:18.000Z",
        "payment_expires_at": "2027-06-09T21:59:18.000Z",
        "renewal_fee_usd": 10.46,
        "effective_annual_exposure_usd": 0.0,
        "expected_cname_target": None,
        "routing_records_allowed": False,
    },
}


def compute_registrar_ledger_sha256(
    ledger: Optional[Dict[str, Dict[str, Any]]] = None,
) -> str:
    """Computes deterministic SHA-256 digest of the canonical portfolio Registrar ledger."""
    target = ledger if ledger is not None else CLOUDFLARE_PORTFOLIO_REGISTRAR_LEDGER
    canonical = json.dumps(target, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


CLOUDFLARE_REGISTRAR_ATTESTATION_SHA256: str = compute_registrar_ledger_sha256()


@dataclass(frozen=True)
class DeclarativeTenantContract:
    """
    Single declarative registration contract for a pseofactory tenant property.
    All downstream discovery, qualification, syndication, video synthesis,
    indexing velocity, GSC remediation, and maintenance loops derive their
    per-tenant wiring and statutory/entity metadata from this contract.
    Zero em-dashes. Zero en-dashes.
    """

    property_id: str
    repo_dir_name: str
    domain: str
    canonical_base: str = ""
    brand_name: str = ""
    package_name: str = ""
    dist_dir: str = "dist"
    repo_root: str = ""
    runner_work_dist_dir: str = ""
    env_prefix: str = ""
    linkedin_company_id: str = ""
    cloudflare_zone_id: str = ""
    cloudflare_pages_cname_target: str = ""
    truth_profile: Optional[TenantTruthProfile] = None
    statutory_truth: Optional[StatutoryTruthRule] = None
    entity_type: str = ""
    research_entity: str = ""
    legal_entity: str = ""
    publisher_entity_label: str = ""
    editorial_classification: str = ""
    primary_statutory_authority: str = ""
    economic_dataset_label: str = ""
    llms_manifest_title: str = ""
    llms_statutory_summary_block: str = ""
    home_topic_label: str = ""
    tools_directory_topic_label: str = ""
    fallback_calculator_title: str = ""
    default_calculator_fallback_title: str = ""
    default_heading_fallback_label: str = ""
    default_query_syntax_template: str = ""
    statutory_intent_tokens: Tuple[str, ...] = ()
    own_boundary_tokens: Tuple[str, ...] = ()
    cross_tenant_own_markers: Tuple[str, ...] = ()
    category_seed_taxonomy: Dict[str, Any] = field(default_factory=dict)
    default_core_tools: Tuple[Dict[str, Any], ...] = ()
    cannibalization_clone_map: Dict[str, Dict[str, str]] = field(default_factory=dict)
    cannibalizing_clone_consolidation_map: Dict[str, Dict[str, str]] = field(default_factory=dict)
    flagship_anchor_slugs: Tuple[str, ...] = ()
    video_branding: Dict[str, Any] = field(default_factory=dict)
    default_cpc_usd: float = 10.5
    default_erpm_usd: float = 85.0
    default_sample_query: str = ""
    default_sample_slug: str = ""
    top_modifier_fallback: str = "(2026 Rules)"
    top_modifier_family: str = ""
    vertical_paren_modifier: str = "Statutory Guide"
    default_smoke_probe: Dict[str, str] = field(default_factory=dict)
    smoke_probe_query: str = ""
    smoke_foreign_query: str = ""
    priority_hub_slugs: Tuple[str, ...] = ()
    default_complementary_peers: Tuple[Tuple[str, str], ...] = ()
    primary_fallback_manifest_slug: str = ""
    primary_partner_key: str = ""
    primary_partner_name: str = ""
    primary_partner_url: str = ""
    primary_partner_cta: str = ""
    tools_directory_seed_section_html: str = ""
    audience_tier: str = "business"

    def __post_init__(self) -> None:
        eff_tier = str(self.audience_tier or "business").strip().lower()
        if eff_tier not in ("consumer", "business"):
            eff_tier = "business"
        if self.repo_root:
            try:
                marker_path = Path(self.repo_root) / ".pseofactory.json"
                if marker_path.is_file():
                    marker_data = json.loads(marker_path.read_text(encoding="utf-8"))
                    if isinstance(marker_data, dict):
                        marker_tier = str(marker_data.get("audience_tier") or "").strip().lower()
                        if marker_tier in ("consumer", "business"):
                            eff_tier = marker_tier
            except Exception:
                pass
        object.__setattr__(self, "audience_tier", eff_tier)
        if not self.canonical_base and self.domain:
            object.__setattr__(self, "canonical_base", f"https://{self.domain}")
        if not self.package_name and self.property_id:
            object.__setattr__(self, "package_name", self.property_id)
        if not self.brand_name and self.property_id:
            object.__setattr__(self, "brand_name", self.property_id.capitalize())
        if self.cannibalizing_clone_consolidation_map and not self.cannibalization_clone_map:
            object.__setattr__(
                self,
                "cannibalization_clone_map",
                dict(self.cannibalizing_clone_consolidation_map),
            )
        elif self.cannibalization_clone_map and not self.cannibalizing_clone_consolidation_map:
            object.__setattr__(
                self,
                "cannibalizing_clone_consolidation_map",
                self.cannibalization_clone_map,
            )
        if self.default_calculator_fallback_title and not self.fallback_calculator_title:
            object.__setattr__(self, "fallback_calculator_title", self.default_calculator_fallback_title)
        elif self.fallback_calculator_title and not self.default_calculator_fallback_title:
            object.__setattr__(self, "default_calculator_fallback_title", self.fallback_calculator_title)
        if self.cross_tenant_own_markers and not self.own_boundary_tokens:
            object.__setattr__(self, "own_boundary_tokens", tuple(self.cross_tenant_own_markers))
        if (self.smoke_probe_query or self.smoke_foreign_query) and not self.default_smoke_probe:
            object.__setattr__(
                self,
                "default_smoke_probe",
                {
                    "query": self.smoke_probe_query or f"{self.property_id} calculator",
                    "foreign_query": self.smoke_foreign_query,
                },
            )
        if self.truth_profile is None:
            eff_stat = self.statutory_truth or TenantStatutoryTruth(tenant_id=self.property_id)
            synth_profile = TenantTruthProfile(
                tenant_id=self.property_id,
                brand_name=self.brand_name,
                canonical_domain=self.canonical_base,
                pricing_tiers={},
                features={},
                statutory_truth=eff_stat,
                claims_allowlist=[],
                claims_banned=[],
                mandatory_disclosures=[],
                cross_tenant_forbidden_tokens=set(),
            )
            object.__setattr__(self, "truth_profile", synth_profile)

    @property
    def repo_root_path(self) -> Path:
        if self.repo_root:
            return Path(self.repo_root)
        return Path(f"/home/ubuntuadmin/projects/{self.repo_dir_name or self.property_id}")

    def to_tenant_config_dict(self) -> Dict[str, str]:
        return {
            "property_id": self.property_id,
            "repo_dir_name": self.repo_dir_name,
            "domain": self.domain,
            "canonical_base": self.canonical_base,
            "brand_name": self.brand_name,
            "package_name": self.package_name,
            "dist_dir": self.dist_dir,
            "linkedin_company_id": self.linkedin_company_id,
            "audience_tier": self.audience_tier,
        }


TenantRegistrationContract = DeclarativeTenantContract


def _build_canonical_tenant_declarations() -> Dict[str, DeclarativeTenantContract]:
    return {
        "profithelm": DeclarativeTenantContract(
            property_id="profithelm",
            repo_dir_name="profithelm-platform",
            domain="profithelm.com",
            canonical_base="https://profithelm.com",
            brand_name="ProfitHelm",
            package_name="profithelm",
            dist_dir="dist",
            repo_root="/home/ubuntuadmin/projects/profithelm-platform",
            runner_work_dist_dir="/home/ubuntuadmin/.local/share/actions-runner/profithelm-platform/_work/profithelm-platform/profithelm-platform/dist",
            env_prefix="PROFITHELM",
            linkedin_company_id="143884102",
            cloudflare_zone_id="e0d591326d8e26365edd7867453b604f",
            cloudflare_pages_cname_target="profithelm.pages.dev",
            truth_profile=_build_profithelm_profile(),
            research_entity="ProfitHelm Quantitative Research",
            legal_entity="ProfitHelm LLC",
            publisher_entity_label="ProfitHelm LLC",
            editorial_classification="Deterministic B2B Corporate Tax, Section 179 Depreciation, Section 1031 Exchange & Treasury Modeling Engine",
            primary_statutory_authority="IRC Section 1(j); IRC Section 179; IRC Section 1031",
            economic_dataset_label="IRS SOI Tax Statistics and Federal Reserve Macroeconomic Series",
            llms_manifest_title="ProfitHelm: Complete Machine Knowledge Base & Statutory Calculation Manifest",
            llms_statutory_summary_block=(
                "## Key Statutory Authorities\n"
                "- OBBBA (P.L. 119-21) & IRS Rev. Proc. 2025-32 / 2026-35: Permanently extends the 10%-37% federal marginal tax brackets (repealing the 39.6% sunset) with Single standard deductions of $16,100 (2026) and $16,600 (2027) under IRC Section 1(j).\n"
                "- Section 179 & 168(k): Maximum deduction cap $2,560,000 ($4,090,000 phase-out), $32,000 Heavy SUV cap (2026), and 100% permanent bonus depreciation under P.L. 119-21.\n"
                "- Section 1031: 45-day replacement identification and 180-day closing deadlines under 26 U.S.C. Section 1031.\n"
                "- GAAP ASC 205-40: Going-concern cash runway forecasting benchmarked to monthly net burn and liquid reserves.\n"
            ),
            home_topic_label="Statutory Tax, Depreciation & Corporate Treasury Calculators",
            tools_directory_topic_label="Statutory Financial Calculators and Decision Tools",
            fallback_calculator_title="Statutory Tax and Financial Model Calculator",
            default_heading_fallback_label="Statutory Tax Calculator",
            default_query_syntax_template="?income={income}&status={status}",
            statutory_intent_tokens=(
                "section 1031",
                "1031 exchange",
                "exchange 1031",
                "like-kind exchange",
                "like kind exchange",
                "section 179",
                "bonus depreciation",
                "section 168",
                "macrs",
                "tcja",
                "commercial clean energy 179d",
                "commercial clean energy",
                "clean energy 179d",
                "cost segregation",
                "capital gains tax",
                "tax bracket",
                "tax brackets",
                "tcja sunset",
                "saas runway",
                "runway calculator",
                "burn rate",
                "prediction market tax",
                "section 1256",
                "1256 contract",
                "section 1202",
                "qsbs",
                "section 174",
                "r&d tax",
                "corporate amt",
                "camt",
                "section 199a",
                "199a",
                "s-corp payroll",
                "niit",
                "crypto tax",
                "treasury yield",
                "financial simulation",
                "1031 boot",
                "1031",
                "179 deduction",
                "vehicle depreciation",
                "irs vehicle",
                "section 301",
                "tariff",
                "tax deduction",
                "tax deductions",
                "capital gains",
                "r&d tax credit",
            ),
            own_boundary_tokens=(
                "profithelm",
                "profithelm.com",
                "143884102",
                "d089d8b3-753e-46dc-9c12-653de16f710d",
                "101906407",
                "section 1031",
                "1031 exchange",
                "section 179",
                "tcja",
            ),
            category_seed_taxonomy={
                "b2b_corporate_tax_and_depreciation": [
                    "section 179 depreciation",
                    "section 174 r&d amortization",
                    "section 199a qbi deduction",
                    "corporate amt camt",
                    "qsbs section 1202 exclusion",
                ],
                "trade_tariffs_and_landed_cost": [
                    "section 301 import tariff",
                    "cbp customs bond",
                    "merchandise processing fee",
                ],
                "entity_payroll_and_commercial_finance": [
                    "s corp vs llc reasonable salary",
                    "commercial invoice factoring",
                    "workers comp class code rate",
                ],
            },
            default_core_tools=(
                {"slug": "irs-tax-brackets", "primary_keyword": "irs tax brackets"},
                {"slug": "crypto-tax-calculator", "primary_keyword": "crypto tax calculator"},
                {"slug": "saas-runway-calculator", "primary_keyword": "saas runway calculator"},
                {"slug": "section-179-calculator", "primary_keyword": "section 179 calculator"},
                {"slug": "tcja-sunset-capital-gains", "primary_keyword": "tcja sunset capital gains"},
                {"slug": "treasury-yield-calculator", "primary_keyword": "treasury yield calculator"},
                {"slug": "section-1031-calculator", "primary_keyword": "section 1031 calculator"},
                {"slug": "capital-gains-calculator", "primary_keyword": "capital gains tax calculator"},
            ),
            flagship_anchor_slugs=(
                "section-179-calculator",
                "irs-tax-brackets",
                "section-1031-calculator",
                "quarterly-estimated-tax-penalty-calculator",
                "commercial-heavy-vehicle-section-179-weight-calculator",
                "macrs-depreciation-calculator",
            ),
            video_branding={
                "brand_name": "ProfitHelm",
                "domain": "profithelm.com",
                "canonical_base": "https://profithelm.com",
                "badge_text": "PROFITHELM.COM | IRC STATUTORY ENGINE",
                "verification_pill": "2026 STATUTORY VERIFIED",
                "bg_rgb": (15, 23, 42),
                "card_rgb": (30, 41, 59),
                "accent_rgb": (16, 185, 129),
                "accent_hex": "#10b981",
                "voice": "en-US-ChristopherNeural",
            },
            default_cpc_usd=10.5,
            default_erpm_usd=85.0,
            default_sample_query="ca tax brackets 2027",
            default_sample_slug="irs-tax-brackets",
            top_modifier_fallback="(2026 Brackets)",
            vertical_paren_modifier="IRC Guide",
            default_smoke_probe={
                "query": "section 179 deduction calculator",
                "foreign_query": "save plan student loan repayment calculator",
            },
            priority_hub_slugs=(
                "irs-tax-brackets",
                "crypto-tax-calculator",
            ),
            default_complementary_peers=(
                ("irs-tax-brackets", "Federal Tax Bracket & Marginal Rate Calculator"),
                ("section-179-calculator", "Section 179 Equipment Depreciation Calculator"),
                ("section-1031-calculator", "Section 1031 Real Estate Exchange Calculator"),
            ),
            primary_fallback_manifest_slug="tax-bracket-capital-allocation-hub",
            primary_partner_key="mercury",
            primary_partner_name="Mercury Business Banking",
            primary_partner_url="https://mercury.com/r/profithelm-llc",
            primary_partner_cta="Open a Mercury Account",
            tools_directory_seed_section_html=(
                '\n      <section class="affiliate-section affiliates-section" data-mechanic="compliant_intent_monetization">\n'
                '        <h2>Verified Commercial Execution Partners</h2>\n'
                '        <div class="affiliate-card partner-card"><a href="/r/xendoo" target="_blank" rel="noopener sponsored nofollow">Xendoo</a></div>\n'
                '      </section>\n    '
            ),
        ),
        "prexvo": DeclarativeTenantContract(
            property_id="prexvo",
            audience_tier="consumer",
            repo_dir_name="prexvo",
            domain="prexvo.com",
            canonical_base="https://prexvo.com",
            brand_name="Prexvo",
            package_name="prexvo",
            dist_dir="dist",
            repo_root="/home/ubuntuadmin/projects/prexvo",
            runner_work_dist_dir="/home/ubuntuadmin/.local/share/actions-runner/prexvo/_work/prexvo/prexvo/dist",
            env_prefix="PREXVO",
            linkedin_company_id="106482194",
            cloudflare_zone_id="fdc412697a55e721ddd3ec7d9070daff",
            cloudflare_pages_cname_target="prexvo.pages.dev",
            truth_profile=_build_prexvo_profile(),
            research_entity="Prexvo Statutory Research Group",
            legal_entity="Prexvo LLC",
            publisher_entity_label="Prexvo Statutory Research Group",
            editorial_classification="Deterministic Title IV Federal Student Loan & Private Refinance Decision Engine",
            primary_statutory_authority="Title IV of the Higher Education Act; 34 CFR Part 685",
            economic_dataset_label="Federal Student Aid Portfolio Summary and HHS Poverty Guidelines",
            llms_manifest_title="Prexvo: Complete Machine Knowledge Base & Title IV Statutory Manifest",
            llms_statutory_summary_block=(
                "## Title IV Statutory Parameter Specifications & Formula Definitions\n"
                "- Repayment Assistance Plan (RAP): Governed by P.L. 119-21 Section 82001. Discretionary income calculated at 225% of 2026 HHS Poverty Guidelines ($15,960 single + $5,680 per additional person under 91 FR 1797). Statutory rate is 10% of discretionary income, 100% unpaid interest subsidy, up to $50/month principal match, and 360-month (30-year) forgiveness.\n"
                "- Income-Based Repayment (IBR): Discretionary income calculated at 150% of HHS Poverty Guidelines under 34 CFR 685.221. Rate is 15% for pre-July 2014 borrowers (25-year forgiveness) and 10% for new borrowers (20-year forgiveness), capped at the 10-year standard payment amount.\n"
                "- Pay As You Earn (PAYE): Governed by 34 CFR 685.209. 150% poverty exemption, 10% discretionary income rate, 20-year forgiveness horizon, capped at 10-year standard repayment payment.\n"
                "- Income-Contingent Repayment (ICR): Governed by 34 CFR 685.209(b). Lesser of: 20% discretionary income over 100% poverty line, or 12-year income-adjusted payment formula. Sole direct IDR option for consolidated Parent PLUS loans.\n"
                "- Tiered Standard Repayment: Governed by 34 CFR 685.208. Fixed amortization terms based on total debt: $7,500-$9,999 (12 years), $10,000-$19,999 (15 years), $20,000-$39,999 (20 years), $40,000-$59,999 (25 years), $60,000+ (30 years).\n"
                "- PSLF Buyback (34 CFR 685.219(g)): Allows borrowers with 120 months of qualifying public service employment to buy back eligible months of deferment or forbearance at the lower historical IDR payment amount.\n"
            ),
            home_topic_label="Federal Student Loan Repayment, PSLF & Title IV Decision Engine",
            tools_directory_topic_label="Statutory Financial Calculators and Decision Tools",
            fallback_calculator_title="Title IV Student Loan Repayment Calculator",
            default_heading_fallback_label="Title IV Repayment Calculator",
            default_query_syntax_template="?agi={agi}&debt={debt}&family={size}&status={status}",
            statutory_intent_tokens=(
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
                "forgiveness tax bomb",
                "ibr tax bomb",
                "ibr payment",
                "ibr repayment",
                "ibr calculator",
                "vs ibr",
                "ibr vs",
                "parent plus",
                "section 108f",
                "public service loan forgiveness",
                "partial financial hardship",
                "income driven repayment",
                "income-driven repayment",
                "loan payment calculator student",
                "fafsa",
                "pell grant",
                "federal student aid",
                "idr",
            ),
            own_boundary_tokens=(
                "prexvo",
                "prexvo.com",
                "106482194",
                "79393cd8-e7dd-49af-a934-f8515d299b19",
                "101927178",
                "title iv",
                "34 cfr",
                "pslf",
                "paye sunset",
                "student loan",
                "repayment assistance plan",
                "income-contingent repayment",
                "direct consolidation",
            ),
            category_seed_taxonomy={
                "title_iv_student_loan_repayment": [
                    "student loan save plan forbearance",
                    "pslf buyback months",
                    "ibr vs rap student loan",
                    "parent plus double consolidation",
                ],
                "student_loan_tax_and_default_relief": [
                    "student loan forgiveness tax bomb",
                    "student loan wage garnishment",
                    "sai fafsa pell grant",
                ],
            },
            default_core_tools=(
                {"slug": "rap-vs-ibr-calculator", "primary_keyword": "rap vs ibr calculator"},
                {"slug": "tiered-standard-calculator", "primary_keyword": "tiered standard calculator"},
                {"slug": "paye-sunset-calculator", "primary_keyword": "paye sunset calculator"},
                {"slug": "icr-repayment-calculator", "primary_keyword": "icr repayment calculator"},
                {"slug": "pslf-qualifying-payment-simulator", "primary_keyword": "pslf qualifying payment simulator"},
                {"slug": "grad-plus-borrowing-cap-calculator", "primary_keyword": "grad plus borrowing cap calculator"},
                {"slug": "ibr-hardship-cap-calculator", "primary_keyword": "ibr hardship cap calculator"},
                {"slug": "married-filing-separately-student-loan-calculator", "primary_keyword": "married filing separately student loan calculator"},
                {"slug": "parent-plus-double-consolidation", "primary_keyword": "parent plus double consolidation"},
                {"slug": "rap-payment-calculator", "primary_keyword": "rap payment calculator"},
                {"slug": "save-plan-litigation-transition", "primary_keyword": "save plan litigation transition"},
                {"slug": "student-loan-refinance-break-even-calculator", "primary_keyword": "student loan refinance break even calculator"},
            ),
            cannibalization_clone_map={
                "pslf-buyback-calculator": {
                    "canonical_slug": "pslf-qualifying-payment-simulator",
                    "redirect_target": "/tools/pslf-qualifying-payment-simulator/",
                },
                "repayment-assistance-plan-calculator": {
                    "canonical_slug": "rap-payment-calculator",
                    "redirect_target": "/tools/rap-payment-calculator/",
                },
                "student-loan-interest-subsidy-calculator": {
                    "canonical_slug": "save-plan-litigation-transition",
                    "redirect_target": "/tools/save-plan-litigation-transition/",
                },
                "tax-deduction-for-car-loan-interest": {
                    "canonical_slug": "student-loan-repayment-calculator",
                    "redirect_target": "/tools/",
                },
            },
            flagship_anchor_slugs=(
                "student-loan-rap-calculator",
                "rap-vs-ibr-calculator",
                "pslf-qualifying-payment-simulator",
                "save-to-rap-migration-calculator",
                "married-filing-separately-student-loan-calculator",
                "parent-plus-double-consolidation",
            ),
            video_branding={
                "brand_name": "Prexvo",
                "domain": "prexvo.com",
                "canonical_base": "https://prexvo.com",
                "badge_text": "PREXVO.COM | TITLE IV STATUTORY ENGINE",
                "verification_pill": "34 CFR PART 685 VERIFIED",
                "bg_rgb": (15, 23, 42),
                "card_rgb": (30, 41, 59),
                "accent_rgb": (56, 189, 248),
                "accent_hex": "#38bdf8",
                "voice": "en-US-ChristopherNeural",
            },
            default_cpc_usd=8.0,
            default_erpm_usd=75.0,
            default_sample_query="rap calculator",
            default_sample_slug="rap-payment-calculator",
            top_modifier_fallback="(2026 RAP vs IBR)",
            vertical_paren_modifier="IDR & RAP",
            default_smoke_probe={
                "query": "save plan student loan repayment calculator",
                "foreign_query": "soc 2 type ii audit cost calculator",
            },
            priority_hub_slugs=(),
            default_complementary_peers=(
                ("student-loan-repayment-calculator", "Title IV Student Loan Repayment Calculator"),
                ("rap-vs-ibr-calculator", "RAP vs IBR Repayment Comparison Calculator"),
                ("pslf-buyback-calculator", "PSLF Buyback Settlement Calculator"),
            ),
            primary_fallback_manifest_slug="rap-payment-calculator",
            primary_partner_key="splash_financial",
            primary_partner_name="Splash Financial Student Loan Refinancing",
            primary_partner_url="https://www.splashfinancial.com/",
            primary_partner_cta="Compare Rates with Splash Financial",
            tools_directory_seed_section_html="",
        ),
        "gainhelm": DeclarativeTenantContract(
            property_id="gainhelm",
            repo_dir_name="gainhelm",
            domain="gainhelm.com",
            canonical_base="https://gainhelm.com",
            brand_name="GainHelm",
            package_name="gainhelm",
            dist_dir="dist",
            repo_root="/home/ubuntuadmin/projects/gainhelm",
            runner_work_dist_dir="/home/ubuntuadmin/.local/share/actions-runner/gainhelm/_work/gainhelm/gainhelm/dist",
            env_prefix="GAINHELM",
            linkedin_company_id="106482195",
            cloudflare_zone_id="0a03264e19beb2cb17ba01860b701701",
            cloudflare_pages_cname_target="gainhelm.pages.dev",
            truth_profile=_build_gainhelm_profile(),
            research_entity="GainHelm Cyber Compliance & Audit Economics Research",
            legal_entity="GainHelm LLC",
            publisher_entity_label="GainHelm Cyber Compliance & Audit Economics Research",
            editorial_classification="Deterministic Enterprise Cyber Compliance, GRC Audit Cost & Statutory Security Governance Engine",
            primary_statutory_authority="AICPA SSAE 18 (AT-C Section 205); 32 CFR Part 170 (CMMC 2.0); 45 CFR 160.404",
            economic_dataset_label="AICPA Assurance Services Benchmarks, DoD 32 CFR Part 170 Cost Tables, and HHS OCR Breach Archive",
            llms_manifest_title="GainHelm: Complete Machine Knowledge Base & Cyber Compliance Statutory Manifest",
            llms_statutory_summary_block=(
                "## Key Cyber Compliance & Audit Statutory Authorities\n"
                "- SOC 2 Type I & Type II: Governed by AICPA SSAE 18 (AT-C Section 205) and 2017 Trust Services Criteria (TSP Section 100).\n"
                "- CMMC 2.0 & NIST SP 800-171: Governed by 32 CFR Part 170, DFARS 252.204-7012 / 7019 / 7020 / 7021, and DoD SPRS scoring [-203 to +110] with 88-point conditional POA&M floor.\n"
                "- ISO/IEC 27001:2022: Governed by ISO/IEC 27006-1:2024 mandatory Stage 1 and Stage 2 auditor-day tables and 93 Annex A controls.\n"
                "- HIPAA & HITECH Civil Monetary Penalties: Governed by 45 CFR 160.404 and 42 U.S.C. 1320d-5 four-tier culpability schedules and 500-record media notification triggers.\n"
                "- FedRAMP & PCI DSS v4.0.1: Governed by 44 U.S.C. 3607 (NIST SP 800-53 Rev 5 3PAO baselines) and PCI DSS v4.0.1 Merchant Levels 1-4 QSA ROC standards.\n"
            ),
            home_topic_label="Enterprise Cyber Compliance, GRC Audit Cost & Statutory Security Governance Calculators",
            tools_directory_topic_label="Enterprise Cyber Compliance and GRC Audit Cost Calculators",
            fallback_calculator_title="Enterprise Cyber Compliance and GRC Audit Cost Calculator",
            default_heading_fallback_label="Enterprise Compliance Calculator",
            default_query_syntax_template="?headcount={headcount}&extra_criteria={extra_criteria}",
            statutory_intent_tokens=(
                "ssae 18",
                "soc 2 audit",
                "soc 2 type",
                "soc 2 compliance",
                "cmmc 2.0",
                "c3pao",
                "32 cfr part 170",
                "nist 800-171",
                "sprs score",
                "iso 27001",
                "iso 27006",
                "45 cfr 160.404",
                "hipaa violation penalty",
                "hitrust certification",
                "fedramp authorization",
                "pci dss 4.0",
                "penetration testing cost",
                "cyber liability insurance",
                "soc 2",
                "soc2",
                "cmmc",
                "nist 800 171",
                "sprs",
                "fedramp",
                "hipaa compliance",
                "pci dss",
            ),
            own_boundary_tokens=(
                "gainhelm",
                "gainhelm.com",
                "106482195",
                "252d3e3c-d342-48fc-8359-eb3700e68b1f",
                "101927180",
                "vanta_security",
                "drata_compliance",
                "sprinto_compliance",
                "thoropass_audit",
                "coalition_cyber_insurance",
                "cobalt_pentest",
                "gh_soc2_cmmc_audit_workpapers",
                "gh_hipaa_iso27001_governance_kit",
            ),
            category_seed_taxonomy={
                "enterprise_grc_and_cyber_compliance": [
                    "soc 2 type 2 audit",
                    "cmmc level 2 c3pao",
                    "nist 800 171 sprs score",
                    "iso 27001 certification",
                    "hipaa compliance penalty",
                    "pci dss 4.0 assessment",
                ],
            },
            default_core_tools=(
                {"slug": "soc-2-audit-cost-calculator", "primary_keyword": "soc 2 audit cost calculator"},
                {"slug": "cmmc-2-0-compliance-cost-calculator", "primary_keyword": "cmmc 2.0 compliance cost calculator"},
                {"slug": "nist-800-171-sprs-score-calculator", "primary_keyword": "nist 800-171 sprs score calculator"},
                {"slug": "iso-27001-certification-cost-calculator", "primary_keyword": "iso 27001 certification cost calculator"},
                {"slug": "hipaa-violation-penalty-breach-cost-calculator", "primary_keyword": "hipaa violation penalty breach cost calculator"},
                {"slug": "penetration-testing-scoping-cost-calculator", "primary_keyword": "penetration testing scoping cost calculator"},
                {"slug": "cyber-liability-insurance-breach-exposure-calculator", "primary_keyword": "cyber liability insurance breach exposure calculator"},
                {"slug": "fedramp-authorization-3pao-cost-calculator", "primary_keyword": "fedramp authorization 3pao cost calculator"},
                {"slug": "pci-dss-4-0-compliance-cost-calculator", "primary_keyword": "pci dss 4.0 compliance cost calculator"},
                {"slug": "hitrust-csf-e1-i1-r2-certification-cost-calculator", "primary_keyword": "hitrust csf e1 i1 r2 certification cost calculator"},
            ),
            cannibalization_clone_map={
                "cmmc-level-2-audit-cost-calculator": {
                    "canonical_slug": "cmmc-2-0-compliance-cost-calculator",
                    "redirect_target": "/tools/cmmc-2-0-compliance-cost-calculator/",
                },
                "penetration-testing-cost-estimator": {
                    "canonical_slug": "penetration-testing-scoping-cost-calculator",
                    "redirect_target": "/tools/penetration-testing-scoping-cost-calculator/",
                },
                "cyber-liability-insurance-premium-calculator": {
                    "canonical_slug": "cyber-liability-insurance-breach-exposure-calculator",
                    "redirect_target": "/tools/cyber-liability-insurance-breach-exposure-calculator/",
                },
                "fedramp-authorization-cost-calculator": {
                    "canonical_slug": "fedramp-authorization-3pao-cost-calculator",
                    "redirect_target": "/tools/fedramp-authorization-3pao-cost-calculator/",
                },
                "pci-dss-4-0-compliance-audit-cost-calculator": {
                    "canonical_slug": "pci-dss-4-0-compliance-cost-calculator",
                    "redirect_target": "/tools/pci-dss-4-0-compliance-cost-calculator/",
                },
                "hitrust-certification-cost-roi-calculator": {
                    "canonical_slug": "hitrust-csf-e1-i1-r2-certification-cost-calculator",
                    "redirect_target": "/tools/hitrust-csf-e1-i1-r2-certification-cost-calculator/",
                },
            },
            flagship_anchor_slugs=(
                "soc-2-compliance-cost-calculator",
                "iso-27001-certification-cost-calculator",
                "cmmc-2-0-compliance-cost-calculator",
            ),
            video_branding={
                "brand_name": "GainHelm",
                "domain": "gainhelm.com",
                "canonical_base": "https://gainhelm.com",
                "badge_text": "GAINHELM.COM | GRC AUDIT ENGINE",
                "verification_pill": "AICPA & NIST VERIFIED",
                "bg_rgb": (15, 23, 42),
                "card_rgb": (30, 41, 59),
                "accent_rgb": (99, 102, 241),
                "accent_hex": "#6366f1",
                "voice": "en-US-ChristopherNeural",
            },
            default_cpc_usd=14.5,
            default_erpm_usd=95.0,
            default_sample_query="soc 2 audit cost calculator",
            default_sample_slug="soc-2-audit-cost-calculator",
            top_modifier_fallback="(GRC Audit)",
            vertical_paren_modifier="GRC Audit",
            default_smoke_probe={
                "query": "soc 2 type ii audit cost calculator",
                "foreign_query": "section 179 deduction calculator",
            },
            priority_hub_slugs=(
                "soc-2-audit-cost-calculator",
                "cmmc-2-0-compliance-cost-calculator",
            ),
            default_complementary_peers=(
                ("soc-2-audit-cost-calculator", "SOC 2 Audit Cost & GRC Automation Calculator"),
                ("cmmc-2-0-compliance-cost-calculator", "CMMC 2.0 Level 2 Compliance Cost Calculator"),
                ("nist-800-171-sprs-score-calculator", "NIST 800-171 DoD SPRS Score Calculator"),
            ),
            primary_fallback_manifest_slug="soc-2-audit-cost-calculator",
            primary_partner_key="vanta_security",
            primary_partner_name="Vanta Automated SOC 2, ISO 27001 & HIPAA Compliance",
            primary_partner_url="https://www.vanta.com/",
            primary_partner_cta="Automate Audit Readiness with Vanta",
            tools_directory_seed_section_html="",
        ),
    }


CANONICAL_TENANT_DECLARATIONS: Dict[str, DeclarativeTenantContract] = _build_canonical_tenant_declarations()
CANONICAL_TENANT_REGISTRY: Dict[str, DeclarativeTenantContract] = CANONICAL_TENANT_DECLARATIONS

LIENBOND_TENANT_CONTRACT: DeclarativeTenantContract = DeclarativeTenantContract(
    property_id="lienbond",
    repo_dir_name="lienbond",
    domain="lienbond.com",
    canonical_base="https://lienbond.com",
    brand_name="LienBond",
    package_name="lienbond",
    dist_dir="dist",
    repo_root="/home/ubuntuadmin/projects/lienbond",
    runner_work_dist_dir="/home/ubuntuadmin/.local/share/actions-runner/lienbond/_work/lienbond/lienbond/dist",
    env_prefix="LIENBOND",
    linkedin_company_id="",
    cloudflare_zone_id="47b340339ead09422ed5f28fabe85c4f",
    cloudflare_pages_cname_target="lienbond.pages.dev",
    truth_profile=_build_lienbond_profile(),
    research_entity="LienBond Statutory Surety & Construction Compliance Research",
    legal_entity="LienBond LLC",
    publisher_entity_label="LienBond Statutory Surety & Construction Compliance Research",
    editorial_classification="Deterministic Construction Surety Bond, Workers Compensation EMR, 50-State Mechanics Lien & Davis-Bacon Prevailing Wage Engine",
    primary_statutory_authority="40 U.S.C. 3131 (Miller Act); 40 U.S.C. 3141 (Davis-Bacon Act); Cal. Civ. Code 8132-8416; Tex. Prop. Code Ch. 53; NCCI Experience Rating Plan",
    economic_dataset_label="NCCI Workers Compensation Class Rate Benchmarks, Surety Association Sliding-Scale Schedules & 50-State Mechanics Lien Statutory Tables",
    llms_manifest_title="LienBond: Complete Machine Knowledge Base & Statutory Surety/Lien Calculation Manifest",
    llms_statutory_summary_block=(
        "## Statutory Surety, Workers Comp & Construction Lien Authorities\n"
        "- Federal Miller Act (40 U.S.C. 3131-3134 & FAR 28.102): Requires 100% performance and payment bonds on federal construction contracts exceeding $150,000.\n"
        "- NCCI Workers Compensation & EMR Formula: Manual_Premium = (Annual_Payroll / 100) * State_Class_Rate; Net_Premium = Manual_Premium * EMR_Factor * (1 - Schedule_Credit).\n"
        "- 50-State Mechanics Lien & Preliminary Notice Deadlines: Governed by Cal. Civ. Code 8202/8412/8414 (20-day preliminary notice, 30/60/90-day recording), Tex. Prop. Code 53.052/53.056 (15th day of 2nd/3rd month notice), and Fla. Stat. 713.06/713.08 (45-day Notice to Owner, 90-day Claim of Lien).\n"
        "- Davis-Bacon Prevailing Wage (40 U.S.C. 3141 & 29 CFR Part 5): Overtime_Hourly_Pay = (Base_Prevailing_Rate * 1.5) + max(0, Required_Fringe_Rate - Annualized_Bona_Fide_Benefit_Credit).\n"
        "- ERISA Section 412 Fidelity Bond (29 U.S.C. 1112): Required_Bond = clamp(Plan_Assets * 0.10, $1,000, $500,000 or $1,000,000 with employer securities).\n"
    ),
    home_topic_label="Contractor Surety Bonds, Workers Comp EMR & 50-State Mechanics Lien Calculators",
    tools_directory_topic_label="Statutory Construction Surety, Workers Comp & Mechanics Lien Calculators",
    fallback_calculator_title="Statutory Surety Bond, Workers Comp & Mechanics Lien Calculator",
    default_heading_fallback_label="Statutory Surety & Lien Calculator",
    default_query_syntax_template="?contract={contract}&state={state}",
    statutory_intent_tokens=(
        "surety bond",
        "license bond",
        "performance bond",
        "payment bond",
        "miller act",
        "bid bond",
        "workers comp",
        "workers compensation",
        "class code",
        "ncci emr",
        "emr factor",
        "emr impact",
        "emr rate",
        "experience modification",
        "erisa fidelity",
        "fidelity bond",
        "mechanics lien",
        "contractor lien",
        "preliminary notice",
        "lien waiver",
        "lien release",
        "retainage",
        "prompt payment act",
        "davis bacon",
        "prevailing wage",
        "wh-347",
        "contractor markup",
        "notice to owner",
        "workers compensation payroll",
        "contractor license bond",
    ),
    own_boundary_tokens=(
        "lienbond",
        "lienbond.com",
        "47b340339ead09422ed5f28fabe85c4f",
        "5ce463de-dd46-4356-871d-e6d1214b5d57",
        "101927181",
        "thimble_contractor",
        "jobber_field_service",
        "levelset_lien_filing",
        "lb_surety_lien_wh347_packet",
        "lb_workers_comp_emr_audit_packet",
    ),
    category_seed_taxonomy={
        "surety_bonds_and_underwriting": [
            "contractor license bond cost calculator by credit score",
            "miller act performance and payment bond premium calculator",
            "bid bond to performance bond capacity calculator",
            "erisa fidelity bond coverage amount calculator",
        ],
        "workers_comp_and_contractor_insurance": [
            "workers compensation class code rate calculator by state",
            "experience modification rate emr impact calculator",
            "general contractor commercial general liability coi cost calculator",
        ],
        "mechanics_lien_retainage_and_prevailing_wage": [
            "contractor lien release statutory matrix by state",
            "commercial construction retainage interest penalty calculator by state",
            "davis bacon prevailing wage fringe benefit rate calculator",
        ],
    },
    default_core_tools=(
        {"slug": "workers-compensation-class-code-rate-calculator-by-state", "primary_keyword": "workers compensation class code rate calculator by state"},
        {"slug": "contractor-license-bond-cost-calculator-by-credit-score", "primary_keyword": "contractor license bond cost calculator by credit score"},
        {"slug": "miller-act-performance-and-payment-bond-premium-calculator", "primary_keyword": "performance and payment bond premium calculator"},
        {"slug": "contractor-lien-release-statutory-matrix-by-state", "primary_keyword": "contractor lien release statutory matrix by state"},
        {"slug": "commercial-construction-retainage-interest-penalty-calculator-by-state", "primary_keyword": "commercial construction retainage interest penalty calculator by state"},
        {"slug": "davis-bacon-prevailing-wage-fringe-benefit-rate-calculator", "primary_keyword": "davis bacon prevailing wage fringe benefit rate calculator"},
        {"slug": "erisa-fidelity-bond-coverage-amount-calculator", "primary_keyword": "erisa fidelity bond coverage amount calculator"},
        {"slug": "contractor-overhead-and-profit-markup-vs-margin-calculator", "primary_keyword": "contractor overhead and profit markup vs margin calculator"},
        {"slug": "experience-modification-rate-emr-workers-comp-penalty-calculator", "primary_keyword": "experience modification rate emr workers comp penalty calculator"},
        {"slug": "california-texas-florida-preliminary-notice-deadline-calculator", "primary_keyword": "preliminary notice deadline calculator california texas florida"},
    ),
    flagship_anchor_slugs=(
        "workers-compensation-class-code-rate-calculator-by-state",
        "contractor-license-bond-cost-calculator-by-credit-score",
        "contractor-lien-release-statutory-matrix-by-state",
    ),
    video_branding={
        "brand_name": "LienBond",
        "domain": "lienbond.com",
        "canonical_base": "https://lienbond.com",
        "badge_text": "LIENBOND.COM | SURETY & LIEN ENGINE",
        "verification_pill": "50-STATE STATUTORY VERIFIED",
        "bg_rgb": (15, 23, 42),
        "card_rgb": (30, 41, 59),
        "accent_rgb": (245, 158, 11),
        "accent_hex": "#f59e0b",
        "voice": "en-US-ChristopherNeural",
    },
    default_cpc_usd=18.5,
    default_erpm_usd=115.0,
    default_sample_query="workers compensation class code rate calculator by state",
    default_sample_slug="workers-compensation-class-code-rate-calculator-by-state",
    top_modifier_fallback="(50-State Statutory)",
    vertical_paren_modifier="Surety & Lien Guide",
    default_smoke_probe={
        "query": "miller act performance and payment bond premium calculator",
        "foreign_query": "save plan student loan repayment calculator",
    },
    priority_hub_slugs=(
        "workers-compensation-class-code-rate-calculator-by-state",
        "contractor-lien-release-statutory-matrix-by-state",
    ),
    default_complementary_peers=(
        ("workers-compensation-class-code-rate-calculator-by-state", "Workers Comp Class Code & EMR Calculator"),
        ("contractor-license-bond-cost-calculator-by-credit-score", "Contractor License Surety Bond Cost Calculator"),
        ("contractor-lien-release-statutory-matrix-by-state", "50-State Mechanics Lien Deadline & Waiver Matrix"),
    ),
    primary_fallback_manifest_slug="workers-compensation-class-code-rate-calculator-by-state",
    primary_partner_key="simply_business",
    primary_partner_name="Simply Business Commercial Contractor Insurance & Bonding",
    primary_partner_url="https://www.simplybusiness.com/",
    primary_partner_cta="Compare Instant Contractor Insurance & Bond Quotes at Simply Business",
    tools_directory_seed_section_html="",
)

CANONICAL_TENANT_DECLARATIONS["lienbond"] = LIENBOND_TENANT_CONTRACT

SPAWNED_TENANT_DECLARATIONS: Dict[str, DeclarativeTenantContract] = {}

CANONICAL_TENANT_IDS: List[str] = []
CANONICAL_TENANT_DOMAINS: List[str] = []
CANONICAL_TENANT_HOSTS: Dict[str, str] = {}
CANONICAL_TENANT_CONFIGS: Dict[str, Dict[str, str]] = {}
DEFAULT_TENANT_LINKEDIN_IDS: Dict[str, str] = {}
TENANT_STATUTORY_INTENT_TOKENS: Dict[str, List[str]] = {}
TENANT_CATEGORY_SEED_TAXONOMY: Dict[str, Dict[str, List[str]]] = {}
TENANT_VIDEO_BRANDING: Dict[str, Dict[str, Any]] = {}
TENANT_FLAGSHIP_ANCHOR_SLUGS: Dict[str, Tuple[str, ...]] = {}
TENANT_SMOKE_PROBES: Dict[str, Dict[str, str]] = {}
TENANT_DEFAULT_CPC_USD: Dict[str, float] = {}
TENANT_DEFAULT_ERPM_USD: Dict[str, float] = {}
TENANT_CORE_TOOLS_BY_ID: Dict[str, List[Dict[str, Any]]] = {}
TENANT_CANNIBALIZATION_MAPS_BY_ID: Dict[str, Dict[str, Dict[str, str]]] = {}
TENANT_FOREIGN_BOUNDARY_TOKENS: Dict[str, Set[str]] = {}
CANONICAL_PRODUCTION_PROPERTIES: Set[str] = set()
REPO_DIR_TO_PROPERTY_ID: Dict[str, str] = {}


def _sync_derived_tenant_registries() -> None:
    """
    Synchronizes all derived per-tenant dictionaries in-place from
    CANONICAL_TENANT_DECLARATIONS so downstream loops hold live references
    without touching separate modules when registering or updating a tenant.
    """
    CANONICAL_TENANT_IDS.clear()
    CANONICAL_TENANT_DOMAINS.clear()
    CANONICAL_TENANT_HOSTS.clear()
    CANONICAL_TENANT_CONFIGS.clear()
    DEFAULT_TENANT_LINKEDIN_IDS.clear()
    TENANT_STATUTORY_INTENT_TOKENS.clear()
    TENANT_CATEGORY_SEED_TAXONOMY.clear()
    TENANT_VIDEO_BRANDING.clear()
    TENANT_FLAGSHIP_ANCHOR_SLUGS.clear()
    TENANT_SMOKE_PROBES.clear()
    TENANT_DEFAULT_CPC_USD.clear()
    TENANT_DEFAULT_ERPM_USD.clear()
    active_pids = set(CANONICAL_TENANT_DECLARATIONS.keys()) | set(SPAWNED_TENANT_DECLARATIONS.keys())
    for stale_pid in list(TENANT_CORE_TOOLS_BY_ID.keys()):
        if stale_pid not in active_pids:
            TENANT_CORE_TOOLS_BY_ID.pop(stale_pid, None)
    for stale_pid in list(TENANT_CANNIBALIZATION_MAPS_BY_ID.keys()):
        if stale_pid not in active_pids:
            TENANT_CANNIBALIZATION_MAPS_BY_ID.pop(stale_pid, None)
    TENANT_FOREIGN_BOUNDARY_TOKENS.clear()
    CANONICAL_PRODUCTION_PROPERTIES.clear()
    CANONICAL_PRODUCTION_PROPERTIES.update({"pseofactory", "factory", "default"})
    REPO_DIR_TO_PROPERTY_ID.clear()

    for pid, contract in CANONICAL_TENANT_DECLARATIONS.items():
        CANONICAL_TENANT_IDS.append(pid)
        CANONICAL_TENANT_DOMAINS.append(contract.domain)
        CANONICAL_TENANT_HOSTS[pid] = contract.domain
        CANONICAL_TENANT_CONFIGS[pid] = contract.to_tenant_config_dict()
        if contract.linkedin_company_id:
            DEFAULT_TENANT_LINKEDIN_IDS[pid] = contract.linkedin_company_id
        TENANT_STATUTORY_INTENT_TOKENS[pid] = list(contract.statutory_intent_tokens)
        TENANT_CATEGORY_SEED_TAXONOMY[pid] = {
            k: list(v) for k, v in contract.category_seed_taxonomy.items()
        }
        TENANT_VIDEO_BRANDING[pid] = dict(contract.video_branding)
        TENANT_FLAGSHIP_ANCHOR_SLUGS[pid] = tuple(contract.flagship_anchor_slugs)
        TENANT_SMOKE_PROBES[pid] = dict(contract.default_smoke_probe)
        TENANT_DEFAULT_CPC_USD[pid] = float(contract.default_cpc_usd)
        TENANT_DEFAULT_ERPM_USD[pid] = float(contract.default_erpm_usd)
        existing_tools_list = TENANT_CORE_TOOLS_BY_ID.setdefault(pid, [])
        existing_tools_list.clear()
        existing_tools_list.extend(dict(t) for t in contract.default_core_tools)
        existing_cann_map = TENANT_CANNIBALIZATION_MAPS_BY_ID.setdefault(pid, {})
        existing_cann_map.update({
            k: dict(v) for k, v in contract.cannibalization_clone_map.items()
        })
        CANONICAL_PRODUCTION_PROPERTIES.add(pid)
        if contract.repo_dir_name:
            CANONICAL_PRODUCTION_PROPERTIES.add(contract.repo_dir_name)
            REPO_DIR_TO_PROPERTY_ID[contract.repo_dir_name.lower()] = pid
        REPO_DIR_TO_PROPERTY_ID[pid] = pid

    for pid, contract in SPAWNED_TENANT_DECLARATIONS.items():
        if pid in CANONICAL_TENANT_DECLARATIONS:
            continue
        CANONICAL_TENANT_HOSTS[pid] = contract.domain
        CANONICAL_TENANT_CONFIGS[pid] = contract.to_tenant_config_dict()
        if contract.linkedin_company_id:
            DEFAULT_TENANT_LINKEDIN_IDS[pid] = contract.linkedin_company_id
        TENANT_STATUTORY_INTENT_TOKENS[pid] = list(contract.statutory_intent_tokens)
        TENANT_CATEGORY_SEED_TAXONOMY[pid] = {
            k: list(v) for k, v in contract.category_seed_taxonomy.items()
        }
        TENANT_VIDEO_BRANDING[pid] = dict(contract.video_branding)
        TENANT_FLAGSHIP_ANCHOR_SLUGS[pid] = tuple(contract.flagship_anchor_slugs)
        TENANT_SMOKE_PROBES[pid] = dict(contract.default_smoke_probe)
        TENANT_DEFAULT_CPC_USD[pid] = float(contract.default_cpc_usd)
        TENANT_DEFAULT_ERPM_USD[pid] = float(contract.default_erpm_usd)
        existing_tools_list = TENANT_CORE_TOOLS_BY_ID.setdefault(pid, [])
        existing_tools_list.clear()
        existing_tools_list.extend(dict(t) for t in contract.default_core_tools)
        existing_cann_map = TENANT_CANNIBALIZATION_MAPS_BY_ID.setdefault(pid, {})
        existing_cann_map.update({
            k: dict(v) for k, v in contract.cannibalization_clone_map.items()
        })
        CANONICAL_PRODUCTION_PROPERTIES.add(pid)
        if contract.repo_dir_name:
            CANONICAL_PRODUCTION_PROPERTIES.add(contract.repo_dir_name)
            REPO_DIR_TO_PROPERTY_ID[contract.repo_dir_name.lower()] = pid
        REPO_DIR_TO_PROPERTY_ID[pid] = pid

    all_decls = {**CANONICAL_TENANT_DECLARATIONS, **SPAWNED_TENANT_DECLARATIONS}
    for pid, contract in all_decls.items():
        explicit_forbidden = (
            {t.lower() for t in contract.truth_profile.cross_tenant_forbidden_tokens}
            if contract.truth_profile and contract.truth_profile.cross_tenant_forbidden_tokens
            else set()
        )
        peer_tokens: Set[str] = set()
        for other_id, other_contract in all_decls.items():
            if other_id == pid:
                continue
            peer_tokens.add(other_id.lower())
            if other_contract.domain:
                peer_tokens.add(other_contract.domain.lower())
            if other_contract.linkedin_company_id:
                peer_tokens.add(other_contract.linkedin_company_id.lower())
            for own_tok in other_contract.own_boundary_tokens:
                if own_tok:
                    peer_tokens.add(own_tok.lower())
        merged_forbidden = explicit_forbidden | peer_tokens
        TENANT_FOREIGN_BOUNDARY_TOKENS[pid] = merged_forbidden
        if contract.truth_profile is not None:
            contract.truth_profile.cross_tenant_forbidden_tokens.update(merged_forbidden)


_sync_derived_tenant_registries()


def list_canonical_tenant_ids() -> Tuple[str, ...]:
    """Returns ordered tuple of registered canonical tenant property IDs."""
    return tuple(CANONICAL_TENANT_IDS)


def list_canonical_tenant_domains() -> Tuple[str, ...]:
    """Returns ordered tuple of registered canonical tenant domains."""
    return tuple(CANONICAL_TENANT_DOMAINS)


def list_canonical_repo_dir_names() -> Tuple[str, ...]:
    """Returns ordered tuple of registered canonical tenant repository directory names."""
    return tuple(c.repo_dir_name for c in CANONICAL_TENANT_DECLARATIONS.values() if c.repo_dir_name)


def resolve_canonical_property_id(
    tenant_or_context: Optional[str] = "profithelm",
    repo_root: Optional[Any] = None,
    default: str = "profithelm",
) -> str:
    """
    Resolves a property_id, repo_dir_name, domain, URL, or filesystem path
    to a registered tenant property_id, a TruthPack property_id, or the raw non-empty
    tenant identifier. NEVER silently collapses an unknown real tenant ID to 'profithelm'.
    """
    if repo_root is not None:
        try:
            marker_file = Path(repo_root) / ".pseofactory.json"
            if marker_file.is_file():
                marker_data = json.loads(marker_file.read_text(encoding="utf-8"))
                if isinstance(marker_data, dict):
                    marker_pid = str(marker_data.get("property_id") or "").strip().lower()
                    if marker_pid:
                        if marker_pid in ("profithelm-platform", "factory"):
                            return "profithelm"
                        return marker_pid
        except Exception:
            pass

    raw = str(tenant_or_context or "").strip().lower()
    if raw in ("profithelm-platform", "factory"):
        return "profithelm"
    if raw in CANONICAL_TENANT_DECLARATIONS:
        return raw
    if raw in SPAWNED_TENANT_DECLARATIONS:
        return raw
    if raw in REPO_DIR_TO_PROPERTY_ID:
        return REPO_DIR_TO_PROPERTY_ID[raw]

    try:
        from pseofactory.truth_pack import discover_truth_pack_ids

        tp_ids = set(discover_truth_pack_ids())
        if raw in tp_ids:
            return raw
    except Exception:
        tp_ids = set()

    combined = f"{raw} {repo_root or ''}".lower()
    all_decls = {**CANONICAL_TENANT_DECLARATIONS, **SPAWNED_TENANT_DECLARATIONS}
    # Check non-default tenants first so specific substrings win over default fallback
    for pid, contract in all_decls.items():
        if pid == default:
            continue
        if (
            pid in combined
            or (contract.repo_dir_name and contract.repo_dir_name.lower() in combined)
            or (contract.domain and contract.domain.lower() in combined)
        ):
            return pid
    for tp_pid in sorted(tp_ids):
        if tp_pid != default and tp_pid in combined:
            return tp_pid

    if default in all_decls:
        def_c = all_decls[default]
        if (
            default in combined
            or (def_c.repo_dir_name and def_c.repo_dir_name.lower() in combined)
            or (def_c.domain and def_c.domain.lower() in combined)
        ):
            return default

    # Never collapse a real unknown tenant ID (e.g. 'synthetic_fifth_site' or 'site_05') to 'profithelm'
    if raw and raw not in ("default", "pseofactory", "factory") and "/" not in raw and "\\" not in raw and " " not in raw:
        return raw
    return default


def get_tenant_contract(
    tenant_or_context: Optional[str] = "profithelm",
    repo_root: Optional[Any] = None,
    default: str = "profithelm",
) -> DeclarativeTenantContract:
    """
    Returns the DeclarativeTenantContract for a tenant ID, domain, or repo path.
    Supports 50+ sites dynamically via TruthPack synthesis; fails closed for unknown sites.
    """
    pid = resolve_canonical_property_id(tenant_or_context, repo_root=repo_root, default=default)
    existing = CANONICAL_TENANT_DECLARATIONS.get(pid) or SPAWNED_TENANT_DECLARATIONS.get(pid)
    if existing is not None:
        return existing

    pack = _load_truth_pack_safe(pid, workspace_root=Path(repo_root).parent if repo_root else None)
    if pack is not None:
        profile = _build_profile_from_truth_pack(pack)
        domain = re.sub(r"^https?://", "", str(pack.canonical_domain or f"{pid}.com")).strip("/")
        return DeclarativeTenantContract(
            property_id=pack.property_id,
            repo_dir_name=pack.property_id,
            domain=domain,
            canonical_base=pack.canonical_domain or f"https://{domain}",
            brand_name=pack.brand_name,
            package_name=pack.property_id,
            truth_profile=profile,
            statutory_truth=profile.statutory_truth,
            audience_tier=pack.audience_tier or "business",
        )

    raise KeyError(f"TRUTH_PACK_MISSING: Unknown tenant contract '{pid}' (no registration or Truth Pack found)")


def _token_matches_query(tok: str, q_lower: str) -> bool:
    """Matches statutory intent token against query using word boundaries for short or numeric tokens."""
    if (len(tok) <= 3 and tok.isalnum()) or tok.isdigit():
        return bool(re.search(rf"\b{re.escape(tok)}\b", q_lower))
    return tok in q_lower


def match_tenant_statutory_intent(query: str, include_spawned: bool = False) -> Dict[str, bool]:
    """
    Evaluates a search query against all registered tenants' statutory_intent_tokens
    in TENANT_STATUTORY_INTENT_TOKENS (plus SPAWNED_TENANT_DECLARATIONS when include_spawned=True).
    """
    q_lower = (query or "").lower().strip()
    matched: Dict[str, bool] = {}
    for pid, tokens in TENANT_STATUTORY_INTENT_TOKENS.items():
        hit = any(_token_matches_query(tok, q_lower) for tok in tokens)
        if not hit and pid == "profithelm" and ("1031" in q_lower and "exchange" in q_lower):
            hit = True
        matched[pid] = hit
    if include_spawned:
        for pid, contract in SPAWNED_TENANT_DECLARATIONS.items():
            if pid not in matched:
                matched[pid] = any(_token_matches_query(tok, q_lower) for tok in contract.statutory_intent_tokens)
    return matched


def register_declarative_tenant(contract: DeclarativeTenantContract) -> DeclarativeTenantContract:
    """
    Registers a DeclarativeTenantContract into CANONICAL_TENANT_DECLARATIONS and
    synchronizes all derived per-tenant dictionaries and TenantFactStore profiles in-place.
    """
    pid = str(contract.property_id).strip().lower()
    if not pid:
        raise ValueError("DeclarativeTenantContract.property_id must be non-empty")
    CANONICAL_TENANT_DECLARATIONS[pid] = contract
    _sync_derived_tenant_registries()
    if TenantFactStore._instance is not None and contract.truth_profile is not None:
        TenantFactStore._instance._profiles[pid] = contract.truth_profile
        for existing_pid, existing_prof in TenantFactStore._instance._profiles.items():
            existing_prof.cross_tenant_forbidden_tokens.update(
                TENANT_FOREIGN_BOUNDARY_TOKENS.get(existing_pid, set())
            )
    return contract


def unregister_declarative_tenant(property_id: str) -> bool:
    """
    Unregisters a non-core or temporary tenant from CANONICAL_TENANT_DECLARATIONS
    and restores derived registries (used by unit test fixtures).
    """
    pid = str(property_id or "").strip().lower()
    if pid not in CANONICAL_TENANT_DECLARATIONS:
        return False
    del CANONICAL_TENANT_DECLARATIONS[pid]
    # Restore canonical truth profiles for remaining tenants so test tokens are scrubbed
    fresh_defaults = _build_canonical_tenant_declarations()
    for rem_pid in list(CANONICAL_TENANT_DECLARATIONS.keys()):
        if rem_pid in fresh_defaults:
            CANONICAL_TENANT_DECLARATIONS[rem_pid] = fresh_defaults[rem_pid]
    _sync_derived_tenant_registries()
    if TenantFactStore._instance is not None:
        TenantFactStore._instance._profiles.pop(pid, None)
        for rem_pid, rem_contract in CANONICAL_TENANT_DECLARATIONS.items():
            if rem_contract.truth_profile is not None:
                TenantFactStore._instance._profiles[rem_pid] = rem_contract.truth_profile
    return True


class TenantFactStore:
    """
    Centralized singleton store for tenant truth profiles.
    Enforces truth assertions, claim verification, and tenant isolation boundaries.
    Zero em-dashes. Zero en-dashes.
    """

    _instance: Optional["TenantFactStore"] = None

    def __init__(self):
        self._profiles: Dict[str, TenantTruthProfile] = {
            pid: contract.truth_profile
            for pid, contract in {**CANONICAL_TENANT_DECLARATIONS, **SPAWNED_TENANT_DECLARATIONS}.items()
            if contract.truth_profile is not None
        }

    @staticmethod
    def classify_domain_lifecycle(tenant_or_domain: str) -> str:
        """
        Classifies a tenant ID or domain into its canonical lifecycle tier:
        ACTIVE_TENANT, STAGED_RESERVE, PERSONAL_INFRA, DECOMMISSIONED, or UNMAPPED.
        Zero em-dashes. Zero en-dashes.
        """
        raw = (tenant_or_domain or "").strip().lower()
        if not raw:
            return "UNMAPPED"
        norm = raw if "." in raw else f"{raw}.com"
        if norm in CANONICAL_TENANT_DOMAINS or raw in CANONICAL_TENANT_DECLARATIONS:
            return "ACTIVE_TENANT"
        if norm in STAGED_RESERVE_TENANT_DOMAINS:
            return "STAGED_RESERVE"
        if norm in PERSONAL_INFRASTRUCTURE_DOMAINS:
            return "PERSONAL_INFRA"
        if norm in DECOMMISSIONED_TENANT_DOMAINS:
            return "DECOMMISSIONED"
        return "UNMAPPED"

    @staticmethod
    def get_registrar_attestation(tenant_or_domain: str) -> Optional[Dict[str, Any]]:
        """Returns a copy of the attested Registrar record for a portfolio domain."""
        raw = (tenant_or_domain or "").strip().lower()
        if not raw:
            return None
        norm = raw if "." in raw else f"{raw}.com"
        entry = CLOUDFLARE_PORTFOLIO_REGISTRAR_LEDGER.get(norm)
        return dict(entry) if entry is not None else None

    @staticmethod
    def verify_registrar_ledger_integrity(
        ledger: Optional[Dict[str, Dict[str, Any]]] = None,
        reference_utc: Optional[datetime] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Verifies cryptographic attestation, transfer-lock integrity (locked=True,
        clienttransferprohibited), WHOIS redaction (privacy=True), auto_renew alignment,
        and expiration/sunset horizon bounds across all attested Cloudflare portfolio domains.
        Zero em-dashes. Zero en-dashes.
        """
        target = ledger if ledger is not None else CLOUDFLARE_PORTFOLIO_REGISTRAR_LEDGER
        now_dt = reference_utc or datetime.now(timezone.utc)
        violations: List[str] = []

        expected_domain_count = len(CLOUDFLARE_PORTFOLIO_REGISTRAR_LEDGER)
        if len(target) != expected_domain_count:
            violations.append(
                f"Expected {expected_domain_count} portfolio domains in ledger, found {len(target)}"
            )

        total_exposure = 0.0
        sunset_windows_days: Dict[str, float] = {}
        kept_renewal_horizons_days: Dict[str, float] = {}

        for domain, rec in target.items():
            tier = TenantFactStore.classify_domain_lifecycle(domain)
            if rec.get("lifecycle_tier") != tier:
                violations.append(f"{domain} lifecycle_tier mismatch: {rec.get('lifecycle_tier')} != {tier}")
            if rec.get("locked") is not True:
                violations.append(f"{domain} transfer lock is False (must be locked=True)")
            statuses = str(rec.get("registry_statuses") or "").lower()
            if "clienttransferprohibited" not in statuses:
                violations.append(f"{domain} missing clienttransferprohibited in registry_statuses")
            if rec.get("privacy") is not True or rec.get("privacy_mode") != "redaction":
                violations.append(f"{domain} WHOIS privacy redaction not enabled")

            exp_str = str(rec.get("expires_at") or "")
            try:
                exp_dt = datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
                days_remaining = (exp_dt - now_dt).total_seconds() / 86400.0
            except Exception as exc:
                violations.append(f"{domain} invalid expires_at timestamp '{exp_str}': {exc}")
                days_remaining = -9999.0

            auto_renew = rec.get("auto_renew")
            if tier in ("ACTIVE_TENANT", "STAGED_RESERVE", "PERSONAL_INFRA"):
                if auto_renew is not True:
                    violations.append(f"{domain} ({tier}) has auto_renew={auto_renew} (must be True)")
                kept_renewal_horizons_days[domain] = round(days_remaining, 2)
                if days_remaining <= 0 and auto_renew is not True:
                    violations.append(f"{domain} has expired without auto_renew coverage")
            elif tier == "DECOMMISSIONED":
                if auto_renew is not False:
                    violations.append(f"{domain} (DECOMMISSIONED) has auto_renew={auto_renew} (must be False)")
                if rec.get("routing_records_allowed") is not False:
                    violations.append(f"{domain} (DECOMMISSIONED) must have routing_records_allowed=False")
                if float(rec.get("effective_annual_exposure_usd", -1.0)) != 0.0:
                    violations.append(f"{domain} (DECOMMISSIONED) must have $0.00 annual exposure")
                sunset_windows_days[domain] = round(days_remaining, 2)
            else:
                violations.append(f"{domain} has unmapped lifecycle tier {tier}")

            total_exposure += float(rec.get("effective_annual_exposure_usd", 0.0))

        digest = compute_registrar_ledger_sha256(target)
        if target is CLOUDFLARE_PORTFOLIO_REGISTRAR_LEDGER and digest != CLOUDFLARE_REGISTRAR_ATTESTATION_SHA256:
            violations.append("Registrar ledger SHA-256 digest mismatch")

        details = {
            "attestation_sha256": digest,
            "domains_verified": len(target),
            "total_annual_exposure_usd": round(total_exposure, 2),
            "kept_renewal_horizons_days": kept_renewal_horizons_days,
            "sunset_windows_days": sunset_windows_days,
        }
        if violations:
            return False, "Registrar ledger integrity violations: " + "; ".join(violations), details
        return (
            True,
            f"Registrar attestation verified across {len(target)} domains (locked=True, privacy=redaction, exposure=${total_exposure:.2f}/yr, sha256={digest[:12]})",
            details,
        )

    @classmethod
    def get_instance(cls) -> "TenantFactStore":
        """Returns singleton instance of TenantFactStore."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Resets singleton instance for test isolation."""
        cls._instance = None

    @classmethod
    def get_statutory_truth(
        cls,
        tenant_id: str,
        workspace_root: Optional[Path] = None,
    ) -> TenantStatutoryTruth:
        """
        Returns TenantStatutoryTruth backed by TruthPack (or registered tenant profile).
        Exposes .regulator_name, .controlling_statute, and .effective_tax_year.
        Fails closed with TruthPackMissingError for unknown tenants without a TruthPack.
        """
        from pseofactory.truth_pack import TruthPackMissingError

        pid = resolve_canonical_property_id(tenant_id, default=str(tenant_id or "").strip().lower())
        store = cls.get_instance()
        pack = _load_truth_pack_safe(pid, workspace_root=workspace_root)
        prof = store.get_profile(pid, workspace_root=workspace_root)
        if prof is not None and prof.statutory_truth is not None:
            if prof.statutory_truth.regulator_name and prof.statutory_truth.controlling_statute:
                return prof.statutory_truth
            if pack is not None:
                tp_truth = _build_statutory_truth_from_truth_pack(pack)
                return TenantStatutoryTruth(
                    tenant_id=pid,
                    statutory_citations={**tp_truth.statutory_citations, **prof.statutory_truth.statutory_citations},
                    limits_and_thresholds={**tp_truth.limits_and_thresholds, **prof.statutory_truth.limits_and_thresholds},
                    regulator_name=prof.statutory_truth.regulator_name or tp_truth.regulator_name,
                    controlling_statute=prof.statutory_truth.controlling_statute or tp_truth.controlling_statute,
                    effective_tax_year=prof.statutory_truth.effective_tax_year or tp_truth.effective_tax_year,
                )
            return prof.statutory_truth
        if pack is not None:
            return _build_statutory_truth_from_truth_pack(pack)
        raise TruthPackMissingError(
            f"TRUTH_PACK_MISSING: No Truth Pack or registered profile found for tenant '{tenant_id}'"
        )

    def get_profile(
        self,
        tenant: str,
        workspace_root: Optional[Path] = None,
    ) -> Optional[TenantTruthProfile]:
        """Retrieves tenant profile by identifier, dynamically loading TruthPack for 5th+ sites."""
        if not tenant:
            return None
        pid = str(tenant).lower().strip()
        existing = self._profiles.get(pid)
        if existing is not None:
            return existing
        pack = _load_truth_pack_safe(pid, workspace_root=workspace_root)
        if pack is not None:
            built = _build_profile_from_truth_pack(pack)
            self._profiles[pid] = built
            return built
        return None

    def verify_price(self, tenant: str, price_usd: float) -> bool:
        """
        Verifies if price_usd matches an official pricing tier for the tenant.
        Zero em-dashes. Zero en-dashes.
        """
        profile = self.get_profile(tenant)
        if not profile:
            return False
        valid_prices = {tier.price_usd for tier in profile.pricing_tiers.values()}
        return float(price_usd) in valid_prices

    def verify_feature(self, tenant: str, feature_name: str) -> bool:
        """
        Verifies if feature_name is recognized and enabled for the tenant.
        Zero em-dashes. Zero en-dashes.
        """
        profile = self.get_profile(tenant)
        if not profile:
            return False
        for f_key, f_val in profile.features.items():
            if f_key.lower() == feature_name.lower().strip() or f_val.name.lower() == feature_name.lower().strip():
                return f_val.enabled
        return False

    _VERIFY_CLAIM_CACHE: Dict[Tuple[str, str, str], Tuple[bool, List[str]]] = {}

    def verify_claim(
        self,
        tenant: str,
        text: str,
        context: Optional[str] = None,
        spec_disclosures: Optional[List[str]] = None,
    ) -> Tuple[bool, List[str]]:
        """
        Inspects text against tenant truth profile and TruthPack:
        0. Fail closed when tenant has neither TruthPack nor registered profile
        1. Banned marketing claims (profile + TruthPack regexes)
        2. Unverified pricing numbers ($XX/mo AND one-time offer/checkout strings)
        3. Cross-tenant boundary contamination
        4. Mandatory regulatory disclosures (including GainHelm non-bare-c3pao and full LienBond)
        5. Statutory threshold limit boundaries, TruthPack citation allowlists, & ground-truth figures
        Returns (is_valid, violations_list).
        Zero em-dashes. Zero en-dashes.
        """
        assert_no_forbidden_dashes(text, context=context or f"verify_claim({tenant})")
        tenant_norm = str(tenant or "").lower().strip()
        pack = _load_truth_pack_safe(tenant_norm)
        profile = self.get_profile(tenant_norm)
        if not profile and pack is None:
            return False, [
                f"TRUTH_PACK_MISSING: No Truth Pack or registered profile found for tenant '{tenant}'"
            ]

        cache_key: Optional[Tuple[str, str, str]] = None
        if not spec_disclosures and len(text) >= 256:
            text_digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
            cache_key = (tenant_norm, text_digest, str(context or ""))
            cached = self._VERIFY_CLAIM_CACHE.get(cache_key)
            if cached is not None:
                return cached[0], list(cached[1])

        violations: List[str] = []
        text_lower = text.lower()

        # 1. Banned claims check (profile substrings + TruthPack regex patterns)
        for banned in profile.claims_banned:
            if banned.lower() in text_lower:
                violations.append(
                    f"Banned claim detected for {profile.brand_name}: '{banned}'"
                )
        if pack is not None:
            for b_rule in getattr(pack, "banned_claims", []) or []:
                b_pat = str(b_rule.get("pattern") or "").strip() if isinstance(b_rule, dict) else ""
                b_reason = str(b_rule.get("reason") or "Banned TruthPack claim").strip() if isinstance(b_rule, dict) else "Banned TruthPack claim"
                if b_pat:
                    try:
                        if re.search(b_pat, text, re.IGNORECASE):
                            msg = f"Banned TruthPack claim detected for {profile.brand_name}: {b_reason}"
                            if msg not in violations:
                                violations.append(msg)
                    except re.error:
                        pass

        # 2. Pricing verification (/mo AND one-time offer/checkout pricing strings)
        if "$" in text or "offer_price_usd" in text_lower or "price_usd" in text_lower or "data-offer-price" in text_lower:
            valid_prices = {float(tier.price_usd) for tier in profile.pricing_tiers.values()}
            if pack is not None and isinstance(getattr(pack, "pricing_tiers", None), dict):
                for t_obj in pack.pricing_tiers.values():
                    if isinstance(t_obj, dict) and t_obj.get("price_usd") is not None:
                        try:
                            valid_prices.add(float(t_obj["price_usd"]))
                        except (TypeError, ValueError):
                            pass

            allowed_statutory_monthly = {
                float(v)
                for k, v in profile.statutory_truth.limits_and_thresholds.items()
                if isinstance(v, (int, float)) and ("monthly" in k or "subsidy" in k)
            }
            calc_output_markers = (
                "payment", "repayment", "installment", "rap", "ibr", "icr", "save",
                "pslf", "loan", "debt", "student", "agi", "borrower", "forbearance",
                "subsidy", "discretionary", "tax", "interest", "savings", "deduction",
                "bond", "premium", "retainage", "salary", "payroll", "breach",
                "penalty", "cost", "/yr", "annual", "lease", "burn", "mrr",
            )
            explicit_saas_tier_markers = (
                "pricing", "pricing tier", "pro tier", "enterprise tier", "starter tier",
                "quick tier", "full tier", "subscription", "membership", "upgrade to",
                "pro plan", "starter plan", "paid plan", "monthly plan",
            )
            for m_price in re.finditer(
                r'\$(\d+(?:\.\d{1,2})?)\s*(?:/|\s*per\s*)(?:mo|month)',
                text,
                re.IGNORECASE,
            ):
                price_val = float(m_price.group(1))
                if price_val in valid_prices or price_val in allowed_statutory_monthly:
                    continue
                win_start = max(0, m_price.start() - 110)
                win_end = min(len(text_lower), m_price.end() + 110)
                window = text_lower[win_start:win_end]
                has_saas_marker = any(sm in window for sm in explicit_saas_tier_markers)
                has_calc_marker = any(cm in window for cm in calc_output_markers)
                if has_calc_marker and not has_saas_marker:
                    continue
                violations.append(
                    f"Unverified price claim '${price_val}' contradicts {profile.brand_name} pricing tiers {sorted(valid_prices)}"
                )

            # One-time pricing / offer / checkout strings (e.g. $49, $99, $999)
            for m_offer_kv in re.finditer(
                r'(?:offer_price_usd|checkout_price|tier_price|data-offer-price)\s*(?:["\']?\s*[:=]\s*["\']?|\|\|\s*)\$?(\d+(?:\.\d{1,2})?)',
                text,
                re.IGNORECASE,
            ):
                p_val = float(m_offer_kv.group(1))
                if p_val not in valid_prices:
                    msg = f"Unverified one-time offer/checkout price '${p_val:g}' contradicts {profile.brand_name} pricing tiers {sorted(valid_prices)}"
                    if msg not in violations:
                        violations.append(msg)

            onetime_offer_markers = (
                "one-time", "one time", "unlock", "checkout", "pricing tier",
                "full workpaper", "quick worksheet", "partner slot", "upgrade to",
                "pro plan", "pro tier", "enterprise tier", "starter tier",
                "buy now", "order summary", "paywall", "get instant access",
                "instant worksheet", "data pack", "playbook",
            )
            statutory_or_calc_skip_markers = (
                "bond", "miller act", "cslb", "min_premium", "minimum premium",
                "principal match", "deduction", "section 179", "section 1202",
                "poverty", "loan", "agi", "penalty", "forensic", "c3pao", "cpa fee",
                "audit cost", "payroll", "salary", "fob", "tariff", "cap", "limit",
                "annual", "/yr", "per year", "per month", "/mo",
            )
            if any(om in text_lower for om in onetime_offer_markers):
                for m_ot in re.finditer(r'(?<![0-9.])\$(\d{1,4}(?:\.\d{1,2})?)\b(?![,\d])', text):
                    p_val = float(m_ot.group(1))
                    if p_val in valid_prices or p_val == 0.0:
                        continue
                    win_start = max(0, m_ot.start() - 80)
                    win_end = min(len(text_lower), m_ot.end() + 80)
                    win = text_lower[win_start:win_end]
                    has_offer_ctx = any(om in win for om in onetime_offer_markers)
                    has_stat_skip = any(sm in win for sm in statutory_or_calc_skip_markers)
                    # Only flag when offer/checkout context is tightly paired without statutory calc context
                    # OR when explicit checkout/one-time/pro-tier phrasing is adjacent
                    strong_checkout_ctx = any(
                        cm in win
                        for cm in ("one-time", "one time", "checkout", "pricing tier", "pro plan", "pro tier", "enterprise tier", "buy now", "order summary", "unlock", "partner slot")
                    )
                    if has_offer_ctx and (strong_checkout_ctx or not has_stat_skip):
                        msg = f"Unverified one-time pricing claim '${p_val:g}' contradicts {profile.brand_name} pricing tiers {sorted(valid_prices)}"
                        if msg not in violations:
                            violations.append(msg)

        # 3. Cross-tenant boundary isolation (exempting verified parent-entity Zoho mailbox & Stripe legal name)
        boundary_scan_lower = text_lower
        if tenant_norm != "profithelm":
            boundary_scan_lower = re.sub(r"arif\.coskun@profithelm\.com", "", boundary_scan_lower)
            boundary_scan_lower = re.sub(r"\bprofithelm\s+llc\b", "", boundary_scan_lower)
        for token in profile.cross_tenant_forbidden_tokens:
            tok_l = token.lower()
            if tok_l in boundary_scan_lower and re.search(rf"(?<![a-z0-9]){re.escape(tok_l)}(?![a-z0-9])", boundary_scan_lower):
                violations.append(
                    f"Cross-tenant contamination on {profile.brand_name}: found forbidden boundary token '{token}'"
                )

        # 4. Mandatory regulatory disclosures
        if tenant_norm == "profithelm":
            has_tax_modeling = (
                "tax scenario modeling" in text_lower
                or "entity tax modeling" in text_lower
                or "tax modeling scenarios" in text_lower
            )
            if has_tax_modeling:
                has_c230 = (
                    "circular 230" in text_lower
                    or "treasury department circular no. 230" in text_lower
                )
                if not has_c230:
                    violations.append(
                        "Missing mandatory Circular 230 regulatory disclosure: 'Circular 230 tax modeling disclaimer: Information generated is for deterministic computational modeling purposes and does not constitute formal tax, legal, or investment advice under Treasury Department Circular No. 230.'"
                    )
        elif tenant_norm == "prexvo":
            is_route_or_index_registry = (
                "verified_routes_count" in text_lower
                or "autonomous facebook group discovery & topic routing matrix" in text_lower
                or "github seed discovery & authority architecture" in text_lower
            )
            if ("refinance" in text_lower or "refinancing" in text_lower) and not is_route_or_index_registry:
                has_ymyl = (
                    "waives federal protections" in text_lower
                    or "eliminates federal protections" in text_lower
                    or "waive federal protections" in text_lower
                    or "permanently forfeits" in text_lower
                    or "forfeits access to federal" in text_lower
                )
                if not has_ymyl:
                    violations.append(
                        "Missing mandatory YMYL forfeiture disclaimer: 'Refinancing federal student loans permanently waives federal protections'"
                    )
        elif tenant_norm == "gainhelm":
            has_audit_modeling = (
                "audit scenario modeling" in text_lower
                or "compliance audit modeling" in text_lower
                or "attestation scenario modeling" in text_lower
            )
            if has_audit_modeling:
                # Never auto-pass just because 'c3pao' or 'licensed cpa' appears anywhere on the page;
                # require explicit non-CPA / non-C3PAO / planning-estimate disclaimer wording.
                has_tp_disc = False
                if pack is not None and getattr(pack, "disclosures", None):
                    for disc in pack.disclosures:
                        pats = getattr(disc, "required_text_patterns", []) or []
                        if pats and all(re.search(p, text, re.IGNORECASE) for p in pats):
                            has_tp_disc = True
                            break
                has_attestation_disc = has_tp_disc or (
                    "statutory compliance audit disclaimer" in text_lower
                    or "does not constitute a formal cpa" in text_lower
                    or "not a licensed cpa" in text_lower
                    or "not a c3pao" in text_lower
                    or "non-cpa / non-c3pao" in text_lower
                    or ("planning estimate" in text_lower and "not a" in text_lower)
                )
                if not has_attestation_disc:
                    violations.append(
                        "Missing mandatory GainHelm attestation disclosure: 'Statutory compliance audit disclaimer: Cost, penalty, and control-scoping figures are deterministic computational models and do not constitute a formal CPA attestation opinion, DoD C3PAO certification, QSA Report on Compliance, or legal counsel.'"
                    )
        elif tenant_norm == "lienbond":
            ctx_low_lb = str(context or "").lower()
            is_lb_modeling = (
                "<html" in text_lower
                or "surety scenario modeling" in text_lower
                or "underwriting scenario modeling" in text_lower
                or "lien scenario modeling" in text_lower
                or "emr scenario modeling" in text_lower
                or "/tools/" in ctx_low_lb
                or "tools/" in ctx_low_lb
            )
            if is_lb_modeling:
                has_tp_lb_disc = False
                if pack is not None and getattr(pack, "disclosures", None):
                    for disc in pack.disclosures:
                        pats = getattr(disc, "required_text_patterns", []) or []
                        if pats and all(re.search(p, text, re.IGNORECASE) for p in pats):
                            has_tp_lb_disc = True
                            break
                has_lb_disc = has_tp_lb_disc or (
                    (
                        "do not constitute legal advice" in text_lower
                        or "does not constitute legal advice" in text_lower
                        or "non-attorney" in text_lower
                        or "not a licensed attorney" in text_lower
                        or "not a licensed surety" in text_lower
                    )
                    and (
                        "underwriting estimate" in text_lower
                        or "informational" in text_lower
                        or "non-licensed producer" in text_lower
                    )
                )
                if not has_lb_disc:
                    violations.append(
                        "Missing mandatory LienBond underwriting/non-legal disclaimer: 'LienBond is not a licensed attorney, surety underwriter, or insurance producer; outputs are informational underwriting estimates only and do not constitute legal advice.'"
                    )
        elif pack is not None and getattr(pack, "disclosures", None) and "<html" in text_lower:
            slug_ctx_dyn = str(context or "").lower()
            for disc in pack.disclosures:
                applies_pats = getattr(disc, "applies_to_slug_patterns", []) or [".*"]
                if any(re.search(ap, slug_ctx_dyn, re.IGNORECASE) for ap in applies_pats):
                    req_pats = getattr(disc, "required_text_patterns", []) or []
                    if req_pats and not all(re.search(rp, text, re.IGNORECASE) for rp in req_pats):
                        violations.append(
                            f"Missing mandatory {profile.brand_name} disclosure '{disc.disclosure_id}': '{disc.canonical_text}'"
                        )

        if spec_disclosures:
            for disclosure_phrase in spec_disclosures:
                if disclosure_phrase and disclosure_phrase.lower() not in text_lower:
                    violations.append(
                        f"Missing mandatory disclosure containing '{disclosure_phrase}'"
                    )

        # 5. Statutory threshold limit boundaries & ground-truth benchmark figures
        proxy_js_patterns = (
            'regime === "2027_sunset" ? 0.285',
            "0.235 : 0.252",
            "Math.round(adjGain * 0.238)",
            "cliffMults = [0.74, 0.80",
            "Math.round(retainedVal * 1.12)",
            "Math.round(taxVal * 0.82)",
        )
        for p_js in proxy_js_patterns:
            if p_js in text:
                violations.append(
                    f"Client-side JS flat proxy multiplier '{p_js}' detected: embedded calculators and sensitivity tables must evaluate progressive statutory brackets and non-linear AST formulas"
                )

        prose_scan_text = text
        if "<style" in text_lower:
            prose_scan_text = re.sub(r"<style\b[^>]*>[\s\S]*?</style\s*>", " ", prose_scan_text, flags=re.IGNORECASE)
        if "<script" in text_lower:
            prose_scan_text = re.sub(
                r"<script\b(?![^>]*ld\+json)[^>]*>[\s\S]*?</script\s*>",
                " ",
                prose_scan_text,
                flags=re.IGNORECASE,
            )

        # Dynamic TruthPack citations_allowlist forbidden_slug_patterns enforcement (works for 50+ sites)
        if pack is not None and getattr(pack, "citations_allowlist", None):
            canon_m_cit = re.search(r'rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']', text_lower)
            eff_slug_ctx = f"{context or ''} {canon_m_cit.group(1) if canon_m_cit else ''}".lower().strip()
            if eff_slug_ctx:
                cit_prose = re.sub(r"<nav\b[^>]*>[\s\S]*?</nav\s*>", " ", prose_scan_text, flags=re.IGNORECASE)
                cit_prose = re.sub(
                    r'<a\b[^>]*href=["\'](?:/tools/|https?://[^"\']+/tools/)[^"\']*["\'][^>]*>[\s\S]*?</a\s*>',
                    " ",
                    cit_prose,
                    flags=re.IGNORECASE,
                )
                cit_prose = re.sub(r"<[^>]+>", " ", cit_prose)
                for c_key, c_meta in pack.citations_allowlist.items():
                    if not isinstance(c_meta, dict):
                        continue
                    forb_pats = c_meta.get("forbidden_slug_patterns") or []
                    cit_pats = c_meta.get("patterns") or []
                    if forb_pats and cit_pats and any(re.search(fp, eff_slug_ctx, re.IGNORECASE) for fp in forb_pats):
                        for cp in cit_pats:
                            if re.search(cp, cit_prose, re.IGNORECASE):
                                msg = (
                                    f"Forbidden statutory citation '{c_meta.get('canonical', c_key)}' "
                                    f"used on disallowed slug context '{eff_slug_ctx}'"
                                )
                                if msg not in violations:
                                    violations.append(msg)
                                break

        if tenant_norm == "profithelm":
            prose_lower = prose_scan_text.lower()
            from pseofactory.contracts import _extract_anchor_windows
            # Section 179 SUV / heavy vehicle cap ($30,500 for 2024 / $31,300 for 2025 / $32,000 for 2026 Rev. Proc. 2025-32)
            if ("suv" in prose_lower or "vehicle" in prose_lower) and "$" in prose_scan_text:
                suv_win = _extract_anchor_windows(prose_scan_text, prose_lower, ("suv", "vehicle"), pre=260, post=260)
                suv_clause_matches = re.finditer(
                    r'(?:(?:suv|heavy\s*vehicle)[^\.\n]{0,140}?(?:deduct(?:ion)?|allowance|expens(?:e|ing)|cap|limit|maximum)\s+(?:of\s+)?(?:up to\s+)?\$([0-9,]+)|(?:deduct(?:ion)?|allowance|expens(?:e|ing)|cap|limit|maximum)\s+(?:of\s+)?(?:up to\s+)?\$([0-9,]+)[^\.\n]{0,140}?(?:suv|heavy\s*vehicle))',
                    suv_win,
                    re.IGNORECASE,
                ) if suv_win else ()
                for m_obj in suv_clause_matches:
                    raw_val = m_obj.group(1) or m_obj.group(2)
                    clause_low = m_obj.group(0).lower()
                    win_start = max(0, m_obj.start() - 60)
                    win_end = min(len(suv_win), m_obj.end() + 80)
                    window_low = suv_win[win_start:win_end].lower()
                    try:
                        val = float(raw_val.replace(",", ""))
                        has_2024_qual = "2024" in window_low and "in 2026" not in clause_low
                        has_2025_qual = "2025" in window_low and "in 2026" not in clause_low
                        suv_cap = 30500.0 if has_2024_qual else (31300.0 if has_2025_qual else 32000.0)
                        is_general_s179_contrast = (
                            val in (1220000.0, 1250000.0, 2500000.0, 2560000.0)
                            and (
                                "32,000" in window_low
                                or "30,500" in window_low
                                or "31,300" in window_low
                                or "qualifying equipment" in clause_low
                                or "179(b)(1)" in clause_low
                            )
                        )
                        if val > suv_cap and not is_general_s179_contrast:
                            violations.append(
                                f"Section 179 heavy vehicle/SUV limit contradiction: claimed ${val:,.0f} exceeds statutory cap of $32,000 for 2026 ($31,300 for 2025, $30,500 for 2024)"
                            )
                        elif val in (30500.0, 31300.0) and "2026" in window_low and not (has_2024_qual or has_2025_qual):
                            violations.append(
                                f"Stale 2026 Heavy SUV Section 179 cap '${val:,.0f}' detected: 2026 statutory SUV cap under IRS Rev. Proc. 2025-32 is $32,000"
                            )
                    except ValueError:
                        pass

            stale_suv_tokens = (
                "$31,300 cap + bonus",
                "$31,300 + bonus depr.",
                "$31,300 suv cap",
                "$31,300 irc 179(b)(5) cap",
                "irc §179(b)(5) $31,300 cap",
                "irc \\u00a7179(b)(5) $31,300 cap",
                "$31,300 (irc §179(b)(5))",
                "$31,300 statutory section 179 cap ($30,500 prior-year",
                "capped at a $31,300 section 179 deduction in 2026",
                "allowance of up to $31,300 plus 60% bonus depreciation",
                "capped at a $30,500 section 179 deduction in 2026",
                "2026 heavy suv cap is $30,500",
                "2026 statutory suv cap is $30,500",
            )
            for st_suv in stale_suv_tokens:
                if st_suv in text_lower:
                    violations.append(
                        f"Stale 2026 Heavy SUV Section 179 cap '{st_suv}' detected: 2026 statutory SUV cap under IRS Rev. Proc. 2025-32 is $32,000 ($31,300 for 2025, $30,500 for 2024)"
                    )

            # Section 179 overall expense limit ($1,220,000 for 2024 / $2,500,000 for 2025 OBBBA / $2,560,000 for 2026 Rev. Proc. 2025-32)
            if "179" in prose_lower and "$" in prose_scan_text:
                s179_win = _extract_anchor_windows(prose_scan_text, prose_lower, ("179",), pre=260, post=260)
                s179_matches = re.findall(
                    r'(?:section\s*179[^\.\n]{0,140}?(?:deduct(?:ion)?|expense(?:\s+limit)?|cap|maximum)\s+(?:up to\s+)?\$([0-9,]+)|(?:deduct(?:ion)?|expense(?:\s+limit)?|cap|maximum)\s+(?:up to\s+)?\$([0-9,]+)[^\.\n]{0,140}?section\s*179)',
                    s179_win,
                    re.IGNORECASE,
                ) if s179_win else []
                for m in s179_matches:
                    raw_val = m[0] or m[1]
                    try:
                        val = float(raw_val.replace(",", ""))
                        if "2026" in text_lower or "obbba" in text_lower:
                            s179_cap = 2560000.0
                        elif "2025" in text_lower:
                            s179_cap = 2500000.0
                        else:
                            s179_cap = 1220000.0
                        if val > s179_cap:
                            violations.append(
                                f"Section 179 expense limit contradiction: claimed ${val:,.0f} exceeds statutory limit of $1,220,000 for 2024 ($2,500,000 for 2025 OBBBA, $2,560,000 for 2026)"
                            )
                    except ValueError:
                        pass

            stale_2026_179_patterns = (
                "full cap ($1.29m)",
                "irc 179 ($1.29m cap)",
                "$1,220,000 (full basis 100%)",
                "$1,250,000 section 179 cap",
                "$3,130,000 section 179 phase-out threshold",
                "high-cap scenario ($1.25m statutory limit)",
                "above $3,130,000 in total asset purchases",
            )
            for st_179 in stale_2026_179_patterns:
                if st_179 in text_lower:
                    violations.append(
                        f"Section 179 2026 statutory limit contradiction: '{st_179}' contradicts 2026 OBBBA statutory deduction cap of $2,560,000 ($2.56M) and $4,090,000 phase-out threshold"
                    )
            if "$1,250,000" in text and "2026" in text_lower and re.search(r"in\s+2026[^\.\n]{0,140}?up\s+to\s+\$1,250,000\s+in\s+qualifying", text, re.IGNORECASE):
                violations.append(
                    "Section 179 2026 statutory limit contradiction: claiming 'In 2026 ... up to $1,250,000' contradicts 2026 OBBBA statutory deduction cap of $2,560,000"
                )

            stale_tcja_tokens = ("$18,340", "$22,238", "$3,898", "$29,238")
            for st_tok in stale_tcja_tokens:
                if st_tok in text and any(
                    kw in text_lower
                    for kw in ("tcja", "2027", "tax bracket", "federal tax", "federal income tax", "sunset")
                ):
                    violations.append(
                        f"Stale TCJA vs 2027 Sunset figure '{st_tok}' detected: contradicts ground-truth statutory engine ($19,181 TCJA tax, $23,530 Sunset tax, +$4,349 delta at $125k Single; $30,416 Sunset tax at $150k Single)"
                    )

            # Stale 2027 Sunset Head of Household standard deduction ($12,700 instead of $12,900)
            if "head_of_household: 12700" in text or "head_of_household' ? 12700" in text or 'head_of_household" ? 12700' in text:
                violations.append(
                    "Stale 2027 Sunset Head of Household standard deduction '12700' detected in calculation logic: ground-truth statutory baseline is $12,900"
                )

            # Stale pre-OBBBA bonus depreciation (20%, 60%, 80% claimed for 2026 instead of 100% P.L. 119-21 Sec. 70301)
            if "rembasis * 0.20" in text_lower or "rem179 * 0.20" in text_lower or "rembasis * 0.80" in text_lower or "rem179 * 0.80" in text_lower:
                violations.append(
                    "Stale bonus depreciation multiplier detected in workbench calculation logic: P.L. 119-21 Section 70301 permanently restored 100% (1.0) IRC 168(k) bonus depreciation"
                )
            if (
                "bonus" in text_lower
                and "depreciation" in text_lower
                and any(pct in text_lower for pct in ("20%", "40%", "60%", "80%"))
                and "2026" in text_lower
                and re.search(
                    r"(?:(?:20|40|60|80)%\s+(?:first-year\s+)?bonus\s+depreciation[^\.\n]{0,80}?2026|bonus\s+depreciation\s+(?:is|at|of|rate\s+is)\s+(?:20|40|60|80)%[^\.\n]{0,80}?2026|in\s+2026[^\.\n]{0,80}?(?:20|40|60|80)%\s+(?:first-year\s+)?bonus\s+depreciation)",
                    text_lower,
                )
            ):
                violations.append(
                    "Stale 2026 bonus depreciation rate (20%/40%/60%/80%) detected: P.L. 119-21 Section 70301 permanently restored 100% IRC 168(k) bonus depreciation for 2026"
                )

            # Unverified legacy $49/$79/$199 offer fallback in JS
            if "offer_price_usd || 49" in text or "offer_price_usd || 79" in text:
                violations.append(
                    "Unverified legacy offer_price_usd fallback ('49' or '79') detected in runtime script: contradicts ProfitHelm ($15 quick / $29 full) canonical pricing tiers"
                )

            # Corrupted subtraction syntax from aggressive hyphen replacement
            if "(1: 13.3% state rate)" in text or "(100%: 15% exclusion)" in text:
                violations.append(
                    "Corrupted mathematical subtraction syntax detected ('(1: 13.3% state rate)' or '(100%: 15% exclusion)'); must preserve minus sign in mathematical formulas"
                )

            # Un-capped or stale 2025 OASDI S-Corp FICA savings ($19,125, $13,180, or 2025 $13,193/$176,100 instead of 2026 $14,235 at $184,500 cap)
            if (
                "$19,125" in text
                or '"published_output": 19125' in text
                or "produces 19,125.00" in text_lower
                or "$13,180" in text
                or '"published_output": 13180' in text
                or "produces 13,180.00" in text_lower
                or '"published_output": 13193' in text
                or "produces 13,193.00" in text_lower
                or '"ss_wage_cap": 176100' in text
                or "const ssWageCap = 176100;" in text
                or "$13,193 in self-employment tax" in text
                or 'id="val-annual_fica_savings">$13,193<' in text
                or 'id="val-combined_tax_savings">$21,193<' in text
                or "+$13,193 Annual FICA Payroll Tax Saved" in text
                or "saves $13,193 in FICA" in text
                or "saves $13,193 annually" in text
            ) and (
                "s-corp" in text_lower or "reasonable salary" in text_lower or "reasonable-salary" in text_lower
            ):
                violations.append(
                    "Stale S-Corp FICA tax savings figure ('$19,125', '$13,180', or 2025 '$13,193'/'$176,100') detected: under the 2026 $184,500 Social Security OASDI wage base cap and 92.35% Schedule SE factor ($203,170 SE base on $220,000 net), verified savings at $95,000 salary is $14,235 ($11,098.00 OASDI + $3,136.93 Medicare)"
                )

            # Stale 2026 Single $125k OBBBA federal tax ($18,918 instead of $18,734 under Rev. Proc. 2025-32)
            if "$18,918" in text and ("2026" in text_lower or "obbba" in text_lower or "rev. proc. 2025-32" in text_lower):
                violations.append(
                    "Contradictory 2026 federal tax figure '$18,918' detected: under OBBBA (P.L. 119-21) and IRS Rev. Proc. 2025-32 ($16,100 standard deduction), Single $125,000 federal income tax is $18,734 in 2026 ($18,389.50 in 2027 at $16,600 standard deduction)"
                )

            # Rounded Section 301 tariff landed cost ($161,000 instead of $160,966 when MPF/HMF are $528.40/$237.50)
            if (
                '"published_output": 161000' in text
                or 'data-baseline-output="161000' in text
                or "produces 161,000.00" in text_lower
                or ("$161,000" in text and ("$528.40" in text or "$160,966" in text or "merchandise processing fee" in text_lower))
            ) and ("301" in text_lower and "tariff" in text_lower):
                violations.append(
                    "Inexact Section 301 tariff landed cost figure '$161,000' detected: ground-truth landed cost at $120,000 FOB + $34,200 duty + $6,000 freight + $528.40 MPF + $237.50 HMF is $160,966"
                )

            # Zero-income-tax state year-label contradiction ($10,539 post-sunset 2027 tax labeled as 2026 federal tax)
            if "$10,539 in 2026 federal tax" in text_lower or "$10,539 in 2027 post-sunset federal tax" in text_lower:
                violations.append(
                    "Zero-income-tax state year-label or 2027 post-sunset contradiction: '$10,539' uses repealed 2027 post-sunset brackets (10%/15%/25%) instead of enacted OBBBA (P.L. 119-21) permanent 10%-37% brackets"
                )

            # Year- and status-bound OBBBA (P.L. 119-21) & IRS Rev. Proc. 2025-32 / 2026-35 / Notice 2025-67 enforcement
            repealed_sunset_claims = (
                "under irc section 1(j) sunset reversion",
                "tcja sunset: federal marginal rates revert to 10%-39.6% on december 31, 2025",
                '"sunset_standard_deduction": 8600',
                '"sunset_standard_deduction":8600',
                "0% (expired dec 31, 2025)",
                "0.0 (expired dec 31, 2025)",
                "20% -> 0%",
                "$15,000 -> $8,600",
                "$30,000 -> $17,200",
                "2027 post-sunset (irc §1(j) reversion)",
                "2027 post-sunset statutory rate",
                'value="2027_sunset"',
                "sunset reversion ($8,600 single",
                "39.6% top marginal bracket and $8,600",
                "reverts from 37% to 39.6%",
            )
            for r_claim in repealed_sunset_claims:
                if r_claim in text_lower:
                    violations.append(
                        f"Repealed pre-OBBBA TCJA sunset claim '{r_claim}' presented as active 2026/2027 law: OBBBA (P.L. 119-21) permanently extended the 10%-37% brackets, 20% Section 199A QBI deduction, and enhanced standard deduction ($16,100 Single / $32,200 MFJ for 2026; $16,600 / $33,200 for 2027)"
                    )

            # In HTML/table/manifest contexts, reject pre-OBBBA $23,530 / +$4,349 / $19,941 sunset calculations
            # unless $23,530 / +$4,349 is explicitly labeled as a "Repealed Pre-OBBBA" comparison counterfactual on the federal hub
            is_state_spoke_ctx = bool(
                (context and re.search(r"irs-2027-tax-brackets/(?!index\.html)[a-z-]+", str(context).lower()))
                or re.search(
                    r'rel=["\']canonical["\'][^>]*href=["\'][^"\']*?/tools/irs-2027-tax-brackets/[a-z-]+/?["\']',
                    text_lower,
                )
            )
            has_unlabeled_sunset_output = (
                '"published_output": 23530' in text
                or '"published_output": 19941' in text
                or "$19,941" in text
                or (
                    ("$23,530" in text or "+$4,349" in text)
                    and (is_state_spoke_ctx or "repealed pre-obbba" not in text_lower)
                )
            )
            if (
                "<html" in text_lower
                or "<table" in text_lower
                or "calculation-manifest" in text_lower
                or (context and "irs-2027-tax-brackets" in str(context).lower())
            ) and has_unlabeled_sunset_output:
                violations.append(
                    "Repealed pre-OBBBA sunset calculation output ($23,530 / +$4,349 / $19,941) detected in active page/manifest: must evaluate enacted OBBBA (P.L. 119-21) 10%-37% progressive brackets and Rev. Proc. 2025-32 standard deductions"
                )

            # 2025 limits masquerading as 2026/2027 schedules
            stale_2025_in_2026_tokens = (
                "$15,000 single / $30,000 mfj",
                "<td>$15,000 (single) / $30,000 (mfj)</td>",
                "$23,500 (irc §402(g) cap)",
                "$23,500 (irc section 402(g) cap)",
                "14.4% (13.3% + 1.1% sdi)",
                "1.1% sdi)",
                "$15,240 ($12,103.00 social security + $3,136.93 medicare)",
            )
            for st_25 in stale_2025_in_2026_tokens:
                if st_25 in text_lower:
                    violations.append(
                        f"Stale 2025 or contradictory statutory limit '{st_25}' presented in 2026/2027 schedule: 2026 law requires $16,100 Single / $32,200 MFJ standard deduction (Rev. Proc. 2025-32), $24,500 401(k) cap (Notice 2025-67), $184,500 OASDI wage base, 1.3% CA SDI (14.6% top CA rate), 100% Section 168(k) bonus depreciation, and $14,235 S-Corp FICA savings"
                    )

            # Equipment Lease vs Section 179 capital expensing misattribution
            ctx_low_ph = f"{context or ''} {text_lower[:1200]}".lower()
            if "equipment-lease-tax-deduction" in ctx_low_ph and (
                "up to $2,560,000 in qualifying commercial equipment placed in service during the 2026 tax year" in text_lower
                or "standard capex allocation ($850k qualifying equipment)" in text_lower
                or "calculates first-year equipment expensing" in text_lower
            ):
                violations.append(
                    "Statutory authority misattribution on equipment-lease-tax-deduction: IRC Section 179 capital expensing assertions injected onto IRC Section 162(a)(3) / ASC 842 operating lease page"
                )

            # SaaS Runway catch-all pollution on non-runway ProfitHelm pages
            if (
                "12 to 18 months of net cash runway" in text_lower
                or "high-growth operator ($1.5m arr, 14-month runway)" in text_lower
            ):
                is_runway_ctx = any(
                    k in ctx_low_ph
                    for k in ("saas-runway", "burn-rate", "cash-runway", "going-concern", "verify_claim(profithelm)")
                ) or (not context and "<html" not in text_lower)
                if not is_runway_ctx:
                    violations.append(
                        "Statutory overlay misattribution: SaaS Runway (GAAP ASC 205-40) citation assertions and decision matrix injected onto non-runway page"
                    )

        elif tenant_norm == "prexvo":
            # PSLF qualifying payments: strictly 120 payments
            if "pslf" in text_lower or "public service" in text_lower:
                if "120 to 240 certified monthly payments" in text_lower and (
                    "pslf" in (context or "").lower()
                    or "public-service" in (context or "").lower()
                    or "pslf buyback calculator determines" in text_lower
                    or "pslf qualifying payment simulator determines" in text_lower
                ):
                    violations.append(
                        "PSLF payment requirement contradiction: claiming '120 to 240 certified monthly payments' for PSLF contradicts statutory requirement of 120 qualifying monthly payments under 34 CFR 685.219"
                    )
                pslf_matches = re.finditer(
                    r'(?:(?:pslf|public\s+service\s+loan\s+forgiveness)[^\.\n]{0,140}?(?<![a-zA-Z0-9_\\])(\d+)\s+(?:qualifying\s+)?(?:monthly\s+)?payments?|(?<![a-zA-Z0-9_\\])(\d+)\s+(?:qualifying\s+)?(?:monthly\s+)?payments?[^\.\n]{0,140}?(?:pslf|public\s+service\s+loan\s+forgiveness))',
                    prose_scan_text,
                    re.IGNORECASE,
                )
                for m_obj in pslf_matches:
                    p_str = m_obj.group(1) or m_obj.group(2)
                    span_low = m_obj.group(0).lower()
                    try:
                        payments = int(p_str)
                        if payments != 120:
                            # Allow sentences that explicitly pair 120-payment PSLF with 240/300/360-payment IDR/RAP forgiveness
                            has_explicit_120_pslf = bool(
                                re.search(
                                    r"(?:120[-\s]+(?:qualifying\s+|monthly\s+|certified\s+)?(?:payment|month)[^\.\n]{0,60}?(?:pslf|public\s+service)|(?:pslf|public\s+service)[^\.\n]{0,60}?120[-\s]+(?:qualifying\s+|monthly\s+|certified\s+)?(?:payment|month)|pslf\s*\(120)",
                                    span_low,
                                )
                            )
                            if not (payments in (240, 300, 360) and has_explicit_120_pslf):
                                violations.append(
                                    f"PSLF payment requirement contradiction: claimed {payments} payments contradicts statutory requirement of 120 qualifying monthly payments under 34 CFR 685.219"
                                )
                    except ValueError:
                        pass

            # Stale / erroneous 2026 HHS Poverty Guideline ($16,120) or RAP forgiveness term (120 to 240 months instead of 360)
            if "$16,120" in text and ("poverty" in text_lower or "fpl" in text_lower or "hhs" in text_lower):
                violations.append(
                    "Erroneous 2026 HHS Poverty Guideline '$16,120' detected: 91 FR 1797 sets 2026 1-person contiguous guideline at $15,960 ($5,680 per additional person)"
                )

            # Stale RAP Scenario A ($244.58 / $58,700) and Scenario B ($494.58 / $118,700) detection
            if "$244.58" in text or "$58,700" in text:
                violations.append(
                    "Stale RAP Scenario A calculation detected ($244.58 or $58,700): contradicts 2026 HHS poverty guideline under 91 FR 1797 ($15,960)"
                )
            if "$494.58" in text or "$118,700" in text:
                violations.append(
                    "Stale RAP Scenario B calculation detected ($494.58 or $118,700): contradicts 2026 HHS poverty guideline under 91 FR 1797 ($15,960)"
                )
            if "784.12" in text:
                violations.append(
                    "Stale ICR payment figure '784.12' detected: ground-truth 34 CFR 685.209(b) 12-year income-adjusted payment at $60k balance / 6.5% / $65k AGI is $651.25/mo"
                )
            if "48212.5" in text:
                violations.append(
                    "Invalid 225% FPL poverty exemption '48212.50' detected: ground-truth 2026 HHS 225% exemption is $35,910.00 (single at $15,960 FPL) or $48,690.00 (family size 2 at $21,640 FPL)"
                )
            if "family size 2 ($47,587.50" in text_lower and ("$248.23" in text or "$223.23" in text):
                violations.append(
                    "Prexvo RAP family-size contradiction: pairs family size 2 exemption with single-filer RAP payment"
                )
            if "$164.90/mo" in text and "$65,000" in text:
                violations.append(
                    "Prexvo RAP AGI contradiction: $164.90/mo RAP payment corresponds to $55,000 AGI, not $65,000 AGI"
                )

            # Unhydrated SSR calculator metric placeholders ($0.00 in primary repayment metrics)
            if "$0.00" in text and re.search(
                r'id=["\']metric-(?:rap_payment|ibr_payment|standard_10yr|tiered_standard)["\'][^>]*>\s*\$0\.00\s*<',
                text,
                re.IGNORECASE,
            ):
                violations.append(
                    "Unhydrated SSR calculator placeholder '$0.00' detected in primary repayment metric card; SSR output must reflect ground-truth engine evaluation"
                )

            # Incomplete IBR statutory payment rate cell in comparison table
            if "15%" in text and "discretionary" in text_lower and re.search(
                r'<td[^>]*>\s*15%\s+Discretionary\s*</td>', text, re.IGNORECASE
            ):
                violations.append(
                    "Incomplete IBR statutory rate '15% Discretionary' in comparison table cell: must specify '10% to 15% Discretionary' covering post-2014 new borrowers (10%) and pre-2014 borrowers (15%) under 34 CFR 685.209"
                )

            # Unverified $29/$39/$49 offer fallback in JS on consumer tenant Prexvo ($9 quick / $19 full)
            if "offer_price_usd || 29" in text or "offer_price_usd || 39" in text:
                violations.append(
                    "Unverified offer_price_usd fallback ('29' or '39') detected in runtime script: contradicts Prexvo ($9 quick / $19 full) canonical pricing tiers"
                )

            # Plan-specific contradiction: attributing 225% ($35,212.50) to IBR, PAYE, ICR, Tiered Standard, Grad PLUS, Refinance, or institutional pages
            if re.search(
                r"(?:ibr\s+hardship(?:\s+cap)?(?:\s+calculator)?|paye\s+sunset(?:\s+eligibility)?(?:\s+calculator)?|icr\s+repayment(?:\s+calculator)?|income[-\s]contingent\s+repayment|tiered\s+standard(?:\s+repayment)?(?:\s+calculator)?|grad\s+plus(?:\s+borrowing)?(?:\s+cap)?(?:\s+calculator)?|student\s+loan\s+refinance(?:\s+break[-\s]even)?(?:\s+calculator)?|parent\s+plus\s+repayment)\s+(?:determines\s+monthly\s+obligations\s+using\s+the\s+225\s+percent|subtracts\s+225\s+percent|under\s+title\s+iv\s+34\s+cfr\s+part\s+685\s+using\s+225%)",
                text_lower,
            ):
                violations.append(
                    "Prexvo plan-threshold contradiction: non-RAP plan (IBR, PAYE, ICR, Tiered Standard, Grad PLUS, Parent PLUS, or Refinance) misattributed to RAP 225% HHS Poverty Guideline"
                )
            if re.search(
                r"calculate\s+(?:tools\s+directory|disclaimers|methodology|privacy|about)\s+under\s+title\s+iv",
                text_lower,
            ):
                violations.append(
                    "Prexvo non-tool institutional page contains calculator template meta/prose ('Calculate ... under Title IV')"
                )
            ctx_low_px = (context or "").lower()
            if (
                ctx_low_px in ("tools/index.html", "disclaimers/index.html", "methodology/index.html")
                or 'rel="canonical" href="https://prexvo.com/tools/"' in text_lower
                or 'rel="canonical" href="https://prexvo.com/disclaimers/"' in text_lower
                or 'rel="canonical" href="https://prexvo.com/methodology/"' in text_lower
            ) and (
                'id="gsc-striking-overlay"' in text_lower
                or "student loan deferment calculator determines monthly obligations" in text_lower
            ):
                violations.append(
                    "Prexvo institutional/directory page overlay pollution: calculator striking-distance overlay injected onto non-calculator directory or institutional route"
                )
        elif tenant_norm == "gainhelm":
            # Unverified legacy $49/$79 offer fallback in JS on business tenant GainHelm ($15 quick / $29 full)
            if "offer_price_usd || 49" in text or "offer_price_usd || 79" in text:
                violations.append(
                    "Unverified legacy offer_price_usd fallback ('49' or '79') detected: contradicts GainHelm ($15 quick / $29 full) canonical pricing tiers"
                )
            # Unhydrated SSR calculator metric placeholders ($0.00 in primary compliance metrics)
            if "$0.00" in text and re.search(
                r'id=["\']metric-(?:soc2_total_cost|cmmc_total_cost|sprs_score|iso27001_total_cost|hipaa_penalty)["\'][^>]*>\s*\$0\.00\s*<',
                text,
                re.IGNORECASE,
            ):
                violations.append(
                    "Unhydrated SSR calculator placeholder '$0.00' detected in primary GainHelm compliance metric card; SSR output must reflect ground-truth engine evaluation"
                )
            # NIST SP 800-171 SPRS score bounds [-203, 110] and erroneous -196 minimum
            if "sprs" in text_lower:
                for sprs_m in re.finditer(
                    r"sprs\s+score\s+(?:of\s+)?([+-]?\d{1,4})\b",
                    text_lower,
                ):
                    try:
                        sprs_val = int(sprs_m.group(1))
                        if sprs_val > 110 or sprs_val < -203:
                            violations.append(
                                f"NIST SP 800-171 SPRS score contradiction: claimed {sprs_val} is outside statutory [-203, 110] bounds under DFARS 252.204-7019/7020"
                            )
                    except ValueError:
                        pass
                if re.search(r"(?:min(?:imum)?(?:\s+score)?|-196\s+to\s*\+?110|sprs[^\.\n]{0,40}-196\b)", text_lower):
                    if re.search(r"(?<![0-9])-196(?![0-9,.])", text_lower):
                        violations.append(
                            "NIST SP 800-171 SPRS minimum score contradiction: '-196' is erroneous; official DoD Methodology v1.2.1 minimum is -203 (44 5-pt, 14 3-pt, 51 1-pt, 1 0-pt)"
                        )
            # BLS SOC 15-1212 wage rate contradiction ($95/hr or $61.40/hr vs signed $121.67/hr loaded rate)
            if (
                "$95/hr" in text_lower
                or "$61.40/hr" in text_lower
                or "$61.40 per hour" in text_lower
                or "($61.40/hr)" in text_lower
            ):
                violations.append(
                    "BLS SOC 15-1212 wage benchmark contradiction: '$95/hr' or '$61.40/hr' contradicts cryptographically signed BLS OEWS dataset ($121.67/hr mean loaded hourly rate; $120,360 median annual wage)"
                )
            # ISO/IEC 27006-1:2024 auditor-day contradiction for 75-employee baseline (9.0 days / $16,200 vs signed 11.0 days / $21,450)
            if (
                "75-employee organization requires 9.0" in text_lower
                or "certification body fee ($16,200)" in text_lower
                or "combining $16,200.00 in registrar fees" in text_lower
                or "<td>46 to 85 employees</td>\n              <td>9.0 auditor days</td>" in text_lower
            ):
                violations.append(
                    "ISO/IEC 27006-1:2024 auditor-day contradiction: 75-employee baseline requires 11.0 Stage 1+2 auditor days ($21,450.00 registrar fee, $66,350.60 total cost) per signed AICPA/ISO dataset, not 9.0 auditor days ($16,200)"
                )
            # HIPAA 45 CFR 160.404 penalty cap & baseline exposure contradictions (2026 Tier 4 cap is $2,190,294 under 91 FR 3665 / 91 FR 66566)
            if (
                "$2,134,831" in text
                or "2134831" in text
                or "$2,067,813" in text
                or "2067813" in text
                or "$622,500" in text
                or '"published_output": 622500' in text
                or '<td class="td-plan-name">hipaa hitech tier 2 breach</td>' in text_lower
            ):
                if not any(hq in text_lower for hq in ("2023 cap", "2024 cap", "2025 cap", "historical")):
                    violations.append(
                        "HIPAA 45 CFR 160.404 statutory contradiction: contradicts 2026 HHS OCR Tier 4 annual cap ($2,190,294.00 under 91 FR 3665 / 91 FR 66566)"
                    )
            # SOC 2 / CMMC / PCI DSS / Cyber Insurance component & sum contradictions
            if (
                "cpa audit fee ($28,500)" in text_lower
                or "includes $28,500.00 in cpa attestation fees" in text_lower
                or ("$14,600.40" in text and "totals $78,100.00" in text_lower)
                or '"published_output": 78100.0' in text
                or "$28,000 cpa audit" in text_lower
                or "$20,500 ($121.67/hr bls" in text_lower
            ):
                violations.append(
                    "SOC 2 AICPA SSAE 18 component/sum contradiction: baseline 75-employee 3-TSC Type II cost is $78,100.40 ($37,000.00 CPA + $15,000.00 GRC + $11,500.00 pentest + $14,600.40 labor)"
                )
            if (
                "2,500 compromised ephi records" in text_lower
                or "2,500 ephi records" in text_lower
                or "2,500-record ephi breach" in text_lower
                or "$525,500 (" in text_lower
                or "$512,500 total hipaa" in text_lower
                or "2,500 records *" in text_lower
            ):
                violations.append(
                    "HIPAA 45 CFR 160.404 benchmark contradiction: canonical Tier 3 baseline uses 1,500 ePHI records ($387,500.00 remediation + $2,190,294.00 2026 cap = $2,577,794.00), not 2,500 records ($512,500 / $525,500)"
                )
            if (
                "c3pao fee ($47,000)" in text_lower
                or "$47,000.00 in accredited c3pao assessment fees" in text_lower
                or "($52,000 c3pao assessment" in text_lower
            ):
                violations.append(
                    "CMMC 2.0 Level 2 component contradiction: baseline is $48,500.00 C3PAO + $26,400.00 enclave + $46,234.60 remediation labor + $13,400.00 RPO = $134,534.60"
                )
            if (
                '"published_output": 38900' in text
                or "reduces its $5m policy limit premium by 28 percent to $38,900.00" in text_lower
            ):
                violations.append(
                    "Cyber Liability Insurance baseline contradiction: ground-truth formula output is $40,900.00 ($20,415.00 annual premium + $20,485.00 self-insured retention), not $38,900.00"
                )
            if (
                "quarterly asv scans ($4,800)" in text_lower
                or "$4,800.00 in quarterly asv scans" in text_lower
                or "$94,799.80" in text
            ):
                violations.append(
                    "PCI DSS v4.0.1 component contradiction: ground-truth formula uses $3,800.00 ASV + $13,200.00 CDE systems + $12,500.00 pentest + $21,900.60 remediation labor ($93,400.60 total), not $4,800.00 ASV or $94,799.80"
                )
            # GainHelm generic SOC 2 / CMMC / ISO 27006 overlay misattribution on specialized tools
            ctx_low_gh = f"{context or ''} {text_lower[:1200]}".lower()
            is_non_soc2_gh_tool = any(
                k in ctx_low_gh
                for k in (
                    "hipaa-violation",
                    "pci-dss",
                    "fedramp-authorization",
                    "hitrust-csf",
                    "penetration-testing",
                    "cyber-liability",
                    "iso-27001",
                    "nist-800-171-sprs",
                )
            )
            if is_non_soc2_gh_tool and (
                "determines enterprise compliance expenditures under aicpa ssae 18 (at-c section 205), dod 32 cfr part 170 (cmmc 2.0), and iso/iec 27006-1:2024 auditor-day tables" in text_lower
                or "first-year soc 2 type ii or iso 27001 compliance under aicpa ssae 18 and iso/iec 27006-1:2024 combines accredited cpa/registrar fees ($25,000 to $65,000)" in text_lower
            ):
                violations.append(
                    "GainHelm statutory authority misattribution: generic SOC 2 / CMMC / ISO 27006 template copy injected onto specialized compliance tool"
                )
        elif tenant_norm == "lienbond":
            ctx_low_lb = f"{context or ''} {text_lower[:1200]}".lower()
            is_wc_or_emr_ctx = any(k in ctx_low_lb for k in ("workers-comp", "workers comp", "class-code", "class code", "emr"))
            if is_wc_or_emr_ctx:
                if re.search(r"\b(?:irc\s*(?:section|sec\.?)?\s*3111|26\s*u\.s\.c\.?\s*3111)\b", prose_scan_text, re.IGNORECASE):
                    msg = "LienBond statutory misattribution: IRC Section 3111 (employer FICA payroll tax) is forbidden on NCCI workers compensation class-code / EMR tools"
                    if msg not in violations:
                        violations.append(msg)
                if re.search(r"\b29\s*cfr\s*(?:part\s*)?1904\b", prose_scan_text, re.IGNORECASE):
                    msg = "LienBond statutory misattribution: 29 CFR 1904 (OSHA recordkeeping) is forbidden on NCCI workers compensation class-code / EMR calculation tools"
                    if msg not in violations:
                        violations.append(msg)

            ctx_norm_lb = (context or "").strip().lower().replace("\\", "/")
            is_lb_directory_page = (
                ctx_norm_lb in ("index.html", "tools/index.html", "dist/index.html", "dist/tools/index.html")
                or ctx_norm_lb.endswith("/tools/index.html")
                or ctx_norm_lb.endswith("/dist/index.html")
                or ctx_norm_lb in ("tools", "tools/")
                or bool(
                    re.search(
                        r'<link\b[^>]*rel=["\']canonical["\'][^>]*href=["\']https?://[^/"\']+/(?:tools/)?["\']',
                        text_lower[:3000],
                    )
                )
                or '"@type": "collectionpage"' in text_lower[:5000]
                or '"@type":"collectionpage"' in text_lower[:5000]
                or "tools directory" in text_lower[:2000]
            )
            lb_route_hint = ctx_norm_lb
            if not ("license-bond" in lb_route_hint or "license bond" in lb_route_hint or "bid-bond" in lb_route_hint or "bid bond" in lb_route_hint):
                title_h1_m = re.search(r"<title[^>]*>([\s\S]*?)</title>|<h1[^>]*>([\s\S]*?)</h1>", text_lower[:4000])
                if title_h1_m:
                    lb_route_hint = f"{lb_route_hint} {title_h1_m.group(1) or ''} {title_h1_m.group(2) or ''}"
                else:
                    lb_route_hint = ctx_low_lb
            is_license_bond_ctx = (
                not is_lb_directory_page
                and ("license-bond" in lb_route_hint or "license bond" in lb_route_hint)
                and "bid-bond" not in lb_route_hint
                and "bid bond" not in lb_route_hint
            )
            is_bid_bond_ctx = (
                not is_lb_directory_page
                and ("bid-bond" in lb_route_hint or "bid bond" in lb_route_hint)
                and "license-bond" not in lb_route_hint
                and "license bond" not in lb_route_hint
            )
            if is_license_bond_ctx and re.search(r"\b(?:far\s*28\.101|5%\s*(?:to|-)\s*20%\s*penal\s*sum|bid\s+bond\s+penal\s+sum)\b", prose_scan_text, re.IGNORECASE):
                violations.append(
                    "LienBond bond-type misattribution: FAR 28.101 Bid Bond penal sum (5%-20%) applied to a Contractor License Bond page"
                )
            if is_bid_bond_ctx and re.search(r"\b(?:0\.75%\s*(?:to|-)\s*10%\s*(?:annual\s+)?license\s+bond|cslb\s+\$25,000\s+license\s+bond\s+rate)\b", prose_scan_text, re.IGNORECASE):
                violations.append(
                    "LienBond bond-type misattribution: Contractor License Bond annual underwriting rate applied to a FAR 28.101 Bid Bond penal sum page"
                )

            if "miller act" in text_lower:
                for m_ma in re.finditer(
                    r"miller\s+act[^\.\n]{0,140}?(?:threshold(?:\s+(?:of|is|exceeding|over|above|at))?|contracts?\s+(?:exceeding|over|above)|requires?\s+bonds?\s+(?:above|over|at))\s+\$([0-9,]+)",
                    prose_scan_text,
                    re.IGNORECASE,
                ):
                    try:
                        ma_val = float(m_ma.group(1).replace(",", ""))
                        if ma_val not in (150000.0, 35000.0):
                            violations.append(
                                f"LienBond Miller Act threshold contradiction: claimed ${ma_val:,.0f}; 40 U.S.C. 3131 / FAR 28.102-1 threshold is $150,000 ($35,000 alternative payment protection floor)"
                            )
                    except ValueError:
                        pass

        is_valid = len(violations) == 0
        if cache_key is not None:
            if len(self._VERIFY_CLAIM_CACHE) > 1024:
                self._VERIFY_CLAIM_CACHE.clear()
            self._VERIFY_CLAIM_CACHE[cache_key] = (is_valid, list(violations))
        return is_valid, violations

    def assert_tenant_isolation(self, tenant: str, text: str) -> None:
        """
        Asserts strict tenant boundary isolation.
        Raises PropertyContaminationError if foreign tokens or banned claims bleed across tenants.
        Zero em-dashes. Zero en-dashes.
        """
        is_valid, violations = self.verify_claim(tenant=tenant, text=text)
        if not is_valid:
            raise PropertyContaminationError(
                f"Tenant isolation assertion failed for '{tenant}': {violations[0]}"
            )


class TruthReconciliationEngine:
    """
    Deterministic Truth-Reconciliation and Auto-Remediation Engine.
    Binds prose, comparison tables, autonomous citation assertions, AI-mode decision matrices,
    JSON-LD structured schema, and interactive calculator JS logic to the versioned
    TenantFactStore ground-truth registry while stripping speculative filler.
    Zero LLM calls, 100% deterministic, idempotent, zero em-dashes, zero en-dashes.
    """

    VERSION: str = "2026.10.23-v2"

    SPECULATIVE_FILLER_REPLACEMENTS: Tuple[Tuple[str, str], ...] = (
        ("In today's rapidly evolving tax landscape, ", ""),
        ("In today's complex regulatory environment, ", ""),
        ("It is important to note that ", ""),
        ("It is worth noting that ", ""),
        ("Needless to say, ", ""),
        ("As a general rule of thumb, ", ""),
    )

    PROFITHELM_HTML_REPLACEMENTS: Tuple[Tuple[str, str], ...] = (
        ("with real-time scenario mo...", "with scenario analysis."),
        ("with real-time scenario ...", "with scenario analysis."),
        ("with real-time scenari...", "with scenario analysis."),
        ("divided by (1 - 0.133)", "divided by (1 minus 0.133)"),
        ("IRC Sections 1001, 1012, 1222, and 1411", "IRC Section 1001, Section 1012, Section 1222, and Section 1411"),
        ("IRC Sections 3111 and 3301", "IRC Section 3111 and Section 3301"),
        ("IRC Sections ", "IRC Section "),
        (
            "High-earner household evaluating SALT cap interaction, NIIT 3.8% surtax, and post-TCJA sunset rate schedules",
            "High-earner household evaluating SALT cap interaction, NIIT 3.8% surtax, and enacted OBBBA (P.L. 119-21) rate schedules",
        ),
        (
            "standard deductions, and post-TCJA sunset brackets.",
            "standard deductions, and enacted OBBBA brackets.",
        ),
        (
            "and post-TCJA sunset rate reversions (10, 15, 25, 28, 33, 35, and 39.6 percent) alongside",
            "and enacted OBBBA (P.L. 119-21) permanent brackets (10, 12, 22, 24, 32, 35, and 37 percent) alongside",
        ),
        # Stale 2024/2025 Section 179 caps and phaseout thresholds presented as 2026 rules
        ("$1,220,000 (Full Basis 100%)", "$2,560,000 (Full Basis 100%)"),
        ("up to $1,250,000 in qualifying commercial equipment", "up to $2,560,000 in qualifying commercial equipment"),
        ("above $3,130,000 in total asset purchases", "above $4,090,000 in total asset purchases"),
        ("$1,250,000 Section 179 Cap (IRC Section 179(b)(1))", "$2,560,000 Section 179 Cap (IRC Section 179(b)(1))"),
        ("$3,130,000 Section 179 Phase-Out Threshold (IRC 179(b)(2))", "$4,090,000 Section 179 Phase-Out Threshold (IRC 179(b)(2))"),
        ("CapEx Intensive Expansion ($3.6M Total Equipment Placed in Service)", "CapEx Intensive Expansion ($4.35M Total Equipment Placed in Service)"),
        ("Combine Remaining $780k Section 179 Allowance + IRC 168(k) Bonus", "Combine Remaining $2.30M Section 179 Allowance + IRC 168(k) Bonus"),
        ("$412,000 First-Year Combined Depreciation Tax Shield", "$1,522,500 First-Year Combined Depreciation Tax Shield"),
        ("High-Cap Scenario ($1.25M Statutory Limit)", "High-Cap Scenario ($2.56M Statutory Limit)"),
        ("&quot;cost&quot;: 1250000,", "&quot;cost&quot;: 2560000,"),
        ('"cost": 1250000,', '"cost": 2560000,'),
        ("IRC 179 ($1.29M Cap) / 168(k) 20% Bonus", "IRC 179 ($2.56M Cap) / 168(k) 100% Bonus"),
        ("Full Cap ($1.29M)", "Full Cap ($2.56M)"),
        # Stale 2026 Heavy SUV cap ($31,300 / $30,500 -> $32,000) and pre-OBBBA bonus depreciation (20%/60%/80% -> 100%)
        (
            "capped at a $31,300 Section 179 deduction in 2026",
            "capped at a $32,000 statutory Section 179 deduction (IRS Rev. Proc. 2025-32)",
        ),
        (
            "$31,300 statutory Section 179 cap ($30,500 prior-year inflation baseline)",
            "$32,000 statutory Section 179 cap (IRS Rev. Proc. 2025-32; $31,300 for 2025)",
        ),
        ("Heavy SUV 6,000 to 14,000 lbs ($110k / $31,300 SUV Cap)", "Heavy SUV 6,000 to 14,000 lbs ($110k / $32,000 SUV Cap)"),
        ("Heavy SUV 6,000 to 14,000 lbs GVWR ($31,300 IRC 179(b)(5) Cap + Bonus)", "Heavy SUV 6,000 to 14,000 lbs GVWR ($32,000 IRC 179(b)(5) Cap + 100% Bonus)"),
        ("Heavy SUVs (6,000-14,000 lbs, $31,300 Cap + Bonus)", "Heavy SUVs (6,000-14,000 lbs, $32,000 Cap + 100% Bonus)"),
        ("Heavy SUV Tax Savings ($31,300 Cap + Bonus)", "Heavy SUV Tax Savings ($32,000 Cap + 100% Bonus)"),
        ("<td>$31,300 + Bonus Depr.</td>", "<td>$32,000 + 100% Bonus Depr.</td>"),
        ("<td>$31,300 (IRC §179(b)(5))</td>", "<td>$32,000 (IRC §179(b)(5))</td>"),
        ("IRC §179(b)(5) $31,300 cap", "IRC §179(b)(5) $32,000 cap"),
        ("IRC \\u00a7179(b)(5) $31,300 cap", "IRC \\u00a7179(b)(5) $32,000 cap"),
        ("60% on balance (2024-2026 phase-down)", "100% on balance (P.L. 119-21 Sec. 70301)"),
        ("<td>60% on balance</td>", "<td>100% on balance</td>"),
        ("<td>$53,320 on $85,000 basis</td>", "<td>$68,000 on $85,000 basis</td>"),
        ("and 60% bonus depreciation under Section 168(k)", "and 100% bonus depreciation under Section 168(k)"),
        (
            "qualifies for an immediate first-year Section 179 expense allowance of up to $31,300 plus 60% bonus depreciation on the remaining basis. At 80% business use ($68,000 basis), your total first-year deduction reaches $53,320, reducing net income tax liability by $19,728 at the 37% marginal rate.",
            "qualifies for an immediate first-year Section 179 expense allowance of up to $32,000 plus 100% bonus depreciation on the remaining basis. At 80% business use ($68,000 basis), your total first-year deduction reaches $68,000, reducing net income tax liability by $25,160 at the 37% marginal rate.",
        ),
        (
            "qualifies for the IRC Section 280F heavy SUV allowance of up to $31,300 plus 60% bonus depreciation on the remaining basis. At 80% business use ($68,000 basis), your total first-year deduction reaches $53,320, reducing net income tax liability by $19,728 at a 37% marginal tax bracket.",
            "qualifies for the IRC Section 280F heavy SUV allowance of up to $32,000 plus 100% bonus depreciation on the remaining basis. At 80% business use ($68,000 basis), your total first-year deduction reaches $68,000, reducing net income tax liability by $25,160 at a 37% marginal tax bracket.",
        ),
        (
            'id="val-first_year_deduction">$53,320<',
            'id="val-first_year_deduction">$68,000<',
        ),
        (
            'id="val-tax_savings">$19,728<',
            'id="val-tax_savings">$25,160<',
        ),
        (
            'id="val-effective_cost">$65,272<',
            'id="val-effective_cost">$59,840<',
        ),
        # Inline calculator JS parity
        ("var suv179 = Math.min(cost, 31300);", "var suv179 = Math.min(cost, 32000);"),
        ("var suv179 = Math.min(cost, 30500);", "var suv179 = Math.min(cost, 32000);"),
        (
            "const suvCap = 31300 * busUse;\n      const suvBonus = Math.max(0, basis - suvCap) * 0.60;",
            "const suvCap = 32000 * busUse;\n      const suvBonus = Math.max(0, basis - suvCap) * 1.0;",
        ),
        (
            "Math.min(basis, 31300) + Math.max(0, basis - 31300) * 0.60",
            "Math.min(basis, 32000) + Math.max(0, basis - 32000) * 1.0",
        ),
        # 2027 Sunset Head of Household standard deduction ($12,700 -> $12,900) & runtime bonus depreciation (100% OBBBA)
        ("head_of_household: 12700", "head_of_household: 12900"),
        ("hoh: 12700", "hoh: 12900"),
        ("(status === 'head_of_household' ? 12700 : 8600)", "(status === 'head_of_household' ? 12900 : 8600)"),
        ("remBasis * 0.80", "remBasis * 1.0"),
        ("rem179 * 0.80", "rem179 * 1.0"),
        ("remBasis * 0.20", "remBasis * 1.0"),
        ("rem179 * 0.20", "rem179 * 1.0"),
        (
            "data.offer_price_usd || 49",
            'data.offer_price_usd || ((window.location && window.location.hostname && String(window.location.hostname).slice(0, 3) === "pre") ? 19 : 29)',
        ),
        (
            "data.offer_price_usd || (isPrexvo ? 19 : 49)",
            'data.offer_price_usd || ((window.location && window.location.hostname && String(window.location.hostname).slice(0, 3) === "pre") ? 19 : 29)',
        ),
        ("$19,125 in self-employment tax ($15,500 OASDI + $3,625 Medicare)", "$14,235 in self-employment tax ($11,098 OASDI + $3,137 Medicare)"),
        ("$13,180 in self-employment tax ($10,056 OASDI + $3,124 Medicare)", "$14,235 in self-employment tax ($11,098 OASDI + $3,137 Medicare)"),
        ("$13,193 in self-employment tax ($10,056 OASDI + $3,137 Medicare)", "$14,235 in self-employment tax ($11,098 OASDI + $3,137 Medicare)"),
        ("($10,056.40 OASDI savings below the $176,100 cap plus $3,123.60 Medicare savings)", "($11,098.00 OASDI savings below the $184,500 cap plus $3,136.93 Medicare savings)"),
        ("($10,056.40 OASDI savings below the $176,100 cap plus $3,136.93 Medicare savings)", "($11,098.00 OASDI savings below the $184,500 cap plus $3,136.93 Medicare savings)"),
        ("const ssWageCap = 176100;", "const ssWageCap = 184500;"),
        ('id="val-se_tax_savings">$13,180<', 'id="val-se_tax_savings">$14,235<'),
        ('id="val-se_tax_savings">$13,193<', 'id="val-se_tax_savings">$14,235<'),
        ('id="val-annual_fica_savings">$13,180<', 'id="val-annual_fica_savings">$14,235<'),
        ('id="val-annual_fica_savings">$13,193<', 'id="val-annual_fica_savings">$14,235<'),
        ('id="val-combined_tax_savings">$21,193<', 'id="val-combined_tax_savings">$22,235<'),
        ('id="val-sole_prop_se_tax">$27,705<', 'id="val-sole_prop_se_tax">$28,770<'),
        ('id="val-sole_prop_se_tax">$27,728<', 'id="val-sole_prop_se_tax">$28,770<'),
        ('id="val-scorp_fica_tax">$14,525<', 'id="val-scorp_fica_tax">$14,535<'),
        ("<td>$12,393</td>", "<td>$10,484</td>"),
        ("<td>$11,082</td>", "<td>$10,484</td>"),
        ("<td>$13,180</td>", "<td>$14,235</td>"),
        ("<td>$13,193</td>", "<td>$14,235</td>"),
        ("<td>$11,010</td>", "<td>$11,406</td>"),
        ("<td>$10,485</td>", "<td>$11,406</td>"),
        ("<td>$10,364</td>", "<td>$11,406</td>"),
        ("$27,713 Schedule C Self-Employment Tax", "$28,770 Schedule C Self-Employment Tax"),
        ("$27,728 Schedule C Self-Employment Tax", "$28,770 Schedule C Self-Employment Tax"),
        ("$27,728 Schedule SE Tax", "$28,770 Schedule SE Tax"),
        ("+$13,180 Annual FICA Payroll Tax Saved", "+$14,235 Annual FICA Payroll Tax Saved"),
        ("+$13,193 Annual FICA Payroll Tax Saved", "+$14,235 Annual FICA Payroll Tax Saved"),
        ("saves $13,180 in FICA taxes.", "saves $14,235 in FICA taxes."),
        ("saves $13,193 in FICA taxes.", "saves $14,235 in FICA taxes."),
        ("saves $13,193 annually in self-employment taxes", "saves $14,235 annually in self-employment taxes"),
        ("$13,193 Annual FICA Saved", "$14,235 Annual FICA Saved"),
        ("+$13,193 Self-Employment Tax Drag", "+$14,235 Self-Employment Tax Drag"),
        ("$13,193 Verified FICA Alpha", "$14,235 Verified FICA Alpha"),
        ("$13,193 Annual Payroll Tax Savings vs Sole Proprietorship", "$14,235 Annual Payroll Tax Savings vs Sole Proprietorship"),
        ("$34,425 Unstructured Pass-Through SE Tax", "$33,591 Unstructured Pass-Through SE Tax"),
        ("$32,549 Unstructured Pass-Through SE Tax", "$33,591 Unstructured Pass-Through SE Tax"),
        ("+$12,240 Medicare Surtax &amp; FICA Shield", "+$11,406 Medicare Surtax &amp; FICA Shield"),
        ("+$12,240 Medicare Surtax & FICA Shield", "+$11,406 Medicare Surtax & FICA Shield"),
        ("+$10,364 Medicare Surtax &amp; FICA Shield", "+$11,406 Medicare Surtax &amp; FICA Shield"),
        ("+$10,364 Medicare Surtax & FICA Shield", "+$11,406 Medicare Surtax & FICA Shield"),
        ("OASDI $176,100 Social Security Cap", "OASDI $184,500 Social Security Cap"),
        ("OASDI wage base limit ($176,100)", "OASDI wage base limit ($184,500)"),
        ("OASDI Social Security wage base cap ($176,100)", "OASDI Social Security wage base cap ($184,500)"),
        ("up to $176,100 OASDI base;", "up to $184,500 OASDI base;"),
        ("up to $176,100 per employee)", "up to $184,500 per employee)"),
        ('id="cliff-exposure-2026" class="calc-metric-value"><strong>$13,193 FICA Saved</strong>', 'id="cliff-exposure-2026" class="calc-metric-value"><strong>$14,235 FICA Saved</strong>'),
        ('data-range-low="$10,554" data-range-baseline="$13,193" data-range-high="$15,832"', 'data-range-low="$11,388" data-range-baseline="$14,235" data-range-high="$17,082"'),
        ('id="hero-range-low">$10,554<', 'id="hero-range-low">$11,388<'),
        ('id="hero-range-baseline">$13,193<', 'id="hero-range-baseline">$14,235<'),
        ('id="hero-range-high">$15,832<', 'id="hero-range-high">$17,082<'),
        ('data-baseline-output="13193.0">13,193<', 'data-baseline-output="14235.0">14,235<'),
        ('class="scenario-baseline">13,193<', 'class="scenario-baseline">14,235<'),
        ('class="scenario-ast-eval" data-tier="baseline">13,193<', 'class="scenario-ast-eval" data-tier="baseline">14,235<'),
        ('class="scenario-conservative">10,554.40<', 'class="scenario-conservative">11,388.00<'),
        ('class="scenario-moderate-contraction">11,873.70<', 'class="scenario-moderate-contraction">12,811.50<'),
        ('class="scenario-moderate-expansion">14,512.30<', 'class="scenario-moderate-expansion">15,658.50<'),
        ('class="scenario-aggressive">15,831.60<', 'class="scenario-aggressive">17,082.00<'),
        ("ss_wage_cap=140880", "ss_wage_cap=147600"),
        ("ss_wage_cap=176100", "ss_wage_cap=184500"),
        ("ss_wage_cap=211320", "ss_wage_cap=221400"),
        # 2026 vs 2027 Single $125k OBBBA reconciliation ($18,918 -> $18,734 in 2026; $18,638 in 2027)
        ("$18,918 ($25,358 w/ CA)", "$18,734 ($25,621 w/ CA)"),
        ("$18,918 2026 Federal Income Tax", "$18,734 2026 Federal Income Tax"),
        ("$18,734 2027 OBBBA Federal Tax", "$18,638 2027 OBBBA Federal Tax"),
        ('id="cliff-exposure-2027" class="calc-metric-value"><strong>$18,734 Federal Tax</strong>', 'id="cliff-exposure-2027" class="calc-metric-value"><strong>$18,638 Federal Tax</strong>'),
        ("-$184 Chained-CPI Indexing Relief", "-$96 Chained-CPI Indexing Relief"),
        # Corrupted mathematical subtraction syntax
        ("(1: 13.3% state rate)", "(1 - 13.3% state rate)"),
        ("(100%: 15% exclusion)", "(100% - 15% exclusion)"),
        # S-Corp reasonable salary OASDI wage base cap reconciliation ($19,125 / $13,180 / 2025 $13,193 -> 2026 $14,235)
        (
            '"formula": "round((net_business_income - reasonable_w2_salary) * 0.153, 0)",\n  "inputs": {\n    "net_business_income": 225000.0,\n    "reasonable_w2_salary": 100000.0\n  },\n  "published_output": 19125.0,',
            '"formula": "round((min(net_business_income * 0.9235, ss_wage_cap) - min(reasonable_salary, ss_wage_cap)) * 0.124 + ((net_business_income * 0.9235) - reasonable_salary) * 0.029, 0)",\n  "inputs": {\n    "net_business_income": 220000.0,\n    "reasonable_salary": 95000.0,\n    "ss_wage_cap": 184500.0\n  },\n  "published_output": 14235.0,',
        ),
        (
            '"formula": "round((oasdi_taxable_delta * 0.124) + (medicare_taxable_delta * 0.029), 0)",\n  "inputs": {\n    "oasdi_taxable_delta": 81100.0,\n    "medicare_taxable_delta": 107425.0\n  },\n  "published_output": 13180.0,',
            '"formula": "round((min(net_business_income * 0.9235, ss_wage_cap) - min(reasonable_salary, ss_wage_cap)) * 0.124 + ((net_business_income * 0.9235) - reasonable_salary) * 0.029, 0)",\n  "inputs": {\n    "net_business_income": 220000.0,\n    "reasonable_salary": 95000.0,\n    "ss_wage_cap": 184500.0\n  },\n  "published_output": 14235.0,',
        ),
        (
            '"inputs": {\n    "net_business_income": 220000.0,\n    "reasonable_salary": 95000.0,\n    "ss_wage_cap": 176100.0\n  },\n  "published_output": 13193.0,',
            '"inputs": {\n    "net_business_income": 220000.0,\n    "reasonable_salary": 95000.0,\n    "ss_wage_cap": 184500.0\n  },\n  "published_output": 14235.0,',
        ),
        (
            "Deterministic evaluation of round((net_business_income: reasonable_w2_salary) * 0.153, 0) produces 19,125.00.",
            "Deterministic evaluation of round((min(net_business_income * 0.9235, ss_wage_cap) - min(reasonable_salary, ss_wage_cap)) * 0.124 + ((net_business_income * 0.9235) - reasonable_salary) * 0.029, 0) produces 14,235.00.",
        ),
        (
            "Deterministic evaluation of round((net_business_income - reasonable_w2_salary) * 0.153, 0) produces 19,125.00.",
            "Deterministic evaluation of round((min(net_business_income * 0.9235, ss_wage_cap) - min(reasonable_salary, ss_wage_cap)) * 0.124 + ((net_business_income * 0.9235) - reasonable_salary) * 0.029, 0) produces 14,235.00.",
        ),
        (
            "Deterministic evaluation of round((oasdi_taxable_delta * 0.124) + (medicare_taxable_delta * 0.029), 0) produces 13,180.00.",
            "Deterministic evaluation of round((min(net_business_income * 0.9235, ss_wage_cap) - min(reasonable_salary, ss_wage_cap)) * 0.124 + ((net_business_income * 0.9235) - reasonable_salary) * 0.029, 0) produces 14,235.00.",
        ),
        (
            "Deterministic evaluation of round(oasdi_savings + medicare_savings, 0) produces 13,180.00.",
            "Deterministic evaluation of round((min(net_business_income * 0.9235, ss_wage_cap) - min(reasonable_salary, ss_wage_cap)) * 0.124 + ((net_business_income * 0.9235) - reasonable_salary) * 0.029, 0) produces 14,235.00.",
        ),
        (
            "Deterministic evaluation of round((min(net_business_income * 0.9235, ss_wage_cap) - min(reasonable_salary, ss_wage_cap)) * 0.124 + ((net_business_income * 0.9235) - reasonable_salary) * 0.029, 0) produces 13,193.00.",
            "Deterministic evaluation of round((min(net_business_income * 0.9235, ss_wage_cap) - min(reasonable_salary, ss_wage_cap)) * 0.124 + ((net_business_income * 0.9235) - reasonable_salary) * 0.029, 0) produces 14,235.00.",
        ),
        # Treasury yield calculator state TEY table reconciliation
        ("<td>10.90%</td>\n                  <td>5.64%</td>", "<td>10.90%</td>\n                  <td>5.84%</td>"),
        ("<td>10.75%</td>\n                  <td>5.62%</td>", "<td>10.75%</td>\n                  <td>5.82%</td>"),
        ("<td>9.00%</td>\n                  <td>5.46%</td>", "<td>9.00%</td>\n                  <td>5.63%</td>"),
        ('<td><span class="badge-tag">5.64% TEY</span></td>', '<td><span class="badge-tag">5.84% TEY</span></td>'),
        ('<td><span class="badge-tag">5.62% TEY</span></td>', '<td><span class="badge-tag">5.82% TEY</span></td>'),
        ('<td><span class="badge-tag">5.46% TEY</span></td>', '<td><span class="badge-tag">5.63% TEY</span></td>'),
        # Section 301 tariff landed cost reconciliation ($161,000 -> $160,966)
        (
            '"freight_and_mpf_hmf": 6800.0',
            '"freight_and_mpf_hmf": 6766.0',
        ),
        (
            '"published_output": 161000.0',
            '"published_output": 160966.0',
        ),
        (
            "Deterministic evaluation of round(fob_value * (1.0 + section_301_rate + base_mfn_rate) + freight_and_mpf_hmf, 0) produces 161,000.00.",
            "Deterministic evaluation of round(fob_value * (1.0 + section_301_rate + base_mfn_rate) + freight_and_mpf_hmf, 0) produces 160,966.00.",
        ),
        # Equipment Lease Tax Deduction overlay misattribution of Section 179 purchase caps
        (
            "In 2026, Equipment Lease Tax Deduction under IRC Section 179 and Section 168(k) allows businesses to expense up to $2,560,000 in qualifying commercial equipment placed in service, phasing out dollar-for-dollar above $4,090,000 in total asset purchases. Remaining basis qualifies for 20% first-year bonus depreciation and MACRS recovery on IRS Form 4562.",
            "Under IRC Section 162(a)(3) and GAAP ASC 842, operating equipment lease payments are 100% deductible as ordinary business expenses in the period incurred without upfront capital expenditure, whereas financed equipment purchases utilize IRC Section 179 ($32,000 Heavy SUV cap) and 100% Section 168(k) bonus depreciation ($68,000 first-year write-off on $85,000 at 80% business use).",
        ),
        (
            "or default to First-In, First-Out (FIFO) on Form 8949.",
            "or apply the statutory First-In, First-Out (FIFO) sequence on Form 8949.",
        ),
    )

    PREXVO_IBR_PAYE_HTML_REPLACEMENTS: Tuple[Tuple[str, str], ...] = (
        (
            "Under Title IV regulation 34 CFR Part 685, IBR Hardship Cap Calculator determines monthly obligations using the 225 percent HHS Poverty Guideline exemption ($35,212.50 protected single-filer income) and a 10 percent discretionary rate. Qualifying borrowers receive a 100 percent unpaid interest subsidy and full principal forgiveness after 120 to 240 certified monthly payments.",
            "Under Title IV regulation 34 CFR 685.209 and 20 U.S.C. 1098e, IBR Hardship Cap Calculator determines monthly obligations using the 150 percent HHS Poverty Guideline exemption ($23,475 protected single-filer income) and a 10 to 15 percent discretionary rate capped at the 10-year Standard Repayment ceiling, with principal forgiveness after 240 to 300 qualifying payments.",
        ),
        (
            "Under Title IV regulation 34 CFR Part 685, PAYE Sunset Eligibility determines monthly obligations using the 225 percent HHS Poverty Guideline exemption ($35,212.50 protected single-filer income) and a 10 percent discretionary rate. Qualifying borrowers receive a 100 percent unpaid interest subsidy and full principal forgiveness after 120 to 240 certified monthly payments.",
            "Under Title IV regulation 34 CFR 685.209 and 20 U.S.C. 1098e, PAYE Sunset Eligibility determines monthly obligations using the 150 percent HHS Poverty Guideline exemption ($23,475 protected single-filer income) and a 10 to 15 percent discretionary rate capped at the 10-year Standard Repayment ceiling, with principal forgiveness after 240 to 300 qualifying payments.",
        ),
        (
            "Calculate IBR Hardship Cap under Title IV 34 CFR Part 685 using 225% HHS Poverty Guidelines, discretionary income caps, and forgiveness rules.",
            "Calculate IBR Hardship Cap under Title IV 34 CFR 685.209 using 150% HHS Poverty Guidelines ($23,475 single exemption), hardship caps, and forgiveness rules.",
        ),
        (
            "Calculate PAYE Sunset Eligibility under Title IV 34 CFR Part 685 using 225% HHS Poverty Guidelines, discretionary income caps, and forgiveness rules.",
            "Calculate PAYE Sunset Eligibility under Title IV 34 CFR 685.209 using 150% HHS Poverty Guidelines ($23,475 single exemption), hardship caps, and forgiveness rules.",
        ),
        (
            "Under 34 CFR Part 685, ibr hardship cap calculator subtracts 225 percent of the applicable HHS Poverty Guideline from Adjusted Gross Income and assesses 10 percent of discretionary income divided by 12, with 100 percent of unpaid monthly interest waived.",
            "Under 34 CFR 685.209 and 20 U.S.C. 1098e, ibr hardship cap calculator subtracts 150 percent of the applicable HHS Poverty Guideline ($23,475 single baseline) from Adjusted Gross Income and assesses 10 percent (post-2014 new borrowers) or 15 percent (pre-2014 borrowers) of discretionary income divided by 12, capped at the 10-year Standard Repayment amount.",
        ),
        (
            "Under 34 CFR Part 685, paye sunset eligibility calculator subtracts 225 percent of the applicable HHS Poverty Guideline from Adjusted Gross Income and assesses 10 percent of discretionary income divided by 12, with 100 percent of unpaid monthly interest waived.",
            "Under 34 CFR 685.209 and 20 U.S.C. 1098e, paye sunset eligibility calculator subtracts 150 percent of the applicable HHS Poverty Guideline ($23,475 single baseline) from Adjusted Gross Income and assesses 10 percent of discretionary income divided by 12, capped at the 10-year Standard Repayment amount.",
        ),
        (
            "<td>225% Federal Poverty Exemption ($35,212.50 Single RAP Baseline)</td>\n          <td>2026 RAP / IBR with 100% Unpaid Interest Waiver</td>\n          <td><strong>$2,244 Annual Payment Reduction + $1,420 Annual Interest Subsidy (34 CFR 685.209)</strong></td>",
            "<td>150% Federal Poverty Exemption ($23,475 Single IBR/PAYE Baseline)</td>\n          <td>2026 IBR / PAYE Hardship Cap vs RAP Transition Evaluation</td>\n          <td><strong>$179.38/mo Post-2014 IBR/PAYE Payment Capped Below 10-Year Standard (34 CFR 685.209)</strong></td>",
        ),
        (
            "Single borrower at $65,000 AGI with 225% HHS poverty exemption ($248.23/mo RAP payment).",
            "Single borrower at $65,000 AGI with 150% HHS poverty exemption ($23,475 protected baseline).",
        ),
        (
            "225% FPL ($35,212.50)",
            "150% FPL ($23,475)",
        ),
    )

    PREXVO_ALL_HTML_REPLACEMENTS: Tuple[Tuple[str, str], ...] = (
        (
            "matching up to $50 per month in principal reduction.",
            "matching up to $50 in monthly principal reduction.",
        ),
        (
            "data.offer_price_usd || 29",
            'data.offer_price_usd || ((window.location && window.location.hostname && String(window.location.hostname).slice(0, 3) === "pre") ? 19 : 29)',
        ),
        (
            "data.offer_price_usd || (isPrexvo ? 19 : 49)",
            'data.offer_price_usd || ((window.location && window.location.hostname && String(window.location.hostname).slice(0, 3) === "pre") ? 19 : 29)',
        ),
        # Clarify RAP vs Old IBR 15% baseline in comparison tables
        (
            "<td>Prior Baseline (150% Poverty)</td>\n                  <td>$519.06 / mo</td>",
            "<td>Prior Baseline (150% Poverty, 15% Old IBR)</td>\n                  <td>$519.06 / mo</td>",
        ),
        # PSLF Buyback & PSLF Simulator overlay/prose 120-payment accuracy
        (
            "Under Title IV regulation 34 CFR Part 685, PSLF Buyback Calculator determines monthly obligations using the 225 percent HHS Poverty Guideline exemption ($35,212.50 protected single-filer income) and a 10 percent discretionary rate. Qualifying borrowers receive a 100 percent unpaid interest subsidy and full principal forgiveness after 120 to 240 certified monthly payments.",
            "Under 34 CFR 685.219(g), the PSLF Buyback Hold Harmless provision allows federal Direct Loan borrowers with 120 months of certified public service employment to buy back eligible deferment or forbearance months at the historical IDR rate, achieving tax-free forgiveness after 120 qualifying monthly payments.",
        ),
        (
            "Under Title IV regulation 34 CFR Part 685, PSLF Qualifying Payment Simulator determines monthly obligations using the 225 percent HHS Poverty Guideline exemption ($35,212.50 protected single-filer income) and a 10 percent discretionary rate. Qualifying borrowers receive a 100 percent unpaid interest subsidy and full principal forgiveness after 120 to 240 certified monthly payments.",
            "Under 34 CFR 685.219, Public Service Loan Forgiveness (PSLF) discharges 100 percent of remaining federal Direct Loan principal and interest tax-free after 120 qualifying monthly payments under an eligible income-driven repayment plan (RAP, IBR, PAYE, or ICR) while employed full-time by a qualifying public service employer.",
        ),
        # ICR & Parent PLUS 100% poverty ($15,650) accuracy
        (
            "Under Title IV regulation 34 CFR Part 685, ICR Repayment Calculator determines monthly obligations using the 225 percent HHS Poverty Guideline exemption ($35,212.50 protected single-filer income) and a 10 percent discretionary rate. Qualifying borrowers receive a 100 percent unpaid interest subsidy and full principal forgiveness after 120 to 240 certified monthly payments.",
            "Under Title IV regulation 34 CFR 685.209(b), the Income-Contingent Repayment (ICR) plan calculates monthly obligations as the lesser of 20 percent of discretionary income above 100 percent of the HHS Poverty Guideline ($15,650 single baseline) or a 12-year fixed payment adjusted by income, with forgiveness after 300 qualifying payments.",
        ),
        (
            "Under 34 CFR Part 685, icr repayment calculator subtracts 225 percent of the applicable HHS Poverty Guideline from Adjusted Gross Income and assesses 10 percent of discretionary income divided by 12, with 100 percent of unpaid monthly interest waived.",
            "Under 34 CFR 685.209(b), icr repayment calculator subtracts 100 percent of the applicable HHS Poverty Guideline ($15,650 single baseline) from Adjusted Gross Income and assesses the lesser of 20 percent of discretionary income divided by 12 or a 12-year income-adjusted fixed payment.",
        ),
        (
            "Calculate ICR Repayment under Title IV 34 CFR Part 685 using 225% HHS Poverty Guidelines, discretionary income caps, and forgiveness rules.",
            "Calculate ICR Repayment under Title IV 34 CFR 685.209(b) using 100% HHS Poverty Guidelines ($15,650 single baseline) and 20% discretionary income rules.",
        ),
        (
            "Calculate Parent PLUS Repayment Strategy under Title IV 34 CFR Part 685 using 225% HHS Poverty Guidelines, discretionary income caps, and forgiveness rules.",
            "Calculate Parent PLUS Repayment Strategy under Title IV 34 CFR 685.209(b) using Direct Consolidation and ICR 100% HHS Poverty Guideline ($15,650) rules.",
        ),
        # Tiered Standard 34 CFR 685.208 accuracy
        (
            "Under Title IV regulation 34 CFR Part 685, Tiered Standard Repayment determines monthly obligations using the 225 percent HHS Poverty Guideline exemption ($35,212.50 protected single-filer income) and a 10 percent discretionary rate. Qualifying borrowers receive a 100 percent unpaid interest subsidy and full principal forgiveness after 120 to 240 certified monthly payments.",
            "Under Title IV regulation 34 CFR 685.208, Tiered Standard Repayment determines fixed monthly obligations based on total entering Direct Loan principal across four statutory amortization tiers of 10, 12, 15, 20, and 30 years (120 to 360 monthly payments) with a $50 minimum monthly payment.",
        ),
        (
            "Under 34 CFR Part 685, tiered standard repayment calculator subtracts 225 percent of the applicable HHS Poverty Guideline from Adjusted Gross Income and assesses 10 percent of discretionary income divided by 12, with 100 percent of unpaid monthly interest waived.",
            "Under 34 CFR 685.208, tiered standard repayment calculator determines fixed monthly obligations by amortizing total Direct Loan principal across statutory 120, 180, 240, or 360 monthly payment tiers based on entering loan balance.",
        ),
        (
            "Calculate Tiered Standard Repayment under Title IV 34 CFR Part 685 using 225% HHS Poverty Guidelines, discretionary income caps, and forgiveness rules.",
            "Calculate Tiered Standard Repayment under Title IV 34 CFR 685.208 across 10, 12, 15, 20, and 30-year fixed amortization schedules by loan balance.",
        ),
        # Grad PLUS Borrowing Cap HEA Section 455(a) & 34 CFR 685.203 accuracy
        (
            "Under Title IV of the Higher Education Act and 34 CFR 685.208, the Tiered Standard Repayment schedule assigns fixed amortization horizons of 10, 15, 20, or 25 years (120 to 300 monthly payments) strictly by total entering student loan balance, independent of borrower Adjusted Gross Income.",
            "Under Title IV of the Higher Education Act (20 U.S.C. 1087e) and 34 CFR 685.203, federal graduate borrowing caps limit Direct Unsubsidized Loans to $20,500 annually ($138,500 aggregate cap), while Grad PLUS and private supplemental financing cover remaining certified Cost of Attendance.",
        ),
        (
            "Under Title IV regulation 34 CFR Part 685, Grad PLUS Borrowing Cap determines monthly obligations using the 225 percent HHS Poverty Guideline exemption ($35,212.50 protected single-filer income) and a 10 percent discretionary rate. Qualifying borrowers receive a 100 percent unpaid interest subsidy and full principal forgiveness after 120 to 240 certified monthly payments.",
            "Under Title IV of the Higher Education Act (20 U.S.C. 1087e) and 34 CFR 685.203, Grad PLUS Borrowing Cap models the $20,500 annual Direct Unsubsidized Loan ceiling, the $138,500 aggregate graduate limit, and Cost of Attendance funding gaps.",
        ),
        (
            "Under 34 CFR Part 685, grad plus borrowing cap calculator subtracts 225 percent of the applicable HHS Poverty Guideline from Adjusted Gross Income and assesses 10 percent of discretionary income divided by 12, with 100 percent of unpaid monthly interest waived.",
            "Under HEA Section 455(a) and 34 CFR 685.203, grad plus borrowing cap calculator subtracts the $20,500 annual Direct Unsubsidized Loan limit and institutional aid from certified Cost of Attendance to quantify residual graduate funding gaps.",
        ),
        (
            "Calculate Grad PLUS Borrowing Cap under Title IV 34 CFR Part 685 using 225% HHS Poverty Guidelines, discretionary income caps, and forgiveness rules.",
            "Calculate Graduate Direct Unsubsidized ($20,500 annual / $138,500 aggregate) and Grad PLUS borrowing caps under Title IV HEA and 34 CFR 685.203.",
        ),
        # Student Loan Refinance Break-Even accuracy
        (
            "Under Title IV regulation 34 CFR Part 685, Student Loan Refinance Break-Even vs Title IV Protection Calculator determines monthly obligations using the 225 percent HHS Poverty Guideline exemption ($35,212.50 protected single-filer income) and a 10 percent discretionary rate. Qualifying borrowers receive a 100 percent unpaid interest subsidy and full principal forgiveness after 120 to 240 certified monthly payments.",
            "Under Truth in Lending Act (TILA) Regulation Z (12 CFR Part 1026) and Title IV benefit forfeiture rules, the Student Loan Refinance Break-Even Calculator compares private APR interest savings against the permanent forfeiture of federal IDR subsidies and PSLF forgiveness.",
        ),
        (
            "Under 34 CFR Part 685, student loan refinance break even calculator subtracts 225 percent of the applicable HHS Poverty Guideline from Adjusted Gross Income and assesses 10 percent of discretionary income divided by 12, with 100 percent of unpaid monthly interest waived.",
            "Under 12 CFR Part 1026 and Title IV benefit forfeiture rules, student loan refinance break even calculator compares private refinance interest savings against the dollar value of forfeited federal IDR subsidies and PSLF forgiveness. Refinancing federal student loans permanently waives federal protections.",
        ),
        (
            "Calculate Student Loan Refinance Break: Even vs Title IV Protection under Title IV 34 CFR Part 685 using 225% HHS Poverty Guidelines, discretionary.",
            "Compare student loan refinance interest savings against forfeited Title IV IDR subsidies and PSLF forgiveness under 34 CFR Part 685.",
        ),
        # Income-Based Student Loan Repayment Calculator accuracy
        (
            "Under Title IV regulation 34 CFR Part 685, Income-Based Student Loan Repayment Calculator determines monthly obligations using the 225 percent HHS Poverty Guideline exemption ($35,212.50 protected single-filer income) and a 10 percent discretionary rate. Qualifying borrowers receive a 100 percent unpaid interest subsidy and full principal forgiveness after 120 to 240 certified monthly payments.",
            "Under Title IV regulation 34 CFR 685.209 and 20 U.S.C. 1098e, the Income-Based Student Loan Repayment Calculator compares 150 percent HHS Poverty Guideline ($23,475 single baseline) IBR payments against the 225 percent ($35,212.50) Repayment Assistance Plan (RAP) and 10-year Standard ceilings.",
        ),
        (
            "Under 34 CFR Part 685, income based student loan repayment calculator subtracts 225 percent of the applicable HHS Poverty Guideline from Adjusted Gross Income and assesses 10 percent of discretionary income divided by 12, with 100 percent of unpaid monthly interest waived.",
            "Under 34 CFR 685.209 and 20 U.S.C. 1098e, income based student loan repayment calculator subtracts 150 percent of the applicable HHS Poverty Guideline ($23,475 single baseline) for IBR or 225 percent ($35,212.50) for RAP from Adjusted Gross Income to determine monthly obligations.",
        ),
        (
            "Calculate Income-Based Student Loan Repayment under Title IV 34 CFR Part 685 using 225% HHS Poverty Guidelines, discretionary income caps, and.",
            "Calculate Income-Based Repayment (IBR) and RAP monthly payments under Title IV 34 CFR 685.209 using 150% and 225% HHS Poverty Guidelines.",
        ),
        # Married Filing Separately meta truncation repair
        (
            "Calculate Married Filing Separately Student Loan Tax vs IDR Calculator under Title IV 34 CFR Part 685 using 225% HHS Poverty Guidelines, discretionary.",
            "Compare Married Filing Separately vs Jointly student loan payments under 34 CFR 685.209 against lost IRC tax credits to maximize net household savings.",
        ),
        # Prexvo inline ICR 12-year base rounding parity ($601.15 * incomeFactor -> $651.25)
        (
            "const icrOptionB = amortize(balance, rate, 144) * incomeFactor;",
            "const icrOptionB = (Math.round(amortize(balance, rate, 144) * 100) / 100) * incomeFactor;",
        ),
    )

    GAINHELM_HTML_REPLACEMENTS: Tuple[Tuple[str, str], ...] = (
        (
            "data.offer_price_usd || 49",
            'data.offer_price_usd || ((window.location && window.location.hostname && String(window.location.hostname).slice(0, 3) === "pre") ? 19 : 29)',
        ),
        (
            "data.offer_price_usd || (isPrexvo ? 19 : 49)",
            'data.offer_price_usd || ((window.location && window.location.hostname && String(window.location.hostname).slice(0, 3) === "pre") ? 19 : 29)',
        ),
        ("SPRS score of 115", "SPRS score of 110"),
        ("($95/hr)", "($121.67/hr)"),
        ("($61.40/hr)", "($121.67/hr)"),
        ("$61.40 per hour base wage", "$121.67 per hour loaded wage"),
        (
            "$14,600.40 in internal security engineering labor (120 hours at $121.67/hr), total first-year compliance investment totals $78,100.00",
            "$14,600.40 in internal security engineering labor (120 hours at $121.67/hr), total first-year compliance investment totals $78,100.40",
        ),
        (
            "a 75-employee enterprise incurs a baseline SOC 2 Type II total outlay of $78,100.00",
            "a 75-employee enterprise incurs a baseline SOC 2 Type II total outlay of $78,100.40",
        ),
        ("<strong>$78,100 SOC 2 TCO</strong>", "<strong>$78,100.40 SOC 2 TCO</strong>"),
        ("$78,100 Automated GRC SOC 2 Type II", "$78,100.40 Automated GRC SOC 2 Type II"),
        ("<strong>$78,100 Verified SOC 2 Baseline</strong>", "<strong>$78,100.40 Verified SOC 2 Baseline</strong>"),
        ("$78,100 Net Type II Audit TCO", "$78,100.40 Net Type II Audit TCO"),
        (
            '<td id="comp-live-tax" class="calc-metric-value"><strong>$78,100</strong></td>',
            '<td id="comp-live-tax" class="calc-metric-value"><strong>$78,100.40</strong></td>',
        ),
        (
            '<td class="td-plan-name">HIPAA HITECH Tier 2 Breach</td>',
            '<td class="td-plan-name">HIPAA HITECH Tier 3 Breach</td>',
        ),
        ("$2,134,831", "$2,190,294"),
        ("2134831", "2190294"),
        ("$2,067,813", "$2,190,294"),
        ("2067813", "2190294"),
        ("$94,799.80", "$93,400.60"),
        ("94799.80", "93400.60"),
        ("$94,800.00", "$93,400.60"),
        ("94800.00", "93400.60"),
        ("$23,500.00 in remediation", "$21,900.60 in remediation"),
        ("$23,500.00 CDE remediation labor", "$21,900.60 CDE remediation labor"),
        ("$23,300.00 CDE remediation labor", "$21,900.60 CDE remediation labor"),
        ("$95.00/hr", "$121.67/hr"),
        ("$622,500 Breach", "$2,577,794 Breach"),
        ("$622,500 HHS OCR Tier 2 Breach Exposure", "$2,577,794 HHS OCR Tier 3 Breach Exposure"),
        ("$622,500 HIPAA Breach", "$2,577,794 HIPAA Breach"),
        ("$622,500 Unshielded Breach Liability", "$2,577,794 Unshielded Breach Liability"),
        ("$622,500 / $115,000", "$2,577,794 / $115,000"),
    )

    @classmethod
    def reconcile_html_truth(
        cls,
        html_content: str,
        tenant: str,
        rel_path: str = "",
        slug: str = "",
        manifest_data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, List[str]]:
        """
        Deterministically reconciles prose, comparison tables, autonomous assertions,
        decision matrices, structured JSON-LD schema, and inline calculator JS against
        TenantFactStore ground truth while stripping speculative filler.
        Returns (updated_html, list_of_repaired_categories).
        """
        import html as _html_lib
        import json as _json_lib

        updated = html_content
        repairs: List[str] = []
        tenant_norm = resolve_canonical_property_id(tenant, default=str(tenant or "").strip().lower() or "profithelm")
        combined_slug = f"{rel_path.lower()} {slug.lower()}"

        # 1. Strip speculative filler phrases across prose
        for filler_old, filler_new in cls.SPECULATIVE_FILLER_REPLACEMENTS:
            if filler_old in updated:
                updated = updated.replace(filler_old, filler_new)
                if "speculative_filler_stripped" not in repairs:
                    repairs.append("speculative_filler_stripped")

        # 2. Tenant-specific deterministic statutory truth replacements
        if tenant_norm == "profithelm":
            for old_str, new_str in cls.PROFITHELM_HTML_REPLACEMENTS:
                if old_str in updated:
                    updated = updated.replace(old_str, new_str)
                    if "profithelm_statutory_truth_reconciled" not in repairs:
                        repairs.append("profithelm_statutory_truth_reconciled")
            suv_cap_pat = re.compile(
                r'((?:qualifying\s+)?(?:heavy\s+SUVs?|commercial\s+vehicles?|passenger\s+vehicles?)\s+(?:capped\s+at|cap\s+at(?:\s+a)?|limit\s+of|deduction\s+of)\s+)\$(?:2,560,000|2\.56M|31,300|30,500)',
                re.IGNORECASE,
            )
            if suv_cap_pat.search(updated):
                updated = suv_cap_pat.sub(r'\1$32,000', updated)
                if "profithelm_statutory_truth_reconciled" not in repairs:
                    repairs.append("profithelm_statutory_truth_reconciled")
        elif tenant_norm == "prexvo":
            for old_str, new_str in cls.PREXVO_ALL_HTML_REPLACEMENTS:
                if old_str in updated:
                    updated = updated.replace(old_str, new_str)
                    if "prexvo_plan_threshold_reconciled" not in repairs:
                        repairs.append("prexvo_plan_threshold_reconciled")
            is_ibr_or_paye = (
                any(k in combined_slug for k in ("ibr-hardship", "paye-sunset"))
                or "IBR Hardship Cap Calculator" in updated
                or "PAYE Sunset Eligibility" in updated
            ) and "rap-vs-ibr" not in combined_slug
            if is_ibr_or_paye:
                for old_str, new_str in cls.PREXVO_IBR_PAYE_HTML_REPLACEMENTS:
                    if old_str in updated:
                        updated = updated.replace(old_str, new_str)
                        if "prexvo_plan_threshold_reconciled" not in repairs:
                            repairs.append("prexvo_plan_threshold_reconciled")
                if "ibr-hardship" in combined_slug and '"name": "RAP vs IBR Repayment Calculator"' in updated:
                    updated = updated.replace(
                        '"name": "RAP vs IBR Repayment Calculator"',
                        '"name": "IBR Hardship Cap & Partial Financial Hardship Calculator"',
                    )
                    if "prexvo_plan_threshold_reconciled" not in repairs:
                        repairs.append("prexvo_plan_threshold_reconciled")
            if any(k in combined_slug for k in ("icr-repayment", "tiered-standard", "grad-plus", "refinance")):
                if (
                    "<td>225% Federal Poverty Exemption ($35,212.50 Single RAP Baseline)</td>" in updated
                    and "<td><strong>$2,244 Annual Payment Reduction + $1,420 Annual Interest Subsidy (34 CFR 685.209)</strong></td>" in updated
                ):
                    if "icr-repayment" in combined_slug:
                        updated = updated.replace(
                            "<td>225% Federal Poverty Exemption ($35,212.50 Single RAP Baseline)</td>\n          <td>2026 RAP / IBR with 100% Unpaid Interest Waiver</td>\n          <td><strong>$2,244 Annual Payment Reduction + $1,420 Annual Interest Subsidy (34 CFR 685.209)</strong></td>",
                            "<td>100% Federal Poverty Exemption ($15,650 Single ICR Baseline)</td>\n          <td>Direct Consolidation into 34 CFR 685.209(b) ICR Schedule</td>\n          <td><strong>$651.25/mo ICR Payment ($171.25/mo Savings vs $822.50 10-Yr Standard)</strong></td>",
                        )
                    elif "tiered-standard" in combined_slug:
                        updated = updated.replace(
                            "<td>225% Federal Poverty Exemption ($35,212.50 Single RAP Baseline)</td>\n          <td>2026 RAP / IBR with 100% Unpaid Interest Waiver</td>\n          <td><strong>$2,244 Annual Payment Reduction + $1,420 Annual Interest Subsidy (34 CFR 685.209)</strong></td>",
                            "<td>$60,000+ Balance Tier (30-Year / 360-Month Amortization)</td>\n          <td>34 CFR 685.208 Tiered Standard vs 10-Year Standard</td>\n          <td><strong>$379.24/mo Tiered Payment ($302.05/mo Lower Fixed Obligation vs $681.29/mo)</strong></td>",
                        )
                    elif "grad-plus" in combined_slug:
                        updated = updated.replace(
                            "<td>225% Federal Poverty Exemption ($35,212.50 Single RAP Baseline)</td>\n          <td>2026 RAP / IBR with 100% Unpaid Interest Waiver</td>\n          <td><strong>$2,244 Annual Payment Reduction + $1,420 Annual Interest Subsidy (34 CFR 685.209)</strong></td>",
                            "<td>$20,500 Annual Direct Unsubsidized Cap ($138,500 Aggregate)</td>\n          <td>Exhaust Direct Unsubsidized Before Grad PLUS / Private Credit</td>\n          <td><strong>Lower Origination Fee (1.057% vs 4.228%) + Full Title IV IDR/PSLF Eligibility</strong></td>",
                        )
                    elif "refinance" in combined_slug:
                        updated = updated.replace(
                            "<td>225% Federal Poverty Exemption ($35,212.50 Single RAP Baseline)</td>\n          <td>2026 RAP / IBR with 100% Unpaid Interest Waiver</td>\n          <td><strong>$2,244 Annual Payment Reduction + $1,420 Annual Interest Subsidy (34 CFR 685.209)</strong></td>",
                            "<td>$55,000 Balance Refinanced from 7.0% Federal to 5.2% Private APR</td>\n          <td>Private Refinance Only After Confirming Zero IDR/PSLF Value</td>\n          <td><strong>$990 First-Year Interest Savings (Permanently Waives Federal Protections)</strong></td>",
                        )
                    if "prexvo_plan_threshold_reconciled" not in repairs:
                        repairs.append("prexvo_plan_threshold_reconciled")
        elif tenant_norm == "gainhelm":
            for old_str, new_str in cls.GAINHELM_HTML_REPLACEMENTS:
                if old_str in updated:
                    updated = updated.replace(old_str, new_str)
                    if "gainhelm_statutory_truth_reconciled" not in repairs:
                        repairs.append("gainhelm_statutory_truth_reconciled")

        # 3. Ensure signal/index.html has a valid WebPage JSON-LD schema block if missing
        if (
            ("signal/index.html" in rel_path.lower() or slug.lower() == "signal")
            and 'type="application/ld+json"' not in updated
            and "</head>" in updated
        ):
            tenant_contract = get_tenant_contract(tenant_norm)
            canon_m = re.search(
                r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']',
                updated,
                re.IGNORECASE,
            )
            sig_url = canon_m.group(1) if canon_m else f"{tenant_contract.canonical_base}/signal/"
            t_m = re.search(r"<title[^>]*>([\s\S]*?)</title>", updated, re.IGNORECASE)
            sig_title = (
                _html_lib.unescape(re.sub(r"<[^>]+>", "", t_m.group(1)).strip())
                if t_m
                else f"{tenant_contract.brand_name} Statutory Signal"
            )
            ld_payload = {
                "@context": "https://schema.org",
                "@type": "WebPage",
                "@id": f"{sig_url.rstrip('/')}/#webpage",
                "name": sig_title,
                "url": sig_url,
                "description": "Deterministic federal and state statutory tax and capital allocation telemetry signal.",
            }
            ld_script = f'  <script type="application/ld+json">\n{_json_lib.dumps(ld_payload, indent=2)}\n  </script>\n</head>'
            updated = updated.replace("</head>", ld_script, 1)
            repairs.append("signal_webpage_jsonld_injected")

        # 4. Enforce 1:1 FAQPage JSON-LD <-> visible <details> FAQ answer parity if FAQs exist
        if '"FAQPage"' in updated and "<details" in updated:
            dom_faqs: List[Tuple[str, str]] = []
            seen_dom_faq_q: Set[str] = set()
            for dm in re.finditer(r"<details\b([^>]*)>([\s\S]*?)</details>", updated, re.IGNORECASE):
                d_attrs = (dm.group(1) or "").lower()
                if "mobile-nav-menu" in d_attrs or "mobile-nav" in d_attrs:
                    continue
                d_inner = dm.group(2)
                if "<nav" in d_inner.lower() and "<p" not in d_inner.lower():
                    continue
                sm = re.search(r"<summary\b[^>]*>([\s\S]*?)</summary>", d_inner, re.IGNORECASE)
                if not sm:
                    continue
                q_txt = _html_lib.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", sm.group(1)))).strip()
                if q_txt.lower() in ("menu", "navigation", "toggle navigation menu") or q_txt.lower() in seen_dom_faq_q:
                    continue
                pm_ans = re.search(r"<p\b[^>]*>([\s\S]*?)</p>", d_inner, re.IGNORECASE)
                after_s = pm_ans.group(1) if pm_ans else d_inner[sm.end():]
                a_txt = _html_lib.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", after_s))).strip()
                if q_txt and a_txt:
                    seen_dom_faq_q.add(q_txt.lower())
                    dom_faqs.append((q_txt, a_txt))

            if dom_faqs:
                faq_entities = [
                    {
                        "@type": "Question",
                        "name": q_t,
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": a_t,
                        },
                    }
                    for q_t, a_t in dom_faqs
                ]

                def _sync_ld_faq_answers(m_ld: re.Match) -> str:
                    o_tag, raw_json, c_tag = m_ld.group(1), m_ld.group(2), m_ld.group(3)
                    try:
                        parsed = _json_lib.loads(raw_json.strip())
                        if isinstance(parsed, dict):
                            if "@graph" in parsed and isinstance(parsed["@graph"], list):
                                for node in parsed["@graph"]:
                                    if isinstance(node, dict) and node.get("@type") == "FAQPage":
                                        if node.get("mainEntity") != faq_entities:
                                            node["mainEntity"] = faq_entities
                                            return f"{o_tag}\n{_json_lib.dumps(parsed, indent=2)}\n  {c_tag}"
                            elif parsed.get("@type") == "FAQPage":
                                if parsed.get("mainEntity") != faq_entities:
                                    parsed["mainEntity"] = faq_entities
                                    return f"{o_tag}\n{_json_lib.dumps(parsed, indent=2)}\n  {c_tag}"
                    except Exception:
                        pass
                    return m_ld.group(0)

                synced_html = re.sub(
                    r'(<script[^>]+type=["\']application/ld\+json["\'][^>]*>)([\s\S]*?)(</script>)',
                    _sync_ld_faq_answers,
                    updated,
                    flags=re.IGNORECASE,
                )
                if synced_html != updated:
                    updated = synced_html
                    if "faq_schema_dom_synced" not in repairs:
                        repairs.append("faq_schema_dom_synced")

        # 5. Reconcile SoftwareApplication JSON-LD name & url
        h1_m = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", updated, re.IGNORECASE)
        h1_title = _html_lib.unescape(re.sub(r"<[^>]+>", "", h1_m.group(1)).strip()) if h1_m else ""

        # Align Title with H1 if discrepant (only for tool calculators and leaves)
        canon_m_tmp = re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']+)["\']', updated, re.I)
        canon_check = canon_m_tmp.group(1).strip() if canon_m_tmp else ""
        is_non_tool_page = (
            (rel_path or "") in ("index.html", "", "404.html")
            or any((rel_path or "").lower().startswith(x) for x in ("privacy", "disclaimers", "disclaimer", "methodology", "about", "terms", "contact", "static/signal", "signal"))
            or (slug or "").lower() in ("privacy", "disclaimers", "disclaimer", "methodology", "about", "terms", "contact", "signal", "tools-directory", "index", "tools")
            or any(f"/{x}/" in canon_check.lower() or canon_check.lower().rstrip("/").endswith(f"/{x}") for x in ("privacy", "disclaimers", "disclaimer", "methodology", "about", "terms", "contact", "signal"))
            or canon_check.lower().rstrip("/").endswith("/tools")
            or (rel_path or "").rstrip("/") in ("tools/index.html", "tools")
        )
        is_tool_leaf = (not is_non_tool_page) and (
            (("tools/" in (rel_path or "").lower()) and (rel_path or "").rstrip("/") != "tools/index.html")
            or ("/tools/" in canon_check.lower() and not canon_check.rstrip("/").endswith("/tools"))
        )
        t_m = re.search(r"<title[^>]*>([\s\S]*?)</title>", updated, re.IGNORECASE)
        if is_tool_leaf and t_m and h1_title:
            cur_title = _html_lib.unescape(t_m.group(1)).strip()
            from pseofactory.audit import _titles_match
            if not _titles_match(cur_title, h1_title):
                from pseofactory.gsc_remediation import _normalize_title_50_60
                prof_for_brand = TenantFactStore.get_instance().get_profile(tenant_norm)
                if prof_for_brand is not None and prof_for_brand.brand_name:
                    brand_sfx = prof_for_brand.brand_name
                else:
                    decl_for_brand = CANONICAL_TENANT_DECLARATIONS.get(tenant_norm) or SPAWNED_TENANT_DECLARATIONS.get(tenant_norm)
                    brand_sfx = (
                        decl_for_brand.brand_name
                        if decl_for_brand is not None and decl_for_brand.brand_name
                        else tenant_norm.replace("_", " ").replace("-", " ").title()
                    )
                cand_title = _normalize_title_50_60(h1_title, brand_sfx, tenant_norm)
                if cand_title and cand_title != cur_title:
                    new_t_tag = f"<title>{cand_title}</title>"
                    updated = re.sub(r'<title>.*?</title>', new_t_tag, updated, count=1, flags=re.I | re.DOTALL)
                    repairs.append("title_aligned_with_h1")

        if is_tool_leaf and '"SoftwareApplication"' in updated:
            clean_page_title = h1_title
            if not clean_page_title and t_m:
                page_title = _html_lib.unescape(re.sub(r"<[^>]+>", "", t_m.group(1)).strip())
                clean_page_title = re.sub(r'\s*[|\-]\s*(?:ProfitHelm|Prexvo|GainHelm|LienBond).*$', '', page_title, flags=re.I).strip()
                clean_page_title = re.sub(r'\s+202[4-9]\s+Model\s+Tool\s+Guide\s*$', '', clean_page_title, flags=re.I).strip()

            if clean_page_title and slug:
                tenant_contract = get_tenant_contract(tenant_norm)
                canon_m = re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']+)["\']', updated, re.I)
                tool_canon_url = canon_m.group(1).strip() if canon_m else f"{tenant_contract.canonical_base}/tools/{slug}/"

                def _sync_app_ld(m_ld: re.Match) -> str:
                    o_tag, raw_json, c_tag = m_ld.group(1), m_ld.group(2), m_ld.group(3)
                    try:
                        parsed = _json_lib.loads(raw_json.strip())
                        changed_ld = False
                        if isinstance(parsed, dict):
                            nodes = parsed.get("@graph") if isinstance(parsed.get("@graph"), list) else [parsed]
                            for node in nodes:
                                if isinstance(node, dict) and (node.get("@type") == "SoftwareApplication" or (isinstance(node.get("@type"), list) and "SoftwareApplication" in node.get("@type"))):
                                    from pseofactory.audit import _titles_match
                                    curr_name = str(node.get("name") or "")
                                    if not _titles_match(curr_name, clean_page_title):
                                        node["name"] = clean_page_title
                                        changed_ld = True
                                    if "url" in node and node.get("url") != tool_canon_url:
                                        node["url"] = tool_canon_url
                                        changed_ld = True
                                    elif ("tools/" in rel_path or "tools/" in combined_slug) and node.get("url") != tool_canon_url:
                                        node["url"] = tool_canon_url
                                        changed_ld = True
                            if changed_ld:
                                return f"{o_tag}\n{_json_lib.dumps(parsed, indent=2)}\n  {c_tag}"
                    except Exception:
                        pass
                    return m_ld.group(0)

                synced_app_html = re.sub(
                    r'(<script[^>]+type=["\']application/ld\+json["\'][^>]*>)([\s\S]*?)(</script>)',
                    _sync_app_ld,
                    updated,
                    flags=re.IGNORECASE,
                )
                if synced_app_html != updated:
                    updated = synced_app_html
                    if "software_application_schema_synced" not in repairs:
                        repairs.append("software_application_schema_synced")

        # 6. Reconcile multi-dataset-join data attributes
        man_stat_val = ""
        man_econ_val = ""
        man_m = re.search(r'<script[^>]*class=["\'][^"\']*calculation-manifest[^"\']*["\'][^>]*>(.*?)</script>', updated, re.DOTALL) or re.search(r'<script[^>]*id=["\']calculation-manifest["\'][^>]*>(.*?)</script>', updated, re.DOTALL)
        if man_m:
            try:
                man_d = _json_lib.loads(man_m.group(1).strip())
                man_stat_val = man_d.get("statutory_authority") or man_d.get("statutory_provenance") or ""
                man_econ_val = man_d.get("economic_dataset") or man_d.get("economic_source") or ""
            except Exception:
                pass
        if man_m:
            try:
                curr_man = _json_lib.loads(man_m.group(1).strip())
                m_changed = False
                if manifest_data:
                    m_slug = manifest_data.get("slug")
                    m_slug_norm = str(m_slug or "").replace("/", "-")
                    slug_norm = str(slug or "").replace("/", "-")
                    rel_tool_norm = (
                        rel_path[len("tools/") : -len("/index.html")].replace("/", "-")
                        if (rel_path.startswith("tools/") and rel_path.endswith("/index.html"))
                        else ""
                    )
                    is_exact_tool = bool(
                        m_slug
                        and (
                            rel_path == f"tools/{m_slug}/index.html"
                            or slug == m_slug
                            or m_slug_norm in (slug_norm, rel_tool_norm)
                        )
                    )
                    sync_fields = (
                        (
                            "statutory_authority",
                            "economic_dataset",
                            "model_name",
                            "formula",
                            "inputs",
                            "published_output",
                            "sample_calculation",
                        )
                        if is_exact_tool
                        else ("statutory_authority", "economic_dataset", "model_name", "formula")
                    )
                    is_stale_sunset_manifest = (
                        "sunset_standard_deduction" in str(manifest_data.get("formula", ""))
                        or "sunset_standard_deduction" in str(manifest_data.get("inputs", ""))
                        or "post-sunset" in str(manifest_data.get("sample_calculation", "")).lower()
                    )
                    for k in sync_fields:
                        if is_stale_sunset_manifest and k in ("formula", "inputs", "published_output", "sample_calculation"):
                            continue
                        if k == "formula":
                            if not is_exact_tool:
                                m_inputs = set(manifest_data.get("inputs", {}).keys())
                                c_inputs = set(curr_man.get("inputs", {}).keys())
                                if m_inputs and not m_inputs.issubset(c_inputs) and curr_man.get("formula"):
                                    continue
                        if k in manifest_data and curr_man.get(k) != manifest_data[k]:
                            curr_man[k] = manifest_data[k]
                            m_changed = True

                # Deterministically reconcile calculation manifest formulas and inputs across programmatic leaves
                if tenant_norm == "profithelm":
                    truthpack_179_f = (
                        "round(min(equipment_cost * business_use_pct, 32000.0 if is_heavy_suv == 1 else max(0.0, 2560000.0 - max(0.0, equipment_cost - 4090000.0))) "
                        "+ max(0.0, equipment_cost * business_use_pct - min(equipment_cost * business_use_pct, 32000.0 if is_heavy_suv == 1 else max(0.0, 2560000.0 - max(0.0, equipment_cost - 4090000.0)))) * (bonus_pct / 100.0), 2)"
                    )
                    estate_179_f = (
                        "round(min(equipment_cost * business_use_pct, (is_heavy_suv * 32000.0 + (1 - is_heavy_suv) * max(0.0, 2560000.0 - max(0.0, equipment_cost - 4090000.0)))) "
                        "+ max(0.0, equipment_cost * business_use_pct - min(equipment_cost * business_use_pct, (is_heavy_suv * 32000.0 + (1 - is_heavy_suv) * max(0.0, 2560000.0 - max(0.0, equipment_cost - 4090000.0))))) * (bonus_pct / 100.0), 2)"
                    )

                    # Reconcile equipment-lease-vs-buy-section-179-calculator
                    if "equipment-lease-vs-buy-section-179-calculator" in combined_slug or "equipment-lease-vs-buy-section-179-calculator" in rel_path:
                        has_legacy_lease_dom = (
                            'id="input-year_one_financing_payments"' in updated
                            and 'id="input-business_use_pct"' not in updated
                        )
                        if not has_legacy_lease_dom:
                            from pseofactory.contracts import safe_eval_mathematical_formula

                            m_in = curr_man.get("inputs") if isinstance(curr_man.get("inputs"), dict) else {}
                            curr_f = curr_man.get("formula")
                            has_valid_4in = (
                                set(m_in.keys()) == {"equipment_cost", "business_use_pct", "is_heavy_suv", "bonus_pct"}
                                and curr_f in (truthpack_179_f, estate_179_f)
                            )
                            if has_valid_4in:
                                expected_out = round(float(safe_eval_mathematical_formula(curr_f, m_in)), 2)
                                if abs(float(curr_man.get("published_output", 0.0)) - expected_out) > 0.01:
                                    curr_man["published_output"] = expected_out
                                    m_changed = True
                                if curr_man.get("formula_id") != "section_179_heavy_suv_plus_bonus_2026":
                                    curr_man["formula_id"] = "section_179_heavy_suv_plus_bonus_2026"
                                    m_changed = True
                            else:
                                target_in = {
                                    "equipment_cost": 85000.0,
                                    "business_use_pct": 0.8,
                                    "is_heavy_suv": 1,
                                    "bonus_pct": 100.0,
                                }
                                target_out = round(float(safe_eval_mathematical_formula(truthpack_179_f, target_in)), 2)
                                if (
                                    curr_man.get("formula") != truthpack_179_f
                                    or curr_man.get("inputs") != target_in
                                    or abs(float(curr_man.get("published_output", 0.0)) - target_out) > 0.01
                                    or curr_man.get("formula_id") != "section_179_heavy_suv_plus_bonus_2026"
                                ):
                                    curr_man["formula_id"] = "section_179_heavy_suv_plus_bonus_2026"
                                    curr_man["formula"] = truthpack_179_f
                                    curr_man["inputs"] = target_in
                                    curr_man["published_output"] = target_out
                                    m_changed = True

                    # Reconcile irs-2027-tax-brackets federal hub (all 7 progressive 2026 single brackets, $16,100 std ded)
                    if rel_path == "tools/irs-2027-tax-brackets/index.html" or slug == "irs-2027-tax-brackets":
                        std_var = (
                            "standard_deduction_2026"
                            if ('name="standard_deduction_2026"' in updated and 'name="standard_deduction"' not in updated)
                            else "standard_deduction"
                        )
                        target_f = (
                            f"round(0.10 * min(max(0.0, gross_income - {std_var}), 12400.0) "
                            f"+ 0.12 * max(0.0, min(max(0.0, gross_income - {std_var}), 50400.0) - 12400.0) "
                            f"+ 0.22 * max(0.0, min(max(0.0, gross_income - {std_var}), 105700.0) - 50400.0) "
                            f"+ 0.24 * max(0.0, min(max(0.0, gross_income - {std_var}), 201775.0) - 105700.0) "
                            f"+ 0.32 * max(0.0, min(max(0.0, gross_income - {std_var}), 256225.0) - 201775.0) "
                            f"+ 0.35 * max(0.0, min(max(0.0, gross_income - {std_var}), 640600.0) - 256225.0) "
                            f"+ 0.37 * max(0.0, max(0.0, gross_income - {std_var}) - 640600.0), 2)"
                        )
                        if curr_man.get("formula") != target_f:
                            curr_man["formula"] = target_f
                            m_changed = True
                        target_in = {"gross_income": 125000.0, std_var: 16100.0}
                        if curr_man.get("inputs") != target_in:
                            curr_man["inputs"] = target_in
                            m_changed = True
                        if curr_man.get("published_output") != 18734.0:
                            curr_man["published_output"] = 18734.0
                            m_changed = True
                        if curr_man.get("formula_id") != "federal_income_tax_2026_single":
                            curr_man["formula_id"] = "federal_income_tax_2026_single"
                            m_changed = True

                    # Reconcile section-179-calculator vehicle leaves (preserve/emit 4-input section_179_heavy_suv_plus_bonus_2026)
                    elif (
                        (rel_path.startswith("tools/section-179-calculator/") and rel_path != "tools/section-179-calculator/index.html")
                        or (slug.startswith("section-179-calculator/") and slug != "section-179-calculator")
                        or slug.startswith("section-179-calculator-")
                    ):
                        m_in = curr_man.get("inputs") if isinstance(curr_man.get("inputs"), dict) else {}
                        cost_v = m_in.get("equipment_cost") if m_in.get("equipment_cost") is not None else m_in.get("vehicle_cost")
                        if cost_v is not None:
                            from pseofactory.contracts import safe_eval_mathematical_formula
                            # Determine heavy SUV vs full Section 179 equipment/commercial vehicle
                            # Heavy SUVs: BMW X5, Escalade, Suburban, Yukon XL, Defender 110, Navigator L, Cayenne
                            suv_slugs = (
                                "bmw-x5", "escalade", "suburban", "yukon", "defender", "navigator", "cayenne"
                            )
                            is_heavy_suv = 1 if any(k in combined_slug for k in suv_slugs) else 0
                            curr_f = curr_man.get("formula")
                            has_valid_4in = (
                                set(m_in.keys()) == {"equipment_cost", "business_use_pct", "is_heavy_suv", "bonus_pct"}
                                and curr_f in (truthpack_179_f, estate_179_f)
                                and int(m_in.get("is_heavy_suv", -1)) == is_heavy_suv
                                and float(m_in.get("bonus_pct", 0.0)) == 100.0
                            )
                            if has_valid_4in:
                                target_out = round(float(safe_eval_mathematical_formula(curr_f, m_in)), 2)
                                if abs(float(curr_man.get("published_output", 0.0)) - target_out) > 0.01:
                                    curr_man["published_output"] = target_out
                                    m_changed = True
                                if curr_man.get("formula_id") != "section_179_heavy_suv_plus_bonus_2026":
                                    curr_man["formula_id"] = "section_179_heavy_suv_plus_bonus_2026"
                                    m_changed = True
                            else:
                                bus_raw = m_in.get("business_use_pct")
                                if bus_raw is None:
                                    bus_raw = m_in.get("business_use_rate")
                                bus_v = float(bus_raw) if bus_raw is not None else 1.0
                                target_f = estate_179_f if curr_f == estate_179_f else truthpack_179_f
                                target_in = {
                                    "equipment_cost": float(cost_v),
                                    "business_use_pct": bus_v,
                                    "is_heavy_suv": is_heavy_suv,
                                    "bonus_pct": 100.0,
                                }
                                target_out = round(float(safe_eval_mathematical_formula(target_f, target_in)), 2)
                                if (
                                    curr_man.get("formula") != target_f
                                    or curr_man.get("inputs") != target_in
                                    or abs(float(curr_man.get("published_output", 0.0)) - target_out) > 0.01
                                    or curr_man.get("formula_id") != "section_179_heavy_suv_plus_bonus_2026"
                                ):
                                    curr_man["formula_id"] = "section_179_heavy_suv_plus_bonus_2026"
                                    curr_man["formula"] = target_f
                                    curr_man["inputs"] = target_in
                                    curr_man["published_output"] = target_out
                                    m_changed = True

                if m_changed:
                    updated = updated.replace(man_m.group(1), f"\n{_json_lib.dumps(curr_man, indent=2)}\n")
                    if "embedded_manifest_synced" not in repairs:
                        repairs.append("embedded_manifest_synced")
            except Exception:
                pass
        if not man_stat_val:
            try:
                st_dynamic = TenantFactStore.get_statutory_truth(tenant_norm)
                man_stat_val = st_dynamic.controlling_statute or f"{tenant_norm} Statutory Schedule"
            except Exception:
                man_stat_val = f"{tenant_norm} Statutory Schedule"
        if not man_econ_val:
            decl_econ = CANONICAL_TENANT_DECLARATIONS.get(tenant_norm) or SPAWNED_TENANT_DECLARATIONS.get(tenant_norm)
            if decl_econ is not None and decl_econ.economic_dataset_label:
                man_econ_val = decl_econ.economic_dataset_label
            else:
                man_econ_val = "Published Federal & Macroeconomic Reference Series"

        if "multi-dataset-join" in updated:
            mdj_m = re.search(r'<(?:div|section|aside)[^>]*class=["\'][^"\']*multi-dataset-join[^"\']*["\'][^>]*>', updated, re.I)
            if mdj_m:
                tag_str = mdj_m.group(0)
                new_tag = tag_str
                if "data-statutory-source=" in new_tag:
                    new_tag = re.sub(r'data-statutory-source=["\'][^"\']*["\']', f'data-statutory-source="{man_stat_val}"', new_tag)
                else:
                    new_tag = new_tag[:-1] + f' data-statutory-source="{man_stat_val}">'

                if "data-economic-source=" in new_tag:
                    new_tag = re.sub(r'data-economic-source=["\'][^"\']*["\']', f'data-economic-source="{man_econ_val}"', new_tag)
                else:
                    new_tag = new_tag[:-1] + f' data-economic-source="{man_econ_val}">'

                if new_tag != tag_str:
                    updated = updated.replace(tag_str, new_tag, 1)
                    if "multi_dataset_join_sources_injected" not in repairs:
                        repairs.append("multi_dataset_join_sources_injected")

        # 6b. Reconcile calculation table data attributes with manifest dataset sources
        if "<table" in updated:
            before_tbl_sync = updated
            if man_econ_val:
                updated = re.sub(
                    r'(<table\b[^>]*data-economic-source=)(["\'])(.*?)\2',
                    rf'\1"{man_econ_val}"',
                    updated,
                    flags=re.IGNORECASE,
                )
            if man_stat_val:
                updated = re.sub(
                    r'(<table\b[^>]*data-statutory-source=)(["\'])(.*?)\2',
                    rf'\1"{man_stat_val}"',
                    updated,
                    flags=re.IGNORECASE,
                )
            if updated != before_tbl_sync and "calculation_table_sources_reconciled" not in repairs:
                repairs.append("calculation_table_sources_reconciled")

        # 6c. Reconcile result-box structural class if missing on calculation results container
        if is_tool_leaf and not re.search(r'<(?:div|section|aside)[^>]*class=["\'][^"\']*\bresult-box\b', updated, re.I):
            res_cont_m = re.search(
                r'<(div|section|aside)([^>]*class=["\'][^"\']*\b(?:calc-outputs-panel|calc-results-column|baseline-output-summary|result-card|results-panel|metric-grid)\b[^"\']*)(["\'][^>]*>)',
                updated,
                re.IGNORECASE,
            )
            if res_cont_m:
                tag, before_quote, after_quote = res_cont_m.group(1), res_cont_m.group(2), res_cont_m.group(3)
                new_tag = f"<{tag}{before_quote} result-box{after_quote}"
                updated = updated.replace(res_cont_m.group(0), new_tag, 1)
                if "result_box_class_reconciled" not in repairs:
                    repairs.append("result_box_class_reconciled")

        # 7. Reconcile Prexvo YMYL Refinancing Forfeiture Disclaimer
        if tenant_norm == "prexvo" and "refinanc" in combined_slug:
            disclaimer_text = "Refinancing a federal student loan into a private note permanently forfeits access to federal income-driven repayment (IDR, SAVE, RAP, IBR), Public Service Loan Forgiveness (PSLF), administrative forbearance, and federal death or disability discharge."
            # Clean any stray orphaned closing </aside> tags immediately preceding regulatory-forfeiture-warning
            cleaned_orphan_aside = re.sub(
                r'(?:</aside>\s*)+(<div\b[^>]*class=["\'][^"\']*\bregulatory-forfeiture-warning\b)',
                r"\1",
                updated,
                flags=re.IGNORECASE,
            )
            # Only move regulatory-forfeiture-warning outside quick-answer if it is actually nested inside <aside class="quick-answer">...</aside>
            qa_aside_m = re.search(
                r'<aside\b[^>]*class=["\'][^"\']*\bquick-answer\b[^"\']*["\'][^>]*>([\s\S]*?)</aside>',
                cleaned_orphan_aside,
                flags=re.IGNORECASE,
            )
            if qa_aside_m and "regulatory-forfeiture-warning" in qa_aside_m.group(1):
                m_warn = re.search(
                    r'(\s*<div\b[^>]*class=["\'][^"\']*\bregulatory-forfeiture-warning\b[^"\']*["\'][^>]*>[^<]*(?:<(?!/?div\b)[^<]*)*</div>)\s*</aside>$',
                    qa_aside_m.group(0),
                    flags=re.IGNORECASE,
                )
                if m_warn:
                    warn_block = m_warn.group(1).strip()
                    healed_qa = qa_aside_m.group(0)[: m_warn.start()] + f"\n</aside>\n  {warn_block}"
                    updated = cleaned_orphan_aside.replace(qa_aside_m.group(0), healed_qa, 1)
                    if "regulatory_warning_moved_outside_quick_answer" not in repairs:
                        repairs.append("regulatory_warning_moved_outside_quick_answer")
            elif cleaned_orphan_aside != updated:
                updated = cleaned_orphan_aside
                if "regulatory_warning_orphan_aside_cleaned" not in repairs:
                    repairs.append("regulatory_warning_orphan_aside_cleaned")

            if "permanently forfeits access" not in updated:
                qa_target_m = re.search(
                    r'<aside\b[^>]*class=["\'][^"\']*\bquick-answer\b[^"\']*["\'][^>]*>[\s\S]*?</aside>',
                    updated,
                    flags=re.IGNORECASE,
                )
                if qa_target_m:
                    disc_markup = (
                        f'{qa_target_m.group(0)}\n'
                        f'  <div class="regulatory-forfeiture-warning card" style="margin-top: 12px; padding: 12px; border-left: 4px solid var(--status-danger); background: var(--surface-subtle); font-size: 0.875rem;">'
                        f'<strong style="color: var(--status-danger);">Mandatory YMYL Regulatory Disclosure:</strong> {disclaimer_text}</div>'
                    )
                    updated = updated.replace(qa_target_m.group(0), disc_markup, 1)
                elif "<footer" in updated:
                    disc_markup = f'<section class="ymyl-disclaimer card" style="margin: 24px auto; max-width: 800px; padding: 16px;"><p style="font-size: 0.85rem; color: var(--text-secondary);"><strong>Regulatory Notice:</strong> {disclaimer_text}</p></section>\n<footer'
                    updated = updated.replace("<footer", disc_markup, 1)
                else:
                    updated = updated.replace("</body>", f'<p class="forfeiture-disclaimer">{disclaimer_text}</p>\n</body>', 1)
                repairs.append("prexvo_refinance_forfeiture_disclaimer_injected")


        # 9. Reconcile FAQPage visibility in HTML body
        if "FAQPage" in updated:
            import html as _html_lib

            updated = re.sub(
                r'\s*<section class="faq-section card" style="margin-top:\s*2rem;(?:\s*padding:\s*1\.5rem;?)?">[\s\S]*?</section>',
                '',
                updated,
                flags=re.IGNORECASE,
            )
            body_no_scripts = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', updated, flags=re.DOTALL | re.IGNORECASE)
            vis_norm_lower = " ".join(
                _html_lib.unescape(re.sub(r'<[^>]+>', ' ', body_no_scripts)).split()
            ).lower()
            raw_unesc_lower = " ".join(_html_lib.unescape(body_no_scripts).split()).lower()
            missing_faqs: List[Tuple[str, str]] = []
            for ld_match in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>', updated, re.I):
                try:
                    ld_data = _json_lib.loads(ld_match.group(1).strip())
                    graph_nodes = ld_data.get("@graph", [ld_data]) if isinstance(ld_data, dict) else []
                    for node in graph_nodes:
                        if isinstance(node, dict) and node.get("@type") == "FAQPage":
                            for q_node in node.get("mainEntity", []):
                                if isinstance(q_node, dict):
                                    q_name = _html_lib.unescape(str(q_node.get("name") or "")).strip()
                                    a_obj = q_node.get("acceptedAnswer", {})
                                    a_txt = _html_lib.unescape(str(a_obj.get("text") or "")).strip() if isinstance(a_obj, dict) else ""
                                    q_norm = " ".join(q_name.split()).lower()
                                    if q_norm and q_norm not in vis_norm_lower and q_norm not in raw_unesc_lower:
                                        missing_faqs.append((q_name, a_txt))
                except Exception:
                    pass
            if missing_faqs:
                deduped_missing: List[Tuple[str, str]] = []
                seen_q = set()
                for q, a in missing_faqs:
                    q_clean = " ".join(q.split()).lower()
                    if q_clean not in seen_q:
                        seen_q.add(q_clean)
                        deduped_missing.append((q, a))
                missing_faqs = deduped_missing

                # Check if an existing FAQ <section> already exists to avoid duplicate FAQ sections
                sec_stack: List[Tuple[int, int, str]] = []
                faq_sec_candidates: List[Tuple[int, int, int, int, str, str, str]] = []
                for sec_m in re.finditer(r'<(/?)section\b[^>]*>', updated, flags=re.IGNORECASE):
                    if not sec_m.group(1):
                        sec_stack.append((sec_m.start(), sec_m.end(), sec_m.group(0)))
                    elif sec_stack:
                        s_start, inner_start, o_tag = sec_stack.pop()
                        s_end = sec_m.end()
                        c_tag = sec_m.group(0)
                        cls_m = re.search(r'\bclass\s*=\s*(["\'])(.*?)\1', o_tag, flags=re.IGNORECASE | re.DOTALL)
                        cls_val = cls_m.group(2) if cls_m else ""
                        inner_sec = updated[inner_start:sec_m.start()]
                        has_faq_cls = bool(re.search(r'\b(?:faq-section|overlay-faqs)\b', cls_val, flags=re.IGNORECASE))
                        own_inner = re.sub(r'<section\b[\s\S]*?</section>', '', inner_sec, flags=re.IGNORECASE)
                        has_faq_hd = bool(
                            re.search(
                                r'<h[1-4]\b[^>]*>(?:(?!</h[1-4]>).)*?\bFrequently\s+Asked\s+Questions\b',
                                own_inner,
                                flags=re.IGNORECASE | re.DOTALL,
                            )
                        )
                        if has_faq_cls or has_faq_hd:
                            faq_sec_candidates.append((0 if has_faq_cls else 1, -len(sec_stack), s_start, s_end, o_tag, inner_sec, c_tag))

                if faq_sec_candidates:
                    faq_sec_candidates.sort(key=lambda item: (item[0], item[1], item[2]))
                    _, _, faq_s, faq_e, f_open, f_inner, f_close = faq_sec_candidates[0]
                    uses_details = ('<details' in f_inner.lower()) or ('class="faq-list"' in f_inner.lower()) or ("class='faq-list'" in f_inner.lower())
                    if uses_details:
                        add_faq_html = "\n".join(
                            f'    <details class="faq-item faq-card" style="margin-bottom: 1rem; border: 1px solid var(--border);">\n'
                            f'      <summary class="touch-target" style="display: flex; align-items: center; min-height: 44px; min-width: 44px; padding: 8px 4px; cursor: pointer; font-weight: 700;">{_html_lib.escape(q, quote=False)}</summary>\n'
                            f'      <p style="font-size: 0.9375rem; color: var(--text-secondary); margin: 0.25rem 0 0 0;">{_html_lib.escape(a, quote=False)}</p>\n'
                            f'    </details>'
                            for q, a in missing_faqs
                        )
                    else:
                        add_faq_html = "\n".join(
                            f'    <div class="faq-item" style="margin-bottom: 1.25rem;">\n'
                            f'      <h3 style="font-size: 1.1rem; font-weight: 600; margin-bottom: 0.5rem;">{_html_lib.escape(q, quote=False)}</h3>\n'
                            f'      <p style="font-size: 0.95rem; line-height: 1.5; color: var(--text-secondary);">{_html_lib.escape(a, quote=False)}</p>\n'
                            f'    </div>'
                            for q, a in missing_faqs
                        )
                    if 'class="faq-list"' in f_inner.lower() or "class='faq-list'" in f_inner.lower():
                        new_inner = re.sub(
                            r'(</div>\s*)$',
                            lambda m: f'\n{add_faq_html}\n{m.group(1)}',
                            f_inner,
                            count=1,
                        )
                        if new_inner == f_inner:
                            new_inner = f"{f_inner.rstrip()}\n{add_faq_html}\n"
                    else:
                        new_inner = f"{f_inner.rstrip()}\n{add_faq_html}\n"
                    updated = updated[:faq_s] + f"{f_open}{new_inner}{f_close}" + updated[faq_e:]
                    repairs.append("faq_section_rendered_in_body")
                else:
                    has_h2_faq = bool(re.search(r'<h2[^>]*>\s*Frequently Asked Questions\s*</h2>', updated, re.I))
                    heading_tag = "h3" if has_h2_faq else "h2"
                    faq_items_html = "\n".join(
                        f'    <div class="faq-item" style="margin-bottom: 1.25rem;">\n'
                        f'      <h3 style="font-size: 1.1rem; font-weight: 600; margin-bottom: 0.5rem;">{_html_lib.escape(q, quote=False)}</h3>\n'
                        f'      <p style="font-size: 0.95rem; line-height: 1.5; color: var(--text-secondary);">{_html_lib.escape(a, quote=False)}</p>\n'
                        f'    </div>'
                        for q, a in missing_faqs
                    )
                    faq_markup = (
                        f'\n  <section class="faq-section card" style="margin-top: 2rem; padding: 1.5rem;">\n'
                        f'    <{heading_tag} style="font-size: 1.4rem; font-weight: 700; margin-bottom: 1rem;">Frequently Asked Questions</{heading_tag}>\n'
                        f'{faq_items_html}\n'
                        f'  </section>\n'
                    )
                    if "</main>" in updated:
                        updated = updated.replace("</main>", f"{faq_markup}</main>", 1)
                        repairs.append("faq_section_rendered_in_body")
                    elif "<footer" in updated:
                        updated = updated.replace("<footer", f"{faq_markup}<footer", 1)
                        repairs.append("faq_section_rendered_in_body")

        return updated, repairs

    @classmethod
    def reconcile_overlay_spec_truth(
        cls,
        raw_ov: Dict[str, Any],
        tenant: str,
        slug: str = "",
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Deterministically reconciles a persisted GSC overlay JSON dictionary against
        TenantFactStore ground truth so stale 2026 Section 179 caps ($1,250,000 / $3,130,000 / $31,300)
        or Prexvo IBR/PAYE/ICR/Tiered/GradPLUS/PSLF/Refinance thresholds are healed in place.
        """
        import json as _json_lib

        if not isinstance(raw_ov, dict):
            return raw_ov, False
        ov_slug = str(raw_ov.get("slug") or slug or "").lower()
        tenant_norm = resolve_canonical_property_id(tenant, default=str(tenant or "").strip().lower() or "profithelm")
        serialized = _json_lib.dumps(raw_ov, ensure_ascii=False)
        updated_str = serialized

        if tenant_norm == "profithelm":
            for old_s, new_s in (
                ("up to $1,250,000 in qualifying commercial equipment", "up to $2,560,000 in qualifying commercial equipment"),
                ("above $3,130,000 in total asset purchases", "above $4,090,000 in total asset purchases"),
                ("$1,250,000 Section 179 Cap (IRC Section 179(b)(1))", "$2,560,000 Section 179 Cap (IRC Section 179(b)(1))"),
                ("$3,130,000 Section 179 Phase-Out Threshold (IRC 179(b)(2))", "$4,090,000 Section 179 Phase-Out Threshold (IRC 179(b)(2))"),
                ("CapEx Intensive Expansion ($3.6M Total Equipment Placed in Service)", "CapEx Intensive Expansion ($4.35M Total Equipment Placed in Service)"),
                ("Combine Remaining $780k Section 179 Allowance + IRC 168(k) Bonus", "Combine Remaining $2.30M Section 179 Allowance + IRC 168(k) Bonus"),
                ("$412,000 First-Year Combined Depreciation Tax Shield", "$1,522,500 First-Year Combined Depreciation Tax Shield"),
                ("High-Cap Scenario ($1.25M Statutory Limit)", "High-Cap Scenario ($2.56M Statutory Limit)"),
                ('"cost": 1250000', '"cost": 2560000'),
                (
                    "capped at a $31,300 Section 179 deduction in 2026",
                    "capped at a $32,000 statutory Section 179 deduction (IRS Rev. Proc. 2025-32)",
                ),
                (
                    "In 2026, Equipment Lease Tax Deduction under IRC Section 179 and Section 168(k) allows businesses to expense up to $2,560,000 in qualifying commercial equipment placed in service, phasing out dollar-for-dollar above $4,090,000 in total asset purchases. Remaining basis qualifies for 20% first-year bonus depreciation and MACRS recovery on IRS Form 4562.",
                    "Under IRC Section 162(a)(3) and GAAP ASC 842, operating equipment lease payments are 100% deductible as ordinary business expenses in the period incurred without upfront capital expenditure, whereas financed equipment purchases utilize IRC Section 179 ($32,000 Heavy SUV cap) and 100% Section 168(k) bonus depreciation ($68,000 first-year write-off on $85,000 at 80% business use).",
                ),
                ("$27,713 Schedule C Self-Employment Tax", "$28,770 Schedule C Self-Employment Tax"),
                ("$27,728 Schedule C Self-Employment Tax", "$28,770 Schedule C Self-Employment Tax"),
                ("+$13,180 Annual FICA Payroll Tax Saved", "+$14,235 Annual FICA Payroll Tax Saved"),
                ("+$13,193 Annual FICA Payroll Tax Saved", "+$14,235 Annual FICA Payroll Tax Saved"),
                ("saves $13,180 in FICA taxes.", "saves $14,235 in FICA taxes."),
                ("saves $13,193 in FICA taxes.", "saves $14,235 in FICA taxes."),
                ("$34,425 Unstructured Pass-Through SE Tax", "$33,591 Unstructured Pass-Through SE Tax"),
                ("$32,549 Unstructured Pass-Through SE Tax", "$33,591 Unstructured Pass-Through SE Tax"),
                ("+$12,240 Medicare Surtax & FICA Shield", "+$11,406 Medicare Surtax & FICA Shield"),
                ("+$10,364 Medicare Surtax & FICA Shield", "+$11,406 Medicare Surtax & FICA Shield"),
                ("OASDI $176,100 Social Security Cap", "OASDI $184,500 Social Security Cap"),
                ("$13,193 Annual Payroll Tax Savings vs Sole Proprietorship", "$14,235 Annual Payroll Tax Savings vs Sole Proprietorship"),
                ("up to $176,100 per employee)", "up to $184,500 per employee)"),
                (
                    "or default to First-In, First-Out (FIFO) on Form 8949.",
                    "or apply the statutory First-In, First-Out (FIFO) sequence on Form 8949.",
                ),
                (
                    "Under IRC Section 1(j), expiration of the Tax Cuts and Jobs Act reverts ordinary federal marginal rates to 10%, 15%, 25%, 28%, 33%, 35%, and 39.6% while contracting the single standard deduction from $16,100 (2026) to $13,600 (2027 post-sunset).",
                    "Under OBBBA (P.L. 119-21) and IRC Section 1(j), the 10%, 12%, 22%, 24%, 32%, 35%, and 37% federal marginal rates and 20% Section 199A QBI deduction are permanently extended, with single standard deductions of $16,100 (2026 Rev. Proc. 2025-32) and $16,500 (2027).",
                ),
                (
                    "For a single filer earning $125,000 gross income, reverting from 2026 TCJA brackets ($19,181 federal tax) to 2027 post-sunset brackets ($23,530 federal tax) increases annual federal income tax liability by +$4,349.",
                    "For a single filer earning $125,000 gross income in California, 2026 combined federal, California FTB, and FICA/CA SDI tax liability is $38,767 ($18,734 federal tax with the $16,100 standard deduction, $8,833 CA FTB tax, and $11,200 FICA + 1.3% CA SDI), leaving $86,233 net take-home pay.",
                ),
                (
                    "IRC Section 1(j) TCJA Sunset ($16,100 -> $13,600 Standard Deduction)",
                    "OBBBA (P.L. 119-21) & Rev. Proc. 2025-32 ($16,100 -> $16,500 Standard Deduction)",
                ),
                (
                    "+$4,349 Annual Sunset Tax Increase ($19,181 TCJA vs $23,530 Post-Sunset)",
                    "$38,767 Combined 2026 Tax ($18,734 Federal + $8,833 CA FTB + $11,200 Payroll)",
                ),
                (
                    "Compare 2026 TCJA vs 2027 Post-Sunset Marginal Brackets",
                    "Compare 2026 Rev. Proc. 2025-32 vs 2027 Enacted OBBBA Marginal Brackets",
                ),
                (
                    "High-earner household evaluating SALT cap interaction, NIIT 3.8% surtax, and post-TCJA sunset rate schedules",
                    "High-earner household evaluating SALT cap interaction, NIIT 3.8% surtax, and enacted OBBBA (P.L. 119-21) rate schedules",
                ),
                (
                    "standard deductions, and post-TCJA sunset brackets.",
                    "standard deductions, and enacted OBBBA brackets.",
                ),
                (
                    "and post-TCJA sunset rate reversions (10, 15, 25, 28, 33, 35, and 39.6 percent) alongside",
                    "and enacted OBBBA (P.L. 119-21) permanent brackets (10, 12, 22, 24, 32, 35, and 37 percent) alongside",
                ),
            ):
                if old_s in updated_str:
                    updated_str = updated_str.replace(old_s, new_s)
            if ov_slug == "section-179-vehicle-equipment-deduction":
                if "Calculate Section 179 deductions under IRC Section 179 ($2,560,000 cap, $4,090,000 phase-out)" in updated_str:
                    updated_str = updated_str.replace(
                        "Calculate Section 179 deductions under IRC Section 179 ($2,560,000 cap, $4,090,000 phase-out) and Section 168(k) bonus depreciation on IRS Form 4562.",
                        "Model combined IRC Section 179 expensing, 100% bonus depreciation, and business-use recapture thresholds for commercial vehicles and equipment.",
                    )
                if '"Section 179 Calculator 2026 (Form 4562) | ProfitHelm"' in updated_str:
                    updated_str = updated_str.replace(
                        '"Section 179 Calculator 2026 (Form 4562) | ProfitHelm"',
                        '"Section 179 Commercial Vehicle & Equipment Deduction Calculator | ProfitHelm"',
                    )
            elif ov_slug == "commercial-heavy-vehicle-section-179-weight-calculator":
                for old_desc in (
                    "Model combined IRC Section 179 expensing, 20% bonus depreciation, and business-use recapture thresholds for commercial vehicles and equipment.",
                    "Model combined IRC Section 179 expensing, 100% bonus depreciation, and business-use recapture thresholds for commercial vehicles and equipment.",
                ):
                    updated_str = updated_str.replace(
                        old_desc,
                        "Calculate commercial heavy vehicle (GVWR over 6,000 lbs) IRC Section 179 deductions ($32,000 SUV cap vs full truck expensing) on IRS Form 4562.",
                    )
            elif ov_slug == "equipment-lease-vs-buy-section-179-calculator":
                updated_str = updated_str.replace(
                    "Calculate commercial equipment operating lease tax deductions under IRC Section 162(a)(3) and ASC 842 vs Section 179 purchase expensing.",
                    "Compare commercial equipment lease vs buy after-tax cash flow under IRC Section 162(a)(3) lease deductions and IRC Section 179 purchase expensing.",
                )
        elif tenant_norm == "prexvo":
            for old_s, new_s in cls.PREXVO_ALL_HTML_REPLACEMENTS:
                if old_s in updated_str:
                    updated_str = updated_str.replace(old_s, new_s)
            if any(k in ov_slug for k in ("ibr-hardship", "paye-sunset")) and "rap-vs" not in ov_slug:
                for old_s, new_s in cls.PREXVO_IBR_PAYE_HTML_REPLACEMENTS:
                    if old_s in updated_str:
                        updated_str = updated_str.replace(old_s, new_s)
        elif tenant_norm == "gainhelm":
            for old_s, new_s in cls.GAINHELM_HTML_REPLACEMENTS:
                if old_s in updated_str:
                    updated_str = updated_str.replace(old_s, new_s)
        elif tenant_norm == "lienbond":
            updated_str = updated_str.replace(
                "California, Texas and Florida Calculator | LienBond",
                "California, Texas & Florida Notice Calculator | LienBond",
            )

        if updated_str != serialized:
            parsed = _json_lib.loads(updated_str)
            changed = True
        else:
            parsed = dict(raw_ov)
            changed = False

        if tenant_norm == "prexvo" and "refinanc" in ov_slug:
            discs = parsed.setdefault("mandatory_disclosures", [])
            disclaimer_phrase = "Refinancing a federal student loan into a private note permanently forfeits access to federal income-driven repayment (IDR, SAVE, RAP, IBR), Public Service Loan Forgiveness (PSLF), administrative forbearance, and federal death or disability discharge."
            if not any("permanently forfeits" in str(d).lower() or "forfeits access" in str(d).lower() or "permanently waives" in str(d).lower() for d in discs):
                discs.append(disclaimer_phrase)
                changed = True

        if changed:
            return parsed, True
        return raw_ov, False

    _AUDIT_TRUTH_CACHE: Dict[Tuple[str, str, str, str, bool], List[str]] = {}
    _AUDIT_TRUTH_HTML_SCAN_CACHE: Dict[Tuple[str, str, Tuple[bool, bool, bool]], List[str]] = {}

    @classmethod
    def audit_html_truth_reconciliation(
        cls,
        html_content: str,
        tenant: str,
        rel_path: str = "",
        slug: str = "",
        include_fact_store: bool = True,
    ) -> List[str]:
        """
        Deterministically audits an HTML document for any remaining factual drift,
        intra-page statutory contradictions, inline JS cap mismatches, or speculative filler.
        Returns a list of violation descriptions (empty list == PASS).
        """
        tenant_norm = resolve_canonical_property_id(tenant, default=str(tenant or "").strip().lower() or "profithelm")
        h_digest: Optional[str] = None
        cache_key: Optional[Tuple[str, str, str, str, bool]] = None
        if html_content and len(html_content) >= 256:
            h_digest = hashlib.sha256(html_content.encode("utf-8", errors="ignore")).hexdigest()
            cache_key = (h_digest, tenant_norm, str(rel_path), str(slug), bool(include_fact_store))
            cached_v = cls._AUDIT_TRUTH_CACHE.get(cache_key)
            if cached_v is not None:
                return list(cached_v)

        violations: List[str] = []
        if include_fact_store:
            store = TenantFactStore.get_instance()
            ok, store_violations = store.verify_claim(tenant=tenant, text=html_content, context=rel_path or slug)
            if not ok:
                violations.extend(store_violations)

        combined_slug = f"{rel_path.lower()} {slug.lower()}" if tenant_norm == "prexvo" else ""
        slug_flags = (
            (
                any(k in combined_slug for k in ("ibr-hardship", "paye-sunset")),
                "rap-vs-ibr" in combined_slug,
                "ibr-hardship" in combined_slug,
            )
            if tenant_norm == "prexvo"
            else (False, False, False)
        )
        scan_cache_key = (h_digest, tenant_norm, slug_flags) if h_digest is not None else None
        cached_scan = cls._AUDIT_TRUTH_HTML_SCAN_CACHE.get(scan_cache_key) if scan_cache_key is not None else None

        if cached_scan is not None:
            for msg in cached_scan:
                if msg not in violations:
                    violations.append(msg)
        else:
            scan_violations: List[str] = []
            for filler_old, _ in cls.SPECULATIVE_FILLER_REPLACEMENTS:
                if filler_old in html_content:
                    scan_violations.append(f"Speculative filler phrase detected: '{filler_old.strip()}'")

            if tenant_norm == "profithelm":
                for old_str, _ in cls.PROFITHELM_HTML_REPLACEMENTS:
                    if old_str in html_content:
                        msg = f"Unreconciled ProfitHelm statutory figure or JS cap: '{old_str[:60]}'"
                        if msg not in scan_violations:
                            scan_violations.append(msg)
                if "Math.min(cost, 31300)" in html_content or "Math.min(basis, 31300)" in html_content or "const suvCap = 31300" in html_content or "Math.min(cost, 30500)" in html_content or "Math.min(basis, 30500)" in html_content or "const suvCap = 30500" in html_content:
                    scan_violations.append("Inline calculator JS uses stale 30500/31300 Heavy SUV cap instead of 2026 statutory 32000 cap (IRS Rev. Proc. 2025-32)")
                if "<td>60% on balance</td>" in html_content or "60% on balance (2024-2026 phase-down)" in html_content or "<td>20% on balance</td>" in html_content:
                    scan_violations.append("Stale 20%/60% bonus depreciation rate in 2026 Section 179 comparison table (P.L. 119-21 Sec. 70301 rate is 100%)")
            elif tenant_norm == "prexvo":
                for old_str, _ in cls.PREXVO_ALL_HTML_REPLACEMENTS:
                    if old_str in html_content:
                        msg = f"Unreconciled Prexvo statutory figure or plan claim: '{old_str[:60]}'"
                        if msg not in scan_violations:
                            scan_violations.append(msg)
                is_ibr_or_paye = (
                    slug_flags[0]
                    or "IBR Hardship Cap Calculator" in html_content
                    or "PAYE Sunset Eligibility" in html_content
                ) and not slug_flags[1]
                if is_ibr_or_paye:
                    for old_str, _ in cls.PREXVO_IBR_PAYE_HTML_REPLACEMENTS:
                        if old_str in html_content:
                            msg = f"Unreconciled Prexvo IBR/PAYE threshold figure: '{old_str[:60]}'"
                            if msg not in scan_violations:
                                scan_violations.append(msg)
                    if slug_flags[2] and '"name": "RAP vs IBR Repayment Calculator"' in html_content:
                        scan_violations.append("IBR Hardship Cap Calculator JSON-LD SoftwareApplication name misattributed as 'RAP vs IBR Repayment Calculator'")
            elif tenant_norm == "gainhelm":
                for old_str, _ in cls.GAINHELM_HTML_REPLACEMENTS:
                    if old_str in html_content:
                        msg = f"Unreconciled GainHelm statutory figure or pricing tier: '{old_str[:60]}'"
                        if msg not in scan_violations:
                            scan_violations.append(msg)

            if scan_cache_key is not None:
                if len(cls._AUDIT_TRUTH_HTML_SCAN_CACHE) > 1024:
                    cls._AUDIT_TRUTH_HTML_SCAN_CACHE.clear()
                cls._AUDIT_TRUTH_HTML_SCAN_CACHE[scan_cache_key] = list(scan_violations)
            for msg in scan_violations:
                if msg not in violations:
                    violations.append(msg)

        if cache_key is not None:
            if len(cls._AUDIT_TRUTH_CACHE) > 1024:
                cls._AUDIT_TRUTH_CACHE.clear()
            cls._AUDIT_TRUTH_CACHE[cache_key] = list(violations)
        return violations

    @classmethod
    def reconcile_estate_assets(
        cls,
        dist_dir: Union[str, Path],
        property_id: str,
        repo_root: Optional[Union[str, Path]] = None,
        sync_llms: bool = True,
        degraded_overlays: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[str]:
        """
        Scans and deterministically reconciles all estate assets (HTML, JSON, XML, TXT, MD, JS, VTT)
        against TenantFactStore, statutory limits, and tenant Python engines.
        Returns list of repaired asset file paths.
        Zero em-dashes. Zero en-dashes.
        """
        import json as _json_lib
        tenant_norm = resolve_canonical_property_id(property_id, default=str(property_id or "").strip().lower() or "profithelm")
        d = Path(dist_dir).resolve()
        r_root = Path(repo_root).resolve() if repo_root else (d.parent if d.parent.is_dir() else None)
        repaired_paths: List[str] = []

        # 1. Reconcile dist/manifests/*.json FIRST
        manifests_dir = d / "manifests"
        if manifests_dir.is_dir():
            for man_f in sorted(manifests_dir.glob("*.json")):
                try:
                    raw_txt = man_f.read_text(encoding="utf-8")
                    man_d = _json_lib.loads(raw_txt)
                    changed = False
                    if tenant_norm == "profithelm":
                        if "2,560,000" in raw_txt and ("suv" in man_f.name.lower() or "vehicle" in man_f.name.lower()):
                            raw_txt = raw_txt.replace("2,560,000", "32,000")
                            man_d = _json_lib.loads(raw_txt)
                            changed = True
                        if man_f.name == "s-corp-reasonable-salary-tax-calculator.json" and (
                            man_d.get("published_output") in (19125.0, 13180.0, 13193.0)
                            or (isinstance(man_d.get("inputs"), dict) and man_d["inputs"].get("ss_wage_cap") == 176100.0)
                        ):
                            man_d["formula"] = "round((min(net_business_income * 0.9235, ss_wage_cap) - min(reasonable_salary, ss_wage_cap)) * 0.124 + ((net_business_income * 0.9235) - reasonable_salary) * 0.029, 0)"
                            man_d["inputs"] = {"net_business_income": 220000.0, "reasonable_salary": 95000.0, "ss_wage_cap": 184500.0}
                            man_d["published_output"] = 14235.0
                            man_d["sample_calculation"] = "Deterministic evaluation of round((min(net_business_income * 0.9235, ss_wage_cap) - min(reasonable_salary, ss_wage_cap)) * 0.124 + ((net_business_income * 0.9235) - reasonable_salary) * 0.029, 0) produces 14,235.00."
                            changed = True
                        if man_f.name == "irs-2027-tax-brackets.json" and (
                            "sunset_standard_deduction" in raw_txt
                            or man_d.get("published_output") == 23530.0
                            or "1240.0 + min(max(0.0," in str(man_d.get("formula", ""))
                            or "standard_deduction_2026" in raw_txt
                        ):
                            man_d["formula_id"] = "federal_income_tax_2026_single"
                            man_d["model_name"] = "2026 Federal Income Tax (Single Filer, Rev. Proc. 2025-32)"
                            man_d["formula"] = (
                                "round(0.10 * min(max(0.0, gross_income - standard_deduction), 12400.0) "
                                "+ 0.12 * max(0.0, min(max(0.0, gross_income - standard_deduction), 50400.0) - 12400.0) "
                                "+ 0.22 * max(0.0, min(max(0.0, gross_income - standard_deduction), 105700.0) - 50400.0) "
                                "+ 0.24 * max(0.0, min(max(0.0, gross_income - standard_deduction), 201775.0) - 105700.0) "
                                "+ 0.32 * max(0.0, min(max(0.0, gross_income - standard_deduction), 256225.0) - 201775.0) "
                                "+ 0.35 * max(0.0, min(max(0.0, gross_income - standard_deduction), 640600.0) - 256225.0) "
                                "+ 0.37 * max(0.0, max(0.0, gross_income - standard_deduction) - 640600.0), 2)"
                            )
                            man_d["inputs"] = {"gross_income": 125000.0, "standard_deduction": 16100.0}
                            man_d["published_output"] = 18734.0
                            man_d["statutory_authority"] = "P.L. 119-21 Section 70101, IRS Rev. Proc. 2025-32 & Rev. Proc. 2026-35"
                            man_d["sample_calculation"] = "For a $125,000 Single filer in 2026 under permanent OBBBA (P.L. 119-21) 10%-37% brackets ($16,100 standard deduction under Rev. Proc. 2025-32), federal income tax is $18,734.00."
                            changed = True
                        if man_f.name == "equipment-lease-vs-buy-section-179-calculator.json" and (
                            "year_one_financing_payments" in raw_txt or man_d.get("published_output") == 18000.0
                        ):
                            man_d["formula_id"] = "section_179_heavy_suv_plus_bonus_2026"
                            man_d["model_name"] = "2026Section179with32000HeavySUVCap100BonusDepreciation"
                            man_d["formula"] = (
                                "round(min(equipment_cost * business_use_pct, 32000.0 if is_heavy_suv == 1 else max(0.0, 2560000.0 - max(0.0, equipment_cost - 4090000.0))) "
                                "+ max(0.0, equipment_cost * business_use_pct - min(equipment_cost * business_use_pct, 32000.0 if is_heavy_suv == 1 else max(0.0, 2560000.0 - max(0.0, equipment_cost - 4090000.0)))) * (bonus_pct / 100.0), 2)"
                            )
                            man_d["inputs"] = {
                                "equipment_cost": 85000.0,
                                "business_use_pct": 0.8,
                                "is_heavy_suv": 1,
                                "bonus_pct": 100.0,
                            }
                            man_d["published_output"] = 68000.0
                            man_d["statutory_authority"] = "IRC Section 179, P.L. 119-21 Section 70301 (168(k)), Rev. Proc. 2025-32"
                            man_d["sample_calculation"] = "Baseline TruthPack inputs produce 68000.0"
                            changed = True
                    elif tenant_norm == "prexvo":
                        if "refinanc" in man_f.name.lower():
                            discs = man_d.setdefault("mandatory_disclosures", [])
                            if not any("permanently forfeits" in disc.lower() for disc in discs):
                                discs.append(
                                    "Refinancing a federal student loan into a private note permanently forfeits access to federal income-driven repayment (IDR, SAVE, RAP, IBR), Public Service Loan Forgiveness (PSLF), administrative forbearance, and federal death or disability discharge."
                                )
                                changed = True
                    if changed:
                        man_f.write_text(_json_lib.dumps(man_d, indent=2), encoding="utf-8")
                        repaired_paths.append(str(man_f))
                except Exception:
                    pass

        # 2a. Reconcile dist/feed.xml
        feed_xml_f = d / "feed.xml"
        if feed_xml_f.is_file():
            try:
                raw_feed = feed_xml_f.read_text(encoding="utf-8")
                updated_feed = raw_feed
                if tenant_norm == "prexvo":
                    if "refinanc" in updated_feed.lower() and not any(ph in updated_feed.lower() for ph in ("permanently forfeits", "forfeited federal benefits", "waives federal protections")):
                        updated_feed = re.sub(
                            r'(<description>[^<]*?(?:refinanc|forgiveness)[^<]*?)(</description>)',
                            r'\1 (Note: refinancing permanently forfeits access to federal income-driven repayment and forgiveness programs).\2',
                            updated_feed,
                            count=1,
                            flags=re.I,
                        )
                if updated_feed != raw_feed:
                    feed_xml_f.write_text(updated_feed, encoding="utf-8")
                    repaired_paths.append(str(feed_xml_f))
            except Exception:
                pass

        # 2b. Reconcile dist/llms.txt and dist/llms-full.txt
        if tenant_norm == "prexvo":
            for fname in ("llms.txt", "llms-full.txt"):
                l_f = d / fname
                if l_f.is_file():
                    try:
                        llms_txt = l_f.read_text(encoding="utf-8")
                        if "refinanc" in llms_txt.lower() and not any(ph in llms_txt.lower() for ph in ("permanently forfeits", "forfeited federal benefits", "waives federal protections")):
                            if fname == "llms.txt":
                                llms_txt = re.sub(
                                    r'(- \[Student Loan Refinance Break-Even Calculator\]\([^\)]+\):[^\n]+)',
                                    r'\1 Note: refinancing permanently forfeits access to federal income-driven repayment and forgiveness programs.',
                                    llms_txt,
                                )
                            else:
                                llms_txt += "\n\nNote on Student Loan Refinancing: Refinancing a federal student loan into a private note permanently forfeits access to federal income-driven repayment (IDR, SAVE, RAP, IBR), Public Service Loan Forgiveness (PSLF), and federal protections.\n"
                            l_f.write_text(llms_txt, encoding="utf-8")
                            repaired_paths.append(str(l_f))
                    except Exception:
                        pass

        # 2c. Reconcile dist/catalog.json
        cat_f = d / "catalog.json"
        if cat_f.is_file() and tenant_norm == "prexvo":
            try:
                raw_cat = cat_f.read_text(encoding="utf-8")
                if "refinanc" in raw_cat.lower() and not any(ph in raw_cat.lower() for ph in ("permanently forfeits", "forfeited federal benefits", "waives federal protections")):
                    parsed_cat = _json_lib.loads(raw_cat)
                    if isinstance(parsed_cat, dict) and "tools" in parsed_cat:
                        for t_obj in parsed_cat["tools"]:
                            if "refinanc" in str(t_obj.get("slug", "")).lower():
                                t_obj["description"] = t_obj.get("description", "") + " Refinancing permanently forfeits access to federal income-driven repayment and forgiveness programs."
                        cat_f.write_text(_json_lib.dumps(parsed_cat, indent=2), encoding="utf-8")
                        repaired_paths.append(str(cat_f))
            except Exception:
                pass

        # 2d. Reconcile dist/videos/*.vtt
        vid_dir = d / "videos"
        if vid_dir.is_dir() and tenant_norm == "prexvo":
            for vtt_f in sorted(vid_dir.glob("*.vtt")):
                if "refinanc" in vtt_f.name.lower():
                    try:
                        vtt_txt = vtt_f.read_text(encoding="utf-8")
                        if not any(ph in vtt_txt.lower() for ph in ("permanently forfeits", "forfeited federal benefits", "waives federal protections")):
                            vtt_txt = vtt_txt.rstrip() + "\n\n00:00:29.800 --> 00:00:36.000\nRefinancing federal student loans permanently forfeits access to federal income-driven repayment and forgiveness programs.\n"
                            vtt_f.write_text(vtt_txt, encoding="utf-8")
                            repaired_paths.append(str(vtt_f))
                    except Exception:
                        pass

        # 2e. Index degraded rolled-back overlays
        if degraded_overlays is None:
            degraded_overlays = {}
            ov_search_dirs = []
            if r_root:
                ov_search_dirs.extend([r_root / "content" / "overlays", r_root / ".agy" / "overlays"])
            if d.parent != r_root:
                ov_search_dirs.extend([d.parent / "content" / "overlays", d.parent / ".agy" / "overlays"])
            for ov_dir in ov_search_dirs:
                if not ov_dir.is_dir():
                    continue
                for ov_file in sorted(ov_dir.rglob("*.json")):
                    try:
                        ov_data = _json_lib.loads(ov_file.read_text(encoding="utf-8"))
                        if isinstance(ov_data, dict) and str(ov_data.get("status") or "").upper() == "DEGRADED_ROLLED_BACK":
                            rel_s = str(ov_data.get("slug") or ov_file.relative_to(ov_dir).with_suffix("").as_posix()).strip("/")
                            degraded_overlays[rel_s] = ov_data
                            for hub_pfx in ("irs-2027-tax-brackets", "section-1031-calculator", "section-179-calculator"):
                                if rel_s.startswith(f"{hub_pfx}-"):
                                    alt_s = f"{hub_pfx}/{rel_s[len(hub_pfx) + 1:]}"
                                    degraded_overlays[alt_s] = ov_data
                    except Exception:
                        pass

        # 3. Reconcile HTML files in dist/
        if d.is_dir():
            for html_file in sorted(d.rglob("*.html")):
                if html_file.name.startswith("."):
                    continue
                try:
                    rel_p = html_file.relative_to(d).as_posix()
                    parts = html_file.relative_to(d).parts
                    if len(parts) >= 2 and parts[0] == "tools":
                        if parts[1] == "index.html":
                            slug = ""
                        elif len(parts) >= 4 and parts[-1] == "index.html":
                            slug = "/".join(parts[1:-1])
                        else:
                            slug = parts[1]
                    else:
                        slug = html_file.stem
                    m_data = None
                    if slug:
                        cand_files = [
                            manifests_dir / f"{slug}.json",
                            manifests_dir / f"{slug.replace('/', '-')}.json",
                            manifests_dir / f"{slug.replace('/', '_')}.json",
                        ]
                        for cand_m_f in cand_files:
                            if cand_m_f.is_file():
                                try:
                                    m_data = _json_lib.loads(cand_m_f.read_text(encoding="utf-8"))
                                    break
                                except Exception:
                                    pass
                    content = html_file.read_text(encoding="utf-8", errors="ignore")
                    updated_html, rep_list = cls.reconcile_html_truth(
                        content,
                        tenant=tenant_norm,
                        rel_path=rel_p,
                        slug=slug,
                        manifest_data=m_data,
                    )
                    slug_keys = [slug, rel_p.replace("tools/", "").replace("/index.html", ""), rel_p.replace("/index.html", "")]
                    matched_ov = next((degraded_overlays[k] for k in slug_keys if k in degraded_overlays), None)
                    if matched_ov:
                        from pseofactory.gsc_remediation import rollback_degraded_overlay_from_html
                        before_rb = updated_html
                        updated_html = rollback_degraded_overlay_from_html(updated_html, matched_ov)
                        if updated_html != before_rb and "degraded_overlay_rolled_back" not in rep_list:
                            rep_list.append("degraded_overlay_rolled_back")
                    if rep_list and updated_html != content:
                        tmp_html = html_file.with_name(f".{html_file.name}.{os.getpid()}.tmp")
                        try:
                            tmp_html.write_text(updated_html, encoding="utf-8")
                            os.replace(tmp_html, html_file)
                        finally:
                            if tmp_html.exists():
                                try:
                                    tmp_html.unlink()
                                except OSError:
                                    pass
                        repaired_paths.append(str(html_file))
                except Exception:
                    pass

        # 3. Reconcile dist/ai-benchmarks/ and syndication/ai_benchmarks/
        target_benchmark_dirs = [d / "ai-benchmarks"]
        if r_root:
            target_benchmark_dirs.append(r_root / "syndication" / "ai_benchmarks")
        central_bench = Path(f"/home/ubuntuadmin/projects/pseofactory/syndication/{tenant_norm}/ai_benchmarks")
        if central_bench.is_dir():
            target_benchmark_dirs.append(central_bench)

        for bench_dir in target_benchmark_dirs:
            if not bench_dir.is_dir():
                continue
            hub_json = bench_dir / "public_statistics_citation_hub.json"
            if hub_json.is_file():
                try:
                    txt = hub_json.read_text(encoding="utf-8")
                    updated_txt = txt.replace("IRC Sections ", "IRC Section ")
                    if tenant_norm == "profithelm":
                        updated_txt = re.sub(
                            r'((?:qualifying\s+)?(?:heavy\s+SUVs?|commercial\s+vehicles?|passenger\s+vehicles?)\s+(?:capped\s+at|cap\s+at(?:\s+a)?|limit\s+of|deduction\s+of)\s+)\$(?:2,560,000|2\.56M|31,300|30,500)',
                            r'\1$32,000',
                            updated_txt,
                            flags=re.IGNORECASE,
                        )
                    if updated_txt != txt:
                        hub_json.write_text(updated_txt, encoding="utf-8")
                        repaired_paths.append(str(hub_json))
                except Exception:
                    pass

            hub_md = bench_dir / "public_statistics_citation_hub.md"
            if hub_md.is_file():
                try:
                    txt = hub_md.read_text(encoding="utf-8")
                    updated_txt = txt.replace("IRC Sections ", "IRC Section ")
                    if tenant_norm == "profithelm":
                        updated_txt = re.sub(
                            r'((?:qualifying\s+)?(?:heavy\s+SUVs?|commercial\s+vehicles?|passenger\s+vehicles?)\s+(?:capped\s+at|cap\s+at(?:\s+a)?|limit\s+of|deduction\s+of)\s+)\$(?:2,560,000|2\.56M|31,300|30,500)',
                            r'\1$32,000',
                            updated_txt,
                            flags=re.IGNORECASE,
                        )
                    if updated_txt != txt:
                        hub_md.write_text(updated_txt, encoding="utf-8")
                        repaired_paths.append(str(hub_md))
                except Exception:
                    pass

            ref_md = bench_dir / "ai_citations_reference.md"
            if ref_md.is_file():
                try:
                    txt = ref_md.read_text(encoding="utf-8")
                    updated_txt = txt.replace("IRC Sections 179", "IRC Section 179").replace("IRC Sections ", "IRC Section ")
                    if updated_txt != txt:
                        ref_md.write_text(updated_txt, encoding="utf-8")
                        repaired_paths.append(str(ref_md))
                except Exception:
                    pass

        # 4. Reconcile dist/videos/batch_seo_catalog.json and tenant overlays
        vid_cat = d / "videos" / "batch_seo_catalog.json"
        if vid_cat.is_file():
            try:
                txt = vid_cat.read_text(encoding="utf-8")
                updated_txt = txt.replace("IRC Sections 3111 & 3301", "IRC Section 3111 and Section 3301")
                updated_txt = updated_txt.replace("IRC Sections 3111", "IRC Section 3111").replace("IRC Sections ", "IRC Section ")
                if updated_txt != txt:
                    vid_cat.write_text(updated_txt, encoding="utf-8")
                    repaired_paths.append(str(vid_cat))
            except Exception:
                pass

        if r_root and r_root.is_dir():
            for ov_rel in (".agy/overlays", "content/overlays"):
                ov_dir = r_root / ov_rel
                if not ov_dir.is_dir():
                    continue
                for ov_file in sorted(ov_dir.glob("*.json")):
                    try:
                        ov_txt = ov_file.read_text(encoding="utf-8")
                        ov_new = ov_txt
                        if tenant_norm == "profithelm":
                            for old_str, new_str in cls.PROFITHELM_HTML_REPLACEMENTS:
                                if old_str in ov_new:
                                    ov_new = ov_new.replace(old_str, new_str)
                        elif tenant_norm == "prexvo":
                            for old_str, new_str in cls.PREXVO_ALL_HTML_REPLACEMENTS:
                                if old_str in ov_new:
                                    ov_new = ov_new.replace(old_str, new_str)
                        elif tenant_norm == "gainhelm":
                            for old_str, new_str in cls.GAINHELM_HTML_REPLACEMENTS:
                                if old_str in ov_new:
                                    ov_new = ov_new.replace(old_str, new_str)
                        if ov_new != ov_txt:
                            ov_file.write_text(ov_new, encoding="utf-8")
                            repaired_paths.append(str(ov_file))
                    except Exception:
                        pass
            dyn_tools_f = r_root / "profithelm" / "data" / "dynamic_tools.json"
            if dyn_tools_f.is_file() and tenant_norm == "profithelm":
                try:
                    dt_txt = dyn_tools_f.read_text(encoding="utf-8")
                    dt_new = dt_txt
                    for old_str, new_str in cls.PROFITHELM_HTML_REPLACEMENTS:
                        if old_str in dt_new:
                            dt_new = dt_new.replace(old_str, new_str)
                    parsed_dt = _json_lib.loads(dt_new)
                    dt_items = parsed_dt if isinstance(parsed_dt, list) else parsed_dt.get("tools", [])
                    dt_item_changed = False
                    for dt_obj in dt_items:
                        if isinstance(dt_obj, dict):
                            for d_key in ("description", "problem_statement"):
                                d_val = str(dt_obj.get(d_key) or "")
                                if len(d_val) > 160 and "with real-time scenario modeling." in d_val:
                                    dt_obj[d_key] = d_val.replace("with real-time scenario modeling.", "with scenario analysis.")
                                    dt_item_changed = True
                    if dt_item_changed:
                        dt_new = _json_lib.dumps(parsed_dt, ensure_ascii=False, indent=2) + "\n"
                    if dt_new != dt_txt:
                        dyn_tools_f.write_text(dt_new, encoding="utf-8")
                        repaired_paths.append(str(dyn_tools_f))
                except Exception:
                    pass
        if tenant_norm == "profithelm":
            for mf_name in ("feed.xml", "llms.txt", "llms-full.txt"):
                mf_p = d / mf_name
                if mf_p.is_file():
                    try:
                        mf_txt = mf_p.read_text(encoding="utf-8")
                        mf_new = mf_txt
                        for old_str, new_str in cls.PROFITHELM_HTML_REPLACEMENTS:
                            if old_str in mf_new:
                                mf_new = mf_new.replace(old_str, new_str)
                        if mf_new != mf_txt:
                            mf_p.write_text(mf_new, encoding="utf-8")
                            repaired_paths.append(str(mf_p))
                    except Exception:
                        pass
        if sync_llms:
            try:
                from pseofactory.maintenance import AutonomousFreshnessMaintenanceEngine

                AutonomousFreshnessMaintenanceEngine.sync_tenant_llms_manifests(
                    dist_dir=d,
                    property_id=tenant_norm,
                )
            except Exception:
                pass

        # 5. Reconcile syndication/ and affiliate routes
        target_synd_dirs = []
        if r_root and (r_root / "syndication").is_dir():
            target_synd_dirs.append(r_root / "syndication")
        central_synd = Path(f"/home/ubuntuadmin/projects/pseofactory/syndication/{tenant_norm}")
        if central_synd.is_dir():
            target_synd_dirs.append(central_synd)

        for s_dir in target_synd_dirs:
            if not s_dir.is_dir():
                continue
            # Reconcile affiliate_routes_verified.json
            aff_json_f = s_dir / "affiliate_routes_verified.json"
            if aff_json_f.is_file():
                try:
                    from pseofactory.affiliates import (
                        AFFILIATE_REGISTRY,
                        AFFILIATE_REGISTRY_BY_PROPERTY,
                        lookup_affiliate_partner,
                    )
                    from pseofactory.maintenance import CrossPropertyContaminationScanner

                    raw_aff = _json_lib.loads(aff_json_f.read_text(encoding="utf-8"))
                    routes = raw_aff.get("routes", [])
                    scanner = CrossPropertyContaminationScanner()
                    cleaned_routes = []
                    for r in routes:
                        if isinstance(r, dict):
                            route_hint = str(r.get("route") or r.get("url") or "")
                            partner_key = str(
                                r.get("partner")
                                or (route_hint if "/r/" in route_hint else "")
                                or r.get("slug")
                                or route_hint
                            )
                        else:
                            partner_key = str(r)
                        partner_norm = (
                            partner_key.lower()
                            .split("?", 1)[0]
                            .replace("/r/", "")
                            .strip("/")
                            .replace("-", "_")
                        )
                        owned_entry = lookup_affiliate_partner(partner_norm, property_id=tenant_norm)
                        if owned_entry is not None:
                            owned_prop = str(getattr(owned_entry, "property_id", "") or "").strip().lower()
                            if owned_prop == tenant_norm:
                                cleaned_routes.append(r)
                            continue
                        if partner_norm and (
                            partner_norm in AFFILIATE_REGISTRY
                            or any(
                                prop_key != tenant_norm and partner_norm in prop_reg
                                for prop_key, prop_reg in AFFILIATE_REGISTRY_BY_PROPERTY.items()
                            )
                        ):
                            continue
                        route_blob = _json_lib.dumps(r) if isinstance(r, dict) else str(r)
                        if scanner.scan_text(route_blob, tenant_norm):
                            continue
                        cleaned_routes.append(r)

                    if len(cleaned_routes) != len(routes):
                        raw_aff["routes"] = cleaned_routes
                        raw_aff["verified_routes_count"] = len(cleaned_routes)
                        aff_json_f.write_text(_json_lib.dumps(raw_aff, indent=2), encoding="utf-8")
                        repaired_paths.append(str(aff_json_f))
                except Exception:
                    pass

            # Quora / syndication tax brackets (3.0% bracket claim)
            for qf in s_dir.rglob("*"):
                if qf.is_file() and qf.suffix in (".md", ".txt"):
                    try:
                        txt = qf.read_text(encoding="utf-8")
                        updated_txt = txt
                        if re.search(r'(?:\b3(?:\.0)?%\s+(?:federal\s+)?(?:marginal\s+)?(?:tax\s+)?bracket\b|\b(?:federal\s+)?(?:tax\s+)?bracket\s+(?:of|at)\s+3(?:\.0)?%)', updated_txt, re.I):
                            updated_txt = re.sub(
                                r'(?:\bfederal\s+)?3(?:\.0)?%\s+(?:federal\s+)?(?:marginal\s+)?(?:tax\s+)?bracket\b',
                                '3% marginal rate increase',
                                updated_txt,
                                flags=re.I,
                            )
                            updated_txt = re.sub(
                                r'\b(?:federal\s+)?(?:tax\s+)?bracket\s+(?:of|at)\s+3(?:\.0)?%',
                                '3% marginal rate increase',
                                updated_txt,
                                flags=re.I,
                            )
                            updated_txt = updated_txt.replace("3.0% federal marginal tax bracket", "3 percentage point marginal tax rate increase")
                            updated_txt = updated_txt.replace("3.0% bracket", "3 percentage point rate shift")
                        if updated_txt != txt:
                            qf.write_text(updated_txt, encoding="utf-8")
                            repaired_paths.append(str(qf))
                    except Exception:
                        pass

            # PSLF 120 payments in save-plan-litigation-transition
            save_dir = s_dir / "save-plan-litigation-transition"
            if save_dir.is_dir():
                for sf in save_dir.glob("*"):
                    if sf.is_file() and sf.suffix in (".json", ".md", ".txt"):
                        try:
                            txt = sf.read_text(encoding="utf-8")
                            updated_txt = txt
                            if "2022 PSLF" in updated_txt:
                                updated_txt = updated_txt.replace("2022 PSLF", "120 monthly PSLF")
                            if updated_txt != txt:
                                sf.write_text(updated_txt, encoding="utf-8")
                                repaired_paths.append(str(sf))
                        except Exception:
                            pass

            # Prexvo Refinance Assets YMYL Forfeiture Disclaimer in syndication
            if tenant_norm == "prexvo":
                disclaimer_para = "\n\nMandatory Regulatory Disclosure: Refinancing federal student loans permanently waives federal protections and forfeits access to federal income-driven repayment (IDR, SAVE, RAP, IBR), Public Service Loan Forgiveness (PSLF), administrative forbearance, and federal death or disability discharge."
                disclaimer_html = '\n<p class="regulatory-disclosure" style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 1.5rem;"><strong>Mandatory Regulatory Disclosure:</strong> Refinancing federal student loans permanently waives federal protections and forfeits access to federal income-driven repayment (IDR, SAVE, RAP, IBR), Public Service Loan Forgiveness (PSLF), administrative forbearance, and federal death or disability discharge.</p>'
                for rf in s_dir.rglob("*"):
                    if not rf.is_file() or rf.name.startswith("."):
                        continue
                    if "refinanc" in rf.name.lower() or "refinanc" in str(rf).lower():
                        if rf.suffix in (".md", ".txt"):
                            try:
                                txt = rf.read_text(encoding="utf-8")
                                if "permanently forfeits" not in txt and "waives federal protections" not in txt:
                                    rf.write_text(txt.rstrip() + disclaimer_para, encoding="utf-8")
                                    repaired_paths.append(str(rf))
                            except Exception:
                                pass
                        elif rf.suffix == ".html":
                            try:
                                txt = rf.read_text(encoding="utf-8")
                                if "permanently forfeits" not in txt and "waives federal protections" not in txt:
                                    if "</body>" in txt:
                                        txt = txt.replace("</body>", f"{disclaimer_html}\n</body>", 1)
                                    else:
                                        txt = txt + disclaimer_html
                                    rf.write_text(txt, encoding="utf-8")
                                    repaired_paths.append(str(rf))
                            except Exception:
                                pass
                        elif rf.suffix == ".json":
                            try:
                                raw_json = _json_lib.loads(rf.read_text(encoding="utf-8"))
                                changed_json = False
                                if isinstance(raw_json, dict):
                                    if "markdown" in raw_json and isinstance(raw_json["markdown"], str):
                                        if "permanently forfeits" not in raw_json["markdown"] and "waives federal protections" not in raw_json["markdown"]:
                                            raw_json["markdown"] = raw_json["markdown"].rstrip() + disclaimer_para
                                            changed_json = True
                                    if "description" in raw_json and isinstance(raw_json["description"], str):
                                        if "permanently forfeits" not in raw_json["description"] and "waives federal protections" not in raw_json["description"]:
                                            raw_json["description"] = f"{raw_json['description']} Warning: Refinancing federal student loans permanently waives federal protections and forfeits access to federal IDR and PSLF.".strip()
                                            changed_json = True
                                    if "files" in raw_json and isinstance(raw_json["files"], dict):
                                        for fn, fobj in raw_json["files"].items():
                                            if isinstance(fobj, dict) and "content" in fobj and isinstance(fobj["content"], str):
                                                if "permanently forfeits" not in fobj["content"] and "waives federal protections" not in fobj["content"]:
                                                    fobj["content"] = fobj["content"].rstrip() + disclaimer_para
                                                    changed_json = True
                                if changed_json:
                                    rf.write_text(_json_lib.dumps(raw_json, indent=2), encoding="utf-8")
                                    repaired_paths.append(str(rf))
                            except Exception:
                                pass

        # Prexvo Refinance .vtt transcripts
        if tenant_norm == "prexvo" and d.is_dir():
            vtt_dir = d / "videos"
            if vtt_dir.is_dir():
                for vtt_f in vtt_dir.glob("*refinanc*.vtt"):
                    try:
                        vtt_txt = vtt_f.read_text(encoding="utf-8")
                        if "permanently forfeits" not in vtt_txt:
                            vtt_append = "\n\n00:00:29.800 --> 00:00:35.000\nMandatory Regulatory Disclosure: Refinancing federal student loans permanently waives federal protections and forfeits access to federal IDR and PSLF."
                            vtt_f.write_text(vtt_txt.rstrip() + vtt_append, encoding="utf-8")
                            repaired_paths.append(str(vtt_f))
                    except Exception:
                        pass

        # GainHelm HIPAA 45 CFR 160.404 Tier 3 benchmark parity across syndication, ai-benchmarks, and video catalog
        if tenant_norm == "gainhelm" and r_root is not None and r_root.is_dir():
            gh_repls = [
                (
                    "(2,500 ePHI records * $165 forensic/notification cost) + $100,000 45 CFR 160.404 Tier 2 reasonable cause penalty = $512,500 total HIPAA breach exposure",
                    "(1,500 ePHI records * $165 forensic/notification cost) + $140,000 legal/PR crisis defense + $2,190,294 45 CFR 160.404 Tier 3 penalty cap = $2,577,794 total HIPAA breach exposure",
                ),
                (
                    "(2,500 ePHI records * $165 per-record forensic/notification cost) + $113,000 45 CFR 160.404 Tier 2 penalty = $525,500 total HIPAA breach exposure",
                    "(1,500 ePHI records * $165 per-record forensic/notification cost) + $140,000 legal/PR crisis defense + $2,190,294 45 CFR 160.404 Tier 3 penalty cap = $2,577,794 total HIPAA breach exposure",
                ),
                ("2,500 ePHI records", "1,500 ePHI records"),
                ("$512,500 total HIPAA breach exposure", "$2,577,794 total HIPAA breach exposure"),
                ("$525,500 total HIPAA breach exposure", "$2,577,794 total HIPAA breach exposure"),
                ("$2,455,313 total HIPAA breach exposure", "$2,577,794 total HIPAA breach exposure"),
                ("$512,500.00", "$2,577,794.00"),
                ("$525,500.00", "$2,577,794.00"),
                ("$512,500", "$2,577,794"),
                ("$525,500", "$2,577,794"),
                ("512500.0", "2577794.0"),
                ("525500.0", "2577794.0"),
                ("512500", "2577794"),
                ("525500", "2577794"),
                ("$2,067,813", "$2,190,294"),
                ("2067813", "2190294"),
            ]
            gh_targets: List[Path] = []
            for sub_rel in ("syndication", "ai-benchmarks", "dist/ai-benchmarks", "dist/videos"):
                sub_p = r_root / sub_rel
                if sub_p.is_dir():
                    for ext in ("*.html", "*.md", "*.txt", "*.json", "*.jsonl"):
                        gh_targets.extend(sub_p.rglob(ext))
            for gf in gh_targets:
                if "hipaa" not in gf.as_posix().lower() and gf.name != "batch_seo_catalog.json" and "benchmark" not in gf.name.lower():
                    continue
                try:
                    g_orig = gf.read_text(encoding="utf-8")
                    g_txt = g_orig
                    for old_s, new_s in gh_repls:
                        if old_s in g_txt:
                            g_txt = g_txt.replace(old_s, new_s)
                    if g_txt != g_orig:
                        gf.write_text(g_txt, encoding="utf-8")
                        repaired_paths.append(str(gf))
                except Exception:
                    pass

        # 6. Prexvo Refinance Assets YMYL Forfeiture Disclaimer in dist (catalog.json, feed.xml, llms.txt, llms-full.txt)
        if tenant_norm == "prexvo" and d.is_dir():
            disclaimer_str = "Refinancing a federal student loan into a private note permanently forfeits access to federal income-driven repayment (IDR, SAVE, RAP, IBR), Public Service Loan Forgiveness (PSLF), administrative forbearance, and federal death or disability discharge."
            feed_xml = d / "feed.xml"
            if feed_xml.is_file():
                try:
                    txt = feed_xml.read_text(encoding="utf-8")
                    if "permanently forfeits" not in txt:
                        idx = txt.find("<link>https://prexvo.com/tools/student-loan-refinance-break-even-calculator/</link>")
                        if idx != -1:
                            desc_start = txt.find("<description>", idx)
                            desc_end = txt.find("</description>", desc_start)
                            if desc_start != -1 and desc_end != -1:
                                orig_desc = txt[desc_start+13:desc_end]
                                new_desc = f"{orig_desc} Warning: {disclaimer_str}"
                                txt = txt[:desc_start+13] + new_desc + txt[desc_end:]
                                feed_xml.write_text(txt, encoding="utf-8")
                                repaired_paths.append(str(feed_xml))
                except Exception:
                    pass

            catalog_json = d / "catalog.json"
            if catalog_json.is_file():
                try:
                    cat_data = _json_lib.loads(catalog_json.read_text(encoding="utf-8"))
                    cat_changed = False
                    if isinstance(cat_data, dict):
                        cur_disc = str(cat_data.get("disclosure") or "")
                        if "permanently forfeits" not in cur_disc.lower():
                            cat_data["disclosure"] = disclaimer_str
                            cat_changed = True
                        tools_list = cat_data.get("tools") if isinstance(cat_data.get("tools"), list) else []
                        for t_item in tools_list:
                            if isinstance(t_item, dict):
                                for forbidden_k in ("quick_answer", "inputs", "formula", "published_output", "query_syntax"):
                                    if forbidden_k in t_item:
                                        t_item.pop(forbidden_k, None)
                                        cat_changed = True
                    if cat_changed:
                        catalog_json.write_text(_json_lib.dumps(cat_data, indent=2) + "\n", encoding="utf-8")
                        repaired_paths.append(str(catalog_json))
                except Exception:
                    pass

            llms_txt = d / "llms.txt"
            if llms_txt.is_file():
                try:
                    llms_raw = llms_txt.read_text(encoding="utf-8")
                    if "permanently forfeits" not in llms_raw:
                        if "student-loan-refinance-break-even-calculator" in llms_raw:
                            lines = []
                            for line in llms_raw.splitlines():
                                if "student-loan-refinance-break-even-calculator" in line and "permanently forfeits" not in line:
                                    lines.append(f"{line} Warning: {disclaimer_str}")
                                else:
                                    lines.append(line)
                            new_llms_raw = "\n".join(lines)
                        else:
                            new_llms_raw = llms_raw.rstrip() + f"\n\nMandatory Regulatory Disclosure: {disclaimer_str}\n"
                        if new_llms_raw != llms_raw:
                            llms_txt.write_text(new_llms_raw, encoding="utf-8")
                            repaired_paths.append(str(llms_txt))
                except Exception:
                    pass

            llms_full = d / "llms-full.txt"
            if llms_full.is_file():
                try:
                    full_raw = llms_full.read_text(encoding="utf-8")
                    changed_full = False
                    if "2022 qualifying payments" in full_raw:
                        full_raw = full_raw.replace("2022 qualifying payments", "120 monthly qualifying payments")
                        changed_full = True
                    if "2022 PSLF" in full_raw:
                        full_raw = full_raw.replace("2022 PSLF", "120 monthly PSLF")
                        changed_full = True
                    if "permanently forfeits" not in full_raw and "forfeits access to federal" not in full_raw:
                        match_ref = re.search(r"Student Loan Refinance Break[- ]Even Calculator", full_raw, re.IGNORECASE)
                        idx_sec = match_ref.start() if match_ref else -1
                        if idx_sec != -1:
                            ans_idx = full_raw.find("Direct Statutory Answer:", idx_sec)
                            if ans_idx != -1:
                                eol_idx = full_raw.find("\n", ans_idx)
                                if eol_idx != -1:
                                    full_raw = full_raw[:eol_idx] + f" Warning: {disclaimer_str}" + full_raw[eol_idx:]
                                    changed_full = True
                            else:
                                full_raw = full_raw + f"\n\nMandatory Regulatory Disclosure: {disclaimer_str}\n"
                                changed_full = True
                        else:
                            full_raw = full_raw + f"\n\nMandatory Regulatory Disclosure: {disclaimer_str}\n"
                            changed_full = True
                    if changed_full:
                        llms_full.write_text(full_raw, encoding="utf-8")
                        repaired_paths.append(str(llms_full))
                except Exception:
                    pass

        # 7. Reconcile content/overlays/*.json and .agy/overlays/*.json
        if r_root:
            for sub_dir_name in ("content/overlays", ".agy/overlays"):
                overlays_dir = r_root / sub_dir_name
                if overlays_dir.is_dir():
                    for ov_f in overlays_dir.glob("*.json"):
                        try:
                            raw_data = _json_lib.loads(ov_f.read_text(encoding="utf-8"))
                            fixed_data, was_fixed = cls.reconcile_overlay_spec_truth(raw_data, tenant=tenant_norm, slug=ov_f.stem)
                            if was_fixed:
                                ov_f.write_text(_json_lib.dumps(fixed_data, indent=2), encoding="utf-8")
                                repaired_paths.append(str(ov_f))
                        except Exception:
                            pass

        return repaired_paths

    reconcile_estate_truth = reconcile_estate_assets


__all__ = [
    "PricingTier",
    "FeatureContract",
    "TenantStatutoryTruth",
    "TenantTruthProfile",
    "DeclarativeTenantContract",
    "TenantRegistrationContract",
    "CANONICAL_TENANT_DECLARATIONS",
    "CANONICAL_TENANT_REGISTRY",
    "CANONICAL_TENANT_IDS",
    "CANONICAL_TENANT_DOMAINS",
    "CANONICAL_TENANT_HOSTS",
    "CANONICAL_TENANT_CONFIGS",
    "DEFAULT_TENANT_LINKEDIN_IDS",
    "TENANT_STATUTORY_INTENT_TOKENS",
    "TENANT_CATEGORY_SEED_TAXONOMY",
    "TENANT_VIDEO_BRANDING",
    "TENANT_FLAGSHIP_ANCHOR_SLUGS",
    "TENANT_SMOKE_PROBES",
    "TENANT_DEFAULT_CPC_USD",
    "TENANT_DEFAULT_ERPM_USD",
    "TENANT_CORE_TOOLS_BY_ID",
    "TENANT_CANNIBALIZATION_MAPS_BY_ID",
    "TENANT_FOREIGN_BOUNDARY_TOKENS",
    "CANONICAL_PRODUCTION_PROPERTIES",
    "REPO_DIR_TO_PROPERTY_ID",
    "list_canonical_tenant_ids",
    "list_canonical_tenant_domains",
    "list_canonical_repo_dir_names",
    "resolve_canonical_property_id",
    "get_tenant_contract",
    "match_tenant_statutory_intent",
    "register_declarative_tenant",
    "unregister_declarative_tenant",
    "TenantFactStore",
    "TruthReconciliationEngine",
    "PropertyContaminationError",
]

