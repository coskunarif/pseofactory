"""
Regression and verification tests for:
1. x-like:2098466536394494211 Engine Upgrade #1: Above-the-fold Instant Range Anchor
   (#hero-range-anchor) and Step 1 State-First Hero Selector (#quote-intake-hero-state)
   synced with #quote-intake-state and URL ?state= parameters.
2. x-like:2098466536394494211 Engine Upgrade #2: Self-Serve "Register Your Firm"
   B2B Partner Supply Intake (#partner-registration-drawer / #partner-registration-form)
   and Cloudflare Edge /api/lead-capture partner_registration handling across
   profithelm, gainhelm, and prexvo (while strictly suppressing on restricted YMYL pages).
3. P2 Autonomous Daily Trend-to-Page Builder (execute_autonomous_daily_trend_page_build
   and AutonomousLifecycleSupervisor.run_cycle) enforcing the 1-page-per-tenant-per-day
   cap, cannibalization reconciliation, provenance registration, and zero-orphan linking.
Zero em-dashes. Zero en-dashes.
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict

from pseofactory.compiler import compile_high_effort_page
from pseofactory.contracts import assert_no_forbidden_dashes
from pseofactory.edge import generate_edge_lead_capture_function
from pseofactory.maintenance import ConfigurablePropertyAdapter, TenantRegistry
from pseofactory.pipeline import execute_autonomous_daily_trend_page_build
from pseofactory.supervisor import AutonomousLifecycleSupervisor
from pseofactory.visual_primitives import assert_visual_and_ux_contracts


def _build_sample_spec(property_id: str, slug: str, query: str) -> Dict[str, Any]:
    domain_map = {
        "profithelm": ("profithelm.com", "ProfitHelm", "26 U.S.C. Section 179 and IRC Section 168(k)"),
        "gainhelm": ("gainhelm.com", "GainHelm", "AICPA SSAE 18 AT-C Section 320 and NIST SP 800-53 Rev. 5"),
        "prexvo": ("prexvo.com", "Prexvo", "34 CFR 685.209 and Title IV Higher Education Act"),
    }
    domain, brand, stat_auth = domain_map[property_id]
    return {
        "slug": slug,
        "query": query,
        "title": f"{query.title()} Calculator",
        "property_id": property_id,
        "tenant": property_id,
        "domain": domain,
        "brand_name": brand,
        "canonical_base": f"https://{domain}",
        "model_name": f"{brand}-{slug[:20].title()}-Model-2026",
        "statutory_authority": stat_auth,
        "economic_dataset": "BLS OEWS Wage Series and Federal Reserve FRED Economic Benchmark Data",
        "formula": "round(baseline_amount * effective_rate, 2)",
        "inputs": {"baseline_amount": 100000.0, "effective_rate": 0.25},
        "published_output": 25000.0,
        "sample_calculation": "Evaluating round(100000.0 * 0.25, 2) yields 25,000.00.",
        "mandatory_disclosures": [
            "Refinancing federal student loans permanently waives federal protections, including income-driven repayment and Public Service Loan Forgiveness (PSLF) eligibility under Title IV 34 CFR Part 685."
            if property_id == "prexvo"
            else "Deterministic quantitative modeling disclosure for statutory scenario evaluation."
        ],
    }


def test_state_first_hero_and_instant_range_anchor_and_partner_registration_dom() -> None:
    """
    Verifies that compiled pages across ProfitHelm, GainHelm, and Prexvo commercial
    refinance include:
      1. Above-the-fold #hero-range-anchor with 0.8x conservative, 1.0x baseline, and 1.2x aggressive values.
      2. Step 1 State-First Hero input (#quote-intake-hero-state) inside #calculator-workspace-anchor
         above <form class="calculator-form">.
      3. Self-serve #partner-registration-drawer and #partner-registration-form on commercial pages,
         strictly suppressed on restricted YMYL public-service pages.
    """
    ph_res = compile_high_effort_page(
        _build_sample_spec("profithelm", "section-179-heavy-equipment-tax-calculator", "section 179 heavy equipment tax")
    )
    ph_html = ph_res["html"]
    assert_no_forbidden_dashes(ph_html, "profithelm compiled html")
    assert_visual_and_ux_contracts(ph_html, context="profithelm compiled html", require_primitives=True)

    assert 'id="hero-range-anchor"' in ph_html
    assert 'data-mechanic="instant_range_anchor"' in ph_html
    assert 'data-range-low="20,000"' in ph_html
    assert 'data-range-baseline="25,000"' in ph_html
    assert 'data-range-high="30,000"' in ph_html
    assert 'href="#partner-registration-drawer"' in ph_html

    assert 'id="state-first-hero-bar"' in ph_html
    assert 'data-mechanic="state_first_hero_input"' in ph_html
    assert 'id="quote-intake-hero-state"' in ph_html
    hero_state_pos = ph_html.find('id="quote-intake-hero-state"')
    calc_form_pos = ph_html.find('<form class="calculator-form"')
    assert 0 < hero_state_pos < calc_form_pos

    assert 'id="partner-registration-drawer"' in ph_html
    assert 'data-mechanic="partner_supply_registration"' in ph_html
    assert 'id="partner-registration-form"' in ph_html

    # Verify GainHelm commercial page
    gh_res = compile_high_effort_page(
        _build_sample_spec("gainhelm", "soc-2-audit-cost-calculator", "soc 2 audit cost")
    )
    gh_html = gh_res["html"]
    assert 'id="hero-range-anchor"' in gh_html
    assert 'id="quote-intake-hero-state"' in gh_html
    assert 'id="partner-registration-drawer"' in gh_html

    # Verify Prexvo commercial refinance page has partner registration drawer
    px_refi_res = compile_high_effort_page(
        _build_sample_spec("prexvo", "student-loan-refinance-rate-calculator", "student loan refinance rate")
    )
    px_refi_html = px_refi_res["html"]
    assert 'id="hero-range-anchor"' in px_refi_html
    assert 'id="quote-intake-hero-state"' in px_refi_html
    assert 'id="partner-registration-drawer"' in px_refi_html

    # Verify Prexvo restricted YMYL public-service page suppresses partner registration drawer
    px_pslf_res = compile_high_effort_page(
        _build_sample_spec("prexvo", "pslf-qualifying-payment-simulator", "pslf qualifying payment simulator")
    )
    px_pslf_html = px_pslf_res["html"]
    assert 'id="hero-range-anchor"' in px_pslf_html
    assert 'id="quote-intake-hero-state"' in px_pslf_html
    assert 'id="partner-registration-drawer"' not in px_pslf_html
    assert 'href="#partner-registration-drawer"' not in px_pslf_html


def test_edge_lead_capture_partner_registration_across_all_three_tenants(tmp_path: Path) -> None:
    """
    Executes the generated Cloudflare Pages Function /api/lead-capture in Node.js across
    profithelm, gainhelm, and prexvo to verify:
      1. POST with intent='partner_registration' validates email + firm_name, returns status='partner_registered',
         lead_type='partner_registration', and a programmable partner-slot checkout URL ($299).
      2. GET summary exposes partner_registrations_count == 1 while keeping qualified_quotes_count == 0.
    """
    expected_skus = {
        "profithelm": "ph_verified_partner_slot",
        "gainhelm": "gh_verified_partner_slot",
        "prexvo": "px_verified_partner_slot",
    }
    for prop, expected_sku in expected_skus.items():
        js_code = generate_edge_lead_capture_function(prop)
        assert_no_forbidden_dashes(js_code, f"edge lead capture {prop}")
        mod_path = tmp_path / f"lead_capture_{prop}.mjs"
        mod_path.write_text(js_code, encoding="utf-8")

        slug = (
            "student-loan-refinance-break-even-calculator"
            if prop == "prexvo"
            else ("soc-2-audit-cost-calculator" if prop == "gainhelm" else "section-179-calculator")
        )
        runner = tmp_path / f"run_{prop}.mjs"
        runner.write_text(
            f"""
import {{ onRequestPost, onRequestGet }} from "./lead_capture_{prop}.mjs";

const env = {{}};
const postReq = new Request("https://{prop}.com/api/lead-capture", {{
  method: "POST",
  headers: {{ "Content-Type": "application/json" }},
  body: JSON.stringify({{
    intent: "partner_registration",
    email: "partners@apexadvisory.com",
    firm_name: "Apex Advisory Partners LLP",
    state: "TX",
    tool_slug: "{slug}"
  }})
}});
const postRes = await onRequestPost({{ request: postReq, env }});
const postJson = await postRes.json();

const getReq = new Request("https://{prop}.com/api/lead-capture", {{ method: "GET" }});
const getRes = await onRequestGet({{ request: getReq, env }});
const getJson = await getRes.json();

console.log(JSON.stringify({{ postStatus: postRes.status, postJson, getJson }}));
""",
            encoding="utf-8",
        )
        proc = subprocess.run(
            ["node", str(runner)],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        out = json.loads(proc.stdout.strip().splitlines()[-1])
        assert out["postStatus"] == 200
        post_data = out["postJson"]
        assert post_data["ok"] is True
        assert post_data["status"] == "partner_registered"
        assert post_data["lead_type"] == "partner_registration"
        assert post_data["firm_name"] == "Apex Advisory Partners LLP"
        assert post_data["state"] == "TX"
        assert post_data["offer_sku"] == expected_sku
        assert post_data["offer_price_usd"] == 299
        assert f"sku={expected_sku}" in post_data["checkout_url"]

        summary = out["getJson"]["summary"]
        assert summary["partner_registrations_count"] == 1
        assert summary["qualified_quotes_count"] == 0
        assert summary["playbook_subscriptions_count"] == 0


def test_p2_autonomous_daily_trend_page_build_and_supervisor_integration(tmp_path: Path) -> None:
    """
    Verifies P2 execute_autonomous_daily_trend_page_build and AutonomousLifecycleSupervisor:
      1. Reconciles already-built slugs in dist/tools/<slug>/index.html to BUILT.
      2. Reconciles cannibalizing slugs to REFACTOR_PAGE.
      3. Builds at most 1 new page per tenant per UTC day, records provenance in
         deployed_voids.json, links the route in dist/tools/index.html and sitemap-leaves.xml,
         and skips the second candidate for the same tenant on the same day.
      4. Integrates cleanly with AutonomousLifecycleSupervisor.run_cycle.
    """
    reg = TenantRegistry()
    for pid, domain, brand in (
        ("profithelm", "profithelm.com", "ProfitHelm"),
        ("prexvo", "prexvo.com", "Prexvo"),
        ("gainhelm", "gainhelm.com", "GainHelm"),
    ):
        t_root = tmp_path / pid
        t_dist = t_root / "dist"
        (t_dist / "tools" / "existing-tool-calculator").mkdir(parents=True, exist_ok=True)
        (t_dist / "tools" / "existing-tool-calculator" / "index.html").write_text(
            "<html><body>Existing</body></html>", encoding="utf-8"
        )
        (t_dist / "tools" / "index.html").write_text(
            "<html><body><main><h1>Tools Directory</h1></main></body></html>",
            encoding="utf-8",
        )
        (t_dist / "sitemap-leaves.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n</urlset>\n',
            encoding="utf-8",
        )
        reg.register_adapter(
            ConfigurablePropertyAdapter(
                property_id=pid,
                brand_name=brand,
                domain=domain,
                canonical_base=f"https://{domain}",
                dist_dir=t_dist,
                repo_path=t_root,
                tools=[{"slug": "existing-tool-calculator", "query": "existing tool calculator"}],
            )
        )

    queue_file = tmp_path / ".agy" / "void_candidates.jsonl"
    ledger_file = tmp_path / ".agy" / "daily_page_build_ledger.json"
    queue_file.parent.mkdir(parents=True, exist_ok=True)

    candidates = [
        # 1. Already built in dist -> should reconcile to BUILT without consuming daily cap
        {
            "property_id": "profithelm",
            "slug": "existing-tool-calculator",
            "query": "existing tool calculator",
            "action": "BUILD_PAGE",
            "status": "PENDING",
            "composite_profit_yield": 99.9,
        },
        # 2. Cannibalizing existing-tool-calculator -> should reconcile to REFACTOR_PAGE
        {
            "property_id": "profithelm",
            "slug": "existing-tool-cost-calculator",
            "query": "existing tool cost calculator",
            "action": "BUILD_PAGE",
            "status": "PENDING",
            "composite_profit_yield": 98.5,
        },
        # 3. Top valid unbuilt ProfitHelm candidate -> should build today (1/1 cap)
        {
            "property_id": "profithelm",
            "slug": "qsbs-section-1202-state-conformity-tax-calculator",
            "query": "qsbs section 1202 state conformity tax calculator",
            "action": "BUILD_PAGE",
            "status": "PENDING",
            "composite_profit_yield": 95.0,
        },
        # 4. Second valid unbuilt ProfitHelm candidate -> should be skipped today due to 1/day cap
        {
            "property_id": "profithelm",
            "slug": "section-199a-qbi-phaseout-wage-limit-calculator",
            "query": "section 199a qbi phaseout wage limit calculator",
            "action": "BUILD_PAGE",
            "status": "PENDING",
            "composite_profit_yield": 91.0,
        },
        # 5. Top valid unbuilt Prexvo candidate -> should build today (1/1 cap for prexvo)
        {
            "property_id": "prexvo",
            "slug": "parent-plus-loan-payment-calculator",
            "query": "parent plus loan payment calculator",
            "action": "BUILD_PAGE",
            "status": "PENDING",
            "composite_profit_yield": 72.7,
        },
    ]
    queue_file.write_text("\n".join(json.dumps(c) for c in candidates) + "\n", encoding="utf-8")

    res = execute_autonomous_daily_trend_page_build(
        property_ids=["profithelm", "prexvo", "gainhelm"],
        void_candidates_path=queue_file,
        ledger_path=ledger_file,
        max_pages_per_tenant_per_day=1,
        date_key="2026-11-07",
        registry=reg,
        dry_run=False,
        enable_gitops=False,
    )

    assert res["status"] == "PASS"
    assert res["reconciled_already_built_count"] == 1
    assert res["reconciled_cannibalizing_count"] == 1
    assert res["built_count"] == 2
    built_by_prop = {b["property_id"]: b["slug"] for b in res["built_pages"]}
    assert built_by_prop == {
        "profithelm": "qsbs-section-1202-state-conformity-tax-calculator",
        "prexvo": "parent-plus-loan-payment-calculator",
    }
    assert "profithelm" in res["skipped_daily_cap_tenants"]

    # Verify compiled HTML files, manifests, provenance, and zero-orphan links
    ph_built_html = (
        tmp_path / "profithelm" / "dist" / "tools" / "qsbs-section-1202-state-conformity-tax-calculator" / "index.html"
    )
    assert ph_built_html.is_file()
    assert 'id="hero-range-anchor"' in ph_built_html.read_text(encoding="utf-8")
    assert (tmp_path / "profithelm" / ".agy" / "deployed_voids.json").is_file()
    assert (
        "/tools/qsbs-section-1202-state-conformity-tax-calculator/"
        in (tmp_path / "profithelm" / "dist" / "tools" / "index.html").read_text(encoding="utf-8")
    )
    assert (
        "https://profithelm.com/tools/qsbs-section-1202-state-conformity-tax-calculator/"
        in (tmp_path / "profithelm" / "dist" / "sitemap-leaves.xml").read_text(encoding="utf-8")
    )

    px_built_html = (
        tmp_path / "prexvo" / "dist" / "tools" / "parent-plus-loan-payment-calculator" / "index.html"
    )
    assert px_built_html.is_file()
    assert (tmp_path / "prexvo" / "content" / "deployed_voids.json").is_file()

    # Running a second time on the same UTC date_key must build 0 pages for profithelm
    res_second = execute_autonomous_daily_trend_page_build(
        property_ids=["profithelm", "prexvo", "gainhelm"],
        void_candidates_path=queue_file,
        ledger_path=ledger_file,
        max_pages_per_tenant_per_day=1,
        date_key="2026-11-07",
        registry=reg,
        dry_run=False,
        enable_gitops=False,
    )
    assert res_second["built_count"] == 0
    assert "profithelm" in res_second["skipped_daily_cap_tenants"]

    # Running via AutonomousLifecycleSupervisor.run_cycle on the next UTC day builds the remaining ProfitHelm candidate
    sup = AutonomousLifecycleSupervisor(
        workspace_root=tmp_path,
        registry=reg,
        void_candidates_path=queue_file,
        daily_build_ledger_path=ledger_file,
        max_pages_per_tenant_per_day=1,
    )
    cycle_res = sup.run_cycle(force=False, dry_run=True, enable_gitops=False)
    assert "daily_trend_page_build" in cycle_res
    assert cycle_res["daily_trend_page_build"]["status"] == "PASS"
