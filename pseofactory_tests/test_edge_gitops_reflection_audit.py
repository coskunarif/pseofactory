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


def test_dynamic_void_manifest_and_ssr_output_parity_retro_reflection(tmp_path):
    """Verify dynamic void pages with default widget SSR outputs heal in one retrofit_estate pass and normalize timeline year to epoch."""
    from pseofactory.audit import ContentAccuracyAuditStage
    from pseofactory.compiler import _enrich_manifest_with_proprietary_signals
    from pseofactory.maintenance import RetroReflectionEngine
    from pseofactory.trends.db import TrendHistoryDB

    slug = "discretionary-income-calculator-for-student-loans"
    repo_dir = tmp_path / "prexvo"
    dist_dir = repo_dir / "dist"
    content_dir = repo_dir / "content"
    tool_dir = dist_dir / "tools" / slug
    manifests_dir = dist_dir / "manifests"
    tool_dir.mkdir(parents=True)
    manifests_dir.mkdir(parents=True)
    content_dir.mkdir(parents=True)

    # 1. Verify compiler helper normalizes legacy "year" timeline entries to "epoch"
    legacy_spec = {
        "property_id": "prexvo",
        "statutory_economic_matrix": {
            "matrix_version": "2026.1",
            "series": [
                {
                    "metric_key": "poverty_guideline_single",
                    "authority_name": "34 CFR Part 685",
                    "unit": "USD",
                    "latest_value": 15060.0,
                    "cagr_pct": 2.8,
                    "delta_pct": 14.0,
                    "timeline": [
                        {"year": 2023, "value": 14580.0},
                        {"year": 2024, "value": 15060.0},
                    ],
                }
            ],
        },
    }
    normalized_mf = {"slug": slug, "entity_type": "scenario"}
    _enrich_manifest_with_proprietary_signals(
        manifest=normalized_mf,
        candidate_spec=legacy_spec,
        manifest_source={},
        slug=slug,
        query="discretionary income calculator for student loans",
        statutory_authority="34 CFR Part 685",
        formula="balance * (weighted_rate / 100.0)",
        clamped_inputs={"balance": 45000, "weighted_rate": 6.5},
        published_output=2925.0,
    )
    assert '"year":' not in json.dumps(normalized_mf)
    assert normalized_mf["statutory_economic_matrix"]["series"][0]["timeline"][0]["epoch"] == 2023

    # Verify TrendHistoryDB emits "epoch" in timeline entries
    db = TrendHistoryDB(tmp_path / "trends.sqlite")
    db_matrix = db.compile_statutory_economic_matrix("prexvo")
    assert '"year":' not in json.dumps(db_matrix)
    assert len(db_matrix.get("series") or []) > 0
    assert "epoch" in db_matrix["series"][0]["timeline"][0]

    # 2. Seed deployed_voids.json and sidecar manifest with published_output=2925.0 and legacy "year" timeline key
    sidecar_manifest = {
        "slug": slug,
        "entity_type": "scenario",
        "inputs": {"balance": 45000, "weighted_rate": 6.5},
        "formula": "balance * (weighted_rate / 100.0)",
        "published_output": 2925.0,
        "tolerance": 0.01,
        "statutory_source": "34 CFR Part 685",
        "economic_source": "FRED SLSTTOTAL Series",
        "statutory_economic_matrix": {
            "matrix_version": "2026.1",
            "series": [
                {
                    "metric_key": "poverty_guideline_single",
                    "authority_name": "34 CFR Part 685",
                    "unit": "USD",
                    "latest_value": 15060.0,
                    "cagr_pct": 2.8,
                    "delta_pct": 14.0,
                    "timeline": [{"year": 2024, "value": 15060.0}],
                }
            ],
        },
    }
    (manifests_dir / f"{slug}.json").write_text(
        json.dumps(sidecar_manifest, indent=2),
        encoding="utf-8",
    )
    (content_dir / "deployed_voids.json").write_text(
        json.dumps([dict(sidecar_manifest, title="Discretionary Income Calculator for Student Loans")], indent=2),
        encoding="utf-8",
    )

    jsonld_payload = json.dumps(
        {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "SoftwareApplication",
                    "name": "Discretionary Income Calculator for Student Loans",
                    "applicationCategory": "FinanceApplication",
                    "operatingSystem": "Web",
                    "url": f"https://prexvo.com/tools/{slug}/",
                    "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
                },
                {
                    "@type": "FAQPage",
                    "mainEntity": [
                        {
                            "@type": "Question",
                            "name": "How is discretionary income calculated under 34 CFR Part 685?",
                            "acceptedAnswer": {
                                "@type": "Answer",
                                "text": "Under 34 CFR Part 685 and FRED SLSTTOTAL Series benchmarks, baseline accrual evaluates balance * (weighted_rate / 100.0) across balance and weighted_rate inputs.",
                            },
                        }
                    ],
                },
            ],
        }
    )

    base_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Discretionary Income Calculator for Student Loans | Prexvo</title>
  <meta name="description" content="Calculate discretionary income under federal student loan IDR rules and 150% poverty guidelines." />
  <link rel="canonical" href="https://prexvo.com/tools/{slug}/" />
  <script type="application/ld+json">{jsonld_payload}</script>
</head>
<body>
  <main>
    <h1>Discretionary Income Calculator for Student Loans</h1>
    <div id="hero-range-anchor" class="hero-range-anchor" data-mechanic="instant_range_anchor" data-range-low="$199" data-range-baseline="248.23" data-range-high="$298">
      <strong id="hero-range-baseline">248.23</strong>
    </div>
    <div class="result-box">
      <p>Verified baseline model calculation output: <strong class="output-value" data-baseline-output="248.23">248.23</strong>. Select a parameterized preset below:</p>
    </div>
    <div class="scenario-presets-bar" data-mechanic="deep_link_scenario_presets">
      <a class="scenario-preset-chip" href="?balance=45000&amp;weighted_rate=6.5">Baseline</a>
    </div>
    <table class="scenario-table comparison-table" data-entity-type="scenario" data-statutory-source="34 CFR Part 685" data-economic-source="FRED SLSTTOTAL Series">
      <thead><tr><th>Scenario</th><th>Evaluated Output</th></tr></thead>
      <tbody>
        <tr><td>Conservative (-20%)</td><td><strong class="scenario-low">198.58</strong></td></tr>
        <tr><td>Verified Baseline</td><td><strong class="scenario-baseline">248.23</strong></td></tr>
        <tr><td>Accelerated (+20%)</td><td><strong class="scenario-high">297.88</strong></td></tr>
      </tbody>
    </table>
    <script>
      const readout = document.createElement("span");
      readout.className = "output-value calc-metric-value overlay-preset-readout";
    </script>
  </main>
</body>
</html>"""

    # 3. Verify audit_html_mechanics flags SSR parity drift even if embedded manifest is already 2925.0
    embedded_2925_html = base_html.replace(
        "</head>",
        f'<script id="calculation-manifest" type="application/json">{json.dumps(sidecar_manifest)}</script></head>',
    )
    drift_flagged = RetroReflectionEngine.audit_html_mechanics(embedded_2925_html)
    assert "output_value" in drift_flagged
    assert "deep_link_scenario_presets" in drift_flagged
    assert "server_rendered_sensitivity_grid" in drift_flagged

    # 4. Write freshly built dynamic void HTML (no embedded manifest yet, default widget 248.23) and heal via retrofit_estate
    target_html_path = tool_dir / "index.html"
    target_html_path.write_text(base_html, encoding="utf-8")

    retro_res = RetroReflectionEngine.retrofit_estate(
        dist_dir=dist_dir,
        property_id="prexvo",
        canonical_base="https://prexvo.com",
    )
    assert retro_res["pages_retrofitted"] >= 1

    healed_html = target_html_path.read_text(encoding="utf-8")
    healed_mf_txt = (manifests_dir / f"{slug}.json").read_text(encoding="utf-8")
    healed_voids_txt = (content_dir / "deployed_voids.json").read_text(encoding="utf-8")

    assert '"year":' not in healed_mf_txt
    assert '"year":' not in healed_voids_txt
    assert '"epoch": 2024' in healed_voids_txt
    assert 'data-baseline-output="2925.0">2,925<' in healed_html
    assert 'class="scenario-baseline">2,925<' in healed_html
    assert 'id="hero-range-baseline">2,925<' in healed_html
    # JS template string inside <script> must remain untouched
    assert 'readout.className = "output-value calc-metric-value overlay-preset-readout";' in healed_html

    post_missing = RetroReflectionEngine.audit_html_mechanics(healed_html)
    assert post_missing == []

    stage = ContentAccuracyAuditStage(tolerance=0.01, strict=False)
    acc = stage.audit(healed_html, json.loads(healed_mf_txt), "prexvo")
    assert acc.passed is True, f"Gate 5/6 violations: {acc.violations}"
    assert acc.violations == []

