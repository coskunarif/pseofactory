"""
Tests for the Native TCPA-Compliant Partner Quote Intake Step & Qualified CPL Lead Funnel:
1. High-value threshold evaluation ($100k+ 1031 Exchange / CapEx Section 179, $50k+ Invoice Factoring,
   $50k+ Prexvo Student Loan Refinance).
2. Frictionless sub-threshold behavior (no forced gating below threshold).
3. Strict YMYL public-service exclusion on Prexvo (PSLF, IBR hardship, SAVE litigation stay 100% free
   of commercial private refinance offers and lead capture).
4. Native HTML/JS rendering (#partner-quote-intake-step) and visual/ergonomic contract compliance.
5. Persisting consented CPL records in `.agy/captured_leads.jsonl` and routing to live partners.
6. Dispatching $100,000+ B2B and student loan refinance leads onto HumanActionBus for
   OTR Solutions, E-file, IPX1031, and Splash Financial partner reps.
7. Edge `/api/lead-capture` function generation and tenant synchronization.
"""

from pathlib import Path
import pytest

from pseofactory.action_bus import HumanActionBus
from pseofactory.partner_tracker import (
    PartnerTrackingEngine,
    evaluate_lead_quote_threshold,
    ingest_qualified_lead,
)
from pseofactory.competitor import render_partner_quote_intake_html
from pseofactory.compiler import compile_high_effort_page
from pseofactory.contracts import assert_no_forbidden_dashes
from pseofactory.maintenance import CrossPropertyContaminationScanner
from pseofactory.visual_primitives import assert_visual_and_ux_contracts
from pseofactory.edge import (
    generate_edge_lead_capture_function,
    sync_tenant_edge_redirect_function,
)



# Mock of the Stripe Checkout Session lookup the edge performs before unlocking paid workpapers.
# A session id of the form cs_live_PAIDFOR_<lead_id> resolves to a paid live session for that lead.
STRIPE_PAID_MOCK_JS = r"""
const __origFetch = globalThis.fetch;
globalThis.fetch = async (url, init) => {
  const m = String(url).match(/api\.stripe\.com\/v1\/checkout\/sessions\/cs_live_PAIDFOR_([A-Za-z0-9_]+)$/);
  if (m) {
    const lead = m[1];
    return new Response(JSON.stringify({
      id: "cs_live_PAIDFOR_" + lead, livemode: true, payment_status: "paid", amount_total: 4900,
      currency: "usd", client_reference_id: lead, metadata: { lead_id: lead }
    }), { status: 200 });
  }
  return __origFetch ? __origFetch(url, init) : new Response("{}", { status: 500 });
};
"""

def test_threshold_evaluation_across_verticals_and_frictionless_sub_threshold():
    # 1. 1031 Exchange: $100,000+ threshold
    sub_1031 = evaluate_lead_quote_threshold("profithelm", "section-1031-calculator", 75000)
    assert sub_1031["eligible"] is True
    assert sub_1031["threshold_usd"] == 100000.0
    assert sub_1031["qualifies_for_quote_intake"] is False
    assert sub_1031["frictionless_mode"] is True

    high_1031 = evaluate_lead_quote_threshold("profithelm", "section-1031-calculator", 150000)
    assert high_1031["qualifies_for_quote_intake"] is True
    assert high_1031["qualifies_for_action_bus_dispatch"] is True
    assert high_1031["frictionless_mode"] is False
    assert high_1031["primary_partner_key"] == "ipx1031"
    assert high_1031["capital_band"] == "100k_250k"

    # 2. CapEx / Section 179: $100,000+ threshold
    sub_179 = evaluate_lead_quote_threshold("profithelm", "section-179-calculator", 60000)
    assert sub_179["threshold_usd"] == 100000.0
    assert sub_179["qualifies_for_quote_intake"] is False
    assert sub_179["frictionless_mode"] is True

    high_179 = evaluate_lead_quote_threshold("profithelm", "section-179-calculator", 120000)
    assert high_179["qualifies_for_quote_intake"] is True
    assert high_179["qualifies_for_action_bus_dispatch"] is True
    assert high_179["primary_partner_key"] == "crest_capital"

    # 3. Invoice Factoring: $50,000+ threshold
    sub_fac = evaluate_lead_quote_threshold("profithelm", "invoice-factoring-cost-apr-calculator", 35000)
    assert sub_fac["threshold_usd"] == 50000.0
    assert sub_fac["qualifies_for_quote_intake"] is False
    assert sub_fac["frictionless_mode"] is True

    mid_fac = evaluate_lead_quote_threshold("profithelm", "invoice-factoring-cost-apr-calculator", 65000)
    assert mid_fac["qualifies_for_quote_intake"] is True
    assert mid_fac["qualifies_for_action_bus_dispatch"] is False
    assert mid_fac["primary_partner_key"] == "otr_solutions_factoring"
    assert mid_fac["capital_band"] == "50k_100k"

    high_fac = evaluate_lead_quote_threshold("profithelm", "invoice-factoring-cost-apr-calculator", 125000)
    assert high_fac["qualifies_for_quote_intake"] is True
    assert high_fac["qualifies_for_action_bus_dispatch"] is True

    # 4. Prexvo Student Loan Refinance: $50,000+ threshold
    sub_refi = evaluate_lead_quote_threshold("prexvo", "student-loan-refinance-break-even-calculator", 32000)
    assert sub_refi["threshold_usd"] == 50000.0
    assert sub_refi["qualifies_for_quote_intake"] is False
    assert sub_refi["frictionless_mode"] is True

    high_refi = evaluate_lead_quote_threshold("prexvo", "student-loan-refinance-break-even-calculator", 115000)
    assert high_refi["qualifies_for_quote_intake"] is True
    assert high_refi["qualifies_for_action_bus_dispatch"] is True
    assert high_refi["primary_partner_key"] == "splash_financial"


def test_restricted_ymyl_public_service_pages_stay_strictly_free_of_refinance_intake(tmp_path):
    restricted_slugs = (
        "pslf-qualifying-payment-simulator",
        "ibr-hardship-cap-calculator",
        "save-plan-litigation-transition",
        "disclaimers",
        "methodology",
    )
    for r_slug in restricted_slugs:
        eval_res = evaluate_lead_quote_threshold("prexvo", r_slug, 150000)
        assert eval_res["eligible"] is False
        assert eval_res["qualifies_for_quote_intake"] is False
        assert render_partner_quote_intake_html(r_slug, "prexvo") == ""

        with pytest.raises(ValueError, match="Restricted public-service|ineligible"):
            ingest_qualified_lead(
                property_id="prexvo",
                tool_slug=r_slug,
                email="borrower@example.edu",
                state="NY",
                capital_band="100k_250k",
                calculated_amount=150000,
                partner_sharing_consent=True,
                leads_ledger_path=tmp_path / "leads.jsonl",
                action_bus_path=tmp_path / "bus.json",
            )


def test_compiled_pages_render_tcpa_quote_intake_and_pass_all_visual_contracts():
    ph_page = compile_high_effort_page(
        {
            "slug": "section-1031-calculator",
            "title": "1031 Exchange Tax Deferral & Boot Calculator",
            "model_name": "1031 Exchange Tax Deferral Model",
            "property_id": "profithelm",
            "canonical_base": "https://profithelm.com",
            "formula": "gross_amount * (1.0 - effective_rate)",
            "inputs": {"gross_amount": 450000.0, "effective_rate": 0.24},
            "published_output": 342000.0,
            "sample_calculation": "Evaluating $450,000 relinquished exchange equity at 24% effective tax rate yields $342,000.00 net retained basis.",
            "statutory_authority": "IRC Section 1031 and IRS Form 8824",
            "economic_dataset": "BEA Fixed Assets Series",
        }
    )
    ph_html = ph_page["html"]
    assert 'id="partner-quote-intake-step"' in ph_html
    assert 'id="partner-quote-intake-form"' in ph_html
    assert 'name="email"' in ph_html
    assert 'name="state"' in ph_html
    assert 'name="capital_band"' in ph_html
    assert 'name="partner_sharing_consent"' in ph_html
    assert 'data-quote-threshold="100000"' in ph_html
    assert_no_forbidden_dashes(ph_html, context="profithelm_1031_html")
    assert_visual_and_ux_contracts(ph_html, context="profithelm_1031_html")
    scanner = CrossPropertyContaminationScanner()
    assert scanner.scan_text(ph_html, "profithelm") == []

    px_refi_page = compile_high_effort_page(
        {
            "slug": "student-loan-refinance-break-even-calculator",
            "title": "Student Loan Refinance Break-Even Calculator",
            "model_name": "Student Loan Refinance Break-Even Model",
            "property_id": "prexvo",
            "canonical_base": "https://prexvo.com",
            "formula": "gross_amount * (1.0 - effective_rate)",
            "inputs": {"gross_amount": 85000.0, "effective_rate": 0.06},
            "published_output": 79900.0,
            "sample_calculation": "Evaluating $85,000 loan balance at 6% rate factor yields $79,900.00 baseline output.",
            "statutory_authority": "Higher Education Act Title IV (20 U.S.C. 1070 et seq.); 34 CFR Part 685",
            "economic_dataset": "Federal Reserve G.19 Consumer Credit Series",
        }
    )
    px_refi_html = px_refi_page["html"]
    assert 'id="partner-quote-intake-step"' in px_refi_html
    assert 'data-quote-threshold="50000"' in px_refi_html
    assert 'data-partner-key="splash_financial"' in px_refi_html
    assert_no_forbidden_dashes(px_refi_html, context="prexvo_refi_html")
    assert_visual_and_ux_contracts(px_refi_html, context="prexvo_refi_html")
    assert scanner.scan_text(px_refi_html, "prexvo") == []

    px_pslf_page = compile_high_effort_page(
        {
            "slug": "pslf-qualifying-payment-simulator",
            "title": "PSLF Qualifying Payment Simulator",
            "model_name": "PSLF Qualifying Payment Simulator Model",
            "property_id": "prexvo",
            "canonical_base": "https://prexvo.com",
            "formula": "gross_amount * (1.0 - effective_rate)",
            "inputs": {"gross_amount": 85000.0, "effective_rate": 0.10},
            "published_output": 76500.0,
            "sample_calculation": "Evaluating $85,000 loan balance at 10% discretionary cap yields $76,500.00 Forgiveness Projection.",
            "statutory_authority": "Higher Education Act Title IV (20 U.S.C. 1070 et seq.); 34 CFR Part 685",
            "economic_dataset": "Federal Reserve G.19 Consumer Credit Series",
        }
    )
    px_pslf_html = px_pslf_page["html"]
    assert 'id="partner-quote-intake-step"' not in px_pslf_html
    assert 'href="/r/' not in px_pslf_html


def test_lead_ingestion_persists_ledger_and_dispatches_100k_leads_to_human_action_bus(tmp_path):
    leads_path = tmp_path / "captured_leads.jsonl"
    bus_path = tmp_path / "human_action_bus.json"
    bus = HumanActionBus(bus_path=bus_path)
    engine = PartnerTrackingEngine(action_bus=bus)

    # 1. Sub-threshold calculation stays frictionless and does not persist or gate
    sub_res = engine.ingest_qualified_lead(
        property_id="profithelm",
        tool_slug="invoice-factoring-cost-apr-calculator",
        email="ops@carrierfleet.com",
        state="TX",
        capital_band="under_50k",
        calculated_amount=30000,
        partner_sharing_consent=False,
        leads_ledger_path=leads_path,
    )
    assert sub_res["status"] == "frictionless_sub_threshold"
    assert sub_res["persisted"] is False
    assert sub_res["frictionless_mode"] is True
    assert sub_res["action_bus_dispatched"] is False

    # 2. $65,000 Invoice Factoring lead (>= $50k threshold, < $100k ActionBus threshold)
    mid_fac_res = engine.ingest_qualified_lead(
        property_id="profithelm",
        tool_slug="invoice-factoring-cost-apr-calculator",
        email="cfo@regionalfreight.com",
        state="TX",
        capital_band="50k_100k",
        calculated_amount=65000,
        partner_sharing_consent=True,
        leads_ledger_path=leads_path,
    )
    assert mid_fac_res["status"] == "captured"
    assert mid_fac_res["persisted"] is True
    assert mid_fac_res["partner_key"] == "otr_solutions_factoring"
    assert "/r/otr_solutions_factoring?" in mid_fac_res["redirect_url"]
    assert "state=TX" in mid_fac_res["redirect_url"]
    assert mid_fac_res["action_bus_dispatched"] is False

    # 3. $150,000 Invoice Factoring lead -> dispatches to OTR Solutions (Wade Fenton) on HumanActionBus
    high_fac_res = engine.ingest_qualified_lead(
        property_id="profithelm",
        tool_slug="invoice-factoring-cost-apr-calculator",
        email="treasury@nationalhauling.com",
        state="IL",
        capital_band="100k_250k",
        calculated_amount=150000,
        partner_sharing_consent=True,
        leads_ledger_path=leads_path,
    )
    assert high_fac_res["action_bus_dispatched"] is True
    assert high_fac_res["action_bus_item_id"] == "act-profithelm-otr-solutions-factoring-high-value-lead-dispatch"

    # 4. $450,000 1031 Exchange lead -> dispatches to IPX1031 on HumanActionBus
    high_1031_res = engine.ingest_qualified_lead(
        property_id="profithelm",
        tool_slug="section-1031-calculator",
        email="sponsor@creholdings.com",
        state="CA",
        capital_band="250k_500k",
        calculated_amount=450000,
        partner_sharing_consent=True,
        leads_ledger_path=leads_path,
    )
    assert high_1031_res["action_bus_dispatched"] is True
    assert high_1031_res["partner_key"] == "ipx1031"
    assert "IPX1031" in high_1031_res["partner_rep_desk"]

    # 5. $180,000 B2B Tax / CapEx lead -> dispatches to E-file (Aaron Rosenthal) on HumanActionBus
    high_tax_res = engine.ingest_qualified_lead(
        property_id="profithelm",
        tool_slug="s-corp-reasonable-salary-tax-calculator",
        email="founder@saasventures.io",
        state="NY",
        capital_band="100k_250k",
        calculated_amount=180000,
        partner_sharing_consent=True,
        leads_ledger_path=leads_path,
    )
    assert high_tax_res["action_bus_dispatched"] is True
    assert high_tax_res["partner_key"] == "turbotax"
    assert "E-file" in high_tax_res["partner_rep_desk"]

    # 6. $140,000 Prexvo Student Loan Refinance lead -> dispatches to Splash Financial on HumanActionBus
    high_refi_res = engine.ingest_qualified_lead(
        property_id="prexvo",
        tool_slug="student-loan-refinance-break-even-calculator",
        email="attending.md@hospital.org",
        state="MA",
        capital_band="100k_250k",
        calculated_amount=140000,
        partner_sharing_consent=True,
        leads_ledger_path=leads_path,
    )
    assert high_refi_res["action_bus_dispatched"] is True
    assert high_refi_res["partner_key"] == "splash_financial"
    assert "Splash Financial" in high_refi_res["partner_rep_desk"]

    captured = engine.get_captured_leads(leads_ledger_path=leads_path)
    assert len(captured) == 5
    pending_bus_items = bus.get_pending_items()
    partner_keys_on_bus = {it.partner_key for it in pending_bus_items}
    assert {"otr_solutions_factoring", "ipx1031", "turbotax", "splash_financial"}.issubset(partner_keys_on_bus)


def test_edge_lead_capture_function_generation_and_tenant_sync(tmp_path):
    ph_js = generate_edge_lead_capture_function("profithelm")
    px_js = generate_edge_lead_capture_function("prexvo")

    assert_no_forbidden_dashes(ph_js, context="profithelm_lead_capture_js")
    assert_no_forbidden_dashes(px_js, context="prexvo_lead_capture_js")

    assert "PROFITHELM_LEADS" in ph_js
    assert "otr_solutions_factoring" in ph_js
    assert "ipx1031" in ph_js
    assert "splash_financial" not in ph_js
    assert "ok: true, success: true" in ph_js
    assert "ok: false, success: false" in ph_js

    assert "PREXVO_LEADS" in px_js
    assert "splash_financial" in px_js
    assert "RESTRICTED_PUBLIC_SERVICE_SLUGS" in px_js
    assert "otr_solutions_factoring" not in px_js
    assert "ok: true, success: true" in px_js
    assert "ok: false, success: false" in px_js

    for prop_id in ("profithelm", "prexvo"):
        repo_dir = tmp_path / prop_id
        (repo_dir / "functions" / "r").mkdir(parents=True)
        (repo_dir / "wrangler.toml").write_text(f'name = "{prop_id}"\n', encoding="utf-8")
        res = sync_tenant_edge_redirect_function(repo_dir, property_id=prop_id)
        assert res["status"] == "UPDATED"
        assert (repo_dir / "functions" / "api" / "lead-capture.js").is_file()


def test_tenant_ci_workflow_and_script_isolation_sync(tmp_path):
    from pseofactory.gitops import sync_tenant_test_isolation_guards
    from pseofactory.trends.cron import TrendCronRunner

    for repo_name in ("profithelm-platform", "prexvo"):
        t_repo = tmp_path / repo_name
        pkg_name = "profithelm" if "profithelm" in repo_name else "prexvo"
        (t_repo / pkg_name).mkdir(parents=True)
        (t_repo / "scripts").mkdir(parents=True)
        (t_repo / ".github" / "workflows").mkdir(parents=True)
        (t_repo / "scripts" / "run_factory.sh").write_text(
            '#!/usr/bin/env bash\nSCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\nREPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"\necho "$$" > "$PID_FILE"\n',
            encoding="utf-8",
        )
        if repo_name == "prexvo":
            (t_repo / "prexvo" / "factory.py").write_text(
                '                        "description": selected_opp.get("description", f"Calculate statutory options for {target_q}."),\n'
                '                is_statutory = isinstance(ex, StatutoryAccuracyError)\n',
                encoding="utf-8",
            )
        (t_repo / ".github" / "workflows" / "ci.yml").write_text(
            "name: Legacy CI\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n",
            encoding="utf-8",
        )
        if repo_name == "profithelm-platform":
            (t_repo / ".github" / "workflows" / "deploy-google.yml").write_text(
                "name: Legacy Deploy\non:\n  push:\n    branches: [main]\njobs:\n  deploy:\n    runs-on: ubuntu-latest\n",
                encoding="utf-8",
            )

        res = sync_tenant_test_isolation_guards(t_repo)
        assert res["status"] == "PASS"
        assert res["updated_files"] >= 2

        rf_text = (t_repo / "scripts" / "run_factory.sh").read_text(encoding="utf-8")
        assert 'readlink -f "${BASH_SOURCE[0]}"' in rf_text
        assert "PSEUFACTORY_HOLDS_SUPERVISOR_LOCK" in rf_text

        if repo_name == "prexvo":
            f_text = (t_repo / "prexvo" / "factory.py").read_text(encoding="utf-8")
            assert "under 34 CFR 685.209 with verified repayment and forgiveness math." in f_text
            assert "SEO checklist verification failed" in f_text

        ci_text = (t_repo / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        assert "runs-on: self-hosted" in ci_text
        assert "cancel-in-progress: true" in ci_text
        assert "unset CLOUDFLARE_API_TOKEN" in ci_text
        assert "if [ ! -f dist/index.html ]; then" in ci_text

        if repo_name == "profithelm-platform":
            dg_text = (t_repo / ".github" / "workflows" / "deploy-google.yml").read_text(encoding="utf-8")
            assert "runs-on: self-hosted" in dg_text
            assert "workflow_dispatch:" in dg_text
            assert "branches: [main]" not in dg_text

    import inspect
    cron_src = inspect.getsource(TrendCronRunner.run_cycle)
    assert '".agy" / "void_candidates.jsonl"' in cron_src

    from pseofactory.maintenance import (
        _needs_page_structure_geo_normalization,
        _normalize_page_structure_and_geo_parity,
    )
    short_meta_html = (
        '<html><head><meta name="description" content="Calculate statutory options for student loan forgiveness update."></head>'
        '<body><h1>Student Loan Forgiveness Update</h1></body></html>'
    )
    assert _needs_page_structure_geo_normalization(short_meta_html) is True
    norm_html, changed = _normalize_page_structure_and_geo_parity(
        short_meta_html,
        property_id="prexvo",
        slug="student-loan-forgiveness-update",
        topic_label="Student Loan Forgiveness Update",
        canonical_url="https://prexvo.com/tools/student-loan-forgiveness-update/",
        stat_auth="Higher Education Act Title IV (20 U.S.C. 1070 et seq.); 34 CFR Part 685",
        econ_ds="Federal Reserve G.19 Consumer Credit Series",
    )
    assert changed is True
    assert _needs_page_structure_geo_normalization(norm_html) is False


def test_playbook_subscription_stripe_checkout_and_transactional_responder(tmp_path):
    from pseofactory.partner_tracker import (
        ingest_playbook_subscription,
        resolve_lead_monetization_offer,
        create_stripe_checkout_session,
        render_transactional_playbook_email,
        dispatch_transactional_playbook,
        get_lead_monitoring_summary,
    )

    scanner = CrossPropertyContaminationScanner()
    leads_path = tmp_path / "captured_leads.jsonl"

    # 1. ProfitHelm 1031 Playbook Subscription attaches $79 workpaper offer and persists to ledger
    ph_sub = ingest_playbook_subscription(
        property_id="profithelm",
        tool_slug="section-1031-calculator",
        email="controller@cre-holdings.com",
        calculated_amount=220000,
        leads_ledger_path=leads_path,
        auto_dispatch_email=False,
    )
    assert ph_sub["status"] == "playbook_subscribed"
    assert ph_sub["persisted"] is True
    assert ph_sub["lead_type"] == "playbook_subscription"
    assert ph_sub["offer_sku"] == "ph_1031_boot_replacement_workpapers"
    assert ph_sub["offer_price_usd"] == 79.0
    assert "/api/lead-capture?checkout=1" in ph_sub["checkout_url"]

    # 2. Prexvo Refi Playbook Subscription attaches $39 decision audit offer and persists to ledger
    px_sub = ingest_playbook_subscription(
        property_id="prexvo",
        tool_slug="student-loan-refinance-break-even-calculator",
        email="fellow@medschool-cohort.org",
        calculated_amount=95000,
        leads_ledger_path=leads_path,
        auto_dispatch_email=False,
    )
    assert px_sub["status"] == "playbook_subscribed"
    assert px_sub["persisted"] is True
    assert px_sub["offer_sku"] == "px_refi_amortization_decision_audit"
    assert px_sub["offer_price_usd"] == 39.0
    assert "/api/lead-capture?checkout=1" in px_sub["checkout_url"]

    # 3. Restricted YMYL public-service pages on Prexvo remain strictly blocked from playbook/checkout capture
    with pytest.raises(ValueError, match="Restricted public-service asset"):
        ingest_playbook_subscription(
            property_id="prexvo",
            tool_slug="pslf-qualifying-payment-simulator",
            email="borrower@publicservice.org",
            leads_ledger_path=leads_path,
        )
    with pytest.raises(ValueError, match="Restricted public-service asset"):
        resolve_lead_monetization_offer("prexvo", "ibr-hardship-cap-calculator")

    # 4. Transactional Playbook Email rendering enforces zero forbidden dashes and strict tenant isolation
    ph_email = render_transactional_playbook_email(ph_sub)
    px_email = render_transactional_playbook_email(px_sub)
    assert_no_forbidden_dashes(ph_email["html_body"], context="ph_playbook_email")
    assert_no_forbidden_dashes(px_email["html_body"], context="px_playbook_email")
    assert scanner.scan_text(ph_email["html_body"], "profithelm") == []
    assert scanner.scan_text(px_email["html_body"], "prexvo") == []
    assert "https://profithelm.com/api/lead-capture?checkout=1" in ph_email["html_body"]
    assert "https://prexvo.com/api/lead-capture?checkout=1" in px_email["html_body"]

    # 5. Dry-run responder and programmable Stripe Checkout session payload verification
    dry_disp = dispatch_transactional_playbook(ph_sub, execute_live=False)
    assert dry_disp["status"] == "dry_run_ready"
    assert dry_disp["dispatched"] is False

    stripe_sess = create_stripe_checkout_session(
        property_id="profithelm",
        tool_slug="invoice-factoring-cost-apr-calculator",
        customer_email="cfo@freightlogistics.com",
        lead_id="lead_profithelm_test123",
        execute_live=False,
    )
    assert stripe_sess["offer_sku"] == "ph_commercial_capital_audit_toolkit"
    assert stripe_sess["offer_price_cents"] == 4900
    assert stripe_sess["request_payload"]["metadata[lead_id]"] == "lead_profithelm_test123"
    assert stripe_sess["request_payload"]["line_items[0][price_data][unit_amount]"] == "4900"

    # 6. Lead monitoring summary aggregates across both properties
    mon = get_lead_monitoring_summary(leads_ledger_path=leads_path)
    assert mon["total_leads"] == 2
    assert mon["by_property"]["profithelm"] == 1
    assert mon["by_property"]["prexvo"] == 1
    assert mon["by_lead_type"]["playbook_subscription"] == 2
    assert mon["total_checkout_offer_pipeline_usd"] == 118.0


def test_edge_lead_capture_js_runtime_playbook_and_checkout_readiness(tmp_path):
    import subprocess
    import json

    for prop_id in ("profithelm", "prexvo"):
        fn_dir = tmp_path / prop_id / "functions" / "api"
        fn_dir.mkdir(parents=True)
        fn_file = fn_dir / "lead-capture.js"
        fn_file.write_text(generate_edge_lead_capture_function(prop_id), encoding="utf-8")

        slug = (
            "section-1031-calculator"
            if prop_id == "profithelm"
            else "student-loan-refinance-break-even-calculator"
        )
        node_script = f"""
        import("./functions/api/lead-capture.js").then(async mod => {{
          const kvStore = new Map();
          const mockEnv = {{
            PROFITHELM_LEADS: {{
              put: async (k, v) => kvStore.set(k, JSON.parse(v)),
              list: async ({{ prefix }}) => ({{
                keys: Array.from(kvStore.keys()).filter(k => k.startsWith(prefix)).map(name => ({{ name }}))
              }}),
              get: async (k) => kvStore.get(k) || null
            }},
            PREXVO_LEADS: {{
              put: async (k, v) => kvStore.set(k, JSON.parse(v)),
              list: async ({{ prefix }}) => ({{
                keys: Array.from(kvStore.keys()).filter(k => k.startsWith(prefix)).map(name => ({{ name }}))
              }}),
              get: async (k) => kvStore.get(k) || null
            }}
          }};

          const playbookReq = {{
            url: "https://{prop_id}.com/api/lead-capture",
            headers: new Headers({{ "content-type": "application/json" }}),
            json: async () => ({{ email: "playbook@{prop_id}.com", source: "/tools/{slug}/" }})
          }};
          const pbRes = await mod.onRequestPost({{ request: playbookReq, env: mockEnv }});
          const pbData = await pbRes.json();

          const getReq = {{
            url: "https://{prop_id}.com/api/lead-capture?limit=50",
            headers: new Headers()
          }};
          const getRes = await mod.onRequestGet({{ request: getReq, env: mockEnv }});
          const getData = await getRes.json();

          const checkoutReq = {{
            url: "https://{prop_id}.com/api/lead-capture?checkout=1&lead_id=" + pbData.lead_id,
            headers: new Headers()
          }};
          const coRes = await mod.onRequestGet({{ request: checkoutReq, env: mockEnv }});
          const coData = await coRes.json();

          console.log(JSON.stringify({{
            pbStatus: pbRes.status,
            pbData,
            getCount: getData.count,
            getSummary: getData.summary,
            coStatus: coRes.status,
            coData
          }}));
        }});
        """
        proc = subprocess.run(
            ["node", "-e", node_script],
            cwd=tmp_path / prop_id,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr
        out = json.loads(proc.stdout.strip())
        assert out["pbStatus"] == 200
        assert out["pbData"]["status"] == "playbook_subscribed"
        assert out["pbData"]["persisted"] is True
        assert out["pbData"]["lead_id"].startswith(f"lead_{prop_id}_")
        # No Stripe key in this mock env: the rail must be honestly unavailable, never a fake session.
        assert out["pbData"]["checkout_url"] is None
        assert out["pbData"]["checkout_mode"] == "checkout_unavailable"
        assert out["pbData"]["checkout_session_id"] is None
        assert out["getCount"] == 1
        assert out["getSummary"]["playbook_subscriptions_count"] == 1
        assert out["coStatus"] == 503
        assert out["coData"]["status"] == "checkout_unavailable"
        assert out["coData"]["offer_sku"] == out["pbData"]["offer_sku"]


def test_edge_lead_capture_subsecond_zoho_failover_and_stripe_telemetry(tmp_path):
    import subprocess
    import json
    from pseofactory.partner_tracker import sync_cloudflare_pages_lead_credentials

    dry_pages = sync_cloudflare_pages_lead_credentials(execute_live=False)
    assert "profithelm" in dry_pages["projects"]
    assert "prexvo" in dry_pages["projects"]
    assert "NANGO_SECRET_KEY" in dry_pages["projects"]["profithelm"]["bound_keys"]
    assert "STRIPE_ACCOUNT_ID" in dry_pages["projects"]["prexvo"]["bound_keys"]

    for prop_id in ("profithelm", "prexvo"):
        fn_dir = tmp_path / f"{prop_id}_failover" / "functions" / "api"
        fn_dir.mkdir(parents=True)
        fn_file = fn_dir / "lead-capture.js"
        fn_file.write_text(generate_edge_lead_capture_function(prop_id), encoding="utf-8")

        slug = (
            "section-1031-calculator"
            if prop_id == "profithelm"
            else "student-loan-refinance-break-even-calculator"
        )
        node_script = f"""
        import("./functions/api/lead-capture.js").then(async mod => {{
          const kvStore = new Map();
          globalThis.fetch = async (url, init) => {{
            const u = String(url);
            if (u.includes("api.zeptomail.com")) {{
              return new Response(JSON.stringify({{
                error: {{
                  code: "TM_4001",
                  request_id: "2d6f.mock.zepto.req",
                  details: [{{ code: "SM_111", message: "Sender address not verified" }}]
                }}
              }}), {{ status: 401 }});
            }}
            if (u.includes("api.nango.dev/connection")) {{
              return new Response(JSON.stringify({{
                credentials: {{ access_token: "1000.mock_zoho_oauth_token" }}
              }}), {{ status: 200 }});
            }}
            if (u.includes("mail.zoho.com/api/accounts")) {{
              return new Response(JSON.stringify({{
                status: {{ code: 200 }},
                data: {{ messageId: "177564400999888777", mailId: "177564400999888777" }}
              }}), {{ status: 200 }});
            }}
            if (u.includes("api.stripe.com/v1/checkout/sessions")) {{
              return new Response(JSON.stringify({{
                error: {{ code: "api_key_expired", message: "Expired API Key provided" }}
              }}), {{ status: 401 }});
            }}
            return new Response("{{}}", {{ status: 200 }});
          }};

          const mockEnv = {{
            EMAIL_PRIMARY_RAIL: "zeptomail",
            ZEPTOMAIL_TOKEN: "Zoho-enczapikey mock_token",
            NANGO_SECRET_KEY: "mock_nango_secret",
            NANGO_CONNECTION_ID: "mock_nango_conn",
            ZOHO_MAIL_ACCOUNT_ID: "676891000000008002",
            STRIPE_ACCOUNT_ID: "acct_1T6fSTIq0ckFsf5j",
            STRIPE_PUBLISHABLE_KEY: "pk_live_mock",
            STRIPE_SECRET_KEY: "sk_test_expired",
            PROFITHELM_LEADS: {{
              put: async (k, v) => kvStore.set(k, JSON.parse(v)),
              list: async ({{ prefix }}) => ({{
                keys: Array.from(kvStore.keys()).filter(k => k.startsWith(prefix)).map(name => ({{ name }}))
              }}),
              get: async (k) => kvStore.get(k) || null
            }},
            PREXVO_LEADS: {{
              put: async (k, v) => kvStore.set(k, JSON.parse(v)),
              list: async ({{ prefix }}) => ({{
                keys: Array.from(kvStore.keys()).filter(k => k.startsWith(prefix)).map(name => ({{ name }}))
              }}),
              get: async (k) => kvStore.get(k) || null
            }}
          }};

          const quoteReq = {{
            url: "https://{prop_id}.com/api/lead-capture",
            headers: new Headers({{ "content-type": "application/json" }}),
            json: async () => ({{
              email: "cfo@freightfleet-logistics.com",
              state: "TX",
              calculated_amount: 175000,
              partner_sharing_consent: true,
              tool_slug: "{slug}"
            }})
          }};
          const qRes = await mod.onRequestPost({{ request: quoteReq, env: mockEnv }});
          const qData = await qRes.json();

          const getReq = {{
            url: "https://{prop_id}.com/api/lead-capture?limit=50",
            headers: new Headers()
          }};
          const getRes = await mod.onRequestGet({{ request: getReq, env: mockEnv }});
          const getData = await getRes.json();

          console.log(JSON.stringify({{ qStatus: qRes.status, qData, getSummary: getData.summary }}));
        }});
        """
        proc = subprocess.run(
            ["node", "-e", node_script],
            cwd=tmp_path / f"{prop_id}_failover",
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr
        out = json.loads(proc.stdout.strip())
        assert out["qStatus"] == 200
        assert out["qData"]["zeptomail_dispatched"] is True
        assert out["qData"]["zeptomail_status"] == "sent_edge_zoho_verified_failover"
        assert out["qData"]["zeptomail_http_status"] == 401
        assert out["qData"]["zeptomail_error_code"] == "SM_111"
        assert out["qData"]["zeptomail_request_id"] == "2d6f.mock.zepto.req"
        assert out["qData"]["email_provider"] == "zoho_mail_oauth"
        assert out["qData"]["email_message_id"] == "177564400999888777"
        assert out["qData"]["lifecycle_stage"] == "fulfilled"
        assert out["qData"]["fulfillment_status"] == "dispatched"
        assert out["qData"]["stripe_called"] is True
        assert out["qData"]["stripe_http_status"] == 401
        assert out["qData"]["stripe_error_code"] == "api_key_expired"
        assert out["qData"]["checkout_mode"] == "checkout_unavailable"
        assert out["qData"]["checkout_session_id"] is None
        assert out["getSummary"]["zeptomail_dispatched_count"] == 1
        assert out["getSummary"]["fulfilled_count"] == 1


def test_edge_workers_synthetic_probe_isolation_zero_crm_billing_kv_spam(tmp_path):
    import subprocess
    import json
    from pseofactory.edge import (
        generate_edge_redirect_function,
        generate_edge_telemetry_function,
    )

    for prop_id in ("profithelm", "prexvo"):
        base_dir = tmp_path / f"{prop_id}_synthetic"
        (base_dir / "functions" / "api").mkdir(parents=True)
        (base_dir / "functions" / "r").mkdir(parents=True)
        (base_dir / "functions" / "api" / "lead-capture.js").write_text(
            generate_edge_lead_capture_function(prop_id), encoding="utf-8"
        )
        (base_dir / "functions" / "api" / "telemetry.js").write_text(
            generate_edge_telemetry_function(prop_id), encoding="utf-8"
        )
        (base_dir / "functions" / "r" / "partner.js").write_text(
            generate_edge_redirect_function(prop_id), encoding="utf-8"
        )

        slug = (
            "section-1031-calculator"
            if prop_id == "profithelm"
            else "student-loan-refinance-break-even-calculator"
        )
        partner_key = "ipx1031" if prop_id == "profithelm" else "splash_financial"
        node_script = f"""
        Promise.all([
          import("./functions/api/lead-capture.js"),
          import("./functions/api/telemetry.js"),
          import("./functions/r/partner.js")
        ]).then(async ([leadMod, telMod, redirMod]) => {{
          const kvStore = new Map();
          let externalFetchCount = 0;
          globalThis.fetch = async () => {{
            externalFetchCount += 1;
            return new Response("{{}}", {{ status: 200 }});
          }};

          const mockKv = {{
            put: async (k, v) => kvStore.set(k, v),
            list: async () => ({{ keys: [] }}),
            get: async () => null
          }};
          const mockEnv = {{
            ZEPTOMAIL_TOKEN: "Zoho-enczapikey live_token",
            NANGO_SECRET_KEY: "live_nango_secret",
            STRIPE_SECRET_KEY: "sk_live_secret",
            PROFITHELM_LEADS: mockKv,
            PREXVO_LEADS: mockKv,
            PROFITHELM_TELEMETRY_KV: mockKv,
            PREXVO_TELEMETRY_KV: mockKv,
            PROFITHELM_CLICK_LEDGER: mockKv,
            PREXVO_CLICK_LEDGER: mockKv
          }};

          const quoteReq = {{
            url: "https://{prop_id}.com/api/lead-capture",
            headers: new Headers({{
              "content-type": "application/json",
              "x-pseofactory-test": "1"
            }}),
            json: async () => ({{
              email: "probe@synthetic.pseofactory.test",
              state: "NY",
              calculated_amount: 185000,
              partner_sharing_consent: true,
              tool_slug: "{slug}",
              synthetic_test: true
            }})
          }};
          const qRes = await leadMod.onRequestPost({{ request: quoteReq, env: mockEnv }});
          const qData = await qRes.json();

          const coReq = {{
            url: "https://{prop_id}.com/api/lead-capture?checkout=1&tool_slug={slug}&synthetic_test=1",
            headers: new Headers({{ "x-pseofactory-test": "1" }})
          }};
          const coRes = await leadMod.onRequestGet({{ request: coReq, env: mockEnv }});
          const coData = await coRes.json();

          const telReq = {{
            url: "https://{prop_id}.com/api/telemetry?synthetic_test=1",
            headers: new Headers({{
              "content-type": "application/json",
              "x-pseofactory-test": "1"
            }}),
            json: async () => ({{
              schema_version: "2.0",
              event_type: "synthetic_e2e_probe",
              slug: "{slug}",
              synthetic_test: true
            }})
          }};
          const telRes = await telMod.onRequestPost({{ request: telReq, env: mockEnv }});
          const telData = await telRes.json();

          const redirReq = {{
            url: "https://{prop_id}.com/r/{partner_key}?source_tool={slug}&synthetic_test=1",
            headers: new Headers({{ "x-pseofactory-test": "1" }})
          }};
          const redirFn = redirMod.onRequestGet || redirMod.onRequest;
          const redirRes = await redirFn({{
            request: redirReq,
            env: mockEnv,
            params: {{ partner: "{partner_key}" }}
          }});

          console.log(JSON.stringify({{
            kvSize: kvStore.size,
            externalFetchCount,
            qHeader: qRes.headers.get("X-Edge-Synthetic-Test"),
            qData,
            coData,
            telHeader: telRes.headers.get("X-Edge-Synthetic-Test"),
            telData,
            redirStatus: redirRes.status,
            redirHeader: redirRes.headers.get("X-Edge-Synthetic-Test"),
            redirPartner: redirRes.headers.get("X-Edge-Partner")
          }}));
        }});
        """
        proc = subprocess.run(
            ["node", "-e", node_script],
            cwd=base_dir,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr
        out = json.loads(proc.stdout.strip())
        assert out["kvSize"] == 0
        assert out["externalFetchCount"] == 0
        assert out["qHeader"] == "1"
        assert out["qData"]["persisted"] is False
        assert out["qData"]["synthetic_test"] is True
        assert out["qData"]["zeptomail_status"] == "synthetic_test_suppressed"
        assert out["qData"]["checkout_mode"] == "checkout_unavailable"
        assert out["qData"]["stripe_called"] is False
        assert out["coData"]["status"] == "checkout_unavailable"
        assert out["coData"]["checkout_mode"] == "checkout_unavailable"
        assert out["coData"]["synthetic_test"] is True
        assert out["telHeader"] == "1"
        assert out["telData"]["status"] == "RECORDED"
        assert out["telData"]["persisted"] is False
        assert out["telData"]["synthetic_test"] is True
        assert out["redirStatus"] == 302
        assert out["redirHeader"] == "1"
        assert out["redirPartner"] == partner_key


def test_real_browser_e2e_interactive_surface_across_profithelm_and_prexvo(tmp_path):
    from pseofactory.browser_verifier import UnifiedBrowserAuditor
    from pseofactory.server import EphemeralDistServer

    auditor = UnifiedBrowserAuditor(dist_dir=tmp_path)
    reachable, msg = auditor.check_cdp_reachability()
    if not reachable:
        pytest.skip(f"Chrome CDP unreachable: {msg}")

    specs = [
        {
            "slug": "section-1031-calculator",
            "title": "1031 Exchange Tax Deferral & Boot Calculator",
            "model_name": "1031 Exchange Tax Deferral Model",
            "property_id": "profithelm",
            "canonical_base": "https://profithelm.com",
            "formula": "gross_amount * (1.0 - effective_rate)",
            "inputs": {"gross_amount": 450000.0, "effective_rate": 0.24},
            "published_output": 342000.0,
            "sample_calculation": "Evaluating $450,000 relinquished exchange equity at 24% effective tax rate yields $342,000.00 net retained basis.",
            "statutory_authority": "IRC Section 1031 and IRS Form 8824",
            "economic_dataset": "BEA Fixed Assets Series",
        },
        {
            "slug": "student-loan-refinance-break-even-calculator",
            "title": "Student Loan Refinance Break-Even Calculator",
            "model_name": "Student Loan Refinance Break-Even Model",
            "property_id": "prexvo",
            "canonical_base": "https://prexvo.com",
            "formula": "gross_amount * (1.0 - effective_rate)",
            "inputs": {"gross_amount": 85000.0, "effective_rate": 0.06},
            "published_output": 79900.0,
            "sample_calculation": "Evaluating $85,000 loan balance at 6% rate factor yields $79,900.00 baseline output.",
            "statutory_authority": "Higher Education Act Title IV (20 U.S.C. 1070 et seq.); 34 CFR Part 685",
            "economic_dataset": "Federal Reserve G.19 Consumer Credit Series",
        },
        {
            "slug": "soc-2-audit-cost-calculator",
            "title": "SOC 2 Type II Audit Cost & GRC Readiness Calculator",
            "model_name": "SOC 2 Audit Cost Model",
            "property_id": "gainhelm",
            "canonical_base": "https://gainhelm.com",
            "formula": "gross_amount * (1.0 - effective_rate)",
            "inputs": {"gross_amount": 65000.0, "effective_rate": 0.15},
            "published_output": 55250.0,
            "sample_calculation": "Evaluating $65,000 SOC 2 readiness scope at 15% automation savings factor yields $55,250.00 net audit cost.",
            "statutory_authority": "32 CFR Part 170 and AICPA SSAE 18 (AT-C Section 205)",
            "economic_dataset": "BLS Occupational Employment and Wages Series",
        },
    ]

    for spec in specs:
        prop_id = spec["property_id"]
        slug = spec["slug"]
        dist_dir = tmp_path / prop_id / "dist"
        tool_dir = dist_dir / "tools" / slug
        tool_dir.mkdir(parents=True, exist_ok=True)
        compiled = compile_high_effort_page(spec)
        html_str = compiled["html"]
        if 'id="lead-capture-form"' not in html_str:
            footer_form = (
                '<form id="lead-capture-form" class="lead-capture-form">'
                '<input type="email" name="email" placeholder="Enter work email" required>'
                '<button type="submit">Send Playbook</button>'
                '</form></body>'
            )
            html_str = html_str.replace("</body>", footer_form)
        (tool_dir / "index.html").write_text(html_str, encoding="utf-8")
        (dist_dir / "index.html").write_text(html_str, encoding="utf-8")

        with EphemeralDistServer(dist_dir) as server:
            prop_auditor = UnifiedBrowserAuditor(dist_dir=dist_dir)
            route = f"/tools/{slug}/"
            report = prop_auditor.audit_interactive_surface(server.base_url, route)
            assert report["passed"] is True, f"Interactive audit failed for {prop_id}: {report}"
            assert report["console_errors"] == []
            assert report["page_errors"] == []
            assert report["links_audit"]["invalid_links"] == []
            assert report["links_audit"]["unrouted_affiliate_links"] == []
            assert report["deep_link_hydration"]["tested"] is True
            assert report["deep_link_hydration"]["passed"] is True
            assert report["calculator_and_presets"]["tested"] is True
            assert report["calculator_and_presets"]["passed"] is True
            assert report["cliff_visualizer"]["present"] is True
            assert report["cliff_visualizer"]["passed"] is True
            assert report["scenario_comparator"]["present"] is True
            assert report["scenario_comparator"]["passed"] is True
            assert report["blueprint_actions"]["present"] is True
            assert report["blueprint_actions"]["passed"] is True
            assert report["post_calc_upgrade_drawer"]["present"] is True
            assert report["post_calc_upgrade_drawer"]["passed"] is True
            assert report["post_calc_upgrade_drawer"]["preview_rendered"] is True
            assert report["post_calc_upgrade_drawer"]["datapack_download_triggered"] is True
            assert report["playbook_lead_capture_and_checkout"]["present"] is True
            assert report["playbook_lead_capture_and_checkout"]["passed"] is True
            assert report["partner_quote_intake_and_checkout"]["present"] is True
            assert report["partner_quote_intake_and_checkout"]["passed"] is True
            assert report["focus_and_keyboard_navigation"]["passed"] is True
            assert report["focus_and_keyboard_navigation"]["skip_link_valid"] is True
            assert report["focus_and_keyboard_navigation"]["zero_outline_failures"] == []
            assert report["affiliate_redirect_and_telemetry"]["tested"] is True
            assert report["affiliate_redirect_and_telemetry"]["passed"] is True
            assert report["affiliate_redirect_and_telemetry"]["dom_click_handled"] is True

            assert len(server.captured_leads) >= 2
            assert len(server.checkout_sessions) >= 2
            assert len(server.telemetry_events) >= 1
            assert len(server.redirect_events) >= 1

    # Also verify real compiled tenant routes across profithelm-platform (156), prexvo (25), and gainhelm (15)
    from pathlib import Path
    from pseofactory.browser_verifier import RouteManifestExtractor
    from pseofactory.visual_primitives import normalize_html_visual_primitives

    tenant_Matrix = [
        ("profithelm", Path("/home/ubuntuadmin/projects/profithelm-platform/dist"), 156, [
            "index.html",
            "tools/section-179-calculator/index.html",
            "tools/crypto-tax-calculator/index.html",
        ]),
        ("prexvo", Path("/home/ubuntuadmin/projects/prexvo/dist"), 25, [
            "index.html",
            "tools/student-loan-repayment-calculator/index.html",
        ]),
        ("gainhelm", Path("/home/ubuntuadmin/projects/gainhelm/dist"), 15, [
            "index.html",
            "tools/soc-2-audit-cost-calculator/index.html",
            "tools/cmmc-2-0-compliance-cost-calculator/index.html",
        ]),
    ]
    for prop_id, real_dist, expected_min_routes, sample_rel_files in tenant_Matrix:
        if not real_dist.is_dir():
            continue
        real_routes = RouteManifestExtractor(real_dist).extract_routes()
        assert len(real_routes) >= expected_min_routes, f"{prop_id} expected >={expected_min_routes} routes, got {len(real_routes)}"
        real_sample_dist = tmp_path / f"real_{prop_id}" / "dist"
        real_sample_dist.mkdir(parents=True, exist_ok=True)
        for rel_f in sample_rel_files:
            src_f = real_dist / rel_f
            if src_f.is_file():
                dst_f = real_sample_dist / rel_f
                dst_f.parent.mkdir(parents=True, exist_ok=True)
                norm_h, _ = normalize_html_visual_primitives(src_f.read_text(encoding="utf-8"), is_tenant_porcelain=True)
                dst_f.write_text(norm_h, encoding="utf-8")
        real_auditor = UnifiedBrowserAuditor(dist_dir=real_dist, property_id=prop_id, fail_closed=True)
        with EphemeralDistServer(real_sample_dist, property_id=prop_id) as real_srv:
            for rel_f in sample_rel_files:
                route_path = "/" if rel_f == "index.html" else "/" + rel_f[: -len("index.html")]
                finding = real_auditor.audit_route(real_srv.base_url, route_path)
                assert finding["cls_value"] == 0.0
                assert finding["widget_failures"] == [], f"Widget failures on {prop_id} {route_path}: {finding['widget_failures']}"
                assert finding["interactive_surface"]["passed"] is True, f"Interactive surface failed on {prop_id} {route_path}: {finding['interactive_surface']}"
                assert finding["interactive_surface"]["focus_and_keyboard_navigation"]["passed"] is True
                assert finding["interactive_surface"]["calculator_and_presets"]["button_failures"] == []
                assert finding["interactive_surface"]["calculator_and_presets"]["input_failures"] == []
                assert finding["interactive_surface"]["links_audit"]["invalid_links"] == []


def test_personalized_audit_workpaper_synthesis_across_all_skus():
    from pseofactory.partner_tracker import (
        assert_no_forbidden_dashes,
        synthesize_personalized_audit_workpaper,
    )

    cases = [
        (
            "profithelm",
            "section-1031-calculator",
            {
                "lead_id": "lead_profithelm_1031_wp",
                "calculated_amount": 420000.0,
                "state": "CA",
                "email": "investor@pacific-industrial.com",
                "scenario_inputs": {"relinquished_price": 420000, "replacement_price": 480000},
                "scenario_outputs": {"primary": "$319,200"},
            },
            "ph_1031_boot_replacement_workpapers",
            79.0,
        ),
        (
            "profithelm",
            "freight-invoice-factoring-cost-calculator",
            {
                "lead_id": "lead_profithelm_cap_wp",
                "calculated_amount": 180000.0,
                "state": "TX",
                "email": "fleet@freightfleet-logistics.com",
                "scenario_inputs": {"invoice_volume": 180000, "advance_rate": 90},
                "scenario_outputs": {"primary": "$162,000"},
            },
            "ph_commercial_capital_audit_toolkit",
            49.0,
        ),
        (
            "profithelm",
            "california-s-corp-reasonable-compensation-tax-calculator",
            {
                "lead_id": "lead_profithelm_tax_wp",
                "calculated_amount": 260000.0,
                "state": "CA",
                "email": "cpa@pacific-industrial.com",
                "scenario_inputs": {"net_business_income": 260000},
                "scenario_outputs": {"primary": "$198,000"},
            },
            "ph_statutory_tax_audit_workpapers",
            49.0,
        ),
        (
            "prexvo",
            "student-loan-refinance-break-even-calculator",
            {
                "lead_id": "lead_prexvo_refi_wp",
                "calculated_amount": 115000.0,
                "state": "NY",
                "email": "resident@metro-health.org",
                "scenario_inputs": {"loan_balance": 115000, "current_rate": 7.2, "refi_rate": 4.8, "term_years": 10},
                "scenario_outputs": {"primary": "$18,420"},
            },
            "px_refi_amortization_decision_audit",
            39.0,
        ),
    ]

    for prop_id, slug, rec, expected_sku, expected_price in cases:
        for mode in ("free_playbook", "paid_toolkit"):
            wp = synthesize_personalized_audit_workpaper(
                property_id=prop_id,
                tool_slug=slug,
                lead_record=rec,
                mode=mode,
            )
            assert wp["offer_sku"] == expected_sku
            assert wp["offer_price_usd"] == expected_price
            assert wp["calculated_amount"] == rec["calculated_amount"]
            assert len(wp["reconciliation_schedule"]) >= 4
            assert len(wp["sensitivity_matrix"]) >= 3
            assert len(wp["deliverables"]) >= 4
            assert wp["playbook_url"].startswith("/api/lead-capture?playbook=1")
            assert wp["fulfillment_url"].startswith("/api/lead-capture?fulfill=1")
            assert wp["csv_fulfillment_url"].endswith("&format=csv")
            assert "Line Code,Statutory Line Item" in wp["csv_content"]
            assert "<!DOCTYPE html>" in wp["html_report"]
            assert rec["lead_id"] in wp["html_report"]
            assert_no_forbidden_dashes(wp["html_report"], context=f"{prop_id}:{slug}:{mode}:html")
            assert_no_forbidden_dashes(wp["csv_content"], context=f"{prop_id}:{slug}:{mode}:csv")


def test_edge_lead_capture_playbook_and_fulfillment_value_ladder(tmp_path):
    import json
    import subprocess

    for prop_id, slug in [
        ("profithelm", "section-1031-calculator"),
        ("prexvo", "student-loan-refinance-break-even-calculator"),
    ]:
        js_code = generate_edge_lead_capture_function(prop_id)
        mod_path = tmp_path / f"lead_ladder_{prop_id}.mjs"
        mod_path.write_text(js_code, encoding="utf-8")

        runner = f"""
import {{ onRequestPost, onRequestGet }} from {json.dumps(str(mod_path))};
{STRIPE_PAID_MOCK_JS}
const env = {{ STRIPE_SECRET_KEY: "sk_live_mock" }};
const pbReq = new Request("https://{prop_id}.com/api/lead-capture", {{
  method: "POST",
  headers: {{ "Content-Type": "application/json", "X-Pseofactory-Test": "1" }},
  body: JSON.stringify({{
    email: "ladder-probe@synthetic.pseofactory.test",
    tool_slug: {json.dumps(slug)},
    scenario_amount: 175000,
    scenario_inputs: {{ gross_amount: 175000, rate: 6.5 }},
    scenario_outputs: {{ primary: "$142,500" }},
    blueprint_state: {{
      slug: {json.dumps(slug)},
      calculated_amount: 175000,
      inputs: {{ gross_amount: 175000, rate: 6.5 }},
      outputs: {{ primary: "$142,500" }}
    }},
    synthetic_test: true
  }})
}});
const pbRes = await onRequestPost({{ request: pbReq, env }});
const pbData = await pbRes.json();

const playJsonReq = new Request("https://{prop_id}.com" + pbData.playbook_url + "&synthetic_test=1", {{
  method: "GET",
  headers: {{ "X-Pseofactory-Test": "1" }}
}});
const playJsonRes = await onRequestGet({{ request: playJsonReq, env }});
const playJsonData = await playJsonRes.json();

const fulfillHtmlReq = new Request("https://{prop_id}.com" + pbData.fulfillment_url + "&session_id=cs_live_PAIDFOR_" + pbData.lead_id + "&format=html&synthetic_test=1", {{
  method: "GET",
  headers: {{ "X-Pseofactory-Test": "1" }}
}});
const fulfillHtmlRes = await onRequestGet({{ request: fulfillHtmlReq, env }});
const fulfillHtmlText = await fulfillHtmlRes.text();

const fulfillCsvReq = new Request("https://{prop_id}.com" + pbData.csv_fulfillment_url + "&session_id=cs_live_PAIDFOR_" + pbData.lead_id + "&synthetic_test=1", {{
  method: "GET",
  headers: {{ "X-Pseofactory-Test": "1" }}
}});
const fulfillCsvRes = await onRequestGet({{ request: fulfillCsvReq, env }});
const fulfillCsvText = await fulfillCsvRes.text();

console.log(JSON.stringify({{
  pbData,
  playJsonData,
  fulfillHtmlStatus: fulfillHtmlRes.status,
  fulfillHtmlType: fulfillHtmlRes.headers.get("content-type"),
  fulfillHtmlHasTable: fulfillHtmlText.includes("<table") && fulfillHtmlText.includes(pbData.lead_id),
  fulfillCsvStatus: fulfillCsvRes.status,
  fulfillCsvType: fulfillCsvRes.headers.get("content-type"),
  fulfillCsvHasHeader: fulfillCsvText.includes("Line Code,Statutory Line Item"),
}}));
"""
        runner_path = tmp_path / f"run_ladder_{prop_id}.mjs"
        runner_path.write_text(runner, encoding="utf-8")
        proc = subprocess.run(["node", str(runner_path)], capture_output=True, text=True, check=True)
        out = json.loads(proc.stdout.strip().splitlines()[-1])

        assert out["pbData"]["ok"] is True
        assert out["pbData"]["status"] == "playbook_subscribed"
        assert out["pbData"]["calculated_amount"] == 175000
        assert out["pbData"]["capital_band"] == "100k_250k"
        assert out["pbData"]["playbook_url"].startswith("/api/lead-capture?playbook=1")
        assert out["pbData"]["fulfillment_url"].startswith("/api/lead-capture?fulfill=1")
        assert out["pbData"]["csv_fulfillment_url"].endswith("&format=csv")
        assert len(out["pbData"]["reconciliation_schedule"]) >= 4
        assert out["playJsonData"]["ok"] is True
        assert out["playJsonData"]["status"] == "playbook_ready"
        assert out["fulfillHtmlStatus"] == 200
        assert "text/html" in out["fulfillHtmlType"]
        assert out["fulfillHtmlHasTable"] is True
        assert out["fulfillCsvStatus"] == 200
        assert "text/csv" in out["fulfillCsvType"]
        assert out["fulfillCsvHasHeader"] is True


def test_trend_mined_statutory_timeseries_and_three_rail_monetization(tmp_path):
    import json
    import subprocess
    from pseofactory.affiliates import qualify_monetization_opportunity
    from pseofactory.partner_tracker import (
        _fetch_zoho_access_token_from_nango,
        _read_stripe_cli_credentials,
        diagnose_stripe_merchant_readiness,
        sync_cloudflare_pages_lead_credentials,
        synthesize_personalized_audit_workpaper,
    )

    cli_creds = _read_stripe_cli_credentials()
    assert cli_creds["account_id"] == "acct_1T6fSTIq0ckFsf5j"
    assert callable(_fetch_zoho_access_token_from_nango)
    cf_dry = sync_cloudflare_pages_lead_credentials(execute_live=False)
    assert "STRIPE_SECRET_KEY" in cf_dry["projects"]["profithelm"]["bound_keys"]
    assert "STRIPE_SECRET_KEY" in cf_dry["projects"]["prexvo"]["bound_keys"]

    stripe_diag = diagnose_stripe_merchant_readiness(execute_live=False)
    assert stripe_diag["stripe_account_id"] == "acct_1T6fSTIq0ckFsf5j"
    assert stripe_diag["merchant_email"] == "arif.coskun@profithelm.com"
    assert stripe_diag["display_name"] == "CoachOS"
    assert stripe_diag["product_count"] >= 4
    assert "ph_1031_boot_replacement_workpapers" in stripe_diag["product_skus"]
    assert "px_refi_amortization_decision_audit" in stripe_diag["product_skus"]
    assert stripe_diag["bank_payout_settlement"]["charges_enabled"] is True
    assert stripe_diag["bank_payout_settlement"]["payouts_enabled"] is True
    assert stripe_diag["bank_payout_settlement"]["bank_name"] == "MERCURY, PARTNERING WITH CHOICE BANK"
    assert stripe_diag["bank_payout_settlement"]["routing_number"] == "091311229"
    assert stripe_diag["bank_payout_settlement"]["account_last4"] == "1395"
    assert stripe_diag["bank_payout_settlement"]["webhook_url"] == "https://api.thecoachloop.com/api/webhooks/stripe"

    q_1031 = qualify_monetization_opportunity(
        "section 1031 exchange boot calculator",
        slug="section-1031-calculator",
        property_id="profithelm",
        search_volume=1000,
    )
    assert q_1031["monetization_rail_mix"] == "three_rail_b2b_quote_stripe_asset_and_affiliate"
    assert q_1031["stripe_digital_asset"]["eligible"] is True
    assert q_1031["stripe_digital_asset"]["offer_sku"] == "ph_1031_boot_replacement_workpapers"
    assert q_1031["stripe_digital_asset"]["offer_price_usd"] == 79.0
    assert q_1031["b2b_quote_intake"]["eligible"] is True
    assert q_1031["estimated_stripe_asset_monthly_revenue_usd"] > 0
    assert q_1031["total_compounded_monthly_revenue_usd"] > q_1031["estimated_monthly_revenue_usd"]

    q_pslf = qualify_monetization_opportunity(
        "pslf qualifying payment simulator",
        slug="pslf-qualifying-payment-simulator",
        property_id="prexvo",
        search_volume=1000,
    )
    assert q_pslf["monetization_rail_mix"] == "public_service_non_commercial"
    assert q_pslf["stripe_digital_asset"]["eligible"] is False
    assert q_pslf["b2b_quote_intake"]["eligible"] is False
    assert q_pslf["estimated_stripe_asset_monthly_revenue_usd"] == 0.0

    for prop_id, slug, expected_series_id in [
        ("profithelm", "section-1031-calculator", "fred_dgs10_yield"),
        ("profithelm", "section-179-depreciation-calculator", "irs_sec179_cap"),
        ("profithelm", "california-s-corp-reasonable-salary-tax-savings-calculator", "irs_sec199a_qbi"),
        ("prexvo", "student-loan-refinance-break-even-calculator", "ed_direct_undergrad_rate"),
    ]:
        wp = synthesize_personalized_audit_workpaper(
            property_id=prop_id,
            tool_slug=slug,
            lead_record={
                "lead_id": f"lead_{prop_id}_trend",
                "calculated_amount": 320000,
                "state": "CA",
                "scenario_inputs": {"custom_balance": 320000, "rate_pct": 5.25},
                "scenario_outputs": {"primary": "$48,200"},
            },
            mode="paid_toolkit",
        )
        ts_list = wp["statutory_trend_timeseries"]
        assert len(ts_list) >= 3
        series_ids = {row["series_id"] for row in ts_list}
        assert expected_series_id in series_ids
        for row in ts_list:
            pts = row.get("points") or {}
            assert "2024" in pts
            assert "2026" in pts
            assert "2030" in pts
        assert wp["custom_parameter_ledger"]["calculated_amount"] == 320000
        assert wp["custom_parameter_ledger"]["inputs"]["custom_balance"] == 320000
        assert f"TREND-{expected_series_id}" in wp["csv_content"]
        assert "Multi-Year Statutory &amp; Macroeconomic Trend Benchmarks (2024 to 2030)" in wp["html_report"]

        js_code = generate_edge_lead_capture_function(prop_id)
        mod_path = tmp_path / f"edge_trend_{prop_id}_{slug[:12]}.mjs"
        mod_path.write_text(js_code, encoding="utf-8")
        runner = f"""
import {{ onRequestGet }} from {json.dumps(str(mod_path))};
{STRIPE_PAID_MOCK_JS}
const env = {{ STRIPE_SECRET_KEY: "sk_live_mock" }};
const inputsParam = encodeURIComponent(JSON.stringify({{ custom_amount: 410000, custom_rate: 5.4 }}));
const chkReq = new Request("https://{prop_id}.com/api/lead-capture?checkout=1&lead_id=lead_custom_1&tool_slug={slug}&amount=410000&inputs_json=" + inputsParam + "&synthetic_test=1", {{
  method: "GET",
  headers: {{ "X-Pseofactory-Test": "1" }}
}});
const chkRes = await onRequestGet({{ request: chkReq, env }});
const chkData = await chkRes.json();

const ffReq = new Request("https://{prop_id}.com/api/lead-capture?fulfill=1&lead_id=lead_custom_1&session_id=cs_live_PAIDFOR_lead_custom_1&source={slug}&amount=410000&inputs_json=" + inputsParam + "&synthetic_test=1", {{
  method: "GET",
  headers: {{ "X-Pseofactory-Test": "1" }}
}});
const ffRes = await onRequestGet({{ request: ffReq, env }});
const ffData = await ffRes.json();
console.log(JSON.stringify({{ chkData, ffData }}));
"""
        runner_path = tmp_path / f"run_trend_{prop_id}_{slug[:12]}.mjs"
        runner_path.write_text(runner, encoding="utf-8")
        proc = subprocess.run(["node", str(runner_path)], capture_output=True, text=True, check=True)
        out = json.loads(proc.stdout.strip().splitlines()[-1])
        # Synthetic probes never reach Stripe, so the rail is honestly unavailable (not "ready").
        assert out["chkData"]["ok"] is False
        assert out["chkData"]["status"] == "checkout_unavailable"
        assert out["chkData"]["stripe_account_id"] == "acct_1T6fSTIq0ckFsf5j"
        expected_merchant_email = f"arif.coskun@{prop_id}.com"
        assert out["chkData"]["stripe_merchant_email"] == expected_merchant_email
        assert out["chkData"]["reservation_captured"] is True
        assert out["chkData"]["reservation_id"] == "rsv_lead_custom_1"
        assert out["chkData"]["diagnostic_telemetry"]["merchant_email"] == expected_merchant_email
        assert out["chkData"]["calculated_amount"] == 410000
        assert out["chkData"]["statutory_trend_series_count"] >= 3
        assert out["ffData"]["ok"] is True
        assert out["ffData"]["calculated_amount"] == 410000
        assert len(out["ffData"]["statutory_trend_timeseries"]) >= 3
        assert out["ffData"]["custom_parameter_ledger"]["calculated_amount"] == 410000
        assert out["ffData"]["custom_parameter_ledger"]["inputs"]["custom_amount"] == 410000
        assert f"TREND-{expected_series_id}" in out["ffData"]["csv_content"]


def test_post_purchase_return_urls_direct_sku_routing_and_autonomous_audit(tmp_path):
    """
    Verifies:
    1. Prexvo and ProfitHelm post-purchase return URLs (success_url / cancel_url) resolve to
       canonical /tools/<slug>/ routes (not 404 root /<slug>/ routes on Prexvo).
    2. Direct ?sku=<sku> requests on /api/lead-capture?checkout=1 and ?fulfill=1 resolve the
       exact requested SKU ($79 1031, $49 commercial capital, $49 statutory tax, $39 Prexvo refi)
       even when tool_slug is omitted, and section-301-tariff-landed-cost-calculator maps to
       ph_commercial_capital_audit_toolkit.
    3. Autonomous end-to-end monetization and fulfillment self-audit verifies all 4 sellable SKUs,
       Mercury bank settlement, YMYL public-service isolation, and outbound affiliate attribution.
    """
    import subprocess
    import json
    from pseofactory.partner_tracker import (
        resolve_lead_monetization_offer,
        synthesize_personalized_audit_workpaper,
    )

    px_offer = resolve_lead_monetization_offer(
        property_id="prexvo",
        tool_slug="student-loan-refinance-break-even-calculator",
        lead_id="lead_prexvo_return_test",
    )
    assert px_offer["success_url"].startswith(
        "https://prexvo.com/tools/student-loan-refinance-break-even-calculator/?checkout_status=success"
    )
    assert px_offer["cancel_url"].startswith(
        "https://prexvo.com/tools/student-loan-refinance-break-even-calculator/?checkout_status=cancelled"
    )

    tariff_offer = resolve_lead_monetization_offer(
        property_id="profithelm",
        tool_slug="section-301-tariff-landed-cost-calculator",
        lead_id="lead_ph_tariff",
    )
    assert tariff_offer["offer_sku"] == "ph_commercial_capital_audit_toolkit"
    assert tariff_offer["offer_price_usd"] == 49.0

    for sku, expected_price in [
        ("ph_1031_boot_replacement_workpapers", 79.0),
        ("ph_commercial_capital_audit_toolkit", 49.0),
        ("ph_statutory_tax_audit_workpapers", 49.0),
    ]:
        direct_offer = resolve_lead_monetization_offer(
            property_id="profithelm",
            tool_slug="general",
            sku=sku,
            lead_id=f"lead_sku_{sku[:10]}",
        )
        assert direct_offer["offer_sku"] == sku
        assert direct_offer["offer_price_usd"] == expected_price
        assert "/tools/" in direct_offer["success_url"]

        wp_direct = synthesize_personalized_audit_workpaper(
            property_id="profithelm",
            tool_slug="general",
            lead_record={"lead_id": f"lead_wp_{sku[:10]}", "offer_sku": sku},
            mode="paid_toolkit",
        )
        assert wp_direct["offer_sku"] == sku
        assert wp_direct["offer_price_usd"] == expected_price

    ph_js = generate_edge_lead_capture_function("profithelm")
    px_js = generate_edge_lead_capture_function("prexvo")
    ph_mod = tmp_path / "ph_lead_capture.mjs"
    px_mod = tmp_path / "px_lead_capture.mjs"
    ph_mod.write_text(ph_js, encoding="utf-8")
    px_mod.write_text(px_js, encoding="utf-8")

    runner = f"""
import * as phMod from {json.dumps(str(ph_mod))};
import * as pxMod from {json.dumps(str(px_mod))};
{STRIPE_PAID_MOCK_JS}
const env = {{ STRIPE_SECRET_KEY: "sk_live_mock" }};
const capChk = await (await phMod.onRequestGet({{
  request: new Request("https://profithelm.com/api/lead-capture?checkout=1&sku=ph_commercial_capital_audit_toolkit&synthetic_test=1"),
  env
}})).json();
const taxChk = await (await phMod.onRequestGet({{
  request: new Request("https://profithelm.com/api/lead-capture?checkout=1&sku=ph_statutory_tax_audit_workpapers&synthetic_test=1"),
  env
}})).json();
const capFf = await (await phMod.onRequestGet({{
  request: new Request("https://profithelm.com/api/lead-capture?fulfill=1&lead_id=lead_sku_cap&session_id=cs_live_PAIDFOR_lead_sku_cap&sku=ph_commercial_capital_audit_toolkit&synthetic_test=1"),
  env
}})).json();
const pxChk = await (await pxMod.onRequestGet({{
  request: new Request("https://prexvo.com/api/lead-capture?checkout=1&sku=px_refi_amortization_decision_audit&synthetic_test=1"),
  env
}})).json();
console.log(JSON.stringify({{ capChk, taxChk, capFf, pxChk }}));
"""
    runner_path = tmp_path / "run_sku_routing.mjs"
    runner_path.write_text(runner, encoding="utf-8")
    proc = subprocess.run(["node", str(runner_path)], capture_output=True, text=True, check=True)
    res = json.loads(proc.stdout.strip().splitlines()[-1])
    assert res["capChk"]["offer_sku"] == "ph_commercial_capital_audit_toolkit"
    assert res["capChk"]["offer_price_usd"] == 49
    assert res["capChk"]["success_url"].startswith("https://profithelm.com/tools/")
    assert res["taxChk"]["offer_sku"] == "ph_statutory_tax_audit_workpapers"
    assert res["taxChk"]["offer_price_usd"] == 49
    assert res["capFf"]["offer_sku"] == "ph_commercial_capital_audit_toolkit"
    assert res["pxChk"]["offer_sku"] == "px_refi_amortization_decision_audit"
    assert res["pxChk"]["success_url"].startswith("https://prexvo.com/tools/")

    from pseofactory.partner_tracker import audit_end_to_end_monetization_and_fulfillment
    audit_rep = audit_end_to_end_monetization_and_fulfillment(execute_live=False)
    assert audit_rep["status"] == "PASS"
    assert audit_rep["stripe_and_mercury_settlement"]["bank_routing_number"] == "091311229"
    assert audit_rep["stripe_and_mercury_settlement"]["bank_account_last4"] == "1395"
    assert len(audit_rep["catalog_skus"]) == 6
    assert all(item["checkout_ready"] and item["fulfillment_ready"] for item in audit_rep["catalog_skus"].values())
    assert audit_rep["ymyl_public_service_isolation"]["isolated"] is True
    assert audit_rep["outbound_affiliate_attribution"]["profithelm"]["total_routes"] == 22
    assert audit_rep["outbound_affiliate_attribution"]["prexvo"]["total_routes"] == 5







def test_edge_email_defaults_to_verified_zoho_rail_without_zeptomail_roundtrip(tmp_path):
    """ZeptoMail returns SM_111 (sender domain not verified in the agent) on every lead, so the
    verified Zoho OAuth (Nango) rail is primary and ZeptoMail is never called on the hot path."""
    import json
    import subprocess

    for prop_id, slug in (
        ("profithelm", "section-1031-calculator"),
        ("prexvo", "student-loan-refinance-break-even-calculator"),
    ):
        mod = tmp_path / f"email_primary_{prop_id}.mjs"
        mod.write_text(generate_edge_lead_capture_function(prop_id), encoding="utf-8")
        runner = f"""
import {{ onRequestPost }} from {json.dumps(str(mod))};
let zeptoCalls = 0;
globalThis.fetch = async (url) => {{
  const u = String(url);
  if (u.includes("api.zeptomail.com")) {{ zeptoCalls += 1; return new Response("{{}}", {{ status: 401 }}); }}
  if (u.includes("api.nango.dev/connection")) return new Response(JSON.stringify({{ credentials: {{ access_token: "tok" }} }}), {{ status: 200 }});
  if (u.includes("mail.zoho.com/api/accounts")) return new Response(JSON.stringify({{ data: {{ messageId: "m1" }} }}), {{ status: 200 }});
  return new Response("{{}}", {{ status: 500 }});
}};
const env = {{ ZEPTOMAIL_TOKEN: "t", NANGO_SECRET_KEY: "s", NANGO_CONNECTION_ID: "c" }};
const res = await onRequestPost({{ request: new Request("https://{prop_id}.com/api/lead-capture", {{
  method: "POST", headers: {{ "Content-Type": "application/json" }},
  body: JSON.stringify({{ email: "jane.doe@acme-llc.com", tool_slug: {json.dumps(slug)} }}) }}), env }});
const data = await res.json();
console.log(JSON.stringify({{ status: data.zeptomail_status, provider: data.email_provider, zeptoCalls }}));
"""
        p = tmp_path / f"run_email_primary_{prop_id}.mjs"
        p.write_text(runner, encoding="utf-8")
        proc = subprocess.run(["node", str(p)], capture_output=True, text=True, check=True)
        out = json.loads(proc.stdout.strip().splitlines()[-1])
        assert out["status"] == "sent_edge_zoho_direct"
        assert out["provider"] == "zoho_mail_oauth"
        assert out["zeptoCalls"] == 0


def test_ui_ux_e2e_repro_gate(tmp_path):
    """
    Deterministic reproduction gate for the 4 UI/UX verification and runtime defects:
    1. EphemeralDistServer serves exact on-disk HTML bytes without in-memory normalization,
       evaluates dist/_redirects, returns 302 on GET /api/lead-capture?checkout=1&redirect=1,
       and derives /r/<partner> redirects from canonical affiliates.py / edge.py contracts.
    2. Visual primitives apply --border-focus on :focus / :focus-visible, inject skip-to-content
       #main-content target, and real Chrome CDP verifies visible focus rings on interactive elements.
    3. Every preset/switcher/scenario/action button (including data-preset-crit on GainHelm and
       data-preset-sec179 on ProfitHelm) and every calculator input/select/slider updates outputs
       synchronously without SERP workbench scope clobbering.
    4. UnifiedBrowserAuditor verifies all internal links, #fragment targets, _redirects, and
       all /r/<partner> + /api/* destinations end-to-end.
    """
    import urllib.error
    import urllib.request
    from pseofactory.browser_verifier import UnifiedBrowserAuditor
    from pseofactory.server import EphemeralDistServer
    from pseofactory.visual_primitives import normalize_html_visual_primitives

    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    # 1a. Verify EphemeralDistServer serves exact raw HTML bytes on disk without normalizing in memory
    raw_unnormalized = "<!DOCTYPE html><html><head><title>Raw</title></head><body><h1>Raw Disk Bytes</h1></body></html>"
    (dist_dir / "raw-check.html").write_text(raw_unnormalized, encoding="utf-8")
    (dist_dir / "_redirects").write_text(
        "/calculators/tax-brackets/ /tools/section-1031-calculator/ 301\n"
        "/vs/* /tools/section-1031-calculator/ 301\n",
        encoding="utf-8",
    )

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(_NoRedirect)

    with EphemeralDistServer(dist_dir) as server:
        with urllib.request.urlopen(f"{server.base_url}/raw-check.html", timeout=5) as resp:
            served_html = resp.read().decode("utf-8")
        assert served_html == raw_unnormalized, "EphemeralDistServer must serve exact on-disk HTML bytes without in-memory normalization"

        # 1b. Verify dist/_redirects exact and splat rules return 301 Location
        for redir_path in ("/calculators/tax-brackets/", "/vs/legacy-competitor"):
            try:
                opener.open(f"{server.base_url}{redir_path}", timeout=5)
                pytest.fail(f"Expected 301 redirect for {redir_path}")
            except urllib.error.HTTPError as exc:
                assert exc.code in (301, 302)
                assert exc.headers.get("Location") == "/tools/section-1031-calculator/"

        # 1c. Verify canonical partner redirects match affiliates.py / edge.py (zero hardcoded drift)
        expected_partner_prefixes = {
            "ipx1031": "https://www.ipx1031.com/start-an-exchange/",
            "mercury": "https://mercury.com/r/profithelm-llc",
            "kalshi": "https://kalshi.pxf.io/",
            "coinledger": "https://coinledger.io/?fpr=arif-554004",
            "koinly": "https://koinly.io/?fpr=arif-4c0b88",
        }
        for p_key, expected_prefix in expected_partner_prefixes.items():
            try:
                opener.open(
                    f"{server.base_url}/r/{p_key}?source_tool=section-1031-calculator&cta_slot=primary&subid=profithelm:section-1031-calculator:primary",
                    timeout=5,
                )
                pytest.fail(f"Expected 302 redirect for /r/{p_key}")
            except urllib.error.HTTPError as exc:
                assert exc.code == 302
                loc = exc.headers.get("Location") or ""
                assert loc.startswith(expected_prefix), f"/r/{p_key} redirected to {loc!r}, expected prefix {expected_prefix!r}"
                assert exc.headers.get("X-Edge-Partner") == p_key

        # 1d. Verify GET /api/lead-capture?checkout=1&...&redirect=1 returns 302 redirect when not requesting format=json
        try:
            opener.open(
                f"{server.base_url}/api/lead-capture?checkout=1&property_id=profithelm&tool_slug=section-1031-calculator&sku=ph_1031_boot_replacement_workpapers&redirect=1",
                timeout=5,
            )
            pytest.fail("Expected 302 redirect on GET /api/lead-capture?checkout=1&...&redirect=1")
        except urllib.error.HTTPError as exc:
            assert exc.code == 302
            assert exc.headers.get("Location"), "Expected Location header on 302 checkout redirect"

    # 2 & 3 & 4. Real-browser CDP verification of focus states, skip links, all presets/switchers/inputs/sliders, and links
    auditor = UnifiedBrowserAuditor(dist_dir=dist_dir)
    reachable, msg = auditor.check_cdp_reachability()
    assert reachable, f"Chrome CDP must be reachable for E2E verification: {msg}"

    # Compile a GainHelm page with .calc-switcher-btn[data-preset-hc][data-preset-crit] and ProfitHelm page with [data-preset-sec179]
    gh_spec = {
        "slug": "soc-2-audit-cost-calculator",
        "title": "SOC 2 Type II Audit Cost & GRC Readiness Calculator",
        "model_name": "SOC 2 Audit Cost Model",
        "property_id": "gainhelm",
        "canonical_base": "https://gainhelm.com",
        "formula": "gross_amount * (1.0 - effective_rate)",
        "inputs": {"gross_amount": 65000.0, "effective_rate": 0.15},
        "published_output": 55250.0,
        "sample_calculation": "Evaluating $65,000 SOC 2 readiness scope at 15% automation savings factor yields $55,250.00 net audit cost.",
        "statutory_authority": "32 CFR Part 170 and AICPA SSAE 18 (AT-C Section 205)",
        "economic_dataset": "BLS Occupational Employment and Wages Series",
    }
    compiled_gh = compile_high_effort_page(gh_spec)["html"]
    # Inject a GainHelm-style .calc-switcher-btn with data-preset-hc and data-preset-crit and secondary calc-input-headcount / calc-input-extra_criteria
    gh_switcher_snippet = (
        '<div class="calc-switcher" role="group" aria-label="Company Stage Presets">'
        '<button type="button" class="calc-switcher-btn active" data-preset-hc="75" data-preset-crit="2">Series A (75 Emp / 3 TSC)</button>'
        '<button type="button" class="calc-switcher-btn" data-preset-hc="250" data-preset-crit="4">Enterprise (250 Emp / 5 TSC)</button>'
        '<input type="number" id="calc-input-headcount" data-calc-input="headcount" value="75">'
        '<input type="number" id="calc-input-extra_criteria" data-calc-input="extra_criteria" value="2">'
        '</div>'
    )
    compiled_gh = compiled_gh.replace("</main>", gh_switcher_snippet + "</main>", 1)
    compiled_gh, _ = normalize_html_visual_primitives(compiled_gh, theme="porcelain")

    gh_tool_dir = dist_dir / "tools" / "soc-2-audit-cost-calculator"
    gh_tool_dir.mkdir(parents=True, exist_ok=True)
    (gh_tool_dir / "index.html").write_text(compiled_gh, encoding="utf-8")
    sec1031_dir = dist_dir / "tools" / "section-1031-calculator"
    sec1031_dir.mkdir(parents=True, exist_ok=True)
    (sec1031_dir / "index.html").write_text(compiled_gh, encoding="utf-8")
    (dist_dir / "index.html").write_text(compiled_gh, encoding="utf-8")

    with EphemeralDistServer(dist_dir) as server:
        gh_auditor = UnifiedBrowserAuditor(dist_dir=dist_dir)
        rep = gh_auditor.audit_interactive_surface(server.base_url, "/tools/soc-2-audit-cost-calculator/")
        assert rep["passed"] is True, f"Interactive surface audit failed: {rep}"
        assert "focus_and_keyboard_navigation" in rep, "audit_interactive_surface must include focus_and_keyboard_navigation check"
        focus_rep = rep["focus_and_keyboard_navigation"]
        assert focus_rep["passed"] is True, f"Focus & keyboard audit failed: {focus_rep}"
        assert focus_rep["skip_link_valid"] is True
        assert focus_rep["positive_tabindex_traps"] == []
        assert focus_rep["zero_outline_failures"] == []
        assert focus_rep["focusable_count"] >= 5

        calc_rep = rep["calculator_and_presets"]
        assert calc_rep["passed"] is True, f"Calculator and presets audit failed: {calc_rep}"
        assert calc_rep.get("buttons_tested_count", 0) >= 4
        assert calc_rep.get("button_failures") == []
        assert calc_rep.get("inputs_tested_count", 0) >= 2
        assert calc_rep.get("input_failures") == []


def test_edge_stripe_checkout_unlocked_email_kv_preservation_and_rich_playbook_email(tmp_path):
    """
    Verifies three live conversion requirements across ProfitHelm and Prexvo edge workers:
    1. Anonymous GET /api/lead-capture?checkout=1 omits customer_email from Stripe session
       creation so Stripe Checkout lets the buyer type their own email instead of locking
       cfo@profithelm.com or borrower@prexvo.com.
    2. When a lead already submitted an email via POST /api/lead-capture, a subsequent
       GET /api/lead-capture?checkout=1&lead_id=<id> preserves their stored KV email and
       pre-fills that real email into Stripe Checkout rather than overwriting it with a placeholder.
    3. When an anonymous buyer completes payment on Stripe (returning customer_details.email
       on /v1/checkout/sessions/cs_live_...), fulfill=1 syncs that real buyer email onto the
       settled lead record so lead_origin is 'real' (not 'internal_probe').
    4. Playbook email body dispatched by dispatchEdgeZeptoMailPlaybook includes the inline
       4-line reconciliation_schedule table and direct free Playbook worksheet/CSV links.
    """
    import subprocess
    import json

    for prop_id in ("profithelm", "prexvo"):
        fn_dir = tmp_path / f"{prop_id}_conv" / "functions" / "api"
        fn_dir.mkdir(parents=True)
        fn_file = fn_dir / "lead-capture.js"
        fn_file.write_text(generate_edge_lead_capture_function(prop_id), encoding="utf-8")

        slug = (
            "section-1031-calculator"
            if prop_id == "profithelm"
            else "student-loan-refinance-break-even-calculator"
        )
        node_script = f"""
        import("./functions/api/lead-capture.js").then(async mod => {{
          const kvStore = new Map();
          const stripePostBodies = [];
          let capturedEmailHtml = "";
          globalThis.fetch = async (url, init) => {{
            const u = String(url);
            if (u.includes("api.nango.dev/connection")) {{
              return new Response(JSON.stringify({{
                credentials: {{ access_token: "1000.mock_zoho_oauth_token" }}
              }}), {{ status: 200 }});
            }}
            if (u.includes("mail.zoho.com/api/accounts")) {{
              const parsed = JSON.parse(init.body || "{{}}");
              capturedEmailHtml = parsed.content || "";
              return new Response(JSON.stringify({{
                status: {{ code: 200 }},
                data: {{ messageId: "msg_rich_123", mailId: "msg_rich_123" }}
              }}), {{ status: 200 }});
            }}
            if (u === "https://api.stripe.com/v1/checkout/sessions" && init && init.method === "POST") {{
              stripePostBodies.push(String(init.body || ""));
              return new Response(JSON.stringify({{
                id: "cs_live_SESSION_" + stripePostBodies.length,
                url: "https://checkout.stripe.com/c/pay/cs_live_SESSION_" + stripePostBodies.length
              }}), {{ status: 200 }});
            }}
            if (u.includes("api.stripe.com/v1/checkout/sessions/cs_live_PAID_ANON")) {{
              return new Response(JSON.stringify({{
                id: "cs_live_PAID_ANON",
                livemode: true,
                payment_status: "paid",
                amount_total: 4900,
                currency: "usd",
                client_reference_id: "lead_{prop_id}_anon_buyer",
                customer_details: {{ email: "realbuyer@externalclient.io" }},
                metadata: {{
                  lead_id: "lead_{prop_id}_anon_buyer",
                  property_id: "{prop_id}",
                  calculated_amount: "325000",
                  state: "TX"
                }}
              }}), {{ status: 200 }});
            }}
            return new Response("{{}}", {{ status: 200 }});
          }};

          const mockEnv = {{
            NANGO_SECRET_KEY: "mock_nango_secret",
            NANGO_CONNECTION_ID: "mock_nango_conn",
            ZOHO_MAIL_ACCOUNT_ID: "676891000000008002",
            STRIPE_ACCOUNT_ID: "acct_1T6fSTIq0ckFsf5j",
            STRIPE_PUBLISHABLE_KEY: "pk_live_mock",
            STRIPE_SECRET_KEY: "sk_live_mock",
            PROFITHELM_LEADS: {{
              put: async (k, v) => kvStore.set(k, JSON.parse(v)),
              list: async ({{ prefix }}) => ({{
                keys: Array.from(kvStore.keys()).filter(k => k.startsWith(prefix)).map(name => ({{ name }}))
              }}),
              get: async (k) => kvStore.get(k) || null
            }},
            PREXVO_LEADS: {{
              put: async (k, v) => kvStore.set(k, JSON.parse(v)),
              list: async ({{ prefix }}) => ({{
                keys: Array.from(kvStore.keys()).filter(k => k.startsWith(prefix)).map(name => ({{ name }}))
              }}),
              get: async (k) => kvStore.get(k) || null
            }}
          }};

          // 1. Anonymous checkout=1 click (no email query param)
          const anonCoRes = await mod.onRequestGet({{
            request: new Request("https://{prop_id}.com/api/lead-capture?checkout=1&tool_slug={slug}&amount=325000&lead_id=lead_{prop_id}_anon_buyer&format=json"),
            env: mockEnv
          }});
          const anonCoData = await anonCoRes.json();

          // 2. Playbook form submission with real visitor email, followed by checkout=1 with lead_id (no email query param)
          const pbRes = await mod.onRequestPost({{
            request: {{
              url: "https://{prop_id}.com/api/lead-capture",
              headers: new Headers({{ "content-type": "application/json" }}),
              json: async () => ({{
                email: "leadbuyer@acmecorp.io",
                source: "/tools/{slug}/",
                tool_slug: "{slug}",
                scenario_amount: 410000
              }})
            }},
            env: mockEnv
          }});
          const pbData = await pbRes.json();

          const leadCoRes = await mod.onRequestGet({{
            request: new Request("https://{prop_id}.com/api/lead-capture?checkout=1&lead_id=" + pbData.lead_id + "&tool_slug={slug}&format=json"),
            env: mockEnv
          }});
          const leadCoData = await leadCoRes.json();

          // 3. Anonymous buyer completes Stripe Checkout and hits fulfill=1
          const fulfillRes = await mod.onRequestGet({{
            request: new Request("https://{prop_id}.com/api/lead-capture?fulfill=1&lead_id=lead_{prop_id}_anon_buyer&tool_slug={slug}&session_id=cs_live_PAID_ANON&format=json"),
            env: mockEnv
          }});
          const fulfillData = await fulfillRes.json();

          const listRes = await mod.onRequestGet({{
            request: new Request("https://{prop_id}.com/api/lead-capture?limit=50"),
            env: mockEnv
          }});
          const listData = await listRes.json();

          console.log(JSON.stringify({{
            stripePostBodies,
            capturedEmailHtml,
            anonCoStatus: anonCoRes.status,
            leadCoStatus: leadCoRes.status,
            fulfillStatus: fulfillRes.status,
            listData
          }}));
        }});
        """
        proc = subprocess.run(
            ["node", "-e", node_script],
            cwd=tmp_path / f"{prop_id}_conv",
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr
        out = json.loads(proc.stdout.strip())
        bodies = out["stripePostBodies"]
        assert len(bodies) >= 3
        # Body 0: anonymous GET checkout=1 -> must NOT lock customer_email to cfo@profithelm.com / borrower@prexvo.com
        assert "customer_email=" not in bodies[0], f"Anonymous checkout locked customer_email: {bodies[0]}"
        # Body 1 (from POST) and Body 2 (from GET checkout=1&lead_id=...) -> must pass leadbuyer@acmecorp.io
        assert "customer_email=leadbuyer%40acmecorp.io" in bodies[2], f"Stored KV lead email was overwritten on checkout=1: {bodies[2]}"
        # Rich Playbook email must include reconciliation table and playbook=1 links
        email_html = out["capturedEmailHtml"]
        assert "playbook=1" in email_html, f"Playbook email missing free playbook=1 link: {email_html}"
        assert "format=csv" in email_html, f"Playbook email missing CSV schedule link: {email_html}"
        assert "<table" in email_html and "Statutory Line Item" in email_html, f"Playbook email missing inline reconciliation table: {email_html}"
        # Fulfilled anonymous checkout must sync realbuyer@externalclient.io from Stripe customer_details so lead_origin is 'real'
        settled_lead = next((l for l in out["listData"]["leads"] if l["lead_id"] == f"lead_{prop_id}_anon_buyer"), None)
        assert settled_lead is not None
        assert settled_lead["settlement_status"] == "settled"
        assert settled_lead["lead_origin"] == "real", f"Settled anonymous buyer should have lead_origin='real' from Stripe customer_details.email, got: {settled_lead}"


