"""
End-to-End Truth Check Test Suite for pseofactory Substrate.
Verifies cross-referencing of tables, calculator outputs, and headline claims
against official statutory rules and verified financial benchmarks for both
ProfitHelm and Prexvo.
Zero em-dashes. Zero en-dashes.
"""

import json
import pytest

from pseofactory.audit import audit_rendered_asset
from pseofactory.contracts import (
    STATUTORY_LIMITS,
    STATUTORY_TAX_BRACKETS,
    detect_uncorroborated_statutory_claims,
)
from pseofactory.maintenance import LiveTruthAuditEngine
from pseofactory.tenant_facts import TenantFactStore


def test_statutory_brackets_and_obbba_section_179_constants():
    """Verifies 2026/2027 statutory tax brackets and 2026 OBBBA Section 179 limits."""
    assert STATUTORY_LIMITS["section_179_max_deduction"][2026] == 2560000.0
    assert STATUTORY_LIMITS["section_179_phaseout_threshold"][2026] == 4090000.0
    assert STATUTORY_LIMITS["section_179_heavy_vehicle_suv"][2026] == 30500.0

    b2026_single = STATUTORY_TAX_BRACKETS[2026]["single"]
    assert b2026_single[0]["max_income"] == 12050.0
    assert b2026_single[1]["max_income"] == 48900.0
    assert b2026_single[2]["max_income"] == 104400.0

    b2027_single = STATUTORY_TAX_BRACKETS[2027]["single"]
    assert b2027_single[0]["max_income"] == 12200.0
    assert b2027_single[1]["max_income"] == 49600.0
    assert b2027_single[2]["max_income"] == 120200.0
    assert b2027_single[-1]["rate"] == 39.6

    clean_claims = (
        "Under 2026 OBBBA rules, the Section 179 deduction limit is $2,560,000 with a "
        "$4,090,000 phase-out threshold and $30,500 heavy SUV cap."
    )
    assert detect_uncorroborated_statutory_claims(clean_claims) == []


def test_tenant_fact_store_rejects_stale_profithelm_and_prexvo_claims():
    """Verifies TenantFactStore fail-closed rejection of stale figures on both properties."""
    store = TenantFactStore()

    # Valid ProfitHelm claims pass
    ok_ph, v_ph = store.verify_claim(
        "profithelm",
        "For a $125,000 single earner, federal tax increases by $4,349 (+22.7%), moving from $19,181 to $23,530. Full Cap ($2.56M).",
    )
    assert ok_ph is True
    assert v_ph == []

    # Stale ProfitHelm claims fail closed
    for stale_ph in (
        "Moving from $18,340 under TCJA to $22,238 post-sunset.",
        "Increases federal tax liability by $3,898 (+21.3%).",
        "Federal income tax accounts for $29,238 on $150k in California.",
        "GVWR: 8,500 lbs - Full Cap ($1.29M)",
    ):
        ok, violations = store.verify_claim("profithelm", stale_ph)
        assert ok is False, f"Expected stale claim to fail: {stale_ph}"
        assert len(violations) >= 1

    # Valid Prexvo claims pass
    ok_px, v_px = store.verify_claim(
        "prexvo",
        "Scenario A yields $248.23 monthly payment, $76.77 monthly interest subsidy, and $59,575.20 over 20 years. "
        "Scenario B yields $498.23 monthly payment and $78,617.64 across 158 months. "
        "<td>10% to 15% Discretionary</td>",
    )
    assert ok_px is True
    assert v_px == []

    # Stale Prexvo claims fail closed
    for stale_px in (
        "Scenario A required monthly payment is $244.58 with $58,700 total.",
        "Scenario B required monthly payment is $494.58 with $118,700 total.",
        '<div id="metric-rap_payment" class="calc-metric-value">$0.00</div>',
        "<td>15% Discretionary</td>",
    ):
        ok, violations = store.verify_claim("prexvo", stale_px)
        assert ok is False, f"Expected stale Prexvo claim to fail: {stale_px}"
        assert len(violations) >= 1


def test_live_truth_audit_engine_end_to_end_verification():
    """Verifies LiveTruthAuditEngine cross-checks manifests, scenario tables, and proprietary calculation tables."""
    engine = LiveTruthAuditEngine()

    valid_html = """
    <html>
      <body>
        <span class="output-value">$248.23</span>
        <script type="application/json" class="calculation-manifest">
          {"formula": "round((agi * 0.05) / 12 - (dependents * 50 / 12), 2)", "inputs": {"agi": 60000, "dependents": 1}, "published_output": 245.83}
        </script>
      </body>
    </html>
    """
    # Notice published_output 245.83 matches formula, but .output-value is 248.23 -> must flag mismatch
    violations_mismatch = engine.audit_html(valid_html, property_id="prexvo", context="test_mismatch.html")
    assert any("SSR .output-value" in v for v in violations_mismatch)

    aligned_html = """
    <html>
      <body>
        <span class="output-value">$245.83</span>
        <script type="application/json" class="calculation-manifest">
          {"formula": "round((agi * 0.05) / 12 - (dependents * 50 / 12), 2)", "inputs": {"agi": 60000, "dependents": 1}, "published_output": 245.83}
        </script>
        <table class="scenario-table">
          <tbody>
            <tr><td>0.8x</td><td>$196.66</td><td>$196.66</td><td>$2,359.97</td></tr>
            <tr><td>0.9x</td><td>$221.25</td><td>$221.25</td><td>$2,654.96</td></tr>
            <tr><td>1.0x</td><td>$245.83</td><td>$245.83</td><td>$2,949.96</td></tr>
            <tr><td>1.1x</td><td>$270.41</td><td>$270.41</td><td>$3,244.96</td></tr>
            <tr><td>1.2x</td><td>$295.00</td><td>$295.00</td><td>$3,539.95</td></tr>
          </tbody>
        </table>
      </body>
    </html>
    """
    assert engine.audit_html(aligned_html, property_id="prexvo", context="aligned.html") == []

    # Corrupt 1.2x row in scenario-table -> must fail closed
    corrupted_scenario = aligned_html.replace("$295.00", "$999.00")
    v_scen = engine.audit_html(corrupted_scenario, property_id="prexvo", context="corrupt_scenario.html")
    assert any("Scenario table row 1.2x" in v for v in v_scen)

    # Proprietary calculation table arithmetic check
    prop_table_ok = """
    <html>
      <body>
        <table class="proprietary-calculation-table">
          <tbody>
            <tr><td>Conservative Baseline</td><td>$100,000</td><td>$15,000</td><td>-2.5%</td><td>$85,000</td></tr>
          </tbody>
        </table>
      </body>
    </html>
    """
    assert engine.audit_html(prop_table_ok, property_id="profithelm", context="prop_ok.html") == []

    prop_table_bad = prop_table_ok.replace("$85,000", "$91,000")
    v_prop = engine.audit_html(prop_table_bad, property_id="profithelm", context="prop_bad.html")
    assert any("Proprietary table row arithmetic drift" in v for v in v_prop)


def test_test_vs_production_ledger_and_wal_isolation(tmp_path):
    """
    Verifies that GitOps and Distribution ledgers, WAL queues, and run manifests
    automatically isolate to tempfile.gettempdir() during pytest or test fixture execution
    and transition WAL events from PENDING to COMPLETED/STAGED.
    """
    import tempfile
    from pseofactory.gitops import GitOpsCoordinator, IdempotencyLedger, ShipperQueue
    from pseofactory.distributor import (
        DistributionIdempotencyLedger,
        SyndicationWALQueue,
        dispatch_to_distribution_lead,
    )

    tmp_root = tempfile.gettempdir()
    gitops_ledger = IdempotencyLedger()
    dist_ledger = DistributionIdempotencyLedger()
    shipper_q = ShipperQueue()
    synd_q = SyndicationWALQueue(property_id="test_property")
    coord = GitOpsCoordinator(repo_path=tmp_path, dry_run=True)

    assert str(gitops_ledger.ledger_path).startswith(tmp_root)
    assert str(dist_ledger.ledger_path).startswith(tmp_root)
    assert str(shipper_q.queues_dir).startswith(tmp_root)
    assert str(synd_q.queues_dir).startswith(tmp_root)
    assert str(coord.runs_base).startswith(tmp_root)

    # Verify ShipperQueue transitions from PENDING to COMPLETED
    rec = shipper_q.enqueue({"run_id": "test-run-1"})
    assert rec["status"] == "PENDING"
    shipper_q.complete_event(rec["event_id"], status="COMPLETED", details={"head_sha": "abc1234"})
    updated_lines = [
        json.loads(line)
        for line in shipper_q.queue_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    matched = [r for r in updated_lines if r.get("event_id") == rec["event_id"]]
    assert matched and matched[-1]["status"] == "COMPLETED"

    # Verify dispatch_to_distribution_lead completes its SyndicationWALQueue event
    dist_res = dispatch_to_distribution_lead(
        run_id="test-dist-wal-1",
        property_id="profithelm",
        dry_run=True,
        dist_dir=tmp_path,
        tools=[{"slug": "irs-2027-tax-brackets", "title": "IRS 2027 Tax Brackets Calculator"}],
    )
    assert dist_res["status"] == "STAGED"
    ph_q = SyndicationWALQueue(property_id="profithelm")
    wal_entries = [
        json.loads(line)
        for line in ph_q.queue_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(
        e.get("payload", {}).get("run_id") == "test-dist-wal-1" and e.get("status") == "STAGED"
        for e in wal_entries
    )


def test_stub_video_artifacts_detected_and_purged_by_reflection_and_audit(tmp_path):
    """
    Verifies that 36-byte ftypisom stub .mp4 files and unrendered batch_seo_catalog.json
    entries in dist/videos/ are flagged as drift by AssetIntegrityEvaluator and
    RetroReflectionEngine.audit_estate, and purged by RetroReflectionEngine.retrofit_estate.
    """
    from pseofactory.maintenance import (
        AssetIntegrityEvaluator,
        ConfigurablePropertyAdapter,
        DriftReason,
        RetroReflectionEngine,
    )

    dist_dir = tmp_path / "dist"
    videos_dir = dist_dir / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><title>ProfitHelm</title>"
        "<meta name='description' content='Deterministic tax and financial modeling calculators.'>"
        "<link rel='canonical' href='https://profithelm.com/'></head>"
        "<body><main><h1>ProfitHelm</h1></main></body></html>",
        encoding="utf-8",
    )

    stub_mp4 = videos_dir / "fake-stub-tool.mp4"
    stub_mp4.write_bytes(b"\x00\x00\x00 ftypisom\x00\x00\x02\x00isomiso2mp41\x00\x00\x00\x08free")
    assert stub_mp4.stat().st_size == 36

    real_mp4 = videos_dir / "real-rendered-tool.mp4"
    real_mp4.write_bytes(b"\x00\x00\x00 ftypisom" + (b"\x01" * 4096))

    cat_file = videos_dir / "batch_seo_catalog.json"
    cat_file.write_text(
        json.dumps(
            [
                {"slug": "fake-stub-tool", "video_file": str(stub_mp4), "size_bytes": 36},
                {"slug": "real-rendered-tool", "video_file": str(real_mp4), "size_bytes": real_mp4.stat().st_size},
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    # 1. RetroReflectionEngine.audit_estate detects the stub video
    estate_audit = RetroReflectionEngine.audit_estate(dist_dir, "profithelm")
    assert estate_audit["status"] == "STALE"
    assert "videos/batch_seo_catalog.json" in estate_audit["stale_pages"]

    # 2. AssetIntegrityEvaluator.audit_all flags STRUCTURAL_CONTRACT_VIOLATION
    adapter = ConfigurablePropertyAdapter(
        property_id="profithelm",
        brand_name="ProfitHelm",
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        dist_dir=dist_dir,
    )
    evaluator = AssetIntegrityEvaluator(enforce_master_seo=False)
    eval_rep = evaluator.audit_all(adapter, check_engine_drift=False, check_ledger=False)
    assert eval_rep.status == "DRIFT"
    assert any(
        DriftReason.STRUCTURAL_CONTRACT_VIOLATION in rec.reasons
        and "batch_seo_catalog.json" in rec.asset_path
        for rec in eval_rep.drifted_assets
    )

    # 3. RetroReflectionEngine.retrofit_estate purges the 36-byte stub and prunes the catalog
    retro_res = RetroReflectionEngine.retrofit_estate(dist_dir, "profithelm", canonical_base="https://profithelm.com")
    assert retro_res["status"] == "PASS"
    assert not stub_mp4.exists()
    assert real_mp4.exists()

    cleaned_cat = json.loads(cat_file.read_text(encoding="utf-8"))
    assert len(cleaned_cat) == 1
    assert cleaned_cat[0]["slug"] == "real-rendered-tool"


def test_concurrent_multi_tenant_cycle_manifest_and_draft_atomicity(tmp_path):
    """
    Replays the cycle_1791956856_26bd85 concurrent multi-tenant write overlap:
    runs profithelm and prexvo concurrently in a ThreadPoolExecutor sharing a single
    cycle_id and verifies zero JSON corruption, preserved per-tenant manifests under
    'tenants', and zero leakage into production /home/ubuntuadmin/projects/.agy/runs.
    """
    import concurrent.futures
    from pseofactory.gitops import GitOpsCoordinator
    from pseofactory.distributor import dispatch_to_distribution_lead

    shared_cycle_id = "cycle_stress_concurrent_overlap"
    runs_dir = tmp_path / "runs"

    def _run_tenant(prop: str) -> dict:
        t_repo = tmp_path / prop
        t_dist = t_repo / "dist"
        t_dist.mkdir(parents=True, exist_ok=True)
        coord = GitOpsCoordinator(repo_path=t_repo, run_id=shared_cycle_id, dry_run=True)
        coord.runs_base = runs_dir
        g_res = coord.dispatch_to_shipper(
            run_id=shared_cycle_id,
            property_id=prop,
            dry_run=True,
            skip_ci=True,
            skip_edge=True,
            dist_dir=t_dist,
        )
        slug = "student-loan-rap-calculator" if prop == "prexvo" else "irs-2027-tax-brackets"
        d_res = dispatch_to_distribution_lead(
            run_id=shared_cycle_id,
            property_id=prop,
            dry_run=True,
            dist_dir=t_dist,
            tools=[{"slug": slug, "title": slug.replace("-", " ").title()}],
        )
        return {"gitops": g_res.status, "dist": d_res["status"]}

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        f_ph = pool.submit(_run_tenant, "profithelm")
        f_px = pool.submit(_run_tenant, "prexvo")
        res_ph = f_ph.result()
        res_px = f_px.result()

    assert res_ph["gitops"] == "DRY_RUN"
    assert res_px["gitops"] == "DRY_RUN"
    assert res_ph["dist"] == "STAGED"
    assert res_px["dist"] == "STAGED"

    manifest_file = runs_dir / shared_cycle_id / "release_manifest.json"
    assert manifest_file.exists()
    manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert "tenants" in manifest_data
    assert "profithelm" in manifest_data["tenants"]
    assert "prexvo" in manifest_data["tenants"]
    assert (runs_dir / shared_cycle_id / "release_manifest_profithelm.json").exists()
    assert (runs_dir / shared_cycle_id / "release_manifest_prexvo.json").exists()
    from pathlib import Path
    assert not Path(f"/home/ubuntuadmin/projects/.agy/runs/{shared_cycle_id}").exists()


def test_automatic_workspace_tracking_reconciliation_without_manual_scripts(tmp_path):
    """
    Replays all historical tracking state corruption patterns:
    - Non-canonical test queue files (fast_distribution_queue.jsonl, profithelm-platform_release_queue.jsonl, prop_a_release_queue.jsonl)
    - Aborted PENDING WAL records in ShipperQueue and SyndicationWALQueue
    - Concatenated multi-writer JSON manifest (Extra data), 0-byte manifest, and test-leaked /tmp/pytest-... run dir
    - Superseded ci_failure_incident.json and UNHEALTHY_DEPLOY manifests
    Verifies reconcile_workspace_tracking_state() heals all of them automatically.
    """
    from pseofactory.gitops import ShipperQueue, reconcile_workspace_tracking_state
    from pseofactory.distributor import SyndicationWALQueue

    runs_dir = tmp_path / "runs"
    queues_dir = tmp_path / "queues"
    ledger_path = runs_dir / "gitops_idempotency_ledger.json"
    runs_dir.mkdir(parents=True, exist_ok=True)
    queues_dir.mkdir(parents=True, exist_ok=True)

    # 1. Seed non-canonical test queue files
    for bad_q in (
        "fast_distribution_queue.jsonl",
        "profithelm-platform_release_queue.jsonl",
        "prop_a_release_queue.jsonl",
        "t1_distribution_queue.jsonl",
    ):
        (queues_dir / bad_q).write_text("", encoding="utf-8")

    # 2. Seed aborted PENDING WAL events followed by a completed event
    sq = ShipperQueue(property_id="profithelm", queues_dir=queues_dir)
    aborted_evt = sq.enqueue({"run_id": "crashed-run-1", "token": "tok_aborted"})
    completed_evt = sq.enqueue({"run_id": "ok-run-2", "token": "tok_ok"})
    sq.complete_event(completed_evt["event_id"], status="COMPLETED")
    assert aborted_evt["status"] == "PENDING"

    dq = SyndicationWALQueue(property_id="prexvo", queues_dir=queues_dir)
    aborted_dist = dq.enqueue({"run_id": "crashed-dist-1"})
    completed_dist = dq.enqueue({"run_id": "ok-dist-2"})
    dq.complete_event(completed_dist["event_id"], status="COMPLETED")
    assert aborted_dist["status"] == "PENDING"

    # 3. Seed test-contaminated idempotency ledger
    ledger_path.write_text(
        json.dumps(
            {
                "tok_test_1": {"property_id": "test_property"},
                "tok_prod_1": {"property_id": "profithelm"},
            }
        ),
        encoding="utf-8",
    )

    # 4. Seed test-leaked run directory (/tmp/pytest-...)
    leaked_dir = runs_dir / "cycle_leaked_pytest"
    leaked_dir.mkdir(parents=True, exist_ok=True)
    (leaked_dir / "release_manifest.json").write_text(
        json.dumps({"project": "/tmp/pytest-of-ubuntuadmin/test_e2e/prexvo", "property_id": "prexvo"}),
        encoding="utf-8",
    )

    # 5. Seed concatenated JSON manifest (Extra data) and 0-byte manifest
    concat_dir = runs_dir / "cycle_concat_prod"
    concat_dir.mkdir(parents=True, exist_ok=True)
    obj1 = json.dumps({"status": "SUCCESS", "project": "/home/ubuntuadmin/projects/prexvo", "property_id": "prexvo"}, indent=2)
    obj2 = json.dumps({"status": "SUCCESS", "project": "/home/ubuntuadmin/projects/profithelm-platform", "property_id": "profithelm"}, indent=2)
    (concat_dir / "release_manifest.json").write_text(obj1 + "\n" + obj2, encoding="utf-8")

    empty_dir = runs_dir / "coldstart-proof-e2e"
    empty_dir.mkdir(parents=True, exist_ok=True)
    (empty_dir / "release_manifest.json").write_text("", encoding="utf-8")

    # 6. Seed superseded ci_failure_incident.json and UNHEALTHY_DEPLOY manifest
    inc_dir = runs_dir / "cycle_old_ci_fail"
    inc_dir.mkdir(parents=True, exist_ok=True)
    (inc_dir / "ci_failure_incident.json").write_text(
        json.dumps(
            {
                "run_id": "cycle_old_ci_fail",
                "project": "/home/ubuntuadmin/projects/profithelm-platform",
                "status": "CI_FAILURE",
                "failed_sha": "old_sha_111111",
            }
        ),
        encoding="utf-8",
    )
    (inc_dir / "release_manifest.json").write_text(
        json.dumps(
            {
                "run_id": "cycle_old_ci_fail",
                "project": "/home/ubuntuadmin/projects/profithelm-platform",
                "status": "UNHEALTHY_DEPLOY",
                "head_sha": "old_sha_111111",
            }
        ),
        encoding="utf-8",
    )

    rec_summary = reconcile_workspace_tracking_state(
        runs_dir=runs_dir,
        queues_dir=queues_dir,
        ledger_path=ledger_path,
        repo_heads={"profithelm-platform": "new_healthy_sha_999999"},
    )
    assert rec_summary["status"] == "PASS"
    assert rec_summary["pruned_queue_files"] == 4
    assert rec_summary["reconciled_wal_events"] >= 2
    assert rec_summary["pruned_ledger_tokens"] == 1
    assert rec_summary["pruned_test_runs"] == 1
    assert rec_summary["repaired_manifests"] >= 2
    assert rec_summary["resolved_incidents"] == 1

    # Verify zero PENDING WAL records remain
    for q_file in queues_dir.glob("*.jsonl"):
        for line in q_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                assert json.loads(line)["status"] != "PENDING"

    # Verify concatenated manifest is now valid JSON with both tenants preserved
    repaired_concat = json.loads((concat_dir / "release_manifest.json").read_text(encoding="utf-8"))
    assert "tenants" in repaired_concat
    assert "prexvo" in repaired_concat["tenants"]
    assert "profithelm" in repaired_concat["tenants"]

    # Verify incident and unhealthy manifest marked resolved
    resolved_inc = json.loads((inc_dir / "ci_failure_incident.json").read_text(encoding="utf-8"))
    assert resolved_inc["status"] == "RESOLVED_BY_SUBSEQUENT_RELEASE"
    resolved_man = json.loads((inc_dir / "release_manifest.json").read_text(encoding="utf-8"))
    assert resolved_man["status"] == "RECONCILED_BY_SUBSEQUENT_RELEASE"


def test_failed_deployment_rolls_back_substrate_lock_and_completes_wal(tmp_path):
    """
    Replays a delayed/failed GitOps deployment during MaintenanceLifecycle.run on a tenant
    git repository (profithelm-platform) and verifies that substrate_lock.json is rolled back
    to its exact prior bytes (leaving zero dirty files in git status) and WAL records are
    completed with PUSH_FAILED (never left PENDING).
    """
    import subprocess
    from unittest.mock import patch
    from pseofactory.gitops import GitOpsResult
    from pseofactory.maintenance import (
        AssetIntegrityEvaluator,
        ConfigurablePropertyAdapter,
        MaintenanceLifecycle,
        TenantRegistry,
    )

    tenant_repo = tmp_path / "profithelm-platform"
    dist_dir = tenant_repo / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(tenant_repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tenant_repo), "config", "user.email", "test@profithelm.com"], check=True)
    subprocess.run(["git", "-C", str(tenant_repo), "config", "user.name", "Test Runner"], check=True)

    original_lock_content = json.dumps(
        {
            "dist_fingerprint": "0000000000000000",
            "engine_hash": "1111111111111111",
            "property_id": "profithelm",
            "substrate_hash": "1111111111111111",
            "total_assets": 1,
        },
        indent=2,
        sort_keys=True,
    ) + "\n"
    lock_file = tenant_repo / "substrate_lock.json"
    lock_file.write_text(original_lock_content, encoding="utf-8")
    subprocess.run(["git", "-C", str(tenant_repo), "add", "substrate_lock.json"], check=True)
    subprocess.run(["git", "-C", str(tenant_repo), "commit", "-m", "chore: initial lock"], check=True, capture_output=True)

    (dist_dir / "index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        "<title>ProfitHelm Tax & Financial Calculators</title>"
        "<meta name='description' content='Deterministic tax and financial modeling calculators for founders.'>"
        "<link rel='canonical' href='https://profithelm.com/'></head>"
        "<body><main><h1>ProfitHelm Financial Modeling</h1>"
        "<div class='quick-answer'><p>Calculate exact federal and state tax liabilities in seconds.</p></div>"
        "<p>" + ("Quantitative statutory analysis across federal and state brackets. " * 30) + "</p>"
        "</main></body></html>",
        encoding="utf-8",
    )

    adapter = ConfigurablePropertyAdapter(
        property_id="profithelm",
        brand_name="ProfitHelm",
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        dist_dir=dist_dir,
        repo_path=tenant_repo,
    )
    reg = TenantRegistry()
    reg.register_adapter(adapter)

    lifecycle = MaintenanceLifecycle(
        registry=reg,
        evaluator=AssetIntegrityEvaluator(enforce_master_seo=False),
    )
    with patch(
        "pseofactory.gitops.GitOpsCoordinator.dispatch_to_shipper",
        return_value=GitOpsResult(status="PUSH_FAILED", property_id="profithelm", error="Simulated network failure"),
    ):
        res = lifecycle.run(
            adapter,
            force=True,
            dry_run=False,
            enable_gitops=True,
            enable_distribution=False,
        )

    assert res.status == "FAILED"
    assert res.gitops_status == "FAILED"
    assert lock_file.read_text(encoding="utf-8") == original_lock_content
    st_out = subprocess.run(
        ["git", "-C", str(tenant_repo), "status", "--porcelain", "-uno"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert st_out == ""


def test_daily_indexing_inspector_auto_remediate_drains_rollover_queue(tmp_path):
    """
    Replays a pending GSC rollover queue (when overall_status is PASS and candidate queue is empty)
    during DailyIndexingInspector.run_inspection(auto_remediate=True) and verifies that:
    1. Auto-remediation runs and drains the rollover queue to 0 when child sitemaps pass.
    2. Rollover-only reconciliation does NOT write untracked content/overlays/*.json files
       or mutate existing dist/tools/*/index.html canonical tags in place.
    """
    from unittest.mock import patch
    from pseofactory.indexing_inspector import DailyIndexingInspector
    from pseofactory.telemetry import AtomicTelemetryLogger

    agy_dir = tmp_path / ".agy"
    agy_dir.mkdir(parents=True, exist_ok=True)
    dist_tool_dir = tmp_path / "dist" / "tools" / "saas-runway-calculator"
    dist_tool_dir.mkdir(parents=True, exist_ok=True)
    original_html = (
        '<!DOCTYPE html><html lang="en"><head>\n'
        '  <meta charset="utf-8">\n'
        '  <link rel="canonical" href="https://profithelm.com/tools/saas-runway-calculator">\n'
        '  <title>SaaS Runway Calculator | ProfitHelm</title>\n'
        '</head><body><main><h1>SaaS Runway Calculator</h1></main></body></html>\n'
    )
    tool_html_file = dist_tool_dir / "index.html"
    tool_html_file.write_text(original_html, encoding="utf-8")

    rollover_path = agy_dir / "gsc_rollover_queue.json"
    rollover_path.write_text(
        json.dumps([
            "https://profithelm.com/",
            "https://profithelm.com/tools/saas-runway-calculator",
        ]),
        encoding="utf-8",
    )
    quarantine_path = agy_dir / "indexing_quarantine_ledger.json"
    quarantine_path.write_text(json.dumps({}), encoding="utf-8")
    velocity_path = agy_dir / "indexing_velocity_ledger.json"
    velocity_path.write_text(json.dumps({"routes": []}), encoding="utf-8")
    recovery_path = agy_dir / "metric_recovery_ledger.json"
    telemetry_path = agy_dir / "telemetry.jsonl"

    inspector = DailyIndexingInspector(
        tenant_id="profithelm",
        base_dir=tmp_path,
        agy_dir=agy_dir,
        recovery_ledger_path=recovery_path,
        quarantine_ledger_path=quarantine_path,
        velocity_ledger_path=velocity_path,
        rollover_queue_path=rollover_path,
        telemetry_logger=AtomicTelemetryLogger(log_path=telemetry_path),
    )

    with patch.object(
        inspector,
        "audit_child_sitemaps_and_section_coverage",
        return_value={"status": "PASS", "section_coverage": {}},
    ):
        rep = inspector.run_inspection(dry_run=False, auto_remediate=True)

    assert rep["audit_status"] == "PASS"
    assert rep["gsc_rollover"]["queue_size"] == 0
    assert rep["gsc_rollover"]["reconciled_urls_count"] == 2
    assert json.loads(rollover_path.read_text(encoding="utf-8")) == []
    assert not (tmp_path / "content" / "overlays").exists()
    assert tool_html_file.read_text(encoding="utf-8") == original_html


def test_tenant_tracked_test_repair_records_and_test_isolation_self_healing(tmp_path):
    """
    Replays the exact failure mode where Stage 5 pytest runs in profithelm-platform
    created .agy/runs/test_run_*/repair_bundle.json and Stage 6 'git add -f .agy/runs/'
    force-committed them into HEAD (so every subsequent test run left modified
    .agy/runs/test_run_*/repair_bundle.json records in git status).
    Verifies that:
    1. sync_tenant_test_isolation_guards injects test-run isolation into profithelm/repair.py
       and unstages .agy/runs in profithelm/factory.py.
    2. reconcile_workspace_tracking_state prunes test_run_* directories across .agy/runs
       and cleans dirty tracked .agy/runs/* files in tenant working trees.
    3. GitOpsCoordinator.stage_tracked untracks any force-committed .agy/runs/* files
       so subsequent commits permanently remove them from git tracking.
    """
    import subprocess
    import pseofactory.gitops as gitops_mod
    from pseofactory.gitops import (
        GitOpsCoordinator,
        reconcile_workspace_tracking_state,
    )

    tenant_repo = tmp_path / "profithelm-platform"
    tenant_repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(tenant_repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tenant_repo), "config", "user.email", "test@profithelm.com"], check=True)
    subprocess.run(["git", "-C", str(tenant_repo), "config", "user.name", "Test Runner"], check=True)

    (tenant_repo / ".gitignore").write_text(".agy/\ndist/\n", encoding="utf-8")
    ph_pkg = tenant_repo / "profithelm"
    ph_pkg.mkdir(parents=True, exist_ok=True)
    repair_py = ph_pkg / "repair.py"
    repair_py.write_text(
        'from pathlib import Path\n'
        'import os\n'
        'BASE_DIR = Path(__file__).resolve().parent.parent\n'
        'def create_repair_context_bundle(run_id=None):\n'
        '    saved_path = None\n'
        '    if run_id:\n'
        '        target_locations = [\n'
        '            Path(".agy/runs") / run_id / "repair_bundle.json",\n'
        '            Path("/home/ubuntuadmin/projects/.agy/runs") / run_id / "repair_bundle.json",\n'
        '            BASE_DIR / ".agy" / "runs" / run_id / "repair_bundle.json",\n'
        '        ]\n'
        '    return saved_path\n',
        encoding="utf-8",
    )
    factory_py = ph_pkg / "factory.py"
    factory_py.write_text(
        'import subprocess\n'
        'def run_pipeline(redirect_mappings, redirects_file, gsc_actions, synthesized_spec, dist_tools, BASE_DIR, env, in_test):\n'
        '        if redirect_mappings:\n'
        '            redirects_file.parent.mkdir(parents=True, exist_ok=True)\n'
        '            redirects_file.write_text(json.dumps(redirect_mappings, indent=2), encoding="utf-8")\n'
        '            from profithelm.config import register_tool\n'
        '            if synthesized_spec:\n'
        '                register_tool(synthesized_spec, persist=True)\n'
        '        synd_dir = export_all_syndication_files(tools=dist_tools)\n'
        '    subprocess.run(\n'
        '        ["git", "add", "-f", "dist/", "machine_endpoints/", ".agy/runs/", "profithelm/data/statutory.db"],\n'
        '        cwd=BASE_DIR,\n'
        '        env=env,\n'
        '        check=False,\n'
        '    )\n',
        encoding="utf-8",
    )
    generator_py = ph_pkg / "generator.py"
    generator_py.write_text(
        'from datetime import datetime, timezone\n'
        'import json\n'
        'def check_env():\n'
        '    return "PYTEST_CURRENT_TEST" in os.environ\n',
        encoding="utf-8",
    )

    # Simulate force-tracked test repair records in HEAD (commit b093bbb7 pattern)
    for r_id in (
        "test_run_bundle_schema_check",
        "test_run_empty_inputs",
        "test_run_healing_verification",
    ):
        rb = tenant_repo / ".agy" / "runs" / r_id / "repair_bundle.json"
        rb.parent.mkdir(parents=True, exist_ok=True)
        rb.write_text(json.dumps({"run_id": r_id, "timestamp": "2026-10-17T12:02:03"}), encoding="utf-8")
    fc = tenant_repo / ".agy" / "runs" / "factory_concurrency.jsonl"
    fc.write_text('{"event": "LOCK_CONTENTION_TIMEOUT"}\n', encoding="utf-8")

    subprocess.run(["git", "-C", str(tenant_repo), "add", ".gitignore", "profithelm/"], check=True)
    subprocess.run(["git", "-C", str(tenant_repo), "add", "-f", ".agy/runs/"], check=True)
    subprocess.run(["git", "-C", str(tenant_repo), "commit", "-m", "feat(factory): autonomous pipeline update"], check=True, capture_output=True)

    # Simulate subsequent pytest run modifying the tracked test repair records
    for r_id in (
        "test_run_bundle_schema_check",
        "test_run_empty_inputs",
        "test_run_healing_verification",
    ):
        rb = tenant_repo / ".agy" / "runs" / r_id / "repair_bundle.json"
        rb.write_text(json.dumps({"run_id": r_id, "timestamp": "2026-10-17T21:08:00"}), encoding="utf-8")

    dirty_before = subprocess.run(
        ["git", "-C", str(tenant_repo), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert "M .agy/runs/test_run_bundle_schema_check/repair_bundle.json" in dirty_before

    # 1. Reconcile workspace tracking state (read-only mode restores tracked .agy/runs to clean HEAD)
    rec = reconcile_workspace_tracking_state(
        queues_dir=tmp_path / "queues",
        runs_dir=tenant_repo / ".agy" / "runs",
        ledger_path=tmp_path / "ledger.json",
        tenant_repos=[tenant_repo],
    )
    assert rec.get("pruned_test_runs", 0) >= 3
    clean_after_reconcile = subprocess.run(
        ["git", "-C", str(tenant_repo), "status", "--porcelain", "--", ".agy/runs"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert clean_after_reconcile == ""

    # 2. Sync tenant test isolation guards and stage via GitOpsCoordinator
    sync_fn = getattr(gitops_mod, "sync_tenant_test_isolation_guards", lambda _p: {"updated_files": 0})
    guard_res = sync_fn(tenant_repo)
    assert guard_res["updated_files"] >= 3
    assert "not is_test_run" in repair_py.read_text(encoding="utf-8")
    assert '"git", "add", "-f", "dist/", "machine_endpoints/", ".agy/runs/"' in factory_py.read_text(encoding="utf-8")
    assert '".agy/runs"' in factory_py.read_text(encoding="utf-8")
    assert 'if redirect_mappings and gsc_actions.get("consolidate_pages") and not os.getenv("PYTEST_CURRENT_TEST"):' in factory_py.read_text(encoding="utf-8")
    assert 'if synthesized_spec and not in_test:' in factory_py.read_text(encoding="utf-8")
    assert 'import os\n' in generator_py.read_text(encoding="utf-8")

    coord = GitOpsCoordinator(repo_path=tenant_repo)
    staged = coord.stage_tracked(tenant_repo)
    assert ".agy/runs/test_run_bundle_schema_check/repair_bundle.json" in staged
    subprocess.run(["git", "-C", str(tenant_repo), "commit", "-m", "fix(profithelm-platform): automated release sync"], check=True, capture_output=True)

    tracked_agy = subprocess.run(
        ["git", "-C", str(tenant_repo), "ls-files", ".agy/"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert tracked_agy == ""
    final_status = subprocess.run(
        ["git", "-C", str(tenant_repo), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert final_status == ""


def test_midnight_factory_build_dist_stash_and_redirect_rollup_self_healing(tmp_path, monkeypatch):
    """
    Replays the exact midnight 2026-10-18 failure chain in profithelm-platform:
    1. Stage 3 compiled date rollovers into dist/sitemap.xml and dist/tools/irs-2027-tax-brackets/<state>/index.html.
    2. Stage 5 pytest failed on test_gsc_traffic_insights_parsing_and_status because
       rollup_redirected_gsc_rows overwrote non-redirected row['page'] ('https://profithelm.com/vs/test')
       with 'https://profithelm.com/vs/test/'.
    3. scripts/run_factory.sh ran 'git stash push --include-untracked -- dist/' on a repo where 'dist/'
       is in .gitignore while files inside dist/ are force-tracked, causing git stash to stage all
       modified dist/ files ('M  dist/...'), create a stash entry, and abort with exit code 1 before
       resetting the working tree and index.
    4. reconcile_workspace_tracking_state failed with NameError ('ws' is not defined) when called
       in production mode (tenant_repos=None).
    """
    import subprocess
    from pseofactory.qualification import rollup_redirected_gsc_rows, sync_tenant_redirect_rollup_adapters
    from pseofactory.gitops import reconcile_workspace_tracking_state, sync_tenant_test_isolation_guards

    # 1. Verify rollup_redirected_gsc_rows preserves non-redirected page URL while rolling up redirected URLs
    non_red_res = rollup_redirected_gsc_rows(
        [{"page": "https://profithelm.com/vs/test", "impressions": "12", "position": "3.2"}],
        property_id="profithelm",
    )
    assert len(non_red_res["rows"]) == 1
    assert non_red_res["rows"][0]["page"] == "https://profithelm.com/vs/test"
    assert non_red_res["rows"][0]["canonical_url"] == "https://profithelm.com/vs/test/"
    assert non_red_res["redirected_rows_count"] == 0

    red_res = rollup_redirected_gsc_rows(
        [
            {"page": "https://profithelm.com/tools/2027-california-tax-brackets/", "query": "ca tax", "impressions": 20, "clicks": 2, "position": 7.0},
            {"page": "https://profithelm.com/tools/irs-2027-tax-brackets/california", "query": "ca tax", "impressions": 10, "clicks": 1, "position": 9.0},
        ],
        property_id="profithelm",
    )
    assert len(red_res["rows"]) == 1
    assert red_res["rows"][0]["page"] == "https://profithelm.com/tools/irs-2027-tax-brackets/california/"
    assert red_res["rows"][0]["impressions"] == 30
    assert red_res["rows"][0]["redirected_impressions"] == 20
    assert red_res["rows"][0]["direct_impressions"] == 10

    # 2. Simulate tenant repo with dist/ in .gitignore and force-tracked dist/sitemap.xml & state tax page
    tenant_repo = tmp_path / "profithelm-platform"
    tenant_repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(tenant_repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tenant_repo), "config", "user.email", "test@profithelm.com"], check=True)
    subprocess.run(["git", "-C", str(tenant_repo), "config", "user.name", "Test Runner"], check=True)

    (tenant_repo / ".gitignore").write_text(".agy/\ndist/\n", encoding="utf-8")
    sitemap_f = tenant_repo / "dist" / "sitemap.xml"
    state_f = tenant_repo / "dist" / "tools" / "irs-2027-tax-brackets" / "california" / "index.html"
    sitemap_f.parent.mkdir(parents=True, exist_ok=True)
    state_f.parent.mkdir(parents=True, exist_ok=True)
    sitemap_f.write_text("<urlset><url><lastmod>2026-10-17</lastmod></url></urlset>\n", encoding="utf-8")
    state_f.write_text('<html><script type="application/ld+json">{"dateModified": "2026-10-17"}</script></html>\n', encoding="utf-8")

    scripts_dir = tenant_repo / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    run_factory_sh = scripts_dir / "run_factory.sh"
    run_factory_sh.write_text(
        '#!/bin/bash\n'
        'cleanup() {\n'
        '    if [ -d "$PROJECT_DIR/.git" ] && [ -f "$FAILED_MARKER" ]; then\n'
        '        local dist_dirty\n'
        '        dist_dirty=$(git -C "$PROJECT_DIR" status --porcelain dist/ 2>/dev/null || true)\n'
        '        if [ -n "$dist_dirty" ]; then\n'
        '            git -C "$PROJECT_DIR" stash push --include-untracked -m "agy-aborted-factory-dist-$(date +%s)" -- dist/ 2>/dev/null || true\n'
        '        fi\n'
        '    fi\n'
        '}\n'
        'on_error() {\n'
        '    if [ -d "$PROJECT_DIR/.git" ]; then\n'
        '        local dist_dirty\n'
        '        dist_dirty=$(git -C "$PROJECT_DIR" status --porcelain dist/ 2>/dev/null || true)\n'
        '        if [ -n "$dist_dirty" ]; then\n'
        '            git -C "$PROJECT_DIR" stash push --include-untracked -m "agy-failed-run-factory-dist-$(date +%s)" -- dist/ 2>/dev/null || true\n'
        '        fi\n'
        '    fi\n'
        '}\n'
        '    if [ -d "$WORKTREE_SANDBOX" ]; then\n'
        '        mkdir -p "$WORKTREE_SANDBOX/.agy"\n'
        '        [ -f "$PROJECT_DIR/.agy/engine_hash.json" ] && cp -f "$PROJECT_DIR/.agy/engine_hash.json" "$WORKTREE_SANDBOX/.agy/engine_hash.json"\n'
        '        cd "$WORKTREE_SANDBOX"\n'
        '    fi\n',
        encoding="utf-8",
    )

    ph_dir = tenant_repo / "profithelm"
    ph_dir.mkdir(parents=True, exist_ok=True)
    factory_py = ph_dir / "factory.py"
    factory_py.write_text(
        'import os, sys, subprocess\n'
        'from pathlib import Path\n'
        'BASE_DIR = Path(__file__).resolve().parent.parent\n'
        'if __name__ == "__main__":\n'
        '    verdict = "FAILED_AT_TESTS"\n'
        '    is_live = True\n'
        '    clean_verdicts = {"FACTORY_PIPELINE_COMPLETE_100_PERCENT_GREEN"}\n'
        '    if verdict not in clean_verdicts:\n'
        '        sys.exit(1)\n'
        '    sys.exit(0)\n',
        encoding="utf-8",
    )

    prexvo_dir = tenant_repo / "prexvo"
    prexvo_dir.mkdir(parents=True, exist_ok=True)
    prexvo_obs = prexvo_dir / "observer.py"
    prexvo_obs.write_text(
        'def fetch_gsc_traffic_insights():\n'
        '    insights = {"status": "UNAVAILABLE", "top_pages": []}\n'
        '    has_valid_data = True\n'
        '    if has_valid_data:\n'
        '        insights["status"] = "CONNECTED"\n'
        '\n'
        '    return insights\n',
        encoding="utf-8",
    )

    subprocess.run(["git", "-C", str(tenant_repo), "add", ".gitignore", "scripts/", "profithelm/", "prexvo/"], check=True)
    subprocess.run(["git", "-C", str(tenant_repo), "add", "-f", "dist/"], check=True)
    subprocess.run(["git", "-C", str(tenant_repo), "commit", "-m", "Initial tracked dist"], check=True, capture_output=True)

    # Simulate midnight build modifying dist/ followed by git stash push --include-untracked -- dist/
    sitemap_f.write_text("<urlset><url><lastmod>2026-10-18</lastmod></url></urlset>\n", encoding="utf-8")
    state_f.write_text('<html><script type="application/ld+json">{"dateModified": "2026-10-18"}</script></html>\n', encoding="utf-8")
    stash_Attempt = subprocess.run(
        ["git", "-C", str(tenant_repo), "stash", "push", "--include-untracked", "-m", "agy-failed-run-factory-dist-1792307933", "--", "dist/"],
        capture_output=True,
        text=True,
        check=False,
    )
    # Because dist/ is in .gitignore, git stash push --include-untracked -- dist/ exits 1 after staging dist/ into index!
    assert stash_Attempt.returncode != 0
    staged_status = subprocess.run(
        ["git", "-C", str(tenant_repo), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "M  dist/sitemap.xml" in staged_status
    assert "M  dist/tools/irs-2027-tax-brackets/california/index.html" in staged_status

    # 3. Verify reconcile_workspace_tracking_state heals staged dist/ and drops the aborted stash without NameError
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    rec = reconcile_workspace_tracking_state(
        runs_dir=tmp_path / "runs",
        queues_dir=tmp_path / "queues",
        ledger_path=tmp_path / "ledger.json",
        tenant_repos=[tenant_repo],
    )
    assert rec["status"] == "PASS"
    assert rec["healed_tenant_trees"] >= 1
    assert rec["dropped_stashes"] >= 1
    assert subprocess.run(["git", "-C", str(tenant_repo), "status", "--porcelain"], capture_output=True, text=True, check=True).stdout.strip() == ""
    assert subprocess.run(["git", "-C", str(tenant_repo), "stash", "list"], capture_output=True, text=True, check=True).stdout.strip() == ""

    # 4. Verify sync_tenant_test_isolation_guards hardens scripts/run_factory.sh, profithelm/factory.py, workflows, jev.py, and cli.py
    wf_dir = tenant_repo / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    ci_yml = wf_dir / "ci.yml"
    dg_yml = wf_dir / "deploy-google.yml"
    ci_yml.write_text("name: legacy\n", encoding="utf-8")
    dg_yml.write_text("name: legacy-dg\n", encoding="utf-8")
    jev_py = ph_dir / "jev.py"
    jev_py.write_text(
        'def _resolve_api_key() -> str:\n'
        '    """Resolves TypeSafe AI API key from environment, local .env, or workspace satellite .env."""\n'
        '    key = os.environ.get("TYPESAFE_API_KEY", "").strip()\n'
        '    return key\n'
        '                    verdict = "VERIFIED" if (safe_val >= 0.60 and fit_score >= 1.0) else "REJECTED"\n',
        encoding="utf-8",
    )
    cli_py = ph_dir / "cli.py"
    cli_py.write_text(
        '    try:\n'
        '        from profithelm.gsc_adapter import audit_search_console_performance\n'
        '        rep["sc_audit"] = audit_search_console_performance()\n'
        '    except Exception as ex:\n'
        '        rep["sc_audit"] = {"status": "SKIPPED", "reason": str(ex)}\n',
        encoding="utf-8",
    )
    guard_res = sync_tenant_test_isolation_guards(tenant_repo)
    assert guard_res["updated_files"] >= 6
    rf_after = run_factory_sh.read_text(encoding="utf-8")
    assert "--include-untracked" not in rf_after
    assert 'git -C "$PROJECT_DIR" reset -q HEAD -- dist/' in rf_after
    assert 'git -C "$PROJECT_DIR" checkout -q HEAD -- dist/' in rf_after
    assert 'export PROFITHELM_DIST_DIR="$WORKTREE_SANDBOX/dist"' in rf_after
    assert '"reset", "-q", "HEAD", "--", "dist"' in factory_py.read_text(encoding="utf-8")
    assert 'PROFITHELM_OFFLINE_JEV="1"' in ci_yml.read_text(encoding="utf-8")
    assert "pip install -e ." not in ci_yml.read_text(encoding="utf-8")
    assert "if: github.event_name == 'workflow_dispatch'\n" in dg_yml.read_text(encoding="utf-8")
    assert "PROFITHELM_OFFLINE_JEV" in jev_py.read_text(encoding="utf-8")
    assert "safe_val = max(safe_val, 0.85)" in jev_py.read_text(encoding="utf-8")
    assert "Offline CI or test environment" in cli_py.read_text(encoding="utf-8")

    # 5. Verify sync_tenant_redirect_rollup_adapters wires prexvo/observer.py and .agy/overlays fallback in gsc_adapter.py
    ph_gsc = ph_dir / "gsc_adapter.py"
    ph_gsc.write_text(
        'def load_page_overlay(slug, base_dir=None):\n'
        '    path = get_overlay_path(slug, base_dir=base_dir)\n'
        '    if not path.is_file():\n'
        '        return None\n'
        '    return {}\n',
        encoding="utf-8",
    )
    updated_ph = sync_tenant_redirect_rollup_adapters(tenant_repo, property_id="profithelm")
    assert updated_ph >= 1
    assert 'BASE_DIR / ".agy" / "overlays"' in ph_gsc.read_text(encoding="utf-8")

    updated_px = sync_tenant_redirect_rollup_adapters(tenant_repo, property_id="prexvo")
    assert updated_px >= 1
    assert "rollup_redirected_gsc_rows" in prexvo_obs.read_text(encoding="utf-8")


def test_unattended_timer_concurrency_and_distribution_verification(tmp_path):
    """
    Verifies unattended timer concurrency and downstream distribution gates:
    1. Treasury Yield Calculator checklist copy contains zero spaced hyphens (' - ')
    2. Concurrent TrendHistoryDB.acquire_lock(timeout=...) serializes overlapping threads without BlockingIOError
    3. MaintenanceLifecycle.run verifies distribution BEFORE writing substrate_lock.json or invoking GitOps shipper
    4. ShipperQueue.reconcile_stale_events reconciles superseded CI_FAILURE WAL records
    5. reconcile_workspace_tracking_state preserves locked canonical overlays in .agy/overlays/ and removes FAILED.* markers
    Zero em-dashes. Zero en-dashes.
    """
    import re
    import threading
    import time
    from unittest.mock import patch
    from pseofactory.competitor import render_competitor_winning_pattern_blocks
    from pseofactory.gitops import ShipperQueue, reconcile_workspace_tracking_state
    from pseofactory.indexing.preflight import PreflightReport
    from pseofactory.maintenance import ConfigurablePropertyAdapter, MaintenanceLifecycle
    from pseofactory.trends.db import TrendHistoryDB

    # 1. Verify treasury-yield-calculator blocks contain zero spaced hyphens in body copy
    blocks = render_competitor_winning_pattern_blocks(
        slug="treasury-yield-calculator",
        title="Treasury Bill Yield vs HYSA Tax-Equivalent Yield Calculator",
        property_id="profithelm",
        canonical_base="https://profithelm.com",
        statutory_authority="31 U.S.C. 3124",
        economic_dataset="U.S. Treasury Daily Yield Curve",
    )
    combined_html = "\n".join(str(v) for v in blocks.values())
    body_text = re.sub(r"<[^>]+>", " ", combined_html)
    assert re.search(r"\s-\s", body_text) is None

    # 2. Verify TrendHistoryDB.acquire_lock(non_blocking=True, timeout=...) waits cleanly when another thread releases lock
    db_file = tmp_path / "trends.db"
    db1 = TrendHistoryDB(db_file)
    db2 = TrendHistoryDB(db_file)
    events = []

    def holder():
        with db1.acquire_lock(non_blocking=True, timeout=0.0):
            events.append("holder_acquired")
            time.sleep(0.25)
            events.append("holder_releasing")

    t = threading.Thread(target=holder)
    t.start()
    while "holder_acquired" not in events:
        time.sleep(0.02)
    with db2.acquire_lock(non_blocking=True, timeout=2.0):
        events.append("waiter_acquired")
    t.join()
    assert events == ["holder_acquired", "holder_releasing", "waiter_acquired"]

    # 3. Verify MaintenanceLifecycle.run aborts on failed distribution BEFORE writing substrate_lock.json or calling GitOps
    tenant_dir = tmp_path / "profithelm-platform"
    (tenant_dir / ".git" / "info").mkdir(parents=True, exist_ok=True)
    dist_dir = tenant_dir / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    agy_dir = tenant_dir / ".agy"
    agy_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.html").write_text(
        "<!DOCTYPE html><html><head><title>ProfitHelm</title>"
        '<link rel="canonical" href="https://profithelm.com/"></head>'
        "<body><main><h1>ProfitHelm</h1></main></body></html>",
        encoding="utf-8",
    )
    adapter = ConfigurablePropertyAdapter(
        property_id="profithelm",
        brand_name="ProfitHelm",
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        dist_dir=dist_dir,
        repo_path=tenant_dir,
    )
    call_order = []

    def fake_airlock(*args, **kwargs):
        call_order.append("airlock")
        return PreflightReport(
            property_id="profithelm",
            domain="profithelm.com",
            total_inspected=1,
            passed_count=1,
            blocked_count=0,
            tier1_hubs_eligible=1,
            tier2_leaves_queued=0,
            breakdown={},
            push_eligible_urls=["https://profithelm.com/"],
            sitemap_eligible_urls=["https://profithelm.com/"],
            blocked_urls=[],
            is_gate_passed=True,
        )

    def fake_dist_fail(*args, **kwargs):
        call_order.append("distribution")
        return {"status": "FAILED", "error": "Simulated interrupted distribution run"}

    def fake_shipper(*args, **kwargs):
        call_order.append("gitops")
        raise AssertionError("GitOps shipper must not run when distribution fails")

    lifecycle = MaintenanceLifecycle()
    with patch("pseofactory.indexing.preflight.IndexingPreflightEngine.inspect_dist", side_effect=fake_airlock), \
         patch("pseofactory.distributor.dispatch_to_distribution_lead", side_effect=fake_dist_fail), \
         patch("pseofactory.gitops.GitOpsCoordinator.dispatch_to_shipper", side_effect=fake_shipper):
        res = lifecycle.run(
            adapter,
            force=True,
            enable_gitops=True,
            enable_distribution=True,
            state_file=agy_dir / "engine_hash.json",
            ledger_file=agy_dir / "asset_ledger.json",
        )
    assert res.status == "FAILED"
    assert res.distribution_status == "FAILED"
    assert "gitops" not in call_order
    assert not (tenant_dir / "substrate_lock.json").exists()
    assert not (agy_dir / "engine_hash.json").exists()

    # 4. Verify ShipperQueue.reconcile_stale_events reconciles superseded CI_FAILURE records
    queues_dir = tmp_path / "queues"
    sq = ShipperQueue(property_id="profithelm", queues_dir=queues_dir)
    e1 = sq.enqueue({"run_id": "run-ci-fail", "token": "tok_fail"})
    sq.complete_event(e1["event_id"], status="CI_FAILURE")
    e2 = sq.enqueue({"run_id": "run-ok", "token": "tok_ok"})
    sq.complete_event(e2["event_id"], status="COMPLETED")
    reconciled_count = sq.reconcile_stale_events()
    assert reconciled_count == 1
    q_lines = [json.loads(line) for line in sq.queue_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert q_lines[0]["status"] == "RECONCILED_SUPERSEDED"
    assert q_lines[0]["previous_status"] == "CI_FAILURE"

    # 5. Verify reconcile_workspace_tracking_state preserves locked canonical overlays in .agy/overlays/ and removes FAILED.*
    (agy_dir / "overlays").mkdir(parents=True, exist_ok=True)
    (tenant_dir / "content" / "overlays").mkdir(parents=True, exist_ok=True)
    canonical_ov = {"slug": "irs-2027-tax-brackets", "locked_until": "2026-11-15T00:00:00+00:00", "canonical": True}
    duplicate_ov = {"slug": "irs-2027-tax-brackets", "locked_until": "2026-11-16T00:00:00+00:00", "canonical": False}
    (agy_dir / "overlays" / "irs-2027-tax-brackets.json").write_text(json.dumps(canonical_ov), encoding="utf-8")
    (tenant_dir / "content" / "overlays" / "irs-2027-tax-brackets.json").write_text(json.dumps(duplicate_ov), encoding="utf-8")
    (agy_dir / "FAILED.profithelm_factory").write_text("1", encoding="utf-8")

    rec_ws = reconcile_workspace_tracking_state(
        runs_dir=tmp_path / "runs",
        queues_dir=queues_dir,
        ledger_path=tmp_path / "ledger.json",
        tenant_repos=[tenant_dir],
    )
    assert rec_ws["status"] == "PASS"
    preserved = json.loads((agy_dir / "overlays" / "irs-2027-tax-brackets.json").read_text(encoding="utf-8"))
    assert preserved["canonical"] is True
    assert not (tenant_dir / "content" / "overlays" / "irs-2027-tax-brackets.json").exists()
    assert not (agy_dir / "FAILED.profithelm_factory").exists()

    # 6. Verify sync_tenant_redirect_rollup_adapters synchronizes check_queue and in_test guards
    from pseofactory.qualification import sync_tenant_redirect_rollup_adapters
    from pseofactory.trends.treg_checker import TregChecker

    ph_fac = tenant_dir / "profithelm" / "factory.py"
    ph_fac.parent.mkdir(parents=True, exist_ok=True)
    ph_fac.write_text(
        '    if live_probe is None:\n'
        '        live_probe = live_deploy or (os.getenv("PROFITHELM_LIVE_PROBE") == "1")\n'
        '        # Pre-Run Empty-Queue Gate\n'
        '        if top_opp is None and top_trend is None and not target_query:\n'
        '            from profithelm.staleness import evaluate_system_staleness\n'
        '            staleness = evaluate_system_staleness()\n'
        '            requires_recompile = staleness.get("requires_recompile", False)\n'
        '            if not requires_recompile and not force:\n'
        '                pass\n',
        encoding="utf-8",
    )
    assert sync_tenant_redirect_rollup_adapters(tenant_dir, property_id="profithelm") >= 1
    ph_synced = ph_fac.read_text(encoding="utf-8")
    assert "if check_queue:\n        abort_on_zero_asset = True" in ph_synced
    assert "if (not requires_recompile or check_queue) and not force:" in ph_synced

    px_dir = tmp_path / "prexvo"
    px_fac = px_dir / "prexvo" / "factory.py"
    px_fac.parent.mkdir(parents=True, exist_ok=True)
    px_fac.write_text(
        '    if live_probe is None:\n'
        '        live_probe = live_deploy or (os.getenv("PREXVO_LIVE_PROBE") == "1")\n'
        '        if top_opp is None and not target_query:\n'
        '            from prexvo.staleness import evaluate_system_staleness\n'
        '            staleness = evaluate_system_staleness()\n'
        '            requires_recompile = staleness.get("requires_recompile", False)\n'
        '            if not requires_recompile and not force:\n'
        '                pass\n',
        encoding="utf-8",
    )
    assert sync_tenant_redirect_rollup_adapters(px_dir, property_id="prexvo") >= 1
    px_synced = px_fac.read_text(encoding="utf-8")
    assert 'in_test = bool(os.getenv("PYTEST_CURRENT_TEST") or os.getenv("PREXVO_IN_TEST") == "1")' in px_synced
    assert "if (not requires_recompile or check_queue) and not force:" in px_synced

    checker = TregChecker(check_ai_citations=True)
    assert hasattr(checker, "_max_live_ai_calls")
    assert checker._max_live_ai_calls >= 1


def test_spoke_quick_answer_word_bounds_commercial_context_and_equipment_healing(tmp_path):
    """
    Verifies that:
    1. Multi-word state Section 1031 spokes (e.g. New York, District of Columbia) and IRS 2027 tax-bracket
       spokes retain state-specific dollar calculations, commercial property exchange context, and strict
       40-60 word bounds in both .quick-answer-body and <aside class="quick-answer"> even after overlay injection.
    2. Section 179 vehicle spokes (e.g. GMC Yukon XL) distinguish sec179-cost commercial acquisition cost
       from sec179-res-writeoff and remain within 40-60 words.
    3. Equipment vertical hubs without '179' in the slug (e.g. equipment-lease-tax-deduction) preserve
       Section 179 statutory authority across _resolve_manifest_for_page and _overlay_spec_needs_heal.
    Zero em-dashes. Zero en-dashes.
    """
    import re
    from pseofactory.gsc_remediation import compile_remediation_overlay_spec, inject_overlay_into_html
    from pseofactory.maintenance import RetroReflectionEngine

    equip_html = (
        '<!DOCTYPE html><html lang="en" data-theme="porcelain"><head>'
        '<link rel="canonical" href="https://profithelm.com/tools/equipment-lease-tax-deduction/"></head>'
        '<body><main><h1>Equipment Lease Tax Deduction</h1>'
        '<script type="application/json" id="calculation-manifest" class="calculation-manifest">'
        '{"model_name": "Equipment Lease Tax Deduction Model", "formula": "gross_amount * (1.0 - effective_rate)", '
        '"inputs": {"gross_amount": 100000.0, "effective_rate": 0.24}, "published_output": 76000.0, '
        '"statutory_authority": "26 U.S.C. Section 179; IRC Section 168(k); IRS Form 4562", '
        '"economic_dataset": "BLS Producer Price Index (PPI) and Federal Reserve Industrial Production Index (G.17)"}'
        '</script></main></body></html>'
    )
    equip_manifest = RetroReflectionEngine._resolve_manifest_for_page(
        equip_html,
        property_id="profithelm",
        slug="equipment-lease-tax-deduction",
    )
    assert "Section 179" in equip_manifest["statutory_authority"]

    nav_polluted_html = (
        '<!DOCTYPE html><html lang="en" data-theme="porcelain"><head>'
        '<link rel="canonical" href="https://profithelm.com/tools/section-179-calculator/lincoln-navigator-l/"></head>'
        '<body><main><h1>Lincoln Navigator L Heavy SUV Section 179</h1>'
        '<aside data-mechanic="instant_edge_case_trap_immediacy"><p>Immediate Quadratic Fee Drag and Section 1256 Tax Bifurcation Trap Alert</p></aside>'
        '<table class="statutory-pitfalls-table" data-statutory-source="CFTC 17 CFR Part 40; IRC Section 1256; IRC Section 165(d)" data-economic-source="FRED 3-Month Treasury Bill (DTB3)"></table>'
        '</main></body></html>'
    )
    nav_manifest = RetroReflectionEngine._resolve_manifest_for_page(
        nav_polluted_html,
        property_id="profithelm",
        slug="section-179-calculator/lincoln-navigator-l",
    )
    assert "Section 179" in nav_manifest["statutory_authority"]
    assert "CFTC" not in nav_manifest["statutory_authority"]

    for st_slug, def_v, fed_v, st_v in (
        ("new-york", "$661,950", "$460,300", "$201,650"),
        ("district-of-columbia", "$460,300", "$460,300", "$0"),
    ):
        spoke_1031_html = (
            '<!DOCTYPE html><html lang="en" data-theme="porcelain"><head>'
            f'<title>{st_slug.title()} Section 1031 Real Estate Tax Deferral Rules &amp; Calculator (2026)</title>'
            f'<meta name="description" content="Calculate {st_slug} Section 1031 tax deferral: {def_v} total tax deferred ({fed_v} federal + {st_v} state) under IRC Section 1031.">'
            f'<meta property="og:description" content="Calculate {st_slug} Section 1031 tax deferral: {def_v} total tax deferred ({fed_v} federal + {st_v} state) under IRC Section 1031.">'
            f'<link rel="canonical" href="https://profithelm.com/tools/section-1031-calculator/{st_slug}/"></head>'
            '<body><main><h1>Section 1031 Calculator</h1>'
            '<aside class="quick-answer"><div class="quick-answer-body"><p>Short initial answer.</p></div></aside>'
            '<div id="calculator-workspace-anchor">'
            '<input type="number" id="sec1031-sale-price" value="2500000">'
            f'<span id="sec1031-res-deferred">{def_v}</span>'
            f'<span id="sec1031-res-fed-tax">{fed_v}</span>'
            f'<span id="sec1031-res-state-tax">{st_v}</span>'
            '</div></main></body></html>'
        )
        ov_1031 = compile_remediation_overlay_spec(
            {
                "slug": f"section-1031-calculator/{st_slug}",
                "target_url": f"https://profithelm.com/tools/section-1031-calculator/{st_slug}/",
                "query": f"{st_slug.replace('-', ' ')} section 1031 exchange",
                "position": 9.0,
                "impressions": 60,
            },
            tenant_id="profithelm",
        )
        assert "commercial real estate" in ov_1031["quick_answer"].lower()
        pre_retro_html, _ = RetroReflectionEngine.retrofit_html(
            spoke_1031_html,
            property_id="profithelm",
            slug=f"section-1031-calculator/{st_slug}",
        )
        ov_injected = inject_overlay_into_html(pre_retro_html, ov_1031)
        final_1031, _ = RetroReflectionEngine.retrofit_html(
            ov_injected,
            property_id="profithelm",
            slug=f"section-1031-calculator/{st_slug}",
        )
        qa_m = re.search(r'<aside[^>]*class=["\'][^"\']*quick-answer[^"\']*["\'][^>]*>([\s\S]*?)</aside>', final_1031, re.I)
        qb_m = re.search(r'<div[^>]*class=["\'][^"\']*quick-answer-body[^"\']*["\'][^>]*>([\s\S]*?)</div>', qa_m.group(1), re.I)
        aside_words = len(re.sub(r"<[^>]+>", " ", qa_m.group(1)).split())
        body_words = len(re.sub(r"<[^>]+>", " ", qb_m.group(1)).split())
        assert 40 <= body_words <= 60
        assert 40 <= aside_words <= 60
        assert "commercial property exchange" in qb_m.group(1)
        assert def_v in qb_m.group(1) and fed_v in qb_m.group(1) and st_v in qb_m.group(1)
        assert RetroReflectionEngine.audit_html_mechanics(final_1031) == []

    veh_html = (
        '<!DOCTYPE html><html lang="en" data-theme="porcelain"><head>'
        '<title>GMC Yukon XL 4WD Section 179 Tax Deduction Calculator (7,700 lbs GVWR)</title>'
        '<meta name="description" content="Calculate GMC Yukon XL Section 179 write-off: $37,180 deduction and $13,013 tax savings (7,700 lbs GVWR) under IRC Section 179.">'
        '<meta property="og:description" content="Calculate GMC Yukon XL Section 179 write-off: $37,180 deduction and $13,013 tax savings (7,700 lbs GVWR) under IRC Section 179.">'
        '<link rel="canonical" href="https://profithelm.com/tools/section-179-calculator/gmc-yukon-xl/"></head>'
        '<body><main><h1>GMC Yukon XL (7,700 lbs GVWR)</h1>'
        '<aside class="quick-answer"><div class="quick-answer-body"><p>The GMC Yukon XL qualifies for passenger vehicle business depreciation write-offs with $13,013 tax savings.</p></div></aside>'
        '<div id="calculator-workspace-anchor">'
        '<input type="number" id="sec179-cost" value="63900">'
        '<span id="sec179-res-writeoff">$37,180</span>'
        '<span id="sec179-res-savings">$13,013</span>'
        '<span id="sec179-res-netcost">$50,887</span>'
        '</div></main></body></html>'
    )
    final_veh, _ = RetroReflectionEngine.retrofit_html(
        veh_html,
        property_id="profithelm",
        slug="section-179-calculator/gmc-yukon-xl",
    )
    v_qa_m = re.search(r'<aside[^>]*class=["\'][^"\']*quick-answer[^"\']*["\'][^>]*>([\s\S]*?)</aside>', final_veh, re.I)
    v_qb_m = re.search(r'<div[^>]*class=["\'][^"\']*quick-answer-body[^"\']*["\'][^>]*>([\s\S]*?)</div>', v_qa_m.group(1), re.I)
    assert 40 <= len(re.sub(r"<[^>]+>", " ", v_qb_m.group(1)).split()) <= 60
    assert 40 <= len(re.sub(r"<[^>]+>", " ", v_qa_m.group(1)).split()) <= 60
    assert "$63,900 commercial acquisition cost" in v_qb_m.group(1)
    assert "$37,180 in first-year" in v_qb_m.group(1)
    assert RetroReflectionEngine.audit_html_mechanics(final_veh) == []


def test_syndication_workflow_truth_store_audit_and_historical_replay(tmp_path):
    """
    Verifies:
    1. Single-pass raw manifest and audit trail inspection distinguishes observed payload quality
       from unverified assumptions and treats untested/missing channels as UNKNOWN.
    2. Upgraded publishing workflow across canonical tools, YouTube scripts, LinkedIn, Facebook,
       Ghost, and exact-match GitHub Gists (deliberately omitting Reddit) delivers calculation-backed
       proof locked to statutory facts for both ProfitHelm and Prexvo.
    3. Outside truth-store audit passes 100% on upgraded assets and automatically fails thin stubs,
       Reddit-containing packs, missing/unknown channels, unparameterized URLs, formula drift, and
       stale statutory numbers, including replay against historical repo runs.
    """
    import copy
    from pathlib import Path
    from pseofactory.audit import (
        audit_distribution_draft_payload,
        audit_historical_distribution_runs,
        audit_syndication_asset_against_truth_store,
        inspect_raw_syndication_manifests_and_trails,
    )
    from pseofactory.distributor import (
        dispatch_to_distribution_lead,
        export_all_syndication_files,
        generate_all_distribution_assets,
    )

    # 1. Single-pass inspection treats untested channels on legacy manifests as UNKNOWN
    legacy_synd_dir = tmp_path / "legacy_syndication" / "prexvo" / "rap-vs-ibr-calculator"
    legacy_synd_dir.mkdir(parents=True)
    (legacy_synd_dir / "syndication_pack.json").write_text(
        json.dumps(
            {
                "title": "RAP vs IBR Calculator",
                "url": "https://prexvo.com/tools/rap-vs-ibr-calculator/",
                "dual_dataset_citations": True,
                "linkedin": {"content": "Compare RAP vs IBR at https://prexvo.com/tools/rap-vs-ibr-calculator/"},
                "facebook": {"content": "Compare RAP vs IBR"},
                "youtube": {"description": "Compare RAP vs IBR"},
                "substack_teardown": {"article_markdown": "Short 50 char stub."},
                "reddit": {"content": "Reddit post"},
            }
        ),
        encoding="utf-8",
    )
    diag = inspect_raw_syndication_manifests_and_trails(
        syndication_root=tmp_path / "legacy_syndication",
        runs_dir="/home/ubuntuadmin/projects/.agy/runs",
    )
    assert diag["manifests_inspected"] == 1
    assert diag["unknown_channels"].get("ghost") == "UNKNOWN"
    assert diag["unknown_channels"].get("github_gist") == "UNKNOWN"
    assert diag["observed_facts"]["boolean_citation_packs"] == 1
    assert diag["observed_facts"]["thin_substack_packs"] == 1
    assert len(diag["unverified_assumptions_falsified"]) >= 4

    # 2. Upgraded workflow across all ProfitHelm and Prexvo tools omits Reddit and passes truth-store audit
    for prop in ("profithelm", "prexvo"):
        assets = generate_all_distribution_assets(property_id=prop)
        assert len(assets) >= (21 if prop == "profithelm" else 13)
        for slug, pack in assets.items():
            assert "reddit" not in pack
            assert "reddit_teardown" not in pack
            for req_ch in ("youtube", "linkedin", "facebook", "ghost", "github_gist"):
                assert req_ch in pack and pack[req_ch]
            assert "?" in pack["url"] and "=" in pack["url"]
            audit_res = audit_syndication_asset_against_truth_store(pack, property_id=prop)
            assert audit_res["status"] == "PASS", f"{prop}/{slug} failed truth audit: {audit_res['failures']}"
            assert audit_res["unknown_channels"] == []

        # Export to disk and verify reddit.md is purged while ghost & github_gist are written
        out_dir = tmp_path / "exported_syndication" / prop
        stale_reddit = out_dir / next(iter(assets.keys())) / "reddit.md"
        stale_reddit.parent.mkdir(parents=True, exist_ok=True)
        stale_reddit.write_text("# Stale Reddit", encoding="utf-8")

        export_all_syndication_files(output_dir=out_dir, property_id=prop)
        first_slug = next(iter(assets.keys()))
        assert not (out_dir / first_slug / "reddit.md").exists()
        assert (out_dir / first_slug / "ghost.json").is_file()
        assert (out_dir / first_slug / "ghost_article.md").is_file()
        assert (out_dir / first_slug / "github_gist.json").is_file()
        assert (out_dir / first_slug / "github_gist.md").is_file()

        # Verify dispatch_to_distribution_lead omits Reddit and passes draft audit
        dist_res = dispatch_to_distribution_lead(
            run_id=f"test-truth-upgrade-{prop}",
            property_id=prop,
            dry_run=True,
            dist_dir=tmp_path / "dist",
            tools=[{"slug": first_slug, "title": assets[first_slug]["title"]}],
        )
        assert "reddit" not in dist_res["channels"]
        assert "ghost" in dist_res["channels"]
        assert "github_gist" in dist_res["channels"]
        assert dist_res["truth_store_audit"]["status"] == "PASS"

    # 3. Demonstrate that thin, Reddit-containing, unparameterized, formula-drifted, or statutory-mismatched drafts fail automatically
    valid_pack = copy.deepcopy(generate_all_distribution_assets(property_id="profithelm")["section-179-calculator"])

    # 3a. Reddit present -> PROHIBITED_CHANNEL_REDDIT
    reddit_pack = copy.deepcopy(valid_pack)
    reddit_pack["reddit"] = {"target_subreddit": "r/tax", "content": "Legacy Reddit post"}
    res_reddit = audit_syndication_asset_against_truth_store(reddit_pack, property_id="profithelm")
    assert res_reddit["status"] == "FAIL"
    assert "PROHIBITED_CHANNEL_REDDIT" in res_reddit["violations"]

    # 3b. Missing Ghost / GitHub Gist -> MISSING_OR_UNKNOWN_CHANNEL + marked UNKNOWN
    missing_ch_pack = copy.deepcopy(valid_pack)
    missing_ch_pack.pop("ghost", None)
    missing_ch_pack.pop("github_gist", None)
    res_missing = audit_syndication_asset_against_truth_store(missing_ch_pack, property_id="profithelm")
    assert res_missing["status"] == "FAIL"
    assert "ghost" in res_missing["unknown_channels"]
    assert "github_gist" in res_missing["unknown_channels"]

    # 3c. Calculation parity drift -> CALCULATION_PARITY_MISMATCH
    bad_math_pack = copy.deepcopy(valid_pack)
    bad_math_pack["calculation_proof"]["published_output"] = 999999.0
    res_math = audit_syndication_asset_against_truth_store(bad_math_pack, property_id="profithelm")
    assert res_math["status"] == "FAIL"
    assert any("CALCULATION_PARITY_MISMATCH" in v for v in res_math["violations"])

    # 3d. Stale statutory figure ($1,220,000 Section 179 cap / $31,300 SUV cap / 60% bonus depreciation) -> STATUTORY_TRUTH_MISMATCH
    stale_stat_pack = copy.deepcopy(valid_pack)
    stale_stat_pack["linkedin"]["content"] += "\nUnder 2026 rules, the Section 179 cap is $1,220,000 with a $31,300 SUV limit and 60% bonus depreciation."
    res_stat = audit_syndication_asset_against_truth_store(stale_stat_pack, property_id="profithelm")
    assert res_stat["status"] == "FAIL"
    assert any("STATUTORY_TRUTH_MISMATCH" in v for v in res_stat["violations"])

    # 3e. Unparameterized URL & generic filler -> UNPARAMETERIZED_CANONICAL_URL + THIN_PAYLOAD_STUB
    thin_pack = copy.deepcopy(valid_pack)
    thin_pack["facebook"]["content"] = (
        "Users analyze complex tax liabilities across multiple scenarios resulting in a 15% to 35% variance: "
        "https://profithelm.com/tools/section-179-calculator/"
    )
    res_thin = audit_syndication_asset_against_truth_store(thin_pack, property_id="profithelm")
    assert res_thin["status"] == "FAIL"
    assert any("UNPARAMETERIZED_CANONICAL_URL:facebook" in v for v in res_thin["violations"])
    assert any("THIN_PAYLOAD_STUB" in v for v in res_thin["violations"])

    # 4. Replay against earlier historical repo runs in /home/ubuntuadmin/projects/.agy/runs
    runs_dir = Path("/home/ubuntuadmin/projects/.agy/runs")
    if runs_dir.is_dir():
        hist_report = audit_historical_distribution_runs(runs_dir=runs_dir, limit=40)
        assert hist_report["runs_audited"] > 0
        assert hist_report["runs_failed"] == hist_report["runs_audited"]
        assert hist_report["runs_passed"] == 0
        reasons = hist_report["failure_reason_counts"]
        assert (
            reasons.get("EMPTY_DISTRIBUTION_RUN_ZERO_ASSETS", 0) > 0
            or reasons.get("PROHIBITED_CHANNEL_REDDIT", 0) > 0
            or reasons.get("MISSING_CALCULATION_PROOF", 0) > 0
        )


def test_post_overlay_retrofit_ordering_and_substrate_lock_drift_gates(tmp_path):
    """
    Verifies orchestration ordering and drift gate invariants:
    1. RefactorCascadeEngine runs RetroReflectionEngine.retrofit_estate AFTER _reapply_active_overlay
       so spoke overlays never leave un-retrofitted generic meta descriptions or quick-answer blocks.
    2. AssetIntegrityEvaluator detects _needs_page_structure_geo_normalization violations on tool pages
       and detects stale substrate_lock.json even when .agy/engine_hash.json matches compute_engine_hash().
    Zero em-dashes. Zero en-dashes.
    """
    import json
    import shutil
    from pathlib import Path
    from pseofactory.drift import compute_engine_hash, record_engine_hash
    from pseofactory.maintenance import (
        AssetDriftRecord,
        AssetIntegrityEvaluator,
        ConfigurablePropertyAdapter,
        DriftReason,
        RefactorCascadeEngine,
        RetroReflectionEngine,
    )

    import shutil

    repo_dir = tmp_path / "profithelm-platform"
    dist_dir = repo_dir / "dist"
    spoke_dir = dist_dir / "tools" / "irs-2027-tax-brackets" / "alabama"
    spoke_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / ".git").mkdir(parents=True, exist_ok=True)

    # Copy a real compiled spoke page and its active overlay from profithelm-platform
    src_spoke = Path("/home/ubuntuadmin/projects/profithelm-platform/dist/tools/irs-2027-tax-brackets/alabama/index.html")
    initial_spoke_html = src_spoke.read_text(encoding="utf-8")
    spoke_file = spoke_dir / "index.html"
    spoke_file.write_text(initial_spoke_html, encoding="utf-8")

    ov_dir = repo_dir / ".agy" / "overlays"
    ov_dir.mkdir(parents=True, exist_ok=True)
    src_ov = Path("/home/ubuntuadmin/projects/profithelm-platform/.agy/overlays/irs-2027-tax-brackets-alabama.json")
    if src_ov.is_file():
        shutil.copy2(src_ov, ov_dir / "irs-2027-tax-brackets-alabama.json")

    def _build_all() -> bool:
        spoke_file.write_text(initial_spoke_html, encoding="utf-8")
        return True

    adapter = ConfigurablePropertyAdapter(
        property_id="profithelm",
        domain="profithelm.com",
        brand_name="ProfitHelm",
        canonical_base="https://profithelm.com",
        dist_dir=dist_dir,
        build_all_fn=_build_all,
        repo_path=repo_dir,
    )

    evaluator = AssetIntegrityEvaluator()
    cascade = RefactorCascadeEngine(evaluator=evaluator)
    rec = AssetDriftRecord(
        asset_path=str(spoke_file),
        slug="alabama",
        reasons=[DriftReason.ENGINE_HASH_DRIFT],
        details=["Engine hash drift"],
    )
    res = cascade.refactor_all([rec], adapter, force=True)
    assert res["failed"] == 0
    assert res["refactored"] == 1

    # Verify RetroReflectionEngine.audit_estate reports 0 stale pages after RefactorCascadeEngine.refactor_all
    estate_audit = RetroReflectionEngine.audit_estate(dist_dir, "profithelm")
    assert estate_audit["status"] == "PASS", f"Expected PASS after refactor_all, got: {estate_audit}"
    assert estate_audit["stale_count"] == 0

    # Verify AssetIntegrityEvaluator detects stale substrate_lock.json even when .agy/engine_hash.json is current
    state_file = repo_dir / ".agy" / "engine_hash.json"
    record_engine_hash(state_file)
    (repo_dir / "substrate_lock.json").write_text(
        json.dumps(
            {
                "property_id": "profithelm",
                "engine_hash": "0000000000000000000000000000000000000000000000000000000000000000",
                "substrate_hash": "0000000000000000000000000000000000000000000000000000000000000000",
                "dist_fingerprint": "stale",
                "total_assets": 1,
            }
        ),
        encoding="utf-8",
    )
    evaluator._audit_cache.clear()
    drift_rep = evaluator.audit_all(adapter, check_engine_drift=True, check_ledger=False)
    assert drift_rep.drifted_assets_count == 1
    assert DriftReason.ENGINE_HASH_DRIFT in drift_rep.drifted_assets[0].reasons

    # Once substrate_lock.json matches compute_engine_hash(), audit_all passes
    cur_hash = compute_engine_hash()
    (repo_dir / "substrate_lock.json").write_text(
        json.dumps(
            {
                "property_id": "profithelm",
                "engine_hash": cur_hash,
                "substrate_hash": cur_hash,
                "dist_fingerprint": "aligned",
                "total_assets": 1,
            }
        ),
        encoding="utf-8",
    )
    evaluator._audit_cache.clear()
    aligned_rep = evaluator.audit_all(adapter, check_engine_drift=True, check_ledger=False)
    assert aligned_rep.drifted_assets_count == 0


def test_single_pass_seo_document_parser_excludes_style_and_script_from_page_text():
    """
    Verifies SinglePassSEODocumentParser excludes inline <style> and non-JSON <script>
    blocks from page_text while preserving JSON-LD and calculation-manifest script payloads.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.verifier import SinglePassSEODocumentParser

    html = (
        "<!DOCTYPE html><html lang='en'><head>"
        "<title>2026 Section 179 Tax Calculator (Form 4562) | ProfitHelm</title>"
        "<style>.secret-css-token { color: red; }</style>"
        "<script type='application/ld+json'>{\"@context\":\"https://schema.org\",\"@type\":\"WebApplication\"}</script>"
        "<script type='application/json' id='calculation-manifest'>{\"model\":\"sec179\"}</script>"
        "<script>const secretJsToken = 999999;</script>"
        "</head><body><h1>Section 179 Calculator</h1><p>Statutory limit $1,250,000.</p></body></html>"
    )
    parser = SinglePassSEODocumentParser(brand_domain="profithelm.com")
    parser.feed(html)
    assert "secret-css-token" not in parser.page_text
    assert "secretJsToken" not in parser.page_text
    assert len(parser.json_ld_blocks) == 1
    assert len(parser.embedded_manifest_blocks) == 1


def test_truth_reconciliation_engine_auto_remediation_and_audit():
    """
    Verifies TruthReconciliationEngine deterministically detects and repairs stale 2026
    statutory figures, inline calculator JS caps, FAQ JSON-LD to DOM drift, missing signal
    WebPage JSON-LD, Prexvo IBR/PAYE vs RAP plan thresholds, and speculative filler.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.tenant_facts import TruthReconciliationEngine

    stale_ph_html = """<!DOCTYPE html><html lang="en"><head>
    <title>2026 Section 179 Tax Calculator (Form 4562) | ProfitHelm</title>
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "FAQPage",
      "mainEntity": [
        {
          "@type": "Question",
          "name": "What is the 2026 Section 179 SUV cap?",
          "acceptedAnswer": {
            "@type": "Answer",
            "text": "Stale schema answer"
          }
        }
      ]
    }
    </script>
    </head><body>
    <p>In today's rapidly evolving tax landscape, In 2026, Commercial Asset allows immediate first-year expensing of up to $1,250,000 in qualifying commercial equipment and software placed in service under IRC Section 179(b)(1), phasing out dollar-for-dollar above $3,130,000 in total asset purchases.</p>
    <p>Heavy SUVs are capped at a $31,300 Section 179 deduction in 2026. IRC 179 ($1.29M Cap) / 168(k) 20% Bonus.</p>
    <table><tr><td>$1,220,000 (Full Basis 100%)</td><td>60% on balance</td><td>$31,300 + Bonus Depr.</td></tr></table>
    <details class="faq-item"><summary>What is the 2026 Section 179 SUV cap?</summary><p>Under IRC Section 179(b)(5), the 2026 Heavy SUV cap is $30,500 ($31,300 for 2025 inflation-adjusted schedules).</p></details>
    <script>var suv179 = Math.min(cost, 31300);</script>
    </body></html>"""

    pre_violations = TruthReconciliationEngine.audit_html_truth_reconciliation(
        stale_ph_html,
        tenant="profithelm",
        rel_path="tools/section-179-calculator/index.html",
        slug="section-179-calculator",
    )
    assert len(pre_violations) >= 4

    reconciled_ph, repairs = TruthReconciliationEngine.reconcile_html_truth(
        stale_ph_html,
        tenant="profithelm",
        rel_path="tools/section-179-calculator/index.html",
        slug="section-179-calculator",
    )
    assert "speculative_filler_stripped" in repairs
    assert "profithelm_statutory_truth_reconciled" in repairs
    assert "faq_schema_dom_synced" in repairs
    assert "$2,560,000 (Full Basis 100%)" in reconciled_ph
    assert "up to $2,560,000 in qualifying commercial equipment" in reconciled_ph
    assert "above $4,090,000 in total asset purchases" in reconciled_ph
    assert "IRC 179 ($2.56M Cap) / 168(k) 20% Bonus" in reconciled_ph
    assert "var suv179 = Math.min(cost, 30500);" in reconciled_ph
    assert "<td>20% on balance</td>" in reconciled_ph
    assert "Stale schema answer" not in reconciled_ph

    post_violations = TruthReconciliationEngine.audit_html_truth_reconciliation(
        reconciled_ph,
        tenant="profithelm",
        rel_path="tools/section-179-calculator/index.html",
        slug="section-179-calculator",
    )
    assert post_violations == []

    # Verify Prexvo IBR Hardship Cap plan-threshold reconciliation
    stale_px_html = """<!DOCTYPE html><html lang="en"><head><title>2026 IBR Hardship Cap Calculator | Prexvo</title></head><body>
    <p>Under Title IV regulation 34 CFR Part 685, IBR Hardship Cap Calculator determines monthly obligations using the 225 percent HHS Poverty Guideline exemption ($35,212.50 protected single-filer income) and a 10 percent discretionary rate. Qualifying borrowers receive a 100 percent unpaid interest subsidy and full principal forgiveness after 120 to 240 certified monthly payments.</p>
    </body></html>"""
    assert TruthReconciliationEngine.audit_html_truth_reconciliation(
        stale_px_html, tenant="prexvo", slug="ibr-hardship-cap-calculator"
    )
    reconciled_px, px_repairs = TruthReconciliationEngine.reconcile_html_truth(
        stale_px_html, tenant="prexvo", slug="ibr-hardship-cap-calculator"
    )
    assert "prexvo_plan_threshold_reconciled" in px_repairs
    assert "150 percent HHS Poverty Guideline exemption ($23,475 protected single-filer income)" in reconciled_px
    assert (
        TruthReconciliationEngine.audit_html_truth_reconciliation(
            reconciled_px, tenant="prexvo", slug="ibr-hardship-cap-calculator"
        )
        == []
    )


def test_multi_channel_social_conversion_and_deeplink_hydration(tmp_path):
    """
    Verifies end-to-end social syndication conversion upgrades across ProfitHelm (21 tools)
    and Prexvo (13 tools):
    1. Every tool in both tenants has a bespoke statutory calculation proof (zero generic
       gross_amount*marginal_rate fallbacks) and passes truth-store audit with 0 failures.
    2. LinkedIn (strictly corporate company_id 143884102 / 106482194), Facebook, and X
       include zero-link native teaser_content + parameterized first_comment / first_comment_url
       with utm_content=first_comment to eliminate feed-suppression penalties.
    3. Referral-yield prioritization ranks tools deterministically combining commercial/statutory
       priority, GSC striking-distance impressions, and partner click telemetry.
    4. export_all_syndication_files writes root {slug}-linkedin.md, {slug}-newsletter.md,
       and {slug}-Substack Notes-post.txt so evaluate_gsc_candidate_readiness reports 0 missing files.
    5. visual_primitives runtime includes hydrateInputsFromLocationSearch() and multi-channel
       social traffic_source attribution, and affiliates aggregates by_traffic_source.
    """
    from pseofactory.audit import audit_syndication_asset_against_truth_store
    from pseofactory.contracts import assert_linkedin, assert_no_personal_attribution, assert_x_post
    from pseofactory.distributor import (
        CURATED_TOOL_CALCULATION_PROOFS,
        PREXVO_TOOL_SCENARIOS,
        export_all_syndication_files,
        generate_all_distribution_assets,
        prioritize_distribution_queue_by_referral_yield,
    )
    from pseofactory.gsc_remediation import evaluate_asset_conversion_and_distribution_readiness
    from pseofactory.maintenance import GAINHELM_DEFAULT_TOOLS, PREXVO_DEFAULT_TOOLS, PROFITHELM_DEFAULT_TOOLS
    from pseofactory.visual_primitives import render_runtime_synchronizer_script
    from pseofactory.affiliates import aggregate_outbound_partner_engagement

    # 1. ProfitHelm: all 21 active tools have curated statutory proofs and zero-link native teasers
    from pseofactory.qualification import is_retired_or_consolidated_slug
    px_slugs = {t["slug"] for t in PREXVO_DEFAULT_TOOLS} | set(PREXVO_TOOL_SCENARIOS.keys())
    gh_slugs = {t["slug"] for t in GAINHELM_DEFAULT_TOOLS}
    ph_all_21_tools = [
        {"slug": s, "title": s.replace("-", " ").title()}
        for s in sorted(CURATED_TOOL_CALCULATION_PROOFS.keys())
        if s not in px_slugs
        and s not in gh_slugs
        and not is_retired_or_consolidated_slug(s, "profithelm")
        and not is_retired_or_consolidated_slug(s, "prexvo")
    ]
    ph_assets = generate_all_distribution_assets(tools=ph_all_21_tools, property_id="profithelm")
    assert len(ph_assets) == 21
    for slug, pack in ph_assets.items():
        assert slug in CURATED_TOOL_CALCULATION_PROOFS, f"Missing curated proof for {slug}"
        audit_res = audit_syndication_asset_against_truth_store(pack, property_id="profithelm")
        assert audit_res["status"] == "PASS", f"ProfitHelm {slug} failed truth audit: {audit_res}"
        assert pack["linkedin"]["company_id"] == "143884102"
        assert pack["linkedin"]["post_mode"] == "zero_link_teaser_plus_first_comment"
        assert "https://" not in pack["linkedin"]["teaser_content"]
        assert "utm_content=first_comment" in pack["linkedin"]["first_comment_url"]
        assert "https://" not in pack["facebook"]["teaser_content"]
        assert "utm_content=first_comment" in pack["facebook"]["first_comment_url"]
        assert_x_post(pack["x"]["content"])
        assert_linkedin(pack["linkedin"]["content"])
        assert_no_personal_attribution(pack["linkedin"]["content"], context=slug)

    # 2. Prexvo: all active tools route to corporate company_id 106482194 and pass truth store audit
    px_all_tools = [
        {"slug": s, "title": s.replace("-", " ").title()}
        for s in sorted(PREXVO_TOOL_SCENARIOS.keys())
        if not is_retired_or_consolidated_slug(s, "prexvo")
    ]
    px_assets = generate_all_distribution_assets(tools=px_all_tools, property_id="prexvo")
    assert len(px_assets) == len(px_all_tools) >= 13
    for slug, pack in px_assets.items():
        audit_res = audit_syndication_asset_against_truth_store(pack, property_id="prexvo")
        assert audit_res["status"] == "PASS", f"Prexvo {slug} failed truth audit: {audit_res}"
        assert pack["linkedin"]["company_id"] == "106482194"
        assert "https://" not in pack["linkedin"]["teaser_content"]
        assert "utm_content=first_comment" in pack["linkedin"]["first_comment_url"]
        assert_x_post(pack["x"]["content"])
        assert_linkedin(pack["linkedin"]["content"])
        assert_no_personal_attribution(pack["linkedin"]["content"], context=slug)

    # 3. Referral-yield prioritization
    ph_ranked = prioritize_distribution_queue_by_referral_yield(property_id="profithelm", tools=ph_all_21_tools)
    px_ranked = prioritize_distribution_queue_by_referral_yield(property_id="prexvo", tools=px_all_tools)
    assert len(ph_ranked) == 21
    assert len(px_ranked) == len(px_all_tools)
    assert ph_ranked[0]["priority_score"] >= ph_ranked[-1]["priority_score"]
    assert px_ranked[0]["company_id"] == "106482194"

    # 4. Root syndication discovery files eliminate missing_syndication_files in GSC readiness check
    synd_out = tmp_path / "syndication"
    export_all_syndication_files(
        output_dir=synd_out,
        tools=[PROFITHELM_DEFAULT_TOOLS[0]],
        property_id="profithelm",
    )
    first_slug = PROFITHELM_DEFAULT_TOOLS[0]["slug"]
    assert (synd_out / f"{first_slug}-linkedin.md").is_file()
    assert (synd_out / f"{first_slug}-newsletter.md").is_file()
    assert (synd_out / f"{first_slug}-Substack Notes-post.txt").is_file()
    readiness = evaluate_asset_conversion_and_distribution_readiness(
        slug=first_slug,
        tenant_id="profithelm",
        impressions=100,
        position=8.2,
        base_dir=tmp_path,
    )
    assert readiness["missing_syndication_files"] == []
    assert readiness["has_external_distribution"] is True

    # 5. Deep-link URL hydration runtime and social traffic source attribution
    wb_html = render_runtime_synchronizer_script()
    assert "function hydrateInputsFromLocationSearch()" in wb_html
    assert "hydrateInputsFromLocationSearch();" in wb_html
    assert "linkedin_company" in wb_html
    assert "facebook_social" in wb_html
    assert "youtube_video" in wb_html

    agg = aggregate_outbound_partner_engagement(
        [
            {
                "event_type": "workbench_interaction",
                "interaction_type": "social_deeplink_hydrated",
                "tool_slug": "section-179-calculator",
                "property_id": "profithelm",
                "traffic_source": "linkedin_company",
            },
            {
                "event_type": "affiliate_click",
                "tool_slug": "section-179-calculator",
                "partner_key": "ramp",
                "property_id": "profithelm",
                "traffic_source": "linkedin_company",
            },
        ],
        property_id="profithelm",
    )
    assert "by_traffic_source" in agg
    assert agg["by_traffic_source"]["linkedin_company"]["deeplink_hydrations"] == 1
    assert agg["by_traffic_source"]["linkedin_company"]["outbound_clicks"] == 1


def test_comprehensive_truth_reconciliation_and_cross_element_parity_gates(tmp_path):
    """
    Verifies the upgraded deterministic TruthReconciliationEngine, TenantFactStore,
    audit_rendered_asset, audit_syndication_asset_against_truth_store, and RetroReflectionEngine
    across ProfitHelm and Prexvo mathematical, statutory, and cross-element parity invariants.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.audit import (
        audit_rendered_asset,
        audit_syndication_asset_against_truth_store,
    )
    from pseofactory.distributor import generate_social_syndication_pack
    from pseofactory.gsc_remediation import (
        _normalize_meta_120_155,
        _normalize_title_50_60,
        compile_remediation_overlay_spec,
    )
    from pseofactory.maintenance import RetroReflectionEngine
    from pseofactory.tenant_facts import TenantFactStore, TruthReconciliationEngine
    from pseofactory.verifier import verify_html_cross_web_consensus_and_corroboration
    from pseofactory.visual_primitives import render_runtime_synchronizer_script

    # 1. Runtime script uses 20% bonus depreciation (0.20) and tenant-aware offer price fallback
    runtime_js = render_runtime_synchronizer_script()
    assert "remBasis * 0.20" in runtime_js
    assert "remBasis * 0.80" not in runtime_js
    assert "offer_price_usd || 29" not in runtime_js

    # 2. ProfitHelm HTML truth reconciliation heals 80% bonus, HoH 12700, S-Corp $19,125, Tariff $161,000, Treasury 0.06
    drifted_ph_html = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>S-Corp Reasonable Salary Tax Calculator 2026 | ProfitHelm</title>'
        '<link rel="canonical" href="https://profithelm.com/tools/s-corp-reasonable-salary-tax-calculator/"></head>'
        '<body><main>'
        '<script>var b = remBasis * 0.80; var hoh = { single: 8600, mfj: 17200, hoh: 12700 };</script>'
        '<p>Saves $19,125 in self-employment tax ($15,500 OASDI + $3,625 Medicare). '
        'Section 301 landed cost is $161,000 ($6,800 freight). Formula: Yield / (1: 13.3% state rate).</p>'
        '<script type="application/ld+json">{"@context":"https://schema.org","@type":"Offer","price":"29"}</script>'
        '</main></body></html>'
    )
    ph_issues_before = TruthReconciliationEngine.audit_html_truth_reconciliation(
        drifted_ph_html,
        tenant="profithelm",
        rel_path="tools/s-corp-reasonable-salary-tax-calculator/index.html",
    )
    assert len(ph_issues_before) >= 5
    gate_before = verify_html_cross_web_consensus_and_corroboration(
        drifted_ph_html,
        rel_path="tools/s-corp-reasonable-salary-tax-calculator/index.html",
        require_corroboration=False,
    )
    assert gate_before["status"] == "FAIL"

    healed_ph_html, ph_repairs = TruthReconciliationEngine.reconcile_html_truth(
        drifted_ph_html,
        tenant="profithelm",
        slug="s-corp-reasonable-salary-tax-calculator",
    )
    assert ph_repairs
    assert "remBasis * 0.20" in healed_ph_html
    assert "hoh: 12900" in healed_ph_html
    assert "$13,193 in self-employment tax ($10,056 OASDI + $3,137 Medicare)" in healed_ph_html
    assert "(1 - 13.3% state rate)" in healed_ph_html
    assert '"price":"49"' in healed_ph_html
    assert (
        TruthReconciliationEngine.audit_html_truth_reconciliation(
            healed_ph_html,
            tenant="profithelm",
            rel_path="tools/s-corp-reasonable-salary-tax-calculator/index.html",
        )
        == []
    )

    # 3. Prexvo plan-specific statutory threshold reconciliation (IBR 150%, ICR 100%, Tiered Standard 34 CFR 685.208, Grad PLUS, PSLF)
    drifted_ibr_html = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<link rel="canonical" href="https://prexvo.com/tools/ibr-hardship-cap-calculator/"></head>'
        '<body><main><h1>IBR Hardship Cap Calculator</h1>'
        '<div class="quick-answer-body"><p>Calculates 2026 payments using the 225% FPL ($35,212.50) exemption and 300-month timeline.</p></div>'
        '</main></body></html>'
    )
    assert TruthReconciliationEngine.audit_html_truth_reconciliation(
        drifted_ibr_html,
        tenant="prexvo",
        rel_path="tools/ibr-hardship-cap-calculator/index.html",
    )
    healed_ibr_html, _ = TruthReconciliationEngine.reconcile_html_truth(
        drifted_ibr_html,
        tenant="prexvo",
        slug="ibr-hardship-cap-calculator",
    )
    assert "150% FPL ($23,475)" in healed_ibr_html
    assert "225% FPL" not in healed_ibr_html
    assert (
        TruthReconciliationEngine.audit_html_truth_reconciliation(
            healed_ibr_html,
            tenant="prexvo",
            rel_path="tools/ibr-hardship-cap-calculator/index.html",
        )
        == []
    )

    # 4. Non-calculator Prexvo pages (disclaimers, methodology, privacy, about, tools-directory) preserve non-calculator titles/meta
    disc_title = _normalize_title_50_60("Disclaimers", "Prexvo", "prexvo")
    assert "Disclaimers" in disc_title
    assert "Calculator" not in disc_title
    disc_meta = _normalize_meta_120_155("Disclaimers", "prexvo", "disclaimers")
    assert 120 <= len(disc_meta) <= 155
    assert "225% HHS Poverty" not in disc_meta
    assert "Calculate Disclaimers" not in disc_meta

    # 5. Tax-equivalent yield percentage precision for treasury-yield-calculator (6.13)
    treasury_m = RetroReflectionEngine.PROFITHELM_FALLBACK_MANIFESTS["treasury-yield-calculator"]
    assert treasury_m["published_output"] == 6.13
    treasury_html = (
        '<!DOCTYPE html><html lang="en" data-theme="porcelain"><head>'
        '<link rel="canonical" href="https://profithelm.com/tools/treasury-yield-calculator/"></head>'
        '<body><main><h1>Treasury Yield Calculator</h1></main></body></html>'
    )
    retro_treasury_html, _ = RetroReflectionEngine.retrofit_html(
        treasury_html,
        property_id="profithelm",
        slug="treasury-yield-calculator",
        canonical_url="https://profithelm.com/tools/treasury-yield-calculator/",
    )
    assert 'data-baseline-output="6.13">6.13</strong>' in retro_treasury_html
    assert 'class="scenario-baseline">6.13</strong>' in retro_treasury_html
    treasury_audit = audit_rendered_asset(
        retro_treasury_html,
        candidate_spec=treasury_m,
        tenant="profithelm",
    )
    assert treasury_audit.gate_results["formula_evaluation_parity"] is True
    assert treasury_audit.gate_results["table_cell_truthfulness"] is True

    # 6. Syndication truth audit unpacks TenantFactStore.verify_claim tuple and catches stale claims
    valid_scorp_pack = generate_social_syndication_pack(
        "s-corp-reasonable-salary-tax-calculator",
        property_id="profithelm",
    )
    scorp_synd_res = audit_syndication_asset_against_truth_store(
        valid_scorp_pack,
        property_id="profithelm",
        fact_store=TenantFactStore.get_instance(),
    )
    assert scorp_synd_res["passed"] is True
    assert scorp_synd_res["violations"] == []

    stale_pack = dict(valid_scorp_pack)
    stale_pack["linkedin"] = dict(valid_scorp_pack["linkedin"])
    stale_pack["linkedin"]["content"] = stale_pack["linkedin"]["content"] + " Bonus depreciation is 80% in 2026."
    stale_synd_res = audit_syndication_asset_against_truth_store(
        stale_pack,
        property_id="profithelm",
        fact_store=TenantFactStore.get_instance(),
    )
    assert stale_synd_res["passed"] is False
    assert any("STATUTORY_TRUTH_MISMATCH" in v for v in stale_synd_res["violations"])

    # 7. Equipment lease overlay spec uses IRC Section 162(a)(3) and FASB ASC 842
    equip_spec = compile_remediation_overlay_spec(
        {
            "target_url": "https://profithelm.com/tools/equipment-lease-tax-deduction/",
            "query": "equipment lease tax deduction calculator",
            "impressions": 120,
            "position": 8.5,
        },
        tenant_id="profithelm",
    )
    assert "162(a)(3)" in equip_spec["quick_answer"]
    assert "ASC 842" in equip_spec["quick_answer"]


def test_mid_rebuild_dom_parity_git_archive_fallback_and_aborted_run_manifest_synthesis(tmp_path):
    """
    Verifies:
    1. PartnerTrackingEngine.audit_readiness_and_vault_parity() falls back to git archive HEAD:dist
       when a concurrent tenant build_all() temporarily overwrites dist/ before overlay re-injection.
    2. reconcile_workspace_tracking_state() synthesizes a reconciled release_manifest.json when a
       run directory terminated at Stage 5 (ci_failure_incident.json) or Stage 7 (verification_proof.txt)
       without writing a manifest.
    Zero em-dashes. Zero en-dashes.
    """
    import subprocess
    from pseofactory.action_bus import HumanActionBus
    from pseofactory.gitops import reconcile_workspace_tracking_state
    from pseofactory.partner_tracker import EmailIngestionEngine, PartnerTrackingEngine

    # 1. Create a git repo whose committed HEAD dist/ has >= 671 network-tracked /r/ links,
    #    then overwrite the working-tree dist/ with an incomplete mid-rebuild page (only 5 /r/ links).
    ph_repo = tmp_path / "profithelm-platform"
    ph_dist = ph_repo / "dist"
    ph_dist.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(ph_repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(ph_repo), "config", "user.email", "test@profithelm.com"], check=True)
    subprocess.run(["git", "-C", str(ph_repo), "config", "user.name", "Test Runner"], check=True)

    full_links_html = "<html><body>" + "".join(
        '<a href="/r/mercury">Mercury</a>' for _ in range(700)
    ) + "</body></html>"
    (ph_dist / "index.html").write_text(full_links_html, encoding="utf-8")
    subprocess.run(["git", "-C", str(ph_repo), "add", "-f", "dist/index.html"], check=True)
    subprocess.run(["git", "-C", str(ph_repo), "commit", "-m", "chore: full compiled dist"], check=True, capture_output=True)

    # Simulate mid-rebuild working tree with only 10 links (< 671 threshold)
    (ph_dist / "index.html").write_text(
        "<html><body>" + "".join('<a href="/r/mercury">Mercury</a>' for _ in range(10)) + "</body></html>",
        encoding="utf-8",
    )

    px_dist = tmp_path / "prexvo" / "dist"
    px_dist.mkdir(parents=True, exist_ok=True)
    (px_dist / "index.html").write_text(
        "<html><body>" + "".join('<a href="/r/sofi">SoFi</a>' for _ in range(80)) + "</body></html>",
        encoding="utf-8",
    )

    tracker = PartnerTrackingEngine(
        email_engine=EmailIngestionEngine(
            cache_path=str(tmp_path / "mail_cache.json"),
            state_path=str(tmp_path / "mail_state.json"),
        ),
        action_bus=HumanActionBus(bus_path=str(tmp_path / "bus.json")),
    )
    audit = tracker.audit_readiness_and_vault_parity(
        profithelm_dist_dir=str(ph_dist),
        prexvo_dist_dir=str(px_dist),
    )
    assert audit["properties"]["profithelm"]["compiled_dom_parity"]["total_outbound_r_links"] == 700
    assert audit["properties"]["prexvo"]["compiled_dom_parity"]["total_outbound_r_links"] == 80

    # 2. Verify reconcile_workspace_tracking_state synthesizes release_manifest.json for aborted runs
    runs_dir = tmp_path / "runs"
    aborted_ci_dir = runs_dir / "monetization-e2e-repair"
    aborted_ci_dir.mkdir(parents=True, exist_ok=True)
    (aborted_ci_dir / "ci_failure_incident.json").write_text(
        json.dumps(
            {
                "run_id": "monetization-e2e-repair",
                "project": "/home/ubuntuadmin/projects/pseofactory",
                "failed_sha": "598b68b",
                "status": "CI_FAILURE",
            }
        ),
        encoding="utf-8",
    )
    rec = reconcile_workspace_tracking_state(
        runs_dir=runs_dir,
        queues_dir=tmp_path / "queues",
        ledger_path=tmp_path / "ledger.json",
        repo_heads={"pseofactory": "acbe3bb"},
    )
    assert rec["status"] == "PASS"
    assert (aborted_ci_dir / "release_manifest.json").is_file()
    synth_man = json.loads((aborted_ci_dir / "release_manifest.json").read_text(encoding="utf-8"))
    assert synth_man["status"] == "RECONCILED_BY_SUBSEQUENT_RELEASE"
    assert synth_man["reconciled_by_head_sha"] == "acbe3bb"


def test_gainhelm_full_three_tenant_stage_parity(tmp_path):
    """
    Verifies that GainHelm executes with 100% deterministic parity alongside
    ProfitHelm and Prexvo across:
    1. Multi-channel syndication generation, curated statutory calculation proofs,
       YouTube transcript brand parity ('GainHelm'), and AI benchmark matrices.
    2. Partner tracking readiness, publisher prerequisites, cluster monetization gaps,
       and three-rail checkout/fulfillment workpapers ($79 SOC 2/CMMC and $49 HIPAA/ISO).
    3. Indexing inspector, indexing feedback loop, and push indexer tenant boundaries.
    4. Trend history DB statutory economic timeseries, cron property assignment, and
       competitor query modifier expansion.
    """
    from pseofactory.audit import audit_syndication_asset_against_truth_store
    from pseofactory.browser_verifier import GainHelmBrowserAdapter
    from pseofactory.qualification import evaluate_query_modifier_expansion_vs_distinct_tool
    from pseofactory.distributor import (
        CURATED_TOOL_CALCULATION_PROOFS,
        generate_ai_benchmark_nodes,
        generate_all_distribution_assets,
        generate_youtube_syndication,
    )
    from pseofactory.indexing.feedback_loop import IndexingFeedbackLoop
    from pseofactory.indexing.milestones import VALID_TENANTS as MILESTONE_TENANTS
    from pseofactory.indexing_inspector import DailyIndexingInspector
    from pseofactory.maintenance import GAINHELM_DEFAULT_TOOLS
    from pseofactory.partner_tracker import (
        PartnerTrackingEngine,
        resolve_lead_monetization_offer,
        synthesize_personalized_audit_workpaper,
    )
    from pseofactory.trends.cron import TrendCronRunner
    from pseofactory.trends.db import TrendHistoryDB

    assert "gainhelm" in MILESTONE_TENANTS
    insp = DailyIndexingInspector(tenant_id="gainhelm", base_dir=tmp_path)
    assert insp.tenant_id == "gainhelm"

    gh_browser = GainHelmBrowserAdapter()
    assert gh_browser.tenant_id == "gainhelm"
    assert gh_browser.canonical_domain == "https://gainhelm.com"
    assert len(gh_browser.get_widget_specs()) >= 3

    gh_assets = generate_all_distribution_assets(tools=GAINHELM_DEFAULT_TOOLS, property_id="gainhelm")
    assert len(gh_assets) == 10
    for slug, pack in gh_assets.items():
        assert slug in CURATED_TOOL_CALCULATION_PROOFS
        audit_res = audit_syndication_asset_against_truth_store(pack, property_id="gainhelm")
        assert audit_res["status"] == "PASS", f"GainHelm {slug} failed truth audit: {audit_res}"
        yt = generate_youtube_syndication(slug, property_id="gainhelm")
        assert "GainHelm" in yt["transcript"]
        assert f"https://gainhelm.com/tools/{slug}/" in yt["description"]

    bench = generate_ai_benchmark_nodes(tenant="gainhelm")
    assert len(bench["files"]) >= 7
    assert "soc2_cmmc_audit_benchmarks.md" in bench["files"]

    db = TrendHistoryDB(db_path=tmp_path / "test_trends.db")
    mat = db.compile_statutory_economic_matrix("gainhelm", "soc 2 audit cost calculator")
    assert len(mat["series"]) >= 4
    cron = TrendCronRunner(db_path=tmp_path / "test_trends.db")
    assign = cron.determine_property_assignment("cmmc 2.0 level 2 c3pao audit cost calculator")
    assert assign["property_id"] == "gainhelm"
    assert assign["contamination_scan_passed"] == 1

    mod_eval = evaluate_query_modifier_expansion_vs_distinct_tool(
        "soc 2 type 2 audit cost for 50 employees",
        property_id="gainhelm",
    )
    assert mod_eval["decision"] == "EXPAND_EXISTING_PAGE"
    assert mod_eval["action"] == "REFACTOR_PAGE"
    assert mod_eval["matched_tool_slug"] == "soc-2-audit-cost-calculator"

    offer_79 = resolve_lead_monetization_offer("gainhelm", "soc-2-audit-cost-calculator", lead_id="lead_gh_test")
    assert offer_79["offer_sku"] == "gh_soc2_cmmc_audit_workpapers"
    assert offer_79["offer_price_usd"] == 79.0
    wp_79 = synthesize_personalized_audit_workpaper(
        property_id="gainhelm",
        tool_slug="soc-2-audit-cost-calculator",
        lead_record={"lead_id": "lead_gh_test", "offer_sku": "gh_soc2_cmmc_audit_workpapers"},
        mode="paid_toolkit",
    )
    assert len(wp_79["reconciliation_schedule"]) >= 4
    assert len(wp_79["statutory_trend_timeseries"]) >= 3

    tracker = PartnerTrackingEngine()
    gaps = tracker.analyze_cluster_monetization_gaps()
    assert "gainhelm" in gaps["properties"]
    assert gaps["properties"]["gainhelm"]["uncovered_count"] == 0

    fb = IndexingFeedbackLoop(property_id="gainhelm", base_dir=tmp_path)
    assert fb.domain == "gainhelm.com"

    # 5. Edge function parity (lead-capture.js, checkout.js, lead-fulfillment.js, telemetry.js)
    from pseofactory.edge import generate_edge_lead_capture_function, sync_tenant_edge_redirect_function

    gh_lead_js = generate_edge_lead_capture_function("gainhelm")
    assert "resolveEdgeStripeCheckoutOffer" in gh_lead_js
    assert "stripe_live_session" in gh_lead_js
    assert "html_report" in gh_lead_js
    assert "csv_content" in gh_lead_js
    assert "lead_gainhelm_" in gh_lead_js

    gh_repo = tmp_path / "gainhelm_repo"
    (gh_repo / "functions" / "r").mkdir(parents=True, exist_ok=True)
    sync_res = sync_tenant_edge_redirect_function(gh_repo, "gainhelm")
    assert sync_res["status"] == "UPDATED"
    assert (gh_repo / "functions" / "api" / "lead-capture.js").is_file()
    assert (gh_repo / "functions" / "api" / "telemetry.js").is_file()
    assert (gh_repo / "functions" / "api" / "checkout.js").is_file()
    assert (gh_repo / "functions" / "api" / "lead-fulfillment.js").is_file()
    assert "withCheckoutFlag" in (gh_repo / "functions" / "api" / "checkout.js").read_text(encoding="utf-8")
    assert "withFulfillFlag" in (gh_repo / "functions" / "api" / "lead-fulfillment.js").read_text(encoding="utf-8")

    # 6. Legacy SQLite schema migration parity (serp_weaknesses + 'gainhelm' CHECK constraint)
    import sqlite3
    from pseofactory.trends.models import PropertyAssignmentRecord, TregSnapshotRecord

    legacy_db_path = tmp_path / "legacy_trends.db"
    conn = sqlite3.connect(str(legacy_db_path))
    conn.executescript(
        """
        CREATE TABLE treg_metric_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            query_slug TEXT NOT NULL,
            cycle_id TEXT NOT NULL,
            search_volume INTEGER NOT NULL DEFAULT 0,
            cpc_usd REAL NOT NULL DEFAULT 0.0,
            competition_index REAL NOT NULL DEFAULT 0.0,
            keyword_difficulty REAL NOT NULL DEFAULT 0.0,
            position_zero_vacant INTEGER NOT NULL DEFAULT 0,
            historical_stability REAL NOT NULL DEFAULT 0.85,
            volume_delta_pct REAL NOT NULL DEFAULT 0.0,
            cpc_delta_pct REAL NOT NULL DEFAULT 0.0,
            volatility_score REAL NOT NULL DEFAULT 0.0,
            checked_at TEXT NOT NULL
        );
        CREATE TABLE property_assignments (
            assignment_id TEXT PRIMARY KEY,
            query_slug TEXT NOT NULL,
            cycle_id TEXT NOT NULL,
            property_id TEXT NOT NULL CHECK(property_id IN ('prexvo', 'profithelm', 'unassigned')),
            assignment_basis TEXT NOT NULL,
            matched_existing_slug TEXT,
            cannibalization_score REAL NOT NULL DEFAULT 0.0,
            current_position REAL NOT NULL DEFAULT 100.0,
            contamination_scan_passed INTEGER NOT NULL DEFAULT 1,
            assigned_at TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()

    migrated_db = TrendHistoryDB(db_path=legacy_db_path)
    migrated_db.record_treg_snapshot(
        TregSnapshotRecord(
            snapshot_id="snap_gh_1",
            query_slug="soc-2-type-2-audit-cost-calculator",
            cycle_id="cycle_gh_1",
            search_volume=2400,
            cpc_usd=38.5,
            competition_index=0.72,
            keyword_difficulty=42.0,
            position_zero_vacant=1,
            historical_stability=0.9,
            volume_delta_pct=12.0,
            cpc_delta_pct=5.0,
            volatility_score=0.1,
            checked_at="2026-10-26T21:00:00Z",
            serp_weaknesses='["thin_blog"]',
        )
    )
    migrated_db.record_property_assignment(
        PropertyAssignmentRecord(
            assignment_id="assign_gh_1",
            query_slug="soc-2-type-2-audit-cost-calculator",
            cycle_id="cycle_gh_1",
            property_id="gainhelm",
            assignment_basis="Direct GRC match",
            matched_existing_slug="soc-2-audit-cost-calculator",
            cannibalization_score=0.05,
            current_position=100.0,
            contamination_scan_passed=1,
            assigned_at="2026-10-26T21:00:00Z",
        )
    )
    pa_row = migrated_db.get_connection().execute(
        "SELECT property_id FROM property_assignments WHERE assignment_id = 'assign_gh_1'"
    ).fetchone()
    assert pa_row is not None and pa_row["property_id"] == "gainhelm"

    # 7. Deep syndication, AI benchmarks, GSC math domain, and statutory spike parity
    from pseofactory.distributor import (
        TOOL_YOUTUBE_METADATA,
        generate_ai_benchmark_nodes,
        compile_public_benchmark_citation_hubs,
        compile_broken_calculator_link_reclamation_briefs,
        prioritize_distribution_queue_by_referral_yield,
        export_all_syndication_files,
    )
    from pseofactory.gsc_remediation import classify_deterministic_math_opportunity
    from pseofactory.seo_growth_loops import SEEDED_LIVE_GSC_URL_INSPECTIONS
    from pseofactory.trends.collectors import StatutoryEconomicDatasetCollector

    assert "soc-2-audit-cost-calculator" in TOOL_YOUTUBE_METADATA
    assert "cmmc-level-2-audit-cost-calculator" in TOOL_YOUTUBE_METADATA
    assert "hitrust-certification-cost-calculator" in TOOL_YOUTUBE_METADATA

    gh_bm = generate_ai_benchmark_nodes(tenant="gainhelm")
    px_bm = generate_ai_benchmark_nodes(tenant="prexvo")
    assert gh_bm["nodes_count"] == px_bm["nodes_count"] == 4
    assert gh_bm["files_count"] == px_bm["files_count"] == 11
    assert compile_public_benchmark_citation_hubs("gainhelm")["payload"]["citable_statistics_count"] == 3
    assert compile_broken_calculator_link_reclamation_briefs("gainhelm")["briefs_count"] == 2

    gh_queue = prioritize_distribution_queue_by_referral_yield(property_id="gainhelm")
    assert len(gh_queue) >= 10
    assert gh_queue[0]["company_id"] == "106482195"
    assert gh_queue[0]["revenue_priority_score"] == 69.0

    gh_synd_dir = tmp_path / "gh_syndication"
    export_all_syndication_files(output_dir=gh_synd_dir, property_id="gainhelm")
    soc2_gs = (gh_synd_dir / "soc-2-audit-cost-calculator" / "google_sites.html").read_text(encoding="utf-8")
    assert len(soc2_gs) > 3500
    assert "application/ld+json" in soc2_gs
    soc2_pack = json.loads((gh_synd_dir / "soc-2-audit-cost-calculator" / "syndication_pack.json").read_text(encoding="utf-8"))
    assert soc2_pack["linkedin"]["post_mode"] == "zero_link_teaser_plus_first_comment"
    assert "--company-id 106482195" in soc2_pack["linkedin"]["command_hint"]

    gsc_math = classify_deterministic_math_opportunity(
        slug="soc-2-audit-cost-calculator",
        query="soc 2 type 2 audit cost",
        tenant_id="gainhelm",
    )
    assert gsc_math["math_domain"] == "CYBER_COMPLIANCE_STATUTORY_MATH"
    assert "AICPA SSAE 18" in gsc_math["statutory_citation"]
    assert "gainhelm" in SEEDED_LIVE_GSC_URL_INSPECTIONS
    assert len(SEEDED_LIVE_GSC_URL_INSPECTIONS["gainhelm"]) >= 4

    stat_collector = StatutoryEconomicDatasetCollector(db_path=legacy_db_path)
    spikes = stat_collector.harvest_statutory_spikes()
    spike_props = {s.raw_payload.get("property_id") for s in spikes}
    assert {"profithelm", "prexvo", "gainhelm"}.issubset(spike_props)


def test_gainhelm_edge_direct_contract_upgrades_and_post_checkout_monetization(tmp_path):
    """
    Verifies:
    1. MonetizationHub.get_direct_contract_upgrades('gainhelm') maps all 6 GainHelm GRC partner slots
       to active, counterparty-approved B2B affiliate contracts (Ramp Impact #51436, Xendoo Impact #16354,
       LawDepot CJ #4544498) with zero cross-tenant forbidden token contamination.
    2. GainHelm's generated functions/r/[partner].js executes in Node.js, upgrading all 6 /r/<partner>
       routes to HTTP 302 commission-bearing contracts with X-Edge-Contract-Tier: direct_contract_upgraded
       and preserving subId1/sharedid (Impact) and sid (CJ).
    3. GainHelm's generated functions/api/lead-capture.js onRequestPost invokes resolveEdgeStripeCheckoutOffer
       on POST /api/checkout, POST /api/lead-fulfillment, and POST /api/lead-capture.
    4. PartnerTrackingEngine.audit_readiness_and_vault_parity() reports 100.0% edge_upgraded_click_share_pct
       for gainhelm, and reconcile_non_active_partnerships_and_edge_routes() classifies all 6 GRC partners
       under NEWLY_APPROVED_AND_WIRED_AT_EDGE.
    """
    import subprocess
    from pseofactory.affiliates_hub import MonetizationHub
    from pseofactory.edge import (
        generate_edge_lead_capture_function,
        sync_tenant_edge_redirect_function,
    )
    from pseofactory.maintenance import CrossPropertyContaminationScanner
    from pseofactory.partner_tracker import PartnerTrackingEngine

    hub = MonetizationHub()
    gh_upgrades = hub.get_direct_contract_upgrades("gainhelm")
    expected_keys = {
        "vanta_security",
        "drata_compliance",
        "sprinto_compliance",
        "thoropass_audit",
        "coalition_cyber_insurance",
        "cobalt_pentest",
    }
    assert set(gh_upgrades.keys()) == expected_keys
    assert gh_upgrades["vanta_security"] == "https://join.ramp.com/c/7932737/3981015/51436"
    assert gh_upgrades["drata_compliance"] == "https://join.ramp.com/c/7932737/3981015/51436"
    assert gh_upgrades["sprinto_compliance"] == "https://www.jdoqocy.com/click-101906407-16985242"
    assert gh_upgrades["thoropass_audit"] == "https://xendoo.pxf.io/c/7932737/1357375/16354"
    assert gh_upgrades["coalition_cyber_insurance"] == "https://www.jdoqocy.com/click-101906407-16985242"
    assert gh_upgrades["cobalt_pentest"] == "https://join.ramp.com/c/7932737/3981015/51436"

    gh_repo = tmp_path / "gainhelm"
    (gh_repo / "functions" / "r").mkdir(parents=True, exist_ok=True)
    sync_tenant_edge_redirect_function(gh_repo, property_id="gainhelm")
    scanner = CrossPropertyContaminationScanner()
    assert scanner.scan_directory(gh_repo / "functions", "gainhelm") == {}

    gh_r = gh_repo / "functions" / "r" / "[partner].js"
    node_script = f"""
    (async () => {{
      const ghRedirect = await import({json.dumps(gh_r.as_uri())});

      // 1. Impact contract upgrade (vanta_security -> join.ramp.com)
      const vantaRes = await ghRedirect.onRequest({{
        request: new Request("https://gainhelm.com/r/vanta_security?source_tool=soc-2-audit-cost-calculator&cta_slot=hero_callout&subid=vanta_soc2_hero"),
        env: {{}},
        params: {{ partner: "vanta_security" }}
      }});
      if (vantaRes.status !== 302) process.exit(10);
      const vantaLoc = new URL(vantaRes.headers.get("Location"));
      if (vantaLoc.hostname !== "join.ramp.com" || !vantaLoc.pathname.includes("/51436")) process.exit(11);
      if (vantaLoc.searchParams.get("subId1") !== "vanta_soc2_hero") process.exit(12);
      if (vantaLoc.searchParams.get("sharedid") !== "soc-2-audit-cost-calculator") process.exit(13);
      if (vantaRes.headers.get("X-Edge-Contract-Tier") !== "direct_contract_upgraded") process.exit(14);
      if (!String(vantaRes.headers.get("X-Edge-Native-Destination") || "").startsWith("https://www.vanta.com/")) process.exit(15);

      // 2. CJ contract upgrade (sprinto_compliance -> www.jdoqocy.com)
      const sprintoRes = await ghRedirect.onRequest({{
        request: new Request("https://gainhelm.com/r/sprinto_compliance?source_tool=soc-2-audit-cost-calculator&cta_slot=comparison_table&subid=sprinto_soc2_table"),
        env: {{}},
        params: {{ partner: "sprinto_compliance" }}
      }});
      if (sprintoRes.status !== 302) process.exit(20);
      const sprintoLoc = new URL(sprintoRes.headers.get("Location"));
      if (sprintoLoc.hostname !== "www.jdoqocy.com") process.exit(21);
      if (sprintoLoc.searchParams.get("sid") !== "sprinto_soc2_table") process.exit(22);
      if (sprintoRes.headers.get("X-Edge-Contract-Tier") !== "direct_contract_upgraded") process.exit(23);

      // 3. Impact Xendoo contract upgrade (thoropass_audit -> xendoo.pxf.io)
      const thoroRes = await ghRedirect.onRequest({{
        request: new Request("https://gainhelm.com/r/thoropass_audit?source_tool=hitrust-certification-cost-calculator&cta_slot=hero_callout&subid=thoro_hitrust_hero"),
        env: {{}},
        params: {{ partner: "thoropass_audit" }}
      }});
      if (thoroRes.status !== 302) process.exit(30);
      const thoroLoc = new URL(thoroRes.headers.get("Location"));
      if (thoroLoc.hostname !== "xendoo.pxf.io") process.exit(31);
      if (thoroLoc.searchParams.get("subId1") !== "thoro_hitrust_hero") process.exit(32);

      process.exit(0);
    }})().catch(err => {{ console.error(err); process.exit(99); }});
    """
    proc = subprocess.run(["node", "-e", node_script], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"Node GainHelm edge redirect test failed (exit {proc.returncode}): {proc.stderr}"

    gh_lead_js = generate_edge_lead_capture_function("gainhelm")
    assert "const stripeOffer = await resolveEdgeStripeCheckoutOffer(" in gh_lead_js
    assert "live_destination_url: liveDestinationUrl" in gh_lead_js
    assert "lookupEdgeLeadRecord" in gh_lead_js
    assert "statutory_trend_timeseries: statutoryTrendTimeseries" in gh_lead_js
    assert "GH-400" in gh_lead_js

    gh_lead_file = gh_repo / "functions" / "api" / "lead-capture.js"
    gh_lead_file.parent.mkdir(parents=True, exist_ok=True)
    gh_lead_file.write_text(gh_lead_js, encoding="utf-8")

    lead_node_script = f"""
    (async () => {{
      const ghLead = await import({json.dumps(gh_lead_file.as_uri())});
      const fulfillRes = await ghLead.onRequestGet({{
        request: new Request("https://gainhelm.com/api/lead-capture?fulfill=1&lead_id=lead_test_gh_999&sku=gh_soc2_cmmc_audit_workpapers&tool_slug=soc-2-audit-cost-calculator&amount=62000&state=CA&synthetic_test=1"),
        env: {{}}
      }});
      if (fulfillRes.status !== 200) process.exit(40);
      const data = await fulfillRes.json();
      if (data.status !== "toolkit_fulfilled") process.exit(41);
      if (!Array.isArray(data.reconciliation_schedule) || data.reconciliation_schedule.length !== 4) process.exit(42);
      if (!Array.isArray(data.sensitivity_matrix) || data.sensitivity_matrix.length !== 3) process.exit(43);
      if (!Array.isArray(data.statutory_trend_timeseries) || data.statutory_trend_timeseries.length !== 3) process.exit(44);
      if (!Array.isArray(data.deliverables) || data.deliverables.length !== 4) process.exit(45);
      if (!data.playbook_url || !data.custom_parameter_ledger) process.exit(46);
      const tableCount = String(data.html_report || "").split("<table").length - 1;
      if (tableCount < 3 || String(data.html_report || "").length < 4500) process.exit(47);
      const csvLines = String(data.csv_content || "").trim().split("\\n");
      if (csvLines.length !== 8) process.exit(48);
      process.exit(0);
    }})().catch(err => {{ console.error(err); process.exit(98); }});
    """
    proc_lead = subprocess.run(["node", "-e", lead_node_script], capture_output=True, text=True, check=False)
    assert proc_lead.returncode == 0, f"Node GainHelm lead fulfillment test failed (exit {proc_lead.returncode}): {proc_lead.stderr}"

    tracker = PartnerTrackingEngine()
    audit = tracker.audit_readiness_and_vault_parity()
    gh_dom = audit["properties"]["gainhelm"]["compiled_dom_parity"]
    assert gh_dom["edge_upgraded_click_share_pct"] == 100.0
    assert gh_dom["pending_partner_links_in_dom"] == 0

    gh_recon = audit["non_active_reconciliation"]["properties"]["gainhelm"]
    assert gh_recon["total_canonical_partners"] == 6
    assert gh_recon["counts_by_state"]["NEWLY_APPROVED_AND_WIRED_AT_EDGE"] == 6


def test_end_to_end_six_department_handoff_chain_across_all_three_tenants(tmp_path):
    """
    Verifies the direct 6-department handoff chain:
      DISCOVERY -> MONETIZATION -> ENGINEERING -> VERIFICATION -> SYNDICATION -> DEPLOYMENT
    across all 3 canonical live tenants (profithelm, prexvo, gainhelm).
    Confirms every department validates its upstream inputs, executes its full responsibility
    for all three tenants without divergence, and emits its guaranteed output contract.
    """
    from pseofactory.supervisor import (
        CANONICAL_DEPARTMENT_CONTRACTS,
        CANONICAL_TENANTS,
        DepartmentPipelineStateMachine,
        verify_department_handoff_chain,
    )

    assert CANONICAL_TENANTS == ("profithelm", "prexvo", "gainhelm")
    assert len(CANONICAL_DEPARTMENT_CONTRACTS) == 6

    report = verify_department_handoff_chain(
        workspace_root="/home/ubuntuadmin/projects",
        property_ids=["profithelm", "prexvo", "gainhelm"],
        persist=False,
        heal_markers=False,
        strict_current_engine_hash=False,
    )
    assert report["overall_status"] == "PASS", f"Handoff chain failed: {report.get('failures')}"
    assert report["stages_total"] == 6
    assert report["stages_passed"] == 6
    assert report["failing_stages_count"] == 0
    assert report["target_tenants"] == ["profithelm", "prexvo", "gainhelm"]
    assert report["discovered_tenants"] == ["profithelm", "prexvo", "gainhelm"]

    expected_order = (
        "DISCOVERY",
        "MONETIZATION",
        "ENGINEERING",
        "VERIFICATION",
        "SYNDICATION",
        "DEPLOYMENT",
    )
    for idx, stage_name in enumerate(expected_order, start=1):
        s_rep = report["stages"][stage_name]
        assert s_rep["order"] == idx
        assert s_rep["status"] == "PASS", f"Stage {stage_name} failed: {s_rep.get('errors')}"
        assert s_rep["inputs_validated"] is True
        assert s_rep["outputs_validated"] is True
        assert s_rep["missing_inputs"] == []
        assert s_rep["missing_outputs"] == []
        per_tenant = s_rep["summary"].get("per_tenant") or {}
        for pid in CANONICAL_TENANTS:
            assert pid in per_tenant, f"Stage {stage_name} missing tenant summary for {pid}"
            assert per_tenant[pid]["status"] == "PASS", (
                f"Stage {stage_name} tenant {pid} failed: {per_tenant[pid]}"
            )

    # Verify isolated state persistence via DepartmentPipelineStateMachine
    state_file = tmp_path / "department_pipeline.json"
    sm = DepartmentPipelineStateMachine(state_path=state_file)
    for stage_name in expected_order:
        sm.record_stage(stage_name, "PASS", report["stages"][stage_name]["summary"])
    persisted = sm.finalize_and_persist(cycle_id="test_e2e_handoff_chain", overall_status="PASS")
    assert state_file.is_file()
    assert persisted["overall_status"] == "PASS"
    assert persisted["tenants_managed"] == ["profithelm", "prexvo", "gainhelm"]
    assert set(persisted["contracts"].keys()) == set(expected_order)


def test_multi_tenant_engine_hash_latch_and_isolated_builder_offline_jev(tmp_path):
    """
    Verifies the GitOps multi-tenant truth guarantees:
    1. detect_engine_drift blocks reporting ALIGNED whenever any canonical tenant
       (profithelm-platform, prexvo, gainhelm) has a stale substrate_lock.json or
       uncommitted dist/ changes, and only reports ALIGNED once all 3 tenants match expected_hash.
    2. SubprocessPropertyAdapter.build_asset sets PROFITHELM_OFFLINE_JEV=1 and fast-paths single-tool
       rebuilds via build_tool_page instead of falling back to full build_all() without offline JEV.
    3. ShipperQueue.reconcile_stale_events and SyndicationWALQueue.reconcile_stale_events reconcile
       stale DRY_RUN and STAGED events when superseded by a newer COMPLETED release/distribution.
    """
    import json
    import subprocess
    import pseofactory.drift as drift_mod
    from pseofactory.drift import (
        compute_engine_hash,
        detect_engine_drift,
        record_engine_hash,
    )
    from pseofactory.maintenance import SubprocessPropertyAdapter
    from pseofactory.gitops import ShipperQueue
    from pseofactory.distributor import SyndicationWALQueue

    # 1. ShipperQueue and SyndicationWALQueue reconcile stale DRY_RUN and STAGED events when superseded by COMPLETED
    q_dir = tmp_path / "queues"
    q_dir.mkdir(parents=True, exist_ok=True)
    sq = ShipperQueue(property_id="profithelm", queues_dir=q_dir)
    e_dry = sq.enqueue({"run_id": "r1", "property_id": "profithelm"})
    sq.complete_event(e_dry["event_id"], status="DRY_RUN")
    e_live = sq.enqueue({"run_id": "r2", "property_id": "profithelm"})
    sq.complete_event(e_live["event_id"], status="COMPLETED")
    assert sq.reconcile_stale_events() == 1
    sq_records = [json.loads(line) for line in sq.queue_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert all(r["status"] == "COMPLETED" for r in sq_records)

    dq = SyndicationWALQueue(property_id="profithelm", queues_dir=q_dir)
    d_staged = dq.enqueue({"run_id": "d1", "property_id": "profithelm"})
    dq.complete_event(d_staged["event_id"], status="STAGED")
    d_live = dq.enqueue({"run_id": "d2", "property_id": "profithelm"})
    dq.complete_event(d_live["event_id"], status="COMPLETED")
    assert dq.reconcile_stale_events() == 1
    dq_records = [json.loads(line) for line in dq.queue_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert all(r["status"] == "COMPLETED" for r in dq_records)

    # 2. SubprocessPropertyAdapter.build_asset sets PROFITHELM_OFFLINE_JEV=1 and fast-paths build_tool_page
    mock_repo = tmp_path / "mock_profithelm"
    pkg_dir = mock_repo / "profithelm"
    dist_dir = mock_repo / "dist"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.html").write_text("<html><body>hub</body></html>\n", encoding="utf-8")
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "builder.py").write_text(
        "import os\n"
        "from pathlib import Path\n"
        "TOOLS = [{'slug': 'section-179-calculator', 'title': 'Section 179'}]\n"
        "def build_tool_page(tool):\n"
        "    assert os.environ.get('PROFITHELM_OFFLINE_JEV') == '1', 'Missing PROFITHELM_OFFLINE_JEV=1'\n"
        "    out = Path(os.environ['FACTORY_DIST_DIR']) / 'tools' / tool['slug'] / 'index.html'\n"
        "    out.parent.mkdir(parents=True, exist_ok=True)\n"
        "    out.write_text('<html><head><title>Section 179</title></head><body><h1>Section 179</h1></body></html>', encoding='utf-8')\n"
        "def build_all(dist_dir=None):\n"
        "    raise RuntimeError('Should not fall back to full build_all when build_tool_page fast-path applies')\n",
        encoding="utf-8",
    )
    adapter = SubprocessPropertyAdapter(
        property_id="profithelm",
        brand_name="ProfitHelm",
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        dist_dir=dist_dir,
        repo_path=mock_repo,
    )
    assert adapter.build_asset("section-179-calculator") is True
    assert (dist_dir / "tools" / "section-179-calculator" / "index.html").is_file()

    # 3. Multi-tenant substrate_lock.json and git working tree alignment check before latching engine_hash.json
    ws_root = tmp_path / "workspace"
    ws_root.mkdir(parents=True, exist_ok=True)
    current_hash = compute_engine_hash()
    stale_hash = "9777a1f36438134a8ad5c2e53e84074b9debbceeab1fd2df118229a1b6afc1c4"

    for repo_name, lock_hash in (
        ("profithelm-platform", stale_hash),
        ("prexvo", current_hash),
        ("gainhelm", current_hash),
    ):
        rp = ws_root / repo_name
        rp.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", str(rp)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(rp), "config", "user.email", "test@antigravity.local"], check=True)
        subprocess.run(["git", "-C", str(rp), "config", "user.name", "Test Worker"], check=True)
        (rp / "dist").mkdir(parents=True, exist_ok=True)
        (rp / "dist" / "index.html").write_text("<html><body>ok</body></html>\n", encoding="utf-8")
        (rp / "substrate_lock.json").write_text(
            json.dumps({"property_id": repo_name, "engine_hash": lock_hash, "substrate_hash": lock_hash}),
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(rp), "add", "-A"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(rp), "commit", "-m", "initial"], check=True, capture_output=True)

    state_file = ws_root / ".agy" / "engine_hash.json"
    record_engine_hash(state_file, hash_value=current_hash)
    verify_fn = getattr(drift_mod, "verify_all_tenants_aligned_for_latch", None)
    assert verify_fn is not None
    aligned, reasons = verify_fn(
        workspace_root=ws_root,
        expected_hash=current_hash,
        require_git_clean_and_pushed=True,
    )
    assert aligned is False
    assert any("profithelm: substrate_lock.json hash" in r for r in reasons)

    drift_res = detect_engine_drift(state_file=state_file, verify_tenants=True, workspace_root=ws_root)
    assert drift_res["drifted"] is True
    assert drift_res["status"] == "DRIFT"
    assert drift_res["reason"] == "TENANT_SUBSTRATE_OR_GIT_DRIFT"

    ph_repo = ws_root / "profithelm-platform"
    (ph_repo / "substrate_lock.json").write_text(
        json.dumps({"property_id": "profithelm", "engine_hash": current_hash, "substrate_hash": current_hash}),
        encoding="utf-8",
    )
    aligned_dirty, reasons_dirty = verify_fn(
        workspace_root=ws_root,
        expected_hash=current_hash,
        require_git_clean_and_pushed=True,
    )
    assert aligned_dirty is False
    assert any("profithelm: uncommitted changes in dist/ or substrate_lock.json" in r for r in reasons_dirty)

    subprocess.run(["git", "-C", str(ph_repo), "add", "substrate_lock.json"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(ph_repo), "commit", "-m", "align substrate lock"], check=True, capture_output=True)
    aligned_clean, reasons_clean = verify_fn(
        workspace_root=ws_root,
        expected_hash=current_hash,
        require_git_clean_and_pushed=True,
    )
    assert aligned_clean is True
    assert reasons_clean == []
    drift_clean = detect_engine_drift(state_file=state_file, verify_tenants=True, workspace_root=ws_root)
    assert drift_clean["drifted"] is False
    assert drift_clean["status"] == "ALIGNED"




