"""
Red-Baseline Full-Estate Porcelain Gate Suite.
Verifies real compiled output and real central engine contracts across all 4 tenants
(profithelm, prexvo, gainhelm, lienbond) with zero mocked mocks.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pytest

from pseofactory import cli as pseo_cli
from pseofactory.browser_verifier import RouteManifestExtractor, UnifiedBrowserAuditor
from pseofactory.compiler import compile_lienbond_estate
from pseofactory.distributor import (
    compile_broken_calculator_link_reclamation_briefs,
    compile_public_benchmark_citation_hubs,
)
from pseofactory.edge import build_edge_headers
from pseofactory.maintenance import AssetDriftRecord, AssetIntegrityEvaluator, AssetIntegrityReport, DriftReason
from pseofactory.porcelain_shell import (
    _sync_sitemaps_headers_and_redirects,
    extract_defined_and_referenced_css_vars,
    generate_porcelain_stylesheet,
    get_porcelain_tenant_profile,
    normalize_html_to_porcelain_shell,
    sanitize_inline_styles_outside_svg,
)
from pseofactory.visual_primitives import normalize_html_visual_primitives


TENANT_REPOS: Dict[str, str] = {
    "profithelm": "profithelm-platform",
    "prexvo": "prexvo",
    "gainhelm": "gainhelm",
    "lienbond": "lienbond",
}

TENANT_DOMAINS: Dict[str, str] = {
    "profithelm": "profithelm.com",
    "prexvo": "prexvo.com",
    "gainhelm": "gainhelm.com",
    "lienbond": "lienbond.com",
}

# Explicit minimal JS/ARIA/state hook allowlist (non-layout behavioral hooks only).
STATE_OR_JS_HOOK_CLASSES: Set[str] = {
    "active",
    "open",
    "closed",
    "collapsed",
    "expanded",
    "selected",
    "disabled",
    "hidden",
    "visible",
    "sr-only",
    "visually-hidden",
}

NON_STATE_FEDERAL_OR_GLOBAL_TOOL_MARKERS: Tuple[str, ...] = (
    "soc-2-audit-cost-calculator",
    "eu-ai-act-high-risk-conformity-assessment-cost-calculator",
    "iso-27001-certification-cost-calculator",
    "dora-ict-third-party-risk-compliance-cost-calculator",
    "pci-dss-4-0-compliance-cost-calculator",
    "fedramp-authorization-3pao-cost-calculator",
    "nist-800-171-sprs-score-calculator",
    "cmmc-2-0-compliance-cost-calculator",
    "student-loans-gov",
    "pslf-qualifying-payment-simulator",
    "pslf-buyback-months-reconsideration-student-loan-calculator",
    "rap-payment-calculator",
    "rap-vs-ibr-calculator",
    "surety-bond-cost-calculator-philippines",
    "miller-act-performance-and-payment-bond-premium-calculator",
    "erisa-fidelity-bond-coverage-amount-calculator",
    "davis-bacon-prevailing-wage-fringe-benefit-rate-calculator",
    "saas-runway-calculator",
    "section-301-tariff-landed-cost-calculator",
)


def _resolve_workspace_root() -> Optional[Path]:
    env_ws = os.environ.get("PSEOFACTORY_WORKSPACE_ROOT", "").strip()
    if env_ws:
        cand = Path(env_ws)
        if cand.is_dir():
            return cand
    cur = Path(__file__).resolve().parent
    for _ in range(8):
        if any((cur / repo / "dist").is_dir() for repo in TENANT_REPOS.values()):
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def _require_tenant_dist(tenant_id: str) -> Path:
    ws_root = _resolve_workspace_root()
    if ws_root is None:
        pytest.skip(f"Sibling tenant checkout missing in standalone CI for {tenant_id}")
    dist_dir = ws_root / TENANT_REPOS[tenant_id] / "dist"
    if not dist_dir.is_dir() or not (dist_dir / "index.html").is_file():
        pytest.skip(f"Tenant dist missing on disk: {dist_dir}")
    return dist_dir


def _iter_public_html_files(dist_dir: Path) -> List[Path]:
    out: List[Path] = []
    for hp in sorted(dist_dir.rglob("*.html")):
        rel = hp.relative_to(dist_dir).as_posix()
        if rel.startswith(("signal/", "static/signal/")):
            continue
        out.append(hp)
    return out


def _strip_script_and_style_blocks(html_text: str) -> str:
    return re.sub(r"<(script|style)\b[^>]*>[\s\S]*?</\1>", "", html_text, flags=re.IGNORECASE)


def _strip_css_comments(css_text: str) -> str:
    return re.sub(r"/\*[\s\S]*?\*/", "", css_text)


def _parse_css_blocks(css_text: str) -> List[Tuple[str, str, Optional[str]]]:
    """
    Parses CSS rules into (selector_header, declaration_body, enclosing_media_query).
    Handles nested @media / @supports blocks with balanced braces.
    """
    cleaned = _strip_css_comments(css_text)
    rules: List[Tuple[str, str, Optional[str]]] = []

    def _walk(chunk: str, media_ctx: Optional[str]) -> None:
        i = 0
        n = len(chunk)
        while i < n:
            while i < n and chunk[i].isspace():
                i += 1
            if i >= n:
                break
            brace_idx = chunk.find("{", i)
            if brace_idx < 0:
                break
            header = chunk[i:brace_idx].strip()
            depth = 1
            j = brace_idx + 1
            while j < n and depth > 0:
                if chunk[j] == "{":
                    depth += 1
                elif chunk[j] == "}":
                    depth -= 1
                j += 1
            body = chunk[brace_idx + 1 : j - 1]
            if header.startswith("@media"):
                _walk(body, header)
            elif header.startswith("@"):
                if "{" in body:
                    _walk(body, media_ctx)
            else:
                rules.append((header, body, media_ctx))
            i = j

    _walk(cleaned, None)
    return rules


def _extract_defined_css_classes(css_text: str) -> Set[str]:
    defined: Set[str] = set()
    for selector_header, _, _ in _parse_css_blocks(css_text):
        for sel in selector_header.split(","):
            cleaned_sel = re.sub(r"\[[^\]]*\]", "", sel.strip())
            for m in re.finditer(r"\.([a-zA-Z_-][a-zA-Z0-9_-]*)", cleaned_sel):
                defined.add(m.group(1))
    return defined


def _extract_css_class_declarations(css_text: str, target_class: str) -> List[Tuple[Optional[str], str, str]]:
    """Returns [(media_ctx, selector, body)] for rules targeting target_class."""
    hits: List[Tuple[Optional[str], str, str]] = []
    cls_pat = re.compile(rf"\.{re.escape(target_class)}(?![a-zA-Z0-9_-])")
    for selector_header, body, media_ctx in _parse_css_blocks(css_text):
        for sel in selector_header.split(","):
            s = sel.strip()
            if cls_pat.search(s):
                hits.append((media_ctx, s, body))
    return hits


def _selector_specificity(selector: str) -> Tuple[int, int, int]:
    """Computes (id_count, class_attr_pseudo_count, tag_count) for CSS selectors."""
    s = re.sub(r"::?(?:not|is|where)\([^)]*\)", "", selector)
    s = re.sub(r"\[[^\]]+\]", ".ATTR", s)
    ids = len(re.findall(r"#[a-zA-Z_-][a-zA-Z0-9_-]*", s))
    classes_pseudos = len(re.findall(r"(?:\.[a-zA-Z_-][a-zA-Z0-9_-]*|:[a-zA-Z_-][a-zA-Z0-9_-]*)", s))
    no_ids_cls = re.sub(r"(?:#|\.|::?)[a-zA-Z_-][a-zA-Z0-9_-]*(?:\([^)]*\))?", " ", s)
    tags = len(re.findall(r"\b[a-zA-Z][a-zA-Z0-9]*\b", no_ids_cls))
    return (ids, classes_pseudos, tags)


def _selector_matches_anchor_nav_cta(selector: str) -> bool:
    """Checks if a CSS selector matches <a class='btn btn-cta nav-cta-desktop touch-target'>."""
    if ".nav-cta-desktop" not in selector:
        return False
    parts = [p for p in re.split(r"[\s>+~]+", selector.strip()) if p]
    if not parts:
        return False
    subject = parts[-1]
    tag_m = re.match(r"^([a-zA-Z][a-zA-Z0-9]*)", subject)
    if tag_m and tag_m.group(1).lower() != "a":
        return False
    req_classes = set(re.findall(r"\.([a-zA-Z_-][a-zA-Z0-9_-]*)", subject))
    allowed = {"btn", "btn-cta", "nav-cta-desktop", "touch-target"}
    return "nav-cta-desktop" in req_classes and req_classes.issubset(allowed)


def _is_hook_only_class(cls_name: str) -> bool:
    return (
        cls_name in STATE_OR_JS_HOOK_CLASSES
        or cls_name.startswith(("js-", "is-", "has-"))
    )


def _extract_undefined_ui_classes(dist_dir: Path, css_text: str) -> Dict[str, int]:
    defined = _extract_defined_css_classes(css_text)
    used_counts: Dict[str, int] = {}
    for hp in _iter_public_html_files(dist_dir):
        body = _strip_script_and_style_blocks(hp.read_text(encoding="utf-8", errors="ignore"))
        for cls_attr in re.findall(r'\bclass\s*=\s*["\']([^"\']+)["\']', body):
            for tok in cls_attr.split():
                if tok and not _is_hook_only_class(tok):
                    used_counts[tok] = used_counts.get(tok, 0) + 1
    return {c: cnt for c, cnt in used_counts.items() if c not in defined}


def _parse_headers_blocks(headers_text: str) -> List[Tuple[str, List[str]]]:
    blocks: List[Tuple[str, List[str]]] = []
    cur_route: Optional[str] = None
    cur_lines: List[str] = []
    for raw in headers_text.splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            if not s and cur_route is not None:
                blocks.append((cur_route, cur_lines))
                cur_route = None
                cur_lines = []
            continue
        if not raw[:1].isspace():
            if cur_route is not None:
                blocks.append((cur_route, cur_lines))
            cur_route = s
            cur_lines = []
        elif cur_route is not None:
            cur_lines.append(s)
    if cur_route is not None:
        blocks.append((cur_route, cur_lines))
    return blocks


def _resolve_url_to_dist(dist_dir: Path, domain: str, raw_url: str) -> Optional[Path]:
    u = raw_url.strip()
    if u.startswith(f"https://{domain}") or u.startswith(f"http://{domain}"):
        path_part = re.sub(r"^https?://[^/]+", "", u).split("?", 1)[0].split("#", 1)[0]
    elif u.startswith("/"):
        path_part = u.split("?", 1)[0].split("#", 1)[0]
    else:
        return None
    if not path_part or path_part == "/":
        return dist_dir / "index.html"
    rel = path_part.lstrip("/")
    direct = dist_dir / rel
    if direct.is_file():
        return direct
    return dist_dir / rel.rstrip("/") / "index.html"


@pytest.fixture(scope="module")
def compiled_lienbond_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("compiled_lienbond_gate")
    compile_lienbond_estate(root)
    return root


def test_sanitizer_preserves_horizontal_padding_despite_2px_substring() -> None:
    """
    sanitize_inline_styles_outside_svg must NOT drop valid padding such as '6px 12px'
    or '8px 21px' due to naive substring checks like '2px' in '12px'.
    """
    css = generate_porcelain_stylesheet("profithelm")
    known_vars, _ = extract_defined_and_referenced_css_vars(css)

    snippet = (
        '<a href="#partner-registration-drawer" class="touch-target hero-register-firm-link" '
        'style="padding: 6px 12px; min-height: 44px;">Register Your Firm</a>'
    )
    sanitized = sanitize_inline_styles_outside_svg(snippet, known_vars)
    failures: List[str] = []
    if "padding" not in sanitized or "12px" not in sanitized:
        failures.append(f"6px 12px stripped: {sanitized}")

    snippet_21 = (
        '<a href="#partner-registration-drawer" class="touch-target hero-register-firm-link" '
        'style="padding: 8px 21px; min-height: 44px;">Register Your Firm</a>'
    )
    sanitized_21 = sanitize_inline_styles_outside_svg(snippet_21, known_vars)
    if "padding" not in sanitized_21 or "21px" not in sanitized_21:
        failures.append(f"8px 21px stripped: {sanitized_21}")

    full_html = (
        "<!DOCTYPE html><html lang='en'><head><title>Sec 179 | ProfitHelm</title>"
        "<meta name='description' content='Section 179 equipment deduction calculator.'></head>"
        "<body><main><h1>Section 179</h1>"
        f"<section class='hero-section tool-hero card'>{snippet}</section>"
        "</main></body></html>"
    )
    norm_html, _ = normalize_html_to_porcelain_shell(
        full_html,
        "tools/section-179-calculator/index.html",
        get_porcelain_tenant_profile("profithelm"),
    )
    has_inline_pad = bool(
        re.search(
            r'class=["\'][^"\']*\bhero-register-firm-link\b[^"\']*["\'][^>]*style=["\'][^"\']*padding:\s*6px\s+12px',
            norm_html,
            flags=re.IGNORECASE,
        )
    )
    css_pad_rules = [
        body
        for _, _, body in _extract_css_class_declarations(css, "hero-register-firm-link")
        if re.search(r"\bpadding\s*:", body)
    ]
    if not has_inline_pad and not css_pad_rules:
        failures.append("Normalized HTML and Porcelain CSS left .hero-register-firm-link with zero padding")

    assert not failures, f"Sanitizer horizontal padding failures: {failures}"


def test_mobile_375px_nav_cta_desktop_specificity_overrides_btn_cta() -> None:
    """
    Inside @media (max-width: 768px), .nav-cta-desktop must win the CSS cascade over
    desktop base rule `a.btn-cta { display: inline-flex; }` (specificity (0, 1, 1)).
    """
    failures: List[str] = []
    for tid in ("profithelm", "prexvo", "gainhelm", "lienbond"):
        css = generate_porcelain_stylesheet(tid)
        desktop_a_btn_spec = (0, 0, 0)
        for media_ctx, sel, body in _extract_css_class_declarations(css, "btn-cta"):
            if media_ctx is None and re.search(r"\bdisplay\s*:\s*inline-flex\b", body):
                spec = _selector_specificity(sel)
                if spec > desktop_a_btn_spec:
                    desktop_a_btn_spec = spec
        if desktop_a_btn_spec < (0, 1, 1):
            failures.append(f"[{tid}] missing desktop a.btn-cta display:inline-flex baseline")
            continue

        mobile_hide_winners: List[Tuple[str, Tuple[int, int, int], bool]] = []
        for media_ctx, sel, body in _extract_css_class_declarations(css, "nav-cta-desktop"):
            if media_ctx and "max-width" in media_ctx and "768px" in media_ctx:
                if re.search(r"\bdisplay\s*:\s*none\b", body) and _selector_matches_anchor_nav_cta(sel):
                    has_imp = bool(re.search(r"\bdisplay\s*:\s*none\s*!important\b", body))
                    spec = _selector_specificity(sel)
                    if has_imp or spec >= desktop_a_btn_spec:
                        mobile_hide_winners.append((sel, spec, has_imp))

        if not mobile_hide_winners:
            failures.append(
                f"[{tid}] mobile @media (max-width: 768px) .nav-cta-desktop loses specificity to "
                f"a.btn-cta {desktop_a_btn_spec}"
            )
    assert not failures, "; ".join(failures)


@pytest.mark.xdist_group("lienbond_compiled")
def test_compiled_lienbond_stylesheet_covers_all_rendered_ui_classes(compiled_lienbond_root: Path) -> None:
    """
    Freshly compiled compile_lienbond_estate dist/css/style.css must define selectors for every
    rendered UI/layout class in non-/signal/ dist/**/*.html (minus explicit behavioral hooks).
    """
    dist_dir = compiled_lienbond_root / "dist"
    css_path = dist_dir / "css" / "style.css"
    assert css_path.is_file(), f"Missing stylesheet {css_path}"
    css_text = css_path.read_text(encoding="utf-8", errors="ignore")

    defined = _extract_defined_css_classes(css_text)
    missing_core = [
        cls_name
        for cls_name in (
            "workpaper-unlock-card",
            "workpaper-preview-controls",
            "calc-number-input",
            "comparison-table",
            "hero-register-firm-link",
            "post-calc-upgrade-drawer",
            "post-calc-upgrade-btn",
            "serp-intent-banner",
            "faq-section",
        )
        if cls_name not in defined
    ]
    undef = _extract_undefined_ui_classes(dist_dir, css_text)
    top_missing = sorted(undef.items(), key=lambda kv: (-kv[1], kv[0]))[:25]
    assert not missing_core and not undef, (
        f"Compiled LienBond style.css missing_core={missing_core}, "
        f"total_undef={len(undef)} top={top_missing}"
    )


@pytest.mark.host_estate
@pytest.mark.parametrize("tenant_id", ["profithelm", "prexvo", "gainhelm", "lienbond"])
def test_real_dist_stylesheets_cover_all_rendered_ui_classes(tenant_id: str) -> None:
    """
    Every UI/layout CSS class rendered in real non-/signal/ dist/**/*.html must be defined in
    dist/css/style.css, and mobile .nav-cta-desktop must win over desktop a.btn-cta.
    """
    dist_dir = _require_tenant_dist(tenant_id)
    css_path = dist_dir / "css" / "style.css"
    assert css_path.is_file(), f"Missing stylesheet {css_path}"
    css_text = css_path.read_text(encoding="utf-8", errors="ignore")

    undef = _extract_undefined_ui_classes(dist_dir, css_text)
    top_missing = sorted(undef.items(), key=lambda kv: (-kv[1], kv[0]))[:25]

    mobile_hide_winners = [
        (sel, body)
        for media_ctx, sel, body in _extract_css_class_declarations(css_text, "nav-cta-desktop")
        if media_ctx
        and "768px" in media_ctx
        and re.search(r"\bdisplay\s*:\s*none\b", body)
        and _selector_matches_anchor_nav_cta(sel)
        and (
            re.search(r"\bdisplay\s*:\s*none\s*!important\b", body)
            or _selector_specificity(sel) >= (0, 1, 1)
        )
    ]
    assert not undef and mobile_hide_winners, (
        f"[{tenant_id}] undef_classes={len(undef)} top={top_missing}; "
        f"mobile_nav_cta_specificity_ok={bool(mobile_hide_winners)}"
    )


def _audit_html_hygiene_issues(dist_dir: Path, css_text: str) -> List[str]:
    issues: List[str] = []
    reg_link_has_css_pad = any(
        re.search(r"\bpadding\s*:", body)
        for _, _, body in _extract_css_class_declarations(css_text, "hero-register-firm-link")
    )

    for hp in _iter_public_html_files(dist_dir):
        rel = hp.relative_to(dist_dir).as_posix()
        raw = hp.read_text(encoding="utf-8", errors="ignore")
        visible = _strip_script_and_style_blocks(raw)

        if "round((" in visible:
            issues.append(f"{rel}: leaked raw Python formula 'round(('")

        if re.search(
            r'class=["\'][^"\']*\b(?:ymyl-disclaimer-banner|ftc-disclosure-card)\b',
            visible,
            flags=re.IGNORECASE,
        ):
            issues.append(f"{rel}: legacy clutter .ymyl-disclaimer-banner/.ftc-disclosure-card present")

        faq_sections = re.findall(
            r'<section\b[^>]*class=["\'][^"\']*\b(?:faq-section|overlay-faqs)\b[^"\']*["\']',
            visible,
            flags=re.IGNORECASE,
        )
        faq_headings = re.findall(
            r"<h[1-4]\b[^>]*>[^<]*Frequently Asked Questions",
            visible,
            flags=re.IGNORECASE,
        )
        if len(faq_sections) > 1 or len(faq_headings) > 1:
            issues.append(
                f"{rel}: duplicate FAQ blocks (sections={len(faq_sections)}, headings={len(faq_headings)})"
            )

        calc_containers = re.findall(
            r'class=["\'][^"\']*\b(?:interactive-calculator-container|calculation-container|calculator-grid)\b',
            visible,
        )
        calc_btns = re.findall(r'(?<![a-zA-Z0-9_-])id=["\'](?:calculate-btn|calc-submit-btn)["\']', visible)
        serp_wbs = re.findall(r'(?<![a-zA-Z0-9_-])id=["\']serp-incumbent-depth-workbench["\']', visible)
        if len(calc_containers) > 1 or len(calc_btns) > 1 or len(serp_wbs) > 1:
            issues.append(
                f"{rel}: duplicate calculator blocks (containers={len(calc_containers)}, "
                f"btns={len(calc_btns)}, serp_wb={len(serp_wbs)})"
            )

        if not reg_link_has_css_pad:
            m_reg = re.search(
                r'<a\b[^>]*class=["\'][^"\']*\bhero-register-firm-link\b[^"\']*["\'][^>]*>',
                visible,
                flags=re.IGNORECASE,
            )
            if m_reg and not re.search(r"\bpadding\s*:", m_reg.group(0), flags=re.IGNORECASE):
                issues.append(f"{rel}: .hero-register-firm-link has zero padding")

    return issues


@pytest.mark.xdist_group("lienbond_compiled")
def test_compiled_lienbond_estate_zero_raw_python_dup_calcs_dup_faqs_or_legacy_clutter(
    compiled_lienbond_root: Path,
) -> None:
    """
    Compiled compile_lienbond_estate output must have zero raw Python round(( formulas,
    zero duplicate calculators, zero duplicate FAQs, zero legacy disclaimer clutter, and
    non-zero padding on .hero-register-firm-link.
    """
    dist_dir = compiled_lienbond_root / "dist"
    css_text = (dist_dir / "css" / "style.css").read_text(encoding="utf-8", errors="ignore")
    issues = _audit_html_hygiene_issues(dist_dir, css_text)
    assert not issues, f"Compiled LienBond HTML hygiene failures ({len(issues)}): {issues[:12]}"


@pytest.mark.host_estate
@pytest.mark.parametrize("tenant_id", ["profithelm", "prexvo", "gainhelm", "lienbond"])
def test_real_dist_zero_duplicate_calcs_faqs_raw_python_and_legacy_clutter(tenant_id: str) -> None:
    """
    Real dist/ HTML across all 4 estates must contain zero duplicate calculators, zero duplicate FAQs,
    zero raw Python round(( formulas, and zero legacy ymyl-disclaimer-banner/ftc-disclosure-card clutter.
    """
    dist_dir = _require_tenant_dist(tenant_id)
    css_text = (dist_dir / "css" / "style.css").read_text(encoding="utf-8", errors="ignore")
    issues = _audit_html_hygiene_issues(dist_dir, css_text)
    assert not issues, f"[{tenant_id}] HTML hygiene failures ({len(issues)}): {issues[:15]}"


@pytest.mark.host_estate
def test_no_wrong_jurisdiction_state_first_hero_bar_on_non_state_tools() -> None:
    """
    Federal, international, and non-state tools must NOT inject or retain US-state #state-first-hero-bar.
    Checks both central normalize_html_visual_primitives and real dist/ HTML on disk.
    """
    failures: List[str] = []

    for domain, slug in (
        ("gainhelm.com", "soc-2-audit-cost-calculator"),
        ("gainhelm.com", "eu-ai-act-high-risk-conformity-assessment-cost-calculator"),
        ("prexvo.com", "student-loans-gov"),
        ("lienbond.com", "surety-bond-cost-calculator-philippines"),
    ):
        sample_html = (
            f"<!DOCTYPE html><html><head><link rel='canonical' href='https://{domain}/tools/{slug}/'></head><body><main>"
            "<section class='hero-section tool-hero card'><h1>Sample Federal/Global Tool</h1></section>"
            "<div id='state-first-hero-bar' class='state-first-hero-bar'>State Bar</div>"
            "<form id='partner-quote-intake-form'><select id='quote-intake-state'></select></form>"
            "<div id='saveable-decision-blueprint'></div>"
            "<strong class='output-value'>$12,500</strong>"
            "</main></body></html>"
        )
        out, _ = normalize_html_visual_primitives(sample_html, is_tenant_porcelain=True)
        if 'id="state-first-hero-bar"' in out or 'id="partner-quote-intake-form"' in out:
            failures.append(f"central:normalize_html_visual_primitives({slug})")

    ws_root = _resolve_workspace_root()
    if ws_root is not None:
        for tenant_id, repo_name in TENANT_REPOS.items():
            dist_dir = ws_root / repo_name / "dist"
            if not dist_dir.is_dir():
                continue
            for hp in _iter_public_html_files(dist_dir):
                rel = hp.relative_to(dist_dir).as_posix()
                if any(marker in rel for marker in NON_STATE_FEDERAL_OR_GLOBAL_TOOL_MARKERS):
                    txt = hp.read_text(encoding="utf-8", errors="ignore")
                    if 'id="state-first-hero-bar"' in txt:
                        failures.append(f"{tenant_id}/{rel}")

    assert not failures, (
        f"Wrong-jurisdiction #state-first-hero-bar injected on non-state tools ({len(failures)}): {failures[:15]}"
    )


def test_edge_headers_override_robots_txt_stale_s_maxage(tmp_path: Path) -> None:
    """
    build_edge_headers, _sync_sitemaps_headers_and_redirects, and all 4 real dist/_headers
    must explicitly configure /robots.txt so it never inherits /* stale s-maxage=86400.
    """
    failures: List[str] = []

    headers_txt = build_edge_headers("https://profithelm.com", routes=["/", "/tools/"])
    blocks = dict(_parse_headers_blocks(headers_txt))
    if "/robots.txt" not in blocks:
        failures.append("build_edge_headers missing explicit /robots.txt cache block")
    else:
        robots_cc = next((h for h in blocks["/robots.txt"] if h.lower().startswith("cache-control:")), "")
        if not robots_cc or "s-maxage=86400" in robots_cc.lower():
            failures.append(f"build_edge_headers /robots.txt Cache-Control={robots_cc!r}")

    tmp_dist = tmp_path / "dist"
    tmp_dist.mkdir(parents=True)
    (tmp_dist / "index.html").write_text("<html><body><h1>Home</h1></body></html>", encoding="utf-8")
    (tmp_dist / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
    (tmp_dist / "_headers").write_text(headers_txt, encoding="utf-8")
    _sync_sitemaps_headers_and_redirects(tmp_dist, get_porcelain_tenant_profile("profithelm"))
    synced_blocks = dict(_parse_headers_blocks((tmp_dist / "_headers").read_text(encoding="utf-8")))
    if "/robots.txt" not in synced_blocks:
        failures.append("_sync_sitemaps_headers_and_redirects missing /robots.txt rule")
    else:
        synced_cc = next((h for h in synced_blocks["/robots.txt"] if h.lower().startswith("cache-control:")), "")
        if not synced_cc or "s-maxage=86400" in synced_cc.lower():
            failures.append(f"_sync_sitemaps_headers_and_redirects /robots.txt Cache-Control={synced_cc!r}")

    ws_root = _resolve_workspace_root()
    if ws_root is not None:
        for tenant_id, repo_name in TENANT_REPOS.items():
            dist_dir = ws_root / repo_name / "dist"
            if not dist_dir.is_dir():
                continue
            h_file = dist_dir / "_headers"
            if not h_file.is_file():
                failures.append(f"[{tenant_id}] missing dist/_headers")
                continue
            t_blocks = dict(_parse_headers_blocks(h_file.read_text(encoding="utf-8", errors="ignore")))
            if "/robots.txt" not in t_blocks:
                failures.append(f"[{tenant_id}] dist/_headers missing explicit /robots.txt rule")
            else:
                t_cc = next((h for h in t_blocks["/robots.txt"] if h.lower().startswith("cache-control:")), "")
                if not t_cc or "s-maxage=86400" in t_cc.lower():
                    failures.append(f"[{tenant_id}] dist/_headers /robots.txt Cache-Control={t_cc!r}")

    assert not failures, f"/robots.txt edge cache policy failures: {failures}"


@pytest.mark.host_estate
def test_profithelm_app_js_versioned_query_string() -> None:
    """
    ProfitHelm HTML referencing /static/js/app.js must carry a ?v= version query string
    both after central normalize_html_to_porcelain_shell and across profithelm-platform/dist/**/*.html.
    """
    failures: List[str] = []

    ph_html = (
        "<!DOCTYPE html><html lang='en'><head><title>Sec 179 | ProfitHelm</title>"
        "<meta name='description' content='Section 179 equipment deduction calculator.'></head>"
        "<body><main><h1>Section 179</h1></main>"
        '<script src="/static/js/app.js" defer></script></body></html>'
    )
    norm_ph, _ = normalize_html_to_porcelain_shell(
        ph_html,
        "tools/section-179-calculator/index.html",
        get_porcelain_tenant_profile("profithelm"),
    )
    if not re.search(r"/static/js/app\.js\?v=[a-zA-Z0-9._-]+", norm_ph):
        failures.append("central normalize_html_to_porcelain_shell left /static/js/app.js unversioned")

    ws_root = _resolve_workspace_root()
    if ws_root is not None:
        ph_dist = ws_root / "profithelm-platform" / "dist"
        if ph_dist.is_dir():
            unversioned = [
                hp.relative_to(ph_dist).as_posix()
                for hp in _iter_public_html_files(ph_dist)
                if re.search(r"/static/js/app\.js(?!\?v=)", hp.read_text(encoding="utf-8", errors="ignore"))
            ]
            if unversioned:
                failures.append(
                    f"profithelm-platform/dist has {len(unversioned)} files with bare /static/js/app.js: "
                    f"{unversioned[:8]}"
                )

    assert not failures, f"ProfitHelm app.js versioning failures: {failures}"


@pytest.mark.host_estate
def test_favicon_and_og_image_assets_present_and_non_placeholder() -> None:
    """
    Central normalization and real dist/ HTML/JSON-LD must never emit placeholder href='data:,'
    favicons or reference missing /favicon.ico or missing og:image files (gainhelm-og.png, prexvo-og.png).
    """
    failures: List[str] = []

    raw_data_fav = (
        "<!DOCTYPE html><html lang='en'><head><title>GainHelm</title>"
        '<meta name="description" content="Enterprise compliance cost calculator.">'
        '<link rel="icon" href="data:,">'
        '<meta property="og:image" content="https://gainhelm.com/static/img/gainhelm-og.png">'
        "</head><body><main><h1>GainHelm</h1></main></body></html>"
    )
    norm_gh, _ = normalize_html_to_porcelain_shell(
        raw_data_fav,
        "index.html",
        get_porcelain_tenant_profile("gainhelm"),
    )
    if 'href="data:,"' in norm_gh:
        failures.append("central normalize_html_to_porcelain_shell preserved placeholder href='data:,'")

    ws_root = _resolve_workspace_root()
    if ws_root is not None:
        for tenant_id, repo_name in TENANT_REPOS.items():
            dist_dir = ws_root / repo_name / "dist"
            if not dist_dir.is_dir():
                continue
            domain = TENANT_DOMAINS[tenant_id]
            for hp in _iter_public_html_files(dist_dir):
                rel = hp.relative_to(dist_dir).as_posix()
                txt = hp.read_text(encoding="utf-8", errors="ignore")

                if re.search(
                    r'<link\b[^>]*rel=["\'][^"\']*icon[^"\']*["\'][^>]*href=["\']data:,["\']',
                    txt,
                    flags=re.IGNORECASE,
                ):
                    failures.append(f"{tenant_id}/{rel}: placeholder href='data:,' favicon")

                for og_url in re.findall(
                    r'<meta\b[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']',
                    txt,
                    flags=re.IGNORECASE,
                ):
                    target = _resolve_url_to_dist(dist_dir, domain, og_url)
                    if target is not None and not target.is_file():
                        failures.append(f"{tenant_id}/{rel}: missing og:image {og_url}")

                for fav_url in re.findall(
                    r'<link\b[^>]*rel=["\'][^"\']*icon[^"\']*["\'][^>]*href=["\']([^"\']+)["\']',
                    txt,
                    flags=re.IGNORECASE,
                ):
                    if fav_url.startswith("data:"):
                        continue
                    target = _resolve_url_to_dist(dist_dir, domain, fav_url)
                    if target is not None and not target.is_file():
                        failures.append(f"{tenant_id}/{rel}: missing favicon {fav_url}")

                for jtxt in re.findall(
                    r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>',
                    txt,
                    flags=re.IGNORECASE,
                ):
                    for img_u in re.findall(r'"(?:logo|image)"\s*:\s*"([^"]+)"', jtxt):
                        target = _resolve_url_to_dist(dist_dir, domain, img_u)
                        if target is not None and not target.is_file():
                            failures.append(f"{tenant_id}/{rel}: missing JSON-LD image/logo {img_u}")

    assert not failures, f"Favicon/OG image asset failures ({len(failures)}): {failures[:15]}"


@pytest.mark.host_estate
def test_ai_benchmarks_json_zero_404_urls() -> None:
    """
    Every tenant-domain URL inside dist/ai-benchmarks/*.json and central distributor
    citation/reclamation generators must resolve to an existing file/route in dist/.
    """
    ws_root = _resolve_workspace_root()
    if ws_root is None:
        pytest.skip("Sibling tenant checkouts missing in standalone CI for dist/ai-benchmarks route resolution")

    broken_ai_urls: List[str] = []
    for tenant_id, repo_name in TENANT_REPOS.items():
        dist_dir = ws_root / repo_name / "dist"
        if not dist_dir.is_dir():
            continue
        domain = TENANT_DOMAINS[tenant_id]

        ai_dir = dist_dir / "ai-benchmarks"
        if ai_dir.is_dir():
            for jf in sorted(ai_dir.glob("*.json")):
                jraw = jf.read_text(encoding="utf-8", errors="ignore")
                for url in re.findall(rf"https?://{re.escape(domain)}[a-zA-Z0-9._~:/?#\[\]@!$&'+,;=%-]*", jraw):
                    target = _resolve_url_to_dist(dist_dir, domain, url)
                    if target is not None and not target.is_file():
                        broken_ai_urls.append(f"{tenant_id}/ai-benchmarks/{jf.name}: 404 URL {url}")

        if tenant_id in ("profithelm", "prexvo", "gainhelm"):
            hub_payload = compile_public_benchmark_citation_hubs(tenant_id)
            recl_payload = compile_broken_calculator_link_reclamation_briefs(tenant_id)
            gen_blob = json.dumps({"hub": hub_payload, "recl": recl_payload})
            for url in re.findall(rf"https?://{re.escape(domain)}[a-zA-Z0-9._~:/?#\[\]@!$&'+,;=%-]*", gen_blob):
                target = _resolve_url_to_dist(dist_dir, domain, url)
                if target is not None and not target.is_file():
                    broken_ai_urls.append(f"distributor({tenant_id}): 404 URL {url}")

    assert not broken_ai_urls, f"Broken ai-benchmarks 404 URLs ({len(broken_ai_urls)}): {broken_ai_urls[:15]}"


def _load_cli_module(cli_path: Path, mod_name: str):
    spec = importlib.util.spec_from_file_location(mod_name, str(cli_path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.xdist_group("lienbond_compiled")
def test_lienbond_cli_inspects_drifted_assets_count_not_drifted(
    compiled_lienbond_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    Compiled lienbond/cli.py (and workspace lienbond/cli.py if present) must inspect
    report.drifted_assets_count (never nonexistent report.drifted) and fail closed on drift.
    """
    drifted_report = AssetIntegrityReport(
        property_id="lienbond",
        total_assets_checked=10,
        compliant_assets_count=7,
        drifted_assets_count=3,
        drifted_assets=[
            AssetDriftRecord(
                asset_path="dist/index.html",
                reasons=[DriftReason.STRUCTURAL_CONTRACT_VIOLATION],
                details=["Real drift item"],
            )
        ],
        status="DRIFT",
    )
    monkeypatch.setattr(AssetIntegrityEvaluator, "audit_all", lambda self, adapter, **kw: drifted_report)

    cli_paths = [compiled_lienbond_root / "lienbond" / "cli.py"]
    ws_root = _resolve_workspace_root()
    if ws_root is not None:
        ws_cli = ws_root / "lienbond" / "lienbond" / "cli.py"
        if ws_cli.is_file():
            cli_paths.append(ws_cli)

    failures: List[str] = []
    for idx, cli_p in enumerate(cli_paths):
        assert cli_p.is_file(), f"Missing {cli_p}"
        cli_mod = _load_cli_module(cli_p, f"_lienbond_cli_gate_{idx}")
        rc = cli_mod.main(["audit", "--envelope"])
        out_txt = capsys.readouterr().out.strip().splitlines()[-1]
        env_obj = json.loads(out_txt)
        if rc != 1 or env_obj.get("status") != "FAIL":
            failures.append(f"{cli_p} returned rc={rc} status={env_obj.get('status')!r} on drifted_assets_count=3")

    assert not failures, "; ".join(failures)


@pytest.mark.host_estate
def test_pseofactory_cli_pipeline_audit_does_not_silently_cap_to_8(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    pseofactory.cli.cmd_audit in pipeline mode (PSEUFACTORY_SUPERVISOR_LOCK_HELD=1) without
    --sample must NOT silently cap ProfitHelm browser audit to 8 routes.
    """
    sample_sizes_seen: List[Optional[int]] = []

    def _spy_run_audit(self: UnifiedBrowserAuditor, sample_size: Optional[int] = None) -> Dict[str, Any]:
        sample_sizes_seen.append(sample_size)
        fake_routes = ["/"] + [f"/tools/tool-{i}/" for i in range(1, 29)]
        selected = RouteManifestExtractor(self.dist_dir).select_smart_routes(fake_routes, sample_size=sample_size)
        return {
            "status": "PASS",
            "total_routes": len(fake_routes),
            "routes_audited": len(selected),
            "failed_count": 0,
            "selected_routes": selected,
        }

    monkeypatch.setenv("PSEUFACTORY_SUPERVISOR_LOCK_HELD", "1")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("PSEOFACTORY_SKIP_DEFAULT_BROWSER_AUDIT", raising=False)
    monkeypatch.setattr(UnifiedBrowserAuditor, "run_audit", _spy_run_audit)

    class _PassReport:
        property_id = "profithelm"
        total_assets_checked = 30
        compliant_assets_count = 30
        drifted_assets_count = 0
        drifted_assets: List[Any] = []
        status = "PASS"

        def to_dict(self) -> Dict[str, Any]:
            return {
                "property_id": self.property_id,
                "total_assets_checked": self.total_assets_checked,
                "compliant_assets_count": self.compliant_assets_count,
                "drifted_assets_count": self.drifted_assets_count,
                "status": self.status,
            }

    monkeypatch.setattr(pseo_cli, "audit_property_assets", lambda **kw: _PassReport())
    monkeypatch.setattr(pseo_cli, "_run_seo_fix_checklist_gate", lambda prop_id, as_json: True)

    args = argparse.Namespace(
        property="profithelm",
        dist_dir=None,
        browser=False,
        no_browser=False,
        sample=None,
        cdp_port=9222,
        fail_closed=False,
        check_engine_drift=False,
        department_handoffs=False,
        json=True,
    )
    audit_rc = pseo_cli.cmd_audit(args)
    capsys.readouterr()
    assert audit_rc == 0
    assert sample_sizes_seen, "cmd_audit did not invoke UnifiedBrowserAuditor.run_audit"
    eff_sample = sample_sizes_seen[0]
    assert eff_sample is None or eff_sample <= 0 or eff_sample >= 30, (
        f"pseofactory.cli.cmd_audit silently capped ProfitHelm pipeline browser audit to "
        f"sample_size={eff_sample}, skipping non-sample pages"
    )
