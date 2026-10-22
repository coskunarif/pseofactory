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

    assert "PREXVO_LEADS" in px_js
    assert "splash_financial" in px_js
    assert "RESTRICTED_PUBLIC_SERVICE_SLUGS" in px_js
    assert "otr_solutions_factoring" not in px_js

    for prop_id in ("profithelm", "prexvo"):
        repo_dir = tmp_path / prop_id
        (repo_dir / "functions" / "r").mkdir(parents=True)
        (repo_dir / "wrangler.toml").write_text(f'name = "{prop_id}"\n', encoding="utf-8")
        res = sync_tenant_edge_redirect_function(repo_dir, property_id=prop_id)
        assert res["status"] == "UPDATED"
        assert (repo_dir / "functions" / "api" / "lead-capture.js").is_file()
