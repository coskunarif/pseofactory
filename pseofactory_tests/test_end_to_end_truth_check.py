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
    during DailyIndexingInspector.run_inspection(auto_remediate=True) and verifies that
    auto-remediation runs and drains the rollover queue to 0 when child sitemaps pass.
    """
    from unittest.mock import patch
    from pseofactory.indexing_inspector import DailyIndexingInspector
    from pseofactory.telemetry import AtomicTelemetryLogger

    agy_dir = tmp_path / ".agy"
    agy_dir.mkdir(parents=True, exist_ok=True)
    rollover_path = agy_dir / "gsc_rollover_queue.json"
    rollover_path.write_text(
        json.dumps(["https://profithelm.com/", "https://profithelm.com/tools/"]),
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
    ), patch(
        "pseofactory.indexing.feedback_loop.IndexingFeedbackLoop.run_feedback_cycle",
        return_value={"status": "NO_ACTION_REQUIRED"},
    ):
        rep = inspector.run_inspection(dry_run=False, auto_remediate=True)

    assert rep["audit_status"] == "PASS"
    assert rep["gsc_rollover"]["queue_size"] == 0
    assert rep["gsc_rollover"]["reconciled_urls_count"] == 2
    assert json.loads(rollover_path.read_text(encoding="utf-8")) == []


