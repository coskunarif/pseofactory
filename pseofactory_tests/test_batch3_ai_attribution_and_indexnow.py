"""
Batch 3B verification suite:
1. 10-domain AI referrer attribution, #:~:text= detection, and filtered one-shot ai_landing beacon.
2. 'How did you find this calculator?' self-attribution on lead/partner forms + edge KV persistence.
3. 7d/28d intent-segmented AIO Observatory + SQLite ALTER TABLE migration + CSV join helper.
4. Branded vs non-branded GSC split + Bing Webmaster AI Performance CSV ingest.
5. Post-deploy IndexNow sitemap diff + Retry-After backoff ledger + CI workflow guard.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

import yaml

from pseofactory.aio_observatory import (
    AIOObservatory,
    ROLLING_WINDOW_DAYS,
    classify_query_intent,
    join_external_ai_telemetry,
    load_watchlist,
)
from pseofactory.edge import (
    generate_edge_lead_capture_function,
    generate_edge_telemetry_function,
)
from pseofactory.indexer import (
    PushIndexer,
    push_changed_urls_to_indexnow_post_deploy,
)
from pseofactory.seo_growth_loops import (
    compute_branded_vs_nonbranded_gsc_split,
    ingest_bing_ai_performance_csv,
)
from pseofactory.visual_primitives import (
    normalize_html_visual_primitives,
    render_runtime_synchronizer_js,
)


def _run_node_runtime_attribution_probe(
    referrer: str = "",
    href: str = "https://profithelm.com/tools/section-179-calculator/",
    search: str = "",
    hash_str: str = "",
    nav_entry_name: str = "",
    with_partner_form: bool = False,
    click_pill: str = "",
) -> Dict[str, Any]:
    runtime_js = render_runtime_synchronizer_js("profithelm")
    driver = r"""
const vm = require("vm");
const fs = require("fs");
const cfg = JSON.parse(process.env.PROBE_CFG || "{}");
const runtimeCode = fs.readFileSync(0, "utf8");

const docListeners = { click: [], submit: [], input: [], change: [], DOMContentLoaded: [] };
const allElements = [];
const fetchCalls = [];
const beaconPayloads = [];

class El {
  constructor(tag, attrs = {}, text = "") {
    this.tagName = String(tag || "DIV").toUpperCase();
    this.attributes = {};
    this.style = { cssText: "", display: "" };
    this.children = [];
    this.parentElement = null;
    this.textContent = text;
    this.value = attrs.value || "";
    this.type = attrs.type || "";
    this.name = attrs.name || "";
    this.id = attrs.id || "";
    this._listeners = {};
    const cls = new Set(String(attrs.class || "").split(/\s+/).filter(Boolean));
    const self = this;
    this.classList = {
      add(c) { cls.add(c); self.attributes.class = Array.from(cls).join(" "); },
      remove(c) { cls.delete(c); self.attributes.class = Array.from(cls).join(" "); },
      contains(c) { return cls.has(c); }
    };
    for (const [k, v] of Object.entries(attrs)) {
      this.attributes[k] = String(v);
      if (k === "id") this.id = String(v);
      if (k === "name") this.name = String(v);
    }
    allElements.push(this);
  }
  getAttribute(k) {
    if (k === "id") return this.id || null;
    if (k === "name") return this.name || null;
    return Object.prototype.hasOwnProperty.call(this.attributes, k) ? this.attributes[k] : null;
  }
  setAttribute(k, v) {
    this.attributes[k] = String(v);
    if (k === "id") this.id = String(v);
    if (k === "name") this.name = String(v);
    if (k === "value") this.value = String(v);
  }
  hasAttribute(k) { return this.getAttribute(k) !== null; }
  removeAttribute(k) { delete this.attributes[k]; }
  appendChild(ch) {
    ch.parentElement = this;
    this.children.push(ch);
    if (!allElements.includes(ch)) allElements.push(ch);
    return ch;
  }
  insertBefore(ch, _ref) { return this.appendChild(ch); }
  _matchesSingle(sel) {
    if (sel.startsWith("#")) return this.id === sel.slice(1);
    if (sel.startsWith(".")) return this.classList.contains(sel.slice(1));
    const am = sel.match(/^([a-zA-Z0-9_-]*)\[([a-zA-Z0-9_-]+)(?:([\^$*]?=)["']?([^"'\]]*)["']?)?\]$/);
    if (am) {
      const [, t, a, op, v] = am;
      if (t && this.tagName !== t.toUpperCase()) return false;
      const cur = this.getAttribute(a);
      if (cur === null) return false;
      if (!op) return true;
      if (op === "=") return cur === v;
      if (op === "*=") return cur.includes(v);
      if (op === "^=") return cur.startsWith(v);
      return false;
    }
    return this.tagName === sel.toUpperCase();
  }
  matchesSelector(sel) {
    return String(sel).split(",").map(s => s.trim()).filter(Boolean).some(p => this._matchesSingle(p));
  }
  closest(sel) {
    let cur = this;
    while (cur) {
      if (cur.matchesSelector(sel)) return cur;
      cur = cur.parentElement;
    }
    return null;
  }
  querySelectorAll(sel) {
    const out = [];
    const walk = (n) => {
      for (const ch of n.children || []) {
        if (ch.matchesSelector(sel)) out.push(ch);
        walk(ch);
      }
    };
    walk(this);
    return out;
  }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  dispatchEvent(ev) {
    ev.target = this;
    for (const fn of (docListeners[ev.type] || [])) fn(ev);
    return !ev.defaultPrevented;
  }
  click() {
    this.dispatchEvent({ type: "click", preventDefault() {}, stopImmediatePropagation() {} });
  }
}

const body = new El("BODY");
const main = body.appendChild(new El("MAIN"));
if (cfg.with_partner_form) {
  const form = main.appendChild(new El("FORM", { id: "partner-registration-form", class: "partner-registration-form", action: "/api/lead-capture" }));
  form.appendChild(new El("INPUT", { type: "text", name: "firm_name", value: "Apex Tax Advisory" }));
  form.appendChild(new El("INPUT", { type: "email", name: "email", value: "advisor@apextax.example" }));
  form.appendChild(new El("SELECT", { name: "state", value: "CA" }));
  form.appendChild(new El("DIV", { class: "cf-turnstile-slot" }));
  form.appendChild(new El("BUTTON", { type: "submit" }, "Apply"));
}

const documentObj = {
  readyState: "complete",
  referrer: cfg.referrer || "",
  body,
  getElementById(id) { return allElements.find(e => e.id === id) || null; },
  querySelector(sel) { return body.querySelector(sel); },
  querySelectorAll(sel) { return body.querySelectorAll(sel); },
  createElement(tag) { return new El(tag); },
  addEventListener(type, fn) {
    if (!docListeners[type]) docListeners[type] = [];
    docListeners[type].push(fn);
  }
};

const parsedUrl = new URL(cfg.href || "https://profithelm.com/tools/section-179-calculator/");
const storage = {};
const windowObj = {
  __PSEO_SYNTHETIC_TEST__: true,
  addEventListener() {},
  localStorage: {
    getItem(k) { return Object.prototype.hasOwnProperty.call(storage, k) ? storage[k] : null; },
    setItem(k, v) { storage[k] = String(v); }
  },
  location: {
    origin: parsedUrl.origin,
    hostname: parsedUrl.hostname,
    pathname: parsedUrl.pathname,
    search: cfg.search !== undefined ? cfg.search : parsedUrl.search,
    hash: cfg.hash_str !== undefined ? cfg.hash_str : parsedUrl.hash,
    href: cfg.href || parsedUrl.href,
  },
  history: { replaceState() {} },
  navigator: {
    sendBeacon(url, payload) { beaconPayloads.push({ url, payload: String(payload) }); return true; }
  },
  fetch(url, opts = {}) {
    fetchCalls.push({ url: String(url), method: opts.method || "GET", body: opts.body || null, headers: opts.headers || {} });
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ ok: true, lead_id: "lead_1", firm_name: "Apex Tax Advisory" }) });
  },
  Event: class { constructor(t) { this.type = t; } },
  URLSearchParams,
  Blob: function(parts) { this.parts = parts; },
  setTimeout(fn) { fn(); return 1; },
  clearTimeout() {},
  setInterval() { return 1; },
  clearInterval() {}
};
windowObj.window = windowObj;
windowObj.document = documentObj;

const perfObj = cfg.nav_entry_name
  ? { getEntriesByType(t) { return t === "navigation" ? [{ name: cfg.nav_entry_name }] : []; } }
  : undefined;

const ctx = vm.createContext({
  window: windowObj,
  document: documentObj,
  navigator: windowObj.navigator,
  location: windowObj.location,
  history: windowObj.history,
  performance: perfObj,
  Event: windowObj.Event,
  URLSearchParams,
  Blob: windowObj.Blob,
  setTimeout: windowObj.setTimeout,
  clearTimeout: windowObj.clearTimeout,
  setInterval: windowObj.setInterval,
  clearInterval: windowObj.clearInterval,
  Math, JSON, Object, Array, String, Number, Boolean, RegExp, Date, Promise, parseFloat, parseInt, isNaN, encodeURIComponent, decodeURIComponent
});

vm.runInContext(runtimeCode, ctx);

let submittedPayload = null;
let pillCount = 0;
let attrLabel = "";
if (cfg.with_partner_form) {
  const form = documentObj.getElementById("partner-registration-form");
  pillCount = form.querySelectorAll("[data-attribution-pill]").length;
  const lbl = form.querySelector("label");
  attrLabel = lbl ? lbl.textContent : "";
  if (cfg.click_pill) {
    const pill = form.querySelectorAll("[data-attribution-pill]").find(p => p.getAttribute("data-attribution-pill") === cfg.click_pill);
    if (pill) pill.click();
  }
  form.dispatchEvent({ type: "submit", preventDefault() {}, stopImmediatePropagation() {} });
  const leadCall = fetchCalls.find(c => c.url === "/api/lead-capture" && c.method === "POST");
  if (leadCall && leadCall.body) submittedPayload = JSON.parse(leadCall.body);
}

const aiBeacons = fetchCalls
  .filter(c => c.url === "/api/telemetry" && c.body)
  .map(c => JSON.parse(c.body))
  .filter(p => p.event === "ai_landing");

process.stdout.write(JSON.stringify({
  traffic_source: windowObj.__pseoResolveTrafficSource(),
  text_fragment: windowObj.__pseoDetectTextFragmentReferral(),
  ai_beacons: aiBeacons,
  telemetry_call_count: fetchCalls.filter(c => c.url === "/api/telemetry").length,
  pill_count: pillCount,
  attr_label: attrLabel,
  submitted_payload: submittedPayload
}));
"""
    proc = subprocess.run(
        ["node", "-e", driver],
        input=runtime_js,
        text=True,
        capture_output=True,
        env={
            **dict(__import__("os").environ),
            "PROBE_CFG": json.dumps(
                {
                    "referrer": referrer,
                    "href": href,
                    "search": search,
                    "hash_str": hash_str,
                    "nav_entry_name": nav_entry_name,
                    "with_partner_form": with_partner_form,
                    "click_pill": click_pill,
                }
            ),
        },
        check=True,
    )
    return json.loads(proc.stdout)


def test_ten_domain_ai_referrers_utm_overrides_and_filtered_ai_landing_beacon():
    expected_domains = [
        ("https://chatgpt.com/", "chatgpt_search"),
        ("https://chat.openai.com/c/123", "chatgpt_search"),
        ("https://www.perplexity.ai/search/foo", "perplexity_ai"),
        ("https://claude.ai/chat/abc", "claude_ai"),
        ("https://gemini.google.com/app", "gemini_ai"),
        ("https://copilot.microsoft.com/chats/123", "copilot_ai"),
        ("https://copilot.com/", "copilot_ai"),
        ("https://grok.x.ai/", "grok_ai"),
        ("https://search.brave.com/search?q=tax", "brave_search_ai"),
        ("https://chat.deepseek.com/", "deepseek_ai"),
    ]
    for ref_url, expected_src in expected_domains:
        res = _run_node_runtime_attribution_probe(referrer=ref_url)
        assert res["traffic_source"] == expected_src, (ref_url, res)
        assert len(res["ai_beacons"]) == 1, (ref_url, res)
        assert res["ai_beacons"][0]["traffic_source"] == expected_src
        assert res["ai_beacons"][0]["text_fragment_referral"] is False

    # utm_source overrides even with empty or generic Google referrer
    for utm_val, expected_src in [
        ("chatgpt", "chatgpt_search"),
        ("perplexity", "perplexity_ai"),
        ("claude", "claude_ai"),
        ("gemini", "gemini_ai"),
        ("copilot", "copilot_ai"),
        ("grok", "grok_ai"),
        ("brave", "brave_search_ai"),
        ("deepseek", "deepseek_ai"),
        ("google_ai_mode", "google_ai_mode"),
    ]:
        res = _run_node_runtime_attribution_probe(
            referrer="https://www.google.com/",
            href=f"https://profithelm.com/tools/section-179-calculator/?utm_source={utm_val}",
            search=f"?utm_source={utm_val}",
        )
        assert res["traffic_source"] == expected_src
        assert len(res["ai_beacons"]) == 1

    # #:~:text= detected via performance.getEntriesByType('navigation')[0].name even when stripped from location.href
    frag_res = _run_node_runtime_attribution_probe(
        referrer="https://www.google.com/",
        href="https://profithelm.com/tools/section-179-calculator/",
        nav_entry_name="https://profithelm.com/tools/section-179-calculator/#:~:text=Section%20179%20limit",
    )
    assert frag_res["text_fragment"] is True
    assert frag_res["traffic_source"] == "google_organic"
    assert len(frag_res["ai_beacons"]) == 1
    assert frag_res["ai_beacons"][0]["text_fragment_referral"] is True

    # Non-AI human traffic (regular Google organic or direct) emits ZERO ai_landing beacons!
    for human_ref in ("https://www.google.com/", "https://www.linkedin.com/feed/", ""):
        human_res = _run_node_runtime_attribution_probe(referrer=human_ref)
        assert len(human_res["ai_beacons"]) == 0, (human_ref, human_res)
        assert human_res["telemetry_call_count"] == 0, (human_ref, human_res)


def test_edge_telemetry_persists_ai_landing_traffic_source_and_text_fragment_to_kv():
    telemetry_mjs = generate_edge_telemetry_function("profithelm")
    driver = r"""
import fs from "node:fs";
const code = fs.readFileSync(0, "utf8");
const b64 = Buffer.from(code, "utf8").toString("base64");
(async () => {
  const mod = await import("data:text/javascript;base64," + b64);
  const kvStore = new Map();
  const env = {
    TELEMETRY_EXPORT_SECRET: "sec_123",
    PROFITHELM_TELEMETRY_KV: {
      async put(k, v, opts) { kvStore.set(k, { value: JSON.parse(v), metadata: opts && opts.metadata }); },
      async list() {
        return {
          keys: Array.from(kvStore.entries()).map(([name, rec]) => ({ name, metadata: rec.metadata })),
          list_complete: true,
          cursor: null
        };
      }
    }
  };
  const postReq = new Request("https://profithelm.com/api/telemetry", {
    method: "POST",
    headers: { "Content-Type": "application/json", "User-Agent": "Mozilla/5.0" },
    body: JSON.stringify({
      event: "ai_landing",
      event_type: "ai_landing",
      tool_slug: "section-179-calculator",
      path: "/tools/section-179-calculator/",
      traffic_source: "perplexity_ai",
      text_fragment_referral: true
    })
  });
  const postResp = await mod.onRequestPost({ request: postReq, env });
  const postJson = await postResp.json();
  const getReq = new Request("https://profithelm.com/api/telemetry", {
    method: "GET",
    headers: { "Authorization": "Bearer sec_123" }
  });
  const getResp = await mod.onRequestGet({ request: getReq, env });
  const getJson = await getResp.json();
  process.stdout.write(JSON.stringify({ postJson, getJson, kvSize: kvStore.size }));
})();
"""
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", driver],
        input=telemetry_mjs,
        text=True,
        capture_output=True,
        check=True,
    )
    out = json.loads(proc.stdout)
    assert out["kvSize"] == 1
    assert out["postJson"]["persisted"] is True
    assert out["postJson"]["traffic_source"] == "perplexity_ai"
    assert out["postJson"]["text_fragment_referral"] is True
    ev = out["getJson"]["events"][0]
    assert ev["event"] == "ai_landing"
    assert ev["traffic_source"] == "perplexity_ai"
    assert ev["text_fragment_referral"] is True


def test_self_attribution_form_field_and_edge_lead_capture_persistence():
    # 1. Compile-time HTML injection onto partner/lead forms (idempotent, leaves calculator forms untouched)
    sample_html = """<!doctype html><html><head><title>Partners</title><link rel="canonical" href="https://profithelm.com/partners/"></head><body>
    <main>
      <form id="partner-registration-form" action="/api/lead-capture" method="post">
        <input type="text" name="firm_name" required>
        <input type="email" name="email" required>
        <div class="cf-turnstile-slot" data-turnstile-slot="1"></div>
        <button type="submit" class="touch-target">Submit</button>
      </form>
      <form id="calc-form" class="calculator-form">
        <input type="number" id="field-gross_income" value="100000" min="0" max="1000000">
      </form>
    </main></body></html>"""
    norm_html, actions = normalize_html_visual_primitives(sample_html, is_tenant_porcelain=True)
    assert "self_attribution_field" in actions
    assert 'name="attribution_source"' in norm_html
    assert "How did you find this calculator?" in norm_html
    for pill in ("Google Search", "ChatGPT / AI", "YouTube", "Reddit", "Referral / Other"):
        assert f'data-attribution-pill="{pill}"' in norm_html
    # Idempotent on second pass (check HTML markup excluding inline runtime <script>)
    import re as _re
    norm_html_2, actions_2 = normalize_html_visual_primitives(norm_html, is_tenant_porcelain=True)
    assert "self_attribution_field" not in actions_2
    body_no_scripts = _re.sub(r"<script\b[^>]*>[\s\S]*?</script>", "", norm_html_2, flags=_re.IGNORECASE)
    assert body_no_scripts.count('name="attribution_source"') == 1
    calc_form_m = _re.search(r'<form\b[^>]*id="calc-form"[^>]*>[\s\S]*?</form>', body_no_scripts)
    assert calc_form_m and 'name="attribution_source"' not in calc_form_m.group(0)

    # 2. Runtime Node VM pill click + form submit carries attribution_source
    rt_res = _run_node_runtime_attribution_probe(
        referrer="https://chatgpt.com/",
        with_partner_form=True,
        click_pill="ChatGPT / AI",
    )
    assert rt_res["pill_count"] == 5
    assert "How did you find this calculator?" in rt_res["attr_label"]
    assert rt_res["submitted_payload"]["attribution_source"] == "ChatGPT / AI"

    # 3. Edge /api/lead-capture persists attribution_source into KV across tenants
    for prop in ("profithelm", "prexvo", "gainhelm", "lienbond", "acme-dynamic"):
        lead_mjs = generate_edge_lead_capture_function(prop)
        driver = r"""
import fs from "node:fs";
const code = fs.readFileSync(0, "utf8");
const b64 = Buffer.from(code, "utf8").toString("base64");
(async () => {
  const mod = await import("data:text/javascript;base64," + b64);
  const kvStore = new Map();
  const env = {
    LEADS_KV: {
      async put(k, v, opts) { kvStore.set(k, { value: JSON.parse(v), metadata: opts && opts.metadata }); },
      async get(k) { const x = kvStore.get(k); return x ? JSON.stringify(x.value) : null; }
    }
  };
  const req = new Request("https://example.com/api/lead-capture", {
    method: "POST",
    headers: { "Content-Type": "application/json", "User-Agent": "Mozilla/5.0" },
    body: JSON.stringify({
      intent: "partner_registration",
      email: "partner@firm.io",
      firm_name: "Firm LLC",
      state: "CA",
      attribution_source: "ChatGPT / AI"
    })
  });
  const resp = await mod.onRequestPost({ request: req, env });
  const json = await resp.json();
  const stored = kvStore.get(json.lead_id);
  process.stdout.write(JSON.stringify({ status: resp.status, json, stored }));
})();
"""
        proc = subprocess.run(
            ["node", "--input-type=module", "-e", driver],
            input=lead_mjs,
            text=True,
            capture_output=True,
            check=True,
        )
        out = json.loads(proc.stdout)
        assert out["status"] == 200, (prop, out)
        assert out["json"]["attribution_source"] == "ChatGPT / AI"
        assert out["stored"]["value"]["attribution_source"] == "ChatGPT / AI"
        assert out["stored"]["metadata"]["attribution_source"] == "ChatGPT / AI"


def test_aio_observatory_7d_28d_intent_migration_and_csv_join(tmp_path):
    assert ROLLING_WINDOW_DAYS == (7, 28)
    assert classify_query_intent("how much does a cmmc level 2 assessment cost") == "factual"
    assert classify_query_intent("ibr vs rap student loan cost with income and dependents") == "multi_variable"
    assert classify_query_intent("cmmc 2.0 compliance cost calculator") == "tool_recommendation"

    # Legacy SQLite DB without intent column must auto-migrate via ALTER TABLE
    db_path = tmp_path / "legacy_aio.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE aio_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            tenant TEXT NOT NULL,
            query TEXT NOT NULL,
            sampled_at TEXT NOT NULL,
            found INTEGER,
            answer TEXT,
            citations TEXT,
            provider TEXT,
            cost_usd REAL,
            error TEXT
        )
        """
    )
    now = datetime.now(timezone.utc)
    conn.execute(
        "INSERT INTO aio_snapshots VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            "legacy_1",
            "gainhelm",
            "cmmc 2.0 compliance cost calculator",
            (now - timedelta(days=15)).isoformat(),
            1,
            "Costs $30,000.",
            json.dumps([{"url": "https://gainhelm.com/tools/cmmc-2-0-compliance-cost-calculator/", "title": "CMMC"}]),
            "fake",
            0.001,
            None,
        ),
    )
    conn.commit()
    conn.close()

    obs = AIOObservatory(db_path)
    cols = {r[1] for r in sqlite3.connect(str(db_path)).execute("PRAGMA table_info(aio_snapshots)")}
    assert "intent" in cols

    # Record a recent 7d factual query
    obs.record(
        "gainhelm",
        "what is cmmc level 2 assessment cost",
        {"found": True, "answer": "$30,000.", "citations": [{"url": "https://preveil.com/blog/cmmc", "title": "PreVeil"}]},
        at=now - timedelta(days=2),
    )

    rolling = obs.scoreboard_rolling()
    assert rolling["rolling_windows"] == [7, 28]
    # 7d sees only the 2-day-old factual sample; 28d sees both factual + 15-day-old migrated tool_recommendation sample
    assert rolling["window_7d"]["tenants"]["gainhelm"]["samples"] == 1
    assert "factual" in rolling["window_7d"]["tenants"]["gainhelm"]["intent_breakdown"]
    assert rolling["window_28d"]["tenants"]["gainhelm"]["samples"] == 2
    assert set(rolling["window_28d"]["tenants"]["gainhelm"]["intent_breakdown"].keys()) == {"factual", "tool_recommendation"}

    # Watchlist supports include_intent=True while preserving default 2-tuple behavior
    wl_default = load_watchlist(path=tmp_path / "missing.json")
    assert all(len(item) == 2 for item in wl_default)
    wl_intent = load_watchlist(path=tmp_path / "missing.json", include_intent=True)
    assert all(len(item) == 3 and item[2] in ("factual", "multi_variable", "tool_recommendation") for item in wl_intent)

    # CSV join helper matches canonical URLs across www/trailing-slash/query differences
    gsc_csv = tmp_path / "gsc_genai.csv"
    gsc_csv.write_text(
        "Page,Clicks,Impressions,Query\n"
        "https://www.gainhelm.com/tools/cmmc-2-0-compliance-cost-calculator/?utm_source=x,42,1200,cmmc calculator\n",
        encoding="utf-8",
    )
    bing_csv = tmp_path / "bing_ai.csv"
    bing_csv.write_text(
        "Cited Page,Citations,Clicks,Impressions,Grounding Queries\n"
        "https://gainhelm.com/tools/cmmc-2-0-compliance-cost-calculator,9,15,450,cmmc level 2 cost\n",
        encoding="utf-8",
    )
    snapshots = [
        {
            "query": "cmmc 2.0 compliance cost calculator",
            "citations": [{"url": "https://gainhelm.com/tools/cmmc-2-0-compliance-cost-calculator/"}],
        }
    ]
    joined = join_external_ai_telemetry(snapshots, gsc_genai_csv_path=gsc_csv, bing_ai_csv_path=bing_csv)
    assert joined["summary"]["matched_gsc_genai_snapshots"] == 1
    assert joined["summary"]["matched_bing_ai_snapshots"] == 1
    assert joined["joined_records"][0]["gsc_genai"][0]["clicks"] == 42.0
    assert joined["joined_records"][0]["bing_ai"][0]["citations"] == 9.0


def test_branded_vs_nonbranded_gsc_split_and_bing_ai_performance_ingest(tmp_path):
    gsc_rows = [
        {"date": "2026-11-01", "query": "profithelm section 179 calculator", "clicks": 40, "impressions": 200},
        {"date": "2026-11-01", "query": "section 179 deduction calculator", "clicks": 60, "impressions": 800},
        {"date": "2026-11-02", "query": "profithelm.com tax planner", "clicks": 80, "impressions": 300},
        {"date": "2026-11-02", "query": "ca ptet pass through tax calculator", "clicks": 20, "impressions": 700},
    ]
    split = compute_branded_vs_nonbranded_gsc_split(gsc_rows, ["profithelm", "profithelm.com"])
    assert split["branded_clicks"] == 120
    assert split["branded_impressions"] == 500
    assert split["nonbranded_clicks"] == 80
    assert split["nonbranded_impressions"] == 1500
    assert split["branded_click_share"] == 0.6
    assert split["nonbranded_click_share"] == 0.4
    assert split["branded_impression_share"] == 0.25
    assert split["nonbranded_impression_share"] == 0.75
    assert split["trend"]["has_chronological_trend"] is True
    assert split["trend"]["direction"] == "branded_growing"
    assert len(split["daily_series"]) == 2

    bing_csv = tmp_path / "bing_topic_portfolio.csv"
    bing_csv.write_text(
        "Cited Page,Topic,Grounding Queries,Citations,Clicks,Impressions,Month\n"
        "https://www.profithelm.com/tools/section-179-calculator/,Section 179,section 179 limit | bonus depreciation,12,28,900,2026-11\n"
        "/tools/california-ptet-calculator/,CA PTET,california ptet election,5,10,300,2026-11\n"
        "https://otherdomain.com/ignore,Ignore,foo,99,99,99,2026-11\n",
        encoding="utf-8",
    )
    parsed = ingest_bing_ai_performance_csv(bing_csv, "profithelm.com")
    assert parsed["rows_parsed"] == 2
    assert parsed["skipped_foreign_domain"] == 1
    assert parsed["total_citations"] == 17
    assert parsed["total_clicks"] == 38
    assert parsed["total_impressions"] == 1200
    assert len(parsed["unique_cited_urls"]) == 2
    assert parsed["unique_topics"] == ["CA PTET", "Section 179"]


def test_post_deploy_indexnow_helper_and_ci_workflow(tmp_path, monkeypatch):
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "tools" / "alpha").mkdir(parents=True)
    (dist_dir / "tools" / "beta").mkdir(parents=True)
    (dist_dir / "tools" / "alpha" / "index.html").write_text("<html><body>Alpha v1</body></html>", encoding="utf-8")
    (dist_dir / "tools" / "beta" / "index.html").write_text("<html><body>Beta v1</body></html>", encoding="utf-8")
    (dist_dir / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        "  <url><loc>https://profithelm.com/tools/alpha/</loc></url>\n"
        "  <url><loc>https://profithelm.com/tools/beta/</loc></url>\n"
        "</urlset>\n",
        encoding="utf-8",
    )

    class _FakeResp:
        def __init__(self, status=202):
            self.status = status

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    posted_batches = []

    def _fake_urlopen(req, timeout=10):
        posted_batches.append((req.full_url, json.loads(req.data.decode("utf-8"))))
        return _FakeResp(202)

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    # 1. First live run pushes both URLs
    res1 = push_changed_urls_to_indexnow_post_deploy(dist_dir, "profithelm.com", dry_run=False)
    assert res1["status"] == "DISPATCHED"
    assert res1["urls_submitted"] == 2
    assert res1["urls_dispatched"] == 2
    assert res1["urls_skipped_unchanged"] == 0
    assert len(posted_batches) == 2

    # 2. Second run with unchanged HTML skips both URLs cleanly (zero network calls)
    posted_batches.clear()
    res2 = push_changed_urls_to_indexnow_post_deploy(dist_dir, "profithelm.com", dry_run=False)
    assert res2["status"] == "IDEMPOTENT_NO_OP"
    assert res2["urls_dispatched"] == 0
    assert res2["urls_skipped_unchanged"] == 2
    assert posted_batches == []

    # 3. Updating beta HTML causes only beta to be pushed
    (dist_dir / "tools" / "beta" / "index.html").write_text("<html><body>Beta v2</body></html>", encoding="utf-8")
    res3 = push_changed_urls_to_indexnow_post_deploy(dist_dir, "profithelm.com", dry_run=True)
    assert res3["status"] == "SIMULATED"
    assert res3["urls_submitted"] == 2
    assert res3["urls_dispatched"] == 1
    assert res3["urls_skipped_unchanged"] == 1
    assert res3["changed_urls"] == ["https://profithelm.com/tools/beta/"]

    # 4. Retry-After backoff ledger suppresses push during active cooldown
    idx_helper = PushIndexer(
        domain="profithelm.com",
        base_dir=tmp_path,
        dist_dir=dist_dir,
        ledger_path=tmp_path / ".agy" / "index_push_ledger.json",
    )
    idx_helper._save_indexnow_backoff_state(
        {"host": "profithelm.com", "retry_after_until": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()}
    )
    res4 = push_changed_urls_to_indexnow_post_deploy(dist_dir, "profithelm.com", dry_run=False)
    assert res4["status"] == "RATE_LIMITED_COOLDOWN"
    assert res4["skipped"] is True
    assert res4["urls_dispatched"] == 0

    # 5. CI workflow contains opt-in non-blocking post-deploy-indexnow hook
    ci_path = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "ci.yml"
    ci_doc = yaml.safe_load(ci_path.read_text(encoding="utf-8"))
    assert "post-deploy-indexnow" in ci_doc["jobs"]
    job = ci_doc["jobs"]["post-deploy-indexnow"]
    assert job["continue-on-error"] is True
    assert "INDEXNOW_POST_DEPLOY_ENABLED == '1'" in job["if"]
    assert "refs/heads/main" in job["if"]
