"""
Focused regression tests for factory gaps (queue canonicalization, core-route 410 protection,
report-only 410 deletion, and 4-tenant market_intel metadata).
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pseofactory.gitops import GitOpsCoordinator, reconcile_workspace_tracking_state
from pseofactory.market_intel import (
    ACTIVE_REVENUE_TENANT_DOMAINS,
    STAGED_RESERVE_DOMAIN_METADATA,
    STAGED_RESERVE_DOMAINS,
    MarketIntelligenceEngine,
)
from pseofactory.seo_growth_loops import (
    PROTECTED_CORE_ROUTES,
    _is_protected_core_route,
    compile_ai_citation_digital_pr_queue,
    evaluate_content_portfolio_decisions,
)


def _init_git_repo(repo_dir: Path) -> None:
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main", str(repo_dir)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo_dir), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo_dir), "config", "user.name", "Test User"], check=True)


def test_reconcile_workspace_tracking_state_never_overwrites_canonical_void_queue(tmp_path: Path) -> None:
    """
    (a) reconcile_workspace_tracking_state must NEVER copy a stale root void_candidates.jsonl
    over <repo>/.agy/void_candidates.jsonl, and _mark_rolled_back_void_candidates defaults to
    <repo>/.agy/void_candidates.jsonl rather than /home/ubuntuadmin/projects/.agy/void_candidates.jsonl.
    """
    repo_dir = tmp_path / "pseofactory"
    _init_git_repo(repo_dir)

    stale_root = repo_dir / "void_candidates.jsonl"
    stale_root.write_text(json.dumps({"slug": "stale-old-entry", "status": "PENDING"}) + "\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo_dir), "add", "void_candidates.jsonl"], check=True)
    subprocess.run(["git", "-C", str(repo_dir), "commit", "-m", "initial stale root"], check=True, capture_output=True)

    # Modify stale root file so git status --porcelain reports it dirty
    stale_root.write_text(json.dumps({"slug": "stale-dirty-entry", "status": "PENDING"}) + "\n", encoding="utf-8")

    agy_dir = repo_dir / ".agy"
    agy_dir.mkdir(parents=True, exist_ok=True)
    canonical_queue = agy_dir / "void_candidates.jsonl"
    canonical_records = [
        json.dumps({"slug": "live-nov-26-entry-1", "status": "PENDING"}),
        json.dumps({"slug": "live-nov-26-entry-2", "status": "BUILT"}),
    ]
    canonical_payload = "\n".join(canonical_records) + "\n"
    canonical_queue.write_text(canonical_payload, encoding="utf-8")

    summary = reconcile_workspace_tracking_state(
        runs_dir=tmp_path / "runs",
        queues_dir=tmp_path / "queues",
        ledger_path=tmp_path / "ledger.json",
        tenant_repos=[repo_dir],
    )
    assert summary["status"] == "PASS"
    assert canonical_queue.read_text(encoding="utf-8") == canonical_payload

    # Also verify compile_ai_citation_digital_pr_queue prioritizes .agy/void_candidates.jsonl over root fallback
    sim_root = tmp_path / "sim_repo"
    sim_dist = sim_root / "dist"
    (sim_dist / "tools" / "section-179-deduction-calculator").mkdir(parents=True, exist_ok=True)
    (sim_dist / "tools" / "section-179-deduction-calculator" / "index.html").write_text(
        "<html><head><title>Section 179 Deduction Calculator</title></head><body><h1>Section 179 Deduction Calculator</h1></body></html>",
        encoding="utf-8",
    )
    (sim_root / ".agy").mkdir(parents=True, exist_ok=True)
    (sim_root / ".agy" / "void_candidates.jsonl").write_text(
        json.dumps(
            {
                "slug": "section-179-deduction-calculator",
                "query": "section 179 deduction calculator",
                "search_volume": 400,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (sim_root / "void_candidates.jsonl").write_text(
        json.dumps(
            {
                "slug": "stale-root-section-179-calculator",
                "query": "stale root section 179 tax calculator",
                "search_volume": 900,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    pr_rep = compile_ai_citation_digital_pr_queue(
        property_id="profithelm",
        repo_root=sim_root,
        dist_dir=sim_dist,
        consolidated_gsc={
            "current_rows": [
                {
                    "query": "section 179 deduction calculator",
                    "canonical_path": "/tools/section-179-deduction-calculator",
                    "impressions": 40,
                    "clicks": 2,
                    "position": 9.0,
                }
            ]
        },
        persist=False,
    )
    assert pr_rep["queue_count"] >= 1
    pr_slugs = {item["slug"] for item in pr_rep["queue"]}
    assert "section-179-deduction-calculator" in pr_slugs
    assert "stale-root-section-179-calculator" not in pr_slugs

    # Verify _mark_rolled_back_void_candidates source points to <repo>/.agy/void_candidates.jsonl as production default
    import inspect

    rb_src = inspect.getsource(GitOpsCoordinator._mark_rolled_back_void_candidates)
    assert '".agy" / "void_candidates.jsonl"' in rb_src
    assert "/home/ubuntuadmin/projects/.agy/void_candidates.jsonl" not in rb_src


def test_protected_core_routes_never_queued_for_410_even_at_365_days(tmp_path: Path) -> None:
    """
    (b) /partners/, /about/, /, /tools/ and all governance/core/feed routes are hard-blocked
    from ever entering .agy/prune_noindex_queue.json or receiving PRUNE_410_GONE, even with
    365 days age and 0 impressions.
    """
    assert "partners" in PROTECTED_CORE_ROUTES
    for core_route in (
        "/",
        "index.html",
        "/tools/",
        "tools/index.html",
        "/partners/",
        "partners/index.html",
        "https://gainhelm.com/partners/",
        "/about/",
        "/contact/",
        "/privacy/",
        "/terms/",
        "/methodology/",
        "/editorial-policy/",
        "/disclosure/",
        "/disclaimer/",
        "/legal/",
        "/guides/",
        "/categories/",
        "/states/",
        "/blog/",
        "/resources/",
        "/pricing/",
        "/faq/",
        "/sitemap.xml",
        "/sitemap-tools.xml",
        "/feed.xml",
        "/robots.txt",
        "/llms.txt",
        "/catalog.json",
        "/404.html",
        "/404",
    ):
        assert _is_protected_core_route(core_route), f"Expected protected core route: {core_route}"

    repo_root = tmp_path / "gainhelm_core_guard"
    dist_dir = repo_root / "dist"
    old_ts = (datetime.now(timezone.utc) - timedelta(days=365)).timestamp()

    core_html_paths = [
        dist_dir / "index.html",
        dist_dir / "tools" / "index.html",
        dist_dir / "partners" / "index.html",
        dist_dir / "about" / "index.html",
        dist_dir / "contact" / "index.html",
        dist_dir / "privacy" / "index.html",
        dist_dir / "terms" / "index.html",
        dist_dir / "methodology" / "index.html",
        dist_dir / "editorial-policy" / "index.html",
        dist_dir / "disclosure" / "index.html",
        dist_dir / "disclaimer" / "index.html",
        dist_dir / "legal" / "index.html",
        dist_dir / "guides" / "index.html",
        dist_dir / "categories" / "index.html",
        dist_dir / "states" / "index.html",
        dist_dir / "blog" / "index.html",
        dist_dir / "resources" / "index.html",
        dist_dir / "pricing" / "index.html",
        dist_dir / "faq" / "index.html",
        dist_dir / "404.html",
    ]
    for hf in core_html_paths:
        hf.parent.mkdir(parents=True, exist_ok=True)
        hf.write_text(
            f"<html><head><title>{hf.parent.name or 'Home'}</title></head>"
            f"<body><main><h1>{hf.parent.name or 'Home'}</h1></main></body></html>",
            encoding="utf-8",
        )
        os.utime(hf, (old_ts, old_ts))

    # Also add an active tool page so report has a healthy tool
    active_tool = dist_dir / "tools" / "soc-2-readiness-calculator" / "index.html"
    active_tool.parent.mkdir(parents=True, exist_ok=True)
    active_tool.write_text(
        "<html><head><title>SOC 2 Calculator</title></head><body><main><h1>SOC 2 Calculator</h1></main></body></html>",
        encoding="utf-8",
    )
    os.utime(active_tool, (old_ts, old_ts))

    report = evaluate_content_portfolio_decisions(
        property_id="gainhelm",
        repo_root=repo_root,
        dist_dir=dist_dir,
        consolidated_gsc={
            "date_range": ("2026-05-01", "2026-05-28"),
            "current_rows": [
                {
                    "query": "soc 2 readiness calculator",
                    "canonical_path": "/tools/soc-2-readiness-calculator",
                    "impressions": 45,
                    "clicks": 4,
                    "position": 5.5,
                }
            ],
            "impressions_by_path": {"/tools/soc-2-readiness-calculator": 45},
            "clicks_by_path": {"/tools/soc-2-readiness-calculator": 4},
        },
        max_age_days=90.0,
        persist=True,
    )

    assert report["action_breakdown"]["PRUNE_410_GONE"] == 0
    assert report["zero_impression_candidates"] == []
    decision_paths = {d["url_path"] for d in report["decisions"]}
    assert "/partners" not in decision_paths
    assert "/about" not in decision_paths
    assert "/" not in decision_paths
    assert "/tools" not in decision_paths

    prune_queue = json.loads((repo_root / ".agy" / "prune_noindex_queue.json").read_text(encoding="utf-8"))
    assert prune_queue["queued_count"] == 0
    assert prune_queue["candidates"] == []
    assert prune_queue["consolidation_executed"] is False
    assert prune_queue["report_only"] is True
    assert prune_queue["approval_required"] is True
    assert prune_queue["strip_internal_links"] is False
    assert prune_queue["execution_mode"] == "REPORT_ONLY"


def test_aged_zero_impression_tool_leaf_is_strictly_report_only_without_html_mutation(tmp_path: Path) -> None:
    """
    (c) An aged zero-impression tool leaf page is queued strictly as report_only with
    consolidation_executed=False and strip_internal_links=False, and donor HTML is never mutated.
    """
    repo_root = tmp_path / "prexvo_report_only"
    dist_dir = repo_root / "dist"
    old_ts = (datetime.now(timezone.utc) - timedelta(days=200)).timestamp()

    hub_html = (
        '<html><head><title>Tools</title></head><body><main>'
        '<a href="/tools/aged-zero-impr-leaf/">Aged Leaf</a>'
        "</main></body></html>"
    )
    hub_file = dist_dir / "tools" / "index.html"
    hub_file.parent.mkdir(parents=True, exist_ok=True)
    hub_file.write_text(hub_html, encoding="utf-8")
    os.utime(hub_file, (old_ts, old_ts))

    partners_html = "<html><head><title>Partners</title></head><body><h1>Partners</h1></body></html>"
    partners_file = dist_dir / "partners" / "index.html"
    partners_file.parent.mkdir(parents=True, exist_ok=True)
    partners_file.write_text(partners_html, encoding="utf-8")
    os.utime(partners_file, (old_ts, old_ts))

    leaf_file = dist_dir / "tools" / "aged-zero-impr-leaf" / "index.html"
    leaf_file.parent.mkdir(parents=True, exist_ok=True)
    leaf_file.write_text(
        "<html><head><title>Aged Leaf</title></head><body><main><h1>Aged Leaf</h1></main></body></html>",
        encoding="utf-8",
    )
    os.utime(leaf_file, (old_ts, old_ts))

    report = evaluate_content_portfolio_decisions(
        property_id="prexvo",
        repo_root=repo_root,
        dist_dir=dist_dir,
        consolidated_gsc={
            "date_range": ("2026-05-01", "2026-05-28"),
            "current_rows": [],
            "impressions_by_path": {},
            "clicks_by_path": {},
        },
        max_age_days=90.0,
        persist=True,
    )

    assert len(report["zero_impression_candidates"]) == 1
    cand = report["zero_impression_candidates"][0]
    assert cand["url_path"] == "/tools/aged-zero-impr-leaf"
    assert cand["http_status"] == 410
    assert cand["consolidation_executed"] is False
    assert cand["report_only"] is True
    assert cand["approval_required"] is True
    assert cand["strip_internal_links"] is False
    assert cand["execution_mode"] == "REPORT_ONLY"

    prune_queue = json.loads((repo_root / ".agy" / "prune_noindex_queue.json").read_text(encoding="utf-8"))
    assert prune_queue["queued_count"] == 1
    assert prune_queue["consolidation_executed"] is False
    assert prune_queue["report_only"] is True
    assert prune_queue["approval_required"] is True
    assert prune_queue["strip_internal_links"] is False
    assert prune_queue["execution_mode"] == "REPORT_ONLY"
    assert prune_queue["candidates"][0]["url_path"] == "/tools/aged-zero-impr-leaf"
    assert prune_queue["candidates"][0]["strip_internal_links"] is False

    # Donor HTML and protected pages remain untouched; no edgeGone middleware created
    assert hub_file.read_text(encoding="utf-8") == hub_html
    assert partners_file.read_text(encoding="utf-8") == partners_html
    assert not (repo_root / "functions" / "_middleware.js").exists()


def test_market_intel_four_active_tenants_zero_hibernated_reserve_domains(tmp_path: Path) -> None:
    """
    (d) market_intel lists all 4 active tenants (profithelm, prexvo, gainhelm, lienbond)
    and 0 hibernated reserve domains.
    """
    assert set(ACTIVE_REVENUE_TENANT_DOMAINS) == {
        "profithelm.com",
        "prexvo.com",
        "gainhelm.com",
        "lienbond.com",
    }
    assert STAGED_RESERVE_DOMAINS == ()
    assert STAGED_RESERVE_DOMAIN_METADATA == {}

    engine = MarketIntelligenceEngine(db_path=tmp_path / "market_intel_4t.db")
    report = engine.run_workflow(sync_db=False, simulate_three_cycle_confirmation=False)
    assert report["staged_reserve_domains"] == []
    assert {t["tenant_id"] for t in report["existing_tenants"]} == {
        "profithelm",
        "prexvo",
        "gainhelm",
        "lienbond",
    }
    assert {t["domain"] for t in report["existing_tenants"]} == {
        "profithelm.com",
        "prexvo.com",
        "gainhelm.com",
        "lienbond.com",
    }


def test_protected_core_route_partners_overlay_blocked_on_compile_persist_eval_and_inject(tmp_path: Path) -> None:
    """
    Even if .agy/overlays/partners.json already exists on disk, overlay evaluation,
    compilation, persistence, feedback_loop HTML repair, and inject_overlay_into_html
    must skip dist/partners/index.html and leave its <title> and HTML 100% untouched.
    """
    from unittest.mock import MagicMock

    from pseofactory.gsc_remediation import (
        compile_remediation_overlay_spec,
        evaluate_expired_overlays,
        inject_overlay_into_html,
        is_non_tool_overlay_target,
        persist_overlay_respecting_lock,
    )
    from pseofactory.indexing.feedback_loop import IndexingFeedbackLoop

    repo_root = tmp_path / "prexvo"
    dist_dir = repo_root / "dist"
    partners_dir = dist_dir / "partners"
    partners_dir.mkdir(parents=True, exist_ok=True)
    partners_file = partners_dir / "index.html"
    original_partners_html = (
        '<!DOCTYPE html><html lang="en"><head>'
        "<title>Partners &amp; Editorial Disclosure | Prexvo</title>"
        '<meta name="description" content="Partner directory and disclosures for Prexvo.">'
        '<link rel="canonical" href="https://prexvo.com/partners/">'
        "</head><body><main><h1>Partners</h1><p>Disclosure info.</p></main></body></html>"
    )
    partners_file.write_text(original_partners_html, encoding="utf-8")

    # Seed legacy polluted .agy/overlays/partners.json on disk
    ov_dir = repo_root / ".agy" / "overlays"
    ov_dir.mkdir(parents=True, exist_ok=True)
    legacy_ov = {
        "slug": "partners",
        "tenant_id": "prexvo",
        "property_id": "prexvo",
        "target_url": "https://prexvo.com/partners/",
        "query": "partners",
        "title_rewrite": "Partners 2026 Calculator (Title IV Rules) | Prexvo",
        "quick_answer": "Should never be injected onto partners.",
        "h2_headings": ["Partners 2026 Calculator"],
        "status": "ACTIVE_LOCKED",
        "created_at": (datetime.now(timezone.utc) - timedelta(days=40)).isoformat(),
        "locked_until": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
        "measurement_lock_days": 28,
        "baseline_position": 12.0,
        "baseline_impressions": 20,
    }
    legacy_ov_file = ov_dir / "partners.json"
    legacy_ov_file.write_text(json.dumps(legacy_ov, indent=2), encoding="utf-8")

    assert is_non_tool_overlay_target(html=original_partners_html, overlay_data=legacy_ov, slug="partners") is True

    # 1. inject_overlay_into_html must leave dist/partners/index.html untouched
    assert inject_overlay_into_html(original_partners_html, legacy_ov) == original_partners_html

    # 2. evaluate_expired_overlays must never touch dist/partners/index.html and prunes stale partners.json
    eval_res = evaluate_expired_overlays(
        site_url="sc-domain:prexvo.com",
        base_dir=repo_root,
        persist=True,
        live_queries=[],
    )
    assert eval_res["total_evaluated"] == 0
    assert partners_file.read_text(encoding="utf-8") == original_partners_html
    assert not legacy_ov_file.exists()

    # 3. compile_remediation_overlay_spec + persist_overlay_respecting_lock refuse core routes
    compiled = compile_remediation_overlay_spec(
        {
            "slug": "partners",
            "tenant_id": "prexvo",
            "target_url": "https://prexvo.com/partners/",
            "query": "partners",
            "impressions": 40,
            "position": 10.0,
        },
        tenant_id="prexvo",
    )
    assert compiled["blocked_protected_core_route"] is True
    assert compiled["skip_overlay"] is True
    assert compiled["overlay_allowed"] is False
    assert compiled["title_rewrite"] == ""
    assert compiled["h2_headings"] == []

    _, written = persist_overlay_respecting_lock(legacy_ov_file, legacy_ov)
    assert written is False
    assert not legacy_ov_file.exists()

    # 4. IndexingFeedbackLoop._apply_html_repairs_for_slug refuses protected core routes
    loop = IndexingFeedbackLoop(
        property_id="prexvo",
        domain="prexvo.com",
        canonical_base="https://prexvo.com",
        base_dir=repo_root,
        dist_dir=dist_dir,
        indexer=MagicMock(),
        inspector=MagicMock(),
        preflight_engine=MagicMock(),
        milestone_tracker=MagicMock(event_log=[]),
        telemetry_logger=MagicMock(),
    )
    assert loop._is_protected_hub_route("partners", "https://prexvo.com/partners/") is True
    assert loop._apply_html_repairs_for_slug("partners", "https://prexvo.com/partners/", legacy_ov) is False
    assert partners_file.read_text(encoding="utf-8") == original_partners_html

