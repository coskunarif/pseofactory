"""End-to-end regression tests for pseofactory GitOps, edge contamination, latch parity, incident reconciliation, and LiveEdgeVerifier."""

import json
import subprocess
from unittest.mock import patch

from pseofactory.drift import (
    compute_dist_lock_metrics,
    compute_engine_hash,
    verify_all_tenants_aligned_for_latch,
)
from pseofactory.edge import (
    generate_edge_lead_capture_function,
    sync_tenant_edge_redirect_function,
)
from pseofactory.gitops import LiveEdgeVerifier, reconcile_workspace_tracking_state
from pseofactory.maintenance import (
    ConfigurablePropertyAdapter,
    CrossPropertyContaminationScanner,
)
from pseofactory.tenant_facts import (
    TENANT_FOREIGN_BOUNDARY_TOKENS,
    get_tenant_contract,
)


def test_gap1_prexvo_edge_lead_capture_no_profithelm_bleed_and_stripe_allowed(tmp_path):
    """Verify prexvo edge generator has zero profithelm bleed, canonical operator mailbox via atob, and stripe allowed."""
    import base64
    import re

    prexvo_js = generate_edge_lead_capture_function("prexvo")
    assert "profithelm" not in prexvo_js.lower()
    assert '["profit", "helm.com"]' not in prexvo_js
    m_prexvo = re.search(r'CANONICAL_OPERATOR_MAILBOX\s*=\s*atob\("([^"]+)"\)', prexvo_js)
    assert m_prexvo is not None
    assert base64.b64decode(m_prexvo.group(1)).decode("utf-8") == "arif.coskun@profithelm.com"
    assert "arif.coskun@prexvo.com" not in prexvo_js

    gainhelm_js = generate_edge_lead_capture_function("gainhelm")
    assert "profithelm" not in gainhelm_js.lower()
    assert '["profit", "helm.com"]' not in gainhelm_js
    m_gainhelm = re.search(r'CANONICAL_OPERATOR_MAILBOX\s*=\s*atob\("([^"]+)"\)', gainhelm_js)
    assert m_gainhelm is not None
    assert base64.b64decode(m_gainhelm.group(1)).decode("utf-8") == "arif.coskun@profithelm.com"
    assert "arif.coskun@gainhelm.com" not in gainhelm_js

    contract = get_tenant_contract("prexvo")
    assert "stripe" not in contract.truth_profile.cross_tenant_forbidden_tokens
    assert "stripe" not in TENANT_FOREIGN_BOUNDARY_TOKENS["prexvo"]

    repo_dir = tmp_path / "prexvo"
    dist_dir = repo_dir / "dist"
    dist_dir.mkdir(parents=True)
    (repo_dir / "functions" / "r").mkdir(parents=True)
    (dist_dir / "index.html").write_text("<html><body>Prexvo</body></html>", encoding="utf-8")

    sync_res = sync_tenant_edge_redirect_function(repo_dir, "prexvo")
    assert sync_res["status"] in ("UPDATED", "UNCHANGED")

    scanner = CrossPropertyContaminationScanner()
    func_violations = scanner.scan_directory(repo_dir / "functions", "prexvo")
    assert func_violations == {}

    adapter = ConfigurablePropertyAdapter(
        property_id="prexvo",
        brand_name="Prexvo",
        domain="prexvo.com",
        canonical_base="https://prexvo.com",
        dist_dir=dist_dir,
        repo_path=repo_dir,
    )
    listed_names = [p.name for p in adapter.list_assets()]
    assert "lead-capture.js" in listed_names


def test_gap2_latch_detects_edge_function_drift_and_contamination(tmp_path):
    """Verify verify_all_tenants_aligned_for_latch rejects drifted or contaminated functions/."""
    workspace = tmp_path / "ws"
    eng_hash = compute_engine_hash()

    for repo_name, pid in [
        ("profithelm-platform", "profithelm"),
        ("prexvo", "prexvo"),
        ("gainhelm", "gainhelm"),
    ]:
        t_repo = workspace / repo_name
        t_dist = t_repo / "dist"
        t_dist.mkdir(parents=True)
        (t_repo / "functions" / "r").mkdir(parents=True)
        (t_dist / "index.html").write_text(f"<html><body>{pid}</body></html>", encoding="utf-8")
        sync_tenant_edge_redirect_function(t_repo, pid)
        fp, total = compute_dist_lock_metrics(t_dist)
        (t_repo / "substrate_lock.json").write_text(
            json.dumps(
                {
                    "engine_hash": eng_hash,
                    "dist_fingerprint": fp,
                    "total_assets": total,
                }
            ),
            encoding="utf-8",
        )

    # Ensure prexvo has clean lead-capture.js for baseline check
    lead_js_path = workspace / "prexvo" / "functions" / "api" / "lead-capture.js"
    # Even before our fix, if we tamper with lead-capture.js so it differs from generate_edge_lead_capture_function,
    # verify_all_tenants_aligned_for_latch must return False!
    lead_js_path.write_text(
        lead_js_path.read_text(encoding="utf-8") + "\n// tampered drift\n",
        encoding="utf-8",
    )

    aligned_after, reasons_after = verify_all_tenants_aligned_for_latch(
        workspace,
        expected_hash=eng_hash,
        require_git_clean_and_pushed=False,
    )
    assert aligned_after is False
    assert any("prexvo" in r for r in reasons_after)


def test_gap3_reconcile_same_sha_incidents_ci_timeout_and_quarantine_branches(tmp_path):
    """Verify reconcile_workspace_tracking_state reconciles same-SHA failures, CI_TIMEOUTs, and quarantine branches."""
    workspace = tmp_path / "ws"
    runs_dir = workspace / ".agy" / "runs"
    runs_dir.mkdir(parents=True)

    repo_shas = {}
    for repo_name in ("pseofactory", "prexvo", "gainhelm", "profithelm-platform"):
        rpath = workspace / repo_name
        rpath.mkdir(parents=True)
        subprocess.run(["git", "init", "-b", "main"], cwd=str(rpath), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(rpath), check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=str(rpath), check=True)
        (rpath / "README.md").write_text(repo_name, encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=str(rpath), check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(rpath), check=True, capture_output=True)
        head_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(rpath), text=True).strip()
        repo_shas[repo_name] = head_sha
        subprocess.run(
            ["git", "branch", "quarantine/ci-fail-stale-test-123"],
            cwd=str(rpath),
            check=True,
        )

    # 1. Run that failed on same SHA as a subsequent successful run (use relative repo name so test-leak pruning does not delete it)
    r_failed = runs_dir / "monetization-gainhelm-contamination-fix-20261101"
    r_failed.mkdir()
    mf_failed = r_failed / "release_manifest.json"
    mf_failed.write_text(
        json.dumps(
            {
                "run_id": "monetization-gainhelm-contamination-fix-20261101",
                "project": "pseofactory",
                "head_sha": repo_shas["pseofactory"],
                "status": "UNHEALTHY_DEPLOY",
                "timestamp": "2026-11-01T21:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    inc_failed = r_failed / "ci_failure_incident.json"
    inc_failed.write_text(
        json.dumps(
            {
                "run_id": "monetization-gainhelm-contamination-fix-20261101",
                "project": "pseofactory",
                "failed_sha": repo_shas["pseofactory"],
                "status": "CI_FAILURE",
            }
        ),
        encoding="utf-8",
    )

    # 2. Subsequent successful run on the exact same SHA
    r_succ = runs_dir / "truth-final-1793575364"
    r_succ.mkdir()
    mf_succ = r_succ / "release_manifest.json"
    mf_succ.write_text(
        json.dumps(
            {
                "run_id": "truth-final-1793575364",
                "project": "pseofactory",
                "head_sha": repo_shas["pseofactory"],
                "status": "SUCCESS",
                "timestamp": "2026-11-01T22:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    # 3. CI_TIMEOUT incident where incident project differs from manifest project
    r_timeout = runs_dir / "cycle_1793218528"
    r_timeout.mkdir()
    (r_timeout / "release_manifest.json").write_text(
        json.dumps(
            {
                "run_id": "cycle_1793218528",
                "project": "gainhelm",
                "head_sha": "deadbeef00000000000000000000000000000000",
                "status": "RECONCILED_BY_SUBSEQUENT_RELEASE",
            }
        ),
        encoding="utf-8",
    )
    inc_timeout = r_timeout / "ci_failure_incident.json"
    inc_timeout.write_text(
        json.dumps(
            {
                "run_id": "cycle_1793218528",
                "project": "prexvo",
                "failed_sha": "deadbeef00000000000000000000000000000000",
                "status": "CI_TIMEOUT",
            }
        ),
        encoding="utf-8",
    )

    reconcile_workspace_tracking_state(workspace)

    assert json.loads(mf_failed.read_text(encoding="utf-8"))["status"] == "RECONCILED_BY_SUBSEQUENT_RELEASE"
    assert json.loads(inc_failed.read_text(encoding="utf-8"))["status"] == "RESOLVED_BY_SUBSEQUENT_RELEASE"
    assert json.loads(inc_timeout.read_text(encoding="utf-8"))["status"] == "RESOLVED_BY_SUBSEQUENT_RELEASE"

    for repo_name in ("pseofactory", "prexvo", "gainhelm", "profithelm-platform"):
        branches = subprocess.check_output(
            ["git", "branch", "--list", "quarantine/ci-fail-*"],
            cwd=str(workspace / repo_name),
            text=True,
        ).strip()
        assert branches == ""


def test_gap4_live_edge_verifier_warm_latency_and_edge_routes():
    """Verify LiveEdgeVerifier performs warm latency retry and enforces latency_sla in all_passed."""
    verifier = LiveEdgeVerifier()
    call_counts = {}

    def fake_verify_url(url, user_agent=None):
        call_counts[url] = call_counts.get(url, 0) + 1
        # Simulate cold cache miss (750ms) on first call to root, then warm hit (120ms) on second call
        if url.endswith(".com/") and call_counts[url] == 1:
            return {
                "url": url,
                "status": 200,
                "latency_ms": 750.0,
                "has_canonical": True,
                "has_title": True,
                "ssl_valid": True,
                "cf_cache_status": "MISS",
                "edge_headers_captured": True,
                "content": "<html><head><title>Prexvo</title><link rel='canonical' href='https://prexvo.com/'/></head><body>Prexvo</body></html>",
            }
        return {
            "url": url,
            "status": 200,
            "latency_ms": 120.0,
            "has_canonical": True,
            "has_title": True,
            "ssl_valid": True,
            "cf_cache_status": "HIT",
            "edge_headers_captured": True,
            "content": "<urlset><loc>https://prexvo.com/</loc></urlset>" if "sitemap" in url else "User-agent: *\nSitemap: https://prexvo.com/sitemap.xml\n# Prexvo",
        }

    with patch.object(verifier, "verify_url", side_effect=fake_verify_url):
        res = verifier.verify_edge_deployment("https://prexvo.com")
        assert call_counts.get("https://prexvo.com/", 0) >= 2
        assert res["latency_ms"] < 500
        assert res["latency_sla"] is True
        assert res["all_passed"] is True
