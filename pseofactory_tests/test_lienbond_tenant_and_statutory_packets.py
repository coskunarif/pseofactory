"""
Tests for LienBond (lienbond.com) greenfield tenant compilation, live domain
registration availability verification, and upgraded jurisdiction-locked
statutory execution packets across all tenants.

Zero em-dashes. Zero en-dashes.
"""

from pathlib import Path

from pseofactory.affiliates import (
    LIENBOND_AFFILIATES,
    LIENBOND_MONETIZED_CALCULATOR_SLUGS,
    bind_asset_partner_roster,
    get_affiliate_route,
    get_affiliates_for_property,
)
from pseofactory.compiler import (
    compile_high_effort_page,
    compile_lienbond_estate,
    get_lienbond_expansion_specs,
)
from pseofactory.contracts import assert_no_forbidden_dashes
from pseofactory.edge import (
    generate_edge_lead_capture_function,
    generate_edge_redirect_function,
    generate_edge_telemetry_function,
)
from pseofactory.lead_classification import OWN_TENANT_DOMAINS
from pseofactory.market_intel import (
    evaluate_greenfield_tenant_candidates,
    verify_domain_registration_availability,
)
from pseofactory.partner_tracker import (
    evaluate_lead_quote_threshold,
    resolve_lead_monetization_offer,
    resolve_post_calculation_upgrade_spec,
)
from pseofactory.tenant_facts import (
    CANONICAL_TENANT_IDS,
    TenantFactStore,
    get_tenant_contract,
    resolve_canonical_property_id,
)


def test_domain_registration_availability_verification() -> None:
    """Verifies that lienbond.com is available while insurebond.com is registered."""
    avail_res = verify_domain_registration_availability("lienbond.com", probe_live=False)
    assert avail_res["domain"] == "lienbond.com"
    assert avail_res["available"] is True
    assert avail_res["status"] == "AVAILABLE"
    assert avail_res["cloudflare_wholesale_price_usd"] == 10.46

    reg_res = verify_domain_registration_availability("insurebond.com", probe_live=False)
    assert reg_res["domain"] == "insurebond.com"
    assert reg_res["available"] is False
    assert reg_res["status"] == "REGISTERED"

    candidates = evaluate_greenfield_tenant_candidates()
    surety_eval = next(c for c in candidates if c.vertical_id == "commercial_surety_insurance")
    assert surety_eval.recommended_domain == "insurebond.com"
    assert surety_eval.recommended_domain_available is False
    assert surety_eval.recommended_available_tenant_id == "lienbond"
    assert surety_eval.recommended_available_domain == "lienbond.com"
    assert "lienbond.com" in surety_eval.verified_available_domains


def test_lienbond_tenant_contract_and_affiliate_isolation() -> None:
    """Verifies LienBond tenant contract, domain classification, and affiliate roster isolation."""
    assert CANONICAL_TENANT_IDS == ["profithelm", "prexvo", "gainhelm"]
    assert "lienbond.com" in OWN_TENANT_DOMAINS
    assert resolve_canonical_property_id("lienbond") == "lienbond"
    assert resolve_canonical_property_id("https://lienbond.com/tools/contractor-license-bond-cost-calculator/") == "lienbond"

    contract = get_tenant_contract("lienbond")
    assert contract.property_id == "lienbond"
    assert contract.domain == "lienbond.com"
    assert len(contract.default_core_tools) == 10

    profile = TenantFactStore().get_profile("lienbond")
    assert profile.brand_name == "LienBond"
    assert profile.canonical_domain == "https://lienbond.com"

    affs = get_affiliates_for_property("lienbond")
    assert set(affs.keys()) == set(LIENBOND_AFFILIATES.keys())
    assert "suretybonds_direct" in affs
    assert "simply_business" in affs
    assert "levelset_lien_filing" in affs

    for slug in LIENBOND_MONETIZED_CALCULATOR_SLUGS:
        route = get_affiliate_route("lienbond", slug)
        assert route["property_id"] == "lienbond"
        assert route["partner_key"] in LIENBOND_AFFILIATES
        roster = bind_asset_partner_roster("lienbond", slug)
        assert roster["property_id"] == "lienbond"
        assert len(roster["roster_keys"]) >= 2


def test_upgraded_statutory_execution_packets_across_all_tenants() -> None:
    """Verifies that edge lead-capture functions for all 4 tenants include statutory_execution_artifacts and preview gating."""
    expected_suffixes = {
        "gainhelm": "GAINHELM",
        "prexvo": "PREXVO",
        "profithelm": "PROFITHELM",
        "lienbond": "LIENBOND",
    }
    for prop, suffix in expected_suffixes.items():
        js_code = generate_edge_lead_capture_function(prop)
        assert_no_forbidden_dashes(js_code, context=f"edge lead-capture {prop}")
        assert "statutory_execution_artifacts" in js_code
        assert "UNREDACTED_READY_FOR_FILING" in js_code
        assert "PREVIEW_REDACTED_PENDING_CHECKOUT" in js_code
        assert f'"payment_intent_data[statement_descriptor_suffix]": "{suffix}"' in js_code

    redir_js = generate_edge_redirect_function("lienbond")
    assert_no_forbidden_dashes(redir_js, context="lienbond redirect js")
    assert "lienbond.com" in redir_js

    tel_js = generate_edge_telemetry_function("lienbond")
    assert_no_forbidden_dashes(tel_js, context="lienbond telemetry js")
    assert "LIENBOND_TELEMETRY_KV" in tel_js

    offer = resolve_lead_monetization_offer("lienbond", "contractor-license-bond-cost-calculator")
    assert offer["offer_sku"] == "lb_surety_lien_wh347_packet"
    assert offer["offer_price_usd"] == 79.0

    wc_offer = resolve_lead_monetization_offer("lienbond", "workers-comp-class-code-rate-calculator")
    assert wc_offer["offer_sku"] == "lb_workers_comp_emr_audit_packet"
    assert wc_offer["offer_price_usd"] == 49.0

    thresh = evaluate_lead_quote_threshold("lienbond", "performance-payment-bond-cost-calculator", 120000.0)
    assert thresh["eligible"] is True
    assert thresh["qualifies_for_quote_intake"] is True
    assert thresh["primary_partner_key"] == "suretybonds_direct"

    upgrade_spec = resolve_post_calculation_upgrade_spec("lienbond", "mechanics-lien-filing-deadline-calculator")
    assert upgrade_spec is not None
    assert upgrade_spec["offer_sku"] == "lb_surety_lien_wh347_packet"
    assert upgrade_spec["trend_series_count"] >= 3


def test_compile_lienbond_estate_end_to_end(tmp_path: Path) -> None:
    """Compiles the full LienBond estate and verifies all 10 calculators, manifests, sitemaps, and edge functions."""
    specs = get_lienbond_expansion_specs()
    assert len(specs) == 10

    first_page = compile_high_effort_page(specs[0])
    assert first_page["tenant"] == "lienbond"
    assert first_page["verified"] is True
    assert "https://lienbond.com/tools/workers-compensation-class-code-rate-calculator-by-state/" in first_page["html"]

    estate_res = compile_lienbond_estate(tmp_path)
    assert estate_res["property_id"] == "lienbond"
    assert estate_res["compiled_count"] == 10

    for slug in LIENBOND_MONETIZED_CALCULATOR_SLUGS:
        leaf_html = tmp_path / "dist" / "tools" / slug / "index.html"
        manifest_json = tmp_path / "dist" / "manifests" / f"{slug}.json"
        assert leaf_html.is_file(), f"Missing compiled calculator {slug}"
        assert manifest_json.is_file(), f"Missing manifest {slug}"
        html_txt = leaf_html.read_text(encoding="utf-8")
        assert_no_forbidden_dashes(html_txt, context=f"lienbond {slug}")
        assert 'data-property="lienbond"' in html_txt
        assert 'data-property-id="lienbond"' in html_txt

    assert (tmp_path / ".pseofactory.json").is_file()
    assert (tmp_path / "wrangler.toml").is_file()
    assert (tmp_path / "functions" / "r" / "[partner].js").is_file()
    assert (tmp_path / "functions" / "api" / "lead-capture.js").is_file()
    assert (tmp_path / "functions" / "api" / "telemetry.js").is_file()
    assert (tmp_path / "functions" / "api" / "checkout.js").is_file()
    assert (tmp_path / "functions" / "api" / "lead-fulfillment.js").is_file()

    import json
    from pseofactory.maintenance import RetroReflectionEngine

    retro_res = RetroReflectionEngine.retrofit_estate(tmp_path / "dist", "lienbond")
    assert retro_res["status"] == "PASS"
    audit_res = RetroReflectionEngine.audit_estate(tmp_path / "dist", "lienbond")
    assert audit_res["status"] == "PASS"
    assert audit_res["stale_count"] == 0
    cat_obj = json.loads((tmp_path / "dist" / "catalog.json").read_text(encoding="utf-8"))
    assert cat_obj["property_id"] == "lienbond"
    assert cat_obj["domain"] == "lienbond.com"
