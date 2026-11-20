"""
Tests for LienBond (lienbond.com) greenfield tenant compilation, live domain
registration availability verification, and upgraded jurisdiction-locked
statutory execution packets across all tenants.

Zero em-dashes. Zero en-dashes.
"""

import re
from pathlib import Path

import pytest

from pseofactory.affiliates import (
    LIENBOND_AFFILIATES,
    LIENBOND_MONETIZED_CALCULATOR_SLUGS,
    bind_asset_partner_roster,
    get_affiliate_route,
    get_affiliates_for_property,
)
from pseofactory.browser_verifier import UnifiedBrowserAuditor
from pseofactory.compiler import (
    LIENBOND_EXPANSION_SPECS,
    _format_human_readable_formula,
    compile_high_effort_page,
    compile_lienbond_estate,
    get_lienbond_expansion_specs,
)
from pseofactory.contracts import assert_no_forbidden_dashes
from pseofactory.edge import (
    generate_edge_lead_capture_function,
    generate_edge_redirect_function,
    generate_edge_telemetry_function,
)
from pseofactory.lead_classification import OWN_TENANT_DOMAINS
from pseofactory.market_intel import (
    evaluate_greenfield_tenant_candidates,
    verify_domain_registration_availability,
)
from pseofactory.partner_tracker import (
    evaluate_lead_quote_threshold,
    resolve_lead_monetization_offer,
    resolve_post_calculation_upgrade_spec,
)
from pseofactory.tenant_facts import (
    CANONICAL_TENANT_IDS,
    TenantFactStore,
    get_tenant_contract,
    resolve_canonical_property_id,
)


def test_domain_registration_availability_verification() -> None:
    """Verifies that lienbond.com is available while insurebond.com is registered."""
    avail_res = verify_domain_registration_availability("lienbond.com", probe_live=False)
    assert avail_res["domain"] == "lienbond.com"
    assert avail_res["available"] is True
    assert avail_res["status"] == "AVAILABLE"
    assert avail_res["cloudflare_wholesale_price_usd"] == 10.46

    reg_res = verify_domain_registration_availability("insurebond.com", probe_live=False)
    assert reg_res["domain"] == "insurebond.com"
    assert reg_res["available"] is False
    assert reg_res["status"] == "REGISTERED"

    candidates = evaluate_greenfield_tenant_candidates()
    surety_eval = next(c for c in candidates if c.vertical_id == "commercial_surety_insurance")
    assert surety_eval.recommended_domain == "insurebond.com"
    assert surety_eval.recommended_domain_available is False
    assert surety_eval.recommended_available_tenant_id == "lienbond"
    assert surety_eval.recommended_available_domain == "lienbond.com"
    assert "lienbond.com" in surety_eval.verified_available_domains


def test_lienbond_tenant_contract_and_affiliate_isolation() -> None:
    """Verifies LienBond tenant contract, domain classification, and affiliate roster isolation."""
    assert CANONICAL_TENANT_IDS == ["profithelm", "prexvo", "gainhelm", "lienbond"]
    assert "lienbond.com" in OWN_TENANT_DOMAINS
    assert resolve_canonical_property_id("lienbond") == "lienbond"
    assert resolve_canonical_property_id("https://lienbond.com/tools/contractor-license-bond-cost-calculator/") == "lienbond"

    contract = get_tenant_contract("lienbond")
    assert contract.property_id == "lienbond"
    assert contract.domain == "lienbond.com"
    assert len(contract.default_core_tools) == 10

    profile = TenantFactStore().get_profile("lienbond")
    assert profile.brand_name == "LienBond"
    assert profile.canonical_domain == "https://lienbond.com"

    affs = get_affiliates_for_property("lienbond")
    assert set(affs.keys()) == set(LIENBOND_AFFILIATES.keys())
    assert "suretybonds_direct" in affs
    assert "simply_business" in affs
    assert "levelset_lien_filing" in affs

    for slug in LIENBOND_MONETIZED_CALCULATOR_SLUGS:
        route = get_affiliate_route("lienbond", slug)
        assert route["property_id"] == "lienbond"
        assert route["partner_key"] in LIENBOND_AFFILIATES
        roster = bind_asset_partner_roster("lienbond", slug)
        assert roster["property_id"] == "lienbond"
        assert len(roster["roster_keys"]) >= 2


def test_upgraded_statutory_execution_packets_across_all_tenants() -> None:
    """Verifies that edge lead-capture functions for all 4 tenants include statutory_execution_artifacts and preview gating."""
    expected_suffixes = {
        "gainhelm": "GAINHELM",
        "prexvo": "PREXVO",
        "profithelm": "PROFITHELM",
        "lienbond": "LIENBOND",
    }
    for prop, suffix in expected_suffixes.items():
        js_code = generate_edge_lead_capture_function(prop)
        assert_no_forbidden_dashes(js_code, context=f"edge lead-capture {prop}")
        assert "statutory_execution_artifacts" in js_code
        assert "UNREDACTED_READY_FOR_FILING" in js_code
        assert "PREVIEW_REDACTED_PENDING_CHECKOUT" in js_code
        assert f'"payment_intent_data[statement_descriptor_suffix]": "{suffix}"' in js_code

    redir_js = generate_edge_redirect_function("lienbond")
    assert_no_forbidden_dashes(redir_js, context="lienbond redirect js")
    assert "lienbond.com" in redir_js

    tel_js = generate_edge_telemetry_function("lienbond")
    assert_no_forbidden_dashes(tel_js, context="lienbond telemetry js")
    assert "LIENBOND_TELEMETRY_KV" in tel_js

    offer = resolve_lead_monetization_offer("lienbond", "contractor-license-bond-cost-calculator")
    assert offer["offer_sku"] == "lb_surety_lien_wh347_packet"
    assert offer["offer_price_usd"] == 79.0

    wc_offer = resolve_lead_monetization_offer("lienbond", "workers-comp-class-code-rate-calculator")
    assert wc_offer["offer_sku"] == "lb_workers_comp_emr_audit_packet"
    assert wc_offer["offer_price_usd"] == 49.0

    thresh = evaluate_lead_quote_threshold("lienbond", "performance-payment-bond-cost-calculator", 120000.0)
    assert thresh["eligible"] is True
    assert thresh["qualifies_for_quote_intake"] is True
    assert thresh["primary_partner_key"] == "suretybonds_direct"

    upgrade_spec = resolve_post_calculation_upgrade_spec("lienbond", "mechanics-lien-filing-deadline-calculator")
    assert upgrade_spec is not None
    assert upgrade_spec["offer_sku"] == "lb_surety_lien_wh347_packet"
    assert upgrade_spec["trend_series_count"] >= 3


def test_compile_lienbond_estate_end_to_end(tmp_path: Path) -> None:
    """Compiles the full LienBond estate and verifies all 10 calculators, manifests, sitemaps, and edge functions."""
    specs = get_lienbond_expansion_specs()
    assert len(specs) == 10

    first_page = compile_high_effort_page(specs[0])
    assert first_page["tenant"] == "lienbond"
    assert first_page["verified"] is True
    assert "https://lienbond.com/tools/workers-compensation-class-code-rate-calculator-by-state/" in first_page["html"]

    estate_res = compile_lienbond_estate(tmp_path)
    assert estate_res["property_id"] == "lienbond"
    assert estate_res["compiled_count"] == 10

    for slug in LIENBOND_MONETIZED_CALCULATOR_SLUGS:
        leaf_html = tmp_path / "dist" / "tools" / slug / "index.html"
        manifest_json = tmp_path / "dist" / "manifests" / f"{slug}.json"
        assert leaf_html.is_file(), f"Missing compiled calculator {slug}"
        assert manifest_json.is_file(), f"Missing manifest {slug}"
        html_txt = leaf_html.read_text(encoding="utf-8")
        assert_no_forbidden_dashes(html_txt, context=f"lienbond {slug}")
        assert 'data-property="lienbond"' in html_txt
        assert 'data-property-id="lienbond"' in html_txt

    assert (tmp_path / ".pseofactory.json").is_file()
    assert (tmp_path / "wrangler.toml").is_file()
    assert (tmp_path / "functions" / "r" / "[partner].js").is_file()
    assert (tmp_path / "functions" / "api" / "lead-capture.js").is_file()
    assert (tmp_path / "functions" / "api" / "telemetry.js").is_file()
    assert (tmp_path / "functions" / "api" / "checkout.js").is_file()
    assert (tmp_path / "functions" / "api" / "lead-fulfillment.js").is_file()

    import json
    from pseofactory.maintenance import RetroReflectionEngine

    retro_res = RetroReflectionEngine.retrofit_estate(tmp_path / "dist", "lienbond")
    assert retro_res["status"] == "PASS"
    audit_res = RetroReflectionEngine.audit_estate(tmp_path / "dist", "lienbond")
    assert audit_res["status"] == "PASS"
    assert audit_res["stale_count"] == 0
    cat_obj = json.loads((tmp_path / "dist" / "catalog.json").read_text(encoding="utf-8"))
    assert cat_obj["property_id"] == "lienbond"
    assert cat_obj["domain"] == "lienbond.com"


def test_provision_tenant_custom_domain_and_dns_reconciler() -> None:
    """Verifies automated Cloudflare Pages custom-domain binding and DNS CNAME/SPF/DMARC provisioning plan for lienbond.com."""
    from pseofactory.infra_audit import provision_tenant_custom_domain_and_dns

    plan = provision_tenant_custom_domain_and_dns(
        property_id="lienbond",
        domain="lienbond.com",
        pages_target="lienbond.pages.dev",
        execute_live=False,
    )
    assert plan["status"] == "DRY_RUN_PLANNED"
    assert plan["property_id"] == "lienbond"
    assert plan["domain"] == "lienbond.com"
    assert plan["pages_target"] == "lienbond.pages.dev"
    assert plan["pages_custom_domains_attached"] == ["lienbond.com", "www.lienbond.com"]
    assert len(plan["planned_dns_records"]) == 4
    cname_targets = [r["content"] for r in plan["planned_dns_records"] if r["type"] == "CNAME"]
    assert cname_targets == ["lienbond.pages.dev", "lienbond.pages.dev"]


def test_lienbond_p2_daily_build_and_rebuild_persistence(tmp_path: Path) -> None:
    """
    Verifies that execute_autonomous_daily_trend_page_build:
      1. Builds a Factor-7-verified P2 page for lienbond and records source='p2_autonomous_daily_builder'
         in content/deployed_voids.json.
      2. Preserves the P2 page across subsequent compile_lienbond_estate() rebuilds.
    """
    import json
    from pseofactory.compiler import compile_lienbond_estate
    from pseofactory.pipeline import (
        ConfigurablePropertyAdapter,
        TenantRegistry,
        execute_autonomous_daily_trend_page_build,
    )

    lb_root = tmp_path / "lienbond"
    init_res = compile_lienbond_estate(lb_root)
    assert init_res["status"] == "PASS"
    assert init_res["compiled_count"] == 10

    reg = TenantRegistry()
    reg.register_adapter(
        ConfigurablePropertyAdapter(
            property_id="lienbond",
            brand_name="LienBond",
            domain="lienbond.com",
            canonical_base="https://lienbond.com",
            dist_dir=lb_root / "dist",
            repo_path=lb_root,
            tools=[{"slug": p["slug"]} for p in init_res["compiled_pages"]],
        )
    )
    queue_file = tmp_path / "void_candidates.jsonl"
    ledger_file = tmp_path / "daily_ledger.json"
    candidate = {
        "property_id": "lienbond",
        "tenant": "lienbond",
        "slug": "subcontractor-default-insurance-sdi-vs-performance-bond-cost-calculator",
        "query": "subcontractor default insurance sdi vs performance bond cost calculator",
        "title": "SDI vs Subcontractor Performance Bond Calculator",
        "action": "BUILD_PAGE",
        "status": "PENDING",
        "composite_profit_yield": 96.1,
        "statutory_authority": "40 U.S.C. Section 3131 (Miller Act) & AIA Document A312-2010 Dual-Obligee Subcontractor Surety Standards",
        "economic_dataset": "SFAA Commercial Surety Loss Cost Series & BLS PPI Construction Inputs WPUIP2311001",
        "model_name": "LienBond-SDI-vs-Subcontractor-Performance-Bond-Spread-Model-2026",
        "formula": "round((annual_subcontract_volume * (sub_bond_rate_pct / 100.0)) - ((annual_subcontract_volume * (sdi_base_rate_pct / 100.0)) + (expected_default_claims * sdi_deductible_per_claim)), 2)",
        "inputs": {
            "annual_subcontract_volume": 50000000.0,
            "sub_bond_rate_pct": 1.35,
            "sdi_base_rate_pct": 0.65,
            "expected_default_claims": 0.5,
            "sdi_deductible_per_claim": 250000.0,
        },
        "published_output": 225000.0,
        "sample_calculation": (
            "General contractor managing $50,000,000.00 in annual subcontract volume comparing 1.35% "
            "subcontractor performance bonds ($675,000.00) against a 0.65% Subcontractor Default Insurance "
            "(SDI) policy ($325,000.00 base premium) plus 0.5 expected default claims at a $250,000.00 "
            "retention ($125,000.00 expected retention cost) = $225,000.00 net annual underwriting savings."
        ),
    }
    queue_file.write_text(json.dumps(candidate) + "\n", encoding="utf-8")

    p2_res = execute_autonomous_daily_trend_page_build(
        property_ids=["lienbond"],
        void_candidates_path=queue_file,
        ledger_path=ledger_file,
        max_pages_per_tenant_per_day=1,
        date_key="2026-11-09",
        registry=reg,
        dry_run=False,
        enable_gitops=False,
    )
    assert p2_res["status"] == "PASS"
    assert p2_res["built_count"] == 1
    dv_path = lb_root / "content" / "deployed_voids.json"
    assert dv_path.is_file()
    dv_list = json.loads(dv_path.read_text(encoding="utf-8"))
    assert len(dv_list) == 1
    assert dv_list[0]["source"] == "p2_autonomous_daily_builder"
    assert dv_list[0]["slug"] == "subcontractor-default-insurance-sdi-vs-performance-bond-cost-calculator"

    rebuild_res = compile_lienbond_estate(lb_root)
    assert rebuild_res["status"] == "PASS"
    assert rebuild_res["compiled_count"] == 11
    rebuilt_slugs = [p["slug"] for p in rebuild_res["compiled_pages"]]
    assert "subcontractor-default-insurance-sdi-vs-performance-bond-cost-calculator" in rebuilt_slugs
    assert (
        lb_root
        / "dist"
        / "tools"
        / "subcontractor-default-insurance-sdi-vs-performance-bond-cost-calculator"
        / "index.html"
    ).is_file()

    from pseofactory.indexer import PushIndexer
    from pseofactory.maintenance import RetroReflectionEngine
    from pseofactory.verifier import audit_estate_technical_seo_and_cannibalization

    assert (
        "subcontractor-default-insurance-sdi-vs-performance-bond-cost-calculator"
        in RetroReflectionEngine.LIENBOND_FALLBACK_MANIFESTS
    )
    seo_rep = audit_estate_technical_seo_and_cannibalization(
        dist_dir=lb_root / "dist",
        property_id="lienbond",
    )
    assert seo_rep["passed"] is True, f"SEO issues on LienBond: {seo_rep['issues']}"

    indexer = PushIndexer(
        domain="lienbond.com",
        canonical_base="https://lienbond.com",
        base_dir=lb_root,
        dist_dir=lb_root / "dist",
        tenant_id="lienbond",
    )
    assert indexer.domain == "lienbond.com"
    assert indexer.tenant_id == "lienbond"
    airlock = indexer.preflight_airlock(
        urls=["https://lienbond.com/tools/subcontractor-default-insurance-sdi-vs-performance-bond-cost-calculator/"],
        dist_dir=lb_root / "dist",
    )
    assert len(airlock.valid_urls) == 1
    assert len(airlock.quarantined_urls) == 0


def test_compiled_calculator_submit_flushes_query_params_synchronously() -> None:
    """
    Verifies the compiled form submit handler clears pending debounce timers and invokes
    window.history.replaceState synchronously with current DOM inputs (zero 150ms race).
    """
    import json
    import re
    import subprocess

    res = compile_high_effort_page(
        {
            "slug": "contractor-license-bond-cost-calculator-by-credit-score",
            "query": "contractor license bond cost calculator by credit score",
            "title": "Contractor License Bond Cost Calculator",
            "property_id": "lienbond",
            "canonical_base": "https://lienbond.com",
            "statutory_authority": "U.S. Treasury Department Circular 570 and 40 U.S.C. Section 3131",
            "economic_dataset": "BLS Producer Price Index for Construction & SFAA Loss Ratio Series",
            "model_name": "Contractor License Bond Credit Tier Underwriting Model",
            "formula": "round((bond_amount * credit_tier_rate_pct / 100.0) * term_years, 2)",
            "inputs": {"bond_amount": 25000, "credit_tier_rate_pct": 1.5, "term_years": 1},
            "published_output": 375.0,
            "sample_calculation": "Evaluating a $25,000 bond at 1.5% for 1 year yields $375.00 premium",
        }
    )
    html = res["html"]
    scripts = re.findall(r"<script(?:\s+[^>]*)?>(.*?)</script>", html, flags=re.DOTALL | re.IGNORECASE)
    calc_scripts = [s for s in scripts if "updateQueryParams" in s and "handleRecompute" in s]
    assert calc_scripts, "Expected compiled inline calculator script with updateQueryParams"
    calc_js = calc_scripts[-1]

    node_harness = (
        "const vm = require('vm');\n"
        "const listeners = {};\n"
        "const replaceCalls = [];\n"
        "const bondInput = { id: 'input-bond_amount', name: 'bond_amount', type: 'number', value: '25000' };\n"
        "const rateInput = { id: 'input-credit_tier_rate_pct', name: 'credit_tier_rate_pct', type: 'number', value: '1.5' };\n"
        "const termInput = { id: 'input-term_years', name: 'term_years', type: 'number', value: '1' };\n"
        "const form = {\n"
        "  querySelectorAll: () => [bondInput, rateInput, termInput],\n"
        "  addEventListener: (ev, fn) => { (listeners[ev] = listeners[ev] || []).push(fn); },\n"
        "};\n"
        "const outputElem = { textContent: '' };\n"
        "let scheduled = [];\n"
        "const sandbox = {\n"
        "  URL, URLSearchParams,\n"
        "  setTimeout: (fn, ms) => { const id = scheduled.length + 1; scheduled.push({ id, fn, ms, cleared: false }); return id; },\n"
        "  clearTimeout: (id) => { const item = scheduled.find((x) => x.id === id); if (item) item.cleared = true; },\n"
        "  window: {\n"
        "    location: { href: 'https://lienbond.com/tools/contractor-license-bond-cost-calculator-by-credit-score/', search: '' },\n"
        "    history: { replaceState: (_s, _t, u) => { replaceCalls.push(u); sandbox.window.location.href = u; sandbox.window.location.search = new URL(u).search; } },\n"
        "    addEventListener: () => {},\n"
        "  },\n"
        "  document: {\n"
        "    readyState: 'complete',\n"
        "    getElementById: (id) => (id.endsWith('-calculator') ? form : null),\n"
        "    querySelector: (sel) => (sel === '.output-value' ? outputElem : null),\n"
        "    addEventListener: () => {},\n"
        "  },\n"
        "};\n"
        f"vm.runInNewContext({json.dumps(calc_js)}, sandbox);\n"
        "bondInput.value = '99000';\n"
        "for (const fn of (listeners.input || [])) fn({ target: bondInput });\n"
        "const preSubmitSyncCalls = replaceCalls.length;\n"
        "for (const fn of (listeners.submit || [])) fn({ preventDefault: () => {} });\n"
        "const postSubmitCalls = replaceCalls.slice();\n"
        "const allCleared = scheduled.every((s) => s.cleared);\n"
        "console.log(JSON.stringify({ preSubmitSyncCalls, postSubmitCalls, allCleared, output: outputElem.textContent }));\n"
    )
    proc = subprocess.run(["node", "-e", node_harness], capture_output=True, text=True, check=True, timeout=15)
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    assert out["preSubmitSyncCalls"] == 0
    assert out["allCleared"] is True
    assert len(out["postSubmitCalls"]) == 1
    assert "bond_amount=99000" in out["postSubmitCalls"][0]


@pytest.mark.xdist_group("cdp_9222")
def test_lienbond_readable_formulas_and_compiled_estate_zero_spaced_hyphens(tmp_path: Path) -> None:
    """
    Verifies _format_human_readable_formula emits zero spaced hyphens (\\s+-\\s+) across all
    LIENBOND_EXPANSION_SPECS and fallback paths, and compiled LienBond HTML passes UnifiedBrowserAuditor dashes=0.
    """
    spaced_hyphen_re = re.compile(r"\s+-\s+")

    for spec in LIENBOND_EXPANSION_SPECS:
        readable = _format_human_readable_formula(spec["formula"])
        assert not spaced_hyphen_re.search(readable), f"{spec['slug']}: spaced hyphen in {readable!r}"
        assert_no_forbidden_dashes(readable, context=f"readable formula {spec['slug']}")

    # Explicit subtraction and SyntaxError fallback checks
    sub_readable = _format_human_readable_formula("round(contract_price - 100000.0, 2)")
    assert sub_readable == "Contract Price minus 100,000"
    assert not spaced_hyphen_re.search(sub_readable)

    fallback_readable = _format_human_readable_formula("round((contract_price - 100000.0), 2")
    assert not spaced_hyphen_re.search(fallback_readable), f"Fallback emitted spaced hyphen: {fallback_readable!r}"
    assert "minus" in fallback_readable

    estate_res = compile_lienbond_estate(tmp_path)
    assert estate_res["status"] == "PASS"
    dist_dir = tmp_path / "dist"

    for hp in sorted(dist_dir.rglob("*.html")):
        txt = hp.read_text(encoding="utf-8", errors="ignore")
        assert_no_forbidden_dashes(txt, context=hp.relative_to(dist_dir).as_posix())
        title_m = re.search(r"<title[^>]*>([\s\S]*?)</title>", txt, flags=re.IGNORECASE)
        if title_m:
            assert not spaced_hyphen_re.search(title_m.group(1)), f"{hp}: title spaced hyphen {title_m.group(1)!r}"
        body_m = re.search(r"<body[^>]*>([\s\S]*)</body>", txt, flags=re.IGNORECASE)
        if body_m:
            vis = re.sub(
                r"<(script|style|code|pre|noscript)\b[^>]*>[\s\S]*?</\1>",
                "",
                body_m.group(1),
                flags=re.IGNORECASE,
            )
            vis_text = re.sub(r"<[^>]+>", "\n", vis)
            for line in vis_text.splitlines():
                assert not spaced_hyphen_re.search(line), (
                    f"{hp.relative_to(dist_dir)}: spaced hyphen in visible body: {line.strip()[:100]!r}"
                )

    auditor = UnifiedBrowserAuditor(dist_dir=dist_dir, property_id="lienbond", fail_closed=True)
    cdp_ok, _ = auditor.check_cdp_reachability()
    if cdp_ok:
        report = auditor.run_audit(sample_size=None)
        dash_findings = [
            {"route": f.get("route"), "dashes": f.get("dashes")}
            for f in report.get("findings", [])
            if f.get("dashes")
        ]
        assert dash_findings == [], f"LienBond browser dash violations: {dash_findings}"
        assert report.get("failed_count") == 0, (
            f"LienBond browser audit failed_count={report.get('failed_count')}: "
            f"{[f for f in report.get('findings', []) if f.get('dashes') or f.get('hierarchy_violations')]}"
        )


def test_reflect_recompiles_lienbond_when_substrate_compiler_syncs(tmp_path: Path, monkeypatch) -> None:
    """
    Verifies reflect_and_recompile_all_assets invokes LienBond build_all() both when
    lienbond/_pseo_substrate/pseofactory/compiler.py changes (force=False) and when force=True.
    """
    import pseofactory.maintenance as maint_mod
    from pseofactory.maintenance import (
        AssetIntegrityReport,
        RetroReflectionEngine,
        SubprocessPropertyAdapter,
        TenantRegistry,
        reflect_and_recompile_all_assets,
    )
    from pseofactory.porcelain_shell import compile_tenant_porcelain_estate, sync_tenant_porcelain_shell

    lb_root = tmp_path / "lienbond"
    pkg_dir = lb_root / "lienbond"
    dist_dir = lb_root / "dist"
    (dist_dir / "tools").mkdir(parents=True, exist_ok=True)
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "builder.py").write_text("def build_all():\n    return True\n", encoding="utf-8")
    (dist_dir / "index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><title>LienBond Hub</title></head>"
        "<body><main><h1>LienBond Hub</h1><p>Surety calculators.</p></main></body></html>",
        encoding="utf-8",
    )
    (dist_dir / "tools" / "index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><title>LienBond Tools</title></head>"
        "<body><main><h1>LienBond Tools</h1><p>Directory.</p></main></body></html>",
        encoding="utf-8",
    )
    sync_tenant_porcelain_shell(lb_root, "lienbond")
    compile_tenant_porcelain_estate(dist_dir, "lienbond", repo_root=lb_root)

    # Simulate stale synced compiler.py inside LienBond's _pseo_substrate
    sub_compiler = pkg_dir / "_pseo_substrate" / "pseofactory" / "compiler.py"
    assert sub_compiler.is_file()
    sub_compiler.write_text("# stale compiler\n", encoding="utf-8")

    adapter = SubprocessPropertyAdapter(
        property_id="lienbond",
        brand_name="LienBond",
        domain="lienbond.com",
        canonical_base="https://lienbond.com",
        dist_dir=dist_dir,
        repo_path=lb_root,
    )
    reg = TenantRegistry()
    reg.register_adapter(adapter)

    build_calls: list[str] = []
    monkeypatch.setattr(adapter, "build_all", lambda: build_calls.append("build_all") or True)
    monkeypatch.setattr(
        maint_mod.AssetIntegrityEvaluator,
        "audit_all",
        lambda self, adp, **kw: AssetIntegrityReport(
            property_id="lienbond",
            status="PASS",
            total_assets_checked=2,
            compliant_assets_count=2,
            drifted_assets=[],
        ),
    )
    monkeypatch.setattr(RetroReflectionEngine, "audit_estate", lambda *a, **kw: {"status": "PASS", "stale_count": 0})
    monkeypatch.setattr(RetroReflectionEngine, "retrofit_estate", lambda *a, **kw: {"status": "PASS", "pages_retrofitted": 0, "porcelain_compiled": True})

    # 1. force=False still rebuilds LienBond when _pseo_substrate/pseofactory/compiler.py was updated
    reflect_and_recompile_all_assets(
        properties=["lienbond"],
        force=False,
        latch_state=False,
        run_downstream=False,
        registry=reg,
        workspace_root=tmp_path,
    )
    assert build_calls == ["build_all"]

    # 2. force=True rebuilds LienBond even when _pseo_substrate is already in sync
    reflect_and_recompile_all_assets(
        properties=["lienbond"],
        force=True,
        latch_state=False,
        run_downstream=False,
        registry=reg,
        workspace_root=tmp_path,
    )
    assert build_calls == ["build_all", "build_all"]


def _run_lienbond_substrate_audit_subprocess(lb_repo: Path) -> dict:
    """Runs AssetIntegrityEvaluator(enforce_master_seo=True) and detect_engine_drift from _pseo_substrate."""
    import json
    import os
    import subprocess
    import sys

    sub_root = lb_repo / "lienbond" / "_pseo_substrate"
    script = (
        "import json, sys\n"
        "from pathlib import Path\n"
        "sys.modules['bs4'] = None\n"
        "import pseofactory\n"
        "from pseofactory.drift import detect_engine_drift\n"
        "from pseofactory.maintenance import AssetIntegrityEvaluator, SubprocessPropertyAdapter\n"
        "repo = Path.cwd().resolve()\n"
        "assert '_pseo_substrate' in Path(pseofactory.__file__).resolve().parts, pseofactory.__file__\n"
        "drift_res = detect_engine_drift(repo / '.agy' / 'engine_hash.json')\n"
        "adp = SubprocessPropertyAdapter(\n"
        "    property_id='lienbond',\n"
        "    brand_name='LienBond',\n"
        "    domain='lienbond.com',\n"
        "    canonical_base='https://lienbond.com',\n"
        "    dist_dir=repo / 'dist',\n"
        "    repo_path=repo,\n"
        ")\n"
        "report = AssetIntegrityEvaluator(enforce_master_seo=True).audit_all(adp)\n"
        "reasons = []\n"
        "for rec in report.drifted_assets:\n"
        "    reasons.extend([r.value if hasattr(r, 'value') else str(r) for r in rec.reasons])\n"
        "print(json.dumps({\n"
        "    'pseofactory_file': pseofactory.__file__,\n"
        "    'drift': drift_res,\n"
        "    'status': report.status,\n"
        "    'total_assets_checked': report.total_assets_checked,\n"
        "    'drifted_assets_count': report.drifted_assets_count,\n"
        "    'reasons': sorted(set(reasons)),\n"
        "}))\n"
    )
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONPATH": f"{lb_repo}{os.pathsep}{sub_root}",
        "WORKSPACE_ROOT": ".",
    }
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(lb_repo),
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=240,
    )
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_lienbond_clean_ci_and_local_substrate_audit_drift_parity(tmp_path: Path) -> None:
    """
    Verifies _pseo_substrate audit alignment and tamper detection for both:
    (a) clean CI checkouts without .agy/ (using synced_substrate_hash vs full engine_hash), and
    (b) local checkouts with .agy/engine_hash.json alongside substrate_lock.json.
    """
    import json
    import shutil
    from pseofactory.drift import record_engine_hash, write_substrate_lock
    from pseofactory.porcelain_shell import sync_tenant_porcelain_shell

    lb_repo = tmp_path / "lienbond"
    estate_res = compile_lienbond_estate(lb_repo, run_retrofit=True)
    assert estate_res["status"] == "PASS"
    sync_tenant_porcelain_shell(lb_repo, "lienbond")
    write_substrate_lock(lb_repo, property_id="lienbond", sync_ledgers=False)

    lock_path = lb_repo / "substrate_lock.json"
    orig_lock_text = lock_path.read_text(encoding="utf-8")
    lock_data = json.loads(orig_lock_text)
    assert lock_data["engine_hash"] != lock_data["synced_substrate_hash"]

    # Case (a): Clean CI checkout without .agy/ passes enforce_master_seo=True and bs4=None
    shutil.rmtree(lb_repo / ".agy", ignore_errors=True)
    clean_res = _run_lienbond_substrate_audit_subprocess(lb_repo)
    assert "_pseo_substrate" in clean_res["pseofactory_file"]
    assert clean_res["drift"]["status"] == "ALIGNED"
    assert clean_res["drift"]["drift_detected"] is False
    assert clean_res["status"] == "PASS"
    assert clean_res["drifted_assets_count"] == 0

    # Case (a.2): Corrupting synced_substrate_hash in substrate_lock.json fails with ENGINE_HASH_DRIFT
    corrupted_lock = dict(lock_data)
    corrupted_lock["synced_substrate_hash"] = "f" * 64
    lock_path.write_text(json.dumps(corrupted_lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    corrupt_lock_res = _run_lienbond_substrate_audit_subprocess(lb_repo)
    assert corrupt_lock_res["drift"]["drift_detected"] is True
    assert corrupt_lock_res["drifted_assets_count"] > 0
    assert "ENGINE_HASH_DRIFT" in corrupt_lock_res["reasons"]
    lock_path.write_text(orig_lock_text, encoding="utf-8")

    # Case (a.3): Editing a synced _pseo_substrate module fails with ENGINE_HASH_DRIFT
    sub_contracts = lb_repo / "lienbond" / "_pseo_substrate" / "pseofactory" / "contracts.py"
    orig_contracts = sub_contracts.read_text(encoding="utf-8")
    sub_contracts.write_text(orig_contracts + "\n# tampered substrate check\n", encoding="utf-8")
    tamper_sub_res = _run_lienbond_substrate_audit_subprocess(lb_repo)
    assert tamper_sub_res["drift"]["drift_detected"] is True
    assert tamper_sub_res["drifted_assets_count"] > 0
    assert "ENGINE_HASH_DRIFT" in tamper_sub_res["reasons"]
    sub_contracts.write_text(orig_contracts, encoding="utf-8")

    # Case (b): Local checkout WITH .agy/engine_hash.json (full hash) + matching substrate_lock.json passes
    agy_eh_path = lb_repo / ".agy" / "engine_hash.json"
    record_engine_hash(agy_eh_path, hash_value=lock_data["engine_hash"])
    agy_eh_data = json.loads(agy_eh_path.read_text(encoding="utf-8"))
    assert "synced_substrate_hash" not in agy_eh_data
    assert agy_eh_data["engine_hash"] == lock_data["engine_hash"]

    local_ok_res = _run_lienbond_substrate_audit_subprocess(lb_repo)
    assert local_ok_res["drift"]["status"] == "ALIGNED"
    assert local_ok_res["drift"]["drift_detected"] is False
    assert local_ok_res["status"] == "PASS"
    assert local_ok_res["drifted_assets_count"] == 0

    # Case (b.2): Corrupting .agy/engine_hash.json fails closed with ENGINE_HASH_DRIFT
    agy_eh_path.write_text(
        json.dumps({"engine_hash": "0" * 64, "substrate_hash": "0" * 64}),
        encoding="utf-8",
    )
    local_bad_res = _run_lienbond_substrate_audit_subprocess(lb_repo)
    assert local_bad_res["drift"]["status"] == "DRIFT"
    assert local_bad_res["drift"]["drift_detected"] is True
    assert local_bad_res["drifted_assets_count"] > 0
    assert "ENGINE_HASH_DRIFT" in local_bad_res["reasons"]


def test_contracts_bs4_fallback_strict_when_bs4_unavailable(monkeypatch) -> None:
    """
    Verifies stdlib HTMLParser fallback when bs4 is unavailable preserves strict
    layout homogeneity, minimum >=3 item threshold, and semantic compression assertions.
    """
    import sys
    import pytest
    from pseofactory.contracts import (
        assert_comparison_layout_contracts,
        assert_multi_scale_semantic_compression,
    )

    monkeypatch.setitem(sys.modules, "bs4", None)

    valid_cards_html = (
        '<div class="comparison-container">'
        '  <div class="card" data-entity-type="SuretyBondModel">Plan A</div>'
        '  <div class="card" data-entity-type="SuretyBondModel">Plan B</div>'
        '  <div class="card" data-entity-type="SuretyBondModel">Plan C</div>'
        "</div>"
    )
    err_msg: str | None = None
    ok = False
    try:
        ok = assert_comparison_layout_contracts(valid_cards_html)
    except (ValueError, ImportError) as exc:
        err_msg = str(exc) or type(exc).__name__
    assert err_msg is None, err_msg
    assert ok is True

    valid_carousel_html = (
        "<carousel>"
        '  <card data-entity-type="SuretyBondModel">Item 1</card>'
        '  <card data-entity-type="SuretyBondModel">Item 2</card>'
        '  <card data-entity-type="SuretyBondModel">Item 3</card>'
        "</carousel>"
    )
    carousel_err: str | None = None
    carousel_ok = False
    try:
        carousel_ok = assert_comparison_layout_contracts(valid_carousel_html)
    except (ValueError, ImportError) as exc:
        carousel_err = str(exc) or type(exc).__name__
    assert carousel_err is None, carousel_err
    assert carousel_ok is True

    under_three_html = (
        '<div class="comparison-container">'
        '  <div class="card" data-entity-type="SuretyBondModel">Plan A</div>'
        '  <div class="card" data-entity-type="SuretyBondModel">Plan B</div>'
        "</div>"
    )
    with pytest.raises(ValueError, match="Minimum Asset Threshold violated"):
        assert_comparison_layout_contracts(under_three_html)

    under_three_direct_children = (
        '<div class="comparison-container">'
        "  <div>Direct A</div>"
        "  <div>Direct B</div>"
        "</div>"
    )
    with pytest.raises(ValueError, match="Minimum Asset Threshold violated"):
        assert_comparison_layout_contracts(under_three_direct_children)

    heterogeneous_html = (
        '<div class="comparison-container">'
        '  <div class="card" data-entity-type="SuretyBondModel">Plan A</div>'
        '  <div class="card" data-entity-type="TaxCalculationModel">Plan B</div>'
        '  <div class="card" data-entity-type="SuretyBondModel">Plan C</div>'
        "</div>"
    )
    with pytest.raises(ValueError, match="Homogeneity Law violated"):
        assert_comparison_layout_contracts(heterogeneous_html)

    valid_p_html = (
        "<p>LienBond calculates contractor surety bond rates under federal Miller Act rules. "
        "The underwriting model evaluates credit tiers deterministically. "
        "Contractors verify statutory bond limits before bidding.</p>"
        "<p>SuretyCalculator models Miller Act performance bond tiers cleanly. "
        "Each formula adheres to Treasury Circular 570 rules. "
        "SuretyCalculator confirms fixed sliding scale premiums across states.</p>"
    )
    comp_err: str | None = None
    comp_ok = False
    try:
        comp_ok = assert_multi_scale_semantic_compression(
            valid_p_html,
            entity_name="SuretyCalculator",
            brand_name="LienBond",
        )
    except (ValueError, ImportError) as exc:
        comp_err = str(exc) or type(exc).__name__
    assert comp_err is None, comp_err
    assert comp_ok is True

    unanchored_p_html = (
        "<p>This paragraph omits any reference to the required subject. "
        "It states generic surety terms without proper entity anchoring. "
        "Therefore the compression verifier must reject it.</p>"
    )
    with pytest.raises(ValueError, match="Micro entity anchoring violated"):
        assert_multi_scale_semantic_compression(
            unanchored_p_html,
            entity_name="SuretyCalculator",
            brand_name="LienBond",
        )

    wrong_sentence_count_html = (
        "<p>LienBond calculates contractor surety bond rates under federal law. "
        "Only two sentences appear here.</p>"
    )
    with pytest.raises(ValueError, match="Meso atomic structure violated"):
        assert_multi_scale_semantic_compression(
            wrong_sentence_count_html,
            entity_name="SuretyCalculator",
            brand_name="LienBond",
        )


def test_lienbond_synced_ci_workflow_installs_pytest_and_beautifulsoup4(tmp_path: Path) -> None:
    """Verifies sync_tenant_test_isolation_guards emits pytest and beautifulsoup4 in LienBond ci.yml."""
    import yaml
    from pseofactory.gitops import sync_tenant_test_isolation_guards

    lb_repo = tmp_path / "lienbond"
    (lb_repo / "lienbond").mkdir(parents=True)
    (lb_repo / ".pseofactory.json").write_text('{"property_id": "lienbond"}\n', encoding="utf-8")
    workflows_dir = lb_repo / ".github" / "workflows"
    workflows_dir.mkdir(parents=True)
    (workflows_dir / "ci.yml").write_text("name: stale\n", encoding="utf-8")

    sync_tenant_test_isolation_guards(lb_repo, property_id="lienbond")
    ci_text = (workflows_dir / "ci.yml").read_text(encoding="utf-8")
    assert "\u2014" not in ci_text
    assert "\u2013" not in ci_text

    parsed = yaml.safe_load(ci_text)
    install_runs = [
        step.get("run", "")
        for step in parsed["jobs"]["verify"]["steps"]
        if step.get("name") == "Install Test Runner"
    ]
    assert len(install_runs) == 1
    assert "pytest" in install_runs[0]
    assert "beautifulsoup4" in install_runs[0]
    assert "python3 -m lienbond.cli audit" in ci_text


def test_lienbond_git_archive_ci_audit_tracks_substrate_syndication_and_ignores_top_level(
    tmp_path: Path,
) -> None:
    """
    Verifies anchored /syndication/ and /dist/syndication/ rules in .gitignore keep
    repo-root syndication artifacts untracked while tracking
    lienbond/_pseo_substrate/pseofactory/syndication/__init__.py in HEAD so an
    isolated git archive HEAD checkout passes lienbond.cli audit cleanly.
    """
    import io
    import json
    import os
    import subprocess
    import sys
    import tarfile
    from pseofactory.drift import write_substrate_lock
    from pseofactory.gitops import GitOpsCoordinator, sync_tenant_test_isolation_guards
    from pseofactory.porcelain_shell import sync_tenant_porcelain_shell

    lb_repo = tmp_path / "lienbond"
    lb_repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main", str(lb_repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(lb_repo), "config", "user.email", "ci@lienbond.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(lb_repo), "config", "user.name", "LienBond CI"], check=True, capture_output=True)

    estate_res = compile_lienbond_estate(lb_repo, run_retrofit=True)
    assert estate_res["status"] == "PASS"
    sync_tenant_porcelain_shell(lb_repo, "lienbond")

    (lb_repo / "syndication").mkdir(parents=True, exist_ok=True)
    (lb_repo / "syndication" / "pack.json").write_text('{"pack": "ignored"}\n', encoding="utf-8")
    (lb_repo / "dist" / "syndication").mkdir(parents=True, exist_ok=True)
    (lb_repo / "dist" / "syndication" / "secret.html").write_text(
        "<!DOCTYPE html><html><body>Ignored Syndication</body></html>\n",
        encoding="utf-8",
    )

    sync_tenant_test_isolation_guards(lb_repo, property_id="lienbond")
    gi_lines = (lb_repo / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "/syndication/" in gi_lines
    assert "/dist/syndication/" in gi_lines
    assert "syndication/" not in gi_lines
    assert "dist/syndication/" not in gi_lines

    write_substrate_lock(lb_repo, property_id="lienbond", sync_ledgers=True)
    coord = GitOpsCoordinator(lb_repo, branch="main")
    coord.stage_tracked()
    subprocess.run(
        ["git", "-C", str(lb_repo), "commit", "-m", "chore(lienbond): stage compiled estate and substrate"],
        check=True,
        capture_output=True,
    )

    head_files = set(
        subprocess.check_output(
            ["git", "-C", str(lb_repo), "ls-tree", "-r", "--name-only", "HEAD"],
            text=True,
        ).splitlines()
    )
    tracked_files = set(
        subprocess.check_output(
            ["git", "-C", str(lb_repo), "ls-files"],
            text=True,
        ).splitlines()
    )
    assert "syndication/pack.json" not in head_files
    assert "syndication/pack.json" not in tracked_files
    assert "dist/syndication/secret.html" not in head_files
    assert "dist/syndication/secret.html" not in tracked_files
    assert "lienbond/_pseo_substrate/pseofactory/syndication/__init__.py" in head_files

    archive_proc = subprocess.run(
        ["git", "-C", str(lb_repo), "archive", "--format=tar", "HEAD"],
        check=True,
        capture_output=True,
    )
    ci_checkout = tmp_path / "ci_checkout"
    ci_checkout.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(archive_proc.stdout), mode="r:*") as tf:
        if sys.version_info >= (3, 12):
            tf.extractall(ci_checkout, filter="data")
        else:
            tf.extractall(ci_checkout)

    assert not (ci_checkout / ".git").exists()
    assert not (ci_checkout / ".agy").exists()
    assert not (ci_checkout / "syndication" / "pack.json").exists()
    assert not (ci_checkout / "dist" / "syndication" / "secret.html").exists()
    assert (ci_checkout / "lienbond" / "_pseo_substrate" / "pseofactory" / "syndication" / "__init__.py").is_file()

    clean_env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "WORKSPACE_ROOT": ".",
        "PYTHONPATH": f".{os.pathsep}lienbond/_pseo_substrate",
    }
    cli_proc = subprocess.run(
        [sys.executable, "-m", "lienbond.cli", "audit"],
        cwd=str(ci_checkout),
        env=clean_env,
        capture_output=True,
        text=True,
        timeout=240,
    )
    assert cli_proc.returncode == 0, (
        f"Expected rc == 0 for lienbond.cli audit, got {cli_proc.returncode}; "
        f"stdout={cli_proc.stdout!r} stderr={cli_proc.stderr!r}"
    )
    audit_payload = json.loads(cli_proc.stdout)
    assert audit_payload["status"] == "PASS"
    assert audit_payload["drifted_assets_count"] == 0
    assert audit_payload["total_assets_checked"] > 0

    bs4_probe = (
        "import contextlib, io, json, sys\n"
        "from pathlib import Path\n"
        "sys.modules['bs4'] = None\n"
        "import pseofactory\n"
        "import pseofactory.syndication\n"
        "from pseofactory.drift import detect_engine_drift\n"
        "import lienbond.cli as lb_cli\n"
        "assert '_pseo_substrate' in Path(pseofactory.__file__).resolve().parts, pseofactory.__file__\n"
        "assert '_pseo_substrate' in Path(pseofactory.syndication.__file__).resolve().parts, pseofactory.syndication.__file__\n"
        "drift_res = detect_engine_drift(Path('.agy/engine_hash.json'))\n"
        "buf = io.StringIO()\n"
        "with contextlib.redirect_stdout(buf):\n"
        "    rc = lb_cli.main(['audit'])\n"
        "print(json.dumps({'rc': rc, 'drift': drift_res, 'audit': json.loads(buf.getvalue())}))\n"
    )
    bs4_proc = subprocess.run(
        [sys.executable, "-c", bs4_probe],
        cwd=str(ci_checkout),
        env=clean_env,
        capture_output=True,
        text=True,
        timeout=240,
    )
    assert bs4_proc.returncode == 0, f"bs4=None probe failed: stderr={bs4_proc.stderr!r}"
    bs4_res = json.loads(bs4_proc.stdout.strip().splitlines()[-1])
    assert bs4_res["rc"] == 0
    assert bs4_res["drift"]["status"] == "ALIGNED"
    assert bs4_res["drift"]["drift_detected"] is False
    assert bs4_res["audit"]["status"] == "PASS"
    assert bs4_res["audit"]["drifted_assets_count"] == 0


def test_lienbond_upgrades_legacy_gitignore_and_recompute_stages_substrate_syndication(
    tmp_path: Path,
) -> None:
    """
    Verifies sync_tenant_test_isolation_guards upgrades legacy bare syndication/ and
    dist/syndication/ entries to anchored /syndication/ and /dist/syndication/, and
    recompute_and_amend_tenant_lock_and_ledger stages _pseo_substrate/pseofactory/**/*.py
    without staging ignored top-level syndication files.
    """
    import subprocess
    from pseofactory.gitops import (
        recompute_and_amend_tenant_lock_and_ledger,
        sync_tenant_test_isolation_guards,
    )
    from pseofactory.porcelain_shell import sync_tenant_porcelain_shell

    lb_repo = tmp_path / "lienbond_legacy"
    lb_repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main", str(lb_repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(lb_repo), "config", "user.email", "ci@lienbond.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(lb_repo), "config", "user.name", "LienBond CI"], check=True, capture_output=True)

    estate_res = compile_lienbond_estate(lb_repo, run_retrofit=False)
    assert estate_res["status"] == "PASS"
    sync_tenant_porcelain_shell(lb_repo, "lienbond")

    (lb_repo / ".gitignore").write_text(
        "__pycache__/\n*.py[cod]\n.agy/\ndist/\nsyndication/\ndist/syndication/\n",
        encoding="utf-8",
    )
    (lb_repo / "syndication").mkdir(parents=True, exist_ok=True)
    (lb_repo / "syndication" / "pack.json").write_text('{"pack": "ignored"}\n', encoding="utf-8")
    (lb_repo / "dist" / "syndication").mkdir(parents=True, exist_ok=True)
    (lb_repo / "dist" / "syndication" / "secret.html").write_text("<html>ignored</html>\n", encoding="utf-8")

    subprocess.run(["git", "-C", str(lb_repo), "add", ".gitignore", ".pseofactory.json", "substrate_lock.json"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(lb_repo), "commit", "-m", "init legacy lienbond"], check=True, capture_output=True)

    sync_tenant_test_isolation_guards(lb_repo, property_id="lienbond")
    gi_lines = (lb_repo / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert gi_lines.count("/syndication/") == 1
    assert gi_lines.count("/dist/syndication/") == 1
    assert "syndication/" not in gi_lines
    assert "dist/syndication/" not in gi_lines
    assert "dist/" not in gi_lines

    ok = recompute_and_amend_tenant_lock_and_ledger(lb_repo, property_id="lienbond", amend=False)
    assert ok is True

    staged_files = set(
        subprocess.check_output(
            ["git", "-C", str(lb_repo), "diff", "--cached", "--name-only"],
            text=True,
        ).splitlines()
    )
    assert "lienbond/_pseo_substrate/pseofactory/syndication/__init__.py" in staged_files
    assert "lienbond/_pseo_substrate/pseofactory/compiler.py" in staged_files
    assert "syndication/pack.json" not in staged_files
    assert "dist/syndication/secret.html" not in staged_files

