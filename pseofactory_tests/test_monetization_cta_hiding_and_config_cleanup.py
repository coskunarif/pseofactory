"""Targeted regression tests for monetization CTA hiding, vault SKU sync, and Zoho-first email dispatch."""

from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from pseofactory import affiliates as aff_mod
from pseofactory import compiler
from pseofactory import edge
from pseofactory import estate_common
from pseofactory import partner_tracker as pt
from pseofactory.visual_primitives import normalize_html_visual_primitives


VAULT_PATH = Path(__file__).resolve().parent.parent / "pseofactory" / "monetization_vault.json"


def _write_mutated_vault(tmp_path: Path, mutator: Any) -> Path:
    data = json.loads(VAULT_PATH.read_text(encoding="utf-8"))
    mutator(data)
    out = tmp_path / "monetization_vault.json"
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# 1. Hide ALL unapproved/declined partner CTAs + data-driven pending -> live flip
# ---------------------------------------------------------------------------


def test_zero_unapproved_r_ctas_across_zero_contract_tenants_and_future_tenant() -> None:
    # Compiler CTA block for GainHelm, LienBond, and Prexvo explicit refinance: 0 /r/ links, 1st-party checkout CTA
    cases = [
        ("gainhelm", "soc-2-audit-cost-calculator", "soc 2 audit cost", False, True, False),
        ("lienbond", "contractor-license-bond-cost-calculator-by-credit-score", "contractor license bond cost", False, False, True),
        ("prexvo", "student-loan-refinance-break-even-calculator", "student loan refinance break even", True, False, False),
    ]
    for prop_id, slug, query, is_px, is_gh, is_lb in cases:
        block = compiler._render_compiler_monetization_and_guardrail_html(
            slug=slug,
            query=query,
            is_prexvo=is_px,
            candidate_spec={},
            is_gainhelm=is_gh,
            is_lienbond=is_lb,
        )
        combined = f"{block['html']}\n{block['inline_calc_cta_html']}\n{block['comparison_table_cta_html']}"
        assert "/r/" not in combined, f"Unapproved /r/ link leaked in compiler block for {prop_id}"
        assert 'data-first-party-checkout="true"' in block["html"]
        assert "/api/lead-capture?checkout=1" in block["html"]
        assert 'id="partner-registration-drawer"' in block["html"]
        if is_px:
            low_b = block["html"].lower()
            assert "permanently eliminates" in low_b
            assert "pslf" in low_b and "income-driven" in low_b

    # Prexvo restricted public-service YMYL page: 0 /r/ links AND 0 commercial checkout CTAs
    pslf_block = compiler._render_compiler_monetization_and_guardrail_html(
        slug="pslf-qualifying-payment-simulator",
        query="pslf qualifying payment calculator",
        candidate_spec={},
        is_prexvo=True,
    )
    assert "/r/" not in pslf_block["html"]
    assert "/api/lead-capture?checkout=1" not in pslf_block["html"]
    assert 'data-restricted-public-service="true"' in pslf_block["html"]

    # ProfitHelm keeps live partners (xendoo/mercury/ramp/etc.) and strips pending/declined ones
    ph_mixed_html = (
        '<html><head><link rel="canonical" href="https://profithelm.com/tools/section-179-calculator/"></head>'
        "<body><main>"
        '<section class="affiliates-section">'
        '<div class="partner-card"><a href="/r/xendoo">Xendoo</a></div>'
        '<div class="partner-card"><a href="/r/next_insurance_b2b">Next Insurance</a></div>'
        '<div class="partner-card"><a href="/r/suretybonds_direct">SuretyBondsDirect</a></div>'
        "</section></main></body></html>"
    )
    ph_norm = aff_mod.normalize_html_callout_message_match(ph_mixed_html, property_id="profithelm")
    assert "/r/xendoo" in ph_norm
    assert "/r/next_insurance_b2b" not in ph_norm
    assert "/r/suretybonds_direct" not in ph_norm

    # Future 50+ site tenant not in hardcoded lists: fail-closed hides unapproved /r/ links dynamically
    future_html = (
        '<html><head><link rel="canonical" href="https://acme-fin.example/tools/margin-calc/"></head>'
        "<body><main>"
        '<section class="affiliates-section"><div class="partner-card">'
        '<a href="/r/acme_pending_vendor">Acme Pending</a></div></section>'
        "</main></body></html>"
    )
    future_clean = aff_mod.strip_unapproved_partner_ctas_from_html(
        future_html,
        property_id="acme_fin",
        slug="margin-calc",
    )
    assert "/r/acme_pending_vendor" not in future_clean
    assert "/api/lead-capture?checkout=1" in future_clean

    # visual_primitives fallback CTA must NOT inject unapproved /r/ link on zero-contract tenants
    vp_in = (
        '<!doctype html><html><head><link rel="canonical" href="https://gainhelm.com/tools/soc-2-audit-cost-calculator/"></head>'
        '<body><main><div id="partner-quote-intake-step" data-property="gainhelm" data-partner-key="vanta_security" '
        'data-partner-name="Vanta" data-tool-slug="soc-2-audit-cost-calculator"></div></main></body></html>'
    )
    vp_out, _ = normalize_html_visual_primitives(vp_in)
    assert "/r/vanta_security" not in vp_out


def test_partner_flip_pending_to_live_auto_renders_r_cta_across_engine(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Flip vanta_security (gainhelm), splash_financial (prexvo), simply_business (lienbond),
    # and add a live partner on a dynamic future tenant ("future50")
    def _promote(v: Dict[str, Any]) -> None:
        v["properties"]["gainhelm"]["partners"]["vanta_security"]["status"] = "live"
        v["properties"]["prexvo"]["partners"]["splash_financial"]["status"] = "live"
        v["properties"]["lienbond"]["partners"]["simply_business"]["status"] = "live"
        v["properties"]["future50"] = {
            "name": "Future50",
            "property_id": "future50",
            "partners": {
                "approved_vendor": {"status": "live"},
                "pending_vendor": {"status": "pending"},
            },
        }

    tmp_vault = _write_mutated_vault(tmp_path, _promote)
    monkeypatch.setattr(aff_mod, "MONETIZATION_VAULT_PATH", tmp_vault)

    # 1. GainHelm compiler + estate_common auto-render /r/vanta_security while drata_compliance stays hidden
    gh_block = compiler._render_compiler_monetization_and_guardrail_html(
        slug="soc-2-audit-cost-calculator",
        query="soc 2 audit cost",
        is_prexvo=False,
        candidate_spec={},
        is_gainhelm=True,
    )
    assert "/r/vanta_security" in gh_block["html"]
    assert "/r/drata_compliance" not in gh_block["html"]

    gh_matrix = estate_common.build_partners_matrix_section(
        affiliates=aff_mod.GAINHELM_AFFILIATES,
        section_title="GRC Partners",
        section_desc_with_cards="Live",
        section_desc_empty="Empty",
        slug="soc-2-audit-cost-calculator",
    )
    assert "/r/vanta_security" in gh_matrix
    assert "/r/drata_compliance" not in gh_matrix

    # 2. Prexvo compiler auto-renders /r/splash_financial while pending credible & declined sofi stay hidden
    px_block = compiler._render_compiler_monetization_and_guardrail_html(
        slug="student-loan-refinance-break-even-calculator",
        query="student loan refinance break even",
        is_prexvo=True,
        candidate_spec={},
    )
    assert "/r/splash_financial" in px_block["html"]
    assert "/r/credible" not in px_block["html"]
    assert "/r/sofi" not in px_block["html"]

    # 3. LienBond compiler auto-renders /r/simply_business while pending suretybonds_direct stays hidden
    lb_block = compiler._render_compiler_monetization_and_guardrail_html(
        slug="workers-compensation-class-code-rate-calculator-by-state",
        query="workers comp class code calculator",
        is_prexvo=False,
        candidate_spec={},
        is_lienbond=True,
    )
    assert "/r/simply_business" in lb_block["html"]
    assert "/r/suretybonds_direct" not in lb_block["html"]
    assert "/r/next_insurance_b2b" not in lb_block["html"]

    # 4. Future 50+ tenant dynamically keeps approved_vendor and strips pending_vendor
    f50_html = (
        '<html><body><section class="affiliates-section">'
        '<div class="partner-card"><a href="/r/approved_vendor">Approved</a></div>'
        '<div class="partner-card"><a href="/r/pending_vendor">Pending</a></div>'
        "</section></body></html>"
    )
    f50_out = aff_mod.strip_unapproved_partner_ctas_from_html(f50_html, property_id="future50", slug="calc")
    assert "/r/approved_vendor" in f50_out
    assert "/r/pending_vendor" not in f50_out


def test_edge_redirect_fail_closed_routes_remain_intact_while_html_hides_unapproved() -> None:
    for prop_id, expected_route in (
        ("prexvo", "splash_financial"),
        ("gainhelm", "vanta_security"),
        ("lienbond", "simply_business"),
    ):
        edge_js = edge.generate_edge_redirect_function(property_id=prop_id)
        assert expected_route in edge_js
        assert "blocked_unapproved_partner" in edge_js


# ---------------------------------------------------------------------------
# 2 & 3. Vault SKU sync (20 SKUs), hub.vault_data fix, dynamic readiness, Sovrn/PartnerStack status
# ---------------------------------------------------------------------------


def test_vault_has_all_20_stripe_skus_and_updated_network_statuses() -> None:
    vault = json.loads(VAULT_PATH.read_text(encoding="utf-8"))
    digital_products = vault["master_networks"]["stripe"]["digital_products"]
    assert len(digital_products) == 20
    expected_new_skus = {
        "px_instant_repayment_worksheet_19": ("prexvo", 19.0),
        "ph_verified_partner_slot": ("profithelm", 299.0),
        "px_verified_partner_slot": ("prexvo", 299.0),
        "gh_verified_partner_slot": ("gainhelm", 299.0),
        "lb_verified_partner_slot": ("lienbond", 299.0),
    }
    for sku, (prop, price) in expected_new_skus.items():
        assert sku in digital_products
        assert digital_products[sku]["property_id"] == prop
        assert float(digital_products[sku]["price_usd"]) == price
        assert int(digital_products[sku]["price_cents"]) == int(price * 100)

    sovrn = vault["master_networks"]["sovrn_commerce"]
    assert sovrn["account_status"] == "denied"
    assert sovrn["enabled"] is False
    assert "profithelm.com" in sovrn.get("eligibility_note", "").lower()

    pstack = vault["master_networks"]["partnerstack"]
    assert pstack["marketplace_status"] == "declined_reapply_2026_11_25"
    assert pstack["marketplace_application_status"] == "declined_reapply_2026_11_25"
    assert pstack["network_profile_completion_pct"] == 94


def test_diagnose_stripe_readiness_and_e2e_audit_read_all_20_skus_from_vault_data() -> None:
    diag = pt.diagnose_stripe_merchant_readiness(execute_live=False)
    assert diag["product_count"] == 20
    assert len(diag["product_skus"]) == 20
    for sku in (
        "px_instant_repayment_worksheet_19",
        "ph_verified_partner_slot",
        "px_verified_partner_slot",
        "gh_verified_partner_slot",
        "lb_verified_partner_slot",
    ):
        assert sku in diag["product_skus"]

    e2e = pt.audit_end_to_end_monetization_and_fulfillment(execute_live=False, repo_roots={})
    catalog_skus = e2e["catalog_skus"]
    assert len(catalog_skus) == 20
    for sku in (
        "px_instant_repayment_worksheet_19",
        "ph_verified_partner_slot",
        "px_verified_partner_slot",
        "gh_verified_partner_slot",
        "lb_verified_partner_slot",
    ):
        assert sku in catalog_skus
        assert catalog_skus[sku]["checkout_ready"] is True
        assert catalog_skus[sku]["fulfillment_ready"] is True


# ---------------------------------------------------------------------------
# 4. dispatch_transactional_playbook Zoho-first rail priority + ZeptoMail fallback
# ---------------------------------------------------------------------------


class _FakeHTTPResp:
    def __init__(self, payload: Dict[str, Any], status: int = 200) -> None:
        self._payload = json.dumps(payload).encode("utf-8")
        self.status = status

    def __enter__(self) -> "_FakeHTTPResp":
        return self

    def __exit__(self, *exc: Any) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


def _sample_lead() -> Dict[str, Any]:
    return {
        "property_id": "profithelm",
        "email": "controller@realclient.example",
        "tool_slug": "section-179-calculator",
        "lead_id": "lead_zoho_first_test",
        "synthetic_test": False,
    }


def _full_dual_rail_creds(primary_rail: str = "") -> Dict[str, str]:
    creds = {
        "ZEPTOMAIL_TOKEN": "Zoho-enczapikey fake_zepto_tok",
        "ZEPTOMAIL_FROM_EMAIL": "arif.coskun@profithelm.com",
        "NANGO_BASE_URL": "https://api.nango.dev",
        "NANGO_CONNECTION_ID": "conn_zoho_test",
        "NANGO_INTEGRATION_ID": "zoho-mail",
        "NANGO_SECRET_KEY": "fake_nango_secret",
    }
    if primary_rail:
        creds["EMAIL_PRIMARY_RAIL"] = primary_rail
    return creds


def test_dispatch_transactional_playbook_defaults_to_zoho_first_without_touching_zeptomail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EMAIL_PRIMARY_RAIL", raising=False)
    called_urls: List[str] = []

    def _fake_urlopen(req: Any, timeout: int = 15) -> _FakeHTTPResp:
        url = req.full_url if hasattr(req, "full_url") else str(req)
        called_urls.append(url)
        if "nango.dev/connection" in url:
            return _FakeHTTPResp({"credentials": {"access_token": "zoho_tok_ok"}})
        if "mail.zoho.com/api/accounts/" in url and url.endswith("/messages"):
            return _FakeHTTPResp({"data": {"messageId": "zoho_msg_1", "mailId": "zoho_mail_1"}})
        if url == "https://mail.zoho.com/api/accounts":
            return _FakeHTTPResp({"data": [{"accountId": "acct_123"}]})
        raise AssertionError(f"Unexpected URL called: {url}")

    with (
        patch("pseofactory.partner_tracker._load_email_engine_credentials", return_value=_full_dual_rail_creds()),
        patch("urllib.request.urlopen", side_effect=_fake_urlopen),
    ):
        res = pt.dispatch_transactional_playbook(
            _sample_lead(),
            execute_live=True,
            recipient_override="controller@realclient.com",
        )

    assert res["dispatched"] is True
    assert res["primary_rail"] == "zoho"
    assert res["provider"] == "zoho_mail_oauth"
    assert res["status"] == "sent_zoho_primary"
    assert res["zoho_attempted"] is True
    assert res["zoho_failover_attempted"] is False
    assert res["zeptomail_attempted"] is False
    assert not any("zeptomail" in u for u in called_urls)


def test_dispatch_transactional_playbook_falls_back_to_zeptomail_if_zoho_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EMAIL_PRIMARY_RAIL", raising=False)
    called_urls: List[str] = []

    def _fake_urlopen(req: Any, timeout: int = 15) -> _FakeHTTPResp:
        url = req.full_url if hasattr(req, "full_url") else str(req)
        called_urls.append(url)
        if "nango.dev" in url:
            raise RuntimeError("nango_temporary_timeout")
        if "zeptomail.com" in url:
            return _FakeHTTPResp({"request_id": "zepto_fallback_ok"})
        raise AssertionError(f"Unexpected URL called: {url}")

    with (
        patch("pseofactory.partner_tracker._load_email_engine_credentials", return_value=_full_dual_rail_creds()),
        patch("urllib.request.urlopen", side_effect=_fake_urlopen),
    ):
        res = pt.dispatch_transactional_playbook(
            _sample_lead(),
            execute_live=True,
            recipient_override="controller@realclient.com",
        )

    assert res["dispatched"] is True
    assert res["provider"] == "zeptomail_v1"
    assert res["status"] == "sent_zeptomail"
    assert res["zoho_attempted"] is True
    assert res["zeptomail_attempted"] is True
    assert "nango_temporary_timeout" in str(res["zoho_error"])
    assert any("nango.dev" in u for u in called_urls)
    assert any("zeptomail.com" in u for u in called_urls)


def test_dispatch_transactional_playbook_honors_explicit_zeptomail_primary_and_fails_over_to_zoho(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EMAIL_PRIMARY_RAIL", raising=False)
    called_urls: List[str] = []

    def _fake_urlopen(req: Any, timeout: int = 15) -> _FakeHTTPResp:
        url = req.full_url if hasattr(req, "full_url") else str(req)
        called_urls.append(url)
        if "zeptomail.com" in url:
            err_body = io.BytesIO(b'{"error": {"code": "TM_4001", "details": [{"code": "SM_111"}]}}')
            raise urllib.error.HTTPError(url, 400, "Bad Request", {}, err_body)
        if "nango.dev/connection" in url:
            return _FakeHTTPResp({"credentials": {"access_token": "zoho_tok_failover"}})
        if url == "https://mail.zoho.com/api/accounts":
            return _FakeHTTPResp({"data": [{"accountId": "acct_123"}]})
        if "mail.zoho.com/api/accounts/" in url and url.endswith("/messages"):
            return _FakeHTTPResp({"data": {"messageId": "zoho_msg_fo", "mailId": "zoho_mail_fo"}})
        raise AssertionError(f"Unexpected URL called: {url}")

    with (
        patch(
            "pseofactory.partner_tracker._load_email_engine_credentials",
            return_value=_full_dual_rail_creds(primary_rail="zeptomail"),
        ),
        patch("urllib.request.urlopen", side_effect=_fake_urlopen),
    ):
        res = pt.dispatch_transactional_playbook(
            _sample_lead(),
            execute_live=True,
            recipient_override="controller@realclient.com",
        )

    assert res["dispatched"] is True
    assert res["primary_rail"] == "zeptomail"
    assert res["zeptomail_attempted"] is True
    assert res["zeptomail_error_code"] == "SM_111"
    assert res["zoho_failover_attempted"] is True
    assert res["provider"] == "zoho_mail_oauth"
    assert res["status"] == "sent_zoho_verified_failover"
    assert called_urls[0].startswith("https://api.zeptomail.com")


def test_blockers_and_nits_active_direct_skip_callout_env_override_and_synthetic_tenant(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pseofactory.contracts import detect_asset_partner_roster_and_slot_issues

    # Blocker 5: status == 'active_direct' in vault is treated as live
    def _set_active_direct(v: Dict[str, Any]) -> None:
        v["properties"]["gainhelm"]["partners"]["vanta_security"]["status"] = "active_direct"

    tmp_vault = _write_mutated_vault(tmp_path, _set_active_direct)
    assert aff_mod.is_partner_live_in_vault("gainhelm", "vanta_security", vault_path=tmp_vault) is True

    # Blocker 4: skip_callout_if_unchanged=True must NOT leave unapproved /r/ links unstripped
    raw_gh = (
        '<html><head><link rel="canonical" href="https://gainhelm.com/tools/soc-2-audit-cost-calculator/"></head>'
        '<body><section class="affiliates-section"><div class="partner-card">'
        '<a href="/r/vanta_security">Vanta</a></div></section></body></html>'
    )
    rep_out, _ = aff_mod.reposition_affiliate_placements_from_gsc_signals(
        raw_gh,
        property_id="gainhelm",
        slug="soc-2-audit-cost-calculator",
        skip_callout_if_unchanged=True,
    )
    assert "/r/vanta_security" not in rep_out

    # Blocker 6: os.environ EMAIL_PRIMARY_RAIL overrides .env default
    monkeypatch.setenv("EMAIL_PRIMARY_RAIL", "zeptomail")
    loaded_creds = pt._load_email_engine_credentials()
    assert loaded_creds.get("EMAIL_PRIMARY_RAIL") == "zeptomail"

    # Blocker 7: synthetic 5th tenant never bleeds ProfitHelm branding or ph_ SKU
    fp_html = aff_mod.build_first_party_workpaper_cta_html("acme_fin", slug="margin-calc")
    assert "ProfitHelm" not in fp_html
    assert "ph_" not in fp_html
    assert "acme_fin" in fp_html
    assert 'rel="nofollow"' in fp_html

    # Nit 3: Prexvo first-party CTA has single non-duplicated Title IV forfeiture notice
    px_fp = aff_mod.build_first_party_workpaper_cta_html("prexvo", slug="student-loan-refinance-break-even-calculator")
    assert px_fp.lower().count("permanently") == 1

    # Nit 4: absolute URL /r/ links are stripped and mixed sections clean stale data-partner / data-partner-roster
    abs_html = (
        '<html><body><section class="affiliates-section" data-partner="ipx1031" data-partner-roster="ipx1031,xendoo">'
        '<div class="partner-card"><a href="https://profithelm.com/r/ipx1031">IPX1031</a></div>'
        '<div class="partner-card"><a href="/r/xendoo">Xendoo</a></div>'
        "</section></body></html>"
    )
    cleaned_abs = aff_mod.strip_unapproved_partner_ctas_from_html(abs_html, property_id="profithelm", slug="section-179-calculator")
    assert "/r/ipx1031" not in cleaned_abs
    assert "/r/xendoo" in cleaned_abs
    assert 'data-partner="xendoo"' in cleaned_abs
    assert 'data-partner-roster="xendoo"' in cleaned_abs

    # Nit 7: unknown 5th tenant in contracts.py does NOT accept ProfitHelm partner /r/xendoo as native
    c_issues = detect_asset_partner_roster_and_slot_issues(
        '<html><body><a href="/r/xendoo?source_tool=t&subid=s&cta_slot=c" rel="noopener sponsored nofollow" target="_blank">Xendoo</a></body></html>',
        property_id="acme_fin",
        slug="margin-calc",
    )
    assert any("Cross-tenant partner bleed" in i for i in c_issues), c_issues


def test_pending_to_live_restores_stripped_placeholder_for_gainhelm_and_prexvo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Proves that once a stripped (data-partner-ctas-hidden='unapproved') page for GainHelm or Prexvo
    has a partner flip pending -> live in monetization_vault.json, reposition_affiliate_placements_from_gsc_signals
    cleanly swaps the placeholder back into the full live partner matrix <section> + .calc-inline-cta
    while preserving id= and #partner-registration-drawer (and Prexvo's Title IV statutory warning).
    """
    from bs4 import BeautifulSoup

    # --- 1. GainHelm: strip under zero-contract real vault, then flip drata_compliance -> live ---
    gh_seed = (
        '<html><head><title>SOC 2 Audit Cost Calculator | GainHelm</title>'
        '<link rel="canonical" href="https://gainhelm.com/tools/soc-2-audit-cost-calculator/"></head>'
        '<body><main>'
        '<div class="result-box"><div class="kpi-block"><span>$38,500</span></div>'
        '<div id="calc-result-quick-unlock-bar"></div></div>'
        '<section id="gainhelm-partners" class="affiliate-section affiliates-section" data-primary-partner="vanta_security">'
        '<h2>Recommended Partner Solutions</h2>'
        '<div class="partner-card" data-partner="vanta_security"><a href="/r/vanta_security">Vanta</a></div>'
        '<div id="partner-registration-drawer" class="partner-registration-drawer"><details><summary>Partner Listing</summary></details></div>'
        '</section></main></body></html>'
    )
    gh_stripped = aff_mod.strip_unapproved_partner_ctas_from_html(
        gh_seed,
        property_id="gainhelm",
        slug="soc-2-audit-cost-calculator",
    )
    assert 'data-partner-ctas-hidden="unapproved"' in gh_stripped
    assert 'id="gainhelm-partners"' in gh_stripped
    assert 'id="partner-registration-drawer"' in gh_stripped
    assert "/r/" not in gh_stripped
    assert "calc-inline-cta" not in gh_stripped

    def _flip_gh_and_px_live(v: Dict[str, Any]) -> None:
        v["properties"]["gainhelm"]["partners"]["drata_compliance"]["status"] = "live"
        v["properties"]["prexvo"]["partners"]["credible"]["status"] = "live"

    live_vault = _write_mutated_vault(tmp_path, _flip_gh_and_px_live)
    monkeypatch.setattr(aff_mod, "MONETIZATION_VAULT_PATH", live_vault)

    gh_restored, gh_meta = aff_mod.reposition_affiliate_placements_from_gsc_signals(
        gh_stripped,
        property_id="gainhelm",
        slug="soc-2-audit-cost-calculator",
    )
    gh_soup = BeautifulSoup(gh_restored, "html.parser")
    gh_sec = gh_soup.select_one("section.affiliates-section")
    assert gh_sec is not None, "GainHelm live partner <section> was not restored from placeholder"
    assert gh_sec.get("id") == "gainhelm-partners"
    assert gh_sec.get("data-primary-partner") == "drata_compliance"
    assert gh_sec.select_one("#partner-registration-drawer") is not None
    assert gh_sec.select_one("h2") is not None
    assert gh_sec.select_one("h2").get_text(" ", strip=True) == "Recommended Partner Solutions"
    assert 'data-partner-ctas-hidden="unapproved"' not in gh_restored
    gh_inline = gh_soup.select_one(".calc-inline-cta")
    assert gh_inline is not None and gh_inline.get("data-partner") == "drata_compliance"
    gh_r_links = [a.get("href", "") for a in gh_soup.select('a[href*="/r/"]')]
    assert gh_r_links and all("/r/drata_compliance" in h for h in gh_r_links)
    assert "/r/vanta_security" not in gh_restored
    assert gh_meta["after_primary_partner"] == "drata_compliance"

    gh_restored_pass2, _ = aff_mod.reposition_affiliate_placements_from_gsc_signals(
        gh_restored,
        property_id="gainhelm",
        slug="soc-2-audit-cost-calculator",
    )
    assert gh_restored_pass2 == gh_restored

    # --- 2. Prexvo: strip under zero-contract real vault, then flip credible -> live ---
    monkeypatch.setattr(aff_mod, "MONETIZATION_VAULT_PATH", Path(aff_mod.__file__).resolve().parent / "monetization_vault.json")
    px_seed = (
        '<html><head><title>Grad PLUS Borrowing Cap Calculator | Prexvo</title>'
        '<link rel="canonical" href="https://prexvo.com/tools/grad-plus-borrowing-cap-calculator/"></head>'
        '<body><main>'
        '<div class="result-box"><div class="kpi-block"><span>$42,000</span></div>'
        '<div id="calc-result-quick-unlock-bar"></div></div>'
        '<section id="prexvo-partners" class="ymyl-refinance-guardrail refinance-partner-section" data-property="prexvo">'
        '<h2>Private Student Loan Refinance Comparison</h2>'
        '<div class="partner-matrix-grid">'
        '<div class="partner-card" data-partner="splash_financial"><a href="/r/splash_financial">Splash</a></div>'
        '</div>'
        '<div id="partner-registration-drawer" class="partner-registration-drawer"><details><summary>Partner Listing</summary></details></div>'
        '</section></main></body></html>'
    )
    px_stripped = aff_mod.strip_unapproved_partner_ctas_from_html(
        px_seed,
        property_id="prexvo",
        slug="grad-plus-borrowing-cap-calculator",
    )
    assert 'data-partner-ctas-hidden="unapproved"' in px_stripped
    assert 'id="prexvo-partners"' in px_stripped
    assert 'id="partner-registration-drawer"' in px_stripped
    assert "ymyl-statutory-warning" in px_stripped
    assert "/r/" not in px_stripped
    assert "calc-inline-cta" not in px_stripped

    monkeypatch.setattr(aff_mod, "MONETIZATION_VAULT_PATH", live_vault)
    px_restored, px_meta = aff_mod.reposition_affiliate_placements_from_gsc_signals(
        px_stripped,
        property_id="prexvo",
        slug="grad-plus-borrowing-cap-calculator",
    )
    px_soup = BeautifulSoup(px_restored, "html.parser")
    px_sec = px_soup.select_one("section.refinance-partner-section")
    assert px_sec is not None, "Prexvo live partner <section> was not restored from placeholder"
    assert px_sec.get("id") == "prexvo-partners"
    assert px_sec.get("data-primary-partner") == "credible"
    assert px_sec.select_one(".partner-matrix-grid") is not None
    assert px_sec.select_one(".partner-card[data-partner='credible']") is not None
    assert px_sec.select_one("#partner-registration-drawer") is not None
    assert px_sec.select_one(".ymyl-statutory-warning") is not None
    assert 'data-partner-ctas-hidden="unapproved"' not in px_restored
    px_inline = px_soup.select_one(".calc-inline-cta")
    assert px_inline is not None and px_inline.get("data-partner") == "credible"
    px_r_links = [a.get("href", "") for a in px_soup.select('a[href*="/r/"]')]
    assert px_r_links and all("/r/credible" in h for h in px_r_links)
    assert "/r/splash_financial" not in px_restored
    assert px_meta["after_primary_partner"] == "credible"

    px_restored_pass2, _ = aff_mod.reposition_affiliate_placements_from_gsc_signals(
        px_restored,
        property_id="prexvo",
        slug="grad-plus-borrowing-cap-calculator",
    )
    assert px_restored_pass2 == px_restored


