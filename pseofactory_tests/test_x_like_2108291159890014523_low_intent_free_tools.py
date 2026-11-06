"""x-like:2108291159890014523 (@HsanC_): free tools drive low-intent traffic and 0 sales.

The tool-keyword pipeline must reject high-volume, low-buyer-intent utility clusters and
emit high-intent 'best X tools' / 'alternative to X' targets.
"""

from __future__ import annotations

from pseofactory.competitor import (
    build_high_intent_comparison_targets,
    score_tool_cluster_roi_and_crawl_risk,
)


def _cluster(kw: str, vol: int) -> dict:
    return {
        "primary_keyword": kw, "target_slug": kw.replace(" ", "-"), "combined_volume": vol,
        "avg_kd": 15.0, "avg_top10_dr": 40.0, "avg_tool_results_in_top10": 5.0,
    }


def test_low_intent_traffic_only_cluster_rejected() -> None:
    out = score_tool_cluster_roi_and_crawl_risk(_cluster("youtube shorts downloader", 60000))
    assert out["low_intent_traffic_only"] is True
    assert out["recommended_action"] == "REJECT_LOW_INTENT_TRAFFIC_ONLY"


def test_high_intent_calculator_cluster_survives() -> None:
    out = score_tool_cluster_roi_and_crawl_risk(_cluster("section 179 deduction calculator", 20000))
    assert out["low_intent_traffic_only"] is False
    assert out["recommended_action"] == "BUILD_NEW_CANONICAL_TOOL"
    assert out["scores"]["buyer_intent_score"] >= 25.0


def test_high_intent_comparison_targets() -> None:
    t = build_high_intent_comparison_targets("Tax Software", ["TurboTax", "turbotax", "H&R Block"])
    kws = [x["keyword"] for x in t]
    assert kws[0] == "best tax software tools"
    assert "alternative to turbotax" in kws and "h&r block alternative" in kws
    assert len([k for k in kws if "turbotax" in k]) == 2
