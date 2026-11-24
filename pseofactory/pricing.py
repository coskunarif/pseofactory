"""
pseofactory Single Pricing Source of Truth (SSOT).
Defines canonical consumer and business tier pricing, SKU normalization,
per-tenant digital product catalogs, and Stripe inline price_data builders.
Designed for 50+ sites via audience_tier ("consumer" or "business") with
automatic inheritance and .pseofactory.json override support.

Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from pseofactory.contracts import assert_no_forbidden_dashes

DEFAULT_AUDIENCE_TIER: str = "business"
VALID_AUDIENCE_TIERS: Tuple[str, ...] = ("consumer", "business")

# Canonical one-time pricing matrix by audience tier.
# Consumer (e.g., Prexvo): $9 quick / $19 full / $299 partner slot.
# Business (ProfitHelm, GainHelm, LienBond, and default for new tenants): $15 quick / $29 full / $299 partner slot.
TIER_PRICING: Dict[str, Dict[str, Dict[str, Any]]] = {
    "consumer": {
        "quick": {
            "tier_kind": "quick",
            "label": "Quick Worksheet",
            "price_usd": 9.0,
            "price_cents": 900,
            "currency": "usd",
            "billing_mode": "payment",
        },
        "full": {
            "tier_kind": "full",
            "label": "Full Workpaper & Data Pack",
            "price_usd": 19.0,
            "price_cents": 1900,
            "currency": "usd",
            "billing_mode": "payment",
        },
        "partner_slot": {
            "tier_kind": "partner_slot",
            "label": "Verified Calculator Partner Slot",
            "price_usd": 299.0,
            "price_cents": 29900,
            "currency": "usd",
            "billing_mode": "payment",
        },
    },
    "business": {
        "quick": {
            "tier_kind": "quick",
            "label": "Quick Worksheet",
            "price_usd": 15.0,
            "price_cents": 1500,
            "currency": "usd",
            "billing_mode": "payment",
        },
        "full": {
            "tier_kind": "full",
            "label": "Full Workpaper & Data Pack",
            "price_usd": 29.0,
            "price_cents": 2900,
            "currency": "usd",
            "billing_mode": "payment",
        },
        "partner_slot": {
            "tier_kind": "partner_slot",
            "label": "Verified Calculator Partner Slot",
            "price_usd": 299.0,
            "price_cents": 29900,
            "currency": "usd",
            "billing_mode": "payment",
        },
    },
}

# Deprecated or duplicate SKU identifiers mapped to their single canonical SKU.
SKU_ALIASES: Dict[str, str] = {
    "lb_workers_comp_emr_audit_kit": "lb_workers_comp_emr_audit_packet",
    "ph_1031_boot_waterfall_kit": "ph_1031_boot_replacement_workpapers",
    "ph_section179_macrs_audit_kit": "ph_commercial_capital_audit_toolkit",
}

TENANT_DEFAULT_AUDIENCE_TIER: Dict[str, str] = {
    "prexvo": "consumer",
    "profithelm": "business",
    "gainhelm": "business",
    "lienbond": "business",
}

TENANT_SKU_PREFIX: Dict[str, str] = {
    "profithelm": "ph",
    "prexvo": "px",
    "gainhelm": "gh",
    "lienbond": "lb",
}

TENANT_BRAND_NAMES: Dict[str, str] = {
    "profithelm": "ProfitHelm",
    "prexvo": "Prexvo",
    "gainhelm": "GainHelm",
    "lienbond": "LienBond",
}

QUICK_SKU_BY_PROPERTY: Dict[str, str] = {
    "profithelm": "ph_instant_statutory_worksheet_19",
    "prexvo": "px_instant_repayment_worksheet_19",
    "gainhelm": "gh_instant_compliance_worksheet_19",
    "lienbond": "lb_instant_lien_bond_worksheet_19",
}

PARTNER_SLOT_SKU_BY_PROPERTY: Dict[str, str] = {
    "profithelm": "ph_verified_partner_slot",
    "prexvo": "px_verified_partner_slot",
    "gainhelm": "gh_verified_partner_slot",
    "lienbond": "lb_verified_partner_slot",
}

_PARTNER_SLOT_DELIVERABLES: List[str] = [
    "Verified Commercial Partner Desk Placement on Target Calculator Route",
    "State-Filtered High-Intent Lead Routing & SubID Attribution Feed",
    "Direct Calculator CTA & Partner Matrix Priority Slot",
    "Monthly Partner Attribution & Conversion Reconciliation Digest",
]


def normalize_sku(sku: str) -> str:
    """Normalizes a SKU identifier and resolves deprecated aliases to the canonical SKU."""
    clean = str(sku or "").strip().lower()
    if not clean:
        return ""
    return SKU_ALIASES.get(clean, clean)


def normalize_audience_tier(raw_tier: Optional[str], default: str = DEFAULT_AUDIENCE_TIER) -> str:
    """Validates and normalizes an audience_tier string to 'consumer' or 'business'."""
    val = str(raw_tier or "").strip().lower()
    if val in VALID_AUDIENCE_TIERS:
        return val
    return default if default in VALID_AUDIENCE_TIERS else DEFAULT_AUDIENCE_TIER


def _read_audience_tier_from_marker(repo_root: Union[str, Path]) -> Optional[str]:
    """Reads optional audience_tier override from <repo_root>/.pseofactory.json."""
    try:
        marker = Path(repo_root) / ".pseofactory.json"
        if not marker.is_file():
            return None
        data = json.loads(marker.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            raw = str(data.get("audience_tier") or "").strip().lower()
            if raw in VALID_AUDIENCE_TIERS:
                return raw
    except Exception:
        return None
    return None


def get_audience_tier(
    property_id: str,
    repo_root: Optional[Union[str, Path]] = None,
) -> str:
    """
    Resolves audience_tier ('consumer' or 'business') for any tenant.
    Precedence:
    1. Explicit .pseofactory.json audience_tier override (if repo_root given or resolvable).
    2. DeclarativeTenantContract.audience_tier from tenant_facts.py.
    3. Built-in default map (prexvo -> consumer; all business and future tenants -> business).
    """
    prop_clean = str(property_id or "").strip().lower()
    if repo_root:
        marker_tier = _read_audience_tier_from_marker(repo_root)
        if marker_tier:
            return marker_tier

    try:
        from pseofactory.tenant_facts import (
            CANONICAL_TENANT_DECLARATIONS,
            SPAWNED_TENANT_DECLARATIONS,
        )

        contract = (
            CANONICAL_TENANT_DECLARATIONS.get(prop_clean)
            or SPAWNED_TENANT_DECLARATIONS.get(prop_clean)
        )
        if contract is not None:
            if getattr(contract, "repo_root", ""):
                marker_tier = _read_audience_tier_from_marker(contract.repo_root)
                if marker_tier:
                    return marker_tier
            c_tier = str(getattr(contract, "audience_tier", "") or "").strip().lower()
            if c_tier in VALID_AUDIENCE_TIERS:
                return c_tier
    except Exception:
        pass

    return TENANT_DEFAULT_AUDIENCE_TIER.get(prop_clean, DEFAULT_AUDIENCE_TIER)


def get_tier_pricing(audience_tier: str = DEFAULT_AUDIENCE_TIER) -> Dict[str, Dict[str, Any]]:
    """Returns a deep copy of the canonical quick/full/partner_slot pricing for an audience tier."""
    tier = normalize_audience_tier(audience_tier)
    return {k: dict(v) for k, v in TIER_PRICING[tier].items()}


def get_valid_prices_for_tenant(
    property_id: str,
    repo_root: Optional[Union[str, Path]] = None,
) -> Set[float]:
    """Returns the canonical set of valid USD prices for a tenant ({0.0, quick, full, partner_slot})."""
    tier = get_audience_tier(property_id, repo_root=repo_root)
    tp = TIER_PRICING[tier]
    return {
        0.0,
        float(tp["quick"]["price_usd"]),
        float(tp["full"]["price_usd"]),
        float(tp["partner_slot"]["price_usd"]),
    }


def classify_sku_tier_kind(sku: str) -> str:
    """Classifies a SKU string into 'partner_slot', 'quick', or 'full'."""
    s = normalize_sku(sku)
    if s in ("partner_slot", "partner") or s.endswith("_verified_partner_slot") or "partner_slot" in s:
        return "partner_slot"
    if s == "quick" or "_instant_" in s or s.endswith("_worksheet_19") or s.endswith("_quick_worksheet"):
        return "quick"
    return "full"


def build_stripe_price_data(offer: Dict[str, Any], brand_name: str = "") -> Dict[str, Any]:
    """Builds canonical Stripe Checkout inline line_items[0].price_data from a resolved offer dict."""
    price_cents = int(offer["price_cents"])
    currency = str(offer.get("currency") or "usd").strip().lower()
    title = str(offer.get("title") or offer.get("offer_title") or "Workpaper Package").strip()
    description = str(offer.get("description") or "").strip()
    if not description:
        tier_kind = str(offer.get("tier_kind") or classify_sku_tier_kind(str(offer.get("sku") or "")))
        brand = brand_name or TENANT_BRAND_NAMES.get(str(offer.get("property_id") or "").lower(), "Platform")
        if tier_kind == "partner_slot":
            description = (
                f"{brand} Verified Calculator Partner Slot - Direct high-intent partner placement, "
                "state-filtered lead routing, and SubID attribution feed"
            )
        elif tier_kind == "quick":
            description = f"{brand} Quick Worksheet - Print-ready scenario workpaper and summary CSV export"
        else:
            description = (
                f"{brand} Full Workpaper & Data Pack - Multi-row dynamic schedules, "
                "5-point sensitivity table, CSV export, JSON data pack, and execution checklist"
            )
    assert_no_forbidden_dashes(title, context="stripe_price_data.name")
    assert_no_forbidden_dashes(description, context="stripe_price_data.description")
    return {
        "currency": currency,
        "unit_amount": price_cents,
        "product_data": {
            "name": title,
            "description": description,
        },
    }


def _build_canonical_offer_catalog() -> Dict[str, Dict[str, Any]]:
    """Constructs the canonical SKU catalog for all active tenants with pricing strictly derived from TIER_PRICING."""
    raw_specs: List[Dict[str, Any]] = [
        # ---- ProfitHelm (business: $15 quick / $29 full / $299 partner slot) ----
        {
            "sku": "ph_instant_statutory_worksheet_19",
            "property_id": "profithelm",
            "tier_kind": "quick",
            "vertical": "b2b_tax_advisory",
            "title": "ProfitHelm Quick Tax & Depreciation Worksheet",
            "description": (
                "ProfitHelm Quick Worksheet - Print/PDF-ready executive workpaper reflecting your actual "
                "calculator inputs and outputs, formula breakdown, compliance notes, and summary CSV export"
            ),
            "statutory_authority": "26 U.S.C. Section 1, IRC Section 199A, Section 179, and IRS Rev. Proc. 2025-32",
            "default_slug": "section-179-calculator",
            "trend_timeseries_ids": ["irs_sec199a_qbi", "ssa_fica_wage_base", "fred_cpilfesl_inflation"],
            "deliverables": [
                "Print/PDF-ready executive workpaper reflecting your exact calculator inputs and outputs (HTML/PDF)",
                "Formula, statutory authority, and 2026 compliance methodology breakdown (HTML/PDF)",
                "Summary reconciliation table export (CSV)",
            ],
        },
        {
            "sku": "ph_1031_boot_replacement_workpapers",
            "property_id": "profithelm",
            "tier_kind": "full",
            "vertical": "1031_exchange",
            "title": "ProfitHelm Section 1031 Full Workpaper & Data Pack",
            "description": (
                "ProfitHelm Full Workpaper & Data Pack - Dynamic 5-point boot sensitivity schedule, "
                "45-day/180-day exchange timeline, full multi-row CSV, JSON data pack, and execution checklist"
            ),
            "statutory_authority": "IRC Section 1031, Treas. Reg. 1.1031(k)-1, and IRS Form 8824",
            "default_slug": "section-1031-calculator",
            "trend_timeseries_ids": ["fred_dgs10_yield", "fred_cpilfesl_inflation", "irs_sec199a_qbi"],
            "deliverables": [
                "Everything in the Quick Worksheet populated with your exact calculator inputs and outputs (HTML/PDF)",
                "Dynamic 5-point boot and replacement equity sensitivity schedule computed from your inputs (HTML/CSV)",
                "45-day identification and 180-day closing statutory milestone schedule (HTML/CSV)",
                "Complete structured JSON data pack with inputs, outputs, schedules, and statutory metadata (JSON)",
                "Unredacted IRC Section 1031 QI assignment and safe-harbor execution checklist clauses (HTML/PDF)",
            ],
        },
        {
            "sku": "ph_commercial_capital_audit_toolkit",
            "property_id": "profithelm",
            "tier_kind": "full",
            "vertical": "commercial_capital",
            "title": "ProfitHelm Section 179 & Commercial Capital Full Workpaper & Data Pack",
            "description": (
                "ProfitHelm Full Workpaper & Data Pack - Dynamic 6-year MACRS depreciation schedule, "
                "5-point CapEx/APR sensitivity table, full multi-row CSV, JSON data pack, and filing checklist"
            ),
            "statutory_authority": "IRC Section 179, Section 168(k), IRS Form 4562, and UCC Article 9",
            "default_slug": "section-179-calculator",
            "trend_timeseries_ids": [
                "irs_sec179_cap",
                "irs_sec179_phaseout",
                "irs_sec168k_bonus",
                "cbp_sec301_tariff",
                "fred_dgs10_yield",
            ],
            "deliverables": [
                "Everything in the Quick Worksheet populated with your exact calculator inputs and outputs (HTML/PDF)",
                "Dynamic 6-year 200% DB MACRS vs Section 179/168(k) depreciation recovery schedule (HTML/CSV)",
                "Dynamic 5-point equipment basis and business-use sensitivity table computed from your inputs (HTML/CSV)",
                "Complete structured JSON data pack with inputs, outputs, schedules, and statutory metadata (JSON)",
                "Unredacted Form 4562 election and lender term-sheet execution checklist clauses (HTML/PDF)",
            ],
        },
        {
            "sku": "ph_statutory_tax_audit_workpapers",
            "property_id": "profithelm",
            "tier_kind": "full",
            "vertical": "b2b_tax_advisory",
            "title": "ProfitHelm 2026-2027 Tax & CPA Full Workpaper & Data Pack",
            "description": (
                "ProfitHelm Full Workpaper & Data Pack - Dynamic 5-point income/bracket sensitivity table, "
                "4-quarter safe-harbor schedule, full multi-row CSV, JSON data pack, and CPA checklist"
            ),
            "statutory_authority": "26 U.S.C. Section 1, IRC Section 199A, and IRS Rev. Proc. 2025-32",
            "default_slug": "s-corp-reasonable-salary-tax-calculator",
            "trend_timeseries_ids": [
                "irs_sec199a_qbi",
                "ssa_fica_wage_base",
                "irs_sec168k_bonus",
                "fred_cpilfesl_inflation",
            ],
            "deliverables": [
                "Everything in the Quick Worksheet populated with your exact calculator inputs and outputs (HTML/PDF)",
                "Dynamic 5-point income and marginal rate sensitivity schedule computed from your inputs (HTML/CSV)",
                "4-quarter IRC Section 6654 estimated tax safe-harbor installment schedule (HTML/CSV)",
                "Complete structured JSON data pack with inputs, outputs, schedules, and statutory metadata (JSON)",
                "Unredacted CPA substantiation and statutory filing checklist clauses (HTML/PDF)",
            ],
        },
        {
            "sku": "ph_verified_partner_slot",
            "property_id": "profithelm",
            "tier_kind": "partner_slot",
            "vertical": "b2b_partner_slot",
            "title": "Verified Calculator Partner Slot",
            "description": (
                "ProfitHelm Verified Calculator Partner Slot - Direct high-intent partner placement on "
                "ProfitHelm calculator routes, state-filtered lead routing, and SubID attribution feed"
            ),
            "statutory_authority": "16 CFR Part 255 Commercial Partner Desk Attribution & Placement Protocol",
            "default_slug": "section-1031-calculator",
            "trend_timeseries_ids": ["irs_sec199a_qbi", "fred_dgs10_yield", "fred_cpilfesl_inflation"],
            "deliverables": list(_PARTNER_SLOT_DELIVERABLES),
        },
        # ---- Prexvo (consumer: $9 quick / $19 full / $299 partner slot) ----
        {
            "sku": "px_instant_repayment_worksheet_19",
            "property_id": "prexvo",
            "tier_kind": "quick",
            "vertical": "student_loan_refinance",
            "title": "Prexvo Quick Repayment & Refinance Worksheet",
            "description": (
                "Prexvo Quick Worksheet - Print/PDF-ready executive borrower worksheet reflecting your actual "
                "loan inputs and outputs, formula breakdown, Title IV compliance notes, and summary CSV export"
            ),
            "statutory_authority": "20 U.S.C. 1087e, Truth in Lending Act (12 CFR Part 1026), and 34 CFR 685.209",
            "default_slug": "student-loan-refinance-break-even-calculator",
            "trend_timeseries_ids": ["ed_direct_undergrad_rate", "ed_idr_discretionary_levy", "hhs_fpl_single_base"],
            "deliverables": [
                "Print/PDF-ready executive borrower worksheet reflecting your exact loan inputs and outputs (HTML/PDF)",
                "Amortization formula, APR comparison, and Title IV federal protection notes (HTML/PDF)",
                "Summary loan comparison table export (CSV)",
            ],
        },
        {
            "sku": "px_refi_amortization_decision_audit",
            "property_id": "prexvo",
            "tier_kind": "full",
            "vertical": "student_loan_refinance",
            "title": "Prexvo Full Amortization Workpaper & Data Pack",
            "description": (
                "Prexvo Full Workpaper & Data Pack - Dynamic multi-period loan amortization schedule, "
                "5-point APR sensitivity table, full multi-row CSV, JSON data pack, and Title IV checklist"
            ),
            "statutory_authority": "Higher Education Act Title IV (20 U.S.C. 1070 et seq.) and 34 CFR Part 685",
            "default_slug": "student-loan-refinance-break-even-calculator",
            "trend_timeseries_ids": [
                "ed_direct_undergrad_rate",
                "ed_idr_discretionary_levy",
                "ed_idr_fpl_multiplier",
                "hhs_fpl_single_base",
                "irs_sec108f_tax_free_forgiveness",
            ],
            "deliverables": [
                "Everything in the Quick Worksheet populated with your exact loan inputs and outputs (HTML/PDF)",
                "Dynamic multi-period amortization schedule (Month 1-12 detail + Year 1-N annual balance/interest rollups) computed from your inputs (HTML/CSV)",
                "Dynamic 5-point APR spread sensitivity table computed from your loan principal and term (HTML/CSV)",
                "Complete structured JSON data pack with inputs, outputs, schedules, and Title IV metadata (JSON)",
                "Unredacted 34 CFR 685 forfeiture waiver, TILA rescission, and cosigner release checklist clauses (HTML/PDF)",
            ],
        },
        {
            "sku": "px_verified_partner_slot",
            "property_id": "prexvo",
            "tier_kind": "partner_slot",
            "vertical": "student_loan_partner_slot",
            "title": "Verified Calculator Partner Slot",
            "description": (
                "Prexvo Verified Calculator Partner Slot - Direct high-intent partner placement on "
                "Prexvo refinance calculator routes, state-filtered lead routing, and SubID attribution feed"
            ),
            "statutory_authority": "16 CFR Part 255 Commercial Partner Desk Attribution & Placement Protocol",
            "default_slug": "student-loan-refinance-break-even-calculator",
            "trend_timeseries_ids": ["ed_direct_undergrad_rate", "ed_idr_discretionary_levy", "hhs_fpl_single_base"],
            "deliverables": list(_PARTNER_SLOT_DELIVERABLES),
        },
        # ---- GainHelm (business: $15 quick / $29 full / $299 partner slot) ----
        {
            "sku": "gh_instant_compliance_worksheet_19",
            "property_id": "gainhelm",
            "tier_kind": "quick",
            "vertical": "b2b_cyber_compliance",
            "title": "GainHelm Quick Compliance Budget & Scoping Worksheet",
            "description": (
                "GainHelm Quick Worksheet - Print/PDF-ready executive audit scoping workpaper reflecting your actual "
                "calculator inputs and outputs, methodology breakdown, statutory notes, and summary CSV export"
            ),
            "statutory_authority": "AICPA SSAE 18 (AT-C 205), DoD 32 CFR Part 170, ISO/IEC 27006-1:2024, and 45 CFR 160.404",
            "default_slug": "soc-2-audit-cost-calculator",
            "trend_timeseries_ids": ["dod_32cfr170_cmmc_controls", "iso_27006_stage2_days"],
            "deliverables": [
                "Print/PDF-ready executive audit scoping workpaper reflecting your exact calculator inputs and outputs (HTML/PDF)",
                "Audit cost methodology, statutory authority, and compliance scoping notes (HTML/PDF)",
                "Summary budget reconciliation table export (CSV)",
            ],
        },
        {
            "sku": "gh_soc2_cmmc_audit_workpapers",
            "property_id": "gainhelm",
            "tier_kind": "full",
            "vertical": "b2b_cyber_compliance",
            "title": "GainHelm SOC 2 Type II, CMMC 2.0 & NIST 800-171 Audit Scoping Workpaper Suite",
            "description": (
                "GainHelm Full Workpaper & Data Pack - Dynamic 5-point audit scope sensitivity table, "
                "6-phase 180-day readiness/POA&M schedule, full multi-row CSV, JSON data pack, and execution checklist"
            ),
            "statutory_authority": "AICPA SSAE 18 (AT-C Section 205), Trust Services Criteria (TSP Section 100) & 32 CFR Part 170",
            "default_slug": "soc-2-audit-cost-calculator",
            "trend_timeseries_ids": [
                "dod_32cfr170_cmmc_controls",
                "nist_800_171_sprs_max",
                "hhs_ocr_hipaa_tier4_cap",
                "iso_27006_stage2_days",
            ],
            "deliverables": [
                "JSON + CSV Control Scoping Matrix (AICPA Trust Services Criteria, NIST 800-171 & ISO 27001 Annex A)",
                "Auditor-Day Rate & Readiness Gap Worksheet (Type I vs Type II observation window sensitivity)",
                "CISO & CFO Board Budget Approval Template with GRC automation ROI comparison",
                "3-Year Audit, Penetration Testing & Compliance Staffing Total Cost of Ownership (TCO) Schedule",
            ],
        },
        {
            "sku": "gh_hipaa_iso27001_governance_kit",
            "property_id": "gainhelm",
            "tier_kind": "full",
            "vertical": "b2b_cyber_compliance",
            "title": "GainHelm ISO 27001, HIPAA & Governance Full Workpaper & Data Pack",
            "description": (
                "GainHelm Full Workpaper & Data Pack - Dynamic 5-point governance and penalty exposure sensitivity table, "
                "6-phase 180-day readiness schedule, full multi-row CSV, JSON data pack, and execution checklist"
            ),
            "statutory_authority": "ISO/IEC 27006-1:2024, 45 CFR 160.404 (HITECH Act), and PCI DSS v4.0.1",
            "default_slug": "iso-27001-certification-cost-calculator",
            "trend_timeseries_ids": ["iso_27006_stage2_days", "hhs_ocr_hipaa_tier4_cap", "dod_32cfr170_cmmc_controls"],
            "deliverables": [
                "Everything in the Quick Worksheet populated with your exact calculator inputs and outputs (HTML/PDF)",
                "Dynamic 5-point compliance scope, penalty mitigation, and multi-framework reuse sensitivity table (HTML/CSV)",
                "Dynamic 6-phase 180-day certification and governance milestone schedule scaled to your scope (HTML/CSV)",
                "Complete structured JSON data pack with inputs, outputs, schedules, and regulatory metadata (JSON)",
                "Unredacted governance scope attestation, remediation calendar, and safe-harbor clauses (HTML/PDF)",
            ],
        },
        {
            "sku": "gh_verified_partner_slot",
            "property_id": "gainhelm",
            "tier_kind": "partner_slot",
            "vertical": "b2b_cyber_partner_slot",
            "title": "Verified Calculator Partner Slot",
            "description": (
                "GainHelm Verified Calculator Partner Slot - Direct high-intent partner placement on "
                "GainHelm compliance calculator routes, state-filtered lead routing, and SubID attribution feed"
            ),
            "statutory_authority": "16 CFR Part 255 Commercial Partner Desk Attribution & Placement Protocol",
            "default_slug": "soc-2-audit-cost-calculator",
            "trend_timeseries_ids": ["dod_32cfr170_cmmc_controls", "iso_27006_stage2_days", "hhs_ocr_hipaa_tier4_cap"],
            "deliverables": list(_PARTNER_SLOT_DELIVERABLES),
        },
        # ---- LienBond (business: $15 quick / $29 full / $299 partner slot) ----
        {
            "sku": "lb_instant_lien_bond_worksheet_19",
            "property_id": "lienbond",
            "tier_kind": "quick",
            "vertical": "commercial_surety_insurance",
            "title": "LienBond Quick Surety, EMR & Lien Worksheet",
            "description": (
                "LienBond Quick Worksheet - Print/PDF-ready executive construction compliance workpaper reflecting "
                "your actual calculator inputs and outputs, formula breakdown, state statutory notes, and summary CSV export"
            ),
            "statutory_authority": "40 U.S.C. Section 3131, U.S. Treasury Circular 570, and NCCI Experience Rating Plan",
            "default_slug": "contractor-license-bond-cost-calculator-by-credit-score",
            "trend_timeseries_ids": ["sfaa_surety_loss_ratio", "ncci_emr_split_point"],
            "deliverables": [
                "Print/PDF-ready executive contractor workpaper reflecting your exact calculator inputs and outputs (HTML/PDF)",
                "Surety rate, NCCI EMR, and state statutory lien deadline methodology breakdown (HTML/PDF)",
                "Summary compliance reconciliation table export (CSV)",
            ],
        },
        {
            "sku": "lb_surety_bond_underwriting_kit",
            "property_id": "lienbond",
            "tier_kind": "full",
            "vertical": "commercial_surety_insurance",
            "title": "LienBond Surety Bond Full Workpaper & Data Pack",
            "description": (
                "LienBond Full Workpaper & Data Pack - Dynamic 5-point credit/underwriting tier sensitivity table, "
                "state statutory bond/lien milestone schedule, full multi-row CSV, JSON data pack, and filing clauses"
            ),
            "statutory_authority": "40 U.S.C. Section 3131 (Miller Act), FAR 28.102, and U.S. Treasury Circular 570",
            "default_slug": "contractor-license-bond-cost-calculator-by-credit-score",
            "trend_timeseries_ids": ["sfaa_surety_loss_ratio", "census_vip_construction"],
            "deliverables": [
                "Everything in the Quick Worksheet populated with your exact calculator inputs and outputs (HTML/PDF)",
                "Dynamic 5-point credit-tier surety bond premium and working capital capacity sensitivity table (HTML/CSV)",
                "State statutory Miller Act / notice / recording milestone timeline schedule (HTML/CSV)",
                "Complete structured JSON data pack with inputs, outputs, schedules, and statutory metadata (JSON)",
                "Unredacted payment bond notice, waiver, and surety submission execution clauses (HTML/PDF)",
            ],
        },
        {
            "sku": "lb_workers_comp_emr_audit_packet",
            "property_id": "lienbond",
            "tier_kind": "full",
            "vertical": "commercial_surety_insurance",
            "title": "LienBond Workers Comp & EMR Full Workpaper & Data Pack",
            "description": (
                "LienBond Full Workpaper & Data Pack - Dynamic 5-point EMR/payroll sensitivity table, "
                "statutory audit compliance milestone schedule, full multi-row CSV, JSON data pack, and execution clauses"
            ),
            "statutory_authority": "NCCI Experience Rating Plan Manual and State Workers Compensation Rating Bureaus",
            "default_slug": "experience-modification-rate-emr-workers-comp-penalty-calculator",
            "trend_timeseries_ids": ["ncci_emr_split_point", "bls_construction_injury_rate"],
            "deliverables": [
                "Everything in the Quick Worksheet populated with your exact calculator inputs and outputs (HTML/PDF)",
                "Dynamic 5-point EMR factor and payroll audit surcharge sensitivity table computed from your inputs (HTML/CSV)",
                "Workers compensation audit defense and state compliance milestone schedule (HTML/CSV)",
                "Complete structured JSON data pack with inputs, outputs, schedules, and NCCI metadata (JSON)",
                "Unredacted NCCI overtime deduction and carrier audit execution checklist clauses (HTML/PDF)",
            ],
        },
        {
            "sku": "lb_wh347_certified_payroll_packet",
            "property_id": "lienbond",
            "tier_kind": "full",
            "vertical": "commercial_surety_insurance",
            "title": "LienBond Davis-Bacon WH-347 Full Workpaper & Data Pack",
            "description": (
                "LienBond Full Workpaper & Data Pack - Dynamic 5-point prevailing wage/fringe sensitivity table, "
                "certified payroll milestone schedule, full multi-row CSV, JSON data pack, and WH-347 compliance clauses"
            ),
            "statutory_authority": "40 U.S.C. Section 3141 (Davis-Bacon Act) and 29 CFR Part 5",
            "default_slug": "davis-bacon-prevailing-wage-fringe-benefit-rate-calculator",
            "trend_timeseries_ids": ["dol_whd_prevailing_wage", "bls_eci_construction"],
            "deliverables": [
                "Everything in the Quick Worksheet populated with your exact calculator inputs and outputs (HTML/PDF)",
                "Dynamic 5-point prevailing wage, overtime, and fringe offset sensitivity table computed from your inputs (HTML/CSV)",
                "DOL Form WH-347 weekly compliance and payroll audit milestone schedule (HTML/CSV)",
                "Complete structured JSON data pack with inputs, outputs, schedules, and 29 CFR Part 5 metadata (JSON)",
                "Unredacted 29 CFR 5.5 Statement of Compliance and NCCI audit execution clauses (HTML/PDF)",
            ],
        },
        {
            "sku": "lb_mechanics_lien_waiver_packet",
            "property_id": "lienbond",
            "tier_kind": "full",
            "vertical": "commercial_surety_insurance",
            "title": "LienBond Mechanics Lien & Waiver Full Workpaper & Data Pack",
            "description": (
                "LienBond Full Workpaper & Data Pack - Dynamic 5-point retainage/exposure sensitivity table, "
                "state statutory preliminary notice and recording calendar, full CSV, JSON data pack, and waiver clauses"
            ),
            "statutory_authority": "Cal. Civ. Code Sections 8132-8416, Tex. Prop. Code Ch. 53, and Fla. Stat. Section 713.06",
            "default_slug": "california-texas-florida-preliminary-notice-deadline-calculator",
            "trend_timeseries_ids": ["census_vip_construction", "sfaa_surety_loss_ratio"],
            "deliverables": [
                "Everything in the Quick Worksheet populated with your exact calculator inputs and outputs (HTML/PDF)",
                "Dynamic 5-point retainage holdback and surety exposure sensitivity table computed from your inputs (HTML/CSV)",
                "State-specific preliminary notice, lien recording, and enforcement deadline schedule (HTML/CSV)",
                "Complete structured JSON data pack with inputs, outputs, schedules, and state statute metadata (JSON)",
                "Unredacted conditional progress waiver and payment bond claim execution clauses (HTML/PDF)",
            ],
        },
        {
            "sku": "lb_surety_lien_wh347_packet",
            "property_id": "lienbond",
            "tier_kind": "full",
            "vertical": "commercial_surety_insurance",
            "title": "LienBond Master Surety, Lien & WH-347 Full Workpaper & Data Pack",
            "description": (
                "LienBond Full Workpaper & Data Pack - Dynamic 5-point underwriting/EMR/retainage sensitivity table, "
                "state statutory deadline calendar, full multi-row CSV, JSON data pack, and execution clauses"
            ),
            "statutory_authority": "40 U.S.C. Sections 3131 & 3141, U.S. Treasury Circular 570, and State Mechanics Lien Statutes",
            "default_slug": "miller-act-performance-and-payment-bond-premium-calculator",
            "trend_timeseries_ids": ["sfaa_surety_loss_ratio", "ncci_emr_split_point", "census_vip_construction"],
            "deliverables": [
                "Everything in the Quick Worksheet populated with your exact calculator inputs and outputs (HTML/PDF)",
                "Dynamic 5-point surety bond, EMR, and retainage exposure sensitivity table computed from your inputs (HTML/CSV)",
                "State statutory preliminary notice, lien recording, and WH-347 compliance milestone schedule (HTML/CSV)",
                "Complete structured JSON data pack with inputs, outputs, schedules, and statutory metadata (JSON)",
                "Unredacted lien waiver, Miller Act notice, and WH-347 compliance execution clauses (HTML/PDF)",
            ],
        },
        {
            "sku": "lb_verified_partner_slot",
            "property_id": "lienbond",
            "tier_kind": "partner_slot",
            "vertical": "commercial_surety_partner_slot",
            "title": "Verified Calculator Partner Slot",
            "description": (
                "LienBond Verified Calculator Partner Slot - Direct high-intent partner placement on "
                "LienBond contractor calculator routes, state-filtered lead routing, and SubID attribution feed"
            ),
            "statutory_authority": "16 CFR Part 255 Commercial Partner Desk Attribution & Placement Protocol",
            "default_slug": "contractor-license-bond-cost-calculator-by-credit-score",
            "trend_timeseries_ids": ["sfaa_surety_loss_ratio", "ncci_emr_split_point", "census_vip_construction"],
            "deliverables": list(_PARTNER_SLOT_DELIVERABLES),
        },
    ]

    catalog: Dict[str, Dict[str, Any]] = {}
    for spec in raw_specs:
        prop_id = spec["property_id"]
        tier_kind = spec["tier_kind"]
        aud_tier = TENANT_DEFAULT_AUDIENCE_TIER.get(prop_id, DEFAULT_AUDIENCE_TIER)
        price_meta = TIER_PRICING[aud_tier][tier_kind]
        entry = {
            **spec,
            "audience_tier": aud_tier,
            "price_usd": float(price_meta["price_usd"]),
            "price_cents": int(price_meta["price_cents"]),
            "currency": str(price_meta["currency"]),
            "billing_mode": str(price_meta["billing_mode"]),
        }
        assert_no_forbidden_dashes(entry["title"], context=f"pricing.{entry['sku']}.title")
        assert_no_forbidden_dashes(entry["description"], context=f"pricing.{entry['sku']}.description")
        for d in entry["deliverables"]:
            assert_no_forbidden_dashes(d, context=f"pricing.{entry['sku']}.deliverable")
        catalog[entry["sku"]] = entry
    return catalog


OFFER_CATALOG: Dict[str, Dict[str, Any]] = _build_canonical_offer_catalog()


def _select_full_sku_for_slug(property_id: str, slug: str = "", vertical: str = "") -> str:
    """Selects the canonical full-tier SKU for a given property, calculator slug, and vertical."""
    prop_clean = str(property_id or "profithelm").strip().lower()
    s = str(slug or "").strip().lower()
    v = str(vertical or "").strip().lower()

    if prop_clean == "prexvo":
        return "px_refi_amortization_decision_audit"

    if prop_clean == "gainhelm":
        try:
            from pseofactory.affiliates import get_gainhelm_framework_profile

            prof = get_gainhelm_framework_profile(slug=s, vertical=v)
            prof_sku = normalize_sku(str((prof or {}).get("offer_sku") or ""))
            if prof_sku:
                return prof_sku
        except Exception:
            pass
        if any(
            tok in s or tok in v
            for tok in (
                "hipaa",
                "iso-27001",
                "iso27001",
                "pci",
                "hitrust",
                "cyber-liability",
                "cyber-insurance",
                "dora",
                "eu-ai",
                "eu_ai",
                "gdpr",
                "ccpa",
                "cpra",
                "nis2",
                "sec-8k",
                "sec_8k",
                "sec_cyber",
                "sec-cybersecurity",
                "8k-item-105",
            )
        ):
            return "gh_hipaa_iso27001_governance_kit"
        return "gh_soc2_cmmc_audit_workpapers"

    if prop_clean == "lienbond":
        if any(tok in s or tok in v for tok in ("lien", "waiver", "retainage", "preliminary-notice")):
            return "lb_mechanics_lien_waiver_packet"
        if any(tok in s or tok in v for tok in ("prevailing-wage", "davis-bacon", "wh-347", "wh347")):
            return "lb_wh347_certified_payroll_packet"
        if any(tok in s or tok in v for tok in ("workers-comp", "emr", "general-liability", "builders-risk", "sdi")):
            return "lb_workers_comp_emr_audit_packet"
        if any(tok in s or tok in v for tok in ("license-bond", "surety-bond", "bid-bond", "erisa-fidelity")):
            return "lb_surety_bond_underwriting_kit"
        return "lb_surety_lien_wh347_packet"

    if prop_clean == "profithelm":
        if any(tok in s or tok in v for tok in ("1031", "like-kind", "exchange", "8824", "3840", "boot", "dst")):
            return "ph_1031_boot_replacement_workpapers"
        if any(tok in s or tok in v for tok in ("factoring", "invoice", "179", "equipment", "capex", "tariff", "301", "landed-cost", "macrs", "lease", "vehicle", "gvwr")):
            return "ph_commercial_capital_audit_toolkit"
        return "ph_statutory_tax_audit_workpapers"

    prefix = TENANT_SKU_PREFIX.get(prop_clean, prop_clean[:3] or "pf")
    return f"{prefix}_full_workpaper_pack"


def _synthesize_dynamic_tenant_offer(
    property_id: str,
    tier_kind: str,
    audience_tier: str,
    slug: str = "",
    vertical: str = "",
) -> Dict[str, Any]:
    """Synthesizes a canonical offer for any future tenant (50+ site ready) not in OFFER_CATALOG."""
    prop_clean = str(property_id or "tenant").strip().lower()
    brand = TENANT_BRAND_NAMES.get(prop_clean, prop_clean.replace("-", " ").replace("_", " ").title())
    prefix = TENANT_SKU_PREFIX.get(prop_clean, prop_clean[:3] or "pf")
    tk = tier_kind if tier_kind in ("quick", "full", "partner_slot") else "full"
    price_meta = TIER_PRICING[audience_tier][tk]

    if tk == "partner_slot":
        sku = f"{prefix}_verified_partner_slot"
        title = "Verified Calculator Partner Slot"
        description = (
            f"{brand} Verified Calculator Partner Slot - Direct high-intent partner placement, "
            "state-filtered lead routing, and SubID attribution feed"
        )
        authority = "16 CFR Part 255 Commercial Partner Desk Attribution & Placement Protocol"
        deliverables = list(_PARTNER_SLOT_DELIVERABLES)
    elif tk == "quick":
        sku = f"{prefix}_quick_worksheet"
        title = f"{brand} Quick Calculation Worksheet"
        description = (
            f"{brand} Quick Worksheet - Print/PDF-ready executive workpaper reflecting your actual "
            "calculator inputs and outputs, formula breakdown, compliance notes, and summary CSV export"
        )
        authority = f"{brand} Statutory Calculation & Compliance Reference"
        deliverables = [
            "Print/PDF-ready executive workpaper reflecting your exact calculator inputs and outputs (HTML/PDF)",
            "Formula, statutory authority, and compliance methodology breakdown (HTML/PDF)",
            "Summary reconciliation table export (CSV)",
        ]
    else:
        sku = f"{prefix}_full_workpaper_pack"
        title = f"{brand} Full Workpaper & Data Pack"
        description = (
            f"{brand} Full Workpaper & Data Pack - Dynamic 5-point sensitivity and projection schedules, "
            "full multi-row CSV export, structured JSON data pack, and execution checklist"
        )
        authority = f"{brand} Statutory Calculation & Audit Reference"
        deliverables = [
            "Everything in the Quick Worksheet populated with your exact calculator inputs and outputs (HTML/PDF)",
            "Dynamic 5-point sensitivity and multi-period projection schedule computed from your inputs (HTML/CSV)",
            "Complete structured JSON data pack with inputs, outputs, schedules, and statutory metadata (JSON)",
            "Unredacted statutory execution and filing checklist clauses (HTML/PDF)",
        ]

    entry = {
        "sku": sku,
        "offer_sku": sku,
        "property_id": prop_clean,
        "audience_tier": audience_tier,
        "tier_kind": tk,
        "vertical": str(vertical or ("b2b_partner_slot" if tk == "partner_slot" else "statutory_workpaper")),
        "title": title,
        "description": description,
        "price_usd": float(price_meta["price_usd"]),
        "price_cents": int(price_meta["price_cents"]),
        "currency": str(price_meta["currency"]),
        "billing_mode": str(price_meta["billing_mode"]),
        "statutory_authority": authority,
        "default_slug": str(slug or "general").strip().lower() or "general",
        "deliverables": deliverables,
        "trend_timeseries_ids": [],
    }
    entry["stripe_price_data"] = build_stripe_price_data(entry, brand_name=brand)
    return entry


def resolve_offer_pricing(
    property_id: str,
    tier_kind: str = "full",
    slug: str = "",
    vertical: str = "",
    sku: str = "",
    repo_root: Optional[Union[str, Path]] = None,
    audience_tier: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Single pricing resolver for any property, tier_kind ('quick' | 'full' | 'partner_slot'),
    calculator slug, vertical, or explicit SKU.
    Always computes price_usd, price_cents, currency='usd', deliverables, and stripe_price_data
    from canonical TIER_PRICING and the tenant's resolved audience_tier.
    """
    prop_clean = str(property_id or "profithelm").strip().lower()
    norm_sku = normalize_sku(sku)

    # If an explicit canonical SKU is provided and exists in OFFER_CATALOG, infer its property/tier_kind.
    if norm_sku and norm_sku in OFFER_CATALOG:
        base = dict(OFFER_CATALOG[norm_sku])
        eff_prop = str(base["property_id"])
        aud_tier = (
            normalize_audience_tier(audience_tier)
            if audience_tier
            else get_audience_tier(eff_prop, repo_root=repo_root)
        )
        eff_tk = str(base["tier_kind"])
        price_meta = TIER_PRICING[aud_tier][eff_tk]
        base["audience_tier"] = aud_tier
        base["price_usd"] = float(price_meta["price_usd"])
        base["price_cents"] = int(price_meta["price_cents"])
        base["currency"] = str(price_meta["currency"])
        base["billing_mode"] = str(price_meta["billing_mode"])
        base["offer_sku"] = base["sku"]
        base["deliverables"] = list(base["deliverables"])
        base["trend_timeseries_ids"] = list(base.get("trend_timeseries_ids") or [])
        base["stripe_price_data"] = build_stripe_price_data(
            base,
            brand_name=TENANT_BRAND_NAMES.get(eff_prop, eff_prop.capitalize()),
        )
        return base

    aud_tier = (
        normalize_audience_tier(audience_tier)
        if audience_tier
        else get_audience_tier(prop_clean, repo_root=repo_root)
    )
    eff_tk = (
        classify_sku_tier_kind(norm_sku)
        if norm_sku
        else (str(tier_kind or "full").strip().lower())
    )
    if eff_tk not in ("quick", "full", "partner_slot"):
        eff_tk = "full"

    if eff_tk == "quick" and prop_clean in QUICK_SKU_BY_PROPERTY:
        target_sku = QUICK_SKU_BY_PROPERTY[prop_clean]
    elif eff_tk == "partner_slot" and prop_clean in PARTNER_SLOT_SKU_BY_PROPERTY:
        target_sku = PARTNER_SLOT_SKU_BY_PROPERTY[prop_clean]
    elif eff_tk == "full" and prop_clean in TENANT_SKU_PREFIX:
        target_sku = _select_full_sku_for_slug(prop_clean, slug=slug, vertical=vertical)
    else:
        return _synthesize_dynamic_tenant_offer(
            property_id=prop_clean,
            tier_kind=eff_tk,
            audience_tier=aud_tier,
            slug=slug,
            vertical=vertical,
        )

    if target_sku in OFFER_CATALOG:
        return resolve_offer_pricing(
            property_id=prop_clean,
            tier_kind=eff_tk,
            slug=slug,
            vertical=vertical,
            sku=target_sku,
            repo_root=repo_root,
            audience_tier=audience_tier,
        )
    return _synthesize_dynamic_tenant_offer(
        property_id=prop_clean,
        tier_kind=eff_tk,
        audience_tier=aud_tier,
        slug=slug,
        vertical=vertical,
    )


def get_tenant_catalog(
    property_id: str,
    repo_root: Optional[Union[str, Path]] = None,
    audience_tier: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Returns all canonical SKUs for a property keyed by SKU, with live resolved pricing."""
    prop_clean = str(property_id or "profithelm").strip().lower()
    matched = [sku for sku, item in OFFER_CATALOG.items() if item["property_id"] == prop_clean]
    if not matched:
        return {
            item["sku"]: item
            for item in (
                resolve_offer_pricing(prop_clean, tier_kind="quick", repo_root=repo_root, audience_tier=audience_tier),
                resolve_offer_pricing(prop_clean, tier_kind="full", repo_root=repo_root, audience_tier=audience_tier),
                resolve_offer_pricing(prop_clean, tier_kind="partner_slot", repo_root=repo_root, audience_tier=audience_tier),
            )
        }
    return {
        sku: resolve_offer_pricing(prop_clean, sku=sku, repo_root=repo_root, audience_tier=audience_tier)
        for sku in matched
    }


def get_all_digital_products() -> Dict[str, Dict[str, Any]]:
    """Returns the canonical monetization_vault.json-compatible digital_products dictionary."""
    products: Dict[str, Dict[str, Any]] = {}
    for sku in OFFER_CATALOG:
        resolved = resolve_offer_pricing(OFFER_CATALOG[sku]["property_id"], sku=sku)
        products[sku] = {
            "sku": resolved["sku"],
            "property_id": resolved["property_id"],
            "audience_tier": resolved["audience_tier"],
            "tier_kind": resolved["tier_kind"],
            "vertical": resolved["vertical"],
            "title": resolved["title"],
            "description": resolved["description"],
            "price_usd": resolved["price_usd"],
            "price_cents": resolved["price_cents"],
            "currency": resolved["currency"],
            "statutory_authority": resolved["statutory_authority"],
            "trend_timeseries_ids": list(resolved.get("trend_timeseries_ids") or []),
            "deliverables": list(resolved["deliverables"]),
        }
    return products


def get_edge_pricing_table_json(property_id: str) -> str:
    """
    Serializes the canonical per-tenant SKU catalog into deterministic JSON
    for direct embedding in generated functions/api/lead-capture.js.
    """
    catalog = get_tenant_catalog(property_id)
    edge_map: Dict[str, Dict[str, Any]] = {}
    for sku, item in catalog.items():
        edge_map[sku] = {
            "sku": item["sku"],
            "property_id": item["property_id"],
            "audience_tier": item["audience_tier"],
            "tier_kind": item["tier_kind"],
            "vertical": item["vertical"],
            "title": item["title"],
            "description": item["description"],
            "price_usd": int(item["price_usd"]) if float(item["price_usd"]).is_integer() else float(item["price_usd"]),
            "price_cents": int(item["price_cents"]),
            "currency": item["currency"],
            "billing_mode": item["billing_mode"],
            "statutory_authority": item["statutory_authority"],
            "default_slug": item["default_slug"],
            "deliverables": list(item["deliverables"]),
        }
    rendered = json.dumps(edge_map, indent=2, sort_keys=False)
    assert_no_forbidden_dashes(rendered, context=f"edge_pricing_table({property_id})")
    return rendered


__all__ = [
    "DEFAULT_AUDIENCE_TIER",
    "VALID_AUDIENCE_TIERS",
    "TIER_PRICING",
    "SKU_ALIASES",
    "TENANT_DEFAULT_AUDIENCE_TIER",
    "TENANT_SKU_PREFIX",
    "TENANT_BRAND_NAMES",
    "QUICK_SKU_BY_PROPERTY",
    "PARTNER_SLOT_SKU_BY_PROPERTY",
    "OFFER_CATALOG",
    "normalize_sku",
    "normalize_audience_tier",
    "get_audience_tier",
    "get_tier_pricing",
    "get_valid_prices_for_tenant",
    "classify_sku_tier_kind",
    "build_stripe_price_data",
    "resolve_offer_pricing",
    "get_tenant_catalog",
    "get_all_digital_products",
    "get_edge_pricing_table_json",
]
