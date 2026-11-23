"""
Regression tests for indexing, video factory, feedback loop, AIO observatory,
and LinkedIn queue fixes (swarm_indexing_video).
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pseofactory.aio_observatory import (
    AIOObservatory,
    treg_sampler,
)
from pseofactory.distributor import _sync_linkedin_company_queue
from pseofactory.indexer import GOOGLE_INDEXING_DAILY_QUOTA, PushIndexer
from pseofactory.indexing.feedback_loop import IndexingFeedbackLoop
from pseofactory.indexing_inspector import DailyIndexingInspector
from pseofactory.telemetry import AtomicTelemetryLogger, TelemetryEvent
from pseofactory.video_factory import (
    YouTubeQuotaGovernor,
    _save_upload_idempotency_record,
    reconcile_remote_youtube_video_quality_and_visibility,
    run_autonomous_video_pipeline,
    upload_tool_video_to_youtube,
)


def _make_site(tmp_path: Path, tenant_id: str, domain: str, slugs: list[str]) -> tuple[Path, Path, PushIndexer]:
    base_dir = tmp_path / tenant_id
    dist_dir = base_dir / "dist"
    agy_dir = base_dir / ".agy"
    dist_dir.mkdir(parents=True, exist_ok=True)
    agy_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "robots.txt").write_text(
        "User-agent: Googlebot\nAllow: /\n"
        "User-agent: Bingbot\nAllow: /\n"
        "User-agent: PerplexityBot\nAllow: /\n"
        "User-agent: GPTBot\nAllow: /\n"
        "User-agent: ClaudeBot\nAllow: /\n"
        "User-agent: Meta-ExternalAgent\nAllow: /\n"
        "User-agent: Applebot-Extended\nAllow: /\n",
        encoding="utf-8",
    )
    (dist_dir / "llms.txt").write_text("# LLMs\n", encoding="utf-8")
    (dist_dir / "feed.xml").write_text("<rss></rss>\n", encoding="utf-8")
    urls = []
    for slug in slugs:
        tdir = dist_dir / "tools" / slug
        tdir.mkdir(parents=True, exist_ok=True)
        url = f"https://{domain}/tools/{slug}/"
        urls.append(url)
        body_words = " ".join(["deterministic"] * 180)
        (tdir / "index.html").write_text(
            f"<!DOCTYPE html><html><head><title>{slug}</title>"
            f'<meta name="viewport" content="width=device-width, initial-scale=1.0">'
            f'<link rel="canonical" href="{url}"></head>'
            f'<body><main><h1>{slug}</h1><aside class="quick-answer">Direct answer 2026.</aside>'
            f"<p>{body_words}</p></main></body></html>",
            encoding="utf-8",
        )
    sm_entries = "".join(f"<url><loc>{u}</loc></url>" for u in urls)
    (dist_dir / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><urlset>{sm_entries}</urlset>',
        encoding="utf-8",
    )
    idx = PushIndexer(
        domain=domain,
        canonical_base=f"https://{domain}",
        base_dir=base_dir,
        dist_dir=dist_dir,
        ledger_path=agy_dir / "index_push_ledger.json",
        audit_log_path=agy_dir / "indexing_audit_log.json",
        rollover_queue_path=agy_dir / "gsc_rollover_queue.json",
        tenant_id=tenant_id,
    )
    idx.repo_root = base_dir
    idx.quota_governor_path = tmp_path / "shared_gsc_quota_governor.json"
    idx.ensure_indexnow_key_file()
    return base_dir, dist_dir, idx


def _frozen_datetime_cls(fixed_utc: datetime):
    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_utc.replace(tzinfo=None)
            return fixed_utc.astimezone(tz)

    return _FrozenDateTime


def test_gsc_quota_governor_resets_on_pacific_time_not_utc(tmp_path: Path) -> None:
    """
    Google Indexing API resets at midnight Pacific Time (America/Los_Angeles).
    A 429 at 2026-11-22T03:29:04Z (2026-11-21 19:29 PST) must bucket under
    2026-11-21 PT, stay blocked at 2026-11-22T04:00:00Z (20:00 PST), and reset
    cleanly at 2026-11-22T08:05:00Z (2026-11-22 00:05 PST).
    """
    _, _, idx = _make_site(tmp_path, "prexvo", "prexvo.com", ["rap-calc"])

    t_429 = datetime(2026, 11, 22, 3, 29, 4, tzinfo=timezone.utc)
    t_same_pt_evening = datetime(2026, 11, 22, 4, 0, 0, tzinfo=timezone.utc)
    t_after_pt_midnight = datetime(2026, 11, 22, 8, 5, 0, tzinfo=timezone.utc)

    with patch("pseofactory.indexer.datetime", _frozen_datetime_cls(t_429)):
        tripped = idx.trip_gsc_quota_breaker(bucket="indexing", reason="HTTP 429")
    assert tripped["date"] == "2026-11-21"

    with patch("pseofactory.indexer.datetime", _frozen_datetime_cls(t_same_pt_evening)):
        still_blocked = idx.check_and_consume_gsc_quota(units=1, bucket="indexing")
    assert still_blocked["date"] == "2026-11-21"
    assert still_blocked["allowed"] is False

    with patch("pseofactory.indexer.datetime", _frozen_datetime_cls(t_after_pt_midnight)):
        reset_ok = idx.check_and_consume_gsc_quota(units=1, bucket="indexing")
    assert reset_ok["date"] == "2026-11-22"
    assert reset_ok["allowed"] is True


def test_submit_gsc_indexing_quota_exhausted_reports_quota_deferred_and_honest_audit(tmp_path: Path) -> None:
    """
    When GSC indexing quota is exhausted (effective_daily_cap == 0):
    1. submit_gsc_indexing must report status='QUOTA_DEFERRED' (not 'IDEMPOTENT_NO_OP')
       and preserve all URLs in gsc_rollover_queue.json.
    2. WAL must commit status='QUOTA_DEFERRED' (not 'DISPATCHED').
    3. audit_asset_submission_status(live=True) must NOT report google_accepted=True
       merely because dist/sitemap.xml exists, nor bing_accepted=True merely because
       the local IndexNow key file exists.
    """
    base_dir, _, idx = _make_site(tmp_path, "gainhelm", "gainhelm.com", ["soc-2-calc", "cmmc-calc"])
    urls = [
        "https://gainhelm.com/tools/soc-2-calc/",
        "https://gainhelm.com/tools/cmmc-calc/",
    ]
    idx.trip_gsc_quota_breaker(bucket="indexing", reason="HTTP 429 daily quota exhausted")

    fake_gsccli = tmp_path / "gsccli"
    fake_gsccli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    with (
        patch("pseofactory.indexer.shutil.which", return_value=str(fake_gsccli)),
        patch.object(idx, "submit_fast_index", return_value={"status": "DISPATCHED", "actions": []}),
        patch.object(idx, "submit_gsc_sitemaps", return_value={"status": "ACCEPTED", "submissions": []}),
        patch.object(idx, "verify_gsc_indexation_loop", return_value={"oracle_verdict": "PENDING_INDEXATION"}),
    ):
        res = idx.submit_gsc_indexing(urls=urls, live=True, drain_rollover=False)

    gsc_api_blocks = [r for r in res["results"] if r.get("engine") == "google_indexing_api"]
    assert len(gsc_api_blocks) == 1
    assert gsc_api_blocks[0]["status"] == "QUOTA_DEFERRED"
    assert gsc_api_blocks[0]["quota_deferred_count"] == 2
    assert set(idx.load_gsc_rollover_queue()) == set(urls)

    wal_path = base_dir / ".agy" / ".indexing_intent_wal.jsonl"
    wal_rows = [json.loads(line) for line in wal_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    terminal = [r for r in wal_rows if r.get("intent_id") == res["intent_id"] and r.get("status") != "PENDING_INTENT"]
    assert terminal and terminal[-1]["status"] == "QUOTA_DEFERRED"

    # Honest audit: zero URLs pushed to Google or Bing, despite sitemap.xml and key file on disk
    audit = idx.audit_asset_submission_status(live=True)
    assert audit["summary"]["google_accepted_count"] == 0
    assert audit["summary"]["bing_accepted_count"] == 0
    assert audit["summary"]["overall_acceptance_rate_pct"] == 0.0


def test_daily_indexing_inspector_detects_indexing_anomaly_429_events(tmp_path: Path) -> None:
    """
    DailyIndexingInspector.audit_gsc_rollover_queue must detect HTTP_429_QUOTA_EXHAUSTED
    logged under event_type='INDEXING_ANOMALY' by PushIndexer.submit_gsc_indexing.
    """
    telemetry_path = tmp_path / "telemetry_events.jsonl"
    logger = AtomicTelemetryLogger(log_path=telemetry_path)
    rollover_path = tmp_path / "gsc_rollover_queue.json"
    rollover_path.write_text(
        json.dumps(["https://prexvo.com/tools/rap-payment-calculator/"]),
        encoding="utf-8",
    )

    logger.log_event(
        TelemetryEvent(
            event_type="INDEXING_ANOMALY",
            tenant_id="prexvo",
            error_type="HTTP_429_QUOTA_EXHAUSTED",
            error_message="429 Quota exhausted during GSC indexing on https://prexvo.com/tools/rap-payment-calculator/",
            action_taken="PRESERVED_ROLLOVER",
        )
    )

    inspector = DailyIndexingInspector(
        tenant_id="prexvo",
        rollover_queue_path=rollover_path,
        telemetry_logger=logger,
    )
    res = inspector.audit_gsc_rollover_queue()
    assert res["quota_exhausted"] is True
    assert res["status"] == "FAIL"
    assert len(res["quota_reasons"]) >= 1


def test_youtube_upload_ledger_merge_preserves_truth_flags_and_fresh_upload_persists_flags(tmp_path: Path) -> None:
    """
    1. _save_upload_idempotency_record must merge and preserve has_captions=True,
       has_pinned_comment=True, thumbnail_confirmed=True when a lower-fidelity sync
       (e.g., gitops.py reading dist/videos/uploaded_log.json) writes False values.
    2. Fresh upload_tool_video_to_youtube with caption + comment + thumbnail must
       immediately persist has_captions=True, has_pinned_comment=True, thumbnail_confirmed=True.
    3. Reconcile must not call thumbnails.set when refresh_thumbnail=False and must
       enforce a per-PT-day backoff so a video cannot reconcile 20x in one day.
    """
    repo_dir = tmp_path / "profithelm-platform"
    dist_dir = repo_dir / "dist"
    videos_dir = dist_dir / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)
    slug = "irs-2027-tax-brackets"

    # 1. Merge preserves truth flags
    _save_upload_idempotency_record(
        repo_dir,
        "profithelm",
        slug,
        {
            "property_id": "profithelm",
            "slug": slug,
            "video_id": "FdqR1G6GOUE",
            "privacy": "public",
            "has_captions": True,
            "has_pinned_comment": True,
            "thumbnail_confirmed": True,
        },
    )
    _save_upload_idempotency_record(
        repo_dir,
        "profithelm",
        slug,
        {
            "property_id": "profithelm",
            "slug": slug,
            "video_id": "FdqR1G6GOUE",
            "privacy": "public",
            "has_captions": False,
            "has_pinned_comment": False,
        },
    )
    ledger_path = repo_dir / ".agy" / "youtube_upload_ledger.json"
    saved = json.loads(ledger_path.read_text(encoding="utf-8"))["uploads"][f"profithelm:{slug}"]
    assert saved["has_captions"] is True
    assert saved["has_pinned_comment"] is True
    assert saved["thumbnail_confirmed"] is True

    # 2. Fresh upload persists has_captions, has_pinned_comment, thumbnail_confirmed
    slug2 = "section-179-calculator"
    (videos_dir / f"{slug2}.mp4").write_bytes(b"\x00" * 4096)
    (videos_dir / f"{slug2}.vtt").write_text("WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nHi\n", encoding="utf-8")
    (videos_dir / f"{slug2}-thumb.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 2048)

    gov = YouTubeQuotaGovernor(
        ledger_path=tmp_path / "yt_quota.json",
        upload_log_path=tmp_path / "upload_log.json",
    )
    fake_upload_stdout = json.dumps(
        {
            "success": True,
            "engine": "youtube_data_api_v3",
            "video_id": "vid_new_179",
            "video_url": "https://www.youtube.com/watch?v=vid_new_179",
            "quota_units_used": 2101,
        }
    )
    fake_proc = MagicMock(returncode=0, stdout=fake_upload_stdout, stderr="")
    with (
        patch("pseofactory.video_factory.probe_media_file", return_value={"valid": True, "size_bytes": 4096, "duration_seconds": 15.0}),
        patch("pseofactory.video_factory.subprocess.run", return_value=fake_proc),
        patch("pseofactory.video_factory.sync_video_catalog_and_metadata"),
    ):
        up_res = upload_tool_video_to_youtube(
            slug=slug2,
            property_id="profithelm",
            dist_dir=dist_dir,
            repo_root=repo_dir,
            privacy="public",
            live_upload=True,
            quota_governor=gov,
            upload_caption=True,
            post_pinned_comment=True,
        )
    assert up_res["status"] == "UPLOADED"
    saved2 = json.loads(ledger_path.read_text(encoding="utf-8"))["uploads"][f"profithelm:{slug2}"]
    assert saved2["has_captions"] is True
    assert saved2["has_pinned_comment"] is True
    assert saved2["thumbnail_confirmed"] is True

    # 3. Reconcile passes refresh_thumbnail=False when thumbnail_confirmed=True and backs off for the PT day
    slug3 = "section-1031-calculator"
    _save_upload_idempotency_record(
        repo_dir,
        "profithelm",
        slug3,
        {
            "property_id": "profithelm",
            "slug": slug3,
            "video_id": "w-Kx_w7Yz7o",
            "privacy": "unlisted",
            "has_captions": True,
            "has_pinned_comment": True,
            "thumbnail_confirmed": True,
        },
    )
    reconcile_calls: list[dict] = []

    def _fake_reconcile(**kwargs):
        reconcile_calls.append(kwargs)
        return {
            "video_id": kwargs["video_id"],
            "privacyStatus": "unlisted",
            "before_status": {"privacyStatus": "unlisted", "has_captions": True, "has_pinned_comment": True},
            "after_status": {"privacyStatus": "unlisted", "has_captions": True, "has_pinned_comment": True},
        }

    fixed_t = datetime(2026, 11, 22, 18, 0, 0, tzinfo=timezone.utc)
    with (
        patch("pseofactory.video_factory._in_pytest", return_value=False),
        patch("pseofactory.video_factory.datetime", _frozen_datetime_cls(fixed_t)),
        patch("pseofactory.video_factory._load_upload_idempotency_map") as load_mock,
        patch("pseofactory.video_factory._save_upload_idempotency_record") as save_mock,
        patch("pseofactory.video_factory.reconcile_remote_youtube_video_quality_and_visibility", side_effect=_fake_reconcile),
    ):
        state_holder = {
            slug3: {
                "property_id": "profithelm",
                "slug": slug3,
                "video_id": "w-Kx_w7Yz7o",
                "privacy": "unlisted",
                "has_captions": True,
                "has_pinned_comment": True,
                "thumbnail_confirmed": True,
            }
        }
        load_mock.side_effect = lambda *a, **kw: {k: dict(v) for k, v in state_holder.items()}
        save_mock.side_effect = lambda _r, _p, s, rec: state_holder.__setitem__(s, dict(rec))

        r1 = upload_tool_video_to_youtube(
            slug=slug3,
            property_id="profithelm",
            dist_dir=dist_dir,
            repo_root=repo_dir,
            privacy="public",
            live_upload=True,
            quota_governor=gov,
        )
        r2 = upload_tool_video_to_youtube(
            slug=slug3,
            property_id="profithelm",
            dist_dir=dist_dir,
            repo_root=repo_dir,
            privacy="public",
            live_upload=True,
            quota_governor=gov,
        )
    assert len(reconcile_calls) == 1
    assert reconcile_calls[0]["refresh_thumbnail"] is False
    assert r1["reconciled_in_place"] is not None
    assert r2["reconciled_in_place"] is None


def test_youtube_quota_governor_pt_reset_cost_fairness_and_starvation_telemetry(tmp_path: Path) -> None:
    """
    1. estimate_upload_cost includes comment (50u) + status check (1u) -> 2101u with thumb+caption.
    2. Quota buckets align to Pacific Time (America/Los_Angeles) so evening PT (next UTC date)
       does not prematurely reset quota and drop same-PT-day reconciles.
    3. Fair per-tenant reservation across 4 active tenants prevents profithelm from starving lienbond.
    4. run_autonomous_video_pipeline with 100% QUOTA_DEFERRED_STAGED reports QUOTA_STARVED
       and upload_blackout_detected=True (never PASS).
    """
    assert YouTubeQuotaGovernor.estimate_upload_cost(include_thumbnail=True, include_caption=True) == 2101

    ledger_path = tmp_path / "youtube_quota_ledger.json"
    upload_log_path = tmp_path / "upload_log.json"
    gov = YouTubeQuotaGovernor(
        ledger_path=ledger_path,
        upload_log_path=upload_log_path,
        daily_ceiling_units=10000,
        safety_reserve_units=400,
    )

    # At 2026-11-23T03:48Z (= 2026-11-22 19:48 PST), PT date is still 2026-11-22
    t_evening_pt = datetime(2026, 11, 23, 3, 48, 0, tzinfo=timezone.utc)
    t_next_pt_day = datetime(2026, 11, 23, 8, 10, 0, tzinfo=timezone.utc)
    with patch("pseofactory.video_factory.datetime", _frozen_datetime_cls(t_evening_pt)):
        gov.record_upload_consumption("profithelm", "s1", "v1", 2101)
        gov.record_upload_consumption("profithelm", "s1:in_place_reconcile", "v1:reconcile:1", 100)
        st_pt = gov.get_budget_status(include_thumbnail=True, include_caption=True)
    assert st_pt.date_utc == "2026-11-22"
    assert st_pt.used_units_today == 2201

    # After PT midnight (08:10Z = 00:10 PST), bucket resets to 2026-11-23
    with patch("pseofactory.video_factory.datetime", _frozen_datetime_cls(t_next_pt_day)):
        st_reset = gov.get_budget_status(include_thumbnail=True, include_caption=True)
    assert st_reset.date_utc == "2026-11-23"
    assert st_reset.used_units_today == 0

    # Per-tenant fairness across 4 tenants: profithelm gets 1 slot, cannot take lienbond's reserved slot
    fair_gov = YouTubeQuotaGovernor(
        ledger_path=tmp_path / "fair_quota.json",
        upload_log_path=tmp_path / "fair_upload_log.json",
        daily_ceiling_units=10000,
        safety_reserve_units=400,
    )
    tenants = ["profithelm", "prexvo", "gainhelm", "lienbond"]
    with patch("pseofactory.video_factory.datetime", _frozen_datetime_cls(t_next_pt_day)):
        st_ph1 = fair_gov.get_budget_status(
            include_thumbnail=True, include_caption=True, property_id="profithelm", active_tenants=tenants
        )
        assert st_ph1.can_upload is True
        fair_gov.record_upload_consumption("profithelm", "tool-1", "vid_ph_1", 2101)

        # ProfitHelm already took its 1 guaranteed slot; remaining 3 slots are reserved for prexvo, gainhelm, lienbond
        st_ph2 = fair_gov.get_budget_status(
            include_thumbnail=True, include_caption=True, property_id="profithelm", active_tenants=tenants
        )
        assert st_ph2.can_upload is False
        assert "FAIRNESS" in st_ph2.reason or "RESERVED" in st_ph2.reason

        # LienBond can STILL upload!
        st_lb = fair_gov.get_budget_status(
            include_thumbnail=True, include_caption=True, property_id="lienbond", active_tenants=tenants
        )
        assert st_lb.can_upload is True

    # Quota-starvation blackout telemetry: 100% QUOTA_DEFERRED_STAGED with 0 verified uploads must NOT report PASS
    repo_dir = tmp_path / "lienbond"
    dist_dir = repo_dir / "dist"
    videos_dir = dist_dir / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)
    slug = "bid-bond-calculator"
    (dist_dir / "tools" / slug).mkdir(parents=True, exist_ok=True)
    (dist_dir / "tools" / slug / "index.html").write_text(
        "<!DOCTYPE html><html><head><title>Bid Bond Calculator</title></head><body><h1>Bid Bond</h1></body></html>",
        encoding="utf-8",
    )
    (videos_dir / f"{slug}.mp4").write_bytes(b"\x00" * 65536)

    with patch(
        "pseofactory.video_factory.upload_tool_video_to_youtube",
        return_value={"status": "QUOTA_DEFERRED_STAGED", "slug": slug, "property_id": "lienbond", "quota_units_used": 0},
    ):
        tel = run_autonomous_video_pipeline(
            property_id="lienbond",
            tools=[{"slug": slug, "title": "Bid Bond Calculator"}],
            dist_dir=dist_dir,
            repo_root=repo_dir,
            max_renders=0,
            synthesize_missing=False,
            live_upload=True,
            quota_governor=fair_gov,
        )
    assert tel["status"] == "QUOTA_STARVED"
    assert tel["status"] != "PASS"
    assert tel["upload_blackout_detected"] is True
    assert tel["quota_deferred_count"] == 1


def test_feedback_loop_preserves_distributor_broadcast_ledger_fields(tmp_path: Path) -> None:
    """
    feedback_loop._sync_external_distribution_for_candidate must inspect both
    post_url and url, and must merge/preserve rich distributor.py fields
    (mode, dispatches, metrics, youtube_video_id) instead of overwriting with a 4-key stub.
    """
    base_dir = tmp_path / "prexvo"
    dist_dir = base_dir / "dist"
    (base_dir / ".agy").mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)

    b_ledger = base_dir / ".agy" / "broadcast_ledger.json"
    rich_entry = {
        "slug": "discretionary-income-calculator-for-student-loans",
        "post_url": "https://prexvo.com/tools/discretionary-income-calculator-for-student-loans/?agi=65000",
        "mode": "SYNDICATED_VERIFIED",
        "company_id": "106482194",
        "youtube_video_id": "yt_abc123",
        "dispatches": {"youtube": "LIVE_PUBLISHED", "linkedin": "BLOCKED_ADMIN_ACCESS"},
        "metrics": {"linkedin_access_status": "ADMIN_ACCESS_DENIED", "youtube_has_captions": True},
    }
    b_ledger.write_text(json.dumps([rich_entry], indent=2), encoding="utf-8")

    loop = IndexingFeedbackLoop(
        property_id="prexvo",
        domain="prexvo.com",
        canonical_base="https://prexvo.com",
        base_dir=base_dir,
        dist_dir=dist_dir,
        indexer=MagicMock(),
        preflight_engine=MagicMock(),
    )
    loop._sync_external_distribution_for_candidate(
        slug="discretionary-income-calculator-for-student-loans",
        target_url="https://prexvo.com/tools/discretionary-income-calculator-for-student-loans/",
        overlay_spec={"title_rewrite": "Discretionary Income Calc", "quick_answer": "Fast answer."},
    )

    after = json.loads(b_ledger.read_text(encoding="utf-8"))
    assert len(after) == 1
    assert after[0]["mode"] == "SYNDICATED_VERIFIED"
    assert after[0]["dispatches"]["youtube"] == "LIVE_PUBLISHED"
    assert after[0]["metrics"]["youtube_has_captions"] is True
    assert after[0]["youtube_video_id"] == "yt_abc123"


def test_aio_observatory_retries_transient_502_timeout_and_blocks_junk_probes(tmp_path: Path) -> None:
    """
    1. treg_sampler retries transient HTTP 502 and subprocess TimeoutExpired with
       bounded exponential backoff, succeeding when a retry passes.
    2. treg_sampler fails fast on deterministic HTTP 400 (no retries).
    3. Junk probe queries like 'amazon com robots txt' are rejected from record/sample.
    """
    ok_stdout = json.dumps(
        {
            "output": {"found": True, "data": {"answerMarkdown": "Costs $500.", "citations": []}},
            "provider": "AnyAPI",
            "costUsd": 0.0018,
        }
    )
    calls = {"n": 0}

    def _flaky_run(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return MagicMock(returncode=1, stdout="", stderr="treg: HTTP 502 bad gateway")
        if calls["n"] == 2:
            raise subprocess.TimeoutExpired(cmd="treg", timeout=10)
        return MagicMock(returncode=0, stdout=ok_stdout, stderr="")

    sleeps: list[float] = []
    with (
        patch("pseofactory.aio_observatory.shutil.which", return_value="/usr/bin/treg"),
        patch("pseofactory.aio_observatory.subprocess.run", side_effect=_flaky_run),
        patch("time.sleep", side_effect=lambda s: sleeps.append(s)),
    ):
        res = treg_sampler("soc 2 audit cost calculator", timeout=10.0)
    assert res["found"] is True
    assert calls["n"] == 3
    assert len(sleeps) == 2
    assert sleeps[1] >= sleeps[0]

    # HTTP 400 fails fast without retrying
    calls_400 = {"n": 0}

    def _err_400(*args, **kwargs):
        calls_400["n"] += 1
        return MagicMock(returncode=1, stdout="", stderr="treg: HTTP 400 bad request")

    with (
        patch("pseofactory.aio_observatory.shutil.which", return_value="/usr/bin/treg"),
        patch("pseofactory.aio_observatory.subprocess.run", side_effect=_err_400),
        patch("time.sleep"),
    ):
        with pytest.raises(RuntimeError, match="HTTP 400"):
            treg_sampler("bad query", timeout=10.0)
    assert calls_400["n"] == 1

    # Junk probe guard
    obs = AIOObservatory(tmp_path / "aio.db")
    summary = obs.sample(
        [("profithelm", "amazon com robots txt"), ("gainhelm", "soc 2 audit cost calculator")],
        sampler=lambda q: {"found": True, "answer": "Costs $500.", "citations": [], "provider": "fake", "cost_usd": 0.0},
    )
    assert summary["sampled"] == 1
    assert summary["skipped_junk"] == 1
    assert obs.analyze("amazon com robots txt")["samples"] == 0


def test_linkedin_queue_sync_prunes_stale_blocked_and_unverified_tenant_items(tmp_path: Path) -> None:
    """
    When li_admin_status != 'VERIFIED_COMPANY_ADMIN', _sync_linkedin_company_queue
    must prune any stale queued items for that tenant while preserving all other
    tenants' items atomically.
    """
    tmp_queue = tmp_path / "queue.json"
    seeded = [
        {"slug": "ph-1", "property_id": "profithelm", "company_id": "143884102", "priority_score": 80.0},
        {"slug": "px-1", "property_id": "prexvo", "company_id": "106482194", "priority_score": 70.0},
        {"slug": "px-2", "property_id": "prexvo", "company_id": "106482194", "priority_score": 65.0},
        {"slug": "gh-1", "property_id": "gainhelm", "company_id": "106482195", "priority_score": 60.0},
    ]
    tmp_queue.write_text(json.dumps(seeded, indent=2), encoding="utf-8")

    res_px = _sync_linkedin_company_queue(
        li_queue_path=tmp_queue,
        norm_prop="prexvo",
        corp_company_id="106482194",
        li_admin_status="ADMIN_ACCESS_DENIED",
        prioritized_queue=[],
        all_assets={},
    )
    assert res_px["updated"] is True
    assert res_px["pruned_count"] == 2
    after_px = json.loads(tmp_queue.read_text(encoding="utf-8"))
    assert [r["property_id"] for r in after_px] == ["profithelm", "gainhelm"]

    res_gh = _sync_linkedin_company_queue(
        li_queue_path=tmp_queue,
        norm_prop="gainhelm",
        corp_company_id="106482195",
        li_admin_status="UNVERIFIED_ADMIN_ACCESS",
        prioritized_queue=[],
        all_assets={},
    )
    assert res_gh["updated"] is True
    assert res_gh["pruned_count"] == 1
    after_gh = json.loads(tmp_queue.read_text(encoding="utf-8"))
    assert [r["property_id"] for r in after_gh] == ["profithelm"]

    # Second call when already pruned must be a no-op
    pre_bytes = tmp_queue.read_bytes()
    res_px2 = _sync_linkedin_company_queue(
        li_queue_path=tmp_queue,
        norm_prop="prexvo",
        corp_company_id="106482194",
        li_admin_status="ADMIN_ACCESS_DENIED",
        prioritized_queue=[],
        all_assets={},
    )
    assert res_px2["updated"] is False
    assert res_px2["pruned_count"] == 0
    assert tmp_queue.read_bytes() == pre_bytes
