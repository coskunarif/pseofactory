"""
Wave 1 Lane E1 Regression Tests:
- compliance.py: GSC-SPAM-02 script/style stripping, GSC-SPAM-03 Porcelain FAQ cards & HTML unescape,
  GSC-HELP-03 .quick-answer presence & 40-60 word invariant.
- verifier.py: MasterSEOVerifier dynamic .pseofactory.json backfill for all tenants (gainhelm, prexvo,
  5th+ sites) and zero RetroReflectionEngine.retrofit_estate mutations in read-only audit helpers.
- maintenance.py: _compute_engine_fingerprint full pseofactory/*.py tree & dynamic .pseofactory.json
  tenant discovery, and fail-closed IndexingPreflightEngine exception handling.

Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from pseofactory.compiler import compile_high_effort_page
from pseofactory.compliance import ComplianceStatus, GoogleSearchCentralComplianceMatrix
from pseofactory.maintenance import (
    AssetIntegrityEvaluator,
    ConfigurablePropertyAdapter,
    MaintenanceLifecycle,
    RetroReflectionEngine,
)
from pseofactory.verifier import (
    MasterSEOVerifier,
    audit_estate_technical_seo_and_cannibalization,
    evaluate_x_like_2102328294410461564_capability_matrix,
    evaluate_x_like_2108272246804648049_capability_matrix,
    evaluate_x_like_2109219955271196726_capability_matrix,
    evaluate_x_like_2109835011772035193_capability_matrix,
)


def _base_spec() -> dict:
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


def test_gsc_spam_02_ignores_script_and_style_regex_braces():
    """GSC-SPAM-02 must strip <script>/<style> before scanning for {token} format leakage."""
    spec = _base_spec()
    html_doc = compile_high_effort_page(spec)["html"]
    html_with_js_regex = html_doc.replace(
        "</body>",
        "<script>const fmtRe = /\\B(?=(\\d{3})+(?!\\d))/g;</script>"
        "<style>.card { margin: 0; }</style></body>",
        1,
    )

    matrix = GoogleSearchCentralComplianceMatrix()
    report = matrix.audit_single_asset(html_with_js_regex, spec)
    spam02 = report.verdicts_by_principle["GSC-SPAM-02"]
    assert spam02.status == ComplianceStatus.PASS
    assert spam02.violations == []


def test_gsc_spam_03_accepts_porcelain_faq_cards_and_html_entities():
    """GSC-SPAM-03 must accept Porcelain <details class='faq-item faq-card'> and HTML-unescape text."""
    spec = _base_spec()
    html_doc = compile_high_effort_page(spec)["html"]
    porcelain_html = html_doc.replace(
        '<details class="faq-accordion">',
        '<details class="faq-item faq-card" data-overlay-faq="true">',
    )
    porcelain_html = porcelain_html.replace("IRC Section 179(b)(1)", "IRC Section 179&#x28;b&#x29;&#x28;1&#x29;")

    # Keep JSON-LD unescaped while visible HTML uses entity-encoded text
    idx_ld = porcelain_html.find("</script>")
    assert idx_ld != -1

    matrix = GoogleSearchCentralComplianceMatrix()
    report = matrix.audit_single_asset(porcelain_html, spec)
    spam03 = report.verdicts_by_principle["GSC-SPAM-03"]
    assert spam03.status == ComplianceStatus.PASS, f"Unexpected violations: {spam03.violations}"


def test_gsc_help_03_enforces_quick_answer_presence_and_word_range():
    """GSC-HELP-03 must fail when .quick-answer is missing or outside 40-60 words."""
    spec = _base_spec()
    html_doc = compile_high_effort_page(spec)["html"]
    matrix = GoogleSearchCentralComplianceMatrix()

    # 1. Baseline passes
    ok_rep = matrix.audit_single_asset(html_doc, spec)
    assert ok_rep.verdicts_by_principle["GSC-HELP-03"].status == ComplianceStatus.PASS

    # 2. Missing .quick-answer fails
    missing_qa_html = html_doc.replace('class="quick-answer"', 'class="legacy-summary"')
    miss_rep = matrix.audit_single_asset(missing_qa_html, spec)
    assert miss_rep.verdicts_by_principle["GSC-HELP-03"].status == ComplianceStatus.FAIL
    assert miss_rep.overall_pass is False

    # 3. Too short .quick-answer (<40 words) fails
    start = html_doc.index('<aside class="quick-answer"')
    end = html_doc.index("</aside>", start) + len("</aside>")
    short_qa_html = (
        html_doc[:start]
        + '<aside class="quick-answer"><p>Short summary only.</p></aside>'
        + html_doc[end:]
    )
    short_rep = matrix.audit_single_asset(short_qa_html, spec)
    assert short_rep.verdicts_by_principle["GSC-HELP-03"].status == ComplianceStatus.FAIL
    assert short_rep.overall_pass is False

    # 4. Too long .quick-answer (>60 words) fails
    long_words = " ".join(f"word{i}" for i in range(65))
    long_qa_html = (
        html_doc[:start]
        + f'<aside class="quick-answer"><p>{long_words}</p></aside>'
        + html_doc[end:]
    )
    long_rep = matrix.audit_single_asset(long_qa_html, spec)
    assert long_rep.verdicts_by_principle["GSC-HELP-03"].status == ComplianceStatus.FAIL
    assert long_rep.overall_pass is False


def test_master_seo_verifier_backfills_all_pseofactory_tenants(tmp_path: Path):
    """MasterSEOVerifier must backfill domain/canonical_base/brand_name for any .pseofactory.json tenant."""
    # 1. Existing tenants (gainhelm, prexvo) when constructed from dist_dir only
    for repo_name, expected_domain, expected_brand in (
        ("gainhelm", "gainhelm.com", "GainHelm"),
        ("prexvo", "prexvo.com", "Prexvo"),
    ):
        dist_dir = Path("/home/ubuntuadmin/projects") / repo_name / "dist"
        if dist_dir.is_dir():
            v = MasterSEOVerifier(dist_dir=dist_dir, allow_mutations=False)
            assert v.domain == expected_domain
            assert v.canonical_base == f"https://{expected_domain}"
            assert v.brand_name == expected_brand

    # 2. Synthetic 5th+ tenant in tmp_path with .pseofactory.json
    fifth_repo = tmp_path / "acmecorp"
    fifth_dist = fifth_repo / "dist"
    fifth_dist.mkdir(parents=True)
    (fifth_repo / ".pseofactory.json").write_text(
        json.dumps(
            {
                "property_id": "acmecorp",
                "domain": "acmecorp.com",
                "canonical_base": "https://acmecorp.com",
                "brand_name": "AcmeCorp",
                "package_name": "acmecorp",
                "dist_dir": "dist",
            }
        ),
        encoding="utf-8",
    )
    (fifth_dist / "index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><title>AcmeCorp</title>"
        "<link rel='canonical' href='https://acmecorp.com/'></head>"
        "<body><h1>AcmeCorp</h1><a href='/about/'>About</a></body></html>",
        encoding="utf-8",
    )
    (fifth_dist / "about").mkdir()
    (fifth_dist / "about" / "index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><title>About AcmeCorp</title>"
        "<link rel='canonical' href='https://acmecorp.com/about/'></head>"
        "<body><h1>About</h1></body></html>",
        encoding="utf-8",
    )

    v_fifth = MasterSEOVerifier(dist_dir=fifth_dist, allow_mutations=False)
    assert v_fifth.domain == "acmecorp.com"
    assert v_fifth.canonical_base == "https://acmecorp.com"
    assert v_fifth.brand_name == "AcmeCorp"


def test_verifier_read_only_audits_never_call_retrofit_estate(tmp_path: Path):
    """Read-only verifier audit/evaluation helpers must never mutate estates via retrofit_estate."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text("<html><head><title>x</title></head><body></body></html>", encoding="utf-8")

    with patch.object(
        RetroReflectionEngine,
        "retrofit_estate",
        side_effect=AssertionError("Read-only audit must never call retrofit_estate"),
    ):
        rep = audit_estate_technical_seo_and_cannibalization(dist_dir=dist_dir, property_id="profithelm")
        assert rep["passed"] is False

        m1 = evaluate_x_like_2109219955271196726_capability_matrix(include_live_estate_audit=False)
        assert "matrix" in m1
        m2 = evaluate_x_like_2102328294410461564_capability_matrix(include_live_audit=False)
        assert "matrix" in m2
        m3 = evaluate_x_like_2108272246804648049_capability_matrix(include_live_tenant_check=False)
        assert "matrix" in m3
        m4 = evaluate_x_like_2109835011772035193_capability_matrix(include_live_estate_audit=False)
        assert "matrix" in m4


def test_engine_fingerprint_hashes_full_tree_and_dynamic_tenants(tmp_path: Path, monkeypatch):
    """_compute_engine_fingerprint must hash full pseofactory/*.py tree and dynamic .pseofactory.json tenants."""
    fp = AssetIntegrityEvaluator._compute_engine_fingerprint()
    for required_mod in (
        "porcelain_shell.py:",
        "verifier.py:",
        "edge.py:",
        "affiliates.py:",
        "compliance.py:",
        "indexing/preflight.py:",
    ):
        assert required_mod in fp, f"Missing {required_mod} in engine fingerprint"

    # Dynamic 5th+ tenant discovery
    fake_projects = tmp_path / "projects"
    fifth_repo = fake_projects / "novabond"
    fifth_engine = fifth_repo / "novabond" / "engine"
    fifth_engine.mkdir(parents=True)
    (fifth_repo / ".pseofactory.json").write_text(
        json.dumps(
            {
                "property_id": "novabond",
                "domain": "novabond.com",
                "canonical_base": "https://novabond.com",
                "brand_name": "NovaBond",
                "package_name": "novabond",
                "dist_dir": "dist",
            }
        ),
        encoding="utf-8",
    )
    formula_file = fifth_engine / "rates.py"
    formula_file.write_text("RATE = 0.02\n", encoding="utf-8")

    import pseofactory.maintenance as maint_mod

    orig_path = Path

    class _PatchedPath(type(Path())):
        def __new__(cls, *args, **kwargs):
            if args and str(args[0]) == "/home/ubuntuadmin/projects":
                return orig_path(fake_projects)
            return orig_path(*args, **kwargs)

    monkeypatch.setattr(maint_mod, "Path", _PatchedPath)

    fp_before = AssetIntegrityEvaluator._compute_engine_fingerprint()
    assert "novabond/engine/rates.py:" in fp_before
    formula_file.write_text("RATE = 0.03\n", encoding="utf-8")
    fp_after = AssetIntegrityEvaluator._compute_engine_fingerprint()
    assert fp_before != fp_after


@pytest.mark.parametrize("dry_run", [False, True])
def test_maintenance_airlock_exception_fails_closed(tmp_path: Path, dry_run: bool):
    """IndexingPreflightEngine exceptions in MaintenanceLifecycle must fail closed (never SUCCESS/DRY_RUN)."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True)
    agy_dir = tmp_path / ".agy"
    agy_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><title>T</title>"
        "<meta name='description' content='Valid description for test page in maintenance.'></head>"
        "<body><h1>T</h1><p>Body text.</p></body></html>",
        encoding="utf-8",
    )
    adapter = ConfigurablePropertyAdapter(
        property_id="profithelm",
        brand_name="ProfitHelm",
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        dist_dir=dist_dir,
    )
    lifecycle = MaintenanceLifecycle()

    with patch(
        "pseofactory.indexing.preflight.IndexingPreflightEngine.inspect_dist",
        side_effect=RuntimeError("Preflight airlock crashed"),
    ), patch(
        "pseofactory.indexer.PushIndexer.dispatch_automated_indexing"
    ) as mock_push:
        res = lifecycle.run(
            adapter,
            force=True,
            dry_run=dry_run,
            enable_gitops=False,
            enable_distribution=False,
            state_file=agy_dir / "engine_hash.json",
            ledger_file=agy_dir / "asset_ledger.json",
        )

    assert res.indexing_status == "FAILED"
    assert res.status == "PARTIAL"
    mock_push.assert_not_called()
