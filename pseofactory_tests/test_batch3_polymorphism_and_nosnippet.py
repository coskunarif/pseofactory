"""
Batch 3C Verification Suite:
1. Cross-domain governance copy polymorphism (< 0.50 pairwise <main> similarity across 4 live profiles
   and dynamic 50+ tenant hashing without hardcoded tenant lists).
2. Cross-domain CSS design-token & layout-cluster polymorphism preserving WCAG AA, 44px touch targets,
   and Porcelain layout invariants.
3. audit_cross_tenant_footprint_variance() pass + fail-closed checks.
4. Opt-in 1-tenant data-nosnippet split-test gate (default False, balanced wrappers on non-cliff
   secondary lookup tables & workpaper preview blocks only).
5. detect_data_nosnippet_markup_issues() + verifier fail-closed enforcement against boolean traps
   (data-nosnippet="false", data-nosnippet="true"), unclosed/unbalanced tags, and root/quick-answer blocks.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import difflib
import html as html_lib
import re
from pathlib import Path
from typing import Dict, List

import pytest

from pseofactory.contracts import (
    assert_ai_crawl_access_and_snippet_eligibility,
    detect_data_nosnippet_markup_issues,
)
from pseofactory.porcelain_shell import (
    GOVERNANCE_ROUTES,
    _extract_defined_css_classes_for_audit,
    audit_porcelain_shell_page,
    build_governance_pages,
    extract_defined_and_referenced_css_vars,
    generate_porcelain_stylesheet,
    generate_porcelain_stylesheet_from_profile,
    get_porcelain_tenant_profile,
    is_nosnippet_split_test_enabled,
    normalize_html_to_porcelain_shell,
)
from pseofactory.verifier import (
    MasterSEOVerifier,
    audit_cross_tenant_footprint_variance,
    verify_html_ai_crawl_access_and_snippet_eligibility,
)

LIVE_TENANTS = ("gainhelm", "lienbond", "prexvo", "profithelm")


def _extract_main_words(html_text: str) -> List[str]:
    m = re.search(r"<main\b[^>]*>([\s\S]*?)</main>", html_text, flags=re.IGNORECASE)
    region = m.group(1) if m else html_text
    region = re.sub(r"<(script|style|noscript|svg)\b[^>]*>[\s\S]*?</\1>", " ", region, flags=re.IGNORECASE)
    plain = html_lib.unescape(re.sub(r"<[^>]+>", " ", region))
    return re.findall(r"[a-z0-9]+", plain.lower())


def _make_synthetic_profile(prop_id: str) -> Dict[str, object]:
    """Builds a synthetic non-registered tenant profile to test 50+ domain polymorphism."""
    base = get_porcelain_tenant_profile("profithelm")
    brand = " ".join(w.capitalize() for w in prop_id.replace("-", "_").split("_") if w)
    domain = f"{prop_id}.com"
    prof = dict(base)
    prof.update(
        {
            "property_id": prop_id,
            "package_name": prop_id.replace("-", "_"),
            "repo_dir_name": prop_id,
            "brand_name": brand,
            "domain": domain,
            "canonical_base": f"https://{domain}",
            "linkedin_company_id": "",
            "research_entity": f"{brand} Research Group",
            "legal_entity": f"{brand} LLC",
            "publisher_entity_label": f"{brand} LLC",
            "impact_verification_uuid": "",
            "cj_property_id": "",
            "sovrn_domain_key": "",
            "contact_email": f"editorial@{domain}",
            "editorial_classification": f"Deterministic {brand} Modeling Engine",
            "primary_statutory_authority": f"{brand} Federal & State Statutory Code",
            "economic_dataset_label": f"{brand} Empirical Public Benchmark Series",
            "home_topic_label": f"{brand} Statutory & Quantitative Calculators",
            "tools_directory_topic_label": f"{brand} Interactive Decision Models",
            "default_gsc_token": "",
            "default_tools": [
                (f"{prop_id}-primary-estimator", f"{brand} Primary Exposure Estimator"),
                (f"{prop_id}-compliance-matrix", f"{brand} Compliance Matrix Calculator"),
            ],
        }
    )
    return prof


def _sample_calculator_html(brand: str, slug: str, prop_id: str) -> str:
    qa = (
        f"Use this deterministic {brand} statutory model governed by enacted federal and state schedules "
        "to calculate baseline exposure, marginal effective rates, phaseout adjustments, and annual compliance "
        "thresholds in real time across multi-year filing scenarios while verifying statutory cliffs before "
        "exporting a structured audit workpaper."
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <title>Statutory Exposure Calculator | {brand}</title>
  <meta name="description" content="Deterministic {brand} statutory exposure and multi-year cliff calculator.">
</head>
<body>
  <main>
    <section class="hero-section card">
      <h1>{brand} Statutory Exposure Calculator</h1>
      <aside class="quick-answer" role="region" aria-label="Quick Answer Summary">
        <p class="quick-answer-body">{qa}</p>
      </aside>
    </section>
    <div class="interactive-calculator-container" id="calculator-workspace-anchor">
      <div class="calc-grid">
        <div class="calc-inputs-column">
          <form id="calc-form">
            <label for="base_amt">Base Amount</label>
            <input id="base_amt" type="number" value="125000">
            <button id="calculate-btn" type="submit">Calculate</button>
          </form>
        </div>
        <div id="calc-results" class="calc-results-column result-box">
          <div class="calc-metrics-grid">
            <div class="calc-metric-card calc-metric-highlight">
              <div class="calc-metric-label">Primary Scope Total</div>
              <div class="calc-metric-value" id="metric-primary_total">$12,500</div>
            </div>
          </div>
          <div class="calc-geo-answer-box">
            <div class="calc-geo-answer-title">Primary Scope Summary</div>
            <p>Baseline annual statutory calculation equals $12,500 under standard thresholds.</p>
          </div>
          <div class="workpaper-preview-controls" data-step="1" data-property-id="{prop_id}" data-tool-slug="{slug}">
            <button type="button" id="btn-preview-workpaper" class="workpaper-preview-btn">Preview Workpaper</button>
          </div>
          <div id="workpaper-preview-panel" class="workpaper-preview-panel" hidden data-tool-slug="{slug}">
            <div class="workpaper-preview-row"><span>Row 1</span><span>$12,500</span></div>
            <div class="workpaper-preview-row workpaper-preview-locked"><span>Locked Appendix</span><span>Unlock</span></div>
          </div>
        </div>
      </div>
    </div>
    <section id="workpaper-unlock-card" class="workpaper-unlock-card card pseo-card">
      <h2>Download Audit Workpaper</h2>
      <button type="button" class="workpaper-cta-primary" data-checkout-trigger="1" data-offer-price="29">Unlock ($29)</button>
    </section>
    <section class="serp-cliff-visualizer card" id="multi-year-cliff-visualizer">
      <h2>Multi-Year Statutory Cliff Summary</h2>
      <div class="table-wrap pseo-table-wrap">
        <table class="serp-cliff-matrix-table">
          <thead><tr><th>Year</th><th>Cliff Exposure</th></tr></thead>
          <tbody><tr><td>2026</td><td id="cliff-exposure-2026">$12,500</td></tr></tbody>
        </table>
      </div>
    </section>
    <section class="comparison-table-section card">
      <h2>Secondary Scenario Lookup Table</h2>
      <div class="table-wrap pseo-table-wrap">
        <table class="scenario-table comparison-table">
          <thead><tr><th>Input Tier</th><th>Estimated Liability</th></tr></thead>
          <tbody><tr><td>$100,000</td><td>$10,000</td></tr><tr><td>$250,000</td><td>$25,000</td></tr></tbody>
        </table>
      </div>
    </section>
    <section class="card">
      <h2>Statutory Pitfalls Reference Matrix</h2>
      <div class="table-wrap pseo-table-wrap">
        <table class="statutory-pitfalls-table">
          <thead><tr><th>Trigger</th><th>Penalty</th></tr></thead>
          <tbody><tr><td>Late Filing</td><td>5% monthly</td></tr></tbody>
        </table>
      </div>
    </section>
  </main>
</body>
</html>"""


def test_cross_domain_governance_copy_polymorphism_below_50_percent():
    """Verify <main> pairwise word similarity across all 4 live profiles is strictly < 0.50."""
    govs: Dict[str, Dict[str, str]] = {
        tid: build_governance_pages(get_porcelain_tenant_profile(tid)) for tid in LIVE_TENANTS
    }

    for tid, pages in govs.items():
        assert set(pages.keys()) == set(GOVERNANCE_ROUTES)
        for route, html_doc in pages.items():
            assert "\u2014" not in html_doc and "\u2013" not in html_doc
            issues = audit_porcelain_shell_page(html_doc, f"{route}/index.html", property_id=tid)
            assert issues == [], f"{tid}/{route} failed shell audit: {issues}"
            qa_m = re.search(
                r'<aside\b[^>]*class=["\'][^"\']*\bquick-answer\b[^"\']*["\'][^>]*>([\s\S]*?)</aside>',
                html_doc,
                flags=re.IGNORECASE,
            )
            assert qa_m, f"{tid}/{route} missing quick-answer"
            qa_words = re.sub(r"<[^>]+>", " ", qa_m.group(1)).split()
            assert 40 <= len(qa_words) <= 60, f"{tid}/{route} quick-answer word count={len(qa_words)}"

        partners_html = pages["partners"]
        assert 'data-partners-page="1"' in partners_html
        assert 'name="offer_sku"' in partners_html
        assert 'action="/api/lead-capture"' in partners_html
        assert 'id="partner-registration-form"' in partners_html

    for route in ("about", "partners", "contact", "terms", "privacy"):
        for i in range(len(LIVE_TENANTS)):
            for j in range(i + 1, len(LIVE_TENANTS)):
                t1, t2 = LIVE_TENANTS[i], LIVE_TENANTS[j]
                w1 = _extract_main_words(govs[t1][route])
                w2 = _extract_main_words(govs[t2][route])
                s1, s2 = set(w1), set(w2)
                jaccard = len(s1 & s2) / max(1, len(s1 | s2))
                seq = difflib.SequenceMatcher(None, w1, w2, autojunk=False).ratio()
                assert jaccard < 0.50, f"/{route}/ {t1} vs {t2} jaccard={jaccard:.4f} >= 0.50"
                assert seq < 0.50, f"/{route}/ {t1} vs {t2} sequence={seq:.4f} >= 0.50"

    # Multi-tenant dynamic scalability: 6 arbitrary unknown domains with zero hardcoded lists
    synthetic_props = (
        "meridian-tax",
        "harbor-surety",
        "cedar-compliance",
        "summit-student",
        "keystone-payroll",
        "beacon-audit",
    )
    synth_profiles = {sp: _make_synthetic_profile(sp) for sp in synthetic_props}
    synth_abouts = {sp: build_governance_pages(prof)["about"] for sp, prof in synth_profiles.items()}
    assert len(set(synth_abouts.values())) == len(synthetic_props)
    for sp, html_doc in synth_abouts.items():
        css_sp = generate_porcelain_stylesheet_from_profile(synth_profiles[sp])
        vars_sp, _ = extract_defined_and_referenced_css_vars(css_sp)
        classes_sp = _extract_defined_css_classes_for_audit(css_sp)
        assert (
            audit_porcelain_shell_page(
                html_doc,
                "about/index.html",
                css_defined_vars=vars_sp,
                css_defined_classes=classes_sp,
            )
            == []
        )


def test_cross_domain_css_polymorphism_and_wcag_invariants():
    """Verify per-domain CSS variants drop pairwise similarity well below legacy 98.5%+ while keeping invariants."""
    css_by_tenant = {tid: generate_porcelain_stylesheet(tid) for tid in LIVE_TENANTS}

    for tid, css_text in css_by_tenant.items():
        assert "\u2014" not in css_text and "\u2013" not in css_text
        assert "--bg-canvas: #fbfcfd;" in css_text
        assert "--bg-surface: #ffffff;" in css_text
        assert "--text-primary: #0f172a;" in css_text
        assert "#calculate-btn" in css_text
        assert "min-height: 44px;" in css_text
        assert "@media print" in css_text
        defined, referenced = extract_defined_and_referenced_css_vars(css_text)
        assert referenced - defined == set()

    for i in range(len(LIVE_TENANTS)):
        for j in range(i + 1, len(LIVE_TENANTS)):
            t1, t2 = LIVE_TENANTS[i], LIVE_TENANTS[j]
            l1 = css_by_tenant[t1].splitlines()
            l2 = css_by_tenant[t2].splitlines()
            seq = difflib.SequenceMatcher(None, l1, l2, autojunk=False).ratio()
            s1 = {ln.strip() for ln in l1 if ln.strip()}
            s2 = {ln.strip() for ln in l2 if ln.strip()}
            jac = len(s1 & s2) / max(1, len(s1 | s2))
            assert seq < 0.50, f"CSS {t1} vs {t2} line_seq={seq:.4f} >= 0.50"
            assert jac < 0.60, f"CSS {t1} vs {t2} line_jaccard={jac:.4f} >= 0.60"

    # Unknown domains dynamically resolve distinct CSS variants
    c1 = generate_porcelain_stylesheet_from_profile(_make_synthetic_profile("alpha-ledger"))
    c2 = generate_porcelain_stylesheet_from_profile(_make_synthetic_profile("delta-surety"))
    assert c1 != c2


def test_audit_cross_tenant_footprint_variance_pass_and_fail_closed(tmp_path: Path):
    """Verify audit_cross_tenant_footprint_variance passes polymorphic builds and fails closed on clones."""
    dist_map: Dict[str, Path] = {}
    for tid in LIVE_TENANTS:
        d = tmp_path / tid / "dist"
        (d / "css").mkdir(parents=True, exist_ok=True)
        (d / "css" / "style.css").write_text(generate_porcelain_stylesheet(tid), encoding="utf-8")
        gov = build_governance_pages(get_porcelain_tenant_profile(tid))
        for slug, html_doc in gov.items():
            route_dir = d / slug
            route_dir.mkdir(parents=True, exist_ok=True)
            (route_dir / "index.html").write_text(html_doc, encoding="utf-8")
        dist_map[tid] = d

    res = audit_cross_tenant_footprint_variance(dist_map)
    assert res["status"] == "PASS", res["issues"]
    assert res["passed"] is True
    assert res["max_main_similarity"] < 0.50
    assert res["max_css_similarity"] < 0.50

    # Fail-closed check: clone /about/ from gainhelm into prexvo
    cloned_about = (dist_map["gainhelm"] / "about" / "index.html").read_text(encoding="utf-8")
    (dist_map["prexvo"] / "about" / "index.html").write_text(cloned_about, encoding="utf-8")
    bad_res = audit_cross_tenant_footprint_variance(dist_map)
    assert bad_res["status"] == "FAIL"
    assert bad_res["passed"] is False
    assert any("about" in msg and "gainhelm" in msg and "prexvo" in msg for msg in bad_res["issues"])

    # Fail-closed check: clone style.css across two tenants
    (dist_map["prexvo"] / "about" / "index.html").write_text(
        build_governance_pages(get_porcelain_tenant_profile("prexvo"))["about"],
        encoding="utf-8",
    )
    cloned_css = (dist_map["gainhelm"] / "css" / "style.css").read_text(encoding="utf-8")
    (dist_map["lienbond"] / "css" / "style.css").write_text(cloned_css, encoding="utf-8")
    bad_css_res = audit_cross_tenant_footprint_variance(dist_map)
    assert bad_css_res["status"] == "FAIL"
    assert any("style.css" in msg for msg in bad_css_res["issues"])


def test_opt_in_one_tenant_data_nosnippet_split_test_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Verify:
    1. Default fleet behavior has nosnippet_split_test=False and emits ZERO data-nosnippet.
    2. Opt-in PSEUFACTORY_NOSNIPPET_SPLIT_TENANT=gainhelm wraps non-cliff secondary lookup tables
       and workpaper preview blocks in balanced <div data-nosnippet>...</div> while leaving
       other tenants unchanged and keeping quick-answer, form, primary scope, and cliff visualizer open.
    3. Resulting HTML passes verifier snippet gates and is idempotent across re-normalization.
    """
    monkeypatch.delenv("PSEUFACTORY_NOSNIPPET_SPLIT_TENANT", raising=False)
    gh_prof = get_porcelain_tenant_profile("gainhelm")
    ph_prof = get_porcelain_tenant_profile("profithelm")
    assert gh_prof["nosnippet_split_test_enabled"] is False
    assert is_nosnippet_split_test_enabled(gh_prof) is False

    raw_gh = _sample_calculator_html("GainHelm", "soc-2-audit-cost-calculator", "gainhelm")
    raw_ph = _sample_calculator_html("ProfitHelm", "section-179-calculator", "profithelm")

    default_gh, _ = normalize_html_to_porcelain_shell(raw_gh, "tools/soc-2-audit-cost-calculator/index.html", gh_prof)
    assert "data-nosnippet" not in default_gh

    # Opt-in pilot tenant via env var
    monkeypatch.setenv("PSEUFACTORY_NOSNIPPET_SPLIT_TENANT", "gainhelm")
    assert is_nosnippet_split_test_enabled(gh_prof) is True
    assert is_nosnippet_split_test_enabled(ph_prof) is False

    pilot_gh, _ = normalize_html_to_porcelain_shell(raw_gh, "tools/soc-2-audit-cost-calculator/index.html", gh_prof)
    non_pilot_ph, _ = normalize_html_to_porcelain_shell(raw_ph, "tools/section-179-calculator/index.html", ph_prof)

    assert "data-nosnippet" not in non_pilot_ph
    assert "<div data-nosnippet>" in pilot_gh
    assert 'data-nosnippet="' not in pilot_gh.lower()
    assert detect_data_nosnippet_markup_issues(pilot_gh) == []

    # Idempotency on pass 2
    pilot_gh_pass2, _ = normalize_html_to_porcelain_shell(
        pilot_gh, "tools/soc-2-audit-cost-calculator/index.html", gh_prof
    )
    assert pilot_gh_pass2 == pilot_gh

    # Workpaper preview blocks and secondary lookup tables are wrapped; cliff & quick-answer & form stay open
    assert re.search(r'<div data-nosnippet>\s*<div class="workpaper-preview-controls"', pilot_gh)
    assert re.search(r'<div data-nosnippet>\s*<div id="workpaper-preview-panel"', pilot_gh)
    assert re.search(
        r'<div data-nosnippet>\s*<div class="table-wrap pseo-table-wrap">\s*<table class="scenario-table',
        pilot_gh,
    )
    assert re.search(
        r'<div data-nosnippet>\s*<div class="table-wrap pseo-table-wrap">\s*<table class="statutory-pitfalls-table',
        pilot_gh,
    )
    assert not re.search(r"<div data-nosnippet>[^<]*<table class=\"serp-cliff-matrix-table", pilot_gh)
    assert "<div data-nosnippet><aside class=\"quick-answer\"" not in pilot_gh
    assert "<div data-nosnippet><form" not in pilot_gh

    # Passes all snippet eligibility & contract gates
    assert assert_ai_crawl_access_and_snippet_eligibility(pilot_gh) is True
    v_res = verify_html_ai_crawl_access_and_snippet_eligibility(pilot_gh, "tools/soc-2-audit-cost-calculator/index.html")
    assert v_res["status"] == "PASS", v_res["issues"]

    dist_dir = tmp_path / "dist"
    (dist_dir / "tools" / "soc-2-audit-cost-calculator").mkdir(parents=True, exist_ok=True)
    (dist_dir / "tools" / "soc-2-audit-cost-calculator" / "index.html").write_text(pilot_gh, encoding="utf-8")
    verifier = MasterSEOVerifier(dist_dir=dist_dir, domain="gainhelm.com", allow_mutations=False)
    sg = verifier.check_snippet_gate(dist_dir)
    seg = verifier.check_snippet_eligibility_gate(dist_dir)
    assert sg["status"] == "PASS", sg["issues"]
    assert seg["status"] == "PASS", seg["issues"]


def test_detect_data_nosnippet_markup_issues_and_verifier_fail_closed(tmp_path: Path):
    """
    Verify balanced <div data-nosnippet> is permitted while boolean attribute traps
    (data-nosnippet="false", data-nosnippet="true", data-nosnippet=""), unbalanced/unclosed tags,
    root containers, and quick-answer wrappers FAIL CLOSED.
    """
    qa_50 = " ".join(["statutory"] * 45)
    valid_html = (
        "<!DOCTYPE html><html lang='en'><head><title>Valid</title></head><body><main>"
        f"<aside class='quick-answer'><p>{qa_50}</p></aside>"
        "<div data-nosnippet><div class='table-wrap'><table><tr><td>1</td></tr></table></div></div>"
        "</main></body></html>"
    )
    assert detect_data_nosnippet_markup_issues(valid_html) == []
    assert verify_html_ai_crawl_access_and_snippet_eligibility(valid_html)["status"] == "PASS"

    bad_cases = [
        ("boolean_false", valid_html.replace("<div data-nosnippet>", '<div data-nosnippet="false">')),
        ("boolean_true", valid_html.replace("<div data-nosnippet>", '<div data-nosnippet="true">')),
        ("boolean_empty", valid_html.replace("<div data-nosnippet>", '<div data-nosnippet="">')),
        (
            "unclosed_div",
            "<!DOCTYPE html><html><body><main>"
            f"<aside class='quick-answer'><p>{qa_50}</p></aside>"
            "<div data-nosnippet><p>Unclosed block</p>"
            "</main></body></html>",
        ),
        (
            "unbalanced_section",
            "<!DOCTYPE html><html><body><main>"
            f"<aside class='quick-answer'><p>{qa_50}</p></aside>"
            "<section><div data-nosnippet><p>Out of order</p></section></div>"
            "</main></body></html>",
        ),
        ("root_main", valid_html.replace("<main>", "<main data-nosnippet>")),
        ("qa_wrapped", valid_html.replace("<aside class='quick-answer'>", "<aside class='quick-answer' data-nosnippet>")),
    ]

    for label, bad_html in bad_cases:
        issues = detect_data_nosnippet_markup_issues(bad_html)
        assert issues, f"{label}: detect_data_nosnippet_markup_issues failed to flag"
        with pytest.raises(ValueError):
            assert_ai_crawl_access_and_snippet_eligibility(bad_html)
        v_mem = verify_html_ai_crawl_access_and_snippet_eligibility(bad_html)
        assert v_mem["status"] == "FAIL", f"{label}: verify_html_ai_crawl_access_and_snippet_eligibility passed"

        bad_dist = tmp_path / label / "dist"
        (bad_dist / "tools" / "bad-tool").mkdir(parents=True, exist_ok=True)
        (bad_dist / "tools" / "bad-tool" / "index.html").write_text(bad_html, encoding="utf-8")
        verifier = MasterSEOVerifier(dist_dir=bad_dist, domain="example.com", allow_mutations=False)
        assert verifier.check_snippet_gate(bad_dist)["status"] == "FAIL", f"{label}: check_snippet_gate passed"
        assert verifier.check_snippet_eligibility_gate(bad_dist)["status"] == "FAIL", f"{label}: check_snippet_eligibility_gate passed"
