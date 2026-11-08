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


from pseofactory.edge import (
    build_canonical_partner_catalog,
    resolve_canonical_partner_redirect,
)


def _build_local_partner_destinations() -> Dict[str, str]:
    catalog = build_canonical_partner_catalog()
    return {
        k: str(v.get("effectiveUrl") or v.get("defaultUrl") or "")
        for k, v in catalog.items()
        if v.get("effectiveUrl") or v.get("defaultUrl")
    }


_LOCAL_PARTNER_DESTINATIONS: Dict[str, str] = _build_local_partner_destinations()


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
        dist_srv = getattr(self, "dist_server", None)
        explicit_prop = getattr(dist_srv, "property_id", None) if dist_srv is not None else None
        if explicit_prop:
            return str(explicit_prop).strip().lower()
        root_low = self.root_dir.lower()
        if "prexvo" in root_low:
            return "prexvo"
        if "gainhelm" in root_low:
            return "gainhelm"
        if "lienbond" in root_low:
            return "lienbond"
        return "profithelm"

    def _evaluate_redirects_file(self, clean_path: str, query_str: str = "") -> Optional[tuple]:
        redirects_file = Path(self.root_dir) / "_redirects"
        if not redirects_file.is_file():
            return None
        try:
            raw_lines = redirects_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            return None

        req_norm = clean_path if clean_path.startswith("/") else f"/{clean_path}"
        req_stripped = req_norm.rstrip("/") if req_norm != "/" else "/"

        for line in raw_lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            tokens = stripped.split()
            if len(tokens) < 2:
                continue
            src = tokens[0].strip()
            dst = tokens[1].strip()
            status_code = 301
            if len(tokens) >= 3:
                code_str = tokens[2].rstrip("!")
                if code_str.isdigit():
                    status_code = int(code_str)
            # Skip internal 200 SPA fallback rewrites for /r/* and /api/* handled natively
            if status_code == 200:
                continue

            matched_target: Optional[str] = None
            if src.endswith("/*"):
                prefix = src[:-1]  # e.g. "/vs/"
                prefix_no_slash = prefix.rstrip("/")
                if req_norm == prefix_no_slash or req_norm.startswith(prefix):
                    splat_val = req_norm[len(prefix):] if req_norm.startswith(prefix) else ""
                    matched_target = dst.replace(":splat", splat_val)
            else:
                src_stripped = src.rstrip("/") if src != "/" else "/"
                if req_norm == src or req_stripped == src_stripped:
                    matched_target = dst

            if matched_target:
                if query_str and "?" not in matched_target:
                    matched_target = f"{matched_target}?{query_str}"
                return (status_code, matched_target)
        return None

    def _handle_affiliate_redirect(self, is_head: bool = False) -> None:
        parsed_url = urllib.parse.urlsplit(self.path)
        partner = parsed_url.path[len("/r/"):].strip("/").lower()
        in_qs_pairs = urllib.parse.parse_qsl(parsed_url.query, keep_blank_values=False)
        flat_qs: Dict[str, str] = {}
        for k, v in in_qs_pairs:
            clean_k = re.sub(r"^(?:amp;)+", "", k, flags=re.IGNORECASE)
            if clean_k and v and clean_k not in flat_qs:
                flat_qs[clean_k] = v

        prop_id = self._detect_property_id()
        resolved = resolve_canonical_partner_redirect(
            partner,
            query_params=flat_qs,
            property_id=prop_id,
        )
        if not resolved:
            self.send_error(404, "Partner not found")
            return

        final_url = resolved["location"]
        source_tool = resolved["source_tool"]
        cta_slot = resolved["cta_slot"]
        subid = resolved["subid"]
        contract_tier = resolved["contract_tier"]
        native_dest = resolved["native_destination"]

        dist_srv = getattr(self, "dist_server", None)
        if dist_srv is not None:
            dist_srv.redirect_events.append({
                "partner_key": partner,
                "source_tool": source_tool,
                "cta_slot": cta_slot,
                "subid": subid,
                "contract_tier": contract_tier,
                "native_destination": native_dest,
                "location": final_url,
            })

        self.send_response(302)
        self.send_header("Location", final_url)
        self.send_header("Cache-Control", "private, no-cache, no-store, must-revalidate")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.send_header("X-Edge-Partner", partner)
        self.send_header("X-Edge-Subid", subid)
        self.send_header("X-Edge-Contract-Tier", contract_tier)
        self.send_header("X-Edge-Native-Destination", native_dest)
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
        if clean_path in ("/api/lead-capture", "/api/checkout", "/api/lead-fulfillment"):
            from pseofactory.partner_tracker import (
                resolve_lead_monetization_offer,
                synthesize_personalized_audit_workpaper,
            )
            qs = urllib.parse.parse_qs(parsed_url.query)
            if clean_path == "/api/checkout" and "checkout" not in qs:
                qs["checkout"] = ["1"]
            elif clean_path == "/api/lead-fulfillment" and "fulfill" not in qs:
                qs["fulfill"] = ["1"]
            prop_id = self._detect_property_id()
            dist_srv = getattr(self, "dist_server", None)
            if qs.get("playbook", [""])[0] == "1" or qs.get("fulfill", [""])[0] == "1" or qs.get("mode", [""])[0] in ("playbook", "fulfill"):
                is_fulfill = qs.get("fulfill", [""])[0] == "1" or qs.get("mode", [""])[0] == "fulfill"
                lead_id = qs.get("lead_id", [f"lead_{prop_id}_direct"])[0]
                session_id = qs.get("session_id", [""])[0].strip()
                settle_flag = qs.get("settle", [""])[0].strip().lower() in ("1", "true")
                if is_fulfill and clean_path == "/api/lead-fulfillment" and not session_id and not settle_flag:
                    self._send_json(402, {
                        "ok": False,
                        "success": False,
                        "settled": False,
                        "status": "payment_required",
                        "property_id": prop_id,
                        "lead_id": lead_id,
                        "error": "Verified paid Stripe Checkout session required to unlock unredacted statutory filing packet.",
                    })
                    return
                default_slug = (
                    "section-1031-calculator"
                    if prop_id == "profithelm"
                    else (
                        "soc-2-audit-cost-calculator"
                        if prop_id == "gainhelm"
                        else (
                            "contractor-license-bond-cost-calculator-by-credit-score"
                            if prop_id == "lienbond"
                            else "student-loan-refinance-break-even-calculator"
                        )
                    )
                )
                tool_slug = qs.get("tool_slug", qs.get("slug", [default_slug]))[0]
                stored_rec = None
                if dist_srv is not None:
                    for item in dist_srv.captured_leads:
                        if item.get("lead_id") == lead_id:
                            stored_rec = dict(item)
                            break
                eff_rec: Dict[str, Any] = stored_rec or {"lead_id": lead_id, "property_id": prop_id, "tool_slug": tool_slug}
                amt_raw = qs.get("amount", [""])[0]
                if amt_raw:
                    try:
                        eff_rec["calculated_amount"] = float(amt_raw)
                    except Exception:
                        pass
                state_raw = qs.get("state", [""])[0]
                if state_raw:
                    eff_rec["state"] = state_raw
                email_raw = qs.get("email", [""])[0]
                if email_raw:
                    eff_rec["email"] = email_raw
                inp_json_raw = qs.get("inputs_json", [""])[0]
                if inp_json_raw:
                    try:
                        parsed_inps = json.loads(inp_json_raw)
                        if isinstance(parsed_inps, dict):
                            eff_rec["scenario_inputs"] = {**(eff_rec.get("scenario_inputs") or {}), **parsed_inps}
                    except Exception:
                        pass
                out_json_raw = qs.get("outputs_json", [""])[0]
                if out_json_raw:
                    try:
                        parsed_outs = json.loads(out_json_raw)
                        if isinstance(parsed_outs, dict):
                            eff_rec["scenario_outputs"] = {**(eff_rec.get("scenario_outputs") or {}), **parsed_outs}
                    except Exception:
                        pass
                wp = synthesize_personalized_audit_workpaper(
                    property_id=prop_id,
                    tool_slug=tool_slug,
                    lead_record=eff_rec,
                    mode="paid_toolkit" if is_fulfill else "free_playbook",
                )
                fmt = qs.get("format", ["json"])[0].lower()
                if fmt == "csv":
                    payload = wp["csv_content"].encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/csv; charset=utf-8")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                if fmt == "html":
                    payload = wp["html_report"].encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                if fmt == "datapack":
                    dp_obj = wp.get("statutory_data_pack") or {}
                    payload = json.dumps(dp_obj, indent=2).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header(
                        "Content-Disposition",
                        f'attachment; filename="datapack_{tool_slug}_{lead_id}.json"',
                    )
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                self._send_json(200, {
                    "ok": True,
                    "success": True,
                    "status": "toolkit_fulfilled" if is_fulfill else "playbook_ready",
                    **wp,
                })
                return
            if qs.get("checkout", [""])[0] == "1" or qs.get("mode", [""])[0] == "checkout":
                lead_id = qs.get("lead_id", [f"lead_{prop_id}_direct"])[0]
                default_slug = (
                    "section-1031-calculator"
                    if prop_id == "profithelm"
                    else ("soc-2-audit-cost-calculator" if prop_id == "gainhelm" else "student-loan-refinance-break-even-calculator")
                )
                tool_slug = qs.get("tool_slug", qs.get("slug", [default_slug]))[0]
                sku_param = qs.get("sku", qs.get("offer_sku", [""]))[0] or None
                offer = resolve_lead_monetization_offer(prop_id, tool_slug, lead_id=lead_id, sku=sku_param)
                eff_rec_chk: Dict[str, Any] = {"lead_id": lead_id, "property_id": prop_id, "tool_slug": tool_slug}
                if sku_param:
                    eff_rec_chk["offer_sku"] = sku_param
                amt_raw = qs.get("amount", [""])[0]
                if amt_raw:
                    try:
                        eff_rec_chk["calculated_amount"] = float(amt_raw)
                    except Exception:
                        pass
                inp_json_raw = qs.get("inputs_json", [""])[0]
                if inp_json_raw:
                    try:
                        parsed_inps = json.loads(inp_json_raw)
                        if isinstance(parsed_inps, dict):
                            eff_rec_chk["scenario_inputs"] = parsed_inps
                    except Exception:
                        pass
                wp_chk = synthesize_personalized_audit_workpaper(
                    property_id=prop_id,
                    tool_slug=tool_slug,
                    lead_record=eff_rec_chk,
                    mode="paid_toolkit",
                )
                dp_url = offer.get("datapack_url") or (str(offer.get("fulfillment_url") or "") + "&format=datapack")
                chk_record = {
                    "ok": True,
                    "success": True,
                    "status": "checkout_session_ready",
                    "property_id": prop_id,
                    "lead_id": lead_id,
                    "workpaper_id": wp_chk["workpaper_id"],
                    "tool_slug": tool_slug,
                    "offer_sku": offer["offer_sku"],
                    "offer_title": offer["offer_title"],
                    "offer_price_usd": offer["offer_price_usd"],
                    "statutory_authority": offer["statutory_authority"],
                    "deliverables": offer["deliverables"],
                    "calculated_amount": wp_chk["calculated_amount"],
                    "capital_band": wp_chk["capital_band"],
                    "custom_parameter_ledger": wp_chk["custom_parameter_ledger"],
                    "reconciliation_schedule": wp_chk.get("reconciliation_schedule") or [],
                    "statutory_data_pack": wp_chk.get("statutory_data_pack") or {},
                    "settlement_attribution": wp_chk.get("settlement_attribution") or {},
                    "statutory_trend_series_count": len(wp_chk.get("statutory_trend_timeseries") or []),
                    "checkout_url": offer["checkout_url"],
                    "playbook_url": offer["playbook_url"],
                    "fulfillment_url": offer["fulfillment_url"],
                    "csv_fulfillment_url": offer["csv_fulfillment_url"],
                    "datapack_url": dp_url,
                    "checkout_session_id": offer["checkout_session_id"],
                    "checkout_mode": "edge_checkout_rail",
                    "stripe_account_id": "acct_1T6fSTIq0ckFsf5j",
                    "stripe_merchant_email": f"arif.coskun@{prop_id}.com",
                }
                if dist_srv is not None:
                    dist_srv.checkout_sessions.append(chk_record)
                fmt_param = qs.get("format", [""])[0].strip().lower()
                redirect_param = qs.get("redirect", [""])[0].strip().lower()
                accept_hdr = str(self.headers.get("Accept") or "").lower()
                if fmt_param != "json" and (redirect_param in ("1", "true") or "text/html" in accept_hdr):
                    redir_loc = str(
                        offer.get("checkout_url")
                        or offer.get("success_url")
                        or f"/tools/{tool_slug}/?checkout_status=ready"
                    )
                    self.send_response(302)
                    self.send_header("Location", redir_loc)
                    self.send_header("Cache-Control", "private, no-cache, no-store, must-revalidate")
                    self.send_header("X-Edge-Checkout-Mode", "edge_checkout_rail")
                    self.send_header("X-Edge-Offer-Sku", str(offer["offer_sku"]))
                    self.end_headers()
                    return
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
        redirect_rule = self._evaluate_redirects_file(clean_path, parsed_url.query)
        if redirect_rule is not None:
            r_status, r_location = redirect_rule
            self.send_response(r_status)
            self.send_header("Location", r_location)
            self.send_header("Cache-Control", "private, no-cache, no-store, must-revalidate")
            self.end_headers()
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
        redirect_rule = self._evaluate_redirects_file(parsed_url.path, parsed_url.query)
        if redirect_rule is not None:
            r_status, r_location = redirect_rule
            self.send_response(r_status)
            self.send_header("Location", r_location)
            self.send_header("Cache-Control", "private, no-cache, no-store, must-revalidate")
            self.end_headers()
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
            from pseofactory.partner_tracker import (
                resolve_lead_monetization_offer,
                synthesize_personalized_audit_workpaper,
            )
            email = str(body.get("email") or "").strip().lower()
            if not email or "@" not in email:
                self._send_json(400, {"ok": False, "success": False, "error": "Please enter a valid email address."})
                return
            raw_slug = str(body.get("tool_slug") or body.get("source") or "calculator").strip().strip("/")
            if raw_slug.startswith("tools/"):
                raw_slug = raw_slug[6:]
            tool_slug = raw_slug.replace("/", "-") or "calculator"
            is_synth = bool(
                body.get("synthetic_test")
                or str(self.headers.get("X-Pseofactory-Test") or "").strip().lower() in ("1", "true")
                or email.endswith("@synthetic.pseofactory.test")
            )
            intent_val = str(body.get("intent") or body.get("lead_type") or "").strip().lower()
            if intent_val == "partner_registration":
                firm_name = str(body.get("firm_name") or body.get("company_name") or "").strip() or (email.split("@")[1] if "@" in email else "Advisory Partner Firm")
                p_state = str(body.get("state") or "CA").strip().upper()[:2] or "CA"
                p_lead_id = str(body.get("lead_id") or f"lead_{prop_id}_partner_{int(time.time() * 1000)}")
                slot_sku = {
                    "prexvo": "px_verified_partner_slot",
                    "gainhelm": "gh_verified_partner_slot",
                    "lienbond": "lb_verified_partner_slot",
                }.get(prop_id, "ph_verified_partner_slot")
                p_checkout_url = (
                    f"/api/lead-capture?checkout=1&lead_id={urllib.parse.quote(p_lead_id)}"
                    f"&sku={slot_sku}&tool_slug={urllib.parse.quote(tool_slug)}&redirect=1"
                )
                p_rec = {
                    "ok": True,
                    "success": True,
                    "status": "partner_registered",
                    "lead_id": p_lead_id,
                    "property_id": prop_id,
                    "lead_type": "partner_registration",
                    "intent": "partner_registration",
                    "lifecycle_stage": "partner_registered",
                    "tool_slug": tool_slug,
                    "email": email,
                    "firm_name": firm_name,
                    "state": p_state,
                    "offer_sku": slot_sku,
                    "offer_title": "Verified Calculator Partner Slot",
                    "offer_price_usd": 299,
                    "checkout_url": p_checkout_url,
                    "synthetic_test": is_synth,
                    "persisted": not is_synth,
                    "zeptomail_status": "synthetic_test_suppressed",
                    "fulfillment_status": "synthetic_verified",
                }
                if dist_srv is not None:
                    dist_srv.captured_leads.append(p_rec)
                self._send_json(200, p_rec)
                return

            partner_key = str(
                body.get("partner_key")
                or (
                    "splash_financial"
                    if prop_id == "prexvo"
                    else ("vanta_security" if prop_id == "gainhelm" else ("simply_business" if prop_id == "lienbond" else "ipx1031"))
                )
            ).strip().lower()
            has_quote_fields = any(
                k in body for k in ("calculated_amount", "loan_balance", "state", "capital_band", "partner_sharing_consent")
            )
            lead_id = f"lead_{prop_id}_{int(time.time() * 1000)}"
            offer = resolve_lead_monetization_offer(prop_id, tool_slug, lead_id=lead_id)
            bp_state = body.get("blueprint_state") if isinstance(body.get("blueprint_state"), dict) else {}
            scen_inputs = body.get("scenario_inputs") if isinstance(body.get("scenario_inputs"), dict) else (
                bp_state.get("inputs") if isinstance(bp_state.get("inputs"), dict) else {}
            )
            scen_outputs = body.get("scenario_outputs") if isinstance(body.get("scenario_outputs"), dict) else (
                bp_state.get("outputs") if isinstance(bp_state.get("outputs"), dict) else {}
            )

            if not has_quote_fields:
                scen_amt = float(body.get("scenario_amount") or bp_state.get("calculated_amount") or 0.0)
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
                    "calculated_amount": scen_amt,
                    "partner_key": partner_key,
                    "redirect_url": redirect_url,
                    "checkout_url": offer["checkout_url"],
                    "playbook_url": offer["playbook_url"],
                    "playbook_csv_url": offer["playbook_csv_url"],
                    "playbook_datapack_url": offer["playbook_datapack_url"],
                    "fulfillment_url": offer["fulfillment_url"],
                    "csv_fulfillment_url": offer["csv_fulfillment_url"],
                    "datapack_url": offer["datapack_url"],
                    "checkout_session_id": offer["checkout_session_id"],
                    "checkout_mode": "edge_checkout_rail",
                    "offer_sku": offer["offer_sku"],
                    "offer_title": offer["offer_title"],
                    "offer_price_usd": offer["offer_price_usd"],
                    "deliverables": offer["deliverables"],
                    "scenario_inputs": scen_inputs,
                    "scenario_outputs": scen_outputs,
                    "blueprint_state": bp_state,
                    "synthetic_test": is_synth,
                    "persisted": not is_synth,
                    "zeptomail_status": "synthetic_test_suppressed",
                    "fulfillment_status": "synthetic_verified",
                }
                wp = synthesize_personalized_audit_workpaper(prop_id, tool_slug, lead_record=record, mode="free_playbook")
                record["reconciliation_schedule"] = wp["reconciliation_schedule"]
                record["sensitivity_matrix"] = wp["sensitivity_matrix"]
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
                "checkout_url": offer["checkout_url"],
                "playbook_url": offer["playbook_url"],
                "playbook_csv_url": offer["playbook_csv_url"],
                "playbook_datapack_url": offer["playbook_datapack_url"],
                "fulfillment_url": offer["fulfillment_url"],
                "csv_fulfillment_url": offer["csv_fulfillment_url"],
                "datapack_url": offer["datapack_url"],
                "checkout_session_id": offer["checkout_session_id"],
                "checkout_mode": "edge_checkout_rail",
                "offer_sku": offer["offer_sku"],
                "offer_title": offer["offer_title"],
                "offer_price_usd": offer["offer_price_usd"],
                "deliverables": offer["deliverables"],
                "scenario_inputs": scen_inputs,
                "scenario_outputs": scen_outputs,
                "blueprint_state": bp_state,
                "synthetic_test": is_synth,
                "persisted": not is_synth,
                "zeptomail_status": "synthetic_test_suppressed",
                "fulfillment_status": "synthetic_verified",
            }
            wp = synthesize_personalized_audit_workpaper(prop_id, tool_slug, lead_record=record, mode="paid_toolkit")
            record["reconciliation_schedule"] = wp["reconciliation_schedule"]
            record["sensitivity_matrix"] = wp["sensitivity_matrix"]
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
        property_id: Optional[str] = None,
    ):
        self.directory = Path(directory).resolve()
        self.host = host
        self.port = port
        self.property_id = property_id
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
