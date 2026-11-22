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


@pytest.mark.host_estate
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


@pytest.mark.host_estate
def test_broadcast_quality_verification_and_keyframe_contact_sheet(tmp_path: Path) -> None:
    """
    Verifies that rendered MP4 streams pass strict EBU R128 broadcast loudness (-14.0 +/- 2.2 LUFS),
    audio-video duration sync (<= 0.08s), dynamic speech range (LRA >= 0.5 LU, never static sine tone),
    zero black frames, zero silence gaps, and zero-defect 4-segment keyframe contact sheet extraction.
    Also verifies quota-aware in-place remote YouTube reconciliation (50-unit videos.update instead
    of 1,650-unit re-upload).
    """
    vf_mod = _require_video_factory_module()
    assert hasattr(vf_mod, "verify_broadcast_stream_quality"), "verify_broadcast_stream_quality missing"
    assert hasattr(vf_mod, "extract_keyframe_contact_sheet"), "extract_keyframe_contact_sheet missing"
    assert hasattr(
        vf_mod, "reconcile_remote_youtube_video_quality_and_visibility"
    ), "reconcile_remote_youtube_video_quality_and_visibility missing"
    assert vf_mod.DEFAULT_UPLOAD_PRIVACY == "public"

    slug = "section-1031-calculator"
    title = "Section 1031 Like-Kind Exchange Tax Deferral Calculator"
    dist_dir = tmp_path / "dist"
    tool_dir = dist_dir / "tools" / slug
    tool_dir.mkdir(parents=True, exist_ok=True)
    (tool_dir / "index.html").write_text(
        f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><title>{title}</title></head>"
        f"<body><main><h1>{title}</h1><p>Statutory calculation under IRC Section 1031.</p></main></body></html>",
        encoding="utf-8",
    )

    asset = vf_mod.synthesize_tool_video_asset(
        tool={"slug": slug, "title": title},
        property_id="profithelm",
        dist_dir=dist_dir,
        repo_root=tmp_path,
        force_render=True,
        use_headless_browser=False,
        use_neural_tts=False,
    )
    mp4_path = Path(asset["video_file"])
    thumb_path = Path(asset["thumbnail_file"])
    vtt_path = Path(asset["vtt_file"])
    assert mp4_path.is_file()
    assert thumb_path.is_file()
    assert vtt_path.is_file()

    # 1. Broadcast stream quality telemetry check (ffprobe + ffmpeg ebur128/silencedetect/blackdetect)
    bq = vf_mod.verify_broadcast_stream_quality(mp4_path)
    assert bq["passed"] is True, f"Broadcast quality failed: {bq}"
    assert bq["av_sync_ok"] is True
    assert bq["av_sync_delta_seconds"] <= 0.08
    assert bq["loudness_ok"] is True
    assert -16.2 <= bq["integrated_lufs"] <= -11.8
    assert bq["dynamic_speech_ok"] is True
    assert bq["lra_lu"] >= 0.5
    assert bq["probe"]["sample_rate"] == 48000
    assert bq["probe"]["channels"] == 2
    assert bq["black_frames_count"] == 0
    assert bq["silence_gaps_count"] == 0

    # 2. Keyframe contact sheet extraction across 4 segments
    kf = vf_mod.extract_keyframe_contact_sheet(
        mp4_path,
        tmp_path / "keyframes",
        label="test_1031",
    )
    assert kf["contact_sheet"] is not None
    assert Path(kf["contact_sheet"]).is_file()
    assert len(kf["segment_frames"]) == 4

    # 3. Quota-aware in-place remote reconciliation (50 units vs 1,650-unit re-upload)
    gov = vf_mod.YouTubeQuotaGovernor(
        ledger_path=tmp_path / "quota_ledger.json",
        upload_log_path=tmp_path / "upload_log.json",
    )
    real_run = subprocess.run
    info_calls = {"count": 0}

    def _mock_subproc(cmd, *args, **kwargs):
        if isinstance(cmd, list) and "info" in cmd:
            info_calls["count"] += 1
            priv = "unlisted" if info_calls["count"] == 1 else "public"
            m = MagicMock()
            m.returncode = 0
            m.stdout = json.dumps(
                {
                    "video_id": "w-Kx_w7Yz7o",
                    "title": "Section 1031 Calculator",
                    "privacy_status": priv,
                    "embeddable": True,
                    "duration": "PT16S",
                    "definition": "hd",
                    "has_captions": True,
                    "quota_units_used": 1,
                }
            )
            m.stderr = ""
            return m
        if isinstance(cmd, list) and "update" in cmd:
            m = MagicMock()
            m.returncode = 0
            m.stdout = json.dumps({"success": True, "video_id": "w-Kx_w7Yz7o", "privacy_status": "public"})
            m.stderr = ""
            return m
        return real_run(cmd, *args, **kwargs)

    with patch("pseofactory.video_factory.subprocess.run", side_effect=_mock_subproc):
        rec = vf_mod.reconcile_remote_youtube_video_quality_and_visibility(
            video_id="w-Kx_w7Yz7o",
            slug=slug,
            property_id="profithelm",
            desired_privacy="public",
            thumbnail_path=thumb_path,
            vtt_path=vtt_path,
            refresh_thumbnail=False,
            upload_caption=False,
            quota_governor=gov,
        )
    assert rec["quota_units_used"] == 50
    assert rec["reupload_cost_avoided_units"] == 1600
    assert rec["before_status"]["privacyStatus"] == "unlisted"
    assert rec["after_status"]["privacyStatus"] == "public"
    assert rec["uploadStatus"] == "processed"
    assert rec["privacyStatus"] == "public"
    assert rec["public_accessible"] is True


def test_cross_platform_syndication_parity_and_public_visibility_verification(tmp_path: Path) -> None:
    """
    Verifies cross-platform syndication parity across LinkedIn, Facebook, and YouTube:
    1. Facebook post contract (`assert_facebook_post`) forbids outbound links in teaser body
       and enforces parameterized `utm_content=first_comment` canonical deep links in the first comment.
    2. Word-boundary truncation (`_clean_tool_title_and_short`) eliminates mid-word slicing
       (`"1031 Like Kind Exchange St"`, `"Section 1250 Re"`), and non-curated prediction-market / 1031
       slugs route to domain-specific calculation proofs instead of `$4,349` tax variance fallback.
    3. `verify_cross_platform_public_visibility` surfaces truthful public visibility across
       LinkedIn (`PUBLIC_FEED_VERIFIED` vs `ADMIN_ACCESS_DENIED`), Facebook (`PUBLIC_PERMALINK_VERIFIED`
       with zero body links and first-comment canonical URL), and YouTube (`PUBLIC_CAPTIONED_COMMENTED_VERIFIED`
       with uploaded WebVTT captions and top-level canonical comment).
    """
    import pseofactory.contracts as contracts_mod
    import pseofactory.distributor as dist_mod

    assert hasattr(contracts_mod, "assert_facebook_post"), "assert_facebook_post missing in pseofactory.contracts"
    assert hasattr(
        dist_mod, "verify_cross_platform_public_visibility"
    ), "verify_cross_platform_public_visibility missing in pseofactory.distributor"

    # 1. Facebook zero-link body + first-comment canonical contract
    with pytest.raises(ValueError, match="External URL detected in Facebook teaser body"):
        contracts_mod.assert_facebook_post(
            "Run the calculator at https://profithelm.com/tools/saas-runway-calculator/ to check your burn.",
            "https://profithelm.com/tools/saas-runway-calculator/?utm_source=facebook&utm_medium=social&utm_campaign=saas-runway-calculator&utm_content=first_comment",
            context="test_fb_inline_url",
        )

    with pytest.raises(ValueError, match="utm_content=first_comment"):
        contracts_mod.assert_facebook_post(
            "A 2026 audit of 500 seed-stage startups reveals a 6.4-month runway gap when net burn excludes deferred tax liabilities. How many months of true net runway does your model project?",
            "https://profithelm.com/tools/saas-runway-calculator/?utm_source=facebook&utm_medium=social",
            context="test_fb_missing_first_comment_utm",
        )

    fb_pack = dist_mod.generate_facebook_post("saas-runway-calculator")
    assert "http://" not in fb_pack["teaser_content"]
    assert "https://" not in fb_pack["teaser_content"]
    assert "utm_source=facebook" in fb_pack["first_comment"]
    assert "utm_content=first_comment" in fb_pack["first_comment"]
    contracts_mod.assert_facebook_post(
        fb_pack["teaser_content"],
        fb_pack["first_comment"],
        context="test_fb_pack_profithelm",
    )

    # 2. Word-boundary truncation & domain calculation proof routing
    _, short_1031 = dist_mod._clean_tool_title_and_short(
        "1031 Like Kind Exchange St Louis MO Calculator",
        "1031-like-kind-exchange-st-louis-mo-calculator",
    )
    assert not short_1031.endswith(" St"), f"Dangling token in short_title: {short_1031!r}"
    _, short_1250 = dist_mod._clean_tool_title_and_short(
        "Section 1250 Recapture Calculator",
        "section-1250-recapture-calculator",
    )
    assert not short_1250.endswith(" Re"), f"Mid-word truncation in short_title: {short_1250!r}"

    pred_proof = dist_mod._resolve_tool_calculation_proof(
        "what-is-implied-probability-in-prediction-markets-calculator",
        property_id="profithelm",
    )
    assert pred_proof["published_output"] == 400.0
    assert "4,349" not in pred_proof["published_output_formatted"]

    exch_proof = dist_mod._resolve_tool_calculation_proof(
        "1031-like-kind-exchange-st-louis-mo-calculator",
        property_id="profithelm",
    )
    assert exch_proof["published_output"] == 292500.0
    assert "4,349" not in exch_proof["published_output_formatted"]

    # 3. Cross-platform public visibility verification across profithelm, prexvo, gainhelm, and lienbond
    # Seed isolated tmp_path tenant fixtures with realistic live-shaped ledgers (zero hardcoded theater)
    ph_repo = tmp_path / "profithelm-platform"
    (ph_repo / ".agy").mkdir(parents=True)
    (ph_repo / "dist" / "videos").mkdir(parents=True)
    (ph_repo / ".agy" / "broadcast_ledger.json").write_text(
        json.dumps(
            [
                {
                    "slug": "saas-runway-calculator",
                    "company_id": "143884102",
                    "post_url": "https://profithelm.com/tools/saas-runway-calculator/",
                    "first_comment": "https://profithelm.com/tools/saas-runway-calculator/?utm_source=linkedin&utm_content=first_comment",
                    "facebook_permalink": "https://www.facebook.com/groups/331399459887663/permalink/1092639183763683/",
                    "dispatches": {"linkedin": "LIVE_PUBLISHED", "facebook": "LIVE_PUBLISHED"},
                    "metrics": {
                        "linkedin_access_status": "VERIFIED_COMPANY_ADMIN",
                        "linkedin_urn": "urn:li:activity:7520927474453643265",
                        "facebook_visibility": "public_permalink_verified",
                        "facebook_first_comment_verified": True,
                    },
                },
                {
                    "slug": "irs-2027-tax-brackets",
                    "company_id": "143884102",
                    "post_url": "https://profithelm.com/tools/irs-2027-tax-brackets/",
                    "first_comment": "https://profithelm.com/tools/irs-2027-tax-brackets/?utm_source=linkedin&utm_content=first_comment",
                    "facebook_permalink": "https://www.facebook.com/groups/1332262893636652/permalink/3281313738731548/",
                    "dispatches": {"linkedin": "LIVE_PUBLISHED", "facebook": "PENDING_ADMIN_MODERATION"},
                    "metrics": {
                        "linkedin_access_status": "VERIFIED_COMPANY_ADMIN",
                        "linkedin_urn": "urn:li:activity:7518942436178464768",
                        "facebook_visibility": "pending_admin_approval",
                        "facebook_first_comment_verified": False,
                    },
                },
            ],
            indent=2,
        ),
        encoding="utf-8",
    )
    (ph_repo / "dist" / "videos" / "uploaded_log.json").write_text(
        json.dumps(
            [
                {
                    "slug": "irs-2027-tax-brackets",
                    "video_id": "kvUXwNgPxWQ",
                    "status": "uploaded",
                    "url": "https://www.youtube.com/watch?v=kvUXwNgPxWQ",
                    "caption_id": "cap-ph-1",
                    "pinned_comment_id": "pin-ph-1",
                }
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    px_repo = tmp_path / "prexvo"
    (px_repo / ".agy").mkdir(parents=True)
    (px_repo / ".agy" / "broadcast_ledger.json").write_text(
        json.dumps(
            [
                {
                    "slug": "student-loan-repayment-calculator",
                    "company_id": "106482194",
                    "post_url": "https://prexvo.com/tools/student-loan-repayment-calculator/",
                    "facebook_permalink": "https://www.facebook.com/groups/331399459887663/permalink/1092642197096715/",
                    "dispatches": {"linkedin": "BLOCKED_ADMIN_ACCESS", "facebook": "LIVE_PUBLISHED"},
                    "metrics": {
                        "linkedin_access_status": "ADMIN_ACCESS_DENIED",
                        "linkedin_urn": None,
                        "facebook_visibility": "public_permalink_verified",
                        "facebook_first_comment_verified": True,
                    },
                }
            ],
            indent=2,
        ),
        encoding="utf-8",
    )
    (px_repo / ".agy" / "youtube_pipeline_telemetry.json").write_text(
        json.dumps(
            {
                "property_id": "prexvo",
                "status": "PASS",
                "upload_error_count": 0,
                "stages": {
                    "4_youtube_distribution": {
                        "results": {
                            "student-loan-repayment-calculator": {
                                "property_id": "prexvo",
                                "slug": "student-loan-repayment-calculator",
                                "status": "ALREADY_UPLOADED_IDEMPOTENT",
                                "video_id": "Q3PK4LtwfrM",
                                "video_url": "https://www.youtube.com/watch?v=Q3PK4LtwfrM",
                                "has_captions": True,
                                "has_pinned_comment": True,
                            }
                        }
                    }
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    gh_repo = tmp_path / "gainhelm"
    (gh_repo / ".agy").mkdir(parents=True)
    (gh_repo / ".agy" / "broadcast_ledger.json").write_text(
        json.dumps(
            [
                {
                    "slug": "soc-2-audit-cost-calculator",
                    "company_id": "106482195",
                    "post_url": "https://gainhelm.com/tools/soc-2-audit-cost-calculator/",
                    "facebook_permalink": "https://www.facebook.com/groups/331399459887663/permalink/1092641363763465/",
                    "dispatches": {"linkedin": "BLOCKED_ADMIN_ACCESS", "facebook": "LIVE_PUBLISHED"},
                    "metrics": {
                        "linkedin_access_status": "ADMIN_ACCESS_DENIED",
                        "linkedin_urn": None,
                        "facebook_visibility": "public_permalink_verified",
                        "facebook_first_comment_verified": True,
                    },
                }
            ],
            indent=2,
        ),
        encoding="utf-8",
    )
    (gh_repo / ".agy" / "youtube_pipeline_telemetry.json").write_text(
        json.dumps(
            {
                "property_id": "gainhelm",
                "status": "PASS",
                "upload_error_count": 0,
                "stages": {
                    "4_youtube_distribution": {
                        "results": {
                            "cmmc-2-0-compliance-cost-calculator": {
                                "property_id": "gainhelm",
                                "slug": "cmmc-2-0-compliance-cost-calculator",
                                "status": "ALREADY_UPLOADED_IDEMPOTENT",
                                "video_id": "5zH1GcBqr-E",
                                "video_url": "https://www.youtube.com/watch?v=5zH1GcBqr-E",
                                "has_captions": True,
                                "has_pinned_comment": True,
                            }
                        }
                    }
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    lb_repo = tmp_path / "lienbond"
    (lb_repo / ".agy").mkdir(parents=True)
    # Seed poisoned cross-tenant entries inside lienbond to prove strict domain & company_id filtering
    (lb_repo / ".agy" / "broadcast_ledger.json").write_text(
        json.dumps(
            [
                {
                    "slug": "bid-bond-calculator",
                    "company_id": "143884102",
                    "url": "https://profithelm.com/tools/bid-bond-calculator/",
                    "post_url": "https://lienbond.com/tools/bid-bond-calculator/",
                    "facebook_permalink": "https://www.facebook.com/groups/331399459887663/permalink/1092641363763465/",
                    "dispatches": {"linkedin": "BLOCKED_ADMIN_ACCESS", "facebook": "LOCAL_DRAFT_ONLY"},
                    "metrics": {
                        "linkedin_access_status": "ADMIN_ACCESS_DENIED",
                        "linkedin_urn": "urn:li:activity:9999999999999999999",
                        "facebook_visibility": "public_permalink_verified",
                    },
                }
            ],
            indent=2,
        ),
        encoding="utf-8",
    )
    (lb_repo / ".agy" / "youtube_pipeline_telemetry.json").write_text(
        json.dumps(
            {
                "property_id": "lienbond",
                "status": "PASS",
                "upload_error_count": 0,
                "stages": {
                    "4_youtube_distribution": {
                        "results": {
                            "bid-bond-calculator": {
                                "property_id": "lienbond",
                                "slug": "bid-bond-calculator",
                                "status": "QUOTA_DEFERRED_STAGED",
                            }
                        }
                    }
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    fixture_repos = {
        "profithelm": ph_repo,
        "prexvo": px_repo,
        "gainhelm": gh_repo,
        "lienbond": lb_repo,
    }
    for prop, f_repo in fixture_repos.items():
        vis = dist_mod.verify_cross_platform_public_visibility(property_id=prop, repo_dir=f_repo)
        assert set(vis["platforms"].keys()) == {"linkedin", "facebook", "youtube"}
        assert "verified_live_platforms" in vis
        assert "channel_statuses" in vis
        if prop == "profithelm":
            assert vis["all_three_platforms_publicly_verifiable"] is True
            assert vis["verified_live_platforms"] == ["linkedin", "facebook", "youtube"]
            assert vis["platforms"]["linkedin"]["company_id"] == "143884102"
            assert vis["platforms"]["linkedin"]["verification_status"] == "PUBLIC_FEED_VERIFIED"
            assert vis["platforms"]["linkedin"]["admin_access_status"] == "VERIFIED_COMPANY_ADMIN"
            assert vis["platforms"]["linkedin"]["channel_status"] == dist_mod.CHANNEL_STATUS_LIVE_PUBLISHED
            assert vis["platforms"]["linkedin"]["verified_public_posts_count"] == 2
            assert vis["platforms"]["facebook"]["verification_status"] == "PUBLIC_PERMALINK_VERIFIED"
            assert vis["platforms"]["facebook"]["verified_public_posts_count"] == 1
            assert vis["platforms"]["facebook"]["moderation_blocked_count"] == 1
            assert vis["platforms"]["youtube"]["verification_status"] == "PUBLIC_VIDEOS_CAPTIONS_AND_COMMENTS_VERIFIED"
            assert vis["platforms"]["youtube"]["verified_public_videos_count"] == 1
            assert all(
                v["has_captions"] is True and v["has_pinned_comment"] is True
                for v in vis["platforms"]["youtube"]["verified_public_videos"]
            )
        elif prop in ("prexvo", "gainhelm"):
            assert vis["all_three_platforms_publicly_verifiable"] is False
            assert vis["verified_live_platforms"] == ["facebook", "youtube"]
            assert vis["platforms"]["linkedin"]["admin_access_status"] == "ADMIN_ACCESS_DENIED"
            assert vis["platforms"]["linkedin"]["channel_status"] == dist_mod.CHANNEL_STATUS_BLOCKED_ADMIN_ACCESS
            assert vis["platforms"]["linkedin"]["verification_status"] == "BLOCKED_COMPANY_PAGE_ADMIN_GRANT_REQUIRED"
            assert vis["platforms"]["linkedin"]["credential_gap"] is not None
            assert vis["platforms"]["facebook"]["verification_status"] == "PUBLIC_PERMALINK_VERIFIED"
            assert vis["platforms"]["facebook"]["verified_public_posts_count"] == 1
            assert all(
                p["outbound_urls_in_body"] == 0 and p["first_comment_verified"] is True
                for p in vis["platforms"]["facebook"]["verified_public_permalinks"]
            )
            assert vis["platforms"]["youtube"]["verified_public_videos_count"] == 1
            assert "ProfitHelm" not in vis["platforms"]["youtube"]["channel_title"]
        else:
            assert prop == "lienbond"
            assert vis["all_three_platforms_publicly_verifiable"] is False
            assert vis["verified_live_platforms"] == []
            assert vis["platforms"]["linkedin"]["company_id"] == ""
            assert vis["platforms"]["linkedin"]["company_name"] == "LienBond"
            assert vis["platforms"]["linkedin"]["channel_status"] == dist_mod.CHANNEL_STATUS_BLOCKED_ADMIN_ACCESS
            assert vis["platforms"]["linkedin"]["verified_public_posts_count"] == 0
            assert vis["platforms"]["facebook"]["channel_status"] == dist_mod.CHANNEL_STATUS_LOCAL_DRAFT_ONLY
            assert vis["platforms"]["facebook"]["verified_public_posts_count"] == 0
            assert vis["platforms"]["youtube"]["channel_status"] == dist_mod.CHANNEL_STATUS_LOCAL_DRAFT_ONLY
            assert vis["platforms"]["youtube"]["verified_public_videos_count"] == 0
            assert "GainHelm" not in vis["platforms"]["linkedin"]["company_name"]
            assert "ProfitHelm" not in vis["platforms"]["youtube"]["channel_title"]


def test_youtube_upload_errors_never_report_pass_and_flag_upload_blackout(tmp_path: Path):
    """
    Regression test for truthful YouTube upload failure reporting:
      1. 14/14 UPLOAD_ERROR with 0 verified uploads must NEVER report status == "PASS";
         must report status == "UPLOAD_BLACKOUT" and upload_blackout_detected is True.
      2. Mixed prior idempotent uploads + live UPLOAD_ERROR must report status == "UPLOAD_DEGRADED"
         and upload_blackout_detected is True (uploaded_live_count == 0).
      3. Legitimate dry-run/offline mode (live_upload=False) preserves status == "PASS".
    """
    vf_mod = _require_video_factory_module()
    YouTubeQuotaGovernor = vf_mod.YouTubeQuotaGovernor
    run_autonomous_video_pipeline = vf_mod.run_autonomous_video_pipeline

    repo_dir = tmp_path / "lienbond"
    dist_dir = repo_dir / "dist"
    videos_dir = dist_dir / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)

    tools_list = [
        {"slug": f"lien-deadline-tool-{i:02d}", "title": f"State {i:02d} Mechanics Lien Deadline Calculator"}
        for i in range(1, 15)
    ]
    for tool in tools_list:
        slug = tool["slug"]
        t_dir = dist_dir / "tools" / slug
        t_dir.mkdir(parents=True, exist_ok=True)
        (t_dir / "index.html").write_text(
            f"<!DOCTYPE html><html><head><title>{tool['title']}</title></head>"
            f"<body><main><h1>{tool['title']}</h1></main></body></html>",
            encoding="utf-8",
        )
        # Seed pre-rendered valid-sized MP4 assets on disk
        (videos_dir / f"{slug}.mp4").write_bytes(b"\x00" * 65536)

    gov = YouTubeQuotaGovernor(
        ledger_path=repo_dir / ".agy" / "youtube_quota_ledger.json",
        upload_log_path=repo_dir / ".agy" / "upload_log.json",
    )

    def _always_fail_upload(**kwargs):
        return {
            "status": "UPLOAD_ERROR",
            "slug": kwargs["slug"],
            "property_id": kwargs["property_id"],
            "error": "OAuth token expired (HTTP 401)",
            "quota_units_used": 0,
        }

    with patch("pseofactory.video_factory.upload_tool_video_to_youtube", side_effect=_always_fail_upload):
        blackout_tel = run_autonomous_video_pipeline(
            property_id="lienbond",
            tools=tools_list,
            dist_dir=dist_dir,
            repo_root=repo_dir,
            max_renders=0,
            synthesize_missing=False,
            live_upload=True,
            quota_governor=gov,
        )

    assert blackout_tel["status"] == "UPLOAD_BLACKOUT"
    assert blackout_tel["status"] != "PASS"
    assert blackout_tel["upload_blackout_detected"] is True
    assert blackout_tel["upload_error_count"] == 14
    assert blackout_tel["attempted_uploads"] == 14
    assert blackout_tel["uploaded_live_count"] == 0
    assert blackout_tel["stages"]["4_youtube_distribution"]["status"] == "UPLOAD_BLACKOUT"
    assert blackout_tel["stages"]["4_youtube_distribution"]["upload_error_count"] == 14
    assert blackout_tel["stages"]["4_youtube_distribution"]["attempted_uploads"] == 14

    # Case 2: Prior idempotent uploads exist alongside new live UPLOAD_ERROR -> UPLOAD_DEGRADED
    def _mixed_idempotent_and_error(**kwargs):
        if kwargs["slug"].endswith("-01"):
            return {
                "status": "ALREADY_UPLOADED_IDEMPOTENT",
                "slug": kwargs["slug"],
                "property_id": kwargs["property_id"],
                "video_id": "yt_existing_01",
                "quota_units_used": 0,
            }
        return _always_fail_upload(**kwargs)

    with patch("pseofactory.video_factory.upload_tool_video_to_youtube", side_effect=_mixed_idempotent_and_error):
        degraded_tel = run_autonomous_video_pipeline(
            property_id="lienbond",
            tools=tools_list[:2],
            dist_dir=dist_dir,
            repo_root=repo_dir,
            max_renders=0,
            synthesize_missing=False,
            live_upload=True,
            quota_governor=gov,
        )

    assert degraded_tel["status"] == "UPLOAD_DEGRADED"
    assert degraded_tel["status"] != "PASS"
    assert degraded_tel["upload_blackout_detected"] is True
    assert degraded_tel["upload_error_count"] == 1
    assert degraded_tel["attempted_uploads"] == 1
    assert degraded_tel["idempotent_uploaded_count"] == 1

    # Case 3: Dry-run / offline (live_upload=False) preserves PASS
    with patch(
        "pseofactory.video_factory.probe_media_file",
        return_value={"valid": True, "has_video": True, "has_audio": True, "size_bytes": 65536},
    ):
        dry_tel = run_autonomous_video_pipeline(
            property_id="lienbond",
            tools=tools_list[:2],
            dist_dir=dist_dir,
            repo_root=repo_dir,
            max_renders=0,
            synthesize_missing=False,
            live_upload=False,
            quota_governor=gov,
        )
    assert dry_tel["status"] == "PASS"
    assert dry_tel["upload_blackout_detected"] is False
    assert dry_tel["upload_error_count"] == 0



