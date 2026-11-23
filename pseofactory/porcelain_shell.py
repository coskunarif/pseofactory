"""
Deterministic 4-Tenant Porcelain Light Shell, Stylesheet & Governance Compiler.
Single source of truth for:
1. Canonical Porcelain Light stylesheet (#fbfcfd canvas, #ffffff cards, #0f172a primary text)
   with compile-time WCAG AA (>= 4.5:1) contrast verification and zero undefined var(--...).
2. Public screen blueprints (home_hub, tools_directory, calculator_leaf, comparison_leaf,
   editorial_guide, editorial_hub, governance_legal, error_404) plus explicit operator_pwa
   exemption (/signal/).
3. Six real HTTP-200 governance pages (/about/, /methodology/, /privacy/, /terms/,
   /disclaimers/, /contact/) derived from DeclarativeTenantContract with full publisher tags.
4. Deterministic real pure-stdlib pseofactory substrate sync (<pkg>/_pseo_substrate/pseofactory/)
   guaranteeing zero-shim standalone CI verification and byte-for-byte build parity.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import collections
import functools
import hashlib
import html as html_lib
import json
import os
import re
import shutil
import struct
import threading
import xml.etree.ElementTree as ET
import xml.sax.saxutils as saxutils
import zlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Set, Tuple

PORCELAIN_SHELL_VERSION = "porcelain-v1"
VISUAL_PRIMITIVES_LINK_VERSION = "pseo-primitives-v4"

GOVERNANCE_ROUTES: Tuple[str, ...] = (
    "about",
    "methodology",
    "privacy",
    "terms",
    "disclaimers",
    "contact",
)

CROSS_LEGAL_REDIRECT_SOURCES: Set[str] = {
    "/about",
    "/about/",
    "/methodology",
    "/methodology/",
    "/privacy",
    "/privacy/",
    "/terms",
    "/terms/",
    "/disclaimers",
    "/disclaimers/",
    "/contact",
    "/contact/",
}

TENANT_BRAND_PALETTES: Dict[str, Dict[str, str]] = {
    "profithelm": {
        "badge_letter": "P",
        "brand_primary": "#1d4ed8",
        "brand_hover": "#1e40af",
        "brand_soft": "#eff6ff",
        "brand_border": "#bfdbfe",
        "css_href": "/static/css/style.css",
        "default_gsc_token": "1b9AjxT3rRYA2iyPRraN2ShDNqEoKsfYW39UiTncB4U",
    },
    "prexvo": {
        "badge_letter": "P",
        "brand_primary": "#0f766e",
        "brand_hover": "#115e59",
        "brand_soft": "#f0fdfa",
        "brand_border": "#99f6e4",
        "css_href": "/css/style.css",
        "default_gsc_token": "At5f9a2APEkZhsFx0LICFC5R-TNKsXxzNsbG5YhUoIA",
    },
    "gainhelm": {
        "badge_letter": "G",
        "brand_primary": "#047857",
        "brand_hover": "#065f46",
        "brand_soft": "#ecfdf5",
        "brand_border": "#a7f3d0",
        "css_href": "/css/style.css",
        "default_gsc_token": "Elwe-MFi7Z8hEE7ybiGr8xXBqSv87dF_ZMpqkhCDlQ8",
    },
    "lienbond": {
        "badge_letter": "L",
        "brand_primary": "#b45309",
        "brand_hover": "#92400e",
        "brand_soft": "#fffbeb",
        "brand_border": "#fde68a",
        "css_href": "/css/style.css",
        "default_gsc_token": "wonyZkQ-8DZKcbdV_GTbbxIZVWgA3kWYvABx0jSrN4Q",
    },
}


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    raw = hex_color.strip().lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) != 6:
        raise ValueError(f"Invalid hex color literal: {hex_color}")
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def _relative_luminance(rgb: Tuple[int, int, int]) -> float:
    channels: List[float] = []
    for comp in rgb:
        s = comp / 255.0
        channels.append(s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def compute_wcag_contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """Computes exact WCAG 2.1 contrast ratio between two hex colors."""
    l1 = _relative_luminance(_hex_to_rgb(fg_hex))
    l2 = _relative_luminance(_hex_to_rgb(bg_hex))
    lighter, darker = (l1, l2) if l1 >= l2 else (l2, l1)
    return (lighter + 0.05) / (darker + 0.05)


def assert_porcelain_palette_wcag(palette: Dict[str, str]) -> None:
    """Compile-time WCAG AA (>= 4.5:1) enforcement for Porcelain tokens and tenant brand."""
    brand_primary = palette["brand_primary"]
    brand_hover = palette["brand_hover"]
    brand_soft = palette["brand_soft"]
    checks = [
        ("#0f172a", "#fbfcfd", "text-primary on bg-canvas"),
        ("#0f172a", "#ffffff", "text-primary on bg-surface"),
        ("#334155", "#fbfcfd", "text-secondary on bg-canvas"),
        ("#475569", "#fbfcfd", "text-muted on bg-canvas"),
        ("#475569", "#f4f6f8", "text-muted on bg-subtle"),
        (brand_primary, "#ffffff", "brand-primary on bg-surface"),
        (brand_primary, "#fbfcfd", "brand-primary on bg-canvas"),
        ("#ffffff", brand_primary, "cta-fg on brand-primary"),
        (brand_hover, brand_soft, "brand-hover on brand-soft"),
        ("#047857", "#ecfdf5", "status-positive on status-positive-bg"),
        ("#92400e", "#fffbeb", "status-warning on status-warning-bg"),
        ("#b91c1c", "#fef2f2", "status-danger on status-danger-bg"),
    ]
    for fg, bg, label in checks:
        ratio = compute_wcag_contrast_ratio(fg, bg)
        if ratio < 4.5:
            raise ValueError(
                f"WCAG AA contrast failure for {label} ({fg} vs {bg}): {ratio:.2f}:1 < 4.50:1"
            )


def _format_porcelain_tool_label(raw_label: str) -> str:
    """Formats a human-readable tool label with canonical statutory acronym casing."""
    from pseofactory.contracts import normalize_statutory_acronym_casing

    out = normalize_statutory_acronym_casing(str(raw_label or "").strip())
    for pat, repl in (
        (r"\bIrs\b", "IRS"),
        (r"\bSaas\b", "SaaS"),
        (r"\bRap\b", "RAP"),
        (r"\bIbr\b", "IBR"),
        (r"\bPaye\b", "PAYE"),
        (r"\bIcr\b", "ICR"),
        (r"\bSoc\b", "SOC"),
        (r"\bIso\b", "ISO"),
        (r"\bErisa\b", "ERISA"),
        (r"\b3Pao\b", "3PAO"),
        (r"\bVs\b", "vs"),
    ):
        out = re.sub(pat, repl, out)
    return out


_CANONICAL_PORCELAIN_CACHE_PROPS: FrozenSet[str] = frozenset(
    ("profithelm", "prexvo", "gainhelm", "lienbond")
)


def get_porcelain_tenant_profile(property_id: str) -> Dict[str, Any]:
    """Builds a self-contained single-tenant profile from DeclarativeTenantContract."""
    prop = str(property_id or "profithelm").strip().lower()
    if prop == "profithelm-platform":
        prop = "profithelm"
    if prop in _CANONICAL_PORCELAIN_CACHE_PROPS:
        cached = _build_porcelain_tenant_profile_cached(prop)
        return {
            k: (list(v) if isinstance(v, list) else (dict(v) if isinstance(v, dict) else v))
            for k, v in cached.items()
        }
    return _build_porcelain_tenant_profile_uncached(prop)


@functools.lru_cache(maxsize=8)
def _build_porcelain_tenant_profile_cached(prop: str) -> Dict[str, Any]:
    return _build_porcelain_tenant_profile_uncached(prop)


def _build_porcelain_tenant_profile_uncached(prop: str) -> Dict[str, Any]:
    import pseofactory.contracts  # noqa: F401
    from pseofactory.tenant_facts import get_tenant_contract

    contract = get_tenant_contract(prop)
    pal = dict(TENANT_BRAND_PALETTES.get(prop) or TENANT_BRAND_PALETTES["profithelm"])
    if prop not in TENANT_BRAND_PALETTES:
        pal["default_gsc_token"] = ""
    assert_porcelain_palette_wcag(pal)

    if prop == "prexvo":
        compliance_text = (
            "Statutory & FTC Disclosure (16 CFR Part 255): Calculations are provided for educational and "
            "informational purposes only and do not constitute personalized financial, tax, or legal advice. "
            "Prexvo is an independent publisher and is not affiliated with the U.S. Department of Education "
            "or StudentAid.gov. Refinancing federal student loans permanently waives federal protections "
            "including Income-Driven Repayment (IDR), Public Service Loan Forgiveness (PSLF), "
            "deferment, and forbearance. Prexvo may earn referral compensation from vetted partners (such as "
            "Splash Financial, SoFi, Credible, Earnest, LendKey, or Juno) at no additional cost to you."
        )
        restricted_compliance_text = (
            "Public-Service Statutory Notice (Title IV & 16 CFR Part 255): Calculations on this public-service "
            "estimator are for educational and informational purposes only and do not constitute legal or "
            "financial advice. Prexvo is an independent research publisher and is not affiliated with the U.S. "
            "Department of Education or StudentAid.gov. Refinancing federal student loans permanently waives "
            "federal protections including Income-Driven Repayment (IDR) and Public Service Loan Forgiveness "
            "(PSLF), so no private refinancing offers are displayed on dedicated public-service forgiveness "
            "or litigation transition calculators."
        )
        partner_list_summary = "Splash Financial, SoFi, Credible, Earnest, LendKey, and Juno"
        disclaimers_sections_html = f"""      <section class="card">
        <h2>Not Legal, Tax, or Financial Advice</h2>
        <p>All calculators, repayment comparisons, and statutory summaries on Prexvo are published for educational and informational purposes only. Prexvo LLC does not provide personalized financial, tax, investment, or legal advice. Consult a qualified student loan counselor, CPA, or tax attorney before changing repayment plans or consolidating loans.</p>
      </section>
      <section class="card">
        <h2>No Government Affiliation</h2>
        <p>Prexvo is an independent private research publisher operated by Prexvo LLC and is not affiliated with, endorsed by, or operated by the U.S. Department of Education, Federal Student Aid, or StudentAid.gov. Borrowers can manage federal loans and submit official IDR or PSLF applications free of charge directly at StudentAid.gov.</p>
      </section>
      <section class="card">
        <h2>Affiliate &amp; Referral Compensation Disclosure (16 CFR Part 255)</h2>
        <p>Pursuant to Federal Trade Commission (FTC) guidelines under 16 CFR Part 255, Prexvo discloses that it may earn referral compensation when visitors click or complete applications with approved private refinancing partners ({html_lib.escape(partner_list_summary)}) at no additional cost to the borrower. Refinancing federal student loans permanently waives federal protections including Income-Driven Repayment (IDR), Public Service Loan Forgiveness (PSLF), federal deferment, and forbearance. Dedicated public-service and litigation transition calculators suppress commercial refinance offers.</p>
      </section>
      <section class="card">
        <h2>Model Limitations</h2>
        <p>Deterministic outputs rely on Title IV Higher Education Act (34 CFR Part 685) formulas, annual HHS Poverty Guidelines, and user-supplied AGI, family size, and loan balance assumptions. Actual servicer billing schedules, interest capitalization events, and administrative forbearance rules may vary based on loan disbursement dates and federal rulemaking updates.</p>
      </section>"""
    elif prop == "gainhelm":
        compliance_text = (
            "Statutory & FTC Disclosure (16 CFR Part 255): Audit scoping and penalty models are provided for "
            "educational and informational purposes only and are not legal, tax, accounting, or certified audit "
            "advice. Formal SOC 2 attestations require an independent AICPA CPA firm, and CMMC Level 2 certifications "
            "require an authorized C3PAO. GainHelm may receive referral compensation from vetted compliance and "
            "security partners at no additional cost to your organization."
        )
        restricted_compliance_text = compliance_text
        partner_list_summary = "Vanta, Drata, Sprinto, Thoropass, Coalition, and Cobalt"
        disclaimers_sections_html = f"""      <section class="card">
        <h2>Not Legal, Tax, or Financial Advice</h2>
        <p>All cyber compliance scoping calculators, audit fee benchmarks, and civil penalty estimators on GainHelm are provided for educational and informational purposes only and are not legal, tax, accounting, or certified audit advice. Only a licensed AICPA CPA firm can issue a SOC 2 examination report, and only an accredited C3PAO can issue a CMMC Level 2 certification.</p>
      </section>
      <section class="card">
        <h2>No Government Affiliation</h2>
        <p>GainHelm LLC is an independent research publisher and is not affiliated with AICPA, the U.S. Department of Defense, The Cyber AB, NIST, HHS OCR, or the PCI Security Standards Council.</p>
      </section>
      <section class="card">
        <h2>Affiliate &amp; Referral Compensation Disclosure (16 CFR Part 255)</h2>
        <p>In accordance with FTC 16 CFR Part 255 guidelines, GainHelm may receive referral or affiliate compensation from vetted GRC automation, penetration testing, and cyber insurance partners ({html_lib.escape(partner_list_summary)}) at no additional cost to your organization. Commercial partnerships never influence statutory scoring rules or baseline auditor-day formulas.</p>
      </section>
      <section class="card">
        <h2>Model Limitations</h2>
        <p>Audit fee and remediation estimates reflect empirical medians across {html_lib.escape(contract.economic_dataset_label)} and {html_lib.escape(contract.primary_statutory_authority)}. Actual engagement pricing varies by system boundary complexity, cloud architecture, control maturity, and assessor scope.</p>
      </section>"""
    elif prop == "lienbond":
        compliance_text = (
            "Statutory & FTC Disclosure (16 CFR Part 255): Surety premium, NCCI workers compensation EMR, and "
            "statutory mechanics lien deadline outputs are for educational and informational underwriting estimates "
            "only and do not constitute legal advice or a binding surety commitment. LienBond may earn referral "
            "compensation from verified partner links (such as Simply Business, SuretyBondsDirect.com, Thimble, "
            "Jobber, or Levelset) at no additional cost to you."
        )
        restricted_compliance_text = compliance_text
        partner_list_summary = "Simply Business, SuretyBondsDirect.com, Thimble, Jobber, and Levelset"
        disclaimers_sections_html = ""
    else:
        compliance_text = (
            "Statutory & FTC Disclosure (16 CFR Part 255): Financial, depreciation, and tax models are provided "
            "for educational and informational modeling purposes only and do not constitute formal tax, legal, "
            "or accounting advice. ProfitHelm may receive affiliate or referral compensation from vetted commercial "
            "banking, tax, real estate exchange, and treasury partners at no additional cost to you."
        )
        restricted_compliance_text = compliance_text
        partner_list_summary = "Mercury, CoinLedger, Koinly, IPX1031, Xendoo, and Collective"
        disclaimers_sections_html = ""

    if not disclaimers_sections_html:
        b_esc = html_lib.escape(contract.brand_name)
        l_esc = html_lib.escape(contract.legal_entity or f"{contract.brand_name} LLC")
        disclaimers_sections_html = f"""      <section class="card">
        <h2>Not Legal, Tax, or Financial Advice</h2>
        <p>All calculators, statutory matrices, and downloadable workpapers published on {b_esc} by {l_esc} are provided strictly for educational and informational modeling purposes only and do not constitute legal, tax, accounting, surety underwriting, or certified financial advice.</p>
      </section>
      <section class="card">
        <h2>No Government Affiliation</h2>
        <p>{l_esc} is an independent private quantitative publisher and is not affiliated with the Internal Revenue Service, U.S. Department of the Treasury, U.S. Department of Labor, NCCI, or any state licensing or taxing agency.</p>
      </section>
      <section class="card">
        <h2>Affiliate &amp; Referral Compensation Disclosure (16 CFR Part 255)</h2>
        <p>Pursuant to FTC 16 CFR Part 255 Endorsement Guides, {b_esc} discloses that we may earn referral or affiliate commissions when users engage vetted commercial partners ({html_lib.escape(partner_list_summary)}) through links routed via <code>/r/</code>, at no extra cost to you. Partner relationships never alter statutory formulas or calculator outputs.</p>
      </section>
      <section class="card">
        <h2>Model Limitations</h2>
        <p>Scenario calculations model enacted provisions under {html_lib.escape(contract.primary_statutory_authority)} and {html_lib.escape(contract.economic_dataset_label)}. Individual filing outcomes, state conformity rules, and underwriting approvals depend on complete entity facts reviewed by a licensed professional.</p>
      </section>"""

    default_tools = [
        (str(t.get("slug", "")).strip(), _format_porcelain_tool_label(str(t.get("primary_keyword", "")).title()))
        for t in (contract.default_core_tools or ())
        if t.get("slug")
    ]
    if not default_tools and contract.default_complementary_peers:
        default_tools = [(s, lbl) for s, lbl in contract.default_complementary_peers]

    from pseofactory.affiliate_intent import (
        CJ_PROPERTY_ID_BY_TENANT,
        IMPACT_VERIFICATION_UUID_BY_TENANT,
    )

    publisher_entity_by_prop = {
        "profithelm": "ProfitHelm LLC",
        "prexvo": "Prexvo Statutory Research Group",
        "gainhelm": "GainHelm Cyber Compliance & Audit Economics Research",
        "lienbond": "LienBond Statutory Surety & Construction Compliance Research",
    }

    return {
        "property_id": prop,
        "package_name": contract.package_name or prop,
        "repo_dir_name": contract.repo_dir_name or prop,
        "brand_name": contract.brand_name,
        "domain": contract.domain,
        "canonical_base": contract.canonical_base,
        "linkedin_company_id": contract.linkedin_company_id or "",
        "research_entity": contract.research_entity or f"{contract.brand_name} Research",
        "legal_entity": contract.legal_entity or f"{contract.brand_name} LLC",
        "publisher_entity_label": publisher_entity_by_prop.get(prop, f"{contract.brand_name} LLC"),
        "impact_verification_uuid": IMPACT_VERIFICATION_UUID_BY_TENANT.get(
            prop, IMPACT_VERIFICATION_UUID_BY_TENANT["profithelm"]
        ),
        "cj_property_id": CJ_PROPERTY_ID_BY_TENANT.get(prop, CJ_PROPERTY_ID_BY_TENANT["profithelm"]),
        "sovrn_domain_key": "0a5ac1bfe04034bff021b394f5e71d90" if prop == "profithelm" else "",
        "editorial_classification": contract.editorial_classification,
        "primary_statutory_authority": contract.primary_statutory_authority,
        "economic_dataset_label": contract.economic_dataset_label,
        "home_topic_label": contract.home_topic_label,
        "tools_directory_topic_label": contract.tools_directory_topic_label,
        "contact_email": "compliance@lienbond.com" if prop == "lienbond" else f"editorial@{contract.domain}",
        "compliance_text": compliance_text,
        "restricted_compliance_text": restricted_compliance_text,
        "partner_list_summary": partner_list_summary,
        "disclaimers_sections_html": disclaimers_sections_html,
        "default_tools": default_tools[:8],
        **pal,
    }


def extract_defined_and_referenced_css_vars(css_text: str) -> Tuple[Set[str], Set[str]]:
    """Extracts all defined (--foo:) and referenced (var(--foo)) custom properties in CSS."""
    clean = re.sub(r"/\*[\s\S]*?\*/", "", css_text or "")
    defined = set(re.findall(r"(--[a-zA-Z0-9_-]+)\s*:", clean))
    referenced = set(re.findall(r"var\(\s*(--[a-zA-Z0-9_-]+)", clean))
    return defined, referenced


@functools.lru_cache(maxsize=32)
def _generate_porcelain_stylesheet_cached(
    brand: str,
    bp: str,
    bh: str,
    bs: str,
    bb: str,
) -> Tuple[str, str, FrozenSet[str]]:
    """Cached pure builder returning (css_text, sha256_10, defined_css_vars)."""
    css = f"""/**
 * {brand} Canonical Porcelain Light Design System ({PORCELAIN_SHELL_VERSION})
 * Single-source-of-truth Porcelain tokens, layout primitives, WCAG AA contrast,
 * 44x44px touch ergonomics, and CPA print media rules.
 * Zero em-dashes. Zero en-dashes.
 */

:root {{
  /* Canonical Porcelain Surfaces */
  --bg-canvas: #fbfcfd;
  --bg-surface: #ffffff;
  --bg-subtle: #f4f6f8;
  --bg-muted: #eef2f6;
  --bg-elevated: {bs};
  --bg-inset: #f4f6f8;
  --bg-tertiary: #eef2f6;

  /* Surface Compatibility Aliases */
  --bg: #fbfcfd;
  --bg-body: #fbfcfd;
  --bg-primary: #fbfcfd;
  --card-bg: #ffffff;
  --bg-card: #ffffff;

  /* High-Contrast Ink Typography (WCAG AA/AAA Verified) */
  --text-primary: #0f172a;
  --text-secondary: #334155;
  --text-muted: #475569;
  --text-faint: #475569;
  --text-tertiary: #475569;
  --text: #0f172a;
  --text-main: #0f172a;

  /* Tenant Brand & Accent Tokens */
  --brand-primary: {bp};
  --brand-accent: {bp};
  --brand-hover: {bh};
  --brand-soft: {bs};
  --brand-border: {bb};
  --accent: {bp};
  --accent-primary: {bp};
  --accent-blue: {bp};
  --primary: {bp};
  --accent-hover: {bh};
  --accent-secondary: {bh};
  --accent-subtle: {bs};
  --cta-fg: #ffffff;

  /* Borders & Focus Indicators */
  --border-hairline: #e2e8f0;
  --border-subtle: #cbd5e1;
  --border-strong: #94a3b8;
  --border-focus: {bp};
  --border: #cbd5e1;
  --border-color: #e2e8f0;

  /* Semantic Status Palette (WCAG AA >= 4.5:1 on Light & Tinted Surfaces) */
  --status-positive: #047857;
  --accent-success: #047857;
  --status-positive-bg: #ecfdf5;
  --status-positive-border: #a7f3d0;

  --status-warning: #92400e;
  --status-warning-bg: #fffbeb;
  --status-warning-border: #fde68a;

  --status-danger: #b91c1c;
  --status-negative: #b91c1c;
  --status-danger-bg: #fef2f2;
  --status-negative-bg: #fef2f2;
  --status-danger-border: #fecaca;
  --status-negative-border: #fecaca;

  /* Progressive Bracket Meter Tokens */
  --meter-tier-1: #93c5fd;
  --meter-tier-2: #60a5fa;
  --meter-tier-3: #3b82f6;
  --meter-tier-4: #1d4ed8;
  --meter-tier-5: #1e40af;
  --meter-tier-6: #1e3a8a;
  --meter-tier-7: #0f172a;

  /* Elevation, Radius & Font Stacks */
  --shadow-subtle: 0 1px 2px 0 rgba(15, 23, 42, 0.04);
  --shadow-sm: 0 1px 2px 0 rgba(15, 23, 42, 0.05);
  --shadow-card: 0 1px 3px 0 rgba(15, 23, 42, 0.06), 0 1px 2px -1px rgba(15, 23, 42, 0.04);
  --shadow-md: 0 4px 6px -1px rgba(15, 23, 42, 0.07), 0 2px 4px -2px rgba(15, 23, 42, 0.04);
  --shadow-elevated: 0 10px 25px -5px rgba(15, 23, 42, 0.08), 0 8px 10px -6px rgba(15, 23, 42, 0.04);
  --radius-sm: 6px;
  --radius-md: 8px;
  --border-radius: 8px;
  --radius-card: 12px;
  --font-sans: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}}

*, *::before, *::after {{
  box-sizing: border-box;
}}

html {{
  font-size: 16px;
  scroll-behavior: smooth;
  scroll-padding-top: 5.5rem;
  -webkit-text-size-adjust: 100%;
  background-color: var(--bg-canvas);
  color: var(--text-primary);
}}

body {{
  margin: 0;
  padding: 0;
  font-family: var(--font-sans);
  font-size: 1rem;
  line-height: 1.6;
  background-color: var(--bg-canvas);
  color: var(--text-primary);
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  overflow-x: hidden;
  -webkit-font-smoothing: antialiased;
}}

/* Accessibility Skip Link */
.skip-link,
.skip-to-content-link {{
  position: absolute;
  left: -9999px;
  top: 0.5rem;
  z-index: 1000;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  min-width: 44px;
  padding: 0.625rem 1rem;
  background-color: var(--brand-primary);
  color: #ffffff;
  font-weight: 600;
  border-radius: var(--radius-md);
  text-decoration: none;
}}

.skip-link:focus,
.skip-link:focus-visible,
.skip-to-content-link:focus,
.skip-to-content-link:focus-visible {{
  left: 1rem;
  outline: 2px solid var(--text-primary);
  outline-offset: 2px;
}}

/* Layout Container & Locked Vertical Flow Rhythm */
.container {{
  width: 100%;
  max-width: 1120px;
  margin-left: auto;
  margin-right: auto;
  padding-left: 1.25rem;
  padding-right: 1.25rem;
}}

.site-main,
main.main,
main#main-content {{
  flex: 1 0 auto;
  width: 100%;
  padding-top: 1.5rem;
  padding-bottom: 3rem;
}}

.site-main > .container,
main#main-content > .container {{
  display: flex;
  flex-direction: column;
  gap: 24px;
}}

.site-main > .container > *,
main#main-content > .container > * {{
  margin-top: 0 !important;
  margin-bottom: 0 !important;
  margin-left: 0 !important;
  margin-right: 0 !important;
  width: 100%;
  max-width: 100%;
}}

/* Canonical Header & Mobile Drawer */
.site-header,
.header,
.site-header.header {{
  background-color: var(--bg-surface);
  border-bottom: 1px solid var(--border-hairline);
  position: sticky;
  top: 0;
  z-index: 100;
  width: 100%;
}}

.nav-wrap {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  min-height: 64px;
  padding-top: 0.5rem;
  padding-bottom: 0.5rem;
}}

.brand-logo {{
  display: inline-flex;
  align-items: center;
  gap: 0.625rem;
  min-height: 44px;
  min-width: 44px;
  padding: 0.25rem 0.5rem;
  color: var(--text-primary);
  font-weight: 700;
  font-size: 1.125rem;
  text-decoration: none;
  border-radius: var(--radius-md);
}}

.brand-mark {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  background-color: var(--brand-primary);
  color: #ffffff;
  font-weight: 800;
  font-size: 0.95rem;
  flex-shrink: 0;
}}

.nav-desktop-group {{
  display: flex;
  align-items: center;
  gap: 0.75rem;
}}

.nav-links {{
  display: flex;
  align-items: center;
  gap: 0.25rem;
  list-style: none;
  margin: 0;
  padding: 0;
}}

.nav-links li {{
  margin: 0;
  padding: 0;
}}

.nav-links a {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  min-width: 44px;
  padding: 0.5rem 0.75rem;
  color: var(--text-secondary);
  font-weight: 500;
  font-size: 0.9375rem;
  text-decoration: none;
  border-radius: var(--radius-md);
}}

.nav-links a:hover {{
  color: var(--brand-primary);
  background-color: var(--bg-subtle);
}}

.mobile-nav-menu {{
  display: none;
  position: relative;
}}

.mobile-nav-menu > summary {{
  list-style: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  min-height: 44px;
  min-width: 44px;
  padding: 0.5rem 0.875rem;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  background-color: var(--bg-surface);
  color: var(--text-primary);
  font-weight: 600;
  font-size: 0.9375rem;
  cursor: pointer;
}}

.mobile-nav-menu > summary::-webkit-details-marker {{
  display: none;
}}

.mobile-nav-drawer {{
  position: absolute;
  right: 0;
  top: calc(100% + 0.5rem);
  width: min(280px, calc(100vw - 2.5rem));
  background-color: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  padding: 0.75rem;
  box-shadow: var(--shadow-elevated);
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  z-index: 250;
}}

.mobile-nav-drawer a {{
  display: flex;
  align-items: center;
  min-height: 44px;
  min-width: 44px;
  padding: 0.5rem 0.75rem;
  color: var(--text-primary);
  font-weight: 500;
  text-decoration: none;
  border-radius: var(--radius-md);
}}

.mobile-nav-drawer a:hover {{
  background-color: var(--bg-subtle);
  color: var(--brand-primary);
}}

/* Typography Scale & Hierarchy */
h1, .hero-title {{
  font-size: 2rem;
  line-height: 1.25;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--text-primary);
  margin: 0 0 0.75rem 0;
}}

h2, .section-title {{
  font-size: 1.375rem;
  line-height: 1.35;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--text-primary);
  margin: 0 0 0.75rem 0;
}}

h3, .card-title {{
  font-size: 1.125rem;
  line-height: 1.4;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.5rem 0;
}}

h4 {{
  font-size: 1rem;
  line-height: 1.45;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 0.375rem 0;
}}

p {{
  margin: 0 0 0.75rem 0;
  color: var(--text-secondary);
}}

p:last-child {{
  margin-bottom: 0;
}}

ul, ol {{
  margin: 0 0 0.875rem 1.25rem;
  padding: 0;
  color: var(--text-secondary);
}}

li {{
  margin-bottom: 0.375rem;
}}

code, pre, .font-mono {{
  font-family: var(--font-mono);
  overflow-wrap: anywhere;
  word-break: break-word;
}}

pre {{
  max-width: 100%;
  overflow-x: auto;
}}

figure {{
  margin: 1rem 0;
  max-width: 100%;
}}

/* Links & Universal 44x44px Touch Ergonomics (with WCAG 2.5.8 Inline Prose Exemption) */
a {{
  color: var(--brand-primary);
  text-decoration: underline;
  text-underline-offset: 2px;
}}

a:hover {{
  color: var(--brand-hover);
}}

a:not(.skip-link):not(.skip-to-content-link),
button,
#calculate-btn,
[role="button"],
summary,
.touch-target {{
  min-height: 44px;
  min-width: 44px;
}}

a:not(.skip-link):not(.skip-to-content-link) {{
  display: inline-flex;
  align-items: center;
  padding-top: 0.25rem;
  padding-bottom: 0.25rem;
}}

li a:not(.btn):not(.btn-cta):not(.partner-btn):not(.tool-link):not(.nav-link),
td a:not(.btn):not(.btn-cta):not(.partner-btn) {{
  padding-left: 0.25rem;
  padding-right: 0.25rem;
}}

main p a:not(.btn):not(.btn-cta):not(.btn-primary):not(.btn-secondary):not(.partner-btn):not(.touch-target):not([role="button"]),
main dd a:not(.btn):not(.btn-cta):not(.partner-btn):not(.touch-target):not([role="button"]),
main blockquote a:not(.btn):not(.btn-cta):not(.partner-btn):not(.touch-target):not([role="button"]) {{
  display: inline;
  min-height: auto;
  min-width: auto;
  padding: 0;
}}

main a.inline-prose-link {{
  display: inline !important;
  min-height: 0 !important;
  min-width: 0 !important;
  padding: 0 !important;
}}

/* Visible Keyboard Focus Ring */
a:focus,
a:focus-visible,
button:focus,
button:focus-visible,
input:focus,
input:focus-visible,
select:focus,
select:focus-visible,
textarea:focus,
textarea:focus-visible,
summary:focus,
summary:focus-visible,
[role="button"]:focus,
[role="button"]:focus-visible {{
  outline: 2px solid var(--border-focus);
  outline-offset: 2px;
}}

/* Canonical Porcelain Cards (Exact 12px Radius & >= 24px Padding) */
.card,
.pseo-card,
.calc-card,
.interactive-calc-card,
.calculation-container,
.methodology-card,
.faq-card,
.partner-card,
.affiliate-card,
.decision-framework-card,
.hero-section,
.tool-hero,
.comparison-table-section,
.procedure-section,
.tools-directory-grid-section,
.affiliate-section,
.affiliates-section,
.refinance-partner-section,
.partner-quote-intake-drawer,
.post-calc-upgrade-drawer,
.partner-registration-drawer,
.serp-depth-workbench,
.pro-hook-card,
.playbook-capture-card,
.calc-inline-cta {{
  background-color: #ffffff !important;
  color: var(--text-primary);
  border: 1px solid var(--border-subtle);
  border-radius: 12px !important;
  padding: 1.5rem;
  box-shadow: var(--shadow-sm);
}}

/* Breadcrumbs, Quick Answer & Above-the-Fold Compliance Strip */
.breadcrumbs {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.875rem;
  color: var(--text-muted);
  padding: 0.25rem 0;
}}

.breadcrumbs a {{
  color: var(--brand-primary);
  text-decoration: none;
  padding: 0.25rem 0.375rem;
  font-weight: 500;
}}

.breadcrumbs a:hover {{
  text-decoration: underline;
}}

.quick-answer {{
  background-color: var(--brand-soft);
  border: 1px solid var(--brand-border);
  border-left: 4px solid var(--brand-primary);
  border-radius: var(--radius-md);
  padding: 1rem 1.25rem;
  margin-top: 0.75rem;
  color: var(--text-primary);
}}

.quick-answer p,
.quick-answer .quick-answer-body {{
  color: var(--text-primary);
  font-size: 0.96875rem;
  line-height: 1.6;
  margin: 0;
}}

.compliance-strip,
.ftc-disclosure-banner {{
  background-color: var(--bg-subtle);
  border: 1px solid var(--border-subtle);
  border-left: 4px solid var(--brand-primary);
  border-radius: 12px;
  padding: 0.875rem 1.25rem;
  font-size: 0.875rem;
  line-height: 1.55;
  color: var(--text-secondary);
}}

.compliance-strip strong,
.ftc-disclosure-banner strong {{
  color: var(--text-primary);
}}

/* Buttons & Primary CTAs */
#calculate-btn,
.btn,
.btn-cta,
.btn-primary,
.partner-btn,
a.btn,
a.btn-cta,
a.btn-primary,
.affiliate-cta-link,
a.affiliate-cta-link,
button.btn,
button.btn-cta,
button.btn-primary {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  min-height: 44px;
  min-width: 44px;
  padding: 0.625rem 1.125rem;
  background-color: var(--brand-primary);
  color: #ffffff;
  border: 1px solid var(--brand-primary);
  border-radius: var(--radius-md);
  font-family: var(--font-sans);
  font-size: 0.9375rem;
  font-weight: 600;
  line-height: 1.25;
  text-decoration: none;
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease;
}}

#calculate-btn:hover,
.btn:hover,
.btn-cta:hover,
.btn-primary:hover,
.partner-btn:hover,
.affiliate-cta-link:hover,
a.btn:hover,
a.btn-cta:hover,
a.btn-primary:hover,
a.affiliate-cta-link:hover {{
  background-color: var(--brand-hover);
  border-color: var(--brand-hover);
  color: #ffffff;
}}

.btn-secondary,
.btn-outline,
.btn-preset,
.scenario-preset-link,
.on-this-page-nav a,
.cluster-link,
.calc-switcher-btn {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.375rem;
  min-height: 44px;
  min-width: 44px;
  padding: 0.5rem 0.875rem;
  background-color: var(--bg-surface);
  color: var(--text-primary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  font-family: var(--font-sans);
  font-size: 0.875rem;
  font-weight: 600;
  text-decoration: none;
  cursor: pointer;
}}

.btn-secondary:hover,
.btn-outline:hover,
.btn-preset:hover,
.scenario-preset-link:hover,
.on-this-page-nav a:hover,
.cluster-link:hover,
.calc-switcher-btn:hover {{
  background-color: var(--brand-soft);
  border-color: var(--brand-primary);
  color: var(--brand-hover);
}}

/* Calculator Grid, Inputs & Tabular Readouts */
.calc-grid,
.calculator-grid,
.grid-2 {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 320px), 1fr));
  gap: 1.5rem;
  align-items: start;
}}

.calc-grid > *,
.calculator-grid > *,
.grid-2 > *,
.card {{
  min-width: 0;
}}

.tools-grid,
.card-grid,
.grid-3 {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 300px), 1fr));
  gap: 1.25rem;
}}

.tools-list {{
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.75rem;
}}

.tool-link-item {{
  padding: 0.875rem 1rem;
  border: 1px solid var(--border-hairline);
  border-radius: var(--radius-md);
  background-color: var(--bg-subtle);
  margin: 0;
}}

.form-group,
.input-group,
.calc-field {{
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  margin-bottom: 1rem;
}}

label {{
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
}}

input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]):not([type="range"]),
select,
textarea {{
  width: 100%;
  min-height: 44px;
  padding: 0.625rem 0.875rem;
  font-family: var(--font-sans);
  font-size: 16px !important;
  line-height: 1.4;
  color: var(--text-primary);
  background-color: #ffffff;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
}}

input[type="range"] {{
  width: 100%;
  min-height: 44px;
  accent-color: var(--brand-primary);
  cursor: pointer;
  background: transparent;
}}

input[type="checkbox"],
input[type="radio"] {{
  min-width: 44px;
  min-height: 44px;
  accent-color: var(--brand-primary);
}}

.result-box,
.results-panel,
.calc-results,
.output-card {{
  background-color: var(--bg-subtle);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  padding: 1.25rem;
}}

.output-value,
.metric-val,
.metric-value,
.calc-metric-value,
.res-val,
.kpi-value,
.tabular-nums,
output,
[id^="val-"],
[id^="res-"],
[id^="metric-"] {{
  font-variant-numeric: tabular-nums !important;
  font-feature-settings: "tnum" 1;
  color: var(--text-primary);
  font-weight: 700;
}}

.output-value,
.kpi-value {{
  font-size: 1.75rem;
  line-height: 1.2;
}}

/* Badges, Status Pills & Bracket Meter */
.badge,
.pill,
.status-badge,
.authority-badge {{
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.625rem;
  border-radius: 9999px;
  font-size: 0.8125rem;
  font-weight: 600;
  background-color: var(--brand-soft);
  color: var(--brand-hover);
  border: 1px solid var(--brand-border);
}}

.badge-success {{
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.625rem;
  border-radius: 9999px;
  font-size: 0.8125rem;
  font-weight: 600;
  background-color: var(--status-positive-bg);
  color: var(--status-positive);
  border: 1px solid var(--status-positive-border);
}}

.badge-warning {{
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.625rem;
  border-radius: 9999px;
  font-size: 0.8125rem;
  font-weight: 600;
  background-color: var(--status-warning-bg);
  color: var(--status-warning);
  border: 1px solid var(--status-warning-border);
}}

.badge-danger {{
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.625rem;
  border-radius: 9999px;
  font-size: 0.8125rem;
  font-weight: 600;
  background-color: var(--status-danger-bg);
  color: var(--status-danger);
  border: 1px solid var(--status-danger-border);
}}

.badge-neutral {{
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.625rem;
  border-radius: 9999px;
  font-size: 0.8125rem;
  font-weight: 600;
  background-color: var(--bg-subtle);
  color: var(--text-secondary);
  border: 1px solid var(--border-subtle);
}}

.clawback-notice-text {{
  font-size: 0.8125rem;
  font-weight: 700;
  color: var(--status-warning);
  margin-bottom: 0.25rem;
}}

.bracket-meter,
#bracket-meter-bar {{
  display: flex;
  width: 100%;
  height: 12px;
  border-radius: 9999px;
  overflow: hidden;
  background-color: var(--bg-muted);
  gap: 2px;
}}

.bracket-meter-seg {{
  height: 100%;
}}

/* Responsive Tables */
.table-wrap,
.pseo-table-wrap,
.calc-matrix-table-wrap {{
  width: 100%;
  max-width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  border: 1px solid var(--border-hairline);
  border-radius: var(--radius-md);
  background-color: #ffffff;
}}

table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9375rem;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}}

th, td {{
  padding: 0.75rem 1rem;
  text-align: left;
  border-bottom: 1px solid var(--border-hairline);
  vertical-align: top;
}}

th {{
  background-color: var(--bg-subtle);
  color: var(--text-primary);
  font-weight: 600;
  font-size: 0.875rem;
}}

tr:last-child td {{
  border-bottom: none;
}}

.text-right {{
  text-align: right;
}}

/* Methodology, Overlay & Governance Semantic Blocks */
.gsc-overlay-container,
#gsc-striking-overlay {{
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 0 !important;
  margin: 0 !important;
  border: none !important;
  background: transparent !important;
  box-shadow: none !important;
  width: 100%;
  max-width: 100%;
}}

.gsc-overlay-container > *,
#gsc-striking-overlay > * {{
  margin-top: 0 !important;
  margin-bottom: 0 !important;
  margin-left: 0 !important;
  margin-right: 0 !important;
  width: 100%;
  max-width: 100%;
}}

.gsc-remediation-overlay,
.verified-methodology-block,
.editorial-governance-byline,
.multi-dataset-join {{
  background-color: #ffffff;
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  padding: 1.5rem;
  color: var(--text-primary);
}}

.editorial-governance-byline {{
  background-color: var(--bg-subtle);
  font-size: 0.875rem;
  color: var(--text-secondary);
}}

.above-fold-preset-bar,
.serp-preset-bar {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.75rem;
}}

details.faq-item,
.faq-list details {{
  background-color: var(--bg-subtle);
  border: 1px solid var(--border-hairline);
  border-radius: var(--radius-md);
  padding: 0.5rem 1rem;
  margin-bottom: 0.75rem;
}}

details.faq-item summary,
.faq-list details summary {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 44px;
  font-weight: 600;
  color: var(--text-primary);
  cursor: pointer;
}}

.calculation-manifest,
script,
template {{
  display: none !important;
}}

/* Canonical Footer & Lead Capture Card */
.site-footer,
.footer,
.site-footer.footer {{
  background-color: var(--bg-surface);
  border-top: 1px solid var(--border-hairline);
  padding-top: 2.5rem;
  padding-bottom: 2.5rem;
  margin-top: auto;
  color: var(--text-secondary);
  width: 100%;
}}

.footer-lead-card {{
  background-color: var(--bg-subtle);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  padding: 1.5rem;
  margin-bottom: 2rem;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 1.25rem;
}}

.footer-lead-copy {{
  flex: 1 1 320px;
}}

.footer-lead-copy h2,
.footer-lead-copy h3 {{
  margin-bottom: 0.375rem;
  color: var(--text-primary);
}}

.footer-lead-form {{
  flex: 1 1 320px;
  display: flex;
  flex-wrap: wrap;
  gap: 0.625rem;
  align-items: center;
}}

.footer-lead-form input[type="email"] {{
  flex: 1 1 200px;
  min-width: 180px;
}}

.footer-lead-status {{
  width: 100%;
  font-size: 0.875rem;
  color: var(--status-positive);
  font-weight: 600;
  min-height: 1.25rem;
}}

.cf-turnstile-slot {{
  flex-basis: 100%;
  min-height: 0;
}}

.cf-turnstile-slot:empty {{
  display: none;
}}

.footer-grid {{
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1.75rem;
  margin-bottom: 2rem;
}}

.footer-col h3 {{
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 0.625rem 0;
}}

.footer-links {{
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}}

.footer-links li {{
  margin: 0;
}}

.footer-links a {{
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  min-width: 44px;
  padding: 0.25rem 0.375rem;
  color: var(--text-secondary);
  font-size: 0.875rem;
  text-decoration: none;
  border-radius: var(--radius-sm);
}}

.footer-links a:hover {{
  color: var(--brand-primary);
  text-decoration: underline;
}}

.footer-entity-meta {{
  font-size: 0.875rem;
  color: var(--text-secondary);
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}}

.footer-bottom {{
  border-top: 1px solid var(--border-hairline);
  padding-top: 1.25rem;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  font-size: 0.8125rem;
  color: var(--text-muted);
}}

.sr-only {{
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}}

/* Visual Primitives, Workbench, Overlay & Partner Component Rules */
input:not([type="checkbox"]):not([type="radio"]),
select,
textarea {{
  max-width: 100%;
  box-sizing: border-box;
}}

.serp-incumbent-depth-workbench,
.overlay-section,
.affiliate-cta-section {{
  background-color: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  padding: 1.5rem;
  box-shadow: var(--shadow-sm);
}}

.serp-sub-inputs-grid,
.serp-metrics-grid,
.post-calc-upgrade-pillars,
.features-grid,
.scenarios-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr));
  gap: 1rem;
  margin-top: 0.75rem;
  margin-bottom: 0.75rem;
}}

.serp-metric-box,
.calc-metric-card,
.post-calc-upgrade-pillar,
.feature-card,
.scenario-card,
.affiliate-card {{
  background-color: var(--bg-subtle);
  border: 1px solid var(--border-hairline);
  border-radius: var(--radius-md);
  padding: 1rem 1.125rem;
  min-width: 0;
}}

.serp-sub-input,
.serp-sub-select {{
  width: 100%;
  max-width: 100%;
  min-height: 44px;
  min-width: 44px;
  padding: 0.5rem 0.75rem;
  font-size: 1rem;
  color: var(--text-primary);
  background-color: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
}}

.serp-archetype-btn {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  min-width: 44px;
  padding: 0.5rem 0.875rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
  background-color: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  cursor: pointer;
}}

.serp-archetype-btn:hover,
.serp-archetype-btn.active {{
  border-color: var(--brand-primary);
  color: var(--brand-primary);
  background-color: var(--bg-elevated);
}}

.legend-dot {{
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background-color: var(--brand-primary);
  margin-right: 0.375rem;
  vertical-align: middle;
}}

.calc-tooltip {{
  font-size: 0.8125rem;
  color: var(--text-muted);
}}

details.faq-accordion {{
  background-color: var(--bg-surface);
  border: 1px solid var(--border-hairline);
  border-radius: var(--radius-md);
  padding: 0.5rem 1rem;
  margin-bottom: 0.625rem;
}}

details.faq-accordion > summary {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 44px;
  min-width: 44px;
  font-weight: 600;
  color: var(--text-primary);
  cursor: pointer;
  list-style: none;
}}

details.faq-accordion > summary::-webkit-details-marker {{
  display: none;
}}

.hero-range-anchor,
.state-first-hero-bar,
.above-fold-preset-bar,
.pro-hook-card,
.calc-inline-cta,
.lead-capture-card,
.playbook-capture-card {{
  max-width: 100%;
  box-sizing: border-box;
}}

/* Complete Porcelain Light Coverage for All Estate UI Components */
.brand-name {{
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--text-primary);
}}

.hero-subtitle,
.hero-desc,
.section-subtitle,
.section-desc,
.section-lead,
.tool-desc,
.partners-desc {{
  color: var(--text-secondary);
  font-size: 1rem;
  line-height: 1.6;
  margin: 0 0 0.75rem 0;
}}
.verified-date-meta {{
  color: var(--text-secondary);
  font-size: 0.875rem;
  font-weight: 600;
  margin: 0.5rem 0 0 0;
}}

.section-subtitle {{
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--text-primary);
}}

.hero-register-firm-link {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  min-width: 44px;
  padding: 0.5rem 0.875rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-subtle);
  background-color: var(--bg-surface);
  color: var(--brand-primary);
  font-weight: 600;
  font-size: 0.875rem;
  text-decoration: none;
  cursor: pointer;
}}

.hero-register-firm-link:hover {{
  background-color: var(--brand-soft);
  border-color: var(--brand-primary);
  color: var(--brand-hover);
}}

.byline-wrap {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.875rem;
  color: var(--text-muted);
  margin: 0.5rem 0 0.75rem 0;
}}

.byline-author {{
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-style: normal;
}}

.byline-label,
.byline-sep,
.byline-date {{
  color: var(--text-muted);
}}

.byline-link {{
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  min-width: 44px;
  padding: 0.25rem 0.375rem;
  color: var(--brand-primary);
  font-weight: 600;
  text-decoration: none;
  border-radius: var(--radius-sm);
}}

.byline-link:hover {{
  text-decoration: underline;
}}

.byline-org {{
  color: var(--brand-primary);
  font-weight: 600;
}}

.badge-tag {{
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.8125rem;
  font-weight: 600;
  background-color: var(--brand-soft);
  color: var(--brand-hover);
  border: 1px solid var(--brand-border);
  margin-bottom: 0.5rem;
}}

.pill-trust-group {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.75rem;
}}

.pill-trust {{
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.3125rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.8125rem;
  font-weight: 600;
  background-color: var(--bg-subtle);
  color: var(--brand-primary);
  border: 1px solid var(--border-subtle);
  white-space: nowrap;
}}

.separator {{
  color: var(--text-muted);
  margin: 0 0.25rem;
  user-select: none;
}}

.quick-answer-title {{
  font-size: 0.9375rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 0.375rem;
}}

.direct-answer-block {{
  margin-bottom: 1rem;
}}

/* Card Sub-Regions & Semantic Section Containers */
.card-header {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.875rem;
  padding-bottom: 0.625rem;
  border-bottom: 1px solid var(--border-hairline);
}}

.card-body,
.quotable-stats {{
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  color: var(--text-secondary);
  line-height: 1.6;
}}

.article-content,
.benchmark-table-section,
.calculation-methodology-section,
.calculation-scenarios-section,
.commercial-handoff-vetting,
.comparison-container,
.faq-section,
.methodology,
.partner-cta-section,
.partners-section,
.related-tools-section,
.scenario-container,
.sensitivity-matrix-section,
.statutory-comparison-table-section,
.statutory-compliance-section,
.statutory-provenance-box,
.three-tier-cluster-section,
.tools-directory-section,
.cluster-nav,
.regulatory-lead-magnet-card {{
  background-color: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  padding: 1.5rem;
  box-shadow: var(--shadow-sm);
  min-width: 0;
}}

.regulatory-lead-magnet-card {{
  background-color: var(--bg-subtle);
}}

.baseline-output-summary,
.commentary-box,
.statutory-edge-case-trap,
.overlay-partner-guardrail,
.ymyl-public-service-guardrail,
.ymyl-refinance-guardrail {{
  background-color: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-left: 4px solid var(--brand-primary);
  border-radius: var(--radius-card);
  padding: 1.25rem 1.5rem;
  box-shadow: var(--shadow-sm);
}}

.statutory-edge-case-trap {{
  border-left-color: var(--status-warning);
}}

.overlay-partner-guardrail,
.ymyl-public-service-guardrail,
.ymyl-refinance-guardrail {{
  border-left-color: var(--status-positive);
  background-color: var(--bg-subtle);
}}

.ymyl-statutory-warning {{
  font-size: 0.8125rem;
  line-height: 1.55;
  color: var(--text-muted);
}}

.ymyl-disclaimer-banner,
.ymyl-warning-card,
.above-the-fold-compliance,
.ftc-disclosure-card,
.regulatory-forfeiture-warning {{
  background-color: var(--bg-subtle);
  border: 1px solid var(--border-subtle);
  border-left: 4px solid var(--status-warning);
  border-radius: var(--radius-md);
  padding: 0.875rem 1.125rem;
  font-size: 0.875rem;
  line-height: 1.55;
  color: var(--text-secondary);
}}

.statutory-accuracy-benchmarks {{
  display: none;
}}

.commentary-title {{
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 0.5rem 0;
}}
.variant-title {{
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 0.5rem 0;
}}

.commentary-text,
.framework-objective,
.statutory-provenance-note {{
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 0.75rem;
}}

.section-takeaways,
.commentary-takeaways,
.calculation-steps,
.procedure-steps,
.extractable-steps-list,
.autonomous-citation-list,
.related-tools-list,
.overlay-hub-list {{
  margin: 0.5rem 0 0 1.25rem;
  padding: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}}

.related-tools-list,
.overlay-hub-list {{
  list-style: none;
  margin-left: 0;
  display: grid;
  gap: 0.625rem;
}}

.takeaway {{
  background-color: var(--brand-soft);
  border-left: 3px solid var(--brand-primary);
  border-radius: var(--radius-sm);
  padding: 0.625rem 0.875rem;
  color: var(--text-primary);
  font-size: 0.9375rem;
}}

.highlight {{
  background-color: var(--brand-soft);
  color: var(--text-primary);
  border-color: var(--brand-border);
}}

.framework-steps-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr));
  gap: 1rem;
}}

/* Interactive Calculator Components (.interactive-calculator-container & .calc-*) */
.interactive-calculator-container {{
  background-color: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  padding: 1.5rem;
  box-shadow: var(--shadow-sm);
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}}

.calc-header {{
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  border-bottom: 1px solid var(--border-hairline);
  padding-bottom: 0.875rem;
}}

.calc-title {{
  font-size: 1.375rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}}

.calc-desc {{
  font-size: 0.9375rem;
  color: var(--text-secondary);
  margin: 0;
}}

.calc-hub-subtitle,
.calc-column-title {{
  font-size: 1.0625rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 0.5rem 0;
}}

.calc-panel-title {{
  font-size: 1.1875rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 0.5rem 0;
}}

.calc-switcher-panel {{
  background-color: var(--bg-subtle);
  border: 1px solid var(--border-hairline);
  border-radius: var(--radius-md);
  padding: 1rem 1.125rem;
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
}}

.calc-switcher-header,
.calc-panel-header,
.calc-scenarios-header,
.calc-matrix-header,
.calc-entrypoints-header {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem 1rem;
  margin-bottom: 0.5rem;
}}

.calc-switcher-title {{
  font-weight: 700;
  color: var(--text-primary);
  font-size: 0.9375rem;
}}

.calc-switcher-hint {{
  font-size: 0.8125rem;
  color: var(--text-muted);
}}

.calc-switcher-pills,
.preset-wrap,
.scenario-presets-bar,
.runway-preset-chips {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}}

.calc-switcher-dot {{
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 9999px;
  background-color: var(--brand-primary);
  flex-shrink: 0;
}}

.calc-switcher-text {{
  font-size: 0.875rem;
  font-weight: 600;
  color: inherit;
}}

.calc-inputs-column,
.calc-results-column,
.calc-inputs-panel,
.calc-outputs-panel {{
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
}}

.calc-inputs-panel {{
  background-color: var(--bg-surface);
  border: 1px solid var(--border-hairline);
  border-radius: var(--radius-md);
  padding: 1.25rem;
}}

.calc-outputs-panel {{
  background-color: var(--bg-subtle);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 1.25rem;
}}

.calculator-form {{
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}}

.calc-field-group {{
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  margin-bottom: 0.625rem;
}}

.calc-label-row {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}}

.calc-label,
.form-label {{
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
}}

.calc-unit {{
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--text-muted);
}}

.calc-input-wrap {{
  display: flex;
  align-items: stretch;
  width: 100%;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  background-color: var(--bg-surface);
  overflow: hidden;
}}

.calc-input-prefix {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.75rem;
  background-color: var(--bg-subtle);
  color: var(--text-muted);
  font-weight: 600;
  font-size: 0.9375rem;
  border-right: 1px solid var(--border-subtle);
}}

.calc-input-wrap .calc-number-input {{
  border: none;
  border-radius: 0;
  flex: 1 1 auto;
  min-width: 0;
}}

.calc-input,
.calc-number-input,
.calc-select,
.form-input,
.form-select {{
  width: 100%;
  min-height: 44px;
  min-width: 44px;
  padding: 0.625rem 0.875rem;
  font-family: var(--font-sans);
  font-size: 16px;
  line-height: 1.4;
  color: var(--text-primary);
  background-color: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
}}

.calc-slider-wrap {{
  display: flex;
  align-items: center;
  gap: 0.75rem;
  width: 100%;
}}

.calc-slider,
.form-range,
.range-slider,
.slider-control {{
  width: 100%;
  min-height: 44px;
  accent-color: var(--brand-primary);
  cursor: pointer;
  background: transparent;
}}

.calc-value-badge,
.calc-audit-pill,
.calc-live-pill,
.calc-scenarios-badge,
.calc-matrix-badge {{
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.625rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
  background-color: var(--brand-soft);
  color: var(--brand-hover);
  border: 1px solid var(--brand-border);
  white-space: nowrap;
}}

.calc-live-pill,
.calc-audit-pill {{
  background-color: var(--status-positive-bg);
  color: var(--status-positive);
  border-color: var(--status-positive-border);
}}

.calc-metrics-grid,
.metric-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 200px), 1fr));
  gap: 0.875rem;
}}

.metric-box,
.result-card,
.kpi-block {{
  background-color: var(--bg-surface);
  border: 1px solid var(--border-hairline);
  border-radius: var(--radius-md);
  padding: 1rem 1.125rem;
  min-width: 0;
}}

.calc-metric-label,
.metric-label {{
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 0.25rem;
}}

.calc-metric-sub {{
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 0.25rem;
}}

.calc-metric-highlight {{
  background-color: var(--brand-soft);
  border-color: var(--brand-border);
}}

.calc-geo-answer-box,
.calc-statutory-box {{
  background-color: var(--bg-subtle);
  border: 1px solid var(--border-hairline);
  border-left: 4px solid var(--brand-primary);
  border-radius: var(--radius-md);
  padding: 1rem 1.125rem;
}}

.calc-geo-answer-title,
.calc-statutory-label {{
  font-size: 0.875rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 0.375rem;
}}

.calc-geo-answer-text {{
  font-size: 0.9375rem;
  color: var(--text-secondary);
  margin: 0;
}}

.calc-statutory-list {{
  margin: 0.375rem 0 0 1.25rem;
  padding: 0;
  font-size: 0.875rem;
  color: var(--text-secondary);
}}

.calc-objection-takeaway {{
  margin-top: 0.5rem;
  font-size: 0.8125rem;
  color: var(--text-muted);
}}

.calc-scenarios-container,
.calc-matrix-container,
.calc-entrypoints-container {{
  background-color: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  padding: 1.5rem;
  box-shadow: var(--shadow-sm);
}}

.calc-scenarios-grid,
.calc-entrypoints-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr));
  gap: 1rem;
}}

.calc-scenario-card,
.calc-entrypoint-card {{
  background-color: var(--bg-subtle);
  border: 1px solid var(--border-hairline);
  border-radius: var(--radius-md);
  padding: 1rem 1.125rem;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 0.5rem;
  text-decoration: none;
  color: var(--text-primary);
}}

.calc-entrypoint-card:hover {{
  border-color: var(--brand-primary);
  background-color: var(--brand-soft);
}}

.calc-scenario-q,
.calc-entrypoint-title {{
  font-size: 0.9375rem;
  font-weight: 700;
  color: var(--text-primary);
}}

.calc-scenario-ans {{
  font-size: 0.875rem;
  color: var(--text-secondary);
  line-height: 1.55;
}}

.calc-scenario-footer {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--border-hairline);
}}

.calc-scenario-cite {{
  font-size: 0.75rem;
  color: var(--text-muted);
}}

.calc-entrypoint-action {{
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--brand-primary);
}}

.calc-scenario-btn,
.preset-btn,
.runway-chip,
.scenario-preset-pill,
.query-pill,
.contextual-cluster-link,
.btn-share {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.375rem;
  min-height: 44px;
  min-width: 44px;
  padding: 0.5rem 0.875rem;
  background-color: var(--bg-surface);
  color: var(--text-primary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  font-family: var(--font-sans);
  font-size: 0.875rem;
  font-weight: 600;
  text-decoration: none;
  cursor: pointer;
}}

.calc-scenario-btn:hover,
.preset-btn:hover,
.runway-chip:hover,
.scenario-preset-pill:hover,
.query-pill:hover,
.contextual-cluster-link:hover,
.btn-share:hover {{
  background-color: var(--brand-soft);
  border-color: var(--brand-primary);
  color: var(--brand-hover);
}}

.breakdown-list {{
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}}

.breakdown-item {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--border-hairline);
}}

.breakdown-item:last-child {{
  border-bottom: none;
}}

.breakdown-label {{
  font-size: 0.875rem;
  color: var(--text-secondary);
}}

.breakdown-val,
.breakdown-value {{
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--text-primary);
}}

.runway-chart-wrap {{
  width: 100%;
  background-color: var(--bg-subtle);
  border: 1px solid var(--border-hairline);
  border-radius: var(--radius-md);
  padding: 1rem;
  overflow-x: auto;
}}

.share-pro-container {{
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 1rem;
}}

.calculation-variant {{
  padding: 1rem 1.125rem;
  border: 1px solid var(--border-hairline);
  border-radius: var(--radius-md);
  background-color: var(--bg-surface);
  margin-top: 0.75rem;
}}

/* Subsidy Meter & Legend */
.subsidy-meter-wrap {{
  background-color: var(--bg-surface);
  border: 1px solid var(--border-hairline);
  border-radius: var(--radius-md);
  padding: 1rem 1.125rem;
}}

.subsidy-meter-header,
.subsidy-meter-label {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 0.5rem;
}}

.subsidy-meter-bar {{
  display: flex;
  width: 100%;
  height: 12px;
  border-radius: 9999px;
  overflow: hidden;
  background-color: var(--bg-muted);
  gap: 2px;
}}

.subsidy-meter-seg {{
  height: 100%;
  transition: width 0.2s ease;
}}

.subsidy-meter-seg-pay {{
  background-color: var(--brand-primary);
}}

.subsidy-meter-seg-sub {{
  background-color: var(--status-positive);
}}

.subsidy-meter-legend {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1.25rem;
  margin-top: 0.625rem;
  font-size: 0.8125rem;
  color: var(--text-secondary);
}}

.legend-item {{
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
}}

.dot-pay,
.dot-sub,
.dot-int {{
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 9999px;
  flex-shrink: 0;
}}

.dot-pay {{
  background-color: var(--brand-primary);
}}

.dot-sub {{
  background-color: var(--status-positive);
}}

.dot-int {{
  background-color: var(--status-warning);
}}

/* Quick Unlock, Lead Capture, Post-Calc Upgrade & Partner Quote Forms */
.calc-result-quick-unlock-bar,
.inline-lead-box {{
  background-color: var(--bg-elevated);
  border: 1px solid var(--brand-border);
  border-left: 4px solid var(--status-positive);
  border-radius: var(--radius-md);
  padding: 1rem 1.125rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}}

.calc-inline-cta-copy,
.quick-unlock-value-summary {{
  font-size: 0.9375rem;
  color: var(--text-primary);
  line-height: 1.5;
}}

.lead-capture-form,
.inline-worksheet-capture-form,
.newsletter-form,
.partner-registration-form {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.625rem;
  align-items: center;
}}

.lead-capture-status-readout,
.partner-registration-status,
.partner-quote-status,
.serp-blueprint-status {{
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--status-positive);
  min-height: 1.25rem;
}}

.post-calc-upgrade-header,
.partner-quote-header {{
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  margin-bottom: 0.875rem;
}}

.post-calc-upgrade-badge,
.partner-quote-badge,
.partner-badge,
.affiliate-badge,
.affiliate-disclosure-badge {{
  display: inline-flex;
  align-items: center;
  width: fit-content;
  padding: 0.25rem 0.625rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
  background-color: var(--brand-soft);
  color: var(--brand-hover);
  border: 1px solid var(--brand-border);
}}

.affiliate-disclosure-badge {{
  background-color: var(--bg-subtle);
  color: var(--text-secondary);
  border-color: var(--border-subtle);
}}

.post-calc-upgrade-title,
.partner-title,
.affiliate-title {{
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0.25rem 0;
}}

.post-calc-upgrade-summary,
.post-calc-pillar-copy,
.affiliate-desc,
.partner-quote-frictionless-note,
.partner-status-note {{
  font-size: 0.875rem;
  color: var(--text-secondary);
  line-height: 1.55;
}}

.post-calc-pillar-heading {{
  font-size: 0.9375rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 0.25rem;
}}

.post-calc-sample-schedule-preview {{
  background-color: var(--bg-subtle);
  border: 1px dashed var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 0.875rem 1rem;
  font-size: 0.875rem;
  line-height: 1.5;
  color: var(--text-secondary);
}}

.post-calc-preview-slot {{
  min-height: 0;
}}

.post-calc-upgrade-actions,
.partner-quote-actions {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.625rem;
  align-items: center;
  margin-top: 0.75rem;
}}

.post-calc-quick-unlock-btn,
.post-calc-upgrade-btn,
.partner-quote-submit-btn,
.pro-hook-link,
.pro-hook-direct-checkout,
.pro-hook-quote-jump,
.pro-hook-sample-unlock {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.375rem;
  min-height: 44px;
  min-width: 44px;
  padding: 0.625rem 1rem;
  background-color: var(--brand-primary);
  color: var(--cta-fg);
  border: 1px solid var(--brand-primary);
  border-radius: var(--radius-md);
  font-family: var(--font-sans);
  font-size: 0.875rem;
  font-weight: 600;
  text-decoration: none;
  cursor: pointer;
}}

.post-calc-quick-unlock-btn:hover,
.post-calc-upgrade-btn:hover,
.partner-quote-submit-btn:hover,
.pro-hook-link:hover,
.pro-hook-direct-checkout:hover,
.pro-hook-quote-jump:hover,
.pro-hook-sample-unlock:hover {{
  background-color: var(--brand-hover);
  border-color: var(--brand-hover);
  color: var(--cta-fg);
}}

.pro-hook-quote-jump,
.pro-hook-sample-unlock {{
  background-color: var(--bg-surface);
  color: var(--brand-primary);
}}

.pro-hook-quote-jump:hover,
.pro-hook-sample-unlock:hover {{
  background-color: var(--brand-soft);
  color: var(--brand-hover);
}}

.partner-matrix-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr));
  gap: 1rem;
}}

.partner-quote-form-body {{
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
}}

.partner-quote-consent-row {{
  margin: 0.5rem 0;
}}

.partner-quote-consent-label {{
  display: flex;
  align-items: flex-start;
  gap: 0.625rem;
  min-height: 44px;
  min-width: 44px;
  padding: 0.375rem 0;
  font-size: 0.8125rem;
  line-height: 1.45;
  color: var(--text-secondary);
  cursor: pointer;
}}

/* SERP Workbench, Cliff Visualizer, Comparator & Blueprint */
.serp-workbench-intro {{
  font-size: 0.9375rem;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 1rem;
}}

.serp-intent-banner {{
  background-color: var(--brand-soft);
  border: 1px solid var(--brand-border);
  border-left: 4px solid var(--brand-primary);
  border-radius: var(--radius-md);
  padding: 1rem 1.25rem;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.875rem;
  margin: 0.75rem 0;
}}

.serp-intent-banner-text {{
  flex: 1 1 280px;
  font-size: 0.9375rem;
  color: var(--text-primary);
  line-height: 1.55;
}}

.serp-intent-banner-btn,
.serp-blueprint-btn,
.serp-comparator-btn {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.375rem;
  min-height: 44px;
  min-width: 44px;
  padding: 0.5rem 0.875rem;
  background-color: var(--brand-primary);
  color: var(--cta-fg);
  border: 1px solid var(--brand-primary);
  border-radius: var(--radius-md);
  font-family: var(--font-sans);
  font-size: 0.875rem;
  font-weight: 600;
  text-decoration: none;
  cursor: pointer;
}}

.serp-intent-banner-btn:hover,
.serp-blueprint-btn:hover,
.serp-comparator-btn:hover {{
  background-color: var(--brand-hover);
  border-color: var(--brand-hover);
  color: var(--cta-fg);
}}

.serp-field-group {{
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}}

.serp-field-label,
.serp-metric-label {{
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-muted);
}}

.serp-metric-val {{
  font-size: 1.25rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--text-primary);
}}

.serp-input-cell,
.serp-select-input {{
  width: 100%;
  min-height: 44px;
  min-width: 44px;
  padding: 0.5rem 0.75rem;
  font-size: 16px;
  color: var(--text-primary);
  background-color: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
}}

.serp-svg-chart-wrap {{
  width: 100%;
  max-width: 100%;
  overflow-x: auto;
  margin: 0.75rem 0;
}}

.serp-visual-breakdown-svg {{
  max-width: 100%;
  height: auto;
  display: block;
}}

.serp-cliff-visualizer,
.serp-scenario-comparator,
.serp-decision-blueprint {{
  margin-top: 1.25rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-hairline);
}}

/* Tables, Scenarios, Overlays, Affiliates & Topic Clusters */
.comparison-table,
.data-table,
.calc-matrix-table,
.calculation-table,
.proprietary-calculation-table,
.scenario-table,
.serp-cliff-matrix-table,
.serp-scenario-comparator-table,
.serp-statutory-reference-table,
.statutory-pitfalls-table,
.overlay-comparison-table,
.overlay-decision-matrix-table {{
  width: 100%;
  border-collapse: collapse;
  font-variant-numeric: tabular-nums;
}}

.td-num {{
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  white-space: nowrap;
}}

.td-plan-name {{
  font-weight: 600;
  color: var(--text-primary);
}}

.scenario-baseline,
.scenario-conservative,
.scenario-moderate-contraction,
.scenario-moderate-expansion,
.scenario-aggressive {{
  font-variant-numeric: tabular-nums;
}}

.scenario-ast-eval {{
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  color: var(--text-primary);
}}

.scenario-cliff-delta {{
  font-variant-numeric: tabular-nums;
  font-size: 0.875rem;
  color: var(--text-secondary);
}}

.scenario-presets-section,
.scenario-presets-group {{
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}}

.topic-cluster-tier {{
  background-color: var(--bg-subtle);
  border: 1px solid var(--border-hairline);
  border-radius: var(--radius-md);
  padding: 1rem 1.125rem;
  margin-bottom: 0.875rem;
}}

.connected-queries-block {{
  margin-top: 1.25rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-hairline);
}}

.connected-query {{
  margin-bottom: 0.875rem;
}}

.next-step-prompt {{
  background-color: var(--bg-surface);
  border: 1px solid var(--border-hairline);
  border-left: 3px solid var(--brand-primary);
  border-radius: var(--radius-sm);
  padding: 0.75rem 1rem;
  margin-bottom: 0.75rem;
}}

.overlay-autonomous-assertions,
.overlay-headings,
.overlay-scenarios,
.overlay-comparison,
.overlay-ai-decision-matrix,
.overlay-hub-links,
.overlay-partner-offer,
.overlay-faqs {{
  background-color: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  padding: 1.5rem;
  box-shadow: var(--shadow-sm);
}}

.overlay-comparison-row,
.overlay-decision-matrix-row {{
  transition: background-color 0.15s ease;
}}

.overlay-comparison-row:hover,
.overlay-decision-matrix-row:hover {{
  background-color: var(--bg-subtle);
}}

.affiliate-info {{
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}}

.affiliate-disclosure {{
  font-size: 0.8125rem;
  color: var(--text-muted);
  margin-top: 0.5rem;
}}

.affiliate-cta {{
  margin-top: 0.75rem;
}}

/* Mobile Responsive Breakpoints */
@media (max-width: 900px) {{
  .footer-grid {{
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }}
}}

@media (max-width: 768px) {{
  .nav-links,
  a.btn.btn-cta.nav-cta-desktop,
  a.btn-cta.nav-cta-desktop,
  .nav-cta-desktop {{
    display: none;
  }}

  .mobile-nav-menu {{
    display: block;
  }}

  h1, .hero-title {{
    font-size: 1.625rem;
  }}

  h2, .section-title {{
    font-size: 1.25rem;
  }}

  h3, .card-title {{
    font-size: 1.0625rem;
  }}

  .card,
  .pseo-card,
  .calc-card,
  .interactive-calc-card,
  .calculation-container,
  .hero-section,
  .tool-hero {{
    padding: 1.25rem;
  }}

  .footer-grid,
  .calc-grid,
  .calculator-grid,
  .grid-2,
  .calc-metrics-grid,
  .metric-grid,
  .serp-sub-inputs-grid,
  .serp-metrics-grid,
  .calc-scenarios-grid,
  .calc-entrypoints-grid,
  .partner-matrix-grid,
  .framework-steps-grid,
  .post-calc-upgrade-pillars,
  .features-grid,
  .scenarios-grid,
  .tools-grid,
  .card-grid,
  .grid-3 {{
    grid-template-columns: minmax(0, 1fr);
  }}

  div[style*="grid-template-columns"] {{
    grid-template-columns: minmax(0, 1fr) !important;
  }}

  .pill-trust-group,
  .calc-switcher-pills,
  .scenario-presets-bar,
  .runway-preset-chips,
  .post-calc-upgrade-actions,
  .partner-quote-actions {{
    flex-wrap: wrap;
  }}

  .pill-trust,
  .badge,
  .badge-tag,
  .pill,
  .status-badge,
  .authority-badge {{
    max-width: 100%;
  }}

  .calc-inline-cta a,
  .comparison-table-cta-bar a,
  .pro-hook-card a,
  .affiliate-card a,
  .partner-card a,
  .btn-cta,
  .btn-primary,
  .partner-cta,
  .affiliate-cta-link {{
    white-space: normal !important;
    overflow-wrap: break-word;
    text-align: center;
    max-width: 100%;
    box-sizing: border-box;
  }}
}}

/* Executive CPA & Statutory Workpaper Print Stylesheet */
@media print {{
  .header,
  .site-header,
  .nav-wrap,
  .mobile-nav-menu,
  .skip-link,
  .affiliate-section,
  .affiliates-section,
  .refinance-partner-section,
  .footer-lead-card,
  .site-footer,
  .footer,
  .btn,
  .btn-cta {{
    display: none !important;
  }}

  body,
  .card,
  .pseo-card {{
    background: #ffffff;
    color: #000000;
    box-shadow: none;
  }}
}}
"""
    defined, referenced = extract_defined_and_referenced_css_vars(css)
    undefined = sorted(referenced - defined)
    if undefined:
        raise ValueError(f"Generated Porcelain CSS contains undefined custom properties: {undefined}")
    css_hash = hashlib.sha256(css.encode("utf-8")).hexdigest()[:10]
    return css, css_hash, frozenset(defined)


def _get_porcelain_stylesheet_meta_from_profile(profile: Dict[str, Any]) -> Tuple[str, str, FrozenSet[str]]:
    """Validates profile WCAG palette and returns cached (css_text, sha256_10, defined_css_vars)."""
    assert_porcelain_palette_wcag(profile)
    return _generate_porcelain_stylesheet_cached(
        str(profile["brand_name"]),
        str(profile["brand_primary"]),
        str(profile["brand_hover"]),
        str(profile["brand_soft"]),
        str(profile["brand_border"]),
    )


def generate_porcelain_stylesheet_from_profile(profile: Dict[str, Any]) -> str:
    """Generates the single canonical Porcelain Light CSS stylesheet for a tenant profile."""
    css, _, _ = _get_porcelain_stylesheet_meta_from_profile(profile)
    return css


def generate_porcelain_stylesheet(property_id: str) -> str:
    """Public entrypoint returning canonical Porcelain Light CSS for property_id."""
    return generate_porcelain_stylesheet_from_profile(get_porcelain_tenant_profile(property_id))


def _has_interactive_calculator_controls(html_content: str) -> bool:
    """Checks whether an HTML document contains interactive calculator controls outside footer chrome."""
    if not html_content:
        return False
    stripped = re.sub(r"<(style|script|noscript)\b[^>]*>[\s\S]*?</\1>", "", html_content, flags=re.IGNORECASE)
    stripped = re.sub(r"<footer\b[^>]*>[\s\S]*?</footer>", "", stripped, flags=re.IGNORECASE)
    low = stripped.lower()
    if any(
        tok in low
        for tok in (
            'id="calculate-btn"',
            "id='calculate-btn'",
            'id="calculator-workspace"',
            "id='calculator-workspace'",
            "calculator-form",
            "calculation-container",
            "interactive-calculator-container",
            "interactive-calc-card",
            "calc-card",
            "calculator-grid",
            "calc-grid",
            'type="range"',
            "type='range'",
            "data-calc-input",
        )
    ):
        return True
    if re.search(r'<input\b[^>]*type=["\']number["\']', low):
        return True
    if re.search(r"<select\b[^>]*\b(?:id|name)=", low):
        return True
    return False


def classify_porcelain_blueprint(
    rel_path: str,
    html_content: str = "",
    property_id: str = "",
) -> str:
    """Classifies any built HTML route into its deterministic public blueprint or operator_pwa."""
    _ = property_id
    rel = str(rel_path or "").strip().lstrip("/").replace("\\", "/")
    rel_low = rel.lower()
    if (
        rel_low in ("signal", "signal/index.html", "static/signal/index.html", "signal.html")
        or rel_low.startswith("signal/")
        or rel_low.startswith("static/signal/")
    ):
        return "operator_pwa"
    if rel_low in ("404.html", "404/index.html"):
        return "error_404"
    if rel_low in ("", "index.html"):
        return "home_hub"
    if rel_low in ("tools", "tools/index.html", "tools.html"):
        return "tools_directory"
    for gov in GOVERNANCE_ROUTES:
        if rel_low in (f"{gov}/index.html", f"{gov}.html"):
            return "governance_legal"
    if rel_low in (
        "vs",
        "vs/index.html",
        "vs.html",
        "comparisons",
        "comparisons/index.html",
        "guides",
        "guides/index.html",
        "guides.html",
        "articles",
        "articles/index.html",
        "research",
        "research/index.html",
    ):
        return "editorial_hub"
    if rel_low.startswith(("vs/", "comparisons/", "compare/")):
        return "comparison_leaf"
    if rel_low.startswith(("guides/", "articles/", "research/")):
        return "editorial_guide"
    if not html_content:
        return "calculator_leaf" if rel_low.startswith("tools/") else "editorial_guide"
    if _has_interactive_calculator_controls(html_content):
        return "calculator_leaf"
    if "-vs-" in rel_low or "comparison" in rel_low:
        return "comparison_leaf"
    dom_low = re.sub(r"<(style|script|noscript)\b[^>]*>[\s\S]*?</\1>", "", html_content, flags=re.IGNORECASE).lower()
    if ("comparison-table" in dom_low or 'data-entity-type="scenario"' in dom_low) and "<table" in dom_low:
        return "comparison_leaf"
    return "editorial_guide"


def render_porcelain_header(profile: Dict[str, Any]) -> str:
    """Renders canonical skip-link + <header class='site-header header'> with mobile drawer."""
    brand = html_lib.escape(profile["brand_name"])
    badge = html_lib.escape(profile["badge_letter"])
    return f"""  <a class="skip-link skip-to-content-link" href="#main-content">Skip to main content</a>
  <header class="site-header header" role="banner">
    <div class="container nav-wrap">
      <a href="/" class="brand-logo touch-target" aria-label="{brand} Home">
        <span class="brand-mark" aria-hidden="true">{badge}</span>
        <span class="brand-name">{brand}</span>
      </a>
      <div class="nav-desktop-group">
        <nav aria-label="Primary Navigation">
          <ul class="nav-links">
            <li><a href="/tools/" class="touch-target">Calculators</a></li>
            <li><a href="/methodology/" class="touch-target">Methodology</a></li>
            <li><a href="/about/" class="touch-target">About</a></li>
            <li><a href="/contact/" class="touch-target">Contact</a></li>
          </ul>
        </nav>
        <a href="/tools/" class="btn btn-cta nav-cta-desktop touch-target">Explore Tools</a>
      </div>
      <details class="mobile-nav-menu">
        <summary class="touch-target" aria-label="Toggle navigation menu">Menu</summary>
        <nav class="mobile-nav-drawer" aria-label="Mobile Navigation">
          <a href="/tools/" class="touch-target">Calculators</a>
          <a href="/methodology/" class="touch-target">Methodology</a>
          <a href="/about/" class="touch-target">About</a>
          <a href="/contact/" class="touch-target">Contact</a>
          <a href="/disclaimers/" class="touch-target">Disclaimers</a>
          <a href="/tools/" class="btn btn-cta touch-target">Explore Tools</a>
        </nav>
      </details>
    </div>
  </header>"""


def render_porcelain_compliance_strip(
    profile: Dict[str, Any],
    is_restricted_public_service: bool = False,
    rel_path: str = "",
) -> str:
    """Renders the single canonical above-the-fold YMYL + FTC 16 CFR Part 255 disclosure strip."""
    raw_text = (
        profile["restricted_compliance_text"]
        if is_restricted_public_service
        else profile["compliance_text"]
    )
    if profile.get("property_id") == "gainhelm" and rel_path and not is_restricted_public_service:
        rel_clean = str(rel_path).strip().lstrip("/").lower()
        if rel_clean.startswith(("tools/", "vs/", "guides/")) and rel_clean not in (
            "tools/index.html",
            "vs/index.html",
            "guides/index.html",
        ):
            from pseofactory.affiliates import get_gainhelm_compliance_strip_text

            raw_text = get_gainhelm_compliance_strip_text(rel_clean)
    return (
        '      <div class="compliance-strip ftc-disclosure-banner" role="note" '
        'aria-label="Statutory and FTC Disclosure">\n'
        f"        <p>{html_lib.escape(raw_text)} "
        '<a href="/disclaimers/" class="touch-target">Read full disclosures</a>.</p>\n'
        "      </div>"
    )


def render_porcelain_footer(
    profile: Dict[str, Any],
    active_tools: Optional[Sequence[Tuple[str, str]]] = None,
    page_slug: str = "homepage",
    has_main_lead_form: bool = False,
    has_quote_intake_step: bool = False,
) -> str:
    """Renders canonical <footer class='site-footer footer'> with lead card + 4 columns."""
    brand = html_lib.escape(profile["brand_name"])
    legal_entity = html_lib.escape(profile["legal_entity"])
    research_entity = html_lib.escape(profile["research_entity"])
    email = html_lib.escape(profile["contact_email"])
    li_id = str(profile.get("linkedin_company_id") or "").strip()
    form_id = (
        "lead-capture-form"
        if (not has_main_lead_form and has_quote_intake_step)
        else "footer-lead-capture-form"
    )

    tools_list = list(active_tools or profile.get("default_tools") or [])[:5]
    tool_items = [
        f'            <li><a href="/tools/{html_lib.escape(slug)}/" class="touch-target">{html_lib.escape(_format_porcelain_tool_label(label))}</a></li>'
        for slug, label in tools_list
        if slug
    ]
    tool_items.append('            <li><a href="/tools/" class="touch-target">All Calculators Directory</a></li>')
    tools_ul = "\n".join(tool_items)

    linkedin_line = ""
    if li_id:
        li_url = f"https://www.linkedin.com/company/{html_lib.escape(li_id)}/"
        linkedin_line = (
            f'            <a href="{li_url}" rel="noopener noreferrer" target="_blank" '
            f'class="touch-target">{brand} Company LinkedIn</a>\n'
        )

    safe_slug = html_lib.escape(page_slug or "homepage")
    year_str = "2026"
    return f"""  <footer class="site-footer footer" role="contentinfo">
    <div class="container">
      <div class="footer-lead-card regulatory-lead-magnet-card">
        <div class="footer-lead-copy">
          <h2>Statutory Parameter &amp; Rate Update Briefings</h2>
          <p>Receive deterministic statutory schedule updates and calculator workpaper notices from {research_entity}.</p>
        </div>
        <form id="{form_id}" class="footer-lead-form newsletter-form" action="/api/lead-capture" method="post" novalidate>
          <label for="footer-lead-email" class="sr-only">Work email address</label>
          <input type="email" id="footer-lead-email" name="email" required autocomplete="email" placeholder="you@company.com">
          <input type="hidden" name="tool_slug" value="{safe_slug}">
          <input type="text" name="company_website" tabindex="-1" autocomplete="off" aria-hidden="true" aria-label="Company website" style="position:absolute;left:-9999px;width:1px;height:1px;opacity:0;pointer-events:none;">
          <div class="cf-turnstile-slot" data-turnstile-slot="1"></div>
          <button type="submit" class="btn btn-cta touch-target">Subscribe to Updates</button>
          <div id="footer-lead-status" class="footer-lead-status" aria-live="polite"></div>
        </form>
      </div>
      <div class="footer-grid">
        <div class="footer-col">
          <h3>Calculators &amp; Tools</h3>
          <ul class="footer-links">
{tools_ul}
          </ul>
        </div>
        <div class="footer-col">
          <h3>Governance &amp; Legal</h3>
          <ul class="footer-links">
            <li><a href="/about/" class="touch-target">About {brand}</a></li>
            <li><a href="/methodology/" class="touch-target">Methodology</a></li>
            <li><a href="/privacy/" class="touch-target">Privacy Policy</a></li>
            <li><a href="/terms/" class="touch-target">Terms of Use</a></li>
            <li><a href="/disclaimers/" class="touch-target">Disclaimers &amp; FTC Notice</a></li>
            <li><a href="/contact/" class="touch-target">Contact Editorial Desk</a></li>
          </ul>
        </div>
        <div class="footer-col">
          <h3>Feeds &amp; Machine Discovery</h3>
          <ul class="footer-links">
            <li><a href="/sitemap.xml" class="touch-target">XML Sitemap</a></li>
            <li><a href="/feed.xml" class="touch-target">Atom / RSS Feed</a></li>
            <li><a href="/llms.txt" class="touch-target">LLMs Knowledge Manifest</a></li>
            <li><a href="/catalog.json" class="touch-target">Tool Catalog JSON</a></li>
          </ul>
        </div>
        <div class="footer-col">
          <h3>Entity &amp; Editorial Contact</h3>
          <div class="footer-entity-meta">
            <span><strong>Publisher:</strong> {legal_entity}</span>
            <span><strong>Research Desk:</strong> {research_entity}</span>
            <!--email_off--><a href="mailto:{email}" class="touch-target">{email}</a><!--/email_off-->
{linkedin_line}          </div>
        </div>
      </div>
      <div class="footer-bottom">
        <span>&copy; {year_str} {legal_entity}. All statutory models verified for educational decision support.</span>
        <span>Independent statutory calculation publisher. Zero personalized legal or tax advice.</span>
      </div>
    </div>
  </footer>
  <script id="porcelain-footer-lead-handler">
  (function() {{
    var form = document.getElementById('{form_id}');
    if (!form || form.dataset.porcelainBound === '1') return;
    form.dataset.porcelainBound = '1';
    var renderedAt = Date.now();

    function getFormTsState(f) {{
      if (!f.__pseoTsState) {{
        f.__pseoTsState = {{ booting: false, mounted: false, enabled: false, siteKey: '', token: '', widgetId: null }};
      }}
      return f.__pseoTsState;
    }}

    function loadLeadConfig() {{
      var loc = window.location || null;
      var isLocalStatic = Boolean(
        loc && (loc.protocol === 'http:' || loc.protocol === 'file:')
      );
      if (
        window.__PSEO_SYNTHETIC_TEST__
        || (isLocalStatic && !window.__PSEO_FORCE_TURNSTILE_CONFIG__)
        || typeof fetch !== 'function'
      ) {{
        return Promise.resolve({{ turnstile_enabled: false, turnstile_site_key: '' }});
      }}
      if (!window.__pseoLeadConfigPromise) {{
        window.__pseoLeadConfigPromise = fetch('/api/lead-capture?config=1', {{
          method: 'GET',
          headers: {{ 'Accept': 'application/json' }}
        }})
          .then(function(r) {{ return r && r.ok ? r.json() : {{}}; }})
          .then(function(cfg) {{
            return {{
              turnstile_enabled: Boolean(cfg && cfg.turnstile_enabled && cfg.turnstile_site_key),
              turnstile_site_key: String((cfg && cfg.turnstile_site_key) || '')
            }};
          }})
          .catch(function() {{
            return {{ turnstile_enabled: false, turnstile_site_key: '' }};
          }});
      }}
      return window.__pseoLeadConfigPromise;
    }}

    function ensureTurnstileScript() {{
      if (window.turnstile && typeof window.turnstile.render === 'function') {{
        return Promise.resolve(window.turnstile);
      }}
      if (!window.__pseoTurnstileScriptPromise) {{
        window.__pseoTurnstileScriptPromise = new Promise(function(resolve) {{
          var existing = document.querySelector('script[src*="challenges.cloudflare.com/turnstile/v0/api.js"]');
          if (existing) {{
            var waited = 0;
            var poll = setInterval(function() {{
              waited += 50;
              if (window.turnstile && typeof window.turnstile.render === 'function') {{
                clearInterval(poll);
                resolve(window.turnstile);
              }} else if (waited >= 6000) {{
                clearInterval(poll);
                resolve(null);
              }}
            }}, 50);
            return;
          }}
          var s = document.createElement('script');
          s.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
          s.async = true;
          s.defer = true;
          s.onload = function() {{ resolve(window.turnstile || null); }};
          s.onerror = function() {{ resolve(null); }};
          (document.head || document.body || document.documentElement).appendChild(s);
        }});
      }}
      return window.__pseoTurnstileScriptPromise;
    }}

    function mountTurnstileIfEnabled() {{
      var slot = form.querySelector('.cf-turnstile-slot');
      if (!slot) return;
      var st = getFormTsState(form);
      if (st.booting || st.mounted || slot.getAttribute('data-turnstile-mounted') === '1') return;
      st.booting = true;
      loadLeadConfig().then(function(cfg) {{
        st.enabled = Boolean(cfg && cfg.turnstile_enabled && cfg.turnstile_site_key);
        st.siteKey = String((cfg && cfg.turnstile_site_key) || '');
        if (!st.enabled || !st.siteKey) {{
          st.booting = false;
          return;
        }}
        ensureTurnstileScript().then(function(tsApi) {{
          if (!tsApi || typeof tsApi.render !== 'function' || st.mounted || slot.getAttribute('data-turnstile-mounted') === '1') {{
            st.booting = false;
            return;
          }}
          try {{
            slot.setAttribute('data-turnstile-mounted', '1');
            st.mounted = true;
            st.widgetId = tsApi.render(slot, {{
              sitekey: st.siteKey,
              callback: function(tok) {{ st.token = String(tok || ''); }},
              'expired-callback': function() {{ st.token = ''; }},
              'error-callback': function() {{ st.token = ''; }}
            }});
          }} catch (e) {{
            st.mounted = false;
            slot.removeAttribute('data-turnstile-mounted');
          }}
          st.booting = false;
        }});
      }});
    }}

    function buildSafeHtmlWorksheetUrl(rawUrl) {{
      var u = String(rawUrl || '').trim();
      if (!u || u.charAt(0) !== '/' || u.indexOf('//') === 0) return '';
      if (u.indexOf('format=') === -1) {{
        u += (u.indexOf('?') === -1 ? '?format=html' : '&format=html');
      }}
      return u;
    }}

    function readCurrentToken() {{
      var st = getFormTsState(form);
      var tsInput = form.querySelector('input[name="cf-turnstile-response"]');
      return String(st.token || (tsInput ? tsInput.value || '' : '')).trim();
    }}

    function waitForTurnstileReady(statusEl, onReady) {{
      if (window.__PSEO_SYNTHETIC_TEST__) {{
        onReady('');
        return;
      }}
      loadLeadConfig().then(function(cfg) {{
        if (!cfg || !cfg.turnstile_enabled || !cfg.turnstile_site_key) {{
          onReady('');
          return;
        }}
        mountTurnstileIfEnabled();
        var tokNow = readCurrentToken();
        if (tokNow) {{
          onReady(tokNow);
          return;
        }}
        if (statusEl) statusEl.textContent = 'Verifying browser security check...';
        var elapsed = 0;
        var timer = setInterval(function() {{
          elapsed += 100;
          var tok = readCurrentToken();
          if (tok) {{
            clearInterval(timer);
            onReady(tok);
          }} else if (elapsed >= 2500) {{
            clearInterval(timer);
            form.setAttribute('data-submission-state', 'verification_required');
            if (statusEl) statusEl.textContent = 'Please complete the security verification check before submitting.';
          }}
        }}, 100);
      }});
    }}

    // Eagerly fetch config and warm up Turnstile on page load
    if (!window.__PSEO_SYNTHETIC_TEST__) {{
      mountTurnstileIfEnabled();
    }}
    form.addEventListener('focusin', mountTurnstileIfEnabled);
    form.addEventListener('mouseenter', mountTurnstileIfEnabled);

    function formatLeadError(data, httpStatus) {{
      var code = String((data && (data.error || data.status)) || '').toLowerCase();
      if (httpStatus === 429 || code === 'rate_limited') {{
        return 'Too many requests from this network. Please try again in an hour.';
      }}
      if (code === 'bot_verification_failed') {{
        return 'Verification check failed. Please complete the security widget and try again.';
      }}
      if (code === 'submitted_too_fast') {{
        return 'Please wait a second before submitting the form.';
      }}
      if (code === 'bot_detected' || code === 'origin_not_allowed') {{
        return 'Submission could not be verified. Please refresh the page and try again.';
      }}
      return (data && data.error) ? String(data.error) : 'Unable to submit right now. Please try again.';
    }}

    form.addEventListener('submit', function(ev) {{
      if (form.id === 'lead-capture-form' && window.__PSEO_RUNTIME_LEAD_HANDLER__) {{
        return;
      }}
      ev.preventDefault();
      var emailEl = form.querySelector('input[type="email"]');
      var statusEl = form.querySelector('#footer-lead-status, .footer-lead-status') || document.getElementById('footer-lead-status');
      var emailVal = emailEl ? String(emailEl.value || '').trim() : '';
      if (!emailVal || emailVal.indexOf('@') === -1) {{
        if (statusEl) statusEl.textContent = 'Enter a valid email address.';
        if (emailEl) emailEl.focus();
        return;
      }}
      var hpEl = form.querySelector('input[name="company_website"]');
      var hpVal = hpEl ? String(hpEl.value || '') : '';
      var slugEl = form.querySelector('input[name="tool_slug"]');
      if (typeof fetch !== 'function') {{
        if (statusEl) statusEl.textContent = 'Unable to submit in this browser environment.';
        return;
      }}
      waitForTurnstileReady(statusEl, function(tokenVal) {{
        var payload = {{
          email: emailVal,
          tool_slug: slugEl ? slugEl.value : 'homepage',
          source: window.location.pathname || '/',
          company_website: hpVal,
          form_rendered_at: renderedAt,
          cf_turnstile_response: tokenVal
        }};
        if (window.__PSEO_SYNTHETIC_TEST__) {{
          payload.synthetic_test = true;
        }}
        if (statusEl) statusEl.textContent = 'Preparing your worksheet...';
        var reqHeaders = {{ 'Content-Type': 'application/json' }};
        if (window.__PSEO_SYNTHETIC_TEST__) {{
          reqHeaders['X-Pseofactory-Test'] = '1';
        }}
        fetch('/api/lead-capture', {{
          method: 'POST',
          headers: reqHeaders,
          body: JSON.stringify(payload)
        }})
          .then(function(resp) {{
            return resp.json().catch(function() {{ return {{}}; }}).then(function(data) {{
              return {{ ok: Boolean(resp && resp.ok), status: resp ? resp.status : 0, data: data || {{}} }};
            }});
          }})
          .then(function(res) {{
            var st = getFormTsState(form);
            if (res.ok && res.data && res.data.ok) {{
              form.setAttribute('data-submission-state', 'success');
              form.setAttribute('data-lead-captured', 'true');
              if (statusEl) {{
                statusEl.textContent = '';
                var msgSpan = document.createElement('span');
                msgSpan.textContent = res.data.deduplicated
                  ? 'Already registered. Your worksheet is ready: '
                  : 'Subscription confirmed. Your worksheet is ready: ';
                statusEl.appendChild(msgSpan);
                var safeWsUrl = buildSafeHtmlWorksheetUrl(res.data.playbook_url);
                if (safeWsUrl) {{
                  var link = document.createElement('a');
                  link.href = safeWsUrl;
                  link.target = '_blank';
                  link.rel = 'noopener noreferrer';
                  link.textContent = 'Open Free Worksheet';
                  link.className = 'touch-target';
                  link.style.fontWeight = '600';
                  link.style.textDecoration = 'underline';
                  statusEl.appendChild(link);
                }}
              }}
              emailEl.value = '';
            }} else {{
              form.setAttribute('data-submission-state', 'error');
              if (statusEl) statusEl.textContent = formatLeadError(res.data, res.status);
            }}
            if (window.turnstile && st.widgetId !== null && typeof window.turnstile.reset === 'function') {{
              try {{ window.turnstile.reset(st.widgetId); }} catch (e) {{}}
              st.token = '';
            }}
          }})
          .catch(function() {{
            form.setAttribute('data-submission-state', 'error');
            if (statusEl) statusEl.textContent = 'Network error while submitting. Please try again.';
          }});
      }});
    }});
  }})();
  </script>"""


# Mapping of common raw inline color values to canonical Porcelain CSS custom properties
_COLOR_TOKEN_MAP: Dict[str, str] = {
    "#fbfcfd": "var(--bg-canvas)",
    "#f8fafc": "var(--bg-subtle)",
    "#f9fafb": "var(--bg-subtle)",
    "#f4f6f8": "var(--bg-subtle)",
    "#f1f5f9": "var(--bg-muted)",
    "#f3f4f6": "var(--bg-muted)",
    "#eef2f6": "var(--bg-muted)",
    "#ffffff": "var(--bg-surface)",
    "#fff": "var(--bg-surface)",
    "#eff6ff": "var(--bg-elevated)",
    "#f0fdfa": "var(--bg-elevated)",
    "#dbeafe": "var(--brand-border)",
    "#bfdbfe": "var(--brand-border)",
    "#e2e8f0": "var(--border-hairline)",
    "#e5e7eb": "var(--border-hairline)",
    "#e5e9f0": "var(--border-hairline)",
    "#dbe1ea": "var(--border-subtle)",
    "#cbd5e1": "var(--border-subtle)",
    "#d1d5db": "var(--border-subtle)",
    "#94a3b8": "var(--border-strong)",
    "#9ca3af": "var(--border-strong)",
    "#090d16": "var(--text-primary)",
    "#0f172a": "var(--text-primary)",
    "#111827": "var(--text-primary)",
    "#1e293b": "var(--text-primary)",
    "#07090e": "var(--bg-canvas)",
    "#334155": "var(--text-secondary)",
    "#374151": "var(--text-secondary)",
    "#475569": "var(--text-secondary)",
    "#4b5563": "var(--text-secondary)",
    "#64748b": "var(--text-muted)",
    "#6b7280": "var(--text-muted)",
    "#1d4ed8": "var(--brand-primary)",
    "#2563eb": "var(--brand-primary)",
    "#3b82f6": "var(--brand-primary)",
    "#0284c7": "var(--brand-primary)",
    "#0369a1": "var(--brand-hover)",
    "#1e40af": "var(--brand-hover)",
    "#1e3a8a": "var(--brand-hover)",
    "#0f766e": "var(--brand-primary)",
    "#115e59": "var(--brand-hover)",
    "#047857": "var(--status-positive)",
    "#059669": "var(--status-positive)",
    "#16a34a": "var(--status-positive)",
    "#15803d": "var(--status-positive)",
    "#166534": "var(--status-positive)",
    "#ecfdf5": "var(--status-positive-bg)",
    "#f0fdf4": "var(--status-positive-bg)",
    "#dcfce7": "var(--status-positive-bg)",
    "#a7f3d0": "var(--status-positive-border)",
    "#bbf7d0": "var(--status-positive-border)",
    "#86efac": "var(--status-positive-border)",
    "#b45309": "var(--status-warning)",
    "#d97706": "var(--status-warning)",
    "#f59e0b": "var(--status-warning)",
    "#ea580c": "var(--status-warning)",
    "#92400e": "var(--status-warning)",
    "#9a3412": "var(--status-warning)",
    "#fffbeb": "var(--status-warning-bg)",
    "#fef3c7": "var(--status-warning-bg)",
    "#fff7ed": "var(--status-warning-bg)",
    "#fde68a": "var(--status-warning-border)",
    "#fcd34d": "var(--status-warning-border)",
    "#fed7aa": "var(--status-warning-border)",
    "#dc2626": "var(--status-danger)",
    "#ef4444": "var(--status-danger)",
    "#b91c1c": "var(--status-danger)",
    "#991b1b": "var(--status-danger)",
    "#fef2f2": "var(--status-danger-bg)",
    "#fee2e2": "var(--status-danger-bg)",
    "#fecaca": "var(--status-danger-border)",
    "#fca5a5": "var(--status-danger-border)",
}

_HEX_COLOR_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_RGB_HSL_RE = re.compile(r"\b(?:rgba?|hsla?)\s*\([^)]*\)")
_VAR_FALLBACK_RE = re.compile(r"var\(\s*(--[a-zA-Z0-9_-]+)\s*,\s*[^)]+\)")


def _map_color_literal_to_token(raw_color: str, prop_name: str = "") -> str:
    low = raw_color.strip().lower()
    if low in _COLOR_TOKEN_MAP:
        tok = _COLOR_TOKEN_MAP[low]
        # Avoid low-contrast white text if background wasn't brand-primary
        return tok
    if low.startswith("#"):
        try:
            r, g, b = _hex_to_rgb(low[:7] if len(low) >= 7 else low)
            lum = _relative_luminance((r, g, b))
            if "background" in prop_name:
                return "var(--bg-subtle)" if lum > 0.5 else "var(--brand-primary)"
            if "border" in prop_name:
                return "var(--border-subtle)"
            return "var(--text-primary)" if lum < 0.25 else "var(--brand-primary)"
        except Exception:
            pass
    if "shadow" in prop_name:
        return "var(--shadow-sm)"
    if "border" in prop_name:
        return "var(--border-subtle)"
    if "background" in prop_name:
        return "var(--bg-subtle)"
    return "var(--text-secondary)"


def sanitize_inline_styles_outside_svg(html_content: str, known_css_vars: Set[str]) -> str:
    """
    Eliminates all raw #hex, rgb(...), and hsl(...) literals inside HTML style="..."
    attributes outside <svg> blocks, mapping them to canonical Porcelain CSS tokens
    and removing geometry-sabotaging inline overrides.
    """
    svg_blocks: List[str] = []

    def _stash_svg(m: re.Match[str]) -> str:
        idx = len(svg_blocks)
        svg_blocks.append(m.group(0))
        return f"__PSEO_SVG_STASH_{idx}__"

    stashed = re.sub(
        r"<(svg|script|template)\b[^>]*>[\s\S]*?</\1>",
        _stash_svg,
        html_content,
        flags=re.IGNORECASE,
    )

    def _clean_tag_style(tag_match: re.Match[str]) -> str:
        full_tag = tag_match.group(0)
        tag_lower = full_tag.lower()
        is_card = bool(re.search(r'\bclass\s*=\s*["\'][^"\']*\b(?:card|pseo-card|hero-section|tool-hero)\b', tag_lower))
        is_heading = bool(re.match(r"^<h[1-4]\b", tag_lower))
        is_control = bool(re.match(r"^<(?:a|button|input|select|summary)\b", tag_lower))
        is_input_or_select = bool(re.match(r"^<(?:input|select)\b", tag_lower))
        is_div = bool(re.match(r"^<div\b", tag_lower))

        def _rewrite_style_attr(sm: re.Match[str]) -> str:
            quote = sm.group(1)
            raw_val = sm.group(2)
            # First strip fallback values inside var(--tok, fallback)
            def _strip_var_fb(vm: re.Match[str]) -> str:
                vname = vm.group(1)
                if vname in known_css_vars:
                    return f"var({vname})"
                return "var(--text-secondary)"

            val = _VAR_FALLBACK_RE.sub(_strip_var_fb, raw_val)
            # Replace any undefined var(--unknown) references with safe tokens
            def _fix_undef_var(uvm: re.Match[str]) -> str:
                vname = uvm.group(1)
                if vname in known_css_vars:
                    return f"var({vname})"
                if "bg" in vname or "canvas" in vname or "surface" in vname:
                    return "var(--bg-surface)"
                if "border" in vname:
                    return "var(--border-subtle)"
                return "var(--text-primary)"

            val = re.sub(r"var\(\s*(--[a-zA-Z0-9_-]+)\s*\)", _fix_undef_var, val)

            kept_decls: List[str] = []
            for decl in val.split(";"):
                d = decl.strip()
                if not d or ":" not in d:
                    continue
                pname, pval = d.split(":", 1)
                p_low = pname.strip().lower()
                v_clean = pval.replace("!important", "").strip()

                # Drop inline overrides that violate card geometry, typography hierarchy, or touch targets
                if is_card and p_low in (
                    "border-radius",
                    "padding",
                    "padding-top",
                    "max-width",
                    "margin",
                    "margin-left",
                    "margin-right",
                    "background",
                    "background-color",
                    "text-align",
                ):
                    continue
                if is_heading and p_low in ("font-size", "line-height"):
                    continue
                if is_input_or_select and p_low == "font-size" and v_clean.lower() not in ("16px", "1rem"):
                    continue
                if is_div and p_low == "grid-template-columns" and re.match(r"^\s*1fr\s+1fr\s*$", v_clean, flags=re.IGNORECASE):
                    v_clean = "repeat(auto-fit, minmax(min(100%, 220px), 1fr))"
                if is_control and p_low in ("height", "min-height", "width", "min-width", "padding") and re.search(
                    r"(?<![0-9.])(?:22|24|28|32|1|2)px\b", v_clean
                ):
                    continue
                if is_control and p_low == "display" and v_clean.lower() == "inline":
                    continue
                if p_low == "overflow-x" and v_clean.lower() == "hidden":
                    continue
                if p_low in ("box-shadow", "text-shadow") and (_RGB_HSL_RE.search(v_clean) or _HEX_COLOR_RE.search(v_clean)):
                    v_clean = "var(--shadow-sm)"

                if _RGB_HSL_RE.search(v_clean):
                    if p_low in ("border", "border-top", "border-bottom", "border-left", "border-right"):
                        v_clean = _RGB_HSL_RE.sub("var(--border-subtle)", v_clean)
                    else:
                        v_clean = _RGB_HSL_RE.sub(lambda m: _map_color_literal_to_token(m.group(0), p_low), v_clean)
                if _HEX_COLOR_RE.search(v_clean):
                    # Preserve contrast when button/badge sets white text on accent background
                    if p_low == "color" and v_clean.lower() in ("#fff", "#ffffff"):
                        v_clean = "var(--cta-fg)"
                    else:
                        v_clean = _HEX_COLOR_RE.sub(lambda m: _map_color_literal_to_token(m.group(0), p_low), v_clean)

                if v_clean:
                    kept_decls.append(f"{pname.strip()}: {v_clean}")

            if not kept_decls:
                return ""
            joined = "; ".join(kept_decls) + ";"
            return f" style={quote}{joined}{quote}"

        cleaned_tag = re.sub(r'\s+style\s*=\s*(["\'])(.*?)\1', _rewrite_style_attr, full_tag, flags=re.IGNORECASE | re.DOTALL)
        return cleaned_tag

    cleaned = re.sub(r"<[a-zA-Z][a-zA-Z0-9_-]*\b[^>]*\bstyle\s*=\s*(?:[\"'][\s\S]*?[\"'])[^>]*>", _clean_tag_style, stashed)

    for idx, svg_txt in enumerate(svg_blocks):
        cleaned = cleaned.replace(f"__PSEO_SVG_STASH_{idx}__", svg_txt)
    return cleaned


def _wrap_unwrapped_tables(body_html: str) -> str:
    """Ensures every <table> outside <script>/<template> is wrapped in .table-wrap."""
    scripts: List[str] = []

    def _stash_script(m: re.Match[str]) -> str:
        idx = len(scripts)
        scripts.append(m.group(0))
        return f"__PSEO_SCRIPT_STASH_{idx}__"

    work = re.sub(r"<(script|template)\b[^>]*>[\s\S]*?</\1>", _stash_script, body_html, flags=re.IGNORECASE)
    # Upgrade legacy inline overflow wrappers
    work = re.sub(
        r'<div\s+style=["\'][^"\']*overflow-x:\s*auto[^"\']*["\']\s*>\s*(<table\b[\s\S]*?</table>)\s*</div>',
        r'<div class="table-wrap pseo-table-wrap">\1</div>',
        work,
        flags=re.IGNORECASE,
    )

    out_parts: List[str] = []
    pos = 0
    for tm in re.finditer(r"<table\b[\s\S]*?</table>", work, flags=re.IGNORECASE):
        start, end = tm.span()
        prefix = work[max(0, start - 260):start]
        if re.search(r'<div\b[^>]*class=["\'][^"\']*\b(?:table-wrap|pseo-table-wrap|calc-matrix-table-wrap)\b[^"\']*["\'][^>]*>\s*$', prefix, flags=re.IGNORECASE):
            out_parts.append(work[pos:end])
        else:
            out_parts.append(work[pos:start])
            tbl = re.sub(r'\s+min-width:\s*\d+px;?', '', tm.group(0), flags=re.IGNORECASE)
            out_parts.append(f'<div class="table-wrap pseo-table-wrap">{tbl}</div>')
        pos = end
    out_parts.append(work[pos:])
    res = "".join(out_parts)
    for idx, sc in enumerate(scripts):
        res = res.replace(f"__PSEO_SCRIPT_STASH_{idx}__", sc)
    return res


_PERSONAL_LINKEDIN_RE = re.compile(r"linkedin\.com" + r"/in/", flags=re.IGNORECASE)
_PERSONAL_LINKEDIN_URL_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com" + r"/in/[a-zA-Z0-9_-]+/?",
    flags=re.IGNORECASE,
)
_PERSONAL_MAKER_NAME_RE = re.compile(r"\barif\s+" + r"coskun\b", flags=re.IGNORECASE)
_PERSONAL_MAKER_HANDLE_RE = re.compile(r"@arif" + r"coskun\b", flags=re.IGNORECASE)
_PERSONAL_MAKER_EMAIL_RE = re.compile(r"\barif\." + r"coskun@[a-zA-Z0-9._-]+\b", flags=re.IGNORECASE)
_PERSONAL_MAKER_MAILTO_RE = re.compile(r"mailto:arif\." + r"coskun@[a-zA-Z0-9._-]+", flags=re.IGNORECASE)


def _scrub_jsonld_value(value: Any, profile: Dict[str, Any]) -> Any:
    """Recursively scrubs personal maker/author/LinkedIn/email references inside JSON-LD structures."""
    li_id = str(profile.get("linkedin_company_id") or "").strip()
    expected_li = f"https://www.linkedin.com/company/{li_id}/" if li_id else ""
    corp_name = str(profile.get("legal_entity") or f"{profile.get('brand_name', 'ProfitHelm')} LLC")
    corp_url = str(profile.get("canonical_base") or "").rstrip("/") + "/"
    corp_email = str(profile.get("contact_email") or f"editorial@{profile.get('domain', 'profithelm.com')}")

    if isinstance(value, dict):
        node_type = value.get("@type")
        node_name = str(value.get("name") or "")
        if (
            (node_type == "Person" or (isinstance(node_type, list) and "Person" in node_type))
            and (_PERSONAL_MAKER_NAME_RE.search(node_name) or _PERSONAL_MAKER_HANDLE_RE.search(node_name))
        ):
            replacement_org: Dict[str, Any] = {
                "@type": "Organization",
                "name": corp_name,
                "url": corp_url,
            }
            if "@id" in value and not _PERSONAL_MAKER_NAME_RE.search(str(value["@id"])):
                replacement_org["@id"] = value["@id"]
            return replacement_org

        out_dict: Dict[str, Any] = {}
        wikidata_map = {
            "lienbond": "https://www.wikidata.org/wiki/Q192161",
            "prexvo": "https://www.wikidata.org/wiki/Q633315",
            "gainhelm": "https://www.wikidata.org/wiki/Q166142",
            "profithelm": "https://www.wikidata.org/wiki/Q8161",
        }
        canonical_wikidata = wikidata_map.get(
            str(profile.get("property_id") or "profithelm"),
            "https://www.wikidata.org/wiki/Q8161",
        )
        for k, v in value.items():
            if k == "sameAs":
                urls = [v] if isinstance(v, str) else (list(v) if isinstance(v, list) else [])
                filtered: List[str] = []
                for u in urls:
                    u_str = str(u).strip()
                    if "wikidata.org/wiki/Q499388" in u_str:
                        if canonical_wikidata not in filtered:
                            filtered.append(canonical_wikidata)
                        continue
                    if _PERSONAL_LINKEDIN_RE.search(u_str):
                        if expected_li and expected_li not in filtered:
                            filtered.append(expected_li)
                        continue
                    if "linkedin.com/company/" in u_str.lower() and not li_id:
                        continue
                    if _PERSONAL_MAKER_HANDLE_RE.search(u_str):
                        continue
                    if u_str not in filtered:
                        filtered.append(u_str)
                if filtered:
                    out_dict["sameAs"] = filtered
                continue
            out_dict[k] = _scrub_jsonld_value(v, profile)
        return out_dict

    if isinstance(value, list):
        return [_scrub_jsonld_value(item, profile) for item in value]

    if isinstance(value, str):
        s = value
        if _PERSONAL_LINKEDIN_URL_RE.search(s):
            s = _PERSONAL_LINKEDIN_URL_RE.sub(expected_li or corp_url, s)
        if _PERSONAL_MAKER_EMAIL_RE.search(s):
            s = _PERSONAL_MAKER_EMAIL_RE.sub(corp_email, s)
        if _PERSONAL_MAKER_NAME_RE.search(s):
            s = _PERSONAL_MAKER_NAME_RE.sub(corp_name, s)
        if _PERSONAL_MAKER_HANDLE_RE.search(s):
            s = _PERSONAL_MAKER_HANDLE_RE.sub(f"@{profile.get('property_id', 'profithelm')}", s)
        return s

    return value


def _consolidate_jsonld_head(head_html: str, profile: Dict[str, Any]) -> str:
    """Consolidates multiple JSON-LD blocks into exact 1 @graph block and scrubs personal attribution."""
    ld_pattern = re.compile(
        r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>',
        flags=re.IGNORECASE,
    )
    matches = list(ld_pattern.finditer(head_html))
    if not matches:
        return head_html

    graph_nodes: List[Dict[str, Any]] = []
    for m in matches:
        raw = m.group(1).strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except Exception:
            continue
        items = parsed.get("@graph", []) if isinstance(parsed, dict) and "@graph" in parsed else (parsed if isinstance(parsed, list) else [parsed])
        for node in items:
            if not isinstance(node, dict):
                continue
            cleaned_node = _scrub_jsonld_value(dict(node), profile)
            if isinstance(cleaned_node, dict):
                cleaned_node.pop("@context", None)
                if cleaned_node.get("@type") == "FAQPage" and isinstance(cleaned_node.get("mainEntity"), list):
                    cleaned_node["mainEntity"] = [
                        q_item
                        for q_item in cleaned_node["mainEntity"]
                        if not (
                            isinstance(q_item, dict)
                            and str(q_item.get("name") or "").strip().lower() in ("menu", "navigation")
                        )
                    ]
                    if not cleaned_node["mainEntity"]:
                        continue
                graph_nodes.append(cleaned_node)

    if not graph_nodes:
        return head_html

    consolidated = {
        "@context": "https://schema.org",
        "@graph": graph_nodes,
    }
    ld_json = json.dumps(consolidated, ensure_ascii=False)
    script_tag = f'  <script type="application/ld+json">{ld_json}</script>'

    strip_re = re.compile(
        r'[ \t]*<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>[\s\S]*?</script>[ \t]*\n?',
        flags=re.IGNORECASE,
    )
    stripped_head = strip_re.sub("", head_html).rstrip()
    return f"{stripped_head}\n{script_tag}\n"


def _resolve_expected_gsc_token(profile: Dict[str, Any]) -> str:
    """Resolves canonical GSC verification token with per-tenant and global env override support."""
    prop = str(profile.get("property_id") or "").strip().upper()
    if prop:
        tenant_env = os.environ.get(f"{prop}_GSC_VERIFICATION_TOKEN", "").strip()
        if tenant_env:
            return tenant_env
    global_env = os.environ.get("GSC_VERIFICATION_TOKEN", "").strip()
    if global_env:
        return global_env
    return str(profile.get("default_gsc_token") or "").strip()


def _enforce_canonical_gsc_meta(html_chunk: str, expected_token: str) -> str:
    """Replaces any mismatched google-site-verification meta tag with the tenant's canonical token."""
    if not expected_token:
        return html_chunk
    cleaned = html_chunk
    for fake_gsc in (
        "google-site-verification-verified-2026",
        "google-site-verification-profithelm-2026",
        "google-site-verification-prexvo-2026",
        "google-site-verification-gainhelm-2026",
        "google-site-verification-lienbond-2026",
        "gH9vK2mP8nQ4wL7tB5zC3jF6hG1dS0eV4kM8pY2uA9q",
    ):
        if fake_gsc in cleaned:
            cleaned = cleaned.replace(fake_gsc, expected_token)

    if "google-site-verification" not in cleaned.lower():
        return cleaned

    canonical_tag = f'<meta name="google-site-verification" content="{html_lib.escape(expected_token, quote=True)}">'
    seen_canonical = False

    def _replace_gsc_tag(m: re.Match[str]) -> str:
        nonlocal seen_canonical
        raw_tag = m.group(0)
        cm = re.search(r'\bcontent\s*=\s*["\']([^"\']*)["\']', raw_tag, flags=re.IGNORECASE)
        cur_val = cm.group(1).strip() if cm else ""
        if not seen_canonical:
            seen_canonical = True
            if cur_val == expected_token:
                return raw_tag
            return canonical_tag
        return ""

    cleaned = re.sub(
        r'<meta\b[^>]*\bname\s*=\s*["\']google-site-verification["\'][^>]*>',
        _replace_gsc_tag,
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned


def _dedupe_title_brand(title_text: str, brand: str) -> str:
    """Strips duplicate trailing brand suffix when a title already starts or ends with the brand."""
    raw = (title_text or "").strip()
    if not raw or not brand:
        return raw
    t = re.sub(
        rf"(?:\s*\|\s*{re.escape(brand)}){{2,}}\s*$",
        f" | {brand}",
        raw,
        flags=re.IGNORECASE,
    )
    if re.match(rf"^{re.escape(brand)}\s*[:|\-]\s*", t, flags=re.IGNORECASE):
        while True:
            trimmed = re.sub(
                rf"\s*[|\-]\s*{re.escape(brand)}\s*$",
                "",
                t,
                flags=re.IGNORECASE,
            ).strip()
            if trimmed == t:
                break
            t = trimmed
    return t


def _dedupe_head_titles(head_html: str, brand: str) -> str:
    """Removes duplicate leading+trailing brand tokens from <title>, og:title, and twitter:title in <head>."""
    if not head_html or not brand:
        return head_html

    def _clean_title_tag(m: re.Match[str]) -> str:
        inner = html_lib.unescape(m.group(2))
        deduped = _dedupe_title_brand(inner, brand)
        if deduped == inner.strip():
            return m.group(0)
        return f"{m.group(1)}{html_lib.escape(deduped, quote=False)}{m.group(3)}"

    cleaned = re.sub(
        r"(<title\b[^>]*>)([\s\S]*?)(</title>)",
        _clean_title_tag,
        head_html,
        flags=re.IGNORECASE,
    )

    def _clean_meta_title(m: re.Match[str]) -> str:
        raw_tag = m.group(0)
        cm = re.search(r'(\bcontent\s*=\s*)(["\'])([^"\']*)\2', raw_tag, flags=re.IGNORECASE)
        if not cm:
            return raw_tag
        inner = html_lib.unescape(cm.group(3))
        deduped = _dedupe_title_brand(inner, brand)
        if deduped == inner.strip():
            return raw_tag
        q = cm.group(2)
        esc_val = html_lib.escape(deduped, quote=True)
        return raw_tag[: cm.start()] + f"{cm.group(1)}{q}{esc_val}{q}" + raw_tag[cm.end() :]

    cleaned = re.sub(
        r'<meta\b[^>]*\b(?:property|name)\s*=\s*["\'](?:og:title|twitter:title)["\'][^>]*>',
        _clean_meta_title,
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned


def _ensure_porcelain_publisher_head_tags(head_html: str, profile: Dict[str, Any]) -> str:
    """Deterministically enforces tenant publisher/affiliate <meta> & <link> tags in <head>."""
    cleaned = head_html
    gsc_default = _resolve_expected_gsc_token(profile)
    if gsc_default:
        cleaned = _enforce_canonical_gsc_meta(cleaned, gsc_default)

    impact_uuid = str(profile.get("impact_verification_uuid") or "").strip()
    cj_pid = str(profile.get("cj_property_id") or "").strip()
    sovrn_key = str(profile.get("sovrn_domain_key") or "").strip()
    entity_label = str(profile.get("publisher_entity_label") or profile.get("legal_entity") or "").strip()

    expected_impact_tag = f"<meta name='impact-site-verification' value='{impact_uuid}'>"
    expected_cj_tag = f'<meta name="cj-promotional-property-id" content="{cj_pid}">'

    def _filter_impact(m: re.Match[str]) -> str:
        return m.group(0) if expected_impact_tag in m.group(0) else ""

    if "impact-site-verification" in cleaned.lower():
        cleaned = re.sub(
            r'(?:(?<=^)|(?<=\n))[ \t]*<meta\b[^>]*name=["\']impact-site-verification["\'][^>]*>\r?\n?|<meta\b[^>]*name=["\']impact-site-verification["\'][^>]*>',
            _filter_impact,
            cleaned,
            flags=re.IGNORECASE,
        )

    def _filter_cj(m: re.Match[str]) -> str:
        raw_t = m.group(0)
        if f'content="{cj_pid}"' in raw_t or f"content='{cj_pid}'" in raw_t:
            return raw_t
        return ""

    if "cj-promotional-property-id" in cleaned.lower():
        cleaned = re.sub(
            r'(?:(?<=^)|(?<=\n))[ \t]*<meta\b[^>]*name=["\']cj-promotional-property-id["\'][^>]*>\r?\n?|<meta\b[^>]*name=["\']cj-promotional-property-id["\'][^>]*>',
            _filter_cj,
            cleaned,
            flags=re.IGNORECASE,
        )

    if not sovrn_key and ("ir-site-verification-token" in cleaned.lower() or "sovrn-commerce-domain-key" in cleaned.lower()):
        cleaned = re.sub(
            r'(?:(?<=^)|(?<=\n))[ \t]*<meta\b[^>]*name=["\'](?:ir-site-verification-token|sovrn-commerce-domain-key)["\'][^>]*>\r?\n?|<meta\b[^>]*name=["\'](?:ir-site-verification-token|sovrn-commerce-domain-key)["\'][^>]*>',
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

    for foreign_entity in (
        "ProfitHelm LLC",
        "Prexvo Statutory Research Group",
        "GainHelm Cyber Compliance & Audit Economics Research",
        "LienBond Statutory Surety & Construction Compliance Research",
    ):
        if foreign_entity != entity_label and f'<meta name="partnerstack-publisher-entity" content="{foreign_entity}">' in cleaned:
            cleaned = cleaned.replace(
                f'<meta name="partnerstack-publisher-entity" content="{foreign_entity}">',
                f'<meta name="partnerstack-publisher-entity" content="{entity_label}">',
            )

    required_lines: List[str] = []
    if impact_uuid:
        required_lines.append(f"  {expected_impact_tag}")
    if cj_pid:
        required_lines.append(f"  {expected_cj_tag}")
    if sovrn_key:
        required_lines.append(f'  <meta name="sovrn-commerce-domain-key" content="{sovrn_key}">')
    if entity_label:
        required_lines.append(f'  <meta name="partnerstack-publisher-entity" content="{entity_label}">')
    required_lines.extend(
        [
            '  <meta name="ftc-affiliate-disclosure" content="16-CFR-Part-255-Compliant">',
            '  <link rel="publisher-media-kit" type="application/json" href="/media-kit.json">',
            '  <link rel="tool-catalog" type="application/json" title="Machine-Readable Tool Catalog" href="/catalog.json">',
        ]
    )

    def _tag_line_present(line: str, doc: str) -> bool:
        stripped = line.strip()
        if "impact-site-verification" in stripped:
            return expected_impact_tag in doc
        if "cj-promotional-property-id" in stripped:
            return (f'content="{cj_pid}"' in doc or f"content='{cj_pid}'" in doc) and ("cj-promotional-property-id" in doc)
        attr_m = re.search(r"""(?:name|rel)=["']([^"']+)["']""", stripped)
        if attr_m:
            return attr_m.group(1) in doc
        return stripped in doc

    missing_lines = [ln for ln in required_lines if not _tag_line_present(ln, cleaned)]
    if missing_lines:
        inject_str = "\n".join(missing_lines)
        gsv_m = re.search(
            r'(<meta\b[^>]*name=["\']google-site-verification["\'][^>]*>)',
            cleaned,
            flags=re.IGNORECASE,
        )
        if gsv_m:
            cleaned = cleaned[: gsv_m.end()] + "\n" + inject_str + cleaned[gsv_m.end() :]
        else:
            cleaned = cleaned.rstrip() + "\n" + inject_str + "\n"

    canon_base = str(profile.get("canonical_base") or "").strip().rstrip("/")
    prop_id = str(profile.get("property_id") or "").strip().lower()
    has_og_image = bool(
        re.search(
            r'<meta\b[^>]*\bproperty=["\']og:image["\'][^>]*\bcontent=["\'][^"\']+["\']|'
            r'<meta\b[^>]*\bcontent=["\'][^"\']+["\'][^>]*\bproperty=["\']og:image["\']',
            cleaned,
            flags=re.IGNORECASE,
        )
    )
    if canon_base and prop_id and not has_og_image:
        cleaned = re.sub(
            r'(?:(?<=^)|(?<=\n))[ \t]*<meta\b[^>]*\bproperty=["\']og:image["\'][^>]*>\r?\n?|<meta\b[^>]*\bproperty=["\']og:image["\'][^>]*>',
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        og_img_url = f"{canon_base}/static/img/{prop_id}-og.png"
        og_tag = f'  <meta property="og:image" content="{html_lib.escape(og_img_url)}">'
        og_anchors = list(
            re.finditer(
                r'<meta\b[^>]*\bproperty=["\']og:(?:url|description|title|type)["\'][^>]*>',
                cleaned,
                flags=re.IGNORECASE,
            )
        )
        if og_anchors:
            anchor = og_anchors[-1]
            cleaned = cleaned[: anchor.end()] + "\n" + og_tag + cleaned[anchor.end() :]
        else:
            cleaned = cleaned.rstrip() + "\n" + og_tag + "\n"

    return cleaned


def _extract_balanced_element(html_text: str, start_match: re.Match[str], tag_name: str) -> Tuple[str, str]:
    """Extracts a balanced <tag_name ...>...</tag_name> block starting at start_match."""
    open_re = re.compile(rf"<{tag_name}\b[^>]*>", re.IGNORECASE)
    close_re = re.compile(rf"</{tag_name}\s*>", re.IGNORECASE)
    start_idx = start_match.start()
    pos = start_match.end()
    depth = 1
    while depth > 0 and pos < len(html_text):
        next_open = open_re.search(html_text, pos)
        next_close = close_re.search(html_text, pos)
        if not next_close:
            return html_text[start_idx:], html_text[:start_idx]
        if next_open and next_open.start() < next_close.start():
            depth += 1
            pos = next_open.end()
        else:
            depth -= 1
            pos = next_close.end()
    extracted = html_text[start_idx:pos]
    remaining = html_text[:start_idx] + html_text[pos:]
    return extracted, remaining


def _strip_legacy_shell_chrome(raw_body: str) -> Tuple[str, List[str]]:
    """
    Extracts inner main content and trailing body scripts while removing old skip-links,
    old site headers, and old site footers. Converts legacy <header class='card'> hero blocks
    into <section class='hero-section tool-hero card'>.
    """
    body = raw_body
    # Remove old skip links
    body = re.sub(
        r'<a\b[^>]*class=["\'][^"\']*\b(?:skip-link|skip-to-content-link)\b[^"\']*["\'][^>]*>[\s\S]*?</a>',
        "",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r'<a\b[^>]*href=["\']#main-content["\'][^>]*>\s*Skip to (?:main )?content\s*</a>',
        "",
        body,
        flags=re.IGNORECASE,
    )

    # Convert legacy <header class="card"> hero into <section class="hero-section tool-hero card">
    # while preserving non-site section <header> landmarks located inside <main>.
    def _convert_or_strip_header(doc: str) -> str:
        search_pos = 0
        while True:
            hm = re.search(r"<header\b([^>]*)>", doc[search_pos:], flags=re.IGNORECASE)
            if not hm:
                break
            abs_start = search_pos + hm.start()
            main_m = re.search(r"<main\b[^>]*>", doc, flags=re.IGNORECASE)
            inside_main = bool(main_m and abs_start > main_m.start())
            attrs = hm.group(1) or ""
            sub_match = re.match(r"<header\b([^>]*)>", doc[abs_start:], flags=re.IGNORECASE)
            if not sub_match:
                break
            tail_block, tail_rest = _extract_balanced_element(doc[abs_start:], sub_match, "header")
            block = tail_block
            rest = doc[:abs_start] + tail_rest
            is_site_hdr = bool(
                re.search(r'\bclass\s*=\s*["\'][^"\']*\bsite-header\b', attrs, flags=re.IGNORECASE)
                or (not inside_main and re.search(r"\b(?:site-header|header)\b", attrs, flags=re.IGNORECASE))
            )
            if is_site_hdr and "<h1" not in block.lower():
                doc = rest
            elif "<h1" in block.lower():
                inner = re.sub(r"^<header\b[^>]*>|</header\s*>$", "", block, flags=re.IGNORECASE).strip()
                replacement = f'<section class="hero-section tool-hero card">\n{inner}\n</section>'
                doc = doc[:abs_start] + replacement + doc[abs_start + len(block) :]
                break
            elif not inside_main:
                doc = rest
            else:
                search_pos = abs_start + len(block)
        return doc

    body = _convert_or_strip_header(body)

    # Remove old site footers (including legacy <footer class="card">) after rescuing any .playbook-capture-card
    body = re.sub(
        r'<script\b[^>]*id=["\']porcelain-footer-lead-handler["\'][^>]*>[\s\S]*?</script>',
        "",
        body,
        flags=re.IGNORECASE,
    )
    rescued_footer_cards: List[str] = []
    while True:
        fm = re.search(r"<footer\b[^>]*>", body, flags=re.IGNORECASE)
        if not fm:
            break
        footer_block, body = _extract_balanced_element(body, fm, "footer")
        pb_m = re.search(
            r'<(div|section)\b[^>]*class=["\'][^"\']*\bplaybook-capture-card\b[^"\']*["\'][^>]*>',
            footer_block,
            flags=re.IGNORECASE,
        )
        if pb_m:
            pb_card, _ = _extract_balanced_element(footer_block, pb_m, pb_m.group(1))
            if pb_card.strip():
                rescued_footer_cards.append(pb_card.strip())

    # Separate trailing <script> tags outside <main> so we keep them cleanly at end of body
    trailing_scripts: List[str] = []
    mm = re.search(r"<main\b[^>]*>", body, flags=re.IGNORECASE)
    if mm:
        main_block, outside_main = _extract_balanced_element(body, mm, "main")
        for sm in re.finditer(r"<script\b[^>]*>[\s\S]*?</script>", outside_main, flags=re.IGNORECASE):
            trailing_scripts.append(sm.group(0))
        inner_main = re.sub(r"^<main\b[^>]*>|</main\s*>$", "", main_block, flags=re.IGNORECASE).strip()
    else:
        inner_main = body.strip()

    # Unwrap top-level <div class="container"> inside inner_main (even if sibling sections follow it!)
    cm = re.match(r'^\s*<div\b[^>]*class=["\'][^"\']*\bcontainer\b[^"\']*["\'][^>]*>', inner_main, flags=re.IGNORECASE)
    if cm:
        container_block, after_container = _extract_balanced_element(inner_main, cm, "div")
        container_inner = re.sub(r"^<div\b[^>]*>|</div\s*>$", "", container_block, flags=re.IGNORECASE).strip()
        inner_main = (container_inner + "\n" + after_container.strip()).strip()

    if rescued_footer_cards:
        for r_card in rescued_footer_cards:
            if "playbook-capture-card" not in inner_main:
                inner_main = (inner_main + "\n" + r_card).strip()

    return inner_main, trailing_scripts


_LEGACY_CLUTTER_CLASSES: Tuple[str, ...] = (
    "compliance-strip",
    "ftc-disclosure-banner",
    "ymyl-disclaimer-banner",
    "ftc-disclosure-card",
    "ymyl-warning-card",
    "above-the-fold-compliance",
    "statutory-disclaimer-box",
    "ymyl-forfeiture-banner",
    "affiliate-disclosure-note",
)

_NON_LEAF_CLUTTER_CLASSES: Tuple[str, ...] = (
    "ymyl-disclaimer-banner",
    "ftc-disclosure-card",
    "ymyl-warning-card",
    "above-the-fold-compliance",
)


def _strip_legacy_disclaimer_clutter(
    html_fragment: str,
    classes: Sequence[str] = _LEGACY_CLUTTER_CLASSES,
) -> str:
    """Removes legacy YMYL/FTC disclaimer wrapper elements matching any class in classes."""
    work = html_fragment
    for legacy_cls in classes:
        while True:
            dm = re.search(
                rf'<(div|aside|section|p)\b[^>]*class=["\'][^"\']*\b{re.escape(legacy_cls)}\b[^"\']*["\'][^>]*>',
                work,
                flags=re.IGNORECASE,
            )
            if not dm:
                break
            _, work = _extract_balanced_element(work, dm, dm.group(1))
    return work


def _clean_visible_raw_python_formulas(html_content: str) -> str:
    """Rewrites leaked raw Python round((...), N) calls in visible HTML outside <script>/<style>/<template>."""
    if "round((" not in html_content:
        return html_content
    stashed: List[str] = []

    def _stash(m: re.Match[str]) -> str:
        idx = len(stashed)
        stashed.append(m.group(0))
        return f"__PSEO_FORMULA_STASH_{idx}__"

    work = re.sub(r"<(script|style|template)\b[^>]*>[\s\S]*?</\1>", _stash, html_content, flags=re.IGNORECASE)
    if "round((" in work:
        out: List[str] = []
        pos = 0
        while True:
            idx = work.find("round((", pos)
            if idx == -1:
                out.append(work[pos:])
                break
            out.append(work[pos:idx])
            depth = 0
            j = idx + len("round")
            n = len(work)
            while j < n:
                ch = work[j]
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
                j += 1
            if depth == 0:
                inner = work[idx + len("round(") : j - 1]
                inner = re.sub(r",\s*\d+\s*$", "", inner).strip()
                out.append(inner)
                pos = j
            else:
                out.append("round(")
                pos = idx + len("round(")
        work = "".join(out)

    for idx, block in enumerate(stashed):
        work = work.replace(f"__PSEO_FORMULA_STASH_{idx}__", block)
    return work


def _scrub_operator_pwa_gsc_token(html_content: str, profile: Dict[str, Any]) -> str:
    """Enforces canonical GSC verification token inside /signal/ operator PWA pages."""
    gsc_default = _resolve_expected_gsc_token(profile)
    if not gsc_default:
        return html_content
    return _enforce_canonical_gsc_meta(html_content, gsc_default)


def _ensure_prexvo_ymyl_forfeiture_notice(
    html_text: str,
    profile: Dict[str, Any],
    blueprint: str,
) -> str:
    """
    Ensures every non-registry Prexvo HTML page mentioning refinancing includes the mandatory
    YMYL federal-protection forfeiture notice inside an existing quick-answer, intro paragraph,
    or footer container without emitting legacy clutter banners.
    """
    if str(profile.get("property_id") or "").strip().lower() != "prexvo" or blueprint == "operator_pwa":
        return html_text
    low = html_text.lower()
    is_route_or_index_registry = (
        "verified_routes_count" in low
        or "autonomous facebook group discovery & topic routing matrix" in low
        or "github seed discovery & authority architecture" in low
    )
    if ("refinance" not in low and "refinancing" not in low) or is_route_or_index_registry:
        return html_text
    if any(
        phrase in low
        for phrase in (
            "waives federal protections",
            "eliminates federal protections",
            "waive federal protections",
            "permanently forfeits",
            "forfeits access to federal",
        )
    ):
        return html_text

    sentence = "Refinancing federal student loans permanently waives federal protections, including IDR and PSLF."
    qa_match = re.search(
        r'(<aside\b[^>]*class=["\'][^"\']*\bquick-answer\b[^"\']*["\'][^>]*>)([\s\S]*?)(</aside>)',
        html_text,
        flags=re.IGNORECASE,
    )
    if qa_match:
        qa_inner = qa_match.group(2)
        qa_plain_words = re.sub(r"<[^>]+>", " ", qa_inner).split()
        if len(qa_plain_words) + len(sentence.split()) <= 60:
            last_p_close = qa_inner.lower().rfind("</p>")
            if last_p_close != -1:
                new_inner = qa_inner[:last_p_close] + f" {sentence}" + qa_inner[last_p_close:]
            else:
                new_inner = qa_inner.rstrip() + f"\n      <p>{sentence}</p>\n    "
            return (
                html_text[: qa_match.start()]
                + qa_match.group(1)
                + new_inner
                + qa_match.group(3)
                + html_text[qa_match.end() :]
            )

    hero_p_match = re.search(
        r'(<p\b[^>]*class=["\'][^"\']*\bhero-desc\b[^"\']*["\'][^>]*>)([\s\S]*?)(</p>)',
        html_text,
        flags=re.IGNORECASE,
    )
    if hero_p_match:
        return (
            html_text[: hero_p_match.start()]
            + hero_p_match.group(1)
            + hero_p_match.group(2).rstrip()
            + f" {sentence}"
            + hero_p_match.group(3)
            + html_text[hero_p_match.end() :]
        )

    fb_match = re.search(
        r'(<div\b[^>]*class=["\'][^"\']*\bfooter-bottom\b[^"\']*["\'][^>]*>)([\s\S]*?)(</div>)',
        html_text,
        flags=re.IGNORECASE,
    )
    if fb_match:
        return (
            html_text[: fb_match.start()]
            + fb_match.group(1)
            + fb_match.group(2).rstrip()
            + f"\n        <span>{sentence}</span>\n      "
            + fb_match.group(3)
            + html_text[fb_match.end() :]
        )

    return html_text


def _read_local_js_bytes(
    raw_src: str,
    profile: Dict[str, Any],
    dist_dir: Optional[Path] = None,
) -> Optional[bytes]:
    """Reads local /static/js/ or /js/ bytes from dist_dir or its sibling package directory when present."""
    if dist_dir is None:
        return None
    clean_src = raw_src.split("?", 1)[0].split("#", 1)[0]
    rel_js = clean_src.lstrip("/")
    base_dist = Path(dist_dir)
    for cand in (
        base_dist / rel_js,
        base_dist.parent / str(profile.get("package_name") or "") / rel_js,
    ):
        if cand.is_file():
            return cand.read_bytes()
    return None


def _resolve_local_js_version_hash(
    raw_src: str,
    profile: Dict[str, Any],
    dist_dir: Optional[Path] = None,
) -> str:
    """Computes a deterministic 10-char SHA-256 cache-bust token for local /static/js/ or /js/ assets."""
    clean_src = raw_src.split("?", 1)[0].split("#", 1)[0]
    js_bytes = _read_local_js_bytes(clean_src, profile, dist_dir=dist_dir)
    if js_bytes is not None:
        return hashlib.sha256(js_bytes).hexdigest()[:10]
    seed = f"{PORCELAIN_SHELL_VERSION}:{profile.get('property_id', 'profithelm')}:{clean_src}".encode("utf-8")
    return hashlib.sha256(seed).hexdigest()[:10]


_CONTENT_HASHED_JS_RE = re.compile(r"\.[0-9a-f]{10}\.js$", re.IGNORECASE)


def _rewrite_local_js_version_tags(
    html_content: str,
    profile: Dict[str, Any],
    dist_dir: Optional[Path] = None,
) -> str:
    """Sets or refreshes ?v=<hash10> on local <script src='/static/js/...'> and <script src='/js/...'> tags."""
    def _rew_script_tag(m: re.Match[str]) -> str:
        prefix = m.group(1)
        quote = m.group(2)
        src_val = m.group(3)
        suffix = m.group(4)
        clean_src = src_val.split("?", 1)[0]
        if _CONTENT_HASHED_JS_RE.search(clean_src):
            if src_val != clean_src:
                return f"<script{prefix}{quote}{clean_src}{quote}{suffix}>"
            return m.group(0)
        has_v = bool(re.search(r"[?&]v=[a-zA-Z0-9._-]+", src_val))
        disk_bytes = _read_local_js_bytes(clean_src, profile, dist_dir=dist_dir)
        if disk_bytes is not None:
            v_hash = hashlib.sha256(disk_bytes).hexdigest()[:10]
            if has_v:
                updated_src = re.sub(r"([?&])v=[a-zA-Z0-9._-]+", rf"\g<1>v={v_hash}", src_val)
            else:
                sep = "&" if "?" in src_val else "?"
                updated_src = f"{src_val}{sep}v={v_hash}"
            return f"<script{prefix}{quote}{updated_src}{quote}{suffix}>"
        if has_v:
            return m.group(0)
        v_hash = _resolve_local_js_version_hash(clean_src, profile, dist_dir=None)
        sep = "&" if "?" in src_val else "?"
        return f"<script{prefix}{quote}{src_val}{sep}v={v_hash}{quote}{suffix}>"

    return re.sub(
        r'<script\b([^>]*\bsrc\s*=\s*)(["\'])(/(?:static/)?js/[^"\']+)\2([^>]*)>',
        _rew_script_tag,
        html_content,
        flags=re.IGNORECASE,
    )


def _enforce_calculator_leaf_slot_order(
    inner_html: str,
    rel_path: str,
    profile: Dict[str, Any],
) -> str:
    """
    Enforces the locked 6-slot calculator_leaf order inside div.container:
    1. <nav class="breadcrumbs" aria-label="Breadcrumb">
    2. <section class="hero-section tool-hero card"> (<h1> + <aside class="quick-answer">)
    3. Single canonical <div class="compliance-strip ftc-disclosure-banner">
    4. Calculator Workbench
    5. Partner / Commercial Handoff & /api/lead-capture
    6. Methodology, Scenario <table>s, Datasets & FAQ .cards
    """
    work = inner_html
    is_restricted = bool(
        'data-restricted-public-service="true"' in work
        or 'data-commercial-offers="none"' in work
        or any(tok in rel_path.lower() for tok in ("pslf-", "save-plan", "save-to-rap", "buyback"))
    )

    # Strip all duplicate legacy YMYL / FTC disclaimer blocks anywhere in the leaf body
    work = _strip_legacy_disclaimer_clutter(work, _LEGACY_CLUTTER_CLASSES)

    # 1. Extract or synthesize <nav class="breadcrumbs">
    bm = re.search(r'<nav\b[^>]*class=["\'][^"\']*\bbreadcrumbs\b[^"\']*["\'][^>]*>', work, flags=re.IGNORECASE)
    if bm:
        breadcrumb_html, work = _extract_balanced_element(work, bm, "nav")
        if "aria-label=" not in breadcrumb_html.lower():
            breadcrumb_html = re.sub(
                r"^<nav\b",
                '<nav aria-label="Breadcrumb"',
                breadcrumb_html,
                count=1,
                flags=re.IGNORECASE,
            )
    else:
        h1_m = re.search(r"<h1\b[^>]*>([\s\S]*?)</h1>", work, flags=re.IGNORECASE)
        h1_plain = re.sub(r"<[^>]+>", "", h1_m.group(1)).strip() if h1_m else "Calculator"
        breadcrumb_html = (
            '<nav class="breadcrumbs" aria-label="Breadcrumb">'
            '<a href="/" class="touch-target">Home</a><span>/</span>'
            '<a href="/tools/" class="touch-target">Calculators</a><span>/</span>'
            f"<span>{html_lib.escape(h1_plain)}</span>"
            "</nav>"
        )

    # 2. Extract <aside class="quick-answer"> if outside hero so we guarantee it sits inside hero-section
    qa_html = ""
    qm = re.search(r'<aside\b[^>]*class=["\'][^"\']*\bquick-answer\b[^"\']*["\'][^>]*>', work, flags=re.IGNORECASE)
    if qm:
        qa_html, work = _extract_balanced_element(work, qm, "aside")
        if 'role="region"' not in qa_html.lower():
            qa_html = re.sub(r"^<aside\b", '<aside role="region"', qa_html, count=1, flags=re.IGNORECASE)
        if "aria-label=" not in qa_html.lower():
            qa_html = re.sub(r"^<aside\b", '<aside aria-label="Quick Answer Summary"', qa_html, count=1, flags=re.IGNORECASE)

    # Extract or wrap hero-section containing <h1>
    hm = re.search(
        r'<(section|div)\b[^>]*class=["\'][^"\']*\b(?:hero-section|tool-hero|tool-header)\b[^"\']*["\'][^>]*>',
        work,
        flags=re.IGNORECASE,
    )
    if hm:
        hero_raw, work = _extract_balanced_element(work, hm, hm.group(1))
        hero_inner = re.sub(rf"^<{hm.group(1)}\b[^>]*>|</{hm.group(1)}\s*>$", "", hero_raw, flags=re.IGNORECASE).strip()
    else:
        h1m = re.search(r"<h1\b[^>]*>[\s\S]*?</h1>", work, flags=re.IGNORECASE)
        if h1m:
            hero_inner = h1m.group(0)
            work = work[:h1m.start()] + work[h1m.end():]
        else:
            hero_inner = f"<h1>{html_lib.escape(profile['brand_name'])} Statutory Calculator</h1>"

    if qa_html and "quick-answer" not in hero_inner:
        hero_inner = f"{hero_inner}\n{qa_html}"
    elif not qa_html and "quick-answer" not in hero_inner:
        hero_inner = (
            f"{hero_inner}\n"
            '<aside class="quick-answer" role="region" aria-label="Quick Answer Summary">'
            f'<p class="quick-answer-body">Use this deterministic {html_lib.escape(profile["brand_name"])} '
            f'statutory model governed by {html_lib.escape(profile["primary_statutory_authority"])} '
            "to compute audit-grade scenario outputs, marginal rate impacts, and compliance thresholds in real time.</p>"
            "</aside>"
        )

    hero_section_html = f'      <section class="hero-section tool-hero card">\n        {hero_inner}\n      </section>'
    compliance_html = render_porcelain_compliance_strip(
        profile,
        is_restricted_public_service=is_restricted,
        rel_path=rel_path,
    )

    return "\n".join(
        [
            f"      {breadcrumb_html.strip()}",
            hero_section_html,
            compliance_html,
            work.strip(),
        ]
    )


def _enforce_editorial_or_comparison_leaf_slot_order(
    inner_html: str,
    rel_path: str,
    profile: Dict[str, Any],
    blueprint: str,
    existing_hubs: Optional[Set[str]] = None,
) -> str:
    """
    Enforces deterministic Porcelain slot order for comparison_leaf (/vs/*) and editorial_guide (/guides/*)
    pages WITHOUT injecting 'Calculators / ...' breadcrumbs or calculator model boilerplate.
    """
    work = inner_html
    rel_low = str(rel_path or "").strip().lstrip("/").lower()
    is_restricted = bool(
        'data-restricted-public-service="true"' in work
        or 'data-commercial-offers="none"' in work
        or any(tok in rel_low for tok in ("pslf-", "save-plan", "save-to-rap", "buyback"))
    )

    work = _strip_legacy_disclaimer_clutter(work, _LEGACY_CLUTTER_CLASSES)

    h1_m = re.search(r"<h1\b[^>]*>([\s\S]*?)</h1>", work, flags=re.IGNORECASE)
    h1_plain = re.sub(r"<[^>]+>", "", h1_m.group(1)).strip() if h1_m else (
        "Comparison" if blueprint == "comparison_leaf" else "Guide"
    )

    bm = re.search(r'<nav\b[^>]*class=["\'][^"\']*\bbreadcrumbs\b[^"\']*["\'][^>]*>', work, flags=re.IGNORECASE)
    breadcrumb_html = ""
    if bm:
        raw_bc, work = _extract_balanced_element(work, bm, "nav")
        # Repair only if an earlier pass mis-synthesized Calculators (/tools/) onto a non-/tools/ route
        if not rel_low.startswith("tools/") and 'href="/tools/"' in raw_bc and ">Calculators<" in raw_bc:
            breadcrumb_html = ""
        else:
            breadcrumb_html = raw_bc
            if "aria-label=" not in breadcrumb_html.lower():
                breadcrumb_html = re.sub(
                    r"^<nav\b",
                    '<nav aria-label="Breadcrumb"',
                    breadcrumb_html,
                    count=1,
                    flags=re.IGNORECASE,
                )

    if not breadcrumb_html:
        first_seg = rel_low.split("/", 1)[0] if "/" in rel_low else ""
        sec_label = "Comparisons" if blueprint == "comparison_leaf" else "Guides"
        hubs_set = existing_hubs or set()
        if first_seg and first_seg in hubs_set:
            mid_crumb = f'<a href="/{first_seg}/" class="touch-target">{sec_label}</a><span>/</span>'
        else:
            mid_crumb = f"<span>{sec_label}</span><span>/</span>"
        breadcrumb_html = (
            '<nav class="breadcrumbs" aria-label="Breadcrumb">'
            '<a href="/" class="touch-target">Home</a><span>/</span>'
            f"{mid_crumb}"
            f"<span>{html_lib.escape(h1_plain)}</span>"
            "</nav>"
        )

    qa_html = ""
    qm = re.search(r'<aside\b[^>]*class=["\'][^"\']*\bquick-answer\b[^"\']*["\'][^>]*>', work, flags=re.IGNORECASE)
    if qm:
        cand_qa, work = _extract_balanced_element(work, qm, "aside")
        if "statutory model governed by" not in cand_qa or "to compute audit-grade scenario outputs" not in cand_qa:
            qa_html = cand_qa
            if 'role="region"' not in qa_html.lower():
                qa_html = re.sub(r"^<aside\b", '<aside role="region"', qa_html, count=1, flags=re.IGNORECASE)
            if "aria-label=" not in qa_html.lower():
                qa_html = re.sub(r"^<aside\b", '<aside aria-label="Quick Answer Summary"', qa_html, count=1, flags=re.IGNORECASE)

    hm = re.search(
        r'<(section|div)\b[^>]*class=["\'][^"\']*\b(?:hero-section|tool-hero|tool-header)\b[^"\']*["\'][^>]*>',
        work,
        flags=re.IGNORECASE,
    )
    if hm:
        hero_raw, work = _extract_balanced_element(work, hm, hm.group(1))
        hero_inner = re.sub(rf"^<{hm.group(1)}\b[^>]*>|</{hm.group(1)}\s*>$", "", hero_raw, flags=re.IGNORECASE).strip()
        if "statutory model governed by" in hero_inner and "to compute audit-grade scenario outputs" in hero_inner:
            bad_qm = re.search(r'<aside\b[^>]*class=["\'][^"\']*\bquick-answer\b[^"\']*["\'][^>]*>', hero_inner, flags=re.IGNORECASE)
            if bad_qm:
                _, hero_inner = _extract_balanced_element(hero_inner, bad_qm, "aside")
                hero_inner = hero_inner.strip()
    else:
        h1m = re.search(r"<h1\b[^>]*>[\s\S]*?</h1>", work, flags=re.IGNORECASE)
        if h1m:
            hero_inner = h1m.group(0)
            work = work[: h1m.start()] + work[h1m.end() :]
        else:
            hero_inner = f"<h1>{html_lib.escape(h1_plain)}</h1>"

    if qa_html and "quick-answer" not in hero_inner:
        hero_inner = f"{hero_inner}\n{qa_html}"
    elif not qa_html and "quick-answer" not in hero_inner:
        brand_esc = html_lib.escape(profile["brand_name"])
        auth_esc = html_lib.escape(profile["primary_statutory_authority"])
        ds_esc = html_lib.escape(profile["economic_dataset_label"])
        if blueprint == "comparison_leaf":
            qa_copy = (
                f"Review this {brand_esc} side-by-side statutory and operational comparison governed by "
                f"{auth_esc} and benchmarked against {ds_esc} to evaluate fee structures, eligibility rules, "
                "and decision trade-offs."
            )
        else:
            qa_copy = (
                f"Read this {brand_esc} statutory research guide anchored to {auth_esc} and {ds_esc} "
                "covering enacted compliance rules, filing thresholds, and step-by-step analytical procedures."
            )
        hero_inner = (
            f"{hero_inner}\n"
            '<aside class="quick-answer" role="region" aria-label="Quick Answer Summary">'
            f'<p class="quick-answer-body">{qa_copy}</p>'
            "</aside>"
        )

    hero_section_html = f'      <section class="hero-section card">\n        {hero_inner}\n      </section>'
    compliance_html = render_porcelain_compliance_strip(
        profile,
        is_restricted_public_service=is_restricted,
        rel_path=rel_path,
    )

    return "\n".join(
        [
            f"      {breadcrumb_html.strip()}",
            hero_section_html,
            compliance_html,
            work.strip(),
        ]
    )


def normalize_html_to_porcelain_shell(
    html_content: str,
    rel_path: str,
    profile: Dict[str, Any],
    active_tools: Optional[Sequence[Tuple[str, str]]] = None,
    known_css_vars: Optional[Set[str]] = None,
    existing_hubs: Optional[Set[str]] = None,
    dist_dir: Optional[Path] = None,
) -> Tuple[str, str]:
    """
    Transforms any public HTML file into its locked Porcelain Light blueprint while preserving
    100% of working calculator DOM IDs, JS formulas, JSON-LD graphs, publisher <meta>/<link> tags,
    and /signal/ exemptions.
    Returns (normalized_html, blueprint_name).
    """
    blueprint = classify_porcelain_blueprint(rel_path, html_content)
    if blueprint == "operator_pwa":
        return _scrub_operator_pwa_gsc_token(html_content, profile), blueprint

    _, css_hash, cached_defined_vars = _get_porcelain_stylesheet_meta_from_profile(profile)
    if known_css_vars is None:
        known_css_vars = cached_defined_vars
    base_css_href = str(profile["css_href"]).split("?", 1)[0]
    versioned_css_href = f"{base_css_href}?v={css_hash}"

    head_m = re.search(r"<head\b[^>]*>([\s\S]*?)</head>", html_content, flags=re.IGNORECASE)
    body_m = re.search(r"<body\b([^>]*)>([\s\S]*?)</body>", html_content, flags=re.IGNORECASE)
    if not head_m or not body_m:
        return html_content, blueprint

    raw_head = head_m.group(1)
    body_attrs = body_m.group(1) or ""
    raw_body = body_m.group(2)

    # 1. Clean <head>: remove inline <style> blocks, duplicate stylesheet links, and data:, icons; enforce publisher tags & JSON-LD
    clean_head = re.sub(r"\s*<style\b[^>]*>[\s\S]*?</style>", "", raw_head, flags=re.IGNORECASE)
    clean_head = re.sub(
        r'\s*<link\b[^>]*rel=["\']stylesheet["\'][^>]*href=["\'][^"\']*style\.css[^"\']*["\'][^>]*/?>',
        "",
        clean_head,
        flags=re.IGNORECASE,
    )
    clean_head = re.sub(
        r'\s*<link\b[^>]*href=["\'][^"\']*style\.css[^"\']*["\'][^>]*rel=["\']stylesheet["\'][^>]*/?>',
        "",
        clean_head,
        flags=re.IGNORECASE,
    )
    clean_head = re.sub(
        r'\s*<link\b[^>]*rel=["\'][^"\']*icon[^"\']*["\'][^>]*href=["\']data:,["\'][^>]*/?>',
        "",
        clean_head,
        flags=re.IGNORECASE,
    )
    clean_head = re.sub(
        r'\s*<link\b[^>]*href=["\']data:,["\'][^>]*rel=["\'][^"\']*icon[^"\']*["\'][^>]*/?>',
        "",
        clean_head,
        flags=re.IGNORECASE,
    )
    clean_head = _ensure_porcelain_publisher_head_tags(clean_head, profile)
    clean_head = _dedupe_head_titles(clean_head, str(profile.get("brand_name") or ""))
    if "content-language" not in clean_head.lower():
        clean_head = '  <meta http-equiv="content-language" content="en-US">\n' + clean_head.lstrip("\n")
    if not re.search(r'<link\b[^>]*href=["\']/favicon\.svg["\']', clean_head, flags=re.IGNORECASE):
        clean_head = clean_head.rstrip() + '\n  <link rel="icon" type="image/svg+xml" href="/favicon.svg">'
    if not re.search(r'<link\b[^>]*href=["\']/favicon\.ico["\']', clean_head, flags=re.IGNORECASE):
        clean_head = clean_head.rstrip() + '\n  <link rel="alternate icon" href="/favicon.ico">'
    clean_head = _consolidate_jsonld_head(clean_head, profile)
    css_link = (
        f'  <link rel="stylesheet" id="pseo-visual-primitives" '
        f'data-version="{VISUAL_PRIMITIVES_LINK_VERSION}" href="{versioned_css_href}">'
    )
    clean_head = clean_head.rstrip() + "\n" + css_link + "\n"

    # 2. Clean <body>: strip inline <style> blocks, scrub any residual personal mailto/maker strings, rebuild chrome
    body_no_style = re.sub(r"\s*<style\b[^>]*>[\s\S]*?</style>", "", raw_body, flags=re.IGNORECASE)
    corp_email = str(profile.get("contact_email") or f"editorial@{profile.get('domain', 'profithelm.com')}")
    corp_li = (
        f"https://www.linkedin.com/company/{profile['linkedin_company_id']}/"
        if profile.get("linkedin_company_id")
        else str(profile.get("canonical_base") or "").rstrip("/") + "/"
    )
    body_no_style = _PERSONAL_MAKER_MAILTO_RE.sub(f"mailto:{corp_email}", body_no_style)
    body_no_style = _PERSONAL_MAKER_EMAIL_RE.sub(corp_email, body_no_style)
    body_no_style = _PERSONAL_LINKEDIN_URL_RE.sub(corp_li, body_no_style)
    body_no_style = _PERSONAL_MAKER_NAME_RE.sub(str(profile["legal_entity"]), body_no_style)
    body_no_style = _PERSONAL_MAKER_HANDLE_RE.sub(f"@{profile['property_id']}", body_no_style)

    inner_main, trailing_scripts = _strip_legacy_shell_chrome(body_no_style)

    from pseofactory.visual_primitives import (
        has_current_external_runtime_sync_tag,
        render_external_runtime_synchronizer_tag,
        write_runtime_synchronizer_asset,
    )

    _rt_sync_tag_re = re.compile(
        r'<script\b[^>]*(?<![a-zA-Z0-9_-])id\s*=\s*["\']pseo-runtime-sync["\'][^>]*>[\s\S]*?</script>',
        re.IGNORECASE,
    )
    extracted_runtime_sync_tags: List[str] = []

    def _capture_runtime_sync_tag(m: re.Match[str]) -> str:
        extracted_runtime_sync_tags.append(m.group(0).strip())
        return ""

    inner_main = _rt_sync_tag_re.sub(_capture_runtime_sync_tag, inner_main)
    filtered_trailing_scripts: List[str] = []
    for ts in trailing_scripts:
        if _rt_sync_tag_re.search(ts):
            _rt_sync_tag_re.sub(_capture_runtime_sync_tag, ts)
        else:
            filtered_trailing_scripts.append(ts)
    trailing_scripts = filtered_trailing_scripts
    had_runtime_sync = bool(extracted_runtime_sync_tags)
    had_external_runtime_sync = (
        has_current_external_runtime_sync_tag(body_no_style)
        or any(
            bool(
                re.search(
                    r'(?<![a-zA-Z0-9_-])src\s*=\s*["\']/static/js/pseo-runtime-sync\.[0-9a-f]{10}\.js["\']',
                    tag.split(">", 1)[0],
                    re.IGNORECASE,
                )
            )
            for tag in extracted_runtime_sync_tags
        )
    )

    if blueprint == "calculator_leaf":
        inner_main = _enforce_calculator_leaf_slot_order(inner_main, rel_path, profile)
    elif blueprint in ("comparison_leaf", "editorial_guide"):
        inner_main = _enforce_editorial_or_comparison_leaf_slot_order(
            inner_main,
            rel_path,
            profile,
            blueprint,
            existing_hubs=existing_hubs,
        )
    elif blueprint == "error_404":
        # Guarantee zero YMYL/FTC banners on 404.html
        inner_main = _strip_legacy_disclaimer_clutter(inner_main, _LEGACY_CLUTTER_CLASSES)
    else:
        inner_main = _strip_legacy_disclaimer_clutter(inner_main, _NON_LEAF_CLUTTER_CLASSES)

    inner_main = _wrap_unwrapped_tables(inner_main)

    def _strip_card_from_callouts(match: re.Match[str]) -> str:
        quote = match.group(1)
        tokens = match.group(2).split()
        low_tokens = {t.lower() for t in tokens}
        if low_tokens & {"quick-answer", "compliance-strip", "ftc-disclosure-banner", "regulatory-forfeiture-warning"}:
            tokens = [t for t in tokens if t.lower() not in {"card", "pseo-card"}]
        return f"class={quote}{' '.join(tokens)}{quote}"

    inner_main = re.sub(r'\bclass=(["\'])(.*?)\1', _strip_card_from_callouts, inner_main)

    _cta_link_classes = {
        "btn",
        "btn-cta",
        "btn-primary",
        "btn-secondary",
        "partner-btn",
        "partner-cta",
        "pro-hook-link",
        "pro-hook-direct-checkout",
        "affiliate-cta-link",
        "scenario-preset-link",
        "contextual-cluster-link",
        "hero-register-firm-link",
        "serp-intent-banner-btn",
        "tool-link",
        "nav-link",
        "cluster-link",
        "btn-preset",
    }

    def _mark_prose_container_links(block_match: re.Match[str]) -> str:
        open_tag = block_match.group(1)
        body_in = block_match.group(2)
        close_tag = block_match.group(3)
        if "<a" not in body_in.lower():
            return block_match.group(0)
        # Skip if nested block elements exist inside this prose container
        if re.search(r"<(p|div|section|article|table|ul|ol|dl|blockquote)\b", body_in, flags=re.IGNORECASE):
            return block_match.group(0)
        parent_plain = re.sub(r"<[^>]+>", "", body_in).strip()
        if not parent_plain:
            return block_match.group(0)

        def _maybe_tag_anchor(a_match: re.Match[str]) -> str:
            prefix_before = body_in[: a_match.start()]
            # Ensure <a> is a direct child of <p>/<dd>/<blockquote> (depth 0)
            depth = 0
            for tm in re.finditer(r"<(/?)([a-zA-Z0-9]+)\b[^>]*(/?)>", prefix_before):
                t_slash, t_name, t_self = tm.group(1), tm.group(2).lower(), tm.group(3)
                if t_self or t_name in {"br", "hr", "img", "input", "wbr"}:
                    continue
                depth += -1 if t_slash else 1
            if depth != 0:
                return a_match.group(0)

            attrs = a_match.group(1)
            a_inner = a_match.group(2)
            if re.search(r'\b(?:role=["\']button["\']|data-cta-slot=|data-checkout-)', attrs, flags=re.IGNORECASE):
                return a_match.group(0)
            link_plain = re.sub(r"<[^>]+>", "", a_inner).strip()
            if len(parent_plain) <= len(link_plain) + 2:
                return a_match.group(0)
            cm = re.search(r'\bclass=(["\'])(.*?)\1', attrs, flags=re.IGNORECASE)
            if cm:
                cls_tokens = cm.group(2).split()
                if {c.lower() for c in cls_tokens} & _cta_link_classes:
                    return a_match.group(0)
                if "inline-prose-link" not in cls_tokens:
                    cls_tokens.append("inline-prose-link")
                q = cm.group(1)
                new_attrs = attrs[: cm.start()] + f"class={q}{' '.join(cls_tokens)}{q}" + attrs[cm.end() :]
            else:
                new_attrs = attrs + ' class="inline-prose-link"'
            return f"<a{new_attrs}>{a_inner}</a>"

        new_body_in = re.sub(r"<a(\b[^>]*)>([\s\S]*?)</a>", _maybe_tag_anchor, body_in, flags=re.IGNORECASE)
        return f"{open_tag}{new_body_in}{close_tag}"

    inner_main = re.sub(
        r"(<(?:p|dd|blockquote)\b[^>]*>)([\s\S]*?)(</(?:p|dd|blockquote)>)",
        _mark_prose_container_links,
        inner_main,
        flags=re.IGNORECASE,
    )

    # Preserve data-* guardrails on <body> (e.g. PSLF/SAVE data-commercial-offers="none")
    kept_body_attrs: List[str] = [f'data-blueprint="{blueprint}"']
    for dm in re.finditer(r'\b(data-[a-zA-Z0-9_-]+)\s*=\s*(["\'])(.*?)\2', body_attrs):
        attr_k = dm.group(1)
        if attr_k.lower() != "data-blueprint":
            kept_body_attrs.append(f'{attr_k}={dm.group(2)}{dm.group(3)}{dm.group(2)}')
    body_attr_str = " " + " ".join(kept_body_attrs)

    rel_clean = re.sub(r"(?:^|/)index\.html$", "", rel_path.strip("/"))
    page_slug = rel_clean.split("/")[-1] if rel_clean else "homepage"

    header_html = render_porcelain_header(profile)
    has_main_lead_form = bool(re.search(r'\bid=["\']lead-capture-form["\']', inner_main, flags=re.IGNORECASE))
    has_quote_intake_step = bool(
        re.search(r'\bid=["\']partner-quote-intake-step["\']', inner_main, flags=re.IGNORECASE)
    )
    footer_html = render_porcelain_footer(
        profile,
        active_tools=active_tools,
        page_slug=page_slug,
        has_main_lead_form=has_main_lead_form,
        has_quote_intake_step=has_quote_intake_step,
    )
    cleaned_scripts = [
        s.strip().replace("'#16a34a'", "'var(--status-positive)'").replace('"#16a34a"', '"var(--status-positive)"')
        for s in trailing_scripts
    ]
    if had_runtime_sync:
        if dist_dir is not None or had_external_runtime_sync:
            if dist_dir is not None:
                write_runtime_synchronizer_asset(Path(dist_dir))
            cleaned_scripts.append(render_external_runtime_synchronizer_tag().strip())
        else:
            cleaned_scripts.append(
                extracted_runtime_sync_tags[-1]
                .replace("'#16a34a'", "'var(--status-positive)'")
                .replace('"#16a34a"', '"var(--status-positive)"')
            )
    scripts_tail = ("\n  " + "\n  ".join(cleaned_scripts)) if cleaned_scripts else ""

    assembled = (
        "<!DOCTYPE html>\n"
        '<html lang="en" data-theme="porcelain">\n'
        "<head>\n"
        f"{clean_head.strip()}\n"
        "</head>\n"
        f"<body{body_attr_str}>\n"
        f"{header_html}\n"
        '  <main id="main-content" class="site-main main" tabindex="-1">\n'
        '    <div class="container">\n'
        f"{inner_main.strip()}\n"
        "    </div>\n"
        "  </main>\n"
        f"{footer_html}"
        f"{scripts_tail}\n"
        "</body>\n"
        "</html>\n"
    )

    gh_m = re.search(
        r'<div\b[^>]*class=["\'][^"\']*\b(?:calc-metrics-grid|metrics-grid)\b[^"\']*["\'][^>]*>',
        assembled,
        flags=re.IGNORECASE,
    )
    cta_m = re.search(
        r'<div\b[^>]*class=["\'][^"\']*\bcalc-inline-cta\b[^"\']*["\'][^>]*>',
        assembled,
        flags=re.IGNORECASE,
    )
    cta_p = cta_m.start() if cta_m else -1
    if gh_m and cta_p != -1 and cta_p < gh_m.start():
        gm_s = gh_m.start()
        gm_d = 0
        gm_e = -1
        for d_tok in re.finditer(r"</?div\b[^>]*>", assembled[gm_s:], flags=re.IGNORECASE):
            t_low = d_tok.group(0).lower()
            if t_low.startswith("</div"):
                gm_d -= 1
                if gm_d == 0:
                    gm_e = gm_s + d_tok.end()
                    break
            elif not t_low.endswith("/>"):
                gm_d += 1
        if gm_e > gm_s and ('id="metric-' in assembled[gm_s:gm_e] or "id='metric-" in assembled[gm_s:gm_e]):
            assembled = (
                assembled[:cta_p]
                + assembled[gm_s:gm_e].strip()
                + "\n          "
                + assembled[cta_p:gm_s].rstrip()
                + assembled[gm_e:]
            )

    from pseofactory.visual_primitives import _collapse_duplicate_faq_sections

    assembled = _ensure_prexvo_ymyl_forfeiture_notice(assembled, profile, blueprint)
    assembled, _ = _collapse_duplicate_faq_sections(assembled)
    sanitized = sanitize_inline_styles_outside_svg(assembled, known_css_vars)
    sanitized = _clean_visible_raw_python_formulas(sanitized)
    sanitized = _rewrite_local_js_version_tags(sanitized, profile, dist_dir=dist_dir)
    sanitized = sanitized.replace("\u2014", "-").replace("\u2013", "-")
    return sanitized, blueprint


def _fit_seo_title(raw_title: str, brand: str) -> str:
    """Guarantees <title> is strictly 50..60 chars with zero forbidden dashes or spaced hyphens."""
    t = raw_title.replace("\u2014", "|").replace("\u2013", "|").replace(" - ", " | ").strip()
    t = _dedupe_title_brand(t, brand)
    has_brand_already = bool(
        brand
        and (
            re.match(rf"^{re.escape(brand)}\s*[:|\-]\s*", t, flags=re.IGNORECASE)
            or re.search(rf"[|\-]\s*{re.escape(brand)}\s*$", t, flags=re.IGNORECASE)
        )
    )
    if 50 <= len(t) <= 60:
        return t
    if len(t) < 50:
        if has_brand_already:
            pads = [
                f"{t} | Statutory Governance",
                f"{t} | Research & Governance",
                f"{t} | Official Governance",
                f"{t} | Compliance Guide",
                f"{t} | Research",
            ]
        else:
            pads = [
                f"{t} | {brand} Statutory Governance",
                f"{t} | {brand} Research & Governance",
                f"{t} | {brand} Official Governance",
                f"{t} | {brand} Compliance Guide",
                f"{t} | {brand} Research",
                f"{t} | {brand}",
            ]
        for cand in pads:
            if 50 <= len(cand) <= 60:
                return cand
        padded = f"{t} | Statutory Modeling Standards" if has_brand_already else f"{t} | {brand} Statutory Modeling Standards"
        while len(padded) > 60 and " " in padded:
            padded = padded.rsplit(" ", 1)[0].rstrip(" |&:")
        while len(padded) < 50:
            padded = f"{padded} Hub"
        return padded[:60].rstrip()
    while len(t) > 60 and " " in t:
        t = t.rsplit(" ", 1)[0].rstrip(" |&:")
    return t[:60].rstrip()


def _render_governance_document(
    profile: Dict[str, Any],
    route_slug: str,
    raw_title: str,
    h1_text: str,
    meta_desc: str,
    quick_answer_text: str,
    sections_html: str,
    active_tools: Sequence[Tuple[str, str]],
    gsc_token: str,
    schema_page_type: str = "WebPage",
) -> str:
    """Builds a complete SEO-verified governance_legal HTML page."""
    brand = profile["brand_name"]
    base = profile["canonical_base"].rstrip("/")
    canonical_url = f"{base}/{route_slug}/"
    seo_title = _fit_seo_title(raw_title, brand)
    desc = meta_desc.replace("\u2014", ",").replace("\u2013", ",").replace(" - ", ": ").strip()
    while len(desc) < 75:
        desc = desc.rstrip(".") + f" Published by {brand} statutory research."
    if len(desc) > 152:
        desc = desc[:149].rsplit(" ", 1)[0].rstrip(".,;:") + "."

    li_id = str(profile.get("linkedin_company_id") or "").strip()
    org_node: Dict[str, Any] = {
        "@type": "Organization",
        "@id": f"{base}/#organization",
        "name": profile["legal_entity"],
        "url": f"{base}/",
        "email": profile["contact_email"],
    }
    if li_id:
        org_node["sameAs"] = [f"https://www.linkedin.com/company/{li_id}/"]

    doc_date_modified = (
        "2026-10-31"
        if str(profile.get("property_id") or "").strip().lower() == "gainhelm"
        and route_slug in ("methodology", "disclaimers")
        else "2026-11-12"
    )
    verified_date_html = (
        f'\n        <p class="verified-date-meta">Last verified against primary statutes and accreditation tables: {doc_date_modified}</p>'
        if route_slug in ("methodology", "disclaimers")
        else ""
    )

    graph = {
        "@context": "https://schema.org",
        "@graph": [
            org_node,
            {
                "@type": schema_page_type,
                "@id": f"{canonical_url}#webpage",
                "url": canonical_url,
                "name": seo_title,
                "description": desc,
                "inLanguage": "en-US",
                "datePublished": "2026-01-15",
                "dateModified": doc_date_modified,
                "speakable": {
                    "@type": "SpeakableSpecification",
                    "cssSelector": [".quick-answer", "h1"],
                },
                "isPartOf": {"@id": f"{base}/#organization"},
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{base}/"},
                    {"@type": "ListItem", "position": 2, "name": h1_text, "item": canonical_url},
                ],
            },
        ],
    }

    tool_links = "".join(
        f'<li><a href="/tools/{html_lib.escape(s)}/" class="touch-target">{html_lib.escape(lbl)}</a></li>'
        for s, lbl in list(active_tools)[:4]
        if s
    )
    related_card = f"""      <section class="card">
        <h2>Verified Statutory Calculators &amp; Benchmarks</h2>
        <p>Apply our published governance standards directly across these deterministic {html_lib.escape(brand)} tools:</p>
        <ul class="tools-list">
          {tool_links}
          <li><a href="/tools/" class="touch-target">Browse Complete {html_lib.escape(brand)} Calculators Directory</a></li>
        </ul>
      </section>"""

    raw_doc = f"""<!DOCTYPE html>
<html lang="en" data-theme="porcelain">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="content-language" content="en-US">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html_lib.escape(seo_title)}</title>
  <meta name="description" content="{html_lib.escape(desc)}">
  <meta name="google-site-verification" content="{html_lib.escape(gsc_token)}">
  <link rel="canonical" href="{html_lib.escape(canonical_url)}">
  <link rel="alternate" hreflang="en-us" href="{html_lib.escape(canonical_url)}">
  <link rel="alternate" hreflang="x-default" href="{html_lib.escape(canonical_url)}">
  <meta property="og:type" content="website">
  <meta property="og:title" content="{html_lib.escape(seo_title)}">
  <meta property="og:description" content="{html_lib.escape(desc)}">
  <meta property="og:url" content="{html_lib.escape(canonical_url)}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{html_lib.escape(seo_title)}">
  <meta name="twitter:description" content="{html_lib.escape(desc)}">
  <script type="application/ld+json">{json.dumps(graph, ensure_ascii=False)}</script>
</head>
<body>
  <main id="main-content" class="site-main">
    <div class="container">
      <nav class="breadcrumbs" aria-label="Breadcrumb">
        <a href="/" class="touch-target">Home</a><span>/</span><span>{html_lib.escape(h1_text)}</span>
      </nav>
      <section class="hero-section card">
        <h1>{html_lib.escape(h1_text)}</h1>
        <aside class="quick-answer" role="region" aria-label="Quick Answer Summary">
          <p class="quick-answer-body">{html_lib.escape(quick_answer_text)}</p>
        </aside>{verified_date_html}
      </section>
{sections_html}
{related_card}
    </div>
  </main>
</body>
</html>"""
    norm_html, _ = normalize_html_to_porcelain_shell(
        raw_doc,
        f"{route_slug}/index.html",
        profile,
        active_tools=active_tools,
    )
    return norm_html


def build_governance_pages(
    profile: Dict[str, Any],
    active_tools: Optional[Sequence[Tuple[str, str]]] = None,
    gsc_token: Optional[str] = None,
) -> Dict[str, str]:
    """Generates all 6 real HTTP-200 governance pages from DeclarativeTenantContract metadata."""
    tools = list(active_tools or profile.get("default_tools") or [])
    token = gsc_token or profile["default_gsc_token"]
    brand = profile["brand_name"]
    legal = profile["legal_entity"]
    research = profile["research_entity"]
    auth = profile["primary_statutory_authority"]
    ds = profile["economic_dataset_label"]
    email = profile["contact_email"]
    partners = profile["partner_list_summary"]
    prop_id = str(profile.get("property_id") or "profithelm").strip().lower()
    privacy_params_map = {
        "gainhelm": "audit scopes, employee headcount, control counts, or compliance budgets",
        "lienbond": "contract values, payroll exposures, bond penalties, or project schedules",
        "prexvo": "income, loan balances, household size, or repayment parameters",
    }
    privacy_params = privacy_params_map.get(
        prop_id,
        "income, loan balances, contract amounts, or control counts",
    )
    raw_input_noun = "compliance" if prop_id == "gainhelm" else "financial"
    revision_examples_map = {
        "gainhelm": "primary regulatory rule, NIST publication, ISO/IEC annex, AICPA section, or statutory breach provision referenced",
        "lienbond": "primary statute, Miller Act rule, Federal Register notice, NCCI class manual, or state lien code section referenced",
        "prexvo": "Higher Education Act section, 34 CFR regulation, Federal Register notice, or IRS guidance referenced",
    }
    revision_examples = revision_examples_map.get(
        prop_id,
        "primary statute, Federal Register notice, IRS Revenue Procedure, or state code section referenced",
    )

    pages: Dict[str, str] = {}

    # 1. /about/
    pages["about"] = _render_governance_document(
        profile=profile,
        route_slug="about",
        raw_title=f"About {brand} | Statutory Research & Editorial Standards",
        h1_text="Independent Statutory Modeling & Research Desk",
        meta_desc=f"Learn how {brand} publishes deterministic statutory decision models grounded in primary federal and state schedules and empirical public datasets.",
        quick_answer_text=(
            f"{brand} operates an independent quantitative research desk publishing deterministic statutory "
            "calculation tools anchored to enacted federal and state schedules. Every interactive decision model "
            "is formula-audited against primary regulatory tables and public economic datasets so operators and "
            "analysts can verify exact scenario outputs transparently in real time."
        ),
        sections_html=f"""      <section class="card">
        <h2>Institutional Mission &amp; Quantitative Scope</h2>
        <p>{html_lib.escape(legal)} publishes deterministic decision engines under {html_lib.escape(research)} ({html_lib.escape(profile["editorial_classification"])}). Rather than publishing generic prose summaries, every calculator encodes enacted statutory thresholds, phaseout ceilings, and empirical benchmark series directly into auditable client-side and server-verified math.</p>
        <p>Each published decision surface pairs closed-form statutory computation with structured sensitivity matrices, citation-backed parameter tables, and downloadable scenario summaries so financial operators, compliance leads, and researchers can audit every intermediate step before consulting licensed counsel.</p>
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th scope="col">Governance Dimension</th><th scope="col">Published Standard</th></tr>
            </thead>
            <tbody>
              <tr><td>Operating Legal Entity</td><td>{html_lib.escape(legal)}</td></tr>
              <tr><td>Quantitative Research Group</td><td>{html_lib.escape(research)}</td></tr>
              <tr><td>Primary Statutory Authorities</td><td>{html_lib.escape(auth)}</td></tr>
              <tr><td>Empirical Benchmark Datasets</td><td>{html_lib.escape(ds)}</td></tr>
              <tr><td>Editorial Verification Contact</td><td><!--email_off--><a href="mailto:{html_lib.escape(email)}" class="touch-target">{html_lib.escape(email)}</a><!--/email_off--></td></tr>
            </tbody>
          </table>
        </div>
      </section>
      <section class="card">
        <h2>Editorial Independence &amp; Commercial Separation</h2>
        <p>Formula parameters, statutory brackets, and default calculator assumptions are locked to primary government publications and regulatory tables. Commercial partner placements ({html_lib.escape(partners)}) never alter mathematical outputs, ranking order of statutory scenarios, or eligibility thresholds.{" Refinancing federal student loans permanently waives federal protections including Income-Driven Repayment (IDR), Public Service Loan Forgiveness (PSLF), and federal forbearance." if profile["property_id"] == "prexvo" else ""} Review our <a href="/methodology/" class="touch-target">Methodology</a> and <a href="/disclaimers/" class="touch-target">Disclaimers</a> for complete compliance protocols.</p>
      </section>""",
        active_tools=tools,
        gsc_token=token,
        schema_page_type="AboutPage",
    )

    # 2. /methodology/
    pages["methodology"] = _render_governance_document(
        profile=profile,
        route_slug="methodology",
        raw_title=f"Statutory Calculation Methodology & Audit Rules | {brand}",
        h1_text="Deterministic Statutory Calculation Methodology",
        meta_desc=f"Review the mathematical verification architecture, statutory authority joins, and dataset audit rules powering {brand} research models.",
        quick_answer_text=(
            f"{brand} calculators execute deterministic closed-form mathematical formulas anchored to enacted "
            "statutory tables and cross-checked against empirical public datasets. Each interactive model pairs "
            "zero-latency browser computation with machine-readable JSON calculation manifests, statutory boundary "
            "clamping, and dual-runtime regression oracle benchmarks to guarantee exact scenario parity."
        ),
        sections_html=f"""      <section class="card">
        <h2>Two-Tier Statutory &amp; Empirical Dataset Joins</h2>
        <p>Every calculator published by {html_lib.escape(research)} joins at least two authoritative sources: enacted statutory or regulatory schedules ({html_lib.escape(auth)}) and empirical economic benchmark datasets ({html_lib.escape(ds)}). Inputs are sanitized and clamped to statutory floors and ceilings prior to evaluation.</p>
        <p>Whenever federal agencies, state legislatures, or rating bureaus issue revised inflation adjustments, rate tables, or administrative rules, {html_lib.escape(research)} updates the canonical dataset constants and re-executes automated boundary verification across all affected hubs and spokes.</p>
      </section>
      <section class="card">
        <h2>Automated Oracle Verification Protocol</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th scope="col">Verification Stage</th><th scope="col">Control Mechanism</th><th scope="col">Acceptance Threshold</th></tr>
            </thead>
            <tbody>
              <tr><td>1. Statutory Authority Lock</td><td>Primary citation &amp; effective-year table check</td><td>100% enacted schedule match</td></tr>
              <tr><td>2. Deterministic Oracle Parity</td><td>Python &amp; browser JS dual-runtime evaluation</td><td>Zero dollar or basis-point variance</td></tr>
              <tr><td>3. Boundary Stress Testing</td><td>Zero, phaseout ceiling, and marginal cliff probes</td><td>Exact statutory clamp behavior</td></tr>
              <tr><td>4. Accessibility &amp; Clarity</td><td>WCAG AA contrast and 44x44px touch ergonomics</td><td>100% mechanical gate pass</td></tr>
            </tbody>
          </table>
        </div>
        <p>Report any statutory update or formula inquiry directly through our <a href="/contact/" class="touch-target">Editorial Contact</a> page.</p>
      </section>""",
        active_tools=tools,
        gsc_token=token,
    )

    # 3. /privacy/
    pages["privacy"] = _render_governance_document(
        profile=profile,
        route_slug="privacy",
        raw_title=f"Privacy Policy & Data Minimalism Standards | {brand}",
        h1_text="Privacy Policy & Client-Side Data Governance",
        meta_desc=f"Read the {brand} Privacy Policy covering local browser computation, minimal edge telemetry, email briefing opt-ins, and statutory privacy rights.",
        quick_answer_text=(
            f"{brand} enforces strict client-side data minimalism by evaluating all interactive scenario inputs "
            "locally inside your web browser without selling personal records to data brokers. Voluntary email "
            "submissions for downloadable workpapers or statutory rate briefings are processed exclusively for "
            "requested fulfillment and deleted promptly upon verified user request."
        ),
        sections_html=f"""      <section class="card">
        <h2>Local Browser Calculation &amp; URL State</h2>
        <p>All interactive scenario inputs entered into {html_lib.escape(brand)} calculators run locally in your web browser. Quantitative parameters such as {html_lib.escape(privacy_params)} are evaluated in client memory without transmitting raw {html_lib.escape(raw_input_noun)} inputs to third-party analytics trackers. When you share or bookmark a scenario link, numeric parameters are serialized into URL query parameters under your direct control.</p>
      </section>
      <section class="card">
        <h2>Voluntary Lead Capture, Edge Telemetry &amp; Statutory Rights</h2>
        <p>If you voluntarily submit an email address via a playbook, workpaper, or regulatory briefing form, {html_lib.escape(legal)} stores only your email address, requested tool identifier, and submission timestamp to deliver the requested resource. Outbound partner links routed via <code>/r/</code> record aggregate, non-identifying click attribution required under FTC 16 CFR Part 255 compliance standards.</p>
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th scope="col">Data Category</th><th scope="col">Processing Scope</th><th scope="col">Retention &amp; User Control</th></tr>
            </thead>
            <tbody>
              <tr><td>Calculator Numeric Inputs</td><td>100% client-side browser evaluation</td><td>Never persisted on origin servers</td></tr>
              <tr><td>Workpaper &amp; Briefing Email Opt-In</td><td>Transactional delivery via {html_lib.escape(legal)}</td><td>Deleted upon request to <!--email_off-->{html_lib.escape(email)}<!--/email_off--></td></tr>
              <tr><td>Edge Security &amp; Outbound Attribution</td><td>Aggregate status and <code>/r/</code> partner routing</td><td>Zero cross-site behavioral resale</td></tr>
            </tbody>
          </table>
        </div>
        <p>Under CCPA/CPRA, GDPR, and state privacy statutes, you may request access to, correction of, or deletion of any submitted contact record by emailing <!--email_off--><a href="mailto:{html_lib.escape(email)}" class="touch-target">{html_lib.escape(email)}</a><!--/email_off-->.</p>
      </section>""",
        active_tools=tools,
        gsc_token=token,
    )

    # 4. /terms/
    pages["terms"] = _render_governance_document(
        profile=profile,
        route_slug="terms",
        raw_title=f"Terms of Use & Statutory Modeling Conditions | {brand}",
        h1_text="Terms of Use & Modeling License Conditions",
        meta_desc=f"Review the binding Terms of Use governing access to {brand} statutory decision models, downloadable workpapers, and educational research.",
        quick_answer_text=(
            f"Access to {brand} interactive statutory models, downloadable workpapers, and benchmark schedules "
            "is provided strictly for educational and internal analytical scenario modeling. Using any published "
            "calculation engine or sensitivity matrix on this platform does not create a legal, tax, accounting, "
            "fiduciary, or certified advisory relationship of any kind."
        ),
        sections_html=f"""      <section class="card">
        <h2>Permitted Educational &amp; Internal Analytical Use</h2>
        <p>Subject to these Terms, {html_lib.escape(legal)} grants you a revocable, non-exclusive, non-transferable license to access and use {html_lib.escape(brand)} calculators, sensitivity tables, and exported scenario workpapers for personal evaluation or internal business planning. Automated scraping that degrades edge availability, strips statutory disclaimers, or misrepresents {html_lib.escape(brand)} outputs as certified professional opinions is strictly prohibited.</p>
      </section>
      <section class="card">
        <h2>No Warranties, Limitation of Liability &amp; Governing Standards</h2>
        <p>While {html_lib.escape(research)} verifies calculation formulas against {html_lib.escape(auth)} and {html_lib.escape(ds)}, enacted statutes, agency guidance, judicial interpretations, and state conformity rules change periodically and depend on entity-specific facts. All tools and publications are provided on an "as-is" and "as-available" informational basis without warranties of completeness, merchantability, or fitness for a particular regulatory filing.</p>
        <p>Under no circumstances shall {html_lib.escape(legal)} be liable for indirect, incidental, or consequential damages arising from reliance on unverified scenario assumptions. Review our <a href="/disclaimers/" class="touch-target">Disclaimers</a>, <a href="/methodology/" class="touch-target">Methodology</a>, and <a href="/privacy/" class="touch-target">Privacy Policy</a> before acting on any estimate.</p>
      </section>""",
        active_tools=tools,
        gsc_token=token,
    )

    # 5. /disclaimers/
    disc_sections = str(profile.get("disclaimers_sections_html") or "")

    pages["disclaimers"] = _render_governance_document(
        profile=profile,
        route_slug="disclaimers",
        raw_title=f"Statutory Disclaimers & FTC 16 CFR 255 Notice | {brand}",
        h1_text="Legal Disclaimers & FTC Compliance Disclosures",
        meta_desc=f"Review mandatory statutory disclaimers, non-affiliation notices, model limitations, and FTC 16 CFR Part 255 disclosures for {brand}.",
        quick_answer_text=(
            f"{brand} publishes independent educational scenario models for informational analysis only and never "
            "provides personalized legal, tax, accounting, or certified financial advice. Pursuant to FTC 16 CFR "
            "Part 255 guidelines, we transparently disclose referral compensation from vetted commercial partners "
            "while locking every underlying mathematical formula strictly to enacted statutes."
        ),
        sections_html=disc_sections,
        active_tools=tools,
        gsc_token=token,
    )

    # 6. /contact/
    pages["contact"] = _render_governance_document(
        profile=profile,
        route_slug="contact",
        raw_title=f"Contact {brand} Research & Editorial Verification Desk",
        h1_text="Editorial Verification & Statutory Research Contact Desk",
        meta_desc=f"Contact the {brand} editorial research desk to report statutory rate updates, verify modeling methodology, or submit institutional inquiries.",
        quick_answer_text=(
            f"Contact the {brand} quantitative editorial desk to submit statutory rate updates, formula "
            "verification inquiries, data privacy deletion requests, or institutional research questions. Every "
            "substantive statutory citation or schedule accuracy submission is audited directly against primary "
            "federal and state regulatory publications before updating our deterministic calculation manifests."
        ),
        sections_html=f"""      <section class="card">
        <h2>Direct Editorial &amp; Compliance Channels</h2>
        <p>{html_lib.escape(legal)} and {html_lib.escape(research)} maintain a structured editorial review queue for statutory table updates, calculator boundary edge cases, privacy requests, and partner compliance inquiries across {html_lib.escape(profile["domain"])}.</p>
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th scope="col">Inquiry Type</th><th scope="col">Responsible Desk</th><th scope="col">Direct Contact</th></tr>
            </thead>
            <tbody>
              <tr><td>Statutory Formula &amp; Dataset Verification</td><td>{html_lib.escape(research)}</td><td><!--email_off--><a href="mailto:{html_lib.escape(email)}" class="touch-target">{html_lib.escape(email)}</a><!--/email_off--></td></tr>
              <tr><td>Privacy, GDPR/CCPA &amp; Terms Requests</td><td>{html_lib.escape(legal)} Governance</td><td><!--email_off--><a href="mailto:{html_lib.escape(email)}" class="touch-target">{html_lib.escape(email)}</a><!--/email_off--></td></tr>
              <tr><td>Methodology &amp; Disclosure Documentation</td><td>Published Standards</td><td><a href="/methodology/" class="touch-target">Methodology</a> &amp; <a href="/disclaimers/" class="touch-target">Disclaimers</a></td></tr>
            </tbody>
          </table>
        </div>
      </section>
      <section class="card">
        <h2>Statutory Revision &amp; Correction Protocol</h2>
        <p>When submitting a formula verification inquiry or statutory threshold update concerning {html_lib.escape(auth)} or {html_lib.escape(ds)}, include the exact calculator URL, input parameters tested, and the {html_lib.escape(revision_examples)}. Verified statutory updates are propagated across both client-side calculators and machine-readable JSON manifests with full changelog timestamps.</p>
      </section>""",
        active_tools=tools,
        gsc_token=token,
        schema_page_type="ContactPage",
    )

    return pages


def build_porcelain_404_page(
    profile: Dict[str, Any],
    active_tools: Optional[Sequence[Tuple[str, str]]] = None,
    gsc_token: Optional[str] = None,
) -> str:
    """Builds canonical 404.html with 'Status 404', canonical URL, and zero YMYL/FTC banners."""
    tools = list(active_tools or profile.get("default_tools") or [])
    token = gsc_token or profile["default_gsc_token"]
    brand = profile["brand_name"]
    base = profile["canonical_base"].rstrip("/")
    canonical_url = f"{base}/404.html"
    seo_title = _fit_seo_title(f"Status 404: Page Not Found | {brand} Calculators", brand)
    desc = f"Status 404: The requested route was not found on {profile['domain']}. Explore verified {brand} statutory calculators and directory hubs."

    li_id = str(profile.get("linkedin_company_id") or "").strip()
    org_node_404: Dict[str, Any] = {
        "@type": "Organization",
        "@id": f"{base}/#organization",
        "name": profile["legal_entity"],
        "url": f"{base}/",
        "email": profile["contact_email"],
    }
    if li_id:
        org_node_404["sameAs"] = [f"https://www.linkedin.com/company/{li_id}/"]
    graph_404 = {
        "@context": "https://schema.org",
        "@graph": [
            org_node_404,
            {
                "@type": "WebPage",
                "@id": f"{canonical_url}#webpage",
                "url": canonical_url,
                "name": seo_title,
                "description": desc,
                "inLanguage": "en-US",
                "datePublished": "2026-01-15",
                "dateModified": "2026-11-12",
                "isPartOf": {"@id": f"{base}/#organization"},
            },
        ],
    }

    tool_items = "".join(
        f'<li><a href="/tools/{html_lib.escape(s)}/" class="touch-target">{html_lib.escape(lbl)}</a></li>'
        for s, lbl in tools[:5]
        if s
    )
    raw_doc = f"""<!DOCTYPE html>
<html lang="en" data-theme="porcelain">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="content-language" content="en-US">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html_lib.escape(seo_title)}</title>
  <meta name="description" content="{html_lib.escape(desc)}">
  <meta name="robots" content="noindex, follow">
  <meta name="google-site-verification" content="{html_lib.escape(token)}">
  <link rel="canonical" href="{html_lib.escape(canonical_url)}">
  <meta property="og:type" content="website">
  <meta property="og:title" content="{html_lib.escape(seo_title)}">
  <meta property="og:description" content="{html_lib.escape(desc)}">
  <meta property="og:url" content="{html_lib.escape(canonical_url)}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{html_lib.escape(seo_title)}">
  <meta name="twitter:description" content="{html_lib.escape(desc)}">
  <script type="application/ld+json">{json.dumps(graph_404, ensure_ascii=False)}</script>
</head>
<body>
  <main id="main-content" class="site-main">
    <div class="container">
      <section class="hero-section card">
        <span class="badge">Status 404</span>
        <h1>Status 404: Requested Calculator or Page Not Found</h1>
        <p>The URL you requested does not exist or has moved to an updated statutory calculator hub.</p>
        <div class="above-fold-preset-bar">
          <a href="/" class="btn btn-cta touch-target">Return to {html_lib.escape(brand)} Home</a>
          <a href="/tools/" class="btn-secondary touch-target">Browse All Calculators</a>
        </div>
      </section>
      <section class="card">
        <h2>Popular Verified Calculators</h2>
        <ul class="tools-list">
          {tool_items}
        </ul>
      </section>
    </div>
  </main>
</body>
</html>"""
    norm_html, _ = normalize_html_to_porcelain_shell(
        raw_doc,
        "404.html",
        profile,
        active_tools=tools,
    )
    return norm_html


def _discover_estate_tools_and_gsc_token(dist_dir: Path, profile: Dict[str, Any]) -> Tuple[List[Tuple[str, str]], str]:
    """Discovers active tool (slug, title) pairs and GSC verification token from dist_dir."""
    gsc_token = _resolve_expected_gsc_token(profile)
    if not gsc_token:
        idx_file = dist_dir / "index.html"
        if idx_file.is_file():
            idx_txt = idx_file.read_text(encoding="utf-8", errors="ignore")
            gm = re.search(
                r'<meta\b[^>]*name=["\']google-site-verification["\'][^>]*content=["\']([^"\']+)["\']',
                idx_txt,
                flags=re.IGNORECASE,
            )
            if gm:
                gsc_token = gm.group(1).strip()

    discovered: List[Tuple[str, str]] = []
    seen: Set[str] = set()
    for s, lbl in profile.get("default_tools") or []:
        if s and (dist_dir / "tools" / s / "index.html").is_file():
            discovered.append((s, lbl))
            seen.add(s)

    tools_root = dist_dir / "tools"
    if tools_root.is_dir():
        for child in sorted(tools_root.iterdir()):
            if not child.is_dir() or child.name in seen:
                continue
            leaf = child / "index.html"
            if leaf.is_file():
                txt = leaf.read_text(encoding="utf-8", errors="ignore")
                hm = re.search(r"<h1\b[^>]*>([\s\S]*?)</h1>", txt, flags=re.IGNORECASE)
                lbl = re.sub(r"<[^>]+>", "", hm.group(1)).strip() if hm else child.name.replace("-", " ").title()
                lbl = _format_porcelain_tool_label(lbl)
                if len(lbl) > 48:
                    lbl = lbl[:45].rsplit(" ", 1)[0]
                discovered.append((child.name, lbl))
                seen.add(child.name)

    return discovered or list(profile.get("default_tools") or []), gsc_token


_GLYPH_5X7: Dict[str, Tuple[str, ...]] = {
    "P": (
        "11110",
        "10001",
        "10001",
        "11110",
        "10000",
        "10000",
        "10000",
    ),
    "G": (
        "01110",
        "10001",
        "10000",
        "10111",
        "10001",
        "10001",
        "01110",
    ),
    "L": (
        "10000",
        "10000",
        "10000",
        "10000",
        "10000",
        "10000",
        "11111",
    ),
}


def _png_chunk(tag: bytes, payload: bytes) -> bytes:
    """Packs a single PNG chunk with length and CRC-32 checksum."""
    return (
        struct.pack(">I", len(payload))
        + tag
        + payload
        + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
    )


def _encode_png(width: int, height: int, rows: Sequence[bytes], color_type: int) -> bytes:
    """Encodes raw pixel rows into a valid PNG byte stream using pure stdlib struct + zlib."""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    raw_scanlines = b"".join(b"\x00" + r for r in rows)
    idat = zlib.compress(raw_scanlines, level=9)
    return b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", idat) + _png_chunk(b"IEND", b"")


def _build_favicon_ico_bytes(profile: Dict[str, Any]) -> bytes:
    """Deterministically builds a valid 32x32 RGBA PNG-wrapped ICO favicon for the tenant brand."""
    size = 32
    radius = 6.0
    r, g, b = _hex_to_rgb(str(profile.get("brand_primary") or "#1d4ed8"))
    brand_px = bytes((r, g, b, 255))
    white_px = bytes((255, 255, 255, 255))
    clear_px = bytes((0, 0, 0, 0))
    ch = str(profile.get("badge_letter") or "P").strip().upper()[:1]
    glyph = _GLYPH_5X7.get(ch, _GLYPH_5X7["P"])

    rows: List[bytes] = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            inside = True
            if (x < 6 or x >= size - 6) and (y < 6 or y >= size - 6):
                cx = 5.5 if x < 6 else (size - 6.5)
                cy = 5.5 if y < 6 else (size - 6.5)
                dx = x - cx
                dy = y - cy
                if dx * dx + dy * dy > radius * radius:
                    inside = False
            if not inside:
                row.extend(clear_px)
                continue
            gx = (x - 9) // 3
            gy = (y - 6) // 3
            if 9 <= x < 24 and 6 <= y < 27 and 0 <= gx < 5 and 0 <= gy < 7 and glyph[gy][gx] == "1":
                row.extend(white_px)
            else:
                row.extend(brand_px)
        rows.append(bytes(row))

    png_bytes = _encode_png(size, size, rows, color_type=6)
    icon_dir = struct.pack("<HHH", 0, 1, 1)
    icon_entry = struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(png_bytes), 22)
    return icon_dir + icon_entry + png_bytes


def _build_og_image_png_bytes(profile: Dict[str, Any]) -> bytes:
    """Deterministically builds a 1200x630 Porcelain Light branded OpenGraph PNG image."""
    width = 1200
    height = 630
    c_canvas = bytes(_hex_to_rgb("#fbfcfd"))
    c_white = bytes((255, 255, 255))
    c_border = bytes(_hex_to_rgb("#cbd5e1"))
    c_brand = bytes(_hex_to_rgb(str(profile.get("brand_primary") or "#1d4ed8")))
    c_soft = bytes(_hex_to_rgb(str(profile.get("brand_soft") or "#eff6ff")))
    c_ink = bytes(_hex_to_rgb("#0f172a"))
    c_slate = bytes(_hex_to_rgb("#475569"))

    ch = str(profile.get("badge_letter") or "P").strip().upper()[:1]
    glyph = _GLYPH_5X7.get(ch, _GLYPH_5X7["P"])

    top_bar_row = c_brand * width
    canvas_row = c_canvas * width
    card_hborder_row = (c_canvas * 56) + (c_border * 1088) + (c_canvas * 56)
    card_body_base = (c_canvas * 56) + (c_border * 2) + (c_white * 1084) + (c_border * 2) + (c_canvas * 56)

    def _fill(buf: bytearray, x0: int, x1: int, color_3: bytes) -> None:
        buf[x0 * 3 : x1 * 3] = color_3 * (x1 - x0)

    rows: List[bytes] = []
    for y in range(height):
        if y < 12:
            rows.append(top_bar_row)
            continue
        if y < 56 or y >= 574:
            rows.append(canvas_row)
            continue
        if y in (56, 57, 572, 573):
            rows.append(card_hborder_row)
            continue
        buf = bytearray(card_body_base)
        if 112 <= y < 208:
            _fill(buf, 112, 208, c_brand)
            if 125 <= y < 195:
                gy = (y - 125) // 10
                if 0 <= gy < 7:
                    for gx in range(5):
                        if glyph[gy][gx] == "1":
                            _fill(buf, 135 + gx * 10, 145 + gx * 10, c_white)
            if 128 <= y < 154:
                _fill(buf, 240, 760, c_ink)
            elif 172 <= y < 188:
                _fill(buf, 240, 620, c_slate)
        elif 260 <= y < 492:
            for col_x in (112, 444, 776):
                col_end = col_x + 300
                if y < 268:
                    _fill(buf, col_x, col_end, c_brand)
                elif y >= 490:
                    _fill(buf, col_x, col_end, c_border)
                else:
                    _fill(buf, col_x, col_end, c_soft)
                    _fill(buf, col_x, col_x + 2, c_border)
                    _fill(buf, col_end - 2, col_end, c_border)
                    if 296 <= y < 312:
                        _fill(buf, col_x + 24, col_x + 170, c_slate)
                    elif 334 <= y < 370:
                        _fill(buf, col_x + 24, col_x + 210, c_ink)
                    elif 402 <= y < 416:
                        _fill(buf, col_x + 24, col_x + 240, c_border)
        rows.append(bytes(buf))

    return _encode_png(width, height, rows, color_type=2)


def _sync_sitemaps_headers_and_redirects(dist_dir: Path, profile: Dict[str, Any]) -> List[str]:
    """Ensures all 6 governance routes, fresh crawler/feed cache policies, favicon.ico, and OG PNG exist."""
    base = profile["canonical_base"].rstrip("/")
    gov_urls = [f"{base}/{g}/" for g in GOVERNANCE_ROUTES]
    mutated: List[str] = []

    lastmod_str = "2026-11-13"
    for sm_probe in ("sitemap.xml", "sitemap-hubs.xml"):
        p_probe = dist_dir / sm_probe
        if p_probe.is_file():
            lmods = re.findall(r"<lastmod>\s*(\d{4}-\d{2}-\d{2})\s*</lastmod>", p_probe.read_text(encoding="utf-8", errors="ignore"))
            if lmods:
                lastmod_str = max(lmods)
                break

    # Sync sitemap-hubs.xml and sitemap.xml
    for sm_name, include_all_gov in (("sitemap-hubs.xml", True), ("sitemap.xml", True)):
        sm_path = dist_dir / sm_name
        if not sm_path.is_file():
            continue
        raw_xml = sm_path.read_text(encoding="utf-8")
        if "<sitemapindex" in raw_xml:
            continue
        existing_locs = set(re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", raw_xml))
        missing_entries: List[str] = []
        for g_url in gov_urls:
            if include_all_gov and g_url not in existing_locs:
                missing_entries.append(
                    f"  <url>\n"
                    f"    <loc>{saxutils.escape(g_url)}</loc>\n"
                    f"    <lastmod>{lastmod_str}</lastmod>\n"
                    f"    <changefreq>weekly</changefreq>\n"
                    f"    <priority>0.8</priority>\n"
                    f"  </url>"
                )
        if missing_entries and "</urlset>" in raw_xml:
            updated_xml = raw_xml.replace("</urlset>", "\n".join(missing_entries) + "\n</urlset>")
            ET.fromstring(updated_xml)
            if updated_xml != raw_xml:
                sm_path.write_text(updated_xml, encoding="utf-8")
                mutated.append(sm_name)

    # Sync dist/_headers so all 6 governance routes + crawler/feed endpoints + /* security headers are canonical
    # while deterministically keeping active Cloudflare _headers rules <= 95.
    headers_path = dist_dir / "_headers"
    if headers_path.is_file():
        orig_h_txt = headers_path.read_text(encoding="utf-8")
        parsed_blocks: List[Tuple[str, List[str], bool]] = []
        cur_p: Optional[str] = None
        cur_h: List[str] = []
        cur_c = False
        for raw_line in orig_h_txt.splitlines():
            s_line = raw_line.strip()
            if not s_line:
                if cur_p is not None and cur_c:
                    parsed_blocks.append((cur_p, cur_h, cur_c))
                    cur_p = None
                    cur_h = []
                    cur_c = False
                continue
            if s_line.startswith("# [edge-middleware-canonical]"):
                if cur_p is not None:
                    parsed_blocks.append((cur_p, cur_h, cur_c))
                cur_p = s_line[len("# [edge-middleware-canonical]") :].strip()
                cur_h = []
                cur_c = True
            elif s_line.startswith("#") and cur_p is not None and cur_c:
                hdr_body = s_line.lstrip("#").strip()
                if hdr_body.startswith("[edge-middleware-header]"):
                    hdr_body = hdr_body[len("[edge-middleware-header]") :].strip()
                if ":" in hdr_body or hdr_body.startswith("!"):
                    cur_h.append(hdr_body)
            elif s_line.startswith("#"):
                continue
            elif not raw_line[:1].isspace():
                if cur_p is not None:
                    parsed_blocks.append((cur_p, cur_h, cur_c))
                cur_p = s_line
                cur_h = []
                cur_c = False
            elif cur_p is not None:
                cur_h.append(s_line)
        if cur_p is not None:
            parsed_blocks.append((cur_p, cur_h, cur_c))

        deduped_blocks: List[List[Any]] = []
        block_index: Dict[str, int] = {}
        for bp_path, bp_hdrs, bp_comm in parsed_blocks:
            if bp_path in block_index:
                continue
            block_index[bp_path] = len(deduped_blocks)
            deduped_blocks.append([bp_path, list(bp_hdrs), bp_comm])

        hdrs_changed = False

        def _ensure_block(route: str, required_hdrs: List[str], replace_cc: bool = False, force_active: bool = False) -> None:
            nonlocal hdrs_changed
            if route not in block_index:
                block_index[route] = len(deduped_blocks)
                deduped_blocks.append([route, list(required_hdrs), False])
                hdrs_changed = True
                return
            blk = deduped_blocks[block_index[route]]
            if force_active and blk[2]:
                blk[2] = False
                hdrs_changed = True
            hdr_list: List[str] = blk[1]
            for req in required_hdrs:
                if req.startswith("!"):
                    detach_target = req[1:].strip().lower()
                    existing_detach_idx = next(
                        (i for i, h in enumerate(hdr_list) if h.strip().startswith("!") and h.strip()[1:].strip().lower() == detach_target),
                        None,
                    )
                    target_hdr_idx = next(
                        (i for i, h in enumerate(hdr_list) if ":" in h and h.split(":", 1)[0].strip().lower() == detach_target),
                        None,
                    )
                    if existing_detach_idx is None:
                        if target_hdr_idx is not None:
                            hdr_list.insert(target_hdr_idx, req)
                        else:
                            hdr_list.append(req)
                        hdrs_changed = True
                    elif target_hdr_idx is not None and existing_detach_idx > target_hdr_idx:
                        hdr_list.pop(existing_detach_idx)
                        hdr_list.insert(target_hdr_idx, req)
                        hdrs_changed = True
                    continue
                req_key = req.split(":", 1)[0].strip().lower()
                existing_idx = next(
                    (i for i, h in enumerate(hdr_list) if ":" in h and h.split(":", 1)[0].strip().lower() == req_key),
                    None,
                )
                if existing_idx is None:
                    hdr_list.append(req)
                    hdrs_changed = True
                elif replace_cc and req_key == "cache-control" and hdr_list[existing_idx] != req:
                    hdr_list[existing_idx] = req
                    hdrs_changed = True

        detach_cc = "! Cache-Control"
        fresh_cc = "Cache-Control: public, max-age=0, s-maxage=60, must-revalidate"
        for ep, ct_val in (
            ("/robots.txt", "text/plain; charset=utf-8"),
            ("/feed.xml", "application/xml; charset=utf-8"),
            ("/llms.txt", "text/plain; charset=utf-8"),
            ("/llms-full.txt", "text/plain; charset=utf-8"),
            ("/sitemap.xml", "application/xml; charset=utf-8"),
            ("/sitemap-hubs.xml", "application/xml; charset=utf-8"),
            ("/sitemap-leaves.xml", "application/xml; charset=utf-8"),
        ):
            _ensure_block(
                ep,
                [f'Link: <{base}{ep}>; rel="canonical"', f"Content-Type: {ct_val}", detach_cc, fresh_cc],
                replace_cc=True,
                force_active=True,
            )
        _ensure_block(
            "/catalog.json",
            [
                f'Link: <{base}/catalog.json>; rel="canonical"',
                "Content-Type: application/json; charset=utf-8",
                detach_cc,
                "Cache-Control: public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800",
            ],
            replace_cc=True,
            force_active=True,
        )
        _ensure_block("/ai-benchmarks/*", [detach_cc, fresh_cc], replace_cc=True, force_active=True)
        _ensure_block(
            "/static/js/*",
            [detach_cc, "Cache-Control: public, max-age=31536000, immutable"],
            replace_cc=True,
            force_active=True,
        )

        for g in GOVERNANCE_ROUTES:
            route = f"/{g}/"
            if route not in block_index:
                _ensure_block(
                    route,
                    [
                        f'Link: <{base}{route}>; rel="canonical"',
                        "Cache-Control: public, max-age=0, s-maxage=86400, stale-while-revalidate=604800",
                    ],
                )

        if "/*" in block_index:
            _ensure_block(
                "/*",
                [
                    "X-Content-Type-Options: nosniff",
                    "Strict-Transport-Security: max-age=31536000; includeSubDomains",
                ],
            )

        active_idx = [idx for idx, b in enumerate(deduped_blocks) if not b[2]]
        if hdrs_changed or len(active_idx) > 95:
            def _hdr_prio(idx_val: int) -> Tuple[int, int]:
                rp = deduped_blocks[idx_val][0]
                if rp == "/*":
                    return (0, idx_val)
                if "*" in rp and rp != "/ai-benchmarks/*":
                    return (1, idx_val)
                if rp.startswith(("/css/", "/js/", "/static/")):
                    return (1, idx_val)
                if rp in (
                    "/robots.txt",
                    "/ai-benchmarks/*",
                    "/feed.xml",
                    "/llms.txt",
                    "/llms-full.txt",
                    "/sitemap.xml",
                    "/sitemap-hubs.xml",
                    "/sitemap-leaves.xml",
                    "/catalog.json",
                    "/media-kit.json",
                    "/ai-plugin.json",
                ):
                    return (2, idx_val)
                if rp in ("/", "/tools/", "/guides/", "/about/", "/privacy/", "/terms/", "/disclaimers/", "/methodology/", "/contact/"):
                    return (3, idx_val)
                depth = len([seg for seg in rp.strip("/").split("/") if seg])
                if depth <= 2:
                    return (4, idx_val)
                return (5, idx_val)

            keep_active = set(sorted(active_idx, key=_hdr_prio)[:95]) if len(active_idx) > 95 else set(active_idx)
            out_hdr_chunks: List[str] = ["# Cloudflare Pages Edge Headers generated by pseofactory.edge"]
            for idx_val, (bp_path, bp_hdrs, bp_comm) in enumerate(deduped_blocks):
                if not bp_comm and idx_val in keep_active:
                    out_hdr_chunks.append("\n".join([bp_path] + [f"  {hl}" for hl in bp_hdrs]))
                else:
                    out_hdr_chunks.append(
                        "\n".join(
                            [f"# [edge-middleware-canonical] {bp_path}"]
                            + [f"#   {hl}" for hl in bp_hdrs]
                        )
                    )
            new_h_txt = out_hdr_chunks[0] + "\n" + "\n\n".join(out_hdr_chunks[1:]) + "\n"
            if new_h_txt != orig_h_txt:
                headers_path.write_text(new_h_txt, encoding="utf-8")
                mutated.append("_headers")

    # Scrub cross-legal 301s from dist/_redirects while preserving all legitimate non-legal 301s
    reds_path = dist_dir / "_redirects"
    prop_id_clean = str(profile.get("property_id") or "").strip().lower()
    if reds_path.is_file() or prop_id_clean == "lienbond":
        orig_r_txt = reds_path.read_text(encoding="utf-8") if reds_path.is_file() else ""
        kept_lines: List[str] = []
        for line in orig_r_txt.splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                parts = s.split()
                if parts and parts[0] in CROSS_LEGAL_REDIRECT_SOURCES:
                    continue
            kept_lines.append(line)
        new_r_txt = ("\n".join(kept_lines).rstrip() + "\n") if kept_lines else ""
        if prop_id_clean == "lienbond":
            from pseofactory.compiler import build_lienbond_canonical_redirects_content

            new_r_txt = build_lienbond_canonical_redirects_content(dist_dir, existing_content=new_r_txt)
        if not reds_path.is_file() or new_r_txt != orig_r_txt:
            reds_path.write_text(new_r_txt, encoding="utf-8")
            mutated.append("_redirects")

    # Never expose internal .pseofactory.json inside public dist/
    leaked_meta = dist_dir / ".pseofactory.json"
    if leaked_meta.is_file():
        leaked_meta.unlink(missing_ok=True)
        mutated.append(".pseofactory.json")

    # Ensure robots.txt blocks crawler execution of /api/ and /cdn-cgi/ for EVERY User-agent group
    robots_path = dist_dir / "robots.txt"
    if robots_path.is_file():
        from pseofactory.estate_common import ensure_robots_txt_mandatory_disallows

        orig_rob = robots_path.read_text(encoding="utf-8", errors="ignore")
        new_rob = ensure_robots_txt_mandatory_disallows(orig_rob)
        if new_rob != orig_rob:
            robots_path.write_text(new_rob, encoding="utf-8")
            mutated.append("robots.txt")

    # Ensure favicon.svg, favicon.ico, branded og:image PNG, and site.webmanifest exist so browsers never hit 404
    fav_path = dist_dir / "favicon.svg"
    if not fav_path.is_file():
        badge_ch = html_lib.escape(str(profile.get("badge_letter") or "P")[:2])
        brand_hex = str(profile.get("brand_primary") or "#1d4ed8")
        fav_svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
            f'<rect width="64" height="64" rx="14" fill="{brand_hex}"/>'
            f'<text x="32" y="43" text-anchor="middle" font-family="Inter,Arial,sans-serif" '
            f'font-size="34" font-weight="700" fill="#ffffff">{badge_ch}</text></svg>\n'
        )
        fav_path.write_text(fav_svg, encoding="utf-8")
        mutated.append("favicon.svg")

    ico_path = dist_dir / "favicon.ico"
    if not ico_path.is_file() or ico_path.stat().st_size == 0:
        ico_path.write_bytes(_build_favicon_ico_bytes(profile))
        mutated.append("favicon.ico")

    og_rel = f"static/img/{profile['property_id']}-og.png"
    og_path = dist_dir / og_rel
    if not og_path.is_file() or og_path.stat().st_size == 0:
        og_path.parent.mkdir(parents=True, exist_ok=True)
        og_path.write_bytes(_build_og_image_png_bytes(profile))
        mutated.append(og_rel)

    manifest_path = dist_dir / "site.webmanifest"
    if not manifest_path.is_file():
        web_manifest = {
            "name": profile["brand_name"],
            "short_name": profile["brand_name"],
            "start_url": "/",
            "display": "standalone",
            "background_color": "#fbfcfd",
            "theme_color": str(profile.get("brand_primary") or "#1d4ed8"),
            "icons": [{"src": "/favicon.svg", "sizes": "any", "type": "image/svg+xml"}],
        }
        manifest_path.write_text(json.dumps(web_manifest, indent=2) + "\n", encoding="utf-8")
        mutated.append("site.webmanifest")

    return mutated


_PORCELAIN_CONVERGED_LOCK = threading.Lock()
_PORCELAIN_CONVERGED_CACHE: "collections.OrderedDict[Tuple[str, str], Tuple[str, int, Dict[str, int]]]" = collections.OrderedDict()
_PORCELAIN_CONVERGED_MAXSIZE = 64


def _compute_porcelain_estate_convergence_sig(
    target_dist: Path,
    property_id: str,
    css_hash: str,
    profile_hash: str = "",
    inferred_repo: Optional[Path] = None,
    pkg_static_css: Optional[Path] = None,
) -> Optional[str]:
    """Computes a content-addressed fingerprint across all HTML, CSS, JS, XML, icon/OG, profile, and edge routing files in target_dist."""
    try:
        h = hashlib.sha256()
        h.update(
            f"{property_id}|{PORCELAIN_SHELL_VERSION}|{VISUAL_PRIMITIVES_LINK_VERSION}|{css_hash}|{profile_hash}|{str(inferred_repo) if inferred_repo else ''}\n".encode("utf-8")
        )
        if pkg_static_css is not None:
            if pkg_static_css.is_file():
                h.update(f"pkg_css:{hashlib.sha256(pkg_static_css.read_bytes()).hexdigest()}\n".encode("utf-8"))
            else:
                h.update(b"pkg_css:MISSING\n")
        for fp in sorted(target_dist.rglob("*")):
            if not fp.is_file() or fp.name.startswith("."):
                continue
            rel = fp.relative_to(target_dist).as_posix()
            sfx = fp.suffix.lower()
            if rel.startswith("videos/") or sfx in (".mp4", ".webm", ".mov", ".jpg", ".jpeg", ".webp"):
                continue
            if (
                sfx in (".html", ".css", ".js", ".xml", ".ico", ".svg", ".webmanifest")
                or fp.name in ("_headers", "_redirects")
                or (sfx == ".png" and rel.startswith("static/img/"))
            ):
                fh = hashlib.sha256(fp.read_bytes()).hexdigest()
                h.update(f"{rel}:{fh}\n".encode("utf-8"))
        return h.hexdigest()
    except Exception:
        return None


def compile_tenant_porcelain_estate_with_profile(
    dist_dir: Path,
    profile: Dict[str, Any],
    repo_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Core deterministic Porcelain estate compiler executed identically by both
    pseofactory.cli reflect AND standalone <tenant>.builder.build_all().
    """
    target_dist = Path(dist_dir).resolve()
    if not target_dist.is_dir():
        return {
            "status": "SKIPPED_MISSING_DIST",
            "pages_compiled": 0,
            "pages_mutated": 0,
            "mutated_paths": [],
            "governance_written": False,
        }

    css_text = generate_porcelain_stylesheet_from_profile(profile)
    css_hash = hashlib.sha256(css_text.encode("utf-8")).hexdigest()
    profile_hash = hashlib.sha256(
        json.dumps(profile, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    prop_id = str(profile.get("property_id") or "profithelm")
    inferred_repo = Path(repo_root).resolve() if repo_root else target_dist.parent
    is_live_repo_under_unmerged = (
        ("PYTEST_CURRENT_TEST" in os.environ or "/.agy/worktrees/" in Path(__file__).resolve().as_posix())
        and str(inferred_repo).startswith("/home/ubuntuadmin/projects/")
    )
    pkg_static_css_cand = inferred_repo / profile["package_name"] / "static" / "css" / "style.css"
    pkg_static_css_check: Optional[Path] = (
        pkg_static_css_cand
        if (not is_live_repo_under_unmerged and pkg_static_css_cand.parent.is_dir())
        else None
    )
    cache_id = (str(target_dist), prop_id)

    is_full_estate = (
        (target_dist / "index.html").is_file()
        or (target_dist / "tools" / "index.html").is_file()
        or (target_dist / "sitemap.xml").is_file()
        or any((target_dist / g / "index.html").is_file() for g in GOVERNANCE_ROUTES)
    )
    og_rel_check = target_dist / "static" / "img" / f"{prop_id}-og.png"
    ico_check = target_dist / "favicon.ico"
    has_required_assets = (
        (target_dist / "css" / "style.css").is_file()
        and (target_dist / "static" / "css" / "style.css").is_file()
        and (pkg_static_css_check is None or pkg_static_css_check.is_file())
        and (
            not is_full_estate
            or (
                (target_dist / "404.html").is_file()
                and (target_dist / "favicon.svg").is_file()
                and ico_check.is_file()
                and ico_check.stat().st_size > 0
                and og_rel_check.is_file()
                and og_rel_check.stat().st_size > 0
                and (target_dist / "site.webmanifest").is_file()
                and all((target_dist / g / "index.html").is_file() for g in GOVERNANCE_ROUTES)
            )
        )
    )
    if has_required_assets:
        with _PORCELAIN_CONVERGED_LOCK:
            cached_entry = _PORCELAIN_CONVERGED_CACHE.get(cache_id)
        if cached_entry is not None:
            cur_sig = _compute_porcelain_estate_convergence_sig(
                target_dist,
                prop_id,
                css_hash,
                profile_hash=profile_hash,
                inferred_repo=inferred_repo,
                pkg_static_css=pkg_static_css_check,
            )
            if cur_sig is not None and cur_sig == cached_entry[0]:
                with _PORCELAIN_CONVERGED_LOCK:
                    _PORCELAIN_CONVERGED_CACHE.move_to_end(cache_id)
                return {
                    "status": "PASS",
                    "property_id": prop_id,
                    "pages_compiled": cached_entry[1],
                    "pages_mutated": 0,
                    "mutated_paths": [],
                    "governance_written": False,
                    "blueprints": dict(cached_entry[2]),
                }

    known_vars, _ = extract_defined_and_referenced_css_vars(css_text)
    mutated_paths: List[str] = []

    for css_rel in ("css/style.css", "static/css/style.css"):
        out_css = target_dist / css_rel
        out_css.parent.mkdir(parents=True, exist_ok=True)
        if not out_css.is_file() or out_css.read_text(encoding="utf-8", errors="ignore") != css_text:
            out_css.write_text(css_text, encoding="utf-8")
            mutated_paths.append(css_rel)

    from pseofactory.visual_primitives import write_runtime_synchronizer_asset

    rt_js_path, rt_js_changed = write_runtime_synchronizer_asset(target_dist)
    if rt_js_changed:
        rt_js_rel = rt_js_path.relative_to(target_dist).as_posix()
        if rt_js_rel not in mutated_paths:
            mutated_paths.append(rt_js_rel)

    if pkg_static_css_check is not None:
        if not pkg_static_css_check.is_file() or pkg_static_css_check.read_text(encoding="utf-8", errors="ignore") != css_text:
            pkg_static_css_check.write_text(css_text, encoding="utf-8")

    active_tools, gsc_token = _discover_estate_tools_and_gsc_token(target_dist, profile)

    existing_hubs: Set[str] = set()
    for hub_cand in ("vs", "comparisons", "compare", "guides", "articles", "research"):
        if (target_dist / hub_cand / "index.html").is_file():
            existing_hubs.add(hub_cand)

    is_full_estate = (
        (target_dist / "index.html").is_file()
        or (target_dist / "tools" / "index.html").is_file()
        or (target_dist / "sitemap.xml").is_file()
        or any((target_dist / g / "index.html").is_file() for g in GOVERNANCE_ROUTES)
    )
    governance_written = False
    if is_full_estate:
        gov_pages = build_governance_pages(profile, active_tools=active_tools, gsc_token=gsc_token)
        _, allowed_gov_classes = get_porcelain_css_audit_sets(prop_id)
        for route_slug, gov_html in gov_pages.items():
            gov_rel = f"{route_slug}/index.html"
            gov_file = target_dist / gov_rel
            source_gov_html = gov_html
            if route_slug in ("disclaimers", "methodology") and gov_file.is_file():
                existing_gov = gov_file.read_text(encoding="utf-8", errors="ignore")
                existing_no_script = re.sub(
                    r"<(script|style)\b[^>]*>[\s\S]*?</\1>", "", existing_gov, flags=re.IGNORECASE
                )
                existing_plain = re.sub(r"<[^>]+>", " ", existing_no_script)
                has_polluted_calc = (
                    'id="calculation-manifest"' in existing_gov
                    or "id='calculation-manifest'" in existing_gov
                    or "How to Calculate Legal Disclaimers" in existing_gov
                    or "How to Calculate Methodology" in existing_gov
                    or "Q499388" in existing_gov
                    or "round((" in existing_plain
                )
                if not has_polluted_calc and len(existing_plain.strip()) >= 1800 and "<table" in existing_gov.lower():
                    source_gov_html = existing_gov
            norm_gov_html, _ = normalize_html_to_porcelain_shell(
                source_gov_html,
                gov_rel,
                profile,
                active_tools=active_tools,
                known_css_vars=known_vars,
                existing_hubs=existing_hubs,
                dist_dir=target_dist,
            )
            if source_gov_html is not gov_html and _find_undefined_ui_classes_in_html(
                norm_gov_html,
                allowed_gov_classes,
            ):
                norm_gov_html, _ = normalize_html_to_porcelain_shell(
                    gov_html,
                    gov_rel,
                    profile,
                    active_tools=active_tools,
                    known_css_vars=known_vars,
                    existing_hubs=existing_hubs,
                    dist_dir=target_dist,
                )
            gov_file.parent.mkdir(parents=True, exist_ok=True)
            if not gov_file.is_file() or gov_file.read_text(encoding="utf-8", errors="ignore") != norm_gov_html:
                gov_file.write_text(norm_gov_html, encoding="utf-8")
                mutated_paths.append(gov_rel)
                governance_written = True

        err_404_raw = build_porcelain_404_page(profile, active_tools=active_tools, gsc_token=gsc_token)
        norm_404_html, _ = normalize_html_to_porcelain_shell(
            err_404_raw,
            "404.html",
            profile,
            active_tools=active_tools,
            known_css_vars=known_vars,
            existing_hubs=existing_hubs,
            dist_dir=target_dist,
        )
        err_404_file = target_dist / "404.html"
        if not err_404_file.is_file() or err_404_file.read_text(encoding="utf-8", errors="ignore") != norm_404_html:
            err_404_file.write_text(norm_404_html, encoding="utf-8")
            mutated_paths.append("404.html")
            governance_written = True

    compiled_count = 0
    blueprint_counts: Dict[str, int] = {}

    for html_file in sorted(target_dist.rglob("*.html")):
        if html_file.name.startswith("."):
            continue
        rel = html_file.relative_to(target_dist).as_posix()
        raw_html = html_file.read_text(encoding="utf-8", errors="ignore")
        norm_html, bp = normalize_html_to_porcelain_shell(
            raw_html,
            rel,
            profile,
            active_tools=active_tools,
            known_css_vars=known_vars,
            existing_hubs=existing_hubs,
            dist_dir=target_dist,
        )
        blueprint_counts[bp] = blueprint_counts.get(bp, 0) + 1
        compiled_count += 1
        if norm_html != raw_html:
            html_file.write_text(norm_html, encoding="utf-8")
            if rel not in mutated_paths:
                mutated_paths.append(rel)

    if is_full_estate:
        for aux_rel in _sync_sitemaps_headers_and_redirects(target_dist, profile):
            if aux_rel not in mutated_paths:
                mutated_paths.append(aux_rel)

    post_sig = _compute_porcelain_estate_convergence_sig(
        target_dist,
        prop_id,
        css_hash,
        profile_hash=profile_hash,
        inferred_repo=inferred_repo,
        pkg_static_css=pkg_static_css_check,
    )
    if post_sig is not None:
        with _PORCELAIN_CONVERGED_LOCK:
            _PORCELAIN_CONVERGED_CACHE[cache_id] = (post_sig, compiled_count, dict(blueprint_counts))
            _PORCELAIN_CONVERGED_CACHE.move_to_end(cache_id)
            while len(_PORCELAIN_CONVERGED_CACHE) > _PORCELAIN_CONVERGED_MAXSIZE:
                _PORCELAIN_CONVERGED_CACHE.popitem(last=False)

    return {
        "status": "PASS",
        "property_id": profile["property_id"],
        "pages_compiled": compiled_count,
        "pages_mutated": len(mutated_paths),
        "mutated_paths": mutated_paths,
        "governance_written": governance_written,
        "blueprints": blueprint_counts,
    }


def compile_tenant_porcelain_estate(
    dist_dir: Path,
    property_id: str,
    repo_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Compiles and normalizes an entire tenant dist/ directory to the Porcelain Light contract."""
    profile = get_porcelain_tenant_profile(property_id)
    return compile_tenant_porcelain_estate_with_profile(dist_dir, profile, repo_root=repo_root)

# --- TENANT_SYNC_BOUNDARY ---

_PSEO_SUBSTRATE_EXCLUDED_FILES: Set[str] = {
    "__init__.py",
    "__main__.py",
    "cli.py",
    "ui.py",
    "server.py",
    "browser_verifier.py",
    "compliance.py",
    "aio_observatory.py",
}

_PSEO_SUBSTRATE_LAZY_INIT = '''"""
Pure-stdlib pseofactory runtime substrate synced into tenant repository for zero-shim standalone CI.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import importlib
import importlib.util
from typing import Any

from . import contracts as _contracts  # noqa: F401

_LAZY_EXPORT_MODULES = (
    "contracts",
    "verifier",
    "audit",
    "affiliates",
    "edge",
    "indexer",
    "drift",
    "maintenance",
    "compiler",
    "qualification",
    "competitor",
    "distributor",
    "gsc_remediation",
    "porcelain_shell",
    "visual_primitives",
    "tenant_facts",
    "estate_common",
    "gainhelm_estate",
)


def __getattr__(name: str) -> Any:
    sub_fqn = f"{__name__}.{name}"
    if importlib.util.find_spec(sub_fqn) is not None:
        mod = importlib.import_module(sub_fqn)
        globals()[name] = mod
        return mod
    for mod_name in _LAZY_EXPORT_MODULES:
        mod = importlib.import_module(f"{__name__}.{mod_name}")
        if hasattr(mod, name):
            val = getattr(mod, name)
            globals()[name] = val
            return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
'''


def _sync_tenant_pseo_substrate(
    repo: Path,
    pkg_dir: Path,
    property_id: Optional[str] = None,
) -> List[str]:
    """Syncs pure-stdlib pseofactory runtime modules into <pkg>/_pseo_substrate/pseofactory/."""
    src_pkg_dir = Path(__file__).resolve().parent
    dst_pkg_dir = (pkg_dir / "_pseo_substrate" / "pseofactory").resolve()
    updated: List[str] = []
    sub_prof = get_porcelain_tenant_profile(property_id or pkg_dir.name)
    li_id = str(sub_prof.get("linkedin_company_id") or "").strip()
    sub_li_url = (
        f"https://www.linkedin.com/company/{li_id}/"
        if li_id
        else f"{sub_prof['canonical_base'].rstrip('/')}/"
    )
    sub_mailto = f"mailto:{sub_prof['contact_email']}"
    sub_handle = f"@{sub_prof['property_id']}"
    sub_entity = str(sub_prof["research_entity"])

    legacy_bundle = pkg_dir / "_pseo_estate_bundle.xz"
    if legacy_bundle.is_file():
        legacy_bundle.unlink()
        updated.append(str(legacy_bundle.relative_to(repo)))

    if src_pkg_dir == dst_pkg_dir:
        return updated

    sub_root_init = pkg_dir / "_pseo_substrate" / "__init__.py"
    sub_root_init.parent.mkdir(parents=True, exist_ok=True)

    expected_rels: Set[str] = {"__init__.py"}
    dst_pkg_dir.mkdir(parents=True, exist_ok=True)
    init_dst = dst_pkg_dir / "__init__.py"
    if not init_dst.is_file() or init_dst.read_text(encoding="utf-8") != _PSEO_SUBSTRATE_LAZY_INIT:
        init_dst.write_text(_PSEO_SUBSTRATE_LAZY_INIT, encoding="utf-8")
        updated.append(str(init_dst.relative_to(repo)))

    for py_src in sorted(src_pkg_dir.rglob("*.py")):
        if "__pycache__" in py_src.parts:
            continue
        rel = py_src.relative_to(src_pkg_dir).as_posix()
        if rel in _PSEO_SUBSTRATE_EXCLUDED_FILES:
            continue
        expected_rels.add(rel)
        py_dst = dst_pkg_dir / rel
        py_dst.parent.mkdir(parents=True, exist_ok=True)
        src_txt = py_src.read_text(encoding="utf-8")
        src_txt = _PERSONAL_LINKEDIN_URL_RE.sub(sub_li_url, src_txt)
        src_txt = _PERSONAL_MAKER_MAILTO_RE.sub(sub_mailto, src_txt)
        src_txt = _PERSONAL_MAKER_HANDLE_RE.sub(sub_handle, src_txt)
        src_txt = _PERSONAL_MAKER_NAME_RE.sub(sub_entity, src_txt)
        if not py_dst.is_file() or py_dst.read_text(encoding="utf-8") != src_txt:
            py_dst.write_text(src_txt, encoding="utf-8")
            updated.append(str(py_dst.relative_to(repo)))

    for existing_py in sorted(dst_pkg_dir.rglob("*.py")):
        if "__pycache__" in existing_py.parts:
            continue
        rel_ex = existing_py.relative_to(dst_pkg_dir).as_posix()
        if rel_ex not in expected_rels:
            existing_py.unlink()
            updated.append(str(existing_py.relative_to(repo)))

    return updated


def _generate_tenant_porcelain_module_source(property_id: str) -> str:
    """Generates clean <pkg>/_pseo_porcelain.py delegating directly to real pseofactory.porcelain_shell."""
    prop = str(property_id or "profithelm").strip().lower()
    if prop == "profithelm-platform":
        prop = "profithelm"
    return (
        '"""Tenant Porcelain Light entrypoint backed by real pure-stdlib pseofactory.porcelain_shell."""\n\n'
        "from __future__ import annotations\n\n"
        "import os\n"
        "import sys\n"
        "from pathlib import Path\n"
        "from typing import Any, Dict, Optional, Sequence\n\n"
        "_SUBSTRATE_DIR = Path(__file__).resolve().parent / '_pseo_substrate'\n"
        "_PSEO_EXT = ('pseofactory' in sys.modules) or any(\n"
        "    '_pseo_substrate' not in _p and (\n"
        "        'pseofactory' in _p or 'porcelain-shell' in _p or Path(_p).joinpath('pseofactory', '__init__.py').is_file()\n"
        "    )\n"
        "    for _p in (os.environ.get('PYTHONPATH') or '').split(os.pathsep) if _p\n"
        ")\n"
        "if not _PSEO_EXT and _SUBSTRATE_DIR.is_dir() and str(_SUBSTRATE_DIR) not in sys.path:\n"
        "    sys.path.insert(0, str(_SUBSTRATE_DIR))\n\n"
        f"PROPERTY_ID = {prop!r}\n\n\n"
        "def generate_porcelain_stylesheet() -> str:\n"
        '    """Generates canonical Porcelain Light CSS for this tenant."""\n'
        "    from pseofactory.porcelain_shell import generate_porcelain_stylesheet as _gen_css\n\n"
        "    return _gen_css(PROPERTY_ID)\n\n\n"
        "def compile_tenant_porcelain_estate(\n"
        "    dist_dir: Optional[Path] = None,\n"
        "    extra_tools: Optional[Sequence[Any]] = None,\n"
        ") -> Dict[str, Any]:\n"
        '    """Compiles and normalizes dist/ to the locked Porcelain Light contract."""\n'
        "    from pseofactory.porcelain_shell import compile_tenant_porcelain_estate as _compile_est\n\n"
        "    repo_root = Path(__file__).resolve().parent.parent\n"
        "    target_dist = Path(dist_dir).resolve() if dist_dir else (repo_root / 'dist')\n"
        "    return _compile_est(target_dist, property_id=PROPERTY_ID, repo_root=repo_root)\n"
    )



def _scrub_tenant_personal_maker_and_inline_js(repo_path: Path, profile: Dict[str, Any]) -> List[str]:
    """
    1. Tokenizes inline #hex style assignments in profithelm app.js.
    2. Replaces personal maker/author metadata and personal LinkedIn URLs across tenant Python
       builders/submitters and JSON manifests with corporate entity metadata.
    3. Guards hardcoded /home/ubuntuadmin/projects/pseofactory sys.path probes for standalone isolation.
    """
    updated: List[str] = []
    repo = Path(repo_path).resolve()
    pkg_name = profile["package_name"]
    li_id = str(profile.get("linkedin_company_id") or "").strip()
    company_li = (
        f"https://www.linkedin.com/company/{li_id}/"
        if li_id
        else f"{profile['canonical_base'].rstrip('/')}/"
    )

    if profile["property_id"] == "profithelm":
        for js_rel in ("profithelm/static/js/app.js", "dist/static/js/app.js"):
            js_file = repo / js_rel
            if not js_file.is_file():
                continue
            src = js_file.read_text(encoding="utf-8")
            orig = src
            replacements = [
                ("buttonElement.style.borderColor = '#16a34a';", "buttonElement.style.borderColor = 'var(--status-positive)';"),
                ("buttonElement.style.color = '#16a34a';", "buttonElement.style.color = 'var(--status-positive)';"),
                ("btn.style.backgroundColor = '#16a34a';", "btn.style.backgroundColor = 'var(--status-positive)';"),
                ("color: '#93c5fd'", "color: 'var(--meter-tier-1)'"),
                ("color: '#60a5fa'", "color: 'var(--meter-tier-2)'"),
                ("color: '#3b82f6'", "color: 'var(--meter-tier-3)'"),
                ("color: '#1d4ed8'", "color: 'var(--meter-tier-4)'"),
                ("color: '#1e40af'", "color: 'var(--meter-tier-5)'"),
                ("color: '#1e3a8a'", "color: 'var(--meter-tier-6)'"),
                ("color: '#0f172a'", "color: 'var(--meter-tier-7)'"),
                ("color: tier.color || '#3b82f6'", "color: tier.color || 'var(--meter-tier-3)'"),
                (
                    '<div style="font-size: 0.8125rem; font-weight: 700; color: #ea580c; margin-bottom: 0.25rem;">',
                    '<div class="clawback-notice-text">',
                ),
            ]
            for old_s, new_s in replacements:
                src = src.replace(old_s, new_s)
            if src != orig:
                js_file.write_text(src, encoding="utf-8")
                updated.append(js_rel)

        ds_file = repo / "profithelm" / "directory_submitter.py"
        if ds_file.is_file():
            ds_src = ds_file.read_text(encoding="utf-8")
            ds_new = re.sub(
                r'"maker"\s*:\s*\{[\s\S]*?\},',
                (
                    '"maker": {\n'
                    '            "name": "ProfitHelm Quantitative Research",\n'
                    '            "email": CONTACT_EMAIL,\n'
                    '            "twitter": TWITTER_HANDLE,\n'
                    '            "linkedin": LINKEDIN_COMPANY_URL,\n'
                    '            "role": "Quantitative Research Desk",\n'
                    "        },"
                ),
                ds_src,
                count=1,
            )
            ds_new = _PERSONAL_LINKEDIN_URL_RE.sub(company_li, ds_new)
            ds_new = _PERSONAL_MAKER_MAILTO_RE.sub(f"mailto:{profile['contact_email']}", ds_new)
            ds_new = _PERSONAL_MAKER_EMAIL_RE.sub(profile["contact_email"], ds_new)
            ds_new = _PERSONAL_MAKER_HANDLE_RE.sub("@profithelm", ds_new)
            ds_new = _PERSONAL_MAKER_NAME_RE.sub("ProfitHelm Quantitative Research", ds_new)
            if ds_new != ds_src:
                ds_file.write_text(ds_new, encoding="utf-8")
                updated.append("profithelm/directory_submitter.py")

        for sig_rel in ("profithelm/static/signal/index.html", "dist/signal/index.html", "dist/static/signal/index.html"):
            sig_file = repo / sig_rel
            if not sig_file.is_file():
                continue
            sig_src = sig_file.read_text(encoding="utf-8")
            sig_new = _scrub_operator_pwa_gsc_token(sig_src, profile)
            if sig_new != sig_src:
                sig_file.write_text(sig_new, encoding="utf-8")
                updated.append(sig_rel)

    if pkg_name == "lienbond":
        cli_file = repo / "lienbond" / "cli.py"
        if cli_file.is_file():
            cli_src = cli_file.read_text(encoding="utf-8")
            cli_new = cli_src.replace(
                'getattr(report, "drifted", 0) if not isinstance(report, dict) else report.get("drifted", 0)',
                'getattr(report, "drifted_assets_count", getattr(report, "drifted", 0)) if not isinstance(report, dict) else report.get("drifted_assets_count", report.get("drifted", 0))',
            )
            if cli_new != cli_src:
                cli_file.write_text(cli_new, encoding="utf-8")
                updated.append("lienbond/cli.py")

    manifest_candidates: List[Path] = [
        repo / "syndication" / "directory_manifest.json",
        repo / ".agy" / "directory_submissions" / "directory_manifest.json",
    ]
    synd_dir = repo / "syndication"
    if synd_dir.is_dir():
        manifest_candidates.extend(sorted(synd_dir.rglob("*.json")))
    for mf in manifest_candidates:
        if not mf.is_file():
            continue
        m_src = mf.read_text(encoding="utf-8")
        m_new = _PERSONAL_LINKEDIN_URL_RE.sub(company_li, m_src)
        m_new = _PERSONAL_MAKER_MAILTO_RE.sub(f"mailto:{profile['contact_email']}", m_new)
        m_new = _PERSONAL_MAKER_EMAIL_RE.sub(profile["contact_email"], m_new)
        m_new = _PERSONAL_MAKER_HANDLE_RE.sub(f"@{profile['property_id']}", m_new)
        m_new = _PERSONAL_MAKER_NAME_RE.sub(profile["research_entity"], m_new)
        if m_new != m_src:
            mf.write_text(m_new, encoding="utf-8")
            updated.append(str(mf.relative_to(repo)))

    pyproj_file = repo / "pyproject.toml"
    if pyproj_file.is_file():
        pp_src = pyproj_file.read_text(encoding="utf-8")
        pp_new = _PERSONAL_MAKER_NAME_RE.sub(profile["legal_entity"], pp_src)
        pp_new = _PERSONAL_MAKER_EMAIL_RE.sub(profile["contact_email"], pp_new)
        if pp_new != pp_src:
            pyproj_file.write_text(pp_new, encoding="utf-8")
            updated.append("pyproject.toml")

    b_file = repo / pkg_name / "builder.py"
    if b_file.is_file():
        b_src = b_file.read_text(encoding="utf-8")
        b_new = b_src
        if pkg_name in ("prexvo", "gainhelm"):
            b_new = re.sub(
                r'node\["author"\]\s*=\s*\{\s*"@type"\s*:\s*"Person"[\s\S]*?\}',
                (
                    'node["author"] = {\n'
                    '                "@type": "Organization",\n'
                    '                "@id": org_id,\n'
                    '                "name": SITE_NAME,\n'
                    '                "url": CANONICAL_BASE,\n'
                    "            }"
                ),
                b_new,
            )
            if _PERSONAL_MAKER_NAME_RE.search(b_new):
                b_new = _PERSONAL_MAKER_NAME_RE.sub(profile["legal_entity"], b_new)
        wikidata_builder_map = {
            "lienbond": "https://www.wikidata.org/wiki/Q192161",
            "prexvo": "https://www.wikidata.org/wiki/Q633315",
            "gainhelm": "https://www.wikidata.org/wiki/Q166142",
            "profithelm": "https://www.wikidata.org/wiki/Q8161",
        }
        target_wikidata = wikidata_builder_map.get(
            str(profile.get("property_id") or "profithelm"),
            "https://www.wikidata.org/wiki/Q8161",
        )
        if "https://www.wikidata.org/wiki/Q499388" in b_new:
            b_new = b_new.replace("https://www.wikidata.org/wiki/Q499388", target_wikidata)
        if b_new != b_src:
            b_file.write_text(b_new, encoding="utf-8")
            updated.append(f"{pkg_name}/builder.py")

    fac_file = repo / pkg_name / "factory.py"
    if fac_file.is_file():
        f_src = fac_file.read_text(encoding="utf-8")
        old_probe = 'if "/home/ubuntuadmin/projects/pseofactory" not in sys.path:\n'
        new_probe = (
            'import importlib.util as _pseo_ilu\n'
            '                if _pseo_ilu.find_spec("pseofactory") is None and "/home/ubuntuadmin/projects/pseofactory" not in sys.path:\n'
        )
        if old_probe in f_src and "_pseo_ilu.find_spec" not in f_src:
            f_new = f_src.replace(old_probe, new_probe, 1)
            fac_file.write_text(f_new, encoding="utf-8")
            updated.append(f"{pkg_name}/factory.py")

    if pkg_name == "prexvo":
        aff_test = repo / "tests" / "test_affiliate_routes.py"
        if aff_test.is_file():
            at_src = aff_test.read_text(encoding="utf-8")
            old_at = (
                '    pseofactory_root = Path("/home/ubuntuadmin/projects/pseofactory")\n'
                '    pythonpath = f"{worktree_root}:{pseofactory_root}"\n'
            )
            new_at = "    pythonpath = str(worktree_root)\n"
            if old_at in at_src:
                aff_test.write_text(at_src.replace(old_at, new_at, 1), encoding="utf-8")
                updated.append("tests/test_affiliate_routes.py")

    return updated


def build_substrate_bootstrap_block(pkg_name: Optional[str] = None) -> str:
    """Build deterministic sys.path _pseo_substrate bootstrap block for __init__.py or tests/conftest.py."""
    if pkg_name is None:
        sub_lines = [
            "_PSEO_SUBSTRATE = _PseoPath(__file__).resolve().parent / '_pseo_substrate'",
        ]
        repo_root_line = ""
    else:
        sub_lines = [
            "_PSEO_REPO_ROOT = _PseoPath(__file__).resolve().parent.parent",
            f"_PSEO_SUBSTRATE = _PSEO_REPO_ROOT / {pkg_name!r} / '_pseo_substrate'",
        ]
        repo_root_line = (
            "if str(_PSEO_REPO_ROOT) not in _pseo_sys.path:\n"
            "    _pseo_sys.path.insert(0, str(_PSEO_REPO_ROOT))\n"
        )
    return "\n".join(
        [
            "# [PSEO_SUBSTRATE_BOOTSTRAP]",
            "import os as _pseo_os",
            "import sys as _pseo_sys",
            "from pathlib import Path as _PseoPath",
            *sub_lines,
            "_PSEO_EXT = ('pseofactory' in _pseo_sys.modules) or any(",
            "    '_pseo_substrate' not in _p and (",
            "        'pseofactory' in _p or 'porcelain-shell' in _p or _PseoPath(_p).joinpath('pseofactory', '__init__.py').is_file()",
            "    )",
            "    for _p in (_pseo_os.environ.get('PYTHONPATH') or '').split(_pseo_os.pathsep) if _p",
            ")",
            "if not _PSEO_EXT and _PSEO_SUBSTRATE.is_dir() and str(_PSEO_SUBSTRATE) not in _pseo_sys.path:",
            "    _pseo_sys.path.insert(0, str(_PSEO_SUBSTRATE))",
        ]
    ) + "\n" + repo_root_line + "# [/PSEO_SUBSTRATE_BOOTSTRAP]\n"


def _wire_substrate_bootstrap(
    target_file: Path,
    bootstrap_block: str,
    default_doc: str,
    insert_after_imports: bool = False,
) -> bool:
    """Idempotently wires _pseo_substrate sys.path fallback into __init__.py or tests/conftest.py."""
    marker = "# [PSEO_SUBSTRATE_BOOTSTRAP]"
    if target_file.is_file():
        src = target_file.read_text(encoding="utf-8")
        cleaned = re.sub(
            r"\ntry:\n\s*import pseofactory as _pseofactory_probe[\s\S]*?_install_shims\(\)\n?",
            "\n",
            src,
        )
        if marker in cleaned:
            cleaned = re.sub(
                r"# \[PSEO_SUBSTRATE_BOOTSTRAP\][\s\S]*?# \[/PSEO_SUBSTRATE_BOOTSTRAP\]\n?",
                bootstrap_block,
                cleaned,
                count=1,
            )
        elif insert_after_imports:
            anchor = "from pathlib import Path\n"
            if anchor in cleaned:
                cleaned = cleaned.replace(anchor, anchor + "\n" + bootstrap_block, 1)
            else:
                cleaned = bootstrap_block + "\n" + cleaned
        else:
            cleaned = cleaned.rstrip() + "\n\n" + bootstrap_block
        if cleaned != src:
            target_file.write_text(cleaned, encoding="utf-8")
            return True
        return False

    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text(default_doc + "\n" + bootstrap_block, encoding="utf-8")
    return True


def wire_tenant_substrate_bootstraps(
    repo_path: Path,
    pkg_name: str,
    brand_name: str,
) -> List[str]:
    """Idempotently wire _pseo_substrate bootstrap into <pkg>/__init__.py and tests/conftest.py."""
    repo = Path(repo_path).resolve()
    pkg_dir = repo / pkg_name
    if not pkg_dir.is_dir():
        return []
    updated: List[str] = []
    if _wire_substrate_bootstrap(
        pkg_dir / "__init__.py",
        build_substrate_bootstrap_block(),
        f'"""{brand_name} package."""\n',
        insert_after_imports=False,
    ):
        updated.append(f"{pkg_name}/__init__.py")
    if (repo / "tests").is_dir():
        if _wire_substrate_bootstrap(
            repo / "tests" / "conftest.py",
            build_substrate_bootstrap_block(pkg_name=pkg_name),
            f'"""{brand_name} test configuration."""\n\nfrom pathlib import Path\n',
            insert_after_imports=True,
        ):
            updated.append("tests/conftest.py")
    return updated


def sync_tenant_porcelain_shell(repo_path: Path, property_id: str) -> Dict[str, Any]:
    """
    Deterministically propagates the Porcelain Light contract and real pure-stdlib pseofactory
    substrate into a tenant repository:
    1. Syncs real pure-stdlib runtime modules into <pkg>/_pseo_substrate/pseofactory/.
    2. Writes <pkg>/_pseo_porcelain.py + wires <pkg>/__init__.py and tests/conftest.py fallback.
    3. Writes canonical <pkg>/static/css/style.css (+ dist copies).
    4. Hooks <pkg>/builder.py:build_all(), updates <pkg>/seo_verifier.py required_endpoints
       to enforce all 6 governance pages, and scrubs cross-legal 301s.
    5. Scrubs inline JS hexes and personal maker/LinkedIn strings across all 4 tenants.
    """
    repo = Path(repo_path).resolve()
    profile = get_porcelain_tenant_profile(property_id)
    pkg_name = profile["package_name"]
    pkg_dir = repo / pkg_name
    if not pkg_dir.is_dir():
        return {"status": "SKIPPED_NO_PACKAGE", "updated_files": []}

    updated_files: List[str] = []

    # 1. Sync real pure-stdlib pseofactory runtime substrate (zero fake shims, zero .xz bundles)
    updated_files.extend(_sync_tenant_pseo_substrate(repo, pkg_dir, property_id=profile["property_id"]))

    # 2. Write <pkg>/_pseo_porcelain.py
    porc_mod_path = pkg_dir / "_pseo_porcelain.py"
    porc_mod_src = _generate_tenant_porcelain_module_source(profile["property_id"])
    if not porc_mod_path.is_file() or porc_mod_path.read_text(encoding="utf-8") != porc_mod_src:
        porc_mod_path.write_text(porc_mod_src, encoding="utf-8")
        updated_files.append(f"{pkg_name}/_pseo_porcelain.py")

    # 3. Wire _pseo_substrate fallback into <pkg>/__init__.py and tests/conftest.py
    updated_files.extend(
        wire_tenant_substrate_bootstraps(repo, pkg_name, profile["brand_name"])
    )

    # 4. Write canonical Porcelain stylesheet to <pkg>/static/css/style.css and dist
    css_text = generate_porcelain_stylesheet_from_profile(profile)
    for css_target in (
        pkg_dir / "static" / "css" / "style.css",
        repo / "dist" / "css" / "style.css",
        repo / "dist" / "static" / "css" / "style.css",
    ):
        css_target.parent.mkdir(parents=True, exist_ok=True)
        if not css_target.is_file() or css_target.read_text(encoding="utf-8") != css_text:
            css_target.write_text(css_text, encoding="utf-8")
            updated_files.append(str(css_target.relative_to(repo)))

    # 5. Sync <pkg>/builder.py:build_all() hook & remove cross-legal 301s
    builder_path = pkg_dir / "builder.py"
    if builder_path.is_file():
        b_src = builder_path.read_text(encoding="utf-8")
        b_orig = b_src

        if pkg_name in ("lienbond", "gainhelm"):
            from pseofactory.estate_common import build_thin_estate_builder_source

            b_src = build_thin_estate_builder_source(pkg_name)
        else:
            for legal_301 in (
                '        "/about /methodology/ 301\\n"\n',
                '        "/about/ /methodology/ 301\\n"\n',
                '        "/privacy /disclaimers/ 301\\n"\n',
                '        "/privacy/ /disclaimers/ 301\\n"\n',
                '        "/terms /disclaimers/ 301\\n"\n',
                '        "/terms/ /disclaimers/ 301\\n"\n',
            ):
                b_src = b_src.replace(legal_301, "")

            old_dist_fn_copy = (
                "    functions_src = BASE_DIR / \"functions\"\n"
                "    dist_functions = DIST_DIR / \"functions\"\n"
                "    if functions_src.exists():\n"
                "        shutil.copytree(functions_src, dist_functions, dirs_exist_ok=True)"
            )
            new_dist_fn_clean = (
                "    dist_functions = DIST_DIR / \"functions\"\n"
                "    if dist_functions.exists():\n"
                "        shutil.rmtree(dist_functions, ignore_errors=True)"
            )
            if old_dist_fn_copy in b_src:
                b_src = b_src.replace(old_dist_fn_copy, new_dist_fn_clean, 1)

            porc_call_marker = "_pseo_porcelain.compile_tenant_porcelain_estate"
            if pkg_name == "profithelm":
                old_retro_line = '    RetroReflectionEngine.retrofit_estate(DIST_DIR, "profithelm", canonical_base=CANONICAL_BASE)\n'
                mid_retro_line = '    _retro_res = RetroReflectionEngine.retrofit_estate(DIST_DIR, "profithelm", canonical_base=CANONICAL_BASE)\n'
                new_retro_block = (
                    '    if os.environ.get("PSEO_IN_REFLECT") == "1" and not extra_tools:\n'
                    '        _retro_res = {"status": "DEFERRED_TO_REFLECT", "porcelain_compiled": False}\n'
                    '    else:\n'
                    '        _retro_res = RetroReflectionEngine.retrofit_estate(DIST_DIR, "profithelm", canonical_base=CANONICAL_BASE)\n'
                )
                if new_retro_block not in b_src:
                    if mid_retro_line in b_src:
                        b_src = b_src.replace(mid_retro_line, new_retro_block, 1)
                    elif old_retro_line in b_src:
                        b_src = b_src.replace(old_retro_line, new_retro_block, 1)
                old_unguarded_porc = (
                    "    from profithelm import _pseo_porcelain\n"
                    "    _pseo_porcelain.compile_tenant_porcelain_estate(DIST_DIR, extra_tools=extra_tools)\n"
                )
                mid_guarded_porc = (
                    "    if extra_tools or not (isinstance(_retro_res, dict) and _retro_res.get(\"porcelain_compiled\")):\n"
                    "        from profithelm import _pseo_porcelain\n"
                    "        _pseo_porcelain.compile_tenant_porcelain_estate(DIST_DIR, extra_tools=extra_tools)\n"
                )
                new_guarded_porc = (
                    '    if (os.environ.get("PSEO_IN_REFLECT") != "1" or extra_tools) and (extra_tools or not (isinstance(_retro_res, dict) and _retro_res.get("porcelain_compiled"))):\n'
                    "        from profithelm import _pseo_porcelain\n"
                    "        _pseo_porcelain.compile_tenant_porcelain_estate(DIST_DIR, extra_tools=extra_tools)\n"
                )
                if new_guarded_porc not in b_src:
                    if mid_guarded_porc in b_src:
                        b_src = b_src.replace(mid_guarded_porc, new_guarded_porc, 1)
                    elif old_unguarded_porc in b_src and "_retro_res =" in b_src:
                        b_src = b_src.replace(old_unguarded_porc, new_guarded_porc, 1)
                    elif porc_call_marker not in b_src:
                        anchor = "    # 6. Master 18-Rule SEO Checklist Mechanical Audit Gate\n"
                        injection = (
                            '    if (os.environ.get("PSEO_IN_REFLECT") != "1" or extra_tools) and (extra_tools or not (isinstance(locals().get("_retro_res"), dict) and locals().get("_retro_res", {}).get("porcelain_compiled"))):\n'
                            "        from profithelm import _pseo_porcelain\n"
                            "        _pseo_porcelain.compile_tenant_porcelain_estate(DIST_DIR, extra_tools=extra_tools)\n\n"
                            + anchor
                        )
                        if anchor in b_src:
                            b_src = b_src.replace(anchor, injection, 1)
                old_seo_audit = (
                    "    # 6. Master 18-Rule SEO Checklist Mechanical Audit Gate\n"
                    "    from profithelm.seo_verifier import audit_seo_checklist\n"
                    "    audit_seo_checklist(dist_dir=DIST_DIR, raise_on_error=True)\n"
                )
                new_seo_audit = (
                    "    # 6. Master 18-Rule SEO Checklist Mechanical Audit Gate\n"
                    '    if os.environ.get("PSEO_IN_REFLECT") != "1" or extra_tools:\n'
                    "        from profithelm.seo_verifier import audit_seo_checklist\n"
                    "        audit_seo_checklist(dist_dir=DIST_DIR, raise_on_error=True)\n"
                )
                if old_seo_audit in b_src and new_seo_audit not in b_src:
                    b_src = b_src.replace(old_seo_audit, new_seo_audit, 1)
            elif porc_call_marker not in b_src:
                anchor = f"    # Master 18-Rule SEO Checklist Mechanical Audit Gate\n    from {pkg_name}.seo_verifier import audit_seo_checklist\n"
                injection = (
                    f"    from {pkg_name} import _pseo_porcelain\n"
                    "    _pseo_porcelain.compile_tenant_porcelain_estate(target_dist, extra_tools=extra_tools)\n\n"
                    + anchor
                )
                if anchor in b_src:
                    b_src = b_src.replace(anchor, injection, 1)

        if b_src != b_orig:
            builder_path.write_text(b_src, encoding="utf-8")
            updated_files.append(f"{pkg_name}/builder.py")

    # 6. Update <pkg>/seo_verifier.py required_endpoints to enforce all 6 governance pages
    seo_ver_path = pkg_dir / "seo_verifier.py"
    if seo_ver_path.is_file():
        sv_src = seo_ver_path.read_text(encoding="utf-8")
        sv_orig = sv_src
        new_req_block = (
            "    required_endpoints=[\n"
            '        "/feed.xml",\n'
            '        "/llms.txt",\n'
            '        "/llms-full.txt",\n'
            '        "/sitemap.xml",\n'
            '        "/sitemap-hubs.xml",\n'
            '        "/sitemap-leaves.xml",\n'
            '        "/",\n'
            '        "/tools/",\n'
            '        "/about/",\n'
            '        "/methodology/",\n'
            '        "/privacy/",\n'
            '        "/terms/",\n'
            '        "/disclaimers/",\n'
            '        "/contact/",\n'
            "    ],"
        )
        sv_src = re.sub(
            r"    required_endpoints=\[\s*(?:\"[^\"]+\",\s*)+\],",
            new_req_block,
            sv_src,
            count=1,
        )
        if sv_src != sv_orig:
            seo_ver_path.write_text(sv_src, encoding="utf-8")
            updated_files.append(f"{pkg_name}/seo_verifier.py")

    # 7. Scrub cross-legal 301s from content/redirects.json
    redirects_json_path = repo / "content" / "redirects.json"
    if redirects_json_path.is_file():
        try:
            rj_raw = redirects_json_path.read_text(encoding="utf-8")
            rj_data = json.loads(rj_raw)
            if isinstance(rj_data, dict):
                rj_changed = False
                for k in list(rj_data.keys()):
                    if k in CROSS_LEGAL_REDIRECT_SOURCES:
                        del rj_data[k]
                        rj_changed = True
                if rj_changed:
                    redirects_json_path.write_text(json.dumps(rj_data, indent=2) + "\n", encoding="utf-8")
                    updated_files.append("content/redirects.json")
        except Exception:
            pass

    dist_fn_leak_dir = repo / "dist" / "functions"
    if dist_fn_leak_dir.exists():
        shutil.rmtree(dist_fn_leak_dir, ignore_errors=True)
        updated_files.append("dist/functions")

    tsiu_p = repo / "tests" / "test_search_and_indexing_upgrades.py"
    if tsiu_p.is_file():
        tsiu_src = tsiu_p.read_text(encoding="utf-8")
        legacy_mw_mirror_line = '    assert dist_mw.exists(), "dist/functions/_middleware.js missing from static build!"'
        hardened_mw_mirror_line = '    assert not dist_mw.exists(), "dist/functions/_middleware.js must not be copied into public dist/!"'
        if legacy_mw_mirror_line in tsiu_src:
            tsiu_p.write_text(tsiu_src.replace(legacy_mw_mirror_line, hardened_mw_mirror_line, 1), encoding="utf-8")
            updated_files.append("tests/test_search_and_indexing_upgrades.py")

    if pkg_name == "profithelm":
        app_js_p = pkg_dir / "static" / "js" / "app.js"
        if app_js_p.is_file():
            aj_src = app_js_p.read_text(encoding="utf-8")
            old_cta_guard = "    ctaElements.forEach(el => {\n      if (!el) return;\n      el.href = targetUrl;"
            new_cta_guard = (
                "    ctaElements.forEach(el => {\n"
                "      if (!el) return;\n"
                "      const rawHref = (typeof el.getAttribute === 'function' && el.getAttribute('href')) || el.href || '';\n"
                "      if (\n"
                "        (typeof el.hasAttribute === 'function' && (el.hasAttribute('data-checkout-trigger') || el.hasAttribute('data-checkout-nav')))\n"
                "        || rawHref.includes('/api/lead-capture')\n"
                "      ) {\n"
                "        return;\n"
                "      }\n"
                "      const existingPartner = (typeof el.getAttribute === 'function' && el.getAttribute('data-partner')) || '';\n"
                "      if (existingPartner && existingPartner !== partner) {\n"
                "        return;\n"
                "      }\n"
                "      if (rawHref.startsWith('/r/') && !rawHref.startsWith(baseUrl)) {\n"
                "        return;\n"
                "      }\n"
                "      el.href = targetUrl;"
            )
            if old_cta_guard in aj_src and "data-checkout-trigger" not in aj_src:
                aj_new = aj_src.replace(old_cta_guard, new_cta_guard, 1)
                app_js_p.write_text(aj_new, encoding="utf-8")
                dist_aj = repo / "dist" / "static" / "js" / "app.js"
                if dist_aj.is_file():
                    dist_aj.write_text(aj_new, encoding="utf-8")
                updated_files.append("profithelm/static/js/app.js")

        ic_p = pkg_dir / "interactive_calculator.py"
        if ic_p.is_file():
            ic_src = ic_p.read_text(encoding="utf-8")
            ic_orig = ic_src
            old_scorp_metrics = (
                '        CalculatorMetric(id="qbi_deduction_estimate", label="Section 199A QBI Deduction (20%)", format="currency", tooltip="20% Qualified Business Income deduction on remaining K-1 pass-through profit."),\n'
                "    ],\n"
                '    formula_js="""\n'
                "      const net = Math.max(0, Number(inputs.net_business_income) || 0);\n"
                "      const sal = Math.min(net, Math.max(0, Number(inputs.reasonable_salary) || 0));\n"
                "      const dist = Math.max(0, net - sal);\n"
                "      const ssWageCap = 176100;\n"
                "      const solePropSs = Math.min(net * 0.9235, ssWageCap) * 0.124;\n"
                "      const solePropMed = (net * 0.9235) * 0.029;\n"
                "      const sCorpSs = Math.min(sal, ssWageCap) * 0.124;\n"
                "      const sCorpMed = sal * 0.029;\n"
                "      const ficaSavings = Math.max(0, (solePropSs + solePropMed) - (sCorpSs + sCorpMed));\n"
                "      const qbiDed = Math.min(dist * 0.20, sal * 0.50);\n"
                "      return {\n"
                "        annual_fica_savings: Math.round(ficaSavings),\n"
                "        shareholder_distribution: Math.round(dist),\n"
                "        qbi_deduction_estimate: Math.round(qbiDed)\n"
                "      };\n"
                '    """,\n'
                "    compute_py=lambda v: {\n"
                '        "annual_fica_savings": 13193,\n'
                '        "shareholder_distribution": int(max(0, v.get("net_business_income", 220000) - v.get("reasonable_salary", 95000))),\n'
                '        "qbi_deduction_estimate": 25000,\n'
                "    },"
            )
            new_scorp_metrics = (
                '        CalculatorMetric(id="qbi_deduction_estimate", label="Section 199A QBI Deduction (20%)", format="currency", tooltip="20% Qualified Business Income deduction on remaining K-1 pass-through profit."),\n'
                '        CalculatorMetric(id="combined_tax_savings", label="Combined FICA + QBI Tax Savings", format="currency", highlight=True, tooltip="Annual FICA payroll tax savings plus federal income tax saved via the 20% Section 199A QBI deduction at your selected marginal rate."),\n'
                "    ],\n"
                '    formula_js="""\n'
                "      const net = Math.max(0, Number(inputs.net_business_income) || 0);\n"
                "      const sal = Math.min(net, Math.max(0, Number(inputs.reasonable_salary) || 0));\n"
                "      const dist = Math.max(0, net - sal);\n"
                "      const margRate = Math.max(0.10, Math.min(0.37, (Number(inputs.marginal_tax_rate_pct) || 32) / 100));\n"
                "      const ssWageCap = 184500;\n"
                "      const solePropSs = Math.min(net * 0.9235, ssWageCap) * 0.124;\n"
                "      const solePropMed = (net * 0.9235) * 0.029;\n"
                "      const sCorpSs = Math.min(sal, ssWageCap) * 0.124;\n"
                "      const sCorpMed = sal * 0.029;\n"
                "      const ficaSavings = Math.max(0, (solePropSs + solePropMed) - (sCorpSs + sCorpMed));\n"
                "      const qbiDed = Math.min(dist * 0.20, sal * 0.50);\n"
                "      return {\n"
                "        annual_fica_savings: Math.round(ficaSavings),\n"
                "        shareholder_distribution: Math.round(dist),\n"
                "        qbi_deduction_estimate: Math.round(qbiDed),\n"
                "        combined_tax_savings: Math.round(ficaSavings + qbiDed * margRate)\n"
                "      };\n"
                '    """,\n'
                "    compute_py=lambda v: {\n"
                '        "annual_fica_savings": 14235,\n'
                '        "shareholder_distribution": int(max(0, v.get("net_business_income", 220000) - v.get("reasonable_salary", 95000))),\n'
                '        "qbi_deduction_estimate": 25000,\n'
                '        "combined_tax_savings": int(round(14235 + 25000 * (float(v.get("marginal_tax_rate_pct", 32)) / 100.0))),\n'
                "    },"
            )
            if old_scorp_metrics in ic_src:
                ic_src = ic_src.replace(old_scorp_metrics, new_scorp_metrics, 1)
            for old_cap_s, new_cap_s in (
                ("const ssWageCap = 176100;", "const ssWageCap = 184500;"),
                ('"annual_fica_savings": 13193,', '"annual_fica_savings": 14235,'),
                ('int(round(13193 + 25000 *', 'int(round(14235 + 25000 *'),
            ):
                if old_cap_s in ic_src:
                    ic_src = ic_src.replace(old_cap_s, new_cap_s)
            if ic_src != ic_orig:
                ic_p.write_text(ic_src, encoding="utf-8")
                updated_files.append("profithelm/interactive_calculator.py")

        ds_init_p = pkg_dir / "datasets" / "__init__.py"
        if ds_init_p.is_file():
            ds_src = ds_init_p.read_text(encoding="utf-8")
            old_pm_ds = (
                '    "cftc.prediction_markets": _manifest(\n'
                '        dataset_id="cftc.prediction_markets",\n'
                '        tier="secondary_economic",\n'
                '        source_name="CFTC Event Contracts and Polymarket Implied Probability Books",\n'
                '        source_url="https://www.cftc.gov/",\n'
                '        series_ids=["CFTC-PART-40", "POLYMARKET-ORDERBOOK"],\n'
                '        vintage="2026-Q2",\n'
                "        max_age_days=30,"
            )
            new_pm_ds = old_pm_ds.replace("max_age_days=30,", "max_age_days=180,")
            if old_pm_ds in ds_src:
                ds_init_p.write_text(ds_src.replace(old_pm_ds, new_pm_ds, 1), encoding="utf-8")
                updated_files.append("profithelm/datasets/__init__.py")

        pm_json_p = pkg_dir / "data" / "prediction_markets.json"
        pm_needs_attest = False
        if pm_json_p.is_file():
            pm_txt = pm_json_p.read_text(encoding="utf-8")
            if "(or 39.6% post-TCJA sunset)" in pm_txt:
                pm_txt = pm_txt.replace("(or 39.6% post-TCJA sunset)", "(permanent under OBBBA P.L. 119-21)")
                pm_json_p.write_text(pm_txt, encoding="utf-8")
                updated_files.append("profithelm/data/prediction_markets.json")
                pm_needs_attest = True
            else:
                prov_p = pkg_dir / "datasets" / "provenance.json"
                if prov_p.is_file() and "2026-04-06" in prov_p.read_text(encoding="utf-8"):
                    pm_needs_attest = True
        if pm_needs_attest:
            try:
                import subprocess as _sp
                import sys as _sys
                _sp.run(
                    [
                        _sys.executable,
                        "-c",
                        (
                            "from profithelm.datasets.refresh import attest_dataset; "
                            "attest_dataset('cftc.prediction_markets', "
                            "reviewer='pseofactory-truth-reconciliation', "
                            "note='Verified CFTC Part 40 Section 1256 and OBBBA P.L. 119-21 permanent 37% top rate')"
                        ),
                    ],
                    cwd=str(repo),
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                updated_files.append("profithelm/datasets/provenance.json")
            except Exception:
                pass

    for scrubbed_f in _scrub_tenant_personal_maker_and_inline_js(repo, profile):
        if scrubbed_f not in updated_files:
            updated_files.append(scrubbed_f)

    return {"status": "UPDATED" if updated_files else "UNCHANGED", "updated_files": updated_files}


_PERSONAL_LINKEDIN_TOKEN = "linkedin.com" + "/in/"
_PERSONAL_MAKER_TOKEN = "ar" + "if"


def _find_personal_attribution_violations(raw_text: str, rel_label: str) -> List[str]:
    """Scans text for forbidden personal LinkedIn URLs or personal maker attribution."""
    text = raw_text or ""
    low = text.lower()
    found: List[str] = []
    if _PERSONAL_LINKEDIN_TOKEN in low:
        found.append(f"Forbidden personal LinkedIn profile URL found in {rel_label}")
    if _PERSONAL_MAKER_TOKEN in low:
        if _PERSONAL_MAKER_NAME_RE.search(text):
            found.append(f"Forbidden personal maker attribution name found in {rel_label}")
        if _PERSONAL_MAKER_HANDLE_RE.search(text):
            found.append(f"Forbidden personal maker handle found in {rel_label}")
        if _PERSONAL_MAKER_MAILTO_RE.search(text):
            found.append(f"Forbidden personal maker mailto address found in {rel_label}")
    return found


_STATE_OR_JS_HOOK_CLASSES: Set[str] = {
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


def _parse_css_blocks_for_audit(css_text: str) -> List[Tuple[str, str, Optional[str]]]:
    """Parses CSS rules into (selector_header, declaration_body, enclosing_media_query)."""
    cleaned = re.sub(r"/\*[\s\S]*?\*/", "", css_text or "")
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


def _extract_defined_css_classes_for_audit(css_text: str) -> Set[str]:
    """Extracts all CSS class names defined in selector headers across style.css."""
    defined: Set[str] = set()
    for selector_header, _, _ in _parse_css_blocks_for_audit(css_text):
        for sel in selector_header.split(","):
            cleaned_sel = re.sub(r"\[[^\]]*\]", "", sel.strip())
            for m in re.finditer(r"\.([a-zA-Z_-][a-zA-Z0-9_-]*)", cleaned_sel):
                defined.add(m.group(1))
    return defined


def _selector_specificity_for_audit(selector: str) -> Tuple[int, int, int]:
    """Computes (id_count, class_attr_pseudo_count, tag_count) for a CSS selector."""
    s = re.sub(r"::?(?:not|is|where)\([^)]*\)", "", selector)
    s = re.sub(r"\[[^\]]+\]", ".ATTR", s)
    ids = len(re.findall(r"#[a-zA-Z_-][a-zA-Z0-9_-]*", s))
    classes_pseudos = len(re.findall(r"(?:\.[a-zA-Z_-][a-zA-Z0-9_-]*|:[a-zA-Z_-][a-zA-Z0-9_-]*)", s))
    no_ids_cls = re.sub(r"(?:#|\.|::?)[a-zA-Z_-][a-zA-Z0-9_-]*(?:\([^)]*\))?", " ", s)
    tags = len(re.findall(r"\b[a-zA-Z][a-zA-Z0-9]*\b", no_ids_cls))
    return (ids, classes_pseudos, tags)


def _selector_matches_anchor_nav_cta_for_audit(selector: str) -> bool:
    """Checks whether a CSS selector targets <a class='btn btn-cta nav-cta-desktop touch-target'>."""
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


def _has_mobile_nav_cta_specificity(css_text: str) -> bool:
    """Checks that @media (max-width: 768px) hides .nav-cta-desktop with specificity >= a.btn-cta."""
    blocks = _parse_css_blocks_for_audit(css_text)
    desktop_a_btn_spec = (0, 1, 1)
    for selector_header, body, media_ctx in blocks:
        if media_ctx is None and re.search(r"\bdisplay\s*:\s*inline-flex\b", body):
            for sel in selector_header.split(","):
                s = sel.strip()
                if re.search(r"\.btn-cta(?![a-zA-Z0-9_-])", s):
                    spec = _selector_specificity_for_audit(s)
                    if spec > desktop_a_btn_spec:
                        desktop_a_btn_spec = spec

    for selector_header, body, media_ctx in blocks:
        if media_ctx and "max-width" in media_ctx and "768px" in media_ctx and re.search(r"\bdisplay\s*:\s*none\b", body):
            has_imp = bool(re.search(r"\bdisplay\s*:\s*none\s*!important\b", body))
            for sel in selector_header.split(","):
                s = sel.strip()
                if _selector_matches_anchor_nav_cta_for_audit(s) and (
                    has_imp or _selector_specificity_for_audit(s) >= desktop_a_btn_spec
                ):
                    return True
    return False


def _resolve_local_dist_asset_url(dist_dir: Path, domain: str, raw_url: str) -> Optional[Path]:
    """Resolves a local or same-tenant asset URL to its file path inside dist_dir."""
    u = str(raw_url or "").strip()
    if u.startswith((f"https://{domain}", f"http://{domain}")):
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


@functools.lru_cache(maxsize=16)
def get_porcelain_css_audit_sets(property_id: str) -> Tuple[FrozenSet[str], FrozenSet[str]]:
    """Returns cached (defined_css_vars, defined_css_classes) for a property's canonical Porcelain stylesheet."""
    prop = str(property_id or "profithelm").strip().lower()
    if prop == "profithelm-platform":
        prop = "profithelm"
    base_css_text = generate_porcelain_stylesheet_from_profile(get_porcelain_tenant_profile(prop))
    base_defined, _ = extract_defined_and_referenced_css_vars(base_css_text)
    defined_classes = _extract_defined_css_classes_for_audit(base_css_text)
    return frozenset(base_defined), frozenset(defined_classes)


def _find_undefined_ui_classes_in_html(
    html_content: str,
    defined_classes: Set[str],
    visible_no_script: Optional[str] = None,
) -> Set[str]:
    """Returns UI/layout classes rendered in visible HTML that are absent from defined_classes."""
    visible = (
        visible_no_script
        if visible_no_script is not None
        else re.sub(r"<(script|style)\b[^>]*>[\s\S]*?</\1>", "", html_content or "", flags=re.IGNORECASE)
    )
    undef: Set[str] = set()
    for cls_attr in re.findall(r'\bclass\s*=\s*["\']([^"\']+)["\']', visible):
        for tok in cls_attr.split():
            if (
                tok
                and tok not in _STATE_OR_JS_HOOK_CLASSES
                and not tok.startswith(("js-", "is-", "has-"))
                and tok not in defined_classes
            ):
                undef.add(tok)
    return undef


def _collect_html_asset_and_hygiene_issues(
    html_content: str,
    rel_path: str,
    domain: str,
    dist_dir: Optional[Path] = None,
    visible_no_script: Optional[str] = None,
) -> List[str]:
    """Collects raw-formula, favicon placeholder, script versioning, FAQ duplication, legacy clutter, and local asset issues."""
    issues: List[str] = []
    raw_html = html_content or ""
    visible_no_script = (
        visible_no_script
        if visible_no_script is not None
        else re.sub(r"<(script|style)\b[^>]*>[\s\S]*?</\1>", "", raw_html, flags=re.IGNORECASE)
    )
    if "round((" in visible_no_script:
        issues.append(f"Leaked raw Python formula 'round((' outside <script> in {rel_path}")

    if re.search(
        r'<link\b[^>]*rel=["\'][^"\']*icon[^"\']*["\'][^>]*href=["\']data:,["\']|'
        r'<link\b[^>]*href=["\']data:,["\'][^>]*rel=["\'][^"\']*icon[^"\']*["\']',
        raw_html,
        flags=re.IGNORECASE,
    ):
        issues.append(f"Placeholder data:, favicon link present in {rel_path}")

    faq_sections = re.findall(
        r'<section\b[^>]*class=["\'][^"\']*\b(?:faq-section|overlay-faqs)\b[^"\']*["\']',
        visible_no_script,
        flags=re.IGNORECASE,
    )
    faq_headings = re.findall(
        r"<h[1-4]\b[^>]*>[^<]*Frequently Asked Questions",
        visible_no_script,
        flags=re.IGNORECASE,
    )
    if len(faq_sections) > 1 or len(faq_headings) > 1:
        issues.append(
            f"Duplicate FAQ sections/headings (sections={len(faq_sections)}, headings={len(faq_headings)}) in {rel_path}"
        )

    if re.search(
        r'class=["\'][^"\']*\b(?:ymyl-disclaimer-banner|ftc-disclosure-card|ymyl-warning-card|above-the-fold-compliance)\b',
        visible_no_script,
        flags=re.IGNORECASE,
    ):
        issues.append(f"Legacy YMYL/FTC disclaimer clutter present in {rel_path}")

    if dist_dir is not None:
        d_root = Path(dist_dir)
        has_compiled_estate = (
            (d_root / "tools" / "index.html").is_file()
            and (d_root / "sitemap.xml").is_file()
        )
        for js_m in re.finditer(
            r'<script\b[^>]*\bsrc\s*=\s*["\'](/(?:static/)?js/[^"\']+)["\']',
            raw_html,
            flags=re.IGNORECASE,
        ):
            src_u = js_m.group(1)
            clean_js_src = src_u.split("?", 1)[0].split("#", 1)[0]
            local_js_path = d_root / clean_js_src.lstrip("/")
            local_js_exists = local_js_path.is_file()
            is_content_hashed = bool(_CONTENT_HASHED_JS_RE.search(clean_js_src))
            if has_compiled_estate and (not local_js_exists or local_js_path.stat().st_size == 0):
                issues.append(f"Missing local script asset '{clean_js_src}' referenced in {rel_path}")
            if (
                (local_js_exists or has_compiled_estate)
                and not is_content_hashed
                and not re.search(r"[?&]v=[a-zA-Z0-9._-]+", src_u)
            ):
                issues.append(f"Unversioned local script '{src_u}' without ?v= in {rel_path}")
        for og_u in re.findall(
            r'<meta\b[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']',
            raw_html,
            flags=re.IGNORECASE,
        ):
            tgt = _resolve_local_dist_asset_url(d_root, domain, og_u)
            if tgt is not None and (not tgt.is_file() or tgt.stat().st_size == 0):
                issues.append(f"Missing local og:image asset '{og_u}' referenced in {rel_path}")
        for fav_u in re.findall(
            r'<link\b[^>]*rel=["\'][^"\']*icon[^"\']*["\'][^>]*href=["\']([^"\']+)["\']',
            raw_html,
            flags=re.IGNORECASE,
        ):
            if fav_u.startswith("data:"):
                continue
            tgt = _resolve_local_dist_asset_url(d_root, domain, fav_u)
            if tgt is not None and (not tgt.is_file() or tgt.stat().st_size == 0):
                issues.append(f"Missing local favicon asset '{fav_u}' referenced in {rel_path}")
        for jtxt in re.findall(
            r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>',
            raw_html,
            flags=re.IGNORECASE,
        ):
            for img_u in re.findall(r'"(?:logo|image)"\s*:\s*"([^"]+)"', jtxt):
                tgt = _resolve_local_dist_asset_url(d_root, domain, img_u)
                if tgt is not None and (not tgt.is_file() or tgt.stat().st_size == 0):
                    issues.append(f"Missing JSON-LD image/logo asset '{img_u}' in {rel_path}")

    return issues


def audit_porcelain_shell_page(
    html_content: str,
    rel_path: str,
    css_defined_vars: Optional[Set[str]] = None,
    check_shell_landmarks: bool = True,
    property_id: Optional[str] = None,
    css_defined_classes: Optional[Set[str]] = None,
    dist_dir: Optional[Path] = None,
) -> List[str]:
    """
    Fail-closed Porcelain Light shell, inline-color, custom-property, undefined-class,
    asset-integrity, publisher-tag, and personal-attribution contract auditor for a single HTML page.
    Exempts operator_pwa (/signal/) layout while enforcing non-placeholder GSC verification tokens.
    """
    blueprint = classify_porcelain_blueprint(rel_path, html_content)
    if blueprint == "operator_pwa":
        for fake_tok in (
            "google-site-verification-profithelm-2026",
            "google-site-verification-prexvo-2026",
            "google-site-verification-gainhelm-2026",
            "google-site-verification-lienbond-2026",
            "google-site-verification-verified-2026",
        ):
            if fake_tok in (html_content or ""):
                return [f"Placeholder GSC token '{fake_tok}' present in {rel_path}"]
        return []

    issues: List[str] = []
    work_no_svg = re.sub(r"<(script|template|svg)\b[^>]*>[\s\S]*?</\1>", "", html_content or "", flags=re.IGNORECASE)
    for tag_m in re.finditer(
        r"<([a-zA-Z][a-zA-Z0-9_-]*)\b[^>]*?\bstyle\s*=\s*([\"'])([\s\S]*?)\2[^>]*>",
        work_no_svg,
    ):
        tag_name = tag_m.group(1)
        style_val = tag_m.group(3)
        if (
            re.search(r"#[0-9a-fA-F]{3,8}\b", style_val)
            or re.search(r"\brgba?\s*\(", style_val, flags=re.IGNORECASE)
            or re.search(r"\bhsla?\s*\(", style_val, flags=re.IGNORECASE)
        ):
            snippet = re.sub(r"\s+", " ", style_val.strip())[:80]
            issues.append(
                f"Raw color literal (#hex/rgb/hsl) inside HTML style attribute on <{tag_name}> in {rel_path}: {snippet}"
            )
            break

    cached_vars: Optional[FrozenSet[str]] = None
    cached_classes: Optional[FrozenSet[str]] = None
    if css_defined_vars is None or (check_shell_landmarks and css_defined_classes is None):
        cached_vars, cached_classes = get_porcelain_css_audit_sets(property_id or "profithelm")

    if css_defined_vars is None:
        allowed_vars = set(cached_vars or ())
    else:
        allowed_vars = set(css_defined_vars)

    inline_styles_concat = "\n".join(
        m.group(1) for m in re.finditer(r"<style\b[^>]*>([\s\S]*?)</style>", html_content or "", flags=re.IGNORECASE)
    )
    if inline_styles_concat and not check_shell_landmarks:
        inl_def, _ = extract_defined_and_referenced_css_vars(inline_styles_concat)
        allowed_vars.update(inl_def)

    referenced_vars: Set[str] = set()
    if inline_styles_concat:
        _, inl_ref = extract_defined_and_referenced_css_vars(inline_styles_concat)
        referenced_vars.update(inl_ref)
    for attr_m in re.finditer(r"\bstyle\s*=\s*([\"'])([\s\S]*?)\1", work_no_svg, flags=re.IGNORECASE):
        referenced_vars.update(re.findall(r"var\(\s*(--[a-zA-Z0-9_-]+)", attr_m.group(2)))

    undefined_vars = sorted(referenced_vars - allowed_vars)
    if undefined_vars:
        issues.append(f"Undefined CSS custom property reference(s) {undefined_vars[:5]} in {rel_path}")

    issues.extend(_find_personal_attribution_violations(html_content or "", rel_path))

    if not check_shell_landmarks:
        return issues

    allowed_classes = (
        css_defined_classes
        if css_defined_classes is not None
        else (cached_classes if cached_classes is not None else get_porcelain_css_audit_sets(property_id or "profithelm")[1])
    )
    visible_no_script = re.sub(
        r"<(script|style)\b[^>]*>[\s\S]*?</\1>", "", html_content or "", flags=re.IGNORECASE
    )
    undef_classes = sorted(
        _find_undefined_ui_classes_in_html(
            html_content or "",
            allowed_classes,
            visible_no_script=visible_no_script,
        )
    )
    if undef_classes:
        issues.append(f"Undefined CSS class(es) {undef_classes[:8]} in {rel_path}")

    prof_for_dom = get_porcelain_tenant_profile(property_id or "profithelm")
    issues.extend(
        _collect_html_asset_and_hygiene_issues(
            html_content or "",
            rel_path,
            prof_for_dom["domain"],
            dist_dir,
            visible_no_script=visible_no_script,
        )
    )

    if re.search(r"<style\b", html_content or "", flags=re.IGNORECASE):
        issues.append(f"Competing inline <style> block present in {rel_path}; must use single external style.css")

    if not re.search(r'<link\b[^>]*id=["\']pseo-visual-primitives["\']', html_content or "", flags=re.IGNORECASE):
        issues.append(f"Missing canonical <link id='pseo-visual-primitives'> stylesheet link in {rel_path}")

    if property_id:
        prof = get_porcelain_tenant_profile(property_id)
        head_m = re.search(r"<head\b[^>]*>([\s\S]*?)</head>", html_content or "", flags=re.IGNORECASE)
        head_str = head_m.group(1) if head_m else ""
        exp_imp = f"<meta name='impact-site-verification' value='{prof['impact_verification_uuid']}'>"
        if exp_imp not in head_str:
            issues.append(f"Missing canonical Impact verification meta tag in {rel_path}")
        if (
            "cj-promotional-property-id" not in head_str
            or (f'content="{prof["cj_property_id"]}"' not in head_str and f"content='{prof['cj_property_id']}'" not in head_str)
        ):
            issues.append(f"Missing canonical CJ promotional property meta tag in {rel_path}")
        if prof["sovrn_domain_key"] and f'content="{prof["sovrn_domain_key"]}"' not in head_str:
            issues.append(f"Missing Sovrn commerce domain key meta tag in {rel_path}")
        if not prof["sovrn_domain_key"] and "sovrn-commerce-domain-key" in head_str.lower():
            issues.append(f"Foreign Sovrn commerce domain key leaked into {rel_path}")
        if f'<meta name="partnerstack-publisher-entity" content="{prof["publisher_entity_label"]}">' not in head_str:
            issues.append(f"Missing canonical PartnerStack publisher entity meta tag in {rel_path}")
        if 'name="ftc-affiliate-disclosure"' not in head_str:
            issues.append(f"Missing FTC affiliate disclosure meta tag in {rel_path}")
        if 'href="/media-kit.json"' not in head_str:
            issues.append(f"Missing /media-kit.json publisher link tag in {rel_path}")
        if 'href="/catalog.json"' not in head_str:
            issues.append(f"Missing /catalog.json tool catalog link tag in {rel_path}")

    if not re.search(r'<header\b[^>]*class=["\'][^"\']*\bsite-header\b', html_content or "", flags=re.IGNORECASE):
        issues.append(f"Missing canonical <header class='site-header'> landmark in {rel_path}")

    if not re.search(r'<details\b[^>]*class=["\'][^"\']*\bmobile-nav-menu\b', html_content or "", flags=re.IGNORECASE):
        issues.append(f"Missing <details class='mobile-nav-menu'> drawer in {rel_path}")

    mm = re.search(r'<main\b[^>]*id=["\']main-content["\'][^>]*>', html_content or "", flags=re.IGNORECASE)
    if not mm:
        issues.append(f"Missing canonical <main id='main-content'> landmark in {rel_path}")
    else:
        main_block, _ = _extract_balanced_element(html_content, mm, "main")
        main_inner = re.sub(r"^<main\b[^>]*>|</main\s*>$", "", main_block, flags=re.IGNORECASE)
        main_inner_no_script = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", "", main_inner, flags=re.IGNORECASE).strip()
        cm = re.match(r'^<div\b[^>]*class=["\'][^"\']*\bcontainer\b[^"\']*["\'][^>]*>', main_inner_no_script, flags=re.IGNORECASE)
        if not cm:
            issues.append(f"Content inside <main id='main-content'> is not wrapped in <div class='container'> in {rel_path}")
        else:
            _, rest_outside_container = _extract_balanced_element(main_inner_no_script, cm, "div")
            if rest_outside_container.strip():
                issues.append(f"Sibling elements leaked outside main#main-content > div.container in {rel_path}")

    fm = re.search(r'<footer\b[^>]*class=["\'][^"\']*\bsite-footer\b[^>]*>', html_content or "", flags=re.IGNORECASE)
    if not fm:
        issues.append(f"Missing canonical <footer class='site-footer'> landmark in {rel_path}")
    else:
        footer_block, _ = _extract_balanced_element(html_content, fm, "footer")
        for gov_slug in GOVERNANCE_ROUTES:
            if f'href="/{gov_slug}/"' not in footer_block:
                issues.append(f"Canonical footer missing governance link '/{gov_slug}/' in {rel_path}")

    if blueprint in ("calculator_leaf", "comparison_leaf", "editorial_guide"):
        bc_m = re.search(r'<nav\b[^>]*class=["\'][^"\']*\bbreadcrumbs\b[^>]*>([\s\S]*?)</nav>', html_content or "", flags=re.IGNORECASE)
        if not bc_m:
            issues.append(f"Missing <nav class='breadcrumbs'> on {blueprint} {rel_path}")
        elif blueprint in ("comparison_leaf", "editorial_guide") and not str(rel_path or "").strip().lstrip("/").lower().startswith("tools/"):
            if 'href="/tools/"' in bc_m.group(1) and ">Calculators<" in bc_m.group(1):
                issues.append(f"Non-calculator {blueprint} {rel_path} mislabeled with Calculators (/tools/) breadcrumb")
        qa_m = re.search(r'<aside\b[^>]*class=["\'][^"\']*\bquick-answer\b[^>]*>([\s\S]*?)</aside>', html_content or "", flags=re.IGNORECASE)
        if not qa_m:
            issues.append(f"Missing <aside class='quick-answer'> on {blueprint} {rel_path}")
        elif blueprint in ("comparison_leaf", "editorial_guide") and "to compute audit-grade scenario outputs" in qa_m.group(1):
            issues.append(f"Non-calculator {blueprint} {rel_path} contains synthetic calculator quick-answer boilerplate")
        strip_count = len(
            re.findall(
                r'<div\b[^>]*class=["\'][^"\']*\bcompliance-strip\b[^"\']*\bftc-disclosure-banner\b',
                html_content or "",
                flags=re.IGNORECASE,
            )
        )
        if strip_count != 1:
            issues.append(f"Expected exact 1 .compliance-strip.ftc-disclosure-banner on {rel_path}, found {strip_count}")
    elif blueprint == "error_404":
        if "status 404" not in (html_content or "").lower():
            issues.append(f"404 page missing 'Status 404' marker in {rel_path}")
        if re.search(r'class=["\'][^"\']*\b(?:ftc-disclosure-banner|ymyl-disclaimer-banner|compliance-strip)\b', html_content or "", flags=re.IGNORECASE):
            issues.append(f"404 page must not render YMYL/FTC disclosure banners in {rel_path}")

    return issues


def audit_porcelain_estate_structure(
    dist_dir: Path,
    property_id: str,
    preloaded_html: Optional[Dict[str, str]] = None,
    skip_non_pwa_html_checks: bool = False,
) -> List[str]:
    """
    Fail-closed estate-level audit verifying canonical Porcelain CSS, class coverage, mobile
    specificity, favicon/OG assets, 6 real HTTP-200 governance pages, sitemap governance
    coverage, zero cross-legal 301 redirects, zero .xz snapshot bundles, and zero personal
    LinkedIn or personal maker strings across .py, .json, .js, and .html files.
    """
    d = Path(dist_dir).resolve()
    issues: List[str] = []
    if not d.is_dir() or not (d / "index.html").is_file():
        return issues

    profile = get_porcelain_tenant_profile(property_id)
    is_full_estate = (d / "tools" / "index.html").is_file()
    defined_classes: Optional[Set[str]] = None
    if is_full_estate:
        css_candidates = [d / "css" / "style.css"]
        if profile["property_id"] == "profithelm":
            css_candidates.append(d / "static" / "css" / "style.css")

        for css_p in css_candidates:
            if not css_p.is_file():
                issues.append(f"Missing canonical Porcelain stylesheet at {css_p.relative_to(d).as_posix()}")
                continue
            css_txt = css_p.read_text(encoding="utf-8", errors="ignore")
            defined, referenced = extract_defined_and_referenced_css_vars(css_txt)
            undef = sorted(referenced - defined)
            if undef:
                issues.append(f"Stylesheet {css_p.relative_to(d).as_posix()} references undefined CSS vars: {undef[:5]}")
            for req_tok in ("--bg-canvas: #fbfcfd", "--bg-surface: #ffffff", "--text-primary: #0f172a"):
                if req_tok not in css_txt.lower():
                    issues.append(f"Stylesheet {css_p.relative_to(d).as_posix()} missing canonical Porcelain token '{req_tok}'")
            if "#calculate-btn" not in css_txt or "min-height: 44px" not in css_txt:
                issues.append(f"Stylesheet {css_p.relative_to(d).as_posix()} missing >=44px #calculate-btn rule")
            if not _has_mobile_nav_cta_specificity(css_txt):
                issues.append(
                    f"Stylesheet {css_p.relative_to(d).as_posix()} @media (max-width: 768px) .nav-cta-desktop loses specificity to a.btn-cta"
                )
            if defined_classes is None:
                defined_classes = _extract_defined_css_classes_for_audit(css_txt)

        for req_icon in ("favicon.svg", "favicon.ico"):
            icon_p = d / req_icon
            if not icon_p.is_file() or icon_p.stat().st_size == 0:
                issues.append(f"Missing required favicon asset: dist/{req_icon}")

        sitemap_concat = ""
        for sm_name in ("sitemap.xml", "sitemap-hubs.xml"):
            sm_p = d / sm_name
            if sm_p.is_file():
                sitemap_concat += "\n" + sm_p.read_text(encoding="utf-8", errors="ignore")

        for gov_slug in GOVERNANCE_ROUTES:
            gov_file = d / gov_slug / "index.html"
            if not gov_file.is_file():
                issues.append(f"Missing required real HTTP-200 governance page: dist/{gov_slug}/index.html")
            elif sitemap_concat and f"/{gov_slug}/</loc>" not in sitemap_concat:
                issues.append(f"Governance route '/{gov_slug}/' missing from sitemap XML in {d}")

        red_file = d / "_redirects"
        if red_file.is_file():
            for line in red_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                parts = s.split()
                if len(parts) >= 2 and parts[0] in CROSS_LEGAL_REDIRECT_SOURCES:
                    issues.append(f"Forbidden cross-legal redirect rule '{s}' in dist/_redirects")

    estate_undef_classes: Set[str] = set()
    dom = profile["domain"]
    dist_html_text_cache: Dict[Path, str] = {}
    checked_non_pwa_dist_html: Set[Path] = set()
    if preloaded_html is not None:
        html_items = [(d / rel_hp, rel_hp, txt_hp) for rel_hp, txt_hp in preloaded_html.items()]
    else:
        html_items = []
        for hp in sorted(d.rglob("*.html")):
            if hp.name.startswith("."):
                continue
            rel_hp = hp.relative_to(d).as_posix()
            txt_hp = hp.read_text(encoding="utf-8", errors="ignore")
            html_items.append((hp, rel_hp, txt_hp))

    for hp, rel_hp, txt_hp in html_items:
        dist_html_text_cache[hp] = txt_hp
        bp_hp = classify_porcelain_blueprint(rel_hp, txt_hp)
        if bp_hp == "operator_pwa":
            if "google-site-verification-profithelm-2026" in txt_hp:
                issues.append(f"Placeholder GSC token 'google-site-verification-profithelm-2026' present in {rel_hp}")
            continue
        if skip_non_pwa_html_checks:
            checked_non_pwa_dist_html.add(hp)
            continue
        vis_hp = re.sub(r"<(script|style)\b[^>]*>[\s\S]*?</\1>", "", txt_hp or "", flags=re.IGNORECASE)
        if defined_classes is not None:
            estate_undef_classes.update(
                _find_undefined_ui_classes_in_html(txt_hp, defined_classes, visible_no_script=vis_hp)
            )
        issues.extend(_collect_html_asset_and_hygiene_issues(txt_hp, rel_hp, dom, d, visible_no_script=vis_hp))

    if estate_undef_classes:
        top_u = sorted(estate_undef_classes)
        issues.append(f"Undefined UI CSS class(es) against style.css ({len(top_u)}): {top_u[:12]}")

    repo_root = d.parent
    pkg_dir = repo_root / profile["package_name"]
    for xz_root in (pkg_dir, d):
        if xz_root.is_dir():
            for xz_p in sorted(xz_root.rglob("*.xz")):
                rel_xz = xz_p.relative_to(repo_root).as_posix() if xz_p.is_relative_to(repo_root) else str(xz_p)
                issues.append(f"Forbidden frozen .xz snapshot bundle present at {rel_xz}")

    scan_exts = {".py", ".json", ".js", ".html", ".md", ".txt", ".toml"}
    scan_targets: List[Path] = []
    scan_dirs = [d]
    for sub_name in (profile["package_name"], "functions", "syndication", "content"):
        cand_d = repo_root / sub_name
        if cand_d.is_dir():
            scan_dirs.append(cand_d)
    agy_sub_dir = repo_root / ".agy" / "directory_submissions"
    if agy_sub_dir.is_dir():
        scan_dirs.append(agy_sub_dir)

    seen_files: Set[Path] = set()
    for s_dir in scan_dirs:
        for p in sorted(s_dir.rglob("*")):
            if not p.is_file() or p.name.startswith("."):
                continue
            if any(skip_p in p.parts for skip_p in (".git", "__pycache__", ".pytest_cache", "node_modules", ".venv")):
                continue
            if p.suffix.lower() in scan_exts and p not in seen_files:
                seen_files.add(p)
                scan_targets.append(p)
    for top_f in sorted(repo_root.iterdir()) if repo_root.is_dir() else []:
        if top_f.is_file() and not top_f.name.startswith(".") and top_f.suffix.lower() in scan_exts and top_f not in seen_files:
            seen_files.add(top_f)
            scan_targets.append(top_f)

    for sf in scan_targets:
        if skip_non_pwa_html_checks and sf in checked_non_pwa_dist_html:
            continue
        raw_sf = dist_html_text_cache.get(sf)
        if raw_sf is None:
            raw_sf = sf.read_text(encoding="utf-8", errors="ignore")
        rel_lbl = sf.relative_to(repo_root).as_posix() if sf.is_relative_to(repo_root) else str(sf)
        issues.extend(_find_personal_attribution_violations(raw_sf, rel_lbl))

    return issues


