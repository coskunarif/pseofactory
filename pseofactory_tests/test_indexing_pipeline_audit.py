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

    fake_gsccli = tmp_path / "gsccli"
    fake_gsccli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    with (
        patch("pseofactory.indexer.shutil.which", return_value=str(fake_gsccli)),
        patch("subprocess.run", return_value=mock_proc_429) as run_mock,
    ):
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


def test_synthesized_1031_calculator_manifest_and_ssr_parity(tmp_path: Path) -> None:
    """
    Verifies that RetroReflectionEngine synthesizes a valid Section 1031 manifest
    with published_output=348900.0 for synthesized 1031 slugs (such as
    'section-1031-exchange-deferral-calculator') and passes Gate 5 SSR Metric Parity.
    """
    from pseofactory.maintenance import RetroReflectionEngine
    from pseofactory.audit import verify_manifest_ssr_metric_parity

    slug = "section-1031-exchange-deferral-calculator"
    html_in = """<!DOCTYPE html>
<html lang="en">
<head><title>Section 1031 Exchange Deferral Calculator | ProfitHelm</title></head>
<body>
  <div id="val-realized_gain">$900,000</div>
  <div id="val-recapture_tax">$75,000</div>
  <div id="val-net_tax_deferred">$348,900</div>
  <div id="val-replacement_basis">$1,100,000</div>
</body>
</html>"""
    manifest = RetroReflectionEngine._resolve_manifest_for_page(
        html_in,
        property_id="profithelm",
        slug=slug,
    )
    assert manifest["published_output"] == 348900.0
    issues = verify_manifest_ssr_metric_parity(
        html_in,
        published_output=manifest["published_output"],
        slug=slug,
    )
    assert issues == []


def test_unpushed_empty_engines_entry_classified_new_and_dispatched(tmp_path: Path) -> None:
    """
    Verifies:
    1. A ledger entry with matching top-level hash but empty engines={} is classified
       as NEW (is_new=True), never EXISTING, so dispatch_automated_indexing submits it
       rather than returning IDEMPOTENT_NO_OP.
    2. 2-segment /tools/<calculator>/ paths are classified as asset_type='hub' and
       included in automated dispatch, while 3-segment /tools/<hub>/<leaf>/ paths
       remain asset_type='leaf' and excluded by default.
    3. audit_asset_submission_status(live=True) does not count engines={} entries as
       Google/Bing accepted.
    4. dispatch_automated_indexing(live=True) does not latch an engines={} entry when
       IndexNow fails.
    """
    base_dir = tmp_path / "gainhelm"
    dist_dir = base_dir / "dist"
    agy_dir = base_dir / ".agy"
    agy_dir.mkdir(parents=True, exist_ok=True)
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")

    hub_url = "https://gainhelm.com/tools/soc-2-audit-cost-calculator/"
    leaf_url = "https://gainhelm.com/tools/soc-2-audit-cost-calculator/texas/"
    _write_test_html(
        dist_dir / "tools" / "soc-2-audit-cost-calculator" / "index.html",
        hub_url,
        "SOC 2 Audit Cost Calculator",
    )
    _write_test_html(
        dist_dir / "tools" / "soc-2-audit-cost-calculator" / "texas" / "index.html",
        leaf_url,
        "SOC 2 Audit Cost Calculator Texas",
    )
    (dist_dir / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"<url><loc>{hub_url}</loc></url>"
        f"<url><loc>{leaf_url}</loc></url>"
        "</urlset>",
        encoding="utf-8",
    )

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
    hub_hash = indexer.get_url_content_hash(hub_url)
    indexer.save_pushed_ledger(
        {
            hub_url: {
                "hash": hub_hash,
                "last_pushed": "2026-11-01T00:00:00+00:00",
                "push_count": 1,
                "tenant_id": "gainhelm",
                "engines": {},
            }
        }
    )

    inspection = indexer.inspect_platform_assets()
    by_url = {a["url"]: a for a in inspection["assets"]}
    assert by_url[hub_url]["asset_type"] == "hub"
    assert by_url[hub_url]["is_new"] is True
    assert by_url[hub_url]["status"] == "NEW"
    assert by_url[leaf_url]["asset_type"] == "leaf"

    audit_before = indexer.audit_asset_submission_status(assets=inspection["assets"], live=True)
    assert audit_before["summary"]["google_accepted_count"] == 0
    assert audit_before["summary"]["bing_accepted_count"] == 0

    sim_dispatch = indexer.dispatch_automated_indexing(live=False)
    assert sim_dispatch["dispatch_type"] == "NEW_ASSETS_SUBMITTED"
    assert hub_url in sim_dispatch["urls_submitted"]
    assert leaf_url not in sim_dispatch["urls_submitted"]

    # If live IndexNow fails, ledger must NOT latch an engines={} entry for hub_url
    indexer.save_pushed_ledger({})
    with (
        patch.object(
            indexer,
            "submit_indexnow_batch",
            return_value={"status": "FAILED", "urls_submitted": 1, "urls_dispatched": 0},
        ),
        patch.object(indexer, "ping_websub_hub", return_value={"status": "SIMULATED"}),
        patch.object(indexer, "ping_pingomatic", return_value={"status": "SIMULATED"}),
        patch.object(
            indexer,
            "submit_gsc_indexing",
            return_value={"results": [], "sitemap_registration": {"status": "ACCEPTED", "submissions": []}},
        ),
        patch.object(indexer, "submit_indexmysite", return_value={"status": "SKIPPED"}),
        patch.object(indexer, "submit_fast_index", return_value={"status": "SKIPPED"}),
    ):
        indexer.dispatch_automated_indexing(live=True)
    assert hub_url not in indexer.load_pushed_ledger()


def test_submit_bing_webmaster_accepts_dispatched_and_idempotent_no_op(tmp_path: Path) -> None:
    """
    Verifies submit_bing_webmaster maps DISPATCHED and IDEMPOTENT_NO_OP to SUCCESS,
    while mapping FAILED and QUARANTINED_ALL to FAILED.
    """
    base_dir = tmp_path / "lienbond"
    dist_dir = base_dir / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    indexer = PushIndexer(
        domain="lienbond.com",
        canonical_base="https://lienbond.com",
        base_dir=base_dir,
        dist_dir=dist_dir,
        tenant_id="lienbond",
    )

    for ok_status in ("DISPATCHED", "IDEMPOTENT_NO_OP", "SIMULATED", "PARTIAL"):
        with patch.object(
            indexer,
            "submit_indexnow_batch",
            return_value={"status": ok_status, "urls_submitted": 3},
        ):
            res = indexer.submit_bing_webmaster(urls=["https://lienbond.com/"], dry_run=False)
        assert res["status"] == "SUCCESS", f"Expected SUCCESS for {ok_status}, got {res}"
        assert res["urls_submitted"] == 3

    for bad_status in ("FAILED", "QUARANTINED_ALL"):
        with patch.object(
            indexer,
            "submit_indexnow_batch",
            return_value={"status": bad_status, "urls_submitted": 0},
        ):
            res = indexer.submit_bing_webmaster(urls=["https://lienbond.com/"], dry_run=False)
        assert res["status"] == "FAILED", f"Expected FAILED for {bad_status}, got {res}"


def test_deterministic_per_domain_indexnow_keys_across_50_plus_tenants(tmp_path: Path) -> None:
    """
    Verifies derive_deterministic_indexnow_key and PushIndexer.__init__ preserve
    existing live keys (profithelm.com, gainhelm.com) and generate deterministic,
    unique per-domain keys for lienbond.com, prexvo.com, and any 50+ future domains
    without falling back to ProfitHelm's key or DEFAULT_INDEXNOW_KEY.
    """
    import hashlib
    from pseofactory.indexer import DEFAULT_INDEXNOW_KEY, derive_deterministic_indexnow_key

    ph_key = hashlib.sha256(b"profithelm.com:indexnow:v2").hexdigest()[:32]
    gh_key = "c5430f81d11340a6bda3162725e24a03"
    lb_key = hashlib.sha256(b"lienbond.com:indexnow:v1").hexdigest()[:32]
    px_key = hashlib.sha256(b"prexvo.com:indexnow:v1").hexdigest()[:32]
    t50_key = hashlib.sha256(b"tenant-fifty.example:indexnow:v1").hexdigest()[:32]

    assert derive_deterministic_indexnow_key("profithelm.com") == ph_key
    assert derive_deterministic_indexnow_key("www.profithelm.com") == ph_key
    assert derive_deterministic_indexnow_key("gainhelm.com") == gh_key
    assert derive_deterministic_indexnow_key("lienbond.com") == lb_key
    assert derive_deterministic_indexnow_key("prexvo.com") == px_key
    assert derive_deterministic_indexnow_key("https://tenant-fifty.example/tools/") == t50_key

    assert len({ph_key, gh_key, lb_key, px_key, t50_key, DEFAULT_INDEXNOW_KEY}) == 6

    for dom, expected in (
        ("profithelm.com", ph_key),
        ("gainhelm.com", gh_key),
        ("lienbond.com", lb_key),
        ("prexvo.com", px_key),
        ("tenant-fifty.example", t50_key),
    ):
        t_dir = tmp_path / dom
        idx = PushIndexer(domain=dom, canonical_base=f"https://{dom}", base_dir=t_dir, dist_dir=t_dir / "dist")
        assert idx.indexnow_key == expected
        if dom != "profithelm.com":
            assert idx.indexnow_key != ph_key
            assert idx.indexnow_key != DEFAULT_INDEXNOW_KEY

    # Existing valid deployed dist/<32-hex>.txt keyfile is preserved for tenants with custom live keys
    custom_dir = tmp_path / "custom-deployed"
    custom_dist = custom_dir / "dist"
    custom_dist.mkdir(parents=True, exist_ok=True)
    custom_key = "0123456789abcdef0123456789abcdef"
    (custom_dist / f"{custom_key}.txt").write_text(custom_key + "\n", encoding="utf-8")
    idx_custom = PushIndexer(
        domain="prexvo.com",
        canonical_base="https://prexvo.com",
        base_dir=custom_dir,
        dist_dir=custom_dist,
    )
    assert idx_custom.indexnow_key == custom_key


