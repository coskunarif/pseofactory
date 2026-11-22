"""
Wave 4: Social Distribution Truth regression suite (100% synthetic, CI-portable).
Proves:
  1. LienBond dispatch preserves 100% of ProfitHelm's 29 LinkedIn queue entries in a synthetic tmp_path queue.
  2. All 12 stale profithelm.com URLs and all 14 foreign company_id "143884102" entries in a synthetic
     14-entry LienBond broadcast_ledger.json self-heal cleanly (in both distributor.py and qualification.py).
  3. Honest channel status taxonomy (LIVE_PUBLISHED, LOCAL_DRAFT_ONLY, BLOCKED_ADMIN_ACCESS,
     POLICY_DISABLED, UPLOAD_ERROR) and truthful all_three_platforms_publicly_verifiable == False
     whenever LinkedIn, Facebook, and YouTube are not all live.
  4. Synthetic 50+ tenant ("newco") running dispatch_to_distribution_lead and export_all_syndication_files
     leaks zero "143884102", zero "106482196", and zero "profithelm.com" anywhere in prioritized_queue,
     all_assets, directory_manifest.json, or broadcast_ledger.json.
  5. Existing broadcast_ledger.json youtube_has_captions / youtube_has_pinned_comment flags are preserved
     for verified video_ids when youtube_pipeline_telemetry.json omits them, and verification_status
     truthfully distinguishes PUBLIC_VIDEOS_CAPTIONS_AND_COMMENTS_VERIFIED vs LIVE_PUBLISHED.
  6. _sync_linkedin_company_queue uses sidecar lock + atomic replace with zero leftover temp files.
  7. Zero live writes to /home/ubuntuadmin/projects/arif-cli/social/linkedin-toolkit/data/queue.json during pytest.

Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

from pseofactory import distributor as dist_mod
from pseofactory.qualification import _clean_syndication_directories_and_ledgers


LIVE_QUEUE_PATH = Path("/home/ubuntuadmin/projects/arif-cli/social/linkedin-toolkit/data/queue.json")

_SYNTHETIC_LIENBOND_SLUGS: List[str] = [
    "bid-bond-calculator",
    "performance-and-payment-bond-cost-calculator",
    "miller-act-performance-and-payment-bond-premium-calculator",
    "contractor-license-bond-cost-calculator-by-credit-score",
    "contractor-lien-release-statutory-matrix-by-state",
    "california-texas-florida-preliminary-notice-deadline-calculator",
    "commercial-construction-retainage-interest-penalty-calculator-by-state",
    "workers-compensation-class-code-rate-calculator-by-state",
    "emr-experience-modification-rate-impact-calculator",
    "builders-risk-insurance-cost-calculator",
    "subcontractor-default-insurance-vs-surety-bond-calculator",
    "davis-bacon-certified-payroll-fringe-benefit-calculator",
    "general-liability-contractor-insurance-cost-calculator",
    "surety-bond-indemnity-working-capital-capacity-calculator",
]


def _build_synthetic_linkedin_queue() -> List[Dict[str, Any]]:
    """Deterministic 65-entry queue: 29 profithelm, 23 prexvo, 13 gainhelm."""
    items: List[Dict[str, Any]] = []
    for idx in range(29):
        items.append(
            {
                "slug": f"ph-tool-{idx:02d}",
                "property_id": "profithelm",
                "company_id": "143884102",
                "priority_score": 60.0 - idx * 0.1,
                "text": f"ProfitHelm deterministic benchmark {idx}",
            }
        )
    for idx in range(23):
        items.append(
            {
                "slug": f"px-tool-{idx:02d}",
                "property_id": "prexvo",
                "company_id": "106482194",
                "priority_score": 55.0 - idx * 0.1,
                "text": f"Prexvo deterministic benchmark {idx}",
            }
        )
    for idx in range(13):
        items.append(
            {
                "slug": f"gh-tool-{idx:02d}",
                "property_id": "gainhelm",
                "company_id": "106482195",
                "priority_score": 50.0 - idx * 0.1,
                "text": f"GainHelm deterministic benchmark {idx}",
            }
        )
    return items


def _seed_lienbond_contaminated_ledger(target_ledger: Path) -> List[Dict[str, Any]]:
    """Deterministic 14-entry contaminated LienBond ledger (12 profithelm.com URLs, 14 company_id 143884102)."""
    target_ledger.parent.mkdir(parents=True, exist_ok=True)
    entries: List[Dict[str, Any]] = []
    for idx, slug in enumerate(_SYNTHETIC_LIENBOND_SLUGS):
        row: Dict[str, Any] = {
            "slug": slug,
            "timestamp": "2026-11-13T00:36:38+00:00",
            "mode": "SYNDICATED_STAGED",
            "company_id": "143884102",
            "priority_score": 60.0 - idx * 0.1,
            "post_url": f"https://lienbond.com/tools/{slug}/?payroll=500000&class_rate=8.42&emr=0.95",
            "dispatches": {
                "x": "SUCCESS",
                "linkedin": "BLOCKED_ADMIN_ACCESS_DENIED",
                "facebook": "STAGED",
                "youtube": "QUOTA_DEFERRED_STAGED",
                "ghost": "STAGED",
                "github_gist": "STAGED",
            },
            "metrics": {
                "linkedin_access_status": "ADMIN_ACCESS_DENIED",
                "linkedin_urn": None,
                "facebook_visibility": "staged",
                "facebook_first_comment_verified": False,
            },
        }
        if idx >= 2:
            row["url"] = f"https://profithelm.com/tools/{slug}/?income=125000&status=single&state=CA"
        entries.append(row)
    target_ledger.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    return entries


def test_lienbond_dispatch_preserves_all_profithelm_linkedin_queue_entries(tmp_path: Path) -> None:
    """
    LienBond has no configured LinkedIn company_id (must resolve to "", never "143884102").
    Dispatching LienBond against a synthetic 65-entry tmp_path queue (29 ProfitHelm, 23 Prexvo, 13 GainHelm)
    must leave 100% of ProfitHelm, Prexvo, and GainHelm entries untouched.
    """
    assert dist_mod._resolve_tenant_linkedin_company_id("profithelm") == "143884102"
    assert dist_mod._resolve_tenant_linkedin_company_id("prexvo") == "106482194"
    assert dist_mod._resolve_tenant_linkedin_company_id("gainhelm") == "106482195"
    assert dist_mod._resolve_tenant_linkedin_company_id("lienbond") == ""
    assert dist_mod._resolve_tenant_linkedin_company_id("unconfigured_tenant_99") == ""

    tmp_queue = tmp_path / "linkedin_queue.json"
    seeded_queue = _build_synthetic_linkedin_queue()
    tmp_queue.write_text(json.dumps(seeded_queue, indent=2), encoding="utf-8")

    before_queue = json.loads(tmp_queue.read_text(encoding="utf-8"))
    before_ph = [x for x in before_queue if dist_mod._normalize_property_id(x.get("property_id")) == "profithelm"]
    before_px = [x for x in before_queue if dist_mod._normalize_property_id(x.get("property_id")) == "prexvo"]
    before_gh = [x for x in before_queue if dist_mod._normalize_property_id(x.get("property_id")) == "gainhelm"]
    assert len(before_ph) == 29
    assert len(before_px) == 23
    assert len(before_gh) == 13

    lb_repo = tmp_path / "lienbond"
    (lb_repo / "dist").mkdir(parents=True)
    _seed_lienbond_contaminated_ledger(lb_repo / ".agy" / "broadcast_ledger.json")

    res = dist_mod.dispatch_to_distribution_lead(
        run_id="wave4-lb-queue-preserve",
        property_id="lienbond",
        dry_run=False,
        dist_dir=lb_repo / "dist",
        tools=[
            {
                "slug": "bid-bond-calculator",
                "title": "Bid Bond Calculator",
            }
        ],
        synthesize_videos=False,
        live_video_upload=False,
        linkedin_queue_path=tmp_queue,
    )

    assert res["company_id"] == ""
    assert "143884102" not in json.dumps(res["release_commands"])
    assert "143884102" not in json.dumps(res["owner_calls"])
    assert "106482196" not in json.dumps(res["prioritized_queue"])
    assert "106482196" not in json.dumps(res["all_assets"])

    after_queue = json.loads(tmp_queue.read_text(encoding="utf-8"))
    after_ph = [x for x in after_queue if dist_mod._normalize_property_id(x.get("property_id")) == "profithelm"]
    after_px = [x for x in after_queue if dist_mod._normalize_property_id(x.get("property_id")) == "prexvo"]
    after_gh = [x for x in after_queue if dist_mod._normalize_property_id(x.get("property_id")) == "gainhelm"]
    after_lb = [x for x in after_queue if dist_mod._normalize_property_id(x.get("property_id")) == "lienbond"]

    assert len(after_ph) == 29
    assert len(after_px) == 23
    assert len(after_gh) == 13
    assert len(after_lb) == 0
    assert after_queue == before_queue


def test_linkedin_queue_sync_filters_by_property_id_not_company_id_and_uses_atomic_locked_write(tmp_path: Path) -> None:
    """
    Even if two distinct properties somehow shared a company_id in queue.json,
    _sync_linkedin_company_queue filters strictly by property_id, preserves all other tenants,
    acquires a sidecar lock file, and leaves zero stray temp files behind.
    """
    tmp_queue = tmp_path / "shared_queue.json"
    seeded = [
        {"slug": "ph-1", "property_id": "profithelm", "company_id": "143884102", "priority_score": 70.0},
        {"slug": "ph-2", "property_id": "profithelm", "company_id": "143884102", "priority_score": 65.0},
        {"slug": "other-tenant-1", "property_id": "other_tenant", "company_id": "143884102", "priority_score": 60.0},
        {"slug": "px-1", "property_id": "prexvo", "company_id": "106482194", "priority_score": 55.0},
    ]
    tmp_queue.write_text(json.dumps(seeded, indent=2), encoding="utf-8")

    sync_res = dist_mod._sync_linkedin_company_queue(
        li_queue_path=tmp_queue,
        norm_prop="profithelm",
        corp_company_id="143884102",
        li_admin_status="VERIFIED_COMPANY_ADMIN",
        prioritized_queue=[{"slug": "irs-2027-tax-brackets", "priority_score": 80.0}],
        all_assets={
            "irs-2027-tax-brackets": {
                "linkedin": {
                    "content": "Deterministic 2027 bracket proof.",
                    "teaser_content": "2027 bracket proof.",
                    "first_comment": "https://profithelm.com/tools/irs-2027-tax-brackets/",
                    "first_comment_url": "https://profithelm.com/tools/irs-2027-tax-brackets/",
                }
            }
        },
    )
    assert sync_res["updated"] is True
    assert (tmp_path / "shared_queue.json.lock").is_file()
    assert list(tmp_path.glob("*.tmp")) == []

    updated = json.loads(tmp_queue.read_text(encoding="utf-8"))
    by_prop: Dict[str, List[Dict[str, Any]]] = {}
    for row in updated:
        by_prop.setdefault(row["property_id"], []).append(row)
    assert len(by_prop["other_tenant"]) == 1
    assert len(by_prop["prexvo"]) == 1
    assert [r["slug"] for r in by_prop["profithelm"]] == ["irs-2027-tax-brackets"]

    # Non-verified tenant (ADMIN_ACCESS_DENIED) is skipped completely
    pre_bytes = tmp_queue.read_bytes()
    skip_res = dist_mod._sync_linkedin_company_queue(
        li_queue_path=tmp_queue,
        norm_prop="prexvo",
        corp_company_id="106482194",
        li_admin_status="ADMIN_ACCESS_DENIED",
        prioritized_queue=[{"slug": "pslf-simulator", "priority_score": 75.0}],
        all_assets={},
    )
    assert skip_res["updated"] is False
    assert tmp_queue.read_bytes() == pre_bytes


def test_lienbond_broadcast_ledger_self_heals_foreign_urls_and_company_ids(tmp_path: Path) -> None:
    """
    Seeds a 100% synthetic 14-entry contaminated LienBond broadcast_ledger.json
    (12 stale profithelm.com `url` fields, 14 foreign company_id "143884102" values,
    and a stale unverified facebook_permalink) in tmp_path and proves BOTH distributor.py
    and qualification.py self-heal every entry cleanly.
    """
    # Part A: Self-heal via dispatch_to_distribution_lead
    lb_repo = tmp_path / "lienbond_dist"
    (lb_repo / "dist").mkdir(parents=True)
    ledger_path = lb_repo / ".agy" / "broadcast_ledger.json"
    before_entries = _seed_lienbond_contaminated_ledger(ledger_path)
    before_entries[0]["facebook_permalink"] = (
        "https://www.facebook.com/groups/331399459887663/permalink/1092641363763465/"
    )
    before_entries[0].setdefault("dispatches", {})["newsletter"] = "SUCCESS"
    ledger_path.write_text(json.dumps(before_entries, indent=2), encoding="utf-8")

    assert sum(1 for e in before_entries if "profithelm.com" in str(e.get("url", ""))) == 12
    assert sum(1 for e in before_entries if str(e.get("company_id", "")) == "143884102") == 14

    tools_from_ledger = [{"slug": e["slug"], "title": e["slug"].replace("-", " ").title()} for e in before_entries]
    dist_mod.dispatch_to_distribution_lead(
        run_id="wave4-lb-self-heal",
        property_id="lienbond",
        dry_run=False,
        dist_dir=lb_repo / "dist",
        tools=tools_from_ledger,
        synthesize_videos=False,
        live_video_upload=False,
    )

    healed = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert len(healed) == 14
    for entry in healed:
        assert entry["company_id"] is None, f"Foreign company_id leaked on {entry['slug']}: {entry['company_id']}"
        assert "profithelm.com" not in str(entry.get("post_url", "")).lower()
        assert "lienbond.com" in str(entry.get("post_url", "")).lower()
        if "url" in entry:
            assert "profithelm.com" not in str(entry["url"]).lower()
            assert "lienbond.com" in str(entry["url"]).lower()
        assert "facebook_permalink" not in entry
        disp = entry["dispatches"]
        assert disp["x"] == dist_mod.CHANNEL_STATUS_POLICY_DISABLED
        assert disp["linkedin"] == dist_mod.CHANNEL_STATUS_BLOCKED_ADMIN_ACCESS
        assert disp["facebook"] == dist_mod.CHANNEL_STATUS_LOCAL_DRAFT_ONLY
        assert disp["ghost"] == dist_mod.CHANNEL_STATUS_LOCAL_DRAFT_ONLY
        assert disp["github_gist"] == dist_mod.CHANNEL_STATUS_LOCAL_DRAFT_ONLY
        if "newsletter" in disp:
            assert disp["newsletter"] == dist_mod.CHANNEL_STATUS_LOCAL_DRAFT_ONLY
        assert "SUCCESS" not in disp.values()
        assert entry["mode"] == "SYNDICATED_STAGED"

    # Part B: Self-heal via qualification._clean_syndication_directories_and_ledgers
    lb_repo_q = tmp_path / "lienbond_qual"
    (lb_repo_q / ".agy").mkdir(parents=True)
    qual_ledger_path = lb_repo_q / ".agy" / "broadcast_ledger.json"
    before_q = _seed_lienbond_contaminated_ledger(qual_ledger_path)
    before_q[0]["post_url"] = "https://profithelm.com/tools/wrong-domain/"
    qual_ledger_path.write_text(json.dumps(before_q, indent=2), encoding="utf-8")

    cleaned_cnt = _clean_syndication_directories_and_ledgers(lb_repo_q, "lienbond", set())
    assert cleaned_cnt >= 1
    healed_q = json.loads(qual_ledger_path.read_text(encoding="utf-8"))
    assert len(healed_q) == 14
    for entry in healed_q:
        assert "profithelm.com" not in str(entry.get("post_url", "")).lower()
        assert "lienbond.com" in str(entry.get("post_url", "")).lower()
        if "url" in entry:
            assert "profithelm.com" not in str(entry["url"]).lower()
            assert "lienbond.com" in str(entry["url"]).lower()
        assert entry.get("company_id") is None


def test_honest_channel_taxonomy_and_delivery_summary_partitions_all_channels(tmp_path: Path) -> None:
    """
    Verifies all 5 canonical status constants across broadcast_ledger.json,
    verify_cross_platform_public_visibility, and dispatch_to_distribution_lead's
    channel_delivery_summary (including UPLOAD_ERROR and SYNDICATED_VERIFIED vs SYNDICATED_STAGED).
    """
    assert dist_mod.CHANNEL_STATUS_LIVE_PUBLISHED == "LIVE_PUBLISHED"
    assert dist_mod.CHANNEL_STATUS_LOCAL_DRAFT_ONLY == "LOCAL_DRAFT_ONLY"
    assert dist_mod.CHANNEL_STATUS_BLOCKED_ADMIN_ACCESS == "BLOCKED_ADMIN_ACCESS"
    assert dist_mod.CHANNEL_STATUS_POLICY_DISABLED == "POLICY_DISABLED"
    assert dist_mod.CHANNEL_STATUS_UPLOAD_ERROR == "UPLOAD_ERROR"

    gh_repo = tmp_path / "gainhelm_err"
    (gh_repo / "dist").mkdir(parents=True)
    (gh_repo / ".agy").mkdir(parents=True)
    (gh_repo / ".agy" / "broadcast_ledger.json").write_text(
        json.dumps(
            [
                {
                    "slug": "soc-2-audit-cost-calculator",
                    "company_id": "106482195",
                    "post_url": "https://gainhelm.com/tools/soc-2-audit-cost-calculator/",
                    "dispatches": {"x": "SUCCESS", "linkedin": "BLOCKED_ADMIN_ACCESS_DENIED"},
                    "metrics": {"linkedin_access_status": "ADMIN_ACCESS_DENIED"},
                }
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    fake_vf_error = {
        "status": "UPLOAD_BLACKOUT",
        "property_id": "gainhelm",
        "upload_error_count": 1,
        "upload_blackout_detected": True,
        "per_slug_dispatch_status": {"soc-2-audit-cost-calculator": "UPLOAD_ERROR"},
        "stages": {
            "4_youtube_distribution": {
                "results": {
                    "soc-2-audit-cost-calculator": {
                        "property_id": "gainhelm",
                        "slug": "soc-2-audit-cost-calculator",
                        "status": "UPLOAD_ERROR",
                        "error": "quotaExceeded",
                    }
                }
            }
        },
    }
    with patch("pseofactory.video_factory.run_autonomous_video_pipeline", return_value=fake_vf_error):
        res_err = dist_mod.dispatch_to_distribution_lead(
            run_id="wave4-gh-upload-error",
            property_id="gainhelm",
            dry_run=False,
            dist_dir=gh_repo / "dist",
            tools=[{"slug": "soc-2-audit-cost-calculator", "title": "SOC 2 Audit Cost Calculator"}],
            synthesize_videos=False,
            live_video_upload=False,
        )

    assert res_err["status"] == "SUCCESS"
    assert res_err["public_visibility_verification"]["all_three_platforms_publicly_verifiable"] is False
    assert res_err["public_visibility_verification"]["channel_statuses"] == {
        "linkedin": "BLOCKED_ADMIN_ACCESS",
        "facebook": "LOCAL_DRAFT_ONLY",
        "youtube": "UPLOAD_ERROR",
    }
    summary = res_err["channel_delivery_summary"]
    assert summary["total_channels"] == len(res_err["channels"])
    assert sum(summary["counts"].values()) == len(res_err["channels"])
    assert summary["policy_disabled"] == ["x"]
    assert summary["blocked_admin_access"] == ["linkedin"]
    assert summary["upload_error"] == ["youtube"]
    assert summary["live_published"] == []
    assert "facebook" in summary["local_draft_only"]
    assert "ghost" in summary["local_draft_only"]
    assert "github_gist" in summary["local_draft_only"]

    ledger_err = json.loads((gh_repo / ".agy" / "broadcast_ledger.json").read_text(encoding="utf-8"))
    assert ledger_err[0]["mode"] == "SYNDICATED_STAGED"
    assert ledger_err[0]["dispatches"]["x"] == "POLICY_DISABLED"
    assert ledger_err[0]["dispatches"]["linkedin"] == "BLOCKED_ADMIN_ACCESS"
    assert ledger_err[0]["dispatches"]["youtube"] == "UPLOAD_ERROR"
    assert ledger_err[0]["dispatches"]["facebook"] == "LOCAL_DRAFT_ONLY"

    # YouTube ALREADY_UPLOADED_IDEMPOTENT with video_id -> LIVE_PUBLISHED + SYNDICATED_VERIFIED
    # while all_three_platforms_publicly_verifiable remains False when LI & FB are not live
    fake_vf_live = {
        "status": "PASS",
        "property_id": "gainhelm",
        "upload_error_count": 0,
        "per_slug_dispatch_status": {"soc-2-audit-cost-calculator": "ALREADY_UPLOADED_IDEMPOTENT"},
        "stages": {
            "4_youtube_distribution": {
                "results": {
                    "soc-2-audit-cost-calculator": {
                        "property_id": "gainhelm",
                        "slug": "soc-2-audit-cost-calculator",
                        "status": "ALREADY_UPLOADED_IDEMPOTENT",
                        "video_id": "5zH1GcBqr-E",
                        "video_url": "https://www.youtube.com/watch?v=5zH1GcBqr-E",
                    }
                }
            }
        },
    }
    with patch("pseofactory.video_factory.run_autonomous_video_pipeline", return_value=fake_vf_live):
        res_live = dist_mod.dispatch_to_distribution_lead(
            run_id="wave4-gh-yt-live",
            property_id="gainhelm",
            dry_run=False,
            dist_dir=gh_repo / "dist",
            tools=[{"slug": "soc-2-audit-cost-calculator", "title": "SOC 2 Audit Cost Calculator"}],
            synthesize_videos=False,
            live_video_upload=False,
        )

    assert res_live["public_visibility_verification"]["all_three_platforms_publicly_verifiable"] is False
    assert res_live["public_visibility_verification"]["verified_live_platforms"] == ["youtube"]
    assert res_live["channel_delivery_summary"]["live_published"] == ["youtube"]
    # Captions/comments were not verified in fake_vf_live -> verification_status is LIVE_PUBLISHED (not over-claimed)
    assert res_live["public_visibility_verification"]["platforms"]["youtube"]["verification_status"] == "LIVE_PUBLISHED"
    ledger_live = json.loads((gh_repo / ".agy" / "broadcast_ledger.json").read_text(encoding="utf-8"))
    assert ledger_live[0]["mode"] == "SYNDICATED_VERIFIED"
    assert ledger_live[0]["dispatches"]["youtube"] == "LIVE_PUBLISHED"
    assert ledger_live[0]["dispatches"]["x"] == "POLICY_DISABLED"


def test_youtube_caption_and_comment_flags_preserved_from_existing_broadcast_ledger(tmp_path: Path) -> None:
    """
    When youtube_pipeline_telemetry.json omits has_captions / has_pinned_comment for a verified
    video_id, verify_cross_platform_public_visibility preserves those verified flags from
    existing broadcast_ledger.json rather than downgrading them to False.
    """
    px_repo = tmp_path / "prexvo_yt_meta"
    (px_repo / ".agy").mkdir(parents=True)
    (px_repo / ".agy" / "broadcast_ledger.json").write_text(
        json.dumps(
            [
                {
                    "slug": "student-loan-refinance-break-even-calculator",
                    "company_id": "106482194",
                    "post_url": "https://prexvo.com/tools/student-loan-refinance-break-even-calculator/",
                    "youtube_video_id": "RskQpr5KB6w",
                    "metrics": {
                        "linkedin_access_status": "ADMIN_ACCESS_DENIED",
                        "youtube_video_id": "RskQpr5KB6w",
                        "youtube_has_captions": True,
                        "youtube_has_pinned_comment": True,
                        "youtube_view_count": 42,
                        "youtube_comment_count": 3,
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
                            "student-loan-refinance-break-even-calculator": {
                                "property_id": "prexvo",
                                "slug": "student-loan-refinance-break-even-calculator",
                                "status": "ALREADY_UPLOADED_IDEMPOTENT",
                                "video_id": "RskQpr5KB6w",
                                "video_url": "https://www.youtube.com/watch?v=RskQpr5KB6w",
                            }
                        }
                    }
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    vis = dist_mod.verify_cross_platform_public_visibility(property_id="prexvo", repo_dir=px_repo)
    yt_tel = vis["platforms"]["youtube"]
    assert yt_tel["channel_status"] == "LIVE_PUBLISHED"
    assert yt_tel["verification_status"] == "PUBLIC_VIDEOS_CAPTIONS_AND_COMMENTS_VERIFIED"
    assert yt_tel["verified_public_videos_count"] == 1
    v0 = yt_tel["verified_public_videos"][0]
    assert v0["video_id"] == "RskQpr5KB6w"
    assert v0["has_captions"] is True
    assert v0["has_pinned_comment"] is True
    assert v0["view_count"] == 42
    assert v0["comment_count"] == 3


def test_newco_50plus_tenant_dispatch_and_export_have_zero_profithelm_or_lienbond_leaks(tmp_path: Path) -> None:
    """
    Proves 50+ tenant isolation for BOTH unregistered ("unregistered_newco") and declaratively
    registered ("newco", with empty linkedin_company_id) tenants:
    zero "143884102", zero "106482196", and zero "profithelm.com" anywhere in
    prioritized_queue, all_assets, generate_linkedin_post, directory_manifest.json,
    or broadcast_ledger.json.
    """
    from pseofactory.tenant_facts import (
        DeclarativeTenantContract,
        StatutoryTruthRule,
        register_declarative_tenant,
        unregister_declarative_tenant,
    )

    # 1. Unregistered tenant checks (never inherits ProfitHelm defaults)
    unreg_repo = tmp_path / "unregistered_newco"
    unreg_synd = unreg_repo / "syndication"
    unreg_synd.mkdir(parents=True)
    unreg_tools = [{"slug": "unreg-margin-calculator", "title": "Unreg Margin Calculator"}]

    assert dist_mod._resolve_tenant_linkedin_company_id("unregistered_newco") == ""
    unreg_vis = dist_mod.verify_cross_platform_public_visibility(
        property_id="unregistered_newco",
        repo_dir=unreg_repo,
    )
    assert unreg_vis["property_id"] == "unregistered_newco"
    assert unreg_vis["all_three_platforms_publicly_verifiable"] is False
    assert unreg_vis["verified_live_platforms"] == []
    assert unreg_vis["platforms"]["linkedin"]["company_id"] == ""
    assert unreg_vis["platforms"]["linkedin"]["channel_status"] == "BLOCKED_ADMIN_ACCESS"

    unreg_pq = dist_mod.prioritize_distribution_queue_by_referral_yield(
        property_id="unregistered_newco",
        tools=unreg_tools,
        repo_root=unreg_repo,
    )
    assert unreg_pq[0]["company_id"] == ""
    assert "143884102" not in json.dumps(unreg_pq)
    assert "106482196" not in json.dumps(unreg_pq)

    unreg_li = dist_mod.generate_linkedin_company_post("unreg-margin-calculator", property_id="unregistered_newco")
    assert unreg_li["company_id"] == ""
    assert "143884102" not in json.dumps(unreg_li)

    unreg_assets = dist_mod.generate_all_distribution_assets(
        tools=unreg_tools,
        property_id="unregistered_newco",
    )
    unreg_assets_blob = json.dumps(unreg_assets)
    assert "143884102" not in unreg_assets_blob
    assert "106482196" not in unreg_assets_blob
    assert "profithelm.com" not in unreg_assets_blob.lower()

    # 2. Declaratively registered 50+ tenant ("newco") with empty linkedin_company_id:
    #    full dispatch_to_distribution_lead passes truth-store audit with zero leaks
    newco_repo = tmp_path / "newco"
    (newco_repo / "dist").mkdir(parents=True)
    synd_out = newco_repo / "syndication"
    synd_out.mkdir(parents=True)
    newco_tools = [{"slug": "newco-margin-calculator", "title": "NewCo Margin Calculator"}]

    newco_contract = DeclarativeTenantContract(
        property_id="newco",
        brand_name="NewCo",
        domain="newco.com",
        repo_dir_name="newco",
        package_name="newco",
        dist_dir="dist",
        linkedin_company_id="",
        cloudflare_zone_id="22222222222222222222222222222222",
        cloudflare_pages_cname_target="newco.pages.dev",
        entity_type="Commercial Margin and Unit Economics Simulation Engine",
        statutory_truth=StatutoryTruthRule(
            tenant_id="newco",
            statutory_citations={"irc_title_26": "IRC Title 26"},
            limits_and_thresholds={},
        ),
        statutory_intent_tokens=("newco margin",),
        category_seed_taxonomy={"margin": ("newco margin calculator",)},
        default_core_tools=({"slug": "newco-margin-calculator", "primary_keyword": "newco margin calculator"},),
        cannibalizing_clone_consolidation_map={},
        flagship_anchor_slugs=("newco-margin-calculator",),
        video_branding={
            "brand_name": "NewCo",
            "domain": "newco.com",
            "canonical_base": "https://newco.com",
            "badge_text": "NEWCO.COM | MARGIN ENGINE",
            "verification_pill": "VERIFIED MODEL",
            "bg_rgb": (15, 23, 42),
            "card_rgb": (30, 41, 59),
            "accent_rgb": (56, 189, 248),
            "accent_hex": "#38bdf8",
            "voice": "en-US-ChristopherNeural",
        },
        smoke_probe_query="newco margin calculator",
        smoke_foreign_query="save plan student loan repayment calculator",
        default_cpc_usd=10.0,
        default_erpm_usd=80.0,
        default_calculator_fallback_title="NewCo Margin Calculator",
        default_heading_fallback_label="Margin Calculator",
        default_sample_query="newco margin calculator",
        default_sample_slug="newco-margin-calculator",
        top_modifier_family="newco-margin-calculator",
        publisher_entity_label="NewCo Research Group",
        cross_tenant_own_markers=("newco.com", "newco"),
    )

    try:
        register_declarative_tenant(newco_contract)
        res = dist_mod.dispatch_to_distribution_lead(
            run_id="wave4-newco-50plus-isolation",
            property_id="newco",
            dry_run=False,
            dist_dir=newco_repo / "dist",
            tools=newco_tools,
            synthesize_videos=False,
            live_video_upload=False,
        )

        assert res["company_id"] == ""
        pq_blob = json.dumps(res["prioritized_queue"])
        assets_blob = json.dumps(res["all_assets"])
        ledger_blob = (newco_repo / ".agy" / "broadcast_ledger.json").read_text(encoding="utf-8")

        for label, blob in (
            ("prioritized_queue", pq_blob),
            ("all_assets", assets_blob),
            ("broadcast_ledger", ledger_blob),
        ):
            assert "143884102" not in blob, f"Leaked 143884102 into newco {label}"
            assert "106482196" not in blob, f"Leaked 106482196 into newco {label}"
            assert "profithelm.com" not in blob.lower(), f"Leaked profithelm.com into newco {label}"

        ledger_rows = json.loads(ledger_blob)
        assert len(ledger_rows) == 1
        assert ledger_rows[0]["company_id"] is None
        assert "newco.com" in ledger_rows[0]["post_url"]

        dist_mod.export_all_syndication_files(
            output_dir=synd_out,
            tools=newco_tools,
            property_id="newco",
        )
        dm = json.loads((synd_out / "directory_manifest.json").read_text(encoding="utf-8"))
        dm_blob = json.dumps(dm)
        assert "143884102" not in dm_blob
        assert "106482196" not in dm_blob
        assert "profithelm.com" not in dm_blob.lower()
        assert "linkedin_company_url" not in dm["base_manifest"]["social"]
    finally:
        unregister_declarative_tenant("newco")


def test_zero_live_writes_to_arif_cli_linkedin_queue_during_pytest(tmp_path: Path) -> None:
    """
    During pytest, calling dispatch_to_distribution_lead without an explicit tmp_path
    linkedin_queue_path must NEVER write to /home/ubuntuadmin/projects/arif-cli/.../queue.json.
    """
    assert dist_mod._is_live_workspace_path(LIVE_QUEUE_PATH) is True
    existed_before = LIVE_QUEUE_PATH.is_file()
    before_sha = hashlib.sha256(LIVE_QUEUE_PATH.read_bytes()).hexdigest() if existed_before else None
    before_mtime = LIVE_QUEUE_PATH.stat().st_mtime_ns if existed_before else None

    ph_repo = tmp_path / "profithelm_isolated"
    (ph_repo / "dist").mkdir(parents=True)
    (ph_repo / ".agy").mkdir(parents=True)
    (ph_repo / ".agy" / "broadcast_ledger.json").write_text(
        json.dumps(
            [
                {
                    "slug": "irs-2027-tax-brackets",
                    "company_id": "143884102",
                    "post_url": "https://profithelm.com/tools/irs-2027-tax-brackets/",
                    "metrics": {
                        "linkedin_access_status": "VERIFIED_COMPANY_ADMIN",
                        "linkedin_urn": "urn:li:activity:7518942436178464768",
                    },
                }
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    dist_mod.dispatch_to_distribution_lead(
        run_id="wave4-no-live-queue-write",
        property_id="profithelm",
        dry_run=False,
        dist_dir=ph_repo / "dist",
        tools=[{"slug": "irs-2027-tax-brackets", "title": "IRS 2027 Tax Brackets"}],
        synthesize_videos=False,
        live_video_upload=False,
    )

    assert LIVE_QUEUE_PATH.is_file() == existed_before
    if existed_before:
        assert hashlib.sha256(LIVE_QUEUE_PATH.read_bytes()).hexdigest() == before_sha
        assert LIVE_QUEUE_PATH.stat().st_mtime_ns == before_mtime
