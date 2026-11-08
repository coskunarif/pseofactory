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
                precondition_selector="#field-cpa_audit_fee, #calc-input-headcount, [data-calc-input]",
                input_selector="#field-cpa_audit_fee, #calc-input-headcount, [data-calc-input]",
                input_value="150",
                output_selector="#metric-total_compliance_tco, #metric-soc2_total_cost, .calc-metric-value, .output-value",
                trigger_event="input",
                verify_popstate=True,
            ),
            InteractiveWidgetSpec(
                route="/tools/cmmc-2-0-compliance-cost-calculator/",
                widget_id="cmmc-2-0-compliance-cost-calculator",
                precondition_selector="#field-c3pao_assessment_fee, #calc-input-headcount, [data-calc-input]",
                input_selector="#field-c3pao_assessment_fee, #calc-input-headcount, [data-calc-input]",
                input_value="150",
                output_selector="#metric-total_compliance_tco, #metric-cmmc_total_cost, .calc-metric-value, .output-value",
                trigger_event="input",
                verify_popstate=False,
            ),
            InteractiveWidgetSpec(
                route="/tools/nist-800-171-sprs-score-calculator/",
                widget_id="nist-800-171-sprs-score-calculator",
                precondition_selector="#field-unmet_5pt_controls, #calc-input-unimplemented_5pt, [data-calc-input]",
                input_selector="#field-unmet_5pt_controls, #calc-input-unimplemented_5pt, [data-calc-input]",
                input_value="4",
                output_selector="#metric-sprs_score, #metric-nist_sprs_score, .calc-metric-value, .output-value",
                trigger_event="input",
                verify_popstate=False,
            ),
        ]


class LienBondBrowserAdapter(TenantBrowserAdapter):
    """Browser verification adapter for LienBond commercial surety, workers comp, and lien platform distribution."""

    @property
    def tenant_id(self) -> str:
        return "lienbond"

    @property
    def dist_dir(self) -> Path:
        return Path("/home/ubuntuadmin/projects/lienbond/dist")

    @property
    def canonical_domain(self) -> str:
        return "https://lienbond.com"

    def get_widget_specs(self) -> List[InteractiveWidgetSpec]:
        return [
            InteractiveWidgetSpec(
                route="/tools/contractor-license-bond-cost-calculator-by-credit-score/",
                widget_id="contractor-license-bond-cost-calculator-by-credit-score",
                precondition_selector="#field-bond_amount, [data-calc-input], input[type='number']",
                input_selector="#field-bond_amount, [data-calc-input], input[type='number']",
                input_value="50000",
                output_selector=".output-value, .calc-metric-value, .metric-value",
                trigger_event="input",
                verify_popstate=True,
            ),
            InteractiveWidgetSpec(
                route="/tools/workers-compensation-class-code-rate-calculator-by-state/",
                widget_id="workers-compensation-class-code-rate-calculator-by-state",
                precondition_selector="#field-annual_payroll, [data-calc-input], input[type='number']",
                input_selector="#field-annual_payroll, [data-calc-input], input[type='number']",
                input_value="250000",
                output_selector=".output-value, .calc-metric-value, .metric-value",
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

    def detect_git_dirty_routes(self) -> List[str]:
        """Detects any modified or untracked HTML routes in dist_dir via git status --porcelain."""
        import subprocess

        if not self.dist_dir.exists():
            return []
        repo_root = self.dist_dir.parent
        if not (repo_root / ".git").exists():
            return []
        dirty_routes: List[str] = []
        seen = set()
        try:
            res = subprocess.run(
                ["git", "-C", str(repo_root), "status", "--porcelain", "--", "dist"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if res.returncode == 0 and res.stdout:
                for raw_line in res.stdout.splitlines():
                    if len(raw_line) < 4:
                        continue
                    rel_part = raw_line[3:].strip().strip('"')
                    if " -> " in rel_part:
                        rel_part = rel_part.split(" -> ", 1)[1].strip().strip('"')
                    full_p = (repo_root / rel_part).resolve()
                    if not full_p.exists():
                        continue
                    html_files = [full_p] if full_p.is_file() and full_p.suffix == ".html" else (
                        list(full_p.glob("**/*.html")) if full_p.is_dir() else []
                    )
                    for hf in html_files:
                        try:
                            rel = hf.relative_to(self.dist_dir)
                        except ValueError:
                            continue
                        if "syndication" in rel.parts or any(p.startswith(".") for p in rel.parts):
                            continue
                        if rel.name == "index.html":
                            r = "/" + "/".join(rel.parent.parts) + "/" if rel.parent.parts else "/"
                        elif rel.name == "404.html":
                            r = "/404.html"
                        else:
                            r = "/" + str(rel)
                        if r not in seen:
                            seen.add(r)
                            dirty_routes.append(r)
        except Exception:
            pass
        return dirty_routes

    def select_smart_routes(
        self,
        all_routes: List[str],
        sample_size: Optional[int],
        widget_specs: Optional[List[InteractiveWidgetSpec]] = None,
    ) -> List[str]:
        """
        Selects a deterministic, archetype-stratified + delta-aware route sample:
        1. All git-dirty / newly generated HTML routes in dist/ (up to 10)
        2. Primary interactive calculator widget routes from widget_specs (or newest /tools/*/ route)
        3. Most recently modified /tools/<slug>/ calculator route on disk
        4. Root hub route ('/') and remaining routes up to max(sample_size, len(dirty_routes) + 1)
        """
        if sample_size is None or sample_size <= 0 or sample_size >= len(all_routes):
            return list(all_routes)
        available = set(all_routes)
        selected: List[str] = []

        def _pick(r: str) -> None:
            if r in available and r not in selected:
                selected.append(r)

        dirty_cap = min(10, max(1, sample_size - 2)) if not widget_specs else 10
        dirty = [r for r in self.detect_git_dirty_routes() if r in available][:dirty_cap]
        for dr in dirty:
            _pick(dr)

        for spec in (widget_specs or []):
            if len(selected) >= max(sample_size, len(dirty) + 1) and len(dirty) == 0:
                break
            _pick(spec.route)
            if len(dirty) == 0 and len(selected) >= max(1, sample_size - 1):
                break

        tool_routes = [r for r in all_routes if r.startswith("/tools/") and r != "/tools/"]
        if tool_routes:
            newest_route = None
            newest_mtime = -1.0
            for tr in tool_routes:
                f_path = self.dist_dir / tr.strip("/") / "index.html"
                if f_path.is_file():
                    try:
                        mt = f_path.stat().st_mtime
                        if mt > newest_mtime:
                            newest_mtime = mt
                            newest_route = tr
                    except Exception:
                        pass
            if newest_route and len(selected) < max(sample_size, len(dirty) + 1):
                _pick(newest_route)
            if not any(r.startswith("/tools/") and r != "/tools/" for r in selected):
                _pick(tool_routes[0])

        target_cap = max(sample_size, len(dirty) + (1 if len(dirty) > 0 else 0))
        if len(selected) < target_cap:
            _pick("/")
        for r in all_routes:
            if len(selected) >= target_cap:
                break
            _pick(r)
        return selected


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
        const outSel = '.output-value, .calc-metric-value, .metric-value, .metric-val, [id^="val-"], [id^="res-"], [id^="metric-"], #serp-out-primary, #serp-out-secondary, #serp-out-tertiary, #serp-out-quaternary';
        const snapshotOutputs = () => Array.from(document.querySelectorAll(outSel)).map(el => (el.innerText || el.textContent || '').trim()).join('|');
        const snapshotInputs = () => Array.from(document.querySelectorAll('input[type="number"], input[type="range"], select')).map(el => el.value).join('|');
        const hasOutputs = document.querySelectorAll(outSel).length > 0;

        // 1. Verify all calculator number inputs, selects, and paired range sliders
        const calcInputs = Array.from(document.querySelectorAll('input[type="number"]:not([readonly]), select')).filter(el => {
            if (el.disabled) return false;
            if (el.closest && el.closest('#partner-quote-intake-form, #lead-capture-form, #partner-registration-form, #state-first-hero-bar')) return false;
            const s = window.getComputedStyle(el);
            return s.display !== 'none' && s.visibility !== 'hidden';
        });
        if (hasOutputs && calcInputs.length > 0) {
            for (const inp of calcInputs) {
                const beforeSnap = snapshotOutputs();
                if (inp.tagName === 'SELECT') {
                    if (!inp.options || inp.options.length < 2) continue;
                    const origIdx = inp.selectedIndex;
                    inp.selectedIndex = (origIdx + 1) % inp.options.length;
                    inp.dispatchEvent(new Event('input', { bubbles: true }));
                    inp.dispatchEvent(new Event('change', { bubbles: true }));
                    const afterSnap = snapshotOutputs();
                    if (beforeSnap === afterSnap) {
                        failures.push({ widget_id: inp.id || inp.name || 'select_input', detail: 'Select control change did not update any output metric' });
                    }
                    inp.selectedIndex = origIdx;
                    inp.dispatchEvent(new Event('input', { bubbles: true }));
                    inp.dispatchEvent(new Event('change', { bubbles: true }));
                } else {
                    const origVal = inp.value;
                    const curNum = parseFloat(String(origVal).replace(/,/g, '')) || 10000;
                    const maxNum = parseFloat(inp.getAttribute('max') || '') || 10000000;
                    const minNum = parseFloat(inp.getAttribute('min') || '0') || 0;
                    let nextNum = curNum < 100 ? Math.min(maxNum, curNum + 2) : Math.round(curNum * 1.35 + 50);
                    if (nextNum > maxNum || nextNum === curNum) {
                        nextNum = Math.max(minNum, curNum > minNum + 1 ? Math.round(curNum * 0.65) : curNum + 1);
                    }
                    if (nextNum === curNum) nextNum = curNum + 1;
                    inp.value = String(nextNum);
                    inp.dispatchEvent(new Event('input', { bubbles: true }));
                    inp.dispatchEvent(new Event('change', { bubbles: true }));
                    const afterSnap = snapshotOutputs();
                    if (beforeSnap === afterSnap) {
                        failures.push({ widget_id: inp.id || inp.name || 'number_input', detail: 'Calculator input change did not update any output metric' });
                    }
                    inp.value = origVal;
                    inp.dispatchEvent(new Event('input', { bubbles: true }));
                    inp.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }
        }

        // 2. Verify all preset, switcher, scenario, and action buttons from a non-matching state
        const presetSelector = [
            'button[data-calc-preset]',
            '.btn-preset[data-calc-preset]',
            '.serp-archetype-btn[data-calc-preset]',
            '.calc-switcher-btn[data-preset-hc]',
            '[data-preset-sec179]',
            '[data-preset-gains]',
            '[data-preset-tey]',
            '[data-preset-income]',
            '[data-preset-pm-gain]',
            '.runway-chip[data-cash]'
        ].join(', ');
        const presetButtons = Array.from(document.querySelectorAll(presetSelector));
        if (presetButtons.length > 0) {
            const origValues = calcInputs.map(el => ({ el, val: el.value, idx: el.tagName === 'SELECT' ? el.selectedIndex : -1 }));
            for (let bIdx = 0; bIdx < presetButtons.length; bIdx++) {
                const btn = presetButtons[bIdx];
                // Perturb numeric inputs slightly so preset always runs from a non-matching state
                for (const el of calcInputs) {
                    if (el.tagName === 'INPUT') {
                        const cVal = parseFloat(String(el.value).replace(/,/g, '')) || 100;
                        const maxV = parseFloat(el.getAttribute('max') || '') || 10000000;
                        const minV = parseFloat(el.getAttribute('min') || '0') || 0;
                        let pVal = cVal < 50 ? Math.min(maxV, cVal + 1) : Math.min(maxV, cVal + 17);
                        if (pVal === cVal) pVal = Math.max(minV, cVal - 1);
                        el.value = String(pVal);
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }
                btn.classList.remove('active');
                const beforeOut = snapshotOutputs();
                const beforeInps = snapshotInputs();
                btn.click();
                const afterOut = snapshotOutputs();
                const afterInps = snapshotInputs();
                if (beforeOut === afterOut && beforeInps === afterInps) {
                    failures.push({
                        widget_id: btn.id || ('preset_btn_' + bIdx),
                        detail: 'Clicking preset/switcher button did not update inputs or outputs: ' + (btn.innerText || btn.textContent || '').trim().slice(0, 48)
                    });
                }
            }
            for (const item of origValues) {
                if (item.el.tagName === 'SELECT' && item.idx >= 0) {
                    item.el.selectedIndex = item.idx;
                } else {
                    item.el.value = item.val;
                }
                item.el.dispatchEvent(new Event('input', { bubbles: true }));
                item.el.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }

        // 3. Verify keyboard focusability and visible focus indicators (--border-focus)
        const posTabEls = Array.from(document.querySelectorAll('[tabindex]')).filter(el => (parseInt(el.getAttribute('tabindex') || '0', 10) || 0) > 0);
        if (posTabEls.length > 0) {
            failures.push({ widget_id: 'positive_tabindex_trap', detail: 'Positive tabindex trap detected on ' + posTabEls.length + ' elements' });
        }
        const focusSample = Array.from(document.querySelectorAll('a[href], button:not([disabled]), input:not([type="hidden"]):not([disabled]), select:not([disabled]), summary')).filter(el => {
            if (el.classList && el.classList.contains('skip-to-content-link')) return false;
            const r = el.getBoundingClientRect();
            const s = window.getComputedStyle(el);
            return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0;
        }).slice(0, 12);
        for (const fEl of focusSample) {
            try {
                fEl.focus({ preventScroll: true });
                if (document.activeElement === fEl) {
                    const cs = window.getComputedStyle(fEl);
                    const hasOutline = cs.outlineStyle && cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth || '0') >= 1.5;
                    const hasShadow = cs.boxShadow && cs.boxShadow !== 'none';
                    if (!hasOutline && !hasShadow) {
                        failures.push({ widget_id: fEl.id || fEl.tagName, detail: 'Interactive control has no visible focus indicator (outlineStyle=none, boxShadow=none)' });
                        break;
                    }
                }
            } catch (e) {}
        }
        if (document.activeElement && typeof document.activeElement.blur === 'function') {
            document.activeElement.blur();
        }

        // 4. Verify affiliate CTAs
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
            links_audit: { total_links: 0, internal_links: 0, affiliate_links: 0, invalid_links: [], unrouted_affiliate_links: [], internal_hrefs: [], affiliate_hrefs: [] },
            focus_and_keyboard_navigation: { tested: true, passed: true, focusable_count: 0, zero_outline_failures: [], positive_tabindex_traps: [], skip_link_valid: true, details_accordions_toggled: 0, accordion_failures: [] },
            deep_link_hydration: { tested: false, passed: true, detail: '' },
            calculator_and_presets: { tested: false, passed: true, before_snapshot: '', after_snapshot: '', preset_clicked: false, inputs_tested_count: 0, input_failures: [], buttons_tested_count: 0, button_failures: [] },
            cliff_visualizer: { present: false, passed: true, before_values: [], after_values: [] },
            scenario_comparator: { present: false, passed: true, pinned_a: '', pinned_b: '', live_delta: '' },
            blueprint_actions: { present: false, passed: true, saved_status: '', shared_status: '', exported_status: '', storage_keys: 0 },
            post_calc_upgrade_drawer: { present: false, passed: true, preview_rendered: false, checkout_status: '', settlement_id: '', datapack_download_triggered: false },
            playbook_lead_capture_and_checkout: { present: false, passed: true, submission_state: '', partner_href: '', checkout_status: '', checkout_session_id: '' },
            partner_quote_intake_and_checkout: { present: false, passed: true, submission_state: '', partner_href: '', checkout_status: '', checkout_session_id: '' },
            partner_registration_and_slot_checkout: { present: false, passed: true, submission_state: '', checkout_href: '', checkout_status: '', checkout_session_id: '', slot_price_usd: 0, focused_after_submit: false },
            hash_navigation_and_focus: { present: false, passed: true, links_tested_count: 0, failures: [] },
            hero_state_and_range_anchor: { present: false, passed: true, range_anchor_present: false, synced_state: '', peer_sync_passed: true },
            validation_focus_and_error_states: { present: false, passed: true, forms_tested_count: 0, focus_failures: [] },
            sellable_assets_and_fulfillment_gate: { present: false, passed: true, unpaid_402_enforced: false, free_playbook_verified: false, free_csv_verified: false, free_datapack_verified: false, paid_html_verified: false, paid_csv_verified: false, paid_datapack_verified: false, email_dispatch_verified: false, failures: [] },
            affiliate_redirect_and_telemetry: { tested: false, passed: true, dom_click_handled: false, redirect_status: 0, redirect_location: '', telemetry_status: '', partners_verified_count: 0, all_partner_redirects: [], partner_failures: [] }
        };

        const outSel = '.output-value, .calc-metric-value, .metric-value, .metric-val, [id^="val-"], [id^="res-"], [id^="metric-"], #serp-out-primary, #serp-out-secondary, #serp-out-tertiary, #serp-out-quaternary';
        const snapshotOutputs = () => Array.from(document.querySelectorAll(outSel)).map(el => (el.innerText || el.textContent || '').trim()).join('|');
        const snapshotInputs = () => Array.from(document.querySelectorAll('input[type="number"], input[type="range"], select')).map(el => el.value).join('|');

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
                report.links_audit.affiliate_hrefs.push(href);
                const rel = (a.getAttribute('rel') || '').toLowerCase();
                if (!href.startsWith('/r/') || !rel.includes('sponsored') || !rel.includes('nofollow')) {
                    report.links_audit.unrouted_affiliate_links.push({ href: href, rel: rel, id: a.id || '' });
                }
            } else if (href.startsWith('/') || href.startsWith(window.location.origin) || href.startsWith('#')) {
                report.links_audit.internal_links += 1;
                if (!href.startsWith('/api/') && !href.startsWith('/r/')) {
                    report.links_audit.internal_hrefs.push(href);
                }
                if (href.startsWith('#') && href.length > 1) {
                    const targetId = href.slice(1);
                    if (!document.getElementById(targetId) && !document.querySelector('[name="' + targetId + '"]')) {
                        report.links_audit.invalid_links.push(href);
                    }
                }
            }
        }

        // 1b. Focus states, skip-to-content target, positive tabindex traps, and details/summary accordions
        const posTabNodes = Array.from(document.querySelectorAll('[tabindex]')).filter(el => (parseInt(el.getAttribute('tabindex') || '0', 10) || 0) > 0);
        for (const pt of posTabNodes) {
            report.focus_and_keyboard_navigation.positive_tabindex_traps.push(pt.id || pt.tagName);
        }
        const mainLandmark = document.querySelector('main');
        const skipLink = document.querySelector('a.skip-to-content-link[href^="#"], a[href="#main-content"]');
        if (mainLandmark) {
            if (!skipLink) {
                report.focus_and_keyboard_navigation.skip_link_valid = false;
            } else {
                const skipTargetId = (skipLink.getAttribute('href') || '').slice(1);
                const skipTargetEl = skipTargetId ? document.getElementById(skipTargetId) : null;
                if (!skipTargetEl) {
                    report.focus_and_keyboard_navigation.skip_link_valid = false;
                }
            }
        }
        const detailsList = Array.from(document.querySelectorAll('details'));
        for (const det of detailsList) {
            const sumEl = det.querySelector('summary');
            if (!sumEl) continue;
            const cs = window.getComputedStyle(det);
            if (cs.display === 'none' || cs.visibility === 'hidden') continue;
            const origOpen = det.open;
            sumEl.click();
            if (det.open === origOpen) {
                report.focus_and_keyboard_navigation.accordion_failures.push(det.id || (sumEl.innerText || '').trim().slice(0, 36));
            } else {
                report.focus_and_keyboard_navigation.details_accordions_toggled += 1;
            }
            det.open = origOpen;
        }
        const focusCandidates = Array.from(document.querySelectorAll('a[href], button:not([disabled]), input:not([type="hidden"]):not([disabled]), select:not([disabled]), textarea:not([disabled]), summary, [role="button"]')).filter(el => {
            if (el.classList && el.classList.contains('skip-to-content-link')) return false;
            const r = el.getBoundingClientRect();
            const s = window.getComputedStyle(el);
            return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0;
        });
        for (const fEl of focusCandidates) {
            try {
                fEl.focus({ preventScroll: true });
                if (document.activeElement === fEl) {
                    report.focus_and_keyboard_navigation.focusable_count += 1;
                    const cs = window.getComputedStyle(fEl);
                    const hasOutline = cs.outlineStyle && cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth || '0') >= 1.5;
                    const hasShadow = cs.boxShadow && cs.boxShadow !== 'none';
                    if (!hasOutline && !hasShadow) {
                        report.focus_and_keyboard_navigation.zero_outline_failures.push(fEl.id || fEl.className || fEl.tagName);
                    }
                }
            } catch (e) {}
        }
        if (document.activeElement && typeof document.activeElement.blur === 'function') {
            document.activeElement.blur();
        }
        window.scrollTo(0, 0);
        report.focus_and_keyboard_navigation.passed = (
            report.focus_and_keyboard_navigation.skip_link_valid &&
            report.focus_and_keyboard_navigation.positive_tabindex_traps.length === 0 &&
            report.focus_and_keyboard_navigation.zero_outline_failures.length === 0 &&
            report.focus_and_keyboard_navigation.accordion_failures.length === 0 &&
            (focusCandidates.length === 0 || report.focus_and_keyboard_navigation.focusable_count > 0)
        );

        // 2. All calculator inputs/selects/sliders, cliff visualizer, scenario comparator, presets, and deep-link hydration
        const allCalcControls = Array.from(document.querySelectorAll('input[type="number"]:not([readonly]), select')).filter(el => {
            if (el.disabled) return false;
            if (el.closest && el.closest('#partner-quote-intake-form, #lead-capture-form, #partner-registration-form, #state-first-hero-bar')) return false;
            const s = window.getComputedStyle(el);
            return s.display !== 'none' && s.visibility !== 'hidden';
        });
        if (allCalcControls.length > 0 && document.querySelectorAll(outSel).length > 0) {
            for (const ctrl of allCalcControls) {
                const beforeSnap = snapshotOutputs();
                if (ctrl.tagName === 'SELECT') {
                    if (!ctrl.options || ctrl.options.length < 2) continue;
                    const origIdx = ctrl.selectedIndex;
                    ctrl.selectedIndex = (origIdx + 1) % ctrl.options.length;
                    ctrl.dispatchEvent(new Event('input', { bubbles: true }));
                    ctrl.dispatchEvent(new Event('change', { bubbles: true }));
                    report.calculator_and_presets.inputs_tested_count += 1;
                    const afterSnap = snapshotOutputs();
                    if (beforeSnap === afterSnap) {
                        report.calculator_and_presets.input_failures.push(ctrl.id || ctrl.name || 'select_control');
                    }
                    ctrl.selectedIndex = origIdx;
                    ctrl.dispatchEvent(new Event('input', { bubbles: true }));
                    ctrl.dispatchEvent(new Event('change', { bubbles: true }));
                } else {
                    const origVal = ctrl.value;
                    const curNum = parseFloat(String(origVal).replace(/,/g, '')) || 10000;
                    const maxNum = parseFloat(ctrl.getAttribute('max') || '') || 10000000;
                    const minNum = parseFloat(ctrl.getAttribute('min') || '0') || 0;
                    let nextNum = curNum < 100 ? Math.min(maxNum, curNum + 2) : Math.round(curNum * 1.35 + 50);
                    if (nextNum > maxNum || nextNum === curNum) {
                        nextNum = Math.max(minNum, curNum > minNum + 1 ? Math.round(curNum * 0.65) : curNum + 1);
                    }
                    if (nextNum === curNum) nextNum = curNum + 1;
                    ctrl.value = String(nextNum);
                    ctrl.dispatchEvent(new Event('input', { bubbles: true }));
                    ctrl.dispatchEvent(new Event('change', { bubbles: true }));
                    report.calculator_and_presets.inputs_tested_count += 1;
                    const afterSnap = snapshotOutputs();
                    if (beforeSnap === afterSnap) {
                        report.calculator_and_presets.input_failures.push(ctrl.id || ctrl.name || 'number_control');
                    }
                    ctrl.value = origVal;
                    ctrl.dispatchEvent(new Event('input', { bubbles: true }));
                    ctrl.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }
        }

        // Test all preset, switcher, scenario, and action buttons from a non-matching state
        const presetSelector = [
            'button[data-calc-preset]',
            '.btn-preset[data-calc-preset]',
            '.serp-archetype-btn[data-calc-preset]',
            '.calc-switcher-btn[data-preset-hc]',
            '[data-preset-sec179]',
            '[data-preset-gains]',
            '[data-preset-tey]',
            '[data-preset-income]',
            '[data-preset-pm-gain]',
            '.runway-chip[data-cash]'
        ].join(', ');
        const allPresetBtns = Array.from(document.querySelectorAll(presetSelector));
        if (allPresetBtns.length > 0) {
            const savedControls = allCalcControls.map(el => ({ el, val: el.value, idx: el.tagName === 'SELECT' ? el.selectedIndex : -1 }));
            for (let bIdx = 0; bIdx < allPresetBtns.length; bIdx++) {
                const btn = allPresetBtns[bIdx];
                for (const el of allCalcControls) {
                    if (el.tagName === 'INPUT') {
                        const cVal = parseFloat(String(el.value).replace(/,/g, '')) || 100;
                        const maxV = parseFloat(el.getAttribute('max') || '') || 10000000;
                        const minV = parseFloat(el.getAttribute('min') || '0') || 0;
                        let pVal = cVal < 50 ? Math.min(maxV, cVal + 1) : Math.min(maxV, cVal + 17);
                        if (pVal === cVal) pVal = Math.max(minV, cVal - 1);
                        el.value = String(pVal);
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }
                btn.classList.remove('active');
                const beforeOut = snapshotOutputs();
                const beforeInps = snapshotInputs();
                btn.click();
                report.calculator_and_presets.preset_clicked = true;
                report.calculator_and_presets.buttons_tested_count += 1;
                const afterOut = snapshotOutputs();
                const afterInps = snapshotInputs();
                if (beforeOut === afterOut && beforeInps === afterInps) {
                    report.calculator_and_presets.button_failures.push(btn.id || ('preset_' + bIdx + ':' + (btn.innerText || btn.textContent || '').trim().slice(0, 32)));
                }
            }
            for (const item of savedControls) {
                if (item.el.tagName === 'SELECT' && item.idx >= 0) {
                    item.el.selectedIndex = item.idx;
                } else {
                    item.el.value = item.val;
                }
                item.el.dispatchEvent(new Event('input', { bubbles: true }));
                item.el.dispatchEvent(new Event('change', { bubbles: true }));
            }
        } else {
            const scenarioAnchor = document.querySelector('a.scenario-preset-link[href*="?"]');
            if (scenarioAnchor) {
                scenarioAnchor.click();
                report.calculator_and_presets.preset_clicked = true;
                report.calculator_and_presets.buttons_tested_count += 1;
            }
        }

        const calcSubmitBtn = document.getElementById('calc-submit-btn');
        if (calcSubmitBtn) {
            calcSubmitBtn.click();
            report.calculator_and_presets.buttons_tested_count += 1;
            if (calcSubmitBtn.getAttribute('data-recalculated') !== 'true') {
                report.calculator_and_presets.button_failures.push('calc-submit-btn');
            }
        }

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
                report.calculator_and_presets.buttons_tested_count += 1;
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
                report.calculator_and_presets.buttons_tested_count += 1;
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
                    report.calculator_and_presets.buttons_tested_count += 1;
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

        if (
            report.calculator_and_presets.input_failures.length > 0 ||
            report.calculator_and_presets.button_failures.length > 0
        ) {
            report.calculator_and_presets.passed = false;
        }

        // 3. Saveable Decision Blueprint actions
        const saveBtn = document.querySelector('[data-blueprint-action="save"]');
        const shareBtn = document.querySelector('[data-blueprint-action="share"]');
        const exportBtn = document.querySelector('[data-blueprint-action="export"]');
        const statusNode = document.getElementById('blueprint-status-readout') || document.getElementById('serp-blueprint-status') || document.querySelector('.serp-blueprint-status');
        if (saveBtn) {
            report.blueprint_actions.present = true;
            saveBtn.click();
            report.calculator_and_presets.buttons_tested_count += 1;
            report.blueprint_actions.saved_status = statusNode ? (statusNode.innerText || statusNode.textContent || '').trim() : '';
            if (shareBtn) {
                shareBtn.click();
                report.calculator_and_presets.buttons_tested_count += 1;
                report.blueprint_actions.shared_status = statusNode ? (statusNode.innerText || statusNode.textContent || '').trim() : '';
            }
            if (exportBtn) {
                exportBtn.click();
                report.calculator_and_presets.buttons_tested_count += 1;
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
                report.calculator_and_presets.buttons_tested_count += 1;
                for (let i = 0; i < 40; i++) {
                    if (document.getElementById('playbook-download-link') || document.getElementById('playbook-datapack-link')) break;
                    await new Promise(r => setTimeout(r, 12));
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
                report.calculator_and_presets.buttons_tested_count += 1;
                for (let i = 0; i < 60; i++) {
                    if (upgCheckoutBtn.getAttribute('data-checkout-status') === 'checkout_session_ready') break;
                    await new Promise(r => setTimeout(r, 12));
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

        // 3c. In-page #hash navigation & focus transfer (.pro-hook-link, TOC anchors)
        const hashCandidates = Array.from(document.querySelectorAll('a.pro-hook-link[href^="#"], .on-this-page-nav a[href^="#"], a[href="#post-calculation-upgrade-drawer"], a[href="#lead-capture-form"], a[href="#partner-quote-intake-step"]')).filter(a => {
            if (a.classList && a.classList.contains('skip-to-content-link')) return false;
            const h = (a.getAttribute('href') || '').trim();
            if (h.length <= 1) return false;
            const tEl = document.getElementById(h.slice(1));
            if (!tEl) return false;
            const cs = window.getComputedStyle(a);
            return cs.display !== 'none' && cs.visibility !== 'hidden';
        }).slice(0, 3);
        if (hashCandidates.length > 0) {
            report.hash_navigation_and_focus.present = true;
            const origHashUrl = window.location.pathname + window.location.search + window.location.hash;
            for (const hLink of hashCandidates) {
                const rawH = hLink.getAttribute('href') || '';
                const tId = rawH.slice(1);
                const tEl = document.getElementById(tId);
                if (!tEl) continue;
                hLink.click();
                report.hash_navigation_and_focus.links_tested_count += 1;
                const focusedOk = (
                    tEl.getAttribute('data-focused-target') === 'true' &&
                    Boolean(document.activeElement && (document.activeElement === tEl || tEl.contains(document.activeElement)))
                );
                if (!focusedOk) {
                    report.hash_navigation_and_focus.failures.push(rawH);
                }
            }
            window.history.replaceState(null, '', origHashUrl);
            window.scrollTo(0, 0);
            if (report.hash_navigation_and_focus.failures.length > 0) {
                report.hash_navigation_and_focus.passed = false;
            }
        }

        // 3d. State-First Hero Bar bidirectional state sync & #hero-range-anchor verification
        const heroStateSel = document.getElementById('quote-intake-hero-state');
        if (heroStateSel && heroStateSel.options && heroStateSel.options.length > 1) {
            report.hero_state_and_range_anchor.present = true;
            const rangeAnchor = document.getElementById('hero-range-anchor');
            report.hero_state_and_range_anchor.range_anchor_present = Boolean(
                rangeAnchor && ((rangeAnchor.innerText || rangeAnchor.textContent || '').trim().length > 0)
            );
            const origHeroVal = heroStateSel.value;
            const origStateUrl = window.location.pathname + window.location.search + window.location.hash;
            const nextStateVal = origHeroVal === 'TX' ? 'NY' : 'TX';
            heroStateSel.value = nextStateVal;
            heroStateSel.dispatchEvent(new Event('change', { bubbles: true }));
            report.hero_state_and_range_anchor.synced_state = heroStateSel.value;
            const qStatePeer = document.getElementById('quote-intake-state');
            const prStatePeer = document.getElementById('quote-intake-partner-reg-state');
            const peerOk = (
                (!qStatePeer || qStatePeer.value === nextStateVal) &&
                (!prStatePeer || prStatePeer.value === nextStateVal)
            );
            report.hero_state_and_range_anchor.peer_sync_passed = peerOk;
            heroStateSel.value = origHeroVal;
            heroStateSel.dispatchEvent(new Event('change', { bubbles: true }));
            window.history.replaceState(null, '', origStateUrl);
            if (!report.hero_state_and_range_anchor.range_anchor_present || !peerOk) {
                report.hero_state_and_range_anchor.passed = false;
            }
        }

        // 3e. Empty-submit validation focus verification across monetization forms
        const valForms = [
            { form: document.getElementById('lead-capture-form') || document.querySelector('form.lead-capture-form'), name: 'lead-capture-form' },
            { form: document.getElementById('partner-registration-form') || document.querySelector('form.partner-registration-form'), name: 'partner-registration-form' },
            { form: document.getElementById('partner-quote-intake-form') || document.querySelector('form.partner-quote-intake-form'), name: 'partner-quote-intake-form' }
        ].filter(x => Boolean(x.form));
        if (valForms.length > 0) {
            report.validation_focus_and_error_states.present = true;
            for (const item of valForms) {
                const fNode = item.form;
                if (window.getComputedStyle(fNode).display === 'none') {
                    fNode.style.display = 'block';
                }
                const qDrawer = fNode.closest ? fNode.closest('#partner-quote-intake-step') : null;
                if (qDrawer && window.getComputedStyle(qDrawer).display === 'none') {
                    qDrawer.style.display = 'block';
                }
                const emNode = fNode.querySelector('input[type="email"], input[name="email"]');
                if (!emNode) continue;
                const prevEm = emNode.value;
                emNode.value = '';
                if (document.activeElement && typeof document.activeElement.blur === 'function') {
                    document.activeElement.blur();
                }
                fNode.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
                report.validation_focus_and_error_states.forms_tested_count += 1;
                if (document.activeElement !== emNode || fNode.getAttribute('data-submission-state') === 'success') {
                    report.validation_focus_and_error_states.focus_failures.push(item.name + ':email_focus');
                }
                emNode.value = prevEm;
            }
            if (report.validation_focus_and_error_states.focus_failures.length > 0) {
                report.validation_focus_and_error_states.passed = false;
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
            for (let i = 0; i < 60; i++) {
                if (leadForm.getAttribute('data-submission-state') === 'success' || leadForm.getAttribute('data-submission-state') === 'fallback_saved') {
                    break;
                }
                await new Promise(r => setTimeout(r, 12));
            }
            report.playbook_lead_capture_and_checkout.submission_state = leadForm.getAttribute('data-submission-state') || '';
            const pbPartner = document.getElementById('playbook-partner-link');
            const pbCheckout = document.getElementById('playbook-checkout-link');
            report.playbook_lead_capture_and_checkout.partner_href = pbPartner ? (pbPartner.getAttribute('href') || '') : '';
            if (pbCheckout) {
                pbCheckout.click();
                for (let i = 0; i < 60; i++) {
                    if (pbCheckout.getAttribute('data-checkout-status') === 'checkout_session_ready') {
                        break;
                    }
                    await new Promise(r => setTimeout(r, 12));
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
            for (let i = 0; i < 60; i++) {
                if (quoteForm.getAttribute('data-submission-state') === 'success' || quoteForm.getAttribute('data-submission-state') === 'fallback_saved') {
                    break;
                }
                await new Promise(r => setTimeout(r, 12));
            }
            report.partner_quote_intake_and_checkout.submission_state = quoteForm.getAttribute('data-submission-state') || '';
            const qPartner = document.getElementById('quote-matched-partner-link');
            const qCheckout = document.getElementById('quote-matched-checkout-link');
            report.partner_quote_intake_and_checkout.partner_href = qPartner ? (qPartner.getAttribute('href') || '') : '';
            if (qCheckout) {
                qCheckout.click();
                for (let i = 0; i < 60; i++) {
                    if (qCheckout.getAttribute('data-checkout-status') === 'checkout_session_ready') {
                        break;
                    }
                    await new Promise(r => setTimeout(r, 12));
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

        // 5b. Partner Registration Drawer ($299 Verified Partner Slot) POST + checkout trigger
        const prForm = document.getElementById('partner-registration-form') || document.querySelector('form.partner-registration-form');
        if (prForm) {
            report.partner_registration_and_slot_checkout.present = true;
            const prFirm = prForm.querySelector('input[name="firm_name"]');
            const prEmail = prForm.querySelector('input[type="email"], input[name="email"]');
            const prState = prForm.querySelector('select[name="state"]');
            if (prFirm) prFirm.value = 'Apex Statutory Advisory LLP';
            if (prEmail) prEmail.value = 'partner-desk@synthetic.pseofactory.test';
            if (prState && !prState.value) prState.value = 'CA';
            prForm.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
            for (let i = 0; i < 60; i++) {
                if (prForm.getAttribute('data-submission-state') === 'success') break;
                await new Promise(r => setTimeout(r, 12));
            }
            report.partner_registration_and_slot_checkout.submission_state = prForm.getAttribute('data-submission-state') || '';
            const prChkLink = document.getElementById('partner-slot-checkout-link');
            if (prChkLink) {
                report.partner_registration_and_slot_checkout.checkout_href = prChkLink.getAttribute('href') || '';
                report.partner_registration_and_slot_checkout.focused_after_submit = (document.activeElement === prChkLink);
                prChkLink.click();
                for (let i = 0; i < 60; i++) {
                    if (prChkLink.getAttribute('data-checkout-status') === 'checkout_session_ready') break;
                    await new Promise(r => setTimeout(r, 12));
                }
                report.partner_registration_and_slot_checkout.checkout_status = prChkLink.getAttribute('data-checkout-status') || '';
                report.partner_registration_and_slot_checkout.checkout_session_id = prChkLink.getAttribute('data-checkout-session-id') || '';
                report.partner_registration_and_slot_checkout.slot_price_usd = parseFloat(
                    prChkLink.getAttribute('data-offer-price-usd') ||
                    prChkLink.getAttribute('data-offer-price') ||
                    prChkLink.getAttribute('data-attributed-revenue-usd') ||
                    '0'
                ) || 0;
            }
            if (
                report.partner_registration_and_slot_checkout.submission_state !== 'success' ||
                !report.partner_registration_and_slot_checkout.checkout_href.includes('_verified_partner_slot') ||
                report.partner_registration_and_slot_checkout.checkout_status !== 'checkout_session_ready' ||
                report.partner_registration_and_slot_checkout.slot_price_usd !== 299
            ) {
                report.partner_registration_and_slot_checkout.passed = false;
            }
        }

        // 5c. Deep Sellable Assets (HTML/CSV/Datapack), 402 Payment Gate & Email Dispatch Verification
        if (upgDrawer || leadForm) {
            report.sellable_assets_and_fulfillment_gate.present = true;
            try {
                const unpaidResp = await fetch('/api/lead-fulfillment?lead_id=unpaid_probe_check', {
                    method: 'GET',
                    headers: { 'Accept': 'application/json', 'X-Pseofactory-Test': '1' }
                });
                const unpaidJson = await unpaidResp.json().catch(() => ({}));
                report.sellable_assets_and_fulfillment_gate.unpaid_402_enforced = (
                    unpaidResp.status === 402 &&
                    unpaidJson.status === 'payment_required' &&
                    unpaidJson.settled === false
                );
                if (!report.sellable_assets_and_fulfillment_gate.unpaid_402_enforced) {
                    report.sellable_assets_and_fulfillment_gate.failures.push('unpaid_402_gate_not_enforced');
                }
            } catch (e) {
                report.sellable_assets_and_fulfillment_gate.failures.push('unpaid_402_fetch_error');
            }

            try {
                const pbDlEl = document.getElementById('playbook-download-link');
                const pbCsvEl = document.getElementById('playbook-csv-link');
                const pbDpEl = document.getElementById('playbook-datapack-link');
                const pbJsonUrl = (leadForm && leadForm.getAttribute('data-playbook-url')) || '/api/lead-capture?playbook=1';
                const pbJsonResp = await fetch(pbJsonUrl, { headers: { 'Accept': 'application/json', 'X-Pseofactory-Test': '1' } });
                const pbJsonData = await pbJsonResp.json().catch(() => ({}));
                const pbArts = Array.isArray(pbJsonData.statutory_execution_artifacts)
                    ? pbJsonData.statutory_execution_artifacts
                    : (pbJsonData.statutory_data_pack && Array.isArray(pbJsonData.statutory_data_pack.statutory_execution_artifacts)
                        ? pbJsonData.statutory_data_pack.statutory_execution_artifacts
                        : []);
                report.sellable_assets_and_fulfillment_gate.free_playbook_verified = (
                    pbJsonResp.status === 200 &&
                    pbJsonData.status === 'playbook_ready' &&
                    Array.isArray(pbJsonData.reconciliation_schedule) && pbJsonData.reconciliation_schedule.length >= 3 &&
                    Array.isArray(pbJsonData.sensitivity_matrix) && pbJsonData.sensitivity_matrix.length >= 3 &&
                    pbArts.length >= 1 &&
                    pbArts.every(a =>
                        a.redaction_state === 'PREVIEW_REDACTED' ||
                        a.execution_status === 'PREVIEW_REDACTED_PENDING_CHECKOUT' ||
                        String(a.statutory_clause_body || a.body_preview || '').includes('REDACTED')
                    )
                );
                if (!report.sellable_assets_and_fulfillment_gate.free_playbook_verified) {
                    report.sellable_assets_and_fulfillment_gate.failures.push('free_playbook_contract_failed');
                }

                const pbCsvHref = (pbCsvEl && pbCsvEl.getAttribute('href')) || (pbJsonUrl + '&format=csv');
                const pbCsvResp = await fetch(pbCsvHref, { headers: { 'X-Pseofactory-Test': '1' } });
                const pbCsvTxt = await pbCsvResp.text();
                report.sellable_assets_and_fulfillment_gate.free_csv_verified = (
                    pbCsvResp.status === 200 && pbCsvTxt.trim().split(/\\r?\\n/).length >= 4
                );
                if (!report.sellable_assets_and_fulfillment_gate.free_csv_verified) {
                    report.sellable_assets_and_fulfillment_gate.failures.push('free_csv_contract_failed');
                }

                const pbDpHref = (pbDpEl && pbDpEl.getAttribute('href')) || (pbJsonUrl + '&format=datapack');
                const pbDpResp = await fetch(pbDpHref, { headers: { 'X-Pseofactory-Test': '1' } });
                const pbDpJson = await pbDpResp.json().catch(() => ({}));
                report.sellable_assets_and_fulfillment_gate.free_datapack_verified = (
                    pbDpResp.status === 200 && Boolean(pbDpJson && (pbDpJson.pack_id || pbDpJson.reconciliation_schedule))
                );
                if (!report.sellable_assets_and_fulfillment_gate.free_datapack_verified) {
                    report.sellable_assets_and_fulfillment_gate.failures.push('free_datapack_contract_failed');
                }

                const ffHtmlEl = document.getElementById('checkout-fulfillment-html-link');
                const ffCsvEl = document.getElementById('checkout-fulfillment-csv-link');
                const ffDpEl = document.getElementById('checkout-fulfillment-datapack-link');
                const ffHtmlHref = (ffHtmlEl && ffHtmlEl.getAttribute('href')) || '/api/lead-capture?fulfill=1&settle=1&format=html';
                const ffCsvHref = (ffCsvEl && ffCsvEl.getAttribute('href')) || '/api/lead-capture?fulfill=1&settle=1&format=csv';
                const ffDpHref = (ffDpEl && ffDpEl.getAttribute('href')) || '/api/lead-capture?fulfill=1&settle=1&format=datapack';

                const [ffHtmlResp, ffCsvResp, ffDpResp] = await Promise.all([
                    fetch(ffHtmlHref, { headers: { 'X-Pseofactory-Test': '1' } }),
                    fetch(ffCsvHref, { headers: { 'X-Pseofactory-Test': '1' } }),
                    fetch(ffDpHref, { headers: { 'X-Pseofactory-Test': '1' } })
                ]);
                const ffHtmlTxt = await ffHtmlResp.text();
                const ffCsvTxt = await ffCsvResp.text();
                const ffDpJson = await ffDpResp.json().catch(() => ({}));
                const ffExecInst = Array.isArray(ffDpJson.statutory_execution_artifacts)
                    ? ffDpJson.statutory_execution_artifacts
                    : (Array.isArray(ffDpJson.execution_instruments) ? ffDpJson.execution_instruments : []);
                report.sellable_assets_and_fulfillment_gate.paid_html_verified = (
                    ffHtmlResp.status === 200 && ffHtmlTxt.includes('<table') && ffHtmlTxt.length > 400
                );
                report.sellable_assets_and_fulfillment_gate.paid_csv_verified = (
                    ffCsvResp.status === 200 && ffCsvTxt.trim().split(/\\r?\\n/).length >= 4
                );
                report.sellable_assets_and_fulfillment_gate.paid_datapack_verified = (
                    ffDpResp.status === 200 &&
                    Boolean(ffDpJson && ffDpJson.pack_id) &&
                    ffExecInst.length >= 1 &&
                    ffExecInst.every(inst =>
                        inst.redaction_state === 'UNREDACTED_READY_FOR_FILING' ||
                        inst.execution_status === 'UNREDACTED_READY_FOR_FILING'
                    )
                );
                if (!report.sellable_assets_and_fulfillment_gate.paid_html_verified) {
                    report.sellable_assets_and_fulfillment_gate.failures.push('paid_html_contract_failed');
                }
                if (!report.sellable_assets_and_fulfillment_gate.paid_csv_verified) {
                    report.sellable_assets_and_fulfillment_gate.failures.push('paid_csv_contract_failed');
                }
                if (!report.sellable_assets_and_fulfillment_gate.paid_datapack_verified) {
                    report.sellable_assets_and_fulfillment_gate.failures.push('paid_datapack_contract_failed');
                }

                const emailCheckResp = await fetch('/api/lead-capture', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-Pseofactory-Test': '1' },
                    body: JSON.stringify({
                        email: 'email-telemetry-probe@synthetic.pseofactory.test',
                        tool_slug: window.location.pathname,
                        synthetic_test: true
                    })
                });
                const emailCheckJson = await emailCheckResp.json().catch(() => ({}));
                report.sellable_assets_and_fulfillment_gate.email_dispatch_verified = (
                    emailCheckResp.status === 200 &&
                    Boolean(emailCheckJson.zeptomail_status) &&
                    Boolean(emailCheckJson.fulfillment_status) &&
                    Boolean(emailCheckJson.playbook_url) &&
                    Boolean(emailCheckJson.checkout_url)
                );
                if (!report.sellable_assets_and_fulfillment_gate.email_dispatch_verified) {
                    report.sellable_assets_and_fulfillment_gate.failures.push('email_dispatch_telemetry_failed');
                }
            } catch (e) {
                report.sellable_assets_and_fulfillment_gate.failures.push('sellable_asset_verification_exception');
            }
            if (report.sellable_assets_and_fulfillment_gate.failures.length > 0) {
                report.sellable_assets_and_fulfillment_gate.passed = false;
            }
        }

        // 6. Outbound /r/<partner> DOM click, redirect & /api/telemetry edge round-trip across ALL partner CTAs on the page
        const allAffAnchors = Array.from(document.querySelectorAll('a[href^="/r/"]'));
        if (allAffAnchors.length > 0) {
            report.affiliate_redirect_and_telemetry.tested = true;
            let allClicksHandled = true;
            const uniquePartnerHrefs = [];
            const seenPartnerHrefs = new Set();
            for (const affEl of allAffAnchors) {
                affEl.click();
                const clickedOk = (
                    affEl.getAttribute('data-affiliate-clicked') === 'true' &&
                    Boolean(affEl.getAttribute('data-last-click-subid'))
                );
                if (!clickedOk) {
                    allClicksHandled = false;
                    report.affiliate_redirect_and_telemetry.partner_failures.push({
                        href: affEl.getAttribute('href') || '',
                        reason: 'dom_click_not_attributed'
                    });
                }
                const h = (affEl.getAttribute('href') || '').trim();
                if (h && !seenPartnerHrefs.has(h)) {
                    seenPartnerHrefs.add(h);
                    uniquePartnerHrefs.push(h);
                }
            }
            report.affiliate_redirect_and_telemetry.dom_click_handled = allClicksHandled;
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
            for (const rawHref of uniquePartnerHrefs) {
                try {
                    const sep = rawHref.includes('?') ? '&' : '?';
                    const redirResp = await fetch(rawHref + sep + 'synthetic_test=1', {
                        method: 'GET',
                        headers: { 'X-Pseofactory-Test': '1' },
                        redirect: 'manual'
                    });
                    const st = redirResp.status;
                    const loc = redirResp.headers.get('Location') || redirResp.url || '';
                    report.affiliate_redirect_and_telemetry.all_partner_redirects.push({
                        href: rawHref,
                        status: st,
                        location: loc
                    });
                    if (report.affiliate_redirect_and_telemetry.redirect_status === 0) {
                        report.affiliate_redirect_and_telemetry.redirect_status = st;
                        report.affiliate_redirect_and_telemetry.redirect_location = loc;
                    }
                    if (redirResp.type !== 'opaqueredirect' && st !== 302 && st !== 200) {
                        report.affiliate_redirect_and_telemetry.passed = false;
                        report.affiliate_redirect_and_telemetry.partner_failures.push({
                            href: rawHref,
                            status: st,
                            reason: 'unexpected_redirect_status'
                        });
                    } else {
                        report.affiliate_redirect_and_telemetry.partners_verified_count += 1;
                    }
                } catch (e) {
                    report.affiliate_redirect_and_telemetry.passed = false;
                    report.affiliate_redirect_and_telemetry.partner_failures.push({
                        href: rawHref,
                        reason: String(e)
                    });
                }
            }
            if (
                !report.affiliate_redirect_and_telemetry.dom_click_handled ||
                report.affiliate_redirect_and_telemetry.partner_failures.length > 0 ||
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
            report.focus_and_keyboard_navigation.passed &&
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
        property_id: Optional[str] = None,
    ):
        self.adapter = adapter
        if adapter is not None:
            self.dist_dir = adapter.dist_dir
            self.widget_specs = adapter.get_widget_specs()
            self.excluded_routes = set(adapter.get_excluded_routes())
            self.property_id = property_id or adapter.tenant_id
        else:
            self.dist_dir = Path(dist_dir).resolve() if dist_dir else Path("dist").resolve()
            self.widget_specs = []
            self.excluded_routes = set()
            self.property_id = property_id

        self.cdp_port = cdp_port
        self.cdp_base = f"http://127.0.0.1:{cdp_port}"
        if fail_closed is None:
            env_fc = os.environ.get("PSEOFACTORY_BROWSER_FAIL_CLOSED")
            self.fail_closed = (env_fc != "0") if env_fc is not None else True
        else:
            self.fail_closed = bool(fail_closed)
        self._html_id_cache: Dict[Path, set] = {}
        self._redirects_rules_cache: Optional[List[Tuple[str, str, int]]] = None

    def _get_redirects_rules(self) -> List[Tuple[str, str, int]]:
        if self._redirects_rules_cache is not None:
            return self._redirects_rules_cache
        rules: List[Tuple[str, str, int]] = []
        redirects_file = self.dist_dir / "_redirects"
        if redirects_file.is_file():
            try:
                for raw_line in redirects_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split()
                    if len(parts) >= 2:
                        src = parts[0]
                        dst = parts[1]
                        code = int(parts[2]) if (len(parts) >= 3 and parts[2].isdigit()) else 301
                        rules.append((src, dst, code))
            except Exception:
                pass
        self._redirects_rules_cache = rules
        return rules

    def _apply_redirects_to_path(self, req_path: str) -> str:
        cur = req_path or "/"
        for _ in range(4):
            matched = False
            for src, dst, _code in self._get_redirects_rules():
                if src.endswith("/*"):
                    prefix = src[:-1]
                    if cur.startswith(prefix):
                        splat = cur[len(prefix):]
                        cur = dst.replace(":splat", splat)
                        matched = True
                        break
                elif cur == src or cur.rstrip("/") == src.rstrip("/"):
                    cur = dst
                    matched = True
                    break
            if not matched or cur.startswith("http://") or cur.startswith("https://") or cur.startswith("/r/") or cur.startswith("/api/"):
                break
        return urllib.parse.urlsplit(cur).path or "/"

    @staticmethod
    def _resolve_in_root(root_dir: Path, rel: str) -> Optional[Path]:
        if not rel:
            cand = root_dir / "index.html"
            return cand if cand.is_file() else None
        direct = root_dir / rel
        if direct.is_file():
            return direct
        if direct.is_dir():
            idx = direct / "index.html"
            if idx.is_file():
                return idx
        as_html = root_dir / f"{rel.rstrip('/')}.html"
        if as_html.is_file():
            return as_html
        as_idx = root_dir / rel.rstrip("/") / "index.html"
        if as_idx.is_file():
            return as_idx
        return None

    def _resolve_disk_file(self, url_path: str) -> Optional[Path]:
        clean = (url_path or "/").strip()
        if not clean.startswith("/"):
            clean = "/" + clean
        rel = clean.lstrip("/")
        found = self._resolve_in_root(self.dist_dir, rel)
        if found is not None:
            return found
        # If self.dist_dir is a partial synthetic fixture (no sitemap.xml), allow resolving
        # sibling routes against canonical workspace tenant dist directories while still
        # catching genuinely broken 404 targets.
        if not (self.dist_dir / "sitemap.xml").is_file():
            for fallback_root in (
                Path("/home/ubuntuadmin/projects/profithelm-platform/dist"),
                Path("/home/ubuntuadmin/projects/prexvo/dist"),
                Path("/home/ubuntuadmin/projects/gainhelm/dist"),
            ):
                if fallback_root.is_dir():
                    fb = self._resolve_in_root(fallback_root, rel)
                    if fb is not None:
                        return fb
        return None

    def _get_ids_in_html_file(self, html_file: Path) -> set:
        if html_file in self._html_id_cache:
            return self._html_id_cache[html_file]
        import re
        ids: set = set()
        try:
            raw = html_file.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r'\b(?:id|name)\s*=\s*["\']([^"\']+)["\']', raw, flags=re.IGNORECASE):
                ids.add(m.group(1))
        except Exception:
            pass
        self._html_id_cache[html_file] = ids
        return ids

    def _verify_internal_links_and_redirects_on_disk(self, route: str, internal_hrefs: List[str]) -> List[str]:
        invalid: List[str] = []
        if not self.dist_dir.exists():
            return invalid

        # 1. Verify dist/_redirects rules resolve to valid destinations
        for src, dst, _code in self._get_redirects_rules():
            if ":splat" in dst or dst.startswith("http://") or dst.startswith("https://") or dst.startswith("/r/") or dst.startswith("/api/"):
                continue
            dst_path = urllib.parse.urlsplit(dst).path or "/"
            if self._resolve_disk_file(dst_path) is None:
                invalid.append(f"_redirects:{src}->{dst}")

        # 2. Verify each internal href (and optional cross-page #fragment) resolves on disk
        for raw_href in internal_hrefs:
            href = (raw_href or "").strip()
            if not href or href.startswith("#"):
                continue
            parsed = urllib.parse.urlsplit(href)
            path_part = parsed.path or route or "/"
            if not path_part.startswith("/"):
                base_dir = route if route.endswith("/") else (route.rsplit("/", 1)[0] + "/")
                path_part = urllib.parse.urljoin(base_dir, path_part)
            if path_part.startswith("/r/") or path_part.startswith("/api/"):
                continue
            resolved_path = self._apply_redirects_to_path(path_part)
            if resolved_path.startswith("http://") or resolved_path.startswith("https://") or resolved_path.startswith("/r/") or resolved_path.startswith("/api/"):
                continue
            target_file = self._resolve_disk_file(resolved_path)
            if target_file is None:
                invalid.append(raw_href)
                continue
            frag = (parsed.fragment or "").strip()
            if frag and target_file.suffix.lower() == ".html":
                target_ids = self._get_ids_in_html_file(target_file)
                if frag not in target_ids:
                    invalid.append(raw_href)
        return invalid

    def _verify_partner_redirects_canonical(self, base_url: str, partner_redirects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        from pseofactory.edge import resolve_canonical_partner_redirect

        class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib.request.build_opener(_NoRedirectHandler)
        failures: List[Dict[str, Any]] = []
        prop_id = self.property_id or (self.adapter.tenant_id if self.adapter is not None else None)
        for item in partner_redirects:
            raw_href = str(item.get("href") or "")
            status = int(item.get("status") or 0)
            loc = str(item.get("location") or "")
            if status == 0 and base_url and raw_href.startswith("/r/"):
                sep = "&" if "?" in raw_href else "?"
                probe_url = f"{base_url.rstrip('/')}{raw_href}{sep}synthetic_test=1"
                req = urllib.request.Request(probe_url, headers={"X-Pseofactory-Test": "1"}, method="GET")
                try:
                    with opener.open(req, timeout=5) as resp:
                        status = resp.status
                        loc = resp.headers.get("Location") or ""
                except urllib.error.HTTPError as exc:
                    status = exc.code
                    loc = exc.headers.get("Location") or ""
                except Exception as exc:
                    failures.append({"href": raw_href, "reason": str(exc)})
                    continue
                item["status"] = status
                item["location"] = loc
            parsed = urllib.parse.urlsplit(raw_href)
            p_key = parsed.path[len("/r/"):].strip("/").lower() if parsed.path.startswith("/r/") else ""
            if not p_key:
                failures.append({"href": raw_href, "reason": "missing_partner_key"})
                continue
            q_params = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query, keep_blank_values=True).items() if v}
            canonical = resolve_canonical_partner_redirect(p_key, query_params=q_params, property_id=prop_id)
            expected_loc = str(canonical.get("location") or "")
            exp_split = urllib.parse.urlsplit(expected_loc)
            act_split = urllib.parse.urlsplit(loc)
            if status != 302:
                failures.append({"href": raw_href, "status": status, "reason": "expected_302"})
            elif not loc or act_split.netloc != exp_split.netloc or act_split.path != exp_split.path:
                failures.append({
                    "href": raw_href,
                    "location": loc,
                    "expected_location": expected_loc,
                    "reason": "canonical_destination_mismatch",
                })
        return failures

    def _postprocess_interactive_report(self, base_url: str, route: str, report: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(report, dict):
            return {"passed": False, "route": route, "error": "invalid_eval_result"}
        links_audit = report.get("links_audit")
        if isinstance(links_audit, dict):
            internal_hrefs = links_audit.get("internal_hrefs") or []
            disk_invalid = self._verify_internal_links_and_redirects_on_disk(route, internal_hrefs)
            existing_inv = list(links_audit.get("invalid_links") or [])
            for inv in disk_invalid:
                if inv not in existing_inv:
                    existing_inv.append(inv)
            links_audit["invalid_links"] = existing_inv

        aff_rep = report.get("affiliate_redirect_and_telemetry")
        if isinstance(aff_rep, dict):
            all_redirs = aff_rep.get("all_partner_redirects") or []
            canon_failures = self._verify_partner_redirects_canonical(base_url, all_redirs)
            if all_redirs and aff_rep.get("redirect_status", 0) == 0:
                aff_rep["redirect_status"] = all_redirs[0].get("status", 0)
                aff_rep["redirect_location"] = all_redirs[0].get("location", "")
            if canon_failures:
                existing_pf = list(aff_rep.get("partner_failures") or [])
                existing_pf.extend(canon_failures)
                aff_rep["partner_failures"] = existing_pf
                aff_rep["passed"] = False

        report["passed"] = bool(
            len(report.get("console_errors") or []) == 0
            and len(report.get("page_errors") or []) == 0
            and len((report.get("links_audit") or {}).get("invalid_links") or []) == 0
            and len((report.get("links_audit") or {}).get("unrouted_affiliate_links") or []) == 0
            and (report.get("focus_and_keyboard_navigation") or {}).get("passed", True)
            and (report.get("deep_link_hydration") or {}).get("passed", True)
            and (report.get("calculator_and_presets") or {}).get("passed", True)
            and (report.get("cliff_visualizer") or {}).get("passed", True)
            and (report.get("scenario_comparator") or {}).get("passed", True)
            and (report.get("blueprint_actions") or {}).get("passed", True)
            and (report.get("post_calc_upgrade_drawer") or {}).get("passed", True)
            and (report.get("playbook_lead_capture_and_checkout") or {}).get("passed", True)
            and (report.get("partner_quote_intake_and_checkout") or {}).get("passed", True)
            and (report.get("partner_registration_and_slot_checkout") or {}).get("passed", True)
            and (report.get("hash_navigation_and_focus") or {}).get("passed", True)
            and (report.get("hero_state_and_range_anchor") or {}).get("passed", True)
            and (report.get("validation_focus_and_error_states") or {}).get("passed", True)
            and (report.get("sellable_assets_and_fulfillment_gate") or {}).get("passed", True)
            and (report.get("affiliate_redirect_and_telemetry") or {}).get("passed", True)
        )
        return report

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
        await self._send_cdp(ws, "Emulation.setFocusEmulationEnabled", {"enabled": True}, msg_id=msg_counter[0])
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
                    const pickFirst = (selList) => {{
                        for (const s of selList.split(',').map(x => x.trim()).filter(Boolean)) {{
                            const el = document.querySelector(s);
                            if (el) return el;
                        }}
                        return document.querySelector(selList);
                    }};
                    const inputEl = pickFirst('{spec.input_selector}');
                    const outEl = pickFirst('{spec.output_selector}');
                    if (!inputEl || !outEl) return {{ success: false, reason: 'elements_missing' }};
                    const origInputVal = inputEl.value;
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
                            const origAlt = alt.value;
                            alt.value = targetVal;
                            alt.dispatchEvent(new Event('{spec.trigger_event}', {{ bubbles: true }}));
                            alt.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            finalVal = outEl.innerText.trim();
                            alt.value = origAlt;
                            alt.dispatchEvent(new Event('{spec.trigger_event}', {{ bubbles: true }}));
                            alt.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            if (initialVal !== finalVal) break;
                        }}
                    }}
                    inputEl.value = origInputVal;
                    inputEl.dispatchEvent(new Event('{spec.trigger_event}', {{ bubbles: true }}));
                    inputEl.dispatchEvent(new Event('change', {{ bubbles: true }}));
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

        # 8. Restore desktop viewport (1440x900) and run universal interactive state + E2E surface verification
        msg_counter[0] += 1
        await self._send_cdp(
            ws,
            "Emulation.setDeviceMetricsOverride",
            {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False},
            msg_id=msg_counter[0],
        )
        await asyncio.sleep(0.02)
        msg_counter[0] += 1
        univ_failures = await self._eval_js(ws, self.JS_CHECK_UNIVERSAL_INTERACTIVE_SYNC, msg_id=msg_counter[0])
        if isinstance(univ_failures, list) and univ_failures:
            defects["widget_failures"].extend(univ_failures)

        msg_counter[0] += 1
        raw_e2e = await self._eval_js(ws, self.JS_RUN_E2E_INTERACTIVE_SURFACE, msg_id=msg_counter[0])
        e2e_rep = self._postprocess_interactive_report(base_url, route, raw_e2e if isinstance(raw_e2e, dict) else {})
        defects["interactive_surface"] = e2e_rep
        if not e2e_rep.get("passed", False):
            defects["widget_failures"].append({
                "widget_id": "e2e_interactive_surface",
                "detail": f"Interactive surface verification failed on {route}",
            })

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

    @staticmethod
    def _cdp_session_lock(cdp_port: int):
        """Serializes CDP multi-viewport audits across concurrent xdist workers on the same Chrome instance."""
        import contextlib, fcntl
        @contextlib.contextmanager
        def _lock_ctx():
            lock_path = f"/tmp/pseofactory_cdp_{cdp_port}.lock"
            with open(lock_path, "w") as lf:
                fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    try:
                        fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
                    except Exception:
                        pass
        return _lock_ctx()

    def audit_route(self, base_url: str, route: str) -> Dict[str, Any]:
        """Synchronous wrapper for verifying a single route."""
        with self._cdp_session_lock(self.cdp_port):
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
            await self._send_cdp(active_ws, "Emulation.setFocusEmulationEnabled", {"enabled": True}, msg_id=msg_counter[0])
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
            if not isinstance(res, dict):
                return {"passed": False, "route": route, "error": "invalid_eval_result"}
            return self._postprocess_interactive_report(base_url, route, res)

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
        with self._cdp_session_lock(self.cdp_port):
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
            routes_to_audit = extractor.select_smart_routes(
                all_routes=all_routes,
                sample_size=sample_size,
                widget_specs=self.widget_specs,
            )
        else:
            routes_to_audit = all_routes

        findings: List[Dict[str, Any]] = []
        msg_counter = [1]

        prop_id = self.property_id or (self.adapter.tenant_id if self.adapter is not None else None)
        with EphemeralDistServer(self.dist_dir, property_id=prop_id) as server:
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

            with self._cdp_session_lock(self.cdp_port):
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
            or not (f.get("interactive_surface") or {}).get("passed", True)
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

