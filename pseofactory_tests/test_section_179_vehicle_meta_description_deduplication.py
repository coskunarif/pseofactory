"""
Regression test suite for Section 179 vehicle equipment meta description deduplication.
Verifies that section-179-calculator and section-179-vehicle-equipment-deduction
produce distinct, domain-accurate meta descriptions and titles with zero em-dashes or en-dashes.
"""

from typing import Dict, Any
from pseofactory.gsc_remediation import compile_remediation_overlay_spec, _normalize_meta_120_155
from pseofactory.maintenance import RetroReflectionEngine, PROFITHELM_DEFAULT_TOOLS
from pseofactory.tenant_facts import TruthReconciliationEngine


def test_section_179_vehicle_overlay_distinct_from_root_calculator() -> None:
    """Verifies compile_remediation_overlay_spec creates unique meta description and title for vehicle deduction."""
    cand_root: Dict[str, Any] = {
        "slug": "section-179-calculator",
        "target_url": "https://profithelm.com/tools/section-179-calculator/",
        "query": "section 179 calculator",
        "position": 8.0,
        "impressions": 250,
    }
    cand_veh: Dict[str, Any] = {
        "slug": "section-179-vehicle-equipment-deduction",
        "target_url": "https://profithelm.com/tools/section-179-vehicle-equipment-deduction/",
        "query": "section 179 vehicle equipment deduction",
        "position": 12.0,
        "impressions": 180,
    }

    ov_root = compile_remediation_overlay_spec(cand_root, tenant_id="profithelm")
    ov_veh = compile_remediation_overlay_spec(cand_veh, tenant_id="profithelm")

    assert ov_root["meta_description"] != ov_veh["meta_description"]
    assert ov_root["title_rewrite"] != ov_veh["title_rewrite"]
    assert 120 <= len(ov_root["meta_description"]) <= 155
    assert 120 <= len(ov_veh["meta_description"]) <= 155
    assert "\u2014" not in ov_root["meta_description"]
    assert "\u2013" not in ov_root["meta_description"]
    assert "\u2014" not in ov_veh["meta_description"]
    assert "\u2013" not in ov_veh["meta_description"]


def test_overlay_spec_needs_heal_detects_duplicate_section_179_meta() -> None:
    """Verifies _overlay_spec_needs_heal flags duplicate root Section 179 description on vehicle deduction tool."""
    duplicate_ov: Dict[str, Any] = {
        "slug": "section-179-vehicle-equipment-deduction",
        "target_url": "https://profithelm.com/tools/section-179-vehicle-equipment-deduction/",
        "title_rewrite": "Section 179 Calculator 2026 (Form 4562) | ProfitHelm",
        "meta_description": "Calculate Section 179 deductions under IRC Section 179 ($2,560,000 cap, $4,090,000 phase-out) and Section 168(k) bonus depreciation on IRS Form 4562.",
        "quick_answer": "Under IRC Section 179 and Section 280F, commercial vehicles capture first-year expensing.",
    }

    assert RetroReflectionEngine._overlay_spec_needs_heal("section-179-vehicle-equipment-deduction", duplicate_ov) is True


def test_truth_reconciliation_heals_duplicate_section_179_meta() -> None:
    """Verifies TruthReconciliationEngine replaces duplicate root description and title with vehicle-specific copy."""
    duplicate_ov: Dict[str, Any] = {
        "slug": "section-179-vehicle-equipment-deduction",
        "target_url": "https://profithelm.com/tools/section-179-vehicle-equipment-deduction/",
        "title_rewrite": "Section 179 Calculator 2026 (Form 4562) | ProfitHelm",
        "meta_description": "Calculate Section 179 deductions under IRC Section 179 ($2,560,000 cap, $4,090,000 phase-out) and Section 168(k) bonus depreciation on IRS Form 4562.",
        "quick_answer": "Under IRC Section 179 and Section 280F, commercial vehicles capture first-year expensing.",
    }

    reconciled, changed = TruthReconciliationEngine.reconcile_overlay_spec_truth(
        duplicate_ov, tenant="profithelm", slug="section-179-vehicle-equipment-deduction"
    )

    assert changed is True
    assert reconciled["meta_description"] != duplicate_ov["meta_description"]
    assert "vehicle" in reconciled["meta_description"].lower() or "commercial" in reconciled["meta_description"].lower()
    assert 120 <= len(reconciled["meta_description"]) <= 155
    assert "\u2014" not in reconciled["meta_description"]
    assert "\u2013" not in reconciled["meta_description"]
