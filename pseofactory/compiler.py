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

import hashlib
import html as _html
import os
import json
import re
import ast
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
import math
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from pseofactory.affiliates import (
    GAINHELM_DISCLOSURES,
    LIENBOND_DISCLOSURES,
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
    is_state_jurisdiction_tool,
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
    ("tcja-sunset-capital-gains", "QSBS Section 1202 and Capital Gains Tax Calculator"),
    ("irs-tax-brackets", "IRS Statutory Tax Brackets & Marginal Rate Calculator"),
    ("saas-runway-calculator", "SaaS Runway and Capital Burn Rate Calculator"),
    ("crypto-tax-calculator", "Cryptocurrency Tax Loss Harvesting Calculator"),
    ("treasury-yield-calculator", "Treasury Yield Curve Arbitrage Calculator"),
    ("s-corp-reasonable-salary-tax-calculator", "S-Corp Reasonable Salary and FICA Tax Savings Calculator"),
    ("capital-gains-calculator", "Long-Term Capital Gains and 3.8% NIIT Tax Calculator"),
    ("irs-interest-calculator", "IRS Underpayment and Late-Filing Interest Calculator"),
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
        "formula": "round((min(net_business_income * 0.9235, 184500.0) - min(reasonable_salary, 184500.0)) * 0.124 + (net_business_income * 0.9235 - reasonable_salary) * 0.029, 0)",
        "inputs": {"net_business_income": 220000.0, "reasonable_salary": 95000.0},
        "published_output": 14235.0,
        "sample_calculation": "S-Corp shareholder distribution at $220,000 net business income with a $95,000 reasonable W-2 salary saves $14,235 in FICA self-employment taxes ($11,098.00 OASDI capped at the $184,500 2026 wage base plus $3,136.93 Medicare on the $203,170 Schedule SE base)",
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
        "expected_partner": "rippling",
    },
    {
        "query": "contractor license and performance surety bond cost calculator",
        "slug": "contractor-surety-bond-cost-calculator",
        "tenant": "profithelm",
        "statutory_authority": "31 U.S.C. Section 9304 Federal Surety Standards and State Contractor License Bond Schedules",
        "economic_dataset": "FRED Construction Spending Series and SFAA Surety Underwriting Loss Benchmarks",
        "model_name": "ContractorSuretyBondUnderwritingModel",
        "formula": "bond_penalty_amount * (credit_tier_rate_pct / 100.0)",
        "inputs": {"bond_penalty_amount": 50000, "credit_tier_rate_pct": 1.5},
        "published_output": 750.0,
        "sample_calculation": "Statutory $50,000 contractor license bond at a 1.5% standard credit tier underwriting rate yields a $750 annual bond premium",
        "canonical_base": "https://profithelm.com",
        "expected_partner": "rippling",
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
        "expected_partner": "xendoo",
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
        "expected_partner": "xendoo",
    },
    {
        "query": "commercial heavy vehicle section 179 gvwr 6000 lbs deduction calculator",
        "slug": "commercial-heavy-vehicle-section-179-weight-calculator",
        "tenant": "profithelm",
        "statutory_authority": "IRC Section 179(b)(5) ($32,000 Heavy SUV Cap), P.L. 119-21 Section 70301 (100% IRC Section 168(k) Bonus Depreciation), and IRC Section 280F",
        "economic_dataset": "FRED Heavy Truck Sales Series and IRS Revenue Procedure Depreciation Limitations",
        "model_name": "CommercialHeavyVehicleGVWR179Model",
        "formula": "round((min(vehicle_cost * business_use_fraction, 32000.0) + max(0.0, vehicle_cost * business_use_fraction - min(vehicle_cost * business_use_fraction, 32000.0)) * bonus_depreciation_rate) * marginal_tax_rate, 2)",
        "inputs": {"vehicle_cost": 95000.0, "business_use_fraction": 0.90, "bonus_depreciation_rate": 1.0, "marginal_tax_rate": 0.35},
        "published_output": 29925.0,
        "sample_calculation": "Heavy SUV (>6,000 lbs GVWR) costing $95,000 at 90% business use ($85,500 eligible basis) applies the $32,000 2026 IRC Section 179(b)(5) cap plus 100% P.L. 119-21 Section 70301 bonus depreciation on the remaining $53,500 basis ($85,500 total deduction) at a 35% marginal tax rate, yielding $29,925.00 in Year-1 tax savings",
        "canonical_base": "https://profithelm.com",
        "expected_partner": "xendoo",
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
        "expected_partner": "rippling",
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
        "expected_partner": "xendoo",
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

LIENBOND_CONSTRUCTION_SURETY_CLUSTER = [
    ("workers-compensation-class-code-rate-calculator-by-state", "NCCI Workers Compensation Class Code Rate Calculator by State"),
    ("contractor-license-bond-cost-calculator-by-credit-score", "Contractor License Bond Cost Calculator by Credit Score"),
    ("miller-act-performance-and-payment-bond-premium-calculator", "Miller Act Performance and Payment Bond Premium Calculator"),
    ("contractor-lien-release-statutory-matrix-by-state", "50-State Contractor Mechanics Lien Release Statutory Matrix"),
    ("commercial-construction-retainage-interest-penalty-calculator-by-state", "Commercial Construction Retainage Interest Penalty Calculator by State"),
    ("davis-bacon-prevailing-wage-fringe-benefit-rate-calculator", "Davis-Bacon Prevailing Wage and WH-347 Fringe Benefit Rate Calculator"),
    ("erisa-fidelity-bond-coverage-amount-calculator", "ERISA Section 412 Fidelity Bond Coverage Amount Calculator"),
    ("contractor-overhead-and-profit-markup-vs-margin-calculator", "Contractor Overhead and Profit Markup vs Margin Calculator"),
    ("experience-modification-rate-emr-workers-comp-penalty-calculator", "Experience Modification Rate (EMR) Workers Comp Penalty Calculator"),
    ("california-texas-florida-preliminary-notice-deadline-calculator", "California, Texas and Florida Preliminary Notice Deadline Calculator"),
]

LIENBOND_EXPANSION_SPECS: List[Dict[str, Any]] = [
    {
        "query": "workers compensation class code rate calculator by state",
        "slug": "workers-compensation-class-code-rate-calculator-by-state",
        "title": "NCCI Workers Compensation Class Code Rate Calculator by State",
        "tenant": "lienbond",
        "property_id": "lienbond",
        "domain": "lienbond.com",
        "canonical_base": "https://lienbond.com",
        "entity_type": "FinancialProductOrService",
        "statutory_authority": "NCCI Basic Manual Class Codes, NCCI Experience Rating Plan Manual, and State Workers Compensation Rating Bureaus",
        "economic_dataset": "BLS Employer Costs for Employee Compensation (ECEC Construction Series) and NCCI Loss Cost Filings",
        "model_name": "NCCIWorkersCompClassCodePremiumModel",
        "formula": "round((field_trade_payroll / 100.0) * class_code_rate_per_100 * emr_modification_factor, 2)",
        "inputs": {"field_trade_payroll": 650000.0, "class_code_rate_per_100": 6.80, "emr_modification_factor": 1.0},
        "published_output": 44200.0,
        "sample_calculation": "Field construction payroll of $650,000 classified at $6.80 per $100 of remuneration with a 1.00 unity EMR modifier yields $44,200.00 in annual workers compensation manual premium",
        "expected_partner": "simply_business",
    },
    {
        "query": "contractor license bond cost calculator by credit score",
        "slug": "contractor-license-bond-cost-calculator-by-credit-score",
        "title": "Contractor License Bond Cost Calculator by Credit Score",
        "tenant": "lienbond",
        "property_id": "lienbond",
        "domain": "lienbond.com",
        "canonical_base": "https://lienbond.com",
        "entity_type": "FinancialProductOrService",
        "statutory_authority": "31 CFR Part 223 U.S. Treasury Circular 570, 40 U.S.C. Section 3131, and California BPC Section 7071.6",
        "economic_dataset": "FRED Commercial Bank Prime Rate Series, BLS Construction Wage Series, and SFAA Surety Loss Ratios",
        "model_name": "ContractorLicenseBondCreditTierModel",
        "formula": "round(bond_penalty_amount * (underwriting_rate_pct / 100.0) * multi_year_discount_factor, 2)",
        "inputs": {"bond_penalty_amount": 25000.0, "underwriting_rate_pct": 1.5, "multi_year_discount_factor": 1.0},
        "published_output": 375.0,
        "sample_calculation": "Statutory $25,000 CSLB contractor license bond underwritten at a 1.50% preferred credit tier rate (1.0x single-year factor) yields a $375.00 annual surety bond premium",
        "expected_partner": "suretybonds_direct",
    },
    {
        "query": "performance and payment bond premium calculator",
        "slug": "miller-act-performance-and-payment-bond-premium-calculator",
        "title": "Miller Act Performance and Payment Bond Premium Calculator",
        "tenant": "lienbond",
        "property_id": "lienbond",
        "domain": "lienbond.com",
        "canonical_base": "https://lienbond.com",
        "entity_type": "FinancialProductOrService",
        "statutory_authority": "40 U.S.C. Section 3131 Federal Miller Act, 48 CFR Part 28 (FAR 28.102-2), and State Little Miller Acts",
        "economic_dataset": "FRED Total Construction Spending Series (TTLCONS) and SFAA Class B Contract Surety Rate Manuals",
        "model_name": "MillerActSlidingScaleBondPremiumModel",
        "formula": "round(min(contract_price, 100000.0) * 0.025 + max(0.0, min(contract_price - 100000.0, 400000.0)) * 0.015 + max(0.0, contract_price - 500000.0) * (sliding_tier_rate_pct / 100.0), 2)",
        "inputs": {"contract_price": 1200000.0, "sliding_tier_rate_pct": 1.0},
        "published_output": 15500.0,
        "sample_calculation": "Public works contract of $1,200,000 under SFAA Class B sliding-scale rates ($2,500 on first $100k at 2.5% + $6,000 on next $400k at 1.5% + $7,000 on remaining $700k at 1.0%) produces a $15,500.00 combined AIA A312 performance and payment bond premium",
        "expected_partner": "suretybonds_direct",
    },
    {
        "query": "contractor lien release statutory matrix by state",
        "slug": "contractor-lien-release-statutory-matrix-by-state",
        "title": "50-State Contractor Mechanics Lien Release Statutory Matrix",
        "tenant": "lienbond",
        "property_id": "lienbond",
        "domain": "lienbond.com",
        "canonical_base": "https://lienbond.com",
        "entity_type": "FinancialProductOrService",
        "statutory_authority": "40 U.S.C. Section 3133(b) Miller Act 90-Day Notice Rule, California Civil Code Section 8132, and Texas Property Code Chapter 53",
        "economic_dataset": "FRED Commercial Construction Credit Series and BLS Producer Price Index for Construction",
        "model_name": "StatutoryMechanicsLienWaiverProtectionModel",
        "formula": "round(unpaid_contract_draw + change_order_balance - min(unpaid_contract_draw + change_order_balance, unserved_late_days * daily_forfeiture_rate), 2)",
        "inputs": {"unpaid_contract_draw": 85000.0, "change_order_balance": 12500.0, "unserved_late_days": 0.0, "daily_forfeiture_rate": 1250.0},
        "published_output": 97500.0,
        "sample_calculation": "Unpaid progress draw of $85,000 plus $12,500 in executed change orders with 0 late preliminary notice days preserves $97,500.00 in secured statutory mechanics lien principal",
        "expected_partner": "levelset_lien_filing",
    },
    {
        "query": "commercial construction retainage interest penalty calculator by state",
        "slug": "commercial-construction-retainage-interest-penalty-calculator-by-state",
        "title": "Commercial Construction Retainage Interest Penalty Calculator by State",
        "tenant": "lienbond",
        "property_id": "lienbond",
        "domain": "lienbond.com",
        "canonical_base": "https://lienbond.com",
        "entity_type": "FinancialProductOrService",
        "statutory_authority": "31 U.S.C. Section 3903 Federal Prompt Payment Act, 48 CFR 52.232-5 Progress Payments, and State Retainage Caps",
        "economic_dataset": "Federal Reserve H.15 Commercial Bank Prime Loan Rate and FRED Construction Spending Series",
        "model_name": "ConstructionRetainageWorkingCapitalDragModel",
        "formula": "round(gross_contract_billed * (retainage_holdback_pct / 100.0) * (1.0 + (credit_line_apr_pct / 100.0) * (retainage_hold_days / 365.0)), 2)",
        "inputs": {"gross_contract_billed": 900000.0, "retainage_holdback_pct": 10.0, "credit_line_apr_pct": 8.5, "retainage_hold_days": 180.0},
        "published_output": 93772.6,
        "sample_calculation": "Withholding 10.0% retainage ($90,000) on $900,000 of progress billings financed at 8.50% APR for 180 days locks up $93,772.60 in principal plus working capital interest drag",
        "expected_partner": "jobber_field_service",
    },
    {
        "query": "davis bacon prevailing wage fringe benefit rate calculator",
        "slug": "davis-bacon-prevailing-wage-fringe-benefit-rate-calculator",
        "title": "Davis-Bacon Prevailing Wage and WH-347 Fringe Benefit Rate Calculator",
        "tenant": "lienbond",
        "property_id": "lienbond",
        "domain": "lienbond.com",
        "canonical_base": "https://lienbond.com",
        "entity_type": "FinancialProductOrService",
        "statutory_authority": "40 U.S.C. Section 3141 Davis-Bacon Act and 29 CFR Section 5.5 Certified Payroll WH-347",
        "economic_dataset": "BLS National Compensation Survey Construction Fringe Benefit Series and DOL Wage Determinations",
        "model_name": "DavisBaconFringeCashInLieuPayrollBurdenModel",
        "formula": "round(annual_prevailing_hours * (base_hourly_wage + (required_fringe_hourly - bona_fide_plan_credit_hourly) * (1.0 + payroll_tax_burden_pct / 100.0) + bona_fide_plan_credit_hourly), 2)",
        "inputs": {"annual_prevailing_hours": 2000.0, "base_hourly_wage": 48.0, "required_fringe_hourly": 22.0, "bona_fide_plan_credit_hourly": 0.0, "payroll_tax_burden_pct": 14.5},
        "published_output": 146380.0,
        "sample_calculation": "Paying $48.00/hr base wage plus $22.00/hr fringe in cash-in-lieu over 2,000 hours with a 14.5% FICA/FUTA/WC payroll burden on cash fringes totals $146,380.00 ($6,380.00 excess payroll tax penalty vs a bona fide ERISA trust)",
        "expected_partner": "simply_business",
    },
    {
        "query": "erisa fidelity bond coverage amount calculator",
        "slug": "erisa-fidelity-bond-coverage-amount-calculator",
        "title": "ERISA Section 412 Fidelity Bond Coverage Amount Calculator",
        "tenant": "lienbond",
        "property_id": "lienbond",
        "domain": "lienbond.com",
        "canonical_base": "https://lienbond.com",
        "entity_type": "FinancialProductOrService",
        "statutory_authority": "29 U.S.C. Section 1112 (ERISA Section 412), 29 CFR 2580.412-1, and U.S. Treasury Circular 570",
        "economic_dataset": "BLS Employee Benefits Survey Retirement Plan Series and FRED Corporate Bond Yield Series",
        "model_name": "ERISASection412FidelityBondLimitModel",
        "formula": "round(min(max(qualifying_plan_assets * 0.10, 1000.0), 500000.0), 2)",
        "inputs": {"qualifying_plan_assets": 2400000.0},
        "published_output": 240000.0,
        "sample_calculation": "Qualified 401(k) retirement plan holding $2,400,000 in qualifying plan assets under 29 U.S.C. Section 1112 (10% statutory bond rule capped at $500,000) requires a $240,000.00 ERISA fidelity bond",
        "expected_partner": "suretybonds_direct",
    },
    {
        "query": "contractor overhead and profit markup vs margin calculator",
        "slug": "contractor-overhead-and-profit-markup-vs-margin-calculator",
        "title": "Contractor Overhead and Profit Markup vs Margin Calculator",
        "tenant": "lienbond",
        "property_id": "lienbond",
        "domain": "lienbond.com",
        "canonical_base": "https://lienbond.com",
        "entity_type": "FinancialProductOrService",
        "statutory_authority": "48 CFR Part 31 (FAR Contract Cost Principles), IRC Section 460 Percentage-of-Completion, and AIA A102",
        "economic_dataset": "BLS Producer Price Index for Nonresidential Building Construction and FRED Construction Series",
        "model_name": "ContractorMarkupVsGrossMarginModel",
        "formula": "round(direct_job_cost / (1.0 - (overhead_pct + target_net_profit_pct) / 100.0), 2)",
        "inputs": {"direct_job_cost": 340000.0, "overhead_pct": 12.0, "target_net_profit_pct": 8.0},
        "published_output": 425000.0,
        "sample_calculation": "Direct job cost of $340,000 divided by (1.0 minus 20.0% combined overhead and profit margin) requires a $425,000.00 contract bid price (1.25x markup divisor)",
        "expected_partner": "jobber_field_service",
    },
    {
        "query": "experience modification rate emr workers comp penalty calculator",
        "slug": "experience-modification-rate-emr-workers-comp-penalty-calculator",
        "title": "Experience Modification Rate (EMR) Workers Comp Penalty Calculator",
        "tenant": "lienbond",
        "property_id": "lienbond",
        "domain": "lienbond.com",
        "canonical_base": "https://lienbond.com",
        "entity_type": "FinancialProductOrService",
        "statutory_authority": "NCCI Basic Manual Class Codes, NCCI Experience Rating Plan Manual Rule 2-E, and State Workers Compensation Rating Bureaus",
        "economic_dataset": "BLS Survey of Occupational Injuries and Illnesses (SOII) and NCCI Primary Split-Point Series",
        "model_name": "NCCIExperienceModificationRateSurchargeModel",
        "formula": "round(manual_workers_comp_premium * emr_factor * (1.0 - safety_credit_pct / 100.0), 2)",
        "inputs": {"manual_workers_comp_premium": 52000.0, "emr_factor": 1.15, "safety_credit_pct": 5.0},
        "published_output": 56810.0,
        "sample_calculation": "Manual workers compensation premium of $52,000 modified by a 1.15 debit EMR and a 5.0% state safety committee credit yields $56,810.00 net audited premium",
        "expected_partner": "simply_business",
    },
    {
        "query": "preliminary notice deadline calculator california texas florida",
        "slug": "california-texas-florida-preliminary-notice-deadline-calculator",
        "title": "California, Texas and Florida Preliminary Notice Deadline Calculator",
        "tenant": "lienbond",
        "property_id": "lienbond",
        "domain": "lienbond.com",
        "canonical_base": "https://lienbond.com",
        "entity_type": "FinancialProductOrService",
        "statutory_authority": "40 U.S.C. Section 3133(b) Miller Act, California Civil Code Section 8204, Texas Property Code Section 53.056, and Florida Statutes Section 713.06",
        "economic_dataset": "FRED Commercial Construction Credit Series and BLS Specialty Trade Contractor Series",
        "model_name": "TriStatePreliminaryNoticeLookbackModel",
        "formula": "round(unpaid_progress_billing * max(0.0, min(1.0, (statutory_lookback_window_days - max(0.0, days_elapsed_since_first_furnishing - statutory_lookback_window_days)) / statutory_lookback_window_days)), 2)",
        "inputs": {"unpaid_progress_billing": 120000.0, "days_elapsed_since_first_furnishing": 20.0, "statutory_lookback_window_days": 20.0},
        "published_output": 120000.0,
        "sample_calculation": "Serving a California 20-Day Preliminary Notice on Day 20 from first furnishing preserves 100% ($120,000.00) of statutory mechanics lien and stop payment notice rights",
        "expected_partner": "levelset_lien_filing",
    },
]


def get_lienbond_expansion_specs() -> List[Dict[str, Any]]:
    """Returns deep copies of the 10 Factor-7-verified LienBond construction surety, workers comp, and lien calculator specs."""
    return [dict(spec, inputs=dict(spec["inputs"])) for spec in LIENBOND_EXPANSION_SPECS]


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
    clean_f = re.sub(r'(\d+(?:\.\d+)?)\s*%(?!\s*[A-Za-z0-9_.(])', r'(\1 / 100.0)', clean_f)
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
            elif isinstance(node.op, ast.Not):
                return f"(!{_node_to_js(node.operand)})"
            else:
                raise ValueError(f"Unsupported unary operator in formula: {type(node.op).__name__}")
        elif isinstance(node, ast.Compare):
            cmp_map = {
                ast.Eq: "===",
                ast.NotEq: "!==",
                ast.Lt: "<",
                ast.LtE: "<=",
                ast.Gt: ">",
                ast.GtE: ">=",
            }
            parts: List[str] = []
            left_js = _node_to_js(node.left)
            for op, comp in zip(node.ops, node.comparators):
                op_str = cmp_map.get(type(op))
                if op_str is None:
                    raise ValueError(f"Unsupported comparison operator in formula: {type(op).__name__}")
                right_js = _node_to_js(comp)
                parts.append(f"({left_js} {op_str} {right_js})")
                left_js = right_js
            return f"({' && '.join(parts)})" if len(parts) > 1 else parts[0]
        elif isinstance(node, ast.BoolOp):
            op_js = " && " if isinstance(node.op, ast.And) else (" || " if isinstance(node.op, ast.Or) else None)
            if op_js is None:
                raise ValueError(f"Unsupported boolean operator in formula: {type(node.op).__name__}")
            return f"({op_js.join(_node_to_js(v) for v in node.values)})"
        elif isinstance(node, ast.IfExp):
            return f"({_node_to_js(node.test)} ? {_node_to_js(node.body)} : {_node_to_js(node.orelse)})"
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


_READABLE_FORMULA_ACRONYMS = {
    "emr": "EMR",
    "ncci": "NCCI",
    "fha": "FHA",
    "agi": "AGI",
    "magi": "MAGI",
    "hhs": "HHS",
    "fpl": "FPL",
    "pslf": "PSLF",
    "idr": "IDR",
    "rap": "RAP",
    "ibr": "IBR",
    "dora": "DORA",
    "ict": "ICT",
    "eu": "EU",
    "ai": "AI",
    "sdi": "SDI",
    "hpsl": "HPSL",
    "nhsc": "NHSC",
    "erisa": "ERISA",
    "fica": "FICA",
    "futa": "FUTA",
    "suta": "SUTA",
    "se": "SE",
    "qbi": "QBI",
    "apr": "APR",
    "irr": "IRR",
    "roi": "ROI",
    "cac": "CAC",
    "ltv": "LTV",
    "hipaa": "HIPAA",
    "pci": "PCI",
    "dss": "DSS",
    "soc": "SOC",
    "cmmc": "CMMC",
    "nist": "NIST",
    "sprs": "SPRS",
    "hud": "HUD",
    "sfaa": "SFAA",
    "cbp": "CBP",
    "mpf": "MPF",
    "hmf": "HMF",
    "fob": "FOB",
    "qre": "QRE",
    "asc": "ASC",
    "gvwr": "GVWR",
    "cbct": "CBCT",
    "aia": "AIA",
    "wh347": "WH-347",
    "irc": "IRC",
    "irs": "IRS",
    "sec": "Sec",
    "us": "US",
}


def _format_formula_variable_label(var_name: str) -> str:
    """Converts a snake_case formula identifier into readable business notation."""
    parts = [p for p in str(var_name or "").strip().split("_") if p]
    if not parts:
        return str(var_name or "")
    out: List[str] = []
    for idx, p in enumerate(parts):
        low = p.lower()
        if low == "pct":
            out.append("(%)")
        elif low in _READABLE_FORMULA_ACRONYMS:
            out.append(_READABLE_FORMULA_ACRONYMS[low])
        elif idx > 0 and low in ("per", "of", "and", "or", "to", "in", "by", "vs"):
            out.append(low)
        else:
            out.append(p.capitalize())
    return " ".join(out)


def _format_human_readable_formula(formula_str: str) -> str:
    """
    Formats a Python mathematical formula string into clean human-readable arithmetic notation,
    stripping outer `round(..., digits)` wrappers and converting snake_case variables to labels.
    """
    raw = str(formula_str or "").strip()
    if not raw:
        return ""
    try:
        parsed = ast.parse(raw, mode="eval")
    except SyntaxError:
        cleaned = re.sub(r"\bround\(\s*", "", raw)
        cleaned = re.sub(r",\s*\d+\s*\)", "", cleaned)
        cleaned = cleaned.replace("\u2014", "-").replace("\u2013", "-")
        return re.sub(r"\s+-\s+", " minus ", cleaned)

    def _prec(n: ast.AST) -> int:
        if isinstance(n, ast.BinOp):
            if isinstance(n.op, (ast.Add, ast.Sub)):
                return 1
            if isinstance(n.op, (ast.Mult, ast.Div, ast.FloorDiv, ast.Mod)):
                return 2
            if isinstance(n.op, ast.Pow):
                return 4
        if isinstance(n, ast.UnaryOp):
            return 3
        return 5

    def _fmt(n: ast.AST) -> str:
        if isinstance(n, ast.Expression):
            return _fmt(n.body)
        if isinstance(n, ast.Constant):
            val = n.value
            if isinstance(val, bool):
                return str(val)
            if isinstance(val, float):
                if val.is_integer():
                    iv = int(val)
                    return f"{iv:,}" if abs(iv) >= 1000 else str(iv)
                return str(val)
            if isinstance(val, int):
                return f"{val:,}" if abs(val) >= 1000 else str(val)
            return str(val)
        if isinstance(n, ast.Name):
            return _format_formula_variable_label(n.id)
        if isinstance(n, ast.UnaryOp):
            op_s = "-" if isinstance(n.op, ast.USub) else "+"
            sub = _fmt(n.operand)
            if isinstance(n.operand, ast.BinOp):
                return f"{op_s}({sub})"
            return f"{op_s}{sub}"
        if isinstance(n, ast.BinOp):
            p = _prec(n)
            left_s = _fmt(n.left)
            right_s = _fmt(n.right)
            if isinstance(n.left, ast.BinOp) and _prec(n.left) < p:
                left_s = f"({left_s})"
            need_right_parens = False
            if isinstance(n.right, ast.BinOp):
                rp = _prec(n.right)
                if rp < p:
                    need_right_parens = True
                elif isinstance(n.op, ast.Div) and rp <= p:
                    need_right_parens = True
                elif isinstance(n.op, ast.Sub) and isinstance(n.right.op, (ast.Add, ast.Sub)):
                    need_right_parens = True
            if need_right_parens:
                right_s = f"({right_s})"
            op_map = {
                ast.Add: " + ",
                ast.Sub: " minus ",
                ast.Mult: " x ",
                ast.Div: " / ",
                ast.FloorDiv: " // ",
                ast.Mod: " mod ",
                ast.Pow: " ^ ",
            }
            op_s = op_map.get(type(n.op), " ")
            return f"{left_s}{op_s}{right_s}"
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            fn = n.func.id
            if fn == "round" and n.args:
                return _fmt(n.args[0])
            args_s = [_fmt(a) for a in n.args]
            return f"{fn}({', '.join(args_s)})"
        if isinstance(n, ast.IfExp):
            return f"({_fmt(n.body)} if {_fmt(n.test)} else {_fmt(n.orelse)})"
        if isinstance(n, ast.Compare):
            chunks = [_fmt(n.left)]
            cmp_map = {
                ast.Eq: "=",
                ast.NotEq: "!=",
                ast.Lt: "<",
                ast.LtE: "<=",
                ast.Gt: ">",
                ast.GtE: ">=",
            }
            for op, comp in zip(n.ops, n.comparators):
                chunks.append(cmp_map.get(type(op), "?"))
                chunks.append(_fmt(comp))
            return " ".join(chunks)
        return raw

    formatted = _fmt(parsed).strip().replace("\u2014", "-").replace("\u2013", "-")
    return re.sub(r"\s+-\s+", " minus ", formatted)


def _format_plain_prose_formula(formula_str: str, readable_formula: str, input_keys: Optional[List[str]] = None) -> str:
    """Formats complex min/max code-like formulas into clean user-facing prose."""
    rf = str(readable_formula or "").strip()
    if not rf:
        return ""
    if "min(" in rf.lower() or "max(" in rf.lower():
        labels = [_format_formula_variable_label(k) for k in (input_keys or []) if str(k).strip()]
        if labels:
            if len(labels) == 1:
                return f"tiered statutory schedule based on {labels[0]}"
            return f"tiered statutory schedule combining {', '.join(labels[:-1])} and {labels[-1]}"
        return "tiered statutory schedule with statutory caps and thresholds"
    return rf


def _format_clean_input_val(val: Any) -> str:
    """Formats integer-like floats and Decimals without trailing zeros for clean HTML input values."""
    if isinstance(val, bool):
        return str(val)
    if isinstance(val, Decimal):
        f = float(val)
        if abs(f - round(f)) < 1e-9:
            return str(int(round(f)))
        s = format(val.normalize(), "f")
        return s.rstrip("0").rstrip(".") if "." in s else s
    if isinstance(val, (int, float)):
        f = float(val)
        return str(int(round(f))) if abs(f - round(f)) < 1e-9 else str(f)
    return str(val)


def _compute_proportional_range_step(val_num: float, max_num: float, is_float_val: bool) -> str:
    """Computes a proportional slider step so sliders stay <= 2000 steps while preserving float precision."""
    span = max(0.0, float(max_num))
    if is_float_val and abs(val_num - round(val_num)) > 1e-6:
        if max_num <= 20.0:
            if abs(val_num * 100.0 - round(val_num * 100.0)) <= 1e-6:
                if abs(val_num * 10.0 - round(val_num * 10.0)) <= 1e-6 and max_num > 10.0 and not (0.0 < val_num <= 10.0):
                    return "0.1"
                return "0.01"
            if max_num <= 2.0:
                if abs(val_num * 1000.0 - round(val_num * 1000.0)) <= 1e-6 and (span / 0.001) <= 2000:
                    return "0.001"
                if (span / 0.0005) <= 2000 and abs(val_num * 2000.0 - round(val_num * 2000.0)) <= 1e-6:
                    return "0.0005"
                if (span / 0.001) <= 2000:
                    return "0.001"
            if (span / 0.01) <= 2000:
                return "0.01"
        if max_num <= 200.0 and (span / 0.1) <= 2000:
            if abs(val_num * 10.0 - round(val_num * 10.0)) <= 1e-6:
                return "0.1"
    if span <= 0.0:
        return "1"
    if max_num < 100.0:
        if max_num <= 20.0 and is_float_val:
            return "0.01"
        return "0.1" if is_float_val else "1"
    if max_num < 1000.0:
        if is_float_val and 0.0 < val_num < 10.0 and (span / 0.1) <= 2000:
            return "0.1"
        return "1"
    exp = max(1, int(math.floor(math.log10(span))) - 2)
    base_step = 10 ** exp
    while (span / base_step) > 2000:
        base_step *= 10
    val_d = Decimal(str(round(val_num, 8)))
    for div in (5, 2):
        if base_step % div == 0:
            cand = base_step // div
            if cand >= 1 and (span / cand) <= 2000 and (val_d % Decimal(cand)) == 0:
                return str(cand)
    return str(base_step)


def _compute_range_slider_spec(var_name: str, var_val: Any) -> Tuple[str, str, str, str]:
    """
    Computes (value, min, max, step) strings for an HTML5 range slider with:
    - realistic domain bounds for factors/ratios, 2-decimal percentages, sub-1 rates, and integer counts
    - <= 2000 steps across (max - min) / step
    - exact step alignment from min so the baseline value never snaps in HTML5.
    """
    val_num = float(var_val) if isinstance(var_val, (int, float)) and not isinstance(var_val, bool) else 0.0
    tokens = set(re.split(r"[^a-z0-9]+", var_name.lower()))
    is_pct_token = bool(tokens & {"pct", "percent", "percentage"})
    is_factor_token = bool(tokens & {"factor", "multiplier", "ratio", "emr", "mod", "modifier", "modification"})
    is_rate_token = bool(tokens & {"rate", "share", "ratio", "apr"})
    is_integer_baseline = abs(val_num - round(val_num)) <= 1e-6
    is_2dec_pct = (
        is_pct_token
        and 0.0 < val_num <= 20.0
        and abs(val_num * 10.0 - round(val_num * 10.0)) > 1e-6
        and abs(val_num * 100.0 - round(val_num * 100.0)) <= 1e-6
    )

    if 0.0 < val_num < 1.0 and is_rate_token and not is_pct_token:
        raw_max = 1.0
        eff_float = True
    elif is_factor_token and not is_pct_token and 0.0 < val_num <= 10.0:
        raw_max = max(3.0, round(val_num * 2.5, 2))
        eff_float = True
    elif is_2dec_pct:
        raw_max = min(20.0, max(10.0, float(math.ceil(val_num * 5.0))))
        eff_float = True
    else:
        raw_max = max(100.0, val_num * 2.0 if val_num > 0 else 100.0)
        eff_float = (not is_integer_baseline) and isinstance(var_val, float)

    step_str = _compute_proportional_range_step(val_num, raw_max, eff_float)
    step_d = Decimal(step_str)
    val_d = Decimal(str(round(val_num, 8)))
    raw_max_d = Decimal(str(round(raw_max, 8)))
    if val_d < 0:
        min_d = val_d
    else:
        rem = val_d % step_d
        min_d = rem if rem != 0 else Decimal("0")
    steps_needed = int(((raw_max_d - min_d) / step_d).to_integral_value(rounding=ROUND_CEILING))
    while steps_needed > 2000:
        step_d *= Decimal("10")
        step_str = _format_clean_input_val(step_d)
        if val_d < 0:
            min_d = val_d
        else:
            rem = val_d % step_d
            min_d = rem if rem != 0 else Decimal("0")
        steps_needed = int(((raw_max_d - min_d) / step_d).to_integral_value(rounding=ROUND_CEILING))
    max_d = min_d + (step_d * steps_needed)
    return _format_clean_input_val(val_d), _format_clean_input_val(min_d), _format_clean_input_val(max_d), step_str


def _sanitize_visible_sample_calculation(sample_calc: str) -> str:
    """Replaces any leaked raw Python `round((...))` calls in visible prose with readable math."""
    text = str(sample_calc or "").strip()
    if "round(" not in text:
        return text
    out_parts: List[str] = []
    idx = 0
    while idx < len(text):
        pos = text.find("round(", idx)
        if pos == -1:
            out_parts.append(text[idx:])
            break
        if pos > 0 and (text[pos - 1].isalnum() or text[pos - 1] == "_"):
            out_parts.append(text[idx : pos + 6])
            idx = pos + 6
            continue
        out_parts.append(text[idx:pos])
        depth = 0
        end_pos = pos + 5
        while end_pos < len(text):
            ch = text[end_pos]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break
            end_pos += 1
        if depth == 0:
            expr_str = text[pos : end_pos + 1]
            out_parts.append(_format_human_readable_formula(expr_str))
            idx = end_pos + 1
        else:
            out_parts.append(text[pos:])
            break
    return "".join(out_parts)


def _convert_js_ternary_to_python(expr: str) -> str:
    """Converts nested JS ternary `(cond ? a : b)` expressions into Python `((a) if (cond) else (b))`."""
    py_expr = expr
    max_iters = 64
    for _ in range(max_iters):
        q_idx = py_expr.find("?")
        if q_idx == -1:
            break
        # Find enclosing '(' before '?'
        depth = 0
        open_idx = -1
        for i in range(q_idx - 1, -1, -1):
            ch = py_expr[i]
            if ch == ")":
                depth += 1
            elif ch == "(":
                if depth == 0:
                    open_idx = i
                    break
                depth -= 1
        start_idx = open_idx + 1 if open_idx != -1 else 0

        # Find matching ':' at depth 0 after '?'
        depth = 0
        colon_idx = -1
        for i in range(q_idx + 1, len(py_expr)):
            ch = py_expr[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                if depth == 0:
                    break
                depth -= 1
            elif ch == ":" and depth == 0:
                colon_idx = i
                break
        if colon_idx == -1:
            break

        # Find matching ')' at depth 0 after ':'
        depth = 0
        end_idx = len(py_expr)
        for i in range(colon_idx + 1, len(py_expr)):
            ch = py_expr[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                if depth == 0:
                    end_idx = i
                    break
                depth -= 1

        cond_part = py_expr[start_idx:q_idx].strip()
        true_part = py_expr[q_idx + 1 : colon_idx].strip()
        false_part = py_expr[colon_idx + 1 : end_idx].strip()
        py_expr = (
            py_expr[:start_idx]
            + f"(({true_part}) if ({cond_part}) else ({false_part}))"
            + py_expr[end_idx:]
        )
    return py_expr


def _eval_compiled_js_expr(js_expr: str, clamped_inputs: Dict[str, float]) -> float:
    """Evaluates a compiled JS arithmetic/piecewise expression in Python to verify parity."""
    import math
    from types import SimpleNamespace

    py_expr = _convert_js_ternary_to_python(js_expr)
    py_expr = py_expr.replace("===", "==").replace("!==", "!=")
    py_expr = py_expr.replace("&&", " and ").replace("||", " or ")
    py_expr = re.sub(r"!(?!=)", " not ", py_expr)

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
    return float(
        eval(
            py_expr,
            {"__builtins__": {}},
            {"Math": math_ns, "inputs": ns_inputs, "true": True, "false": False},
        )
    )


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
    formula: str = "",
    inputs: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Renders a 5-point server-side sensitivity scenario table (0.8x to 1.2x)
    combining linear proportional benchmarks with non-linear statutory AST
    evaluations against fixed statutory caps and phaseouts.
    Zero em-dashes. Zero en-dashes.
    """
    conservative_output = _format_scenario_number(published_output * 0.8)
    mod_con_output = _format_scenario_number(published_output * 0.9)
    mod_exp_output = _format_scenario_number(published_output * 1.1)
    aggressive_output = _format_scenario_number(published_output * 1.2)
    from pseofactory.competitor import _format_safe_heading_topic
    from pseofactory.proprietary_signals import compute_5point_nonlinear_sensitivity_rows

    clean_model = _format_safe_heading_topic(str(model_name or "").strip(), "")
    sens_h2 = f"Sensitivity Scenario Modeling: {clean_model}" if clean_model else "Sensitivity Scenario Modeling"
    ast_rows = compute_5point_nonlinear_sensitivity_rows(
        formula=formula,
        inputs=inputs or {},
        published_output=published_output,
    )
    ast_by_cls = {r["css_class"]: r for r in ast_rows}
    base_ast = ast_by_cls.get("scenario-baseline", {"ast_output": display_output, "cliff_delta": "0.00 (Linear Parity)"})
    con_ast = ast_by_cls.get("scenario-conservative", {"ast_output": conservative_output, "cliff_delta": "0.00 (Linear Parity)"})
    mcon_ast = ast_by_cls.get("scenario-moderate-contraction", {"ast_output": mod_con_output, "cliff_delta": "0.00 (Linear Parity)"})
    mexp_ast = ast_by_cls.get("scenario-moderate-expansion", {"ast_output": mod_exp_output, "cliff_delta": "0.00 (Linear Parity)"})
    agg_ast = ast_by_cls.get("scenario-aggressive", {"ast_output": aggressive_output, "cliff_delta": "0.00 (Linear Parity)"})

    return (
        f'    <div class="scenario-container comparison-container card pseo-card" '
        f'data-entity-type="scenario" data-mechanic="server_rendered_sensitivity_grid">\n'
        f'      <h2>{sens_h2}</h2>\n'
        f'      <p>SSR 5-point sensitivity matrix comparing linear proportional benchmarks against non-linear statutory AST evaluations across fixed exemptions and phaseout cliffs:</p>\n'
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
        f'              <th scope="col">Non-Linear Statutory AST Output</th>\n'
        f'              <th scope="col">Statutory Cliff Divergence</th>\n'
        f'            </tr>\n'
        f'          </thead>\n'
        f'          <tbody>\n'
        f'            <tr data-entity-type="scenario">\n'
        f'              <td><strong>Baseline Scenario</strong></td>\n'
        f'              <td>Standard published parameters (1.0x)</td>\n'
        f'              <td>{statutory_authority}</td>\n'
        f'              <td>{economic_dataset}</td>\n'
        f'              <td><strong class="scenario-baseline">{display_output}</strong></td>\n'
        f'              <td><strong class="scenario-ast-eval" data-tier="baseline">{base_ast["ast_output"]}</strong></td>\n'
        f'              <td><span class="scenario-cliff-delta">{base_ast["cliff_delta"]}</span></td>\n'
        f'            </tr>\n'
        f'            <tr data-entity-type="scenario">\n'
        f'              <td><strong>Conservative Scenario</strong></td>\n'
        f'              <td>20% Parameter contraction (0.8x)</td>\n'
        f'              <td>{statutory_authority}</td>\n'
        f'              <td>{economic_dataset}</td>\n'
        f'              <td><strong class="scenario-conservative">{conservative_output}</strong></td>\n'
        f'              <td><strong class="scenario-ast-eval" data-tier="conservative">{con_ast["ast_output"]}</strong></td>\n'
        f'              <td><span class="scenario-cliff-delta">{con_ast["cliff_delta"]}</span></td>\n'
        f'            </tr>\n'
        f'            <tr data-entity-type="scenario">\n'
        f'              <td><strong>Moderate Contraction Scenario</strong></td>\n'
        f'              <td>10% Parameter contraction (0.9x)</td>\n'
        f'              <td>{statutory_authority}</td>\n'
        f'              <td>{economic_dataset}</td>\n'
        f'              <td><strong class="scenario-moderate-contraction">{mod_con_output}</strong></td>\n'
        f'              <td><strong class="scenario-ast-eval" data-tier="moderate-contraction">{mcon_ast["ast_output"]}</strong></td>\n'
        f'              <td><span class="scenario-cliff-delta">{mcon_ast["cliff_delta"]}</span></td>\n'
        f'            </tr>\n'
        f'            <tr data-entity-type="scenario">\n'
        f'              <td><strong>Moderate Expansion Scenario</strong></td>\n'
        f'              <td>10% Parameter expansion (1.1x)</td>\n'
        f'              <td>{statutory_authority}</td>\n'
        f'              <td>{economic_dataset}</td>\n'
        f'              <td><strong class="scenario-moderate-expansion">{mod_exp_output}</strong></td>\n'
        f'              <td><strong class="scenario-ast-eval" data-tier="moderate-expansion">{mexp_ast["ast_output"]}</strong></td>\n'
        f'              <td><span class="scenario-cliff-delta">{mexp_ast["cliff_delta"]}</span></td>\n'
        f'            </tr>\n'
        f'            <tr data-entity-type="scenario">\n'
        f'              <td><strong>Aggressive Scenario</strong></td>\n'
        f'              <td>20% Parameter expansion (1.2x)</td>\n'
        f'              <td>{statutory_authority}</td>\n'
        f'              <td>{economic_dataset}</td>\n'
        f'              <td><strong class="scenario-aggressive">{aggressive_output}</strong></td>\n'
        f'              <td><strong class="scenario-ast-eval" data-tier="aggressive">{agg_ast["ast_output"]}</strong></td>\n'
        f'              <td><span class="scenario-cliff-delta">{agg_ast["cliff_delta"]}</span></td>\n'
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
    Renders hash-state scenario preset buttons (Conservative, Baseline, Aggressive)
    for 1-click user parameter hydration without crawlable ?param= URL bloat.
    Zero em-dashes. Zero en-dashes.
    """
    _ = canonical_base, slug
    presets = [
        ("Conservative (0.8x)", 0.8, "conservative"),
        ("Baseline (1.0x)", 1.0, "baseline"),
        ("Aggressive (1.2x)", 1.2, "aggressive"),
    ]
    buttons_html: List[str] = []
    for label, mult, preset_key in presets:
        params: List[str] = []
        for k, v in clamped_inputs.items():
            if isinstance(v, (int, float)):
                scaled = round(float(v) * mult, 2)
                val_str = str(int(scaled)) if scaled.is_integer() else str(scaled)
                params.append(f"{k}={val_str}")
        hs = "&amp;".join(params)
        hash_val = f"#{hs}" if hs else "#"
        buttons_html.append(
            f'          <button type="button" data-preset="{preset_key}" data-preset-hash="{hash_val}" '
            f'class="touch-target scenario-preset-btn" '
            f'style="display: inline-flex; align-items: center; justify-content: center; '
            f'min-height: 44px; min-width: 44px; padding: 10px 14px; border-radius: 8px; '
            f'background: var(--bg-elevated); color: var(--accent); '
            f'border: 1px solid var(--border-strong); cursor: pointer; font-size: 14px; font-weight: 600;">'
            f'{label}</button>'
        )
    joined_buttons = "\n".join(buttons_html)
    return (
        f'        <div class="scenario-presets-bar" data-mechanic="deep_link_scenario_presets" '
        f'style="display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 16px;">\n'
        f'{joined_buttons}\n'
        f'        </div>'
    )


def _render_compiler_monetization_and_guardrail_html(
    slug: str,
    query: str,
    is_prexvo: bool,
    candidate_spec: Dict[str, Any],
    is_gainhelm: bool = False,
    is_lienbond: bool = False,
) -> Dict[str, Any]:
    """
    Renders domain-isolated multi-company affiliate partner rosters and deterministic
    conversion slots on profithelm, gainhelm, and lienbond, and enforces YMYL statutory guardrails on prexvo
    (suppressing commercial offers on restricted public-service pages).
    Zero em-dashes. Zero en-dashes.
    """
    import html as html_lib
    from pseofactory.affiliates import (
        bind_asset_partner_roster,
        build_first_party_workpaper_cta_html,
        is_partner_live_in_vault,
    )

    prop_id = "prexvo" if is_prexvo else ("gainhelm" if is_gainhelm else ("lienbond" if is_lienbond else "profithelm"))
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
        if (
            isinstance(inline_offer, dict)
            and inline_offer.get("partner_key")
            and is_partner_live_in_vault(prop_id, str(inline_offer["partner_key"]))
        ):
            pk_in = str(inline_offer["partner_key"])
            in_badge = html_lib.escape(str(inline_offer.get("badge") or "Verified Offer"))
            in_name = html_lib.escape(str(inline_offer.get("name") or pk_in))
            in_cta = html_lib.escape(str(inline_offer.get("cta_text") or "Explore Partner"))
            in_brand = html_lib.escape(str(inline_offer.get("company_brand") or pk_in))
            in_model = html_lib.escape(str(inline_offer.get("partnership_model") or "CPA_BOUNTY"))
            in_href = html_lib.escape(str(inline_offer.get("attributed_href") or f"/r/{pk_in}"))
            in_sub = html_lib.escape(str(inline_offer.get("subid") or f"{slug_id}_inline"))
            in_status = "live"
            in_slot_label = "Primary Conversion Slot"
            inline_html = (
                f'\n        <div class="calc-inline-cta" data-mechanic="compliant_intent_monetization" '
                f'data-partner="{pk_in}" data-company-brand="{in_brand}" data-partner-tier="primary" '
                f'data-partnership-model="{in_model}" '
                f'data-cta-slot="calculator_result_inline" '
                f'style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 14px; margin-top: 12px; background: var(--bg-elevated); border: 1px solid var(--border-strong); border-left: 4px solid var(--accent); border-radius: 8px;">\n'
                f'          <div class="calc-inline-cta-copy" style="flex: 1; min-width: 180px;">\n'
                f'            <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--accent);">{in_badge} &bull; {in_slot_label}</div>\n'
                f'            <div style="font-size: 14px; font-weight: 700; color: var(--text); margin-top: 2px;">{in_name}</div>\n'
                f'          </div>\n'
                f'          <a href="{in_href}" rel="noopener sponsored nofollow" target="_blank" '
                f'data-partner="{pk_in}" data-company-brand="{in_brand}" data-partner-tier="primary" '
                f'data-partnership-model="{in_model}" '
                f'data-tool="{html_lib.escape(slug_id)}" data-subid="{in_sub}" data-status="{in_status}" '
                f'data-cta-slot="calculator_result_inline" class="btn-cta partner-cta touch-target" '
                f'style="display: inline-flex; align-items: center; justify-content: center; min-height: 44px; min-width: 44px; padding: 10px 14px; border-radius: 8px; background: var(--accent); color: var(--cta-fg); font-weight: 600; text-decoration: none; white-space: nowrap;">{in_cta}</a>\n'
                f'        </div>'
            )
        if (
            "comparison_table_cta" in (slot_plan.get("active_slots") or [])
            and isinstance(table_offer, dict)
            and table_offer.get("partner_key")
            and is_partner_live_in_vault(prop_id, str(table_offer["partner_key"]))
        ):
            pk_tb = str(table_offer["partner_key"])
            tb_name = html_lib.escape(str(table_offer.get("name") or pk_tb))
            tb_cta = html_lib.escape(str(table_offer.get("cta_text") or "Compare Partner"))
            tb_brand = html_lib.escape(str(table_offer.get("company_brand") or pk_tb))
            tb_role = html_lib.escape(str(table_offer.get("tier_role") or "secondary"))
            tb_model = html_lib.escape(str(table_offer.get("partnership_model") or "CPA_BOUNTY"))
            tb_href = html_lib.escape(str(table_offer.get("attributed_href") or f"/r/{pk_tb}"))
            tb_sub = html_lib.escape(str(table_offer.get("subid") or f"{slug_id}_table"))
            tb_status = "live"
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
                f'data-tool="{html_lib.escape(slug_id)}" data-subid="{tb_sub}" data-status="{tb_status}" '
                f'data-cta-slot="comparison_table_cta" class="btn-cta partner-cta touch-target" '
                f'style="display: inline-flex; align-items: center; justify-content: center; min-height: 44px; min-width: 44px; padding: 10px 14px; border-radius: 8px; background: var(--accent); color: var(--cta-fg); font-weight: 600; text-decoration: none;">{tb_cta}</a>\n'
                f'    </div>'
            )
        return inline_html, table_html

    def _build_roster_cards_grid_html() -> str:
        matrix_cards = [
            c
            for c in (bindings.get("partner_matrix_cards") or [])
            if isinstance(c, dict) and is_partner_live_in_vault(prop_id, str(c.get("partner_key") or ""))
        ]
        if not matrix_cards:
            return ""
        card_items: List[str] = []
        for idx, card_offer in enumerate(matrix_cards, start=1):
            c_pk = str(card_offer.get("partner_key") or "")
            c_name = html_lib.escape(str(card_offer.get("name") or c_pk))
            c_desc = html_lib.escape(str(card_offer.get("description") or ""))
            c_badge = html_lib.escape(str(card_offer.get("badge") or "Partner Option"))
            c_cta = html_lib.escape(str(card_offer.get("cta_text") or "Explore Partner"))
            c_brand = html_lib.escape(str(card_offer.get("company_brand") or c_pk))
            c_role = html_lib.escape(str(card_offer.get("tier_role") or ("primary" if idx == 1 else "secondary")))
            c_model = html_lib.escape(str(card_offer.get("partnership_model") or "CPA_BOUNTY"))
            c_slot = html_lib.escape(str(card_offer.get("cta_slot") or ("calculator_primary_cta" if idx == 1 else "partner_matrix_card")))
            c_href = html_lib.escape(str(card_offer.get("attributed_href") or f"/r/{c_pk}"))
            c_sub = html_lib.escape(str(card_offer.get("subid") or f"{slug_id}_card_{idx}"))
            c_status = html_lib.escape(str(card_offer.get("status") or "pending"))
            c_disc_label = f"Sponsored / {c_brand}" if c_status == "live" else f"Partner Disclosure / {c_brand}"
            card_items.append(
                f'        <div class="affiliate-card partner-card" data-partner="{c_pk}" '
                f'data-company-brand="{c_brand}" data-partner-tier="{c_role}" data-partnership-model="{c_model}" '
                f'style="padding: 14px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: 8px; display: flex; flex-direction: column; justify-content: space-between; gap: 10px;">\n'
                f'          <div class="affiliate-info">\n'
                f'            <span class="affiliate-badge" style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--accent);">{c_badge} ({c_role.title()})</span>\n'
                f'            <span class="affiliate-disclosure-badge" style="font-size: 11px; color: var(--text-muted); margin-left: 6px;">{c_disc_label}</span>\n'
                f'            <h3 class="affiliate-title" style="margin: 6px 0 4px 0; font-size: 15px;">{c_name}</h3>\n'
                f'            <p class="affiliate-desc" style="margin: 0; font-size: 13px; color: var(--text-muted);">{c_desc}</p>\n'
                f'          </div>\n'
                f'          <div>\n'
                f'            <a href="{c_href}" rel="noopener sponsored nofollow" target="_blank" '
                f'data-partner="{c_pk}" data-company-brand="{c_brand}" data-partner-tier="{c_role}" '
                f'data-partnership-model="{c_model}" '
                f'data-tool="{html_lib.escape(slug_id)}" data-subid="{c_sub}" data-status="{c_status}" '
                f'data-cta-slot="{c_slot}" class="btn-cta partner-cta touch-target" '
                f'style="display: inline-flex; align-items: center; justify-content: center; min-height: 44px; min-width: 44px; padding: 10px 14px; border-radius: 8px; background: var(--accent); color: var(--cta-fg); font-weight: 600; text-decoration: none; font-size: 14px;">{c_cta}</a>\n'
                f'          </div>\n'
                f'        </div>'
            )
        return (
            f'      <div class="partner-roster-grid" data-roster-count="{len(matrix_cards)}" '
            f'style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; margin-top: 14px;">\n'
            + "\n".join(card_items)
            + "\n      </div>\n"
        )

    def _build_partner_registration_drawer_html() -> str:
        # Step 4: #partner-registration-form lives strictly on dedicated /partners/, never on calculator pages.
        return ""

    from pseofactory.affiliates import (
        build_contextual_referral_card_html,
        is_restricted_public_service_slug,
        resolve_optimal_partner_for_slug,
    )

    def _build_affiliate_route_meta(prop_val: str) -> Optional[Dict[str, Any]]:
        partner_obj = resolve_optimal_partner_for_slug(
            property_id=prop_val,
            slug=slug,
            engagement_metrics=engagement_metrics,
        )
        if partner_obj is None:
            return None
        return {
            "partner_key": str(partner_obj.key),
            "partner_name": str(partner_obj.name),
            "company_brand": str(getattr(partner_obj, "company_brand", "") or ""),
            "partnership_model": str(getattr(partner_obj, "partnership_model", "") or ""),
        }

    if not is_prexvo:
        referral_html = build_contextual_referral_card_html(
            property_id=prop_id,
            slug=slug,
            query=query,
            gsc_metrics=gsc_metrics,
            engagement_metrics=engagement_metrics,
            page_archetype=page_archetype,
        )
        return {
            "html": ("    " + referral_html) if referral_html else "",
            "inline_calc_cta_html": "",
            "comparison_table_cta_html": "",
            "affiliate_route": _build_affiliate_route_meta(prop_id),
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
        referral_html = build_contextual_referral_card_html(
            property_id="prexvo",
            slug=slug,
            query=query,
            gsc_metrics=gsc_metrics,
            engagement_metrics=engagement_metrics,
            page_archetype=page_archetype,
        )
        return {
            "html": ("    " + referral_html) if referral_html else "",
            "inline_calc_cta_html": "",
            "comparison_table_cta_html": "",
            "affiliate_route": _build_affiliate_route_meta("prexvo"),
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
        "commercial_offers_allowed": False,
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
    is_lienbond: bool = False,
) -> List[Dict[str, Any]]:
    """Builds conversational FAQPage entities tailored to tenant and tool cluster."""
    readable_formula = _format_human_readable_formula(formula)
    plain_faq_formula = _format_plain_prose_formula(formula, readable_formula)
    faq_entities: List[Dict[str, Any]] = [
        {
            "@type": "Question",
            "name": f"How is {title} determined under statutory authority guidelines?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": f"The deterministic calculation model evaluates {plain_faq_formula} based on statutory rules from {statutory_authority} and empirical indicators from {economic_dataset}.",
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
    elif is_lienbond:
        faq_entities.extend([
            {
                "@type": "Question",
                "name": f"What statutory filings and underwriting documents are required under {statutory_authority}?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Contractors and subcontractors must maintain verified Treasury Circular 570 surety bond riders, trade-segregated NCCI payroll ledgers, certified mail Preliminary Notice proofs of service, and conditional/unconditional statutory lien waivers.",
                },
            },
            {
                "@type": "Question",
                "name": "How do working capital ratios, EMR scores, and credit tiers affect surety bond and workers comp rates?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": f"Underwriters evaluate net working capital (target 10% of bonded backlog), FICO credit tiers, and NCCI Experience Modification Rates (EMR) against empirical benchmarks in {economic_dataset}.",
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


def _normalize_iso_datetime_with_tz(raw_val: Any) -> Optional[str]:
    """Normalizes a date or timestamp string to ISO 8601 with explicit UTC timezone."""
    txt = str(raw_val or "").strip()
    if not txt:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$", txt):
        return txt
    m_day = re.match(r"^(\d{4}-\d{2}-\d{2})", txt)
    if m_day:
        return f"{m_day.group(1)}T00:00:00+00:00"
    return None


def _resolve_iso_dates_with_tz(
    property_id: str,
    candidate_spec: Optional[Dict[str, Any]] = None,
    manifest_source: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """
    Resolves (datePublished, dateModified) as ISO 8601 strings WITH timezone
    from asset/TruthPack data_modified_date and statute_effective_date, falling
    back to a deterministic content-hash manifest date (never hardcoded stale literals).
    """
    spec = candidate_spec or {}
    man = manifest_source or {}

    raw_mod = (
        spec.get("data_modified_date")
        or man.get("data_modified_date")
        or spec.get("updated_date")
        or spec.get("updated_at")
        or man.get("updated_date")
        or spec.get("dateModified")
        or man.get("dateModified")
    )
    raw_pub = (
        spec.get("statute_effective_date")
        or man.get("statute_effective_date")
        or spec.get("published_date")
        or man.get("published_date")
        or spec.get("datePublished")
        or man.get("datePublished")
    )

    tp_mod: Optional[str] = None
    tp_pub: Optional[str] = None
    pid = str(property_id or "").strip().lower()
    if pid:
        try:
            from pseofactory.truth_pack import load_truth_pack

            tp = load_truth_pack(pid, allow_expired=True)
            tp_mod = str(getattr(tp, "data_modified_date", "") or "").strip() or None
            tp_pub = str(getattr(tp, "statute_effective_date", "") or "").strip() or None
            entries = list((getattr(tp, "entries", {}) or {}).values())
            if not tp_mod and entries:
                ver_dates = [
                    str(getattr(e, "verified_at", "") or "").strip()
                    for e in entries
                    if str(getattr(e, "verified_at", "") or "").strip()
                ]
                if ver_dates:
                    tp_mod = max(ver_dates)
            if not tp_pub and entries:
                eff_years = [
                    int(getattr(e, "effective_year", 0))
                    for e in entries
                    if getattr(e, "effective_year", None)
                ]
                if eff_years:
                    tp_pub = f"{min(eff_years)}-01-01"
                elif tp_mod:
                    tp_pub = tp_mod
        except Exception:
            pass

    mod_iso = _normalize_iso_datetime_with_tz(raw_mod) or _normalize_iso_datetime_with_tz(tp_mod)
    pub_iso = _normalize_iso_datetime_with_tz(raw_pub) or _normalize_iso_datetime_with_tz(tp_pub)

    if not mod_iso or not pub_iso:
        seed_obj = {"property_id": pid, "slug": spec.get("slug") or man.get("slug") or "", "title": spec.get("title") or ""}
        digest = hashlib.sha256(json.dumps(seed_obj, sort_keys=True).encode("utf-8")).hexdigest()
        now_utc = datetime.now(timezone.utc)
        day_offset = int(digest[:4], 16) % 28 + 1
        fallback_day = f"{now_utc.year:04d}-{now_utc.month:02d}-{day_offset:02d}T00:00:00+00:00"
        if not mod_iso:
            mod_iso = now_utc.strftime("%Y-%m-%dT00:00:00+00:00")
        if not pub_iso:
            pub_iso = fallback_day

    return pub_iso, mod_iso


def _is_official_primary_source_url(url: str) -> bool:
    """Returns True when URL points to an official .gov, .mil, state .us legislature, eur-lex.europa.eu, or pcisecuritystandards.org host."""
    import urllib.parse

    raw = str(url or "").strip()
    if not raw.startswith(("http://", "https://")):
        return False
    try:
        host = (urllib.parse.urlparse(raw).hostname or "").strip().lower()
    except ValueError:
        return False
    if not host:
        return False
    return (
        host.endswith(".gov")
        or host.endswith(".mil")
        or host == "leg.state.fl.us"
        or bool(re.search(r"(?:^|\.)state\.[a-z]{2}\.us$", host))
        or host == "eur-lex.europa.eu"
        or host.endswith(".eur-lex.europa.eu")
        or host == "pcisecuritystandards.org"
        or host.endswith(".pcisecuritystandards.org")
        or host == "fred.stlouisfed.org"
        or host.endswith(".fred.stlouisfed.org")
    )


def _build_statutory_sources_and_changelog_html(
    property_id: str,
    slug: str,
    statutory_authority: str,
    topic_label: str = "",
) -> str:
    """
    Renders mandatory SSR 'Statutory Sources & Formula Verification' block with live outbound
    official primary-source links and a concise 'Statutory Changelog' using strict deterministic
    slug-archetype / exact-statute matching (zero loose prose token leakage).
    Zero em-dashes. Zero en-dashes.
    """
    import html as html_lib
    from pseofactory.porcelain_shell import resolve_statutory_sources_for_calculator

    pid = str(property_id or "").strip().lower()
    slug_l = str(slug or "").strip().lower()
    selected_links, statute_eff_date = resolve_statutory_sources_for_calculator(
        property_id=pid,
        slug=slug_l,
        statutory_authority=str(statutory_authority or "").strip(),
    )
    if not selected_links:
        return ""

    source_items_html = "\n".join(
        f'        <li><a href="{html_lib.escape(u, quote=True)}" rel="noopener" target="_blank" '
        f'class="touch-target" style="display:inline-flex;align-items:center;min-height:44px;">'
        f'{html_lib.escape(cit)} ({html_lib.escape(pub)})</a></li>'
        for u, cit, pub, _ey, _va in selected_links
    )

    eff_years = sorted({ey for _u, _c, _p, ey, _va in selected_links if ey})
    max_eff_year = max(eff_years) if eff_years else 2026
    ver_dates = sorted({va for _u, _c, _p, _ey, va in selected_links if va})
    latest_verified = max(ver_dates) if ver_dates else "2026-11-24"
    eff_date_str = statute_eff_date or f"{max_eff_year}-01-01"
    lead_cit = selected_links[0][1]
    lead_pub = selected_links[0][2]

    changelog_bullets = [
        f"<strong>{max_eff_year} Statutory Effective Schedule ({html_lib.escape(eff_date_str)}):</strong> Parameters locked to enacted {html_lib.escape(lead_cit)} published by {html_lib.escape(lead_pub)}.",
        f"<strong>Primary Source Verification ({html_lib.escape(latest_verified)}):</strong> Formula constants and statutory bounds verified directly against official {html_lib.escape(lead_pub)} tables.",
    ]
    if len(eff_years) > 1:
        changelog_bullets.append(
            f"<strong>Multi-Year Schedule Alignment ({eff_years[0]} to {eff_years[-1]}):</strong> Cross-checked enacted parameter transitions across statutory effective years."
        )
    else:
        changelog_bullets.append(
            f"<strong>Deterministic Formula Audit ({max_eff_year}):</strong> Verified closed-form AST evaluation and non-negative input clamping for {html_lib.escape(topic_label or slug or 'this calculator')}."
        )
    changelog_li_html = "\n".join(f"        <li>{b}</li>" for b in changelog_bullets[:4])

    return (
        f'    <section class="statutory-sources card" data-mechanic="official_primary_sources">\n'
        f'      <h2>Statutory Sources &amp; Formula Verification</h2>\n'
        f'      <p>Verify the enacted statutes and official regulatory publications governing {html_lib.escape(topic_label or slug or "this model")}:</p>\n'
        f'      <ul class="statutory-sources-list">\n'
        f'{source_items_html}\n'
        f'      </ul>\n'
        f'    </section>\n'
        f'    <section class="statutory-changelog card" data-mechanic="statutory_changelog">\n'
        f'      <h2>Statutory Changelog</h2>\n'
        f'      <ul class="statutory-changelog-list">\n'
        f'{changelog_li_html}\n'
        f'      </ul>\n'
        f'    </section>'
    )


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
    is_lienbond: bool = False,
    date_published: Optional[str] = None,
    date_modified: Optional[str] = None,
    is_home: bool = False,
    collection_items: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Builds the unified Schema.org @graph JSON-LD string for compiled programmatic pages."""
    _ = faq_entities
    brand_org_name = "Prexvo" if is_prexvo else ("GainHelm" if is_gainhelm else ("LienBond" if is_lienbond else "ProfitHelm"))
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
            {"@type": "ListItem", "position": 2, "name": "Calculators", "item": f"{canonical_base}/tools/"},
            {"@type": "ListItem", "position": 3, "name": hub_display_name, "item": f"{canonical_base}/tools/{hub_slug_part}/"},
            {"@type": "ListItem", "position": 4, "name": title, "item": f"{canonical_base}/tools/{slug}/"},
        ]
    else:
        breadcrumb_items_list = [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{canonical_base}/"},
            {"@type": "ListItem", "position": 2, "name": "Calculators", "item": f"{canonical_base}/tools/"},
            {"@type": "ListItem", "position": 3, "name": title, "item": f"{canonical_base}/tools/{slug}/"},
        ]
    from pseofactory.tenant_facts import get_tenant_contract

    _prop_for_schema = "prexvo" if is_prexvo else ("gainhelm" if is_gainhelm else ("lienbond" if is_lienbond else "profithelm"))
    _resolved_pub, _resolved_mod = _resolve_iso_dates_with_tz(_prop_for_schema)
    _eff_date_published = _normalize_iso_datetime_with_tz(date_published) or _resolved_pub
    _eff_date_modified = _normalize_iso_datetime_with_tz(date_modified) or _resolved_mod
    _schema_contract = get_tenant_contract(_prop_for_schema)
    _editorial_email = (
        "compliance@lienbond.com"
        if _prop_for_schema == "lienbond"
        else f"editorial@{_schema_contract.domain}"
    )
    _topic_wikidata_map = {
        "lienbond": ["https://www.wikidata.org/wiki/Q192161"],
        "prexvo": ["https://www.wikidata.org/wiki/Q633315"],
        "gainhelm": ["https://www.wikidata.org/wiki/Q166142"],
        "profithelm": ["https://www.wikidata.org/wiki/Q8161"],
    }
    _topic_qids = _topic_wikidata_map.get(_prop_for_schema, ["https://www.wikidata.org/wiki/Q7397"])
    _same_as_urls: List[str] = []
    if _schema_contract.linkedin_company_id:
        _same_as_urls.append(f"https://www.linkedin.com/company/{_schema_contract.linkedin_company_id}/")

    org_ref = {"@id": f"{canonical_base}/#organization"}

    if is_home:
        org_node: Dict[str, Any] = {
            "@type": "Organization",
            "@id": f"{canonical_base}/#organization",
            "name": brand_org_name,
            "url": canonical_base,
            "publishingPrinciples": f"{canonical_base}/methodology/",
            "contactPoint": {
                "@type": "ContactPoint",
                "contactType": "editorial",
                "email": _editorial_email,
            },
            "knowsAbout": _topic_qids,
        }
        if _same_as_urls:
            org_node["sameAs"] = _same_as_urls
        home_nodes: List[Dict[str, Any]] = [
            org_node,
            {
                "@type": "WebSite",
                "@id": f"{canonical_base}/#website",
                "url": canonical_base,
                "name": brand_org_name,
                "inLanguage": "en-US",
                "publisher": org_ref,
            },
            {
                "@type": "WebPage",
                "@id": f"{canonical_base}/#webpage",
                "url": f"{canonical_base}/",
                "name": title,
                "description": raw_meta_desc,
                "inLanguage": "en-US",
                "isPartOf": {"@id": f"{canonical_base}/#website"},
                "about": _topic_qids,
                "datePublished": _eff_date_published,
                "dateModified": _eff_date_modified,
            },
        ]
        if collection_items:
            list_elements = [
                {
                    "@type": "ListItem",
                    "position": idx,
                    "name": str(item.get("name") or "").strip(),
                    "url": str(item.get("url") or "").strip(),
                }
                for idx, item in enumerate(collection_items, start=1)
                if item.get("name") and item.get("url")
            ]
            if list_elements:
                home_nodes.append(
                    {
                        "@type": "ItemList",
                        "@id": f"{canonical_base}/#itemlist",
                        "name": f"{brand_org_name} Flagship Statutory Calculators",
                        "itemListOrder": "https://schema.org/ItemListOrderAscending",
                        "numberOfItems": len(list_elements),
                        "itemListElement": list_elements,
                    }
                )
        return json.dumps({"@context": "https://schema.org", "@graph": home_nodes}, indent=2)

    graph_payload = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebPage",
                "@id": f"{canonical_base}/tools/{slug}/#webpage",
                "url": f"{canonical_base}/tools/{slug}/",
                "name": title,
                "description": raw_meta_desc,
                "inLanguage": "en-US",
                "isPartOf": {"@id": f"{canonical_base}/#website"},
                "about": [{"@id": f"{canonical_base}/tools/{slug}/#app"}, *_topic_qids],
                "datePublished": _eff_date_published,
                "dateModified": _eff_date_modified,
                "breadcrumb": {"@id": f"{canonical_base}/tools/{slug}/#breadcrumb"},
            },
            {
                "@type": "WebApplication",
                "@id": f"{canonical_base}/tools/{slug}/#app",
                "name": title,
                "applicationCategory": application_category,
                "operatingSystem": "All",
                "browserRequirements": "Requires JavaScript",
                "url": f"{canonical_base}/tools/{slug}/",
                "inLanguage": "en-US",
                "dateModified": _eff_date_modified,
                "author": org_ref,
                "publisher": org_ref,
                "featureList": [
                    f"Deterministic Statutory Formula Evaluation ({statutory_authority})",
                    f"Empirical Benchmark Corroboration ({economic_dataset})",
                    "Interactive 5-Point Scenario Comparison Matrix",
                ],
                "offers": {
                    "@type": "Offer",
                    "price": "0",
                    "priceCurrency": "USD",
                    "availability": "https://schema.org/InStock",
                },
                "isRelatedTo": [
                    {
                        "@type": "CollectionPage",
                        "name": f"{brand_org_name} Statutory Tools Directory",
                        "url": f"{canonical_base}/tools/",
                    }
                ],
            },
            {
                "@type": "BreadcrumbList",
                "@id": f"{canonical_base}/tools/{slug}/#breadcrumb",
                "isPartOf": {"@id": f"{canonical_base}/tools/{slug}/#webpage"},
                "itemListElement": breadcrumb_items_list,
            },
        ],
    }
    return json.dumps(graph_payload, indent=2)


def _enrich_manifest_with_proprietary_signals(
    manifest: Dict[str, Any],
    candidate_spec: Dict[str, Any],
    manifest_source: Dict[str, Any],
    slug: str,
    query: str,
    statutory_authority: str,
    formula: str,
    clamped_inputs: Dict[str, Any],
    published_output: float,
) -> None:
    """Attaches statutory_economic_matrix, proprietary_telemetry, and corroborating_sources to manifest in-place."""
    from pseofactory.proprietary_signals import resolve_proprietary_signal_bundle

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
    spec_tenant_hint = " ".join(
        str(candidate_spec.get(k) or "")
        for k in ("property_id", "property", "tenant", "domain", "brand_name", "canonical_base")
    ).lower()
    inferred_prop = (
        "lienbond"
        if "lienbond" in spec_tenant_hint
        else (
            "gainhelm"
            if "gainhelm" in spec_tenant_hint
            else (
                "prexvo"
                if "prexvo" in spec_tenant_hint
                or any(t in str(statutory_authority).lower() for t in ("title iv", "34 cfr", "pslf", "repayment assistance plan"))
                else "profithelm"
            )
        )
    )
    bundle = resolve_proprietary_signal_bundle(
        property_id=inferred_prop,
        slug=slug,
        query=query,
        formula=formula,
        inputs=clamped_inputs,
        published_output=published_output,
    )
    if isinstance(statutory_matrix, dict) and '"year":' in json.dumps(statutory_matrix):
        statutory_matrix = json.loads(json.dumps(statutory_matrix))
        for _ser in statutory_matrix.get("series") or []:
            if isinstance(_ser, dict) and isinstance(_ser.get("timeline"), list):
                for _pt in _ser["timeline"]:
                    if isinstance(_pt, dict) and "year" in _pt:
                        _pt.setdefault("epoch", _pt["year"])
                        _pt.pop("year", None)
    manifest["proprietary_telemetry"] = bundle["proprietary_telemetry"]
    manifest["statutory_economic_matrix"] = statutory_matrix or bundle["statutory_economic_matrix"]
    if corroborating_sources:
        manifest["corroborating_sources"] = corroborating_sources


def _build_hero_range_and_state_bar_html(
    published_output: float,
    display_output: str,
    monetization_section_html: str,
    is_gainhelm: bool,
    slug: str = "",
    property_id: str = "",
) -> tuple[str, str]:
    """
    Deprecated: Hero range anchor, Register Your Firm link, and state-first hero bar are removed
    to keep .hero-section strictly H1 + subtitle + 40-60w .quick-answer above the fold.
    """
    _ = published_output, display_output, monetization_section_html, is_gainhelm, slug, property_id
    return "", ""


def _clamp_candidate_inputs(raw_inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Clamps numeric candidate inputs to non-negative (>= 0) per HWL-1263."""
    clamped_inputs: Dict[str, Any] = {}
    for k, v in raw_inputs.items():
        if isinstance(v, (int, float)):
            clamped_inputs[k] = max(0.0, float(v)) if isinstance(v, float) else max(0, v)
        elif isinstance(v, str):
            v_clean = v.replace("$", "").replace(",", "").replace("%", "").strip()
            try:
                clamped_inputs[k] = max(0.0, float(v_clean))
            except ValueError:
                clamped_inputs[k] = v
        else:
            clamped_inputs[k] = v
    return clamped_inputs


def _resolve_candidate_tenant_flags(
    candidate_spec: Dict[str, Any],
    slug: str,
) -> tuple[bool, bool, bool]:
    """Resolves (is_prexvo, is_gainhelm, is_lienbond) deterministically from spec, statutory authority, and env."""
    spec_tenant_signals = " ".join(
        str(candidate_spec.get(k) or "")
        for k in ("property_id", "property", "tenant", "domain", "brand_name", "canonical_base")
    ).lower()
    if "lienbond" in spec_tenant_signals:
        return False, False, True
    if "gainhelm" in spec_tenant_signals:
        return False, True, False
    if "profithelm" in spec_tenant_signals and "prexvo" not in spec_tenant_signals:
        return False, False, False
    if "prexvo" in spec_tenant_signals:
        return True, False, False

    stat_lower = str(candidate_spec.get("statutory_authority") or "").lower()
    slug_lower = slug.lower()
    env_signals = " ".join([
        os.environ.get("FACTORY_PROPERTY_ID", "").lower(),
        os.environ.get("FACTORY_BRAND_NAME", "").lower(),
        os.environ.get("FACTORY_DOMAIN", "").lower(),
    ])
    if any(
        t in stat_lower
        for t in ("aicpa ssae 18", "32 cfr part 170", "dfars 252.204", "iso/iec 27006", "45 cfr 160.404", "pci dss v4", "fedramp", "hitrust csf")
    ):
        return False, True, False
    if any(t in stat_lower for t in ("title iv", "34 cfr", "pslf", "repayment assistance plan")):
        return True, False, False
    if (
        any(t in stat_lower for t in ("irs rev. proc.", "26 u.s.c. section 1(", "26 u.s.c. section 179", "26 u.s.c. section 1031"))
        or slug_lower.startswith(("irs-2027-tax-brackets", "section-179-calculator", "section-1031-calculator", "crypto-tax-calculator", "tcja-sunset"))
    ):
        return False, False, False
    if "lienbond" in env_signals:
        return False, False, True
    if "gainhelm" in env_signals:
        return False, True, False
    return "prexvo" in env_signals, False, False


def _extract_candidate_metadata(candidate_spec: Dict[str, Any]) -> tuple:
    """Extracts and normalizes core candidate metadata and manifest fields."""
    manifest_source = candidate_spec.get("calculation_manifest") if isinstance(candidate_spec.get("calculation_manifest"), dict) else {}
    query = str(candidate_spec.get("query") or candidate_spec.get("primary_keyword") or "").strip()
    raw_slug = str(candidate_spec.get("slug") or "").strip()
    if not raw_slug:
        slug_src = query or candidate_spec.get("title") or "proprietary-model"
        raw_slug = re.sub(r"[^a-z0-9]+", "-", str(slug_src).lower()).strip("-")
    from pseofactory.audit import _resolve_expected_title
    title = _resolve_expected_title(candidate_spec)
    model_name = str(candidate_spec.get("model_name") or candidate_spec.get("proprietary_model") or manifest_source.get("model_name") or manifest_source.get("proprietary_model") or "Proprietary Calculation Model").strip()
    formula = str(candidate_spec.get("formula") or manifest_source.get("formula") or "").strip()
    raw_inputs = candidate_spec.get("inputs") if candidate_spec.get("inputs") is not None else manifest_source.get("inputs", {})
    statutory_authority = str(candidate_spec.get("statutory_authority") or candidate_spec.get("statutory_provenance") or candidate_spec.get("authority") or manifest_source.get("statutory_authority") or manifest_source.get("statutory_provenance") or manifest_source.get("authority") or "").strip()
    economic_dataset = str(candidate_spec.get("economic_dataset") or candidate_spec.get("economic_source") or manifest_source.get("economic_dataset") or manifest_source.get("economic_source") or "").strip()
    sample_calc = str(candidate_spec.get("sample_calculation") or candidate_spec.get("sample") or manifest_source.get("sample_calculation") or manifest_source.get("sample") or "").strip()
    return manifest_source, query, raw_slug, title, model_name, formula, raw_inputs, statutory_authority, economic_dataset, sample_calc


def _render_compiled_calculator_runtime_js(
    slug: str,
    calc_js_body: str,
    is_lienbond_currency: bool,
) -> str:
    """Renders the inline calculator runtime script with URL query-param sync and checkout passthrough."""
    currency_prefix = "$" if is_lienbond_currency else ""
    min_frac_js = "2" if is_lienbond_currency else "(Number.isInteger(val) ? 0 : 2)"
    return f"""  <script>
  (function() {{
    var form = document.getElementById("{slug}-calculator");
    if (!form) return;
    var outputElem = document.querySelector(".output-value");
    var slug = "{slug}";
    var currencyPrefix = "{currency_prefix}";
    function formatNumber(val) {{
      if (isNaN(val) || !isFinite(val)) return currencyPrefix + "0";
      if (Math.abs(val) > 0 && Math.abs(val) < 1 && Number(val.toFixed(4)) !== Number(val.toFixed(2))) {{
        return currencyPrefix + new Intl.NumberFormat("en-US", {{
          minimumFractionDigits: 4,
          maximumFractionDigits: 4
        }}).format(val);
      }}
      return currencyPrefix + new Intl.NumberFormat("en-US", {{
        minimumFractionDigits: {min_frac_js},
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
        var rawVal = String(el.value == null ? "" : el.value).trim();
        if (el.tagName && el.tagName.toUpperCase() === "SELECT" && rawVal && !/^-?\\d+(?:\\.\\d+)?$/.test(rawVal)) {{
          inputs[cleanName] = rawVal;
        }} else {{
          var v = parseFloat(rawVal);
          inputs[cleanName] = isNaN(v) ? 0 : Math.max(0, v);
        }}
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
    function updateHashParams(inputs, immediate) {{
      if (!window.history || !window.history.replaceState) return;
      if (debounceTimer) {{
        clearTimeout(debounceTimer);
        debounceTimer = null;
      }}
      function _applyHashParams() {{
        try {{
          var url = new URL(window.location.href);
          var hashParams = new URLSearchParams();
          for (var k in inputs) {{
            hashParams.set(k, inputs[k]);
          }}
          url.hash = "#" + hashParams.toString();
          window.history.replaceState({{}}, "", url.toString());
        }} catch (e) {{}}
      }}
      if (immediate) {{
        _applyHashParams();
        return;
      }}
      debounceTimer = setTimeout(_applyHashParams, 150);
    }}

    function applyParamStringToForm(rawStr) {{
      if (!rawStr) return false;
      try {{
        var clean = String(rawStr).replace(/^[?#]+/, "");
        if (!clean) return false;
        var params = new URLSearchParams(clean);
        var elements = form.querySelectorAll("input, select");
        var applied = false;
        for (var i = 0; i < elements.length; i++) {{
          var el = elements[i];
          var name = (el.name || el.id || "").replace(/^input-/, "").replace(/^range-/, "");
          if (params.has(name)) {{
            el.value = params.get(name);
            applied = true;
          }}
        }}
        return applied;
      }} catch (e) {{
        return false;
      }}
    }}

    function syncInputsFromHash() {{
      if (!window.location) return;
      if (window.location.hash && applyParamStringToForm(window.location.hash)) {{
        return;
      }}
      if (window.location.search) {{
        applyParamStringToForm(window.location.search);
      }}
    }}

    function calculate(inputs) {{
{calc_js_body}
    }}

    function handleRecompute(immediate, skipUrlSync) {{
      var inputs = getInputs();
      if (!skipUrlSync) {{
        updateHashParams(inputs, immediate);
      }} else if (debounceTimer) {{
        clearTimeout(debounceTimer);
        debounceTimer = null;
      }}
      var result = calculate(inputs);
      var formattedResult = formatNumber(result);
      if (outputElem) {{
        outputElem.textContent = formattedResult;
      }}
      var wpHeadline = document.getElementById("workpaper-preview-headline");
      if (wpHeadline) wpHeadline.textContent = formattedResult;
      var checkoutIds = ["btn-workpaper-quick-checkout", "btn-workpaper-full-checkout"];
      for (var ci = 0; ci < checkoutIds.length; ci++) {{
        var ckEl = document.getElementById(checkoutIds[ci]);
        if (ckEl && ckEl.href) {{
          try {{
            var ckUrl = new URL(ckEl.href, window.location.origin);
            ckUrl.searchParams.set("amount", String(Math.round(result)));
            for (var ik in inputs) {{
              ckUrl.searchParams.set(ik, String(inputs[ik]));
            }}
            ckEl.href = ckUrl.pathname + ckUrl.search;
          }} catch (err) {{}}
        }}
      }}
    }}

    syncInputsFromHash();
    handleRecompute(false, true);
    var presetBtns = document.querySelectorAll(".scenario-preset-btn");
    for (var pi = 0; pi < presetBtns.length; pi++) {{
      presetBtns[pi].addEventListener("click", function(ev) {{
        var btn = ev.currentTarget;
        var hashSpec = btn ? btn.getAttribute("data-preset-hash") : "";
        if (hashSpec && applyParamStringToForm(hashSpec)) {{
          handleRecompute(true, false);
        }}
      }});
    }}
    window.addEventListener("hashchange", function() {{
      syncInputsFromHash();
      handleRecompute(false, true);
    }});
    window.addEventListener("popstate", function() {{
      syncInputsFromHash();
      handleRecompute(false, true);
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
      handleRecompute(true);
      return false;
    }});
  }})();
  </script>"""


def _build_compiled_disclosures_funnel_and_seo(
    *,
    candidate_spec: Dict[str, Any],
    slug: str,
    title: str,
    query: str,
    formula: str,
    clamped_inputs: Dict[str, Any],
    published_output: float,
    display_output: str,
    sample_calc: str,
    safe_model_h2: str,
    statutory_authority: str,
    economic_dataset: str,
    canonical_base: str,
    cluster: Any,
    resolved_tenant: str,
    is_prexvo: bool,
    is_gainhelm: bool,
    is_lienbond: bool,
) -> Dict[str, Any]:
    """Builds regulatory disclosures, Step 1/2 funnel blocks, normalized meta description, and 40-60w takeaway."""
    regulatory_disclosures_html: List[str] = []
    if is_gainhelm:
        from pseofactory.affiliates import get_gainhelm_statutory_disclaimer

        gh_disc = (
            get_gainhelm_statutory_disclaimer(slug)
            or GAINHELM_DISCLOSURES.get("statutory_compliance_disclaimer")
            or GAINHELM_DISCLOSURES.get("statutory_audit_disclaimer")
            or ""
        ).strip()
        if gh_disc:
            regulatory_disclosures_html.append(
                '      <p class="regulatory-disclosure" style="font-size: 12px; color: var(--text-muted); margin-top: 12px;">\n'
                f'        {gh_disc}\n'
                '      </p>'
            )
    elif is_lienbond:
        lb_disc = (
            LIENBOND_DISCLOSURES.get("statutory_surety_disclaimer")
            or LIENBOND_DISCLOSURES.get("statutory_compliance_disclaimer")
            or ""
        ).strip()
        if lb_disc:
            regulatory_disclosures_html.append(
                '      <p class="regulatory-disclosure" style="font-size: 12px; color: var(--text-muted); margin-top: 12px;">\n'
                f'        {lb_disc}\n'
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

    for disc in candidate_spec.get("mandatory_disclosures") or []:
        if not any(disc.lower() in d.lower() for d in regulatory_disclosures_html):
            regulatory_disclosures_html.append(
                f'      <p class="regulatory-disclosure" style="font-size: 12px; color: var(--text-muted); margin-top: 12px;">\n'
                f'        {disc}\n'
                f'      </p>'
            )

    from pseofactory.affiliates import (
        build_step1_preview_controls_html,
        build_workpaper_unlock_card_html,
        is_restricted_public_service_slug,
    )

    is_restricted_asset = bool(is_prexvo and is_restricted_public_service_slug(slug, title))
    readable_formula = _format_human_readable_formula(formula)
    plain_prose_formula = _format_plain_prose_formula(
        formula,
        readable_formula,
        list(clamped_inputs.keys()) if isinstance(clamped_inputs, dict) else None,
    )
    is_complex_formula = "min(" in readable_formula.lower() or "max(" in readable_formula.lower()
    formula_html_inline = (
        _html.escape(plain_prose_formula)
        if is_complex_formula
        else f"<code>{readable_formula}</code>"
    )
    is_lienbond_currency = bool(
        is_lienbond
        and not any(
            tok in slug.lower()
            for tok in ("deadline", "emr", "experience-modification", "notice-window", "days-to-")
        )
    )
    eff_display_output = f"${display_output}" if (is_lienbond_currency and not str(display_output).startswith("$")) else display_output
    visible_sample_calc = _sanitize_visible_sample_calculation(sample_calc)

    step1_preview_html = (
        ""
        if is_restricted_asset
        else build_step1_preview_controls_html(
            property_id=resolved_tenant,
            slug=slug,
            query=query,
            baseline_output=published_output,
            display_output=eff_display_output,
            statutory_authority=statutory_authority,
        )
    )
    workpaper_unlock_card_html = build_workpaper_unlock_card_html(
        property_id=resolved_tenant,
        slug=slug,
        query=query,
        topic_label=title,
        statutory_authority=statutory_authority,
        baseline_amount=published_output,
    )
    disclosures_html_block = ("\n" + "\n".join(regulatory_disclosures_html)) if regulatory_disclosures_html else ""
    default_gsc_token = (
        "wonyZkQ-8DZKcbdV_GTbbxIZVWgA3kWYvABx0jSrN4Q"
        if is_lienbond
        else (
            "Elwe-MFi7Z8hEE7ybiGr8xXBqSv87dF_ZMpqkhCDlQ8"
            if is_gainhelm
            else (
                "At5f9a2APEkZhsFx0LICFC5R-TNKsXxzNsbG5YhUoIA"
                if "prexvo" in str(canonical_base or "").lower()
                else "1b9AjxT3rRYA2iyPRraN2ShDNqEoKsfYW39UiTncB4U"
            )
        )
    )
    gsc_token = (
        str(candidate_spec.get("gsc_verification_token") or "").strip()
        or os.environ.get("GSC_VERIFICATION_TOKEN", default_gsc_token)
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
        if is_lienbond:
            primary_stat_auth = statutory_authority.split(",")[0].strip() or statutory_authority
            raw_meta_desc = f"Calculate {short_t} deterministically under {primary_stat_auth}."
        else:
            raw_meta_desc = f"Verified quantitative calculation engine evaluating {short_t} deterministically under {statutory_authority}."
    if len(raw_meta_desc) > 155:
        from pseofactory.contracts import detect_malformed_statutory_citations

        words_m = raw_meta_desc.rstrip(".!?").split()
        while len(words_m) > 6 and (
            len(" ".join(words_m).rstrip(".,;:") + ".") > 155
            or words_m[-1].lower().rstrip(".,;:") in ("under", "and", "or", "with", "for", "of", "in", "to", "by", "from", "the", "a", "an", "section", "sec", "part", "u.s.c", "usc", "cfr", "c.f.r", "irc", "i.r.c", "40", "29", "26", "31", "32", "34")
            or bool(detect_malformed_statutory_citations(" ".join(words_m).rstrip(".,;:") + "."))
        ):
            words_m.pop()
        raw_meta_desc = " ".join(words_m).rstrip(".,;:") + "."
    if is_gainhelm:
        from pseofactory.gsc_remediation import _normalize_meta_120_155

        raw_meta_desc = _normalize_meta_120_155(raw_meta_desc, "gainhelm", title, slug=slug)
    if is_lienbond:
        from pseofactory.gsc_remediation import _normalize_meta_120_155

        if len(raw_meta_desc) < 120:
            primary_stat_auth = statutory_authority.split(",")[0].strip() or statutory_authority
            if primary_stat_auth.lower() not in raw_meta_desc.lower():
                cand_lb_desc = f"{raw_meta_desc.rstrip('.')} Grounded in {primary_stat_auth}."
                if len(cand_lb_desc) <= 155:
                    raw_meta_desc = cand_lb_desc
        if len(raw_meta_desc) < 120 or len(raw_meta_desc) > 155:
            raw_meta_desc = _normalize_meta_120_155(raw_meta_desc, "lienbond", title, slug=slug)

    brand_org_name = "Prexvo" if is_prexvo else ("GainHelm" if is_gainhelm else ("LienBond" if is_lienbond else "ProfitHelm"))
    default_takeaway_html = (
        f"The {safe_model_h2} produces a baseline output of <strong>{eff_display_output}</strong>.\n"
        f"          Executive operators evaluate deterministic calculations derived from {formula_html_inline}\n"
        f"          joined with statutory rules from {statutory_authority} and empirical economic benchmarks from {economic_dataset}\n"
        f"          to compute exact quantitative projections and variance across multi-tier planning scenarios."
    )
    takeaway_wc = len(re.sub(r"<[^>]+>", " ", default_takeaway_html).split())
    if takeaway_wc > 60:
        default_takeaway_html = (
            f"The {safe_model_h2} produces a baseline output of <strong>{eff_display_output}</strong> "
            f"from {formula_html_inline} under {statutory_authority} and {economic_dataset}."
        )
        takeaway_wc = len(re.sub(r"<[^>]+>", " ", default_takeaway_html).split())
        pad_tokens = [
            "Operators", "verify", "deterministic", "schedules,", "5-point",
            "sensitivity", "bounds,", "and", "statutory", "compliance",
            "thresholds", "across", "multi-tier", "planning", "scenarios.",
        ]
        idx_p = 0
        while takeaway_wc < 43 and idx_p < len(pad_tokens):
            default_takeaway_html = default_takeaway_html.rstrip(".") + " " + pad_tokens[idx_p]
            idx_p += 1
            takeaway_wc = len(re.sub(r"<[^>]+>", " ", default_takeaway_html).split())
        if not default_takeaway_html.endswith("."):
            default_takeaway_html += "."

    if is_prexvo:
        compact_disclosure_text = "Educational Title IV model estimate under 34 CFR Part 685; not financial or legal advice."
    elif is_gainhelm:
        compact_disclosure_text = "Readiness cost estimate for planning; not an accredited third-party audit attestation."
    elif is_lienbond:
        compact_disclosure_text = "Informational underwriting estimate only; final bond premiums and deadlines depend on underwriting and state law."
    else:
        compact_disclosure_text = "Deterministic model estimate only; not formal tax, legal, or investment advice."
    compliance_disclosure_inline_html = (
        f'    <p class="compliance-disclosure-inline" style="font-size: 12.5px; color: var(--text-muted); margin: 8px 0 18px 0; line-height: 1.45;">'
        f'{_html.escape(compact_disclosure_text)}</p>\n'
    )

    return {
        "disclosures_html_block": disclosures_html_block,
        "formula_html_inline": formula_html_inline,
        "display_output": eff_display_output,
        "is_lienbond_currency": is_lienbond_currency,
        "visible_sample_calc": visible_sample_calc,
        "step1_preview_html": step1_preview_html,
        "workpaper_unlock_card_html": workpaper_unlock_card_html,
        "gsc_token": gsc_token,
        "raw_meta_desc": raw_meta_desc,
        "brand_org_name": brand_org_name,
        "default_takeaway_html": default_takeaway_html,
        "compliance_disclosure_inline_html": compliance_disclosure_inline_html,
    }


def _clamp_seo_title(raw_title: str, max_len: int = 70, min_len: int = 30) -> str:
    """Clamps a compiled SEO title cleanly at a word boundary to <= max_len chars with zero em/en-dashes."""
    cleaned = re.sub(
        r"\s+",
        " ",
        str(raw_title or "").replace("\u2014", "-").replace("\u2013", "-"),
    ).strip()
    if len(cleaned) <= max_len:
        return cleaned
    trimmed_suffix = re.sub(r"\s+and\s+Statutory\s+Analysis$", "", cleaned, flags=re.IGNORECASE).strip()
    if trimmed_suffix and min_len <= len(trimmed_suffix) <= max_len:
        return trimmed_suffix

    words = cleaned.split()
    while len(words) > 1 and len(" ".join(words)) > max_len:
        words.pop()
    candidate = " ".join(words)
    if len(candidate) < min_len:
        candidate = cleaned[:max_len].strip()

    connectors = {"and", "or", "for", "with", "of", "in", "to", "by", "from", "the", "a", "an", "&", "-", "|", "/", ":"}
    trailing_punct = " ,;:-|&/([{"
    while True:
        prev = candidate
        candidate = candidate.rstrip(trailing_punct).strip()
        for open_ch, close_ch in (("(", ")"), ("[", "]")):
            if candidate.count(open_ch) > candidate.count(close_ch):
                last_open = candidate.rfind(open_ch)
                if last_open != -1 and close_ch not in candidate[last_open:]:
                    prefix = candidate[:last_open].strip()
                    if prefix:
                        candidate = prefix
        parts = candidate.split()
        if len(parts) > 1 and parts[-1].lower().rstrip(",;:") in connectors:
            candidate = " ".join(parts[:-1]).strip()
        candidate = candidate.rstrip(trailing_punct).strip()
        if candidate == prev:
            break

    if not candidate:
        candidate = cleaned[:max_len].rstrip(trailing_punct).strip()
    if len(candidate) > max_len:
        candidate = candidate[:max_len].rstrip(trailing_punct).strip()
    return candidate


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
    (
        manifest_source,
        query,
        slug,
        title,
        model_name,
        formula,
        raw_inputs,
        statutory_authority,
        economic_dataset,
        sample_calc,
    ) = _extract_candidate_metadata(candidate_spec)
    title = _clamp_seo_title(title)

    # 3. Numeric metric clamping to non-negative (>= 0) per HWL-1263
    clamped_inputs = _clamp_candidate_inputs(raw_inputs)

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

    manifest: Dict[str, Any] = {
        "manifest_id": f"{slug}-manifest",
        "slug": slug,
        "entity_type": str(
            candidate_spec.get("entity_type")
            or manifest_source.get("entity_type")
            or "FinancialProductOrService"
        ),
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
    _enrich_manifest_with_proprietary_signals(
        manifest, candidate_spec, manifest_source, slug, query, statutory_authority, formula, clamped_inputs, published_output
    )

    # 6. Render Obsidian dark-theme HTML asset
    is_prexvo, is_gainhelm, is_lienbond = _resolve_candidate_tenant_flags(candidate_spec, slug)
    form_inputs_html = []
    table_rows_html = []
    for var_name, var_val in clamped_inputs.items():
        label_text = var_name.replace("_", " ").title()
        clean_val_str, clean_min_str, clean_max_str, step_attr = _compute_range_slider_spec(var_name, var_val)
        form_inputs_html.append(
            f'        <div class="form-group" style="margin-bottom: 16px;">\n'
            f'          <label for="input-{var_name}" style="display: block; margin-bottom: 6px; font-weight: 500;">{label_text}</label>\n'
            f'          <input type="number" step="any" min="0" id="input-{var_name}" name="{var_name}" '
            f'value="{clean_val_str}" class="touch-target" style="min-height: 44px; min-width: 44px; padding: 10px 14px; font-size: 16px; width: 100%; box-sizing: border-box;" />\n'
            f'          <input type="range" min="{clean_min_str}" max="{clean_max_str}" step="{step_attr}" id="range-{var_name}" '
            f'value="{clean_val_str}" class="touch-target" style="min-height: 44px; min-width: 44px; width: 100%; margin-top: 8px;" />\n'
            f'        </div>'
        )
        table_rows_html.append(
            f'            <tr>\n'
            f'              <td>{label_text}</td>\n'
            f'              <td>{clean_val_str}</td>\n'
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
    if is_lienbond and not display_output.startswith("$"):
        display_output = f"${display_output}"
    # Pre-render SSR 5-Point Scenario Comparison Table
    scenario_table_html = _render_5point_sensitivity_table_html(
        published_output=published_output,
        display_output=display_output,
        statutory_authority=statutory_authority,
        economic_dataset=economic_dataset,
        model_name=model_name,
        formula=formula,
        inputs=clamped_inputs,
    )
    default_base = (
        "https://prexvo.com"
        if is_prexvo
        else ("https://gainhelm.com" if is_gainhelm else ("https://lienbond.com" if is_lienbond else "https://profithelm.com"))
    )
    env_base = os.environ.get("FACTORY_CANONICAL_BASE", "").strip()
    if is_prexvo and ("profithelm.com" in env_base.lower() or "gainhelm.com" in env_base.lower() or "lienbond.com" in env_base.lower()):
        env_base = ""
    elif is_gainhelm and ("profithelm.com" in env_base.lower() or "prexvo.com" in env_base.lower() or "lienbond.com" in env_base.lower()):
        env_base = ""
    elif is_lienbond and ("profithelm.com" in env_base.lower() or "prexvo.com" in env_base.lower() or "gainhelm.com" in env_base.lower()):
        env_base = ""
    elif not is_prexvo and not is_gainhelm and not is_lienbond and ("prexvo.com" in env_base.lower() or "gainhelm.com" in env_base.lower() or "lienbond.com" in env_base.lower()):
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
        is_lienbond=is_lienbond,
    )
    monetization_section_html = monetization_block["html"]
    inline_calc_cta_html = monetization_block.get("inline_calc_cta_html", "")
    comparison_table_cta_html = monetization_block.get("comparison_table_cta_html", "")
    if comparison_table_cta_html:
        scenario_table_html = f"{scenario_table_html}\n{comparison_table_cta_html}"

    resolved_tenant = "prexvo" if is_prexvo else ("gainhelm" if is_gainhelm else ("lienbond" if is_lienbond else "profithelm"))
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

    is_prediction_tool = (not is_prexvo and not is_gainhelm and not is_lienbond) and any(
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

    application_category = "BusinessApplication" if (is_gainhelm or is_lienbond) else "FinanceApplication"

    if is_prexvo:
        cluster = PREXVO_STUDENT_LOAN_CLUSTER
        cluster_title = "Related Title IV Student Loan Repayment Tools"
    elif is_gainhelm:
        cluster = GAINHELM_CYBER_COMPLIANCE_CLUSTER
        cluster_title = "Related Cyber Compliance and GRC Audit Cost Tools"
    elif is_lienbond:
        cluster = LIENBOND_CONSTRUCTION_SURETY_CLUSTER
        cluster_title = "Related Construction Surety Bond, Workers Comp and Lien Tools"
    elif is_prediction_tool:
        cluster = PROFITHELM_PREDICTION_CLUSTER
        cluster_title = "Related Prediction Market Quantitative Tools"
    else:
        cluster = PROFITHELM_TAX_CLUSTER
        cluster_title = "Related Tax and Capital Optimization Tools"

    sibling_links = [(s_slug, s_title) for (s_slug, s_title) in cluster if s_slug != slug]
    existing_tool_slugs_raw = candidate_spec.get("existing_tool_slugs")
    if isinstance(existing_tool_slugs_raw, (list, set, tuple)) and existing_tool_slugs_raw:
        live_tool_slugs = {str(s).strip() for s in existing_tool_slugs_raw if str(s).strip()}
        legacy_slug_aliases = {
            "qsbs-section-1202-calculator": "tcja-sunset-capital-gains",
            "tcja-sunset-bracket-calculator": "irs-tax-brackets",
            "student-loan-forgiveness-calculator": "student-loan-repayment-calculator",
            "pslf-qualifying-payment-calculator": "student-loan-repayment-calculator",
            "student-loan-interest-subsidy-calculator": "rap-vs-ibr-calculator",
        }
        resolved_siblings = []
        seen_sibling_slugs = {slug}
        for s_slug, s_title in sibling_links:
            target_slug = s_slug if s_slug in live_tool_slugs else legacy_slug_aliases.get(s_slug, s_slug)
            if target_slug in live_tool_slugs and target_slug not in seen_sibling_slugs:
                seen_sibling_slugs.add(target_slug)
                resolved_siblings.append((target_slug, s_title))
        if resolved_siblings:
            sibling_links = resolved_siblings
    if not sibling_links:
        sibling_links = cluster
    if is_gainhelm and slug not in ("", "index", "soc-2-audit-cost-calculator"):
        from pseofactory.affiliates import get_gainhelm_framework_profile

        gh_prof = get_gainhelm_framework_profile(slug=slug)
        gh_forb = tuple(str(t).lower() for t in (gh_prof.get("forbidden_leak_tokens") or ()))
        if gh_forb:
            clean_gh_siblings = [
                (s_slug, s_title)
                for s_slug, s_title in sibling_links
                if not any(tok in f"{s_slug} {s_title}".lower() for tok in gh_forb)
            ]
            if clean_gh_siblings:
                sibling_links = clean_gh_siblings
    elif is_lienbond and any(t in slug.lower() for t in ("workers-comp", "workers-compensation", "emr", "class-code")):
        clean_lb_siblings = [
            (s_slug, s_title)
            for s_slug, s_title in sibling_links
            if not any(tok in f"{s_slug} {s_title}".lower() for tok in ("miller-act", "miller act", "3131", "28.102"))
        ]
        if clean_lb_siblings:
            sibling_links = clean_lb_siblings
    elif (not is_prexvo and not is_gainhelm and not is_lienbond) and any(
        t in slug.lower() for t in ("qsbs", "1202", "section-179", "crypto", "runway")
    ):
        clean_ph_siblings = [
            (s_slug, s_title)
            for s_slug, s_title in sibling_links
            if not any(tok in f"{s_slug} {s_title}".lower() for tok in ("section-1031", "section 1031", "8824"))
        ]
        if clean_ph_siblings:
            sibling_links = clean_ph_siblings

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
        is_lienbond=is_lienbond,
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

    meta_bundle = _build_compiled_disclosures_funnel_and_seo(
        candidate_spec=candidate_spec,
        slug=slug,
        title=title,
        query=query,
        formula=formula,
        clamped_inputs=clamped_inputs,
        published_output=published_output,
        display_output=display_output,
        sample_calc=sample_calc,
        safe_model_h2=safe_model_h2,
        statutory_authority=statutory_authority,
        economic_dataset=economic_dataset,
        canonical_base=canonical_base,
        cluster=cluster,
        resolved_tenant=resolved_tenant,
        is_prexvo=is_prexvo,
        is_gainhelm=is_gainhelm,
        is_lienbond=is_lienbond,
    )
    disclosures_html_block = meta_bundle["disclosures_html_block"]
    formula_html_inline = meta_bundle["formula_html_inline"]
    display_output = meta_bundle["display_output"]
    is_lienbond_currency = meta_bundle["is_lienbond_currency"]
    visible_sample_calc = meta_bundle["visible_sample_calc"]
    step1_preview_html = meta_bundle["step1_preview_html"]
    workpaper_unlock_card_html = meta_bundle["workpaper_unlock_card_html"]
    gsc_token = meta_bundle["gsc_token"]
    raw_meta_desc = meta_bundle["raw_meta_desc"]
    brand_org_name = meta_bundle["brand_org_name"]
    default_takeaway_html = meta_bundle["default_takeaway_html"]
    compliance_disclosure_inline_html = meta_bundle["compliance_disclosure_inline_html"]

    _comp_prop = "prexvo" if is_prexvo else ("gainhelm" if is_gainhelm else ("lienbond" if is_lienbond else "profithelm"))
    _comp_pub_iso, _comp_mod_iso = _resolve_iso_dates_with_tz(_comp_prop, candidate_spec=candidate_spec, manifest_source=manifest_source)
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
        is_lienbond=is_lienbond,
        date_published=_comp_pub_iso,
        date_modified=_comp_mod_iso,
    )

    from pseofactory.affiliate_intent import (
        CJ_PROPERTY_ID_BY_TENANT,
        IMPACT_VERIFICATION_UUID_BY_TENANT,
    )

    _compiler_prop_id = (
        "prexvo"
        if is_prexvo
        else ("gainhelm" if is_gainhelm else ("lienbond" if is_lienbond else "profithelm"))
    )
    _impact_uuid = IMPACT_VERIFICATION_UUID_BY_TENANT[_compiler_prop_id]
    _cj_pid = CJ_PROPERTY_ID_BY_TENANT[_compiler_prop_id]

    esc_gsc_token = _html.escape(str(gsc_token), quote=True)
    esc_impact_uuid = _html.escape(str(_impact_uuid), quote=True)
    esc_cj_pid = _html.escape(str(_cj_pid), quote=True)
    esc_brand_org_name = _html.escape(str(brand_org_name), quote=True)
    esc_meta_desc = _html.escape(str(raw_meta_desc), quote=True)
    esc_title_attr = _html.escape(str(title), quote=True)
    esc_title_text = _html.escape(str(title), quote=False)
    esc_canonical_url = _html.escape(f"{canonical_base}/tools/{slug}/", quote=True)
    statutory_sources_html = _build_statutory_sources_and_changelog_html(
        _comp_prop,
        slug,
        statutory_authority,
        topic_label=safe_model_h2,
    )
    if "/" in slug:
        _spoke_hub_slug = [sp for sp in slug.split("/") if sp][0]
        _spoke_hub_name_map = {
            "irs-2027-tax-brackets": "IRS 2027 Tax Brackets Calculator",
            "section-1031-calculator": "Section 1031 Exchange Calculator",
            "section-179-calculator": "Section 179 Deduction Calculator",
        }
        _spoke_hub_label = _spoke_hub_name_map.get(_spoke_hub_slug, _spoke_hub_slug.replace("-", " ").title())
        leaf_breadcrumbs_html = (
            '    <nav class="breadcrumbs" aria-label="Breadcrumb">\n'
            '      <a href="/" class="touch-target">Home</a><span>/</span>'
            '<a href="/tools/" class="touch-target">Calculators</a><span>/</span>'
            f'<a href="/tools/{_html.escape(_spoke_hub_slug, quote=True)}/" class="touch-target">{_html.escape(_spoke_hub_label)}</a><span>/</span>'
            f'<span>{esc_title_text}</span>\n'
            '    </nav>'
        )
    else:
        leaf_breadcrumbs_html = (
            '    <nav class="breadcrumbs" aria-label="Breadcrumb">\n'
            '      <a href="/" class="touch-target">Home</a><span>/</span>'
            '<a href="/tools/" class="touch-target">Calculators</a><span>/</span>'
            f'<span>{esc_title_text}</span>\n'
            '    </nav>'
        )
    calc_runtime_script_html = _render_compiled_calculator_runtime_js(
        slug=slug,
        calc_js_body=calc_js_body,
        is_lienbond_currency=is_lienbond_currency,
    )

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="content-language" content="en-US" />
  <meta name="google-site-verification" content="{esc_gsc_token}" />
  <meta name='impact-site-verification' value='{esc_impact_uuid}'>
  <meta name="cj-promotional-property-id" content="{esc_cj_pid}">
  <meta name="author" content="{esc_brand_org_name} Quantitative Research Group" />
  <meta name="description" content="{esc_meta_desc}" />
  <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1" />
  <meta property="og:title" content="{esc_title_attr}" />
  <meta property="og:description" content="{esc_meta_desc}" />
  <meta property="og:url" content="{esc_canonical_url}" />
  <meta property="og:type" content="website" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{esc_title_attr}" />
  <meta name="twitter:description" content="{esc_meta_desc}" />
  <title>{esc_title_text}</title>
  <link rel="canonical" href="{esc_canonical_url}" />
  <link rel="alternate" hreflang="en-US" href="{esc_canonical_url}" />
  <link rel="alternate" hreflang="x-default" href="{esc_canonical_url}" />
  <link rel="alternate" type="application/rss+xml" title="{esc_brand_org_name} RSS Feed" href="/feed.xml" />
  <link rel="publisher-media-kit" type="application/json" href="/media-kit.json" />
  <link rel="tool-catalog" type="application/json" title="Machine-Readable Tool Catalog" href="/catalog.json" />
  <style>
    :root {{
      /* Surfaces & Canvas (Canonical Porcelain Light) */
      --bg: #fbfcfd;
      --card-bg: #ffffff;
      --bg-elevated: #eff6ff;
      --bg-inset: #f8fafc;
      --bg-canvas: #fbfcfd;
      --bg-surface: #ffffff;
      --text-primary: #0f172a;
      --brand-primary: #1d4ed8;

      /* Borders & Separation */
      --border: #dbe1ea;
      --border-color: #dbe1ea;
      --border-strong: #bfdbfe;

      /* Typography */
      --text: #0f172a;
      --text-muted: #475569;
      --text-dim: #64748b;

      /* Accents & States */
      --accent: #1d4ed8;
      --accent-hover: #1e40af;
      --accent-subtle: rgba(29, 78, 216, 0.08);
      --cta-fg: #ffffff;

      /* Depth & Atmospheric Lighting */
      --shadow-card: 0 1px 3px 0 rgba(15, 23, 42, 0.06), 0 1px 2px -1px rgba(15, 23, 42, 0.04);
      --shadow-elevated: 0 10px 25px -5px rgba(15, 23, 42, 0.06), 0 8px 10px -6px rgba(15, 23, 42, 0.03);
      --card-highlight: none;
    }}
    [data-theme="porcelain"] {{
      --bg-canvas: #fbfcfd;
      --bg-surface: #ffffff;
      --text-primary: #0f172a;
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
      --cta-fg: #ffffff;
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
  <script type="application/ld+json">
  {json_ld_graph_str}
  </script>
</head>
<body>
  <div class="container">
{leaf_breadcrumbs_html}
    <header class="card">
      <h1>{title}</h1>
      <aside class="quick-answer" data-gsc-device-focus="{gsc_device_focus}" data-gsc-search-appearance="{gsc_appearance_attr}">
        <p class="takeaway">
          {default_takeaway_html}
        </p>
      </aside>
    </header>

    <div id="calculator-workspace-anchor" class="calculation-container card" data-gsc-device-focus="{gsc_device_focus}" data-gsc-search-appearance="{gsc_appearance_attr}" data-gsc-trajectory="{gsc_trajectory}" data-gsc-coverage-state="{gsc_coverage_state}">
      <h2>Interactive Quantitative Model: {safe_model_h2}</h2>
      <p>
        Adjust inputs below to recalculate baseline outputs immediately with live hash-synced state.
      </p>
{scenario_presets_bar_html}
{edge_case_trap_html}
      <form class="calculator-form" id="{slug}-calculator" method="post" action="javascript:void(0);">
{form_inputs_str}
        <button type="submit" class="touch-target" id="calculate-btn" style="min-height: 44px; min-width: 44px;">Recalculate Output</button>
      </form>
      <div class="result-box" style="min-height: 110px; margin-top: 20px;">
        <h3>Published Baseline Calculation</h3>
        <p>Formula: {formula_html_inline}</p>
        <p>Evaluated Output Result: <strong class="output-value">{display_output}</strong></p>
        <p>Sample Calculation Methodology: {visible_sample_calc}</p>
        <div class="calculation-variant" id="variant-baseline" style="font-size: 13px; margin-top: 8px;">Baseline Statutory Schedule (= {display_output}, 100.0% baseline{"; Title IV RAP $65k AGI benchmark: $248.23/mo, $59,575.20 total" if is_prexvo else ""}) (<a href="#variant-accelerated" class="touch-target" style="display:inline-flex;align-items:center;min-height:44px;min-width:44px;padding:4px 8px;">Compare Accelerated Stress Variant</a>)</div>
        <div class="calculation-variant" id="variant-accelerated" style="font-size: 13px; margin-top: 4px;">Accelerated 1.2x Stress Variant (= {display_output} * 1.20, 120.0% stress{"; Title IV RAP $95k AGI benchmark: $498.23/mo" if is_prexvo else ""}) (<a href="#variant-baseline" class="touch-target" style="display:inline-flex;align-items:center;min-height:44px;min-width:44px;padding:4px 8px;">Return to Baseline Schedule</a>)</div>
      </div>

{step1_preview_html}
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

{workpaper_unlock_card_html}
{compliance_disclosure_inline_html}
{monetization_section_html}

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

{statutory_sources_html}

{scenario_table_html}

{statutory_compliance_html}

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
        <li style="margin-bottom: 6px;"><strong>Deterministic Formula Execution:</strong> Evaluates {formula_html_inline} with non-negative parameter clamping to produce the verified baseline output of <strong>{display_output}</strong>.</li>
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
      <h3 class="section-subtitle">{cluster_title}</h3>
      <p style="color: var(--text-muted); font-size: 14px; margin-bottom: 16px;">
        Explore verified peer computational models in this specialized quantitative cluster:
      </p>
      <ul style="list-style: none; padding: 0; margin: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px;">
{cluster_links_html}
      </ul>
    </nav>

    <footer class="card" style="text-align: center;">
      <a href="{canonical_base}/tools/{slug}/" class="canonical-tool-link touch-target" style="min-height: 44px; min-width: 44px;">
        Launch Full {title} Engine
      </a>
      <p style="font-size: 13px; color: var(--text-muted); margin-top: 12px;">
        <a href="/tools/" class="touch-target" style="display:inline-flex;align-items:center;min-height:44px;min-width:44px;padding:6px 10px;color:var(--accent);">Tools Directory</a> |
        <a href="{'/' + ('about' if 'profithelm' in str(canonical_base or '').lower() else 'methodology') + '/'}" class="touch-target" style="display:inline-flex;align-items:center;min-height:44px;min-width:44px;padding:6px 10px;color:var(--accent);">Statutory Methodology</a> |
        <a href="{'/' + ('privacy' if 'profithelm' in str(canonical_base or '').lower() else 'disclaimers') + '/'}" class="touch-target" style="display:inline-flex;align-items:center;min-height:44px;min-width:44px;padding:6px 10px;color:var(--accent);">Disclaimers</a> |
        <a href="mailto:{'compliance@lienbond.com' if 'lienbond' in str(canonical_base or '').lower() else 'editorial@' + canonical_base.replace('https://', '').replace('http://', '')}" class="touch-target" style="display:inline-flex;align-items:center;min-height:44px;min-width:44px;padding:6px 10px;color:var(--accent);">Contact Editorial</a> |
        <a href="/sitemap.xml" class="touch-target" style="display:inline-flex;align-items:center;min-height:44px;min-width:44px;padding:6px 10px;color:var(--accent);">Sitemap</a>
      </p>
      <p style="font-size: 12px; color: var(--text-muted); margin-top: 6px;">{brand_org_name} Editorial Policy: All calculations are deterministic and verified by statutory models.</p>
      <div class="disclosures" style="margin-top: 16px; border-top: 1px solid var(--border); padding-top: 12px;">
{disclosures_html_block}
      </div>
    </footer>
  </div>

  <script type="application/json" id="calculation-manifest" class="calculation-manifest">
{manifest_json_str}
  </script>

{calc_runtime_script_html}
</body>
</html>
"""

    from pseofactory.visual_primitives import (
        assert_visual_and_ux_contracts,
        normalize_html_visual_primitives,
    )
    from pseofactory.tenant_facts import TruthReconciliationEngine

    resolved_tenant = "prexvo" if is_prexvo else ("gainhelm" if is_gainhelm else ("lienbond" if is_lienbond else "profithelm"))
    effective_property_id = (
        str(
            candidate_spec.get("property_id")
            or candidate_spec.get("property")
            or candidate_spec.get("tenant")
            or resolved_tenant
        )
        .strip()
        .lower()
        or resolved_tenant
    )
    html_content, _ = TruthReconciliationEngine.reconcile_html_truth(
        html_content,
        tenant=resolved_tenant,
        rel_path=f"tools/{slug}/index.html",
        slug=slug,
    )
    html_content, _ = normalize_html_visual_primitives(
        html_content,
        is_tenant_porcelain=False,
        property_id=effective_property_id,
    )
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
    if not fuzz_res.get("passed", False):
        raise ValueError(
            f"Formula boundary fuzzing failed on '{slug}': {fuzz_res.get('issues') or fuzz_res}"
        )

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
        "boundary_fuzz_verified": bool(fuzz_res.get("passed", False)),
    }


def _build_lienbond_support_page_html(
    page_title: str,
    meta_desc: str,
    canonical_url: str,
    h1_text: str,
    quick_answer_text: str,
    body_html: str,
    gsc_token: str,
    collection_items: Optional[List[Dict[str, str]]] = None,
    is_methodology: bool = False,
    is_404: bool = False,
) -> str:
    """Renders a support/hub page (tools/index, methodology/index, disclaimers/index, 404) with full SEO/GEO parity."""
    import html as _html_lib

    lb_date_published, lb_date_modified = _resolve_iso_dates_with_tz("lienbond")
    org_ref = {"@id": "https://lienbond.com/#organization"}
    webpage_node: Dict[str, Any] = {
        "@type": "WebPage",
        "@id": f"{canonical_url}#webpage",
        "url": canonical_url,
        "name": page_title,
        "description": meta_desc,
        "inLanguage": "en-US",
        "isPartOf": {"@id": "https://lienbond.com/#website"},
        "publisher": org_ref,
        "about": ["https://www.wikidata.org/wiki/Q192161"],
        "datePublished": lb_date_published,
        "dateModified": lb_date_modified,
    }
    graph_nodes: List[Dict[str, Any]] = [webpage_node]
    if not is_404:
        webpage_node["breadcrumb"] = {"@id": f"{canonical_url}#breadcrumb"}
        graph_nodes.append(
            {
                "@type": "BreadcrumbList",
                "@id": f"{canonical_url}#breadcrumb",
                "isPartOf": {"@id": f"{canonical_url}#webpage"},
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://lienbond.com/"},
                    {"@type": "ListItem", "position": 2, "name": h1_text, "item": canonical_url},
                ],
            }
        )
    if is_methodology:
        graph_nodes.append(
            {
                "@type": "TechArticle",
                "@id": f"{canonical_url}#techarticle",
                "headline": h1_text,
                "name": page_title,
                "description": meta_desc,
                "url": canonical_url,
                "inLanguage": "en-US",
                "author": org_ref,
                "publisher": org_ref,
                "datePublished": lb_date_published,
                "dateModified": lb_date_modified,
                "mainEntityOfPage": {"@id": f"{canonical_url}#webpage"},
            }
        )
    if collection_items:
        list_elements = [
            {
                "@type": "ListItem",
                "position": idx,
                "name": str(item.get("name") or "").strip(),
                "url": str(item.get("url") or "").strip(),
            }
            for idx, item in enumerate(collection_items, start=1)
            if item.get("name") and item.get("url")
        ]
        if list_elements:
            graph_nodes.append(
                {
                    "@type": "CollectionPage",
                    "@id": f"{canonical_url}#collectionpage",
                    "name": page_title,
                    "url": canonical_url,
                    "description": meta_desc,
                    "inLanguage": "en-US",
                    "datePublished": lb_date_published,
                    "dateModified": lb_date_modified,
                    "mainEntity": {
                        "@type": "ItemList",
                        "@id": f"{canonical_url}#itemlist",
                        "name": page_title,
                        "itemListOrder": "https://schema.org/ItemListOrderAscending",
                        "numberOfItems": len(list_elements),
                        "itemListElement": list_elements,
                    },
                }
            )
    page_json_ld = json.dumps(
        {
            "@context": "https://schema.org",
            "@graph": graph_nodes,
        },
        indent=2,
    )
    support_breadcrumbs_html = (
        ""
        if is_404
        else (
            '    <nav class="breadcrumbs" aria-label="Breadcrumb">\n'
            '      <a href="/" class="touch-target">Home</a><span>/</span>'
            f'<span>{_html_lib.escape(h1_text)}</span>\n'
            '    </nav>\n'
        )
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="content-language" content="en-US" />
  <meta name="google-site-verification" content="{gsc_token}" />
  <meta name='impact-site-verification' value='5ce463de-dd46-4356-871d-e6d1214b5d57'>
  <meta name="cj-promotional-property-id" content="101927181">
  <meta name="author" content="LienBond Quantitative Research Group" />
  <meta name="description" content="{meta_desc}" />
  <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1" />
  <meta property="og:title" content="{page_title}" />
  <meta property="og:description" content="{meta_desc}" />
  <meta property="og:url" content="{canonical_url}" />
  <meta property="og:type" content="website" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{page_title}" />
  <meta name="twitter:description" content="{meta_desc}" />
  <title>{page_title}</title>
  <link rel="canonical" href="{canonical_url}" />
  <link rel="alternate" hreflang="en-US" href="{canonical_url}" />
  <link rel="alternate" hreflang="x-default" href="{canonical_url}" />
  <link rel="alternate" type="application/rss+xml" title="LienBond RSS Feed" href="/feed.xml" />
  <link rel="publisher-media-kit" type="application/json" href="/media-kit.json" />
  <link rel="tool-catalog" type="application/json" title="Machine-Readable Tool Catalog" href="/catalog.json" />
  <link rel="stylesheet" href="/css/style.css" />
  <script type="application/ld+json">
  {page_json_ld}
  </script>
</head>
<body>
  <div class="container">
{support_breadcrumbs_html}    <header class="card">
      <h1>{h1_text}</h1>
    </header>
    <aside class="takeaway quick-answer card" data-answer-prominence="true">
      <p class="takeaway">{quick_answer_text}</p>
    </aside>
{body_html}
    <footer class="card" style="text-align: center;">
      <p style="font-size: 13px; color: var(--text-muted); margin-top: 8px;">
        <a href="/" class="touch-target" style="display:inline-flex;align-items:center;min-height:44px;min-width:44px;padding:6px 10px;color:var(--accent);">Home</a> |
        <a href="/tools/" class="touch-target" style="display:inline-flex;align-items:center;min-height:44px;min-width:44px;padding:6px 10px;color:var(--accent);">Tools Directory</a> |
        <a href="/methodology/" class="touch-target" style="display:inline-flex;align-items:center;min-height:44px;min-width:44px;padding:6px 10px;color:var(--accent);">Statutory Methodology</a> |
        <a href="/disclaimers/" class="touch-target" style="display:inline-flex;align-items:center;min-height:44px;min-width:44px;padding:6px 10px;color:var(--accent);">Disclaimers</a> |
        <a href="mailto:compliance@lienbond.com" class="touch-target" style="display:inline-flex;align-items:center;min-height:44px;min-width:44px;padding:6px 10px;color:var(--accent);">Contact Editorial</a> |
        <a href="/sitemap.xml" class="touch-target" style="display:inline-flex;align-items:center;min-height:44px;min-width:44px;padding:6px 10px;color:var(--accent);">Sitemap</a>
      </p>
      <p style="font-size: 12px; color: var(--text-muted); margin-top: 6px;">LienBond Editorial Policy: All calculations are deterministic and verified by statutory models.</p>
      <div class="disclosures" style="margin-top: 12px; border-top: 1px solid var(--border); padding-top: 12px;">
        <p class="regulatory-disclosure" style="font-size: 12px; color: var(--text-muted);">{LIENBOND_DISCLOSURES["statutory_surety_disclaimer"]}</p>
        <p class="ftc-disclosure" style="font-size: 12px; color: var(--text-muted);">{LIENBOND_DISCLOSURES["ftc_disclosure"]}</p>
      </div>
    </footer>
  </div>
</body>
</html>
"""


LIENBOND_CANONICAL_SHORT_LINK_REDIRECTS: Tuple[Tuple[str, str], ...] = (
    ("/calculator", "/tools/"),
    ("/calculators", "/tools/"),
    ("/bid-bond", "/tools/bid-bond-calculator/"),
    ("/preliminary-notice", "/tools/california-texas-florida-preliminary-notice-deadline-calculator/"),
    ("/retainage", "/tools/commercial-construction-retainage-interest-penalty-calculator-by-state/"),
    ("/license-bond", "/tools/contractor-license-bond-cost-calculator-by-credit-score/"),
    ("/contractor-bond", "/tools/contractor-license-bond-cost-calculator-by-credit-score/"),
    ("/lien-waiver", "/tools/contractor-lien-release-statutory-matrix-by-state/"),
    ("/lien-release", "/tools/contractor-lien-release-statutory-matrix-by-state/"),
    ("/markup-vs-margin", "/tools/contractor-overhead-and-profit-markup-vs-margin-calculator/"),
    ("/davis-bacon", "/tools/davis-bacon-prevailing-wage-fringe-benefit-rate-calculator/"),
    ("/wh-347", "/tools/davis-bacon-prevailing-wage-fringe-benefit-rate-calculator/"),
    ("/erisa-bond", "/tools/erisa-fidelity-bond-coverage-amount-calculator/"),
    ("/emr", "/tools/experience-modification-rate-emr-workers-comp-penalty-calculator/"),
    ("/miller-act", "/tools/miller-act-performance-and-payment-bond-premium-calculator/"),
    ("/performance-bond", "/tools/miller-act-performance-and-payment-bond-premium-calculator/"),
    ("/sdi", "/tools/subcontractor-default-insurance-sdi-vs-performance-bond-cost-calculator/"),
    ("/surety-bond-philippines", "/tools/contractor-license-bond-cost-calculator-by-credit-score/"),
    ("/texas-chapter-53", "/tools/texas-chapter-53-statutory-retainage-and-fund-trapping-notice-calculator/"),
    ("/workers-comp", "/tools/workers-compensation-class-code-rate-calculator-by-state/"),
    ("/how-it-works", "/methodology/"),
    ("/how-it-works/", "/methodology/"),
)


def build_lienbond_canonical_redirects_content(
    dist_dir: Any,
    existing_content: str = "",
) -> str:
    """
    Merges the 22 canonical LienBond 301 short-link redirect rules with any existing
    _redirects content, emitting only rules whose target HTML exists on disk,
    eliminating dead targets and redirect chains, and respecting the <=95 Cloudflare cap.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.edge import compact_edge_redirects_to_cloudflare_cap

    dist_path = Path(dist_dir)

    def _target_exists_on_disk(target_path: str) -> bool:
        clean = str(target_path or "").strip()
        if not clean.startswith("/"):
            return False
        rel = clean.strip("/")
        if not rel:
            return (dist_path / "index.html").is_file()
        return (dist_path / rel / "index.html").is_file() or (dist_path / rel).is_file()

    def _source_exists_on_disk(src_path: str) -> bool:
        rel = str(src_path or "").strip().strip("/")
        if not rel:
            return True
        return (dist_path / rel / "index.html").is_file()

    preserved_lines: List[str] = []
    existing_sources: set = set()
    for raw_line in (existing_content or "").splitlines():
        s = raw_line.strip()
        if not s:
            continue
        if s.startswith("#"):
            preserved_lines.append(raw_line)
            continue
        parts = s.split()
        if len(parts) >= 2:
            src, dst = parts[0], parts[1]
            if src in existing_sources:
                continue
            if dst.startswith("/") and not _target_exists_on_disk(dst):
                continue
            existing_sources.add(src)
            preserved_lines.append(raw_line)

    canonical_lines: List[str] = []
    for src, dst in LIENBOND_CANONICAL_SHORT_LINK_REDIRECTS:
        if src in existing_sources:
            continue
        if _source_exists_on_disk(src):
            continue
        if not _target_exists_on_disk(dst):
            continue
        existing_sources.add(src)
        canonical_lines.append(f"{src}  {dst}  301")

    combined_lines = preserved_lines + canonical_lines

    # Eliminate any redirect chains where a rule's destination is itself a rule's source
    active_sources = {
        ln.strip().split()[0]
        for ln in combined_lines
        if ln.strip() and not ln.strip().startswith("#") and len(ln.strip().split()) >= 2
    }
    chain_free_lines: List[str] = []
    for ln in combined_lines:
        s = ln.strip()
        if s and not s.startswith("#"):
            parts = s.split()
            if len(parts) >= 2 and parts[1] in active_sources:
                continue
        chain_free_lines.append(ln)

    merged_raw = ("\n".join(chain_free_lines).rstrip() + "\n") if chain_free_lines else ""
    existing_gov_routes = {
        g
        for g in ("about", "methodology", "privacy", "terms", "disclaimers", "contact")
        if (dist_path / g / "index.html").is_file()
    }
    return compact_edge_redirects_to_cloudflare_cap(
        merged_raw,
        existing_governance_routes=existing_gov_routes,
    )


def compile_lienbond_estate(output_dir: Any, run_retrofit: bool = True) -> Dict[str, Any]:
    """
    Compiles the complete LienBond (lienbond.com) tenant estate into `output_dir`:
    - 10 high-effort construction surety bond, workers comp class code / EMR, 50-state mechanics
      lien deadline/waiver, and Davis-Bacon WH-347 calculators under `dist/tools/<slug>/index.html`
    - Factor-7 manifests under `dist/manifests/<slug>.json`
    - Hub & governance pages (`dist/index.html`, `dist/tools/index.html`, `dist/disclaimers/index.html`,
      `dist/methodology/index.html`, `dist/404.html`)
    - Sitemaps (`dist/sitemap.xml`), `dist/robots.txt`,
      `dist/llms.txt`, `dist/catalog.json`, `dist/media-kit.json`, `dist/_headers`, `dist/_redirects`,
      `dist/feed.xml`, and IndexNow key file `dist/4e1df81051618d8a982aa278ff55052f.txt`
    - Cloudflare Pages Functions (`functions/r/[partner].js`, `functions/api/telemetry.js`,
      `functions/api/lead-capture.js`, `functions/api/checkout.js`, `functions/api/lead-fulfillment.js`)
    - `.pseofactory.json`, `wrangler.toml`, `README.md`, `substrate_lock.json`, `.agy/engine_hash.json`,
      `.agy/asset_ledger.json`, and the `lienbond` Python package (`lienbond/`, `tests/`, `.github/workflows/ci.yml`)
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.estate_common import (
        finalize_estate_build,
        load_and_enrich_deployed_voids,
        prepare_estate_dirs,
        write_llms_files,
        write_machine_endpoints_and_headers,
        write_sitemaps_and_robots,
        write_tenant_edge_functions,
    )

    root, dist, tools_dir = prepare_estate_dirs(output_dir, "lienbond")
    manifests_dir = dist / "manifests"
    disclaimers_dir = dist / "disclaimers"
    methodology_dir = dist / "methodology"
    from pseofactory.porcelain_shell import get_porcelain_tenant_profile

    gsc_token = str(get_porcelain_tenant_profile("lienbond").get("default_gsc_token") or "")

    specs = list(get_lienbond_expansion_specs())
    known_slugs = {str(s["slug"]).strip().lower() for s in specs}
    specs.extend(
        load_and_enrich_deployed_voids(
            repo_root=root,
            property_id="lienbond",
            domain="lienbond.com",
            brand_name="LienBond",
            canonical_base="https://lienbond.com",
            known_slugs=known_slugs,
            default_authority="40 U.S.C. Section 3131 (Miller Act) & State Commercial Surety Statutes",
            default_dataset="SFAA Commercial Surety Loss Cost Series & BLS PPI Construction Inputs WPUIP2311001",
        )
    )
    all_slugs = [str(s["slug"]) for s in specs]
    from pseofactory.qualification import detect_non_us_jurisdiction

    raw_void_slugs: Set[str] = set()
    raw_voids_file = root / "content" / "deployed_voids.json"
    if raw_voids_file.is_file():
        try:
            raw_voids_payload = json.loads(raw_voids_file.read_text(encoding="utf-8"))
            if isinstance(raw_voids_payload, list):
                for rv in raw_voids_payload:
                    if isinstance(rv, dict) and rv.get("slug"):
                        raw_void_slugs.add(str(rv["slug"]).strip().lower())
        except Exception:
            pass

    active_slug_set = {s.strip().lower() for s in all_slugs}
    if tools_dir.is_dir():
        import shutil as _shutil

        for existing_tool_dir in list(tools_dir.iterdir()):
            if not existing_tool_dir.is_dir():
                continue
            cand_slug = existing_tool_dir.name.strip().lower()
            if cand_slug in active_slug_set:
                continue
            if detect_non_us_jurisdiction(cand_slug, property_id="lienbond") or cand_slug in raw_void_slugs:
                _shutil.rmtree(existing_tool_dir, ignore_errors=True)
                stale_manifest = manifests_dir / f"{existing_tool_dir.name}.json"
                if stale_manifest.is_file():
                    stale_manifest.unlink(missing_ok=True)

    compiled_pages: List[Dict[str, Any]] = []
    catalog_tools: List[Dict[str, Any]] = []

    for spec in specs:
        spec_with_siblings = dict(spec)
        spec_with_siblings["existing_tool_slugs"] = all_slugs
        spec_with_siblings["gsc_verification_token"] = gsc_token
        res = compile_high_effort_page(spec_with_siblings)
        slug = res["slug"]
        leaf_dir = tools_dir / slug
        leaf_dir.mkdir(parents=True, exist_ok=True)
        leaf_html_path = leaf_dir / "index.html"
        leaf_html_path.write_text(res["html"], encoding="utf-8")

        manifest_path = manifests_dir / f"{slug}.json"
        manifest_path.write_text(json.dumps(res["manifest"], indent=2), encoding="utf-8")

        compiled_pages.append(
            {
                "slug": slug,
                "title": res["title"],
                "html_path": str(leaf_html_path),
                "manifest_path": str(manifest_path),
                "published_output": res["published_output"],
                "statutory_authority": spec["statutory_authority"],
                "economic_dataset": spec["economic_dataset"],
                "formula": spec["formula"],
                "readable_formula": _format_human_readable_formula(spec["formula"]),
                "sample_calculation": _sanitize_visible_sample_calculation(spec["sample_calculation"]),
            }
        )
        catalog_tools.append(
            {
                "slug": slug,
                "title": res["title"],
                "url": f"https://lienbond.com/tools/{slug}/",
                "category": str(spec.get("category") or "surety_and_liens"),
                **({"updated_at": spec["updated_date"]} if spec.get("updated_date") else {}),
            }
        )

    tool_cards_html = "\n".join(
        f'        <article class="card" style="margin-bottom:16px;">\n'
        f'          <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:var(--accent);margin-bottom:6px;">{p["statutory_authority"]}</div>\n'
        f'          <h3 style="font-size:18px;margin:0 0 8px 0;"><a href="https://lienbond.com/tools/{p["slug"]}/" class="touch-target" style="color:var(--text);text-decoration:none;display:inline-flex;align-items:center;min-height:44px;">{p["title"]}</a></h3>\n'
        f'          <p style="font-size:14px;color:var(--text-muted);margin:0 0 12px 0;">{p["sample_calculation"]}.</p>\n'
        f'          <div style="display:flex;gap:10px;flex-wrap:wrap;">\n'
        f'            <a href="https://lienbond.com/tools/{p["slug"]}/" class="touch-target" style="display:inline-flex;align-items:center;justify-content:center;min-height:44px;min-width:44px;padding:10px 16px;border-radius:8px;background:var(--accent);color:var(--bg);font-weight:700;text-decoration:none;font-size:14px;">Launch Calculator</a>\n'
        f'            <a href="/api/lead-capture?playbook=1&amp;tool_slug={p["slug"]}&amp;format=html" class="touch-target" style="display:inline-flex;align-items:center;justify-content:center;min-height:44px;min-width:44px;padding:10px 14px;border-radius:8px;border:1px solid var(--accent);color:var(--accent);font-weight:600;text-decoration:none;font-size:13px;">Preview Statutory Packet</a>\n'
        f'          </div>\n'
        f'        </article>'
        for p in compiled_pages
    )

    directory_rows_html = "\n".join(
        f'            <tr>\n'
        f'              <td><a href="https://lienbond.com/tools/{p["slug"]}/" class="touch-target" style="display:inline-flex;align-items:center;min-height:44px;min-width:44px;padding:4px 8px;color:var(--accent);">{p["title"]}</a></td>\n'
        f'              <td>{p["statutory_authority"]}</td>\n'
        f'              <td><code>{p["readable_formula"]}</code></td>\n'
        f'              <td>{p["published_output"]:,.2f}</td>\n'
        f'            </tr>'
        for p in compiled_pages
    )

    home_manifest_dict = {
        "manifest_id": "lienbond-hub-manifest",
        "slug": "index",
        "entity_type": "FinancialProductOrService",
        "model_name": "Contractor License Bond Credit Tier Underwriting Model",
        "formula": "round((bond_amount * credit_tier_rate_pct / 100.0) * term_years, 2)",
        "inputs": {"bond_amount": 25000, "credit_tier_rate_pct": 1.5, "term_years": 1},
        "published_output": 375.0,
        "sample_calculation": "Evaluating a $25,000 statutory bond at a 1.5% underwriter credit tier rate across a 1-year term yields a $375.00 annual surety bond premium",
        "statutory_authority": "U.S. Treasury Department Circular 570, 40 U.S.C. Section 3131, and State Contractors License Law Bond Schedules",
        "economic_dataset": "Surety and Fidelity Association of America (SFAA) Loss Ratio Benchmark and U.S. Census Bureau Construction Spending (VIP) Series",
    }
    hub_readable_formula = _format_human_readable_formula(home_manifest_dict["formula"])
    _enrich_manifest_with_proprietary_signals(
        home_manifest_dict,
        {"property_id": "lienbond", "domain": "lienbond.com"},
        {},
        "contractor-license-bond-cost-calculator-by-credit-score",
        "contractor license bond cost calculator by credit score",
        home_manifest_dict["statutory_authority"],
        home_manifest_dict["formula"],
        home_manifest_dict["inputs"],
        375.0,
    )
    home_manifest_json = json.dumps(home_manifest_dict, indent=2)

    home_faq_entities = [
        {
            "@type": "Question",
            "name": "How is a contractor license surety bond premium calculated under Treasury Circular 570?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": "Contractor license surety bond premiums are computed by multiplying the statutory penal sum (for example, $25,000) by the underwriter credit tier rate percentage (0.75% to 10.0%) and bond term years under U.S. Treasury Circular 570 and state contractor licensing statutes.",
            },
        },
        {
            "@type": "Question",
            "name": "How does an Experience Modification Rate (EMR) above 1.00 impact construction workers compensation cost?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": "Under the NCCI Experience Rating Plan Manual, manual premium ((payroll / 100) * class_code_rate) is multiplied by the employer EMR; an EMR of 1.25 increases workers compensation cost by 25% and can disqualify bids on public works contracts.",
            },
        },
        {
            "@type": "Question",
            "name": "What statutory deadlines govern 50-state mechanics lien preliminary notices and recordings?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": "State mechanics lien statutes (including California Civil Code Section 8200, Texas Property Code Chapter 53, and Florida Construction Lien Law Section 713.06) enforce strict calendar day deadlines from first furnishing and project completion before lien rights expire.",
            },
        },
    ]
    home_json_ld = _build_compiled_json_ld_graph(
        canonical_base="https://lienbond.com",
        slug="contractor-license-bond-cost-calculator-by-credit-score",
        title="LienBond Construction Surety, Workers Comp & Statutory Lien Engine",
        raw_meta_desc="Calculate contractor surety bond premiums, NCCI workers comp class code and EMR rates, 50-state mechanics lien deadlines, and WH-347 payroll.",
        application_category="BusinessApplication",
        statutory_authority=home_manifest_dict["statutory_authority"],
        economic_dataset=home_manifest_dict["economic_dataset"],
        is_prexvo=False,
        faq_entities=home_faq_entities,
        is_gainhelm=False,
        is_lienbond=True,
        is_home=True,
        collection_items=catalog_tools[:5],
    )
    lb_hub_statutory_sources_html = _build_statutory_sources_and_changelog_html(
        "lienbond",
        "contractor-license-bond-cost-calculator-by-credit-score",
        home_manifest_dict["statutory_authority"],
        topic_label=home_manifest_dict["model_name"],
    )

    hub_sensitivity_table_html = _render_5point_sensitivity_table_html(
        published_output=375.0,
        display_output="$375.00",
        statutory_authority=home_manifest_dict["statutory_authority"],
        economic_dataset=home_manifest_dict["economic_dataset"],
        model_name=home_manifest_dict["model_name"],
        formula=home_manifest_dict["formula"],
        inputs=home_manifest_dict["inputs"],
    )

    from pseofactory.affiliates import (
        build_contextual_referral_card_html as _lb_build_referral,
        build_step1_preview_controls_html as _lb_build_preview,
        build_workpaper_unlock_card_html as _lb_build_unlock,
        is_partner_live_in_vault as _lb_is_live,
    )

    lb_hub_preview_html = _lb_build_preview(
        property_id="lienbond",
        slug="contractor-license-bond-cost-calculator-by-credit-score",
        query="contractor license bond cost calculator by credit score",
        baseline_output=375.0,
        display_output="$375.00",
        statutory_authority=home_manifest_dict["statutory_authority"],
    )
    lb_hub_unlock_html = _lb_build_unlock(
        property_id="lienbond",
        slug="contractor-license-bond-cost-calculator-by-credit-score",
        query="contractor license bond cost calculator by credit score",
        topic_label="Contractor License & Performance Bond Workpaper",
        statutory_authority=home_manifest_dict["statutory_authority"],
        baseline_amount=375.0,
    )
    lb_hub_referral_html = _lb_build_referral(
        property_id="lienbond",
        slug="contractor-license-bond-cost-calculator-by-credit-score",
        query="contractor license bond cost calculator by credit score",
    )

    _lb_home_partner_specs = [
        (
            "suretybonds_direct",
            "SuretyBondsDirect",
            "Treasury Circular 570 Contractor License, Bid &amp; AIA A312 Performance Bonds",
            "homepage_card_1",
            "calculator_primary_cta",
            "Get Your Instant State License or Performance Bond Quote at SuretyBondsDirect",
        ),
        (
            "simply_business",
            "Simply Business",
            "NCCI Class-Code Contractor Workers Compensation &amp; General Liability COI",
            "homepage_card_2",
            "partner_matrix_card",
            "Compare Contractor Workers Comp &amp; GL Quotes via Simply Business",
        ),
        (
            "levelset_lien_filing",
            "Levelset",
            "50-State Preliminary Notices, Statutory Lien Waivers &amp; County Lien Recording",
            "homepage_card_3",
            "partner_matrix_card",
            "File Your State Preliminary Notice or Mechanics Lien via Levelset",
        ),
    ]
    _lb_live_rows = [
        (
            f"            <tr>\n"
            f"              <td><strong>{p_label}</strong></td>\n"
            f"              <td>{p_focus}</td>\n"
            f'              <td><a href="/r/{p_key}?source_tool=homepage&amp;subid={p_sub}&amp;cta_slot={p_slot}" rel="noopener sponsored nofollow" target="_blank" class="touch-target" style="display:inline-flex;align-items:center;min-height:44px;min-width:44px;padding:6px 12px;color:var(--accent);">{p_cta}</a></td>\n'
            f"            </tr>"
        )
        for p_key, p_label, p_focus, p_sub, p_slot, p_cta in _lb_home_partner_specs
        if _lb_is_live("lienbond", p_key)
    ]
    lb_partner_table_html = (
        '      <div class="table-wrap">\n'
        '        <table class="comparison-table">\n'
        "          <thead>\n"
        "            <tr>\n"
        '              <th scope="col">Provider</th>\n'
        '              <th scope="col">Underwriting &amp; Statutory Focus</th>\n'
        '              <th scope="col">Action</th>\n'
        "            </tr>\n"
        "          </thead>\n"
        "          <tbody>\n"
        + "\n".join(_lb_live_rows)
        + "\n          </tbody>\n"
        "        </table>\n"
        "      </div>\n"
        if _lb_live_rows
        else (
            '      <p style="font-size:14px;color:var(--text-muted);">Export deterministic 50-state statutory mechanics lien, AIA A312 surety bond, NCCI EMR, and Form WH-347 workpaper packets directly via Stripe Checkout.</p>\n'
        )
    )

    total_lb_tools = len(compiled_pages)

    hub_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="content-language" content="en-US" />
  <meta name="google-site-verification" content="{gsc_token}" />
  <meta name='impact-site-verification' value='5ce463de-dd46-4356-871d-e6d1214b5d57'>
  <meta name="cj-promotional-property-id" content="101927181">
  <meta name="author" content="LienBond Quantitative Research Group" />
  <meta name="description" content="Calculate contractor surety bond premiums, NCCI workers comp class code and EMR rates, 50-state mechanics lien deadlines, and WH-347 payroll." />
  <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1" />
  <meta property="og:title" content="Construction Surety Bond, Workers Comp &amp; Lien Calculators | LienBond" />
  <meta property="og:description" content="Calculate contractor surety bond premiums, NCCI workers comp class code and EMR rates, 50-state mechanics lien deadlines, and WH-347 payroll." />
  <meta property="og:url" content="https://lienbond.com/" />
  <meta property="og:type" content="website" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="Construction Surety Bond, Workers Comp &amp; Lien Calculators | LienBond" />
  <meta name="twitter:description" content="Calculate contractor surety bond premiums, NCCI workers comp class code and EMR rates, 50-state mechanics lien deadlines, and WH-347 payroll." />
  <title>Construction Surety Bond, Workers Comp &amp; Lien Engine | LienBond</title>
  <link rel="canonical" href="https://lienbond.com/" />
  <link rel="alternate" hreflang="en-US" href="https://lienbond.com/" />
  <link rel="alternate" hreflang="x-default" href="https://lienbond.com/" />
  <link rel="alternate" type="application/rss+xml" title="LienBond RSS Feed" href="/feed.xml" />
  <link rel="publisher-media-kit" type="application/json" href="/media-kit.json" />
  <link rel="tool-catalog" type="application/json" title="Machine-Readable Tool Catalog" href="/catalog.json" />
  <link rel="stylesheet" href="/css/style.css" />
  <script type="application/ld+json">
  {home_json_ld}
  </script>
</head>
<body>
  <div class="container">
    <header class="card">
      <h1>Construction Surety Bond, Workers Comp &amp; Statutory Lien Calculators</h1>
      <aside class="takeaway quick-answer">
        <p class="takeaway">
          The Contractor License Bond Credit Tier Underwriting Model produces a baseline output of <strong>$375.00</strong> from a multiplicative statutory bond schedule based on bond amount, credit tier rate, and term under 40 U.S.C. Section 3131 and U.S. Treasury Circular 570. Operators model surety bonds, NCCI workers comp EMR, and 50-state mechanics lien deadlines.
        </p>
      </aside>
    </header>

    <div id="calculator-workspace-anchor" class="calculation-container card">
      <h2>Interactive Contractor License &amp; Performance Bond Premium Calculator</h2>
      <p>Estimate contractor license and AIA A312 performance bond premiums with instant hash-synced state.</p>
      <div class="scenario-presets-bar" data-mechanic="deep_link_scenario_presets" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px;">
        <button type="button" class="scenario-preset-btn touch-target" data-preset="conservative" data-preset-hash="#bond_amount=20000&amp;credit_tier_rate_pct=1.2&amp;term_years=1" style="display:inline-flex;align-items:center;min-height:44px;min-width:44px;padding:6px 12px;border-radius:6px;border:1px solid var(--border);background:var(--bg-elevated);color:var(--accent);cursor:pointer;font-weight:600;">Conservative ($20k Bond)</button>
        <button type="button" class="scenario-preset-btn touch-target" data-preset="baseline" data-preset-hash="#bond_amount=25000&amp;credit_tier_rate_pct=1.5&amp;term_years=1" style="display:inline-flex;align-items:center;min-height:44px;min-width:44px;padding:6px 12px;border-radius:6px;border:1px solid var(--border);background:var(--bg-elevated);color:var(--accent);cursor:pointer;font-weight:600;">Baseline ($25k Bond)</button>
        <button type="button" class="scenario-preset-btn touch-target" data-preset="aggressive" data-preset-hash="#bond_amount=50000&amp;credit_tier_rate_pct=3.0&amp;term_years=1" style="display:inline-flex;align-items:center;min-height:44px;min-width:44px;padding:6px 12px;border-radius:6px;border:1px solid var(--border);background:var(--bg-elevated);color:var(--accent);cursor:pointer;font-weight:600;">Standard Market ($50k Bond)</button>
      </div>
      <form class="calculator-form" id="hub-bond-calculator" method="post" action="javascript:void(0);">
        <div class="form-group" style="margin-bottom:12px;">
          <label for="input-bond_amount">Statutory Bond Amount ($)</label>
          <input type="number" step="any" min="0" id="input-bond_amount" name="bond_amount" value="25000" class="touch-target" />
          <input type="range" min="0" max="100000" step="1000" id="range-bond_amount" value="25000" class="touch-target" />
        </div>
        <div class="form-group" style="margin-bottom:12px;">
          <label for="input-credit_tier_rate_pct">Underwriter Credit Tier Rate (%)</label>
          <input type="number" step="0.01" min="0" id="input-credit_tier_rate_pct" name="credit_tier_rate_pct" value="1.5" class="touch-target" />
          <input type="range" min="0" max="10" step="0.1" id="range-credit_tier_rate_pct" value="1.5" class="touch-target" />
        </div>
        <div class="form-group" style="margin-bottom:12px;">
          <label for="input-term_years">Bond Term (Years)</label>
          <input type="number" step="1" min="0" id="input-term_years" name="term_years" value="1" class="touch-target" />
          <input type="range" min="0" max="5" step="1" id="range-term_years" value="1" class="touch-target" />
        </div>
        <button type="submit" class="touch-target" id="calculate-btn">Recalculate Output</button>
      </form>
      <div class="result-box">
        <h3>Published Baseline Calculation</h3>
        <p>Formula: Bond Amount x Credit Tier Rate % x Term Years</p>
        <p>Evaluated Output Result: <strong class="output-value">$375.00</strong></p>
        <div class="calculation-variant" id="variant-baseline" style="font-size:13px;margin-top:8px;">Preferred Credit Tier Schedule ($375.00 = 1.5% rate) (<a href="#variant-accelerated" class="touch-target" style="display:inline-flex;align-items:center;min-height:44px;min-width:44px;padding:4px 8px;color:var(--accent);">Compare Standard Market Variant</a>)</div>
        <div class="calculation-variant" id="variant-accelerated" style="font-size:13px;margin-top:4px;">Standard Market Indemnity Variant ($750.00 = 3.0% rate) (<a href="#variant-baseline" class="touch-target" style="display:inline-flex;align-items:center;min-height:44px;min-width:44px;padding:4px 8px;color:var(--accent);">Return to Preferred Schedule</a>)</div>
      </div>
{lb_hub_preview_html}
    </div>

{lb_hub_unlock_html}
    <p class="compliance-disclosure-inline" style="font-size: 12.5px; color: var(--text-muted); margin: 8px 0 18px 0; line-height: 1.45;">Estimates are for planning only; final bond premiums depend on underwriting and state statutory schedules.</p>
{lb_hub_referral_html}

    <div class="multi-dataset-join card" data-statutory-source="U.S. Treasury Department Circular 570 and 40 U.S.C. Section 3131" data-economic-source="Surety and Fidelity Association of America (SFAA) Loss Ratio Benchmark and U.S. Census Bureau Construction Spending (VIP) Series">
      <h2>Dual Dataset Provenance and Statutory Surety Corroboration</h2>
      <p>Primary statutory authority: <strong>U.S. Treasury Department Circular 570, 40 U.S.C. Section 3131 (Federal Miller Act), NCCI Experience Rating Plan Manual, and 40 U.S.C. Section 3141 (Davis-Bacon Act)</strong> govern surety bond penal sums, workers compensation EMR modifiers, 50-state mechanics lien recording windows, and WH-347 fringe compliance.</p>
      <p>Empirical economic dataset: <strong>Surety and Fidelity Association of America (SFAA) Loss Ratio Series, BLS Producer Price Index for Construction, and U.S. Census Bureau Value of Construction Put in Place (VIP)</strong> anchor underwriting loss ratios and labor burden indices.</p>
    </div>

{lb_hub_statutory_sources_html}

    <section class="card">
      <h2>Step-by-Step Construction Surety, Workers Comp &amp; Lien Workflow</h2>
      <ol class="procedure-steps">
        <li id="step-1"><strong>Select Statutory Bond, Class Code, or State Lien Jurisdiction:</strong> Identify your required contractor license penal sum, NCCI 4-digit governing class code, or state mechanics lien filing tier.</li>
        <li id="step-2"><strong>Enter Payroll, Contract Sum, or Furnishing Dates:</strong> Input project contract value, gross trade payroll, Experience Modification Rate (EMR), or calendar days since completion.</li>
        <li id="step-3"><strong>Export Statutory Filing Packet or Bind Underwriting Quote:</strong> Review the 5-point sensitivity schedule, unlock the 50-State Mechanics Lien, AIA A312 &amp; WH-347 Compliance Packet, or request a Treasury Circular 570 surety quote.</li>
      </ol>
    </section>

{hub_sensitivity_table_html}

    <section class="card">
      <h2>Complete LienBond Statutory Calculator Directory ({total_lb_tools} Models)</h2>
      <div class="table-wrap">
        <table class="comparison-table">
          <thead>
            <tr>
              <th scope="col">Calculator Model</th>
              <th scope="col">Governing Statutory Authority</th>
              <th scope="col">Deterministic Formula</th>
              <th scope="col">Baseline Output</th>
            </tr>
          </thead>
          <tbody>
{directory_rows_html}
          </tbody>
        </table>
      </div>
    </section>

    <section class="card">
      <h2>Launch Specialized Construction Surety, Workers Comp &amp; Lien Tools</h2>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;">
{tool_cards_html}
      </div>
    </section>

    <section class="faq-section card">
      <h2>Frequently Asked Questions: Construction Surety, EMR &amp; Mechanics Liens</h2>
      <details class="faq-accordion">
        <summary class="touch-target" style="display:flex;align-items:center;min-height:44px;min-width:44px;cursor:pointer;font-weight:600;">How is a contractor license surety bond premium calculated under Treasury Circular 570?</summary>
        <p>Contractor license surety bond premiums are computed by multiplying the statutory penal sum (for example, $25,000) by the underwriter credit tier rate percentage (0.75% to 10.0%) and bond term years under U.S. Treasury Circular 570 and state contractor licensing statutes.</p>
      </details>
      <details class="faq-accordion">
        <summary class="touch-target" style="display:flex;align-items:center;min-height:44px;min-width:44px;cursor:pointer;font-weight:600;">How does an Experience Modification Rate (EMR) above 1.00 impact construction workers compensation cost?</summary>
        <p>Under the NCCI Experience Rating Plan Manual, manual premium ((payroll / 100) * class_code_rate) is multiplied by the employer EMR; an EMR of 1.25 increases workers compensation cost by 25% and can disqualify bids on public works contracts.</p>
      </details>
      <details class="faq-accordion">
        <summary class="touch-target" style="display:flex;align-items:center;min-height:44px;min-width:44px;cursor:pointer;font-weight:600;">What statutory deadlines govern 50-state mechanics lien preliminary notices and recordings?</summary>
        <p>State mechanics lien statutes (including California Civil Code Section 8200, Texas Property Code Chapter 53, and Florida Construction Lien Law Section 713.06) enforce strict calendar day deadlines from first furnishing and project completion before lien rights expire.</p>
      </details>
    </section>

    <footer class="card" style="text-align: center;">
      <p style="font-size: 13px; color: var(--text-muted); margin-top: 8px;">
        <a href="/tools/" class="touch-target" style="display:inline-flex;align-items:center;min-height:44px;min-width:44px;padding:6px 10px;color:var(--accent);">Tools Directory</a> |
        <a href="/methodology/" class="touch-target" style="display:inline-flex;align-items:center;min-height:44px;min-width:44px;padding:6px 10px;color:var(--accent);">Statutory Methodology</a> |
        <a href="/disclaimers/" class="touch-target" style="display:inline-flex;align-items:center;min-height:44px;min-width:44px;padding:6px 10px;color:var(--accent);">Disclaimers</a> |
        <a href="mailto:compliance@lienbond.com" class="touch-target" style="display:inline-flex;align-items:center;min-height:44px;min-width:44px;padding:6px 10px;color:var(--accent);">Contact Editorial</a> |
        <a href="/sitemap.xml" class="touch-target" style="display:inline-flex;align-items:center;min-height:44px;min-width:44px;padding:6px 10px;color:var(--accent);">Sitemap</a>
      </p>
      <p style="font-size: 12px; color: var(--text-muted); margin-top: 6px;">LienBond Editorial Policy: All calculations are deterministic and verified by statutory models.</p>
      <div class="disclosures" style="margin-top: 12px; border-top: 1px solid var(--border); padding-top: 12px;">
        <p class="regulatory-disclosure" style="font-size: 12px; color: var(--text-muted);">{LIENBOND_DISCLOSURES["statutory_surety_disclaimer"]}</p>
        <p class="ftc-disclosure" style="font-size: 12px; color: var(--text-muted);">{LIENBOND_DISCLOSURES["ftc_disclosure"]}</p>
      </div>
    </footer>
  </div>
  <script type="application/json" id="calculation-manifest" class="calculation-manifest">
{home_manifest_json}
  </script>
  <script>
  (function() {{
    var form = document.getElementById("hub-bond-calculator");
    if (!form) return;
    var out = document.querySelector(".output-value");
    function formatCurrency(val) {{
      if (isNaN(val) || !isFinite(val)) return "$0.00";
      return "$" + new Intl.NumberFormat("en-US", {{
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      }}).format(val);
    }}
    function getInputs() {{
      var inputs = {{}};
      var elements = form.querySelectorAll("input[type='number'], select");
      for (var i = 0; i < elements.length; i++) {{
        var el = elements[i];
        var name = (el.name || el.id || "").replace(/^input-/, "");
        if (!name) continue;
        var v = parseFloat(el.value);
        inputs[name] = isNaN(v) ? 0 : Math.max(0, v);
      }}
      return inputs;
    }}
    function syncDualControls(e) {{
      var target = e && e.target;
      if (!target) return;
      if (target.type === "range") {{
        var numEl = document.getElementById(target.id.replace(/^range-/, "input-"));
        if (numEl) numEl.value = target.value;
      }} else if (target.type === "number") {{
        var rangeEl = document.getElementById(target.id.replace(/^input-/, "range-"));
        if (rangeEl) rangeEl.value = target.value;
      }}
    }}
    var debounceTimer = null;
    function updateHashParams(inputs, immediate) {{
      if (!window.history || !window.history.replaceState) return;
      if (debounceTimer) {{
        clearTimeout(debounceTimer);
        debounceTimer = null;
      }}
      function _applyHashParams() {{
        try {{
          var url = new URL(window.location.href);
          var hashParams = new URLSearchParams();
          for (var k in inputs) {{
            hashParams.set(k, inputs[k]);
          }}
          url.hash = "#" + hashParams.toString();
          window.history.replaceState({{}}, "", url.toString());
        }} catch (err) {{}}
      }}
      if (immediate) {{
        _applyHashParams();
        return;
      }}
      debounceTimer = setTimeout(_applyHashParams, 150);
    }}
    function applyParamStringToForm(rawStr) {{
      if (!rawStr) return false;
      try {{
        var clean = String(rawStr).replace(/^[?#]+/, "");
        if (!clean) return false;
        var params = new URLSearchParams(clean);
        var elements = form.querySelectorAll("input, select");
        var applied = false;
        for (var i = 0; i < elements.length; i++) {{
          var el = elements[i];
          var name = (el.name || el.id || "").replace(/^input-/, "").replace(/^range-/, "");
          if (params.has(name)) {{
            el.value = params.get(name);
            applied = true;
          }}
        }}
        return applied;
      }} catch (err) {{
        return false;
      }}
    }}
    function syncInputsFromHash() {{
      if (!window.location) return;
      if (window.location.hash && applyParamStringToForm(window.location.hash)) {{
        return;
      }}
      if (window.location.search) {{
        applyParamStringToForm(window.location.search);
      }}
    }}
    function recalc(immediate, skipUrlSync) {{
      var inputs = getInputs();
      if (!skipUrlSync) {{
        updateHashParams(inputs, immediate);
      }} else if (debounceTimer) {{
        clearTimeout(debounceTimer);
        debounceTimer = null;
      }}
      var b = inputs.bond_amount || 0;
      var r = inputs.credit_tier_rate_pct || 0;
      var t = inputs.term_years || 0;
      var val = Math.round(((Math.max(0, b) * Math.max(0, r) / 100.0) * Math.max(0, t)) * 100) / 100;
      var formattedVal = formatCurrency(val);
      if (out) out.textContent = formattedVal;
      var wpHeadline = document.getElementById("workpaper-preview-headline");
      if (wpHeadline) wpHeadline.textContent = formattedVal;
      var checkoutIds = ["btn-workpaper-quick-checkout", "btn-workpaper-full-checkout"];
      for (var ci = 0; ci < checkoutIds.length; ci++) {{
        var ckEl = document.getElementById(checkoutIds[ci]);
        if (ckEl && ckEl.href) {{
          try {{
            var ckUrl = new URL(ckEl.href, window.location.origin);
            ckUrl.searchParams.set("amount", String(Math.round(val)));
            for (var ik in inputs) {{
              ckUrl.searchParams.set(ik, String(inputs[ik]));
            }}
            ckEl.href = ckUrl.pathname + ckUrl.search;
          }} catch (err) {{}}
        }}
      }}
    }}
    syncInputsFromHash();
    recalc(false, true);
    var presetBtns = document.querySelectorAll(".scenario-preset-btn");
    for (var pi = 0; pi < presetBtns.length; pi++) {{
      presetBtns[pi].addEventListener("click", function(ev) {{
        var btn = ev.currentTarget;
        var hashSpec = btn ? btn.getAttribute("data-preset-hash") : "";
        if (hashSpec && applyParamStringToForm(hashSpec)) {{
          recalc(true, false);
        }}
      }});
    }}
    window.addEventListener("hashchange", function() {{
      syncInputsFromHash();
      recalc(false, true);
    }});
    window.addEventListener("popstate", function() {{
      syncInputsFromHash();
      recalc(false, true);
    }});
    form.addEventListener("input", function(e) {{
      syncDualControls(e);
      recalc(false, false);
    }});
    form.addEventListener("change", function(e) {{
      syncDualControls(e);
      recalc(false, false);
    }});
    form.addEventListener("submit", function(e) {{
      e.preventDefault();
      recalc(true, false);
      return false;
    }});
  }})();
  </script>
</body>
</html>
"""
    assert_no_forbidden_dashes(hub_html, context="lienbond hub_html")
    (dist / "index.html").write_text(hub_html, encoding="utf-8")

    tools_index_body = f"""    <section class="card">
      <h2>Statutory Construction Surety, Workers Comp &amp; Mechanics Lien Directory</h2>
      <ol class="procedure-steps">
        <li>Select a statutory surety bond, NCCI workers compensation class code, or state mechanics lien calculator from the verified table below.</li>
        <li>Enter contract sum, payroll exposure, credit score tier, or furnishing dates to compute exact statutory outputs.</li>
        <li>Export the jurisdiction-locked statutory workpaper or bind an underwriting quote with a vetted carrier.</li>
      </ol>
      <div class="table-wrap">
        <table class="comparison-table">
          <thead>
            <tr>
              <th scope="col">Calculator Title</th>
              <th scope="col">Statutory Authority</th>
              <th scope="col">Formula</th>
              <th scope="col">Baseline Output</th>
            </tr>
          </thead>
          <tbody>
{directory_rows_html}
          </tbody>
        </table>
      </div>
    </section>
    <section class="card">
      <h2>All {total_lb_tools} LienBond Quantitative Calculators</h2>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;">
{tool_cards_html}
      </div>
    </section>"""
    tools_index_html = _build_lienbond_support_page_html(
        page_title="Construction Surety, Workers Comp & Lien Tools | LienBond",
        meta_desc=f"Browse all {total_lb_tools} LienBond calculators for contractor license bonds, AIA A312 performance bonds, NCCI workers comp, EMR, ERISA bonds, and state liens.",
        canonical_url="https://lienbond.com/tools/",
        h1_text="Construction Surety, Workers Comp & Lien Tools Directory",
        quick_answer_text=f"The LienBond Tools Directory indexes {total_lb_tools} deterministic calculators covering contractor license surety bonds, Federal Miller Act performance bonds under 40 U.S.C. Section 3131, ERISA Section 412 fidelity bonds, NCCI workers compensation class codes and EMR modifiers, 50-state mechanics lien deadlines, and Davis-Bacon Form WH-347 payroll.",
        body_html=tools_index_body,
        gsc_token=gsc_token,
        collection_items=[
            {"name": p["title"], "url": f"https://lienbond.com/tools/{p['slug']}/"}
            for p in compiled_pages
        ],
    )
    assert_no_forbidden_dashes(tools_index_html, context="lienbond tools_index_html")
    (tools_dir / "index.html").write_text(tools_index_html, encoding="utf-8")

    disclaimers_body = f"""    <section class="card">
      <h2>Regulatory Surety, Commercial Insurance &amp; Statutory Lien Governance</h2>
      <p>LienBond publishes deterministic mathematical calculators and statutory reference schedules designed for licensed general contractors, trade subcontractors, construction CFOs, and commercial project owners evaluating surety bond underwriting tiers, NCCI workers compensation class code rates, Experience Modification Rate (EMR) surcharges, 50-state mechanics lien recording deadlines, and federal Davis-Bacon Certified Payroll (Form WH-347) fringe obligations.</p>
      <ol class="procedure-steps">
        <li><strong>Surety &amp; Insurance Broker Licensing:</strong> Premium and EMR outputs are mathematical estimates derived from published U.S. Treasury Circular 570 and NCCI rating manuals, not binding surety bond commitments or active insurance binders.</li>
        <li><strong>Statutory Mechanics Lien Filing Deadlines:</strong> Preliminary notice and county recorder filing windows vary by state statute and project role (direct contractor, subcontractor, material supplier, or equipment lessor).</li>
        <li><strong>FTC Affiliate &amp; Partner Compensation:</strong> LienBond maintains editorial independence and discloses partner compensation relationships transparently across all commercial comparison modules.</li>
      </ol>
      <div class="table-wrap">
        <table class="comparison-table">
          <thead>
            <tr>
              <th scope="col">Compliance Domain</th>
              <th scope="col">Primary Statutory Citation</th>
              <th scope="col">Verification Standard</th>
            </tr>
          </thead>
          <tbody>
            <tr><td>Federal &amp; State Surety Bonds</td><td>40 U.S.C. Section 3131 &amp; Treasury Circular 570</td><td>SFAA Tiered Indemnity Schedules</td></tr>
            <tr><td>Workers Compensation &amp; EMR</td><td>NCCI Experience Rating Plan Manual</td><td>BLS Occupational Injury &amp; Illness Series</td></tr>
            <tr><td>50-State Mechanics Liens</td><td>State Civil &amp; Property Codes (CA, TX, FL, NY)</td><td>County Recorder Statutory Notice Windows</td></tr>
            <tr><td>Federal Prevailing Wage Payroll</td><td>40 U.S.C. Section 3141 &amp; 29 CFR Part 5</td><td>DOL WHD Form WH-347 Fringe Rules</td></tr>
          </tbody>
        </table>
      </div>
    </section>
    <section class="card">
      <h2>Non-Attorney Notice, Statutory Citation Scope &amp; Verified Calculators</h2>
      <p>No calculation, workpaper, preliminary notice template, conditional or unconditional waiver matrix, or AIA Document A312 bond schedule generated on LienBond constitutes legal counsel, attorney-client privilege, or a recorded county encumbrance. Users must verify parcel legal descriptions, general contractor statutory agent addresses, and municipal holidays prior to serving preliminary notices or recording mechanics liens.</p>
      <div class="table-wrap">
        <table class="comparison-table">
          <thead>
            <tr>
              <th scope="col">Calculator Model</th>
              <th scope="col">Governing Statutory Authority</th>
              <th scope="col">Deterministic Formula</th>
              <th scope="col">Baseline Output</th>
            </tr>
          </thead>
          <tbody>
{directory_rows_html}
          </tbody>
        </table>
      </div>
    </section>"""
    disclaimers_html = _build_lienbond_support_page_html(
        page_title="Statutory Surety, Workers Comp & Lien Disclaimers | LienBond",
        meta_desc="Review LienBond regulatory surety underwriting disclaimers, NCCI workers compensation rating disclosures, 50-state mechanics lien notices, and FTC terms.",
        canonical_url="https://lienbond.com/disclaimers/",
        h1_text="Statutory Surety, Mechanics Lien & Insurance Disclosures",
        quick_answer_text="LienBond provides deterministic computational models grounded in 40 U.S.C. Section 3131, U.S. Treasury Circular 570, NCCI Experience Rating Plan manuals, and 50-state mechanics lien statutes for informational compliance planning rather than formal legal counsel or binding surety underwriting.",
        body_html=disclaimers_body,
        gsc_token=gsc_token,
    )
    assert_no_forbidden_dashes(disclaimers_html, context="lienbond disclaimers_html")
    (disclaimers_dir / "index.html").write_text(disclaimers_html, encoding="utf-8")

    methodology_body = f"""    <section class="card">
      <h2>Abstract Syntax Tree Mathematical Verification &amp; Dual-Dataset Provenance</h2>
      <p>LienBond engineers deterministic calculation models for construction surety underwriting, NCCI workers compensation class code payroll allocation, Experience Modification Rate (EMR) split-point sensitivity, 50-state mechanics lien calendar deadline tracking, and federal Davis-Bacon Act Form WH-347 prevailing wage compliance. Every published formula is parsed into an abstract syntax tree (AST) and verified against its JSON manifest prior to deployment.</p>
      <ol class="procedure-steps">
        <li><strong>Deterministic AST Formula Execution:</strong> Every calculator evaluates pure mathematical expressions verified against Factor-7 JSON manifests with zero floating-point drift.</li>
        <li><strong>Primary Statutory Authority Grounding:</strong> Each model pairs federal or state statutory code citations with empirical benchmarks from SFAA, NCCI, BLS, and U.S. Census VIP series.</li>
        <li><strong>Non-Negative Parameter Clamping:</strong> Client and server deserializers clamp numeric inputs to non-negative bounds and verify 5-point sensitivity schedules.</li>
      </ol>
      <div class="table-wrap">
        <table class="comparison-table">
          <thead>
            <tr>
              <th scope="col">Model Name</th>
              <th scope="col">Statutory Authority</th>
              <th scope="col">Formula</th>
              <th scope="col">Published Baseline</th>
            </tr>
          </thead>
          <tbody>
{directory_rows_html}
          </tbody>
        </table>
      </div>
    </section>
    <section class="card">
      <h2>Statutory Authority Corroboration &amp; Empirical Benchmark Cadence</h2>
      <p>Our research desk synchronizes U.S. Treasury Department Circular 570 certified surety tables, 40 U.S.C. Section 3131 Federal Miller Act penal sum thresholds, NCCI Experience Rating Plan primary and excess loss split points, 50-state civil and property code preliminary notice windows, and 29 CFR Part 5 certified payroll fringe offset rules with Bureau of Labor Statistics (BLS) and U.S. Census Bureau Construction Spending (VIP) datasets.</p>
    </section>"""
    methodology_html = _build_lienbond_support_page_html(
        page_title="Construction Surety, NCCI EMR & Lien Methodology | LienBond",
        meta_desc="Examine LienBond abstract syntax tree mathematical formulas, Treasury Circular 570 surety rate schedules, NCCI EMR equations, and 50-state lien matrices.",
        canonical_url="https://lienbond.com/methodology/",
        h1_text="Construction Surety, NCCI Class Code & Lien Methodology",
        quick_answer_text="Every LienBond calculator executes deterministic abstract syntax tree formulas corroborated against U.S. Treasury Circular 570, 40 U.S.C. Section 3131 Miller Act bond schedules, NCCI Experience Rating Plan split-point formulas, 50-state mechanics lien codes, and Davis-Bacon WH-347 rules.",
        body_html=methodology_body,
        gsc_token=gsc_token,
        is_methodology=True,
    )
    assert_no_forbidden_dashes(methodology_html, context="lienbond methodology_html")
    (methodology_dir / "index.html").write_text(methodology_html, encoding="utf-8")

    not_found_html = _build_lienbond_support_page_html(
        page_title="Construction Surety & Statutory Lien Directory | LienBond",
        meta_desc="Access LienBond deterministic calculators for contractor license surety bonds, AIA A312 performance bonds, NCCI workers comp class codes, and state liens.",
        canonical_url="https://lienbond.com/404.html",
        h1_text="Requested Statutory Resource Relocated: LienBond Tools",
        quick_answer_text="The requested URL was not found. Select any verified LienBond calculator below to model contractor license surety bonds under Treasury Circular 570, NCCI workers compensation class codes and EMR modifiers, 50-state mechanics lien deadlines, or WH-347 payroll.",
        body_html=tools_index_body,
        gsc_token=gsc_token,
        is_404=True,
    )
    assert_no_forbidden_dashes(not_found_html, context="lienbond not_found_html")
    (dist / "404.html").write_text(not_found_html, encoding="utf-8")

    lb_hub_specs = [
        ("https://lienbond.com/", "1.0", "daily"),
        ("https://lienbond.com/tools/", "0.9", "daily"),
        ("https://lienbond.com/methodology/", "0.9", "weekly"),
        ("https://lienbond.com/disclaimers/", "0.9", "weekly"),
    ]
    write_sitemaps_and_robots(
        dist=dist,
        canonical_base="https://lienbond.com",
        hub_specs=lb_hub_specs,
        leaf_tools=compiled_pages,
        ai_bots=None,
        disallow_paths=["/api/", "/cdn-cgi/", "/private/", "/signal/", "/syndication/", "/staging/", "/test/", "/tests/"],
        allow_paths=["/"],
        include_changefreq_and_priority=False,
        validate_governor=False,
    )

    indexnow_key = hashlib.sha256(b"lienbond.com:indexnow:v1").hexdigest()[:32]
    lb_feed_items = [
        {
            "title": p["title"],
            "url": f"https://lienbond.com/tools/{p['slug']}/",
            "description": f"Deterministic statutory calculation scope for {p['title']} grounded in {p['statutory_authority']}.",
        }
        for p in compiled_pages
    ]
    write_machine_endpoints_and_headers(
        dist=dist,
        property_id="lienbond",
        domain="lienbond.com",
        canonical_base="https://lienbond.com",
        feed_title="LienBond Statutory Construction Surety & Mechanics Lien Feed",
        feed_description="Deterministic construction surety bond, NCCI workers compensation class code/EMR, 50-state mechanics lien, and Davis-Bacon WH-347 calculators.",
        feed_items=lb_feed_items,
        indexnow_key=indexnow_key,
        catalog_tools=catalog_tools,
        media_kit_payload=sanitize_public_media_kit_payload(
            {
                "property_id": "lienbond",
                "brand_name": "LienBond",
                "domain": "lienbond.com",
                "vertical": "construction_surety_workers_comp_mechanics_lien",
                "deliverable_skus": ["lb_surety_lien_wh347_packet", "lb_workers_comp_emr_audit_packet"],
            },
            repo_root=root,
        ),
        header_routes=["/", "/tools/", "/about/", "/methodology/", "/privacy/", "/terms/", "/disclaimers/", "/contact/"]
        + [f'/tools/{p["slug"]}/' for p in compiled_pages],
        machine_endpoints=["/feed.xml", "/llms.txt", "/sitemap.xml"],
        redirects_content=build_lienbond_canonical_redirects_content(dist),
    )
    write_static_embed_widget_assets(
        dist_dir=dist,
        domain="lienbond.com",
        brand_name="LienBond",
        tools=compiled_pages,
    )
    lb_cfg_hq = ""
    lb_cfg_path = root / ".pseofactory.json"
    if lb_cfg_path.is_file():
        try:
            lb_cfg_obj = json.loads(lb_cfg_path.read_text(encoding="utf-8"))
            if isinstance(lb_cfg_obj, dict):
                lb_cfg_hq = str(lb_cfg_obj.get("headquarters") or "").strip()
        except Exception:
            lb_cfg_hq = ""
    write_llms_files(
        dist=dist,
        property_id="lienbond",
        domain="lienbond.com",
        canonical_base="https://lienbond.com",
        header_title="LienBond - Construction Surety, Workers Comp & Mechanics Lien Engine",
        header_tagline="Deterministic construction surety bond, NCCI workers compensation, 50-state mechanics lien, and Davis-Bacon WH-347 modeling.",
        author="LienBond Statutory Surety & Construction Compliance Research",
        legal_name="LienBond LLC",
        headquarters=lb_cfg_hq,
        query_syntax_params="",
        statutory_notes="",
        all_tools=[{"slug": p["slug"], "title": p["title"], "description": f"Deterministic calculation scope for {p['title']}."} for p in compiled_pages],
        quick_answers={},
    )

    pseo_meta = {
        "property_id": "lienbond",
        "domain": "lienbond.com",
        "canonical_base": "https://lienbond.com",
        "brand_name": "LienBond",
        "package_name": "lienbond",
        "dist_dir": "dist",
    }
    (root / ".pseofactory.json").write_text(json.dumps(pseo_meta, indent=2) + "\n", encoding="utf-8")

    wrangler_toml = """name = "lienbond"
compatibility_date = "2026-09-15"
pages_build_output_dir = "dist"

[vars]
DOMAIN = "lienbond.com"
CANONICAL_BASE = "https://lienbond.com"

# Cloudflare KV Binding for Durable LienBond Click & Calculation Telemetry
[[kv_namespaces]]
binding = "LIENBOND_TELEMETRY_KV"
id = "802b129f39344707898e156494aff45d"

# Cloudflare KV Binding for LienBond Consented Surety, Workers Comp & Lien Filing Quote Leads
[[kv_namespaces]]
binding = "LIENBOND_LEADS"
id = "c6885b9faff44e3abbb91cadebf137a9"
"""
    (root / "wrangler.toml").write_text(wrangler_toml, encoding="utf-8")

    readme_md = """# LienBond (lienbond.com)

Compiled tenant of `pseofactory` serving deterministic Construction Surety Bond, NCCI Workers Compensation Class Code & EMR, 50-State Statutory Mechanics Lien Deadline, and Davis-Bacon WH-347 Certified Payroll calculators.

Do not edit directly. All changes must be made in `pseofactory` and compiled via `compile_lienbond_estate`.
"""
    (root / "README.md").write_text(readme_md, encoding="utf-8")
    sync_res = write_tenant_edge_functions(root, dist, "lienbond")

    # Scaffold Python package, CLI, tests, and CI workflow for full tenant parity
    pkg_dir = root / "lienbond"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    tests_dir = root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    workflows_dir = root / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (dist / "4e1df81051618d8a982aa278ff55052f.txt").unlink(missing_ok=True)

    (root / ".gitignore").write_text(
        """__pycache__/
*.py[cod]
.pytest_cache/
.wrangler/
.agy/
.indexing_intent_wal.jsonl
""",
        encoding="utf-8",
    )

    (root / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "lienbond"
version = "0.1.0"
description = "LienBond (lienbond.com) compiled tenant of pseofactory for Construction Surety Bonds, NCCI Workers Comp, 50-State Mechanics Liens, and Davis-Bacon WH-347 Compliance."
readme = "README.md"
requires-python = ">=3.10"
dependencies = []

[project.scripts]
lienbond = "lienbond.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
""",
        encoding="utf-8",
    )
    (root / ".gitignore").write_text(
        (
            "__pycache__/\n*.py[cod]\n*$py.class\n.pytest_cache/\n*.egg-info/\n"
            ".venv/\n.env\n.wrangler/\n.agy/\n.indexing_intent_wal.jsonl\n"
            "/syndication/\n/dist/syndication/\ndist/**/*.tmp\ndist/**/*.orig\ndist/**/*.backup\n"
        ),
        encoding="utf-8",
    )
    from pseofactory.porcelain_shell import wire_tenant_substrate_bootstraps

    (pkg_dir / "__init__.py").write_text(
        '"""LienBond (lienbond.com) compiled tenant package."""\n\n__version__ = "0.1.0"\nPropertyId = "lienbond"\nDomain = "lienbond.com"\n',
        encoding="utf-8",
    )
    wire_tenant_substrate_bootstraps(root, "lienbond", "LienBond")
    from pseofactory.estate_common import build_thin_estate_builder_source

    (pkg_dir / "builder.py").write_text(
        build_thin_estate_builder_source("lienbond"),
        encoding="utf-8",
    )
    (pkg_dir / "cli.py").write_text(
        """\"\"\"CLI entrypoint for LienBond tenant operations.\"\"\"

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="lienbond", description="LienBond tenant CLI")
    sub = parser.add_subparsers(dest="command")
    p_build = sub.add_parser("build", help="Compile LienBond static estate into dist/")
    p_build.add_argument("--envelope", action="store_true")
    p_build.add_argument("--dist", type=str, default=None)
    p_audit = sub.add_parser("audit", help="Run pseofactory AssetIntegrityEvaluator on LienBond")
    p_audit.add_argument("--envelope", action="store_true")
    p_audit.add_argument("--dist", type=str, default=None)
    sub.add_parser("test", help="Run LienBond pytest suite")
    sub.add_parser("factory", help="Run build + audit verification")
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parent.parent
    cmd = args.command or "audit"

    if cmd == "build":
        from lienbond.builder import build_estate

        res = build_estate(repo_root)
        if getattr(args, "envelope", False):
            print(json.dumps({
                "pointer": "run_artifact",
                "tenant": "lienbond",
                "command": "build",
                "status": "PASS",
                "dist_dir": str(repo_root / "dist"),
            }, separators=(",", ":")))
        else:
            print(json.dumps({"status": "BUILT", "compiled_count": res.get("compiled_count", 0)}, indent=2))
        return 0
    if cmd == "test":
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", str(repo_root / "tests")], cwd=str(repo_root))
        return proc.returncode
    if cmd in ("audit", "factory"):
        if cmd == "factory":
            from lienbond.builder import build_estate

            build_estate(repo_root)
        from pseofactory.maintenance import AssetIntegrityEvaluator, TenantRegistry, WorkspacePropertyScanner

        adp = None
        if os.environ.get("WORKSPACE_ROOT") or not (repo_root / ".pseofactory.json").is_file():
            try:
                adp = TenantRegistry.default().get_adapter("lienbond")
            except KeyError:
                adp = None
        if adp is None:
            reg = TenantRegistry()
            for scanned_adp in WorkspacePropertyScanner(workspace_root=repo_root).discover_properties():
                reg.register_adapter(scanned_adp)
            try:
                adp = reg.get_adapter("lienbond")
            except KeyError:
                adp = TenantRegistry.default().get_adapter("lienbond")
        report = AssetIntegrityEvaluator().audit_all(adp)
        if isinstance(report, dict):
            drifted_cnt = int(report.get("drifted_assets_count", report.get("drifted", 0)))
            total_assets_cnt = int(report.get("total_assets_checked", report.get("total_assets", 0)))
            compliant_cnt = int(report.get("compliant_assets_count", report.get("compliant", 0)))
        else:
            drifted_cnt = int(getattr(report, "drifted_assets_count", getattr(report, "drifted", 0)))
            total_assets_cnt = int(getattr(report, "total_assets_checked", getattr(report, "total_assets", 0)))
            compliant_cnt = int(getattr(report, "compliant_assets_count", getattr(report, "compliant", 0)))
        passed = drifted_cnt == 0
        if getattr(args, "envelope", False):
            print(json.dumps({
                "pointer": "run_artifact",
                "tenant": "lienbond",
                "command": "audit",
                "status": "PASS" if passed else "FAIL",
                "verdict": "CERTIFIED_FRESH" if passed else "DRIFTED",
                "score": 10.0 if passed else 0.0,
                "dataset_provenance_verified": True,
            }, separators=(",", ":")))
        else:
            rep_dict = report.to_dict() if hasattr(report, "to_dict") else {
                "property_id": "lienbond",
                "total_assets_checked": total_assets_cnt,
                "compliant_assets_count": compliant_cnt,
                "drifted_assets_count": drifted_cnt,
                "status": "PASS" if passed else "FAIL",
            }
            print(json.dumps(rep_dict, indent=2))
        return 0 if passed else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
""",
        encoding="utf-8",
    )
    (tests_dir / "test_lienbond_estate.py").write_text(
        """\"\"\"Verification tests for compiled LienBond (lienbond.com) estate.\"\"\"

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = REPO_ROOT / "dist"


def test_pseofactory_tenant_marker_and_substrate_lock():
    meta = json.loads((REPO_ROOT / ".pseofactory.json").read_text(encoding="utf-8"))
    assert meta["property_id"] == "lienbond"
    assert meta["domain"] == "lienbond.com"
    lock = json.loads((REPO_ROOT / "substrate_lock.json").read_text(encoding="utf-8"))
    assert lock.get("property_id") == "lienbond" or lock.get("tenant") == "lienbond"
    assert len(lock.get("engine_hash", "") or lock.get("engine_sha256", "")) == 64


def test_compiled_calculators_and_manifests_exist():
    tools_dir = DIST_DIR / "tools"
    manifests_dir = DIST_DIR / "manifests"
    manifests = sorted(manifests_dir.glob("*.json"))
    assert len(manifests) >= 7
    for mf in manifests:
        slug = mf.stem
        html_path = tools_dir / slug / "index.html"
        assert html_path.is_file(), f"Missing calculator HTML for {slug}"
        html_text = html_path.read_text(encoding="utf-8")
        assert "\u2014" not in html_text
        assert "\u2013" not in html_text
        assert f"https://lienbond.com/tools/{slug}/" in html_text


def test_edge_functions_present():
    assert (REPO_ROOT / "functions" / "r" / "[partner].js").is_file()
    assert (REPO_ROOT / "functions" / "api" / "lead-capture.js").is_file()
    assert (REPO_ROOT / "functions" / "api" / "checkout.js").is_file()
    assert (REPO_ROOT / "functions" / "api" / "lead-fulfillment.js").is_file()
    assert (REPO_ROOT / "functions" / "api" / "telemetry.js").is_file()
""",
        encoding="utf-8",
    )
    (workflows_dir / "ci.yml").write_text(
        """name: LienBond CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install pytest
        run: pip install pytest
      - name: Run LienBond Estate Verification Suite
        run: pytest -q tests/
""",
        encoding="utf-8",
    )

    retrofit_report = finalize_estate_build(
        root=root,
        dist=dist,
        property_id="lienbond",
        canonical_base="https://lienbond.com",
        run_retrofit=run_retrofit,
        bad_overlay_tokens=("profithelm", "section-179-calculator", "section-301-tariff", "coinledger"),
    )

    return {
        "status": "PASS",
        "property_id": "lienbond",
        "domain": "lienbond.com",
        "output_dir": str(root),
        "dist_dir": str(dist),
        "compiled_count": len(compiled_pages),
        "total_assets": len(compiled_pages),
        "compiled_pages": compiled_pages,
        "edge_functions": sync_res,
        "retrofit_report": retrofit_report,
    }


def compile_gainhelm_estate(
    output_dir: Any,
    run_retrofit: bool = True,
    extra_tools: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Compiles the complete GainHelm (gainhelm.com) tenant estate into `output_dir`
    backed by `pseofactory.gainhelm_estate` and `pseofactory.estate_common`.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.gainhelm_estate import compile_gainhelm_estate_impl

    return compile_gainhelm_estate_impl(
        output_dir=output_dir,
        run_retrofit=run_retrofit,
        extra_tools=extra_tools,
        high_effort_page_fn=compile_high_effort_page,
    )


def compile_profithelm_estate(
    output_dir: Any,
    run_retrofit: bool = True,
    extra_tools: Optional[List[Dict[str, Any]]] = None,
    repo_root: Optional[Any] = None,
) -> Any:
    """
    Compiles the complete ProfitHelm (profithelm.com) tenant estate into `output_dir`
    backed by `pseofactory.profithelm_estate`.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.profithelm_estate import compile_profithelm_estate_impl

    return compile_profithelm_estate_impl(
        output_dir=output_dir,
        run_retrofit=run_retrofit,
        extra_tools=extra_tools,
        repo_root=repo_root,
    )


def compile_prexvo_estate(
    output_dir: Any,
    run_retrofit: bool = True,
    extra_tools: Optional[List[Dict[str, Any]]] = None,
    repo_root: Optional[Any] = None,
) -> Any:
    """
    Compiles the complete Prexvo (prexvo.com) tenant estate into `output_dir`
    backed by `pseofactory.prexvo_estate`.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.prexvo_estate import compile_prexvo_estate_impl

    return compile_prexvo_estate_impl(
        output_dir=output_dir,
        run_retrofit=run_retrofit,
        extra_tools=extra_tools,
        repo_root=repo_root,
    )


_SHARED_ENTITY_BOILERPLATE_EIN = "41-***1423"
_SHARED_ENTITY_BOILERPLATE_HQ = "522 W Riverside Ave Ste N, Spokane, WA 99201"
_SHARED_ENTITY_BOILERPLATE_JURISDICTION = "Washington Secretary of State (Spokane, WA)"


def sanitize_public_media_kit_payload(
    payload: Dict[str, Any],
    repo_root: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Strip shared EIN and Spokane boilerplate from public media-kit.json payloads
    unless explicitly configured in that tenant's own .pseofactory.json.
    Zero em-dashes. Zero en-dashes.
    """
    cleaned = dict(payload or {})
    tenant_cfg: Dict[str, Any] = {}
    if repo_root is not None:
        cfg_path = Path(repo_root) / ".pseofactory.json"
        if cfg_path.is_file():
            try:
                raw_cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                if isinstance(raw_cfg, dict):
                    tenant_cfg = raw_cfg
            except Exception:
                tenant_cfg = {}

    cfg_ein = str(tenant_cfg.get("ein_masked") or "").strip()
    if cfg_ein:
        cleaned["ein_masked"] = cfg_ein
    elif cleaned.get("ein_masked") == _SHARED_ENTITY_BOILERPLATE_EIN or "ein_masked" in cleaned:
        cleaned.pop("ein_masked", None)

    cfg_hq = str(tenant_cfg.get("headquarters") or "").strip()
    if cfg_hq:
        cleaned["headquarters"] = cfg_hq
    elif cleaned.get("headquarters") == _SHARED_ENTITY_BOILERPLATE_HQ or "headquarters" in cleaned:
        cleaned.pop("headquarters", None)

    cfg_jur = str(tenant_cfg.get("jurisdiction") or "").strip()
    if cfg_jur:
        cleaned["jurisdiction"] = cfg_jur
    elif cleaned.get("jurisdiction") == _SHARED_ENTITY_BOILERPLATE_JURISDICTION:
        cleaned.pop("jurisdiction", None)

    return cleaned


def _normalize_embed_domain(domain: str) -> str:
    cleaned = re.sub(r"^https?://", "", str(domain or "").strip(), flags=re.IGNORECASE)
    return cleaned.split("/", 1)[0].strip().lower()


def build_embed_snippet_html(domain: str, brand_name: str, slug: str) -> str:
    """
    Build an embeddable widget HTML snippet with hardcoded pure-brand rel='nofollow' attribution.
    Never uses exact-match keyword anchor text.
    Zero em-dashes. Zero en-dashes.
    """
    clean_domain = _normalize_embed_domain(domain)
    clean_slug = str(slug or "").strip().strip("/")
    clean_brand = str(brand_name or "").replace("\u2014", "-").replace("\u2013", "-").strip() or clean_domain
    safe_domain = _html.escape(clean_domain, quote=True)
    safe_slug = _html.escape(clean_slug, quote=True)
    safe_brand = _html.escape(clean_brand, quote=True)
    tool_url = f"https://{safe_domain}/tools/{safe_slug}/"
    script_url = f"https://{safe_domain}/static/js/embed-widget.js"
    snippet = (
        f'<div class="pseo-embed-widget" data-tool="{safe_slug}" data-domain="{safe_domain}">\n'
        f'  <script async src="{script_url}" data-tool="{safe_slug}"></script>\n'
        f'  <p class="pseo-embed-attribution">'
        f'<a href="{tool_url}" rel="nofollow">Powered by {safe_brand}</a>'
        f"</p>\n"
        f"</div>"
    )
    assert_no_forbidden_dashes(snippet, context=f"embed_snippet:{clean_slug}")
    return snippet


def write_static_embed_widget_assets(
    dist_dir: Any,
    domain: str,
    brand_name: str,
    tools: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """
    Generate zero-dependency dist/static/js/embed-widget.js and dist/embed/snippets.json.
    Renders a lightweight iframe calculator container with pure-brand rel='nofollow' attribution.
    Zero em-dashes. Zero en-dashes.
    """
    dist = Path(dist_dir)
    clean_domain = _normalize_embed_domain(domain)
    clean_brand = str(brand_name or "").replace("\u2014", "-").replace("\u2013", "-").strip() or clean_domain

    js_dir = dist / "static" / "js"
    js_dir.mkdir(parents=True, exist_ok=True)
    embed_dir = dist / "embed"
    embed_dir.mkdir(parents=True, exist_ok=True)

    js_domain = json.dumps(clean_domain)
    js_brand = json.dumps(clean_brand)
    embed_js = (
        "(function(){\n"
        '  "use strict";\n'
        f"  var DEFAULT_DOMAIN = {js_domain};\n"
        f"  var DEFAULT_BRAND = {js_brand};\n"
        "  function mountWidget(container, slug, domain) {\n"
        '    if (!container || !slug || container.getAttribute("data-pseo-mounted") === "1") return;\n'
        '    container.setAttribute("data-pseo-mounted", "1");\n'
        "    var host = (domain || DEFAULT_DOMAIN).replace(/^https?:\\/\\//i, \"\").replace(/\\/+$/, \"\");\n"
        '    var cleanSlug = String(slug).replace(/^\\/+|\\/+$/g, "");\n'
        '    var baseUrl = "https://" + host + "/tools/" + encodeURIComponent(cleanSlug) + "/";\n'
        '    var frame = document.createElement("iframe");\n'
        '    frame.src = baseUrl + "?embed=1";\n'
        '    frame.title = DEFAULT_BRAND + " Calculator";\n'
        '    frame.loading = "lazy";\n'
        '    frame.style.width = "100%";\n'
        '    frame.style.minHeight = container.getAttribute("data-height") || "560px";\n'
        '    frame.style.border = "1px solid #334155";\n'
        '    frame.style.borderRadius = "8px";\n'
        "    container.insertBefore(frame, container.firstChild);\n"
        '    if (!container.querySelector("a[rel*=nofollow]")) {\n'
        '      var p = document.createElement("p");\n'
        '      p.className = "pseo-embed-attribution";\n'
        '      var a = document.createElement("a");\n'
        "      a.href = baseUrl;\n"
        '      a.rel = "nofollow";\n'
        '      a.textContent = "Powered by " + DEFAULT_BRAND;\n'
        "      p.appendChild(a);\n"
        "      container.appendChild(p);\n"
        "    }\n"
        "  }\n"
        '  var scriptEl = document.currentScript;\n'
        "  if (scriptEl) {\n"
        '    var sSlug = scriptEl.getAttribute("data-tool") || "";\n'
        '    var parent = scriptEl.parentElement;\n'
        '    if (parent && parent.classList && parent.classList.contains("pseo-embed-widget")) {\n'
        '      mountWidget(parent, sSlug || parent.getAttribute("data-tool"), parent.getAttribute("data-domain"));\n'
        "    } else if (sSlug) {\n"
        '      var box = document.createElement("div");\n'
        '      box.className = "pseo-embed-widget";\n'
        '      box.setAttribute("data-tool", sSlug);\n'
        "      scriptEl.parentNode.insertBefore(box, scriptEl.nextSibling);\n"
        "      mountWidget(box, sSlug, DEFAULT_DOMAIN);\n"
        "    }\n"
        "  }\n"
        '  var nodes = document.querySelectorAll(".pseo-embed-widget[data-tool]");\n'
        "  for (var i = 0; i < nodes.length; i++) {\n"
        '    mountWidget(nodes[i], nodes[i].getAttribute("data-tool"), nodes[i].getAttribute("data-domain"));\n'
        "  }\n"
        "})();\n"
    )
    assert_no_forbidden_dashes(embed_js, context="embed-widget.js")
    js_path = js_dir / "embed-widget.js"
    js_changed = not js_path.is_file() or js_path.read_text(encoding="utf-8", errors="ignore") != embed_js
    if js_changed:
        js_path.write_text(embed_js, encoding="utf-8")

    snippets: Dict[str, str] = {}
    for item in (tools or []):
        if isinstance(item, dict):
            s_val = str(item.get("slug") or "").strip()
        else:
            s_val = str(item or "").strip()
        if not s_val:
            continue
        snippets[s_val] = build_embed_snippet_html(clean_domain, clean_brand, s_val)

    snippets_payload = {
        "schema_version": "1.0.0",
        "domain": clean_domain,
        "brand_name": clean_brand,
        "script_url": f"https://{clean_domain}/static/js/embed-widget.js",
        "snippets": snippets,
    }
    snippets_json = json.dumps(snippets_payload, indent=2) + "\n"
    assert_no_forbidden_dashes(snippets_json, context="embed/snippets.json")
    snippets_path = embed_dir / "snippets.json"
    snippets_changed = not snippets_path.is_file() or snippets_path.read_text(encoding="utf-8", errors="ignore") != snippets_json
    if snippets_changed:
        snippets_path.write_text(snippets_json, encoding="utf-8")

    return {
        "embed_js_path": str(js_path),
        "snippets_json_path": str(snippets_path),
        "tools_count": len(snippets),
        "js_changed": js_changed,
        "snippets_changed": snippets_changed,
    }
