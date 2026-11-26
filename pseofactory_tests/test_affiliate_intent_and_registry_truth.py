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
    assert PROFITHELM_AFFILIATES["koinly"].default_url == "https://koinly.io/?via=F0D55B86&utm_source=affiliate"
    assert "fpr=arif-4c0b88" not in PROFITHELM_AFFILIATES["koinly"].default_url


def test_vault_is_reconciled_with_registry():
    vault = json.loads(VAULT.read_text(encoding="utf-8"))
    text = VAULT.read_text(encoding="utf-8")
    assert not any(pid in text for pid in DEAD_CJ_PROPERTY_IDS)
    assert ACTIVE_CJ_PROPERTY_ID in text
    assert "via=A4FABF09&utm_source=affiliate" not in text
    assert "fpr=arif-4c0b88" not in text
    assert "https://koinly.io/?via=F0D55B86&utm_source=affiliate" in text
    props = vault["properties"]
    assert props["profithelm"]["partners"]["ramp"]["status"] == "live"
    assert props["profithelm"]["partners"]["koinly"]["url"] == "https://koinly.io/?via=F0D55B86&utm_source=affiliate"
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
    assert not (dist / "llms-full.txt").exists()
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


def test_normalize_html_callout_injects_inline_cta_when_result_box_class_added(tmp_path, monkeypatch):
    from pseofactory import affiliates as aff_mod
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
    # While GainHelm has 0 live partners in monetization_vault.json, unapproved /r/ CTAs are hidden
    # and replaced with the 1st-party Stripe Checkout workpaper CTA.
    out_pending = normalize_html_callout_message_match(html, property_id="gainhelm")
    assert "/r/" not in out_pending
    assert 'data-first-party-checkout="true"' in out_pending

    # Once vanta_security flips from pending -> live in monetization_vault.json, inline CTA auto-appears.
    vault_copy = json.loads(VAULT.read_text(encoding="utf-8"))
    vault_copy["properties"]["gainhelm"]["partners"]["vanta_security"]["status"] = "live"
    tmp_vault = tmp_path / "monetization_vault.json"
    tmp_vault.write_text(json.dumps(vault_copy), encoding="utf-8")
    monkeypatch.setattr(aff_mod, "MONETIZATION_VAULT_PATH", tmp_vault)
    out = normalize_html_callout_message_match(html, property_id="gainhelm")
    assert 'data-cta-slot="calculator_result_inline"' in out
    assert 'class="calc-inline-cta"' in out
    assert "/r/vanta_security" in out

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
        'live_items = [x for x in c if p_info.get("status") in ("live", "pending")]\nif status not in ("live", "pending"):\n    pass\n',
        encoding="utf-8",
    )
    freshness.write_text(
        'if effective_status not in ("live", "pending"):\n    pass\nif status in ("live", "pending"):\n    pass\nif getattr(p_data, "status", "") in ("live", "pending"):\n    pass\n',
        encoding="utf-8",
    )
    assert sync_fn(tmp_path) is True
    builder_txt = builder.read_text(encoding="utf-8")
    freshness_txt = freshness.read_text(encoding="utf-8")
    assert '== "live"' in builder_txt
    assert '!= "live"' in freshness_txt
    assert "pending" not in builder_txt
    assert "pending" not in freshness_txt
    assert "declined" not in builder_txt
    assert "declined" not in freshness_txt


def test_profithelm_factory_pipeline_test_sync_adds_top_level_pytest_import():
    from pathlib import Path
    import inspect
    from pseofactory.maintenance import reflect_and_recompile_all_assets

    src = inspect.getsource(reflect_and_recompile_all_assets)
    assert 'not ph_fp_src.startswith("import pytest") and "\\nimport pytest" not in ph_fp_src' in src


def test_koinly_live_native_via_tracking_url_across_registry_vault_hub_and_edge_runtime(tmp_path):
    import subprocess
    from urllib.parse import parse_qs, urlsplit
    import pseofactory.affiliate_intent as affiliate_intent
    from pseofactory.action_bus import HumanActionBus
    from pseofactory.affiliates_hub import AUTHORITATIVE_EDGE_REDIRECT_URLS
    from pseofactory.email_ingest import EmailIngestionEngine, EmailMessage
    from pseofactory.partner_tracker import PartnerTrackingEngine

    expected_url = "https://koinly.io/?via=F0D55B86&utm_source=affiliate"

    # 1. Registry, vault, hub, and compiled edge redirect source all agree on native via=F0D55B86
    assert PROFITHELM_AFFILIATES["koinly"].default_url == expected_url
    assert getattr(affiliate_intent, "KOINLY_NATIVE_AFFILIATE_URL", None) == expected_url
    assert is_intent_matched("koinly", expected_url) is True
    assert is_intent_matched("coinledger", expected_url) is False
    assert is_intent_matched("vanta_security", expected_url) is False
    vault_raw = VAULT.read_text(encoding="utf-8")
    assert "fpr=arif-4c0b88" not in vault_raw
    assert "A4FABF09" not in vault_raw
    vault = json.loads(vault_raw)
    koinly_vault = vault["properties"]["profithelm"]["partners"]["koinly"]
    assert koinly_vault["url"] == expected_url
    assert koinly_vault["direct_url"] == expected_url

    assert AUTHORITATIVE_EDGE_REDIRECT_URLS["koinly"] == expected_url
    hub = MonetizationHub()
    assert hub.get_direct_contract_upgrades("profithelm")["koinly"] == expected_url

    edge_js = generate_edge_redirect_function("profithelm", hub=hub)
    assert expected_url in edge_js
    assert "fpr=arif-4c0b88" not in edge_js
    assert "A4FABF09" not in edge_js

    # 2. Execute generated ProfitHelm functions/r/[partner].js in Node.js for human Chrome GET /r/koinly
    edge_file = tmp_path / "profithelm_r.mjs"
    edge_file.write_text(edge_js, encoding="utf-8")
    runner = tmp_path / "run_koinly_check.mjs"
    runner.write_text(
        """
import * as ph from "./profithelm_r.mjs";

const CHROME_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";

const bareRes = await ph.onRequest({
  request: new Request("https://profithelm.com/r/koinly", {
    method: "GET",
    headers: { "user-agent": CHROME_UA },
  }),
  env: {},
  params: { partner: "koinly" },
});

const taggedRes = await ph.onRequest({
  request: new Request("https://profithelm.com/r/koinly?source_tool=crypto-tax-calculator&cta_slot=card_1&utm_source=profithelm", {
    method: "GET",
    headers: { "user-agent": CHROME_UA },
  }),
  env: {},
  params: { partner: "koinly" },
});

console.log(JSON.stringify({
  bare: { status: bareRes.status, location: bareRes.headers.get("Location") },
  tagged: { status: taggedRes.status, location: taggedRes.headers.get("Location") },
}));
""",
        encoding="utf-8",
    )
    proc = subprocess.run(["node", str(runner)], cwd=str(tmp_path), capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout.strip().splitlines()[-1])

    assert out["bare"]["status"] == 302
    assert out["bare"]["location"] == expected_url

    assert out["tagged"]["status"] == 302
    tagged_qs = parse_qs(urlsplit(out["tagged"]["location"]).query)
    assert tagged_qs.get("via") == ["F0D55B86"]
    assert tagged_qs.get("utm_source") == ["affiliate"]
    assert "fpr" not in tagged_qs

    # 3. Historical FirstPromoter Newsletter #1588 email must NEVER overwrite live native via=F0D55B86
    email_engine = EmailIngestionEngine(
        cache_path=tmp_path / "email_cache.json",
        state_path=tmp_path / "email_state.json",
    )
    action_bus = HumanActionBus(bus_path=tmp_path / "bus.json")
    tracker = PartnerTrackingEngine(email_engine=email_engine, action_bus=action_bus)
    legacy_msg = EmailMessage(
        id="1588",
        message_id="<1588@firstpromoter.com>",
        account="zoho",
        mailbox="Newsletter",
        subject="Welcome to Koinly Affiliates!",
        sender_name="Koinly Affiliates",
        sender_email="promoter@firstpromoter.com",
        date="2026-10-20 19:14:05+00:00",
        body_snippet="Welcome to Koinly Affiliates! Your referral link is http://koinly.io?fpr=arif-4c0b88",
    )
    classified = email_engine.classify_partner_emails([legacy_msg])
    promo = tracker.auto_promote_approved_links(classified, persist=False)
    assert promo["promoted_count"] == 0
    assert tracker.hub.get_direct_contract_upgrades("profithelm")["koinly"] == expected_url






