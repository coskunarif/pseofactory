"""Registry/vault truth and intent-matched `/r/<partner>` routing across all three tenants."""

import json
from pathlib import Path

from pseofactory.affiliate_intent import (
    ACTIVE_CJ_PROPERTY_ID,
    DEAD_CJ_PROPERTY_IDS,
    GRC_PARTNER_KEYS,
    RAMP_IMPACT_URL,
    XENDOO_IMPACT_URL,
    filter_intent_matched_contracts,
    is_intent_matched,
)
from pseofactory.affiliates import GAINHELM_AFFILIATES, PREXVO_AFFILIATES, PROFITHELM_AFFILIATES
from pseofactory.affiliates_hub import MonetizationHub
from pseofactory.edge import generate_edge_redirect_function

VAULT = Path(__file__).resolve().parent.parent / "pseofactory" / "monetization_vault.json"


def test_grc_and_1031_keys_never_resolve_to_unrelated_contracts():
    for key in GRC_PARTNER_KEYS:
        assert not is_intent_matched(key, RAMP_IMPACT_URL)
        assert not is_intent_matched(key, XENDOO_IMPACT_URL)
    for key in ("ipx1031", "exeter1031", "first_american", "first_american_1031"):
        assert not is_intent_matched(key, XENDOO_IMPACT_URL)
    assert is_intent_matched("xendoo", XENDOO_IMPACT_URL)
    assert is_intent_matched("ramp", RAMP_IMPACT_URL)
    swaps = {"vanta_security": RAMP_IMPACT_URL, "ipx1031": XENDOO_IMPACT_URL, "ramp": RAMP_IMPACT_URL}
    assert filter_intent_matched_contracts(swaps) == {"ramp": RAMP_IMPACT_URL}


def test_hub_exposes_no_grc_or_1031_swaps():
    hub = MonetizationHub()
    assert hub.get_direct_contract_upgrades("gainhelm") == {}
    ph = hub.get_direct_contract_upgrades("profithelm")
    assert "ipx1031" not in ph and "exeter1031" not in ph
    assert ph["ramp"] == RAMP_IMPACT_URL


def test_unapproved_lenders_and_grc_vendors_are_not_marked_live():
    assert {k: p.status for k, p in PREXVO_AFFILIATES.items()} == {
        "splash_financial": "pending",
        "sofi": "declined",
        "credible": "pending",
        "earnest": "declined",
        "lendkey": "pending",
    }
    assert all(p.status == "pending" for p in GAINHELM_AFFILIATES.values())
    assert PROFITHELM_AFFILIATES["ramp"].status == "live"
    assert "join.ramp.com" in PROFITHELM_AFFILIATES["ramp"].default_url
    assert "fpr=arif-4c0b88" in PROFITHELM_AFFILIATES["koinly"].default_url


def test_vault_is_reconciled_with_registry():
    vault = json.loads(VAULT.read_text(encoding="utf-8"))
    text = VAULT.read_text(encoding="utf-8")
    assert not any(pid in text for pid in DEAD_CJ_PROPERTY_IDS)
    assert ACTIVE_CJ_PROPERTY_ID in text
    assert "via=A4FABF09&utm_source=affiliate" not in text
    props = vault["properties"]
    assert props["profithelm"]["partners"]["ramp"]["status"] == "live"
    assert {v["status"] for v in props["prexvo"]["partners"].values()} == {"pending", "declined"}
    assert {v["status"] for v in props["gainhelm"]["partners"].values()} == {"pending"}


def test_generated_redirects_have_no_checkout_hijack_or_grc_swaps():
    px = generate_edge_redirect_function("prexvo")
    assert "directCheckoutUrl" not in px
    assert "yield_gated_direct_checkout_capture" not in px
    assert "px_refi_amortization_decision_audit" not in px
    gh = generate_edge_redirect_function("gainhelm")
    for grc in GRC_PARTNER_KEYS & set(GAINHELM_AFFILIATES):
        block = gh.split(f"  {grc}: {{", 1)[1].split("}", 1)[0]
        assert "directContractUrl" not in block, grc
    ph = generate_edge_redirect_function("profithelm")
    block = ph.split("  ipx1031: {", 1)[1].split("}", 1)[0]
    assert "xendoo.pxf.io" not in block


def test_prexvo_llms_manifest_sync_preserves_ymyl_refinance_disclaimer(tmp_path):
    from pseofactory.maintenance import RetroReflectionEngine

    dist = tmp_path / "dist"
    tool_dir = dist / "tools" / "student-loan-refinance-break-even-calculator"
    tool_dir.mkdir(parents=True)
    (tool_dir / "index.html").write_text(
        "<html><head><title>Refi</title>"
        '<meta name="description" content="Calculate student loan refinance APR savings.">'
        "</head><body><h1>Student Loan Refinance Break-Even Calculator</h1></body></html>",
        encoding="utf-8",
    )
    (dist / "llms.txt").write_text(
        "# Prexvo\n- [Student Loan Refinance Break-Even Calculator]"
        "(https://prexvo.com/tools/student-loan-refinance-break-even-calculator/): Old summary.\n",
        encoding="utf-8",
    )
    (dist / "llms-full.txt").write_text("# Prexvo\n", encoding="utf-8")
    (dist / "catalog.json").write_text("{}", encoding="utf-8")
    RetroReflectionEngine.sync_tenant_llms_manifests(dist, "prexvo", canonical_base="https://prexvo.com")
    assert "permanently forfeits" in (dist / "llms.txt").read_text(encoding="utf-8").lower()
    assert "permanently forfeits" in (dist / "llms-full.txt").read_text(encoding="utf-8").lower()
    assert "permanently forfeits" in (dist / "catalog.json").read_text(encoding="utf-8").lower()


def test_profithelm_state_spoke_manifest_formula_parity():
    from pseofactory.maintenance import RetroReflectionEngine

    html = (
        '<input id="tax-income" value="75000">'
        '<div id="res-total-tax">$15,155</div>'
    )
    spoke = RetroReflectionEngine._extract_spoke_manifest_from_html(
        html,
        "irs-2027-tax-brackets/alabama",
        "26 U.S.C. Section 1(j)",
        "IRS SOI",
    )
    assert spoke is not None
    assert spoke["formula"].startswith("round(1220.0 + min(max(0.0, (gross_income - sunset_standard_deduction) - 12200.0)")


def test_normalize_html_callout_injects_inline_cta_when_result_box_class_added():
    from pseofactory.affiliates import normalize_html_callout_message_match

    html = (
        '<html><head><link rel="canonical" href="https://gainhelm.com/tools/cmmc-2-0-compliance-cost-calculator/"></head>'
        '<body>'
        '<div class="calc-results-column result-box" aria-live="polite">'
        '<h3 class="calc-column-title">Deterministic Statutory &amp; Audit Outputs</h3>'
        '<div id="res-total">$45,000</div>'
        '</div>'
        '<section class="refinance-partner-section affiliates-section"><a href="/r/vanta_security">Vanta</a></section>'
        '</body></html>'
    )
    out = normalize_html_callout_message_match(html, property_id="gainhelm")
    assert 'data-cta-slot="calculator_result_inline"' in out
    assert 'class="calc-inline-cta"' in out

    ph_html = (
        '<html><head><link rel="canonical" href="https://profithelm.com/tools/section-1031-calculator/"></head>'
        '<body>'
        '<div class="card result-card result-box">'
        '<div class="card-header"><h3>Outputs</h3></div>'
        '<div id="res-total">$120,000</div>'
        '</div>'
        '<section class="affiliate-section affiliates-section" data-primary-partner="ipx1031" data-partner-roster="ipx1031" data-gsc-tier="baseline"><a href="/r/ipx1031">IPX1031</a></section>'
        '</body></html>'
    )
    ph_out = normalize_html_callout_message_match(ph_html, property_id="profithelm")
    assert 'data-cta-slot="calculator_result_inline"' in ph_out
    assert 'class="calc-inline-cta"' in ph_out


def test_sync_prexvo_affiliate_status_compat(tmp_path):
    from pseofactory import maintenance

    sync_fn = getattr(maintenance, "_sync_prexvo_affiliate_status_compat", None)
    assert callable(sync_fn)
    px_dir = tmp_path / "prexvo"
    px_dir.mkdir(parents=True)
    builder = px_dir / "builder.py"
    freshness = px_dir / "freshness.py"
    builder.write_text(
        'live_items = [x for x in c if p_info.get("status") == "live"]\nif status != "live":\n    pass\n',
        encoding="utf-8",
    )
    freshness.write_text(
        'if effective_status != "live":\n    pass\nif status == "live":\n    pass\nif getattr(p_data, "status", "") == "live":\n    pass\n',
        encoding="utf-8",
    )
    assert sync_fn(tmp_path) is True
    builder_txt = builder.read_text(encoding="utf-8")
    freshness_txt = freshness.read_text(encoding="utf-8")
    assert 'in ("live", "pending")' in builder_txt
    assert 'not in ("live", "pending")' in freshness_txt
    assert "declined" not in builder_txt
    assert "declined" not in freshness_txt


def test_profithelm_factory_pipeline_test_sync_adds_top_level_pytest_import():
    from pathlib import Path
    import inspect
    from pseofactory.maintenance import reflect_and_recompile_all_assets

    src = inspect.getsource(reflect_and_recompile_all_assets)
    assert 'not ph_fp_src.startswith("import pytest") and "\\nimport pytest" not in ph_fp_src' in src





