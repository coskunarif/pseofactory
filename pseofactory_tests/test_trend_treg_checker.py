"""
Tests for pseofactory treg durability cross-checker.
Verifies keyword volume, CPC, competition density, and Position 0 vacancy evaluation via treg routes.
Zero em-dashes. Zero en-dashes.
"""

import json
from unittest.mock import patch, MagicMock

from pseofactory.trends.treg_checker import TregChecker
from pseofactory.trends.models import TregDurabilityResult


def test_treg_checker_mock_registry():
    """Verifies TregChecker correctly returns pre-registered mock metrics."""
    mock_fixtures = {
        "form 8829 calculator": {
            "search_volume": 3600,
            "cpc_usd": 4.80,
            "competition_index": 0.35,
            "keyword_difficulty": 18.0,
            "position_zero_vacant": True,
        }
    }
    checker = TregChecker(mock_data=mock_fixtures)
    res = checker.check_query("form 8829 calculator")

    assert isinstance(res, TregDurabilityResult)
    assert res.query == "form 8829 calculator"
    assert res.search_volume == 3600
    assert res.cpc_usd == 4.80
    assert res.keyword_difficulty == 18.0
    assert res.position_zero_vacant is True


def test_treg_checker_position_zero_vacancy_hwl_1215():
    """
    Enforces HWL-1215: Position 0 is vacant when KD < 25.0 even if explicit flag is unset.
    """
    checker = TregChecker()
    # Case 1: KD = 16.0 (< 25) without explicit position_zero_vacant
    override_low_kd = {
        "search_volume": 2400,
        "cpc_usd": 3.50,
        "keyword_difficulty": 16.0,
    }
    res1 = checker.check_query("ai token usage cost estimator", mock_override=override_low_kd)
    assert res1.position_zero_vacant is True

    # Case 2: KD = 55.0 (>= 25) with position_zero_vacant = False
    override_high_kd = {
        "search_volume": 2100,
        "cpc_usd": 0.20,
        "keyword_difficulty": 55.0,
        "position_zero_vacant": False,
    }
    res2 = checker.check_query("spacex launch scrubbed reasons", mock_override=override_high_kd)
    assert res2.position_zero_vacant is False


def test_treg_checker_caching():
    """Verifies in-memory cache returns previous result without reprocessing."""
    checker = TregChecker(mock_data={"test query": {"search_volume": 500}})
    res1 = checker.check_query("test query")
    res2 = checker.check_query("test query")
    assert res1 is res2


def test_treg_checker_subprocess_invocation():
    """Verifies external treg CLI is invoked with route cap header and JSON payload."""
    checker = TregChecker(max_cost="0.05", timeout=5.0)

    mock_stdout = json.dumps({
        "result": {
            "search_volume": 4200,
            "cpc_usd": 5.10,
            "competition_index": 0.40,
            "keyword_difficulty": 12.0,
            "position_zero_vacant": True,
        }
    })

    with patch("shutil.which", return_value="/usr/local/bin/treg"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=mock_stdout)
            res = checker.check_query("commercial solar clean energy tax deduction")

            assert res.search_volume == 4200
            assert res.cpc_usd == 5.10
            assert res.keyword_difficulty == 12.0

            # Verify CLI arguments
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "call" in call_args
            assert "treg.google.keywords.volume" in call_args
            assert "X-Treg-Route-Max-Cost: 0.05" in call_args


def test_treg_checker_offline_fallback():
    """Verifies robust fallback when treg is not installed or unreachable."""
    checker = TregChecker()
    with patch("shutil.which", return_value=None):
        res = checker.check_query("unique unmocked query")
        assert res.search_volume > 0
        assert res.keyword_difficulty < 25.0
        assert res.position_zero_vacant is True
        assert "offline_fallback" in res.endpoint_called


def test_parse_ai_citation_payload_vacant_and_occupied():
    """
    Verifies DataForSEO chat_gpt/llm_scraper/live/advanced payload parsing
    distinguishes vacant AI citation slots from occupied ones.
    """
    from pseofactory.trends.treg_checker import parse_ai_citation_payload

    # Case 1: Only Reddit and raw IRS .gov cited -> vacant interactive calculator slot
    vacant_payload = {
        "tasks": [
            {
                "result": [
                    {
                        "items": [
                            {
                                "sources": [
                                    {"domain": "www.irs.gov", "url": "https://www.irs.gov/pub/irs-pdf/f8829.pdf"},
                                    {"domain": "reddit.com", "url": "https://www.reddit.com/r/tax/comments/123"},
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
    }
    parsed_vacant = parse_ai_citation_payload(vacant_payload)
    assert parsed_vacant["ai_citation_vacant"] is True
    assert parsed_vacant["tenant_cited"] is False
    assert "irs.gov" in parsed_vacant["ai_cited_domains"]
    assert "reddit.com" in parsed_vacant["ai_cited_domains"]

    # Case 2: Tenant domain already cited -> not vacant
    tenant_payload = {
        "result": {
            "sources": [
                {"domain": "profithelm.com", "url": "https://profithelm.com/tools/section-179-calculator"},
            ]
        }
    }
    parsed_tenant = parse_ai_citation_payload(tenant_payload)
    assert parsed_tenant["tenant_cited"] is True
    assert parsed_tenant["ai_citation_vacant"] is False

    # Case 3: Two strong commercial calculator authorities cited -> not vacant
    occupied_payload = {
        "result": {
            "sources": [
                {"domain": "calculator.net"},
                {"domain": "smartasset.com"},
            ]
        }
    }
    parsed_occupied = parse_ai_citation_payload(occupied_payload)
    assert parsed_occupied["ai_citation_vacant"] is False
    assert parsed_occupied["strong_authority_count"] == 2


def test_treg_checker_ai_citation_subprocess():
    """
    Verifies check_ai_citation invokes dataforseo.x.ai-optimization-chat-gpt-llm-scraper-live-advanced
    with X-Treg-Route-Max-Cost: 0.01 ($0.004/call route).
    """
    checker = TregChecker(ai_max_cost="0.01", check_ai_citations=True)
    mock_ai_stdout = json.dumps({
        "result": {
            "sources": [
                {"domain": "irs.gov", "url": "https://www.irs.gov/forms-pubs/about-form-8829"},
                {"domain": "reddit.com", "url": "https://www.reddit.com/r/smallbusiness/"},
            ]
        }
    })

    with patch("shutil.which", return_value="/usr/local/bin/treg"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=mock_ai_stdout)
            ai_res = checker.check_ai_citation("form 8829 deduction calculator")

            assert ai_res["ai_citation_checked"] is True
            assert ai_res["ai_citation_vacant"] is True
            assert ai_res["ai_cited_domains"] == ["irs.gov", "reddit.com"]

            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "dataforseo.x.ai-optimization-chat-gpt-llm-scraper-live-advanced" in call_args
            assert "X-Treg-Route-Max-Cost: 0.01" in call_args


def test_parse_ai_citation_payload_gap_status_classification():
    """
    Verifies parse_ai_citation_payload and offline fallback classify MISSING_AI_OVERVIEW
    vs LOSING_TO_WEAKER_DOMAINS accurately.
    """
    from pseofactory.trends.treg_checker import parse_ai_citation_payload

    missing_res = parse_ai_citation_payload({"result": {"sources": []}})
    assert missing_res["missing_ai_overview"] is True
    assert missing_res["losing_to_weaker_domains"] is False
    assert missing_res["citation_gap_status"] == "MISSING_AI_OVERVIEW"

    weaker_res = parse_ai_citation_payload(
        {
            "result": {
                "sources": [
                    {"domain": "studentaid.gov", "url": "https://studentaid.gov/manage-loans/forgiveness-cancellation"},
                    {"domain": "reddit.com", "url": "https://www.reddit.com/r/StudentLoans/"},
                ]
            }
        }
    )
    assert weaker_res["missing_ai_overview"] is False
    assert weaker_res["losing_to_weaker_domains"] is True
    assert weaker_res["weaker_cited_domains"] == ["studentaid.gov", "reddit.com"]
    assert weaker_res["citation_gap_status"] == "LOSING_TO_WEAKER_DOMAINS"


def test_treg_checker_falls_back_to_serpstat_on_402_route_max_cost():
    """
    When treg.google.keywords.volume fails with HTTP 402 route_max_cost, TregChecker
    automatically falls back to serpstat.google.keywords.volume and returns a real
    non-synthetic measured TregDurabilityResult in both batch and single-query paths.
    """
    serpstat_endpoint = "serpstat.google.keywords.volume"
    serpstat_stdout = json.dumps(
        {
            "id": "1",
            "result": {
                "data": [
                    {
                        "keyword": "irs interest calculator",
                        "region_queries_count": 1300,
                        "cost": 1.25,
                        "concurrency": 45,
                        "difficulty": 33,
                    }
                ]
            },
        }
    )

    def _side_effect(cmd, *args, **kwargs):
        if "treg.google.keywords.volume" in cmd:
            return MagicMock(returncode=1, stdout="", stderr="HTTP 402 route_max_cost")
        if serpstat_endpoint in cmd:
            return MagicMock(returncode=0, stdout=serpstat_stdout, stderr="")
        return MagicMock(returncode=1, stdout="", stderr="unexpected endpoint")

    with patch("shutil.which", return_value="/usr/local/bin/treg"):
        with patch("subprocess.run", side_effect=_side_effect):
            batch_checker = TregChecker(max_cost="0.05", timeout=5.0)
            batch_res = batch_checker.check_queries_batch(["irs interest calculator"])
            r_batch = batch_res["irs interest calculator"]
            assert r_batch.endpoint_called == serpstat_endpoint
            assert r_batch.is_synthetic is False
            assert r_batch.search_volume == 1300
            assert r_batch.cpc_usd == 1.25
            assert r_batch.competition_index == 0.45
            assert r_batch.keyword_difficulty == 33.0

            single_checker = TregChecker(max_cost="0.05", timeout=5.0)
            r_single = single_checker.check_query("irs interest calculator")
            assert r_single.endpoint_called == serpstat_endpoint
            assert r_single.is_synthetic is False
            assert r_single.search_volume == 1300
            assert r_single.cpc_usd == 1.25
            assert r_single.competition_index == 0.45
            assert r_single.keyword_difficulty == 33.0



