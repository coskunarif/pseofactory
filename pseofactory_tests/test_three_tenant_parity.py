"""Regression tests for three-tenant first-class parity (ProfitHelm, Prexvo, GainHelm)."""

from __future__ import annotations

from pathlib import Path
import pytest

from pseofactory.affiliates import (
    _match_gsc_query_specialized_partner,
    estimate_partner_approval_revenue_impact,
    qualify_monetization_opportunity,
)
from pseofactory.affiliates_hub import MonetizationHub
from pseofactory.drift import detect_engine_drift
from pseofactory.email_ingest import EmailIngestionEngine, EmailMessage
from pseofactory.gitops import sync_tenant_test_isolation_guards
from pseofactory.pipeline import FactoryPipeline
from pseofactory.qualification import sync_tenant_redirect_rollup_adapters
from pseofactory.tenant_facts import (
    CANONICAL_TENANT_DECLARATIONS,
    CANONICAL_TENANT_IDS,
    TenantFactStore,
    TruthReconciliationEngine,
)
from pseofactory.trends.jev_engine import JevEngine
from pseofactory.trends.models import TregDurabilityResult, TrendCandidate


def test_canonical_tenant_registry_includes_all_three_tenants() -> None:
    assert tuple(CANONICAL_TENANT_IDS) == ("profithelm", "prexvo", "gainhelm")
    assert set(CANONICAL_TENANT_DECLARATIONS.keys()) == {"profithelm", "prexvo", "gainhelm"}


def test_determine_property_assignment_disambiguates_across_all_three_tenants() -> None:
    pipeline = FactoryPipeline()
    r1 = pipeline.determine_property_assignment("s-corp reasonable salary vs soc 2 audit", explicit_tenant="profithelm")
    assert r1["basis"] == "cross_contaminated"
    assert "soc 2 audit" in r1["foreign_tokens"]

    r2 = pipeline.determine_property_assignment("save plan discretionary income vs soc 2 audit", explicit_tenant="prexvo")
    assert r2["basis"] == "cross_contaminated"
    assert "soc 2 audit" in r2["foreign_tokens"]

    r3 = pipeline.determine_property_assignment("cmmc 2.0 sprs score calculator for defense contractor")
    assert r3["property_id"] == "gainhelm"
    assert r3["contamination_scan_passed"] == 1


def test_qualify_monetization_opportunity_symmetric_cross_tenant_isolation() -> None:
    # ProfitHelm must reject pure GainHelm cyber/compliance queries
    ph_cyber = qualify_monetization_opportunity(
        query="soc 2 type ii audit readiness cost",
        property_id="profithelm",
        search_volume=500,
    )
    assert ph_cyber["monetization_qualified"] is False
    assert ph_cyber["intent_tier"] == "cross_tenant_contamination"

    # GainHelm must reject pure ProfitHelm B2B tax/accounting queries
    gh_tax = qualify_monetization_opportunity(
        query="s-corp reasonable salary tax calculator",
        property_id="gainhelm",
        search_volume=500,
    )
    assert gh_tax["monetization_qualified"] is False
    assert gh_tax["intent_tier"] == "cross_tenant_contamination"

    # GainHelm must reject pure Prexvo student loan queries
    gh_loan = qualify_monetization_opportunity(
        query="pslf qualifying payment recount calculator",
        property_id="gainhelm",
        search_volume=500,
    )
    assert gh_loan["monetization_qualified"] is False
    assert gh_loan["intent_tier"] == "cross_tenant_contamination"

    # GainHelm must qualify high-intent cyber compliance queries and match specialized partners
    gh_valid = qualify_monetization_opportunity(
        query="drata soc 2 automation pricing calculator",
        property_id="gainhelm",
        search_volume=800,
        cpc_usd=18.0,
    )
    assert gh_valid["monetization_qualified"] is True
    assert gh_valid["intent_tier"] == "enterprise_cyber_compliance_grc"

    mock_roster = [
        {"partner_key": "vanta_security"},
        {"partner_key": "drata_compliance"},
        {"partner_key": "sprinto_compliance"},
        {"partner_key": "thoropass_audit"},
        {"partner_key": "coalition_cyber_insurance"},
        {"partner_key": "cobalt_pentest"},
    ]
    assert (
        _match_gsc_query_specialized_partner(
            property_id="gainhelm",
            vertical_family="cyber_compliance_grc",
            query="cobalt pentest cost",
            roster_offers=mock_roster,
        )
        == "cobalt_pentest"
    )
    assert (
        _match_gsc_query_specialized_partner(
            property_id="gainhelm",
            vertical_family="cyber_compliance_grc",
            query="coalition cyber insurance quote",
            roster_offers=mock_roster,
        )
        == "coalition_cyber_insurance"
    )
    assert (
        _match_gsc_query_specialized_partner(
            property_id="gainhelm",
            vertical_family="cyber_compliance_grc",
            query="thoropass audit pricing",
            roster_offers=mock_roster,
        )
        == "thoropass_audit"
    )
    assert (
        _match_gsc_query_specialized_partner(
            property_id="gainhelm",
            vertical_family="cyber_compliance_grc",
            query="sprinto iso 27001",
            roster_offers=mock_roster,
        )
        == "sprinto_compliance"
    )
    assert (
        _match_gsc_query_specialized_partner(
            property_id="gainhelm",
            vertical_family="cyber_compliance_grc",
            query="vanta soc 2 compliance",
            roster_offers=mock_roster,
        )
        == "vanta_security"
    )
    assert (
        _match_gsc_query_specialized_partner(
            property_id="gainhelm",
            vertical_family="cyber_compliance_grc",
            query="cmmc 2.0 defense contractor",
            roster_offers=mock_roster,
        )
        == "drata_compliance"
    )


def test_estimate_partner_approval_revenue_impact_supports_gainhelm() -> None:
    impact = estimate_partner_approval_revenue_impact("gainhelm", "vanta_security")
    assert impact["property_id"] == "gainhelm"
    assert impact["partner_key"] == "vanta_security"
    assert impact["estimated_monthly_revenue_impact_usd"] > 0


def test_monetization_hub_cross_tenant_isolation_all_three_tenants() -> None:
    hub = MonetizationHub()

    # Prexvo rejects GainHelm partner keys and slugs
    with pytest.raises(ValueError, match="Strict isolation violation"):
        hub.get_route("prexvo", partner_key="vanta_security", tool_slug="soc-2-audit-cost-calculator")

    # ProfitHelm rejects GainHelm partner keys and slugs
    with pytest.raises(ValueError, match="Strict isolation violation"):
        hub.get_route("profithelm", partner_key="vanta_security", tool_slug="soc-2-audit-cost-calculator")

    # GainHelm rejects ProfitHelm and Prexvo slugs
    with pytest.raises(ValueError, match="Strict isolation violation"):
        hub.get_route("gainhelm", tool_slug="section-179-calculator")

    with pytest.raises(ValueError, match="Strict isolation violation"):
        hub.get_route("gainhelm", tool_slug="student-loan-repayment-calculator")

    # GainHelm routes valid compliance partner cleanly
    gh_ok = hub.get_route("gainhelm", partner_key="vanta_security", tool_slug="soc-2-audit-cost-calculator")
    assert gh_ok["partner"] == "vanta_security"


def test_jev_engine_handles_gainhelm_intent_tiers() -> None:
    jev = JevEngine()

    out_of_scope_cand = TrendCandidate(
        id="gh-1",
        query="random consumer recipe blog",
        slug="random-consumer-recipe-blog",
        source="gsc",
        velocity=2.5,
        acceleration=0.8,
        z_score=3.0,
        intent_cluster="calculator",
        metadata={"property_id": "gainhelm"},
    )
    out_of_scope_treg = TregDurabilityResult(
        query="random consumer recipe blog",
        search_volume=1200,
        cpc_usd=4.5,
        keyword_difficulty=20.0,
    )
    rejected = jev.evaluate(out_of_scope_cand, out_of_scope_treg)
    assert rejected.action == "REJECT"
    assert rejected.composite_profit_yield == 0.0

    valid_cand = TrendCandidate(
        id="gh-2",
        query="soc 2 type ii audit readiness calculator",
        slug="soc-2-type-ii-audit-readiness-calculator",
        source="gsc",
        velocity=3.2,
        acceleration=1.1,
        z_score=3.8,
        intent_cluster="calculator",
        metadata={"property_id": "gainhelm"},
    )
    valid_treg = TregDurabilityResult(
        query="soc 2 type ii audit readiness calculator",
        search_volume=2400,
        cpc_usd=18.5,
        keyword_difficulty=22.0,
        position_zero_vacant=True,
    )
    accepted = jev.evaluate(valid_cand, valid_treg)
    assert accepted.composite_profit_yield > 0.0


def test_tenant_fact_store_and_truth_reconciliation_for_gainhelm() -> None:
    store = TenantFactStore()

    # Missing CPA/C3PAO disclaimer on compliance audit claim should fail
    ok_missing_disc, viol_missing_disc = store.verify_claim(
        "gainhelm",
        "SOC 2 Type II compliance audit modeling estimates 420 engineering hours saved.",
    )
    assert ok_missing_disc is False
    assert any("disclaimer" in v.lower() or "attestation" in v.lower() for v in viol_missing_disc)

    # Invalid $29 pricing fallback and SPRS 115 out-of-bounds should fail
    ok_bad_facts, viol_bad_facts = store.verify_claim(
        "gainhelm",
        "GainHelm Pro Plan starts at $29/mo with an SPRS score of 115. "
        "Informational estimates only - does not constitute formal CPA or C3PAO attestation.",
    )
    assert ok_bad_facts is False
    assert len(viol_bad_facts) >= 2

    # Valid GainHelm claim passes
    ok_valid, viol_valid = store.verify_claim(
        "gainhelm",
        "GainHelm Pro Plan starts at $49/mo with a maximum NIST SP 800-171 SPRS score of 110. "
        "Informational estimates only - does not constitute formal CPA or C3PAO attestation.",
    )
    assert ok_valid is True
    assert viol_valid == []

    # TruthReconciliationEngine fixes GainHelm HTML drift and uses dynamic canonical URL
    reconciler = TruthReconciliationEngine()
    dirty_html = (
        "<html><head><title>GainHelm Audit Signal</title></head>"
        "<body><p>Upgrade for $29/mo to reach an SPRS score of 115.</p></body></html>"
    )
    clean_html, repairs = reconciler.reconcile_html_truth(
        dirty_html,
        tenant="gainhelm",
        rel_path="signal/index.html",
        slug="signal",
    )
    assert "$49/mo" in clean_html
    assert "SPRS score of 110" in clean_html
    assert "https://gainhelm.com/signal/" in clean_html
    assert "gainhelm_statutory_truth_reconciled" in repairs
    assert "signal_webpage_jsonld_injected" in repairs


def test_email_ingestion_recognizes_gainhelm_partners(tmp_path: Path) -> None:
    engine = EmailIngestionEngine(
        cache_path=str(tmp_path / "cache.json"),
        state_path=str(tmp_path / "state.json"),
    )
    msgs = [
        EmailMessage(
            id="gh-sent-1",
            message_id="gh-sent-1",
            account="zoho",
            mailbox="Sent",
            date="2026-10-29T12:00:00Z",
            subject="Partnership Inquiry - GainHelm SOC 2 Calculator",
            sender_name="Arif Coskun",
            sender_email="partners@vanta.com",
            body_snippet="Submitting application for Vanta Trust Management Platform partnership.",
            raw_headers={"to_email": "partners@vanta.com"},
        )
    ]
    classified = engine.classify_partner_emails(msgs)
    assert len(classified) == 1
    assert classified[0].property_id == "gainhelm"
    assert classified[0].partner_key == "vanta_security"


def test_detect_engine_drift_accepts_lock_path_alias(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "gainhelm"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "config.py").write_text("SITE_URL = 'https://gainhelm.com'\n", encoding="utf-8")
    lock_file = tmp_path / "substrate_lock.json"

    res1 = detect_engine_drift(lock_path=lock_file, base_dirs=[pkg_dir], auto_record=True)
    assert lock_file.is_file()
    assert res1["state_file"] == str(lock_file)

    res2 = detect_engine_drift(lock_path=lock_file, base_dirs=[pkg_dir], auto_record=False)
    assert res2["drift_detected"] is False


def test_sync_tenant_guards_provisions_gainhelm_infrastructure(tmp_path: Path) -> None:
    repo = tmp_path / "gainhelm"
    (repo / "gainhelm" / "datasets" / "sources").mkdir(parents=True)
    (repo / "pyproject.toml").write_text("[project]\nname = 'gainhelm'\n", encoding="utf-8")
    (repo / "gainhelm" / "observer.py").write_text(
        '"""GainHelm observer."""\nfrom pathlib import Path\n',
        encoding="utf-8",
    )
    (repo / "gainhelm" / "factory.py").write_text(
        '"""GainHelm factory."""\nfrom pathlib import Path\n',
        encoding="utf-8",
    )

    changed = sync_tenant_test_isolation_guards(repo)
    assert changed["status"] == "PASS"
    rel_files = {Path(p).relative_to(repo).as_posix() for p in changed["files"]}
    assert ".github/workflows/ci.yml" in rel_files
    assert "scripts/run_factory.sh" in rel_files
    assert "gainhelm/datasets/join.py" in rel_files
    assert "gainhelm/observer.py" in rel_files
    assert "gainhelm/factory.py" in rel_files

    rollup_changed = sync_tenant_redirect_rollup_adapters(repo)
    assert isinstance(rollup_changed, int)
    assert "rollup_redirected_gsc_rows" in (repo / "gainhelm" / "observer.py").read_text(encoding="utf-8")
    assert "run_factory_pipeline" in (repo / "gainhelm" / "factory.py").read_text(encoding="utf-8")
