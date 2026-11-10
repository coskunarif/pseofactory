import os
from pathlib import Path

from pseofactory.action_bus import HumanActionBus
from pseofactory.contracts import assert_youtube_transcript
from pseofactory.distributor import _generate_youtube_transcript
from pseofactory.gitops import (
    TenantFactoryLockGuard,
    isolated_worktree,
    reconcile_workspace_tracking_state,
)
from pseofactory.indexing.milestones import MilestoneTracker
from pseofactory.trends.db import TrendHistoryDB


def test_assert_youtube_transcript_lienbond_brand():
    transcript_pack = _generate_youtube_transcript(
        "contractor-license-bond-cost-calculator",
        property_id="lienbond",
    )
    assert assert_youtube_transcript(transcript_pack, property_id="lienbond") is True
    assert "LienBond" in transcript_pack["full_text"]


def test_reconcile_workspace_tracking_state_preserves_lienbond_queues(tmp_path: Path):
    queues_dir = tmp_path / ".agy" / "queues"
    queues_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = tmp_path / ".agy" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    lb_queue = queues_dir / "lienbond_release_queue.jsonl"
    lb_queue.write_text('{"event_id": "evt1", "status": "COMPLETED"}\n', encoding="utf-8")

    lb_dist_queue = queues_dir / "lienbond_distribution_queue.jsonl"
    lb_dist_queue.write_text('{"event_id": "evt2", "status": "COMPLETED"}\n', encoding="utf-8")

    reconcile_workspace_tracking_state(
        runs_dir=runs_dir,
        queues_dir=queues_dir,
        ledger_path=tmp_path / ".agy" / "ledger.json",
        tenant_repos=[],
    )

    assert lb_queue.is_file(), "reconcile_workspace_tracking_state must not delete lienbond_release_queue.jsonl"
    assert lb_dist_queue.is_file(), "reconcile_workspace_tracking_state must not delete lienbond_distribution_queue.jsonl"


def test_trend_history_db_supports_lienbond_property(tmp_path: Path):
    db_path = tmp_path / "trends.db"
    db = TrendHistoryDB(db_path=str(db_path))

    matrix = db.compile_statutory_economic_matrix("lienbond")
    assert matrix["property_id"] == "lienbond"
    assert "40 U.S.C. 3131" in matrix["statutory_authority"]

    db.upsert_statutory_economic_timeseries([
        {
            "series_id": "test_miller_act_threshold",
            "property_id": "lienbond",
            "jurisdiction": "US-FEDERAL",
            "statutory_citation": "40 U.S.C. 3131",
            "metric_key": "miller_act_federal_surety_threshold_usd",
            "metric_label": "Miller Act Threshold",
            "effective_year": 2026,
            "metric_value": 150000.0,
            "unit": "USD",
            "source_agency": "GSA / FAR",
        }
    ])
    rows = db.get_statutory_economic_timeseries(property_id="lienbond")
    assert any(r.series_id == "test_miller_act_threshold" for r in rows)


def test_tenant_factory_lock_guard_exports_env_marker(tmp_path: Path, monkeypatch):
    env_key = "PSEUFACTORY_HOLDS_LIENBOND_LOCK"
    monkeypatch.setenv("PSEUFACTORY_LOCK_DIR", str(tmp_path))
    monkeypatch.delenv(env_key, raising=False)
    with TenantFactoryLockGuard("lienbond", timeout=5.0):
        assert os.environ.get(env_key) == "1"
    assert os.environ.get(env_key) is None


def test_isolated_worktree_and_lock_guard_rollback_on_exception(tmp_path: Path, monkeypatch):
    import subprocess
    repo_dir = tmp_path / "mock_tenant"
    dist_dir = repo_dir / "dist"
    dist_dir.mkdir(parents=True)
    index_f = dist_dir / "index.html"
    index_f.write_text("<html>clean</html>", encoding="utf-8")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_dir, check=True, capture_output=True)

    with isolated_worktree(repo_dir) as wt_path:
        assert wt_path != repo_dir
        assert (wt_path / "dist" / "index.html").read_text(encoding="utf-8") == "<html>clean</html>"
        (wt_path / "dist" / "index.html").write_text("<html>worktree-edit</html>", encoding="utf-8")
        assert index_f.read_text(encoding="utf-8") == "<html>clean</html>"
    assert not wt_path.exists()

    monkeypatch.setenv("PSEUFACTORY_LOCK_DIR", str(tmp_path))
    try:
        with TenantFactoryLockGuard("lienbond", repo_path=repo_dir, timeout=5.0):
            index_f.write_text("<html>partial-corrupt-write</html>", encoding="utf-8")
            (dist_dir / "orphan.html").write_text("orphan", encoding="utf-8")
            raise RuntimeError("simulated mid-build failure")
    except RuntimeError:
        pass

    assert index_f.read_text(encoding="utf-8") == "<html>clean</html>"
    assert not (dist_dir / "orphan.html").exists()


def test_milestone_tracker_and_action_bus_support_lienbond(tmp_path: Path):
    tracker = MilestoneTracker(tenant="lienbond")
    assert tracker.tenant == "lienbond"

    bus = HumanActionBus(bus_path=tmp_path / "actions.json")
    item = bus.route_high_value_qualified_lead(
        property_id="lienbond",
        tool_slug="contractor-license-bond-cost-calculator",
        lead_id="lead_lienbond_test123",
        email="contractor@example.com",
        calculated_amount=250000.0,
        state="CA",
        capital_band="250k_to_1m",
        partner_sharing_consent=True,
    )
    assert item.property_id == "lienbond"


def test_recompute_tenant_lock_enforces_visual_primitive_and_quick_unlock_parity_and_gitignore(tmp_path: Path):
    import json
    import subprocess
    from pseofactory.drift import compute_dist_lock_metrics
    from pseofactory.gitops import recompute_and_amend_tenant_lock_and_ledger

    repo_dir = tmp_path / "mock_profithelm"
    tool_dir = repo_dir / "dist" / "tools" / "irs-2027-tax-brackets"
    tool_dir.mkdir(parents=True)

    (repo_dir / ".pseofactory.json").write_text('{"property_id": "profithelm"}\n', encoding="utf-8")
    (repo_dir / "substrate_lock.json").write_text('{"property_id": "profithelm"}\n', encoding="utf-8")
    (repo_dir / ".gitignore").write_text("__pycache__/\n.agy/\n", encoding="utf-8")

    stale_html = (
        '<!DOCTYPE html><html><head><style id="pseo-visual-primitives">/* stale */</style></head><body>'
        '<div id="partner-quote-intake-step" data-property-id="profithelm" data-tool-slug="irs-2027-tax-brackets" data-calculated-amount="125000"></div>'
        '<div id="calc-result-quick-unlock-bar" class="calc-result-quick-unlock-bar" data-contextual-v2="1">'
        '<div>Get Your 2027 2027 Federal &amp; State + Federal Tax Bracket &amp; W-4 Paycheck Plan</div>'
        '<form id="inline-worksheet-capture-form"><button id="btn-inline-worksheet-submit" style="white-space: nowrap;">Send</button></form>'
        '<div><a id="btn-calc-result-quick-unlock" style="white-space: nowrap;">Unlock</a></div>'
        "</div></body></html>"
    )
    index_f = tool_dir / "index.html"
    index_f.write_text(stale_html, encoding="utf-8")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_dir, check=True, capture_output=True)

    ok = recompute_and_amend_tenant_lock_and_ledger(repo_dir, property_id="profithelm", amend=False)
    assert ok is True

    gi_txt = (repo_dir / ".gitignore").read_text(encoding="utf-8")
    assert "syndication/" in gi_txt
    assert "dist/syndication/" in gi_txt

    healed_html = index_f.read_text(encoding="utf-8")
    assert "2027 2027 " not in healed_html
    assert "#btn-calc-result-quick-unlock," in healed_html
    assert 'id="btn-calc-result-quick-unlock"' in healed_html
    assert "white-space: normal; text-align: center; max-width: 100%; box-sizing: border-box;" in healed_html

    lock_data = json.loads((repo_dir / "substrate_lock.json").read_text(encoding="utf-8"))
    actual_fp, _ = compute_dist_lock_metrics(repo_dir / "dist")
    assert lock_data["dist_fingerprint"] == actual_fp


def test_quick_unlock_balanced_div_replacement_never_clobbers_downstream_forms():
    from pseofactory.visual_primitives import normalize_html_visual_primitives

    # Bar without inner </form>, followed by downstream #partner-quote-intake-form
    raw_html = (
        '<!DOCTYPE html><html><head><style id="pseo-visual-primitives">/* stale */</style></head><body>'
        '<div id="partner-quote-intake-step" data-property-id="prexvo" data-tool-slug="grad-plus-borrowing-cap-calculator" data-calculated-amount="65000">'
        '<div id="calc-result-quick-unlock-bar" class="calc-result-quick-unlock-bar" data-contextual-v2="1">'
        '<div class="nested-header"><div>Legacy form-less quick bar with RAP vs. IBR vs. Refinance amortization schedule</div></div>'
        "</div>"
        '<div class="important-downstream-section"><form id="partner-quote-intake-form"><button type="submit">Get Quote</button></form></div>'
        "</div></body></html>"
    )
    healed, _ = normalize_html_visual_primitives(raw_html)
    assert "important-downstream-section" in healed
    assert 'id="partner-quote-intake-form"' in healed
    assert "RAP vs. IBR vs. Refinance amortization schedule" not in healed
    assert "RAP vs. IBR vs. Standard amortization schedule" in healed


def test_write_substrate_lock_preserves_lienbond_fields_and_syncs_ledgers_and_freshness(tmp_path: Path):
    import json
    from pseofactory.drift import write_substrate_lock

    repo_dir = tmp_path / "lienbond"
    custom_dist = tmp_path / "custom_dist" / "tools" / "contractor-license-bond-cost-calculator"
    custom_dist.mkdir(parents=True)
    repo_dir.mkdir(parents=True)

    (custom_dist / "index.html").write_text(
        '<!DOCTYPE html><html><head><style id="pseo-visual-primitives">/* stale */</style></head><body><h1>Bond</h1></body></html>',
        encoding="utf-8",
    )
    (repo_dir / "freshness_audit_report.json").write_text(
        json.dumps({"merkle_drift": {"drifted": True, "substrate_hash": "old"}, "substrate_hash": "old"}),
        encoding="utf-8",
    )
    agy_dir = repo_dir / ".agy"
    agy_dir.mkdir(parents=True)
    (agy_dir / "engine_hash.json").write_text('{"engine_hash": "old"}\n', encoding="utf-8")
    (agy_dir / "asset_ledger.json").write_text("{}\n", encoding="utf-8")

    payload = write_substrate_lock(
        repo_dir,
        property_id="lienbond",
        expected_hash="deadbeef1234",
        dist_dir=tmp_path / "custom_dist",
        sync_ledgers=True,
    )
    assert payload["property_id"] == "lienbond"
    assert payload["tenant"] == "lienbond"
    assert payload["engine_sha256"] == "deadbeef1234"
    assert payload["engine_hash"] == "deadbeef1234"
    assert payload["substrate_hash"] == "deadbeef1234"
    assert payload["total_assets"] == 1

    freshness = json.loads((repo_dir / "freshness_audit_report.json").read_text(encoding="utf-8"))
    assert freshness["substrate_hash"] == "deadbeef1234"
    assert freshness["merkle_drift"]["substrate_hash"] == "deadbeef1234"
    assert freshness["merkle_drift"]["drifted"] is False

    eh_data = json.loads((agy_dir / "engine_hash.json").read_text(encoding="utf-8"))
    assert eh_data["engine_hash"] == "deadbeef1234"

    al_data = json.loads((agy_dir / "asset_ledger.json").read_text(encoding="utf-8"))
    assert "tools/contractor-license-bond-cost-calculator/index.html" in al_data["assets"]



