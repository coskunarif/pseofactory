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
                    acceleration=6.0 if idx < 3 else 0.5,
                    z_score=3.2 if idx < 3 else 1.8,
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


class GSCSearchConsoleCollector(BaseSuggestCollector):
    """
    Harvester for persisted and live Google Search Console multi-dimensional telemetry.
    Surfaces breakout queries (recent_28d vs prior_28d_baseline), striking-distance queries (pos 4-20),
    and mobile CTR deficit queries directly into the upstream discovery pipeline.
    """

    def __init__(
        self,
        db_path: Optional[Any] = None,
        properties: Optional[List[str]] = None,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = MAX_RETRIES,
    ):
        super().__init__("gsc_search_console", timeout=timeout, retries=retries)
        self.db_path = db_path
        self.properties = properties or ["profithelm", "prexvo"]

    def fetch_suggestions(self, query: str = "") -> List[str]:
        spikes = self.harvest_gsc_spikes(seed_filter=query)
        return [s.query for s in spikes]

    def harvest_gsc_spikes(self, seed_filter: str = "") -> List[FeedSpike]:
        from pseofactory.trends.db import DEFAULT_DB_PATH, TrendHistoryDB

        target_db = self.db_path or DEFAULT_DB_PATH
        try:
            tdb = TrendHistoryDB(target_db)
        except Exception:
            return []

        now = datetime.now(timezone.utc).isoformat()
        results: List[FeedSpike] = []
        seen: set[str] = set()
        seed_low = str(seed_filter or "").strip().lower()

        for prop in self.properties:
            try:
                recent_rows = tdb.get_gsc_query_page_windows(prop, window_key="recent_28d")
                prior_rows = tdb.get_gsc_query_page_windows(prop, window_key="prior_28d_baseline")
                dev_rows = tdb.get_gsc_device_metrics(prop, window_key="recent_90d") or tdb.get_gsc_device_metrics(prop, window_key="recent_28d")
                sa_rows = tdb.get_gsc_search_appearance_metrics(prop, window_key="recent_90d")
            except Exception:
                continue

            prior_map = {(r.page, r.query.lower()): r for r in prior_rows}
            dev_by_qp: Dict[tuple[str, str], Dict[str, Any]] = {}
            for dr in dev_rows:
                if dr.query and dr.page:
                    dev_by_qp.setdefault((dr.page, dr.query.lower()), {})[dr.device] = {
                        "clicks": dr.clicks,
                        "impressions": dr.impressions,
                        "ctr": dr.ctr,
                        "position": dr.position,
                    }
            sa_names = [s.search_appearance for s in sa_rows]

            for r in recent_rows:
                q_clean = r.query.strip()
                q_low = q_clean.lower()
                if not q_clean or q_low in seen:
                    continue
                if seed_low and seed_low not in q_low and q_low not in seed_low:
                    continue
                prior = prior_map.get((r.page, q_low))
                prior_imp = prior.impressions if prior else 0
                imp_delta = r.impressions - prior_imp
                pos_delta = (prior.position - r.position) if (prior and prior.position > 0 and r.position > 0) else 0.0

                dev_info = dev_by_qp.get((r.page, q_low), {})
                mob_ctr = float((dev_info.get("MOBILE") or {}).get("ctr", 0.0) or 0.0)
                desk_ctr = float((dev_info.get("DESKTOP") or {}).get("ctr", 0.0) or 0.0)
                mob_ctr_gap = round(desk_ctr - mob_ctr, 4)

                # Qualify if breakout impressions, striking distance (4..20), or mobile CTR deficit
                if r.impressions < 2 and imp_delta <= 0:
                    continue
                seen.add(q_low)
                velocity = round(max(25.0, float(r.impressions) * 4.0 + max(0.0, imp_delta * 3.0)), 2)
                accel = round(max(2.0, float(imp_delta) * 1.5 + max(0.0, pos_delta * 2.0)), 2)
                z_val = round(min(6.0, 2.0 + (r.impressions / 20.0) + (0.5 if 4.0 <= r.position <= 20.0 else 0.0)), 2)
                spike_id = generate_spike_id(self.source_name, q_clean, now)
                results.append(
                    FeedSpike(
                        id=spike_id,
                        query=q_clean,
                        source=self.source_name,
                        detected_at=now,
                        sample_count=max(100, r.impressions * 25),
                        velocity=velocity,
                        acceleration=accel,
                        z_score=z_val,
                        baseline_mean=float(max(1, prior_imp)),
                        baseline_std=2.5,
                        raw_payload={
                            "property_id": prop,
                            "page": r.page,
                            "impressions": r.impressions,
                            "clicks": r.clicks,
                            "ctr": r.ctr,
                            "current_position": r.position,
                            "prior_28d_impressions": prior_imp,
                            "mobile_ctr": mob_ctr,
                            "desktop_ctr": desk_ctr,
                            "mobile_ctr_gap": mob_ctr_gap,
                            "search_appearances": sa_names,
                            "gsc_telemetry": {
                                "property_id": prop,
                                "page": r.page,
                                "impressions": r.impressions,
                                "clicks": r.clicks,
                                "ctr": r.ctr,
                                "position": r.position,
                                "prior_28d_impressions": prior_imp,
                                "mobile_ctr": mob_ctr,
                                "desktop_ctr": desk_ctr,
                                "mobile_ctr_gap": mob_ctr_gap,
                                "search_appearances": sa_names,
                            },
                        },
                    )
                )
        return results


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
            if isinstance(collector, GSCSearchConsoleCollector):
                try:
                    for s in collector.harvest_gsc_spikes():
                        q_key = s.query.lower().strip()
                        if q_key and q_key not in seen_queries:
                            seen_queries.add(q_key)
                            all_spikes.append(s)
                except Exception:
                    pass
                continue

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
