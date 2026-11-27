"""
Focused regression tests for factory discovery gaps (collectors, cron routing,
jurisdiction filter, metadata isolation, Jev intent weights, and dynamic seeds).
Zero em-dashes. Zero en-dashes.
"""

import json
import logging
from pathlib import Path
from unittest.mock import patch

from pseofactory.trends.collectors import (
    DuckDuckGoSuggestCollector,
    MultiSourceCollector,
    RedditSuggestCollector,
    YouTubeSuggestCollector,
)
from pseofactory.trends.cron import (
    DEFAULT_CRON_SEEDS,
    DEFAULT_VOID_CANDIDATES_SINK,
    TrendCronRunner,
    build_dynamic_cron_seeds,
    detect_non_us_jurisdiction,
    reconcile_superseded_pending_rows,
)
from pseofactory.trends.jev_engine import (
    MIN_BUILD_YIELD,
    JevEngine,
    calculate_intent_weight,
    determine_target_asset_type,
)
from pseofactory.tenant_facts import match_tenant_statutory_intent


def test_youtube_suggest_parses_json_and_jsonp_and_logs_warning(caplog):
    """(a) YouTubeSuggestCollector parses clean JSON (client=firefox) and JSONP fallback."""
    collector = YouTubeSuggestCollector()

    json_payload = json.dumps(["section 179", ["section 179 deduction", "section 179 vehicle"]]).encode("utf-8")
    with patch("pseofactory.trends.collectors.make_resilient_request", return_value=json_payload) as mock_req:
        res_json = collector.fetch_suggestions("section 179")
        assert res_json == ["section 179 deduction", "section 179 vehicle"]
        called_url = mock_req.call_args[0][0]
        assert "client=firefox&ds=yt" in called_url

    jsonp_payload = b'window.google.ac.h(["1031",[["1031 exchange calculator",0],["1031 boot rules",0]]])'
    with patch("pseofactory.trends.collectors.make_resilient_request", return_value=jsonp_payload):
        res_jsonp = collector.fetch_suggestions("1031")
        assert res_jsonp == ["1031 exchange calculator", "1031 boot rules"]

    with caplog.at_level(logging.WARNING, logger="pseofactory.trends.collectors"):
        with patch("pseofactory.trends.collectors.make_resilient_request", return_value=b"not-valid-json-or-jsonp"):
            assert collector.fetch_suggestions("broken") == []
        assert any("YouTubeSuggestCollector failed to parse" in rec.message for rec in caplog.records)


def test_duckduckgo_collector_replaces_blocked_reddit_while_preserving_compat():
    """MultiSourceCollector uses DuckDuckGoSuggestCollector; RedditSuggestCollector remains importable."""
    multi = MultiSourceCollector()
    names = [c.source_name for c in multi.collectors]
    assert "duckduckgo_suggest" in names
    assert "reddit_autocomplete" not in names
    assert callable(RedditSuggestCollector)

    ddg = DuckDuckGoSuggestCollector()
    ddg_payload = json.dumps([{"phrase": "1031 exchange calculator"}, {"phrase": "1031 boot calculator"}]).encode("utf-8")
    with patch("pseofactory.trends.collectors.make_resilient_request", return_value=ddg_payload):
        assert ddg.fetch_suggestions("1031") == ["1031 exchange calculator", "1031 boot calculator"]


def test_detect_non_us_jurisdiction_avoids_us_state_false_positives():
    """(b) US states/regions such as New Mexico are allowed while non-US markers remain blocked."""
    from pseofactory.qualification import detect_non_us_jurisdiction as qual_detect

    assert qual_detect("new mexico tax brackets 2027", property_id="profithelm") is None
    assert detect_non_us_jurisdiction("new mexico tax brackets 2027", property_id="profithelm") is None
    assert detect_non_us_jurisdiction("new-mexico-tax-brackets-2027", property_id="profithelm") is None
    assert detect_non_us_jurisdiction("new england contractor lien", property_id="lienbond") is None
    assert detect_non_us_jurisdiction("new york section 179 deduction", property_id="profithelm") is None
    assert detect_non_us_jurisdiction("new jersey mechanics lien", property_id="lienbond") is None
    assert detect_non_us_jurisdiction("georgia contractor bond calculator", property_id="lienbond") is None
    assert detect_non_us_jurisdiction("georgia workers comp rate", property_id="lienbond") is None

    assert detect_non_us_jurisdiction("mexico tax calculator", property_id="profithelm") == "mexico"
    assert detect_non_us_jurisdiction("england tax calculator", property_id="profithelm") == "united_kingdom"
    assert detect_non_us_jurisdiction("british columbia tax calculator", property_id="profithelm") == "canada"
    assert detect_non_us_jurisdiction("republic of georgia tax calculator", property_id="profithelm") == "georgia"


def test_property_id_metadata_overwrites_gsc_source_property(tmp_path: Path):
    """(c) cand.metadata['property_id'] is overwritten with assigned_property (no GSC leak)."""
    db_file = tmp_path / "gsc_leak.db"
    fixture_file = tmp_path / "gsc_unassigned.json"
    spikes = [
        {
            "id": "gsc-leak-1",
            "query": "commercial solar itc depreciation schedule calculator",
            "source": "gsc_search_console",
            "property_id": "profithelm",
            "velocity": 62.0,
            "acceleration": 14.0,
            "z_score": 3.5,
            "treg_mock": {
                "search_volume": 2400,
                "cpc_usd": 8.50,
                "keyword_difficulty": 18.0,
                "position_zero_vacant": True,
                "historical_stability": 0.90,
            },
            "jev_mock": {"jev_score": 1.75, "durable_prob": 0.90},
        }
    ]
    fixture_file.write_text(json.dumps(spikes), encoding="utf-8")

    captured_property_ids = []
    orig_eval = JevEngine.evaluate

    def _spy_eval(self, candidate, *args, **kwargs):
        captured_property_ids.append((candidate.metadata or {}).get("property_id"))
        return orig_eval(self, candidate, *args, **kwargs)

    runner = TrendCronRunner(db_path=db_file)
    with patch.object(JevEngine, "evaluate", autospec=True, side_effect=_spy_eval):
        res = runner.run_cycle(
            cycle_id="cycle_gsc_leak_01",
            fixture_path=fixture_file,
            include_unassigned=True,
            dry_run=False,
        )

    assert captured_property_ids == ["unassigned"]
    assert res["monitored"][0]["property_id"] == "unassigned"


def test_calculate_intent_weight_handles_calculation_and_estimate_word_forms():
    """(d) Word forms calculation/calculate/estimate get full 1.0 transactional weight."""
    for q in (
        "workers compensation payroll calculation",
        "1031 exchange calculation",
        "calculate section 179 deduction",
        "estimate student loan payment",
        "estimating surety bond cost",
        "hipaa penalty estimation",
    ):
        assert calculate_intent_weight("informational", q) == 1.0
        assert determine_target_asset_type(q, "informational") == "interactive_calculator"


def test_min_build_yield_remains_60():
    """(e) min_build_yield quality bar remains strictly >= 60.0."""
    assert MIN_BUILD_YIELD == 60.0
    assert JevEngine().min_build_yield == 60.0
    assert TrendCronRunner().min_yield == 60.0


def test_expanded_tenant_statutory_routing_without_cross_contamination():
    """(f) All 4 active tenants route domain queries deterministically with zero cross-contamination."""
    runner = TrendCronRunner()
    expected = {
        "1031 boot calculator": "profithelm",
        "section 301 tariff calculator": "profithelm",
        "irs vehicle depreciation calculator": "profithelm",
        "public service loan forgiveness calculator": "prexvo",
        "partial financial hardship calculator": "prexvo",
        "idr calculator": "prexvo",
        "surety bond rate calculator": "lienbond",
        "mechanics lien deadlines by state": "lienbond",
        "soc 2 audit cost calculator": "gainhelm",
        "nist 800 171 sprs score calculator": "gainhelm",
    }
    for query, expected_prop in expected.items():
        res = runner.determine_property_assignment(query)
        assert res["property_id"] == expected_prop, f"Failed routing for {query!r}: {res}"
        assert res["contamination_scan_passed"] == 1, f"Contamination failed for {query!r}: {res}"

    # Short 'idr' and numeric '1031' tokens must not false-match inside unrelated words/numbers
    assert match_tenant_statutory_intent("gridiron equipment lease calculator")["prexvo"] is False
    assert match_tenant_statutory_intent("zip code 21031 property tax")["profithelm"] is False


def test_trend_intake_default_sink_and_pipeline_supersedes_pending(tmp_path: Path):
    """trend-intake defaults --sink to canonical .agy/void_candidates.jsonl and TrendPipeline supersedes PENDING."""
    from pseofactory.cli import build_parser
    from pseofactory.trends.pipeline import run_trend_pipeline

    parser = build_parser()
    args = parser.parse_args(["trend-intake"])
    assert args.sink == str(DEFAULT_VOID_CANDIDATES_SINK)
    assert str(args.sink).endswith(".agy/void_candidates.jsonl")

    sink_file = tmp_path / "pipeline_void.jsonl"
    sink_file.write_text(
        json.dumps(
            {
                "query": "obscure viral meme gadget",
                "slug": "obscure-viral-meme-gadget",
                "property_id": "unassigned",
                "action": "BUILD_PAGE",
                "status": "PENDING",
                "evaluated_at": "2026-11-11T08:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    run_trend_pipeline(
        spikes=[
            {
                "id": "sp-pipe-1",
                "query": "obscure viral meme gadget",
                "source": "google_suggest",
                "velocity": 15.0,
                "acceleration": 1.0,
                "z_score": 1.8,
                "treg_mock": {
                    "search_volume": 100,
                    "cpc_usd": 0.2,
                    "keyword_difficulty": 70.0,
                    "position_zero_vacant": False,
                },
            }
        ],
        sink_path=sink_file,
    )
    rows = [json.loads(line) for line in sink_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    old_build = [r for r in rows if r.get("action") == "BUILD_PAGE"]
    assert len(old_build) == 1
    assert old_build[0]["status"] == "SUPERSEDED"


def test_dynamic_seed_expansion_and_canonical_queue_reconciliation(tmp_path: Path):
    """(g) Dynamic seed expansion synthesizes tenant seeds and stale PENDING rows are superseded."""
    base_seeds = {s.strip().lower() for s in DEFAULT_CRON_SEEDS.split(",") if s.strip()}
    dyn_day1 = build_dynamic_cron_seeds(cycle_index=10, max_dynamic=20)
    dyn_day2 = build_dynamic_cron_seeds(cycle_index=11, max_dynamic=20)

    assert 16 <= len(dyn_day1) <= 24
    assert all(s.lower() not in base_seeds for s in dyn_day1)
    assert dyn_day1 != dyn_day2

    runner = TrendCronRunner()
    assert runner.default_sink_path == DEFAULT_VOID_CANDIDATES_SINK.resolve()
    assert str(runner.default_sink_path).endswith(".agy/void_candidates.jsonl")

    sink_file = tmp_path / "void_candidates.jsonl"
    stale_row = {
        "query": "1031 boot calculator",
        "slug": "1031-boot-calculator",
        "property_id": "profithelm",
        "action": "BUILD_PAGE",
        "status": "PENDING",
        "evaluated_at": "2026-11-11T08:00:00Z",
    }
    sink_file.write_text(json.dumps(stale_row) + "\n", encoding="utf-8")

    updated = reconcile_superseded_pending_rows(
        sink_file,
        [
            {
                "query": "1031 boot calculator",
                "slug": "1031-boot-calculator",
                "property_id": "profithelm",
                "action": "MONITOR",
                "evaluated_at": "2026-11-27T09:00:00Z",
            }
        ],
    )
    assert updated == 1
    rows = [json.loads(line) for line in sink_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows[0]["status"] == "SUPERSEDED"
    assert rows[0]["superseded_by_action"] == "MONITOR"
