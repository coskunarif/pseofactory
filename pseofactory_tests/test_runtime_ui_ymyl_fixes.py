from __future__ import annotations

from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

import pytest

from pseofactory.affiliates import normalize_html_callout_message_match
from pseofactory.compiler import _render_compiler_monetization_and_guardrail_html
from pseofactory.contracts import detect_asset_partner_roster_and_slot_issues
from pseofactory.gainhelm_estate import (
    _render_calculator_widget,
    compute_gainhelm_framework_benchmarks,
)
from pseofactory.maintenance import RetroReflectionEngine
from pseofactory.porcelain_shell import (
    _sync_sitemaps_headers_and_redirects,
    build_governance_pages,
    get_porcelain_tenant_profile,
)
from pseofactory.visual_primitives import (
    _retrofit_monetization_and_navigation_ux,
    render_runtime_synchronizer_js,
)


def _run_playwright_dom(html: str, js_probe: str) -> dict:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.set_content(html, wait_until="load")
        result = page.evaluate(js_probe)
        browser.close()
        return result


def test_runtime_sync_js_syntax_valid_and_zero_dashes() -> None:
    js = render_runtime_synchronizer_js()
    assert "\u2014" not in js
    assert "\u2013" not in js
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tf:
        tf.write(js)
        tmp_path = Path(tf.name)
    try:
        res = subprocess.run(["node", "--check", str(tmp_path)], capture_output=True, text=True, check=False)
        assert res.returncode == 0, f"node --check failed: {res.stderr}"
    finally:
        tmp_path.unlink(missing_ok=True)


def test_comparator_and_cliff_not_overwritten_with_irs_tax_on_non_income_tax_pages() -> None:
    rt_js = render_runtime_synchronizer_js()
    html = f"""<!doctype html>
<html><body>
<main>
  <div id="hero-range-anchor">
    <strong id="hero-range-low">$280,000</strong>
    <strong id="hero-range-baseline">$350,000</strong>
    <strong id="hero-range-high">$420,000</strong>
  </div>
  <span class="output-value">350,000</span>
  <form id="calc-form">
    <input id="sec179-cost" type="number" value="350000" />
  </form>
  <div id="sec179-res-writeoff">$350,000</div>
  <section id="serp-incumbent-depth-workbench" data-workbench-mode="sec179">
    <input id="serp-179-cost" type="number" value="350000" />
    <input id="serp-179-income" type="number" value="320000" />
    <input id="serp-179-apr" type="number" value="6.75" />
    <select id="serp-179-class"><option value="machinery_100" selected>Machinery</option></select>
    <span id="serp-out-primary">$350,000</span>
    <span id="serp-out-secondary">$122,500</span>
    <span id="serp-out-tertiary">$70,000</span>
    <span id="serp-out-quaternary">+$52,500</span>
    <span id="serp-cliff-val-0">$122k</span>
    <span id="serp-cliff-val-1">$122k</span>
    <span id="serp-cliff-val-2">$122k</span>
  </section>
  <section id="multi-year-cliff-visualizer">
    <div id="cliff-bar-2026"></div><span id="cliff-exposure-2026">$53,000 SUV / $350k Equip</span>
    <div id="cliff-bar-2028"></div><span id="cliff-exposure-2028">$68,000 SUV / 100% Bonus</span>
  </section>
  <section id="stateful-scenario-comparator">
    <button type="button" data-scenario-pin="A">Pin A</button>
    <button type="button" data-scenario-pin="B">Pin B</button>
    <button type="button" data-scenario-pin="RESET">Reset</button>
    <table>
      <tr>
        <td id="comp-a-input">$350,000</td>
        <td id="comp-b-input">$350,000 Commercial Equipment (100% Use)</td>
        <td id="comp-live-input">+$0</td>
      </tr>
      <tr>
        <td id="comp-a-retained">$312,000</td>
        <td id="comp-b-retained">$227,500</td>
        <td id="comp-live-retained">$38,000 SUV / $350,000 Equip Write-Off</td>
      </tr>
      <tr>
        <td id="comp-a-tax">$13,300 Cash Tax Saved (at 35%)</td>
        <td id="comp-b-tax">$122,500 Cash Tax Saved (at 35%)</td>
        <td id="comp-live-tax">$38,000 / $350,000</td>
      </tr>
      <tr>
        <td id="comp-a-delta">$0</td>
        <td id="comp-b-delta">+$109,200 Tax Shield Expansion</td>
        <td id="comp-live-delta">+$109,200</td>
      </tr>
    </table>
  </section>
</main>
<script>
window.updateSection179Calculator = function() {{
  var c = parseFloat(document.getElementById("sec179-cost").value) || 0;
  document.getElementById("sec179-res-writeoff").textContent = "$" + Math.round(c).toLocaleString("en-US");
}};
</script>
<script>{rt_js}</script>
</body></html>"""

    res = _run_playwright_dom(
        html,
        """() => {
            const inp = document.getElementById("sec179-cost");
            inp.value = "525000";
            inp.dispatchEvent(new Event("input", {bubbles: true}));
            inp.dispatchEvent(new Event("change", {bubbles: true}));
            const afterInput = {
                heroBase: document.getElementById("hero-range-baseline").textContent.trim(),
                heroLow: document.getElementById("hero-range-low").textContent.trim(),
                heroHigh: document.getElementById("hero-range-high").textContent.trim(),
                outVal: document.querySelector(".output-value").textContent.trim(),
                compATax: document.getElementById("comp-a-tax").textContent.trim(),
                compBTax: document.getElementById("comp-b-tax").textContent.trim(),
                compLTax: document.getElementById("comp-live-tax").textContent.trim(),
                cliff2028: document.getElementById("cliff-exposure-2028").textContent.trim(),
                svgCliff0: document.getElementById("serp-cliff-val-0").textContent.trim(),
            };
            // Pin A -> change -> Pin B -> check non-IRS pinned values -> Reset restores SSR
            document.querySelector('[data-scenario-pin="A"]').click();
            inp.value = "700000";
            inp.dispatchEvent(new Event("input", {bubbles: true}));
            document.querySelector('[data-scenario-pin="B"]').click();
            const afterPin = {
                compARet: document.getElementById("comp-a-retained").textContent.trim(),
                compBRet: document.getElementById("comp-b-retained").textContent.trim(),
                compBTax: document.getElementById("comp-b-tax").textContent.trim(),
            };
            document.querySelector('[data-scenario-pin="RESET"]').click();
            const afterReset = {
                compATax: document.getElementById("comp-a-tax").textContent.trim(),
                compBTax: document.getElementById("comp-b-tax").textContent.trim(),
            };
            return {afterInput, afterPin, afterReset};
        }""",
    )
    # 1. Hero KPI updates live from #sec179-res-writeoff ($525,000) instead of staying frozen at $350,000
    assert res["afterInput"]["heroBase"] == "$525,000"
    assert res["afterInput"]["heroLow"] == "$420,000"
    assert res["afterInput"]["heroHigh"] == "$630,000"
    assert res["afterInput"]["outVal"] == "525,000"
    # 2. SSR domain comparator is NOT overwritten with IRS income tax ($147,362), and cliff scales proportionally (1.5x) while preserving its domain suffix
    assert res["afterInput"]["compATax"] == "$13,300 Cash Tax Saved (at 35%)"
    assert res["afterInput"]["compBTax"] == "$122,500 Cash Tax Saved (at 35%)"
    assert res["afterInput"]["compLTax"] == "$38,000 / $350,000"
    assert res["afterInput"]["cliff2028"] == "$102,000 SUV / 100% Bonus"
    assert "$126,174" not in res["afterInput"]["cliff2028"]
    assert "$147,362" not in res["afterPin"]["compBTax"]
    # 3. Pinning works cleanly and Reset restores SSR comparator text
    assert res["afterPin"]["compARet"] and res["afterPin"]["compARet"] != "$0"
    assert res["afterPin"]["compBRet"] and res["afterPin"]["compBRet"] != "$0"
    assert res["afterReset"]["compATax"] == "$13,300 Cash Tax Saved (at 35%)"
    assert res["afterReset"]["compBTax"] == "$122,500 Cash Tax Saved (at 35%)"


def test_hero_range_syncs_live_on_prexvo_and_profithelm_native_outputs() -> None:
    rt_js = render_runtime_synchronizer_js()
    html = f"""<!doctype html>
<html><body>
<main>
  <div id="hero-range-anchor">
    <strong id="hero-range-low">$198.58</strong>
    <strong id="hero-range-baseline">$248.23</strong>
    <strong id="hero-range-high">$297.88</strong>
  </div>
  <span class="output-value">248.23</span>
  <form class="calculator-form">
    <input id="field-agi" type="number" value="65000" />
  </form>
  <div id="metric-rap_payment">$248.23</div>
</main>
<script>
document.getElementById("field-agi").addEventListener("input", function() {{
  var agi = parseFloat(this.value) || 0;
  var mo = Math.max(0, (agi - 35212.5) * 0.10 / 12);
  document.getElementById("metric-rap_payment").textContent = "$" + mo.toFixed(2);
}});
</script>
<script>{rt_js}</script>
</body></html>"""

    res = _run_playwright_dom(
        html,
        """() => {
            const agi = document.getElementById("field-agi");
            agi.value = "95000";
            agi.dispatchEvent(new Event("input", {bubbles: true}));
            return {
                metric: document.getElementById("metric-rap_payment").textContent.trim(),
                heroBase: document.getElementById("hero-range-baseline").textContent.trim(),
                heroLow: document.getElementById("hero-range-low").textContent.trim(),
                heroHigh: document.getElementById("hero-range-high").textContent.trim(),
                outVal: document.querySelector(".output-value").textContent.trim(),
            };
        }""",
    )
    assert res["metric"] == "$498.23"
    assert res["heroBase"] == "$498.23"
    assert res["heroLow"] == "$398.58"
    assert res["heroHigh"] == "$597.88"
    assert res["outVal"] == "498.23"


def test_prexvo_suppressed_default_ymyl_never_gets_commercial_r_links() -> None:
    block = _render_compiler_monetization_and_guardrail_html(
        slug="discretionary-income-calculator-for-student-loans",
        query="discretionary income calculator for student loans",
        is_prexvo=True,
        candidate_spec={},
    )
    assert 'data-commercial-offers="suppressed-default"' in block["html"]
    assert block["commercial_offers_allowed"] is False
    assert block["affiliate_route"] is None

    page_html = f"""<!doctype html>
<html><head><link rel="canonical" href="https://prexvo.com/tools/discretionary-income-calculator-for-student-loans/"></head>
<body><main>
  <div class="result-box"><span class="output-value">248.23</span></div>
  <div id="partner-quote-intake-step" data-property-id="prexvo" data-tool-slug="discretionary-income-calculator-for-student-loans"></div>
  {block["html"]}
</main></body></html>"""

    retro_ux, _ = _retrofit_monetization_and_navigation_ux(page_html)
    assert 'href="/r/' not in retro_ux
    assert "href='/r/" not in retro_ux

    retro_aff = normalize_html_callout_message_match(
        retro_ux,
        property_id="prexvo",
    )
    assert 'href="/r/' not in retro_aff
    assert "href='/r/" not in retro_aff

    issues = detect_asset_partner_roster_and_slot_issues(
        html_text=retro_aff,
        property_id="prexvo",
        rel_path="tools/discretionary-income-calculator-for-student-loans/index.html",
        slug="discretionary-income-calculator-for-student-loans",
    )
    assert issues == []


def test_gainhelm_calculator_syncs_url_state_on_input_and_preset() -> None:
    benchmarks = compute_gainhelm_framework_benchmarks()
    section_html = _render_calculator_widget(
        benchmarks=benchmarks,
        tool_slug="soc-2-audit-cost-calculator",
    )
    assert "window.history.replaceState" in section_html
    assert "syncUrlState" in section_html

    full_html = f"""<!doctype html>
<html><body><main>
  <span class="output-value">78,100.40</span>
  <strong id="hero-range-low">$62,480</strong>
  <strong id="hero-range-baseline">$78,100</strong>
  <strong id="hero-range-high">$93,720</strong>
  {section_html}
</main></body></html>"""

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.route("https://gainhelm.test/**", lambda route: route.fulfill(status=200, content_type="text/html", body=full_html))
        page.goto("https://gainhelm.test/tools/soc-2-audit-cost-calculator/", wait_until="load")
        assert "?" not in page.url
        page.locator("#calc-input-headcount").fill("150")
        page.locator("#calc-input-headcount").dispatch_event("change")
        assert "headcount=150" in page.url
        # Reload with synced URL query and confirm hydration
        synced_url = page.url
        page.goto(synced_url, wait_until="load")
        assert page.locator("#calc-input-headcount").input_value() == "150"
        # Preset click also updates URL
        preset = page.locator(".calc-switcher-btn").nth(1)
        if preset.count() > 0:
            preset.click()
            assert "?" in page.url and "headcount=" in page.url
        browser.close()


def test_porcelain_headers_detach_cache_control_and_governance_email_off(tmp_path: Path) -> None:
    profile = get_porcelain_tenant_profile("gainhelm")
    pages = build_governance_pages(profile, active_tools=[], gsc_token="")
    for slug in ("about", "privacy", "contact"):
        html = pages[slug]
        assert "<!--email_off-->" in html
        # Every mailto link in governance pages must be wrapped by <!--email_off-->
        for m in re.finditer(r"<a\b[^>]*href=\"mailto:[^\"]+\"[^>]*>.*?</a>", html):
            start = max(0, m.start() - 20)
            end = min(len(html), m.end() + 20)
            assert "<!--email_off-->" in html[start:m.start()], f"{slug} mailto missing opening email_off"
            assert "<!--/email_off-->" in html[m.end():end], f"{slug} mailto missing closing email_off"

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "_headers").write_text(
        "# Cloudflare Pages Edge Headers generated by pseofactory.edge\n"
        "/*\n"
        "  Cache-Control: public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800\n\n"
        "/sitemap.xml\n"
        "  Cache-Control: public, max-age=0, s-maxage=60, must-revalidate\n\n"
        "/catalog.json\n"
        "  Cache-Control: public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800\n",
        encoding="utf-8",
    )
    _sync_sitemaps_headers_and_redirects(dist, profile)
    first_pass = (dist / "_headers").read_text(encoding="utf-8")
    for ep in ("/sitemap.xml", "/sitemap-hubs.xml", "/sitemap-leaves.xml", "/feed.xml", "/llms.txt", "/llms-full.txt", "/catalog.json", "/ai-benchmarks/*", "/static/js/*"):
        block_m = re.search(rf"^{re.escape(ep)}\n((?:  .*\n)+)", first_pass, flags=re.M)
        assert block_m, f"Missing _headers block for {ep}"
        lines = [l.strip() for l in block_m.group(1).splitlines()]
        detach_i = lines.index("! Cache-Control")
        cc_i = next(i for i, l in enumerate(lines) if l.startswith("Cache-Control:"))
        assert detach_i < cc_i, f"! Cache-Control must precede Cache-Control for {ep}"
        assert lines.count("! Cache-Control") == 1

    # Idempotency on second pass
    _sync_sitemaps_headers_and_redirects(dist, profile)
    assert (dist / "_headers").read_text(encoding="utf-8") == first_pass


def test_maintenance_sitemap_sync_prevents_hub_leaf_overlap(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    (dist / "tools" / "soc-2-audit-cost-calculator").mkdir(parents=True)
    (dist / "tools" / "soc-2-audit-cost-calculator" / "index.html").write_text(
        "<!doctype html><html><head><title>SOC 2</title></head><body><h1>SOC 2</h1></body></html>",
        encoding="utf-8",
    )
    (dist / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        '  <url><loc>https://gainhelm.com/</loc><lastmod>2026-11-22</lastmod></url>\n'
        '  <url><loc>https://gainhelm.com/tools/soc-2-audit-cost-calculator/</loc><lastmod>2026-11-22</lastmod></url>\n'
        '</urlset>\n',
        encoding="utf-8",
    )
    # Pre-existing overlap in sitemap-hubs.xml should be pruned, and never re-added
    (dist / "sitemap-hubs.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        '  <url><loc>https://gainhelm.com/</loc><lastmod>2026-11-22</lastmod></url>\n'
        '  <url><loc>https://gainhelm.com/tools/soc-2-audit-cost-calculator/</loc><lastmod>2026-11-22</lastmod></url>\n'
        '</urlset>\n',
        encoding="utf-8",
    )
    (dist / "sitemap-leaves.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        '  <url><loc>https://gainhelm.com/tools/soc-2-audit-cost-calculator/</loc><lastmod>2026-11-22</lastmod></url>\n'
        '</urlset>\n',
        encoding="utf-8",
    )

    RetroReflectionEngine.sync_tenant_publisher_prerequisites(
        dist_dir=dist,
        property_id="gainhelm",
        canonical_base="https://gainhelm.com",
    )

    def _locs(name: str) -> set[str]:
        root = ET.parse(dist / name).getroot()
        return {el.text.strip() for el in root.iter() if el.tag.endswith("loc") and el.text}

    sm = _locs("sitemap.xml")
    hubs = _locs("sitemap-hubs.xml")
    leaves = _locs("sitemap-leaves.xml")
    assert hubs & leaves == set()
    assert (hubs | leaves) == sm
    assert "https://gainhelm.com/tools/soc-2-audit-cost-calculator/" in leaves
    assert "https://gainhelm.com/tools/soc-2-audit-cost-calculator/" not in hubs


def test_porcelain_replaces_legacy_article_class_governance_pages(tmp_path: Path) -> None:
    from pseofactory.porcelain_shell import (
        audit_porcelain_shell_page,
        compile_tenant_porcelain_estate_with_profile,
    )

    dist = tmp_path / "dist"
    (dist / "disclaimers").mkdir(parents=True)
    (dist / "methodology").mkdir(parents=True)
    (dist / "index.html").write_text(
        "<!doctype html><html><head><title>Prexvo</title></head><body><main><h1>Prexvo</h1></main></body></html>",
        encoding="utf-8",
    )
    filler = " ".join(["Title IV 34 CFR Part 685 statutory calculation standard."] * 40)
    legacy_html = (
        "<!doctype html><html><head><title>Legacy Prexvo Governance</title></head><body><main>"
        '<h1 class="article-title">Statutory Disclaimers</h1>'
        '<p class="article-lead">Legacy lead paragraph with undefined class.</p>'
        '<h2 class="article-h2">Compliance Schedule</h2>'
        f'<p class="article-p">{filler}</p>'
        "<table><thead><tr><th>Statute</th><th>Scope</th></tr></thead>"
        "<tbody><tr><td>34 CFR 685</td><td>Federal repayment</td></tr></tbody></table>"
        "</main></body></html>"
    )
    (dist / "disclaimers" / "index.html").write_text(legacy_html, encoding="utf-8")
    (dist / "methodology" / "index.html").write_text(legacy_html, encoding="utf-8")

    profile = get_porcelain_tenant_profile("prexvo")
    compile_tenant_porcelain_estate_with_profile(dist, profile)

    for slug in ("disclaimers", "methodology"):
        out_html = (dist / slug / "index.html").read_text(encoding="utf-8")
        assert "article-title" not in out_html
        assert "article-h2" not in out_html
        assert "article-lead" not in out_html
        assert "article-p" not in out_html
        issues = audit_porcelain_shell_page(
            out_html,
            f"{slug}/index.html",
            property_id="prexvo",
            dist_dir=dist,
        )
        undef_issues = [i for i in issues if "Undefined CSS class" in i]
        assert undef_issues == [], f"{slug} still has undefined CSS classes: {undef_issues}"


def test_compile_lienbond_estate_prunes_stale_off_jurisdiction_tool_dir(tmp_path: Path) -> None:
    from pseofactory.compiler import compile_lienbond_estate

    stale_slug = "surety-bond-cost-calculator-philippines"
    stale_dir = tmp_path / "dist" / "tools" / stale_slug
    stale_dir.mkdir(parents=True)
    (stale_dir / "index.html").write_text(
        "<!doctype html><html><head><title>Stale</title></head><body><h1>Stale</h1></body></html>",
        encoding="utf-8",
    )
    manifests_dir = tmp_path / "dist" / "manifests"
    manifests_dir.mkdir(parents=True)
    stale_manifest = manifests_dir / f"{stale_slug}.json"
    stale_manifest.write_text('{"slug": "surety-bond-cost-calculator-philippines"}', encoding="utf-8")

    compile_lienbond_estate(tmp_path)

    assert not stale_dir.exists(), "Stale off-jurisdiction tool dir must be pruned"
    assert not stale_manifest.exists(), "Stale off-jurisdiction manifest must be pruned"
    assert (
        tmp_path / "dist" / "tools" / "contractor-license-bond-cost-calculator-by-credit-score" / "index.html"
    ).is_file()


def test_non_income_tax_cliff_scales_domain_suffix_without_svg_cliff_nodes() -> None:
    rt_js = render_runtime_synchronizer_js()
    html = f"""<!doctype html>
<html><body>
<main>
  <div id="hero-range-anchor">
    <strong id="hero-range-low">$62,480</strong>
    <strong id="hero-range-baseline">$78,100.40</strong>
    <strong id="hero-range-high">$93,720</strong>
  </div>
  <span class="output-value">78,100.40</span>
  <form id="soc2-compliance-form">
    <input id="calc-input-headcount" type="number" value="75" />
    <input id="calc-input-extra_criteria" type="number" value="2" />
  </form>
  <section id="serp-incumbent-depth-workbench" data-workbench-mode="cyber_grc">
    <input id="serp-b2b-gross" type="number" value="84000" />
    <input id="serp-b2b-deduction" type="number" value="25800" />
    <input id="serp-b2b-rate" type="number" value="22.0" />
  </section>
  <section id="multi-year-cliff-visualizer">
    <div id="cliff-bar-2024"></div><span id="cliff-exposure-2024">$64,800 SOC 2 TCO</span>
    <div id="cliff-bar-2025"></div><span id="cliff-exposure-2025">$71,200 SOC 2 TCO</span>
    <div id="cliff-bar-2026"></div><span id="cliff-exposure-2026">$78,100.40 SOC 2 TCO</span>
    <div id="cliff-bar-2027"></div><span id="cliff-exposure-2027">$83,400 SOC 2 TCO</span>
    <div id="cliff-bar-2028"></div><span id="cliff-exposure-2028">$94,600 SOC 2 TCO</span>
  </section>
  <section id="stateful-scenario-comparator">
    <table><tr>
      <td id="comp-a-tax">$78,100.40 Net Type II Audit TCO</td>
      <td id="comp-b-tax">$125,900 Unoptimized Manual TCO</td>
    </tr></table>
  </section>
</main>
<script>
window.__complianceSyncWorkspaceOutputs = function() {{
  var hc = parseFloat(document.getElementById("calc-input-headcount").value) || 75;
  var crit = parseFloat(document.getElementById("calc-input-extra_criteria").value) || 0;
  var total = Math.round((28000 + crit * 4500 + 26500 + 120 * (hc / 75) * 121.67) * 100) / 100;
  document.getElementById("hero-range-baseline").textContent = "$" + total.toLocaleString("en-US", {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
  document.querySelector(".output-value").textContent = total.toLocaleString("en-US", {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
}};
</script>
<script>{rt_js}</script>
</body></html>"""

    res = _run_playwright_dom(
        html,
        """() => {
            const before = document.getElementById("cliff-exposure-2024").textContent.trim();
            const crit = document.getElementById("calc-input-extra_criteria");
            crit.value = "4";
            crit.dispatchEvent(new Event("input", {bubbles: true}));
            crit.dispatchEvent(new Event("change", {bubbles: true}));
            return {
                before,
                after2024: document.getElementById("cliff-exposure-2024").textContent.trim(),
                after2026: document.getElementById("cliff-exposure-2026").textContent.trim(),
                heroBase: document.getElementById("hero-range-baseline").textContent.trim(),
                compATax: document.getElementById("comp-a-tax").textContent.trim(),
                compBTax: document.getElementById("comp-b-tax").textContent.trim(),
            };
        }""",
    )
    assert res["heroBase"] == "$87,100.40"
    assert res["after2024"] != res["before"]
    assert res["after2024"].endswith("SOC 2 TCO")
    assert res["after2024"] == "$72,267 SOC 2 TCO"
    assert res["after2026"] == "$87,100.40 SOC 2 TCO"
    assert res["compATax"] == "$78,100.40 Net Type II Audit TCO"
    assert res["compBTax"] == "$125,900 Unoptimized Manual TCO"


