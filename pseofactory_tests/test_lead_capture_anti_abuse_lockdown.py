"""
Defense-in-depth anti-abuse lockdown contract tests for /api/lead-capture,
porcelain_shell.py footer/root-slug normalization, and EphemeralDistServer.
Covers all 4 tenants (profithelm, gainhelm, prexvo, lienbond).
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import json
import subprocess
import urllib.request
from pathlib import Path

import pytest

from pseofactory.contracts import assert_no_forbidden_dashes, detect_tool_utility_issues
from pseofactory.edge import generate_edge_lead_capture_function
from pseofactory.porcelain_shell import (
    get_porcelain_tenant_profile,
    normalize_html_to_porcelain_shell,
    render_porcelain_footer,
)
from pseofactory.server import EphemeralDistServer


TENANT_SPECS = [
    ("profithelm", "profithelm.com", "PROFITHELM_LEADS", "section-1031-calculator"),
    ("gainhelm", "gainhelm.com", "GAINHELM_LEADS", "soc-2-audit-cost-calculator"),
    ("prexvo", "prexvo.com", "PREXVO_LEADS", "student-loan-refinance-break-even-calculator"),
    ("lienbond", "lienbond.com", "LIENBOND_LEADS", "contractor-license-bond-cost-calculator-by-credit-score"),
]


@pytest.mark.parametrize("prop_id,domain,kv_binding,default_slug", TENANT_SPECS)
def test_edge_lead_capture_anti_abuse_lockdown_all_tenants(
    tmp_path: Path, prop_id: str, domain: str, kv_binding: str, default_slug: str
) -> None:
    """
    Verifies every anti-abuse layer across all 4 tenants in real Node.js execution:
    - Default free form POST suppresses outbound email (free_form_email_disabled, 0 mail calls)
    - Paid Stripe fulfillment email still dispatches when free-form email is disabled
    - GET ?config=1 returns dynamic Turnstile config with Cache-Control
    - Same-Origin & strict CORS enforcement (no ACAO: * when DOMAIN is configured)
    - Query-param email is ignored on POST (400); form-urlencoded body works
    - Honeypot field -> 403 bot_detected
    - Form timing < 1200ms -> 403 submitted_too_fast
    - Turnstile siteverify fail-closed on missing/invalid/wrong-host token; valid token -> 200
    - Per-IP hourly rate limit blocks 4th request -> 429 rate_limited + Retry-After: 3600
    - Per-email 24h dedup returns 200 already_subscribed + deduplicated: true without duplicate KV/mail
    - Global 25/day email cap returns daily_cap_suppressed on 26th email
    - index.html slug normalizes to homepage; HTML/XSS in slug is stripped and escaped in email
    - Synthetic probe (X-Pseofactory-Test: 1) bypasses guards and writes zero KV / zero email
    """
    js_src = generate_edge_lead_capture_function(prop_id)
    assert_no_forbidden_dashes(js_src, f"lead_capture_lockdown_{prop_id}")

    mod_path = tmp_path / f"lead-capture-{prop_id}.mjs"
    mod_path.write_text(js_src, encoding="utf-8")

    runner = tmp_path / f"run_{prop_id}.mjs"
    runner.write_text(
        f"""
import * as mod from {json.dumps(str(mod_path))};

function makeKv() {{
  const map = new Map();
  return {{
    map,
    put: async (k, v) => {{ map.set(k, String(v)); }},
    get: async (k) => (map.has(k) ? map.get(k) : null),
    list: async ({{ prefix }}) => ({{
      keys: Array.from(map.keys()).filter((k) => k.startsWith(prefix)).map((name) => ({{ name }})),
    }}),
  }};
}}

let mailFetchCalls = 0;
let lastZohoBody = null;
let turnstileMode = "valid";

globalThis.fetch = async (url, init) => {{
  const u = String(url);
  if (u.includes("challenges.cloudflare.com/turnstile/v0/siteverify")) {{
    if (turnstileMode === "throw") throw new Error("network_down");
    if (turnstileMode === "http500") return new Response("err", {{ status: 500 }});
    if (turnstileMode === "invalid") return new Response(JSON.stringify({{ success: false }}), {{ status: 200 }});
    if (turnstileMode === "wrong_host") {{
      return new Response(JSON.stringify({{ success: true, hostname: "evil-phish.example" }}), {{ status: 200 }});
    }}
    return new Response(JSON.stringify({{ success: true, hostname: "{domain}" }}), {{ status: 200 }});
  }}
  if (u.includes("api.nango.dev/connection")) {{
    mailFetchCalls += 1;
    return new Response(JSON.stringify({{ credentials: {{ access_token: "zoho_tok_1" }} }}), {{ status: 200 }});
  }}
  if (u.includes("mail.zoho.com/api/accounts")) {{
    mailFetchCalls += 1;
    lastZohoBody = JSON.parse((init && init.body) || "{{}}");
    return new Response(JSON.stringify({{ status: {{ code: 200 }}, data: {{ messageId: "msg_ok_" + mailFetchCalls }} }}), {{ status: 200 }});
  }}
  if (u.includes("api.zeptomail.com")) {{
    mailFetchCalls += 1;
    return new Response(JSON.stringify({{ request_id: "zepto_ok_" + mailFetchCalls }}), {{ status: 200 }});
  }}
  if (u.includes("api.stripe.com/v1/checkout/sessions")) {{
    return new Response(JSON.stringify({{ id: "cs_live_test_1", url: "https://checkout.stripe.com/c/pay/cs_live_test_1" }}), {{ status: 200 }});
  }}
  return new Response("{{}}", {{ status: 404 }});
}};

const out = {{}};

// 1. GET ?config=1 (disabled vs enabled)
{{
  const rOff = await mod.onRequestGet({{
    request: new Request("https://{domain}/api/lead-capture?config=1"),
    env: {{ DOMAIN: "{domain}" }},
  }});
  const rOn = await mod.onRequestGet({{
    request: new Request("https://{domain}/api/lead-capture?config=1", {{
      headers: {{ Origin: "https://{domain}" }},
    }}),
    env: {{ DOMAIN: "{domain}", TURNSTILE_SITE_KEY: "0x4AAA_SITE", TURNSTILE_SECRET_KEY: "0x4AAA_SEC" }},
  }});
  out.configOff = {{ status: rOff.status, body: await rOff.json(), cc: rOff.headers.get("cache-control") }};
  out.configOn = {{ status: rOn.status, body: await rOn.json(), acao: rOn.headers.get("access-control-allow-origin") }};
}}

// 2. Default free form POST suppresses outbound email (zero mail fetch calls) and persists to KV
{{
  mailFetchCalls = 0;
  const kv = makeKv();
  const env = {{
    DOMAIN: "{domain}",
    NANGO_SECRET_KEY: "n_sec",
    NANGO_CONNECTION_ID: "n_conn",
    ZEPTOMAIL_TOKEN: "z_tok",
    STRIPE_SECRET_KEY: "sk_live_mock",
    {kv_binding}: kv,
  }};
  const res = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "POST",
      headers: {{ "content-type": "application/json", origin: "https://{domain}" }},
      body: JSON.stringify({{
        email: "visitor1@realcompany.io",
        tool_slug: "index.html",
        form_rendered_at: Date.now() - 5000,
      }}),
    }}),
    env,
  }});
  const body = await res.json();
  out.defaultFreePost = {{
    status: res.status,
    acao: res.headers.get("access-control-allow-origin"),
    mailFetchCalls,
    zeptomail_dispatched: body.zeptomail_dispatched,
    zeptomail_status: body.zeptomail_status,
    email_provider: body.email_provider,
    tool_slug: body.tool_slug,
    has_playbook_url: Boolean(body.playbook_url),
    has_fulfill_url: Boolean(body.fulfill_url || body.fulfillment_url),
    has_checkout_url: Boolean(body.checkout_url),
    persisted: body.persisted,
    kv_has_lead: kv.map.has(body.lead_id),
  }};

  // 3. Per-email 24h dedup on second submission of same email
  const resDup = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "POST",
      headers: {{ "content-type": "application/json", origin: "https://{domain}" }},
      body: JSON.stringify({{
        email: "visitor1@realcompany.io",
        tool_slug: "{default_slug}",
        form_rendered_at: Date.now() - 5000,
      }}),
    }}),
    env,
  }});
  const dupBody = await resDup.json();
  const leadKeysAfterDup = Array.from(kv.map.keys()).filter((k) => k.startsWith("lead_{prop_id}_"));
  out.dedup = {{
    status: resDup.status,
    body: dupBody,
    leadCount: leadKeysAfterDup.length,
    mailFetchCalls,
  }};
}}

// 4. Paid Stripe fulfillment email STILL dispatches even when PLAYBOOK_FREE_EMAIL_ENABLED is unset
{{
  mailFetchCalls = 0;
  const kv = makeKv();
  const paidRes = await mod.dispatchEdgePaidFulfillmentEmail(
    {{
      NANGO_SECRET_KEY: "n_sec",
      NANGO_CONNECTION_ID: "n_conn",
      {kv_binding}: kv,
    }},
    {{
      lead_id: "lead_{prop_id}_paid_1",
      email: "buyer@realcompany.io",
      tool_slug: "{default_slug}",
    }},
    "cs_live_paid_session_1",
    false
  );
  out.paidEmail = {{ paidRes, mailFetchCalls }};
}}

// 5. Same-Origin & strict CORS enforcement (missing Origin/Referer, cross-origin, pages.dev allowed)
{{
  const kv = makeKv();
  const env = {{ DOMAIN: "{domain}", {kv_binding}: kv }};
  const rNoOrigin = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "POST",
      headers: {{ "content-type": "application/json" }},
      body: JSON.stringify({{ email: "a@realco.io", tool_slug: "{default_slug}" }}),
    }}),
    env,
  }});
  const rCross = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "POST",
      headers: {{ "content-type": "application/json", origin: "https://attacker.evil" }},
      body: JSON.stringify({{ email: "a@realco.io", tool_slug: "{default_slug}" }}),
    }}),
    env,
  }});
  const rPagesDev = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "POST",
      headers: {{ "content-type": "application/json", origin: "https://preview-123.{prop_id}.pages.dev" }},
      body: JSON.stringify({{ email: "pagesdev@realco.io", tool_slug: "{default_slug}" }}),
    }}),
    env,
  }});
  const rOpt = await mod.onRequestOptions({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "OPTIONS",
      headers: {{ origin: "https://attacker.evil" }},
    }}),
    env,
  }});
  out.originChecks = {{
    noOrigin: {{ status: rNoOrigin.status, body: await rNoOrigin.json(), acao: rNoOrigin.headers.get("access-control-allow-origin") }},
    crossOrigin: {{ status: rCross.status, body: await rCross.json(), acao: rCross.headers.get("access-control-allow-origin") }},
    pagesDev: {{ status: rPagesDev.status, acao: rPagesDev.headers.get("access-control-allow-origin") }},
    optionsCrossAcao: rOpt.headers.get("access-control-allow-origin"),
  }};
}}

// 6. Query-param email ignored on POST (400); form-urlencoded body accepted
{{
  const kv = makeKv();
  const env = {{ DOMAIN: "{domain}", {kv_binding}: kv }};
  const rQueryEmail = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture?email=victim@realco.io", {{
      method: "POST",
      headers: {{ "content-type": "application/json", origin: "https://{domain}" }},
      body: JSON.stringify({{ tool_slug: "{default_slug}" }}),
    }}),
    env,
  }});
  const rFormBody = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "POST",
      headers: {{ "content-type": "application/x-www-form-urlencoded", origin: "https://{domain}" }},
      body: "email=formuser%40realco.io&tool_slug=%2Findex.html",
    }}),
    env,
  }});
  out.queryVsForm = {{
    queryEmailStatus: rQueryEmail.status,
    formBodyStatus: rFormBody.status,
    formBodyJson: await rFormBody.json(),
  }};
}}

// 7. Honeypot & form timing checks
{{
  const kv = makeKv();
  const env = {{ DOMAIN: "{domain}", {kv_binding}: kv }};
  const rHp = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "POST",
      headers: {{ "content-type": "application/json", origin: "https://{domain}" }},
      body: JSON.stringify({{ email: "bot@realco.io", company_website: "https://spam.biz" }}),
    }}),
    env,
  }});
  const rFast = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "POST",
      headers: {{ "content-type": "application/json", origin: "https://{domain}" }},
      body: JSON.stringify({{ email: "fast@realco.io", form_rendered_at: Date.now() - 200 }}),
    }}),
    env,
  }});
  out.hpAndFast = {{
    hp: {{ status: rHp.status, body: await rHp.json() }},
    fast: {{ status: rFast.status, body: await rFast.json() }},
  }};
}}

// 8. Turnstile siteverify (missing, invalid, wrong host, throw -> 403; valid -> 200)
{{
  const kv = makeKv();
  const env = {{
    DOMAIN: "{domain}",
    TURNSTILE_SITE_KEY: "0x4AAA_SITE",
    TURNSTILE_SECRET_KEY: "0x4AAA_SEC",
    {kv_binding}: kv,
  }};
  const rMissing = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "POST",
      headers: {{ "content-type": "application/json", origin: "https://{domain}" }},
      body: JSON.stringify({{ email: "ts1@realco.io" }}),
    }}),
    env,
  }});
  turnstileMode = "invalid";
  const rInvalid = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "POST",
      headers: {{ "content-type": "application/json", origin: "https://{domain}" }},
      body: JSON.stringify({{ email: "ts2@realco.io", cf_turnstile_response: "bad_tok" }}),
    }}),
    env,
  }});
  turnstileMode = "wrong_host";
  const rWrongHost = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "POST",
      headers: {{ "content-type": "application/json", origin: "https://{domain}" }},
      body: JSON.stringify({{ email: "ts3@realco.io", cf_turnstile_response: "wrong_host_tok" }}),
    }}),
    env,
  }});
  turnstileMode = "throw";
  const rThrow = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "POST",
      headers: {{ "content-type": "application/json", origin: "https://{domain}" }},
      body: JSON.stringify({{ email: "ts4@realco.io", cf_turnstile_response: "err_tok" }}),
    }}),
    env,
  }});
  turnstileMode = "valid";
  const rValid = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "POST",
      headers: {{ "content-type": "application/json", origin: "https://{domain}" }},
      body: JSON.stringify({{ email: "ts5@realco.io", cf_turnstile_response: "good_tok" }}),
    }}),
    env,
  }});
  out.turnstile = {{
    missing: {{ status: rMissing.status, body: await rMissing.json() }},
    invalid: {{ status: rInvalid.status, body: await rInvalid.json() }},
    wrongHost: {{ status: rWrongHost.status, body: await rWrongHost.json() }},
    throwErr: {{ status: rThrow.status, body: await rThrow.json() }},
    valid: {{ status: rValid.status }},
  }};
}}

// 9. Per-IP rate limit blocks 4th request -> 429 rate_limited
{{
  const kv = makeKv();
  const env = {{ DOMAIN: "{domain}", {kv_binding}: kv }};
  const statuses = [];
  let fourthBody = null;
  let fourthRetryAfter = null;
  for (let i = 1; i <= 4; i++) {{
    const r = await mod.onRequestPost({{
      request: new Request("https://{domain}/api/lead-capture", {{
        method: "POST",
        headers: {{
          "content-type": "application/json",
          origin: "https://{domain}",
          "cf-connecting-ip": "203.0.113.42",
        }},
        body: JSON.stringify({{ email: `ipuser${{i}}@realco.io`, tool_slug: "{default_slug}" }}),
      }}),
      env,
    }});
    statuses.push(r.status);
    if (i === 4) {{
      fourthBody = await r.json();
      fourthRetryAfter = r.headers.get("retry-after");
    }}
  }}
  out.rateLimit = {{ statuses, fourthBody, fourthRetryAfter }};
}}

// 10. Global daily 25/day email cap + HTML escaping of XSS slug
{{
  mailFetchCalls = 0;
  lastZohoBody = null;
  const kv = makeKv();
  const dayKey = "mailcap:day:" + new Date().toISOString().slice(0, 10);
  await kv.put(dayKey, JSON.stringify({{ count: 24 }}));
  const env = {{
    DOMAIN: "{domain}",
    PLAYBOOK_FREE_EMAIL_ENABLED: "1",
    NANGO_SECRET_KEY: "n_sec",
    NANGO_CONNECTION_ID: "n_conn",
    {kv_binding}: kv,
  }};
  const r25 = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "POST",
      headers: {{ "content-type": "application/json", origin: "https://{domain}" }},
      body: JSON.stringify({{
        email: "cap25@realco.io",
        tool_slug: "<script>alert(1)</script>\\r\\nmy-calc",
      }}),
    }}),
    env,
  }});
  const b25 = await r25.json();
  const callsAfter25 = mailFetchCalls;
  const r26 = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "POST",
      headers: {{ "content-type": "application/json", origin: "https://{domain}" }},
      body: JSON.stringify({{
        email: "cap26@realco.io",
        tool_slug: "{default_slug}",
      }}),
    }}),
    env,
  }});
  const b26 = await r26.json();
  out.dailyCapAndXss = {{
    b25_dispatched: b25.zeptomail_dispatched,
    b25_slug: b25.tool_slug,
    lastZohoSubject: lastZohoBody && lastZohoBody.subject,
    lastZohoContent: lastZohoBody && lastZohoBody.content,
    b26_dispatched: b26.zeptomail_dispatched,
    b26_status: b26.zeptomail_status,
    extraMailCallsOn26: mailFetchCalls - callsAfter25,
  }};
}}

// 11. Synthetic probe bypasses Turnstile/Origin/honeypot/rate-limit and writes zero KV / zero email
{{
  mailFetchCalls = 0;
  const kv = makeKv();
  const env = {{
    DOMAIN: "{domain}",
    TURNSTILE_SECRET_KEY: "0x4AAA_SEC",
    PLAYBOOK_FREE_EMAIL_ENABLED: "1",
    NANGO_SECRET_KEY: "n_sec",
    NANGO_CONNECTION_ID: "n_conn",
    {kv_binding}: kv,
  }};
  const rSynth = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "POST",
      headers: {{ "content-type": "application/json", "x-pseofactory-test": "1" }},
      body: JSON.stringify({{
        email: "probe@synthetic.pseofactory.test",
        tool_slug: "{default_slug}",
        synthetic_test: true,
      }}),
    }}),
    env,
  }});
  const bSynth = await rSynth.json();
  out.synthetic = {{
    status: rSynth.status,
    synthetic_test: bSynth.synthetic_test,
    persisted: bSynth.persisted,
    zeptomail_status: bSynth.zeptomail_status,
    kvSize: kv.map.size,
    mailFetchCalls,
  }};
}}

console.log(JSON.stringify(out));
""",
        encoding="utf-8",
    )

    proc = subprocess.run(["node", str(runner)], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, f"{prop_id} node error: {proc.stderr}"
    res = json.loads(proc.stdout.strip().splitlines()[-1])

    # 1. GET ?config=1
    assert res["configOff"]["status"] == 200
    assert res["configOff"]["body"]["turnstile_enabled"] is False
    assert res["configOff"]["body"]["turnstile_site_key"] == ""
    assert "max-age=300" in (res["configOff"]["cc"] or "")
    assert res["configOn"]["status"] == 200
    assert res["configOn"]["body"]["turnstile_enabled"] is True
    assert res["configOn"]["body"]["turnstile_site_key"] == "0x4AAA_SITE"
    assert res["configOn"]["acao"] == f"https://{domain}"

    # 2. Default free-form POST suppresses outbound email
    df = res["defaultFreePost"]
    assert df["status"] == 200
    assert df["acao"] == f"https://{domain}"
    assert df["mailFetchCalls"] == 0
    assert df["zeptomail_dispatched"] is False
    assert df["zeptomail_status"] == "free_form_email_disabled"
    assert df["email_provider"] == "none"
    assert df["tool_slug"] == "homepage"
    assert df["has_playbook_url"] is True
    assert df["has_fulfill_url"] is True
    assert df["has_checkout_url"] is True
    assert df["persisted"] is True
    assert df["kv_has_lead"] is True

    # 3. Per-email 24h dedup
    dd = res["dedup"]
    assert dd["status"] == 200
    assert dd["body"]["status"] == "already_subscribed"
    assert dd["body"]["deduplicated"] is True
    assert dd["body"]["zeptomail_dispatched"] is False
    assert dd["body"]["zeptomail_status"] == "deduplicated_suppressed"
    assert dd["body"]["playbook_url"]
    assert dd["body"]["fulfill_url"]
    assert dd["leadCount"] == 1
    assert dd["mailFetchCalls"] == 0

    # 4. Paid Stripe fulfillment still sends email
    assert res["paidEmail"]["paidRes"]["dispatched"] is True
    assert res["paidEmail"]["paidRes"]["status"] == "sent_edge_zoho_paid_fulfillment"
    assert res["paidEmail"]["mailFetchCalls"] >= 2

    # 5. Same-Origin & strict CORS
    oc = res["originChecks"]
    assert oc["noOrigin"]["status"] == 403
    assert oc["noOrigin"]["body"]["error"] == "origin_not_allowed"
    assert oc["noOrigin"]["acao"] != "*"
    assert oc["crossOrigin"]["status"] == 403
    assert oc["crossOrigin"]["body"]["error"] == "origin_not_allowed"
    assert oc["crossOrigin"]["acao"] == f"https://{domain}"
    assert oc["pagesDev"]["status"] == 200
    assert oc["pagesDev"]["acao"] == f"https://preview-123.{prop_id}.pages.dev"
    assert oc["optionsCrossAcao"] == f"https://{domain}"

    # 6. Query-param email ignored; form-urlencoded works
    qf = res["queryVsForm"]
    assert qf["queryEmailStatus"] == 400
    assert qf["formBodyStatus"] == 200
    assert qf["formBodyJson"]["tool_slug"] == "homepage"

    # 7. Honeypot & fast submission
    assert res["hpAndFast"]["hp"]["status"] == 403
    assert res["hpAndFast"]["hp"]["body"]["error"] == "bot_detected"
    assert res["hpAndFast"]["fast"]["status"] == 403
    assert res["hpAndFast"]["fast"]["body"]["error"] == "submitted_too_fast"

    # 8. Turnstile fail-closed
    ts = res["turnstile"]
    for key in ("missing", "invalid", "wrongHost", "throwErr"):
        assert ts[key]["status"] == 403, f"Turnstile {key} should be 403"
        assert ts[key]["body"]["error"] == "bot_verification_failed"
    assert ts["valid"]["status"] == 200

    # 9. Per-IP rate limit
    assert res["rateLimit"]["statuses"] == [200, 200, 200, 429]
    assert res["rateLimit"]["fourthBody"]["error"] == "rate_limited"
    assert res["rateLimit"]["fourthBody"]["retry_after_seconds"] == 3600
    assert res["rateLimit"]["fourthRetryAfter"] == "3600"

    # 10. Global 25/day email cap + XSS sanitization
    dc = res["dailyCapAndXss"]
    assert dc["b25_dispatched"] is True
    assert "<" not in dc["b25_slug"] and ">" not in dc["b25_slug"]
    assert "\r" not in (dc["lastZohoSubject"] or "") and "\n" not in (dc["lastZohoSubject"] or "")
    assert "<script>" not in (dc["lastZohoContent"] or "").lower()
    assert dc["b26_dispatched"] is False
    assert dc["b26_status"] == "daily_cap_suppressed"
    assert dc["extraMailCallsOn26"] == 0

    # 11. Synthetic probe isolation
    sy = res["synthetic"]
    assert sy["status"] == 200
    assert sy["synthetic_test"] is True
    assert sy["persisted"] is False
    assert sy["zeptomail_status"] == "synthetic_test_suppressed"
    assert sy["kvSize"] == 0
    assert sy["mailFetchCalls"] == 0


def test_porcelain_root_index_slug_and_footer_anti_abuse_markup() -> None:
    """Verifies root index.html normalizes to 'homepage' and footer includes honeypot + Turnstile slot."""
    profile = get_porcelain_tenant_profile("profithelm")
    raw_home = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>ProfitHelm Home</title></head>
<body><main><h1>ProfitHelm Calculators</h1><p>Deterministic statutory models.</p></main></body>
</html>
"""
    norm_home, _ = normalize_html_to_porcelain_shell(raw_home, "index.html", profile)
    assert 'name="tool_slug" value="homepage"' in norm_home
    assert 'name="tool_slug" value="index.html"' not in norm_home
    assert 'name="company_website"' in norm_home
    assert 'class="cf-turnstile-slot"' in norm_home
    assert "/api/lead-capture?config=1" in norm_home
    assert "challenges.cloudflare.com/turnstile/v0/api.js?render=explicit" in norm_home
    assert "playbook_url" in norm_home
    assert_no_forbidden_dashes(norm_home, "porcelain_root_home_anti_abuse")

    norm_tool, _ = normalize_html_to_porcelain_shell(
        raw_home, "tools/section-1031-calculator/index.html", profile
    )
    assert 'name="tool_slug" value="section-1031-calculator"' in norm_tool

    footer_html = render_porcelain_footer(profile, page_slug="homepage")
    assert 'name="company_website"' in footer_html
    assert 'aria-label="Company website"' in footer_html
    assert 'class="cf-turnstile-slot"' in footer_html
    assert "localhost" not in footer_html
    assert "127.0.0.1" not in footer_html
    assert "localhost" not in norm_home
    assert "127.0.0.1" not in norm_home
    assert_no_forbidden_dashes(footer_html, "render_porcelain_footer_anti_abuse")
    utility_issues = detect_tool_utility_issues(norm_home, rel_path="index.html")
    assert not any("company_website" in issue for issue in utility_issues), utility_issues


def test_ephemeral_dist_server_handles_lead_capture_config_endpoint(tmp_path: Path) -> None:
    """Verifies local EphemeralDistServer serves GET /api/lead-capture?config=1 with 200 JSON."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "index.html").write_text("<!doctype html><html><body>ok</body></html>", encoding="utf-8")

    with EphemeralDistServer(dist_dir) as srv:
        url = f"{srv.base_url}/api/lead-capture?config=1"
        with urllib.request.urlopen(url, timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["ok"] is True
            assert data["success"] is True
            assert data["turnstile_enabled"] is False
            assert data["turnstile_site_key"] == ""


@pytest.mark.parametrize("prop_id,domain,kv_binding,default_slug", TENANT_SPECS)
def test_edge_adversarial_origin_protocol_pages_fulfill_nonstring_and_unknown_ip(
    tmp_path: Path, prop_id: str, domain: str, kv_binding: str, default_slug: str
) -> None:
    """
    Regression tests for adversarial review findings across all 4 tenants:
    1. Rejects foreign *.pages.dev, non-https protocols (http://, ftp://) on Origin/Referer/CORS
       and foreign *.pages.dev on Turnstile verifyJson.hostname; allows scoped tenant pages.dev.
    2. Guards POST ?fulfill=1 against synthetic probes (402, 0 Stripe calls), cross-origin (403,
       0 Stripe calls), and IP rate-limit exhaustion (429, 0 Stripe calls on 4th).
    3. Rejects non-string cf_turnstile_response (array/object/number) with 403 and 0 siteverify calls.
    4. Enforces per-IP rate limit via 'unknown' bucket when both CF-Connecting-IP and X-Forwarded-For are absent.
    """
    js_src = generate_edge_lead_capture_function(prop_id)
    mod_path = tmp_path / f"adv-{prop_id}.mjs"
    mod_path.write_text(js_src, encoding="utf-8")

    runner = tmp_path / f"run_adv_{prop_id}.mjs"
    runner.write_text(
        f"""
import * as mod from {json.dumps(str(mod_path))};

function makeKv() {{
  const map = new Map();
  return {{
    map,
    put: async (k, v) => {{ map.set(k, String(v)); }},
    get: async (k) => (map.has(k) ? map.get(k) : null),
    list: async ({{ prefix }}) => ({{
      keys: Array.from(map.keys()).filter((k) => k.startsWith(prefix)).map((name) => ({{ name }})),
    }}),
  }};
}}

let stripeCalls = 0;
let siteverifyCalls = 0;
let tsVerifyHost = "{domain}";

globalThis.fetch = async (url) => {{
  const u = String(url);
  if (u.includes("api.stripe.com")) {{
    stripeCalls += 1;
    return new Response(JSON.stringify({{ id: "cs_live_unpaid", payment_status: "unpaid" }}), {{ status: 200 }});
  }}
  if (u.includes("challenges.cloudflare.com/turnstile/v0/siteverify")) {{
    siteverifyCalls += 1;
    return new Response(JSON.stringify({{ success: true, hostname: tsVerifyHost }}), {{ status: 200 }});
  }}
  return new Response("{{}}", {{ status: 404 }});
}};

const out = {{}};

// 1. Foreign *.pages.dev and non-https protocol rejection on Origin, CORS, and Turnstile hostname
{{
  const kv = makeKv();
  const env = {{ DOMAIN: "{domain}", {kv_binding}: kv }};
  const rForeignPages = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "POST",
      headers: {{ "content-type": "application/json", origin: "https://attacker-spammer-999.pages.dev" }},
      body: JSON.stringify({{ email: "a@realco.io", tool_slug: "{default_slug}" }}),
    }}),
    env,
  }});
  const rEvilSuffixPages = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "POST",
      headers: {{ "content-type": "application/json", origin: "https://evil{prop_id}.pages.dev" }},
      body: JSON.stringify({{ email: "a@realco.io", tool_slug: "{default_slug}" }}),
    }}),
    env,
  }});
  const rHttpOrigin = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "POST",
      headers: {{ "content-type": "application/json", origin: "http://{domain}" }},
      body: JSON.stringify({{ email: "a@realco.io", tool_slug: "{default_slug}" }}),
    }}),
    env,
  }});
  const rFtpReferer = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "POST",
      headers: {{ "content-type": "application/json", referer: "ftp://{domain}/tools/" }},
      body: JSON.stringify({{ email: "a@realco.io", tool_slug: "{default_slug}" }}),
    }}),
    env,
  }});
  const rOptForeignPages = await mod.onRequestOptions({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "OPTIONS",
      headers: {{ origin: "https://attacker-spammer-999.pages.dev" }},
    }}),
    env,
  }});
  const rOptHttp = await mod.onRequestOptions({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "OPTIONS",
      headers: {{ origin: "http://{domain}" }},
    }}),
    env,
  }});
  const rOwnPagesRoot = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "POST",
      headers: {{ "content-type": "application/json", origin: "https://{prop_id}.pages.dev" }},
      body: JSON.stringify({{ email: "ownpages@realco.io", tool_slug: "{default_slug}" }}),
    }}),
    env,
  }});
  const rOwnPagesPreview = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "POST",
      headers: {{ "content-type": "application/json", origin: "https://abc123.{prop_id}.pages.dev" }},
      body: JSON.stringify({{ email: "preview@realco.io", tool_slug: "{default_slug}" }}),
    }}),
    env,
  }});
  out.originHardening = {{
    foreignPages: {{ status: rForeignPages.status, acao: rForeignPages.headers.get("access-control-allow-origin") }},
    evilSuffixPages: {{ status: rEvilSuffixPages.status }},
    httpOrigin: {{ status: rHttpOrigin.status, acao: rHttpOrigin.headers.get("access-control-allow-origin") }},
    ftpReferer: {{ status: rFtpReferer.status }},
    optForeignPagesAcao: rOptForeignPages.headers.get("access-control-allow-origin"),
    optHttpAcao: rOptHttp.headers.get("access-control-allow-origin"),
    ownPagesRoot: {{ status: rOwnPagesRoot.status, acao: rOwnPagesRoot.headers.get("access-control-allow-origin") }},
    ownPagesPreview: {{ status: rOwnPagesPreview.status, acao: rOwnPagesPreview.headers.get("access-control-allow-origin") }},
  }};
}}

// 2. Turnstile hostname rejects foreign *.pages.dev and accepts scoped tenant pages.dev; non-string tokens fail with 0 fetch
{{
  const kv = makeKv();
  const env = {{
    DOMAIN: "{domain}",
    TURNSTILE_SECRET_KEY: "0x4AAA_SEC",
    {kv_binding}: kv,
  }};
  siteverifyCalls = 0;
  const rArr = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "POST",
      headers: {{ "content-type": "application/json", origin: "https://{domain}" }},
      body: JSON.stringify({{ email: "ns1@realco.io", cf_turnstile_response: ["tok"] }}),
    }}),
    env,
  }});
  const rObj = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "POST",
      headers: {{ "content-type": "application/json", origin: "https://{domain}" }},
      body: JSON.stringify({{ email: "ns2@realco.io", cf_turnstile_response: {{ tok: 1 }} }}),
    }}),
    env,
  }});
  const rNum = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "POST",
      headers: {{ "content-type": "application/json", origin: "https://{domain}" }},
      body: JSON.stringify({{ email: "ns3@realco.io", cf_turnstile_response: 12345 }}),
    }}),
    env,
  }});
  const callsAfterNonStrings = siteverifyCalls;

  tsVerifyHost = "attacker-spammer-999.pages.dev";
  const rForeignTs = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "POST",
      headers: {{ "content-type": "application/json", origin: "https://{domain}" }},
      body: JSON.stringify({{ email: "tsf@realco.io", cf_turnstile_response: "tok_foreign" }}),
    }}),
    env,
  }});

  tsVerifyHost = "branch-1.{prop_id}.pages.dev";
  const rScopedTs = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture", {{
      method: "POST",
      headers: {{ "content-type": "application/json", origin: "https://{domain}" }},
      body: JSON.stringify({{ email: "tss@realco.io", cf_turnstile_response: "tok_scoped" }}),
    }}),
    env,
  }});
  out.turnstileHardening = {{
    arrStatus: rArr.status,
    objStatus: rObj.status,
    numStatus: rNum.status,
    callsAfterNonStrings,
    foreignPagesTsStatus: rForeignTs.status,
    scopedPagesTsStatus: rScopedTs.status,
  }};
}}

// 3. POST ?fulfill=1 guards: synthetic probe, cross-origin, and per-IP rate limit
{{
  stripeCalls = 0;
  const kv = makeKv();
  const env = {{
    DOMAIN: "{domain}",
    STRIPE_SECRET_KEY: "sk_live_mock",
    {kv_binding}: kv,
  }};
  const rSynthFulfill = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture?fulfill=1", {{
      method: "POST",
      headers: {{ "content-type": "application/json", "x-pseofactory-test": "1" }},
      body: JSON.stringify({{ session_id: "cs_live_probe_1", lead_id: "lead_{prop_id}_probe", synthetic_test: true }}),
    }}),
    env,
  }});
  const callsAfterSynth = stripeCalls;

  const rCrossFulfill = await mod.onRequestPost({{
    request: new Request("https://{domain}/api/lead-capture?fulfill=1", {{
      method: "POST",
      headers: {{ "content-type": "application/json", origin: "https://evil.example" }},
      body: JSON.stringify({{ session_id: "cs_live_cross_1", lead_id: "lead_{prop_id}_cross" }}),
    }}),
    env,
  }});
  const callsAfterCross = stripeCalls;

  const fulfillRlStatuses = [];
  let callsBeforeFourth = 0;
  for (let i = 1; i <= 4; i++) {{
    if (i === 4) callsBeforeFourth = stripeCalls;
    const rf = await mod.onRequestPost({{
      request: new Request("https://{domain}/api/lead-capture?fulfill=1", {{
        method: "POST",
        headers: {{ "content-type": "application/json", origin: "https://{domain}", "cf-connecting-ip": "198.51.100.77" }},
        body: JSON.stringify({{ session_id: "cs_live_unpaid_" + i, lead_id: "lead_{prop_id}_rl_" + i }}),
      }}),
      env,
    }});
    fulfillRlStatuses.push(rf.status);
  }}
  out.fulfillGuard = {{
    synthStatus: rSynthFulfill.status,
    synthBody: await rSynthFulfill.json(),
    callsAfterSynth,
    crossStatus: rCrossFulfill.status,
    callsAfterCross,
    fulfillRlStatuses,
    stripeCallsOnFourth: stripeCalls - callsBeforeFourth,
  }};
}}

// 4. Missing IP headers fallback to 'unknown' rate-limit bucket
{{
  const kv = makeKv();
  const env = {{ DOMAIN: "{domain}", {kv_binding}: kv }};
  const unknownIpStatuses = [];
  for (let i = 1; i <= 4; i++) {{
    const r = await mod.onRequestPost({{
      request: new Request("https://{domain}/api/lead-capture", {{
        method: "POST",
        headers: {{ "content-type": "application/json", origin: "https://{domain}" }},
        body: JSON.stringify({{ email: `noip${{i}}@realco.io`, tool_slug: "{default_slug}" }}),
      }}),
      env,
    }});
    unknownIpStatuses.push(r.status);
  }}
  out.unknownIpStatuses = unknownIpStatuses;
}}

console.log(JSON.stringify(out));
""",
        encoding="utf-8",
    )
    proc = subprocess.run(["node", str(runner)], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, f"{prop_id} adv node error: {proc.stderr}"
    res = json.loads(proc.stdout.strip().splitlines()[-1])

    oh = res["originHardening"]
    assert oh["foreignPages"]["status"] == 403
    assert oh["foreignPages"]["acao"] == f"https://{domain}"
    assert oh["evilSuffixPages"]["status"] == 403
    assert oh["httpOrigin"]["status"] == 403
    assert oh["httpOrigin"]["acao"] == f"https://{domain}"
    assert oh["ftpReferer"]["status"] == 403
    assert oh["optForeignPagesAcao"] == f"https://{domain}"
    assert oh["optHttpAcao"] == f"https://{domain}"
    assert oh["ownPagesRoot"]["status"] == 200
    assert oh["ownPagesRoot"]["acao"] == f"https://{prop_id}.pages.dev"
    assert oh["ownPagesPreview"]["status"] == 200
    assert oh["ownPagesPreview"]["acao"] == f"https://abc123.{prop_id}.pages.dev"

    th = res["turnstileHardening"]
    assert th["arrStatus"] == 403
    assert th["objStatus"] == 403
    assert th["numStatus"] == 403
    assert th["callsAfterNonStrings"] == 0
    assert th["foreignPagesTsStatus"] == 403
    assert th["scopedPagesTsStatus"] == 200

    fg = res["fulfillGuard"]
    assert fg["synthStatus"] == 402
    assert fg["synthBody"]["synthetic_test"] is True
    assert fg["callsAfterSynth"] == 0
    assert fg["crossStatus"] == 403
    assert fg["callsAfterCross"] == 0
    assert fg["fulfillRlStatuses"] == [402, 402, 402, 429]
    assert fg["stripeCallsOnFourth"] == 0

    assert res["unknownIpStatuses"] == [200, 200, 200, 429]


def test_frontend_footer_and_runtime_sync_turnstile_coordination_dom(tmp_path: Path) -> None:
    """
    Runs BOTH #porcelain-footer-lead-handler AND pseo-runtime-sync together in a Node.js DOM VM
    for both footer form IDs:
    - Case A: footer form has id="lead-capture-form" (158/168 ProfitHelm pages) + runtime sync loaded
    - Case B: footer form has id="footer-lead-capture-form" + runtime sync loaded
    Verifies:
    1. /api/lead-capture?config=1 is fetched eagerly once on load (shared promise).
    2. window.turnstile.render is called AT MOST ONCE per slot (zero duplicate widgets).
    3. Fast submit before Turnstile token arrives waits for token instead of firing an empty-token POST.
    4. Case A writes status into #footer-lead-status without injecting a duplicate #lead-capture-status,
       and renders a clickable &format=html worksheet link with target="_blank" rel="noopener noreferrer".
    5. Case B renders a safe &format=html worksheet link with target="_blank" rel="noopener noreferrer"
       and ignores unsafe javascript: / //evil playbook_url values.
    """
    import re
    from pseofactory.visual_primitives import render_runtime_synchronizer_js

    profile = get_porcelain_tenant_profile("profithelm")
    footer_lead_id_html = render_porcelain_footer(
        profile, page_slug="homepage", has_main_lead_form=False, has_quote_intake_step=True
    )
    footer_alt_id_html = render_porcelain_footer(
        profile, page_slug="homepage", has_main_lead_form=True, has_quote_intake_step=False
    )

    m_a = re.search(r'<script id="porcelain-footer-lead-handler">([\s\S]*?)</script>', footer_lead_id_html)
    m_b = re.search(r'<script id="porcelain-footer-lead-handler">([\s\S]*?)</script>', footer_alt_id_html)
    assert m_a and m_b
    rt_js = render_runtime_synchronizer_js()

    runner = tmp_path / "dom_coord.mjs"
    runner.write_text(
        f"""
import vm from "node:vm";

const FOOTER_SCRIPT_A = {json.dumps(m_a.group(1))};
const FOOTER_SCRIPT_B = {json.dumps(m_b.group(1))};
const RUNTIME_SYNC_JS = {json.dumps(rt_js)};

class MiniEl {{
  constructor(tag, attrs = {{}}) {{
    this.tagName = tag.toUpperCase();
    this.attrs = {{ ...attrs }};
    this.id = attrs.id || "";
    this.className = attrs.class || "";
    this.name = attrs.name || "";
    this.type = attrs.type || "";
    this.value = attrs.value || "";
    this.href = attrs.href || "";
    this.target = "";
    this.rel = "";
    this.dataset = {{}};
    this.style = {{}};
    this.children = [];
    this.parentNode = null;
    this._textContent = "";
    this._listeners = {{}};
    this.classList = {{
      contains: (c) => String(this.className || "").split(/\\s+/).includes(c),
      add: (c) => {{ if (!this.classList.contains(c)) this.className = (this.className + " " + c).trim(); }},
      remove: (c) => {{ this.className = String(this.className || "").split(/\\s+/).filter((x) => x !== c).join(" "); }},
    }};
  }}
  get textContent() {{ return this._textContent; }}
  set textContent(v) {{ this._textContent = String(v); this.children = []; }}
  setAttribute(k, v) {{
    this.attrs[k] = String(v);
    if (k === "id") this.id = String(v);
    if (k === "class") this.className = String(v);
  }}
  getAttribute(k) {{
    if (k === "id") return this.id || null;
    if (k === "class") return this.className || null;
    return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null;
  }}
  removeAttribute(k) {{ delete this.attrs[k]; }}
  appendChild(child) {{
    child.parentNode = this;
    this.children.push(child);
    return child;
  }}
  removeChild(child) {{
    this.children = this.children.filter((c) => c !== child);
    child.parentNode = null;
  }}
  addEventListener(type, fn) {{
    if (!this._listeners[type]) this._listeners[type] = [];
    this._listeners[type].push(fn);
  }}
  focus() {{}}
  _matchesSingle(sel) {{
    const s = sel.trim();
    if (s.startsWith("#")) return this.id === s.slice(1);
    if (s.startsWith(".")) return this.classList.contains(s.slice(1));
    const mAttr = s.match(/^([a-z]+)\\[([a-z-]+)="([^"]+)"\\]$/i);
    if (mAttr) {{
      const [, tag, attr, val] = mAttr;
      if (this.tagName !== tag.toUpperCase()) return false;
      return (attr === "type" ? this.type : attr === "name" ? this.name : this.getAttribute(attr)) === val;
    }}
    return this.tagName === s.toUpperCase();
  }}
  matches(selector) {{
    return selector.split(",").some((part) => this._matchesSingle(part));
  }}
  closest(selector) {{
    let cur = this;
    while (cur) {{
      if (cur.matches(selector)) return cur;
      cur = cur.parentNode;
    }}
    return null;
  }}
  _walk(out = []) {{
    for (const c of this.children) {{
      out.push(c);
      c._walk(out);
    }}
    return out;
  }}
  querySelectorAll(selector) {{
    return this._walk().filter((el) => el.matches(selector));
  }}
  querySelector(selector) {{
    return this.querySelectorAll(selector)[0] || null;
  }}
}}

async function runCase(formId, footerScript, playbookUrlToReturn) {{
  const root = new MiniEl("html");
  const head = root.appendChild(new MiniEl("head"));
  const body = root.appendChild(new MiniEl("body"));
  const form = body.appendChild(new MiniEl("form", {{ id: formId, class: "footer-lead-form newsletter-form" }}));
  const emailInp = form.appendChild(new MiniEl("input", {{ id: "footer-lead-email", type: "email", name: "email", value: "human@realcorp.io" }}));
  form.appendChild(new MiniEl("input", {{ type: "hidden", name: "tool_slug", value: "homepage" }}));
  form.appendChild(new MiniEl("input", {{ type: "text", name: "company_website", value: "" }}));
  const slot = form.appendChild(new MiniEl("div", {{ class: "cf-turnstile-slot", "data-turnstile-slot": "1" }}));
  form.appendChild(new MiniEl("button", {{ type: "submit" }}));
  const footerStatus = form.appendChild(new MiniEl("div", {{ id: "footer-lead-status", class: "footer-lead-status" }}));

  const docListeners = {{}};
  const doc = {{
    readyState: "complete",
    head,
    body,
    documentElement: root,
    createElement: (t) => new MiniEl(t),
    getElementById: (id) => root._walk().find((el) => el.id === id) || null,
    querySelector: (sel) => root.querySelector(sel),
    querySelectorAll: (sel) => root.querySelectorAll(sel),
    addEventListener: (type, fn, capture = false) => {{
      const k = type + (capture ? ":cap" : ":bub");
      if (!docListeners[k]) docListeners[k] = [];
      docListeners[k].push(fn);
    }},
  }};

  let configFetches = 0;
  let postPayloads = [];
  let renderCount = 0;
  let pendingTsCallback = null;

  const win = {{
    location: {{ origin: "https://profithelm.com", hostname: "profithelm.com", pathname: "/", search: "", href: "https://profithelm.com/" }},
    history: {{ replaceState() {{}} }},
    localStorage: {{ getItem() {{ return null; }}, setItem() {{}} }},
    navigator: {{ sendBeacon() {{ return true; }} }},
    addEventListener() {{}},
    URLSearchParams,
    turnstile: {{
      render(el, opts) {{
        renderCount += 1;
        pendingTsCallback = opts.callback;
        return "w_" + renderCount;
      }},
      reset() {{}},
    }},
    fetch(url, opts = {{}}) {{
      const u = String(url);
      if (u.includes("config=1")) {{
        configFetches += 1;
        return new Promise((resolve) => setTimeout(() => resolve({{
          ok: true,
          status: 200,
          json: async () => ({{ ok: true, turnstile_enabled: true, turnstile_site_key: "0x4AAA_TEST" }}),
        }}), 20));
      }}
      if (u.includes("/api/lead-capture") && opts.method === "POST") {{
        postPayloads.push(JSON.parse(opts.body));
        return Promise.resolve({{
          ok: true,
          status: 200,
          json: async () => ({{
            ok: true,
            status: "playbook_subscribed",
            lead_id: "lead_profithelm_dom_1",
            playbook_url: playbookUrlToReturn,
            checkout_url: "/api/lead-capture?checkout=1&lead_id=lead_profithelm_dom_1",
            redirect_url: "/r/ipx1031?lead_id=lead_profithelm_dom_1",
          }}),
        }});
      }}
      return Promise.resolve({{ ok: true, status: 200, json: async () => ({{ ok: true }}) }});
    }},
  }};
  win.window = win;
  win.document = doc;

  const ctx = vm.createContext({{
    window: win,
    document: doc,
    fetch: win.fetch,
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    URLSearchParams,
    Promise,
    Date,
    Math,
    JSON,
    console,
  }});

  // Execute in real page order: footer handler first, then runtime sync
  vm.runInContext(footerScript, ctx);
  vm.runInContext(RUNTIME_SYNC_JS, ctx);

  // Simulate user fast-submitting BEFORE config/Turnstile resolves!
  let stopped = false;
  const submitEv = {{
    target: form,
    preventDefault() {{}},
    stopImmediatePropagation() {{ stopped = true; }},
  }};
  for (const fn of docListeners["submit:cap"] || []) {{
    fn(submitEv);
    if (stopped) break;
  }}
  if (!stopped) {{
    for (const fn of form._listeners.submit || []) {{
      fn(submitEv);
    }}
  }}

  // Immediately after fast submit, zero POST should have fired yet (waiting on config + Turnstile!)
  const postsImmediatelyAfterFastSubmit = postPayloads.length;

  // Wait for config fetch + Turnstile render
  await new Promise((r) => setTimeout(r, 80));
  const postsBeforeToken = postPayloads.length;

  // Now Turnstile resolves its token callback
  if (typeof pendingTsCallback === "function") {{
    pendingTsCallback("ts_verified_token_xyz");
  }}
  await new Promise((r) => setTimeout(r, 220));

  const allLinks = footerStatus._walk().filter((el) => el.tagName === "A");
  const dupStatusEl = root._walk().find((el) => el.id === "lead-capture-status") || null;

  return {{
    formId,
    configFetches,
    renderCount,
    slotMountedAttr: slot.getAttribute("data-turnstile-mounted"),
    postsImmediatelyAfterFastSubmit,
    postsBeforeToken,
    postCountAfterToken: postPayloads.length,
    submittedToken: postPayloads[0] ? postPayloads[0].cf_turnstile_response : null,
    hasDuplicateLeadCaptureStatus: Boolean(dupStatusEl),
    footerStatusText: footerStatus.textContent,
    footerLinks: allLinks.map((a) => ({{ id: a.id, href: a.href, target: a.target, rel: a.rel, text: a.textContent }})),
  }};
}}

const caseA = await runCase("lead-capture-form", FOOTER_SCRIPT_A, "/api/lead-capture?playbook=1&lead_id=lead_profithelm_dom_1");
const caseB = await runCase("footer-lead-capture-form", FOOTER_SCRIPT_B, "/api/lead-capture?playbook=1&lead_id=lead_profithelm_dom_1");
const caseBUnsafe = await runCase("footer-lead-capture-form", FOOTER_SCRIPT_B, "javascript:alert(1)");
console.log(JSON.stringify({{ caseA, caseB, caseBUnsafe }}));
""",
        encoding="utf-8",
    )

    proc = subprocess.run(["node", str(runner)], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, f"DOM coordination test error: {proc.stderr}"
    out = json.loads(proc.stdout.strip().splitlines()[-1])

    # Case A: footer id="lead-capture-form" + pseo-runtime-sync
    ca = out["caseA"]
    assert ca["configFetches"] == 1
    assert ca["renderCount"] == 1, f"Expected turnstile.render once, got {ca['renderCount']}"
    assert ca["slotMountedAttr"] == "1"
    assert ca["postsImmediatelyAfterFastSubmit"] == 0
    assert ca["postsBeforeToken"] == 0
    assert ca["postCountAfterToken"] == 1
    assert ca["submittedToken"] == "ts_verified_token_xyz"
    assert ca["hasDuplicateLeadCaptureStatus"] is False
    pb_links_a = [a for a in ca["footerLinks"] if "playbook=1" in a["href"]]
    assert pb_links_a, f"Expected playbook link inside #footer-lead-status, got: {ca['footerLinks']}"
    assert any("format=html" in a["href"] and a["target"] == "_blank" and "noopener" in a["rel"] for a in pb_links_a)

    # Case B: footer id="footer-lead-capture-form" + pseo-runtime-sync
    cb = out["caseB"]
    assert cb["configFetches"] == 1
    assert cb["renderCount"] == 1, f"Expected turnstile.render once, got {cb['renderCount']}"
    assert cb["slotMountedAttr"] == "1"
    assert cb["postsImmediatelyAfterFastSubmit"] == 0
    assert cb["postsBeforeToken"] == 0
    assert cb["postCountAfterToken"] == 1
    assert cb["submittedToken"] == "ts_verified_token_xyz"
    assert len(cb["footerLinks"]) == 1
    ws_link = cb["footerLinks"][0]
    assert ws_link["href"] == "/api/lead-capture?playbook=1&lead_id=lead_profithelm_dom_1&format=html"
    assert ws_link["target"] == "_blank"
    assert ws_link["rel"] == "noopener noreferrer"

    # Case B unsafe playbook_url must be rejected (zero rendered anchor links)
    assert out["caseBUnsafe"]["footerLinks"] == []

