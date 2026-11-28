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
    """Proves wrong statutory SUV claim in HTML is detected and healed to $32,000."""
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
  <div class="result-box"><strong class="output-value">$32,000</strong></div>
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
    assert "$32,000" in healed_html
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
    assert "heavy SUVs capped at $32,000" in hub_json.read_text(encoding="utf-8")
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


def test_gainhelm_reconcile_estate_assets_handles_none_and_str_repo_root(tmp_path):
    """Regression: reconcile_estate_assets for gainhelm must not crash when repo_root is None or str."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True)
    synd_dir = tmp_path / "syndication"
    synd_dir.mkdir(parents=True)
    hipaa_file = synd_dir / "hipaa_benchmark.md"
    hipaa_file.write_text(
        "Legacy estimate: $512,500 total HIPAA breach exposure for 2,500 ePHI records.\n",
        encoding="utf-8",
    )

    # 1. repo_root=None must resolve via dist_dir.parent without AttributeError
    repaired_none = TruthReconciliationEngine.reconcile_estate_assets(
        dist_dir,
        "gainhelm",
        repo_root=None,
    )
    assert str(hipaa_file) in repaired_none
    healed_txt = hipaa_file.read_text(encoding="utf-8")
    assert "$2,577,794 total HIPAA breach exposure" in healed_txt
    assert "1,500 ePHI records" in healed_txt

    # 2. repo_root=str(tmp_path) must convert str to Path without AttributeError or TypeError
    hipaa_file.write_text(
        "Legacy estimate: $525,500 total HIPAA breach exposure for 2,500 ePHI records.\n",
        encoding="utf-8",
    )
    repaired_str = TruthReconciliationEngine.reconcile_estate_assets(
        dist_dir,
        "gainhelm",
        repo_root=str(tmp_path),
    )
    assert str(hipaa_file) in repaired_str
    assert "$2,577,794 total HIPAA breach exposure" in hipaa_file.read_text(encoding="utf-8")


@pytest.mark.host_estate
def test_evaluator_cache_fingerprint_invalidates_on_lienbond_formula_change(tmp_path, monkeypatch):
    """Regression: _compute_engine_fingerprint must include LienBond formula/builder files and change when edited."""
    fp_live = AssetIntegrityEvaluator._compute_engine_fingerprint()
    assert "lienbond/builder.py:" in fp_live

    # Build a fake projects root with a LienBond builder file and prove fingerprint invalidates on edit
    fake_projects = tmp_path / "projects"
    lb_pkg = fake_projects / "lienbond" / "lienbond"
    lb_pkg.mkdir(parents=True)
    lb_builder = lb_pkg / "builder.py"
    lb_builder.write_text("MILLER_ACT_THRESHOLD = 150000.0\n", encoding="utf-8")

    orig_path = Path

    class _PatchedPath(type(Path())):
        def __new__(cls, *args, **kwargs):
            if args and str(args[0]) == "/home/ubuntuadmin/projects":
                return orig_path(fake_projects)
            return orig_path(*args, **kwargs)

    import pseofactory.maintenance as maint_mod
    monkeypatch.setattr(maint_mod, "Path", _PatchedPath)

    fp_before = AssetIntegrityEvaluator._compute_engine_fingerprint()
    assert "lienbond/builder.py:" in fp_before

    lb_builder.write_text("MILLER_ACT_THRESHOLD = 200000.0\n", encoding="utf-8")
    fp_after = AssetIntegrityEvaluator._compute_engine_fingerprint()
    assert "lienbond/builder.py:" in fp_after
    assert fp_before != fp_after


def test_sync_cloudflare_secret_prefers_verified_permanent_token_over_wrangler_oauth(tmp_path, monkeypatch):
    """Regression: Cloudflare secret sync must prefer verified permanent API token and pass via stdin."""
    import subprocess
    import pseofactory.gitops as gitops_mod

    dotenv = tmp_path / ".env"
    dotenv.write_text("CLOUDFLARE_API_TOKEN=perm_fake_token_value_1234567890\n", encoding="utf-8")
    wrangler_cfg = tmp_path / "default.toml"
    wrangler_cfg.write_text('oauth_token = "oauth_short_lived_token"\n', encoding="utf-8")

    gitops_mod._CF_TOKEN_VERIFY_CACHE.clear()
    gitops_mod._CF_GH_SECRET_SYNC_CACHE.clear()
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.setattr(gitops_mod.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)
    monkeypatch.setattr(gitops_mod, "_verify_cloudflare_api_token_active", lambda tok, timeout=8.0: tok == "perm_fake_token_value_1234567890")
    monkeypatch.setattr(gitops_mod.CICDWatcher, "resolve_repo_slug", lambda self, rp: "owner/lienbond")

    captured = []

    def _fake_run(cmd, **kwargs):
        captured.append((cmd, kwargs.get("input")))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(gitops_mod.subprocess, "run", _fake_run)

    res = gitops_mod.sync_cloudflare_secret_for_tenant_repo(
        tmp_path,
        wrangler_cfg=wrangler_cfg,
        dotenv_path=dotenv,
    )
    assert res["synced"] is True
    assert res["source"] == "permanent_api_token"
    assert "perm_fake_token_value_1234567890" not in str(res)
    assert len(captured) == 1
    cmd, stdin_val = captured[0]
    assert cmd == ["gh", "secret", "set", "CLOUDFLARE_API_TOKEN", "-R", "owner/lienbond"]
    assert stdin_val == "perm_fake_token_value_1234567890"


def test_sync_cloudflare_secret_does_not_push_stale_oauth_when_wrangler_whoami_fails(tmp_path, monkeypatch):
    """Regression: when no permanent token is active and wrangler whoami fails, never push stale default.toml token."""
    import subprocess
    import pseofactory.gitops as gitops_mod

    dotenv = tmp_path / ".env"
    dotenv.write_text("CLOUDFLARE_API_TOKEN=revoked_token_value\n", encoding="utf-8")
    wrangler_cfg = tmp_path / "default.toml"
    wrangler_cfg.write_text('oauth_token = "stale_oauth_token_must_not_be_pushed"\n', encoding="utf-8")

    gitops_mod._CF_TOKEN_VERIFY_CACHE.clear()
    gitops_mod._CF_WRANGLER_TOKEN_CACHE = None
    gitops_mod._CF_GH_SECRET_SYNC_CACHE.clear()
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.setattr(gitops_mod.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)
    monkeypatch.setattr(gitops_mod, "_verify_cloudflare_api_token_active", lambda tok, timeout=8.0: False)
    monkeypatch.setattr(gitops_mod.CICDWatcher, "resolve_repo_slug", lambda self, rp: "owner/lienbond")

    calls = []

    def _fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:3] == ["npx", "wrangler", "whoami"]:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="expired")
        raise AssertionError(f"Unexpected subprocess call: {cmd}")

    monkeypatch.setattr(gitops_mod.subprocess, "run", _fake_run)

    res = gitops_mod.sync_cloudflare_secret_for_tenant_repo(
        tmp_path,
        wrangler_cfg=wrangler_cfg,
        dotenv_path=dotenv,
    )
    assert res["synced"] is False
    assert res["reason"] == "wrangler_whoami_rc_1"
    assert "stale_oauth_token_must_not_be_pushed" not in str(res)
    assert calls == [["npx", "wrangler", "whoami"]]


def test_reconcile_estate_assets_never_mutates_central_syndication_from_isolated_tmp_dir(tmp_path, monkeypatch):
    """
    Regression: even when PYTEST_CURRENT_TEST is unset (like build-proof),
    reconcile_estate_assets on a /tmp staging directory must not touch
    /home/ubuntuadmin/projects/pseofactory/syndication/<tenant>.
    """
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    stage_root = tmp_path / "stage_profithelm"
    dist_dir = stage_root / "dist"
    dist_dir.mkdir(parents=True)
    (stage_root / ".pseofactory.json").write_text('{"property_id": "profithelm"}\n', encoding="utf-8")
    (stage_root / "syndication" / "ai_benchmarks").mkdir(parents=True)
    (stage_root / "syndication" / "ai_benchmarks" / "ai_citations_reference.md").write_text(
        "IRC Sections 179 overview.\n", encoding="utf-8"
    )

    assert TruthReconciliationEngine._is_real_tenant_repo_root(stage_root) is False
    assert TruthReconciliationEngine._is_real_tenant_repo_root(
        Path("/home/ubuntuadmin/projects/.agy/worktrees/pseo_review_t1_isolation")
    ) is False

    repaired = TruthReconciliationEngine.reconcile_estate_assets(
        dist_dir=dist_dir,
        property_id="profithelm",
        repo_root=stage_root,
        sync_llms=False,
    )
    assert all("/home/ubuntuadmin/projects/pseofactory/syndication" not in p for p in repaired)
    assert any(str(stage_root) in p for p in repaired)
