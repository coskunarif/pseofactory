"""
Tests for pseofactory trend collectors.
Verifies multi-source suggest harvesters, retry ceilings, timeout bounds, and error resilience.
Zero em-dashes. Zero en-dashes.
"""

import json
from unittest.mock import patch, MagicMock
from urllib.error import URLError

from pseofactory.trends.collectors import (
    GoogleSuggestCollector,
    YouTubeSuggestCollector,
    RedditSuggestCollector,
    HackerNewsCollector,
    GoogleTrendsRSSCollector,
    MultiSourceCollector,
    make_resilient_request,
    generate_spike_id,
)
from pseofactory.trends.models import FeedSpike


def test_make_resilient_request_success():
    """Verifies make_resilient_request succeeds on valid 200 response."""
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"status": "ok"}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        data = make_resilient_request("https://example.com/api", timeout=3.0, retries=1)
        assert data == b'{"status": "ok"}'


def test_make_resilient_request_timeout_and_retries():
    """Verifies make_resilient_request enforces retry ceiling and returns None on persistent error."""
    with patch("urllib.request.urlopen", side_effect=URLError("Connection refused")) as mock_urlopen:
        data = make_resilient_request("https://example.com/fail", timeout=10.0, retries=5)
        assert data is None
        # Enforces retry ceiling <= 2 (attempt 0, 1, 2 = 3 calls total)
        assert mock_urlopen.call_count == 3


def test_google_suggest_collector():
    """Verifies GoogleSuggestCollector parses chrome suggest JSON array."""
    sample_json = json.dumps(["loan", ["loan calculator", "loan payment estimator", "loan payoff schedule"]]).encode()
    collector = GoogleSuggestCollector(timeout=4.0, retries=2)
    assert collector.timeout == 4.0
    assert collector.retries == 2

    with patch("pseofactory.trends.collectors.make_resilient_request", return_value=sample_json):
        suggestions = collector.fetch_suggestions("loan")
        assert len(suggestions) == 3
        assert "loan calculator" in suggestions

        spikes = collector.harvest_spikes("loan")
        assert len(spikes) == 3
        assert all(isinstance(s, FeedSpike) for s in spikes)
        assert spikes[0].query == "loan calculator"
        assert spikes[0].source == "google_suggest"
        assert spikes[0].velocity > spikes[1].velocity


def test_youtube_suggest_collector():
    """Verifies YouTubeSuggestCollector parses complete suggest responses."""
    sample_json = json.dumps(["tax", ["tax bracket breakdown", "tax deduction tutorial"]]).encode()
    collector = YouTubeSuggestCollector()

    with patch("pseofactory.trends.collectors.make_resilient_request", return_value=sample_json):
        suggestions = collector.fetch_suggestions("tax")
        assert len(suggestions) == 2
        assert suggestions[0] == "tax bracket breakdown"


def test_reddit_suggest_collector():
    """Verifies RedditSuggestCollector parses subreddit autocomplete JSON."""
    sample_payload = json.dumps({
        "data": {
            "children": [
                {"data": {"title": "r/personalfinance"}},
                {"data": {"name": "financialindependence"}},
            ]
        }
    }).encode()
    collector = RedditSuggestCollector()

    with patch("pseofactory.trends.collectors.make_resilient_request", return_value=sample_payload):
        suggestions = collector.fetch_suggestions("finance")
        assert len(suggestions) == 2
        assert "personalfinance" in suggestions


def test_hackernews_collector():
    """Verifies HackerNewsCollector parses Algolia hits."""
    sample_payload = json.dumps({
        "hits": [
            {"title": "Show HN: Fast SQLite Vector Search"},
            {"title": "Ask HN: How do you track programmatic SEO?"},
        ]
    }).encode()
    collector = HackerNewsCollector()

    with patch("pseofactory.trends.collectors.make_resilient_request", return_value=sample_payload):
        suggestions = collector.fetch_suggestions("vector")
        assert len(suggestions) == 2
        assert "Show HN: Fast SQLite Vector Search" in suggestions


def test_google_trends_rss_collector():
    """Verifies GoogleTrendsRSSCollector parses daily RSS XML."""
    sample_rss = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Daily Search Trends</title>
        <item>
          <title>Section 179 Clean Energy Deduction</title>
        </item>
        <item>
          <title>Mortgage Refinance Rates 2026</title>
        </item>
      </channel>
    </rss>
    """
    collector = GoogleTrendsRSSCollector()

    with patch("pseofactory.trends.collectors.make_resilient_request", return_value=sample_rss):
        topics = collector.fetch_suggestions()
        assert len(topics) == 2
        assert topics[0] == "Section 179 Clean Energy Deduction"
        assert topics[1] == "Mortgage Refinance Rates 2026"


def test_multi_source_collector_deduplication():
    """Verifies MultiSourceCollector aggregates across providers and deduplicates queries."""
    c1 = GoogleSuggestCollector()
    c2 = YouTubeSuggestCollector()

    json1 = json.dumps(["loan", ["direct consolidation loan", "loan calculator"]]).encode()
    json2 = json.dumps(["loan", ["loan calculator", "student loan repayment"]]).encode()

    multi = MultiSourceCollector(collectors=[c1, c2])

    with patch("pseofactory.trends.collectors.make_resilient_request") as mock_req:
        mock_req.side_effect = [json1, json2]
        spikes = multi.harvest(["loan"])

        queries = [s.query for s in spikes]
        assert len(queries) == 3
        assert len(set(queries)) == 3
        assert "direct consolidation loan" in queries
        assert "loan calculator" in queries
        assert "student loan repayment" in queries


def test_generate_spike_id_deterministic():
    """Verifies spike ID is consistent and deterministic."""
    id1 = generate_spike_id("google_suggest", "form 8829 calculator", "2026-10-08T08:00:00Z")
    id2 = generate_spike_id("google_suggest", "form 8829 calculator", "2026-10-08T08:30:00Z")
    id3 = generate_spike_id("youtube_suggest", "form 8829 calculator", "2026-10-08T08:00:00Z")
    assert id1 == id2
    assert id1 != id3
