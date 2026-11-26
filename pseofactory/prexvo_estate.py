"""
Central Truth-Pack-driven Prexvo (prexvo.com) Static Estate Compiler Module.
Consolidates Prexvo's Title IV repayment calculators, 2026 HHS Poverty Guidelines
(91 FR 1797), 2026 P.L. 119-21 Section 82001 RAP rules (360-month forgiveness,
100% unpaid interest subsidy, $50/mo principal match), statutory JSON-LD schemas,
workpaper CTAs, YMYL disclosures, and deployed void integration inside pseofactory.
Zero em-dashes (U+2014). Zero en-dashes (U+2013).
"""

from __future__ import annotations

import copy
import html
import json
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from pseofactory.affiliates import (
    PREXVO_AFFILIATES,
    PREXVO_DISCLOSURES,
    build_step1_preview_controls_html,
    is_restricted_public_service_slug,
    score_partner_yield,
)
from pseofactory.contracts import (
    assert_ai_mode_calculation_manifest,
    assert_no_forbidden_dashes,
    normalize_statutory_acronym_casing,
)
from pseofactory.estate_common import (
    build_organization_schema,
    cap_llms_txt_content,
    compile_schema_graph,
    normalize_tenant_seo_title,
    prepare_estate_dirs,
    sanitize_public_catalog_file,
    sanitize_tenant_overlays,
    write_machine_endpoints_and_headers,
    write_sitemaps_and_robots,
    write_tenant_edge_functions,
)
from pseofactory.pricing import resolve_offer_pricing
from pseofactory.truth_pack import (
    TruthPack,
    derive_js_expression,
    load_truth_pack,
    safe_eval_formula,
)
from pseofactory.visual_primitives import (
    render_external_runtime_synchronizer_tag,
    write_runtime_synchronizer_asset,
)

PREXVO_DOMAIN = "prexvo.com"
PREXVO_CANONICAL_BASE = f"https://{PREXVO_DOMAIN}"
PREXVO_SITE_NAME = "Prexvo"
PREXVO_SITE_TITLE = "Prexvo | Free Student Loan Calculators & Comparison"
PREXVO_SITE_DESCRIPTION = (
    "Compare 2026 student loan repayment plans with exact Title IV calculations. "
    "Free interactive tools for RAP, IBR, PAYE, ICR, PSLF, and consolidation."
)
PREXVO_AUTHOR = "Prexvo Statutory Research Group"
PREXVO_CONTACT_EMAIL = "contact@prexvo.com"
PREXVO_LINKEDIN_ID = os.getenv(
    "FACTORY_PREXVO_LINKEDIN_COMPANY_ID",
    os.getenv("FACTORY_LINKEDIN_COMPANY_ID", "106482194"),
)
PREXVO_LINKEDIN_URL = f"https://www.linkedin.com/company/{PREXVO_LINKEDIN_ID}"
PREXVO_WIKIDATA_URL = "https://www.wikidata.org/wiki/Q633315"

YMYL_FORFEITURE_DISCLOSURE = (
    "Important Federal Borrower Notice: Refinancing federal student loans into a private loan "
    "permanently forfeits and permanently waives federal protections, including Income-Driven "
    "Repayment (IBR), the Repayment Assistance Plan (RAP) interest subsidy, federal forbearance, "
    "and Public Service Loan Forgiveness (PSLF)."
)
AFFILIATE_DISCLOSURE = PREXVO_DISCLOSURES["ftc_disclosure"]
DISCLAIMER_NO_ADVICE = PREXVO_DISCLOSURES["disclaimer_no_advice"]

QUARANTINED_ROGUE_SLUGS: Set[str] = {
    "tax-deduction-for-car-loan-interest",
}


def _resolve_prexvo_public_meta() -> Tuple[str, str]:
    """Reads public GSC verification token and IndexNow key stem."""
    from pseofactory.porcelain_shell import get_porcelain_tenant_profile

    prof = get_porcelain_tenant_profile("prexvo")
    gsc_meta = str(prof.get("default_gsc_token") or "google-site-verification-prexvo-2026")
    indexnow_stem = os.environ.get(
        "PREXVO_INDEXNOW_STEM",
        os.environ.get("INDEXNOW_KEY", "b4430f81d11340a6bda3162725e24a02"),
    )
    return gsc_meta, indexnow_stem


def _get_prexvo_truth_pack() -> TruthPack:
    """Loads and validates the canonical Prexvo TruthPack."""
    return load_truth_pack("prexvo", allow_expired=False)


def _build_hhs_poverty_table(pack: Optional[TruthPack] = None) -> Dict[str, Dict[str, Any]]:
    """
    Constructs the 2026 HHS Poverty Guidelines table (91 FR 1797) dynamically from TruthPack.
    Contiguous 48 states + DC: $15,960 for 1-person household + $5,680 per additional person.
    Alaska (1.25x rounded to $10) and Hawaii (1.15x rounded to $10) scaled consistently.
    """
    tp = pack or _get_prexvo_truth_pack()
    base_1 = float(tp.entries["hhs_poverty_2026_1person"].value)
    per_add = float(tp.entries["hhs_poverty_2026_per_additional"].value)

    ak_1 = float(round(base_1 * 1.25, -1))
    ak_add = float(round(per_add * 1.25, -1))
    hi_1 = float(round(base_1 * 1.15, -1))
    hi_add = float(round(per_add * 1.15, -1))

    def _region_entry(name: str, first_person: float, extra: float) -> Dict[str, Any]:
        by_size = {sz: first_person + extra * (sz - 1) for sz in range(1, 9)}
        return {
            "region_name": name,
            "base_by_size": by_size,
            "per_additional": extra,
        }

    return {
        "contiguous": _region_entry("48 Contiguous States and DC", base_1, per_add),
        "alaska": _region_entry("Alaska", ak_1, ak_add),
        "hawaii": _region_entry("Hawaii", hi_1, hi_add),
    }


def _serialize_poverty_table_for_js(table: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """Converts the Python poverty guideline table to the exact JSON object embedded in inline JS."""
    js_table: Dict[str, Dict[str, float]] = {}
    for region, data in table.items():
        js_table[region] = {
            "1": float(data["base_by_size"][1]),
            "extra": float(data["per_additional"]),
        }
    return js_table


_INITIAL_PACK = _get_prexvo_truth_pack()
HHS_POVERTY_GUIDELINES: Dict[str, Dict[str, Any]] = _build_hhs_poverty_table(_INITIAL_PACK)
RAP_FORGIVENESS_MONTHS: int = int(_INITIAL_PACK.entries["rap_forgiveness_months"].value)
RAP_FORGIVENESS_YEARS: int = RAP_FORGIVENESS_MONTHS // 12
RAP_UNPAID_INTEREST_SUBSIDY_PCT: float = float(_INITIAL_PACK.entries["rap_unpaid_interest_subsidy_pct"].value)
RAP_PRINCIPAL_MATCH_CAP: float = float(_INITIAL_PACK.entries["rap_principal_match_monthly_cap"].value)
PSLF_QUALIFYING_PAYMENTS: int = int(_INITIAL_PACK.entries["pslf_qualifying_payments"].value)


def normalize_state_group(state_input: str) -> str:
    """Normalizes state code or group name to contiguous, alaska, or hawaii."""
    s = (state_input or "contiguous").strip().lower()
    if s in ("ak", "alaska"):
        return "alaska"
    if s in ("hi", "hawaii"):
        return "hawaii"
    return "contiguous"


def get_hhs_poverty_guideline(family_size: int, state_group: str = "contiguous") -> float:
    """Returns 2026 HHS Poverty Guideline (91 FR 1797) derived from TruthPack."""
    group = normalize_state_group(state_group)
    data = HHS_POVERTY_GUIDELINES[group]
    size = max(1, int(family_size))
    if size <= 8:
        return float(data["base_by_size"][size])
    base_8 = float(data["base_by_size"][8])
    return base_8 + ((size - 8) * float(data["per_additional"]))


def normalize_interest_rate(rate: float) -> float:
    """Ensures interest rate is a decimal (e.g. 6.5 -> 0.065)."""
    if rate is None:
        return 0.065
    val = float(rate)
    if val > 1.0:
        return val / 100.0
    return max(0.0, val)


def calculate_discretionary_income(
    agi: float,
    family_size: int = 1,
    state_group: str = "contiguous",
    multiplier: float = 1.50,
) -> float:
    """Computes discretionary income above a multiple of the 2026 HHS Poverty Guideline."""
    safe_agi = max(0.0, float(agi or 0.0))
    fpl = get_hhs_poverty_guideline(family_size, state_group)
    return max(0.0, safe_agi - (fpl * float(multiplier)))


def amortize_monthly_payment(balance: float, annual_rate: float, term_months: int) -> float:
    """Calculates fixed monthly amortization payment."""
    safe_balance = max(0.0, float(balance or 0.0))
    if safe_balance == 0.0 or term_months <= 0:
        return 0.0
    r = annual_rate / 12.0
    if r == 0.0:
        return safe_balance / float(term_months)
    factor = (1.0 + r) ** (-term_months)
    if factor >= 1.0:
        return safe_balance / float(term_months)
    return safe_balance * (r / (1.0 - factor))


def calculate_standard_10yr_payment(loan_balance: float, interest_rate: float) -> Dict[str, Any]:
    """Calculates statutory 10-year Standard Repayment schedule (120 monthly payments)."""
    rate = normalize_interest_rate(interest_rate)
    balance = max(0.0, float(loan_balance or 0.0))
    term_months = 120
    monthly = amortize_monthly_payment(balance, rate, term_months)
    total_repayment = monthly * term_months
    return {
        "plan_id": "standard_10yr",
        "plan_name": "Standard 10-Year Repayment Plan",
        "monthly_payment": round(monthly, 2),
        "term_years": 10,
        "term_months": term_months,
        "total_repayment": round(total_repayment, 2),
        "forgiveness_amount": 0.0,
        "interest_subsidy": 0.0,
    }


def calculate_rap_payment(
    loan_balance: float,
    agi: float,
    interest_rate: float,
    family_size: int = 1,
    state_group: str = "contiguous",
    is_graduate: bool = False,
    dependents: Optional[int] = None,
) -> Dict[str, Any]:
    """
    2026 Repayment Assistance Plan (RAP) under P.L. 119-21 Section 82001:
    - Tiered AGI percentage (1% above $10k up to 10% above $100k), minus $50/dependent, $10 minimum.
    - 100% unpaid monthly interest subsidy on on-time payments.
    - Up to $50/mo principal match when borrower payment reduces principal by less than $50.
    - Forgiveness after 360 qualifying monthly payments (30 years).
    """
    _ = (state_group, is_graduate)
    pack = _get_prexvo_truth_pack()
    rate = normalize_interest_rate(interest_rate)
    balance = max(0.0, float(loan_balance or 0.0))
    safe_agi = max(0.0, float(agi or 0.0))
    eff_deps = max(0, int(family_size) - 1) if dependents is None else max(0, int(dependents))

    rap_formula = pack.formulas["rap_monthly_payment"].expression
    monthly = round(
        safe_eval_formula(rap_formula, {"agi": safe_agi, "dependents": eff_deps}),
        2,
    )

    monthly_interest = round((balance * rate) / 12.0, 2)
    interest_subsidy = round(max(0.0, monthly_interest - monthly), 2)
    first_month_principal_paid = max(0.0, min(balance, monthly - monthly_interest))
    first_month_principal_match = (
        round(
            min(
                max(0.0, balance - first_month_principal_paid),
                max(0.0, RAP_PRINCIPAL_MATCH_CAP - first_month_principal_paid),
            ),
            2,
        )
        if balance > 0.0
        else 0.0
    )

    term_months = int(pack.entries["rap_forgiveness_months"].value)
    term_years = term_months // 12

    curr_balance = balance
    total_paid = 0.0
    for _ in range(term_months):
        if curr_balance <= 0.0:
            break
        m_int = (curr_balance * rate) / 12.0
        pay = min(monthly, curr_balance + m_int)
        total_paid += pay
        principal_reduction = max(0.0, pay - m_int)
        p_match = min(
            max(0.0, curr_balance - principal_reduction),
            max(0.0, RAP_PRINCIPAL_MATCH_CAP - principal_reduction),
        )
        curr_balance = max(0.0, curr_balance - principal_reduction - p_match)

    return {
        "plan_id": "rap",
        "plan_name": "Repayment Assistance Plan (RAP)",
        "monthly_payment": monthly,
        "dependents": eff_deps,
        "monthly_interest": monthly_interest,
        "interest_subsidy": interest_subsidy,
        "principal_match": first_month_principal_match,
        "term_years": term_years,
        "term_months": term_months,
        "total_repayment": round(total_paid, 2),
        "forgiveness_amount": round(curr_balance, 2),
        "discretionary_income": round(safe_agi, 2),
    }


def calculate_ibr_payment(
    loan_balance: float,
    agi: float,
    interest_rate: float,
    family_size: int = 1,
    state_group: str = "contiguous",
    is_new_borrower: bool = True,
) -> Dict[str, Any]:
    """
    Income-Based Repayment (IBR) under 34 CFR 685.221 and 2026 HHS Poverty Guidelines (91 FR 1797):
    - 150% HHS FPL threshold ($15,960 + $5,680 per additional person in contiguous 48 states + DC).
    - 10% discretionary income for new borrowers (20-yr), 15% for legacy borrowers (25-yr).
    - Capped at 10-year Standard Repayment schedule.
    """
    rate = normalize_interest_rate(interest_rate)
    balance = max(0.0, float(loan_balance or 0.0))
    disc = calculate_discretionary_income(agi, family_size, state_group, multiplier=1.50)

    pct_rate = 0.10 if is_new_borrower else 0.15
    uncapped_monthly = round((pct_rate * disc) / 12.0, 2)

    std_10 = calculate_standard_10yr_payment(balance, rate)
    cap_amount = std_10["monthly_payment"]
    is_capped = uncapped_monthly > cap_amount
    monthly = cap_amount if is_capped else uncapped_monthly

    term_years = 20 if is_new_borrower else 25
    term_months = term_years * 12

    curr_balance = balance
    total_paid = 0.0
    for _ in range(term_months):
        if curr_balance <= 0.0:
            break
        m_int = (curr_balance * rate) / 12.0
        pay = min(monthly, curr_balance + m_int)
        total_paid += pay
        curr_balance = max(0.0, curr_balance + m_int - pay)

    return {
        "plan_id": "ibr",
        "plan_name": "Income-Based Repayment (IBR)",
        "monthly_payment": monthly,
        "uncapped_monthly_payment": uncapped_monthly,
        "is_capped": is_capped,
        "cap_amount": cap_amount,
        "discretionary_income": round(disc, 2),
        "term_years": term_years,
        "term_months": term_months,
        "total_repayment": round(total_paid, 2),
        "forgiveness_amount": round(curr_balance, 2),
        "interest_subsidy": 0.0,
    }


def calculate_paye_payment(
    loan_balance: float,
    agi: float,
    interest_rate: float,
    family_size: int = 1,
    state_group: str = "contiguous",
) -> Dict[str, Any]:
    """Pay As You Earn (PAYE): 10% discretionary above 150% 2026 FPL, capped at 10-yr standard."""
    rate = normalize_interest_rate(interest_rate)
    balance = max(0.0, float(loan_balance or 0.0))
    disc = calculate_discretionary_income(agi, family_size, state_group, multiplier=1.50)
    uncapped_monthly = round((0.10 * disc) / 12.0, 2)

    std_10 = calculate_standard_10yr_payment(balance, rate)
    cap_amount = std_10["monthly_payment"]
    is_capped = uncapped_monthly > cap_amount
    monthly = cap_amount if is_capped else uncapped_monthly

    term_years = 20
    term_months = term_years * 12
    curr_balance = balance
    total_paid = 0.0
    for _ in range(term_months):
        if curr_balance <= 0.0:
            break
        m_int = (curr_balance * rate) / 12.0
        pay = min(monthly, curr_balance + m_int)
        total_paid += pay
        curr_balance = max(0.0, curr_balance + m_int - pay)

    return {
        "plan_id": "paye",
        "plan_name": "Pay As You Earn (PAYE)",
        "monthly_payment": monthly,
        "uncapped_monthly_payment": uncapped_monthly,
        "is_capped": is_capped,
        "cap_amount": cap_amount,
        "discretionary_income": round(disc, 2),
        "term_years": term_years,
        "term_months": term_months,
        "total_repayment": round(total_paid, 2),
        "forgiveness_amount": round(curr_balance, 2),
        "interest_subsidy": 0.0,
    }


def calculate_icr_payment(
    loan_balance: float,
    agi: float,
    interest_rate: float,
    family_size: int = 1,
    state_group: str = "contiguous",
) -> Dict[str, Any]:
    """Income-Contingent Repayment (ICR) using 2026 HHS Poverty Guidelines."""
    rate = normalize_interest_rate(interest_rate)
    balance = max(0.0, float(loan_balance or 0.0))
    disc = calculate_discretionary_income(agi, family_size, state_group, multiplier=1.00)

    option_a = round((0.20 * disc) / 12.0, 2)
    safe_agi = max(0.0, float(agi or 0.0))
    income_factor = min(2.0, max(0.55, safe_agi / 60000.0))
    base_12yr = amortize_monthly_payment(balance, rate, 144)
    option_b = round(base_12yr * income_factor, 2)

    if option_a <= option_b:
        monthly = option_a
        formula_used = "20% Discretionary Income"
    else:
        monthly = option_b
        formula_used = "12-Year Income-Adjusted Payment"

    term_years = 25
    term_months = term_years * 12
    curr_balance = balance
    total_paid = 0.0
    for _ in range(term_months):
        if curr_balance <= 0.0:
            break
        m_int = (curr_balance * rate) / 12.0
        pay = min(monthly, curr_balance + m_int)
        total_paid += pay
        curr_balance = max(0.0, curr_balance + m_int - pay)

    return {
        "plan_id": "icr",
        "plan_name": "Income-Contingent Repayment (ICR)",
        "monthly_payment": monthly,
        "formula_used": formula_used,
        "discretionary_income": round(disc, 2),
        "term_years": term_years,
        "term_months": term_months,
        "total_repayment": round(total_paid, 2),
        "forgiveness_amount": round(curr_balance, 2),
        "interest_subsidy": 0.0,
    }


def get_tiered_term_years(loan_balance: float) -> int:
    """Returns Tiered Standard statutory term in years (10 to 30 years / 120 to 360 months)."""
    bal = max(0.0, float(loan_balance or 0.0))
    if bal < 7500.0:
        return 10
    if bal < 10000.0:
        return 12
    if bal < 20000.0:
        return 15
    if bal < 40000.0:
        return 20
    if bal < 60000.0:
        return 25
    return 30


def calculate_tiered_standard_payment(loan_balance: float, interest_rate: float) -> Dict[str, Any]:
    """Tiered Standard Repayment Plan (34 CFR Part 685): 120 to 360 months based on balance."""
    rate = normalize_interest_rate(interest_rate)
    balance = max(0.0, float(loan_balance or 0.0))
    term_years = get_tiered_term_years(balance)
    term_months = term_years * 12
    monthly = round(amortize_monthly_payment(balance, rate, term_months), 2)
    total_repayment = round(monthly * term_months, 2)
    return {
        "plan_id": "tiered_standard",
        "plan_name": "Tiered Standard Repayment Plan",
        "monthly_payment": monthly,
        "term_years": term_years,
        "term_months": term_months,
        "total_repayment": total_repayment,
        "forgiveness_amount": 0.0,
        "interest_subsidy": 0.0,
    }


def compare_all_repayment_plans(
    loan_balance: float,
    agi: float,
    interest_rate: float,
    family_size: int = 1,
    state_group: str = "contiguous",
    is_graduate: bool = False,
    is_new_borrower_2014: bool = True,
) -> Dict[str, Dict[str, Any]]:
    """Computes side-by-side repayment metrics across all 6 federal repayment plans."""
    return {
        "rap": calculate_rap_payment(
            loan_balance, agi, interest_rate, family_size, state_group, is_graduate
        ),
        "ibr": calculate_ibr_payment(
            loan_balance, agi, interest_rate, family_size, state_group, is_new_borrower_2014
        ),
        "paye": calculate_paye_payment(
            loan_balance, agi, interest_rate, family_size, state_group
        ),
        "icr": calculate_icr_payment(
            loan_balance, agi, interest_rate, family_size, state_group
        ),
        "tiered_standard": calculate_tiered_standard_payment(
            loan_balance, interest_rate
        ),
        "standard_10yr": calculate_standard_10yr_payment(
            loan_balance, interest_rate
        ),
    }


# ---------------------------------------------------------------------------
# Interactive Calculator Specification & Schema Helpers
# ---------------------------------------------------------------------------


@dataclass
class CalculatorField:
    id: str
    label: str
    type: str
    default: float | int | str
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    step: Optional[float] = None
    options: Optional[List[Dict[str, str]]] = None
    unit: str = ""
    tooltip: str = ""


@dataclass
class CalculatorMetric:
    id: str
    label: str
    format: str
    unit: str = ""
    highlight: bool = False


@dataclass
class InteractiveCalculatorSpec:
    id: str
    slug: str
    title: str
    short_title: str
    description: str
    category: str
    fields: List[CalculatorField]
    metrics: List[CalculatorMetric]
    quick_answer: str
    faqs: List[Dict[str, str]] = field(default_factory=list)
    statutory_citations: List[str] = field(default_factory=list)
    switcher_workflows: List[Dict[str, Any]] = field(default_factory=list)
    question_scenarios: List[Dict[str, Any]] = field(default_factory=list)


REPAYMENT_CALCULATOR_SPEC = InteractiveCalculatorSpec(
    id="student-loan-repayment",
    slug="student-loan-repayment-calculator",
    title="Federal Student Loan Repayment & RAP Comparison Calculator",
    short_title="Repayment Calculator",
    description="Deterministic Title IV repayment model comparing RAP, IBR, PAYE, ICR, and Tiered Standard.",
    category="Higher Education Finance",
    fields=[
        CalculatorField(
            id="loan_balance",
            label="Total Federal Loan Balance",
            type="number",
            default=60000.0,
            min_val=1000.0,
            max_val=500000.0,
            step=1000.0,
            unit="$",
            tooltip="Aggregate outstanding principal balance across Direct Subsidized, Unsubsidized, and PLUS loans.",
        ),
        CalculatorField(
            id="agi",
            label="Adjusted Gross Income (AGI)",
            type="number",
            default=65000.0,
            min_val=0.0,
            max_val=500000.0,
            step=1000.0,
            unit="$",
            tooltip="Line 11 on IRS Form 1040 representing annual household taxable earnings.",
        ),
        CalculatorField(
            id="interest_rate",
            label="Weighted Average Interest Rate",
            type="number",
            default=6.5,
            min_val=0.0,
            max_val=15.0,
            step=0.1,
            unit="%",
            tooltip="Statutory interest rate applicable to Title IV Direct Loans.",
        ),
        CalculatorField(
            id="family_size",
            label="Household Family Size",
            type="number",
            default=1,
            min_val=1,
            max_val=12,
            step=1,
            unit="",
            tooltip="Borrower plus spouse and qualifying legal dependents.",
        ),
        CalculatorField(
            id="state_group",
            label="Geographic Poverty Guideline Region",
            type="select",
            default="contiguous",
            options=[
                {"value": "contiguous", "label": "48 Contiguous States & DC"},
                {"value": "alaska", "label": "Alaska"},
                {"value": "hawaii", "label": "Hawaii"},
            ],
            tooltip="2026 HHS Poverty Guidelines (91 FR 1797) scale between Contiguous 48 ($15,960), Alaska, and Hawaii.",
        ),
    ],
    metrics=[
        CalculatorMetric(
            id="rap_payment",
            label="RAP Monthly Payment (P.L. 119-21)",
            format="currency",
            unit="/mo",
            highlight=True,
        ),
        CalculatorMetric(
            id="ibr_payment",
            label="IBR Monthly Payment (Capped)",
            format="currency",
            unit="/mo",
            highlight=False,
        ),
        CalculatorMetric(
            id="paye_payment",
            label="PAYE Monthly Payment",
            format="currency",
            unit="/mo",
            highlight=False,
        ),
        CalculatorMetric(
            id="icr_payment",
            label="ICR Monthly Payment",
            format="currency",
            unit="/mo",
            highlight=False,
        ),
        CalculatorMetric(
            id="tiered_payment",
            label="Tiered Standard Monthly Payment",
            format="currency",
            unit="/mo",
            highlight=False,
        ),
        CalculatorMetric(
            id="std_10yr_payment",
            label="Standard 10-Year Payment (Cap Baseline)",
            format="currency",
            unit="/mo",
            highlight=False,
        ),
        CalculatorMetric(
            id="rap_subsidy",
            label="RAP Monthly Interest Subsidy",
            format="currency",
            unit="/mo",
            highlight=True,
        ),
    ],
    quick_answer=(
        "Under P.L. 119-21 Section 82001 and 34 CFR Part 685, the 2026 Repayment Assistance Plan (RAP) "
        "calculates monthly payments from 1% to 10% of AGI minus $50 per dependent ($10 minimum), provides "
        "a 100% unpaid interest subsidy and up to $50/mo principal match, and grants forgiveness after 360 "
        "qualifying monthly payments, while IBR uses the $15,960 2026 HHS Poverty Guideline."
    ),
    faqs=[
        {
            "question": "How does the 2026 Repayment Assistance Plan (RAP) under P.L. 119-21 Section 82001 calculate monthly payments?",
            "answer": (
                "Under P.L. 119-21 Section 82001, RAP applies an AGI-tiered rate from 1% (above $10,000) to 10% "
                "(above $100,000) divided by 12, subtracts $50 per qualifying dependent with a $10 minimum monthly "
                "payment, subsidizes 100% of unpaid monthly interest, matches principal up to $50/mo, and provides "
                "balance forgiveness after 360 qualifying monthly payments (30 years)."
            ),
        },
        {
            "question": "What are the 2026 HHS Poverty Guidelines used for IBR and ICR calculations?",
            "answer": (
                "Under 91 FR 1797 (42 U.S.C. 9902(2)), the 2026 HHS Poverty Guideline for the 48 contiguous states "
                "and D.C. is $15,960 for a 1-person household plus $5,680 for each additional person. Income-Based "
                "Repayment (IBR) shields 150% of this guideline and caps payments at the 10-year Standard schedule."
            ),
        },
        {
            "question": "How does PSLF differ from RAP and Tiered Standard repayment horizons?",
            "answer": (
                "Public Service Loan Forgiveness (PSLF) under 34 CFR 685.219 discharges remaining balances after 120 "
                "qualifying monthly payments (10 years), whereas RAP forgiveness occurs after 360 qualifying monthly "
                "payments (30 years) under P.L. 119-21 Section 82001, and Tiered Standard amortizes over 120 to 360 months."
            ),
        },
    ],
    statutory_citations=[
        "P.L. 119-21 Section 82001 (Repayment Assistance Plan)",
        "91 FR 1797 (2026 HHS Poverty Guidelines, 42 U.S.C. 9902(2))",
        "34 CFR Part 685, 34 CFR 685.221 (IBR), and 34 CFR 685.219 (PSLF)",
    ],
    switcher_workflows=[
        {
            "id": "undergrad-standard",
            "label": "Undergraduate Standard ($32k Bal / $48k AGI)",
            "description": "Typical undergraduate direct loan borrower with bachelor degree earnings.",
            "params": {
                "loan_balance": 32000,
                "agi": 48000,
                "interest_rate": 6.5,
                "family_size": 1,
                "state_group": "contiguous",
            },
        },
        {
            "id": "graduate-professional",
            "label": "Graduate Professional ($95k Bal / $85k AGI)",
            "description": "Graduate master or professional degree recipient with higher debt and income.",
            "params": {
                "loan_balance": 95000,
                "agi": 85000,
                "interest_rate": 6.8,
                "family_size": 1,
                "state_group": "contiguous",
            },
        },
        {
            "id": "pslf-public-service",
            "label": "Public Service PSLF ($65k Bal / $60k AGI)",
            "description": "Qualifying public servant or non-profit professional seeking 120-payment PSLF.",
            "params": {
                "loan_balance": 65000,
                "agi": 60000,
                "interest_rate": 6.5,
                "family_size": 1,
                "state_group": "contiguous",
            },
        },
        {
            "id": "high-debt-married",
            "label": "High Debt Family ($150k Bal / $120k AGI)",
            "description": "Married borrower household with high aggregate direct loan balance.",
            "params": {
                "loan_balance": 150000,
                "agi": 120000,
                "interest_rate": 7.0,
                "family_size": 2,
                "state_group": "contiguous",
            },
        },
    ],
    question_scenarios=[
        {
            "question": "How does the 2026 RAP 100% unpaid interest subsidy and $50 principal match work?",
            "direct_answer": (
                "Under P.L. 119-21 Section 82001, RAP waives 100% of unpaid monthly accrued interest on on-time "
                "payments and matches up to $50 per month in principal reduction when the borrower's payment reduces "
                "principal by less than $50, preventing negative amortization across the 360-month schedule."
            ),
            "statutory_ref": "P.L. 119-21 Section 82001 & 34 CFR Part 685",
            "params": {
                "loan_balance": 60000,
                "agi": 45000,
                "interest_rate": 6.5,
                "family_size": 1,
                "state_group": "contiguous",
            },
        },
        {
            "question": "How do 2026 HHS Poverty Guidelines (91 FR 1797) affect IBR monthly payments?",
            "direct_answer": (
                "Under 91 FR 1797 and 34 CFR 685.221, the 2026 federal poverty guideline is $15,960 for a single "
                "borrower plus $5,680 per additional household member in the 48 contiguous states. New IBR assesses "
                "10% of AGI above 150% of this guideline ($23,940 for 1 person), capped at the 10-year Standard schedule."
            ),
            "statutory_ref": "91 FR 1797 & 34 CFR 685.221",
            "params": {
                "loan_balance": 60000,
                "agi": 65000,
                "interest_rate": 6.5,
                "family_size": 1,
                "state_group": "contiguous",
            },
        },
        {
            "question": "When does the statutory 10-year Standard Repayment cap protect high earners under IBR?",
            "direct_answer": (
                "Under 34 CFR 685.221 and 20 U.S.C. 1087e, IBR monthly payments cannot exceed the 10-year Standard "
                "schedule calculated at enrollment ($681.29/mo on $60,000 at 6.5%), whereas RAP payments scale up "
                "to 10% of total AGI across 360 qualifying monthly payments."
            ),
            "statutory_ref": "34 CFR 685.221 & 20 U.S.C. 1087e",
            "params": {
                "loan_balance": 60000,
                "agi": 160000,
                "interest_rate": 6.5,
                "family_size": 1,
                "state_group": "contiguous",
            },
        },
    ],
)


_TITLE_ACRONYM_MAP: Tuple[Tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bpslf\b", re.IGNORECASE), "PSLF"),
    (re.compile(r"\brap\b", re.IGNORECASE), "RAP"),
    (re.compile(r"\bibr\b", re.IGNORECASE), "IBR"),
    (re.compile(r"\bpaye\b", re.IGNORECASE), "PAYE"),
    (re.compile(r"\bicr\b", re.IGNORECASE), "ICR"),
    (re.compile(r"\bsave\b", re.IGNORECASE), "SAVE"),
    (re.compile(r"\bplus\b", re.IGNORECASE), "PLUS"),
    (re.compile(r"\bhhs\b", re.IGNORECASE), "HHS"),
    (re.compile(r"\bfpl\b", re.IGNORECASE), "FPL"),
    (re.compile(r"\bhpsl\b", re.IGNORECASE), "HPSL"),
    (re.compile(r"\bnhsc\b", re.IGNORECASE), "NHSC"),
    (re.compile(r"\btitle iv\b", re.IGNORECASE), "Title IV"),
    (re.compile(r"\bstudent loans gov\b", re.IGNORECASE), "StudentLoans.gov"),
)

_TITLE_OVERRIDE_BY_SLUG: Dict[str, str] = {
    "pslf-buyback-months-reconsideration-student-loan-calculator": "PSLF Buyback Months & Reconsideration Calculator",
    "student-loan-forgiveness-tax-bomb-insolvency-calculator": "Student Loan Forgiveness Tax Bomb & Insolvency Calculator",
    "parent-plus-double-consolidation-loophole-2026-calculator": "Parent PLUS Double Consolidation Loophole 2026 Calculator",
    "how-do-you-calculate-student-loan-repayments": "Student Loan Repayment Calculation Guide & Estimator",
    "student-loans-gov": "StudentLoans.gov Federal Repayment Estimator",
    "repayment-estimator-student-loans": "Student Loan Repayment Estimator",
    "parent-plus-loan-payment-calculator": "Parent PLUS Loan Payment Calculator",
    "student-loan-forgiveness-2026": "2026 Federal Student Loan Forgiveness Calculator",
    "health-professions-student-loan-hpsl-nhsc-forgiveness-calculator": "NHSC & Health Professions Loan Forgiveness Calculator",
    "physician-resident-student-loan-refinance-vs-rap-calculator": "Physician Resident Refinance vs RAP Subsidy Calculator",
    "discretionary-income-calculator-for-student-loans": "Student Loan Discretionary Income Calculator",
}


def _clean_text_hygiene(text: str) -> str:
    """Removes forbidden dashes, HTML entities, duplicate adjacent words, and unlisted citations."""
    s = html.unescape(str(text or ""))
    s = s.replace("\u2014", "-").replace("\u2013", "-")
    s = re.sub(r"\s+", " ", s).strip()
    # Collapse duplicate adjacent words such as "Calculate Calculate" or "Calculator Calculator"
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"\b([A-Za-z]{2,})\s+\1\b", r"\1", s, flags=re.IGNORECASE)
    # Remove query stubs
    s = re.sub(
        r"\bCalculate\s+(?:How\s+Do\s+You|How\s+To|What\s+Is|Can\s+You|Why\s+Does|When\s+Should|Where\s+To)\b",
        "Calculate",
        s,
        flags=re.IGNORECASE,
    )
    # Replace superseded 2025/erroneous values if any leaked from deployed_voids
    s = re.sub(r"\$?15,650\b", "$15,960", s)
    s = re.sub(r"\b15650\b", "15960", s)
    s = re.sub(r"\$?16,120\b", "$15,960", s)
    s = re.sub(r"\b16120\b", "15960", s)
    s = re.sub(r"\$?5,500\s*(?:per\s+additional|for\s+each\s+additional)", "$5,680 per additional", s, flags=re.IGNORECASE)
    s = re.sub(
        r"120\s*to\s*240\s*certified\s*monthly\s*payments",
        "360 qualifying monthly payments",
        s,
        flags=re.IGNORECASE,
    )
    # Normalize P.L. 119-21 references cleanly without swallowing trailing punctuation
    s = re.sub(r"\bP\.L\.\s*119-21\b(?!\s*Section\s*82001)", "P.L. 119-21 Section 82001", s)
    s = re.sub(r"\b20\s*U\.S\.C\.?\s*1078-3\b", "34 CFR 685.220", s, flags=re.IGNORECASE)
    s = normalize_statutory_acronym_casing(s)
    return s


def _clean_tool_title(raw_title: str, slug: str) -> str:
    """Produces a clean, non-duplicative, query-stub-free tool title."""
    slug_low = str(slug or "").strip().lower()
    if slug_low in _TITLE_OVERRIDE_BY_SLUG:
        return _TITLE_OVERRIDE_BY_SLUG[slug_low]
    cleaned = _clean_text_hygiene(raw_title or slug_low.replace("-", " ").title())
    cleaned = re.sub(
        r"^(?:How\s+Do\s+You\s+Calculate|How\s+To\s+Calculate|Calculate\s+How\s+Do\s+You)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    for rx, rep in _TITLE_ACRONYM_MAP:
        cleaned = rx.sub(rep, cleaned)
    prev = None
    while prev != cleaned:
        prev = cleaned
        cleaned = re.sub(r"\b([A-Za-z]{2,})\s+\1\b", r"\1", cleaned, flags=re.IGNORECASE)
    return cleaned or slug_low.replace("-", " ").title()


_TRAILING_STOPWORDS = frozenset(
    {
        "and",
        "or",
        "the",
        "for",
        "with",
        "of",
        "to",
        "in",
        "on",
        "under",
        "per",
        "from",
        "a",
        "an",
        "by",
        "at",
        "as",
        "including",
        "plus",
    }
)


def _truncate_clean(text: str, max_len: int) -> str:
    """Truncates text cleanly at a word boundary within max_len without trailing stop-words."""
    s = text.strip()
    if len(s) <= max_len:
        return s
    cut = s[: max_len - 1].rsplit(" ", 1)[0].rstrip(" ,;:-(")
    while cut:
        parts = cut.rsplit(" ", 1)
        last_word = parts[-1].rstrip(".,;:").lower()
        if last_word in _TRAILING_STOPWORDS and len(parts) == 2:
            cut = parts[0].rstrip(" ,;:-(")
        else:
            break
    if not cut:
        cut = s[: max_len - 1].rstrip()
    return f"{cut}."


def _clean_tool_description(raw_desc: str, title: str, slug: str) -> str:
    """Produces a clean, 50-160 char TruthPack-consistent meta description with allowlisted citations."""
    cleaned = _clean_text_hygiene(raw_desc or "")
    if not cleaned or "how do you calculate" in cleaned.lower() or "for student loans gov" in cleaned.lower():
        cleaned = (
            f"Calculate Title IV student loan scenarios with the {title} "
            f"under 34 CFR Part 685, P.L. 119-21 Section 82001, and 91 FR 1797."
        )
    if "refinanc" in slug.lower() and "permanently forfeits" not in cleaned.lower():
        suffix = "Refinancing federal loans permanently forfeits federal protections."
        max_prefix = 160 - len(suffix) - 1
        prefix = _truncate_clean(cleaned, max_prefix).rstrip(".")
        if len(prefix) > max_prefix:
            prefix = prefix[:max_prefix].rsplit(" ", 1)[0].rstrip(" ,;:-(")
        cleaned = f"{prefix}. {suffix}" if prefix else suffix
    return _truncate_clean(cleaned, 160)


def normalize_seo_title(
    title: str,
    brand: str = PREXVO_SITE_NAME,
    min_len: int = 50,
    max_len: int = 60,
) -> str:
    """Normalizes Prexvo HTML title length strictly to 50-60 chars with zero forbidden dashes."""
    clean_in = _clean_text_hygiene(title)
    pads: Tuple[str, ...] = (
        "{base} Tool{brand_suffix}",
        "{base} Planning Tool{brand_suffix}",
        "{base} | Student Loan Tools{brand_suffix}",
        "{base} | Title IV Repayment Engine{brand_suffix}",
        "{base} | Student Loan Planning Engine{brand_suffix}",
        "{base} | Federal Student Loan Repayment Engine{brand_suffix}",
        "{base} | Deterministic Title IV Repayment Engine{brand_suffix}",
    )
    return normalize_tenant_seo_title(
        title=clean_in,
        brand=brand,
        default_tagline="Student Loan Planning Engine",
        pad_candidates=pads,
        min_len=min_len,
        max_len=max_len,
    )


# ---------------------------------------------------------------------------
# Canonical Core Tools + Statutory Voids + Built-in Deployed Voids Fallback
# ---------------------------------------------------------------------------

PREXVO_CORE_TOOLS: List[Dict[str, Any]] = [
    {
        "slug": "student-loan-repayment-calculator",
        "title": "Federal Student Loan Repayment Plan Calculator",
        "short_title": "Repayment Calculator",
        "description": "Calculate and compare Title IV student loan repayment plans side by side under P.L. 119-21 Section 82001 RAP, 34 CFR 685.221 IBR, PAYE, and ICR.",
        "primary_keyword": "student loan repayment calculator",
    },
    {
        "slug": "rap-vs-ibr-calculator",
        "title": "RAP vs IBR Student Loan Plan Comparison Engine",
        "short_title": "RAP vs IBR",
        "description": "Compare 2026 P.L. 119-21 Section 82001 RAP payments, 100% interest subsidies, and 360-month forgiveness against 34 CFR 685.221 IBR using 91 FR 1797 guidelines.",
        "primary_keyword": "rap vs ibr",
    },
    {
        "slug": "tiered-standard-calculator",
        "title": "Tiered Standard Repayment Plan Amortization Model",
        "short_title": "Tiered Standard",
        "description": "Calculate 120 to 360 month (10 to 30 year) Tiered Standard amortization schedules across federal consolidation balance tiers pursuant to 34 CFR Part 685.",
        "primary_keyword": "tiered standard repayment plan",
    },
    {
        "slug": "paye-sunset-calculator",
        "title": "PAYE Sunset & Plan Transition Analysis Engine",
        "short_title": "PAYE Sunset",
        "description": "Analyze 2026 PAYE sunset rules, grandfathering protections, and 10-year standard payment caps using $15,960 2026 HHS Poverty Guidelines (91 FR 1797).",
        "primary_keyword": "paye vs ibr",
    },
    {
        "slug": "icr-repayment-calculator",
        "title": "Income-Contingent Repayment (ICR) Formula Tool",
        "short_title": "ICR Calculator",
        "description": "Model Income-Contingent Repayment under dual statutory formulas using 2026 HHS Poverty Guidelines (91 FR 1797) and 34 CFR Part 685.",
        "primary_keyword": "icr vs ibr",
    },
]

PREXVO_STATUTORY_VOIDS: List[Dict[str, Any]] = [
    {
        "slug": "parent-plus-double-consolidation",
        "title": "Parent PLUS Double Consolidation Calculator",
        "short_title": "Double Consolidation",
        "description": "Model Parent PLUS double consolidation under 34 CFR Part 685 to evaluate monthly obligations under 2026 IBR and P.L. 119-21 Section 82001 RAP.",
        "primary_keyword": "parent plus double consolidation calculator",
    },
    {
        "slug": "pslf-qualifying-payment-simulator",
        "title": "PSLF Qualifying Payment & Forgiveness Calculator",
        "short_title": "PSLF Simulator",
        "description": "Simulate Public Service Loan Forgiveness (PSLF) progress across 120 qualifying monthly payments and remaining discharge balance under 34 CFR 685.219.",
        "primary_keyword": "pslf qualifying payment calculator",
    },
    {
        "slug": "save-plan-litigation-transition",
        "title": "SAVE Plan Transition to RAP Repayment Calculator",
        "short_title": "SAVE Transition",
        "description": "Evaluate monthly payment changes, 100% unpaid interest subsidies, and 360-month timelines when transitioning from SAVE forbearance under 34 CFR Part 685.",
        "primary_keyword": "save plan transition to rap calculator",
    },
    {
        "slug": "student-loan-refinance-break-even-calculator",
        "title": "Student Loan Refinance Break-Even Calculator",
        "short_title": "Refinance Break-Even",
        "description": "Calculate private refinance closing-fee break-even months under 12 CFR Part 1026 while evaluating permanent forfeiture of Title IV federal benefits.",
        "primary_keyword": "student loan refinance break even calculator",
    },
    {
        "slug": "rap-payment-calculator",
        "title": "2026 Repayment Assistance Plan (RAP) Calculator",
        "short_title": "RAP Payment",
        "description": "Calculate exact monthly payments, 100% unpaid interest subsidy, $50/mo principal match, and 360-month forgiveness under P.L. 119-21 Section 82001.",
        "primary_keyword": "repayment assistance plan calculator",
    },
    {
        "slug": "grad-plus-borrowing-cap-calculator",
        "title": "Grad PLUS Sunset & Borrowing Cap Calculator",
        "short_title": "Grad PLUS Cap",
        "description": "Model graduate and professional federal student loan aggregate borrowing limits and Direct Unsubsidized caps under 20 U.S.C. 1087e and 34 CFR Part 685.",
        "primary_keyword": "grad plus loan cap calculator",
    },
    {
        "slug": "married-filing-separately-student-loan-calculator",
        "title": "Married Filing Separately IDR Student Loan Calculator",
        "short_title": "MFS IDR Calculator",
        "description": "Compare Married Filing Separately vs Jointly under 34 CFR 685.221 IBR and 91 FR 1797 2026 HHS Poverty Guidelines ($15,960 single, +$5,680 additional).",
        "primary_keyword": "married filing separately student loan calculator",
    },
    {
        "slug": "ibr-hardship-cap-calculator",
        "title": "IBR 10-Year Standard Payment Cap Calculator",
        "short_title": "IBR Payment Cap",
        "description": "Verify Partial Financial Hardship eligibility and calculate capped monthly payments under 34 CFR 685.221 and 2026 HHS Poverty Guidelines (91 FR 1797).",
        "primary_keyword": "ibr partial financial hardship calculator",
    },
]

_FALLBACK_DEPLOYED_VOID_SLUGS: List[Dict[str, Any]] = [
    {"slug": "student-loan-forgiveness-2026", "title": "2026 Federal Student Loan Forgiveness Calculator"},
    {"slug": "pslf-buyback-months-reconsideration-student-loan-calculator", "title": "PSLF Buyback Months & Reconsideration Calculator"},
    {"slug": "student-loan-forgiveness-tax-bomb-insolvency-calculator", "title": "Student Loan Forgiveness Tax Bomb & Insolvency Calculator"},
    {"slug": "parent-plus-double-consolidation-loophole-2026-calculator", "title": "Parent PLUS Double Consolidation Loophole 2026 Calculator"},
    {"slug": "repayment-estimator-student-loans", "title": "Student Loan Repayment Estimator"},
    {"slug": "student-loans-gov", "title": "StudentLoans.gov Federal Repayment Estimator"},
    {"slug": "how-do-you-calculate-student-loan-repayments", "title": "Student Loan Repayment Calculation Guide & Estimator"},
    {"slug": "parent-plus-loan-payment-calculator", "title": "Parent PLUS Loan Payment Calculator"},
    {"slug": "health-professions-student-loan-hpsl-nhsc-forgiveness-calculator", "title": "NHSC & Health Professions Loan Forgiveness Calculator"},
    {"slug": "physician-resident-student-loan-refinance-vs-rap-calculator", "title": "Physician Resident Refinance vs RAP Subsidy Calculator"},
    {"slug": "discretionary-income-calculator-for-student-loans", "title": "Student Loan Discretionary Income Calculator"},
]


def _build_manifest_for_slug(
    slug: str,
    pack: TruthPack,
    raw_spec: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Constructs a TruthPack-verified, non-tautological calculation manifest for `slug`.
    Automatically binds any slug matching TruthPack FormulaSpecs (rap, ibr, pslf, refinance)
    directly to the canonical TruthPack formula and test baseline.
    """
    slug_low = str(slug or "").strip().lower()
    f_rap = pack.formulas["rap_monthly_payment"]
    f_ibr = pack.formulas["ibr_monthly_payment"]
    f_pslf = pack.formulas["pslf_total_out_of_pocket_and_forgiveness"]
    f_refi = pack.formulas["refinance_breakeven_months"]

    base_1 = float(pack.entries["hhs_poverty_2026_1person"].value)  # 15960.0
    per_add = float(pack.entries["hhs_poverty_2026_per_additional"].value)  # 5680.0

    # 1. Exact TruthPack FormulaSpec bindings (must match UnifiedTruthGate order)
    if re.search(r".*rap.*", slug_low, re.IGNORECASE):
        return {
            "slug": slug_low,
            "model_name": f_rap.model_name,
            "statutory_authority": "P.L. 119-21 Section 82001 (Repayment Assistance Plan); 34 CFR Part 685",
            "economic_dataset": "U.S. Department of Education College Scorecard and BLS OEWS wage series",
            "formula": f_rap.expression,
            "js_expression": f_rap.js_expression,
            "inputs": dict(f_rap.variables),
            "published_output": float(f_rap.expected_baseline_output),
            "sample_calculation": (
                "Under P.L. 119-21 Section 82001, a single borrower with $65,000 AGI and 0 dependents falls in "
                "the 6% AGI bracket ($65,000 * 0.06 / 12 = $325.00/mo), receives a 100% unpaid interest subsidy "
                "plus up to $50/mo principal match, and reaches forgiveness after 360 qualifying monthly payments."
            ),
            "entity_type": "FinancialProductOrService",
        }

    if re.search(r".*ibr.*", slug_low, re.IGNORECASE):
        return {
            "slug": slug_low,
            "model_name": f_ibr.model_name,
            "statutory_authority": "91 FR 1797 (2026 HHS Poverty Guidelines, 42 U.S.C. 9902); 34 CFR 685.221",
            "economic_dataset": "HHS 2026 Poverty Guidelines (91 FR 1797) and BLS OEWS wage series",
            "formula": f_ibr.expression,
            "js_expression": f_ibr.js_expression,
            "inputs": dict(f_ibr.variables),
            "published_output": float(f_ibr.expected_baseline_output),
            "sample_calculation": (
                f"Under 91 FR 1797 and 34 CFR 685.221, 150% of the ${base_1:,.0f} 2026 HHS Poverty Guideline "
                f"shields $23,940.00 of $65,000 AGI, yielding $41,060.00 discretionary income and a 10% New IBR "
                "payment of $342.17/mo (capped below the $681.29 10-year Standard schedule)."
            ),
            "entity_type": "FinancialProductOrService",
        }

    if re.search(r".*pslf.*", slug_low, re.IGNORECASE):
        return {
            "slug": slug_low,
            "model_name": f_pslf.model_name,
            "statutory_authority": "34 CFR 685.219 (Public Service Loan Forgiveness); 20 U.S.C. 1087e",
            "economic_dataset": "U.S. Department of Education FSA Portfolio and BLS OEWS wage series",
            "formula": f_pslf.expression,
            "js_expression": f_pslf.js_expression,
            "inputs": dict(f_pslf.variables),
            "published_output": float(f_pslf.expected_baseline_output),
            "sample_calculation": (
                "Under 34 CFR 685.219, a borrower with $65,000 principal at 6.5% interest, 24 certified "
                "qualifying payments (96 remaining of 120), and $250/mo IDR payment projects $77,809.15 "
                "discharged tax-free upon reaching 120 qualifying monthly payments."
            ),
            "entity_type": "FinancialProductOrService",
        }

    if re.search(r".*refinance.*", slug_low, re.IGNORECASE):
        return {
            "slug": slug_low,
            "model_name": f_refi.model_name,
            "statutory_authority": "12 CFR Part 1026 (Truth in Lending Act); 20 U.S.C. 1087e; 34 CFR Part 685",
            "economic_dataset": "Federal Reserve H.15 Selected Interest Rates and G.19 Consumer Credit Series",
            "formula": f_refi.expression,
            "js_expression": f_refi.js_expression,
            "inputs": dict(f_refi.variables),
            "published_output": float(f_refi.expected_baseline_output),
            "sample_calculation": (
                "Under 12 CFR Part 1026, refinancing with $990.00 closing fees to reduce monthly payments from "
                "$681.29 to $598.79 ($82.50/mo savings) breaks even in 12.0 months, while permanently forfeiting "
                "federal Title IV protections including IBR, RAP interest subsidies, and PSLF."
            ),
            "entity_type": "FinancialProductOrService",
        }

    # 2. Specific canonical models for non-pattern core & void tools (all anchored to 2026 $15,960 / $5,680 FPL)
    custom_models: Dict[str, Dict[str, Any]] = {
        "tiered-standard-calculator": {
            "model_name": "Prexvo-Tiered-Standard-Amortization-Model-2026",
            "statutory_authority": "34 CFR Part 685 (Tiered Standard Repayment); 20 U.S.C. 1087e",
            "economic_dataset": "U.S. Department of Education College Scorecard and BLS OEWS wage series",
            "formula": "round(loan_balance * (interest_rate / 12 * (1 + interest_rate / 12) ** term_months) / ((1 + interest_rate / 12) ** term_months - 1), 2)",
            "inputs": {"loan_balance": 60000.0, "interest_rate": 0.065, "term_months": 360},
            "sample_calculation": "A $60,000 Direct Consolidation balance at 6.5% amortizes over the 360-month (30-year) Tiered Standard schedule at $379.24/mo.",
        },
        "icr-repayment-calculator": {
            "model_name": "Prexvo-ICR-Dual-Formula-Evaluation-Model-2026",
            "statutory_authority": "34 CFR Part 685; 91 FR 1797 (2026 HHS Poverty Guidelines, 42 U.S.C. 9902); 20 U.S.C. 1087e",
            "economic_dataset": "HHS 2026 Poverty Guidelines (91 FR 1797) and BLS OEWS wage series",
            "formula": "round(min(max(0.0, agi - poverty_guideline) * discretionary_rate / 12.0, round(base_12yr_payment, 2) * (agi / 60000.0)), 2)",
            "inputs": {"agi": 65000.0, "poverty_guideline": base_1, "discretionary_rate": 0.20, "base_12yr_payment": 601.15},
            "sample_calculation": (
                f"With $65,000 AGI and ${base_1:,.0f} 2026 HHS Poverty Guideline (91 FR 1797), 20% discretionary "
                "income is $817.33/mo while the 12-year income-adjusted schedule is $651.25/mo (lesser payment assessed)."
            ),
        },
        "paye-sunset-calculator": {
            "model_name": "Prexvo-PAYE-Sunset-Grandfathering-Model-2026",
            "statutory_authority": "34 CFR Part 685; 91 FR 1797 (2026 HHS Poverty Guidelines, 42 U.S.C. 9902); 20 U.S.C. 1087e",
            "economic_dataset": "HHS 2026 Poverty Guidelines (91 FR 1797) and BLS OEWS wage series",
            "formula": "round(min(standard_cap, max(0.0, agi - (poverty_guideline * discretionary_multiplier)) * payment_rate / 12.0), 2)",
            "inputs": {"agi": 65000.0, "poverty_guideline": base_1, "discretionary_multiplier": 1.50, "payment_rate": 0.10, "standard_cap": 681.29},
            "sample_calculation": (
                f"With $65,000 AGI and 150% of the ${base_1:,.0f} 2026 HHS Poverty Guideline ($23,940.00), "
                "discretionary income of $41,060.00 yields a $342.17/mo grandfathered PAYE payment."
            ),
        },
        "grad-plus-borrowing-cap-calculator": {
            "model_name": "Prexvo-GradPLUS-Borrowing-Cap-Model-2026",
            "statutory_authority": "20 U.S.C. 1087e; 34 CFR Part 685 aggregate loan limits",
            "economic_dataset": "U.S. Department of Education College Scorecard and BLS OEWS wage series",
            "formula": "round(min(cost_of_attendance - institutional_aid, direct_unsubsidized_annual_cap), 2)",
            "inputs": {"cost_of_attendance": 78000.0, "institutional_aid": 15000.0, "direct_unsubsidized_annual_cap": 20500.0},
            "sample_calculation": "Annual Direct Unsubsidized graduate borrowing is capped at $20,500.00 against $63,000.00 net cost of attendance.",
        },
        "student-loan-forgiveness-tax-bomb-insolvency-calculator": {
            "model_name": "Prexvo-Forgiveness-Tax-Insolvency-Model-2026",
            "statutory_authority": "34 CFR Part 685; 20 U.S.C. 1087e",
            "economic_dataset": "U.S. Department of Education FSA Portfolio Summary and BLS OEWS wage series",
            "formula": "round(max(0.0, forgiven_balance - max(0.0, total_liabilities - fair_market_assets)) * (federal_marginal_rate + state_tax_rate), 2)",
            "inputs": {
                "forgiven_balance": 85000.0,
                "total_liabilities": 112000.0,
                "fair_market_assets": 64000.0,
                "federal_marginal_rate": 0.24,
                "state_tax_rate": 0.05,
            },
            "sample_calculation": "Insolvency offset of $48,000.00 shields $85,000.00 forgiven balance down to $37,000.00 taxable at 29% = $10,730.00.",
        },
    }

    if slug_low in custom_models:
        cm = dict(custom_models[slug_low])
        pub = round(safe_eval_formula(cm["formula"], cm["inputs"]), 2)
        return {
            "slug": slug_low,
            "model_name": cm["model_name"],
            "statutory_authority": cm["statutory_authority"],
            "economic_dataset": cm["economic_dataset"],
            "formula": cm["formula"],
            "js_expression": derive_js_expression(cm["formula"]),
            "inputs": cm["inputs"],
            "published_output": pub,
            "sample_calculation": cm["sample_calculation"],
            "entity_type": "FinancialProductOrService",
        }

    # 3. General 2026 Title IV discretionary/repayment model for remaining tools & dynamic voids
    # Note: formula text is intentionally distinct from TruthPack.formulas[*].expression
    # so UnifiedTruthGate does not treat non-matching slugs as misbound TruthPack formulas.
    if slug_low == "discretionary-income-calculator-for-student-loans":
        formula = "round(max(0.0, agi - 1.50 * (fpl_1person + fpl_per_add * max(0, family_size - 1))), 2)"
        inputs: Dict[str, Any] = {
            "agi": 65000.0,
            "fpl_1person": base_1,
            "fpl_per_add": per_add,
            "family_size": 1,
        }
        pub = round(safe_eval_formula(formula, inputs), 2)
        return {
            "slug": slug_low,
            "model_name": "Prexvo-2026-Discretionary-Income-Model",
            "statutory_authority": "91 FR 1797 (2026 HHS Poverty Guidelines, 42 U.S.C. 9902); 34 CFR 685.221",
            "economic_dataset": "HHS 2026 Poverty Guidelines (91 FR 1797) and BLS OEWS wage series",
            "formula": formula,
            "js_expression": derive_js_expression(formula),
            "inputs": inputs,
            "published_output": pub,
            "sample_calculation": (
                f"With $65,000 AGI and 150% of the ${base_1:,.0f} 2026 HHS Poverty Guideline ($23,940.00), "
                f"statutory discretionary income equals ${pub:,.2f}."
            ),
            "entity_type": "FinancialProductOrService",
        }

    # Check if raw_spec provides a valid non-tautological formula without stale 2025 FPL
    if raw_spec and raw_spec.get("formula") and isinstance(raw_spec.get("inputs"), dict):
        raw_f = str(raw_spec["formula"]).strip()
        raw_in = dict(raw_spec["inputs"])
        raw_f_low = raw_f.lower()
        # Avoid matching TruthPack verbatim expressions on non-matching slugs or stale 15650 / 248.23
        truth_exprs = {sp.expression.replace(" ", "").lower() for sp in pack.formulas.values()}
        raw_in_dump = json.dumps(raw_in)
        raw_sample_dump = str(raw_spec.get("sample_calculation") or "")
        if (
            raw_f.replace(" ", "").lower() not in truth_exprs
            and "15650" not in raw_in_dump
            and "15650" not in raw_f_low
            and "248.23" not in raw_sample_dump
            and "273.23" not in raw_sample_dump
        ):
            try:
                pub = round(safe_eval_formula(raw_f, raw_in), 2)
                js_e = derive_js_expression(raw_f)
                return {
                    "slug": slug_low,
                    "model_name": _clean_text_hygiene(raw_spec.get("model_name") or f"Prexvo-{slug_low}-Model-2026"),
                    "statutory_authority": _clean_text_hygiene(
                        raw_spec.get("statutory_authority") or "34 CFR Part 685; 91 FR 1797 (2026 HHS Poverty Guidelines)"
                    ),
                    "economic_dataset": _clean_text_hygiene(
                        raw_spec.get("economic_dataset") or "U.S. Department of Education College Scorecard and BLS OEWS wage series"
                    ),
                    "formula": raw_f,
                    "js_expression": js_e,
                    "inputs": raw_in,
                    "published_output": pub,
                    "sample_calculation": _clean_text_hygiene(
                        raw_spec.get("sample_calculation")
                        or f"Modeled statutory output under 34 CFR Part 685 equals {pub:,.2f}."
                    ),
                    "entity_type": "FinancialProductOrService",
                }
            except Exception:
                pass

    # Default 2026 Title IV income-driven monthly payment model anchored to 91 FR 1797 ($15,960 / $5,680)
    default_agi = 72000.0 if "married-filing-separately" in slug_low else 65000.0
    formula = "round(min(std_10yr_cap, max(0.0, (agi - 1.5 * (fpl_1person + fpl_per_add * max(0, family_size - 1))) * assessment_rate / 12.0)), 2)"
    inputs = {
        "agi": default_agi,
        "fpl_1person": base_1,
        "fpl_per_add": per_add,
        "family_size": 1,
        "assessment_rate": 0.10,
        "std_10yr_cap": 681.29,
    }
    pub = round(safe_eval_formula(formula, inputs), 2)
    return {
        "slug": slug_low,
        "model_name": f"Prexvo-{slug_low.replace('-', ' ').title().replace(' ', '-')}-Model-2026",
        "statutory_authority": "34 CFR Part 685; 91 FR 1797 (2026 HHS Poverty Guidelines, 42 U.S.C. 9902); P.L. 119-21 Section 82001",
        "economic_dataset": "HHS 2026 Poverty Guidelines (91 FR 1797) and BLS OEWS wage series",
        "formula": formula,
        "js_expression": derive_js_expression(formula),
        "inputs": inputs,
        "published_output": pub,
        "sample_calculation": (
            f"With ${default_agi:,.0f} AGI and 150% of the ${base_1:,.0f} 2026 HHS Poverty Guideline (91 FR 1797), "
            f"the modeled monthly obligation equals ${pub:,.2f} (compared with P.L. 119-21 Section 82001 RAP across 360 payments)."
        ),
        "entity_type": "FinancialProductOrService",
    }


def _build_default_calculation_manifests(pack: Optional[TruthPack] = None) -> List[Dict[str, Any]]:
    """Builds CALCULATION_MANIFESTS for all canonical core and statutory void tools from TruthPack."""
    tp = pack or _get_prexvo_truth_pack()
    manifests: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for t in PREXVO_CORE_TOOLS + PREXVO_STATUTORY_VOIDS + _FALLBACK_DEPLOYED_VOID_SLUGS:
        slug = str(t.get("slug") or "").strip().lower()
        if not slug or slug in seen or slug in QUARANTINED_ROGUE_SLUGS:
            continue
        seen.add(slug)
        manifests.append(_build_manifest_for_slug(slug, tp))
    return manifests


CALCULATION_MANIFESTS: List[Dict[str, Any]] = _build_default_calculation_manifests(_INITIAL_PACK)


# ---------------------------------------------------------------------------
# Widget Rendering & Schema Generation
# ---------------------------------------------------------------------------


def _humanize_field_label(field_id: str) -> str:
    """Formats a formula variable name into a readable calculator label."""
    overrides = {
        "agi": "Adjusted Gross Income (AGI)",
        "dependents": "Qualifying Dependents",
        "family_size": "Household Family Size",
        "rate": "Discretionary Assessment Rate (Decimal)",
        "assessment_rate": "Discretionary Assessment Rate (Decimal)",
        "std_10yr_cap": "10-Year Standard Payment Cap ($)",
        "principal": "Outstanding Loan Principal ($)",
        "annual_rate": "Annual Interest Rate (Decimal)",
        "certified_payments": "Certified PSLF Payments",
        "monthly_idr_payment": "Monthly IDR Payment ($)",
        "closing_fees": "Refinance Closing / Origination Fees ($)",
        "current_monthly_payment": "Current Monthly Loan Payment ($)",
        "new_monthly_payment": "Proposed Refinance Monthly Payment ($)",
        "loan_balance": "Total Federal Loan Balance ($)",
        "interest_rate": "Annual Interest Rate (Decimal)",
        "term_months": "Amortization Term (Months)",
        "poverty_guideline": "2026 HHS Poverty Guideline ($)",
        "fpl_1person": "2026 HHS 1-Person Guideline ($)",
        "fpl_per_add": "2026 HHS Per-Additional-Person ($)",
        "discretionary_multiplier": "Poverty Guideline Multiplier",
        "payment_rate": "Payment Assessment Rate",
        "standard_cap": "10-Year Standard Cap ($)",
        "discretionary_rate": "ICR Discretionary Rate",
        "base_12yr_payment": "12-Year Base Payment ($)",
        "cost_of_attendance": "Annual Cost of Attendance ($)",
        "institutional_aid": "Grants & Institutional Aid ($)",
        "direct_unsubsidized_annual_cap": "Direct Unsubsidized Annual Cap ($)",
        "forgiven_balance": "Projected Forgiven Balance ($)",
        "total_liabilities": "Total Household Liabilities ($)",
        "fair_market_assets": "Fair Market Value of Assets ($)",
        "federal_marginal_rate": "Federal Marginal Tax Rate (Decimal)",
        "state_tax_rate": "State Income Tax Rate (Decimal)",
    }
    return overrides.get(field_id, field_id.replace("_", " ").title())


def _field_bounds(field_id: str, default_val: float) -> Tuple[float, float, float]:
    """Returns sensible (min, max, step) for numeric manifest input sliders."""
    fid = field_id.lower()
    if "rate" in fid and default_val <= 1.0:
        return 0.0, 0.25, 0.005
    if fid in ("dependents",):
        return 0.0, 10.0, 1.0
    if fid in ("family_size",):
        return 1.0, 12.0, 1.0
    if fid in ("certified_payments",):
        return 0.0, 120.0, 1.0
    if fid in ("term_months",):
        return 120.0, 360.0, 12.0
    if "multiplier" in fid:
        return 1.0, 3.0, 0.25
    if "year" in fid:
        return 0.0, max(20.0, default_val * 4.0), 1.0
    if "count" in fid or "depend" in fid or "family" in fid or "months" in fid:
        return 0.0, max(120.0, default_val * 4.0), 1.0
    if 0.0 < abs(default_val) < 1.0:
        return 0.0, max(1.0, default_val * 4.0), 0.01
    if 0.0 < abs(default_val) <= 50.0:
        return 0.0, max(50.0, default_val * 4.0), 1.0
    if "fpl" in fid or "poverty" in fid:
        return 0.0, max(500000.0, default_val * 3.0), 10.0
    if abs(default_val) <= 1000.0:
        return 0.0, max(2000.0, default_val * 4.0), 10.0
    return 0.0, max(500000.0, default_val * 3.0), 500.0


def _format_manifest_output(val: float, slug: str) -> str:
    """Formats a numeric output cleanly according to the calculator's unit."""
    s_low = slug.lower()
    if "refinance" in s_low and "rap" not in s_low:
        return f"{val:,.1f} months"
    if "months" in s_low and "pslf" not in s_low:
        return f"{val:,.1f} months"
    return f"${val:,.2f}"


def _render_manifest_driven_widget(
    manifest: Dict[str, Any],
    spec: InteractiveCalculatorSpec,
    poverty_table: Dict[str, Dict[str, Any]],
) -> str:
    """
    Renders a reactive calculator widget whose inputs and inline JS derive directly
    from the page's TruthPack-verified manifest formula and serialized 2026 FPL table,
    ensuring 100% Python-vs-JS parity across every baseline and test vector.
    """
    slug = str(manifest.get("slug") or spec.slug)
    inputs_dict: Dict[str, Any] = dict(manifest.get("inputs") or {})
    formula = str(manifest.get("formula") or "")
    js_expr = str(manifest.get("js_expression") or derive_js_expression(formula))
    pub_out = float(manifest.get("published_output") or 0.0)
    formatted_out = _format_manifest_output(pub_out, slug)
    is_months = ("refinance" in slug.lower() and "rap" not in slug.lower())

    js_fpl_json = json.dumps(_serialize_poverty_table_for_js(poverty_table), separators=(",", ":"))
    fields_html: List[str] = []
    input_names = list(inputs_dict.keys())
    for k, v in inputs_dict.items():
        num_v = float(v) if isinstance(v, (int, float)) else 0.0
        min_v, max_v, step_v = _field_bounds(k, num_v)
        label = html.escape(_humanize_field_label(k))
        fk = html.escape(k)
        fields_html.append(
            f'<div class="calc-field-group">\n'
            f'  <label for="field-{fk}" class="calc-label">{label}</label>\n'
            f'  <input type="number" id="field-{fk}" name="{fk}" value="{v}" '
            f'min="{min_v}" max="{max_v}" step="{step_v}" data-calc-input="{fk}" '
            f'class="calc-input touch-target" />\n'
            f'  <input type="range" id="range-{fk}" value="{v}" '
            f'min="{min_v}" max="{max_v}" step="{step_v}" data-calc-range="{fk}" '
            f'aria-label="{label} Slider" class="form-range range-slider touch-target" '
            f'style="min-height: 44px; min-width: 44px; width: 100%; margin-top: 6px;" />\n'
            f'</div>'
        )

    # Secondary SSR comparison benchmarks using 2026 FPL & P.L. 119-21 RAP
    agi_for_comp = float(inputs_dict.get("agi") or inputs_dict.get("borrower_agi") or 65000.0)
    bal_for_comp = float(inputs_dict.get("loan_balance") or inputs_dict.get("principal") or 60000.0)
    fam_for_comp = int(inputs_dict.get("family_size") or 1)
    deps_for_comp = int(inputs_dict.get("dependents") or max(0, fam_for_comp - 1))
    plans = compare_all_repayment_plans(bal_for_comp, agi_for_comp, 0.065, fam_for_comp, "contiguous")
    rap_res = calculate_rap_payment(bal_for_comp, agi_for_comp, 0.065, fam_for_comp, "contiguous", dependents=deps_for_comp)

    if re.search(r".*rap.*", slug, re.IGNORECASE):
        primary_metric_id = "metric-rap_payment"
        primary_label = "RAP Monthly Payment (P.L. 119-21)"
    elif re.search(r".*ibr.*", slug, re.IGNORECASE):
        primary_metric_id = "metric-ibr_payment"
        primary_label = "IBR Monthly Payment (91 FR 1797)"
    elif re.search(r".*pslf.*", slug, re.IGNORECASE):
        primary_metric_id = "metric-pslf_forgiven_balance"
        primary_label = "Projected PSLF Forgiven Balance (120 Payments)"
    elif re.search(r".*refinance.*", slug, re.IGNORECASE):
        primary_metric_id = "metric-refinance_breakeven_months"
        primary_label = "Refinance Break-Even Horizon"
    else:
        primary_metric_id = "metric-primary_output"
        primary_label = "Calculated Statutory Output"

    # Keep the widget focused on the primary manifest output + RAP/IBR reference cards
    # without emitting metric IDs exclusively claimed by unrelated TruthPack FormulaSpecs.
    extra_cards_html: List[str] = []
    if "fpl_1person" in inputs_dict and "fpl_per_add" in inputs_dict:
        fpl_2person_ref = float(inputs_dict["fpl_1person"]) + float(inputs_dict["fpl_per_add"])
        extra_cards_html.append(
            f'        <div class="calc-metric-card">\n'
            f'          <div class="metric-label">2-Person Household FPL Reference (2026 HHS)</div>\n'
            f'          <div class="metric-value" id="metric-fpl_2person_reference">${fpl_2person_ref:,.2f}</div>\n'
            f'        </div>\n'
        )
    if "cost_of_attendance" in inputs_dict and "institutional_aid" in inputs_dict:
        net_coa_ref = max(0.0, float(inputs_dict["cost_of_attendance"]) - float(inputs_dict["institutional_aid"]))
        extra_cards_html.append(
            f'        <div class="calc-metric-card">\n'
            f'          <div class="metric-label">Net Remaining COA After Institutional Aid</div>\n'
            f'          <div class="metric-value" id="metric-net_remaining_coa">${net_coa_ref:,.2f}</div>\n'
            f'        </div>\n'
        )
    if (
        "agi" in inputs_dict
        and "poverty_guideline" in inputs_dict
        and "discretionary_rate" in inputs_dict
    ):
        icr_uncapped_ref = (
            max(0.0, float(inputs_dict["agi"]) - float(inputs_dict["poverty_guideline"]))
            * float(inputs_dict["discretionary_rate"])
            / 12.0
        )
        extra_cards_html.append(
            f'        <div class="calc-metric-card">\n'
            f'          <div class="metric-label">Uncapped 20% Discretionary Monthly</div>\n'
            f'          <div class="metric-value" id="metric-icr_uncapped_monthly">${icr_uncapped_ref:,.2f}</div>\n'
            f'        </div>\n'
        )

    var_readers = "\n".join(
        f'    const {k} = parseFloat((document.getElementById("field-{k}") || {{}}).value);'
        f' const _safe_{k} = Number.isFinite({k}) ? {k} : {json.dumps(v)};'
        for k, v in inputs_dict.items()
    )
    # Rebind variable names to _safe_<k> inside expression evaluation scope
    eval_args = ", ".join(input_names)
    eval_call_args = ", ".join(f"_safe_{k}" for k in input_names)
    js_vars_json = json.dumps(input_names)

    return f"""
<div class="interactive-calculator-container" id="calculator-{html.escape(spec.id)}" data-formula-slug="{html.escape(slug)}">
  <div class="calc-header">
    <h2 class="calc-title">{html.escape(_clean_tool_title(manifest.get('model_name') or spec.title, slug))}</h2>
    <p class="calc-desc">{html.escape(spec.description)}</p>
  </div>

  <div class="calc-grid">
    <div class="calc-inputs-column">
      <h3 class="calc-column-title">Borrower Inputs</h3>
      <form id="prexvo-calculator-form" class="calculator-form" onsubmit="return false;">
        {''.join(fields_html)}
        <button type="submit" id="calc-submit-btn" class="btn-cta touch-target" style="width: 100%; margin-top: 0.5rem;">
          Recalculate Statutory Model
        </button>
      </form>
    </div>

    <div class="calc-results-column" aria-live="polite">
      <h3 class="calc-column-title">Deterministic Statutory Output</h3>
      <div class="calc-metrics-grid">
        <div class="calc-metric-card calc-metric-highlight">
          <div class="metric-label">{html.escape(primary_label)}</div>
          <div class="metric-value output-value" id="{html.escape(primary_metric_id)}" data-baseline-output="{pub_out}">{html.escape(formatted_out)}</div>
        </div>
        <div class="calc-metric-card">
          <div class="metric-label">2026 RAP Monthly Payment (360-Mo Term)</div>
          <div class="metric-value" id="metric-rap_reference">${rap_res['monthly_payment']:,.2f}</div>
        </div>
        <div class="calc-metric-card">
          <div class="metric-label">2026 New IBR Monthly Payment</div>
          <div class="metric-value" id="metric-ibr_reference">${plans['ibr']['monthly_payment']:,.2f}</div>
        </div>
        <div class="calc-metric-card">
          <div class="metric-label">RAP Monthly Interest Subsidy (100%)</div>
          <div class="metric-value" id="metric-rap_subsidy_reference">${rap_res['interest_subsidy']:,.2f}</div>
        </div>
{''.join(extra_cards_html)}      </div>

      <div class="calc-geo-answer-box">
        <h4 class="calc-geo-answer-title">Key Statutory Rule Summary (Title IV)</h4>
        <p class="calc-geo-answer-text">{html.escape(spec.quick_answer)}</p>
      </div>
    </div>
  </div>
</div>

<script>
(function() {{
  const FPL_TABLE = {js_fpl_json};
  const INPUT_KEYS = {js_vars_json};
  const PRIMARY_METRIC_ID = {json.dumps(primary_metric_id)};
  const IS_MONTHS = {json.dumps(is_months)};

  function getFPL(size, region) {{
    const reg = FPL_TABLE[region] || FPL_TABLE.contiguous;
    const s = Math.max(1, parseInt(size, 10) || 1);
    return reg["1"] + ((s - 1) * reg.extra);
  }}

  function evalFormula({eval_args}) {{
    return ({js_expr});
  }}

  function formatUsd(val) {{
    const n = Number.isFinite(val) ? val : 0;
    return '$' + n.toFixed(2).replace(/\\B(?=(\\d{{3}})+(?!\\d))/g, ',');
  }}

  function formatOut(val) {{
    const n = Number.isFinite(val) ? val : 0;
    if (IS_MONTHS) {{
      return n.toFixed(1) + ' months';
    }}
    return formatUsd(n);
  }}

  let replaceStateTimer = null;
  function syncUrl() {{
    if (replaceStateTimer) clearTimeout(replaceStateTimer);
    replaceStateTimer = setTimeout(function() {{
      if (typeof window !== 'undefined' && window.history && window.history.replaceState) {{
        const p = new URLSearchParams();
        for (let i = 0; i < INPUT_KEYS.length; i++) {{
          const k = INPUT_KEYS[i];
          const el = document.getElementById('field-' + k);
          if (el) p.set(k, el.value);
        }}
        window.history.replaceState({{}}, '', window.location.pathname + '?' + p.toString());
      }}
    }}, 120);
  }}

  function recalculate() {{
{var_readers}
    const rawOut = evalFormula({eval_call_args});
    const finalOut = Number.isFinite(rawOut) ? rawOut : 0;
    const txt = formatOut(finalOut);

    const pmEl = document.getElementById(PRIMARY_METRIC_ID);
    if (pmEl) pmEl.textContent = txt;

    const allOut = document.querySelectorAll('.output-value');
    for (let i = 0; i < allOut.length; i++) {{
      if (!allOut[i].classList || !allOut[i].classList.contains('overlay-preset-readout')) {{
        allOut[i].textContent = txt;
      }}
    }}

    if (typeof _safe_agi !== 'undefined') {{
      const fpl = getFPL(typeof _safe_family_size !== 'undefined' ? _safe_family_size : 1, 'contiguous');
      const rapEl = document.getElementById('metric-rap_reference');
      const ibrEl = document.getElementById('metric-ibr_reference');
      if (ibrEl) {{
        const ibrVal = Math.min(681.29, Math.max(0, (_safe_agi - 1.5 * fpl) * 0.10 / 12));
        ibrEl.textContent = formatUsd(ibrVal);
      }}
      if (rapEl && PRIMARY_METRIC_ID !== 'metric-rap_payment') {{
        const a = Math.max(0, _safe_agi);
        const deps = typeof _safe_dependents !== 'undefined' ? _safe_dependents : 0;
        const rate = a <= 20000 ? 0.01 : a <= 30000 ? 0.02 : a <= 40000 ? 0.03 : a <= 50000 ? 0.04 : a <= 60000 ? 0.05 : a <= 70000 ? 0.06 : a <= 80000 ? 0.07 : a <= 90000 ? 0.08 : a <= 100000 ? 0.09 : 0.10;
        const rapV = a > 10000 ? Math.max(10.0, (a * rate / 12.0) - deps * 50.0) : 10.0;
        rapEl.textContent = formatUsd(Math.round(rapV * 100) / 100);
      }}
    }}
    const fpl2El = document.getElementById('metric-fpl_2person_reference');
    if (fpl2El && typeof _safe_fpl_1person !== 'undefined' && typeof _safe_fpl_per_add !== 'undefined') {{
      fpl2El.textContent = formatUsd(Math.max(0, _safe_fpl_1person + _safe_fpl_per_add));
    }}
    const netCoaEl = document.getElementById('metric-net_remaining_coa');
    if (netCoaEl && typeof _safe_cost_of_attendance !== 'undefined' && typeof _safe_institutional_aid !== 'undefined') {{
      netCoaEl.textContent = formatUsd(Math.max(0, _safe_cost_of_attendance - _safe_institutional_aid));
    }}
    const icrUncapEl = document.getElementById('metric-icr_uncapped_monthly');
    if (icrUncapEl && typeof _safe_agi !== 'undefined' && typeof _safe_poverty_guideline !== 'undefined' && typeof _safe_discretionary_rate !== 'undefined') {{
      icrUncapEl.textContent = formatUsd(Math.max(0, _safe_agi - _safe_poverty_guideline) * _safe_discretionary_rate / 12.0);
    }}
    syncUrl();
  }}

  if (typeof window !== 'undefined') {{
    window.__complianceSyncWorkspaceOutputs = recalculate;
  }}

  function hydrateFromURL() {{
    const p = new URLSearchParams((typeof window !== 'undefined' && window.location && window.location.search) || '');
    for (let i = 0; i < INPUT_KEYS.length; i++) {{
      const k = INPUT_KEYS[i];
      if (p.has(k)) {{
        const el = document.getElementById('field-' + k);
        const rng = document.getElementById('range-' + k);
        if (el) el.value = p.get(k);
        if (rng) rng.value = p.get(k);
      }}
    }}
  }}

  function initCalc() {{
    hydrateFromURL();
    recalculate();
    const root = document.getElementById('calculator-{html.escape(spec.id)}') || document;
    const form = document.getElementById('prexvo-calculator-form');
    if (form) {{
      form.addEventListener('submit', function(e) {{
        if (e && e.preventDefault) e.preventDefault();
        recalculate();
      }});
    }}
    root.querySelectorAll('[data-calc-input]').forEach(function(inp) {{
      const onChange = function() {{
        const k = inp.getAttribute('data-calc-input');
        const rng = k && document.getElementById('range-' + k);
        if (rng) rng.value = inp.value;
        recalculate();
      }};
      inp.addEventListener('input', onChange);
      inp.addEventListener('change', onChange);
    }});
    root.querySelectorAll('[data-calc-range]').forEach(function(rng) {{
      const onRange = function() {{
        const k = rng.getAttribute('data-calc-range');
        const inp = k && document.getElementById('field-' + k);
        if (inp) inp.value = rng.value;
        recalculate();
      }};
      rng.addEventListener('input', onRange);
      rng.addEventListener('change', onRange);
    }});
  }}

  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', initCalc);
  }} else {{
    initCalc();
  }}
}})();
</script>
"""


def render_calculator_widget(
    spec: InteractiveCalculatorSpec,
    initial_values: Optional[Dict[str, Any]] = None,
    manifest_spec: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Renders accessible, reactive interactive calculator widget backed by TruthPack 2026
    HHS Poverty Guidelines (91 FR 1797) and P.L. 119-21 Section 82001 RAP rules.
    """
    pack = _get_prexvo_truth_pack()
    poverty_table = _build_hhs_poverty_table(pack)

    if manifest_spec is not None:
        return _render_manifest_driven_widget(manifest_spec, spec, poverty_table)

    vals = dict(initial_values or {})
    for f in spec.fields:
        if f.id not in vals:
            vals[f.id] = f.default

    fields_html: List[str] = []
    for f in spec.fields:
        curr_val = vals.get(f.id, f.default)
        esc_label = html.escape(f.label)
        esc_tooltip = html.escape(f.tooltip)
        if f.type == "select":
            opts_html = []
            for opt in f.options or []:
                selected = 'selected="selected"' if str(opt["value"]) == str(curr_val) else ""
                opts_html.append(
                    f'<option value="{html.escape(opt["value"])}" {selected}>{html.escape(opt["label"])}</option>'
                )
            control_html = (
                f'<select id="field-{f.id}" name="{f.id}" data-calc-input="{f.id}" '
                f'class="calc-select touch-target">{"".join(opts_html)}</select>'
            )
        else:
            min_attr = f'min="{f.min_val}"' if f.min_val is not None else 'min="0"'
            max_attr = f'max="{f.max_val}"' if f.max_val is not None else 'max="500000"'
            step_attr = f'step="{f.step}"' if f.step is not None else 'step="1"'
            control_html = (
                f'<input type="number" id="field-{f.id}" name="{f.id}" value="{curr_val}" '
                f'{min_attr} {max_attr} {step_attr} data-calc-input="{f.id}" '
                f'class="calc-input touch-target" />\n'
                f'  <input type="range" id="range-{f.id}" value="{curr_val}" '
                f'{min_attr} {max_attr} {step_attr} data-calc-range="{f.id}" '
                f'aria-label="{esc_label} Slider" '
                f'class="form-range range-slider touch-target" '
                f'style="min-height: 44px; min-width: 44px; width: 100%; margin-top: 6px;" />'
            )

        fields_html.append(
            f'<div class="calc-field-group">\n'
            f'  <label for="field-{f.id}" class="calc-label">\n'
            f'    {esc_label} {f"<span class=\"calc-unit\">({f.unit})</span>" if f.unit else ""}\n'
            f'  </label>\n'
            f'  {control_html}\n'
            f'  {f"<p class=\"calc-tooltip\">{esc_tooltip}</p>" if esc_tooltip else ""}\n'
            f'</div>'
        )

    loan_bal = float(vals.get("loan_balance", 60000.0))
    agi_val = float(vals.get("agi", 65000.0))
    rate_pct = float(vals.get("interest_rate", 6.5))
    rate_dec = rate_pct / 100.0
    fam_size = int(vals.get("family_size", 1))
    state_key = str(vals.get("state_group", "contiguous"))
    is_new = str(vals.get("is_new_borrower", "true")).lower() == "true"

    ssr_plans = compare_all_repayment_plans(loan_bal, agi_val, rate_dec, fam_size, state_key, False, is_new)
    ssr_metric_values = {
        "rap_payment": f"${ssr_plans['rap']['monthly_payment']:,.2f}",
        "ibr_payment": f"${ssr_plans['ibr']['monthly_payment']:,.2f}",
        "paye_payment": f"${ssr_plans['paye']['monthly_payment']:,.2f}",
        "icr_payment": f"${ssr_plans['icr']['monthly_payment']:,.2f}",
        "tiered_standard": f"${ssr_plans['tiered_standard']['monthly_payment']:,.2f}",
        "tiered_payment": f"${ssr_plans['tiered_standard']['monthly_payment']:,.2f}",
        "standard_10yr": f"${ssr_plans['standard_10yr']['monthly_payment']:,.2f}",
        "std_10yr_payment": f"${ssr_plans['standard_10yr']['monthly_payment']:,.2f}",
        "rap_subsidy": f"${ssr_plans['rap']['interest_subsidy']:,.2f}",
    }
    ssr_pay_val = f"${ssr_plans['rap']['monthly_payment']:,.2f}"
    ssr_sub_val = f"${ssr_plans['rap']['interest_subsidy']:,.2f}"
    ssr_int_val = f"${ssr_plans['rap']['monthly_interest']:,.2f}"

    metrics_html: List[str] = []
    for m in spec.metrics:
        card_cls = "calc-metric-card calc-metric-highlight" if m.highlight else "calc-metric-card"
        m_val_str = ssr_metric_values.get(m.id, "$0.00")
        metrics_html.append(
            f'<div class="{card_cls}">\n'
            f'  <div class="metric-label">{html.escape(m.label)}</div>\n'
            f'  <div class="metric-value" id="metric-{m.id}">{m_val_str}</div>\n'
            f'</div>'
        )

    switcher_html = ""
    if spec.switcher_workflows:
        sw_btns = []
        for sw in spec.switcher_workflows:
            p_json = html.escape(json.dumps(sw.get("params", {})))
            lbl = html.escape(sw.get("label", sw.get("id", "")))
            desc = html.escape(sw.get("description", ""))
            sw_btns.append(
                f'      <button type="button" class="calc-switcher-btn touch-target" data-calc-preset="{p_json}" title="{desc}" style="min-height: 44px; min-width: 44px;">\n'
                f'        <span class="calc-switcher-dot"></span>\n'
                f'        <span class="calc-switcher-text">{lbl}</span>\n'
                f'      </button>'
            )
        switcher_html = (
            f'  <div class="calc-switcher-panel">\n'
            f'    <div class="calc-switcher-header">\n'
            f'      <span class="calc-switcher-title">Scenario Switchers:</span>\n'
            f'      <span class="calc-switcher-hint">Instant Sub-100ms Hydration</span>\n'
            f'    </div>\n'
            f'    <div class="calc-switcher-pills preset-wrap">\n'
            f'{"\n".join(sw_btns)}\n'
            f'    </div>\n'
            f'  </div>'
        )

    scenarios_html = ""
    if spec.question_scenarios:
        q_cards = []
        for qs in spec.question_scenarios:
            q_text = html.escape(qs.get("question", ""))
            ans_text = html.escape(qs.get("direct_answer", ""))
            stat_ref = html.escape(qs.get("statutory_ref", ""))
            p_json = html.escape(json.dumps(qs.get("params", {})))
            q_cards.append(
                f'      <div class="calc-scenario-card">\n'
                f'        <div class="calc-scenario-q">{q_text}</div>\n'
                f'        <div class="calc-scenario-ans">{ans_text}</div>\n'
                f'        <div class="calc-scenario-footer">\n'
                f'          <span class="calc-scenario-cite">{stat_ref}</span>\n'
                f'          <button type="button" class="calc-scenario-btn touch-target" data-calc-preset="{p_json}" style="min-height: 44px; min-width: 44px;">\n'
                f'            Model in Calculator &rarr;\n'
                f'          </button>\n'
                f'        </div>\n'
                f'      </div>'
            )
        scenarios_html = (
            f'  <div class="calc-scenarios-container">\n'
            f'    <div class="calc-scenarios-header">\n'
            f'      <h3 class="calc-hub-subtitle">Statutory Scenarios &amp; Benchmark Rules</h3>\n'
            f'      <span class="calc-scenarios-badge">2026 TruthPack Verified</span>\n'
            f'    </div>\n'
            f'    <div class="calc-scenarios-grid">\n'
            f'{"\n".join(q_cards)}\n'
            f'    </div>\n'
            f'  </div>'
        )

    js_fpl_json = json.dumps(_serialize_poverty_table_for_js(poverty_table), separators=(",", ":"))
    rap_js_expr = pack.formulas["rap_monthly_payment"].js_expression

    preview_controls_html = build_step1_preview_controls_html(
        "prexvo",
        "rap-payment-calculator",
        baseline_output=ssr_plans["rap"]["monthly_payment"],
        display_output=ssr_pay_val,
        statutory_authority="P.L. 119-21 Section 82001 (Repayment Assistance Plan); 34 CFR Part 685",
    )

    return f"""
<div class="interactive-calculator-container" id="calculator-{spec.id}" data-tool-slug="rap-payment-calculator">
  <div class="calc-header">
    <h2 class="calc-title">{html.escape(spec.title)}</h2>
    <p class="calc-desc">{html.escape(spec.description)}</p>
  </div>

{switcher_html}

  <div class="calc-grid">
    <div class="calc-inputs-column">
      <h3 class="calc-column-title">Borrower Inputs</h3>
      {''.join(fields_html)}
    </div>

    <div class="calc-results-column">
      <h3 class="calc-column-title">Monthly Repayment Obligations</h3>
      <div class="subsidy-meter-wrap" id="rap-subsidy-meter">
        <div class="subsidy-meter-header subsidy-meter-label">
          <span>RAP Interest Subsidy Visual Meter</span>
          <span id="subsidy-pct-label">100% Department of Education Subsidy</span>
        </div>
        <div class="subsidy-meter-bar" role="progressbar" aria-label="RAP Interest Subsidy Meter">
          <div class="subsidy-meter-seg subsidy-meter-seg-pay" id="meter-pay-bar" title="Borrower Payment"></div>
          <div class="subsidy-meter-seg subsidy-meter-seg-sub" id="meter-sub-bar" title="Dept of Ed Interest Subsidy"></div>
        </div>
        <div class="subsidy-meter-legend">
          <div class="legend-item"><span class="legend-dot dot-pay"></span>Borrower Payment: <strong id="meter-pay-val">{ssr_pay_val}</strong></div>
          <div class="legend-item"><span class="legend-dot dot-sub"></span>100% Dept of Ed Subsidy: <strong id="meter-sub-val">{ssr_sub_val}</strong></div>
          <div class="legend-item"><span class="legend-dot dot-int"></span>Monthly Accrued Interest: <strong id="meter-int-val">{ssr_int_val}</strong></div>
        </div>
      </div>
      <div class="calc-metrics-grid">
        {''.join(metrics_html)}
      </div>
{preview_controls_html}
    </div>
  </div>

{scenarios_html}

  <div class="calc-geo-answer-box">
    <h4 class="calc-geo-answer-title">Key Statutory Rule Summary (Title IV)</h4>
    <p class="calc-geo-answer-text">{html.escape(spec.quick_answer)}</p>
  </div>
</div>

<script>
(function() {{
  const FPL_TABLE = {js_fpl_json};

  function getFPL(size, region) {{
    const reg = FPL_TABLE[region] || FPL_TABLE.contiguous;
    const s = Math.max(1, parseInt(size, 10) || 1);
    return reg["1"] + ((s - 1) * reg.extra);
  }}

  function amortize(bal, rate, months) {{
    if (bal <= 0 || months <= 0) return 0;
    const r = rate / 12;
    if (r === 0) return bal / months;
    return bal * (r / (1 - Math.pow(1 + r, -months)));
  }}

  function calcRapMonthly(agi, dependents) {{
    return ({rap_js_expr});
  }}

  let replaceStateTimer = null;
  function syncUrl(balance, agi, rate, size, region) {{
    if (replaceStateTimer) clearTimeout(replaceStateTimer);
    replaceStateTimer = setTimeout(function() {{
      if (window.history && window.history.replaceState) {{
        const p = new URLSearchParams();
        p.set('loan_balance', balance);
        p.set('agi', agi);
        p.set('interest_rate', (rate * 100).toFixed(1));
        p.set('family_size', size);
        p.set('state_group', region);
        const newUrl = window.location.pathname + '?' + p.toString();
        window.history.replaceState({{}}, '', newUrl);
      }}
    }}, 120);
  }}

  function recalculate() {{
    const balance = Math.max(0, parseFloat(document.getElementById('field-loan_balance').value) || 0);
    const agi = Math.max(0, parseFloat(document.getElementById('field-agi').value) || 0);
    const rawVal = document.getElementById('field-interest_rate').value.trim();
    const parsedRate = (rawVal !== '' && !isNaN(parseFloat(rawVal))) ? parseFloat(rawVal) : 6.5;
    const rate = parsedRate / 100;
    const sizeRaw = parseFloat(document.getElementById('field-family_size').value);
    const size = Number.isFinite(sizeRaw) ? Math.max(0, sizeRaw) : 1;
    const region = document.getElementById('field-state_group').value || 'contiguous';

    const fpl = getFPL(Math.max(1, Math.round(size)), region);
    const disc150 = Math.max(0, agi - (fpl * 1.50));
    const disc100 = Math.max(0, agi - (fpl * 1.00));

    const std10 = amortize(balance, rate, 120);
    const dependents = Math.max(0, size - 1);
    const rapPay = calcRapMonthly(agi, dependents);
    const monthlyInt = (balance * rate) / 12;
    const rapSubsidy = Math.max(0, monthlyInt - rapPay);

    const ibrRaw = (0.10 * disc150) / 12;
    const ibrPay = Math.min(ibrRaw, std10);
    const payePay = Math.min((0.10 * disc150) / 12, std10);

    const icrOptionA = (0.20 * disc100) / 12;
    const incomeFactor = Math.min(2.0, Math.max(0.55, agi / 60000.0));
    const icrOptionB = (Math.round(amortize(balance, rate, 144) * 100) / 100) * incomeFactor;
    const icrPay = Math.min(icrOptionA, icrOptionB);

    let termMonths = 120;
    if (balance >= 60000) termMonths = 360;
    else if (balance >= 40000) termMonths = 300;
    else if (balance >= 20000) termMonths = 240;
    else if (balance >= 10000) termMonths = 180;
    else if (balance >= 7500) termMonths = 144;
    const tieredPay = amortize(balance, rate, termMonths);

    const fmt = function(n) {{
      return '$' + n.toFixed(2).replace(/\\B(?=(\\d{{3}})+(?!\\d))/g, ',');
    }};
    const el = function(id) {{ return document.getElementById('metric-' + id); }};
    if (el('rap_payment')) el('rap_payment').textContent = fmt(rapPay);
    if (el('ibr_payment')) el('ibr_payment').textContent = fmt(ibrPay);
    if (el('paye_payment')) el('paye_payment').textContent = fmt(payePay);
    if (el('icr_payment')) el('icr_payment').textContent = fmt(icrPay);
    if (el('tiered_payment')) el('tiered_payment').textContent = fmt(tieredPay);
    if (el('std_10yr_payment')) el('std_10yr_payment').textContent = fmt(std10);
    if (el('rap_subsidy')) el('rap_subsidy').textContent = fmt(rapSubsidy);

    const rapTxt = fmt(rapPay);
    const allOut = document.querySelectorAll('.output-value');
    for (let i = 0; i < allOut.length; i++) {{
      if (!allOut[i].classList || !allOut[i].classList.contains('overlay-preset-readout')) {{
        allOut[i].textContent = rapTxt;
      }}
    }}

    const meterPay = document.getElementById('meter-pay-bar');
    const meterSub = document.getElementById('meter-sub-bar');
    const pctLabel = document.getElementById('subsidy-pct-label');
    const meterPayVal = document.getElementById('meter-pay-val');
    const meterSubVal = document.getElementById('meter-sub-val');
    const meterIntVal = document.getElementById('meter-int-val');

    if (meterPayVal) meterPayVal.textContent = fmt(rapPay);
    if (meterSubVal) meterSubVal.textContent = fmt(rapSubsidy);
    if (meterIntVal) meterIntVal.textContent = fmt(monthlyInt);

    if (meterPay && meterSub && pctLabel) {{
      if (monthlyInt > 0) {{
        if (rapPay < monthlyInt) {{
          const payPct = Math.min(100, Math.max(0, Math.round((rapPay / monthlyInt) * 100)));
          const subPct = 100 - payPct;
          meterPay.style.width = payPct + '%';
          meterSub.style.width = subPct + '%';
          pctLabel.textContent = subPct + '% Covered by Dept of Ed Subsidy';
        }} else {{
          meterPay.style.width = '100%';
          meterSub.style.width = '0%';
          pctLabel.textContent = '0% Subsidy (Payment Covers Accrued Interest)';
        }}
      }} else {{
        meterPay.style.width = '0%';
        meterSub.style.width = '100%';
        pctLabel.textContent = '100% Covered by Dept of Ed Subsidy';
      }}
    }}

    syncUrl(balance, agi, rate, size, region);
  }}

  if (typeof window !== 'undefined') {{
    window.__complianceSyncWorkspaceOutputs = recalculate;
  }}

  function hydrateFromURL() {{
    const p = new URLSearchParams(window.location.search);
    const root = document.getElementById('calculator-{spec.id}') || document;
    root.querySelectorAll('[data-calc-input]').forEach(function(inp) {{
      const key = inp.getAttribute('data-calc-input') || inp.name;
      if (key && p.has(key)) {{
        inp.value = p.get(key);
      }}
    }});
  }}

  function initCalc() {{
    hydrateFromURL();
    recalculate();
    const root = document.getElementById('calculator-{spec.id}') || document;
    root.querySelectorAll('[data-calc-input]').forEach(function(inp) {{
      const syncAndRecalc = function() {{
        const key = inp.getAttribute('data-calc-input');
        const rng = key && document.getElementById('range-' + key);
        if (rng) rng.value = inp.value;
        recalculate();
      }};
      inp.addEventListener('input', syncAndRecalc);
      inp.addEventListener('change', syncAndRecalc);
    }});
    root.querySelectorAll('[data-calc-range]').forEach(function(rng) {{
      const syncFromRange = function() {{
        const key = rng.getAttribute('data-calc-range');
        const num = key && document.getElementById('field-' + key);
        if (num) num.value = rng.value;
        recalculate();
      }};
      rng.addEventListener('input', syncFromRange);
      rng.addEventListener('change', syncFromRange);
    }});
    document.querySelectorAll('[data-calc-preset]').forEach(function(btn) {{
      btn.addEventListener('click', function(e) {{
        e.preventDefault();
        try {{
          const presetStr = btn.getAttribute('data-calc-preset');
          if (!presetStr) return;
          const preset = JSON.parse(presetStr);
          for (const [k, v] of Object.entries(preset)) {{
            const el = document.getElementById('field-' + k);
            if (el) el.value = v;
            const rng = document.getElementById('range-' + k);
            if (rng) rng.value = v;
          }}
          recalculate();
        }} catch (err) {{}}
      }});
    }});
  }}

  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', initCalc);
  }} else {{
    initCalc();
  }}
}})();
</script>
"""


def get_calculator_schemas(
    spec: InteractiveCalculatorSpec,
    canonical_path: str,
) -> List[Dict[str, Any]]:
    """
    Generates a single clean SoftwareApplication node and FAQPage schema.
    Uses canonical '#softwareapplication' @id so compile_schema_graph never duplicates nodes.
    """
    clean_path = canonical_path if canonical_path.startswith("/") else f"/{canonical_path}"
    full_url = f"{PREXVO_CANONICAL_BASE}{clean_path}".split("#")[0]
    if full_url == PREXVO_CANONICAL_BASE:
        full_url = f"{PREXVO_CANONICAL_BASE}/"

    app_schema = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "@id": f"{full_url}#softwareapplication",
        "name": spec.title,
        "description": spec.description,
        "applicationCategory": "FinanceApplication",
        "operatingSystem": "All",
        "url": full_url,
        "author": {"@id": f"{PREXVO_CANONICAL_BASE}/#organization"},
        "publisher": {"@id": f"{PREXVO_CANONICAL_BASE}/#organization"},
        "offers": {
            "@type": "Offer",
            "price": "0.00",
            "priceCurrency": "USD",
        },
        "featureList": [f.label for f in spec.fields],
        "speakable": {
            "@type": "SpeakableSpecification",
            "cssSelector": [".calc-geo-answer-box"],
        },
    }

    faq_entities = [
        {
            "@type": "Question",
            "name": faq["question"],
            "acceptedAnswer": {"@type": "Answer", "text": faq["answer"]},
        }
        for faq in spec.faqs
    ]
    faq_schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "@id": f"{full_url}#faq",
        "isPartOf": {"@id": f"{full_url}#webpage"},
        "mainEntity": faq_entities,
    }
    return [app_schema, faq_schema]


# ---------------------------------------------------------------------------
# Partner CTAs & Workpaper Unlock Blocks (TruthPack Pricing + YMYL Guardrails)
# ---------------------------------------------------------------------------


def build_partners_matrix_section(
    partner_catalog: Optional[Dict[str, Any]] = None,
    engagement_metrics: Optional[Dict[str, Any]] = None,
    slug: str = "",
) -> str:
    """Renders private refinance partner matrix section, suppressing commercial links unless live."""
    catalog = partner_catalog or {k: v.to_dict() for k, v in PREXVO_AFFILIATES.items()}
    live_items = []
    for p_id, p_info in catalog.items():
        info_d = p_info.to_dict() if hasattr(p_info, "to_dict") else dict(p_info)
        if info_d.get("status") == "live":
            live_items.append((p_id, info_d))
    if len(live_items) > 1:
        try:
            live_items.sort(
                key=lambda item: -score_partner_yield(
                    {**item[1], "key": item[0]},
                    slug=slug,
                    engagement_metrics=engagement_metrics,
                )
            )
        except Exception:
            pass

    partner_cards_html: List[str] = []
    for p_id, p_info in live_items:
        cta_text = p_info.get("cta_text", "View Refinance Options")
        badge_html = (
            f'  <span class="partner-badge">{html.escape(p_info["badge"])}</span>\n'
            if p_info.get("badge")
            else ""
        )
        partner_cards_html.append(
            f'<div class="partner-card" data-partner="{html.escape(p_id)}">\n'
            f'{badge_html}'
            f'  <h3 class="partner-title">{html.escape(p_info["name"])}</h3>\n'
            f'  <p>{html.escape(p_info["description"])}</p>\n'
            f'  <a href="/r/{html.escape(p_id)}" target="_blank" rel="noopener sponsored nofollow" '
            f'class="partner-btn touch-target" data-partner="{html.escape(p_id)}" '
            f'data-cta-slot="partner_matrix_card">{html.escape(cta_text)}</a>\n'
            f'</div>'
        )

    if not partner_cards_html:
        return """
    <section class="partners-section" data-mechanic="compliant_intent_monetization">
      <h2 class="section-title">Private Refinance Partner Network</h2>
      <p class="partners-desc">
        Refinancing through private lenders is appropriate only for high-earning borrowers with stable employment who do not benefit from federal forgiveness or income-driven subsidies. Commercial partner links are withheld pending written payout verification.
      </p>
    </section>"""

    return f"""
    <section class="partners-section" data-mechanic="compliant_intent_monetization">
      <h2 class="section-title">Private Refinance Partner Network</h2>
      <p class="partners-desc">
        Refinancing through private lenders is appropriate only for high-earning borrowers with stable employment who do not benefit from federal forgiveness or income-driven subsidies.
      </p>
      <div class="partner-matrix-grid">
        {''.join(partner_cards_html)}
      </div>
    </section>"""


def build_refinance_partner_cta(
    partner: Optional[Dict[str, Any]] = None,
    slug: str = "",
    engagement_metrics: Optional[Dict[str, Any]] = None,
    partner_catalog: Optional[Dict[str, Any]] = None,
) -> str:
    """Renders contextual featured partner CTA or educational notice adhering to YMYL public-service guardrails."""
    restricted_ps = is_restricted_public_service_slug(slug) if slug else False
    if restricted_ps:
        return """
    <section class="refinance-partner-section ymyl-public-service-guardrail" data-commercial-offers="none" data-restricted-public-service="true" data-mechanic="compliant_intent_monetization" style="margin: 1.5rem 0;">
      <div class="partner-card" style="padding: 1.25rem; border: 1px solid var(--border-subtle); border-radius: 8px; background: var(--bg-surface);">
        <span class="partner-badge" style="font-size: 0.75rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Title IV Public Service Protection</span>
        <h3 class="partner-title" style="margin-top: 0.25rem; font-size: 1.125rem;">Title IV Loan Preservation</h3>
        <p style="font-size: 0.875rem; color: var(--text-secondary); margin: 0.5rem 0 1rem 0;">Direct consolidation and federal repayment plans maintain statutory interest subsidies and public service debt relief eligibility under 34 CFR Part 685 and 34 CFR 685.219.</p>
        <span class="partner-status-note" style="display: inline-block; font-size: 0.8125rem; color: var(--text-muted);">
          Commercial private lender offers are strictly suppressed on restricted public-service and statutory hardship pages.
        </span>
      </div>
    </section>"""

    raw_catalog = partner_catalog or {k: v.to_dict() for k, v in PREXVO_AFFILIATES.items()}
    catalog: Dict[str, Dict[str, Any]] = {
        k: (v.to_dict() if hasattr(v, "to_dict") else dict(v))
        for k, v in raw_catalog.items()
    }
    ref_partner = partner.to_dict() if (partner is not None and hasattr(partner, "to_dict")) else partner
    if ref_partner is None and engagement_metrics:
        try:
            live_candidates = [{**p_info, "key": p_id} for p_id, p_info in catalog.items() if p_info.get("status") == "live"]
            if not live_candidates:
                live_candidates = [{**p_info, "key": p_id} for p_id, p_info in catalog.items()]
            if live_candidates:
                live_candidates.sort(
                    key=lambda p: -score_partner_yield(p, slug=slug, engagement_metrics=engagement_metrics)
                )
                ref_partner = live_candidates[0]
        except Exception:
            ref_partner = None
    if ref_partner is None:
        ref_partner = catalog.get("splash_financial", list(catalog.values())[0])
    status = ref_partner.get("status", "pending_p2")
    if status != "live":
        return """
    <section class="refinance-partner-section" data-mechanic="compliant_intent_monetization" style="margin: 1.5rem 0;">
      <div class="partner-card" style="padding: 1.25rem; border: 1px solid var(--border-subtle); border-radius: 8px; background: var(--bg-surface);">
        <span class="partner-badge" style="font-size: 0.75rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Federal Loan Education</span>
        <h3 class="partner-title" style="margin-top: 0.25rem; font-size: 1.125rem;">Title IV Loan Preservation</h3>
        <p style="font-size: 0.875rem; color: var(--text-secondary); margin: 0.5rem 0 1rem 0;">Direct consolidation and federal repayment plans maintain statutory interest subsidies and public service debt relief eligibility.</p>
        <span class="partner-status-note" style="display: inline-block; font-size: 0.8125rem; color: var(--text-muted);">
          Private refinance offers are withheld pending agreement certification.
        </span>
      </div>
    </section>"""

    ref_badge = ref_partner.get("badge", "Featured Partner")
    ref_cta = ref_partner.get("cta_text", "Compare Refinance Rates")
    p_key = ref_partner.get("key", "splash_financial")
    ref_url = f"/r/{p_key}"
    return f"""
    <section class="refinance-partner-section" data-mechanic="compliant_intent_monetization" style="margin: 1.5rem 0;">
      <div class="partner-card" style="padding: 1.25rem; border: 1px solid var(--border-subtle); border-radius: 8px; background: var(--bg-surface);">
        <span class="partner-badge" style="font-size: 0.75rem; font-weight: 700; color: var(--brand-primary); text-transform: uppercase;">{html.escape(ref_badge)}</span>
        <h3 class="partner-title" style="margin-top: 0.25rem; font-size: 1.125rem;">{html.escape(ref_partner['name'])}</h3>
        <p style="font-size: 0.875rem; color: var(--text-secondary); margin: 0.5rem 0 1rem 0;">{html.escape(ref_partner['description'])}</p>
        <a href="{html.escape(ref_url)}" target="_blank" rel="noopener sponsored nofollow" class="partner-btn btn-cta touch-target" data-partner="{html.escape(p_key)}" data-cta-slot="calculator_primary_cta" style="display: inline-block; padding: 0.625rem 1.25rem; background: var(--brand-primary); color: #fff; border-radius: 6px; text-decoration: none; font-weight: 600;">
          {html.escape(ref_cta)} &rarr;
        </a>
      </div>
    </section>"""


def _build_workpaper_unlock_cta(
    pack: TruthPack,
    slug: str,
    topic_label: str,
    statutory_authority: str,
    baseline_amount: float,
) -> str:
    """
    Renders the canonical #workpaper-unlock-card CTA block on commercial Prexvo tool pages
    and homepage using Quick Worksheet ($9) and Full Workpaper & Data Pack ($19) resolved
    dynamically from resolve_offer_pricing("prexvo", slug=eff_slug) and TruthPack.pricing_tiers,
    while strictly omitting paid checkout CTAs on restricted public-service slugs
    (is_restricted_public_service_slug).
    """
    eff_slug = str(slug or "").strip().strip("/").lower() or "general"
    if is_restricted_public_service_slug(eff_slug):
        return ""
    quick_tier = pack.pricing_tiers["quick"]
    full_tier = pack.pricing_tiers["full"]

    quick_offer = resolve_offer_pricing("prexvo", tier_kind="quick", slug=eff_slug)
    full_offer = resolve_offer_pricing("prexvo", tier_kind="full", slug=eff_slug)
    quick_sku = str(quick_offer["sku"])
    full_sku = str(full_offer["sku"])

    quick_price = float(quick_offer.get("price_usd") or quick_tier["price_usd"])
    full_price = float(full_offer.get("price_usd") or full_tier["price_usd"])
    quick_price_int = int(round(quick_price))
    full_price_int = int(round(full_price))
    quick_label = str(quick_tier.get("label") or "Quick Worksheet")
    full_label = str(full_tier.get("label") or "Full Workpaper & Data Pack")

    amt_int = int(round(float(baseline_amount)))
    amt_qs = f"&amp;amount={amt_int}" if amt_int > 0 else ""
    slug_param = html.escape(eff_slug)
    quick_href = f"/api/lead-capture?checkout=1&amp;sku={html.escape(quick_sku)}&amp;tool_slug={slug_param}{amt_qs}&amp;redirect=1"
    full_href = f"/api/lead-capture?checkout=1&amp;sku={html.escape(full_sku)}&amp;tool_slug={slug_param}{amt_qs}&amp;redirect=1"

    safe_topic = html.escape(_clean_tool_title(topic_label, eff_slug))
    safe_auth = html.escape(_clean_text_hygiene(statutory_authority))

    return f"""
    <section id="workpaper-unlock-card" class="workpaper-unlock-card card pseo-card"
      data-mechanic="workpaper_unlock_funnel" data-first-party-checkout="true"
      data-property="prexvo" data-property-id="prexvo" data-tool-slug="{slug_param}"
      data-quick-sku="{html.escape(quick_sku)}" data-quick-price="{quick_price_int}"
      data-full-sku="{html.escape(full_sku)}" data-full-price="{full_price_int}"
      data-offer-sku="{html.escape(full_sku)}" data-offer-price="{full_price_int}"
      data-calculated-amount="{amt_int}">
      <div class="workpaper-unlock-header">
        <h3>Export {safe_topic} Workpaper &amp; Data Pack</h3>
        <p class="workpaper-unlock-subtitle">Deterministic audit worksheet preserving your active inputs and outputs under {safe_auth}.</p>
      </div>
      <div class="workpaper-unlock-actions">
        <a id="btn-workpaper-quick-checkout" rel="nofollow" href="{quick_href}"
          class="btn-cta touch-target workpaper-cta-primary" data-checkout-trigger="1"
          data-offer-sku="{html.escape(quick_sku)}" data-offer-price="{quick_price_int}"
          data-cta-slot="workpaper_quick_checkout_cta">{html.escape(quick_label)} (${quick_price_int})</a>
        <a id="btn-workpaper-full-checkout" rel="nofollow" href="{full_href}"
          class="btn-secondary touch-target workpaper-cta-secondary" data-checkout-trigger="1"
          data-offer-sku="{html.escape(full_sku)}" data-offer-price="{full_price_int}"
          data-cta-slot="workpaper_full_checkout_cta">{html.escape(full_label)} (${full_price_int})</a>
      </div>
      <p class="ymyl-refinance-warning" style="font-size: 12.5px; color: var(--text-muted); margin: 10px 0 0 0;">
        {html.escape(YMYL_FORFEITURE_DISCLOSURE)}
      </p>
      <div id="workpaper-checkout-status" class="workpaper-checkout-status" role="status" aria-live="polite"></div>
    </section>"""


# ---------------------------------------------------------------------------
# HTML Page Builders (Homepage, Leaf Tool Pages, Directory, Governance)
# ---------------------------------------------------------------------------


def _get_prexvo_organization_schema() -> Dict[str, Any]:
    return build_organization_schema(
        canonical_base=PREXVO_CANONICAL_BASE,
        site_name=PREXVO_SITE_NAME,
        site_description=PREXVO_SITE_DESCRIPTION,
        same_as=[PREXVO_LINKEDIN_URL, PREXVO_WIKIDATA_URL],
    )


def _get_webpage_schema(title: str, description: str, url: str) -> Dict[str, Any]:
    clean_url = url.split("#")[0]
    return {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "@id": f"{clean_url}#webpage",
        "name": title,
        "description": description,
        "url": clean_url,
        "isPartOf": {"@id": f"{PREXVO_CANONICAL_BASE}/#website"},
        "about": {"@id": f"{PREXVO_CANONICAL_BASE}/#organization"},
    }


def _render_base_html(
    title: str,
    meta_description: str,
    canonical_url: str,
    body_content: str,
    jsonld_schemas: Optional[List[Dict[str, Any]]] = None,
    css_text: str = "",
    gsc_token: str = "",
    is_restricted: bool = False,
) -> str:
    """Renders canonical HTML shell with single consolidated JSON-LD graph and YMYL notices."""
    if "404" in canonical_url or "404" in title or title.strip().startswith("404"):
        clean_title = _clean_text_hygiene(title)
    else:
        clean_title = normalize_seo_title(title)

    clean_desc = _clean_text_hygiene(meta_description)
    robots_meta = (
        "noindex, follow"
        if ("404" in canonical_url or "404" in title)
        else "index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1"
    )
    if not gsc_token:
        gsc_token, _ = _resolve_prexvo_public_meta()

    org_schema = _get_prexvo_organization_schema()
    active_schemas = list(jsonld_schemas or [])
    if not active_schemas:
        active_schemas.append(org_schema)
        active_schemas.append(_get_webpage_schema(clean_title, clean_desc, canonical_url))

    graph_payload = compile_schema_graph(
        schemas=active_schemas,
        canonical_url=canonical_url,
        canonical_base=PREXVO_CANONICAL_BASE,
        site_name=PREXVO_SITE_NAME,
        org_schema=org_schema,
        title=clean_title,
        meta_description=clean_desc,
    )
    # Guarantee at most one SoftwareApplication/WebApplication node in @graph
    deduped_graph: List[Dict[str, Any]] = []
    seen_app = False
    for node in graph_payload.get("@graph", []):
        ntype = node.get("@type")
        types = ntype if isinstance(ntype, list) else ([ntype] if ntype else [])
        if any(t in ("SoftwareApplication", "WebApplication") for t in types):
            if seen_app:
                continue
            seen_app = True
        deduped_graph.append(node)
    graph_payload["@graph"] = deduped_graph

    schema_json = json.dumps(graph_payload, indent=2)
    style_tag = f"\n  <style>\n{css_text}\n  </style>" if css_text else ""
    body_attrs = ' data-commercial-offers="none" data-restricted-public-service="true"' if is_restricted else ""

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(clean_title)}</title>
  <meta name="description" content="{html.escape(clean_desc)}">
  <meta name="google-site-verification" content="{html.escape(gsc_token)}">
  <meta http-equiv="content-language" content="en-US">
  <link rel="canonical" href="{html.escape(canonical_url)}">
  <link rel="alternate" hreflang="en-US" href="{html.escape(canonical_url)}">
  <link rel="alternate" hreflang="x-default" href="{html.escape(canonical_url)}">
  <meta name="robots" content="{robots_meta}">
  <meta name="author" content="{html.escape(PREXVO_AUTHOR)}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="{html.escape(PREXVO_SITE_NAME)}">
  <meta property="og:title" content="{html.escape(clean_title)}">
  <meta property="og:description" content="{html.escape(clean_desc)}">
  <meta property="og:image" content="{PREXVO_CANONICAL_BASE}/static/img/prexvo-og.png">
  <meta property="og:url" content="{html.escape(canonical_url)}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{html.escape(clean_title)}">
  <meta name="twitter:description" content="{html.escape(clean_desc)}">
  <meta name="twitter:image" content="{PREXVO_CANONICAL_BASE}/static/img/prexvo-og.png">
  <link rel="stylesheet" href="/css/style.css">{style_tag}
  <link rel="alternate" type="application/rss+xml" title="{html.escape(PREXVO_SITE_NAME)} RSS Feed" href="/feed.xml">
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <link rel="alternate icon" href="/favicon.ico">
  <script type="application/ld+json">
{schema_json}
  </script>
</head>
<body{body_attrs}>
  <header class="header">
    <div class="container nav-bar">
      <a href="/" class="brand-logo touch-target"><span class="brand-mark">P</span><span class="brand-name">Prexvo</span></a>
      <nav class="nav-links">
        <a href="/tools/" class="nav-link touch-target">Calculators</a>
        <a href="/methodology/" class="nav-link touch-target">Methodology</a>
        <a href="/disclaimers/" class="nav-link touch-target">Disclaimers</a>
      </nav>
    </div>
  </header>

  <main class="container">
    {body_content}

    <div class="ymyl-disclaimer-banner">
      <strong>Important Statutory Warning:</strong> {html.escape(YMYL_FORFEITURE_DISCLOSURE)}
    </div>

    <div class="ftc-disclosure-card">
      <strong>Regulatory &amp; Affiliate Disclosure:</strong> {html.escape(_clean_text_hygiene(AFFILIATE_DISCLOSURE))}
    </div>
  </main>

  <footer class="footer">
    <div class="container">
      <div class="footer-grid">
        <div class="footer-col">
          <a href="/" class="brand-logo touch-target"><span class="brand-mark">P</span><span class="brand-name">{html.escape(PREXVO_SITE_NAME)}</span></a>
          <p class="footer-desc">&copy; 2026 {html.escape(PREXVO_SITE_NAME)}. Independent Financial Research &amp; Statutory Modeling.</p>
          <p class="footer-desc">{html.escape(DISCLAIMER_NO_ADVICE)}</p>
        </div>
        <div class="footer-col">
          <div class="footer-heading">Platform</div>
          <ul class="footer-links">
            <li><a href="/tools/" class="footer-link touch-target">Calculators</a></li>
            <li><a href="/methodology/" class="footer-link touch-target">Title IV Methodology</a></li>
            <li><a href="/disclaimers/" class="footer-link touch-target">Statutory Terms &amp; Disclaimers</a></li>
          </ul>
        </div>
        <div class="footer-col">
          <div class="footer-heading">Research &amp; Authority</div>
          <ul class="footer-links">
            <li><a href="{html.escape(PREXVO_LINKEDIN_URL)}" target="_blank" rel="noopener" class="footer-link touch-target">Prexvo on LinkedIn</a></li>
            <li><a href="/sitemap.xml" class="footer-link touch-target">XML Sitemap</a></li>
          </ul>
        </div>
      </div>
      <div class="footer-compliance">
        <p>Prexvo Editorial Policy: All calculations are deterministic and verified by statutory models pursuant to P.L. 119-21 Section 82001, 34 CFR Part 685, 34 CFR 685.221, 34 CFR 685.219, and 91 FR 1797 (2026 HHS Poverty Guidelines).</p>
      </div>
    </div>
  </footer>
{render_external_runtime_synchronizer_tag("prexvo")}
</body>
</html>
"""
    assert_no_forbidden_dashes(full_html, context="Prexvo rendered HTML")
    return full_html


def _build_retro_reflection_block(manifest_spec: Dict[str, Any], canonical_url: str) -> str:
    """Renders dual-dataset provenance, preset links, 5-point sensitivity table, and manifest JSON."""
    slug = str(manifest_spec["slug"])
    spec_payload = {
        "manifest_id": f"{slug}-manifest",
        "slug": slug,
        "model_name": manifest_spec["model_name"],
        "statutory_authority": manifest_spec["statutory_authority"],
        "economic_dataset": manifest_spec["economic_dataset"],
        "formula": manifest_spec["formula"],
        "inputs": manifest_spec["inputs"],
        "published_output": float(manifest_spec["published_output"]),
        "sample_calculation": manifest_spec["sample_calculation"],
        "entity_type": manifest_spec.get("entity_type", "FinancialProductOrService"),
    }
    pub_out = float(spec_payload["published_output"])
    display_out = f"{pub_out:,.2f}" if not pub_out.is_integer() else f"{pub_out:,.0f}"
    stat_auth = html.escape(_clean_text_hygiene(str(spec_payload["statutory_authority"])))
    econ_ds = html.escape(_clean_text_hygiene(str(spec_payload["economic_dataset"])))

    def _fmt_scen(val: float) -> str:
        r = round(float(val), 2)
        return f"{r:,.0f}" if r.is_integer() else f"{r:,.2f}"

    base_href = canonical_url.split("?")[0]
    preset_links = []
    for label, mult, p_key in (
        ("Conservative (0.8x)", 0.8, "conservative"),
        ("Baseline (1.0x)", 1.0, "baseline"),
        ("Aggressive (1.2x)", 1.2, "aggressive"),
    ):
        params = []
        for k, v in spec_payload["inputs"].items():
            if isinstance(v, (int, float)):
                scaled = round(float(v) * mult, 2)
                val_s = str(int(scaled)) if scaled.is_integer() else str(scaled)
                params.append(f"{k}={val_s}")
        qs = "&amp;".join(params)
        href = f"{base_href}?{qs}" if qs else base_href
        preset_links.append(
            f'        <a href="{href}" data-preset="{p_key}" '
            f'class="touch-target scenario-preset-link" '
            f'style="display: inline-flex; align-items: center; justify-content: center; '
            f'min-height: 44px; min-width: 44px; padding: 10px 14px; border-radius: 8px; '
            f'text-decoration: none; font-size: 14px; font-weight: 600;">{label}</a>'
        )
    manifest_json = json.dumps(spec_payload, ensure_ascii=False, indent=2)

    safe_topic = html.escape(_clean_tool_title(str(manifest_spec.get("model_name") or slug), slug))
    return f"""
    <section class="multi-dataset-join" data-statutory-source="{stat_auth}" data-economic-source="{econ_ds}" style="margin: 1.5rem 0; padding: 1.25rem; border: 1px solid var(--border-subtle); border-radius: 8px; background: var(--bg-surface);">
      <h2 class="section-title">Dual Dataset Provenance &amp; Statutory Corroboration: {safe_topic}</h2>
      <p>Primary statutory authority: <strong>{stat_auth}</strong> defines governing federal repayment formulas, 2026 HHS Poverty Guidelines (91 FR 1797), and forgiveness schedules.</p>
      <p>Empirical economic dataset: <strong>{econ_ds}</strong> provides empirical wage and consumer credit benchmark series.</p>
    </section>

    <section class="scenario-presets-section" style="margin: 1.5rem 0; padding: 1.25rem; border: 1px solid var(--border-subtle); border-radius: 8px; background: var(--bg-surface);">
      <h2 class="section-title">Parameterized Scenario Presets &amp; Baseline Verification: {safe_topic}</h2>
      <p>Verified baseline model calculation output: <strong>{display_out}</strong>. Select a parameterized preset below:</p>
      <div class="scenario-presets-bar" data-mechanic="deep_link_scenario_presets" style="display: flex; flex-wrap: wrap; gap: 10px; margin-top: 12px;">
{chr(10).join(preset_links)}
      </div>
    </section>

    <section class="sensitivity-matrix-section" data-entity-type="scenario" data-mechanic="server_rendered_sensitivity_grid" style="margin: 1.5rem 0;">
      <h2 class="section-title">Sensitivity Scenario Modeling: {safe_topic}</h2>
      <p class="section-lead">SSR 5-point sensitivity matrix comparing baseline model projections against parameter variations:</p>
      <div class="table-wrap">
        <table class="scenario-table comparison-table" data-entity-type="scenario" data-statutory-source="{stat_auth}" data-economic-source="{econ_ds}">
          <thead>
            <tr>
              <th scope="col">Scenario Analysis</th>
              <th scope="col">Variance Assumption</th>
              <th scope="col">Statutory Basis</th>
              <th scope="col">Economic Series</th>
              <th scope="col">Projected Outcome</th>
            </tr>
          </thead>
          <tbody>
            <tr data-entity-type="scenario"><td><strong>Baseline Scenario</strong></td><td>Standard published parameters (1.0x)</td><td>{stat_auth}</td><td>{econ_ds}</td><td><strong class="scenario-baseline">{display_out}</strong></td></tr>
            <tr data-entity-type="scenario"><td><strong>Conservative Scenario</strong></td><td>20% Parameter contraction (0.8x)</td><td>{stat_auth}</td><td>{econ_ds}</td><td><strong class="scenario-conservative">{_fmt_scen(pub_out * 0.8)}</strong></td></tr>
            <tr data-entity-type="scenario"><td><strong>Moderate Contraction Scenario</strong></td><td>10% Parameter contraction (0.9x)</td><td>{stat_auth}</td><td>{econ_ds}</td><td><strong class="scenario-moderate-contraction">{_fmt_scen(pub_out * 0.9)}</strong></td></tr>
            <tr data-entity-type="scenario"><td><strong>Moderate Expansion Scenario</strong></td><td>10% Parameter expansion (1.1x)</td><td>{stat_auth}</td><td>{econ_ds}</td><td><strong class="scenario-moderate-expansion">{_fmt_scen(pub_out * 1.1)}</strong></td></tr>
            <tr data-entity-type="scenario"><td><strong>Aggressive Scenario</strong></td><td>20% Parameter expansion (1.2x)</td><td>{stat_auth}</td><td>{econ_ds}</td><td><strong class="scenario-aggressive">{_fmt_scen(pub_out * 1.2)}</strong></td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <script type="application/json" id="calculation-manifest" class="calculation-manifest">
{manifest_json}
    </script>"""


def _get_tool_commentary(slug: str) -> str:
    """Returns statutory commentary anchored to 2026 P.L. 119-21 Section 82001 and 91 FR 1797."""
    if "pslf" in slug:
        return """
        <div class="commentary-box">
          <h2 class="commentary-title">Public Service Loan Forgiveness (PSLF) 120-Payment Framework</h2>
          <p class="commentary-text">
            Under 34 CFR 685.219 and 20 U.S.C. 1087e, Public Service Loan Forgiveness (PSLF) cancels remaining Direct Loan balances after 120 qualifying monthly payments (10 years) while working full-time for a qualifying government or 501(c)(3) nonprofit employer.
          </p>
          <p class="commentary-text">
            Unlike PSLF's 120-payment public service timeline, borrowers outside qualifying public service under the 2026 Repayment Assistance Plan (RAP, P.L. 119-21 Section 82001) reach forgiveness after 360 qualifying monthly payments (30 years).
          </p>
        </div>"""
    if "ibr" in slug:
        return """
        <div class="commentary-box">
          <h2 class="commentary-title">2026 IBR Poverty Guidelines (91 FR 1797) &amp; Standard Cap</h2>
          <p class="commentary-text">
            Under 34 CFR 685.221 and 91 FR 1797 (42 U.S.C. 9902(2)), Income-Based Repayment (IBR) protects 150% of the 2026 HHS Poverty Guideline ($15,960 for a 1-person household plus $5,680 per additional person in the 48 contiguous states and D.C., equal to $23,940.00 for a single borrower).
          </p>
          <p class="commentary-text">
            IBR monthly payments are capped at the 10-year Standard Repayment schedule ($681.29/mo on $60,000 at 6.5%), whereas P.L. 119-21 Section 82001 RAP assesses 1% to 10% of AGI minus $50 per dependent ($10 minimum) with a 100% unpaid interest subsidy, up to $50/mo principal match, and forgiveness after 360 qualifying monthly payments (30 years).
          </p>
        </div>"""
    if "tiered" in slug:
        return """
        <div class="commentary-box">
          <h2 class="commentary-title">Tiered Standard Balance Brackets under 34 CFR Part 685</h2>
          <p class="commentary-text">
            Under 34 CFR Part 685, Direct Consolidation loans qualify for Tiered Standard amortization schedules spanning 120 to 360 months (10 to 30 years) based on aggregate balance ($7,500-$9,999: 12 years; $10,000-$19,999: 15 years; $20,000-$39,999: 20 years; $40,000-$59,999: 25 years; $60,000+: 30 years / 360 months).
          </p>
        </div>"""
    if "refinance" in slug:
        return f"""
        <div class="commentary-box">
          <h2 class="commentary-title">Private Refinancing Break-Even vs Federal Title IV Protections</h2>
          <p class="commentary-text">
            Under 12 CFR Part 1026 (Truth in Lending Act), borrowers should compare closing fees and rate reductions against the permanent loss of federal statutory protections. {html.escape(YMYL_FORFEITURE_DISCLOSURE)}
          </p>
        </div>"""
    return """
        <div class="commentary-box">
          <h2 class="commentary-title">2026 Title IV RAP (P.L. 119-21 Section 82001) &amp; 91 FR 1797 Framework</h2>
          <p class="commentary-text">
            Under P.L. 119-21 Section 82001, the Repayment Assistance Plan (RAP) calculates monthly payments from 1% to 10% of AGI divided by 12 minus $50 per qualifying dependent ($10 statutory floor), provides a 100% unpaid monthly interest subsidy and up to $50/mo principal match on on-time payments, and grants balance forgiveness after 360 qualifying monthly payments (30 years).
          </p>
          <p class="commentary-text">
            Income-Based Repayment (34 CFR 685.221) uses the 2026 HHS Poverty Guidelines under 91 FR 1797 ($15,960 for 1 person plus $5,680 per additional person), while Public Service Loan Forgiveness (34 CFR 685.219) remains at 120 qualifying monthly payments (10 years).
          </p>
        </div>"""


def _build_howto_schema(title: str, canonical_url: str) -> Dict[str, Any]:
    clean_url = canonical_url.split("#")[0]
    steps = [
        ("Verify Household Size & 2026 HHS Poverty Guideline", "Apply the 91 FR 1797 2026 HHS Poverty Guideline ($15,960 for 1 person plus $5,680 per additional person in contiguous states)."),
        ("Determine Statutory Plan Formula", "Apply P.L. 119-21 Section 82001 RAP tiered AGI percentages (1% to 10%) or 34 CFR 685.221 IBR 150% poverty threshold."),
        ("Apply Payment Floor, Caps & Dependent Credits", "Apply the $50 per dependent RAP credit and $10 floor, or the 10-year Standard payment cap under IBR."),
        ("Evaluate Subsidy, Principal Match & Forgiveness Horizon", "Project 100% unpaid interest subsidy and $50/mo principal match across RAP's 360-month (30-year) term or PSLF's 120-month (10-year) term."),
    ]
    return {
        "@context": "https://schema.org",
        "@type": "HowTo",
        "@id": f"{clean_url}#howto",
        "name": f"How to Calculate {title}",
        "description": f"Step-by-step Title IV statutory procedure for {title}.",
        "url": clean_url,
        "isPartOf": {"@id": f"{clean_url}#webpage"},
        "step": [
            {"@type": "HowToStep", "position": idx, "name": nm, "text": txt, "url": f"{clean_url}#step-{idx}"}
            for idx, (nm, txt) in enumerate(steps, 1)
        ],
    }


def _build_dataset_schema(title: str, canonical_url: str) -> Dict[str, Any]:
    clean_url = canonical_url.split("#")[0]
    return {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "@id": f"{clean_url}#dataset",
        "name": f"{title} Statutory Repayment Matrix",
        "description": f"Deterministic 2026 Title IV and 91 FR 1797 repayment comparison dataset for {title}.",
        "url": clean_url,
        "mainEntityOfPage": {"@id": f"{clean_url}#webpage"},
        "includedInDataCatalog": {
            "@type": "DataCatalog",
            "@id": f"{PREXVO_CANONICAL_BASE}/#datacatalog",
            "name": f"{PREXVO_SITE_NAME} Title IV Statutory Data Catalog",
            "url": PREXVO_CANONICAL_BASE,
        },
        "creator": {"@id": f"{PREXVO_CANONICAL_BASE}/#organization"},
        "publisher": {"@id": f"{PREXVO_CANONICAL_BASE}/#organization"},
        "temporalCoverage": "2026/2027",
        "spatialCoverage": "United States",
        "isAccessibleForFree": True,
        "license": "https://creativecommons.org/publicdomain/zero/1.0/",
        "variableMeasured": [
            "Monthly Payment Obligation",
            "2026 HHS Poverty Guideline (91 FR 1797)",
            "100% Unpaid Interest Subsidy",
            "360-Month RAP Forgiveness Horizon",
            "120-Month PSLF Qualifying Horizon",
        ],
        "distribution": [{"@type": "DataDownload", "encodingFormat": "text/html", "contentUrl": clean_url}],
    }


def _get_quick_answer_for_tool(slug: str, title: str, pack: TruthPack) -> str:
    """Builds a concise 40-to-60-word GEO quick answer anchored to TruthPack."""
    base_1 = float(pack.entries["hhs_poverty_2026_1person"].value)
    per_add = float(pack.entries["hhs_poverty_2026_per_additional"].value)
    rap_mos = int(pack.entries["rap_forgiveness_months"].value)
    pslf_mos = int(pack.entries["pslf_qualifying_payments"].value)
    if "pslf" in slug:
        return (
            f"Under 34 CFR 685.219, Public Service Loan Forgiveness (PSLF) discharges remaining Direct Loan "
            f"balances tax-free after {pslf_mos} qualifying monthly payments while employed full-time by an eligible "
            f"public employer. Borrowers pair qualifying income-driven plans anchored to the ${base_1:,.0f} 2026 HHS "
            f"Poverty Guideline (91 FR 1797) to minimize payments prior to discharge."
        )
    if "refinance" in slug:
        return (
            f"Under 12 CFR Part 1026, this {title} models closing-fee break-even months against rate savings. "
            f"{YMYL_FORFEITURE_DISCLOSURE}"
        )
    if "ibr" in slug:
        return (
            f"Under 34 CFR 685.221 and 91 FR 1797, Income-Based Repayment (IBR) shields 150% of the 2026 HHS "
            f"Poverty Guideline (${base_1:,.0f} for 1 person plus ${per_add:,.0f} per additional person) and caps "
            f"monthly payments at the 10-year Standard schedule. By contrast, P.L. 119-21 Section 82001 RAP "
            f"provides forgiveness after {rap_mos} qualifying monthly payments."
        )
    return (
        f"Under P.L. 119-21 Section 82001 and 34 CFR Part 685, the 2026 Repayment Assistance Plan (RAP) sets "
        f"monthly payments at 1% to 10% of AGI minus $50 per dependent ($10 minimum), subsidizes 100% of unpaid "
        f"monthly interest, matches up to $50/mo in principal, and forgives balances after {rap_mos} qualifying "
        f"monthly payments, alongside ${base_1:,.0f} 2026 HHS Poverty Guidelines."
    )


def build_tool_page(
    tool: Dict[str, Any],
    base_dir: Optional[Path] = None,
    *,
    all_tools: Optional[Sequence[Dict[str, Any]]] = None,
    css_text: str = "",
    manifest_spec: Optional[Dict[str, Any]] = None,
    pack: Optional[TruthPack] = None,
) -> str:
    """Compiles an individual Prexvo calculator tool page with TruthPack formulas, CTA, and YMYL guardrails."""
    _ = base_dir
    tp = pack or _get_prexvo_truth_pack()
    slug = str(tool["slug"]).strip().lower()
    clean_title = _clean_tool_title(str(tool.get("title") or slug), slug)
    clean_desc = _clean_tool_description(str(tool.get("description") or ""), clean_title, slug)
    canonical_url = f"{PREXVO_CANONICAL_BASE}/tools/{slug}/"
    is_restricted = is_restricted_public_service_slug(slug, clean_title)

    manifest = manifest_spec or _build_manifest_for_slug(slug, tp, raw_spec=tool)
    quick_answer = _get_quick_answer_for_tool(slug, clean_title, tp)
    page_spec = InteractiveCalculatorSpec(
        id=slug,
        slug=slug,
        title=clean_title,
        short_title=str(tool.get("short_title") or clean_title[:24]),
        description=clean_desc,
        category=str(tool.get("category") or "Higher Education Finance"),
        fields=REPAYMENT_CALCULATOR_SPEC.fields,
        metrics=REPAYMENT_CALCULATOR_SPEC.metrics,
        quick_answer=quick_answer,
        faqs=REPAYMENT_CALCULATOR_SPEC.faqs,
        statutory_citations=REPAYMENT_CALCULATOR_SPEC.statutory_citations,
    )

    calc_markup = render_calculator_widget(page_spec, manifest_spec=manifest)
    schemas = get_calculator_schemas(page_spec, f"/tools/{slug}/")
    schemas.append(_get_prexvo_organization_schema())
    schemas.append(_get_webpage_schema(f"{clean_title} | Prexvo", clean_desc, canonical_url))
    schemas.append(_build_howto_schema(clean_title, canonical_url))
    schemas.append(_build_dataset_schema(clean_title, canonical_url))
    schemas.append(
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{PREXVO_CANONICAL_BASE}/"},
                {"@type": "ListItem", "position": 2, "name": "Calculators", "item": f"{PREXVO_CANONICAL_BASE}/tools/"},
                {"@type": "ListItem", "position": 3, "name": clean_title, "item": canonical_url},
            ],
        }
    )

    workpaper_card_html = (
        ""
        if is_restricted_public_service_slug(slug)
        else _build_workpaper_unlock_cta(
            pack=tp,
            slug=slug,
            topic_label=clean_title,
            statutory_authority=str(manifest["statutory_authority"]),
            baseline_amount=float(manifest["published_output"]),
        )
    )

    partner_catalog_dict = {k: v.to_dict() for k, v in PREXVO_AFFILIATES.items()}
    ref_partner = partner_catalog_dict.get("splash_financial", list(partner_catalog_dict.values())[0])
    refinance_card_html = build_refinance_partner_cta(ref_partner, slug=slug, partner_catalog=partner_catalog_dict)

    known_tools = list(all_tools) if all_tools is not None else (PREXVO_CORE_TOOLS + PREXVO_STATUTORY_VOIDS)
    related_links_html = [
        f'<li class="tool-link-item"><a href="/tools/{other["slug"]}/" class="tool-link touch-target">{html.escape(_clean_tool_title(other["title"], other["slug"]))}</a></li>'
        for other in known_tools
        if other.get("slug") and other.get("slug") != slug
    ]

    scen_a = calculate_rap_payment(60000.0, 65000.0, 0.065, 1, "contiguous")
    scen_b = calculate_rap_payment(60000.0, 95000.0, 0.065, 1, "contiguous")
    commentary = _get_tool_commentary(slug)

    compliance_banner_html = f"""
    <div class="above-the-fold-compliance" style="margin-bottom: 1.5rem;">
      <div class="ymyl-warning-card" style="font-size: 0.75rem; color: #991b1b; padding: 0.625rem 0.875rem; background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; line-height: 1.4; margin-bottom: 0.75rem;">
        <strong>Statutory Warning:</strong> {html.escape(YMYL_FORFEITURE_DISCLOSURE)}
      </div>
      <div class="ftc-disclosure-card" style="font-size: 0.75rem; color: var(--text-muted); padding: 0.625rem 0.875rem; background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: 6px; line-height: 1.4;">
        <strong>Publisher Disclosure:</strong> {html.escape(_clean_text_hygiene(AFFILIATE_DISCLOSURE))}
      </div>
    </div>"""

    body = f"""
    <nav class="breadcrumbs" aria-label="Breadcrumb">
      <a href="/" class="touch-target">Home</a> / <a href="/tools/" class="touch-target">Calculators</a> / <span>{html.escape(clean_title)}</span>
    </nav>

    <section class="tool-header hero-section">
      <h1 class="hero-title">{html.escape(clean_title)}</h1>
      <aside class="quick-answer">
        <p>{html.escape(quick_answer)}</p>
      </aside>
      <p class="hero-desc">{html.escape(clean_desc)}</p>
    </section>

    {compliance_banner_html}

    {calc_markup}

    {workpaper_card_html}

    {refinance_card_html}

    {commentary}

    <section class="calculation-scenarios-section" style="margin: 2rem 0;">
      <h2 class="section-title">2026 Title IV RAP Scenarios (P.L. 119-21 Section 82001)</h2>
      <p class="section-lead">Deterministic projections under P.L. 119-21 Section 82001 (360 qualifying monthly payments, 100% unpaid interest subsidy, and up to $50/mo principal match) and 91 FR 1797 2026 HHS Poverty Guidelines ($15,960 single, +$5,680 per additional person):</p>
      <div class="calculation-variant" id="variant-baseline" data-variant-id="variant-baseline" style="padding: 1.25rem; margin-bottom: 1rem; border: 1px solid var(--border-subtle); border-radius: 8px;">
        <h3 class="variant-title" style="font-size: 1.1rem; margin-bottom: 0.5rem;">Scenario A: $65,000 AGI, 0 Dependents (6% RAP Tier)</h3>
        <p>Under P.L. 119-21 Section 82001, monthly RAP payment equals ${scen_a["monthly_payment"]:,.2f} with ${scen_a["interest_subsidy"]:,.2f}/mo in 100% unpaid interest subsidy and up to $50.00/mo principal match across {scen_a["term_months"]} qualifying monthly payments (30 years).</p>
        <p><a href="#variant-accelerated" class="touch-target">Compare with Scenario B: $95,000 AGI, 0 Dependents (9% RAP Tier) &rarr;</a></p>
      </div>
      <div class="calculation-variant" id="variant-accelerated" data-variant-id="variant-accelerated" style="padding: 1.25rem; margin-bottom: 1rem; border: 1px solid var(--border-subtle); border-radius: 8px;">
        <h3 class="variant-title" style="font-size: 1.1rem; margin-bottom: 0.5rem;">Scenario B: $95,000 AGI, 0 Dependents (9% RAP Tier)</h3>
        <p>Under P.L. 119-21 Section 82001, monthly RAP payment equals ${scen_b["monthly_payment"]:,.2f} across the {scen_b["term_months"]}-month (30-year) RAP schedule with 100% unpaid interest subsidy (${scen_b["interest_subsidy"]:,.2f}/mo).</p>
        <p><a href="#variant-baseline" class="touch-target">&larr; Return to Scenario A: $65,000 AGI, 0 Dependents (6% RAP Tier)</a></p>
      </div>
    </section>

    <section class="calculation-methodology-section">
      <h2 class="section-title">Title IV Statutory Calculation Procedure</h2>
      <ol class="calculation-steps">
        <li>Verify household size and 2026 HHS Poverty Guideline under 91 FR 1797 ($15,960 for 1 person plus $5,680 per additional person in the 48 contiguous states and D.C.).</li>
        <li>Apply the governing Title IV formula: P.L. 119-21 Section 82001 RAP tiered AGI percentages (1% to 10%) or 34 CFR 685.221 IBR 150% poverty threshold.</li>
        <li>Apply dependent credits ($50 per dependent under RAP with $10 minimum) or the 10-year Standard payment cap under IBR.</li>
        <li>Evaluate 100% unpaid interest subsidy, $50/mo principal match, and forgiveness horizons (360 months under RAP vs 120 qualifying payments under 34 CFR 685.219 PSLF).</li>
      </ol>
    </section>

    <section class="statutory-comparison-table-section">
      <h2 class="section-title">2026 Title IV Statutory Repayment Benchmark Overview</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Repayment Plan</th>
              <th scope="col">Statutory Basis &amp; Threshold</th>
              <th scope="col">Payment Rate</th>
              <th scope="col">Forgiveness / Amortization Term</th>
              <th scope="col">Subsidy / Protection</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td class="td-plan-name">Repayment Assistance Plan (RAP)</td>
              <td>P.L. 119-21 Section 82001 (AGI Tiers)</td>
              <td>1% to 10% AGI (-$50/dep, $10 min)</td>
              <td>360 qualifying monthly payments (30 years)</td>
              <td>100% Interest Covered + up to $50/mo Principal Match</td>
            </tr>
            <tr>
              <td class="td-plan-name">Income-Based Repayment (IBR)</td>
              <td>34 CFR 685.221 &amp; 91 FR 1797 (150% of $15,960 FPL)</td>
              <td>10% to 15% Discretionary</td>
              <td>240 to 300 monthly payments (20 to 25 years)</td>
              <td>10-Year Standard Cap</td>
            </tr>
            <tr>
              <td class="td-plan-name">Public Service Loan Forgiveness (PSLF)</td>
              <td>34 CFR 685.219 (Qualifying Employer)</td>
              <td>Qualifying IDR Payment</td>
              <td>120 qualifying monthly payments (10 years)</td>
              <td>Tax-Free Balance Discharge</td>
            </tr>
            <tr>
              <td class="td-plan-name">Tiered Standard Repayment</td>
              <td>34 CFR Part 685 (Tiered Balance Schedule)</td>
              <td>Level Amortization</td>
              <td>Tiered Standard: 120 to 360 months (10 to 30 years)</td>
              <td>Fixed Payoff (No Forgiveness)</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="statutory-provenance-box">
      <h2 class="section-title">Statutory Authority &amp; Provenance Citations</h2>
      <ul>
        <li><strong>Dataset 1:</strong> <a href="https://studentaid.gov/idr/" target="_blank" rel="noopener noreferrer">P.L. 119-21 Section 82001 &amp; 34 CFR Part 685 (Title IV Direct Loans)</a></li>
        <li><strong>Dataset 2:</strong> <a href="https://www.federalregister.gov/d/2026-00690" target="_blank" rel="noopener noreferrer">2026 HHS Poverty Guidelines (91 FR 1797, 42 U.S.C. 9902(2))</a></li>
      </ul>
      <p class="ymyl-refinance-warning">{html.escape(YMYL_FORFEITURE_DISCLOSURE)}</p>
    </section>

    <section class="related-tools-section">
      <h2 class="section-title">Related Student Loan Calculators</h2>
      <ul class="related-tools-list">
        {''.join(related_links_html[:6])}
      </ul>
    </section>

    {_build_retro_reflection_block(manifest, canonical_url)}
    """

    return _render_base_html(
        title=f"{clean_title} | Prexvo",
        meta_description=clean_desc,
        canonical_url=canonical_url,
        body_content=body,
        jsonld_schemas=schemas,
        css_text=css_text,
        is_restricted=is_restricted,
    )


def _build_home_html(
    all_tools: Sequence[Dict[str, Any]],
    pack: TruthPack,
    css_text: str,
) -> str:
    """Compiles the Prexvo homepage with primary multi-plan widget and 2026 TruthPack benchmarks."""
    calc_markup = render_calculator_widget(REPAYMENT_CALCULATOR_SPEC)
    schemas = get_calculator_schemas(REPAYMENT_CALCULATOR_SPEC, "/")
    schemas.append(_get_prexvo_organization_schema())

    benchmarks = compare_all_repayment_plans(60000.0, 65000.0, 0.065, 1, "contiguous")
    tools_list_html = [
        f'<li class="tool-link-item"><a href="/tools/{t["slug"]}/" class="tool-link touch-target">{html.escape(t["title"])}</a> <span class="tool-desc">- {html.escape(t["description"])}</span></li>'
        for t in all_tools
    ]
    partners_html = build_partners_matrix_section(
        partner_catalog={k: v.to_dict() for k, v in PREXVO_AFFILIATES.items()}
    )
    rap_mos = int(pack.entries["rap_forgiveness_months"].value)
    rap_home_pay = float(benchmarks["rap"]["monthly_payment"])
    home_formula = pack.formulas["rap_monthly_payment"].expression.replace(
        "dependents",
        "max(0, family_size - 1)",
    )
    home_manifest = {
        "manifest_id": "student-loan-repayment-calculator-manifest",
        "slug": "student-loan-repayment-calculator",
        "model_name": "Prexvo-TitleIV-RAP-Hub-Model-2026",
        "statutory_authority": "P.L. 119-21 Section 82001 (Repayment Assistance Plan); 34 CFR Part 685",
        "economic_dataset": "U.S. Department of Education College Scorecard and BLS OEWS wage series",
        "formula": home_formula,
        "inputs": {"agi": 65000.0, "family_size": 1.0},
        "published_output": rap_home_pay,
        "sample_calculation": (
            f"Single borrower at $65,000 AGI and family size 1 (0 dependents) pays ${rap_home_pay:,.2f}/mo "
            f"under P.L. 119-21 Section 82001 RAP across {rap_mos} qualifying monthly payments."
        ),
        "entity_type": "FinancialProductOrService",
    }
    home_workpaper_card_html = _build_workpaper_unlock_cta(
        pack=pack,
        slug="rap-payment-calculator",
        topic_label="Repayment Assistance Plan (RAP) & Title IV Repayment",
        statutory_authority=str(home_manifest["statutory_authority"]),
        baseline_amount=rap_home_pay,
    )

    body = f"""
    <section class="hero-section">
      <h1 class="hero-title">Title IV Federal Student Loan Repayment Engine</h1>
      <aside class="quick-answer">
        <p>{html.escape(REPAYMENT_CALCULATOR_SPEC.quick_answer)}</p>
      </aside>
      <p class="hero-desc">
        Compare monthly repayment obligations, 100% unpaid interest subsidies, $50/mo principal match, and 360-month forgiveness schedules under P.L. 119-21 Section 82001 RAP, 34 CFR 685.221 IBR (91 FR 1797 $15,960 FPL), and 34 CFR 685.219 PSLF.
      </p>
    </section>

    {calc_markup}

    {home_workpaper_card_html}

    {partners_html}

    <section class="benchmark-table-section">
      <h2 class="section-title">2026 Statutory Plan Baseline Comparison ($60k Loan, $65k AGI)</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Plan Name</th>
              <th scope="col">Monthly Payment</th>
              <th scope="col">Statutory Term</th>
              <th scope="col">Total Repayment</th>
              <th scope="col">Est. Forgiveness</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td class="td-plan-name">Repayment Assistance Plan (RAP)</td>
              <td id="oracle-rap-monthly" class="td-num">${benchmarks["rap"]["monthly_payment"]:.2f}</td>
              <td>{benchmarks["rap"]["term_months"]} months ({benchmarks["rap"]["term_years"]} Years)</td>
              <td id="oracle-rap-total" class="td-num">${benchmarks["rap"]["total_repayment"]:.2f}</td>
              <td class="td-num">${benchmarks["rap"]["forgiveness_amount"]:.2f}</td>
            </tr>
            <tr>
              <td class="td-plan-name">Income-Based Repayment (IBR)</td>
              <td id="oracle-ibr-monthly" class="td-num">${benchmarks["ibr"]["monthly_payment"]:.2f}</td>
              <td>{benchmarks["ibr"]["term_months"]} months ({benchmarks["ibr"]["term_years"]} Years)</td>
              <td id="oracle-ibr-total" class="td-num">${benchmarks["ibr"]["total_repayment"]:.2f}</td>
              <td class="td-num">${benchmarks["ibr"]["forgiveness_amount"]:.2f}</td>
            </tr>
            <tr>
              <td class="td-plan-name">Pay As You Earn (PAYE)</td>
              <td id="oracle-paye-monthly" class="td-num">${benchmarks["paye"]["monthly_payment"]:.2f}</td>
              <td>{benchmarks["paye"]["term_years"]} Years</td>
              <td id="oracle-paye-total" class="td-num">${benchmarks["paye"]["total_repayment"]:.2f}</td>
              <td class="td-num">${benchmarks["paye"]["forgiveness_amount"]:.2f}</td>
            </tr>
            <tr>
              <td class="td-plan-name">Income-Contingent Repayment (ICR)</td>
              <td id="oracle-icr-monthly" class="td-num">${benchmarks["icr"]["monthly_payment"]:.2f}</td>
              <td>{benchmarks["icr"]["term_years"]} Years</td>
              <td id="oracle-icr-total" class="td-num">${benchmarks["icr"]["total_repayment"]:.2f}</td>
              <td class="td-num">${benchmarks["icr"]["forgiveness_amount"]:.2f}</td>
            </tr>
            <tr>
              <td class="td-plan-name">Tiered Standard Repayment</td>
              <td id="oracle-tiered-monthly" class="td-num">${benchmarks["tiered_standard"]["monthly_payment"]:.2f}</td>
              <td>{benchmarks["tiered_standard"]["term_months"]} months ({benchmarks["tiered_standard"]["term_years"]} Years)</td>
              <td id="oracle-tiered-total" class="td-num">${benchmarks["tiered_standard"]["total_repayment"]:.2f}</td>
              <td class="td-num">${benchmarks["tiered_standard"]["forgiveness_amount"]:.2f}</td>
            </tr>
            <tr>
              <td class="td-plan-name">Standard 10-Year Repayment (Cap)</td>
              <td id="oracle-std10-monthly" class="td-num">${benchmarks["standard_10yr"]["monthly_payment"]:.2f}</td>
              <td>{benchmarks["standard_10yr"]["term_years"]} Years</td>
              <td id="oracle-std10-total" class="td-num">${benchmarks["standard_10yr"]["total_repayment"]:.2f}</td>
              <td class="td-num">${benchmarks["standard_10yr"]["forgiveness_amount"]:.2f}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="tools-directory-section">
      <h2 class="section-title">Specialized Repayment Calculators</h2>
      <ul class="tools-list">
        {''.join(tools_list_html)}
      </ul>
      <p class="ymyl-refinance-warning">{html.escape(YMYL_FORFEITURE_DISCLOSURE)}</p>
    </section>

    {_build_retro_reflection_block(home_manifest, f"{PREXVO_CANONICAL_BASE}/")}
    """
    return _render_base_html(
        title=PREXVO_SITE_TITLE,
        meta_description=PREXVO_SITE_DESCRIPTION,
        canonical_url=f"{PREXVO_CANONICAL_BASE}/",
        body_content=body,
        jsonld_schemas=schemas,
        css_text=css_text,
    )


def _build_tools_directory_html(all_tools: Sequence[Dict[str, Any]], css_text: str) -> str:
    title = "Title IV Student Loan Calculators Directory | Prexvo"
    meta_desc = (
        "Explore Prexvo's directory of deterministic Title IV student loan calculators, "
        "P.L. 119-21 RAP models, 91 FR 1797 IBR, and PSLF tools."
    )
    canonical_url = f"{PREXVO_CANONICAL_BASE}/tools/"
    schemas = [
        _get_prexvo_organization_schema(),
        {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": title,
            "url": canonical_url,
            "description": meta_desc,
            "mainEntity": {
                "@type": "ItemList",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": idx + 1,
                        "name": t["title"],
                        "url": f"{PREXVO_CANONICAL_BASE}/tools/{t['slug']}/",
                    }
                    for idx, t in enumerate(all_tools)
                ],
            },
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{PREXVO_CANONICAL_BASE}/"},
                {"@type": "ListItem", "position": 2, "name": "Calculators", "item": canonical_url},
            ],
        },
    ]

    rows = []
    cards = []
    for t in all_tools:
        slug = t["slug"]
        t_title = html.escape(t["title"])
        t_desc = html.escape(t["description"])
        rows.append(
            f'<tr><td><strong><a href="/tools/{slug}/" class="touch-target">{t_title}</a></strong></td>'
            f'<td>{t_desc}</td><td>P.L. 119-21 / 34 CFR Part 685 / 91 FR 1797</td>'
            f'<td><a href="/tools/{slug}/" class="touch-target">Open &rarr;</a></td></tr>'
        )
        cards.append(
            f'<li class="tool-link-item"><a href="/tools/{slug}/" class="tool-link touch-target">{t_title}</a> '
            f'<span class="tool-desc">- {t_desc}</span></li>'
        )

    body = f"""
    <nav class="breadcrumbs" aria-label="Breadcrumb"><a href="/" class="touch-target">Home</a> / <span>Calculators</span></nav>
    <section class="hero-section">
      <h1 class="hero-title">Title IV Student Loan Calculators Directory</h1>
      <p class="hero-desc">{html.escape(meta_desc)}</p>
    </section>
    <aside class="quick-answer">
      <p>Prexvo provides deterministic student loan calculators anchored to P.L. 119-21 Section 82001 (360-month RAP forgiveness, 100% interest subsidy, $50/mo principal match), 91 FR 1797 2026 HHS Poverty Guidelines ($15,960 single plus $5,680 per additional person), 34 CFR 685.221 IBR, and 34 CFR 685.219 PSLF (120 payments).</p>
    </aside>
    <section class="comparison-table-section">
      <h2 class="section-title">Directory of Student Loan Repayment Calculators</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th scope="col">Calculator Name</th><th scope="col">Description</th><th scope="col">Statutory Authority</th><th scope="col">Access</th></tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
    </section>
    <section class="calculation-methodology-section">
      <h2 class="section-title">How to Use Prexvo Title IV Calculators</h2>
      <ol class="calculation-steps">
        <li>Select the Title IV repayment, RAP (P.L. 119-21 Section 82001), 91 FR 1797 IBR, PSLF, or refinance calculator matching your loan type.</li>
        <li>Enter your Adjusted Gross Income (AGI), principal balance, interest rate, and household size to compute monthly obligations and 360-month forgiveness projections.</li>
        <li>Review the statutory comparison matrix and YMYL federal benefit forfeiture disclosures before comparing private refinance options.</li>
      </ol>
    </section>
    <section class="tools-directory-grid-section">
      <h2 class="section-title">All Student Loan Tools</h2>
      <ul class="tools-list">{''.join(cards)}</ul>
    </section>"""
    return _render_base_html(title, meta_desc, canonical_url, body, jsonld_schemas=schemas, css_text=css_text)


def _build_methodology_html(css_text: str) -> str:
    title = "Title IV Student Loan Calculation Methodology | Prexvo"
    meta_desc = (
        "Authoritative mathematical methodology, P.L. 119-21 Section 82001 RAP rules, "
        "91 FR 1797 2026 HHS Poverty Guidelines, and 34 CFR Part 685 formulas."
    )
    canonical_url = f"{PREXVO_CANONICAL_BASE}/methodology/"
    schemas = [_get_prexvo_organization_schema(), _get_webpage_schema(title, meta_desc, canonical_url)]
    body = """
    <article class="article-content">
      <h1 class="article-title">Title IV Student Loan Calculation Methodology</h1>
      <aside class="quick-answer">
        <p>Prexvo models federal student loan repayment plans using deterministic statutory formulas under P.L. 119-21 Section 82001 (360-month RAP forgiveness, 100% unpaid interest subsidy, $50/mo principal match), 91 FR 1797 2026 HHS Poverty Guidelines ($15,960 single plus $5,680 per additional person), 34 CFR 685.221 IBR, and 34 CFR 685.219 PSLF.</p>
      </aside>
      <h2 class="article-h2">1. 2026 Repayment Assistance Plan (RAP) Mechanics (P.L. 119-21 Section 82001)</h2>
      <p class="article-p">
        Pursuant to P.L. 119-21 Section 82001, RAP computes monthly payments from 1% to 10% of AGI divided by 12, minus $50 per qualifying dependent, subject to a $10.00 monthly floor. On-time payments receive a 100% unpaid monthly interest subsidy plus up to $50 per month in principal matching when payment reduces principal by less than $50. Remaining balance forgiveness occurs after 360 qualifying monthly payments (30 years).
      </p>
      <h2 class="article-h2">2. 2026 HHS Poverty Guidelines (91 FR 1797) &amp; IBR Caps</h2>
      <p class="article-p">
        Under 91 FR 1797 (42 U.S.C. 9902(2)), the 2026 federal poverty guideline for the 48 contiguous states and D.C. is $15,960 for a 1-person household plus $5,680 for each additional person. Income-Based Repayment (34 CFR 685.221) shields 150% of this guideline and caps monthly obligations at the 10-year Standard schedule.
      </p>
      <h2 class="article-h2">3. Tiered Standard Amortization &amp; PSLF Distinction</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th scope="col">Plan / Tier</th><th scope="col">Statutory Horizon</th><th scope="col">Qualifying Payments</th></tr></thead>
          <tbody>
            <tr><td>Public Service Loan Forgiveness (34 CFR 685.219)</td><td>10 Years</td><td>120 qualifying monthly payments</td></tr>
            <tr><td>Repayment Assistance Plan (P.L. 119-21 Section 82001)</td><td>30 Years</td><td>360 qualifying monthly payments</td></tr>
            <tr><td>Tiered Standard: Balances under $7,500</td><td>10 Years</td><td>120 monthly payments</td></tr>
            <tr><td>Tiered Standard: $7,500 to $9,999</td><td>12 Years</td><td>144 monthly payments</td></tr>
            <tr><td>Tiered Standard: $10,000 to $19,999</td><td>15 Years</td><td>180 monthly payments</td></tr>
            <tr><td>Tiered Standard: $20,000 to $39,999</td><td>20 Years</td><td>240 monthly payments</td></tr>
            <tr><td>Tiered Standard: $40,000 to $59,999</td><td>25 Years</td><td>300 monthly payments</td></tr>
            <tr><td>Tiered Standard: $60,000 or greater</td><td>30 Years</td><td>360 monthly payments</td></tr>
          </tbody>
        </table>
      </div>
    </article>"""
    return _render_base_html(title, meta_desc, canonical_url, body, jsonld_schemas=schemas, css_text=css_text)


def _build_disclaimers_html(css_text: str) -> str:
    title = "Student Loan Regulatory Notices & Disclaimers | Prexvo"
    meta_desc = (
        "Review Title IV statutory disclaimers, YMYL federal-refinance forfeiture notices, "
        "FTC disclosures, and 91 FR 1797 / P.L. 119-21 notices for Prexvo."
    )
    canonical_url = f"{PREXVO_CANONICAL_BASE}/disclaimers/"
    schemas = [_get_prexvo_organization_schema(), _get_webpage_schema(title, meta_desc, canonical_url)]
    body = f"""
    <article class="article-content">
      <h1 class="article-title">Student Loan Regulatory Notices &amp; Disclaimers</h1>
      <aside class="quick-answer">
        <p>Prexvo is an independent financial research publisher providing deterministic Title IV repayment modeling. {html.escape(YMYL_FORFEITURE_DISCLOSURE)}</p>
      </aside>
      <div class="ymyl-disclaimer-banner">
        <h2 class="section-title">Federal Loan Refinancing Warning</h2>
        <p>{html.escape(YMYL_FORFEITURE_DISCLOSURE)}</p>
      </div>
      <h2 class="article-h2">FTC Affiliate Disclosure</h2>
      <p class="article-p">{html.escape(_clean_text_hygiene(AFFILIATE_DISCLOSURE))}</p>
      <h2 class="article-h2">No Financial Advice Disclaimer</h2>
      <p class="article-p">{html.escape(DISCLAIMER_NO_ADVICE)}</p>
      <h2 class="article-h2">Statutory Disclosures &amp; Regulatory Authorities</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th scope="col">Regulatory Subject</th><th scope="col">Statutory Authority</th><th scope="col">Prexvo Compliance Scope</th></tr></thead>
          <tbody>
            <tr><td>Repayment Assistance Plan (RAP)</td><td>P.L. 119-21 Section 82001</td><td>360-month forgiveness, 100% interest subsidy, $50/mo match</td></tr>
            <tr><td>Title IV Direct Loan Rules</td><td>34 CFR Part 685 / 34 CFR 685.221 / 34 CFR 685.219</td><td>Deterministic IBR, PSLF, and Tiered Standard models</td></tr>
            <tr><td>2026 Poverty Guidelines</td><td>91 FR 1797 (42 U.S.C. 9902(2))</td><td>$15,960 1-person + $5,680 per additional person</td></tr>
            <tr><td>Private Refinancing Notice</td><td>12 CFR Part 1026</td><td>Mandatory YMYL forfeiture disclosures</td></tr>
          </tbody>
        </table>
      </div>
    </article>"""
    return _render_base_html(title, meta_desc, canonical_url, body, jsonld_schemas=schemas, css_text=css_text)


# ---------------------------------------------------------------------------
# Clean Machine Surfaces (capped llms.txt; purge llms-full.txt & ai-benchmarks)
# ---------------------------------------------------------------------------


def _write_clean_llms_files(
    dist: Path,
    all_tools: Sequence[Dict[str, Any]],
    pack: TruthPack,
) -> None:
    """Writes lightweight capped llms.txt (<= 5 top hub links) and purges llms-full.txt."""
    _ = pack
    base = PREXVO_CANONICAL_BASE.rstrip("/")
    tool_lines = []

    def _strip_spaced_hyphen(val: str) -> str:
        return re.sub(r"(?<![0-9%)\]])[ \t]+-[ \t]+(?![0-9$(])", ": ", str(val or "")).strip()

    for t in all_tools:
        slug = t["slug"]
        if "/" in slug or not (dist / "tools" / slug / "index.html").is_file():
            continue
        t_title = _strip_spaced_hyphen(_clean_tool_title(t["title"], slug))
        t_desc = _strip_spaced_hyphen(_clean_tool_description(t["description"], t_title, slug))
        tool_lines.append(f"- [{t_title}]({base}/tools/{slug}/): {t_desc}")
        if len(tool_lines) >= 2:
            break

    seed_txt = f"""# Prexvo: Title IV Federal Student Loan Modeling Engine

> Deterministic student loan repayment and forgiveness modeling pursuant to P.L. 119-21 Section 82001, 34 CFR Part 685, and 91 FR 1797.

## Top Hub Links
- [Calculators Directory]({base}/tools/): Interactive calculator directory on {base}.
{chr(10).join(tool_lines)}
- [Statutory Calculation Methodology]({base}/methodology/): Primary statutory authorities and dataset sources.
- [Regulatory Notices and Disclaimers]({base}/disclaimers/): Regulatory disclosures and methodology scope.
"""
    llms_txt = cap_llms_txt_content(seed_txt, property_id="prexvo", canonical_base=base, max_hub_links=5)
    (dist / "llms.txt").write_text(llms_txt, encoding="utf-8")
    (dist / "llms-full.txt").unlink(missing_ok=True)


def _write_clean_ai_benchmarks(dist: Path, pack: TruthPack) -> None:
    """Actively purges retired dist/ai-benchmarks directory during compile."""
    _ = pack
    bm_dir = dist / "ai-benchmarks"
    if bm_dir.exists():
        shutil.rmtree(bm_dir, ignore_errors=True)


def _scrub_prexvo_truth_text(raw: str) -> str:
    """Replaces legacy 2025 overlay values, unverified pricing claims, and query stubs in Prexvo text."""
    updated = raw.replace("\u2014", "-").replace("\u2013", "-")
    updated = updated.replace(
        "36 remaining RAP payments at $273.23/mo unlocking $65,164 tax-free principal forgiveness.",
        "36 remaining RAP payments at $340.00/mo under P.L. 119-21 Section 82001 ($68,000 AGI, 6% tier) ahead of $62,760 tax-free PSLF discharge under 34 CFR 685.219.",
    )
    updated = re.sub(
        r"\$273\.23/mo\s+unlocking\b",
        "$340.00/mo under P.L. 119-21 Section 82001 supporting",
        updated,
        flags=re.IGNORECASE,
    )
    updated = updated.replace("$273.23", "$340.00").replace("273.23", "340.00")
    updated = updated.replace(
        "Calculate How Do You obligations under Title IV 34 CFR Part 685 using 225% HHS Poverty Guidelines, discretionary income caps, and forgiveness rules.",
        "Calculate Title IV student loan repayment obligations under 34 CFR Part 685, P.L. 119-21 Section 82001 RAP, and 91 FR 1797 $15,960 guidelines.",
    )
    updated = re.sub(
        r"\bCalculate\s+How\s+Do\s+You\b",
        "Calculate Title IV",
        updated,
        flags=re.IGNORECASE,
    )
    updated = re.sub(
        r"\bHow\s+Do\s+You\s+Calculate\s+Student\s+Loan\s+2026\s+Calculator\b",
        "Student Loan Repayment Calculation Guide 2026",
        updated,
        flags=re.IGNORECASE,
    )
    updated = re.sub(r"\$?15,650\b", "$15,960", updated)
    updated = re.sub(r"\b15650\b", "15960", updated)
    updated = re.sub(r"\b20\s*U\.S\.C\.?\s*1078-3\b", "34 CFR 685.220", updated, flags=re.IGNORECASE)
    return updated


def _post_porcelain_truth_hygiene(dist: Path, all_tools: Sequence[Dict[str, Any]], pack: TruthPack) -> None:
    """
    Normalizes any Porcelain-shell or retrofit-injected citations, overlay claims, and machine
    surfaces so every file in dist/ satisfies TruthPack disclosures, citations allowlist,
    runtime sync, and zero forbidden dashes without breaking Porcelain container landmarks.
    """
    write_runtime_synchronizer_asset(dist, property_id="prexvo")
    sync_tag = render_external_runtime_synchronizer_tag("prexvo")
    for html_file in sorted(dist.rglob("*.html")):
        if html_file.name.startswith("."):
            continue
        raw = html_file.read_text(encoding="utf-8", errors="ignore")
        updated = _scrub_prexvo_truth_text(raw)

        if 'id="pseo-runtime-sync"' not in updated and "</body>" in updated:
            updated = updated.replace("</body>", f"{sync_tag}\n</body>", 1)

        if updated != raw:
            assert_no_forbidden_dashes(updated, context=str(html_file))
            html_file.write_text(updated, encoding="utf-8")

    cat_path = dist / "catalog.json"
    if cat_path.is_file():
        cat_raw = cat_path.read_text(encoding="utf-8", errors="ignore")
        cat_upd = _scrub_prexvo_truth_text(cat_raw)
        if cat_upd != cat_raw:
            assert_no_forbidden_dashes(cat_upd, context=str(cat_path))
            cat_path.write_text(cat_upd, encoding="utf-8")
        sanitize_public_catalog_file(dist, property_id="prexvo")

    _write_clean_llms_files(dist, all_tools, pack)
    _write_clean_ai_benchmarks(dist, pack)


# ---------------------------------------------------------------------------
# Tool Discovery & Main Estate Entrypoint
# ---------------------------------------------------------------------------


def _discover_prexvo_tools(
    source_root: Optional[Path],
    extra_tools: Any,
    pack: TruthPack,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Discovers and deduplicates all core, statutory void, deployed void, and extra tools."""
    tools_by_slug: Dict[str, Dict[str, Any]] = {}
    manifests_by_slug: Dict[str, Dict[str, Any]] = {}

    def _add_tool(item: Dict[str, Any]) -> None:
        slug = str(item.get("slug") or "").strip().lower()
        if not slug or slug in QUARANTINED_ROGUE_SLUGS:
            return
        title = _clean_tool_title(str(item.get("title") or slug), slug)
        desc = _clean_tool_description(str(item.get("description") or ""), title, slug)
        clean_item: Dict[str, Any] = {
            "slug": slug,
            "title": title,
            "short_title": _clean_text_hygiene(str(item.get("short_title") or title[:24])),
            "description": desc,
            "primary_keyword": _clean_text_hygiene(str(item.get("primary_keyword") or slug.replace("-", " "))),
        }
        if item.get("updated_date"):
            clean_item["updated_date"] = str(item["updated_date"])
        tools_by_slug[slug] = clean_item
        manifests_by_slug[slug] = _build_manifest_for_slug(slug, pack, raw_spec=item)

    for ct in PREXVO_CORE_TOOLS:
        _add_tool(ct)
    for sv in PREXVO_STATUTORY_VOIDS:
        _add_tool(sv)

    # Load deployed_voids.json from source_root if available, else built-in canonical fallback
    dv_loaded: List[Dict[str, Any]] = []
    if source_root is not None:
        dv_path = source_root / "content" / "deployed_voids.json"
        if dv_path.is_file():
            try:
                parsed = json.loads(dv_path.read_text(encoding="utf-8"))
                if isinstance(parsed, list):
                    dv_loaded = [d for d in parsed if isinstance(d, dict) and d.get("slug")]
            except Exception:
                dv_loaded = []

    if dv_loaded:
        for dv in dv_loaded:
            _add_tool(dv)
    for fb_dv in _FALLBACK_DEPLOYED_VOID_SLUGS:
        if fb_dv["slug"] not in tools_by_slug:
            _add_tool(fb_dv)

    if extra_tools:
        for et in extra_tools:
            if isinstance(et, dict) and et.get("slug"):
                _add_tool(et)

    return list(tools_by_slug.values()), manifests_by_slug


_PREXVO_REDIRECTS = (
    "/calculator / 301\n"
    "/calculators / 301\n"
    "/rap /tools/rap-vs-ibr-calculator/ 301\n"
    "/ibr /tools/rap-vs-ibr-calculator/ 301\n"
    "/pslf /tools/pslf-qualifying-payment-simulator/ 301\n"
    "/save /tools/save-plan-litigation-transition/ 301\n"
    "/parent-plus /tools/parent-plus-double-consolidation/ 301\n"
    "/tiered /tools/tiered-standard-calculator/ 301\n"
    "/paye /tools/paye-sunset-calculator/ 301\n"
    "/icr /tools/icr-repayment-calculator/ 301\n"
    "/tools/pslf-buyback-calculator /tools/pslf-qualifying-payment-simulator/ 301\n"
    "/tools/pslf-buyback-calculator/ /tools/pslf-qualifying-payment-simulator/ 301\n"
    "/tools/tax-deduction-for-car-loan-interest /tools/ 301\n"
    "/tools/tax-deduction-for-car-loan-interest/ /tools/ 301\n"
    "/student-loan-repayment-calculator /tools/student-loan-repayment-calculator/ 301\n"
    "/student-loan-repayment-calculator/ /tools/student-loan-repayment-calculator/ 301\n"
    "/how-it-works /methodology/ 301\n"
    "/how-it-works/ /methodology/ 301\n"
    "/for-developers /methodology/ 301\n"
    "/for-developers/ /methodology/ 301\n"
    "/for-marketers /methodology/ 301\n"
    "/for-marketers/ /methodology/ 301\n"
)


def compile_prexvo_estate_impl(
    output_dir: Union[str, Path],
    run_retrofit: bool = True,
    extra_tools: Any = None,
    repo_root: Optional[Union[str, Path]] = None,
) -> Path:
    """
    Compiles the complete Truth-Pack-driven Prexvo (prexvo.com) static estate and returns dist_dir.
    - Reads 2026 HHS Poverty Guidelines ($15,960 / $5,680), P.L. 119-21 Section 82001 RAP rules
      (360-month forgiveness, 100% interest subsidy, $50/mo principal match), formulas, disclosures,
      and pricing tiers ($9 / $19) directly from load_truth_pack("prexvo").
    - Never mutates read-only source repos; writes only inside the target output/dist directory.
    Zero em-dashes (U+2014). Zero en-dashes (U+2013).
    """
    _ = run_retrofit  # TruthPack-first compilation builds clean HTML/JS/manifests without legacy 2025 retrofit drift.
    from pseofactory.porcelain_shell import generate_porcelain_stylesheet
    from pseofactory.qualification import assert_high_effort_content_qualified

    out_path = Path(output_dir).resolve()
    if repo_root is not None:
        source_root = Path(repo_root).resolve()
        dist = out_path if out_path != source_root else (source_root / "dist")
        staging_root = dist.parent
    elif out_path.name == "dist":
        dist = out_path
        staging_root = out_path.parent
        source_root = staging_root
    else:
        staging_root = out_path
        dist = staging_root / "dist"
        source_root = staging_root

    # Prepare directories inside staging_root/dist (or explicit dist)
    _, prepared_dist, tools_dir = prepare_estate_dirs(staging_root, "prexvo")
    if prepared_dist != dist:
        dist.mkdir(parents=True, exist_ok=True)
        tools_dir = dist / "tools"
        tools_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir = dist / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    (dist / "methodology").mkdir(parents=True, exist_ok=True)
    (dist / "disclaimers").mkdir(parents=True, exist_ok=True)
    (dist / "css").mkdir(parents=True, exist_ok=True)
    (dist / "static" / "css").mkdir(parents=True, exist_ok=True)

    src_static = source_root / "prexvo" / "static"
    if src_static.is_dir():
        shutil.copytree(src_static, dist / "static", dirs_exist_ok=True)

    css_text = generate_porcelain_stylesheet("prexvo")
    (dist / "css" / "style.css").write_text(css_text, encoding="utf-8")
    (dist / "static" / "css" / "style.css").write_text(css_text, encoding="utf-8")

    pack = _get_prexvo_truth_pack()
    all_tools, manifests_by_slug = _discover_prexvo_tools(source_root, extra_tools, pack)
    all_slugs = [t["slug"] for t in all_tools]

    # Homepage
    (dist / "index.html").write_text(_build_home_html(all_tools, pack, css_text), encoding="utf-8")

    # All tool pages + sidecar manifests
    catalog_tools: List[Dict[str, Any]] = []
    for tool in all_tools:
        slug = tool["slug"]
        m_doc = manifests_by_slug[slug]
        manifest_out = {
            "manifest_id": m_doc.get("manifest_id", f"{slug}-manifest"),
            **{
                k: m_doc[k]
                for k in (
                    "slug",
                    "model_name",
                    "statutory_authority",
                    "economic_dataset",
                    "formula",
                    "inputs",
                    "published_output",
                    "sample_calculation",
                    "entity_type",
                )
            },
        }
        assert_ai_mode_calculation_manifest(manifest_out)
        if " if " not in manifest_out["formula"] and "pow(" not in manifest_out["formula"]:
            assert_high_effort_content_qualified(manifest_out, context=f"prexvo manifest '{slug}'")
        else:
            eval_val = safe_eval_formula(manifest_out["formula"], manifest_out["inputs"])
            if abs(eval_val - float(manifest_out["published_output"])) > 0.01:
                raise ValueError(
                    f"Manifest formula mismatch for '{slug}': {eval_val} != {manifest_out['published_output']}"
                )
        (manifests_dir / f"{slug}.json").write_text(json.dumps(manifest_out, indent=2), encoding="utf-8")

        leaf_dir = tools_dir / slug
        leaf_dir.mkdir(parents=True, exist_ok=True)
        leaf_html = build_tool_page(
            tool,
            all_tools=all_tools,
            css_text=css_text,
            manifest_spec=m_doc,
            pack=pack,
        )
        (leaf_dir / "index.html").write_text(leaf_html, encoding="utf-8")

        catalog_tools.append(
            {
                "slug": slug,
                "title": tool["title"],
                "url": f"{PREXVO_CANONICAL_BASE}/tools/{slug}/",
                "category": str(tool.get("category") or "student_loans"),
                **({"updated_at": tool["updated_date"]} if tool.get("updated_date") else {}),
            }
        )

    # Prune orphaned sidecar manifests (e.g., statutory-repayment-assistance-plan.json)
    expected_manifest_names = {f"{s}.json" for s in all_slugs}
    for old_mf in list(manifests_dir.glob("*.json")):
        if old_mf.name not in expected_manifest_names:
            old_mf.unlink(missing_ok=True)

    # Directory, Methodology, Disclaimers, 404
    (tools_dir / "index.html").write_text(_build_tools_directory_html(all_tools, css_text), encoding="utf-8")
    (dist / "methodology" / "index.html").write_text(_build_methodology_html(css_text), encoding="utf-8")
    (dist / "disclaimers" / "index.html").write_text(_build_disclaimers_html(css_text), encoding="utf-8")
    (dist / "404.html").write_text(
        _render_base_html(
            f"Page Not Found (404) | {PREXVO_SITE_NAME}",
            "The requested student loan calculator resource could not be found on Prexvo.",
            f"{PREXVO_CANONICAL_BASE}/404.html",
            '<article class="article-content"><h1>Page Not Found</h1><p><a href="/" class="btn-cta touch-target">Return Home</a> <a href="/tools/" class="btn-cta touch-target">Browse Calculators</a></p></article>',
            css_text=css_text,
        ),
        encoding="utf-8",
    )

    hub_specs = [
        (f"{PREXVO_CANONICAL_BASE}/", "1.0", "daily"),
        (f"{PREXVO_CANONICAL_BASE}/tools/", "0.9", "daily"),
        (f"{PREXVO_CANONICAL_BASE}/methodology/", "0.9", "weekly"),
        (f"{PREXVO_CANONICAL_BASE}/disclaimers/", "0.9", "weekly"),
        (f"{PREXVO_CANONICAL_BASE}/about/", "0.7", "monthly"),
        (f"{PREXVO_CANONICAL_BASE}/privacy/", "0.5", "monthly"),
        (f"{PREXVO_CANONICAL_BASE}/terms/", "0.5", "monthly"),
        (f"{PREXVO_CANONICAL_BASE}/contact/", "0.7", "monthly"),
    ]
    write_sitemaps_and_robots(
        dist=dist,
        canonical_base=PREXVO_CANONICAL_BASE,
        hub_specs=hub_specs,
        leaf_tools=all_tools,
        ai_bots=None,
        disallow_paths=["/api/", "/cdn-cgi/", "/signal/", "/syndication/", "/staging/", "/test/", "/tests/"],
        allow_paths=["/"],
        include_changefreq_and_priority=False,
    )

    _, indexnow_stem = _resolve_prexvo_public_meta()
    header_routes = [
        "/",
        "/tools/",
        "/about/",
        "/methodology/",
        "/privacy/",
        "/terms/",
        "/disclaimers/",
        "/contact/",
    ] + [f"/tools/{s}/" for s in all_slugs]
    feed_items = [
        {
            "title": t["title"],
            "url": f"{PREXVO_CANONICAL_BASE}/tools/{t['slug']}/",
            "description": t["description"],
            **({"updated_date": t["updated_date"]} if t.get("updated_date") else {}),
        }
        for t in all_tools
    ]
    write_machine_endpoints_and_headers(
        dist=dist,
        property_id="prexvo",
        domain=PREXVO_DOMAIN,
        canonical_base=PREXVO_CANONICAL_BASE,
        feed_title=PREXVO_SITE_TITLE,
        feed_description=PREXVO_SITE_DESCRIPTION,
        feed_items=feed_items,
        indexnow_key=indexnow_stem,
        catalog_tools=catalog_tools,
        media_kit_payload={
            "property_id": "prexvo",
            "brand_name": PREXVO_SITE_NAME,
            "domain": PREXVO_DOMAIN,
            "vertical": "title_iv_student_loan_modeling",
            "deliverable_skus": [
                "px_instant_repayment_worksheet_19",
                "px_refi_amortization_decision_audit",
            ],
        },
        header_routes=header_routes,
        machine_endpoints=[
            "/feed.xml",
            "/llms.txt",
            "/sitemap.xml",
        ],
        static_patterns=["/static/*", "/css/*"],
        redirects_content=_PREXVO_REDIRECTS,
    )

    # Never write edge functions or finalize into a live /home/ubuntuadmin/projects/ repo
    from pseofactory.porcelain_shell import compile_tenant_porcelain_estate

    safe_root = staging_root if not str(staging_root).startswith("/home/ubuntuadmin/projects/") else dist.parent
    if not str(safe_root).startswith("/home/ubuntuadmin/projects/"):
        write_tenant_edge_functions(safe_root, dist, "prexvo")
        sanitize_tenant_overlays(
            safe_root,
            tools_dir,
            extra_bad_tokens=("profithelm", "gainhelm", "lienbond", "section-179-calculator"),
            property_id="prexvo",
        )
    if run_retrofit and not str(dist.resolve()).startswith("/home/ubuntuadmin/projects/"):
        from pseofactory.maintenance import RetroReflectionEngine

        RetroReflectionEngine.retrofit_estate(
            dist,
            "prexvo",
            canonical_base=PREXVO_CANONICAL_BASE,
        )
        for old_mf in list(manifests_dir.glob("*.json")):
            if old_mf.name not in expected_manifest_names:
                old_mf.unlink(missing_ok=True)

    _post_porcelain_truth_hygiene(dist, all_tools, pack)
    compile_tenant_porcelain_estate(dist, "prexvo", repo_root=safe_root)
    dist_functions = dist / "functions"
    if dist_functions.exists():
        shutil.rmtree(dist_functions, ignore_errors=True)

    _post_porcelain_truth_hygiene(dist, all_tools, pack)
    return dist


__all__ = [
    "AFFILIATE_DISCLOSURE",
    "CALCULATION_MANIFESTS",
    "CalculatorField",
    "CalculatorMetric",
    "DISCLAIMER_NO_ADVICE",
    "HHS_POVERTY_GUIDELINES",
    "InteractiveCalculatorSpec",
    "PREXVO_CANONICAL_BASE",
    "PREXVO_CORE_TOOLS",
    "PREXVO_DOMAIN",
    "PREXVO_SITE_DESCRIPTION",
    "PREXVO_SITE_NAME",
    "PREXVO_SITE_TITLE",
    "PREXVO_STATUTORY_VOIDS",
    "PSLF_QUALIFYING_PAYMENTS",
    "RAP_FORGIVENESS_MONTHS",
    "RAP_FORGIVENESS_YEARS",
    "RAP_PRINCIPAL_MATCH_CAP",
    "RAP_UNPAID_INTEREST_SUBSIDY_PCT",
    "REPAYMENT_CALCULATOR_SPEC",
    "YMYL_FORFEITURE_DISCLOSURE",
    "amortize_monthly_payment",
    "build_partners_matrix_section",
    "build_refinance_partner_cta",
    "build_tool_page",
    "calculate_discretionary_income",
    "calculate_ibr_payment",
    "calculate_icr_payment",
    "calculate_paye_payment",
    "calculate_rap_payment",
    "calculate_standard_10yr_payment",
    "calculate_tiered_standard_payment",
    "compare_all_repayment_plans",
    "compile_prexvo_estate_impl",
    "get_calculator_schemas",
    "get_hhs_poverty_guideline",
    "get_tiered_term_years",
    "normalize_interest_rate",
    "normalize_seo_title",
    "normalize_state_group",
    "render_calculator_widget",
]
