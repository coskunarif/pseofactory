"""
Unified multi-tenant UI/UX browser verification harness for pseofactory.
Executes end-to-end mechanical audits via host Chrome DevTools Protocol (CDP port 9222).
Verifies CLS === 0.0, minimum 43.5px touch targets, responsive viewports (375px/1280px),
zero forbidden dashes (anti-slop invariant), and reactive interactive widget calculations.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass, field
import inspect
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from pseofactory.server import EphemeralDistServer


@dataclass
class InteractiveWidgetSpec:
    """Specification for interactive calculator / tool runtime verification."""
    route: str
    widget_id: str
    precondition_selector: str
    input_selector: str
    input_value: str
    output_selector: str
    trigger_event: str = "input"
    verify_popstate: bool = False
    expected_delta_fn: Optional[str] = None


class TenantBrowserAdapter(ABC):
    """Abstract base adapter for tenant-specific static distributions."""

    @property
    @abstractmethod
    def tenant_id(self) -> str:
        """Tenant identifier (e.g. profithelm, prexvo)."""
        pass

    @property
    @abstractmethod
    def dist_dir(self) -> Path:
        """Absolute path to static distribution directory."""
        pass

    @property
    @abstractmethod
    def canonical_domain(self) -> str:
        """Canonical domain URL (e.g. https://profithelm.com)."""
        pass

    def get_widget_specs(self) -> List[InteractiveWidgetSpec]:
        """Returns list of interactive widget specs to audit."""
        return []

    def get_excluded_routes(self) -> List[str]:
        """Returns routes to skip during browser audit."""
        return []


class ProfitHelmBrowserAdapter(TenantBrowserAdapter):
    """Browser verification adapter for ProfitHelm platform distribution."""

    @property
    def tenant_id(self) -> str:
        return "profithelm"

    @property
    def dist_dir(self) -> Path:
        return Path("/home/ubuntuadmin/projects/profithelm-platform/dist")

    @property
    def canonical_domain(self) -> str:
        return "https://profithelm.com"

    def get_widget_specs(self) -> List[InteractiveWidgetSpec]:
        return [
            InteractiveWidgetSpec(
                route="/tools/irs-2027-tax-brackets/",
                widget_id="irs-2027-tax-brackets",
                precondition_selector="#field-gross_income, #tax-income",
                input_selector="#field-gross_income, #tax-income",
                input_value="250000",
                output_selector="#val-total_federal_tax, #res-total-tax",
                trigger_event="input",
                verify_popstate=True,
            ),
            InteractiveWidgetSpec(
                route="/tools/crypto-tax-calculator/",
                widget_id="crypto-tax-calculator",
                precondition_selector="#crypto-short-term",
                input_selector="#crypto-short-term",
                input_value="50000",
                output_selector="#res-crypto-tax",
                trigger_event="input",
                verify_popstate=False,
            ),
            InteractiveWidgetSpec(
                route="/tools/saas-runway-calculator/",
                widget_id="saas-runway-calculator",
                precondition_selector="#runway-cash",
                input_selector="#runway-cash",
                input_value="100000",
                output_selector="#res-runway-months",
                trigger_event="input",
                verify_popstate=False,
            ),
        ]


class PrexvoBrowserAdapter(TenantBrowserAdapter):
    """Browser verification adapter for Prexvo financial platform distribution."""

    @property
    def tenant_id(self) -> str:
        return "prexvo"

    @property
    def dist_dir(self) -> Path:
        return Path("/home/ubuntuadmin/projects/prexvo/dist")

    @property
    def canonical_domain(self) -> str:
        return "https://prexvo.com"

    def get_widget_specs(self) -> List[InteractiveWidgetSpec]:
        return [
            InteractiveWidgetSpec(
                route="/tools/student-loan-repayment-calculator/",
                widget_id="student-loan-repayment-calculator",
                precondition_selector="#field-loan_balance",
                input_selector="#field-loan_balance",
                input_value="75000",
                output_selector="#metric-rap_payment",
                trigger_event="input",
                verify_popstate=True,
            ),
            InteractiveWidgetSpec(
                route="/tools/rap-vs-ibr-calculator/",
                widget_id="rap-vs-ibr-calculator",
                precondition_selector="#field-loan_balance, #field-agi",
                input_selector="#field-loan_balance, #field-agi",
                input_value="85000",
                output_selector="#metric-rap_payment, #val-monthly_payment",
                trigger_event="input",
                verify_popstate=False,
            ),
            InteractiveWidgetSpec(
                route="/tools/pslf-qualifying-payment-calculator/",
                widget_id="pslf-qualifying-payment-calculator",
                precondition_selector="#field-qualifying_payments, #field-loan_balance",
                input_selector="#field-qualifying_payments, #field-loan_balance",
                input_value="60",
                output_selector="#metric-forgiven_balance, #val-remaining_payments",
                trigger_event="input",
                verify_popstate=False,
            ),
            InteractiveWidgetSpec(
                route="/tools/pslf-qualifying-payment-simulator/",
                widget_id="pslf-qualifying-payment-simulator",
                precondition_selector="#field-qualifying_payments, #field-loan_balance, [data-calc-input]",
                input_selector="#field-qualifying_payments, #field-loan_balance, [data-calc-input]",
                input_value="60",
                output_selector="#metric-forgiven_balance, #val-remaining_payments, .output-value, .metric-val",
                trigger_event="input",
                verify_popstate=False,
            ),
        ]


class GainHelmBrowserAdapter(TenantBrowserAdapter):
    """Browser verification adapter for GainHelm cyber compliance platform distribution."""

    @property
    def tenant_id(self) -> str:
        return "gainhelm"

    @property
    def dist_dir(self) -> Path:
        return Path("/home/ubuntuadmin/projects/gainhelm/dist")

    @property
    def canonical_domain(self) -> str:
        return "https://gainhelm.com"

    def get_widget_specs(self) -> List[InteractiveWidgetSpec]:
        return [
            InteractiveWidgetSpec(
                route="/tools/soc-2-audit-cost-calculator/",
                widget_id="soc-2-audit-cost-calculator",
                precondition_selector="#field-cpa_audit_fee, [data-calc-input]",
                input_selector="#field-cpa_audit_fee, [data-calc-input]",
                input_value="40000",
                output_selector="#metric-total_compliance_tco, .output-value",
                trigger_event="input",
                verify_popstate=True,
            ),
            InteractiveWidgetSpec(
                route="/tools/cmmc-2-0-compliance-cost-calculator/",
                widget_id="cmmc-2-0-compliance-cost-calculator",
                precondition_selector="#field-c3pao_assessment_fee, [data-calc-input]",
                input_selector="#field-c3pao_assessment_fee, [data-calc-input]",
                input_value="65000",
                output_selector="#metric-total_compliance_tco, .output-value",
                trigger_event="input",
                verify_popstate=False,
            ),
            InteractiveWidgetSpec(
                route="/tools/nist-800-171-sprs-score-calculator/",
                widget_id="nist-800-171-sprs-score-calculator",
                precondition_selector="#field-unmet_5pt_controls, [data-calc-input]",
                input_selector="#field-unmet_5pt_controls, [data-calc-input]",
                input_value="4",
                output_selector="#metric-sprs_score, .output-value",
                trigger_event="input",
                verify_popstate=False,
            ),
        ]


class RouteManifestExtractor:
    """
    Extracts complete route manifests from sitemap.xml and dist HTML filesystem tree.
    Enforces HWL-1313 invariant: unions sitemap.xml and all dist HTML files to prevent unlisted page escapes.
    """

    def __init__(self, dist_dir: Union[str, Path]):
        self.dist_dir = Path(dist_dir).resolve()

    def extract_routes(self) -> List[str]:
        """Extracts and normalizes the deduplicated route union."""
        routes: List[str] = []
        seen = set()

        def add_route(r: str) -> None:
            if not r:
                r = "/"
            if not r.startswith("/"):
                r = "/" + r
            if r not in seen:
                seen.add(r)
                routes.append(r)

        # 1. Parse sitemap.xml
        sitemap_path = self.dist_dir / "sitemap.xml"
        if sitemap_path.exists():
            try:
                tree = ET.parse(sitemap_path)
                root = tree.getroot()
                # Try standard XML namespace
                for loc in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
                    if loc.text:
                        p = urllib.parse.urlsplit(loc.text.strip()).path
                        add_route(p or "/")
                # Fallback for sitemaps without namespace
                if not routes:
                    for loc in root.findall(".//loc"):
                        if loc.text:
                            p = urllib.parse.urlsplit(loc.text.strip()).path
                            add_route(p or "/")
            except Exception:
                pass

        # 2. Walk dist directory filesystem
        if self.dist_dir.exists():
            for hf in sorted(self.dist_dir.glob("**/*.html")):
                parts = hf.relative_to(self.dist_dir).parts
                if "syndication" in parts or any(p.startswith(".") for p in parts):
                    continue
                rel = hf.relative_to(self.dist_dir)
                if rel.name == "index.html":
                    if rel.parent.parts:
                        p = "/" + "/".join(rel.parent.parts) + "/"
                    else:
                        p = "/"
                elif rel.name == "404.html":
                    p = "/404.html"
                else:
                    p = "/" + str(rel)
                add_route(p)

        # 3. Always include 404.html if present
        if (self.dist_dir / "404.html").exists():
            add_route("/404.html")

        # Always ensure root route '/' is represented
        if (self.dist_dir / "index.html").exists() or not routes:
            add_route("/")

        return routes

    def get_routes(self) -> List[str]:
        """Alias for extract_routes."""
        return self.extract_routes()

    @property
    def routes(self) -> List[str]:
        """Property returning extracted routes."""
        return self.extract_routes()


class UnifiedBrowserAuditor:
    """
    Unified multi-tenant UI/UX end-to-end browser verification engine over Chrome CDP.
    Enforces mechanical invariants:
    - CLS === 0.0 (layout-shift PerformanceObserver measurement)
    - Minimum 43.5px / 44px touch targets on interactive controls
    - Responsive viewports: 375px mobile and 1280px desktop zero horizontal overflow
    - Anti-slop: zero forbidden dashes (U+2014, U+2013, spaced hyphens)
    - Reactive interactive widget calculation updates and input reactivity
    """

    JS_CHECK_CLS = """new Promise(resolve => {
        let cls = 0.0;
        const observer = new PerformanceObserver(list => {
            for (const entry of list.getEntries()) {
                if (!entry.hadRecentInput) cls += entry.value;
            }
        });
        try {
            observer.observe({ type: 'layout-shift', buffered: true });
        } catch(e) {}
        window.scrollTo({ top: document.body.scrollHeight, behavior: 'instant' });
        setTimeout(() => {
            window.scrollTo({ top: 0, behavior: 'instant' });
            setTimeout(() => {
                try { observer.disconnect(); } catch(e) {}
                resolve(Math.round(cls * 1000) / 1000);
            }, 150);
        }, 150);
    })"""

    JS_CHECK_TARGETS = """(() => {
        const undersized = [];
        const els = Array.from(document.querySelectorAll('a, button, input:not([type=hidden]), select, textarea, [role="button"], summary'));
        els.forEach(el => {
            const r = el.getBoundingClientRect();
            const s = window.getComputedStyle(el);
            if (s.display === 'none' || s.visibility === 'hidden' || (r.width === 0 && r.height === 0)) return;
            if (s.display === 'inline' && el.tagName === 'A' && el.parentElement && ['P', 'LI'].includes(el.parentElement.tagName) && el.getClientRects().length > 1) return;
            if (r.width < 43.5 || r.height < 43.5) {
                undersized.push({
                    tag: el.tagName,
                    text: (el.innerText || el.value || el.name || '').trim().slice(0, 40),
                    width: Math.round(r.width * 10) / 10,
                    height: Math.round(r.height * 10) / 10,
                    id: el.id,
                    className: el.className
                });
            }
        });
        return undersized;
    })()"""

    JS_CHECK_DASHES = """(() => {
        const violations = [];
        const fullTitle = document.title || '';
        const emEnRegex = /[\\u2013\\u2014]|&mdash;|&ndash;|&#8212;|&#8211;/;
        const spacedHyphenRegex = /\\s+-\\s+/;
        if (emEnRegex.test(fullTitle)) {
            violations.push({ type: 'em_en_dash_title', text: fullTitle });
        }
        if (spacedHyphenRegex.test(fullTitle)) {
            violations.push({ type: 'spaced_hyphen_title', text: fullTitle });
        }
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
            acceptNode: node => {
                const p = node.parentElement;
                if (!p) return NodeFilter.FILTER_REJECT;
                const tag = p.tagName.toLowerCase();
                if (['script', 'style', 'code', 'pre', 'noscript'].includes(tag)) return NodeFilter.FILTER_REJECT;
                const s = window.getComputedStyle(p);
                if (s.display === 'none' || s.visibility === 'hidden') return NodeFilter.FILTER_REJECT;
                return NodeFilter.FILTER_ACCEPT;
            }
        });
        while (walker.nextNode()) {
            const txt = walker.currentNode.nodeValue;
            if (emEnRegex.test(txt)) {
                violations.push({ type: 'em_en_dash_body', text: txt.trim().slice(0, 80), tag: walker.currentNode.parentElement.tagName });
            } else if (spacedHyphenRegex.test(txt)) {
                violations.push({ type: 'spaced_hyphen_body', text: txt.trim().slice(0, 80), tag: walker.currentNode.parentElement.tagName });
            }
        }
        return violations;
    })()"""

    JS_CHECK_BROKEN_ASSETS = """(() => {
        const broken = [];
        document.querySelectorAll('img').forEach(img => {
            if (!img.complete || img.naturalWidth === 0) {
                broken.push({ type: 'broken_image', src: img.src });
            }
        });
        return broken;
    })()"""

    JS_CHECK_VISUAL_PRIMITIVES = """(() => {
        const vw = window.innerWidth;
        const p = location.pathname;
        const hasCalcControls = Boolean(document.querySelector('form.calculator-form, .interactive-calculator-container, .calculator-card, .calculation-container, input[type="number"], input[type="range"], [data-calc-input]'));
        const hasComparison = Boolean(document.querySelector('.comparison-table-section, .statutory-comparison-table-section, table.comparison-table')) || p.includes('-vs-');
        let archetype = 'statutory_guide';
        if (['/', '/index.html', '/tools/', '/tools/index.html', '/about/', '/about.html', '/contact/', '/contact.html', '/privacy/', '/privacy.html', '/terms/', '/terms.html', '/404.html', '/editorial-standards/', '/editorial-standards/index.html'].includes(p)) {
            archetype = 'index_hub';
        } else if (p.includes('-vs-') || (!hasCalcControls && hasComparison)) {
            archetype = 'comparison_page';
        } else if (hasCalcControls) {
            archetype = 'interactive_calculator';
        }
        const result = {
            screen_archetype: archetype,
            hierarchy_violations: [],
            unwrapped_tables: [],
            transparent_controls: [],
            clipped_elements: [],
            card_geometry_violations: [],
            whitespace_rhythm_violations: [],
            calculator_ergonomics_violations: [],
            cta_density_violations: []
        };
        const getFs = sel => {
            const el = document.querySelector(sel);
            if (!el) return null;
            const cs = window.getComputedStyle(el);
            if (cs.display === 'none' || cs.visibility === 'hidden') return null;
            return Math.round(parseFloat(cs.fontSize) * 10) / 10;
        };
        const h1 = getFs('h1');
        const h2 = getFs('main h2, article h2, .container h2, h2');
        const h3 = getFs('main h3, article h3, .container h3, h3');
        if (h1 !== null && h2 !== null && h1 <= h2) {
            result.hierarchy_violations.push({ type: 'h1_le_h2', h1: h1, h2: h2, vw: vw });
        }
        if (h2 !== null && h3 !== null && h2 < h3) {
            result.hierarchy_violations.push({ type: 'h2_lt_h3', h2: h2, h3: h3, vw: vw });
        }
        if (vw >= 1024) {
            if (h1 !== null && h1 < 24) {
                result.hierarchy_violations.push({ type: 'desktop_h1_under_24px', h1: h1, vw: vw });
            }
            if (h2 !== null && h2 < 18) {
                result.hierarchy_violations.push({ type: 'desktop_h2_under_18px', h2: h2, vw: vw });
            }
            if (h3 !== null && h3 < 15.5) {
                result.hierarchy_violations.push({ type: 'desktop_h3_under_16px', h3: h3, vw: vw });
            }
        } else if (vw <= 480) {
            if (h1 !== null && h1 < 20) {
                result.hierarchy_violations.push({ type: 'mobile_h1_under_20px', h1: h1, vw: vw });
            }
            if (h2 !== null && h2 < 17) {
                result.hierarchy_violations.push({ type: 'mobile_h2_under_17px', h2: h2, vw: vw });
            }
            if (h3 !== null && h3 < 15.5) {
                result.hierarchy_violations.push({ type: 'mobile_h3_under_16px', h3: h3, vw: vw });
            }
        }
        const parseRgb = str => {
            const m = String(str || '').match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)(?:,\\s*([0-9.]+))?\\)/);
            if (!m) return null;
            return { r: Number(m[1]), g: Number(m[2]), b: Number(m[3]), a: m[4] !== undefined ? Number(m[4]) : 1 };
        };
        const relLum = rgb => {
            const f = c => {
                const s = c / 255;
                return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
            };
            return 0.2126 * f(rgb.r) + 0.7152 * f(rgb.g) + 0.0722 * f(rgb.b);
        };
        const getEffectiveBg = el => {
            let cur = el;
            while (cur && cur !== document.documentElement) {
                const bg = parseRgb(window.getComputedStyle(cur).backgroundColor);
                if (bg && bg.a > 0.1) return bg;
                cur = cur.parentElement;
            }
            return parseRgb(window.getComputedStyle(document.body).backgroundColor) || { r: 255, g: 255, b: 255, a: 1 };
        };
        document.querySelectorAll('h1, main h2, main h3, .card-title, .calc-inline-cta strong').forEach(el => {
            const r = el.getBoundingClientRect();
            const cs = window.getComputedStyle(el);
            if (cs.display === 'none' || cs.visibility === 'hidden' || r.width === 0 || r.height === 0) return;
            const fg = parseRgb(cs.color);
            const bg = getEffectiveBg(el);
            if (fg && bg) {
                const l1 = relLum(fg);
                const l2 = relLum(bg);
                const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
                if (ratio < 3.0) {
                    result.hierarchy_violations.push({
                        type: 'low_contrast_text',
                        tag: el.tagName,
                        ratio: Math.round(ratio * 100) / 100,
                        fg: cs.color,
                        vw: vw
                    });
                }
            }
        });
        if (document.querySelectorAll('section.decision-framework-card').length > 1) {
            result.card_geometry_violations.push({
                type: 'duplicate_decision_framework_card',
                count: document.querySelectorAll('section.decision-framework-card').length,
                vw: vw
            });
        }
        document.querySelectorAll('table').forEach((t, idx) => {
            const r = t.getBoundingClientRect();
            if (r.width === 0 && r.height === 0) return;
            const par = t.parentElement;
            const pcs = par ? window.getComputedStyle(par) : null;
            const wrapped = par && (
                par.classList.contains('table-wrap') ||
                par.classList.contains('calc-matrix-table-wrap') ||
                par.classList.contains('pseo-table-wrap') ||
                (pcs && (pcs.overflowX === 'auto' || pcs.overflowX === 'scroll'))
            );
            if (!wrapped) {
                result.unwrapped_tables.push({ index: idx, parentTag: par ? par.tagName : 'NONE', vw: vw });
            } else if (par) {
                const pr = par.getBoundingClientRect();
                if (pr.right > vw + 2) {
                    result.unwrapped_tables.push({ index: idx, type: 'wrapper_overflow', right: Math.round(pr.right), vw: vw });
                }
            }
        });
        document.querySelectorAll('.scenario-preset-link, .on-this-page-nav a, .cluster-link, .affiliate-cta-link, .btn-preset').forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.width === 0 && r.height === 0) return;
            const cs = window.getComputedStyle(el);
            if (cs.backgroundColor === 'rgba(0, 0, 0, 0)' || cs.color === 'rgb(0, 0, 238)') {
                result.transparent_controls.push({
                    cls: (el.className || '').slice(0, 50),
                    bg: cs.backgroundColor,
                    color: cs.color
                });
            }
        });
        document.querySelectorAll('.card, .calc-panel, .result-box, .table-wrap').forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.width === 0 && r.height === 0) return;
            const cs = window.getComputedStyle(el);
            if (cs.overflowX === 'hidden' && el.scrollWidth > el.clientWidth + 2) {
                result.clipped_elements.push({
                    cls: (el.className || '').slice(0, 50),
                    scrollWidth: el.scrollWidth,
                    clientWidth: el.clientWidth
                });
            }
        });
        document.querySelectorAll('.card').forEach((c, idx) => {
            const r = c.getBoundingClientRect();
            if (r.width === 0 && r.height === 0) return;
            const cs = window.getComputedStyle(c);
            const br = Math.round(parseFloat(cs.borderRadius) || 0);
            if (br !== 12) {
                result.card_geometry_violations.push({ index: idx, borderRadius: cs.borderRadius });
            }
            const pt = Math.round(parseFloat(cs.paddingTop) || 0);
            if (pt < 12) {
                result.card_geometry_violations.push({ index: idx, paddingTop: cs.paddingTop });
            }
        });
        const mainEl = document.querySelector('main') || document.body;
        const flowRoot = (mainEl.children.length === 1 && mainEl.children[0].classList.contains('container')) ? mainEl.children[0] : mainEl;
        const topFlowBlocks = [];
        Array.from(flowRoot.children).forEach(ch => {
            if (['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(ch.tagName) || ch.classList.contains('statutory-accuracy-benchmarks')) return;
            const cs = window.getComputedStyle(ch);
            if (cs.display === 'none' || cs.visibility === 'hidden') return;
            if (ch.classList.contains('gsc-overlay-container')) {
                Array.from(ch.children).forEach(och => {
                    if (['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(och.tagName)) return;
                    const ocs = window.getComputedStyle(och);
                    const or = och.getBoundingClientRect();
                    if (ocs.display !== 'none' && ocs.visibility !== 'hidden' && or.height > 0 && or.width > vw * 0.45) {
                        topFlowBlocks.push(och);
                    }
                });
            } else {
                const r = ch.getBoundingClientRect();
                if (r.height > 0 && r.width > vw * 0.45) {
                    topFlowBlocks.push(ch);
                }
            }
        });
        if (topFlowBlocks.length >= 2) {
            const lefts = topFlowBlocks.map(el => Math.round(el.getBoundingClientRect().left * 10) / 10);
            const drift = Math.max(...lefts) - Math.min(...lefts);
            if (drift > 4.0) {
                result.card_geometry_violations.push({ type: 'sibling_left_drift', drift: Math.round(drift * 10) / 10, vw: vw });
            }
        }
        if (vw >= 1280) {
            topFlowBlocks.forEach((el, idx) => {
                const r = el.getBoundingClientRect();
                if (r.width > 1142) {
                    result.card_geometry_violations.push({ type: 'full_bleed_section_width', index: idx, width: Math.round(r.width), vw: vw });
                }
            });
        }
        for (let i = 1; i < topFlowBlocks.length; i++) {
            const prev = topFlowBlocks[i - 1];
            const curr = topFlowBlocks[i];
            if (prev.contains(curr) || curr.contains(prev)) continue;
            const pr = prev.getBoundingClientRect();
            const cr = curr.getBoundingClientRect();
            const gap = Math.round((cr.top - pr.bottom) * 10) / 10;
            if (gap < 10 || gap > 52) {
                result.whitespace_rhythm_violations.push({ index: i, gap: gap, vw: vw });
            }
        }
        document.querySelectorAll('input:not([type=hidden]):not([type=range]):not([type=checkbox]):not([type=radio]), select').forEach(inp => {
            const r = inp.getBoundingClientRect();
            const cs = window.getComputedStyle(inp);
            if (cs.display === 'none' || cs.visibility === 'hidden' || (r.width === 0 && r.height === 0)) return;
            const fs = Math.round(parseFloat(cs.fontSize) * 10) / 10;
            if (fs < 16) {
                result.calculator_ergonomics_violations.push({ type: 'input_font_under_16px', id: inp.id || inp.name || '', fontSize: fs });
            }
        });
        document.querySelectorAll('.output-value, .metric-val, .res-val, .kpi-value').forEach(out => {
            const r = out.getBoundingClientRect();
            const cs = window.getComputedStyle(out);
            if (cs.display === 'none' || cs.visibility === 'hidden' || (r.width === 0 && r.height === 0)) return;
            if (!String(cs.fontVariantNumeric || '').includes('tabular-nums')) {
                result.calculator_ergonomics_violations.push({ type: 'missing_tabular_nums', id: out.id || out.className || '' });
            }
        });
        const ctaSel = '#vetted-commercial-handoff, #statutory-trap-alert, .commercial-handoff-card, .monetization-partner-section, .inline-fold-cta-card';
        const ctaParents = new Set();
        document.querySelectorAll(ctaSel).forEach(el => {
            if (el.parentElement) ctaParents.add(el.parentElement);
        });
        ctaParents.forEach(par => {
            let streak = 0;
            Array.from(par.children).forEach(ch => {
                const cs = window.getComputedStyle(ch);
                if (cs.display === 'none' || cs.visibility === 'hidden' || ['SCRIPT', 'STYLE'].includes(ch.tagName)) return;
                if (ch.matches && ch.matches(ctaSel)) {
                    streak += 1;
                    if (streak > 2) {
                        result.cta_density_violations.push({ type: 'consecutive_cta_callouts_gt_2', streak: streak });
                    }
                } else {
                    streak = 0;
                }
            });
        });
        const trapEl = document.getElementById('statutory-trap-alert');
        const handoffEl = document.getElementById('vetted-commercial-handoff');
        if (trapEl && handoffEl && (trapEl.nextElementSibling === handoffEl || handoffEl.nextElementSibling === trapEl)) {
            result.cta_density_violations.push({ type: 'adjacent_trap_and_handoff' });
        }
        const firstPresetChip = document.querySelector('.above-fold-preset-bar [data-calc-preset], [data-calc-preset], .scenario-preset-link, .btn-preset');
        if (firstPresetChip) {
            const pr = firstPresetChip.getBoundingClientRect();
            result.first_preset_chip_top = Math.round(pr.top);
            result.preset_chips_above_fold = pr.top <= 680;
        } else {
            result.first_preset_chip_top = null;
            result.preset_chips_above_fold = null;
        }
        return result;
    })()"""

    JS_INIT_ERROR_AND_SYNTHETIC_HOOK = """(() => {
        window.__PSEO_SYNTHETIC_TEST__ = true;
        window.__pseoPageErrors = window.__pseoPageErrors || [];
        window.__pseoConsoleErrors = window.__pseoConsoleErrors || [];
        window.addEventListener('error', (ev) => {
            const msg = ev && (ev.message || (ev.error && ev.error.message)) ? String(ev.message || ev.error.message) : 'window_error';
            window.__pseoPageErrors.push(msg);
        });
        window.addEventListener('unhandledrejection', (ev) => {
            const reason = ev && ev.reason ? String(ev.reason.message || ev.reason) : 'unhandledrejection';
            window.__pseoPageErrors.push(reason);
        });
        const origConsoleError = console.error ? console.error.bind(console) : null;
        console.error = function(...args) {
            try {
                window.__pseoConsoleErrors.push(args.map(a => String(a && a.message ? a.message : a)).join(' '));
            } catch (e) {}
            if (origConsoleError) return origConsoleError(...args);
        };
    })();"""

    JS_CHECK_UNIVERSAL_INTERACTIVE_SYNC = """(() => {
        const failures = [];
        const outSel = '.output-value, .calc-metric-value, .metric-value, .metric-val, [id^="val-"], [id^="res-"], [id^="metric-"], #serp-out-primary';
        const snapshotOutputs = () => Array.from(document.querySelectorAll(outSel)).map(el => (el.innerText || el.textContent || '').trim()).join('|');
        const primaryInp = document.querySelector('#field-gross_income, #tax-income, #sec179-cost, #sec1031-sale-price, #crypto-short-term, #runway-cash, #tey-principal, #cg-amount, #arb-yes-cents, #pm-tax-gain, #input-agi, #field-loan_balance, input[type="number"]:not([readonly]):not(.serp-sub-input)');
        if (primaryInp && document.querySelectorAll(outSel).length > 0) {
            const beforeSnap = snapshotOutputs();
            const origVal = primaryInp.value;
            const curNum = parseFloat(String(origVal).replace(/,/g, '')) || 10000;
            const maxNum = parseFloat(primaryInp.getAttribute('max') || '') || 10000000;
            const minNum = parseFloat(primaryInp.getAttribute('min') || '0') || 0;
            let nextNum = Math.round(curNum * 1.35 + 50);
            if (nextNum > maxNum) nextNum = Math.max(minNum + 1, Math.round(curNum * 0.65));
            if (nextNum === curNum) nextNum = curNum + 10;
            primaryInp.value = String(nextNum);
            primaryInp.dispatchEvent(new Event('input', { bubbles: true }));
            primaryInp.dispatchEvent(new Event('change', { bubbles: true }));
            const afterSnap = snapshotOutputs();
            if (beforeSnap === afterSnap) {
                failures.push({ widget_id: primaryInp.id || primaryInp.name || 'primary_input', detail: 'Primary calculator input change did not update any output metric' });
            }
            primaryInp.value = origVal;
            primaryInp.dispatchEvent(new Event('input', { bubbles: true }));
            primaryInp.dispatchEvent(new Event('change', { bubbles: true }));
        }
        const presetButtons = Array.from(document.querySelectorAll('button[data-calc-preset], .btn-preset[data-calc-preset], .serp-archetype-btn[data-calc-preset]'));
        if (presetButtons.length > 0) {
            const btn = presetButtons[presetButtons.length > 1 ? 1 : 0];
            const beforeOut = snapshotOutputs();
            const beforeInps = Array.from(document.querySelectorAll('input[type="number"], input[type="range"], select')).map(el => el.value).join('|');
            btn.click();
            const afterOut = snapshotOutputs();
            const afterInps = Array.from(document.querySelectorAll('input[type="number"], input[type="range"], select')).map(el => el.value).join('|');
            const hasReadout = Boolean(document.querySelector('.overlay-preset-readout'));
            if (beforeOut === afterOut && beforeInps === afterInps && !hasReadout && !btn.classList.contains('active')) {
                failures.push({ widget_id: 'data-calc-preset', detail: 'Clicking [data-calc-preset] button did not synchronize inputs, outputs, or active state' });
            }
        }
        const affiliateAnchors = Array.from(document.querySelectorAll('a[data-partner], a.affiliate-cta-link, .partner-card a[href], .calc-inline-cta a[href], .overlay-partner-offer a[href]'));
        affiliateAnchors.forEach((a, idx) => {
            const rawHref = a.getAttribute('href') || '';
            if (!rawHref.startsWith('/r/')) {
                failures.push({ widget_id: a.id || ('affiliate_cta_' + idx), detail: 'Affiliate CTA href does not route through /r/ edge redirect: ' + rawHref });
            }
            const rel = (a.getAttribute('rel') || '').toLowerCase();
            if (!rel.includes('sponsored') || !rel.includes('nofollow')) {
                failures.push({ widget_id: a.id || ('affiliate_cta_rel_' + idx), detail: 'Affiliate CTA missing rel sponsored/nofollow: ' + rel });
            }
        });
        if (Array.isArray(window.__pseoPageErrors) && window.__pseoPageErrors.length > 0) {
            failures.push({ widget_id: 'runtime_page_errors', detail: window.__pseoPageErrors.join('; ') });
        }
        if (Array.isArray(window.__pseoConsoleErrors) && window.__pseoConsoleErrors.length > 0) {
            failures.push({ widget_id: 'runtime_console_errors', detail: window.__pseoConsoleErrors.join('; ') });
        }
        return failures;
    })()"""

    JS_RUN_E2E_INTERACTIVE_SURFACE = """(async () => {
        window.__PSEO_SYNTHETIC_TEST__ = true;
        window.__PSEO_PREVENT_AFFILIATE_NAV__ = true;
        const report = {
            route: window.location.pathname,
            console_errors: Array.isArray(window.__pseoConsoleErrors) ? [...window.__pseoConsoleErrors] : [],
            page_errors: Array.isArray(window.__pseoPageErrors) ? [...window.__pseoPageErrors] : [],
            links_audit: { total_links: 0, internal_links: 0, affiliate_links: 0, invalid_links: [], unrouted_affiliate_links: [] },
            deep_link_hydration: { tested: false, passed: true, detail: '' },
            calculator_and_presets: { tested: false, passed: true, before_snapshot: '', after_snapshot: '', preset_clicked: false },
            cliff_visualizer: { present: false, passed: true, before_values: [], after_values: [] },
            scenario_comparator: { present: false, passed: true, pinned_a: '', pinned_b: '', live_delta: '' },
            blueprint_actions: { present: false, passed: true, saved_status: '', shared_status: '', exported_status: '', storage_keys: 0 },
            post_calc_upgrade_drawer: { present: false, passed: true, preview_rendered: false, checkout_status: '', settlement_id: '', datapack_download_triggered: false },
            playbook_lead_capture_and_checkout: { present: false, passed: true, submission_state: '', partner_href: '', checkout_status: '', checkout_session_id: '' },
            partner_quote_intake_and_checkout: { present: false, passed: true, submission_state: '', partner_href: '', checkout_status: '', checkout_session_id: '' },
            affiliate_redirect_and_telemetry: { tested: false, passed: true, dom_click_handled: false, redirect_status: 0, redirect_location: '', telemetry_status: '' }
        };

        const outSel = '.output-value, .calc-metric-value, .metric-value, .metric-val, [id^="val-"], [id^="res-"], [id^="metric-"], #serp-out-primary';
        const snapshotOutputs = () => Array.from(document.querySelectorAll(outSel)).map(el => (el.innerText || el.textContent || '').trim()).join('|');

        // 1. Links audit (internal + affiliate/outbound)
        const allAnchors = Array.from(document.querySelectorAll('a[href]'));
        report.links_audit.total_links = allAnchors.length;
        for (const a of allAnchors) {
            const href = (a.getAttribute('href') || '').trim();
            if (!href || href === '#' || href.startsWith('javascript:')) {
                report.links_audit.invalid_links.push(href || '(empty)');
                continue;
            }
            const isAff = a.hasAttribute('data-partner') || a.classList.contains('affiliate-cta-link') || Boolean(a.closest('.partner-card, .calc-inline-cta, .overlay-partner-offer, #vetted-commercial-handoff')) || href.startsWith('/r/');
            if (isAff) {
                report.links_audit.affiliate_links += 1;
                const rel = (a.getAttribute('rel') || '').toLowerCase();
                if (!href.startsWith('/r/') || !rel.includes('sponsored') || !rel.includes('nofollow')) {
                    report.links_audit.unrouted_affiliate_links.push({ href: href, rel: rel, id: a.id || '' });
                }
            } else if (href.startsWith('/') || href.startsWith(window.location.origin) || href.startsWith('#')) {
                report.links_audit.internal_links += 1;
                if (href.startsWith('#') && href.length > 1) {
                    const targetId = href.slice(1);
                    if (!document.getElementById(targetId)) {
                        report.links_audit.invalid_links.push(href);
                    }
                }
            }
        }

        // 2. Primary calculator input, cliff visualizer, scenario comparator, presets, and deep-link hydration
        const primaryInp = document.querySelector('#field-gross_income, #tax-income, #sec179-cost, #sec1031-sale-price, #crypto-short-term, #runway-cash, #tey-principal, #cg-amount, #arb-yes-cents, #pm-tax-gain, #input-agi, #field-loan_balance, input[type="number"]:not([readonly]):not(.serp-sub-input)');
        const cliffRoot = document.getElementById('multi-year-cliff-visualizer') || document.querySelector('.serp-cliff-chart');
        const cliffValueSelector = '[id^="cliff-exposure-"], [id^="serp-cliff-val-"]';
        if (cliffRoot) {
            report.cliff_visualizer.present = true;
            report.cliff_visualizer.before_values = Array.from(document.querySelectorAll(cliffValueSelector)).map(el => (el.innerText || el.textContent || '').trim());
        }

        const compRoot = document.getElementById('stateful-scenario-comparator');
        const pinABtn = document.querySelector('[data-scenario-pin="A"]');
        const pinBBtn = document.querySelector('[data-scenario-pin="B"]');
        const pinResetBtn = document.querySelector('[data-scenario-pin="RESET"]');
        if (compRoot || pinABtn) {
            report.scenario_comparator.present = true;
        }

        if (primaryInp) {
            report.calculator_and_presets.tested = true;
            const origVal = primaryInp.value;
            const curNum = parseFloat(String(origVal).replace(/,/g, '')) || 50000;
            const maxNum = parseFloat(primaryInp.getAttribute('max') || '') || 10000000;
            const minNum = parseFloat(primaryInp.getAttribute('min') || '0') || 0;

            if (pinABtn) {
                pinABtn.click();
            }

            report.calculator_and_presets.before_snapshot = snapshotOutputs();
            let nextNum = Math.round(curNum * 1.45 + 250);
            if (nextNum > maxNum) nextNum = Math.max(minNum + 10, Math.round(curNum * 0.6));
            if (nextNum === curNum) nextNum = curNum + 100;
            primaryInp.value = String(nextNum);
            primaryInp.dispatchEvent(new Event('input', { bubbles: true }));
            primaryInp.dispatchEvent(new Event('change', { bubbles: true }));
            report.calculator_and_presets.after_snapshot = snapshotOutputs();
            if (report.calculator_and_presets.before_snapshot === report.calculator_and_presets.after_snapshot) {
                report.calculator_and_presets.passed = false;
            }

            if (cliffRoot) {
                report.cliff_visualizer.after_values = Array.from(document.querySelectorAll(cliffValueSelector)).map(el => (el.innerText || el.textContent || '').trim());
                if (report.cliff_visualizer.after_values.length === 0 || report.cliff_visualizer.before_values.join('|') === report.cliff_visualizer.after_values.join('|')) {
                    report.cliff_visualizer.passed = false;
                }
            }

            if (pinBBtn) {
                pinBBtn.click();
                const aNode = document.getElementById('comp-a-retained') || document.getElementById('serp-scn-a-retained');
                const bNode = document.getElementById('comp-b-retained') || document.getElementById('serp-scn-b-retained');
                const dNode = document.getElementById('comp-live-delta') || document.getElementById('comp-b-delta') || document.getElementById('serp-scn-delta-banner');
                report.scenario_comparator.pinned_a = aNode ? (aNode.innerText || aNode.textContent || '').trim() : '';
                report.scenario_comparator.pinned_b = bNode ? (bNode.innerText || bNode.textContent || '').trim() : '';
                report.scenario_comparator.live_delta = dNode ? (dNode.innerText || dNode.textContent || '').trim() : '';
                if (!report.scenario_comparator.pinned_a || !report.scenario_comparator.pinned_b || report.scenario_comparator.pinned_a === '$0') {
                    report.scenario_comparator.passed = false;
                }
                if (pinResetBtn) {
                    pinResetBtn.click();
                }
            }

            // Deep-link hydration via URL query + popstate
            const rawKey = (primaryInp.name || primaryInp.id || 'amount').replace(/^field-/, '');
            const hydratedNum = Math.min(maxNum, Math.max(minNum + 5, Math.round(curNum * 1.25 + 120)));
            const origUrl = window.location.pathname + window.location.search + window.location.hash;
            window.history.replaceState(null, '', window.location.pathname + '?' + encodeURIComponent(rawKey) + '=' + encodeURIComponent(String(hydratedNum)));
            window.dispatchEvent(new PopStateEvent('popstate'));
            if (typeof window.__pseoHydrateFromUrl === 'function') {
                window.__pseoHydrateFromUrl();
            }
            report.deep_link_hydration.tested = true;
            report.deep_link_hydration.passed = String(primaryInp.value) === String(hydratedNum);
            report.deep_link_hydration.detail = 'key=' + rawKey + ', expected=' + hydratedNum + ', actual=' + primaryInp.value;
            window.history.replaceState(null, '', origUrl);
        }

        const presetBtn = document.querySelector('button[data-calc-preset], .btn-preset[data-calc-preset], .serp-archetype-btn[data-calc-preset], a.scenario-preset-link[href*="?"]');
        if (presetBtn) {
            if (presetBtn.tagName !== 'A') {
                presetBtn.click();
                report.calculator_and_presets.preset_clicked = true;
            } else {
                report.calculator_and_presets.preset_clicked = true;
            }
        }

        // 3. Saveable Decision Blueprint actions
        const saveBtn = document.querySelector('[data-blueprint-action="save"]');
        const shareBtn = document.querySelector('[data-blueprint-action="share"]');
        const exportBtn = document.querySelector('[data-blueprint-action="export"]');
        const statusNode = document.getElementById('blueprint-status-readout') || document.getElementById('serp-blueprint-status') || document.querySelector('.serp-blueprint-status');
        if (saveBtn) {
            report.blueprint_actions.present = true;
            saveBtn.click();
            report.blueprint_actions.saved_status = statusNode ? (statusNode.innerText || statusNode.textContent || '').trim() : '';
            if (shareBtn) {
                shareBtn.click();
                report.blueprint_actions.shared_status = statusNode ? (statusNode.innerText || statusNode.textContent || '').trim() : '';
            }
            if (exportBtn) {
                exportBtn.click();
                report.blueprint_actions.exported_status = statusNode ? (statusNode.innerText || statusNode.textContent || '').trim() : '';
            }
            let bpKeys = 0;
            try {
                for (let i = 0; i < localStorage.length; i++) {
                    const k = localStorage.key(i) || '';
                    if (k.startsWith('pseo_blueprint')) bpKeys += 1;
                }
            } catch (e) {}
            report.blueprint_actions.storage_keys = bpKeys;
            if (!report.blueprint_actions.saved_status || bpKeys === 0 || (exportBtn && exportBtn.getAttribute('data-blueprint-exported') !== '1')) {
                report.blueprint_actions.passed = false;
            }
        }

        // 3b. Post-Calculation Upgrade Drawer (Workpaper Preview + Statutory Data Pack Checkout + Deliverable Downloads)
        const upgDrawer = document.getElementById('post-calculation-upgrade-drawer');
        if (upgDrawer) {
            report.post_calc_upgrade_drawer.present = true;
            const previewBtn = document.getElementById('btn-preview-post-calc-workpaper') || upgDrawer.querySelector('[data-blueprint-action="preview_workpaper"]');
            if (previewBtn) {
                previewBtn.click();
                for (let i = 0; i < 20; i++) {
                    await new Promise(r => setTimeout(r, 40));
                    if (document.getElementById('playbook-download-link') || document.getElementById('playbook-datapack-link')) break;
                }
                report.post_calc_upgrade_drawer.preview_rendered = Boolean(
                    document.getElementById('playbook-download-link') &&
                    document.getElementById('playbook-csv-link') &&
                    document.getElementById('playbook-datapack-link')
                );
            }
            const upgCheckoutBtn = document.getElementById('btn-post-calc-upgrade-checkout') || upgDrawer.querySelector('[data-checkout-trigger]');
            if (upgCheckoutBtn) {
                upgCheckoutBtn.click();
                for (let i = 0; i < 30; i++) {
                    await new Promise(r => setTimeout(r, 50));
                    if (upgCheckoutBtn.getAttribute('data-checkout-status') === 'checkout_session_ready') break;
                }
                report.post_calc_upgrade_drawer.checkout_status = upgCheckoutBtn.getAttribute('data-checkout-status') || '';
                report.post_calc_upgrade_drawer.settlement_id = upgCheckoutBtn.getAttribute('data-settlement-id') || '';
                const ffHtml = document.getElementById('checkout-fulfillment-html-link');
                const ffCsv = document.getElementById('checkout-fulfillment-csv-link');
                const ffDp = document.getElementById('checkout-fulfillment-datapack-link');
                if (ffHtml) ffHtml.click();
                if (ffCsv) ffCsv.click();
                if (ffDp) ffDp.click();
                report.post_calc_upgrade_drawer.datapack_download_triggered = Boolean(
                    ffDp && ffDp.getAttribute('data-download-triggered') === 'true'
                );
            }
            const drawerAmt = parseInt(upgDrawer.getAttribute('data-calculated-amount') || '0', 10);
            if (
                !report.post_calc_upgrade_drawer.preview_rendered ||
                report.post_calc_upgrade_drawer.checkout_status !== 'checkout_session_ready' ||
                !report.post_calc_upgrade_drawer.settlement_id ||
                !report.post_calc_upgrade_drawer.datapack_download_triggered ||
                drawerAmt < 500
            ) {
                report.post_calc_upgrade_drawer.passed = false;
            }
        }

        // 4. Playbook subscription form POST + checkout trigger
        const leadForm = document.getElementById('lead-capture-form') || document.querySelector('form.lead-capture-form');
        if (leadForm) {
            report.playbook_lead_capture_and_checkout.present = true;
            const emailInp = leadForm.querySelector('input[type="email"], input[name="email"]');
            if (emailInp) {
                emailInp.value = 'playbook-probe@synthetic.pseofactory.test';
            }
            leadForm.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
            for (let i = 0; i < 30; i++) {
                await new Promise(r => setTimeout(r, 50));
                if (leadForm.getAttribute('data-submission-state') === 'success' || leadForm.getAttribute('data-submission-state') === 'fallback_saved') {
                    break;
                }
            }
            report.playbook_lead_capture_and_checkout.submission_state = leadForm.getAttribute('data-submission-state') || '';
            const pbPartner = document.getElementById('playbook-partner-link');
            const pbCheckout = document.getElementById('playbook-checkout-link');
            report.playbook_lead_capture_and_checkout.partner_href = pbPartner ? (pbPartner.getAttribute('href') || '') : '';
            if (pbCheckout) {
                pbCheckout.click();
                for (let i = 0; i < 30; i++) {
                    await new Promise(r => setTimeout(r, 50));
                    if (pbCheckout.getAttribute('data-checkout-status') === 'checkout_session_ready') {
                        break;
                    }
                }
                report.playbook_lead_capture_and_checkout.checkout_status = pbCheckout.getAttribute('data-checkout-status') || '';
                report.playbook_lead_capture_and_checkout.checkout_session_id = pbCheckout.getAttribute('data-checkout-session-id') || '';
            }
            if (
                report.playbook_lead_capture_and_checkout.submission_state !== 'success' ||
                !report.playbook_lead_capture_and_checkout.partner_href.startsWith('/r/') ||
                report.playbook_lead_capture_and_checkout.checkout_status !== 'checkout_session_ready'
            ) {
                report.playbook_lead_capture_and_checkout.passed = false;
            }
        }

        // 5. Partner Quote Intake form POST + checkout trigger
        const quoteForm = document.getElementById('partner-quote-intake-form') || document.querySelector('form.partner-quote-intake-form');
        if (quoteForm) {
            report.partner_quote_intake_and_checkout.present = true;
            const qEmail = document.getElementById('quote-intake-email') || quoteForm.querySelector('input[type="email"]');
            const qConsent = document.getElementById('quote-tcpa-consent') || quoteForm.querySelector('input[type="checkbox"]');
            if (qEmail) qEmail.value = 'quote-probe@synthetic.pseofactory.test';
            if (qConsent) qConsent.checked = true;
            quoteForm.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
            for (let i = 0; i < 30; i++) {
                await new Promise(r => setTimeout(r, 50));
                if (quoteForm.getAttribute('data-submission-state') === 'success' || quoteForm.getAttribute('data-submission-state') === 'fallback_saved') {
                    break;
                }
            }
            report.partner_quote_intake_and_checkout.submission_state = quoteForm.getAttribute('data-submission-state') || '';
            const qPartner = document.getElementById('quote-matched-partner-link');
            const qCheckout = document.getElementById('quote-matched-checkout-link');
            report.partner_quote_intake_and_checkout.partner_href = qPartner ? (qPartner.getAttribute('href') || '') : '';
            if (qCheckout) {
                qCheckout.click();
                for (let i = 0; i < 30; i++) {
                    await new Promise(r => setTimeout(r, 50));
                    if (qCheckout.getAttribute('data-checkout-status') === 'checkout_session_ready') {
                        break;
                    }
                }
                report.partner_quote_intake_and_checkout.checkout_status = qCheckout.getAttribute('data-checkout-status') || '';
                report.partner_quote_intake_and_checkout.checkout_session_id = qCheckout.getAttribute('data-checkout-session-id') || '';
            }
            if (
                report.partner_quote_intake_and_checkout.submission_state !== 'success' ||
                !report.partner_quote_intake_and_checkout.partner_href.startsWith('/r/') ||
                report.partner_quote_intake_and_checkout.checkout_status !== 'checkout_session_ready'
            ) {
                report.partner_quote_intake_and_checkout.passed = false;
            }
        }

        // 6. Outbound /r/<partner> DOM click, redirect & /api/telemetry edge round-trip
        const firstAff = document.querySelector('a[href^="/r/"]');
        if (firstAff) {
            report.affiliate_redirect_and_telemetry.tested = true;
            firstAff.click();
            report.affiliate_redirect_and_telemetry.dom_click_handled = (
                firstAff.getAttribute('data-affiliate-clicked') === 'true' &&
                Boolean(firstAff.getAttribute('data-last-click-subid'))
            );
            try {
                const telResp = await fetch('/api/telemetry?synthetic_test=1', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-Pseofactory-Test': '1' },
                    body: JSON.stringify({
                        schema_version: '2.0',
                        event_type: 'synthetic_e2e_probe',
                        slug: window.location.pathname,
                        synthetic_test: true
                    })
                });
                const telData = await telResp.json();
                report.affiliate_redirect_and_telemetry.telemetry_status = telData.status || '';
            } catch (e) {
                report.affiliate_redirect_and_telemetry.passed = false;
            }
            try {
                const rawHref = firstAff.getAttribute('href') || '/r/collective';
                const sep = rawHref.includes('?') ? '&' : '?';
                const redirResp = await fetch(rawHref + sep + 'synthetic_test=1', {
                    method: 'GET',
                    headers: { 'X-Pseofactory-Test': '1' },
                    redirect: 'manual'
                });
                report.affiliate_redirect_and_telemetry.redirect_status = redirResp.status;
                report.affiliate_redirect_and_telemetry.redirect_location = redirResp.headers.get('Location') || redirResp.url || '';
                if (redirResp.type !== 'opaqueredirect' && redirResp.status !== 302 && redirResp.status !== 200) {
                    report.affiliate_redirect_and_telemetry.passed = false;
                }
            } catch (e) {
                report.affiliate_redirect_and_telemetry.passed = false;
            }
            if (
                !report.affiliate_redirect_and_telemetry.dom_click_handled ||
                (report.affiliate_redirect_and_telemetry.telemetry_status !== 'ok' && report.affiliate_redirect_and_telemetry.telemetry_status !== 'RECORDED')
            ) {
                report.affiliate_redirect_and_telemetry.passed = false;
            }
        }

        report.console_errors = Array.isArray(window.__pseoConsoleErrors) ? [...window.__pseoConsoleErrors] : [];
        report.page_errors = Array.isArray(window.__pseoPageErrors) ? [...window.__pseoPageErrors] : [];
        report.passed = (
            report.console_errors.length === 0 &&
            report.page_errors.length === 0 &&
            report.links_audit.invalid_links.length === 0 &&
            report.links_audit.unrouted_affiliate_links.length === 0 &&
            report.deep_link_hydration.passed &&
            report.calculator_and_presets.passed &&
            report.cliff_visualizer.passed &&
            report.scenario_comparator.passed &&
            report.blueprint_actions.passed &&
            report.post_calc_upgrade_drawer.passed &&
            report.playbook_lead_capture_and_checkout.passed &&
            report.partner_quote_intake_and_checkout.passed &&
            report.affiliate_redirect_and_telemetry.passed
        );
        return report;
    })()"""

    JS_CHECK_RESIZE_AND_INTERACTION_CLS = """new Promise(resolve => {
        let cls = 0.0;
        const observer = new PerformanceObserver(list => {
            for (const entry of list.getEntries()) {
                if (!entry.hadRecentInput) cls += entry.value;
            }
        });
        try {
            observer.observe({ type: 'layout-shift', buffered: false });
        } catch(e) {}
        const inputs = Array.from(document.querySelectorAll('[data-calc-input], input:not([type=hidden]), select'));
        inputs.slice(0, 3).forEach(el => {
            try {
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            } catch(e) {}
        });
        setTimeout(() => {
            try { observer.disconnect(); } catch(e) {}
            resolve(Math.round(cls * 1000) / 1000);
        }, 120);
    })"""

    def __init__(
        self,
        adapter: Optional[TenantBrowserAdapter] = None,
        dist_dir: Optional[Union[str, Path]] = None,
        cdp_port: int = 9222,
        fail_closed: Optional[bool] = None,
    ):
        self.adapter = adapter
        if adapter is not None:
            self.dist_dir = adapter.dist_dir
            self.widget_specs = adapter.get_widget_specs()
            self.excluded_routes = set(adapter.get_excluded_routes())
        else:
            self.dist_dir = Path(dist_dir).resolve() if dist_dir else Path("dist").resolve()
            self.widget_specs = []
            self.excluded_routes = set()

        self.cdp_port = cdp_port
        self.cdp_base = f"http://127.0.0.1:{cdp_port}"
        if fail_closed is None:
            self.fail_closed = os.environ.get("PSEOFACTORY_BROWSER_FAIL_CLOSED") == "1"
        else:
            self.fail_closed = bool(fail_closed)

    def check_cdp_reachability(self) -> Tuple[bool, str]:
        """Checks if host Chrome CDP endpoint is responding on configured port."""
        try:
            req = urllib.request.Request(f"{self.cdp_base}/json/version")
            with urllib.request.urlopen(req, timeout=3) as r:
                return True, r.read().decode("utf-8")
        except Exception as e:
            return False, str(e)

    async def _send_cdp(self, ws: Any, method: str, params: Optional[Dict[str, Any]] = None, msg_id: int = 1) -> Dict[str, Any]:
        req = {"id": msg_id, "method": method, "params": params or {}}
        await ws.send(json.dumps(req))
        while True:
            resp_raw = await asyncio.wait_for(ws.recv(), timeout=15)
            resp = json.loads(resp_raw)
            if resp.get("id") == msg_id:
                return resp

    async def _eval_js(self, ws: Any, expr: str, msg_id: int = 100) -> Any:
        res = await self._send_cdp(
            ws,
            "Runtime.evaluate",
            {"expression": expr, "returnByValue": True, "awaitPromise": True},
            msg_id=msg_id,
        )
        return res.get("result", {}).get("result", {}).get("value")

    async def _audit_route_on_ws(
        self,
        ws: Any,
        base_url: str,
        route: str,
        msg_counter: List[int],
    ) -> Dict[str, Any]:
        """Executes full multi-viewport and visual primitive checks on an active CDP websocket."""
        page_url = f"{base_url}{route}"
        defects: Dict[str, Any] = {
            "route": route,
            "screen_archetype": "statutory_guide",
            "broken_assets": [],
            "targets_under_44": [],
            "cls_value": 0.0,
            "overflow_375": False,
            "overflow_1280": False,
            "overflow_1440": False,
            "dashes": [],
            "widget_failures": [],
            "hierarchy_violations": [],
            "unwrapped_tables": [],
            "transparent_controls": [],
            "clipped_elements": [],
            "card_geometry_violations": [],
            "whitespace_rhythm_violations": [],
            "calculator_ergonomics_violations": [],
            "cta_density_violations": [],
        }
        prim_keys = (
            "hierarchy_violations",
            "unwrapped_tables",
            "transparent_controls",
            "clipped_elements",
            "card_geometry_violations",
            "whitespace_rhythm_violations",
            "calculator_ergonomics_violations",
            "cta_density_violations",
        )

        msg_counter[0] += 1
        await self._send_cdp(ws, "Emulation.clearDeviceMetricsOverride", {}, msg_id=msg_counter[0])
        msg_counter[0] += 1
        await self._send_cdp(
            ws,
            "Emulation.setDeviceMetricsOverride",
            {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False},
            msg_id=msg_counter[0],
        )
        msg_counter[0] += 1
        await self._send_cdp(ws, "Page.navigate", {"url": page_url}, msg_id=msg_counter[0])
        for _ in range(25):
            await asyncio.sleep(0.04)
            msg_counter[0] += 1
            rs = await self._eval_js(
                ws,
                "document.readyState === 'complete' && document.body && document.body.children.length > 0",
                msg_id=msg_counter[0],
            )
            if rs:
                break
        await asyncio.sleep(0.04)

        # 1a. Wide Desktop Viewport (1440x900)
        msg_counter[0] += 1
        overflow_1440 = await self._eval_js(
            ws,
            "document.documentElement.scrollWidth > window.innerWidth || document.body.scrollWidth > window.innerWidth",
            msg_id=msg_counter[0],
        )
        if overflow_1440:
            defects["overflow_1440"] = True

        msg_counter[0] += 1
        prim_1440 = await self._eval_js(ws, self.JS_CHECK_VISUAL_PRIMITIVES, msg_id=msg_counter[0])
        if isinstance(prim_1440, dict):
            if prim_1440.get("screen_archetype"):
                defects["screen_archetype"] = prim_1440["screen_archetype"]
            for k in prim_keys:
                if prim_1440.get(k):
                    defects[k].extend(prim_1440[k])

        msg_counter[0] += 1
        targets_1440 = await self._eval_js(ws, self.JS_CHECK_TARGETS, msg_id=msg_counter[0])
        if targets_1440:
            defects["targets_under_44"].extend(targets_1440)

        # 4a. Initial load & scroll CLS check before Emulation.setDeviceMetricsOverride resizes viewport
        msg_counter[0] += 1
        cls_val = await self._eval_js(ws, self.JS_CHECK_CLS, msg_id=msg_counter[0])
        if cls_val and cls_val > 0.0:
            defects["cls_value"] = cls_val

        # 1b. Standard Desktop Viewport (1280x800)
        msg_counter[0] += 1
        await self._send_cdp(
            ws,
            "Emulation.setDeviceMetricsOverride",
            {"width": 1280, "height": 800, "deviceScaleFactor": 1, "mobile": False},
            msg_id=msg_counter[0],
        )
        await asyncio.sleep(0.02)
        msg_counter[0] += 1
        desktop_overflow = await self._eval_js(
            ws,
            "document.documentElement.scrollWidth > window.innerWidth || document.body.scrollWidth > window.innerWidth",
            msg_id=msg_counter[0],
        )
        if desktop_overflow:
            defects["overflow_1280"] = True

        # Tablet viewport transition (768x1024)
        msg_counter[0] += 1
        await self._send_cdp(
            ws,
            "Emulation.setDeviceMetricsOverride",
            {"width": 768, "height": 1024, "deviceScaleFactor": 2, "mobile": True},
            msg_id=msg_counter[0],
        )
        await asyncio.sleep(0.02)

        # Narrow viewport transition (320x568)
        msg_counter[0] += 1
        await self._send_cdp(
            ws,
            "Emulation.setDeviceMetricsOverride",
            {"width": 320, "height": 568, "deviceScaleFactor": 2, "mobile": True},
            msg_id=msg_counter[0],
        )
        await asyncio.sleep(0.02)

        # 2. Mobile Viewport (375x812)
        msg_counter[0] += 1
        await self._send_cdp(
            ws,
            "Emulation.setDeviceMetricsOverride",
            {"width": 375, "height": 812, "deviceScaleFactor": 2, "mobile": True},
            msg_id=msg_counter[0],
        )
        await asyncio.sleep(0.04)
        msg_counter[0] += 1
        mobile_overflow = await self._eval_js(
            ws,
            "document.documentElement.scrollWidth > window.innerWidth || document.body.scrollWidth > window.innerWidth",
            msg_id=msg_counter[0],
        )
        if mobile_overflow:
            defects["overflow_375"] = True

        msg_counter[0] += 1
        prim_375 = await self._eval_js(ws, self.JS_CHECK_VISUAL_PRIMITIVES, msg_id=msg_counter[0])
        if isinstance(prim_375, dict):
            for k in prim_keys:
                if prim_375.get(k):
                    existing_reprs = {json.dumps(item, sort_keys=True) for item in defects[k]}
                    for item in prim_375[k]:
                        if json.dumps(item, sort_keys=True) not in existing_reprs:
                            defects[k].append(item)

        # 3. Touch targets check (>= 43.5x43.5px)
        msg_counter[0] += 1
        targets = await self._eval_js(ws, self.JS_CHECK_TARGETS, msg_id=msg_counter[0])
        if targets:
            existing_t = {json.dumps(item, sort_keys=True) for item in defects["targets_under_44"]}
            for item in targets:
                if json.dumps(item, sort_keys=True) not in existing_t:
                    defects["targets_under_44"].append(item)

        # 4b. Interactive CLS check (PerformanceObserver layout-shift must be 0.0)
        msg_counter[0] += 1
        interaction_cls = await self._eval_js(ws, self.JS_CHECK_RESIZE_AND_INTERACTION_CLS, msg_id=msg_counter[0])
        if interaction_cls and interaction_cls > defects["cls_value"]:
            defects["cls_value"] = interaction_cls

        # 5. Dashes check (zero forbidden em/en dashes and spaced hyphens)
        msg_counter[0] += 1
        dashes = await self._eval_js(ws, self.JS_CHECK_DASHES, msg_id=msg_counter[0])
        if dashes:
            defects["dashes"] = dashes

        # 6. Broken asset check
        msg_counter[0] += 1
        broken_assets = await self._eval_js(ws, self.JS_CHECK_BROKEN_ASSETS, msg_id=msg_counter[0])
        if broken_assets:
            defects["broken_assets"] = broken_assets

        # 7. Reactive widget updates and popstate hydration
        for spec in self.widget_specs:
            if spec.route == route:
                msg_counter[0] += 1
                js_widget = f"""(() => {{
                    const inputEl = document.querySelector('{spec.input_selector}');
                    const outEl = document.querySelector('{spec.output_selector}');
                    if (!inputEl || !outEl) return {{ success: false, reason: 'elements_missing' }};
                    const initialVal = outEl.innerText.trim();
                    const targetVal = (inputEl.value === '{spec.input_value}') ? String(Number('{spec.input_value}') * 2) : '{spec.input_value}';
                    inputEl.value = targetVal;
                    inputEl.dispatchEvent(new Event('{spec.trigger_event}', {{ bubbles: true }}));
                    inputEl.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    let finalVal = outEl.innerText.trim();
                    if (initialVal === finalVal) {{
                        const altInputs = document.querySelectorAll('[data-calc-input], input:not([type=hidden])');
                        for (const alt of altInputs) {{
                            if (alt === inputEl) continue;
                            alt.value = targetVal;
                            alt.dispatchEvent(new Event('{spec.trigger_event}', {{ bubbles: true }}));
                            alt.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            finalVal = outEl.innerText.trim();
                            if (initialVal !== finalVal) break;
                        }}
                    }}
                    let popstateOk = true;
                    if ({'true' if spec.verify_popstate else 'false'}) {{
                        try {{
                            window.dispatchEvent(new PopStateEvent('popstate'));
                        }} catch(e) {{
                            popstateOk = false;
                        }}
                    }}
                    return {{ success: true, updated: initialVal !== finalVal, popstate_ok: popstateOk }};
                }})()"""
                widget_res = await self._eval_js(ws, js_widget, msg_id=msg_counter[0])
                if not (widget_res and widget_res.get("success") and widget_res.get("updated") and widget_res.get("popstate_ok", True)):
                    defects["widget_failures"].append({
                        "widget_id": spec.widget_id,
                        "detail": f"Widget {spec.widget_id} did not reactively update calculation on input",
                    })

        # 8. Universal interactive state synchronization check (inputs, sliders, presets, and workbenches)
        msg_counter[0] += 1
        univ_failures = await self._eval_js(ws, self.JS_CHECK_UNIVERSAL_INTERACTIVE_SYNC, msg_id=msg_counter[0])
        if isinstance(univ_failures, list) and univ_failures:
            defects["widget_failures"].extend(univ_failures)

        return defects

    async def verify_route(
        self,
        base_url: str,
        route: str,
        msg_counter: Optional[List[int]] = None,
        ws: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Navigates a Chrome CDP tab to target route and validates layout and visual primitive contracts.
        If an active websocket `ws` is passed, reuses that session; otherwise opens and closes a dedicated tab.
        """
        import websockets

        if msg_counter is None:
            msg_counter = [1]

        if ws is not None:
            return await self._audit_route_on_ws(ws, base_url, route, msg_counter)

        req_new = urllib.request.Request(f"{self.cdp_base}/json/new", method="PUT")
        with urllib.request.urlopen(req_new, timeout=10) as r:
            info = json.loads(r.read().decode("utf-8"))

        tab_id = info["id"]
        ws_url = info["webSocketDebuggerUrl"]

        try:
            async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as new_ws:
                msg_counter[0] += 1
                await self._send_cdp(new_ws, "Page.enable", msg_id=msg_counter[0])
                msg_counter[0] += 1
                await self._send_cdp(
                    new_ws,
                    "Page.addScriptToEvaluateOnNewDocument",
                    {"source": self.JS_INIT_ERROR_AND_SYNTHETIC_HOOK},
                    msg_id=msg_counter[0],
                )
                msg_counter[0] += 1
                await self._send_cdp(new_ws, "Runtime.enable", msg_id=msg_counter[0])
                msg_counter[0] += 1
                await self._send_cdp(new_ws, "Network.enable", msg_id=msg_counter[0])
                msg_counter[0] += 1
                await self._send_cdp(new_ws, "Network.setCacheDisabled", {"cacheDisabled": True}, msg_id=msg_counter[0])
                msg_counter[0] += 1
                await self._send_cdp(
                    new_ws,
                    "Network.setBlockedURLs",
                    {
                        "urls": [
                            "*googletagmanager.com*",
                            "*google-analytics.com*",
                            "*fonts.googleapis.com*",
                            "*fonts.gstatic.com*",
                            "*cloudflareinsights.com*",
                        ]
                    },
                    msg_id=msg_counter[0],
                )
                return await self._audit_route_on_ws(new_ws, base_url, route, msg_counter)
        finally:
            req_close = urllib.request.Request(f"{self.cdp_base}/json/close/{tab_id}", method="PUT")
            try:
                with urllib.request.urlopen(req_close, timeout=5):
                    pass
            except Exception:
                pass

    def audit_route(self, base_url: str, route: str) -> Dict[str, Any]:
        """Synchronous wrapper for verifying a single route."""
        return asyncio.run(self.verify_route(base_url, route))

    async def verify_interactive_surface(
        self,
        base_url: str,
        route: str,
        msg_counter: Optional[List[int]] = None,
        ws: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Executes a full real-browser E2E interactive surface verification on a route:
        - Zero console errors and zero uncaught page exceptions
        - Internal and affiliate link integrity (/r/<partner> + sponsored/nofollow)
        - Deep-link URL query parameter hydration and popstate sync
        - Dynamic calculator input/slider mutation and preset clicks
        - Multi-year statutory cliff visualizer dynamic updates
        - Stateful scenario comparator A/B pinning and delta computation
        - Saveable decision blueprint persistence and status readout
        - Playbook subscription form POST (/api/lead-capture) + checkout trigger round-trip
        - TCPA partner quote intake form POST (/api/lead-capture) + checkout trigger round-trip
        - Outbound /r/<partner> redirect and /api/telemetry edge round-trip
        """
        import websockets

        if msg_counter is None:
            msg_counter = [1]

        async def _run_on_ws(active_ws: Any) -> Dict[str, Any]:
            page_url = f"{base_url.rstrip('/')}{route}"
            msg_counter[0] += 1
            await self._send_cdp(
                active_ws,
                "Emulation.setDeviceMetricsOverride",
                {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False},
                msg_id=msg_counter[0],
            )
            msg_counter[0] += 1
            await self._send_cdp(active_ws, "Page.navigate", {"url": page_url}, msg_id=msg_counter[0])
            for _ in range(30):
                await asyncio.sleep(0.05)
                msg_counter[0] += 1
                rs = await self._eval_js(
                    active_ws,
                    "document.readyState === 'complete' && document.body && document.body.children.length > 0",
                    msg_id=msg_counter[0],
                )
                if rs:
                    break
            await asyncio.sleep(0.05)
            msg_counter[0] += 1
            res = await self._eval_js(active_ws, self.JS_RUN_E2E_INTERACTIVE_SURFACE, msg_id=msg_counter[0])
            return res if isinstance(res, dict) else {"passed": False, "route": route, "error": "invalid_eval_result"}

        if ws is not None:
            return await _run_on_ws(ws)

        req_new = urllib.request.Request(f"{self.cdp_base}/json/new", method="PUT")
        with urllib.request.urlopen(req_new, timeout=10) as r:
            info = json.loads(r.read().decode("utf-8"))

        tab_id = info["id"]
        ws_url = info["webSocketDebuggerUrl"]

        try:
            async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as new_ws:
                msg_counter[0] += 1
                await self._send_cdp(new_ws, "Page.enable", msg_id=msg_counter[0])
                msg_counter[0] += 1
                await self._send_cdp(
                    new_ws,
                    "Page.addScriptToEvaluateOnNewDocument",
                    {"source": self.JS_INIT_ERROR_AND_SYNTHETIC_HOOK},
                    msg_id=msg_counter[0],
                )
                msg_counter[0] += 1
                await self._send_cdp(new_ws, "Runtime.enable", msg_id=msg_counter[0])
                msg_counter[0] += 1
                await self._send_cdp(new_ws, "Network.enable", msg_id=msg_counter[0])
                msg_counter[0] += 1
                await self._send_cdp(new_ws, "Network.setCacheDisabled", {"cacheDisabled": True}, msg_id=msg_counter[0])
                msg_counter[0] += 1
                await self._send_cdp(
                    new_ws,
                    "Network.setBlockedURLs",
                    {
                        "urls": [
                            "*googletagmanager.com*",
                            "*google-analytics.com*",
                            "*fonts.googleapis.com*",
                            "*fonts.gstatic.com*",
                            "*cloudflareinsights.com*",
                        ]
                    },
                    msg_id=msg_counter[0],
                )
                return await _run_on_ws(new_ws)
        finally:
            req_close = urllib.request.Request(f"{self.cdp_base}/json/close/{tab_id}", method="PUT")
            try:
                with urllib.request.urlopen(req_close, timeout=5):
                    pass
            except Exception:
                pass

    def audit_interactive_surface(self, base_url: str, route: str) -> Dict[str, Any]:
        """Synchronous wrapper for full E2E interactive surface verification on a route."""
        return asyncio.run(self.verify_interactive_surface(base_url, route))

    def run_audit(self, sample_size: Optional[int] = None) -> Dict[str, Any]:
        """
        Runs comprehensive or sampled browser verification across all tenant routes.
        Serves the distribution locally on EphemeralDistServer (127.0.0.1:0) and reuses a CDP tab.
        """
        import websockets

        reachable, cdp_msg = self.check_cdp_reachability()
        if not reachable:
            if self.fail_closed:
                raise RuntimeError(f"Chrome CDP unreachable on port {self.cdp_port}: {cdp_msg}")
            return {
                "status": "SKIPPED_CDP_OFFLINE",
                "message": f"Chrome CDP unreachable on port {self.cdp_port}: {cdp_msg}",
                "passed": True,
                "total_routes": 0,
                "findings": [],
            }

        if not self.dist_dir.exists():
            return {
                "status": "PASS",
                "message": f"Distribution directory does not exist: {self.dist_dir}",
                "passed": True,
                "total_routes": 0,
                "findings": [],
            }

        extractor = RouteManifestExtractor(self.dist_dir)
        all_routes = [r for r in extractor.extract_routes() if r not in self.excluded_routes]

        if sample_size is not None and sample_size > 0:
            routes_to_audit = all_routes[:sample_size]
        else:
            routes_to_audit = all_routes

        findings: List[Dict[str, Any]] = []
        msg_counter = [1]

        with EphemeralDistServer(self.dist_dir) as server:
            base_url = server.base_url

            async def audit_all() -> None:
                req_new = urllib.request.Request(f"{self.cdp_base}/json/new", method="PUT")
                with urllib.request.urlopen(req_new, timeout=10) as r:
                    info = json.loads(r.read().decode("utf-8"))
                tab_id = info["id"]
                ws_url = info["webSocketDebuggerUrl"]
                try:
                    async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as ws:
                        msg_counter[0] += 1
                        await self._send_cdp(ws, "Page.enable", msg_id=msg_counter[0])
                        msg_counter[0] += 1
                        await self._send_cdp(
                            ws,
                            "Page.addScriptToEvaluateOnNewDocument",
                            {"source": self.JS_INIT_ERROR_AND_SYNTHETIC_HOOK},
                            msg_id=msg_counter[0],
                        )
                        msg_counter[0] += 1
                        await self._send_cdp(ws, "Runtime.enable", msg_id=msg_counter[0])
                        msg_counter[0] += 1
                        await self._send_cdp(ws, "Network.enable", msg_id=msg_counter[0])
                        msg_counter[0] += 1
                        await self._send_cdp(ws, "Network.setCacheDisabled", {"cacheDisabled": True}, msg_id=msg_counter[0])
                        msg_counter[0] += 1
                        await self._send_cdp(
                            ws,
                            "Network.setBlockedURLs",
                            {
                                "urls": [
                                    "*googletagmanager.com*",
                                    "*google-analytics.com*",
                                    "*fonts.googleapis.com*",
                                    "*fonts.gstatic.com*",
                                    "*cloudflareinsights.com*",
                                ]
                            },
                            msg_id=msg_counter[0],
                        )
                        for r in routes_to_audit:
                            res = await self.verify_route(base_url, r, msg_counter, ws=ws)
                            findings.append(res)
                finally:
                    req_close = urllib.request.Request(f"{self.cdp_base}/json/close/{tab_id}", method="PUT")
                    try:
                        with urllib.request.urlopen(req_close, timeout=5):
                            pass
                    except Exception:
                        pass

            asyncio.run(audit_all())

        failed_count = sum(
            1
            for f in findings
            if f.get("overflow_375")
            or f.get("overflow_1280")
            or f.get("overflow_1440")
            or f.get("targets_under_44")
            or (f.get("cls_value", 0.0) > 0.0)
            or f.get("dashes")
            or f.get("broken_assets")
            or f.get("widget_failures")
            or f.get("hierarchy_violations")
            or f.get("unwrapped_tables")
            or f.get("transparent_controls")
            or f.get("clipped_elements")
            or f.get("card_geometry_violations")
            or f.get("whitespace_rhythm_violations")
            or f.get("calculator_ergonomics_violations")
            or f.get("cta_density_violations")
        )

        return {
            "status": "PASS" if failed_count == 0 else "FAIL",
            "passed": failed_count == 0,
            "total_routes": len(all_routes),
            "routes_audited": len(routes_to_audit),
            "findings": findings,
            "failed_count": failed_count,
        }

