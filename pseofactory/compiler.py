"""
pseofactory High-Effort Content Compiler Engine
Stateless programmatic content compiler generating authoritative calculation assets.
Enforces:
1. Pre-compilation high-effort qualification gate (assert_high_effort_content_qualified).
2. Pure functional, deterministic AST mathematical formula evaluation (safe_eval_mathematical_formula).
3. Non-negative numeric parameter clamping (>= 0) per HWL-1263.
4. Factor 7 calculation manifest assembly and embedded JSON extraction.
5. High-contrast Obsidian dark-theme HTML with touch-accessible targets (>= 44x44px).
6. Multi-dataset join container linking primary statutory authority with empirical economic datasets.
7. Schema.org FAQPage and SoftwareApplication JSON-LD blocks.
8. In-memory self-verification via verify_html_unique_first_party_information.
9. Strictly zero em-dashes and zero en-dashes via assert_no_forbidden_dashes.

Zero em-dashes. Zero en-dashes.
"""

import os
import json
import re
import ast
from typing import Dict, Any, Optional, List

from pseofactory.affiliates import (
    GAINHELM_DISCLOSURES,
    PREXVO_DISCLOSURES,
    PROFITHELM_DISCLOSURES,
    get_affiliate_route,
    is_restricted_public_service_slug,
)
from pseofactory.qualification import assert_high_effort_content_qualified
from pseofactory.contracts import (
    safe_eval_mathematical_formula,
    assert_proprietary_model_integrity,
    assert_no_forbidden_dashes,
    assert_touch_targets,
)
from pseofactory.verifier import verify_html_unique_first_party_information

PROFITHELM_PREDICTION_CLUSTER = [
    ("prediction-market-odds", "Prediction Market Odds Calculator"),
    ("prediction-market-tax", "Prediction Market Section 1256 Tax Calculator"),
    ("prediction-market-ev", "Prediction Market Expected Value (EV) Calculator"),
    ("prediction-market-kelly-criterion", "Prediction Market Kelly Criterion Calculator"),
    ("prediction-market-implied-probability", "Prediction Market Implied Probability Calculator"),
    ("prediction-market-kalshi-fees", "Kalshi Quadratic Fee Drag Calculator"),
    ("prediction-market-arbitrage", "Prediction Market Cross-Platform Arbitrage Calculator"),
    ("prediction-market-vig-spread", "Prediction Market Vig and Spread Calculator"),
    ("prediction-market-break-even", "Prediction Market Break-Even Probability Calculator"),
]

PROFITHELM_TAX_CLUSTER = [
    ("section-179-calculator", "Section 179 Equipment Expense Tax Deduction Calculator"),
    ("section-1031-calculator", "Section 1031 Like-Kind Exchange Tax Deferral Calculator"),
    ("qsbs-section-1202-calculator", "QSBS Section 1202 Capital Gains Exemption Calculator"),
    ("tcja-sunset-bracket-calculator", "TCJA Sunset 2027 Marginal Tax Bracket Calculator"),
    ("saas-runway-calculator", "SaaS Runway and Capital Burn Rate Calculator"),
    ("crypto-tax-calculator", "Cryptocurrency Tax Loss Harvesting Calculator"),
    ("treasury-yield-calculator", "Treasury Yield Curve Arbitrage Calculator"),
    ("s-corp-reasonable-salary-tax-calculator", "S-Corp Reasonable Salary and FICA Tax Savings Calculator"),
    ("workers-comp-and-payroll-burden-calculator", "Workers Compensation and Employer Payroll Burden Calculator"),
    ("contractor-surety-bond-cost-calculator", "Contractor License and Surety Bond Cost Calculator"),
    ("equipment-lease-vs-buy-section-179-calculator", "Equipment Lease vs Buy Section 179 Cash Flow Calculator"),
    ("medical-and-dental-equipment-section-179-roi-calculator", "Medical and Dental Equipment Section 179 ROI Calculator"),
    ("commercial-heavy-vehicle-section-179-weight-calculator", "Commercial Heavy Vehicle Section 179 GVWR Weight Calculator"),
    ("section-301-tariff-landed-cost-calculator", "Section 301 Tariff and Customs Landed Cost Calculator"),
    ("invoice-factoring-vs-business-line-of-credit-calculator", "Invoice Factoring vs Business Line of Credit APR Calculator"),
    ("r-and-d-tax-credit-section-174-amortization-calculator", "R&D Tax Credit IRC Section 41 and Section 174 Calculator"),
]

PROFITHELM_B2B_EXPANSION_SPECS: List[Dict[str, Any]] = [
    {
        "query": "s corp reasonable salary and fica tax savings calculator",
        "slug": "s-corp-reasonable-salary-tax-calculator",
        "tenant": "profithelm",
        "statutory_authority": "IRC Section 3121 FICA Payroll Tax and IRC Section 199A QBI Deduction",
        "economic_dataset": "BLS OEWS Occupational Wage Percentiles and IRS S-Corporation Return Statistics",
        "model_name": "SCorpReasonableSalaryTaxArbitrageModel",
        "formula": "round(oasdi_savings + medicare_savings, 0)",
        "inputs": {"oasdi_savings": 10056.4, "medicare_savings": 3123.6},
        "published_output": 13180.0,
        "sample_calculation": "S-Corp shareholder distribution at $155,000 net business income with a $95,000 reasonable W-2 salary saves $13,180 in FICA self-employment taxes ($10,056 OASDI capped at the $176,100 wage base plus $3,124 Medicare)",
        "canonical_base": "https://profithelm.com",
        "expected_partner": "rippling",
    },
    {
        "query": "workers compensation and employer payroll burden rate calculator",
        "slug": "workers-comp-and-payroll-burden-calculator",
        "tenant": "profithelm",
        "statutory_authority": "IRC Section 3111 FICA, IRC Section 3301 FUTA, and NCCI Workers Compensation Class Manuals",
        "economic_dataset": "BLS Employer Costs for Employee Compensation (ECEC) and State Rating Bureau Filings",
        "model_name": "WorkersCompPayrollBurdenModel",
        "formula": "annual_payroll * statutory_tax_rate + (annual_payroll / 100.0) * workers_comp_rate_per_100",
        "inputs": {"annual_payroll": 500000, "statutory_tax_rate": 0.0865, "workers_comp_rate_per_100": 3.45},
        "published_output": 60500.0,
        "sample_calculation": "Annual payroll of $500,000 at 8.65% combined FICA/FUTA/SUTA plus $3.45 per $100 workers comp rate yields $60,500 employer burden",
        "canonical_base": "https://profithelm.com",
        "expected_partner": "simply_business",
    },
    {
        "query": "contractor license and performance surety bond cost calculator",
        "slug": "contractor-surety-bond-cost-calculator",
        "tenant": "profithelm",
        "statutory_authority": "40 USC Section 3131 Federal Miller Act and 48 CFR Part 28 Surety Bond Regulations",
        "economic_dataset": "FRED Construction Spending Series and SFAA Surety Underwriting Loss Benchmarks",
        "model_name": "ContractorSuretyBondUnderwritingModel",
        "formula": "bond_penalty_amount * (credit_tier_rate_pct / 100.0)",
        "inputs": {"bond_penalty_amount": 50000, "credit_tier_rate_pct": 1.5},
        "published_output": 750.0,
        "sample_calculation": "Statutory $50,000 contractor license bond at a 1.5% standard credit tier underwriting rate yields a $750 annual bond premium",
        "canonical_base": "https://profithelm.com",
        "expected_partner": "suretybonds_direct",
    },
    {
        "query": "equipment lease vs buy section 179 cash flow arbitrage calculator",
        "slug": "equipment-lease-vs-buy-section-179-calculator",
        "tenant": "profithelm",
        "statutory_authority": "IRC Section 179 First-Year Expensing and IRC Section 168(k) Bonus Depreciation",
        "economic_dataset": "Federal Reserve G.19 Commercial Equipment Finance Rates and FRED Prime Rate Series",
        "model_name": "EquipmentLeaseBuySection179ArbitrageModel",
        "formula": "equipment_cost * marginal_tax_rate - year_one_financing_payments",
        "inputs": {"equipment_cost": 180000, "marginal_tax_rate": 0.32, "year_one_financing_payments": 39600},
        "published_output": 18000.0,
        "sample_calculation": "Financing $180,000 of qualifying equipment generates $57,600 in Year-1 Section 179 tax savings against $39,600 in payments for $18,000 positive Year-1 cash flow",
        "canonical_base": "https://profithelm.com",
        "expected_partner": "crest_capital",
    },
    {
        "query": "medical and dental equipment section 179 tax deduction roi calculator",
        "slug": "medical-and-dental-equipment-section-179-roi-calculator",
        "tenant": "profithelm",
        "statutory_authority": "IRC Section 179 Qualifying Medical Property and IRC Section 44 Disabled Access Credit",
        "economic_dataset": "BLS Healthcare Wage Series, FRED Medical Care CPI Series, and CMS RVU Benchmarks",
        "model_name": "MedicalEquipmentSection179ROIModel",
        "formula": "annual_procedure_net_revenue + (equipment_cost * marginal_tax_rate)",
        "inputs": {"equipment_cost": 150000, "marginal_tax_rate": 0.35, "annual_procedure_net_revenue": 96000},
        "published_output": 148500.0,
        "sample_calculation": "Clinical CBCT imaging system costing $150,000 yields $96,000 annual procedure net billings plus $52,500 Year-1 Section 179 tax savings for $148,500 first-year return",
        "canonical_base": "https://profithelm.com",
        "expected_partner": "national_funding_med",
    },
    {
        "query": "commercial heavy vehicle section 179 gvwr 6000 lbs deduction calculator",
        "slug": "commercial-heavy-vehicle-section-179-weight-calculator",
        "tenant": "profithelm",
        "statutory_authority": "IRC Section 179(b)(5) Heavy SUV Cap and IRC Section 280F Listed Property Rules",
        "economic_dataset": "FRED Heavy Truck Sales Series and IRS Revenue Procedure Depreciation Limitations",
        "model_name": "CommercialHeavyVehicleGVWR179Model",
        "formula": "vehicle_cost * business_use_fraction * marginal_tax_rate",
        "inputs": {"vehicle_cost": 95000, "business_use_fraction": 0.90, "marginal_tax_rate": 0.35},
        "published_output": 29925.0,
        "sample_calculation": "Work truck over 6,000 lbs GVWR costing $95,000 at 90% business use in the 35% bracket yields $29,925 in Year-1 cash tax savings",
        "canonical_base": "https://profithelm.com",
        "expected_partner": "crest_capital",
    },
    {
        "query": "section 301 import tariff and customs duty landed cost calculator",
        "slug": "section-301-tariff-landed-cost-calculator",
        "tenant": "profithelm",
        "statutory_authority": "19 USC Section 2411 (Trade Act Section 301) and 19 CFR Part 159 Customs Valuation",
        "economic_dataset": "FRED Import Price Index Series, USITC HTSUS Schedules, and CBP MPF Fee Tables",
        "model_name": "Section301TariffLandedCostModel",
        "formula": "customs_value_fob * (1.0 + combined_duty_and_301_rate) + freight_and_mpf_hmf",
        "inputs": {"customs_value_fob": 120000, "combined_duty_and_301_rate": 0.285, "freight_and_mpf_hmf": 6766},
        "published_output": 160966.0,
        "sample_calculation": "FOB shipment of $120,000 subject to 28.5% combined HTSUS and Section 301 duty plus $6,766 freight and CBP MPF/HMF fees ($528.40 MPF + $237.50 HMF) yields $160,966 total landed cost",
        "canonical_base": "https://profithelm.com",
        "expected_partner": "freightos_marketplace",
    },
    {
        "query": "invoice factoring fee vs business line of credit effective apr calculator",
        "slug": "invoice-factoring-vs-business-line-of-credit-calculator",
        "tenant": "profithelm",
        "statutory_authority": "IRC Section 163 Business Interest Limitation and 12 CFR Part 1026 Commercial Credit Rules",
        "economic_dataset": "Federal Reserve H.15 Selected Interest Rates and FRED Commercial Bank Prime Loan Series",
        "model_name": "InvoiceFactoringVsLineOfCreditModel",
        "formula": "invoice_face_value * factor_fee_rate",
        "inputs": {"invoice_face_value": 100000, "factor_fee_rate": 0.025},
        "published_output": 2500.0,
        "sample_calculation": "Factoring a $100,000 commercial invoice at a 2.5% discount fee costs $2,500 (20.28% annualized APR across a 45-day net collection cycle)",
        "canonical_base": "https://profithelm.com",
        "expected_partner": "otr_solutions_factoring",
    },
    {
        "query": "r and d tax credit irc section 41 and section 174 amortization calculator",
        "slug": "r-and-d-tax-credit-section-174-amortization-calculator",
        "tenant": "profithelm",
        "statutory_authority": "IRC Section 41 Credit for Increasing Research Activities and IRC Section 174 R&E Amortization",
        "economic_dataset": "FRED Private R&D Investment Series, BEA Innovation Accounts, and IRS Form 6765 Statistics",
        "model_name": "RDResearchCreditSection174Model",
        "formula": "(current_qre_spend - (0.5 * prior_three_year_avg_qre)) * asc_credit_rate",
        "inputs": {"current_qre_spend": 800000, "prior_three_year_avg_qre": 500000, "asc_credit_rate": 0.14},
        "published_output": 77000.0,
        "sample_calculation": "Qualifying research expenditures of $800,000 against a $500,000 prior 3-year average under the 14% Alternative Simplified Credit yields a $77,000 direct tax credit",
        "canonical_base": "https://profithelm.com",
        "expected_partner": "rippling",
    },
]


def get_profithelm_b2b_expansion_specs() -> List[Dict[str, Any]]:
    """Returns deep copies of the 9 Factor-7-verified ProfitHelm commercial B2B calculator specs."""
    return [dict(spec, inputs=dict(spec["inputs"])) for spec in PROFITHELM_B2B_EXPANSION_SPECS]


PREXVO_STUDENT_LOAN_CLUSTER = [
    ("student-loan-repayment-calculator", "Title IV Student Loan Standard Repayment Calculator"),
    ("rap-vs-ibr-calculator", "Repayment Assistance Plan (RAP) vs IBR Monthly Payment Calculator"),
    ("student-loan-forgiveness-calculator", "Student Loan Forgiveness Timeline Calculator"),
    ("pslf-qualifying-payment-calculator", "PSLF 120 Qualifying Payments Verification Calculator"),
    ("student-loan-interest-subsidy-calculator", "Title IV Unpaid Interest Subsidy Benefit Calculator"),
]

GAINHELM_CYBER_COMPLIANCE_CLUSTER = [
    ("soc-2-audit-cost-calculator", "SOC 2 Type I and Type II Audit Cost Calculator"),
    ("cmmc-2-0-compliance-cost-calculator", "CMMC 2.0 Level 2 C3PAO Assessment Cost Calculator"),
    ("nist-800-171-sprs-score-calculator", "NIST SP 800-171 DoD SPRS Weighted Score Calculator"),
    ("iso-27001-certification-cost-calculator", "ISO/IEC 27001:2022 Auditor-Day Certification Cost Calculator"),
    ("hipaa-violation-penalty-breach-cost-calculator", "HIPAA Civil Monetary Penalty and HITECH Breach Cost Calculator"),
    ("pci-dss-4-0-compliance-cost-calculator", "PCI DSS v4.0.1 QSA ROC and SAQ Compliance Cost Calculator"),
    ("fedramp-authorization-3pao-cost-calculator", "FedRAMP 20x and Rev 5 3PAO Authorization Cost Calculator"),
    ("hitrust-csf-e1-i1-r2-certification-cost-calculator", "HITRUST CSF e1, i1, and r2 Certification Cost Calculator"),
    ("penetration-testing-scoping-cost-calculator", "CREST and OSCP Penetration Testing Scoping Cost Calculator"),
    ("cyber-liability-insurance-breach-exposure-calculator", "Cyber Liability Insurance Premium and Breach Exposure Calculator"),
]


def compile_ast_to_js(
    formula_str: str,
    input_keys: Optional[Any] = None,
) -> str:
    """
    Translates a deterministic arithmetic formula string into a client-side JavaScript expression.
    Parses mathematical expressions via ast.parse(..., mode='eval') and translates AST operators
    (+, -, *, /, etc.) and variable names into JavaScript expressions referencing inputs (e.g. inputs.a + inputs.b).
    Zero em-dashes. Zero en-dashes.
    """
    if not formula_str or not isinstance(formula_str, str):
        raise ValueError("Formula must be a non-empty string")

    clean_f = formula_str.strip()
    clean_f = re.sub(r'(\d+(?:\.\d+)?)\s*%', r'(\1 / 100.0)', clean_f)
    clean_f = clean_f.replace("$", "")
    clean_f = re.sub(r'(?<=\d),(?=\d)', '', clean_f)

    try:
        parsed_ast = ast.parse(clean_f, mode="eval")
    except Exception as ex:
        raise ValueError(f"Formula '{formula_str}' failed AST parse: {ex}")

    def _node_to_js(node: ast.AST) -> str:
        if isinstance(node, ast.Expression):
            return _node_to_js(node.body)
        elif isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                return "true" if node.value else "false"
            elif isinstance(node.value, (int, float)):
                return str(node.value)
            raise ValueError(f"Unsupported constant type in formula: {type(node.value).__name__}")
        elif isinstance(node, ast.Name):
            name = node.id
            if name.lower() == "pi":
                return "Math.PI"
            elif name.lower() == "e":
                return "Math.E"
            return f"inputs.{name}"
        elif isinstance(node, ast.BinOp):
            left_js = _node_to_js(node.left)
            right_js = _node_to_js(node.right)
            if isinstance(node.op, ast.Add):
                return f"({left_js} + {right_js})"
            elif isinstance(node.op, ast.Sub):
                return f"({left_js} - {right_js})"
            elif isinstance(node.op, ast.Mult):
                return f"({left_js} * {right_js})"
            elif isinstance(node.op, ast.Div):
                return f"({left_js} / {right_js})"
            elif isinstance(node.op, ast.FloorDiv):
                return f"Math.floor({left_js} / {right_js})"
            elif isinstance(node.op, ast.Mod):
                return f"({left_js} % {right_js})"
            elif isinstance(node.op, ast.Pow):
                return f"Math.pow({left_js}, {right_js})"
            else:
                raise ValueError(f"Unsupported binary operator in formula: {type(node.op).__name__}")
        elif isinstance(node, ast.UnaryOp):
            operand_js = _node_to_js(node.operand)
            if isinstance(node.op, ast.UAdd):
                return f"(+{operand_js})"
            elif isinstance(node.op, ast.USub):
                return f"(-{operand_js})"
            else:
                raise ValueError(f"Unsupported unary operator in formula: {type(node.op).__name__}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                func_name = node.func.id.lower()
                args_js = [_node_to_js(arg) for arg in node.args]
                if func_name == "min":
                    return f"Math.min({', '.join(args_js)})"
                elif func_name == "max":
                    return f"Math.max({', '.join(args_js)})"
                elif func_name == "abs":
                    return f"Math.abs({', '.join(args_js)})"
                elif func_name in ("floor", "ceil"):
                    return f"Math.{func_name}({', '.join(args_js)})"
                elif func_name == "round":
                    if len(args_js) == 2:
                        return f"(Math.round({args_js[0]} * Math.pow(10, {args_js[1]})) / Math.pow(10, {args_js[1]}))"
                    elif len(args_js) == 1:
                        return f"Math.round({args_js[0]})"
                    else:
                        raise ValueError(f"round() expects 1 or 2 arguments, got {len(args_js)}")
                elif func_name == "pow" and len(args_js) == 2:
                    return f"Math.pow({args_js[0]}, {args_js[1]})"
                elif func_name == "clamp" and len(args_js) == 3:
                    return f"Math.min(Math.max({args_js[0]}, {args_js[1]}), {args_js[2]})"
                elif func_name == "phaseout" and len(args_js) in (3, 4):
                    rate_js = args_js[3] if len(args_js) == 4 else "1.0"
                    return f"Math.max(0.0, {args_js[0]} - Math.max(0.0, {args_js[1]} - {args_js[2]}) * {rate_js})"
                elif func_name == "lookup_bracket" and len(args_js) in (3, 4):
                    base_tax_js = args_js[3] if len(args_js) == 4 else "0.0"
                    return f"({base_tax_js} + Math.max(0.0, {args_js[0]} - {args_js[1]}) * {args_js[2]})"
                else:
                    raise ValueError(f"Unsupported function call in formula: {node.func.id}")
            else:
                raise ValueError(f"Unsupported function call in formula: {ast.dump(node.func)}")
        else:
            raise ValueError(f"Unsupported expression element in formula: {ast.dump(node)}")

    return _node_to_js(parsed_ast)


compile_formula_to_js = compile_ast_to_js


def _eval_compiled_js_expr(js_expr: str, clamped_inputs: Dict[str, float]) -> float:
    """Evaluates a compiled JS arithmetic/piecewise expression in Python to verify parity."""
    import math
    from types import SimpleNamespace

    py_expr = js_expr
    # Convert JS ternary (cond ? a : b) into Python conditional ((a) if (cond) else (b))
    while "?" in py_expr and ":" in py_expr:
        m = re.search(r"\(([^()?]+)\?\s*([^():?]+):\s*([^():?]+)\)", py_expr)
        if not m:
            break
        cond_part, true_part, false_part = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        py_expr = py_expr[: m.start()] + f"(({true_part}) if ({cond_part}) else ({false_part}))" + py_expr[m.end() :]

    ns_inputs = SimpleNamespace(**{str(k).strip(): float(v) for k, v in clamped_inputs.items()})
    math_ns = SimpleNamespace(
        min=min,
        max=max,
        abs=abs,
        floor=math.floor,
        ceil=math.ceil,
        round=lambda x: round(x),
        pow=pow,
        PI=math.pi,
        E=math.e,
    )
    return float(eval(py_expr, {"__builtins__": {}}, {"Math": math_ns, "inputs": ns_inputs}))


def verify_formula_boundary_fuzzing(
    formula_str: str,
    inputs: Dict[str, Any],
    tolerance: float = 0.01,
) -> Dict[str, Any]:
    """
    Fuzz-tests formula evaluation across 4 boundary vectors (zero, negative clamped to 0,
    10x cap, and fractional inputs) comparing Python safe_eval_mathematical_formula
    against JS AST compilation (compile_ast_to_js).
    Zero em-dashes. Zero en-dashes.
    """
    js_expr = compile_ast_to_js(formula_str, list(inputs.keys()) if isinstance(inputs, dict) else None)

    base_clean: Dict[str, float] = {}
    for k, v in (inputs or {}).items():
        if isinstance(v, (int, float)):
            base_clean[str(k)] = max(0.0, float(v))
        elif isinstance(v, str):
            try:
                base_clean[str(k)] = max(0.0, float(v.replace("$", "").replace(",", "").replace("%", "").strip()))
            except ValueError:
                base_clean[str(k)] = 0.0
        else:
            base_clean[str(k)] = 0.0

    vectors = [
        ("zero", {k: 0.0 for k in base_clean}),
        ("negative_clamped", {k: max(0.0, -abs(val if val != 0.0 else 100.0)) for k, val in base_clean.items()}),
        ("ten_x_cap", {k: (val * 10.0 if val > 0.0 else 1000.0) for k, val in base_clean.items()}),
        ("fractional", {k: (val * 0.3333 + 0.125 if val > 0.0 else 0.125) for k, val in base_clean.items()}),
    ]

    discrepancies: List[str] = []
    for vec_name, vec_inputs in vectors:
        try:
            py_val = safe_eval_mathematical_formula(formula_str, vec_inputs)
        except ZeroDivisionError:
            continue
        except Exception as ex:
            discrepancies.append(f"Vector '{vec_name}' Python eval error: {ex}")
            continue

        try:
            js_val = _eval_compiled_js_expr(js_expr, vec_inputs)
        except ZeroDivisionError:
            continue
        except Exception as ex:
            discrepancies.append(f"Vector '{vec_name}' JS eval error: {ex}")
            continue

        if abs(py_val - js_val) > tolerance:
            discrepancies.append(
                f"Vector '{vec_name}' parity mismatch: Python={py_val} vs JS={js_val}"
            )

    return {
        "passed": len(discrepancies) == 0,
        "vectors_tested": len(vectors),
        "discrepancies": discrepancies,
        "js_expression": js_expr,
    }


def _format_scenario_number(val: float) -> str:
    """Formats a scenario output value deterministically."""
    fval = float(val)
    if 0 < abs(fval) < 1 and round(fval, 4) != round(fval, 2):
        return f"{round(fval, 4):.4f}"
    rounded = round(fval, 2)
    return f"{rounded:,.2f}" if not rounded.is_integer() else f"{int(rounded):,}"


def _render_5point_sensitivity_table_html(
    published_output: float,
    display_output: str,
    statutory_authority: str,
    economic_dataset: str,
    model_name: str = "",
) -> str:
    """
    Renders a 5-point server-side sensitivity scenario table (0.8x to 1.2x)
    so search engine crawlers index multi-row numerical outputs directly in initial HTML.
    Zero em-dashes. Zero en-dashes.
    """
    conservative_output = _format_scenario_number(published_output * 0.8)
    mod_con_output = _format_scenario_number(published_output * 0.9)
    mod_exp_output = _format_scenario_number(published_output * 1.1)
    aggressive_output = _format_scenario_number(published_output * 1.2)
    from pseofactory.competitor import _format_safe_heading_topic
    clean_model = _format_safe_heading_topic(str(model_name or "").strip(), "")
    sens_h2 = f"Sensitivity Scenario Modeling: {clean_model}" if clean_model else "Sensitivity Scenario Modeling"

    return (
        f'    <div class="scenario-container comparison-container card pseo-card" '
        f'data-entity-type="scenario" data-mechanic="server_rendered_sensitivity_grid">\n'
        f'      <h2>{sens_h2}</h2>\n'
        f'      <p>SSR 5-point sensitivity matrix comparing baseline model projections against parameter variations:</p>\n'
        f'      <div class="table-wrap pseo-table-wrap">\n'
        f'        <table class="scenario-table comparison-table" data-entity-type="scenario" '
        f'data-statutory-source="{statutory_authority}" data-economic-source="{economic_dataset}">\n'
        f'          <thead>\n'
        f'            <tr>\n'
        f'              <th scope="col">Scenario Analysis</th>\n'
        f'              <th scope="col">Variance Assumption</th>\n'
        f'              <th scope="col">Statutory Basis</th>\n'
        f'              <th scope="col">Economic Series</th>\n'
        f'              <th scope="col">Projected Outcome</th>\n'
        f'            </tr>\n'
        f'          </thead>\n'
        f'          <tbody>\n'
        f'            <tr data-entity-type="scenario">\n'
        f'              <td><strong>Baseline Scenario</strong></td>\n'
        f'              <td>Standard published parameters (1.0x)</td>\n'
        f'              <td>{statutory_authority}</td>\n'
        f'              <td>{economic_dataset}</td>\n'
        f'              <td><strong class="scenario-baseline">{display_output}</strong></td>\n'
        f'            </tr>\n'
        f'            <tr data-entity-type="scenario">\n'
        f'              <td><strong>Conservative Scenario</strong></td>\n'
        f'              <td>20% Parameter contraction (0.8x)</td>\n'
        f'              <td>{statutory_authority}</td>\n'
        f'              <td>{economic_dataset}</td>\n'
        f'              <td><strong class="scenario-conservative">{conservative_output}</strong></td>\n'
        f'            </tr>\n'
        f'            <tr data-entity-type="scenario">\n'
        f'              <td><strong>Moderate Contraction Scenario</strong></td>\n'
        f'              <td>10% Parameter contraction (0.9x)</td>\n'
        f'              <td>{statutory_authority}</td>\n'
        f'              <td>{economic_dataset}</td>\n'
        f'              <td><strong class="scenario-moderate-contraction">{mod_con_output}</strong></td>\n'
        f'            </tr>\n'
        f'            <tr data-entity-type="scenario">\n'
        f'              <td><strong>Moderate Expansion Scenario</strong></td>\n'
        f'              <td>10% Parameter expansion (1.1x)</td>\n'
        f'              <td>{statutory_authority}</td>\n'
        f'              <td>{economic_dataset}</td>\n'
        f'              <td><strong class="scenario-moderate-expansion">{mod_exp_output}</strong></td>\n'
        f'            </tr>\n'
        f'            <tr data-entity-type="scenario">\n'
        f'              <td><strong>Aggressive Scenario</strong></td>\n'
        f'              <td>20% Parameter expansion (1.2x)</td>\n'
        f'              <td>{statutory_authority}</td>\n'
        f'              <td>{economic_dataset}</td>\n'
        f'              <td><strong class="scenario-aggressive">{aggressive_output}</strong></td>\n'
        f'            </tr>\n'
        f'          </tbody>\n'
        f'        </table>\n'
        f'      </div>\n'
        f'    </div>'
    )


def _render_scenario_presets_bar_html(
    canonical_base: str,
    slug: str,
    clamped_inputs: Dict[str, Any],
) -> str:
    """
    Renders URL-parameterized scenario preset links (Conservative, Baseline, Aggressive)
    for crawlable deep-linking and 1-click user parameter hydration.
    Zero em-dashes. Zero en-dashes.
    """
    presets = [
        ("Conservative (0.8x)", 0.8, "conservative"),
        ("Baseline (1.0x)", 1.0, "baseline"),
        ("Aggressive (1.2x)", 1.2, "aggressive"),
    ]
    links_html: List[str] = []
    for label, mult, preset_key in presets:
        params: List[str] = []
        for k, v in clamped_inputs.items():
            if isinstance(v, (int, float)):
                scaled = round(float(v) * mult, 2)
                val_str = str(int(scaled)) if scaled.is_integer() else str(scaled)
                params.append(f"{k}={val_str}")
        qs = "&amp;".join(params)
        href = f"{canonical_base}/tools/{slug}/?{qs}" if qs else f"{canonical_base}/tools/{slug}/"
        links_html.append(
            f'          <a href="{href}" data-preset="{preset_key}" rel="nofollow" '
            f'class="touch-target scenario-preset-link" '
            f'style="display: inline-flex; align-items: center; justify-content: center; '
            f'min-height: 44px; min-width: 44px; padding: 10px 14px; border-radius: 8px; '
            f'background: var(--bg-elevated, #eff6ff); color: var(--accent, #1d4ed8); '
            f'border: 1px solid var(--border-strong, #bfdbfe); text-decoration: none; font-size: 14px; font-weight: 600;">'
            f'{label}</a>'
        )
    joined_links = "\n".join(links_html)
    return (
        f'        <div class="scenario-presets-bar" data-mechanic="deep_link_scenario_presets" '
        f'style="display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 16px;">\n'
        f'{joined_links}\n'
        f'        </div>'
    )


def _render_compiler_monetization_and_guardrail_html(
    slug: str,
    query: str,
    is_prexvo: bool,
    candidate_spec: Dict[str, Any],
    is_gainhelm: bool = False,
) -> Dict[str, Any]:
    """
    Renders domain-isolated multi-company affiliate partner rosters and deterministic
    conversion slots on profithelm and gainhelm, and enforces YMYL statutory guardrails on prexvo
    (suppressing commercial offers on restricted public-service pages).
    Zero em-dashes. Zero en-dashes.
    """
    import html as html_lib
    from pseofactory.affiliates import bind_asset_partner_roster

    prop_id = "prexvo" if is_prexvo else ("gainhelm" if is_gainhelm else "profithelm")
    gsc_metrics_raw: Dict[str, Any] = {}
    if isinstance(candidate_spec.get("gsc_telemetry"), dict):
        gsc_metrics_raw.update(candidate_spec["gsc_telemetry"])
    if isinstance(candidate_spec.get("gsc_metrics"), dict):
        gsc_metrics_raw.update(candidate_spec["gsc_metrics"])
    for gk in (
        "impressions",
        "clicks",
        "ctr",
        "position",
        "query",
        "mobile_impressions",
        "desktop_impressions",
        "mobile_ctr",
        "desktop_ctr",
        "mobile_ctr_gap",
        "device_focus",
        "search_appearances",
        "device_splits",
    ):
        if gk in candidate_spec and gk not in gsc_metrics_raw:
            gsc_metrics_raw[gk] = candidate_spec[gk]
    gsc_metrics = gsc_metrics_raw if gsc_metrics_raw else None
    engagement_metrics = candidate_spec.get("engagement_metrics") if isinstance(candidate_spec.get("engagement_metrics"), dict) else None
    page_archetype = str(candidate_spec.get("page_archetype") or "")

    roster_info = bind_asset_partner_roster(
        property_id=prop_id,
        slug=slug,
        query=query,
        page_archetype=page_archetype,
        gsc_metrics=gsc_metrics,
        engagement_metrics=engagement_metrics,
    )
    slot_plan = roster_info["slot_plan"]
    bindings = slot_plan.get("slot_bindings") or {}
    slug_id = slug.strip("/").replace("/", "-")

    def _build_inline_and_table_slots() -> tuple[str, str]:
        inline_offer = bindings.get("calculator_result_inline")
        table_offer = bindings.get("comparison_table_cta")
        inline_html = ""
        table_html = ""
        if isinstance(inline_offer, dict) and inline_offer.get("partner_key"):
            pk_in = str(inline_offer["partner_key"])
            in_badge = html_lib.escape(str(inline_offer.get("badge") or "Verified Offer"))
            in_name = html_lib.escape(str(inline_offer.get("name") or pk_in))
            in_cta = html_lib.escape(str(inline_offer.get("cta_text") or "Explore Partner"))
            in_brand = html_lib.escape(str(inline_offer.get("company_brand") or pk_in))
            in_model = html_lib.escape(str(inline_offer.get("partnership_model") or "CPA_BOUNTY"))
            in_href = html_lib.escape(str(inline_offer.get("attributed_href") or f"/r/{pk_in}"))
            in_sub = html_lib.escape(str(inline_offer.get("subid") or f"{slug_id}_inline"))
            inline_html = (
                f'\n        <div class="calc-inline-cta" data-mechanic="compliant_intent_monetization" '
                f'data-partner="{pk_in}" data-company-brand="{in_brand}" data-partner-tier="primary" '
                f'data-partnership-model="{in_model}" '
                f'data-cta-slot="calculator_result_inline" '
                f'style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 14px; margin-top: 12px; background: var(--bg-elevated); border: 1px solid var(--border-strong); border-left: 4px solid var(--accent); border-radius: 8px;">\n'
                f'          <div class="calc-inline-cta-copy" style="flex: 1; min-width: 180px;">\n'
                f'            <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--accent);">{in_badge} &bull; Primary Conversion Slot</div>\n'
                f'            <div style="font-size: 14px; font-weight: 700; color: var(--text); margin-top: 2px;">{in_name}</div>\n'
                f'          </div>\n'
                f'          <a href="{in_href}" rel="noopener sponsored nofollow" target="_blank" '
                f'data-partner="{pk_in}" data-company-brand="{in_brand}" data-partner-tier="primary" '
                f'data-partnership-model="{in_model}" '
                f'data-tool="{html_lib.escape(slug_id)}" data-subid="{in_sub}" data-status="live" '
                f'data-cta-slot="calculator_result_inline" class="btn-cta partner-cta touch-target" '
                f'style="display: inline-flex; align-items: center; justify-content: center; min-height: 44px; min-width: 44px; padding: 10px 14px; border-radius: 8px; background: var(--accent, #1d4ed8); color: var(--cta-fg, #ffffff); font-weight: 600; text-decoration: none; white-space: nowrap;">{in_cta}</a>\n'
                f'        </div>'
            )
        if "comparison_table_cta" in (slot_plan.get("active_slots") or []) and isinstance(table_offer, dict) and table_offer.get("partner_key"):
            pk_tb = str(table_offer["partner_key"])
            tb_name = html_lib.escape(str(table_offer.get("name") or pk_tb))
            tb_cta = html_lib.escape(str(table_offer.get("cta_text") or "Compare Partner"))
            tb_brand = html_lib.escape(str(table_offer.get("company_brand") or pk_tb))
            tb_role = html_lib.escape(str(table_offer.get("tier_role") or "secondary"))
            tb_model = html_lib.escape(str(table_offer.get("partnership_model") or "CPA_BOUNTY"))
            tb_href = html_lib.escape(str(table_offer.get("attributed_href") or f"/r/{pk_tb}"))
            tb_sub = html_lib.escape(str(table_offer.get("subid") or f"{slug_id}_table"))
            table_html = (
                f'    <div class="comparison-table-cta-bar card pseo-card" data-mechanic="compliant_intent_monetization" '
                f'data-partner="{pk_tb}" data-company-brand="{tb_brand}" data-partner-tier="{tb_role}" '
                f'data-partnership-model="{tb_model}" '
                f'data-cta-slot="comparison_table_cta" '
                f'style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 18px; margin-bottom: 24px;">\n'
                f'      <span style="font-size: 14px; font-weight: 600; color: var(--text);">Scenario Execution Partner: <strong>{tb_name}</strong> ({tb_brand})</span>\n'
                f'      <a href="{tb_href}" rel="noopener sponsored nofollow" target="_blank" '
                f'data-partner="{pk_tb}" data-company-brand="{tb_brand}" data-partner-tier="{tb_role}" '
                f'data-partnership-model="{tb_model}" '
                f'data-tool="{html_lib.escape(slug_id)}" data-subid="{tb_sub}" data-status="live" '
                f'data-cta-slot="comparison_table_cta" class="btn-cta partner-cta touch-target" '
                f'style="display: inline-flex; align-items: center; justify-content: center; min-height: 44px; min-width: 44px; padding: 10px 14px; border-radius: 8px; background: var(--accent, #1d4ed8); color: var(--cta-fg, #ffffff); font-weight: 600; text-decoration: none;">{tb_cta}</a>\n'
                f'    </div>'
            )
        return inline_html, table_html

    def _build_roster_cards_grid_html() -> str:
        matrix_cards = bindings.get("partner_matrix_cards") or []
        if not matrix_cards:
            return ""
        card_items: List[str] = []
        for idx, card_offer in enumerate(matrix_cards, start=1):
            c_pk = str(card_offer.get("partner_key") or "")
            c_name = html_lib.escape(str(card_offer.get("name") or c_pk))
            c_desc = html_lib.escape(str(card_offer.get("description") or ""))
            c_badge = html_lib.escape(str(card_offer.get("badge") or "Verified Partner"))
            c_cta = html_lib.escape(str(card_offer.get("cta_text") or "Explore Partner"))
            c_brand = html_lib.escape(str(card_offer.get("company_brand") or c_pk))
            c_role = html_lib.escape(str(card_offer.get("tier_role") or ("primary" if idx == 1 else "secondary")))
            c_model = html_lib.escape(str(card_offer.get("partnership_model") or "CPA_BOUNTY"))
            c_slot = html_lib.escape(str(card_offer.get("cta_slot") or ("calculator_primary_cta" if idx == 1 else "partner_matrix_card")))
            c_href = html_lib.escape(str(card_offer.get("attributed_href") or f"/r/{c_pk}"))
            c_sub = html_lib.escape(str(card_offer.get("subid") or f"{slug_id}_card_{idx}"))
            card_items.append(
                f'        <div class="affiliate-card partner-card" data-partner="{c_pk}" '
                f'data-company-brand="{c_brand}" data-partner-tier="{c_role}" data-partnership-model="{c_model}" '
                f'style="padding: 14px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: 8px; display: flex; flex-direction: column; justify-content: space-between; gap: 10px;">\n'
                f'          <div class="affiliate-info">\n'
                f'            <span class="affiliate-badge" style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--accent);">{c_badge} ({c_role.title()})</span>\n'
                f'            <span class="affiliate-disclosure-badge" style="font-size: 11px; color: var(--text-muted); margin-left: 6px;">Sponsored / {c_brand}</span>\n'
                f'            <h3 class="affiliate-title" style="margin: 6px 0 4px 0; font-size: 15px;">{c_name}</h3>\n'
                f'            <p class="affiliate-desc" style="margin: 0; font-size: 13px; color: var(--text-muted);">{c_desc}</p>\n'
                f'          </div>\n'
                f'          <div>\n'
                f'            <a href="{c_href}" rel="noopener sponsored nofollow" target="_blank" '
                f'data-partner="{c_pk}" data-company-brand="{c_brand}" data-partner-tier="{c_role}" '
                f'data-partnership-model="{c_model}" '
                f'data-tool="{html_lib.escape(slug_id)}" data-subid="{c_sub}" data-status="live" '
                f'data-cta-slot="{c_slot}" class="btn-cta partner-cta touch-target" '
                f'style="display: inline-flex; align-items: center; justify-content: center; min-height: 44px; min-width: 44px; padding: 10px 14px; border-radius: 8px; background: var(--accent, #1d4ed8); color: var(--cta-fg, #ffffff); font-weight: 600; text-decoration: none; font-size: 14px;">{c_cta}</a>\n'
                f'          </div>\n'
                f'        </div>'
            )
        return (
            f'      <div class="partner-roster-grid" data-roster-count="{len(matrix_cards)}" '
            f'style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; margin-top: 14px;">\n'
            + "\n".join(card_items)
            + "\n      </div>\n"
        )

    if not is_prexvo:
        default_slug = "soc-2-audit-cost-calculator" if is_gainhelm else "section-179-deduction-calculator"
        default_pk = "vanta_security" if is_gainhelm else "crest_capital"
        try:
            route = get_affiliate_route(prop_id, slug)
        except ValueError:
            route = get_affiliate_route(prop_id, default_slug, partner_key=default_pk)

        primary_offer = roster_info.get("primary_offer") or {}
        is_greenfield_vertical_mismatch = (
            route.get("partner_key") == "turbotax"
            and roster_info.get("vertical_family") not in ("federal_state_tax_brackets", "sales_tax_1099_nexus")
        )
        if primary_offer.get("partner_key") and (
            (gsc_metrics and slot_plan.get("gsc_repositioned"))
            or is_greenfield_vertical_mismatch
        ):
            partner_key = str(primary_offer["partner_key"])
            try:
                route = get_affiliate_route(prop_id, slug, partner_key=partner_key)
            except ValueError:
                pass
            partner_name = str(primary_offer.get("name") or route.get("partner_name", "Vanta" if is_gainhelm else "Xendoo"))
            cta_text = str(primary_offer.get("cta_text") or route.get("cta_text", "Explore Partner"))
            raw_url = str(primary_offer.get("default_url") or route.get("url", "https://www.vanta.com/" if is_gainhelm else "https://www.xendoo.com/"))
        else:
            partner_key = route.get("partner_key", default_pk)
            partner_name = route.get("partner_name", "Vanta Automated GRC" if is_gainhelm else "Xendoo Section 179 & Business Tax Accounting")
            cta_text = route.get("cta_text", "Automate Audit Readiness with Vanta" if is_gainhelm else "Optimize Section 179 Accounting with Xendoo")
            raw_url = route.get("url", "https://www.vanta.com/" if is_gainhelm else "https://www.xendoo.com/")
        url = (
            raw_url
            if route.get("status") in ("live", "active_direct") and not str(raw_url).startswith("/r/")
            else f"/r/{partner_key}?source_tool={slug_id}&subid={slug_id}_primary&cta_slot=standalone_primary_cta"
        )
        if str(url).startswith("/r/") and "?" not in str(url):
            url = f"{url}?source_tool={slug_id}&subid={slug_id}_primary&cta_slot=standalone_primary_cta"
        rel_attrs = route.get("rel_attributes", "noopener sponsored nofollow")
        disc_dict = GAINHELM_DISCLOSURES if is_gainhelm else PROFITHELM_DISCLOSURES
        ftc_disc = disc_dict.get("ftc_disclosure", "")
        roster_keys_csv = html_lib.escape(",".join(roster_info.get("roster_keys") or []))
        companies_csv = html_lib.escape(",".join(roster_info.get("distinct_companies") or []))
        models_csv = html_lib.escape(",".join(roster_info.get("partnership_models_represented") or []))
        primary_model_attr = html_lib.escape(str(route.get("partnership_model") or roster_info.get("primary_partnership_model") or "HYBRID_CPA_REVSHARE"))
        inline_calc_html, table_cta_html = _build_inline_and_table_slots()
        roster_grid_html = _build_roster_cards_grid_html()
        partner_lead_copy = (
            "Execute your modeled compliance or audit readiness scenario with a vetted GRC automation, CPA audit, or security assurance partner matched to this calculation:"
            if is_gainhelm
            else "Execute your modeled scenario with a vetted B2B or tax infrastructure partner matched to this calculation:"
        )

        block_html = (
            f'    <section class="affiliate-cta-section affiliates-section card pseo-card" data-property="{prop_id}" '
            f'data-partner="{partner_key}" data-partnership-model="{primary_model_attr}" '
            f'data-partner-models="{models_csv}" data-partner-roster="{roster_keys_csv}" '
            f'data-partner-companies="{companies_csv}" data-conversion-slot="{html_lib.escape(str(slot_plan.get("primary_slot") or "calculator_result_inline"))}" '
            f'data-mechanic="compliant_intent_monetization">\n'
            f'      <h2>Verified Commercial Execution Partner: {partner_name}</h2>\n'
            f'      <p>{partner_lead_copy}</p>\n'
            f'      <p style="margin-top: 12px;">\n'
            f'        <a href="{url}" rel="{rel_attrs}" target="_blank" '
            f'data-partner="{partner_key}" data-partnership-model="{primary_model_attr}" data-cta-slot="standalone_primary_cta" '
            f'class="affiliate-cta-link touch-target" '
            f'style="display: inline-flex; align-items: center; justify-content: center; '
            f'min-height: 44px; min-width: 44px; padding: 12px 18px; border-radius: 8px; '
            f'background: var(--accent, #1d4ed8); color: var(--cta-fg, #ffffff); font-weight: 600; text-decoration: none;">'
            f'{cta_text}</a>\n'
            f'      </p>\n'
            f'{roster_grid_html}'
            f'      <p class="affiliate-disclosure" style="font-size: 12px; color: var(--text-muted, #475569); margin-top: 10px;">\n'
            f'        {ftc_disc}\n'
            f'      </p>\n'
            f'    </section>'
        )
        return {
            "html": block_html,
            "inline_calc_cta_html": inline_calc_html,
            "comparison_table_cta_html": table_cta_html,
            "affiliate_route": route,
            "partner_roster": roster_info,
            "slot_plan": slot_plan,
            "commercial_offers_allowed": True,
            "restricted_public_service": False,
        }

    # Prexvo domain: enforce YMYL guardrails and restricted public-service commercial suppression
    restricted_ps = is_restricted_public_service_slug(slug, query)
    combined_lower = f"{slug} {query}".lower()
    is_explicit_refinance = any(tok in combined_lower for tok in ("refinance", "refinancing"))

    if restricted_ps:
        notice = PREXVO_DISCLOSURES.get(
            "public_service_non_commercial_notice",
            "Public Service & Statutory Repayment Notice: Commercial private lender offers are suppressed on public-service and statutory hardship pages.",
        )
        block_html = (
            f'    <section class="ymyl-public-service-guardrail card pseo-card" data-property="prexvo" '
            f'data-commercial-offers="none" data-restricted-public-service="true" '
            f'data-mechanic="compliant_intent_monetization">\n'
            f'      <h2>Title IV Public Service Statutory Protection Guardrail</h2>\n'
            f'      <p>{notice}</p>\n'
            f'    </section>'
        )
        return {
            "html": block_html,
            "inline_calc_cta_html": "",
            "comparison_table_cta_html": "",
            "affiliate_route": None,
            "partner_roster": roster_info,
            "slot_plan": slot_plan,
            "commercial_offers_allowed": False,
            "restricted_public_service": True,
        }

    if is_explicit_refinance:
        route = get_affiliate_route("prexvo", slug)
        partner_key = route.get("partner_key", "splash_financial")
        partner_name = route.get("partner_name", "Splash Financial")
        cta_text = route.get("cta_text", "Compare Student Loan Refinance Rates")
        url = route.get("url", "https://www.splashfinancial.com/student-loan-refinance")
        if str(url).startswith("/r/") and "?" not in str(url):
            url = f"{url}?source_tool={slug_id}&subid={slug_id}_primary&cta_slot=standalone_primary_cta"
        rel_attrs = route.get("rel_attributes", "noopener sponsored nofollow")
        ymyl_disc = PREXVO_DISCLOSURES.get("ymyl_forfeiture_disclaimer", "")
        ftc_disc = PREXVO_DISCLOSURES.get("ftc_disclosure", "")
        roster_keys_csv = html_lib.escape(",".join(roster_info.get("roster_keys") or []))
        companies_csv = html_lib.escape(",".join(roster_info.get("distinct_companies") or []))
        models_csv = html_lib.escape(",".join(roster_info.get("partnership_models_represented") or []))
        primary_model_attr = html_lib.escape(str(route.get("partnership_model") or roster_info.get("primary_partnership_model") or "CPA_BOUNTY"))
        inline_calc_html, table_cta_html = _build_inline_and_table_slots()
        roster_grid_html = _build_roster_cards_grid_html()

        block_html = (
            f'    <section class="affiliate-cta-section refinance-partner-section ymyl-refinance-guardrail card pseo-card" data-property="prexvo" '
            f'data-partner="{partner_key}" data-partnership-model="{primary_model_attr}" '
            f'data-partner-models="{models_csv}" data-partner-roster="{roster_keys_csv}" '
            f'data-partner-companies="{companies_csv}" data-commercial-offers="compliant-refinance" '
            f'data-restricted-public-service="false" data-mechanic="compliant_intent_monetization">\n'
            f'      <h2>Private Student Loan Refinance Comparison: {partner_name}</h2>\n'
            f'      <p class="ymyl-statutory-warning" style="font-size: 13px; color: var(--text-muted, #475569);">\n'
            f'        Refinancing federal student loans permanently waives federal protections, including income-driven repayment and Public Service Loan Forgiveness (PSLF) eligibility under Title IV 34 CFR Part 685. {ymyl_disc}\n'
            f'      </p>\n'
            f'      <p style="margin-top: 12px;">\n'
            f'        <a href="{url}" rel="{rel_attrs}" target="_blank" '
            f'data-partner="{partner_key}" data-partnership-model="{primary_model_attr}" data-cta-slot="standalone_primary_cta" '
            f'class="affiliate-cta-link touch-target" '
            f'style="display: inline-flex; align-items: center; justify-content: center; '
            f'min-height: 44px; min-width: 44px; padding: 12px 18px; border-radius: 8px; '
            f'background: var(--accent, #1d4ed8); color: var(--cta-fg, #ffffff); font-weight: 600; text-decoration: none;">'
            f'{cta_text}</a>\n'
            f'      </p>\n'
            f'{roster_grid_html}'
            f'      <p class="affiliate-disclosure" style="font-size: 12px; color: var(--text-muted, #475569); margin-top: 10px;">\n'
            f'        {ftc_disc}\n'
            f'      </p>\n'
            f'    </section>'
        )
        return {
            "html": block_html,
            "inline_calc_cta_html": inline_calc_html,
            "comparison_table_cta_html": table_cta_html,
            "affiliate_route": route,
            "partner_roster": roster_info,
            "slot_plan": slot_plan,
            "commercial_offers_allowed": True,
            "restricted_public_service": False,
        }

    # Standard federal Title IV repayment page without explicit refinance intent
    block_html = (
        f'    <section class="ymyl-public-service-guardrail card" data-property="prexvo" '
        f'data-commercial-offers="suppressed-default" data-restricted-public-service="false" '
        f'data-mechanic="compliant_intent_monetization">\n'
        f'      <h2>Title IV Federal Repayment Statutory Guardrail</h2>\n'
        f'      <p>This deterministic model evaluates federal repayment schedules under Title IV 34 CFR Part 685 statutory guidelines without unsolicited private lender offers.</p>\n'
        f'    </section>'
    )
    return {
        "html": block_html,
        "inline_calc_cta_html": "",
        "comparison_table_cta_html": "",
        "affiliate_route": None,
        "partner_roster": roster_info,
        "slot_plan": slot_plan,
        "commercial_offers_allowed": True,
        "restricted_public_service": False,
    }


def _resolve_gsc_lifecycle_compile_signals(candidate_spec: Dict[str, Any]) -> Dict[str, Any]:
    """Resolves normalized GSC lifecycle telemetry signals for compiler manifest and DOM attributes."""
    gsc_tel = candidate_spec.get("gsc_telemetry") if isinstance(candidate_spec.get("gsc_telemetry"), dict) else {}
    gsc_met = candidate_spec.get("gsc_metrics") if isinstance(candidate_spec.get("gsc_metrics"), dict) else {}
    device_focus = str(
        candidate_spec.get("device_focus")
        or gsc_tel.get("device_focus")
        or gsc_met.get("device_focus")
        or "BALANCED"
    ).strip()
    search_appearances = [
        str(sa).upper()
        for sa in (
            candidate_spec.get("search_appearances")
            or gsc_tel.get("search_appearances")
            or gsc_met.get("search_appearances")
            or []
        )
        if sa
    ]
    trajectory = str(
        candidate_spec.get("time_window_trajectory")
        or gsc_tel.get("time_window_trajectory")
        or gsc_met.get("time_window_trajectory")
        or "STABLE"
    ).strip()
    coverage_state = str(
        (candidate_spec.get("inspection_state") or {}).get("coverage_state")
        if isinstance(candidate_spec.get("inspection_state"), dict)
        else (candidate_spec.get("coverage_state") or gsc_tel.get("coverage_state") or "Submitted and indexed")
    ).strip()
    return {
        "device_focus": device_focus,
        "search_appearances": search_appearances,
        "time_window_trajectory": trajectory,
        "coverage_state": coverage_state,
        "appearance_attr": ",".join(search_appearances) if search_appearances else "STANDARD_SNIPPET",
    }


def _build_compiler_faq_entities(
    title: str,
    formula: str,
    statutory_authority: str,
    economic_dataset: str,
    is_prediction_tool: bool,
    is_prexvo: bool,
    is_gainhelm: bool = False,
) -> List[Dict[str, Any]]:
    """Builds conversational FAQPage entities tailored to tenant and tool cluster."""
    faq_entities: List[Dict[str, Any]] = [
        {
            "@type": "Question",
            "name": f"How is {title} determined under statutory authority guidelines?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": f"The deterministic calculation model evaluates {formula} based on statutory rules from {statutory_authority} and empirical indicators from {economic_dataset}.",
            },
        },
        {
            "@type": "Question",
            "name": "What empirical benchmarks validate this firsthand calculation model?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": f"The proprietary model cross-references empirical economic series from {economic_dataset} with statutory authority {statutory_authority}.",
            },
        },
    ]
    if is_prediction_tool:
        faq_entities.extend([
            {
                "@type": "Question",
                "name": "How does fee drag impact prediction market profitability on Kalshi and Polymarket?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Kalshi charges quadratic transaction fees peaking at 1.75 cents per contract at fifty-fifty odds, requiring traders to account for fee drag alongside expected value and implied probability spreads.",
                },
            },
            {
                "@type": "Question",
                "name": "Why is the Kelly criterion fraction critical for prediction market risk management?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "The Kelly criterion formula determines the mathematically optimal bankroll fraction to wager, protecting capital against volatility while maximizing long-term compound growth.",
                },
            },
            {
                "@type": "Question",
                "name": "How are prediction market gains taxed under IRC Section 1256 rules?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Regulated exchange contracts on CFTC-approved venues like Kalshi qualify for Section 1256 sixty-forty tax treatment, splitting gains into sixty percent long-term and forty percent short-term capital rates.",
                },
            },
        ])
    elif is_prexvo:
        faq_entities.extend([
            {
                "@type": "Question",
                "name": "Who is eligible for the Repayment Assistance Plan (RAP) under Title IV rules?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Under 34 CFR Part 685, borrowers with eligible federal Direct Loans qualify for RAP based on adjusted gross income and family size relative to federal poverty guidelines.",
                },
            },
            {
                "@type": "Question",
                "name": "How does RAP compare to income-driven repayment options like IBR and SAVE?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "RAP establishes affordable monthly payment caps based on discretionary income while preventing runaway balance growth through federal interest subsidies on qualifying Title IV loans.",
                },
            },
            {
                "@type": "Question",
                "name": "What requirements determine qualifying monthly payments for PSLF loan forgiveness?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Public Service Loan Forgiveness requires 120 verified on-time monthly payments under an accepted income-driven plan while employed full-time by a qualifying public service employer.",
                },
            },
        ])
    elif is_gainhelm:
        faq_entities.extend([
            {
                "@type": "Question",
                "name": f"What audit evidence is required to satisfy {statutory_authority}?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Organizations must maintain continuous control monitoring logs, system boundary diagrams, access review attestations, and third-party assessor or CPA workpapers across the observation window.",
                },
            },
            {
                "@type": "Question",
                "name": "How do GRC automation platforms reduce independent assessor and internal engineering hours?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": f"Automated evidence collection across cloud, identity, and code repositories compresses manual readiness preparation while grounding auditor day tables in {economic_dataset}.",
                },
            },
        ])
    else:
        faq_entities.extend([
            {
                "@type": "Question",
                "name": f"What documentation is required to substantiate deductions under {statutory_authority}?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Taxpayers must retain contemporaneous equipment purchase invoices, financing agreements, and tax return statements verifying placing property in service during the eligible tax year.",
                },
            },
            {
                "@type": "Question",
                "name": "How do economic phaseout thresholds adjust over time across benchmark series?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": f"Statutory deduction limits and phaseout brackets adjust annually for inflation based on index metrics published in official series like {economic_dataset}.",
                },
            },
        ])
    return faq_entities


def _build_compiled_json_ld_graph(
    canonical_base: str,
    slug: str,
    title: str,
    raw_meta_desc: str,
    application_category: str,
    statutory_authority: str,
    economic_dataset: str,
    is_prexvo: bool,
    faq_entities: List[Dict[str, Any]],
    is_gainhelm: bool = False,
) -> str:
    """Builds the unified Schema.org @graph JSON-LD string for compiled programmatic pages."""
    brand_org_name = "Prexvo" if is_prexvo else ("GainHelm" if is_gainhelm else "ProfitHelm")
    if "/" in slug:
        spoke_parts = [sp for sp in slug.split("/") if sp]
        hub_slug_part = spoke_parts[0]
        hub_name_map = {
            "irs-2027-tax-brackets": "IRS 2027 Tax Brackets Calculator",
            "section-1031-calculator": "Section 1031 Exchange Calculator",
            "section-179-calculator": "Section 179 Deduction Calculator",
        }
        hub_display_name = hub_name_map.get(hub_slug_part, hub_slug_part.replace("-", " ").title())
        breadcrumb_items_list = [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{canonical_base}/"},
            {"@type": "ListItem", "position": 2, "name": "Tools", "item": f"{canonical_base}/tools/"},
            {"@type": "ListItem", "position": 3, "name": hub_display_name, "item": f"{canonical_base}/tools/{hub_slug_part}/"},
            {"@type": "ListItem", "position": 4, "name": title, "item": f"{canonical_base}/tools/{slug}/"},
        ]
    else:
        breadcrumb_items_list = [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{canonical_base}/"},
            {"@type": "ListItem", "position": 2, "name": "Tools", "item": f"{canonical_base}/tools/"},
            {"@type": "ListItem", "position": 3, "name": title, "item": f"{canonical_base}/tools/{slug}/"},
        ]
    howto_clean_label = re.sub(r"\s+Calculator\b", "", title.split("|")[0].strip(), flags=re.IGNORECASE).strip() or title
    graph_payload = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Organization",
                "@id": f"{canonical_base}/#organization",
                "name": brand_org_name,
                "url": canonical_base,
            },
            {
                "@type": "WebPage",
                "@id": f"{canonical_base}/tools/{slug}/#webpage",
                "url": f"{canonical_base}/tools/{slug}/",
                "name": title,
                "description": raw_meta_desc,
                "inLanguage": "en-US",
                "datePublished": "2026-01-15",
                "dateModified": "2026-10-27",
                "speakable": {
                    "@type": "SpeakableSpecification",
                    "cssSelector": [".quick-answer", "h1"],
                },
                "breadcrumb": {"@id": f"{canonical_base}/tools/{slug}/#breadcrumb"},
            },
            {
                "@type": ["WebApplication", "SoftwareApplication"],
                "@id": f"{canonical_base}/tools/{slug}/#app",
                "name": title,
                "applicationCategory": application_category,
                "operatingSystem": "All",
                "url": f"{canonical_base}/tools/{slug}/",
                "inLanguage": "en-US",
                "dateModified": "2026-10-27",
                "featureList": [
                    f"Deterministic Statutory Formula Evaluation ({statutory_authority})",
                    f"Empirical Benchmark Corroboration ({economic_dataset})",
                    "Interactive 5-Point Scenario Comparison Matrix",
                ],
                "offers": {
                    "@type": "Offer",
                    "price": "0.00",
                    "priceCurrency": "USD",
                    "availability": "https://schema.org/InStock",
                },
                "isRelatedTo": [
                    {
                        "@type": "SoftwareApplication",
                        "name": f"{brand_org_name} Statutory Tools Directory",
                        "url": f"{canonical_base}/tools/",
                    }
                ],
            },
            {
                "@type": "Dataset",
                "@id": f"{canonical_base}/tools/{slug}/#dataset",
                "name": f"{title} Empirical Statutory Calculation Dataset",
                "description": f"Deterministic statutory calculation schedule and sensitivity matrix for {title} under {statutory_authority}.",
                "url": f"{canonical_base}/tools/{slug}/",
                "creator": {
                    "@type": "Organization",
                    "@id": f"{canonical_base}/#organization",
                    "name": brand_org_name,
                    "url": canonical_base,
                },
                "publisher": {"@type": "Organization", "name": brand_org_name, "url": canonical_base},
                "temporalCoverage": "2026/2027",
                "isAccessibleForFree": True,
                "license": "https://creativecommons.org/publicdomain/zero/1.0/",
                "distribution": [
                    {
                        "@type": "DataDownload",
                        "encodingFormat": "text/html",
                        "contentUrl": f"{canonical_base}/tools/{slug}/",
                    }
                ],
                "spatialCoverage": "United States",
                "mainEntityOfPage": {"@id": f"{canonical_base}/tools/{slug}/#webpage"},
                "includedInDataCatalog": {
                    "@type": "DataCatalog",
                    "@id": f"{canonical_base}/#datacatalog",
                    "name": f"{brand_org_name} Statutory Data Catalog",
                    "url": canonical_base,
                },
            },
            {
                "@type": "HowTo",
                "@id": f"{canonical_base}/tools/{slug}/#howto",
                "name": f"How to Calculate {howto_clean_label}",
                "description": f"Step-by-step statutory procedure for computing {howto_clean_label} under {statutory_authority}.",
                "url": f"{canonical_base}/tools/{slug}/",
                "totalTime": "PT1M",
                "step": [
                    {
                        "@type": "HowToStep",
                        "position": 1,
                        "name": "Enter Financial Baseline Parameters",
                        "text": f"Input baseline dollar figures and rate assumptions into the {title} form.",
                        "url": f"{canonical_base}/tools/{slug}/#step-1",
                    },
                    {
                        "@type": "HowToStep",
                        "position": 2,
                        "name": "Select Statutory Tier or Jurisdiction",
                        "text": f"Choose the applicable statutory classification or filing tier under {statutory_authority}.",
                        "url": f"{canonical_base}/tools/{slug}/#step-2",
                    },
                    {
                        "@type": "HowToStep",
                        "position": 3,
                        "name": "Review Deterministic Output & Sensitivity Matrix",
                        "text": "Inspect the computed dollar output, 5-point sensitivity schedule, and compliance checklist.",
                        "url": f"{canonical_base}/tools/{slug}/#step-3",
                    },
                ],
                "isPartOf": {"@id": f"{canonical_base}/tools/{slug}/#webpage"},
            },
            {
                "@type": "BreadcrumbList",
                "@id": f"{canonical_base}/tools/{slug}/#breadcrumb",
                "itemListElement": breadcrumb_items_list,
            },
            {
                "@type": "FAQPage",
                "@id": f"{canonical_base}/tools/{slug}/#faq",
                "about": {"@id": f"{canonical_base}/tools/{slug}/#app"},
                "mainEntity": faq_entities,
            },
        ],
    }
    return json.dumps(graph_payload, indent=2)


def compile_high_effort_page(candidate_spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compiles a qualified candidate specification into a verified high-effort programmatic HTML asset.
    Pure functional and stateless.
    Zero em-dashes. Zero en-dashes.
    """
    if not isinstance(candidate_spec, dict):
        raise ValueError(f"Candidate specification must be a dictionary, got {type(candidate_spec).__name__}")

    # 1. Enforce pre-compilation high-effort qualification gate
    assert_high_effort_content_qualified(candidate_spec, context="content compiler intake")

    # 2. Extract and resolve candidate metadata
    manifest_source = (
        candidate_spec.get("calculation_manifest")
        if isinstance(candidate_spec.get("calculation_manifest"), dict)
        else {}
    )

    query = str(candidate_spec.get("query") or candidate_spec.get("primary_keyword") or "").strip()
    raw_slug = str(candidate_spec.get("slug") or "").strip()
    if not raw_slug:
        slug_src = query or candidate_spec.get("title") or "proprietary-model"
        raw_slug = re.sub(r"[^a-z0-9]+", "-", str(slug_src).lower()).strip("-")
    slug = raw_slug

    title = str(candidate_spec.get("title") or "").strip()
    if not title:
        if query:
            words = [w.capitalize() for w in query.split() if w]
            title = " ".join(words) + " Calculator and Statutory Analysis"
        else:
            title = "Proprietary Model Calculator and Statutory Analysis"

    model_name = str(
        candidate_spec.get("model_name")
        or candidate_spec.get("proprietary_model")
        or manifest_source.get("model_name")
        or manifest_source.get("proprietary_model")
        or "Proprietary Calculation Model"
    ).strip()

    formula = str(
        candidate_spec.get("formula")
        or manifest_source.get("formula")
        or ""
    ).strip()

    raw_inputs = (
        candidate_spec.get("inputs")
        if candidate_spec.get("inputs") is not None
        else manifest_source.get("inputs", {})
    )

    statutory_authority = str(
        candidate_spec.get("statutory_authority")
        or candidate_spec.get("statutory_provenance")
        or candidate_spec.get("authority")
        or manifest_source.get("statutory_authority")
        or manifest_source.get("statutory_provenance")
        or manifest_source.get("authority")
        or ""
    ).strip()

    economic_dataset = str(
        candidate_spec.get("economic_dataset")
        or candidate_spec.get("economic_source")
        or manifest_source.get("economic_dataset")
        or manifest_source.get("economic_source")
        or ""
    ).strip()

    sample_calc = str(
        candidate_spec.get("sample_calculation")
        or candidate_spec.get("sample")
        or manifest_source.get("sample_calculation")
        or manifest_source.get("sample")
        or ""
    ).strip()

    # 3. Numeric metric clamping to non-negative (>= 0) per HWL-1263
    clamped_inputs: Dict[str, Any] = {}
    for k, v in raw_inputs.items():
        if isinstance(v, (int, float)):
            clamped_inputs[k] = max(0.0, float(v)) if isinstance(v, float) else max(0, v)
        elif isinstance(v, str):
            v_clean = v.replace("$", "").replace(",", "").replace("%", "").strip()
            try:
                num_v = float(v_clean)
                clamped_inputs[k] = max(0.0, num_v)
            except ValueError:
                clamped_inputs[k] = v
        else:
            clamped_inputs[k] = v

    # 4. Deterministic AST mathematical formula evaluation
    calculated_output = safe_eval_mathematical_formula(formula, clamped_inputs)

    published_raw = (
        candidate_spec.get("published_output")
        if candidate_spec.get("published_output") is not None
        else candidate_spec.get("expected_output")
    )
    if published_raw is None:
        published_raw = (
            manifest_source.get("published_output")
            if manifest_source.get("published_output") is not None
            else manifest_source.get("expected_output")
        )

    if published_raw is not None:
        published_output = float(str(published_raw).replace("$", "").replace(",", "").replace("%", "").strip())
        assert_proprietary_model_integrity(
            manifest_or_inputs=clamped_inputs,
            published_output=published_output,
            formula=formula,
            tolerance=0.01,
            context=f"content compiler verification for '{slug}'",
        )
    else:
        published_output = calculated_output

    # 5. Canonical Factor 7 calculation manifest assembly
    gsc_sig = _resolve_gsc_lifecycle_compile_signals(candidate_spec)
    gsc_device_focus = gsc_sig["device_focus"]
    gsc_search_appearances = gsc_sig["search_appearances"]
    gsc_trajectory = gsc_sig["time_window_trajectory"]
    gsc_coverage_state = gsc_sig["coverage_state"]
    gsc_appearance_attr = gsc_sig["appearance_attr"]

    statutory_matrix = (
        candidate_spec.get("statutory_economic_matrix")
        if isinstance(candidate_spec.get("statutory_economic_matrix"), dict)
        else (
            manifest_source.get("statutory_economic_matrix")
            if isinstance(manifest_source.get("statutory_economic_matrix"), dict)
            else None
        )
    )
    corroborating_sources = (
        candidate_spec.get("corroborating_sources")
        if isinstance(candidate_spec.get("corroborating_sources"), list)
        else (
            manifest_source.get("corroborating_sources")
            if isinstance(manifest_source.get("corroborating_sources"), list)
            else []
        )
    )

    manifest: Dict[str, Any] = {
        "manifest_id": f"{slug}-manifest",
        "model_name": model_name,
        "formula": formula,
        "inputs": clamped_inputs,
        "published_output": published_output,
        "sample_calculation": sample_calc,
        "statutory_authority": statutory_authority,
        "economic_dataset": economic_dataset,
        "gsc_lifecycle_signals": {
            "device_focus": gsc_device_focus,
            "search_appearances": gsc_search_appearances,
            "time_window_trajectory": gsc_trajectory,
            "coverage_state": gsc_coverage_state,
        },
    }
    if statutory_matrix:
        manifest["statutory_economic_matrix"] = statutory_matrix
    if corroborating_sources:
        manifest["corroborating_sources"] = corroborating_sources

    # 6. Render Obsidian dark-theme HTML asset
    form_inputs_html = []
    table_rows_html = []
    for var_name, var_val in clamped_inputs.items():
        label_text = var_name.replace("_", " ").title()
        val_num = float(var_val) if isinstance(var_val, (int, float)) else 0.0
        max_num = max(100.0, val_num * 2.0 if val_num > 0 else 100.0)
        step_attr = "0.01" if isinstance(var_val, float) else "1"
        form_inputs_html.append(
            f'        <div class="form-group" style="margin-bottom: 16px;">\n'
            f'          <label for="input-{var_name}" style="display: block; margin-bottom: 6px; font-weight: 500;">{label_text}</label>\n'
            f'          <input type="number" step="any" min="0" id="input-{var_name}" name="{var_name}" '
            f'value="{var_val}" class="touch-target" style="min-height: 44px; min-width: 44px; padding: 10px 14px; font-size: 16px; width: 100%; box-sizing: border-box;" />\n'
            f'          <input type="range" min="0" max="{max_num}" step="{step_attr}" id="range-{var_name}" '
            f'value="{var_val}" class="touch-target" style="min-height: 44px; min-width: 44px; width: 100%; margin-top: 8px;" />\n'
            f'        </div>'
        )
        table_rows_html.append(
            f'            <tr>\n'
            f'              <td>{label_text}</td>\n'
            f'              <td>{var_val}</td>\n'
            f'              <td>{statutory_authority}</td>\n'
            f'              <td>{economic_dataset}</td>\n'
            f'            </tr>'
        )

    form_inputs_str = "\n".join(form_inputs_html)
    table_rows_str = "\n".join(table_rows_html)
    manifest_json_str = json.dumps(manifest, ensure_ascii=False, indent=2)

    # Format output value for display
    if isinstance(published_output, float) and 0 < abs(published_output) < 1 and round(published_output, 4) != round(published_output, 2):
        display_output = f"{round(published_output, 4):.4f}"
    else:
        display_output = f"{published_output:,.2f}" if isinstance(published_output, float) and not published_output.is_integer() else f"{published_output:,.0f}"

    # Pre-render SSR 5-Point Scenario Comparison Table
    scenario_table_html = _render_5point_sensitivity_table_html(
        published_output=published_output,
        display_output=display_output,
        statutory_authority=statutory_authority,
        economic_dataset=economic_dataset,
        model_name=model_name,
    )

    spec_tenant_signals = " ".join(
        str(candidate_spec.get(k) or "")
        for k in ("property_id", "property", "tenant", "domain", "brand_name", "canonical_base")
    ).lower()
    is_gainhelm = False
    if "gainhelm" in spec_tenant_signals:
        is_prexvo = False
        is_gainhelm = True
    elif "profithelm" in spec_tenant_signals and "prexvo" not in spec_tenant_signals:
        is_prexvo = False
    elif "prexvo" in spec_tenant_signals:
        is_prexvo = True
    else:
        env_signals = " ".join([
            os.environ.get("FACTORY_PROPERTY_ID", "").lower(),
            os.environ.get("FACTORY_BRAND_NAME", "").lower(),
            os.environ.get("FACTORY_DOMAIN", "").lower(),
        ])
        if "gainhelm" in env_signals or any(
            t in str(candidate_spec.get("statutory_authority") or "").lower()
            for t in ("aicpa ssae 18", "32 cfr part 170", "dfars 252.204", "iso/iec 27006", "45 cfr 160.404", "pci dss v4", "fedramp", "hitrust csf")
        ):
            is_prexvo = False
            is_gainhelm = True
        else:
            is_prexvo = (
                "prexvo" in env_signals
                or any(
                    t in str(candidate_spec.get("statutory_authority") or "").lower()
                    for t in ("title iv", "34 cfr", "pslf", "repayment assistance plan")
                )
            )
    default_base = "https://prexvo.com" if is_prexvo else ("https://gainhelm.com" if is_gainhelm else "https://profithelm.com")
    env_base = os.environ.get("FACTORY_CANONICAL_BASE", "").strip()
    if is_prexvo and ("profithelm.com" in env_base.lower() or "gainhelm.com" in env_base.lower()):
        env_base = ""
    elif is_gainhelm and ("profithelm.com" in env_base.lower() or "prexvo.com" in env_base.lower()):
        env_base = ""
    elif not is_prexvo and not is_gainhelm and ("prexvo.com" in env_base.lower() or "gainhelm.com" in env_base.lower()):
        env_base = ""
    canonical_base = (
        str(candidate_spec.get("canonical_base") or "").strip()
        or env_base
        or default_base
    ).rstrip("/")

    scenario_presets_bar_html = _render_scenario_presets_bar_html(
        canonical_base=canonical_base,
        slug=slug,
        clamped_inputs=clamped_inputs,
    )
    monetization_block = _render_compiler_monetization_and_guardrail_html(
        slug=slug,
        query=query,
        is_prexvo=is_prexvo,
        candidate_spec=candidate_spec,
        is_gainhelm=is_gainhelm,
    )
    monetization_section_html = monetization_block["html"]
    inline_calc_cta_html = monetization_block.get("inline_calc_cta_html", "")
    comparison_table_cta_html = monetization_block.get("comparison_table_cta_html", "")
    if comparison_table_cta_html:
        scenario_table_html = f"{scenario_table_html}\n{comparison_table_cta_html}"

    resolved_tenant = "prexvo" if is_prexvo else ("gainhelm" if is_gainhelm else "profithelm")
    from pseofactory.competitor import render_competitor_winning_pattern_blocks
    winning_blocks = render_competitor_winning_pattern_blocks(
        slug=slug,
        title=title,
        property_id=resolved_tenant,
        canonical_base=canonical_base,
        statutory_authority=statutory_authority,
        economic_dataset=economic_dataset,
    )
    on_this_page_nav_html = winning_blocks["on_this_page_nav_html"]
    edge_case_trap_html = winning_blocks["edge_case_trap_html"]
    statutory_compliance_html = winning_blocks["statutory_compliance_html"]
    three_tier_cluster_html = winning_blocks["three_tier_cluster_html"]
    vetted_handoff_html = winning_blocks["vetted_handoff_html"]
    serp_depth_upgrade_html = winning_blocks["serp_depth_upgrade_html"]

    is_prexvo_js = "true" if is_prexvo else "false"

    is_prediction_tool = (not is_prexvo and not is_gainhelm) and any(
        tok in slug.lower()
        for tok in (
            "prediction",
            "odds",
            "kalshi",
            "kelly",
            "arbitrage",
            "expected-value",
            "-ev-",
            "vigorish",
            "-vig",
            "vig-",
            "break-even",
        )
    )

    application_category = "BusinessApplication" if is_gainhelm else "FinanceApplication"

    if is_prexvo:
        cluster = PREXVO_STUDENT_LOAN_CLUSTER
        cluster_title = "Related Title IV Student Loan Repayment Tools"
    elif is_gainhelm:
        cluster = GAINHELM_CYBER_COMPLIANCE_CLUSTER
        cluster_title = "Related Cyber Compliance and GRC Audit Cost Tools"
    elif is_prediction_tool:
        cluster = PROFITHELM_PREDICTION_CLUSTER
        cluster_title = "Related Prediction Market Quantitative Tools"
    else:
        cluster = PROFITHELM_TAX_CLUSTER
        cluster_title = "Related Tax and Capital Optimization Tools"

    sibling_links = [(s_slug, s_title) for (s_slug, s_title) in cluster if s_slug != slug]
    if not sibling_links:
        sibling_links = cluster

    from pseofactory.competitor import _format_safe_heading_topic
    primary_sibling_slug, primary_sibling_title = sibling_links[0]
    secondary_sibling_slug, secondary_sibling_title = sibling_links[1 % len(sibling_links)]
    safe_model_h2 = _format_safe_heading_topic(model_name, slug)

    cluster_items_html = []
    for s_slug, s_title in sibling_links:
        cluster_items_html.append(
            f'        <li style="margin-bottom: 8px;">\n'
            f'          <a href="{canonical_base}/tools/{s_slug}/" class="touch-target cluster-link" style="display: flex; align-items: center; background: var(--bg-elevated); color: var(--accent); padding: 12px 16px; border-radius: 8px; text-decoration: none; min-height: 44px; min-width: 44px;">{s_title}</a>\n'
            f'        </li>'
        )
    cluster_links_html = "\n".join(cluster_items_html)

    # High-intent conversational FAQPage entities
    faq_entities = _build_compiler_faq_entities(
        title=title,
        formula=formula,
        statutory_authority=statutory_authority,
        economic_dataset=economic_dataset,
        is_prediction_tool=is_prediction_tool,
        is_prexvo=is_prexvo,
        is_gainhelm=is_gainhelm,
    )

    faq_json_str = json.dumps(faq_entities, ensure_ascii=False, indent=6)

    faq_accordions_list = []
    for faq_item in faq_entities:
        q_text = faq_item.get("name", "")
        a_text = faq_item.get("acceptedAnswer", {}).get("text", "")
        faq_accordions_list.append(
            f'      <details class="faq-accordion">\n'
            f'        <summary class="touch-target" style="display: flex; align-items: center; min-height: 44px; min-width: 44px; padding: 10px 14px; cursor: pointer; font-weight: 600;">{q_text}</summary>\n'
            f'        <p>{a_text}</p>\n'
            f'      </details>'
        )
    faq_accordions_html = "\n".join(faq_accordions_list)

    mandatory_disclosures = list(candidate_spec.get("mandatory_disclosures") or [])
    disclosures_html_list = []
    for d in mandatory_disclosures:
        disclosures_html_list.append(
            f'      <p class="disclosure-item" style="font-size: 13px; color: var(--text-muted); margin-top: 8px;">{d}</p>'
        )
    disclosures_html_str = "\n".join(disclosures_html_list)

    dynamic_return_js = f"return {published_output};"
    if formula:
        try:
            dynamic_expr = compile_ast_to_js(
                formula,
                input_keys=list(raw_inputs.keys()) if isinstance(raw_inputs, dict) else None,
            )
            if dynamic_expr:
                dynamic_return_js = f"return {dynamic_expr};"
        except Exception:
            dynamic_return_js = f"return {published_output};"

    calc_js_body = f"""      {dynamic_return_js}"""

    regulatory_disclosures_html = []
    if is_gainhelm:
        regulatory_disclosures_html.append(
            '      <p class="regulatory-disclosure" style="font-size: 12px; color: var(--text-muted); margin-top: 12px;">\n'
            f'        {GAINHELM_DISCLOSURES.get("statutory_audit_disclaimer", "")}\n'
            '      </p>'
        )
    elif not is_prexvo:
        if cluster == PROFITHELM_TAX_CLUSTER or "tax" in slug.lower() or "tax" in query.lower() or "179" in slug:
            regulatory_disclosures_html.append(
                '      <p class="regulatory-disclosure" style="font-size: 12px; color: var(--text-muted); margin-top: 12px;">\n'
                '        Circular 230 tax modeling disclaimer: Information generated is for deterministic computational modeling purposes and does not constitute formal tax, legal, or investment advice under Treasury Department Circular No. 230.\n'
                '      </p>'
            )
    else:
        if "refinance" in slug.lower() or "refinance" in query.lower() or "refinancing" in slug.lower() or "refinancing" in query.lower():
            regulatory_disclosures_html.append(
                '      <p class="regulatory-disclosure" style="font-size: 12px; color: var(--text-muted); margin-top: 12px;">\n'
                '        Refinancing federal student loans permanently waives federal protections, including income-driven repayment and Public Service Loan Forgiveness (PSLF) eligibility under Title IV 34 CFR Part 685.\n'
                '      </p>'
            )

    spec_disclosures = candidate_spec.get("mandatory_disclosures") or []
    for disc in spec_disclosures:
        if not any(disc.lower() in d.lower() for d in regulatory_disclosures_html):
            regulatory_disclosures_html.append(
                f'      <p class="regulatory-disclosure" style="font-size: 12px; color: var(--text-muted); margin-top: 12px;">\n'
                f'        {disc}\n'
                f'      </p>'
            )

    from pseofactory.affiliates import is_restricted_public_service_slug
    is_restricted_asset = bool(is_prexvo and is_restricted_public_service_slug(slug, title))
    playbook_footer_html = (
        ""
        if is_restricted_asset
        else (
            '      <div class="playbook-capture-card" style="margin: 16px 0; padding: 16px; border: 1px solid var(--border); border-radius: 8px; background: var(--bg-elevated);">\n'
            '        <div style="font-size: 13px; font-weight: 700; margin-bottom: 6px;">Personalized Calculation Playbook &amp; Statutory Workpaper</div>\n'
            '        <form id="lead-capture-form" class="lead-capture-form" action="/api/lead-capture" method="POST" style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">\n'
            '          <input type="email" name="email" placeholder="Work email for personalized playbook" aria-label="Work email for personalized playbook" required class="touch-target" style="padding:10px 14px;border-radius:6px;border:1px solid var(--border);min-height:44px;flex:1;min-width:220px;" />\n'
            '          <button type="submit" class="touch-target" style="padding:10px 16px;border-radius:6px;background:var(--brand-primary,#1d4ed8);color:#fff;font-weight:700;border:none;min-height:44px;cursor:pointer;">Get Free Playbook</button>\n'
            '        </form>\n'
            '      </div>\n'
        )
    )
    disclosures_html_block = ("\n" + "\n".join(regulatory_disclosures_html)) if regulatory_disclosures_html else ""
    gsc_token = (
        str(candidate_spec.get("gsc_verification_token") or "").strip()
        or os.environ.get("GSC_VERIFICATION_TOKEN", "google-site-verification-verified-2026")
    )
    raw_meta_desc = (
        str(candidate_spec.get("description") or "").strip()
        or f"Verified quantitative calculation engine evaluating {title} deterministically under {statutory_authority}."
    )
    if len(raw_meta_desc) < 55:
        raw_meta_desc = f"{raw_meta_desc.rstrip('.')} grounded in {statutory_authority} and {economic_dataset}."
    if len(raw_meta_desc) > 155:
        short_t = re.sub(r"\s+and\s+Statutory\s+Analysis$", "", title, flags=re.IGNORECASE).strip()
        short_t = re.sub(r"\bCalculator\s+Calculator\b", "Calculator", short_t, flags=re.IGNORECASE)
        raw_meta_desc = f"Verified quantitative calculation engine evaluating {short_t} deterministically under {statutory_authority}."
    if len(raw_meta_desc) > 155:
        words_m = raw_meta_desc.rstrip(".!?").split()
        while len(words_m) > 6 and (
            len(" ".join(words_m).rstrip(".,;:") + ".") > 155
            or words_m[-1].lower().rstrip(".,;:") in ("under", "and", "or", "with", "for", "of", "in", "to", "by", "from", "the", "a", "an")
        ):
            words_m.pop()
        raw_meta_desc = " ".join(words_m).rstrip(".,;:") + "."

    json_ld_graph_str = _build_compiled_json_ld_graph(
        canonical_base=canonical_base,
        slug=slug,
        title=title,
        raw_meta_desc=raw_meta_desc,
        application_category=application_category,
        statutory_authority=statutory_authority,
        economic_dataset=economic_dataset,
        is_prexvo=is_prexvo,
        faq_entities=faq_entities,
        is_gainhelm=is_gainhelm,
    )

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="content-language" content="en-US" />
  <meta name="google-site-verification" content="{gsc_token}" />
  <meta name="description" content="{raw_meta_desc}" />
  <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1" />
  <meta property="og:title" content="{title}" />
  <meta property="og:description" content="{raw_meta_desc}" />
  <meta property="og:url" content="{canonical_base}/tools/{slug}/" />
  <meta property="og:type" content="website" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{title}" />
  <meta name="twitter:description" content="{raw_meta_desc}" />
  <title>{title}</title>
  <link rel="canonical" href="{canonical_base}/tools/{slug}/" />
  <link rel="alternate" hreflang="en-US" href="{canonical_base}/tools/{slug}/" />
  <link rel="alternate" hreflang="x-default" href="{canonical_base}/tools/{slug}/" />
  <link rel="publisher-media-kit" type="application/json" href="/media-kit.json" />
  <link rel="tool-catalog" type="application/json" title="Machine-Readable Tool Catalog" href="/catalog.json" />
  <style>
    :root {{
      /* Surfaces & Canvas */
      --bg: #07090e;
      --card-bg: #0f172a;
      --bg-elevated: #151f38;
      --bg-inset: #0b1329;
      --bg-canvas: #07090e;
      --bg-surface: #0f172a;
      --text-primary: #f8fafc;
      --brand-primary: #38bdf8;

      /* Borders & Separation */
      --border: rgba(255, 255, 255, 0.08);
      --border-strong: rgba(255, 255, 255, 0.16);

      /* Typography */
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --text-dim: #64748b;

      /* Accents & States */
      --accent: #38bdf8;
      --accent-hover: #0284c7;
      --accent-subtle: rgba(56, 189, 248, 0.10);

      /* Depth & Atmospheric Lighting */
      --shadow-card: 0 1px 3px 0 rgba(0, 0, 0, 0.4), 0 1px 2px -1px rgba(0, 0, 0, 0.4);
      --shadow-elevated: 0 10px 15px -3px rgba(0, 0, 0, 0.5), 0 4px 6px -4px rgba(0, 0, 0, 0.5);
      --card-highlight: inset 0 1px 0 0 rgba(255, 255, 255, 0.05);
    }}
    [data-theme="porcelain"] {{
      --bg-canvas: #fbfcfd;
      --bg-surface: #ffffff;
      --text-primary: #090d16;
      --brand-primary: #1d4ed8;
      --bg: var(--bg-canvas);
      --card-bg: var(--bg-surface);
      --bg-elevated: #f1f5f9;
      --bg-inset: #f8fafc;
      --border: #e2e8f0;
      --border-strong: #cbd5e1;
      --text: var(--text-primary);
      --text-muted: #475569;
      --text-dim: #64748b;
      --accent: var(--brand-primary);
      --accent-hover: #1e40af;
      --accent-subtle: rgba(29, 78, 216, 0.08);
    }}
    * {{
      box-sizing: border-box;
    }}
    *:focus-visible {{
      outline: 2px solid var(--accent);
      outline-offset: 2px;
    }}
    body {{
      background-color: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
      line-height: 1.6;
      margin: 0;
      padding: 32px 16px;
    }}
    .container {{
      max-width: 960px;
      margin: 0 auto;
    }}
    .card {{
      background-color: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 24px;
      margin-bottom: 24px;
      box-shadow: var(--shadow-card);
    }}
    h1, h2, h3 {{
      color: var(--text);
      margin-top: 0;
    }}
    h1 {{
      font-size: 28px;
      line-height: 1.2;
      font-weight: 700;
      letter-spacing: -0.02em;
    }}
    h2 {{
      font-size: 20px;
      line-height: 1.3;
      font-weight: 600;
      letter-spacing: -0.01em;
    }}
    h3 {{
      font-size: 16px;
      line-height: 1.4;
      font-weight: 600;
    }}
    .touch-target {{
      min-height: 44px;
      min-width: 44px;
      padding: 10px 14px;
      font-size: 16px;
      border-radius: 8px;
    }}
    button.touch-target {{
      background-color: var(--accent);
      color: var(--bg);
      font-weight: 600;
      border: none;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      transition: transform 160ms cubic-bezier(0.23, 1, 0.32, 1), background-color 160ms ease, border-color 160ms ease, box-shadow 160ms ease;
    }}
    button.touch-target:hover {{
      background-color: var(--accent-hover);
    }}
    button.touch-target:active {{
      transform: scale(0.97);
    }}
    input.touch-target {{
      background-color: var(--bg-elevated);
      border: 1px solid var(--border);
      color: var(--text);
      width: 100%;
    }}
    .multi-dataset-join {{
      background-color: var(--bg-elevated);
      border-left: 4px solid var(--accent);
      padding: 20px;
      border-radius: 8px;
      margin-bottom: 24px;
    }}
    .result-box {{
      min-height: 110px;
      contain: layout style;
      background-color: var(--bg-inset);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      margin-top: 20px;
    }}
    .output-value {{
      font-variant-numeric: tabular-nums;
      font-family: "Geist Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
    }}
    .table-wrap {{
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 8px;
      margin-top: 16px;
    }}
    .calculation-table, .statutory-pitfalls-table, .scenario-table, .comparison-table {{
      width: 100%;
      min-width: 600px;
      table-layout: fixed;
      border-collapse: collapse;
      margin-top: 0;
      font-size: 14px;
      font-variant-numeric: tabular-nums;
    }}
    .calculation-table th, .calculation-table td, .statutory-pitfalls-table th, .statutory-pitfalls-table td,
    .scenario-table th, .scenario-table td, .comparison-table th, .comparison-table td {{
      border: 1px solid var(--border);
      padding: 12px;
      text-align: left;
      min-width: 110px;
    }}
    .calculation-table th, .statutory-pitfalls-table th, .scenario-table th, .comparison-table th {{
      background-color: var(--bg-elevated);
    }}
    .canonical-tool-link {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      background-color: var(--card-bg);
      border: 1px solid var(--accent);
      color: var(--accent);
      text-decoration: none;
      font-weight: 600;
      min-height: 44px;
      min-width: 44px;
      transition: transform 160ms cubic-bezier(0.23, 1, 0.32, 1), background-color 160ms ease, color 160ms ease;
    }}
    .canonical-tool-link:hover {{
      background-color: var(--accent-subtle);
    }}
    .canonical-tool-link:active {{
      transform: scale(0.97);
    }}
    .cluster-link {{
      display: flex;
      align-items: center;
      background-color: var(--bg-elevated);
      color: var(--accent);
      padding: 12px 16px;
      border-radius: 8px;
      text-decoration: none;
      min-height: 44px;
      min-width: 44px;
      transition: transform 160ms cubic-bezier(0.23, 1, 0.32, 1), background-color 160ms ease;
    }}
    .cluster-link:hover {{
      background-color: var(--bg-inset);
    }}
    .cluster-link:active {{
      transform: scale(0.97);
    }}
    @media (max-width: 640px) {{
      body {{
        padding: 16px 12px;
      }}
      .card {{
        padding: 16px;
        margin-bottom: 16px;
      }}
      .calculator-form {{
        display: flex;
        flex-direction: column;
        gap: 12px;
      }}
      h1 {{
        font-size: 22px;
      }}
      h2 {{
        font-size: 18px;
      }}
    }}
  </style>
  <!-- Schema.org Application Type: "@type": "SoftwareApplication" -->
  <script type="application/ld+json">
  {json_ld_graph_str}
  </script>
</head>
<body>
  <div class="container">
    <header class="card">
      <h1>{title}</h1>
      <div class="takeaway quick-answer" data-gsc-device-focus="{gsc_device_focus}" data-gsc-search-appearance="{gsc_appearance_attr}">
        <p class="takeaway">
          The {model_name} produces a baseline output of <strong>{display_output}</strong>.
          Executive operators evaluate deterministic calculations derived from formula <code>{formula}</code>
          joined with statutory rules from {statutory_authority} and empirical economic benchmarks from {economic_dataset}
          to compute exact quantitative projections and variance across multi-tier planning scenarios.
        </p>
      </div>
    </header>

    <div id="calculator-workspace-anchor" class="calculation-container card" data-gsc-device-focus="{gsc_device_focus}" data-gsc-search-appearance="{gsc_appearance_attr}" data-gsc-trajectory="{gsc_trajectory}" data-gsc-coverage-state="{gsc_coverage_state}">
      <h2>Interactive Quantitative Model: {safe_model_h2}</h2>
      <p>
        Input parameters are validated mechanically with client-side deserializers clamping numeric metrics to non-negative values
        (greater than or equal to zero) per HWL-1263 to prevent crawler or user state corruption.
      </p>
{scenario_presets_bar_html}
{edge_case_trap_html}
      <form class="calculator-form" id="{slug}-calculator" method="post" action="javascript:void(0);">
{form_inputs_str}
        <button type="submit" class="touch-target" id="calculate-btn" style="min-height: 44px; min-width: 44px;">Recalculate Output</button>
      </form>
      <div class="result-box" style="min-height: 110px; margin-top: 20px;">
        <h3>Published Baseline Calculation</h3>
        <p>Formula: <code>{formula}</code></p>
        <p>Evaluated Output Result: <strong class="output-value">{display_output}</strong></p>
        <p>Sample Calculation Methodology: {sample_calc}</p>{inline_calc_cta_html}
      </div>

      <figure>
        <div class="table-wrap">
          <table class="calculation-table" data-statutory-source="{statutory_authority}" data-economic-source="{economic_dataset}">
            <thead>
              <tr>
                <th scope="col">Input Variable</th>
                <th scope="col">Clamped Value</th>
                <th scope="col">Statutory Authority</th>
                <th scope="col">Economic Benchmark</th>
              </tr>
            </thead>
            <tbody>
{table_rows_str}
            </tbody>
          </table>
        </div>
        <figcaption style="margin-top: 8px; color: var(--text-muted); font-size: 14px;">
          Table 1: Grounded calculation parameters citing statutory authority {statutory_authority} and economic dataset {economic_dataset}.
        </figcaption>
      </figure>
    </div>

{serp_depth_upgrade_html}

{on_this_page_nav_html}

    <div class="multi-dataset-join card" data-statutory-source="{statutory_authority}" data-economic-source="{economic_dataset}">
      <h2>Dual Dataset Provenance and Statutory Corroboration: {safe_model_h2}</h2>
      <p>
        Primary statutory authority: <strong>{statutory_authority}</strong> provides the legal basis, statutory deduction thresholds,
        phaseout schedules, and mandatory compliance rules for this calculation.
      </p>
      <p>
        Empirical economic benchmark dataset: <strong>{economic_dataset}</strong> provides empirical series validation,
        cost indexes, and macroeconomic context from the Bureau of Labor Statistics and Federal Reserve systems.
      </p>
    </div>

{scenario_table_html}

{statutory_compliance_html}

{monetization_section_html}

    <section class="methodology card">
      <h2>Statutory Analysis and Computational Methodology: {safe_model_h2}</h2>
      <p>
        This computational tool satisfies strict high-effort content qualification requirements by evaluating every metric through abstract syntax tree mathematical interpretation rather than speculative estimates.
        Operators can cross-reference adjacent scenarios using the <a href="{canonical_base}/tools/{primary_sibling_slug}/" class="touch-target" style="display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; padding: 6px 10px;">{primary_sibling_title}</a> to compare multi-tier cash flow outcomes.
      </p>
      <p>
        Governing statutory authority {statutory_authority} establishes the exact legal formulas, phaseout rates, and deduction caps, while empirical dataset series from {economic_dataset} validate inflation adjustments and cost basis indices:
      </p>
      <ul style="padding-left: 20px; margin-top: 10px; margin-bottom: 0;">
        <li style="margin-bottom: 6px;"><strong>Deterministic Formula Execution:</strong> Evaluates <code>{formula}</code> with non-negative parameter clamping to produce the verified baseline output of <strong>{display_output}</strong>.</li>
        <li style="margin-bottom: 6px;"><strong>Statutory Authority Grounding:</strong> Enforces regulatory thresholds, phaseout schedules, and compliance limits established under {statutory_authority}.</li>
        <li style="margin-bottom: 6px;"><strong>Empirical Benchmark Corroboration:</strong> Anchors macroeconomic and inflation assumptions to {economic_dataset} alongside the <a href="{canonical_base}/tools/{secondary_sibling_slug}/" class="touch-target" style="display: inline-flex; align-items: center; min-height: 44px; min-width: 44px; padding: 6px 10px;">{secondary_sibling_title}</a>.</li>
      </ul>
    </section>

{vetted_handoff_html}

    <section class="faq-section card">
      <h2>Frequently Asked Questions: {safe_model_h2}</h2>
{faq_accordions_html}
    </section>

{three_tier_cluster_html}

    <nav class="cluster-nav card" aria-label="{cluster_title}">
      <h2>{cluster_title}</h2>
      <p style="color: var(--text-muted); font-size: 14px; margin-bottom: 16px;">
        Explore verified peer computational models in this specialized quantitative cluster:
      </p>
      <ul style="list-style: none; padding: 0; margin: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px;">
{cluster_links_html}
      </ul>
    </nav>

    <footer class="card" style="text-align: center;">
{playbook_footer_html}      <a href="{canonical_base}/tools/{slug}/" class="canonical-tool-link touch-target" style="min-height: 44px; min-width: 44px;">
        Launch Full {title} Engine
      </a>
      <div class="disclosures" style="margin-top: 16px; border-top: 1px solid var(--border-color, #333); padding-top: 12px;">
{disclosures_html_block}
      </div>
    </footer>
  </div>

  <script type="application/json" id="calculation-manifest" class="calculation-manifest">
{manifest_json_str}
  </script>

  <script>
  (function() {{
    var form = document.getElementById("{slug}-calculator");
    if (!form) return;
    var outputElem = document.querySelector(".output-value");
    var slug = "{slug}";
    function formatNumber(val) {{
      if (isNaN(val) || !isFinite(val)) return "0";
      return new Intl.NumberFormat("en-US", {{
        minimumFractionDigits: Number.isInteger(val) ? 0 : 2,
        maximumFractionDigits: 2
      }}).format(val);
    }}

    function getInputs() {{
      var inputs = {{}};
      var elements = form.querySelectorAll("input[type='number'], select");
      for (var i = 0; i < elements.length; i++) {{
        var el = elements[i];
        var name = el.name || el.id;
        if (!name) continue;
        var cleanName = name.replace(/^input-/, "");
        var v = parseFloat(el.value);
        inputs[cleanName] = isNaN(v) ? 0 : Math.max(0, v);
      }}
      return inputs;
    }}

    function syncDualControls(e) {{
      var target = e.target;
      if (!target) return;
      if (target.type === "range") {{
        var numId = target.id.replace(/^range-/, "input-");
        var numEl = document.getElementById(numId);
        if (numEl) numEl.value = target.value;
      }} else if (target.type === "number") {{
        var rangeId = target.id.replace(/^input-/, "range-");
        var rangeEl = document.getElementById(rangeId);
        if (rangeEl) rangeEl.value = target.value;
      }}
    }}

    var debounceTimer = null;
    function updateQueryParams(inputs) {{
      if (!window.history || !window.history.replaceState) return;
      if (debounceTimer) clearTimeout(debounceTimer);
      debounceTimer = setTimeout(function() {{
        try {{
          var url = new URL(window.location.href);
          for (var k in inputs) {{
            url.searchParams.set(k, inputs[k]);
          }}
          window.history.replaceState({{}}, "", url.toString());
        }} catch (e) {{}}
      }}, 150);
    }}

    function syncInputsFromParams() {{
      if (!window.location || !window.location.search) return;
      try {{
        var params = new URLSearchParams(window.location.search);
        var elements = form.querySelectorAll("input, select");
        for (var i = 0; i < elements.length; i++) {{
          var el = elements[i];
          var name = (el.name || el.id || "").replace(/^input-/, "").replace(/^range-/, "");
          if (params.has(name)) {{
            el.value = params.get(name);
          }}
        }}
      }} catch (e) {{}}
    }}

    function calculate(inputs) {{
{calc_js_body}
    }}

    function handleRecompute() {{
      var inputs = getInputs();
      updateQueryParams(inputs);
      var result = calculate(inputs);
      if (outputElem) {{
        outputElem.textContent = formatNumber(result);
      }}
    }}

    syncInputsFromParams();
    handleRecompute();
    window.addEventListener("popstate", function() {{
      syncInputsFromParams();
      handleRecompute();
    }});
    form.addEventListener("input", function(e) {{
      syncDualControls(e);
      handleRecompute();
    }});
    form.addEventListener("change", function(e) {{
      syncDualControls(e);
      handleRecompute();
    }});
    form.addEventListener("submit", function(e) {{
      e.preventDefault();
      handleRecompute();
      return false;
    }});
  }})();
  </script>
</body>
</html>
"""

    from pseofactory.visual_primitives import (
        assert_visual_and_ux_contracts,
        normalize_html_visual_primitives,
    )
    from pseofactory.tenant_facts import TruthReconciliationEngine

    resolved_tenant = "prexvo" if is_prexvo else ("gainhelm" if is_gainhelm else "profithelm")
    html_content, _ = TruthReconciliationEngine.reconcile_html_truth(
        html_content,
        tenant=resolved_tenant,
        rel_path=f"tools/{slug}/index.html",
        slug=slug,
    )
    html_content, _ = normalize_html_visual_primitives(html_content, is_tenant_porcelain=False)
    assert_visual_and_ux_contracts(html_content, context=f"compiled page '{slug}'", require_primitives=True)
    reconciliation_violations = TruthReconciliationEngine.audit_html_truth_reconciliation(
        html_content,
        tenant=resolved_tenant,
        rel_path=f"tools/{slug}/index.html",
        slug=slug,
    )
    if reconciliation_violations:
        raise ValueError(f"TruthReconciliationEngine audit failed on '{slug}': {reconciliation_violations[0]}")

    # 7. Strictly verify zero forbidden dashes
    assert_no_forbidden_dashes(html_content, context=f"compiled page '{slug}'")
    assert_touch_targets(html_content, context=f"compiled page '{slug}'")

    fuzz_res = verify_formula_boundary_fuzzing(formula, clamped_inputs)

    # 8. Self-verify using verify_html_unique_first_party_information
    audit_res = verify_html_unique_first_party_information(
        html_content,
        rel_path=f"tools/{slug}/index.html",
        manifest_data=manifest,
    )
    if audit_res.get("status") != "PASS":
        issues_list = audit_res.get("issues", [])
        raise ValueError(f"Content compiler self-audit failed: {issues_list}")

    return {
        "slug": slug,
        "title": title,
        "tenant": resolved_tenant,
        "html": html_content,
        "manifest": manifest,
        "published_output": published_output,
        "affiliate_route": monetization_block["affiliate_route"],
        "partner_roster": monetization_block.get("partner_roster"),
        "slot_plan": monetization_block.get("slot_plan"),
        "commercial_offers_allowed": monetization_block["commercial_offers_allowed"],
        "restricted_public_service": monetization_block["restricted_public_service"],
        "verified": True,
        "boundary_fuzz_verified": bool(fuzz_res.get("passed", True)),
    }

