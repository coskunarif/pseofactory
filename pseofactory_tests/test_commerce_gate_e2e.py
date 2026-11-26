"""
End-to-End Test Suite for Autonomous Commerce, Paywall Isolation & Clickability Gate.
Covers:
1. 50+ site collision-free pricing & SKU generation (solar_pro vs solar_calc, consumer vs business, cross-tenant SKU rejection).
2. Static dist/ deliverable leak detector (csv_content, UNREDACTED_READY_FOR_FILING, *-EXEC-*,
   statutory_execution_artifacts, stale raw 402 CSV/datapack anchors) + verifier.py integration.
3. Isolated Node.js v22 commerce_gate replay (both compliant fixture + negative failure modes AND
   compiled edge workers across all 4 legacy tenants + synthetic 5th site).
4. LiveEdgeVerifier.verify_edge_functions & probe_live_commerce_endpoints (3-tier checkout, unknown SKU 400,
   unpaid ?playbook=1 zero leak, unpaid 402, unsigned webhook 400, /partners/ success_url).
5. Browser verifier JS syntax & contract checks (strict 402, all #anchor + /path/#id navigation,
   homepage #btn-preview-workpaper tool_slug guard, affiliates.py YMYL regex alignment).
6. CLI `commerce-audit` exit codes (0 on PASS, 1 on FAIL).

Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import hashlib
import hmac
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap
import threading
import time
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlparse

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _build_compliant_dist(
    dist_dir: Path,
    property_id: str,
    tool_slug: str,
    quick_price: int,
    full_price: int,
) -> None:
    (dist_dir / "tools" / tool_slug).mkdir(parents=True, exist_ok=True)
    (dist_dir / "partners").mkdir(parents=True, exist_ok=True)
    (dist_dir / "manifests").mkdir(parents=True, exist_ok=True)
    (dist_dir / "ai-benchmarks").mkdir(parents=True, exist_ok=True)
    (dist_dir / "static" / "js").mkdir(parents=True, exist_ok=True)

    (dist_dir / "index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><title>Home</title></head>"
        "<body><footer><a href='/partners/'>Partners</a></footer></body></html>",
        encoding="utf-8",
    )
    (dist_dir / "tools" / "index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><title>Tools</title></head><body><h1>Tools</h1></body></html>",
        encoding="utf-8",
    )
    (dist_dir / "about").mkdir(parents=True, exist_ok=True)
    (dist_dir / "about" / "index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><title>About</title></head><body><h1>About</h1></body></html>",
        encoding="utf-8",
    )
    (dist_dir / "tools" / tool_slug / "index.html").write_text(
        f"<!DOCTYPE html><html lang='en'><head><title>{tool_slug}</title></head>"
        f"<body><main><h1>{tool_slug}</h1>"
        f"<form class='calculator-form'><input type='number' value='10000'></form>"
        f"<section id='workpaper-unlock-card' data-tool-slug='{tool_slug}'>"
        f"<a data-checkout-trigger='1' data-offer-price='{quick_price}' href='/api/checkout?sku=q'>Quick ${quick_price}</a>"
        f"<a data-checkout-trigger='1' data-offer-price='{full_price}' href='/api/checkout?sku=f'>Full ${full_price}</a>"
        f"</section></main></body></html>",
        encoding="utf-8",
    )
    (dist_dir / "partners" / "index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><title>Partners</title></head>"
        "<body><main><form id='partner-registration-form' data-offer-price='299'>"
        "<button type='submit'>Reserve Partner Slot $299</button></form></main></body></html>",
        encoding="utf-8",
    )
    (dist_dir / "catalog.json").write_text(json.dumps({"property_id": property_id, "tools": [tool_slug]}), encoding="utf-8")
    (dist_dir / "media-kit.json").write_text(json.dumps({"property_id": property_id}), encoding="utf-8")
    (dist_dir / "manifests" / "site.json").write_text(json.dumps({"property_id": property_id}), encoding="utf-8")
    (dist_dir / "ai-benchmarks" / "summary.json").write_text(json.dumps({"property_id": property_id}), encoding="utf-8")
    (dist_dir / "static" / "js" / "app.js").write_text("console.log('ready');", encoding="utf-8")


def _write_compliant_mock_edge_workers(
    repo_root: Path,
    property_id: str,
    domain: str,
    valid_tool_slug: str,
    tiers: Dict[str, Dict[str, Any]],
    *,
    leak_free_playbook: bool = False,
    allow_bad_sku_200: bool = False,
    partner_wrong_success_path: bool = False,
    quick_leak_datapack: bool = False,
) -> None:
    api_dir = repo_root / "functions" / "api"
    api_dir.mkdir(parents=True, exist_ok=True)

    cfg = {
        "property_id": property_id,
        "domain": domain,
        "valid_tool_slug": valid_tool_slug,
        "tiers": tiers,
        "leak_free_playbook": leak_free_playbook,
        "allow_bad_sku_200": allow_bad_sku_200,
        "partner_wrong_success_path": partner_wrong_success_path,
        "quick_leak_datapack": quick_leak_datapack,
    }

    lead_capture_js = f"""
import crypto from "node:crypto";

const CFG = {json.dumps(cfg)};
const SKU_MAP = {{
  [CFG.tiers.quick.sku]: CFG.tiers.quick,
  [CFG.tiers.full.sku]: CFG.tiers.full,
  [CFG.tiers.partner_slot.sku]: CFG.tiers.partner_slot,
}};

export function getLeadsKv(env) {{
  return (env && (env.LEADS_KV || env.LEADS)) || null;
}}

function jsonResp(payload, status = 200) {{
  return new Response(JSON.stringify(payload), {{
    status,
    headers: {{ "Content-Type": "application/json" }},
  }});
}}

function resolveOffer(rawSku) {{
  const s = String(rawSku || "").trim().toLowerCase();
  if (!s) return CFG.tiers.full;
  return SKU_MAP[s] || null;
}}

function isRestrictedSlug(slug) {{
  const s = String(slug || "").toLowerCase();
  return CFG.property_id === "prexvo" && (s.includes("pslf") || s.includes("buyback") || s.includes("save-plan"));
}}

export async function dispatchEdgePaidFulfillmentEmail(env, record, sessionId) {{
  const tier = resolveOffer(record.offer_sku) || CFG.tiers.full;
  const email = String(record.email || "");
  if (!email) return {{ dispatched: false }};
  const base = `https://${{CFG.domain}}/api/lead-fulfillment?session_id=${{encodeURIComponent(sessionId)}}&sku=${{encodeURIComponent(tier.sku)}}&tool_slug=${{encodeURIComponent(record.tool_slug || CFG.valid_tool_slug)}}`;
  let htmlbody = "";
  if (tier.tier_kind === "quick") {{
    htmlbody = `<p>Quick Worksheet Ready</p><a href="${{base}}&format=html">HTML</a><a href="${{base}}&format=csv">CSV</a>`;
  }} else if (tier.tier_kind === "full") {{
    htmlbody = `<p>Full Workpaper Ready</p><a href="${{base}}&format=html">HTML</a><a href="${{base}}&format=csv">CSV</a><a href="${{base}}&format=datapack">DataPack</a>`;
  }} else {{
    const firm = record.firm_name || "Partner Firm";
    htmlbody = `<p>Partner Slot Confirmed for ${{firm}}</p><a href="${{base}}&format=html">Receipt</a>`;
  }}
  const resp = await fetch("https://api.zeptomail.com/v1.1/email", {{
    method: "POST",
    headers: {{ "Content-Type": "application/json", Authorization: env.ZEPTOMAIL_TOKEN || "" }},
    body: JSON.stringify({{
      from: {{ address: "arif.coskun@profithelm.com" }},
      to: [{{ email_address: {{ address: email }} }}],
      subject: `Ready (${{tier.sku}})`,
      htmlbody,
    }}),
  }});
  return {{ dispatched: resp.ok }};
}}

export async function onRequestGet({{ request, env }}) {{
  const u = new URL(request.url);
  const skuParam = u.searchParams.get("sku") || "";
  const toolSlug = (u.searchParams.get("tool_slug") || CFG.valid_tool_slug).trim().toLowerCase();

  if (isRestrictedSlug(toolSlug)) {{
    return jsonResp({{ ok: false, error: "restricted_public_service_slug" }}, 400);
  }}

  if (u.searchParams.get("checkout") === "1" || u.pathname === "/api/checkout") {{
    const offer = resolveOffer(skuParam);
    if (!offer && !CFG.allow_bad_sku_200) {{
      return jsonResp({{ ok: false, error: "invalid_sku" }}, 400);
    }}
    const effOffer = offer || CFG.tiers.full;
    const leadId = u.searchParams.get("lead_id") || `lead_${{CFG.property_id}}_${{Date.now()}}_${{Math.random().toString(36).slice(2, 6)}}`;
    const routePath =
      effOffer.tier_kind === "partner_slot"
        ? (CFG.partner_wrong_success_path ? "/tools/partners/" : "/partners/")
        : `/tools/${{toolSlug}}/`;
    const successUrl = `https://${{CFG.domain}}${{routePath}}?checkout_status=success&session_id={{CHECKOUT_SESSION_ID}}`;
    const cancelUrl = `https://${{CFG.domain}}${{routePath}}?checkout_status=cancelled`;
    const params = new URLSearchParams({{
      mode: "payment",
      client_reference_id: leadId,
      success_url: successUrl,
      cancel_url: cancelUrl,
      "line_items[0][price_data][currency]": "usd",
      "line_items[0][price_data][unit_amount]": String(effOffer.price_cents),
      "metadata[property_id]": CFG.property_id,
      "metadata[lead_id]": leadId,
      "metadata[offer_sku]": effOffer.sku,
      "metadata[tool_slug]": toolSlug,
    }});
    const stResp = await fetch("https://api.stripe.com/v1/checkout/sessions", {{
      method: "POST",
      headers: {{ Authorization: `Bearer ${{env.STRIPE_SECRET_KEY}}`, "Content-Type": "application/x-www-form-urlencoded" }},
      body: params.toString(),
    }});
    const stJson = await stResp.json();
    return jsonResp({{
      ok: true,
      status: "checkout_session_ready",
      livemode: true,
      property_id: CFG.property_id,
      lead_id: leadId,
      offer_sku: effOffer.sku,
      offer_price_usd: effOffer.price_usd,
      price_cents: effOffer.price_cents,
      checkout_session_id: stJson.id,
      checkout_url: stJson.url,
      success_url: successUrl,
      cancel_url: cancelUrl,
    }}, 200);
  }}

  if (u.searchParams.get("playbook") === "1") {{
    const fmt = (u.searchParams.get("format") || "json").toLowerCase();
    if (fmt === "csv" || fmt === "datapack") {{
      return jsonResp({{ ok: false, status: "payment_required", settled: false }}, 402);
    }}
    const basePb = {{
      ok: true,
      status: "playbook_ready",
      property_id: CFG.property_id,
      tool_slug: toolSlug,
    }};
    if (CFG.leak_free_playbook) {{
      basePb.csv_content = "Section,Value\\nLEAK,123\\n";
      basePb.period_schedule = [{{ period: "Y1" }}];
    }}
    return jsonResp(basePb, 200);
  }}

  if (u.searchParams.get("fulfill") === "1" || u.pathname === "/api/lead-fulfillment") {{
    const sid = (u.searchParams.get("session_id") || "").trim();
    if (!/^cs_live_/.test(sid)) {{
      return jsonResp({{ ok: false, status: "payment_required", settled: false }}, 402);
    }}
    const stResp = await fetch(`https://api.stripe.com/v1/checkout/sessions/${{encodeURIComponent(sid)}}`, {{
      method: "GET",
      headers: {{ Authorization: `Bearer ${{env.STRIPE_SECRET_KEY}}` }},
    }});
    if (!stResp.ok) {{
      return jsonResp({{ ok: false, status: "payment_required", settled: false }}, 402);
    }}
    const sess = await stResp.json();
    if (sess.payment_status !== "paid" || sess.livemode !== true) {{
      return jsonResp({{ ok: false, status: "payment_required", settled: false }}, 402);
    }}
    const paidSku = (sess.metadata && sess.metadata.offer_sku) || skuParam;
    const paidOffer = resolveOffer(paidSku) || CFG.tiers.full;
    const paidSlug = (sess.metadata && sess.metadata.tool_slug) || toolSlug;
    const paidLeadId = sess.client_reference_id || (sess.metadata && sess.metadata.lead_id) || "lead_mock";
    const fmt = (u.searchParams.get("format") || "json").toLowerCase();
    if (paidOffer.tier_kind === "quick" && fmt === "datapack") {{
      return jsonResp({{ ok: false, status: "payment_required", settled: false }}, 402);
    }}
    const reconSchedule = [
      {{
        line_code: "REC-01",
        line_item: `Primary modeled adjustment for ${{paidSlug}}`,
        authority: "Statutory Baseline",
        baseline_value: "$10,000.00",
        optimized_value: "$8,500.00",
        delta_impact: "-$1,500.00",
      }},
    ];
    if (fmt === "csv") {{
      const escCell = (v) => '"' + String(v === undefined || v === null ? "" : v).replace(/"/g, '""') + '"';
      const rows = [
        ["Section", "Line Code", "Line Item", "Authority / Detail", "Baseline Value", "Optimized / Modeled Value", "Delta / Notes"],
        ["META", "META-TOOL", "Tool Slug", "Canonical Route", paidSlug, paidSlug, "Verified"],
        ["META", "META-STATE", "Jurisdiction", "State Code", "CA", "CA", "Applicable"],
        ["META", "META-SKU", "Offer SKU", "Pricing Tier", paidOffer.sku, paidOffer.sku, paidOffer.tier_kind],
        ["META", "META-LEAD", "Lead Reference", "Session Lead ID", paidLeadId, paidLeadId, "Settled"],
        ["META", "META-YEAR", "Tax / Statutory Year", "Compliance Cycle", "2026", "2026", "Current"],
        ["RECONCILIATION", reconSchedule[0].line_code, reconSchedule[0].line_item, reconSchedule[0].authority, reconSchedule[0].baseline_value, reconSchedule[0].optimized_value, reconSchedule[0].delta_impact],
      ];
      const csvBody = rows.map((r) => r.map(escCell).join(",")).join("\\n") + "\\n";
      return new Response(csvBody, {{ status: 200, headers: {{ "Content-Type": "text/csv" }} }});
    }}
    if (fmt === "html") {{
      const firmName = (sess.metadata && sess.metadata.firm_name) || "";
      return new Response(
        `<html><body><h1>${{paidOffer.tier_kind}} (${{paidSlug}})</h1><p>${{firmName}}</p><p>session_id=${{sid}}</p></body></html>`,
        {{ status: 200, headers: {{ "Content-Type": "text/html" }} }}
      );
    }}
    if (fmt === "datapack") {{
      return jsonResp({{ pack_id: `dp_${{sid}}`, tier_kind: paidOffer.tier_kind, tool_slug: paidSlug, reconciliation_schedule: reconSchedule }}, 200);
    }}
    const dpUrl = (paidOffer.tier_kind === "quick" && !CFG.quick_leak_datapack)
      ? null
      : `/api/lead-fulfillment?session_id=${{sid}}&format=datapack`;
    return jsonResp({{
      ok: true,
      status: "toolkit_fulfilled",
      offer_sku: paidOffer.sku,
      tier_kind: paidOffer.tier_kind,
      datapack_url: dpUrl,
      settlement_attribution: {{ datapack_url: dpUrl }},
    }}, 200);
  }}

  return jsonResp({{ ok: true, property_id: CFG.property_id }}, 200);
}}

export async function onRequestPost(ctx) {{
  return jsonResp({{ ok: true }}, 200);
}}

export async function onRequestOptions() {{
  return new Response(null, {{ status: 204 }});
}}
"""

    checkout_js = (
        'import { onRequestGet as lcGet, onRequestPost as lcPost, onRequestOptions as lcOpt } from "./lead-capture.js";\n'
        'export async function onRequestGet(ctx) { const u = new URL(ctx.request.url); u.searchParams.set("checkout", "1"); return lcGet({ ...ctx, request: new Request(u.toString(), ctx.request) }); }\n'
        'export async function onRequestPost(ctx) { return lcPost(ctx); }\n'
        'export async function onRequestOptions(ctx) { return lcOpt(ctx); }\n'
    )
    fulfillment_js = (
        'import { onRequestGet as lcGet, onRequestPost as lcPost, onRequestOptions as lcOpt } from "./lead-capture.js";\n'
        'export async function onRequestGet(ctx) { const u = new URL(ctx.request.url); u.searchParams.set("fulfill", "1"); return lcGet({ ...ctx, request: new Request(u.toString(), ctx.request) }); }\n'
        'export async function onRequestPost(ctx) { return lcPost(ctx); }\n'
        'export async function onRequestOptions(ctx) { return lcOpt(ctx); }\n'
    )
    webhook_js = f"""
import crypto from "node:crypto";
import {{ getLeadsKv, dispatchEdgePaidFulfillmentEmail }} from "./lead-capture.js";

const CFG = {json.dumps(cfg)};

export async function onRequestPost({{ request, env }}) {{
  const sigHdr = request.headers.get("stripe-signature") || "";
  if (!env || !env.STRIPE_WEBHOOK_SECRET) {{
    return new Response(JSON.stringify({{ ok: false, error: "missing_secret" }}), {{ status: 503 }});
  }}
  const parts = Object.fromEntries(sigHdr.split(",").map((p) => p.split("=")));
  const rawBody = await request.text();
  if (!parts.t || !parts.v1) {{
    return new Response(JSON.stringify({{ ok: false, error: "bad_sig" }}), {{ status: 400 }});
  }}
  const expected = crypto.createHmac("sha256", env.STRIPE_WEBHOOK_SECRET).update(`${{parts.t}}.${{rawBody}}`).digest("hex");
  if (expected !== parts.v1) {{
    return new Response(JSON.stringify({{ ok: false, error: "sig_mismatch" }}), {{ status: 400 }});
  }}
  const evt = JSON.parse(rawBody);
  const sess = (evt.data && evt.data.object) || {{}};
  const sid = sess.id;
  const meta = sess.metadata || {{}};
  const leadId = sess.client_reference_id || meta.lead_id;
  const kv = getLeadsKv(env);
  const lockKey = "stripe_session_fulfilled:" + sid;
  if (kv && (await kv.get(lockKey))) {{
    return new Response(JSON.stringify({{ ok: true, already_fulfilled: true, email_dispatched: false }}), {{ status: 200 }});
  }}
  const rec = {{
    lead_id: leadId,
    property_id: CFG.property_id,
    tool_slug: meta.tool_slug || CFG.valid_tool_slug,
    offer_sku: meta.offer_sku,
    firm_name: meta.firm_name || "",
    email: (sess.customer_details && sess.customer_details.email) || "",
    settled: true,
    stripe_payment_verified: true,
  }};
  if (kv) {{
    await kv.put(leadId, JSON.stringify(rec));
    await kv.put(lockKey, JSON.stringify({{ email_dispatched: true }}));
  }}
  const mailRes = await dispatchEdgePaidFulfillmentEmail(env, rec, sid);
  return new Response(JSON.stringify({{ ok: true, email_dispatched: Boolean(mailRes.dispatched) }}), {{ status: 200 }});
}}
"""

    (api_dir / "lead-capture.js").write_text(lead_capture_js, encoding="utf-8")
    (api_dir / "checkout.js").write_text(checkout_js, encoding="utf-8")
    (api_dir / "lead-fulfillment.js").write_text(fulfillment_js, encoding="utf-8")
    (api_dir / "stripe-webhook.js").write_text(webhook_js, encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Static dist/ deliverable leak detector + verifier.py integration
# ---------------------------------------------------------------------------


def test_static_dist_deliverable_leak_detector_and_verifier_integration(tmp_path: Path) -> None:
    from pseofactory.commerce_gate import audit_static_dist_deliverable_leaks
    from pseofactory.verifier import verify_estate_monetization_and_funnel_hygiene

    dist = tmp_path / "profithelm" / "dist"
    _build_compliant_dist(dist, "profithelm", "section-179-calculator", 15, 29)

    clean_res = audit_static_dist_deliverable_leaks(dist, "profithelm")
    assert clean_res["status"] == "PASS", clean_res
    assert clean_res["passed"] is True
    assert clean_res["files_scanned"] >= 9

    leak_cases = [
        ("tools/section-179-calculator/index.html", "<div>csv_content</div>", "csv_content"),
        ("manifests/site.json", '{"state":"UNREDACTED_READY_FOR_FILING"}', "UNREDACTED_READY_FOR_FILING"),
        ("catalog.json", '{"id":"PH-EXEC-001"}', "PH-EXEC-"),
        ("media-kit.json", '{"id":"GH-EXEC-001"}', "GH-EXEC-"),
        ("ai-benchmarks/summary.json", '{"id":"LB-EXEC-001"}', "LB-EXEC-"),
        ("static/js/app.js", 'var x = "PX-EXEC-001";', "PX-EXEC-"),
        ("manifests/leaked.json", '{"statutory_execution_artifacts":[]}', "statutory_execution_artifacts"),
        (
            "tools/section-179-calculator/index.html",
            '<a href="/api/lead-capture?playbook=1&tool_slug=section-179-calculator&format=csv">CSV</a>',
            "stale raw HTTP 402",
        ),
        (
            "tools/section-179-calculator/index.html",
            '<a href="/api/lead-capture?playbook=1&tool_slug=section-179-calculator&format=datapack">JSON</a>',
            "stale raw HTTP 402",
        ),
    ]

    for rel_path, payload, expected_tok in leak_cases:
        bad_dist = tmp_path / f"bad_{rel_path.replace('/', '_')}_{expected_tok}"
        _build_compliant_dist(bad_dist, "profithelm", "section-179-calculator", 15, 29)
        target_f = bad_dist / rel_path
        target_f.parent.mkdir(parents=True, exist_ok=True)
        existing_txt = target_f.read_text(encoding="utf-8") if target_f.is_file() else ""
        target_f.write_text(existing_txt + payload, encoding="utf-8")

        res = audit_static_dist_deliverable_leaks(bad_dist, "profithelm")
        assert res["status"] == "FAIL", f"Expected FAIL for {rel_path} ({expected_tok})"
        assert any(expected_tok in v for v in res["violations"]), res["violations"]

        v_res = verify_estate_monetization_and_funnel_hygiene(bad_dist, property_id="profithelm")
        assert v_res["status"] == "FAIL"
        assert any("dist_deliverable_leak:" in issue for issue in v_res["issues"]), v_res["issues"]


# ---------------------------------------------------------------------------
# 2. Isolated Node.js v22 commerce_gate replay (positive + negative fail-closed)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(shutil.which("node") is None, reason="node binary required for edge replay")
def test_commerce_gate_node_replay_positive_and_negative_gates(tmp_path: Path) -> None:
    from pseofactory.commerce_gate import (
        audit_tenant_commerce_fail_closed,
        resolve_tenant_commerce_matrix,
        verify_local_edge_commerce_replay,
    )

    # Compliant Prexvo (consumer $9/$19/$299 + PSLF YMYL 400) and ProfitHelm (business $15/$29/$299)
    for prop_id, domain, slug, q_p, f_p in (
        ("prexvo", "prexvo.com", "student-loan-refinance-break-even-calculator", 9, 19),
        ("profithelm", "profithelm.com", "section-179-calculator", 15, 29),
    ):
        repo = tmp_path / f"ok_{prop_id}"
        dist = repo / "dist"
        _build_compliant_dist(dist, prop_id, slug, q_p, f_p)
        (repo / ".pseofactory.json").write_text(
            json.dumps({"property_id": prop_id, "domain": domain, "canonical_base": f"https://{domain}"}),
            encoding="utf-8",
        )
        matrix = resolve_tenant_commerce_matrix(prop_id, repo_root=repo, dist_dir=dist)
        _write_compliant_mock_edge_workers(repo, prop_id, domain, slug, matrix["tiers"])

        replay = verify_local_edge_commerce_replay(repo, prop_id, dist_dir=dist)
        assert replay["status"] == "PASS", replay["issues"]
        full_rep = audit_tenant_commerce_fail_closed(repo, prop_id, dist_dir=dist)
        assert full_rep.passed is True, full_rep.issues

    # Negative fail-closed tests: every defect class must FAIL
    for defect_name, defect_kwargs in (
        ("leak_free_playbook", {"leak_free_playbook": True}),
        ("allow_bad_sku_200", {"allow_bad_sku_200": True}),
        ("partner_wrong_success_path", {"partner_wrong_success_path": True}),
        ("quick_leak_datapack", {"quick_leak_datapack": True}),
    ):
        bad_repo = tmp_path / f"bad_{defect_name}"
        bad_dist = bad_repo / "dist"
        _build_compliant_dist(bad_dist, "profithelm", "section-179-calculator", 15, 29)
        (bad_repo / ".pseofactory.json").write_text(
            json.dumps({"property_id": "profithelm", "domain": "profithelm.com", "canonical_base": "https://profithelm.com"}),
            encoding="utf-8",
        )
        matrix = resolve_tenant_commerce_matrix("profithelm", repo_root=bad_repo, dist_dir=bad_dist)
        _write_compliant_mock_edge_workers(
            bad_repo, "profithelm", "profithelm.com", "section-179-calculator", matrix["tiers"], **defect_kwargs
        )
        rep = verify_local_edge_commerce_replay(bad_repo, "profithelm", dist_dir=bad_dist)
        assert rep["status"] == "FAIL", f"Defect '{defect_name}' should have failed closed"
        assert len(rep["issues"]) >= 1


# ---------------------------------------------------------------------------
# 3. 50+ site collision-free pricing & SKU generation (Worker 1 contract)
# ---------------------------------------------------------------------------


def test_fifty_site_collision_free_pricing_and_cross_tenant_sku_rejection(tmp_path: Path) -> None:
    from pseofactory import pricing

    # Verify consumer vs business pricing across 50+ dynamic tenants, including solar_pro vs solar_calc
    seen_skus: Dict[str, str] = {}
    sample_names = ["solar_pro", "solar_calc", "solar_grid", "solar_home", "solar_fleet"] + [
        f"niche_site_{idx:02d}" for idx in range(1, 50)
    ]
    assert len(sample_names) >= 54

    for idx, pid in enumerate(sample_names):
        aud_tier = "consumer" if idx % 2 == 0 else "business"
        repo = tmp_path / pid
        repo.mkdir(parents=True, exist_ok=True)
        (repo / ".pseofactory.json").write_text(
            json.dumps({"property_id": pid, "domain": f"{pid}.com", "audience_tier": aud_tier}),
            encoding="utf-8",
        )
        cat_res = pricing.get_tenant_edge_pricing_catalog(pid, repo_root=repo)
        offers = cat_res["offers"]
        exp_q, exp_f = (900, 1900) if aud_tier == "consumer" else (1500, 2900)
        tier_cents = {v["tier_kind"]: v["price_cents"] for v in offers.values()}
        assert tier_cents["quick"] == exp_q
        assert tier_cents["full"] == exp_f
        assert tier_cents["partner_slot"] == 29900
        for sku_k in offers:
            assert sku_k not in seen_skus, f"SKU collision '{sku_k}' between '{seen_skus[sku_k]}' and '{pid}'"
            seen_skus[sku_k] = pid

    # Cross-tenant SKU rejection
    sp_cat = pricing.get_tenant_edge_pricing_catalog("solar_pro", repo_root=tmp_path / "solar_pro")
    sc_cat = pricing.get_tenant_edge_pricing_catalog("solar_calc", repo_root=tmp_path / "solar_calc")
    sp_sku = sp_cat["quick_sku"]
    sc_sku = sc_cat["quick_sku"]
    assert pricing.validate_tenant_sku("solar_pro", sp_sku, repo_root=tmp_path / "solar_pro")[0] is True
    assert pricing.validate_tenant_sku("solar_pro", sc_sku, repo_root=tmp_path / "solar_pro")[0] is False
    assert pricing.validate_tenant_sku("solar_pro", "nonexistent_sku_xyz", repo_root=tmp_path / "solar_pro")[0] is False


# ---------------------------------------------------------------------------
# 4. Compiled Edge Worker Replay across 4 legacy tenants + 5th synthetic site
# ---------------------------------------------------------------------------


@pytest.mark.skipif(shutil.which("node") is None, reason="node binary required for compiled edge replay")
def test_compiled_edge_commerce_replay_all_legacy_and_fifth_site(tmp_path: Path) -> None:
    from pseofactory import edge
    from pseofactory.commerce_gate import verify_local_edge_commerce_replay

    tenants = [
        ("profithelm", "profithelm.com", "section-179-calculator", "business", 15, 29),
        ("prexvo", "prexvo.com", "student-loan-refinance-break-even-calculator", "consumer", 9, 19),
        ("gainhelm", "gainhelm.com", "soc-2-audit-cost-calculator", "business", 15, 29),
        ("lienbond", "lienbond.com", "contractor-license-bond-cost-calculator-by-credit-score", "business", 15, 29),
        ("solar_pro", "solarpro.example", "commercial-solar-roi-calculator", "business", 15, 29),
    ]

    for prop_id, domain, slug, aud_tier, q_p, f_p in tenants:
        repo = tmp_path / prop_id
        dist = repo / "dist"
        _build_compliant_dist(dist, prop_id, slug, q_p, f_p)
        (repo / ".pseofactory.json").write_text(
            json.dumps(
                {
                    "property_id": prop_id,
                    "domain": domain,
                    "canonical_base": f"https://{domain}",
                    "audience_tier": aud_tier,
                }
            ),
            encoding="utf-8",
        )
        (repo / "functions" / "api").mkdir(parents=True, exist_ok=True)
        if hasattr(edge, "sync_tenant_edge_functions"):
            edge.sync_tenant_edge_functions(repo, property_id=prop_id)
        else:
            api_dir = repo / "functions" / "api"
            lc_js = edge.generate_edge_lead_capture_function(prop_id, audience_tier=aud_tier, repo_root=repo)
            wh_js = edge.generate_edge_stripe_webhook_function(prop_id)
            checkout_js = (
                'import { onRequestGet as lcGet, onRequestPost as lcPost, onRequestOptions as lcOpt } from "./lead-capture.js";\n'
                "function withFlag(ctx) { const u = new URL(ctx.request.url); if (!u.searchParams.has('checkout')) u.searchParams.set('checkout', '1'); return { ...ctx, request: new Request(u.toString(), ctx.request) }; }\n"
                "export async function onRequestGet(ctx) { return lcGet(withFlag(ctx)); }\n"
                "export async function onRequestPost(ctx) { return lcPost(withFlag(ctx)); }\n"
                "export async function onRequestOptions(ctx) { return lcOpt(ctx); }\n"
            )
            fulfill_js = (
                'import { onRequestGet as lcGet, onRequestPost as lcPost, onRequestOptions as lcOpt } from "./lead-capture.js";\n'
                "function withFlag(ctx) { const u = new URL(ctx.request.url); if (!u.searchParams.has('fulfill')) u.searchParams.set('fulfill', '1'); return { ...ctx, request: new Request(u.toString(), ctx.request) }; }\n"
                "export async function onRequestGet(ctx) { return lcGet(withFlag(ctx)); }\n"
                "export async function onRequestPost(ctx) { return lcPost(withFlag(ctx)); }\n"
                "export async function onRequestOptions(ctx) { return lcOpt(ctx); }\n"
            )
            (api_dir / "lead-capture.js").write_text(lc_js, encoding="utf-8")
            (api_dir / "stripe-webhook.js").write_text(wh_js, encoding="utf-8")
            (api_dir / "checkout.js").write_text(checkout_js, encoding="utf-8")
            (api_dir / "lead-fulfillment.js").write_text(fulfill_js, encoding="utf-8")
        replay = verify_local_edge_commerce_replay(repo, prop_id, dist_dir=dist)
        assert replay["status"] == "PASS", f"{prop_id} compiled edge replay failed: {replay['issues']}"


@pytest.mark.skipif(shutil.which("node") is None, reason="node binary required for asset content quality gate")
def test_paid_asset_content_quality_gate_passes_across_all_four_tenants(tmp_path: Path) -> None:
    from pseofactory import edge
    from pseofactory.commerce_gate import (
        _LEGACY_REPRESENTATIVE_TOOL_CATEGORIES,
        verify_local_edge_commerce_replay,
    )

    tenants = [
        ("profithelm", "profithelm.com", "business", 15, 29),
        ("prexvo", "prexvo.com", "consumer", 9, 19),
        ("gainhelm", "gainhelm.com", "business", 15, 29),
        ("lienbond", "lienbond.com", "business", 15, 29),
    ]

    for prop_id, domain, aud_tier, q_p, f_p in tenants:
        expected_slugs = list(_LEGACY_REPRESENTATIVE_TOOL_CATEGORIES[prop_id])
        assert len(expected_slugs) == 4
        repo = tmp_path / f"acq_{prop_id}"
        dist = repo / "dist"
        _build_compliant_dist(dist, prop_id, expected_slugs[0], q_p, f_p)
        for extra_slug in expected_slugs[1:]:
            (dist / "tools" / extra_slug).mkdir(parents=True, exist_ok=True)
            (dist / "tools" / extra_slug / "index.html").write_text(
                f"<!DOCTYPE html><html lang='en'><head><title>{extra_slug}</title></head>"
                f"<body><main><h1>{extra_slug}</h1></main></body></html>",
                encoding="utf-8",
            )
        (repo / ".pseofactory.json").write_text(
            json.dumps(
                {
                    "property_id": prop_id,
                    "domain": domain,
                    "canonical_base": f"https://{domain}",
                    "audience_tier": aud_tier,
                }
            ),
            encoding="utf-8",
        )
        (repo / "functions" / "api").mkdir(parents=True, exist_ok=True)
        if hasattr(edge, "sync_tenant_edge_functions"):
            edge.sync_tenant_edge_functions(repo, property_id=prop_id)
        else:
            api_dir = repo / "functions" / "api"
            lc_js = edge.generate_edge_lead_capture_function(prop_id, audience_tier=aud_tier, repo_root=repo)
            wh_js = edge.generate_edge_stripe_webhook_function(prop_id)
            checkout_js = (
                'import { onRequestGet as lcGet, onRequestPost as lcPost, onRequestOptions as lcOpt } from "./lead-capture.js";\n'
                "function withFlag(ctx) { const u = new URL(ctx.request.url); if (!u.searchParams.has('checkout')) u.searchParams.set('checkout', '1'); return { ...ctx, request: new Request(u.toString(), ctx.request) }; }\n"
                "export async function onRequestGet(ctx) { return lcGet(withFlag(ctx)); }\n"
                "export async function onRequestPost(ctx) { return lcPost(withFlag(ctx)); }\n"
                "export async function onRequestOptions(ctx) { return lcOpt(ctx); }\n"
            )
            fulfill_js = (
                'import { onRequestGet as lcGet, onRequestPost as lcPost, onRequestOptions as lcOpt } from "./lead-capture.js";\n'
                "function withFlag(ctx) { const u = new URL(ctx.request.url); if (!u.searchParams.has('fulfill')) u.searchParams.set('fulfill', '1'); return { ...ctx, request: new Request(u.toString(), ctx.request) }; }\n"
                "export async function onRequestGet(ctx) { return lcGet(withFlag(ctx)); }\n"
                "export async function onRequestPost(ctx) { return lcPost(withFlag(ctx)); }\n"
                "export async function onRequestOptions(ctx) { return lcOpt(ctx); }\n"
            )
            (api_dir / "lead-capture.js").write_text(lc_js, encoding="utf-8")
            (api_dir / "stripe-webhook.js").write_text(wh_js, encoding="utf-8")
            (api_dir / "checkout.js").write_text(checkout_js, encoding="utf-8")
            (api_dir / "lead-fulfillment.js").write_text(fulfill_js, encoding="utf-8")

        replay = verify_local_edge_commerce_replay(repo, prop_id, dist_dir=dist)
        assert replay["passed"] is True, f"{prop_id} replay failed: {replay['issues']}"
        acq = replay.get("asset_content_quality") or {}
        assert acq.get("passed") is True, f"{prop_id} asset_content_quality failed: {acq}"
        assert acq.get("tools_audited_count") == 4
        assert set(acq.get("audited_tools") or []) == set(expected_slugs)
        assert acq.get("differentiation_passed") is True


@pytest.mark.skipif(shutil.which("node") is None, reason="node binary required for asset content quality negative gate")
def test_paid_asset_content_quality_gate_fails_closed_on_wrong_domain_or_malformed_csv(tmp_path: Path) -> None:
    from pseofactory.commerce_gate import resolve_tenant_commerce_matrix, verify_local_edge_commerce_replay

    # Case 1: Wrong-domain contamination ("DoD CIO" emitted on SOC 2 for gainhelm)
    gh_repo = tmp_path / "bad_soc2_domain"
    gh_dist = gh_repo / "dist"
    _build_compliant_dist(gh_dist, "gainhelm", "soc-2-audit-cost-calculator", 15, 29)
    (gh_repo / ".pseofactory.json").write_text(
        json.dumps({"property_id": "gainhelm", "domain": "gainhelm.com", "canonical_base": "https://gainhelm.com"}),
        encoding="utf-8",
    )
    gh_matrix = resolve_tenant_commerce_matrix("gainhelm", repo_root=gh_repo, dist_dir=gh_dist)
    _write_compliant_mock_edge_workers(
        gh_repo, "gainhelm", "gainhelm.com", "soc-2-audit-cost-calculator", gh_matrix["tiers"]
    )
    (gh_repo / "functions" / "api" / "lead-fulfillment.js").write_text(
        'import { onRequestGet as lcGet, onRequestPost as lcPost, onRequestOptions as lcOpt } from "./lead-capture.js";\n'
        "export async function onRequestGet(ctx) {\n"
        "  const u = new URL(ctx.request.url);\n"
        '  u.searchParams.set("fulfill", "1");\n'
        "  const resp = await lcGet({ ...ctx, request: new Request(u.toString(), ctx.request) });\n"
        '  const slug = (u.searchParams.get("tool_slug") || "").toLowerCase();\n'
        '  const fmt = (u.searchParams.get("format") || "json").toLowerCase();\n'
        '  if (resp.status === 200 && slug === "soc-2-audit-cost-calculator" && fmt === "html") {\n'
        "    const body = await resp.text();\n"
        '    return new Response(body + "<p>Regulator: DoD CIO</p>", { status: 200, headers: { "Content-Type": "text/html" } });\n'
        "  }\n"
        "  return resp;\n"
        "}\n"
        "export async function onRequestPost(ctx) { return lcPost(ctx); }\n"
        "export async function onRequestOptions(ctx) { return lcOpt(ctx); }\n",
        encoding="utf-8",
    )
    gh_rep = verify_local_edge_commerce_replay(gh_repo, "gainhelm", dist_dir=gh_dist)
    assert gh_rep["passed"] is False
    assert gh_rep["asset_content_quality"]["passed"] is False
    assert any("DoD CIO" in msg and "soc-2-audit-cost-calculator" in msg for msg in gh_rep["issues"]), gh_rep["issues"]

    # Case 2: Ragged CSV missing META-TOOL
    csv_repo = tmp_path / "bad_ragged_csv"
    csv_dist = csv_repo / "dist"
    _build_compliant_dist(csv_dist, "profithelm", "section-179-calculator", 15, 29)
    (csv_repo / ".pseofactory.json").write_text(
        json.dumps({"property_id": "profithelm", "domain": "profithelm.com", "canonical_base": "https://profithelm.com"}),
        encoding="utf-8",
    )
    ph_matrix = resolve_tenant_commerce_matrix("profithelm", repo_root=csv_repo, dist_dir=csv_dist)
    _write_compliant_mock_edge_workers(
        csv_repo, "profithelm", "profithelm.com", "section-179-calculator", ph_matrix["tiers"]
    )
    (csv_repo / "functions" / "api" / "lead-fulfillment.js").write_text(
        'import { onRequestGet as lcGet, onRequestPost as lcPost, onRequestOptions as lcOpt } from "./lead-capture.js";\n'
        "export async function onRequestGet(ctx) {\n"
        "  const u = new URL(ctx.request.url);\n"
        '  u.searchParams.set("fulfill", "1");\n'
        "  const resp = await lcGet({ ...ctx, request: new Request(u.toString(), ctx.request) });\n"
        '  const fmt = (u.searchParams.get("format") || "json").toLowerCase();\n'
        '  if (resp.status === 200 && fmt === "csv") {\n'
        '    return new Response("Section,Code,Item,Auth,Base,Opt,Notes\\nMETA,META-STATE,CA,US,1,2,3\\nRAGGED,ONLY,3COLS\\n", { status: 200, headers: { "Content-Type": "text/csv" } });\n'
        "  }\n"
        "  return resp;\n"
        "}\n"
        "export async function onRequestPost(ctx) { return lcPost(ctx); }\n"
        "export async function onRequestOptions(ctx) { return lcOpt(ctx); }\n",
        encoding="utf-8",
    )
    csv_rep = verify_local_edge_commerce_replay(csv_repo, "profithelm", dist_dir=csv_dist)
    assert csv_rep["passed"] is False
    assert csv_rep["asset_content_quality"]["passed"] is False
    assert any("Ragged CSV" in msg for msg in csv_rep["issues"]), csv_rep["issues"]
    assert any("META-TOOL" in msg for msg in csv_rep["issues"]), csv_rep["issues"]

    # Case 3: Broken token slop (undefined + U+2014) & identical reconciliation_schedule across categories
    slop_repo = tmp_path / "bad_slop_and_generic"
    slop_dist = slop_repo / "dist"
    _build_compliant_dist(slop_dist, "profithelm", "section-179-calculator", 15, 29)
    (slop_repo / ".pseofactory.json").write_text(
        json.dumps({"property_id": "profithelm", "domain": "profithelm.com", "canonical_base": "https://profithelm.com"}),
        encoding="utf-8",
    )
    _write_compliant_mock_edge_workers(
        slop_repo, "profithelm", "profithelm.com", "section-179-calculator", ph_matrix["tiers"]
    )
    (slop_repo / "functions" / "api" / "lead-fulfillment.js").write_text(
        'import { onRequestGet as lcGet, onRequestPost as lcPost, onRequestOptions as lcOpt } from "./lead-capture.js";\n'
        "export async function onRequestGet(ctx) {\n"
        "  const u = new URL(ctx.request.url);\n"
        '  u.searchParams.set("fulfill", "1");\n'
        "  const resp = await lcGet({ ...ctx, request: new Request(u.toString(), ctx.request) });\n"
        '  const fmt = (u.searchParams.get("format") || "json").toLowerCase();\n'
        '  if (resp.status === 200 && fmt === "html") {\n'
        "    const body = await resp.text();\n"
        '    return new Response(body + "<p>Val: undefined " + String.fromCharCode(0x2014) + "</p>", { status: 200, headers: { "Content-Type": "text/html" } });\n'
        "  }\n"
        '  if (resp.status === 200 && fmt === "datapack") {\n'
        "    const dp = await resp.json();\n"
        '    dp.reconciliation_schedule = [{ line_code: "GEN-1", line_item: "Generic Identical Label" }];\n'
        '    return new Response(JSON.stringify(dp), { status: 200, headers: { "Content-Type": "application/json" } });\n'
        "  }\n"
        "  return resp;\n"
        "}\n"
        "export async function onRequestPost(ctx) { return lcPost(ctx); }\n"
        "export async function onRequestOptions(ctx) { return lcOpt(ctx); }\n",
        encoding="utf-8",
    )
    slop_rep = verify_local_edge_commerce_replay(slop_repo, "profithelm", dist_dir=slop_dist)
    assert slop_rep["passed"] is False
    assert slop_rep["asset_content_quality"]["passed"] is False
    assert any("undefined" in msg for msg in slop_rep["issues"]), slop_rep["issues"]
    assert any("U+2014" in msg for msg in slop_rep["issues"]), slop_rep["issues"]
    assert any("Tool-Category Differentiation failed" in msg for msg in slop_rep["issues"]), slop_rep["issues"]


# ---------------------------------------------------------------------------
# 5. LiveEdgeVerifier & probe_live_commerce_endpoints
# ---------------------------------------------------------------------------


def test_live_probe_and_gitops_verify_edge_functions(tmp_path: Path) -> None:
    from pseofactory.commerce_gate import probe_live_commerce_endpoints, resolve_tenant_commerce_matrix
    from pseofactory.gitops import LiveEdgeVerifier

    repo = tmp_path / "acme_solar"
    dist = repo / "dist"
    _build_compliant_dist(dist, "acme_solar", "solar-roi-calculator", 9, 19)
    (repo / ".pseofactory.json").write_text(
        json.dumps({"property_id": "acme_solar", "domain": "acmesolar.com", "audience_tier": "consumer"}),
        encoding="utf-8",
    )
    matrix = resolve_tenant_commerce_matrix("acme_solar", repo_root=repo, dist_dir=dist)
    tiers = matrix["tiers"]
    sku_lookup = {v["sku"]: v for v in tiers.values()}

    state = {"leak_pb": False, "bad_webhook_503": False}

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def _send(self, code: int, body: Any, ctype: str = "application/json") -> None:
            raw = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            p = urlparse(self.path)
            qs = parse_qs(p.query)
            if p.path.startswith("/partners") or p.path.startswith("/tools/"):
                self._send(200, b"<html><body><h1>Route OK</h1></body></html>", "text/html")
                return
            if p.path.startswith("/r/"):
                self.send_response(302)
                self.send_header("Location", "https://www.mercury.com/")
                self.end_headers()
                return
            if p.path == "/api/lead-fulfillment":
                self._send(402, {"ok": False, "status": "payment_required", "settled": False})
                return
            if p.path == "/api/checkout" or (p.path == "/api/lead-capture" and qs.get("checkout") == ["1"]):
                req_sku = (qs.get("sku") or [tiers["full"]["sku"]])[0]
                if req_sku not in sku_lookup:
                    self._send(400, {"ok": False, "error": "invalid_sku"})
                    return
                spec = sku_lookup[req_sku]
                succ_path = "/partners/" if spec["tier_kind"] == "partner_slot" else "/tools/solar-roi-calculator/"
                self._send(
                    200,
                    {
                        "ok": True,
                        "status": "checkout_session_ready",
                        "checkout_mode": "stripe_live_session",
                        "livemode": True,
                        "property_id": "acme_solar",
                        "offer_sku": spec["sku"],
                        "offer_price_usd": spec["price_usd"],
                        "price_cents": spec["price_cents"],
                        "checkout_session_id": "cs_live_probe_1",
                        "checkout_url": "https://checkout.stripe.com/c/pay/cs_live_probe_1",
                        "success_url": f"http://127.0.0.1:{self.server.server_address[1]}{succ_path}?checkout_status=success&session_id={{CHECKOUT_SESSION_ID}}",
                    },
                )
                return
            if p.path == "/api/lead-capture":
                if qs.get("playbook") == ["1"]:
                    fmt = (qs.get("format") or ["json"])[0]
                    if fmt in ("csv", "datapack"):
                        self._send(402, {"ok": False, "status": "payment_required", "settled": False})
                        return
                    payload = {"ok": True, "status": "playbook_ready", "property_id": "acme_solar"}
                    if state["leak_pb"]:
                        payload["csv_content"] = "LEAK,1"
                    self._send(200, payload)
                    return
                self._send(200, {"ok": True, "auth_required": True, "property_id": "acme_solar"})
                return
            self._send(404, {"ok": False})

        def do_POST(self):
            p = urlparse(self.path)
            if p.path == "/api/stripe-webhook":
                if state["bad_webhook_503"]:
                    self._send(503, {"ok": False, "error": "stripe_webhook_secret_unconfigured"})
                else:
                    self._send(400, {"ok": False, "error": "invalid_stripe_signature_header"})
                return
            length = int(self.headers.get("Content-Length") or "0")
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            if body.get("intent") == "partner_registration":
                self._send(
                    200,
                    {
                        "ok": True,
                        "status": "partner_registered",
                        "offer_sku": tiers["partner_slot"]["sku"],
                        "offer_price_usd": 299.0,
                    },
                )
                return
            self._send(200, {"ok": True, "synthetic_test": True, "persisted": False, "property_id": "acme_solar"})

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        base_url = f"http://127.0.0.1:{srv.server_address[1]}"
        live_rep = probe_live_commerce_endpoints(base_url, "acme_solar", repo_root=repo, dist_dir=dist)
        assert live_rep["status"] == "PASS", live_rep["issues"]

        verifier = LiveEdgeVerifier(timeout=5.0, retries=1)
        edge_rep = verifier.verify_edge_functions(base_url, property_id="acme_solar", dist_dir=dist)
        assert edge_rep["status"] == "PASS", edge_rep["issues"]

        state["leak_pb"] = True
        fail_pb = probe_live_commerce_endpoints(base_url, "acme_solar", repo_root=repo, dist_dir=dist)
        assert fail_pb["status"] == "FAIL"
        state["leak_pb"] = False

        state["bad_webhook_503"] = True
        fail_wh = verifier.verify_edge_functions(base_url, property_id="acme_solar", dist_dir=dist)
        assert fail_wh["status"] == "FAIL"
    finally:
        srv.shutdown()
        srv.server_close()


# ---------------------------------------------------------------------------
# 6. Browser Verifier JS contracts & syntax check
# ---------------------------------------------------------------------------


@pytest.mark.skipif(shutil.which("node") is None, reason="node binary required for JS syntax validation")
def test_browser_verifier_js_contracts_and_syntax() -> None:
    from pseofactory import browser_verifier

    bv_js = browser_verifier.UnifiedBrowserAuditor.JS_RUN_E2E_INTERACTIVE_SURFACE
    assert "free_preview_raw_402_download_link" in bv_js
    assert "pbCsvResp.status !== 402" in bv_js
    assert "pbDpResp.status !== 402" in bv_js
    assert "pbCsvResp.status !== 200" not in bv_js
    assert "pbDpResp.status !== 200" not in bv_js
    assert "reconciliation_schedule.length >= 3" not in bv_js
    assert "preview_workpaper_sent_wrong_tool_slug" in bv_js
    assert "normHashPagePath" in bv_js
    assert "links_tested_count" in bv_js

    # Validate JS compiles cleanly under Node.js v22
    check_script = f"new Function({json.dumps('return ' + bv_js)}); console.log('JS_OK');"
    proc = subprocess.run(["node", "--input-type=module", "-e", check_script], capture_output=True, text=True, timeout=15)
    assert proc.returncode == 0, proc.stderr
    assert "JS_OK" in proc.stdout


# ---------------------------------------------------------------------------
# 7. CLI commerce-audit exit codes
# ---------------------------------------------------------------------------


@pytest.mark.skipif(shutil.which("node") is None, reason="node binary required for CLI commerce-audit")
def test_cli_commerce_audit_exit_codes(tmp_path: Path) -> None:
    from pseofactory import cli
    from pseofactory.commerce_gate import resolve_tenant_commerce_matrix

    ws = tmp_path / "ws"
    repo = ws / "solar_calc"
    dist = repo / "dist"
    _build_compliant_dist(dist, "solar_calc", "solar-savings-calculator", 9, 19)
    (repo / ".pseofactory.json").write_text(
        json.dumps({"property_id": "solar_calc", "domain": "solarcalc.com", "audience_tier": "consumer"}),
        encoding="utf-8",
    )
    matrix = resolve_tenant_commerce_matrix("solar_calc", repo_root=repo, dist_dir=dist, workspace_root=ws)
    _write_compliant_mock_edge_workers(repo, "solar_calc", "solarcalc.com", "solar-savings-calculator", matrix["tiers"])

    rc_pass = cli.main(["commerce-audit", "--property", "solar_calc", "--workspace-root", str(ws), "--json"])
    assert rc_pass == 0

    # Inject a dist leak -> must exit non-zero (1)
    (dist / "catalog.json").write_text('{"leak":"UNREDACTED_READY_FOR_FILING"}', encoding="utf-8")
    rc_fail = cli.main(["commerce-audit", "--property", "solar_calc", "--workspace-root", str(ws), "--json"])
    assert rc_fail == 1

    # Real CLI subprocess invocation check
    sub = subprocess.run(
        [sys.executable, "-m", "pseofactory.cli", "commerce-audit", "--property", "solar_calc", "--workspace-root", str(ws), "--json"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert sub.returncode == 1
    out_obj = json.loads(sub.stdout)
    assert out_obj["status"] == "FAIL"
