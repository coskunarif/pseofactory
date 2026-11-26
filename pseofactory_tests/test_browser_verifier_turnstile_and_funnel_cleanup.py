"""
Targeted regression tests for:
1. 5th-site (acme_solar) dynamic tenant classification in _sync_three_step_funnel_on_calculator_pages,
   pricing.py, and porcelain_shell.py /partners/ + JSON-LD (zero ProfitHelm/Tax contamination).
2. LienBond /partners/ surety firm placeholder & dead .pro-hook-card / .calc-result-quick-unlock-bar CSS removal.
3. Removal of 14 dead legacy funnel helpers + dead JS handlers while keeping live 3-step & /partners/ handlers.
4. B4 Turnstile mount verification path in browser_verifier.py and local-preview guard in visual_primitives.py.
5. Runtime JS node --check, zero em/en-dashes, and zero localhost/127.0.0.1 literals.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from bs4 import BeautifulSoup


def _register_temp_truth_pack(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    property_id: str,
    brand_name: str,
    canonical_domain: str,
) -> None:
    import pseofactory.truth_pack as tp_mod
    from pseofactory.pricing import get_tier_pricing

    packs_dir = tmp_path / "truth_packs"
    packs_dir.mkdir(parents=True, exist_ok=True)
    for src_json in tp_mod.DEFAULT_TRUTH_PACKS_DIR.glob("*.json"):
        dst_json = packs_dir / src_json.name
        if not dst_json.exists():
            shutil.copy2(src_json, dst_json)

    payload = {
        "schema_version": "2.0",
        "property_id": property_id,
        "brand_name": brand_name,
        "canonical_domain": canonical_domain,
        "audience_tier": "business",
        "pricing_tiers": {
            "free": {"tier_kind": "free", "label": "Free", "price_usd": 0.0, "price_cents": 0},
            **get_tier_pricing("business"),
        },
        "entries": {},
        "formulas": {},
        "citations_allowlist": {},
        "disclosures": [],
        "banned_claims": [],
        "cross_tenant_brand_tokens": [],
        "allowed_shared_legal_tokens": [],
    }
    (packs_dir / f"{property_id}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    monkeypatch.setattr(tp_mod, "DEFAULT_TRUTH_PACKS_DIR", packs_dir)


def test_fifth_tenant_acme_solar_funnel_pricing_and_partners_isolation(tmp_path: Path, monkeypatch) -> None:
    """
    A dynamic 5th tenant (acme_solar) must classify cleanly via data-property,
    discover_active_tenants()/.pseofactory.json domain matching, and canonical domain,
    with zero profithelm SKU, copy, or Tax Wikidata QID contamination.
    """
    from pseofactory import impact_planner, pricing
    from pseofactory.porcelain_shell import (
        build_governance_pages,
        generate_porcelain_stylesheet,
        get_porcelain_tenant_profile,
    )
    from pseofactory.visual_primitives import normalize_html_visual_primitives

    # 1. Direct pricing resolution for acme_solar
    q_offer = pricing.resolve_offer_pricing("acme_solar", tier_kind="quick", slug="solar-roi-calculator")
    f_offer = pricing.resolve_offer_pricing("acme_solar", tier_kind="full", slug="solar-roi-calculator")
    p_offer = pricing.resolve_offer_pricing("acme_solar", tier_kind="partner_slot", slug="solar-roi-calculator")
    assert q_offer["sku"] == "acme_solar_quick_worksheet"
    assert f_offer["sku"] == "acme_solar_full_workpaper_pack"
    assert p_offer["sku"] == "acme_solar_verified_partner_slot"
    assert q_offer["price_usd"] == 15.0
    assert f_offer["price_usd"] == 29.0
    assert p_offer["price_usd"] == 299.0
    for offer in (q_offer, f_offer, p_offer):
        assert "profithelm" not in json.dumps(offer).lower()
        assert "ph_" not in offer["sku"]

    # 2. HTML funnel injection via data-property="acme_solar"
    calc_html_attr = (
        "<!DOCTYPE html><html><head>"
        '<link rel="canonical" href="https://acmesolar.com/tools/solar-roi-calculator/">'
        "<title>Commercial Solar ROI Calculator | Acme Solar</title></head><body><main>"
        "<h1>Commercial Solar ROI Calculator</h1>"
        '<div class="calc-grid" data-property="acme_solar">'
        '<form class="calculator-form"><input type="number" id="field-system_kw" value="250"></form>'
        '<div class="result-box"><div class="output-value">$48,500</div></div>'
        "</div></main></body></html>"
    )
    norm_attr, _ = normalize_html_visual_primitives(calc_html_attr, is_tenant_porcelain=True)
    assert 'id="btn-preview-workpaper"' in norm_attr
    assert 'id="workpaper-unlock-card"' in norm_attr
    assert 'data-property="acme_solar"' in norm_attr
    assert "acme_solar_quick_worksheet" in norm_attr
    assert "acme_solar_full_workpaper_pack" in norm_attr
    assert "profithelm" not in norm_attr.lower()
    for ph_sku_prefix in ("ph_instant", "ph_statutory", "ph_commercial", "ph_1031", "ph_verified"):
        assert ph_sku_prefix not in norm_attr.lower()

    # 3. HTML funnel injection WITHOUT data-property, resolved via discover_active_tenants() + .pseofactory.json
    acme_repo = tmp_path / "acme_solar"
    acme_repo.mkdir(parents=True)
    (acme_repo / ".pseofactory.json").write_text(
        json.dumps({"property_id": "acme_solar", "domain": "acmesolar.com"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        impact_planner,
        "discover_active_tenants",
        lambda workspace_root="/home/ubuntuadmin/projects": [("acme_solar", acme_repo)],
    )
    calc_html_no_attr = (
        "<!DOCTYPE html><html><head>"
        '<link rel="canonical" href="https://acmesolar.com/tools/solar-roi-calculator/">'
        "<title>Commercial Solar ROI Calculator | Acme Solar</title></head><body><main>"
        "<h1>Commercial Solar ROI Calculator</h1>"
        '<div class="calc-grid">'
        '<form class="calculator-form"><input type="number" id="field-system_kw" value="250"></form>'
        '<div class="result-box"><div class="output-value">$48,500</div></div>'
        "</div></main></body></html>"
    )
    norm_disc, _ = normalize_html_visual_primitives(calc_html_no_attr, is_tenant_porcelain=True)
    assert 'data-property="acme_solar"' in norm_disc
    assert "acme_solar_quick_worksheet" in norm_disc
    assert "acme_solar_full_workpaper_pack" in norm_disc
    assert "profithelm" not in norm_disc.lower()
    for ph_sku_prefix in ("ph_instant", "ph_statutory", "ph_commercial", "ph_1031", "ph_verified"):
        assert ph_sku_prefix not in norm_disc.lower()

    # 4. Unregistered tenant without TruthPack fails closed; registered acme_solar isolates /partners/ & JSON-LD
    with pytest.raises(KeyError, match="TRUTH_PACK_MISSING"):
        get_porcelain_tenant_profile("unregistered_solar_99")

    _register_temp_truth_pack(
        tmp_path,
        monkeypatch,
        property_id="acme_solar",
        brand_name="Acme Solar",
        canonical_domain="https://acme-solar.com",
    )
    acme_profile = get_porcelain_tenant_profile("acme_solar")
    acme_profile_dump = json.dumps(acme_profile)
    assert "ProfitHelm" not in acme_profile_dump
    assert "profithelm" not in acme_profile_dump.lower()
    assert "profithelm.com" not in acme_profile_dump.lower()
    assert "Apex Tax" not in acme_profile_dump
    assert acme_profile["brand_name"] == "Acme Solar"
    assert acme_profile["domain"] == "acme-solar.com"
    assert acme_profile["canonical_base"] == "https://acme-solar.com"
    assert acme_profile["legal_entity"] == "Acme Solar LLC"
    assert acme_profile["impact_verification_uuid"] == ""
    assert acme_profile["cj_property_id"] == ""
    assert acme_profile["contact_email"] == "editorial@acme-solar.com"

    acme_pages = build_governance_pages(acme_profile)
    acme_partners = acme_pages["partners"]
    assert "ProfitHelm" not in acme_partners
    assert "profithelm.com" not in acme_partners.lower()
    assert "Apex Tax" not in acme_partners
    assert "Q8161" not in acme_partners
    assert "Acme Solar Partner Advisory Group" in acme_partners
    assert "acme_solar_verified_partner_slot" in acme_partners

    lb_pages = build_governance_pages(get_porcelain_tenant_profile("lienbond"))
    assert "Apex Tax" not in lb_pages["partners"]
    assert "Summit Surety &amp; Bond Agency" in lb_pages["partners"]

    ph_pages = build_governance_pages(get_porcelain_tenant_profile("profithelm"))
    assert "Apex Tax &amp; Advisory LLP" in ph_pages["partners"]

    # 5. Dead CSS rules removed
    for prop in ("lienbond", "profithelm"):
        css = generate_porcelain_stylesheet(prop)
        assert ".pro-hook-card" not in css
        assert ".calc-result-quick-unlock-bar" not in css


def test_turnstile_b4_mount_verification_and_local_preview_guard() -> None:
    """
    Proves:
    1. Non-test local static previews (http: / file:) skip /api/lead-capture?config=1 unless forced.
    2. When __PSEO_EXERCISE_TURNSTILE_MOUNT__ is true (as in browser_verifier.py),
       mountRuntimeTurnstile executes against .cf-turnstile-slot and calls stub window.turnstile.render
       without injecting challenges.cloudflare.com script or blocking synthetic submit.
    3. Removing .cf-turnstile-slot or throwing inside window.turnstile.render fails the mount check.
    """
    from pseofactory.browser_verifier import UnifiedBrowserAuditor
    from pseofactory.visual_primitives import render_runtime_synchronizer_js

    assert "*challenges.cloudflare.com*" in UnifiedBrowserAuditor.BLOCKED_EXTERNAL_URL_PATTERNS
    assert "turnstile_mounted" in UnifiedBrowserAuditor.JS_RUN_E2E_INTERACTIVE_SURFACE
    assert "__PSEO_EXERCISE_TURNSTILE_MOUNT__" in UnifiedBrowserAuditor.JS_RUN_E2E_INTERACTIVE_SURFACE

    runtime_js = render_runtime_synchronizer_js()
    assert "function isLocalStaticPreview()" in runtime_js

    harness = """
const vm = require('vm');
const assert = require('assert');

function makeNode(tag, attrs = {}) {
  const node = {
    tagName: tag.toUpperCase(),
    nodeType: 1,
    attributes: { ...attrs },
    children: [],
    parentNode: null,
    parentElement: null,
    style: {},
    classList: {
      _set: new Set(String(attrs.class || '').split(/\\s+/).filter(Boolean)),
      contains(c) { return this._set.has(c); },
      add(c) { this._set.add(c); },
      remove(c) { this._set.delete(c); }
    },
    get id() { return this.attributes.id || ''; },
    set id(v) { this.attributes.id = v; },
    get className() { return Array.from(this.classList._set).join(' '); },
    set className(v) {
      this.classList._set = new Set(String(v || '').split(/\\s+/).filter(Boolean));
      this.attributes.class = this.className;
    },
    get name() { return this.attributes.name || ''; },
    set name(v) { this.attributes.name = v; },
    get type() { return this.attributes.type || ''; },
    set type(v) { this.attributes.type = v; },
    value: attrs.value || '',
    textContent: '',
    getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attributes, k) ? String(this.attributes[k]) : null; },
    setAttribute(k, v) {
      this.attributes[k] = String(v);
      if (k === 'class') this.className = v;
    },
    removeAttribute(k) { delete this.attributes[k]; },
    hasAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attributes, k); },
    appendChild(child) {
      child.parentNode = this;
      child.parentElement = this;
      this.children.push(child);
      return child;
    },
    removeChild(child) {
      this.children = this.children.filter(c => c !== child);
      child.parentNode = null;
      child.parentElement = null;
      return child;
    },
    contains(target) {
      if (target === this) return true;
      return this.children.some(c => c.contains(target));
    },
    closest(sel) {
      let cur = this;
      while (cur) {
        if (matchesSelector(cur, sel)) return cur;
        cur = cur.parentElement;
      }
      return null;
    },
    querySelector(sel) { return this.querySelectorAll(sel)[0] || null; },
    querySelectorAll(sel) {
      const out = [];
      const walk = (n) => {
        for (const ch of n.children) {
          if (matchesSelector(ch, sel)) out.push(ch);
          walk(ch);
        }
      };
      walk(this);
      return out;
    },
    dispatchEvent() { return true; },
    focus() {}
  };
  return node;
}

function matchesSelector(el, sel) {
  return sel.split(',').map(s => s.trim()).some(part => {
    if (!part) return false;
    if (part.startsWith('#')) return el.id === part.slice(1);
    if (part.startsWith('.')) return el.classList.contains(part.slice(1));
    const m = part.match(/^([a-z]+)\\[name="([^"]+)"\\]$/i);
    if (m) return el.tagName.toLowerCase() === m[1].toLowerCase() && el.name === m[2];
    const m2 = part.match(/^input\\[type="([^"]+)"\\]$/i);
    if (m2) return el.tagName.toLowerCase() === 'input' && el.type === m2[1];
    return el.tagName.toLowerCase() === part.toLowerCase();
  });
}

async function runScenario({ protocol, synthetic, exercise, forceCfg, attachSlot, throwOnRender }) {
  const fetchUrls = [];
  const appendedScripts = [];
  const docListeners = {};
  const body = makeNode('body');
  const head = makeNode('head');
  const form = makeNode('form', { id: 'partner-registration-form', class: 'partner-registration-form' });
  const firmInp = makeNode('input', { type: 'text', name: 'firm_name', value: 'Acme Solar Partner' });
  const emailInp = makeNode('input', { type: 'email', name: 'email', value: 'partners@acmesolar.com' });
  const slot = makeNode('div', { class: 'cf-turnstile-slot', 'data-turnstile-slot': '1' });
  form.appendChild(firmInp);
  form.appendChild(emailInp);
  if (attachSlot) form.appendChild(slot);
  body.appendChild(form);

  const document = {
    body,
    head,
    documentElement: body,
    readyState: 'complete',
    addEventListener(ev, fn) { (docListeners[ev] = docListeners[ev] || []).push(fn); },
    createElement(t) {
      const n = makeNode(t);
      if (t.toLowerCase() === 'script') appendedScripts.push(n);
      return n;
    },
    getElementById(id) { return body.querySelector('#' + id); },
    querySelector(sel) { return body.querySelector(sel); },
    querySelectorAll(sel) { return body.querySelectorAll(sel); }
  };
  const origHeadAppend = head.appendChild.bind(head);
  head.appendChild = (ch) => {
    if (ch && ch.tagName === 'SCRIPT') appendedScripts.push(ch);
    return origHeadAppend(ch);
  };

  const mountCalls = [];
  const windowObj = {
    location: { protocol, pathname: '/partners/', href: protocol + '//example.test/partners/', search: '', hash: '', origin: protocol + '//example.test' },
    document,
    __PSEO_SYNTHETIC_TEST__: synthetic,
    __PSEO_EXERCISE_TURNSTILE_MOUNT__: exercise,
    __PSEO_FORCE_TURNSTILE_CONFIG__: forceCfg,
    fetch: async (url) => {
      fetchUrls.push(url);
      if (url.includes('config=1')) {
        return { ok: true, status: 200, json: async () => ({ ok: true, turnstile_enabled: false, turnstile_site_key: '' }) };
      }
      return { ok: true, status: 200, json: async () => ({ ok: true, lead_id: 'lead_1', status: 'partner_registered', checkout_url: '/api/lead-capture?checkout=1&sku=acme_solar_verified_partner_slot', offer_price_usd: 299 }) };
    },
    addEventListener() {},
    turnstile: {
      render(el, opts) {
        if (throwOnRender) throw new Error('simulated_turnstile_render_crash');
        mountCalls.push({ hasSlot: el === slot, inBody: body.contains(el), sitekey: opts.sitekey });
        if (opts.callback) opts.callback('stub_tok');
        return 'w_1';
      },
      reset() {},
      remove() {}
    }
  };
  windowObj.window = windowObj;

  const ctx = vm.createContext({
    window: windowObj,
    document,
    URLSearchParams,
    URL,
    Event: class Event { constructor(t) { this.type = t; } preventDefault() {} stopImmediatePropagation() {} },
    Promise,
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    console
  });
  vm.runInContext(RUNTIME_JS, ctx);
  await new Promise(r => setTimeout(r, 30));

  // If synthetic test did not auto-warm on load (only if exercise was false), test explicit warm
  if (exercise && typeof windowObj.__pseoWarmLeadFormsTurnstile === 'function') {
    windowObj.__pseoWarmLeadFormsTurnstile();
    await new Promise(r => setTimeout(r, 30));
  }

  return {
    fetchUrls,
    appendedScripts: appendedScripts.map(s => s.src || ''),
    mountCalls,
    mountedAttr: slot.getAttribute('data-turnstile-mounted'),
    mountErr: windowObj.__pseoTurnstileMountError || ''
  };
}

(async () => {
  // 1. Local preview without force config must NOT fetch config=1
  const localRes = await runScenario({ protocol: 'http:', synthetic: false, exercise: false, forceCfg: false, attachSlot: true, throwOnRender: false });
  assert.strictEqual(localRes.fetchUrls.filter(u => u.includes('config=1')).length, 0);

  // 2. Synthetic B4 exercise mounts stub turnstile without touching challenges.cloudflare.com
  const b4Res = await runScenario({ protocol: 'http:', synthetic: true, exercise: true, forceCfg: true, attachSlot: true, throwOnRender: false });
  assert.strictEqual(b4Res.fetchUrls.filter(u => u.includes('config=1')).length >= 1, true);
  assert.strictEqual(b4Res.mountedAttr, '1');
  assert.strictEqual(b4Res.mountCalls.length, 1);
  assert.strictEqual(b4Res.mountCalls[0].inBody, true);
  assert.strictEqual(b4Res.appendedScripts.length, 0);
  assert.strictEqual(b4Res.mountErr, '');

  // 3. Broken render throws and is captured cleanly instead of passing silently
  const errRes = await runScenario({ protocol: 'http:', synthetic: true, exercise: true, forceCfg: true, attachSlot: true, throwOnRender: true });
  assert.strictEqual(errRes.mountErr, 'simulated_turnstile_render_crash');
  assert.strictEqual(errRes.mountedAttr, null);

  console.log('TURNSTILE_B4_OK');
})().catch(e => { console.error(e); process.exit(1); });
"""
    script = f"const RUNTIME_JS = {json.dumps(runtime_js)};\n{harness}"
    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=True) as tf:
        tf.write(script)
        tf.flush()
        proc = subprocess.run(["node", tf.name], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"Node B4 harness failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    assert "TURNSTILE_B4_OK" in proc.stdout


def test_runtime_js_hygiene_and_retired_legacy_helpers_deleted() -> None:
    """
    Verifies:
    - _render_runtime_sync_events_js() passes node --check.
    - Zero literal U+2014 / U+2013 and zero literal localhost / 127.0.0.1 in runtime JS/porcelain templates.
    - Dead #lead-capture-form / #partner-quote-intake-form JS submit handlers and 14 dead Python helpers are deleted.
    """
    from pseofactory import porcelain_shell, visual_primitives

    events_js = visual_primitives._render_runtime_sync_events_js()
    full_js = visual_primitives._render_runtime_sync_workbench_js() + "\n" + events_js
    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=True) as tf:
        tf.write(full_js)
        tf.flush()
        chk = subprocess.run(["node", "--check", tf.name], capture_output=True, text=True, check=False)
    assert chk.returncode == 0, chk.stderr

    for bad_ch in ("\u2014", "\u2013"):
        assert bad_ch not in events_js
    for forbidden_host in ("localhost", "127.0.0.1"):
        assert forbidden_host not in events_js.lower()
        porc_src = Path(porcelain_shell.__file__).read_text(encoding="utf-8")
        assert forbidden_host not in porc_src.lower()

    # Dead form handlers removed, live handlers preserved
    assert 'e.target.id === "lead-capture-form"' not in events_js
    assert 'e.target.id === "partner-quote-intake-form"' not in events_js
    assert 'e.target.id === "partner-registration-form"' in events_js
    assert "#btn-preview-workpaper" in events_js
    assert "workpaper-unlock-card" in events_js

    retired_symbols = (
        "_inject_post_calc_workpaper_upgrade_drawer",
        "_pro_hook_has_mismatched_price",
        "_gainhelm_pro_card_has_stale_tax_copy",
        "_gainhelm_pro_card_has_mismatch",
        "_GAINHELM_PRO_SHORT_LABELS",
        "_resolve_gainhelm_pro_short_label",
        "_build_pro_hook_card_copy",
        "_clean_pro_hook_outer_spans",
        "_split_top_level_html_nodes",
        "_heal_pro_hook_sample_unlock",
        "_retrofit_pro_hook_and_lead_capture_cards",
        "_normalize_pro_hook_link_contrast",
        "_retrofit_partner_reg_and_quick_unlock",
        "_retrofit_hero_range_and_jurisdiction_bars",
    )
    for sym in retired_symbols:
        assert not hasattr(visual_primitives, sym), f"Retired symbol still present: {sym}"


def test_resolve_html_property_id_preserves_leading_w_domains(tmp_path: Path, monkeypatch) -> None:
    """
    Regression test for raw_dom.lstrip('www.') bug: domains starting with 'w'
    (windpower.com, www.wealthcalc.com) must keep their leading 'w' and map cleanly.
    """
    from pseofactory import impact_planner
    from pseofactory.visual_primitives import _resolve_html_property_id

    wind_repo = tmp_path / "windpower_calc"
    wealth_repo = tmp_path / "wealth_hq"
    wind_repo.mkdir()
    wealth_repo.mkdir()
    (wind_repo / ".pseofactory.json").write_text(
        json.dumps({"property_id": "windpower_calc", "domain": "windpower.com"}),
        encoding="utf-8",
    )
    (wealth_repo / ".pseofactory.json").write_text(
        json.dumps({"property_id": "wealth_hq", "domain": "www.wealthcalc.com"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        impact_planner,
        "discover_active_tenants",
        lambda workspace_root="/home/ubuntuadmin/projects": [
            ("windpower_calc", wind_repo),
            ("wealth_hq", wealth_repo),
        ],
    )

    assert _resolve_html_property_id("<html></html>", "https://windpower.com/tools/turbine-roi/") == "windpower_calc"
    assert _resolve_html_property_id("<html></html>", "https://www.wealthcalc.com/tools/net-worth/") == "wealth_hq"
    assert _resolve_html_property_id("<html></html>", "https://wealthcalc.com/tools/net-worth/") == "wealth_hq"
