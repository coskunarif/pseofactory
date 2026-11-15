"""
Deterministic reproducer tests for live-proven pseofactory reflection, UI/UX,
calculator math integrity, edge leak, CI drift, and containment defects.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def test_porcelain_css_cache_bust_query_version() -> None:
    """Porcelain normalized HTML must append ?v=<hash> to style.css to bust immutable edge cache."""
    from pseofactory.porcelain_shell import (
        get_porcelain_tenant_profile,
        normalize_html_to_porcelain_shell,
    )

    raw_html = (
        "<!DOCTYPE html><html lang='en'><head><title>Cap Rate | Prexvo</title>"
        "<meta name='description' content='Deterministic student loan repayment calculator.'></head>"
        "<body><main><h1>Cap Rate Calculator</h1><p>Body copy.</p></main></body></html>"
    )
    for pid in ("profithelm", "prexvo", "gainhelm", "lienbond"):
        norm_html, _ = normalize_html_to_porcelain_shell(
            raw_html,
            "tools/sample-calc/index.html",
            get_porcelain_tenant_profile(pid),
        )
        assert re.search(
            r'<link\b[^>]*id=["\']pseo-visual-primitives["\'][^>]*href=["\'][^"\']*style\.css\?v=[0-9a-f]{8,12}["\']',
            norm_html,
        ), f"Expected content-hashed style.css?v=<hash> link for {pid}"


def test_porcelain_stylesheet_covers_workbench_and_inline_prose_links() -> None:
    """Porcelain CSS must style visual_primitives workbench classes and keep prose links inline."""
    from pseofactory.browser_verifier import UnifiedBrowserAuditor
    from pseofactory.contracts import assert_touch_targets
    from pseofactory.porcelain_shell import generate_porcelain_stylesheet

    css = generate_porcelain_stylesheet("lienbond")
    assert_touch_targets(css, is_css=True, context="porcelain_stylesheet")

    required_selectors = (
        ".serp-sub-inputs-grid",
        ".serp-metrics-grid",
        ".serp-metric-box",
        ".serp-sub-select",
        ".serp-sub-input",
        ".serp-archetype-btn",
        ".post-calc-upgrade-pillars",
        ".post-calc-upgrade-pillar",
        ".feature-card",
        ".overlay-section",
        ".calc-metric-card",
        ".legend-dot",
        ".affiliate-card",
        ".scenario-card",
        "details.faq-accordion",
    )
    for sel in required_selectors:
        assert sel in css, f"Missing Porcelain CSS definition for {sel}"

    assert "display: inline;" in css, "Inline prose links inside main p must use display: inline;"
    assert "parentText.length > linkText.length" in UnifiedBrowserAuditor.JS_CHECK_TARGETS


def test_porcelain_shell_preserves_scripts_governance_and_tenant_substrate(tmp_path: Path) -> None:
    """Porcelain sanitizer/compiler must preserve <script> strings, rich disclaimers, and tenant identity."""
    from pseofactory.porcelain_shell import (
        _strip_legacy_shell_chrome,
        _sync_tenant_pseo_substrate,
        compile_tenant_porcelain_estate,
        sanitize_inline_styles_outside_svg,
    )

    html_with_script = (
        '<div><p style="color: #1d4ed8;">Text</p>'
        '<script>var tpl = \'<div style="color: #123456; padding: 2px;">raw</div>\';</script></div>'
    )
    sanitized = sanitize_inline_styles_outside_svg(
        html_with_script, {"--brand-primary", "--text-primary", "--text-secondary", "--bg-surface", "--border-subtle"}
    )
    assert 'color: #123456; padding: 2px;' in sanitized

    body_with_inner_header_and_playbook = (
        '<header class="site-header"><nav>Old Nav</nav></header>'
        '<main><div class="container">'
        '<h1>Calculator Title</h1>'
        '<section class="card"><header class="section-heading"><h2>Schedule A</h2></header><p>Row</p></section>'
        '</div></main>'
        '<footer class="card"><div class="playbook-capture-card" id="rescued-playbook">Capture</div><p>Copyright</p></footer>'
    )
    inner_main, _ = _strip_legacy_shell_chrome(body_with_inner_header_and_playbook)
    assert "<h2>Schedule A</h2>" in inner_main
    assert 'id="rescued-playbook"' in inner_main

    repo_dir = tmp_path / "lienbond"
    dist_dir = repo_dir / "dist"
    (dist_dir / "tools").mkdir(parents=True)
    (dist_dir / "disclaimers").mkdir(parents=True)
    (dist_dir / "index.html").write_text(
        "<!DOCTYPE html><html><head><title>LienBond</title></head><body><main><h1>LienBond</h1></main></body></html>",
        encoding="utf-8",
    )
    (dist_dir / "tools" / "index.html").write_text(
        "<!DOCTYPE html><html><head><title>Tools</title></head><body><main><h1>Tools</h1></main></body></html>",
        encoding="utf-8",
    )
    (dist_dir / ".pseofactory.json").write_text('{"property_id":"lienbond"}', encoding="utf-8")
    (dist_dir / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")

    rich_disclaimer = (
        "<!DOCTYPE html><html lang='en'><head><title>50-State Statutory Disclaimers | LienBond</title>"
        "<meta name='description' content='50-state statutory mechanics lien and surety bond legal disclaimers.'></head>"
        "<body><main><h1>50-State Statutory Mechanics Lien Disclaimers</h1>"
        "<p>" + ("California Civil Code Section 8200 preliminary 20-day notice rules. " * 55) + "</p>"
        "<table><thead><tr><th>State</th><th>Statute</th></tr></thead>"
        "<tbody><tr><td>CA</td><td>Cal. Civ. Code 8200</td></tr></tbody></table>"
        "</main></body></html>"
    )
    (dist_dir / "disclaimers" / "index.html").write_text(rich_disclaimer, encoding="utf-8")

    compile_tenant_porcelain_estate(dist_dir, property_id="lienbond", repo_root=repo_dir)
    compiled_disc = (dist_dir / "disclaimers" / "index.html").read_text(encoding="utf-8")
    assert "Cal. Civ. Code 8200" in compiled_disc
    assert not (dist_dir / ".pseofactory.json").exists()
    robots_after = (dist_dir / "robots.txt").read_text(encoding="utf-8")
    assert "Disallow: /api/" in robots_after

    pkg_dir = repo_dir / "lienbond"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    _sync_tenant_pseo_substrate(repo_dir, pkg_dir, property_id="lienbond")
    synced_porc = (pkg_dir / "_pseo_substrate" / "pseofactory" / "porcelain_shell.py").read_text(encoding="utf-8")
    assert "compliance@lienbond.com" in synced_porc or "lienbond" in synced_porc


def test_visual_primitives_never_clobbers_exact_calculator_math_and_fixes_hero_range() -> None:
    """visual_primitives JS must not overwrite exact calculator outputs with 0.7+0.3*cVal/bVal fudge factors."""
    from pseofactory.visual_primitives import (
        _render_runtime_sync_events_js,
        _render_runtime_sync_workbench_js,
        _retrofit_hero_range_and_jurisdiction_bars,
        _retrofit_partner_reg_and_quick_unlock,
    )

    js = _render_runtime_sync_workbench_js() + "\n" + _render_runtime_sync_events_js()
    assert "0.7 + 0.3 *" not in js
    assert "* 0.065" not in js
    assert 'el.type !== "range"' in js or 'el.type === "range"' in js

    # Hero range baseline must preserve $ when output-value sits next to $ prefix
    sample_html = (
        '<section class="hero-section card"><h1>Calculator</h1></section>'
        '<div id="saveable-decision-blueprint">'
        '<div class="kpi-row"><span class="output-prefix">$</span><span class="output-value">14,800</span></div>'
        '</div>'
    )
    actions: list[str] = []
    retro = _retrofit_hero_range_and_jurisdiction_bars(
        sample_html,
        tool_slug="soc-2-cost",
        default_state="DE",
        has_quote_intake=True,
        us_jurisdictions=[("DE", "Delaware (DE)")],
        actions=actions,
    )
    assert 'id="hero-range-baseline">$14,800</strong>' in retro

    # GainHelm #metric-* result container must sit ABOVE .calc-inline-cta
    gh_html = (
        '<div id="partner-quote-intake-step" data-calculated-amount="74000"></div>'
        '<div class="result-box">'
        '<div class="calc-inline-cta"><a href="/r/vanta_security" data-cta-slot="calculator_result_inline">Vanta</a></div>'
        '<div class="metrics-grid" id="gainhelm-metrics"><div class="metric-card"><span id="metric-soc2_total_cost">$74,000</span></div></div>'
        '<div class="lead-capture-card">Lead</div>'
        '</div>'
    )
    gh_actions: list[str] = []
    gh_retro = _retrofit_partner_reg_and_quick_unlock(
        gh_html,
        prop_id="gainhelm",
        tool_slug="soc-2-audit-cost-calculator",
        default_state="DE",
        has_quote_intake=True,
        q_tag='<div id="partner-quote-intake-step" data-calculated-amount="74000">',
        actions=gh_actions,
    )
    assert gh_retro.index('id="metric-soc2_total_cost"') < gh_retro.index('class="calc-inline-cta"')


def test_gsc_remediation_compiler_and_signals_content_integrity(tmp_path: Path) -> None:
    """Verifies Prexvo 12x annual conversion, LienBond prose/schema cleanliness, and OBBBA 100% bonus copy."""
    from pseofactory.compiler import compile_lienbond_estate
    from pseofactory.gsc_remediation import inject_overlay_into_html
    from pseofactory.proprietary_signals import compute_multi_year_longitudinal_trajectory

    base_leaf = (
        "<!DOCTYPE html><html><head><link rel='canonical' href='https://prexvo.com/tools/rap-repayment-calculator/'></head>"
        "<body><main><div class='container'><h1>RAP Calculator</h1></div></main></body></html>"
    )
    overlay_html = inject_overlay_into_html(
        base_leaf,
        {
            "tenant_id": "prexvo",
            "slug": "rap-repayment-calculator",
            "ai_mode_decision_matrix": [
                {
                    "profile": "Single Borrower ($60k AGI)",
                    "statutory_threshold": "225% FPL",
                    "optimal_path": "2026 RAP",
                    "net_dollar_impact": "$187/mo Reduction vs 10-Year Standard ($541/mo vs $728/mo)",
                    "next_action": "Enroll in RAP",
                }
            ],
        },
    )
    assert "($2,244 Annual vs $2,244 Annual)" not in overlay_html
    assert "$6,492 Annual vs $8,736 Annual" in overlay_html

    lb_root = tmp_path / "lb_estate"
    compile_lienbond_estate(lb_root, run_retrofit=False)
    home_html = (lb_root / "dist" / "index.html").read_text(encoding="utf-8")
    leaf_html = (
        lb_root / "dist" / "tools" / "contractor-license-bond-cost-calculator-by-credit-score" / "index.html"
    ).read_text(encoding="utf-8")
    assert "HWL-1263" not in home_html
    assert "HWL-1263" not in leaf_html
    assert "Q499388" not in home_html
    assert "Q499388" not in leaf_html
    assert any(p.suffix == ".txt" and len(p.stem) == 32 for p in (lb_root / "dist").glob("*.txt"))

    traj = compute_multi_year_longitudinal_trajectory(
        property_id="profithelm",
        slug="equipment-lease-vs-buy-tax-calculator",
        topic_label="Equipment Lease vs Buy Tax Calculator",
    )
    assert "20% in 2026 and 0% in 2027" not in traj["summary"]


def test_edge_dist_functions_no_leak_and_non_apex_noindex_parity(tmp_path: Path) -> None:
    """Edge sync must never leak server JS into dist/functions/ and must inject isNonApexDev into _middleware.js."""
    from pseofactory.edge import sync_tenant_edge_redirect_function

    repo = tmp_path / "prexvo"
    (repo / "dist" / "functions" / "api").mkdir(parents=True)
    (repo / "dist" / "functions" / "api" / "signal.js").write_text("SECRET_TOKEN", encoding="utf-8")
    (repo / "functions").mkdir(parents=True)
    (repo / "functions" / "_middleware.js").write_text(
        'export async function onRequest(context) {\n'
        '  const url = new URL(context.request.url);\n'
        '  const pathname = url.pathname;\n'
        '  return await context.next();\n'
        '}\n',
        encoding="utf-8",
    )

    sync_tenant_edge_redirect_function(repo, property_id="prexvo")
    assert not (repo / "dist" / "functions").exists()
    mw_after = (repo / "functions" / "_middleware.js").read_text(encoding="utf-8")
    assert "isNonApexDev" in mw_after
    assert "noindex, nofollow" in mw_after


def test_drift_ci_substrate_lock_fallback_containment_truth_and_ui_auth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Covers CI substrate_lock fallback, workspace containment, em-dash non-bypass, and UI session auth."""
    from pseofactory.drift import compute_dist_lock_metrics, compute_engine_hash, detect_engine_drift
    from pseofactory.maintenance import LiveTruthAuditEngine, WorkspacePropertyScanner
    from pseofactory.ui import DashboardRequestHandler

    # 1. Clean CI tenant checkout without .agy/engine_hash.json falls back to substrate_lock.json
    tenant_repo = tmp_path / "clean_ci_tenant"
    (tenant_repo / "dist").mkdir(parents=True)
    (tenant_repo / "dist" / "index.html").write_text("<html><body>ok</body></html>", encoding="utf-8")
    (tenant_repo / ".pseofactory.json").write_text('{"property_id":"profithelm"}', encoding="utf-8")
    fp, tot = compute_dist_lock_metrics(tenant_repo / "dist")
    eh = compute_engine_hash()
    (tenant_repo / "substrate_lock.json").write_text(
        json.dumps(
            {
                "property_id": "profithelm",
                "engine_hash": eh,
                "substrate_hash": eh,
                "synced_substrate_hash": eh,
                "dist_fingerprint": fp,
                "total_assets": tot,
            }
        ),
        encoding="utf-8",
    )
    ci_drift = detect_engine_drift(state_file=tenant_repo / ".agy" / "engine_hash.json")
    assert ci_drift["status"] == "ALIGNED"

    # 2. LiveTruthAuditEngine must NOT return [] when an em-dash is present on a page with bad math
    truth_engine = LiveTruthAuditEngine()
    bad_html_with_emdash = (
        "<html><body><h1>Calculator \u2014 Test</h1>"
        '<script type="application/json" id="calculation-manifest">'
        '{"formula": "a - a + 500", "inputs": {"a": 100}, "published_output": 999}'
        "</script>"
        '<span class="output-value">$999</span></body></html>'
    )
    violations = truth_engine.audit_html(bad_html_with_emdash, property_id="profithelm", context="bad.html")
    assert len(violations) > 0

    # 3. WorkspacePropertyScanner must ignore non-pSEO repos (no .pseofactory.json/factory.json) when enforce_manifest=True / live workspace
    fake_ws = tmp_path / "projects_ws"
    roku = fake_ws / "extreme-roku-cinema"
    (roku / "dist").mkdir(parents=True)
    (roku / "pyproject.toml").write_text('[project]\nname = "extreme-roku-cinema"\nversion = "0.1.0"\n', encoding="utf-8")
    scanner = WorkspacePropertyScanner(workspace_root=fake_ws, require_manifest=True)
    assert [a.property_id for a in scanner.discover_properties()] == []

    # 4. DashboardRequestHandler allows browser session cookie when PSEODASHBOARD_API_TOKEN is set
    monkeypatch.setenv("PSEODASHBOARD_API_TOKEN", "test_secret_token_123")
    cookie_val = DashboardRequestHandler._compute_session_cookie("test_secret_token_123")
    dummy = MagicMock(spec=DashboardRequestHandler)
    dummy.command = "POST"
    dummy.headers = {
        "Cookie": f"pseo_ui_session={cookie_val}",
        "Host": "127.0.0.1:8090",
        "Origin": "http://127.0.0.1:8090",
    }
    assert DashboardRequestHandler._check_api_auth(dummy) is True


def test_post_reflection_audit_gates_lienbond_titles_prexvo_loan_monthly_and_meta_uniqueness() -> None:
    """Covers LienBond title/H1 parity, Prexvo loan $/mo non-pricing figures, and distinct Section 179/lease metas."""
    from pseofactory.audit import _titles_match
    from pseofactory.gsc_remediation import _normalize_meta_120_155, apply_remediation_overlay_to_html
    from pseofactory.tenant_facts import TenantFactStore

    # 1. LienBond 50-60 char SEO titles must match full descriptive H1s in Gate 1
    assert _titles_match(
        "Commercial Construction Retainage Calculator | LienBond",
        "Commercial Construction Retainage Interest Penalty Calculator by State",
    )
    assert _titles_match(
        "Davis-Bacon Prevailing Wage and WH-347 Calculator | LienBond",
        "Davis-Bacon Prevailing Wage and WH-347 Fringe Benefit Rate Calculator",
    )
    assert _titles_match(
        "ERISA Section 412 Fidelity Bond Calculator | LienBond",
        "ERISA Section 412 Fidelity Bond Coverage Amount Calculator",
    )
    assert _titles_match(
        "Experience Modification Rate (EMR) Calculator | LienBond",
        "Experience Modification Rate (EMR) Workers Comp Penalty Calculator",
    )
    fixed_lb_html = apply_remediation_overlay_to_html(
        "<html><head><title>Old</title></head><body><h1>California, Texas and Florida Preliminary Notice Deadline Calculator</h1></body></html>",
        {
            "tenant": "lienbond",
            "slug": "california-texas-florida-preliminary-notice-deadline-calculator",
            "title_rewrite": "California, Texas and Florida Calculator | LienBond",
        },
    )
    assert "Notice Calculator | LienBond" in fixed_lb_html
    m_title = re.search(r"<title>(.*?)</title>", fixed_lb_html)
    assert m_title and _titles_match(
        m_title.group(1),
        "California, Texas and Florida Preliminary Notice Deadline Calculator",
    )

    # 2. Prexvo student loan $/mo payment/tax/savings figures must NOT be flagged as SaaS pricing tiers,
    #    while actual SaaS tier pricing hallucinations ($49/mo Pro Tier) MUST still be flagged.
    store = TenantFactStore.get_instance()
    ok_loan, viol_loan = store.verify_claim(
        "prexvo",
        "Under 34 CFR 685.209(e), filing separately lowers the monthly RAP payment by $410.31/mo ($4,923.72/yr). "
        "After subtracting the $120.42/mo ($1,445/yr) marginal federal income tax increase, separate filing yields "
        "$289.90/mo ($3,478.75/yr) in net household savings.",
        context="tools/married-filing-separately-student-loan-calculator/index.html",
    )
    assert ok_loan is True, f"Unexpected loan monthly false positive: {viol_loan}"
    ok_bad_tier, _ = store.verify_claim("prexvo", "Pricing: $49/mo Pro Tier", context="index.html")
    assert ok_bad_tier is False

    # 3. ProfitHelm Section 179 heavy-vehicle vs equipment-deduction and lease vs lease-vs-buy metas must be unique
    m_lease = _normalize_meta_120_155(
        "", "profithelm", "equipment lease tax deduction", slug="equipment-lease-tax-deduction"
    )
    m_lease_buy = _normalize_meta_120_155(
        "", "profithelm", "equipment lease vs buy section 179 calculator", slug="equipment-lease-vs-buy-section-179-calculator"
    )
    assert m_lease != m_lease_buy

    m_veh = _normalize_meta_120_155(
        "", "profithelm", "section 179 vehicle equipment deduction", slug="section-179-vehicle-equipment-deduction"
    )
    m_heavy = _normalize_meta_120_155(
        "", "profithelm", "commercial heavy vehicle section 179 weight calculator", slug="commercial-heavy-vehicle-section-179-weight-calculator"
    )
    assert m_veh != m_heavy


def test_governance_pages_never_treated_as_calculators_or_polluted(tmp_path: Path) -> None:
    """Governance routes (disclaimers/, methodology/, etc.) must never be classified as calculator pages."""
    from pseofactory.maintenance import RetroReflectionEngine
    from pseofactory.porcelain_shell import compile_tenant_porcelain_estate

    dist = tmp_path / "dist"
    (dist / "disclaimers").mkdir(parents=True)
    polluted_disclaimers = (
        "<!DOCTYPE html><html><head><script type='application/ld+json'>{\"sameAs\":[\"https://www.wikidata.org/wiki/Q499388\"]}</script></head>"
        "<body><main><h1>Disclaimers</h1><table><tr><th>A</th><td>" + ("statutory text " * 200) + "</td></tr></table>"
        "<script id='calculation-manifest' type='application/json'>{\"formula\":\"a+b\"}</script></main></body></html>"
    )
    disc_file = dist / "disclaimers" / "index.html"
    disc_file.write_text(polluted_disclaimers, encoding="utf-8")
    (dist / "index.html").write_text("<!DOCTYPE html><html><body><main><h1>Home</h1></main></body></html>", encoding="utf-8")

    assert RetroReflectionEngine.is_tool_or_calculator_page(disc_file, dist, polluted_disclaimers) is False
    compile_tenant_porcelain_estate(dist, property_id="gainhelm", repo_root=tmp_path)
    cleaned = disc_file.read_text(encoding="utf-8")
    assert "Q499388" not in cleaned
    assert 'id="calculation-manifest"' not in cleaned and "id='calculation-manifest'" not in cleaned
