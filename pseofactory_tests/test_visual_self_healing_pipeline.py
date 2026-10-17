"""
Automated Fault-Injection and Unattended Self-Healing Pipeline Tests.
Challenges pseofactory across all four unattended lifecycle stages:
1. Contract (contracts.py & verifier.py)
2. Audit (audit.py & AssetIntegrityEvaluator)
3. Maintenance (RefactorCascadeEngine, MaintenanceLifecycle, AutonomousLifecycleSupervisor)
4. Reflection (RetroReflectionEngine & reflect_and_recompile_all_assets)

Deliberately seeds 5 realistic classes of visual and UX flaws:
- Flaw 1: Missing or corrupted theme styles and undefined CSS custom properties (var(--...))
- Flaw 2: Unwrapped <table> elements and horizontal overflow sabotage (overflow-x: hidden, fixed 1200px width)
- Flaw 3: Cramped tap targets (< 44px inline dimensions, display: inline, cramped CSS rules)
- Flaw 4: Inverted heading typography hierarchy (h1 < h2) and cramped card geometry
- Flaw 5: Broken calculator inputs/sliders/presets (min >= max, step <= 0, disabled, NaN, bad JSON, missing sync script)

Verifies that every flaw is deterministically blocked by Contract and Audit gates,
automatically repaired by unattended Maintenance and Reflection without --force,
and verified clean in real headless Chrome (BrowserPageVerifier) on desktop and mobile viewports.
Zero em-dashes. Zero en-dashes. Zero spaced hyphens.
"""

from __future__ import annotations

from pathlib import Path
import re
import shutil

import pytest

from pseofactory.audit import audit_rendered_asset
from pseofactory.browser_verifier import UnifiedBrowserAuditor
from pseofactory.compiler import compile_high_effort_page
from pseofactory.contracts import (
    assert_tool_utility_contract,
    assert_touch_targets,
    detect_tool_utility_issues,
)
from pseofactory.drift import (
    compute_asset_fingerprint,
    record_asset_ledger,
    record_engine_hash,
)
from pseofactory.maintenance import (
    AssetIntegrityEvaluator,
    ConfigurablePropertyAdapter,
    DriftReason,
    MaintenanceLifecycle,
    RefactorCascadeEngine,
    RetroReflectionEngine,
    reflect_and_recompile_all_assets,
)
from pseofactory.supervisor import AutonomousLifecycleSupervisor
from pseofactory.visual_primitives import (
    assert_visual_and_ux_contracts,
    detect_visual_and_ux_contract_issues,
    normalize_html_visual_primitives,
)


def _build_clean_candidate_spec() -> dict:
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


def _seed_flaw_1_missing_theme_styles(html: str) -> str:
    """Seeds Flaw 1: Strips #pseo-visual-primitives and injects undefined CSS custom properties."""
    sabotaged = re.sub(
        r'<style[^>]*id=["\']pseo-visual-primitives["\'][^>]*>[\s\S]*?</style>',
        "",
        html,
        flags=re.IGNORECASE,
    )
    sabotaged = sabotaged.replace(
        "<main",
        '<main style="background-color: var(--missing-canvas-bg); color: var(--missing-ink-token);"',
        1,
    )
    return sabotaged


def _seed_flaw_2_overflowing_table(html: str) -> str:
    """Seeds Flaw 2: Unwraps <table> and injects overflow-x: hidden + width: 1200px container."""
    sabotaged = re.sub(
        r'<div[^>]*class=["\'][^"\']*\btable-wrap\b[^"\']*["\'][^>]*>\s*(<table\b[\s\S]*?</table>)\s*</div>',
        r"\1",
        html,
        count=1,
        flags=re.IGNORECASE,
    )
    sabotaged = sabotaged.replace(
        "<table",
        '<table style="overflow-x: hidden; min-width: 980px;"',
        1,
    )
    return sabotaged


def _seed_flaw_3_cramped_tap_targets(html: str) -> str:
    """Seeds Flaw 3: Injects < 44px inline dimensions, display: inline, and tiny CSS rule."""
    sabotaged = html.replace(
        "</head>",
        "<style>.tiny-tap-rule { min-height: 24px; min-width: 28px; }</style></head>",
        1,
    )
    sabotaged = re.sub(
        r"<button\b([^>]*)>",
        r'<button\1 style="height: 22px; min-height: 22px; width: 32px; display: inline; padding: 1px;">',
        sabotaged,
        count=1,
        flags=re.IGNORECASE,
    )
    return sabotaged


def _seed_flaw_4_broken_visual_hierarchy(html: str) -> str:
    """Seeds Flaw 4: Inverts h1/h2 font sizes via inline !important and cramps .card padding/radius."""
    sabotaged = re.sub(
        r"<h1\b([^>]*)>",
        r'<h1\1 style="font-size: 14px !important;">',
        html,
        count=1,
        flags=re.IGNORECASE,
    )
    sabotaged = re.sub(
        r"<h2\b([^>]*)>",
        r'<h2\1 style="font-size: 36px !important;">',
        sabotaged,
        count=1,
        flags=re.IGNORECASE,
    )
    sabotaged = re.sub(
        r'(<div\b[^>]*class=["\'][^"\']*\bcard\b[^"\']*["\'])',
        r'\1 style="padding: 2px; border-radius: 0px;"',
        sabotaged,
        count=1,
        flags=re.IGNORECASE,
    )
    return sabotaged


def _seed_flaw_5_broken_calculator_inputs(html: str) -> str:
    """
    Seeds Flaw 5:
    - Strips #pseo-runtime-sync script
    - Sabotages <input type="number"> and <input type="range"> with min="500" max="100" step="0" disabled
    - Injects malformed data-calc-preset JSON and broken .scenario-preset-link
    """
    sabotaged = re.sub(
        r'<script[^>]*id=["\']pseo-runtime-sync["\'][^>]*>[\s\S]*?</script>',
        "",
        html,
        flags=re.IGNORECASE,
    )
    sabotaged = re.sub(
        r'(<input\b[^>]*type=["\']number["\'][^>]*)>',
        r'\1 min="500" max="100" step="0" disabled>',
        sabotaged,
        count=1,
        flags=re.IGNORECASE,
    )
    sabotaged = re.sub(
        r'(<input\b[^>]*type=["\']range["\'][^>]*)>',
        r'\1 min="900" max="50" step="-5" disabled>',
        sabotaged,
        count=1,
        flags=re.IGNORECASE,
    )
    sabotaged = re.sub(
        r'data-calc-preset=(["\']).*?\1',
        'data-calc-preset="{corrupted_json"',
        sabotaged,
        count=1,
        flags=re.IGNORECASE,
    )
    sabotaged = re.sub(
        r'(<a\b[^>]*class=["\'][^"\']*scenario-preset-link[^"\']*["\'][^>]*?)href=["\'][^"\']*["\']([^>]*?)data-preset=["\'][^"\']*["\']',
        r'\1href="#"\2',
        sabotaged,
        count=1,
        flags=re.IGNORECASE,
    )
    return sabotaged


def test_stage_1_and_2_contract_and_audit_block_all_five_flaw_classes():
    """
    Verifies that Stage 1 (Contract) and Stage 2 (Audit) deterministically detect and block
    each of the 5 seeded visual and UX flaw classes when starting from a clean compiled page.
    """
    spec = _build_clean_candidate_spec()
    clean_html = compile_high_effort_page(spec)["html"]

    # Baseline clean HTML must pass both Contract and Audit stages with 0 issues
    assert detect_visual_and_ux_contract_issues(clean_html) == []
    assert assert_visual_and_ux_contracts(clean_html) is True
    assert detect_tool_utility_issues(clean_html) == []
    assert assert_tool_utility_contract(clean_html) is True
    clean_audit = audit_rendered_asset(clean_html, spec, tenant="profithelm")
    assert clean_audit.passed is True, f"Clean compiled HTML failed audit: {clean_audit.violations}"

    flaw_builders = [
        ("missing_theme_styles", _seed_flaw_1_missing_theme_styles),
        ("overflowing_table", _seed_flaw_2_overflowing_table),
        ("cramped_tap_target", _seed_flaw_3_cramped_tap_targets),
        ("broken_visual_hierarchy", _seed_flaw_4_broken_visual_hierarchy),
        ("broken_calculator_interaction", _seed_flaw_5_broken_calculator_inputs),
    ]

    from pseofactory.verifier import verify_html_tool_utility_contract

    for flaw_name, seed_fn in flaw_builders:
        sabotaged_html = seed_fn(clean_html)
        # 1. Stage 1 Contract check must flag and reject the sabotaged HTML
        issues = detect_visual_and_ux_contract_issues(sabotaged_html, rel_path=f"{flaw_name}.html")
        assert len(issues) > 0, f"Contract detector missed seeded flaw '{flaw_name}'"
        with pytest.raises(ValueError):
            assert_visual_and_ux_contracts(sabotaged_html, context=flaw_name)

        utility_issues = detect_tool_utility_issues(sabotaged_html, rel_path=f"{flaw_name}.html")
        assert len(utility_issues) > 0, f"ToolUtility contract missed seeded flaw '{flaw_name}'"
        verifier_gate = verify_html_tool_utility_contract(sabotaged_html, rel_path=f"{flaw_name}.html")
        assert verifier_gate["status"] == "FAIL", f"VerifierStage.check_tool_utility_gate missed '{flaw_name}'"

        if flaw_name == "cramped_tap_target":
            with pytest.raises(ValueError):
                assert_touch_targets(sabotaged_html, context=flaw_name)

        # 2. Stage 2 Audit check (audit_rendered_asset) must fail Gate 10
        audit_report = audit_rendered_asset(sabotaged_html, spec, tenant="profithelm")
        assert audit_report.passed is False, f"audit_rendered_asset failed to block '{flaw_name}'"
        assert audit_report.gate_results.get("antislop_and_touch_target") is False

        # 3. Deterministic self-healing via normalize_html_visual_primitives must restore 100% compliance
        healed_html, repairs = normalize_html_visual_primitives(sabotaged_html)
        assert len(repairs) > 0, f"normalize_html_visual_primitives reported 0 repairs for '{flaw_name}'"
        assert detect_visual_and_ux_contract_issues(healed_html, rel_path=f"{flaw_name}.html") == []
        assert verify_html_tool_utility_contract(healed_html, rel_path=f"{flaw_name}.html")["status"] == "PASS"
        healed_audit = audit_rendered_asset(healed_html, spec, tenant="profithelm")
        assert healed_audit.passed is True, (
            f"Self-healed HTML for '{flaw_name}' still failed audit: {healed_audit.violations}"
        )


def test_stage_3_unattended_maintenance_and_supervisor_self_heal_seeded_flaws(tmp_path):
    """
    Challenges Stage 3 (AssetIntegrityEvaluator -> RefactorCascadeEngine -> MaintenanceLifecycle
    -> AutonomousLifecycleSupervisor) without --force.
    Seeds all 5 flaw classes across compiled assets in an isolated tenant dist_dir, verifies
    unattended audit flags STRUCTURAL_CONTRACT_VIOLATION, and verifies unattended maintenance
    and supervisor self-heal every asset to 0 drift.
    """
    dist_dir = tmp_path / "dist"
    tools_dir = dist_dir / "tools" / "section-179-equipment-tax-calculator"
    tools_dir.mkdir(parents=True, exist_ok=True)
    agy_dir = tmp_path / ".agy"
    agy_dir.mkdir(parents=True, exist_ok=True)

    spec = _build_clean_candidate_spec()
    clean_tool_html = compile_high_effort_page(spec)["html"]

    # Create a non-tool landing page and a tool page, both initially clean
    landing_file = dist_dir / "index.html"
    tool_file = tools_dir / "index.html"

    clean_landing_html, _ = normalize_html_visual_primitives(
        """<!DOCTYPE html>
<html lang="en" data-theme="porcelain">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ProfitHelm Tax Intelligence</title>
  <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
  <main class="container">
    <h1>ProfitHelm Corporate Tax Calculators</h1>
    <div class="card">
      <h2>Statutory Financial Models</h2>
      <div class="table-wrap pseo-table-wrap">
        <table class="data-table">
          <thead><tr><th>Model</th><th>Authority</th><th>Status</th></tr></thead>
          <tbody><tr><td>Section 179</td><td>26 U.S.C. 179</td><td>Active</td></tr></tbody>
        </table>
      </div>
      <a href="/tools/section-179-equipment-tax-calculator/" class="btn-cta touch-target">Launch Tool</a>
    </div>
  </main>
</body>
</html>""",
        is_tenant_porcelain=True,
    )
    landing_file.write_text(clean_landing_html, encoding="utf-8")
    tool_file.write_text(clean_tool_html, encoding="utf-8")

    adapter = ConfigurablePropertyAdapter(
        property_id="profithelm_test",
        brand_name="ProfitHelm",
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        dist_dir=dist_dir,
        repo_path=tmp_path,
    )
    evaluator = AssetIntegrityEvaluator(enforce_master_seo=False)

    # Confirm baseline clean state has 0 drift
    baseline_report = evaluator.audit_all(adapter, check_engine_drift=False, check_ledger=False)
    assert baseline_report.status == "PASS"
    assert baseline_report.drifted_assets_count == 0

    # Record baseline engine hash and asset ledger
    state_file = agy_dir / "engine_hash.json"
    ledger_file = agy_dir / "asset_ledger.json"
    e_hash = record_engine_hash(state_file)
    record_asset_ledger(
        ledger_file,
        asset_hashes={
            "index.html": compute_asset_fingerprint(landing_file),
            "tools/section-179-equipment-tax-calculator/index.html": compute_asset_fingerprint(tool_file),
        },
        engine_hash=e_hash,
    )

    # Deliberately seed all 5 flaw classes into the live dist_dir files
    sabotaged_landing = _seed_flaw_1_missing_theme_styles(
        _seed_flaw_2_overflowing_table(_seed_flaw_3_cramped_tap_targets(clean_landing_html))
    )
    sabotaged_tool = _seed_flaw_1_missing_theme_styles(
        _seed_flaw_2_overflowing_table(
            _seed_flaw_3_cramped_tap_targets(
                _seed_flaw_4_broken_visual_hierarchy(_seed_flaw_5_broken_calculator_inputs(clean_tool_html))
            )
        )
    )
    landing_file.write_text(sabotaged_landing, encoding="utf-8")
    tool_file.write_text(sabotaged_tool, encoding="utf-8")

    # Unattended audit (with check_engine_drift=False, check_ledger=False, exactly as supervisor runs)
    # MUST detect both sabotaged files as STRUCTURAL_CONTRACT_VIOLATION
    sabotaged_report = evaluator.audit_all(adapter, check_engine_drift=False, check_ledger=False)
    assert sabotaged_report.status == "DRIFT"
    assert sabotaged_report.drifted_assets_count == 2
    for rec in sabotaged_report.drifted_assets:
        assert DriftReason.STRUCTURAL_CONTRACT_VIOLATION in rec.reasons

    # Run unattended MaintenanceLifecycle (force=False)
    lifecycle = MaintenanceLifecycle(
        evaluator=evaluator,
        cascade_engine=RefactorCascadeEngine(evaluator=evaluator, dlq_path=agy_dir / "dlq.json"),
    )
    maint_result = lifecycle.run(
        adapter,
        force=False,
        dry_run=False,
        state_file=state_file,
        ledger_file=ledger_file,
    )
    assert maint_result.status == "SUCCESS"
    assert maint_result.assets_failed == 0

    # Verify both files are now 100% self-healed
    post_maint_report = evaluator.audit_all(adapter, check_engine_drift=False, check_ledger=False)
    assert post_maint_report.status == "PASS", f"Remaining drift: {post_maint_report.drifted_assets}"
    assert post_maint_report.drifted_assets_count == 0

    # Now re-seed single-asset flaw (only 1 of 4 files drifted, so should_bulk_rebuild is False
    # and RefactorCascadeEngine.refactor_asset single-file path is exercised via Supervisor)
    extra_clean_file_1 = dist_dir / "about.html"
    extra_clean_file_1.write_text(clean_landing_html, encoding="utf-8")
    extra_clean_file_2 = dist_dir / "contact.html"
    extra_clean_file_2.write_text(clean_landing_html, encoding="utf-8")
    tool_file.write_text(_seed_flaw_5_broken_calculator_inputs(clean_tool_html), encoding="utf-8")

    from pseofactory.maintenance import TenantRegistry
    from pseofactory.supervisor import AsyncFleetCoordinator

    reg = TenantRegistry()
    reg.register_adapter(adapter)
    coordinator = AsyncFleetCoordinator(registry=reg, lifecycle=lifecycle)
    supervisor = AutonomousLifecycleSupervisor(
        workspace_root=tmp_path,
        registry=reg,
        coordinator=coordinator,
        state_file=state_file,
        ledger_file=ledger_file,
        heartbeat_path=agy_dir / "heartbeat.json",
    )
    sup_summary = supervisor.run_cycle(force=False, dry_run=False, enable_gitops=False)
    assert sup_summary["status"] == "SUCCESS"

    post_sup_report = evaluator.audit_all(adapter, check_engine_drift=False, check_ledger=False)
    assert post_sup_report.status == "PASS"
    assert post_sup_report.drifted_assets_count == 0


def test_stage_4_unattended_reflection_and_real_browser_verification(tmp_path):
    """
    Challenges Stage 4 (RetroReflectionEngine.audit_estate, retrofit_estate, and
    reflect_and_recompile_all_assets(force=False)) on real cloned ProfitHelm and Prexvo pages
    seeded with all 5 visual and UX flaw classes, then verifies the self-healed pages
    in real headless Chrome (UnifiedBrowserAuditor) across desktop and mobile viewports.
    """
    ph_src = Path("/home/ubuntuadmin/projects/profithelm-platform/dist")
    px_src = Path("/home/ubuntuadmin/projects/prexvo/dist")
    if not ph_src.is_dir() or not px_src.is_dir():
        pytest.skip("Tenant dist directories not present")

    ph_dist = tmp_path / "profithelm" / "dist"
    ph_tools = ph_dist / "tools" / "saas-runway-calculator"
    ph_tools.mkdir(parents=True, exist_ok=True)
    if (ph_src / "static" / "css").is_dir():
        shutil.copytree(ph_src / "static" / "css", ph_dist / "static" / "css")
    if (ph_src / "static" / "img").is_dir():
        shutil.copytree(ph_src / "static" / "img", ph_dist / "static" / "img")

    px_dist = tmp_path / "prexvo" / "dist"
    px_tools = px_dist / "tools" / "grad-plus-borrowing-cap-calculator"
    px_tools.mkdir(parents=True, exist_ok=True)
    if (px_src / "css").is_dir():
        shutil.copytree(px_src / "css", px_dist / "css")

    ph_src_landing = (ph_src / "index.html").read_text(encoding="utf-8")
    ph_src_tool = (ph_src / "tools" / "saas-runway-calculator" / "index.html").read_text(encoding="utf-8")
    px_src_landing = (px_src / "index.html").read_text(encoding="utf-8")
    px_src_tool = (px_src / "tools" / "grad-plus-borrowing-cap-calculator" / "index.html").read_text(encoding="utf-8")

    # Seed all 5 flaw classes into cloned ProfitHelm and Prexvo pages
    (ph_dist / "index.html").write_text(
        _seed_flaw_1_missing_theme_styles(
            _seed_flaw_3_cramped_tap_targets(_seed_flaw_4_broken_visual_hierarchy(ph_src_landing))
        ),
        encoding="utf-8",
    )
    (ph_tools / "index.html").write_text(
        _seed_flaw_1_missing_theme_styles(
            _seed_flaw_2_overflowing_table(
                _seed_flaw_3_cramped_tap_targets(
                    _seed_flaw_4_broken_visual_hierarchy(_seed_flaw_5_broken_calculator_inputs(ph_src_tool))
                )
            )
        ),
        encoding="utf-8",
    )
    (px_dist / "index.html").write_text(
        _seed_flaw_1_missing_theme_styles(
            _seed_flaw_3_cramped_tap_targets(_seed_flaw_4_broken_visual_hierarchy(px_src_landing))
        ),
        encoding="utf-8",
    )
    (px_tools / "index.html").write_text(
        _seed_flaw_1_missing_theme_styles(
            _seed_flaw_2_overflowing_table(
                _seed_flaw_3_cramped_tap_targets(
                    _seed_flaw_4_broken_visual_hierarchy(_seed_flaw_5_broken_calculator_inputs(px_src_tool))
                )
            )
        ),
        encoding="utf-8",
    )

    # 1. Verify RetroReflectionEngine.audit_estate detects BOTH non-tool landing pages AND tool pages across both tenants
    ph_audit_before = RetroReflectionEngine.audit_estate(ph_dist, property_id="profithelm")
    assert ph_audit_before["status"] == "STALE"
    assert "index.html" in ph_audit_before["stale_pages"]
    assert "tools/saas-runway-calculator/index.html" in ph_audit_before["stale_pages"]

    px_audit_before = RetroReflectionEngine.audit_estate(px_dist, property_id="prexvo")
    assert px_audit_before["status"] == "STALE"
    assert "index.html" in px_audit_before["stale_pages"]
    assert "tools/grad-plus-borrowing-cap-calculator/index.html" in px_audit_before["stale_pages"]

    ph_auditor = UnifiedBrowserAuditor(dist_dir=ph_dist)
    px_auditor = UnifiedBrowserAuditor(dist_dir=px_dist)
    cdp_ok, _ = ph_auditor.check_cdp_reachability()
    if cdp_ok:
        ph_browser_before = ph_auditor.run_audit()
        assert ph_browser_before["passed"] is False
        px_browser_before = px_auditor.run_audit()
        assert px_browser_before["passed"] is False

    # 2. Run unattended reflect_and_recompile_all_assets(force=False) across both tenants
    ph_adapter = ConfigurablePropertyAdapter(
        property_id="profithelm",
        brand_name="ProfitHelm",
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        dist_dir=ph_dist,
        repo_path=tmp_path / "profithelm",
        tools=[{"slug": "saas-runway-calculator", "title": "SaaS Runway Calculator"}],
    )
    px_adapter = ConfigurablePropertyAdapter(
        property_id="prexvo",
        brand_name="Prexvo",
        domain="prexvo.com",
        canonical_base="https://prexvo.com",
        dist_dir=px_dist,
        repo_path=tmp_path / "prexvo",
        tools=[{"slug": "grad-plus-borrowing-cap-calculator", "title": "Grad PLUS Borrowing Cap Calculator"}],
    )
    from pseofactory.maintenance import TenantRegistry

    reg = TenantRegistry()
    reg.register_adapter(ph_adapter)
    reg.register_adapter(px_adapter)

    reflect_res = reflect_and_recompile_all_assets(
        properties=["profithelm", "prexvo"],
        force=False,
        latch_state=False,
        run_downstream=False,
        registry=reg,
        workspace_root=tmp_path,
    )
    assert reflect_res["status"] == "PASS"
    assert reflect_res["property_reports"]["profithelm"]["retrofitted"] >= 2
    assert reflect_res["property_reports"]["prexvo"]["retrofitted"] >= 2

    # 3. Verify RetroReflectionEngine.audit_estate now reports PASS (0 stale pages) on both tenants
    ph_audit_after = RetroReflectionEngine.audit_estate(ph_dist, property_id="profithelm")
    assert ph_audit_after["status"] == "PASS", f"ProfitHelm stale pages remain: {ph_audit_after}"
    assert ph_audit_after["stale_count"] == 0

    px_audit_after = RetroReflectionEngine.audit_estate(px_dist, property_id="prexvo")
    assert px_audit_after["status"] == "PASS", f"Prexvo stale pages remain: {px_audit_after}"
    assert px_audit_after["stale_count"] == 0

    # 4. Verify real headless Chrome (UnifiedBrowserAuditor) passes 100% on desktop & mobile viewports for both tenants
    if cdp_ok:
        ph_browser_after = ph_auditor.run_audit()
        assert ph_browser_after["passed"] is True, (
            f"ProfitHelm real-browser verification failed after self-healing: {ph_browser_after['findings']}"
        )
        assert ph_browser_after["failed_count"] == 0

        px_browser_after = px_auditor.run_audit()
        assert px_browser_after["passed"] is True, (
            f"Prexvo real-browser verification failed after self-healing: {px_browser_after['findings']}"
        )
        assert px_browser_after["failed_count"] == 0


