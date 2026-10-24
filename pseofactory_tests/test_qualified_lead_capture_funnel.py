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
            url: "https://{prop_id}.com" + pbData.checkout_url,
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
        assert "/api/lead-capture?checkout=1" in out["pbData"]["checkout_url"]
        assert out["getCount"] == 1
        assert out["getSummary"]["playbook_subscriptions_count"] == 1
        assert out["coStatus"] == 200
        assert out["coData"]["status"] == "checkout_session_ready"
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
        assert out["qData"]["checkout_mode"] == "edge_checkout_rail"
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
        assert out["qData"]["checkout_mode"] == "edge_checkout_rail"
        assert out["qData"]["stripe_called"] is False
        assert out["coData"]["status"] == "checkout_session_ready"
        assert out["coData"]["checkout_mode"] == "edge_checkout_rail"
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
            assert report["playbook_lead_capture_and_checkout"]["present"] is True
            assert report["playbook_lead_capture_and_checkout"]["passed"] is True
            assert report["partner_quote_intake_and_checkout"]["present"] is True
            assert report["partner_quote_intake_and_checkout"]["passed"] is True
            assert report["affiliate_redirect_and_telemetry"]["tested"] is True
            assert report["affiliate_redirect_and_telemetry"]["passed"] is True

            assert len(server.captured_leads) >= 2
            assert len(server.checkout_sessions) >= 2
            assert len(server.telemetry_events) >= 1
            assert len(server.redirect_events) >= 1


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

const env = {{}};
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

const fulfillHtmlReq = new Request("https://{prop_id}.com" + pbData.fulfillment_url + "&format=html&synthetic_test=1", {{
  method: "GET",
  headers: {{ "X-Pseofactory-Test": "1" }}
}});
const fulfillHtmlRes = await onRequestGet({{ request: fulfillHtmlReq, env }});
const fulfillHtmlText = await fulfillHtmlRes.text();

const fulfillCsvReq = new Request("https://{prop_id}.com" + pbData.csv_fulfillment_url + "&synthetic_test=1", {{
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
        diagnose_stripe_merchant_readiness,
        synthesize_personalized_audit_workpaper,
    )

    stripe_diag = diagnose_stripe_merchant_readiness(execute_live=False)
    assert stripe_diag["stripe_account_id"] == "acct_1T6fSTIq0ckFsf5j"
    assert stripe_diag["merchant_email"] == "arif.coskun@profithelm.com"
    assert stripe_diag["display_name"] == "CoachOS"
    assert stripe_diag["product_count"] >= 4
    assert "ph_1031_boot_replacement_workpapers" in stripe_diag["product_skus"]
    assert "px_refi_amortization_decision_audit" in stripe_diag["product_skus"]

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
const env = {{}};
const inputsParam = encodeURIComponent(JSON.stringify({{ custom_amount: 410000, custom_rate: 5.4 }}));
const chkReq = new Request("https://{prop_id}.com/api/lead-capture?checkout=1&lead_id=lead_custom_1&tool_slug={slug}&amount=410000&inputs_json=" + inputsParam + "&synthetic_test=1", {{
  method: "GET",
  headers: {{ "X-Pseofactory-Test": "1" }}
}});
const chkRes = await onRequestGet({{ request: chkReq, env }});
const chkData = await chkRes.json();

const ffReq = new Request("https://{prop_id}.com/api/lead-capture?fulfill=1&lead_id=lead_custom_1&tool_slug={slug}&amount=410000&inputs_json=" + inputsParam + "&synthetic_test=1", {{
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
        assert out["chkData"]["ok"] is True
        assert out["chkData"]["stripe_account_id"] == "acct_1T6fSTIq0ckFsf5j"
        assert out["chkData"]["stripe_merchant_email"] == "arif.coskun@profithelm.com"
        assert out["chkData"]["reservation_captured"] is True
        assert out["chkData"]["reservation_id"] == "rsv_lead_custom_1"
        assert out["chkData"]["diagnostic_telemetry"]["merchant_email"] == "arif.coskun@profithelm.com"
        assert out["chkData"]["diagnostic_telemetry"]["cli_key_expires_at"] == "2026-06-03"
        assert out["chkData"]["calculated_amount"] == 410000
        assert out["chkData"]["statutory_trend_series_count"] >= 3
        assert out["ffData"]["ok"] is True
        assert out["ffData"]["calculated_amount"] == 410000
        assert len(out["ffData"]["statutory_trend_timeseries"]) >= 3
        assert out["ffData"]["custom_parameter_ledger"]["calculated_amount"] == 410000
        assert out["ffData"]["custom_parameter_ledger"]["inputs"]["custom_amount"] == 410000
        assert f"TREND-{expected_series_id}" in out["ffData"]["csv_content"]




