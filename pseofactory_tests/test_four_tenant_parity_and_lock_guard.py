import os
from pathlib import Path

from pseofactory.action_bus import HumanActionBus
from pseofactory.contracts import assert_youtube_transcript
from pseofactory.distributor import _generate_youtube_transcript
from pseofactory.gitops import (
    TenantFactoryLockGuard,
    isolated_worktree,
    reconcile_workspace_tracking_state,
)
from pseofactory.indexing.milestones import MilestoneTracker
from pseofactory.trends.db import TrendHistoryDB


def test_assert_youtube_transcript_lienbond_brand():
    transcript_pack = _generate_youtube_transcript(
        "contractor-license-bond-cost-calculator",
        property_id="lienbond",
    )
    assert assert_youtube_transcript(transcript_pack, property_id="lienbond") is True
    assert "LienBond" in transcript_pack["full_text"]


def test_reconcile_workspace_tracking_state_preserves_lienbond_queues(tmp_path: Path):
    queues_dir = tmp_path / ".agy" / "queues"
    queues_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = tmp_path / ".agy" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    lb_queue = queues_dir / "lienbond_release_queue.jsonl"
    lb_queue.write_text('{"event_id": "evt1", "status": "COMPLETED"}\n', encoding="utf-8")

    lb_dist_queue = queues_dir / "lienbond_distribution_queue.jsonl"
    lb_dist_queue.write_text('{"event_id": "evt2", "status": "COMPLETED"}\n', encoding="utf-8")

    reconcile_workspace_tracking_state(
        runs_dir=runs_dir,
        queues_dir=queues_dir,
        ledger_path=tmp_path / ".agy" / "ledger.json",
        tenant_repos=[],
    )

    assert lb_queue.is_file(), "reconcile_workspace_tracking_state must not delete lienbond_release_queue.jsonl"
    assert lb_dist_queue.is_file(), "reconcile_workspace_tracking_state must not delete lienbond_distribution_queue.jsonl"


def test_trend_history_db_supports_lienbond_property(tmp_path: Path):
    db_path = tmp_path / "trends.db"
    db = TrendHistoryDB(db_path=str(db_path))

    matrix = db.compile_statutory_economic_matrix("lienbond")
    assert matrix["property_id"] == "lienbond"
    assert "40 U.S.C. 3131" in matrix["statutory_authority"]

    db.upsert_statutory_economic_timeseries([
        {
            "series_id": "test_miller_act_threshold",
            "property_id": "lienbond",
            "jurisdiction": "US-FEDERAL",
            "statutory_citation": "40 U.S.C. 3131",
            "metric_key": "miller_act_federal_surety_threshold_usd",
            "metric_label": "Miller Act Threshold",
            "effective_year": 2026,
            "metric_value": 150000.0,
            "unit": "USD",
            "source_agency": "GSA / FAR",
        }
    ])
    rows = db.get_statutory_economic_timeseries(property_id="lienbond")
    assert any(r.series_id == "test_miller_act_threshold" for r in rows)


def test_tenant_factory_lock_guard_exports_env_marker(tmp_path: Path, monkeypatch):
    env_key = "PSEUFACTORY_HOLDS_LIENBOND_LOCK"
    monkeypatch.setenv("PSEUFACTORY_LOCK_DIR", str(tmp_path))
    monkeypatch.delenv(env_key, raising=False)
    with TenantFactoryLockGuard("lienbond", timeout=5.0):
        assert os.environ.get(env_key) == "1"
    assert os.environ.get(env_key) is None


def test_isolated_worktree_and_lock_guard_rollback_on_exception(tmp_path: Path, monkeypatch):
    import subprocess
    repo_dir = tmp_path / "mock_tenant"
    dist_dir = repo_dir / "dist"
    dist_dir.mkdir(parents=True)
    index_f = dist_dir / "index.html"
    index_f.write_text("<html>clean</html>", encoding="utf-8")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_dir, check=True, capture_output=True)

    with isolated_worktree(repo_dir) as wt_path:
        assert wt_path != repo_dir
        assert (wt_path / "dist" / "index.html").read_text(encoding="utf-8") == "<html>clean</html>"
        (wt_path / "dist" / "index.html").write_text("<html>worktree-edit</html>", encoding="utf-8")
        assert index_f.read_text(encoding="utf-8") == "<html>clean</html>"
    assert not wt_path.exists()

    monkeypatch.setenv("PSEUFACTORY_LOCK_DIR", str(tmp_path))
    try:
        with TenantFactoryLockGuard("lienbond", repo_path=repo_dir, timeout=5.0):
            index_f.write_text("<html>partial-corrupt-write</html>", encoding="utf-8")
            (dist_dir / "orphan.html").write_text("orphan", encoding="utf-8")
            raise RuntimeError("simulated mid-build failure")
    except RuntimeError:
        pass

    assert index_f.read_text(encoding="utf-8") == "<html>clean</html>"
    assert not (dist_dir / "orphan.html").exists()


def test_milestone_tracker_and_action_bus_support_lienbond(tmp_path: Path):
    tracker = MilestoneTracker(tenant="lienbond")
    assert tracker.tenant == "lienbond"

    bus = HumanActionBus(bus_path=tmp_path / "actions.json")
    item = bus.route_high_value_qualified_lead(
        property_id="lienbond",
        tool_slug="contractor-license-bond-cost-calculator",
        lead_id="lead_lienbond_test123",
        email="contractor@example.com",
        calculated_amount=250000.0,
        state="CA",
        capital_band="250k_to_1m",
        partner_sharing_consent=True,
    )
    assert item.property_id == "lienbond"


def test_recompute_tenant_lock_enforces_visual_primitive_and_quick_unlock_parity_and_gitignore(tmp_path: Path):
    import json
    import subprocess
    from pseofactory.drift import compute_dist_lock_metrics
    from pseofactory.gitops import recompute_and_amend_tenant_lock_and_ledger

    repo_dir = tmp_path / "mock_profithelm"
    tool_dir = repo_dir / "dist" / "tools" / "irs-2027-tax-brackets"
    tool_dir.mkdir(parents=True)

    (repo_dir / ".pseofactory.json").write_text('{"property_id": "profithelm"}\n', encoding="utf-8")
    (repo_dir / "substrate_lock.json").write_text('{"property_id": "profithelm"}\n', encoding="utf-8")
    (repo_dir / ".gitignore").write_text("__pycache__/\n.agy/\n", encoding="utf-8")

    stale_html = (
        '<!DOCTYPE html><html><head><style id="pseo-visual-primitives">/* stale */</style></head><body>'
        '<div id="partner-quote-intake-step" data-property-id="profithelm" data-tool-slug="irs-2027-tax-brackets" data-calculated-amount="125000"></div>'
        '<div id="calc-result-quick-unlock-bar" class="calc-result-quick-unlock-bar" data-contextual-v2="1">'
        '<div>Get Your 2027 2027 Federal &amp; State + Federal Tax Bracket &amp; W-4 Paycheck Plan</div>'
        '<form id="inline-worksheet-capture-form"><button id="btn-inline-worksheet-submit" style="white-space: nowrap;">Send</button></form>'
        '<div><a id="btn-calc-result-quick-unlock" style="white-space: nowrap;">Unlock</a></div>'
        "</div></body></html>"
    )
    index_f = tool_dir / "index.html"
    index_f.write_text(stale_html, encoding="utf-8")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_dir, check=True, capture_output=True)

    ok = recompute_and_amend_tenant_lock_and_ledger(repo_dir, property_id="profithelm", amend=False)
    assert ok is True

    gi_txt = (repo_dir / ".gitignore").read_text(encoding="utf-8")
    assert "syndication/" in gi_txt
    assert "dist/syndication/" in gi_txt

    healed_html = index_f.read_text(encoding="utf-8")
    assert "2027 2027 " not in healed_html
    assert "#btn-calc-result-quick-unlock," in healed_html
    assert 'id="btn-calc-result-quick-unlock"' in healed_html
    assert "white-space: normal; text-align: center; max-width: 100%; box-sizing: border-box;" in healed_html

    lock_data = json.loads((repo_dir / "substrate_lock.json").read_text(encoding="utf-8"))
    actual_fp, _ = compute_dist_lock_metrics(repo_dir / "dist")
    assert lock_data["dist_fingerprint"] == actual_fp


def test_quick_unlock_balanced_div_replacement_never_clobbers_downstream_forms():
    from pseofactory.visual_primitives import normalize_html_visual_primitives

    # Bar without inner </form>, followed by downstream #partner-quote-intake-form
    raw_html = (
        '<!DOCTYPE html><html><head><style id="pseo-visual-primitives">/* stale */</style></head><body>'
        '<div id="partner-quote-intake-step" data-property-id="prexvo" data-tool-slug="grad-plus-borrowing-cap-calculator" data-calculated-amount="65000">'
        '<div id="calc-result-quick-unlock-bar" class="calc-result-quick-unlock-bar" data-contextual-v2="1">'
        '<div class="nested-header"><div>Legacy form-less quick bar with RAP vs. IBR vs. Refinance amortization schedule</div></div>'
        "</div>"
        '<div class="important-downstream-section"><form id="partner-quote-intake-form"><button type="submit">Get Quote</button></form></div>'
        "</div></body></html>"
    )
    healed, _ = normalize_html_visual_primitives(raw_html)
    assert "important-downstream-section" in healed
    assert 'id="partner-quote-intake-form"' in healed
    assert "RAP vs. IBR vs. Refinance amortization schedule" not in healed
    assert "RAP vs. IBR vs. Standard amortization schedule" in healed


def test_write_substrate_lock_preserves_lienbond_fields_and_syncs_ledgers_and_freshness(tmp_path: Path):
    import json
    from pseofactory.drift import write_substrate_lock

    repo_dir = tmp_path / "lienbond"
    custom_dist = tmp_path / "custom_dist" / "tools" / "contractor-license-bond-cost-calculator"
    custom_dist.mkdir(parents=True)
    repo_dir.mkdir(parents=True)

    (custom_dist / "index.html").write_text(
        '<!DOCTYPE html><html><head><style id="pseo-visual-primitives">/* stale */</style></head><body><h1>Bond</h1></body></html>',
        encoding="utf-8",
    )
    (repo_dir / "freshness_audit_report.json").write_text(
        json.dumps({"merkle_drift": {"drifted": True, "substrate_hash": "old"}, "substrate_hash": "old"}),
        encoding="utf-8",
    )
    agy_dir = repo_dir / ".agy"
    agy_dir.mkdir(parents=True)
    (agy_dir / "engine_hash.json").write_text('{"engine_hash": "old"}\n', encoding="utf-8")
    (agy_dir / "asset_ledger.json").write_text("{}\n", encoding="utf-8")

    payload = write_substrate_lock(
        repo_dir,
        property_id="lienbond",
        expected_hash="deadbeef1234",
        dist_dir=tmp_path / "custom_dist",
        sync_ledgers=True,
    )
    assert payload["property_id"] == "lienbond"
    assert payload["tenant"] == "lienbond"
    assert payload["engine_sha256"] == "deadbeef1234"
    assert payload["engine_hash"] == "deadbeef1234"
    assert payload["substrate_hash"] == "deadbeef1234"
    assert payload["total_assets"] == 1

    freshness = json.loads((repo_dir / "freshness_audit_report.json").read_text(encoding="utf-8"))
    assert freshness["substrate_hash"] == "deadbeef1234"
    assert freshness["merkle_drift"]["substrate_hash"] == "deadbeef1234"
    assert freshness["merkle_drift"]["drifted"] is False

    eh_data = json.loads((agy_dir / "engine_hash.json").read_text(encoding="utf-8"))
    assert eh_data["engine_hash"] == "deadbeef1234"

    al_data = json.loads((agy_dir / "asset_ledger.json").read_text(encoding="utf-8"))
    assert "tools/contractor-license-bond-cost-calculator/index.html" in al_data["assets"]


def test_no_copy_oscillation_between_reposition_and_normalize_and_no_inline_lock_templates():
    from pseofactory.affiliates import (
        normalize_html_callout_message_match,
        reposition_affiliate_placements_from_gsc_signals,
    )
    import pseofactory.gitops as gitops_mod

    gitops_src = Path(gitops_mod.__file__).read_text(encoding="utf-8")
    assert '(BASE_DIR / "substrate_lock.json").write_text(' not in gitops_src

    for slug, title in (
        ("tcja-sunset-capital-gains", "TCJA Sunset Capital Gains Tax Calculator"),
        ("irs-interest-calculator-2027", "IRS Underpayment & Overpayment Interest Calculator 2027"),
        ("r-d-tax-credit-for-game-development-calculator", "R&D Tax Credit for Game Development Calculator"),
        ("section-199a-qbi-phaseout-wage-limit-calculator", "Section 199A QBI Deduction Phaseout & W-2 Wage Limit Calculator"),
        ("section-280g-golden-parachute-excise-tax-safe-harbor-calculator", "Section 280G Golden Parachute Safe Harbor Calculator"),
    ):
        sample_html = (
            f'<!DOCTYPE html><html><head><title>{title}</title>'
            f'<link rel="canonical" href="https://profithelm.com/tools/{slug}/" /></head><body>'
            f'<h1>{title}</h1>'
            '<div class="result-card"><div class="card-header"><h2 class="card-title">Projected Output</h2></div></div>'
            '<section class="affiliate-section affiliates-section"><a href="/r/crest_capital">Xendoo</a></section>'
            '<section class="overlay-section overlay-partner-offer affiliate-cta-section card" data-property="profithelm" data-partner="crest_capital">'
            '<h3 class="section-subtitle">Recommended Partner Solution</h3><a href="/r/crest_capital">CTA</a></section>'
            "</body></html>"
        )
        rep_html, _ = reposition_affiliate_placements_from_gsc_signals(sample_html, property_id="profithelm", slug=slug)
        norm_html = normalize_html_callout_message_match(rep_html, property_id="profithelm")
        assert norm_html == rep_html, f"Copy oscillation detected between reposition and normalize for {slug}"


def test_idempotency_of_write_substrate_lock_on_lienbond_result_box_and_prexvo_rap_meter():
    from pseofactory.affiliates import normalize_html_callout_message_match
    from pseofactory.visual_primitives import normalize_html_visual_primitives

    lb_html = (
        '<!DOCTYPE html><html><head><title>LienBond</title><link rel="canonical" href="https://lienbond.com/" /></head><body>'
        '<div id="partner-quote-intake-step" data-property-id="lienbond" data-tool-slug="contractor-license-bond-cost-calculator-by-credit-score" data-calculated-amount="125000"></div>'
        '<div class="result-box"><p><strong class="output-value" data-baseline-output="375.0">375</strong></p>'
        '<div class="calculation-variant" id="variant-baseline">Preferred Credit Tier Schedule ($375.00 = 1.5% rate) (<a href="#variant-accelerated">Compare Standard Market Variant</a>)'
        '\n          <div id="calc-result-quick-unlock-bar" class="calc-result-quick-unlock-bar" data-contextual-v2="1"><div>old</div></div>\n'
        '<div class="pro-hook-card"><span>Pro</span></div></div>'
        '<div class="calculation-variant" id="variant-accelerated">Standard Market Indemnity Variant (<a href="#variant-baseline">Return</a>)</div>'
        '</div><section class="affiliates-section"><a href="/r/simply_business">Simply Business</a></section></body></html>'
    )
    pass1, _ = normalize_html_visual_primitives(lb_html)
    pass1 = normalize_html_callout_message_match(pass1, property_id="lienbond")
    pass2, _ = normalize_html_visual_primitives(pass1)
    pass2 = normalize_html_callout_message_match(pass2, property_id="lienbond")
    assert pass2 == pass1
    assert 'Compare Standard Market Variant</a>)</div>' in pass2

    px_html = (
        '<!DOCTYPE html><html><head><title>Prexvo RAP</title><link rel="canonical" href="https://prexvo.com/tools/grad-plus-borrowing-cap-calculator/" /></head><body>'
        '<div class="calc-results-column"><h3 class="calc-column-title">Results</h3>\n'
        '      <div class="subsidy-meter-wrap" id="rap-subsidy-meter"><div class="subsidy-meter-legend">Legend</div></div>\n'
        '      <div id="calc-result-quick-unlock-bar" class="calc-result-quick-unlock-bar">Bar</div>\n'
        '</div><section class="refinance-partner-section"><a href="/r/splash_financial">Splash</a></section></body></html>'
    )
    px_pass1 = normalize_html_callout_message_match(px_html, property_id="prexvo")
    px_pass2 = normalize_html_callout_message_match(px_pass1, property_id="prexvo")
    assert px_pass2 == px_pass1


def test_cloudflare_redirects_cap_and_middleware_sync_across_four_tenants(tmp_path: Path):
    import json
    from pseofactory.edge import sync_tenant_edge_redirect_function
    from pseofactory.verifier import MasterSEOVerifier

    # 1. Simulate a 162-line _redirects file (>100 Cloudflare Pages hard ceiling)
    repo_dir = tmp_path / "profithelm-platform"
    dist_dir = repo_dir / "dist"
    (repo_dir / "functions" / "r").mkdir(parents=True)
    (repo_dir / "content").mkdir(parents=True)
    for route_rel in (
        "index.html",
        "about/index.html",
        "privacy/index.html",
        "tools/index.html",
        "tools/section-179-calculator/index.html",
        "tools/saas-runway-calculator/index.html",
        "tools/section-1031-calculator/index.html",
        "tools/prediction-market-odds/index.html",
        "tools/section-174-r-d-amortization-calculator-2026/index.html",
        "tools/section-301-import-tariff-landed-cost-calculator/index.html",
    ):
        p = dist_dir / route_rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("<!DOCTYPE html><html><body>OK</body></html>", encoding="utf-8")

    raw_lines = [
        "/methodology  /about/  301",
        "/methodology/  /about/  301",
        "/disclaimers  /privacy/  301",
        "/disclaimers/  /privacy/  301",
        "/terms  /privacy/  301",
        "/terms/  /privacy/  301",
        "/vs/ordermetrics  /tools/section-179-calculator/  301",
        "/vs/ordermetrics/  /tools/section-179-calculator/  301",
        "/vs/ordermetrics/*  /tools/section-179-calculator/  301",
        "/vs/*  /tools/saas-runway-calculator/  301",
    ]
    for idx in range(74):
        raw_lines.append(f"/tools/retired-calc-{idx}  /tools/  301")
        raw_lines.append(f"/tools/retired-calc-{idx}/  /tools/  301")
    raw_lines.extend(
        [
            "/tools/landed-cost-calculator  /tools/section-301-import-tariff-landed-cost-calculator/  301",
            "/tools/landed-cost-calculator/  /tools/section-301-import-tariff-landed-cost-calculator/  301",
            "/tools/section-174-r-d-amortization-calculator  /tools/section-174-r-d-amortization-calculator-2026/  301",
            "/tools/section-174-r-d-amortization-calculator/  /tools/section-174-r-d-amortization-calculator-2026/  301",
        ]
    )
    assert len(raw_lines) == 162
    (dist_dir / "_redirects").write_text("\n".join(raw_lines) + "\n", encoding="utf-8")
    (repo_dir / "content" / "redirects.json").write_text(
        json.dumps(
            {
                "/tools/landed-cost-calculator": {
                    "target": "/tools/section-301-import-tariff-landed-cost-calculator/",
                    "status": 301,
                },
                "/tools/section-174-r-d-amortization-calculator": {
                    "target": "/tools/section-174-r-d-amortization-calculator-2026/",
                    "status": 301,
                },
            }
        ),
        encoding="utf-8",
    )
    (repo_dir / "functions" / "_middleware.js").write_text(
        "export async function onRequest(context) {\n"
        "  const url = new URL(context.request.url);\n"
        "  const hostname = url.hostname.toLowerCase();\n"
        "  const pathname = url.pathname;\n"
        "  const legacySaaSRedirects = {\n"
        '    "/pricing": "/tools/saas-runway-calculator/",\n'
        "  };\n"
        "  if (legacySaaSRedirects[pathname]) {\n"
        "    return Response.redirect(`${url.origin}${legacySaaSRedirects[pathname]}`, 301);\n"
        "  }\n"
        "  const response = await context.next();\n"
        "  return response;\n"
        "}\n",
        encoding="utf-8",
    )

    # Raw 162-line _redirects must fail MasterSEOVerifier check_url_redirects_gate before compaction
    raw_gate = MasterSEOVerifier(dist_dir=dist_dir, domain="profithelm.com").check_url_redirects_gate()
    assert raw_gate["status"] == "FAIL"

    sync_tenant_edge_redirect_function(repo_dir, property_id="profithelm")

    compacted_txt = (dist_dir / "_redirects").read_text(encoding="utf-8")
    non_comment_lines = [
        ln for ln in compacted_txt.splitlines() if ln.strip() and not ln.strip().startswith("#")
    ]
    assert len(non_comment_lines) <= 95
    assert "/vs/ordermetrics  /tools/section-179-calculator/  301" in compacted_txt
    assert "/vs/ordermetrics/  /tools/section-179-calculator/  301" in compacted_txt
    assert "/vs/ordermetrics/*  /tools/section-179-calculator/  301" in compacted_txt

    from pseofactory.edge import (
        EdgeConfigStandards,
        compact_edge_redirects_to_cloudflare_cap,
        parse_edge_redirects_rules,
        validate_edge_redirects_file,
    )

    post_val = validate_edge_redirects_file(dist_dir / "_redirects")
    assert post_val["status"] == "PASS", post_val["issues"]
    assert post_val["active_rules_count"] <= EdgeConfigStandards.MAX_CLOUDFLARE_REDIRECTS_RULES
    assert post_val["total_rules_count"] == 162

    mw_txt = (repo_dir / "functions" / "_middleware.js").read_text(encoding="utf-8")
    assert '"/tools/landed-cost-calculator": "/tools/section-301-import-tariff-landed-cost-calculator/"' in mw_txt
    assert '"/tools/section-174-r-d-amortization-calculator/": "/tools/section-174-r-d-amortization-calculator-2026/"' in mw_txt
    assert "_matchedRedirectTarget" in mw_txt

    # Even if a tenant build overwrites dist/functions/_middleware.js while functions/_middleware.js is unchanged,
    # sync_tenant_edge_redirect_function must re-mirror functions/_middleware.js into dist/functions/_middleware.js.
    dist_fn_dir = dist_dir / "functions"
    dist_fn_dir.mkdir(parents=True, exist_ok=True)
    (dist_fn_dir / "_middleware.js").write_text("// stale builder middleware\n", encoding="utf-8")
    sync_tenant_edge_redirect_function(repo_dir, property_id="profithelm")
    assert (dist_fn_dir / "_middleware.js").read_text(encoding="utf-8") == mw_txt

    # Verify MasterSEOVerifier gate passes with 0 dead chains and <= 95 active rules
    gate_res = MasterSEOVerifier(dist_dir=dist_dir, domain="profithelm.com").check_url_redirects_gate()
    assert gate_res["status"] == "PASS", gate_res["issues"]

    # Verify all 4 workspace tenant dist/_redirects (when present) compact cleanly to <= 95 active rules with 0 dead chains
    for t_dir, t_dom in (
        ("profithelm-platform", "profithelm.com"),
        ("prexvo", "prexvo.com"),
        ("gainhelm", "gainhelm.com"),
        ("lienbond", "lienbond.com"),
    ):
        real_dist = Path("/home/ubuntuadmin/projects") / t_dir / "dist"
        real_red = real_dist / "_redirects"
        if real_red.is_file():
            comp = compact_edge_redirects_to_cloudflare_cap(real_red.read_text(encoding="utf-8"))
            act = parse_edge_redirects_rules(comp, include_middleware_overflow=False)
            tot = parse_edge_redirects_rules(comp, include_middleware_overflow=True)
            assert len(act) <= 95, f"{t_dir} active rules {len(act)} > 95"
            srcs = {s for s, _d, _c, _o in tot}
            for src, dst, code, _ov in tot:
                assert code == "301"
                assert dst not in srcs, f"{t_dir} redirect chain {src} -> {dst}"
                if dst.startswith("/") and "*" not in dst and ":" not in dst:
                    dst_clean = dst.strip("/")
                    dst_html = (real_dist / "index.html") if not dst_clean else (real_dist / dst_clean / "index.html")
                    assert dst_html.is_file(), f"{t_dir} dead redirect target {src} -> {dst}"


def test_lienbond_ci_deploy_syndication_and_metadata_parity(tmp_path: Path):
    import json
    from pseofactory.content_angles import expand_commercial_and_question_keywords
    from pseofactory.distributor import export_all_syndication_files
    from pseofactory.drift import write_substrate_lock
    from pseofactory.gitops import sync_tenant_test_isolation_guards

    lb_repo = tmp_path / "lienbond"
    (lb_repo / "lienbond").mkdir(parents=True)
    (lb_repo / ".github" / "workflows").mkdir(parents=True)
    (lb_repo / ".github" / "workflows" / "ci.yml").write_text("name: old\n", encoding="utf-8")
    (lb_repo / ".pseofactory.json").write_text('{"property_id": "lienbond"}\n', encoding="utf-8")
    (lb_repo / "dist" / "tools" / "miller-act-performance-and-payment-bond-premium-calculator").mkdir(parents=True)
    (lb_repo / "dist" / "index.html").write_text("<!DOCTYPE html><html><body>LienBond</body></html>", encoding="utf-8")
    (lb_repo / "dist" / "tools" / "miller-act-performance-and-payment-bond-premium-calculator" / "index.html").write_text(
        "<!DOCTYPE html><html><body>Miller Act</body></html>",
        encoding="utf-8",
    )

    sync_tenant_test_isolation_guards(lb_repo)
    lb_ci = (lb_repo / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "runs-on: ubuntu-latest" in lb_ci
    assert "runs-on: self-hosted" not in lb_ci
    assert "pytest -q tests/" in lb_ci
    assert "if: github.event_name == 'push' && github.ref == 'refs/heads/main'" in lb_ci
    assert "CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}" in lb_ci
    assert "CLOUDFLARE_ACCOUNT_ID: '8789c54bef2d281d4a8afb4df34f9878'" in lb_ci
    assert "npx wrangler pages deploy dist --project-name=lienbond --branch=main" in lb_ci

    kw_matrix = expand_commercial_and_question_keywords(
        "miller act performance and payment bond premium calculator",
        property_id="lienbond",
    )
    assert kw_matrix["property_id"] == "lienbond"
    assert "40 U.S.C. 3131" in kw_matrix["authority_basis"]

    synd_dir = lb_repo / "syndication"
    synd_dir.mkdir(parents=True)
    # Pre-seed contaminated ProfitHelm directory_manifest.json to verify clean overwrite
    (synd_dir / "directory_manifest.json").write_text('{"base_manifest": {"name": "ProfitHelm"}}\n', encoding="utf-8")
    export_all_syndication_files(
        output_dir=synd_dir,
        tools=[
            {
                "slug": "miller-act-performance-and-payment-bond-premium-calculator",
                "title": "Miller Act Performance and Payment Bond Premium Calculator",
                "primary_keyword": "miller act performance and payment bond premium calculator",
                "category": "surety_bonds",
            }
        ],
        property_id="lienbond",
    )
    dm = json.loads((synd_dir / "directory_manifest.json").read_text(encoding="utf-8"))
    assert dm["base_manifest"]["name"] == "LienBond"
    assert dm["base_manifest"]["social"]["linkedin_company_url"] == "https://www.linkedin.com/company/106482196"
    assert "profithelm" not in json.dumps(dm).lower()

    pack_path = synd_dir / "miller-act-performance-and-payment-bond-premium-calculator" / "syndication_pack.json"
    pack_txt = pack_path.read_text(encoding="utf-8")
    pack_data = json.loads(pack_txt)
    assert pack_data["keyword_intent_matrix"]["property_id"] == "lienbond"
    assert "profithelm" not in pack_txt.lower()
    assert (synd_dir / "ai_benchmarks" / "ai_benchmarks_manifest.json").is_file()

    write_substrate_lock(lb_repo, property_id="lienbond", expected_hash="cafebabe9999", sync_ledgers=True)
    assert (lb_repo / "freshness_audit_report.json").is_file()
    assert (lb_repo / "dist" / "ai-benchmarks" / "ai_benchmarks_manifest.json").is_file()
    fresh = json.loads((lb_repo / "freshness_audit_report.json").read_text(encoding="utf-8"))
    assert fresh["status"] == "PASS"
    assert fresh["substrate_hash"] == "cafebabe9999"


def test_youtube_upload_ledger_merges_into_uploaded_log_before_substrate_lock_hash(tmp_path: Path):
    import json
    from pseofactory.drift import compute_dist_lock_metrics, write_substrate_lock
    from pseofactory.video_factory import _load_upload_idempotency_map, _save_upload_idempotency_record

    repo_dir = tmp_path / "profithelm-platform"
    videos_dir = repo_dir / "dist" / "videos"
    videos_dir.mkdir(parents=True)
    (repo_dir / "dist" / "index.html").write_text("<!DOCTYPE html><html><body>PH</body></html>", encoding="utf-8")
    (videos_dir / "uploaded_log.json").write_text(
        json.dumps(
            [
                {
                    "slug": "existing-tool",
                    "video_id": "abc123xyz",
                    "title": "Existing Tool Video",
                    "uploaded_at": "2026-11-08T18:00:00Z",
                    "status": "uploaded_public",
                    "url": "https://www.youtube.com/watch?v=abc123xyz",
                    "caption_id": "cap-1",
                    "pinned_comment_id": "pin-1",
                }
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    _save_upload_idempotency_record(
        repo_dir,
        "profithelm",
        "1031-exchange-capital-gains-calculator",
        {
            "property_id": "profithelm",
            "slug": "1031-exchange-capital-gains-calculator",
            "video_id": "1Fx_mJRj9h0",
            "video_url": "https://www.youtube.com/watch?v=1Fx_mJRj9h0",
            "title": "1031 Exchange Capital Gains Calculator (2026 Rules)",
            "privacy": "public",
            "timestamp": "2026-11-10T18:00:12Z",
            "caption_id": "cap-1031",
            "pinned_comment_id": "pin-1031",
        },
    )
    assert (repo_dir / ".agy" / "youtube_upload_ledger.json.lock").exists()

    # Inject a foreign-prefixed record lacking inner property_id to verify strict key-prefix isolation
    ledger_file = repo_dir / ".agy" / "youtube_upload_ledger.json"
    ledger_data = json.loads(ledger_file.read_text(encoding="utf-8"))
    ledger_data["uploads"]["gainhelm:soc-2-audit-cost-calculator"] = {
        "slug": "soc-2-audit-cost-calculator",
        "video_id": "ghForeign99",
        "title": "SOC 2 Video",
        "timestamp": "2026-11-10T18:05:00Z",
    }
    ledger_file.write_text(json.dumps(ledger_data, indent=2) + "\n", encoding="utf-8")

    idemp_ph = _load_upload_idempotency_map(repo_dir, "profithelm")
    assert "1031-exchange-capital-gains-calculator" in idemp_ph
    assert "soc-2-audit-cost-calculator" not in idemp_ph

    lock_payload = write_substrate_lock(repo_dir, property_id="profithelm", expected_hash="beef1234", sync_ledgers=True)
    merged_log = json.loads((videos_dir / "uploaded_log.json").read_text(encoding="utf-8"))
    slugs = [entry["slug"] for entry in merged_log]
    assert slugs == ["existing-tool", "1031-exchange-capital-gains-calculator"]
    assert merged_log[1]["video_id"] == "1Fx_mJRj9h0"
    assert merged_log[1]["caption_id"] == "cap-1031"
    assert merged_log[1]["pinned_comment_id"] == "pin-1031"

    actual_fp, _ = compute_dist_lock_metrics(repo_dir / "dist")
    assert lock_payload["dist_fingerprint"] == actual_fp


def test_middleware_prefix_specificity_query_preservation_single_hop_and_corrupt_ledger_fail_closed(
    tmp_path: Path,
):
    import json
    import subprocess
    import pytest
    from pseofactory.edge import sync_tenant_edge_redirect_function
    from pseofactory.video_factory import _save_upload_idempotency_record

    repo_dir = tmp_path / "profithelm-platform"
    dist_dir = repo_dir / "dist"
    (repo_dir / "functions" / "r").mkdir(parents=True)
    for rel in (
        "index.html",
        "tools/index.html",
        "tools/section-179-calculator/index.html",
        "tools/saas-runway-calculator/index.html",
        "tools/section-301-import-tariff-landed-cost-calculator/index.html",
    ):
        hp = dist_dir / rel
        hp.parent.mkdir(parents=True, exist_ok=True)
        hp.write_text("<!DOCTYPE html><html><body>OK</body></html>", encoding="utf-8")

    (dist_dir / "_redirects").write_text(
        "/vs/ordermetrics  /tools/section-179-calculator/  301\n"
        "/vs/ordermetrics/  /tools/section-179-calculator/  301\n"
        "/vs/ordermetrics/*  /tools/section-179-calculator/  301\n"
        "/vs/*  /tools/saas-runway-calculator/  301\n"
        "/tools/landed-cost-calculator  /tools/section-301-import-tariff-landed-cost-calculator/  301\n",
        encoding="utf-8",
    )
    (repo_dir / "functions" / "_middleware.js").write_text(
        "export async function onRequest(context) {\n"
        "  const url = new URL(context.request.url);\n"
        "  const hostname = url.hostname.toLowerCase();\n"
        "  const pathname = url.pathname;\n\n"
        '  if (hostname === "www.profithelm.com") {\n'
        "    return Response.redirect(`https://profithelm.com${pathname}${url.search}`, 301);\n"
        "  }\n\n"
        "  const legacySaaSRedirects = {\n"
        '    "/pricing": "/tools/saas-runway-calculator/",\n'
        "  };\n\n"
        '  const _normRedirectPath = pathname.length > 1 && pathname.endsWith("/") ? pathname.slice(0, -1) : pathname;\n'
        '  const _matchedRedirectTarget = legacySaaSRedirects[pathname] || legacySaaSRedirects[_normRedirectPath] || legacySaaSRedirects[_normRedirectPath + "/"];\n'
        "  if (_matchedRedirectTarget) {\n"
        "    return Response.redirect(`${url.origin}${_matchedRedirectTarget}`, 301);\n"
        "  }\n\n"
        "  const legacyPrefixTargets = [\n"
        '    ["/vs/", "/tools/saas-runway-calculator/"],\n'
        "  ];\n"
        "  for (const [prefix, target] of legacyPrefixTargets) {\n"
        "    if (pathname.startsWith(prefix)) {\n"
        "      return Response.redirect(`${url.origin}${target}`, 301);\n"
        "    }\n"
        "  }\n\n"
        "  const response = await context.next();\n"
        "  return response;\n"
        "}\n",
        encoding="utf-8",
    )

    sync_tenant_edge_redirect_function(repo_dir, property_id="profithelm")
    mw_path = repo_dir / "functions" / "_middleware.js"
    first_pass = mw_path.read_text(encoding="utf-8")

    # Idempotency check on second pass
    sync_tenant_edge_redirect_function(repo_dir, property_id="profithelm")
    assert mw_path.read_text(encoding="utf-8") == first_pass

    node_probe = f"""
import {{ onRequest }} from {json.dumps(mw_path.as_uri())};

async function evalReq(rawUrl) {{
  const res = await onRequest({{
    request: new Request(rawUrl),
    next: async () => new Response("<html>OK</html>", {{ status: 200, headers: {{ "Content-Type": "text/html" }} }}),
  }});
  return {{ status: res.status, location: res.headers.get("location") }};
}}

const out = {{
  ordermetricsSubpath: await evalReq("https://profithelm.com/vs/ordermetrics/sample"),
  ordermetricsWithUtm: await evalReq("https://profithelm.com/vs/ordermetrics/sample?utm_source=linkedin&utm_medium=cpc"),
  vsGenericWithUtm: await evalReq("https://profithelm.com/vs/other-tool?utm_source=x"),
  exactWithUtm: await evalReq("https://profithelm.com/tools/landed-cost-calculator?utm_source=gsc&utm_campaign=nov"),
  wwwLegacyExactSingleHop: await evalReq("https://www.profithelm.com/tools/landed-cost-calculator?utm_source=gsc"),
  wwwLegacyPrefixSingleHop: await evalReq("https://www.profithelm.com/vs/ordermetrics/sample?ref=nav"),
  wwwCanonicalSingleHop: await evalReq("https://www.profithelm.com/tools/section-179-calculator/?ref=nav"),
  apexCanonicalPass: await evalReq("https://profithelm.com/tools/section-179-calculator/"),
}};
console.log(JSON.stringify(out));
"""
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", node_probe],
        capture_output=True,
        text=True,
        check=True,
    )
    results = json.loads(proc.stdout.strip())
    assert results["ordermetricsSubpath"] == {
        "status": 301,
        "location": "https://profithelm.com/tools/section-179-calculator/",
    }
    assert results["ordermetricsWithUtm"] == {
        "status": 301,
        "location": "https://profithelm.com/tools/section-179-calculator/?utm_source=linkedin&utm_medium=cpc",
    }
    assert results["vsGenericWithUtm"] == {
        "status": 301,
        "location": "https://profithelm.com/tools/saas-runway-calculator/?utm_source=x",
    }
    assert results["exactWithUtm"] == {
        "status": 301,
        "location": "https://profithelm.com/tools/section-301-import-tariff-landed-cost-calculator/?utm_source=gsc&utm_campaign=nov",
    }
    assert results["wwwLegacyExactSingleHop"] == {
        "status": 301,
        "location": "https://profithelm.com/tools/section-301-import-tariff-landed-cost-calculator/?utm_source=gsc",
    }
    assert results["wwwLegacyPrefixSingleHop"] == {
        "status": 301,
        "location": "https://profithelm.com/tools/section-179-calculator/?ref=nav",
    }
    assert results["wwwCanonicalSingleHop"] == {
        "status": 301,
        "location": "https://profithelm.com/tools/section-179-calculator/?ref=nav",
    }
    assert results["apexCanonicalPass"]["status"] == 200

    # Corrupt non-empty youtube_upload_ledger.json must fail closed without wiping existing bytes
    corrupt_ledger = repo_dir / ".agy" / "youtube_upload_ledger.json"
    corrupt_ledger.parent.mkdir(parents=True, exist_ok=True)
    corrupt_payload = '{"uploads": {"profithelm:keep-me": {"video_id": "abc"}} BROKEN'
    corrupt_ledger.write_text(corrupt_payload, encoding="utf-8")
    with pytest.raises(RuntimeError, match="Corrupt non-empty YouTube upload ledger"):
        _save_upload_idempotency_record(
            repo_root=repo_dir,
            property_id="profithelm",
            slug="new-tool",
            record={"slug": "new-tool", "video_id": "xyz987"},
        )
    assert corrupt_ledger.read_text(encoding="utf-8") == corrupt_payload







