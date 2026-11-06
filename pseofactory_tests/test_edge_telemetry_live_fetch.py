"""Regression: live edge telemetry fetch must survive large, chunked, paginated, slow responses."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from pseofactory.partner_tracker import PartnerTrackingEngine


def _events(n, start=0):
    return [
        {
            "event_id": f"evt_{start + i}",
            "event_type": "affiliate_click",
            "event": "affiliate_click",
            "partner_key": "vanta_security",
            "tool_slug": "iso-27001-certification-cost-calculator",
            "cta_slot": "partner_matrix_card",
            "subid": f"sub_{start + i}_" + "x" * 400,
            "timestamp": "2026-11-06T10:00:00.000Z",
        }
        for i in range(n)
    ]


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        time.sleep(0.3)
        if "cursor=page2" in self.path:
            body = {"ok": True, "events": _events(100, 100), "cursor": "", "list_complete": True}
        else:
            body = {"ok": True, "events": _events(100), "cursor": "page2", "list_complete": False}
        raw = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()  # no Content-Length, like the edge
        self.wfile.write(raw)


def test_live_fetch_handles_large_paginated_response(tmp_path, monkeypatch):
    import urllib.request

    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        real_urlopen = urllib.request.urlopen
        base = f"http://127.0.0.1:{srv.server_port}"

        def fake_urlopen(req, *a, **kw):
            url = req.full_url if hasattr(req, "full_url") else req
            local = base + url.split(".com", 1)[1]
            new = urllib.request.Request(local, headers=dict(getattr(req, "headers", {})))
            return real_urlopen(new, *a, **kw)

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        res = PartnerTrackingEngine().sync_edge_click_telemetry(fetch_live=True, ledger_dir=tmp_path)
    finally:
        srv.shutdown()
    for prop in ("profithelm", "prexvo", "gainhelm"):
        assert res[prop]["total_durable_events"] == 200, res[prop].get("fetch_error")
        assert not res[prop].get("fetch_error")
