"""Behavioral proof that edge lead-capture never books revenue without verified Stripe payment.

Runs the REAL generated Cloudflare Pages Function for each tenant under node with a mocked
global fetch (Stripe API) and a mocked KV namespace.
"""

import json
import shutil
import subprocess
import textwrap

import pytest

from pseofactory.edge import generate_edge_lead_capture_function
from pseofactory.lead_classification import (
    classify_lead_email,
    is_verified_stripe_payment,
    revenue_summary,
    verified_revenue_usd,
)

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is required")

TENANTS = {"profithelm": 49, "prexvo": 39, "gainhelm": 79}

HARNESS = textwrap.dedent(
    r"""
    import fs from "node:fs";
    const [modPath, tenant] = process.argv.slice(2);
    const mod = await import(modPath);
    const kvStore = new Map();
    const kv = {
      async put(k, v) { kvStore.set(k, v); },
      async get(k, opts) { const v = kvStore.get(k); return v ? (opts && opts.type === "json" ? JSON.parse(v) : v) : null; },
      async list() { return { keys: [...kvStore.keys()].map((name) => ({ name })) }; },
    };
    const stripeSessions = {
      cs_live_PAID: { id: "cs_live_PAID", livemode: true, payment_status: "paid", amount_total: 4900, currency: "usd", client_reference_id: "LEAD", metadata: { lead_id: "LEAD", property_id: tenant } },
      cs_live_UNPAID: { id: "cs_live_UNPAID", livemode: true, payment_status: "unpaid", amount_total: 4900, currency: "usd", client_reference_id: "LEAD", metadata: { lead_id: "LEAD", property_id: tenant } },
      cs_live_OTHERLEAD: { id: "cs_live_OTHERLEAD", livemode: true, payment_status: "paid", amount_total: 4900, currency: "usd", client_reference_id: "SOMEONE_ELSE", metadata: { lead_id: "SOMEONE_ELSE", property_id: tenant } },
      cs_live_OTHERTENANT: { id: "cs_live_OTHERTENANT", livemode: true, payment_status: "paid", amount_total: 4900, currency: "usd", client_reference_id: "LEAD", metadata: { lead_id: "LEAD", property_id: "elsewhere" } },
    };
    globalThis.fetch = async (url, init) => {
      const u = String(url);
      const m = u.match(/api\.stripe\.com\/v1\/checkout\/sessions\/([^?]+)$/);
      if (m) {
        const s = stripeSessions[decodeURIComponent(m[1])];
        return new Response(JSON.stringify(s || { error: { code: "resource_missing" } }), { status: s ? 200 : 404 });
      }
      if (u.endsWith("/v1/checkout/sessions")) {
        return new Response(JSON.stringify({ id: "cs_live_NEW", url: "https://checkout.stripe.com/c/pay/cs_live_NEW" }), { status: 200 });
      }
      return new Response("{}", { status: 500 });
    };
    const results = {};
    const env = { STRIPE_SECRET_KEY: "sk_live_mock", LEADS_KV: kv, LEADS: kv };
    const call = async (qs, e = env, headers = {}) => {
      const r = await mod.onRequestGet({ request: new Request("https://t.example/api/lead-capture?" + qs, { headers }), env: e });
      const text = await r.text();
      let body = null; try { body = JSON.parse(text); } catch (_) {}
      return { status: r.status, body, location: r.headers.get("location") };
    };
    const base = "lead_id=LEAD&tool_slug=" + (tenant === "prexvo" ? "student-loan-refinance-break-even-calculator" : tenant === "gainhelm" ? "soc-2-audit-cost-calculator" : "section-1031-calculator");
    results.no_session = await call(base + "&fulfill=1");
    results.cs_edge = await call(base + "&fulfill=1&session_id=cs_edge_LEAD");
    results.unpaid = await call(base + "&fulfill=1&session_id=cs_live_UNPAID");
    results.other_lead = await call(base + "&fulfill=1&session_id=cs_live_OTHERLEAD");
    results.other_tenant = await call(base + "&fulfill=1&session_id=cs_live_OTHERTENANT");
    results.unknown = await call(base + "&fulfill=1&session_id=cs_live_NOPE");
    results.no_key = await call(base + "&fulfill=1&session_id=cs_live_PAID", { LEADS_KV: kv });
    results.settle_param = await call(base + "&checkout=1&settle=1&format=json", { LEADS_KV: kv });
    results.settle_redirect = await call(base + "&checkout=1&settle=1&redirect=1", { LEADS_KV: kv });
    results.list_before_paid = await call("limit=50");
    results.paid = await call(base + "&fulfill=1&session_id=cs_live_PAID&format=json");
    results.list_after_paid = await call("limit=50");
    results.checkout_live = await call(base + "&checkout=1&format=json");
    console.log(JSON.stringify(results));
    """
)


def _run(tmp_path, tenant):
    mod = tmp_path / f"{tenant}.mjs"
    mod.write_text(generate_edge_lead_capture_function(tenant), encoding="utf-8")
    harness = tmp_path / "harness.mjs"
    harness.write_text(HARNESS, encoding="utf-8")
    proc = subprocess.run(
        ["node", str(harness), str(mod), tenant], capture_output=True, text=True, timeout=60
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("tenant", sorted(TENANTS))
def test_unpaid_or_forged_sessions_never_settle(tmp_path, tenant):
    res = _run(tmp_path, tenant)
    for name in ("no_session", "cs_edge", "unpaid", "other_lead", "other_tenant", "unknown", "no_key"):
        r = res[name]
        assert r["status"] == 402, (name, r)
        assert r["body"]["status"] == "payment_required"
        assert r["body"]["settled"] is False
        assert r["body"]["attributed_revenue_usd"] == 0
    reasons = {n: res[n]["body"]["reason"] for n in res if isinstance(res[n].get("body"), dict) and "reason" in res[n]["body"]}
    assert reasons["cs_edge"] == "session_id_must_be_a_live_stripe_checkout_session"
    assert reasons["unpaid"] == "payment_status_unpaid"
    assert reasons["other_lead"] == "lead_id_mismatch"
    assert reasons["other_tenant"] == "property_mismatch"
    assert reasons["no_key"] == "stripe_secret_key_not_configured"


@pytest.mark.parametrize("tenant", sorted(TENANTS))
def test_settle_query_param_is_ignored_and_checkout_never_bypasses_stripe(tmp_path, tenant):
    res = _run(tmp_path, tenant)
    # Without a Stripe key the checkout rail must be honestly unavailable, never a free unlock.
    assert res["settle_param"]["status"] == 503
    assert res["settle_param"]["body"]["status"] == "checkout_unavailable"
    assert res["settle_param"]["body"]["checkout_session_id"] is None
    assert res["settle_param"]["body"]["checkout_url"] is None
    loc = res["settle_redirect"]["location"] or ""
    assert "fulfill=1" not in loc and "format=html" not in loc
    assert "checkout_status=unavailable" in loc
    before = res["list_before_paid"]["body"]["summary"]
    assert before["attributed_revenue_usd"] == 0
    assert before["settled_upgrades_count"] == 0
    assert before["settlement_policy"] == "stripe_verified_only"


@pytest.mark.parametrize("tenant", sorted(TENANTS))
def test_verified_paid_session_settles_exactly_once_with_real_amount(tmp_path, tenant):
    res = _run(tmp_path, tenant)
    assert res["paid"]["status"] == 200, res["paid"]
    after = res["list_after_paid"]["body"]["summary"]
    assert after["settled_upgrades_count"] == 1
    assert after["attributed_revenue_usd"] == 49.0  # amount_total from Stripe, not list price
    assert res["checkout_live"]["status"] == 200
    assert res["checkout_live"]["body"]["checkout_session_id"] == "cs_live_NEW"
    # success_url must carry the Stripe session id so the paid page can be verified server-side
    assert "session_id={CHECKOUT_SESSION_ID}" in res["checkout_live"]["body"]["success_url"]
    # public lead list must be PII-masked
    for lead in res["list_after_paid"]["body"]["leads"]:
        assert "***" in (lead["email"] or "***")


def test_generated_edge_has_no_free_settlement_paths():
    for tenant in TENANTS:
        js = generate_edge_lead_capture_function(tenant)
        assert "cs_edge_" not in js
        assert 'get("settle")' not in js
        assert "edge_checkout_rail" not in js
        assert "item.zeptomail_dispatched ||" not in js


def test_lead_classifier_and_revenue_summary_are_truthful():
    for email in (
        "arif.coskun@profithelm.com",
        "coskun.arf@gmail.com",
        "audit@gainhelm.com",
        "ciso@gainhelm.com",
        "support@profithelm.com",
        "x@example.com",
        "t@freightfleet-logistics.com",
    ):
        assert classify_lead_email(email) == "synthetic", email
    assert classify_lead_email("jane.doe@acme-llc.com") == "real"
    rows = [
        {"email": "audit@gainhelm.com", "settlement_status": "settled", "attributed_revenue_usd": 79},
        {"email": "jane.doe@acme-llc.com", "settlement_status": "settled", "attributed_revenue_usd": 49},
        {
            "email": "jane.doe@acme-llc.com",
            "settlement_status": "settled",
            "attributed_revenue_usd": 49,
            "stripe_payment_verified": True,
            "stripe_payment_status": "paid",
            "stripe_checkout_session_id": "cs_live_abc123",
        },
    ]
    assert verified_revenue_usd(rows[0]) == 0.0
    assert is_verified_stripe_payment(rows[2])
    summ = revenue_summary(rows)
    assert summ["verified_cash_usd"] == 49.0
    assert summ["unverified_settled_claims"] == 2
    assert summ["unverified_settled_claims_usd"] == 128.0
    assert summ["synthetic_probe_leads"] == 1
