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
            assert "treg.google.keywords.ideas" in call_args
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
