"""
Batch 3A regression suite:
1. Purge dead/harmful syndication channels from active_channels & export_all_syndication_files
   and actively purge stale files while keeping zero-URL Reddit monitoring separate from auto-posting.
2. Autonomous per-brand GitHub statutory dataset repo bundle exporter + verify_schedules.py self-test.
3. Zero-dependency static embeddable calculator widget + pure-brand rel="nofollow" attribution.
4. Upgraded ParasiteLedger (.agy/external_authority_ledger.json) + rel="nofollow" embed verification
   + bounded read-only maintenance.audit_external_authority_liveness.
5. Public media-kit.json strips shared EIN (41-***1423) and Spokane boilerplate unless explicitly
   configured in that tenant's own .pseofactory.json.

Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Dict

import pytest

from pseofactory import compiler as compiler_mod
from pseofactory import distributor as dist_mod
from pseofactory import maintenance as maint_mod
from pseofactory.parasite_ledger import (
    AUTHORITY_SURFACE_DIRECTORY,
    AUTHORITY_SURFACE_EMBED,
    AUTHORITY_SURFACE_GITHUB_REPO,
    LIVE,
    REMOVED,
    ParasiteLedger,
    resolve_tenant_external_authority_ledger_path,
    verify_embed_attribution_html,
)
from pseofactory.truth_pack import load_truth_pack


def test_purged_channels_removed_from_active_and_stale_files_purged(tmp_path: Path) -> None:
    synd_dir = tmp_path / "syndication"
    slug = "section-179-calculator"
    tool_dir = synd_dir / slug
    tool_dir.mkdir(parents=True)

    stale_files = (
        "google_sites.html",
        "quora.md",
        "quora.txt",
        "github_gist.json",
        "github_gist.md",
        "section_179_calculator_proof.py",
        "ghost.json",
        "ghost_article.md",
        "facebook.txt",
        "x_post.txt",
        "linkedin_company.txt",
        "linkedin_pulse.md",
        "substack_teardown.md",
        "reddit.md",
    )
    for sf in stale_files:
        (tool_dir / sf).write_text("stale content", encoding="utf-8")
    (synd_dir / "google_sites_entity_buffers.md").write_text("stale", encoding="utf-8")

    tools = [{"slug": slug, "title": "Section 179 Calculator"}]
    out = dist_mod.export_all_syndication_files(
        output_dir=synd_dir,
        tools=tools,
        property_id="profithelm",
    )
    assert out == synd_dir

    for sf in stale_files:
        assert not (tool_dir / sf).exists(), f"Stale file {sf} should have been purged"
    assert not (synd_dir / "google_sites_entity_buffers.md").exists()

    assert (tool_dir / "syndication_pack.json").is_file()
    assert (tool_dir / "outreach_pitch.txt").is_file()
    assert (tool_dir / "youtube_metadata.json").is_file()
    assert (synd_dir / "embed_snippets.json").is_file()
    assert (synd_dir / "github_repo_bundle" / "README.md").is_file()

    for removed_ch in (
        "google_sites",
        "quora",
        "github_gist",
        "ghost",
        "x",
        "facebook",
        "linkedin_company",
        "linkedin_pulse",
        "substack_teardown",
    ):
        assert removed_ch not in dist_mod.DEFAULT_ACTIVE_CHANNELS
    assert "github_statutory_repo" in dist_mod.DEFAULT_ACTIVE_CHANNELS

    # Legacy helpers remain safely importable
    assert callable(dist_mod.generate_ghost_article)
    assert callable(dist_mod.generate_exact_match_github_gist)
    assert callable(dist_mod.generate_quora_thread_answer)
    assert callable(dist_mod.generate_parasite_google_sites_html)


def test_zero_url_reddit_monitoring_separated_from_autoposting(tmp_path: Path) -> None:
    tools = [{"slug": "soc-2-audit-cost-calculator", "title": "SOC 2 Audit Cost Calculator"}]
    plan = dist_mod.build_reddit_monitoring_discovery_plan(
        property_id="gainhelm",
        tools=tools,
        subreddits=["r/cybersecurity", "r/compliance"],
    )
    assert plan["mode"] == "READ_ONLY_MONITORING_DISCOVERY"
    assert plan["auto_post_enabled"] is False
    assert plan["never_auto_post"] is True
    assert plan["outbound_urls_allowed"] == 0
    plan_blob = json.dumps(plan)
    assert "http://" not in plan_blob
    assert "https://" not in plan_blob
    assert "gainhelm.com" not in plan_blob

    dist_res = dist_mod.dispatch_to_distribution_lead(
        run_id="batch3a-reddit-guard",
        property_id="gainhelm",
        dry_run=True,
        dist_dir=tmp_path / "dist",
        tools=tools,
    )
    assert "reddit" not in dist_res["channels"]
    assert "reddit" in dist_res["omitted_channels"]
    assert "github_statutory_repo" in dist_res["channels"]


def test_github_statutory_repo_bundle_and_verify_script(tmp_path: Path) -> None:
    tp = load_truth_pack("gainhelm", allow_expired=True)
    tools = [{"slug": "soc-2-audit-cost-calculator", "title": "SOC 2 Audit Cost Calculator"}]
    synd_dir = tmp_path / "syndication"

    res = dist_mod.export_brand_github_statutory_repo_bundle(
        property_id="gainhelm",
        domain="gainhelm.com",
        tools=tools,
        truth_pack=tp,
        output_dir=synd_dir,
    )
    bundle_dir = Path(res["bundle_dir"])
    assert bundle_dir == synd_dir / "github_repo_bundle"
    json_path = bundle_dir / "datasets" / "statutory_schedules.json"
    csv_path = bundle_dir / "datasets" / "statutory_schedules.csv"
    readme_path = bundle_dir / "README.md"
    verify_path = bundle_dir / "verify_schedules.py"

    assert json_path.is_file()
    assert csv_path.is_file()
    assert readme_path.is_file()
    assert verify_path.is_file()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["property_id"] == "gainhelm"
    assert payload["domain"] == "gainhelm.com"
    assert payload["record_count"] == len(payload["schedules"]) > 0

    with open(csv_path, "r", encoding="utf-8", newline="") as cf:
        csv_rows = list(csv.DictReader(cf))
    assert len(csv_rows) == payload["record_count"]

    readme_txt = readme_path.read_text(encoding="utf-8")
    assert "https://gainhelm.com/" in readme_txt
    assert (".gov" in readme_txt) or ("acq.osd.mil" in readme_txt) or ("federalregister.gov" in readme_txt)

    for file_p in (json_path, csv_path, readme_path, verify_path):
        txt = file_p.read_text(encoding="utf-8")
        assert "coskunarif" not in txt.lower()
        assert "\u2014" not in txt
        assert "\u2013" not in txt

    proc = subprocess.run(
        [sys.executable, str(verify_path)],
        cwd=str(bundle_dir),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"verify_schedules.py failed: {proc.stderr}"
    verify_out = json.loads(proc.stdout.strip())
    assert verify_out["status"] == "PASS"
    assert verify_out["rows"] == payload["record_count"]


def test_static_embed_widget_and_nofollow_attribution(tmp_path: Path) -> None:
    snippet = compiler_mod.build_embed_snippet_html(
        domain="https://lienbond.com/",
        brand_name="LienBond",
        slug="bid-bond-calculator",
    )
    assert '<a href="https://lienbond.com/tools/bid-bond-calculator/" rel="nofollow">Powered by LienBond</a>' in snippet
    assert "/static/js/embed-widget.js" in snippet
    assert "\u2014" not in snippet
    assert "\u2013" not in snippet

    # Verify distributor wrapper delegates identically
    assert dist_mod.build_embed_snippet_html("lienbond.com", "LienBond", "bid-bond-calculator") == snippet

    dist_dir = tmp_path / "dist"
    res = compiler_mod.write_static_embed_widget_assets(
        dist_dir=dist_dir,
        domain="lienbond.com",
        brand_name="LienBond",
        tools=[{"slug": "bid-bond-calculator"}],
    )
    js_path = Path(res["embed_js_path"])
    assert js_path == dist_dir / "static" / "js" / "embed-widget.js"
    assert js_path.is_file()
    js_txt = js_path.read_text(encoding="utf-8")
    assert "iframe" in js_txt
    assert "nofollow" in js_txt
    assert "Powered by " in js_txt
    assert "cdn." not in js_txt.lower()
    assert "\u2014" not in js_txt
    assert "\u2013" not in js_txt

    snippets_json = json.loads((dist_dir / "embed" / "snippets.json").read_text(encoding="utf-8"))
    assert snippets_json["snippets"]["bid-bond-calculator"] == snippet


def test_external_authority_ledger_and_readonly_maintenance_audit(tmp_path: Path) -> None:
    # Verify verify_embed_attribution_html rejects dofollow & missing links, accepts rel="nofollow"
    ok_attr = verify_embed_attribution_html(
        '<div><a href="https://prexvo.com/tools/pslf-calculator/" rel="nofollow">Powered by Prexvo</a></div>',
        "prexvo.com",
    )
    assert ok_attr["valid"] is True
    assert ok_attr["reason"] == "OK"

    dofollow_attr = verify_embed_attribution_html(
        '<div><a href="https://prexvo.com/tools/pslf-calculator/">Best PSLF Calculator</a></div>',
        "prexvo.com",
    )
    assert dofollow_attr["valid"] is False
    assert dofollow_attr["reason"] == "MISSING_REL_NOFOLLOW"

    missing_attr = verify_embed_attribution_html("<div>No link</div>", "prexvo.com")
    assert missing_attr["valid"] is False
    assert missing_attr["reason"] == "MISSING_TARGET_LINK"

    class _AuthorityHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            routes: Dict[str, tuple[int, str]] = {
                "/embed-ok": (
                    200,
                    '<html><body><a href="https://prexvo.com/tools/pslf/" rel="nofollow">Powered by Prexvo</a></body></html>',
                ),
                "/embed-dofollow": (
                    200,
                    '<html><body><a href="https://prexvo.com/tools/pslf/">PSLF Tool</a></body></html>',
                ),
                "/github-ok": (200, "<html><body>Prexvo Statutory Repo</body></html>"),
                "/directory-gone": (404, "Not Found"),
            }
            code, body = routes.get(self.path, (404, ""))
            self.send_response(code)
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))

        def log_message(self, *args):
            pass

    srv = HTTPServer(("127.0.0.1", 0), _AuthorityHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        base = f"http://127.0.0.1:{srv.server_port}"
        repo_root = tmp_path / "prexvo_repo"
        ledger = ParasiteLedger.for_tenant(repo_root)
        assert ledger.path == resolve_tenant_external_authority_ledger_path(repo_root)

        assert ledger.record_authority_asset(
            url=f"{base}/embed-ok",
            surface_type=AUTHORITY_SURFACE_EMBED,
            platform="partner_blog",
            tenant="prexvo",
            target_domain="prexvo.com",
            tool_slug="pslf",
        )
        assert ledger.record_authority_asset(
            url=f"{base}/embed-dofollow",
            surface_type=AUTHORITY_SURFACE_EMBED,
            platform="partner_blog_2",
            tenant="prexvo",
            target_domain="prexvo.com",
            tool_slug="pslf",
        )
        assert ledger.record_authority_asset(
            url=f"{base}/github-ok",
            surface_type=AUTHORITY_SURFACE_GITHUB_REPO,
            platform="github",
            tenant="prexvo",
            target_domain="prexvo.com",
        )
        assert ledger.record_authority_asset(
            url=f"{base}/directory-gone",
            surface_type=AUTHORITY_SURFACE_DIRECTORY,
            platform="crunchbase",
            tenant="prexvo",
            target_domain="prexvo.com",
        )

        with pytest.raises(ValueError, match="Unsupported B2B directory"):
            ledger.record_authority_asset(
                url=f"{base}/spam-dir",
                surface_type=AUTHORITY_SURFACE_DIRECTORY,
                platform="spam_link_farm",
                tenant="prexvo",
            )

        res = ledger.check_authority_liveness(max_urls=10)
        assert res[f"{base}/embed-ok"]["state"] == LIVE
        assert res[f"{base}/embed-ok"]["attribution_valid"] is True
        assert res[f"{base}/embed-dofollow"]["state"] == LIVE
        assert res[f"{base}/embed-dofollow"]["attribution_valid"] is False
        assert res[f"{base}/embed-dofollow"]["attribution_reason"] == "MISSING_REL_NOFOLLOW"
        assert res[f"{base}/github-ok"]["state"] == LIVE
        assert res[f"{base}/directory-gone"]["state"] == REMOVED

        # Read-only maintenance audit must not mutate the ledger file on disk
        before_bytes = ledger.path.read_bytes()
        audit_rep = maint_mod.audit_external_authority_liveness(
            repo_root=repo_root,
            property_id="prexvo",
            target_domain="prexvo.com",
            max_urls=2,
            perform_network_checks=True,
        )
        after_bytes = ledger.path.read_bytes()
        assert before_bytes == after_bytes
        assert audit_rep["read_only"] is True
        assert audit_rep["inspected_count"] == 2
        assert audit_rep["tracked_count"] == 4

        full_rep = maint_mod.audit_external_authority_liveness(
            repo_root=repo_root,
            property_id="prexvo",
            target_domain="prexvo.com",
            max_urls=10,
            perform_network_checks=False,
        )
        assert full_rep["status"] == "ATTENTION_REQUIRED"
        assert full_rep["live_count"] == 3
        assert full_rep["removed_count"] == 1
        assert len(full_rep["attribution_failures"]) == 1
    finally:
        srv.shutdown()


def test_media_kit_strips_shared_ein_and_spokane_unless_configured(tmp_path: Path) -> None:
    # 1. Tenant without EIN/headquarters in .pseofactory.json must NOT leak shared ProfitHelm boilerplate
    gh_root = tmp_path / "gainhelm"
    gh_dist = gh_root / "dist"
    gh_dist.mkdir(parents=True)
    (gh_root / ".pseofactory.json").write_text(
        json.dumps({"property_id": "gainhelm", "domain": "gainhelm.com", "brand_name": "GainHelm"}),
        encoding="utf-8",
    )
    (gh_dist / "index.html").write_text(
        "<!doctype html><html><head></head><body><h1>GainHelm</h1></body></html>",
        encoding="utf-8",
    )
    maint_mod.RetroReflectionEngine.sync_tenant_publisher_prerequisites(
        gh_dist, "gainhelm", "https://gainhelm.com"
    )
    gh_mk_raw = (gh_dist / "media-kit.json").read_text(encoding="utf-8")
    assert "41-***1423" not in gh_mk_raw
    assert "522 W Riverside Ave Ste N" not in gh_mk_raw
    gh_mk = json.loads(gh_mk_raw)
    assert "ein_masked" not in gh_mk
    assert "headquarters" not in gh_mk

    # 2. Tenant with explicit .pseofactory.json entity values preserves its own values
    custom_root = tmp_path / "profithelm"
    custom_dist = custom_root / "dist"
    custom_dist.mkdir(parents=True)
    (custom_root / ".pseofactory.json").write_text(
        json.dumps(
            {
                "property_id": "profithelm",
                "domain": "profithelm.com",
                "ein_masked": "99-***0001",
                "headquarters": "100 Main St, Austin, TX 78701",
            }
        ),
        encoding="utf-8",
    )
    (custom_dist / "index.html").write_text(
        "<!doctype html><html><head></head><body><h1>ProfitHelm</h1></body></html>",
        encoding="utf-8",
    )
    maint_mod.RetroReflectionEngine.sync_tenant_publisher_prerequisites(
        custom_dist, "profithelm", "https://profithelm.com"
    )
    custom_mk = json.loads((custom_dist / "media-kit.json").read_text(encoding="utf-8"))
    assert custom_mk["ein_masked"] == "99-***0001"
    assert custom_mk["headquarters"] == "100 Main St, Austin, TX 78701"

    # 3. Direct compiler.sanitize_public_media_kit_payload check
    sanitized = compiler_mod.sanitize_public_media_kit_payload(
        {
            "property_id": "prexvo",
            "ein_masked": "41-***1423",
            "headquarters": "522 W Riverside Ave Ste N, Spokane, WA 99201",
        },
        repo_root=gh_root,
    )
    assert "ein_masked" not in sanitized
    assert "headquarters" not in sanitized


def test_zero_forbidden_dashes_in_batch3_modified_files() -> None:
    worktree_root = Path(__file__).resolve().parent.parent
    for rel in (
        "pseofactory/distributor.py",
        "pseofactory/parasite_ledger.py",
        "pseofactory/compiler.py",
        "pseofactory/maintenance.py",
        "pseofactory_tests/test_wave4_distribution_truth.py",
        "pseofactory_tests/test_batch3_autonomous_offsite.py",
    ):
        txt = (worktree_root / rel).read_text(encoding="utf-8")
        assert "\u2014" not in txt, f"U+2014 found in {rel}"
        assert "\u2013" not in txt, f"U+2013 found in {rel}"
