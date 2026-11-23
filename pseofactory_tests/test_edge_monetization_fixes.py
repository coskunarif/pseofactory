"""Behavioral regression tests for edge monetization, secret hygiene, earnings ledger,
falsification truth, E2E SKU coverage, and email correspondence parsing.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

from pseofactory.action_bus import HumanActionBus
from pseofactory.affiliates_hub import (
    DEFAULT_PARTNERSTACK_API_KEY,
    DEFAULT_SOVRN_API_KEY,
    MonetizationHub,
)
from pseofactory.edge import generate_edge_lead_capture_function
from pseofactory.email_ingest import (
    EmailIngestionEngine,
    EmailMessage,
    _extract_bounced_recipient,
)
from pseofactory.partner_tracker import (
    PartnerTrackingEngine,
    audit_end_to_end_monetization_and_fulfillment,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# 1. [P0] Edge /api/checkout paywall bypass across all 4 tenants
# ---------------------------------------------------------------------------

CHECKOUT_PAYWALL_HARNESS = textwrap.dedent(
    r"""
    const [modPath, tenant, sku, slug] = process.argv.slice(2);
    const mod = await import(modPath);
    const kvStore = new Map();
    const kv = {
      async put(k, v) { kvStore.set(k, v); },
      async get(k, opts) {
        const v = kvStore.get(k);
        return v ? (opts && opts.type === "json" ? JSON.parse(v) : v) : null;
      },
      async list() { return { keys: [...kvStore.keys()].map((name) => ({ name })) }; },
    };
    const paidSession = {
      id: "cs_live_PAID_VERIFY_1",
      livemode: true,
      payment_status: "paid",
      amount_total: 7900,
      currency: "usd",
      client_reference_id: "lead_paywall_test",
      metadata: { lead_id: "lead_paywall_test", property_id: tenant, offer_sku: sku, tool_slug: slug },
    };
    globalThis.fetch = async (url) => {
      const u = String(url);
      if (u.includes("/v1/checkout/sessions/cs_live_PAID_VERIFY_1")) {
        return new Response(JSON.stringify(paidSession), { status: 200 });
      }
      if (u.endsWith("/v1/checkout/sessions")) {
        return new Response(
          JSON.stringify({ id: "cs_live_NEW_CHK", url: "https://checkout.stripe.com/c/pay/cs_live_NEW_CHK" }),
          { status: 200 }
        );
      }
      return new Response("{}", { status: 500 });
    };

    const env = { STRIPE_SECRET_KEY: "sk_live_mock", LEADS_KV: kv, LEADS: kv };
    const qs = `lead_id=lead_paywall_test&sku=${encodeURIComponent(sku)}&tool_slug=${encodeURIComponent(slug)}&amount=250000&state=CA`;

    const chkLiveRes = await mod.onRequestGet({
      request: new Request(`https://${tenant}.com/api/lead-capture?checkout=1&${qs}&format=json`, {
        headers: { Accept: "application/json" },
      }),
      env,
    });
    const chkLive = { status: chkLiveRes.status, body: await chkLiveRes.json() };

    const chkSynthRes = await mod.onRequestGet({
      request: new Request(`https://${tenant}.com/api/lead-capture?checkout=1&${qs}&synthetic_test=1&format=json`, {
        headers: { Accept: "application/json", "X-Pseofactory-Test": "1" },
      }),
      env,
    });
    const chkSynth = { status: chkSynthRes.status, body: await chkSynthRes.json() };

    const postLeadRes = await mod.onRequestPost({
      request: new Request(`https://${tenant}.com/api/lead-capture?synthetic_test=1`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Pseofactory-Test": "1" },
        body: JSON.stringify({
          email: "buyer@acme-corp.example",
          tool_slug: slug,
          sku,
          calculated_amount: 250000,
          state: "CA",
          synthetic_test: true,
        }),
      }),
      env,
    });
    const postLead = { status: postLeadRes.status, body: await postLeadRes.json() };

    const fulfillPaidRes = await mod.onRequestGet({
      request: new Request(`https://${tenant}.com/api/lead-capture?fulfill=1&${qs}&session_id=cs_live_PAID_VERIFY_1&format=json`, {
        headers: { Accept: "application/json" },
      }),
      env,
    });
    const fulfillPaid = { status: fulfillPaidRes.status, body: await fulfillPaidRes.json() };

    console.log(JSON.stringify({ chkLive, chkSynth, postLead, fulfillPaid }));
    """
)


@pytest.mark.skipif(shutil.which("node") is None, reason="node is required")
@pytest.mark.parametrize(
    ("tenant", "sku", "slug"),
    [
        ("profithelm", "ph_1031_boot_replacement_workpapers", "section-1031-calculator"),
        ("prexvo", "px_refi_amortization_decision_audit", "student-loan-refinance-break-even-calculator"),
        ("gainhelm", "gh_soc2_cmmc_audit_workpapers", "soc-2-audit-cost-calculator"),
        ("lienbond", "lb_surety_lien_wh347_packet", "davis-bacon-prevailing-wage-fringe-benefit-rate-calculator"),
    ],
)
def test_edge_unpaid_checkout_never_leaks_paid_deliverables(tmp_path: Path, tenant: str, sku: str, slug: str):
    mod_path = tmp_path / f"{tenant}_lead_capture.mjs"
    mod_path.write_text(generate_edge_lead_capture_function(tenant), encoding="utf-8")
    harness_path = tmp_path / "paywall_harness.mjs"
    harness_path.write_text(CHECKOUT_PAYWALL_HARNESS, encoding="utf-8")

    proc = subprocess.run(
        ["node", str(harness_path), str(mod_path), tenant, sku, slug],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout.strip().splitlines()[-1])

    # Unpaid checkout responses (both live session creation and synthetic/unavailable) must NOT leak
    # unredacted paid deliverables or claim datapack_delivered=true.
    for key in ("chkLive", "chkSynth"):
        body = out[key]["body"]
        serialized = json.dumps(body)
        assert "UNREDACTED_READY_FOR_FILING" not in serialized, (tenant, key)
        for forbidden_field in (
            "statutory_execution_artifacts",
            "statutory_data_pack",
            "reconciliation_schedule",
            "sensitivity_matrix",
        ):
            assert forbidden_field not in body, (tenant, key, forbidden_field)
        stl = body.get("settlement_attribution") or {}
        if stl:
            assert stl.get("datapack_delivered") is False, (tenant, key, stl)

    assert out["chkLive"]["status"] == 200
    assert str(out["chkLive"]["body"].get("checkout_url") or "").startswith("https://checkout.stripe.com/")

    # Unpaid POST lead capture must also never leak UNREDACTED_READY_FOR_FILING or claim datapack_delivered=true.
    post_body = out["postLead"]["body"]
    assert "UNREDACTED_READY_FOR_FILING" not in json.dumps(post_body), tenant
    post_stl = post_body.get("settlement_attribution") or {}
    if post_stl:
        assert post_stl.get("datapack_delivered") is False, (tenant, post_stl)

    # Verified paid fulfillment MUST still deliver the full unredacted bundle with datapack_delivered=true.
    paid_body = out["fulfillPaid"]["body"]
    assert out["fulfillPaid"]["status"] == 200, paid_body
    assert "UNREDACTED_READY_FOR_FILING" in json.dumps(paid_body), tenant
    assert len(paid_body.get("statutory_execution_artifacts") or []) >= 3
    assert isinstance(paid_body.get("statutory_data_pack"), dict)
    assert (paid_body.get("settlement_attribution") or {}).get("datapack_delivered") is True


# ---------------------------------------------------------------------------
# 2. [P0] Zero hardcoded live affiliate API keys in source or vault JSON
# ---------------------------------------------------------------------------

def test_no_hardcoded_live_affiliate_api_keys_in_repo(monkeypatch: pytest.MonkeyPatch):
    import re

    hub_src = (REPO_ROOT / "pseofactory" / "affiliates_hub.py").read_text(encoding="utf-8")
    vault_raw = (REPO_ROOT / "pseofactory" / "monetization_vault.json").read_text(encoding="utf-8")
    vault_data = json.loads(vault_raw)

    # affiliates_hub.py must NOT assign non-empty hardcoded literal defaults to secret API keys.
    assert re.search(r'^DEFAULT_SOVRN_API_KEY\s*=\s*""\s*$', hub_src, re.MULTILINE)
    assert re.search(r'^DEFAULT_PARTNERSTACK_API_KEY\s*=\s*""\s*$', hub_src, re.MULTILINE)
    assert DEFAULT_SOVRN_API_KEY == ""
    assert DEFAULT_PARTNERSTACK_API_KEY == ""

    # Vault JSON must not embed plaintext API keys.
    assert vault_data["master_networks"]["sovrn_commerce"]["api_key"] == ""
    assert vault_data["master_networks"]["partnerstack"]["api_key"] == ""

    # Without env vars set, MonetizationHub must return empty strings for secret API keys.
    monkeypatch.delenv("SOVRN_COMMERCE_API_KEY", raising=False)
    monkeypatch.delenv("PARTNERSTACK_API_KEY", raising=False)
    hub = MonetizationHub()
    assert hub.sovrn_api_key == ""
    assert hub.partnerstack_api_key == ""

    # With env vars set, MonetizationHub must read them from the environment.
    monkeypatch.setenv("SOVRN_COMMERCE_API_KEY", "env_sovrn_secret_test")
    monkeypatch.setenv("PARTNERSTACK_API_KEY", "env_ps_secret_test")
    assert hub.sovrn_api_key == "env_sovrn_secret_test"
    assert hub.partnerstack_api_key == "env_ps_secret_test"


# ---------------------------------------------------------------------------
# 3. [P1] Partner earnings ledger attribution & sticky live_api_polled fix
# ---------------------------------------------------------------------------

def test_partner_earnings_ledger_attribution_and_no_sticky_live_poll(tmp_path: Path):
    email_engine = EmailIngestionEngine(
        cache_path=tmp_path / "email_cache.json",
        state_path=tmp_path / "email_state.json",
    )
    action_bus = HumanActionBus(bus_path=tmp_path / "bus.json")
    tracker = PartnerTrackingEngine(email_engine=email_engine, action_bus=action_bus)

    # Pre-seed an older ledger claiming live_api_polled_in_current_run=True
    ledger_path = tmp_path / "partner_earnings_ledger.json"
    ledger_path.write_text(
        json.dumps(
            {
                "portals": {
                    "impact": {"live_api_polled_in_current_run": True, "last_synced_at": "2026-11-22T00:00:00Z"},
                    "cj_affiliate": {"live_api_polled_in_current_run": True, "last_synced_at": "2026-11-22T00:00:00Z"},
                }
            }
        ),
        encoding="utf-8",
    )

    ledger = tracker.sync_partner_earnings_and_balances(
        fetch_live_api=False,
        ledger_path=str(ledger_path),
    )

    # When live_network=False, no portal was polled live in the current run and sync_mode is vault_cached.
    assert ledger["sync_mode"] == "vault_cached"
    assert ledger["live_polled_portals_count"] == 0
    for pk in ("impact", "cj_affiliate", "partnerstack"):
        portal = ledger["portals"][pk]
        assert portal["live_api_polled_in_current_run"] is False
        if portal["auth_status"] == "SESSION_EXPIRED_CACHED_SNAPSHOT":
            assert portal["is_authenticated_and_syncing"] is False

    partners = ledger["partners"]
    # Active CJ partners must map to cj_affiliate, never disabled sovrn_commerce.
    for cj_key in ("efile_com", "eztaxreturn_com", "freetaxusa", "wallethub", "lawdepot"):
        assert partners[cj_key]["portal_key"] == "cj_affiliate", cj_key

    # Active Xendoo must map to firstpromoter_xendoo (not disabled sovrn_commerce).
    assert partners["xendoo"]["portal_key"] == "firstpromoter_xendoo"

    # Pending crest_capital must NOT hijack firstpromoter_xendoo or fabricate +1 click.
    assert partners["crest_capital"]["portal_key"] != "firstpromoter_xendoo"
    assert partners["crest_capital"]["portal_verified_clicks"] == 0

    # Pending partners must NOT receive hardcoded literal click counts.
    for pending_key in ("turbotax", "taxslayer", "suretybonds_direct"):
        assert partners[pending_key]["portal_verified_clicks"] == 0, pending_key


# ---------------------------------------------------------------------------
# 4. [P2] Falsification report uses dynamic truth & correct _vault schema
# ---------------------------------------------------------------------------

def test_falsification_report_computes_discrepancies_dynamically(tmp_path: Path):
    email_engine = EmailIngestionEngine(
        cache_path=tmp_path / "email_cache.json",
        state_path=tmp_path / "email_state.json",
    )
    action_bus = HumanActionBus(bus_path=tmp_path / "bus.json")
    tracker = PartnerTrackingEngine(email_engine=email_engine, action_bus=action_bus)

    out_path = tmp_path / "falsification.json"
    report = tracker.falsify_monetization_and_partner_health(
        execute_live=False,
        persist_path=str(out_path),
        repo_roots={},
    )
    part_f = report["partner_connection_falsification"]
    disc_ids = {d["discrepancy_id"] for d in part_f["discrepancies"]}

    # Resolved historical Oct 2026 false alarms must NOT be emitted when code is clean.
    assert "cj_publisher_id_split_brain" not in disc_ids
    assert "ramp_registry_status_mismatch" not in disc_ids
    assert "koinly_tracking_param_mismatch" not in disc_ids
    assert "ipx1031_unaffiliated_and_cross_redirected" not in disc_ids

    # Current real unmonetized tenant gaps (0 approved affiliate contracts on prexvo/gainhelm/lienbond)
    # MUST be dynamically detected.
    assert part_f["truly_approved_and_resolving_direct_partners_on_profithelm_count"] == 13
    assert part_f["prexvo_approved_affiliate_contracts_count"] == 0
    assert part_f["gainhelm_approved_affiliate_contracts_count"] == 0
    assert part_f["lienbond_approved_affiliate_contracts_count"] == 0
    assert "prexvo_zero_approved_affiliate_contracts" in disc_ids
    assert "gainhelm_zero_approved_affiliate_contracts" in disc_ids
    assert "lienbond_zero_approved_affiliate_contracts" in disc_ids
    assert report["are_all_claimed_partner_connections_healthy"] is False


# ---------------------------------------------------------------------------
# 5. [P2] E2E monetization audit covers LienBond and $19 SKUs
# ---------------------------------------------------------------------------

def test_e2e_monetization_audit_includes_lienbond_and_19_dollar_skus():
    report = audit_end_to_end_monetization_and_fulfillment(execute_live=False, repo_roots={})
    skus = report["catalog_skus"]

    expected_required_skus = {
        "ph_1031_boot_replacement_workpapers",
        "ph_commercial_capital_audit_toolkit",
        "ph_statutory_tax_audit_workpapers",
        "ph_instant_statutory_worksheet_19",
        "px_refi_amortization_decision_audit",
        "px_instant_repayment_worksheet_19",
        "gh_soc2_cmmc_audit_workpapers",
        "gh_hipaa_iso27001_governance_kit",
        "gh_instant_compliance_worksheet_19",
        "lb_instant_lien_bond_worksheet_19",
        "lb_surety_bond_underwriting_kit",
        "lb_workers_comp_emr_audit_packet",
        "lb_wh347_certified_payroll_packet",
        "lb_mechanics_lien_waiver_packet",
        "lb_surety_lien_wh347_packet",
    }
    missing = expected_required_skus - set(skus.keys())
    assert not missing, f"Missing SKUs from catalog_skus: {sorted(missing)}"
    for sku_id in expected_required_skus:
        assert skus[sku_id]["checkout_ready"] is True, sku_id
        assert skus[sku_id]["fulfillment_ready"] is True, sku_id
        assert skus[sku_id]["settlement_gate_enforced"] is True, sku_id


# ---------------------------------------------------------------------------
# 6. [P2] Email bounce & check-in correspondence parser accuracy
# ---------------------------------------------------------------------------

def test_email_correspondence_anomalies_filters_delays_spam_and_parses_real_smtp_and_recipient(tmp_path: Path):
    email_engine = EmailIngestionEngine(
        cache_path=tmp_path / "email_cache.json",
        state_path=tmp_path / "email_state.json",
    )

    # 1. _extract_bounced_recipient must ignore both arif.coskun@profithelm.com AND arif@profithelm.com
    raw_zoho_bounce_1076 = (
        "Date: Sun, 8 Nov 2026 01:32:02 -0800\n"
        "From: mailer-daemon@mail.zoho.com\n"
        "To: arif@profithelm.com\n"
        "Subject: Undelivered Mail Returned to Sender\n\n"
        "[2] text/plain (261 B)\n"
        "A message that you sent could not be delivered. This is a permanent error.\n\n"
        "s***@profithelm.com, ERROR CODE :550\n"
    )
    assert _extract_bounced_recipient(raw_zoho_bounce_1076, sender_email="mailer-daemon@mail.zoho.com") == "s***@profithelm.com"

    # 2. Soft Delay notice must NOT be counted as a hard bounce;
    #    421 bounce with unrelated 3-digit number (544) in MIME metadata must NOT report smtp_code="544";
    #    Spam folder messages must NOT appear in unanswered_partner_checkins.
    msgs = [
        EmailMessage(
            id="1088",
            message_id="<delay-1088@mail.zoho.com>",
            account="zoho",
            mailbox="Inbox",
            date="2026-11-21T07:12:58-08:00",
            subject="Mail Delivery Status Notification (Delay)",
            sender_name="",
            sender_email="mailer-daemon@mail.zoho.com",
            body_snippet=(
                "From: mailer-daemon@mail.zoho.com\nTo: arif.coskun@profithelm.com\n"
                "Subject: Mail Delivery Status Notification (Delay)\n"
                "[2] text/plain (521 B)\nTHIS IS A WARNING MESSAGE ONLY.\n"
                "YOU DO NOT NEED TO RESEND YOUR MESSAGE.\nkeri8403@gmail.com"
            ),
        ),
        EmailMessage(
            id="1070",
            message_id="<bounce-1070@mail.zoho.com>",
            account="zoho",
            mailbox="Inbox",
            date="2026-11-02T02:39:19-08:00",
            subject="Undelivered Mail Returned to Sender",
            sender_name="",
            sender_email="mailer-daemon@mail.zoho.com",
            body_snippet=(
                "From: mailer-daemon@mail.zoho.com\nTo: arif@profithelm.com\n"
                "Subject: Undelivered Mail Returned to Sender\n"
                "[2] text/plain (544 B)\nThis is a permanent error.\n\n"
                "ciso@gainhelm.com, ERROR CODE :421 - Temporary refusal"
            ),
        ),
        EmailMessage(
            id="1076",
            message_id="<bounce-1076@mail.zoho.com>",
            account="zoho",
            mailbox="Inbox",
            date="2026-11-08T01:32:02-08:00",
            subject="Undelivered Mail Returned to Sender",
            sender_name="",
            sender_email="mailer-daemon@mail.zoho.com",
            body_snippet=raw_zoho_bounce_1076,
        ),
        EmailMessage(
            id="spam-574",
            message_id="<spam-574@drivesocialweb.com>",
            account="zoho",
            mailbox="Spam",
            date="2026-11-17T22:07:52Z",
            subject="branded merch for Prexvo.Com",
            sender_name="Sophia Markle",
            sender_email="sophia.markle@drivesocialweb.com",
            body_snippet="Who's the right person to talk to at Prexvo.Com about branded apparel and promo items?",
        ),
    ]

    rep = email_engine.analyze_correspondence_anomalies_and_checkins(msgs, fetch_live=False)
    bounce_by_id = {b["email_id"]: b for b in rep["hard_bounces"]}

    # Delay notice excluded from hard_bounces
    assert "1088" not in bounce_by_id
    # Real bounces preserved with accurate recipient & real SMTP code
    assert "1076" in bounce_by_id
    assert bounce_by_id["1076"]["bounced_recipient"] == "s***@profithelm.com"
    assert bounce_by_id["1076"]["smtp_code"] == "550"

    assert "1070" in bounce_by_id
    assert bounce_by_id["1070"]["bounced_recipient"] == "ciso@gainhelm.com"
    assert bounce_by_id["1070"]["smtp_code"] != "544"
    assert bounce_by_id["1070"]["smtp_code"] == "421"

    # Spam folder excluded from unanswered_partner_checkins
    checkin_ids = {c["email_id"] for c in rep["unanswered_partner_checkins"]}
    assert "spam-574" not in checkin_ids
