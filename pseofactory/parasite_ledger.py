"""
Parasite syndication survival ledger (x-like:2103576504143634852, ch. 2/20/23).

Records every third-party (parasite) URL the engine syndicates, rechecks it for
liveness, indexing, rank and AI citation, and turns the history into a per-tenant
platform ranking so future syndication favors platforms whose pages survive.

Indexing, rank and AI-citation probes are injectable. A probe that is not supplied
records None ("unknown"); unknown is never counted as success or failure.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import fcntl
import json
import os
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

DEFAULT_PARASITE_LEDGER_PATH = Path("/home/ubuntuadmin/projects/.agy/runs/parasite_ledger.json")

LIVE = "live"
REMOVED = "removed"
UNREACHABLE = "unreachable"

Probe = Callable[[str], Optional[Any]]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_fetcher(url: str, timeout: float = 10.0) -> int:
    """Return the final HTTP status for url, or 0 when unreachable."""
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "pseofactory-parasite-ledger/1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except Exception:
        return 0


def classify_status(status: int) -> str:
    if 200 <= status < 300:
        return LIVE
    if status in (404, 410, 451) or status in (401, 403):
        return REMOVED
    return UNREACHABLE


class ParasiteLedger:
    def __init__(self, path: Optional[Union[str, Path]] = None):
        self.path = Path(path) if path is not None else DEFAULT_PARASITE_LEDGER_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.path.with_suffix(".lock")

    def _mutate(self, fn: Callable[[Dict[str, Any]], Any]) -> Any:
        with open(self.lock_path, "a+", encoding="utf-8") as lock_f:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
            try:
                records = self._load()
                result = fn(records)
                tmp = self.path.with_suffix(f".tmp.{os.getpid()}_{uuid.uuid4().hex[:8]}")
                with open(tmp, "w", encoding="utf-8") as tf:
                    tf.write(json.dumps(records, indent=2, sort_keys=True))
                    tf.flush()
                    os.fsync(tf.fileno())
                os.replace(tmp, self.path)
                return result
            finally:
                fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def records(self) -> Dict[str, Any]:
        return self._load()

    def record_post(
        self,
        url: str,
        platform: str,
        tenant: str,
        keyword: str = "",
        tool_slug: str = "",
    ) -> bool:
        """Register a syndicated URL. Returns True if new, False if already tracked."""

        def _do(records: Dict[str, Any]) -> bool:
            if url in records:
                return False
            records[url] = {
                "url": url,
                "platform": platform.lower(),
                "tenant": tenant,
                "keyword": keyword,
                "tool_slug": tool_slug,
                "posted_at": _now(),
                "checks": [],
            }
            return True

        return bool(self._mutate(_do))

    def check_all(
        self,
        fetcher: Callable[[str], int] = default_fetcher,
        index_probe: Optional[Probe] = None,
        rank_probe: Optional[Probe] = None,
        ai_citation_probe: Optional[Probe] = None,
    ) -> Dict[str, Any]:
        """Recheck every tracked URL once and append a check row to its history."""
        urls = list(self._load().keys())
        results: Dict[str, Any] = {}
        for url in urls:
            status = fetcher(url)
            state = classify_status(status)
            row = {
                "checked_at": _now(),
                "http_status": status,
                "state": state,
                "indexed": index_probe(url) if index_probe and state == LIVE else None,
                "rank": rank_probe(url) if rank_probe and state == LIVE else None,
                "ai_cited": ai_citation_probe(url) if ai_citation_probe and state == LIVE else None,
            }
            results[url] = row

        def _do(records: Dict[str, Any]) -> None:
            for url, row in results.items():
                if url in records:
                    records[url]["checks"].append(row)

        self._mutate(_do)
        return results

    @staticmethod
    def _latest(rec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return rec["checks"][-1] if rec.get("checks") else None

    def platform_scores(self, tenant: Optional[str] = None, keyword: Optional[str] = None) -> List[Dict[str, Any]]:
        """Rank platforms by survival, then indexing, then AI citation. Unchecked pages are excluded."""
        buckets: Dict[str, Dict[str, int]] = {}
        for rec in self._load().values():
            if tenant and rec.get("tenant") != tenant:
                continue
            if keyword and rec.get("keyword") != keyword:
                continue
            latest = self._latest(rec)
            if latest is None:
                continue
            b = buckets.setdefault(rec["platform"], {"n": 0, "live": 0, "indexed": 0, "indexed_known": 0, "cited": 0})
            b["n"] += 1
            b["live"] += latest["state"] == LIVE
            if latest.get("indexed") is not None:
                b["indexed_known"] += 1
                b["indexed"] += bool(latest["indexed"])
            b["cited"] += bool(latest.get("ai_cited"))
        scores = []
        for platform, b in buckets.items():
            scores.append(
                {
                    "platform": platform,
                    "pages": b["n"],
                    "survival_rate": b["live"] / b["n"],
                    "indexed_rate": (b["indexed"] / b["indexed_known"]) if b["indexed_known"] else None,
                    "ai_citation_rate": b["cited"] / b["n"],
                }
            )
        scores.sort(
            key=lambda s: (s["survival_rate"], s["indexed_rate"] or 0.0, s["ai_citation_rate"], s["pages"]),
            reverse=True,
        )
        return scores

    def recommend_platforms(self, tenant: str, keyword: Optional[str] = None, min_pages: int = 1) -> List[str]:
        """Platforms ordered best-first for this tenant; keyword-specific evidence wins when present."""
        scored = self.platform_scores(tenant=tenant, keyword=keyword) if keyword else []
        if not any(s["pages"] >= min_pages for s in scored):
            scored = self.platform_scores(tenant=tenant)
        return [s["platform"] for s in scored if s["pages"] >= min_pages and s["survival_rate"] > 0]
