"""
Ephemeral loopback HTTP distribution server for pseofactory.
Binds to 127.0.0.1:0 for kernel-allocated dynamic ports, preventing port collisions.
Enforces strict path confinement to eliminate directory traversal escapes.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

import hashlib
import hmac
import html as html_lib
import http.server
import json
import os
from pathlib import Path
import re
import socketserver
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import urllib.parse
import uuid


from pseofactory.edge import (
    build_canonical_partner_catalog,
    resolve_canonical_partner_redirect,
)

_PAID_WORKPAPER_FIELDS: Tuple[str, ...] = (
    "csv_content",
    "period_schedule",
    "sensitivity_matrix",
    "statutory_trend_timeseries",
    "statutory_execution_artifacts",
    "statutory_data_pack",
    "reconciliation_schedule",
)
_STRIPE_REPLAY_WINDOW_SECONDS: int = 300
_STRIPE_LIVE_SID_RE = re.compile(r"^cs_live_[A-Za-z0-9_]+$")
_STRIPE_V1_HEX_RE = re.compile(r"^[0-9a-fA-F]{64}$")


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


def _append_query_param(url: Optional[str], key: str, value: str) -> Optional[str]:
    """Appends or updates a query parameter on a URL string while preserving None/empty."""
    raw = str(url or "").strip()
    if not raw:
        return None
    parts = urllib.parse.urlsplit(raw)
    pairs = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True) if k != key]
    pairs.append((key, value))
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(pairs), parts.fragment))


def _build_preview_summary_rows(wp: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Returns at most 2 redacted preview summary rows from a workpaper reconciliation schedule."""
    rows = wp.get("reconciliation_schedule")
    if not isinstance(rows, list):
        return []
    out: List[Dict[str, Any]] = []
    for row in rows[:2]:
        if not isinstance(row, dict):
            continue
        out.append({
            "line_code": row.get("line_code", ""),
            "line_item": row.get("line_item", ""),
            "authority": row.get("authority", ""),
            "baseline_value": row.get("baseline_value", ""),
            "optimized_value": row.get("optimized_value", ""),
            "delta_impact": row.get("delta_impact", ""),
            "execution_status": "REDACTED_PREVIEW_ONLY",
        })
    return out


def _strip_paid_workpaper_fields(
    payload: Dict[str, Any],
    preview_rows: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Strips paid workpaper deliverables and attaches redacted preview summary metadata."""
    rows = preview_rows if preview_rows is not None else _build_preview_summary_rows(payload)
    for field_name in _PAID_WORKPAPER_FIELDS:
        payload.pop(field_name, None)
    payload["preview_mode"] = True
    payload["paid_unlock_required"] = True
    payload["preview_summary_rows"] = rows
    return payload


def _parse_stripe_signature_header(header_value: str) -> Optional[Tuple[str, int, List[str]]]:
    """Parses Stripe-Signature 't=<ts>,v1=<64hex>' header; returns (ts_str, ts_int, v1_list) or None."""
    raw = str(header_value or "").strip()
    if not raw:
        return None
    ts_str = ""
    v1_list: List[str] = []
    for part in raw.split(","):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k == "t" and v.isdigit():
            ts_str = v
        elif k == "v1" and _STRIPE_V1_HEX_RE.match(v):
            v1_list.append(v.lower())
    if not ts_str or not v1_list:
        return None
    ts_sec = int(ts_str)
    if ts_sec <= 0:
        return None
    return (ts_str, ts_sec, v1_list)


def _normalize_tool_slug(raw_slug: Any, default_slug: str = "general") -> str:
    """Normalizes a slug or /tools/<slug>/ path into a bare lowercase slug."""
    s = str(raw_slug or "").strip().strip("/").lower()
    if s.startswith("tools/"):
        s = s[6:].strip("/")
    elif s == "tools":
        s = ""
    return s or default_slug


class QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """
    HTTP request handler with suppressed logging, strict path confinement,
    and built-in local edge route emulation (/api/lead-capture, /api/checkout,
    /api/lead-fulfillment, /api/stripe-webhook, /api/telemetry, /r/<partner>).
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

    def copyfile(self, source, outputfile) -> None:
        """Sends static files <= 4 MiB in a single write burst so Chromium never paints partial streaming HTML."""
        try:
            pos = source.tell()
            source.seek(0, os.SEEK_END)
            size = source.tell() - pos
            source.seek(pos)
            if 0 < size <= 4 * 1024 * 1024:
                outputfile.write(source.read())
                return
        except Exception:
            pass
        super().copyfile(source, outputfile)

    def _send_json(self, status_code: int, payload: Dict[str, Any], extra_headers: Optional[Dict[str, str]] = None) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "private, no-cache, no-store, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept, Authorization, Stripe-Signature, X-Pseofactory-Test")
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
        for cand_dir in (Path(self.root_dir), Path(self.root_dir).parent):
            marker = cand_dir / ".pseofactory.json"
            if marker.is_file():
                try:
                    data = json.loads(marker.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        pid = str(data.get("property_id") or data.get("id") or "").strip().lower()
                        if pid:
                            return pid
                except Exception:
                    pass
        root_low = self.root_dir.lower()
        if "prexvo" in root_low:
            return "prexvo"
        if "gainhelm" in root_low:
            return "gainhelm"
        if "lienbond" in root_low:
            return "lienbond"
        return "profithelm"

    def _default_tool_slug(self, prop_id: str) -> str:
        legacy_defaults = {
            "profithelm": "section-1031-calculator",
            "gainhelm": "soc-2-audit-cost-calculator",
            "lienbond": "contractor-license-bond-cost-calculator-by-credit-score",
            "prexvo": "student-loan-refinance-break-even-calculator",
        }
        if prop_id in legacy_defaults:
            return legacy_defaults[prop_id]
        tools_dir = Path(self.root_dir) / "tools"
        if tools_dir.is_dir():
            for child in sorted(tools_dir.iterdir()):
                if child.is_dir() and child.name != "partners" and (child / "index.html").is_file():
                    return child.name.lower()
        return "general"

    def _server_origin(self) -> str:
        host_hdr = str(self.headers.get("Host") or "").strip()
        if host_hdr:
            return f"http://{host_hdr}"
        dist_srv = getattr(self, "dist_server", None)
        if dist_srv is not None:
            return dist_srv.base_url
        return ""

    def _get_parsed_redirects(self) -> List[tuple]:
        redirects_file = Path(self.root_dir) / "_redirects"
        try:
            st = redirects_file.stat()
            sig = (st.st_ino, st.st_mtime_ns, st.st_size)
        except OSError:
            return []

        dist_srv = getattr(self, "dist_server", None)
        if dist_srv is not None:
            cached = getattr(dist_srv, "_redirects_cache", None)
            if cached is not None and cached[0] == sig:
                return cached[1]

        try:
            raw_lines = redirects_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            return []

        parsed: List[tuple] = []
        for line in raw_lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("# [edge-middleware-redirect]"):
                stripped = stripped[len("# [edge-middleware-redirect]") :].strip()
            elif stripped.startswith("#"):
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
            parsed.append((src, dst, status_code))

        if dist_srv is not None:
            dist_srv._redirects_cache = (sig, parsed)
        return parsed

    def _evaluate_redirects_file(self, clean_path: str, query_str: str = "") -> Optional[tuple]:
        rules = self._get_parsed_redirects()
        if not rules:
            return None

        req_norm = clean_path if clean_path.startswith("/") else f"/{clean_path}"
        req_stripped = req_norm.rstrip("/") if req_norm != "/" else "/"

        for src, dst, status_code in rules:
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
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept, Authorization, Stripe-Signature, X-Pseofactory-Test")
        self.end_headers()

    def _send_bad_request_error(self, prop_id: str, tool_slug: str, exc: Exception) -> None:
        from pseofactory.affiliates import is_restricted_public_service_slug

        msg = str(exc)
        is_ymyl = bool(
            prop_id == "prexvo"
            and (
                is_restricted_public_service_slug(tool_slug, tool_slug)
                or "restricted public-service" in msg.lower()
            )
        )
        err_code = "restricted_ymyl_route" if is_ymyl else "invalid_or_cross_tenant_sku"
        self._send_json(
            400,
            {
                "ok": False,
                "success": False,
                "status": "error",
                "error": err_code,
                "message": msg,
                "property_id": prop_id,
            },
        )

    def _validate_offer_or_send_400(
        self,
        prop_id: str,
        tool_slug: str,
        lead_id: str,
        sku_param: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        from pseofactory.affiliates import is_restricted_public_service_slug
        from pseofactory.partner_tracker import resolve_lead_monetization_offer

        if prop_id == "prexvo" and is_restricted_public_service_slug(tool_slug, tool_slug):
            self._send_bad_request_error(
                prop_id,
                tool_slug,
                ValueError(
                    f"Restricted public-service asset '{tool_slug}' on Prexvo cannot attach commercial checkout offers."
                ),
            )
            return None
        try:
            return resolve_lead_monetization_offer(
                prop_id,
                tool_slug,
                lead_id=lead_id,
                sku=sku_param or None,
            )
        except ValueError as exc:
            self._send_bad_request_error(prop_id, tool_slug, exc)
            return None

    def _build_checkout_return_urls(
        self,
        offer: Dict[str, Any],
        tool_slug: str,
        lead_id: str,
    ) -> Tuple[str, str]:
        tier_kind = str(offer.get("tier_kind") or "full").strip().lower()
        sku = str(offer.get("offer_sku") or "")
        origin = self._server_origin()
        lead_q = urllib.parse.quote(lead_id)
        sku_q = urllib.parse.quote(sku)
        if tier_kind == "partner_slot" or tool_slug == "partners" or sku.endswith("_verified_partner_slot"):
            return (
                f"{origin}/partners/?checkout_status=success&checkout_fulfilled=1&lead_id={lead_q}&sku={sku_q}&tier=partner_slot&session_id={{CHECKOUT_SESSION_ID}}",
                f"{origin}/partners/?checkout_status=cancelled&lead_id={lead_q}&sku={sku_q}&tier=partner_slot",
            )
        raw_path = urllib.parse.urlsplit(str(offer.get("success_url") or "")).path
        if not raw_path:
            raw_path = "/" if tool_slug in ("", "index", "home", "homepage", "general") or tool_slug.endswith("-hub") else f"/tools/{tool_slug}/"
        return (
            f"{origin}{raw_path}?checkout_status=success&checkout_fulfilled=1&lead_id={lead_q}&sku={sku_q}&session_id={{CHECKOUT_SESSION_ID}}",
            f"{origin}{raw_path}?checkout_status=cancelled&lead_id={lead_q}&sku={sku_q}",
        )

    def _handle_checkout_request(
        self,
        prop_id: str,
        qs: Dict[str, List[str]],
        body: Optional[Dict[str, Any]] = None,
    ) -> None:
        from pseofactory.partner_tracker import synthesize_personalized_audit_workpaper

        b = body if isinstance(body, dict) else {}
        dist_srv = getattr(self, "dist_server", None)
        lead_id = str(b.get("lead_id") or qs.get("lead_id", [f"lead_{prop_id}_direct"])[0] or f"lead_{prop_id}_direct").strip()
        default_slug = self._default_tool_slug(prop_id)
        raw_slug = b.get("tool_slug") or b.get("slug") or qs.get("tool_slug", qs.get("slug", [default_slug]))[0]
        tool_slug = _normalize_tool_slug(raw_slug, default_slug)
        sku_param = str(b.get("sku") or b.get("offer_sku") or qs.get("sku", qs.get("offer_sku", [""]))[0] or "").strip() or None

        offer = self._validate_offer_or_send_400(prop_id, tool_slug, lead_id, sku_param=sku_param)
        if offer is None:
            return

        eff_rec_chk: Dict[str, Any] = {"lead_id": lead_id, "property_id": prop_id, "tool_slug": tool_slug}
        if sku_param:
            eff_rec_chk["offer_sku"] = offer["offer_sku"]
        firm_name = str(b.get("firm_name") or b.get("company_name") or qs.get("firm_name", qs.get("company_name", [""]))[0] or "").strip()
        if firm_name:
            eff_rec_chk["firm_name"] = firm_name
        email_val = str(b.get("email") or qs.get("email", [""])[0] or "").strip().lower()
        if email_val:
            eff_rec_chk["email"] = email_val
        state_val = str(b.get("state") or qs.get("state", [""])[0] or "").strip()
        if state_val:
            eff_rec_chk["state"] = state_val
        amt_raw = b.get("calculated_amount") if b.get("calculated_amount") is not None else qs.get("amount", [""])[0]
        if amt_raw not in (None, ""):
            try:
                eff_rec_chk["calculated_amount"] = float(amt_raw)
            except Exception:
                pass
        inp_val = b.get("scenario_inputs") if isinstance(b.get("scenario_inputs"), dict) else None
        if inp_val is not None:
            eff_rec_chk["scenario_inputs"] = inp_val
        else:
            inp_json_raw = qs.get("inputs_json", [""])[0]
            if inp_json_raw:
                try:
                    parsed_inps = json.loads(inp_json_raw)
                    if isinstance(parsed_inps, dict):
                        eff_rec_chk["scenario_inputs"] = parsed_inps
                except Exception:
                    pass
        out_val = b.get("scenario_outputs") if isinstance(b.get("scenario_outputs"), dict) else None
        if out_val is not None:
            eff_rec_chk["scenario_outputs"] = out_val
        else:
            out_json_raw = qs.get("outputs_json", [""])[0]
            if out_json_raw:
                try:
                    parsed_outs = json.loads(out_json_raw)
                    if isinstance(parsed_outs, dict):
                        eff_rec_chk["scenario_outputs"] = parsed_outs
                except Exception:
                    pass

        try:
            wp_chk = synthesize_personalized_audit_workpaper(
                property_id=prop_id,
                tool_slug=tool_slug,
                lead_record=eff_rec_chk,
                mode="paid_toolkit",
            )
        except ValueError as exc:
            self._send_bad_request_error(prop_id, tool_slug, exc)
            return

        tier_kind = str(offer.get("tier_kind") or "full").strip().lower()
        offer_price_usd = float(
            offer.get("offer_price_usd")
            if offer.get("offer_price_usd") is not None
            else offer.get("price_usd", 0)
        )
        price_cents = int(round(offer_price_usd * 100))
        datapack_included = tier_kind == "full"
        checkout_session_id = f"cs_live_local_{uuid.uuid4().hex[:16]}"

        fulfillment_url = _append_query_param(str(offer.get("fulfillment_url") or ""), "session_id", checkout_session_id)
        csv_fulfillment_url = (
            None
            if tier_kind == "partner_slot"
            else _append_query_param(str(offer.get("csv_fulfillment_url") or ""), "session_id", checkout_session_id)
        )
        raw_dp_url = offer.get("datapack_url") or (str(offer.get("fulfillment_url") or "") + "&format=datapack")
        datapack_url = (
            _append_query_param(str(raw_dp_url), "session_id", checkout_session_id)
            if datapack_included
            else None
        )
        success_url, cancel_url = self._build_checkout_return_urls(offer, tool_slug, lead_id)

        stl_attr = dict(wp_chk.get("settlement_attribution") or {})
        stl_attr["fulfillment_url"] = fulfillment_url
        stl_attr["csv_fulfillment_url"] = csv_fulfillment_url
        stl_attr["datapack_url"] = datapack_url
        if not datapack_included:
            stl_attr["datapack_delivered"] = False

        chk_record: Dict[str, Any] = {
            "ok": True,
            "success": True,
            "status": "checkout_session_ready",
            "livemode": True,
            "property_id": prop_id,
            "lead_id": lead_id,
            "workpaper_id": wp_chk["workpaper_id"],
            "tool_slug": tool_slug,
            "tier_kind": tier_kind,
            "datapack_included": datapack_included,
            "offer_sku": offer["offer_sku"],
            "offer_title": offer["offer_title"],
            "offer_price_usd": offer_price_usd,
            "price_cents": price_cents,
            "statutory_authority": offer["statutory_authority"],
            "deliverables": offer["deliverables"],
            "calculated_amount": wp_chk["calculated_amount"],
            "capital_band": wp_chk["capital_band"],
            "custom_parameter_ledger": wp_chk["custom_parameter_ledger"],
            "settlement_attribution": stl_attr,
            "statutory_trend_series_count": len(wp_chk.get("statutory_trend_timeseries") or []),
            "checkout_url": offer["checkout_url"],
            "playbook_url": offer["playbook_url"],
            "fulfillment_url": fulfillment_url,
            "csv_fulfillment_url": csv_fulfillment_url,
            "datapack_url": datapack_url,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "checkout_session_id": checkout_session_id,
            "checkout_mode": "edge_checkout_rail",
            "stripe_account_id": "acct_1T6fSTIq0ckFsf5j",
            "stripe_merchant_email": f"arif.coskun@{prop_id}.com",
        }
        if dist_srv is not None:
            dist_srv.checkout_sessions.append(chk_record)
            dist_srv.paid_sessions[checkout_session_id] = {
                "session_id": checkout_session_id,
                "property_id": prop_id,
                "lead_id": lead_id,
                "sku": offer["offer_sku"],
                "offer_sku": offer["offer_sku"],
                "tier_kind": tier_kind,
                "tool_slug": tool_slug,
                "amount_total_cents": price_cents,
                "payment_status": "paid",
                "livemode": True,
                "firm_name": firm_name,
                "email": email_val,
                "calculated_amount": eff_rec_chk.get("calculated_amount"),
                "state": state_val,
                "scenario_inputs": eff_rec_chk.get("scenario_inputs") or {},
                "scenario_outputs": eff_rec_chk.get("scenario_outputs") or {},
                "source": "local_ephemeral_checkout",
            }
        if body is None:
            fmt_param = qs.get("format", [""])[0].strip().lower()
            redirect_param = qs.get("redirect", [""])[0].strip().lower()
            accept_hdr = str(self.headers.get("Accept") or "").lower()
            if fmt_param != "json" and (redirect_param in ("1", "true") or "text/html" in accept_hdr):
                redir_loc = str(
                    offer.get("checkout_url")
                    or success_url
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

    def _apply_fulfillment_session_links(
        self,
        wp: Dict[str, Any],
        paid_tier: str,
        session_id: str,
        firm_name: str = "",
    ) -> None:
        orig_ff = str(wp.get("fulfillment_url") or "")
        orig_csv = str(wp.get("csv_fulfillment_url") or "")
        orig_dp = str(wp.get("datapack_url") or "")

        sess_ff = _append_query_param(orig_ff, "session_id", session_id)
        sess_csv = None if paid_tier == "partner_slot" else _append_query_param(orig_csv, "session_id", session_id)
        sess_dp = _append_query_param(orig_dp, "session_id", session_id) if paid_tier == "full" else None

        wp["fulfillment_url"] = sess_ff
        wp["csv_fulfillment_url"] = sess_csv
        wp["datapack_url"] = sess_dp
        wp["preview_mode"] = False
        wp["paid_unlock_required"] = False
        wp["tier_kind"] = paid_tier
        wp["datapack_included"] = (paid_tier == "full")
        if firm_name:
            wp["firm_name"] = firm_name

        stl = wp.get("settlement_attribution")
        if isinstance(stl, dict):
            stl["fulfillment_url"] = sess_ff
            stl["csv_fulfillment_url"] = sess_csv
            stl["datapack_url"] = sess_dp
            if paid_tier != "full":
                stl["datapack_delivered"] = False
            if firm_name:
                stl["firm_name"] = firm_name

        html_out = str(wp.get("html_report") or "")
        if orig_csv and sess_csv:
            html_out = html_out.replace(
                html_lib.escape(orig_csv, quote=True),
                html_lib.escape(sess_csv, quote=True),
            )
        elif paid_tier == "partner_slot":
            html_out = re.sub(r"<a[^>]*>Download CSV Schedule</a>", "", html_out)

        if orig_dp and sess_dp:
            html_out = html_out.replace(
                html_lib.escape(orig_dp, quote=True),
                html_lib.escape(sess_dp, quote=True),
            )
        elif paid_tier in ("quick", "partner_slot"):
            html_out = re.sub(r"<a[^>]*>Download Statutory Data Pack \(JSON\)</a>", "", html_out)

        if firm_name and html_lib.escape(firm_name, quote=True) not in html_out and firm_name not in html_out:
            safe_firm = html_lib.escape(firm_name, quote=True)
            html_out = html_out.replace("</h1>", f"</h1><p><strong>Verified Partner Firm:</strong> {safe_firm}</p>", 1)

        if "session_id=" not in html_out and sess_ff:
            ff_html_href = _append_query_param(sess_ff, "format", "html") or sess_ff
            safe_href = html_lib.escape(ff_html_href, quote=True)
            receipt_link = f"<a href='{safe_href}' style='background:#0f766e;color:#fff;text-decoration:none;padding:8px 14px;border-radius:6px;font-size:12px;font-weight:700;'>Verified Fulfillment Receipt (HTML)</a>"
            if "Print / Save PDF</button>" in html_out:
                html_out = html_out.replace("Print / Save PDF</button>", f"Print / Save PDF</button>{receipt_link}", 1)
            else:
                html_out = html_out.replace("</body>", f"<div>{receipt_link}</div></body>", 1)

        wp["html_report"] = html_out

        if paid_tier == "quick":
            for k in ("statutory_data_pack", "statutory_execution_artifacts"):
                wp.pop(k, None)
        elif paid_tier == "partner_slot":
            for k in (
                "statutory_data_pack",
                "statutory_execution_artifacts",
                "csv_content",
                "reconciliation_schedule",
                "sensitivity_matrix",
                "period_schedule",
                "statutory_trend_timeseries",
            ):
                wp.pop(k, None)

    def _handle_playbook_or_fulfill(
        self,
        prop_id: str,
        qs: Dict[str, List[str]],
        body: Optional[Dict[str, Any]] = None,
    ) -> None:
        from pseofactory.partner_tracker import synthesize_personalized_audit_workpaper

        b = body if isinstance(body, dict) else {}
        dist_srv = getattr(self, "dist_server", None)
        mode_val = str(b.get("mode") or qs.get("mode", [""])[0] or "").strip().lower()
        is_fulfill = (
            qs.get("fulfill", [""])[0] == "1"
            or b.get("fulfill") is True
            or mode_val == "fulfill"
        )
        lead_id = str(b.get("lead_id") or qs.get("lead_id", [f"lead_{prop_id}_direct"])[0] or f"lead_{prop_id}_direct").strip()
        session_id = str(b.get("session_id") or qs.get("session_id", [""])[0] or "").strip()
        default_slug = self._default_tool_slug(prop_id)
        raw_slug = b.get("tool_slug") or b.get("slug") or qs.get("tool_slug", qs.get("slug", [default_slug]))[0]
        tool_slug = _normalize_tool_slug(raw_slug, default_slug)
        sku_param = str(b.get("sku") or b.get("offer_sku") or qs.get("sku", qs.get("offer_sku", [""]))[0] or "").strip() or None
        fmt = str(b.get("format") or qs.get("format", ["json"])[0] or "json").strip().lower()

        req_offer = self._validate_offer_or_send_400(prop_id, tool_slug, lead_id, sku_param=sku_param)
        if req_offer is None:
            return

        if not is_fulfill and fmt in ("csv", "datapack", "datapack_json"):
            self._send_json(
                402,
                {
                    "ok": False,
                    "success": False,
                    "status": "payment_required",
                    "settled": False,
                    "property_id": prop_id,
                    "lead_id": lead_id,
                    "error": "paid_export_requires_checkout",
                },
            )
            return

        paid_sess: Optional[Dict[str, Any]] = None
        paid_tier = str(req_offer.get("tier_kind") or "full").strip().lower()
        paid_offer = req_offer
        if is_fulfill:
            if dist_srv is not None and session_id:
                cand_sess = dist_srv.paid_sessions.get(session_id)
                if isinstance(cand_sess, dict):
                    sess_prop = str(cand_sess.get("property_id") or "").strip().lower()
                    if not sess_prop or sess_prop == prop_id:
                        paid_sess = cand_sess
            if paid_sess is None:
                self._send_json(
                    402,
                    {
                        "ok": False,
                        "success": False,
                        "status": "payment_required",
                        "settled": False,
                        "property_id": prop_id,
                        "lead_id": lead_id,
                        "error": "verified_paid_session_required",
                    },
                )
                return

            paid_sku = str(paid_sess.get("sku") or paid_sess.get("offer_sku") or req_offer["offer_sku"]).strip().lower()
            if paid_sku and paid_sku != req_offer["offer_sku"]:
                paid_offer = self._validate_offer_or_send_400(prop_id, tool_slug, lead_id, sku_param=paid_sku)
                if paid_offer is None:
                    return
            paid_tier = str(paid_sess.get("tier_kind") or paid_offer.get("tier_kind") or "full").strip().lower()

            if paid_tier == "quick":
                if fmt in ("datapack", "datapack_json"):
                    self._send_json(
                        402,
                        {
                            "ok": False,
                            "success": False,
                            "status": "payment_required",
                            "settled": False,
                            "property_id": prop_id,
                            "lead_id": lead_id,
                            "error": "datapack_requires_full_tier_checkout",
                        },
                    )
                    return
                if sku_param and str(req_offer.get("tier_kind") or "").lower() != "quick":
                    self._send_json(
                        402,
                        {
                            "ok": False,
                            "success": False,
                            "status": "payment_required",
                            "settled": False,
                            "property_id": prop_id,
                            "lead_id": lead_id,
                            "error": "tier_escalation_requires_full_checkout",
                        },
                    )
                    return
            elif paid_tier == "partner_slot" and fmt in ("csv", "datapack", "datapack_json"):
                self._send_json(
                    402,
                    {
                        "ok": False,
                        "success": False,
                        "status": "payment_required",
                        "settled": False,
                        "property_id": prop_id,
                        "lead_id": lead_id,
                        "error": "partner_slot_receipt_html_only",
                    },
                )
                return

        stored_rec = None
        if dist_srv is not None:
            for item in dist_srv.captured_leads:
                if item.get("lead_id") == lead_id:
                    stored_rec = dict(item)
                    break
        eff_rec: Dict[str, Any] = stored_rec or {"lead_id": lead_id, "property_id": prop_id, "tool_slug": tool_slug}
        if is_fulfill and paid_sess is not None:
            eff_rec["offer_sku"] = paid_offer["offer_sku"]
            eff_rec["stripe_checkout_session_id"] = session_id
            eff_rec["stripe_payment_verified"] = True
            eff_rec["stripe_payment_status"] = "paid"
            eff_rec["settled"] = True
            for k in ("firm_name", "email", "state", "calculated_amount"):
                if not eff_rec.get(k) and paid_sess.get(k):
                    eff_rec[k] = paid_sess[k]
            if not eff_rec.get("scenario_inputs") and isinstance(paid_sess.get("scenario_inputs"), dict):
                eff_rec["scenario_inputs"] = dict(paid_sess["scenario_inputs"])
            if not eff_rec.get("scenario_outputs") and isinstance(paid_sess.get("scenario_outputs"), dict):
                eff_rec["scenario_outputs"] = dict(paid_sess["scenario_outputs"])
        elif sku_param:
            eff_rec["offer_sku"] = req_offer["offer_sku"]

        amt_raw = b.get("calculated_amount") if b.get("calculated_amount") is not None else qs.get("amount", [""])[0]
        if amt_raw not in (None, ""):
            try:
                eff_rec["calculated_amount"] = float(amt_raw)
            except Exception:
                pass
        state_raw = str(b.get("state") or qs.get("state", [""])[0] or "").strip()
        if state_raw:
            eff_rec["state"] = state_raw
        email_raw = str(b.get("email") or qs.get("email", [""])[0] or "").strip()
        if email_raw:
            eff_rec["email"] = email_raw
        firm_raw = str(b.get("firm_name") or b.get("company_name") or qs.get("firm_name", qs.get("company_name", [""]))[0] or "").strip()
        if firm_raw:
            eff_rec["firm_name"] = firm_raw
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

        try:
            wp = synthesize_personalized_audit_workpaper(
                property_id=prop_id,
                tool_slug=tool_slug,
                lead_record=eff_rec,
                mode="paid_toolkit" if is_fulfill else "free_playbook",
            )
        except ValueError as exc:
            self._send_bad_request_error(prop_id, tool_slug, exc)
            return

        if is_fulfill:
            self._apply_fulfillment_session_links(
                wp,
                paid_tier=paid_tier,
                session_id=session_id,
                firm_name=str(eff_rec.get("firm_name") or ""),
            )
            if fmt == "csv":
                payload = str(wp.get("csv_content") or "").encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            if fmt == "html":
                payload = str(wp.get("html_report") or "").encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            if fmt in ("datapack", "datapack_json"):
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
                "status": "toolkit_fulfilled",
                **wp,
            })
            return

        if fmt == "html":
            payload = str(wp.get("html_report") or "").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        pb_resp = {
            "ok": True,
            "success": True,
            "status": "playbook_ready",
            **wp,
        }
        _strip_paid_workpaper_fields(pb_resp)
        if str(req_offer.get("tier_kind") or "").lower() != "full":
            pb_resp["datapack_url"] = None
        if str(req_offer.get("tier_kind") or "").lower() == "partner_slot":
            pb_resp["csv_fulfillment_url"] = None
        self._send_json(200, pb_resp)

    def _handle_stripe_webhook_post(self, raw_body: str, prop_id: str) -> None:
        from pseofactory.partner_tracker import resolve_lead_monetization_offer

        dist_srv = getattr(self, "dist_server", None)
        sig_header = str(
            self.headers.get("Stripe-Signature")
            or self.headers.get("stripe-signature")
            or ""
        ).strip()
        parsed_sig = _parse_stripe_signature_header(sig_header)
        if parsed_sig is None:
            self._send_json(400, {"ok": False, "error": "invalid_stripe_signature_header"})
            return

        ts_str, ts_sec, v1_list = parsed_sig
        secret = str(getattr(dist_srv, "stripe_webhook_secret", "") or "").strip() if dist_srv is not None else ""
        if secret:
            now_sec = int(time.time())
            if abs(now_sec - ts_sec) > _STRIPE_REPLAY_WINDOW_SECONDS:
                self._send_json(400, {"ok": False, "error": "stripe_signature_timestamp_expired"})
                return
            signed_payload = f"{ts_str}.{raw_body}".encode("utf-8")
            expected_hex = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
            if not any(hmac.compare_digest(cand, expected_hex) for cand in v1_list):
                self._send_json(400, {"ok": False, "error": "stripe_signature_mismatch"})
                return

        try:
            event = json.loads(raw_body)
        except Exception:
            self._send_json(400, {"ok": False, "error": "invalid_json_payload"})
            return
        if not isinstance(event, dict):
            self._send_json(400, {"ok": False, "error": "invalid_json_payload"})
            return

        if event.get("type") != "checkout.session.completed":
            self._send_json(
                200,
                {
                    "ok": True,
                    "ignored": True,
                    "reason": "unhandled_event_type",
                    "event_type": event.get("type"),
                },
            )
            return

        data_obj = event.get("data") if isinstance(event.get("data"), dict) else {}
        session = data_obj.get("object") if isinstance(data_obj.get("object"), dict) else {}
        session_id = str(session.get("id") or "").strip()
        if (
            session.get("livemode") is not True
            or session.get("payment_status") != "paid"
            or not _STRIPE_LIVE_SID_RE.match(session_id)
        ):
            self._send_json(
                200,
                {
                    "ok": True,
                    "ignored": True,
                    "reason": "non_live_or_unpaid_session",
                    "session_id": session_id or None,
                },
            )
            return

        meta = session.get("metadata") if isinstance(session.get("metadata"), dict) else {}
        meta_prop = str(meta.get("property_id") or "").strip().lower()
        if meta_prop and meta_prop != prop_id:
            self._send_json(
                200,
                {
                    "ok": True,
                    "ignored": True,
                    "reason": "property_mismatch",
                    "expected_property": prop_id,
                    "received_property": meta_prop,
                },
            )
            return

        eff_prop = meta_prop or prop_id
        lead_id = str(session.get("client_reference_id") or meta.get("lead_id") or f"lead_{eff_prop}_{session_id}").strip()
        tool_slug = _normalize_tool_slug(meta.get("tool_slug"), self._default_tool_slug(eff_prop))
        meta_sku = str(meta.get("offer_sku") or meta.get("sku") or "").strip().lower()
        amount_cents = int(session.get("amount_total") or 0)
        tier_kind = "full"
        resolved_sku = meta_sku
        try:
            if meta_sku:
                off = resolve_lead_monetization_offer(eff_prop, tool_slug, lead_id=lead_id, sku=meta_sku)
                tier_kind = str(off.get("tier_kind") or "full").lower()
                resolved_sku = str(off.get("offer_sku") or meta_sku)
            else:
                from pseofactory.pricing import get_tenant_edge_pricing_catalog
                cat = get_tenant_edge_pricing_catalog(eff_prop)
                q_sku = str(cat["quick_sku"])
                p_sku = str(cat["partner_slot_sku"])
                f_sku = str(cat["default_full_sku"])
                q_cents = int(cat["offers"][q_sku]["price_cents"])
                p_cents = int(cat["offers"][p_sku]["price_cents"])
                if 0 < amount_cents <= q_cents:
                    tier_kind = "quick"
                    resolved_sku = q_sku
                elif amount_cents >= p_cents:
                    tier_kind = "partner_slot"
                    resolved_sku = p_sku
                else:
                    tier_kind = "full"
                    resolved_sku = f_sku
        except Exception:
            if resolved_sku.endswith("_verified_partner_slot") or "partner_slot" in resolved_sku:
                tier_kind = "partner_slot"
            elif "_instant_" in resolved_sku or "_quick_" in resolved_sku or resolved_sku.endswith("_worksheet_19"):
                tier_kind = "quick"

        cust_details = session.get("customer_details") if isinstance(session.get("customer_details"), dict) else {}
        customer_email = str(cust_details.get("email") or session.get("customer_email") or "").strip().lower()
        firm_name = str(meta.get("firm_name") or "").strip()

        already_fulfilled = False
        if dist_srv is not None:
            already_fulfilled = session_id in dist_srv.paid_sessions
            dist_srv.paid_sessions[session_id] = {
                "session_id": session_id,
                "property_id": eff_prop,
                "lead_id": lead_id,
                "sku": resolved_sku,
                "offer_sku": resolved_sku,
                "tier_kind": tier_kind,
                "tool_slug": tool_slug,
                "amount_total_cents": amount_cents,
                "payment_status": "paid",
                "livemode": True,
                "email": customer_email,
                "firm_name": firm_name,
                "source": "stripe_webhook_verified",
            }

        self._send_json(
            200,
            {
                "ok": True,
                "fulfilled": True,
                "already_fulfilled": already_fulfilled,
                "lead_id": lead_id,
                "session_id": session_id,
                "property_id": eff_prop,
                "settlement_status": "settled",
            },
        )

    def do_GET(self) -> None:
        if self._is_traversal_attempt():
            self.send_error(403, "Forbidden")
            return
        parsed_url = urllib.parse.urlsplit(self.path)
        clean_path = parsed_url.path
        if clean_path.startswith("/r/"):
            self._handle_affiliate_redirect(is_head=False)
            return
        if clean_path == "/api/stripe-webhook":
            self._send_json(
                405,
                {"ok": False, "error": "method_not_allowed"},
                extra_headers={"Allow": "POST, OPTIONS"},
            )
            return
        if clean_path in ("/api/lead-capture", "/api/checkout", "/api/lead-fulfillment"):
            qs = urllib.parse.parse_qs(parsed_url.query)
            if qs.get("config", [""])[0] == "1":
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "success": True,
                        "turnstile_enabled": False,
                        "turnstile_site_key": "",
                    },
                    extra_headers={"Cache-Control": "public, max-age=300"},
                )
                return
            if clean_path == "/api/checkout" and "checkout" not in qs:
                qs["checkout"] = ["1"]
            elif clean_path == "/api/lead-fulfillment" and "fulfill" not in qs:
                qs["fulfill"] = ["1"]
            prop_id = self._detect_property_id()
            dist_srv = getattr(self, "dist_server", None)
            if qs.get("playbook", [""])[0] == "1" or qs.get("fulfill", [""])[0] == "1" or qs.get("mode", [""])[0] in ("playbook", "fulfill"):
                self._handle_playbook_or_fulfill(prop_id, qs)
                return
            if qs.get("checkout", [""])[0] == "1" or qs.get("mode", [""])[0] == "checkout":
                self._handle_checkout_request(prop_id, qs)
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
        if clean_path in ("/css/style.css", "/static/css/style.css"):
            disk_css = Path(self.root_dir) / clean_path.lstrip("/")
            if not disk_css.is_file():
                from pseofactory.porcelain_shell import generate_porcelain_stylesheet
                css_bytes = generate_porcelain_stylesheet(self._detect_property_id()).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/css; charset=utf-8")
                self.send_header("Content-Length", str(len(css_bytes)))
                self.end_headers()
                self.wfile.write(css_bytes)
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
        qs = urllib.parse.parse_qs(parsed_url.query)
        content_len = int(self.headers.get("Content-Length", "0") or "0")
        raw_bytes = self.rfile.read(content_len) if content_len > 0 else b""
        raw_body = raw_bytes.decode("utf-8", errors="replace")

        dist_srv = getattr(self, "dist_server", None)
        prop_id = self._detect_property_id()

        if clean_path == "/api/stripe-webhook":
            self._handle_stripe_webhook_post(raw_body, prop_id)
            return

        try:
            body = json.loads(raw_body) if raw_body.strip() else {}
            if not isinstance(body, dict):
                body = {}
        except Exception:
            body = {}

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

        mode_val = str(body.get("mode") or qs.get("mode", [""])[0] or "").strip().lower()
        if clean_path == "/api/checkout" or (
            clean_path == "/api/lead-capture"
            and (qs.get("checkout", [""])[0] == "1" or body.get("checkout") is True or mode_val == "checkout")
        ):
            self._handle_checkout_request(prop_id, qs, body=body)
            return

        if clean_path == "/api/lead-fulfillment" or (
            clean_path == "/api/lead-capture"
            and (qs.get("fulfill", [""])[0] == "1" or body.get("fulfill") is True or mode_val == "fulfill")
        ):
            if "fulfill" not in qs and body.get("fulfill") is not True:
                qs["fulfill"] = ["1"]
            self._handle_playbook_or_fulfill(prop_id, qs, body=body)
            return

        if clean_path == "/api/lead-capture":
            from pseofactory.partner_tracker import synthesize_personalized_audit_workpaper

            email = str(body.get("email") or "").strip().lower()
            if not email or "@" not in email:
                self._send_json(400, {"ok": False, "success": False, "error": "Please enter a valid email address."})
                return
            raw_slug = str(body.get("tool_slug") or body.get("source") or "calculator").strip().strip("/")
            if raw_slug.lower() == "index.html":
                raw_slug = "homepage"
            elif raw_slug.startswith("tools/"):
                raw_slug = raw_slug[6:]
            tool_slug = raw_slug.replace("/", "-") or "calculator"
            is_synth = bool(
                body.get("synthetic_test")
                or str(self.headers.get("X-Pseofactory-Test") or "").strip().lower() in ("1", "true")
                or email.endswith("@synthetic.pseofactory.test")
            )
            intent_val = str(body.get("intent") or body.get("lead_type") or "").strip().lower()
            if intent_val == "partner_registration":
                from pseofactory.pricing import resolve_offer_pricing

                firm_name = str(body.get("firm_name") or body.get("company_name") or "").strip() or (email.split("@")[1] if "@" in email else "Advisory Partner Firm")
                p_state = str(body.get("state") or "CA").strip().upper()[:2] or "CA"
                p_lead_id = str(body.get("lead_id") or f"lead_{prop_id}_partner_{int(time.time() * 1000)}")
                slot_offer = resolve_offer_pricing(prop_id, tier_kind="partner_slot")
                slot_sku = str(slot_offer["sku"])
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
                    "offer_title": str(slot_offer.get("title") or "Verified Calculator Partner Slot"),
                    "offer_price_usd": slot_offer.get("price_usd", 299),
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
            post_sku = str(body.get("sku") or body.get("offer_sku") or "").strip() or None
            offer = self._validate_offer_or_send_400(prop_id, tool_slug, lead_id, sku_param=post_sku)
            if offer is None:
                return
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
                _strip_paid_workpaper_fields(record, preview_rows=_build_preview_summary_rows(wp))
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
            wp = synthesize_personalized_audit_workpaper(prop_id, tool_slug, lead_record=record, mode="free_playbook")
            _strip_paid_workpaper_fields(record, preview_rows=_build_preview_summary_rows(wp))
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
        stripe_webhook_secret: str = "",
    ):
        self.directory = Path(directory).resolve()
        self.host = host
        self.port = port
        self.property_id = property_id
        self.stripe_webhook_secret: str = str(stripe_webhook_secret or "")
        self.server: Optional[socketserver.TCPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.captured_leads: List[Dict[str, Any]] = []
        self.checkout_sessions: List[Dict[str, Any]] = []
        self.paid_sessions: Dict[str, Dict[str, Any]] = {}
        self.telemetry_events: List[Dict[str, Any]] = []
        self.redirect_events: List[Dict[str, Any]] = []

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start(self) -> int:
        """Starts the ephemeral HTTP server in a background daemon thread."""
        if self.server is not None:
            return self.port

        # Pre-warm lazy imports in the main thread before spawning handler threads
        # so concurrent requests do not contend on Python's import lock.
        try:
            from pseofactory.trends.db import TrendHistoryDB  # noqa: F401
            from pseofactory.partner_tracker import (  # noqa: F401
                resolve_lead_monetization_offer,
                synthesize_personalized_audit_workpaper,
            )
            from pseofactory.affiliates import is_restricted_public_service_slug  # noqa: F401
            from pseofactory.pricing import resolve_offer_pricing  # noqa: F401
        except Exception:
            pass

        directory_str = str(self.directory)
        parent_self = self

        class BoundQuietHandler(QuietHTTPRequestHandler):
            server_root_dir = directory_str
            dist_server = parent_self

        class EphemeralTCPServer(socketserver.ThreadingTCPServer):
            allow_reuse_address = True
            daemon_threads = True
            request_queue_size = 128

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
