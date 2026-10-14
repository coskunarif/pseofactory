"""
Deterministic binary test oracles and independent corollary checks for
multi-tenant child sitemap generation, explicit per-child GSC registration,
idempotent ChildSitemapPushLedger tracking, and per-section GSC coverage attribution.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Dict, List

import pytest

from pseofactory.contracts import (
    assert_no_forbidden_dashes,
    assert_sitemap_index_parses,
    assert_sitemap_parses,
)
from pseofactory.drift import (
    compute_asset_fingerprint,
    detect_engine_drift,
    record_asset_ledger,
    record_engine_hash,
)
from pseofactory.gsc_remediation import (
    compile_remediation_overlay_spec,
    prioritize_gsc_signals,
)
from pseofactory.indexer import (
    ChildSitemapPushLedger,
    PushIndexer,
    SitemapGovernor,
    TEMPLATE_SITEMAP_SECTIONS,
    build_multi_tenant_sitemaps,
    classify_url_template_section,
)
from pseofactory.indexing.feedback_loop import (
    CANONICAL_TEMPLATE_DEFECT,
    CONTENT_DEPTH_DEFICIT,
    DEAD_ROUTE_IN_SITEMAP,
    IndexingFeedbackLoop,
    SectionExclusionClassifier,
    THIN_OR_ANSWER_DEFICIENCY,
)
from pseofactory.indexing_inspector import DailyIndexingInspector
from pseofactory.maintenance import (
    AssetIntegrityEvaluator,
    ConfigurablePropertyAdapter,
    RefactorCascadeEngine,
)
from pseofactory.verifier import MasterSEOVerifier


def _write_minimal_valid_html(path: Path, canonical_url: str, title: str = "Valid Sovereign Tool Page") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body_words = " ".join(
        [
            "Deterministic statutory benchmark analysis with verified federal and state rates,"
            " interactive calculation methodology, unit margin formulas, and empirical audit tables."
        ]
        * 12
    )
    html = (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        f"  <title>{title} | Sovereign Benchmark</title>\n"
        "  <meta name=\"description\" content=\"Deterministic benchmark analysis with verified statutory rates and instant calculation output.\" />\n"
        f"  <link rel=\"canonical\" href=\"{canonical_url}\" />\n"
        "</head>\n"
        "<body>\n"
        f"  <h1>{title}</h1>\n"
        f"  <main><p>{body_words}</p></main>\n"
        "</body>\n"
        "</html>\n"
    )
    path.write_text(html, encoding="utf-8")


def test_template_section_classification_and_date_bucketing() -> None:
    """
    Oracle 1: URLs classify into products, categories, articles (with YYYY-MM date buckets),
    and guides via path or tenant metadata without hardcoded tenant domain assumptions.
    """
    assert TEMPLATE_SITEMAP_SECTIONS == ("products", "categories", "articles", "guides")

    p_info = classify_url_template_section(
        "https://alpha.example.com/products/widget-pro",
        canonical_base="https://alpha.example.com",
    )
    assert p_info["section"] == "products"
    assert p_info["child_sitemap"] == "sitemap-products.xml"
    assert p_info["child_sitemap_url"] == "https://alpha.example.com/sitemap-products.xml"

    c_info = classify_url_template_section(
        "https://alpha.example.com/categories/tax-calculators",
        canonical_base="https://alpha.example.com",
    )
    assert c_info["section"] == "categories"
    assert c_info["child_sitemap"] == "sitemap-categories.xml"

    a_dated = classify_url_template_section(
        "https://alpha.example.com/articles/2026-09/q3-margin-audit",
        canonical_base="https://alpha.example.com",
    )
    assert a_dated["section"] == "articles"
    assert a_dated["date_bucket"] == "2026-09"
    assert a_dated["child_sitemap"] == "sitemap-articles-2026-09.xml"

    a_meta = classify_url_template_section(
        "https://alpha.example.com/insights/unit-economics-breakdown",
        metadata={"section": "articles", "published_at": "2026-10-12T08:30:00Z"},
        canonical_base="https://alpha.example.com",
    )
    assert a_meta["section"] == "articles"
    assert a_meta["date_bucket"] == "2026-10"
    assert a_meta["child_sitemap"] == "sitemap-articles-2026-10.xml"

    g_info = classify_url_template_section(
        "https://alpha.example.com/guides/how-to-audit-cogs",
        canonical_base="https://alpha.example.com",
    )
    assert g_info["section"] == "guides"
    assert g_info["child_sitemap"] == "sitemap-guides.xml"

    # Custom tenant section_rules override without hardcoding tenant routes in engine
    custom_info = classify_url_template_section(
        "https://custom-tenant.io/catalog-sku/sku-900",
        canonical_base="https://custom-tenant.io",
        section_rules={"products": ("/catalog-sku/",)},
    )
    assert custom_info["section"] == "products"
    assert custom_info["child_sitemap"] == "sitemap-products.xml"


def test_multi_tenant_child_sitemap_generation_isolation_and_caps(tmp_path: Path) -> None:
    """
    Oracle 2: Multi-tenant sitemap generation breaks out products, categories,
    articles by date, guides, tier sitemaps (hubs/leaves), master sitemap.xml,
    and sitemap-index.xml while preserving strict tenant isolation, crawl-budget
    velocity caps (MAX_BATCH_SIZE = 2000), hub caps (TIER1_HUB_CAP = 150), and
    banning em-dashes and en-dashes.
    """
    tenant_a_dir = tmp_path / "tenant_a" / "dist"
    tenant_b_dir = tmp_path / "tenant_b" / "dist"

    tenant_a_urls = [
        "https://tenanta.com/",
        "https://tenanta.com/products/margin-analyzer",
        "https://tenanta.com/products/fee-calculator",
        "https://tenanta.com/categories/ecommerce-tools",
        "https://tenanta.com/articles/2026-08/summer-cpi-report",
        "https://tenanta.com/articles/2026-09/autumn-rate-update",
        "https://tenanta.com/guides/complete-landed-cost-guide",
    ]
    tenant_b_urls = [
        "https://tenantb.org/",
        "https://tenantb.org/products/dispatch-router",
        "https://tenantb.org/categories/field-service",
        "https://tenantb.org/articles/2026-10/winter-sla-benchmarks",
        "https://tenantb.org/guides/dispatcher-onboarding-playbook",
    ]

    res_a = build_multi_tenant_sitemaps(
        tenant_a_urls,
        dist_dir=tenant_a_dir,
        canonical_base="https://tenanta.com",
        domain="tenanta.com",
        tenant_id="tenanta",
        lastmod="2026-10-13",
    )
    res_b = build_multi_tenant_sitemaps(
        tenant_b_urls,
        dist_dir=tenant_b_dir,
        canonical_base="https://tenantb.org",
        domain="tenantb.org",
        tenant_id="tenantb",
        lastmod="2026-10-13",
    )

    expected_a_children = {
        "sitemap-products.xml",
        "sitemap-categories.xml",
        "sitemap-articles-2026-08.xml",
        "sitemap-articles-2026-09.xml",
        "sitemap-guides.xml",
        "sitemap-hubs.xml",
        "sitemap-leaves.xml",
    }
    assert expected_a_children.issubset(set(res_a["child_sitemaps"].keys()))
    assert (tenant_a_dir / "sitemap-index.xml").is_file()
    assert (tenant_a_dir / "sitemap.xml").is_file()

    # Validate XML contracts and zero forbidden dashes across all generated files
    for xml_file in sorted(tenant_a_dir.glob("sitemap*.xml")):
        content = xml_file.read_text(encoding="utf-8")
        assert_no_forbidden_dashes(content, context=xml_file.name)
        assert "\u2014" not in content
        assert "\u2013" not in content
        if xml_file.name == "sitemap-index.xml":
            assert_sitemap_index_parses(content)
            assert_sitemap_parses(content, allow_index=True)
        else:
            assert_sitemap_parses(content, allow_index=False)

    # Corollary check: Strict multi-tenant isolation (zero cross-tenant URL bleed)
    for xml_file in sorted(tenant_a_dir.glob("sitemap*.xml")):
        text_a = xml_file.read_text(encoding="utf-8")
        assert "tenantb.org" not in text_a
        assert "https://tenanta.com/" in text_a

    for xml_file in sorted(tenant_b_dir.glob("sitemap*.xml")):
        text_b = xml_file.read_text(encoding="utf-8")
        assert "tenanta.com" not in text_b
        assert "https://tenantb.org/" in text_b

    # Verify cross-tenant URL injection raises ValueError under strict_isolation=True
    with pytest.raises(ValueError, match="Cross-tenant URL"):
        build_multi_tenant_sitemaps(
            ["https://tenanta.com/products/a", "https://tenantb.org/products/b"],
            canonical_base="https://tenanta.com",
            domain="tenanta.com",
            tenant_id="tenanta",
            strict_isolation=True,
            write_files=False,
        )

    # Verify MasterSEOVerifier.check_sitemap_gate validates all child sitemaps and sitemap-index.xml
    verifier_a = MasterSEOVerifier(
        dist_dir=tenant_a_dir,
        canonical_base="https://tenanta.com",
        domain="tenanta.com",
        brand_name="Tenant A",
    )
    gate_a = verifier_a.check_sitemap_gate(tenant_a_dir)
    assert gate_a["status"] == "PASS"
    assert "sitemap-index.xml" in gate_a["sitemaps_checked"]
    assert "sitemap-products.xml" in gate_a["sitemaps_checked"]
    assert "sitemap-articles-2026-09.xml" in gate_a["sitemaps_checked"]

    # Verify crawl-budget velocity cap (MAX_BATCH_SIZE = 2000) and TIER1_HUB_CAP (150)
    many_urls = (
        [f"https://tenanta.com/categories/hub-{i}" for i in range(200)]
        + [f"https://tenanta.com/products/item-{i}/detail" for i in range(2100)]
    )
    capped_bundle = build_multi_tenant_sitemaps(
        many_urls,
        canonical_base="https://tenanta.com",
        domain="tenanta.com",
        tenant_id="tenanta",
        lastmod="2026-10-13",
        write_files=False,
    )
    assert len(capped_bundle["tier1_hubs"]) == SitemapGovernor.TIER1_HUB_CAP
    assert capped_bundle["master_sitemap"]["url_count"] == SitemapGovernor.MAX_BATCH_SIZE


def test_explicit_child_sitemap_gsc_submission_and_idempotent_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Oracle 3: Every child sitemap is explicitly submitted via gsccli sitemaps submit
    (never relying solely on master-index auto-detection), tracked idempotently in
    ChildSitemapPushLedger by content hash, and verified for isolated
    'Submitted pages only' filtering.
    """
    dist_dir = tmp_path / "tenant_alpha" / "dist"
    ledger_path = tmp_path / ".agy" / "child_sitemap_push_ledger.json"

    urls = [
        "https://alpha.io/",
        "https://alpha.io/products/unit-margin-calc",
        "https://alpha.io/categories/finance-ops",
        "https://alpha.io/articles/2026-10/q4-tax-update",
        "https://alpha.io/guides/margin-protection-guide",
    ]

    indexer = PushIndexer(
        domain="alpha.io",
        canonical_base="https://alpha.io",
        dist_dir=dist_dir,
        child_sitemap_ledger_path=ledger_path,
        tenant_id="alpha",
    )
    indexer.generate_multi_tenant_sitemaps(urls=urls, lastmod="2026-10-13")

    executed_commands: List[List[str]] = []

    class DummyCompletedProcess:
        def __init__(self, returncode: int = 0, stdout: str = "Submitted OK", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_subprocess_run(cmd: List[str], *args: Any, **kwargs: Any) -> DummyCompletedProcess:
        executed_commands.append(list(cmd))
        return DummyCompletedProcess(0, "Submitted OK", "")

    monkeypatch.setattr("pseofactory.indexer.subprocess.run", fake_subprocess_run)

    # First submission: every child sitemap + master sitemaps must be explicitly submitted
    sub_res_1 = indexer.submit_gsc_sitemaps(
        urls=urls,
        live=True,
        site="sc-domain:alpha.io",
        gsccli_bin="gsccli",
    )

    assert sub_res_1["status"] == "ACCEPTED"
    assert sub_res_1["verification"]["submitted_pages_only_filter_ready"] is True
    assert sub_res_1["verification"]["explicitly_submitted_all"] is True
    assert sub_res_1["sitemaps_submitted_count"] == sub_res_1["total_sitemaps_targeted"]
    assert sub_res_1["sitemaps_skipped_unchanged"] == 0

    submitted_urls = [entry["sitemap_url"] for entry in sub_res_1["submissions"]]
    assert "https://alpha.io/sitemap-products.xml" in submitted_urls
    assert "https://alpha.io/sitemap-categories.xml" in submitted_urls
    assert "https://alpha.io/sitemap-articles-2026-10.xml" in submitted_urls
    assert "https://alpha.io/sitemap-guides.xml" in submitted_urls
    assert "https://alpha.io/sitemap-hubs.xml" in submitted_urls
    assert "https://alpha.io/sitemap-leaves.xml" in submitted_urls
    assert "https://alpha.io/sitemap-index.xml" in submitted_urls
    assert "https://alpha.io/sitemap.xml" in submitted_urls

    # Verify exact gsccli sitemaps submit command invocations
    assert len(executed_commands) == len(submitted_urls)
    for cmd in executed_commands:
        assert cmd[:3] == ["gsccli", "sitemaps", "submit"]
        assert "-s" in cmd
        assert "sc-domain:alpha.io" in cmd

    # Second submission with identical content: idempotent ledger skips all unchanged sitemaps
    executed_commands.clear()
    sub_res_2 = indexer.submit_gsc_sitemaps(
        urls=urls,
        live=True,
        site="sc-domain:alpha.io",
        gsccli_bin="gsccli",
    )
    assert sub_res_2["status"] == "IDEMPOTENT_NO_OP"
    assert sub_res_2["sitemaps_submitted_count"] == 0
    assert sub_res_2["sitemaps_skipped_unchanged"] == sub_res_1["total_sitemaps_targeted"]
    assert sub_res_2["verification"]["submitted_pages_only_filter_ready"] is True
    assert len(executed_commands) == 0

    # Third submission after modifying ONLY products section: only changed sitemaps re-submit
    urls.append("https://alpha.io/products/new-sku-pricer")
    indexer.generate_multi_tenant_sitemaps(urls=urls, lastmod="2026-10-13")
    executed_commands.clear()
    sub_res_3 = indexer.submit_gsc_sitemaps(
        urls=urls,
        live=True,
        site="sc-domain:alpha.io",
        gsccli_bin="gsccli",
    )
    assert sub_res_3["status"] == "ACCEPTED"
    resubmitted_names = {
        item["sitemap_name"]
        for item in sub_res_3["submissions"]
        if item["status"] == "ACCEPTED"
    }
    skipped_names = {
        item["sitemap_name"]
        for item in sub_res_3["submissions"]
        if item["status"] == "IDEMPOTENT_SKIP"
    }
    assert "sitemap-products.xml" in resubmitted_names
    assert "sitemap-categories.xml" in skipped_names
    assert "sitemap-guides.xml" in skipped_names
    assert "sitemap-articles-2026-10.xml" in skipped_names


def test_section_exclusion_classifier_and_coverage_attribution() -> None:
    """
    Oracle 4: Unindexed drops ('Crawled - currently not indexed',
    'Discovered - currently not indexed', 404 dead routes, canonical mismatches,
    and thin content) map cleanly to their template section and child sitemap
    with isolated 'Submitted pages only' scope.
    """
    signals = [
        {
            "url": "https://alpha.io/products/legacy-widget",
            "coverage_state": "Crawled - currently not indexed",
            "fetch_state": "SUCCESSFUL",
        },
        {
            "url": "https://alpha.io/categories/obsolete-taxonomy",
            "coverage_state": "Not found (404)",
            "http_status": 404,
        },
        {
            "url": "https://alpha.io/articles/2026-09/thin-market-note",
            "coverage_state": "Crawled - currently not indexed",
            "word_count": 120,
        },
        {
            "url": "https://alpha.io/guides/mismatched-canonical-guide",
            "coverage_state": "Alternate page with proper canonical tag",
            "user_canonical": "https://alpha.io/guides/mismatched-canonical-guide",
            "google_canonical": "https://alpha.io/guides/other-guide",
        },
        {
            "url": "https://alpha.io/products/healthy-calculator",
            "coverage_state": "Submitted and indexed",
            "verdict": "PASS",
            "is_indexed": True,
        },
    ]

    report = SectionExclusionClassifier.attribute_coverage_by_section(
        signals,
        canonical_base="https://alpha.io",
        tenant_id="alpha",
    )
    assert report["total_records"] == 5
    assert report["total_unindexed"] == 4

    assert report["by_child_sitemap"]["sitemap-products.xml"]["unindexed_count"] == 1
    assert report["by_child_sitemap"]["sitemap-products.xml"]["indexed_count"] == 1
    assert report["by_child_sitemap"]["sitemap-categories.xml"]["unindexed_count"] == 1
    assert report["by_child_sitemap"]["sitemap-articles-2026-09.xml"]["unindexed_count"] == 1
    assert report["by_child_sitemap"]["sitemap-guides.xml"]["unindexed_count"] == 1

    # Verify individual exclusion classifications
    prod_drop = SectionExclusionClassifier.classify_exclusion(
        signals[0],
        canonical_base="https://alpha.io",
        tenant_id="alpha",
    )
    assert prod_drop["section"] == "products"
    assert prod_drop["child_sitemap"] == "sitemap-products.xml"
    assert prod_drop["child_sitemap_url"] == "https://alpha.io/sitemap-products.xml"
    assert prod_drop["submitted_pages_only_scope"] == "Submitted pages only (sitemap-products.xml)"
    assert prod_drop["classification"] == THIN_OR_ANSWER_DEFICIENCY
    assert prod_drop["is_crawled_not_indexed"] is True

    cat_drop = SectionExclusionClassifier.classify_exclusion(
        signals[1],
        canonical_base="https://alpha.io",
        tenant_id="alpha",
    )
    assert cat_drop["section"] == "categories"
    assert cat_drop["child_sitemap"] == "sitemap-categories.xml"
    assert cat_drop["classification"] == DEAD_ROUTE_IN_SITEMAP

    art_drop = SectionExclusionClassifier.classify_exclusion(
        signals[2],
        canonical_base="https://alpha.io",
        tenant_id="alpha",
    )
    assert art_drop["section"] == "articles"
    assert art_drop["date_bucket"] == "2026-09"
    assert art_drop["child_sitemap"] == "sitemap-articles-2026-09.xml"
    assert art_drop["classification"] == CONTENT_DEPTH_DEFICIT

    guide_drop = SectionExclusionClassifier.classify_exclusion(
        signals[3],
        canonical_base="https://alpha.io",
        tenant_id="alpha",
    )
    assert guide_drop["section"] == "guides"
    assert guide_drop["child_sitemap"] == "sitemap-guides.xml"
    assert guide_drop["classification"] == CANONICAL_TEMPLATE_DEFECT

    # Verify remediation overlay and prioritization preserve child sitemap attribution
    prioritized = prioritize_gsc_signals(signals[:4], tenant_id="alpha")
    assert len(prioritized) == 4
    first_spec = compile_remediation_overlay_spec(prioritized[0], tenant_id="alpha")
    assert first_spec["child_sitemap"].startswith("sitemap-")
    assert first_spec["submitted_pages_only_scope"] == f"Submitted pages only ({first_spec['child_sitemap']})"


def test_unified_atomic_workflow_dispatch_feedback_and_inspector(
    tmp_path: Path,
) -> None:
    """
    Oracle 5: PushIndexer.dispatch_automated_indexing, IndexingFeedbackLoop.run_feedback_cycle,
    and DailyIndexingInspector.run_inspection execute as a unified, atomic pipeline that
    generates child sitemaps, explicitly registers each child sitemap in GSC, and attributes
    per-section coverage.
    """
    base_dir = tmp_path / "sovereign"
    dist_dir = base_dir / "dist"
    ledger_dir = base_dir / ".agy"
    child_ledger_path = ledger_dir / "child_sitemap_push_ledger.json"

    page_specs = [
        ("index.html", "https://sovereign.io/", "Sovereign Hub"),
        ("products/margin-tool/index.html", "https://sovereign.io/products/margin-tool", "Margin Tool Product"),
        ("categories/calculators/index.html", "https://sovereign.io/categories/calculators", "Calculators Category"),
        ("articles/2026-10/rate-brief/index.html", "https://sovereign.io/articles/2026-10/rate-brief", "October Rate Brief"),
        ("guides/audit-handbook/index.html", "https://sovereign.io/guides/audit-handbook", "Audit Handbook Guide"),
    ]
    for rel_path, url, title in page_specs:
        _write_minimal_valid_html(dist_dir / rel_path, url, title=title)

    indexer = PushIndexer(
        domain="sovereign.io",
        canonical_base="https://sovereign.io",
        indexnow_key="a" * 32,
        base_dir=base_dir,
        dist_dir=dist_dir,
        ledger_path=ledger_dir / "pushed_urls.json",
        velocity_ledger_path=ledger_dir / "velocity.json",
        rollover_queue_path=ledger_dir / "rollover.json",
        audit_log_path=ledger_dir / "audit_log.json",
        child_sitemap_ledger_path=child_ledger_path,
        tenant_id="sovereign",
    )

    candidate_urls = [u for _, u, _ in page_specs]
    indexer.generate_multi_tenant_sitemaps(urls=candidate_urls, lastmod="2026-10-13")
    dispatch_res = indexer.dispatch_automated_indexing(
        urls=candidate_urls,
        live=False,
    )
    assert dispatch_res["status"] == "SUCCESS"
    assert dispatch_res["sitemap_registration"]["verification"]["submitted_pages_only_filter_ready"] is True
    submitted_sm_names = {s["sitemap_name"] for s in dispatch_res["child_sitemap_submissions"]}
    assert "sitemap-products.xml" in submitted_sm_names
    assert "sitemap-categories.xml" in submitted_sm_names
    assert "sitemap-articles-2026-10.xml" in submitted_sm_names
    assert "sitemap-guides.xml" in submitted_sm_names

    # Verify FeedbackLoop atomic cycle attributes section coverage and verifies child sitemaps
    loop = IndexingFeedbackLoop(
        property_id="sovereign",
        domain="sovereign.io",
        canonical_base="https://sovereign.io",
        base_dir=base_dir,
        dist_dir=dist_dir,
        indexer=indexer,
    )
    cycle_report = loop.run_feedback_cycle(
        dry_run=True,
        live=False,
        unindexed_urls=[
            {
                "url": "https://sovereign.io/products/margin-tool",
                "coverage_state": "Crawled - currently not indexed",
                "fetch_state": "SUCCESSFUL",
            },
            {
                "url": "https://sovereign.io/articles/2026-10/rate-brief",
                "coverage_state": "Crawled - currently not indexed",
                "word_count": 95,
            },
        ],
        skip_recompile=True,
    )
    assert cycle_report["status"] == "SUCCESS"
    sec_cov = cycle_report["section_coverage_attribution"]
    assert sec_cov["by_child_sitemap"]["sitemap-products.xml"]["unindexed_count"] == 1
    assert sec_cov["by_child_sitemap"]["sitemap-articles-2026-10.xml"]["unindexed_count"] == 1

    # Verify DailyIndexingInspector reports child sitemaps and section coverage
    inspector = DailyIndexingInspector(
        tenant_id="sovereign",
        base_dir=base_dir,
        agy_dir=ledger_dir,
        child_sitemap_ledger_path=child_ledger_path,
    )
    audit_section = inspector.audit_child_sitemaps_and_section_coverage(
        coverage_records=[
            {
                "url": "https://sovereign.io/guides/audit-handbook",
                "coverage_state": "Crawled - currently not indexed",
            }
        ],
    )
    assert audit_section["status"] == "PASS"
    assert audit_section["registration_verification"]["submitted_pages_only_filter_ready"] is True
    assert audit_section["section_coverage"]["by_child_sitemap"]["sitemap-guides.xml"]["unindexed_count"] == 1


def test_engine_drift_gate_and_no_hardcoded_tenant_routes(tmp_path: Path) -> None:
    """
    Oracle 6: Engine hash drift gate and AssetIntegrityEvaluator validate child sitemaps
    and sitemap-index.xml while still rejecting <sitemapindex> inside sitemap.xml,
    and preflight_airlock contains zero hardcoded tenant content routes.
    """
    # Check preflight_airlock source has no hardcoded /products, /collections, /blogs, /pages
    airlock_src = inspect.getsource(PushIndexer.preflight_airlock)
    for forbidden_route in ('"/products"', '"/collections"', '"/blogs"', '"/pages"'):
        assert forbidden_route not in airlock_src

    # Verify preflight_airlock allows legitimate /products and /guides routes
    dist_dir = tmp_path / "dist"
    _write_minimal_valid_html(
        dist_dir / "products" / "calc" / "index.html",
        "https://clean.io/products/calc",
        title="Clean Calculator",
    )
    build_multi_tenant_sitemaps(
        ["https://clean.io/products/calc"],
        dist_dir=dist_dir,
        canonical_base="https://clean.io",
        domain="clean.io",
        tenant_id="clean",
        lastmod="2026-10-13",
    )

    indexer = PushIndexer(domain="clean.io", canonical_base="https://clean.io", dist_dir=dist_dir)
    airlock_res = indexer.preflight_airlock(
        ["https://clean.io/products/calc"],
        dist_dir=dist_dir,
    )
    assert "https://clean.io/products/calc" in airlock_res.valid_urls
    assert len(airlock_res.quarantined_urls) == 0

    # Verify engine hash drift gate and AssetIntegrityEvaluator on child sitemaps + sitemap-index.xml
    state_file = tmp_path / ".agy" / "engine_hash.json"
    ledger_file = tmp_path / ".agy" / "asset_ledger.json"
    record_engine_hash(state_file)
    drift_check = detect_engine_drift(state_file)
    assert drift_check["drift_detected"] is False

    adapter = ConfigurablePropertyAdapter(
        property_id="clean_prop",
        domain="clean.io",
        canonical_base="https://clean.io",
        brand_name="Clean Sovereign",
        dist_dir=dist_dir,
    )
    asset_hashes = {
        p.relative_to(dist_dir).as_posix(): compute_asset_fingerprint(p)
        for p in adapter.list_assets()
    }
    record_asset_ledger(ledger_file, asset_hashes)

    evaluator = AssetIntegrityEvaluator(enforce_master_seo=False)
    report = evaluator.audit_all(adapter, ledger_path=ledger_file, state_file=state_file)
    assert report.status == "PASS"
    assert report.drifted_assets_count == 0

    # Verify RefactorCascadeEngine.map_dependencies includes all child sitemaps
    cascade = RefactorCascadeEngine(evaluator=evaluator)
    deps = cascade.map_dependencies(dist_dir / "products" / "calc" / "index.html", adapter)
    dep_names = {p.name for p in deps}
    assert "sitemap.xml" in dep_names
    assert "sitemap-index.xml" in dep_names
    assert "sitemap-products.xml" in dep_names
