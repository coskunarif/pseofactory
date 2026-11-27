"""
Deterministic regression tests for:
1. Same-origin shared-tab navigation barrier & layout-settle / CDP eval error handling
   across UnifiedBrowserAuditor._audit_route_on_ws and verify_interactive_surface (_run_on_ws).
2. Human-mode failure reporting in pseofactory.cli.cmd_audit across all Browser CDP Audit paths.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

import pytest

import pseofactory.cli as pseo_cli
from pseofactory.browser_verifier import InteractiveWidgetSpec, UnifiedBrowserAuditor
from pseofactory.server import EphemeralDistServer


class _FakeCDPWebSocket:
    """
    Minimal stateful CDP WebSocket double modeling a single browser tab reused
    across multiple same-origin navigations.
    """

    def __init__(
        self,
        base_url: str,
        initial_route: str = "/tools/first/",
        stale_polls: int = 3,
        interactive_polls: int = 2,
        transient_context_error_on_poll: Optional[int] = None,
        post_nav_eval_error_keyword: Optional[str] = None,
        post_nav_exception_keyword: Optional[str] = None,
        redirect_map: Optional[Dict[str, str]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.current_route = initial_route
        self.ready_state = "complete"
        self.window_props: Dict[str, Any] = {}
        self.stale_polls = stale_polls
        self.interactive_polls = interactive_polls
        self.transient_context_error_on_poll = transient_context_error_on_poll
        self.post_nav_eval_error_keyword = post_nav_eval_error_keyword
        self.post_nav_exception_keyword = post_nav_exception_keyword
        self.redirect_map = redirect_map or {}

        self._pending_route: Optional[str] = None
        self._polls_since_nav = 0
        self._outbox: List[str] = []
        self.eval_log: List[Tuple[str, str, str]] = []
        self.viewport_widths_seen: List[int] = []
        self._viewport_width = 1440

    @staticmethod
    def _norm_path(path: str) -> str:
        raw = urlsplit(path or "/").path or "/"
        if raw.endswith("/index.html"):
            raw = raw[: -len("/index.html")] or "/"
        if len(raw) > 1 and raw.endswith("/"):
            raw = raw[:-1]
        if raw.endswith(".html"):
            raw = raw[:-5] or "/"
        return raw or "/"

    def _advance_navigation_if_needed(self) -> Optional[Dict[str, Any]]:
        if self._pending_route is None:
            return None
        self._polls_since_nav += 1
        if (
            self.transient_context_error_on_poll is not None
            and self._polls_since_nav == self.transient_context_error_on_poll
        ):
            return {"error": {"code": -32000, "message": "Execution context was destroyed."}}
        if self._polls_since_nav <= self.stale_polls:
            # Tab still holds the previous document on the same origin.
            return None
        if self._polls_since_nav <= self.stale_polls + self.interactive_polls:
            if self.current_route != self._pending_route or self.ready_state == "complete":
                self.current_route = self._pending_route
                self.window_props = {}
                self.ready_state = "interactive"
            return None
        self.current_route = self._pending_route
        self.window_props = {}
        self.ready_state = "complete"
        self._pending_route = None
        return None

    async def send(self, raw_msg: str) -> None:
        req = json.loads(raw_msg)
        msg_id = req["id"]
        method = req["method"]
        params = req.get("params") or {}

        if method == "Emulation.setDeviceMetricsOverride":
            self._viewport_width = int(params.get("width", self._viewport_width))
            self.viewport_widths_seen.append(self._viewport_width)
            self._outbox.append(json.dumps({"id": msg_id, "result": {}}))
            return

        if method == "Page.navigate":
            target_url = str(params.get("url") or "")
            parsed = urlsplit(target_url)
            target_route = parsed.path or "/"
            target_route = self.redirect_map.get(target_route, target_route)
            self._pending_route = target_route
            self._polls_since_nav = 0
            self._outbox.append(json.dumps({"id": msg_id, "result": {"frameId": "main", "loaderId": "loader-2"}}))
            return

        if method == "Runtime.evaluate":
            expr = str(params.get("expression") or "")
            if "__pseoNavNonce =" in expr:
                m = re.search(r"window\.__pseoNavNonce\s*=\s*(\"[^\"]+\")", expr)
                if m:
                    self.window_props["__pseoNavNonce"] = json.loads(m.group(1))
                val = {"stamped": True}
                self._outbox.append(json.dumps({"id": msg_id, "result": {"result": {"type": "object", "value": val}}}))
                return

            if "nonceCleared" in expr:
                nav_err = self._advance_navigation_if_needed()
                if nav_err is not None:
                    self._outbox.append(json.dumps({"id": msg_id, **nav_err}))
                    return
                m_nonce = re.search(r"window\.__pseoNavNonce\s*!==\s*(\"[^\"]+\")", expr)
                expected_nonce = json.loads(m_nonce.group(1)) if m_nonce else None
                m_base = re.search(r"href\.startsWith\((\"[^\"]+\")\)", expr)
                base_prefix = json.loads(m_base.group(1)) if m_base else self.base_url
                m_path = re.search(r"actualPath\s*===\s*(\"[^\"]+\")", expr)
                expected_norm = json.loads(m_path.group(1)) if m_path else "/"
                current_url = f"{self.base_url}{self.current_route}"
                actual_norm = self._norm_path(self.current_route)
                val = {
                    "nonce_cleared": self.window_props.get("__pseoNavNonce") != expected_nonce,
                    "href_ok": current_url.startswith(base_prefix),
                    "ready_complete": self.ready_state == "complete",
                    "has_body": True,
                    "css_ready": True,
                    "target_matched": actual_norm == expected_norm,
                    "actual_path": self.current_route,
                    "ready_state": self.ready_state,
                }
                self._outbox.append(json.dumps({"id": msg_id, "result": {"result": {"type": "object", "value": val}}}))
                return

            if "document.readyState ===" in expr and "window.location.href.startsWith(" in expr:
                nav_err = self._advance_navigation_if_needed()
                if nav_err is not None:
                    self._outbox.append(json.dumps({"id": msg_id, **nav_err}))
                    return
                m_base = re.search(r"window\.location\.href\.startsWith\((\"[^\"]+\")\)", expr)
                base_prefix = json.loads(m_base.group(1)) if m_base else self.base_url
                current_url = f"{self.base_url}{self.current_route}"
                if "document.readyState === 'interactive' || document.readyState === 'complete'" in expr:
                    ready_ok = self.ready_state in ("interactive", "complete")
                else:
                    ready_ok = self.ready_state == "complete"
                val = bool(current_url.startswith(base_prefix) and ready_ok)
                self._outbox.append(json.dumps({"id": msg_id, "result": {"result": {"type": "boolean", "value": val}}}))
                return

            self.eval_log.append((self.current_route, self.ready_state, expr[:80]))

            if self.post_nav_eval_error_keyword and self.post_nav_eval_error_keyword in expr:
                self._outbox.append(
                    json.dumps(
                        {"id": msg_id, "error": {"code": -32000, "message": "Execution context was destroyed."}}
                    )
                )
                return

            if self.post_nav_exception_keyword and self.post_nav_exception_keyword in expr:
                self._outbox.append(
                    json.dumps(
                        {
                            "id": msg_id,
                            "result": {
                                "result": {"type": "object", "subtype": "error"},
                                "exceptionDetails": {
                                    "text": "Uncaught",
                                    "exception": {"description": "TypeError: simulated DOM crash"},
                                },
                            },
                        }
                    )
                )
                return

            if expr.strip() == "window.innerWidth":
                val = self._viewport_width
            elif "requestAnimationFrame" in expr and "innerWidth ===" in expr:
                val = True
            elif "__PSEO_PREVENT_AFFILIATE_NAV__" in expr:
                val = {
                    "route": self.current_route,
                    "console_errors": [],
                    "page_errors": [],
                    "links_audit": {
                        "total_links": 1,
                        "internal_links": 1,
                        "affiliate_links": 0,
                        "invalid_links": [],
                        "unrouted_affiliate_links": [],
                        "internal_hrefs": [],
                        "affiliate_hrefs": [],
                    },
                    "focus_and_keyboard_navigation": {"passed": True},
                    "deep_link_hydration": {"passed": True},
                    "calculator_and_presets": {"passed": True},
                    "cliff_visualizer": {"passed": True},
                    "scenario_comparator": {"passed": True},
                    "blueprint_actions": {"passed": True},
                    "post_calc_upgrade_drawer": {"passed": True},
                    "playbook_lead_capture_and_checkout": {"passed": True},
                    "partner_quote_intake_and_checkout": {"passed": True},
                    "partner_registration_and_slot_checkout": {"passed": True},
                    "hash_navigation_and_focus": {"passed": True},
                    "hero_state_and_range_anchor": {"passed": True},
                    "validation_focus_and_error_states": {"passed": True},
                    "sellable_assets_and_fulfillment_gate": {"passed": True},
                    "affiliate_redirect_and_telemetry": {"passed": True},
                    "passed": True,
                }
            elif "scrollWidth > window.innerWidth" in expr:
                val = False
            elif "screen_archetype" in expr:
                val = {
                    "screen_archetype": "interactive_calculator",
                    "hierarchy_violations": [],
                    "unwrapped_tables": [],
                    "transparent_controls": [],
                    "clipped_elements": [],
                    "card_geometry_violations": [],
                    "whitespace_rhythm_violations": [],
                    "calculator_ergonomics_violations": [],
                    "cta_density_violations": [],
                }
            elif "const undersized = [];" in expr:
                val = []
            elif "layout-shift" in expr:
                val = 0.0
            elif "emEnRegex" in expr or "broken_local_subresource" in expr or "runtime_page_errors" in expr:
                val = []
            elif "elements_missing" in expr:
                if self.current_route == "/tools/second/" and self.ready_state == "complete":
                    val = {"success": True, "updated": True, "popstate_ok": True}
                else:
                    val = {"success": False, "reason": "elements_missing"}
            else:
                val = None

            self._outbox.append(
                json.dumps({"id": msg_id, "result": {"result": {"type": "object", "value": val}}})
            )
            return

        self._outbox.append(json.dumps({"id": msg_id, "result": {}}))

    async def recv(self) -> str:
        return self._outbox.pop(0)


def test_shared_tab_navigation_barrier_blocks_stale_previous_document(tmp_path: Path) -> None:
    """
    Reproduces the same-origin shared-tab race across BOTH _audit_route_on_ws (verify_route)
    and _run_on_ws (verify_interactive_surface). When the reused tab still holds route N-1
    with readyState === 'complete' and transitions through 'interactive' before route N commits,
    the navigation barrier must wait until route N reaches 'complete' in a fresh Window.
    """
    base_url = "http://127.0.0.1:45123"
    auditor = UnifiedBrowserAuditor(dist_dir=tmp_path, fail_closed=True)
    auditor.widget_specs = [
        InteractiveWidgetSpec(
            route="/tools/second/",
            widget_id="second-calc",
            precondition_selector="#inp",
            input_selector="#inp",
            input_value="500",
            output_selector="#out",
        )
    ]

    # 1. verify_route (_audit_route_on_ws) on shared ws starting at stale /tools/first/
    fake_ws = _FakeCDPWebSocket(
        base_url=base_url,
        initial_route="/tools/first/",
        stale_polls=3,
        interactive_polls=2,
        transient_context_error_on_poll=2,
    )
    finding = asyncio.run(auditor.verify_route(base_url, "/tools/second/", ws=fake_ws))

    assert finding["widget_failures"] == [], f"Expected clean widget pass after fresh commit, got: {finding['widget_failures']}"
    assert finding["interactive_surface"]["passed"] is True
    assert finding["interactive_surface"]["route"] == "/tools/second/"
    post_nav_evals = [item for item in fake_ws.eval_log if item[2] != "window.innerWidth"]
    assert post_nav_evals, "Expected post-navigation evaluations to run"
    assert all(r == "/tools/second/" and rs == "complete" for r, rs, _ in post_nav_evals), (
        f"Post-navigation check ran on stale/incomplete document: {post_nav_evals}"
    )

    # 2. verify_interactive_surface (_run_on_ws) on shared ws starting at stale /tools/first/
    fake_ws_e2e = _FakeCDPWebSocket(
        base_url=base_url,
        initial_route="/tools/first/",
        stale_polls=3,
        interactive_polls=2,
    )
    e2e_report = asyncio.run(auditor.verify_interactive_surface(base_url, "/tools/second/", ws=fake_ws_e2e))
    assert e2e_report["passed"] is True
    e2e_evals = [item for item in fake_ws_e2e.eval_log if item[2] != "window.innerWidth"]
    assert e2e_evals
    assert all(r == "/tools/second/" and rs == "complete" for r, rs, _ in e2e_evals), (
        f"verify_interactive_surface evaluated stale/incomplete document: {e2e_evals}"
    )

    # 3. Same-route reload (/tools/second/ -> /tools/second/) must also wait for fresh Window commit
    same_route_ws = _FakeCDPWebSocket(
        base_url=base_url,
        initial_route="/tools/second/",
        stale_polls=3,
        interactive_polls=1,
    )
    same_finding = asyncio.run(auditor.verify_route(base_url, "/tools/second/", ws=same_route_ws))
    assert same_finding["widget_failures"] == []
    assert same_route_ws._polls_since_nav >= 4, "Same-route navigation passed before fresh Window commit"

    # 4. Redirect destination & .html/trailing slash handling still succeeds after nonce cleared
    redir_ws = _FakeCDPWebSocket(
        base_url=base_url,
        initial_route="/tools/first/",
        stale_polls=2,
        interactive_polls=1,
        redirect_map={"/legacy-slug": "/tools/second/"},
    )
    redir_finding = asyncio.run(auditor.verify_route(base_url, "/legacy-slug", ws=redir_ws))
    assert redir_finding["route"] == "/legacy-slug"
    assert redir_finding["interactive_surface"]["route"] == "/tools/second/"
    assert redir_finding["interactive_surface"]["passed"] is True


def test_cdp_eval_error_and_exception_details_fail_closed(tmp_path: Path) -> None:
    """
    CDP Runtime.evaluate protocol errors (destroyed context) or JS exceptionDetails
    after navigation must fail the route cleanly instead of silently passing as None.
    """
    base_url = "http://127.0.0.1:45124"
    auditor = UnifiedBrowserAuditor(dist_dir=tmp_path, fail_closed=True)

    err_ws = _FakeCDPWebSocket(
        base_url=base_url,
        initial_route="/tools/first/",
        stale_polls=1,
        interactive_polls=0,
        post_nav_eval_error_keyword="links_audit",
    )
    err_finding = asyncio.run(auditor.verify_route(base_url, "/tools/second/", ws=err_ws))
    assert err_finding["widget_failures"], "Expected widget_failures when Runtime.evaluate fails post-nav"
    assert err_finding["interactive_surface"]["passed"] is False

    exc_ws = _FakeCDPWebSocket(
        base_url=base_url,
        initial_route="/tools/first/",
        stale_polls=1,
        interactive_polls=0,
        post_nav_exception_keyword="screen_archetype",
    )
    exc_finding = asyncio.run(auditor.verify_route(base_url, "/tools/second/", ws=exc_ws))
    assert exc_finding["widget_failures"], "Expected widget_failures when Runtime.evaluate throws JS exceptionDetails"
    assert exc_finding["interactive_surface"]["passed"] is False


@pytest.mark.host_estate
def test_real_chrome_sequential_shared_tab_audit_with_deferred_script(tmp_path: Path) -> None:
    """
    Real Chrome CDP E2E check across multiple routes in a single shared tab, verifying
    that a calculator hydrated by a deferred external script finishes loading cleanly
    before interactive/visual assertions run.
    """
    auditor = UnifiedBrowserAuditor(dist_dir=tmp_path, fail_closed=True)
    cdp_ok, _ = auditor.check_cdp_reachability()
    if not cdp_ok:
        pytest.skip("Chrome CDP offline")

    from pseofactory.porcelain_shell import compile_tenant_porcelain_estate

    (tmp_path / "static" / "js").mkdir(parents=True, exist_ok=True)
    (tmp_path / "static" / "js" / "calc.js").write_text(
        "document.addEventListener('DOMContentLoaded', () => {"
        "  const inp = document.getElementById('field-amount');"
        "  const out = document.getElementById('val-result');"
        "  if (inp && out) {"
        "    const sync = () => { out.textContent = '$' + String((Number(inp.value) || 0) * 2); };"
        "    const hydrate = () => {"
        "      const raw = (window.location.hash || '').replace(/^#/, '') || window.location.search;"
        "      const q = new URLSearchParams(raw).get('amount');"
        "      if (q !== null) { inp.value = q; }"
        "      sync();"
        "    };"
        "    inp.addEventListener('input', sync);"
        "    inp.addEventListener('change', sync);"
        "    window.addEventListener('hashchange', hydrate);"
        "    window.addEventListener('popstate', hydrate);"
        "    hydrate();"
        "  }"
        "});\n",
        encoding="utf-8",
    )

    def _make_page(title: str, slug_body: str, with_calc: bool = False) -> str:
        calc_block = ""
        script_tag = ""
        if with_calc:
            calc_block = (
                "<section class='card'>"
                "<h2>Calculator Inputs</h2>"
                "<form class='calculator-form'>"
                "<label for='field-amount'>Amount</label>"
                "<input id='field-amount' type='number' value='100'>"
                "<div class='output-value' id='val-result'>$200</div>"
                "</form></section>"
            )
            script_tag = "<script defer src='/static/js/calc.js'></script>"
        return (
            f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
            f"<meta name='description' content='Deterministic test model for {title}.'>"
            f"<title>{title}</title>{script_tag}</head>"
            f"<body><main><h1>{title}</h1><p>{slug_body}</p>{calc_block}</main></body></html>"
        )

    (tmp_path / "index.html").write_text(_make_page("Test Hub", "Deterministic hub page."), encoding="utf-8")
    (tmp_path / "tools").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tools" / "index.html").write_text(_make_page("Tools Directory", "Deterministic tools index."), encoding="utf-8")
    for slug in ("calc-alpha", "calc-beta", "calc-gamma"):
        d = tmp_path / "tools" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(
            _make_page(f"{slug} Calculator", f"Model for {slug}.", with_calc=True),
            encoding="utf-8",
        )
    compile_tenant_porcelain_estate(tmp_path, "profithelm")

    report = auditor.run_audit()
    assert report["passed"] is True, f"Real Chrome sequential audit failed: {report['findings']}"
    assert report["failed_count"] == 0
    assert report["routes_audited"] >= 5


@pytest.mark.host_estate
def test_cli_cmd_audit_prints_per_route_failure_details_across_all_modes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    Verifies human-mode CLI output for Browser CDP Audit prints failing routes,
    widget_failures, interactive_surface reasons, and caps output at 10 routes
    across both default audit and --browser audit paths.
    """
    failing_report = {
        "status": "FAIL",
        "passed": False,
        "total_routes": 167,
        "routes_audited": 167,
        "failed_count": 12,
        "findings": [
            {
                "route": "/tools/good-route/",
                "cls_value": 0.0,
                "overflow_375": False,
                "overflow_1280": False,
                "overflow_1440": False,
                "targets_under_44": [],
                "dashes": [],
                "broken_assets": [],
                "widget_failures": [],
                "interactive_surface": {"passed": True},
            },
            {
                "route": "/tools/broken-calc/",
                "cls_value": 0.12,
                "overflow_375": False,
                "overflow_1280": False,
                "overflow_1440": True,
                "targets_under_44": [],
                "dashes": [],
                "broken_assets": [{"src": "/static/img/missing.png"}],
                "widget_failures": [
                    {"widget_id": "irs-2027-tax-brackets", "detail": "elements_missing"},
                ],
                "interactive_surface": {
                    "passed": False,
                    "console_errors": ["TypeError: cannot read properties of null"],
                    "calculator_and_presets": {"passed": False, "input_failures": ["field-gross_income"]},
                },
                "hierarchy_violations": [{"type": "low_contrast_text"}],
            },
        ]
        + [
            {
                "route": f"/tools/overflow-{idx}/",
                "cls_value": 0.0,
                "overflow_375": True,
                "overflow_1280": False,
                "overflow_1440": False,
                "targets_under_44": [],
                "dashes": [],
                "broken_assets": [],
                "widget_failures": [],
                "interactive_surface": {"passed": True},
            }
            for idx in range(11)
        ],
    }

    class _FakeBrowserAuditor:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def run_audit(self, sample_size: Optional[int] = None) -> Dict[str, Any]:
            return failing_report

    class _PassAssets:
        property_id = "profithelm"
        total_assets_checked = 10
        compliant_assets_count = 10
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

    import pseofactory.browser_verifier as bv_mod

    monkeypatch.setattr(bv_mod, "UnifiedBrowserAuditor", _FakeBrowserAuditor)
    monkeypatch.setattr(pseo_cli, "audit_property_assets", lambda **kw: _PassAssets())
    monkeypatch.setattr(pseo_cli, "_run_seo_fix_checklist_gate", lambda prop_id, as_json: True)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("PSEOFACTORY_SKIP_DEFAULT_BROWSER_AUDIT", raising=False)

    # 1. Default pipeline mode (`python3 -m pseofactory.cli audit --property profithelm`)
    args_default = argparse.Namespace(
        property="profithelm",
        dist_dir=None,
        browser=False,
        no_browser=False,
        sample=None,
        cdp_port=9222,
        fail_closed=False,
        check_engine_drift=False,
        department_handoffs=False,
        json=False,
    )
    rc_default = pseo_cli.cmd_audit(args_default)
    out_default = capsys.readouterr().out
    assert rc_default == 1
    assert "[FAIL] Browser CDP Audit for 'profithelm'" in out_default
    assert "/tools/broken-calc/" in out_default
    assert "irs-2027-tax-brackets" in out_default
    assert "console_errors" in out_default
    assert "calculator_and_presets" in out_default
    assert "1440px" in out_default
    assert "... and 2 more failing route(s)" in out_default
    assert "/tools/good-route/" not in out_default

    # 2. Explicit --browser mode (`--property profithelm --browser`)
    args_browser = argparse.Namespace(**{**vars(args_default), "browser": True})
    rc_browser = pseo_cli.cmd_audit(args_browser)
    out_browser = capsys.readouterr().out
    assert rc_browser == 1
    assert "/tools/broken-calc/" in out_browser
    assert "irs-2027-tax-brackets" in out_browser
    assert "... and 2 more failing route(s)" in out_browser

    # 3. --browser --property all mode
    args_browser_all = argparse.Namespace(**{**vars(args_default), "browser": True, "property": "all"})
    rc_browser_all = pseo_cli.cmd_audit(args_browser_all)
    out_browser_all = capsys.readouterr().out
    assert rc_browser_all == 1
    assert "/tools/broken-calc/" in out_browser_all
    assert "... and 2 more failing route(s)" in out_browser_all
