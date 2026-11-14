"""
Contract & Determinism Verification Suite for 4-Tenant Porcelain Light Unification.
Verifies (strictly inside isolated tmp_path sandboxes with PYTEST_CURRENT_TEST preserved):
1. Canonical Porcelain Light CSS (#fbfcfd canvas, #ffffff cards, #0f172a primary text),
   compile-time WCAG AA >= 4.5:1 contrast enforcement, and zero undefined var(--...).
2. Distinct blueprints for home_hub, tools_directory, calculator_leaf, comparison_leaf (/vs/*),
   editorial_guide (/guides/*), editorial_hub, governance_legal, error_404, and operator_pwa (/signal/).
3. Preservation of tenant publisher/affiliate <meta> & <link> tags across 100% of routes
   (including all 6 HTTP-200 governance pages and 404.html) + zero-mutation idempotency on pass 2.
4. Fail-closed Gate 10 physical CSS verification (#calculate-btn >= 44px in dist/css/style.css)
   and fail-closed .py/.json/.js/.html personal LinkedIn & personal maker detection + scrubbing.
5. Zero fake standalone shims or .xz snapshot bundles: real pure-stdlib substrate execution and
   byte-for-byte SHA-256 parity when running standalone with PYTHONPATH=<tmp_repo> only.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict

import pytest

from pseofactory.audit import audit_estate_accuracy, audit_rendered_asset
from pseofactory.browser_verifier import RouteManifestExtractor, UnifiedBrowserAuditor
from pseofactory.maintenance import CrossPropertyContaminationScanner
from pseofactory import porcelain_shell
from pseofactory.porcelain_shell import (
    GOVERNANCE_ROUTES,
    TENANT_BRAND_PALETTES,
    assert_porcelain_palette_wcag,
    audit_porcelain_estate_structure,
    audit_porcelain_shell_page,
    classify_porcelain_blueprint,
    compile_tenant_porcelain_estate,
    compute_wcag_contrast_ratio,
    extract_defined_and_referenced_css_vars,
    generate_porcelain_stylesheet,
    get_porcelain_tenant_profile,
    normalize_html_to_porcelain_shell,
    sync_tenant_porcelain_shell,
)
from pseofactory.server import EphemeralDistServer
from pseofactory.verifier import MasterSEOVerifier


def test_zero_fake_shims_or_tarball_bundle_helpers_exist():
    for banned_attr in (
        "install_standalone_pseofactory_shims",
        "write_tenant_estate_bundle",
        "restore_standalone_estate_bundle",
        "_StandaloneMasterSEOVerifier",
        "_passthrough_true",
    ):
        assert not hasattr(porcelain_shell, banned_attr), f"Banned fake shim helper still present: {banned_attr}"


def test_porcelain_stylesheets_wcag_aa_and_zero_undefined_vars():
    for tid in ("profithelm", "prexvo", "gainhelm", "lienbond"):
        css = generate_porcelain_stylesheet(tid)
        assert "--bg-canvas: #fbfcfd;" in css
        assert "--bg-surface: #ffffff;" in css
        assert "--text-primary: #0f172a;" in css
        assert "#calculate-btn" in css
        assert "min-height: 44px;" in css
        assert "@media print" in css
        defined, referenced = extract_defined_and_referenced_css_vars(css)
        assert referenced - defined == set(), f"Undefined CSS vars in {tid}: {referenced - defined}"
        pal = TENANT_BRAND_PALETTES[tid]
        assert compute_wcag_contrast_ratio(pal["brand_primary"], "#ffffff") >= 4.5
        assert compute_wcag_contrast_ratio("#ffffff", pal["brand_primary"]) >= 4.5

    bad_palette = dict(TENANT_BRAND_PALETTES["profithelm"])
    bad_palette["brand_primary"] = "#93c5fd"  # Fails 4.5:1 against #ffffff
    with pytest.raises(ValueError, match="WCAG AA contrast failure"):
        assert_porcelain_palette_wcag(bad_palette)


def test_operator_pwa_and_editorial_comparison_blueprint_classification():
    signal_html = '<!DOCTYPE html><html><body style="background:#000000;color:#ffffff;">Signal PWA</body></html>'
    assert classify_porcelain_blueprint("signal/index.html", signal_html) == "operator_pwa"
    assert classify_porcelain_blueprint("static/signal/index.html", signal_html) == "operator_pwa"
    norm_sig, bp = normalize_html_to_porcelain_shell(
        signal_html,
        "signal/index.html",
        get_porcelain_tenant_profile("profithelm"),
    )
    assert bp == "operator_pwa"
    assert norm_sig == signal_html
    assert audit_porcelain_shell_page(signal_html, "signal/index.html", check_shell_landmarks=True) == []

    assert classify_porcelain_blueprint("index.html") == "home_hub"
    assert classify_porcelain_blueprint("tools/index.html") == "tools_directory"
    assert classify_porcelain_blueprint("vs/index.html") == "editorial_hub"
    assert classify_porcelain_blueprint("guides/index.html") == "editorial_hub"
    assert classify_porcelain_blueprint("vs/stripe-vs-chargebee/index.html") == "comparison_leaf"
    assert classify_porcelain_blueprint("guides/asc-606-revenue-recognition/index.html") == "editorial_guide"
    assert classify_porcelain_blueprint(
        "tools/section-179-calculator/index.html",
        "<form><input type='number'><button id='calculate-btn'>Calculate</button></form>",
    ) == "calculator_leaf"
    assert classify_porcelain_blueprint("disclaimers/index.html") == "governance_legal"
    assert classify_porcelain_blueprint("404.html") == "error_404"

    # Verify /vs/* and /guides/* get Comparisons/Guides breadcrumbs and zero calculator quick-answer boilerplate
    profile = get_porcelain_tenant_profile("profithelm")
    vs_raw = (
        "<!DOCTYPE html><html lang='en'><head><title>Stripe Billing vs Chargebee | ProfitHelm</title>"
        "<meta name='description' content='Detailed B2B SaaS billing architecture comparison between Stripe Billing and Chargebee.'></head>"
        "<body><main><h1>Stripe Billing vs Chargebee</h1>"
        "<p>Evaluate seat-based metering, ASC 606 recognition schedules, and dunning recovery fees across both billing engines.</p>"
        "<table><thead><tr><th>Capability</th><th>Stripe Billing</th><th>Chargebee</th></tr></thead>"
        "<tbody><tr><td>Take Rate</td><td>0.7%</td><td>0.75% over tier</td></tr></tbody></table>"
        "</main></body></html>"
    )
    norm_vs, vs_bp = normalize_html_to_porcelain_shell(
        vs_raw, "vs/stripe-vs-chargebee/index.html", profile, existing_hubs={"vs", "guides"}
    )
    assert vs_bp == "comparison_leaf"
    vs_bc = norm_vs.split('<nav class="breadcrumbs"', 1)[1].split("</nav>", 1)[0]
    assert 'href="/vs/" class="touch-target">Comparisons</a>' in vs_bc
    assert 'href="/tools/"' not in vs_bc
    assert "statutory model governed by" not in norm_vs
    assert audit_porcelain_shell_page(
        norm_vs, "vs/stripe-vs-chargebee/index.html", check_shell_landmarks=True, property_id="profithelm"
    ) == []

    # Without a /vs/ hub index, Comparisons renders as a non-broken text crumb rather than a dead link
    norm_vs_no_hub, _ = normalize_html_to_porcelain_shell(vs_raw, "vs/stripe-vs-chargebee/index.html", profile)
    assert "<span>Comparisons</span>" in norm_vs_no_hub

    guide_raw = (
        "<!DOCTYPE html><html lang='en'><head><title>ASC 606 SaaS Revenue Guide | ProfitHelm</title>"
        "<meta name='description' content='Step-by-step ASC 606 SaaS revenue recognition implementation guide for finance teams.'></head>"
        "<body><main><h1>ASC 606 SaaS Revenue Recognition Guide</h1>"
        "<p>Multi-element software arrangements require standalone selling price allocation across performance obligations.</p>"
        "</main></body></html>"
    )
    norm_guide, guide_bp = normalize_html_to_porcelain_shell(
        guide_raw, "guides/asc-606-revenue-recognition/index.html", profile, existing_hubs={"vs", "guides"}
    )
    assert guide_bp == "editorial_guide"
    guide_bc = norm_guide.split('<nav class="breadcrumbs"', 1)[1].split("</nav>", 1)[0]
    assert 'href="/guides/" class="touch-target">Guides</a>' in guide_bc
    assert 'href="/tools/"' not in guide_bc
    assert "statutory model governed by" not in norm_guide
    assert audit_porcelain_shell_page(
        norm_guide, "guides/asc-606-revenue-recognition/index.html", check_shell_landmarks=True, property_id="profithelm"
    ) == []

    # Fail-closed check: if a /vs/ page has a mislabeled Calculators breadcrumb, audit catches it
    tampered_vs = norm_vs.replace(
        'href="/vs/" class="touch-target">Comparisons</a>',
        'href="/tools/" class="touch-target">Calculators</a>',
    )
    tampered_issues = audit_porcelain_shell_page(
        tampered_vs, "vs/stripe-vs-chargebee/index.html", check_shell_landmarks=True, property_id="profithelm"
    )
    assert any("mislabeled" in i.lower() or "calculator" in i.lower() for i in tampered_issues)


def test_gate_10_physical_css_touch_target_and_loophole_closures(tmp_path: Path):
    # 1. Inline #hex and rgb() outside <svg> must fail audit_porcelain_shell_page
    bad_inline_html = (
        "<!DOCTYPE html><html><head>"
        '<link rel="stylesheet" id="pseo-visual-primitives" data-version="pseo-primitives-v4" href="/css/style.css">'
        "</head><body>"
        '<div style="background: #07090e; color: rgb(148, 163, 184);">Dark leak</div>'
        '<span style="color: var(--nonexistent-token-xyz);">Orphan var</span>'
        "<style>.competing { color: red; }</style>"
        "</body></html>"
    )
    issues = audit_porcelain_shell_page(bad_inline_html, "tools/test/index.html", check_shell_landmarks=True)
    assert any("Raw color literal" in i for i in issues)
    assert any("Undefined CSS custom property" in i for i in issues)
    assert any("Competing inline <style>" in i for i in issues)
    assert any("Missing canonical <header" in i for i in issues)
    assert any("Missing canonical <main" in i for i in issues)

    # 2. Gate 10 physical CSS touch-target verification (#calculate-btn >= 44px in dist/css/style.css)
    dist_dir = tmp_path / "gate10_dist"
    (dist_dir / "css").mkdir(parents=True, exist_ok=True)
    calc_raw = (
        "<!DOCTYPE html><html lang='en'><head><title>Cap Rate Calculator | Prexvo</title>"
        "<meta name='description' content='Commercial real estate cap rate and NOI valuation calculator with debt service coverage metrics.'></head>"
        "<body><main><h1>Cap Rate Calculator</h1>"
        "<p>Calculate net operating income and capitalization rate using verified property operating figures.</p>"
        "<form><label for='noi'>Annual NOI</label><input id='noi' type='number' value='125000'>"
        "<button id='calculate-btn' type='submit'>Calculate Cap Rate</button></form>"
        "<section id='methodology'><h2>Methodology</h2><p>Cap Rate equals Annual NOI divided by Purchase Price.</p></section>"
        "</main></body></html>"
    )
    norm_calc, _ = normalize_html_to_porcelain_shell(
        calc_raw, "tools/cap-rate-calculator/index.html", get_porcelain_tenant_profile("prexvo")
    )

    # Missing dist/css/style.css -> Gate 10 MUST fail closed even though <link id="pseo-visual-primitives"> is in HTML!
    res_missing_css = audit_rendered_asset(
        norm_calc, {"slug": "tools/cap-rate-calculator/index.html"}, "prexvo", dist_dir=dist_dir
    )
    assert not res_missing_css.passed
    assert any("gate 10 (touch target)" in v.lower() for v in res_missing_css.violations)

    # Undersized #calculate-btn rule (32px < 44px) -> Gate 10 MUST fail closed
    (dist_dir / "css" / "style.css").write_text(
        "#calculate-btn { min-height: 32px; padding: 4px 8px; }\n", encoding="utf-8"
    )
    res_undersized_css = audit_rendered_asset(
        norm_calc, {"slug": "tools/cap-rate-calculator/index.html"}, "prexvo", dist_dir=dist_dir
    )
    assert not res_undersized_css.passed
    assert any("gate 10 (touch target)" in v.lower() for v in res_undersized_css.violations)

    # Canonical Porcelain stylesheet (>= 44px rule covering #calculate-btn) -> Gate 10 PASSES
    (dist_dir / "css" / "style.css").write_text(generate_porcelain_stylesheet("prexvo"), encoding="utf-8")
    res_valid_css = audit_rendered_asset(
        norm_calc, {"slug": "tools/cap-rate-calculator/index.html"}, "prexvo", dist_dir=dist_dir
    )
    assert not any("gate 10 (touch target)" in v.lower() for v in res_valid_css.violations)

    # 3. MasterSEOVerifier requires all 6 governance routes across all tenants (including lienbond)
    v_lb = MasterSEOVerifier(dist_dir=tmp_path / "lienbond" / "dist", domain="lienbond.com")
    for gov in GOVERNANCE_ROUTES:
        assert f"/{gov}/" in v_lb.required_endpoints

    # 4. RouteManifestExtractor stratifies blueprints cleanly
    mock_routes = [
        "/",
        "/tools/",
        "/tools/calc-a/",
        "/vs/a-vs-b/",
        "/guides/guide-a/",
        "/about/",
        "/disclaimers/",
        "/404.html",
    ]
    sample = RouteManifestExtractor(tmp_path).select_smart_routes(mock_routes, sample_size=6)
    assert "/" in sample
    assert "/tools/" in sample
    assert "/404.html" in sample

    # 5. Real Chrome CDP rejects missing <main>, Obsidian dark body bg, and low-contrast text
    auditor = UnifiedBrowserAuditor(dist_dir=tmp_path, fail_closed=True)
    cdp_ok, _ = auditor.check_cdp_reachability()
    if cdp_ok:
        bad_dist = tmp_path / "bad_cdp_dist"
        bad_dist.mkdir(parents=True, exist_ok=True)
        (bad_dist / "index.html").write_text(
            "<!DOCTYPE html><html lang='en'><head><title>Bad Dark Page Without Main</title>"
            "<style>body { background: #07090e; color: #334155; } .card { background: #0f172a; border-radius: 12px; padding: 24px; }</style>"
            "</head><body><div class='card'><h1>Dark Card Missing Landmarks</h1><p>Low contrast text</p></div></body></html>",
            encoding="utf-8",
        )
        with EphemeralDistServer(bad_dist, property_id="lienbond") as srv:
            finding = auditor.audit_route(srv.base_url, "/")
            h_types = {v.get("type") for v in finding.get("hierarchy_violations", [])}
            c_types = {v.get("type") for v in finding.get("card_geometry_violations", [])}
            assert "missing_site_header" in h_types
            assert "missing_main_landmark" in h_types
            assert "low_contrast_text" in h_types
            assert "non_porcelain_body_bg" in c_types
            assert "non_porcelain_card_bg" in c_types


def test_publisher_tags_on_all_routes_including_governance_and_zero_drift_idempotency(tmp_path: Path):
    for tid in ("profithelm", "prexvo", "gainhelm", "lienbond"):
        dist_dir = tmp_path / tid / "dist"
        (dist_dir / "tools" / "sample-calc").mkdir(parents=True, exist_ok=True)
        (dist_dir / "index.html").write_text(
            f"<!DOCTYPE html><html lang='en'><head><title>{tid.title()} Hub</title></head>"
            f"<body><main><h1>{tid.title()} Hub</h1><p>Deterministic statutory financial models.</p></main></body></html>",
            encoding="utf-8",
        )
        (dist_dir / "tools" / "index.html").write_text(
            f"<!DOCTYPE html><html lang='en'><head><title>{tid.title()} Calculators</title></head>"
            f"<body><main><h1>{tid.title()} Calculators</h1><p>Directory of deterministic calculators.</p></main></body></html>",
            encoding="utf-8",
        )
        (dist_dir / "tools" / "sample-calc" / "index.html").write_text(
            f"<!DOCTYPE html><html lang='en'><head><title>Sample Calculator | {tid.title()}</title></head>"
            f"<body><main><h1>Sample Calculator</h1><form><input type='number' value='100'>"
            f"<button id='calculate-btn'>Calculate</button></form></main></body></html>",
            encoding="utf-8",
        )

        rep1 = compile_tenant_porcelain_estate(dist_dir, tid)
        assert rep1["governance_written"] is True
        assert len(rep1["mutated_paths"]) > 0

        profile = get_porcelain_tenant_profile(tid)
        check_routes = [
            "index.html",
            "tools/index.html",
            "tools/sample-calc/index.html",
            "404.html",
            *[f"{gov}/index.html" for gov in GOVERNANCE_ROUTES],
        ]
        for rel in check_routes:
            html_text = (dist_dir / rel).read_text(encoding="utf-8")
            assert f"value='{profile['impact_verification_uuid']}'" in html_text or f'value="{profile["impact_verification_uuid"]}"' in html_text, f"{tid} {rel} missing Impact UUID"
            assert f'content="{profile["cj_property_id"]}"' in html_text, f"{tid} {rel} missing CJ property ID"
            assert 'name="partnerstack-publisher-entity"' in html_text, f"{tid} {rel} missing PartnerStack tag"
            assert 'name="ftc-affiliate-disclosure"' in html_text, f"{tid} {rel} missing FTC disclosure tag"
            assert 'href="/media-kit.json"' in html_text, f"{tid} {rel} missing /media-kit.json link"
            assert 'href="/catalog.json"' in html_text, f"{tid} {rel} missing /catalog.json link"
            if tid == "profithelm":
                assert 'name="sovrn-commerce-domain-key"' in html_text
            else:
                assert 'name="sovrn-commerce-domain-key"' not in html_text

        # Immediate second pass MUST produce zero mutations (100% idempotent)
        rep2 = compile_tenant_porcelain_estate(dist_dir, tid)
        assert rep2["governance_written"] is False
        assert rep2["mutated_paths"] == [], f"{tid} drifted on second pass: {rep2['mutated_paths']}"


def test_personal_linkedin_and_maker_scrub_plus_fail_closed_repo_scan(tmp_path: Path):
    repo_dir = tmp_path / "profithelm-platform"
    pkg_dir = repo_dir / "profithelm"
    dist_dir = repo_dir / "dist"
    manifest_dir = repo_dir / ".agy" / "directory_submissions"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    (pkg_dir / "directory_submitter.py").write_text(
        'MAKER = {"name": "Arif Coskun", "handle": "@arifcoskun", '
        '"linkedin": "https://www.linkedin.com/in/arif-coskun", '
        '"email": "mailto:arif.coskun@profithelm.com"}\n',
        encoding="utf-8",
    )
    (manifest_dir / "directory_manifest.json").write_text(
        json.dumps(
            {
                "maker_name": "Arif Coskun",
                "maker_handle": "@arifcoskun",
                "linkedin": "https://www.linkedin.com/in/arif-coskun",
            }
        ),
        encoding="utf-8",
    )
    (pkg_dir / "builder.py").write_text(
        "def build_all():\n"
        "    return True\n",
        encoding="utf-8",
    )
    (dist_dir / "index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><title>ProfitHelm</title>"
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"Organization","name":"ProfitHelm",'
        '"founder":{"@type":"Person","name":"Arif Coskun"},'
        '"sameAs":["https://www.linkedin.com/in/arif-coskun"]}'
        "</script></head><body><main><h1>ProfitHelm</h1>"
        "<p>Reviewed by Arif Coskun (<a href='https://www.linkedin.com/in/arif-coskun'>LinkedIn</a>).</p>"
        "</main></body></html>",
        encoding="utf-8",
    )

    # Before scrubbing, fail-closed repo scan catches .py, .json, and .html violations
    pre_issues = audit_porcelain_estate_structure(dist_dir, "profithelm")
    assert any("directory_submitter.py" in i for i in pre_issues)
    assert any("directory_manifest.json" in i for i in pre_issues)

    sync_tenant_porcelain_shell(repo_dir, "profithelm")
    compile_tenant_porcelain_estate(dist_dir, "profithelm")

    post_issues = audit_porcelain_estate_structure(dist_dir, "profithelm")
    assert post_issues == [], f"Unexpected issues after scrub + compile: {post_issues}"

    scrubbed_py = (pkg_dir / "directory_submitter.py").read_text(encoding="utf-8")
    assert "linkedin.com/in/" not in scrubbed_py.lower()
    assert "arif coskun" not in scrubbed_py.lower()
    assert "@arifcoskun" not in scrubbed_py.lower()
    assert "https://www.linkedin.com/company/143884102/" in scrubbed_py

    scrubbed_html = (dist_dir / "index.html").read_text(encoding="utf-8")
    assert "linkedin.com/in/" not in scrubbed_html.lower()
    assert "arif coskun" not in scrubbed_html.lower()
    assert "https://www.linkedin.com/company/143884102/" in scrubbed_html

    # Injecting a personal LinkedIn URL into a .js file or an .xz bundle must fail closed immediately
    (dist_dir / "leak.js").write_text('const author = "https://linkedin.com/in/arif-coskun";\n', encoding="utf-8")
    js_issues = audit_porcelain_estate_structure(dist_dir, "profithelm")
    assert any("leak.js" in i for i in js_issues)
    (dist_dir / "leak.js").unlink()

    (pkg_dir / "_pseo_estate_bundle.xz").write_bytes(b"fake")
    xz_issues = audit_porcelain_estate_structure(dist_dir, "profithelm")
    assert any(".xz" in i for i in xz_issues)


def _hash_dist_tree(dist_dir: Path) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for p in sorted(dist_dir.rglob("*")):
        if not p.is_file() or p.name.startswith("."):
            continue
        rel = p.relative_to(dist_dir).as_posix()
        if rel.startswith("syndication/"):
            continue
        if p.suffix.lower() in (".html", ".css", ".js", ".xml", ".txt", ".json") or p.name in ("_headers", "_redirects"):
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def test_sandbox_standalone_substrate_real_verification_and_sha256_parity(tmp_path: Path):
    assert "PYTEST_CURRENT_TEST" in os.environ, "PYTEST_CURRENT_TEST must remain intact"

    repo_dir = tmp_path / "lienbond"
    pkg_dir = repo_dir / "lienbond"
    tests_dir = repo_dir / "tests"
    dist_dir = repo_dir / "dist"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    tests_dir.mkdir(parents=True, exist_ok=True)

    # Minimal placeholder builder.py; sync_tenant_porcelain_shell overwrites lienbond/builder.py
    # with the real pseofactory.compiler.compile_lienbond_estate standalone entrypoint backed by _pseo_substrate.
    (pkg_dir / "builder.py").write_text("def build_all():\n    return None\n", encoding="utf-8")

    sync_res = sync_tenant_porcelain_shell(repo_dir, "lienbond")
    assert sync_res["status"] == "UPDATED"
    assert "lienbond/builder.py" in sync_res["updated_files"]
    assert any("_pseo_substrate/pseofactory/" in f for f in sync_res["updated_files"])
    assert list(repo_dir.rglob("*.xz")) == []

    standalone_env = {
        k: v for k, v in os.environ.items() if not k.startswith("FACTORY_")
    }
    assert "PYTEST_CURRENT_TEST" in standalone_env
    standalone_env["PYTHONPATH"] = str(repo_dir)
    standalone_env["PYTHONNOUSERSITE"] = "1"

    # Run full real LienBond build_all() + real MasterSEOVerifier + real audit_estate_accuracy inside a subprocess
    # where pseofactory repo is NOT on sys.path (proving _pseo_substrate executes the real 50-state compiler & verifier!)
    standalone_script = (
        "import sys\n"
        "from pathlib import Path\n"
        "sys.path[:] = [p for p in sys.path if '/home/ubuntuadmin/projects/' not in p]\n"
        "sys.meta_path[:] = [m for m in sys.meta_path if '_editable_' not in repr(m).lower()]\n"
        "assert not any('porcelain-shell-unification' in p or p.endswith('/pseofactory') for p in sys.path), sys.path\n"
        "import lienbond.builder as b\n"
        "out_dist = b.build_all()\n"
        "from pseofactory.verifier import MasterSEOVerifier\n"
        "from pseofactory.audit import audit_estate_accuracy\n"
        "import pseofactory\n"
        "assert '_pseo_substrate' in Path(pseofactory.__file__).as_posix(), pseofactory.__file__\n"
        "v = MasterSEOVerifier(dist_dir=out_dist, domain='lienbond.com')\n"
        "seo_rep = v.audit_seo_checklist()\n"
        "assert seo_rep['status'] == 'PASS', f'SEO errors: {seo_rep.get(\"issues\", [])[:5]}'\n"
        "acc = audit_estate_accuracy(out_dist, 'lienbond', strict=True)\n"
        "assert acc['status'] == 'PASS', {k: acc.get(k) for k in ('status', 'failed_assets_count', 'violations')}\n"
    )
    proc1 = subprocess.run(
        [sys.executable, "-c", standalone_script],
        cwd=str(repo_dir),
        env=standalone_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc1.returncode == 0, f"Standalone build+verify failed:\nSTDOUT:\n{proc1.stdout}\nSTDERR:\n{proc1.stderr}"

    hashes_after_standalone = _hash_dist_tree(dist_dir)
    assert "css/style.css" in hashes_after_standalone
    for gov in GOVERNANCE_ROUTES:
        assert f"{gov}/index.html" in hashes_after_standalone

    # Re-compile from parent pseofactory and assert 100% SHA-256 parity (zero drift between standalone & factory!)
    rep_factory = compile_tenant_porcelain_estate(dist_dir, "lienbond")
    assert rep_factory["mutated_paths"] == [], f"Factory vs standalone parity drift: {rep_factory['mutated_paths']}"
    hashes_after_factory = _hash_dist_tree(dist_dir)
    assert hashes_after_standalone == hashes_after_factory

    # Zero cross-property contamination across synced substrate & dist
    scanner = CrossPropertyContaminationScanner()
    contam = scanner.scan_directory(dist_dir, "lienbond")
    assert contam == {}, f"Cross-property contamination in synced sandbox: {list(contam.items())[:5]}"
    assert audit_porcelain_estate_structure(dist_dir, "lienbond") == []
    home_html = (dist_dir / "index.html").read_text(encoding="utf-8")
    assert "linkedin.com/in/" not in home_html.lower()
    assert "linkedin.com/company/" not in home_html.lower()
