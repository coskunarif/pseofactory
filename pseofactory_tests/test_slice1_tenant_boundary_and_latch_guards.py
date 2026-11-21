"""
Regression tests for Slice 1 adversarial review fixes and 04:05 timer forensics:
1. IndexingInspector skips cross-tenant canonical/reason and foreign-slug quarantine records.
2. IndexingFeedbackLoop blocks cross-property syndication/overlay writes and derives
   all production tenant repos (including lienbond) dynamically from CANONICAL_TENANT_DECLARATIONS.
3. clean_cross_property_contaminated_syndication_and_overlays self-heals contaminated
   syndication files and foreign overlays while preserving legitimate tenant assets.
4. _is_strictly_single_threaded_os_process blocks unsafe multi-threaded fork() and
   verify_all_tenants_aligned_for_latch fails closed when lienbond/substrate_lock.json is missing.
5. release_pipeline.sh billing-limit fallback runs pseofactory tests fail-closed.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_indexing_inspector_skips_foreign_canonical_and_foreign_slug_quarantine_records(
    tmp_path: Path,
) -> None:
    from pseofactory.indexing_inspector import DailyIndexingInspector

    base_dir = tmp_path / "profithelm-platform"
    (base_dir / "dist" / "tools" / "section-179-calculator").mkdir(parents=True, exist_ok=True)
    (base_dir / "dist" / "tools" / "section-179-calculator" / "index.html").write_text(
        "<html><body><h1>Section 179</h1></body></html>",
        encoding="utf-8",
    )
    agy_dir = tmp_path / ".agy"
    agy_dir.mkdir(parents=True, exist_ok=True)

    q_path = agy_dir / "indexing_quarantine_ledger.json"
    q_path.write_text(
        json.dumps(
            {
                "https://profithelm.com/tools/soc-2-audit-cost-calculator/": {
                    "url": "https://profithelm.com/tools/soc-2-audit-cost-calculator/",
                    "code": "CANONICAL_MISMATCH",
                    "reason": "Canonical points to https://gainhelm.com/tools/soc-2-audit-cost-calculator/",
                },
                "https://profithelm.com/tools/cmmc-2-0-compliance-cost-calculator/": {
                    "url": "https://profithelm.com/tools/cmmc-2-0-compliance-cost-calculator/",
                    "code": "HTTP_404",
                    "reason": "Page returned HTTP 404",
                },
                "https://profithelm.com/tools/section-179-calculator/": {
                    "url": "https://profithelm.com/tools/section-179-calculator/",
                    "code": "THIN_CONTENT",
                    "reason": "Needs expanded statutory breakdown",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    inspector = DailyIndexingInspector(
        base_dir=base_dir,
        tenant_id="profithelm",
        agy_dir=agy_dir,
        quarantine_ledger_path=q_path,
    )
    audit = inspector.audit_airlock_quarantine()
    assert audit["total_quarantined"] == 1
    assert audit["breakdown"]["THIN_CONTENT"] == 1
    assert audit["breakdown"]["CANONICAL_MISMATCH"] == 0
    assert audit["breakdown"]["HTTP_404"] == 0

    urls = inspector.get_quarantined_urls()
    assert urls == ["https://profithelm.com/tools/section-179-calculator/"]


def test_feedback_loop_blocks_foreign_syndication_and_overlays_and_protects_lienbond(
    tmp_path: Path,
) -> None:
    from pseofactory.indexing.feedback_loop import (
        DiagnosisResult,
        IndexingFeedbackLoop,
        RootCauseClassification,
    )

    ph_repo = tmp_path / "profithelm-platform"
    (ph_repo / "dist" / "tools" / "section-179-calculator").mkdir(parents=True, exist_ok=True)
    (ph_repo / "dist" / "tools" / "section-179-calculator" / "index.html").write_text(
        "<html><body><h1>Section 179 Calculator</h1></body></html>",
        encoding="utf-8",
    )

    loop = IndexingFeedbackLoop(
        base_dir=ph_repo,
        dist_dir=ph_repo / "dist",
        property_id="profithelm",
        domain="profithelm.com",
    )

    # 1. Direct _sync_external_distribution_for_candidate blocks GainHelm slug and foreign URL
    written_foreign_slug = loop._sync_external_distribution_for_candidate(
        slug="soc-2-audit-cost-calculator",
        target_url="https://profithelm.com/tools/soc-2-audit-cost-calculator/",
        overlay_spec={"title_rewrite": "SOC 2 Audit Cost Calculator"},
        dry_run=False,
    )
    assert written_foreign_slug == []
    assert not (ph_repo / "syndication" / "soc-2-audit-cost-calculator-linkedin.md").exists()

    written_foreign_url = loop._sync_external_distribution_for_candidate(
        slug="custom-unknown-grc-tool",
        target_url="https://gainhelm.com/tools/custom-unknown-grc-tool/",
        overlay_spec={"title_rewrite": "Custom GRC Tool"},
        dry_run=False,
    )
    assert written_foreign_url == []
    assert not (ph_repo / "syndication" / "custom-unknown-grc-tool-linkedin.md").exists()

    # 2. execute_engine_repairs refuses to write foreign overlays or syndication, while allowing own tenant
    foreign_diag = DiagnosisResult(
        url="https://profithelm.com/tools/soc-2-audit-cost-calculator/",
        classification=RootCauseClassification.CANONICAL_TEMPLATE_DEFECT.value,
        reason="Canonical points to https://gainhelm.com/tools/soc-2-audit-cost-calculator/",
        remediation_action="SKIP_FOREIGN",
        reflection_path="tools/soc-2-audit-cost-calculator/index.html",
    )
    res = loop.execute_engine_repairs(
        diagnoses=[foreign_diag],
        prioritized_candidates=[
            {
                "slug": "soc-2-audit-cost-calculator",
                "target_url": "https://profithelm.com/tools/soc-2-audit-cost-calculator/",
                "reason": "Canonical points to https://gainhelm.com/tools/soc-2-audit-cost-calculator/",
                "impressions": 50,
                "distribution_gap_detected": True,
            },
            {
                "slug": "section-179-calculator",
                "target_url": "https://profithelm.com/tools/section-179-calculator/",
                "impressions": 80,
                "distribution_gap_detected": True,
            },
        ],
        skip_recompile=True,
        dry_run=False,
    )
    assert "soc-2-audit-cost-calculator" not in res["overlays_written"]
    assert not (ph_repo / "content" / "overlays" / "soc-2-audit-cost-calculator.json").exists()
    assert not (ph_repo / "syndication" / "soc-2-audit-cost-calculator-linkedin.md").exists()
    assert "section-179-calculator" in res["overlays_written"]
    assert (ph_repo / "syndication" / "section-179-calculator-linkedin.md").is_file()

    # 3. Dynamic prod-tenant repo guard covers profithelm-platform, prexvo, gainhelm, AND lienbond
    fake_projects = tmp_path / "projects"
    for repo_name in ("profithelm-platform", "prexvo", "gainhelm", "lienbond"):
        d = fake_projects / repo_name
        d.mkdir(parents=True, exist_ok=True)
        assert IndexingFeedbackLoop._is_canonical_prod_tenant_dir(d, projects_root=fake_projects) is True
    assert IndexingFeedbackLoop._is_canonical_prod_tenant_dir(tmp_path / "sandbox", projects_root=fake_projects) is False


def test_maintenance_self_heals_cross_property_contaminated_syndication_and_overlays(
    tmp_path: Path,
) -> None:
    from pseofactory.maintenance import (
        CrossPropertyContaminationScanner,
        clean_cross_property_contaminated_syndication_and_overlays,
    )

    ph_repo = tmp_path / "profithelm-platform"
    dist_dir = ph_repo / "dist"
    (dist_dir / "tools" / "section-179-calculator").mkdir(parents=True, exist_ok=True)
    (dist_dir / "tools" / "section-179-calculator" / "index.html").write_text(
        "<html><body><h1>Section 179</h1></body></html>",
        encoding="utf-8",
    )

    synd_dir = ph_repo / "syndication"
    synd_dir.mkdir(parents=True, exist_ok=True)
    # Seed contaminated GainHelm files + sibling without token + foreign overlay
    (synd_dir / "soc-2-audit-cost-calculator-linkedin.md").write_text(
        "Run on GainHelm: https://gainhelm.com/tools/soc-2-audit-cost-calculator/\n",
        encoding="utf-8",
    )
    (synd_dir / "soc-2-audit-cost-calculator-newsletter.md").write_text(
        "SOC 2 newsletter body without explicit domain\n",
        encoding="utf-8",
    )
    (synd_dir / "soc-2-audit-cost-calculator-Substack Notes-post.txt").write_text(
        "Explore https://gainhelm.com/tools/soc-2-audit-cost-calculator/\n",
        encoding="utf-8",
    )
    (synd_dir / "legacy-leaked-grc-linkedin.md").write_text(
        "See https://gainhelm.com/tools/legacy-leaked-grc/\n",
        encoding="utf-8",
    )
    (synd_dir / "legacy-leaked-grc-newsletter.md").write_text(
        "Clean sibling of contaminated slug\n",
        encoding="utf-8",
    )
    # Legitimate ProfitHelm syndication file must survive untouched
    (synd_dir / "section-179-calculator-linkedin.md").write_text(
        "Run on ProfitHelm: https://profithelm.com/tools/section-179-calculator/\n",
        encoding="utf-8",
    )

    ov_dir = ph_repo / ".agy" / "overlays"
    ov_dir.mkdir(parents=True, exist_ok=True)
    (ov_dir / "soc-2-audit-cost-calculator.json").write_text(
        json.dumps({"slug": "soc-2-audit-cost-calculator", "target_url": "https://profithelm.com/tools/soc-2-audit-cost-calculator/"}),
        encoding="utf-8",
    )
    (ov_dir / "legacy-leaked-grc.json").write_text(
        json.dumps({"slug": "legacy-leaked-grc", "target_url": "https://profithelm.com/tools/legacy-leaked-grc/"}),
        encoding="utf-8",
    )
    (ov_dir / "section-179-calculator.json").write_text(
        json.dumps({"slug": "section-179-calculator", "target_url": "https://profithelm.com/tools/section-179-calculator/"}),
        encoding="utf-8",
    )

    res = clean_cross_property_contaminated_syndication_and_overlays(
        repo_root=ph_repo,
        property_id="profithelm",
        dist_dir=dist_dir,
    )
    assert len(res["removed_syndication"]) == 5
    assert len(res["removed_overlays"]) == 2
    assert (synd_dir / "section-179-calculator-linkedin.md").is_file()
    assert (ov_dir / "section-179-calculator.json").is_file()
    assert not (synd_dir / "soc-2-audit-cost-calculator-linkedin.md").exists()
    assert not (synd_dir / "soc-2-audit-cost-calculator-newsletter.md").exists()
    assert not (synd_dir / "legacy-leaked-grc-newsletter.md").exists()
    assert not (ov_dir / "soc-2-audit-cost-calculator.json").exists()
    assert not (ov_dir / "legacy-leaked-grc.json").exists()
    assert CrossPropertyContaminationScanner().scan_directory(synd_dir, "profithelm") == {}


def test_drift_single_thread_fork_guard_and_missing_lienbond_lock_fail_closed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import pseofactory.drift as drift_mod

    # 1. PYTEST_XDIST_WORKER forces False
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw0")
    assert drift_mod._is_strictly_single_threaded_os_process() is False
    monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)

    # 2. Multi-threaded /proc/self/status forces False
    orig_read_text = Path.read_text

    def _fake_read_multi(self: Path, *args, **kwargs):
        if str(self) == "/proc/self/status":
            return "Name:\tpython3\nThreads:\t3\n"
        return orig_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _fake_read_multi)
    assert drift_mod._is_strictly_single_threaded_os_process() is False

    # 3. Unreadable /proc/self/status fails closed to False
    def _fake_read_err(self: Path, *args, **kwargs):
        if str(self) == "/proc/self/status":
            raise OSError("unreadable")
        return orig_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _fake_read_err)
    assert drift_mod._is_strictly_single_threaded_os_process() is False
    monkeypatch.setattr(Path, "read_text", orig_read_text)

    # 4. Missing lienbond/substrate_lock.json fails closed when lienbond repo exists
    ws = tmp_path / "ws"
    lb_repo = ws / "lienbond"
    (lb_repo / ".git").mkdir(parents=True, exist_ok=True)
    (lb_repo / "dist").mkdir(parents=True, exist_ok=True)
    (lb_repo / "dist" / "index.html").write_text("<html><body>LienBond</body></html>", encoding="utf-8")

    ok, reasons = drift_mod.verify_all_tenants_aligned_for_latch(
        workspace_root=ws,
        require_git_clean_and_pushed=False,
    )
    assert ok is False
    assert any("lienbond: missing substrate_lock.json" in r for r in reasons), reasons


@pytest.mark.host_estate
def test_release_pipeline_billing_limit_fallback_runs_pseofactory_pytest_fail_closed() -> None:
    pipe_txt = Path("/home/ubuntuadmin/projects/.agy/release_pipeline.sh").read_text(encoding="utf-8")
    idx = pipe_txt.index("recent account payments have failed or your spending limit needs to be increased")
    block = pipe_txt[idx : idx + 3500]
    assert 'elif [[ -f "$PROJECT_DIR/pseofactory/cli.py" ]]; then' in block
    assert "pseofactory_tests/" in block
    assert "CI_SUCCESS=0" in block
    assert 'if [[ "$CI_SUCCESS" -eq 1 ]]; then\n                break' in block


def test_is_foreign_tenant_tool_slug_discovers_dynamic_sibling_and_expansion_tools(
    tmp_path: Path,
) -> None:
    """
    Proves is_foreign_tenant_tool_slug detects:
    1. Expansion slugs (e.g. dora-ict-..., eu-ai-act-..., sec-cybersecurity-incident-...)
       even without sibling repos on disk.
    2. Brand-new P2 or future-tenant slugs dynamically via sibling dist/tools/<slug>/index.html
       under workspace_root (both canonical siblings and .pseofactory.json future tenants).
    3. Never flags a slug that exists in the current tenant's own dist/tools/.
    """
    from pseofactory.maintenance import (
        clean_cross_property_contaminated_syndication_and_overlays,
        is_foreign_tenant_tool_slug,
    )

    ws = tmp_path / "ws"
    ph_repo = ws / "profithelm-platform"
    gh_repo = ws / "gainhelm"
    future_repo = ws / "futurehelm"

    (ph_repo / "dist" / "tools" / "section-179-calculator").mkdir(parents=True, exist_ok=True)
    (ph_repo / "dist" / "tools" / "section-179-calculator" / "index.html").write_text("<html>PH</html>", encoding="utf-8")

    # Brand-new P2 slug compiled in sibling gainhelm (NOT in any static constant)
    (gh_repo / "dist" / "tools" / "brand-new-p2-nis2-audit-cost-calculator").mkdir(parents=True, exist_ok=True)
    (gh_repo / "dist" / "tools" / "brand-new-p2-nis2-audit-cost-calculator" / "index.html").write_text(
        "<html>GH P2</html>", encoding="utf-8"
    )

    # Brand-new future tenant declared only via .pseofactory.json
    (future_repo / "dist" / "tools" / "future-tenant-exclusive-calculator").mkdir(parents=True, exist_ok=True)
    (future_repo / "dist" / "tools" / "future-tenant-exclusive-calculator" / "index.html").write_text(
        "<html>Future</html>", encoding="utf-8"
    )
    (future_repo / ".pseofactory.json").write_text(
        json.dumps({"property_id": "futurehelm", "domain": "futurehelm.com"}),
        encoding="utf-8",
    )

    # 1. Static expansion slugs caught even with no sibling dist
    isolated_dist = tmp_path / "isolated" / "profithelm-platform" / "dist"
    isolated_dist.mkdir(parents=True, exist_ok=True)
    for exp_slug in (
        "dora-ict-third-party-risk-compliance-cost-calculator",
        "eu-ai-act-high-risk-conformity-assessment-cost-calculator",
        "sec-cybersecurity-incident-materiality-8k-item-105-cost-calculator",
    ):
        assert is_foreign_tenant_tool_slug(exp_slug, "profithelm", dist_dir=isolated_dist) is True

    # 2. Dynamic sibling canonical + future tenant slugs caught via ws discovery
    assert is_foreign_tenant_tool_slug(
        "brand-new-p2-nis2-audit-cost-calculator", "profithelm", dist_dir=ph_repo / "dist"
    ) is True
    assert is_foreign_tenant_tool_slug(
        "future-tenant-exclusive-calculator", "profithelm", dist_dir=ph_repo / "dist"
    ) is True

    # 3. Own compiled slug never flagged
    assert is_foreign_tenant_tool_slug("section-179-calculator", "profithelm", dist_dir=ph_repo / "dist") is False

    # 4. End-to-end cleanup removes brand-new sibling slug syndication + overlay with zero domain tokens in body
    (ph_repo / "syndication").mkdir(parents=True, exist_ok=True)
    (ph_repo / ".agy" / "overlays").mkdir(parents=True, exist_ok=True)
    (ph_repo / "syndication" / "brand-new-p2-nis2-audit-cost-calculator-linkedin.md").write_text(
        "Body with no explicit domain string\n", encoding="utf-8"
    )
    (ph_repo / ".agy" / "overlays" / "brand-new-p2-nis2-audit-cost-calculator.json").write_text(
        json.dumps({"slug": "brand-new-p2-nis2-audit-cost-calculator"}), encoding="utf-8"
    )
    (ph_repo / "syndication" / "section-179-calculator-linkedin.md").write_text(
        "Own ProfitHelm body\n", encoding="utf-8"
    )
    cleanup = clean_cross_property_contaminated_syndication_and_overlays(ph_repo, "profithelm", dist_dir=ph_repo / "dist")
    assert cleanup["removed_syndication"] == ["syndication/brand-new-p2-nis2-audit-cost-calculator-linkedin.md"]
    assert cleanup["removed_overlays"] == [".agy/overlays/brand-new-p2-nis2-audit-cost-calculator.json"]
    assert (ph_repo / "syndication" / "section-179-calculator-linkedin.md").is_file()
