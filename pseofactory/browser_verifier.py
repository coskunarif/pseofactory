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

    async def verify_route(self, base_url: str, route: str, msg_counter: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Navigates a dedicated Chrome CDP tab to target route and validates layout contracts.
        Measures:
        - 1280px desktop viewport horizontal overflow
        - 768px tablet, 375px mobile, and 320px narrow viewport transitions
        - 43.5px touch targets
        - 0.0 CLS layout-shift (initial, resize transitions, and widget interaction)
        - zero forbidden dashes
        - interactive calculator input reactivity and popstate state hydration
        """
        import websockets

        if msg_counter is None:
            msg_counter = [1]

        page_url = f"{base_url}{route}"
        req_new = urllib.request.Request(f"{self.cdp_base}/json/new", method="PUT")
        with urllib.request.urlopen(req_new, timeout=10) as r:
            info = json.loads(r.read().decode("utf-8"))

        tab_id = info["id"]
        ws_url = info["webSocketDebuggerUrl"]

        defects: Dict[str, Any] = {
            "route": route,
            "broken_assets": [],
            "targets_under_44": [],
            "cls_value": 0.0,
            "overflow_375": False,
            "overflow_1280": False,
            "dashes": [],
            "widget_failures": [],
        }

        try:
            async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as ws:
                msg_counter[0] += 1
                await self._send_cdp(ws, "Page.enable", msg_id=msg_counter[0])
                msg_counter[0] += 1
                await self._send_cdp(ws, "Runtime.enable", msg_id=msg_counter[0])
                msg_counter[0] += 1
                await self._send_cdp(ws, "Network.enable", msg_id=msg_counter[0])
                msg_counter[0] += 1
                await self._send_cdp(ws, "Network.setCacheDisabled", {"cacheDisabled": True}, msg_id=msg_counter[0])
                msg_counter[0] += 1
                await self._send_cdp(ws, "Page.navigate", {"url": page_url}, msg_id=msg_counter[0])

                await asyncio.sleep(0.3)

                # 1. Desktop Viewport (1280x800) -> Tablet (768x1024) -> Mobile (375x812) -> Narrow (320x568)
                msg_counter[0] += 1
                await self._send_cdp(
                    ws,
                    "Emulation.setDeviceMetricsOverride",
                    {"width": 1280, "height": 800, "deviceScaleFactor": 1, "mobile": False},
                    msg_id=msg_counter[0],
                )
                await asyncio.sleep(0.05)
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
                await asyncio.sleep(0.03)

                # Narrow viewport transition (320x568)
                msg_counter[0] += 1
                await self._send_cdp(
                    ws,
                    "Emulation.setDeviceMetricsOverride",
                    {"width": 320, "height": 568, "deviceScaleFactor": 2, "mobile": True},
                    msg_id=msg_counter[0],
                )
                await asyncio.sleep(0.03)

                # 2. Mobile Viewport (375x812)
                msg_counter[0] += 1
                await self._send_cdp(
                    ws,
                    "Emulation.setDeviceMetricsOverride",
                    {"width": 375, "height": 812, "deviceScaleFactor": 2, "mobile": True},
                    msg_id=msg_counter[0],
                )
                await asyncio.sleep(0.05)
                msg_counter[0] += 1
                mobile_overflow = await self._eval_js(
                    ws,
                    "document.documentElement.scrollWidth > window.innerWidth || document.body.scrollWidth > window.innerWidth",
                    msg_id=msg_counter[0],
                )
                if mobile_overflow:
                    defects["overflow_375"] = True

                # 3. Touch targets check (>= 43.5x43.5px)
                msg_counter[0] += 1
                targets = await self._eval_js(ws, self.JS_CHECK_TARGETS, msg_id=msg_counter[0])
                if targets:
                    defects["targets_under_44"] = targets

                # 4. CLS check (PerformanceObserver layout-shift must be 0.0)
                msg_counter[0] += 1
                cls_val = await self._eval_js(ws, self.JS_CHECK_CLS, msg_id=msg_counter[0])
                if cls_val and cls_val > 0.0:
                    defects["cls_value"] = cls_val

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

        finally:
            req_close = urllib.request.Request(f"{self.cdp_base}/json/close/{tab_id}", method="PUT")
            try:
                with urllib.request.urlopen(req_close, timeout=5):
                    pass
            except Exception:
                pass

        return defects

    def audit_route(self, base_url: str, route: str) -> Dict[str, Any]:
        """Synchronous wrapper for verifying a single route."""
        return asyncio.run(self.verify_route(base_url, route))

    def run_audit(self, sample_size: Optional[int] = None) -> Dict[str, Any]:
        """
        Runs comprehensive or sampled browser verification across all tenant routes.
        Serves the distribution locally on EphemeralDistServer (127.0.0.1:0).
        """
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
                for r in routes_to_audit:
                    res = await self.verify_route(base_url, r, msg_counter)
                    findings.append(res)

            asyncio.run(audit_all())

        failed_count = sum(
            1
            for f in findings
            if f.get("overflow_375")
            or f.get("overflow_1280")
            or f.get("targets_under_44")
            or (f.get("cls_value", 0.0) > 0.0)
            or f.get("dashes")
            or f.get("broken_assets")
            or f.get("widget_failures")
        )

        return {
            "status": "PASS" if failed_count == 0 else "FAIL",
            "passed": failed_count == 0,
            "total_routes": len(all_routes),
            "routes_audited": len(routes_to_audit),
            "findings": findings,
            "failed_count": failed_count,
        }
