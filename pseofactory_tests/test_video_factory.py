"""
Tests for the autonomous multi-tenant video synthesis and quota-aware YouTube
distribution pipeline (`pseofactory.video_factory`).

Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _require_video_factory_module():
    spec = importlib.util.find_spec("pseofactory.video_factory")
    assert spec is not None, "pseofactory.video_factory module is missing from pseofactory"
    import pseofactory.video_factory as vf_mod
    return vf_mod


def test_three_sentence_spoken_transcript_precision_across_tenants() -> None:
    """
    Verifies that every ProfitHelm and Prexvo tool produces a verified 3-sentence
    (40-60 word) spoken script with zero conversational filler and zero forbidden dashes,
    and that invalid scripts are deterministically rejected.
    """
    from pseofactory.maintenance import PREXVO_DEFAULT_TOOLS, PROFITHELM_DEFAULT_TOOLS
    vf_mod = _require_video_factory_module()
    assert_three_sentence_spoken_precision = vf_mod.assert_three_sentence_spoken_precision
    extract_and_verify_three_sentence_script = vf_mod.extract_and_verify_three_sentence_script

    for prop, tools in (
        ("profithelm", PROFITHELM_DEFAULT_TOOLS),
        ("prexvo", PREXVO_DEFAULT_TOOLS),
    ):
        for tool in tools:
            res = extract_and_verify_three_sentence_script(tool, property_id=prop)
            assert res["sentence_count"] == 3, f"{prop}/{tool['slug']} must have 3 sentences"
            assert 40 <= res["word_count"] <= 60, f"{prop}/{tool['slug']} word_count={res['word_count']}"
            assert "\u2014" not in res["spoken_script"]
            assert "\u2013" not in res["spoken_script"]

    # Rejects 2-sentence script
    with pytest.raises(ValueError, match="strictly 3 sentences"):
        assert_three_sentence_spoken_precision(
            "Under IRC Section 179, an $85,000 equipment purchase yields $29,750 in tax savings. "
            "Run the calculator at profithelm.com to model your 2026 deduction.",
            brand_name="ProfitHelm",
        )

    # Rejects too-short (<40 words) 3-sentence script
    with pytest.raises(ValueError, match="40-60 words"):
        assert_three_sentence_spoken_precision(
            "Section 179 allows immediate expensing of $85,000 in 2026. "
            "At a 35% bracket, this saves $29,750 in federal tax. "
            "Model your scenario at profithelm.com.",
            brand_name="ProfitHelm",
        )

    # Rejects legacy conversational filler ("Welcome to ProfitHelm...")
    with pytest.raises(ValueError, match="conversational filler"):
        assert_three_sentence_spoken_precision(
            "Welcome to ProfitHelm, where an $85,000 equipment purchase under IRC Section 179 "
            "generates an immediate $85,000 deduction in 2026. "
            "At a 35% marginal federal tax rate, this reduces your current year tax liability by $29,750. "
            "Compare bonus depreciation phase-down schedules and state conformity limits on ProfitHelm.",
            brand_name="ProfitHelm",
        )


def test_page_value_synthesis_gate_filters_low_value_and_ranks_anchors(tmp_path: Path) -> None:
    """
    Verifies that evaluate_page_video_eligibility gates synthesis on page value score,
    compiled HTML existence, and calculation proof rather than bulk rendering all pages.
    """
    vf_mod = _require_video_factory_module()
    evaluate_page_video_eligibility = vf_mod.evaluate_page_video_eligibility

    dist_dir = tmp_path / "dist"
    for slug in ("section-179-calculator", "contractor-surety-bond-cost-calculator"):
        t_dir = dist_dir / "tools" / slug
        t_dir.mkdir(parents=True, exist_ok=True)
        (t_dir / "index.html").write_text(
            f"<!DOCTYPE html><html><head><title>{slug}</title></head><body><h1>{slug}</h1></body></html>",
            encoding="utf-8",
        )

    tools = [
        {"slug": "section-179-calculator", "title": "Section 179 Tax Deduction Calculator"},
        {
            "slug": "contractor-surety-bond-cost-calculator",
            "title": "Contractor Surety Bond Cost Calculator",
            "low_value": True,
            "priority_score": 25.0,
        },
        {"slug": "irs-2027-tax-brackets", "title": "IRS 2027 Tax Brackets Calculator"},
    ]

    eligibilities = evaluate_page_video_eligibility(
        tools=tools,
        property_id="profithelm",
        dist_dir=dist_dir,
        repo_root=tmp_path,
        min_page_value_score=45.0,
        require_compiled_html=True,
    )
    by_slug = {e.slug: e for e in eligibilities}

    assert by_slug["section-179-calculator"].eligible is True
    assert by_slug["section-179-calculator"].gate_status == "ELIGIBLE_NEEDS_SYNTHESIS"
    assert by_slug["section-179-calculator"].page_value_score >= 70.0

    # Low-value page is gated out
    assert by_slug["contractor-surety-bond-cost-calculator"].eligible is False
    assert by_slug["contractor-surety-bond-cost-calculator"].gate_status == "SKIPPED_LOW_PAGE_VALUE"

    # Uncompiled HTML page is gated out when require_compiled_html=True
    assert by_slug["irs-2027-tax-brackets"].eligible is False
    assert by_slug["irs-2027-tax-brackets"].gate_status == "SKIPPED_UNCOMPILED_HTML"


def test_youtube_daily_10000_unit_quota_governor(tmp_path: Path) -> None:
    """
    Verifies that YouTubeQuotaGovernor enforces the 10,000-unit daily YouTube Data API v3
    quota ceiling (with 400-unit safety reserve = 9,600 effective upload ceiling),
    cross-references upload_log.json, and blocks the 6th upload (5 * 1650 = 8,250 used,
    1,350 remaining < 1,650 required).
    """
    vf_mod = _require_video_factory_module()
    YouTubeQuotaGovernor = vf_mod.YouTubeQuotaGovernor

    ledger_path = tmp_path / "youtube_quota_ledger.json"
    upload_log_path = tmp_path / "upload_log.json"
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    month_str = today_str[:7]

    # Seed 3 uploads in CLI upload_log.json for today (3 * 1650 = 4950 units)
    upload_log_path.write_text(
        json.dumps(
            {
                month_str: {
                    "uploads": [
                        {
                            "timestamp": f"{today_str}T08:00:00",
                            "title": "Upload 1",
                            "video_id": "vid_cli_1",
                            "quota_units_used": 1650,
                        },
                        {
                            "timestamp": f"{today_str}T09:00:00",
                            "title": "Upload 2",
                            "video_id": "vid_cli_2",
                            "quota_units_used": 1650,
                        },
                        {
                            "timestamp": f"{today_str}T10:00:00",
                            "title": "Upload 3",
                            "video_id": "vid_cli_3",
                            "quota_units_used": 1650,
                        },
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    gov = YouTubeQuotaGovernor(
        ledger_path=ledger_path,
        upload_log_path=upload_log_path,
        daily_ceiling_units=10000,
        safety_reserve_units=400,
    )

    st1 = gov.get_budget_status(date_override=today_str)
    assert st1.used_units_today == 4950
    assert st1.remaining_units_today == 4650
    assert st1.can_upload is True
    assert st1.max_additional_uploads_today == 2

    # Record 2 more uploads via governor (total 5 uploads = 8250 units)
    gov.record_upload_consumption("profithelm", "tool-4", "vid_4", 1650, date_override=today_str)
    st2 = gov.record_upload_consumption("prexvo", "tool-5", "vid_5", 1650, date_override=today_str)
    assert st2.used_units_today == 8250
    assert st2.remaining_units_today == 1350
    assert st2.can_upload is False
    assert "DAILY_QUOTA_CEILING_REACHED" in st2.reason


def test_end_to_end_video_synthesis_and_idempotent_youtube_upload(tmp_path: Path) -> None:
    """
    Verifies end-to-end video asset synthesis (.mp4 > 1024 bytes, .vtt, -thumb.png,
    batch_seo_catalog.json, youtube_metadata.json), AssetIntegrityEvaluator compliance,
    and idempotent `youtube upload --engine api` execution with quota deferral.
    """
    from pseofactory.distributor import dispatch_to_distribution_lead, export_all_syndication_files
    from pseofactory.maintenance import AssetIntegrityEvaluator, ConfigurablePropertyAdapter
    vf_mod = _require_video_factory_module()
    YouTubeQuotaGovernor = vf_mod.YouTubeQuotaGovernor
    probe_media_file = vf_mod.probe_media_file
    run_autonomous_video_pipeline = vf_mod.run_autonomous_video_pipeline

    for prop, slug, title, domain in (
        ("profithelm", "section-179-calculator", "Section 179 Tax Deduction Calculator", "profithelm.com"),
        ("prexvo", "student-loan-rap-calculator", "Student Loan RAP Plan Calculator", "prexvo.com"),
    ):
        repo_dir = tmp_path / prop
        dist_dir = repo_dir / "dist"
        synd_dir = repo_dir / "syndication"
        tool_dir = dist_dir / "tools" / slug
        tool_dir.mkdir(parents=True, exist_ok=True)
        (dist_dir / "index.html").write_text(
            f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><title>{prop.title()}</title>"
            f"<meta name='description' content='Deterministic statutory modeling calculators for {prop.title()}.'>"
            f"<link rel='canonical' href='https://{domain}/'></head>"
            f"<body><main><h1>{prop.title()}</h1></main></body></html>",
            encoding="utf-8",
        )
        (tool_dir / "index.html").write_text(
            f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><title>{title}</title>"
            f"<meta name='description' content='Deterministic statutory calculator for {title}.'>"
            f"<link rel='canonical' href='https://{domain}/tools/{slug}/'></head>"
            f"<body><main><h1>{title}</h1></main></body></html>",
            encoding="utf-8",
        )

        tools_list = [{"slug": slug, "title": title}]
        export_all_syndication_files(output_dir=synd_dir, tools=tools_list, property_id=prop)

        gov = YouTubeQuotaGovernor(
            ledger_path=repo_dir / ".agy" / "youtube_quota_ledger.json",
            upload_log_path=repo_dir / ".agy" / "upload_log.json",
        )

        fake_cli_out = json.dumps(
            {
                "success": True,
                "engine": "youtube_data_api_v3",
                "video_id": f"yt_{prop}_123",
                "video_url": f"https://www.youtube.com/watch?v=yt_{prop}_123",
                "quota_units_used": 1650,
            }
        )

        real_run = subprocess.run
        with patch("pseofactory.video_factory.subprocess.run") as mock_subproc:

            def _side_effect(cmd, *args, **kwargs):
                if isinstance(cmd, list) and len(cmd) >= 3 and "upload" in cmd:
                    m = MagicMock()
                    m.returncode = 0
                    m.stdout = fake_cli_out
                    m.stderr = ""
                    return m
                return real_run(cmd, *args, **kwargs)

            mock_subproc.side_effect = _side_effect

            telemetry = run_autonomous_video_pipeline(
                property_id=prop,
                tools=tools_list,
                dist_dir=dist_dir,
                repo_root=repo_dir,
                max_renders=1,
                synthesize_missing=True,
                live_upload=True,
                privacy="unlisted",
                use_headless_browser=False,
                use_neural_tts=False,
                quota_governor=gov,
            )

        assert telemetry["status"] == "PASS"
        assert telemetry["blackout_detected"] is False
        assert telemetry["rendered_videos_on_disk_count"] == 1
        assert telemetry["uploaded_live_count"] == 1
        assert telemetry["per_slug_dispatch_status"][slug] == "UPLOADED"

        mp4_file = dist_dir / "videos" / f"{slug}.mp4"
        vtt_file = dist_dir / "videos" / f"{slug}.vtt"
        thumb_file = dist_dir / "videos" / f"{slug}-thumb.png"
        cat_file = dist_dir / "videos" / "batch_seo_catalog.json"

        assert mp4_file.is_file() and mp4_file.stat().st_size > 1024
        assert vtt_file.is_file() and "WEBVTT" in vtt_file.read_text(encoding="utf-8")
        assert thumb_file.is_file() and thumb_file.stat().st_size > 1024
        probe = probe_media_file(mp4_file)
        assert probe["valid"] is True
        assert probe["has_video"] is True
        assert probe["has_audio"] is True

        cat_data = json.loads(cat_file.read_text(encoding="utf-8"))
        assert len(cat_data) == 1
        assert cat_data[0]["slug"] == slug
        assert cat_data[0]["video_id"] == f"yt_{prop}_123"
        assert cat_data[0]["sentence_count"] == 3
        assert 40 <= cat_data[0]["word_count"] <= 60

        yt_meta = json.loads((synd_dir / slug / "youtube_metadata.json").read_text(encoding="utf-8"))
        assert yt_meta["video_id"] == f"yt_{prop}_123"
        assert yt_meta["upload_status"] == "UPLOADED"

        # Second run must hit idempotency ledger with 0 new uploads and 0 new quota units
        telemetry_2 = run_autonomous_video_pipeline(
            property_id=prop,
            tools=tools_list,
            dist_dir=dist_dir,
            repo_root=repo_dir,
            max_renders=1,
            synthesize_missing=True,
            live_upload=True,
            privacy="unlisted",
            use_headless_browser=False,
            use_neural_tts=False,
            quota_governor=gov,
        )
        assert telemetry_2["uploaded_live_count"] == 0
        assert telemetry_2["idempotent_uploaded_count"] == 1
        assert telemetry_2["per_slug_dispatch_status"][slug] == "ALREADY_UPLOADED_IDEMPOTENT"

        # Verify AssetIntegrityEvaluator passes 100% with the rendered video catalog
        adapter = ConfigurablePropertyAdapter(
            property_id=prop,
            brand_name=prop.title(),
            domain=domain,
            canonical_base=f"https://{domain}",
            dist_dir=dist_dir,
            repo_path=repo_dir,
            tools=tools_list,
        )
        evaluator = AssetIntegrityEvaluator(enforce_master_seo=False, enforce_operational_shield=False)
        audit_rep = evaluator.audit_all(adapter, check_engine_drift=False, check_ledger=False)
        assert not any("batch_seo_catalog.json" in d.asset_path for d in audit_rep.drifted_assets)

        # Verify dispatch_to_distribution_lead includes youtube_video_factory telemetry
        dist_res = dispatch_to_distribution_lead(
            run_id=f"test-vf-dist-{prop}",
            property_id=prop,
            dry_run=True,
            dist_dir=dist_dir,
            tools=tools_list,
        )
        assert "youtube_video_factory" in dist_res
        assert dist_res["youtube_video_factory"]["per_slug_dispatch_status"][slug] == "ALREADY_UPLOADED_IDEMPOTENT"
