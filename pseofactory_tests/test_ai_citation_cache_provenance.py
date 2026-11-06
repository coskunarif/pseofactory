"""
Regression tests for the AI citation cache provenance bug.

Before the fix, TregChecker persisted synthetic offline fallback payloads into
.agy/ai_citation_cache.json as if they were measured, and served every cached
entry forever. 539 of 541 production entries were fabricated, and they drove
citation_gap_status and the ai_math_boost in GSC brief ROI ranking.
Zero em-dashes. Zero en-dashes.
"""

import json
from datetime import datetime, timedelta, timezone

import pseofactory.trends.treg_checker as tc


def _isolate(monkeypatch, tmp_path):
    """Run the checker as production would (no pytest guard), with no treg binary and a temp cache."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(tc.shutil, "which", lambda _name: None)
    monkeypatch.setattr(tc, "_PROCESS_AI_CITATION_CACHE", {})
    monkeypatch.setattr(tc, "_PROCESS_DISK_CACHE_LOADED", True)
    checker = tc.TregChecker(tenant_domains=["gainhelm.com"])
    checker._disk_cache_path = tmp_path / "ai_citation_cache.json"
    # Empty AIO observatory stub so the real observatory DB never leaks into these tests.
    checker.observatory = _EmptyObservatory()
    return checker


class _EmptyObservatory:
    def citation_evidence(self, *_args, **_kwargs):
        return None


def test_offline_fallback_is_never_persisted_as_measured(monkeypatch, tmp_path):
    checker = _isolate(monkeypatch, tmp_path)
    res = checker.check_ai_citation("soc 2 audit cost calculator")

    assert res["endpoint_called"].endswith("#offline_fallback")
    assert res.get("measured") is False

    on_disk = {}
    if checker._disk_cache_path.exists():
        on_disk = json.loads(checker._disk_cache_path.read_text(encoding="utf-8"))
    assert "soc 2 audit cost calculator" not in on_disk
    assert "soc 2 audit cost calculator" not in tc._PROCESS_AI_CITATION_CACHE


def test_fabricated_unstamped_and_expired_entries_are_not_served(monkeypatch, tmp_path):
    checker = _isolate(monkeypatch, tmp_path)
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    poisoned = {
        "endpoint_called": f"{tc.ENDPOINT_AI_CITATION}#offline_fallback",
        "citation_gap_status": "TENANT_CITED",
        "tenant_cited": True,
    }
    tc._PROCESS_AI_CITATION_CACHE["fabricated query"] = dict(poisoned)
    tc._PROCESS_AI_CITATION_CACHE["unstamped query"] = dict(poisoned, endpoint_called=tc.ENDPOINT_AI_CITATION)
    tc._PROCESS_AI_CITATION_CACHE["expired query"] = dict(
        poisoned, endpoint_called=tc.ENDPOINT_AI_CITATION, checked_at=old
    )

    for q in ("fabricated query", "unstamped query", "expired query"):
        res = checker.check_ai_citation(q)
        assert res["citation_gap_status"] != "TENANT_CITED", q
        assert res.get("measured") is False, q


def test_fresh_measured_entry_is_served_from_cache(monkeypatch, tmp_path):
    checker = _isolate(monkeypatch, tmp_path)
    fresh = {
        "query": "cmmc 2.0 compliance cost calculator",
        "endpoint_called": tc.ENDPOINT_AI_CITATION,
        "citation_gap_status": "TENANT_CITED",
        "tenant_cited": True,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "measured": True,
    }
    tc._PROCESS_AI_CITATION_CACHE["cmmc 2.0 compliance cost calculator"] = fresh
    res = checker.check_ai_citation("cmmc 2.0 compliance cost calculator")
    assert res["citation_gap_status"] == "TENANT_CITED"
    assert res["measured"] is True
