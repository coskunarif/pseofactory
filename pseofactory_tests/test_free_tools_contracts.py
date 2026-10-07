"""
Unit & Integration Tests for pseofactory Free Interactive Tools Contracts & Operational Shields
Verifies:
1. ToolUtilityContract (interactive form/container, accessible label pairings, submit CTA, touch targets)
2. Free WebApplication / SoftwareApplication Schema Gate (applicationCategory, offers with price 0, ISO 4217 currency)
3. Operational Rate-Limit & Bot Shield Verification (X-RateLimit-Limit, Cloudflare Turnstile, client cache hooks)
4. Maintenance DriftReason.OPERATIONAL_SHIELD_GAP taxonomy and AssetIntegrityEvaluator enforcement
5. MasterSEOVerifier gates, aliases, and checklist integration
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

import json
import pytest
from pathlib import Path
from typing import Dict, Any

import pseofactory
import pseofactory.contracts as contracts
import pseofactory.verifier as verifier
from pseofactory.contracts import (
    ToolUtilityHTMLParser,
    detect_tool_utility_issues,
    assert_tool_utility_contract,
    detect_free_web_application_schema_issues,
    assert_free_web_application_schema,
    detect_rate_limit_and_bot_shield_issues,
    assert_rate_limit_and_bot_shield,
)
from pseofactory.verifier import (
    MasterSEOVerifier,
    check_tool_utility_gate,
    verify_tool_utility_contract,
    verify_html_tool_utility_contract,
    check_free_web_application_schema_gate,
    verify_free_web_application_schema,
    verify_html_free_web_application_schema,
    check_operational_shield_gate,
    verify_operational_shield,
    verify_rate_limit_and_bot_shield,
    verify_html_structured_data,
)
from pseofactory.maintenance import (
    DriftReason,
    AssetIntegrityEvaluator,
    ConfigurablePropertyAdapter,
)


# =============================================================================
# 1. ToolUtilityContract Tests
# =============================================================================

def test_tool_utility_contract_valid_form_and_labels():
    """Verifies that an interactive tool with a form, labeled inputs, and submit button passes."""
    html_doc = (
        '<!DOCTYPE html><html lang="en"><head><title>Loan Calculator</title></head><body>'
        '<div class="tool-wrapper">'
        '<form id="loan-form">'
        '<label for="principal">Principal Amount</label>'
        '<input type="number" id="principal" name="principal" value="10000" />'
        '<label for="rate">Interest Rate</label>'
        '<input type="number" id="rate" name="rate" value="5.5" />'
        '<button type="submit">Calculate Payment</button>'
        '</form>'
        '</div></body></html>'
    )
    assert assert_tool_utility_contract(html_doc) is True
    res = verify_html_tool_utility_contract(html_doc)
    assert res["status"] == "PASS"
    assert res["tool_valid"] is True
    assert res["violations_count"] == 0


def test_tool_utility_contract_valid_aria_labels():
    """Verifies inputs paired with aria-label or aria-labelledby satisfy the accessibility contract."""
    html_doc = (
        '<div class="calculator-container">'
        '<form>'
        '<input type="text" name="query" aria-label="Search Tax Code" />'
        '<span id="state-label">State Jurisdiction</span>'
        '<input type="text" name="state" aria-labelledby="state-label" />'
        '<button type="submit">Evaluate</button>'
        '</form>'
        '</div>'
    )
    assert assert_tool_utility_contract(html_doc) is True
    assert len(detect_tool_utility_issues(html_doc)) == 0


def test_tool_utility_contract_valid_nested_label():
    """Verifies inputs nested inside <label> tags satisfy label pairing."""
    html_doc = (
        '<form role="form">'
        '<label>Filing Status: <input type="text" name="status" /></label>'
        '<label>Exemptions: <select name="exemptions"><option>0</option></select></label>'
        '<input type="submit" value="Calculate" />'
        '</form>'
    )
    assert assert_tool_utility_contract(html_doc) is True


def test_tool_utility_contract_valid_interactive_container_cta_button():
    """Verifies interactive container with button submit semantics passes."""
    html_doc = (
        '<div role="form" class="tax-calculator-widget">'
        '<label for="amount">Capital Asset Cost</label>'
        '<input type="number" id="amount" name="amount" />'
        '<button type="button" class="btn-calc">Compute Depreciation</button>'
        '</div>'
    )
    assert assert_tool_utility_contract(html_doc) is True


def test_tool_utility_contract_missing_form_or_container():
    """Verifies error raised when no form or interactive container exists."""
    html_doc = '<!DOCTYPE html><html><body><p>Just informative narrative text.</p></body></html>'
    issues = detect_tool_utility_issues(html_doc)
    assert any("Missing interactive form or container" in i for i in issues)
    with pytest.raises(ValueError, match="Tool utility contract violation"):
        assert_tool_utility_contract(html_doc)


def test_tool_utility_contract_missing_inputs():
    """Verifies error raised when a form contains no input controls."""
    html_doc = '<form><button type="submit">Run</button></form>'
    issues = detect_tool_utility_issues(html_doc)
    assert any("Missing interactive input elements" in i for i in issues)
    with pytest.raises(ValueError, match="Missing interactive input elements"):
        assert_tool_utility_contract(html_doc)


def test_tool_utility_contract_unpaired_input():
    """Verifies error raised when an input lacks a label or aria-label."""
    html_doc = (
        '<form>'
        '<input type="text" id="orphan-input" name="orphan" />'
        '<button type="submit">Submit</button>'
        '</form>'
    )
    issues = detect_tool_utility_issues(html_doc)
    assert any("orphan-input" in i and "lacks associated <label> or aria-label" in i for i in issues)
    with pytest.raises(ValueError, match="lacks associated <label> or aria-label"):
        assert_tool_utility_contract(html_doc)


def test_tool_utility_contract_missing_submit_cta():
    """Verifies error raised when form lacks a submit button or action CTA."""
    html_doc = (
        '<form>'
        '<label for="query">Search</label>'
        '<input type="text" id="query" name="query" />'
        '</form>'
    )
    issues = detect_tool_utility_issues(html_doc)
    assert any("Missing submit CTA button" in i for i in issues)
    with pytest.raises(ValueError, match="Missing submit CTA button"):
        assert_tool_utility_contract(html_doc)


def test_tool_utility_contract_forbidden_dashes():
    """Verifies forbidden em-dash or en-dash in tool markup fails."""
    html_doc = (
        '<form>'
        '<label for="q">Search ' + chr(0x2014) + '</label>'
        '<input type="text" id="q" name="q" />'
        '<button type="submit">Submit</button>'
        '</form>'
    )
    issues = detect_tool_utility_issues(html_doc)
    assert any("forbidden em-dash" in i for i in issues)
    with pytest.raises(ValueError, match="forbidden em-dash"):
        assert_tool_utility_contract(html_doc)


def test_tool_utility_contract_undersized_touch_target():
    """Verifies undersized touch target triggers violation."""
    html_doc = (
        '<form style="min-height: 30px;">'
        '<label for="q">Search</label>'
        '<input type="text" id="q" name="q" />'
        '<button type="submit">Submit</button>'
        '</form>'
    )
    issues = detect_tool_utility_issues(html_doc)
    assert any("Touch target min-height < 44px" in i for i in issues)


# =============================================================================
# 2. Free WebApplication / SoftwareApplication Schema Gate Tests
# =============================================================================

def test_assert_free_web_application_schema_valid_webapp():
    """Verifies valid WebApplication schema with applicationCategory and price 0."""
    html_doc = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "WebApplication", '
        '"name": "ProfitHelm Tax Calculator", "applicationCategory": "BusinessApplication", '
        '"operatingSystem": "All", "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}}'
        '</script></head><body><h1>Tax Calculator</h1></body></html>'
    )
    assert assert_free_web_application_schema(html_doc) is True
    res = verify_html_free_web_application_schema(html_doc)
    assert res["status"] == "PASS"
    assert res["schema_valid"] is True
    assert res["violations_count"] == 0


def test_assert_free_web_application_schema_valid_software_app():
    """Verifies valid SoftwareApplication schema with numeric price 0 and EUR currency."""
    html_doc = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "SoftwareApplication", '
        '"name": "Prexvo Repayment Modeler", "applicationCategory": "FinanceApplication", '
        '"offers": {"@type": "Offer", "price": 0, "priceCurrency": "EUR"}}'
        '</script></head><body><h1>Modeler</h1></body></html>'
    )
    assert assert_free_web_application_schema(html_doc) is True


def test_assert_free_web_application_schema_valid_graph_reference():
    """Verifies valid schema in @graph where offers references an Offer node by @id."""
    html_doc = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@graph": ['
        '{"@type": "WebApplication", "@id": "https://profithelm.com/#app", '
        '"name": "Section 179 Modeler", "applicationCategory": "UtilityApplication", '
        '"offers": {"@id": "https://profithelm.com/#free-offer"}}, '
        '{"@type": "Offer", "@id": "https://profithelm.com/#free-offer", '
        '"price": "0.00", "priceCurrency": "USD"}'
        ']}'
        '</script></head><body><h1>Modeler</h1></body></html>'
    )
    assert assert_free_web_application_schema(html_doc) is True


def test_assert_free_web_application_schema_missing_jsonld():
    """Verifies error raised when HTML lacks JSON-LD."""
    html_doc = '<html><head><title>No Schema</title></head><body><h1>Hi</h1></body></html>'
    issues = detect_free_web_application_schema_issues(html_doc)
    assert any("Missing application/ld+json structured data block" in i for i in issues)
    with pytest.raises(ValueError, match="Missing application/ld\\+json"):
        assert_free_web_application_schema(html_doc)


def test_assert_free_web_application_schema_missing_target_type():
    """Verifies error raised when schema is Article or Product rather than WebApplication."""
    html_doc = (
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "Product", "name": "Paid Widget"}'
        '</script>'
    )
    issues = detect_free_web_application_schema_issues(html_doc)
    assert any("Missing WebApplication or SoftwareApplication schema" in i for i in issues)
    with pytest.raises(ValueError, match="Missing WebApplication or SoftwareApplication"):
        assert_free_web_application_schema(html_doc)


def test_assert_free_web_application_schema_missing_category():
    """Verifies error raised when applicationCategory is missing."""
    html_doc = (
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "WebApplication", "name": "App", '
        '"offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}}'
        '</script>'
    )
    issues = detect_free_web_application_schema_issues(html_doc)
    assert any("Missing or empty 'applicationCategory'" in i for i in issues)
    with pytest.raises(ValueError, match="applicationCategory"):
        assert_free_web_application_schema(html_doc)


def test_assert_free_web_application_schema_missing_offers():
    """Verifies error raised when offers block is absent."""
    html_doc = (
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "WebApplication", "name": "App", '
        '"applicationCategory": "BusinessApplication"}'
        '</script>'
    )
    issues = detect_free_web_application_schema_issues(html_doc)
    assert any("Missing 'offers' specification" in i for i in issues)
    with pytest.raises(ValueError, match="offers"):
        assert_free_web_application_schema(html_doc)


def test_assert_free_web_application_schema_non_zero_price():
    """Verifies error raised when offers has non-zero price."""
    html_doc = (
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "WebApplication", "name": "App", '
        '"applicationCategory": "BusinessApplication", '
        '"offers": {"@type": "Offer", "price": "49", "priceCurrency": "USD"}}'
        '</script>'
    )
    issues = detect_free_web_application_schema_issues(html_doc)
    assert any("requires offers with 'price': '0'" in i for i in issues)
    with pytest.raises(ValueError, match="price"):
        assert_free_web_application_schema(html_doc)


def test_assert_free_web_application_schema_invalid_currency():
    """Verifies error raised when priceCurrency is missing or not ISO 4217."""
    html_doc = (
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "WebApplication", "name": "App", '
        '"applicationCategory": "BusinessApplication", '
        '"offers": {"@type": "Offer", "price": "0", "priceCurrency": "INVALID_CURRENCY"}}'
        '</script>'
    )
    issues = detect_free_web_application_schema_issues(html_doc)
    assert any("requires valid ISO 4217 currency" in i for i in issues)
    with pytest.raises(ValueError, match="currency"):
        assert_free_web_application_schema(html_doc)


def test_factor12_structured_data_integration_with_free_schema():
    """Verifies verify_html_structured_data with require_free_app_schema=True."""
    html_valid = (
        '<!DOCTYPE html><html lang="en"><head><title>App</title>'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "WebApplication", "name": "Valid App", '
        '"applicationCategory": "UtilityApplication", "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}}'
        '</script></head><body><h1>Title</h1></body></html>'
    )
    res_valid = verify_html_structured_data(html_valid, require_free_app_schema=True)
    assert res_valid["status"] == "PASS"

    html_no_free = (
        '<!DOCTYPE html><html lang="en"><head><title>App</title>'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "WebApplication", "name": "Paid App", '
        '"applicationCategory": "UtilityApplication", "offers": {"@type": "Offer", "price": "99", "priceCurrency": "USD"}}'
        '</script></head><body><h1>Title</h1></body></html>'
    )
    res_no_free = verify_html_structured_data(html_no_free, require_free_app_schema=True)
    assert res_no_free["status"] == "FAIL"
    assert any("requires offers with 'price': '0'" in i for i in res_no_free["issues"])


# =============================================================================
# 3. Operational Rate-Limit & Bot Shield Verification Tests
# =============================================================================

def test_rate_limit_and_bot_shield_valid_headers_string():
    """Verifies headers string with X-RateLimit-Limit passes."""
    headers_text = (
        "/*\n"
        "  X-RateLimit-Limit: 120\n"
        "  X-RateLimit-Remaining: 119\n"
        "  Cache-Control: public, max-age=3600\n"
    )
    assert assert_rate_limit_and_bot_shield(headers_text) is True
    res = verify_rate_limit_and_bot_shield(headers_text)
    assert res["status"] == "PASS"
    assert res["violations_count"] == 0


def test_rate_limit_and_bot_shield_valid_headers_dict():
    """Verifies header dictionary with rate limit and cloudflare ray passes."""
    headers_dict = {
        "x-ratelimit-limit": "100",
        "cf-ray": "8db3481b9e072b21-SJC",
        "cache-control": "public, max-age=1800",
    }
    assert assert_rate_limit_and_bot_shield(headers_dict) is True
    res = verify_rate_limit_and_bot_shield(headers_dict)
    assert res["status"] == "PASS"


def test_rate_limit_and_bot_shield_valid_html_turnstile():
    """Verifies HTML containing Cloudflare Turnstile bot shield passes."""
    html_doc = (
        '<!DOCTYPE html><html><head><title>Secure Tool</title></head><body>'
        '<form>'
        '<div class="cf-turnstile" data-sitekey="0x4AAAAAA"></div>'
        '<button type="submit">Submit</button>'
        '</form>'
        '</body></html>'
    )
    assert assert_rate_limit_and_bot_shield(html_doc) is True


def test_rate_limit_and_bot_shield_valid_client_cache_hook():
    """Verifies HTML with client-side cache control meta tag passes."""
    html_doc = (
        '<!DOCTYPE html><html><head>'
        '<meta http-equiv="cache-control" content="public, max-age=86400" />'
        '<title>Cached Tool</title></head><body><h1>Tool</h1></body></html>'
    )
    assert assert_rate_limit_and_bot_shield(html_doc) is True


def test_rate_limit_and_bot_shield_missing_indicators():
    """Verifies error raised when neither rate limit, bot shield, nor cache hooks exist."""
    headers_empty: Dict[str, str] = {}
    issues = detect_rate_limit_and_bot_shield_issues(headers_empty)
    assert len(issues) == 1
    assert "Missing operational rate-limit headers" in issues[0]
    with pytest.raises(ValueError, match="Operational rate-limit and bot shield violation"):
        assert_rate_limit_and_bot_shield(headers_empty)


def test_rate_limit_and_bot_shield_forbidden_dashes():
    """Verifies forbidden dashes in headers text trigger contract error."""
    bad_headers = "X-RateLimit-Limit: 100 " + chr(0x2014)
    issues = detect_rate_limit_and_bot_shield_issues(bad_headers)
    assert any("forbidden em-dash" in i for i in issues)
    with pytest.raises(ValueError, match="forbidden em-dash"):
        assert_rate_limit_and_bot_shield(bad_headers)


# =============================================================================
# 4. Maintenance DriftReason & AssetIntegrityEvaluator Tests
# =============================================================================

def test_maintenance_drift_reason_operational_shield_gap_enum():
    """Verifies DriftReason.OPERATIONAL_SHIELD_GAP is correctly registered in taxonomy."""
    assert hasattr(DriftReason, "OPERATIONAL_SHIELD_GAP")
    assert DriftReason.OPERATIONAL_SHIELD_GAP.value == "OPERATIONAL_SHIELD_GAP"
    assert DriftReason.OPERATIONAL_SHIELD_GAP == "OPERATIONAL_SHIELD_GAP"


def test_asset_integrity_evaluator_with_operational_shield_enforcement(tmp_path):
    """Verifies AssetIntegrityEvaluator catches OPERATIONAL_SHIELD_GAP when enabled."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True)

    adapter = ConfigurablePropertyAdapter(
        property_id="test_property",
        brand_name="TestBrand",
        domain="testbrand.com",
        canonical_base="https://testbrand.com",
        dist_dir=dist_dir,
    )

    # Asset without operational shield
    unshielded_html = (
        '<!DOCTYPE html><html lang="en"><head><title>Unshielded</title></head>'
        '<body><h1>Clean Title</h1><p>Compliant text.</p></body></html>'
    )
    unshielded_file = dist_dir / "unshielded.html"
    unshielded_file.write_text(unshielded_html, encoding="utf-8")

    # When enforce_operational_shield is False, unshielded asset produces zero drift reasons
    evaluator_lenient = AssetIntegrityEvaluator(enforce_operational_shield=False)
    record_lenient = evaluator_lenient.audit_asset(unshielded_file, adapter)
    assert record_lenient is None

    # When enforce_operational_shield is True, unshielded asset flags OPERATIONAL_SHIELD_GAP
    evaluator_strict = AssetIntegrityEvaluator(enforce_operational_shield=True)
    record_strict = evaluator_strict.audit_asset(unshielded_file, adapter)
    assert record_strict is not None
    assert DriftReason.OPERATIONAL_SHIELD_GAP in record_strict.reasons
    assert any("Operational shield gap" in d for d in record_strict.details)

    # When shielded asset is tested, passes audit cleanly
    shielded_html = (
        '<!DOCTYPE html><html lang="en"><head><title>Shielded</title>'
        '<meta http-equiv="cache-control" content="public, max-age=3600" />'
        '</head><body><h1>Clean Title</h1><p>Compliant text.</p></body></html>'
    )
    shielded_file = dist_dir / "shielded.html"
    shielded_file.write_text(shielded_html, encoding="utf-8")
    record_shielded = evaluator_strict.audit_asset(shielded_file, adapter)
    assert record_shielded is None


# =============================================================================
# 5. MasterSEOVerifier Gate Methods & Checklist Integration Tests
# =============================================================================

def test_master_seo_verifier_tool_utility_gate(tmp_path):
    """Verifies check_tool_utility_gate on MasterSEOVerifier across positive and negative cases."""
    verifier_inst = MasterSEOVerifier()

    compliant_html = (
        '<div class="tool-calculator">'
        '<form>'
        '<label for="input-data">Data</label>'
        '<input type="text" id="input-data" name="data" />'
        '<button type="submit">Run</button>'
        '</form></div>'
    )
    res_pos = verifier_inst.check_tool_utility_gate(compliant_html)
    assert res_pos["status"] == "PASS"
    assert res_pos["tool_valid"] is True

    non_compliant_html = '<p>No form here</p>'
    res_neg = verifier_inst.check_tool_utility_gate(non_compliant_html)
    assert res_neg["status"] == "FAIL"
    assert res_neg["tool_valid"] is False

    # Alias check
    assert verifier_inst.verify_tool_utility_contract(compliant_html)["status"] == "PASS"
    assert check_tool_utility_gate(compliant_html)["status"] == "PASS"
    assert verify_tool_utility_contract(compliant_html)["status"] == "PASS"


def test_master_seo_verifier_free_schema_gate():
    """Verifies check_free_web_application_schema_gate on MasterSEOVerifier."""
    verifier_inst = MasterSEOVerifier()

    compliant_schema = (
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "WebApplication", "name": "Free Tool", '
        '"applicationCategory": "BusinessApplication", "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}}'
        '</script>'
    )
    res_pos = verifier_inst.check_free_web_application_schema_gate(compliant_schema)
    assert res_pos["status"] == "PASS"

    non_compliant_schema = (
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "WebApplication", "name": "Paid Tool", '
        '"applicationCategory": "BusinessApplication", "offers": {"@type": "Offer", "price": "10", "priceCurrency": "USD"}}'
        '</script>'
    )
    res_neg = verifier_inst.check_free_web_application_schema_gate(non_compliant_schema)
    assert res_neg["status"] == "FAIL"

    # Aliases
    assert verifier_inst.verify_free_web_application_schema(compliant_schema)["status"] == "PASS"
    assert check_free_web_application_schema_gate(compliant_schema)["status"] == "PASS"
    assert verify_free_web_application_schema(compliant_schema)["status"] == "PASS"


def test_master_seo_verifier_operational_shield_gate():
    """Verifies check_operational_shield_gate and verify_operational_shield on MasterSEOVerifier."""
    verifier_inst = MasterSEOVerifier()

    headers_dict = {"x-ratelimit-limit": "60"}
    res_pos = verifier_inst.check_operational_shield_gate(headers_dict)
    assert res_pos["status"] == "PASS"

    res_neg = verifier_inst.check_operational_shield_gate({})
    assert res_neg["status"] == "FAIL"

    # Aliases
    assert verifier_inst.verify_operational_shield(headers_dict)["status"] == "PASS"
    assert check_operational_shield_gate(headers_dict)["status"] == "PASS"
    assert verify_operational_shield(headers_dict)["status"] == "PASS"


def test_audit_seo_checklist_includes_new_gates(tmp_path):
    """Verifies that audit_seo_checklist evaluates check_tool_utility_gate and other new gates."""
    dist_dir = tmp_path / "dist_test"
    dist_dir.mkdir(parents=True)
    tool_dir = dist_dir / "tools" / "calc"
    tool_dir.mkdir(parents=True)

    tool_html = (
        '<!DOCTYPE html><html lang="en"><head><title>Tool Title Here Length 50 to 60 Chars Testing</title>'
        '<meta name="description" content="Meta description between seventy and one hundred sixty characters long for SEO." />'
        '<link rel="canonical" href="https://example.com/tools/calc/" />'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "WebApplication", "name": "Tool", '
        '"applicationCategory": "BusinessApplication", "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}}'
        '</script>'
        '</head><body>'
        '<h1>Tool Calculator</h1>'
        '<div class="calculation-widget">'
        '<form>'
        '<label for="f">Input Field</label>'
        '<input type="number" id="f" name="f" value="100" />'
        '<button type="submit">Submit</button>'
        '</form>'
        '</div>'
        '</body></html>'
    )
    (tool_dir / "index.html").write_text(tool_html, encoding="utf-8")

    verifier_inst = MasterSEOVerifier(dist_dir=dist_dir)
    res = verifier_inst.audit_seo_checklist(dist_dir, enforce_relevance=False)
    gates = res["gates"]

    assert "check_tool_utility_gate" in gates
    assert "check_free_web_application_schema_gate" in gates
    assert "check_operational_shield_gate" in gates
    assert gates["check_tool_utility_gate"]["status"] == "PASS"
    assert gates["check_free_web_application_schema_gate"]["status"] == "PASS"


# =============================================================================
# 6. Re-exports and Packaging Invariant Tests
# =============================================================================

def test_module_re_exports_and_all():
    """Verifies that all new contract and verifier functions are re-exported at top-level."""
    expected_exports = [
        "ToolUtilityHTMLParser",
        "detect_tool_utility_issues",
        "assert_tool_utility_contract",
        "detect_free_web_application_schema_issues",
        "assert_free_web_application_schema",
        "detect_rate_limit_and_bot_shield_issues",
        "assert_rate_limit_and_bot_shield",
        "check_tool_utility_gate",
        "verify_tool_utility_contract",
        "verify_html_tool_utility_contract",
        "check_free_web_application_schema_gate",
        "verify_free_web_application_schema",
        "verify_html_free_web_application_schema",
        "check_operational_shield_gate",
        "verify_operational_shield",
        "verify_rate_limit_and_bot_shield",
    ]
    for symbol in expected_exports:
        assert hasattr(pseofactory, symbol), f"pseofactory missing export: {symbol}"
        assert symbol in pseofactory.__all__, f"pseofactory.__all__ missing: {symbol}"


def test_zero_forbidden_dashes_in_new_code():
    """Mechanical invariant test: zero em-dashes and zero en-dashes in contracts, verifier, maintenance, and tests."""
    repo_root = Path(__file__).resolve().parent.parent

    target_files = [
        repo_root / "pseofactory" / "contracts.py",
        repo_root / "pseofactory" / "verifier.py",
        repo_root / "pseofactory" / "maintenance.py",
        repo_root / "pseofactory_tests" / "test_free_tools_contracts.py",
    ]

    for p in target_files:
        assert p.is_file(), f"Target file not found: {p}"
        content = p.read_text(encoding="utf-8")
        assert "\u2014" not in content, f"Forbidden em-dash (\\u2014) detected in {p.name}"
        assert "\u2013" not in content, f"Forbidden en-dash (\\u2013) detected in {p.name}"
