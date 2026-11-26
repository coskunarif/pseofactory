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
    assert 'id="rescued-playbook"' not in inner_main

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
        normalize_html_visual_primitives,
    )

    js = _render_runtime_sync_workbench_js() + "\n" + _render_runtime_sync_events_js()
    assert "0.7 + 0.3 *" not in js
    assert "* 0.065" not in js
    assert 'el.type !== "range"' in js or 'el.type === "range"' in js

    # Active visual primitives pipeline must strip legacy hero/quick-unlock/pro-hook bloat while preserving $ output-value
    sample_html = (
        '<html><head><link rel="canonical" href="https://gainhelm.com/tools/soc-2-audit-cost-calculator/"></head>'
        '<body><main><section class="hero-section card"><h1>Calculator</h1></section>'
        '<div id="hero-range-anchor" class="hero-range-anchor">Hero Range</div>'
        '<div id="state-first-hero-bar" class="state-first-hero-bar">State Bar</div>'
        '<div class="calc-grid"><div class="result-box">'
        '<div class="kpi-row"><span class="output-prefix">$</span><span class="output-value">14,800</span></div>'
        '<div id="calc-result-quick-unlock-bar">Quick Unlock</div>'
        '<div class="pro-hook-card">Pro Hook</div>'
        '</div></div>'
        '<div id="saveable-decision-blueprint"></div>'
        '</main></body></html>'
    )
    retro, _ = normalize_html_visual_primitives(sample_html, is_tenant_porcelain=True)
    from bs4 import BeautifulSoup as _AuditSoup

    retro_soup = _AuditSoup(retro, "html.parser")
    assert retro_soup.select(
        "#hero-range-baseline, #hero-range-anchor, .hero-range-anchor, "
        "#state-first-hero-bar, .state-first-hero-bar, "
        "#calc-result-quick-unlock-bar, .pro-hook-card"
    ) == []
    assert '<span class="output-prefix">$</span><span class="output-value">14,800</span>' in retro

    # GainHelm #metric-* result container must sit ABOVE .calc-inline-cta
    gh_html = (
        '<html><head><link rel="canonical" href="https://gainhelm.com/tools/soc-2-audit-cost-calculator/"></head><body><main>'
        '<div id="partner-quote-intake-step" data-calculated-amount="74000"></div>'
        '<div class="result-box">'
        '<div class="calc-inline-cta"><a href="/r/vanta_security" data-cta-slot="calculator_result_inline">Vanta</a></div>'
        '<div class="metrics-grid" id="gainhelm-metrics"><div class="metric-card"><span id="metric-soc2_total_cost">$74,000</span></div></div>'
        '<div class="lead-capture-card">Lead</div>'
        '</div></main></body></html>'
    )
    gh_retro, _ = normalize_html_visual_primitives(gh_html, is_tenant_porcelain=True)
    assert 'id="metric-soc2_total_cost"' in gh_retro
    assert 'class="calc-inline-cta"' not in gh_retro
    assert 'id="workpaper-unlock-card"' in gh_retro
    assert gh_retro.index('id="metric-soc2_total_cost"') < gh_retro.index('id="workpaper-unlock-card"')


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


def test_sync_tenant_porcelain_shell_enforces_no_dist_functions_in_staging_lockdown(tmp_path: Path) -> None:
    """sync_tenant_porcelain_shell must enforce that dist/functions/ never exists in builder.py, dist/, or lockdown assertions."""
    from pseofactory.porcelain_shell import sync_tenant_porcelain_shell

    repo = tmp_path / "profithelm-platform"
    pkg = repo / "profithelm"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text('"""ProfitHelm."""\n', encoding="utf-8")
    (pkg / "builder.py").write_text(
        'def build_all():\n'
        '    functions_src = BASE_DIR / "functions"\n'
        '    dist_functions = DIST_DIR / "functions"\n'
        '    if functions_src.exists():\n'
        '        shutil.copytree(functions_src, dist_functions, dirs_exist_ok=True)\n',
        encoding="utf-8",
    )
    leak_fn = repo / "dist" / "functions" / "_middleware.js"
    leak_fn.parent.mkdir(parents=True)
    leak_fn.write_text("export async function onRequest(ctx) { return ctx.next(); }\n", encoding="utf-8")

    tests_dir = repo / "tests"
    tests_dir.mkdir(parents=True)
    tsiu = tests_dir / "test_search_and_indexing_upgrades.py"
    tsiu.write_text(
        'def check_staging_lockdown(DIST_DIR):\n'
        '    dist_mw = DIST_DIR / "functions" / "_middleware.js"\n'
        '    assert dist_mw.exists(), "dist/functions/_middleware.js missing from static build!"\n',
        encoding="utf-8",
    )

    sync_tenant_porcelain_shell(repo, "profithelm")

    assert not (repo / "dist" / "functions").exists()
    assert "shutil.copytree(functions_src, dist_functions" not in (pkg / "builder.py").read_text(encoding="utf-8")
    patched_test = tsiu.read_text(encoding="utf-8")
    assert "assert not dist_mw.exists()" in patched_test


@pytest.mark.host_estate
def test_serp_b2b_deduction_responsiveness_pslf_widget_spec_and_metrics_grid_order(monkeypatch) -> None:
    """
    1. #serp-b2b-deduction must reactively update SERP workbench outputs even when primary gross < $194k (e.g. $50k).
    2. PrexvoBrowserAdapter PSLF widget specs must target Prexvo's real .metric-value (#metric-rap_subsidy / #metric-rap_payment).
    3. GainHelm .calc-metrics-grid must be detected and normalized above .calc-inline-cta across reflection & Porcelain shell.
    """
    from playwright.sync_api import sync_playwright
    from pseofactory.browser_verifier import PrexvoBrowserAdapter
    from pseofactory.maintenance import RetroReflectionEngine
    from pseofactory.porcelain_shell import get_porcelain_tenant_profile, normalize_html_to_porcelain_shell
    from pseofactory.visual_primitives import render_runtime_synchronizer_script

    # 1. Real Chromium execution of render_runtime_synchronizer_script() with $50k gross & $165k -> $222,800 deduction
    script_tag = render_runtime_synchronizer_script()
    doc = (
        "<!DOCTYPE html><html><body><main>"
        "<input type='number' id='field-bond_amount' value='50000' />"
        "<section id='serp-incumbent-depth-workbench' data-workbench-mode='b2b'>"
        "<input type='number' id='serp-b2b-gross' value='50000' />"
        "<input type='number' id='serp-b2b-deduction' value='165000' />"
        "<input type='number' id='serp-b2b-rate' value='24.5' />"
        "<select id='serp-b2b-regime'><option value='optimal_election' selected>Optimal</option></select>"
        "<div id='serp-out-primary'>$6,738</div>"
        "<div id='serp-out-secondary'>$12,250</div>"
        "<div id='serp-out-tertiary'>$5,512</div>"
        "<div id='serp-out-quaternary'>$43,262</div>"
        "</section>"
        "</main>"
        f"{script_tag}</body></html>"
    )
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(doc, wait_until="domcontentloaded")
        snap = page.evaluate(
            """() => {
              const snapOut = () => ['serp-out-primary','serp-out-secondary','serp-out-tertiary','serp-out-quaternary']
                .map(id => document.getElementById(id).textContent).join('|');
              const inp = document.getElementById('serp-b2b-deduction');
              inp.value = '165000';
              inp.dispatchEvent(new Event('input', { bubbles: true }));
              const before = snapOut();
              inp.value = '222800';
              inp.dispatchEvent(new Event('input', { bubbles: true }));
              const after = snapOut();
              return { before, after };
            }"""
        )
        browser.close()
    assert snap["before"] != snap["after"], f"#serp-b2b-deduction failed to update outputs: {snap}"

    # 2. PrexvoBrowserAdapter PSLF widget spec selector parity
    specs = {s.widget_id: s for s in PrexvoBrowserAdapter().get_widget_specs()}
    pslf_sim = specs["pslf-qualifying-payment-simulator"]
    assert "#metric-rap_subsidy" in pslf_sim.output_selector or ".metric-value" in pslf_sim.output_selector
    assert int(pslf_sim.input_value) >= 1000

    # 3. GainHelm .calc-metrics-grid above .calc-inline-cta in reflection detection & Porcelain shell
    gh_inverted = (
        "<!DOCTYPE html><html><head><title>SOC 2 Audit Cost Calculator | GainHelm Statutory Model</title></head>"
        "<body><main><h1>SOC 2 Audit Cost Calculator</h1>"
        "<div class='calc-results-column result-box'>"
        "<h3 class='calc-column-title'>Deterministic Statutory Outputs</h3>"
        "<div class='calc-inline-cta'><a href='/r/vanta_security' data-cta-slot='calculator_result_inline'>Vanta</a></div>"
        "<div class='calc-metrics-grid'><div class='calc-metric-card'><div class='calc-metric-value' id='metric-soc2_total_cost'>$78,100</div></div></div>"
        "</div></main></body></html>"
    )
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    missing = RetroReflectionEngine.audit_html_mechanics(gh_inverted)
    assert "deterministic_visual_primitives" in missing

    norm_gh, _ = normalize_html_to_porcelain_shell(
        gh_inverted,
        "tools/soc-2-audit-cost-calculator/index.html",
        get_porcelain_tenant_profile("gainhelm"),
    )
    assert norm_gh.index("calc-metrics-grid") < norm_gh.index("calc-inline-cta")


def test_washington_spokes_never_classified_as_crypto_and_sec1031_outputs_tracked() -> None:
    """
    'washington' must never match 'wash' (intended for 'wash-sale'), which previously injected
    Crypto Form 1099-DA workbenches onto Washington Section 1031 and Tax Bracket spokes.
    """
    from pseofactory.browser_verifier import UnifiedBrowserAuditor
    from pseofactory.competitor import render_serp_incumbent_depth_upgrade_block
    from pseofactory.maintenance import _has_vertical_competitor_pollution

    wa_1031 = render_serp_incumbent_depth_upgrade_block(
        slug="section-1031-calculator/washington",
        title="Washington 1031 Exchange Calculator",
        property_id="profithelm",
    )
    assert 'data-workbench-mode="sec1031"' in wa_1031
    assert 'data-workbench-mode="crypto"' not in wa_1031

    wa_tax = render_serp_incumbent_depth_upgrade_block(
        slug="irs-2027-tax-brackets/washington",
        title="Washington 2027 Tax Brackets Calculator",
        property_id="profithelm",
    )
    assert 'data-workbench-mode="tax_brackets"' in wa_tax
    assert 'data-workbench-mode="crypto"' not in wa_tax

    polluted_wa_html = (
        '<html><head><link rel="canonical" href="https://profithelm.com/tools/section-1031-calculator/washington/"></head>'
        '<body><section id="serp-incumbent-depth-workbench" data-workbench-mode="crypto">Rev. Proc. 2024-28</section></body></html>'
    )
    assert _has_vertical_competitor_pollution(polluted_wa_html) is True
    assert '[id*="-res-"]' in UnifiedBrowserAuditor.JS_RUN_E2E_INTERACTIVE_SURFACE


def test_porcelain_shell_scrubs_q499388_marks_inline_prose_links_and_wraps_mobile_cta(tmp_path: Path) -> None:
    """
    1. _consolidate_jsonld_head & sync_tenant_porcelain_shell must replace legacy Q499388 Wikidata URLs
       across both reflected dist/ HTML and tenant builder.py files.
    2. Genuine inline sentence links (<p>See <a class="touch-target">disclosures</a>.</p>) must receive
       .inline-prose-link (display: inline; min-height: 0) while standalone <p><a class="touch-target">...</a></p>
       remain 44px touch targets.
    3. Long .calc-inline-cta .btn-cta buttons with inline white-space: nowrap must wrap cleanly on 375px mobile
       without causing horizontal document overflow.
    """
    from pseofactory.porcelain_shell import (
        compile_tenant_porcelain_estate,
        generate_porcelain_stylesheet,
        sync_tenant_porcelain_shell,
    )

    repo = tmp_path / "profithelm-platform"
    pkg = repo / "profithelm"
    dist = repo / "dist"
    (dist / "tools" / "bid-bond-calculator").mkdir(parents=True)
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text('"""ProfitHelm."""\n', encoding="utf-8")
    (pkg / "builder.py").write_text(
        'SAME_AS = ["https://www.wikidata.org/wiki/Q499388"]\n',
        encoding="utf-8",
    )

    raw_leaf = (
        '<!DOCTYPE html><html lang="en"><head><title>Bid Bond</title>'
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@graph":['
        '{"@type":"Organization","name":"ProfitHelm","sameAs":["https://www.wikidata.org/wiki/Q499388"]},'
        '{"@type":"WebPage","name":"Bid Bond","publisher":{"@type":"Organization","name":"ProfitHelm"}}'
        ']}</script></head>'
        '<body><main id="main-content"><div class="container">'
        '<div class="calculation-container card">'
        '<p>For full details, <a href="/disclaimers/" class="touch-target">Read full disclosures</a> before filing.</p>'
        '<p><a href="#scenario-b" class="touch-target">Compare with Accelerated Repayment Scenario B</a></p>'
        '<div class="result-box"><div class="calc-inline-cta">'
        '<div class="calc-inline-cta-copy">Simply Business Bonding</div>'
        '<a href="/r/simply_business" class="btn-cta touch-target" '
        'style="display: inline-flex; min-height: 44px; padding: 10px 14px; white-space: nowrap;">'
        'Compare Instant Workers Comp and Commercial Contractor Surety Quotes at Simply Business</a>'
        "</div></div></div></div></main></body></html>"
    )
    leaf_path = dist / "tools" / "bid-bond-calculator" / "index.html"
    leaf_path.write_text(raw_leaf, encoding="utf-8")
    (dist / "index.html").write_text(raw_leaf, encoding="utf-8")

    sync_tenant_porcelain_shell(repo, property_id="profithelm")
    compile_tenant_porcelain_estate(dist, property_id="profithelm", repo_root=repo)

    builder_txt = (pkg / "builder.py").read_text(encoding="utf-8")
    assert "Q499388" not in builder_txt
    assert "compile_profithelm_estate" in builder_txt

    norm_leaf = leaf_path.read_text(encoding="utf-8")
    assert "Q499388" not in norm_leaf
    assert "https://profithelm.com/#organization" in norm_leaf
    assert 'href="/disclaimers/" class="touch-target inline-prose-link"' in norm_leaf
    assert 'href="#scenario-b" class="touch-target"' in norm_leaf

    norm_home = (dist / "index.html").read_text(encoding="utf-8")
    assert "Q499388" not in norm_home
    home_ld_m = re.search(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>', norm_home)
    assert home_ld_m, "Expected consolidated JSON-LD on homepage"
    home_graph = json.loads(home_ld_m.group(1))["@graph"]
    org_nodes = [n for n in home_graph if n.get("@type") == "Organization"]
    assert org_nodes, f"Expected Organization node on /, got: {home_graph}"
    assert "https://www.wikidata.org/wiki/Q8161" in (org_nodes[0].get("knowsAbout") or [])
    assert "Q8161" not in json.dumps(org_nodes[0].get("sameAs") or [])

    css = generate_porcelain_stylesheet("profithelm")
    assert "main a.inline-prose-link" in css
    assert "white-space: normal !important;" in css


@pytest.mark.host_estate
def test_calculate_btn_preserves_edited_input_before_url_debounce_and_hero_state_picker_routes(tmp_path: Path) -> None:
    """
    Verifies in headless Chromium:
    1. Clicking #calculate-btn within 30ms of editing an input while location.search still holds
       stale query params never overwrites user-edited DOM inputs back to stale URL params,
       while window popstate still re-hydrates from URL.
    2. #quote-intake-hero-state updates primary inputs/outputs on LienBond homepage (/),
       EMR Workers Comp Penalty Calculator, Contractor Lien Release Statutory Matrix (+ #serp-b2b-rate),
       and ProfitHelm Crypto Tax Calculator (+ #res-crypto-state even for single filing status).
    Zero em-dashes. Zero en-dashes.
    """
    import functools
    import http.server
    import threading
    from playwright.sync_api import sync_playwright
    from pseofactory.visual_primitives import render_runtime_synchronizer_script

    script_tag = render_runtime_synchronizer_script()
    site_dir = tmp_path / "site"
    site_dir.mkdir(parents=True, exist_ok=True)

    (site_dir / "lb_home.html").write_text(
        "<!DOCTYPE html><html><body><main>"
        "<select id='quote-intake-hero-state' name='state'><option value='CA'>CA</option><option value='TX'>TX</option></select>"
        "<form id='hub-bond-calculator' class='calculator-form'>"
        "<input type='number' id='input-bond_amount' name='bond_amount' value='25000' />"
        "<input type='number' id='input-credit_tier_rate_pct' name='credit_tier_rate_pct' value='1.5' />"
        "<input type='number' id='input-term_years' name='term_years' value='1' />"
        "<button type='submit' id='calculate-btn'>Recalculate Output</button>"
        "<div class='output-value'>375.00</div>"
        "</form>"
        "<script>"
        "(function(){"
        "var form=document.getElementById('hub-bond-calculator');"
        "var out=document.querySelector('.output-value');"
        "var dt=null;"
        "function recalc(){"
        "var b=parseFloat(document.getElementById('input-bond_amount').value)||0;"
        "var r=parseFloat(document.getElementById('input-credit_tier_rate_pct').value)||0;"
        "var t=parseFloat(document.getElementById('input-term_years').value)||0;"
        "out.textContent=(Math.round((b*r/100*t)*100)/100).toFixed(2);"
        "if(dt)clearTimeout(dt);"
        "dt=setTimeout(function(){var u=new URL(window.location.href);u.searchParams.set('bond_amount',String(b));window.history.replaceState({},'',u.toString());},150);"
        "}"
        "form.addEventListener('input',recalc);"
        "form.addEventListener('change',recalc);"
        "form.addEventListener('submit',function(e){e.preventDefault();recalc();});"
        "})();"
        "</script>"
        f"{script_tag}</main></body></html>",
        encoding="utf-8",
    )

    (site_dir / "lb_emr.html").write_text(
        "<!DOCTYPE html><html><body><main>"
        "<select id='quote-intake-hero-state' name='state'><option value='TX'>TX</option><option value='CA'>CA</option></select>"
        "<form id='emr-calc' class='calculator-form'>"
        "<input type='number' id='input-manual_workers_comp_premium' value='50000' />"
        "<input type='number' id='input-emr_factor' value='1.0' />"
        "<button type='submit' id='calculate-btn'>Recalculate Output</button>"
        "<div class='output-value'>50000.00</div>"
        "</form>"
        "<script>"
        "(function(){"
        "var form=document.getElementById('emr-calc');"
        "var out=document.querySelector('.output-value');"
        "function recalc(){"
        "var p=parseFloat(document.getElementById('input-manual_workers_comp_premium').value)||0;"
        "var e=parseFloat(document.getElementById('input-emr_factor').value)||1;"
        "out.textContent=(p*e).toFixed(2);"
        "}"
        "form.addEventListener('input',recalc);form.addEventListener('change',recalc);"
        "})();"
        "</script>"
        f"{script_tag}</main></body></html>",
        encoding="utf-8",
    )

    (site_dir / "lb_matrix.html").write_text(
        "<!DOCTYPE html><html><body><main>"
        "<select id='quote-intake-hero-state' name='state'><option value='TX'>TX</option><option value='CA'>CA</option><option value='FL'>FL</option></select>"
        "<form id='matrix-calc' class='calculator-form'>"
        "<input type='number' id='input-unpaid_contract_draw' value='85000' />"
        "<input type='number' id='input-change_order_balance' value='12500' />"
        "<input type='number' id='input-unserved_late_days' value='0' />"
        "<input type='number' id='input-daily_forfeiture_rate' value='500' />"
        "<button type='submit' id='calculate-btn'>Recalculate Output</button>"
        "<div class='output-value'>97500.00</div>"
        "</form>"
        "<section id='serp-incumbent-depth-workbench' data-workbench-mode='surety_lien'>"
        "<input type='number' id='serp-b2b-gross' value='85000' />"
        "<input type='number' id='serp-b2b-deduction' value='12500' />"
        "<input type='number' id='serp-b2b-rate' value='18.0' />"
        "<select id='serp-b2b-regime'><option value='optimal_election' selected>Optimal</option></select>"
        "<div id='serp-out-primary'>$13,050</div>"
        "<div id='serp-out-secondary'>$15,300</div>"
        "<div id='serp-out-tertiary'>$2,250</div>"
        "<div id='serp-out-quaternary'>$71,950</div>"
        "</section>"
        f"{script_tag}</main></body></html>",
        encoding="utf-8",
    )

    (site_dir / "ph_crypto.html").write_text(
        "<!DOCTYPE html><html><body><main>"
        "<select id='quote-intake-hero-state' name='state'><option value='TX'>TX</option><option value='CA'>CA</option></select>"
        "<input type='number' id='crypto-short-term' value='45000' />"
        "<input type='number' id='crypto-long-term' value='18000' />"
        "<input type='number' id='crypto-staking' value='2000' />"
        "<input type='number' id='crypto-ordinary-income' value='85000' />"
        "<select id='crypto-status'><option value='single' selected>Single</option><option value='married_joint'>MFJ</option></select>"
        "<select id='crypto-state'><option value='0.0'>TX (0%)</option><option value='0.05' selected>IL (5%)</option><option value='0.093'>CA (9.3%)</option></select>"
        "<div id='res-crypto-tax'>$0</div>"
        "<div id='res-crypto-net'>$0</div>"
        "<div id='res-crypto-rate'>0.0%</div>"
        "<div id='res-crypto-niit'>$0</div>"
        "<div id='res-crypto-state'>$3,250</div>"
        "<script>window.updateCryptoCalculator = function() { /* simulates legacy unpatched app.js */ };</script>"
        f"{script_tag}</main></body></html>",
        encoding="utf-8",
    )

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(QuietHandler, directory=str(site_dir))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # 1 & 2a. #calculate-btn stale URL param race + hero state picker on LienBond /
            page.goto(f"http://127.0.0.1:{port}/lb_home.html?bond_amount=25000", wait_until="domcontentloaded")
            assert page.locator("#input-bond_amount").input_value() == "25000"
            page.locator("#input-bond_amount").fill("31250")
            page.click("#calculate-btn")
            assert page.locator("#input-bond_amount").input_value() == "31250"
            assert page.locator(".output-value").inner_text().strip() == "468.75"
            page.wait_for_timeout(200)
            assert page.locator("#input-bond_amount").input_value() == "31250"
            # popstate still hydrates URL changes
            page.evaluate("() => { window.history.pushState({}, '', '?bond_amount=40000'); window.dispatchEvent(new Event('popstate')); }")
            assert page.locator("#input-bond_amount").input_value() == "40000"

            page.select_option("#quote-intake-hero-state", "TX")
            assert page.locator("#input-bond_amount").input_value() == "10000"
            assert page.locator(".output-value").inner_text().strip() == "150.00"
            page.select_option("#quote-intake-hero-state", "CA")
            assert page.locator("#input-bond_amount").input_value() == "25000"
            assert page.locator(".output-value").inner_text().strip() == "375.00"

            # 2b. LienBond EMR Workers Comp Penalty Calculator
            page.goto(f"http://127.0.0.1:{port}/lb_emr.html", wait_until="domcontentloaded")
            page.select_option("#quote-intake-hero-state", "CA")
            assert page.locator("#input-manual_workers_comp_premium").input_value() == "66750"
            assert page.locator(".output-value").inner_text().strip() == "66750.00"
            page.select_option("#quote-intake-hero-state", "TX")
            assert page.locator("#input-manual_workers_comp_premium").input_value() == "39000"
            assert page.locator(".output-value").inner_text().strip() == "39000.00"

            # 2c. LienBond Contractor Lien Release Statutory Matrix
            page.goto(f"http://127.0.0.1:{port}/lb_matrix.html", wait_until="domcontentloaded")
            page.select_option("#quote-intake-hero-state", "CA")
            assert page.locator("#input-daily_forfeiture_rate").input_value() == "1250"
            assert page.locator("#input-unserved_late_days").input_value() == "0"
            assert page.locator("#serp-b2b-rate").input_value() == "24"
            ca_serp = page.locator("#serp-out-primary").inner_text().strip()
            page.select_option("#quote-intake-hero-state", "FL")
            assert page.locator("#input-daily_forfeiture_rate").input_value() == "1000"
            assert page.locator("#input-unserved_late_days").input_value() == "0"
            assert page.locator("#serp-b2b-rate").input_value() == "9.5"
            fl_serp = page.locator("#serp-out-primary").inner_text().strip()
            assert ca_serp != fl_serp

            # 2d & 3. ProfitHelm Crypto Tax Calculator (#crypto-state + #res-crypto-state for single)
            page.goto(f"http://127.0.0.1:{port}/ph_crypto.html", wait_until="domcontentloaded")
            page.select_option("#quote-intake-hero-state", "CA")
            assert page.locator("#crypto-state").input_value() == "0.093"
            assert page.locator("#res-crypto-state").inner_text().strip() == "$6,045"
            page.select_option("#quote-intake-hero-state", "TX")
            assert page.locator("#crypto-state").input_value() == "0.0"
            assert page.locator("#res-crypto-state").inner_text().strip() == "$0"
            browser.close()
    finally:
        srv.shutdown()


@pytest.mark.host_estate
def test_profithelm_app_js_crypto_state_audit_retrofit_and_live_guard(tmp_path: Path) -> None:
    """
    Verifies RetroReflectionEngine.audit_estate detects missing stateTaxDisplay assignment
    in ProfitHelm static/js/app.js alongside legacy head_of_household: 12700 drift,
    retrofit_estate idempotently patches it right after niitEl assignment, and live repos remain blocked.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.maintenance import RetroReflectionEngine

    repo = tmp_path / "profithelm-platform"
    dist = repo / "dist"
    js_dir = dist / "static" / "js"
    js_dir.mkdir(parents=True, exist_ok=True)
    (dist / "index.html").write_text(
        "<!DOCTYPE html><html><head><title>ProfitHelm</title>"
        "<link rel='canonical' href='https://profithelm.com/'></head>"
        "<body><main><h1>ProfitHelm</h1></main></body></html>",
        encoding="utf-8",
    )

    app_js = js_dir / "app.js"
    app_js.write_text(
        "const STD = { single: 8600, head_of_household: 12700 };\n"
        "function updateCryptoCalculator() {\n"
        "  const niitEl = document.getElementById('res-crypto-niit');\n"
        "  const stateTaxDisplay = document.getElementById('res-crypto-state');\n"
        "  if (niitEl) niitEl.innerText = fmtUSD.format(niitTax);\n"
        "  const crStateInput = document.getElementById('crypto-state');\n"
        "}\n",
        encoding="utf-8",
    )

    pre_audit = RetroReflectionEngine.audit_estate(dist, "profithelm")
    assert pre_audit["stale_pages"].get("static/js/app.js") == ["statutory_truth_reconciliation"]

    retro = RetroReflectionEngine.retrofit_estate(dist, "profithelm", "https://profithelm.com")
    assert retro["status"] == "PASS"
    assert "static/js/app.js" in retro["retrofitted_paths"]

    patched = app_js.read_text(encoding="utf-8")
    assert "head_of_household: 12900" in patched
    expected_block = (
        "  if (niitEl) niitEl.innerText = fmtUSD.format(niitTax);\n"
        "  if (stateTaxDisplay) stateTaxDisplay.innerText = fmtUSD.format(stateTax);"
    )
    assert expected_block in patched

    post_audit = RetroReflectionEngine.audit_estate(dist, "profithelm")
    assert "static/js/app.js" not in post_audit.get("stale_pages", {})

    retro_second = RetroReflectionEngine.retrofit_estate(dist, "profithelm", "https://profithelm.com")
    assert app_js.read_text(encoding="utf-8").count("if (stateTaxDisplay) stateTaxDisplay.innerText = fmtUSD.format(stateTax);") == 1
    assert "static/js/app.js" not in retro_second["retrofitted_paths"]

    live_ph_dist = Path("/home/ubuntuadmin/projects/profithelm-platform/dist")
    if live_ph_dist.is_dir():
        blocked = RetroReflectionEngine.retrofit_estate(live_ph_dist, "profithelm", "https://profithelm.com")
        assert blocked["status"] == "BLOCKED_LIVE_WORKTREE"


def test_stage3b_overlay_mutation_triggers_post_workflow_retrofit_and_normalizes_acronyms(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Regression test for Stage 3b ProfitHelm overlay-mutation bug:
    1. inject_overlay_into_html normalizes statutory acronyms (Amt/Camt, 199a/Qbi, 280g)
       across meta_description, quick_answer, assertions, h2_headings, and FAQ entries so
       visible HTML matches normalized FAQPage JSON-LD.
    2. reflect_and_recompile_all_assets(..., force=True) snapshots dist/**/*.html before/after
       run_all_seo_growth_workflows so overlay-only HTML mutations (with mutated_donor_pages=[])
       trigger post-workflow RetroReflectionEngine.retrofit_estate.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.gsc_remediation import inject_overlay_into_html
    import pseofactory.affiliates as aff_mod
    import pseofactory.qualification as qual_mod
    import pseofactory.seo_growth_loops as sgl_mod
    from pseofactory.maintenance import (
        AssetIntegrityEvaluator,
        AssetIntegrityReport,
        RetroReflectionEngine,
        SubprocessPropertyAdapter,
        TenantRegistry,
        reflect_and_recompile_all_assets,
    )

    base_html = (
        '<!DOCTYPE html><html lang="en"><head>'
        "<title>Corporate AMT CAMT Book Income Calculator | ProfitHelm</title>"
        '<meta name="description" content="Calculate Corporate AMT CAMT Book Income.">'
        '<link rel="canonical" href="https://profithelm.com/tools/corporate-amt-camt-book-income-minimum-tax-calculator/">'
        '<script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"FAQPage","mainEntity":[]}]}</script>'
        "</head><body><main id=\"main-content\"><div class=\"container\">"
        '<h1>Corporate AMT CAMT Book Income Calculator</h1>'
        '<aside class="quick-answer"><div class="quick-answer-body"><p>Baseline.</p></div></aside>'
        '<section class="faq-section"><div class="faq-list"></div></section>'
        "</div></main></body></html>"
    )
    polluted_overlay = {
        "slug": "corporate-amt-camt-book-income-minimum-tax-calculator",
        "tenant_id": "profithelm",
        "title_rewrite": "Corporate Amt Camt & Section 199a Qbi 280g Calculator | ProfitHelm",
        "meta_description": "Calculate Corporate Amt Camt and Section 199a Qbi and Section 280g statutory liabilities accurately.",
        "quick_answer": "Under IRC rules, Corporate Amt Camt and Section 199a Qbi and Section 280g compute deterministic federal liability.",
        "autonomous_citation_assertions": [
            "In 2026, Corporate Amt Camt and Section 280g models apply statutory thresholds."
        ],
        "h2_headings": ["Corporate Amt Camt & Section 199a Qbi Rules"],
        "faq_entries": [
            {
                "question": "How is Corporate Amt Camt calculated under Section 199a Qbi and 280g rules?",
                "answer": "Corporate Amt Camt applies 15% AFSI alongside Section 199a Qbi and Section 280g limits.",
            }
        ],
    }
    injected = inject_overlay_into_html(base_html, polluted_overlay)
    assert "Amt Camt" not in injected and "AMT CAMT" in injected
    assert "199a" not in injected and "199A" in injected
    assert "Qbi" not in injected and "QBI" in injected
    assert "280g" not in injected and "280G" in injected

    repo_dir = tmp_path / "ph_stage3b_repo"
    dist_dir = repo_dir / "dist"
    leaf_dir = dist_dir / "tools" / "irs-2027-tax-brackets" / "hawaii"
    leaf_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.html").write_text("<!DOCTYPE html><html><head></head><body><main></main></body></html>", encoding="utf-8")
    leaf_html = leaf_dir / "index.html"
    leaf_html.write_text(base_html, encoding="utf-8")

    ad = SubprocessPropertyAdapter(
        property_id="profithelm",
        brand_name="ProfitHelm",
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        dist_dir=dist_dir,
        repo_path=repo_dir,
        build_command=["true"],
    )
    reg = TenantRegistry()
    reg.register_adapter(ad)

    event_log: list[str] = []
    mutate_on_workflow = {"enabled": True}

    def _fake_retrofit_estate(*args, **kwargs):
        event_log.append("retrofit")
        return {"status": "PASS", "pages_retrofitted": 0, "porcelain_compiled": True}

    def _fake_run_all_seo_growth_workflows(*args, **kwargs):
        event_log.append("workflow")
        if mutate_on_workflow["enabled"]:
            # Simulate overlay injection mutating HTML on disk while internal_links has 0 mutated_donor_pages
            cur = leaf_html.read_text(encoding="utf-8")
            leaf_html.write_text(
                cur.replace("</main>", '<section class="overlay-section">Injected</section>\n</main>', 1),
                encoding="utf-8",
            )
        return {"status": "PASS", "internal_links": {"mutated_donor_pages": []}}

    def _clean_audit_all(self, adapter, *args, **kwargs):
        return AssetIntegrityReport(
            property_id=adapter.property_id,
            total_assets_checked=2,
            compliant_assets_count=2,
            drifted_assets_count=0,
            drifted_assets=[],
            status="PASS",
        )

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(AssetIntegrityEvaluator, "audit_all", _clean_audit_all)
    monkeypatch.setattr(RetroReflectionEngine, "audit_estate", classmethod(lambda cls, *a, **k: {"stale_count": 0, "stale_pages": []}))
    monkeypatch.setattr(RetroReflectionEngine, "retrofit_estate", classmethod(lambda cls, *a, **k: _fake_retrofit_estate(*a, **k)))
    monkeypatch.setattr(aff_mod, "audit_callout_destination_message_match", lambda *a, **k: {"status": "PASS", "mismatch_count": 0})
    monkeypatch.setattr(qual_mod, "reconcile_tenant_topical_authority_and_cannibalization", lambda *a, **k: {})
    monkeypatch.setattr(sgl_mod, "run_all_seo_growth_workflows", _fake_run_all_seo_growth_workflows)

    # Case 1: Clean estate (stale_count=0) with force=True skips redundant pre-retro and runs retrofit AFTER workflow mutation
    reflect_and_recompile_all_assets(
        properties=["profithelm"],
        force=True,
        run_downstream=False,
        registry=reg,
        defer_live_indexing=True,
        verbose=False,
    )
    assert event_log == ["workflow", "retrofit"], (
        f"Expected single post-workflow retrofit_estate after overlay HTML mutation on clean estate, got {event_log}"
    )

    # Case 2: When pre-retro already ran (stale_count=1, porcelain_compiled=True, force=False), workflow HTML mutation on disk
    # MUST still trigger a second post-workflow retrofit_estate even with mutated_donor_pages=[]
    event_log.clear()
    mutate_on_workflow["enabled"] = True
    monkeypatch.setattr(RetroReflectionEngine, "audit_estate", classmethod(lambda cls, *a, **k: {"stale_count": 1, "stale_pages": ["index.html"]}))
    reflect_and_recompile_all_assets(
        properties=["profithelm"],
        force=False,
        run_downstream=False,
        registry=reg,
        defer_live_indexing=True,
        verbose=False,
    )
    assert event_log == ["retrofit", "workflow", "retrofit"], (
        f"Expected pre-retro + post-workflow retrofit_estate after overlay HTML mutation, got {event_log}"
    )

    # Case 3: Control check - when pre-retro already ran and workflow makes ZERO HTML mutations on disk,
    # post-workflow retrofit_estate is skipped (proving Case 2 is driven by the HTML snapshot check, not force=True)
    event_log.clear()
    mutate_on_workflow["enabled"] = False
    reflect_and_recompile_all_assets(
        properties=["profithelm"],
        force=False,
        run_downstream=False,
        registry=reg,
        defer_live_indexing=True,
        verbose=False,
    )
    assert event_log == ["retrofit", "workflow"], (
        f"Expected no redundant post-workflow retrofit_estate when workflow did not mutate HTML, got {event_log}"
    )



