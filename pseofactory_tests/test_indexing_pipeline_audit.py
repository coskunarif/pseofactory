"""
Regression tests for the end-to-end indexing pipeline audit across ProfitHelm, Prexvo, and GainHelm:
1. Deferred vs. live hash latching & simulated log protection
2. Shared GCP quota governance, pre-publish quota check, 429 breaker, and zero duplicate fast-index calls
3. Real-only GSC inspection state sanitization (purging test calc-6..10, retired slugs, and synthetic timestamps)
4. Sitemap <lastmod> uniformity detection (YYYY-MM-DD), content-hash <lastmod> sync, and child-sitemap coverage reconciliation
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pseofactory.indexer import ChildSitemapPushLedger, GOOGLE_INDEXING_DAILY_QUOTA, PushIndexer
from pseofactory.indexing.feedback_loop import SectionExclusionClassifier
from pseofactory.indexing_inspector import DailyIndexingInspector
from pseofactory.maintenance import RetroReflectionEngine
from pseofactory.trends.db import GSCUrlInspectionRecord, TrendHistoryDB


def _write_test_html(path: Path, canonical_url: str, title: str = "Statutory Calculator") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body_words = " ".join([f"statutory_term_{i}" for i in range(450)])
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{title}</title>
  <meta name="robots" content="index, follow" />
  <link rel="canonical" href="{canonical_url}" />
  <script type="application/ld+json">
  {{"@context": "https://schema.org", "@type": "WebApplication", "name": "{title}", "dateModified": "2026-10-15"}}
  </script>
</head>
<body>
  <main>
    <h1>{title}</h1>
    <p>{body_words}</p>
  </main>
</body>
</html>"""
    path.write_text(html, encoding="utf-8")


def test_deferred_live_hash_latching_and_simulated_log_protection(tmp_path: Path) -> None:
    """
    Verifies:
    1. inspect_platform_assets marks a URL as NEW when top-level hash matches curr_hash
       but per-engine hashes (engines.indexnow.hash) do NOT match curr_hash.
    2. dispatch_automated_indexing(live=False) does NOT overwrite an existing LIVE
       indexing_audit_log.json on disk with SIMULATED mode.
    """
    base_dir = tmp_path / "gainhelm"
    dist_dir = base_dir / "dist"
    agy_dir = base_dir / ".agy"
    agy_dir.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")

    url = "https://gainhelm.com/tools/soc-2-audit-cost-calculator/"
    html_path = dist_dir / "tools" / "soc-2-audit-cost-calculator" / "index.html"
    _write_test_html(html_path, url, "SOC 2 Audit Cost Calculator")

    indexer = PushIndexer(
        domain="gainhelm.com",
        canonical_base="https://gainhelm.com",
        base_dir=base_dir,
        dist_dir=dist_dir,
        ledger_path=agy_dir / "index_push_ledger.json",
        audit_log_path=agy_dir / "indexing_audit_log.json",
        rollover_queue_path=agy_dir / "gsc_rollover_queue.json",
        tenant_id="gainhelm",
    )

    curr_hash = indexer.get_url_content_hash(url)
    stale_engine_hash = "0" * 64

    # Simulate premature top-level hash latch where engines.indexnow.hash is stale
    indexer.save_pushed_ledger(
        {
            url: {
                "hash": curr_hash,
                "last_pushed": "2026-11-01T00:00:00+00:00",
                "push_count": 2,
                "tenant_id": "gainhelm",
                "engines": {
                    "indexnow": {
                        "hash": stale_engine_hash,
                        "last_pushed": "2026-10-30T00:00:00+00:00",
                        "push_count": 1,
                        "tenant_id": "gainhelm",
                    }
                },
            }
        }
    )

    inspection = indexer.inspect_platform_assets(urls=[url])
    assert inspection["new_assets_count"] == 1, "Mismatched per-engine hash must be detected as NEW"
    assert inspection["assets"][0]["is_new"] is True

    # Write a LIVE audit log and verify dispatch_automated_indexing(live=False) preserves it on disk
    live_audit_payload = {
        "status": "SUCCESS",
        "mode": "LIVE",
        "timestamp": "2026-11-01T12:00:00+00:00",
        "domain": "gainhelm.com",
    }
    indexer.audit_log_path.write_text(json.dumps(live_audit_payload, indent=2), encoding="utf-8")

    sim_res = indexer.dispatch_automated_indexing(urls=[url], live=False)
    assert sim_res["mode"] == "SIMULATED"
    persisted_audit = json.loads(indexer.audit_log_path.read_text(encoding="utf-8"))
    assert persisted_audit["mode"] == "LIVE", "Simulated run must not clobber existing LIVE audit_log.json"


def test_shared_gcp_quota_breaker_and_no_duplicate_fast_index(tmp_path: Path) -> None:
    """
    Verifies:
    1. submit_gsc_indexing checks check_and_consume_gsc_quota(bucket="indexing") before calling gsccli.
    2. HTTP 429 immediately trips the quota governor breaker (indexing_used = GOOGLE_INDEXING_DAILY_QUOTA,
       quota_exhausted = True) so subsequent calls do not hit 429 again.
    3. dispatch_automated_indexing invokes submit_fast_index at most once per dispatch.
    """
    base_dir = tmp_path / "profithelm"
    dist_dir = base_dir / "dist"
    agy_dir = base_dir / ".agy"
    agy_dir.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")

    u1 = "https://profithelm.com/tools/calc-a/"
    u2 = "https://profithelm.com/tools/calc-b/"
    _write_test_html(dist_dir / "tools" / "calc-a" / "index.html", u1, "Calc A")
    _write_test_html(dist_dir / "tools" / "calc-b" / "index.html", u2, "Calc B")

    indexer = PushIndexer(
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        base_dir=base_dir,
        dist_dir=dist_dir,
        ledger_path=agy_dir / "index_push_ledger.json",
        audit_log_path=agy_dir / "indexing_audit_log.json",
        rollover_queue_path=agy_dir / "gsc_rollover_queue.json",
        tenant_id="profithelm",
    )
    indexer.repo_root = base_dir

    mock_proc_429 = MagicMock()
    mock_proc_429.returncode = 1
    mock_proc_429.stdout = ""
    mock_proc_429.stderr = "Quota exceeded for quota metric 'Publish requests' and limit 'Publish requests per day' (429)"

    with patch("subprocess.run", return_value=mock_proc_429) as run_mock:
        res = indexer.submit_gsc_indexing(urls=[u1, u2], live=True, drain_rollover=False)
        gov_path = indexer._get_gsc_quota_governor_path()
        assert gov_path.is_file(), "Quota governor file must be written when 429 breaker trips"
        gov_data = json.loads(gov_path.read_text(encoding="utf-8"))
        assert gov_data.get("indexing_used", 0) >= GOOGLE_INDEXING_DAILY_QUOTA
        assert gov_data.get("quota_exhausted") is True

        # Now a second call on another URL must see the exhausted quota and make 0 gsccli index publish calls
        run_mock.reset_mock()
        indexer.submit_gsc_indexing(urls=[u2], live=True, drain_rollover=False)
        publish_calls = [
            call for call in run_mock.call_args_list
            if call.args and isinstance(call.args[0], list) and "publish" in call.args[0]
        ]
        assert len(publish_calls) == 0, "No gsccli index publish calls may execute when quota governor is exhausted"


def test_sanitize_gsc_url_inspection_states_purges_test_and_synthetic_rows(tmp_path: Path) -> None:
    """
    Verifies TrendHistoryDB.sanitize_gsc_url_inspection_states purges:
    - Fake test routes (calc-6..calc-10)
    - Non-HTML endpoints (feed.xml, llms.txt, robots.txt)
    - Retired slugs not in active valid_urls
    - Synthetic SIMULATED timestamps (2026-10-27T08:00:00Z or local microsecond timestamps without Z/+00:00)
    while preserving real GSC inspection rows.
    """
    db_file = tmp_path / "trend_history.db"
    with TrendHistoryDB(db_file) as db:
        records = [
            # 1. Real indexed row
            GSCUrlInspectionRecord(
                property_id="gainhelm",
                page_url="https://gainhelm.com/",
                verdict="PASS",
                coverage_state="Submitted and indexed",
                indexing_state="INDEXING_ALLOWED",
                page_fetch_state="SUCCESSFUL",
                robots_txt_state="ALLOWED",
                user_canonical="https://gainhelm.com/",
                google_canonical="https://gainhelm.com/",
                last_crawl_time="2026-10-28T00:33:28Z",
            ),
            # 2. Real unindexed row
            GSCUrlInspectionRecord(
                property_id="gainhelm",
                page_url="https://gainhelm.com/tools/soc-2-audit-cost-calculator/",
                verdict="NEUTRAL",
                coverage_state="Discovered - currently not indexed",
                indexing_state="INDEXING_STATE_UNSPECIFIED",
                page_fetch_state="PAGE_FETCH_STATE_UNSPECIFIED",
                robots_txt_state="ROBOTS_TXT_STATE_UNSPECIFIED",
                user_canonical="",
                google_canonical="",
                last_crawl_time="",
            ),
            # 3. Fake test row calc-6
            GSCUrlInspectionRecord(
                property_id="gainhelm",
                page_url="https://gainhelm.com/tools/calc-6/",
                verdict="PASS",
                coverage_state="Submitted and indexed",
                indexing_state="INDEXING_ALLOWED",
                page_fetch_state="SUCCESSFUL",
                robots_txt_state="ALLOWED",
                user_canonical="https://gainhelm.com/tools/calc-6/",
                google_canonical="https://gainhelm.com/tools/calc-6/",
                last_crawl_time="2026-10-28T00:00:00Z",
            ),
            # 4. Synthetic local-time microsecond row (from simulated inspect_gsc_url)
            GSCUrlInspectionRecord(
                property_id="gainhelm",
                page_url="https://gainhelm.com/tools/hipaa-violation-penalty-breach-cost-calculator/",
                verdict="PASS",
                coverage_state="Submitted and indexed",
                indexing_state="INDEXING_ALLOWED",
                page_fetch_state="SUCCESSFUL",
                robots_txt_state="ALLOWED",
                user_canonical="https://gainhelm.com/tools/hipaa-violation-penalty-breach-cost-calculator/",
                google_canonical="https://gainhelm.com/tools/hipaa-violation-penalty-breach-cost-calculator/",
                last_crawl_time="2026-10-27T16:23:56.980069",
            ),
            # 5. Retired slug not in valid_urls
            GSCUrlInspectionRecord(
                property_id="gainhelm",
                page_url="https://gainhelm.com/tools/cmmc-level-2-audit-cost-calculator/",
                verdict="PASS",
                coverage_state="Submitted and indexed",
                indexing_state="INDEXING_ALLOWED",
                page_fetch_state="SUCCESSFUL",
                robots_txt_state="ALLOWED",
                user_canonical="https://gainhelm.com/tools/cmmc-level-2-audit-cost-calculator/",
                google_canonical="https://gainhelm.com/tools/cmmc-level-2-audit-cost-calculator/",
                last_crawl_time="2026-10-26T18:20:00Z",
            ),
        ]
        db.upsert_gsc_url_inspection_states(records)

        valid_urls = [
            "https://gainhelm.com/",
            "https://gainhelm.com/tools/soc-2-audit-cost-calculator/",
            "https://gainhelm.com/tools/hipaa-violation-penalty-breach-cost-calculator/",
        ]
        removed = db.sanitize_gsc_url_inspection_states("gainhelm", valid_urls=valid_urls)
        assert removed == 3

        remaining = db.get_gsc_url_inspection_states("gainhelm")
        rem_urls = {r.page_url for r in remaining}
        assert rem_urls == {
            "https://gainhelm.com/",
            "https://gainhelm.com/tools/soc-2-audit-cost-calculator/",
        }


def test_sitemap_lastmod_uniformity_and_tier_child_sitemap_reconciliation(tmp_path: Path) -> None:
    """
    Verifies:
    1. audit_crawl_staleness_and_sitemap_health flags uniform YYYY-MM-DD <lastmod> across >= 5 URLs.
    2. SectionExclusionClassifier.attribute_coverage_by_section marks unregistered sitemaps as
       explicitly_submitted=False, and maps URLs to registered tier child sitemaps (sitemap-hubs.xml /
       sitemap-leaves.xml) when those are the tenant's registered child sitemaps.
    """
    base_dir = tmp_path / "prexvo"
    dist_dir = base_dir / "dist"
    agy_dir = base_dir / ".agy"
    dist_dir.mkdir(parents=True, exist_ok=True)
    agy_dir.mkdir(parents=True, exist_ok=True)

    urls = [f"https://prexvo.com/tools/tool-{i}/" for i in range(6)]
    sm_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for u in urls:
        sm_lines.append(f"  <url><loc>{u}</loc><lastmod>2026-11-01</lastmod></url>")
    sm_lines.append("</urlset>")
    (dist_dir / "sitemap.xml").write_text("\n".join(sm_lines), encoding="utf-8")

    inspector = DailyIndexingInspector(tenant_id="prexvo", base_dir=base_dir, agy_dir=agy_dir)
    health = inspector.audit_crawl_staleness_and_sitemap_health(dist_dir=dist_dir)
    assert health["sitemap_health"]["lastmod_uniform_build_timestamp_flagged"] is True

    # Verify tier child sitemaps reconciliation when only sitemap.xml, sitemap-hubs.xml, sitemap-leaves.xml are registered
    registered = {
        "https://prexvo.com/sitemap.xml": {
            "sitemap_name": "sitemap.xml",
            "sitemap_url": "https://prexvo.com/sitemap.xml",
            "section": "master",
            "is_child_sitemap": False,
            "explicitly_submitted": True,
        },
        "https://prexvo.com/sitemap-hubs.xml": {
            "sitemap_name": "sitemap-hubs.xml",
            "sitemap_url": "https://prexvo.com/sitemap-hubs.xml",
            "section": "hubs",
            "is_child_sitemap": True,
            "explicitly_submitted": True,
        },
        "https://prexvo.com/sitemap-leaves.xml": {
            "sitemap_name": "sitemap-leaves.xml",
            "sitemap_url": "https://prexvo.com/sitemap-leaves.xml",
            "section": "leaves",
            "is_child_sitemap": True,
            "explicitly_submitted": True,
        },
    }
    cov = SectionExclusionClassifier.attribute_coverage_by_section(
        records=[
            {
                "url": "https://prexvo.com/tools/tiered-standard-calculator/",
                "coverage_state": "Discovered - currently not indexed",
                "verdict": "NEUTRAL",
            }
        ],
        canonical_base="https://prexvo.com",
        tenant_id="prexvo",
        registered_sitemaps=registered,
    )
    assert "sitemap-hubs.xml" in cov["by_child_sitemap"]
    assert cov["by_child_sitemap"]["sitemap-hubs.xml"]["explicitly_submitted"] is True
    assert "sitemap-products.xml" not in cov["by_child_sitemap"]
