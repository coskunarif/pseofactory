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


class _SlowPagedHandler(BaseHTTPRequestHandler):
    PAGES = 6

    def log_message(self, *a):
        pass

    def do_GET(self):
        time.sleep(0.5)
        n = 0
        if "cursor=p" in self.path:
            n = int(self.path.split("cursor=p")[1].split("&")[0])
        last = n >= self.PAGES - 1
        body = {
            "ok": True,
            "events": _events(10, n * 10),
            "cursor": "" if last else f"p{n + 1}",
            "list_complete": last,
        }
        raw = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(raw)


def test_live_fetch_respects_time_budget_and_resumes(tmp_path, monkeypatch):
    import urllib.request

    import pseofactory.partner_tracker as pt

    srv = HTTPServer(("127.0.0.1", 0), _SlowPagedHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        real_urlopen = urllib.request.urlopen
        base = f"http://127.0.0.1:{srv.server_port}"

        def fake_urlopen(req, *a, **kw):
            url = req.full_url
            new = urllib.request.Request(base + url.split(".com", 1)[1], headers=dict(req.headers))
            return real_urlopen(new, *a, **kw)

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        monkeypatch.setattr(pt, "TELEMETRY_FETCH_BUDGET_SECONDS", 1.2, raising=False)
        eng = PartnerTrackingEngine()
        first = eng.sync_edge_click_telemetry(fetch_live=True, ledger_dir=tmp_path)
        n1 = first["profithelm"]["total_durable_events"]
        assert 0 < n1 < 60, n1
        for _ in range(6):
            res = eng.sync_edge_click_telemetry(fetch_live=True, ledger_dir=tmp_path)
        assert res["profithelm"]["total_durable_events"] == 60
    finally:
        srv.shutdown()


def test_sync_and_evaluate_loads_engagement_and_excludes_external_governance(tmp_path):
    from pseofactory.action_bus import HumanActionBus
    from pseofactory.email_ingest import EmailIngestionEngine

    bus = HumanActionBus(bus_path=str(tmp_path / "bus.json"))
    bus.route_manual_requirement(
        property_id="profithelm",
        partner_key="shopify_partner_account",
        partner_name="Shopify Partner Governance",
        title="Shopify Governance Warning",
        description="App delisted warning.",
    )
    bus.route_manual_requirement(
        property_id="profithelm",
        partner_key="claude_startups",
        partner_name="Claude Startups Program",
        title="Claude Startups Program",
        description="Startup credits.",
    )
    email_eng = EmailIngestionEngine(
        cache_path=str(tmp_path / "email_cache.json"),
        state_path=str(tmp_path / "email_state.json"),
    )
    eng = PartnerTrackingEngine(email_engine=email_eng, action_bus=bus)
    dash = eng.sync_and_evaluate(force_mail_poll=False)
    ph = dash.profithelm

    # 1. External governance items must not dilute total_registered_partners or readiness score
    real_affiliate_count = sum(1 for p in ph.partners if p.registry_status != "external_governance")
    assert ph.total_registered_partners == real_affiliate_count
    assert ph.monetization_readiness_score == round((ph.active_partners_count / real_affiliate_count) * 100, 1)

    # 2. Default sync_and_evaluate must populate outbound_clicks from the durable engagement ledger
    total_live_clicks = sum(p.outbound_clicks for p in ph.partners if p.operational_status == "LIVE_ACTIVE")
    assert total_live_clicks > 0, "Expected default sync_and_evaluate to load durable edge click telemetry"
