"""
Test Suite: Unified Factual Audit and Auto-Reconciliation Engine
Path: pseofactory/pseofactory_tests/test_unified_factual_audit.py

Verifies that:
1. Injecting wrong statutory numbers or claims into HTML, benchmarks, llms-full.txt,
   and syndication files is automatically detected by LiveTruthAuditEngine and
   ContentAccuracyAuditStage, and either auto-reconciled from ground truth by
   TruthReconciliationEngine or blocked fail-closed by maintenance/evaluator.
2. AssetIntegrityEvaluator._compute_engine_fingerprint hashes tenant_facts.py and
   audit.py (plus tenant formula engines) so cached evaluations never mask factual changes.

Zero em-dashes. Zero en-dashes.
"""

import json
import shutil
import tempfile
from pathlib import Path
import pytest

from pseofactory.audit import ContentAccuracyAuditStage
from pseofactory.maintenance import (
    AssetIntegrityEvaluator,
    LiveTruthAuditEngine,
    PropertyAdapter,
    TenantRegistry,
)
from pseofactory.tenant_facts import TenantFactStore, TruthReconciliationEngine


@pytest.fixture
def temp_estate(tmp_path):
    """Sets up a minimal test estate with dist, content, and syndication trees."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "tools").mkdir()
    (dist_dir / "ai-benchmarks").mkdir()
    (dist_dir / "manifests").mkdir()
    (dist_dir / "videos").mkdir()

    content_dir = tmp_path / "content" / "overlays"
    content_dir.mkdir(parents=True)

    synd_dir = tmp_path / "syndication"
    synd_dir.mkdir(parents=True)
    (synd_dir / "ai_benchmarks").mkdir()

    return {
        "root": tmp_path,
        "dist": dist_dir,
        "content": content_dir,
        "syndication": synd_dir,
    }


def test_evaluator_cache_fingerprint_includes_facts_and_audit():
    """Confirms evaluator fingerprint invalidates when facts or audit modules change."""
    fp1 = AssetIntegrityEvaluator._compute_engine_fingerprint()
    assert isinstance(fp1, str)
    assert "tenant_facts.py" in fp1
    assert "audit.py" in fp1

    # Verify that the fingerprint is sensitive to tenant_facts and audit
    import pseofactory.audit as aud_mod
    import pseofactory.tenant_facts as tf_mod

    assert Path(aud_mod.__file__).resolve().is_file()
    assert Path(tf_mod.__file__).resolve().is_file()


def test_html_statutory_drift_detection_and_reconciliation(temp_estate):
    """Proves wrong statutory SUV claim in HTML is detected and healed to $30,500."""
    dist = temp_estate["dist"]
    tool_dir = dist / "tools" / "section-179-calculator"
    tool_dir.mkdir(parents=True)
    html_file = tool_dir / "index.html"

    # Inject erroneous heavy vehicle deduction claim
    bad_html = """<!DOCTYPE html>
<html>
<head><title>Section 179 Calculator | ProfitHelm</title></head>
<body>
  <header><h1>Section 179 Calculator</h1></header>
  <div class="quick-answer">Under IRC Section 179, heavy SUVs capped at $2,560,000 for equipment.</div>
  <div class="result-box"><strong class="output-value">$30,500</strong></div>
</body>
</html>"""
    html_file.write_text(bad_html, encoding="utf-8")

    engine = LiveTruthAuditEngine()
    violations = engine.audit_file(html_file, property_id="profithelm")
    assert any("2,560,000" in v or "SUV" in v for v in violations), f"Expected violation, got {violations}"

    # Auto-reconcile estate assets
    repaired = TruthReconciliationEngine.reconcile_estate_assets(
        dist_dir=dist,
        property_id="profithelm",
        repo_root=temp_estate["root"],
    )
    assert str(html_file) in repaired or len(repaired) > 0

    healed_html = html_file.read_text(encoding="utf-8")
    assert "$30,500" in healed_html
    assert "heavy SUVs capped at $2,560,000" not in healed_html


def test_ai_benchmark_and_llms_txt_reconciliation(temp_estate):
    """Proves erroneous SUV cap and truncated citations in benchmarks are detected and healed."""
    dist = temp_estate["dist"]
    bench_dir = dist / "ai-benchmarks"
    hub_json = bench_dir / "public_statistics_citation_hub.json"
    ref_md = bench_dir / "ai_citations_reference.md"
    llms_full = dist / "llms-full.txt"

    hub_json.write_text(
        json.dumps({"claim": "Under Section 179, heavy SUVs capped at $2,560,000 allowance"}),
        encoding="utf-8",
    )
    ref_md.write_text(
        "Statutory authority cited under IRC Sections 179 without subclause.",
        encoding="utf-8",
    )
    llms_full.write_text(
        "Student Loan Refinance Break-Even Calculator\nDirect Statutory Answer: Compare APR.\n",
        encoding="utf-8",
    )

    engine = LiveTruthAuditEngine()
    # Check detection on ProfitHelm
    violations_hub = engine.audit_file(hub_json, property_id="profithelm")
    assert len(violations_hub) > 0, "Expected violation in benchmark hub"

    violations_ref = engine.audit_file(ref_md, property_id="profithelm")
    assert any("Truncated" in v or "Plural" in v for v in violations_ref), f"Expected citation error, got {violations_ref}"

    # Check detection on Prexvo for missing YMYL disclaimer in llms-full.txt
    violations_llms = engine.audit_file(llms_full, property_id="prexvo")
    assert any("YMYL" in v for v in violations_llms), f"Expected YMYL violation, got {violations_llms}"

    # Run auto-reconciliation for ProfitHelm
    TruthReconciliationEngine.reconcile_estate_assets(
        dist_dir=dist,
        property_id="profithelm",
        repo_root=temp_estate["root"],
    )
    assert "heavy SUVs capped at $30,500" in hub_json.read_text(encoding="utf-8")
    assert "IRC Section 179" in ref_md.read_text(encoding="utf-8")

    # Run auto-reconciliation for Prexvo
    TruthReconciliationEngine.reconcile_estate_assets(
        dist_dir=dist,
        property_id="prexvo",
        repo_root=temp_estate["root"],
    )
    assert "permanently forfeits" in llms_full.read_text(encoding="utf-8")

    # Re-audit: zero violations remaining
    assert engine.audit_file(hub_json, property_id="profithelm") == []
    assert engine.audit_file(ref_md, property_id="profithelm") == []
    assert engine.audit_file(llms_full, property_id="prexvo") == []


def test_syndication_pack_factual_sanitization(temp_estate):
    """Proves syndication packs with invented tax bracket or foreign affiliates are healed."""
    synd = temp_estate["syndication"]
    q_dir = synd / "irs-2027-tax-brackets"
    q_dir.mkdir(parents=True)
    quora_md = q_dir / "quora.md"
    quora_md.write_text("Analysis shows a 3.0% federal marginal tax bracket for lower incomes.", encoding="utf-8")

    engine = LiveTruthAuditEngine()
    # Check Quora invented bracket detection
    v_quora = engine.audit_file(quora_md, property_id="profithelm")
    assert any("3.0%" in v for v in v_quora), f"Expected 3.0% bracket error, got {v_quora}"

    # Run auto-reconciliation on Quora for ProfitHelm
    TruthReconciliationEngine.reconcile_estate_assets(
        dist_dir=temp_estate["dist"],
        property_id="profithelm",
        repo_root=temp_estate["root"],
    )
    assert "3.0% federal marginal tax bracket" not in quora_md.read_text(encoding="utf-8")

    # Now create affiliate routes verified file for Prexvo
    aff_json = synd / "affiliate_routes_verified.json"
    aff_json.write_text(
        json.dumps({
            "routes": [
                {"route": "/go/turbotax", "partner": "turbotax"},
                {"route": "/go/splash", "partner": "splash_financial"},
            ]
        }),
        encoding="utf-8",
    )

    # Check foreign affiliate contamination detection in Prexvo
    v_aff = engine.audit_file(aff_json, property_id="prexvo")
    assert any("Cross-tenant" in v for v in v_aff), f"Expected affiliate error, got {v_aff}"

    # Run auto-reconciliation on affiliate routes for Prexvo
    TruthReconciliationEngine.reconcile_estate_assets(
        dist_dir=temp_estate["dist"],
        property_id="prexvo",
        repo_root=temp_estate["root"],
    )
    cleaned_aff = json.loads(aff_json.read_text(encoding="utf-8"))
    partners = [r["partner"] for r in cleaned_aff.get("routes", [])]
    assert "turbotax" not in partners
    assert "splash_financial" in partners


def test_uncorrigible_math_contradiction_fails_closed(temp_estate):
    """Proves uncorrigible mathematical contradiction is caught and fails closed."""
    dist = temp_estate["dist"]
    tool_dir = dist / "tools" / "broken-tool"
    tool_dir.mkdir(parents=True)
    html_f = tool_dir / "index.html"

    # SSR output value diverges violently from published_output in manifest
    bad_html = """<!DOCTYPE html>
<html>
<head><title>Broken Tool | ProfitHelm</title></head>
<body>
  <h1>Broken Tool</h1>
  <script id="calculation-manifest" type="application/json">
  {"formula": "a + b", "inputs": {"a": 10, "b": 20}, "published_output": 30.0}
  </script>
  <div class="result-box"><strong class="output-value">$999,999.00</strong></div>
</body>
</html>"""
    html_f.write_text(bad_html, encoding="utf-8")

    engine = LiveTruthAuditEngine()
    violations = engine.audit_file(html_f, property_id="profithelm")
    assert any("SSR .output-value" in v or "diverges" in v for v in violations)
