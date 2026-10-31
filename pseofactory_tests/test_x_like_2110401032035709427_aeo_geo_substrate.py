"""
Tests for x-like:2110401032035709427 (@alexgroberman / X Article 2012725610217627648 /
Microsoft Advertising 'From discovery to influence: A guide to AEO and GEO')
multi-tenant AEO/GEO 3-plane readiness, catalog.json synchronization, JSON-LD
inLanguage/dateModified/SpeakableSpecification/ItemList/isRelatedTo parity, and
GainHelm multi-company partner roster & inline conversion slot enforcement.
Zero em-dashes. Zero en-dashes.
"""

import json
from pathlib import Path

from pseofactory.affiliates import normalize_html_callout_message_match
from pseofactory.maintenance import (
    RetroReflectionEngine,
    _needs_page_structure_geo_normalization,
    _normalize_page_structure_and_geo_parity,
)
from pseofactory.verifier import (
    X_LIKE_2110401032035709427_CAPABILITY_MATRIX,
    audit_aeo_geo_three_plane_readiness,
    evaluate_x_like_2110401032035709427_capability_matrix,
    verify_html_partner_roster_and_slot_contract,
    verify_html_structured_data,
)


def test_x_like_2110401032035709427_capability_matrix_contract() -> None:
    """
    Verifies that X_LIKE_2110401032035709427_CAPABILITY_MATRIX covers all 10 claims
    from x-like:2110401032035709427, X Article 2012725610217627648, and the Microsoft
    Advertising AEO/GEO guide with zero forbidden dashes.
    """
    rep = evaluate_x_like_2110401032035709427_capability_matrix(include_live_tenant_check=False)
    assert rep["status"] == "PASS"
    assert rep["passed"] is True
    assert rep["pointer"] == "x-like:2110401032035709427"
    assert rep["tweet_id"] == "2110401032035709427"
    assert rep["quoted_tweet_id"] == "2012895638955204897"
    assert rep["x_article_id"] == "2012725610217627648"
    assert rep["total_claims_evaluated"] == 10
    assert rep["integrated_compounding_upgrades_count"] == 5
    assert rep["already_solved_count"] == 3
    assert rep["rejected_bloat_or_hype_count"] == 2

    raw_json = json.dumps(X_LIKE_2110401032035709427_CAPABILITY_MATRIX)
    assert "\u2014" not in raw_json
    assert "\u2013" not in raw_json


def test_jsonld_aeo_geo_graph_normalization_across_three_tenants() -> None:
    """
    Verifies that _normalize_page_structure_and_geo_parity stamps inLanguage='en-US',
    datePublished, dateModified, Offer.availability='https://schema.org/InStock',
    SpeakableSpecification, isRelatedTo on calculator pages, and ItemList on root index.html.
    """
    tool_html = (
        '<!doctype html><html lang="en"><head>'
        '<title>CMMC 2.0 Compliance Cost Calculator 2026 | GainHelm</title>'
        '<meta name="description" content="Calculate DoD CMMC 2.0 Level 2 C3PAO assessment fees, NIST SP 800-171 remediation labor, and enclave costs under 32 CFR Part 170.">'
        '<link rel="canonical" href="https://gainhelm.com/tools/cmmc-2-0-compliance-cost-calculator/">'
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@graph":['
        '{"@type":"WebPage","@id":"https://gainhelm.com/tools/cmmc-2-0-compliance-cost-calculator/#webpage","name":"CMMC 2.0 Calculator","url":"https://gainhelm.com/tools/cmmc-2-0-compliance-cost-calculator/"},'
        '{"@type":"SoftwareApplication","@id":"https://gainhelm.com/tools/cmmc-2-0-compliance-cost-calculator/#app","name":"CMMC 2.0 Calculator","applicationCategory":"BusinessApplication","operatingSystem":"All","url":"https://gainhelm.com/tools/cmmc-2-0-compliance-cost-calculator/","offers":{"@type":"Offer","price":"0","priceCurrency":"USD"}}'
        ']}</script></head><body>'
        '<h1>CMMC 2.0 Compliance Cost Calculator</h1>'
        '<aside class="quick-answer"><p>Under 32 CFR Part 170, a 75-employee defense contractor incurs $132,000.00 in CMMC 2.0 Level 2 C3PAO certification costs across 110 NIST SP 800-171 controls.</p></aside>'
        '</body></html>'
    )
    assert _needs_page_structure_geo_normalization(tool_html) is True
    norm_tool, changed = _normalize_page_structure_and_geo_parity(
        tool_html,
        property_id="gainhelm",
        slug="cmmc-2-0-compliance-cost-calculator",
        topic_label="CMMC 2.0 Compliance Cost Calculator",
        canonical_url="https://gainhelm.com/tools/cmmc-2-0-compliance-cost-calculator/",
        stat_auth="32 CFR Part 170 (CMMC 2.0 Final Rule)",
        econ_ds="DoD CMMC 2.0 Regulatory Impact Analysis & BLS SOC 15-1212",
    )
    assert changed is True
    assert '"inLanguage": "en-US"' in norm_tool
    assert '"dateModified": "2026-10-31"' in norm_tool
    assert '"SpeakableSpecification"' in norm_tool
    assert '"isRelatedTo"' in norm_tool
    assert '"https://schema.org/InStock"' in norm_tool
    assert _needs_page_structure_geo_normalization(norm_tool) is False
    sd_res = verify_html_structured_data(norm_tool, rel_path="tools/cmmc-2-0-compliance-cost-calculator/index.html", require_strict=True)
    assert sd_res["status"] == "PASS", sd_res["issues"]

    root_html = (
        '<!doctype html><html lang="en"><head>'
        '<title>GainHelm Cyber Compliance & Audit Cost Calculators 2026</title>'
        '<meta name="description" content="Model enterprise SOC 2 Type II, DoD CMMC 2.0, NIST 800-171 SPRS scores, ISO 27001, and HIPAA penalty exposure with statutory calculators.">'
        '<link rel="canonical" href="https://gainhelm.com">'
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@graph":['
        '{"@type":"WebSite","@id":"https://gainhelm.com/#website","name":"GainHelm","url":"https://gainhelm.com"},'
        '{"@type":"WebPage","@id":"https://gainhelm.com/#webpage","name":"GainHelm","url":"https://gainhelm.com","isPartOf":{"@id":"https://gainhelm.com/#website"}}'
        ']}</script></head><body>'
        '<h1>Enterprise Cyber Compliance & Audit Cost Calculators</h1>'
        '</body></html>'
    )
    assert _needs_page_structure_geo_normalization(root_html) is True
    norm_root, root_changed = _normalize_page_structure_and_geo_parity(
        root_html,
        property_id="gainhelm",
        slug="index",
        topic_label="Enterprise Cyber Compliance & Audit Cost Calculators",
        canonical_url="https://gainhelm.com/",
        stat_auth="AICPA SSAE 18; 32 CFR Part 170",
        econ_ds="BLS OEWS SOC 15-1212",
    )
    assert root_changed is True
    assert '"ItemList"' in norm_root
    assert '"inLanguage": "en-US"' in norm_root
    assert '"dateModified": "2026-10-31"' in norm_root
    assert _needs_page_structure_geo_normalization(norm_root) is False


def test_gainhelm_partner_roster_and_inline_slot_normalization() -> None:
    """
    Verifies that normalize_html_callout_message_match expands GainHelm partner sections
    to 6 distinct companies and injects the above-the-fold calculator_result_inline slot
    into <div class="calc-results-column" aria-live="polite">.
    """
    raw_gainhelm = (
        '<!doctype html><html lang="en"><head>'
        '<title>SOC 2 Audit Cost Calculator 2026 | GainHelm</title>'
        '<link rel="canonical" href="https://gainhelm.com/tools/soc-2-audit-cost-calculator/">'
        '</head><body><main class="container">'
        '<h1>SOC 2 Audit Cost Calculator</h1>'
        '<aside class="quick-answer"><p>Under AICPA SSAE 18, a 75-employee enterprise incurs $78,100.40 in Year-1 SOC 2 Type II costs.</p></aside>'
        '<div class="ftc-disclosure-card">FTC Partner Compensation Disclosure: Sponsored referral links.</div>'
        '<section id="calculator-workspace-anchor" class="interactive-calculator-container">'
        '<div class="calc-grid">'
        '<div class="calc-inputs-column"><form id="gainhelm-compliance-form">'
        '<label for="calc-input-headcount">Headcount</label><input id="calc-input-headcount" type="number" value="75" />'
        '<button type="submit" class="btn-cta touch-target">Calculate</button></form></div>'
        '<div class="calc-results-column" aria-live="polite">'
        '<h3 class="calc-column-title">Deterministic Statutory &amp; Audit Outputs</h3>'
        '<div class="calc-metrics-grid"><div class="calc-metric-value" id="metric-soc2_total_cost">$78,100.40</div></div>'
        '</div></div></section>'
        '<section class="refinance-partner-section" data-mechanic="compliant_intent_monetization">'
        '<div class="partner-card"><a href="/r/vanta_security" target="_blank" rel="noopener sponsored nofollow">Vanta</a></div>'
        '</section>'
        '<table class="comparison-table"><thead><tr><th scope="col">Partner</th></tr></thead><tbody><tr><td>'
        '<a href="/r/drata_compliance?source_tool=soc-2-audit-cost-calculator&amp;subid=soc-2-audit-cost-calculator_table_1&amp;cta_slot=comparison_table_cta" target="_blank" rel="noopener sponsored nofollow" data-partner="drata_compliance" data-cta-slot="comparison_table_cta" class="touch-target">Drata</a>'
        '</td></tr></tbody></table>'
        '</main></body></html>'
    )
    norm_gh = normalize_html_callout_message_match(raw_gainhelm, property_id="gainhelm")
    res = verify_html_partner_roster_and_slot_contract(
        norm_gh,
        property_id="gainhelm",
        slug="soc-2-audit-cost-calculator",
        rel_path="tools/soc-2-audit-cost-calculator/index.html",
    )
    assert res["status"] == "PASS", res["issues"]
    assert len(res["partner_keys"]) >= 6
    assert "calculator_result_inline" in res["slots_found"]


def test_plane_2_catalog_json_and_three_plane_readiness_audit(tmp_path: Path) -> None:
    """
    Verifies that sync_tenant_llms_manifests and sync_tenant_publisher_prerequisites
    generate dist/catalog.json, enrich llms-full.txt with Query Syntax across all tenants,
    link /catalog.json in media-kit.json, and pass audit_aeo_geo_three_plane_readiness.
    """
    dist = tmp_path / "dist"
    tool_dir = dist / "tools" / "soc-2-audit-cost-calculator"
    tool_dir.mkdir(parents=True, exist_ok=True)

    raw_index = (
        '<!doctype html><html lang="en"><head>'
        '<title>GainHelm Cyber Compliance & Audit Cost Calculators 2026</title>'
        '<meta name="description" content="Model enterprise SOC 2 Type II, DoD CMMC 2.0, NIST 800-171 SPRS scores, ISO 27001, and HIPAA penalty exposure with statutory calculators.">'
        '<link rel="canonical" href="https://gainhelm.com">'
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@graph":['
        '{"@type":"WebSite","@id":"https://gainhelm.com/#website","name":"GainHelm","url":"https://gainhelm.com"},'
        '{"@type":"WebPage","@id":"https://gainhelm.com/#webpage","name":"GainHelm","url":"https://gainhelm.com","isPartOf":{"@id":"https://gainhelm.com/#website"}}'
        ']}</script></head><body><h1>GainHelm</h1></body></html>'
    )
    norm_index, _ = _normalize_page_structure_and_geo_parity(
        raw_index,
        property_id="gainhelm",
        slug="index",
        topic_label="GainHelm Cyber Compliance Calculators",
        canonical_url="https://gainhelm.com/",
        stat_auth="AICPA SSAE 18",
        econ_ds="BLS OEWS SOC 15-1212",
    )
    (dist / "index.html").write_text(norm_index, encoding="utf-8")
    (dist / "tools" / "index.html").write_text(norm_index, encoding="utf-8")

    raw_tool = (
        '<!doctype html><html lang="en"><head>'
        '<title>SOC 2 Audit Cost Calculator 2026 | GainHelm</title>'
        '<meta name="description" content="Calculate SOC 2 Type I and Type II CPA audit fees, GRC automation ROI, and internal engineering labor under AICPA SSAE 18.">'
        '<link rel="canonical" href="https://gainhelm.com/tools/soc-2-audit-cost-calculator/">'
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@graph":['
        '{"@type":"WebPage","@id":"https://gainhelm.com/tools/soc-2-audit-cost-calculator/#webpage","name":"SOC 2 Calculator","url":"https://gainhelm.com/tools/soc-2-audit-cost-calculator/"},'
        '{"@type":"SoftwareApplication","@id":"https://gainhelm.com/tools/soc-2-audit-cost-calculator/#app","name":"SOC 2 Calculator","applicationCategory":"BusinessApplication","operatingSystem":"All","url":"https://gainhelm.com/tools/soc-2-audit-cost-calculator/","offers":{"@type":"Offer","price":"0","priceCurrency":"USD"}}'
        ']}</script></head><body><main class="container">'
        '<h1>SOC 2 Audit Cost & GRC Automation Calculator</h1>'
        '<aside class="quick-answer"><p>Under AICPA SSAE 18 (AT-C Section 205), a 75-employee enterprise incurs $78,100.40 in total first-year SOC 2 Type II certification costs.</p></aside>'
        '<div class="ftc-disclosure-card">FTC Partner Compensation Disclosure: Sponsored referral links.</div>'
        '<section id="calculator-workspace-anchor" class="interactive-calculator-container">'
        '<div class="calc-grid">'
        '<div class="calc-inputs-column"><form id="gainhelm-compliance-form">'
        '<label for="calc-input-headcount">Headcount</label><input id="calc-input-headcount" type="number" value="75" />'
        '<button type="submit" class="btn-cta touch-target">Calculate</button></form></div>'
        '<div class="calc-results-column" aria-live="polite">'
        '<h3 class="calc-column-title">Deterministic Statutory &amp; Audit Outputs</h3>'
        '<div class="calc-metrics-grid"><div class="calc-metric-value" id="metric-soc2_total_cost">$78,100.40</div></div>'
        '</div></div></section>'
        '<section class="refinance-partner-section" data-mechanic="compliant_intent_monetization">'
        '<div class="partner-card"><a href="/r/vanta_security" target="_blank" rel="noopener sponsored nofollow">Vanta</a></div>'
        '</section>'
        '<table class="comparison-table"><thead><tr><th scope="col">Partner</th></tr></thead><tbody><tr><td>'
        '<a href="/r/drata_compliance?source_tool=soc-2-audit-cost-calculator&amp;subid=soc-2-audit-cost-calculator_table_1&amp;cta_slot=comparison_table_cta" target="_blank" rel="noopener sponsored nofollow" data-partner="drata_compliance" data-cta-slot="comparison_table_cta" class="touch-target">Drata</a>'
        '</td></tr></tbody></table>'
        '<script type="application/json" id="calculation-manifest" class="calculation-manifest">'
        '{"manifest_id":"soc-2-audit-cost-calculator-manifest","slug":"soc-2-audit-cost-calculator","model_name":"SOC 2 Model","statutory_authority":"AICPA SSAE 18 (AT-C Section 205)","economic_dataset":"BLS OEWS SOC 15-1212","formula":"cpa_fee + grc_cost","inputs":{"cpa_fee":37000,"grc_cost":15000},"published_output":52000.0}'
        '</script>'
        '</main></body></html>'
    )
    norm_tool = normalize_html_callout_message_match(raw_tool, property_id="gainhelm")
    norm_tool, _ = _normalize_page_structure_and_geo_parity(
        norm_tool,
        property_id="gainhelm",
        slug="soc-2-audit-cost-calculator",
        topic_label="SOC 2 Audit Cost Calculator",
        canonical_url="https://gainhelm.com/tools/soc-2-audit-cost-calculator/",
        stat_auth="AICPA SSAE 18 (AT-C Section 205)",
        econ_ds="BLS OEWS SOC 15-1212",
    )
    (tool_dir / "index.html").write_text(norm_tool, encoding="utf-8")
    (dist / "llms.txt").write_text(
        "# GainHelm\n\n> Summary.\n\n## Calculators\n\n## Documentation\n- [Methodology](https://gainhelm.com/methodology/)\n",
        encoding="utf-8",
    )
    (dist / "llms-full.txt").write_text("# GainHelm\n", encoding="utf-8")

    synced = RetroReflectionEngine.sync_tenant_llms_manifests(dist, "gainhelm", canonical_base="https://gainhelm.com")
    prereqs = RetroReflectionEngine.sync_tenant_publisher_prerequisites(dist, "gainhelm", canonical_base="https://gainhelm.com")
    assert "catalog.json" in synced
    assert "llms-full.txt" in synced
    assert "media-kit.json" in prereqs

    readiness = audit_aeo_geo_three_plane_readiness(dist_dir=dist, property_id="gainhelm")
    assert readiness["status"] == "PASS", readiness["issues"]
    assert readiness["plane_2_catalog_feeds_and_manifests"]["catalog_json_present"] is True
    assert readiness["plane_2_catalog_feeds_and_manifests"]["catalog_tools_verified"] == 1


def test_gainhelm_gsc_reposition_retains_six_company_roster_and_quick_answer_boundary(tmp_path: Path) -> None:
    """
    Verifies that:
    1. GainHelm bind_asset_partner_roster and reposition_affiliate_placements_from_gsc_signals
       preserve all 6 distinct GRC partner companies (Vanta, Drata, Sprinto, Thoropass,
       Coalition, Cobalt) even when data-gsc-tier is stamped.
    2. sync_tenant_llms_manifests extracts .quick-answer-body inside <aside class="quick-answer">
       without crossing </aside> into subsequent form/newsletter <p> tags.
    3. sync_tenant_publisher_prerequisites injects /catalog.json and /media-kit.json headers
       into dist/_headers and <link rel="tool-catalog"> into tool HTML <head>.
    """
    from pseofactory.affiliates import (
        bind_asset_partner_roster,
        reposition_affiliate_placements_from_gsc_signals,
    )

    roster = bind_asset_partner_roster(
        property_id="gainhelm",
        slug="soc-2-audit-cost-calculator",
        query="soc 2 audit cost calculator",
    )
    assert roster["distinct_companies_count"] == 6
    assert roster["distinct_companies"] == [
        "Vanta",
        "Drata",
        "Sprinto",
        "Thoropass",
        "Coalition",
        "Cobalt",
    ]

    stale_3_partner_gh = (
        '<!doctype html><html lang="en"><head>'
        '<title>SOC 2 Audit Cost Calculator 2026 | GainHelm</title>'
        '<link rel="canonical" href="https://gainhelm.com/tools/soc-2-audit-cost-calculator/">'
        '</head><body><main class="container">'
        '<h1>SOC 2 Audit Cost Calculator</h1>'
        '<aside class="quick-answer"><div class="quick-answer-title">Key Finding</div>'
        '<div class="quick-answer-body">Under AICPA SSAE 18 (AT-C Section 205), a 75-employee enterprise incurs $78,100.40 in Year-1 SOC 2 Type II certification costs across CPA audit fees and GRC automation.</div>'
        '</aside>'
        '<p>Get automated scenario PDF worksheets and statutory expiration updates directly to your inbox.</p>'
        '<div class="ftc-disclosure-card">FTC Partner Compensation Disclosure: Sponsored referral links.</div>'
        '<section id="calculator-workspace-anchor" class="interactive-calculator-container">'
        '<div class="calc-grid"><div class="calc-results-column" aria-live="polite">'
        '<h3 class="calc-column-title">Deterministic Statutory &amp; Audit Outputs</h3>'
        '</div></div></section>'
        '<section class="affiliate-section affiliates-section" data-mechanic="compliant_intent_monetization" '
        'data-partner="vanta_security" data-primary-partner="vanta_security" '
        'data-partner-roster="vanta_security,drata_compliance,thoropass_audit" '
        'data-partner-companies="Vanta,Drata,Thoropass" data-gsc-tier="BASELINE_MULTI_SLOT">'
        '<h2>Verified Partners</h2>'
        '<div class="partner-card"><a href="/r/vanta_security" target="_blank" rel="noopener sponsored nofollow">Vanta</a></div>'
        '</section></main></body></html>'
    )
    repositioned_gh, rep = reposition_affiliate_placements_from_gsc_signals(
        stale_3_partner_gh,
        property_id="gainhelm",
        slug="soc-2-audit-cost-calculator",
    )
    healed_gh = normalize_html_callout_message_match(repositioned_gh, property_id="gainhelm")
    assert rep["distinct_companies_count"] == 6
    res = verify_html_partner_roster_and_slot_contract(
        healed_gh,
        property_id="gainhelm",
        slug="soc-2-audit-cost-calculator",
        rel_path="tools/soc-2-audit-cost-calculator/index.html",
    )
    assert res["status"] == "PASS", res["issues"]
    assert len(res["partner_keys"]) == 6

    dist = tmp_path / "dist"
    t_dir = dist / "tools" / "soc-2-audit-cost-calculator"
    t_dir.mkdir(parents=True, exist_ok=True)
    (t_dir / "index.html").write_text(healed_gh, encoding="utf-8")
    (dist / "index.html").write_text("<html><head></head><body></body></html>", encoding="utf-8")
    (dist / "tools" / "index.html").write_text("<html><head></head><body></body></html>", encoding="utf-8")
    (dist / "_headers").write_text("/*\n  X-Content-Type-Options: nosniff\n", encoding="utf-8")
    (dist / "llms.txt").write_text("# GainHelm\n\n## Calculators\n", encoding="utf-8")
    (dist / "llms-full.txt").write_text("# GainHelm\n", encoding="utf-8")

    RetroReflectionEngine.sync_tenant_llms_manifests(dist, "gainhelm", canonical_base="https://gainhelm.com")
    RetroReflectionEngine.sync_tenant_publisher_prerequisites(dist, "gainhelm", canonical_base="https://gainhelm.com")

    cat_obj = json.loads((dist / "catalog.json").read_text(encoding="utf-8"))
    qa_extracted = cat_obj["tools"][0]["quick_answer"]
    assert "AICPA SSAE 18" in qa_extracted
    assert "directly to your inbox" not in qa_extracted
    assert 'rel="tool-catalog"' in (t_dir / "index.html").read_text(encoding="utf-8")
    assert "/catalog.json" in (dist / "_headers").read_text(encoding="utf-8")

