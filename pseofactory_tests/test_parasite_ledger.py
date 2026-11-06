"""Parasite survival ledger against a real local HTTP server (x-like:2103576504143634852)."""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from pseofactory.parasite_ledger import LIVE, REMOVED, UNREACHABLE, ParasiteLedger


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        code = 200 if self.path.startswith("/ok") else 404
        self.send_response(code)
        self.end_headers()
        self.wfile.write(b"x")

    def log_message(self, *a):
        pass


@pytest.fixture()
def server():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_survival_ledger_ranks_platforms_by_real_liveness(tmp_path, server):
    led = ParasiteLedger(tmp_path / "l.json")
    assert led.record_post(f"{server}/ok/1", "Reddit", "profithelm", "soc 2 cost")
    assert not led.record_post(f"{server}/ok/1", "reddit", "profithelm")  # idempotent
    led.record_post(f"{server}/ok/2", "linkedin", "profithelm", "soc 2 cost")
    led.record_post(f"{server}/gone/1", "quora", "profithelm", "soc 2 cost")
    led.record_post(f"{server}/gone/2", "quora", "profithelm", "soc 2 cost")

    assert led.recommend_platforms("profithelm") == []  # unchecked pages are not evidence

    res = led.check_all(index_probe=lambda u: "/ok/1" in u)
    assert res[f"{server}/ok/1"]["state"] == LIVE
    assert res[f"{server}/gone/1"]["state"] == REMOVED
    assert res[f"{server}/ok/2"]["indexed"] is False
    assert res[f"{server}/gone/1"]["indexed"] is None  # probes skip dead pages

    # reddit (live + indexed) beats linkedin (live, not indexed); quora (all removed) is dropped
    assert led.recommend_platforms("profithelm") == ["reddit", "linkedin"]
    quora = [s for s in led.platform_scores("profithelm") if s["platform"] == "quora"][0]
    assert quora["survival_rate"] == 0.0 and quora["indexed_rate"] is None


def test_unreachable_is_distinct_and_tenant_scoped(tmp_path):
    led = ParasiteLedger(tmp_path / "l.json")
    led.record_post("http://127.0.0.1:9/x", "medium", "prexvo")
    led.record_post("http://127.0.0.1:9/y", "reddit", "gainhelm")
    res = led.check_all()
    assert res["http://127.0.0.1:9/x"]["state"] == UNREACHABLE
    assert led.recommend_platforms("prexvo") == []
    assert led.platform_scores("gainhelm")[0]["platform"] == "reddit"
    assert led.platform_scores("nobody") == []
