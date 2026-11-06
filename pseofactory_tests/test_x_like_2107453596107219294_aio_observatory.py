"""
Tests for the AI Overview observatory (x-like:2107453596107219294, @jakezward):
track one AI Overview over 7 days, find patterns, reverse engineer citations,
build the page around the findings, and measure tenant citation share.
Zero em-dashes. Zero en-dashes.
"""

import json
from datetime import datetime, timedelta, timezone

import pseofactory.trends.treg_checker as tc
from pseofactory.aio_observatory import (
    AIOObservatory,
    extract_facts,
    extract_headings,
    has_table,
    lead_has_number,
    load_watchlist,
    parse_treg_aio_output,
)

Q = "cmmc level 2 assessment cost"
CORE = "https://www.preveil.com/blog/cmmc-certification-costs/"
ROT = "https://www.paramify.com/blog/cmmc-cost"
ONE = "https://www.linkedin.com/pulse/cmmc-cost-2026"
TENANT = "https://gainhelm.com/tools/cmmc-2-0-compliance-cost-calculator/"

ANSWER = (
    "A CMMC Level 2 assessment typically costs $30,000 to $75,000 in auditor fees.\n\n"
    "### Total All-In Compliance Costs\n\n"
    "| Cost Category | Estimated Expense |\n| --- | --- |\n| Formal C3PAO Assessment | $30,000 to $75,000 |\n\n"
    "### Primary Drivers of Your Cost\n\nScope of CUI. Expect 6 to 12 months of remediation.\n"
)


def _payload(urls, answer=ANSWER, found=True):
    return {"found": found, "answer": answer, "citations": [{"url": u, "title": u} for u in urls], "provider": "fake", "cost_usd": 0.0018}


def _seed(obs, days):
    """days: list of url lists, one AI Overview sample per day ending now."""
    now = datetime.now(timezone.utc)
    for i, urls in enumerate(days):
        at = now - timedelta(days=len(days) - 1 - i, hours=1)
        obs.record("gainhelm", Q, _payload(urls), at=at)


def test_pattern_extractors():
    assert "$30,000 to $75,000" in extract_facts(ANSWER)
    assert "6 to 12 months" in extract_facts(ANSWER)
    assert extract_headings(ANSWER) == ["Total All-In Compliance Costs", "Primary Drivers of Your Cost"]
    assert lead_has_number(ANSWER) is True
    assert lead_has_number("Comparing IBR and RAP comes down to timelines. It costs $5.") is False
    assert has_table(ANSWER) is True
    assert has_table("no table here") is False


def test_parse_treg_envelope():
    raw = json.dumps(
        {
            "output": {"found": True, "data": {"answer": "plain", "answerMarkdown": "### md", "citations": [{"index": 1, "title": "t", "url": CORE}]}},
            "provider": "AnyAPI",
            "costUsd": 0.0018,
        }
    )
    p = parse_treg_aio_output(raw)
    assert p["found"] is True and p["answer"] == "### md" and p["citations"][0]["url"] == CORE and p["cost_usd"] == 0.0018


def test_seven_day_stability_classes_and_blueprint(tmp_path):
    obs = AIOObservatory(tmp_path / "aio.db")
    _seed(
        obs,
        [
            [CORE, ROT],
            [CORE],
            [CORE, ROT, ONE],
            [CORE],
            [CORE, ROT],
            [CORE],
            [CORE],
        ],
    )
    a = obs.analyze(Q, tenant_domains=["gainhelm.com"])
    classes = {c["url"]: c["class"] for c in a["citations"]}
    assert classes == {CORE: "core", ROT: "rotating", ONE: "one_off"}
    assert a["samples"] == 7 and a["aio_presence_rate"] == 1.0 and a["confidence"] == "ok"
    assert a["tenant_citation_rate"] == 0.0

    bp = obs.blueprint(Q, tenant_domains=["gainhelm.com"])
    assert bp["winnable_slots"][0]["url"] == ROT
    assert bp["incumbent_core"][0]["url"] == CORE
    assert "$30,000 to $75,000" in bp["must_include_facts"]
    assert "Total All-In Compliance Costs" in bp["section_headings"]
    assert bp["format"] == {"lead_with_number": True, "include_table": True}
    assert any("rotating citation slot" in act for act in bp["actions"])


def test_window_excludes_old_samples_and_errors_are_unknown(tmp_path):
    obs = AIOObservatory(tmp_path / "aio.db")
    obs.record("gainhelm", Q, _payload([CORE]), at=datetime.now(timezone.utc) - timedelta(days=30))
    obs.record("gainhelm", Q, None, error="treg exit 1")
    assert obs.analyze(Q)["samples"] == 0
    assert obs.citation_evidence(Q, tenant_domains=["gainhelm.com"]) is None


def test_sample_records_errors_without_counting_them(tmp_path):
    obs = AIOObservatory(tmp_path / "aio.db")

    def sampler(q):
        if q == "boom":
            raise RuntimeError("provider down")
        return _payload([CORE])

    summary = obs.sample([("gainhelm", Q), ("gainhelm", "boom")], sampler=sampler)
    assert summary["sampled"] == 1 and summary["errors"] == 1 and summary["found"] == 1
    assert obs.analyze("boom")["samples"] == 0


def test_scoreboard_tenant_citation_share(tmp_path):
    obs = AIOObservatory(tmp_path / "aio.db")
    _seed(obs, [[CORE, TENANT], [CORE], [CORE, TENANT], [CORE]])
    obs.record("gainhelm", "no aio query", _payload([], found=False))
    board = obs.scoreboard()["tenants"]["gainhelm"]
    assert board["queries_tracked"] == 2
    assert board["samples"] == 5
    assert board["aio_presence_rate"] == 0.8
    assert board["citation_share"] == 0.5
    assert board["queries_citing_tenant"] == [Q]
    assert board["top_competitor_domains"][0]["domain"] == "preveil.com"


def test_observatory_evidence_feeds_treg_checker_as_measured(tmp_path, monkeypatch):
    obs = AIOObservatory(tmp_path / "aio.db")
    _seed(obs, [[CORE, TENANT], [CORE, TENANT], [CORE]])
    monkeypatch.setattr(tc, "_PROCESS_AI_CITATION_CACHE", {})
    checker = tc.TregChecker(tenant_domains=["gainhelm.com"], observatory=obs)
    res = checker.check_ai_citation(Q)
    assert res["measured"] is True
    assert res["endpoint_called"] == "google.serp.ai_overview.observatory"
    assert res["citation_gap_status"] == "TENANT_CITED"
    assert res["tenant_citation_rate"] == round(2 / 3, 3)
    assert res["aio_blueprint"]["samples"] == 3
    assert tc.is_fresh_measured_citation(res)


def test_watchlist_covers_all_three_tenants_core_tools(tmp_path):
    pairs = load_watchlist(path=tmp_path / "missing.json")
    tenants = {t for t, _ in pairs}
    assert {"profithelm", "prexvo", "gainhelm"} <= tenants
    assert ("gainhelm", "cmmc 2.0 compliance cost calculator") in pairs
    extra = tmp_path / "wl.json"
    extra.write_text(json.dumps({"gainhelm": ["How much does a CMMC Level 2 assessment cost"]}))
    pairs2 = load_watchlist(path=extra, tenants=["gainhelm"])
    assert ("gainhelm", "how much does a cmmc level 2 assessment cost") in pairs2
    assert all(t == "gainhelm" for t, _ in pairs2)
