"""
Regression tests ensuring non-tool, governance, and utility routes remain strictly
excluded from striking-distance calculator overlays, RetroReflectionEngine.retrofit_html,
and calculator manifest generation across all SEO workflows and local reflect passes.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pseofactory.compiler import compile_gainhelm_estate
from pseofactory.gsc_remediation import (
    evaluate_expired_overlays,
    inject_overlay_into_html,
    rollback_degraded_overlay_from_html,
)
from pseofactory.maintenance import RetroReflectionEngine
from pseofactory.porcelain_shell import compile_tenant_porcelain_estate
import pseofactory.seo_growth_loops as sgl


NON_TOOL_ROUTES = (
    ("index", "/"),
    ("tools", "/tools"),
    ("about", "/about"),
    ("privacy", "/privacy"),
    ("terms", "/terms"),
    ("contact", "/contact"),
    ("disclaimers", "/disclaimers"),
    ("methodology", "/methodology"),
    ("404", "/404"),
    ("404.html", "/404.html"),
    ("signal", "/signal"),
    ("static/signal", "/static/signal"),
)


def _extract_title(html_text: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else ""


def _extract_dates_modified(html_text: str) -> list[str]:
    return re.findall(r'"dateModified"\s*:\s*"([^"]+)"', html_text)


def test_gainhelm_governance_parity_under_seo_growth_workflows_and_reflect_pipeline(tmp_path: Path) -> None:
    """
    Running compile_gainhelm_estate + simulated GSC impressions on /methodology/,
    /disclaimers/, and /tools/soc-2-audit-cost-calculator/ through
    run_all_seo_growth_workflows + RetroReflectionEngine.retrofit_estate +
    compile_tenant_porcelain_estate must keep /methodology/ and /disclaimers/
    byte-for-byte identical to a clean CI compile_gainhelm_estate build.
    """
    clean_root = tmp_path / "clean_ci"
    compile_gainhelm_estate(clean_root)
    clean_dist = clean_root / "dist"
    clean_methodology = (clean_dist / "methodology" / "index.html").read_text(encoding="utf-8")
    clean_disclaimers = (clean_dist / "disclaimers" / "index.html").read_text(encoding="utf-8")

    assert _extract_title(clean_methodology) == "Enterprise Cyber Compliance & Audit Cost | GainHelm"
    assert _extract_title(clean_disclaimers) == "Cyber Compliance Regulatory Notices &amp; Disclaimers | GainHelm"
    assert "2026-10-31" in _extract_dates_modified(clean_methodology)
    assert "2026-10-31" in _extract_dates_modified(clean_disclaimers)
    assert "ISO/IEC 27006-1:2024" in clean_methodology and "<table" in clean_methodology.lower()
    assert "Statutory Disclosures &amp; Regulatory Authorities" in clean_disclaimers and "<table" in clean_disclaimers.lower()
    assert 'id="calculation-manifest"' not in clean_methodology
    assert 'id="calculation-manifest"' not in clean_disclaimers

    local_root = tmp_path / "local_reflect"
    compile_gainhelm_estate(local_root)
    local_dist = local_root / "dist"

    simulated_gsc_rows = [
        {
            "query": "gainhelm cyber compliance",
            "canonical_path": "/",
            "page": "https://gainhelm.com/",
            "impressions": 40,
            "clicks": 2,
            "position": 7.5,
        },
        {
            "query": "cyber compliance calculators",
            "canonical_path": "/tools",
            "page": "https://gainhelm.com/tools/",
            "impressions": 30,
            "clicks": 1,
            "position": 9.0,
        },
        {
            "query": "methodology",
            "canonical_path": "/methodology",
            "page": "https://gainhelm.com/methodology/",
            "impressions": 25,
            "clicks": 0,
            "position": 11.2,
        },
        {
            "query": "disclaimers",
            "canonical_path": "/disclaimers",
            "page": "https://gainhelm.com/disclaimers/",
            "impressions": 18,
            "clicks": 0,
            "position": 13.4,
        },
        {
            "query": "about gainhelm",
            "canonical_path": "/about",
            "page": "https://gainhelm.com/about/",
            "impressions": 12,
            "clicks": 0,
            "position": 14.0,
        },
        {
            "query": "privacy policy",
            "canonical_path": "/privacy",
            "page": "https://gainhelm.com/privacy/",
            "impressions": 10,
            "clicks": 0,
            "position": 15.0,
        },
        {
            "query": "terms of use",
            "canonical_path": "/terms",
            "page": "https://gainhelm.com/terms/",
            "impressions": 10,
            "clicks": 0,
            "position": 15.0,
        },
        {
            "query": "contact gainhelm",
            "canonical_path": "/contact",
            "page": "https://gainhelm.com/contact/",
            "impressions": 10,
            "clicks": 0,
            "position": 15.0,
        },
        {
            "query": "404 page not found",
            "canonical_path": "/404.html",
            "page": "https://gainhelm.com/404.html",
            "impressions": 8,
            "clicks": 0,
            "position": 22.0,
        },
        {
            "query": "gainhelm signal",
            "canonical_path": "/signal",
            "page": "https://gainhelm.com/signal/",
            "impressions": 8,
            "clicks": 0,
            "position": 20.0,
        },
        {
            "query": "gainhelm static signal",
            "canonical_path": "/static/signal",
            "page": "https://gainhelm.com/static/signal/",
            "impressions": 8,
            "clicks": 0,
            "position": 20.0,
        },
        {
            "query": "soc 2 audit cost calculator",
            "canonical_path": "/tools/soc-2-audit-cost-calculator",
            "page": "https://gainhelm.com/tools/soc-2-audit-cost-calculator/",
            "impressions": 85,
            "clicks": 5,
            "position": 6.5,
        },
    ]

    wf_summary = sgl.run_all_seo_growth_workflows(
        property_id="gainhelm",
        repo_root=local_root,
        dist_dir=local_dist,
        live_queries=simulated_gsc_rows,
        apply_overlays=True,
        persist=True,
        live_gsc=False,
    )
    assert wf_summary["status"] == "PASS"

    RetroReflectionEngine.retrofit_estate(local_dist, "gainhelm", canonical_base="https://gainhelm.com")
    compile_tenant_porcelain_estate(local_dist, property_id="gainhelm", repo_root=local_root)

    after_methodology = (local_dist / "methodology" / "index.html").read_text(encoding="utf-8")
    after_disclaimers = (local_dist / "disclaimers" / "index.html").read_text(encoding="utf-8")

    assert after_methodology == clean_methodology
    assert after_disclaimers == clean_disclaimers
    assert _extract_title(after_methodology) == "Enterprise Cyber Compliance & Audit Cost | GainHelm"
    assert _extract_title(after_disclaimers) == "Cyber Compliance Regulatory Notices &amp; Disclaimers | GainHelm"
    assert set(_extract_dates_modified(after_methodology)) == {"2026-10-31"}
    assert set(_extract_dates_modified(after_disclaimers)) == {"2026-10-31"}
    assert 'id="calculation-manifest"' not in after_methodology
    assert 'id="calculation-manifest"' not in after_disclaimers

    for stem_bad in (
        "index",
        "root",
        "tools",
        "tools-directory",
        "about",
        "privacy",
        "terms",
        "contact",
        "disclaimers",
        "methodology",
        "404",
        "404.html",
        "signal",
        "static-signal",
    ):
        assert not (local_root / ".agy" / "overlays" / f"{stem_bad}.json").exists()
        assert not (local_root / "content" / "overlays" / f"{stem_bad}.json").exists()
        assert not (local_dist / "manifests" / f"{stem_bad}.json").exists()

    # Valid tool calculator still receives normal overlay & retrofit handling
    assert (local_root / ".agy" / "overlays" / "soc-2-audit-cost-calculator.json").is_file()
    assert (local_dist / "manifests" / "soc-2-audit-cost-calculator.json").is_file()
    soc2_html = (local_dist / "tools" / "soc-2-audit-cost-calculator" / "index.html").read_text(encoding="utf-8")
    assert 'id="calculation-manifest"' in soc2_html
    assert 'id="gsc-striking-overlay"' in soc2_html
    assert RetroReflectionEngine.audit_estate(local_dist, "gainhelm")["status"] == "PASS"


def test_stale_non_tool_overlays_and_manifests_pruned_without_polluting_governance(tmp_path: Path) -> None:
    """
    Pre-existing stale non-tool overlays (including DEGRADED_ROLLED_BACK) in .agy/overlays/
    and content/overlays/ plus bogus dist/manifests/{methodology,disclaimers,404.html}.json
    must be pruned cleanly and never overwrite governance titles, dates, or tables.
    """
    repo_root = tmp_path / "stale_gh"
    compile_gainhelm_estate(repo_root)
    dist_dir = repo_root / "dist"

    clean_methodology = (dist_dir / "methodology" / "index.html").read_text(encoding="utf-8")
    clean_disclaimers = (dist_dir / "disclaimers" / "index.html").read_text(encoding="utf-8")

    agy_ov_dir = repo_root / ".agy" / "overlays"
    content_ov_dir = repo_root / "content" / "overlays"
    agy_ov_dir.mkdir(parents=True, exist_ok=True)
    content_ov_dir.mkdir(parents=True, exist_ok=True)

    degraded_methodology_ov = {
        "slug": "methodology",
        "property_id": "gainhelm",
        "tenant_id": "gainhelm",
        "target_url": "https://gainhelm.com/methodology/",
        "query": "methodology",
        "status": "DEGRADED_ROLLED_BACK",
        "rolled_back_title_rewrite": "Methodology (GRC Audit Rules) | GainHelm",
        "rolled_back_modifier": "GRC Audit Rules",
        "created_at": "2025-01-01T00:00:00+00:00",
        "locked_until": "2025-02-01T00:00:00+00:00",
        "baseline_impressions": 20,
        "baseline_position": 10.0,
    }
    active_disclaimers_ov = {
        "slug": "disclaimers",
        "property_id": "gainhelm",
        "tenant_id": "gainhelm",
        "target_url": "https://gainhelm.com/disclaimers/",
        "query": "disclaimers",
        "status": "ACTIVE_LOCKED",
        "title_rewrite": "Disclaimers Calculator Model | GainHelm",
        "created_at": "2026-11-15T00:00:00+00:00",
        "locked_until": "2099-01-01T00:00:00+00:00",
        "baseline_impressions": 20,
        "baseline_position": 10.0,
    }

    (agy_ov_dir / "methodology.json").write_text(json.dumps(degraded_methodology_ov, indent=2), encoding="utf-8")
    (content_ov_dir / "methodology.json").write_text(json.dumps(degraded_methodology_ov, indent=2), encoding="utf-8")
    (agy_ov_dir / "disclaimers.json").write_text(json.dumps(active_disclaimers_ov, indent=2), encoding="utf-8")
    (content_ov_dir / "disclaimers.json").write_text(json.dumps(active_disclaimers_ov, indent=2), encoding="utf-8")

    for extra_stem in ("404", "about", "privacy", "terms", "contact", "tools", "index", "signal"):
        (agy_ov_dir / f"{extra_stem}.json").write_text(
            json.dumps({"slug": extra_stem, "status": "DEGRADED_ROLLED_BACK", "rolled_back_title_rewrite": "Bad Title"}),
            encoding="utf-8",
        )
    (content_ov_dir / "static-signal.json").write_text(
        json.dumps({"slug": "static/signal", "status": "ACTIVE_LOCKED", "target_url": "https://gainhelm.com/static/signal/"}),
        encoding="utf-8",
    )

    manifests_dir = dist_dir / "manifests"
    for bogus_mf in ("methodology.json", "disclaimers.json", "404.html.json", "404.json", "about.json", "signal.json"):
        (manifests_dir / bogus_mf).write_text(
            json.dumps({"slug": bogus_mf.removesuffix(".json"), "formula": "a+b", "inputs": {"a": 1, "b": 2}, "published_output": 3}),
            encoding="utf-8",
        )

    # Preserve non-governance manifests emitted by tenant builders (e.g. prexvo statutory-repayment-assistance-plan.json)
    preserved_extra_manifest = manifests_dir / "statutory-repayment-assistance-plan.json"
    preserved_extra_manifest.write_text(
        json.dumps(
            {
                "slug": "statutory-repayment-assistance-plan",
                "model_name": "Statutory RAP Baseline Model",
                "entity_type": "FinancialProductOrService",
                "formula": "round(max(0, agi - 35212.5) * 0.1 / 12, 2)",
                "inputs": {"agi": 65000},
                "published_output": 248.23,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    evaluate_expired_overlays(
        site_url="sc-domain:gainhelm.com",
        base_dir=repo_root,
        live_queries=[],
        persist=True,
        live_gsc=False,
    )
    RetroReflectionEngine.retrofit_estate(dist_dir, "gainhelm", canonical_base="https://gainhelm.com")
    compile_tenant_porcelain_estate(dist_dir, property_id="gainhelm", repo_root=repo_root)

    assert list(agy_ov_dir.glob("*.json")) == []
    assert list(content_ov_dir.glob("*.json")) == []

    for bogus_mf in ("methodology.json", "disclaimers.json", "404.html.json", "404.json", "about.json", "signal.json"):
        assert not (manifests_dir / bogus_mf).exists(), f"Bogus manifest should be pruned: {bogus_mf}"

    assert (manifests_dir / "soc-2-audit-cost-calculator.json").is_file()
    assert preserved_extra_manifest.is_file()

    assert (dist_dir / "methodology" / "index.html").read_text(encoding="utf-8") == clean_methodology
    assert (dist_dir / "disclaimers" / "index.html").read_text(encoding="utf-8") == clean_disclaimers


def test_gated_workflow_helpers_skip_retrofit_html_and_overlay_mutation_on_non_tool_routes(tmp_path: Path) -> None:
    """
    Verifies directly that every gated workflow helper in seo_growth_loops.py,
    overlay inject/rollback helpers in gsc_remediation.py, and RetroReflectionEngine
    classify and skip non-tool/governance/utility HTML without calling retrofit_html
    or creating overlays/manifests.
    """
    gated_retrofit_fn = getattr(sgl, "_retrofit_tool_html_if_eligible", None)

    repo_root = tmp_path / "gated_gh"
    compile_gainhelm_estate(repo_root)
    dist_dir = repo_root / "dist"

    # Seed 404/index, signal, and static/signal pages so every route exists on disk
    for extra_rel in ("signal/index.html", "static/signal/index.html"):
        p = dist_dir / extra_rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            f"<!DOCTYPE html><html><head><title>Signal | GainHelm</title>"
            f"<link rel='canonical' href='https://gainhelm.com/{extra_rel.removesuffix('index.html')}'></head>"
            f"<body><main><h1>Signal</h1></main></body></html>",
            encoding="utf-8",
        )

    # Seed a remediation queue targeting non-tool routes
    agy_dir = repo_root / ".agy"
    agy_dir.mkdir(parents=True, exist_ok=True)
    (agy_dir / "gsc_remediation_queue.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "target_url": f"https://gainhelm.com{route_path}",
                        "slug": route_slug,
                        "query": f"gainhelm {route_slug}",
                        "impressions": 40,
                        "clicks": 0,
                        "position": 10.0,
                    }
                    for route_slug, route_path in NON_TOOL_ROUTES
                ]
            }
        ),
        encoding="utf-8",
    )

    brief_rows = [
        {
            "query": f"gainhelm {route_slug}",
            "canonical_path": route_path,
            "canonical_url": f"https://gainhelm.com{route_path if route_path.endswith(('/', '.html')) else route_path + '/'}",
            "impressions": 30,
            "clicks": 0,
            "position": 9.0,
        }
        for route_slug, route_path in NON_TOOL_ROUTES
    ]
    brief_rep = sgl.compile_search_opportunity_briefs(
        property_id="gainhelm",
        repo_root=repo_root,
        dist_dir=dist_dir,
        consolidated_gsc={"current_rows": brief_rows, "baseline_rows": []},
        apply_overlays=True,
        persist=True,
    )
    assert brief_rep["briefs_count"] == 0
    assert brief_rep["overlays_compiled_count"] == 0
    assert not list((agy_dir / "overlays").glob("*.json")) if (agy_dir / "overlays").is_dir() else True

    # Direct checks on non-tool HTML files through gated workflow helpers
    non_tool_targets = [
        ("methodology", dist_dir / "methodology" / "index.html"),
        ("disclaimers", dist_dir / "disclaimers" / "index.html"),
        ("about", dist_dir / "about" / "index.html"),
        ("privacy", dist_dir / "privacy" / "index.html"),
        ("terms", dist_dir / "terms" / "index.html"),
        ("contact", dist_dir / "contact" / "index.html"),
        ("tools", dist_dir / "tools" / "index.html"),
        ("404.html", dist_dir / "404.html"),
        ("signal", dist_dir / "signal" / "index.html"),
        ("static/signal", dist_dir / "static" / "signal" / "index.html"),
    ]
    for slug_name, html_path in non_tool_targets:
        orig_html = html_path.read_text(encoding="utf-8")

        if callable(gated_retrofit_fn):
            out_html, did_retrofit = gated_retrofit_fn(
                orig_html,
                property_id="gainhelm",
                slug=slug_name,
                dist_dir=dist_dir,
                html_path=html_path,
            )
            assert did_retrofit is False
            assert out_html == orig_html

        mutated = sgl._apply_closed_loop_dom_mutation_to_dist_html(
            html_path=html_path,
            mutation_spec={
                "target_slug": slug_name,
                "serp_depth_upgrade_html": '<section id="serp-incumbent-depth-workbench"><p>Injected</p></section>',
            },
            property_id="gainhelm",
            dist_dir=dist_dir,
        )
        assert mutated is False
        assert html_path.read_text(encoding="utf-8") == orig_html

        polluted_probe = orig_html.replace("</body>", '<script id="calculation-manifest">{}</script></body>')
        assert RetroReflectionEngine.is_tool_or_calculator_page(html_path, dist_dir, polluted_probe) is False

    # Direct overlay inject and rollback checks preserve governance titles and dates
    for gov_name in ("methodology", "disclaimers"):
        gov_path = dist_dir / gov_name / "index.html"
        gov_orig = gov_path.read_text(encoding="utf-8")
        gov_with_stray_ov = gov_orig.replace(
            "</main>",
            '<section class="overlay-section" id="gsc-striking-overlay"><p>Stray</p></section></main>',
        )
        cleaned_inj = inject_overlay_into_html(
            gov_with_stray_ov,
            {
                "slug": gov_name,
                "tenant_id": "gainhelm",
                "status": "ACTIVE_LOCKED",
                "title_rewrite": "Wrong Calculator Title | GainHelm",
            },
        )
        assert _extract_title(cleaned_inj) == _extract_title(gov_orig)
        assert set(_extract_dates_modified(cleaned_inj)) == {"2026-10-31"}
        assert "gsc-striking-overlay" not in cleaned_inj

        cleaned_rb = rollback_degraded_overlay_from_html(
            gov_with_stray_ov,
            {
                "slug": gov_name,
                "tenant_id": "gainhelm",
                "status": "DEGRADED_ROLLED_BACK",
                "rolled_back_title_rewrite": "Wrong Rolled Back Title | GainHelm",
            },
        )
        assert _extract_title(cleaned_rb) == _extract_title(gov_orig)
        assert set(_extract_dates_modified(cleaned_rb)) == {"2026-10-31"}
        assert "gsc-striking-overlay" not in cleaned_rb

    # Eligible un-retrofitted tool page still retrofits cleanly through _retrofit_tool_html_if_eligible
    assert callable(gated_retrofit_fn), "Expected shared _retrofit_tool_html_if_eligible helper in seo_growth_loops.py"
    unretrofitted_tool_html = """<!doctype html>
<html lang="en">
<head>
  <title>SOC 2 Audit Cost Calculator | GainHelm</title>
  <link rel="canonical" href="https://gainhelm.com/tools/soc-2-audit-cost-calculator/">
</head>
<body>
  <main>
    <h1>SOC 2 Audit Cost Calculator</h1>
    <form><label for="emp">Headcount</label><input id="emp" type="number" value="50"></form>
    <div id="result">$28,000</div>
  </main>
  <script>function runCalc(){ return 28000; }</script>
</body>
</html>"""
    soc2_path = dist_dir / "tools" / "soc-2-audit-cost-calculator" / "index.html"
    soc2_out, soc2_rep = gated_retrofit_fn(
        unretrofitted_tool_html,
        property_id="gainhelm",
        slug="soc-2-audit-cost-calculator",
        dist_dir=dist_dir,
        html_path=soc2_path,
    )
    assert soc2_rep is True
    assert 'id="calculation-manifest"' in soc2_out
    assert not (dist_dir / "manifests" / "methodology.json").exists()
    assert not (dist_dir / "manifests" / "disclaimers.json").exists()
    assert not (dist_dir / "manifests" / "404.html.json").exists()


def test_expired_overlays_and_cohort_respect_live_repo_guard_and_flat_tool_routes(
    tmp_path: Path, monkeypatch
) -> None:
    """
    Verifies evaluate_expired_overlays and evaluate_closed_loop_cohort_reflection respect
    _is_live_repo_mutation_blocked (never unlinking or writing inside protected live checkouts),
    while pruning stale governance overlays and rolling back flat HTML tool files in tmp repos,
    and verifies custom-domain root canonicals accept slug='index.html' in retrofit_html.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.gsc_remediation import audit_gsc_cron_cohort_and_cooldown_stability
    import pseofactory.maintenance as maint_mod

    fake_projects = tmp_path / "projects"
    fake_wt_root = fake_projects / ".agy" / "worktrees"
    monkeypatch.setattr(maint_mod, "_LIVE_PROJECTS_ROOT", fake_projects.resolve())
    monkeypatch.setattr(maint_mod, "_WORKTREES_ROOT", fake_wt_root.resolve())

    # 1. Protected live repo root: no unlinks, overlay mutations, HTML rewrites, or ledger writes even when persist=True.
    live_repo = fake_projects / "gainhelm"
    live_dist = live_repo / "dist"
    (live_dist / "methodology").mkdir(parents=True, exist_ok=True)
    (live_dist / "methodology" / "index.html").write_text(
        "<!doctype html><html><head><title>Methodology | GainHelm</title></head>"
        "<body><main><h1>Methodology</h1></main></body></html>",
        encoding="utf-8",
    )
    live_soc2_html = live_dist / "tools" / "soc-2-audit-cost-calculator" / "index.html"
    live_soc2_html.parent.mkdir(parents=True, exist_ok=True)
    live_soc2_bytes = (
        "<!doctype html><html><head><title>SOC 2 Calculator | GainHelm</title></head>"
        "<body><main><h1>SOC 2 Calculator</h1><input id='x' type='number'></main></body></html>"
    ).encode("utf-8")
    live_soc2_html.write_bytes(live_soc2_bytes)

    live_iso_html = live_dist / "tools" / "iso-27001-certification-cost-calculator" / "index.html"
    live_iso_html.parent.mkdir(parents=True, exist_ok=True)
    live_iso_bytes = (
        "<!doctype html><html><head><title>ISO 27001 Calculator | GainHelm</title></head>"
        "<body><main><h1>ISO 27001 Calculator</h1><input id='y' type='number'></main></body></html>"
    ).encode("utf-8")
    live_iso_html.write_bytes(live_iso_bytes)

    live_ov_dir = live_repo / ".agy" / "overlays"
    live_ov_dir.mkdir(parents=True, exist_ok=True)
    meth_ov = live_ov_dir / "methodology.json"
    disc_ov = live_ov_dir / "disclaimers.json"
    soc2_ov = live_ov_dir / "soc-2-audit-cost-calculator.json"
    iso_14d_ov = live_ov_dir / "iso-27001-certification-cost-calculator.json"
    meth_bytes = json.dumps(
        {"slug": "methodology", "target_url": "https://gainhelm.com/methodology/"}
    ).encode("utf-8")
    disc_bytes = json.dumps(
        {"slug": "disclaimers", "target_url": "https://gainhelm.com/disclaimers/"}
    ).encode("utf-8")
    soc2_bytes = json.dumps(
        {
            "slug": "soc-2-audit-cost-calculator",
            "status": "ACTIVE_MEASUREMENT_LOCK",
            "created_at": "2020-01-01T00:00:00+00:00",
            "baseline_position": 12.0,
            "baseline_impressions": 200,
        }
    ).encode("utf-8")
    iso_14d_bytes = json.dumps(
        {
            "slug": "iso-27001-certification-cost-calculator",
            "status": "ACTIVE_LOCKED",
            "measurement_lock_days": 14,
            "lock_days": 14,
            "created_at": "2026-10-01T00:00:00+00:00",
            "baseline_position": 9.0,
            "baseline_impressions": 120,
        }
    ).encode("utf-8")
    meth_ov.write_bytes(meth_bytes)
    disc_ov.write_bytes(disc_bytes)
    soc2_ov.write_bytes(soc2_bytes)
    iso_14d_ov.write_bytes(iso_14d_bytes)

    protected_gsc_rows = [
        {
            "query": "soc 2 audit cost calculator",
            "canonical_path": "/tools/soc-2-audit-cost-calculator",
            "page": "https://gainhelm.com/tools/soc-2-audit-cost-calculator/",
            "impressions": 150,
            "clicks": 3,
            "ctr": 0.02,
            "position": 8.2,
        },
        {
            "query": "iso 27001 certification cost calculator",
            "canonical_path": "/tools/iso-27001-certification-cost-calculator",
            "page": "https://gainhelm.com/tools/iso-27001-certification-cost-calculator/",
            "impressions": 120,
            "clicks": 2,
            "ctr": 0.0167,
            "position": 9.5,
        },
        {
            "query": "hipaa violation penalty calculator",
            "canonical_path": "/tools/hipaa-violation-penalty-breach-cost-calculator",
            "page": "https://gainhelm.com/tools/hipaa-violation-penalty-breach-cost-calculator/",
            "impressions": 95,
            "clicks": 1,
            "ctr": 0.0105,
            "position": 11.4,
        },
    ]

    evaluate_expired_overlays(
        site_url="sc-domain:gainhelm.com",
        base_dir=live_repo,
        persist=True,
        live_queries=[],
    )
    audit_gsc_cron_cohort_and_cooldown_stability(
        property_id="gainhelm",
        repo_root=live_repo,
        live_queries=protected_gsc_rows,
        dry_run=False,
    )
    sgl.compile_search_opportunity_briefs(
        property_id="gainhelm",
        repo_root=live_repo,
        dist_dir=live_dist,
        consolidated_gsc={"current_rows": protected_gsc_rows, "baseline_rows": protected_gsc_rows},
        apply_overlays=True,
        persist=True,
    )
    sgl.evaluate_closed_loop_cohort_reflection(
        property_id="gainhelm",
        repo_root=live_repo,
        dist_dir=live_dist,
        live_queries=protected_gsc_rows,
        persist=True,
    )
    sgl.run_all_seo_growth_workflows(
        property_id="gainhelm",
        repo_root=live_repo,
        dist_dir=live_dist,
        live_queries=protected_gsc_rows,
        apply_overlays=True,
        persist=True,
        live_gsc=False,
    )
    sgl.sync_real_gsc_baselines_to_recovery_ledger(
        property_id="gainhelm",
        repo_root=live_repo,
        live_queries=protected_gsc_rows,
    )

    assert live_soc2_html.read_bytes() == live_soc2_bytes
    assert live_iso_html.read_bytes() == live_iso_bytes
    assert meth_ov.read_bytes() == meth_bytes
    assert disc_ov.read_bytes() == disc_bytes
    assert soc2_ov.read_bytes() == soc2_bytes
    assert iso_14d_ov.read_bytes() == iso_14d_bytes
    assert sorted(p.name for p in live_ov_dir.glob("*.json")) == [
        "disclaimers.json",
        "iso-27001-certification-cost-calculator.json",
        "methodology.json",
        "soc-2-audit-cost-calculator.json",
    ]
    assert not (live_repo / "content" / "overlays").exists()
    assert list((live_repo / ".agy").glob("*.json")) == []

    # 2. Unprotected tmp workspace: governance overlays prune cleanly and flat tool HTML rolls back.
    unprot_repo = tmp_path / "unprotected_gainhelm"
    unprot_dist = unprot_repo / "dist"
    unprot_dist.mkdir(parents=True, exist_ok=True)
    (unprot_dist / "index.html").write_text(
        "<!doctype html><html><head><title>GainHelm</title></head>"
        "<body><main><h1>GainHelm</h1></main></body></html>",
        encoding="utf-8",
    )
    flat_tool_base = (
        "<!doctype html><html><head><title>Flat Tax Calculator | GainHelm</title></head>"
        '<body><main><h1>Flat Tax Calculator</h1><form><input id="inc" type="number" value="100"></form></main></body></html>'
    )
    active_tax_spec = {
        "slug": "tax-calc",
        "tenant_id": "gainhelm",
        "status": "ACTIVE_LOCKED",
        "title_rewrite": "Updated Flat Tax Calc | GainHelm",
        "baseline_title": "Flat Tax Calculator | GainHelm",
        "h2_blocks": [{"heading": "2026 Tax Brackets", "intent": "explain brackets"}],
    }
    flat_tool = unprot_dist / "tax-calc.html"
    flat_tool.write_text(
        inject_overlay_into_html(flat_tool_base, active_tax_spec),
        encoding="utf-8",
    )
    assert 'class="overlay-section' in flat_tool.read_text(encoding="utf-8")
    assert _extract_title(flat_tool.read_text(encoding="utf-8")) == "Updated Flat Tax Calc | GainHelm"

    unprot_ov_dir = unprot_repo / ".agy" / "overlays"
    unprot_ov_dir.mkdir(parents=True, exist_ok=True)
    (unprot_ov_dir / "methodology.json").write_bytes(meth_bytes)
    (unprot_ov_dir / "disclaimers.json").write_bytes(disc_bytes)

    evaluate_expired_overlays(
        site_url="sc-domain:gainhelm.com",
        base_dir=unprot_repo,
        persist=True,
        live_queries=[],
    )
    assert not (unprot_ov_dir / "methodology.json").exists()
    assert not (unprot_ov_dir / "disclaimers.json").exists()

    (unprot_ov_dir / "tax-calc.json").write_text(
        json.dumps(
            {
                "slug": "tax-calc",
                "tenant_id": "gainhelm",
                "status": "DEGRADED_ROLLED_BACK",
                "baseline_title": "Flat Tax Calculator | GainHelm",
                "rolled_back_title_rewrite": "Updated Flat Tax Calc | GainHelm",
            }
        ),
        encoding="utf-8",
    )
    RetroReflectionEngine.retrofit_estate(unprot_dist, "gainhelm", "https://gainhelm.com")
    rolled_back_flat = flat_tool.read_text(encoding="utf-8")
    assert 'class="overlay-section' not in rolled_back_flat
    assert _extract_title(rolled_back_flat) == "Flat Tax Calculator | GainHelm"

    # 3. Any http(s) root canonical URL accepts slug='index.html'; non-root governance canonical skips.
    root_calc_html = """<!doctype html>
<html lang="en">
<head>
  <title>Custom Domain Calculator | CustomTenant</title>
  <link rel="canonical" href="https://customtenant.org/">
</head>
<body>
  <main>
    <h1>Custom Domain Calculator</h1>
    <form><label for="amt">Amount</label><input id="amt" type="number" value="100"></form>
    <div id="result">$100</div>
  </main>
  <script>function calc(){ return 100; }</script>
</body>
</html>"""
    root_out, root_rep = RetroReflectionEngine.retrofit_html(
        root_calc_html,
        property_id="gainhelm",
        slug="index.html",
        dist_dir=unprot_dist,
    )
    assert root_rep
    assert 'id="calculation-manifest"' in root_out

    non_root_gov_html = root_calc_html.replace(
        "https://customtenant.org/", "https://customtenant.org/methodology/"
    )
    gov_out, gov_rep = RetroReflectionEngine.retrofit_html(
        non_root_gov_html,
        property_id="gainhelm",
        slug="index.html",
        dist_dir=unprot_dist,
    )
    assert gov_rep == []
    assert gov_out == non_root_gov_html


def _snapshot_tree_bytes(root_dirs: tuple[Path, ...]) -> dict[str, bytes]:
    snap: dict[str, bytes] = {}
    for base in root_dirs:
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file():
                snap[f"{base.name}/{p.relative_to(base).as_posix()}"] = p.read_bytes()
    return snap


def test_compiled_gainhelm_estate_untouched_by_workflows_and_verifier_under_live_guard(
    tmp_path: Path, monkeypatch
) -> None:
    """
    Verifies a full compile_gainhelm_estate build under mocked _LIVE_PROJECTS_ROOT suffers
    zero file additions or byte mutations in dist/ and functions/ across
    run_all_seo_growth_workflows, evaluate_north_star_targets(persist=False),
    MasterSEOVerifier, and RetroReflectionEngine.sync_tenant_publisher_prerequisites /
    sync_tenant_llms_manifests.
    Zero em-dashes. Zero en-dashes.
    """
    import pseofactory.maintenance as maint_mod
    from pseofactory.verifier import MasterSEOVerifier

    fake_projects = tmp_path / "projects"
    fake_wt_root = fake_projects / ".agy" / "worktrees"
    live_gainhelm = fake_projects / "gainhelm"
    compile_gainhelm_estate(live_gainhelm)

    live_dist = live_gainhelm / "dist"
    live_funcs = live_gainhelm / "functions"
    live_funcs.mkdir(parents=True, exist_ok=True)
    # Seed a custom sentinel in functions/_middleware.js and dist/media-kit.json to catch overwrites.
    mw_file = live_funcs / "_middleware.js"
    mw_file.write_text("export async function onRequest(ctx) { return ctx.next(); }\n", encoding="utf-8")
    media_kit_file = live_dist / "media-kit.json"
    media_kit_file.write_text('{"sentinel": true}\n', encoding="utf-8")

    before_snap = _snapshot_tree_bytes((live_dist, live_funcs, live_gainhelm / ".agy"))
    assert before_snap

    monkeypatch.setattr(maint_mod, "_LIVE_PROJECTS_ROOT", fake_projects.resolve())
    monkeypatch.setattr(maint_mod, "_WORKTREES_ROOT", fake_wt_root.resolve())

    sgl.run_all_seo_growth_workflows(
        property_id="gainhelm",
        repo_root=live_gainhelm,
        dist_dir=live_dist,
        apply_overlays=True,
        persist=True,
        live_gsc=False,
    )
    sgl.evaluate_north_star_targets(
        property_id="gainhelm",
        repo_root=live_gainhelm,
        dist_dir=live_dist,
        persist=False,
    )
    v_ro = MasterSEOVerifier(dist_dir=live_dist, allow_mutations=False)
    assert v_ro.allow_mutations is False
    MasterSEOVerifier(dist_dir=live_dist)
    RetroReflectionEngine.sync_tenant_publisher_prerequisites(
        live_dist,
        property_id="gainhelm",
        canonical_base="https://gainhelm.com",
    )
    RetroReflectionEngine.sync_tenant_llms_manifests(
        live_dist,
        property_id="gainhelm",
        canonical_base="https://gainhelm.com",
    )

    after_snap = _snapshot_tree_bytes((live_dist, live_funcs, live_gainhelm / ".agy"))
    assert after_snap == before_snap


def test_trend_history_db_read_only_and_live_guard_prevent_sqlite_mutations(
    tmp_path: Path, monkeypatch
) -> None:
    """
    Verifies TrendHistoryDB(read_only=True), harvest_and_sync_gsc_multidimensional_telemetry,
    and harvest_and_sync_gsc_daily_timeline never delete URL inspection rows when persist=False
    or rewrite legacy SQLite database bytes in protected live checkouts.
    Zero em-dashes. Zero en-dashes.
    """
    import sqlite3
    import pseofactory.maintenance as maint_mod
    from pseofactory.trends.db import TrendHistoryDB
    from pseofactory.trends.models import GSCUrlInspectionRecord

    # 1. Seeded TrendHistoryDB + live_gsc=True + persist=False preserves rows without deletion.
    repo_ro = tmp_path / "repo_ro_inspect"
    db_ro = repo_ro / "pseofactory" / "trends" / "data" / "trend_history.db"
    (repo_ro / "dist").mkdir(parents=True, exist_ok=True)
    (repo_ro / "dist" / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset><url><loc>https://gainhelm.com/tools/soc-2-audit-cost-calculator/</loc></url></urlset>',
        encoding="utf-8",
    )
    with TrendHistoryDB(db_ro) as seed_tdb:
        seed_tdb.upsert_gsc_url_inspection_states(
            [
                GSCUrlInspectionRecord(
                    property_id="gainhelm",
                    page_url="https://gainhelm.com/tools/calc-7/",
                    verdict="PASS",
                    coverage_state="Submitted and indexed",
                    indexing_state="INDEXING_ALLOWED",
                    page_fetch_state="SUCCESSFUL",
                    robots_txt_state="ALLOWED",
                    user_canonical="https://gainhelm.com/tools/calc-7/",
                    google_canonical="https://gainhelm.com/tools/calc-7/",
                    last_crawl_time="2026-11-10T08:00:00Z",
                    crawled_as="MOBILE",
                    rich_results_verdict="VERDICT_UNSPECIFIED",
                    rich_results_types=[],
                    mobile_usability_verdict="VERDICT_UNSPECIFIED",
                    referring_urls=[],
                    sitemaps=[],
                    root_cause_classification="",
                    recorded_at="2026-11-10T08:00:00+00:00",
                )
            ]
        )

    assert not Path(f"{db_ro}-wal").exists()
    assert not Path(f"{db_ro}-shm").exists()
    before_ro_bytes = db_ro.read_bytes()

    sgl._LIVE_GSC_MULTIDIM_CACHE.clear()
    sgl._LIVE_GSC_CONSOLIDATED_CACHE.clear()
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(sgl, "_invoke_live_gsc_query_cli", lambda *a, **kw: ([], False))

    # Even inside a chmod 0555 read-only directory, cleanly closed WAL DB reads work with zero sidecars.
    db_ro.parent.chmod(0o555)
    try:
        sgl.harvest_and_sync_gsc_multidimensional_telemetry(
            property_id="gainhelm",
            repo_root=repo_ro,
            live_gsc=True,
            persist=False,
        )
        with TrendHistoryDB(db_ro, read_only=True) as check_tdb:
            rows_after = check_tdb.get_gsc_url_inspection_states("gainhelm")
    finally:
        db_ro.parent.chmod(0o755)

    assert len(rows_after) == 1
    assert rows_after[0].page_url == "https://gainhelm.com/tools/calc-7/"
    assert not Path(f"{db_ro}-wal").exists()
    assert not Path(f"{db_ro}-shm").exists()
    assert db_ro.read_bytes() == before_ro_bytes

    # Empty 0-byte DB opened read_only=True returns [] safely with zero WAL/SHM creation.
    empty_db = tmp_path / "empty_ro.db"
    empty_db.touch()
    with TrendHistoryDB(empty_db, read_only=True) as empty_tdb:
        assert empty_tdb.get_gsc_daily_metrics("gainhelm") == []
        assert empty_tdb.get_gsc_url_inspection_states("gainhelm") == []
    assert empty_db.stat().st_size == 0
    assert not Path(f"{empty_db}-wal").exists()
    assert not Path(f"{empty_db}-shm").exists()

    # 2. Legacy SQLite DB under protected _LIVE_PROJECTS_ROOT keeps 100% identical bytes.
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_trend_history_db_read_only")
    fake_projects = tmp_path / "projects"
    fake_wt_root = fake_projects / ".agy" / "worktrees"
    live_pf = fake_projects / "profithelm-platform"
    legacy_db = live_pf / "pseofactory" / "trends" / "data" / "trend_history.db"
    legacy_db.parent.mkdir(parents=True, exist_ok=True)
    raw_conn = sqlite3.connect(str(legacy_db))
    raw_conn.execute("CREATE TABLE dummy (x INT);")
    raw_conn.execute("INSERT INTO dummy VALUES (42);")
    raw_conn.commit()
    raw_conn.close()
    before_db_bytes = legacy_db.read_bytes()

    monkeypatch.setattr(maint_mod, "_LIVE_PROJECTS_ROOT", fake_projects.resolve())
    monkeypatch.setattr(maint_mod, "_WORKTREES_ROOT", fake_wt_root.resolve())
    sgl._LIVE_GSC_MULTIDIM_CACHE.clear()
    sgl._LIVE_GSC_CONSOLIDATED_CACHE.clear()

    with TrendHistoryDB(legacy_db, read_only=True) as ro_tdb:
        assert ro_tdb.get_gsc_url_inspection_states("profithelm") == []
        assert ro_tdb.get_gsc_daily_metrics("profithelm") == []

    sgl.harvest_and_sync_gsc_multidimensional_telemetry(
        property_id="profithelm",
        repo_root=live_pf,
        live_gsc=False,
        persist=True,
    )
    sgl.harvest_and_sync_gsc_daily_timeline(
        property_id="profithelm",
        repo_root=live_pf,
        live_gsc=False,
        persist=True,
    )

    assert legacy_db.read_bytes() == before_db_bytes
    assert not Path(f"{legacy_db}-wal").exists()
    assert not Path(f"{legacy_db}-shm").exists()
    assert not (live_pf / ".agy" / "gsc_lifecycle_telemetry.json").exists()


def test_cohort_reflection_and_retrofit_html_never_write_sidecar_manifests_when_blocked_or_unpersisted(
    tmp_path: Path, monkeypatch
) -> None:
    """
    Verifies neither evaluate_closed_loop_cohort_reflection nor RetroReflectionEngine.retrofit_html
    creates dist/manifests/*.json files in protected live checkouts or when persist=False.
    Zero em-dashes. Zero en-dashes.
    """
    import pseofactory.maintenance as maint_mod

    unretrofitted_tool = """<!doctype html>
<html lang="en">
<head>
  <title>Custom Audit Calculator | GainHelm</title>
  <link rel="canonical" href="https://gainhelm.com/tools/custom-unretrofitted-tool/">
</head>
<body>
  <main>
    <h1>Custom Audit Calculator</h1>
    <form><label for="emp">Headcount</label><input id="emp" type="number" value="50"></form>
    <div id="result">$28,000</div>
  </main>
  <script>function runCalc(){ return 28000; }</script>
</body>
</html>"""

    # 1. Protected live GainHelm checkout: zero dist/manifests/*.json written even when persist=True.
    fake_projects = tmp_path / "projects"
    fake_wt_root = fake_projects / ".agy" / "worktrees"
    live_gainhelm = fake_projects / "gainhelm"
    compile_gainhelm_estate(live_gainhelm)
    live_dist = live_gainhelm / "dist"
    custom_tool_html = live_dist / "tools" / "custom-unretrofitted-tool" / "index.html"
    custom_tool_html.parent.mkdir(parents=True, exist_ok=True)
    custom_tool_html.write_text(unretrofitted_tool, encoding="utf-8")
    (live_dist / "manifests").mkdir(parents=True, exist_ok=True)
    before_manifests = sorted(p.name for p in (live_dist / "manifests").glob("*.json"))

    monkeypatch.setattr(maint_mod, "_LIVE_PROJECTS_ROOT", fake_projects.resolve())
    monkeypatch.setattr(maint_mod, "_WORKTREES_ROOT", fake_wt_root.resolve())

    if "/.agy/worktrees/" in Path(maint_mod.__file__).resolve().as_posix():
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    sgl.evaluate_closed_loop_cohort_reflection(
        property_id="gainhelm",
        repo_root=live_gainhelm,
        dist_dir=live_dist,
        live_queries=[
            {
                "query": "custom audit calculator",
                "canonical_path": "/tools/custom-unretrofitted-tool",
                "page": "https://gainhelm.com/tools/custom-unretrofitted-tool/",
                "impressions": 150,
                "clicks": 3,
                "position": 8.0,
            }
        ],
        propagate_winning_patterns=True,
        persist=True,
    )
    RetroReflectionEngine.retrofit_html(
        unretrofitted_tool,
        property_id="gainhelm",
        slug="custom-unretrofitted-tool",
        dist_dir=live_dist,
    )

    after_manifests = sorted(p.name for p in (live_dist / "manifests").glob("*.json"))
    assert after_manifests == before_manifests
    assert not (live_dist / "manifests" / "custom-unretrofitted-tool.json").exists()

    # 2. Unprotected tmp_path with persist=False: zero dist/manifests/*.json written.
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_cohort_sidecar_persist_false")
    unprot_repo = tmp_path / "unprot_cohort"
    unprot_dist = unprot_repo / "dist"
    unprot_tool = unprot_dist / "tools" / "custom-unretrofitted-tool" / "index.html"
    unprot_tool.parent.mkdir(parents=True, exist_ok=True)
    unprot_tool.write_text(unretrofitted_tool, encoding="utf-8")
    (unprot_dist / "manifests").mkdir(parents=True, exist_ok=True)
    before_unprot = unprot_tool.read_text(encoding="utf-8")

    sgl.evaluate_closed_loop_cohort_reflection(
        property_id="gainhelm",
        repo_root=unprot_repo,
        dist_dir=unprot_dist,
        live_queries=[
            {
                "query": "custom audit calculator",
                "canonical_path": "/tools/custom-unretrofitted-tool",
                "page": "https://gainhelm.com/tools/custom-unretrofitted-tool/",
                "impressions": 150,
                "clicks": 3,
                "position": 8.0,
            }
        ],
        propagate_winning_patterns=True,
        persist=False,
    )

    assert not (unprot_dist / "manifests" / "custom-unretrofitted-tool.json").exists()
    assert unprot_tool.read_text(encoding="utf-8") == before_unprot



