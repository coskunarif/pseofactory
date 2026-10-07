"""
pseofactory Master SEO & GEO Audit Checklist Verification Engine
Enforces mechanical verification gates across all static assets.
All 18 Opus 5.5 SEO Rules + Auxiliary Architectural Quality Gates.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

import re
import sys
import os
import json
import html
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set, Callable

from pseofactory.contracts import (
    FORBIDDEN_JARGON,
    assert_no_forbidden_dashes,
    assert_ai_mode_calculation_manifest,
)


class SEOVerificationError(Exception):
    """Raised when one or more mechanical SEO checklist gates fail."""

    def __init__(
        self,
        message: str,
        issues: Optional[List[str]] = None,
        gates: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.issues = issues or []
        self.violations = self.issues
        self.gates = gates or {}


# =============================================================================
# Zyppy 2026 Content Relevance Single-Pass HTML Parser
# =============================================================================

class SinglePassSEODocumentParser(HTMLParser):
    """
    Streaming single-pass HTML parser extracting structural SEO entities with zero external dependencies.
    """

    def __init__(self, brand_domain: str = ""):
        super().__init__(convert_charrefs=True)
        self.brand_domain = brand_domain
        self.root_lang = ""
        self.title_parts: List[str] = []
        self.meta_description = ""
        self.canonical_url = ""
        self.og_url = ""
        self.meta_content_language = ""
        self.hreflangs: List[str] = []
        self.geo_region = ""
        self.h1_list: List[str] = []
        self.h2_list: List[str] = []
        self.h3_list: List[str] = []
        self.json_ld_blocks: List[str] = []
        self.quick_answer_text_parts: List[str] = []
        self.in_quick_answer = False
        self.quick_answer_depth = 0
        self.table_count = 0
        self.ol_count = 0
        self.has_calculator = False
        self.internal_links: List[str] = []
        self.current_tag: Optional[str] = None
        self.current_data: List[str] = []
        self.tag_stack: List[Tuple[str, Dict[str, str]]] = []
        # Snippet and crawl verification state
        self.has_nosnippet: bool = False
        self.max_snippet: Optional[int] = None
        self.has_noindex: bool = False
        self.max_image_preview: Optional[str] = None
        self.max_video_preview: Optional[int] = None
        self.data_nosnippet_tags: List[str] = []
        self.quick_answer_has_data_nosnippet: bool = False

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        attrs_dict = {k.lower(): (v or "") for k, v in attrs}
        self.tag_stack.append((tag, attrs_dict))

        if "data-nosnippet" in attrs_dict:
            self.data_nosnippet_tags.append(tag)
            if self.in_quick_answer:
                self.quick_answer_has_data_nosnippet = True

        if tag == "html":
            if "lang" in attrs_dict:
                self.root_lang = attrs_dict["lang"]

        elif tag == "title":
            self.current_tag = "title"
            self.current_data = []

        elif tag == "meta":
            name = attrs_dict.get("name", "").lower()
            prop = attrs_dict.get("property", "").lower()
            http_equiv = attrs_dict.get("http-equiv", "").lower()
            content = attrs_dict.get("content", "")
            if name == "description":
                self.meta_description = content
            elif http_equiv == "content-language":
                self.meta_content_language = content
            elif name == "geo.region":
                self.geo_region = content
            elif prop == "og:url":
                self.og_url = content

            if name in ("robots", "googlebot", "google-extended", "bingbot"):
                c_lower = content.lower()
                if "nosnippet" in c_lower:
                    self.has_nosnippet = True
                if "noindex" in c_lower:
                    self.has_noindex = True
                if "max-snippet" in c_lower:
                    m_ms = re.search(r'max-snippet\s*:\s*(-?\d+)', content, re.IGNORECASE)
                    if m_ms:
                        self.max_snippet = int(m_ms.group(1))
                if "max-image-preview" in c_lower:
                    m_mip = re.search(r'max-image-preview\s*:\s*([a-zA-Z0-9_-]+)', content, re.IGNORECASE)
                    if m_mip:
                        self.max_image_preview = m_mip.group(1).lower()
                if "max-video-preview" in c_lower:
                    m_mvp = re.search(r'max-video-preview\s*:\s*(-?\d+)', content, re.IGNORECASE)
                    if m_mvp:
                        self.max_video_preview = int(m_mvp.group(1))

        elif tag == "link":
            rel = attrs_dict.get("rel", "").lower()
            if rel == "canonical":
                self.canonical_url = attrs_dict.get("href", "")
            elif rel == "alternate" and "hreflang" in attrs_dict:
                self.hreflangs.append(attrs_dict["hreflang"].lower())

        elif tag in ("h1", "h2", "h3"):
            self.current_tag = tag
            self.current_data = []

        elif tag == "script":
            if attrs_dict.get("type", "").lower() == "application/ld+json":
                self.current_tag = "script_json_ld"
                self.current_data = []

        elif tag in ("form", "input", "select", "button"):
            self.has_calculator = True

        tag_id = attrs_dict.get("id", "").lower()
        tag_cls = attrs_dict.get("class", "").lower()
        if "calc" in tag_id or "calc" in tag_cls:
            self.has_calculator = True

        if "quick-answer" in tag_cls or "quick-answer" in tag_id:
            self.in_quick_answer = True
            self.quick_answer_depth = len(self.tag_stack)
            if "data-nosnippet" in attrs_dict:
                self.quick_answer_has_data_nosnippet = True
            for anc_tag, anc_attrs in self.tag_stack:
                if "data-nosnippet" in anc_attrs:
                    self.quick_answer_has_data_nosnippet = True
                    break

        if tag == "table":
            self.table_count += 1
        elif tag == "ol":
            self.ol_count += 1

        elif tag == "a":
            href = attrs_dict.get("href", "")
            if href.startswith("/") or (self.brand_domain and self.brand_domain in href):
                self.internal_links.append(href)

    def handle_endtag(self, tag: str):
        if self.current_tag == "title":
            self.title_parts.append("".join(self.current_data))
            self.current_tag = None
        elif self.current_tag == "h1":
            self.h1_list.append("".join(self.current_data).strip())
            self.current_tag = None
        elif self.current_tag == "h2":
            self.h2_list.append("".join(self.current_data).strip())
            self.current_tag = None
        elif self.current_tag == "h3":
            self.h3_list.append("".join(self.current_data).strip())
            self.current_tag = None
        elif self.current_tag == "script_json_ld":
            self.json_ld_blocks.append("".join(self.current_data))
            self.current_tag = None

        if self.in_quick_answer and len(self.tag_stack) <= self.quick_answer_depth:
            self.in_quick_answer = False

        if self.tag_stack and self.tag_stack[-1][0] == tag:
            self.tag_stack.pop()

    def handle_data(self, data: str):
        if self.current_tag in ("title", "h1", "h2", "h3", "script_json_ld"):
            self.current_data.append(data)
        if self.in_quick_answer:
            self.quick_answer_text_parts.append(data)

    @property
    def title(self) -> str:
        return "".join(self.title_parts).strip()

    @property
    def quick_answer_text(self) -> str:
        return "".join(self.quick_answer_text_parts).strip()


# Backward-compatible alias
ZyppyHTMLParser = SinglePassSEODocumentParser

ZYPPY_2026_FACTORS_SPEC = [
    {"factor": "Search Intent Match", "weight": 2.60, "code": "search_intent_match"},
    {"factor": "Page Semantic Relevance", "weight": 2.34, "code": "page_semantic_relevance"},
    {"factor": "Site Topical Authority", "weight": 2.29, "code": "site_topical_authority"},
    {"factor": "Title Relevance", "weight": 2.26, "code": "title_relevance"},
    {"factor": "Passage-level Relevance", "weight": 1.99, "code": "passage_level_relevance"},
    {"factor": "Language Match", "weight": 1.95, "code": "language_match"},
    {"factor": "Geographic Relevance", "weight": 1.89, "code": "geographic_relevance"},
    {"factor": "Keywords in H1", "weight": 1.67, "code": "keywords_in_h1"},
    {"factor": "Keywords in Subheadings", "weight": 1.27, "code": "keywords_in_subheadings"},
    {"factor": "Keywords in URL", "weight": 1.07, "code": "keywords_in_url"},
    {"factor": "Exact-Match Domain", "weight": 0.94, "code": "exact_match_domain"},
    {"factor": "Meta Description", "weight": 0.22, "code": "meta_description"},
]

# Canonical 3-Tier AI Crawler Taxonomy
AI_SEARCH_BOTS = ["googlebot", "bingbot", "perplexitybot", "oai-searchbot"]
AI_USER_TRIGGERED_BOTS = ["chatgpt-user", "claude-web"]
AI_TRAINING_BOTS = [
    "gptbot",
    "google-extended",
    "applebot",
    "applebot-extended",
    "meta-externalagent",
    "ccbot",
    "anthropic-ai",
    "cohere-ai",
    "bytespider",
]



# =============================================================================
# Master SEO Verifier Class
# =============================================================================

class MasterSEOVerifier:
    """
    Parametric Master SEO & GEO Audit Checklist Verification Engine.
    Configurable brand name, canonical base, domain, required endpoints, and leaf checks.
    """

    def __init__(
        self,
        dist_dir: Optional[Path] = None,
        canonical_base: Optional[str] = None,
        domain: Optional[str] = None,
        brand_name: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        required_endpoints: Optional[List[str]] = None,
        leaf_route_checker: Optional[Callable[[Path, List[Tuple[str, str]]], List[str]]] = None,
        is_geo_leaf: Optional[Callable[[str, Path], bool]] = None,
        is_calculation_leaf: Optional[Callable[[str, Path, Any], Optional[str]]] = None,
        code_dirs: Optional[List[Path]] = None,
        min_manifests: int = 8,
        strict_robots: bool = False,
    ):
        self.canonical_base = (
            canonical_base
            if canonical_base is not None
            else os.environ.get("FACTORY_CANONICAL_BASE", "https://profithelm.com")
        ).rstrip("/")
        self.domain = (
            domain
            if domain is not None
            else os.environ.get("FACTORY_DOMAIN", "profithelm.com")
        )
        self.brand_domain = self.domain
        self.brand_name = (
            brand_name
            if brand_name is not None
            else os.environ.get("FACTORY_BRAND_NAME", "ProfitHelm")
        )
        self.dist_dir = (
            Path(dist_dir)
            if dist_dir is not None
            else Path(os.environ.get("FACTORY_DIST_DIR", "/home/ubuntuadmin/projects/profithelm-platform/dist"))
        )
        self.tools = list(tools) if tools else []
        self.min_manifests = min_manifests
        self.strict_robots = strict_robots
        self.leaf_route_checker = leaf_route_checker
        self.is_geo_leaf = is_geo_leaf
        self.is_calculation_leaf = is_calculation_leaf
        self.code_dirs = list(code_dirs) if code_dirs else []

        if required_endpoints is not None:
            self.required_endpoints = list(required_endpoints)
        else:
            self.required_endpoints = [
                "/feed.xml",
                "/llms.txt",
                "/llms-full.txt",
                "/sitemap.xml",
                "/sitemap-hubs.xml",
                "/sitemap-leaves.xml",
                "/",
                "/about/",
                "/privacy/",
                "/tools/",
            ]

    # 1. Alt Text Gate
    def check_alt_text_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        images_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                for m in re.finditer(r'<img\b([^>]*)>', content, re.IGNORECASE):
                    images_checked += 1
                    attrs = m.group(1)
                    alt_m = re.search(r'\balt=["\']([^"\']*)["\']', attrs, re.IGNORECASE)
                    if not alt_m or not alt_m.group(1).strip():
                        issues.append(f"Missing or empty alt attribute on <img> tag in {rel}")
                    elif alt_m.group(1).strip().lower() in ["image", "placeholder"]:
                        issues.append(f"Generic placeholder alt attribute '{alt_m.group(1)}' in {rel}")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_alt_text_gate",
            "images_checked": images_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 2. Sitemap Gate
    def check_sitemap_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        sitemap = target / "sitemap.xml"
        urls_checked = 0

        if not sitemap.is_file():
            issues.append(f"Missing sitemap.xml at {sitemap}")
        else:
            try:
                tree = ET.parse(sitemap)
                root = tree.getroot()
                ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
                locs = [elem.text.strip() for elem in root.findall(".//sm:loc", ns) if elem.text]
                if not locs:
                    locs = [elem.text.strip() for elem in root.findall(".//loc") if elem.text]

                urls_checked = len(locs)
                if urls_checked < 3:
                    issues.append(f"sitemap.xml contains only {urls_checked} URLs (expected >= 3)")

                domain_prefix = f"https://{self.domain}"
                for loc in locs:
                    if not loc.startswith(domain_prefix) and not loc.startswith(self.canonical_base):
                        issues.append(f"Sitemap URL '{loc}' does not match canonical base {domain_prefix}")
            except Exception as ex:
                issues.append(f"Malformed XML in sitemap.xml: {ex}")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_sitemap_gate",
            "urls_checked": urls_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 3. Page Titles Gate
    def check_page_titles_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        pages_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                if p.name == "404.html" or "signal" in p.parts:
                    continue
                pages_checked += 1
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r'<title\b[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
                if not m:
                    issues.append(f"Missing <title> tag in {rel}")
                else:
                    raw_title = m.group(1).strip()
                    if "| |" in raw_title:
                        issues.append(f"Double pipe ('| |') formatting corruption in {rel}: '{raw_title}'")
                    title = html.unescape(raw_title)
                    t_len = len(title)
                    if not (50 <= t_len <= 60):
                        issues.append(f"Title length ({t_len} chars) outside 50-60 range in {rel}: '{title}'")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_page_titles_gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 4. Single H1 Gate
    def check_single_h1_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        pages_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                if p.name == "404.html":
                    continue
                pages_checked += 1
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                h1s = re.findall(r'<h1\b[^>]*>(.*?)</h1>', content, re.IGNORECASE | re.DOTALL)
                if len(h1s) == 0:
                    issues.append(f"Missing <h1> tag in {rel}")
                elif len(h1s) > 1:
                    issues.append(f"Multiple <h1> tags ({len(h1s)}) detected in {rel}")
                elif not re.sub(r'<[^>]+>', '', h1s[0]).strip():
                    issues.append(f"Empty <h1> tag detected in {rel}")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_single_h1_gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 5. Image Compression Gate
    def check_image_compression_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        images_checked = 0
        max_bytes = 500 * 1024  # 500 KB limit
        if target.exists():
            for ext in ["*.png", "*.jpg", "*.jpeg", "*.webp", "*.svg"]:
                for img in target.glob(f"**/{ext}"):
                    images_checked += 1
                    size = img.stat().st_size
                    if size > max_bytes:
                        rel = img.relative_to(target).as_posix()
                        issues.append(f"Image {rel} exceeds 500KB threshold ({size / 1024:.1f} KB)")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_image_compression_gate",
            "images_checked": images_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 6. Page Language Gate
    def check_page_language_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        pages_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                if p.name == "404.html":
                    continue
                pages_checked += 1
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r'<html\b[^>]*\blang=["\']([^"\']*)["\']', content, re.IGNORECASE)
                if not m:
                    issues.append(f"Missing lang attribute on <html> in {rel}")
                elif not (m.group(1).lower().startswith("en")):
                    issues.append(f"Invalid lang attribute '{m.group(1)}' (expected English) in {rel}")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_page_language_gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 7. Canonical Tags Gate
    def check_canonical_tags_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        pages_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                if p.name == "404.html":
                    continue
                pages_checked += 1
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r'<link\b[^>]*\brel=["\']canonical["\'][^>]*\bhref=["\']([^"\']*)["\']', content, re.IGNORECASE)
                if not m:
                    m = re.search(r'<link\b[^>]*\bhref=["\']([^"\']*)["\'][^>]*\brel=["\']canonical["\']', content, re.IGNORECASE)
                if not m:
                    issues.append(f"Missing canonical link tag in {rel}")
                else:
                    c_url = m.group(1).strip()
                    if not c_url.startswith("https://"):
                        issues.append(f"Canonical URL is not absolute HTTPS in {rel}: '{c_url}'")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_canonical_tags_gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 8. HTTP Link Canonical Gate (Rule 19 / Gate 26)
    def check_http_link_canonical_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        headers_file = target / "_headers"
        if not headers_file.is_file():
            issues.append(f"Missing _headers file at {headers_file}")
            return {
                "status": "FAIL",
                "gate": "check_http_link_canonical_gate",
                "headers_checked": 0,
                "violations_count": len(issues),
                "issues": issues,
            }

        content = headers_file.read_text(encoding="utf-8", errors="ignore")
        canonical_link_pattern = re.compile(
            r'Link:\s*<([^>]+)>;\s*rel=["\']?canonical["\']?',
            re.IGNORECASE
        )

        rules: Dict[str, List[str]] = {}
        current_route = None
        for line in content.splitlines():
            line_stripped = line.strip()
            if not line_stripped or line_stripped.startswith("#"):
                continue
            if not line.startswith(" ") and not line.startswith("\t"):
                current_route = line_stripped
                rules[current_route] = []
            elif current_route:
                rules[current_route].append(line_stripped)

        found_canonical_links = []
        for route, headers in rules.items():
            for h in headers:
                m = canonical_link_pattern.search(h)
                if m:
                    found_canonical_links.append((route, m.group(1)))

        if not found_canonical_links:
            issues.append("Zero RFC 5988 canonical Link headers found in dist/_headers")

        for ep in self.required_endpoints:
            matching = [url for r, url in found_canonical_links if r == ep]
            if not matching:
                issues.append(f"Missing RFC 5988 canonical Link header for machine endpoint {ep}")
            else:
                target_url = matching[0]
                if not target_url.startswith("https://"):
                    issues.append(f"Invalid canonical URL scheme in Link header for {ep}: '{target_url}'")
                if ep.endswith(".xml") or ep.endswith(".txt"):
                    if not target_url.endswith(ep):
                        issues.append(f"Canonical URL path mismatch in Link header for {ep}: '{target_url}'")

        if self.leaf_route_checker:
            issues.extend(self.leaf_route_checker(target, found_canonical_links))

        for r, url in found_canonical_links:
            if not url.startswith("https://"):
                issues.append(f"Link header canonical URL '{url}' for route '{r}' is not HTTPS")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_http_link_canonical_gate",
            "headers_checked": len(rules),
            "canonical_links_found": len(found_canonical_links),
            "violations_count": len(issues),
            "issues": issues,
        }

    # 9. AI Mode Manifest Gate
    def check_ai_mode_manifest_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        manifests_dir = target / "manifests"
        manifest_files = list(manifests_dir.glob("*.json")) if manifests_dir.exists() else []

        if not manifest_files:
            issues.append(f"Missing machine-readable calculation manifests in {manifests_dir}")
        else:
            for mf in manifest_files:
                try:
                    spec = json.loads(mf.read_text(encoding="utf-8"))
                    assert_ai_mode_calculation_manifest(spec)
                except Exception as ex:
                    issues.append(f"Calculation manifest {mf.name} failed AI Mode contract: {ex}")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_ai_mode_manifest_gate",
            "manifests_checked": len(manifest_files),
            "violations_count": len(issues),
            "issues": issues,
        }

    check_manifest_gate = check_ai_mode_manifest_gate

    # 10. Robots.txt Gate
    def check_robots_txt_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        robots_file = target / "robots.txt"
        if not robots_file.is_file():
            issues.append(f"Missing robots.txt at {robots_file}")
        else:
            content = robots_file.read_text(encoding="utf-8", errors="ignore")
            content_lower = content.lower()
            if "sitemap.xml" not in content_lower:
                issues.append("robots.txt missing Sitemap directive")
            if "sitemap-hubs.xml" not in content_lower:
                issues.append("robots.txt missing sitemap-hubs.xml directive")
            if "sitemap-leaves.xml" not in content_lower:
                issues.append("robots.txt missing sitemap-leaves.xml directive")
            if "allow: /" not in content_lower:
                issues.append("robots.txt missing 'Allow: /' directive")
            if "disallow: /signal/" not in content_lower:
                issues.append("robots.txt missing 'Disallow: /signal/'")

            # Parse robots.txt sections by user-agent
            sections: Dict[str, Dict[str, List[str]]] = {}
            current_agents: List[str] = []
            for raw_line in content.splitlines():
                line = raw_line.split("#")[0].strip()
                if not line:
                    current_agents = []
                    continue
                if ":" not in line:
                    continue
                key, val = [x.strip() for x in line.split(":", 1)]
                key_lower = key.lower()
                if key_lower == "user-agent":
                    agent = val.lower()
                    current_agents.append(agent)
                    if agent not in sections:
                        sections[agent] = {"allow": [], "disallow": []}
                elif key_lower == "allow" and current_agents:
                    for agent in current_agents:
                        sections[agent]["allow"].append(val)
                elif key_lower == "disallow" and current_agents:
                    for agent in current_agents:
                        sections[agent]["disallow"].append(val)

            def _is_path_disallowed(path: str, allows: List[str], disallows: List[str]) -> bool:
                norm_path = path if path.startswith("/") else f"/{path}"
                longest_allow = -1
                for a in allows:
                    a_clean = a.strip()
                    if not a_clean:
                        continue
                    if norm_path.startswith(a_clean):
                        if len(a_clean) > longest_allow:
                            longest_allow = len(a_clean)
                longest_disallow = -1
                for d in disallows:
                    d_clean = d.strip()
                    if not d_clean:
                        continue
                    if norm_path.startswith(d_clean):
                        if len(d_clean) > longest_disallow:
                            longest_disallow = len(d_clean)
                if longest_disallow > longest_allow:
                    return True
                return False

            def _is_bot_blocked(bot_name: str, path: str) -> bool:
                if bot_name in sections:
                    return _is_path_disallowed(path, sections[bot_name]["allow"], sections[bot_name]["disallow"])
                if "*" in sections:
                    return _is_path_disallowed(path, sections["*"]["allow"], sections["*"]["disallow"])
                return False

            # AI Search and User-Triggered bots must NOT be disallowed on root / or /tools/
            for bot in AI_SEARCH_BOTS + AI_USER_TRIGGERED_BOTS:
                if _is_bot_blocked(bot, "/"):
                    issues.append(f"robots.txt disallows AI search/user bot '{bot}' on root '/'")
                if _is_bot_blocked(bot, "/tools/"):
                    issues.append(f"robots.txt disallows AI search/user bot '{bot}' on '/tools/'")

            if self.strict_robots:
                if (self.tools or (target / "tools").is_dir()) and "allow: /tools/" not in content_lower:
                    issues.append("robots.txt missing 'Allow: /tools/' directive")
                for dis in ("/syndication/", "/staging/", "/test/", "/tests/"):
                    if (target / dis.strip("/")).is_dir() and f"disallow: {dis}" not in content_lower:
                        issues.append(f"robots.txt missing 'Disallow: {dis}'")

                for bot in AI_SEARCH_BOTS + AI_USER_TRIGGERED_BOTS:
                    if bot not in sections:
                        issues.append(f"robots.txt missing User-agent directive for AI crawler {bot}")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_robots_txt_gate",
            "violations_count": len(issues),
            "issues": issues,
        }

    # 11. Readable URLs Gate
    def check_readable_urls_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        if target.exists():
            for p in target.glob("**/*.html"):
                if p.name not in ["index.html", "404.html"]:
                    rel = p.relative_to(target).as_posix()
                    issues.append(f"Non-canonical URL path (raw .html file exposed): {rel}")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_readable_urls_gate",
            "violations_count": len(issues),
            "issues": issues,
        }

    # 12. Schema Markup Gate
    def check_schema_markup_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        schemas_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                if p.name == "404.html" or "signal" in p.parts:
                    continue
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                matches = re.findall(r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', content, re.IGNORECASE | re.DOTALL)
                if not matches:
                    issues.append(f"Missing Schema.org JSON-LD in {rel}")
                else:
                    for m in matches:
                        schemas_checked += 1
                        try:
                            parsed = json.loads(m)
                            if "@context" not in parsed and "@graph" not in parsed:
                                issues.append(f"Schema JSON missing @context or @graph in {rel}")
                        except Exception as ex:
                            issues.append(f"Invalid JSON-LD schema syntax in {rel}: {ex}")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_schema_markup_gate",
            "schemas_checked": schemas_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 13. Noindex Tags Gate
    def check_noindex_tags_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        pages_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                if p.name == "404.html" or "signal" in p.parts:
                    continue
                pages_checked += 1
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                if re.search(r'<meta[^>]*\bcontent=["\'][^"\']*noindex[^"\']*["\'][^>]*>', content, re.IGNORECASE):
                    issues.append(f"Public page {rel} contains accidental 'noindex' directive")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_noindex_tags_gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 14. Internal Linking Gate
    def check_internal_linking_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        pages_checked = 0
        tools_dir = target / "tools"
        if tools_dir.is_dir():
            for p in tools_dir.glob("**/index.html"):
                pages_checked += 1
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                links = re.findall(r'<a\b[^>]*\bhref=["\']([^"\']*)["\'][^>]*>(.*?)</a>', content, re.IGNORECASE | re.DOTALL)
                internal_links = [h for h, _ in links if h.startswith("/") or self.domain in h or self.canonical_base in h]
                if len(internal_links) < 3:
                    issues.append(f"Tool page {rel} has only {len(internal_links)} internal links (expected >= 3)")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_internal_linking_gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 15. Load Performance Gate
    def check_load_performance_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        pages_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                pages_checked += 1
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                for m in re.finditer(r'<script\b([^>]*)>', content, re.IGNORECASE):
                    attrs = m.group(1).lower()
                    if 'type="application/ld+json"' in attrs:
                        continue
                    if "src=" in attrs and not ("async" in attrs or "defer" in attrs):
                        issues.append(f"Render-blocking external script in {rel}: {attrs}")

            css_candidates = [
                target / "css" / "style.css",
                target / "static" / "css" / "style.css",
            ]
            for css_file in css_candidates:
                if css_file.is_file() and css_file.stat().st_size > 100 * 1024:
                    issues.append(f"Main CSS stylesheet exceeds 100KB: {css_file.stat().st_size} bytes")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_load_performance_gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 16. Meta Descriptions Gate
    def check_meta_descriptions_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        pages_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                if p.name == "404.html" or "signal" in p.parts:
                    continue
                pages_checked += 1
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']', content, re.IGNORECASE)
                if not m:
                    m = re.search(r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*name=["\']description["\']', content, re.IGNORECASE)
                if not m:
                    issues.append(f"Missing meta description in {rel}")
                else:
                    desc = html.unescape(m.group(1).strip())
                    if len(desc) < 50 or len(desc) > 165:
                        issues.append(f"Meta description length {len(desc)} outside 50-165 range in {rel}")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_meta_descriptions_gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 17. URL Redirects Gate
    def check_url_redirects_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        redirects_file = target / "_redirects"
        if redirects_file.is_file():
            content = redirects_file.read_text(encoding="utf-8", errors="ignore")
            for line_num, line in enumerate(content.splitlines(), start=1):
                line_clean = line.strip()
                if not line_clean or line_clean.startswith("#"):
                    continue
                parts = line_clean.split()
                if len(parts) < 2:
                    issues.append(f"Malformed redirect rule at line {line_num}: '{line_clean}'")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_url_redirects_gate",
            "violations_count": len(issues),
            "issues": issues,
        }

    # 18. Search Console Tag Gate
    def check_search_console_tag_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        pages_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                if p.name == "404.html":
                    continue
                pages_checked += 1
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r'<meta[^>]*name=["\']google-site-verification["\'][^>]*content=["\']([^"\']+)["\']', content, re.IGNORECASE)
                if not m:
                    m = re.search(r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*name=["\']google-site-verification["\']', content, re.IGNORECASE)
                if not m or not m.group(1).strip():
                    issues.append(f"Missing or empty google-site-verification meta tag in {rel}")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_search_console_tag_gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 19. Hide Test Pages Gate
    def check_hide_test_pages_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        signal_paths = [
            target / "signal" / "index.html",
            target / "static" / "signal" / "index.html",
        ]
        for sp in signal_paths:
            if sp.is_file():
                s_content = sp.read_text(encoding="utf-8", errors="ignore")
                has_noindex = bool(
                    re.search(r'<meta[^>]*name=["\']robots["\'][^>]*content=["\'][^"\']*noindex[^"\']*["\']', s_content, re.IGNORECASE)
                    or re.search(r'<meta[^>]*content=["\'][^"\']*noindex[^"\']*["\'][^>]*name=["\']robots["\']', s_content, re.IGNORECASE)
                )
                if not has_noindex:
                    issues.append(f"Signal intake page {sp.relative_to(target)} missing noindex in meta robots tag")

        robots_txt = target / "robots.txt"
        if robots_txt.is_file():
            robots_content = robots_txt.read_text(encoding="utf-8", errors="ignore")
            if "disallow: /signal/" not in robots_content.lower():
                issues.append(f"{robots_txt.relative_to(target)} is missing 'Disallow: /signal/'")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_hide_test_pages_gate",
            "violations_count": len(issues),
            "issues": issues,
        }

    # 20. No JS Rendering Gate
    def check_no_js_rendering_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        pages_checked = 0
        tools_dir = target / "tools"
        if tools_dir.is_dir():
            for p in tools_dir.glob("**/index.html"):
                pages_checked += 1
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                clean = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', content, flags=re.IGNORECASE)
                clean = re.sub(r'<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>', '', clean, flags=re.IGNORECASE)
                text = re.sub(r'<[^>]+>', ' ', clean)

                # Check for skeleton/placeholder containers and phrases
                placeholder_patterns = [
                    r'\bloading\.{0,3}\b',
                    r'\benable\s+javascript\b',
                    r'\bjavascript\s+is\s+required\b',
                    r'\bjavascript\s+required\b',
                    r'\bloading\s+application\b',
                    r'\bskeleton\b',
                ]
                substantive_text = text
                for pat in placeholder_patterns:
                    substantive_text = re.sub(pat, ' ', substantive_text, flags=re.IGNORECASE)

                words = [w for w in substantive_text.split() if w.strip()]
                if len(words) < 50:
                    issues.append(f"Insufficient static content without JavaScript ({len(words)} substantive words) in {rel}")
                if "<h1" not in content.lower():
                    issues.append(f"Missing <h1> tag in static HTML in {rel}")

                # If quick-answer container is present, verify non-empty text directly in static HTML
                m_qa = re.search(r'<aside[^>]*class=["\'][^"\']*quick-answer[^"\']*["\'][^>]*>(.*?)</aside>', content, re.IGNORECASE | re.DOTALL)
                if m_qa:
                    qa_raw = m_qa.group(1)
                    qa_text = re.sub(r'<[^>]+>', ' ', qa_raw).strip()
                    qa_substantive = qa_text
                    for pat in placeholder_patterns:
                        qa_substantive = re.sub(pat, ' ', qa_substantive, flags=re.IGNORECASE).strip()
                    if not qa_substantive:
                        issues.append(f"Quick-answer container is empty or contains only placeholders awaiting JavaScript hydration in {rel}")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_no_js_rendering_gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 21. Existence Gate (Auxiliary)
    def check_existence_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        tools_dir = target / "tools"
        if self.tools:
            for tool in self.tools:
                slug = tool.get("slug")
                if not slug:
                    continue
                tool_file = tools_dir / slug / "index.html"
                if not tool_file.is_file():
                    issues.append(f"Missing canonical HTML for tool '{slug}' at {tool_file}")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "Existence Gate",
            "issues": issues,
        }

    # 22. Title Length Gate (Auxiliary)
    def check_title_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        res = self.check_page_titles_gate(dist_dir)
        res["gate"] = "Title Length Gate"
        return res

    # 23. Snippet Gate (Auxiliary)
    def check_snippet_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        boxes_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                if p.name == "404.html" or "signal" in p.parts:
                    continue
                content = p.read_text(encoding="utf-8", errors="ignore")
                rel = p.relative_to(target).as_posix()
                m_snippet = re.search(r'<aside[^>]*class=["\'][^"\']*quick-answer[^"\']*["\'][^>]*>(.*?)</aside>', content, re.IGNORECASE | re.DOTALL)
                if m_snippet:
                    boxes_checked += 1
                    snippet_text = re.sub(r"<[^>]+>", " ", m_snippet.group(1))
                    words = [w for w in snippet_text.split() if w.strip()]
                    if not (40 <= len(words) <= 60):
                        issues.append(f"Quick-answer snippet has {len(words)} words (expected 40-60) in {rel}")

                    parser = SinglePassSEODocumentParser(self.brand_domain)
                    parser.feed(content)
                    if parser.has_nosnippet:
                        issues.append(f"Page {rel} contains 'nosnippet' directive, revoking search and AI snippet eligibility")
                    if parser.max_snippet is not None:
                        if parser.max_snippet == 0:
                            issues.append(f"Page {rel} contains 'max-snippet:0' directive, revoking search snippet eligibility")
                        elif parser.max_snippet > 0 and parser.quick_answer_text:
                            if len(parser.quick_answer_text) > parser.max_snippet:
                                issues.append(f"Page {rel} quick-answer ({len(parser.quick_answer_text)} chars) exceeds max-snippet:{parser.max_snippet} limit")
                    if parser.quick_answer_has_data_nosnippet:
                        issues.append(f"Page {rel} quick-answer container or ancestor contains 'data-nosnippet', excluding answer from search snippets and AI Overviews")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "Snippet Gate",
            "boxes_checked": boxes_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # Snippet Eligibility Gate
    def check_snippet_eligibility_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        pages_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                if p.name == "404.html" or "signal" in p.parts:
                    continue
                pages_checked += 1
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                parser = SinglePassSEODocumentParser(self.brand_domain)
                parser.feed(content)

                if parser.has_nosnippet:
                    issues.append(f"Page {rel} contains 'nosnippet' directive, revoking search and AI snippet eligibility")
                if parser.max_snippet is not None:
                    if parser.max_snippet == 0:
                        issues.append(f"Page {rel} contains 'max-snippet:0' directive, revoking search snippet eligibility")
                    elif parser.max_snippet > 0 and parser.quick_answer_text:
                        if len(parser.quick_answer_text) > parser.max_snippet:
                            issues.append(f"Page {rel} quick-answer ({len(parser.quick_answer_text)} chars) exceeds max-snippet:{parser.max_snippet} limit")
                if parser.quick_answer_has_data_nosnippet:
                    issues.append(f"Page {rel} quick-answer container or ancestor contains 'data-nosnippet', excluding answer from search snippets and AI Overviews")

            headers_file = target / "_headers"
            if headers_file.is_file():
                current_route = ""
                for raw_line in headers_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if not raw_line.startswith(" ") and not raw_line.startswith("\t"):
                        current_route = line
                    else:
                        if ":" in line:
                            h_name, h_val = line.split(":", 1)
                            if h_name.strip().lower() == "x-robots-tag":
                                val_lower = h_val.lower()
                                if not current_route.startswith("/signal"):
                                    if "nosnippet" in val_lower:
                                        issues.append(f"_headers applies 'nosnippet' to public route '{current_route}' via X-Robots-Tag")
                                    if re.search(r'max-snippet\s*:\s*0\b', val_lower):
                                        issues.append(f"_headers applies 'max-snippet:0' to public route '{current_route}' via X-Robots-Tag")
                                    if "noindex" in val_lower:
                                        issues.append(f"_headers applies 'noindex' to public route '{current_route}' via X-Robots-Tag")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_snippet_eligibility_gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 24. Schema Validation Gate (Auxiliary)
    def check_schema_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        res = self.check_schema_markup_gate(dist_dir)
        res["gate"] = "Schema Validation Gate"
        return res

    # 25. Citability Gate (Auxiliary)
    def check_citability_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        pages_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                rel = p.relative_to(target).as_posix()
                if "tools" not in p.parts:
                    continue
                pages_checked += 1
                content = p.read_text(encoding="utf-8", errors="ignore").lower()
                if "<ol" not in content:
                    issues.append(f"Missing <ol> calculation steps procedure in {rel}")
                if "<table" not in content and p.name != "index.html":
                    issues.append(f"Missing <table> comparison data in {rel}")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "Citability Gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 26. Cleanliness Gate (Auxiliary)
    def check_cleanliness_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        pages_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                pages_checked += 1
                content = p.read_text(encoding="utf-8", errors="ignore")
                rel = p.relative_to(target).as_posix()

                if "\u2014" in content or "\u2013" in content:
                    issues.append(f"Contains em-dash or en-dash in {rel}")

                content_lower = content.lower()
                for jargon in FORBIDDEN_JARGON:
                    if jargon.lower() in content_lower:
                        issues.append(f"Forbidden jargon or placeholder '{jargon}' detected in {rel}")
                        break

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "Cleanliness Gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 27. Instant Indexing Gate (Auxiliary)
    def check_indexing_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        res = self.check_sitemap_gate(dist_dir)
        res["gate"] = "Instant Indexing Gate"
        return res

    # 28. Zyppy 2026 Content Relevance Gate (12 Factors)
    def check_content_relevance_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        parsed_docs: Dict[str, Tuple[Path, str, SinglePassSEODocumentParser]] = {}
        if target.exists():
            for p in target.glob("**/*.html"):
                rel = p.relative_to(target).as_posix()
                raw_html = p.read_text(encoding="utf-8", errors="ignore")
                parser = SinglePassSEODocumentParser(brand_domain=self.domain)
                parser.feed(raw_html)
                parsed_docs[rel] = (p, raw_html, parser)

        pages_scanned = len(parsed_docs)

        manifests_dir = target / "manifests"
        manifest_files = list(manifests_dir.glob("*.json")) if manifests_dir.is_dir() else []
        sitemap_xml = target / "sitemap.xml"
        sitemap_hubs_xml = target / "sitemap-hubs.xml"
        sitemap_leaves_xml = target / "sitemap-leaves.xml"
        feed_xml = target / "feed.xml"
        llms_txt = target / "llms.txt"
        llms_full_txt = target / "llms-full.txt"
        robots_txt = target / "robots.txt"

        endpoints_scanned = len(manifest_files)
        for ep in [sitemap_xml, sitemap_hubs_xml, sitemap_leaves_xml, feed_xml, llms_txt, llms_full_txt, robots_txt]:
            if ep.is_file():
                endpoints_scanned += 1

        vacuous_pass = (pages_scanned < 10 or endpoints_scanned < 5)
        findings: List[Dict[str, Any]] = []

        # Factor 1: Search Intent Match (weight 2.60)
        gaps_1: List[str] = []
        if vacuous_pass:
            gaps_1.append("Vacuous Pass Prevention: pages_scanned < 10 or endpoints_scanned < 5")
        else:
            for rel, (p, raw, parser) in parsed_docs.items():
                if rel in ("404.html", "privacy/index.html", "about/index.html") or "signal" in p.parts or "static" in p.parts:
                    continue
                if self.is_calculation_leaf:
                    leaf_err = self.is_calculation_leaf(rel, p, parser)
                    if leaf_err:
                        gaps_1.append(leaf_err)
                elif rel.startswith("tools/") and rel != "tools/index.html":
                    if not parser.has_calculator:
                        gaps_1.append(f"{rel}: Missing interactive calculator controls or calculation container")

            if len(manifest_files) < self.min_manifests:
                gaps_1.append(f"Insufficient calculation manifests: found {len(manifest_files)}, expected >= {self.min_manifests}")

            for mf in manifest_files:
                try:
                    mdata = json.loads(mf.read_text(encoding="utf-8"))
                    for req_key in ("formula", "inputs", "sample_calculation"):
                        if req_key not in mdata or not mdata[req_key]:
                            gaps_1.append(f"{mf.relative_to(target).as_posix()}: Missing manifest key '{req_key}'")
                except Exception as ex:
                    gaps_1.append(f"{mf.relative_to(target).as_posix()}: JSON parse failure: {ex}")

        findings.append({
            "factor": "Search Intent Match",
            "weight": 2.60,
            "status": "PASS" if not gaps_1 else "FAIL",
            "passed": len(gaps_1) == 0,
            "gap_count": len(gaps_1),
            "pages_scanned": pages_scanned,
            "examples": gaps_1[:3],
        })

        # Factor 2: Page Semantic Relevance (weight 2.34)
        gaps_2: List[str] = []
        if vacuous_pass:
            gaps_2.append("Vacuous Pass Prevention: pages_scanned < 10 or endpoints_scanned < 5")
        else:
            for rel, (p, raw, parser) in parsed_docs.items():
                if rel in ("404.html", "privacy/index.html", "about/index.html", "index.html", "tools/index.html") or "signal" in p.parts or "static" in p.parts:
                    continue
                schema_types = []
                for block in parser.json_ld_blocks:
                    try:
                        sdata = json.loads(block)
                        if isinstance(sdata, dict):
                            st = sdata.get("@type")
                            if isinstance(st, list):
                                schema_types.extend(st)
                            elif st:
                                schema_types.append(st)
                            if "@graph" in sdata and isinstance(sdata["@graph"], list):
                                for gitm in sdata["@graph"]:
                                    gt = gitm.get("@type")
                                    if isinstance(gt, list):
                                        schema_types.extend(gt)
                                    elif gt:
                                        schema_types.append(gt)
                        elif isinstance(sdata, list):
                            for sitm in sdata:
                                st = sitm.get("@type")
                                if st:
                                    schema_types.append(st)
                    except Exception:
                        pass
                unique_types = set(schema_types)
                if len(unique_types) < 2:
                    gaps_2.append(f"{rel}: Unstacked JSON-LD schema (only {len(unique_types)} @type found)")

                all_headings = parser.h1_list + parser.h2_list
                for h in all_headings:
                    words = h.split()
                    if any(len(w) == 1 and w.isupper() and w not in ('A', 'I') for w in words):
                        gaps_2.append(f"{rel}: Chopped entity label in heading ('{h}')")
                        break

        findings.append({
            "factor": "Page Semantic Relevance",
            "weight": 2.34,
            "status": "PASS" if not gaps_2 else "FAIL",
            "passed": len(gaps_2) == 0,
            "gap_count": len(gaps_2),
            "pages_scanned": pages_scanned,
            "examples": gaps_2[:3],
        })

        # Factor 3: Site Topical Authority (weight 2.29)
        gaps_3: List[str] = []
        if vacuous_pass:
            gaps_3.append("Vacuous Pass Prevention: pages_scanned < 10 or endpoints_scanned < 5")
        else:
            for rel, (p, raw, parser) in parsed_docs.items():
                if rel in ("404.html", "privacy/index.html", "about/index.html", "index.html", "tools/index.html") or "signal" in p.parts or "static" in p.parts:
                    continue
                if p.parent != target / "tools" and p.parent.parent == target / "tools":
                    if len(parser.internal_links) < 3:
                        gaps_3.append(f"{rel}: Insufficient internal links ({len(parser.internal_links)} < 3)")
            if not sitemap_xml.is_file() or not sitemap_hubs_xml.is_file() or not sitemap_leaves_xml.is_file():
                gaps_3.append("Missing one or more required sitemaps (sitemap.xml, sitemap-hubs.xml, sitemap-leaves.xml)")
            if not feed_xml.is_file():
                gaps_3.append("Missing syndication feed.xml")

        findings.append({
            "factor": "Site Topical Authority",
            "weight": 2.29,
            "status": "PASS" if not gaps_3 else "FAIL",
            "passed": len(gaps_3) == 0,
            "gap_count": len(gaps_3),
            "pages_scanned": pages_scanned,
            "examples": gaps_3[:3],
        })

        # Factor 4: Title Relevance (weight 2.26)
        gaps_4: List[str] = []
        dangling_stopwords = {"and", "or", "for", "with", "in", "to", "of", "section", "capital"}
        if vacuous_pass:
            gaps_4.append("Vacuous Pass Prevention: pages_scanned < 10 or endpoints_scanned < 5")
        else:
            for rel, (p, raw, parser) in parsed_docs.items():
                if rel == "404.html" or "signal" in p.parts or "static" in p.parts:
                    continue
                t = html.unescape(parser.title)
                if not t:
                    gaps_4.append(f"{rel}: Empty <title>")
                    continue
                if len(t) < 50 or len(t) > 60:
                    gaps_4.append(f"{rel}: Title length {len(t)} outside 50-60 chars ('{t}')")
                if "| |" in t:
                    gaps_4.append(f"{rel}: Delimiter corruption '| |' in title ('{t}')")
                if "\u2014" in t or "\u2013" in t:
                    gaps_4.append(f"{rel}: Title contains em-dash or en-dash ('{t}')")
                base_t = re.sub(rf'\s*\|\s*{re.escape(self.brand_name)}\s*$', '', t, flags=re.IGNORECASE).strip()
                words = base_t.split()
                if words and words[-1].lower() in dangling_stopwords:
                    gaps_4.append(f"{rel}: Dangling trailing stopword '{words[-1]}' before brand suffix ('{t}')")

        findings.append({
            "factor": "Title Relevance",
            "weight": 2.26,
            "status": "PASS" if not gaps_4 else "FAIL",
            "passed": len(gaps_4) == 0,
            "gap_count": len(gaps_4),
            "pages_scanned": pages_scanned,
            "examples": gaps_4[:3],
        })

        # Factor 5: Passage-level Relevance (weight 1.99)
        gaps_5: List[str] = []
        if vacuous_pass:
            gaps_5.append("Vacuous Pass Prevention: pages_scanned < 10 or endpoints_scanned < 5")
        else:
            for rel, (p, raw, parser) in parsed_docs.items():
                if rel in ("404.html", "privacy/index.html", "about/index.html", "index.html", "tools/index.html") or "signal" in p.parts or "static" in p.parts:
                    continue
                qa = parser.quick_answer_text
                if not qa:
                    gaps_5.append(f"{rel}: Missing quick-answer aside container")
                    continue
                words = qa.split()
                if len(words) < 40 or len(words) > 60:
                    gaps_5.append(f"{rel}: Quick-answer word count {len(words)} outside 40-60 range")
                if "\u2014" in qa or "\u2013" in qa:
                    gaps_5.append(f"{rel}: Quick-answer contains em-dash or en-dash")

        findings.append({
            "factor": "Passage-level Relevance",
            "weight": 1.99,
            "status": "PASS" if not gaps_5 else "FAIL",
            "passed": len(gaps_5) == 0,
            "gap_count": len(gaps_5),
            "pages_scanned": pages_scanned,
            "examples": gaps_5[:3],
        })

        # Factor 6: Language Match (weight 1.95)
        gaps_6: List[str] = []
        if vacuous_pass:
            gaps_6.append("Vacuous Pass Prevention: pages_scanned < 10 or endpoints_scanned < 5")
        else:
            for rel, (p, raw, parser) in parsed_docs.items():
                if rel == "404.html" or "signal" in p.parts or "static" in p.parts:
                    continue
                if not parser.root_lang or not parser.root_lang.startswith("en"):
                    gaps_6.append(f"{rel}: Root <html lang='{parser.root_lang}'> missing or not 'en'")
                if parser.meta_content_language.lower() != "en-us":
                    gaps_6.append(f"{rel}: Missing <meta http-equiv='content-language' content='en-US'>")
                if not ("en-us" in parser.hreflangs and "x-default" in parser.hreflangs):
                    gaps_6.append(f"{rel}: Missing canonical self-referential hreflang alternate links ('en-US', 'x-default')")
            if feed_xml.is_file():
                feed_text = feed_xml.read_text(encoding="utf-8")
                if "<language>en-US</language>" not in feed_text and "<language>en-us</language>" not in feed_text:
                    gaps_6.append("feed.xml missing <language>en-US</language>")

        findings.append({
            "factor": "Language Match",
            "weight": 1.95,
            "status": "PASS" if not gaps_6 else "FAIL",
            "passed": len(gaps_6) == 0,
            "gap_count": len(gaps_6),
            "pages_scanned": pages_scanned,
            "examples": gaps_6[:3],
        })

        # Factor 7: Geographic Relevance (weight 1.89)
        gaps_7: List[str] = []
        if vacuous_pass:
            gaps_7.append("Vacuous Pass Prevention: pages_scanned < 10 or endpoints_scanned < 5")
        else:
            for rel, (p, raw, parser) in parsed_docs.items():
                if "signal" in p.parts or "static" in p.parts:
                    continue
                if self.is_geo_leaf:
                    is_geo = self.is_geo_leaf(rel, p)
                else:
                    is_geo = ("/state/" in rel) or (
                        "/irs-2027-tax-brackets/" in rel and p.parent.name != "irs-2027-tax-brackets"
                    ) or (
                        "/section-1031-calculator/" in rel and p.parent.name != "section-1031-calculator"
                    )
                if is_geo:
                    if not parser.geo_region or not parser.geo_region.startswith("US-"):
                        gaps_7.append(f"{rel}: Missing <meta name='geo.region' content='US-...'>")
                    has_spatial = any("spatialCoverage" in blk or "areaServed" in blk for blk in parser.json_ld_blocks)
                    if not has_spatial:
                        gaps_7.append(f"{rel}: Missing spatialCoverage or areaServed in Schema.org JSON-LD")

        findings.append({
            "factor": "Geographic Relevance",
            "weight": 1.89,
            "status": "PASS" if not gaps_7 else "FAIL",
            "passed": len(gaps_7) == 0,
            "gap_count": len(gaps_7),
            "pages_scanned": pages_scanned,
            "examples": gaps_7[:3],
        })

        # Factor 8: Keywords in H1 (weight 1.67)
        gaps_8: List[str] = []
        if vacuous_pass:
            gaps_8.append("Vacuous Pass Prevention: pages_scanned < 10 or endpoints_scanned < 5")
        else:
            for rel, (p, raw, parser) in parsed_docs.items():
                if rel in ("404.html", "about/index.html") or "signal" in p.parts or "static" in p.parts:
                    continue
                if len(parser.h1_list) != 1:
                    gaps_8.append(f"{rel}: Expected exactly 1 <h1>, found {len(parser.h1_list)}")
                    continue
                h1 = parser.h1_list[0]
                if not h1:
                    gaps_8.append(f"{rel}: Empty <h1>")
                    continue
                if len(h1) < 20 or len(h1) > 70:
                    gaps_8.append(f"{rel}: H1 length {len(h1)} outside 20-70 range ('{h1}')")
                if self.brand_name in h1 or f"| {self.brand_name}" in h1:
                    gaps_8.append(f"{rel}: H1 contains brand suffix '| {self.brand_name}' ('{h1}')")

        findings.append({
            "factor": "Keywords in H1",
            "weight": 1.67,
            "status": "PASS" if not gaps_8 else "FAIL",
            "passed": len(gaps_8) == 0,
            "gap_count": len(gaps_8),
            "pages_scanned": pages_scanned,
            "examples": gaps_8[:3],
        })

        # Factor 9: Keywords in Subheadings (weight 1.27)
        gaps_9: List[str] = []
        if vacuous_pass:
            gaps_9.append("Vacuous Pass Prevention: pages_scanned < 10 or endpoints_scanned < 5")
        else:
            for rel, (p, raw, parser) in parsed_docs.items():
                if rel in ("404.html", "privacy/index.html", "about/index.html", "index.html", "tools/index.html") or "signal" in p.parts or "static" in p.parts:
                    continue
                if len(parser.h2_list) < 2:
                    gaps_9.append(f"{rel}: Less than 2 <h2> subheadings ({len(parser.h2_list)})")
                if len(parser.h2_list) != len(set(parser.h2_list)):
                    gaps_9.append(f"{rel}: Duplicate <h2> subheadings detected")
                for h in parser.h2_list:
                    words = h.split()
                    if any(len(w) == 1 and w.isupper() and w not in ('A', 'I') for w in words):
                        gaps_9.append(f"{rel}: Chopped word in <h2> heading ('{h}')")
                        break

        findings.append({
            "factor": "Keywords in Subheadings",
            "weight": 1.27,
            "status": "PASS" if not gaps_9 else "FAIL",
            "passed": len(gaps_9) == 0,
            "gap_count": len(gaps_9),
            "pages_scanned": pages_scanned,
            "examples": gaps_9[:3],
        })

        # Factor 10: Keywords in URL (weight 1.07)
        gaps_10: List[str] = []
        kebab_pat = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')
        if vacuous_pass:
            gaps_10.append("Vacuous Pass Prevention: pages_scanned < 10 or endpoints_scanned < 5")
        else:
            for rel, (p, raw, parser) in parsed_docs.items():
                if "static" in p.parts or "signal" in p.parts:
                    continue
                parts = [part for part in Path(rel).parts if part not in ("index.html", "404.html")]
                for part in parts:
                    if not kebab_pat.match(part):
                        gaps_10.append(f"{rel}: Path segment '{part}' violates lowercase kebab-case format")
                        break

        findings.append({
            "factor": "Keywords in URL",
            "weight": 1.07,
            "status": "PASS" if not gaps_10 else "FAIL",
            "passed": len(gaps_10) == 0,
            "gap_count": len(gaps_10),
            "pages_scanned": pages_scanned,
            "examples": gaps_10[:3],
        })

        # Factor 11: Exact-Match Domain (weight 0.94)
        gaps_11: List[str] = []
        if vacuous_pass:
            gaps_11.append("Vacuous Pass Prevention: pages_scanned < 10 or endpoints_scanned < 5")
        else:
            domain_prefix = f"https://{self.domain}"
            for rel, (p, raw, parser) in parsed_docs.items():
                if rel == "404.html" or "signal" in p.parts or "static" in p.parts:
                    continue
                if parser.canonical_url and not parser.canonical_url.startswith(domain_prefix):
                    gaps_11.append(f"{rel}: Canonical URL not on {domain_prefix} ('{parser.canonical_url}')")
                if parser.og_url and not parser.og_url.startswith(domain_prefix):
                    gaps_11.append(f"{rel}: OpenGraph URL not on {domain_prefix} ('{parser.og_url}')")

        findings.append({
            "factor": "Exact-Match Domain",
            "weight": 0.94,
            "status": "PASS" if not gaps_11 else "FAIL",
            "passed": len(gaps_11) == 0,
            "gap_count": len(gaps_11),
            "pages_scanned": pages_scanned,
            "examples": gaps_11[:3],
        })

        # Factor 12: Meta Description (weight 0.22)
        gaps_12: List[str] = []
        if vacuous_pass:
            gaps_12.append("Vacuous Pass Prevention: pages_scanned < 10 or endpoints_scanned < 5")
        else:
            for rel, (p, raw, parser) in parsed_docs.items():
                if rel == "404.html" or "signal" in p.parts or "static" in p.parts:
                    continue
                md = parser.meta_description
                if not md:
                    gaps_12.append(f"{rel}: Missing meta description")
                    continue
                if len(md) < 50 or len(md) > 165:
                    gaps_12.append(f"{rel}: Meta description length {len(md)} outside 50-165 range ('{md}')")
                if re.search(r'\$\d+,\.\.\.', md) or re.search(r'\d+\.\.\.', md):
                    gaps_12.append(f"{rel}: Mid-number ellipsis truncation in meta description ('{md}')")
                if "\u2014" in md or "\u2013" in md:
                    gaps_12.append(f"{rel}: Meta description contains em-dash or en-dash ('{md}')")

        findings.append({
            "factor": "Meta Description",
            "weight": 0.22,
            "status": "PASS" if not gaps_12 else "FAIL",
            "passed": len(gaps_12) == 0,
            "gap_count": len(gaps_12),
            "pages_scanned": pages_scanned,
            "examples": gaps_12[:3],
        })

        failing_findings = [f for f in findings if not f["passed"]]
        overall_status = "PASS" if len(failing_findings) == 0 else "FAIL"

        return {
            "status": overall_status,
            "gate": "check_content_relevance_gate",
            "pages_scanned": pages_scanned,
            "endpoints_scanned": endpoints_scanned,
            "factors_evaluated": len(findings),
            "findings": findings,
            "gaps_sorted_by_weight_desc": sorted(failing_findings, key=lambda x: x["weight"], reverse=True),
            "top_gap": failing_findings[0] if failing_findings else None,
        }

    # =========================================================================
    # Master SEO Checklist Audit
    # =========================================================================
    def audit_seo_checklist(
        self,
        dist_dir: Optional[Path] = None,
        raise_on_error: bool = False,
        enforce_relevance: bool = True,
    ) -> Dict[str, Any]:
        """
        Executes master Opus 5.5 SEO & GEO audit checklist across static assets.
        Returns consolidated dictionary with status PASS/FAIL, all evaluated gates, and issue details.
        """
        target = Path(dist_dir) if dist_dir else self.dist_dir
        if not target.exists():
            err_dict = {
                "status": "FAIL",
                "reason": f"Target dist directory {target} does not exist.",
                "gates": {},
                "issues": [f"Directory {target} not found"],
                "total_issues_count": 1,
            }
            if raise_on_error:
                raise SEOVerificationError(f"Target dist directory {target} does not exist.", issues=err_dict["issues"])
            return err_dict

        content_relevance_gate = self.check_content_relevance_gate(target)

        gates = {
            "check_alt_text_gate": self.check_alt_text_gate(target),
            "check_sitemap_gate": self.check_sitemap_gate(target),
            "check_page_titles_gate": self.check_page_titles_gate(target),
            "check_single_h1_gate": self.check_single_h1_gate(target),
            "check_image_compression_gate": self.check_image_compression_gate(target),
            "check_page_language_gate": self.check_page_language_gate(target),
            "check_canonical_tags_gate": self.check_canonical_tags_gate(target),
            "check_robots_txt_gate": self.check_robots_txt_gate(target),
            "check_readable_urls_gate": self.check_readable_urls_gate(target),
            "check_schema_markup_gate": self.check_schema_markup_gate(target),
            "check_noindex_tags_gate": self.check_noindex_tags_gate(target),
            "check_internal_linking_gate": self.check_internal_linking_gate(target),
            "check_load_performance_gate": self.check_load_performance_gate(target),
            "check_meta_descriptions_gate": self.check_meta_descriptions_gate(target),
            "check_url_redirects_gate": self.check_url_redirects_gate(target),
            "check_search_console_tag_gate": self.check_search_console_tag_gate(target),
            "check_hide_test_pages_gate": self.check_hide_test_pages_gate(target),
            "check_no_js_rendering_gate": self.check_no_js_rendering_gate(target),
            "check_http_link_canonical_gate": self.check_http_link_canonical_gate(target),
            "check_snippet_eligibility_gate": self.check_snippet_eligibility_gate(target),
            "check_content_relevance_gate": content_relevance_gate,
            # Auxiliary and legacy aliases
            "check_ai_mode_manifest_gate": self.check_ai_mode_manifest_gate(target),
            "check_manifest_gate": self.check_ai_mode_manifest_gate(target),
            "existence_gate": self.check_existence_gate(target),
            "title_length_gate": self.check_title_gate(target),
            "snippet_gate": self.check_snippet_gate(target),
            "schema_gate": self.check_schema_gate(target),
            "citability_gate": self.check_citability_gate(target),
            "cleanliness_gate": self.check_cleanliness_gate(target),
            "indexing_gate": self.check_indexing_gate(target),
        }

        all_issues = []
        primary_keys = [
            "check_alt_text_gate",
            "check_sitemap_gate",
            "check_page_titles_gate",
            "check_single_h1_gate",
            "check_image_compression_gate",
            "check_page_language_gate",
            "check_canonical_tags_gate",
            "check_robots_txt_gate",
            "check_readable_urls_gate",
            "check_schema_markup_gate",
            "check_noindex_tags_gate",
            "check_internal_linking_gate",
            "check_load_performance_gate",
            "check_meta_descriptions_gate",
            "check_url_redirects_gate",
            "check_search_console_tag_gate",
            "check_hide_test_pages_gate",
            "check_no_js_rendering_gate",
            "check_http_link_canonical_gate",
            "check_snippet_eligibility_gate",
        ]

        for g_key in primary_keys:
            g_res = gates.get(g_key, {})
            if g_res.get("issues"):
                all_issues.extend(g_res["issues"])

        if enforce_relevance and content_relevance_gate.get("status") == "FAIL":
            for gap_item in content_relevance_gate.get("gaps_sorted_by_weight_desc", []):
                ex_summary = f" (e.g. {gap_item['examples'][0]})" if gap_item.get("examples") else ""
                all_issues.append(
                    f"Content Relevance ({gap_item['factor']}, weight {gap_item['weight']:.2f}): "
                    f"{gap_item['gap_count']} gaps detected{ex_summary}"
                )

        all_passed = len(all_issues) == 0

        result = {
            "status": "PASS" if all_passed else "FAIL",
            "craftsmanship_compliant": all_passed,
            "gates": gates,
            "issues": all_issues,
            "total_issues_count": len(all_issues),
            "content_relevance": content_relevance_gate,
        }

        if raise_on_error and not all_passed:
            issue_summary = "; ".join(all_issues[:3])
            if len(all_issues) > 3:
                issue_summary += f" (...and {len(all_issues) - 3} more)"
            raise SEOVerificationError(
                f"SEO checklist verification failed with {len(all_issues)} issues: {issue_summary}",
                issues=all_issues,
                gates=gates,
            )

        return result


# Default module-level MasterSEOVerifier instance
_default_verifier = MasterSEOVerifier()

check_alt_text_gate = _default_verifier.check_alt_text_gate
check_sitemap_gate = _default_verifier.check_sitemap_gate
check_page_titles_gate = _default_verifier.check_page_titles_gate
check_single_h1_gate = _default_verifier.check_single_h1_gate
check_image_compression_gate = _default_verifier.check_image_compression_gate
check_page_language_gate = _default_verifier.check_page_language_gate
check_canonical_tags_gate = _default_verifier.check_canonical_tags_gate
check_http_link_canonical_gate = _default_verifier.check_http_link_canonical_gate
check_ai_mode_manifest_gate = _default_verifier.check_ai_mode_manifest_gate
check_manifest_gate = _default_verifier.check_manifest_gate
check_robots_txt_gate = _default_verifier.check_robots_txt_gate
check_readable_urls_gate = _default_verifier.check_readable_urls_gate
check_schema_markup_gate = _default_verifier.check_schema_markup_gate
check_noindex_tags_gate = _default_verifier.check_noindex_tags_gate
check_internal_linking_gate = _default_verifier.check_internal_linking_gate
check_load_performance_gate = _default_verifier.check_load_performance_gate
check_meta_descriptions_gate = _default_verifier.check_meta_descriptions_gate
check_url_redirects_gate = _default_verifier.check_url_redirects_gate
check_search_console_tag_gate = _default_verifier.check_search_console_tag_gate
check_hide_test_pages_gate = _default_verifier.check_hide_test_pages_gate
check_no_js_rendering_gate = _default_verifier.check_no_js_rendering_gate
check_snippet_eligibility_gate = _default_verifier.check_snippet_eligibility_gate
check_existence_gate = _default_verifier.check_existence_gate
check_title_gate = _default_verifier.check_title_gate
check_snippet_gate = _default_verifier.check_snippet_gate
check_schema_gate = _default_verifier.check_schema_gate
check_citability_gate = _default_verifier.check_citability_gate
check_cleanliness_gate = _default_verifier.check_cleanliness_gate
check_indexing_gate = _default_verifier.check_indexing_gate
check_content_relevance_gate = _default_verifier.check_content_relevance_gate
audit_seo_checklist = _default_verifier.audit_seo_checklist
run_seo_checklist_audit = audit_seo_checklist
