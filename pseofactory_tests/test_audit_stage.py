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


def test_page_structure_geo_immediacy_and_vertical_isolation(profithelm_spec):
    """
    Verifies financial tool page structure and GEO answer-delivery invariants:
    1. H1 -> .quick-answer -> #calculator-workspace-anchor precedes .multi-dataset-join above the fold.
    2. H2 and H3 subheadings are contextualized with entity/model labels and use semantic tags (no <div id="statutory-pitfalls-matrix">).
    3. Methodology section uses concise paragraphs, a scannable <ul> list, and contextual in-prose /tools/ links.
    4. Non-179 B2B verticals (174, 301, surety, factoring, workers-comp, treasury) never receive Section 179 SUV pitfalls.
    5. GSC overlays never truncate meta descriptions at 'and audit-ready.' and synchronize FAQPage JSON-LD 1:1 with <details> FAQs.
    """
    import re
    from pseofactory.competitor import render_competitor_winning_pattern_blocks
    from pseofactory.gsc_remediation import compile_remediation_overlay_spec, inject_overlay_into_html
    from pseofactory.maintenance import RetroReflectionEngine, _extract_faq_schema_and_body_counts

    res = compile_high_effort_page(profithelm_spec)
    html_out = res["html"]

    calc_pos = html_out.find('id="calculator-workspace-anchor"')
    mdj_m = re.search(r'<(?:div|section)[^>]*class=["\'][^"\']*\bmulti-dataset-join\b', html_out)
    assert calc_pos != -1 and mdj_m is not None
    assert calc_pos < mdj_m.start(), "#calculator-workspace-anchor must appear before .multi-dataset-join"
    assert '<h3 id="statutory-pitfalls-matrix"' in html_out
    assert '<div id="statutory-pitfalls-matrix"' not in html_out

    for non_179_slug in (
        "r-and-d-tax-credit-section-174-amortization-calculator",
        "section-301-tariff-landed-cost-calculator",
        "contractor-surety-bond-cost-calculator",
        "invoice-factoring-vs-line-of-credit-apr-calculator",
        "workers-comp-and-payroll-burden-calculator",
        "treasury-bill-vs-high-yield-savings-tax-equivalent-yield-calculator",
    ):
        blocks = render_competitor_winning_pattern_blocks(
            slug=non_179_slug,
            title=non_179_slug.replace("-", " ").title(),
            property_id="profithelm",
            canonical_base="https://profithelm.com",
            statutory_authority="IRC Section 174",
            economic_dataset="BLS PPI Series",
        )
        combined = " ".join(blocks.values())
        assert "heavy SUV (6,000 to 14,000 lbs GVWR)" not in combined, f"Section 179 SUV pollution on {non_179_slug}"

        ov = compile_remediation_overlay_spec(
            {
                "slug": non_179_slug,
                "target_url": f"https://profithelm.com/tools/{non_179_slug}/",
                "query": non_179_slug.replace("-", " "),
                "position": 11.2,
                "impressions": 120,
            },
            tenant_id="profithelm",
        )
        assert 120 <= len(ov["meta_description"]) <= 155
        assert not ov["meta_description"].endswith("and audit-ready.")
        assert 40 <= len(ov["quick_answer"].split()) <= 60

    ov_scorp = compile_remediation_overlay_spec(
        {
            "slug": "s-corp-reasonable-salary-tax-calculator",
            "target_url": "https://profithelm.com/tools/s-corp-reasonable-salary-tax-calculator/",
            "query": "s corp reasonable salary tax calculator",
            "position": 10.5,
            "impressions": 200,
        },
        tenant_id="profithelm",
    )
    with_ov = inject_overlay_into_html(html_out, ov_scorp)
    retro_html, _ = RetroReflectionEngine.retrofit_html(
        with_ov,
        property_id="profithelm",
        slug="s-corp-reasonable-salary-tax-calculator",
    )
    schema_faqs, body_faqs = _extract_faq_schema_and_body_counts(retro_html)
    assert len(schema_faqs) == len(body_faqs)
    assert [q for q, _ in schema_faqs] == [q for q, _ in body_faqs]
    assert "Statutory analysis and compliance guidelines for " not in retro_html
    assert "IRC Section 1(j) Marginal Rate Tiers" not in retro_html
    assert "Revenue Ruling 74-44" in retro_html


def test_body_level_bloat_camelcase_and_llms_manifest_parity(tmp_path):
    """
    Verifies body-level anti-bloat normalization, CamelCase heading splitting,
    spoke quick-answer/meta specificity, and llms.txt / llms-full.txt synchronization.
    """
    from pseofactory.competitor import _format_safe_heading_topic
    from pseofactory.gsc_remediation import compile_remediation_overlay_spec
    from pseofactory.maintenance import RetroReflectionEngine

    assert (
        _format_safe_heading_topic(
            "SCorpReasonableSalaryTaxArbitrageModel Quantitative Model",
            "s-corp-reasonable-salary-tax-calculator",
        )
        == "S-Corp Reasonable Salary Tax"
    )
    assert (
        _format_safe_heading_topic("", "irs-2027-tax-brackets/california")
        == "California 2027 Tax Brackets"
    )
    assert (
        _format_safe_heading_topic("", "section-1031-calculator/texas")
        == "Texas Section 1031 Exchange"
    )
    assert (
        _format_safe_heading_topic("", "section-179-calculator/ford-f150-lightning")
        == "Ford F-150 Lightning EV Truck Section 179"
    )

    noisy_ov = compile_remediation_overlay_spec(
        {
            "slug": "saas-runway-calculator",
            "target_url": "https://profithelm.com/tools/saas-runway-calculator/",
            "query": '("$5m arr") site:linkedin.com/posts',
            "position": 14.0,
            "impressions": 80,
        },
        tenant_id="profithelm",
    )
    assert "linkedin.com" not in noisy_ov["title"].lower()
    assert "SaaS" in noisy_ov["title"]

    spoke_ov = compile_remediation_overlay_spec(
        {
            "slug": "irs-2027-tax-brackets/california",
            "target_url": "https://profithelm.com/tools/irs-2027-tax-brackets/california/",
            "query": "tax advisor",
            "position": 12.0,
            "impressions": 90,
        },
        tenant_id="profithelm",
    )
    assert "California" in spoke_ov["title"]
    assert "tax advisor" not in spoke_ov["title"].lower()
    assert "California 2027 Tax Brackets" in spoke_ov["quick_answer"]

    dist = tmp_path / "dist"
    tool_dir = dist / "tools" / "pslf-buyback-calculator"
    tool_dir.mkdir(parents=True)
    (tool_dir / "index.html").write_text(
        '<!doctype html><html><head>'
        '<title>PSLF Buyback Calculator</title>'
        '<meta name="description" content="Calculate PSLF buyback lump-sum payments under 34 CFR 685.219(g).">'
        '</head><body><h1>PSLF Buyback Calculator</h1>'
        '<aside class="quick-answer"><p>Under 34 CFR 685.219(g), borrowers with 120 months of public service employment can buy back eligible forbearance months.</p></aside>'
        '</body></html>',
        encoding="utf-8",
    )
    (dist / "llms.txt").write_text(
        "# Prexvo - Title IV Engine\n\n> Summary.\n\n## Available Calculators\n\n## Documentation\n- [Methodology](https://prexvo.com/methodology/)\n",
        encoding="utf-8",
    )
    (dist / "llms-full.txt").write_text(
        "# Prexvo\nPrinceton GEO Answer: Old\n",
        encoding="utf-8",
    )
    assert RetroReflectionEngine._has_stale_llms_manifests(dist, "prexvo") is True
    changed = RetroReflectionEngine.sync_tenant_llms_manifests(dist, "prexvo", canonical_base="https://prexvo.com")
    assert "llms.txt" in changed and "llms-full.txt" in changed
    assert RetroReflectionEngine._has_stale_llms_manifests(dist, "prexvo") is False

