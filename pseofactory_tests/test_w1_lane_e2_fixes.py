"""
Wave 1 Lane E2 Surgical Regression Tests:
- Item 25: browser_verifier.py fail-closed missing dist_dir, strict _resolve_disk_file isolation, dynamic active tenant domains in _build_broken_assets_js
- Item 26: compiler.py literal-left modulo AST compilation, <1 4-decimal client/SSR parity, zero bare-load history.replaceState mutation, HTML-escaped meta attributes
- Item 27: edge.py full CIDR/IPv6 SSRF guard parity on gainhelm/lienbond and ?mode=native preserving directContractUrl on live direct-contract partners
- Item 28: porcelain_shell.py _sync_sitemaps_headers_and_redirects merging duplicate _headers route blocks

Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

import pytest

from pseofactory.browser_verifier import UnifiedBrowserAuditor
from pseofactory.compiler import compile_ast_to_js, compile_high_effort_page
from pseofactory.edge import (
    generate_edge_redirect_function,
    resolve_canonical_partner_redirect,
)
from pseofactory.porcelain_shell import (
    _sync_sitemaps_headers_and_redirects,
    get_porcelain_tenant_profile,
)


# ---------------------------------------------------------------------------
# Item 25: browser_verifier.py
# ---------------------------------------------------------------------------


def test_browser_auditor_missing_dist_dir_fails_closed(tmp_path: Path) -> None:
    missing_dist = tmp_path / "does_not_exist_dist"
    assert not missing_dist.exists()

    aud_closed = UnifiedBrowserAuditor(dist_dir=missing_dist, fail_closed=True)
    rep_closed = aud_closed.run_audit()
    assert rep_closed["status"] == "FAIL"
    assert rep_closed["passed"] is False
    assert rep_closed["failed_count"] >= 1

    aud_open = UnifiedBrowserAuditor(dist_dir=missing_dist, fail_closed=False)
    rep_open = aud_open.run_audit()
    assert rep_open["status"] != "PASS"
    assert rep_open["passed"] is False


def test_browser_auditor_resolve_disk_file_never_falls_back_to_other_tenants(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dist_dir = tmp_path / "partial_dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.html").write_text("<html><body>Home</body></html>", encoding="utf-8")
    (dist_dir / "local-page").mkdir(parents=True, exist_ok=True)
    (dist_dir / "local-page" / "index.html").write_text("<html><body>Local</body></html>", encoding="utf-8")

    # Even without sitemap.xml, routes missing from self.dist_dir must NEVER fall back
    # to OTHER tenants' dist directories under pytest, and in production (no PYTEST_CURRENT_TEST)
    # must stay strictly confined to self.dist_dir.
    assert not (dist_dir / "sitemap.xml").is_file()
    aud_ph = UnifiedBrowserAuditor(dist_dir=dist_dir, property_id="profithelm")

    assert aud_ph._resolve_disk_file("/") == dist_dir / "index.html"
    assert aud_ph._resolve_disk_file("/local-page/") == dist_dir / "local-page" / "index.html"
    assert aud_ph._resolve_disk_file("/tools/soc-2-audit-cost-calculator/") is None
    assert aud_ph._resolve_disk_file("/tools/student-loan-repayment-calculator/") is None
    assert aud_ph._resolve_disk_file("/../index.html") is None

    aud_fifth = UnifiedBrowserAuditor(dist_dir=dist_dir, property_id="fifthsite")
    assert aud_fifth._resolve_disk_file("/about/") is None
    assert aud_fifth._resolve_disk_file("/tools/section-179-calculator/") is None

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    assert aud_ph._resolve_disk_file("/about/") is None
    assert aud_ph._resolve_disk_file("/tools/section-179-calculator/") is None


@pytest.mark.skipif(shutil.which("node") is None, reason="node is required")
def test_browser_auditor_broken_assets_js_uses_dynamic_active_tenant_domains(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fifth_repo = tmp_path / "fifthsite"
    fifth_repo.mkdir(parents=True, exist_ok=True)
    (fifth_repo / ".pseofactory.json").write_text(
        json.dumps({"property_id": "fifthsite", "domain": "fifthsite.io", "canonical_base": "https://fifthsite.io"}),
        encoding="utf-8",
    )

    import pseofactory.impact_planner as impact_planner

    monkeypatch.setattr(
        impact_planner,
        "discover_active_tenants",
        lambda workspace_root="/home/ubuntuadmin/projects": [("fifthsite", fifth_repo)],
    )

    js_code = UnifiedBrowserAuditor._build_broken_assets_js(check_meta_assets=True, check_script_assets=True)
    assert "fifthsite.io" in js_code

    # Verify in Node that an og:image pointing at https://fifthsite.io/og.png is rewritten
    # to the local server origin and checked by fetch().
    node_script = (
        "const vm = require('vm');\n"
        "const fetched = [];\n"
        "const ogEl = { getAttribute: (k) => (k === 'content' ? 'https://www.fifthsite.io/static/og.png?v=1' : '') };\n"
        "const sandbox = {\n"
        "  URL, Set, Promise,\n"
        "  window: { location: { origin: 'http://127.0.0.1:43210', href: 'http://127.0.0.1:43210/' } },\n"
        "  document: {\n"
        "    querySelectorAll: (sel) => {\n"
        "      if (sel.includes('og:image')) return [ogEl];\n"
        "      return [];\n"
        "    },\n"
        "  },\n"
        "  fetch: async (url) => { fetched.push(url); return { ok: true, status: 200 }; },\n"
        "};\n"
        f"(async () => {{ const res = await vm.runInNewContext({json.dumps(js_code)}, sandbox); console.log(JSON.stringify({{ fetched, res }})); }})();\n"
    )
    proc = subprocess.run(["node", "-e", node_script], capture_output=True, text=True, check=True, timeout=15)
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    assert out["fetched"] == ["http://127.0.0.1:43210/static/og.png?v=1"]
    assert out["res"] == []


# ---------------------------------------------------------------------------
# Item 26: compiler.py
# ---------------------------------------------------------------------------


def test_compile_ast_to_js_preserves_literal_left_modulo() -> None:
    err_msg = None
    js_mod = None
    try:
        js_mod = compile_ast_to_js("2 % amount", ["amount"])
    except ValueError as exc:
        err_msg = str(exc)
    assert err_msg is None, f"compile_ast_to_js corrupted literal-left modulo: {err_msg}"
    assert js_mod == "(2 % inputs.amount)"
    assert compile_ast_to_js("10 % 3") == "(10 % 3)"
    assert compile_ast_to_js("100 % (x + 1)", ["x"]) == "(100 % (inputs.x + 1))"
    # Percentage suffix still compiles to / 100.0 when not followed by a modulo operand
    assert compile_ast_to_js("amount * 15%", ["amount"]) == "(inputs.amount * (15 / 100.0))"
    assert compile_ast_to_js("round(x * 7.5%, 2)", ["x"]) == "(Math.round((inputs.x * (7.5 / 100.0)) * Math.pow(10, 2)) / Math.pow(10, 2))"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is required")
def test_compiler_sub1_4decimal_parity_and_no_bare_load_replacestate() -> None:
    res = compile_high_effort_page(
        {
            "slug": "sub-one-effective-rate-calculator",
            "query": "effective rate decimal model",
            "title": "Effective Rate Calculator",
            "property_id": "profithelm",
            "canonical_base": "https://profithelm.com",
            "model_name": "Effective Rate Decimal Model",
            "formula": "rate * factor",
            "inputs": {"rate": 0.0385, "factor": 1.0},
            "published_output": 0.0385,
            "sample_calculation": "Rate 0.0385 times factor 1.0 yields 0.0385",
            "statutory_authority": "IRC Section 179(b)(1)",
            "economic_dataset": "FRED DGS10 Series",
        }
    )
    html_text = res["html"]
    assert "0.0385" in html_text

    scripts = re.findall(r"<script(?:\s+[^>]*)?>(.*?)</script>", html_text, flags=re.DOTALL | re.IGNORECASE)
    calc_js = [s for s in scripts if "updateQueryParams" in s and "handleRecompute" in s][-1]

    node_harness = (
        "const vm = require('vm');\n"
        "const listeners = {};\n"
        "const replaceCalls = [];\n"
        "const scheduled = [];\n"
        "const rateInput = { id: 'input-rate', name: 'rate', type: 'number', value: '0.0385' };\n"
        "const factorInput = { id: 'input-factor', name: 'factor', type: 'number', value: '1.0' };\n"
        "const form = {\n"
        "  querySelectorAll: () => [rateInput, factorInput],\n"
        "  addEventListener: (ev, fn) => { (listeners[ev] = listeners[ev] || []).push(fn); },\n"
        "};\n"
        "const outputElem = { textContent: '' };\n"
        "const sandbox = {\n"
        "  URL, URLSearchParams, Intl, Math, Number, String, isNaN, isFinite,\n"
        "  setTimeout: (fn, ms) => { const item = { id: scheduled.length + 1, fn, ms, cleared: false }; scheduled.push(item); return item.id; },\n"
        "  clearTimeout: (id) => { const item = scheduled.find((x) => x.id === id); if (item) item.cleared = true; },\n"
        "  window: {\n"
        "    location: { href: 'https://profithelm.com/tools/sub-one-effective-rate-calculator/', search: '' },\n"
        "    history: { replaceState: (_s, _t, u) => { replaceCalls.push(u); } },\n"
        "    addEventListener: () => {},\n"
        "  },\n"
        "  document: {\n"
        "    getElementById: (id) => (id.endsWith('-calculator') ? form : null),\n"
        "    querySelector: (sel) => (sel === '.output-value' ? outputElem : null),\n"
        "  },\n"
        "};\n"
        f"vm.runInNewContext({json.dumps(calc_js)}, sandbox);\n"
        "const bareOutput = outputElem.textContent;\n"
        "const bareScheduledCount = scheduled.length;\n"
        "const bareReplaceCount = replaceCalls.length;\n"
        "rateInput.value = '0.0412';\n"
        "for (const fn of (listeners.input || [])) fn({ target: rateInput });\n"
        "const inputScheduledCount = scheduled.length;\n"
        "for (const item of scheduled) { if (!item.cleared) item.fn(); }\n"
        "console.log(JSON.stringify({ bareOutput, bareScheduledCount, bareReplaceCount, inputScheduledCount, afterInputOutput: outputElem.textContent, replaceCalls }));\n"
    )
    proc = subprocess.run(["node", "-e", node_harness], capture_output=True, text=True, check=True, timeout=15)
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    assert out["bareOutput"] == "0.0385"
    assert out["bareScheduledCount"] == 0
    assert out["bareReplaceCount"] == 0
    assert out["inputScheduledCount"] == 1
    assert out["afterInputOutput"] == "0.0412"
    assert len(out["replaceCalls"]) == 1
    assert "rate=0.0412" in out["replaceCalls"][0]


def test_compiler_html_escapes_meta_attribute_values() -> None:
    res = compile_high_effort_page(
        {
            "slug": "escaped-meta-attributes-calc",
            "query": 'tax & "quote" model',
            "title": 'S&P "500" <Alpha> Calculator',
            "description": 'Evaluate "A & B" <rate> under IRC Section 179 deterministically.',
            "gsc_verification_token": 'tok"evil&1',
            "property_id": "profithelm",
            "canonical_base": "https://profithelm.com",
            "model_name": "Escaped Meta Model",
            "formula": "cost * 0.21",
            "inputs": {"cost": 100000},
            "published_output": 21000.0,
            "sample_calculation": "Cost 100,000 times 0.21 yields 21,000",
            "statutory_authority": "IRC Section 179(b)(1)",
            "economic_dataset": "FRED CPILFESL Series",
        }
    )
    html_text = res["html"]
    assert '<meta name="google-site-verification" content="tok&quot;evil&amp;1" />' in html_text
    assert '<meta property="og:title" content="S&amp;P &quot;500&quot; &lt;Alpha&gt; Calculator" />' in html_text
    assert '<meta name="twitter:title" content="S&amp;P &quot;500&quot; &lt;Alpha&gt; Calculator" />' in html_text
    assert '<meta name="description" content="Evaluate &quot;A &amp; B&quot; &lt;rate&gt; under IRC Section 179 deterministically." />' in html_text
    assert '<title>S&amp;P "500" &lt;Alpha&gt; Calculator</title>' in html_text


# ---------------------------------------------------------------------------
# Item 27: edge.py
# ---------------------------------------------------------------------------


@pytest.mark.skipif(shutil.which("node") is None, reason="node is required")
def test_edge_gainhelm_lienbond_ssrf_and_mode_native_direct_contract(tmp_path: Path) -> None:
    fake_hub = SimpleNamespace(
        _vault={
            "gainhelm": {
                "vanta_security": {
                    "status": "live",
                    "approved_tracking_url": "https://partner-direct.example/vanta-track?cid=gh1",
                }
            },
            "lienbond": {
                "levelset_lien_filing": {
                    "status": "live",
                    "approved_tracking_url": "https://partner-direct.example/levelset-track?cid=lb1",
                }
            },
            "prexvo": {},
            "profithelm": {},
        },
        get_direct_contract_upgrades=lambda prop: (
            {"vanta_security": "https://partner-direct.example/vanta-track?cid=gh1"}
            if prop == "gainhelm"
            else ({"levelset_lien_filing": "https://partner-direct.example/levelset-track?cid=lb1"} if prop == "lienbond" else {})
        ),
    )

    for prop, partner, expected_prefix, env_var in (
        ("gainhelm", "vanta_security", "https://partner-direct.example/vanta-track", "AFFILIATE_VANTA_SECURITY_URL"),
        ("lienbond", "levelset_lien_filing", "https://partner-direct.example/levelset-track", "AFFILIATE_LEVELSET_LIEN_FILING_URL"),
    ):
        js_src = generate_edge_redirect_function(property_id=prop, hub=fake_hub)
        mod_file = tmp_path / f"{prop}_redirect.mjs"
        mod_file.write_text(js_src, encoding="utf-8")

        node_runner = f"""
import * as mod from {json.dumps(str(mod_file))};

const unsafeTargets = [
  "http://10.0.0.1/admin",
  "http://172.16.0.5/secret",
  "http://192.168.1.1/router",
  "http://169.254.1.1/latest",
  "http://2130706433/",
  "http://0x7f000001/",
  "http://[fd00::1]/",
  "http://[fe80::1]/",
  "http://[::ffff:127.0.0.1]/"
];

const ssrfLocations = [];
for (const badUrl of unsafeTargets) {{
  const res = await mod.onRequest({{
    request: new Request("https://{prop}.com/r/{partner}?synthetic_test=1", {{
      headers: {{ "X-Pseofactory-Test": "1" }}
    }}),
    env: {{ {env_var}: badUrl }},
    params: {{ partner: "{partner}" }}
  }});
  ssrfLocations.push({{ badUrl, status: res.status, loc: res.headers.get("Location") || "" }});
}}

const nativeRes = await mod.onRequest({{
  request: new Request("https://{prop}.com/r/{partner}?mode=native&synthetic_test=1", {{
    headers: {{ "X-Pseofactory-Test": "1" }}
  }}),
  env: {{}},
  params: {{ partner: "{partner}" }}
}});

console.log(JSON.stringify({{
  ssrfLocations,
  nativeStatus: nativeRes.status,
  nativeLocation: nativeRes.headers.get("Location") || "",
  nativeTier: nativeRes.headers.get("X-Edge-Contract-Tier") || ""
}}));
"""
        proc = subprocess.run(["node", "--input-type=module", "-e", node_runner], capture_output=True, text=True, check=True, timeout=15)
        out = json.loads(proc.stdout.strip().splitlines()[-1])

        for item in out["ssrfLocations"]:
            assert not item["loc"].startswith(item["badUrl"]), f"{prop} allowed SSRF URL: {item}"
            assert item["status"] == 302
            assert item["loc"].startswith(f"https://{prop}.com/tools/"), f"{prop} SSRF fallback unexpected: {item}"

        assert out["nativeStatus"] == 302
        assert out["nativeTier"] == "direct_contract_upgraded", f"{prop} ?mode=native stripped tier: {out}"
        assert out["nativeLocation"].startswith(expected_prefix), f"{prop} ?mode=native stripped directContractUrl: {out}"

        py_emul = resolve_canonical_partner_redirect(
            partner,
            query_params={"mode": "native"},
            property_id=prop,
            hub=fake_hub,
        )
        assert py_emul["contract_tier"] == "direct_contract_upgraded"
        assert py_emul["location"].startswith(expected_prefix)


# ---------------------------------------------------------------------------
# Item 28: porcelain_shell.py
# ---------------------------------------------------------------------------


def test_sync_sitemaps_headers_merges_duplicate_route_blocks(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    headers_file = dist_dir / "_headers"
    headers_file.write_text(
        "# Existing headers with duplicate route blocks\n"
        "/tools/custom-calc/\n"
        '  Link: <https://profithelm.com/tools/custom-calc/>; rel="canonical"\n'
        "\n"
        "/tools/custom-calc/\n"
        "  X-Robots-Tag: index, follow\n"
        "  X-Custom-Merge: preserved\n"
        "\n"
        "/about/\n"
        "  X-First-About: one\n"
        "\n"
        "/about/\n"
        "  X-Second-About: two\n",
        encoding="utf-8",
    )

    profile: Dict[str, Any] = get_porcelain_tenant_profile("profithelm")
    mutated = _sync_sitemaps_headers_and_redirects(dist_dir, profile)
    assert "_headers" in mutated

    merged_txt = headers_file.read_text(encoding="utf-8")
    assert merged_txt.count("/tools/custom-calc/\n") == 1
    assert merged_txt.count("/about/\n") == 1
    assert 'Link: <https://profithelm.com/tools/custom-calc/>; rel="canonical"' in merged_txt
    assert "X-Robots-Tag: index, follow" in merged_txt
    assert "X-Custom-Merge: preserved" in merged_txt
    assert "X-First-About: one" in merged_txt
    assert "X-Second-About: two" in merged_txt
