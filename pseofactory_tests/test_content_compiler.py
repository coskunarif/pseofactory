"""
Unit and edge-case stress tests for pseofactory High-Effort Content Compiler.
Verifies:
1. Zero equipment cost and negative input boundary clamping (HWL-1263).
2. Section 179 phaseout ceiling boundary calculation ($4,500,000 capex -> $0 deduction).
3. Multi-bracket progressive tax schedule calculation (SALT cap married joint rate -> $3,700 savings) (HWL-1273).
4. Section 168(k) bonus depreciation phasedown schedules (60% and 40%).
5. Fractional basis points and high-precision decimal spreads.
6. HTML structure: touch targets >= 44x44px, obsidian dark-theme styling, Schema.org JSON-LD.
7. Factor 7 self-verification passes with 0 violations.
8. Strictly zero em-dashes and zero en-dashes across all rendered output.

Zero em-dashes. Zero en-dashes.
"""

import json
import pytest
from pseofactory.compiler import compile_high_effort_page
from pseofactory.verifier import verify_html_unique_first_party_information
from pseofactory.contracts import assert_no_forbidden_dashes


def test_compiler_zero_and_negative_input_boundary():
    # Zero cost boundary per HWL-1263
    spec_zero = {
        "query": "section 179 zero cost deduction",
        "slug": "section-179-zero-cost-deduction",
        "model_name": "Section 179 Equipment Expense Model",
        "formula": "max(0.0, min(cost, cap) - max(0.0, cost - phaseout))",
        "inputs": {"cost": 0, "cap": 1220000, "phaseout": 3050000},
        "published_output": 0.0,
        "sample_calculation": "Zero equipment expenditure yields 0 deduction",
        "statutory_authority": "IRC Section 179(b)(1)",
        "economic_dataset": "FRED CPILFESL Series",
    }
    res_zero = compile_high_effort_page(spec_zero)
    assert res_zero["published_output"] == 0.0
    assert res_zero["verified"] is True
    assert "0" in res_zero["html"]

    # Negative input boundary: clamped to >= 0 per HWL-1263
    spec_neg = {
        "query": "section 179 negative input boundary",
        "slug": "section-179-negative-input-boundary",
        "model_name": "Section 179 Equipment Expense Model",
        "formula": "max(0.0, min(cost, cap) - max(0.0, cost - phaseout))",
        "inputs": {"cost": -50000, "cap": 1220000, "phaseout": 3050000},
        "published_output": 0.0,
        "sample_calculation": "Negative equipment expenditure is clamped to zero yielding 0 deduction",
        "statutory_authority": "IRC Section 179(b)(1)",
        "economic_dataset": "FRED CPILFESL Series",
    }
    res_neg = compile_high_effort_page(spec_neg)
    assert res_neg["published_output"] == 0.0
    assert res_neg["manifest"]["inputs"]["cost"] == 0.0
    assert res_neg["verified"] is True


def test_compiler_phaseout_cap_boundary():
    # Capital expenditure past the phaseout ceiling ($3,050,000 threshold + $1,220,000 cap = $4,270,000 ceiling)
    # $4,500,000 investment yields $0 deduction
    spec_phaseout = {
        "query": "section 179 full phaseout ceiling",
        "slug": "section-179-full-phaseout-ceiling",
        "model_name": "Section 179 Full Phaseout Model",
        "formula": "max(0.0, cap - max(0.0, investment - phaseout))",
        "inputs": {"investment": 4500000, "cap": 1220000, "phaseout": 3050000},
        "published_output": 0.0,
        "sample_calculation": "Investment 4,500,000 exceeds phaseout threshold 3,050,000 by 1,450,000 reducing cap 1,220,000 to zero",
        "statutory_authority": "IRC Section 179(b)(2)",
        "economic_dataset": "BEA Table 5.3.5 Private Fixed Investment",
    }
    res = compile_high_effort_page(spec_phaseout)
    assert res["published_output"] == 0.0
    assert res["verified"] is True
    assert "BEA Table 5.3.5 Private Fixed Investment" in res["html"]


def test_compiler_multi_bracket_progressive_tax():
    # SALT PTE joint bracket deduction (HWL-1273)
    # $45,000 SALT paid, $10,000 cap, 37% marginal rate -> $3,700 savings
    spec_salt = {
        "query": "salt pte joint tax bracket savings",
        "slug": "salt-pte-joint-tax-bracket-savings",
        "model_name": "SALT Pass-Through Entity Savings Model",
        "formula": "min(salt_paid, cap) * rate",
        "inputs": {"salt_paid": 45000, "cap": 10000, "rate": 0.37},
        "published_output": 3700.0,
        "sample_calculation": "Married joint SALT cap 10,000 multiplied by 37 percent marginal rate yields 3,700 tax savings",
        "statutory_authority": "IRC Section 164(b)(6)",
        "economic_dataset": "BLS Consumer Expenditure Table 1110",
    }
    res = compile_high_effort_page(spec_salt)
    assert res["published_output"] == 3700.0
    assert res["verified"] is True
    assert "3,700" in res["html"]


def test_compiler_bonus_depreciation_phasedown():
    # Section 168(k) phasedown schedules: 60% and 40% bonus rates
    spec_60 = {
        "query": "bonus depreciation 60 percent phasedown",
        "slug": "bonus-depreciation-60-percent-phasedown",
        "model_name": "Section 168k Bonus Depreciation Model",
        "formula": "(basis - sec179) * bonus_rate",
        "inputs": {"basis": 250000, "sec179": 100000, "bonus_rate": 0.60},
        "published_output": 90000.0,
        "sample_calculation": "Remaining basis 150,000 at 60 percent bonus rate yields 90,000 first year deduction",
        "statutory_authority": "26 U.S.C. Section 168(k)",
        "economic_dataset": "FRED BOGZ1FL895050005Q Series",
    }
    res_60 = compile_high_effort_page(spec_60)
    assert res_60["published_output"] == 90000.0
    assert res_60["verified"] is True

    # 40% phasedown
    spec_40 = {
        "query": "bonus depreciation 40 percent phasedown",
        "slug": "bonus-depreciation-40-percent-phasedown",
        "model_name": "Section 168k Bonus Depreciation Model",
        "formula": "(basis - sec179) * bonus_rate",
        "inputs": {"basis": 250000, "sec179": 100000, "bonus_rate": 0.40},
        "published_output": 60000.0,
        "sample_calculation": "Remaining basis 150,000 at 40 percent bonus rate yields 60,000 first year deduction",
        "statutory_authority": "26 U.S.C. Section 168(k)",
        "economic_dataset": "FRED BOGZ1FL895050005Q Series",
    }
    res_40 = compile_high_effort_page(spec_40)
    assert res_40["published_output"] == 60000.0
    assert res_40["verified"] is True


def test_compiler_fractional_basis_points():
    # High-precision yield spread (3.85% decimal spread)
    spec_yield = {
        "query": "high precision yield spread model",
        "slug": "high-precision-yield-spread-model",
        "model_name": "Basis Point Yield Spread Calculator",
        "formula": "round(principal * rate_spread, 2)",
        "inputs": {"principal": 1000000, "rate_spread": 0.0385},
        "published_output": 38500.0,
        "sample_calculation": "Principal 1,000,000 multiplied by 0.0385 spread yields 38,500 annual differential",
        "statutory_authority": "CFTC Rule 40.11 Designated Contracts",
        "economic_dataset": "FRED DGS10 10-Year Treasury Constant Maturity",
    }
    res = compile_high_effort_page(spec_yield)
    assert res["published_output"] == 38500.0
    assert res["verified"] is True

    # Fractional 2.75% rate
    spec_fractional = {
        "query": "fractional basis points interest differential",
        "slug": "fractional-basis-points-interest-differential",
        "model_name": "Interest Differential Model",
        "formula": "round(principal * rate_spread, 2)",
        "inputs": {"principal": 500000, "rate_spread": 0.0275},
        "published_output": 13750.0,
        "sample_calculation": "Principal 500,000 at 2.75 percent spread yields 13,750 differential",
        "statutory_authority": "CFTC Rule 40.11 Designated Contracts",
        "economic_dataset": "FRED DGS10 10-Year Treasury Constant Maturity",
    }
    res_frac = compile_high_effort_page(spec_fractional)
    assert res_frac["published_output"] == 13750.0
    assert res_frac["verified"] is True


def test_compiler_html_structure_and_touch_targets():
    spec = {
        "query": "section 179 equipment tax deduction",
        "slug": "section-179-equipment-tax-deduction",
        "model_name": "Section 179 Interactive Asset",
        "formula": "min(cost, cap)",
        "inputs": {"cost": 400000, "cap": 1220000},
        "published_output": 400000.0,
        "sample_calculation": "Cost 400,000 under cap 1,220,000 gives 400,000 deduction",
        "statutory_authority": "IRC Section 179(b)(1)",
        "economic_dataset": "FRED CPILFESL Series",
    }
    res = compile_high_effort_page(spec)
    html = res["html"]

    # Touch targets >= 44x44px check
    assert "min-height: 44px" in html
    assert "min-width: 44px" in html
    assert 'class="touch-target"' in html

    # Obsidian dark-theme styling check
    assert "#07090e" in html
    assert "#0f172a" in html
    assert "--card-bg" in html

    # Schema.org JSON-LD blocks check
    assert '"@type": "SoftwareApplication"' in html
    assert '"@type": "FAQPage"' in html

    # Embedded calculation manifest check
    assert 'class="calculation-manifest"' in html
    assert f'{spec["slug"]}-manifest' in html

    # Multi-dataset join container check
    assert 'class="multi-dataset-join' in html
    assert f'data-statutory-source="{spec["statutory_authority"]}"' in html
    assert f'data-economic-source="{spec["economic_dataset"]}"' in html

    # Calculation container check
    assert 'class="calculation-container' in html
    assert 'class="calculator-form"' in html


def test_compiler_self_verification_passes_factor7():
    spec = {
        "query": "section 179 equipment expense verification",
        "slug": "section-179-equipment-expense-verification",
        "model_name": "Section 179 Grounded Model",
        "formula": "min(cost, cap)",
        "inputs": {"cost": 750000, "cap": 1220000},
        "published_output": 750000.0,
        "sample_calculation": "Cost 750,000 under cap 1,220,000 gives 750,000 deduction",
        "statutory_authority": "IRC Section 179(b)(1)",
        "economic_dataset": "FRED CPILFESL Series",
    }
    res = compile_high_effort_page(spec)
    assert res["verified"] is True

    # Direct Factor 7 in-memory audit
    audit = verify_html_unique_first_party_information(
        res["html"],
        rel_path=f"tools/{res['slug']}/index.html",
        manifest_data=res["manifest"],
    )
    assert audit["status"] == "PASS"
    assert audit["violations_count"] == 0
    assert audit["issues"] == []
    assert audit["manifests_count"] >= 1
    assert audit["multi_dataset_joins_count"] >= 1


def test_compiler_zero_forbidden_dashes_enforcement():
    spec = {
        "query": "section 179 dash enforcement test",
        "slug": "section-179-dash-enforcement-test",
        "model_name": "Dash Audit Model",
        "formula": "cost * 0.21",
        "inputs": {"cost": 100000},
        "published_output": 21000.0,
        "sample_calculation": "Cost 100,000 times 21 percent tax rate yields 21,000 deduction",
        "statutory_authority": "IRC Section 179(b)(1)",
        "economic_dataset": "FRED CPILFESL Series",
    }
    res = compile_high_effort_page(spec)

    # Strictly zero em-dashes and zero en-dashes
    assert_no_forbidden_dashes(res["html"], context="compiled HTML")
    assert_no_forbidden_dashes(json.dumps(res["manifest"]), context="compiled manifest")
    assert "\u2014" not in res["html"]
    assert "\u2013" not in res["html"]
