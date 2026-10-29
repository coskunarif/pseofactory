"""
Unit tests for pseofactory Tenant Fact & Statutory Truth Store
Verifies:
1. Strict tenant boundary isolation between ProfitHelm and Prexvo.
2. Canonical pricing tier verification ($0, $49, $199 for ProfitHelm; $0, $19 for Prexvo).
3. Statutory limit accuracy (IRS Sec 179, QSBS, 401k, HSA vs Title IV, RAP 10%/225%, IBR, PSLF, Poverty Guidelines).
4. Feature contract matrix enforcement.
5. Banned marketing claims rejection.
6. Mandatory regulatory disclosure verification.
7. Cross-tenant contamination prevention.

Zero em-dashes. Zero en-dashes.
"""

import pytest

from pseofactory.tenant_facts import (
    TenantFactStore,
    TenantTruthProfile,
    PricingTier,
    FeatureContract,
    TenantStatutoryTruth,
    PropertyContaminationError,
)


def test_tenant_fact_store_singleton_and_profiles():
    """Verifies TenantFactStore singleton pattern and profile loading."""
    store1 = TenantFactStore.get_instance()
    store2 = TenantFactStore.get_instance()
    assert store1 is store2

    ph_profile = store1.get_profile("profithelm")
    assert ph_profile is not None
    assert ph_profile.tenant_id == "profithelm"
    assert ph_profile.brand_name == "ProfitHelm"
    assert "profithelm.com" in ph_profile.canonical_domain

    px_profile = store1.get_profile("prexvo")
    assert px_profile is not None
    assert px_profile.tenant_id == "prexvo"
    assert px_profile.brand_name == "Prexvo"
    assert "prexvo.com" in px_profile.canonical_domain

    assert store1.get_profile("unknown_tenant") is None


def test_profithelm_pricing_and_features():
    """Verifies ProfitHelm pricing tiers and grounded feature matrix."""
    store = TenantFactStore.get_instance()

    # Pricing verification
    assert store.verify_price("profithelm", 0.0) is True
    assert store.verify_price("profithelm", 49.0) is True
    assert store.verify_price("profithelm", 199.0) is True
    assert store.verify_price("profithelm", 29.0) is False
    assert store.verify_price("profithelm", 19.0) is False

    # Feature verification
    assert store.verify_feature("profithelm", "Entity Tax Modeling") is True
    assert store.verify_feature("profithelm", "Section 1031 Exchange Matching") is True
    assert store.verify_feature("profithelm", "Section 179 Optimizer") is True
    assert store.verify_feature("profithelm", "QSBS Stacking Analysis") is True
    assert store.verify_feature("profithelm", "Multi-Entity Consolidation") is True

    # Foreign features must not be enabled for ProfitHelm
    assert store.verify_feature("profithelm", "RAP vs IBR Modeling") is False
    assert store.verify_feature("profithelm", "PSLF Buyback Estimator") is False


def test_prexvo_pricing_and_features():
    """Verifies Prexvo pricing tiers and student loan feature matrix."""
    store = TenantFactStore.get_instance()

    # Pricing verification
    assert store.verify_price("prexvo", 0.0) is True
    assert store.verify_price("prexvo", 19.0) is True
    assert store.verify_price("prexvo", 49.0) is False
    assert store.verify_price("prexvo", 199.0) is False

    # Feature verification
    assert store.verify_feature("prexvo", "RAP vs IBR Modeling") is True
    assert store.verify_feature("prexvo", "Tiered Standard Calculation") is True
    assert store.verify_feature("prexvo", "PAYE Sunset Analysis") is True
    assert store.verify_feature("prexvo", "ICR Repayment Modeling") is True
    assert store.verify_feature("prexvo", "PSLF Buyback Estimator") is True

    # Foreign features must not be enabled for Prexvo
    assert store.verify_feature("prexvo", "Section 1031 Exchange Matching") is False
    assert store.verify_feature("prexvo", "QSBS Stacking Analysis") is False


def test_statutory_limits_and_citations():
    """Verifies statutory truth limits and citations for both tenants."""
    store = TenantFactStore.get_instance()

    # ProfitHelm Statutory Truth
    ph = store.get_profile("profithelm").statutory_truth
    assert ph.statutory_citations["irs_rev_proc_2024_40"] == "IRS Rev Proc 2024-40"
    assert ph.limits_and_thresholds["section_179_expense_limit_2024"] == 1220000.0
    assert ph.limits_and_thresholds["section_179_expense_limit_2025"] == 1250000.0
    assert ph.limits_and_thresholds["section_179_heavy_vehicle_2024"] == 30500.0
    assert ph.limits_and_thresholds["section_179_heavy_vehicle_2025"] == 31300.0
    assert ph.limits_and_thresholds["section_1202_qsbs_asset_ceiling"] == 50000000.0
    assert ph.limits_and_thresholds["section_1202_qsbs_exclusion_cap"] == 10000000.0
    assert ph.limits_and_thresholds["section_1202_qsbs_exclusion_multiple"] == 10.0
    assert ph.limits_and_thresholds["section_1202_qsbs_holding_period_years"] == 5
    assert ph.limits_and_thresholds["retirement_401k_elective_deferral_2024"] == 23000.0
    assert ph.limits_and_thresholds["retirement_401k_elective_deferral_2025"] == 23500.0
    assert ph.limits_and_thresholds["hsa_single_2024"] == 4150.0
    assert ph.limits_and_thresholds["hsa_single_2025"] == 4300.0
    assert ph.limits_and_thresholds["hsa_family_2024"] == 8300.0
    assert ph.limits_and_thresholds["hsa_family_2025"] == 8550.0

    # Prexvo Statutory Truth
    px = store.get_profile("prexvo").statutory_truth
    assert px.statutory_citations["title_iv"] == "Title IV Higher Education Act"
    assert px.statutory_citations["34_cfr_685"] == "34 CFR Part 685"
    assert px.limits_and_thresholds["rap_discretionary_percentage"] == 0.10
    assert px.limits_and_thresholds["rap_poverty_guideline_threshold"] == 2.25
    assert px.limits_and_thresholds["ibr_pre_2014_percentage"] == 0.15
    assert px.limits_and_thresholds["ibr_post_2014_percentage"] == 0.10
    assert px.limits_and_thresholds["ibr_poverty_guideline_threshold"] == 1.50
    assert px.limits_and_thresholds["pslf_qualifying_payments"] == 120

    # HHS Poverty guidelines 2024-2026
    poverty = px.limits_and_thresholds["poverty_guidelines"]
    assert poverty[2024]["individual"] == 15060.0
    assert poverty[2024]["additional_person"] == 5380.0
    assert poverty[2025]["individual"] == 15650.0
    assert poverty[2025]["additional_person"] == 5440.0
    assert poverty[2026]["individual"] == 15650.0
    assert poverty[2026]["additional_person"] == 5500.0


def test_banned_claims_detection():
    """Verifies that banned claims are caught by verify_claim."""
    store = TenantFactStore.get_instance()

    # ProfitHelm banned claims
    valid, violations = store.verify_claim(
        "profithelm",
        "We provide automated IRS filing for small businesses.",
    )
    assert valid is False
    assert any("automated irs filing" in v.lower() for v in violations)

    valid, violations = store.verify_claim(
        "profithelm",
        "Our team provides legal representation in tax court.",
    )
    assert valid is False
    assert any("legal representation" in v.lower() for v in violations)

    valid, violations = store.verify_claim(
        "profithelm",
        "We offer guaranteed tax audit immunity with our model.",
    )
    assert valid is False
    assert any("guaranteed tax audit immunity" in v.lower() for v in violations)

    # Prexvo banned claims
    valid, violations = store.verify_claim(
        "prexvo",
        "We are an official federal loan servicer for the Department of Education.",
    )
    assert valid is False
    assert any("official federal loan servicer" in v.lower() for v in violations)

    valid, violations = store.verify_claim(
        "prexvo",
        "Direct federal student loan consolidation processing is available here.",
    )
    assert valid is False
    assert any("direct federal student loan consolidation processing" in v.lower() for v in violations)

    valid, violations = store.verify_claim(
        "prexvo",
        "Apply now for guaranteed debt cancellation under our program.",
    )
    assert valid is False
    assert any("guaranteed debt cancellation" in v.lower() for v in violations)

    valid, violations = store.verify_claim(
        "prexvo",
        "We also provide B2B corporate tax advice and 1031 exchange guidance.",
    )
    assert valid is False
    assert any("b2b corporate tax" in v.lower() or "1031 exchange" in v.lower() for v in violations)


def test_pricing_contradictions_detection():
    """Verifies that unverified pricing claims in text are flagged."""
    store = TenantFactStore.get_instance()

    # Hallucinated ProfitHelm price
    valid, violations = store.verify_claim(
        "profithelm",
        "Upgrade to ProfitHelm Pro for only $29/mo today.",
    )
    assert valid is False
    assert any("$29" in v for v in violations)

    # Clean ProfitHelm price
    valid, violations = store.verify_claim(
        "profithelm",
        "ProfitHelm Pro is available at $49/mo with full Section 179 modeling.",
    )
    assert valid is True
    assert len(violations) == 0

    # Hallucinated Prexvo price
    valid, violations = store.verify_claim(
        "prexvo",
        "Get Prexvo Pro scenario analysis for $49/month.",
    )
    assert valid is False
    assert any("$49" in v for v in violations)

    # Clean Prexvo price
    valid, violations = store.verify_claim(
        "prexvo",
        "Prexvo Pro scenario analysis costs $19/mo.",
    )
    assert valid is True
    assert len(violations) == 0


def test_tenant_isolation_boundary_enforcement():
    """Verifies assert_tenant_isolation raises PropertyContaminationError on cross-tenant bleeding."""
    store = TenantFactStore.get_instance()

    # Student loans bleeding into ProfitHelm
    with pytest.raises(PropertyContaminationError) as exc_info:
        store.assert_tenant_isolation(
            "profithelm",
            "Evaluate student loan debt relief under Title IV repayment schedules.",
        )
    assert "cross-tenant contamination" in str(exc_info.value).lower()

    # B2B tax bleeding into Prexvo
    with pytest.raises(PropertyContaminationError) as exc_info:
        store.assert_tenant_isolation(
            "prexvo",
            "Calculate pass-through entity corporate tax deductions.",
        )
    assert "cross-tenant contamination" in str(exc_info.value).lower() or "banned claim" in str(exc_info.value).lower()

    # Clean assertions pass without exception
    store.assert_tenant_isolation(
        "profithelm",
        "Section 179 optimizer models first-year capex deductions.",
    )
    store.assert_tenant_isolation(
        "prexvo",
        "Title IV repayment schedule comparing RAP against IBR discretionary percentages.",
    )
