"""
Tests for pseofactory Content Accuracy & Truthfulness Audit Stage
Covers:
- 10 mechanical truthfulness and accuracy gates unit verification
- Positive clean audit tests for ProfitHelm and Prexvo assets
- Multi-tenant batch execution with 100% clean audit pass
- Negative stress-tests asserting immediate fail-closed rejection
  and zero disk persistence:
  1. Tampered statutory authority citation
  2. Formula evaluation / published output mismatch
  3. Empty template variable leakage ({undefined_key})
  4. Synthetic mock markers in data table
  5. Corrupted Schema.org JSON-LD
  6. Anti-slop forbidden dashes (em-dash and en-dash)
  7. Corrupted touch target (< 44px)
- Non-strict advisory audit mode verification
- Strict mode ContentAccuracyAuditError exception raising
Zero em-dashes. Zero en-dashes.
"""

from pathlib import Path
import pytest

from pseofactory.audit import (
    ContentAccuracyAuditStage,
    ContentAccuracyAuditReport,
    ContentAccuracyAuditError,
    audit_rendered_asset,
)
from pseofactory.compiler import compile_high_effort_page
from pseofactory.pipeline import (
    FactoryPipeline,
    PipelineConfig,
    RejectionReason,
    run_factory_pipeline,
)
from pseofactory.trends.models import FeedSpike


@pytest.fixture
def profithelm_spec():
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
def prexvo_spec():
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


def _make_pipeline_spike(spike_id: str, query: str, tenant: str, candidate_spec: dict = None) -> FeedSpike:
    payload = {
        "id": spike_id,
        "query": query,
        "tenant": tenant,
        "source": "google_suggest",
        "detected_at": "2026-10-09T08:00:00Z",
        "sample_count": 1500,
        "velocity": 45.0,
        "acceleration": 12.0,
        "z_score": 3.5,
        "baseline_mean": 8.0,
        "baseline_std": 2.0,
        "treg_mock": {
            "search_volume": 4000,
            "cpc_usd": 4.50,
            "competition_index": 0.25,
            "keyword_difficulty": 16.0,
            "position_zero_vacant": True,
        },
        "jev_mock": {
            "jev_score": 1.85,
            "durable_prob": 0.92,
            "category": "calculator",
        },
        "incumbents": [
            {
                "domain": "incumbent-test.com",
                "rank": 1,
                "title": "General Guide",
                "weakness_category": "lack_of_formulas",
                "weakness_detail": "Provides static tables without AST formula evaluation",
            }
        ],
        "candidate_angles": [
            {
                "angle_id": f"{tenant}-underdog-01",
                "archetype": "Free Interactive Tool/Calculator",
                "target_audience_niche": "B2B commercial operators",
                "problem_scope": "Real-time progressive statutory computation",
                "geographic_or_vertical_bound": "US Federal Code",
                "primary_value_proposition": "Interactive AST verified deduction engine",
                "first_party_utility_asset": "statutory-tool",
                "divergence_score_min": 0.55,
            }
        ],
    }
    if candidate_spec:
        payload["candidate_spec"] = candidate_spec
    return FeedSpike.from_dict(payload)


# =====================================================================
# Positive Clean Audit Tests
# =====================================================================

def test_audit_stage_clean_profithelm_asset(profithelm_spec):
    """Clean ProfitHelm asset passes all 10 gates with zero violations."""
    res = compile_high_effort_page(profithelm_spec)
    report = audit_rendered_asset(
        html_content=res["html"],
        candidate_spec=profithelm_spec,
        tenant="profithelm",
    )
    assert report.passed is True
    assert len(report.violations) == 0
    assert report.evaluated_output == pytest.approx(400000.0, rel=1e-4)
    assert report.published_output == pytest.approx(400000.0, rel=1e-4)

    expected_gates = [
        "title_h1_parity",
        "model_name_truthfulness",
        "statutory_authority_provenance",
        "economic_dataset_grounding",
        "formula_evaluation_parity",
        "table_cell_truthfulness",
        "template_leakage_free",
        "structural_components",
        "schema_jsonld_parity",
        "antislop_and_touch_target",
    ]
    for g in expected_gates:
        assert report.gate_results[g] is True, f"Gate '{g}' should pass on clean asset"


def test_audit_stage_clean_prexvo_asset(prexvo_spec):
    """Clean Prexvo asset passes all 10 gates with zero violations."""
    res = compile_high_effort_page(prexvo_spec)
    report = audit_rendered_asset(
        html_content=res["html"],
        candidate_spec=prexvo_spec,
        tenant="prexvo",
    )
    assert report.passed is True
    assert len(report.violations) == 0
    assert report.evaluated_output == pytest.approx(2925.0, rel=1e-4)
    assert report.published_output == pytest.approx(2925.0, rel=1e-4)
    for k, v in report.gate_results.items():
        assert v is True, f"Gate '{k}' should pass on clean asset"


def test_audit_stage_multi_tenant_batch_clean_pipeline(tmp_path):
    """
    Multi-tenant batch (ProfitHelm + Prexvo) executes through FactoryPipeline.
    100% of compiled assets pass audit, and disk files persist cleanly.
    """
    spikes = [
        _make_pipeline_spike(
            spike_id="spike-profithelm-clean",
            query="section 179 equipment expense tax deduction calculator",
            tenant="profithelm",
        ),
        _make_pipeline_spike(
            spike_id="spike-prexvo-clean",
            query="direct consolidation loan repayment assistance plan estimator",
            tenant="prexvo",
        ),
    ]

    out_dir = tmp_path / "dist"
    config = PipelineConfig(strict_audit=True)
    result = run_factory_pipeline(spikes=spikes, config=config, output_dir=out_dir)

    assert result.total_spikes == 2
    assert result.compiled_count == 2
    assert result.aborted_count == 0
    assert len(result.compiled_assets) == 2

    for ca in result.compiled_assets:
        assert ca.audit_passed is True
        assert ca.audit_report is not None
        assert ca.audit_report["passed"] is True
        assert ca.output_file is not None
        assert Path(ca.output_file).exists()


# =====================================================================
# Gate-by-Gate Boundary Failure Stress-Tests
# =====================================================================

def test_audit_gate_1_title_h1_parity_mismatch(profithelm_spec):
    """Tampered H1 or title tag triggers Gate 1 failure."""
    res = compile_high_effort_page(profithelm_spec)
    tampered_html = res["html"].replace("<h1>", "<h1>Modified Title Drift ")

    report = audit_rendered_asset(tampered_html, profithelm_spec, "profithelm")
    assert report.passed is False
    assert report.gate_results["title_h1_parity"] is False
    assert any("Title & H1 Parity" in v for v in report.violations)


def test_audit_gate_2_model_name_truthfulness_mismatch(profithelm_spec):
    """Altered or missing model_name triggers Gate 2 failure."""
    res = compile_high_effort_page(profithelm_spec)
    bad_spec = dict(profithelm_spec, model_name="Nonexistent Model Name")

    report = audit_rendered_asset(res["html"], bad_spec, "profithelm")
    assert report.passed is False
    assert report.gate_results["model_name_truthfulness"] is False
    assert any("Model Name" in v for v in report.violations)


def test_audit_gate_3_statutory_authority_provenance_tampered(profithelm_spec):
    """Tampered statutory authority citation triggers Gate 3 failure."""
    res = compile_high_effort_page(profithelm_spec)
    bad_spec = dict(profithelm_spec, statutory_authority="IRC Section 9999(x)")

    report = audit_rendered_asset(res["html"], bad_spec, "profithelm")
    assert report.passed is False
    assert report.gate_results["statutory_authority_provenance"] is False
    assert any("Statutory Authority" in v for v in report.violations)


def test_audit_gate_4_economic_dataset_grounding_tampered(profithelm_spec):
    """Tampered economic dataset benchmark triggers Gate 4 failure."""
    res = compile_high_effort_page(profithelm_spec)
    bad_spec = dict(profithelm_spec, economic_dataset="Synthetic Unverified Dataset")

    report = audit_rendered_asset(res["html"], bad_spec, "profithelm")
    assert report.passed is False
    assert report.gate_results["economic_dataset_grounding"] is False
    assert any("Economic Dataset" in v for v in report.violations)


def test_audit_gate_5_formula_output_mismatch(profithelm_spec):
    """Mathematical mismatch between AST evaluation and published output triggers Gate 5."""
    res = compile_high_effort_page(profithelm_spec)
    tampered_html = res["html"].replace(
        '<strong class="output-value">400,000</strong>',
        '<strong class="output-value">999,999</strong>',
    )

    report = audit_rendered_asset(tampered_html, profithelm_spec, "profithelm")
    assert report.passed is False
    assert report.gate_results["formula_evaluation_parity"] is False
    assert any("Formula Parity" in v for v in report.violations)


def test_audit_gate_6_table_cell_synthetic_mock_marker(profithelm_spec):
    """Synthetic mock/dummy markers or illegal NaN/null in data table trigger Gate 6."""
    res = compile_high_effort_page(profithelm_spec)
    tampered_html = res["html"].replace("<td>Cost</td>", "<td>mock data point</td>")

    report = audit_rendered_asset(tampered_html, profithelm_spec, "profithelm")
    assert report.passed is False
    assert report.gate_results["table_cell_truthfulness"] is False
    assert any("Table Cells" in v for v in report.violations)


def test_audit_gate_7_empty_template_variable_leakage(profithelm_spec):
    """Unrendered format string ({undefined_key}) triggers Gate 7."""
    res = compile_high_effort_page(profithelm_spec)
    tampered_html = res["html"].replace("</div>", " {undefined_template_key} </div>", 1)

    report = audit_rendered_asset(tampered_html, profithelm_spec, "profithelm")
    assert report.passed is False
    assert report.gate_results["template_leakage_free"] is False
    assert any("Template Leakage" in v for v in report.violations)


def test_audit_gate_8_missing_structural_component(profithelm_spec):
    """Omission of mandatory structural components triggers Gate 8."""
    res = compile_high_effort_page(profithelm_spec)
    tampered_html = res["html"].replace('class="result-box"', 'class="removed-box"')

    report = audit_rendered_asset(tampered_html, profithelm_spec, "profithelm")
    assert report.passed is False
    assert report.gate_results["structural_components"] is False
    assert any("Structural Components" in v for v in report.violations)


def test_audit_gate_9_corrupted_schema_jsonld(profithelm_spec):
    """Corrupted Schema.org JSON-LD (e.g. invalid type or missing FAQ answers) triggers Gate 9."""
    res = compile_high_effort_page(profithelm_spec)
    tampered_html = res["html"].replace('"SoftwareApplication"', '"CorruptedApplication"')

    report = audit_rendered_asset(tampered_html, profithelm_spec, "profithelm")
    assert report.passed is False
    assert report.gate_results["schema_jsonld_parity"] is False
    assert any("Schema.org" in v for v in report.violations)


def test_audit_gate_10_anti_slop_forbidden_dashes(profithelm_spec):
    """Forbidden em-dash or en-dash in rendered HTML triggers Gate 10."""
    res = compile_high_effort_page(profithelm_spec)
    tampered_html = res["html"].replace("Executive", "Executive \u2014 Direct Answer")

    report = audit_rendered_asset(tampered_html, profithelm_spec, "profithelm")
    assert report.passed is False
    assert report.gate_results["antislop_and_touch_target"] is False
    assert any("Anti-Slop" in v for v in report.violations)


def test_audit_gate_10_corrupted_touch_target_below_44px(profithelm_spec):
    """Touch target dimension < 44px on calculate button triggers Gate 10."""
    res = compile_high_effort_page(profithelm_spec)
    tampered_html = res["html"].replace(
        'id="calculate-btn" style="min-height: 44px; min-width: 44px;"',
        'id="calculate-btn" style="min-height: 24px; min-width: 24px;"',
    )

    report = audit_rendered_asset(tampered_html, profithelm_spec, "profithelm")
    assert report.passed is False
    assert report.gate_results["antislop_and_touch_target"] is False
    assert any("Touch Target" in v for v in report.violations)


# =====================================================================
# Fail-Closed Pipeline Invariant: Zero Partial File Persistence
# =====================================================================

def test_pipeline_fail_closed_tampered_statutory_authority_zero_disk(tmp_path, monkeypatch):
    """
    Corrupted statutory authority citation in compiled HTML triggers AUDIT_STAGE_FAILED
    and guarantees zero disk persistence.
    """
    def _corrupted_compile(spec):
        res = compile_high_effort_page(spec)
        bad_html = res["html"].replace(spec["statutory_authority"], "IRC Section 9999(x)")
        return dict(res, html=bad_html)

    monkeypatch.setattr("pseofactory.pipeline.compile_high_effort_page", _corrupted_compile)

    spike = _make_pipeline_spike(
        spike_id="spike-corrupt-stat",
        query="section 179 equipment expense tax deduction calculator",
        tenant="profithelm",
    )
    out_dir = tmp_path / "dist"
    pipeline = FactoryPipeline(config=PipelineConfig(strict_audit=True))
    result = pipeline.execute([spike], output_dir=out_dir)

    assert result.compiled_count == 0
    assert result.aborted_count == 1
    assert result.aborted_opportunities[0].reason == RejectionReason.AUDIT_STAGE_FAILED
    assert len(result.aborted_opportunities[0].foreign_tokens) > 0

    # Strict invariant: zero disk persistence
    target_tool_dir = out_dir / "profithelm" / "tools" / "section-179-equipment-expense-tax-deduction-calculator"
    assert not target_tool_dir.exists(), "Target tool directory must not be created on audit failure"
    assert not (target_tool_dir / "index.html").exists(), "Asset file must not be written on audit failure"


def test_pipeline_fail_closed_formula_mismatch_zero_disk(tmp_path, monkeypatch):
    """
    Formula / published output mismatch in compiled HTML triggers AUDIT_STAGE_FAILED
    and guarantees zero disk persistence.
    """
    def _corrupted_compile(spec):
        res = compile_high_effort_page(spec)
        bad_html = res["html"].replace(
            '<strong class="output-value">400,000</strong>',
            '<strong class="output-value">888,888</strong>',
        )
        return dict(res, html=bad_html)

    monkeypatch.setattr("pseofactory.pipeline.compile_high_effort_page", _corrupted_compile)

    spike = _make_pipeline_spike(
        spike_id="spike-corrupt-formula",
        query="section 179 equipment expense tax deduction calculator",
        tenant="profithelm",
    )
    out_dir = tmp_path / "dist"
    pipeline = FactoryPipeline(config=PipelineConfig(strict_audit=True))
    result = pipeline.execute([spike], output_dir=out_dir)

    assert result.compiled_count == 0
    assert result.aborted_count == 1
    assert result.aborted_opportunities[0].reason == RejectionReason.AUDIT_STAGE_FAILED

    target_tool_dir = out_dir / "profithelm" / "tools" / "section-179-equipment-expense-tax-deduction-calculator"
    assert not target_tool_dir.exists()


def test_pipeline_fail_closed_template_leakage_zero_disk(tmp_path, monkeypatch):
    """
    Template variable leakage ({undefined_variable}) triggers AUDIT_STAGE_FAILED
    and guarantees zero disk persistence.
    """
    def _corrupted_compile(spec):
        res = compile_high_effort_page(spec)
        bad_html = res["html"].replace("</h1>", " {undefined_template_var}</h1>")
        return dict(res, html=bad_html)

    monkeypatch.setattr("pseofactory.pipeline.compile_high_effort_page", _corrupted_compile)

    spike = _make_pipeline_spike(
        spike_id="spike-corrupt-template",
        query="section 179 equipment expense tax deduction calculator",
        tenant="profithelm",
    )
    out_dir = tmp_path / "dist"
    pipeline = FactoryPipeline(config=PipelineConfig(strict_audit=True))
    result = pipeline.execute([spike], output_dir=out_dir)

    assert result.compiled_count == 0
    assert result.aborted_count == 1
    assert result.aborted_opportunities[0].reason == RejectionReason.AUDIT_STAGE_FAILED

    target_tool_dir = out_dir / "profithelm" / "tools" / "section-179-equipment-expense-tax-deduction-calculator"
    assert not target_tool_dir.exists()


def test_pipeline_fail_closed_synthetic_mock_table_zero_disk(tmp_path, monkeypatch):
    """
    Synthetic mock tokens in calculation table trigger AUDIT_STAGE_FAILED
    and guarantees zero disk persistence.
    """
    def _corrupted_compile(spec):
        res = compile_high_effort_page(spec)
        bad_html = res["html"].replace("<td>Cost</td>", "<td>mock dataset parameter</td>")
        return dict(res, html=bad_html)

    monkeypatch.setattr("pseofactory.pipeline.compile_high_effort_page", _corrupted_compile)

    spike = _make_pipeline_spike(
        spike_id="spike-corrupt-mock",
        query="section 179 equipment expense tax deduction calculator",
        tenant="profithelm",
    )
    out_dir = tmp_path / "dist"
    pipeline = FactoryPipeline(config=PipelineConfig(strict_audit=True))
    result = pipeline.execute([spike], output_dir=out_dir)

    assert result.compiled_count == 0
    assert result.aborted_count == 1
    assert result.aborted_opportunities[0].reason == RejectionReason.AUDIT_STAGE_FAILED

    target_tool_dir = out_dir / "profithelm" / "tools" / "section-179-equipment-expense-tax-deduction-calculator"
    assert not target_tool_dir.exists()


def test_pipeline_fail_closed_corrupted_schema_jsonld_zero_disk(tmp_path, monkeypatch):
    """
    Corrupted Schema.org JSON-LD triggers AUDIT_STAGE_FAILED
    and guarantees zero disk persistence.
    """
    def _corrupted_compile(spec):
        res = compile_high_effort_page(spec)
        bad_html = res["html"].replace('"SoftwareApplication"', '"TamperedApplication"')
        return dict(res, html=bad_html)

    monkeypatch.setattr("pseofactory.pipeline.compile_high_effort_page", _corrupted_compile)

    spike = _make_pipeline_spike(
        spike_id="spike-corrupt-jsonld",
        query="section 179 equipment expense tax deduction calculator",
        tenant="profithelm",
    )
    out_dir = tmp_path / "dist"
    pipeline = FactoryPipeline(config=PipelineConfig(strict_audit=True))
    result = pipeline.execute([spike], output_dir=out_dir)

    assert result.compiled_count == 0
    assert result.aborted_count == 1
    assert result.aborted_opportunities[0].reason == RejectionReason.AUDIT_STAGE_FAILED

    target_tool_dir = out_dir / "profithelm" / "tools" / "section-179-equipment-expense-tax-deduction-calculator"
    assert not target_tool_dir.exists()


def test_pipeline_fail_closed_anti_slop_dashes_zero_disk(tmp_path, monkeypatch):
    """
    Anti-slop forbidden dashes in compiled HTML trigger AUDIT_STAGE_FAILED
    and guarantees zero disk persistence.
    """
    def _corrupted_compile(spec):
        res = compile_high_effort_page(spec)
        # Note: compile_high_effort_page asserts clean dashes, so bypass compiler self-check
        # by tampering returned dict html directly
        bad_html = res["html"].replace("Executive", "Executive \u2014 Analysis")
        return dict(res, html=bad_html)

    monkeypatch.setattr("pseofactory.pipeline.compile_high_effort_page", _corrupted_compile)

    spike = _make_pipeline_spike(
        spike_id="spike-corrupt-dash",
        query="section 179 equipment expense tax deduction calculator",
        tenant="profithelm",
    )
    out_dir = tmp_path / "dist"
    pipeline = FactoryPipeline(config=PipelineConfig(strict_audit=True))
    result = pipeline.execute([spike], output_dir=out_dir)

    assert result.compiled_count == 0
    assert result.aborted_count == 1
    assert result.aborted_opportunities[0].reason == RejectionReason.AUDIT_STAGE_FAILED

    target_tool_dir = out_dir / "profithelm" / "tools" / "section-179-equipment-expense-tax-deduction-calculator"
    assert not target_tool_dir.exists()


def test_pipeline_fail_closed_corrupted_touch_target_zero_disk(tmp_path, monkeypatch):
    """
    Corrupted touch target (< 44px) triggers AUDIT_STAGE_FAILED
    and guarantees zero disk persistence.
    """
    def _corrupted_compile(spec):
        res = compile_high_effort_page(spec)
        bad_html = res["html"].replace(
            'id="calculate-btn" style="min-height: 44px; min-width: 44px;"',
            'id="calculate-btn" style="min-height: 20px; min-width: 20px;"',
        )
        return dict(res, html=bad_html)

    monkeypatch.setattr("pseofactory.pipeline.compile_high_effort_page", _corrupted_compile)

    spike = _make_pipeline_spike(
        spike_id="spike-corrupt-touch",
        query="section 179 equipment expense tax deduction calculator",
        tenant="profithelm",
    )
    out_dir = tmp_path / "dist"
    pipeline = FactoryPipeline(config=PipelineConfig(strict_audit=True))
    result = pipeline.execute([spike], output_dir=out_dir)

    assert result.compiled_count == 0
    assert result.aborted_count == 1
    assert result.aborted_opportunities[0].reason == RejectionReason.AUDIT_STAGE_FAILED

    target_tool_dir = out_dir / "profithelm" / "tools" / "section-179-equipment-expense-tax-deduction-calculator"
    assert not target_tool_dir.exists()


# =====================================================================
# Non-Strict Advisory Audit & Class Exceptions
# =====================================================================

def test_pipeline_non_strict_advisory_mode(tmp_path, monkeypatch):
    """
    When strict_audit=False, audit failure does NOT block disk write,
    but records audit_passed=False and audit_report in CompiledAssetResult.
    """
    def _corrupted_compile(spec):
        res = compile_high_effort_page(spec)
        bad_html = res["html"].replace(
            '<strong class="output-value">400,000</strong>',
            '<strong class="output-value">999,999</strong>',
        )
        return dict(res, html=bad_html)

    monkeypatch.setattr("pseofactory.pipeline.compile_high_effort_page", _corrupted_compile)

    spike = _make_pipeline_spike(
        spike_id="spike-advisory-01",
        query="section 179 equipment expense tax deduction calculator",
        tenant="profithelm",
    )
    out_dir = tmp_path / "dist"
    pipeline = FactoryPipeline(config=PipelineConfig(strict_audit=False))
    result = pipeline.execute([spike], output_dir=out_dir)

    assert result.compiled_count == 1
    assert result.aborted_count == 0
    ca = result.compiled_assets[0]
    assert ca.audit_passed is False
    assert ca.audit_report is not None
    assert ca.audit_report["passed"] is False
    assert (out_dir / "profithelm" / "tools" / "section-179-equipment-expense-tax-deduction-calculator" / "index.html").exists()


def test_content_accuracy_audit_stage_strict_raises_error(profithelm_spec):
    """ContentAccuracyAuditStage raises ContentAccuracyAuditError in strict mode."""
    res = compile_high_effort_page(profithelm_spec)
    stage = ContentAccuracyAuditStage(strict=True)

    bad_spec = dict(profithelm_spec, statutory_authority="IRC Section 9999(x)")
    with pytest.raises(ContentAccuracyAuditError) as exc_info:
        stage.audit(res["html"], bad_spec, "profithelm")

    assert "Content accuracy audit failed" in str(exc_info.value)
    assert exc_info.value.report is not None
    assert exc_info.value.report.passed is False
