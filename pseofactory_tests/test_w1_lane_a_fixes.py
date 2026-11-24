"""
Wave 1 Lane A surgical regression tests:
1. filter_unchanged_push_urls(engine=None) rollover queue & missing google engine unblocking
2. Unified quarantine ledger (list vs dict preservation) and 50+ tenant path resolution
3. Atomic check_and_consume_gsc_quota under concurrent multi-process/multi-thread contention
4. IndexingPreflightEngine._dist_memo_cache strictness key & offline config reload on inspect_dist
5. Live GSC URL inspection DB upsert error logging and surfacing
Zero em-dashes. Zero en-dashes.
"""

import json
import logging
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from pseofactory.indexer import PushIndexer
from pseofactory.indexing.feedback_loop import IndexingFeedbackLoop
from pseofactory.indexing.preflight import IndexingPreflightEngine


def _make_html(title: str = "Test Tool", words: int = 180, viewport: bool = True) -> str:
    vp = '<meta name="viewport" content="width=device-width, initial-scale=1.0">' if viewport else ""
    body_words = " ".join(["benchmark"] * words)
    return (
        f"<!DOCTYPE html><html><head><title>{title}</title>{vp}"
        '<link rel="canonical" href="https://example.com/tools/calc/">'
        "</head><body>"
        f"<h1>{title}</h1>"
        '<aside class="quick-answer">Direct answer summary for search.</aside>'
        f"<p>{body_words}</p></body></html>"
    )


def _worker_consume_quota(gov_path_str: str, base_dir_str: str, n_calls: int, out_q) -> None:
    idx = PushIndexer(
        domain="tenant1.com",
        canonical_base="https://tenant1.com",
        base_dir=Path(base_dir_str),
        dist_dir=Path(base_dir_str) / "dist",
        tenant_id="tenant1",
    )
    idx.quota_governor_path = Path(gov_path_str)
    allowed_count = 0
    for _ in range(n_calls):
        res = idx.check_and_consume_gsc_quota(units=1, bucket="inspection", tenant_id="tenant1")
        if res["allowed"]:
            allowed_count += 1
    out_q.put(allowed_count)


def test_filter_unchanged_push_urls_unblocks_google_rollover_and_missing_google(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    (dist_dir / "about").mkdir(parents=True, exist_ok=True)
    (dist_dir / "tools" / "calc").mkdir(parents=True, exist_ok=True)
    (dist_dir / "tools" / "done").mkdir(parents=True, exist_ok=True)
    (dist_dir / "about" / "index.html").write_text("<html><body>About</body></html>", encoding="utf-8")
    (dist_dir / "tools" / "calc" / "index.html").write_text("<html><body>Calc</body></html>", encoding="utf-8")
    (dist_dir / "tools" / "done" / "index.html").write_text("<html><body>Done</body></html>", encoding="utf-8")

    ledger_path = tmp_path / ".agy" / "index_push_ledger.json"
    indexer = PushIndexer(
        domain="example.com",
        canonical_base="https://example.com",
        base_dir=tmp_path,
        dist_dir=dist_dir,
        ledger_path=ledger_path,
        rollover_queue_path=tmp_path / ".agy" / "gsc_rollover_queue.json",
        tenant_id="example",
    )

    u_rollover = "https://example.com/about/"
    u_missing_google = "https://example.com/tools/calc/"
    u_both_pushed = "https://example.com/tools/done/"

    h_rollover = indexer.get_url_content_hash(u_rollover)
    h_missing = indexer.get_url_content_hash(u_missing_google)
    h_done = indexer.get_url_content_hash(u_both_pushed)

    indexer.save_pushed_ledger(
        {
            u_rollover: {
                "hash": h_rollover,
                "tenant_id": "example",
                "google_rollover_queued": True,
                "engines": {"indexnow": {"hash": h_rollover}},
            },
            u_missing_google: {
                "hash": h_missing,
                "tenant_id": "example",
                "engines": {"indexnow": {"hash": h_missing}},
            },
            u_both_pushed: {
                "hash": h_done,
                "tenant_id": "example",
                "engines": {
                    "indexnow": {"hash": h_done},
                    "google": {"hash": h_done},
                },
            },
        }
    )

    to_push, skipped = indexer.filter_unchanged_push_urls(
        [u_rollover, u_missing_google, u_both_pushed],
        force=False,
        engine=None,
        tenant_id="example",
    )
    assert u_rollover in to_push
    assert u_missing_google in to_push
    assert u_both_pushed in skipped

    loop = IndexingFeedbackLoop(
        property_id="example",
        domain="example.com",
        base_dir=tmp_path,
        dist_dir=dist_dir,
        indexer=indexer,
    )
    with patch.object(
        indexer,
        "dispatch_automated_indexing",
        return_value={"status": "SUCCESS", "urls_pushed": 2},
    ) as mock_dispatch:
        res = loop.dispatch_multi_engine_push([u_rollover, u_missing_google], live=False)
    assert res["status"] != "IDEMPOTENT_NO_OP"
    assert mock_dispatch.called


def test_quarantine_ledger_preserves_list_and_dict_and_resolves_50_plus_tenants(tmp_path: Path) -> None:
    # 1. Dict ledger updated via preflight.quarantine_blocked_urls must keep dict entries and schema
    dict_ledger = tmp_path / "dict_quarantine.json"
    dict_ledger.write_text(
        json.dumps(
            {
                "https://site.com/existing-404/": {
                    "url": "https://site.com/existing-404/",
                    "code": "QUARANTINE_HTTP_ERROR",
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    engine = IndexingPreflightEngine(domain="site.com", property_id="site", workspace_root=tmp_path)
    engine.quarantine_blocked_urls(
        ["https://site.com/new-thin/"],
        ledger_path=dict_ledger,
    )
    loaded_dict = json.loads(dict_ledger.read_text(encoding="utf-8"))
    assert isinstance(loaded_dict, dict)
    assert "https://site.com/existing-404/" in loaded_dict
    assert "https://site.com/new-thin/" in loaded_dict

    # 2. List ledger updated via PushIndexer.preflight_airlock must keep list entries and schema
    dist_dir = tmp_path / "site_repo" / "dist"
    (dist_dir / "clean").mkdir(parents=True, exist_ok=True)
    (dist_dir / "clean" / "index.html").write_text("<html><body><h1>Clean</h1></body></html>", encoding="utf-8")
    list_ledger = tmp_path / "site_repo" / ".agy" / "indexing_quarantine_ledger.json"
    list_ledger.parent.mkdir(parents=True, exist_ok=True)
    list_ledger.write_text(
        json.dumps(
            [
                {
                    "property_id": "site",
                    "domain": "site.com",
                    "url": "https://site.com/old-preflight-block/",
                    "status": "BLOCKED",
                }
            ],
            indent=2,
        ),
        encoding="utf-8",
    )
    indexer = PushIndexer(
        domain="site.com",
        canonical_base="https://site.com",
        base_dir=tmp_path / "site_repo",
        dist_dir=dist_dir,
        quarantine_ledger_path=list_ledger,
        tenant_id="site",
    )
    airlock_res = indexer.preflight_airlock(["https://site.com/missing-404/"])
    assert len(airlock_res.quarantined_urls) == 1
    loaded_list = json.loads(list_ledger.read_text(encoding="utf-8"))
    assert isinstance(loaded_list, list)
    urls_in_list = {item["url"] for item in loaded_list}
    assert "https://site.com/old-preflight-block/" in urls_in_list
    assert "https://site.com/missing-404/" in urls_in_list

    # 3. Dynamic per-tenant path resolution for 50+ tenants (no fallback to root .agy/)
    ws = tmp_path / "fleet_ws"
    ws.mkdir(parents=True, exist_ok=True)
    for i in range(1, 53):
        t_dir = ws / f"tenant-{i:02d}"
        t_dir.mkdir(parents=True, exist_ok=True)
        (t_dir / ".pseofactory.json").write_text(
            json.dumps({"property_id": f"tenant_{i:02d}", "domain": f"tenant{i:02d}.com"}),
            encoding="utf-8",
        )

    eng_50 = IndexingPreflightEngine(
        domain="tenant50.com",
        property_id="tenant_50",
        dist_dir=None,
        workspace_root=ws,
    )
    eng_50.quarantine_blocked_urls(["https://tenant50.com/bad/"])
    expected_50 = ws / "tenant-50" / ".agy" / "indexing_quarantine_ledger.json"
    assert expected_50.is_file()
    assert not (ws / ".agy" / "indexing_quarantine_ledger.json").exists()

    # Unknown tenant must also not pollute root .agy/indexing_quarantine_ledger.json
    eng_unknown = IndexingPreflightEngine(
        domain="unregistered99.com",
        property_id="unregistered99",
        dist_dir=None,
        workspace_root=ws,
    )
    eng_unknown.quarantine_blocked_urls(["https://unregistered99.com/bad/"])
    assert (ws / ".agy" / "tenants" / "unregistered99" / "indexing_quarantine_ledger.json").is_file()
    assert not (ws / ".agy" / "indexing_quarantine_ledger.json").exists()


def test_check_and_consume_gsc_quota_atomic_under_concurrency(tmp_path: Path) -> None:
    from pseofactory.indexer import _gsc_quota_day_pt

    gov_path = tmp_path / "gsc_quota_governor.json"
    gov_path.write_text(
        json.dumps(
            {
                "date": _gsc_quota_day_pt(),
                "timezone": "America/Los_Angeles",
                "inspection_used": 160,
                "indexing_used": 0,
                "quota_limit": 180,
                "indexing_quota_limit": 200,
                "indexing_by_tenant": {},
                "inspection_by_tenant": {"tenant1": 160},
                "per_tenant_indexing_floor": 40,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # Multi-process contention: 4 processes x 10 calls = 40 attempts for 20 remaining units
    ctx = multiprocessing.get_context("spawn")
    out_q = ctx.Queue()
    procs = [
        ctx.Process(target=_worker_consume_quota, args=(str(gov_path), str(tmp_path), 10, out_q))
        for _ in range(4)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=30)
        assert p.exitcode == 0

    total_allowed = sum(out_q.get(timeout=5) for _ in range(4))
    assert total_allowed == 20
    final_state = json.loads(gov_path.read_text(encoding="utf-8"))
    assert final_state["inspection_used"] == 180
    assert final_state["inspection_by_tenant"]["tenant1"] == 180

    # Also verify multi-thread atomic increment on indexing bucket
    gov_thread = tmp_path / "gsc_quota_governor_threads.json"
    gov_thread.write_text(
        json.dumps(
            {
                "date": _gsc_quota_day_pt(),
                "timezone": "America/Los_Angeles",
                "inspection_used": 0,
                "indexing_used": 0,
                "quota_limit": 180,
                "indexing_quota_limit": 200,
                "indexing_by_tenant": {},
                "inspection_by_tenant": {},
                "per_tenant_indexing_floor": 40,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    def _thread_call(_i: int) -> bool:
        idx = PushIndexer(
            domain="tenant1.com",
            canonical_base="https://tenant1.com",
            base_dir=tmp_path,
            dist_dir=tmp_path / "dist",
            tenant_id="tenant1",
        )
        idx.quota_governor_path = gov_thread
        return idx.check_and_consume_gsc_quota(units=1, bucket="indexing", tenant_id="tenant1")["allowed"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_thread_call, range(25)))

    assert sum(1 for ok in results if ok) == 25
    thread_state = json.loads(gov_thread.read_text(encoding="utf-8"))
    assert thread_state["indexing_used"] == 25
    assert thread_state["indexing_by_tenant"]["tenant1"] == 25


def test_preflight_dist_cache_key_and_offline_config_reload(tmp_path: Path) -> None:
    IndexingPreflightEngine.clear_cache()

    dist_dir = tmp_path / "dist_strict"
    tool_dir = dist_dir / "tools" / "calc"
    tool_dir.mkdir(parents=True, exist_ok=True)
    # 50 words, no viewport meta
    (tool_dir / "index.html").write_text(_make_html(words=50, viewport=False), encoding="utf-8")

    eng_lenient = IndexingPreflightEngine(
        domain="example.com",
        property_id="example",
        dist_dir=dist_dir,
        min_words=10,
        tier1_cap=5,
        require_viewport=False,
        fail_closed=False,
    )
    rep_lenient = eng_lenient.inspect_dist(dist_dir)
    assert rep_lenient.is_gate_passed is True
    assert rep_lenient.passed_count == 1

    # Different min_words on same dist_dir must not hit stale _dist_memo_cache
    eng_strict_words = IndexingPreflightEngine(
        domain="example.com",
        property_id="example",
        dist_dir=dist_dir,
        min_words=150,
        tier1_cap=5,
        require_viewport=False,
        fail_closed=False,
    )
    rep_strict_words = eng_strict_words.inspect_dist(dist_dir)
    assert rep_strict_words.is_gate_passed is False
    assert rep_strict_words.blocked_count == 1

    # Different require_viewport on same dist_dir must not hit stale _dist_memo_cache
    eng_strict_vp = IndexingPreflightEngine(
        domain="example.com",
        property_id="example",
        dist_dir=dist_dir,
        min_words=10,
        tier1_cap=5,
        require_viewport=True,
        fail_closed=False,
    )
    rep_strict_vp = eng_strict_vp.inspect_dist(dist_dir)
    assert rep_strict_vp.is_gate_passed is False
    assert rep_strict_vp.blocked_count == 1

    # Different tier1_cap must not reuse previous push_eligible_urls slice
    dist_multi = tmp_path / "dist_multi"
    for slug in ("a", "b", "c"):
        d = dist_multi / "tools" / slug
        d.mkdir(parents=True, exist_ok=True)
        html = _make_html(words=180, viewport=True).replace(
            "https://example.com/tools/calc/",
            f"https://example.com/tools/{slug}/",
        )
        (d / "index.html").write_text(html, encoding="utf-8")
    rep_cap3 = IndexingPreflightEngine(domain="example.com", tier1_cap=3).inspect_dist(dist_multi)
    rep_cap1 = IndexingPreflightEngine(domain="example.com", tier1_cap=1).inspect_dist(dist_multi)
    assert len(rep_cap3.push_eligible_urls) == 3
    assert len(rep_cap1.push_eligible_urls) == 1

    # Engine constructed with dist_dir=None must reload _redirects, _headers, robots.txt on inspect_dist
    dist_rules = tmp_path / "dist_rules"
    for slug in ("redirected", "header-noindex", "robots-blocked", "ok"):
        d = dist_rules / "tools" / slug
        d.mkdir(parents=True, exist_ok=True)
        html = _make_html(words=180, viewport=True).replace(
            "https://example.com/tools/calc/",
            f"https://example.com/tools/{slug}/",
        )
        (d / "index.html").write_text(html, encoding="utf-8")
    (dist_rules / "_redirects").write_text("/tools/redirected/ /tools/ok/ 301\n", encoding="utf-8")
    (dist_rules / "_headers").write_text("/tools/header-noindex/*\n  X-Robots-Tag: noindex\n", encoding="utf-8")
    (dist_rules / "robots.txt").write_text("User-agent: *\nDisallow: /tools/robots-blocked/\n", encoding="utf-8")

    eng_no_dist = IndexingPreflightEngine(domain="example.com", property_id="example", dist_dir=None)
    rep_rules = eng_no_dist.inspect_dist(dist_rules)
    assert "https://example.com/tools/redirected/" in rep_rules.blocked_urls
    assert "https://example.com/tools/header-noindex/" in rep_rules.blocked_urls
    assert "https://example.com/tools/robots-blocked/" in rep_rules.blocked_urls
    assert rep_rules.push_eligible_urls == ["https://example.com/tools/ok/"]
    assert eng_no_dist.dist_dir is None
    assert eng_no_dist._redirect_rules == []


def test_verify_gsc_indexation_loop_logs_and_surfaces_db_upsert_error(tmp_path: Path, caplog) -> None:
    indexer = PushIndexer(
        domain="example.com",
        canonical_base="https://example.com",
        base_dir=tmp_path,
        dist_dir=tmp_path / "dist",
        tenant_id="example",
    )

    fake_insp = {
        "url": "https://example.com/tools/calc/",
        "status": "INSPECTED",
        "is_indexed": True,
        "verdict": "PASS",
        "coverage_state": "Submitted and indexed",
        "indexing_state": "INDEXING_ALLOWED",
        "page_fetch_state": "SUCCESSFUL",
        "robots_txt_state": "ALLOWED",
    }

    with (
        caplog.at_level(logging.WARNING, logger="pseofactory.indexer"),
        patch.object(indexer, "preflight_airlock", side_effect=lambda urls: (list(urls), [])),
        patch.object(indexer, "inspect_gsc_url", return_value=fake_insp),
        patch(
            "pseofactory.trends.db.TrendHistoryDB.upsert_gsc_url_inspection_states",
            side_effect=RuntimeError("simulated sqlite upsert failure"),
        ),
    ):
        res = indexer.verify_gsc_indexation_loop(
            urls=["https://example.com/tools/calc/"],
            live=True,
        )

    assert "db_upsert_error" in res
    assert "simulated sqlite upsert failure" in res["db_upsert_error"]
    assert any("simulated sqlite upsert failure" in rec.message for rec in caplog.records)
