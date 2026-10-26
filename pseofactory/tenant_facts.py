"""
pseofactory Centralized Tenant Fact & Statutory Truth Store
Stateless immutable profiles for ProfitHelm and Prexvo with strict tenant boundary isolation.
Enforces:
1. Canonical pricing tier verification ($0, $49, $199 for ProfitHelm; $0, $19 for Prexvo).
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
import re
from typing import Dict, List, Any, Optional, Set, Tuple

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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "statutory_citations": dict(self.statutory_citations),
            "limits_and_thresholds": dict(self.limits_and_thresholds),
        }


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


def _build_profithelm_profile() -> TenantTruthProfile:
    """Builds the canonical truth profile for ProfitHelm."""
    pricing = {
        "free": PricingTier(
            name="Free",
            price_usd=0.0,
            billing_period="month",
            features=["Core Calculators", "Section 179 Optimizer"],
        ),
        "pro": PricingTier(
            name="Pro",
            price_usd=49.0,
            billing_period="month",
            features=[
                "Entity Tax Modeling",
                "Section 1031 Exchange Matching",
                "Section 179 Optimizer",
                "QSBS Stacking Analysis",
                "Data Export",
            ],
        ),
        "enterprise": PricingTier(
            name="Enterprise",
            price_usd=199.0,
            billing_period="month",
            features=[
                "Entity Tax Modeling",
                "Section 1031 Exchange Matching",
                "Section 179 Optimizer",
                "QSBS Stacking Analysis",
                "Multi-Entity Consolidation",
                "Priority API",
            ],
        ),
    }

    features = {
        "Entity Tax Modeling": FeatureContract(
            name="Entity Tax Modeling",
            enabled=True,
            tier_availability=["pro", "enterprise"],
            description="Comprehensive pass-through and C-corp entity tax scenario modeling.",
        ),
        "Section 1031 Exchange Matching": FeatureContract(
            name="Section 1031 Exchange Matching",
            enabled=True,
            tier_availability=["pro", "enterprise"],
            description="Section 1031 like-kind exchange identification and timeline tracking.",
        ),
        "Section 179 Optimizer": FeatureContract(
            name="Section 179 Optimizer",
            enabled=True,
            tier_availability=["free", "pro", "enterprise"],
            description="Asset depreciation and first-year expense deduction maximization.",
        ),
        "QSBS Stacking Analysis": FeatureContract(
            name="QSBS Stacking Analysis",
            enabled=True,
            tier_availability=["pro", "enterprise"],
            description="Section 1202 Qualified Small Business Stock tax exemption analysis.",
        ),
        "Multi-Entity Consolidation": FeatureContract(
            name="Multi-Entity Consolidation",
            enabled=True,
            tier_availability=["enterprise"],
            description="Multi-entity corporate structure tax consolidation and reporting.",
        ),
    }

    statutory = TenantStatutoryTruth(
        tenant_id="profithelm",
        statutory_citations={
            "irs_rev_proc_2024_40": "IRS Rev Proc 2024-40",
            "irs_rev_proc_2023_34": "IRS Rev Proc 2023-34",
            "section_179": "IRC Section 179",
            "section_1202": "IRC Section 1202 (QSBS)",
            "circular_230": "Treasury Department Circular No. 230",
            "section_1031": "IRC Section 1031",
        },
        limits_and_thresholds={
            "section_179_expense_limit_2024": 1220000.0,
            "section_179_expense_limit_2025": 1250000.0,
            "section_179_expense_limit_2026": 2560000.0,
            "section_179_phaseout_threshold_2024": 3050000.0,
            "section_179_phaseout_threshold_2025": 3130000.0,
            "section_179_phaseout_threshold_2026": 4090000.0,
            "section_179_heavy_vehicle_2024": 30500.0,
            "section_179_heavy_vehicle_2025": 31300.0,
            "section_179_heavy_vehicle_2026": 30500.0,
            "bonus_depreciation_pct_2026": 0.20,
            "section_1202_qsbs_asset_ceiling": 50000000.0,
            "section_1202_qsbs_exclusion_cap": 10000000.0,
            "section_1202_qsbs_exclusion_multiple": 10.0,
            "section_1202_qsbs_holding_period_years": 5,
            "retirement_401k_elective_deferral_2024": 23000.0,
            "retirement_401k_elective_deferral_2025": 23500.0,
            "hsa_single_2024": 4150.0,
            "hsa_single_2025": 4300.0,
            "hsa_family_2024": 8300.0,
            "hsa_family_2025": 8550.0,
            "standard_deduction_2026_single": 15000.0,
            "standard_deduction_2026_mfj": 30000.0,
            "standard_deduction_2026_hoh": 22500.0,
            "standard_deduction_2027_sunset_single": 8600.0,
            "standard_deduction_2027_sunset_mfj": 17200.0,
            "standard_deduction_2027_sunset_hoh": 12900.0,
            "tcja_vs_sunset_single_125k_tcja_tax": 19181.0,
            "tcja_vs_sunset_single_125k_sunset_tax": 23530.0,
            "tcja_vs_sunset_single_125k_delta": 4349.0,
            "saas_runway_baseline_monthly_revenue": 33000.0,
            "saas_runway_baseline_monthly_burn": 45000.0,
            "saas_runway_baseline_net_monthly_burn": 12000.0,
            "scorp_155k_95k_salary_fica_savings": 13180.0,
            "section_301_tariff_120k_fob_landed_cost": 160966.0,
            "section_179_heavy_suv_85k_80pct_first_year_deduction": 38000.0,
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
    """Builds the canonical truth profile for Prexvo."""
    pricing = {
        "free": PricingTier(
            name="Free",
            price_usd=0.0,
            billing_period="month",
            features=["RAP vs IBR Modeling", "Tiered Standard Calculation", "ICR Repayment Modeling"],
        ),
        "pro": PricingTier(
            name="Pro",
            price_usd=19.0,
            billing_period="month",
            features=[
                "RAP vs IBR Modeling",
                "Tiered Standard Calculation",
                "PAYE Sunset Analysis",
                "ICR Repayment Modeling",
                "PSLF Buyback Estimator",
                "Scenario Export",
            ],
        ),
        "enterprise": PricingTier(
            name="Enterprise",
            price_usd=0.0,
            billing_period="custom",
            features=[
                "RAP vs IBR Modeling",
                "Tiered Standard Calculation",
                "PAYE Sunset Analysis",
                "ICR Repayment Modeling",
                "PSLF Buyback Estimator",
                "Institutional Analytics",
            ],
        ),
    }

    features = {
        "RAP vs IBR Modeling": FeatureContract(
            name="RAP vs IBR Modeling",
            enabled=True,
            tier_availability=["free", "pro", "enterprise"],
            description="Repayment Assistance Plan vs Income-Based Repayment schedule comparison.",
        ),
        "Tiered Standard Calculation": FeatureContract(
            name="Tiered Standard Calculation",
            enabled=True,
            tier_availability=["free", "pro", "enterprise"],
            description="Tiered fixed repayment schedule calculation for direct loans.",
        ),
        "PAYE Sunset Analysis": FeatureContract(
            name="PAYE Sunset Analysis",
            enabled=True,
            tier_availability=["pro", "enterprise"],
            description="Analysis of Pay As You Earn plan phasing out pursuant to 34 CFR 685.209.",
        ),
        "ICR Repayment Modeling": FeatureContract(
            name="ICR Repayment Modeling",
            enabled=True,
            tier_availability=["free", "pro", "enterprise"],
            description="Income-Contingent Repayment plan calculation and discretionary income modeling.",
        ),
        "PSLF Buyback Estimator": FeatureContract(
            name="PSLF Buyback Estimator",
            enabled=True,
            tier_availability=["pro", "enterprise"],
            description="Public Service Loan Forgiveness buyback payment estimation under 34 CFR 685.219.",
        ),
    }

    statutory = TenantStatutoryTruth(
        tenant_id="prexvo",
        statutory_citations={
            "title_iv": "Title IV Higher Education Act",
            "34_cfr_685": "34 CFR Part 685",
            "paye_regulations": "34 CFR 685.209",
            "pslf_regulations": "34 CFR 685.219",
        },
        limits_and_thresholds={
            "rap_discretionary_percentage": 0.10,
            "rap_poverty_guideline_threshold": 2.25,
            "ibr_pre_2014_percentage": 0.15,
            "ibr_post_2014_percentage": 0.10,
            "ibr_poverty_guideline_threshold": 1.50,
            "pslf_qualifying_payments": 120,
            "poverty_guidelines": {
                2024: {"individual": 15060.0, "additional_person": 5380.0},
                2025: {"individual": 15650.0, "additional_person": 5440.0},
                2026: {"individual": 16200.0, "additional_person": 5500.0},
            },
            "poverty_guidelines_2026_hhs_contiguous": 15650.0,
            "poverty_guidelines_2026_hhs_per_additional": 5500.0,
            "rap_exemption_2026_single_contiguous": 35212.50,
            "ibr_exemption_2026_single_contiguous": 23475.00,
            "icr_exemption_2026_single_contiguous": 15650.00,
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
        "stripe",
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
    """Builds the canonical truth profile for GainHelm (Enterprise Cyber Compliance & GRC Governance)."""
    pricing = {
        "free": PricingTier(
            name="Free",
            price_usd=0.0,
            billing_period="month",
            features=[
                "SOC 2 Audit Cost & CPA Scoping",
                "DoD CMMC 2.0 & NIST 800-171 SPRS Scoring",
                "HHS OCR HIPAA Penalty Tier Modeling",
            ],
        ),
        "pro": PricingTier(
            name="Pro",
            price_usd=49.0,
            billing_period="month",
            features=[
                "SOC 2 Audit Cost & CPA Scoping",
                "DoD CMMC 2.0 & NIST 800-171 SPRS Scoring",
                "ISO 27001 Auditor-Day Calculation",
                "HHS OCR HIPAA Penalty Tier Modeling",
                "PCI DSS 4.0 QSA & ROC Scoping",
                "Audit Workpaper Export",
            ],
        ),
        "enterprise": PricingTier(
            name="Enterprise",
            price_usd=199.0,
            billing_period="month",
            features=[
                "SOC 2 Audit Cost & CPA Scoping",
                "DoD CMMC 2.0 & NIST 800-171 SPRS Scoring",
                "ISO 27001 Auditor-Day Calculation",
                "HHS OCR HIPAA Penalty Tier Modeling",
                "PCI DSS 4.0 QSA & ROC Scoping",
                "Multi-Framework Governance Consolidation",
                "Priority GRC API",
            ],
        ),
    }

    features = {
        "SOC 2 Audit Cost & CPA Scoping": FeatureContract(
            name="SOC 2 Audit Cost & CPA Scoping",
            enabled=True,
            tier_availability=["free", "pro", "enterprise"],
            description="AICPA SSAE 18 (AT-C Section 205) Trust Services Criteria Type I and Type II CPA audit cost and readiness modeling.",
        ),
        "DoD CMMC 2.0 & NIST 800-171 SPRS Scoring": FeatureContract(
            name="DoD CMMC 2.0 & NIST 800-171 SPRS Scoring",
            enabled=True,
            tier_availability=["free", "pro", "enterprise"],
            description="32 CFR Part 170 and DFARS 252.204-7012 / 7019 / 7020 NIST SP 800-171 Rev 2 110-control SPRS score and C3PAO budget modeling.",
        ),
        "ISO 27001 Auditor-Day Calculation": FeatureContract(
            name="ISO 27001 Auditor-Day Calculation",
            enabled=True,
            tier_availability=["pro", "enterprise"],
            description="ISO/IEC 27006-1:2024 mandatory Stage 1, Stage 2, and 3-year surveillance auditor-day calculation for ISO/IEC 27001:2022 ISMS.",
        ),
        "HHS OCR HIPAA Penalty Tier Modeling": FeatureContract(
            name="HHS OCR HIPAA Penalty Tier Modeling",
            enabled=True,
            tier_availability=["free", "pro", "enterprise"],
            description="45 CFR 160.404 and 42 U.S.C. 1320d-5 inflation-adjusted 4-Tier civil money penalty exposure and HITECH breach notification cost modeling.",
        ),
        "PCI DSS 4.0 QSA & ROC Scoping": FeatureContract(
            name="PCI DSS 4.0 QSA & ROC Scoping",
            enabled=True,
            tier_availability=["pro", "enterprise"],
            description="PCI SSC PCI DSS v4.0.1 Merchant Level 1-4 SAQ vs QSA Report on Compliance (ROC) and ASV scan cost modeling.",
        ),
    }

    statutory = TenantStatutoryTruth(
        tenant_id="gainhelm",
        statutory_citations={
            "aicpa_ssae_18_atc_205": "AICPA SSAE 18 (AT-C Section 205) & TSP Section 100",
            "dod_32_cfr_part_170": "32 CFR Part 170 (DoD CMMC 2.0 Final Rule)",
            "dfars_252_204_7012": "DFARS 252.204-7012 / 252.204-7019 / 252.204-7020",
            "nist_sp_800_171_rev2": "NIST SP 800-171 Rev 2 (110 Security Requirements)",
            "iso_iec_27006_1_2024": "ISO/IEC 27006-1:2024 & ISO/IEC 27001:2022",
            "hipaa_45_cfr_160_404": "45 CFR 160.404 & 42 U.S.C. 1320d-5 (HITECH Act)",
            "pci_dss_v4_0_1": "PCI DSS v4.0.1 Merchant & Service Provider Scoping",
            "fedramp_44_usc_3607": "44 U.S.C. 3607 (FedRAMP Authorization Act) & NIST SP 800-53 Rev 5",
            "gdpr_art_83_eu_ai_act_art_99": "GDPR Article 83 (EU 2016/679) & EU AI Act Article 99 (EU 2024/1689)",
        },
        limits_and_thresholds={
            "sprs_max_score": 110,
            "sprs_min_score": -203,
            "sprs_total_controls": 110,
            "cmmc_conditional_min_sprs": 88,
            "cmmc_poam_closeout_days": 180,
            "hipaa_tier1_min_per_violation": 141.0,
            "hipaa_tier4_min_per_violation": 71162.0,
            "hipaa_statutory_annual_cap_tier4": 2134831.0,
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
            "soc2_baseline_type2_75emp_total_cost": 48500.0,
            "cmmc_level2_baseline_85emp_total_cost": 94200.0,
            "iso27001_baseline_120emp_3yr_tco": 68400.0,
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
    "arifcoskun.com": {
        "domain": "arifcoskun.com",
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
        "expected_cname_target": "arif-coskun-platform.pages.dev",
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
    """Computes deterministic SHA-256 digest of the canonical 8-domain Registrar ledger."""
    target = ledger if ledger is not None else CLOUDFLARE_PORTFOLIO_REGISTRAR_LEDGER
    canonical = json.dumps(target, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


CLOUDFLARE_REGISTRAR_ATTESTATION_SHA256: str = compute_registrar_ledger_sha256()


class TenantFactStore:
    """
    Centralized singleton store for tenant truth profiles.
    Enforces truth assertions, claim verification, and tenant isolation boundaries.
    Zero em-dashes. Zero en-dashes.
    """

    _instance: Optional["TenantFactStore"] = None

    def __init__(self):
        self._profiles: Dict[str, TenantTruthProfile] = {
            "profithelm": _build_profithelm_profile(),
            "prexvo": _build_prexvo_profile(),
            "gainhelm": _build_gainhelm_profile(),
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
        if norm in ("profithelm.com", "prexvo.com", "gainhelm.com"):
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
        and expiration/sunset horizon bounds across all 8 Cloudflare portfolio domains.
        Zero em-dashes. Zero en-dashes.
        """
        target = ledger if ledger is not None else CLOUDFLARE_PORTFOLIO_REGISTRAR_LEDGER
        now_dt = reference_utc or datetime.now(timezone.utc)
        violations: List[str] = []

        if len(target) != 8:
            violations.append(f"Expected 8 portfolio domains in ledger, found {len(target)}")

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

    def get_profile(self, tenant: str) -> Optional[TenantTruthProfile]:
        """Retrieves tenant profile by identifier (case-insensitive)."""
        if not tenant:
            return None
        return self._profiles.get(str(tenant).lower().strip())

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

    def verify_claim(
        self,
        tenant: str,
        text: str,
        context: Optional[str] = None,
        spec_disclosures: Optional[List[str]] = None,
    ) -> Tuple[bool, List[str]]:
        """
        Inspects text against tenant truth profile:
        1. Banned marketing claims
        2. Unverified pricing numbers ($XX/mo)
        3. Cross-tenant boundary contamination
        4. Mandatory regulatory disclosures
        5. Statutory threshold limit boundaries & ground-truth benchmark figures
        Returns (is_valid, violations_list).
        Zero em-dashes. Zero en-dashes.
        """
        assert_no_forbidden_dashes(text, context=context or f"verify_claim({tenant})")
        profile = self.get_profile(tenant)
        if not profile:
            return False, [f"Unknown tenant '{tenant}'"]

        violations: List[str] = []
        text_lower = text.lower()
        tenant_norm = str(tenant).lower().strip()

        # 1. Banned claims check
        for banned in profile.claims_banned:
            if banned.lower() in text_lower:
                violations.append(
                    f"Banned claim detected for {profile.brand_name}: '{banned}'"
                )

        # 2. Pricing verification
        if "$" in text and ("/mo" in text_lower or "per mo" in text_lower):
            pricing_matches = re.findall(
                r'\$(\d+(?:\.\d{2})?)\s*(?:/|\s*per\s*)(?:mo|month)',
                text,
                re.IGNORECASE,
            )
            valid_prices = {tier.price_usd for tier in profile.pricing_tiers.values()}
            allowed_statutory_monthly = {
                float(v)
                for k, v in profile.statutory_truth.limits_and_thresholds.items()
                if isinstance(v, (int, float)) and ("monthly" in k or "subsidy" in k)
            }
            for price_str in pricing_matches:
                price_val = float(price_str)
                if price_val not in valid_prices and price_val not in allowed_statutory_monthly:
                    violations.append(
                        f"Unverified price claim '${price_val}' contradicts {profile.brand_name} pricing tiers {valid_prices}"
                    )

        # 3. Cross-tenant boundary isolation
        for token in profile.cross_tenant_forbidden_tokens:
            tok_l = token.lower()
            if re.search(rf"(?<![a-z0-9]){re.escape(tok_l)}(?![a-z0-9])", text_lower):
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
            if "refinance" in text_lower or "refinancing" in text_lower:
                has_ymyl = (
                    "waives federal protections" in text_lower
                    or "eliminates federal protections" in text_lower
                    or "waive federal protections" in text_lower
                )
                if not has_ymyl:
                    violations.append(
                        "Missing mandatory YMYL forfeiture disclaimer: 'Refinancing federal student loans permanently waives federal protections'"
                    )

        if spec_disclosures:
            for disclosure_phrase in spec_disclosures:
                if disclosure_phrase and disclosure_phrase.lower() not in text_lower:
                    violations.append(
                        f"Missing mandatory disclosure containing '{disclosure_phrase}'"
                    )

        # 5. Statutory threshold limit boundaries & ground-truth benchmark figures
        if tenant_norm == "profithelm":
            prose_scan_text = (
                re.sub(r"<style\b[^>]*>[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
                if "<style" in text_lower
                else text
            )
            # Section 179 SUV / heavy vehicle cap ($30,500 for 2024/2026 / $31,300 for 2025)
            if "suv" in text_lower or "heavy vehicle" in text_lower:
                suv_clause_matches = re.finditer(
                    r'(?:(?:suv|heavy\s*vehicle)[^\.\n]{0,140}?(?:deduct(?:ion)?|allowance|expens(?:e|ing)|cap|limit|maximum)\s+(?:of\s+)?(?:up to\s+)?\$([0-9,]+)|(?:deduct(?:ion)?|allowance|expens(?:e|ing)|cap|limit|maximum)\s+(?:of\s+)?(?:up to\s+)?\$([0-9,]+)[^\.\n]{0,140}?(?:suv|heavy\s*vehicle))',
                    prose_scan_text,
                    re.IGNORECASE,
                )
                for m_obj in suv_clause_matches:
                    raw_val = m_obj.group(1) or m_obj.group(2)
                    clause_low = m_obj.group(0).lower()
                    # Check a tight window around the match for explicit 2025 qualification
                    win_start = max(0, m_obj.start() - 60)
                    win_end = min(len(prose_scan_text), m_obj.end() + 80)
                    window_low = prose_scan_text[win_start:win_end].lower()
                    try:
                        val = float(raw_val.replace(",", ""))
                        has_2025_qual = "2025" in window_low and "in 2026" not in clause_low
                        suv_cap = 31300.0 if has_2025_qual else 30500.0
                        if val > suv_cap:
                            violations.append(
                                f"Section 179 heavy vehicle/SUV limit contradiction: claimed ${val:,.0f} exceeds statutory cap of $30,500 for 2024/2026 ($31,300 for 2025)"
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
            )
            for st_suv in stale_suv_tokens:
                if st_suv in text_lower:
                    violations.append(
                        f"Stale 2026 Heavy SUV Section 179 cap '{st_suv}' detected: 2026 statutory SUV cap is $30,500 ($31,300 for 2025 inflation-adjusted schedules)"
                    )

            # Section 179 overall expense limit ($1,220,000 for 2024 / $1,250,000 for 2025 / $2,560,000 for 2026 OBBBA)
            if "section 179" in text_lower or "section179" in text_lower:
                s179_matches = re.findall(
                    r'(?:section\s*179[^\.\n]{0,140}?(?:deduct(?:ion)?|expense(?:\s+limit)?|cap|maximum)\s+(?:up to\s+)?\$([0-9,]+)|(?:deduct(?:ion)?|expense(?:\s+limit)?|cap|maximum)\s+(?:up to\s+)?\$([0-9,]+)[^\.\n]{0,140}?section\s*179)',
                    prose_scan_text,
                    re.IGNORECASE,
                )
                for m in s179_matches:
                    raw_val = m[0] or m[1]
                    try:
                        val = float(raw_val.replace(",", ""))
                        if "2026" in text_lower or "obbba" in text_lower:
                            s179_cap = 2560000.0
                        elif "2025" in text_lower:
                            s179_cap = 1250000.0
                        else:
                            s179_cap = 1220000.0
                        if val > s179_cap:
                            violations.append(
                                f"Section 179 expense limit contradiction: claimed ${val:,.0f} exceeds statutory limit of $1,220,000 for 2024 ($1,250,000 for 2025, $2,560,000 for 2026)"
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
            if re.search(r"in\s+2026[^\.\n]{0,140}?up\s+to\s+\$1,250,000\s+in\s+qualifying", text, re.IGNORECASE):
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

            # Stale 80% bonus depreciation in runtime sync script or 2026 prose
            if "rembasis * 0.80" in text_lower or "rem179 * 0.80" in text_lower:
                violations.append(
                    "Stale 80% bonus depreciation multiplier ('* 0.80') detected in workbench calculation logic: 2026 statutory IRC 168(k) bonus depreciation rate is 20% ('* 0.20')"
                )
            if re.search(
                r"(?:(?:60|80)%\s+(?:first-year\s+)?bonus\s+depreciation[^\.\n]{0,80}?2026|bonus\s+depreciation\s+(?:is|rate\s+is)\s+(?:60|80)%[^\.\n]{0,80}?2026|in\s+2026[^\.\n]{0,80}?(?:60|80)%\s+(?:first-year\s+)?bonus\s+depreciation)",
                text_lower,
            ):
                violations.append(
                    "Stale 2026 bonus depreciation rate (60%/80%) detected: 2026 statutory IRC 168(k) bonus depreciation rate is 20%"
                )

            # Unverified $29 offer fallback in JS
            if "offer_price_usd || 29" in text:
                violations.append(
                    "Unverified offer_price_usd fallback '29' detected in runtime script: contradicts ProfitHelm ($49) and Prexvo ($19) canonical pricing tiers"
                )

            # Corrupted subtraction syntax from aggressive hyphen replacement
            if "(1: 13.3% state rate)" in text or "(100%: 15% exclusion)" in text:
                violations.append(
                    "Corrupted mathematical subtraction syntax detected ('(1: 13.3% state rate)' or '(100%: 15% exclusion)'); must preserve minus sign in mathematical formulas"
                )

            # Un-capped OASDI S-Corp FICA savings ($19,125 instead of $13,180 at $155k net / $95k salary)
            if ("$19,125" in text or '"published_output": 19125' in text or "produces 19,125.00" in text_lower) and (
                "s-corp" in text_lower or "reasonable salary" in text_lower or "reasonable-salary" in text_lower
            ):
                violations.append(
                    "Stale S-Corp FICA tax savings figure '$19,125' detected: ignores the 2026 $176,100 Social Security OASDI wage base cap under IRC Section 3121 (verified savings at $155k net / $95k salary is $13,180)"
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
                    r'(?:(?:pslf|public\s+service\s+loan\s+forgiveness)[^\.\n]{0,140}?(\d+)\s*(?:qualifying\s*)?(?:monthly\s*)?payments?|(\d+)\s*(?:qualifying\s*)?(?:monthly\s*)?payments?[^\.\n]{0,140}?(?:pslf|public\s+service\s+loan\s+forgiveness))',
                    text,
                    re.IGNORECASE,
                )
                for m_obj in pslf_matches:
                    p_str = m_obj.group(1) or m_obj.group(2)
                    span_low = m_obj.group(0).lower()
                    try:
                        payments = int(p_str)
                        if payments != 120:
                            # Allow sentences that explicitly pair 120-payment PSLF with 240/300-payment IDR forgiveness
                            has_explicit_120_pslf = bool(
                                re.search(
                                    r"(?:120[-\s]+(?:qualifying\s+|monthly\s+|certified\s+)?(?:payment|month)[^\.\n]{0,60}?(?:pslf|public\s+service)|(?:pslf|public\s+service)[^\.\n]{0,60}?120[-\s]+(?:qualifying\s+|monthly\s+|certified\s+)?(?:payment|month)|pslf\s*\(120)",
                                    span_low,
                                )
                            )
                            if not (payments in (240, 300) and has_explicit_120_pslf):
                                violations.append(
                                    f"PSLF payment requirement contradiction: claimed {payments} payments contradicts statutory requirement of 120 qualifying monthly payments under 34 CFR 685.219"
                                )
                    except ValueError:
                        pass

            # Stale RAP Scenario A ($244.58 / $58,700) and Scenario B ($494.58 / $118,700) detection
            if "$244.58" in text or "$58,700" in text:
                violations.append(
                    "Stale RAP Scenario A calculation detected ($244.58 or $58,700): ground-truth 2026 HHS poverty guideline ($15,650) yields $248.23/mo and $59,575.20 over 240 months"
                )
            if "$494.58" in text or "$118,700" in text:
                violations.append(
                    "Stale RAP Scenario B calculation detected ($494.58 or $118,700): ground-truth 2026 HHS poverty guideline ($15,650) yields $498.23/mo"
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

            # Unverified $29 offer fallback in JS
            if "offer_price_usd || 29" in text:
                violations.append(
                    "Unverified offer_price_usd fallback '29' detected in runtime script: contradicts Prexvo ($19) canonical pricing tier"
                )

            # Plan-specific contradiction: attributing 225% ($35,212.50) to IBR, PAYE, ICR, Tiered Standard, Grad PLUS, Refinance, or institutional pages
            if re.search(
                r"(?:ibr\s+hardship(?:\s+cap)?(?:\s+calculator)?|paye\s+sunset(?:\s+eligibility)?(?:\s+calculator)?|icr\s+repayment(?:\s+calculator)?|income[-\s]contingent\s+repayment|tiered\s+standard(?:\s+repayment)?(?:\s+calculator)?|grad\s+plus(?:\s+borrowing)?(?:\s+cap)?(?:\s+calculator)?|student\s+loan\s+refinance(?:\s+break[-\s]even)?(?:\s+calculator)?|parent\s+plus\s+repayment)\s+(?:determines\s+monthly\s+obligations\s+using\s+the\s+225\s+percent|subtracts\s+225\s+percent|under\s+title\s+iv\s+34\s+cfr\s+part\s+685\s+using\s+225%)",
                text_lower,
            ):
                violations.append(
                    "Prexvo plan-threshold contradiction: non-RAP plan (IBR, PAYE, ICR, Tiered Standard, Grad PLUS, Parent PLUS, or Refinance) misattributed to RAP 225% HHS Poverty Guideline ($35,212.50)"
                )
            if re.search(
                r"calculate\s+(?:tools\s+directory|disclaimers|methodology|privacy|about)\s+under\s+title\s+iv",
                text_lower,
            ):
                violations.append(
                    "Prexvo non-tool institutional page contains calculator template meta/prose ('Calculate ... under Title IV')"
                )

        is_valid = len(violations) == 0
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
        ("IRC 179 ($1.29M Cap) / 168(k) 20% Bonus", "IRC 179 ($2.56M Cap) / 168(k) 20% Bonus"),
        ("Full Cap ($1.29M)", "Full Cap ($2.56M)"),
        # Stale 2026 Heavy SUV cap ($31,300 -> $30,500) and 2024 60% bonus depreciation in 2026 SUV calculators/tables
        (
            "capped at a $31,300 Section 179 deduction in 2026",
            "capped at a $30,500 statutory Section 179 deduction ($31,300 for 2025 inflation-adjusted schedules)",
        ),
        (
            "$31,300 statutory Section 179 cap ($30,500 prior-year inflation baseline)",
            "$30,500 statutory Section 179 cap ($31,300 for 2025 inflation-adjusted schedule)",
        ),
        ("Heavy SUV 6,000 to 14,000 lbs ($110k / $31,300 SUV Cap)", "Heavy SUV 6,000 to 14,000 lbs ($110k / $30,500 SUV Cap)"),
        ("Heavy SUV 6,000 to 14,000 lbs GVWR ($31,300 IRC 179(b)(5) Cap + Bonus)", "Heavy SUV 6,000 to 14,000 lbs GVWR ($30,500 IRC 179(b)(5) Cap + Bonus)"),
        ("Heavy SUVs (6,000-14,000 lbs, $31,300 Cap + Bonus)", "Heavy SUVs (6,000-14,000 lbs, $30,500 Cap + Bonus)"),
        ("Heavy SUV Tax Savings ($31,300 Cap + Bonus)", "Heavy SUV Tax Savings ($30,500 Cap + Bonus)"),
        ("<td>$31,300 + Bonus Depr.</td>", "<td>$30,500 + Bonus Depr.</td>"),
        ("<td>$31,300 (IRC §179(b)(5))</td>", "<td>$30,500 (IRC §179(b)(5))</td>"),
        ("IRC §179(b)(5) $31,300 cap", "IRC §179(b)(5) $30,500 cap"),
        ("IRC \\u00a7179(b)(5) $31,300 cap", "IRC \\u00a7179(b)(5) $30,500 cap"),
        ("60% on balance (2024-2026 phase-down)", "20% on balance (2026 statutory rate)"),
        ("<td>60% on balance</td>", "<td>20% on balance</td>"),
        ("<td>$53,320 on $85,000 basis</td>", "<td>$38,000 on $85,000 basis</td>"),
        ("and 60% bonus depreciation under Section 168(k)", "and 20% bonus depreciation under Section 168(k)"),
        (
            "qualifies for an immediate first-year Section 179 expense allowance of up to $31,300 plus 60% bonus depreciation on the remaining basis. At 80% business use ($68,000 basis), your total first-year deduction reaches $53,320, reducing net income tax liability by $19,728 at the 37% marginal rate.",
            "qualifies for an immediate first-year Section 179 expense allowance of up to $30,500 plus 20% bonus depreciation on the remaining basis. At 80% business use ($68,000 basis), your total first-year deduction reaches $38,000, reducing net income tax liability by $14,060 at the 37% marginal rate.",
        ),
        (
            "qualifies for the IRC Section 280F heavy SUV allowance of up to $31,300 plus 60% bonus depreciation on the remaining basis. At 80% business use ($68,000 basis), your total first-year deduction reaches $53,320, reducing net income tax liability by $19,728 at a 37% marginal tax bracket.",
            "qualifies for the IRC Section 280F heavy SUV allowance of up to $30,500 plus 20% bonus depreciation on the remaining basis. At 80% business use ($68,000 basis), your total first-year deduction reaches $38,000, reducing net income tax liability by $14,060 at a 37% marginal tax bracket.",
        ),
        (
            'id="val-first_year_deduction">$53,320<',
            'id="val-first_year_deduction">$38,000<',
        ),
        (
            'id="val-tax_savings">$19,728<',
            'id="val-tax_savings">$14,060<',
        ),
        (
            'id="val-effective_cost">$65,272<',
            'id="val-effective_cost">$70,940<',
        ),
        (
            'id="val-heavy_suv_capped_savings">$21,895<',
            'id="val-heavy_suv_capped_savings">$14,525<',
        ),
        (
            "<td>$62,556</td><td>$21,895</td>",
            "<td>$41,500</td><td>$14,525</td>",
        ),
        # Inline calculator JS parity
        ("var suv179 = Math.min(cost, 31300);", "var suv179 = Math.min(cost, 30500);"),
        (
            "const suvCap = 31300 * busUse;\n      const suvBonus = Math.max(0, basis - suvCap) * 0.60;",
            "const suvCap = 30500 * busUse;\n      const suvBonus = Math.max(0, basis - suvCap) * 0.20;",
        ),
        (
            "Math.min(basis, 31300) + Math.max(0, basis - 31300) * 0.60",
            "Math.min(basis, 30500) + Math.max(0, basis - 30500) * 0.20",
        ),
        # 2027 Sunset Head of Household standard deduction ($12,700 -> $12,900) & runtime bonus depreciation (80% -> 20%)
        ("head_of_household: 12700", "head_of_household: 12900"),
        ("hoh: 12700", "hoh: 12900"),
        ("(status === 'head_of_household' ? 12700 : 8600)", "(status === 'head_of_household' ? 12900 : 8600)"),
        ("remBasis * 0.80", "remBasis * 0.20"),
        ("rem179 * 0.80", "rem179 * 0.20"),
        (
            "data.offer_price_usd || 29",
            'data.offer_price_usd || ((window.location && window.location.hostname && String(window.location.hostname).slice(0, 3) === "pre") ? 19 : 49)',
        ),
        (
            "data.offer_price_usd || (isPrexvo ? 19 : 49)",
            'data.offer_price_usd || ((window.location && window.location.hostname && String(window.location.hostname).slice(0, 3) === "pre") ? 19 : 49)',
        ),
        ('"price":"29"', '"price":"49"'),
        ('"price": "29"', '"price": "49"'),
        ("$19,125 in self-employment tax ($15,500 OASDI + $3,625 Medicare)", "$13,180 in self-employment tax ($10,056 OASDI + $3,124 Medicare)"),
        # Corrupted mathematical subtraction syntax
        ("(1: 13.3% state rate)", "(1 - 13.3% state rate)"),
        ("(100%: 15% exclusion)", "(100% - 15% exclusion)"),
        # S-Corp reasonable salary OASDI wage base cap reconciliation ($19,125 -> $13,180)
        (
            '"formula": "round((net_business_income - reasonable_w2_salary) * 0.153, 0)",\n  "inputs": {\n    "net_business_income": 225000.0,\n    "reasonable_w2_salary": 100000.0\n  },\n  "published_output": 19125.0,',
            '"formula": "round((oasdi_taxable_delta * 0.124) + (medicare_taxable_delta * 0.029), 0)",\n  "inputs": {\n    "oasdi_taxable_delta": 81100.0,\n    "medicare_taxable_delta": 107425.0\n  },\n  "published_output": 13180.0,',
        ),
        (
            "Deterministic evaluation of round((net_business_income: reasonable_w2_salary) * 0.153, 0) produces 19,125.00.",
            "Deterministic evaluation of round((oasdi_taxable_delta * 0.124) + (medicare_taxable_delta * 0.029), 0) produces 13,180.00.",
        ),
        (
            "Deterministic evaluation of round((net_business_income - reasonable_w2_salary) * 0.153, 0) produces 19,125.00.",
            "Deterministic evaluation of round((oasdi_taxable_delta * 0.124) + (medicare_taxable_delta * 0.029), 0) produces 13,180.00.",
        ),
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
            "Under IRC Section 162(a)(3) and GAAP ASC 842, operating equipment lease payments are 100% deductible as ordinary business expenses in the period incurred without upfront capital expenditure, whereas financed equipment purchases utilize IRC Section 179 ($30,500 Heavy SUV cap) and 20% Section 168(k) bonus depreciation ($38,000 first-year write-off on $85,000 at 80% business use).",
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
            "data.offer_price_usd || 29",
            'data.offer_price_usd || ((window.location && window.location.hostname && String(window.location.hostname).slice(0, 3) === "pre") ? 19 : 49)',
        ),
        (
            "data.offer_price_usd || (isPrexvo ? 19 : 49)",
            'data.offer_price_usd || ((window.location && window.location.hostname && String(window.location.hostname).slice(0, 3) === "pre") ? 19 : 49)',
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
    )

    @classmethod
    def reconcile_html_truth(
        cls,
        html_content: str,
        tenant: str,
        rel_path: str = "",
        slug: str = "",
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
        raw_t = (tenant or "").lower()
        tenant_norm = "prexvo" if "prexvo" in raw_t else ("gainhelm" if "gainhelm" in raw_t else "profithelm")
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

        # 3. Ensure signal/index.html has a valid WebPage JSON-LD schema block if missing
        if (
            ("signal/index.html" in rel_path.lower() or slug.lower() == "signal")
            and 'type="application/ld+json"' not in updated
            and "</head>" in updated
        ):
            canon_m = re.search(
                r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']',
                updated,
                re.IGNORECASE,
            )
            sig_url = canon_m.group(1) if canon_m else "https://profithelm.com/signal/"
            t_m = re.search(r"<title[^>]*>([\s\S]*?)</title>", updated, re.IGNORECASE)
            sig_title = _html_lib.unescape(re.sub(r"<[^>]+>", "", t_m.group(1)).strip()) if t_m else "ProfitHelm Statutory Signal"
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
            for dm in re.finditer(r"<details\b[^>]*>([\s\S]*?)</details>", updated, re.IGNORECASE):
                d_inner = dm.group(1)
                sm = re.search(r"<summary\b[^>]*>([\s\S]*?)</summary>", d_inner, re.IGNORECASE)
                if not sm:
                    continue
                q_txt = _html_lib.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", sm.group(1)))).strip()
                after_s = d_inner[sm.end():]
                a_txt = _html_lib.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", after_s))).strip()
                if q_txt and a_txt:
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
        raw_t = (tenant or "").lower()
        tenant_norm = "prexvo" if "prexvo" in raw_t else ("gainhelm" if "gainhelm" in raw_t else "profithelm")
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
                    "capped at a $30,500 statutory Section 179 deduction ($31,300 for 2025 inflation-adjusted schedules)",
                ),
                (
                    "In 2026, Equipment Lease Tax Deduction under IRC Section 179 and Section 168(k) allows businesses to expense up to $2,560,000 in qualifying commercial equipment placed in service, phasing out dollar-for-dollar above $4,090,000 in total asset purchases. Remaining basis qualifies for 20% first-year bonus depreciation and MACRS recovery on IRS Form 4562.",
                    "Under IRC Section 162(a)(3) and GAAP ASC 842, operating equipment lease payments are 100% deductible as ordinary business expenses in the period incurred without upfront capital expenditure, whereas financed equipment purchases utilize IRC Section 179 ($30,500 Heavy SUV cap) and 20% Section 168(k) bonus depreciation ($38,000 first-year write-off on $85,000 at 80% business use).",
                ),
            ):
                if old_s in updated_str:
                    updated_str = updated_str.replace(old_s, new_s)
        elif tenant_norm == "prexvo":
            for old_s, new_s in cls.PREXVO_ALL_HTML_REPLACEMENTS:
                if old_s in updated_str:
                    updated_str = updated_str.replace(old_s, new_s)
            if any(k in ov_slug for k in ("ibr-hardship", "paye-sunset")) and "rap-vs" not in ov_slug:
                for old_s, new_s in cls.PREXVO_IBR_PAYE_HTML_REPLACEMENTS:
                    if old_s in updated_str:
                        updated_str = updated_str.replace(old_s, new_s)

        if updated_str != serialized:
            return _json_lib.loads(updated_str), True
        return raw_ov, False

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
        violations: List[str] = []
        if include_fact_store:
            store = TenantFactStore.get_instance()
            ok, store_violations = store.verify_claim(tenant=tenant, text=html_content, context=rel_path or slug)
            if not ok:
                violations.extend(store_violations)

        for filler_old, _ in cls.SPECULATIVE_FILLER_REPLACEMENTS:
            if filler_old in html_content:
                violations.append(f"Speculative filler phrase detected: '{filler_old.strip()}'")

        raw_t = (tenant or "").lower()
        tenant_norm = "prexvo" if "prexvo" in raw_t else ("gainhelm" if "gainhelm" in raw_t else "profithelm")
        if tenant_norm == "profithelm":
            for old_str, _ in cls.PROFITHELM_HTML_REPLACEMENTS:
                if old_str in html_content:
                    msg = f"Unreconciled ProfitHelm statutory figure or JS cap: '{old_str[:60]}'"
                    if msg not in violations:
                        violations.append(msg)
            if "Math.min(cost, 31300)" in html_content or "Math.min(basis, 31300)" in html_content or "const suvCap = 31300" in html_content:
                violations.append("Inline calculator JS uses stale 31300 Heavy SUV cap instead of 2026 statutory 30500 cap")
            if "<td>60% on balance</td>" in html_content or "60% on balance (2024-2026 phase-down)" in html_content:
                violations.append("Stale 60% bonus depreciation rate in 2026 Section 179 comparison table (2026 statutory rate is 20%)")
        elif tenant_norm == "prexvo":
            for old_str, _ in cls.PREXVO_ALL_HTML_REPLACEMENTS:
                if old_str in html_content:
                    msg = f"Unreconciled Prexvo statutory figure or plan claim: '{old_str[:60]}'"
                    if msg not in violations:
                        violations.append(msg)
            combined_slug = f"{rel_path.lower()} {slug.lower()}"
            is_ibr_or_paye = (
                any(k in combined_slug for k in ("ibr-hardship", "paye-sunset"))
                or "IBR Hardship Cap Calculator" in html_content
                or "PAYE Sunset Eligibility" in html_content
            ) and "rap-vs-ibr" not in combined_slug
            if is_ibr_or_paye:
                for old_str, _ in cls.PREXVO_IBR_PAYE_HTML_REPLACEMENTS:
                    if old_str in html_content:
                        msg = f"Unreconciled Prexvo IBR/PAYE threshold figure: '{old_str[:60]}'"
                        if msg not in violations:
                            violations.append(msg)
                if "ibr-hardship" in combined_slug and '"name": "RAP vs IBR Repayment Calculator"' in html_content:
                    violations.append("IBR Hardship Cap Calculator JSON-LD SoftwareApplication name misattributed as 'RAP vs IBR Repayment Calculator'")

        return violations


__all__ = [
    "PricingTier",
    "FeatureContract",
    "TenantStatutoryTruth",
    "TenantTruthProfile",
    "TenantFactStore",
    "TruthReconciliationEngine",
    "PropertyContaminationError",
]

