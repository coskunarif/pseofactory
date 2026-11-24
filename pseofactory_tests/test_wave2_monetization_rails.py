"""
Wave 2: Monetization Rails end-to-end verification suite.
Covers all 6 Wave 2 fixes with real Node.js ES-module and VM execution:
1. Stripe checkout.session.completed webhook handler across all 4 tenants
   (fail-closed 503, HMAC-SHA256 signature & replay 400, tenant isolation,
   cs_live_ paid check, shared KV settlement & zero-double-email idempotency,
   LienBond Zoho-to-ZeptoMail failover parity).
2. Fail-closed unapproved /r/* redirects by default across all 4 tenants +
   Python resolve_edge_partner_redirect parity + ProfitHelm live partners active.
3. Truthful monetization audits (_audit_tenant_outbound_routing_truth,
   falsify_monetization_and_partner_health, audit_end_to_end_monetization_and_fulfillment,
   visual_primitives dom_simulation verified/skipped truthfulness).
4. Zero-CLS checkout_status=unavailable and checkout_status=cancelled UX notice.
5. Canonical 22-rule lienbond/dist/_redirects generation and porcelain sync.
6. run_gsc_affiliate_placement_feedback_pass property_id validation and workspace root guard.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from pseofactory.contracts import assert_no_forbidden_dashes


ALL_TENANTS = (
    ("profithelm", "profithelm.com", "PROFITHELM_LEADS", "section-1031-calculator", "ph_1031_boot_replacement_workpapers"),
    ("prexvo", "prexvo.com", "PREXVO_LEADS", "student-loan-refinance-break-even-calculator", "px_refi_amortization_decision_audit"),
    ("gainhelm", "gainhelm.com", "GAINHELM_LEADS", "soc-2-audit-cost-calculator", "gh_soc2_cmmc_audit_workpapers"),
    ("lienbond", "lienbond.com", "LIENBOND_LEADS", "contractor-license-bond-cost-calculator-by-credit-score", "lb_surety_lien_wh347_packet"),
)


@pytest.mark.parametrize("tenant,domain,kv_binding,tool_slug,sku", ALL_TENANTS)
def test_wave2_stripe_webhook_security_settlement_and_zero_double_email(
    tmp_path: Path,
    tenant: str,
    domain: str,
    kv_binding: str,
    tool_slug: str,
    sku: str,
) -> None:
    """
    Executes generated functions/api/stripe-webhook.js, lead-capture.js, and
    lead-fulfillment.js as real Node.js ES modules across all 4 tenants.
    """
    from pseofactory.edge import (
        get_expected_edge_functions_map,
        sync_tenant_edge_redirect_function,
        verify_tenant_edge_functions_parity,
    )
    from pseofactory.estate_common import write_tenant_edge_functions
    from pseofactory.maintenance import CrossPropertyContaminationScanner

    repo = tmp_path / tenant
    (repo / "dist").mkdir(parents=True)
    write_tenant_edge_functions(repo, repo / "dist", tenant)
    sync_tenant_edge_redirect_function(repo, property_id=tenant)

    expected_map = get_expected_edge_functions_map(tenant)
    assert "functions/api/stripe-webhook.js" in expected_map
    assert (repo / "functions" / "api" / "stripe-webhook.js").is_file()
    ok_parity, parity_reasons = verify_tenant_edge_functions_parity(repo, tenant)
    assert ok_parity, f"Edge parity failed for {tenant}: {parity_reasons}"

    contam = CrossPropertyContaminationScanner().scan_directory(repo / "functions", tenant)
    assert not contam, f"Cross-property contamination in {tenant}: {contam}"

    node_script = f"""
import crypto from "node:crypto";
import * as webhook from "./functions/api/stripe-webhook.js";
import * as fulfill from "./functions/api/lead-fulfillment.js";

const kvMap = new Map();
const kv = {{
  get: async (k) => kvMap.has(k) ? kvMap.get(k) : null,
  put: async (k, v) => kvMap.set(k, String(v)),
  list: async ({{ prefix }} = {{}}) => ({{
    keys: Array.from(kvMap.keys()).filter(k => !prefix || k.startsWith(prefix)).map(name => ({{ name }}))
  }}),
}};

const emailCalls = [];
globalThis.fetch = async (url, init) => {{
  const u = String(url);
  if (u.includes("api.nango.dev/connection")) {{
    return new Response(JSON.stringify({{ credentials: {{ access_token: "zoho_tok_test" }} }}), {{ status: 200 }});
  }}
  if (u.includes("mail.zoho.com/api/accounts")) {{
    const body = JSON.parse(init.body || "{{}}");
    emailCalls.push({{ rail: "zoho", to: body.toAddress, subject: body.subject, html: body.content }});
    return new Response(JSON.stringify({{ data: {{ messageId: "zmsg_" + emailCalls.length }} }}), {{ status: 200 }});
  }}
  if (u.includes("api.stripe.com/v1/checkout/sessions/cs_live_WAVE2_PAID_1")) {{
    return new Response(JSON.stringify({{
      id: "cs_live_WAVE2_PAID_1",
      livemode: true,
      payment_status: "paid",
      amount_total: 7900,
      currency: "usd",
      client_reference_id: "lead_{tenant}_w2_001",
      customer_details: {{ email: "buyer@{tenant}-customer.io" }},
      metadata: {{
        lead_id: "lead_{tenant}_w2_001",
        property_id: "{tenant}",
        tool_slug: "{tool_slug}",
        offer_sku: "{sku}",
        calculated_amount: "250000",
        state: "CA"
      }}
    }}), {{ status: 200 }});
  }}
  return new Response("{{}}", {{ status: 404 }});
}};

const secret = "whsec_wave2_test_secret_12345";
const env = {{
  STRIPE_WEBHOOK_SECRET: secret,
  STRIPE_SECRET_KEY: "sk_live_mock_key",
  NANGO_SECRET_KEY: "nango_sec",
  NANGO_CONNECTION_ID: "nango_conn",
  ZOHO_MAIL_ACCOUNT_ID: "676891000000008002",
  {kv_binding}: kv,
}};

function signBody(rawBody, tsSec, sigSecret = secret) {{
  const h = crypto.createHmac("sha256", sigSecret).update(`${{tsSec}}.${{rawBody}}`).digest("hex");
  return `t=${{tsSec}},v1=${{h}}`;
}}

async function postWebhook(rawBody, headersObj, customEnv = env) {{
  const r = await webhook.onRequestPost({{
    request: new Request("https://{domain}/api/stripe-webhook", {{
      method: "POST",
      headers: {{ "content-type": "application/json", ...headersObj }},
      body: rawBody,
    }}),
    env: customEnv,
  }});
  return {{ status: r.status, body: await r.json() }};
}}

const nowSec = Math.floor(Date.now() / 1000);
const optRes = await webhook.onRequestOptions();
const getRes = await webhook.onRequest({{
  request: new Request("https://{domain}/api/stripe-webhook", {{ method: "GET" }}),
  env,
}});

const livePayloadObj = {{
  id: "evt_live_wave2_1",
  type: "checkout.session.completed",
  data: {{
    object: {{
      id: "cs_live_WAVE2_PAID_1",
      livemode: true,
      payment_status: "paid",
      amount_total: 7900,
      currency: "usd",
      client_reference_id: "lead_{tenant}_w2_001",
      customer_details: {{ email: "buyer@{tenant}-customer.io" }},
      metadata: {{
        lead_id: "lead_{tenant}_w2_001",
        property_id: "{tenant}",
        tool_slug: "{tool_slug}",
        offer_sku: "{sku}",
        calculated_amount: "250000",
        state: "CA"
      }}
    }}
  }}
}};
const liveRaw = JSON.stringify(livePayloadObj);

// 1. Missing STRIPE_WEBHOOK_SECRET -> 503
const res503 = await postWebhook(liveRaw, {{ "Stripe-Signature": signBody(liveRaw, nowSec) }}, {{ {kv_binding}: kv }});

// 2. Bad signature -> 400
const resBadSig = await postWebhook(liveRaw, {{ "Stripe-Signature": signBody(liveRaw, nowSec, "whsec_wrong") }});

// 3. Expired replay (>300s) -> 400
const resExpired = await postWebhook(liveRaw, {{ "Stripe-Signature": signBody(liveRaw, nowSec - 420) }});

// 4. Invalid JSON with valid sig -> 400
const badJsonRaw = "{{not-valid-json";
const resBadJson = await postWebhook(badJsonRaw, {{ "Stripe-Signature": signBody(badJsonRaw, nowSec) }});

// 5. Foreign property_id -> 200 ignored
const foreignTenant = "{tenant}" === "profithelm" ? "prexvo" : "profithelm";
const foreignRaw = JSON.stringify({{
  ...livePayloadObj,
  data: {{ object: {{ ...livePayloadObj.data.object, id: "cs_live_FOREIGN_1", metadata: {{ ...livePayloadObj.data.object.metadata, property_id: foreignTenant }} }} }}
}});
const resForeign = await postWebhook(foreignRaw, {{ "Stripe-Signature": signBody(foreignRaw, nowSec) }});

// 5b. Missing / empty metadata.property_id -> fail-closed 200 ignored (0 KV writes, 0 emails)
const kvCountBeforeMissingProp = kvMap.size;
const emailCountBeforeMissingProp = emailCalls.length;
const missingPropMeta = {{ ...livePayloadObj.data.object.metadata }};
delete missingPropMeta.property_id;
const missingPropRaw = JSON.stringify({{
  ...livePayloadObj,
  data: {{ object: {{ ...livePayloadObj.data.object, id: "cs_live_MISSING_PROP_1", metadata: missingPropMeta }} }}
}});
const resMissingProp = await postWebhook(missingPropRaw, {{ "Stripe-Signature": signBody(missingPropRaw, nowSec) }});
const emptyPropRaw = JSON.stringify({{
  ...livePayloadObj,
  data: {{ object: {{ ...livePayloadObj.data.object, id: "cs_live_EMPTY_PROP_1", metadata: {{ ...missingPropMeta, property_id: "   " }} }} }}
}});
const resEmptyProp = await postWebhook(emptyPropRaw, {{ "Stripe-Signature": signBody(emptyPropRaw, nowSec) }});
const missingPropKvDelta = kvMap.size - kvCountBeforeMissingProp;
const missingPropEmailDelta = emailCalls.length - emailCountBeforeMissingProp;

// 6. cs_test_ session -> 200 ignored
const testSessRaw = JSON.stringify({{
  ...livePayloadObj,
  data: {{ object: {{ ...livePayloadObj.data.object, id: "cs_test_12345", livemode: false }} }}
}});
const resTestSess = await postWebhook(testSessRaw, {{ "Stripe-Signature": signBody(testSessRaw, nowSec) }});

// 7. Valid signed cs_live_ -> 200 fulfilled, settles KV (hydrating without pre-checkout record), sends 1 email
const resValid1 = await postWebhook(liveRaw, {{ "Stripe-Signature": signBody(liveRaw, nowSec) }});
const settledAfterFirst = JSON.parse(kvMap.get("lead_{tenant}_w2_001") || "{{}}");
const lockAfterFirst = JSON.parse(kvMap.get("stripe_session_fulfilled:cs_live_WAVE2_PAID_1") || "{{}}");

// 8. Duplicate replay -> 200 already_fulfilled, 0 second email, settled_at preserved
const resReplay = await postWebhook(liveRaw, {{ "Stripe-Signature": signBody(liveRaw, nowSec) }});
const settledAfterReplay = JSON.parse(kvMap.get("lead_{tenant}_w2_001") || "{{}}");

// 9. Browser /api/lead-fulfillment after webhook -> 200, 0 duplicate email, settled_at preserved
const browserRes = await fulfill.onRequestGet({{
  request: new Request("https://{domain}/api/lead-fulfillment?lead_id=lead_{tenant}_w2_001&sku={sku}&tool_slug={tool_slug}&session_id=cs_live_WAVE2_PAID_1&format=json"),
  env,
}});
const browserBody = await browserRes.json();
const settledAfterBrowser = JSON.parse(kvMap.get("lead_{tenant}_w2_001") || "{{}}");

// 10. Synthetic/placeholder email -> settles without dispatching email
const synthRaw = JSON.stringify({{
  ...livePayloadObj,
  data: {{
    object: {{
      ...livePayloadObj.data.object,
      id: "cs_live_SYNTH_2",
      client_reference_id: "lead_{tenant}_w2_synth",
      customer_details: {{ email: "probe@example.invalid" }},
      metadata: {{ ...livePayloadObj.data.object.metadata, lead_id: "lead_{tenant}_w2_synth" }}
    }}
  }}
}});
const resSynth = await postWebhook(synthRaw, {{ "Stripe-Signature": signBody(synthRaw, nowSec) }});

console.log(JSON.stringify({{
  optStatus: optRes.status,
  getStatus: getRes.status,
  res503,
  resBadSig,
  resExpired,
  resBadJson,
  resForeign,
  resMissingProp,
  resEmptyProp,
  missingPropKvDelta,
  missingPropEmailDelta,
  resTestSess,
  resValid1,
  resReplay,
  browserStatus: browserRes.status,
  browserOk: browserBody.ok,
  resSynth,
  emailCalls,
  settledAfterFirst,
  settledAfterReplay,
  settledAfterBrowser,
  lockAfterFirst,
}}));
"""
    runner = repo / "test_webhook_runner.mjs"
    runner.write_text(node_script, encoding="utf-8")
    proc = subprocess.run(["node", str(runner)], cwd=str(repo), capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, f"Node webhook test failed for {tenant}: {proc.stderr}"
    out = json.loads(proc.stdout.strip().splitlines()[-1])

    assert out["optStatus"] == 204
    assert out["getStatus"] == 405
    assert out["res503"]["status"] == 503
    assert out["res503"]["body"]["error"] == "stripe_webhook_secret_unconfigured"
    assert out["resBadSig"]["status"] == 400
    assert out["resExpired"]["status"] == 400
    assert out["resBadJson"]["status"] == 400
    assert out["resForeign"]["status"] == 200 and out["resForeign"]["body"]["ignored"] is True
    assert out["resForeign"]["body"]["reason"] == "property_mismatch"
    assert out["resMissingProp"]["status"] == 200 and out["resMissingProp"]["body"]["ignored"] is True
    assert out["resMissingProp"]["body"]["reason"] == "missing_property_id"
    assert out["resEmptyProp"]["status"] == 200 and out["resEmptyProp"]["body"]["ignored"] is True
    assert out["resEmptyProp"]["body"]["reason"] == "missing_property_id"
    assert out["missingPropKvDelta"] == 0
    assert out["missingPropEmailDelta"] == 0
    assert out["resTestSess"]["status"] == 200 and out["resTestSess"]["body"]["ignored"] is True
    assert out["resTestSess"]["body"]["reason"] == "non_live_or_unpaid_session"

    assert out["resValid1"]["status"] == 200
    assert out["resValid1"]["body"]["fulfilled"] is True
    assert out["resValid1"]["body"]["email_dispatched"] is True
    assert out["settledAfterFirst"]["settlement_status"] == "settled"
    assert out["settledAfterFirst"]["stripe_payment_verified"] is True
    assert out["settledAfterFirst"]["email"] == f"buyer@{tenant}-customer.io"
    assert out["settledAfterFirst"]["paid_fulfillment_email_session_id"] == "cs_live_WAVE2_PAID_1"
    assert out["lockAfterFirst"]["session_id"] == "cs_live_WAVE2_PAID_1"

    assert out["resReplay"]["status"] == 200
    assert out["resReplay"]["body"]["already_fulfilled"] is True
    assert out["resReplay"]["body"]["email_dispatched"] is False
    assert out["settledAfterReplay"]["settled_at"] == out["settledAfterFirst"]["settled_at"]

    assert out["browserStatus"] == 200 and out["browserOk"] is True
    assert out["settledAfterBrowser"]["settled_at"] == out["settledAfterFirst"]["settled_at"]
    assert out["settledAfterBrowser"]["paid_fulfillment_email_session_id"] == "cs_live_WAVE2_PAID_1"

    assert out["resSynth"]["status"] == 200
    assert out["resSynth"]["body"]["email_dispatched"] is False

    # Strictly 1 paid-fulfillment email across initial webhook + duplicate replay + browser return + synthetic session
    assert len(out["emailCalls"]) == 1, f"Expected exactly 1 email, got {len(out['emailCalls'])}: {out['emailCalls']}"
    sent = out["emailCalls"][0]
    assert sent["to"] == f"buyer@{tenant}-customer.io"
    assert "fulfill=1" in sent["html"]
    assert f"lead_id=lead_{tenant}_w2_001" in sent["html"]
    assert "session_id=cs_live_WAVE2_PAID_1" in sent["html"]
    assert_no_forbidden_dashes(sent["html"], context=f"paid_fulfillment_email_{tenant}")


def test_wave2_paid_fulfillment_email_escapes_html_injection(tmp_path: Path) -> None:
    """
    Regression test for Medium Security #24: untrusted client_reference_id and
    metadata.tool_slug payloads containing HTML/XSS tags must be HTML-escaped in
    the paid-fulfillment email body so zero unescaped <script or <img tags appear.
    """
    from pseofactory.edge import sync_tenant_edge_redirect_function

    repo = tmp_path / "profithelm_xss"
    (repo / "functions" / "r").mkdir(parents=True)
    sync_tenant_edge_redirect_function(repo, property_id="profithelm")

    runner = repo / "test_xss_email.mjs"
    runner.write_text(
        """
import crypto from "node:crypto";
import * as webhook from "./functions/api/stripe-webhook.js";

const kvMap = new Map();
const kv = {
  get: async (k) => (kvMap.has(k) ? kvMap.get(k) : null),
  put: async (k, v) => kvMap.set(k, String(v)),
};
let capturedHtml = "";
globalThis.fetch = async (url, init) => {
  const u = String(url);
  if (u.includes("api.nango.dev/connection")) {
    return new Response(JSON.stringify({ credentials: { access_token: "zoho_tok_xss" } }), { status: 200 });
  }
  if (u.includes("mail.zoho.com/api/accounts")) {
    capturedHtml = JSON.parse(init.body || "{}").content || "";
    return new Response(JSON.stringify({ data: { messageId: "zmsg_xss_1" } }), { status: 200 });
  }
  return new Response("{}", { status: 404 });
};

const secret = "whsec_xss_test_999";
const nowSec = Math.floor(Date.now() / 1000);
const rawBody = JSON.stringify({
  id: "evt_live_xss_1",
  type: "checkout.session.completed",
  data: {
    object: {
      id: "cs_live_XSS_TEST_1",
      livemode: true,
      payment_status: "paid",
      amount_total: 4900,
      currency: "usd",
      client_reference_id: 'lead_<img src=x onerror=alert(1)>',
      customer_details: { email: "buyer@safeclient.io" },
      metadata: {
        property_id: "profithelm",
        tool_slug: "<script>alert(1)</script>",
        offer_sku: "ph_commercial_capital_audit_toolkit",
      },
    },
  },
});
const sig = crypto.createHmac("sha256", secret).update(`${nowSec}.${rawBody}`).digest("hex");
const res = await webhook.onRequestPost({
  request: new Request("https://profithelm.com/api/stripe-webhook", {
    method: "POST",
    headers: { "content-type": "application/json", "Stripe-Signature": `t=${nowSec},v1=${sig}` },
    body: rawBody,
  }),
  env: {
    STRIPE_WEBHOOK_SECRET: secret,
    NANGO_SECRET_KEY: "nango_sec",
    NANGO_CONNECTION_ID: "nango_conn",
    PROFITHELM_LEADS: kv,
  },
});
console.log(JSON.stringify({ status: res.status, body: await res.json(), capturedHtml }));
""",
        encoding="utf-8",
    )
    proc = subprocess.run(["node", str(runner)], cwd=str(repo), capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    assert out["status"] == 200
    assert out["body"]["email_dispatched"] is True
    html = out["capturedHtml"]
    assert html
    assert "<script" not in html.lower()
    assert "<img" not in html.lower()
    assert "&lt;img src=x onerror=alert(1)&gt;" in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert_no_forbidden_dashes(html, context="paid_fulfillment_email_xss")


def test_wave2_lienbond_zoho_to_zeptomail_failover_parity(tmp_path: Path) -> None:
    """Verifies LienBond lead-capture.js fails over from Zoho OAuth failure to ZeptoMail."""
    from pseofactory.edge import generate_edge_lead_capture_function

    mod_file = tmp_path / "lead-capture.mjs"
    mod_file.write_text(generate_edge_lead_capture_function("lienbond"), encoding="utf-8")
    runner = tmp_path / "test_lb_failover.mjs"
    runner.write_text(
        """
import { dispatchEdgeZeptoMailPlaybook } from "./lead-capture.mjs";

const attempted = [];
globalThis.fetch = async (url) => {
  const u = String(url);
  if (u.includes("api.nango.dev/connection")) {
    attempted.push("zoho_nango");
    return new Response("upstream_error", { status: 500 });
  }
  if (u.includes("api.zeptomail.com")) {
    attempted.push("zeptomail");
    return new Response(JSON.stringify({ request_id: "zepto_lb_ok_1" }), { status: 200 });
  }
  return new Response("{}", { status: 404 });
};

const res = await dispatchEdgeZeptoMailPlaybook(
  {
    NANGO_SECRET_KEY: "nango_sec",
    NANGO_CONNECTION_ID: "nango_conn",
    ZEPTOMAIL_TOKEN: "zepto_tok_123",
  },
  {
    lead_id: "lead_lb_failover_1",
    email: "contractor@realbuildco.com",
    tool_slug: "bid-bond-calculator",
    calculated_amount: 50000,
    state: "CA",
    redirect_url: "/r/suretybonds_direct",
    offer_title: "50-State Surety Packet",
    offer_price_usd: 79,
  },
  false
);
console.log(JSON.stringify({ attempted, res }));
""",
        encoding="utf-8",
    )
    proc = subprocess.run(["node", str(runner)], cwd=str(tmp_path), capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    assert out["attempted"] == ["zoho_nango", "zeptomail"]
    assert out["res"]["zeptomail_dispatched"] is True
    assert out["res"]["email_provider"] == "zeptomail_v1"


def test_wave2_fail_closed_unapproved_redirects_default_and_opt_in(tmp_path: Path) -> None:
    """
    Verifies fail-closed unapproved /r/* redirects by default across all 4 tenants in Node.js
    and Python resolve_edge_partner_redirect parity:
    - Pending partners hold on-site with X-Edge-Contract-Tier: blocked_unapproved_partner (never checkout!).
    - ProfitHelm live partners remain 100% active redirecting to real affiliate URLs.
    - Explicit ALLOW_UNAPPROVED_EXTERNAL_REDIRECTS=true restores native pass-through.
    - Declined partners stay declined_partner_blocked; unknown partners stay 404.
    """
    from pseofactory.edge import (
        generate_edge_redirect_function,
        resolve_canonical_partner_redirect,
    )

    for prop in ("profithelm", "prexvo", "gainhelm", "lienbond"):
        (tmp_path / f"{prop}_r.mjs").write_text(
            generate_edge_redirect_function(prop), encoding="utf-8"
        )

    runner = tmp_path / "test_redirects.mjs"
    runner.write_text(
        """
import * as ph from "./profithelm_r.mjs";
import * as px from "./prexvo_r.mjs";
import * as gh from "./gainhelm_r.mjs";
import * as lb from "./lienbond_r.mjs";

async function hit(mod, domain, partner, env = {}) {
  const res = await mod.onRequest({
    request: new Request(`https://${domain}/r/${partner}?source_tool=calc&cta_slot=card_1&synthetic_test=1`),
    env,
    params: { partner },
  });
  return {
    status: res.status,
    location: res.headers.get("Location"),
    tier: res.headers.get("X-Edge-Contract-Tier"),
  };
}

const out = {
  ph_live_xendoo: await hit(ph, "profithelm.com", "xendoo"),
  ph_live_efile: await hit(ph, "profithelm.com", "efile_com"),
  ph_live_koinly: await hit(ph, "profithelm.com", "koinly"),
  ph_pending_default: await hit(ph, "profithelm.com", "crest_capital"),
  ph_pending_optin: await hit(ph, "profithelm.com", "crest_capital", { ALLOW_UNAPPROVED_EXTERNAL_REDIRECTS: "true" }),
  ph_declined: await hit(ph, "profithelm.com", "next_insurance_b2b"),
  ph_unknown: await hit(ph, "profithelm.com", "nonexistent_partner_xyz"),
  px_pending_default: await hit(px, "prexvo.com", "splash_financial"),
  px_pending_optin: await hit(px, "prexvo.com", "splash_financial", { ALLOW_UNAPPROVED_EXTERNAL_REDIRECTS: "true" }),
  px_declined: await hit(px, "prexvo.com", "sofi"),
  gh_pending_default: await hit(gh, "gainhelm.com", "vanta_security"),
  gh_pending_optin: await hit(gh, "gainhelm.com", "vanta_security", { ALLOW_UNAPPROVED_EXTERNAL_REDIRECTS: "true" }),
  lb_pending_default: await hit(lb, "lienbond.com", "suretybonds_direct"),
  lb_pending_optin: await hit(lb, "lienbond.com", "suretybonds_direct", { ALLOW_UNAPPROVED_EXTERNAL_REDIRECTS: "true" }),
  lb_declined: await hit(lb, "lienbond.com", "next_insurance_b2b"),
  lb_unknown: await hit(lb, "lienbond.com", "nonexistent_partner_xyz"),
};
console.log(JSON.stringify(out));
""",
        encoding="utf-8",
    )
    proc = subprocess.run(["node", str(runner)], cwd=str(tmp_path), capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout.strip().splitlines()[-1])

    # Live ProfitHelm partners stay 100% active
    assert out["ph_live_xendoo"]["status"] == 302 and "xendoo.pxf.io" in out["ph_live_xendoo"]["location"]
    assert out["ph_live_efile"]["status"] == 302 and "jdoqocy.com" in out["ph_live_efile"]["location"]
    assert out["ph_live_koinly"]["status"] == 302
    assert "via=F0D55B86" in out["ph_live_koinly"]["location"]
    assert "utm_source=affiliate" in out["ph_live_koinly"]["location"]
    assert "fpr=arif-4c0b88" not in out["ph_live_koinly"]["location"]

    # Pending partners default fail-closed on-site hold (never checkout!)
    for key, expected_host in (
        ("ph_pending_default", "profithelm.com"),
        ("px_pending_default", "prexvo.com"),
        ("gh_pending_default", "gainhelm.com"),
        ("lb_pending_default", "lienbond.com"),
    ):
        assert out[key]["status"] == 302
        assert out[key]["tier"] == "blocked_unapproved_partner"
        assert expected_host in out[key]["location"]
        assert "lead-capture" not in out[key]["location"]
        assert "checkout=" not in out[key]["location"]

    # Explicit opt-in passes through to native brand URL
    assert out["ph_pending_optin"]["tier"] == "native_unmonetized_destination"
    assert "crestcapital.com" in out["ph_pending_optin"]["location"]
    assert out["px_pending_optin"]["tier"] == "unapproved_native_unmonetized"
    assert "splashfinancial.com" in out["px_pending_optin"]["location"]
    assert out["gh_pending_optin"]["tier"] == "native_unmonetized_destination"
    assert "vanta.com" in out["gh_pending_optin"]["location"]
    assert out["lb_pending_optin"]["tier"] == "native_unmonetized_destination"
    assert "suretybondsdirect.com" in out["lb_pending_optin"]["location"]

    # Declined and unknown preserved
    assert out["ph_declined"]["tier"] == "declined_partner_blocked"
    assert out["px_declined"]["tier"] == "declined_partner_blocked"
    assert out["lb_declined"]["tier"] == "declined_partner_blocked"
    assert out["ph_unknown"]["status"] == 404
    assert out["lb_unknown"]["status"] == 404

    # Python parity helper matches JS default and opt-in
    py_ph_live = resolve_canonical_partner_redirect("xendoo", property_id="profithelm")
    assert py_ph_live["contract_tier"] == "direct_contract_upgraded"
    for prop, partner in (
        ("profithelm", "crest_capital"),
        ("prexvo", "splash_financial"),
        ("gainhelm", "vanta_security"),
        ("lienbond", "suretybonds_direct"),
    ):
        py_def = resolve_canonical_partner_redirect(partner, property_id=prop, env={})
        assert py_def["contract_tier"] == "blocked_unapproved_partner"
        py_opt = resolve_canonical_partner_redirect(
            partner, property_id=prop, env={"ALLOW_UNAPPROVED_EXTERNAL_REDIRECTS": "true"}
        )
        assert py_opt["contract_tier"] in ("native_unmonetized_destination", "unapproved_native_unmonetized")


def test_wave2_truthful_monetization_audits_detect_real_leaks_and_partial_static(tmp_path: Path) -> None:
    """
    Proves hardcoded 0-leak theater is eliminated:
    1. Legacy opt-in edge redirect + pending /r/* HTML links -> real leaks > 0,
       UNAPPROVED_EXTERNAL_LEAKS_DETECTED, and e2e status == FAIL.
    2. Dead-end /r/unknown_slug link in dist HTML -> real dead_end_404_routes_count > 0
       and e2e status == FAIL.
    3. Fail-closed edge redirect + valid catalog links + execute_live=False ->
       0 leaks, ENFORCED_ZERO_UNAPPROVED_CLICKS, PARTIAL_STATIC_ONLY, and
       dom_action_simulation.verified is False.
    """
    from pseofactory.affiliates import GAINHELM_AFFILIATES
    from pseofactory.edge import generate_edge_redirect_function
    from pseofactory.partner_tracker import (
        PartnerTrackingEngine,
        _audit_tenant_outbound_routing_truth,
        audit_end_to_end_monetization_and_fulfillment,
    )

    legacy_leaking_edge = (
        'const blockUnapproved = Boolean(env && String(env.BLOCK_UNAPPROVED_EXTERNAL_REDIRECTS || "").toLowerCase() === "true");\n'
        'if (blockUnapproved) { /* blocked_unapproved_partner */ }\n'
    )
    safe_edge = generate_edge_redirect_function("gainhelm")

    gh_repo = tmp_path / "gainhelm"
    (gh_repo / "dist" / "tools" / "soc-2-audit-cost-calculator").mkdir(parents=True)
    (gh_repo / "functions" / "r").mkdir(parents=True)
    html_with_pending = (
        '<!DOCTYPE html><html><body>'
        '<a href="/r/vanta_security?source_tool=soc-2">Vanta</a>'
        '<a href="/r/drata_compliance?source_tool=soc-2">Drata</a>'
        '</body></html>'
    )
    (gh_repo / "dist" / "tools" / "soc-2-audit-cost-calculator" / "index.html").write_text(
        html_with_pending, encoding="utf-8"
    )
    (gh_repo / "functions" / "r" / "[partner].js").write_text(legacy_leaking_edge, encoding="utf-8")

    # 1. Real leak detected when edge does NOT block unapproved by default
    leak_truth = _audit_tenant_outbound_routing_truth(
        prop_id="gainhelm",
        reg_map=GAINHELM_AFFILIATES,
        repo_root=gh_repo,
    )
    assert leak_truth["blocks_unapproved_by_default"] is False
    assert leak_truth["html_pending_cta_count"] == 2
    assert leak_truth["edge_blocked_pending_cta_count"] == 0
    assert leak_truth["unapproved_external_leaks_count"] == 2
    assert leak_truth["dead_end_404_routes_count"] == 0

    engine = PartnerTrackingEngine()
    fals_leak = engine.falsify_monetization_and_partner_health(
        execute_live=False,
        repo_roots={"gainhelm": gh_repo},
        persist_path=str(tmp_path / "fals_leak.json"),
    )
    yg_leak = fals_leak["yield_gated_routing_enforcement"]
    assert yg_leak["status"] == "UNAPPROVED_EXTERNAL_LEAKS_DETECTED"
    assert yg_leak["gainhelm_unapproved_external_leaks_count"] == 2

    e2e_leak = audit_end_to_end_monetization_and_fulfillment(
        execute_live=False,
        repo_roots={"gainhelm": gh_repo},
    )
    assert e2e_leak["status"] == "FAIL"
    assert e2e_leak["total_unapproved_external_leaks_count"] == 2

    # 2. Switch to fail-closed Wave 2 edge redirect -> 0 leaks, pending CTAs accounted as edge_blocked
    (gh_repo / "functions" / "r" / "[partner].js").write_text(safe_edge, encoding="utf-8")
    safe_truth = _audit_tenant_outbound_routing_truth(
        prop_id="gainhelm",
        reg_map=GAINHELM_AFFILIATES,
        repo_root=gh_repo,
    )
    assert safe_truth["blocks_unapproved_by_default"] is True
    assert safe_truth["html_pending_cta_count"] == 2
    assert safe_truth["edge_blocked_pending_cta_count"] == 2
    assert safe_truth["unapproved_external_leaks_count"] == 0
    assert safe_truth["dead_end_404_routes_count"] == 0

    fals_clean = engine.falsify_monetization_and_partner_health(
        execute_live=False,
        repo_roots={"gainhelm": gh_repo},
        persist_path=str(tmp_path / "fals_clean.json"),
    )
    assert fals_clean["yield_gated_routing_enforcement"]["status"] == "ENFORCED_ZERO_UNAPPROVED_CLICKS"

    e2e_partial = audit_end_to_end_monetization_and_fulfillment(execute_live=False, repo_roots={})
    assert e2e_partial["status"] == "PARTIAL_STATIC_ONLY"
    assert e2e_partial["ui_ux_button_surface_audit"]["dom_action_simulation"]["skipped"] is True
    assert e2e_partial["ui_ux_button_surface_audit"]["dom_action_simulation"]["verified"] is False
    assert e2e_partial["ui_ux_button_surface_audit"]["dom_action_simulation"]["all_passed"] is False

    # 3. Dead-end 404 route in HTML -> real dead_end_404_routes_count > 0 and FAIL
    (gh_repo / "dist" / "tools" / "soc-2-audit-cost-calculator" / "index.html").write_text(
        '<!DOCTYPE html><html><body><a href="/r/totally_missing_slug_404">Broken</a></body></html>',
        encoding="utf-8",
    )
    dead_truth = _audit_tenant_outbound_routing_truth(
        prop_id="gainhelm",
        reg_map=GAINHELM_AFFILIATES,
        repo_root=gh_repo,
    )
    assert dead_truth["dead_end_404_routes_count"] == 1
    assert "totally_missing_slug_404" in dead_truth["dead_end_404_slugs"]

    e2e_dead = audit_end_to_end_monetization_and_fulfillment(
        execute_live=False,
        repo_roots={"gainhelm": gh_repo},
    )
    assert e2e_dead["status"] == "FAIL"
    assert e2e_dead["total_dead_end_404_routes_count"] == 1


def test_wave2_zero_cls_checkout_unavailable_and_cancelled_notice(tmp_path: Path) -> None:
    """
    Executes render_runtime_synchronizer_js() in Node.js vm to prove:
    - checkout_status=unavailable and checkout_status=cancelled append #checkout-status-notice
      at the BOTTOM of #workpaper-unlock-card (never prepending above the fold).
    - Uses Porcelain warning tokens, role=alert/status, aria-live=polite, zero em/en-dashes,
      two .touch-target links (#checkout-status-retry-link & #checkout-status-free-pack-link).
    - Emits telemetry beacons checkout_status_unavailable / checkout_status_cancelled.
    - hydrateInputsFromLocationSearch ignores checkout_status, checkout_fulfilled, lead_id, sku, session_id.
    """
    from pseofactory.visual_primitives import render_runtime_synchronizer_js

    rt_js = render_runtime_synchronizer_js()
    assert_no_forbidden_dashes(rt_js, context="render_runtime_synchronizer_js")

    runner = tmp_path / "test_checkout_status_ux.mjs"
    runner.write_text(
        f"""
import vm from "node:vm";

const runtimeJs = {json.dumps(rt_js)};

function runScenario(searchQs) {{
  const beacons = [];
  const elementsById = new Map();

  function makeEl(tag, id = "") {{
    const attrs = {{}};
    const el = {{
      tagName: tag.toUpperCase(),
      id,
      className: "",
      href: "",
      type: "",
      value: "",
      textContent: "",
      style: {{ cssText: "" }},
      children: [],
      parentNode: null,
      setAttribute(k, v) {{ attrs[k] = String(v); }},
      getAttribute(k) {{ return attrs[k] ?? null; }},
      hasAttribute(k) {{ return Object.prototype.hasOwnProperty.call(attrs, k); }},
      appendChild(child) {{
        child.parentNode = el;
        el.children.push(child);
        if (child.id) elementsById.set(child.id, child);
        return child;
      }},
      removeChild(child) {{
        const idx = el.children.indexOf(child);
        if (idx >= 0) el.children.splice(idx, 1);
        if (child.id && elementsById.get(child.id) === child) elementsById.delete(child.id);
        child.parentNode = null;
        return child;
      }},
      addEventListener() {{}},
      querySelector() {{ return null; }},
      querySelectorAll() {{ return []; }},
      dispatchEvent() {{}},
    }};
    if (id) elementsById.set(id, el);
    return el;
  }}

  const drawer = makeEl("div", "workpaper-unlock-card");
  const existingHeading = makeEl("h3", "upgrade-drawer-heading");
  drawer.appendChild(existingHeading);

  // Input whose id matches "sku" to confirm ignoreParams skips it
  const skuInput = makeEl("input", "sku");
  skuInput.value = "untouched_initial";

  const doc = {{
    readyState: "complete",
    body: makeEl("body"),
    getElementById(id) {{ return elementsById.get(id) || null; }},
    querySelector(sel) {{
      if (sel === "main") return drawer;
      return null;
    }},
    querySelectorAll() {{ return []; }},
    createElement(tag) {{ return makeEl(tag); }},
    addEventListener() {{}},
  }};

  const sandbox = {{
    console,
    URL,
    URLSearchParams,
    setTimeout,
    clearTimeout,
    addEventListener() {{}},
    removeEventListener() {{}},
    history: {{ replaceState() {{}}, pushState() {{}} }},
    document: doc,
    navigator: {{
      sendBeacon(url, payload) {{
        beacons.push({{ url: String(url), payload: String(payload || "") }});
        return true;
      }},
    }},
    location: {{
      href: "https://profithelm.com/tools/section-1031-calculator/" + searchQs,
      pathname: "/tools/section-1031-calculator/",
      search: searchQs,
      origin: "https://profithelm.com",
    }},
  }};
  sandbox.window = sandbox;

  vm.runInNewContext(runtimeJs, sandbox);

  const notice = elementsById.get("checkout-status-notice") || null;
  const retryLink = elementsById.get("checkout-status-retry-link") || null;
  const freeLink = elementsById.get("checkout-status-free-pack-link") || null;
  return {{
    drawerStatus: drawer.getAttribute("data-checkout-status"),
    childIds: drawer.children.map(c => c.id),
    noticeRole: notice ? notice.getAttribute("role") : null,
    noticeAriaLive: notice ? notice.getAttribute("aria-live") : null,
    noticeStyle: notice ? notice.style.cssText : "",
    noticeText: notice && notice.children[0] ? notice.children[0].textContent : "",
    retryHref: retryLink ? retryLink.href : null,
    retryClass: retryLink ? retryLink.className : null,
    retryStyle: retryLink ? retryLink.style.cssText : "",
    freeHref: freeLink ? freeLink.href : null,
    freeClass: freeLink ? freeLink.className : null,
    freeStyle: freeLink ? freeLink.style.cssText : "",
    skuInputValue: skuInput.value,
    beacons,
  }};
}}

const resUnavailable = runScenario("?checkout_status=unavailable&lead_id=lead_u1&sku=ph_1031_boot_replacement_workpapers");
const resCancelled = runScenario("?checkout_status=cancelled&lead_id=lead_c1&sku=ph_1031_boot_replacement_workpapers");
console.log(JSON.stringify({{ resUnavailable, resCancelled }}));
""",
        encoding="utf-8",
    )
    proc = subprocess.run(["node", str(runner)], cwd=str(tmp_path), capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout.strip().splitlines()[-1])

    for key, expected_status, expected_role, expected_beacon in (
        ("resUnavailable", "unavailable", "alert", "checkout_status_unavailable"),
        ("resCancelled", "cancelled", "status", "checkout_status_cancelled"),
    ):
        r = out[key]
        assert r["drawerStatus"] == expected_status
        # Must append at bottom after existing content (zero CLS above the fold)
        assert r["childIds"] == ["upgrade-drawer-heading", "checkout-status-notice"]
        assert r["noticeRole"] == expected_role
        assert r["noticeAriaLive"] == "polite"
        assert "var(--status-warning-bg)" in r["noticeStyle"]
        assert "var(--status-warning-border)" in r["noticeStyle"]
        assert "var(--text-primary)" in r["noticeStyle"]
        assert_no_forbidden_dashes(r["noticeText"], context=f"checkout_notice_{expected_status}")
        assert r["retryClass"] == "touch-target"
        assert "min-height:44px" in r["retryStyle"]
        assert r["retryHref"].startswith("/api/lead-capture?checkout=1")
        assert "&redirect=1" in r["retryHref"]
        assert r["freeClass"] == "touch-target"
        assert "min-height:44px" in r["freeStyle"]
        assert r["freeHref"].startswith("/api/lead-capture?playbook=1")
        assert "&format=html" in r["freeHref"]
        assert r["skuInputValue"] == "untouched_initial"
        assert any(expected_beacon in b["payload"] for b in r["beacons"]), f"Missing beacon {expected_beacon}: {r['beacons']}"


def test_wave2_lienbond_canonical_redirects_22_rules_zero_chains(tmp_path: Path) -> None:
    """
    Verifies all 22 canonical LienBond 301 short-link rules are emitted when targets exist,
    missing targets are omitted (zero dead targets), zero redirect chains exist, rule count <= 95,
    and porcelain_shell._sync_sitemaps_headers_and_redirects merges missing rules cleanly.
    """
    from pseofactory.compiler import (
        LIENBOND_CANONICAL_SHORT_LINK_REDIRECTS,
        build_lienbond_canonical_redirects_content,
    )
    from pseofactory.porcelain_shell import (
        _sync_sitemaps_headers_and_redirects,
        get_porcelain_tenant_profile,
    )

    assert len(LIENBOND_CANONICAL_SHORT_LINK_REDIRECTS) == 22

    dist_dir = tmp_path / "dist"
    (dist_dir / "tools").mkdir(parents=True)
    (dist_dir / "tools" / "index.html").write_text("<html><body>Tools</body></html>", encoding="utf-8")
    (dist_dir / "methodology").mkdir(parents=True)
    (dist_dir / "methodology" / "index.html").write_text("<html><body>Methodology</body></html>", encoding="utf-8")

    # Create all 14 tool targets
    target_dirs = sorted({dst.strip("/") for _, dst in LIENBOND_CANONICAL_SHORT_LINK_REDIRECTS if dst.startswith("/tools/") and dst != "/tools/"})
    for td in target_dirs:
        p = dist_dir / td
        p.mkdir(parents=True, exist_ok=True)
        (p / "index.html").write_text("<html><body>Tool</body></html>", encoding="utf-8")

    # Start with an empty _redirects file (mirroring pre-Wave-2 lienbond/dist/_redirects)
    (dist_dir / "_redirects").write_text("\n", encoding="utf-8")

    profile = get_porcelain_tenant_profile("lienbond")
    mutated = _sync_sitemaps_headers_and_redirects(dist_dir, profile)
    assert "_redirects" in mutated

    raw_redirects = (dist_dir / "_redirects").read_text(encoding="utf-8")
    assert_no_forbidden_dashes(raw_redirects, context="lienbond_redirects")
    active_rules = [
        ln.strip().split()
        for ln in raw_redirects.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    assert len(active_rules) == 22
    assert len(active_rules) <= 95

    sources = {r[0] for r in active_rules}
    for src, dst in LIENBOND_CANONICAL_SHORT_LINK_REDIRECTS:
        assert [src, dst, "301"] in active_rules
        assert (dist_dir / dst.strip("/") / "index.html").is_file()
        assert dst not in sources, f"Redirect chain detected: {src} -> {dst}"

    # Verify missing target directory omits that rule cleanly (zero dead targets)
    missing_dist = tmp_path / "dist_partial"
    (missing_dist / "tools").mkdir(parents=True)
    (missing_dist / "tools" / "index.html").write_text("<html><body>Tools</body></html>", encoding="utf-8")
    partial_content = build_lienbond_canonical_redirects_content(missing_dist)
    partial_rules = [
        ln.strip().split()
        for ln in partial_content.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    assert [r[0] for r in partial_rules] == ["/calculator", "/calculators"]


def test_wave2_gsc_affiliate_placement_ledger_guards(tmp_path: Path) -> None:
    """
    Verifies run_gsc_affiliate_placement_feedback_pass rejects path-like property_id values
    and refuses writing ledgers into /home/ubuntuadmin/projects/ during pytest or workspace root.
    """
    from pseofactory.affiliates import run_gsc_affiliate_placement_feedback_pass

    for bad_prop in ("/tmp/evil", "../escape", "profithelm/sub", "", "   ", ".hidden"):
        with pytest.raises(ValueError, match="Invalid property_id"):
            run_gsc_affiliate_placement_feedback_pass(
                property_id=bad_prop,
                dist_dir=tmp_path / "dist",
                repo_root=tmp_path,
                gsc_rows=[],
                dry_run=True,
            )

    # Refuse writing to workspace root /home/ubuntuadmin/projects
    ws_root = Path("/home/ubuntuadmin/projects")
    if ws_root.is_dir():
        with pytest.raises(ValueError, match="workspace root"):
            run_gsc_affiliate_placement_feedback_pass(
                property_id="profithelm",
                dist_dir=tmp_path / "dist",
                repo_root=ws_root,
                gsc_rows=[],
                dry_run=False,
            )

        # Refuse writing anywhere inside /home/ubuntuadmin/projects during PYTEST_CURRENT_TEST
        ph_live = ws_root / "profithelm-platform"
        if ph_live.is_dir():
            with pytest.raises(ValueError, match="inside workspace during pytest"):
                run_gsc_affiliate_placement_feedback_pass(
                    property_id="profithelm",
                    dist_dir=tmp_path / "dist",
                    repo_root=ph_live,
                    gsc_rows=[],
                    dry_run=False,
                )

    # Valid tmp_path repo_root writes ledger cleanly inside tmp_path/.agy/
    clean_repo = tmp_path / "isolated_tenant"
    (clean_repo / "dist" / "tools").mkdir(parents=True)
    res = run_gsc_affiliate_placement_feedback_pass(
        property_id="profithelm",
        dist_dir=clean_repo / "dist",
        repo_root=clean_repo,
        gsc_rows=[],
        dry_run=False,
    )
    assert res["property_id"] == "profithelm"
    assert (clean_repo / ".agy" / "gsc_affiliate_placement_ledger.json").is_file()


def test_wave2_prexvo_overlay_guardrail_css_and_insolvency_meta_uniqueness() -> None:
    """
    Regression test for Prexvo Stage 3b violations:
    1. .overlay-partner-guardrail is defined in Porcelain CSS for all 4 tenants and included
       in get_porcelain_css_audit_sets() so restricted YMYL guardrail sections have zero
       undefined CSS class violations.
    2. student-loan-forgiveness-tax-bomb-insolvency-calculator always gets its own IRC Section
       108(a)(1)(B) / IRS Form 982 meta description even when GSC maps a 'public service loan
       forgiveness calculator' query onto it, and stale persisted overlays carrying the PSLF
       120-payment meta description self-heal in both inject_overlay_into_html and
       RetroReflectionEngine._overlay_spec_needs_heal.
    """
    import re
    from pseofactory.gsc_remediation import (
        _normalize_meta_120_155,
        inject_overlay_into_html,
    )
    from pseofactory.maintenance import RetroReflectionEngine
    from pseofactory.porcelain_shell import (
        generate_porcelain_stylesheet,
        get_porcelain_css_audit_sets,
        get_porcelain_tenant_profile,
    )

    for prop in ("profithelm", "prexvo", "gainhelm", "lienbond"):
        css = generate_porcelain_stylesheet(get_porcelain_tenant_profile(prop))
        assert ".overlay-partner-guardrail" in css
        assert_no_forbidden_dashes(css, context=f"porcelain_css_{prop}")
        _, defined_classes = get_porcelain_css_audit_sets(prop)
        assert "overlay-partner-guardrail" in defined_classes

    insolvency_slug = "student-loan-forgiveness-tax-bomb-insolvency-calculator"
    pslf_slug = "pslf-qualifying-payment-simulator"

    insolvency_meta = _normalize_meta_120_155(
        "",
        tenant_id="prexvo",
        query_label="public service loan forgiveness calculator",
        slug=insolvency_slug,
    )
    pslf_meta = _normalize_meta_120_155(
        "",
        tenant_id="prexvo",
        query_label="public service loan forgiveness calculator",
        slug=pslf_slug,
    )
    assert insolvency_meta != pslf_meta
    assert "108(a)(1)(B)" in insolvency_meta
    assert "Form 982" in insolvency_meta
    assert "PSLF 120 qualifying" not in insolvency_meta
    assert "PSLF 120 qualifying" in pslf_meta
    assert_no_forbidden_dashes(insolvency_meta, context="prexvo_insolvency_meta")

    stale_overlay = {
        "slug": insolvency_slug,
        "property_id": "prexvo",
        "tenant_id": "prexvo",
        "query": "public service loan forgiveness calculator",
        "title_rewrite": "Student Loan Forgiveness Tax Bomb Calculator 2026 | Prexvo",
        "meta_description": pslf_meta,
        "quick_answer": "Estimate federal student loan forgiveness tax bomb liability and IRS Form 982 insolvency exclusion under IRC Section 108(a)(1)(B).",
        "restricted_public_service": True,
        "commercial_offers_allowed": False,
    }
    assert RetroReflectionEngine._overlay_spec_needs_heal(insolvency_slug, stale_overlay) is True

    sample_html = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>Old Title</title>'
        f'<link rel="canonical" href="https://prexvo.com/tools/{insolvency_slug}/" />'
        f'<meta name="description" content="{pslf_meta}" />'
        '</head><body><main><h1>Tax Bomb Calculator</h1></main></body></html>'
    )
    healed_html = inject_overlay_into_html(sample_html, stale_overlay)
    m_meta = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']', healed_html, re.IGNORECASE)
    assert m_meta is not None
    assert m_meta.group(1) == insolvency_meta
    assert m_meta.group(1) != pslf_meta


def test_wave2_retro_range_slider_scales_and_clamps_sub_200_inputs(tmp_path: Path) -> None:
    """
    Regression test for Stage 3b.1 Chrome CDP failure on /tools/prediction-market-odds/:
    #retro-range-* sliders (min=0, max=200, value=100) are percentage sensitivity multipliers.
    For paired number inputs with baseV <= 200 (like #arb-yes-cents value=48.5 min=1 max=99),
    dragging the slider must scale baseV * (rVal / 100), clamp to [min, max], and restore exact
    baseV (48.5, NOT 100) when reset to 100 so downstream #arb-capital spread stays intact.
    """
    from pseofactory.visual_primitives import render_runtime_synchronizer_js

    rt_js = render_runtime_synchronizer_js()
    assert_no_forbidden_dashes(rt_js, context="render_runtime_synchronizer_js_retro_range")

    runner = tmp_path / "test_retro_range_scaling.mjs"
    runner.write_text(
        f"""
import vm from "node:vm";

const runtimeJs = {json.dumps(rt_js)};
const docListeners = {{}};
const elementsById = new Map();

function makeInput(id, type, value, min = "", max = "") {{
  const attrs = {{}};
  if (min !== "") attrs.min = String(min);
  if (max !== "") attrs.max = String(max);
  const el = {{
    tagName: "INPUT",
    id,
    name: id,
    type,
    value: String(value),
    style: {{ cssText: "" }},
    setAttribute(k, v) {{ attrs[k] = String(v); }},
    getAttribute(k) {{ return Object.prototype.hasOwnProperty.call(attrs, k) ? attrs[k] : null; }},
    hasAttribute(k) {{ return Object.prototype.hasOwnProperty.call(attrs, k); }},
    closest() {{ return null; }},
    addEventListener() {{}},
    dispatchEvent() {{}},
  }};
  elementsById.set(id, el);
  return el;
}}

const yesInput = makeInput("arb-yes-cents", "number", "48.5", "1", "99");
const retroSlider = makeInput("retro-range-prediction-market-odds", "range", "100", "0", "200");

const doc = {{
  readyState: "complete",
  body: {{ appendChild() {{}} }},
  getElementById(id) {{ return elementsById.get(id) || null; }},
  querySelector(sel) {{
    if (sel === 'input[type="number"]') return yesInput;
    return null;
  }},
  querySelectorAll(sel) {{
    if (sel.includes('input[type="number"]') && sel.includes('input[type="range"]')) {{
      return [yesInput, retroSlider];
    }}
    if (sel.includes('input[type="number"]')) return [yesInput];
    if (sel.includes('input[type="range"]')) return [retroSlider];
    return [];
  }},
  createElement() {{ return makeInput("", "div", ""); }},
  addEventListener(ev, fn) {{
    if (!docListeners[ev]) docListeners[ev] = [];
    docListeners[ev].push(fn);
  }},
}};

const sandbox = {{
  console,
  Event: class Event {{ constructor(type) {{ this.type = type; }} }},
  URL,
  URLSearchParams,
  setTimeout,
  clearTimeout,
  addEventListener() {{}},
  removeEventListener() {{}},
  history: {{ replaceState() {{}}, pushState() {{}} }},
  document: doc,
  navigator: {{ sendBeacon() {{ return true; }} }},
  location: {{
    href: "https://profithelm.com/tools/prediction-market-odds/",
    pathname: "/tools/prediction-market-odds/",
    search: "",
    origin: "https://profithelm.com",
  }},
}};
sandbox.window = sandbox;

vm.runInNewContext(runtimeJs, sandbox);

function fireSlider(val) {{
  retroSlider.value = String(val);
  for (const fn of docListeners.input || []) {{
    fn({{ target: retroSlider }});
  }}
  return yesInput.value;
}}

const at150 = fireSlider(150);
const at100Reset = fireSlider(100);
const at0Clamped = fireSlider(0);
yesInput.setAttribute("data-pseo-base-val", "60");
const at200Clamped = fireSlider(200);
console.log(JSON.stringify({{ at150, at100Reset, at0Clamped, at200Clamped }}));
""",
        encoding="utf-8",
    )
    proc = subprocess.run(["node", str(runner)], cwd=str(tmp_path), capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    assert out["at150"] == "72.75"
    assert out["at100Reset"] == "48.5"
    assert out["at0Clamped"] == "1"
    assert out["at200Clamped"] == "99"


