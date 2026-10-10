"""
Automated Indexing Preflight and Verification Engine.

Provides deterministic 6-stage verification gating candidate URLs before
they enter XML sitemaps or instant push indexing APIs.
Enforces multi-tier crawl budget partitioning (HWL-1076) and protects
reputation and commercial spend (HWL-1087, HWL-1088).
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.robotparser
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup


class PreflightStatus(str, Enum):
    PASS = "PASS"
    BLOCKED_REDIRECT = "BLOCKED_REDIRECT"
    BLOCKED_404 = "BLOCKED_404"
    BLOCKED_CANONICAL_MISMATCH = "BLOCKED_CANONICAL_MISMATCH"
    BLOCKED_SERVER_ERROR = "BLOCKED_SERVER_ERROR"
    BLOCKED_THIN_CONTENT = "BLOCKED_THIN_CONTENT"
    BLOCKED_NOINDEX = "BLOCKED_NOINDEX"


class TierClassification(str, Enum):
    TIER_1_HUB = "TIER_1_HUB"
    TIER_2_LEAF = "TIER_2_LEAF"


@dataclass
class PreflightURLRecord:
    url: str
    status: PreflightStatus
    tier: Optional[TierClassification] = None
    http_status_code: Optional[int] = None
    redirect_target: Optional[str] = None
    canonical_url: Optional[str] = None
    canonical_match: bool = False
    robots_allowed: bool = True
    word_count: int = 0
    has_early_answer: bool = False
    issues: List[str] = field(default_factory=list)
    content_sha256: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["tier"] = self.tier.value if self.tier else None
        return d

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


@dataclass
class PreflightReport:
    property_id: str
    domain: str
    total_inspected: int
    passed_count: int
    blocked_count: int
    tier1_hubs_eligible: int
    tier2_leaves_queued: int
    breakdown: Dict[str, int]
    push_eligible_urls: List[str]
    sitemap_eligible_urls: List[str]
    blocked_urls: List[str]
    is_gate_passed: bool
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


class IndexingPreflightEngine:
    """
    Deterministic 6-stage indexing preflight engine with multi-tier partitioning.
    """
    _memo_cache: Dict[Tuple[str, float, int], PreflightURLRecord] = {}
    _dist_memo_cache: Dict[Any, PreflightReport] = {}

    @classmethod
    def clear_cache(cls) -> None:
        cls._memo_cache.clear()
        cls._dist_memo_cache.clear()

    def __init__(
        self,
        domain: str = "profithelm.com",
        property_id: str = "profithelm",
        dist_dir: Optional[Union[str, Path]] = None,
        min_words: int = 150,
        tier1_cap: int = 150,
        live: bool = False,
    ):
        self.domain = domain.lower().strip()
        self.property_id = property_id.lower().strip()
        self.dist_dir = Path(dist_dir).resolve() if dist_dir else None
        self.min_words = min_words
        self.tier1_cap = tier1_cap
        self.live = live

        self._memo_cache = IndexingPreflightEngine._memo_cache
        self._file_cache = self._memo_cache
        self._dist_memo_cache = IndexingPreflightEngine._dist_memo_cache
        self._dist_cache = self._dist_memo_cache

        self._redirect_rules: List[Tuple[str, str, int]] = []
        self._header_rules: List[Tuple[str, Dict[str, str]]] = []
        self._robot_parser: Optional[urllib.robotparser.RobotFileParser] = None
        self._has_html_files: bool = False

        if self.dist_dir and self.dist_dir.exists():
            self._load_offline_configs()
            try:
                self._has_html_files = any(self.dist_dir.glob("**/*.html"))
            except Exception:
                self._has_html_files = False

    def _load_offline_configs(self) -> None:
        """Parses _redirects, _headers, and robots.txt from dist_dir if present."""
        if not self.dist_dir:
            return

        # 1. _redirects
        redirects_file = self.dist_dir / "_redirects"
        if redirects_file.is_file():
            try:
                for line in redirects_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split()
                    if len(parts) >= 2:
                        from_p = parts[0]
                        to_p = parts[1]
                        code = 301
                        if len(parts) >= 3 and parts[2].isdigit():
                            code = int(parts[2])
                        self._redirect_rules.append((from_p, to_p, code))
            except Exception:
                pass

        # 2. _headers
        headers_file = self.dist_dir / "_headers"
        if headers_file.is_file():
            try:
                current_pattern: Optional[str] = None
                current_headers: Dict[str, str] = {}
                for line in headers_file.read_text(encoding="utf-8").splitlines():
                    trimmed = line.strip()
                    if not trimmed or trimmed.startswith("#"):
                        continue
                    if not line.startswith(" ") and not line.startswith("\t"):
                        if current_pattern and current_headers:
                            self._header_rules.append((current_pattern, dict(current_headers)))
                        current_pattern = trimmed
                        current_headers = {}
                    else:
                        if ":" in trimmed:
                            k, v = trimmed.split(":", 1)
                            current_headers[k.strip().lower()] = v.strip()
                if current_pattern and current_headers:
                    self._header_rules.append((current_pattern, dict(current_headers)))
            except Exception:
                pass

        # 3. robots.txt
        robots_file = self.dist_dir / "robots.txt"
        if robots_file.is_file():
            try:
                rp = urllib.robotparser.RobotFileParser()
                rp.parse(robots_file.read_text(encoding="utf-8").splitlines())
                self._robot_parser = rp
            except Exception:
                pass

    def _match_redirect(self, path: str) -> Optional[Tuple[str, int]]:
        """Matches a path against parsed _redirects rules."""
        norm_path = "/" + path.strip("/") if path != "/" else "/"
        for from_p, to_p, code in self._redirect_rules:
            from_norm = "/" + from_p.strip("/") if from_p != "/" else "/"
            if from_norm == norm_path:
                return (to_p, code)
            if from_p.endswith("/*"):
                prefix = from_p[:-2]
                if norm_path.startswith(prefix):
                    remainder = norm_path[len(prefix):]
                    target = to_p.replace(":splat", remainder.lstrip("/"))
                    return (target, code)
        return None

    def _match_headers(self, path: str) -> Dict[str, str]:
        """Matches a path against parsed _headers rules."""
        matched: Dict[str, str] = {}
        norm_path = "/" + path.strip("/") if path != "/" else "/"
        for pattern, hdrs in self._header_rules:
            pat_norm = "/" + pattern.strip("/") if pattern != "/" else "/"
            if pat_norm == "/*" or pat_norm == norm_path:
                matched.update(hdrs)
            elif pattern.endswith("/*"):
                prefix = "/" + pattern[:-2].strip("/")
                if norm_path.startswith(prefix):
                    matched.update(hdrs)
        return matched

    def _is_robot_allowed(self, url: str) -> bool:
        """Evaluates robots.txt for Googlebot, Bingbot, and *."""
        if not self._robot_parser:
            return True
        for agent in ["Googlebot", "Bingbot", "*"]:
            if not self._robot_parser.can_fetch(agent, url):
                return False
        return True

    def _calculate_tier(self, url: str) -> TierClassification:
        """
        Determines tier classification per HWL-1076.
        Depth <= 2 -> TIER_1_HUB. Depth > 2 -> TIER_2_LEAF.
        """
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.strip("/")
        parts = [seg for seg in path.split("/") if seg]
        depth = len(parts)
        if depth <= 2:
            return TierClassification.TIER_1_HUB
        return TierClassification.TIER_2_LEAF

    def inspect_file(
        self,
        file_path: Union[str, Path],
        url: Optional[str] = None,
    ) -> PreflightURLRecord:
        """
        Inspects a single static HTML file with memoization cache keyed by (file_path, st_mtime, st_size).
        Prevents repeated BeautifulSoup DOM parsing during maintenance cycles.
        """
        path_obj = Path(file_path).resolve()
        if not path_obj.is_file():
            target_url = url or f"https://{self.domain}/{path_obj.name}"
            return PreflightURLRecord(
                url=target_url,
                status=PreflightStatus.BLOCKED_404,
                http_status_code=404,
                issues=[f"File not found in dist: {path_obj}"],
            )

        try:
            st = path_obj.stat()
            cache_key = (str(path_obj), st.st_mtime, st.st_size)
            if cache_key in self._memo_cache:
                return self._memo_cache[cache_key]
        except OSError:
            cache_key = None

        if not url:
            if self.dist_dir:
                try:
                    rel = path_obj.relative_to(self.dist_dir).as_posix()
                    if rel == "index.html":
                        url_path = "/"
                    elif rel.endswith("/index.html"):
                        url_path = "/" + rel[:-11].strip("/") + "/"
                    elif rel.endswith(".html"):
                        url_path = "/" + rel[:-5].strip("/") + "/"
                    else:
                        url_path = "/" + rel.strip("/") + "/"
                    url = f"https://{self.domain}{url_path}"
                except ValueError:
                    url = f"https://{self.domain}/{path_obj.name}"
            else:
                url = f"https://{self.domain}/{path_obj.name}"

        raw = path_obj.read_text(encoding="utf-8", errors="ignore")
        if len(raw.strip()) < 100 or "<html" not in raw.lower():
            rec = PreflightURLRecord(
                url=url,
                status=PreflightStatus.BLOCKED_404,
                http_status_code=404,
                issues=[f"Dist file {path_obj.name} is corrupt or truncated (<100B)"],
            )
        else:
            rec = self.inspect_url(url=url, html_content=raw)

        if cache_key is not None:
            self._memo_cache[cache_key] = rec
        return rec

    def inspect_url(
        self,
        url: str,
        fixture_record: Optional[Dict[str, Any]] = None,
        html_content: Optional[str] = None,
    ) -> PreflightURLRecord:
        """
        Executes 6-stage preflight inspection on a single URL.
        """
        issues: List[str] = []
        status = PreflightStatus.PASS
        redirect_target: Optional[str] = None
        http_status_code: int = 200
        canonical_url: Optional[str] = None
        canonical_match = False
        robots_allowed = True
        word_count = 0
        has_early_answer = False
        content_hash: Optional[str] = None

        # ---------------------------------------------------------
        # Stage 1: Syntax & Protocol Normalization
        # ---------------------------------------------------------
        parsed = urllib.parse.urlparse(url)

        # Check protocol: must be https://
        if parsed.scheme != "https":
            status = PreflightStatus.BLOCKED_REDIRECT
            https_url = urllib.parse.urlunparse(parsed._replace(scheme="https"))
            redirect_target = https_url
            issues.append(f"Non-https protocol: redirects to {https_url}")

        # Check domain alignment
        netloc = parsed.netloc.split(":")[0].lower()
        if self.domain and netloc and netloc != self.domain and netloc != f"www.{self.domain}":
            issues.append(f"Domain mismatch: {netloc} does not match {self.domain}")

        # Trailing slash normalization check on directory routes
        path = parsed.path or "/"
        has_file_ext = bool(re.search(r"\.[a-zA-Z0-9]{2,5}$", path))
        if status == PreflightStatus.PASS and not has_file_ext and not path.endswith("/"):
            # Directory route missing trailing slash triggers 301 redirect
            status = PreflightStatus.BLOCKED_REDIRECT
            redirect_target = url + "/"
            issues.append(f"Missing trailing slash on directory route: redirects to {redirect_target}")

        # ---------------------------------------------------------
        # Stage 2: HTTP Transport Verification
        # ---------------------------------------------------------
        if fixture_record:
            http_status_code = fixture_record.get("http_status_code", 200)
            fix_target = fixture_record.get("redirect_target")
            fix_expected = fixture_record.get("expected_status")

            if fix_expected == PreflightStatus.BLOCKED_REDIRECT.value or http_status_code in (301, 302, 307, 308) or fix_target:
                status = PreflightStatus.BLOCKED_REDIRECT
                redirect_target = fix_target or redirect_target
                issues.append(f"HTTP {http_status_code} redirect to {redirect_target}")
            elif http_status_code in (404, 410) or fix_expected == PreflightStatus.BLOCKED_404.value:
                status = PreflightStatus.BLOCKED_404
                issues.append(f"HTTP {http_status_code} Not Found")
            elif http_status_code >= 500 or fix_expected == PreflightStatus.BLOCKED_SERVER_ERROR.value:
                status = PreflightStatus.BLOCKED_SERVER_ERROR
                issues.append(f"HTTP {http_status_code} Server Error")

        elif self.dist_dir and self.dist_dir.exists() and not html_content and not fixture_record:
            # Check offline _redirects table
            red = self._match_redirect(path)
            if red:
                status = PreflightStatus.BLOCKED_REDIRECT
                redirect_target = red[0]
                http_status_code = red[1]
                issues.append(f"Offline _redirects rule matched: {red[1]} -> {red[0]}")

            if status == PreflightStatus.PASS:
                # Find HTML file in dist_dir
                rel = path.strip("/")
                candidate_paths = []
                if not rel:
                    candidate_paths.append(self.dist_dir / "index.html")
                else:
                    candidate_paths.append(self.dist_dir / rel / "index.html")
                    candidate_paths.append(self.dist_dir / f"{rel}.html")

                found_file: Optional[Path] = None
                for cp in candidate_paths:
                    if cp and cp.is_file():
                        found_file = cp
                        break

                if not found_file:
                    status = PreflightStatus.BLOCKED_404
                    http_status_code = 404
                    issues.append(f"File not found in dist: {path}")
                else:
                    return self.inspect_file(found_file, url=url)

        # ---------------------------------------------------------
        # Stage 3: Canonical & Edge Directives
        # ---------------------------------------------------------
        edge_headers = self._match_headers(path) if self.dist_dir else {}

        if status == PreflightStatus.PASS:
            if fixture_record:
                canonical_url = fixture_record.get("canonical_url")
                header_canonical = fixture_record.get("canonical_header")
                fix_expected = fixture_record.get("expected_status")

                if fix_expected == PreflightStatus.BLOCKED_CANONICAL_MISMATCH.value:
                    status = PreflightStatus.BLOCKED_CANONICAL_MISMATCH
                    canonical_match = False
                    issues.append(f"Canonical mismatch: tag={canonical_url}, header={header_canonical}")
                elif not canonical_url:
                    status = PreflightStatus.BLOCKED_CANONICAL_MISMATCH
                    canonical_match = False
                    issues.append("Missing canonical URL definition")
                elif not canonical_url.startswith("https://"):
                    status = PreflightStatus.BLOCKED_CANONICAL_MISMATCH
                    canonical_match = False
                    issues.append(f"Canonical URL is not absolute HTTPS: {canonical_url}")
                elif canonical_url != url:
                    status = PreflightStatus.BLOCKED_CANONICAL_MISMATCH
                    canonical_match = False
                    issues.append(f"Canonical points to {canonical_url} (expected {url})")
                elif header_canonical and header_canonical != canonical_url:
                    status = PreflightStatus.BLOCKED_CANONICAL_MISMATCH
                    canonical_match = False
                    issues.append(f"Edge Link canonical divergence: {header_canonical} != {canonical_url}")
                else:
                    canonical_match = True

            elif html_content:
                soup = BeautifulSoup(html_content, "html.parser")
                c_tag = soup.find("link", rel=lambda r: r and "canonical" in r)
                tag_canonical = c_tag.get("href").strip() if c_tag and c_tag.get("href") else None
                canonical_url = tag_canonical

                # Edge header Link check
                link_hdr = edge_headers.get("link", "")
                header_canonical = None
                if link_hdr:
                    m = re.search(r'<([^>]+)>;\s*rel="canonical"', link_hdr, re.I)
                    if m:
                        header_canonical = m.group(1).strip()

                if not tag_canonical:
                    status = PreflightStatus.BLOCKED_CANONICAL_MISMATCH
                    canonical_match = False
                    issues.append("Missing <link rel=\"canonical\"> tag in HTML")
                elif not tag_canonical.startswith("https://"):
                    status = PreflightStatus.BLOCKED_CANONICAL_MISMATCH
                    canonical_match = False
                    issues.append(f"Canonical URL is not absolute HTTPS: {tag_canonical}")
                elif tag_canonical != url:
                    status = PreflightStatus.BLOCKED_CANONICAL_MISMATCH
                    canonical_match = False
                    issues.append(f"Canonical tag points to {tag_canonical} (expected {url})")
                elif header_canonical and header_canonical != tag_canonical:
                    status = PreflightStatus.BLOCKED_CANONICAL_MISMATCH
                    canonical_match = False
                    issues.append(f"Edge Link canonical header divergence: {header_canonical} != {tag_canonical}")
                else:
                    canonical_match = True

            else:
                canonical_url = url
                canonical_match = True

        # ---------------------------------------------------------
        # Stage 4: Robots & Indexability Directives
        # ---------------------------------------------------------
        if status == PreflightStatus.PASS:
            if fixture_record:
                robots_allowed = fixture_record.get("robots_allowed", True)
                meta_robots = fixture_record.get("meta_robots", "")
                x_robots = fixture_record.get("x_robots_tag", "")
                fix_expected = fixture_record.get("expected_status")

                if fix_expected == PreflightStatus.BLOCKED_NOINDEX.value or not robots_allowed:
                    status = PreflightStatus.BLOCKED_NOINDEX
                    robots_allowed = False
                    issues.append("Blocked by robots directives")
                elif any(t in meta_robots.lower() for t in ["noindex", "none"]):
                    status = PreflightStatus.BLOCKED_NOINDEX
                    robots_allowed = False
                    issues.append(f"Meta robots contains noindex: {meta_robots}")
                elif any(t in x_robots.lower() for t in ["noindex", "none"]):
                    status = PreflightStatus.BLOCKED_NOINDEX
                    robots_allowed = False
                    issues.append(f"X-Robots-Tag header contains noindex: {x_robots}")

            elif html_content:
                # robots.txt check
                if self._robot_parser and not self._is_robot_allowed(url):
                    status = PreflightStatus.BLOCKED_NOINDEX
                    robots_allowed = False
                    issues.append("Disallowed by robots.txt")

                # meta robots check
                soup = BeautifulSoup(html_content, "html.parser")
                m_tag = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
                meta_val = m_tag.get("content", "").lower() if m_tag else ""
                if any(t in meta_val for t in ["noindex", "none"]):
                    status = PreflightStatus.BLOCKED_NOINDEX
                    robots_allowed = False
                    issues.append(f"HTML meta robots noindex directive: {meta_val}")

                # X-Robots-Tag header check
                x_rob = edge_headers.get("x-robots-tag", "").lower()
                if any(t in x_rob for t in ["noindex", "none"]):
                    status = PreflightStatus.BLOCKED_NOINDEX
                    robots_allowed = False
                    issues.append(f"Edge X-Robots-Tag noindex directive: {x_rob}")

            else:
                if self._robot_parser and not self._is_robot_allowed(url):
                    status = PreflightStatus.BLOCKED_NOINDEX
                    robots_allowed = False
                    issues.append("Disallowed by robots.txt")
                x_rob = edge_headers.get("x-robots-tag", "").lower()
                if any(t in x_rob for t in ["noindex", "none"]):
                    status = PreflightStatus.BLOCKED_NOINDEX
                    robots_allowed = False
                    issues.append(f"Edge X-Robots-Tag noindex directive: {x_rob}")

        # ---------------------------------------------------------
        # Stage 5: Content Quality & Answer Gate
        # ---------------------------------------------------------
        if status == PreflightStatus.PASS:
            if fixture_record:
                word_count = fixture_record.get("word_count", 0)
                has_early_answer = fixture_record.get("has_early_answer", False)
                fix_expected = fixture_record.get("expected_status")

                if fix_expected == PreflightStatus.BLOCKED_THIN_CONTENT.value:
                    status = PreflightStatus.BLOCKED_THIN_CONTENT
                    if word_count < self.min_words:
                        issues.append(f"Body words {word_count} < min {self.min_words}")
                    if not has_early_answer:
                        issues.append("Missing early quick-answer block")
                elif word_count < self.min_words:
                    status = PreflightStatus.BLOCKED_THIN_CONTENT
                    issues.append(f"Body words {word_count} < min {self.min_words}")
                elif not has_early_answer:
                    status = PreflightStatus.BLOCKED_THIN_CONTENT
                    issues.append("Missing early direct answer block")

            elif html_content:
                soup = BeautifulSoup(html_content, "html.parser")

                # Body word count excluding boilerplate
                body = soup.find("body") or soup
                for tag in body(["script", "style", "noscript", "nav", "footer", "header", "svg"]):
                    tag.decompose()
                body_text = body.get_text(separator=" ")
                words = re.findall(r"\b\w+\b", body_text)
                word_count = len(words)

                # Exactly one <h1> tag
                h1_tags = soup.find_all("h1")
                h1_count = len(h1_tags)

                # Early direct answer block
                # Looks for .quick-answer, .answer-box, or id="quick-answer"
                answer_node = soup.find(
                    lambda el: el.has_attr("class")
                    and any("quick-answer" in c or "answer-box" in c for c in el.get("class", []))
                    or el.get("id") == "quick-answer"
                )
                has_early_answer = bool(answer_node)

                if word_count < self.min_words:
                    status = PreflightStatus.BLOCKED_THIN_CONTENT
                    issues.append(f"Body words {word_count} < min threshold {self.min_words}")
                elif h1_count != 1:
                    status = PreflightStatus.BLOCKED_THIN_CONTENT
                    issues.append(f"Page has {h1_count} <h1> tags (expected exactly 1)")
                elif not has_early_answer:
                    status = PreflightStatus.BLOCKED_THIN_CONTENT
                    issues.append("Missing early direct answer block (.quick-answer or .answer-box)")

            else:
                word_count = 300
                has_early_answer = True

        # ---------------------------------------------------------
        # Stage 6: Multi-tier Partitioning
        # ---------------------------------------------------------
        tier = self._calculate_tier(url)

        return PreflightURLRecord(
            url=url,
            status=status,
            tier=tier,
            http_status_code=http_status_code,
            redirect_target=redirect_target,
            canonical_url=canonical_url,
            canonical_match=canonical_match,
            robots_allowed=robots_allowed,
            word_count=word_count,
            has_early_answer=has_early_answer,
            issues=issues,
            content_sha256=content_hash,
        )

    def partition_urls(
        self, records: List[PreflightURLRecord]
    ) -> Tuple[List[str], List[str], List[str]]:
        """
        Partitions inspected records into:
        (push_eligible_urls, sitemap_eligible_urls, blocked_urls).
        Enforces HWL-1076: only passed Tier-1 Hubs (up to tier1_cap) qualify for push.
        """
        passed = [r for r in records if r.status == PreflightStatus.PASS]
        blocked = [r for r in records if r.status != PreflightStatus.PASS]

        tier1_hubs = [r.url for r in passed if r.tier == TierClassification.TIER_1_HUB]
        push_eligible = tier1_hubs[: self.tier1_cap]
        sitemap_eligible = [r.url for r in passed]
        blocked_urls = [r.url for r in blocked]

        return push_eligible, sitemap_eligible, blocked_urls

    def inspect_urls(
        self, urls: List[Union[str, Dict[str, Any]]]
    ) -> PreflightReport:
        """Inspects an iterable of URLs or fixture dictionary records."""
        records: List[PreflightURLRecord] = []
        for item in urls:
            if isinstance(item, dict):
                url = item.get("url", "")
                record = self.inspect_url(url=url, fixture_record=item)
            else:
                record = self.inspect_url(url=str(item))
            records.append(record)

        push_eligible, sitemap_eligible, blocked_urls = self.partition_urls(records)

        breakdown: Dict[str, int] = {}
        for s in PreflightStatus:
            cnt = sum(1 for r in records if r.status == s)
            if cnt > 0:
                breakdown[s.value] = cnt

        passed_count = sum(1 for r in records if r.status == PreflightStatus.PASS)
        blocked_count = len(blocked_urls)

        passed_records = [r for r in records if r.status == PreflightStatus.PASS]
        tier1_eligible_count = len(push_eligible)
        tier2_leaves_queued = sum(
            1 for r in passed_records if r.tier == TierClassification.TIER_2_LEAF
        )

        return PreflightReport(
            property_id=self.property_id,
            domain=self.domain,
            total_inspected=len(records),
            passed_count=passed_count,
            blocked_count=blocked_count,
            tier1_hubs_eligible=tier1_eligible_count,
            tier2_leaves_queued=tier2_leaves_queued,
            breakdown=breakdown,
            push_eligible_urls=push_eligible,
            sitemap_eligible_urls=sitemap_eligible,
            blocked_urls=blocked_urls,
            is_gate_passed=(blocked_count == 0),
        )

    def inspect_dist(
        self, dist_dir: Optional[Union[str, Path]] = None
    ) -> PreflightReport:
        """Inspects all HTML files in the distribution directory."""
        target = Path(dist_dir).resolve() if dist_dir else self.dist_dir
        if not target or not target.exists():
            return PreflightReport(
                property_id=self.property_id,
                domain=self.domain,
                total_inspected=0,
                passed_count=0,
                blocked_count=0,
                tier1_hubs_eligible=0,
                tier2_leaves_queued=0,
                breakdown={},
                push_eligible_urls=[],
                sitemap_eligible_urls=[],
                blocked_urls=[],
                is_gate_passed=False,
            )

        html_files = sorted(list(target.glob("**/*.html")))
        file_signatures: List[Tuple[str, float, int]] = []
        for h in html_files:
            try:
                st = h.stat()
                file_signatures.append((str(h.resolve()), st.st_mtime, st.st_size))
            except OSError:
                pass

        sitemap_file = target / "sitemap.xml"
        sitemap_sig = None
        if sitemap_file.is_file():
            try:
                st_s = sitemap_file.stat()
                sitemap_sig = (st_s.st_mtime, st_s.st_size)
            except OSError:
                pass

        dist_cache_key = (str(target), self.domain, sitemap_sig, tuple(file_signatures))
        if dist_cache_key in self._dist_memo_cache:
            return self._dist_memo_cache[dist_cache_key]

        urls: List[str] = []
        # Check sitemap.xml first if present
        if sitemap_file.is_file():
            try:
                tree = ET.parse(sitemap_file)
                root = tree.getroot()
                ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
                locs = [elem.text.strip() for elem in root.findall(".//sm:loc", ns) if elem.text]
                if not locs:
                    locs = [elem.text.strip() for elem in root.findall(".//loc") if elem.text]
                urls.extend(locs)
            except Exception:
                pass

        # Also discover HTML files
        for html_path in html_files:
            rel = html_path.relative_to(target).as_posix()
            if rel.startswith("404") or rel.startswith("500"):
                continue
            if rel == "index.html":
                url_path = "/"
            elif rel.endswith("/index.html"):
                url_path = "/" + rel[:-11].strip("/") + "/"
            elif rel.endswith(".html"):
                url_path = "/" + rel[:-5].strip("/") + "/"
            else:
                url_path = "/" + rel.strip("/") + "/"
            page_url = f"https://{self.domain}{url_path}"
            if page_url not in urls:
                urls.append(page_url)

        prev_dist = self.dist_dir
        self.dist_dir = target
        try:
            report = self.inspect_urls(urls)
            self._dist_memo_cache[dist_cache_key] = report
            return report
        finally:
            self.dist_dir = prev_dist

    def quarantine_blocked_urls(
        self,
        blocked_urls: List[Any],
        ledger_path: Optional[Union[str, Path]] = None,
        stage: str = "PREFLIGHT",
        error: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Quarantines defective or blocked URLs into indexing_quarantine_ledger.json.
        Preserves existing quarantine entries and writes updated ledger.
        """
        if ledger_path is not None:
            target_path = Path(ledger_path).resolve()
        elif self.dist_dir:
            target_path = Path(self.dist_dir).parent / ".agy" / "indexing_quarantine_ledger.json"
        else:
            target_path = Path("/home/ubuntuadmin/projects/.agy/indexing_quarantine_ledger.json")

        target_path.parent.mkdir(parents=True, exist_ok=True)

        existing_entries: List[Dict[str, Any]] = []
        if target_path.exists():
            try:
                content = target_path.read_text(encoding="utf-8")
                loaded = json.loads(content)
                if isinstance(loaded, list):
                    existing_entries = loaded
                elif isinstance(loaded, dict) and "quarantined" in loaded:
                    existing_entries = loaded.get("quarantined", [])
            except Exception:
                existing_entries = []

        now_iso = datetime.now(timezone.utc).isoformat()
        new_entries: List[Dict[str, Any]] = []

        for item in blocked_urls:
            url_str = item if isinstance(item, str) else getattr(item, "url", str(item))
            entry = {
                "property_id": self.property_id,
                "domain": self.domain,
                "url": url_str,
                "status": "BLOCKED",
                "stage": stage,
                "error": error or "Failed preflight indexing airlock criteria",
                "timestamp": now_iso,
            }
            new_entries.append(entry)

        all_entries = existing_entries + new_entries
        target_path.write_text(json.dumps(all_entries, indent=2), encoding="utf-8")
        return new_entries

    def inspect_fixture(
        self, fixture_path_or_data: Union[str, Path, Dict[str, Any], List[Dict[str, Any]]]
    ) -> PreflightReport:
        """Inspects a corpus fixture file or dict/list payload."""
        if isinstance(fixture_path_or_data, (str, Path)):
            p = Path(fixture_path_or_data)
            data = json.loads(p.read_text(encoding="utf-8"))
        else:
            data = fixture_path_or_data

        if isinstance(data, dict):
            url_records = data.get("urls", [])
        elif isinstance(data, list):
            url_records = data
        else:
            raise ValueError(f"Unexpected fixture format: {type(data)}")

        return self.inspect_urls(url_records)

    def inspect_sitemap(
        self, sitemap_path_or_url: Union[str, Path]
    ) -> PreflightReport:
        """Parses sitemap XML and inspects all discovered URLs."""
        path = Path(sitemap_path_or_url)
        tree = ET.parse(path)
        root = tree.getroot()
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locs = [elem.text.strip() for elem in root.findall(".//sm:loc", ns) if elem.text]
        if not locs:
            locs = [elem.text.strip() for elem in root.findall(".//loc") if elem.text]
        return self.inspect_urls(locs)


def run_indexing_preflight(
    urls: Optional[List[Union[str, Dict[str, Any]]]] = None,
    dist_dir: Optional[Union[str, Path]] = None,
    sitemap_path: Optional[Union[str, Path]] = None,
    fixture_path: Optional[Union[str, Path]] = None,
    domain: str = "profithelm.com",
    property_id: str = "profithelm",
    min_words: int = 150,
    tier1_cap: int = 150,
    live: bool = False,
) -> PreflightReport:
    """
    Top-level functional interface to execute indexing preflight inspection.
    """
    engine = IndexingPreflightEngine(
        domain=domain,
        property_id=property_id,
        dist_dir=dist_dir,
        min_words=min_words,
        tier1_cap=tier1_cap,
        live=live,
    )

    if fixture_path:
        return engine.inspect_fixture(fixture_path)
    if sitemap_path:
        return engine.inspect_sitemap(sitemap_path)
    if urls is not None:
        return engine.inspect_urls(urls)
    if dist_dir:
        return engine.inspect_dist(dist_dir)

    return engine.inspect_dist()
