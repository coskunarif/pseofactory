"""
pseofactory Streaming Suggest & Breakout Feed Collectors
Harvesters for Google suggest, YouTube suggest, Reddit autocomplete, HackerNews Algolia, and Google Trends RSS.
Retry ceiling <= 2, timeout <= 5s, error resilient.
Zero em-dashes. Zero en-dashes.
"""

import json
import time
import urllib.parse
import urllib.request
import urllib.error
import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from pseofactory.trends.models import FeedSpike
from pseofactory.contracts import assert_no_forbidden_dashes


DEFAULT_USER_AGENT = "pseofactory-trend-agent/1.0 (Linux; x86_64)"
MAX_RETRIES = 2
DEFAULT_TIMEOUT = 5.0


def make_resilient_request(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = MAX_RETRIES,
) -> Optional[bytes]:
    """
    Executes HTTP GET request with retry ceiling <= 2 and timeout <= 5.0s.
    Returns bytes on success or None on complete failure.
    Zero em-dashes. Zero en-dashes.
    """
    req_headers = {"User-Agent": DEFAULT_USER_AGENT}
    if headers:
        req_headers.update(headers)

    eff_timeout = min(float(timeout), 5.0)
    eff_retries = min(int(retries), 2)

    req = urllib.request.Request(url, headers=req_headers)
    for attempt in range(eff_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=eff_timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
            if attempt < eff_retries:
                time.sleep(0.05 * (2 ** attempt))
            else:
                return None
    return None


def generate_spike_id(source: str, query: str, timestamp: str) -> str:
    """Generates deterministic SHA-256 ID prefix for a spike."""
    bucket = timestamp[:13] if len(timestamp) >= 13 else timestamp
    token = f"{source}:{query.lower().strip()}:{bucket}"
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


class BaseSuggestCollector:
    """Base class for streaming suggestion collectors."""

    def __init__(self, source_name: str, timeout: float = DEFAULT_TIMEOUT, retries: int = MAX_RETRIES):
        self.source_name = source_name
        self.timeout = min(float(timeout), 5.0)
        self.retries = min(int(retries), 2)

    def fetch_suggestions(self, query: str) -> List[str]:
        raise NotImplementedError

    def harvest_spikes(self, seed_query: str) -> List[FeedSpike]:
        suggestions = self.fetch_suggestions(seed_query)
        spikes: List[FeedSpike] = []
        now = datetime.now(timezone.utc).isoformat()
        for idx, term in enumerate(suggestions):
            clean_term = term.strip()
            if not clean_term:
                continue
            spike_id = generate_spike_id(self.source_name, clean_term, now)
            # Ranking position in autocomplete serves as default velocity proxy
            velocity = max(1.0, 50.0 - (idx * 4.0))
            spikes.append(
                FeedSpike(
                    id=spike_id,
                    query=clean_term,
                    source=self.source_name,
                    detected_at=now,
                    sample_count=int(velocity * 10),
                    velocity=velocity,
                    acceleration=2.0 if idx < 3 else 0.5,
                    z_score=2.5 if idx < 3 else 1.8,
                    baseline_mean=10.0,
                    baseline_std=3.0,
                    raw_payload={"seed": seed_query, "rank": idx},
                )
            )
        return spikes


class GoogleSuggestCollector(BaseSuggestCollector):
    """Harvester for Google Chrome complete search suggestions."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT, retries: int = MAX_RETRIES):
        super().__init__("google_suggest", timeout=timeout, retries=retries)

    def fetch_suggestions(self, query: str) -> List[str]:
        q_enc = urllib.parse.quote(query.strip())
        url = f"https://suggestqueries.google.com/complete/search?client=chrome&q={q_enc}"
        data = make_resilient_request(url, timeout=self.timeout, retries=self.retries)
        if not data:
            return []
        try:
            parsed = json.loads(data.decode("utf-8", errors="ignore"))
            if isinstance(parsed, list) and len(parsed) >= 2 and isinstance(parsed[1], list):
                return [str(s) for s in parsed[1] if s]
        except Exception:
            pass
        return []


class YouTubeSuggestCollector(BaseSuggestCollector):
    """Harvester for YouTube complete search suggestions."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT, retries: int = MAX_RETRIES):
        super().__init__("youtube_suggest", timeout=timeout, retries=retries)

    def fetch_suggestions(self, query: str) -> List[str]:
        q_enc = urllib.parse.quote(query.strip())
        url = f"https://suggestqueries.google.com/complete/search?client=youtube&ds=yt&q={q_enc}"
        data = make_resilient_request(url, timeout=self.timeout, retries=self.retries)
        if not data:
            return []
        try:
            parsed = json.loads(data.decode("utf-8", errors="ignore"))
            if isinstance(parsed, list) and len(parsed) >= 2 and isinstance(parsed[1], list):
                return [str(s) for s in parsed[1] if s]
        except Exception:
            pass
        return []


class RedditSuggestCollector(BaseSuggestCollector):
    """Harvester for Reddit subreddit and search autocomplete."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT, retries: int = MAX_RETRIES):
        super().__init__("reddit_autocomplete", timeout=timeout, retries=retries)

    def fetch_suggestions(self, query: str) -> List[str]:
        q_enc = urllib.parse.quote(query.strip())
        url = f"https://www.reddit.com/api/subreddit_autocomplete_v2.json?query={q_enc}"
        headers = {"User-Agent": "Mozilla/5.0 (Linux; pseofactory-reddit-bot/1.0)"}
        data = make_resilient_request(url, headers=headers, timeout=self.timeout, retries=self.retries)
        if not data:
            return []
        try:
            parsed = json.loads(data.decode("utf-8", errors="ignore"))
            results: List[str] = []
            if isinstance(parsed, dict) and "data" in parsed:
                children = parsed["data"].get("children", [])
                for child in children:
                    d = child.get("data", {})
                    title = d.get("title") or d.get("display_name_prefixed") or d.get("name")
                    if title:
                        results.append(str(title).replace("r/", "").replace("_", " "))
            return results
        except Exception:
            pass
        return []


class HackerNewsCollector(BaseSuggestCollector):
    """Harvester for Hacker News Algolia search API."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT, retries: int = MAX_RETRIES):
        super().__init__("hn_search", timeout=timeout, retries=retries)

    def fetch_suggestions(self, query: str) -> List[str]:
        q_enc = urllib.parse.quote(query.strip())
        url = f"https://hn.algolia.com/api/v1/search?query={q_enc}&tags=story&hitsPerPage=10"
        data = make_resilient_request(url, timeout=self.timeout, retries=self.retries)
        if not data:
            return []
        try:
            parsed = json.loads(data.decode("utf-8", errors="ignore"))
            hits = parsed.get("hits", [])
            titles: List[str] = []
            for h in hits:
                t = h.get("title")
                if t:
                    titles.append(str(t))
            return titles
        except Exception:
            pass
        return []


class GoogleTrendsRSSCollector(BaseSuggestCollector):
    """Harvester for Google Trends Daily RSS Feed."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT, retries: int = MAX_RETRIES, geo: str = "US"):
        super().__init__("google_trends_rss", timeout=timeout, retries=retries)
        self.geo = geo

    def fetch_suggestions(self, query: str = "") -> List[str]:
        url = f"https://trends.google.com/trending/rss?geo={self.geo}"
        data = make_resilient_request(url, timeout=self.timeout, retries=self.retries)
        if not data:
            return []
        try:
            root = ET.fromstring(data)
            items = root.findall(".//item")
            topics: List[str] = []
            for item in items:
                title = item.find("title")
                if title is not None and title.text:
                    topics.append(title.text.strip())
            return topics
        except Exception:
            pass
        return []


class MultiSourceCollector:
    """Coordinates multi-source streaming suggest ingestion across diverse providers."""

    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = MAX_RETRIES,
        collectors: Optional[List[BaseSuggestCollector]] = None,
    ):
        self.timeout = min(float(timeout), 5.0)
        self.retries = min(int(retries), 2)
        if collectors is not None:
            self.collectors = collectors
        else:
            self.collectors = [
                GoogleSuggestCollector(timeout=self.timeout, retries=self.retries),
                YouTubeSuggestCollector(timeout=self.timeout, retries=self.retries),
                RedditSuggestCollector(timeout=self.timeout, retries=self.retries),
                HackerNewsCollector(timeout=self.timeout, retries=self.retries),
                GoogleTrendsRSSCollector(timeout=self.timeout, retries=self.retries),
            ]

    def harvest(self, seed_queries: List[str]) -> List[FeedSpike]:
        """Harvests spikes across all configured collectors for the given seed queries."""
        all_spikes: List[FeedSpike] = []
        seen_queries = set()

        for collector in self.collectors:
            if isinstance(collector, GoogleTrendsRSSCollector):
                try:
                    trends = collector.fetch_suggestions("")
                    now = datetime.now(timezone.utc).isoformat()
                    for idx, topic in enumerate(trends):
                        clean_topic = topic.strip()
                        q_key = clean_topic.lower()
                        if clean_topic and q_key not in seen_queries:
                            seen_queries.add(q_key)
                            spike_id = generate_spike_id(collector.source_name, clean_topic, now)
                            all_spikes.append(
                                FeedSpike(
                                    id=spike_id,
                                    query=clean_topic,
                                    source=collector.source_name,
                                    detected_at=now,
                                    sample_count=2000,
                                    velocity=80.0,
                                    acceleration=15.0,
                                    z_score=3.5,
                                    baseline_mean=10.0,
                                    baseline_std=3.0,
                                    raw_payload={"rank": idx},
                                )
                            )
                except Exception:
                    pass

            for seed in seed_queries:
                try:
                    spikes = collector.harvest_spikes(seed)
                    for s in spikes:
                        q_key = s.query.lower().strip()
                        if q_key and q_key not in seen_queries:
                            seen_queries.add(q_key)
                            all_spikes.append(s)
                except Exception:
                    pass

        return all_spikes
