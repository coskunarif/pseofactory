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

    # 4. Verify sync_tenant_test_isolation_guards hardens scripts/run_factory.sh and profithelm/factory.py
    guard_res = sync_tenant_test_isolation_guards(tenant_repo)
    assert guard_res["updated_files"] >= 2
    rf_after = run_factory_sh.read_text(encoding="utf-8")
    assert "--include-untracked" not in rf_after
    assert 'git -C "$PROJECT_DIR" reset -q HEAD -- dist/' in rf_after
    assert 'git -C "$PROJECT_DIR" checkout -q HEAD -- dist/' in rf_after
    assert 'export PROFITHELM_DIST_DIR="$WORKTREE_SANDBOX/dist"' in rf_after
    assert '"reset", "-q", "HEAD", "--", "dist"' in factory_py.read_text(encoding="utf-8")

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

