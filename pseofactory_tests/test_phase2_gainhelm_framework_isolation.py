"""
Unmocked Phase 2 GainHelm cross-framework isolation and monetization parity tests.
Verifies DORA, EU AI Act, and SEC Form 8-K calculators contain zero SOC 2 / CMMC /
C3PAO / AICPA / HIPAA leaks across workbench, workspace, compliance strip, partner
sections, Python fulfillment, and Edge Worker fulfillment while preserving SOC 2 and
CMMC checkout/fulfillment parity. Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List

import pytest
from bs4 import BeautifulSoup

import pseofactory.affiliates as affiliates_mod
from pseofactory.affiliates import (
    audit_callout_destination_message_match,
    get_affiliate_route,
)
from pseofactory.compiler import compile_gainhelm_estate
from pseofactory.edge import (
    generate_edge_lead_capture_function,
    generate_edge_redirect_function,
)
from pseofactory.maintenance import RetroReflectionEngine
from pseofactory.partner_tracker import (
    evaluate_lead_quote_threshold,
    resolve_lead_monetization_offer,
    resolve_post_calculation_upgrade_spec,
    synthesize_personalized_audit_workpaper,
)
from pseofactory.porcelain_shell import (
    compile_tenant_porcelain_estate,
    get_porcelain_tenant_profile,
    normalize_html_to_porcelain_shell,
)

LIVE_GAINHELM_REPO = Path("/home/ubuntuadmin/projects/gainhelm")


def _strip_esm_exports(js_src: str) -> str:
    """Strips ESM export keywords and trailing export { ... } blocks for non-module node:vm execution."""
    stripped = re.sub(r"\bexport\s+(?=async\s+function\b|function\b)", "", js_src)
    stripped = stripped.replace("export default ", "const __default_export = ")
    stripped = re.sub(r"\bexport\s*\{[\s\S]*?\};?", "", stripped)
    return stripped
FORBIDDEN_NON_AUDIT_TOKENS = ("soc 2", "soc2", "cmmc", "c3pao", "aicpa", "hipaa")
SKU_IDS = (
    "gh_hipaa_iso27001_governance_kit",
    "gh_soc2_cmmc_audit_workpapers",
    "gh_instant_compliance_worksheet_19",
)
NON_US_AUDIT_SLUGS = {
    "dora-ict-third-party-risk-compliance-cost-calculator": {
        "vertical": "dora_eu_ict_resilience",
        "expected_marker": "dora",
        "expected_statute": "2022/2554",
    },
    "eu-ai-act-high-risk-conformity-assessment-cost-calculator": {
        "vertical": "eu_ai_act_conformity",
        "expected_marker": "eu ai act",
        "expected_statute": "2024/1689",
    },
    "sec-cybersecurity-incident-materiality-8k-item-105-cost-calculator": {
        "vertical": "sec_cyber_disclosure",
        "expected_marker": "8-k",
        "expected_statute": "229.106",
    },
}


def _assert_container_framework_clean(node, slug: str, container_name: str) -> None:
    visible = node.get_text(" ", strip=True).lower()
    raw = str(node).lower()
    for sku in SKU_IDS:
        raw = raw.replace(sku, " ")
    # Sibling /tools/... nav links inside nav blocks are allowed; target containers must not cite foreign frameworks
    for tok in FORBIDDEN_NON_AUDIT_TOKENS:
        assert tok not in visible, (
            f"Cross-framework visible text leak '{tok}' in {container_name} on {slug}: "
            f"{visible[max(0, visible.find(tok) - 80):visible.find(tok) + 120]}"
        )
        assert tok not in raw, (
            f"Cross-framework HTML leak '{tok}' in {container_name} on {slug}: "
            f"{raw[max(0, raw.find(tok) - 80):raw.find(tok) + 120]}"
        )


@pytest.mark.host_estate
def test_gainhelm_full_compile_retrofit_porcelain_framework_isolation(tmp_path: Path) -> None:
    repo = tmp_path / "gainhelm_repo"
    (repo / "content").mkdir(parents=True, exist_ok=True)
    voids_path = LIVE_GAINHELM_REPO / "content" / "deployed_voids.json"
    assert voids_path.is_file(), f"Missing deployed_voids.json at {voids_path}"
    shutil.copy2(voids_path, repo / "content" / "deployed_voids.json")

    compile_gainhelm_estate(str(repo))
    RetroReflectionEngine().retrofit_estate(repo / "dist", "gainhelm")
    compile_tenant_porcelain_estate(repo / "dist", property_id="gainhelm", repo_root=repo)

    for slug, meta in NON_US_AUDIT_SLUGS.items():
        page_path = repo / "dist" / "tools" / slug / "index.html"
        assert page_path.is_file(), f"Missing compiled page {page_path}"
        html_txt = page_path.read_text(encoding="utf-8")
        assert "\u2014" not in html_txt and "\u2013" not in html_txt
        soup = BeautifulSoup(html_txt, "html.parser")

        workbenches = soup.select("#serp-incumbent-depth-workbench")
        workspaces = soup.select("#calculator-workspace-anchor")
        compliance_strips = soup.select(".compliance-strip")
        affiliate_sections = soup.select(
            '.affiliate-section, .affiliates-section, .refinance-partner-section, .partners-section, section[data-first-party-checkout="true"]'
        )
        assert len(workbenches) == 1, f"Expected single #serp-incumbent-depth-workbench on {slug}, found {len(workbenches)}"
        assert workbenches, f"Missing #serp-incumbent-depth-workbench on {slug}"
        assert workspaces, f"Missing #calculator-workspace-anchor on {slug}"
        assert compliance_strips, f"Missing .compliance-strip on {slug}"
        assert affiliate_sections, f"Missing monetization/partner section on {slug}"

        for idx, wb_el in enumerate(workbenches):
            _assert_container_framework_clean(wb_el, slug, f"#serp-incumbent-depth-workbench[{idx}]")
        for idx, ws_el in enumerate(workspaces):
            _assert_container_framework_clean(ws_el, slug, f"#calculator-workspace-anchor[{idx}]")
        for idx, cs_el in enumerate(compliance_strips):
            _assert_container_framework_clean(cs_el, slug, f".compliance-strip[{idx}]")
        for idx, aff_sec in enumerate(affiliate_sections):
            _assert_container_framework_clean(aff_sec, slug, f"affiliate_section[{idx}]")

        drawer = soup.select_one("#post-calculation-upgrade-drawer")
        assert drawer is not None, f"Missing #post-calculation-upgrade-drawer on {slug}"
        assert drawer.get("data-offer-sku") == "gh_hipaa_iso27001_governance_kit"
        assert drawer.get("data-offer-price") == "49"
        drawer_title = (soup.select_one("#post-calculation-upgrade-drawer h4.post-calc-upgrade-title") or drawer).get_text(" ", strip=True).lower()
        assert meta["expected_marker"] in drawer_title, drawer_title
        assert meta["expected_statute"] in drawer.get_text(" ", strip=True).lower()

        quote_step = soup.select_one("#partner-quote-intake-step")
        assert quote_step is not None, f"Missing #partner-quote-intake-step on {slug}"
        assert quote_step.get("data-vertical") == meta["vertical"]

        # While all GainHelm partners are pending in monetization_vault.json, zero unapproved /r/ links render.
        r_links = soup.select('a[href^="/r/"]')
        assert r_links == []

    # Confirm SOC 2 and CMMC pages continue rendering SOC 2 / CMMC and $79 SKU cleanly
    soc2_soup = BeautifulSoup(
        (repo / "dist" / "tools" / "soc-2-audit-cost-calculator" / "index.html").read_text(encoding="utf-8"),
        "html.parser",
    )
    assert "soc 2" in soc2_soup.select_one("#post-calculation-upgrade-drawer").get_text(" ", strip=True).lower()
    assert soc2_soup.select_one("#post-calculation-upgrade-drawer").get("data-offer-sku") == "gh_soc2_cmmc_audit_workpapers"
    assert soc2_soup.select_one("#post-calculation-upgrade-drawer").get("data-offer-price") == "79"

    cmmc_soup = BeautifulSoup(
        (repo / "dist" / "tools" / "cmmc-2-0-compliance-cost-calculator" / "index.html").read_text(encoding="utf-8"),
        "html.parser",
    )
    assert "cmmc" in cmmc_soup.select_one(".compliance-strip").get_text(" ", strip=True).lower()
    assert cmmc_soup.select_one("#post-calculation-upgrade-drawer").get("data-offer-sku") == "gh_soc2_cmmc_audit_workpapers"

    # Callout message match check passes with zero mismatches
    callout_audit = audit_callout_destination_message_match(property_id="gainhelm", dist_dir=repo / "dist")
    assert callout_audit["mismatches"] == [], callout_audit["mismatches"]

    # Idempotency check across repeated retrofit + porcelain pass
    dora_before = (repo / "dist" / "tools" / "dora-ict-third-party-risk-compliance-cost-calculator" / "index.html").read_text(encoding="utf-8")
    RetroReflectionEngine().retrofit_estate(repo / "dist", "gainhelm")
    compile_tenant_porcelain_estate(repo / "dist", property_id="gainhelm", repo_root=repo)
    dora_after = (repo / "dist" / "tools" / "dora-ict-third-party-risk-compliance-cost-calculator" / "index.html").read_text(encoding="utf-8")
    assert dora_before == dora_after


def test_gainhelm_stale_html_self_heals_and_edge_fulfillment_parity() -> None:
    profile = get_porcelain_tenant_profile("gainhelm")
    engine = RetroReflectionEngine()

    for slug, meta in NON_US_AUDIT_SLUGS.items():
        stale_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <title>Model | GainHelm</title>
  <link rel="canonical" href="https://gainhelm.com/tools/{slug}/">
</head>
<body>
  <main class="page-main">
    <section class="hero-section"><h1>Compliance Model</h1></section>
    <div id="calculator-workspace-anchor" class="result-card">
      <div class="card-header"><h2>Results</h2></div>
      <div class="calc-inline-cta" data-partner="vanta_security" data-status="pending" data-gsc-tier="baseline">
        <div class="calc-inline-cta-copy">
          <div>Automated SOC 2, ISO 27001 &amp; HIPAA &bull; Partner Option</div>
          <div>Vanta Automated SOC 2, CMMC &amp; ISO 27001</div>
        </div>
        <a href="/r/vanta_security?source_tool={slug}&amp;subid={slug}_inline&amp;cta_slot=calculator_result_inline" data-status="pending">Automate SOC 2, CMMC &amp; ISO 27001 with Vanta &rarr;</a>
      </div>
      <div class="calc-statutory-box">Model summary</div>
    </div>
    <section class="refinance-partner-section affiliates-section" data-gsc-tier="baseline" data-partner-roster="vanta_security,drata_compliance,sprinto_compliance,thoropass_audit,coalition_cyber_insurance,cobalt_pentest">
      <div class="partner-card" data-partner="vanta_security">
        <span class="partner-badge">Automated SOC 2, ISO 27001 &amp; HIPAA</span>
        <h3 class="partner-title">Vanta Automated SOC 2, CMMC &amp; ISO 27001</h3>
        <p>SOC 2, ISO 27001, HIPAA, and CMMC continuous monitoring.</p>
        <a href="/r/vanta_security" data-status="pending">Automate SOC 2, CMMC &amp; ISO 27001 with Vanta &rarr;</a>
      </div>
    </section>
    <section id="serp-incumbent-depth-workbench" class="serp-depth-workbench">
      <div id="partner-quote-intake-step" data-property-id="gainhelm" data-tool-slug="{slug}" data-vertical="soc2_grc_automation" data-calculated-amount="112100">
        <h3>Enterprise GRC Automation &amp; Audit Readiness Quote Intake</h3>
        <p>AICPA CPA / C3PAO assessor matching</p>
        <form><input name="email"></form>
      </div>
      <div id="multi-year-cliff-visualizer"></div>
      <div id="saveable-decision-blueprint" data-blueprint-slug="{slug}">
        <div id="blueprint-status-readout">Ready</div>
        <div id="post-calculation-upgrade-drawer" data-offer-sku="gh_soc2_cmmc_audit_workpapers" data-offer-price="79">
          <h4 class="post-calc-upgrade-title">GainHelm SOC 2 Type II, CMMC 2.0 &amp; NIST 800-171 Audit Scoping Workpaper Suite ($79 One-Time Package)</h4>
          <p class="post-calc-pillar-copy">AICPA SOC 2 Type II Median Licensed CPA Firm Examination Fee, DoD CMMC 2.0 Level 2 C3PAO, HHS OCR HIPAA</p>
        </div>
      </div>
    </section>
  </main>
</body>
</html>"""
        repaired_html, _ = engine.retrofit_html(stale_html, "gainhelm", f"tools/{slug}/index.html")
        normalized_html, _ = normalize_html_to_porcelain_shell(repaired_html, f"tools/{slug}/index.html", profile)
        soup = BeautifulSoup(normalized_html, "html.parser")
        for sel in (
            "#serp-incumbent-depth-workbench",
            "#calculator-workspace-anchor",
            ".compliance-strip",
            'section[data-first-party-checkout="true"]',
        ):
            els = soup.select(sel)
            assert els, f"Missing {sel} after self-heal on {slug}"
            for idx, el in enumerate(els):
                _assert_container_framework_clean(el, slug, f"{sel}[{idx}]")
        assert not soup.select('a[href^="/r/"]')
        assert len(soup.select("#serp-incumbent-depth-workbench")) == 1
        assert soup.select_one("#partner-quote-intake-step").get("data-vertical") == meta["vertical"]

        # Verify Python offer / upgrade / quote / affiliate / workpaper APIs
        offer = resolve_lead_monetization_offer("gainhelm", slug)
        assert offer["offer_sku"] == "gh_hipaa_iso27001_governance_kit"
        assert offer["offer_price_usd"] == 49.0
        assert not any(tok in offer["offer_title"].lower() for tok in FORBIDDEN_NON_AUDIT_TOKENS)

        # Bug 6: generic slug with explicit framework vertical inherits isolated $49 & $19 copy
        gen_offer_49 = resolve_lead_monetization_offer("gainhelm", "general", vertical=meta["vertical"])
        assert gen_offer_49["offer_sku"] == "gh_hipaa_iso27001_governance_kit"
        assert gen_offer_49["offer_price_usd"] == 49.0
        assert not any(tok in gen_offer_49["offer_title"].lower() for tok in FORBIDDEN_NON_AUDIT_TOKENS)
        assert "45 cfr 160.404" not in gen_offer_49["statutory_authority"].lower()

        gen_offer_19 = resolve_lead_monetization_offer(
            "gainhelm", "general", vertical=meta["vertical"], sku="gh_instant_compliance_worksheet_19"
        )
        assert gen_offer_19["offer_sku"] == "gh_instant_compliance_worksheet_19"
        assert gen_offer_19["offer_price_usd"] == 19.0
        assert "45 cfr 160.404" not in gen_offer_19["statutory_authority"].lower()
        assert "aicpa" not in gen_offer_19["statutory_authority"].lower()

        # Bug 7: deduplicated trend series rows
        spec = resolve_post_calculation_upgrade_spec("gainhelm", slug)
        assert len(spec["trend_series_labels"]) == len(set(spec["trend_series_labels"])), spec["trend_series_labels"]
        trend_joined = " ".join(spec["trend_series_labels"]).lower()
        assert not any(tok in trend_joined for tok in FORBIDDEN_NON_AUDIT_TOKENS), trend_joined

        wp = synthesize_personalized_audit_workpaper("gainhelm", slug, {"calculated_amount": 112100.0})
        dp_series = wp["statutory_trend_timeseries"]
        assert len(dp_series) == len({row["series_id"] for row in dp_series}), dp_series
        wp_text = json.dumps(wp["reconciliation_schedule"] + wp["sensitivity_matrix"]).lower()
        assert not any(tok in wp_text for tok in FORBIDDEN_NON_AUDIT_TOKENS), wp_text
        reg_name = str(wp["statutory_data_pack"]["regulator_name"])
        assert not any(tok in reg_name.lower() for tok in FORBIDDEN_NON_AUDIT_TOKENS), reg_name
        get_profile_fn = getattr(affiliates_mod, "get_gainhelm_framework_profile", None)
        classify_fn = getattr(affiliates_mod, "classify_gainhelm_framework", None)
        assert callable(get_profile_fn) and callable(classify_fn), "Missing GainHelm framework classifiers"
        fw_profile = get_profile_fn(slug)
        assert reg_name == fw_profile["regulator_name"]
        assert classify_fn("", meta["vertical"]) == fw_profile["framework_key"]

        explicit_79 = resolve_lead_monetization_offer("gainhelm", slug, sku="gh_soc2_cmmc_audit_workpapers")
        assert explicit_79["offer_sku"] == "gh_soc2_cmmc_audit_workpapers"
        assert explicit_79["offer_price_usd"] == 79.0
        assert "SOC 2" in explicit_79["offer_title"]

        explicit_49_on_soc2 = resolve_lead_monetization_offer("gainhelm", "soc-2-audit-cost-calculator", sku="gh_hipaa_iso27001_governance_kit")
        assert explicit_49_on_soc2["offer_sku"] == "gh_hipaa_iso27001_governance_kit"
        assert explicit_49_on_soc2["offer_price_usd"] == 49.0
        assert "CMMC" not in explicit_49_on_soc2["offer_title"]

        qt = evaluate_lead_quote_threshold("gainhelm", slug, 112100.0)
        assert qt["vertical"] == meta["vertical"]
        assert not any(tok in qt["partner_rep_desk"].lower() for tok in FORBIDDEN_NON_AUDIT_TOKENS)

        # Bug 1: framework-matched Vanta URL via both signatures
        route = get_affiliate_route("gainhelm", slug, partner_key="vanta_security")
        route_alt = get_affiliate_route("gainhelm", "vanta_security", source_tool=slug)
        assert route["url"] == route_alt["url"]
        assert "/products/soc-2" not in route["url"], route["url"]
        route_copy = f"{route['badge']} {route['partner_name']} {route['cta_text']} {route['ymyl_warning']}".lower()
        assert not any(tok in route_copy for tok in FORBIDDEN_NON_AUDIT_TOKENS), route_copy

    # Verify Bugs 1, 2, 5, 6 across FedRAMP, CCPA, HIPAA, ISO 27001, CMMC, SOC 2, etc.
    fedramp_qt = evaluate_lead_quote_threshold("gainhelm", "fedramp-authorization-3pao-cost-calculator", 120000.0)
    assert fedramp_qt["vertical"] == "fedramp_3pao_ato"
    assert "cmmc" not in fedramp_qt["partner_rep_desk"].lower()
    fedramp_wp = synthesize_personalized_audit_workpaper(
        "gainhelm", "fedramp-authorization-3pao-cost-calculator", {"calculated_amount": 120000.0}
    )
    assert "cmmc" not in fedramp_wp["html_report"].lower().replace("gh_soc2_cmmc_audit_workpapers", " ")

    ccpa_qt = evaluate_lead_quote_threshold(
        "gainhelm", "ccpa-cpra-california-privacy-compliance-and-breach-liability-calculator", 100000.0
    )
    assert ccpa_qt["vertical"] == "ccpa_cpra_privacy"
    assert ccpa_qt["primary_partner_key"] == "vanta_security"

    profiles_dict = getattr(affiliates_mod, "GAINHELM_FRAMEWORK_PROFILES", {})
    classify_fn_all = getattr(affiliates_mod, "classify_gainhelm_framework", None)
    assert profiles_dict and callable(classify_fn_all)
    for fw_k, fw_v in profiles_dict.items():
        assert classify_fn_all("", fw_v["vertical"]) == fw_k, f"Round-trip failed for {fw_k}: {fw_v['vertical']}"
        r_fw = get_affiliate_route("gainhelm", fw_v["default_sku_slug"], partner_key="vanta_security")
        assert r_fw["url"].startswith(fw_v["vanta_url"]), (fw_k, r_fw["url"], fw_v["vanta_url"])

    # Generic default compatibility (no slug + no vertical -> SOC 2 / HIPAA default preservation)
    gen_soc2 = resolve_lead_monetization_offer("gainhelm", "general")
    assert gen_soc2["offer_sku"] == "gh_soc2_cmmc_audit_workpapers"
    assert gen_soc2["offer_price_usd"] == 79.0

    # Verify Edge Redirector (/r/vanta_security & /r/vanta) + Edge Lead Capture JS parity via Node VM
    edge_redir_js = re.sub(
        r"\bexport\s+(?=async\s+function\s+onRequest)",
        "",
        generate_edge_redirect_function(property_id="gainhelm"),
    ).replace("onRequest(", "onRedirectRequest(")
    edge_js = _strip_esm_exports(generate_edge_lead_capture_function(property_id="gainhelm"))
    node_script = f"""
{edge_js}
const REDIRECT_MOD = (() => {{
  {edge_redir_js}
  return {{ onRedirectRequest }};
}})();
globalThis.fetch = async (url) => {{
  const sUrl = String(url);
  const m = sUrl.match(/api\\.stripe\\.com\\/v1\\/checkout\\/sessions\\/cs_live_PAIDFOR_([A-Za-z0-9_]+)$/);
  if (m) {{
    return new Response(JSON.stringify({{
      id: "cs_live_PAIDFOR_" + m[1], livemode: true, payment_status: "paid", amount_total: 4900,
      currency: "usd", client_reference_id: m[1], metadata: {{ lead_id: m[1] }}
    }}), {{ status: 200 }});
  }}
  if (sUrl.includes("api.stripe.com/v1/checkout/sessions")) {{
    return new Response(JSON.stringify({{ id: "cs_live_mock_post", url: "https://checkout.stripe.com/c/pay/cs_live_mock_post" }}), {{ status: 200 }});
  }}
  throw new Error("Unexpected fetch in test: " + url);
}};
const stripeEnv = {{ STRIPE_SECRET_KEY: "sk_live_mock" }};
async function run() {{
  const checks = [
    ["dora-ict-third-party-risk-compliance-cost-calculator", "gh_hipaa_iso27001_governance_kit", true, "dora_eu_ict_resilience", "https://www.vanta.com/solutions/dora"],
    ["eu-ai-act-high-risk-conformity-assessment-cost-calculator", "gh_hipaa_iso27001_governance_kit", true, "eu_ai_act_conformity", "https://www.vanta.com/solutions/ai-governance"],
    ["sec-cybersecurity-incident-materiality-8k-item-105-cost-calculator", "gh_hipaa_iso27001_governance_kit", true, "sec_cyber_disclosure", "https://www.vanta.com/platform"],
    ["iso-27001-certification-cost-calculator", "gh_hipaa_iso27001_governance_kit", false, "iso27001_isms", "https://www.vanta.com/products/iso-27001"],
    ["hipaa-violation-penalty-breach-cost-calculator", "gh_hipaa_iso27001_governance_kit", false, "hipaa_healthcare_security", "https://www.vanta.com/products/hipaa"],
    ["pci-dss-4-0-compliance-cost-calculator", "gh_hipaa_iso27001_governance_kit", false, "pci_dss_payments", "https://www.vanta.com/products/pci-dss"],
    ["hitrust-csf-e1-i1-r2-certification-cost-calculator", "gh_hipaa_iso27001_governance_kit", false, "hitrust_csf_assurance", "https://www.vanta.com/platform"],
    ["fedramp-authorization-3pao-cost-calculator", "gh_soc2_cmmc_audit_workpapers", false, "fedramp_3pao_ato", "https://www.vanta.com/solutions/fedramp"],
    ["ccpa-cpra-california-privacy-compliance-and-breach-liability-calculator", "gh_hipaa_iso27001_governance_kit", false, "ccpa_cpra_privacy", "https://www.vanta.com/platform"],
    ["cyber-liability-insurance-breach-exposure-calculator", "gh_hipaa_iso27001_governance_kit", false, "cyber_liability_underwriting", "https://www.vanta.com/platform"],
    ["cmmc-2-0-compliance-cost-calculator", "gh_soc2_cmmc_audit_workpapers", false, "cmmc_dod_defense", "https://www.vanta.com/solutions/cmmc"],
    ["soc-2-audit-cost-calculator", "gh_soc2_cmmc_audit_workpapers", false, "soc2_grc_automation", "https://www.vanta.com/products/soc-2"],
  ];
  let idx = 0;
  for (const [slug, expectedSku, strictIsolated, expectedVertical, expectedVantaBase] of checks) {{
    idx += 1;
    const lid = "lead_test_" + idx;
    const baseQs = "fulfill=1&tool_slug=" + slug + "&amount=112100&lead_id=" + lid + "&session_id=cs_live_PAIDFOR_" + lid + "&synthetic_test=1";
    const hdrs = {{ headers: {{ "x-pseofactory-test": "1" }} }};

    // 0. /r/vanta_security & /r/vanta redirect parity: fail-closed on-site hold by default,
    // and framework-isolated native destination under explicit ALLOW_UNAPPROVED_EXTERNAL_REDIRECTS=true
    for (const pAlias of ["vanta_security", "vanta"]) {{
      const defaultRes = await REDIRECT_MOD.onRedirectRequest({{
        request: new Request("https://gainhelm.com/r/" + pAlias + "?source_tool=" + slug + "&synthetic_test=1"),
        env: stripeEnv,
        params: {{ partner: pAlias }},
      }});
      if (defaultRes.status !== 302) throw new Error("Bad default /r status for " + slug + ": " + defaultRes.status);
      const defaultLoc = defaultRes.headers.get("Location") || "";
      if (!defaultLoc.startsWith("https://gainhelm.com/tools/")) {{
        throw new Error("Expected default on-site hold for /r/" + pAlias + ", got: " + defaultLoc);
      }}
      if (defaultRes.headers.get("X-Edge-Contract-Tier") !== "blocked_unapproved_partner") {{
        throw new Error("Expected blocked_unapproved_partner for /r/" + pAlias + ", got: " + defaultRes.headers.get("X-Edge-Contract-Tier"));
      }}

      const redirRes = await REDIRECT_MOD.onRedirectRequest({{
        request: new Request("https://gainhelm.com/r/" + pAlias + "?source_tool=" + slug + "&synthetic_test=1"),
        env: {{ ...stripeEnv, ALLOW_UNAPPROVED_EXTERNAL_REDIRECTS: "true" }},
        params: {{ partner: pAlias }},
      }});
      if (redirRes.status !== 302) throw new Error("Bad /r status for " + slug + ": " + redirRes.status);
      const loc = redirRes.headers.get("Location") || "";
      if (!loc.startsWith(expectedVantaBase)) {{
        throw new Error("Bad /r/" + pAlias + " Location for " + slug + ": got " + loc + " expected " + expectedVantaBase);
      }}
      if (expectedVantaBase !== "https://www.vanta.com/products/soc-2" && loc.includes("products/soc-2")) {{
        throw new Error("Leaked /products/soc-2 in /r/" + pAlias + " for " + slug + ": " + loc);
      }}
    }}

    // 1. JSON Datapack check
    const resDp = await onRequestGet({{ request: new Request("https://gainhelm.com/api/lead-capture?" + baseQs + "&format=datapack", hdrs), env: stripeEnv }});
    if (resDp.status !== 200) throw new Error("Bad datapack status " + resDp.status + " for " + slug);
    const wp = await resDp.json();
    if (!wp || wp.offer_sku !== expectedSku) throw new Error("Bad SKU for " + slug + ": " + JSON.stringify(wp));

    // 2. HTML Report check (?format=html)
    const resHtml = await onRequestGet({{ request: new Request("https://gainhelm.com/api/lead-capture?" + baseQs + "&format=html", hdrs), env: stripeEnv }});
    if (resHtml.status !== 200) throw new Error("Bad HTML status " + resHtml.status + " for " + slug);
    const htmlReport = await resHtml.text();

    // 3. CSV check (?format=csv)
    const resCsv = await onRequestGet({{ request: new Request("https://gainhelm.com/api/lead-capture?" + baseQs + "&format=csv", hdrs), env: stripeEnv }});
    if (resCsv.status !== 200) throw new Error("Bad CSV status " + resCsv.status + " for " + slug);
    const csvText = await resCsv.text();

    // 4. POST /api/lead-capture check
    const resPost = await onRequestPost({{
      request: new Request("https://gainhelm.com/api/lead-capture", {{
        method: "POST",
        headers: {{ "content-type": "application/json", "x-pseofactory-test": "1" }},
        body: JSON.stringify({{
          email: "secops@example.invalid",
          tool_slug: slug,
          partner_key: "vanta_security",
          calculated_amount: 112100,
          state: "DE",
          partner_sharing_consent: true,
          synthetic_test: true,
        }}),
      }}),
      env: stripeEnv,
    }});
    if (resPost.status !== 200) throw new Error("Bad POST status " + resPost.status + " for " + slug);
    const postJson = await resPost.json();
    if (postJson.vertical !== expectedVertical) throw new Error("Bad POST vertical for " + slug + ": " + postJson.vertical);
    if (postJson.offer_sku !== expectedSku) throw new Error("Bad POST SKU for " + slug + ": " + postJson.offer_sku);
    if (!String(postJson.live_destination_url || "").startsWith(expectedVantaBase)) {{
      throw new Error("Bad POST live_destination_url for " + slug + ": " + postJson.live_destination_url);
    }}
    if (slug.includes("fedramp") && JSON.stringify(postJson).toLowerCase().replaceAll("gh_soc2_cmmc_audit_workpapers", " ").includes("cmmc")) {{
      throw new Error("FedRAMP POST leaked cmmc: " + JSON.stringify(postJson));
    }}

    if (strictIsolated) {{
      const dpTxt = JSON.stringify({{
        offer_title: wp.offer_title,
        statutory_authority: wp.statutory_authority,
        regulator_name: wp.regulator_name,
        reconciliation_schedule: wp.reconciliation_schedule,
        sensitivity_matrix: wp.sensitivity_matrix,
        longitudinal_benchmark_series: wp.longitudinal_benchmark_series,
        statutory_execution_artifacts: wp.statutory_execution_artifacts,
      }}).toLowerCase();
      const postTxt = JSON.stringify({{
        vertical: postJson.vertical,
        partner_rep_desk: postJson.partner_rep_desk,
        live_destination_url: postJson.live_destination_url,
        offer_title: postJson.offer_title,
        reconciliation_schedule: postJson.reconciliation_schedule,
      }}).toLowerCase();
      const htmlClean = htmlReport.toLowerCase().replaceAll("gh_hipaa_iso27001_governance_kit", " ");
      const csvClean = csvText.toLowerCase();
      for (const [label, blob] of [["datapack", dpTxt], ["html", htmlClean], ["csv", csvClean], ["post", postTxt]]) {{
        for (const tok of ["soc 2", "soc2", "cmmc", "c3pao", "aicpa", "hipaa", "45 cfr 160.404"]) {{
          if (blob.includes(tok)) throw new Error("Edge " + label + " leak '" + tok + "' on " + slug);
        }}
      }}
    }}
  }}
  console.log("EDGE_ISOLATION_OK");
}}
run().catch((err) => {{ console.error(err); process.exit(1); }});
"""
    proc = subprocess.run(["node", "-"], input=node_script, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"Node Edge check failed:\n{proc.stdout}\n{proc.stderr}"
    assert "EDGE_ISOLATION_OK" in proc.stdout


def _inject_legacy_gainhelm_drift(html_txt: str, slug: str) -> str:
    """Builds an unhealed pre-Stage-3b legacy fixture with $79 SOC 2 / CMMC drift."""
    from pseofactory.visual_primitives import _find_balanced_div_span

    mutated = html_txt
    replacements = (
        (
            "id",
            "post-calculation-upgrade-drawer",
            (
                f'<div id="post-calculation-upgrade-drawer" class="post-calc-upgrade-drawer" '
                f'data-mechanic="post_calculation_workpaper_upgrade" data-property-id="gainhelm" '
                f'data-tool-slug="{slug}" data-offer-sku="gh_soc2_cmmc_audit_workpapers" '
                f'data-offer-price="79">'
                f'<h4 class="post-calc-upgrade-title">GainHelm SOC 2 Type II, CMMC 2.0 &amp; NIST 800-171 '
                f'Audit Scoping Workpaper Suite ($79 One-Time Package)</h4>'
                f'<p class="post-calc-pillar-copy">AICPA SOC 2 Type II CPA Firm Fee, DoD CMMC 2.0 C3PAO, '
                f'HHS OCR HIPAA</p></div>'
            ),
        ),
        (
            "id",
            "calc-result-quick-unlock-bar",
            (
                '<div id="calc-result-quick-unlock-bar" class="calc-result-quick-unlock-bar" '
                'data-contextual-v2="1" data-offer-sku="gh_soc2_cmmc_audit_workpapers" '
                'data-offer-price="79"><div>SOC 2 Type II &amp; CMMC 2.0 Audit Scope ($79)</div></div>'
            ),
        ),
        (
            "class",
            "calc-inline-cta",
            (
                '<div class="calc-inline-cta" data-partner="vanta_security">'
                '<div class="calc-inline-cta-copy"><div>Automated SOC 2, ISO 27001 &amp; HIPAA</div>'
                '<div>Vanta Trust Management</div></div>'
                '<a href="/r/vanta_security">Automate with Vanta &rarr;</a></div>'
            ),
        ),
    )
    for attr_name, target_val, legacy_block in replacements:
        span = _find_balanced_div_span(mutated, target_val, attr_name=attr_name)
        if span is not None:
            mutated = mutated[: span[0]] + legacy_block + mutated[span[1] :]
        elif target_val == "calc-inline-cta":
            # Post-847424d GainHelm hides unapproved /r/ .calc-inline-cta; inject stale legacy CTA
            # inside .result-box (its authentic pre-847424d DOM location) to test full legacy drift healing.
            rb_span = _find_balanced_div_span(mutated, "result-box", attr_name="class")
            assert rb_span is not None, f"Missing class=result-box in live fixture {slug}"
            close_idx = mutated.rfind("</div>", rb_span[0], rb_span[1])
            assert close_idx != -1, f"Missing closing </div> for result-box in live fixture {slug}"
            mutated = mutated[:close_idx] + "\n" + legacy_block + "\n" + mutated[close_idx:]
        else:
            assert span is not None, f"Missing {attr_name}={target_val} in live fixture {slug}"

    pro_span = _find_balanced_div_span(mutated, "pro-hook-card", attr_name="class")
    if pro_span is not None:
        pro_block = mutated[pro_span[0] : pro_span[1]]
        pro_block = (
            pro_block.replace("gh_hipaa_iso27001_governance_kit", "gh_soc2_cmmc_audit_workpapers")
            .replace('data-offer-price="49"', 'data-offer-price="79"')
            .replace("($49)", "($79)")
            .replace("Locked: $49", "Locked: $79")
        )
        pro_block = re.sub(
            r"<span>[\s\S]*?</span>",
            "<span><strong>Statutory Audit Workpaper:</strong> Export SOC 2 Type II, CMMC 2.0 &amp; HIPAA Schedule</span>",
            pro_block,
            count=1,
            flags=re.IGNORECASE,
        )
        mutated = mutated[: pro_span[0]] + pro_block + mutated[pro_span[1] :]
    else:
        legacy_pro_card = (
            '<div class="pro-hook-card">'
            "<span><strong>Statutory Audit Workpaper:</strong> Export SOC 2 Type II, CMMC 2.0 &amp; HIPAA Schedule</span>"
            '<a href="#post-calculation-upgrade-drawer" class="pro-hook-link touch-target" data-checkout-nav="1">'
            "Export Audit Workpaper ($79) &rarr;</a>"
            '<div class="pro-hook-sample-unlock" data-mechanic="above_fold_packet_sample_unlock">'
            "<div><strong>Unlocked Sample Preview ($57,590 SOC 2 Baseline):</strong> "
            "Line 1 SOC 2 Type II &amp; CMMC Schedule (Locked: $79)</div>"
            '<div><a href="/api/lead-capture?checkout=1&amp;sku=gh_soc2_cmmc_audit_workpapers'
            f'&amp;tool_slug={slug}&amp;amount=57590&amp;redirect=1" rel="nofollow" '
            'class="pro-hook-direct-checkout btn-primary touch-target" data-checkout-trigger="1" '
            'data-offer-sku="gh_soc2_cmmc_audit_workpapers" data-offer-price="79">'
            "Instant Checkout &amp; Download ($79) &rarr;</a></div>"
            "</div></div>"
        )
        cta_span = _find_balanced_div_span(mutated, "calc-inline-cta", attr_name="class")
        assert cta_span is not None, f"Missing injected class=calc-inline-cta in live fixture {slug}"
        mutated = mutated[: cta_span[1]] + "\n" + legacy_pro_card + mutated[cta_span[1] :]

    mutated = re.sub(
        r'(<div\b[^>]*id=["\']partner-quote-intake-step["\'][^>]*\bdata-vertical=["\'])[^"\']+(["\'])',
        r"\1soc2_grc_automation\2",
        mutated,
        count=1,
        flags=re.IGNORECASE,
    )
    return mutated


@pytest.mark.host_estate
def test_gainhelm_live_preexisting_html_heals_via_retrofit_html_and_retrofit_estate(tmp_path: Path) -> None:
    engine = RetroReflectionEngine()

    for slug, meta in NON_US_AUDIT_SLUGS.items():
        live_html_path = LIVE_GAINHELM_REPO / "dist" / "tools" / slug / "index.html"
        assert live_html_path.is_file(), f"Missing live fixture {live_html_path}"
        orig_live_html = live_html_path.read_text(encoding="utf-8")

        # 1a. Verify live gainhelm/dist HTML converges cleanly via retrofit_html & retrofit_estate
        needs_live_repair = bool(
            engine._gainhelm_needs_framework_isolation_heal(orig_live_html, slug)
            or engine.audit_html_mechanics(orig_live_html)
        )
        healed_live, repaired_live = engine.retrofit_html(
            orig_live_html,
            property_id="gainhelm",
            slug=slug,
        )
        if needs_live_repair:
            assert repaired_live, f"Expected non-empty repairs on unhealed live {slug}"
        _assert_live_fixture_healed(healed_live, slug, meta["vertical"], require_pro_hook=False)
        healed_live_second, repaired_live_second = engine.retrofit_html(
            healed_live,
            property_id="gainhelm",
            slug=slug,
        )
        assert repaired_live_second == []
        assert healed_live_second == healed_live

        live_copy_dist = tmp_path / f"live_estate_{slug[:12]}" / "dist"
        live_copy_tool = live_copy_dist / "tools" / slug
        live_copy_tool.mkdir(parents=True, exist_ok=True)
        (live_copy_tool / "index.html").write_text(orig_live_html, encoding="utf-8")
        engine.retrofit_estate(live_copy_dist, "gainhelm")
        live_estate_html = (live_copy_tool / "index.html").read_text(encoding="utf-8")
        _assert_live_fixture_healed(live_estate_html, slug, meta["vertical"], require_pro_hook=False)
        _, live_estate_html_repairs = engine.retrofit_html(
            live_estate_html,
            property_id="gainhelm",
            slug=slug,
        )
        assert live_estate_html_repairs == []
        live_estate_second = engine.retrofit_estate(live_copy_dist, "gainhelm")
        assert f"tools/{slug}/index.html" not in live_estate_second["retrofitted_paths"]

        # 1b. Verify single-file RetroReflectionEngine.retrofit_html heals explicit unhealed legacy HTML
        #     (even when mechanical primitives already exist and audit_html_mechanics returns []).
        legacy_html = _inject_legacy_gainhelm_drift(orig_live_html, slug)
        healed_single, repaired_single = engine.retrofit_html(
            legacy_html,
            property_id="gainhelm",
            slug=slug,
        )
        assert repaired_single, f"Expected non-empty repairs on legacy fixture {slug}"
        _assert_live_fixture_healed(healed_single, slug, meta["vertical"])

        # Strict idempotency: second call on already-healed HTML returns empty repaired list and identical HTML
        healed_second, repaired_second = engine.retrofit_html(
            healed_single,
            property_id="gainhelm",
            slug=slug,
        )
        assert repaired_second == []
        assert healed_second == healed_single

        # 2. Verify RetroReflectionEngine.retrofit_estate also heals overlaid legacy HTML
        #    where .calc-inline-cta was already cleaned but #post-calculation-upgrade-drawer + .pro-hook-card
        #    (with href before class and data-offer-price before data-offer-sku) remain stale $79.
        overlaid_html = re.sub(
            r'(<div\b[^>]*class=["\'][^"\']*\bcalc-inline-cta\b[^"\']*["\'][^>]*>)[\s\S]*?(</div>\s*<a[^>]*>[\s\S]*?</a>\s*</div>)',
            r'\1<div class="calc-inline-cta-copy"><div>EU GRC Automation &bull; Partner Option</div><div>Vanta Trust Management</div></div><a href="/r/vanta_security">Automate with Vanta &rarr;</a></div>',
            legacy_html,
            count=1,
            flags=re.IGNORECASE,
        )
        overlaid_html = re.sub(
            r'data-offer-sku="gh_soc2_cmmc_audit_workpapers"\s+data-offer-price="79"',
            'data-offer-price="79" data-offer-sku="gh_soc2_cmmc_audit_workpapers"',
            overlaid_html,
        )
        dist_dir = tmp_path / f"estate_{slug[:12]}" / "dist"
        tool_dir = dist_dir / "tools" / slug
        tool_dir.mkdir(parents=True, exist_ok=True)
        (tool_dir / "index.html").write_text(overlaid_html, encoding="utf-8")

        engine.retrofit_estate(dist_dir, "gainhelm")
        estate_healed = (tool_dir / "index.html").read_text(encoding="utf-8")
        _assert_live_fixture_healed(estate_healed, slug, meta["vertical"])
        _, estate_repaired_second = engine.retrofit_html(
            estate_healed,
            property_id="gainhelm",
            slug=slug,
        )
        assert estate_repaired_second == []

    # Bug 3 + Bug 4 adversarial probes
    from pseofactory.visual_primitives import _find_balanced_div_span

    adv_slug = "dora-ict-third-party-risk-compliance-cost-calculator"
    adv_base = _inject_legacy_gainhelm_drift(
        (LIVE_GAINHELM_REPO / "dist" / "tools" / adv_slug / "index.html").read_text(encoding="utf-8"),
        adv_slug,
    )
    adv_clean, _ = engine.retrofit_html(adv_base, property_id="gainhelm", slug=adv_slug)
    drawer_sp = _find_balanced_div_span(adv_clean, "post-calculation-upgrade-drawer", attr_name="id")
    assert drawer_sp is not None

    # Bug 3 isolated probe: drawer has generic non-leaking text, but stale $79/gh_soc2_cmmc_audit_workpapers attributes
    attr_only_html = (
        adv_clean[: drawer_sp[0]]
        + '<div id="post-calculation-upgrade-drawer" data-offer-sku="gh_soc2_cmmc_audit_workpapers" data-offer-price="79">'
        + '<h4 class="post-calc-upgrade-title">DORA Compliance Data Pack ($79)</h4>'
        + "<p>Generic readiness summary</p></div>"
        + adv_clean[drawer_sp[1] :]
    )
    attr_healed, attr_repairs = engine.retrofit_html(attr_only_html, property_id="gainhelm", slug=adv_slug)
    assert attr_repairs, "Stale attribute-only drawer must trigger retrofit_html repair"
    _assert_live_fixture_healed(attr_healed, adv_slug, "dora_eu_ict_resilience")

    # Bug 4 probe: stale outer .pro-hook-card span, duplicate .pro-hook-card & .calc-inline-cta,
    # plus outer SOC 2 leak inside #serp-incumbent-depth-workbench that already carries data-mechanic="serp_incumbent_depth_upgrade"
    adv_html = attr_only_html.replace(
        '<div class="pro-hook-card"',
        '<div class="pro-hook-card" data-dup="true"><span>Export SOC 2 Type II, CMMC 2.0 &amp; HIPAA Schedule ($79)</span><a href="#lead-capture-form" class="pro-hook-link">Export ($79)</a></div><div class="pro-hook-card"',
        1,
    ).replace(
        '<div id="multi-year-cliff-visualizer"',
        '<p class="stale-outer-workbench-note">Legacy AICPA SOC 2 &amp; CMMC Level 2 comparison note</p><div id="multi-year-cliff-visualizer"',
        1,
    )
    if '<div class="calc-inline-cta"' in adv_html:
        adv_html = adv_html.replace(
            '<div class="calc-inline-cta"',
            '<div class="calc-inline-cta" data-partner="vanta_security"><div>Automated SOC 2, ISO 27001 &amp; HIPAA</div><a href="/r/vanta_security">SOC 2</a></div><div class="calc-inline-cta"',
            1,
        )
    else:
        adv_html = adv_html.replace(
            '<div class="pro-hook-card"',
            '<div class="calc-inline-cta" data-partner="vanta_security"><div>Automated SOC 2, ISO 27001 &amp; HIPAA</div><a href="/r/vanta_security">SOC 2</a></div><div class="pro-hook-card"',
            1,
        )
    adv_healed, adv_repairs = engine.retrofit_html(adv_html, property_id="gainhelm", slug=adv_slug)
    assert adv_repairs, "Adversarial workbench/duplicate fixture must trigger retrofit_html repairs"
    assert "serp_incumbent_depth_upgrade" in adv_repairs
    _assert_live_fixture_healed(adv_healed, adv_slug, "dora_eu_ict_resilience")


def _assert_live_fixture_healed(
    html_txt: str,
    slug: str,
    expected_vertical: str,
    *,
    require_pro_hook: bool = True,
) -> None:
    soup = BeautifulSoup(html_txt, "html.parser")
    required_selectors = [
        "#serp-incumbent-depth-workbench",
        "#calculator-workspace-anchor",
        "#partner-quote-intake-step",
        "#post-calculation-upgrade-drawer",
        "#calc-result-quick-unlock-bar",
        ".compliance-strip",
        'section[data-first-party-checkout="true"]',
    ]
    if require_pro_hook:
        required_selectors.append(".pro-hook-card")
    for sel in required_selectors:
        els = soup.select(sel)
        assert els, f"Missing {sel} after healing live {slug}"
        for idx, el in enumerate(els):
            _assert_container_framework_clean(el, slug, f"{sel}[{idx}]")
    if not require_pro_hook:
        for idx, el in enumerate(soup.select(".pro-hook-card")):
            _assert_container_framework_clean(el, slug, f".pro-hook-card[{idx}]")
    assert not soup.select('a[href^="/r/"]')

    assert len(soup.select("#serp-incumbent-depth-workbench")) == 1
    quote_step = soup.select_one("#partner-quote-intake-step")
    assert quote_step.get("data-vertical") == expected_vertical

    drawer = soup.select_one("#post-calculation-upgrade-drawer")
    assert drawer.get("data-offer-sku") == "gh_hipaa_iso27001_governance_kit"
    assert drawer.get("data-offer-price") == "49"

    for pro_card in soup.select(".pro-hook-card"):
        pro_link = pro_card.select_one("a.pro-hook-link")
        assert pro_link is not None
        assert "($49)" in pro_link.get_text(" ", strip=True)
        assert "($79)" not in pro_card.get_text(" ", strip=True)

        direct_chk = pro_card.select_one("a.pro-hook-direct-checkout")
        assert direct_chk is not None
        assert "sku=gh_hipaa_iso27001_governance_kit" in (direct_chk.get("href") or "")
        assert direct_chk.get("data-offer-sku") == "gh_hipaa_iso27001_governance_kit"
        assert direct_chk.get("data-offer-price") == "49"
        assert "($49)" in direct_chk.get_text(" ", strip=True)

    quick_bar = soup.select_one("#calc-result-quick-unlock-bar")
    assert "($49)" in quick_bar.get_text(" ", strip=True)
    assert "($79)" not in quick_bar.get_text(" ", strip=True)


_PHASE2_FW_CASES: dict = {
    "dora": {
        "slug": "dora-ict-third-party-risk-compliance-cost-calculator",
        "offer_sku": "gh_hipaa_iso27001_governance_kit",
        "vertical": "dora_eu_ict_resilience",
        "primary_partner_key": "vanta_security",
        "partner_rep_desk": "Vanta EU DORA & Enterprise GRC Automation Desk",
        "vanta_url": "https://www.vanta.com/solutions/dora",
        "statutory_authority": "Regulation (EU) 2022/2554 (DORA Articles 5-30), Commission Delegated Regulation (EU) 2024/1772 & EBA/ESMA/EIOPA RTS",
        "forbidden": ("soc 2", "soc2", "cmmc", "c3pao", "aicpa", "hipaa"),
        "strict_isolated": True,
    },
    "eu_ai_act": {
        "slug": "eu-ai-act-high-risk-conformity-assessment-cost-calculator",
        "offer_sku": "gh_hipaa_iso27001_governance_kit",
        "vertical": "eu_ai_act_conformity",
        "primary_partner_key": "vanta_security",
        "partner_rep_desk": "Vanta AI Governance & EU AI Act Readiness Desk",
        "vanta_url": "https://www.vanta.com/solutions/ai-governance",
        "statutory_authority": "Regulation (EU) 2024/1689 (EU AI Act Annex III, Articles 9-17, 43 & 99) & ISO/IEC 42001:2023",
        "forbidden": ("soc 2", "soc2", "cmmc", "c3pao", "aicpa", "hipaa"),
        "strict_isolated": True,
    },
    "sec_8k": {
        "slug": "sec-cybersecurity-incident-materiality-8k-item-105-cost-calculator",
        "offer_sku": "gh_hipaa_iso27001_governance_kit",
        "vertical": "sec_cyber_disclosure",
        "primary_partner_key": "vanta_security",
        "partner_rep_desk": "Vanta SEC Reg S-K Item 106 & Cyber Governance Desk",
        "vanta_url": "https://www.vanta.com/platform",
        "statutory_authority": "17 CFR 229.106 (Reg S-K Item 106), 17 CFR 249.308 (Form 8-K Item 1.05) & SEC Release 33-11216",
        "forbidden": ("soc 2", "soc2", "cmmc", "c3pao", "aicpa", "hipaa"),
        "strict_isolated": True,
    },
    "gdpr": {
        "slug": "gdpr-data-privacy-compliance-and-article-83-fine-exposure-calculator",
        "offer_sku": "gh_hipaa_iso27001_governance_kit",
        "vertical": "eu_gdpr_privacy",
        "primary_partner_key": "vanta_security",
        "partner_rep_desk": "Vanta GDPR & EU Privacy Automation Desk",
        "vanta_url": "https://www.vanta.com/products/gdpr",
        "statutory_authority": "Regulation (EU) 2016/679 (GDPR Articles 30, 32, 35 & 83) & EDPB Fining Guidelines 04/2022",
        "forbidden": ("soc 2", "soc2", "cmmc", "c3pao", "aicpa", "hipaa"),
        "strict_isolated": True,
    },
    "ccpa": {
        "slug": "ccpa-cpra-california-privacy-compliance-and-breach-liability-calculator",
        "offer_sku": "gh_hipaa_iso27001_governance_kit",
        "vertical": "ccpa_cpra_privacy",
        "primary_partner_key": "vanta_security",
        "partner_rep_desk": "Vanta CCPA/CPRA & Consumer Privacy Automation Desk",
        "vanta_url": "https://www.vanta.com/platform",
        "statutory_authority": "Cal. Civ. Code 1798.100 et seq. (CCPA/CPRA) & 11 CCR 7000 et seq.",
        "forbidden": ("soc 2", "soc2", "cmmc", "c3pao", "aicpa", "hipaa"),
        "strict_isolated": True,
    },
    "nis2": {
        "slug": "nis2-directive-cybersecurity-compliance-and-fine-calculator",
        "offer_sku": "gh_hipaa_iso27001_governance_kit",
        "vertical": "eu_nis2_resilience",
        "primary_partner_key": "vanta_security",
        "partner_rep_desk": "Vanta EU NIS2 & Critical Infrastructure GRC Desk",
        "vanta_url": "https://www.vanta.com/platform",
        "statutory_authority": "Directive (EU) 2022/2555 (NIS2 Articles 20, 21, 23 & 34) & National Member State Transpositions",
        "forbidden": ("soc 2", "soc2", "cmmc", "c3pao", "aicpa", "hipaa"),
        "strict_isolated": True,
    },
    "iso_27001": {
        "slug": "iso-27001-certification-cost-calculator",
        "offer_sku": "gh_hipaa_iso27001_governance_kit",
        "vertical": "iso27001_isms",
        "primary_partner_key": "thoropass_audit",
        "partner_rep_desk": "Thoropass & Vanta ISO/IEC 27001:2022 ISMS Desk",
        "vanta_url": "https://www.vanta.com/products/iso-27001",
        "statutory_authority": "ISO/IEC 27001:2022, ISO/IEC 27006-1:2024 & IAF MD 5 Auditor-Day Rules",
        "forbidden": ("cmmc", "c3pao", "hipaa", "aicpa"),
        "strict_isolated": False,
    },
    "hipaa": {
        "slug": "hipaa-violation-penalty-breach-cost-calculator",
        "offer_sku": "gh_hipaa_iso27001_governance_kit",
        "vertical": "hipaa_healthcare_security",
        "primary_partner_key": "vanta_security",
        "partner_rep_desk": "Vanta HIPAA & Healthcare Security Compliance Desk",
        "vanta_url": "https://www.vanta.com/products/hipaa",
        "statutory_authority": "45 CFR 160.404 (HIPAA CMP Tiers 1-4), 45 CFR Part 164 & 45 CFR 102.3 Inflation Index",
        "forbidden": ("cmmc", "c3pao", "aicpa", "soc 2", "soc2"),
        "strict_isolated": False,
    },
    "pci_dss": {
        "slug": "pci-dss-4-0-compliance-cost-calculator",
        "offer_sku": "gh_hipaa_iso27001_governance_kit",
        "vertical": "pci_dss_payments",
        "primary_partner_key": "cobalt_pentest",
        "partner_rep_desk": "Cobalt & Vanta PCI DSS v4.0.1 Readiness Desk",
        "vanta_url": "https://www.vanta.com/products/pci-dss",
        "statutory_authority": "PCI Security Standards Council PCI DSS v4.0.1 (Requirements 1-12, Req 11.4 & 12.10)",
        "forbidden": ("cmmc", "c3pao", "hipaa"),
        "strict_isolated": False,
    },
    "hitrust": {
        "slug": "hitrust-csf-e1-i1-r2-certification-cost-calculator",
        "offer_sku": "gh_hipaa_iso27001_governance_kit",
        "vertical": "hitrust_csf_assurance",
        "primary_partner_key": "thoropass_audit",
        "partner_rep_desk": "Thoropass & Vanta HITRUST CSF e1/i1/r2 Assessment Desk",
        "vanta_url": "https://www.vanta.com/platform",
        "statutory_authority": "HITRUST CSF v11 (e1, i1, and r2 Validated Assessment & MyCSF Licensing Framework)",
        "forbidden": ("cmmc", "c3pao", "aicpa"),
        "strict_isolated": False,
    },
    "cyber_insurance": {
        "slug": "cyber-liability-insurance-breach-exposure-calculator",
        "offer_sku": "gh_hipaa_iso27001_governance_kit",
        "vertical": "cyber_liability_underwriting",
        "primary_partner_key": "coalition_cyber_insurance",
        "partner_rep_desk": "Coalition Active Cyber Insurance & GRC Underwriting Desk",
        "vanta_url": "https://www.vanta.com/platform",
        "statutory_authority": "NAIC Cyber Insurance Market Data, State Breach Notification Statutes & IBM/Ponemon Cost Factors",
        "forbidden": ("cmmc", "c3pao", "aicpa"),
        "strict_isolated": False,
    },
    "fedramp": {
        "slug": "fedramp-authorization-3pao-cost-calculator",
        "offer_sku": "gh_soc2_cmmc_audit_workpapers",
        "vertical": "fedramp_3pao_ato",
        "primary_partner_key": "drata_compliance",
        "partner_rep_desk": "Drata FedRAMP & 3PAO ATO Readiness Desk",
        "vanta_url": "https://www.vanta.com/solutions/fedramp",
        "statutory_authority": "NIST SP 800-53 Rev 5, FedRAMP Rev 5 Baselines & OMB M-24-15 Authorization Policy",
        "forbidden": ("cmmc", "c3pao", "hipaa", "soc 2", "soc2", "aicpa"),
        "strict_isolated": False,
    },
    "pentest": {
        "slug": "penetration-testing-scoping-cost-calculator",
        "offer_sku": "gh_soc2_cmmc_audit_workpapers",
        "vertical": "offensive_security_pentest",
        "primary_partner_key": "cobalt_pentest",
        "partner_rep_desk": "Cobalt CREST & OSCP PtaaS Scoping Desk",
        "vanta_url": "https://www.vanta.com/platform",
        "statutory_authority": "NIST SP 800-115, PTES Execution Standard, OWASP ASVS v4 & PCI Req 11.4",
        "forbidden": ("cmmc", "c3pao", "hipaa", "aicpa"),
        "strict_isolated": False,
    },
    "cmmc": {
        "slug": "cmmc-2-0-compliance-cost-calculator",
        "offer_sku": "gh_soc2_cmmc_audit_workpapers",
        "vertical": "cmmc_dod_defense",
        "primary_partner_key": "drata_compliance",
        "partner_rep_desk": "Drata CMMC 2.0 & C3PAO Readiness Desk",
        "vanta_url": "https://www.vanta.com/solutions/cmmc",
        "statutory_authority": "32 CFR Part 170 (CMMC 2.0), DFARS 252.204-7012/7021 & NIST SP 800-171 Rev 2",
        "forbidden": (),
        "strict_isolated": False,
    },
    "soc2": {
        "slug": "soc-2-audit-cost-calculator",
        "offer_sku": "gh_soc2_cmmc_audit_workpapers",
        "vertical": "soc2_grc_automation",
        "primary_partner_key": "vanta_security",
        "partner_rep_desk": "Vanta Trust Management & SOC 2 Audit Desk",
        "vanta_url": "https://www.vanta.com/products/soc-2",
        "statutory_authority": "AICPA SSAE 18 (AT-C Section 205), Trust Services Criteria (TSP Section 100) & 32 CFR Part 170",
        "forbidden": (),
        "strict_isolated": False,
    },
}


def _blob_has_forbidden_tokens(html_or_text: str, forbidden: tuple[str, ...]) -> bool:
    if not forbidden or not html_or_text:
        return False
    cleaned = re.sub(r"<script\b[^>]*>.*?</script>", " ", html_or_text, flags=re.S | re.I)
    cleaned = re.sub(r"<style\b[^>]*>.*?</style>", " ", cleaned, flags=re.S | re.I)
    vert_vals = " ".join(re.findall(r'data-vertical=["\']([^"\']+)["\']', cleaned, flags=re.I))
    visible = re.sub(r"<[^>]+>", " ", cleaned)
    combined = f"{visible} {vert_vals}".lower()
    for sku in SKU_IDS:
        combined = combined.replace(sku, " ")
    return any(tok in combined for tok in forbidden)


def test_gainhelm_workpaper_trends_deduplicate_bls_and_block_cross_leaks() -> None:
    """Verifies WITH_DB and FALLBACK_ONLY trend resolution never emits duplicate BLS rows or foreign leaks."""
    import inspect
    import pseofactory.partner_tracker as pt

    ts_params = inspect.signature(pt._resolve_trend_statutory_timeseries_for_workpaper).parameters
    assert "vertical" in ts_params, "_resolve_trend_statutory_timeseries_for_workpaper missing vertical parameter"

    orig_cache = pt._WORKPAPER_TREND_SERIES_CACHE.get("gainhelm")
    try:
        for mode in ("WITH_DB", "FALLBACK_ONLY"):
            if mode == "FALLBACK_ONLY":
                pt._WORKPAPER_TREND_SERIES_CACHE["gainhelm"] = []
            else:
                pt._WORKPAPER_TREND_SERIES_CACHE.pop("gainhelm", None)

            for fw, prof in _PHASE2_FW_CASES.items():
                rows = pt._resolve_trend_statutory_timeseries_for_workpaper(
                    "gainhelm",
                    prof["slug"],
                    prof["offer_sku"],
                    vertical=prof["vertical"],
                )
                sids = [r["series_id"] for r in rows]
                bls_rows = [s for s in sids if "bls_soc_15_1212" in s]
                assert len(bls_rows) <= 1, f"{mode} {fw} emitted duplicate BLS rows: {sids}"
                assert len(rows) >= 3, f"{mode} {fw} returned fewer than 3 trend rows: {sids}"
                if fw == "soc2":
                    assert "fred_cpilfesl_inflation" in sids, f"{mode} soc2 displaced inflation: {sids}"
                if fw in ("iso_27001", "pentest"):
                    assert not any("aicpa" in s or "soc2" in s for s in sids), f"{mode} {fw} leaked AICPA/SOC2: {sids}"
                if fw in ("ccpa", "gdpr", "nis2"):
                    assert not any(
                        tok in s for s in sids for tok in ("dora", "hipaa", "soc2", "cmmc", "aicpa")
                    ), f"{mode} {fw} leaked foreign trend: {sids}"
                if fw in ("hitrust", "cyber_insurance"):
                    assert not any(
                        tok in s for s in sids for tok in ("hipaa", "cmmc", "aicpa", "dora")
                    ), f"{mode} {fw} leaked foreign trend: {sids}"
    finally:
        if orig_cache is None:
            pt._WORKPAPER_TREND_SERIES_CACHE.pop("gainhelm", None)
        else:
            pt._WORKPAPER_TREND_SERIES_CACHE["gainhelm"] = orig_cache


def test_gainhelm_unqualified_slug_affiliate_route_matches_primary_partner() -> None:
    """Verifies get_affiliate_route and resolve_optimal_partner_for_slug agree with framework profiles."""
    from pseofactory.affiliates import get_affiliate_route, resolve_optimal_partner_for_slug

    for fw, prof in _PHASE2_FW_CASES.items():
        slug = prof["slug"]
        route = get_affiliate_route("gainhelm", slug)
        optimal = resolve_optimal_partner_for_slug("gainhelm", slug)
        assert route["partner_key"] == prof["primary_partner_key"], f"{fw}: {route}"
        assert optimal is not None and optimal.key == prof["primary_partner_key"], f"{fw}: {optimal}"
        if prof["primary_partner_key"] == "vanta_security":
            assert route["url"].startswith(prof["vanta_url"]), f"{fw}: {route}"


def test_edge_cmmc_bundle_and_post_partner_key_desk_parity(tmp_path: Path) -> None:
    """Verifies Edge Worker CMMC fulfillment isolation and POST omitted/alias partner_key parity."""
    from pseofactory.edge import generate_edge_lead_capture_function

    edge_js = _strip_esm_exports(
        generate_edge_lead_capture_function(property_id="gainhelm")
    )
    fw_expectations = json.dumps(
        {
            k: {
                "slug": v["slug"],
                "pk": v["primary_partner_key"],
                "desk": v["partner_rep_desk"],
                "vurl": v["vanta_url"],
            }
            for k, v in _PHASE2_FW_CASES.items()
        }
    )
    node_script = tmp_path / "edge_cmmc_and_post_check.mjs"
    node_script.write_text(
        edge_js
        + f"""
globalThis.fetch = async (url) => {{
  const sUrl = String(url);
  const m = sUrl.match(/api\\.stripe\\.com\\/v1\\/checkout\\/sessions\\/cs_live_PAIDFOR_([A-Za-z0-9_]+)$/);
  if (m) {{
    return new Response(JSON.stringify({{
      id: "cs_live_PAIDFOR_" + m[1],
      livemode: true,
      payment_status: "paid",
      amount_total: 7900,
      currency: "usd",
      client_reference_id: m[1],
      metadata: {{ lead_id: m[1] }},
    }}), {{ status: 200 }});
  }}
  if (sUrl.includes("api.stripe.com/v1/checkout/sessions")) {{
    return new Response(JSON.stringify({{
      id: "cs_live_mock_post",
      url: "https://checkout.stripe.com/c/pay/cs_live_mock_post",
    }}), {{ status: 200 }});
  }}
  throw new Error("Unexpected fetch: " + url);
}};
const env = {{ STRIPE_SECRET_KEY: "sk_live_mock" }};
const fwExpected = {fw_expectations};
const aliases = {{
  vanta: "vanta_security",
  vanta_compliance: "vanta_security",
  drata: "drata_compliance",
  sprinto: "sprinto_compliance",
  sprinto_grc: "sprinto_compliance",
  thoropass: "thoropass_audit",
  coalition: "coalition_cyber_insurance",
  cobalt: "cobalt_pentest",
}};
const deskTokens = {{
  vanta_security: "Vanta",
  drata_compliance: "Drata",
  sprinto_compliance: "Sprinto",
  thoropass_audit: "Thoropass",
  coalition_cyber_insurance: "Coalition",
  cobalt_pentest: "Cobalt",
}};
async function run() {{
  for (const fmt of ["datapack", "csv", "html"]) {{
    const res = await onRequestGet({{
      request: new Request(`https://gainhelm.com/api/lead-capture?fulfill=1&sku=gh_soc2_cmmc_audit_workpapers&tool_slug=cmmc-2-0-compliance-cost-calculator&amount=132000&lead_id=lead_cmmc_check&session_id=cs_live_PAIDFOR_lead_cmmc_check&format=${{fmt}}&synthetic_test=1`),
      env,
    }});
    if (res.status !== 200) throw new Error(`CMMC ${{fmt}} HTTP ${{res.status}}`);
    const txt = await res.text();
    const low = txt.toLowerCase();
    if (low.includes("hipaa") || low.includes("hhs ocr") || low.includes("aicpa")) {{
      throw new Error(`CMMC ${{fmt}} cross-framework leak: ${{txt.slice(0, 300)}}`);
    }}
    if (fmt === "datapack") {{
      const dp = JSON.parse(txt);
      if (dp.regulator_name !== "DoD CIO, Cyber-AB & Authorized C3PAO Assessors") {{
        throw new Error(`CMMC regulator mismatch: ${{dp.regulator_name}}`);
      }}
    }}
  }}
  for (const [fw, exp] of Object.entries(fwExpected)) {{
    const resOmit = await onRequestPost({{
      request: new Request("https://gainhelm.com/api/lead-capture", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{
          tool_slug: exp.slug,
          email: "ciso@enterprise-check.com",
          state: "CA",
          calculated_amount: 82000,
          partner_sharing_consent: true,
          synthetic_test: true,
        }}),
      }}),
      env,
    }});
    const outOmit = await resOmit.json();
    if (outOmit.partner_key !== exp.pk || outOmit.partner_rep_desk !== exp.desk || !outOmit.redirect_url.startsWith(`/r/${{exp.pk}}?`)) {{
      throw new Error(`Omitted partner mismatch (${{fw}}): ${{JSON.stringify(outOmit)}}`);
    }}
    if (exp.pk === "vanta_security" && !outOmit.live_destination_url.startsWith(exp.vurl)) {{
      throw new Error(`Omitted vanta URL mismatch (${{fw}}): ${{outOmit.live_destination_url}}`);
    }}
  }}
  for (const [alias, canon] of Object.entries(aliases)) {{
    const resAlias = await onRequestPost({{
      request: new Request("https://gainhelm.com/api/lead-capture", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{
          tool_slug: "soc-2-audit-cost-calculator",
          partner_key: alias,
          email: "ciso@enterprise-check.com",
          state: "NY",
          calculated_amount: 90000,
          partner_sharing_consent: true,
          synthetic_test: true,
        }}),
      }}),
      env,
    }});
    const outAlias = await resAlias.json();
    if (
      outAlias.partner_key !== canon
      || !outAlias.redirect_url.startsWith(`/r/${{canon}}?`)
      || !outAlias.partner_rep_desk.includes(deskTokens[canon])
    ) {{
      throw new Error(`Alias mismatch (${{alias}}): ${{JSON.stringify(outAlias)}}`);
    }}
  }}
}}
run().catch((err) => {{
  console.error(err);
  process.exit(1);
}});
""",
        encoding="utf-8",
    )
    proc = subprocess.run(["node", str(node_script)], capture_output=True, text=True)
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"


def test_gainhelm_generic_slugs_preserve_vertical_in_workpaper_and_email() -> None:
    """Verifies generic slugs preserve isolated GainHelm vertical in thresholds, workpapers, trends, and emails."""
    import inspect
    from pseofactory.partner_tracker import (
        evaluate_lead_quote_threshold,
        render_transactional_playbook_email,
        synthesize_personalized_audit_workpaper,
    )

    assert "vertical" in inspect.signature(evaluate_lead_quote_threshold).parameters, (
        "evaluate_lead_quote_threshold missing vertical parameter"
    )
    for g_slug in ("", "general", "index"):
        for fw in ("dora", "eu_ai_act", "sec_8k", "ccpa"):
            prof = _PHASE2_FW_CASES[fw]
            ev = evaluate_lead_quote_threshold("gainhelm", g_slug, 65000.0, vertical=prof["vertical"])
            assert ev["vertical"] == prof["vertical"]
            assert ev["partner_rep_desk"] == prof["partner_rep_desk"]

            rec = {
                "lead_id": f"lead_gen_{fw}",
                "property_id": "gainhelm",
                "tool_slug": g_slug,
                "vertical": prof["vertical"],
                "email": "ciso@enterprise-check.com",
                "calculated_amount": 65000.0,
            }
            wp = synthesize_personalized_audit_workpaper("gainhelm", g_slug, rec)
            assert wp["settlement_attribution"]["vertical"] == prof["vertical"]
            ts_blob = " ".join(
                f"{s.get('series_id', '')} {s.get('metric_label', '')}"
                for s in wp["statutory_trend_timeseries"]
            )
            assert not _blob_has_forbidden_tokens(ts_blob, prof["forbidden"])

            em = render_transactional_playbook_email(rec)
            em_blob = json.dumps(em)
            assert prof["partner_rep_desk"] in em_blob
            assert prof["statutory_authority"] in em_blob
            assert not _blob_has_forbidden_tokens(em.get("html_body", ""), prof["forbidden"])


@pytest.mark.host_estate
def test_gainhelm_estate_convergence_strict_and_core_containers(tmp_path: Path) -> None:
    """Verifies Pass 1->2->3 tool convergence, strict container isolation, FedRAMP separation, and privacy branches."""
    from pseofactory.competitor import render_serp_incumbent_depth_upgrade_block
    from pseofactory.maintenance import RetroReflectionEngine
    from pseofactory.proprietary_signals import (
        compute_multi_year_longitudinal_trajectory,
        compute_stateful_comparator_defaults,
    )

    dist_copy = tmp_path / "dist"
    src_gh_dist = Path("/home/ubuntuadmin/projects/gainhelm/dist")
    shutil.copytree(src_gh_dist, dist_copy, dirs_exist_ok=True, ignore=shutil.ignore_patterns("videos"))
    src_gh_videos = src_gh_dist / "videos"
    if src_gh_videos.is_dir():
        dst_gh_videos = dist_copy / "videos"
        dst_gh_videos.mkdir(parents=True, exist_ok=True)
        for root_dir, _dirs, files in os.walk(src_gh_videos):
            rel_dir = Path(root_dir).relative_to(src_gh_videos)
            target_dir = dst_gh_videos / rel_dir
            target_dir.mkdir(parents=True, exist_ok=True)
            for fname in files:
                src_file = Path(root_dir) / fname
                dst_file = target_dir / fname
                if src_file.suffix.lower() in {".mp4", ".mov", ".webm"}:
                    if dst_file.exists() or dst_file.is_symlink():
                        dst_file.unlink()
                    os.symlink(src_file, dst_file)
                else:
                    shutil.copy2(src_file, dst_file)
    RetroReflectionEngine.retrofit_estate(dist_dir=dist_copy, property_id="gainhelm")
    r2 = RetroReflectionEngine.retrofit_estate(dist_dir=dist_copy, property_id="gainhelm")
    r3 = RetroReflectionEngine.retrofit_estate(dist_dir=dist_copy, property_id="gainhelm")

    r2_tools = [p for p in r2["retrofitted_paths"] if p.startswith("tools/") or p == "index.html"]
    r3_tools = [p for p in r3["retrofitted_paths"] if p.startswith("tools/") or p == "index.html"]
    assert not r2_tools, f"Pass 2 tool diffs did not converge: {r2_tools}"
    assert not r3_tools, f"Pass 3 tool diffs did not converge: {r3_tools}"

    slug_to_spec = {v["slug"]: (k, v) for k, v in _PHASE2_FW_CASES.items()}
    commercial_selectors = (
        "#partner-quote-intake-step",
        "#post-calculation-upgrade-drawer",
        "#calc-result-quick-unlock-bar",
        ".calc-inline-cta",
        ".pro-hook-card",
        ".compliance-strip",
        ".affiliate-section",
        ".affiliates-section",
        ".refinance-partner-section",
        ".partners-section",
    )
    for tool_dir in sorted((dist_copy / "tools").iterdir()):
        idx = tool_dir / "index.html"
        if not idx.is_file():
            continue
        slug = tool_dir.name
        fw_k, prof = slug_to_spec.get(slug, ("soc2", _PHASE2_FW_CASES["soc2"]))
        if not prof["forbidden"]:
            continue
        soup = BeautifulSoup(idx.read_text(encoding="utf-8"), "html.parser")
        if prof["strict_isolated"]:
            for sel in ("#calculator-workspace-anchor", "#serp-incumbent-depth-workbench") + commercial_selectors:
                for el in soup.select(sel):
                    assert not _blob_has_forbidden_tokens(str(el), prof["forbidden"]), f"{slug} leaked in {sel}"
        else:
            for sel in commercial_selectors:
                for el in soup.select(sel):
                    assert not _blob_has_forbidden_tokens(str(el), prof["forbidden"]), f"{slug} commercial leak in {sel}"
            if fw_k == "fedramp":
                for sel in ("#serp-incumbent-depth-workbench", "#multi-year-cliff-visualizer"):
                    for el in soup.select(sel):
                        assert not _blob_has_forbidden_tokens(str(el), prof["forbidden"]), f"fedramp leaked in {sel}"

    for fw_k in ("fedramp", "ccpa", "gdpr", "nis2"):
        prof = _PHASE2_FW_CASES[fw_k]
        fw_slug = prof["slug"]
        wb_html = render_serp_incumbent_depth_upgrade_block(
            slug=fw_slug,
            property_id="gainhelm",
            topic_label=fw_slug.replace("-", " ").title(),
            statutory_authority="Statutory Authority",
            economic_dataset="Statutory Dataset",
        )
        assert not _blob_has_forbidden_tokens(wb_html, prof["forbidden"]), f"depth workbench leak on {fw_slug}"
        traj = compute_multi_year_longitudinal_trajectory("gainhelm", fw_slug, fw_slug)
        assert not _blob_has_forbidden_tokens(json.dumps(traj), prof["forbidden"]), f"trajectory leak on {fw_slug}"
        comp = compute_stateful_comparator_defaults("gainhelm", fw_slug)
        assert not _blob_has_forbidden_tokens(json.dumps(comp), prof["forbidden"]), f"comparator leak on {fw_slug}"


def test_gainhelm_fallback_manifest_path_slug_pro_sample_unlock_and_partners_section(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies manifest fallback synthesis, path slug normalization, .pro-hook-sample-unlock, and partners-section badge heals."""
    from pseofactory.audit import detect_tautological_or_fabricated_manifest_issues
    from pseofactory.maintenance import RetroReflectionEngine

    custom_cases = (
        ("ccpa-cpra-california-privacy-compliance-and-breach-liability-calculator", _PHASE2_FW_CASES["ccpa"]["forbidden"]),
        ("gdpr-dsar-calculator", _PHASE2_FW_CASES["gdpr"]["forbidden"]),
        ("nis2-directive-calculator", _PHASE2_FW_CASES["nis2"]["forbidden"]),
        ("dora-custom-calculator", _PHASE2_FW_CASES["dora"]["forbidden"]),
    )
    for custom_slug, forbidden in custom_cases:
        mf = RetroReflectionEngine._resolve_manifest_for_page("<html></html>", "gainhelm", slug=custom_slug)
        assert "soc2" not in str(mf.get("model_name") or "").lower(), (custom_slug, mf)
        mf_core = " ".join(
            str(mf.get(k) or "")
            for k in ("model_name", "statutory_authority", "economic_dataset", "sample_calculation")
        )
        assert not _blob_has_forbidden_tokens(mf_core, forbidden), (custom_slug, mf_core)
        taut_issues = detect_tautological_or_fabricated_manifest_issues(
            str(mf.get("formula") or ""),
            mf.get("inputs") or {},
            float(mf.get("published_output") or 0.0),
        )
        assert not taut_issues, (custom_slug, taut_issues)

    base_custom_html = (
        "<html><head><title>DORA Custom Cost Calculator</title></head>"
        "<body><h1>DORA Custom Cost</h1><form><input id='x' value='112100'></form>"
        "<div class='output-value'>$112,100</div></body></html>"
    )
    path_repaired, _ = RetroReflectionEngine.retrofit_html(
        base_custom_html,
        property_id="gainhelm",
        slug="tools/dora-custom-calculator/index.html",
    )
    assert "tools/tools/" not in path_repaired
    assert 'data-tool-slug="dora-custom-calculator"' in path_repaired
    path_pass2, _ = RetroReflectionEngine.retrofit_html(
        path_repaired,
        property_id="gainhelm",
        slug="dora-custom-calculator",
    )
    assert path_pass2 == path_repaired

    dora_forbidden = _PHASE2_FW_CASES["dora"]["forbidden"]
    stale_pro_and_partners = (
        '<html><head><link rel="canonical" href="https://gainhelm.com/tools/dora-ict-third-party-risk-compliance-cost-calculator/">'
        "<title>DORA Calculator</title></head><body><h1>DORA Cost</h1>"
        '<div id="post-calculation-upgrade-drawer" data-offer-sku="gh_hipaa_iso27001_governance_kit" data-offer-price="49" data-calculated-amount="112100"></div>'
        '<div class="pro-hook-card"><span class="pro-hook-badge">SOC 2 Audit ($79)</span>'
        '<a class="pro-hook-link" href="#post-calculation-upgrade-drawer">Export ($79)</a>'
        '<div class="pro-hook-sample-unlock" data-mechanic="above_fold_packet_sample_unlock">'
        "<div>Line 3 Signed SOC 2 &amp; CMMC Workpaper (Locked - $79)</div>"
        '<div><a class="pro-hook-direct-checkout" href="/api/lead-capture?checkout=1&amp;sku=gh_soc2_cmmc_audit_workpapers" data-offer-sku="gh_soc2_cmmc_audit_workpapers" data-offer-price="79">Checkout ($79)</a></div>'
        "</div></div>"
        '<section class="partners-section"><div class="partner-card">'
        '<span class="partner-badge">Automated SOC 2, ISO 27001 &amp; HIPAA</span>'
        '<h3 class="partner-title">Vanta</h3><p>Automated SOC 2 &amp; CMMC</p>'
        '<a href="/r/vanta_security">Vanta</a></div></section></body></html>'
    )
    healed, _ = RetroReflectionEngine.retrofit_html(
        stale_pro_and_partners,
        property_id="gainhelm",
        slug="dora-ict-third-party-risk-compliance-cost-calculator",
    )
    soup = BeautifulSoup(healed, "html.parser")
    sample_unlock = soup.select_one(".pro-hook-sample-unlock")
    assert sample_unlock is not None
    su_txt = sample_unlock.get_text(" ", strip=True)
    assert "Locked: $49" in su_txt
    assert not _blob_has_forbidden_tokens(str(sample_unlock), dora_forbidden)

    # While all GainHelm partners are pending, unapproved /r/ links are hidden and replaced by 1st-party checkout CTA
    assert not soup.select('a[href^="/r/"]')
    fp_sec = soup.select_one('section[data-first-party-checkout="true"]')
    assert fp_sec is not None
    assert not _blob_has_forbidden_tokens(str(fp_sec), dora_forbidden)

    # Once vanta_security flips to live in monetization_vault.json, partners-section badges auto-render framework-clean
    from pseofactory import affiliates as aff_mod

    vault_copy = json.loads(aff_mod.MONETIZATION_VAULT_PATH.read_text(encoding="utf-8"))
    vault_copy["properties"]["gainhelm"]["partners"]["vanta_security"]["status"] = "live"
    tmp_vault = tmp_path / "monetization_vault.json"
    tmp_vault.write_text(json.dumps(vault_copy), encoding="utf-8")
    monkeypatch.setattr(aff_mod, "MONETIZATION_VAULT_PATH", tmp_vault)
    healed_live, _ = RetroReflectionEngine.retrofit_html(
        stale_pro_and_partners,
        property_id="gainhelm",
        slug="dora-ict-third-party-risk-compliance-cost-calculator",
    )
    soup_live = BeautifulSoup(healed_live, "html.parser")
    partners_sec = soup_live.select_one("section.partners-section")
    assert partners_sec is not None
    badges = partners_sec.select("span.partner-badge")
    assert badges and all(not _blob_has_forbidden_tokens(str(b), dora_forbidden) for b in badges)
    assert not _blob_has_forbidden_tokens(str(partners_sec), dora_forbidden)


def test_phase2_edge_generic_slugs_propagate_vertical_across_all_15_frameworks(
    tmp_path: Path,
) -> None:
    """
    Falsifying Node VM probe across all 45 (generic tool_slug x 15 verticals) combinations
    for POST /api/lead-capture, GET /api/lead-capture?fulfill=1, and resolveEdgeStripeCheckoutOffer.
    """
    from pseofactory.affiliates import GAINHELM_FRAMEWORK_PROFILES
    from pseofactory.edge import generate_edge_lead_capture_function

    edge_js = _strip_esm_exports(
        generate_edge_lead_capture_function(property_id="gainhelm")
    )
    fw_specs = {
        fw_k: {
            "vertical": prof["vertical"],
            "primary_partner_key": prof["primary_partner_key"],
            "partner_rep_desk": prof["partner_rep_desk"],
            "offer_sku": prof["offer_sku"],
            "offer_price_usd": int(round(float(prof["offer_price_usd"]))),
            "default_sku_slug": prof["default_sku_slug"],
            "vanta_url": prof["vanta_url"],
            "statutory_authority": prof["statutory_authority"],
            "regulator_name": prof["regulator_name"],
            "forbidden": list(_PHASE2_FW_CASES[fw_k]["forbidden"]),
        }
        for fw_k, prof in GAINHELM_FRAMEWORK_PROFILES.items()
    }
    node_script = tmp_path / "edge_vertical_45_probe.mjs"
    node_script.write_text(
        edge_js
        + f"""
const fwSpecs = {json.dumps(fw_specs)};
const genericSlugs = ["", "general", "index"];
const capturedZepto = [];
const capturedStripeBodies = [];

globalThis.fetch = async (url, init = {{}}) => {{
  const sUrl = String(url);
  if (sUrl.includes("api.zeptomail.com/v1.1/email")) {{
    capturedZepto.push(JSON.parse(String(init.body || "{{}}")));
    return new Response(JSON.stringify({{ data: [{{ message_id: "zm_test" }}], request_id: "req_test" }}), {{ status: 200 }});
  }}
  const mPaid = sUrl.match(/api\\.stripe\\.com\\/v1\\/checkout\\/sessions\\/(cs_live_PAIDFOR_[A-Za-z0-9_]+)$/);
  if (mPaid) {{
    const lid = mPaid[1].replace("cs_live_PAIDFOR_", "");
    return new Response(JSON.stringify({{
      id: mPaid[1],
      livemode: true,
      payment_status: "paid",
      amount_total: 4900,
      currency: "usd",
      client_reference_id: lid,
      metadata: {{ lead_id: lid }},
    }}), {{ status: 200 }});
  }}
  if (sUrl.includes("api.stripe.com/v1/checkout/sessions")) {{
    capturedStripeBodies.push(String(init.body || ""));
    return new Response(JSON.stringify({{
      id: "cs_live_mock_post",
      url: "https://checkout.stripe.com/c/pay/cs_live_mock_post",
    }}), {{ status: 200 }});
  }}
  throw new Error("Unexpected fetch URL: " + sUrl);
}};

function makeIsolatedKv() {{
  const m = new Map();
  return {{
    async get(k) {{ return m.has(k) ? m.get(k) : null; }},
    async put(k, v) {{ m.set(k, v); }},
    async list() {{ return {{ keys: [], list_complete: true }}; }},
  }};
}}

async function run() {{
  let comboCount = 0;
  for (const [fwKey, spec] of Object.entries(fwSpecs)) {{
    for (const gSlug of genericSlugs) {{
      comboCount += 1;
      const env = {{
        LEADS_KV: makeIsolatedKv(),
        STRIPE_SECRET_KEY: "sk_live_mock",
        ZEPTOMAIL_TOKEN: "Zoho-enczapikey mock_tok",
        EMAIL_PRIMARY_RAIL: "zeptomail",
        PLAYBOOK_FREE_EMAIL_ENABLED: "1",
      }};
      const zeptoStart = capturedZepto.length;
      const stripeStart = capturedStripeBodies.length;
      const postRes = await onRequestPost({{
        request: new Request("https://gainhelm.com/api/lead-capture", {{
          method: "POST",
          headers: {{
            "Content-Type": "application/json",
            "CF-Connecting-IP": `198.51.100.${{comboCount}}`,
          }},
          body: JSON.stringify({{
            tool_slug: gSlug,
            vertical: spec.vertical,
            email: `security+c${{comboCount}}@enterprise-client.io`,
            state: "CA",
            calculated_amount: 88000,
            partner_sharing_consent: true,
          }}),
        }}),
        env,
      }});
      if (postRes.status !== 200) throw new Error(`POST status ${{postRes.status}} for ${{fwKey}}:${{gSlug}}`);
      const postJson = await postRes.json();
      if (postJson.tool_slug !== gSlug) {{
        throw new Error(`POST tool_slug overwritten (${{fwKey}}): expected '${{gSlug}}', got '${{postJson.tool_slug}}'`);
      }}
      if (postJson.vertical !== spec.vertical) {{
        throw new Error(`POST vertical mismatch (${{fwKey}}:${{gSlug}}): expected ${{spec.vertical}}, got ${{postJson.vertical}}`);
      }}
      if (postJson.partner_key !== spec.primary_partner_key) {{
        throw new Error(`POST partner_key mismatch (${{fwKey}}:${{gSlug}}): expected ${{spec.primary_partner_key}}, got ${{postJson.partner_key}}`);
      }}
      if (postJson.partner_rep_desk !== spec.partner_rep_desk) {{
        throw new Error(`POST partner_rep_desk mismatch (${{fwKey}}:${{gSlug}}): expected ${{spec.partner_rep_desk}}, got ${{postJson.partner_rep_desk}}`);
      }}
      if (postJson.offer_sku !== spec.offer_sku || Number(postJson.offer_price_usd) !== spec.offer_price_usd) {{
        throw new Error(`POST offer mismatch (${{fwKey}}:${{gSlug}}): ${{postJson.offer_sku}} ($${{postJson.offer_price_usd}})`);
      }}
      if (!String(postJson.redirect_url || "").startsWith(`/r/${{spec.primary_partner_key}}?`)) {{
        throw new Error(`POST redirect_url mismatch (${{fwKey}}:${{gSlug}}): ${{postJson.redirect_url}}`);
      }}
      if (spec.primary_partner_key === "vanta_security" && !String(postJson.live_destination_url || "").startsWith(spec.vanta_url)) {{
        throw new Error(`POST live_destination_url mismatch (${{fwKey}}:${{gSlug}}): ${{postJson.live_destination_url}}`);
      }}
      const expSuccessPrefix = `https://gainhelm.com/tools/${{spec.default_sku_slug}}/?checkout_status=success`;
      if (!String(postJson.success_url || "").startsWith(expSuccessPrefix)) {{
        throw new Error(`POST success_url mismatch (${{fwKey}}:${{gSlug}}): expected ${{expSuccessPrefix}}, got ${{postJson.success_url}}`);
      }}
      if (capturedZepto.length <= zeptoStart) {{
        throw new Error(`Missing ZeptoMail payload for ${{fwKey}}:${{gSlug}}`);
      }}
      const zm = capturedZepto[zeptoStart];
      const expectedSubj = `[GainHelm Playbook] Your Compliance Scoping & Cost Worksheet (${{gSlug || spec.vertical}})`;
      if (zm.subject !== expectedSubj) {{
        throw new Error(`Zepto subject mismatch (${{fwKey}}:${{gSlug}}): expected '${{expectedSubj}}', got '${{zm.subject}}'`);
      }}
      if (!String(zm.htmlbody || "").includes("<h2>Your Calculation Worksheet &amp; Action Plan</h2>")) {{
        throw new Error(`Zepto heading mismatch (${{fwKey}}:${{gSlug}}): ${{zm.htmlbody}}`);
      }}
      const escapedDesk = String(spec.partner_rep_desk || "").replace(/&/g, "&amp;");
      if (!String(zm.htmlbody || "").includes(escapedDesk) && !String(zm.htmlbody || "").includes(spec.partner_rep_desk)) {{
        throw new Error(`Zepto missing desk (${{fwKey}}:${{gSlug}})`);
      }}

      const fulfillLid = `lead_ff_${{fwKey}}_${{gSlug || "empty"}}`;
      const getUrl = new URL("https://gainhelm.com/api/lead-capture");
      getUrl.searchParams.set("fulfill", "1");
      getUrl.searchParams.set("lead_id", fulfillLid);
      getUrl.searchParams.set("session_id", `cs_live_PAIDFOR_${{fulfillLid}}`);
      getUrl.searchParams.set("tool_slug", gSlug);
      getUrl.searchParams.set("vertical", spec.vertical);
      getUrl.searchParams.set("amount", "88000");
      getUrl.searchParams.set("format", "datapack");
      const getRes = await onRequestGet({{ request: new Request(getUrl.toString()), env }});
      if (getRes.status !== 200) throw new Error(`GET fulfill=1 status ${{getRes.status}} for ${{fwKey}}:${{gSlug}}`);
      const dp = await getRes.json();
      if (dp.tool_slug !== gSlug || dp.vertical !== spec.vertical || dp.offer_sku !== spec.offer_sku) {{
        throw new Error(`GET fulfill datapack mismatch (${{fwKey}}:${{gSlug}}): ${{JSON.stringify(dp)}}`);
      }}
      if (dp.statutory_authority !== spec.statutory_authority || dp.regulator_name !== spec.regulator_name) {{
        throw new Error(`GET fulfill authority mismatch (${{fwKey}}:${{gSlug}}): ${{dp.statutory_authority}} | ${{dp.regulator_name}}`);
      }}
      const dpLow = JSON.stringify(dp).replace(/gh_(?:soc2_cmmc_audit_workpapers|hipaa_iso27001_governance_kit|instant_compliance_worksheet_19)/g, "").toLowerCase();
      for (const bad of spec.forbidden) {{
        if (dpLow.includes(bad)) {{
          throw new Error(`GET fulfill datapack leak '${{bad}}' on ${{fwKey}}:${{gSlug}}`);
        }}
      }}

      const coOffer = selectOfferForSlug(gSlug, "", spec.vertical);
      const co = await resolveEdgeStripeCheckoutOffer(
        env,
        `lead_co_${{fwKey}}_${{gSlug || "empty"}}`,
        "security@enterprise-client.io",
        gSlug,
        coOffer,
        false,
        null,
        spec.vertical
      );
      if (co.offer_sku !== spec.offer_sku || Number(co.offer_price_usd) !== spec.offer_price_usd || co.vertical !== spec.vertical) {{
        throw new Error(`resolveEdgeStripeCheckoutOffer mismatch (${{fwKey}}:${{gSlug}}): ${{JSON.stringify(co)}}`);
      }}
      if (!String(co.success_url || "").startsWith(expSuccessPrefix)) {{
        throw new Error(`resolveEdgeStripeCheckoutOffer success_url mismatch (${{fwKey}}:${{gSlug}}): ${{co.success_url}}`);
      }}
      if (capturedStripeBodies.length <= stripeStart || !capturedStripeBodies[capturedStripeBodies.length - 1].includes(encodeURIComponent(spec.vertical))) {{
        throw new Error(`Stripe POST missing vertical metadata for ${{fwKey}}:${{gSlug}}`);
      }}
    }}
  }}
  if (comboCount !== 45) throw new Error(`Expected 45 combos, ran ${{comboCount}}`);
}}
run().catch((err) => {{
  console.error(err);
  process.exit(1);
}});
""",
        encoding="utf-8",
    )
    proc = subprocess.run(["node", str(node_script)], capture_output=True, text=True)
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"


def test_phase2_python_tracker_generic_slugs_propagate_vertical(tmp_path: Path) -> None:
    """
    Verifies PartnerTrackingEngine.evaluate_lead_quote_threshold, ingest_qualified_lead,
    ingest_playbook_subscription, resolve_lead_monetization_offer, create_stripe_checkout_session,
    settle_post_calculation_datapack_upgrade, and render_transactional_playbook_email propagate
    vertical across generic slugs ("", "general", "index") for all 15 GainHelm frameworks,
    normalize leading /tools/<slug>/ prefixes (no /tools/tools/), and round-trip into Edge JS vm.
    """
    from pseofactory.action_bus import HumanActionBus
    import pseofactory.affiliates as aff_mod
    from pseofactory.edge import generate_edge_lead_capture_function
    from pseofactory.partner_tracker import (
        PartnerTrackingEngine,
        create_stripe_checkout_session,
        render_transactional_playbook_email,
        resolve_lead_monetization_offer,
        settle_post_calculation_datapack_upgrade,
        synthesize_personalized_audit_workpaper,
    )

    GAINHELM_FRAMEWORK_PROFILES = getattr(aff_mod, "GAINHELM_FRAMEWORK_PROFILES", None)
    engine = PartnerTrackingEngine()
    engine.action_bus = HumanActionBus(tmp_path / "action_bus.jsonl")
    leads_path = tmp_path / "captured_leads.jsonl"

    # Generic default without sku or explicit vertical remains root "/"
    gen_bare = resolve_lead_monetization_offer("gainhelm", "general")
    assert gen_bare["success_url"].startswith("https://gainhelm.com/?checkout_status=success")
    assert gen_bare["cancel_url"].startswith("https://gainhelm.com/?checkout_status=cancelled")

    # Leading /tools/<slug>/ prefix normalization across Python APIs (zero /tools/tools/)
    prefixed_slug = "/tools/dora-ict-third-party-risk-compliance-cost-calculator/"
    pref_offer = resolve_lead_monetization_offer("gainhelm", prefixed_slug, lead_id="lead_pref_dora")
    assert pref_offer["tool_slug"] == "dora-ict-third-party-risk-compliance-cost-calculator"
    assert pref_offer["success_url"].startswith(
        "https://gainhelm.com/tools/dora-ict-third-party-risk-compliance-cost-calculator/?checkout_status=success"
    )
    assert pref_offer["cancel_url"].startswith(
        "https://gainhelm.com/tools/dora-ict-third-party-risk-compliance-cost-calculator/?checkout_status=cancelled"
    )
    pref_wp = synthesize_personalized_audit_workpaper("gainhelm", prefixed_slug, {"calculated_amount": 112100.0})
    assert pref_wp["tool_slug"] == "dora-ict-third-party-risk-compliance-cost-calculator"
    pref_sess = create_stripe_checkout_session(
        "gainhelm", prefixed_slug, customer_email="secops@client-dora.io", lead_id="lead_pref_dora", execute_live=False
    )
    assert pref_sess["tool_slug"] == "dora-ict-third-party-risk-compliance-cost-calculator"
    assert pref_sess["request_payload"]["metadata[tool_slug]"] == "dora-ict-third-party-risk-compliance-cost-calculator"
    assert pref_sess["request_payload"]["metadata[vertical]"] == "dora_eu_ict_resilience"
    pref_email = render_transactional_playbook_email(
        {
            "lead_id": "lead_pref_dora",
            "property_id": "gainhelm",
            "tool_slug": prefixed_slug,
            "email": "secops@client-dora.io",
            "calculated_amount": 112100.0,
        }
    )
    for blob in (
        pref_offer["success_url"],
        pref_offer["cancel_url"],
        pref_offer["checkout_url"],
        pref_wp["html_report"],
        pref_sess["request_payload"]["success_url"],
        pref_email["html_body"],
    ):
        assert "/tools/tools/" not in blob

    edge_roundtrip_cases: List[Dict[str, str]] = []
    assert isinstance(GAINHELM_FRAMEWORK_PROFILES, dict) and GAINHELM_FRAMEWORK_PROFILES

    for g_slug in ("", "general", "index"):
        for fw_k, prof in GAINHELM_FRAMEWORK_PROFILES.items():
            exp_vert = prof["vertical"]
            exp_pk = prof["primary_partner_key"]
            exp_desk = prof["partner_rep_desk"]
            exp_sku = prof["offer_sku"]
            exp_price = float(prof["offer_price_usd"])
            exp_tool_prefix = f"https://gainhelm.com/tools/{prof['default_sku_slug']}/"

            ev = engine.evaluate_lead_quote_threshold(
                "gainhelm", g_slug, 115000.0, vertical=exp_vert
            )
            assert ev["eligible"] is True, (fw_k, g_slug, ev)
            assert ev["vertical"] == exp_vert
            assert ev["primary_partner_key"] == exp_pk
            assert ev["partner_rep_desk"] == exp_desk

            qt = engine.ingest_qualified_lead(
                property_id="gainhelm",
                tool_slug=g_slug,
                email="security@enterprise-client.io",
                state="CA",
                capital_band="100k_250k",
                calculated_amount=115000.0,
                partner_sharing_consent=True,
                vertical=exp_vert,
                leads_ledger_path=leads_path,
            )
            assert qt["tool_slug"] == g_slug
            assert qt["vertical"] == exp_vert
            assert qt["partner_key"] == exp_pk
            assert qt["partner_rep_desk"] == exp_desk
            assert qt["offer_sku"] == exp_sku
            assert float(qt["offer_price_usd"]) == exp_price
            assert f"vertical={exp_vert}" in qt["checkout_url"]
            assert f"vertical={exp_vert}" in qt["playbook_url"]
            assert f"vertical={exp_vert}" in qt["fulfillment_url"]
            if exp_pk == "vanta_security":
                assert qt["live_destination_url"].startswith(prof["vanta_url"])

            pb = engine.ingest_playbook_subscription(
                property_id="gainhelm",
                tool_slug=g_slug,
                email="security@enterprise-client.io",
                calculated_amount=65000.0,
                leads_ledger_path=leads_path,
                vertical=exp_vert,
            )
            assert pb["tool_slug"] == g_slug
            assert pb["vertical"] == exp_vert
            assert pb["partner_key"] == exp_pk
            assert pb["partner_rep_desk"] == exp_desk
            assert pb["offer_sku"] == exp_sku
            assert float(pb["offer_price_usd"]) == exp_price
            assert f"vertical={exp_vert}" in pb["checkout_url"]
            assert f"vertical={exp_vert}" in pb["playbook_url"]
            assert f"vertical={exp_vert}" in pb["fulfillment_url"]

            lid_rt = f"lead_rt_{fw_k}_{g_slug or 'empty'}"
            offer = resolve_lead_monetization_offer(
                "gainhelm", g_slug, vertical=exp_vert, lead_id=lid_rt
            )
            assert offer["vertical"] == exp_vert
            assert offer["success_url"].startswith(f"{exp_tool_prefix}?checkout_status=success")
            assert offer["cancel_url"].startswith(f"{exp_tool_prefix}?checkout_status=cancelled")
            assert f"vertical={exp_vert}" in offer["checkout_url"]
            assert f"vertical={exp_vert}" in offer["playbook_url"]
            assert f"vertical={exp_vert}" in offer["fulfillment_url"]

            sess = create_stripe_checkout_session(
                property_id="gainhelm",
                tool_slug=g_slug,
                customer_email="security@enterprise-client.io",
                lead_id=lid_rt,
                vertical=exp_vert,
                execute_live=False,
            )
            assert sess["request_payload"]["metadata[vertical]"] == exp_vert
            assert sess["request_payload"]["success_url"].startswith(f"{exp_tool_prefix}?checkout_status=success")
            assert sess["request_payload"]["cancel_url"].startswith(f"{exp_tool_prefix}?checkout_status=cancelled")
            assert f"vertical={exp_vert}" in sess["request_payload"]["metadata[fulfillment_url]"]

            unpaid_ff = settle_post_calculation_datapack_upgrade(
                property_id="gainhelm",
                tool_slug=g_slug,
                lead_id=lid_rt,
                customer_email="security@enterprise-client.io",
                calculated_amount=65000.0,
                leads_ledger_path=leads_path,
                execute_live_checkout=False,
                vertical=exp_vert,
            )
            assert unpaid_ff["status"] == "payment_required"
            assert unpaid_ff["checkout_session"]["request_payload"]["metadata[vertical]"] == exp_vert

            em = render_transactional_playbook_email(pb)
            assert f"vertical={exp_vert}" in em["checkout_endpoint"]
            assert f"vertical={exp_vert}" in em["playbook_endpoint"]
            assert f"vertical={exp_vert}" in em["fulfillment_endpoint"]
            assert em["playbook_endpoint"] in em["html_body"]
            assert em["checkout_endpoint"] in em["html_body"]

            edge_roundtrip_cases.append(
                {
                    "fw": fw_k,
                    "g_slug": g_slug,
                    "lead_id": pb["lead_id"],
                    "exp_vert": exp_vert,
                    "exp_sku": exp_sku,
                    "exp_reg": str(prof["regulator_name"]),
                    "exp_tool_prefix": exp_tool_prefix,
                    "checkout_ep": offer["live_checkout_endpoint"],
                    "playbook_ep": em["playbook_endpoint"],
                    "fulfill_ep": offer["live_fulfillment_endpoint"],
                    "email_checkout_ep": em["checkout_endpoint"],
                }
            )

    edge_js = _strip_esm_exports(
        generate_edge_lead_capture_function(property_id="gainhelm")
    )
    vm_runner = f"""
import vm from "node:vm";
const capturedStripeBodies = [];
const sandbox = {{
  URL,
  URLSearchParams,
  Request,
  Response,
  Headers,
  fetch: async (url, init = {{}}) => {{
    const sUrl = String(url);
    const mPaid = sUrl.match(/api\\.stripe\\.com\\/v1\\/checkout\\/sessions\\/(cs_live_PAIDFOR_[A-Za-z0-9_]+)$/);
    if (mPaid) {{
      const lid = mPaid[1].replace("cs_live_PAIDFOR_", "");
      return new Response(JSON.stringify({{
        id: mPaid[1],
        livemode: true,
        payment_status: "paid",
        amount_total: 4900,
        currency: "usd",
        client_reference_id: lid,
        metadata: {{ lead_id: lid, property_id: "gainhelm" }},
      }}), {{ status: 200 }});
    }}
    if (sUrl.includes("api.stripe.com/v1/checkout/sessions")) {{
      capturedStripeBodies.push(String(init.body || ""));
      return new Response(JSON.stringify({{
        id: "cs_live_vm_ok",
        url: "https://checkout.stripe.com/c/pay/cs_live_vm_ok",
      }}), {{ status: 200 }});
    }}
    throw new Error("Unexpected fetch: " + sUrl);
  }},
  console,
  Math,
  Date,
  JSON,
  Number,
  String,
  Boolean,
  Array,
  Object,
  Map,
  Set,
  Error,
  RegExp,
  encodeURIComponent,
  decodeURIComponent,
  atob: globalThis.atob,
  btoa: globalThis.btoa,
}};
const ctx = vm.createContext(sandbox);
vm.runInContext({json.dumps(edge_js)}, ctx);
const env = {{ STRIPE_SECRET_KEY: "sk_live_mock" }};
const cases = {json.dumps(edge_roundtrip_cases)};
(async () => {{
  for (const c of cases) {{
    const chkStart = capturedStripeBodies.length;
    const chkRes = await ctx.onRequestGet({{
      request: new Request(c.checkout_ep + "&format=json"),
      env,
    }});
    if (chkRes.status !== 200) throw new Error(`Edge checkout HTTP ${{chkRes.status}} for ${{c.fw}}:${{c.g_slug}}`);
    const chkJson = await chkRes.json();
    if (chkJson.offer_sku !== c.exp_sku || chkJson.vertical !== c.exp_vert) {{
      throw new Error(`Edge checkout mismatch (${{c.fw}}:${{c.g_slug}}): ${{JSON.stringify(chkJson)}}`);
    }}
    if (!String(chkJson.success_url || "").startsWith(c.exp_tool_prefix)) {{
      throw new Error(`Edge checkout success_url mismatch (${{c.fw}}:${{c.g_slug}}): ${{chkJson.success_url}}`);
    }}
    if (!String(chkJson.cancel_url || "").startsWith(c.exp_tool_prefix)) {{
      throw new Error(`Edge checkout cancel_url mismatch (${{c.fw}}:${{c.g_slug}}): ${{chkJson.cancel_url}}`);
    }}
    const stripeBody = capturedStripeBodies[chkStart] || "";
    const sp = new URLSearchParams(stripeBody);
    if (sp.get("metadata[vertical]") !== c.exp_vert) {{
      throw new Error(`Edge Stripe metadata[vertical] mismatch (${{c.fw}}:${{c.g_slug}}): ${{sp.get("metadata[vertical]")}}`);
    }}

    const pbRes = await ctx.onRequestGet({{
      request: new Request(c.playbook_ep + "&format=datapack&synthetic_test=1"),
      env,
    }});
    if (pbRes.status !== 200) throw new Error(`Edge playbook HTTP ${{pbRes.status}} for ${{c.fw}}:${{c.g_slug}}`);
    const pbDp = await pbRes.json();
    if (pbDp.offer_sku !== c.exp_sku || pbDp.regulator_name !== c.exp_reg || pbDp.vertical !== c.exp_vert) {{
      throw new Error(`Edge playbook mismatch (${{c.fw}}:${{c.g_slug}}): ${{JSON.stringify(pbDp)}}`);
    }}

    const ffLid = c.lead_id.replace(/^lead_/, "lead_") ;
    const ffUrlObj = new URL(c.fulfill_ep);
    const ffLidParam = ffUrlObj.searchParams.get("lead_id") || ffLid;
    const ffRes = await ctx.onRequestGet({{
      request: new Request(`${{c.fulfill_ep}}&session_id=cs_live_PAIDFOR_${{ffLidParam}}&format=datapack&synthetic_test=1`),
      env,
    }});
    if (ffRes.status !== 200) throw new Error(`Edge fulfill HTTP ${{ffRes.status}} for ${{c.fw}}:${{c.g_slug}}`);
    const ffDp = await ffRes.json();
    if (ffDp.offer_sku !== c.exp_sku || ffDp.regulator_name !== c.exp_reg) {{
      throw new Error(`Edge fulfill mismatch (${{c.fw}}:${{c.g_slug}}): ${{JSON.stringify(ffDp)}}`);
    }}

    const emChkRes = await ctx.onRequestGet({{
      request: new Request(c.email_checkout_ep + "&redirect=1"),
      env,
    }});
    if (emChkRes.status !== 302 || emChkRes.headers.get("X-Edge-Offer-Sku") !== c.exp_sku) {{
      throw new Error(`Edge email checkout redirect mismatch (${{c.fw}}:${{c.g_slug}}): ${{emChkRes.status}}`);
    }}
  }}
  console.log("PY_TO_EDGE_VM_ROUNDTRIP_OK");
}})().catch((e) => {{ console.error(e); process.exit(1); }});
"""
    vm_script = tmp_path / "py_to_edge_vm_roundtrip.mjs"
    vm_script.write_text(vm_runner, encoding="utf-8")
    vm_proc = subprocess.run(["node", str(vm_script)], capture_output=True, text=True, check=False)
    assert vm_proc.returncode == 0, f"{vm_proc.stdout}\n{vm_proc.stderr}"
    assert "PY_TO_EDGE_VM_ROUNDTRIP_OK" in vm_proc.stdout


def test_phase2_non_primary_partner_key_and_zeptomail_parity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Verifies non-primary partner_key selections (and aliases like "thoropass") produce identical
    framework-neutral partner_rep_desk, partner-matched live_destination_url, and parity ZeptoMail
    subject/heading/HTML across Edge JS and Python without leaking SOC 2 / CPA Audit tokens.
    """
    from pseofactory.action_bus import HumanActionBus
    from pseofactory.edge import generate_edge_lead_capture_function
    from pseofactory.partner_tracker import (
        PartnerTrackingEngine,
        dispatch_transactional_playbook,
    )

    cases = [
        ("fedramp", "vanta_security", "vanta_security", "https://www.vanta.com/solutions/fedramp"),
        ("iso_27001", "vanta_security", "vanta_security", "https://www.vanta.com/products/iso-27001"),
        ("pci_dss", "vanta_security", "vanta_security", "https://www.vanta.com/products/pci-dss"),
        ("cmmc", "vanta_security", "vanta_security", "https://www.vanta.com/solutions/cmmc"),
        ("pentest", "vanta_security", "vanta_security", "https://www.vanta.com/platform"),
        ("dora", "thoropass_audit", "thoropass_audit", "https://www.thoropass.com/solutions"),
        ("dora", "thoropass", "thoropass_audit", "https://www.thoropass.com/solutions"),
        ("hipaa", "thoropass_audit", "thoropass_audit", "https://www.thoropass.com/solutions"),
        ("gdpr", "thoropass", "thoropass_audit", "https://www.thoropass.com/solutions"),
        ("ccpa", "thoropass_audit", "thoropass_audit", "https://www.thoropass.com/solutions"),
        ("nis2", "thoropass", "thoropass_audit", "https://www.thoropass.com/solutions"),
    ]
    edge_cases_payload = [
        {
            "fw": fw,
            "slug": _PHASE2_FW_CASES[fw]["slug"],
            "vertical": _PHASE2_FW_CASES[fw]["vertical"],
            "req_pk": req_pk,
            "canon_pk": canon_pk,
            "exp_dest_base": exp_dest_base,
        }
        for fw, req_pk, canon_pk, exp_dest_base in cases
    ]

    edge_js = _strip_esm_exports(
        generate_edge_lead_capture_function(property_id="gainhelm")
    )
    node_script = tmp_path / "edge_non_primary_partner.mjs"
    node_script.write_text(
        edge_js
        + f"""
const testCases = {json.dumps(edge_cases_payload)};
const capturedEmails = [];
globalThis.fetch = async (url, init = {{}}) => {{
  const sUrl = String(url);
  if (sUrl.includes("api.zeptomail.com/v1.1/email")) {{
    capturedEmails.push(JSON.parse(String(init.body || "{{}}")));
    return new Response(JSON.stringify({{ data: [{{ message_id: "zm_np" }}], request_id: "req_np" }}), {{ status: 200 }});
  }}
  if (sUrl.includes("api.stripe.com/v1/checkout/sessions")) {{
    return new Response(JSON.stringify({{ id: "cs_live_np", url: "https://checkout.stripe.com/c/pay/cs_live_np" }}), {{ status: 200 }});
  }}
  throw new Error("Unexpected fetch: " + sUrl);
}};
const env = {{
  STRIPE_SECRET_KEY: "sk_live_mock",
  ZEPTOMAIL_TOKEN: "Zoho-enczapikey mock_tok",
  EMAIL_PRIMARY_RAIL: "zeptomail",
  PLAYBOOK_FREE_EMAIL_ENABLED: "1",
}};
async function run() {{
  const results = [];
  let caseIdx = 0;
  for (const c of testCases) {{
    caseIdx += 1;
    const idx = capturedEmails.length;
    const res = await onRequestPost({{
      request: new Request("https://gainhelm.com/api/lead-capture", {{
        method: "POST",
        headers: {{
          "Content-Type": "application/json",
          "CF-Connecting-IP": `198.51.100.${{caseIdx}}`,
        }},
        body: JSON.stringify({{
          tool_slug: c.slug,
          vertical: c.vertical,
          partner_key: c.req_pk,
          email: `security+np${{caseIdx}}@enterprise-client.io`,
          state: "TX",
          calculated_amount: 110000,
          partner_sharing_consent: true,
        }}),
      }}),
      env,
    }});
    const postJson = await res.json();
    const em = capturedEmails[idx];
    if (!em) throw new Error(`Missing ZeptoMail payload for ${{c.fw}}:${{c.req_pk}}`);
    results.push({{ ...c, postJson, em }});
  }}
  console.log(JSON.stringify(results));
}}
run().catch((err) => {{ console.error(err); process.exit(1); }});
""",
        encoding="utf-8",
    )
    proc = subprocess.run(["node", str(node_script)], capture_output=True, text=True)
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    edge_results = json.loads(proc.stdout.strip())

    py_zepto_payloads: list = []

    class _FakeHttpResp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"data": [{"message_id": "zm_py"}], "request_id": "req_py"}).encode("utf-8")

    def _fake_urlopen(req, timeout=15):
        py_zepto_payloads.append(json.loads(req.data.decode("utf-8")))
        return _FakeHttpResp()

    monkeypatch.setenv("ZEPTOMAIL_TOKEN", "Zoho-enczapikey mock_tok")
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    engine = PartnerTrackingEngine()
    engine.action_bus = HumanActionBus(tmp_path / "action_bus_np.jsonl")
    leads_path = tmp_path / "leads_np.jsonl"

    leak_words = ("soc 2", "soc2", "cpa audit")
    for item in edge_results:
        post_json = item["postJson"]
        em_edge = item["em"]
        assert post_json["partner_key"] == item["canon_pk"]
        assert post_json["redirect_url"].startswith(f"/r/{item['canon_pk']}?")
        assert post_json["live_destination_url"].startswith(item["exp_dest_base"])
        em_edge_body_clean = em_edge["htmlbody"].lower()
        for sku_tok in (
            "gh_soc2_cmmc_audit_workpapers",
            "gh_hipaa_iso27001_governance_kit",
            "gh_instant_compliance_worksheet_19",
        ):
            em_edge_body_clean = em_edge_body_clean.replace(sku_tok, " ")
        for bad in leak_words:
            assert bad not in post_json["partner_rep_desk"].lower()
            assert bad not in post_json["live_destination_url"].lower()
            assert bad not in em_edge["subject"].lower()
            assert bad not in em_edge_body_clean
        assert em_edge["subject"] == f"[GainHelm Playbook] Your Compliance Scoping & Cost Worksheet ({item['slug']})"
        assert "<h2>Your Calculation Worksheet &amp; Action Plan</h2>" in em_edge["htmlbody"]
        import html as _html_mod
        assert (
            _html_mod.escape(post_json["partner_rep_desk"]) in em_edge["htmlbody"]
            or post_json["partner_rep_desk"] in em_edge["htmlbody"]
        )

        qt = engine.ingest_qualified_lead(
            property_id="gainhelm",
            tool_slug=item["slug"],
            email="security@enterprise-client.io",
            state="TX",
            capital_band="100k_250k",
            calculated_amount=110000.0,
            partner_sharing_consent=True,
            partner_key=item["req_pk"],
            vertical=item["vertical"],
            leads_ledger_path=leads_path,
        )
        assert qt["partner_key"] == item["canon_pk"]
        assert qt["partner_rep_desk"] == post_json["partner_rep_desk"]
        assert qt["live_destination_url"].startswith(item["exp_dest_base"])

        before_py = len(py_zepto_payloads)
        disp = dispatch_transactional_playbook(qt, execute_live=True, allow_zoho_failover=False)
        assert disp["dispatched"] is True
        assert len(py_zepto_payloads) == before_py + 1
        em_py = py_zepto_payloads[-1]
        assert em_py["subject"] == em_edge["subject"]
        assert "Your Calculation Worksheet &amp; Action Plan</h2>" in em_py["htmlbody"]
        assert qt["partner_rep_desk"] in em_py["htmlbody"]
        em_py_body_clean = em_py["htmlbody"].lower()
        for sku_tok in (
            "gh_soc2_cmmc_audit_workpapers",
            "gh_hipaa_iso27001_governance_kit",
            "gh_instant_compliance_worksheet_19",
        ):
            em_py_body_clean = em_py_body_clean.replace(sku_tok, " ")
        for bad in leak_words:
            assert bad not in em_py["subject"].lower()
            assert bad not in em_py_body_clean


@pytest.mark.host_estate
def test_phase2_html_healers_partners_section_nested_pro_hook_and_strict_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Verifies:
    1) normalize_html_callout_message_match -> reposition_affiliate_placements_from_gsc_signals
       preserves 'partners-section' and resolves non-Vanta framework primary partner.
    2) Balanced <div> matching on nested .pro-hook-sample-unlock and protection of inner spans
       against _clean_pro_hook_outer_spans overwrite.
    3) Seeded stray leak inside #calculator-workspace-anchor on strict_isolated DORA heals cleanly,
       records 'gainhelm_framework_isolation' in repaired, and converges to 0 diffs on Pass 2.
    """
    import pseofactory.affiliates as aff_mod
    from pseofactory.affiliates import (
        normalize_html_callout_message_match,
        reposition_affiliate_placements_from_gsc_signals,
    )
    from pseofactory.maintenance import RetroReflectionEngine
    import pseofactory.visual_primitives as vp_mod

    has_gainhelm_cross_framework_leak = getattr(aff_mod, "has_gainhelm_cross_framework_leak", None)
    _clean_pro_hook_outer_spans = getattr(vp_mod, "_clean_pro_hook_outer_spans", None)
    _gainhelm_pro_card_has_mismatch = getattr(vp_mod, "_gainhelm_pro_card_has_mismatch", None)

    pentest_slug = "penetration-testing-scoping-cost-calculator"
    pentest_html = (
        f'<html><head><link rel="canonical" href="https://gainhelm.com/tools/{pentest_slug}/">'
        "<title>Penetration Testing Calculator</title></head><body><h1>Pentest Scope</h1>"
        '<section class="partners-section"><div class="partner-card">'
        '<a href="/r/cobalt_pentest">Cobalt</a></div></section></body></html>'
    )
    # Direct reposition_affiliate_placements_from_gsc_signals on <section class="partners-section"> is Pass 1 == Pass 2 idempotent
    # While cobalt_pentest is pending in monetization_vault.json, zero /r/ links render.
    direct_pending_p1, _ = reposition_affiliate_placements_from_gsc_signals(
        pentest_html, property_id="gainhelm", slug=pentest_slug
    )
    direct_pending_p2, _ = reposition_affiliate_placements_from_gsc_signals(
        direct_pending_p1, property_id="gainhelm", slug=pentest_slug
    )
    assert direct_pending_p1 == direct_pending_p2
    assert not BeautifulSoup(direct_pending_p1, "html.parser").select('a[href^="/r/"]')

    # Once cobalt_pentest flips to live in monetization_vault.json, partners-section preserves class and primary partner.
    from pseofactory import affiliates as aff_mod

    vault_copy = json.loads(aff_mod.MONETIZATION_VAULT_PATH.read_text(encoding="utf-8"))
    vault_copy["properties"]["gainhelm"]["partners"]["cobalt_pentest"]["status"] = "live"
    tmp_vault = tmp_path / "monetization_vault.json"
    tmp_vault.write_text(json.dumps(vault_copy), encoding="utf-8")
    monkeypatch.setattr(aff_mod, "MONETIZATION_VAULT_PATH", tmp_vault)

    direct_p1, _ = reposition_affiliate_placements_from_gsc_signals(
        pentest_html, property_id="gainhelm", slug=pentest_slug
    )
    direct_p2, _ = reposition_affiliate_placements_from_gsc_signals(
        direct_p1, property_id="gainhelm", slug=pentest_slug
    )
    assert direct_p1 == direct_p2
    direct_sec = BeautifulSoup(direct_p1, "html.parser").select_one("section.partners-section")
    assert direct_sec is not None
    assert direct_sec.get("data-primary-partner") == "cobalt_pentest"
    assert direct_sec.get("data-partner") == "cobalt_pentest"

    norm_pentest = normalize_html_callout_message_match(pentest_html, property_id="gainhelm")
    repo_pentest, _ = reposition_affiliate_placements_from_gsc_signals(
        norm_pentest, property_id="gainhelm", slug=pentest_slug
    )
    repo_soup = BeautifulSoup(repo_pentest, "html.parser")
    sec_tag = repo_soup.select_one("section.partners-section")
    assert sec_tag is not None, "partners-section class was dropped by reposition_affiliate_placements_from_gsc_signals"
    assert sec_tag.get("data-primary-partner") == "cobalt_pentest"
    assert sec_tag.get("data-partner") == "cobalt_pentest"

    assert callable(has_gainhelm_cross_framework_leak)
    assert callable(_clean_pro_hook_outer_spans)
    assert callable(_gainhelm_pro_card_has_mismatch)

    dora_slug = "dora-ict-third-party-risk-compliance-cost-calculator"
    nested_pro_html = (
        f'<html><head><link rel="canonical" href="https://gainhelm.com/tools/{dora_slug}/">'
        "<title>DORA Calculator</title></head><body><h1>DORA</h1>"
        '<div id="post-calculation-upgrade-drawer" data-offer-sku="gh_hipaa_iso27001_governance_kit" data-offer-price="49" data-calculated-amount="112100"></div>'
        '<div class="pro-hook-card">'
        '<span class="pro-hook-badge">SOC 2 Audit ($79)</span>'
        '<a class="pro-hook-link" href="#post-calculation-upgrade-drawer">Export ($79)</a>'
        '<div class="pro-hook-sample-unlock" data-mechanic="above_fold_packet_sample_unlock">'
        '<div class="preview-shell"><div class="preview-inner">Signed SOC 2 &amp; CMMC Workpaper (Locked - $79)</div></div>'
        '<div><a class="pro-hook-direct-checkout" href="/api/lead-capture?checkout=1&amp;sku=gh_soc2_cmmc_audit_workpapers" data-offer-sku="gh_soc2_cmmc_audit_workpapers" data-offer-price="79">Checkout ($79)</a></div>'
        "</div></div></body></html>"
    )
    healed_nested, _ = RetroReflectionEngine.retrofit_html(
        nested_pro_html, property_id="gainhelm", slug=dora_slug
    )
    nested_soup = BeautifulSoup(healed_nested, "html.parser")
    pro_card = nested_soup.select_one(".pro-hook-card")
    assert pro_card is not None
    su_div = pro_card.select_one(".pro-hook-sample-unlock")
    assert su_div is not None
    su_raw = str(su_div)
    assert len(re.findall(r"<div\b", su_raw, re.I)) == len(re.findall(r"</div>", su_raw, re.I))
    assert "Locked: $49" in su_div.get_text(" ", strip=True)
    assert not has_gainhelm_cross_framework_leak(str(pro_card), dora_slug)
    assert not has_gainhelm_cross_framework_leak(str(nested_soup.select_one("#post-calculation-upgrade-drawer")), dora_slug)

    # Verify outer-span cleanup never clobbers clean sample spans inside .pro-hook-sample-unlock
    inner_span_html = (
        f'<html><head><link rel="canonical" href="https://gainhelm.com/tools/{dora_slug}/">'
        "<title>DORA Calculator</title></head><body><h1>DORA</h1>"
        '<div id="post-calculation-upgrade-drawer" data-offer-sku="gh_hipaa_iso27001_governance_kit" data-offer-price="49" data-calculated-amount="112100"></div>'
        '<div class="pro-hook-card">'
        '<span class="pro-hook-badge">SOC 2 Audit ($79)</span>'
        '<a class="pro-hook-link" href="#post-calculation-upgrade-drawer">Export ($79)</a>'
        '<div class="pro-hook-sample-unlock" data-mechanic="above_fold_packet_sample_unlock">'
        '<div class="preview-shell"><span class="sample-preview-span">Line 3 DORA Register Preview (Locked - $79)</span></div>'
        '<div><a class="pro-hook-direct-checkout" href="/api/lead-capture?checkout=1&amp;sku=gh_hipaa_iso27001_governance_kit" data-offer-sku="gh_hipaa_iso27001_governance_kit" data-offer-price="49">Checkout ($49)</a></div>'
        "</div></div></body></html>"
    )
    healed_span_guard, _ = RetroReflectionEngine.retrofit_html(
        inner_span_html, property_id="gainhelm", slug=dora_slug
    )
    sg_soup = BeautifulSoup(healed_span_guard, "html.parser")
    sg_inner_span = sg_soup.select_one(".pro-hook-sample-unlock span.sample-preview-span")
    assert sg_inner_span is not None
    assert "Line 3 DORA Register Preview (Locked: $49)" in sg_inner_span.get_text(" ", strip=True)
    assert "Statutory Audit Workpaper:" not in str(sg_soup.select_one(".pro-hook-sample-unlock"))

    # Verify seeded cross-framework leak inside #calculator-workspace-anchor heals and converges
    seeded_dora_ws = (
        f'<html><head><link rel="canonical" href="https://gainhelm.com/tools/{dora_slug}/">'
        "<title>DORA Calculator</title></head><body><h1>DORA Cost</h1>"
        '<section id="calculator-workspace-anchor" class="interactive-calculator-container" data-vertical="soc2_grc_automation">'
        '<div class="calc-inputs-column">'
        '<p class="stale-leak">Estimate SOC 2 Type II, AICPA SSAE 18, HIPAA, and CMMC 2.0 C3PAO fees.</p>'
        '<input id="inp-entities" type="number" value="4">'
        "</div>"
        "</section></body></html>"
    )
    ws_pass1, rep1 = RetroReflectionEngine.retrofit_html(
        seeded_dora_ws, property_id="gainhelm", slug=dora_slug
    )
    assert "gainhelm_framework_isolation" in rep1
    ws_soup = BeautifulSoup(ws_pass1, "html.parser")
    ws_sec = ws_soup.select_one("#calculator-workspace-anchor")
    assert ws_sec is not None
    assert ws_sec.select_one("#inp-entities") is not None
    assert not has_gainhelm_cross_framework_leak(str(ws_sec), dora_slug)

    ws_pass2, rep2 = RetroReflectionEngine.retrofit_html(
        ws_pass1, property_id="gainhelm", slug=dora_slug
    )
    assert ws_pass2 == ws_pass1
    assert rep2 == []

    # Verify clean .pro-hook-card containing ($0) and ($57,590 DE Baseline) has zero mismatch,
    # preserves outer <span> labels mentioning ($0) or ($57,590 DE Baseline), and hits fast-path.
    clean_outer_span = (
        '<span class="pro-hook-meta-note">DORA Zero-Baseline ($0) and ($57,590 DE Baseline) Export</span>'
    )
    clean_pro_card = (
        '<div class="pro-hook-card">'
        f"{clean_outer_span}"
        '<a class="pro-hook-link" href="#post-calculation-upgrade-drawer">Export DORA Workpaper ($49)</a>'
        '<div class="pro-hook-sample-unlock" data-mechanic="above_fold_packet_sample_unlock">'
        "<div>Unlocked Sample Preview ($57,590 DE Baseline): Line 1 DORA ICT Control Matrix | "
        "Line 3 Signed Audit Workpaper (Locked: $49)</div>"
        '<div><a class="pro-hook-direct-checkout" href="/api/lead-capture?checkout=1&amp;sku=gh_hipaa_iso27001_governance_kit" '
        'data-offer-sku="gh_hipaa_iso27001_governance_kit" data-offer-price="49">Instant Checkout &amp; Download ($49) &rarr;</a></div>'
        "</div></div>"
    )
    assert _gainhelm_pro_card_has_mismatch(
        clean_pro_card, dora_slug, "gh_hipaa_iso27001_governance_kit", "49"
    ) is False
    assert (
        _clean_pro_hook_outer_spans(
            clean_pro_card,
            tool_slug=dora_slug,
            default_state="DE",
            offer_price="49",
            is_gainhelm=True,
        )
        == clean_pro_card
    )

    clean_dora_base, _ = RetroReflectionEngine.retrofit_html(
        (LIVE_GAINHELM_REPO / "dist" / "tools" / dora_slug / "index.html").read_text(encoding="utf-8"),
        property_id="gainhelm",
        slug=dora_slug,
    )
    from pseofactory.visual_primitives import _find_balanced_div_span
    pro_sp = _find_balanced_div_span(clean_dora_base, "pro-hook-card", attr_name="class")
    if pro_sp is not None:
        clean_dora_with_baseline = clean_dora_base[: pro_sp[0]] + clean_pro_card + clean_dora_base[pro_sp[1] :]
    else:
        qub_sp = _find_balanced_div_span(clean_dora_base, "calc-result-quick-unlock-bar", attr_name="id")
        assert qub_sp is not None
        clean_dora_with_baseline = clean_dora_base[: qub_sp[1]] + "\n" + clean_pro_card + clean_dora_base[qub_sp[1] :]
    assert RetroReflectionEngine._gainhelm_needs_framework_isolation_heal(clean_dora_with_baseline, dora_slug) is False
    RetroReflectionEngine._RETROFIT_HTML_CACHE.clear()
    clean_pass_out, clean_repairs = RetroReflectionEngine.retrofit_html(
        clean_dora_with_baseline, property_id="gainhelm", slug=dora_slug
    )
    assert clean_repairs == []
    assert clean_pass_out == clean_dora_with_baseline
    assert clean_outer_span in clean_pass_out


def test_phase2_bare_generic_sku_soc2_short_and_cmmc_isolation(tmp_path: Path) -> None:
    """
    Verifies Python <-> Edge JS parity across:
    - 12 bare generic slugs + informational_governance resolving to "/" on GET & POST
    - 5 explicit sku=gh_hipaa_iso27001_governance_kit (vertical="") -> /tools/iso-27001-certification-cost-calculator/
    - 5 explicit sku=gh_soc2_cmmc_audit_workpapers (vertical="") -> /tools/soc-2-audit-cost-calculator/
    - Short "soc2" vertical on ("", "general", "index", "home", "homepage") -> /tools/soc-2-audit-cost-calculator/
    - "home" / "homepage" / *-hub on $19 gh_instant_compliance_worksheet_19
    - Python CMMC synthesize_personalized_audit_workpaper + render_transactional_playbook_email free of HIPAA/AICPA/PCI DSS
    """
    from urllib.parse import urlparse
    from pseofactory.edge import generate_edge_lead_capture_function
    from pseofactory.partner_tracker import (
        render_transactional_playbook_email,
        resolve_lead_monetization_offer,
        synthesize_personalized_audit_workpaper,
    )

    bare_slugs_6 = ("", "general", "index", "home", "homepage", "compliance-hub")
    bare_cases = []
    # 12 bare generic slugs (6 slugs x vertical in ("", "general"))
    for vert in ("", "general"):
        for slug in bare_slugs_6:
            bare_cases.append((slug, vert, "", "/"))
    # informational_governance across generic slugs
    for slug in bare_slugs_6:
        bare_cases.append((slug, "informational_governance", "", "/"))
    # 5 explicit sku=gh_hipaa_iso27001_governance_kit (vertical="")
    five_gen = ("", "general", "index", "home", "homepage")
    for slug in five_gen:
        bare_cases.append((slug, "", "gh_hipaa_iso27001_governance_kit", "/tools/iso-27001-certification-cost-calculator/"))
    # 5 explicit sku=gh_soc2_cmmc_audit_workpapers (vertical="")
    for slug in five_gen:
        bare_cases.append((slug, "", "gh_soc2_cmmc_audit_workpapers", "/tools/soc-2-audit-cost-calculator/"))
    # Short "soc2" vertical on 5 generic slugs
    for slug in five_gen:
        bare_cases.append((slug, "soc2", "", "/tools/soc-2-audit-cost-calculator/"))

    roundtrip_payload = []
    for idx, (slug, vert, sku, exp_path) in enumerate(bare_cases):
        lid = f"lead_parity_{idx}"
        offer = resolve_lead_monetization_offer(
            "gainhelm",
            slug,
            vertical=vert,
            lead_id=lid,
            sku=sku,
        )
        assert urlparse(offer["success_url"]).path == exp_path, (slug, vert, sku, offer["success_url"])
        assert urlparse(offer["cancel_url"]).path == exp_path, (slug, vert, sku, offer["cancel_url"])
        assert offer["success_url"].startswith(f"https://gainhelm.com{exp_path}?checkout_status=success")
        assert offer["cancel_url"].startswith(f"https://gainhelm.com{exp_path}?checkout_status=cancelled")
        roundtrip_payload.append({
            "slug": slug,
            "vert": vert,
            "sku": sku,
            "exp_path": exp_path,
            "exp_offer_sku": offer["offer_sku"],
            "checkout_ep": offer["live_checkout_endpoint"],
            "py_checkout_url": offer["checkout_url"],
            "py_success_url": offer["success_url"],
            "py_cancel_url": offer["cancel_url"],
            "py_vertical": offer.get("vertical", ""),
        })

    # $19 quick worksheet parity for "home", "homepage", "compliance-hub"
    for q_slug, q_vert, exp_q_path in (
        ("home", "", "/tools/soc-2-audit-cost-calculator/"),
        ("homepage", "", "/tools/soc-2-audit-cost-calculator/"),
        ("compliance-hub", "", "/"),
        ("home", "dora_eu_ict_resilience", "/tools/dora-ict-third-party-risk-compliance-cost-calculator/"),
        ("homepage", "dora", "/tools/dora-ict-third-party-risk-compliance-cost-calculator/"),
    ):
        q_offer = resolve_lead_monetization_offer(
            "gainhelm",
            q_slug,
            vertical=q_vert,
            sku="gh_instant_compliance_worksheet_19",
            lead_id=f"lead_q19_{q_slug}_{q_vert or 'none'}",
        )
        assert q_offer["offer_sku"] == "gh_instant_compliance_worksheet_19"
        assert q_offer["offer_price_usd"] == 19.0
        assert urlparse(q_offer["success_url"]).path == exp_q_path, (q_slug, q_vert, q_offer["success_url"])
        assert urlparse(q_offer["cancel_url"]).path == exp_q_path, (q_slug, q_vert, q_offer["cancel_url"])

    edge_js = _strip_esm_exports(
        generate_edge_lead_capture_function(property_id="gainhelm")
    )
    vm_runner = f"""
import vm from "node:vm";
const sandbox = {{
  URL,
  URLSearchParams,
  Request,
  Response,
  Headers,
  fetch: async (url) => {{
    if (String(url).includes("api.stripe.com/v1/checkout/sessions")) {{
      return new Response(JSON.stringify({{
        id: "cs_live_bare_parity",
        url: "https://checkout.stripe.com/c/pay/cs_live_bare_parity",
      }}), {{ status: 200 }});
    }}
    throw new Error("Unexpected fetch: " + String(url));
  }},
  console, Math, Date, JSON, Number, String, Boolean, Array, Object, Map, Set, Error, RegExp,
  encodeURIComponent, decodeURIComponent, atob: globalThis.atob, btoa: globalThis.btoa,
}};
const ctx = vm.createContext(sandbox);
vm.runInContext({json.dumps(edge_js)}, ctx);
const env = {{ STRIPE_SECRET_KEY: "sk_live_mock" }};
const cases = {json.dumps(roundtrip_payload)};
(async () => {{
  let caseIdx = 0;
  for (const c of cases) {{
    caseIdx += 1;
    const getRes = await ctx.onRequestGet({{
      request: new Request(c.checkout_ep + "&format=json"),
      env,
    }});
    if (getRes.status !== 200) throw new Error("GET failed: " + JSON.stringify(c));
    const getJson = await getRes.json();
    if (getJson.offer_sku !== c.exp_offer_sku || getJson.vertical !== c.py_vertical) {{
      throw new Error("GET SKU/vertical mismatch: " + JSON.stringify({{ c, getJson }}));
    }}
    if (getJson.checkout_url !== "https://checkout.stripe.com/c/pay/cs_live_bare_parity") {{
      throw new Error("GET checkout_url mismatch: " + getJson.checkout_url);
    }}
    const sUrl = new URL(getJson.success_url);
    const pySUrl = new URL(c.py_success_url);
    if (sUrl.pathname !== c.exp_path || sUrl.pathname !== pySUrl.pathname || sUrl.searchParams.get("sku") !== pySUrl.searchParams.get("sku")) {{
      throw new Error("GET success_url mismatch: " + JSON.stringify({{ c, got: getJson.success_url }}));
    }}
    if (getJson.cancel_url !== c.py_cancel_url) {{
      throw new Error("GET cancel_url mismatch: " + JSON.stringify({{ c, got: getJson.cancel_url }}));
    }}

    const postRes = await ctx.onRequestPost({{
      request: new Request("https://gainhelm.com/api/lead-capture", {{
        method: "POST",
        headers: {{
          "Content-Type": "application/json",
          "CF-Connecting-IP": `198.51.100.${{caseIdx}}`,
        }},
        body: JSON.stringify({{
          tool_slug: c.slug,
          vertical: c.vert,
          sku: c.sku,
          email: `ciso+bare${{caseIdx}}@enterprise-client.io`,
          state: "DE",
          calculated_amount: 85000,
          partner_sharing_consent: true,
        }}),
      }}),
      env,
    }});
    if (postRes.status !== 200) throw new Error("POST failed: " + JSON.stringify(c));
    const postJson = await postRes.json();
    const postSUrl = new URL(postJson.success_url);
    const postCUrl = new URL(postJson.cancel_url);
    if (postSUrl.pathname !== c.exp_path || postCUrl.pathname !== c.exp_path || postJson.offer_sku !== c.exp_offer_sku) {{
      throw new Error("POST toolPath/SKU mismatch: " + JSON.stringify({{ c, postS: postJson.success_url, postC: postJson.cancel_url }}));
    }}
  }}
  // Completely bare GET without tool_slug/vertical/sku resolves to "/"
  const omittedGet = await ctx.onRequestGet({{
    request: new Request("https://gainhelm.com/api/lead-capture?checkout=1&format=json"),
    env,
  }});
  const omittedJson = await omittedGet.json();
  if (new URL(omittedJson.success_url).pathname !== "/" || new URL(omittedJson.cancel_url).pathname !== "/") {{
    throw new Error("Omitted bare GET did not resolve to '/': " + JSON.stringify(omittedJson));
  }}
  console.log("BARE_SKU_SOC2_PARITY_OK");
}})().catch((e) => {{ console.error(e); process.exit(1); }});
"""
    vm_file = tmp_path / "bare_sku_soc2_parity.mjs"
    vm_file.write_text(vm_runner, encoding="utf-8")
    proc = subprocess.run(["node", str(vm_file)], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    assert "BARE_SKU_SOC2_PARITY_OK" in proc.stdout

    # Python CMMC workpaper & email must stay free of HIPAA / AICPA / PCI DSS
    cmmc_slug = "cmmc-2-0-compliance-cost-calculator"
    cmmc_rec = {
        "lead_id": "lead_cmmc_py_iso",
        "property_id": "gainhelm",
        "tool_slug": cmmc_slug,
        "vertical": "cmmc_dod_defense",
        "email": "fso@defense-contractor.io",
        "state": "VA",
        "calculated_amount": 132000.0,
    }
    for wp_mode in ("free_playbook", "paid_toolkit"):
        cmmc_wp = synthesize_personalized_audit_workpaper("gainhelm", cmmc_slug, cmmc_rec, mode=wp_mode)
        wp_blob = json.dumps({
            "reconciliation_schedule": cmmc_wp["reconciliation_schedule"],
            "sensitivity_matrix": cmmc_wp["sensitivity_matrix"],
            "statutory_trend_timeseries": cmmc_wp["statutory_trend_timeseries"],
            "deliverables": cmmc_wp["deliverables"],
            "html_report": cmmc_wp["html_report"],
            "csv_content": cmmc_wp["csv_content"],
        }).lower()
        assert not _blob_has_forbidden_tokens(wp_blob, ("hipaa", "aicpa", "pci dss")), wp_mode
    cmmc_email = render_transactional_playbook_email(cmmc_rec)
    em_blob = json.dumps({
        "subject": cmmc_email["subject"],
        "text_body": cmmc_email.get("text_body", ""),
        "html_body": cmmc_email["html_body"],
    }).lower()
    assert not _blob_has_forbidden_tokens(em_blob, ("hipaa", "aicpa", "pci dss")), em_blob


def test_edge_lead_id_only_lookup_no_stripe_email_and_bare_generic_parity(tmp_path: Path) -> None:
    """
    Verifies GainHelm Edge lead-capture + Python partner_tracker parity:
    1. onRequestGet resolves persisted record BEFORE offer selection so ?checkout=1&lead_id=<id>&redirect=1
       and ?fulfill=1 charge exact $19/$49/$79 SKUs and route to /tools/<framework>/ or /.
    2. When STRIPE_SECRET_KEY is absent, dispatched ZeptoMail HTML links preserve $19/$49 sku= and keep
       bare generic leads free of synthetic vertical/default-$79 sku overrides.
    3. Python dora-hub ($49 -> '/') vs compliance-hub ($79 -> '/'), bare generic ('/'), and CMMC
       zero ISO/IEC 27001 fallback match Edge JS behavior cleanly.
    Zero em-dashes. Zero en-dashes.
    """
    import json
    import re
    import subprocess
    from pseofactory.edge import generate_edge_lead_capture_function
    from pseofactory.partner_tracker import (
        ingest_playbook_subscription,
        ingest_qualified_lead,
        render_transactional_playbook_email,
        resolve_lead_monetization_offer,
        synthesize_personalized_audit_workpaper,
    )

    off_dora_hub = resolve_lead_monetization_offer("gainhelm", "dora-hub", "")
    off_comp_hub = resolve_lead_monetization_offer("gainhelm", "compliance-hub", "")
    assert off_dora_hub["offer_sku"] == "gh_hipaa_iso27001_governance_kit" and off_dora_hub["offer_price_usd"] == 49.0
    assert off_dora_hub["success_url"].startswith("https://gainhelm.com/?")
    assert off_comp_hub["offer_sku"] == "gh_soc2_cmmc_audit_workpapers" and off_comp_hub["offer_price_usd"] == 79.0
    assert off_comp_hub["success_url"].startswith("https://gainhelm.com/?")

    ledger_p = tmp_path / "gh_leads.jsonl"
    q_gen = ingest_qualified_lead(
        property_id="gainhelm",
        tool_slug="general",
        email="lead@enterprise-audit.com",
        state="NY",
        capital_band="50k_to_250k",
        calculated_amount=65000.0,
        partner_sharing_consent=True,
        leads_ledger_path=ledger_p,
    )
    p_gen = ingest_playbook_subscription(
        property_id="gainhelm",
        tool_slug="general",
        email="play@enterprise-audit.com",
        calculated_amount=65000.0,
        leads_ledger_path=ledger_p,
    )
    assert "vertical=" not in q_gen["checkout_url"] and "sku=" not in q_gen["checkout_url"]
    assert "vertical=" not in p_gen["checkout_url"] and "sku=" not in p_gen["checkout_url"]
    assert q_gen.get("has_explicit_vertical") is False and p_gen.get("has_explicit_vertical") is False
    em_gen = render_transactional_playbook_email(q_gen)
    assert "/tools/soc-2-audit-cost-calculator/" not in em_gen["html_body"]

    cmmc_slug = "cmmc-2-0-compliance-cost-calculator"
    for wp_mode in ("free_playbook", "paid_toolkit"):
        cmmc_wp = synthesize_personalized_audit_workpaper(
            "gainhelm", cmmc_slug, {"calculated_amount": 85000.0}, mode=wp_mode
        )
        cmmc_blob = json.dumps(cmmc_wp).lower()
        assert "iso/iec 27001" not in cmmc_blob and "iso_27006" not in cmmc_blob

    lead_js = generate_edge_lead_capture_function(property_id="gainhelm")
    vm_code = _strip_esm_exports(lead_js)
    vm_driver = """
const kvStore = new Map();
const envWithStripe = {
  LEADS_KV: {
    get: async (k, opts) => { const v = kvStore.get(k); return v ? (opts && opts.type === 'json' ? JSON.parse(v) : v) : null; },
    put: async (k, v) => { kvStore.set(k, v); },
  },
  STRIPE_SECRET_KEY: 'sk_test_dummy',
  ZEPTOMAIL_TOKEN: 'zepto_dummy',
};
const envNoStripe = {
  LEADS_KV: envWithStripe.LEADS_KV,
  ZEPTO_API_KEY: 'unused',
  ZEPTOMAIL_TOKEN: 'zepto_dummy',
  PLAYBOOK_FREE_EMAIL_ENABLED: '1',
};
let sentEmails = [];
let stripeBodies = [];
globalThis.fetch = async (url, opts) => {
  const u = String(url);
  if (u.includes('stripe.com')) {
    stripeBodies.push(String(opts.body));
    return { ok: true, status: 200, json: async () => ({ id: 'cs_test_1', url: 'https://checkout.stripe.com/c/pay/cs_test_1' }) };
  }
  if (u.includes('zeptomail.com')) {
    sentEmails.push(JSON.parse(opts.body));
    return { ok: true, status: 200, json: async () => ({ data: [{ message_id: 'zm_1' }] }) };
  }
  return { ok: false, status: 404, json: async () => ({}) };
};

(async () => {
  const cases = [
    { name: 'bare_root', body: { email: 'a@realco.com', state: 'DE', calculated_amount: 65000, partner_sharing_consent: true }, expectedSku: 'gh_soc2_cmmc_audit_workpapers', expectedCents: '7900', expectedPath: '/' },
    { name: 'bare_19', body: { email: 'b@realco.com', state: 'DE', calculated_amount: 65000, partner_sharing_consent: true, sku: 'gh_instant_compliance_worksheet_19' }, expectedSku: 'gh_instant_compliance_worksheet_19', expectedCents: '1900', expectedPath: '/tools/soc-2-audit-cost-calculator/' },
    { name: 'hipaa_49', body: { email: 'c@realco.com', state: 'DE', calculated_amount: 65000, partner_sharing_consent: true, tool_slug: 'hipaa-breach-fine-calculator' }, expectedSku: 'gh_hipaa_iso27001_governance_kit', expectedCents: '4900', expectedPath: '/tools/hipaa-breach-fine-calculator/' },
    { name: 'dora_hub', body: { email: 'd@realco.com', state: 'DE', calculated_amount: 65000, partner_sharing_consent: true, tool_slug: 'dora-hub' }, expectedSku: 'gh_hipaa_iso27001_governance_kit', expectedCents: '4900', expectedPath: '/' },
    { name: 'cmmc_79', body: { email: 'e@realco.com', state: 'DE', calculated_amount: 65000, partner_sharing_consent: true, tool_slug: 'cmmc-compliance-cost-calculator' }, expectedSku: 'gh_soc2_cmmc_audit_workpapers', expectedCents: '7900', expectedPath: '/tools/cmmc-compliance-cost-calculator/' },
  ];
  for (const c of cases) {
    kvStore.clear();
    stripeBodies = [];
    const postResp = await onRequestPost({
      request: new Request('https://gainhelm.com/api/lead-capture', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(c.body),
      }),
      env: envWithStripe,
    });
    const postJson = await postResp.json();
    if (postJson.offer_sku !== c.expectedSku) throw new Error(c.name + ' post sku mismatch: ' + postJson.offer_sku);
    const lid = postJson.lead_id;
    const ffResp = await onRequestGet({
      request: new Request('https://gainhelm.com/api/lead-capture?fulfill=1&lead_id=' + encodeURIComponent(lid)),
      env: envWithStripe,
    });
    if (ffResp.status !== 402) throw new Error(c.name + ' expected 402 got ' + ffResp.status);
    stripeBodies = [];
    const chkResp = await onRequestGet({
      request: new Request('https://gainhelm.com/api/lead-capture?checkout=1&lead_id=' + encodeURIComponent(lid) + '&redirect=1'),
      env: envWithStripe,
    });
    const hdrSku = chkResp.headers.get('X-Edge-Offer-Sku');
    const sp = new URLSearchParams(stripeBodies[0] || '');
    const succPath = new URL(sp.get('success_url')).pathname;
    if (hdrSku !== c.expectedSku || sp.get('line_items[0][price_data][unit_amount]') !== c.expectedCents || succPath !== c.expectedPath) {
      throw new Error(c.name + ' lead_id-only mismatch: ' + JSON.stringify({ hdrSku, cents: sp.get('line_items[0][price_data][unit_amount]'), succPath }));
    }
  }
  for (const c of cases.slice(0, 4)) {
    kvStore.clear();
    sentEmails = [];
    await onRequestPost({
      request: new Request('https://gainhelm.com/api/lead-capture', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(c.body),
      }),
      env: envNoStripe,
    });
    const html = (sentEmails[0] && sentEmails[0].htmlbody) || '';
    const hrefMatch = html.match(/href="([^"]+checkout=1[^"]+)"/);
    if (!hrefMatch) throw new Error(c.name + ' missing no-stripe email checkout href');
    const decodedHref = hrefMatch[1].replace(/&amp;/g, '&');
    const qs = new URL(decodedHref).searchParams;
    if (c.name === 'bare_root' && (qs.get('vertical') || qs.get('sku'))) {
      throw new Error('bare_root email link leaked vertical/sku: ' + hrefMatch[1]);
    }
    if ((c.name === 'bare_19' || c.name === 'hipaa_49' || c.name === 'dora_hub') && qs.get('sku') !== c.expectedSku) {
      throw new Error(c.name + ' no-stripe email lost sku: ' + hrefMatch[1]);
    }
  }
  console.log('EDGE_LEAD_ID_AND_EMAIL_PARITY_OK');
})().catch((e) => { console.error(e); process.exit(1); });
"""
    vm_script = tmp_path / "edge_lead_id_and_email_parity.mjs"
    vm_script.write_text(vm_code + "\n" + vm_driver, encoding="utf-8")
    proc = subprocess.run(["node", str(vm_script)], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    assert "EDGE_LEAD_ID_AND_EMAIL_PARITY_OK" in proc.stdout


def test_phase2_sku_and_vertical_propagation_across_email_datapack_and_edge_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Verifies Bug 4 fixes across all 4 tenants:
    1. render_transactional_playbook_email preserves exact $19 worksheet SKUs and explicit $49 overrides
       across GainHelm (soc-2+$19, dora+$19, soc-2+$49), ProfitHelm (+$19), Prexvo (+$19), LienBond (+$19),
       while keeping bare generic GainHelm leads on '/'.
    2. GainHelm email checkout_endpoint URLs round-trip into Edge Node vm onRequestGet with exact 1900/4900/7900 cents.
    3. settle_post_calculation_datapack_upgrade preserves '/' on stored bare-generic leads (has_explicit_vertical=False)
       and charges $19 on stored $19 worksheet leads.
    4. sync_edge_leads_to_ledger propagates sku= and explicit-vertical filtering cleanly on queued_central_responder
       Edge leads (including ZeptoMail dispatch HTML links).
    Zero em-dashes. Zero en-dashes.
    """
    from urllib.parse import parse_qs, urlparse
    import pseofactory.affiliates as aff_mod
    from pseofactory.edge import generate_edge_lead_capture_function
    from pseofactory.partner_tracker import (
        ingest_qualified_lead,
        render_transactional_playbook_email,
        resolve_lead_monetization_offer,
        settle_post_calculation_datapack_upgrade,
        sync_edge_leads_to_ledger,
        synthesize_personalized_audit_workpaper,
    )

    gh_profiles = getattr(aff_mod, "GAINHELM_FRAMEWORK_PROFILES", None)
    assert isinstance(gh_profiles, dict) and len(gh_profiles) == 15, "Missing 15 GainHelm framework profiles"

    email_cases = [
        {
            "name": "gh_soc2_19",
            "rec": {
                "lead_id": "lead_gh_soc2_19",
                "property_id": "gainhelm",
                "tool_slug": "soc-2-audit-cost-calculator",
                "vertical": "soc2_grc_automation",
                "offer_sku": "gh_instant_compliance_worksheet_19",
                "email": "ciso@client-real.io",
                "calculated_amount": 65000.0,
            },
            "exp_sku": "gh_instant_compliance_worksheet_19",
            "exp_price": "19",
            "exp_cents": "1900",
            "exp_path": "/tools/soc-2-audit-cost-calculator/",
        },
        {
            "name": "gh_dora_19",
            "rec": {
                "lead_id": "lead_gh_dora_19",
                "property_id": "gainhelm",
                "tool_slug": "dora-ict-third-party-risk-compliance-cost-calculator",
                "vertical": "dora_eu_ict_resilience",
                "offer_sku": "gh_instant_compliance_worksheet_19",
                "email": "ciso@client-real.io",
                "calculated_amount": 85000.0,
            },
            "exp_sku": "gh_instant_compliance_worksheet_19",
            "exp_price": "19",
            "exp_cents": "1900",
            "exp_path": "/tools/dora-ict-third-party-risk-compliance-cost-calculator/",
        },
        {
            "name": "gh_soc2_49_override",
            "rec": {
                "lead_id": "lead_gh_soc2_49",
                "property_id": "gainhelm",
                "tool_slug": "soc-2-audit-cost-calculator",
                "vertical": "soc2_grc_automation",
                "offer_sku": "gh_hipaa_iso27001_governance_kit",
                "email": "ciso@client-real.io",
                "calculated_amount": 75000.0,
            },
            "exp_sku": "gh_hipaa_iso27001_governance_kit",
            "exp_price": "49",
            "exp_cents": "4900",
            "exp_path": "/tools/soc-2-audit-cost-calculator/",
        },
        {
            "name": "gh_bare_generic_79",
            "rec": {
                "lead_id": "lead_gh_bare_79",
                "property_id": "gainhelm",
                "tool_slug": "general",
                "vertical": "soc2_grc_automation",
                "has_explicit_vertical": False,
                "has_explicit_sku": False,
                "offer_sku": "gh_soc2_cmmc_audit_workpapers",
                "email": "ciso@client-real.io",
                "calculated_amount": 65000.0,
            },
            "exp_sku": "gh_soc2_cmmc_audit_workpapers",
            "exp_price": "79",
            "exp_cents": "7900",
            "exp_path": "/",
        },
        {
            "name": "ph_1031_19",
            "rec": {
                "lead_id": "lead_ph_1031_19",
                "property_id": "profithelm",
                "tool_slug": "section-1031-calculator",
                "offer_sku": "ph_instant_statutory_worksheet_19",
                "email": "cfo@client-real.io",
                "calculated_amount": 450000.0,
            },
            "exp_sku": "ph_instant_statutory_worksheet_19",
            "exp_price": "19",
            "exp_cents": "1900",
            "exp_path": "/tools/section-1031-calculator/",
        },
        {
            "name": "px_refi_19",
            "rec": {
                "lead_id": "lead_px_refi_19",
                "property_id": "prexvo",
                "tool_slug": "student-loan-refinance-break-even-calculator",
                "offer_sku": "px_instant_repayment_worksheet_19",
                "email": "borrower@client-real.io",
                "calculated_amount": 92000.0,
            },
            "exp_sku": "px_instant_repayment_worksheet_19",
            "exp_price": "19",
            "exp_cents": "1900",
            "exp_path": "/tools/student-loan-refinance-break-even-calculator/",
        },
        {
            "name": "lb_bond_19",
            "rec": {
                "lead_id": "lead_lb_bond_19",
                "property_id": "lienbond",
                "tool_slug": "contractor-license-bond-cost-calculator-by-credit-score",
                "offer_sku": "lb_instant_lien_bond_worksheet_19",
                "email": "contractor@client-real.io",
                "calculated_amount": 150000.0,
            },
            "exp_sku": "lb_instant_lien_bond_worksheet_19",
            "exp_price": "19",
            "exp_cents": "1900",
            "exp_path": "/tools/contractor-license-bond-cost-calculator-by-credit-score/",
        },
    ]

    all_roundtrip_items = []
    for case in email_cases:
        em = render_transactional_playbook_email(case["rec"])
        assert f"(${case['exp_price']})" in em["html_body"], (case["name"], em["html_body"])
        chk_ep = em["checkout_endpoint"]
        pb_ep = em["playbook_endpoint"]
        ff_ep = em["fulfillment_endpoint"]
        assert chk_ep in em["html_body"]
        assert pb_ep in em["html_body"]
        for ep_name, ep_val in (
            ("checkout_endpoint", chk_ep),
            ("playbook_endpoint", pb_ep),
            ("fulfillment_endpoint", ff_ep),
        ):
            qs = parse_qs(urlparse(ep_val).query)
            if case["name"] == "gh_bare_generic_79":
                assert "sku" not in qs and "vertical" not in qs, (ep_name, ep_val)
            else:
                assert qs.get("sku") == [case["exp_sku"]], (case["name"], ep_name, ep_val)
        if case["name"] == "gh_bare_generic_79":
            assert "/tools/soc-2-audit-cost-calculator/" not in em["html_body"]
        if case["name"] == "gh_dora_19":
            assert not _blob_has_forbidden_tokens(em["html_body"], ("soc 2", "soc2", "cmmc", "aicpa", "hipaa"))
        py_offer = resolve_lead_monetization_offer(
            property_id=case["rec"]["property_id"],
            tool_slug=case["rec"]["tool_slug"],
            vertical=case["rec"].get("vertical", ""),
            lead_id=case["rec"]["lead_id"],
            sku="" if case["name"] == "gh_bare_generic_79" else case["exp_sku"],
        )
        assert py_offer["offer_sku"] == case["exp_sku"], (case["name"], py_offer)
        assert float(py_offer["offer_price_usd"]) == float(case["exp_price"]), (case["name"], py_offer)
        all_roundtrip_items.append(
            {
                "name": case["name"],
                "property_id": case["rec"]["property_id"],
                "lead_id": case["rec"]["lead_id"],
                "tool_slug": case["rec"]["tool_slug"],
                "rec": case["rec"],
                "checkout_ep": chk_ep,
                "playbook_ep": pb_ep,
                "fulfill_ep": ff_ep,
                "exp_sku": case["exp_sku"],
                "exp_price": float(case["exp_price"]),
                "exp_cents": case["exp_cents"],
                "exp_path": case["exp_path"],
                "exp_title": py_offer["offer_title"],
                "exp_authority": py_offer["statutory_authority"],
                "exp_deliverables": list(py_offer["deliverables"]),
                "is_bare_generic": case["name"] == "gh_bare_generic_79",
            }
        )

    extra_offer_specs = [
        (
            "px_slot_299",
            "prexvo",
            "student-loan-refinance-break-even-calculator",
            "",
            "px_verified_partner_slot",
            ["($19)", "($39)", "($49)", "($79)"],
            [],
        ),
        (
            "gh_slot_299",
            "gainhelm",
            "soc-2-audit-cost-calculator",
            "",
            "gh_verified_partner_slot",
            ["($19)", "($39)", "($49)", "($79)"],
            [],
        ),
        (
            "ph_slot_299",
            "profithelm",
            "section-1031-calculator",
            "",
            "ph_verified_partner_slot",
            ["($19)", "($39)", "($49)", "($79)"],
            [],
        ),
        (
            "px_std_39",
            "prexvo",
            "student-loan-refinance-break-even-calculator",
            "",
            "px_refi_amortization_decision_audit",
            ["($19)", "($299)"],
            [],
        ),
        (
            "gh_bare_general_19",
            "gainhelm",
            "general",
            "",
            "gh_instant_compliance_worksheet_19",
            ["($39)", "($49)", "($79)"],
            [],
        ),
        (
            "gh_soc2_no_vert_19",
            "gainhelm",
            "soc-2-audit-cost-calculator",
            "",
            "gh_instant_compliance_worksheet_19",
            ["($39)", "($49)", "($79)"],
            [],
        ),
        (
            "gh_cmmc_19",
            "gainhelm",
            "cmmc-2-0-compliance-cost-calculator",
            "cmmc_dod_defense",
            "gh_instant_compliance_worksheet_19",
            ["($39)", "($49)", "($79)"],
            ["soc 2", "soc2", "aicpa", "hipaa"],
        ),
        (
            "gh_bare_general_79",
            "gainhelm",
            "general",
            "",
            "gh_soc2_cmmc_audit_workpapers",
            ["($19)", "($39)", "($49)", "($299)"],
            [],
        ),
        (
            "gh_dora_79_override",
            "gainhelm",
            "dora-ict-third-party-risk-compliance-cost-calculator",
            "",
            "gh_soc2_cmmc_audit_workpapers",
            ["($19)", "($39)", "($49)", "($299)"],
            [],
        ),
    ]
    for fw_k, fw_prof in gh_profiles.items():
        fw_price = int(round(float(fw_prof["offer_price_usd"])))
        extra_offer_specs.append(
            (
                f"gh_fw_{fw_k}",
                "gainhelm",
                str(fw_prof["default_sku_slug"]),
                "",
                "",
                [f"(${p})" for p in (19, 39, 49, 79, 299) if p != fw_price],
                list(fw_prof.get("forbidden_leak_tokens") or ()),
            )
        )

    soc2_prof = gh_profiles["soc2"]
    extra_offer_parity_cases = []
    for case_name, prop_id, slug_val, vert_val, sku_val, forbidden_prices, forbidden_tokens in extra_offer_specs:
        lead_id_extra = f"lead_{case_name}"
        py_extra = resolve_lead_monetization_offer(
            property_id=prop_id,
            tool_slug=slug_val,
            vertical=vert_val,
            lead_id=lead_id_extra,
            sku=sku_val,
        )
        if case_name == "gh_bare_general_19":
            assert "45 cfr 160.404" in py_extra["statutory_authority"].lower()
        elif case_name == "gh_soc2_no_vert_19":
            assert "45 cfr 160.404" not in py_extra["statutory_authority"].lower()
        elif case_name == "gh_cmmc_19":
            cmmc_meta_blob = f"{py_extra['statutory_authority']} {' '.join(py_extra['deliverables'])}".lower()
            assert not _blob_has_forbidden_tokens(cmmc_meta_blob, ("soc 2", "soc2", "aicpa", "hipaa"))
        elif case_name in ("gh_bare_general_79", "gh_dora_79_override"):
            assert py_extra["offer_sku"] == "gh_soc2_cmmc_audit_workpapers"
            assert py_extra["offer_price_usd"] == 79.0
            assert py_extra["offer_title"] == soc2_prof["offer_title"]
            assert py_extra["statutory_authority"] == soc2_prof["statutory_authority"]
            assert py_extra["deliverables"] == soc2_prof["deliverables"]
        elif case_name in ("px_slot_299", "gh_slot_299", "ph_slot_299"):
            assert py_extra["offer_price_usd"] == 299.0
            assert py_extra["offer_title"] == "Verified Calculator Partner Slot"
            assert py_extra["statutory_authority"] == "16 CFR Part 255 Commercial Partner Desk Attribution & Placement Protocol"
            assert len(py_extra["deliverables"]) == 4
        elif case_name.startswith("gh_fw_"):
            fw_key = case_name[len("gh_fw_") :]
            fw_prof = gh_profiles[fw_key]
            assert py_extra["offer_sku"] == fw_prof["offer_sku"]
            assert py_extra["offer_price_usd"] == fw_prof["offer_price_usd"]
            assert py_extra["offer_title"] == fw_prof["offer_title"]
            assert py_extra["statutory_authority"] == fw_prof["statutory_authority"]
            assert py_extra["deliverables"] == fw_prof["deliverables"]
            if fw_key == "dora":
                assert py_extra["offer_price_usd"] == 49.0
                assert "Register of Information" in " ".join(py_extra["deliverables"])
            elif fw_key == "fedramp":
                assert py_extra["offer_price_usd"] == 79.0
                assert "FIPS 140-3" in " ".join(py_extra["deliverables"])

        extra_offer_parity_cases.append(
            {
                "name": case_name,
                "property_id": prop_id,
                "lead_id": lead_id_extra,
                "tool_slug": slug_val,
                "vertical": vert_val,
                "req_sku": sku_val,
                "playbook_ep": py_extra["live_playbook_endpoint"],
                "checkout_ep": py_extra["live_checkout_endpoint"],
                "exp_sku": py_extra["offer_sku"],
                "exp_price": float(py_extra["offer_price_usd"]),
                "exp_cents": str(int(round(float(py_extra["offer_price_usd"]) * 100))),
                "exp_path": urlparse(py_extra["success_url"]).path,
                "exp_title": py_extra["offer_title"],
                "exp_authority": py_extra["statutory_authority"],
                "exp_deliverables": list(py_extra["deliverables"]),
                "forbidden_prices": forbidden_prices,
                "forbidden_tokens": forbidden_tokens,
            }
        )

    # Non-blocking #1: synthesize_personalized_audit_workpaper bare generic stored lead preserves clean checkout/playbook URLs
    wp_bare = synthesize_personalized_audit_workpaper(
        "gainhelm",
        "general",
        {
            "lead_id": "lead_wp_bare_stored",
            "property_id": "gainhelm",
            "tool_slug": "general",
            "vertical": "soc2_grc_automation",
            "has_explicit_vertical": False,
            "has_explicit_sku": False,
            "offer_sku": "gh_soc2_cmmc_audit_workpapers",
            "calculated_amount": 65000.0,
        },
        mode="free_playbook",
    )
    for wp_url_key in ("checkout_url", "playbook_url", "fulfillment_url"):
        assert "sku=" not in wp_bare[wp_url_key], (wp_url_key, wp_bare[wp_url_key])
        assert "vertical=" not in wp_bare[wp_url_key], (wp_url_key, wp_bare[wp_url_key])
    assert "/tools/soc-2-audit-cost-calculator/" not in wp_bare["html_report"]

    wp_dora_19 = synthesize_personalized_audit_workpaper(
        "gainhelm",
        "dora-ict-third-party-risk-compliance-cost-calculator",
        {
            "lead_id": "lead_wp_dora_19",
            "property_id": "gainhelm",
            "tool_slug": "dora-ict-third-party-risk-compliance-cost-calculator",
            "vertical": "dora_eu_ict_resilience",
            "offer_sku": "gh_instant_compliance_worksheet_19",
            "calculated_amount": 85000.0,
        },
        mode="free_playbook",
    )
    for wp_url_key in ("checkout_url", "playbook_url", "fulfillment_url"):
        assert "sku=gh_instant_compliance_worksheet_19" in wp_dora_19[wp_url_key], (wp_url_key, wp_dora_19[wp_url_key])
        assert "vertical=dora_eu_ict_resilience" in wp_dora_19[wp_url_key], (wp_url_key, wp_dora_19[wp_url_key])

    tenant_scripts = {
        prop: _strip_esm_exports(
            generate_edge_lead_capture_function(property_id=prop)
        )
        for prop in ("gainhelm", "profithelm", "prexvo", "lienbond")
    }
    vm_script = tmp_path / "email_all_tenants_roundtrip.mjs"
    vm_script.write_text(
        f"""
import vm from "node:vm";

const tenantScripts = {json.dumps(tenant_scripts)};
const items = {json.dumps(all_roundtrip_items)};
const extraOfferParityCases = {json.dumps(extra_offer_parity_cases)};
const kvMapByTenant = {{}};
const ctxByTenant = {{}};
const expectedCentsByLeadId = {{}};
let stripeBodies = [];

for (const [prop, jsCode] of Object.entries(tenantScripts)) {{
  const kvStore = new Map();
  kvMapByTenant[prop] = kvStore;
  const mockKv = {{
    async get(key, opts) {{
      const entry = kvStore.get(key);
      if (!entry) return null;
      if (opts && opts.type === "json") return JSON.parse(entry.value);
      return entry.value;
    }},
    async put(key, val, opts) {{
      kvStore.set(key, {{ value: String(val), metadata: (opts && opts.metadata) || {{}} }});
    }},
    async list({{ prefix = "", limit = 100 }} = {{}}) {{
      const keys = [];
      for (const [name, entry] of kvStore.entries()) {{
        if (!prefix || name.startsWith(prefix)) {{
          keys.push({{ name, metadata: entry.metadata }});
        }}
        if (keys.length >= limit) break;
      }}
      return {{ keys, list_complete: true }};
    }},
  }};
  const sandbox = {{
    URL,
    URLSearchParams,
    Request,
    Response,
    Headers,
    console,
    Math,
    Date,
    JSON,
    Number,
    String,
    Boolean,
    Array,
    Object,
    Map,
    Set,
    Error,
    RegExp,
    encodeURIComponent,
    decodeURIComponent,
    atob: globalThis.atob,
    btoa: globalThis.btoa,
    fetch: async (url, init = {{}}) => {{
      const sUrl = String(url);
      const mPaid = sUrl.match(/api\\.stripe\\.com\\/v1\\/checkout\\/sessions\\/(cs_live_PAIDFOR_[A-Za-z0-9_]+)$/);
      if (mPaid) {{
        const lid = mPaid[1].replace("cs_live_PAIDFOR_", "");
        return new Response(JSON.stringify({{
          id: mPaid[1],
          livemode: true,
          payment_status: "paid",
          amount_total: Number(expectedCentsByLeadId[lid] || 1900),
          currency: "usd",
          client_reference_id: lid,
          metadata: {{ lead_id: lid, property_id: prop }},
        }}), {{ status: 200 }});
      }}
      if (sUrl.includes("api.stripe.com/v1/checkout/sessions")) {{
        stripeBodies.push(String(init.body || ""));
        return new Response(JSON.stringify({{ id: "cs_live_rt", url: "https://checkout.stripe.com/c/pay/cs_live_rt" }}), {{ status: 200 }});
      }}
      throw new Error("Unexpected fetch in " + prop + ": " + sUrl);
    }},
  }};
  const ctx = vm.createContext(sandbox);
  vm.runInContext(jsCode, ctx);
  ctxByTenant[prop] = {{ ctx, mockKv }};
}}

function assertActionUrlSku(label, urlStr, expSku, isBareGeneric) {{
  const u = new URL("https://example.test" + urlStr);
  const gotSku = u.searchParams.get("sku");
  if (isBareGeneric) {{
    if (gotSku !== null || u.searchParams.get("vertical") !== null) {{
      throw new Error(label + " bare generic leaked sku/vertical: " + urlStr);
    }}
  }} else if (gotSku !== expSku) {{
    throw new Error(label + " expected sku=" + expSku + " got " + gotSku + " in " + urlStr);
  }}
}}

function assertOfferMetadata(label, payload, expSku, expPrice, expTitle, expAuthority, expDeliverables) {{
  if (!payload) return;
  if (payload.offer_sku !== expSku) {{
    throw new Error(label + " payload offer_sku mismatch: " + payload.offer_sku + " !== " + expSku);
  }}
  if (Number(payload.offer_price_usd) !== Number(expPrice)) {{
    throw new Error(label + " payload offer_price_usd mismatch: " + payload.offer_price_usd + " !== " + expPrice);
  }}
  if (payload.offer_title !== expTitle) {{
    throw new Error(label + " payload offer_title mismatch: " + payload.offer_title + " !== " + expTitle);
  }}
  if (payload.statutory_authority !== expAuthority) {{
    throw new Error(label + " payload statutory_authority mismatch: " + payload.statutory_authority + " !== " + expAuthority);
  }}
  if (JSON.stringify(payload.deliverables || []) !== JSON.stringify(expDeliverables)) {{
    throw new Error(label + " payload deliverables mismatch: " + JSON.stringify(payload.deliverables) + " !== " + JSON.stringify(expDeliverables));
  }}
}}

function assertOfferHtmlAndDeliverables(label, htmlText, payload, expSku, expPrice, expTitle, expAuthority, expDeliverables, forbiddenPrices = [], forbiddenTokens = [], requirePriceTag = true) {{
  if (!htmlText || (requirePriceTag && !htmlText.includes("($" + expPrice + ")"))) {{
    throw new Error(label + " missing ($" + expPrice + ") in HTML playbook");
  }}
  if (!htmlText.includes(expTitle)) {{
    throw new Error(label + " missing title '" + expTitle + "' in HTML playbook");
  }}
  if (expAuthority && !htmlText.includes(expAuthority)) {{
    throw new Error(label + " missing statutory_authority '" + expAuthority + "' in HTML playbook");
  }}
  for (const stalePrice of forbiddenPrices) {{
    if (htmlText.includes(stalePrice)) {{
      throw new Error(label + " leaked stale price " + stalePrice + " in HTML playbook");
    }}
  }}
  const htmlClean = String(htmlText).toLowerCase().replace(/gh_(?:soc2_cmmc_audit_workpapers|hipaa_iso27001_governance_kit|instant_compliance_worksheet_19)/g, " ");
  for (const badTok of forbiddenTokens) {{
    if (htmlClean.includes(String(badTok).toLowerCase())) {{
      throw new Error(label + " leaked forbidden token '" + badTok + "' in HTML playbook");
    }}
  }}
  for (const deliv of expDeliverables) {{
    if (!htmlText.includes(deliv)) {{
      throw new Error(label + " missing deliverable '" + deliv + "' in HTML playbook");
    }}
  }}
  assertOfferMetadata(label, payload, expSku, expPrice, expTitle, expAuthority, expDeliverables);
}}

(async () => {{
  const allOfferPrices = [19, 39, 49, 79, 299];
  for (const item of items) {{
    const {{ ctx, mockKv }} = ctxByTenant[item.property_id];
    const env = {{ STRIPE_SECRET_KEY: "sk_live_mock", LEADS_KV: mockKv }};
    ctx.__PSEOFACTORY_LEADS_BUFFER__ = [];
    const stalePrices = allOfferPrices.filter((p) => p !== Number(item.exp_price)).map((p) => "($" + p + ")");
    const itemForbiddenTokens = item.name === "gh_dora_19" ? ["soc 2", "soc2", "cmmc", "aicpa", "hipaa"] : [];

    // 1) Email checkout_endpoint -> Edge onRequestGet (?checkout=1&redirect=1 and &format=json)
    stripeBodies = [];
    const chkRedirRes = await ctx.onRequestGet({{
      request: new Request(item.checkout_ep + "&redirect=1"),
      env,
    }});
    if (chkRedirRes.status !== 302) throw new Error(item.name + " checkout redirect status " + chkRedirRes.status);
    const hdrSku = chkRedirRes.headers.get("X-Edge-Offer-Sku");
    const sp = new URLSearchParams(stripeBodies[0] || "");
    const cents = sp.get("line_items[0][price_data][unit_amount]");
    const succPath = new URL(sp.get("success_url")).pathname;
    if (hdrSku !== item.exp_sku || cents !== item.exp_cents || succPath !== item.exp_path) {{
      throw new Error(item.name + " checkout redirect mismatch: " + JSON.stringify({{ hdrSku, cents, succPath }}));
    }}

    stripeBodies = [];
    const chkJsonRes = await ctx.onRequestGet({{
      request: new Request(item.checkout_ep + "&format=json"),
      env,
    }});
    if (chkJsonRes.status !== 200) throw new Error(item.name + " checkout json status " + chkJsonRes.status);
    const chkJson = await chkJsonRes.json();
    assertOfferMetadata(item.name + " checkout json", chkJson, item.exp_sku, item.exp_price, item.exp_title, item.exp_authority, item.exp_deliverables);
    assertActionUrlSku(item.name + " checkout json playbook_url", chkJson.playbook_url, item.exp_sku, item.is_bare_generic);

    // 2) Email playbook_endpoint -> Edge onRequestGet (?playbook=1 JSON & HTML)
    const pbRes = await ctx.onRequestGet({{
      request: new Request(item.playbook_ep + "&format=json&synthetic_test=1"),
      env,
    }});
    if (pbRes.status !== 200) throw new Error(item.name + " playbook status " + pbRes.status);
    const pbJson = await pbRes.json();
    assertActionUrlSku(item.name + " playbook_url", pbJson.playbook_url, item.exp_sku, item.is_bare_generic);
    const pbHtmlRes = await ctx.onRequestGet({{
      request: new Request(item.playbook_ep + "&format=html&synthetic_test=1"),
      env,
    }});
    if (pbHtmlRes.status !== 200) throw new Error(item.name + " playbook html status " + pbHtmlRes.status);
    const pbHtmlText = await pbHtmlRes.text();
    assertOfferHtmlAndDeliverables(item.name + " playbook json html_report", pbJson.html_report, pbJson, item.exp_sku, item.exp_price, item.exp_title, item.exp_authority, item.exp_deliverables, stalePrices, itemForbiddenTokens);
    assertOfferHtmlAndDeliverables(item.name + " playbook format=html", pbHtmlText, null, item.exp_sku, item.exp_price, item.exp_title, item.exp_authority, item.exp_deliverables, stalePrices, itemForbiddenTokens);

    // 3) Email fulfillment_endpoint -> Edge onRequestGet (?fulfill=1)
    const ffRes = await ctx.onRequestGet({{
      request: new Request(item.fulfill_ep + "&session_id=cs_live_PAIDFOR_" + item.lead_id + "&format=json&synthetic_test=1"),
      env,
    }});
    if (ffRes.status !== 200) throw new Error(item.name + " fulfill status " + ffRes.status);
    const ffJson = await ffRes.json();
    assertOfferMetadata(item.name + " fulfill json", ffJson, item.exp_sku, item.exp_price, item.exp_title, item.exp_authority, item.exp_deliverables);
    for (const stalePrice of stalePrices) {{
      if (String(ffJson.html_report || "").includes(stalePrice)) {{
        throw new Error(item.name + " fulfill html_report leaked " + stalePrice);
      }}
    }}
    for (const deliv of item.exp_deliverables) {{
      if (!String(ffJson.html_report || "").includes(deliv)) {{
        throw new Error(item.name + " fulfill html_report missing deliverable " + deliv);
      }}
    }}
    if (item.exp_authority && !String(ffJson.html_report || "").includes(item.exp_authority)) {{
      throw new Error(item.name + " fulfill html_report missing statutory_authority " + item.exp_authority);
    }}

    // 4) Seed LEADS_KV and verify lead_id-ONLY (no sku=, no tool_slug=) playbook/fulfill/checkout lookups
    await mockKv.put(item.lead_id, JSON.stringify({{
      ...item.rec,
      captured_at: new Date().toISOString(),
    }}));
    ctx.__PSEOFACTORY_LEADS_BUFFER__ = [];
    const domain = item.property_id + ".com";

    const kvPbRes = await ctx.onRequestGet({{
      request: new Request(`https://${{domain}}/api/lead-capture?playbook=1&lead_id=${{encodeURIComponent(item.lead_id)}}&format=json&synthetic_test=1`),
      env,
    }});
    if (kvPbRes.status !== 200) throw new Error(item.name + " KV playbook status " + kvPbRes.status);
    const kvPbJson = await kvPbRes.json();
    assertActionUrlSku(item.name + " KV playbook_url", kvPbJson.playbook_url, item.exp_sku, item.is_bare_generic);
    const kvPbHtmlRes = await ctx.onRequestGet({{
      request: new Request(`https://${{domain}}/api/lead-capture?playbook=1&lead_id=${{encodeURIComponent(item.lead_id)}}&format=html&synthetic_test=1`),
      env,
    }});
    if (kvPbHtmlRes.status !== 200) throw new Error(item.name + " KV playbook html status " + kvPbHtmlRes.status);
    const kvPbHtmlText = await kvPbHtmlRes.text();
    assertOfferHtmlAndDeliverables(item.name + " KV playbook json html_report", kvPbJson.html_report, kvPbJson, item.exp_sku, item.exp_price, item.exp_title, item.exp_authority, item.exp_deliverables, stalePrices, itemForbiddenTokens);
    assertOfferHtmlAndDeliverables(item.name + " KV playbook format=html", kvPbHtmlText, null, item.exp_sku, item.exp_price, item.exp_title, item.exp_authority, item.exp_deliverables, stalePrices, itemForbiddenTokens);

    const kvFfRes = await ctx.onRequestGet({{
      request: new Request(`https://${{domain}}/api/lead-capture?fulfill=1&lead_id=${{encodeURIComponent(item.lead_id)}}&session_id=cs_live_PAIDFOR_${{encodeURIComponent(item.lead_id)}}&format=json&synthetic_test=1`),
      env,
    }});
    if (kvFfRes.status !== 200) throw new Error(item.name + " KV fulfill status " + kvFfRes.status);
    const kvFfJson = await kvFfRes.json();
    assertOfferMetadata(item.name + " KV fulfill json", kvFfJson, item.exp_sku, item.exp_price, item.exp_title, item.exp_authority, item.exp_deliverables);

    stripeBodies = [];
    const kvChkRes = await ctx.onRequestGet({{
      request: new Request(`https://${{domain}}/api/lead-capture?checkout=1&lead_id=${{encodeURIComponent(item.lead_id)}}&format=json`),
      env,
    }});
    if (kvChkRes.status !== 200) throw new Error(item.name + " KV checkout status " + kvChkRes.status);
    const kvChkJson = await kvChkRes.json();
    const kvSp = new URLSearchParams(stripeBodies[0] || "");
    if (kvSp.get("line_items[0][price_data][unit_amount]") !== item.exp_cents) {{
      throw new Error(item.name + " KV checkout cents mismatch: " + kvSp.get("line_items[0][price_data][unit_amount]"));
    }}
    assertOfferMetadata(item.name + " KV checkout json", kvChkJson, item.exp_sku, item.exp_price, item.exp_title, item.exp_authority, item.exp_deliverables);
    assertActionUrlSku(item.name + " KV checkout playbook_url", kvChkJson.playbook_url, item.exp_sku, item.is_bare_generic);
  }}

  // 5) Fallback bundle=null resolveEdgeStripeCheckoutOffer checks across all 4 tenants
  const ghFb19 = await ctxByTenant.gainhelm.ctx.resolveEdgeStripeCheckoutOffer(
    {{}}, "lead_fb_gh19", "ciso@client-real.io", "dora-ict-third-party-risk-compliance-cost-calculator",
    {{ sku: "gh_instant_compliance_worksheet_19", title: "GH 19", price_usd: 19, price_cents: 1900, currency: "usd", statutory_authority: "DORA", deliverables: [] }},
    true, null, "dora_eu_ict_resilience", "gh_instant_compliance_worksheet_19"
  );
  assertActionUrlSku("gh bundle=null 19", ghFb19.playbook_url, "gh_instant_compliance_worksheet_19", false);

  const ghFbBare = await ctxByTenant.gainhelm.ctx.resolveEdgeStripeCheckoutOffer(
    {{}}, "lead_fb_ghbare", "ciso@client-real.io", "general",
    {{ sku: "gh_soc2_cmmc_audit_workpapers", title: "GH 79", price_usd: 79, price_cents: 7900, currency: "usd", statutory_authority: "SOC 2", deliverables: [] }},
    true, null, "", ""
  );
  assertActionUrlSku("gh bundle=null bare", ghFbBare.playbook_url, "gh_soc2_cmmc_audit_workpapers", true);

  const phFb19 = await ctxByTenant.profithelm.ctx.resolveEdgeStripeCheckoutOffer(
    {{}}, "lead_fb_ph19", "cfo@client-real.io", "section-1031-calculator",
    {{ offerSku: "ph_instant_statutory_worksheet_19", offerTitle: "PH 19", offerPriceUsd: 19, offerPriceCents: 1900, statutoryAuthority: "IRC 1031", deliverables: [] }},
    true, null
  );
  assertActionUrlSku("ph bundle=null 19", phFb19.playbook_url, "ph_instant_statutory_worksheet_19", false);

  const pxFb19 = await ctxByTenant.prexvo.ctx.resolveEdgeStripeCheckoutOffer(
    {{}}, "lead_fb_px19", "borrower@client-real.io", "student-loan-refinance-break-even-calculator",
    true, null, "px_instant_repayment_worksheet_19"
  );
  assertActionUrlSku("px bundle=null 19", pxFb19.playbook_url, "px_instant_repayment_worksheet_19", false);

  const lbFb19 = await ctxByTenant.lienbond.ctx.resolveEdgeStripeCheckoutOffer(
    {{}}, "lead_fb_lb19", "contractor@client-real.io", "contractor-license-bond-cost-calculator-by-credit-score",
    {{ sku: "lb_instant_lien_bond_worksheet_19", title: "LB 19", price_usd: 19, price_cents: 1900, currency: "usd", statutory_authority: "Miller Act", deliverables: [] }},
    true, null
  );
  assertActionUrlSku("lb bundle=null 19", lbFb19.playbook_url, "lb_instant_lien_bond_worksheet_19", false);

  // 6) Direct Python resolve_lead_monetization_offer parity across all 15 GainHelm frameworks (sku=""),
  //    bare general / dora + gh_soc2_cmmc_audit_workpapers, $299 partner slots (gh/ph/px), and $19/$39 SKUs
  //    across JSON + format=html + POST -> 402 -> lead_id-only GET
  for (const extraCase of extraOfferParityCases) {{
    const {{ ctx, mockKv }} = ctxByTenant[extraCase.property_id];
    const extraEnv = {{ STRIPE_SECRET_KEY: "sk_live_mock", LEADS_KV: mockKv }};
    const domain = extraCase.property_id + ".com";
    const jsonRes = await ctx.onRequestGet({{
      request: new Request(extraCase.playbook_ep + "&format=json&synthetic_test=1"),
      env: extraEnv,
    }});
    if (jsonRes.status !== 200) throw new Error(extraCase.name + " json status " + jsonRes.status);
    const jsonPayload = await jsonRes.json();
    const htmlRes = await ctx.onRequestGet({{
      request: new Request(extraCase.playbook_ep + "&format=html&synthetic_test=1"),
      env: extraEnv,
    }});
    if (htmlRes.status !== 200) throw new Error(extraCase.name + " html status " + htmlRes.status);
    const htmlPayload = await htmlRes.text();
    assertOfferHtmlAndDeliverables(
      extraCase.name + " json",
      jsonPayload.html_report,
      jsonPayload,
      extraCase.exp_sku,
      extraCase.exp_price,
      extraCase.exp_title,
      extraCase.exp_authority,
      extraCase.exp_deliverables,
      extraCase.forbidden_prices,
      extraCase.forbidden_tokens
    );
    assertOfferHtmlAndDeliverables(
      extraCase.name + " format=html",
      htmlPayload,
      null,
      extraCase.exp_sku,
      extraCase.exp_price,
      extraCase.exp_title,
      extraCase.exp_authority,
      extraCase.exp_deliverables,
      extraCase.forbidden_prices,
      extraCase.forbidden_tokens
    );

    const chkExtraRes = await ctx.onRequestGet({{
      request: new Request(extraCase.checkout_ep + "&format=json"),
      env: extraEnv,
    }});
    if (chkExtraRes.status !== 200) throw new Error(extraCase.name + " checkout status " + chkExtraRes.status);
    const chkExtraJson = await chkExtraRes.json();
    assertOfferMetadata(
      extraCase.name + " checkout json",
      chkExtraJson,
      extraCase.exp_sku,
      extraCase.exp_price,
      extraCase.exp_title,
      extraCase.exp_authority,
      extraCase.exp_deliverables
    );

    // POST -> 402 -> lead_id-only GET roundtrip
    ctx.__PSEOFACTORY_LEADS_BUFFER__ = [];
    const extraIdx = extraOfferParityCases.indexOf(extraCase) + 1;
    const isSlotCase = extraCase.exp_sku.endsWith("_verified_partner_slot");
    const postPayload = isSlotCase
      ? {{
          intent: "partner_registration",
          email: `partner+${{extraCase.name}}@enterprise-real.io`,
          firm_name: "Advisory Partners LLC",
          tool_slug: extraCase.tool_slug,
          state: "DE",
        }}
      : {{
          email: `buyer+${{extraCase.name}}@enterprise-real.io`,
          tool_slug: extraCase.tool_slug,
          ...(extraCase.vertical ? {{ vertical: extraCase.vertical }} : {{}}),
          ...(extraCase.req_sku ? {{ sku: extraCase.req_sku }} : {{}}),
          state: "DE",
          calculated_amount: 95000,
          partner_sharing_consent: true,
        }};
    const postRes = await ctx.onRequestPost({{
      request: new Request(`https://${{domain}}/api/lead-capture`, {{
        method: "POST",
        headers: {{
          "Content-Type": "application/json",
          "CF-Connecting-IP": `198.51.100.${{extraIdx}}`,
        }},
        body: JSON.stringify(postPayload),
      }}),
      env: extraEnv,
    }});
    if (postRes.status !== 200) throw new Error(extraCase.name + " POST status " + postRes.status);
    const postJson = await postRes.json();
    if (postJson.offer_sku !== extraCase.exp_sku || Number(postJson.offer_price_usd) !== Number(extraCase.exp_price)) {{
      throw new Error(extraCase.name + " POST sku/price mismatch: " + JSON.stringify(postJson));
    }}
    if (!isSlotCase) {{
      assertOfferMetadata(
        extraCase.name + " POST json",
        postJson,
        extraCase.exp_sku,
        extraCase.exp_price,
        extraCase.exp_title,
        extraCase.exp_authority,
        extraCase.exp_deliverables
      );
    }}
    const postLid = postJson.lead_id;
    if (!postLid) throw new Error(extraCase.name + " missing postJson.lead_id");
    expectedCentsByLeadId[postLid] = Number(extraCase.exp_cents);

    ctx.__PSEOFACTORY_LEADS_BUFFER__ = [];
    const gate402Res = await ctx.onRequestGet({{
      request: new Request(`https://${{domain}}/api/lead-capture?fulfill=1&lead_id=${{encodeURIComponent(postLid)}}`),
      env: extraEnv,
    }});
    if (gate402Res.status !== 402) throw new Error(extraCase.name + " expected 402 got " + gate402Res.status);
    const gate402Json = await gate402Res.json();
    if (gate402Json.status !== "payment_required" || gate402Json.settled !== false) {{
      throw new Error(extraCase.name + " bad 402 payload: " + JSON.stringify(gate402Json));
    }}

    const lidPbJsonRes = await ctx.onRequestGet({{
      request: new Request(`https://${{domain}}/api/lead-capture?playbook=1&lead_id=${{encodeURIComponent(postLid)}}&format=json&synthetic_test=1`),
      env: extraEnv,
    }});
    if (lidPbJsonRes.status !== 200) throw new Error(extraCase.name + " lead_id playbook json status " + lidPbJsonRes.status);
    const lidPbJson = await lidPbJsonRes.json();
    const lidPbHtmlRes = await ctx.onRequestGet({{
      request: new Request(`https://${{domain}}/api/lead-capture?playbook=1&lead_id=${{encodeURIComponent(postLid)}}&format=html&synthetic_test=1`),
      env: extraEnv,
    }});
    if (lidPbHtmlRes.status !== 200) throw new Error(extraCase.name + " lead_id playbook html status " + lidPbHtmlRes.status);
    const lidPbHtml = await lidPbHtmlRes.text();
    assertOfferHtmlAndDeliverables(
      extraCase.name + " lead_id playbook json",
      lidPbJson.html_report,
      lidPbJson,
      extraCase.exp_sku,
      extraCase.exp_price,
      extraCase.exp_title,
      extraCase.exp_authority,
      extraCase.exp_deliverables,
      extraCase.forbidden_prices,
      extraCase.forbidden_tokens
    );
    assertOfferHtmlAndDeliverables(
      extraCase.name + " lead_id playbook format=html",
      lidPbHtml,
      null,
      extraCase.exp_sku,
      extraCase.exp_price,
      extraCase.exp_title,
      extraCase.exp_authority,
      extraCase.exp_deliverables,
      extraCase.forbidden_prices,
      extraCase.forbidden_tokens
    );

    stripeBodies = [];
    const lidChkRes = await ctx.onRequestGet({{
      request: new Request(`https://${{domain}}/api/lead-capture?checkout=1&lead_id=${{encodeURIComponent(postLid)}}&format=json`),
      env: extraEnv,
    }});
    if (lidChkRes.status !== 200) throw new Error(extraCase.name + " lead_id checkout status " + lidChkRes.status);
    const lidChkJson = await lidChkRes.json();
    assertOfferMetadata(
      extraCase.name + " lead_id checkout json",
      lidChkJson,
      extraCase.exp_sku,
      extraCase.exp_price,
      extraCase.exp_title,
      extraCase.exp_authority,
      extraCase.exp_deliverables
    );
    const lidChkPath = new URL(lidChkJson.success_url).pathname;
    if (lidChkPath !== extraCase.exp_path) {{
      throw new Error(extraCase.name + " lead_id checkout success_url path mismatch: " + lidChkPath + " !== " + extraCase.exp_path);
    }}
    const lidSp = new URLSearchParams(stripeBodies[0] || "");
    if (lidSp.get("line_items[0][price_data][unit_amount]") !== extraCase.exp_cents || lidSp.get("metadata[sku]") !== extraCase.exp_sku) {{
      throw new Error(extraCase.name + " lead_id Stripe params mismatch: " + (stripeBodies[0] || ""));
    }}

    const lidFfRes = await ctx.onRequestGet({{
      request: new Request(`https://${{domain}}/api/lead-capture?fulfill=1&lead_id=${{encodeURIComponent(postLid)}}&session_id=cs_live_PAIDFOR_${{encodeURIComponent(postLid)}}&format=json&synthetic_test=1`),
      env: extraEnv,
    }});
    if (lidFfRes.status !== 200) throw new Error(extraCase.name + " lead_id fulfill status " + lidFfRes.status);
    const lidFfJson = await lidFfRes.json();
    assertOfferHtmlAndDeliverables(
      extraCase.name + " lead_id fulfill json",
      lidFfJson.html_report,
      lidFfJson,
      extraCase.exp_sku,
      extraCase.exp_price,
      extraCase.exp_title,
      extraCase.exp_authority,
      extraCase.exp_deliverables,
      extraCase.forbidden_prices,
      extraCase.forbidden_tokens,
      false
    );
  }}

  console.log("EMAIL_AND_KV_ROUNDTRIP_ALL_TENANTS_OK");
}})().catch((e) => {{ console.error(e); process.exit(1); }});
""",
        encoding="utf-8",
    )
    proc = subprocess.run(["node", str(vm_script)], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    assert "EMAIL_AND_KV_ROUNDTRIP_ALL_TENANTS_OK" in proc.stdout

    # settle_post_calculation_datapack_upgrade: stored bare generic lead preserves '/' and $19 record stays $19
    dp_ledger = tmp_path / "dp_leads.jsonl"
    bare_stored = ingest_qualified_lead(
        property_id="gainhelm",
        tool_slug="general",
        email="buyer@enterprise-real.io",
        state="DE",
        capital_band="50k_to_250k",
        calculated_amount=65000.0,
        partner_sharing_consent=True,
        leads_ledger_path=dp_ledger,
    )
    assert bare_stored["has_explicit_vertical"] is False
    bare_dp = settle_post_calculation_datapack_upgrade(
        property_id="gainhelm",
        tool_slug="general",
        lead_id=bare_stored["lead_id"],
        customer_email="buyer@enterprise-real.io",
        leads_ledger_path=dp_ledger,
        execute_live_checkout=False,
    )
    assert urlparse(bare_dp["checkout_session"]["request_payload"]["success_url"]).path == "/"
    assert "sku=" not in bare_dp["checkout_session"]["checkout_url"]
    assert "vertical=" not in bare_dp["checkout_session"]["checkout_url"]

    dp_19 = settle_post_calculation_datapack_upgrade(
        property_id="gainhelm",
        tool_slug="dora-ict-third-party-risk-compliance-cost-calculator",
        lead_id="lead_gh_dp_19",
        sku="gh_instant_compliance_worksheet_19",
        customer_email="buyer@enterprise-real.io",
        leads_ledger_path=dp_ledger,
        execute_live_checkout=False,
    )
    assert dp_19["offer_sku"] == "gh_instant_compliance_worksheet_19"
    assert dp_19["offer_price_usd"] == 19.0

    # sync_edge_leads_to_ledger: queued_central_responder records propagate sku= & explicit_vertical into ledger + emails
    # Non-blocking #2: LEADS_KV.list() metadata checkout_url ("1" / "") must never clobber computed offer["checkout_url"]
    edge_feeds = {
        "https://gainhelm.com/api/lead-capture": [
            {
                "lead_id": "lead_edge_gh_bare",
                "property_id": "gainhelm",
                "tool_slug": "",
                "vertical": "soc2_grc_automation",
                "has_explicit_vertical": False,
                "has_explicit_sku": False,
                "offer_sku": "gh_soc2_cmmc_audit_workpapers",
                "checkout_url": "",
                "email": "ops@realbuyer.io",
                "calculated_amount": 65000.0,
                "zeptomail_status": "queued_central_responder",
            },
            {
                "lead_id": "lead_edge_gh_dora_19",
                "property_id": "gainhelm",
                "tool_slug": "dora-ict-third-party-risk-compliance-cost-calculator",
                "vertical": "dora_eu_ict_resilience",
                "has_explicit_vertical": True,
                "has_explicit_sku": True,
                "offer_sku": "gh_instant_compliance_worksheet_19",
                "checkout_url": "1",
                "email": "dora@realbuyer.io",
                "calculated_amount": 90000.0,
                "zeptomail_status": "queued_central_responder",
            },
            {
                "lead_id": "lead_edge_gh_soc2_49",
                "property_id": "gainhelm",
                "tool_slug": "soc-2-audit-cost-calculator",
                "vertical": "soc2_grc_automation",
                "has_explicit_sku": True,
                "offer_sku": "gh_hipaa_iso27001_governance_kit",
                "checkout_url": "1",
                "email": "soc2@realbuyer.io",
                "calculated_amount": 72000.0,
                "zeptomail_status": "queued_central_responder",
            },
        ],
        "https://profithelm.com/api/lead-capture": [
            {
                "lead_id": "lead_edge_ph_19",
                "property_id": "profithelm",
                "tool_slug": "section-1031-calculator",
                "offer_sku": "ph_instant_statutory_worksheet_19",
                "checkout_url": "",
                "email": "tax@realbuyer.io",
                "calculated_amount": 350000.0,
                "zeptomail_status": "queued_central_responder",
            }
        ],
    }
    dispatched_zepto = []

    class _MockResp:
        def __init__(self, status: int, payload: bytes):
            self.status = status
            self._payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return self._payload

    def _mock_urlopen(req, timeout=12):
        url_s = req.full_url if hasattr(req, "full_url") else str(req)
        if "api.zeptomail.com" in url_s:
            dispatched_zepto.append(json.loads(req.data.decode("utf-8")))
            return _MockResp(200, json.dumps({"data": [{"message_id": f"zm_{len(dispatched_zepto)}"}], "request_id": "req_sync"}).encode("utf-8"))
        for feed_url, rows in edge_feeds.items():
            if url_s == feed_url:
                return _MockResp(200, json.dumps({"leads": rows}).encode("utf-8"))
        raise AssertionError(f"Unexpected urlopen URL: {url_s}")

    monkeypatch.setenv("ZEPTOMAIL_TOKEN", "Zoho-enczapikey mock_sync_tok")
    monkeypatch.setattr("urllib.request.urlopen", _mock_urlopen)

    sync_ledger = tmp_path / "synced_leads.jsonl"
    sync_res = sync_edge_leads_to_ledger(
        leads_ledger_path=sync_ledger,
        edge_urls={
            "gainhelm": "https://gainhelm.com/api/lead-capture",
            "profithelm": "https://profithelm.com/api/lead-capture",
        },
        auto_fulfill_unfulfilled=True,
        write_back_kv=False,
    )
    assert sync_res["newly_synced_count"] == 4
    assert sync_res["fulfilled_count"] == 4

    synced_by_id = {
        rec["lead_id"]: rec
        for rec in (json.loads(ln) for ln in sync_ledger.read_text(encoding="utf-8").splitlines() if ln.strip())
    }
    for lid_chk, rec_chk in synced_by_id.items():
        assert rec_chk["checkout_url"] not in ("", "1"), (lid_chk, rec_chk["checkout_url"])
        assert rec_chk["checkout_url"].startswith("/api/lead-capture?checkout=1"), (lid_chk, rec_chk["checkout_url"])
    assert "sku=" not in synced_by_id["lead_edge_gh_bare"]["checkout_url"]
    assert "vertical=" not in synced_by_id["lead_edge_gh_bare"]["checkout_url"]
    assert synced_by_id["lead_edge_gh_dora_19"]["offer_price_usd"] == 19.0
    assert "sku=gh_instant_compliance_worksheet_19" in synced_by_id["lead_edge_gh_dora_19"]["checkout_url"]
    assert synced_by_id["lead_edge_gh_soc2_49"]["offer_price_usd"] == 49.0
    assert "sku=gh_hipaa_iso27001_governance_kit" in synced_by_id["lead_edge_gh_soc2_49"]["checkout_url"]
    assert synced_by_id["lead_edge_ph_19"]["offer_price_usd"] == 19.0
    assert "sku=ph_instant_statutory_worksheet_19" in synced_by_id["lead_edge_ph_19"]["checkout_url"]

    zepto_by_to = {p["to"][0]["email_address"]["address"]: p for p in dispatched_zepto}
    assert "/tools/soc-2-audit-cost-calculator/" not in zepto_by_to["ops@realbuyer.io"]["htmlbody"]
    assert "sku=" not in zepto_by_to["ops@realbuyer.io"]["htmlbody"]
    assert "sku=gh_instant_compliance_worksheet_19" in zepto_by_to["dora@realbuyer.io"]["htmlbody"]
    assert "playbook=1" in zepto_by_to["dora@realbuyer.io"]["htmlbody"]
    assert "($19)" in zepto_by_to["dora@realbuyer.io"]["htmlbody"]
    assert "sku=gh_hipaa_iso27001_governance_kit" in zepto_by_to["soc2@realbuyer.io"]["htmlbody"]
    assert "($49)" in zepto_by_to["soc2@realbuyer.io"]["htmlbody"]
    assert "sku=ph_instant_statutory_worksheet_19" in zepto_by_to["tax@realbuyer.io"]["htmlbody"]
    assert "($19)" in zepto_by_to["tax@realbuyer.io"]["htmlbody"]


