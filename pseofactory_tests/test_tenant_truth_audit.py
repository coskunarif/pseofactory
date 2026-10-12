"""
Integration tests for pseofactory Tenant Truth Audit & Single-Scale Action Arbitration
Verifies:
1. Gate 11 (Tenant Fact Parity Gate) in audit_rendered_asset and ContentAccuracyAuditStage.
2. Strict mode ContentAccuracyAuditError raising on truth contradictions.
3. Live dist truth scanning via LiveTruthAuditEngine and AssetIntegrityEvaluator.
4. Single-scale action arbitration hierarchy (P0 Truth > P1 Indexing > P2 Refactor > P3 Build).

Zero em-dashes. Zero en-dashes.
"""

from pathlib import Path
import pytest

from pseofactory.audit import (
    audit_rendered_asset,
    ContentAccuracyAuditStage,
    ContentAccuracyAuditError,
    ContentAccuracyAuditReport,
)
from pseofactory.compiler import compile_high_effort_page
from pseofactory.maintenance import (
    DriftReason,
    AssetDriftRecord,
    LiveTruthAuditEngine,
    AssetIntegrityEvaluator,
    ConfigurablePropertyAdapter,
)
from pseofactory.pipeline import (
    arbitrate_actions,
    FactoryPipeline,
)
from pseofactory.trends.models import FeedSpike


@pytest.fixture
def clean_profithelm_spec():
    return {
        "query": "section 179 equipment expense tax deduction calculator",
        "slug": "section-179-equipment-expense-tax-deduction-calculator",
        "tenant": "profithelm",
        "statutory_authority": "IRC Section 179(b)(1)",
        "economic_dataset": "FRED CPILFESL Series",
        "model_name": "Section 179 Grounded Model",
        "formula": "min(cost, cap)",
        "inputs": {"cost": 400000, "cap": 1220000},
        "published_output": 400000.0,
        "sample_calculation": "Cost 400,000 under cap 1,220,000 gives 400,000 deduction",
        "canonical_base": "https://profithelm.com",
    }


@pytest.fixture
def clean_prexvo_spec():
    return {
        "query": "direct consolidation loan repayment assistance plan estimator",
        "slug": "direct-consolidation-loan-repayment-assistance-plan-estimator",
        "tenant": "prexvo",
        "statutory_authority": "34 CFR Part 685",
        "economic_dataset": "FRED SLSTTOTAL Series",
        "model_name": "Direct Consolidation Loan Weighted Model",
        "formula": "balance * (weighted_rate / 100.0)",
        "inputs": {"balance": 45000, "weighted_rate": 6.5},
        "published_output": 2925.0,
        "sample_calculation": "Balance 45,000 at 6.5 percent weighted rate yields 2,925 annual interest",
        "canonical_base": "https://prexvo.com",
    }


# =====================================================================
# Gate 11: Tenant Fact Parity Gate Tests
# =====================================================================

def test_gate_11_clean_assets_pass(clean_profithelm_spec, clean_prexvo_spec):
    """Clean compiled assets pass Gate 11 with tenant_fact_parity == True."""
    res_ph = compile_high_effort_page(clean_profithelm_spec)
    report_ph = audit_rendered_asset(
        html_content=res_ph["html"],
        candidate_spec=clean_profithelm_spec,
        tenant="profithelm",
    )
    assert report_ph.passed is True
    assert report_ph.gate_results.get("tenant_fact_parity") is True

    res_px = compile_high_effort_page(clean_prexvo_spec)
    report_px = audit_rendered_asset(
        html_content=res_px["html"],
        candidate_spec=clean_prexvo_spec,
        tenant="prexvo",
    )
    assert report_px.passed is True
    assert report_px.gate_results.get("tenant_fact_parity") is True


def test_gate_11_hallucinated_pricing_rejected(clean_profithelm_spec, clean_prexvo_spec):
    """Hallucinated pricing claims contradict tenant pricing tiers and fail Gate 11."""
    # ProfitHelm Pro claiming $29/mo instead of $49/mo
    res_ph = compile_high_effort_page(clean_profithelm_spec)
    dirty_html_ph = res_ph["html"].replace(
        "<h1>",
        "<h1><!-- Pricing: $29/mo Pro Tier -->",
    )
    report_ph = audit_rendered_asset(
        html_content=dirty_html_ph,
        candidate_spec=clean_profithelm_spec,
        tenant="profithelm",
    )
    assert report_ph.passed is False
    assert report_ph.gate_results.get("tenant_fact_parity") is False
    assert any("unverified price claim '$29.0'" in v.lower() for v in report_ph.violations)

    # Prexvo Pro claiming $49/mo instead of $19/mo
    res_px = compile_high_effort_page(clean_prexvo_spec)
    dirty_html_px = res_px["html"].replace(
        "<h1>",
        "<h1><!-- Pricing: $49/mo Pro Tier -->",
    )
    report_px = audit_rendered_asset(
        html_content=dirty_html_px,
        candidate_spec=clean_prexvo_spec,
        tenant="prexvo",
    )
    assert report_px.passed is False
    assert report_px.gate_results.get("tenant_fact_parity") is False
    assert any("unverified price claim '$49.0'" in v.lower() for v in report_px.violations)

    # Assert strict mode raises ContentAccuracyAuditError
    stage = ContentAccuracyAuditStage(strict=True)
    with pytest.raises(ContentAccuracyAuditError):
        stage.audit(dirty_html_ph, clean_profithelm_spec, tenant="profithelm")


def test_gate_11_banned_claims_rejected(clean_profithelm_spec, clean_prexvo_spec):
    """Assets with banned marketing claims fail Gate 11."""
    # ProfitHelm claiming automated IRS filing
    res_ph = compile_high_effort_page(clean_profithelm_spec)
    dirty_html_ph = res_ph["html"] + "<p>Includes automated IRS filing for businesses.</p>"
    report_ph = audit_rendered_asset(
        html_content=dirty_html_ph,
        candidate_spec=clean_profithelm_spec,
        tenant="profithelm",
    )
    assert report_ph.passed is False
    assert report_ph.gate_results.get("tenant_fact_parity") is False
    assert any("banned claim" in v.lower() and "automated irs filing" in v.lower() for v in report_ph.violations)

    # Prexvo claiming to be official federal loan servicer
    res_px = compile_high_effort_page(clean_prexvo_spec)
    dirty_html_px = res_px["html"] + "<p>We are an official federal loan servicer partner.</p>"
    report_px = audit_rendered_asset(
        html_content=dirty_html_px,
        candidate_spec=clean_prexvo_spec,
        tenant="prexvo",
    )
    assert report_px.passed is False
    assert report_px.gate_results.get("tenant_fact_parity") is False
    assert any("banned claim" in v.lower() and "official federal loan servicer" in v.lower() for v in report_px.violations)


def test_gate_11_missing_mandatory_ymyl_disclaimer(clean_prexvo_spec):
    """Prexvo refinance pages missing YMYL forfeiture disclaimer fail Gate 11."""
    res_px = compile_high_effort_page(clean_prexvo_spec)

    # Refinance page without disclaimer fails
    refinance_dirty = res_px["html"] + "<p>Compare student loan refinance offers from leading private lenders.</p>"
    report = audit_rendered_asset(
        html_content=refinance_dirty,
        candidate_spec=clean_prexvo_spec,
        tenant="prexvo",
    )
    assert report.passed is False
    assert report.gate_results.get("tenant_fact_parity") is False
    assert any("ymyl forfeiture disclaimer" in v.lower() for v in report.violations)

    # Refinance page with disclaimer passes Gate 11
    refinance_clean = (
        refinance_dirty
        + "<p>Refinancing federal student loans permanently waives federal protections including IDR and PSLF.</p>"
    )
    report_clean = audit_rendered_asset(
        html_content=refinance_clean,
        candidate_spec=clean_prexvo_spec,
        tenant="prexvo",
    )
    assert report_clean.passed is True
    assert report_clean.gate_results.get("tenant_fact_parity") is True


# =====================================================================
# Live Dist Truth Audit Engine Tests
# =====================================================================

def test_live_truth_audit_engine_dist_scan(tmp_path):
    """Verifies LiveTruthAuditEngine scans dist directory and catches contradictions."""
    engine = LiveTruthAuditEngine()
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()

    # Clean HTML asset
    clean_html = "<html><body><h1>Clean Tool</h1><p>Compliant statutory calculation.</p></body></html>"
    (dist_dir / "clean.html").write_text(clean_html, encoding="utf-8")

    # Contradicted HTML asset with banned claim
    dirty_html = "<html><body><h1>Dirty Tool</h1><p>We provide legal representation in court.</p></body></html>"
    (dist_dir / "dirty.html").write_text(dirty_html, encoding="utf-8")

    drift_records = engine.scan_dist_dir(dist_dir, property_id="profithelm")
    assert len(drift_records) == 1
    rec = drift_records[0]
    assert rec.slug == "dirty"
    assert DriftReason.TRUTH_CONTRADICTION in rec.reasons
    assert any("legal representation" in d.lower() for d in rec.details)


def test_asset_integrity_evaluator_flags_truth_contradiction(tmp_path):
    """Verifies AssetIntegrityEvaluator flags DriftReason.TRUTH_CONTRADICTION."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    adapter = ConfigurablePropertyAdapter(
        property_id="profithelm",
        brand_name="ProfitHelm",
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        dist_dir=dist_dir,
    )

    dirty_file = dist_dir / "bad_price.html"
    dirty_file.write_text(
        "<html><body><h1>Pricing</h1><p>ProfitHelm Pro is only $29/mo!</p></body></html>",
        encoding="utf-8",
    )

    evaluator = AssetIntegrityEvaluator()
    rec = evaluator.audit_asset(dirty_file, adapter=adapter)

    assert rec is not None
    assert DriftReason.TRUTH_CONTRADICTION in rec.reasons
    assert any("unverified price claim '$29.0'" in d.lower() for d in rec.details)


# =====================================================================
# Action Arbitration & Prioritization Tests
# =====================================================================

def test_arbitrate_actions_prioritization():
    """
    Verifies single-scale arbitration hierarchy:
    Rank 1 (P0): TRUTH_CONTRADICTION & PROPERTY_CONTAMINATION
    Rank 2 (P1): INDEXING_DEFECT
    Rank 3 (P2): REFACTOR_PAGE
    Rank 4 (P3): BUILD_PAGE
    """
    spike = FeedSpike(
        id="test-spike-01",
        query="section 179 vehicle deduction",
        source="google_suggest",
        detected_at="2026-10-12T00:00:00Z",
        sample_count=1000,
        velocity=50.0,
        acceleration=10.0,
        z_score=3.0,
        baseline_mean=5.0,
        baseline_std=1.0,
    )

    truth_record = AssetDriftRecord(
        asset_path="/dist/bad.html",
        slug="bad",
        reasons=[DriftReason.TRUTH_CONTRADICTION],
        details=["Unverified price claim $29/mo"],
    )

    contamination_record = AssetDriftRecord(
        asset_path="/dist/cross.html",
        slug="cross",
        reasons=[DriftReason.PROPERTY_CONTAMINATION],
        details=["Foreign tokens"],
    )

    refactor_record = AssetDriftRecord(
        asset_path="/dist/old.html",
        slug="old",
        reasons=[DriftReason.ENGINE_HASH_DRIFT],
        details=["Hash drift"],
    )

    # 1. Truth contradiction (P0) preempts new spike (P3)
    action, payload = arbitrate_actions(
        spikes=[spike],
        drift_records=[truth_record],
    )
    assert action == "REPAIR_TRUTH_CONTRADICTION"
    assert payload is truth_record

    # 2. Contamination (P0) preempts new spike (P3)
    action, payload = arbitrate_actions(
        spikes=[spike],
        drift_records=[contamination_record],
    )
    assert action == "REPAIR_PROPERTY_CONTAMINATION"
    assert payload is contamination_record

    # 3. Indexing defect (P1) preempts refactor (P2) and build (P3)
    action, payload = arbitrate_actions(
        spikes=[spike],
        indexing_defects=["https://profithelm.com/tools/missing-canonical"],
        refactor_candidates=[refactor_record],
    )
    assert action == "REPAIR_INDEXING_DEFECT"
    assert payload == "https://profithelm.com/tools/missing-canonical"

    # 4. Refactor page (P2) preempts new build (P3)
    action, payload = arbitrate_actions(
        spikes=[spike],
        refactor_candidates=[refactor_record],
    )
    assert action == "REFACTOR_PAGE"
    assert payload is refactor_record

    # 5. Build page (P3) executed when no defects exist
    action, payload = arbitrate_actions(
        spikes=[spike],
    )
    assert action == "BUILD_PAGE"
    assert payload is spike

    # 6. FactoryPipeline instance method produces identical ranking
    pipeline = FactoryPipeline()
    p_action, p_payload = pipeline.arbitrate_actions(
        spikes=[spike],
        drift_records=[truth_record],
    )
    assert p_action == "REPAIR_TRUTH_CONTRADICTION"
    assert p_payload is truth_record
