"""
Tests for pseofactory Google Search Central Compliance Matrix
Validates:
1. GoogleSearchCentralComplianceMatrix instantiation and catalog.
2. Single-asset audit with DOM-to-Schema parity, viewport, and template leakage gates.
3. Site corpus audit with pairwise token Jaccard doorway rejection (>0.75) and cannibalization detection.
4. AST-to-JS client calculation parity within 0.01 tolerance.
5. Indexing preflight audit with soft 404 detection and multiple canonical rejection.

Zero em-dashes. Zero en-dashes.
"""

from pathlib import Path
import pytest

from pseofactory.compliance import (
    GoogleSearchCentralComplianceMatrix,
    ComplianceStatus,
    ComplianceSeverity,
    AssetComplianceReport,
    SiteCorpusComplianceReport,
    PRINCIPLE_CATALOG,
)
from pseofactory.compiler import compile_high_effort_page
from pseofactory.indexing.preflight import PreflightStatus


@pytest.fixture
def compliance_matrix():
    return GoogleSearchCentralComplianceMatrix()


@pytest.fixture
def clean_spec():
    return {
        "query": "section 179 equipment expense tax deduction calculator",
        "slug": "section-179-equipment-expense-tax-deduction-calculator",
        "tenant": "profithelm",
        "statutory_authority": "IRC Section 179(b)(1)",
        "economic_dataset": "FRED CPILFESL Series",
        "model_name": "Section 179 Grounded Model",
        "formula": "min(cost, cap)",
        "inputs": {"cost": 400000, "cap": 1220000},
        "published_output": 400000.0,
        "sample_calculation": "Cost 400,000 under cap 1,220,000 gives 400,000 deduction",
        "canonical_base": "https://profithelm.com",
    }


def test_compliance_matrix_catalog(compliance_matrix):
    """Verifies that all 11 Google Search Central principles are registered."""
    assert len(compliance_matrix.principles) == 11
    principle_ids = [p.principle_id for p in compliance_matrix.principles]
    assert "GSC-TECH-01" in principle_ids
    assert "GSC-TECH-04" in principle_ids
    assert "GSC-SPAM-01" in principle_ids
    assert "GSC-SPAM-02" in principle_ids
    assert "GSC-SPAM-03" in principle_ids
    assert "GSC-SPAM-04" in principle_ids
    assert "GSC-HELP-01" in principle_ids


def test_single_asset_clean_compilation_passes(compliance_matrix, clean_spec):
    """Clean compiled asset satisfies all single-asset compliance principles."""
    res = compile_high_effort_page(clean_spec)
    report = compliance_matrix.audit_single_asset(res["html"], clean_spec)

    assert isinstance(report, AssetComplianceReport)
    assert report.overall_pass is True
    assert len(report.blocking_violations) == 0
    assert report.verdicts_by_principle["GSC-SPAM-03"].status == ComplianceStatus.PASS
    assert report.verdicts_by_principle["GSC-TECH-04"].status == ComplianceStatus.PASS
    assert report.verdicts_by_principle["GSC-SPAM-02"].status == ComplianceStatus.PASS
    assert report.verdicts_by_principle["GSC-SPAM-04"].status == ComplianceStatus.PASS


def test_single_asset_hidden_faq_schema_rejected(compliance_matrix, clean_spec):
    """Fails GSC-SPAM-03 when FAQPage schema exists but FAQ accordions are absent from DOM."""
    res = compile_high_effort_page(clean_spec)
    # Strip visible FAQ accordion from HTML body
    tampered_html = res["html"].replace('<details class="faq-accordion">', '<div class="hidden-accordion" style="display:none;">')

    report = compliance_matrix.audit_single_asset(tampered_html, clean_spec)
    assert report.overall_pass is False
    verdict = report.verdicts_by_principle["GSC-SPAM-03"]
    assert verdict.status == ComplianceStatus.FAIL
    assert any("0 visible <details class=\"faq-accordion\">" in v for v in verdict.violations)


def test_single_asset_missing_viewport_rejected(compliance_matrix, clean_spec):
    """Fails GSC-TECH-04 when mobile viewport meta tag is missing."""
    res = compile_high_effort_page(clean_spec)
    tampered_html = res["html"].replace('name="viewport"', 'name="viewport-disabled"')

    report = compliance_matrix.audit_single_asset(tampered_html, clean_spec)
    assert report.overall_pass is False
    verdict = report.verdicts_by_principle["GSC-TECH-04"]
    assert verdict.status == ComplianceStatus.FAIL
    assert any("viewport" in v.lower() for v in verdict.violations)


def test_single_asset_spaced_template_leakage_and_nan(compliance_matrix, clean_spec):
    """Fails GSC-SPAM-02 on spaced format strings and visible NaN text."""
    res = compile_high_effort_page(clean_spec)

    # 1. Spaced format leakage
    html_with_leak = res["html"].replace("</div>", " { user_identity_token } </div>", 1)
    rep_leak = compliance_matrix.audit_single_asset(html_with_leak, clean_spec)
    assert rep_leak.overall_pass is False
    assert rep_leak.verdicts_by_principle["GSC-SPAM-02"].status == ComplianceStatus.FAIL

    # 2. NaN presence outside script tags
    html_with_nan = res["html"].replace("400,000", "NaN", 1)
    rep_nan = compliance_matrix.audit_single_asset(html_with_nan, clean_spec)
    assert rep_nan.overall_pass is False
    assert rep_nan.verdicts_by_principle["GSC-SPAM-02"].status == ComplianceStatus.FAIL
    assert any("NaN" in v for v in rep_nan.verdicts_by_principle["GSC-SPAM-02"].violations)


def test_site_corpus_doorway_rejection(compliance_matrix, clean_spec):
    """Strictly rejects site corpus with pairwise token Jaccard similarity > 0.75."""
    res1 = compile_high_effort_page(clean_spec)

    # Construct near-identical variant differing by only 1 word (geo swap)
    spec_geo = dict(clean_spec)
    spec_geo["slug"] = "texas-section-179-equipment-expense-tax-deduction-calculator"
    spec_geo["query"] = "texas section 179 equipment expense tax deduction calculator"
    res2 = compile_high_effort_page(spec_geo)

    corpus = [
        (clean_spec["slug"], res1["html"], clean_spec),
        (spec_geo["slug"], res2["html"], spec_geo),
    ]

    report = compliance_matrix.audit_site_corpus(corpus, jaccard_ceiling=0.75)
    assert isinstance(report, SiteCorpusComplianceReport)
    assert report.overall_pass is False
    assert report.pairwise_divergence_passed is False
    assert report.cross_asset_jaccard_max > 0.75
    verdict = report.corpus_verdicts["GSC-SPAM-01"]
    assert verdict.status == ComplianceStatus.FAIL
    assert any("exceeds doorway ceiling" in v for v in verdict.violations)


def test_site_corpus_diverse_assets_pass(compliance_matrix, clean_spec):
    """Diverse assets with distinct topics and formulas pass corpus doorway check."""
    res1 = compile_high_effort_page(clean_spec)

    spec_student_loan = {
        "query": "direct consolidation loan repayment assistance plan estimator",
        "slug": "direct-consolidation-loan-repayment-assistance-plan-estimator",
        "tenant": "prexvo",
        "statutory_authority": "34 CFR Part 685",
        "economic_dataset": "BLS Wage and Employment Series",
        "model_name": "Direct Loan RAP Grounded Model",
        "formula": "round(max(0, income - (2.25 * poverty_line)) * 0.05 / 12, 2)",
        "inputs": {"income": 55000, "poverty_line": 15060},
        "published_output": 87.98,
        "sample_calculation": "Discretionary calculation on 55,000 income gives 87.98 monthly",
        "canonical_base": "https://prexvo.com",
    }
    res2 = compile_high_effort_page(spec_student_loan)

    corpus = [
        (clean_spec["slug"], res1["html"], clean_spec),
        (spec_student_loan["slug"], res2["html"], spec_student_loan),
    ]

    report = compliance_matrix.audit_site_corpus(corpus, jaccard_ceiling=0.75)
    assert report.overall_pass is True
    assert report.pairwise_divergence_passed is True
    assert report.cross_asset_jaccard_max < 0.75
    assert report.corpus_verdicts["GSC-SPAM-01"].status == ComplianceStatus.PASS


def test_verify_ast_client_js_parity(compliance_matrix):
    """Verifies numerical parity between Python safe_eval and client JavaScript."""
    spec = {
        "formula": "min(cost, cap)",
    }
    inputs = {"cost": 400000, "cap": 1220000}
    parity_ok = compliance_matrix.verify_ast_client_js_parity(spec, inputs)
    assert parity_ok is True

    # Floating point arithmetic formula
    spec_calc = {
        "formula": "round((balance * rate) / 12, 2)",
    }
    calc_inputs = {"balance": 50000, "rate": 0.065}
    parity_ok2 = compliance_matrix.verify_ast_client_js_parity(spec_calc, calc_inputs)
    assert parity_ok2 is True


def test_audit_indexing_preflight_soft_404(compliance_matrix, tmp_path):
    """Verifies that audit_indexing_preflight rejects soft-404 and multi-canonical pages."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True)

    # 1. Soft 404 page returning HTTP 200 but saying "Page not found"
    soft404_dir = dist_dir / "tools" / "soft404"
    soft404_dir.mkdir(parents=True)
    soft404_html = (
        '<!DOCTYPE html><html><head>'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        '<link rel="canonical" href="https://profithelm.com/tools/soft404/" />'
        '</head><body><h1>Calculator Not Found</h1>'
        '<aside class="quick-answer">Direct definition answer block</aside>'
        '<p>This tool has been discontinued and is not found.</p>'
        + ' word' * 200 + '</body></html>'
    )
    (soft404_dir / "index.html").write_text(soft404_html, encoding="utf-8")

    # 2. Page with conflicting duplicate canonical tags
    multicanon_dir = dist_dir / "tools" / "multicanon"
    multicanon_dir.mkdir(parents=True)
    multicanon_html = (
        '<!DOCTYPE html><html><head>'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        '<link rel="canonical" href="https://profithelm.com/tools/multicanon/" />'
        '<link rel="canonical" href="https://profithelm.com/tools/other/" />'
        '</head><body><h1>Multi Canonical</h1>'
        '<aside class="quick-answer">Direct definition answer block</aside>'
        + ' word' * 200 + '</body></html>'
    )
    (multicanon_dir / "index.html").write_text(multicanon_html, encoding="utf-8")

    urls = [
        "https://profithelm.com/tools/soft404/",
        "https://profithelm.com/tools/multicanon/",
    ]
    report = compliance_matrix.audit_indexing_preflight(urls=urls, dist_dir=dist_dir)

    assert report.is_gate_passed is False
    assert report.blocked_count == 2
    assert "https://profithelm.com/tools/soft404/" in report.blocked_urls
    assert "https://profithelm.com/tools/multicanon/" in report.blocked_urls
