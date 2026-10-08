"""
Tests for pseofactory trend-intake and trend-monitor CLI subcommands.
Zero em-dashes. Zero en-dashes.
"""

import json
from unittest.mock import patch

from pseofactory.cli import main
from pseofactory.trends.models import FeedSpike


def test_cli_trend_intake_with_fixture(tmp_path, capsys):
    """Verifies pseofactory trend-intake with a JSON fixture file."""
    fixture_data = {
        "records": [
            {
                "id": "spike-fixture-01",
                "query": "form 8829 home office deduction calculator 2026",
                "source": "google_suggest",
                "detected_at": "2026-10-08T07:30:00Z",
                "sample_count": 1420,
                "velocity": 48.0,
                "acceleration": 14.5,
                "z_score": 3.8,
                "baseline_mean": 6.2,
                "baseline_std": 1.8,
                "treg_mock": {
                    "search_volume": 3600,
                    "cpc_usd": 4.80,
                    "competition_index": 0.35,
                    "keyword_difficulty": 18.0,
                    "position_zero_vacant": True,
                },
                "jev_mock": {
                    "jev_score": 1.85,
                    "durable_prob": 0.94,
                },
            },
            {
                "id": "spike-fixture-02",
                "query": "zendaya oscars dress designer 2026",
                "source": "google_suggest",
                "detected_at": "2026-10-08T06:15:00Z",
                "sample_count": 8420,
                "velocity": 142.5,
                "acceleration": -45.2,
                "z_score": 5.4,
                "baseline_mean": 12.0,
                "baseline_std": 3.1,
            },
        ]
    }

    fix_file = tmp_path / "fixtures.json"
    fix_file.write_text(json.dumps(fixture_data), encoding="utf-8")
    sink_file = tmp_path / "void_out.jsonl"

    exit_code = main([
        "trend-intake",
        "--fixture", str(fix_file),
        "--sink", str(sink_file),
        "--json",
    ])
    assert exit_code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["total_spikes"] == 2
    assert payload["filtered_noise_count"] == 1
    assert len(payload["approved_build"]) == 1
    assert payload["approved_build"][0]["query"] == "form 8829 home office deduction calculator 2026"
    assert sink_file.exists()


def test_cli_trend_intake_help(capsys):
    """Verifies trend-intake --help displays command description."""
    try:
        main(["trend-intake", "--help"])
    except SystemExit as e:
        assert e.code == 0

    captured = capsys.readouterr()
    assert "trend-intake" in captured.out
    assert "--fixture" in captured.out
    assert "--sink" in captured.out


def test_cli_trend_monitor_help(capsys):
    """Verifies trend-monitor --help displays command description."""
    try:
        main(["trend-monitor", "--help"])
    except SystemExit as e:
        assert e.code == 0

    captured = capsys.readouterr()
    assert "trend-monitor" in captured.out
    assert "--seeds" in captured.out


def test_cli_trend_monitor_execution(capsys):
    """Verifies trend-monitor execution flow with mocked suggestions."""
    mock_spike = FeedSpike(
        id="mock-01",
        query="tax deduction matrix 2026",
        source="google_suggest",
        velocity=50.0,
        acceleration=10.0,
        z_score=3.0,
    )
    with patch("pseofactory.trends.collectors.MultiSourceCollector.harvest", return_value=[mock_spike]):
        exit_code = main(["trend-monitor", "--seeds", "tax deduction", "--json"])
        assert exit_code == 0

        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert "rankings" in payload
        assert len(payload["rankings"]) == 1
