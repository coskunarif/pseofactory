"""
Targeted tests for pseofactory.competitor topic qualification upgrades:
  - Deletion of build_high_intent_comparison_targets (best_of_roundup).
  - Upgraded filter_rankable_tool_keywords gates: kd <= 30, lowest_dr <= tenant_dr + 15,
    reject .gov interactive calculators on Page 1, reject non-transactional AIO SERPs,
    require >= 3 user inputs when provided, and sort by Traffic Potential (fallback to volume).

Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import pseofactory.competitor as comp_mod
from pseofactory.competitor import filter_rankable_tool_keywords


def test_build_high_intent_comparison_targets_deleted() -> None:
    assert not hasattr(comp_mod, "build_high_intent_comparison_targets")
    assert "build_high_intent_comparison_targets" not in comp_mod.__all__


def test_filter_rankable_tool_keywords_strict_gates_and_traffic_potential_sort() -> None:
    rows = [
        {
            "keyword": "high kd 31 calculator",
            "position": 3,
            "volume": 9000,
            "traffic_potential": 12000,
            "kd": 31.0,
            "lowest_dr": 20.0,
            "input_count": 4,
            "tool_results_in_top10": 6,
        },
        {
            "keyword": "high lowest dr calculator",
            "position": 4,
            "volume": 8000,
            "traffic_potential": 11000,
            "kd": 22.0,
            "lowest_dr": 45.0,  # > tenant_dr (25) + 15 = 40
            "input_count": 4,
            "tool_results_in_top10": 6,
        },
        {
            "keyword": "gov simulator on page 1 calculator",
            "position": 2,
            "volume": 7500,
            "traffic_potential": 10000,
            "kd": 18.0,
            "lowest_dr": 25.0,
            "input_count": 4,
            "tool_results_in_top10": 5,
            "top10_urls": ["https://studentaid.gov/loan-simulator/"],
        },
        {
            "keyword": "aio dominated informational query",
            "position": 5,
            "volume": 6000,
            "traffic_potential": 8000,
            "kd": 15.0,
            "lowest_dr": 22.0,
            "input_count": 3,
            "tool_results_in_top10": 4,
            "serp_dominant_format": "ai_overview",
            "intent": "informational",
        },
        {
            "keyword": "too few inputs calculator",
            "position": 5,
            "volume": 5000,
            "traffic_potential": 7000,
            "kd": 15.0,
            "lowest_dr": 22.0,
            "input_count": 2,
            "tool_results_in_top10": 5,
        },
        {
            "keyword": "section 179 depreciation calculator",
            "position": 2,
            "volume": 4000,
            "traffic_potential": 9500,
            "kd": 24.0,
            "lowest_dr": 32.0,
            "input_count": 4,
            "tool_results_in_top10": 7,
        },
        {
            "keyword": "section 1031 boot calculator",
            "position": 3,
            "volume": 6500,  # higher volume, lower traffic_potential
            "traffic_potential": 7100,
            "kd": 21.0,
            "lowest_dr": 30.0,
            "input_count": 5,
            "tool_results_in_top10": 6,
        },
        {
            "keyword": "fallback volume calculator",
            "position": 4,
            "volume": 8200,  # no traffic_potential -> falls back to volume (8200)
            "kd": 20.0,
            "lowest_dr": 28.0,
            "input_count": 3,
            "tool_results_in_top10": 5,
        },
    ]

    res = filter_rankable_tool_keywords(rows, tenant_id="profithelm", tenant_dr=25.0)
    assert res["kd_ceiling"] == 30.0
    assert res["lowest_dr_ceiling"] == 40.0
    assert res["surviving_count"] == 3
    assert res["dropped_count"] == 5

    surv_kws = [r["keyword"] for r in res["surviving_keywords"]]
    # Sorted by traffic_potential (9500 > fallback 8200 > 7100)
    assert surv_kws == [
        "section 179 depreciation calculator",
        "fallback volume calculator",
        "section 1031 boot calculator",
    ]


def test_filter_rankable_tool_keywords_preserves_kd_zero() -> None:
    """Explicit kd=0 must remain 0.0 and never be coerced to default 25.0."""
    rows = [
        {
            "keyword": "zero kd tax calculator",
            "position": 3,
            "volume": 5000,
            "traffic_potential": 6000,
            "kd": 0,
            "lowest_dr": 10.0,
            "input_count": 4,
            "tool_results_in_top10": 5,
        },
        {
            "keyword": "missing kd tax calculator",
            "position": 3,
            "volume": 5000,
            "traffic_potential": 6000,
            # kd omitted -> defaults to 25.0, which exceeds kd_ceiling = 15.0
            "lowest_dr": 10.0,
            "input_count": 4,
            "tool_results_in_top10": 5,
        },
    ]
    res = filter_rankable_tool_keywords(
        rows,
        tenant_id="profithelm",
        tenant_dr=10.0,
        max_kd_delta=5.0,
    )
    assert res["kd_ceiling"] == 15.0
    assert res["surviving_count"] == 1
    assert res["surviving_keywords"][0]["keyword"] == "zero kd tax calculator"
    assert res["surviving_keywords"][0]["kd"] == 0.0
    assert res["dropped_count"] == 1
    assert res["dropped_keywords"][0]["keyword"] == "missing kd tax calculator"
