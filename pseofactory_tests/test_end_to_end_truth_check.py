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

