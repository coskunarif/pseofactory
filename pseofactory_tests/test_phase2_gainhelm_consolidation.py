"""
Phase 2 Slice 0 + Slice 1 (GainHelm Pilot & Shared Compiler Foundations) Test Suite.
All tests execute strictly inside temporary directories and verify standalone
_pseo_substrate CI builds, oracle/SEO parity, Playwright JS interactivity,
categorical <select> handling, CSS heading typography, and DORA leak elimination.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import functools
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Dict

import pytest

import pseofactory.compiler as compiler_mod
from pseofactory.audit import ContentAccuracyAuditStage, audit_code_slop_ratchet
from pseofactory.compiler import compile_high_effort_page
from pseofactory.gitops import sync_tenant_test_isolation_guards
from pseofactory.maintenance import RetroReflectionEngine
from pseofactory.porcelain_shell import (
    generate_porcelain_stylesheet,
    sync_tenant_porcelain_shell,
)

LIVE_GAINHELM_REPO = Path("/home/ubuntuadmin/projects/gainhelm")


def _extract_clean_gainhelm_repo(dst_repo: Path) -> Path:
    """Extracts tracked GainHelm git archive HEAD plus content/deployed_voids.json without host dist/."""
    dst_repo.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        f"git -C {str(LIVE_GAINHELM_REPO)!r} archive HEAD | tar -x -C {str(dst_repo)!r}",
        shell=True,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"git archive failed: {proc.stderr}"
    shutil.copy2(
        LIVE_GAINHELM_REPO / "content" / "deployed_voids.json",
        dst_repo / "content" / "deployed_voids.json",
    )
    shutil.rmtree(dst_repo / "dist", ignore_errors=True)
    assert not (dst_repo / "dist").exists()
    return dst_repo


def test_slice0_css_commentary_title_and_compiler_select_and_gitops_slug(tmp_path: Path) -> None:
    # 1. CSS .commentary-title split from .variant-title (>= 18px: 1.25rem = 20px)
    for tenant_id in ("gainhelm", "prexvo", "lienbond", "profithelm"):
        css = generate_porcelain_stylesheet(tenant_id)
        comm_m = re.search(r"\.commentary-title\s*\{([^}]+)\}", css)
        var_m = re.search(r"\.variant-title\s*\{([^}]+)\}", css)
        assert comm_m is not None, f"Missing .commentary-title rule in {tenant_id} CSS"
        assert var_m is not None, f"Missing .variant-title rule in {tenant_id} CSS"
        assert "font-size: 1.25rem" in comm_m.group(1)
        assert "font-size: 1rem" in var_m.group(1)
        assert ".commentary-title,\n.variant-title" not in css

    # 2. compile_high_effort_page getInputs() preserves categorical non-numeric <select> string values
    res = compile_high_effort_page(
        {
            "slug": "dora-ict-third-party-risk-compliance-cost-calculator",
            "title": "DORA ICT Third-Party Risk Compliance Cost Model",
            "query": "dora ict third party risk compliance cost calculator",
            "property_id": "gainhelm",
            "domain": "gainhelm.com",
            "canonical_base": "https://gainhelm.com",
            "brand_name": "GainHelm",
            "model_name": "GainHelm-EU-DORA-ICT-ThirdParty-Risk-Cost-Model-2026",
            "statutory_authority": "EU Digital Operational Resilience Act (Regulation (EU) 2022/2554)",
            "economic_dataset": "ESAs Joint DORA Oversight Cost Series & BLS OEWS SOC 15-1212",
            "formula": "round(tlpt_red_team_fee + (critical_ict_vendors * fee_per_ict_vendor), 2)",
            "inputs": {"tlpt_red_team_fee": 42000.0, "critical_ict_vendors": 12.0, "fee_per_ict_vendor": 2800.0},
            "published_output": 75600.0,
            "sample_calculation": "TLPT $42,000 + 12 vendors at $2,800 ($33,600) = $75,600.00 DORA baseline.",
        }
    )
    js_match = re.search(r"function getInputs\(\)\s*\{(.*?)\n    \}", res["html"], flags=re.DOTALL)
    assert js_match is not None
    node_probe = (
        "var form = { querySelectorAll: function() { return ["
        "  { tagName: 'SELECT', name: 'regime_tier', value: 'essential_entity' },"
        "  { tagName: 'SELECT', name: 'vendor_count', value: '12' },"
        "  { tagName: 'INPUT', name: 'tlpt_red_team_fee', value: '-50' }"
        "]; } };\n"
        f"function getInputs() {{{js_match.group(1)}\n}}\n"
        "var out = getInputs();\n"
        "if (out.regime_tier !== 'essential_entity') { throw new Error('Expected categorical string, got: ' + JSON.stringify(out)); }\n"
        "if (out.vendor_count !== 12) { throw new Error('Expected numeric 12, got: ' + JSON.stringify(out)); }\n"
        "if (out.tlpt_red_team_fee !== 0) { throw new Error('Expected clamped 0, got: ' + JSON.stringify(out)); }\n"
        "console.log(JSON.stringify(out));\n"
    )
    node_proc = subprocess.run(["node", "-e", node_probe], capture_output=True, text=True, check=False)
    assert node_proc.returncode == 0, f"Node VM check failed: {node_proc.stderr}\n{node_proc.stdout}"
    parsed = json.loads(node_proc.stdout.strip())
    assert parsed == {"regime_tier": "essential_entity", "vendor_count": 12, "tlpt_red_team_fee": 0}

    # 3. gitops.py GainHelm CI uses _pseo_substrate & `gainhelm.cli build` (never copying host dist/),
    # and ProfitHelm test-isolation guard checks `prediction-market-tax` (not `-calculator`).
    gh_mock = tmp_path / "gh_mock"
    (gh_mock / "gainhelm").mkdir(parents=True)
    (gh_mock / "pyproject.toml").write_text('[project]\nname = "gainhelm"\n', encoding="utf-8")
    sync_tenant_test_isolation_guards(gh_mock, "gainhelm")
    gh_ci = (gh_mock / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "python3 -m gainhelm.cli build --dist /tmp/gh_ci_dist" in gh_ci
    assert "python3 -m gainhelm.cli audit --dist /tmp/gh_ci_dist" in gh_ci
    assert "python3 -m gainhelm.cli audit" in gh_ci
    assert "$GITHUB_WORKSPACE/gainhelm/_pseo_substrate" in gh_ci
    assert "/home/ubuntuadmin/projects/gainhelm/dist" not in gh_ci
    assert "/home/ubuntuadmin/projects/pseofactory" not in gh_ci

    ph_mock = tmp_path / "ph_mock"
    (ph_mock / "profithelm").mkdir(parents=True)
    (ph_mock / "profithelm" / "builder.py").write_text(
        '    DIST_DIR.mkdir(parents=True, exist_ok=True)\n'
        '    in_test = bool(os.getenv("PYTEST_CURRENT_TEST") or os.getenv("PROFITHELM_IN_TEST") == "1")\n',
        encoding="utf-8",
    )
    sync_tenant_test_isolation_guards(ph_mock, "profithelm")
    ph_builder = (ph_mock / "profithelm" / "builder.py").read_text(encoding="utf-8")
    assert '"prediction-market-tax"' in ph_builder
    assert "prediction-market-tax-calculator" not in ph_builder


def test_gainhelm_isolated_archive_sync_build_audit_pytest_and_browser(tmp_path: Path) -> None:
    from pseofactory.drift import write_substrate_lock
    from pseofactory.estate_common import build_thin_estate_builder_source

    tmp_repo = _extract_clean_gainhelm_repo(tmp_path / "gainhelm_isolated")
    sync_res = sync_tenant_porcelain_shell(tmp_repo, "gainhelm")
    assert sync_res["status"] in ("UPDATED", "UNCHANGED")
    expected_thin_builder = build_thin_estate_builder_source("gainhelm")
    builder_path = tmp_repo / "gainhelm" / "builder.py"
    thin_builder_txt = builder_path.read_text(encoding="utf-8")
    assert thin_builder_txt == expected_thin_builder

    # Also verify sync_tenant_porcelain_shell overwrites a modified/legacy builder.py in isolation.
    builder_path.write_text("# legacy gainhelm builder stub\n", encoding="utf-8")
    resync_res = sync_tenant_porcelain_shell(tmp_repo, "gainhelm")
    assert resync_res["status"] == "UPDATED"
    assert "gainhelm/builder.py" in resync_res["updated_files"]
    thin_builder_txt = builder_path.read_text(encoding="utf-8")
    assert thin_builder_txt == expected_thin_builder

    sync_tenant_test_isolation_guards(tmp_repo, "gainhelm")
    write_substrate_lock(tmp_repo, property_id="gainhelm", sync_ledgers=False)
    assert len(thin_builder_txt.splitlines()) <= 60
    assert "compile_gainhelm_estate" in thin_builder_txt
    assert "CALCULATION_MANIFESTS" in thin_builder_txt
    assert "TOOL_QUICK_ANSWERS" in thin_builder_txt

    standalone_env: Dict[str, str] = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("FACTORY_") and k != "PYTHONPATH"
    }
    standalone_env["PYTHONPATH"] = f"{tmp_repo}:{tmp_repo / 'gainhelm' / '_pseo_substrate'}"

    # Prove standalone _pseo_substrate resolves locally without worktree or host pseofactory on sys.path
    substrate_probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; from pathlib import Path; "
                "sys.path[:] = [p for p in sys.path if '/home/ubuntuadmin/projects/pseofactory' not in p and '/.agy/worktrees/' not in p]; "
                "import pseofactory, gainhelm.builder as gb; "
                "assert '_pseo_substrate' in Path(pseofactory.__file__).as_posix(), pseofactory.__file__; "
                "assert len(gb.CALCULATION_MANIFESTS) >= 13; "
                "assert len(gb.TOOL_QUICK_ANSWERS) >= 13"
            ),
        ],
        cwd=str(tmp_repo),
        env=standalone_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert substrate_probe.returncode == 0, substrate_probe.stderr

    build_proc = subprocess.run(
        [sys.executable, "-m", "gainhelm.cli", "build", "--envelope"],
        cwd=str(tmp_repo),
        env=standalone_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert build_proc.returncode == 0, f"{build_proc.stdout}\n{build_proc.stderr}"
    assert json.loads(build_proc.stdout.strip())["status"] == "PASS"

    pytest_proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-n", "0", "-q", "tests/"],
        cwd=str(tmp_repo),
        env=standalone_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert pytest_proc.returncode == 0, f"{pytest_proc.stdout}\n{pytest_proc.stderr}"

    audit_proc = subprocess.run(
        [sys.executable, "-m", "gainhelm.cli", "audit", "--envelope"],
        cwd=str(tmp_repo),
        env=standalone_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert audit_proc.returncode == 0, f"{audit_proc.stdout}\n{audit_proc.stderr}"
    audit_env = json.loads(audit_proc.stdout.strip())
    assert audit_env["verdict"] == "CERTIFIED_FRESH"
    assert audit_env["score"] == 10.0

    dist_dir = tmp_repo / "dist"
    # Standalone _pseo_substrate CI build preserves host engine_hash + synced_substrate_hash, includes .md assets,
    # and passes host AssetIntegrityEvaluator(enforce_master_seo=True) with zero drift
    from pseofactory.drift import compute_engine_hash as _host_engine_hash
    from pseofactory.maintenance import AssetIntegrityEvaluator as _HostAssetEval
    from pseofactory.maintenance import SubprocessPropertyAdapter as _HostSubAdapter

    host_eh = _host_engine_hash()
    lock_doc = json.loads((tmp_repo / "substrate_lock.json").read_text(encoding="utf-8"))
    assert lock_doc["engine_hash"] == host_eh
    assert lock_doc["substrate_hash"] == host_eh
    assert lock_doc.get("synced_substrate_hash") and lock_doc["synced_substrate_hash"] != host_eh

    eh_doc = json.loads((tmp_repo / ".agy" / "engine_hash.json").read_text(encoding="utf-8"))
    assert eh_doc["engine_hash"] == host_eh
    assert eh_doc.get("synced_substrate_hash") == lock_doc["synced_substrate_hash"]

    ledger_doc = json.loads((tmp_repo / ".agy" / "asset_ledger.json").read_text(encoding="utf-8"))
    assert any(k.endswith(".md") for k in ledger_doc.get("assets", {})), "Missing .md assets in asset_ledger.json"

    host_adp = _HostSubAdapter(
        property_id="gainhelm",
        brand_name="GainHelm",
        domain="gainhelm.com",
        canonical_base="https://gainhelm.com",
        dist_dir=dist_dir,
        repo_path=tmp_repo,
    )
    host_eval = _HostAssetEval(enforce_master_seo=True).audit_all(host_adp)
    assert host_eval.status == "PASS", f"Host audit failed after standalone _pseo_substrate build: {host_eval.drifted_assets}"

    assert not (dist_dir / "functions").exists()
    assert (dist_dir / "404.html").is_file()
    assert (dist_dir / "c5430f81d11340a6bda3162725e24a03.txt").is_file()
    for fname in ("sitemap.xml", "sitemap-hubs.xml", "sitemap-leaves.xml", "robots.txt", "_headers", "_redirects", "feed.xml", "llms.txt", "llms-full.txt", "catalog.json", "media-kit.json"):
        assert (dist_dir / fname).is_file(), f"Missing dist/{fname}"

    # All 21 sitemap URLs resolve cleanly to built HTML files
    sitemap_urls = re.findall(r"<loc>(.*?)</loc>", (dist_dir / "sitemap.xml").read_text(encoding="utf-8"))
    assert len(sitemap_urls) == 21
    for url in sitemap_urls:
        rel = url.replace("https://gainhelm.com", "").strip("/")
        target_html = (dist_dir / "index.html") if not rel else (dist_dir / rel / "index.html")
        assert target_html.is_file(), f"Missing sitemap HTML target for {url}: {target_html}"

    # Verify _headers stays <= 95 active blocks
    active_header_blocks = [
        ln for ln in (dist_dir / "_headers").read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln[:1].isspace() and not ln.strip().startswith("#")
    ]
    assert len(active_header_blocks) <= 95

    # Methodology & Disclaimers keep statutory tables after Porcelain normalization
    for gov_page in ("methodology", "disclaimers"):
        gov_html = (dist_dir / gov_page / "index.html").read_text(encoding="utf-8")
        assert "<table" in gov_html.lower(), f"Lost statutory table in {gov_page}/index.html"

    # Zero forbidden dashes across dist/ text artifacts
    for asset_path in dist_dir.rglob("*"):
        if asset_path.is_file() and asset_path.suffix.lower() in (".html", ".xml", ".json", ".txt", ".md"):
            content = asset_path.read_text(encoding="utf-8")
            assert "\u2014" not in content and "\u2013" not in content, f"Forbidden dash in {asset_path}"

    # DORA & void pages have zero SOC 2 / CMMC leakage and pass strict ContentAccuracyAuditStage
    dora_html = (dist_dir / "tools" / "dora-ict-third-party-risk-compliance-cost-calculator" / "index.html").read_text(encoding="utf-8")
    assert "$78,100.40" not in dora_html and "78,100" not in dora_html
    assert "$132,000.00" not in dora_html and "132,000" not in dora_html
    assert ContentAccuracyAuditStage.audit_rendered_asset(dora_html, property_id="gainhelm", strict=True) == []

    sec_html = (dist_dir / "tools" / "sec-cybersecurity-incident-materiality-8k-item-105-cost-calculator" / "index.html").read_text(encoding="utf-8")
    assert "$78,100.40" not in sec_html and "$132,000.00" not in sec_html
    assert ContentAccuracyAuditStage.audit_rendered_asset(sec_html, property_id="gainhelm", strict=True) == []

    # SOC 2 has extra_criteria input; non-SOC-2 core tools omit it
    soc2_html = (dist_dir / "tools" / "soc-2-audit-cost-calculator" / "index.html").read_text(encoding="utf-8")
    assert 'id="calc-input-extra_criteria"' in soc2_html
    for other_core in ("cmmc-2-0-compliance-cost-calculator", "iso-27001-certification-cost-calculator", "nist-800-171-sprs-score-calculator"):
        other_html = (dist_dir / "tools" / other_core / "index.html").read_text(encoding="utf-8")
        assert 'id="calc-input-extra_criteria"' not in other_html

    # Arbitrary custom dist & `<parent>/dist` builds from thin builder.py keep parent dir clean of repo artifacts
    for target_name in ("dist", "custom_gainhelm_out"):
        out_parent = tmp_path / f"wrap_{target_name}"
        out_parent.mkdir(parents=True, exist_ok=True)
        target_dist = out_parent / target_name
        custom_proc = subprocess.run(
            [
                sys.executable,
                "-c",
                f"import gainhelm.builder as gb; out = gb.build_all(dist_dir={str(target_dist)!r}); assert (out / 'index.html').is_file()",
            ],
            cwd=str(tmp_repo),
            env=standalone_env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert custom_proc.returncode == 0, custom_proc.stderr
        assert (target_dist / "tools" / "dora-ict-third-party-risk-compliance-cost-calculator" / "index.html").is_file()
        assert (target_dist / "tools" / "eu-ai-act-high-risk-conformity-assessment-cost-calculator" / "index.html").is_file()
        assert (target_dist / "tools" / "sec-cybersecurity-incident-materiality-8k-item-105-cost-calculator" / "index.html").is_file()
        assert not (out_parent / ".pseofactory.json").exists()
        assert not (out_parent / ".agy").exists()
        assert not (out_parent / "functions").exists()

    # Worktree-named directory on PYTHONPATH (without 'pseofactory' in dirname) takes precedence over _pseo_substrate
    alias_root = tmp_path / "phase2-gainhelm-pilot"
    (alias_root / "pseofactory").mkdir(parents=True, exist_ok=True)
    (alias_root / "pseofactory" / "__init__.py").write_text("__marker__ = 'worktree_override'\n", encoding="utf-8")
    (alias_root / "pseofactory" / "porcelain_shell.py").write_text("ok = True\n", encoding="utf-8")
    worktree_env = dict(standalone_env)
    worktree_env["PYTHONPATH"] = f"{alias_root}:{tmp_repo}"
    wt_probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; sys.path[:] = [p for p in sys.path if '/home/ubuntuadmin/projects/' not in p]; "
                "import gainhelm, gainhelm._pseo_porcelain, pseofactory; "
                "assert getattr(pseofactory, '__marker__', None) == 'worktree_override', pseofactory.__file__"
            ),
        ],
        cwd=str(tmp_repo),
        env=worktree_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert wt_probe.returncode == 0, wt_probe.stderr

    # SSR #serp-incumbent-depth-workbench on DORA, EU AI Act, and SEC 8-K omits SOC 2 defaults before any clicks
    void_ssr_expected = {
        "dora-ict-third-party-risk-compliance-cost-calculator": ("$57,590", "$82,000", "$24,410", "$433,073"),
        "eu-ai-act-high-risk-conformity-assessment-cost-calculator": ("$59,105", "$79,000", "$19,895", "$417,229"),
        "sec-cybersecurity-incident-materiality-8k-item-105-cost-calculator": ("$104,650", "$135,000", "$30,350", "$641,688"),
    }
    for v_slug, expected_vals in void_ssr_expected.items():
        v_html = (dist_dir / "tools" / v_slug / "index.html").read_text(encoding="utf-8")
        wb_m = re.search(
            r'<section[^>]*id=["\']serp-incumbent-depth-workbench["\'][\s\S]*?</section>',
            v_html,
            re.IGNORECASE,
        )
        assert wb_m is not None, f"Missing #serp-incumbent-depth-workbench on {v_slug}"
        wb_html = wb_m.group(0)
        for soc2_default in ("$84,000", "$58,200", "$25,800", "$488,000", 'value="84000"', 'value="25800"'):
            assert soc2_default not in wb_html, f"SOC 2 default {soc2_default!r} leaked in SSR workbench of {v_slug}"
        for val_tok in expected_vals:
            assert val_tok in wb_html, f"Expected preset-1 SSR value {val_tok!r} missing in workbench of {v_slug}"

    # Headless Chromium browser check: widgets recompute cleanly, .commentary-title == 20px, zero console/page errors
    from playwright.sync_api import sync_playwright

    class _MockTelemetryHandler(http.server.SimpleHTTPRequestHandler):
        def do_POST(self) -> None:
            self.send_response(204)
            self.end_headers()

        def log_message(self, *args: object) -> None:
            pass

    handler = functools.partial(_MockTelemetryHandler, directory=str(dist_dir))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    browser_errors = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            page.on("pageerror", lambda exc: browser_errors.append(f"pageerror: {exc}"))
            page.on("console", lambda msg: browser_errors.append(f"console.{msg.type}: {msg.text}") if msg.type == "error" else None)

            page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
            assert page.locator("#calc-input-extra_criteria").count() == 1
            assert page.text_content("#metric-soc2_total_cost") == "$78,100.40"
            page.fill("#calc-input-headcount", "150")
            page.dispatch_event("#calc-input-headcount", "input")
            assert page.text_content("#metric-soc2_total_cost") == "$92,700.80"

            page.goto(f"http://127.0.0.1:{port}/tools/cmmc-2-0-compliance-cost-calculator/", wait_until="networkidle")
            assert page.locator("#calc-input-extra_criteria").count() == 0
            assert page.eval_on_selector("h2.commentary-title", "el => getComputedStyle(el).fontSize") == "20px"
            page.click(".calc-switcher-btn:nth-child(2)")
            assert page.text_content("#metric-soc2_total_cost") == "$68,366.80"

            page.goto(f"http://127.0.0.1:{port}/tools/dora-ict-third-party-risk-compliance-cost-calculator/", wait_until="networkidle")
            assert page.text_content(".output-value") == "112,100"
            page.fill("#input-critical_ict_vendors", "20")
            page.dispatch_event("#input-critical_ict_vendors", "input")
            assert page.text_content(".output-value") == "134,500"
            browser.close()
    finally:
        srv.shutdown()

    assert browser_errors == [], f"Headless browser errors detected: {browser_errors}"


def test_gainhelm_overlay_leak_guard_and_slop_ratchet(tmp_path: Path) -> None:
    ratchet = audit_code_slop_ratchet()
    assert ratchet["status"] == "PASS", ratchet
    assert ratchet["duplicate_ast_blocks"] == 0
    assert ratchet["oversized_functions"] == []

    tmp_repo = _extract_clean_gainhelm_repo(tmp_path / "gh_overlay_guard")
    ov_dir = tmp_repo / ".agy" / "overlays"
    ov_dir.mkdir(parents=True, exist_ok=True)
    void_slugs = (
        ("dora-ict-third-party-risk-compliance-cost-calculator", "EU DORA ICT Third-Party Risk Compliance Cost Model | GainHelm", "EU DORA Regulation (EU) 2022/2554 TLPT red-team and Register of Information baseline equals $112,100.00."),
        ("eu-ai-act-high-risk-conformity-assessment-cost-calculator", "EU AI Act Article 43 Conformity Cost Model | GainHelm", "EU Regulation 2024/1689 Article 43 Notified Body and Annex IV dossier baseline equals $120,000.00."),
        ("sec-cybersecurity-incident-materiality-8k-item-105-cost-calculator", "SEC Form 8-K Item 1.05 Materiality Cost Model | GainHelm", "SEC Rule 33-11216 Form 8-K Item 1.05 4-day materiality readiness baseline equals $180,000.00."),
    )
    for v_slug, v_title, v_clean_assert in void_slugs:
        (ov_dir / f"{v_slug}.json").write_text(
            json.dumps(
                {
                    "slug": v_slug,
                    "tenant_id": "gainhelm",
                    "title_rewrite": v_title,
                    "meta_description": f"Calculate {v_slug} audit fees and GRC savings under AICPA SSAE 18, 32 CFR Part 170, and BLS SOC 15-1212.",
                    "description": f"Calculate {v_slug} audit fees under AICPA SSAE 18 and 32 CFR Part 170.",
                    "quick_answer": f"Under AICPA SSAE 18 (AT-C Section 205), DoD 32 CFR Part 170, and C3PAO tables, {v_slug} models CPA and C3PAO fees.",
                    "h2_headings": [
                        f"{v_slug}: 2026 CPA & C3PAO Attestation Fee Schedule",
                        "Compliance Readiness Scenarios",
                    ],
                    "preset_scenarios": [
                        {
                            "id": "preset-leaked",
                            "label": "Leaked CMMC C3PAO Preset",
                            "params": {"headcount": 45},
                            "description": "45-employee B2B SaaS modeling CPA or C3PAO attestation fees.",
                        }
                    ],
                    "comparison_rows": [
                        {
                            "scenario": "Unscoped Multi-Criteria Audit",
                            "baseline": "$64,500 Unbundled CPA / C3PAO Attestation",
                            "optimized": "$37,000 Scoped Attestation",
                            "delta": "-$27,500",
                            "authority": "AICPA SSAE 18 & 32 CFR Part 170",
                        }
                    ],
                    "faq_entries": [
                        {
                            "question": f"How is {v_slug} calculated?",
                            "answer": "Sums external CPA or C3PAO attestation fees under AICPA SSAE 18 and DoD 32 CFR Part 170 (CMMC 2.0).",
                        }
                    ],
                    "faq_schema": {
                        "@context": "https://schema.org",
                        "@type": "FAQPage",
                        "mainEntity": [
                            {
                                "@type": "Question",
                                "name": "Leaked C3PAO FAQ?",
                                "acceptedAnswer": {"@type": "Answer", "text": "Requires AICPA SSAE 18 and 32 CFR Part 170 CMMC 2.0 attestation."},
                            }
                        ],
                    },
                    "autonomous_citation_assertions": [
                        "Baseline SOC 2 Type II audit cost equals $78,100.40 under AICPA SSAE 18.",
                        v_clean_assert,
                    ],
                    "ai_mode_decision_matrix": [
                        {
                            "profile": "Series B SaaS",
                            "statutory_threshold": "AICPA SSAE 18",
                            "optimal_path": "SOC 2 Type II $78,100.40 baseline and $132,000.00 CMMC",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    assert hasattr(compiler_mod, "compile_gainhelm_estate"), "compile_gainhelm_estate missing from compiler.py"
    res = compiler_mod.compile_gainhelm_estate(tmp_repo, run_retrofit=True)
    assert res["status"] == "PASS"

    for v_slug, _, _ in void_slugs:
        v_html = (tmp_repo / "dist" / "tools" / v_slug / "index.html").read_text(encoding="utf-8")
        meta_m = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\']', v_html, re.IGNORECASE)
        assert meta_m is not None
        meta_txt = meta_m.group(1)
        assert "AICPA SSAE 18" not in meta_txt and "32 CFR Part 170" not in meta_txt, f"Leaked meta in {v_slug}: {meta_txt}"

        qa_m = re.search(r'<aside[^>]*class=["\'][^"\']*quick-answer[^"\']*["\'][^>]*>(.*?)</aside>', v_html, re.IGNORECASE | re.DOTALL)
        assert qa_m is not None
        qa_txt = qa_m.group(1)
        for bad_tok in ("AICPA SSAE 18", "32 CFR Part 170", "C3PAO", "CMMC 2.0", "SOC 2", "78,100", "$132,000"):
            assert bad_tok not in qa_txt, f"Leaked {bad_tok!r} in {v_slug} quick-answer: {qa_txt}"

        visible_body = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", "", v_html, flags=re.IGNORECASE)
        visible_no_footer = re.sub(r"<footer\b[\s\S]*?</footer>", "", visible_body, flags=re.IGNORECASE)
        # Strip intentional YMYL legal banner & cross-tool nav links before checking void framework claims
        visible_no_footer = re.sub(r'<div[^>]*ymyl-disclaimer-banner[^>]*>[\s\S]*?</div>', "", visible_no_footer, flags=re.IGNORECASE)
        visible_no_footer = re.sub(r"<a\b[^>]*href=[\"'][^\"']*soc-2[^\"']*[\"'][^>]*>.*?</a>", "", visible_no_footer, flags=re.IGNORECASE)
        visible_no_footer = re.sub(r"<a\b[^>]*href=[\"'][^\"']*cmmc[^\"']*[\"'][^>]*>.*?</a>", "", visible_no_footer, flags=re.IGNORECASE)
        for bad_claim in ("AICPA SSAE 18", "32 CFR Part 170", "C3PAO Attestation", "CPA or C3PAO", "78,100.40", "$132,000.00"):
            assert bad_claim.lower() not in visible_no_footer.lower(), f"Leaked {bad_claim!r} in {v_slug} rendered body"

        assert ContentAccuracyAuditStage.audit_rendered_asset(v_html, property_id="gainhelm", strict=True) == []

    dora_html = (tmp_repo / "dist" / "tools" / "dora-ict-third-party-risk-compliance-cost-calculator" / "index.html").read_text(encoding="utf-8")
    assert "$112,100" in dora_html

    # Direct empty-directory compilation fallback preserves oracle parity with zero gainhelm/checkout sources
    empty_out = tmp_path / "empty_gainhelm"
    empty_res = compiler_mod.compile_gainhelm_estate(empty_out, run_retrofit=True)
    assert empty_res["status"] == "PASS"
    empty_home = (empty_out / "dist" / "index.html").read_text(encoding="utf-8")
    assert 'id="oracle-soc2-total">$78100.40<' in empty_home
    assert 'id="oracle-cmmc-total">$132000.00<' in empty_home

    # RetroReflectionEngine manifest table mirrors central single source of truth
    assert "dora-ict-third-party-risk-compliance-cost-calculator" in RetroReflectionEngine.GAINHELM_FALLBACK_MANIFESTS


def test_reflect_recompiles_gainhelm_when_substrate_syncs_and_force(tmp_path: Path) -> None:
    """
    Verifies real un-mocked SubprocessPropertyAdapter.build_all() inside reflect_and_recompile_all_assets:
    - Fresh reflect(..., force=False, latch_state=False) skips mid-build ledger writes and passes Audit (0 drifted)
    - Subprocess reflect(..., force=True, latch_state=True) re-compiles, retrofits, latches ledger+engine_hash, and passes Audit (0 drifted)
    - Modified _pseo_substrate file is still caught by host AssetIntegrityEvaluator (no forged/weakened hash parity)
    """
    from pseofactory.maintenance import (
        AssetIntegrityEvaluator,
        DriftReason,
        SubprocessPropertyAdapter,
        TenantRegistry,
        reflect_and_recompile_all_assets,
    )
    from pseofactory.porcelain_shell import (
        _extract_defined_css_classes_for_audit,
        _find_undefined_ui_classes_in_html,
        sync_tenant_porcelain_shell,
    )

    gh_root = _extract_clean_gainhelm_repo(tmp_path / "gainhelm")
    # Remove pre-existing stale HEAD substrate_lock.json so r1 tests a clean unlatched cold-start reflect
    (gh_root / "substrate_lock.json").unlink(missing_ok=True)
    if (LIVE_GAINHELM_REPO / ".agy" / "overlays").is_dir():
        shutil.copytree(LIVE_GAINHELM_REPO / ".agy" / "overlays", gh_root / ".agy" / "overlays", dirs_exist_ok=True)
    sync_tenant_porcelain_shell(gh_root, "gainhelm")

    pkg_dir = gh_root / "gainhelm"
    dist_dir = gh_root / "dist"
    (dist_dir / "tools").mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><title>GainHelm Hub</title></head>"
        "<body><main><h1>GainHelm Hub</h1><p>Compliance calculators.</p></main></body></html>",
        encoding="utf-8",
    )

    # Corrupt synced substrate copy so sync_tenant_pseo_substrate + subprocess build triggers automatically
    sub_estate = pkg_dir / "_pseo_substrate" / "pseofactory" / "gainhelm_estate.py"
    assert sub_estate.is_file()
    sub_estate.write_text("# stale gainhelm estate\n", encoding="utf-8")

    adapter = SubprocessPropertyAdapter(
        property_id="gainhelm",
        brand_name="GainHelm",
        domain="gainhelm.com",
        canonical_base="https://gainhelm.com",
        dist_dir=dist_dir,
        repo_path=gh_root,
    )
    reg = TenantRegistry()
    reg.register_adapter(adapter)

    # 1. Fresh reflect with latch_state=False runs REAL SubprocessPropertyAdapter.build_all(), restores substrate,
    # leaves zero mid-build asset_ledger.json mismatches, and passes AssetIntegrityEvaluator(enforce_master_seo=True)
    r1 = reflect_and_recompile_all_assets(
        properties=["gainhelm"],
        force=False,
        latch_state=False,
        run_downstream=False,
        registry=reg,
        workspace_root=tmp_path,
    )
    assert r1.get("status") != "DRIFT", r1
    assert r1["property_reports"]["gainhelm"]["recompiled"] >= 1
    assert sub_estate.read_text(encoding="utf-8") != "# stale gainhelm estate\n"
    assert not (gh_root / ".agy" / "asset_ledger.json").exists()

    eval_after_r1 = AssetIntegrityEvaluator(enforce_master_seo=True).audit_all(adapter)
    assert eval_after_r1.status == "PASS", f"Drifted after latch_state=False: {eval_after_r1.drifted_assets[:5]}"
    retro_after_r1 = RetroReflectionEngine.audit_estate(dist_dir, "gainhelm")
    assert retro_after_r1.get("status") == "PASS" and retro_after_r1.get("stale_count", -1) == 0, retro_after_r1

    defined_css = _extract_defined_css_classes_for_audit((dist_dir / "css" / "style.css").read_text(encoding="utf-8"))
    for html_file in sorted(dist_dir.glob("**/*.html")):
        undef = _find_undefined_ui_classes_in_html(html_file.read_text(encoding="utf-8"), defined_css)
        assert not undef, f"Undefined CSS classes in {html_file.relative_to(dist_dir)}: {sorted(undef)}"

    # 2. force=True + latch_state=True latches final post-retrofit ledger/hashes cleanly and passes audit_all
    r2 = reflect_and_recompile_all_assets(
        properties=["gainhelm"],
        force=True,
        latch_state=True,
        run_downstream=False,
        registry=reg,
        workspace_root=tmp_path,
    )
    assert r2.get("status") != "DRIFT", r2
    assert (gh_root / ".agy" / "asset_ledger.json").is_file()
    assert (gh_root / ".agy" / "engine_hash.json").is_file()
    eval_after_r2 = AssetIntegrityEvaluator(enforce_master_seo=True).audit_all(adapter)
    assert eval_after_r2.status == "PASS", f"Drifted after latch_state=True: {eval_after_r2.drifted_assets[:5]}"

    # 3. Negative tamper test: modifying _pseo_substrate and running standalone build MUST be caught as ENGINE_HASH_DRIFT
    sub_estate.write_text(sub_estate.read_text(encoding="utf-8") + "\n# tampered in ci\n", encoding="utf-8")
    tamper_env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("FACTORY_") and k != "PYTHONPATH"
    }
    tamper_env["PYTHONPATH"] = f"{gh_root}:{pkg_dir / '_pseo_substrate'}"
    tamper_build = subprocess.run(
        [sys.executable, "-m", "gainhelm.cli", "build", "--envelope"],
        cwd=str(gh_root),
        env=tamper_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert tamper_build.returncode == 0, tamper_build.stderr
    eval_tampered = AssetIntegrityEvaluator(enforce_master_seo=True).audit_all(adapter)
    assert eval_tampered.status == "DRIFT"
    assert any(DriftReason.ENGINE_HASH_DRIFT in d.reasons for d in eval_tampered.drifted_assets)


def test_standalone_lienbond_cli_build_and_audit_preserve_bootstrap(tmp_path: Path) -> None:
    """
    Verifies cold-start standalone LienBond CLI flow:
    1. compile_lienbond_estate writes lienbond/__init__.py and tests/conftest.py WITH # [PSEO_SUBSTRATE_BOOTSTRAP].
    2. Standalone `python3 -m lienbond.cli build --envelope` (neither _pseo_substrate nor worktree pseofactory
       on PYTHONPATH) preserves # [PSEO_SUBSTRATE_BOOTSTRAP] in lienbond/__init__.py and tests/conftest.py.
    3. Subsequent standalone `python3 -m lienbond.cli audit --envelope` exits 0 with status==PASS,
       verdict==CERTIFIED_FRESH, and score==10.0.
    """
    lb_root = tmp_path / "lienbond"
    res = compiler_mod.compile_lienbond_estate(lb_root, run_retrofit=True)
    assert res["status"] == "PASS"

    init_file = lb_root / "lienbond" / "__init__.py"
    conftest_file = lb_root / "tests" / "conftest.py"
    assert "# [PSEO_SUBSTRATE_BOOTSTRAP]" in init_file.read_text(encoding="utf-8")
    assert "# [PSEO_SUBSTRATE_BOOTSTRAP]" in conftest_file.read_text(encoding="utf-8")

    standalone_env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("FACTORY_")
        and k not in ("PYTHONPATH", "WORKSPACE_ROOT", "PYTEST_CURRENT_TEST")
    }

    build_proc = subprocess.run(
        [sys.executable, "-m", "lienbond.cli", "build", "--envelope"],
        cwd=str(lb_root),
        env=standalone_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert build_proc.returncode == 0, f"stdout={build_proc.stdout}\nstderr={build_proc.stderr}"
    build_env = json.loads(build_proc.stdout.strip().splitlines()[-1])
    assert build_env["status"] == "PASS"
    assert "# [PSEO_SUBSTRATE_BOOTSTRAP]" in init_file.read_text(encoding="utf-8")
    assert "# [PSEO_SUBSTRATE_BOOTSTRAP]" in conftest_file.read_text(encoding="utf-8")

    audit_proc = subprocess.run(
        [sys.executable, "-m", "lienbond.cli", "audit", "--envelope"],
        cwd=str(lb_root),
        env=standalone_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert audit_proc.returncode == 0, f"stdout={audit_proc.stdout}\nstderr={audit_proc.stderr}"
    audit_env = json.loads(audit_proc.stdout.strip().splitlines()[-1])
    assert audit_env["status"] == "PASS"
    assert audit_env["verdict"] == "CERTIFIED_FRESH"
    assert audit_env["score"] == 10.0


def test_unmocked_subprocess_reflect_latch_false_refreshes_existing_ledger_outside_pytest(
    tmp_path: Path,
) -> None:
    """
    Verifies un-mocked host reflect(..., force=True, latch_state=False, run_downstream=False)
    executed in a real subprocess WITHOUT PYTEST_CURRENT_TEST refreshes an already-existing
    .agy/asset_ledger.json after dist/ mutations while keeping .agy/engine_hash.json untouched,
    so AssetIntegrityEvaluator(enforce_master_seo=True).audit_all(adapter) passes with 0 drifted assets.
    """
    from pseofactory.drift import write_substrate_lock

    gh_root = _extract_clean_gainhelm_repo(tmp_path / "gainhelm")
    (gh_root / "substrate_lock.json").unlink(missing_ok=True)
    if (LIVE_GAINHELM_REPO / ".agy" / "overlays").is_dir():
        shutil.copytree(
            LIVE_GAINHELM_REPO / ".agy" / "overlays",
            gh_root / ".agy" / "overlays",
            dirs_exist_ok=True,
        )
    sync_tenant_porcelain_shell(gh_root, "gainhelm")
    write_substrate_lock(gh_root, property_id="gainhelm", sync_ledgers=False)

    standalone_env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("FACTORY_")
        and k not in ("PYTHONPATH", "WORKSPACE_ROOT", "PYTEST_CURRENT_TEST")
    }
    build_proc = subprocess.run(
        [sys.executable, "-m", "gainhelm.cli", "build", "--envelope"],
        cwd=str(gh_root),
        env=standalone_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert build_proc.returncode == 0, f"stdout={build_proc.stdout}\nstderr={build_proc.stderr}"

    engine_hash_file = gh_root / ".agy" / "engine_hash.json"
    asset_ledger_file = gh_root / ".agy" / "asset_ledger.json"
    assert engine_hash_file.is_file()
    assert asset_ledger_file.is_file()
    eh_before_text = engine_hash_file.read_text(encoding="utf-8")
    eh_before_data = json.loads(eh_before_text)
    ledger_before_data = json.loads(asset_ledger_file.read_text(encoding="utf-8"))

    worktree_root = Path(__file__).resolve().parent.parent
    reflect_env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("FACTORY_")
        and k not in ("PYTHONPATH", "PYTEST_CURRENT_TEST")
    }
    reflect_env["PYTHONPATH"] = str(worktree_root)
    script = f"""
import json
import os
from pathlib import Path
from pseofactory.maintenance import (
    AssetIntegrityEvaluator,
    SubprocessPropertyAdapter,
    TenantRegistry,
    reflect_and_recompile_all_assets,
)

assert "PYTEST_CURRENT_TEST" not in os.environ
gh_root = Path({str(gh_root)!r})
ws_root = Path({str(tmp_path)!r})
adapter = SubprocessPropertyAdapter(
    property_id="gainhelm",
    brand_name="GainHelm",
    domain="gainhelm.com",
    canonical_base="https://gainhelm.com",
    dist_dir=gh_root / "dist",
    repo_path=gh_root,
)
reg = TenantRegistry()
reg.register_adapter(adapter)
res = reflect_and_recompile_all_assets(
    properties=["gainhelm"],
    force=True,
    latch_state=False,
    run_downstream=False,
    defer_live_indexing=True,
    registry=reg,
    workspace_root=ws_root,
)
ev = AssetIntegrityEvaluator(enforce_master_seo=True).audit_all(adapter)
print(json.dumps({{
    "reflect_status": res.get("status"),
    "recompiled": res["property_reports"]["gainhelm"]["recompiled"],
    "eval_status": ev.status,
    "drifted_count": len(ev.drifted_assets),
    "sample_drifted": [d.asset_path for d in ev.drifted_assets[:5]],
}}))
"""
    reflect_proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(worktree_root),
        env=reflect_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert reflect_proc.returncode == 0, f"stdout={reflect_proc.stdout}\nstderr={reflect_proc.stderr}"
    summary = json.loads(reflect_proc.stdout.strip().splitlines()[-1])
    assert summary["reflect_status"] == "PASS", summary
    assert summary["eval_status"] == "PASS", summary
    assert summary["drifted_count"] == 0, summary
    assert engine_hash_file.read_text(encoding="utf-8") == eh_before_text
    ledger_after = json.loads(asset_ledger_file.read_text(encoding="utf-8"))
    assert ledger_after["engine_hash"] == eh_before_data["engine_hash"]
    assert ledger_after["assets"] != ledger_before_data["assets"]
    assert any(
        k.endswith(".html") and ledger_after["assets"].get(k) != ledger_before_data["assets"].get(k)
        for k in ledger_after["assets"]
    )
    assert ledger_after["total_assets"] > 0

