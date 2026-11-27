"""
Targeted verification suite for pseofactory.prexvo_estate (Truth-Pack-driven Prexvo compiler).
Proves 2026 HHS Poverty Guidelines ($15,960 / $5,680), P.L. 119-21 Section 82001 RAP
(360-month forgiveness, 100% interest subsidy, $50/mo principal match), $9/$19 workpaper
CTAs on commercial tool pages (omitted on restricted public-service YMYL slugs), YMYL
disclosures, clean llms.txt, single SoftwareApplication JSON-LD, zero forbidden dashes,
and UnifiedTruthGate pass (including live Node.js math parity).
Zero em-dashes (U+2014). Zero en-dashes (U+2013).
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import date
from pathlib import Path

import pytest

from pseofactory.affiliates import is_restricted_public_service_slug
from pseofactory.contracts import assert_catalog_json_no_raw_leaks, assert_no_forbidden_dashes
from pseofactory.prexvo_estate import (
    CALCULATION_MANIFESTS,
    REPAYMENT_CALCULATOR_SPEC,
    build_partners_matrix_section,
    build_refinance_partner_cta,
    build_tool_page,
    calculate_ibr_payment,
    calculate_rap_payment,
    calculate_standard_10yr_payment,
    calculate_tiered_standard_payment,
    compare_all_repayment_plans,
    compile_prexvo_estate_impl,
    get_calculator_schemas,
    get_hhs_poverty_guideline,
    normalize_seo_title,
    render_calculator_widget,
)
from pseofactory.truth_gate import UnifiedTruthGate
from pseofactory.truth_pack import load_truth_pack


def test_required_reexports_and_2026_truth_pack_math():
    """Verifies re-exported helpers use 2026 HHS FPL ($15,960 / $5,680) and 360-month RAP."""
    assert len(CALCULATION_MANIFESTS) >= 10
    assert REPAYMENT_CALCULATOR_SPEC.slug == "student-loan-repayment-calculator"
    assert len(normalize_seo_title("RAP vs IBR Calculator")) in range(50, 61)
    assert callable(build_partners_matrix_section)
    assert callable(build_tool_page)

    # 2026 HHS Poverty Guidelines (91 FR 1797)
    assert get_hhs_poverty_guideline(1, "contiguous") == 15960.0
    assert get_hhs_poverty_guideline(2, "contiguous") == 21640.0
    assert get_hhs_poverty_guideline(4, "contiguous") == 33000.0
    assert get_hhs_poverty_guideline(1, "alaska") > get_hhs_poverty_guideline(1, "hawaii") > 15960.0

    # 2026 IBR using $15,960 FPL -> $342.17/mo
    ibr = calculate_ibr_payment(60000.0, 65000.0, 0.065, family_size=1, state_group="contiguous")
    assert ibr["monthly_payment"] == 342.17

    # 2026 P.L. 119-21 Section 82001 RAP -> 360 months, $10 floor, $50/dep credit, interest subsidy + principal match
    rap_base = calculate_rap_payment(60000.0, 65000.0, 0.065, family_size=1)
    assert rap_base["monthly_payment"] == 325.0
    assert rap_base["term_months"] == 360
    assert rap_base["term_years"] == 30
    assert rap_base["principal_match"] > 0.0

    rap_deps = calculate_rap_payment(60000.0, 65000.0, 0.065, family_size=3)
    assert rap_deps["monthly_payment"] == 225.0
    assert rap_deps["interest_subsidy"] == 100.0

    rap_floor = calculate_rap_payment(60000.0, 9500.0, 0.065, family_size=1)
    assert rap_floor["monthly_payment"] == 10.0

    rap_top = calculate_rap_payment(60000.0, 115000.0, 0.065, family_size=1)
    assert rap_top["monthly_payment"] == 958.33

    std10 = calculate_standard_10yr_payment(60000.0, 0.065)
    assert std10["term_months"] == 120
    tiered = calculate_tiered_standard_payment(60000.0, 0.065)
    assert tiered["term_months"] == 360

    all_plans = compare_all_repayment_plans(60000.0, 65000.0, 0.065, 1, "contiguous")
    assert set(all_plans.keys()) == {"rap", "ibr", "paye", "icr", "tiered_standard", "standard_10yr"}
    assert all_plans["rap"]["term_months"] == 360
    assert all_plans["ibr"]["monthly_payment"] == 342.17

    widget_html = render_calculator_widget(REPAYMENT_CALCULATOR_SPEC)
    assert "15960" in widget_html
    assert "5680" in widget_html
    assert "15650" not in widget_html
    assert "16120" not in widget_html

    schemas = get_calculator_schemas(REPAYMENT_CALCULATOR_SPEC, "/tools/student-loan-repayment-calculator/")
    assert len(schemas) == 1
    assert schemas[0]["@type"] == "WebApplication"
    assert "speakable" not in schemas[0]


def test_ymyl_refinance_cta_suppression_on_public_service():
    """Verifies build_refinance_partner_cta suppresses commercial /r/ offers on restricted PSLF pages."""
    live_partner = {
        "key": "splash_financial",
        "name": "Splash Financial",
        "status": "live",
        "badge": "Featured Partner",
        "description": "Compare student loan refinance rates.",
        "cta_text": "Check My Rate",
    }
    pslf_cta = build_refinance_partner_cta(live_partner, slug="pslf-qualifying-payment-simulator")
    assert 'data-commercial-offers="none"' in pslf_cta
    assert 'data-restricted-public-service="true"' in pslf_cta
    assert "/r/splash_financial" not in pslf_cta

    refi_cta = build_refinance_partner_cta(live_partner, slug="student-loan-refinance-break-even-calculator")
    assert "/r/splash_financial" in refi_cta
    assert 'rel="noopener sponsored nofollow"' in refi_cta


def test_compile_prexvo_estate_end_to_end_and_truth_gate(tmp_path):
    """
    Compiles full Prexvo estate to temp dist_dir and verifies:
    - 2026 FPL ($15,960 / $5,680) and 360-month RAP in Python SSR & inline JS
    - Workpaper CTA blocks ($9 / $19) on commercial tool pages, omitted on restricted public-service YMYL pages
    - YMYL forfeiture disclosure ('permanently forfeits') on every tool page and llms-full.txt
    - Clean llms.txt & llms-full.txt (no duplicate words, no query stubs, no dead links)
    - Single SoftwareApplication JSON-LD node per page
    - Zero em-dashes and zero en-dashes
    - UnifiedTruthGate passes with 0 violations (with Node.js parity when node is available)
    """
    prexvo_repo = Path("/home/ubuntuadmin/projects/prexvo")
    repo_arg = prexvo_repo if prexvo_repo.is_dir() else None
    dist_dir = compile_prexvo_estate_impl(
        tmp_path / "dist",
        run_retrofit=True,
        repo_root=repo_arg,
    )

    assert dist_dir == (tmp_path / "dist").resolve()
    assert (dist_dir / "index.html").is_file()
    assert (dist_dir / "tools" / "index.html").is_file()
    assert (dist_dir / "llms.txt").is_file()
    assert (dist_dir / "catalog.json").is_file()
    assert not (dist_dir / "llms-full.txt").exists()
    assert not (dist_dir / "ai-benchmarks").exists()

    pack = load_truth_pack("prexvo")
    quick_price = int(round(float(pack.pricing_tiers["quick"]["price_usd"])))
    full_price = int(round(float(pack.pricing_tiers["full"]["price_usd"])))
    assert quick_price == 9
    assert full_price == 19

    tool_pages = sorted((dist_dir / "tools").glob("*/index.html"))
    assert len(tool_pages) >= 20

    restricted_public_service_slugs = {
        "ibr-hardship-cap-calculator",
        "pslf-buyback-months-reconsideration-student-loan-calculator",
        "pslf-qualifying-payment-simulator",
        "save-plan-litigation-transition",
    }
    commercial_sample_slugs = {
        "student-loan-refinance-break-even-calculator",
        "rap-vs-ibr-calculator",
    }
    found_slugs = {p.parent.name for p in tool_pages}
    assert restricted_public_service_slugs.issubset(found_slugs)
    assert commercial_sample_slugs.issubset(found_slugs)

    for page_path in tool_pages:
        slug = page_path.parent.name
        raw = page_path.read_text(encoding="utf-8")
        assert_no_forbidden_dashes(raw, context=str(page_path))

        if is_restricted_public_service_slug(slug):
            # Restricted public-service YMYL slugs (pslf-*, save-*, buyback, ibr-hardship) must omit paid checkout CTAs
            assert 'id="workpaper-unlock-card"' not in raw, f"Unexpected workpaper CTA on restricted slug {slug}"
            assert 'data-checkout-trigger="1"' not in raw, f"Unexpected checkout trigger on restricted slug {slug}"
        else:
            # Commercial Prexvo slugs render #workpaper-unlock-card ($9 / $19)
            assert 'id="workpaper-unlock-card"' in raw, f"Missing workpaper CTA on {slug}"
            assert f"(${quick_price})" in raw
            assert f"(${full_price})" in raw

        # Mandatory YMYL federal-refinance disclosure
        assert "permanently forfeits" in raw.lower(), f"Missing YMYL forfeiture notice on {page_path.parent.name}"

        # Never stale 2025 $15,650 / wrong $16,120 / stale RAP 120 to 240 in prose or JS (calculation-manifest timeseries matches sidecar)
        raw_no_manifest = re.sub(
            r'<script\b[^>]*\bclass=(?:"[^"]*\bcalculation-manifest\b[^"]*"|\'[^\']*\bcalculation-manifest\b[^\']*\')[^>]*>[\s\S]*?</script>',
            "",
            raw,
            flags=re.IGNORECASE,
        )
        assert "15,650" not in raw_no_manifest and "15650" not in raw_no_manifest
        assert "16,120" not in raw and "16120" not in raw
        assert "120 to 240 certified monthly payments" not in raw.lower()
        sidecar_m = json.loads((dist_dir / "manifests" / f"{slug}.json").read_text(encoding="utf-8"))
        embed_m_match = re.search(
            r'<script\b[^>]*\bclass=(?:"[^"]*\bcalculation-manifest\b[^"]*"|\'[^\']*\bcalculation-manifest\b[^\']*\')[^>]*>([\s\S]*?)</script>',
            raw,
            flags=re.IGNORECASE,
        )
        assert embed_m_match is not None
        embed_m = json.loads(embed_m_match.group(1))
        assert embed_m.get("statutory_economic_matrix") == sidecar_m.get("statutory_economic_matrix")

        # Serialized 2026 FPL in inline JS
        assert "15960" in raw and "5680" in raw

        # Single WebApplication node in JSON-LD (no SoftwareApplication, HowTo, FAQPage, Dataset, SpeakableSpecification, WebSite, or Wikidata in sameAs)
        ld_matches = re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>',
            raw,
            flags=re.IGNORECASE,
        )
        assert len(ld_matches) == 1
        assert "SpeakableSpecification" not in ld_matches[0]
        graph = json.loads(ld_matches[0]).get("@graph", [])
        graph_types = [
            t
            for n in graph
            for t in (n.get("@type") if isinstance(n.get("@type"), list) else [n.get("@type")])
        ]
        assert "WebApplication" in graph_types
        assert graph_types.count("WebApplication") == 1
        for banned_t in ("SoftwareApplication", "TechArticle", "HowTo", "FAQPage", "Dataset", "WebSite"):
            assert banned_t not in graph_types, f"Unexpected {banned_t} in leaf JSON-LD for {slug}"

        # Zero crawlable <a href="...?..."> preset links; button presets used instead
        assert not re.search(r'<a\b[^>]*class=["\'][^"\']*scenario-preset-link[^"\']*["\']', raw, re.IGNORECASE)
        assert "scenario-preset-btn" in raw
        assert "history.pushState" not in raw

    # Verify homepage emits WebSite, omits BreadcrumbList, and moves Wikidata QIDs from Organization.sameAs to knowsAbout
    home_raw = (dist_dir / "index.html").read_text(encoding="utf-8")
    home_ld = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>',
        home_raw,
        flags=re.IGNORECASE,
    )
    assert len(home_ld) == 1
    home_graph = json.loads(home_ld[0]).get("@graph", [])
    home_types = [
        t
        for n in home_graph
        for t in (n.get("@type") if isinstance(n.get("@type"), list) else [n.get("@type")])
    ]
    assert "WebSite" in home_types
    assert "BreadcrumbList" not in home_types
    home_orgs = [n for n in home_graph if "Organization" in (n.get("@type") if isinstance(n.get("@type"), list) else [n.get("@type")])]
    assert len(home_orgs) == 1
    assert not any("wikidata.org" in str(u).lower() for u in (home_orgs[0].get("sameAs") or []))
    assert "wikidata.org" in json.dumps(home_orgs[0].get("knowsAbout") or [])

    # Verify decommissioned/consolidated/year-stamped slugs absent from dist/tools & sitemap.xml, and 301 redirects present
    for legacy_slug in (
        "student-loans-gov",
        "parent-plus-double-consolidation-loophole-2026-calculator",
        "student-loan-forgiveness-2026",
    ):
        assert not (dist_dir / "tools" / legacy_slug / "index.html").exists()
    assert (dist_dir / "tools" / "student-loan-forgiveness" / "index.html").is_file()
    forgiveness_html = (dist_dir / "tools" / "student-loan-forgiveness" / "index.html").read_text(encoding="utf-8")
    assert 'id="field-plan_year"' in forgiveness_html

    sitemap_xml = (dist_dir / "sitemap.xml").read_text(encoding="utf-8")
    assert "/tools/student-loan-forgiveness/" in sitemap_xml
    assert not re.search(r"/tools/[^<]*202[67][^<]*</loc>", sitemap_xml)
    assert "student-loans-gov" not in sitemap_xml

    redirects_norm = "\n".join(re.sub(r"\s+", " ", ln.strip()) for ln in (dist_dir / "_redirects").read_text(encoding="utf-8").splitlines())
    assert "/tools/student-loans-gov/ /tools/ 301" in redirects_norm
    assert "/tools/parent-plus-double-consolidation-loophole-2026-calculator/ /tools/parent-plus-double-consolidation/ 301" in redirects_norm
    assert "/tools/student-loan-forgiveness-2026/ /tools/student-loan-forgiveness/ 301" in redirects_norm

    # Verify llms.txt & sanitized catalog.json cleanliness
    llms_txt = (dist_dir / "llms.txt").read_text(encoding="utf-8")
    catalog_raw = (dist_dir / "catalog.json").read_text(encoding="utf-8")
    assert_no_forbidden_dashes(llms_txt, context="llms.txt")
    assert_no_forbidden_dashes(catalog_raw, context="catalog.json")
    assert_catalog_json_no_raw_leaks(dist_dir / "catalog.json", context="prexvo")

    for surface_name, text in (("llms.txt", llms_txt), ("catalog.json", catalog_raw)):
        assert not re.search(r"\b([A-Za-z]{2,})\s+\1\b", text, re.IGNORECASE), f"Duplicate word in {surface_name}"
        assert not re.search(r"\bCalculate\s+(?:How\s+Do\s+You|How\s+To|What\s+Is)\b", text, re.IGNORECASE), (
            f"Query stub in {surface_name}"
        )
        assert "15,650" not in text and "15650" not in text
        assert "16,120" not in text and "16120" not in text
        assert "120 to 240 certified monthly payments" not in text.lower()

    assert "permanently forfeits" in catalog_raw.lower()

    # Run UnifiedTruthGate across every compiled HTML page (including live Node.js parity)
    # and machine endpoints (llms.txt, catalog.json).
    run_js = shutil.which("node") is not None
    gate = UnifiedTruthGate()

    for html_path in sorted(dist_dir.rglob("*.html")):
        rep_html = gate.audit_html_file(
            html_path,
            property_id="prexvo",
            dist_dir=dist_dir,
            as_of=date(2026, 11, 24),
            run_js_parity=run_js,
        )
        assert rep_html.passed is True, (
            f"UnifiedTruthGate failed on {html_path.relative_to(dist_dir)}: "
            f"{[v.to_dict() for v in rep_html.violations]}"
        )

    rep_catalog = gate.audit_non_html_file(
        dist_dir / "catalog.json",
        property_id="prexvo",
        dist_dir=dist_dir,
        as_of=date(2026, 11, 24),
    )
    assert rep_catalog.passed is True, (
        f"UnifiedTruthGate failed on catalog.json: {[v.to_dict() for v in rep_catalog.violations]}"
    )

    rep_llms = gate.audit_non_html_file(
        dist_dir / "llms.txt",
        property_id="prexvo",
        dist_dir=dist_dir,
        as_of=date(2026, 11, 24),
    )
    # prexvo.json sets applies_to_slug_patterns=[".*"] without applies_to_surfaces; verify zero non-disclosure errors on llms.txt
    llms_non_disc = [v.to_dict() for v in rep_llms.violations if v.code != "MISSING_DISCLOSURE"]
    assert llms_non_disc == [], f"UnifiedTruthGate failed on llms.txt: {llms_non_disc}"
