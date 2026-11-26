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
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

DEFAULT_PARASITE_LEDGER_PATH = Path("/home/ubuntuadmin/projects/.agy/runs/parasite_ledger.json")
EXTERNAL_AUTHORITY_LEDGER_FILENAME = "external_authority_ledger.json"

LIVE = "live"
REMOVED = "removed"
UNREACHABLE = "unreachable"

AUTHORITY_SURFACE_EMBED = "embed"
AUTHORITY_SURFACE_GITHUB_REPO = "github_repo"
AUTHORITY_SURFACE_DIRECTORY = "directory"
VALID_AUTHORITY_SURFACES = (
    AUTHORITY_SURFACE_EMBED,
    AUTHORITY_SURFACE_GITHUB_REPO,
    AUTHORITY_SURFACE_DIRECTORY,
)
ALLOWED_B2B_DIRECTORY_PLATFORMS = ("crunchbase", "alternativeto", "g2", "f6s")

Probe = Callable[[str], Optional[Any]]


def resolve_tenant_external_authority_ledger_path(repo_root: Union[str, Path]) -> Path:
    """Return the per-tenant .agy/external_authority_ledger.json path."""
    return Path(repo_root) / ".agy" / EXTERNAL_AUTHORITY_LEDGER_FILENAME


def _normalize_domain(raw_domain: str) -> str:
    cleaned = str(raw_domain or "").strip().lower()
    if "://" in cleaned:
        cleaned = urllib.parse.urlparse(cleaned).hostname or cleaned
    cleaned = cleaned.split("/", 1)[0].split(":", 1)[0].strip(".")
    if cleaned.startswith("www."):
        cleaned = cleaned[4:]
    return cleaned


class _AnchorExtractor(HTMLParser):
    """Minimal stdlib HTML anchor extractor for attribution verification."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: List[Dict[str, Any]] = []
        self._current: Optional[Dict[str, Any]] = None

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag.lower() != "a":
            return
        attr_map = {str(k).lower(): ("" if v is None else str(v)) for k, v in attrs}
        self._current = {
            "href": attr_map.get("href", "").strip(),
            "rel": [tok.lower() for tok in attr_map.get("rel", "").split() if tok.strip()],
            "text_parts": [],
        }

    def handle_data(self, data: str) -> None:
        if self._current is not None:
            self._current["text_parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._current is not None:
            self._current["anchor_text"] = " ".join("".join(self._current.pop("text_parts")).split())
            self.anchors.append(self._current)
            self._current = None


def verify_embed_attribution_html(html: str, target_domain: str) -> Dict[str, Any]:
    """Verify that embedded HTML links to target_domain with rel='nofollow'."""
    norm_target = _normalize_domain(target_domain)
    if not norm_target:
        return {
            "valid": False,
            "has_target_link": False,
            "has_nofollow": False,
            "matching_links": [],
            "reason": "INVALID_TARGET_DOMAIN",
        }
    parser = _AnchorExtractor()
    try:
        parser.feed(str(html or ""))
        parser.close()
    except Exception:
        pass

    matching_links: List[Dict[str, Any]] = []
    for anchor in parser.anchors:
        href = anchor.get("href", "")
        if not href:
            continue
        parsed = urllib.parse.urlparse(href)
        host = _normalize_domain(parsed.hostname or "")
        if not host:
            continue
        if host == norm_target or host.endswith(f".{norm_target}"):
            rel_tokens = list(anchor.get("rel") or [])
            has_nf = "nofollow" in rel_tokens
            matching_links.append(
                {
                    "href": href,
                    "rel": rel_tokens,
                    "anchor_text": anchor.get("anchor_text", ""),
                    "has_nofollow": has_nf,
                }
            )

    has_target_link = bool(matching_links)
    has_nofollow = bool(matching_links) and all(link["has_nofollow"] for link in matching_links)
    if not has_target_link:
        reason = "MISSING_TARGET_LINK"
    elif not has_nofollow:
        reason = "MISSING_REL_NOFOLLOW"
    else:
        reason = "OK"

    return {
        "valid": has_target_link and has_nofollow,
        "has_target_link": has_target_link,
        "has_nofollow": has_nofollow,
        "matching_links": matching_links,
        "reason": reason,
    }


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


def default_html_fetcher(url: str, timeout: float = 10.0, max_bytes: int = 262144) -> Tuple[int, str]:
    """Return (http_status, html_text) for url, bounded to max_bytes."""
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "pseofactory-parasite-ledger/1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(max_bytes)
            return int(resp.status), raw.decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        return int(exc.code), ""
    except Exception:
        return 0, ""


def classify_status(status: int) -> str:
    if 200 <= status < 300:
        return LIVE
    if status in (404, 410, 451) or status in (401, 403):
        return REMOVED
    return UNREACHABLE


class ParasiteLedger:
    def __init__(
        self,
        path: Optional[Union[str, Path]] = None,
        repo_root: Optional[Union[str, Path]] = None,
    ):
        if path is not None:
            self.path = Path(path)
        elif repo_root is not None:
            self.path = resolve_tenant_external_authority_ledger_path(repo_root)
        else:
            self.path = DEFAULT_PARASITE_LEDGER_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.path.with_suffix(".lock")

    @classmethod
    def for_tenant(cls, repo_root: Union[str, Path]) -> "ParasiteLedger":
        """Instantiate a per-tenant ledger backed by .agy/external_authority_ledger.json."""
        return cls(repo_root=repo_root)

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

    def record_authority_asset(
        self,
        url: str,
        surface_type: str,
        platform: str,
        tenant: str,
        target_domain: str = "",
        tool_slug: str = "",
        label: str = "",
    ) -> bool:
        """Register an external authority asset (embed, github_repo, or directory). Returns True if new."""
        norm_surface = str(surface_type or "").strip().lower()
        if norm_surface not in VALID_AUTHORITY_SURFACES:
            raise ValueError(
                f"Unsupported external authority surface '{surface_type}'. "
                f"Expected one of: {', '.join(VALID_AUTHORITY_SURFACES)}"
            )
        norm_platform = str(platform or "").strip().lower()
        if norm_surface == AUTHORITY_SURFACE_DIRECTORY and norm_platform not in ALLOWED_B2B_DIRECTORY_PLATFORMS:
            raise ValueError(
                f"Unsupported B2B directory platform '{platform}'. "
                f"Expected one of: {', '.join(ALLOWED_B2B_DIRECTORY_PLATFORMS)}"
            )

        def _do(records: Dict[str, Any]) -> bool:
            if url in records:
                return False
            records[url] = {
                "url": url,
                "surface_type": norm_surface,
                "platform": norm_platform,
                "tenant": str(tenant or "").strip().lower(),
                "target_domain": _normalize_domain(target_domain),
                "tool_slug": str(tool_slug or "").strip(),
                "label": str(label or "").strip(),
                "posted_at": _now(),
                "checks": [],
            }
            return True

        return bool(self._mutate(_do))

    def check_authority_liveness(
        self,
        fetcher: Optional[Callable[[str], Union[int, Tuple[int, str]]]] = None,
        target_domain: str = "",
        max_urls: int = 50,
    ) -> Dict[str, Any]:
        """Bounded liveness + rel='nofollow' embed attribution check across tracked authority URLs."""
        loaded = self._load()
        urls = list(loaded.keys())[: max(0, int(max_urls))]
        results: Dict[str, Any] = {}
        eff_fetcher = fetcher or default_html_fetcher

        for url in urls:
            rec = loaded.get(url) or {}
            surface_type = str(rec.get("surface_type") or "").strip().lower()
            raw_res = eff_fetcher(url)
            if isinstance(raw_res, tuple) and len(raw_res) == 2:
                status = int(raw_res[0])
                html_body = str(raw_res[1] or "")
            else:
                status = int(raw_res)
                html_body = ""
            state = classify_status(status)
            eff_domain = str(rec.get("target_domain") or target_domain or "").strip()
            row: Dict[str, Any] = {
                "checked_at": _now(),
                "http_status": status,
                "state": state,
                "surface_type": surface_type or "syndication",
            }
            if state == LIVE and surface_type == AUTHORITY_SURFACE_EMBED and eff_domain:
                attr_res = verify_embed_attribution_html(html_body, eff_domain)
                row["attribution_valid"] = bool(attr_res["valid"])
                row["has_nofollow"] = bool(attr_res["has_nofollow"])
                row["attribution_reason"] = attr_res["reason"]
            else:
                row["attribution_valid"] = None
                row["has_nofollow"] = None
                row["attribution_reason"] = None
            results[url] = row

        def _do(records: Dict[str, Any]) -> None:
            for url, row in results.items():
                if url in records:
                    records[url]["checks"].append(row)

        self._mutate(_do)
        return results

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
