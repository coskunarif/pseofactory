"""
Ephemeral loopback HTTP distribution server for pseofactory.
Binds to 127.0.0.1:0 for kernel-allocated dynamic ports, preventing port collisions.
Enforces strict path confinement to eliminate directory traversal escapes.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

import http.server
import json
import os
from pathlib import Path
import re
import socketserver
import threading
import time
from typing import Any, Dict, List, Optional, Union
import urllib.parse


_LOCAL_PARTNER_DESTINATIONS: Dict[str, str] = {
    "ipx1031": "https://xendoo.pxf.io/c/7932737/1357375/16354",
    "crest_capital": "https://xendoo.pxf.io/c/7932737/1357375/16354",
    "equipment_macrs": "https://xendoo.pxf.io/c/7932737/1357375/16354",
    "xendoo": "https://xendoo.pxf.io/c/7932737/1357375/16354",
    "bench": "https://xendoo.pxf.io/c/7932737/1357375/16354",
    "pilot": "https://xendoo.pxf.io/c/7932737/1357375/16354",
    "mercury": "https://mercury.com/partner/profithelm",
    "rippling": "https://try.rippling.com/mcfo1m09qiwt",
    "coinledger": "https://coinledger.io/?fpr=arif79",
    "koinly": "https://koinly.io/?via=C9AC2AD5&utm_source=affiliate",
    "kalshi": "https://kalshi.com/sign-up/?referral=f003999f-7392-4be9-b6d4-376d7de7ae7c",
    "turbotax": "https://www.jdoqocy.com/click-101906407-11917161",
    "taxslayer": "https://www.dpbolvw.net/click-101906407-15704796",
    "freetaxusa": "https://www.dpbolvw.net/click-101906407-15704796",
    "efile": "https://www.jdoqocy.com/click-101906407-11917161",
    "eztaxreturn": "https://www.dpbolvw.net/click-101906407-15704796",
    "lawdepot": "https://www.jdoqocy.com/click-101906407-16985242",
    "suretybonds_direct": "https://www.jdoqocy.com/click-101906407-16985242",
    "otr_solutions_factoring": "https://www.otrsolutions.com/freight-factoring/",
    "splash_financial": "https://www.splashfinancial.com/partner/prexvo",
    "credible_student_loans": "https://www.credible.com/refinance-student-loans",
    "sofi_student_refi": "https://www.sofi.com/refinance-student-loan/",
    "sofi_refi": "https://www.sofi.com/refinance-student-loan/",
    "earnest_student_refi": "https://www.earnest.com/refinance-student-loans",
    "lendkey_student_refi": "https://www.lendkey.com/student-loan-refinancing/",
    "laurel_road": "https://www.laurelroad.com/student-loan-refinancing/",
    "juno": "https://joinjuno.com/student-loan-refinancing",
    "wealthfront": "https://www.wealthfront.com/",
    "fundrise": "https://fundrise.com/",
    "stripe": "https://stripe.com/",
    "ramp": "https://ramp.com/",
    "rho": "https://www.rho.co/",
    "gusto": "https://gusto.com/",
}


def _sanitize_telemetry_dict(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_sanitize_telemetry_dict(x) for x in obj]
    if not isinstance(obj, dict):
        return obj
    forbidden = ("email", "password", "token", "secret", "name", "ssn", "phone")
    cleaned: Dict[str, Any] = {}
    for k, v in obj.items():
        kl = str(k).lower()
        if any(term in kl for term in forbidden):
            continue
        if isinstance(v, str):
            if re.search(r"[^\s@]+@[^\s@]+\.[^\s@]+", v):
                continue
            cleaned[k] = v[:500]
        elif isinstance(v, (dict, list)):
            cleaned[k] = _sanitize_telemetry_dict(v)
        else:
            cleaned[k] = v
    return cleaned


class QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """
    HTTP request handler with suppressed logging, strict path confinement,
    and built-in local edge route emulation (/api/lead-capture, /api/telemetry, /r/<partner>).
    Prevents path traversal attempts (e.g. '../') escaping the distribution root.
    """

    def __init__(self, *args, directory: Optional[Union[str, Path]] = None, **kwargs):
        if directory is None:
            directory = getattr(self, "server_root_dir", None) or os.getcwd()
        self.root_dir = os.path.realpath(str(directory))
        super().__init__(*args, directory=self.root_dir, **kwargs)

    def log_message(self, format: str, *args) -> None:
        """Suppress standard HTTP request logging."""
        pass

    def _send_json(self, status_code: int, payload: Dict[str, Any], extra_headers: Optional[Dict[str, str]] = None) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "private, no-cache, no-store, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept, Authorization, X-Pseofactory-Test")
        if extra_headers:
            for hk, hv in extra_headers.items():
                self.send_header(hk, hv)
        self.end_headers()
        self.wfile.write(body)

    def _is_traversal_attempt(self) -> bool:
        """
        Determines whether the incoming request attempts directory traversal.
        Checks unquoted URL components and verifies resolved canonical path
        is strictly confined within root_dir using os.path.commonpath.
        """
        raw_path = self.path.split("?", 1)[0].split("#", 1)[0]
        unquoted = urllib.parse.unquote(raw_path)
        parts = [p for p in unquoted.split("/") if p]
        if any(p == ".." for p in parts) or ".." in unquoted:
            return True

        translated = super().translate_path(self.path)
        abs_translated = os.path.realpath(translated)
        root = os.path.realpath(self.root_dir)
        try:
            if os.path.commonpath([abs_translated, root]) != root:
                return True
        except Exception:
            return True
        return False

    def _detect_property_id(self) -> str:
        root_low = self.root_dir.lower()
        if "prexvo" in root_low:
            return "prexvo"
        return "profithelm"

    def _handle_affiliate_redirect(self, is_head: bool = False) -> None:
        parsed_url = urllib.parse.urlsplit(self.path)
        partner = parsed_url.path[len("/r/"):].strip("/").lower()
        dest_base = _LOCAL_PARTNER_DESTINATIONS.get(partner)
        if not dest_base:
            try:
                from pseofactory.affiliates import PREXVO_AFFILIATES, PROFITHELM_AFFILIATES
                if partner in PROFITHELM_AFFILIATES:
                    dest_base = PROFITHELM_AFFILIATES[partner].default_url
                elif partner in PREXVO_AFFILIATES:
                    dest_base = PREXVO_AFFILIATES[partner].default_url
            except Exception:
                dest_base = None
        if not dest_base:
            self.send_error(404, "Partner not found")
            return

        in_qs = urllib.parse.parse_qs(parsed_url.query, keep_blank_values=False)
        dest_split = urllib.parse.urlsplit(dest_base)
        out_qs = urllib.parse.parse_qs(dest_split.query, keep_blank_values=False)
        for k in ("subid", "click_id", "utm_source", "utm_medium", "utm_campaign", "utm_content", "source_tool", "cta_slot", "ph_tier", "tier"):
            if k in in_qs and in_qs[k]:
                out_qs[k] = [in_qs[k][0]]
        source_tool = in_qs.get("source_tool", ["direct"])[0]
        cta_slot = in_qs.get("cta_slot", ["edge_redirect"])[0]
        subid = in_qs.get("subid", [f"{source_tool}_{cta_slot}"])[0]
        out_qs.setdefault("subid", [subid])
        final_query = urllib.parse.urlencode(out_qs, doseq=True)
        final_url = urllib.parse.urlunsplit((dest_split.scheme, dest_split.netloc, dest_split.path, final_query, dest_split.fragment))

        dist_srv = getattr(self, "dist_server", None)
        if dist_srv is not None:
            dist_srv.redirect_events.append({
                "partner_key": partner,
                "source_tool": source_tool,
                "cta_slot": cta_slot,
                "subid": subid,
                "location": final_url,
            })

        self.send_response(302)
        self.send_header("Location", final_url)
        self.send_header("Cache-Control", "private, no-cache, no-store, must-revalidate")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.send_header("X-Edge-Partner", partner)
        self.send_header("X-Edge-Subid", subid)
        self.send_header("X-Edge-Telemetry", "recorded")
        self.end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept, Authorization, X-Pseofactory-Test")
        self.end_headers()

    def do_GET(self) -> None:
        if self._is_traversal_attempt():
            self.send_error(403, "Forbidden")
            return
        parsed_url = urllib.parse.urlsplit(self.path)
        clean_path = parsed_url.path
        if clean_path.startswith("/r/"):
            self._handle_affiliate_redirect(is_head=False)
            return
        if clean_path == "/api/lead-capture":
            qs = urllib.parse.parse_qs(parsed_url.query)
            prop_id = self._detect_property_id()
            dist_srv = getattr(self, "dist_server", None)
            if qs.get("checkout", [""])[0] == "1":
                lead_id = qs.get("lead_id", [f"lead_{prop_id}_direct"])[0]
                sku = qs.get("sku", ["prexvo_student_loan_audit_toolkit" if prop_id == "prexvo" else "ph_statutory_audit_toolkit"])[0]
                title = (
                    "Prexvo Student Loan Refinance & Forgiveness Audit Toolkit"
                    if prop_id == "prexvo"
                    else "ProfitHelm Statutory Tax & Capital Audit Workpapers"
                )
                price_usd = 19 if prop_id == "prexvo" else 29
                session_id = f"cs_edge_{lead_id}"
                chk_record = {
                    "ok": True,
                    "success": True,
                    "status": "checkout_session_ready",
                    "property_id": prop_id,
                    "lead_id": lead_id,
                    "offer_sku": sku,
                    "offer_title": title,
                    "offer_price_usd": price_usd,
                    "checkout_url": f"/api/lead-capture?checkout=1&lead_id={urllib.parse.quote(lead_id)}&sku={urllib.parse.quote(sku)}",
                    "checkout_session_id": session_id,
                    "checkout_mode": "edge_checkout_rail",
                }
                if dist_srv is not None:
                    dist_srv.checkout_sessions.append(chk_record)
                self._send_json(200, chk_record)
                return
            leads = list(dist_srv.captured_leads) if dist_srv is not None else []
            self._send_json(200, {
                "ok": True,
                "success": True,
                "property_id": prop_id,
                "count": len(leads),
                "leads": leads,
            })
            return
        if clean_path == "/api/telemetry":
            dist_srv = getattr(self, "dist_server", None)
            events = list(dist_srv.telemetry_events) if dist_srv is not None else []
            self._send_json(200, {"ok": True, "count": len(events), "events": events})
            return
        super().do_GET()

    def do_HEAD(self) -> None:
        if self._is_traversal_attempt():
            self.send_error(403, "Forbidden")
            return
        parsed_url = urllib.parse.urlsplit(self.path)
        if parsed_url.path.startswith("/r/"):
            self._handle_affiliate_redirect(is_head=True)
            return
        super().do_HEAD()

    def do_POST(self) -> None:
        if self._is_traversal_attempt():
            self.send_error(403, "Forbidden")
            return
        parsed_url = urllib.parse.urlsplit(self.path)
        clean_path = parsed_url.path
        content_len = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(content_len).decode("utf-8", errors="ignore") if content_len > 0 else "{}"
        try:
            body = json.loads(raw_body) if raw_body.strip() else {}
        except Exception:
            body = {}

        dist_srv = getattr(self, "dist_server", None)
        prop_id = self._detect_property_id()

        if clean_path == "/api/telemetry":
            sanitized = _sanitize_telemetry_dict(body)
            ev_id = f"evt_local_{int(time.time() * 1000)}"
            sanitized["event_id"] = ev_id
            sanitized.setdefault("property_id", prop_id)
            sanitized.setdefault("event", sanitized.get("event_type", "interaction"))
            sanitized.setdefault("event_type", sanitized.get("event", "interaction"))
            if dist_srv is not None:
                dist_srv.telemetry_events.append(sanitized)
            self._send_json(200, {
                "ok": True,
                "status": "RECORDED",
                "event_id": ev_id,
                "event": sanitized["event"],
                "property_id": prop_id,
            })
            return

        if clean_path == "/api/lead-capture":
            email = str(body.get("email") or "").strip().lower()
            if not email or "@" not in email:
                self._send_json(400, {"ok": False, "success": False, "error": "Please enter a valid email address."})
                return
            raw_slug = str(body.get("tool_slug") or body.get("source") or "calculator").strip().strip("/")
            if raw_slug.startswith("tools/"):
                raw_slug = raw_slug[6:]
            tool_slug = raw_slug.replace("/", "-") or "calculator"
            partner_key = str(body.get("partner_key") or ("splash_financial" if prop_id == "prexvo" else "ipx1031")).strip().lower()
            has_quote_fields = any(
                k in body for k in ("calculated_amount", "loan_balance", "state", "capital_band", "partner_sharing_consent")
            )
            lead_id = f"lead_{prop_id}_{int(time.time() * 1000)}"
            sku = "prexvo_student_loan_audit_toolkit" if prop_id == "prexvo" else "ph_statutory_audit_toolkit"
            offer_title = (
                "Prexvo Student Loan Refinance & Forgiveness Audit Toolkit"
                if prop_id == "prexvo"
                else "ProfitHelm Statutory Tax & Capital Audit Workpapers"
            )
            offer_price = 19 if prop_id == "prexvo" else 29
            checkout_url = f"/api/lead-capture?checkout=1&lead_id={urllib.parse.quote(lead_id)}&sku={urllib.parse.quote(sku)}"

            if not has_quote_fields:
                redirect_url = f"/r/{partner_key}?source={urllib.parse.quote(tool_slug)}&slot=playbook_subscription&lead_id={urllib.parse.quote(lead_id)}"
                record = {
                    "ok": True,
                    "success": True,
                    "status": "playbook_subscribed",
                    "lead_id": lead_id,
                    "property_id": prop_id,
                    "lead_type": "playbook_subscription",
                    "tool_slug": tool_slug,
                    "email": email,
                    "partner_key": partner_key,
                    "redirect_url": redirect_url,
                    "checkout_url": checkout_url,
                    "checkout_session_id": f"cs_edge_{lead_id}",
                    "checkout_mode": "edge_checkout_rail",
                    "offer_sku": sku,
                    "offer_title": offer_title,
                    "offer_price_usd": offer_price,
                }
                if dist_srv is not None:
                    dist_srv.captured_leads.append(record)
                self._send_json(200, record)
                return

            if body.get("partner_sharing_consent") is not True:
                self._send_json(400, {"ok": False, "success": False, "error": "Explicit TCPA partner_sharing_consent is required."})
                return
            state = str(body.get("state") or "CA").strip().upper()[:2]
            calc_amt = float(body.get("calculated_amount") or body.get("loan_balance") or 100000)
            cap_band = str(body.get("capital_band") or "100k_250k")
            subid = f"cpl_{tool_slug[:24]}_{state.lower()}_{int(calc_amt)}"
            redirect_url = (
                f"/r/{partner_key}?source={urllib.parse.quote(tool_slug)}&slot=partner_quote_intake"
                f"&subid={urllib.parse.quote(subid)}&state={state}&capital_band={urllib.parse.quote(cap_band)}"
                f"&amount={int(calc_amt)}&lead_id={urllib.parse.quote(lead_id)}"
            )
            record = {
                "ok": True,
                "success": True,
                "status": "captured",
                "lead_id": lead_id,
                "property_id": prop_id,
                "lead_type": "qualified_quote",
                "tool_slug": tool_slug,
                "email": email,
                "state": state,
                "capital_band": cap_band,
                "calculated_amount": calc_amt,
                "partner_sharing_consent": True,
                "partner_key": partner_key,
                "redirect_url": redirect_url,
                "checkout_url": checkout_url,
                "checkout_session_id": f"cs_edge_{lead_id}",
                "checkout_mode": "edge_checkout_rail",
                "offer_sku": sku,
                "offer_title": offer_title,
                "offer_price_usd": offer_price,
                "zeptomail_status": "synthetic_test_suppressed",
            }
            if dist_srv is not None:
                dist_srv.captured_leads.append(record)
            self._send_json(200, record)
            return

        self.send_error(404, "Endpoint not found")


class EphemeralDistServer:
    """
    Ephemeral loopback HTTP server serving a distribution directory.
    Binds strictly to ('127.0.0.1', 0) for OS kernel allocated dynamic port.
    Context manager (__enter__ / __exit__) ensures complete socket and thread cleanup.
    """

    def __init__(
        self,
        directory: Union[str, Path],
        host: str = "127.0.0.1",
        port: int = 0,
    ):
        self.directory = Path(directory).resolve()
        self.host = host
        self.port = port
        self.server: Optional[socketserver.TCPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.captured_leads: List[Dict[str, Any]] = []
        self.checkout_sessions: List[Dict[str, Any]] = []
        self.telemetry_events: List[Dict[str, Any]] = []
        self.redirect_events: List[Dict[str, Any]] = []

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start(self) -> int:
        """Starts the ephemeral HTTP server in a background daemon thread."""
        if self.server is not None:
            return self.port

        directory_str = str(self.directory)
        parent_self = self

        class BoundQuietHandler(QuietHTTPRequestHandler):
            server_root_dir = directory_str
            dist_server = parent_self

        class EphemeralTCPServer(socketserver.ThreadingTCPServer):
            allow_reuse_address = True
            daemon_threads = True

            def handle_error(self, request, client_address):
                pass

        self.server = EphemeralTCPServer((self.host, self.port), BoundQuietHandler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self.port

    def stop(self) -> None:
        """Stops the server and releases the bound socket port."""
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass
            self.server = None

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
            self.thread = None

    def __enter__(self) -> "EphemeralDistServer":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
