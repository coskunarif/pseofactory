import os
from pathlib import Path

from pseofactory.action_bus import HumanActionBus
from pseofactory.contracts import assert_youtube_transcript
from pseofactory.distributor import _generate_youtube_transcript
from pseofactory.gitops import TenantFactoryLockGuard, reconcile_workspace_tracking_state
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
