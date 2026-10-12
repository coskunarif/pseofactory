"""
Unit tests for EdgeVisitorClassifier and EdgeIntentRouter.
Validates:
1. Referer and URL parameter extraction (Google, Bing, DuckDuckGo, ?q=, ?s=, ?query=).
2. Multi-archetype intent classification aligned with jev_engine.py:
   - Statutory calculations / deductions -> interactive_calculator (1.0)
   - Statutory matrices / rules -> statutory_matrix (1.0)
   - Competitor / product comparisons -> comparison_engine (0.7)
   - General tools -> interactive_calculator (0.8)
   - Noise / memes -> REJECT / noise (0.05)
   - Informational -> void_documentation (0.3)
3. Route decision actions (REWRITE_TO_CLUSTER, INJECT_OVERLAY, PASS_THROUGH).
4. Cloudflare Worker JavaScript script generation.
5. Zero forbidden dashes (U+2014, U+2013) invariant check.
Zero em-dashes. Zero en-dashes.
"""

import json
import shutil
import subprocess
import tempfile
import pytest

from pseofactory.contracts import assert_no_forbidden_dashes
from pseofactory.edge import (
    EdgeVisitorClassifier,
    EdgeIntentRouter,
    generate_edge_worker_script,
    VisitorIntent,
    RouteDecision,
)


def test_referer_extraction_google():
    """Extracts search query from Google Referer headers."""
    headers_1 = {"referer": "https://www.google.com/url?q=section+179+calculator&sa=D"}
    assert EdgeVisitorClassifier.extract_search_query(headers=headers_1) == "section 179 calculator"

    headers_2 = {"Referer": "https://www.google.com/search?q=form+8829+deduction"}
    assert EdgeVisitorClassifier.extract_search_query(headers=headers_2) == "form 8829 deduction"


def test_referer_extraction_bing():
    """Extracts search query from Bing Referer header."""
    headers = {"referer": "https://www.bing.com/search?q=commercial+clean+energy+matrix&form=QBLH"}
    assert EdgeVisitorClassifier.extract_search_query(headers=headers) == "commercial clean energy matrix"


def test_referer_extraction_duckduckgo():
    """Extracts search query from DuckDuckGo Referer header."""
    headers = {"Referer": "https://duckduckgo.com/?q=stripe+vs+paypal&t=h_&ia=web"}
    assert EdgeVisitorClassifier.extract_search_query(headers=headers) == "stripe vs paypal"


def test_url_parameter_extraction():
    """Extracts search query from URL parameters (?q=, ?s=, ?query=)."""
    assert EdgeVisitorClassifier.extract_search_query(url="https://example.com/page?q=hvac+sizing+tool") == "hvac sizing tool"
    assert EdgeVisitorClassifier.extract_search_query(url="/page?s=clean+energy+matrix") == "clean energy matrix"
    assert EdgeVisitorClassifier.extract_search_query(url="?query=invoice+generator+tool") == "invoice generator tool"


def test_url_parameter_precedence_over_referer():
    """URL query parameters take precedence over incoming referer header."""
    headers = {"referer": "https://www.google.com/url?q=old+query"}
    url = "https://example.com/?q=new+specific+tool"
    assert EdgeVisitorClassifier.extract_search_query(headers=headers, url=url) == "new specific tool"


def test_direct_traffic_no_query():
    """Direct traffic without search query returns None."""
    assert EdgeVisitorClassifier.extract_search_query(headers={}, url="/tools/calculator/") is None
    assert EdgeVisitorClassifier.extract_search_query(headers={"referer": "https://example.com/internal/"}) is None


def test_multi_archetype_intent_classification():
    """
    Validates classification of all 6 Search Intent Doctrine archetypes:
    1. Statutory calculations / deductions -> interactive_calculator (1.0)
    2. Statutory matrices / rules -> statutory_matrix (1.0)
    3. Competitor / product comparisons -> comparison_engine (0.7)
    4. General tools -> interactive_calculator (0.8)
    5. Noise / memes -> REJECT / noise (0.05)
    6. Informational -> void_documentation (0.3)
    """
    classifier = EdgeVisitorClassifier()

    # 1. Statutory calculations / deductions
    calc_intent_1 = classifier.classify("section 179 deduction calculator")
    assert calc_intent_1.target_asset_type == "interactive_calculator"
    assert calc_intent_1.intent_weight == 1.0

    calc_intent_2 = classifier.classify("form 8829 deduction")
    assert calc_intent_2.target_asset_type == "interactive_calculator"
    assert calc_intent_2.intent_weight == 1.0

    calc_intent_3 = classifier.classify("statutory calculations for payroll")
    assert calc_intent_3.target_asset_type == "interactive_calculator"
    assert calc_intent_3.intent_weight == 1.0

    # 2. Statutory matrices / rules
    matrix_intent_1 = classifier.classify("commercial clean energy matrix")
    assert matrix_intent_1.target_asset_type == "statutory_matrix"
    assert matrix_intent_1.intent_weight == 1.0

    matrix_intent_2 = classifier.classify("statutory rules for capital depreciation")
    assert matrix_intent_2.target_asset_type == "statutory_matrix"
    assert matrix_intent_2.intent_weight == 1.0

    # 3. Competitor / product comparisons
    comp_intent_1 = classifier.classify("stripe vs paypal fee comparison")
    assert comp_intent_1.target_asset_type == "comparison_engine"
    assert comp_intent_1.intent_weight == 0.7

    comp_intent_2 = classifier.classify("gusto compare adp payroll")
    assert comp_intent_2.target_asset_type == "comparison_engine"
    assert comp_intent_2.intent_weight == 0.7

    # 4. General tools
    tool_intent_1 = classifier.classify("hvac load sizing tool")
    assert tool_intent_1.target_asset_type == "interactive_calculator"
    assert tool_intent_1.intent_weight == 0.8

    tool_intent_2 = classifier.classify("invoice generator tool")
    assert tool_intent_2.target_asset_type == "interactive_calculator"
    assert tool_intent_2.intent_weight == 0.8

    # 5. Noise / memes -> REJECT / noise
    noise_intent_1 = classifier.classify("super bowl halftime meme dance")
    assert noise_intent_1.target_asset_type in ("noise", "REJECT")
    assert noise_intent_1.intent_weight == 0.05
    assert noise_intent_1.action == "REJECT"
    assert noise_intent_1.is_noise is True

    noise_intent_2 = classifier.classify("celebrity gossip leak")
    assert noise_intent_2.target_asset_type in ("noise", "REJECT")
    assert noise_intent_2.intent_weight == 0.05
    assert noise_intent_2.action == "REJECT"
    assert noise_intent_2.is_noise is True

    # 6. Informational -> void_documentation
    info_intent = classifier.classify("what is section 179 depreciation")
    assert info_intent.target_asset_type == "void_documentation"
    assert info_intent.intent_weight == 0.3


def test_route_action_rewrite_to_cluster():
    """REWRITE_TO_CLUSTER when visitor query matches a high-yield cluster different from current path."""
    routes_map = {
        "/tools/section-179-calculator/": {
            "target_asset_type": "interactive_calculator",
            "cluster": "calculator",
            "keywords": ["section 179 deduction calculator"],
        },
        "/matrices/energy/": {
            "target_asset_type": "statutory_matrix",
            "cluster": "statutory_compliance",
        },
    }
    router = EdgeIntentRouter(routes_map=routes_map)

    # Visitor arrives on informational article with high-yield calculator search intent
    decision = router.route(
        current_path="/articles/tax-writeoffs-overview/",
        query="section 179 deduction calculator",
    )
    assert decision.action == "REWRITE_TO_CLUSTER"
    assert decision.target_path == "/tools/section-179-calculator/"
    assert "rewrite" in decision.reason.lower()


def test_route_action_inject_overlay():
    """INJECT_OVERLAY when visitor query matches striking-distance keyword on current page."""
    routes_map = {
        "/tools/section-179-calculator/": {
            "target_asset_type": "interactive_calculator",
            "cluster": "calculator",
            "striking_distance": [
                "section 179 deduction limits",
                "equipment depreciation cap",
            ],
        }
    }
    router = EdgeIntentRouter(routes_map=routes_map)

    decision = router.route(
        current_path="/tools/section-179-calculator/",
        query="section 179 deduction limits",
    )
    assert decision.action == "INJECT_OVERLAY"
    assert decision.target_path == "/tools/section-179-calculator/"
    assert decision.overlay_keyword == "section 179 deduction limits"


def test_route_action_pass_through():
    """PASS_THROUGH when no intent mismatch exists."""
    routes_map = {
        "/tools/section-179-calculator/": {
            "target_asset_type": "interactive_calculator",
            "cluster": "calculator",
            "keywords": ["section 179 deduction calculator"],
        }
    }
    router = EdgeIntentRouter(routes_map=routes_map)

    # 1. Visitor is already on target cluster page
    decision_same = router.route(
        current_path="/tools/section-179-calculator/",
        query="section 179 deduction calculator",
    )
    assert decision_same.action == "PASS_THROUGH"

    # 2. Direct traffic without query
    decision_direct = router.route(
        current_path="/tools/section-179-calculator/",
        query=None,
    )
    assert decision_direct.action == "PASS_THROUGH"

    # 3. Noise query
    decision_noise = router.route(
        current_path="/tools/section-179-calculator/",
        query="funny meme parody dance",
    )
    assert decision_noise.action == "PASS_THROUGH"

    # 4. Informational query on informational page
    decision_info = router.route(
        current_path="/guides/general/",
        query="what is section 179",
    )
    assert decision_info.action == "PASS_THROUGH"


def test_cloudflare_worker_script_generation():
    """Generates a valid production Cloudflare Worker script and verifies syntax."""
    routes_map = {
        "/tools/section-179-calculator/": {
            "target_asset_type": "interactive_calculator",
            "cluster": "calculator",
            "striking_distance": ["section 179 deduction limits"],
        },
        "/matrices/energy/": {
            "target_asset_type": "statutory_matrix",
            "cluster": "statutory_compliance",
        },
    }
    script = generate_edge_worker_script(routes_map=routes_map)

    assert isinstance(script, str)
    assert "export default" in script
    assert "async fetch(request" in script
    assert "REWRITE_TO_CLUSTER" in script
    assert "INJECT_OVERLAY" in script
    assert "PASS_THROUGH" in script
    assert "extractSearchQuery" in script
    assert "classifyVisitorIntent" in script
    assert "determineEdgeRoute" in script

    # Verify zero forbidden dashes invariant in generated script
    assert_no_forbidden_dashes(script, "test_cloudflare_worker_script_generation")

    # If node is installed, verify JS syntax
    if shutil.which("node"):
        with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False) as tmp:
            tmp.write(script)
            tmp_path = tmp.name
        try:
            res = subprocess.run(["node", "--check", tmp_path], capture_output=True, text=True)
            assert res.returncode == 0, f"Node syntax check failed: {res.stderr}"
        finally:
            import os
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


def test_zero_forbidden_dashes_invariant_check():
    """Enforces zero em-dashes (U+2014) and zero en-dashes (U+2013) invariant."""
    classifier = EdgeVisitorClassifier()

    # Em-dash (\u2014) must raise ValueError
    with pytest.raises(ValueError, match="Forbidden em-dash"):
        classifier.classify("section 179 \u2014 calculator")

    # En-dash (\u2013) must raise ValueError
    with pytest.raises(ValueError, match="Forbidden en-dash"):
        classifier.classify("section 179 \u2013 calculator")

    # Valid regular hyphens must pass
    valid_intent = classifier.classify("section 179-calculator")
    assert valid_intent.target_asset_type == "interactive_calculator"
