"""
Test Suite: Unified Zero-Bypass Fail-Closed Truth Gate & Executable Python-vs-JS Math Parity
Path: pseofactory/pseofactory_tests/test_truth_gate.py

Zero em-dashes. Zero en-dashes.
"""

from datetime import date
import json
from pathlib import Path
import pytest

from pseofactory.truth_gate import (
    TruthGateReport,
    TruthViolation,
    UnifiedTruthGate,
    audit_tenant_truth_fail_closed,
    verify_live_js_math_parity,
)


def _make_tax_pack(
    *,
    property_id: str = "profithelm",
    brand_name: str = "ProfitHelm",
    canonical_domain: str = "https://profithelm.com",
    expires_at: str = "2027-12-31",
    entry_expires_at: str = "2027-12-31",
) -> dict:
    return {
        "property_id": property_id,
        "brand_name": brand_name,
        "canonical_domain": canonical_domain,
        "expires_at": expires_at,
        "allowed_shared_legal_tokens": ["irc", "obbba", "treasury", "irs"],
        "affiliate_tokens": ["turbotax", "crest_capital"],
        "pricing_tiers": {
            "free": {"name": "Free", "price_usd": 0.0},
            "quick": {"name": "Quick Worksheet", "price_usd": 15.0},
            "full": {"name": "Full Workpaper", "price_usd": 29.0},
            "partner": {"name": "Partner Slot", "price_usd": 299.0},
        },
        "entries": [
            {
                "id": "std_deduction_single_2026",
                "claim_class": "enacted_law",
                "value": 16100,
                "text": "2026 Single standard deduction $16,100 under Rev. Proc. 2025-32 and 10% to 37% permanent brackets.",
                "superseded_values": [
                    {"value": 15000, "pattern": r"(?:\$15,000|\b15000\b)", "historical_year": 2025},
                ],
                "expires_at": entry_expires_at,
            },
            {
                "id": "heavy_suv_cap_2026",
                "claim_class": "enacted_law",
                "value": 30500,
                "text": "IRC Section 179 heavy SUV deduction cap is $30,500; equipment cap is $2,560,000.",
                "superseded_values": [
                    {"value": "$30,500_2024_only", "pattern": r"\$30,500", "historical_year": 2024},
                    {"value": "$2,560,000_suv", "pattern": r"heavy\s+SUVs?\s+capped\s+at\s+\$2,560,000"},
                ],
                "expires_at": entry_expires_at,
            },
            {
                "id": "qbi_deduction_rate",
                "claim_class": "enacted_law",
                "value": 20,
                "text": "20% Section 199A QBI deduction.",
                "expires_at": entry_expires_at,
            },
            {
                "id": "cpa_prep_fee_benchmark",
                "claim_class": "market_benchmark",
                "value": "$4,500",
                "match_patterns": [r"\$4,500\s+CPA\s+prep"],
                "required_qualifier_patterns": [r"\b(?:estimate|benchmark|range|underwriting|indicative)\b"],
                "expires_at": entry_expires_at,
            },
            {
                "id": "proposed_2028_surtax",
                "claim_class": "future_projection",
                "value": "$12,400",
                "match_patterns": [r"\$12,400\s+future\s+surtax"],
                "required_qualifier_patterns": [r"\b(?:projection|projected|forecast|unenacted|proposed)\b"],
                "expires_at": entry_expires_at,
            },
        ],
        "banned_claims": [
            r"30\.6%\s+reduction\s+in\s+statutory\s+capital\s+drag",
            r"\b3\.0%\s+federal\s+marginal\s+tax\s+bracket\b",
            r"\$30,416\b",
            r"TCJA\s+rates\s+sunset\s+to\s+39\.6%",
        ],
        "citations_allowlist": [
            {"citation": "IRC Section 1(j)", "allowed_slug_patterns": [r"tax-brackets"]},
            {"citation": "26 U.S.C. Section 1(j)", "allowed_slug_patterns": [r"tax-brackets"]},
            {"citation": "IRC Section 179", "allowed_slug_patterns": [r"179", r"vehicle", r"equipment"]},
            {"citation": "IRC Section 199A", "allowed_slug_patterns": [r"qbi", r"199a"]},
            {"citation": "IRC Section 1031", "allowed_slug_patterns": [r"1031"]},
            {
                "citation": "IRC Section 1202",
                "allowed_slug_patterns": [r"qsbs", r"1202"],
                "forbidden_slug_patterns": [r"1031"],
            },
            {"citation": "Rev. Proc. 2025-32"},
            {"citation": "P.L. 119-21"},
        ],
        "disclosures": [
            {
                "id": "circular_230",
                "applies_to_surfaces": ["html"],
                "mandatory_for_all": True,
                "required_text_patterns": [r"Circular\s+230", r"not\s+(?:formal\s+)?tax\s+advice"],
            }
        ],
        "formulas": [
            {
                "id": "irs_2027_tax_brackets",
                "formula": (
                    "round(1240.0 + min(max(0.0, (gross_income - standard_deduction_2026) - 12400.0), 38000.0) * 0.12 "
                    "+ min(max(0.0, (gross_income - standard_deduction_2026) - 50400.0), 55300.0) * 0.22 "
                    "+ max(0.0, (gross_income - standard_deduction_2026) - 105700.0) * 0.24, 0)"
                ),
                "allowed_slug_patterns": [r"irs-2027-tax-brackets"],
                "primary_metric_id": "val-total_federal_tax",
                "allowed_widget_ids": ["val-total_federal_tax"],
                "test_vectors": [
                    {"inputs": {"gross_income": 125000.0, "standard_deduction_2026": 16100.0}, "expected": 18734.0},
                    {"inputs": {"gross_income": 200000.0, "standard_deduction_2026": 16100.0}, "expected": 36734.0},
                ],
            },
            {
                "id": "qbi_deduction_model",
                "formula": "round(qbi * 0.20, 2)",
                "allowed_slug_patterns": [r"qbi-deduction"],
                "primary_metric_id": "val-qbi_deduction",
                "allowed_widget_ids": ["val-qbi_deduction"],
                "forbidden_widget_ids": ["val-total_federal_tax"],
                "test_vectors": [
                    {"inputs": {"qbi": 100000.0}, "expected": 20000.0},
                    {"inputs": {"qbi": 250000.0}, "expected": 50000.0},
                ],
            },
        ],
    }


def _make_lienbond_pack() -> dict:
    return {
        "property_id": "lienbond",
        "brand_name": "LienBond",
        "canonical_domain": "https://lienbond.com",
        "expires_at": "2027-12-31",
        "allowed_shared_legal_tokens": ["treasury", "circular 570"],
        "affiliate_tokens": ["surety_bonds_direct"],
        "pricing_tiers": {
            "free": {"name": "Free", "price_usd": 0.0},
            "quick": {"name": "Quick Worksheet", "price_usd": 15.0},
            "full": {"name": "Full Workpaper", "price_usd": 29.0},
        },
        "entries": [
            {
                "id": "miller_act_threshold",
                "claim_class": "enacted_law",
                "value": 150000,
                "text": "Federal Miller Act 40 U.S.C. 3131 requires bonds on contracts over $150,000.",
                "expires_at": "2027-12-31",
            }
        ],
        "banned_claims": [],
        "citations_allowlist": [
            {"citation": "40 U.S.C. 3131"},
            {
                "citation": "IRC Section 3111",
                "forbidden_slug_patterns": [r"workers-comp", r"emr"],
            },
            {
                "citation": "29 CFR Part 1904",
                "forbidden_slug_patterns": [r"workers-comp", r"emr"],
            },
        ],
        "disclosures": [
            {
                "id": "surety_underwriting",
                "applies_to_surfaces": ["html"],
                "mandatory_for_all": True,
                "required_text_patterns": [r"underwriting\s+and\s+state\s+statutory\s+schedules"],
            }
        ],
        "formulas": [
            {
                "id": "contractor_license_bond",
                "formula": "round(bond_amount * (rate_pct / 100.0) * term_years, 2)",
                "allowed_slug_patterns": [r"contractor-license-bond"],
                "forbidden_slug_patterns": [r"bid-bond"],
                "primary_metric_id": "metric-license_bond_premium",
            },
            {
                "id": "bid_bond_capacity",
                "formula": "round(contract_sum * (bid_pct / 100.0), 2)",
                "allowed_slug_patterns": [r"bid-bond"],
                "primary_metric_id": "metric-bid_bond_penal_sum",
            },
        ],
    }


def _make_gainhelm_pack() -> dict:
    return {
        "property_id": "gainhelm",
        "brand_name": "GainHelm",
        "canonical_domain": "https://gainhelm.com",
        "expires_at": "2027-12-31",
        "allowed_shared_legal_tokens": ["treasury", "nist"],
        "affiliate_tokens": ["vanta_security"],
        "pricing_tiers": {"free": {"price_usd": 0.0}, "quick": {"price_usd": 15.0}, "full": {"price_usd": 29.0}},
        "entries": [],
        "banned_claims": [],
        "citations_allowlist": [],
        "disclosures": [
            {
                "id": "c3pao_assessment_disclaimer",
                "applies_to_surfaces": ["html"],
                "applies_to_content_patterns": [r"\bc3pao\b|\bcmmc\b"],
                "required_text_patterns": [r"not\s+a\s+licensed\s+C3PAO\s+assessment\s+organization"],
            }
        ],
        "formulas": [],
    }


def _build_compliant_tax_html(
    *,
    slug: str = "irs-2027-tax-brackets",
    title: str = "IRS 2027 Tax Brackets Calculator",
    gross_income: float = 125000.0,
    std_ded: float = 16100.0,
    published_output: float = 18734.0,
    ssr_output_str: str = "$18,734",
    metric_id: str = "val-total_federal_tax",
    metric_val_str: str = "$18,734",
    extra_body: str = "",
    extra_js_calc: str = "",
    jsonld_override: str = "",
    include_scenario_table: bool = True,
) -> str:
    manifest = {
        "formula_id": "irs_2027_tax_brackets",
        "formula": (
            "round(1240.0 + min(max(0.0, (gross_income - standard_deduction_2026) - 12400.0), 38000.0) * 0.12 "
            "+ min(max(0.0, (gross_income - standard_deduction_2026) - 50400.0), 55300.0) * 0.22 "
            "+ max(0.0, (gross_income - standard_deduction_2026) - 105700.0) * 0.24, 0)"
        ),
        "inputs": {"gross_income": gross_income, "standard_deduction_2026": std_ded},
        "published_output": published_output,
    }
    jsonld_block = jsonld_override or json.dumps({
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "SoftwareApplication",
                "name": title,
                "offers": {"@type": "Offer", "price": "15.00", "priceCurrency": "USD"},
            },
            {"@type": "BreadcrumbList", "itemListElement": []},
        ],
    })
    scenario_html = ""
    if include_scenario_table:
        scenario_html = f"""
        <table class="scenario-table">
          <tbody>
            <tr><td>0.8x</td><td>Conservative</td><td>${published_output * 0.8:,.2f}</td></tr>
            <tr><td>0.9x</td><td>Moderate</td><td>${published_output * 0.9:,.2f}</td></tr>
            <tr><td>1.0x</td><td>Baseline</td><td><strong class="scenario-baseline">${published_output:,.2f}</strong></td></tr>
            <tr><td>1.1x</td><td>Expansion</td><td>${published_output * 1.1:,.2f}</td></tr>
            <tr><td>1.2x</td><td>Aggressive</td><td>${published_output * 1.2:,.2f}</td></tr>
          </tbody>
        </table>
        """

    js_calc = extra_js_calc or """
        var taxable = Math.max(0, inputs.gross_income - inputs.standard_deduction_2026);
        var tax = 1240.0
          + Math.min(Math.max(0.0, taxable - 12400.0), 38000.0) * 0.12
          + Math.min(Math.max(0.0, taxable - 50400.0), 55300.0) * 0.22
          + Math.max(0.0, taxable - 105700.0) * 0.24;
        return Math.round(tax);
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{title} | ProfitHelm</title>
  <link rel="canonical" href="https://profithelm.com/tools/{slug}/" />
  <script type="application/ld+json">{jsonld_block}</script>
</head>
<body>
  <h1>{title}</h1>
  <p>Evaluated under 26 U.S.C. Section 1(j), P.L. 119-21, and Rev. Proc. 2025-32 ($16,100 standard deduction). Official guidance: <a href="https://www.irs.gov/pub/irs-drop/rp-25-32.pdf" rel="noopener">IRS Rev. Proc. 2025-32</a>.</p>
  <form class="calculator-form" id="{slug}-calculator">
    <input type="number" id="input-gross_income" name="gross_income" value="{gross_income}" />
    <input type="number" id="input-standard_deduction_2026" name="standard_deduction_2026" value="{std_ded}" />
  </form>
  <div class="result-box">
    <strong class="output-value">{ssr_output_str}</strong>
    <div id="{metric_id}" class="calc-metric-value">{metric_val_str}</div>
  </div>
  {scenario_html}
  {extra_body}
  <footer>
    <p>Circular 230 Notice: Informational modeling only, not formal tax advice.</p>
  </footer>
  <script type="application/json" id="calculation-manifest" class="calculation-manifest">
  {json.dumps(manifest)}
  </script>
  <script>
  (function() {{
    var form = document.getElementById("{slug}-calculator");
    if (!form) return;
    var out = document.querySelector(".output-value");
    var metric = document.getElementById("{metric_id}");
    function getInputs() {{
      var els = form.querySelectorAll("input[type='number'], select");
      var inp = {{}};
      for (var i = 0; i < els.length; i++) {{
        var n = (els[i].name || els[i].id || "").replace(/^input-/, "");
        var v = parseFloat(els[i].value);
        inp[n] = isNaN(v) ? 0 : Math.max(0, v);
      }}
      return inp;
    }}
    function calculate(inputs) {{
      {js_calc}
    }}
    function recompute() {{
      var val = calculate(getInputs());
      var fmt = "$" + new Intl.NumberFormat("en-US", {{maximumFractionDigits: 0}}).format(val);
      if (out) out.textContent = fmt;
      if (metric) metric.textContent = fmt;
    }}
    recompute();
    form.addEventListener("input", recompute);
    form.addEventListener("change", recompute);
    form.addEventListener("submit", function(e) {{ e.preventDefault(); recompute(); }});
  }})();
  </script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Gate 1: Truth Pack Presence, Validity & Expiry
# ---------------------------------------------------------------------------

def test_missing_truth_pack_for_synthetic_fifth_site_fails_closed(tmp_path):
    """Synthetic 5th site with no Truth Pack MUST hard fail (never fall back to profithelm)."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><body><h1>Site 5</h1></body></html>", encoding="utf-8")

    gate = UnifiedTruthGate(all_truth_packs={"profithelm": _make_tax_pack()})
    report = gate.audit_estate(dist, property_id="synthetic_site_5")
    assert report.passed is False
    assert report.status == "FAIL"
    assert any(
        v.gate == "GATE_TRUTH_PACK" and v.code == "TRUTH_PACK_MISSING"
        for v in report.violations
    )


def test_expired_truth_pack_entry_fails_closed(tmp_path):
    """Expired Truth Pack or entry (expires_at < as_of) triggers TRUTH_PACK_EXPIRED."""
    expired_pack = _make_tax_pack(expires_at="2027-12-31", entry_expires_at="2025-12-31")
    html = _build_compliant_tax_html()
    gate = UnifiedTruthGate(truth_pack=expired_pack, all_truth_packs={"profithelm": expired_pack})
    report = gate.audit_html_content(
        html,
        property_id="profithelm",
        file_path="tools/irs-2027-tax-brackets/index.html",
        as_of=date(2026, 6, 1),
    )
    assert report.passed is False
    assert any(v.code == "TRUTH_PACK_EXPIRED" for v in report.violations)


def test_empty_or_missing_dist_dir_fails_closed(tmp_path):
    """Missing dist_dir or dist_dir with 0 HTML files MUST fail closed with EMPTY_DIST_DIR."""
    pack = _make_tax_pack()
    gate = UnifiedTruthGate(truth_pack=pack, all_truth_packs={"profithelm": pack})

    missing_rep = gate.audit_estate(tmp_path / "nonexistent_dist", property_id="profithelm")
    assert missing_rep.passed is False
    assert any(v.code == "EMPTY_DIST_DIR" for v in missing_rep.violations)

    empty_dist = tmp_path / "empty_dist"
    empty_dist.mkdir()
    (empty_dist / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
    empty_rep = gate.audit_estate(empty_dist, property_id="profithelm")
    assert empty_rep.passed is False
    assert any(v.code == "EMPTY_DIST_DIR" for v in empty_rep.violations)


def test_fifty_plus_sites_dynamic_scalability():
    """Site #55 with its own TruthPack audits cleanly with zero hardcoded tenant assumptions."""
    pack_55 = {
        "property_id": "site55_medicare",
        "brand_name": "Site55Health",
        "canonical_domain": "https://site55health.com",
        "expires_at": "2028-01-01",
        "allowed_shared_legal_tokens": ["42 cfr"],
        "entries": [
            {
                "id": "part_b_deductible",
                "claim_class": "enacted_law",
                "value": 257,
                "text": "Part B deductible $257 under 42 CFR Part 407.",
                "expires_at": "2028-01-01",
            }
        ],
        "banned_claims": [r"guaranteed\s+medicare\s+approval"],
        "citations_allowlist": [{"citation": "42 CFR Part 407"}],
        "disclosures": [
            {
                "id": "cms_disclaimer",
                "applies_to_surfaces": ["html"],
                "mandatory_for_all": True,
                "required_text_patterns": [r"Not\s+affiliated\s+with\s+CMS"],
            }
        ],
        "formulas": [],
    }
    html = """<!DOCTYPE html>
    <html><head><title>Site55 Tool</title></head>
    <body>
      <p>Part B deductible is $257 under 42 CFR Part 407.</p>
      <footer>Not affiliated with CMS or Medicare.</footer>
    </body></html>"""
    gate = UnifiedTruthGate(
        truth_pack=pack_55,
        all_truth_packs={"profithelm": _make_tax_pack(), "site55_medicare": pack_55},
    )
    rep = gate.audit_html_content(html, property_id="site55_medicare", file_path="index.html")
    assert rep.passed is True, rep.violations


# ---------------------------------------------------------------------------
# Gate 2: Typography Never Silences Downstream Factual Checks
# ---------------------------------------------------------------------------

def test_em_dash_hard_fails_and_does_not_silence_factual_checks():
    """Presence of U+2014 MUST emit FORBIDDEN_DASH AND still catch banned claims and math errors."""
    pack = _make_tax_pack()
    html = _build_compliant_tax_html(
        extra_body="<p>Analysis \u2014 shows a 3.0% federal marginal tax bracket.</p>",
        ssr_output_str="$99,999",
    )
    gate = UnifiedTruthGate(truth_pack=pack, all_truth_packs={"profithelm": pack})
    rep = gate.audit_html_content(
        html,
        property_id="profithelm",
        file_path="tools/irs-2027-tax-brackets/index.html",
    )
    assert rep.passed is False
    codes = {v.code for v in rep.violations}
    assert "FORBIDDEN_DASH" in codes
    assert "BANNED_CLAIM" in codes
    assert "SSR_METRIC_MISMATCH" in codes


# ---------------------------------------------------------------------------
# Gate 3: Banned Claims, Superseded Values in JS, Smart Historical Guard, Stats, Qualifiers
# ---------------------------------------------------------------------------

def test_js_stale_std_deduction_caught_inside_script_and_external_js(tmp_path):
    """Catches `const tcjaStdDed = { single: 15000 }` right inside <script> and external .js."""
    pack = _make_tax_pack()
    html = _build_compliant_tax_html(
        extra_body="",
        extra_js_calc="const tcjaStdDed = { single: 15000 }; return 18734;",
        run_if_unused=None,
    ) if False else _build_compliant_tax_html(
        extra_js_calc="""
        const tcjaStdDed = { single: 15000 };
        var taxable = Math.max(0, inputs.gross_income - inputs.standard_deduction_2026);
        return Math.round(1240.0 + Math.min(Math.max(0.0, taxable - 12400.0), 38000.0) * 0.12 + Math.min(Math.max(0.0, taxable - 50400.0), 55300.0) * 0.22 + Math.max(0.0, taxable - 105700.0) * 0.24);
        """,
    )
    gate = UnifiedTruthGate(truth_pack=pack, all_truth_packs={"profithelm": pack})
    rep = gate.audit_html_content(
        html,
        property_id="profithelm",
        file_path="tools/irs-2027-tax-brackets/index.html",
    )
    assert rep.passed is False
    assert any(v.code == "SUPERSEDED_VALUE" and "JS" in v.message for v in rep.violations)

    js_file = tmp_path / "calc.js"
    js_file.write_text("const tcjaStdDed = { single: 15000 };\n", encoding="utf-8")
    js_rep = gate.audit_non_html_file(js_file, property_id="profithelm")
    assert js_rep.passed is False
    assert any(v.code == "SUPERSEDED_VALUE" for v in js_rep.violations)


def test_superseded_value_smart_historical_context_guard():
    """2024 historical qualification passes; 2026 wrong-year or unlabeled fails."""
    pack = _make_tax_pack()
    gate = UnifiedTruthGate(truth_pack=pack, all_truth_packs={"profithelm": pack})

    good_html = _build_compliant_tax_html(
        extra_body="<p>Historical note: the 2024 cap was $30,500 before indexing.</p>",
    )
    rep_good = gate.audit_html_content(
        good_html,
        property_id="profithelm",
        file_path="tools/irs-2027-tax-brackets/index.html",
    )
    assert rep_good.passed is True, rep_good.violations

    wrong_year_html = _build_compliant_tax_html(
        extra_body="<p>For 2026, heavy vehicle deduction cap is $30,500.</p>",
    )
    rep_bad_year = gate.audit_html_content(
        wrong_year_html,
        property_id="profithelm",
        file_path="tools/irs-2027-tax-brackets/index.html",
    )
    assert rep_bad_year.passed is False
    assert any(v.code == "SUPERSEDED_VALUE" for v in rep_bad_year.violations)

    unlabeled_suv_html = _build_compliant_tax_html(
        extra_body="<p>Under Section 179, heavy SUVs capped at $2,560,000.</p>",
    )
    rep_suv = gate.audit_html_content(
        unlabeled_suv_html,
        property_id="profithelm",
        file_path="tools/irs-2027-tax-brackets/index.html",
    )
    assert rep_suv.passed is False
    assert any(v.code == "SUPERSEDED_VALUE" for v in rep_suv.violations)


def test_banned_and_ungrounded_stat_claims_caught():
    """Catches '30.6% reduction in statutory capital drag' and generic ungrounded statistical percentages."""
    pack = _make_tax_pack()
    gate = UnifiedTruthGate(truth_pack=pack, all_truth_packs={"profithelm": pack})

    bad_drag = _build_compliant_tax_html(
        extra_body="<p>Empirical modeling demonstrates a 30.6% reduction in statutory capital drag.</p>",
    )
    rep1 = gate.audit_html_content(bad_drag, property_id="profithelm", file_path="tools/irs-2027-tax-brackets/index.html")
    assert rep1.passed is False
    codes = {v.code for v in rep1.violations}
    assert "BANNED_CLAIM" in codes
    assert "UNGROUNDED_STAT" in codes

    bad_ungrounded = _build_compliant_tax_html(
        extra_body="<p>Our benchmark study saves 27.4% on average for filers.</p>",
    )
    rep2 = gate.audit_html_content(bad_ungrounded, property_id="profithelm", file_path="tools/irs-2027-tax-brackets/index.html")
    assert rep2.passed is False
    assert any(v.code == "UNGROUNDED_STAT" for v in rep2.violations)

    grounded_pct = _build_compliant_tax_html(
        extra_body="<p>Section 199A provides a 20% reduction on qualified business income.</p>",
    )
    rep3 = gate.audit_html_content(grounded_pct, property_id="profithelm", file_path="tools/irs-2027-tax-brackets/index.html")
    assert rep3.passed is True, rep3.violations


def test_claim_class_qualifiers_enforced():
    """market_benchmark without qualifier and future_projection without projection label both fail."""
    pack = _make_tax_pack()
    gate = UnifiedTruthGate(truth_pack=pack, all_truth_packs={"profithelm": pack})

    unqualified_bm = _build_compliant_tax_html(
        extra_body="<p>Typical filing requires a $4,500 CPA prep fee.</p>",
    )
    rep_bm = gate.audit_html_content(unqualified_bm, property_id="profithelm", file_path="tools/irs-2027-tax-brackets/index.html")
    assert rep_bm.passed is False
    assert any(v.code == "MISSING_BENCHMARK_QUALIFIER" for v in rep_bm.violations)

    qualified_bm = _build_compliant_tax_html(
        extra_body="<p>Industry benchmark estimate range includes $4,500 CPA prep fee.</p>",
    )
    rep_bm_ok = gate.audit_html_content(qualified_bm, property_id="profithelm", file_path="tools/irs-2027-tax-brackets/index.html")
    assert rep_bm_ok.passed is True, rep_bm_ok.violations

    unlabeled_proj = _build_compliant_tax_html(
        extra_body="<p>Filers pay the $12,400 future surtax next cycle.</p>",
    )
    rep_pr = gate.audit_html_content(unlabeled_proj, property_id="profithelm", file_path="tools/irs-2027-tax-brackets/index.html")
    assert rep_pr.passed is False
    assert any(v.code == "MISSING_PROJECTION_LABEL" for v in rep_pr.violations)


# ---------------------------------------------------------------------------
# Gate 4: Citations & Domain-Topic Binding
# ---------------------------------------------------------------------------

def test_citations_unlisted_and_topic_forbidden_caught():
    """Catches fabricated citations, IRC Section 3111 / 29 CFR 1904 on LienBond WC, and IRC 1202 on 1031."""
    ph_pack = _make_tax_pack()
    lb_pack = _make_lienbond_pack()
    gate_ph = UnifiedTruthGate(truth_pack=ph_pack, all_truth_packs={"profithelm": ph_pack, "lienbond": lb_pack})
    gate_lb = UnifiedTruthGate(truth_pack=lb_pack, all_truth_packs={"profithelm": ph_pack, "lienbond": lb_pack})

    # Fabricated citations
    fab_html = _build_compliant_tax_html(
        extra_body="<p>Guided by IRC Section 99999 and Rev. Proc. 2099-999.</p>",
    )
    rep_fab = gate_ph.audit_html_content(fab_html, property_id="profithelm", file_path="tools/irs-2027-tax-brackets/index.html")
    assert rep_fab.passed is False
    assert sum(1 for v in rep_fab.violations if v.code == "UNLISTED_CITATION") >= 2

    # IRC Section 1202 on ProfitHelm 1031 exchange page
    html_1031 = """<!DOCTYPE html><html><head><title>1031 Exchange</title></head><body>
    <p>Governed by IRC Section 1031 and IRC Section 1202.</p>
    <footer>Circular 230 notice.</footer></body></html>"""
    rep_1031 = gate_ph.audit_html_content(
        html_1031,
        property_id="profithelm",
        file_path="tools/section-1031-exchange/index.html",
        is_tool_page=False,
    )
    assert rep_1031.passed is False
    assert any(v.code == "FORBIDDEN_CITATION_TOPIC" and "1202" in v.message for v in rep_1031.violations)

    # IRC Section 3111 and 29 CFR Part 1904 on LienBond workers-comp EMR tool
    html_wc = """<!DOCTYPE html><html><head><title>Workers Comp EMR</title></head><body>
    <p>Includes 40 U.S.C. 3131, IRC Section 3111, and 29 CFR Part 1904.</p>
    <footer>Final premiums depend on underwriting and state statutory schedules.</footer></body></html>"""
    rep_wc = gate_lb.audit_html_content(
        html_wc,
        property_id="lienbond",
        file_path="tools/workers-comp-emr-calculator/index.html",
        is_tool_page=False,
    )
    assert rep_wc.passed is False
    topic_msgs = [v.message for v in rep_wc.violations if v.code == "FORBIDDEN_CITATION_TOPIC"]
    assert any("3111" in m for m in topic_msgs)
    assert any("1904" in m for m in topic_msgs)


# ---------------------------------------------------------------------------
# Gate 5: Disclosures & Dynamic Cross-Tenant Isolation
# ---------------------------------------------------------------------------

def test_dynamic_disclosure_not_satisfied_by_c3pao_keyword_and_cross_tenant_vtt_md(tmp_path):
    """Mentioning 'c3pao' triggers disclosure requirement; foreign tokens caught in .md and .vtt."""
    gh_pack = _make_gainhelm_pack()
    ph_pack = _make_tax_pack()
    lb_pack = _make_lienbond_pack()
    registry = {"gainhelm": gh_pack, "profithelm": ph_pack, "lienbond": lb_pack}

    gate_gh = UnifiedTruthGate(truth_pack=gh_pack, all_truth_packs=registry)
    # Simply mentioning 'c3pao' without full required disclaimer MUST fail
    html_c3pao = """<!DOCTYPE html><html><head><title>CMMC Guide</title></head>
    <body><p>Prepare for your C3PAO audit readiness checklist.</p></body></html>"""
    rep_disc = gate_gh.audit_html_content(html_c3pao, property_id="gainhelm", file_path="tools/cmmc/index.html", is_tool_page=False)
    assert rep_disc.passed is False
    assert any(v.code == "MISSING_DISCLOSURE" for v in rep_disc.violations)

    # Cross-tenant leakage in syndication/*.md and videos/*.vtt
    vtt_f = tmp_path / "demo.vtt"
    vtt_f.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:04.000\nVisit ProfitHelm for tax calculators.\n", encoding="utf-8")
    rep_vtt = gate_gh.audit_non_html_file(vtt_f, property_id="gainhelm")
    assert rep_vtt.passed is False
    assert any(v.code == "CROSS_TENANT_CONTAMINATION" for v in rep_vtt.violations)

    md_f = tmp_path / "quora.md"
    md_f.write_text("Check lienbond.com for surety rates.\n", encoding="utf-8")
    rep_md = gate_gh.audit_non_html_file(md_f, property_id="gainhelm")
    assert rep_md.passed is False
    assert any(v.code == "CROSS_TENANT_CONTAMINATION" for v in rep_md.violations)


# ---------------------------------------------------------------------------
# Gate 6: Topic-Widget Binding, Zero Exemptions, Bid Bond Formula, Real Node JS Parity
# ---------------------------------------------------------------------------

def test_wrong_widget_id_on_qbi_page_and_no_19181_or_len4_exemptions():
    """Catches #val-total_federal_tax on QBI page, and rejects 19181.0 when published_output==18734.0 even with 4+ metrics."""
    pack = _make_tax_pack()
    gate = UnifiedTruthGate(truth_pack=pack, all_truth_packs={"profithelm": pack})

    # 1. Wrong widget #val-total_federal_tax pasted onto QBI deduction page
    qbi_manifest = json.dumps({
        "formula_id": "qbi_deduction_model",
        "formula": "round(qbi * 0.20, 2)",
        "inputs": {"qbi": 100000.0},
        "published_output": 20000.0,
    })
    qbi_html = f"""<!DOCTYPE html><html><head><title>QBI Calculator</title></head><body>
    <form class="calculator-form" id="qbi-deduction-calculator-calculator">
      <input type="number" id="input-qbi" name="qbi" value="100000" />
    </form>
    <strong class="output-value">$20,000</strong>
    <div id="val-qbi_deduction">$20,000</div>
    <div id="val-total_federal_tax">$18,734</div>
    <footer>Circular 230 notice.</footer>
    <script type="application/json" id="calculation-manifest">{qbi_manifest}</script>
    <script>
    (function(){{
      var f = document.getElementById("qbi-deduction-calculator-calculator");
      function run(){{
        var q = parseFloat(document.getElementById("input-qbi").value) || 0;
        var r = Math.round(q * 0.20 * 100) / 100;
        document.querySelector(".output-value").textContent = "$" + r;
        document.getElementById("val-qbi_deduction").textContent = "$" + r;
      }}
      run();
      f.addEventListener("input", run);
    }})();
    </script></body></html>"""
    rep_qbi = gate.audit_html_content(
        qbi_html,
        property_id="profithelm",
        file_path="tools/qbi-deduction-calculator/index.html",
    )
    assert rep_qbi.passed is False
    assert any(v.code == "TOPIC_FORMULA_MISMATCH" and "val-total_federal_tax" in v.message for v in rep_qbi.violations)

    # 2. NO 19181.0 exemption and NO len(metrics) >= 4 exemption
    stale_ssr_html = _build_compliant_tax_html(
        metric_id="val-total_federal_tax",
        metric_val_str="$19,181",
        extra_body=(
            '<div id="metric-a">$1</div><div id="metric-b">$2</div>'
            '<div id="metric-c">$3</div><div id="metric-d">$4</div>'
        ),
    )
    rep_stale = gate.audit_html_content(
        stale_ssr_html,
        property_id="profithelm",
        file_path="tools/irs-2027-tax-brackets/index.html",
    )
    assert rep_stale.passed is False
    assert any(v.code == "SSR_METRIC_MISMATCH" and "19181" in v.message for v in rep_stale.violations)


def test_bid_bond_with_license_bond_375_formula_caught():
    """Catches Contractor License Bond formula ($25,000 * 1.5% = $375) pasted onto bid-bond-calculator."""
    lb_pack = _make_lienbond_pack()
    gate = UnifiedTruthGate(truth_pack=lb_pack, all_truth_packs={"lienbond": lb_pack})
    manifest = json.dumps({
        "formula_id": "contractor_license_bond",
        "formula": "round(bond_amount * (rate_pct / 100.0) * term_years, 2)",
        "inputs": {"bond_amount": 25000.0, "rate_pct": 1.5, "term_years": 1.0},
        "published_output": 375.0,
    })
    html = f"""<!DOCTYPE html><html><head><title>Bid Bond Calculator</title></head><body>
    <form class="calculator-form" id="bid-bond-calculator-calculator">
      <input type="number" id="input-bond_amount" name="bond_amount" value="25000" />
      <input type="number" id="input-rate_pct" name="rate_pct" value="1.5" />
      <input type="number" id="input-term_years" name="term_years" value="1" />
    </form>
    <strong class="output-value">$375.00</strong>
    <div id="metric-bid_bond_penal_sum">$375.00</div>
    <footer>Final premiums depend on underwriting and state statutory schedules.</footer>
    <script type="application/json" id="calculation-manifest">{manifest}</script>
    <script>
    (function(){{
      var f = document.getElementById("bid-bond-calculator-calculator");
      function run(){{
        var b = parseFloat(document.getElementById("input-bond_amount").value) || 0;
        var r = parseFloat(document.getElementById("input-rate_pct").value) || 0;
        var t = parseFloat(document.getElementById("input-term_years").value) || 0;
        var res = (b * (r / 100) * t).toFixed(2);
        document.querySelector(".output-value").textContent = "$" + res;
        document.getElementById("metric-bid_bond_penal_sum").textContent = "$" + res;
      }}
      run();
      f.addEventListener("input", run);
    }})();
    </script></body></html>"""
    rep = gate.audit_html_content(html, property_id="lienbond", file_path="tools/bid-bond-calculator/index.html")
    assert rep.passed is False
    assert any(v.code == "TOPIC_FORMULA_MISMATCH" for v in rep.violations)


def test_real_node_js_vs_python_math_mismatch_and_runtime_error_caught():
    """Real Node.js DOM execution catches wrong JS math on test vectors and JS runtime errors."""
    pack = _make_tax_pack()
    gate = UnifiedTruthGate(truth_pack=pack, all_truth_packs={"profithelm": pack})

    # Case A: JS hardcodes 18734 regardless of input changes (fails on 200k vector!)
    hardcoded_js_html = _build_compliant_tax_html(
        extra_js_calc="return 18734;",
    )
    rep_hc = gate.audit_html_content(
        hardcoded_js_html,
        property_id="profithelm",
        file_path="tools/irs-2027-tax-brackets/index.html",
    )
    assert rep_hc.passed is False
    assert any(v.code == "JS_PARITY_MISMATCH" for v in rep_hc.violations)

    # Case B: JS throws ReferenceError
    broken_js_html = _build_compliant_tax_html(
        extra_js_calc="return undeclared_variable_xyz + 1;",
    )
    rep_err = gate.audit_html_content(
        broken_js_html,
        property_id="profithelm",
        file_path="tools/irs-2027-tax-brackets/index.html",
    )
    assert rep_err.passed is False
    assert any(v.code == "JS_RUNTIME_ERROR" for v in rep_err.violations)


# ---------------------------------------------------------------------------
# Gate 7: JSON-LD, llms.txt, & Full Non-HTML / Syndication Coverage
# ---------------------------------------------------------------------------

def test_jsonld_duplicate_app_node_and_pricing_mismatch_caught():
    """Catches duplicate SoftwareApplication + WebApplication nodes and wrong Offer pricing."""
    pack = _make_tax_pack()
    gate = UnifiedTruthGate(truth_pack=pack, all_truth_packs={"profithelm": pack})

    bad_jsonld = json.dumps({
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "SoftwareApplication", "name": "App 1", "offers": {"@type": "Offer", "price": "79.00"}},
            {"@type": "WebApplication", "name": "App 2"},
        ],
    })
    html = _build_compliant_tax_html(jsonld_override=bad_jsonld)
    rep = gate.audit_html_content(html, property_id="profithelm", file_path="tools/irs-2027-tax-brackets/index.html")
    assert rep.passed is False
    codes = {v.code for v in rep.violations}
    assert "JSONLD_DUPLICATE_APP_NODE" in codes
    assert "JSONLD_PRICING_MISMATCH" in codes


def test_llms_txt_dead_link_html_entity_duplicate_word_query_stub_caught(tmp_path):
    """Catches dead link, R&amp;D, Calculate Calculate, and Calculate How Do You in llms.txt."""
    lb_pack = _make_lienbond_pack()
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><body>Home</body></html>", encoding="utf-8")

    llms_f = dist / "llms.txt"
    llms_f.write_text(
        "# LienBond\n"
        "- [Surety Tool](https://lienbond.com/tools/surety-bond-cost-calculator-philippines/): "
        "Calculate Calculate R&amp;D costs. Calculate How Do You file?\n",
        encoding="utf-8",
    )

    gate = UnifiedTruthGate(truth_pack=lb_pack, all_truth_packs={"lienbond": lb_pack})
    rep = gate.audit_non_html_file(llms_f, property_id="lienbond", dist_dir=dist)
    assert rep.passed is False
    codes = {v.code for v in rep.violations}
    assert "LLMS_DEAD_LINK" in codes
    assert "LLMS_HTML_ENTITY" in codes
    assert "LLMS_DUPLICATE_WORD" in codes
    assert "LLMS_QUERY_STUB" in codes


def test_fail_closed_malformed_manifest_and_jsonld():
    """Malformed JSON in calculation-manifest or JSON-LD MUST fail closed (never silently ignored)."""
    pack = _make_tax_pack()
    gate = UnifiedTruthGate(truth_pack=pack, all_truth_packs={"profithelm": pack})
    html = _build_compliant_tax_html().replace('"published_output": 18734.0', '"published_output": BROKEN_JSON')
    rep = gate.audit_html_content(
        html,
        property_id="profithelm",
        file_path="tools/irs-2027-tax-brackets/index.html",
    )
    assert rep.passed is False
    assert any(v.code == "MANIFEST_MISSING_OR_INVALID" for v in rep.violations)


# ---------------------------------------------------------------------------
# End-to-End Clean Estate Pass
# ---------------------------------------------------------------------------

def test_clean_compliant_estate_passes_100_percent(tmp_path):
    """Full clean estate (HTML, sidecar manifest, llms*.txt, catalog, feed, ai-benchmarks, VTT, syndication) passes."""
    pack = _make_tax_pack()
    other_pack = _make_lienbond_pack()
    registry = {"profithelm": pack, "lienbond": other_pack}

    dist = tmp_path / "dist"
    tool_dir = dist / "tools" / "irs-2027-tax-brackets"
    tool_dir.mkdir(parents=True)
    (dist / "manifests").mkdir()
    (dist / "ai-benchmarks").mkdir()
    (dist / "videos").mkdir()
    synd = tmp_path / "syndication" / "irs-2027-tax-brackets"
    synd.mkdir(parents=True)

    (dist / "index.html").write_text(
        "<!DOCTYPE html><html><head><title>ProfitHelm</title></head>"
        "<body><h1>ProfitHelm</h1><footer>Circular 230 informational notice.</footer></body></html>",
        encoding="utf-8",
    )
    (tool_dir / "index.html").write_text(_build_compliant_tax_html(), encoding="utf-8")
    (dist / "manifests" / "irs-2027-tax-brackets.json").write_text(
        json.dumps({
            "formula": (
                "round(1240.0 + min(max(0.0, (gross_income - standard_deduction_2026) - 12400.0), 38000.0) * 0.12 "
                "+ min(max(0.0, (gross_income - standard_deduction_2026) - 50400.0), 55300.0) * 0.22 "
                "+ max(0.0, (gross_income - standard_deduction_2026) - 105700.0) * 0.24, 0)"
            ),
            "inputs": {"gross_income": 125000.0, "standard_deduction_2026": 16100.0},
            "published_output": 18734.0,
        }),
        encoding="utf-8",
    )
    (dist / "llms.txt").write_text(
        "# ProfitHelm\n- [IRS 2027 Tax Brackets](https://profithelm.com/tools/irs-2027-tax-brackets/): "
        "Modeled under Rev. Proc. 2025-32 and P.L. 119-21.\n",
        encoding="utf-8",
    )
    (dist / "llms-full.txt").write_text(
        "ProfitHelm IRS 2027 Tax Brackets Calculator\n"
        "Evaluates 2026 standard deduction ($16,100) under Rev. Proc. 2025-32.\n",
        encoding="utf-8",
    )
    (dist / "catalog.json").write_text(
        json.dumps({"tools": [{"slug": "irs-2027-tax-brackets", "url": "/tools/irs-2027-tax-brackets/"}]}),
        encoding="utf-8",
    )
    (dist / "feed.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>ProfitHelm</title></channel></rss>',
        encoding="utf-8",
    )
    (dist / "ai-benchmarks" / "summary.json").write_text(
        json.dumps({"authority": "Rev. Proc. 2025-32", "standard_deduction_single": 16100}),
        encoding="utf-8",
    )
    (dist / "videos" / "irs-2027-tax-brackets.vtt").write_text(
        "WEBVTT\n\n00:00:01.000 --> 00:00:05.000\nCalculate 2026 tax brackets under P.L. 119-21.\n",
        encoding="utf-8",
    )
    (synd / "quora.md").write_text(
        "Under P.L. 119-21 and Rev. Proc. 2025-32, the 2026 Single standard deduction is $16,100.\n",
        encoding="utf-8",
    )
    (synd / "newsletter.txt").write_text(
        "Tax modeling update for ProfitHelm under Rev. Proc. 2025-32.\n",
        encoding="utf-8",
    )

    rep = audit_tenant_truth_fail_closed(
        dist,
        property_id="profithelm",
        repo_root=tmp_path,
        as_of=date(2026, 6, 1),
        truth_pack=pack,
        all_truth_packs=registry,
    )
    assert rep.passed is True, f"Expected PASS, got: {[v.to_dict() for v in rep.violations]}"
    assert rep.status == "PASS"
    assert len(rep.files_audited) == 11
    assert rep.truth_pack_sha256
    assert "PASS" in rep.summary()


def test_scenario_table_row_mismatch_and_external_js_parity(tmp_path):
    """Catches 0.8x scenario row drift and external <script src> JS parity mismatch in Node."""
    pack = _make_tax_pack()
    gate = UnifiedTruthGate(truth_pack=pack, all_truth_packs={"profithelm": pack})

    # 1. Scenario row mismatch on 0.8x
    bad_scen = _build_compliant_tax_html().replace(
        f"${18734.0 * 0.8:,.2f}",
        "$9,999.00",
    )
    rep_scen = gate.audit_html_content(
        bad_scen,
        property_id="profithelm",
        file_path="tools/irs-2027-tax-brackets/index.html",
    )
    assert rep_scen.passed is False
    assert any(v.code == "SCENARIO_ROW_MISMATCH" for v in rep_scen.violations)

    # 2. External <script src="/assets/calc.js"> inside dist_dir with JS parity bug
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "tools" / "irs-2027-tax-brackets").mkdir(parents=True)
    (dist / "assets" / "calc.js").write_text(
        """
        (function() {
          var f = document.getElementById("irs-2027-tax-brackets-calculator");
          if (!f) return;
          function run() {
            var gi = parseFloat(document.getElementById("input-gross_income").value) || 0;
            var sd = parseFloat(document.getElementById("input-standard_deduction_2026").value) || 0;
            // Wrong formula on high income (drops 0.24 bracket!)
            var val = Math.round(1240 + Math.max(0, gi - sd - 12400) * 0.12);
            document.querySelector(".output-value").textContent = "$" + val;
            document.getElementById("val-total_federal_tax").textContent = "$" + val;
          }
          run();
          f.addEventListener("input", run);
        })();
        """,
        encoding="utf-8",
    )
    ext_html = f"""<!DOCTYPE html><html><head><title>IRS 2027 Tax Brackets</title></head><body>
    <form class="calculator-form" id="irs-2027-tax-brackets-calculator">
      <input type="number" id="input-gross_income" name="gross_income" value="125000" />
      <input type="number" id="input-standard_deduction_2026" name="standard_deduction_2026" value="16100" />
    </form>
    <strong class="output-value">$18,734</strong>
    <div id="val-total_federal_tax">$18,734</div>
    <footer>Circular 230 informational notice.</footer>
    <script type="application/json" id="calculation-manifest">{json.dumps({
        "formula_id": "irs_2027_tax_brackets",
        "formula": (
            "round(1240.0 + min(max(0.0, (gross_income - standard_deduction_2026) - 12400.0), 38000.0) * 0.12 "
            "+ min(max(0.0, (gross_income - standard_deduction_2026) - 50400.0), 55300.0) * 0.22 "
            "+ max(0.0, (gross_income - standard_deduction_2026) - 105700.0) * 0.24, 0)"
        ),
        "inputs": {"gross_income": 125000.0, "standard_deduction_2026": 16100.0},
        "published_output": 18734.0,
    })}</script>
    <script src="/assets/calc.js"></script>
    </body></html>"""
    html_p = dist / "tools" / "irs-2027-tax-brackets" / "index.html"
    html_p.write_text(ext_html, encoding="utf-8")

    rep_ext = gate.audit_html_file(html_p, property_id="profithelm", dist_dir=dist)
    assert rep_ext.passed is False
    assert any(v.code == "JS_PARITY_MISMATCH" for v in rep_ext.violations)
    rep_dict = rep_ext.to_dict()
    assert rep_dict["status"] == "FAIL"
    assert rep_dict["violation_count"] == len(rep_ext.violations)


def test_real_truth_pack_integration_and_missing_site(tmp_path):
    """Verifies UnifiedTruthGate loads real TruthPack JSONs dynamically and fails closed on missing site."""
    gate = UnifiedTruthGate()

    # Unknown 5th site loaded from real registry MUST fail closed
    empty_dist = tmp_path / "dist5"
    empty_dist.mkdir()
    (empty_dist / "index.html").write_text("<html><body>Site 5</body></html>", encoding="utf-8")
    rep_missing = gate.audit_estate(empty_dist, property_id="synthetic_5th_tenant", as_of=date(2026, 11, 24))
    assert rep_missing.passed is False
    assert any(v.code == "TRUTH_PACK_MISSING" for v in rep_missing.violations)

    # Real profithelm TruthPack catches banned claim + cross-tenant token + $1,250,000 superseded cap
    dirty_html = """<!DOCTYPE html><html><head><title>Section 179</title></head><body>
    <p>30.6% reduction in statutory capital drag with $1,250,000 cap on LienBond.</p>
    <footer>Circular 230 informational notice, not individualized tax advice.</footer>
    </body></html>"""
    rep_dirty = gate.audit_html_content(
        dirty_html,
        property_id="profithelm",
        file_path="tools/section-179-calculator/index.html",
        as_of=date(2026, 11, 24),
        is_tool_page=False,
    )
    assert rep_dirty.passed is False
    codes = {v.code for v in rep_dirty.violations}
    assert "BANNED_CLAIM" in codes
    assert "SUPERSEDED_VALUE" in codes
    assert "CROSS_TENANT_CONTAMINATION" in codes

    # Real profithelm TruthPack passes clean Section 179 page with live JS parity
    clean_179 = f"""<!DOCTYPE html><html><head><title>Section 179 Heavy SUV</title></head><body>
    <p>Under P.L. 119-21 and Rev. Proc. 2025-32, heavy SUVs are capped at $32,000 before bonus depreciation. Primary source: <a href="https://www.irs.gov/pub/irs-drop/rp-25-32.pdf" rel="noopener">IRS Rev. Proc. 2025-32</a>.</p>
    <form class="calculator-form" id="section-179-calculator-calculator">
      <input type="number" id="input-equipment_cost" name="equipment_cost" value="85000" />
      <input type="number" id="input-business_use_pct" name="business_use_pct" value="0.8" />
      <input type="number" id="input-is_heavy_suv" name="is_heavy_suv" value="1" />
      <input type="number" id="input-bonus_pct" name="bonus_pct" value="100" />
    </form>
    <strong class="output-value">$68,000</strong>
    <div id="total-first-year-deduction">$68,000</div>
    <footer>Treasury Circular 230 Notice: does not constitute individualized tax advice.</footer>
    <script type="application/json" id="calculation-manifest">{json.dumps({
        "formula_id": "section_179_heavy_suv_plus_bonus_2026",
        "formula": (
            "round(min(equipment_cost * business_use_pct, 32000.0 if is_heavy_suv == 1 else "
            "max(0.0, 2560000.0 - max(0.0, equipment_cost - 4090000.0))) + "
            "max(0.0, equipment_cost * business_use_pct - min(equipment_cost * business_use_pct, "
            "32000.0 if is_heavy_suv == 1 else max(0.0, 2560000.0 - max(0.0, equipment_cost - 4090000.0)))) * (bonus_pct / 100.0), 2)"
        ),
        "inputs": {"equipment_cost": 85000.0, "business_use_pct": 0.8, "is_heavy_suv": 1, "bonus_pct": 100.0},
        "published_output": 68000.0,
    })}</script>
    <script>
    (function(){{
      var f = document.getElementById("section-179-calculator-calculator");
      function run(){{
        var equipment_cost = parseFloat(document.getElementById("input-equipment_cost").value) || 0;
        var business_use_pct = parseFloat(document.getElementById("input-business_use_pct").value) || 0;
        var is_heavy_suv = parseFloat(document.getElementById("input-is_heavy_suv").value) || 0;
        var bonus_pct = parseFloat(document.getElementById("input-bonus_pct").value) || 0;
        var cap = (is_heavy_suv === 1) ? 32000.0 : Math.max(0.0, 2560000.0 - Math.max(0.0, equipment_cost - 4090000.0));
        var s179 = Math.min(equipment_cost * business_use_pct, cap);
        var rem = Math.max(0.0, (equipment_cost * business_use_pct) - s179);
        var total = Math.round((s179 + rem * (bonus_pct / 100.0)) * 100) / 100;
        document.querySelector(".output-value").textContent = "$" + total;
        document.getElementById("total-first-year-deduction").textContent = "$" + total;
      }}
      run();
      f.addEventListener("input", run);
    }})();
    </script></body></html>"""
    rep_clean = gate.audit_html_content(
        clean_179,
        property_id="profithelm",
        file_path="tools/section-179-calculator/index.html",
        as_of=date(2026, 11, 24),
    )
    assert rep_clean.passed is True, [v.to_dict() for v in rep_clean.violations]


def test_disclosures_scoped_to_prose_surfaces_not_infra_files(tmp_path):
    """
    Infrastructure/index files (robots.txt, sitemap.xml, manifests/*.json, _routes.json,
    catalog.json, media-kit.json, feed.xml, indexnow key .txt, llms.txt, static/js/*.js)
    must NOT fail MISSING_DISCLOSURE, while llms-full.txt, syndication prose, and HTML
    pages STILL fail closed when mandatory disclosures are missing.
    """
    gate = UnifiedTruthGate()
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "manifests").mkdir()
    (dist / "static" / "js").mkdir(parents=True)
    synd = tmp_path / "syndication" / "rap"
    synd.mkdir(parents=True)

    (dist / "index.html").write_text(
        "<!DOCTYPE html><html><head><title>Prexvo</title></head><body><h1>Prexvo</h1>"
        "<footer>Refinancing federal loans permanently waives federal protections and PSLF.</footer>"
        "</body></html>",
        encoding="utf-8",
    )

    infra_files = {
        dist / "robots.txt": "User-agent: *\nAllow: /\nSitemap: https://prexvo.com/sitemap.xml\n",
        dist / "sitemap.xml": '<?xml version="1.0" encoding="UTF-8"?><urlset><url><loc>https://prexvo.com/</loc></url></urlset>',
        dist / "feed.xml": '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>Prexvo</title></channel></rss>',
        dist / "_routes.json": json.dumps({"version": 1, "include": ["/*"], "exclude": []}),
        dist / "catalog.json": json.dumps({"tools": []}),
        dist / "media-kit.json": json.dumps({"brand": "Prexvo"}),
        dist / "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4.txt": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
        dist / "llms.txt": "# Prexvo\n- [Home](https://prexvo.com/): Federal student loan calculators.\n",
        dist / "manifests" / "rap-payment.json": json.dumps({
            "formula": "round(max(0.0, agi - 15650.0) * 0.10 / 12.0, 2)",
            "inputs": {"agi": 65000.0},
            "published_output": 411.25,
        }),
        dist / "static" / "js" / "app.js": "window.__prexvoLoaded = true;\n",
    }
    for fpath, body in infra_files.items():
        fpath.write_text(body, encoding="utf-8")
        rep = gate.audit_non_html_file(fpath, property_id="prexvo", dist_dir=dist, as_of=date(2026, 11, 24))
        assert rep.passed is True, f"Unexpected violation on {fpath.name}: {[v.to_dict() for v in rep.violations]}"

    # Other checks (cross-tenant, forbidden dashes) STILL run on infra files!
    dirty_robots = dist / "robots.txt"
    dirty_robots.write_text("User-agent: *\n# ProfitHelm leaked here\n", encoding="utf-8")
    rep_dirty_robots = gate.audit_non_html_file(dirty_robots, property_id="prexvo", dist_dir=dist, as_of=date(2026, 11, 24))
    assert rep_dirty_robots.passed is False
    assert any(v.code == "CROSS_TENANT_CONTAMINATION" for v in rep_dirty_robots.violations)

    # Prose/short syndication .md/.txt do NOT require 300+ char full legal disclaimers,
    # while llms-full.txt and HTML pages (including google_sites.html) STILL fail closed on MISSING_DISCLOSURE.
    synd_x = synd / "x_post.txt"
    synd_x.write_text("Compare federal student loan repayment calculators.\n", encoding="utf-8")
    rep_synd_clean = gate.audit_non_html_file(synd_x, property_id="prexvo", dist_dir=dist, as_of=date(2026, 11, 24))
    assert rep_synd_clean.passed is True, [v.to_dict() for v in rep_synd_clean.violations]

    # Banned claims / cross-tenant contamination STILL fail on syndication .md/.txt
    synd_md = synd / "quora.md"
    synd_md.write_text("Official federal loan servicer guide.\n", encoding="utf-8")
    rep_synd_bad = gate.audit_non_html_file(synd_md, property_id="prexvo", dist_dir=dist, as_of=date(2026, 11, 24))
    assert rep_synd_bad.passed is False
    assert any(v.code == "BANNED_CLAIM" for v in rep_synd_bad.violations)

    llms_full = dist / "llms-full.txt"
    llms_full.write_text("Prexvo Student Loan Guide\nCompare federal repayment plans.\n", encoding="utf-8")
    rep_llms_full = gate.audit_non_html_file(llms_full, property_id="prexvo", dist_dir=dist, as_of=date(2026, 11, 24))
    assert rep_llms_full.passed is False
    assert any(v.code == "MISSING_DISCLOSURE" for v in rep_llms_full.violations)

    rep_html = gate.audit_html_content(
        "<!DOCTYPE html><html><head><title>RAP</title></head><body><p>Repayment guide.</p></body></html>",
        property_id="prexvo",
        file_path="tools/rap/index.html",
        as_of=date(2026, 11, 24),
        is_tool_page=False,
    )
    assert rep_html.passed is False
    assert any(v.code == "MISSING_DISCLOSURE" for v in rep_html.violations)


def test_superseded_values_respect_non_empty_applies_to_slugs():
    """Entries with non-empty applies_to_slugs apply only to matching paths/slugs; empty applies site-wide."""
    pack = _make_tax_pack()
    pack["entries"].append({
        "id": "rap_only_240_months",
        "claim_class": "enacted_law",
        "value": 360,
        "text": "RAP forgiveness requires 360 monthly payments.",
        "superseded_values": [{"value": 240, "pattern": r"\b240\s+months\b"}],
        "applies_to_slugs": ["rap-payment-calculator", "rap-vs-ibr-calculator"],
        "expires_at": "2027-12-31",
    })
    gate = UnifiedTruthGate(truth_pack=pack, all_truth_packs={"profithelm": pack})

    def _simple_page(body: str) -> str:
        return (
            "<!DOCTYPE html><html><head><title>Model</title></head>"
            f"<body>{body}<footer>Circular 230 informational notice, not formal tax advice.</footer></body></html>"
        )

    # Unrelated slug mentioning '240 months' must NOT fail rap_only_240_months
    rep_ibr = gate.audit_html_content(
        _simple_page("<p>IBR old-borrower forgiveness is 240 months.</p>"),
        property_id="profithelm",
        file_path="tools/ibr-hardship-calculator/index.html",
        is_tool_page=False,
    )
    assert rep_ibr.passed is True, [v.to_dict() for v in rep_ibr.violations]

    # Matching slug mentioning '240 months' MUST fail
    rep_rap = gate.audit_html_content(
        _simple_page("<p>RAP forgiveness is 240 months.</p>"),
        property_id="profithelm",
        file_path="tools/rap-payment-calculator/index.html",
        is_tool_page=False,
    )
    assert rep_rap.passed is False
    assert any(v.code == "SUPERSEDED_VALUE" and "rap_only_240_months" in v.message for v in rep_rap.violations)

    # Site-wide entry (empty applies_to_slugs) STILL fails on any slug
    rep_sw = gate.audit_html_content(
        _simple_page("<p>Standard deduction is $15,000.</p>"),
        property_id="profithelm",
        file_path="tools/ibr-hardship-calculator/index.html",
        is_tool_page=False,
    )
    assert rep_sw.passed is False
    assert any(v.code == "SUPERSEDED_VALUE" and "std_deduction_single_2026" in v.message for v in rep_sw.violations)


def test_adversarial_bid_bond_375_generic_formula_fails_closed():
    """
    Adversarial regression: bid-bond-calculator using generic license-bond-like formula
    `round(bond_amount * rate, 2)` ($25,000 * 0.015 = $375.00) with matching JS MUST fail
    closed with TOPIC_FORMULA_MISMATCH against real lienbond TruthPack.
    """
    gate = UnifiedTruthGate()
    manifest = json.dumps({
        "formula": "round(bond_amount * rate, 2)",
        "inputs": {"bond_amount": 25000.0, "rate": 0.015},
        "published_output": 375.0,
    })
    html = f"""<!DOCTYPE html><html><head><title>Bid Bond Calculator</title></head><body>
    <form class="calculator-form" id="bid-bond-calculator-calculator">
      <input type="number" id="input-bond_amount" name="bond_amount" value="25000" />
      <input type="number" id="input-rate" name="rate" value="0.015" />
    </form>
    <strong class="output-value">$375.00</strong>
    <footer>LienBond is not a licensed attorney or surety underwriter; informational underwriting estimates only.</footer>
    <script type="application/json" id="calculation-manifest">{manifest}</script>
    <script>
    (function(){{
      var f = document.getElementById("bid-bond-calculator-calculator");
      function run(){{
        var b = parseFloat(document.getElementById("input-bond_amount").value) || 0;
        var r = parseFloat(document.getElementById("input-rate").value) || 0;
        document.querySelector(".output-value").textContent = "$" + (b * r).toFixed(2);
      }}
      run();
      f.addEventListener("input", run);
    }})();
    </script></body></html>"""
    rep = gate.audit_html_content(
        html,
        property_id="lienbond",
        file_path="tools/bid-bond-calculator/index.html",
        as_of=date(2026, 11, 24),
        run_js_parity=True,
    )
    assert rep.passed is False
    assert any(v.code == "TOPIC_FORMULA_MISMATCH" for v in rep.violations)


def test_enacted_law_missing_primary_source_link_fails_closed():
    """Enacted-law calculator page with zero outbound .gov/official links MUST fail closed."""
    gate = UnifiedTruthGate()
    html_no_gov = _build_compliant_tax_html().replace(
        '<a href="https://www.irs.gov/pub/irs-drop/rp-25-32.pdf" rel="noopener">IRS Rev. Proc. 2025-32</a>',
        "<span>IRS Rev. Proc. 2025-32</span>",
    )
    pack = _make_tax_pack()
    rep = gate.audit_html_content(
        html_no_gov,
        property_id="profithelm",
        file_path="tools/irs-2027-tax-brackets/index.html",
        truth_pack=pack,
        as_of=date(2026, 11, 26),
        run_js_parity=False,
    )
    assert rep.passed is False
    assert any(v.code == "MISSING_PRIMARY_SOURCE_LINK" for v in rep.violations)
