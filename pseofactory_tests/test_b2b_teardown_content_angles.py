"""
Unit tests for B2B SaaS Teardowns & Technical Audit Blueprints.
Verifies:
1. test_b2b_teardown_fixture_contracts: Fixture syntax, schema, required keys, zero dashes, zero leakage.
2. test_teardown_dataclass_serialization_roundtrip: TeardownEvaluationVector and PractitionerTeardownSpec roundtrip.
3. test_saas_audit_dataclass_serialization_roundtrip: TechnicalAuditChecklistItem and SaaSTechnicalAuditSpec roundtrip.
4. test_underdog_angle_with_specs_serialization_roundtrip: UnderdogAngle roundtrip and backwards compatibility.
5. test_zviadadze_bofu_teardown_divergence_oracle: Nick Zviadadze BoFU teardown triage, divergence >= 0.85, GrantOTriad.
6. test_goodey_plg_onboarding_divergence_oracle: Ben Goodey PLG onboarding teardown triage, divergence >= 0.85.
7. test_azarenko_technical_audit_divergence_oracle: Kristina Azarenko technical audit triage, divergence >= 0.85.
8. test_markdown_brief_generation_with_teardown_and_audit_specs: Brief rendering with vectors, checklists, contracts.

Zero em-dashes. Zero en-dashes.
"""

import json
import os
import pytest

from pseofactory.contracts import assert_no_forbidden_dashes, assert_no_prompt_leakage
from pseofactory.content_angles import (
    GrantOTriad,
    IncumbentSummary,
    UnderdogAngle,
    ContentAngleBrief,
    TeardownEvaluationVector,
    PractitionerTeardownSpec,
    TechnicalAuditChecklistItem,
    SaaSTechnicalAuditSpec,
    calculate_token_jaccard_divergence,
    assert_underdog_angle_divergence,
    evaluate_content_angles,
    generate_markdown_brief,
    VALID_UNDERDOG_ARCHETYPES,
)


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
B2B_FIXTURE_PATH = os.path.join(
    REPO_ROOT, "pseofactory", "fixtures", "b2b_teardown_content_angles_fixture.json"
)


def test_b2b_teardown_fixture_contracts():
    """Validates B2B teardown fixture syntax, schema, required keys, zero dashes, and zero leakage."""
    assert os.path.isfile(B2B_FIXTURE_PATH), f"Missing fixture file at {B2B_FIXTURE_PATH}"

    with open(B2B_FIXTURE_PATH, "r", encoding="utf-8") as f:
        raw_text = f.read()
        fixtures = json.loads(raw_text)

    # Contract checks on fixture json
    assert_no_forbidden_dashes(raw_text, "b2b_teardown_content_angles_fixture")
    assert_no_prompt_leakage(raw_text, "b2b_teardown_content_angles_fixture")

    assert isinstance(fixtures, list)
    assert len(fixtures) == 3

    expected_ids = {
        "b2b_saas_billing_migration_teardown",
        "b2b_saas_plg_onboarding_friction_teardown",
        "b2b_saas_faceted_catalog_audit",
    }
    found_ids = {f["fixture_id"] for f in fixtures}
    assert found_ids == expected_ids

    required_keys = [
        "fixture_id",
        "query",
        "market_segment",
        "search_intent",
        "gsc_metrics",
        "incumbents",
        "existing_site_catalog",
        "expected_triage_action",
        "underdog_angle_specs",
    ]

    for fx in fixtures:
        for k in required_keys:
            assert k in fx, f"Fixture {fx.get('fixture_id')} missing key '{k}'"
            assert fx[k] is not None

        gsc = fx["gsc_metrics"]
        for gk in ["impressions", "clicks", "position", "days_observed"]:
            assert gk in gsc
            assert isinstance(gsc[gk], (int, float))

        for inc in fx["incumbents"]:
            for ik in ["domain", "rank", "title", "weakness_category", "weakness_detail"]:
                assert ik in inc
                assert len(str(inc[ik]).strip()) > 0

        for angle in fx["underdog_angle_specs"]:
            for ak in [
                "angle_id",
                "archetype",
                "target_audience_niche",
                "problem_scope",
                "geographic_or_vertical_bound",
                "primary_value_proposition",
                "first_party_utility_asset",
                "divergence_score_min",
            ]:
                assert ak in angle
                assert len(str(angle[ak]).strip()) > 0
            assert angle["archetype"] in VALID_UNDERDOG_ARCHETYPES


def test_teardown_dataclass_serialization_roundtrip():
    """Validates TeardownEvaluationVector and PractitionerTeardownSpec roundtrip serialization."""
    vector = TeardownEvaluationVector(
        vector_id="pricing_cliff_transparency",
        benchmark_label="Effective Take-Rate at 50k MRR",
        operator_baseline="Transparent public pricing under 0.7 percent take-rate",
        incumbent_gap="Mandatory sales qualification call with 0.75 percent overage take-rate",
        verifiable_metric="0 sales calls required and $3,600 documented annual savings",
    )
    v_dict = vector.to_dict()
    v_roundtrip = TeardownEvaluationVector.from_dict(v_dict)
    assert v_roundtrip == vector
    assert v_roundtrip.vector_id == "pricing_cliff_transparency"

    spec = PractitionerTeardownSpec(
        framework_author="Nick Zviadadze BOFU Teardown Blueprint",
        teardown_subject="B2B SaaS Billing Platform Migration",
        icp_profile="Bootstrapped B2B SaaS founders processing 10k to 100k MRR",
        evaluation_vectors=[vector],
        reproducible_workflow_steps=[
            "Export customer payment token mappings from incumbent billing API",
            "Replay historical invoice webhooks through idempotency verification harness",
        ],
        utility_asset_type="interactive_comparison_matrix",
    )
    s_dict = spec.to_dict()
    s_roundtrip = PractitionerTeardownSpec.from_dict(s_dict)
    assert s_roundtrip == spec
    assert len(s_roundtrip.evaluation_vectors) == 1
    assert s_roundtrip.evaluation_vectors[0].vector_id == "pricing_cliff_transparency"
    assert len(s_roundtrip.reproducible_workflow_steps) == 2


def test_saas_audit_dataclass_serialization_roundtrip():
    """Validates TechnicalAuditChecklistItem and SaaSTechnicalAuditSpec roundtrip serialization."""
    item = TechnicalAuditChecklistItem(
        check_id="AUDIT-CRAWL-01",
        category="crawlability_indexation",
        severity="CRITICAL",
        diagnostic_rule="Faceted filter combinations with 2 or more parameters must return robots noindex",
        verification_heuristic="Verify HTTP response headers and meta robots tags on multi-parameter query URLs",
        remediation_pattern="Add canonical self-referencing base URL and inject robots noindex header",
    )
    i_dict = item.to_dict()
    i_roundtrip = TechnicalAuditChecklistItem.from_dict(i_dict)
    assert i_roundtrip == item
    assert i_roundtrip.check_id == "AUDIT-CRAWL-01"

    spec = SaaSTechnicalAuditSpec(
        framework_author="Kristina Azarenko Technical SaaS Audit Blueprint",
        audit_domain_scope="Faceted B2B SaaS application directory architecture",
        checklist=[item],
        metric_thresholds={"max_crawl_depth": 3, "min_ssr_dom_parity_pct": 98.5},
        utility_asset_type="faceted_indexation_decision_tree",
    )
    s_dict = spec.to_dict()
    s_roundtrip = SaaSTechnicalAuditSpec.from_dict(s_dict)
    assert s_roundtrip == spec
    assert len(s_roundtrip.checklist) == 1
    assert s_roundtrip.metric_thresholds["max_crawl_depth"] == 3


def test_underdog_angle_with_specs_serialization_roundtrip():
    """Validates UnderdogAngle containing teardown_spec and audit_spec serialization."""
    triad = GrantOTriad(
        audience_niche="Bootstrapped B2B SaaS founders processing 10k to 100k MRR",
        problem_scope="Subscription billing platform migration data portability",
        geographic_or_vertical_bound="Global B2B subscription software architectures",
    )
    vector = TeardownEvaluationVector(
        vector_id="vec-1",
        benchmark_label="Pricing",
        operator_baseline="Self-serve",
        incumbent_gap="Sales call",
        verifiable_metric="0 calls",
    )
    teardown = PractitionerTeardownSpec(
        framework_author="Nick Zviadadze",
        teardown_subject="Billing",
        icp_profile="SaaS founders",
        evaluation_vectors=[vector],
        reproducible_workflow_steps=["Step 1", "Step 2"],
    )
    angle = UnderdogAngle(
        angle_id="test_angle",
        triad=triad,
        archetype="Practitioner/Operator Teardown",
        primary_value_proposition="Deterministic billing migration matrix",
        first_party_utility_asset="Interactive calculator",
        divergence_score=0.92,
        teardown_spec=teardown,
    )
    a_dict = angle.to_dict()
    assert "teardown_spec" in a_dict
    assert a_dict["teardown_spec"]["framework_author"] == "Nick Zviadadze"

    a_roundtrip = UnderdogAngle.from_dict(a_dict)
    assert a_roundtrip.angle_id == angle.angle_id
    assert a_roundtrip.teardown_spec is not None
    assert a_roundtrip.teardown_spec.framework_author == "Nick Zviadadze"
    assert a_roundtrip.audit_spec is None

    # Backwards compatibility test: angle without specs
    legacy_angle = UnderdogAngle(
        angle_id="legacy_angle",
        triad=triad,
        archetype="Vertical/Niche Specificity",
        primary_value_proposition="Legacy value prop",
        first_party_utility_asset="Legacy asset",
    )
    legacy_dict = legacy_angle.to_dict()
    assert "teardown_spec" not in legacy_dict
    assert "audit_spec" not in legacy_dict
    legacy_roundtrip = UnderdogAngle.from_dict(legacy_dict)
    assert legacy_roundtrip.teardown_spec is None
    assert legacy_roundtrip.audit_spec is None


def test_zviadadze_bofu_teardown_divergence_oracle():
    """Evaluates Nick Zviadadze BoFU teardown scenario: BUILD_PAGE, divergence >= 0.85, GrantOTriad."""
    with open(B2B_FIXTURE_PATH, "r", encoding="utf-8") as f:
        fixtures = json.load(f)

    zviadadze_fx = next(
        f for f in fixtures if f["fixture_id"] == "b2b_saas_billing_migration_teardown"
    )
    brief = evaluate_content_angles(zviadadze_fx, total_site_impressions=500)

    assert brief.triage_action == "BUILD_PAGE"
    assert len(brief.angles) == 1

    angle = brief.angles[0]
    assert angle.archetype == "Practitioner/Operator Teardown"
    assert angle.divergence_score >= 0.50
    assert angle.divergence_score >= 0.85
    assert angle.teardown_spec is not None
    assert angle.teardown_spec.framework_author == "Nick Zviadadze BOFU Teardown Blueprint"
    assert len(angle.teardown_spec.evaluation_vectors) == 2

    # GrantOTriad bounds validation
    triad = angle.triad
    assert triad.validate() is True
    assert len(triad.audience_niche.strip()) > 0
    assert len(triad.problem_scope.strip()) > 0
    assert len(triad.geographic_or_vertical_bound.strip()) > 0

    # Anti-slop validators
    assert_no_forbidden_dashes(brief.markdown_brief, "Zviadadze brief")
    assert_no_prompt_leakage(brief.markdown_brief, "Zviadadze brief")


def test_goodey_plg_onboarding_divergence_oracle():
    """Evaluates Ben Goodey PLG onboarding teardown scenario: BUILD_PAGE, divergence >= 0.85."""
    with open(B2B_FIXTURE_PATH, "r", encoding="utf-8") as f:
        fixtures = json.load(f)

    goodey_fx = next(
        f for f in fixtures if f["fixture_id"] == "b2b_saas_plg_onboarding_friction_teardown"
    )
    brief = evaluate_content_angles(goodey_fx, total_site_impressions=500)

    assert brief.triage_action == "BUILD_PAGE"
    assert len(brief.angles) == 1

    angle = brief.angles[0]
    assert angle.archetype == "Practitioner/Operator Teardown"
    assert angle.divergence_score >= 0.50
    assert angle.divergence_score >= 0.85
    assert angle.teardown_spec is not None
    assert angle.teardown_spec.framework_author == "Ben Goodey SaaS Workflow Teardown Blueprint"
    assert len(angle.teardown_spec.reproducible_workflow_steps) == 3

    assert_no_forbidden_dashes(brief.markdown_brief, "Goodey brief")
    assert_no_prompt_leakage(brief.markdown_brief, "Goodey brief")


def test_azarenko_technical_audit_divergence_oracle():
    """Evaluates Kristina Azarenko technical audit scenario: BUILD_PAGE, divergence >= 0.85."""
    with open(B2B_FIXTURE_PATH, "r", encoding="utf-8") as f:
        fixtures = json.load(f)

    azarenko_fx = next(
        f for f in fixtures if f["fixture_id"] == "b2b_saas_faceted_catalog_audit"
    )
    brief = evaluate_content_angles(azarenko_fx, total_site_impressions=500)

    assert brief.triage_action == "BUILD_PAGE"
    assert len(brief.angles) == 1

    angle = brief.angles[0]
    assert angle.archetype == "Regulatory/Audit Checklist"
    assert angle.divergence_score >= 0.50
    assert angle.divergence_score >= 0.85
    assert angle.audit_spec is not None
    assert angle.audit_spec.framework_author == "Kristina Azarenko Technical SaaS Audit Blueprint"
    assert len(angle.audit_spec.checklist) == 2
    assert angle.audit_spec.metric_thresholds["max_crawl_depth"] == 3

    assert_no_forbidden_dashes(brief.markdown_brief, "Azarenko brief")
    assert_no_prompt_leakage(brief.markdown_brief, "Azarenko brief")


def test_markdown_brief_generation_with_teardown_and_audit_specs():
    """Asserts generated markdown briefs contain evaluation vectors, checklists, and pass contracts."""
    triad = GrantOTriad(
        audience_niche="B2B SaaS Growth Engineers",
        problem_scope="Frictionless Onboarding",
        geographic_or_vertical_bound="PLG Applications",
    )
    vector = TeardownEvaluationVector(
        vector_id="vec_test_1",
        benchmark_label="Time-to-Value",
        operator_baseline="Under 60 seconds",
        incumbent_gap="14 minutes with demo wall",
        verifiable_metric="60 seconds vs 14 minutes",
    )
    teardown = PractitionerTeardownSpec(
        framework_author="Ben Goodey",
        teardown_subject="Onboarding Flow",
        icp_profile="Growth PMs",
        evaluation_vectors=[vector],
        reproducible_workflow_steps=["Audit landing page", "Measure latency"],
        utility_asset_type="scorecard",
    )
    check_item = TechnicalAuditChecklistItem(
        check_id="CHECK-01",
        category="indexing",
        severity="HIGH",
        diagnostic_rule="Noindex faceted queries",
        verification_heuristic="Check curl headers",
        remediation_pattern="Inject X-Robots-Tag",
    )
    audit = SaaSTechnicalAuditSpec(
        framework_author="Kristina Azarenko",
        audit_domain_scope="Faceted Catalog",
        checklist=[check_item],
        metric_thresholds={"max_depth": 3},
        utility_asset_type="decision_tree",
    )

    angle_teardown = UnderdogAngle(
        angle_id="angle_teardown",
        triad=triad,
        archetype="Practitioner/Operator Teardown",
        primary_value_proposition="Granular onboarding breakdown",
        first_party_utility_asset="Onboarding scorecard",
        divergence_score=0.91,
        teardown_spec=teardown,
    )
    angle_audit = UnderdogAngle(
        angle_id="angle_audit",
        triad=triad,
        archetype="Regulatory/Audit Checklist",
        primary_value_proposition="Deterministic indexing checklist",
        first_party_utility_asset="Decision tree validator",
        divergence_score=0.89,
        audit_spec=audit,
    )

    incumbent = IncumbentSummary(
        domain="competitor.com",
        rank=1,
        title="Generic Guide",
        weakness_category="generic_derivative_listicle",
        weakness_detail="Lacking actionable steps",
    )

    brief_text = generate_markdown_brief(
        query="b2b saas onboarding and technical audit",
        triage_action="BUILD_PAGE",
        evaluation_summary="Qualified for page build",
        angles=[angle_teardown, angle_audit],
        incumbents=[incumbent],
        position=10.0,
        impressions=100,
    )

    # Content assertions
    assert "#### Practitioner Teardown Specification" in brief_text
    assert "Vector vec_test_1: Time-to-Value" in brief_text
    assert "Operator Baseline: Under 60 seconds" in brief_text
    assert "1. Audit landing page" in brief_text
    assert "#### SaaS Technical Audit Specification" in brief_text
    assert "Check CHECK-01 [HIGH] (indexing)" in brief_text
    assert "max_depth: 3" in brief_text

    # Anti-slop contract assertions
    assert_no_forbidden_dashes(brief_text, "Combined brief")
    assert_no_prompt_leakage(brief_text, "Combined brief")
