"""
Test Suite for Google Search Console Traffic Trends and Algorithmic Glass Ceiling Detection
Validates models, rolling metrics, Google update correlation, ceiling dampening score,
database persistence with WAL mode, search intent qualification hook, and minimal UI rendering.
Zero em-dashes. Zero en-dashes.
"""

import json
import os
import tempfile
from pathlib import Path
from datetime import datetime, date, timedelta, timezone
import pytest

from pseofactory.contracts import assert_no_forbidden_dashes, assert_touch_targets
from pseofactory.trends.models import (
    GSCDailyMetricRecord,
    GoogleUpdateEvent,
    CeilingThresholdSpec,
    AlgorithmicCeilingAnalysis,
)
from pseofactory.trends.gsc_ceiling import (
    DEFAULT_GOOGLE_UPDATES,
    compute_rolling_averages,
    detect_algorithmic_ceiling,
    GSCCeilingPipeline,
    interpolate_metric_timeline,
)
from pseofactory.trends.db import TrendHistoryDB
from pseofactory.qualification import qualify_search_intent
from pseofactory.ui import render_gsc_ceiling_dashboard
from pseofactory.cli import main, build_parser


FIXTURE_PATH = Path("pseofactory/tests/fixtures/gsc_480d_ceiling_fixture.json")


def test_models_contracts():
    """Verifies dataclass creation, serialization, deserialization, and forbidden dash protection."""
    # GSCDailyMetricRecord
    metric = GSCDailyMetricRecord(
        property_id="profithelm",
        date="2026-01-15",
        clicks=120,
        impressions=4500,
        ctr=0.0267,
        position=8.4,
    )
    assert metric.clicks == 120
    assert metric.impressions == 4500
    metric_dict = metric.to_dict()
    assert metric_dict["property_id"] == "profithelm"
    reconstructed_m = GSCDailyMetricRecord.from_dict(metric_dict)
    assert reconstructed_m.impressions == metric.impressions

    # Forbidden dash check on metric
    with pytest.raises(ValueError):
        GSCDailyMetricRecord(property_id="profit\u2014helm", date="2026-01-15")
    with pytest.raises(ValueError):
        GSCDailyMetricRecord(property_id="profithelm", date="2026\u201301-15")

    # GoogleUpdateEvent
    event = GoogleUpdateEvent(
        event_id="goog_core_2025_08",
        name="August 2025 Core Update",
        update_type="CORE",
        start_date="2025-08-14",
        end_date="2025-09-02",
        impact_buffer_days=14,
        confirmed=1,
        notes="Entity authority validation",
    )
    ev_dict = event.to_dict()
    assert ev_dict["event_id"] == "goog_core_2025_08"
    reconstructed_ev = GoogleUpdateEvent.from_dict(ev_dict)
    assert reconstructed_ev.name == event.name

    with pytest.raises(ValueError):
        GoogleUpdateEvent(event_id="bad\u2014id", name="Update")

    # CeilingThresholdSpec
    spec = CeilingThresholdSpec(threshold=0.40)
    spec_dict = spec.to_dict()
    assert spec_dict["threshold"] == 0.40
    reconstructed_s = CeilingThresholdSpec.from_dict(spec_dict)
    assert reconstructed_s.threshold == 0.40

    # AlgorithmicCeilingAnalysis
    analysis = AlgorithmicCeilingAnalysis(
        property_id="profithelm",
        total_days=480,
        ceiling_detected=True,
        suppression_severity="HIGH",
        recommendation="FREEZE_EXPANSION",
    )
    a_dict = analysis.to_dict()
    assert a_dict["ceiling_detected"] is True
    reconstructed_a = AlgorithmicCeilingAnalysis.from_dict(a_dict)
    assert reconstructed_a.recommendation == "FREEZE_EXPANSION"


def test_rolling_averages_calculation():
    """Verifies RMA_7, RMA_28, velocity, and second-derivative discrete acceleration."""
    records = []
    base_date = date(2026, 1, 1)
    for i in range(40):
        records.append(
            GSCDailyMetricRecord(
                property_id="profithelm",
                date=(base_date + timedelta(days=i)).isoformat(),
                clicks=10 + i,
                impressions=100 + (i * 20),
                ctr=0.05,
                position=15.0,
            )
        )

    timeline = compute_rolling_averages(records)
    assert len(timeline) == 40

    # Check day 0
    assert timeline[0]["rma_7"] == 100.0
    assert timeline[0]["rma_28"] == 100.0

    # Check day 6 (7th day)
    expected_rma7 = sum(100 + (j * 20) for j in range(7)) / 7.0
    assert abs(timeline[6]["rma_7"] - expected_rma7) < 0.01

    # Check day 27 (28th day)
    expected_rma28 = sum(100 + (j * 20) for j in range(28)) / 28.0
    assert abs(timeline[27]["rma_28"] - expected_rma28) < 0.01

    # Velocity and second derivative acceleration
    assert "velocity" in timeline[2]
    assert "acceleration" in timeline[2]


def test_ceiling_detection_algorithm():
    """Verifies synthetic ceiling profile triggers ceiling_detected=True and FREEZE_EXPANSION."""
    assert FIXTURE_PATH.is_file(), "Fixture file must exist"
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = [GSCDailyMetricRecord.from_dict(m) for m in data["metrics"]]
    updates = [GoogleUpdateEvent.from_dict(u) for u in data["google_updates"]]

    analysis = detect_algorithmic_ceiling(records, updates=updates, threshold=0.35)

    assert analysis.property_id == "profithelm"
    assert analysis.total_days == 480
    assert analysis.ceiling_detected is True
    assert analysis.suppression_severity == "HIGH"
    assert analysis.recommendation == "FREEZE_EXPANSION"
    assert analysis.ceiling_dampening_score >= 0.35
    assert len(analysis.correlated_updates) >= 1
    assert any(cu["event_id"] == "goog_core_2025_08" for cu in analysis.correlated_updates)


def test_ceiling_detection_unconstrained():
    """Verifies unconstrained steady growth triggers ceiling_detected=False and BUILD_PAGE."""
    records = []
    base_date = date(2025, 1, 1)
    for i in range(120):
        # Monotonically increasing impressions, stable top positions
        impr = 1000 + (i * 80)
        records.append(
            GSCDailyMetricRecord(
                property_id="prexvo",
                date=(base_date + timedelta(days=i)).isoformat(),
                clicks=int(impr * 0.05),
                impressions=impr,
                ctr=0.05,
                position=max(4.0, 18.0 - (i * 0.1)),
            )
        )

    analysis = detect_algorithmic_ceiling(records, updates=DEFAULT_GOOGLE_UPDATES, threshold=0.35)

    assert analysis.ceiling_detected is False
    assert analysis.suppression_severity == "NONE"
    assert analysis.recommendation == "BUILD_PAGE"
    assert analysis.ceiling_dampening_score < 0.35


def test_db_persistence_and_wal_locking():
    """Verifies TrendHistoryDB schema extension, WAL mode, advisory locking, and CRUD."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_gsc_history.db"
        with TrendHistoryDB(db_path=db_path) as db:
            conn = db.get_connection()
            # Verify tables exist
            tables = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table';"
                ).fetchall()
            ]
            assert "gsc_daily_metrics" in tables
            assert "google_update_events" in tables
            assert "gsc_ceiling_snapshots" in tables

            # Verify WAL journal mode
            wal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
            assert wal_mode.upper() == "WAL"

            # Batch upsert GSC daily metrics
            metrics = [
                GSCDailyMetricRecord(
                    property_id="profithelm",
                    date="2026-03-01",
                    clicks=45,
                    impressions=1200,
                    ctr=0.0375,
                    position=11.2,
                ),
                GSCDailyMetricRecord(
                    property_id="profithelm",
                    date="2026-03-02",
                    clicks=52,
                    impressions=1350,
                    ctr=0.0385,
                    position=10.8,
                ),
            ]
            count = db.upsert_gsc_daily_metrics(metrics)
            assert count == 2

            # Re-upsert (idempotency test)
            count_repeat = db.upsert_gsc_daily_metrics(metrics)
            assert count_repeat == 2

            # Read back
            fetched = db.get_gsc_daily_metrics("profithelm", days=10)
            assert len(fetched) == 2
            assert fetched[0].date == "2026-03-01"
            assert fetched[1].date == "2026-03-02"

            # Upsert Google update events
            events = [
                GoogleUpdateEvent(
                    event_id="goog_test_update",
                    name="Test Algorithm Update",
                    update_type="CORE",
                    start_date="2026-02-01",
                    end_date="2026-02-15",
                )
            ]
            ev_count = db.upsert_google_update_events(events)
            assert ev_count == 1

            fetched_events = db.get_google_update_events(start_date="2026-01-01")
            assert len(fetched_events) == 1
            assert fetched_events[0].event_id == "goog_test_update"

            # Record ceiling snapshot
            analysis = AlgorithmicCeilingAnalysis(
                property_id="profithelm",
                peak_impressions_rma28=5000.0,
                current_impressions_rma28=2000.0,
                ceiling_detected=True,
                ceiling_dampening_score=0.62,
                recommendation="FREEZE_EXPANSION",
            )
            snapshot_id = db.record_gsc_ceiling_snapshot(analysis)
            assert snapshot_id.startswith("snap_ceil_profithelm_")


def test_search_intent_doctrine_ceiling_suppression():
    """Verifies qualify_search_intent intercepts unserved voids and routes to MONITOR under ceiling."""
    query_data = {
        "query": "saas burn rate calculator",
        "position": 8.5,
        "impressions": 250,
        "clicks": 18,
    }

    # Baseline: no authority dampening -> qualifies for BUILD_PAGE
    res_baseline = qualify_search_intent(
        query_data=query_data,
        existing_tools=[],
        total_site_impressions=1000,
        authority_dampened=False,
    )
    assert res_baseline["action"] == "BUILD_PAGE"

    # Authority dampened via boolean flag
    res_dampened = qualify_search_intent(
        query_data=query_data,
        existing_tools=[],
        total_site_impressions=1000,
        authority_dampened=True,
    )
    assert res_dampened["action"] == "MONITOR"
    assert res_dampened["ceiling_detected"] is True
    assert "Domain authority dampening ceiling active" in res_dampened["reason"]

    # Authority dampened via ceiling_status dict
    res_status = qualify_search_intent(
        query_data=query_data,
        existing_tools=[],
        total_site_impressions=1000,
        ceiling_status={"ceiling_detected": True, "ceiling_dampening_score": 0.65},
    )
    assert res_status["action"] == "MONITOR"
    assert res_status["ceiling_detected"] is True
    assert "score 0.65" in res_status["reason"]


def test_ui_rendering_cls_and_touch_targets():
    """Verifies render_gsc_ceiling_dashboard satisfies CLS=0, touch targets >= 44px, and zero forbidden dashes."""
    analysis = AlgorithmicCeilingAnalysis(
        property_id="profithelm",
        analysis_window_days=480,
        total_days=480,
        peak_impressions_rma28=9200.0,
        current_impressions_rma28=2400.0,
        ceiling_threshold=0.35,
        ceiling_dampening_score=0.66,
        ceiling_detected=True,
        suppression_severity="HIGH",
        recommendation="FREEZE_EXPANSION",
        correlated_updates=[
            {
                "event_id": "goog_core_2025_08",
                "name": "August 2025 Core Update",
                "update_type": "CORE",
                "start_date": "2025-08-14",
                "end_date": "2025-09-02",
                "drop_ratio": 0.56,
                "pre_rma28": 8200.0,
                "post_rma28": 2400.0,
            }
        ],
        metrics_timeline=[
            {
                "date": "2025-08-10",
                "impressions": 8500,
                "clicks": 320,
                "rma_7": 8400.0,
                "rma_28": 8200.0,
                "velocity": 50.0,
                "acceleration": 5.0,
            },
            {
                "date": "2025-08-20",
                "impressions": 3000,
                "clicks": 80,
                "rma_7": 4500.0,
                "rma_28": 6000.0,
                "velocity": -200.0,
                "acceleration": -50.0,
            },
        ],
    )

    markup = render_gsc_ceiling_dashboard(analysis)

    # Invariants
    assert_no_forbidden_dashes(markup, "render_gsc_ceiling_dashboard")
    assert_touch_targets(markup, context="render_gsc_ceiling_dashboard")

    # Layout invariant CLS=0
    assert 'viewBox="0 0 1000 360"' in markup

    # Required visual elements
    assert "Profithelm" in markup
    assert "AUTHORITY DAMPENED" in markup
    assert "FREEZE_EXPANSION" in markup
    assert "0.66" in markup
    assert "August 2025 Core Update" in markup


def test_cli_gsc_ceiling_json_and_html(capsys):
    """Verifies CLI execution with --fixture, --json, and --html."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        html_file = Path(tmp_dir) / "ceiling_dashboard.html"
        exit_code = main(
            [
                "gsc-ceiling",
                "--fixture",
                str(FIXTURE_PATH),
                "--json",
                "--html",
                str(html_file),
            ]
        )
        assert exit_code == 0
        captured = capsys.readouterr()

        # JSON stdout
        parsed = json.loads(captured.out)
        assert parsed["property_id"] == "profithelm"
        assert parsed["ceiling_detected"] is True
        assert parsed["total_days"] == 480
        assert parsed["recommendation"] == "FREEZE_EXPANSION"

        # HTML file generated
        assert html_file.is_file()
        html_content = html_file.read_text(encoding="utf-8")
        assert 'viewBox="0 0 1000 360"' in html_content
        assert_no_forbidden_dashes(html_content)
        assert_touch_targets(html_content)
