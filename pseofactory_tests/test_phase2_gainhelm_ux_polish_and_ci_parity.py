from __future__ import annotations
import pytest

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from pseofactory import compiler as compiler_mod
from pseofactory.affiliates import (
    GAINHELM_AFFILIATES,
    has_gainhelm_cross_framework_leak,
    resolve_contextual_partner_offer_copy,
)
from pseofactory.competitor import (
    render_partner_quote_intake_html,
    render_serp_incumbent_depth_upgrade_block,
)
from pseofactory.edge import generate_edge_lead_capture_function
from pseofactory.gainhelm_estate import _build_partners_matrix_section
from pseofactory.gitops import sync_tenant_test_isolation_guards
from pseofactory.audit import ContentAccuracyAuditStage
from pseofactory.maintenance import RetroReflectionEngine
from pseofactory.partner_tracker import (
    resolve_post_calculation_upgrade_spec,
    synthesize_personalized_audit_workpaper,
)
from pseofactory.porcelain_shell import (
    _extract_defined_css_classes_for_audit,
    _find_undefined_ui_classes_in_html,
    build_governance_pages,
    get_porcelain_tenant_profile,
    sync_tenant_porcelain_shell,
)


def _strip_header_and_footer(html_text: str) -> str:
    no_ftr = re.sub(r"<footer\b[\s\S]*?</footer>", "", html_text, flags=re.IGNORECASE)
    return re.sub(r"<header\b[\s\S]*?</header>", "", no_ftr, flags=re.IGNORECASE)


def test_gainhelm_and_tenant_governance_copy_and_visible_dates(tmp_path: Path) -> None:
    res = compiler_mod.compile_gainhelm_estate(tmp_path, run_retrofit=True)
    assert res["status"] == "PASS", res
    dist = tmp_path / "dist"

    css_text = (dist / "css" / "style.css").read_text(encoding="utf-8")
    defined_css = _extract_defined_css_classes_for_audit(css_text)
    assert "verified-date-meta" in defined_css

    privacy_html = (dist / "privacy" / "index.html").read_text(encoding="utf-8")
    assert "audit scopes, employee headcount, control counts, or compliance budgets" in privacy_html
    for forbidden in ("income", "loan balances", "irs", "raw financial"):
        assert forbidden not in privacy_html.lower()

    contact_html = (dist / "contact" / "index.html").read_text(encoding="utf-8")
    assert (
        "primary regulatory rule, NIST publication, ISO/IEC annex, AICPA section, or statutory breach provision referenced"
        in contact_html
    )
    assert "IRS Revenue Procedure" not in contact_html

    for route in ("methodology", "disclaimers"):
        page_html = (dist / route / "index.html").read_text(encoding="utf-8")
        assert "Last verified against primary statutes and accreditation tables: 2026-10-31" in page_html
        assert '"dateModified": "2026-10-31"' in page_html or '"dateModified":"2026-10-31"' in page_html
        assert not _find_undefined_ui_classes_in_html(page_html, defined_css)

    for prop, exp_priv, exp_rev in (
        ("lienbond", "contract values, payroll exposures, bond penalties, or project schedules", "Miller Act rule"),
        ("prexvo", "income, loan balances, household size, or repayment parameters", "Higher Education Act section"),
        ("profithelm", "income, loan balances, contract amounts, or control counts", "IRS Revenue Procedure"),
    ):
        pages = build_governance_pages(get_porcelain_tenant_profile(prop))
        assert exp_priv in pages["privacy"]
        assert exp_rev in pages["contact"]
        for route in ("methodology", "disclaimers"):
            assert "Last verified against primary statutes and accreditation tables: 2026-11-12" in pages[route]
            assert '"dateModified": "2026-11-12"' in pages[route]


def test_gainhelm_core_tools_ux_polish_partner_cards_serp_and_overlay_pruning(tmp_path: Path) -> None:
    ov_dir = tmp_path / ".agy" / "overlays"
    ov_dir.mkdir(parents=True, exist_ok=True)
    poisoned_hipaa = ov_dir / "hipaa-violation-penalty-breach-cost-calculator.json"
    poisoned_hipaa.write_text(
        json.dumps(
            {
                "slug": "hipaa-violation-penalty-breach-cost-calculator",
                "quick_answer": "Under 32 CFR Part 170 CMMC C3PAO rules, audit fees cost $132,000.",
                "h2_headings": ["C3PAO Readiness Schedule"],
            }
        ),
        encoding="utf-8",
    )

    res = compiler_mod.compile_gainhelm_estate(tmp_path, run_retrofit=True)
    assert res["status"] == "PASS", res
    dist = tmp_path / "dist"
    assert not poisoned_hipaa.exists()
    assert RetroReflectionEngine.audit_estate(dist, "gainhelm")["status"] == "PASS"

    stale_ux_tokens = (
        "DE Baseline",
        "Instant DE Partner Quote",
        "Export Personalized DE Schedule",
        "Statutory Bracket",
        "Effective vs. Marginal",
    )
    tool_pages = sorted(dist.glob("tools/*/index.html"))
    assert len(tool_pages) == 10
    for html_path in tool_pages:
        slug = html_path.parent.name
        html = html_path.read_text(encoding="utf-8")
        body_no_chrome = _strip_header_and_footer(html)
        assert not has_gainhelm_cross_framework_leak(body_no_chrome, slug=slug), f"Leak in {slug}"
        assert ContentAccuracyAuditStage.audit_rendered_asset(html, property_id="gainhelm", strict=True) == []
        for tok in stale_ux_tokens:
            assert tok not in html, f"Found {tok!r} in {slug}"
        if slug != "soc-2-audit-cost-calculator":
            assert "Enterprise SOC 2 Type II, DoD CMMC 2.0" not in html, f"Generic widget title on {slug}"
            assert "CMMC + HITRUST" not in html, f"Generic workbench fallback preset on {slug}"

    iso_html = (dist / "tools" / "iso-27001-certification-cost-calculator" / "index.html").read_text(encoding="utf-8")
    assert 'id="workpaper-unlock-card"' in iso_html
    assert 'data-offer-sku="gh_hipaa_iso27001_governance_kit"' in iso_html
    assert 'data-offer-price="29"' in iso_html

    for intl_slug in (
        "dora-ict-third-party-risk-compliance-cost-calculator",
        "eu-ai-act-high-risk-conformity-assessment-cost-calculator",
        "nis2-directive-compliance-cost-calculator",
        "gdpr-article-83-fine-exposure-calculator",
    ):
        assert render_partner_quote_intake_html(intl_slug, property_id="gainhelm") == ""
        intl_wp = synthesize_personalized_audit_workpaper("gainhelm", intl_slug, mode="free_playbook")
        assert intl_wp["state"] == "EU"
        assert intl_wp["statutory_data_pack"]["framework_jurisdiction"] == "EU"

    dora_cards = _build_partners_matrix_section("dora-ict-third-party-risk-compliance-cost-calculator")
    euai_cards = _build_partners_matrix_section("eu-ai-act-high-risk-conformity-assessment-cost-calculator")
    assert "ISO 27001" not in dora_cards and "ISO Controls" not in dora_cards
    assert "ISO 27001" not in euai_cards
    for pk in ("sprinto_compliance", "thoropass_audit"):
        dora_copy = resolve_contextual_partner_offer_copy(
            pk,
            GAINHELM_AFFILIATES[pk],
            slug="dora-ict-third-party-risk-compliance-cost-calculator",
            property_id="gainhelm",
        )
        assert "ISO 27001" not in str(dora_copy) and "ISO Controls" not in str(dora_copy)
    euai_copy = resolve_contextual_partner_offer_copy(
        "sprinto_compliance",
        GAINHELM_AFFILIATES["sprinto_compliance"],
        slug="eu-ai-act-high-risk-conformity-assessment-cost-calculator",
        property_id="gainhelm",
    )
    assert "ISO 27001" not in str(euai_copy)

    for non_soc2_slug in (
        "iso-27001-certification-cost-calculator",
        "hipaa-violation-penalty-breach-cost-calculator",
        "pci-dss-4-0-compliance-cost-calculator",
        "hitrust-csf-e1-i1-r2-certification-cost-calculator",
        "penetration-testing-scoping-cost-calculator",
        "cyber-liability-insurance-breach-exposure-calculator",
        "cmmc-2-0-compliance-cost-calculator",
        "nist-800-171-sprs-score-calculator",
    ):
        wb = render_serp_incumbent_depth_upgrade_block(
            slug=non_soc2_slug,
            title=non_soc2_slug,
            property_id="gainhelm",
            canonical_base="https://gainhelm.com",
            statutory_authority="Statutory Standard",
            economic_dataset="BLS OEWS SOC 15-1212",
        )
        assert "CMMC + HITRUST" not in wb
        assert not has_gainhelm_cross_framework_leak(wb, slug=non_soc2_slug)


@pytest.mark.host_estate
def test_gainhelm_datapack_edge_metadata_and_ci_temp_build_parity(tmp_path: Path) -> None:
    dora_slug = "dora-ict-third-party-risk-compliance-cost-calculator"
    spec = resolve_post_calculation_upgrade_spec("gainhelm", dora_slug)
    assert spec is not None
    assert spec["compliance_cycle_year"] == "2026"
    assert spec["framework_jurisdiction"] == "EU"
    assert "effective_tax_year" not in spec

    wp = synthesize_personalized_audit_workpaper("gainhelm", dora_slug, mode="free_playbook")
    dp = wp["statutory_data_pack"]
    assert dp["compliance_cycle_year"] == "2026"
    assert dp["framework_jurisdiction"] == "EU"
    assert wp["state"] == "EU"
    assert "effective_tax_year" not in dp

    ph_spec = resolve_post_calculation_upgrade_spec("profithelm", "section-179-calculator")
    assert ph_spec is not None and ph_spec["effective_tax_year"] == "2026"

    edge_file = tmp_path / "lead-capture.mjs"
    edge_file.write_text(generate_edge_lead_capture_function("gainhelm"), encoding="utf-8")
    syntax_chk = subprocess.run(["node", "--check", str(edge_file)], capture_output=True, text=True, check=False)
    assert syntax_chk.returncode == 0, syntax_chk.stderr

    node_script = f"""
import {{ onRequestGet, onRequestPost }} from {json.dumps(edge_file.as_uri())};
const r1FreeDp = await onRequestGet({{
  request: new Request("https://gainhelm.com/api/lead-capture?playbook=1&format=datapack&tool_slug={dora_slug}"),
  env: {{}}
}});
if (r1FreeDp.status !== 402) throw new Error("expected 402 paywall on free format=datapack, got " + r1FreeDp.status);

const r1 = await onRequestGet({{
  request: new Request("https://gainhelm.com/api/lead-capture?playbook=1&format=json&tool_slug={dora_slug}"),
  env: {{}}
}});
if (r1.status !== 200) throw new Error("expected 200 on playbook json, got " + r1.status);
const d1 = await r1.json();
const dp1 = d1.statutory_data_pack || {{}};
if (dp1.compliance_cycle_year !== "2026" || "effective_tax_year" in d1 || "effective_tax_year" in dp1) throw new Error("cycle mismatch");
if (dp1.framework_jurisdiction !== "EU" || dp1.modeled_scenario_summary.state !== "EU") throw new Error("eu state mismatch");

const r2 = await onRequestGet({{
  request: new Request("https://gainhelm.com/api/lead-capture?playbook=1&format=json&tool_slug=soc-2-audit-cost-calculator&state=WA"),
  env: {{}}
}});
const d2 = await r2.json();
const dp2 = d2.statutory_data_pack || {{}};
if (dp2.modeled_scenario_summary.state !== "WA") throw new Error("explicit override lost");

const r3 = await onRequestPost({{
  request: new Request("https://gainhelm.com/api/lead-capture", {{
    method: "POST",
    headers: {{ "Content-Type": "application/json" }},
    body: JSON.stringify({{
      email: "qa@synthetic.pseofactory.test",
      tool_slug: "{dora_slug}",
      calculated_amount: 112100,
      partner_sharing_consent: true,
      synthetic_test: true
    }})
  }}),
  env: {{}}
}});
const d3 = await r3.json();
if (!d3.ok || d3.state !== "EU") throw new Error("post state mismatch");
console.log("NODE_PARITY_OK");
"""
    node_proc = subprocess.run(["node", "--input-type=module", "-e", node_script], capture_output=True, text=True, check=False)
    assert node_proc.returncode == 0 and "NODE_PARITY_OK" in node_proc.stdout, node_proc.stderr

    gh_mock = tmp_path / "gh_ci_mock"
    (gh_mock / "gainhelm").mkdir(parents=True)
    (gh_mock / "pyproject.toml").write_text('[project]\nname = "gainhelm"\n', encoding="utf-8")
    sync_tenant_test_isolation_guards(gh_mock, "gainhelm")
    ci_yml = (gh_mock / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "python3 -m gainhelm.cli build --dist /tmp/gh_ci_dist" in ci_yml
    assert "python3 -m gainhelm.cli audit --dist /tmp/gh_ci_dist" in ci_yml
    assert "python3 -m gainhelm.cli audit\n" in ci_yml

    live_gh = Path("/home/ubuntuadmin/projects/gainhelm")
    if (live_gh / ".git").is_dir():
        gh_repo = tmp_path / "gh_cli_repo"
        gh_repo.mkdir(parents=True)
        arch = subprocess.run(
            f"git -C {str(live_gh)!r} archive HEAD | tar -x -C {str(gh_repo)!r}",
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )
        assert arch.returncode == 0, arch.stderr
        sync_tenant_porcelain_shell(gh_repo, "gainhelm")
        (gh_repo / "dist").mkdir(parents=True, exist_ok=True)
        sentinel = gh_repo / "dist" / "index.html"
        sentinel.write_text("<html><body>STAGE7_COMMITTED_SENTINEL</body></html>", encoding="utf-8")

        temp_dist = tmp_path / "gh_cli_dist"
        env = {
            "PYTHONPATH": f"{gh_repo}:{gh_repo / 'gainhelm' / '_pseo_substrate'}",
            "PATH": os.environ.get("PATH", ""),
        }
        cli_build = subprocess.run(
            [sys.executable, "-m", "gainhelm.cli", "build", "--dist", str(temp_dist)],
            cwd=str(gh_repo),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert cli_build.returncode == 0, cli_build.stderr
        cli_audit = subprocess.run(
            [sys.executable, "-m", "gainhelm.cli", "audit", "--dist", str(temp_dist)],
            cwd=str(gh_repo),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert cli_audit.returncode == 0, cli_audit.stderr
        assert (temp_dist / "index.html").is_file()
        assert sentinel.read_text(encoding="utf-8") == "<html><body>STAGE7_COMMITTED_SENTINEL</body></html>"


@pytest.mark.host_estate
def test_gainhelm_overlay_pruning_all_fields_and_void_isolation(tmp_path: Path) -> None:
    from pseofactory.estate_common import strip_cross_framework_leaks_from_overlay
    from pseofactory.gsc_remediation import compile_remediation_overlay_spec

    ov_dir = tmp_path / ".agy" / "overlays"
    ov_dir.mkdir(parents=True, exist_ok=True)
    pentest_slug = "penetration-testing-scoping-cost-calculator"
    pentest_ov = ov_dir / f"{pentest_slug}.json"
    base_ov = compile_remediation_overlay_spec(
        {
            "slug": pentest_slug,
            "target_url": f"https://gainhelm.com/tools/{pentest_slug}/",
        },
        tenant_id="gainhelm",
    )
    base_ov.update(
        {
            "slug": pentest_slug,
            "hub_links": [
                {"anchor": "SOC 2 Audit Calculator", "href": "/tools/soc-2-audit-cost-calculator/"},
                {"anchor": "CMMC 2.0 Budget", "href": "/tools/cmmc-2-0-compliance-cost-calculator/"},
                {"anchor": "CREST Pentest Scoping Methodology", "href": "/methodology/"},
            ],
            "ai_repair_prompt": "Rewrite SOC 2 Type II and CMMC C3PAO table rows.",
            "comparison_matrix": [
                {"label": "SOC 2 Type II CPA Bundle", "value": "$37,000"},
                {"label": "CREST/OSCP Manual Assessment", "value": "$14,446"},
            ],
            "scenario_presets": [
                {"label": "CMMC Level 2 Enclave + SOC 2", "headcount": 120},
                {"label": "Growth API + Cloud Pentest", "headcount": 75},
            ],
            "faq": [
                {"q": "Does this include CMMC C3PAO audit fees?", "a": "No, that is for 32 CFR Part 170."},
                {"q": "How long does manual API penetration testing take?", "a": "Typically 2 to 3 weeks."},
            ],
            "partner_offer": {
                "partner_key": "thoropass_audit",
                "partner_name": "Thoropass",
                "title": "Continuous SOC 2 Type II + CMMC Readiness",
                "badge": "CPA/C3PAO Partner",
                "disclosure": "GainHelm earns an editorial referral fee on vetted CPA/C3PAO audit quotes.",
                "description": "Bundled CPA & C3PAO audit workflow across SOC 2 and HIPAA.",
                "cta_text": "Request SOC 2 + CMMC Quote",
                "url": "https://thoropass.com/demo",
                "secondary_offers": [
                    {
                        "partner_key": "drata_grc",
                        "partner_name": "Drata",
                        "badge": "Automated SOC 2, ISO 27001 & HIPAA",
                        "description": "Automate SOC 2, ISO 27001, and HIPAA evidence.",
                        "cta_text": "Get Drata SOC 2 Quote",
                        "url": "https://drata.com",
                    }
                ],
                "ranked_partner_candidates": [
                    {
                        "partner_key": "vanta_compliance",
                        "partner_name": "Vanta",
                        "description": "Continuous NIST, CMMC & SOC 2 Controls",
                    }
                ],
                "partner_roster": [
                    {
                        "partner_key": "cobalt_pentest",
                        "partner_name": "Cobalt",
                        "description": "CREST-certified manual penetration testing and API PTaaS.",
                    }
                ],
            },
            "partner_roster": [
                {
                    "partner_key": "sprinto_compliance",
                    "partner_name": "Sprinto",
                    "description": "Automated SOC 2, ISO 27001 & HIPAA readiness.",
                },
                {
                    "partner_key": "cobalt_pentest",
                    "partner_name": "Cobalt",
                    "description": "PTaaS and manual web/API security testing.",
                },
            ],
            "slot_plan": {
                "reposition_reason": "SOC 2 CPA quote prioritized",
                "slot_bindings": {"primary": "SOC 2 + CMMC CPA bundle"},
                "ordered_offers": ["Thoropass SOC 2 + HIPAA bundle", "Cobalt PTaaS"],
            },
        }
    )
    pentest_ov.write_text(json.dumps(base_ov), encoding="utf-8")

    cleaned_direct = strip_cross_framework_leaks_from_overlay(base_ov, pentest_slug)
    assert isinstance(cleaned_direct["partner_roster"], list)
    assert "SOC 2" not in json.dumps(cleaned_direct["partner_roster"])
    assert cleaned_direct["slot_plan"]["ordered_offers"] == ["Cobalt PTaaS"]

    voids_path = Path("/home/ubuntuadmin/projects/gainhelm/content/deployed_voids.json")
    if voids_path.is_file():
        (tmp_path / "content").mkdir(parents=True, exist_ok=True)
        shutil.copy2(voids_path, tmp_path / "content" / "deployed_voids.json")

    res = compiler_mod.compile_gainhelm_estate(tmp_path, run_retrofit=True)
    assert res["status"] == "PASS", res
    dist = tmp_path / "dist"
    pentest_html = (dist / "tools" / pentest_slug / "index.html").read_text(encoding="utf-8")
    no_chrome = _strip_header_and_footer(pentest_html)
    assert not has_gainhelm_cross_framework_leak(no_chrome, slug=pentest_slug)
    assert "CPA/C3PAO" not in no_chrome
    assert "CREST Pentest Scoping Methodology" in no_chrome

    real_ov_src = Path("/home/ubuntuadmin/projects/gainhelm/.agy/overlays")
    if real_ov_src.is_dir():
        real_ws = tmp_path / "real_overlay_compile"
        (real_ws / ".agy" / "overlays").mkdir(parents=True, exist_ok=True)
        for ov_file in sorted(real_ov_src.glob("*.json")):
            shutil.copy2(ov_file, real_ws / ".agy" / "overlays" / ov_file.name)
        if voids_path.is_file():
            (real_ws / "content").mkdir(parents=True, exist_ok=True)
            shutil.copy2(voids_path, real_ws / "content" / "deployed_voids.json")
        real_res = compiler_mod.compile_gainhelm_estate(real_ws, run_retrofit=True)
        assert real_res["status"] == "PASS", real_res
        for page_path in sorted((real_ws / "dist" / "tools").glob("*/index.html")):
            slug = page_path.parent.name
            body_no_chrome = _strip_header_and_footer(page_path.read_text(encoding="utf-8"))
            assert not has_gainhelm_cross_framework_leak(body_no_chrome, slug=slug), f"Real overlay leak in {slug}"
        assert RetroReflectionEngine.audit_estate(real_ws / "dist", "gainhelm")["status"] == "PASS"


def test_gainhelm_subsidy_meter_framework_parity_and_recompute(tmp_path: Path) -> None:
    res = compiler_mod.compile_gainhelm_estate(tmp_path, run_retrofit=True)
    assert res["status"] == "PASS", res
    tools_dir = tmp_path / "dist" / "tools"

    expected_ssr = {
        "soc-2-audit-cost-calculator": ("soc2", "$37,000.00", "$8,030.22", "$14,600.40"),
        "cmmc-2-0-compliance-cost-calculator": ("cmmc", "$48,500.00", "$15,295.00", "$43,700.00"),
        "nist-800-171-sprs-score-calculator": ("sprs", "$48,500.00", "$15,295.00", "$43,700.00"),
        "iso-27001-certification-cost-calculator": ("iso27001", "$21,450.00", "$11,275.20", "$22,550.40"),
        "hipaa-violation-penalty-breach-cost-calculator": ("hipaa", "$2,067,813.00", "$620,343.90", "$387,500.00"),
        "pci-dss-4-0-compliance-cost-calculator": ("pci_dss", "$42,000.00", "$17,460.00", "$38,800.00"),
        "fedramp-authorization-3pao-cost-calculator": ("fedramp", "$210,000.00", "$125,000.00", "$210,000.00"),
        "hitrust-csf-e1-i1-r2-certification-cost-calculator": ("hitrust", "$57,500.00", "$34,500.00", "$36,800.00"),
        "penetration-testing-scoping-cost-calculator": ("pentest", "$14,446.00", "$6,990.00", "$4,660.00"),
        "cyber-liability-insurance-breach-exposure-calculator": ("cyber_insurance", "$20,415.00", "$4,491.30", "$20,485.00"),
    }
    soc2_literals = ("$37,000.00", "$15,000.00", "$8,030.22", "$14,600.40")
    for slug, (exp_mode, exp_pay, exp_sub, exp_int) in expected_ssr.items():
        html = (tools_dir / slug / "index.html").read_text(encoding="utf-8")
        meter_m = re.search(
            r'<div class="subsidy-meter-wrap">[\s\S]*?<span class="legend-item">[\s\S]*?</div>\s*</div>',
            html,
        )
        assert meter_m is not None, f"Missing .subsidy-meter-wrap on {slug}"
        meter_block = meter_m.group(0)
        assert f'data-meter-mode="{exp_mode}"' in meter_block
        assert f'id="meter-pay-val">{exp_pay}<' in meter_block
        assert f'id="meter-sub-val">{exp_sub}<' in meter_block
        assert f'id="meter-int-val">{exp_int}<' in meter_block
        if slug != "soc-2-audit-cost-calculator":
            for lit in soc2_literals:
                assert lit not in meter_block, f"SOC2 literal {lit} leaked into {slug} meter"

    pentest_html = (tools_dir / "penetration-testing-scoping-cost-calculator" / "index.html").read_text(encoding="utf-8")
    hipaa_html = (tools_dir / "hipaa-violation-penalty-breach-cost-calculator" / "index.html").read_text(encoding="utf-8")
    js_node_check = """
import vm from "node:vm";
function extractScript(html) {
  const m = html.match(/<script>\\s*\\(function\\(\\) \\{\\s*var form = document\\.getElementById\\("gainhelm-compliance-form"\\)[\\s\\S]*?<\\/script>/);
  if (!m) throw new Error("Missing calculator script");
  return m[0].replace(/^<script>/, "").replace(/<\\/script>$/, "");
}
function runCalc(html, hcVal, recVal, modeAttr) {
  const els = new Map();
  const mkEl = (id, value = "") => ({
    id, value, textContent: "", style: {},
    attrs: id === "meter-cpa-val" ? { "data-meter-mode": modeAttr, "data-left-label": "L", "data-right-label": "R" } : {},
    getAttribute(k) { return this.attrs[k] ?? null; },
    addEventListener() {},
  });
  for (const id of [
    "gainhelm-compliance-form", "calc-input-headcount", "calc-input-compromised_records",
    "meter-cpa-val", "meter-pay-val", "meter-sub-val", "meter-int-val",
    "meter-seg-cpa", "meter-seg-grc", "metric-pentest_total_cost", "metric-hipaa_exposure",
  ]) els.set(id, mkEl(id));
  els.get("calc-input-headcount").value = String(hcVal);
  els.get("calc-input-compromised_records").value = String(recVal);
  els.get("gainhelm-compliance-form").querySelectorAll = () => [];
  const doc = {
    getElementById: (id) => els.get(id) ?? null,
    querySelectorAll: () => [],
  };
  vm.runInNewContext(extractScript(html), {
    document: doc,
    window: { location: { search: "" } },
    URLSearchParams,
    Math,
    Number,
    parseFloat,
    isNaN,
    isFinite,
    Date,
  });
  return {
    pay: els.get("meter-pay-val").textContent,
    sub: els.get("meter-sub-val").textContent,
    int: els.get("meter-int-val").textContent,
    cpa: els.get("meter-cpa-val").textContent,
    segCpa: els.get("meter-seg-cpa").style.width,
  };
}
const pen = runCalc(%s, 250, 1500, "pentest");
const hip = runCalc(%s, 75, 100, "hipaa");
if (pen.pay === "$14,446.00" || hip.pay === "$2,067,813.00") {
  throw new Error("Meter JS did not recompute: " + JSON.stringify({ pen, hip }));
}
console.log(JSON.stringify({ pen, hip }));
""" % (json.dumps(pentest_html), json.dumps(hipaa_html))
    js_file = tmp_path / "check_meter.mjs"
    js_file.write_text(js_node_check, encoding="utf-8")
    js_proc = subprocess.run(["node", str(js_file)], capture_output=True, text=True, check=False)
    assert js_proc.returncode == 0, js_proc.stderr


def test_gainhelm_legacy_de_baseline_retrofit_healing_and_idempotency() -> None:
    legacy_html = """<!doctype html><html><head><title>Penetration Testing</title></head><body>
    <main>
      <div class="pro-hook-card" data-state="DE">
        <div class="pro-hook-header"><h3>Pro Control Pack</h3></div>
        <div class="pro-hook-sample-unlock">Unlocked Sample Preview ($48,500 DE Baseline): Line 1 Statutory Bracket &amp; Deduction Schedule (Unlocked) | Line 2 Effective vs. Marginal Sensitivity Matrix (Unlocked) | Line 3 Signed Audit Workpaper (Locked: $49)</div>
        <button>Instant DE Partner Quote ($0)</button>
        <span class="pro-hook-footer">Export Personalized DE Schedule &amp; Data Pack</span>
      </div>
    </main>
    </body></html>"""
    pass1, rep1 = RetroReflectionEngine.retrofit_html(
        legacy_html,
        "gainhelm",
        slug="penetration-testing-scoping-cost-calculator",
    )
    pass2, rep2 = RetroReflectionEngine.retrofit_html(
        pass1,
        "gainhelm",
        slug="penetration-testing-scoping-cost-calculator",
    )
    for stale in (
        "DE Baseline",
        "Instant DE Partner Quote",
        "Export Personalized DE Schedule",
        "Statutory Bracket",
    ):
        assert stale not in pass1, f"Stale copy {stale!r} survived retrofit pass 1"
    assert 'class="pro-hook-card"' not in pass1
    assert "compliant_intent_monetization" in rep1
    assert pass2 == pass1
    assert rep2 == []


@pytest.mark.host_estate
def test_gainhelm_full_page_chromium_script1_and_script2_parity(tmp_path: Path) -> None:
    import functools
    import http.server
    import socketserver
    import threading
    from playwright.sync_api import sync_playwright

    class _QuietStaticHandler(http.server.SimpleHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length:
                self.rfile.read(length)
            self.send_response(204)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            pass

    def _parse_num(txt: str) -> float:
        m = re.search(r"-?\d[\d,]*(?:\.\d+)?", txt or "")
        assert m, f"Cannot parse numeric value from {txt!r}"
        return float(m.group(0).replace(",", ""))

    res = compiler_mod.compile_gainhelm_estate(tmp_path, run_retrofit=True)
    assert res["status"] == "PASS", res
    dist = tmp_path / "dist"

    handler = functools.partial(_QuietStaticHandler, directory=str(dist))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    primary_kpi_map = {
        "soc-2-audit-cost-calculator": "metric-soc2_total_cost",
        "cmmc-2-0-compliance-cost-calculator": "metric-cmmc_total_cost",
        "nist-800-171-sprs-score-calculator": "metric-nist_sprs_score",
        "iso-27001-certification-cost-calculator": "metric-iso27001_total_cost",
        "hipaa-violation-penalty-breach-cost-calculator": "metric-hipaa_exposure",
        "pci-dss-4-0-compliance-cost-calculator": "metric-pci_dss_cost",
        "fedramp-authorization-3pao-cost-calculator": "metric-fedramp_total_cost",
        "hitrust-csf-e1-i1-r2-certification-cost-calculator": "metric-hitrust_total_cost",
        "penetration-testing-scoping-cost-calculator": "metric-pentest_total_cost",
        "cyber-liability-insurance-breach-exposure-calculator": "metric-cyber_insurance_total_cost",
    }

    try:
        chrome_bin = Path("/usr/bin/google-chrome")
        launch_kwargs = {"headless": True}
        if chrome_bin.is_file():
            launch_kwargs["executable_path"] = str(chrome_bin)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(**launch_kwargs)
            for slug, kpi_id in primary_kpi_map.items():
                page = browser.new_page()
                errors = []
                page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
                page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
                page.goto(f"http://127.0.0.1:{port}/tools/{slug}/")
                page.wait_for_load_state("domcontentloaded")

                def _assert_parity(stage: str) -> tuple[str, str, str]:
                    kpi_txt = page.locator(f"#{kpi_id}").inner_text().strip()
                    ov_txt = page.locator(".output-value:not(.overlay-preset-readout)").first.inner_text().strip()
                    sav_txt = page.locator("#metric-soc2_automation_savings").inner_text().strip()
                    sub_txt = page.locator("#meter-sub-val").inner_text().strip()
                    assert sav_txt == f"{sub_txt}/yr", f"[{slug}:{stage}] {sav_txt!r} != {sub_txt!r}/yr"
                    assert abs(_parse_num(ov_txt) - _parse_num(kpi_txt)) < 1e-4, f"[{slug}:{stage}] {ov_txt!r} != {kpi_txt!r}"
                    return kpi_txt, ov_txt, sav_txt

                _assert_parity("init")
                presets = page.locator(".calc-switcher-btn")
                assert presets.count() == 3
                presets.nth(1).click()
                _assert_parity("preset2")
                presets.nth(2).click()
                _assert_parity("preset3")
                presets.nth(0).click()
                _assert_parity("preset1")

                if page.locator("#calc-input-headcount").count() > 0:
                    page.fill("#calc-input-headcount", "400")
                    page.dispatch_event("#calc-input-headcount", "input")
                if slug == "hipaa-violation-penalty-breach-cost-calculator":
                    page.fill("#calc-input-compromised_records", "50")
                    page.dispatch_event("#calc-input-compromised_records", "input")
                if slug == "nist-800-171-sprs-score-calculator":
                    page.fill("#calc-input-unimplemented_5pt", "12")
                    page.dispatch_event("#calc-input-unimplemented_5pt", "input")
                page.click("#calc-submit-btn")
                after_submit = _assert_parity("submit_400")
                if slug == "iso-27001-certification-cost-calculator":
                    assert after_submit[0] == "$114,077.92"
                    assert after_submit[1] == "114,077.92"
                if slug == "nist-800-171-sprs-score-calculator":
                    assert after_submit[0] == "42 pts"
                    assert after_submit[1] == "42"

                qs = "headcount=400"
                if slug == "hipaa-violation-penalty-breach-cost-calculator":
                    qs += "&compromised_records=50"
                if slug == "nist-800-171-sprs-score-calculator":
                    qs += "&unimplemented_5pt=12"
                page.goto(f"http://127.0.0.1:{port}/tools/{slug}/?{qs}")
                page.wait_for_load_state("domcontentloaded")
                assert _assert_parity("url_query") == after_submit
                assert not errors, f"[{slug}] errors: {errors}"
                page.close()
            browser.close()
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_runtime_sync_tenant_neutral_and_head_tenant_inference() -> None:
    from pseofactory import verifier as verifier_mod
    from pseofactory.gsc_remediation import _normalize_meta_120_155
    from pseofactory.porcelain_shell import _ensure_prexvo_ymyl_forfeiture_notice
    from pseofactory.verifier import verify_html_cross_web_consensus_and_corroboration
    from pseofactory.visual_primitives import render_runtime_synchronizer_script

    legacy_sync_hook = "__" + "gainhelm" + "SyncWorkspaceOutputs"
    runtime_js = render_runtime_synchronizer_script()
    runtime_low = runtime_js.lower()
    assert "__complianceSyncWorkspaceOutputs" in runtime_js
    assert legacy_sync_hook not in runtime_js
    for tenant_tok in ("gainhelm", "prexvo", "profithelm", "lienbond"):
        assert tenant_tok not in runtime_low, f"Shared runtime script leaked tenant token {tenant_tok!r}"

    # Canonical URL, og:url, title, JSON-LD @id/url, and script-stripped body fallback must beat embedded <script> tokens
    prexvo_script_page = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>RAP vs IBR Repayment Calculator 2026 | Prexvo</title>'
        '<link rel="canonical" href="https://prexvo.com/tools/rap-vs-ibr-calculator/">'
        '</head><body><main>'
        '<h1>RAP vs IBR Repayment Calculator</h1>'
        '<p>Compare federal Title IV repayment plans alongside private refinance lenders such as SoFi, Credible, and Earnest. '
        'Refinancing federal student loans permanently waives federal protections, including IDR and PSLF.</p>'
        f'<script>if (typeof window.{legacy_sync_hook} === "function") {{ window.{legacy_sync_hook}(); }}</script>'
        '</main></body></html>'
    )
    px_res = verify_html_cross_web_consensus_and_corroboration(
        prexvo_script_page,
        rel_path="tools/rap-vs-ibr-calculator/index.html",
    )
    assert px_res["status"] == "PASS", px_res

    prexvo_body_xref = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<meta property="og:url" content="https://prexvo.com/tools/student-loan-repayment-calculator/">'
        '<title>Student Loan Repayment Calculator</title>'
        '</head><body><main>'
        '<p>Borrowers reviewing private rates from SoFi, Credible, or Earnest should note refinancing federal student loans '
        'permanently waives federal protections, including IDR and PSLF. Compare enterprise compliance tools on GainHelm.</p>'
        '</main></body></html>'
    )
    px_xref_res = verify_html_cross_web_consensus_and_corroboration(
        prexvo_body_xref,
        rel_path="tools/student-loan-repayment-calculator/index.html",
    )
    assert not any("GainHelm" in iss for iss in px_xref_res["issues"]), px_xref_res
    assert any("Cross-tenant contamination on Prexvo" in iss for iss in px_xref_res["issues"])

    profithelm_jsonld_page = (
        '<!DOCTYPE html><html lang="en"><head><title>Tax Deferral Tool</title></head><body><main>'
        '<script type="application/ld+json">{"@context":"https://schema.org","@type":"WebPage",'
        '"@id":"https://profithelm.com/tools/section-1031-calculator/#webpage",'
        '"url":"https://profithelm.com/tools/section-1031-calculator/"}</script>'
        '<p>Coordinate IRC Section 179 and Section 1031 like-kind exchange schedules with Mercury treasury accounts.</p>'
        f'<script>var legacyHook = window.{legacy_sync_hook};</script>'
        '</main></body></html>'
    )
    ph_res = verify_html_cross_web_consensus_and_corroboration(
        profithelm_jsonld_page,
        rel_path="tools/section-1031-calculator/index.html",
    )
    assert ph_res["status"] == "PASS", ph_res

    profithelm_body_xref = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>Section 179 Equipment Calculator | ProfitHelm</title>'
        '</head><body><main>'
        '<p>Model IRC Section 179 and Section 1031 depreciation alongside Mercury accounts; see gainhelm.com for SOC 2.</p>'
        '</main></body></html>'
    )
    ph_xref_res = verify_html_cross_web_consensus_and_corroboration(
        profithelm_body_xref,
        rel_path="tools/section-179-calculator/index.html",
    )
    assert not any("GainHelm" in iss for iss in ph_xref_res["issues"]), ph_xref_res
    assert any("Cross-tenant contamination on ProfitHelm" in iss for iss in ph_xref_res["issues"])

    no_head_prexvo_page = (
        '<!DOCTYPE html><html><head><title>Repayment Estimator</title></head><body>'
        '<p>Prexvo federal student loan repayment summary.</p>'
        f'<script>window.{legacy_sync_hook} = function() {{}};</script>'
        '</body></html>'
    )
    no_head_res = verify_html_cross_web_consensus_and_corroboration(
        no_head_prexvo_page,
        rel_path="tools/repayment-estimator/index.html",
    )
    assert no_head_res["status"] == "PASS", no_head_res

    lienbond_page = (
        '<!DOCTYPE html><html><head>'
        '<link rel="canonical" href="https://lienbond.com/tools/contractor-license-bond-cost-calculator-by-credit-score/">'
        '</head><body><p>LienBond surety estimator.</p></body></html>'
    )
    gainhelm_banned_page = (
        '<!DOCTYPE html><html><head>'
        '<link rel="canonical" href="https://gainhelm.com/tools/soc-2-audit-cost-calculator/">'
        '</head><body><p>Compare SoFi rates for SOC 2 compliance.</p></body></html>'
    )
    infer_fn = getattr(verifier_mod, "_infer_tenant_from_html_head", None)
    assert callable(infer_fn), "Missing _infer_tenant_from_html_head helper"
    assert infer_fn(prexvo_script_page) == "prexvo"
    assert infer_fn(prexvo_body_xref) == "prexvo"
    assert infer_fn(profithelm_jsonld_page) == "profithelm"
    assert infer_fn(profithelm_body_xref) == "profithelm"
    assert infer_fn(no_head_prexvo_page) == "prexvo"
    assert infer_fn(lienbond_page) == "lienbond"
    assert infer_fn(gainhelm_banned_page) == "gainhelm"

    gh_res = verify_html_cross_web_consensus_and_corroboration(
        gainhelm_banned_page,
        rel_path="tools/soc-2-audit-cost-calculator/index.html",
    )
    assert gh_res["status"] == "FAIL"
    assert any("Banned claim detected for GainHelm: 'sofi'" in i for i in gh_res["issues"])

    heavy_meta = _normalize_meta_120_155(
        "",
        "profithelm",
        "commercial heavy vehicle section 179 weight calculator",
        slug="commercial-heavy-vehicle-section-179-weight-calculator",
    )
    chev_meta = _normalize_meta_120_155(
        "",
        "profithelm",
        "Chevrolet Silverado 2500HD Heavy Truck Section 179",
        slug="section-179-calculator/chevrolet-silverado-2500hd",
    )
    assert chev_meta != heavy_meta

    long_qa_words = " ".join(["word"] * 53)
    px_disc_html = (
        f'<html><body><aside class="quick-answer"><p>{long_qa_words} refinancing note.</p></aside>'
        '<div class="footer-bottom"><span>Prexvo LLC</span></div></body></html>'
    )
    guarded_html = _ensure_prexvo_ymyl_forfeiture_notice(
        px_disc_html,
        {"property_id": "prexvo"},
        "governance",
    )
    qa_inner = re.search(r'<aside class="quick-answer">([\s\S]*?)</aside>', guarded_html)
    assert qa_inner is not None
    assert len(re.sub(r"<[^>]+>", " ", qa_inner.group(1)).split()) <= 60
    assert "waives federal protections" in guarded_html.lower()


@pytest.mark.host_estate
@pytest.mark.parametrize("tenant", ["prexvo", "profithelm"])
def test_prexvo_and_profithelm_temp_archive_build_and_seo_audit_parity(tmp_path: Path, tenant: str) -> None:
    from pseofactory.verifier import MasterSEOVerifier
    from pseofactory.visual_primitives import (
        get_runtime_synchronizer_script_src,
        has_current_external_runtime_sync_tag,
        render_external_runtime_synchronizer_tag,
    )

    engine_root = Path(__file__).resolve().parents[1]
    base_env = {"PATH": os.environ.get("PATH", "")}
    expected_sync_src = get_runtime_synchronizer_script_src()
    expected_sync_tag = render_external_runtime_synchronizer_tag().strip()

    if tenant == "prexvo":
        live_px = Path("/home/ubuntuadmin/projects/prexvo")
        if (live_px / ".git").is_dir():
            px_repo = tmp_path / "px_cli_repo"
            px_repo.mkdir(parents=True)
            arch_px = subprocess.run(
                f"git -C {str(live_px)!r} archive HEAD | tar -x -C {str(px_repo)!r}",
                shell=True,
                capture_output=True,
                text=True,
                check=False,
            )
            assert arch_px.returncode == 0, arch_px.stderr
            px_dist = tmp_path / "px_cli_dist"
            px_env = {**base_env, "PYTHONPATH": f"{engine_root}:{px_repo}"}
            px_build = subprocess.run(
                [sys.executable, "-m", "prexvo.cli", "build", "--dist", str(px_dist)],
                cwd=str(px_repo),
                env=px_env,
                capture_output=True,
                text=True,
                check=False,
            )
            assert px_build.returncode == 0, f"prexvo build failed:\n{px_build.stdout}\n{px_build.stderr}"
            px_verifier = MasterSEOVerifier(
                dist_dir=px_dist,
                domain="prexvo.com",
                brand_name="Prexvo",
                allow_mutations=False,
            )
            px_audit = px_verifier.audit_seo_checklist(dist_dir=px_dist, raise_on_error=True)
            assert px_audit["status"] == "PASS" and px_audit["total_issues_count"] == 0
            legacy_sync_hook = "__" + "gainhelm" + "SyncWorkspaceOutputs"
            px_sample = (px_dist / "tools" / "student-loan-repayment-calculator" / "index.html").read_text(encoding="utf-8")
            assert legacy_sync_hook not in px_sample
            assert has_current_external_runtime_sync_tag(px_sample)
            assert expected_sync_tag in px_sample
            px_sync_js_path = px_dist / expected_sync_src.lstrip("/")
            assert px_sync_js_path.is_file(), f"Missing external runtime sync JS at {px_sync_js_path}"
            px_sync_js = px_sync_js_path.read_text(encoding="utf-8")
            assert legacy_sync_hook not in px_sync_js
            assert "__complianceSyncWorkspaceOutputs" in px_sync_js
        return

    live_ph = Path("/home/ubuntuadmin/projects/profithelm-platform")
    if (live_ph / ".git").is_dir():
        ph_repo = tmp_path / "ph_cli_repo"
        ph_repo.mkdir(parents=True)
        arch_ph = subprocess.run(
            f"git -C {str(live_ph)!r} archive HEAD | tar -x -C {str(ph_repo)!r}",
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )
        assert arch_ph.returncode == 0, arch_ph.stderr
        ph_env = {**base_env, "PYTHONPATH": f"{engine_root}:{ph_repo}", "PROFITHELM_OFFLINE_JEV": "1"}
        ph_build = subprocess.run(
            [sys.executable, "-m", "profithelm.cli", "build"],
            cwd=str(ph_repo),
            env=ph_env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert ph_build.returncode == 0, f"profithelm build failed:\n{ph_build.stdout}\n{ph_build.stderr}"
        ph_dist = ph_repo / "dist"
        ph_verifier = MasterSEOVerifier(
            dist_dir=ph_dist,
            domain="profithelm.com",
            brand_name="ProfitHelm",
            allow_mutations=False,
        )
        ph_audit = ph_verifier.audit_seo_checklist(dist_dir=ph_dist, raise_on_error=True)
        assert ph_audit["status"] == "PASS" and ph_audit["total_issues_count"] == 0
        legacy_sync_hook = "__" + "gainhelm" + "SyncWorkspaceOutputs"
        ph_sample = (ph_dist / "tools" / "section-179-calculator" / "index.html").read_text(encoding="utf-8")
        assert legacy_sync_hook not in ph_sample
        assert has_current_external_runtime_sync_tag(ph_sample)
        assert expected_sync_tag in ph_sample
        ph_sync_js_path = ph_dist / expected_sync_src.lstrip("/")
        assert ph_sync_js_path.is_file(), f"Missing external runtime sync JS at {ph_sync_js_path}"
        ph_sync_js = ph_sync_js_path.read_text(encoding="utf-8")
        assert legacy_sync_hook not in ph_sync_js
        assert "__complianceSyncWorkspaceOutputs" in ph_sync_js
