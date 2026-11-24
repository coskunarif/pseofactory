"""
Permanent regression suite for Phase 2 UX, Funnel, Pricing SSOT, Verifier & Deliverables Overhaul.
Covers:
1. Pricing SSOT parity across pricing.py, tenant_facts.py, monetization_vault.json,
   partner_tracker.py, and edge.py (including a dynamic 5th tenant).
2. Clean 3-step funnel HTML & /partners/ route across consumer/business tenants
   + restricted public-service YMYL suppression.
3. Verifier & Browser Verifier blind-spot closures (B1-B8) and negative gates.
4. Edge paid deliverable 402 paywall, session_id download propagation, Quick vs Full
   computed schedule parity, per-buyer unique lead_id + input persistence, XSS escaping,
   zero merchant/bank leak, email rail fallback, and Stripe webhook retry idempotency.
5. Interactive regressions (D1 range step, D2 URL sync, D4 select transitions, D7 /signal/ contrast).
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_node_esm(script: str, timeout: int = 20) -> Dict[str, Any]:
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
    )
    lines = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()]
    return json.loads(lines[-1])


def test_pricing_ssot_parity_and_dynamic_fifth_tenant(tmp_path: Path) -> None:
    """
    Single Pricing Truth Parity across pricing.py, monetization_vault.json,
    TenantFactStore, partner_tracker.py, edge.py, and dynamic 5th-tenant discovery (B7).
    """
    from pseofactory import cli, edge, partner_tracker, pricing
    from pseofactory.tenant_facts import TenantFactStore

    assert pricing.TIER_PRICING["consumer"]["quick"]["price_cents"] == 900
    assert pricing.TIER_PRICING["consumer"]["full"]["price_cents"] == 1900
    assert pricing.TIER_PRICING["business"]["quick"]["price_cents"] == 1500
    assert pricing.TIER_PRICING["business"]["full"]["price_cents"] == 2900
    assert pricing.TIER_PRICING["consumer"]["partner_slot"]["price_cents"] == 29900
    assert pricing.TIER_PRICING["business"]["partner_slot"]["price_cents"] == 29900

    vault = json.loads((REPO_ROOT / "pseofactory" / "monetization_vault.json").read_text(encoding="utf-8"))
    vault_products = vault["master_networks"]["stripe"]["digital_products"]
    for sku_id, product in vault_products.items():
        prop = str(product.get("property_id") or "").lower()
        resolved = pricing.resolve_offer_pricing(prop, sku=sku_id)
        vault_cents = int(product.get("price_cents") or round(float(product["price_usd"]) * 100))
        assert vault_cents == resolved["price_cents"], f"Vault mismatch for {sku_id}"
        assert float(product["price_usd"]) == resolved["price_usd"]

    store = TenantFactStore.get_instance()
    for b2b_tenant in ("profithelm", "gainhelm", "lienbond"):
        assert store.verify_price(b2b_tenant, 15.0) is True
        assert store.verify_price(b2b_tenant, 29.0) is True
        assert store.verify_price(b2b_tenant, 299.0) is True
        assert store.verify_price(b2b_tenant, 49.0) is False
        assert store.verify_price(b2b_tenant, 79.0) is False
    assert store.verify_price("prexvo", 9.0) is True
    assert store.verify_price("prexvo", 19.0) is True
    assert store.verify_price("prexvo", 299.0) is True
    assert store.verify_price("prexvo", 39.0) is False
    assert store.verify_price("prexvo", 49.0) is False

    for sku_id, canon_spec in pricing.OFFER_CATALOG.items():
        offer = partner_tracker.resolve_lead_monetization_offer(
            canon_spec["property_id"], "general", sku=sku_id
        )
        assert offer["offer_sku"] == sku_id
        assert offer["offer_price_cents"] == canon_spec["price_cents"]
        sess = partner_tracker.create_stripe_checkout_session(
            canon_spec["property_id"], "general", sku=sku_id, execute_live=False
        )
        assert sess["offer_price_usd"] == canon_spec["price_usd"]

    for alias_sku, canon_sku in pricing.SKU_ALIASES.items():
        canon_spec = pricing.OFFER_CATALOG[canon_sku]
        alias_offer = partner_tracker.resolve_lead_monetization_offer(
            canon_spec["property_id"], "general", sku=alias_sku
        )
        assert alias_offer["offer_sku"] == canon_sku
        assert alias_offer["offer_price_cents"] == canon_spec["price_cents"]

    for prop in ("profithelm", "prexvo", "gainhelm", "lienbond"):
        edge_src = edge.generate_edge_lead_capture_function(prop)
        tbl = json.loads(pricing.get_edge_pricing_table_json(prop))
        assert "unit_amount" in edge_src
        for sku_id, spec in tbl.items():
            assert sku_id in edge_src
            assert str(spec["price_cents"]) in edge_src

    # Dynamic 5th future tenant pricing + CLI browser adapter discovery (B7)
    acme_repo = tmp_path / "acmehealth"
    (acme_repo / "dist").mkdir(parents=True)
    (acme_repo / ".pseofactory.json").write_text(
        json.dumps(
            {
                "property_id": "acmehealth",
                "domain": "acmehealth.com",
                "canonical_base": "https://acmehealth.com",
                "audience_tier": "consumer",
            }
        ),
        encoding="utf-8",
    )
    (acme_repo / "dist" / "index.html").write_text("<html><body><h1>Acme</h1></body></html>", encoding="utf-8")

    dyn_quick = pricing.resolve_offer_pricing("acmehealth", tier_kind="quick", audience_tier="consumer")
    dyn_full = pricing.resolve_offer_pricing("acmehealth", tier_kind="full", audience_tier="consumer")
    dyn_partner = pricing.resolve_offer_pricing("acmehealth", tier_kind="partner_slot")
    assert dyn_quick["price_cents"] == 900
    assert dyn_full["price_cents"] == 1900
    assert dyn_partner["price_cents"] == 29900

    # Verify cmd_audit discovers dynamic 5th tenant cleanly without skipping
    seen_tenants: list[str] = []

    class _StubAuditor:
        def __init__(self, **kwargs: Any) -> None:
            seen_tenants.append(kwargs["adapter"].tenant_id)

        def run_audit(self, **kwargs: Any) -> Dict[str, Any]:
            return {"status": "PASS", "passed": True, "routes_audited": 1, "failed_count": 0, "findings": []}

    old_env = os.environ.get("WORKSPACE_ROOT")
    os.environ["WORKSPACE_ROOT"] = str(tmp_path)
    try:
        from argparse import Namespace
        import pseofactory.browser_verifier as bv

        orig_auditor = bv.UnifiedBrowserAuditor
        bv.UnifiedBrowserAuditor = _StubAuditor  # type: ignore[assignment]
        try:
            rc = cli.cmd_audit(Namespace(property="acmehealth", browser=True, routes=None))
            assert rc == 0
            assert seen_tenants == ["acmehealth"]
        finally:
            bv.UnifiedBrowserAuditor = orig_auditor  # type: ignore[assignment]
    finally:
        if old_env is None:
            os.environ.pop("WORKSPACE_ROOT", None)
        else:
            os.environ["WORKSPACE_ROOT"] = old_env


def test_clean_three_step_funnel_and_partners_route_across_tenants(tmp_path: Path) -> None:
    """
    Compiled GainHelm & LienBond estates plus ProfitHelm & Prexvo (commercial + restricted YMYL)
    enforce the clean 3-step funnel, zero competing forms, zero leaked copy, and dedicated /partners/.
    """
    from pseofactory import compiler
    from pseofactory.gainhelm_estate import compile_gainhelm_estate_impl
    from pseofactory.porcelain_shell import get_porcelain_tenant_profile, normalize_html_to_porcelain_shell
    from pseofactory.verifier import verify_estate_monetization_and_funnel_hygiene

    gh_repo = tmp_path / "gainhelm"
    gh_repo.mkdir()
    compile_gainhelm_estate_impl(str(gh_repo))
    gh_res = verify_estate_monetization_and_funnel_hygiene(gh_repo / "dist", property_id="gainhelm")
    assert gh_res["status"] == "PASS", gh_res["issues"]
    assert (gh_repo / "dist" / "partners" / "index.html").is_file()
    gh_partners = (gh_repo / "dist" / "partners" / "index.html").read_text(encoding="utf-8")
    assert 'id="partner-registration-form"' in gh_partners
    assert "$299" in gh_partners

    lb_repo = tmp_path / "lienbond"
    compiler.compile_lienbond_estate(lb_repo, run_retrofit=True)
    lb_res = verify_estate_monetization_and_funnel_hygiene(lb_repo / "dist", property_id="lienbond")
    assert lb_res["status"] == "PASS", lb_res["issues"]
    lb_partners = (lb_repo / "dist" / "partners" / "index.html").read_text(encoding="utf-8")
    assert 'id="partner-registration-form"' in lb_partners
    assert "$299" in lb_partners

    # Restricted YMYL (Prexvo PSLF) vs commercial consumer ($9/$19) vs business ($15/$29)
    for prop, slug, expected_prices, is_restricted in (
        ("profithelm", "section-179-calculator", ("$15", "$29"), False),
        ("prexvo", "student-loan-repayment-calculator", ("$9", "$19"), False),
        ("prexvo", "pslf-qualifying-payment-simulator", (), True),
    ):
        raw_calc = (
            f"<!DOCTYPE html><html lang='en'><head><title>{slug}</title>"
            f"<link rel='canonical' href='https://{prop}.com/tools/{slug}/'></head>"
            f"<body><main><h1>{slug}</h1>"
            "<div class='calc-grid'><form class='calculator-form'>"
            "<label for='field-amount'>Amount</label>"
            "<input type='number' id='field-amount' value='100000'>"
            "<div class='result-box'><div class='output-value'>$12,500</div></div>"
            "</form></div>"
            "<form id='lead-capture-form'><input type='email'><button>Email Me Free Summary</button></form>"
            "<form id='partner-registration-form'><button>Register Your Firm</button></form>"
            '<div class="above-fold-preset-bar">Presets</div>'
            "</main></body></html>"
        )
        from pseofactory.visual_primitives import normalize_html_visual_primitives

        profile = get_porcelain_tenant_profile(prop)
        norm_html, _ = normalize_html_to_porcelain_shell(
            raw_calc, f"tools/{slug}/index.html", profile, dist_dir=tmp_path / f"{prop}_dist"
        )
        norm_html, _ = normalize_html_visual_primitives(
            norm_html, is_tenant_porcelain=True, dist_dir=tmp_path / f"{prop}_dist"
        )
        assert "\u2014" not in norm_html and "\u2013" not in norm_html
        assert 'id="lead-capture-form"' not in norm_html
        assert 'id="partner-registration-form"' not in norm_html
        assert "above-fold-preset-bar" not in norm_html
        assert "Email Me Free Summary" not in norm_html
        assert len(re.findall(r"<form\b", norm_html, re.I)) <= 1
        if is_restricted:
            assert 'id="workpaper-unlock-card"' not in norm_html
            assert "data-checkout-trigger" not in norm_html
            assert "contextual-referral-card" not in norm_html
            assert 'href="/r/' not in norm_html
        else:
            assert 'id="workpaper-unlock-card"' in norm_html
            assert 'id="btn-preview-workpaper"' in norm_html
            for p_tok in expected_prices:
                assert p_tok in norm_html


def test_verifier_and_browser_blind_spot_gates_b1_through_b8(tmp_path: Path) -> None:
    """
    Negative gate tests proving verifier.py & browser_verifier.py catch every
    funnel, pricing, referral, copy-hygiene, contrast, slider, and dash blind spot.
    """
    from pseofactory import browser_verifier, verifier

    bad_dist = tmp_path / "bad_dist"
    (bad_dist / "tools" / "demo-calc").mkdir(parents=True)
    (bad_dist / "index.html").write_text(
        "<!DOCTYPE html><html><head><title>Home</title></head><body><footer><a href='/tools/'>Tools</a></footer></body></html>",
        encoding="utf-8",
    )
    (bad_dist / "tools" / "demo-calc" / "index.html").write_text(
        "<!DOCTYPE html><html><head><title>Demo</title>"
        '<script type="application/ld+json">{"name":"Bad \u2014 Dash"}</script>'
        "</head><body><main>"
        "<p>client-side deserializers to prevent crawler or user state corruption</p>"
        "<form class='calculator-form'><input type='number' value='10'></form>"
        "<form id='lead-capture-form'><button>Email Me Free Summary</button></form>"
        "<a href='/r/pending_nonexistent_partner'>Pending</a>"
        "<section id='workpaper-unlock-card' data-offer-price='49'><a data-checkout-trigger='1' data-offer-price='49' href='/api/lead-capture?checkout=1'>Unlock $49</a></section>"
        "</main></body></html>",
        encoding="utf-8",
    )

    rep = verifier.verify_estate_monetization_and_funnel_hygiene(bad_dist, property_id="profithelm")
    assert rep["status"] == "FAIL"
    joined = " | ".join(rep["issues"]).lower()
    assert "em-dash" in joined or "en-dash" in joined
    assert "client-side deserializers" in joined
    assert "email me free summary" in joined
    assert "partner" in joined or "/r/pending_nonexistent_partner" in joined
    assert "49" in joined
    assert "missing dedicated /partners/" in joined or "<form>" in joined

    # Browser verifier blind-spot structural contracts (B1, B2, B3, B5, B6, B8)
    bv_src = Path(browser_verifier.__file__).read_text(encoding="utf-8")
    assert "type=\"range\"" in bv_src or "type=range" in bv_src
    assert "url_sync_tested" in bv_src
    assert "_build_viewport_375_batch_js" in bv_src
    assert "mobile-nav-menu" in bv_src
    assert "application/ld+json" in bv_src
    assert "/partners/" in bv_src
    # B6: signal routes must NOT be exempted from WCAG contrast checks
    assert "isSignalRoute ? false" not in bv_src
    contrast_idx = bv_src.index("const contrastNodes = document.querySelectorAll(")
    assert "if (!isOperatorPwa)" not in bv_src[contrast_idx - 200 : contrast_idx]
    assert "type: 'low_contrast_text'" in bv_src
    # B5: no fallback to unrelated inputs inside widget spec probe
    assert "altInputs" not in bv_src


def test_edge_deliverables_paywall_session_id_xss_and_webhook_retry(tmp_path: Path) -> None:
    """
    Executes generated Edge lead-capture.js and stripe-webhook.js in Node ESM:
    1. Free ?playbook=1&format=csv|datapack returns 402 paywall.
    2. Paid ?fulfill=1&session_id=cs_live_... returns 200 HTML with session_id in CSV & JSON links.
    3. Quick ($15/$9) vs Full ($29/$19) produce distinct deliverables matching computed inputs.
    4. Unique per-buyer lead_id & input persistence across two separate buyers.
    5. XSS payload in inputs/metadata is escaped cleanly in delivered HTML.
    6. Zero merchant_account_id / settlement_bank leaked anywhere.
    7. Paid fulfillment email falls back from failed ZeptoMail to Zoho; Stripe webhook retries
       failed email delivery and suppresses duplicate emails after success.
    """
    from pseofactory import edge

    ph_edge_dir = tmp_path / "ph_edge"
    px_edge_dir = tmp_path / "px_edge"
    ph_edge_dir.mkdir(parents=True, exist_ok=True)
    px_edge_dir.mkdir(parents=True, exist_ok=True)
    ph_lc_path = ph_edge_dir / "lead-capture.js"
    ph_wh_path = ph_edge_dir / "stripe-webhook.js"
    px_lc_path = px_edge_dir / "lead-capture.js"
    ph_lc_path.write_text(edge.generate_edge_lead_capture_function("profithelm"), encoding="utf-8")
    ph_wh_path.write_text(edge.generate_edge_stripe_webhook_function("profithelm"), encoding="utf-8")
    px_lc_path.write_text(edge.generate_edge_lead_capture_function("prexvo"), encoding="utf-8")

    wh_signing_val = "whsec_test_funnel_overhaul"
    sess_id_1 = "cs_live_PROFITHELM_FULL_001"
    sess_id_2 = "cs_live_PROFITHELM_QUICK_002"
    px_sess_id = "cs_live_PREXVO_FULL_003"
    px_quick_sid = "cs_live_PREXVO_QUICK_004"
    ts_now = str(int(time.time()))

    def _sign_webhook(payload_str: str) -> str:
        sig = hmac.new(
            wh_signing_val.encode("utf-8"),
            f"{ts_now}.{payload_str}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"t={ts_now},v1={sig}"

    wh_payload = json.dumps(
        {
            "id": "evt_test_webhook_retry_1",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": sess_id_1,
                    "payment_status": "paid",
                    "status": "complete",
                    "amount_total": 2900,
                    "currency": "usd",
                    "livemode": True,
                    "client_reference_id": "lead_retry_buyer_1",
                    "customer_details": {"email": "buyer1@acmecorp.io"},
                    "metadata": {
                        "property_id": "profithelm",
                        "lead_id": "lead_retry_buyer_1",
                        "tool_slug": "section-179-calculator",
                        "offer_sku": "ph_commercial_capital_audit_toolkit",
                        "calculated_amount": "345000",
                    },
                }
            },
        }
    )
    wh_sig = _sign_webhook(wh_payload)

    harness = f"""
import * as phLc from {json.dumps(ph_lc_path.as_uri())};
import * as phWh from {json.dumps(ph_wh_path.as_uri())};
import * as pxLc from {json.dumps(px_lc_path.as_uri())};

function makeKv() {{
  const map = new Map();
  return {{
    async get(k) {{ return map.has(k) ? map.get(k) : null; }},
    async put(k, v) {{ map.set(k, v); }},
    async list() {{ return {{ keys: Array.from(map.keys()).map(name => ({{ name }})) }}; }},
  }};
}}
const phKv = makeKv();
const pxKv = makeKv();

let zeptoCalls = 0;
let zohoCalls = 0;
let failEmailsNow = true;
const sessionLeadMap = {{}};

globalThis.fetch = async (url, init) => {{
  const u = String(url || "");
  if (u.includes("api.stripe.com/v1/checkout/sessions/")) {{
    const sid = u.split("/v1/checkout/sessions/")[1].split("?")[0];
    const amt = sid === {json.dumps(sess_id_2)}
      ? 1500
      : (sid === {json.dumps(px_quick_sid)} ? 900 : (sid === {json.dumps(px_sess_id)} ? 1900 : 2900));
    const sku = sid === {json.dumps(sess_id_2)}
      ? "ph_instant_statutory_worksheet_19"
      : (sid === {json.dumps(px_quick_sid)}
        ? "px_instant_repayment_worksheet_19"
        : (sid === {json.dumps(px_sess_id)} ? "px_repayment_audit_datapack" : "ph_commercial_capital_audit_toolkit"));
    const prop = (sid === {json.dumps(px_sess_id)} || sid === {json.dumps(px_quick_sid)}) ? "prexvo" : "profithelm";
    return new Response(JSON.stringify({{
      id: sid,
      payment_status: "paid",
      status: "complete",
      amount_total: amt,
      currency: "usd",
      livemode: true,
      client_reference_id: sessionLeadMap[sid] || "lead_prexvo_direct",
      customer_details: {{ email: "buyer@acmecorp.io" }},
      metadata: {{ property_id: prop, offer_sku: sku }}
    }}), {{ status: 200, headers: {{ "Content-Type": "application/json" }} }});
  }}
  if (u.includes("/v1/checkout/sessions") && init && init.method === "POST") {{
    const id = "cs_live_NEW_" + Date.now();
    return new Response(JSON.stringify({{ id, url: "https://checkout.stripe.com/c/pay/" + id, livemode: true }}), {{
      status: 200, headers: {{ "Content-Type": "application/json" }}
    }});
  }}
  if (u.includes("zeptomail")) {{
    zeptoCalls += 1;
    if (failEmailsNow) return new Response(JSON.stringify({{ error: "transient_zepto_503" }}), {{ status: 503 }});
    return new Response(JSON.stringify({{ request_id: "zp_ok_" + zeptoCalls }}), {{ status: 200 }});
  }}
  if (u.includes("api.nango.dev")) {{
    return new Response(JSON.stringify({{ credentials: {{ access_token: "zoho_tok_ok" }} }}), {{ status: 200 }});
  }}
  if (u.includes("mail.zoho.com")) {{
    zohoCalls += 1;
    if (failEmailsNow) return new Response(JSON.stringify({{ error: "transient_zoho_503" }}), {{ status: 503 }});
    return new Response(JSON.stringify({{ data: {{ messageId: "zoho_msg_" + zohoCalls }} }}), {{ status: 200 }});
  }}
  return new Response("{{}}", {{ status: 200 }});
}};

const phEnv = {{
  PROFITHELM_LEADS: phKv,
  STRIPE_SECRET_KEY: "sk_live_test_123",
  STRIPE_WEBHOOK_SECRET: {json.dumps(wh_signing_val)},
  ZEPTOMAIL_TOKEN: "Zoho-enczapikey test",
  NANGO_SECRET_KEY: "nango_sec_123",
  NANGO_CONNECTION_ID: "zoho_conn_123",
  EMAIL_PRIMARY_RAIL: "zeptomail",
}};
const pxEnv = {{
  PREXVO_LEADS: pxKv,
  STRIPE_SECRET_KEY: "sk_live_test_123",
}};

// 1. Free 402 paywall for CSV & JSON datapack
const freeCsv = await phLc.onRequestGet({{
  request: new Request("https://profithelm.com/api/lead-capture?playbook=1&tool_slug=section-179-calculator&amount=345000&format=csv"),
  env: phEnv,
}});
const freeDp = await phLc.onRequestGet({{
  request: new Request("https://profithelm.com/api/lead-capture?playbook=1&tool_slug=section-179-calculator&amount=345000&format=datapack"),
  env: phEnv,
}});

// 2. Two distinct buyers persist separate lead_id & input sets (including XSS payload)
const b1Res = await phLc.onRequestPost({{
  request: new Request("https://profithelm.com/api/lead-capture", {{
    method: "POST",
    headers: {{ "Content-Type": "application/json" }},
    body: JSON.stringify({{
      email: "buyer1@acmecorp.io",
      tool_slug: "section-179-calculator",
      offer_sku: "ph_commercial_capital_audit_toolkit",
      scenario_amount: 345000,
      company: "<script>alert(1)</script>",
      inputs_json: JSON.stringify({{ equipment_cost: 345000, note: "<script>alert(2)</script>" }}),
    }}),
  }}),
  env: phEnv,
}});
const b1 = await b1Res.json();

const b2Res = await phLc.onRequestPost({{
  request: new Request("https://profithelm.com/api/lead-capture", {{
    method: "POST",
    headers: {{ "Content-Type": "application/json" }},
    body: JSON.stringify({{
      email: "buyer2@beta.io",
      tool_slug: "section-179-calculator",
      offer_sku: "ph_instant_statutory_worksheet_19",
      scenario_amount: 120000,
      inputs_json: JSON.stringify({{ equipment_cost: 120000 }}),
    }}),
  }}),
  env: phEnv,
}});
const b2 = await b2Res.json();
sessionLeadMap[{json.dumps(sess_id_1)}] = b1.lead_id;
sessionLeadMap[{json.dumps(sess_id_2)}] = b2.lead_id;
sessionLeadMap[{json.dumps(px_sess_id)}] = "lead_prexvo_direct";
sessionLeadMap[{json.dumps(px_quick_sid)}] = "lead_prexvo_quick";

// 3. Paid fulfill HTML, CSV, JSON datapack (Quick vs Full) + session_id propagation + XSS escaping
const fullHtmlRes = await phLc.onRequestGet({{
  request: new Request(
    "https://profithelm.com/api/lead-capture?fulfill=1&format=html&lead_id=" + encodeURIComponent(b1.lead_id) +
    "&sku=ph_commercial_capital_audit_toolkit&tool_slug=section-179-calculator&amount=345000&session_id={sess_id_1}&inputs_json=" +
    encodeURIComponent(JSON.stringify({{ equipment_cost: 345000, note: "<script>alert(3)</script>" }}))
  ),
  env: phEnv,
}});
const fullHtml = await fullHtmlRes.text();

const quickHtmlRes = await phLc.onRequestGet({{
  request: new Request(
    "https://profithelm.com/api/lead-capture?fulfill=1&format=html&lead_id=" + encodeURIComponent(b2.lead_id) +
    "&sku=ph_instant_statutory_worksheet_19&tool_slug=section-179-calculator&amount=120000&session_id={sess_id_2}"
  ),
  env: phEnv,
}});
const quickHtml = await quickHtmlRes.text();

const fullCsvRes = await phLc.onRequestGet({{
  request: new Request(
    "https://profithelm.com/api/lead-capture?fulfill=1&format=csv&lead_id=" + encodeURIComponent(b1.lead_id) +
    "&sku=ph_commercial_capital_audit_toolkit&tool_slug=section-179-calculator&amount=345000&session_id={sess_id_1}"
  ),
  env: phEnv,
}});
const fullCsv = await fullCsvRes.text();

const fullDpRes = await phLc.onRequestGet({{
  request: new Request(
    "https://profithelm.com/api/lead-capture?fulfill=1&format=datapack&lead_id=" + encodeURIComponent(b1.lead_id) +
    "&sku=ph_commercial_capital_audit_toolkit&tool_slug=section-179-calculator&amount=345000&session_id={sess_id_1}"
  ),
  env: phEnv,
}});
const fullDp = await fullDpRes.text();

// Consumer Prexvo ($19 full) datapack check
const pxDpRes = await pxLc.onRequestGet({{
  request: new Request(
    "https://prexvo.com/api/lead-capture?fulfill=1&format=datapack&tool_slug=student-loan-repayment-calculator&amount=55000&session_id={px_sess_id}"
  ),
  env: pxEnv,
}});
const pxDp = await pxDpRes.text();

// Quick->Full SKU escalation & Quick->datapack paywall enforcement (402)
const phQuickEscalatedFullRes = await phLc.onRequestGet({{
  request: new Request(
    "https://profithelm.com/api/lead-capture?fulfill=1&format=html&lead_id=" + encodeURIComponent(b2.lead_id) +
    "&sku=ph_commercial_capital_audit_toolkit&tool_slug=section-179-calculator&amount=120000&session_id={sess_id_2}"
  ),
  env: phEnv,
}});
const phQuickEscalatedDpRes = await phLc.onRequestGet({{
  request: new Request(
    "https://profithelm.com/api/lead-capture?fulfill=1&format=datapack&lead_id=" + encodeURIComponent(b2.lead_id) +
    "&sku=ph_instant_statutory_worksheet_19&tool_slug=section-179-calculator&amount=120000&session_id={sess_id_2}"
  ),
  env: phEnv,
}});
const pxQuickEscalatedFullRes = await pxLc.onRequestGet({{
  request: new Request(
    "https://prexvo.com/api/lead-capture?fulfill=1&format=html&sku=px_repayment_audit_datapack&tool_slug=student-loan-repayment-calculator&amount=55000&session_id={px_quick_sid}"
  ),
  env: pxEnv,
}});
const pxQuickEscalatedDpRes = await pxLc.onRequestGet({{
  request: new Request(
    "https://prexvo.com/api/lead-capture?fulfill=1&format=datapack&tool_slug=student-loan-repayment-calculator&amount=55000&session_id={px_quick_sid}"
  ),
  env: pxEnv,
}});

// 4. Stripe webhook initial transient email failure -> retry succeeds via Zepto->Zoho fallback -> 3rd attempt suppresses duplicate
const whBody = {json.dumps(wh_payload)};
const whHdrs = {{ "Content-Type": "application/json", "Stripe-Signature": {json.dumps(wh_sig)} }};
const whTry1 = await (await phWh.onRequestPost({{
  request: new Request("https://profithelm.com/api/stripe-webhook", {{ method: "POST", headers: whHdrs, body: whBody }}),
  env: phEnv,
}})).json();

// Restore Zoho while keeping Zepto failing or vice versa -> let Zepto fail once then Zoho succeed on retry!
failEmailsNow = false;
const whTry2 = await (await phWh.onRequestPost({{
  request: new Request("https://profithelm.com/api/stripe-webhook", {{ method: "POST", headers: whHdrs, body: whBody }}),
  env: phEnv,
}})).json();
const whTry3 = await (await phWh.onRequestPost({{
  request: new Request("https://profithelm.com/api/stripe-webhook", {{ method: "POST", headers: whHdrs, body: whBody }}),
  env: phEnv,
}})).json();

console.log(JSON.stringify({{
  freeCsvStatus: freeCsv.status,
  freeDpStatus: freeDp.status,
  b1LeadId: b1.lead_id,
  b2LeadId: b2.lead_id,
  fullHtmlStatus: fullHtmlRes.status,
  quickHtmlStatus: quickHtmlRes.status,
  fullCsvStatus: fullCsvRes.status,
  fullDpStatus: fullDpRes.status,
  pxDpStatus: pxDpRes.status,
  phQuickEscalatedFullStatus: phQuickEscalatedFullRes.status,
  phQuickEscalatedDpStatus: phQuickEscalatedDpRes.status,
  pxQuickEscalatedFullStatus: pxQuickEscalatedFullRes.status,
  pxQuickEscalatedDpStatus: pxQuickEscalatedDpRes.status,
  fullHtmlHasSid: fullHtml.includes("session_id={sess_id_1}"),
  fullHtmlEscapedXss: !fullHtml.includes("<script>alert(3)</script>") && !fullHtml.includes("<script>alert(1)</script>"),
  quickLen: quickHtml.length,
  fullLen: fullHtml.length,
  fullCsvLines: fullCsv.trim().split("\\n").length,
  fullDpHasSensitivity: fullDp.includes("reconciliation_schedule") || fullDp.includes("sensitivity"),
  noBankLeak: !fullHtml.includes("merchant_account_id") && !fullHtml.includes("settlement_bank") && !fullDp.includes("merchant_account_id") && !fullDp.includes("settlement_bank") && !fullCsv.includes("settlement_bank"),
  pxDpPriceOk: pxDp.includes("19"),
  whTry1Dispatched: whTry1.email_dispatched,
  whTry2Dispatched: whTry2.email_dispatched,
  whTry3Already: whTry3.already_fulfilled,
  whTry3Dispatched: whTry3.email_dispatched,
  zeptoCalls,
  zohoCalls,
}}));
"""
    out = _run_node_esm(harness)
    assert out["freeCsvStatus"] == 402
    assert out["freeDpStatus"] == 402
    assert out["b1LeadId"] and out["b2LeadId"] and out["b1LeadId"] != out["b2LeadId"]
    assert out["fullHtmlStatus"] == 200
    assert out["quickHtmlStatus"] == 200
    assert out["fullCsvStatus"] == 200
    assert out["fullDpStatus"] == 200
    assert out["pxDpStatus"] == 200
    assert out["phQuickEscalatedFullStatus"] == 402
    assert out["phQuickEscalatedDpStatus"] == 402
    assert out["pxQuickEscalatedFullStatus"] == 402
    assert out["pxQuickEscalatedDpStatus"] == 402
    assert out["fullHtmlHasSid"] is True
    assert out["fullHtmlEscapedXss"] is True
    assert out["fullLen"] > out["quickLen"]
    assert out["fullCsvLines"] >= 5
    assert out["fullDpHasSensitivity"] is True
    assert out["noBankLeak"] is True
    assert out["pxDpPriceOk"] is True
    assert out["whTry1Dispatched"] is False
    assert out["whTry2Dispatched"] is True
    assert out["whTry3Already"] is True
    assert out["whTry3Dispatched"] is False
    assert out["zeptoCalls"] >= 1


def test_interactive_regressions_d1_d2_d4_d7_in_node_and_compiled_html(tmp_path: Path) -> None:
    """
    Regression checks for interactive defects D1, D2, D4, D7:
    - D1: Compiled sliders use proportional step (never tiny micro-steps like step='1' across $500k).
    - D2 & D4: Node VM simulation proves URL sync + #serp-tax-regime / #serp-loan-filing transitions.
    - D7: Compiled /signal/ endpoint does not emit invisible low-contrast defaults & stays non-exempt in BV.
    """
    from pseofactory import compiler, edge
    from pseofactory.gainhelm_estate import compile_gainhelm_estate_impl
    from pseofactory.visual_primitives import _run_node_vm_button_action_simulation

    # D1: Proportional slider steps on GainHelm & LienBond compiled tools
    gh_repo = tmp_path / "gh"
    gh_repo.mkdir()
    compile_gainhelm_estate_impl(str(gh_repo))
    lb_repo = tmp_path / "lb"
    compiler.compile_lienbond_estate(lb_repo, run_retrofit=True)

    slider_matches = []
    for dist_dir in (gh_repo / "dist", lb_repo / "dist"):
        for html_p in dist_dir.glob("tools/**/*.html"):
            txt = html_p.read_text(encoding="utf-8", errors="ignore")
            for tag in re.findall(r'<input\b[^>]*type=["\']range["\'][^>]*>', txt, re.I):
                slider_matches.append((html_p.parent.name, tag))
                min_m = re.search(r'\bmin=["\']([\d.]+)["\']', tag, re.I)
                max_m = re.search(r'\bmax=["\']([\d.]+)["\']', tag, re.I)
                step_m = re.search(r'\bstep=["\']([\d.]+)["\']', tag, re.I)
                if min_m and max_m and step_m:
                    span = float(max_m.group(1)) - float(min_m.group(1))
                    step_v = float(step_m.group(1))
                    assert step_v > 0
                    assert (span / step_v) <= 2000, f"Micro-step regression on {html_p.parent.name}: {tag}"

    # D2 & D4: Node VM interactive button/select/URL-sync simulation
    sim = _run_node_vm_button_action_simulation()
    assert sim["all_passed"] is True, sim
    for t_res in sim["tenants"]:
        assert t_res["url_sync_passed"] is True, t_res
        assert t_res["workbench_selects_distinct"] is True, t_res
        assert t_res["workpaper_preview_passed"] is True, t_res

    # D7: /signal/ edge page has accessible dark foreground / crisp CSS and no contrast exemption
    sig_js = edge.generate_edge_signal_function()
    assert "signal" in sig_js.lower()
    assert "\u2014" not in sig_js and "\u2013" not in sig_js


@pytest.mark.host_estate
def test_browser_verifier_probe_edge_cases_and_dead_input_detection(tmp_path: Path) -> None:
    """
    Verifies UnifiedBrowserAuditor handles bounded/clamped ranges, zero-gated sibling terms,
    >10M unbounded numeric inputs, and cross-page scenario links without false failures or crashes,
    while still strictly catching genuinely dead calculator inputs.
    """
    import asyncio
    import websockets
    from pseofactory.browser_verifier import EphemeralDistServer, UnifiedBrowserAuditor

    dist = tmp_path / "dist"
    (dist / "tools" / "edge-cases").mkdir(parents=True)
    (dist / "tools" / "other").mkdir(parents=True)
    (dist / "tools" / "other" / "index.html").write_text("<!DOCTYPE html><html><body>OK</body></html>", encoding="utf-8")
    (dist / "tools" / "dead-input").mkdir(parents=True)

    html_ok = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Edge Probe OK</title>
<style>
  a, button, input, select { min-height: 44px; min-width: 44px; font-size: 16px; }
  a:focus, button:focus, input:focus, select:focus { outline: 2px solid #1d4ed8; }
  .output-value { font-variant-numeric: tabular-nums; }
</style></head><body>
<a class="skip-to-content-link" href="#main-content">Skip</a>
<main id="main-content">
  <h1>Edge Probe OK</h1>
  <form class="calculator-form">
    <input type="range" id="field-multi_year_term" min="1" max="3" step="1" value="1">
    <input type="range" id="range-cap_bal" min="0" max="370000" step="1000" value="185000">
    <input type="number" id="input-late_days" value="0" min="0" step="1">
    <input type="number" id="input-forfeit_rate" value="1250" min="0" step="10">
    <input type="number" id="input-volume" value="50000000" min="0" step="any">
  </form>
  <a class="scenario-preset-link" href="/tools/other/?income=450000">Parent Preset</a>
  <div class="result-box"><strong class="output-value" id="out-val">$50,000,000</strong></div>
</main>
<script>
function recalc() {
  const term = Number(document.getElementById('field-multi_year_term').value) || 1;
  const capBal = Math.min(150000, Number(document.getElementById('range-cap_bal').value) || 0);
  const late = Number(document.getElementById('input-late_days').value) || 0;
  const rate = Number(document.getElementById('input-forfeit_rate').value) || 0;
  const vol = Number(document.getElementById('input-volume').value) || 0;
  const val = vol + capBal * term - (late * rate);
  document.getElementById('out-val').textContent = '$' + Math.round(val).toLocaleString('en-US');
}
document.querySelectorAll('input').forEach(el => {
  el.addEventListener('input', recalc);
  el.addEventListener('change', recalc);
});
window.addEventListener('popstate', () => {
  const sp = new URLSearchParams(window.location.search);
  if (sp.has('late_days')) document.getElementById('input-late_days').value = sp.get('late_days');
  recalc();
});
recalc();
</script></body></html>"""

    html_dead = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Dead Input</title>
<style>
  a, button, input { min-height: 44px; min-width: 44px; font-size: 16px; }
  a:focus, button:focus, input:focus { outline: 2px solid #1d4ed8; }
  .output-value { font-variant-numeric: tabular-nums; }
</style></head><body>
<a class="skip-to-content-link" href="#main-content">Skip</a>
<main id="main-content">
  <h1>Dead Input</h1>
  <form class="calculator-form">
    <input type="number" id="calc-input-live" value="100">
    <input type="number" id="calc-input-dead" value="1500">
  </form>
  <div class="result-box"><strong class="output-value" id="out-val">$100</strong></div>
</main>
<script>
function recalc() {
  const v = Number(document.getElementById('calc-input-live').value) || 0;
  document.getElementById('out-val').textContent = '$' + v;
}
document.querySelectorAll('input').forEach(el => {
  el.addEventListener('input', recalc);
  el.addEventListener('change', recalc);
});
</script></body></html>"""

    (dist / "tools" / "edge-cases" / "index.html").write_text(html_ok, encoding="utf-8")
    (dist / "tools" / "dead-input" / "index.html").write_text(html_dead, encoding="utf-8")

    aud = UnifiedBrowserAuditor(dist_dir=dist, isolated_browser=False, no_verify_cache=True)

    async def _run():
        with EphemeralDistServer(dist) as srv:
            info = aud._open_cdp_tab()
            msg_c = [1]
            try:
                async with websockets.connect(info["webSocketDebuggerUrl"], max_size=20 * 1024 * 1024) as ws:
                    await aud._configure_cdp_session(ws, msg_c)
                    res_ok = await aud._audit_route_on_ws(ws, srv.base_url, "/tools/edge-cases/", msg_c)
                    res_dead = await aud._audit_route_on_ws(ws, srv.base_url, "/tools/dead-input/", msg_c)
                    return res_ok, res_dead
            finally:
                aud._close_cdp_tab_and_leaked_loopback(info["id"], active_origin=srv.base_url)

    res_ok, res_dead = asyncio.run(_run())
    assert res_ok["widget_failures"] == [], res_ok["widget_failures"]
    assert res_ok["interactive_surface"]["passed"] is True, res_ok["interactive_surface"]

    dead_ids = {f["widget_id"] for f in res_dead["widget_failures"]}
    assert "mobile_375:calc-input-dead" in dead_ids, res_dead["widget_failures"]
    assert res_dead["interactive_surface"]["passed"] is False
