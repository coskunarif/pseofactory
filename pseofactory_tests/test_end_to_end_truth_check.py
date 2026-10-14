"""
End-to-End Truth Check Test Suite for pseofactory Substrate.
Verifies cross-referencing of tables, calculator outputs, and headline claims
against official statutory rules and verified financial benchmarks for both
ProfitHelm and Prexvo.
Zero em-dashes. Zero en-dashes.
"""

import json
import pytest

from pseofactory.audit import audit_rendered_asset
from pseofactory.contracts import (
    STATUTORY_LIMITS,
    STATUTORY_TAX_BRACKETS,
    detect_uncorroborated_statutory_claims,
)
from pseofactory.maintenance import LiveTruthAuditEngine
from pseofactory.tenant_facts import TenantFactStore


def test_statutory_brackets_and_obbba_section_179_constants():
    """Verifies 2026/2027 statutory tax brackets and 2026 OBBBA Section 179 limits."""
    assert STATUTORY_LIMITS["section_179_max_deduction"][2026] == 2560000.0
    assert STATUTORY_LIMITS["section_179_phaseout_threshold"][2026] == 4090000.0
    assert STATUTORY_LIMITS["section_179_heavy_vehicle_suv"][2026] == 30500.0

    b2026_single = STATUTORY_TAX_BRACKETS[2026]["single"]
    assert b2026_single[0]["max_income"] == 12050.0
    assert b2026_single[1]["max_income"] == 48900.0
    assert b2026_single[2]["max_income"] == 104400.0

    b2027_single = STATUTORY_TAX_BRACKETS[2027]["single"]
    assert b2027_single[0]["max_income"] == 12200.0
    assert b2027_single[1]["max_income"] == 49600.0
    assert b2027_single[2]["max_income"] == 120200.0
    assert b2027_single[-1]["rate"] == 39.6

    clean_claims = (
        "Under 2026 OBBBA rules, the Section 179 deduction limit is $2,560,000 with a "
        "$4,090,000 phase-out threshold and $30,500 heavy SUV cap."
    )
    assert detect_uncorroborated_statutory_claims(clean_claims) == []


def test_tenant_fact_store_rejects_stale_profithelm_and_prexvo_claims():
    """Verifies TenantFactStore fail-closed rejection of stale figures on both properties."""
    store = TenantFactStore()

    # Valid ProfitHelm claims pass
    ok_ph, v_ph = store.verify_claim(
        "profithelm",
        "For a $125,000 single earner, federal tax increases by $4,349 (+22.7%), moving from $19,181 to $23,530. Full Cap ($2.56M).",
    )
    assert ok_ph is True
    assert v_ph == []

    # Stale ProfitHelm claims fail closed
    for stale_ph in (
        "Moving from $18,340 under TCJA to $22,238 post-sunset.",
        "Increases federal tax liability by $3,898 (+21.3%).",
        "Federal income tax accounts for $29,238 on $150k in California.",
        "GVWR: 8,500 lbs - Full Cap ($1.29M)",
    ):
        ok, violations = store.verify_claim("profithelm", stale_ph)
        assert ok is False, f"Expected stale claim to fail: {stale_ph}"
        assert len(violations) >= 1

    # Valid Prexvo claims pass
    ok_px, v_px = store.verify_claim(
        "prexvo",
        "Scenario A yields $248.23 monthly payment, $76.77 monthly interest subsidy, and $59,575.20 over 20 years. "
        "Scenario B yields $498.23 monthly payment and $78,617.64 across 158 months. "
        "<td>10% to 15% Discretionary</td>",
    )
    assert ok_px is True
    assert v_px == []

    # Stale Prexvo claims fail closed
    for stale_px in (
        "Scenario A required monthly payment is $244.58 with $58,700 total.",
        "Scenario B required monthly payment is $494.58 with $118,700 total.",
        '<div id="metric-rap_payment" class="calc-metric-value">$0.00</div>',
        "<td>15% Discretionary</td>",
    ):
        ok, violations = store.verify_claim("prexvo", stale_px)
        assert ok is False, f"Expected stale Prexvo claim to fail: {stale_px}"
        assert len(violations) >= 1


def test_live_truth_audit_engine_end_to_end_verification():
    """Verifies LiveTruthAuditEngine cross-checks manifests, scenario tables, and proprietary calculation tables."""
    engine = LiveTruthAuditEngine()

    valid_html = """
    <html>
      <body>
        <span class="output-value">$248.23</span>
        <script type="application/json" class="calculation-manifest">
          {"formula": "round((agi * 0.05) / 12 - (dependents * 50 / 12), 2)", "inputs": {"agi": 60000, "dependents": 1}, "published_output": 245.83}
        </script>
      </body>
    </html>
    """
    # Notice published_output 245.83 matches formula, but .output-value is 248.23 -> must flag mismatch
    violations_mismatch = engine.audit_html(valid_html, property_id="prexvo", context="test_mismatch.html")
    assert any("SSR .output-value" in v for v in violations_mismatch)

    aligned_html = """
    <html>
      <body>
        <span class="output-value">$245.83</span>
        <script type="application/json" class="calculation-manifest">
          {"formula": "round((agi * 0.05) / 12 - (dependents * 50 / 12), 2)", "inputs": {"agi": 60000, "dependents": 1}, "published_output": 245.83}
        </script>
        <table class="scenario-table">
          <tbody>
            <tr><td>0.8x</td><td>$196.66</td><td>$196.66</td><td>$2,359.97</td></tr>
            <tr><td>0.9x</td><td>$221.25</td><td>$221.25</td><td>$2,654.96</td></tr>
            <tr><td>1.0x</td><td>$245.83</td><td>$245.83</td><td>$2,949.96</td></tr>
            <tr><td>1.1x</td><td>$270.41</td><td>$270.41</td><td>$3,244.96</td></tr>
            <tr><td>1.2x</td><td>$295.00</td><td>$295.00</td><td>$3,539.95</td></tr>
          </tbody>
        </table>
      </body>
    </html>
    """
    assert engine.audit_html(aligned_html, property_id="prexvo", context="aligned.html") == []

    # Corrupt 1.2x row in scenario-table -> must fail closed
    corrupted_scenario = aligned_html.replace("$295.00", "$999.00")
    v_scen = engine.audit_html(corrupted_scenario, property_id="prexvo", context="corrupt_scenario.html")
    assert any("Scenario table row 1.2x" in v for v in v_scen)

    # Proprietary calculation table arithmetic check
    prop_table_ok = """
    <html>
      <body>
        <table class="proprietary-calculation-table">
          <tbody>
            <tr><td>Conservative Baseline</td><td>$100,000</td><td>$15,000</td><td>-2.5%</td><td>$85,000</td></tr>
          </tbody>
        </table>
      </body>
    </html>
    """
    assert engine.audit_html(prop_table_ok, property_id="profithelm", context="prop_ok.html") == []

    prop_table_bad = prop_table_ok.replace("$85,000", "$91,000")
    v_prop = engine.audit_html(prop_table_bad, property_id="profithelm", context="prop_bad.html")
    assert any("Proprietary table row arithmetic drift" in v for v in v_prop)
