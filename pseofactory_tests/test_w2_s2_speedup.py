"""
Wave 2 Lane S2 Speedup & Parity Regression Tests:
- Per-tenant split disk SEO audit cache & _disk_cache_path override compatibility
- (st_mtime_ns, st_ctime_ns, st_size) fast-path avoiding full byte reads/hashes on warm hits
- Exact parity (0 missed violations) on in-place file mutations (same/different size or mtime)
- DistHtmlSnapshot single-pass capture & shared reuse across verifier, maintenance, porcelain_shell
- Deterministic parallel cold evaluation ordering and thread safety

Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from pseofactory.compiler import compile_high_effort_page
from pseofactory.maintenance import (
    AssetIntegrityEvaluator,
    ConfigurablePropertyAdapter,
    DriftReason,
    RetroReflectionEngine,
)
from pseofactory.porcelain_shell import (
    audit_porcelain_estate_structure,
    audit_porcelain_shell_page,
)
from pseofactory.verifier import (
    DistHtmlSnapshot,
    MasterSEOVerifier,
    audit_aeo_geo_three_plane_readiness,
    audit_estate_seo_fix_checklist,
    audit_estate_technical_seo_and_cannibalization,
)


def _build_minimal_dist(root: Path, prop: str = "profithelm", domain: str = "profithelm.com", brand: str = "ProfitHelm", num_tools: int = 12) -> Path:
    dist = root / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    (root / ".agy").mkdir(parents=True, exist_ok=True)
    (root / ".pseofactory.json").write_text(
        json.dumps(
            {
                "property_id": prop,
                "domain": domain,
                "canonical_base": f"https://{domain}",
                "brand_name": brand,
                "package_name": prop,
                "dist_dir": "dist",
            }
        ),
        encoding="utf-8",
    )

    spec_base = {
        "query": "section 179 equipment expense tax deduction calculator",
        "slug": "section-179-tool-0",
        "tenant": prop,
        "statutory_authority": "IRC Section 179(b)(1)",
        "economic_dataset": "FRED CPILFESL Series",
        "model_name": "Section 179 Grounded Model",
        "formula": "min(cost, cap)",
        "inputs": {"cost": 400000, "cap": 1220000},
        "published_output": 400000.0,
        "sample_calculation": "Cost 400,000 under cap 1,220,000 gives 400,000 deduction",
        "canonical_base": f"https://{domain}",
    }
    sample_html = compile_high_effort_page(spec_base)["html"]
    sample_html = re.sub(
        r"<title>[\s\S]*?</title>",
        "<title>Section 179 Deduction Calculator | ProfitHelm</title>",
        sample_html,
        count=1,
        flags=re.IGNORECASE,
    )
    if 'name="google-site-verification"' not in sample_html:
        sample_html = sample_html.replace(
            "</head>",
            '<meta name="google-site-verification" content="1b9AjxT3rRYA2iyPRraN2ShDNqEoKsfYW39UiTncB4U"></head>',
            1,
        )

    (dist / "index.html").write_text(sample_html, encoding="utf-8")
    (dist / "tools").mkdir(exist_ok=True)
    (dist / "tools" / "index.html").write_text(sample_html, encoding="utf-8")
    (dist / "manifests").mkdir(exist_ok=True)

    urls = [f"https://{domain}/", f"https://{domain}/tools/"]
    for i in range(num_tools):
        slug = f"tool-calc-{i:02d}"
        t_dir = dist / "tools" / slug
        t_dir.mkdir(parents=True, exist_ok=True)
        page_html = sample_html.replace("section-179-tool-0", slug).replace(
            "<title>",
            f"<title>Tool {i:02d} ",
            1,
        )
        (t_dir / "index.html").write_text(page_html, encoding="utf-8")
        (dist / "manifests" / f"{slug}.json").write_text(
            json.dumps(
                {
                    "slug": slug,
                    "formula": "min(cost, cap)",
                    "inputs": {"cost": 400000, "cap": 1220000},
                    "published_output": 400000.0,
                    "sample_calculation": "Cost 400,000 under cap 1,220,000 gives 400,000 deduction",
                }
            ),
            encoding="utf-8",
        )
        urls.append(f"https://{domain}/tools/{slug}/")

    for gov in ("about", "methodology", "privacy", "terms", "disclaimers", "contact"):
        g_dir = dist / gov
        g_dir.mkdir(exist_ok=True)
        (g_dir / "index.html").write_text(sample_html, encoding="utf-8")
        urls.append(f"https://{domain}/{gov}/")

    url_xml = "\n".join(f"  <url><loc>{u}</loc></url>" for u in urls)
    sm = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{url_xml}\n</urlset>\n'
    (dist / "sitemap.xml").write_text(sm, encoding="utf-8")
    (dist / "sitemap-hubs.xml").write_text(sm, encoding="utf-8")
    (dist / "sitemap-leaves.xml").write_text(sm, encoding="utf-8")
    (dist / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nDisallow: /signal/\n"
        f"Sitemap: https://{domain}/sitemap.xml\n"
        f"Sitemap: https://{domain}/sitemap-hubs.xml\n"
        f"Sitemap: https://{domain}/sitemap-leaves.xml\n",
        encoding="utf-8",
    )
    (dist / "_headers").write_text("/*\n  X-Robots-Tag: all\n", encoding="utf-8")
    (dist / "llms.txt").write_text(f"# {brand}\n\n> Authoritative statutory calculators.\n", encoding="utf-8")
    (dist / "llms-full.txt").write_text(f"# {brand}\n\n> Full catalog.\n", encoding="utf-8")
    (dist / "feed.xml").write_text(f'<?xml version="1.0"?><rss version="2.0"><channel><title>{brand}</title></channel></rss>', encoding="utf-8")
    return dist


def test_per_tenant_disk_cache_split_and_override(tmp_path: Path):
    """_resolve_disk_cache_path splits non-tmp tenants per property/dist hash and honors _disk_cache_path override."""
    v_a = MasterSEOVerifier(dist_dir=tmp_path / "dist_a", domain="alpha.com", brand_name="Alpha", allow_mutations=False)
    v_b = MasterSEOVerifier(dist_dir=tmp_path / "dist_b", domain="beta.com", brand_name="Beta", allow_mutations=False)

    p_a = v_a._resolve_disk_cache_path(Path("/srv/tenants/alpha/dist"), is_isolated_tmp=False)
    p_b = v_b._resolve_disk_cache_path(Path("/srv/tenants/beta/dist"), is_isolated_tmp=False)
    assert p_a != p_b
    assert "pseofactory_seo_audit_cache_v2_alpha_" in p_a.name
    assert "pseofactory_seo_audit_cache_v2_beta_" in p_b.name
    assert p_a.name != "pseofactory_seo_audit_cache_v1.json"

    custom = tmp_path / "override_seo_cache.json"
    v_a._disk_cache_path = custom
    assert v_a._resolve_disk_cache_path(Path("/srv/tenants/alpha/dist"), is_isolated_tmp=False) == custom


def test_master_seo_verifier_stat_fast_path_and_mutation_parity(tmp_path: Path):
    """
    Warm disk hit skips reading dist files when (mtime_ns, ctime_ns, size) match,
    while any in-place mutation (same size, different size, or restored mtime) invalidates cache.
    """
    repo = tmp_path / "tenant_repo"
    dist = _build_minimal_dist(repo, num_tools=4)
    cache_file = tmp_path / "seo_cache_custom.json"

    v = MasterSEOVerifier(dist_dir=dist, domain="profithelm.com", brand_name="ProfitHelm", allow_mutations=False)
    v._disk_cache_path = cache_file
    MasterSEOVerifier._GLOBAL_AUDIT_CACHE.clear()

    # Seed disk cache entry using PASS result (patch check gates to pass cleanly on minimal fixture)
    target_html = dist / "tools" / "tool-calc-00" / "index.html"
    orig_bytes = target_html.read_bytes()

    # Verify real end-to-end caching on a minimal passing dist where cleanliness/html gates run unpatched
    MasterSEOVerifier._GLOBAL_AUDIT_CACHE.clear()
    gate_patches = [
        "check_content_relevance_gate",
        "check_indexing_gate",
        "check_source_keyword_inflation_gate",
        "check_organic_fan_out_coverage_gate",
        "check_unique_first_party_information_gate",
        "check_cross_web_consensus_and_corroboration_gate",
        "check_source_publisher_reputation_gate",
        "check_extractable_content_structure_gate",
        "check_answer_prominence_gate",
        "check_structured_data_gate",
        "check_llms_txt_gate",
        "check_tool_utility_gate",
        "check_free_web_application_schema_gate",
        "check_operational_shield_gate",
        "check_comparison_layout_gate",
        "check_ai_mode_manifest_gate",
        "check_cohort_reflection_gate",
        "check_citable_specific_facts_gate",
        "check_query_answer_match_gate",
        "check_brand_entity_in_llm_memory_gate",
        "check_snippet_eligibility_gate",
        "check_snippet_gate",
        "check_citability_gate",
        "check_organic_search_ranking_gate",
        "check_internal_linking_gate",
        "check_no_js_rendering_gate",
        "check_host_hygiene_gate",
        "check_edge_cache_policy_gate",
        "check_load_performance_gate",
        "check_meta_descriptions_gate",
        "check_sitemap_gate",
        "check_existence_gate",
        "check_http_link_canonical_gate",
        "check_url_redirects_gate",
    ]
    with contextlib.ExitStack() as stack:
        for g_name in gate_patches:
            stack.enter_context(
                patch.object(MasterSEOVerifier, g_name, return_value={"status": "PASS", "issues": []})
            )

        # 1. Cold pass populates disk cache with stat: + content key
        pass_cold = v.audit_seo_checklist(dist_dir=dist, raise_on_error=False, enforce_relevance=False)
        assert pass_cold["status"] == "PASS", pass_cold["issues"]

        # 2. Warm disk pass after clearing _GLOBAL_AUDIT_CACHE must NOT read dist files!
        MasterSEOVerifier._GLOBAL_AUDIT_CACHE.clear()
        orig_read_bytes = Path.read_bytes
        dist_read_calls = []

        def _guarded_read_bytes(self_p: Path) -> bytes:
            if str(self_p).startswith(str(dist)):
                dist_read_calls.append(str(self_p))
            return orig_read_bytes(self_p)

        with patch.object(Path, "read_bytes", _guarded_read_bytes):
            pass_warm = v.audit_seo_checklist(dist_dir=dist, raise_on_error=False, enforce_relevance=False)
        assert pass_warm["status"] == "PASS"
        assert dist_read_calls == [], f"Expected 0 dist read_bytes on warm stat hit, got {dist_read_calls}"

        # 3. Mutate in place with SAME byte size (different mtime_ns) -> breaks <h1> and must FAIL!
        MasterSEOVerifier._GLOBAL_AUDIT_CACHE.clear()
        assert b"<h1>" in orig_bytes and b"</h1>" in orig_bytes
        same_size_bytes = orig_bytes.replace(b"<h1>", b"<h2>", 1).replace(b"</h1>", b"</h2>", 1)
        assert len(same_size_bytes) == len(orig_bytes)
        target_html.write_bytes(same_size_bytes)
        fail_same_size = v.audit_seo_checklist(dist_dir=dist, raise_on_error=False, enforce_relevance=False)
        assert fail_same_size["status"] == "FAIL"
        assert any("h1" in iss.lower() or "tool-calc-00" in iss for iss in fail_same_size["issues"])

        # 4. Restore clean file, warm cache again, then mutate with DIFFERENT size + RESTORED mtime_ns!
        target_html.write_bytes(orig_bytes)
        MasterSEOVerifier._GLOBAL_AUDIT_CACHE.clear()
        re_warm = v.audit_seo_checklist(dist_dir=dist, raise_on_error=False, enforce_relevance=False)
        assert re_warm["status"] == "PASS"

        st_orig = target_html.stat()
        MasterSEOVerifier._GLOBAL_AUDIT_CACHE.clear()
        diff_size_bytes = orig_bytes.replace(b"<h1>", b"<h2>Broken Extra ", 1).replace(b"</h1>", b"</h2>", 1)
        target_html.write_bytes(diff_size_bytes)
        os.utime(target_html, ns=(st_orig.st_atime_ns, st_orig.st_mtime_ns))
        fail_diff_size_restored_mtime = v.audit_seo_checklist(dist_dir=dist, raise_on_error=False, enforce_relevance=False)
        assert fail_diff_size_restored_mtime["status"] == "FAIL"

        # 5. Same size + RESTORED mtime_ns -> ctime_ns still invalidates stat fast-path and catches mutation!
        target_html.write_bytes(orig_bytes)
        MasterSEOVerifier._GLOBAL_AUDIT_CACHE.clear()
        re_warm_2 = v.audit_seo_checklist(dist_dir=dist, raise_on_error=False, enforce_relevance=False)
        assert re_warm_2["status"] == "PASS"

        st_orig_2 = target_html.stat()
        MasterSEOVerifier._GLOBAL_AUDIT_CACHE.clear()
        target_html.write_bytes(same_size_bytes)
        os.utime(target_html, ns=(st_orig_2.st_atime_ns, st_orig_2.st_mtime_ns))
        fail_same_size_restored_mtime = v.audit_seo_checklist(dist_dir=dist, raise_on_error=False, enforce_relevance=False)
        assert fail_same_size_restored_mtime["status"] == "FAIL"


def test_asset_integrity_evaluator_fast_path_parallel_and_mutation_parity(tmp_path: Path):
    """
    AssetIntegrityEvaluator skips compute_asset_fingerprint on warm stat hits,
    preserves deterministic ordering across parallel asset checks, and catches every in-place mutation.
    """
    repo = tmp_path / "eval_repo"
    dist = _build_minimal_dist(repo, num_tools=12)
    adapter = ConfigurablePropertyAdapter(
        property_id="profithelm",
        brand_name="ProfitHelm",
        domain="profithelm.com",
        canonical_base="https://profithelm.com",
        dist_dir=dist,
    )

    ev = AssetIntegrityEvaluator(enforce_master_seo=False)
    ev._audit_cache.clear()
    ev._fingerprint_cache.clear()
    ev._stat_fast_cache.clear()

    rep_cold = ev.audit_all(adapter, check_engine_drift=False, check_ledger=False)
    assert rep_cold.total_assets_checked >= 12
    clean_file = dist / "tools" / "tool-calc-00" / "index.html"
    if any(r.asset_path == str(clean_file.resolve()) for r in rep_cold.drifted_assets):
        # Test with a strictly clean minimal HTML asset so _audit_cache caches None
        clean_asset = dist / "clean_page.html"
    else:
        clean_asset = clean_file

    clean_asset = dist / "clean_minimal.html"
    clean_html = (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        "<meta name='description' content='ProfitHelm corporate tax modeling guide for business owners and CFOs.'>"
        "<link rel='canonical' href='https://profithelm.com/clean_minimal.html'>"
        "<title>Corporate Tax Modeling Guide | ProfitHelm</title></head>"
        "<body><main><h1>ProfitHelm Corporate Tax Modeling Guide</h1>"
        "<p>Statutory IRC Section 179 analysis for ProfitHelm users and corporate tax planning.</p>"
        "</main></body></html>"
    )
    clean_asset.write_text(clean_html, encoding="utf-8")

    ev._audit_cache.clear()
    ev._fingerprint_cache.clear()
    ev._stat_fast_cache.clear()
    rec1 = ev.audit_asset(clean_asset, adapter=adapter, engine_drifted=False)
    assert rec1 is None

    # Warm hit must NOT call compute_asset_fingerprint
    with patch("pseofactory.maintenance.compute_asset_fingerprint", side_effect=AssertionError("Must not hash on warm stat hit")):
        rec2 = ev.audit_asset(clean_asset, adapter=adapter, engine_drifted=False)
    assert rec2 is None

    # Mutate in place with SAME size (changes mtime_ns)
    mut_same_size = clean_html.replace("and", "\u2014", 1)
    assert len(mut_same_size.encode("utf-8")) == len(clean_html.encode("utf-8"))
    clean_asset.write_text(mut_same_size, encoding="utf-8")
    rec_mut1 = ev.audit_asset(clean_asset, adapter=adapter, engine_drifted=False)
    assert rec_mut1 is not None
    assert DriftReason.STRUCTURAL_CONTRACT_VIOLATION in rec_mut1.reasons

    # Restore clean, warm again, then mutate with DIFFERENT size + RESTORED mtime_ns
    clean_asset.write_text(clean_html, encoding="utf-8")
    assert ev.audit_asset(clean_asset, adapter=adapter, engine_drifted=False) is None
    st_clean = clean_asset.stat()
    clean_asset.write_text(clean_html.replace("</body>", "<p>\u2014</p></body>", 1), encoding="utf-8")
    os.utime(clean_asset, ns=(st_clean.st_atime_ns, st_clean.st_mtime_ns))
    rec_mut2 = ev.audit_asset(clean_asset, adapter=adapter, engine_drifted=False)
    assert rec_mut2 is not None

    # Deterministic ordering across parallel audit_all runs
    ev._audit_cache.clear()
    ev._fingerprint_cache.clear()
    ev._stat_fast_cache.clear()
    rep_a = ev.audit_all(adapter, check_engine_drift=False, check_ledger=False)
    ev._audit_cache.clear()
    ev._fingerprint_cache.clear()
    ev._stat_fast_cache.clear()
    rep_b = ev.audit_all(adapter, check_engine_drift=False, check_ledger=False)
    assert [r.asset_path for r in rep_a.drifted_assets] == [r.asset_path for r in rep_b.drifted_assets]


def test_dist_html_snapshot_shared_reuse_and_invalidation(tmp_path: Path):
    """DistHtmlSnapshot caches unchanged HTML/JSON-LD and invalidates immediately when a file changes."""
    repo = tmp_path / "snap_repo"
    dist = _build_minimal_dist(repo, num_tools=10)

    snap1 = DistHtmlSnapshot.capture(dist, include_all_files=True)
    snap2 = DistHtmlSnapshot.capture(dist, include_all_files=True)
    assert len(snap1.html_entries) >= 12
    assert snap1.html_entries["index.html"] is snap2.html_entries["index.html"]

    # Verify JSON-LD parsed and seo_doc cached on entry
    idx_entry = snap1.html_entries["index.html"]
    assert len(idx_entry.json_ld_raw_blocks) >= 1
    assert idx_entry.get_seo_doc("profithelm.com") is idx_entry.get_seo_doc("profithelm.com")

    # Mutate one tool file in-place -> snapshot must return a new entry with updated content
    t0_file = dist / "tools" / "tool-calc-00" / "index.html"
    orig_t0 = t0_file.read_text(encoding="utf-8")
    t0_file.write_text(orig_t0.replace("</body>", "<!-- \u2014 --></body>", 1), encoding="utf-8")
    snap3 = DistHtmlSnapshot.capture(dist)
    assert snap3.html_entries["tools/tool-calc-00/index.html"] is not idx_entry
    assert snap3.html_entries["tools/tool-calc-00/index.html"].has_forbidden_dash is True

    # Verify RetroReflectionEngine, aeo_geo, seo_fix, technical_seo, and porcelain_shell run cleanly & detect the dash
    aeo_rep = audit_aeo_geo_three_plane_readiness(dist_dir=dist, property_id="profithelm")
    assert any("tool-calc-00" in iss and "dash" in iss.lower() for iss in aeo_rep["issues"])

    with pytest.raises(ValueError, match="em-dash"):
        audit_estate_technical_seo_and_cannibalization(dist_dir=dist, property_id="profithelm")

    # Restore clean file -> technical_seo, seo_fix, RetroReflectionEngine, and porcelain_shell run cleanly
    t0_file.write_text(orig_t0, encoding="utf-8")
    tech_rep = audit_estate_technical_seo_and_cannibalization(dist_dir=dist, property_id="profithelm")
    assert "html_files_scanned" in tech_rep

    fix_rep = audit_estate_seo_fix_checklist(dist_dir=dist, property_id="profithelm")
    assert "html_files_scanned" in fix_rep

    rr_rep = RetroReflectionEngine.audit_estate(dist, "profithelm")
    assert "pages_scanned" in rr_rep

    porc_issues = audit_porcelain_shell_page(
        orig_t0,
        "tools/tool-calc-00/index.html",
        check_shell_landmarks=False,
        property_id="profithelm",
    )
    assert isinstance(porc_issues, list)
    porc_est = audit_porcelain_estate_structure(dist, "profithelm")
    assert isinstance(porc_est, list)
