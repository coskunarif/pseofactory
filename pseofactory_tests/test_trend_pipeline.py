"""
Tests for pseofactory end-to-end trend pipeline.
Executes against the 8-record breakout spikes evaluation dataset from data_research_lead.
Asserts transient chatter rejection, treg cross-checking, cannibalization triage, Jev decision rankings,
and atomic flock persistence (HWL-1253).
Zero em-dashes. Zero en-dashes.
"""

import json
from pathlib import Path

from pseofactory.trends.pipeline import TrendPipeline, run_trend_pipeline
from pseofactory.trends.models import FeedSpike
from pseofactory.contracts import (
    assert_no_forbidden_dashes,
    assert_no_prompt_leakage,
    assert_url_safe_slug,
)


EVALUATION_RECORDS = [
    {
        "id": "spike-001",
        "query": "zendaya oscars dress designer 2026",
        "source": "google_suggest",
        "detected_at": "2026-10-08T06:15:00Z",
        "sample_count": 8420,
        "velocity": 142.5,
        "acceleration": -45.2,
        "z_score": 5.4,
        "baseline_mean": 12.0,
        "baseline_std": 3.1,
        "expected_transient_noise": True,
        "treg_mock": {
            "search_volume": 12000,
            "cpc_usd": 0.15,
            "competition_index": 0.08,
            "keyword_difficulty": 48.0,
            "position_zero_vacant": False,
        },
        "jev_mock": {
            "jev_score": 0.15,
            "durable_prob": 0.04,
            "category": "ephemeral_celebrity_gossip",
        },
        "expected_action": "REJECT",
    },
    {
        "id": "spike-002",
        "query": "hawk tuah soundboard remix generator",
        "source": "youtube_suggest",
        "detected_at": "2026-10-08T06:20:00Z",
        "sample_count": 12500,
        "velocity": 310.0,
        "acceleration": -92.0,
        "z_score": 6.8,
        "baseline_mean": 20.0,
        "baseline_std": 4.5,
        "expected_transient_noise": True,
        "treg_mock": {
            "search_volume": 4500,
            "cpc_usd": 0.05,
            "competition_index": 0.02,
            "keyword_difficulty": 18.0,
            "position_zero_vacant": False,
        },
        "jev_mock": {
            "jev_score": 0.08,
            "durable_prob": 0.02,
            "category": "viral_meme",
        },
        "expected_action": "REJECT",
    },
    {
        "id": "spike-003",
        "query": "spacex starship launch scrubbed reasons today",
        "source": "reddit_autocomplete",
        "detected_at": "2026-10-08T07:05:00Z",
        "sample_count": 4800,
        "velocity": 95.0,
        "acceleration": -18.4,
        "z_score": 4.2,
        "baseline_mean": 8.5,
        "baseline_std": 2.2,
        "expected_transient_noise": True,
        "treg_mock": {
            "search_volume": 2100,
            "cpc_usd": 0.20,
            "competition_index": 0.12,
            "keyword_difficulty": 55.0,
            "position_zero_vacant": False,
        },
        "jev_mock": {
            "jev_score": 0.35,
            "durable_prob": 0.12,
            "category": "breaking_news",
        },
        "expected_action": "REJECT",
    },
    {
        "id": "spike-004",
        "query": "super bowl halftime performer leak 2027",
        "source": "google_suggest",
        "detected_at": "2026-10-08T07:12:00Z",
        "sample_count": 3100,
        "velocity": 78.0,
        "acceleration": -5.0,
        "z_score": 3.9,
        "baseline_mean": 9.0,
        "baseline_std": 2.5,
        "expected_transient_noise": True,
        "treg_mock": {
            "search_volume": 1800,
            "cpc_usd": 0.25,
            "competition_index": 0.10,
            "keyword_difficulty": 62.0,
            "position_zero_vacant": False,
        },
        "jev_mock": {
            "jev_score": 0.22,
            "durable_prob": 0.08,
            "category": "entertainment_rumour",
        },
        "expected_action": "REJECT",
    },
    {
        "id": "spike-005",
        "query": "form 8829 home office deduction calculator 2026",
        "source": "google_suggest",
        "detected_at": "2026-10-08T07:30:00Z",
        "sample_count": 1420,
        "velocity": 48.0,
        "acceleration": 14.5,
        "z_score": 3.8,
        "baseline_mean": 6.2,
        "baseline_std": 1.8,
        "expected_transient_noise": False,
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
            "category": "statutory_calculator",
        },
        "expected_action": "BUILD_PAGE",
        "expected_asset_type": "interactive_calculator",
    },
    {
        "id": "spike-006",
        "query": "direct consolidation loan repayment estimator",
        "source": "google_suggest",
        "detected_at": "2026-10-08T07:45:00Z",
        "sample_count": 980,
        "velocity": 34.0,
        "acceleration": 8.2,
        "z_score": 3.1,
        "baseline_mean": 5.0,
        "baseline_std": 1.5,
        "expected_transient_noise": False,
        "treg_mock": {
            "search_volume": 2900,
            "cpc_usd": 6.20,
            "competition_index": 0.45,
            "keyword_difficulty": 22.0,
            "position_zero_vacant": False,
        },
        "jev_mock": {
            "jev_score": 1.75,
            "durable_prob": 0.90,
            "category": "loan_calculator",
        },
        "cannibalization_context": {
            "matches_existing_slug": "direct-consolidation-loan-calculator",
            "current_position": 11.2,
            "cannibalization_score": 0.78,
        },
        "expected_action": "REFACTOR_PAGE",
        "expected_matching_tool": "direct-consolidation-loan-calculator",
    },
    {
        "id": "spike-007",
        "query": "section 179d commercial clean energy deduction matrix",
        "source": "reddit_autocomplete",
        "detected_at": "2026-10-08T08:00:00Z",
        "sample_count": 760,
        "velocity": 28.0,
        "acceleration": 9.8,
        "z_score": 3.4,
        "baseline_mean": 3.2,
        "baseline_std": 1.1,
        "expected_transient_noise": False,
        "treg_mock": {
            "search_volume": 1600,
            "cpc_usd": 12.40,
            "competition_index": 0.40,
            "keyword_difficulty": 14.0,
            "position_zero_vacant": True,
        },
        "jev_mock": {
            "jev_score": 1.80,
            "durable_prob": 0.95,
            "category": "commercial_tax_matrix",
        },
        "cannibalization_context": {
            "matches_existing_slug": "section-179-calculator",
            "cannibalization_score": 0.28,
            "is_cannibalizing": False,
        },
        "expected_action": "BUILD_PAGE",
        "expected_asset_type": "statutory_matrix",
    },
    {
        "id": "spike-008",
        "query": "ai token usage cost estimator by provider",
        "source": "google_suggest",
        "detected_at": "2026-10-08T08:15:00Z",
        "sample_count": 2100,
        "velocity": 62.0,
        "acceleration": 18.0,
        "z_score": 4.1,
        "baseline_mean": 8.0,
        "baseline_std": 2.0,
        "expected_transient_noise": False,
        "treg_mock": {
            "search_volume": 2400,
            "cpc_usd": 3.50,
            "competition_index": 0.25,
            "keyword_difficulty": 16.0,
            "position_zero_vacant": True,
        },
        "jev_mock": {
            "jev_score": 1.68,
            "durable_prob": 0.88,
            "category": "developer_utility",
        },
        "expected_action": "BUILD_PAGE",
        "expected_asset_type": "interactive_calculator",
    },
]


def test_end_to_end_trend_pipeline_with_evaluation_fixtures(tmp_path):
    """
    Executes complete trend pipeline against the 8 breakout spikes evaluation set.
    Validates transient noise rejection, treg cross-checking, Jev triage, and atomic flock persistence.
    """
    sink_file = tmp_path / "void_candidates.jsonl"

    spikes = [
        FeedSpike(
            id=rec["id"],
            query=rec["query"],
            source=rec["source"],
            detected_at=rec["detected_at"],
            sample_count=rec["sample_count"],
            velocity=rec["velocity"],
            acceleration=rec["acceleration"],
            z_score=rec["z_score"],
            baseline_mean=rec["baseline_mean"],
            baseline_std=rec["baseline_std"],
            raw_payload=rec,
        )
        for rec in EVALUATION_RECORDS
    ]

    pipeline = TrendPipeline()
    result = pipeline.process_spikes(raw_spikes=spikes, sink_path=sink_file)

    # 1. Total counts
    assert result["total_spikes"] == 8
    assert result["filtered_noise_count"] == 4
    assert result["evaluated_candidates_count"] == 4

    # 2. Rejection verification: Spikes 1 to 4 must be REJECTED
    rejected_queries = [r["query"] for r in result["rejected"]]
    assert len(result["rejected"]) == 4
    assert "zendaya oscars dress designer 2026" in rejected_queries
    assert "hawk tuah soundboard remix generator" in rejected_queries
    assert "spacex starship launch scrubbed reasons today" in rejected_queries
    assert "super bowl halftime performer leak 2027" in rejected_queries

    # 3. Build Page verification: Spikes 5, 7, 8 must qualify for BUILD_PAGE
    approved_queries = [r["query"] for r in result["approved_build"]]
    assert len(result["approved_build"]) == 3
    assert "form 8829 home office deduction calculator 2026" in approved_queries
    assert "section 179d commercial clean energy deduction matrix" in approved_queries
    assert "ai token usage cost estimator by provider" in approved_queries

    # Target asset types verification
    asset_types = {r["query"]: r["target_asset_type"] for r in result["approved_build"]}
    assert asset_types["form 8829 home office deduction calculator 2026"] == "interactive_calculator"
    assert asset_types["section 179d commercial clean energy deduction matrix"] == "statutory_matrix"
    assert asset_types["ai token usage cost estimator by provider"] == "interactive_calculator"

    # 4. Refactor verification: Spike 6 must route to REFACTOR_PAGE
    assert len(result["refactor_pages"]) == 1
    refactor_item = result["refactor_pages"][0]
    assert refactor_item["query"] == "direct consolidation loan repayment estimator"
    assert refactor_item["matching_tool"] == "direct-consolidation-loan-calculator"
    assert refactor_item["overlay_spec"]["measurement_lock_days"] == 28

    # 5. Composite Profit Yield rankings verification
    rankings = result["rankings"]
    assert len(rankings) == 8
    # Top 4 rankings must be the viable candidates
    top_actions = [r["action"] for r in rankings[:4]]
    assert "REJECT" not in top_actions
    assert all(r["composite_profit_yield"] >= 60.0 for r in result["approved_build"])
    assert all(r["composite_profit_yield"] > 0.0 for r in rankings[:4])
    assert all(r["composite_profit_yield"] == 0.0 for r in rankings[4:])

    # 6. HWL-1253 Atomic flock sink verification
    assert sink_file.exists()
    lines = sink_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 8
    for line in lines:
        data = json.loads(line)
        assert "query" in data
        assert "slug" in data
        assert "action" in data
        assert "composite_profit_yield" in data
        # Content invariants
        assert_no_forbidden_dashes(data["query"], "persisted line query")
        assert_no_forbidden_dashes(data["decision_reason"], "persisted line reason")
        assert_no_prompt_leakage(data["decision_reason"], "persisted line reason")
        assert_url_safe_slug(data["slug"])


def test_run_trend_pipeline_convenience_helper(tmp_path):
    """Verifies run_trend_pipeline helper function."""
    res = run_trend_pipeline(spikes=[EVALUATION_RECORDS[4]], sink_path=tmp_path / "sink.jsonl")
    assert res["total_spikes"] == 1
    assert len(res["approved_build"]) == 1
    assert res["approved_build"][0]["action"] == "BUILD_PAGE"


def test_trend_pipeline_empty_queue_short_circuit_and_duplicate_idempotency(tmp_path):
    """
    Verifies:
    1. Empty spike list short-circuits with status='NO_OP_EMPTY_QUEUE' without creating sink file.
    2. Duplicate spike deliveries into sink_path are deduplicated via composite idempotency_key.
    """
    sink_file = tmp_path / "void_candidates.jsonl"
    pipeline = TrendPipeline()

    empty_res = pipeline.process_spikes(raw_spikes=[], sink_path=sink_file)
    assert empty_res["status"] == "NO_OP_EMPTY_QUEUE"
    assert empty_res["total_spikes"] == 0
    assert not sink_file.exists()

    # First delivery of 8 spikes
    first_res = pipeline.process_spikes(raw_spikes=EVALUATION_RECORDS, sink_path=sink_file)
    assert first_res["status"] == "COMPLETED"
    assert first_res["deduplicated_sink_count"] == 0
    lines_after_first = sink_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines_after_first) == 8
    first_record = json.loads(lines_after_first[0])
    assert "idempotency_key" in first_record
    assert first_record["idempotency_key"].count(":") == 3

    # Duplicate delivery of the exact same 8 spikes
    second_res = pipeline.process_spikes(raw_spikes=EVALUATION_RECORDS, sink_path=sink_file)
    assert second_res["status"] == "COMPLETED"
    assert second_res["deduplicated_sink_count"] == 8
    lines_after_second = sink_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines_after_second) == 8


def test_harvested_statutory_suggest_spikes_qualify_for_build(tmp_path):
    """
    Verifies that top-ranked suggest completions for high-intent statutory/calculator queries
    pass noise filtering, offline treg heuristics, and Jev scoring to reach BUILD_PAGE.
    """
    from unittest.mock import patch
    from pseofactory.trends.collectors import GoogleSuggestCollector

    collector = GoogleSuggestCollector()
    with patch.object(
        collector,
        "fetch_suggestions",
        return_value=[
            "section 179 deduction calculator 2026",
            "celebrity gossip oscars dress",
        ],
    ):
        harvested = collector.harvest_spikes(seed_query="section 179")
    assert len(harvested) == 2

    pipeline = TrendPipeline()
    res = pipeline.process_spikes(raw_spikes=harvested, sink_path=tmp_path / "harvested.jsonl")
    approved_queries = [r["query"] for r in res["approved_build"]]
    rejected_queries = [r["query"] for r in res["rejected"]]
    assert "section 179 deduction calculator 2026" in approved_queries
    assert "celebrity gossip oscars dress" in rejected_queries

