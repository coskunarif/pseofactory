"""
End-to-end regression suite for the Cluster 1 monetization overhaul covering:
1. Canonical promotion of lienbond in tenant_facts.py
2. Atomic vault synchronization & ground-truth reconciliation in monetization_vault.json & affiliates_hub.py
3. Brand-honest intent validation, per-property registry isolation, & fail-closed merchant audits
4. Cloudflare Pages Functions (/r/[partner].js, /api/telemetry.js, /api/lead-capture.js), KV namespace isolation,
   fail-closed TELEMETRY_EXPORT_SECRET auth, anti-bounce suppression, compiler SKU parity, and publisher meta hygiene
5. Zero em-dash (U+2014) and zero en-dash (U+2013) typography enforcement across all owned files
"""

from __future__ import annotations

import copy
import dataclasses
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

from pseofactory import (
    affiliate_intent,
    affiliates,
    affiliates_hub,
    compiler,
    edge,
    lead_classification,
    maintenance,
    tenant_facts,
    visual_primitives,
)


REPO_ROOT = Path(__file__).resolve().parent.parent

OWNED_FILES = [
    "pseofactory/tenant_facts.py",
    "pseofactory/monetization_vault.json",
    "pseofactory/affiliates_hub.py",
    "pseofactory/affiliate_intent.py",
    "pseofactory/affiliates.py",
    "pseofactory/edge.py",
    "pseofactory/compiler.py",
    "pseofactory/maintenance.py",
    "pseofactory/lead_classification.py",
    "pseofactory/visual_primitives.py",
    "pseofactory_tests/test_monetization_overhaul_edge_and_vault.py",
]

EXPECTED_KV_IDS = {
    "profithelm": {
        "PROFITHELM_LEADS": "983a21b6fcd54fbb884740017b7d96f1",
        "PROFITHELM_TELEMETRY_KV": "8c56efedd6214424b83e0e298c33ba27",
    },
    "prexvo": {
        "PREXVO_LEADS": "320285659c4c494187fbf4665290ba93",
        "PREXVO_TELEMETRY_KV": "153917b16871453a9f07bfb39ff3fd98",
    },
    "gainhelm": {
        "GAINHELM_LEADS": "31cdc2315c1e4c808a3c2f0b917cafbd",
        "GAINHELM_TELEMETRY_KV": "d7e2021ef7cf47eea4ae382742481e75",
    },
    "lienbond": {
        "LIENBOND_LEADS": "c6885b9faff44e3abbb91cadebf137a9",
        "LIENBOND_TELEMETRY_KV": "802b129f39344707898e156494aff45d",
    },
}

EXPECTED_LIVE_PROFITHELM_PARTNERS = {
    "coinledger",
    "koinly",
    "mercury",
    "rippling",
    "gusto",
    "ramp",
    "xendoo",
    "kalshi",
    "efile_com",
    "eztaxreturn_com",
    "freetaxusa",
    "wallethub",
    "lawdepot",
}


def _run_node_esm(harness_js: str) -> Dict[str, Any]:
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", harness_js],
        capture_output=True,
        text=True,
        check=True,
    )
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    return json.loads(lines[-1])


# ---------------------------------------------------------------------------
# 1. Canonical Tenant Registry Promotion (tenant_facts.py)
# ---------------------------------------------------------------------------


def test_lienbond_promoted_to_first_class_canonical_tenant() -> None:
    assert tenant_facts.CANONICAL_TENANT_IDS == ["profithelm", "prexvo", "gainhelm", "lienbond"]
    assert tenant_facts.CANONICAL_TENANT_DOMAINS == [
        "profithelm.com",
        "prexvo.com",
        "gainhelm.com",
        "lienbond.com",
    ]
    assert "lienbond" in tenant_facts.CANONICAL_TENANT_DECLARATIONS
    assert len(tenant_facts.TENANT_STATUTORY_INTENT_TOKENS.get("lienbond", ())) >= 20

    lb_repr = repr(tenant_facts.LIENBOND_TENANT_CONTRACT)
    assert "editorial@lienbond.com" not in lb_repr
    assert tenant_facts.LIENBOND_TENANT_CONTRACT.domain == "lienbond.com"


# ---------------------------------------------------------------------------
# 2. Vault Ground Truth & Split-Brain Elimination (monetization_vault.json & affiliates_hub.py)
# ---------------------------------------------------------------------------


def test_monetization_vault_ground_truth_across_all_four_tenants() -> None:
    vault_path = REPO_ROOT / "pseofactory" / "monetization_vault.json"
    vault = json.loads(vault_path.read_text(encoding="utf-8"))

    # Stripe ground truth + all 7 LienBond SKUs
    stripe_cfg = vault["master_networks"]["stripe"]
    assert stripe_cfg["account_id"] == "acct_1T6fSTIq0ckFsf5j"
    assert stripe_cfg["display_name"] == "ProfitHelm LLC"
    assert stripe_cfg.get("cli_key_expires_at") is None

    skus = stripe_cfg["digital_products"]
    expected_lb_skus = {
        "lb_instant_lien_bond_worksheet_19": 1900,
        "lb_surety_bond_underwriting_kit": 4900,
        "lb_workers_comp_emr_audit_kit": 4900,
        "lb_workers_comp_emr_audit_packet": 4900,
        "lb_wh347_certified_payroll_packet": 5900,
        "lb_mechanics_lien_waiver_packet": 6900,
        "lb_surety_lien_wh347_packet": 7900,
    }
    for sku_id, cents in expected_lb_skus.items():
        assert sku_id in skus, f"Missing LienBond SKU {sku_id}"
        price_cents = skus[sku_id].get("price_cents") or int(round(float(skus[sku_id]["price_usd"]) * 100))
        assert price_cents == cents

    # ProfitHelm ground truth
    ph = vault["properties"]["profithelm"]
    assert set(ph["roster_tiers"]["live_revenue_ready"]) == EXPECTED_LIVE_PROFITHELM_PARTNERS
    assert "ramp" not in ph["roster_tiers"].get("awaiting_vendor_response", [])
    assert ph["partners"]["ramp"]["status"] == "live"
    assert ph["partners"]["ramp"]["url"] == "https://join.ramp.com/c/7932737/3981015/51436"

    assert ph["partners"]["xendoo"]["status"] == "live"
    assert ph["partners"]["xendoo"]["url"] == "https://xendoo.pxf.io/c/7932737/1357375/16354"
    assert ph["partners"]["xendoo"]["portal_key"] == "impact"
    assert "500" in str(ph["partners"]["xendoo"].get("commission_est") or ph["partners"]["xendoo"].get("bounty") or "")

    assert ph["agentic_api_programs"]["partnerstack_api_v2"]["active_partners"] == ["rippling"]
    assert ph["agentic_api_programs"]["dub_partners_api"]["is_authenticated_and_syncing"] is False
    assert ph["partners"]["mercury"]["url"] == "https://mercury.com/r/profithelm-llc"
    assert ph["partners"]["koinly"]["commission_est"] == "20% one-time first purchase"

    for pending_key in ("ipx1031", "suretybonds_direct", "crest_capital"):
        assert ph["partners"][pending_key]["status"] == "pending"
    for declined_key in ("next_insurance_b2b", "invoice_simple"):
        assert ph["partners"][declined_key]["status"] == "declined"

    # Prexvo ground truth
    px = vault["properties"]["prexvo"]
    assert px["roster_tiers"]["live_revenue_ready"] == []
    assert px["partners"]["sofi"]["status"] == "declined"
    assert px["partners"]["earnest"]["status"] == "declined"
    for pk in ("splash_financial", "credible", "lendkey"):
        assert px["partners"][pk]["status"] == "pending"

    # GainHelm ground truth
    gh = vault["properties"]["gainhelm"]
    assert gh["roster_tiers"]["live_revenue_ready"] == []
    for pk in (
        "vanta_security",
        "drata_compliance",
        "sprinto_compliance",
        "thoropass_audit",
        "coalition_cyber_insurance",
        "cobalt_pentest",
    ):
        assert gh["partners"][pk]["status"] == "pending"

    # LienBond ground truth
    lb = vault["properties"]["lienbond"]
    assert lb["roster_tiers"]["live_revenue_ready"] == []
    assert lb["partners"]["next_insurance_b2b"]["status"] == "declined"
    for pk in (
        "suretybonds_direct",
        "simply_business",
        "thimble_contractor",
        "jobber_field_service",
        "levelset_lien_filing",
    ):
        assert lb["partners"][pk]["status"] == "pending"


def test_affiliates_hub_authoritative_urls_and_atomic_split_brain_sync(tmp_path: Path) -> None:
    urls = affiliates_hub.AUTHORITATIVE_EDGE_REDIRECT_URLS
    assert set(urls.keys()) == EXPECTED_LIVE_PROFITHELM_PARTNERS
    for pk, u in urls.items():
        assert "101725461" not in u, f"Dead CJ PID in {pk}"
    for cj_pk in ("efile_com", "eztaxreturn_com", "freetaxusa", "wallethub", "lawdepot"):
        assert "101906407" in urls[cj_pk]

    # Copy vault into tmp_path and verify atomic sync + timestamp precedence
    vault_src = REPO_ROOT / "pseofactory" / "monetization_vault.json"
    vault_copy = tmp_path / "monetization_vault.json"
    vault_copy.write_text(vault_src.read_text(encoding="utf-8"), encoding="utf-8")

    hub = affiliates_hub.MonetizationHub(vault_path=vault_copy)

    # 1. Newer categories update must NEVER be overwritten by stale partners entry in _rebuild_partner_vault_index
    px_prop = hub.vault_data["properties"]["prexvo"]
    cat_key = "STUDENT_LOAN_REFINANCE"
    px_prop["categories"][cat_key]["primary_partner"] = "splash_financial"
    px_prop["categories"][cat_key]["status"] = "live"
    px_prop["categories"][cat_key]["direct_url"] = "https://splashfinancial.pxf.io/c/999/111/222"
    px_prop["categories"][cat_key]["updated_at"] = "2099-01-02T00:00:00Z"
    px_prop["partners"]["splash_financial"]["status"] = "pending"
    px_prop["partners"]["splash_financial"]["updated_at"] = "2026-01-01T00:00:00Z"

    hub._rebuild_partner_vault_index()
    assert px_prop["partners"]["splash_financial"]["status"] == "live"
    assert px_prop["partners"]["splash_financial"]["url"] == "https://splashfinancial.pxf.io/c/999/111/222"
    assert "splash_financial" in px_prop["roster_tiers"]["live_revenue_ready"]

    # 2. sync_partner_program with status="declined" atomically updates categories, partners, AND roster_tiers
    hub.sync_partner_program(
        property_id="prexvo",
        partner_key="splash_financial",
        status="declined",
        url="https://www.splashfinancial.com/",
        category=cat_key,
        save=True,
    )
    reloaded = json.loads(vault_copy.read_text(encoding="utf-8"))["properties"]["prexvo"]
    assert reloaded["categories"][cat_key]["status"] == "declined"
    assert reloaded["partners"]["splash_financial"]["status"] == "declined"
    assert "splash_financial" not in reloaded["roster_tiers"]["live_revenue_ready"]
    assert "splash_financial" in reloaded["roster_tiers"]["declined"]

    # 3. sync_from_network_payload ingests declined/rejected records instead of dropping them
    res = hub.sync_from_network_payload(
        "impact",
        [
            {
                "program_key": "credible",
                "category": "STUDENT_LOAN_COMPARISON",
                "status": "declined",
                "direct_url": "https://www.credible.com/",
            }
        ],
        property_id="prexvo",
        save=False,
    )
    assert res["updated"] >= 1
    assert hub.vault_data["properties"]["prexvo"]["partners"]["credible"]["status"] == "declined"


# ---------------------------------------------------------------------------
# 3. Brand-Honest Intent, Per-Property Registry Isolation, & Fail-Closed Audit
# ---------------------------------------------------------------------------


def test_affiliate_intent_rejects_bait_and_switches_and_accepts_honest_contracts() -> None:
    # Every cross-vertical & competitor bait-and-switch MUST return False
    forbidden_pairs = [
        ("suretybonds_direct", "https://www.dpbolvw.net/click-101906407-13784628"),
        ("simply_business", "https://www.dpbolvw.net/click-101906407-13784628"),
        ("hiscox", "https://www.dpbolvw.net/click-101906407-13784628"),
        ("next_insurance_b2b", "https://www.dpbolvw.net/click-101906407-13784628"),
        ("crest_capital", "https://xendoo.pxf.io/c/7932737/1357375/16354"),
        ("stripe", "https://join.ramp.com/c/7932737/3981015/51436"),
        ("interactive_brokers", "https://kalshi.pxf.io/c/7932737/3078072/37770"),
        ("zacks", "https://kalshi.pxf.io/c/7932737/3078072/37770"),
        ("moby", "https://kalshi.pxf.io/c/7932737/3078072/37770"),
        ("turbotax", "https://www.anrdoezrs.net/links/101906407/type/dlg/https://www.efile.com/"),
        ("taxslayer", "https://www.jdoqocy.com/links/101906407/type/dlg/https://www.eztaxreturn.com/"),
        # Dead CJ PID 101725461 must also be rejected even on matching brand
        ("lawdepot", "https://www.anrdoezrs.net/links/101725461/type/dlg/https://www.lawdepot.com/"),
    ]
    for partner_key, bad_url in forbidden_pairs:
        assert affiliate_intent.is_intent_matched(partner_key, bad_url) is False, (
            f"Expected bait-and-switch ({partner_key} -> {bad_url}) to be rejected"
        )

    # All 13 live ProfitHelm URLs must pass brand-honest matching
    for partner_key, live_url in affiliates_hub.AUTHORITATIVE_EDGE_REDIRECT_URLS.items():
        assert affiliate_intent.is_intent_matched(partner_key, live_url) is True, (
            f"Expected honest live contract ({partner_key} -> {live_url}) to match"
        )


def test_per_property_affiliate_registries_and_fail_closed_merchant_audit(tmp_path: Path) -> None:
    ph_reg = affiliates.AFFILIATE_REGISTRY_BY_PROPERTY["profithelm"]
    lb_reg = affiliates.AFFILIATE_REGISTRY_BY_PROPERTY["lienbond"]
    px_reg = affiliates.AFFILIATE_REGISTRY_BY_PROPERTY["prexvo"]
    gh_reg = affiliates.AFFILIATE_REGISTRY_BY_PROPERTY["gainhelm"]

    # Shared keys do not overwrite across ProfitHelm and LienBond
    assert ph_reg is not lb_reg
    assert lb_reg["suretybonds_direct"].status == "pending"
    assert lb_reg["suretybonds_direct"].default_url == "https://www.suretybondsdirect.com/"
    assert "lawdepot" not in lb_reg["suretybonds_direct"].default_url.lower()
    assert lb_reg["simply_business"].status == "pending"
    assert lb_reg["simply_business"].default_url == "https://www.simplybusiness.com/"
    assert lb_reg["next_insurance_b2b"].status == "declined"
    assert lb_reg["next_insurance_b2b"].default_url == "https://www.nextinsurance.com/"

    # All 13 approved ProfitHelm partners are live and brand-honest
    for pk in EXPECTED_LIVE_PROFITHELM_PARTNERS:
        assert pk in ph_reg, f"Missing live ProfitHelm partner {pk}"
        assert ph_reg[pk].status == "live"
        assert affiliate_intent.is_intent_matched(pk, ph_reg[pk].default_url) is True

    for pending_pk in ("ipx1031", "crest_capital", "suretybonds_direct"):
        if pending_pk in ph_reg:
            assert ph_reg[pending_pk].status == "pending"

    # Prexvo declined & fixed vendor URLs (in canonical catalog)
    assert px_reg["sofi"].status == "declined"
    assert px_reg["earnest"].status == "declined"
    px_catalog = edge.build_canonical_partner_catalog("prexvo")
    assert px_catalog["edvestin"]["defaultUrl"] == "https://edvestinu.com/refinance/"
    assert px_catalog["juno"]["defaultUrl"] == "https://joinjuno.com/"
    assert px_catalog["laurel_road"]["defaultUrl"] == "https://www.laurelroad.com/student-loan-refinancing/"

    for partner in gh_reg.values():
        assert partner.status != "live"

    # Honest registries pass audit_merchant_coverage_and_yield across all 4 properties
    # AND honestly report non_paying_passthrough_count instead of hardcoding 0!
    for prop in ("profithelm", "prexvo", "gainhelm", "lienbond"):
        audit = affiliates.audit_merchant_coverage_and_yield(property_id=prop)
        assert audit["status"] == "PASS", f"{prop} failed merchant audit: {audit}"
        assert audit["violations"] == []
        assert audit["non_paying_passthrough_count"] >= 1
    ph_audit = affiliates.audit_merchant_coverage_and_yield(property_id="profithelm")
    assert ph_audit["verified_paying_count"] == 13

    # Fail closed if a partner falsely claims status="live" with an uncontracted passthrough URL
    poisoned_lb = copy.deepcopy(lb_reg)
    poisoned_lb["suretybonds_direct"] = dataclasses.replace(
        poisoned_lb["suretybonds_direct"],
        status="live",
        default_url="https://www.suretybondsdirect.com/",
    )
    failed_audit = affiliates.audit_merchant_coverage_and_yield(
        property_id="lienbond",
        partner_overrides=poisoned_lb,
    )
    assert failed_audit["status"] != "PASS"
    assert len(failed_audit["violations"]) >= 1

    # Fail closed if LienBond borrows ProfitHelm's CJ PID 101906407
    borrowed_lb = copy.deepcopy(lb_reg)
    borrowed_lb["suretybonds_direct"] = dataclasses.replace(
        borrowed_lb["suretybonds_direct"],
        status="live",
        default_url="https://www.anrdoezrs.net/links/101906407/type/dlg/https://www.lawdepot.com/",
    )
    borrowed_audit = affiliates.audit_merchant_coverage_and_yield(
        property_id="lienbond",
        partner_overrides=borrowed_lb,
    )
    assert borrowed_audit["status"] != "PASS"
    assert len(borrowed_audit["violations"]) >= 1

    # _sync_prexvo_affiliate_status_compat never includes "declined" in rendered buttons
    fake_prexvo = tmp_path / "prexvo"
    (fake_prexvo / "prexvo").mkdir(parents=True)
    target_py = fake_prexvo / "prexvo" / "builder.py"
    target_py.write_text(
        'def render_partners(partners):\n'
        '    out = []\n'
        '    for p_info in partners:\n'
        '        if p_info.get("status") in ("live", "pending", "declined"):\n'
        '            out.append(p_info)\n'
        '    return out\n',
        encoding="utf-8",
    )
    changed = maintenance._sync_prexvo_affiliate_status_compat(fake_prexvo)
    assert changed is True
    synced_src = target_py.read_text(encoding="utf-8")
    assert 'if p_info.get("status") in ("live", "pending"):' in synced_src
    assert '"declined"' not in synced_src


# ---------------------------------------------------------------------------
# 4. Cloudflare Edge Workers Runtime Behavior (Executed via Node ESM)
# ---------------------------------------------------------------------------


def test_edge_redirect_workers_preserve_status_block_declined_and_isolate_tenants(tmp_path: Path) -> None:
    ph_js = tmp_path / "ph_redirect.mjs"
    px_js = tmp_path / "px_redirect.mjs"
    gh_js = tmp_path / "gh_redirect.mjs"
    lb_js = tmp_path / "lb_redirect.mjs"

    ph_code = edge.generate_edge_redirect_function(property_id="profithelm")
    px_code = edge.generate_edge_redirect_function(property_id="prexvo")
    gh_code = edge.generate_edge_redirect_function(property_id="gainhelm")
    lb_code = edge.generate_edge_redirect_function(property_id="lienbond")

    # Foreign ProfitHelm routes (ramp, lawdepot, xendoo) must NOT exist in GainHelm or LienBond workers
    for foreign_slug in ('"ramp":', '"lawdepot":', '"xendoo":'):
        assert foreign_slug not in gh_code
        assert foreign_slug not in lb_code

    ph_js.write_text(ph_code, encoding="utf-8")
    px_js.write_text(px_code, encoding="utf-8")
    gh_js.write_text(gh_code, encoding="utf-8")
    lb_js.write_text(lb_code, encoding="utf-8")

    harness = f"""
    import * as ph from {json.dumps(ph_js.as_uri())};
    import * as px from {json.dumps(px_js.as_uri())};
    import * as lb from {json.dumps(lb_js.as_uri())};

    function makeKv() {{
      const puts = [];
      return {{
        puts,
        async put(k, v) {{ puts.push([k, v]); }},
        async get() {{ return null; }},
      }};
    }}

    const leadsKv = makeKv();
    const telKv = makeKv();

    const phRamp = await ph.onRequest({{
      request: new Request("https://profithelm.com/r/ramp?tool=saas-burn"),
      params: {{ partner: "ramp" }},
      env: {{ PROFITHELM_LEADS: leadsKv, PROFITHELM_TELEMETRY_KV: telKv }},
      waitUntil: (p) => p,
    }});

    const pxSofi = await px.onRequest({{
      request: new Request("https://prexvo.com/r/sofi?tool=student-refi"),
      params: {{ partner: "sofi" }},
      env: {{ PREXVO_LEADS: leadsKv, PREXVO_TELEMETRY_KV: telKv }},
      waitUntil: (p) => p,
    }});

    const lbNext = await lb.onRequest({{
      request: new Request("https://lienbond.com/r/next-insurance?tool=workers-comp"),
      params: {{ partner: "next-insurance" }},
      env: {{ LIENBOND_LEADS: leadsKv, LIENBOND_TELEMETRY_KV: telKv }},
      waitUntil: (p) => p,
    }});

    const lbSurety = await lb.onRequest({{
      request: new Request("https://lienbond.com/r/suretybonds-direct?tool=surety-bond"),
      params: {{ partner: "suretybonds-direct" }},
      env: {{ LIENBOND_LEADS: leadsKv, LIENBOND_TELEMETRY_KV: telKv }},
      waitUntil: (p) => p,
    }});

    console.log(JSON.stringify({{
      phRampStatus: phRamp.status,
      phRampLoc: phRamp.headers.get("Location"),
      phRampTier: phRamp.headers.get("X-Edge-Contract-Tier"),
      pxSofiStatus: pxSofi.status,
      pxSofiLoc: pxSofi.headers.get("Location"),
      pxSofiTier: pxSofi.headers.get("X-Edge-Contract-Tier"),
      lbNextStatus: lbNext.status,
      lbNextLoc: lbNext.headers.get("Location"),
      lbNextTier: lbNext.headers.get("X-Edge-Contract-Tier"),
      lbSuretyLoc: lbSurety.headers.get("Location"),
      lbSuretyTier: lbSurety.headers.get("X-Edge-Contract-Tier"),
      leadsKvPuts: leadsKv.puts.length,
    }}));
    """
    out = _run_node_esm(harness)
    assert out["phRampStatus"] == 302
    assert out["phRampLoc"].startswith("https://join.ramp.com/c/7932737/3981015/51436")
    assert out["phRampTier"] in ("live", "direct_contract_upgraded")

    # Declined partners are blocked and redirected to internal calculator, NEVER vendor site
    assert out["pxSofiStatus"] == 302
    assert "sofi.com" not in out["pxSofiLoc"]
    assert out["pxSofiTier"] == "declined_partner_blocked"

    assert out["lbNextStatus"] == 302
    assert "nextinsurance.com" not in out["lbNextLoc"]
    assert out["lbNextTier"] == "declined_partner_blocked"

    # Pending LienBond partner goes to real SuretyBondsDirect (NOT LawDepot) and is never marked live/upgraded
    assert out["lbSuretyLoc"].startswith("https://www.suretybondsdirect.com/")
    assert out["lbSuretyTier"] != "direct_contract_upgraded"

    # Redirect click logging NEVER pollutes *_LEADS KV
    assert out["leadsKvPuts"] == 0


def test_edge_telemetry_worker_kv_quota_guard_and_fail_closed_auth(tmp_path: Path) -> None:
    tel_js = tmp_path / "ph_telemetry.mjs"
    tel_js.write_text(edge.generate_edge_telemetry_function(property_id="profithelm"), encoding="utf-8")

    harness = f"""
    import * as tel from {json.dumps(tel_js.as_uri())};

    function makeKv() {{
      const store = new Map();
      let putCount = 0;
      return {{
        get putCount() {{ return putCount; }},
        async put(k, v) {{ putCount += 1; store.set(k, v); }},
        async get(k) {{ return store.get(k) || null; }},
        async list({{ prefix = "", limit = 50 }} = {{}}) {{
          const keys = [...store.keys()]
            .filter((k) => k.startsWith(prefix))
            .slice(0, limit)
            .map((name) => ({{ name }}));
          return {{ keys }};
        }},
      }};
    }}

    const telKv = makeKv();
    const leadsKv = makeKv();
    const envWithSecret = {{
      PROFITHELM_TELEMETRY_KV: telKv,
      PROFITHELM_LEADS: leadsKv,
      TELEMETRY_EXPORT_SECRET: "sec_live_test_999",
    }};
    const envNoSecret = {{
      PROFITHELM_TELEMETRY_KV: telKv,
      PROFITHELM_LEADS: leadsKv,
    }};

    // 1. High-frequency UI events must NOT write to KV
    for (const evType of ["slider", "slider_drag", "calc_input", "workbench_interaction", "heartbeat"]) {{
      await tel.onRequestPost({{
        request: new Request("https://profithelm.com/api/telemetry", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ event_type: evType, tool_slug: "burn-calc" }}),
        }}),
        env: envWithSecret,
      }});
    }}
    const putsAfterHighFreq = telKv.putCount;

    // 2. Conversion events DO write to TELEMETRY_KV (and never LEADS_KV)
    await tel.onRequestPost({{
      request: new Request("https://profithelm.com/api/telemetry", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ event_type: "affiliate_click", partner_key: "ramp", tool_slug: "burn-calc" }}),
      }}),
      env: envWithSecret,
    }});
    const putsAfterConversion = telKv.putCount;

    // 3. GET without secret or with unset secret MUST fail closed (401)
    const getUnset = await tel.onRequestGet({{
      request: new Request("https://profithelm.com/api/telemetry?limit=10"),
      env: envNoSecret,
    }});
    const getUnauth = await tel.onRequestGet({{
      request: new Request("https://profithelm.com/api/telemetry?limit=10"),
      env: envWithSecret,
    }});
    const getWrong = await tel.onRequestGet({{
      request: new Request("https://profithelm.com/api/telemetry?limit=10", {{
        headers: {{ Authorization: "Bearer wrong_token" }},
      }}),
      env: envWithSecret,
    }});

    // 4. Health probe returns zero records
    const getHealth = await tel.onRequestGet({{
      request: new Request("https://profithelm.com/api/telemetry?health=1"),
      env: envWithSecret,
    }});
    const healthBody = await getHealth.json();

    const getSynth = await tel.onRequestGet({{
      request: new Request("https://profithelm.com/api/telemetry?synthetic_test=1"),
      env: envNoSecret,
    }});
    const synthBody = await getSynth.json();

    // 5. Authenticated GET succeeds
    const getAuth = await tel.onRequestGet({{
      request: new Request("https://profithelm.com/api/telemetry?limit=10", {{
        headers: {{ Authorization: "Bearer sec_live_test_999" }},
      }}),
      env: envWithSecret,
    }});
    const authBody = await getAuth.json();

    console.log(JSON.stringify({{
      putsAfterHighFreq,
      putsAfterConversion,
      leadsKvPuts: leadsKv.putCount,
      getUnsetStatus: getUnset.status,
      getUnauthStatus: getUnauth.status,
      getWrongStatus: getWrong.status,
      getHealthStatus: getHealth.status,
      healthBody,
      synthBody,
      getAuthStatus: getAuth.status,
      authCount: authBody.count,
    }}));
    """
    out = _run_node_esm(harness)
    assert out["putsAfterHighFreq"] == 0
    assert out["putsAfterConversion"] == 1
    assert out["leadsKvPuts"] == 0
    assert out["getUnsetStatus"] == 401
    assert out["getUnauthStatus"] == 401
    assert out["getWrongStatus"] == 401
    assert out["getHealthStatus"] == 200
    assert out["healthBody"] == {"ok": True, "auth_required": True}
    assert out["synthBody"] == {"ok": True, "auth_required": True}
    assert out["getAuthStatus"] == 200
    assert out["authCount"] >= 1


def test_edge_lead_capture_homepage_checkout_lienbond_skus_auth_and_anti_bounce(tmp_path: Path) -> None:
    ph_lead = tmp_path / "ph_lead.mjs"
    gh_lead = tmp_path / "gh_lead.mjs"
    lb_lead = tmp_path / "lb_lead.mjs"

    ph_lead.write_text(edge.generate_edge_lead_capture_function(property_id="profithelm"), encoding="utf-8")
    gh_lead.write_text(edge.generate_edge_lead_capture_function(property_id="gainhelm"), encoding="utf-8")
    lb_lead.write_text(edge.generate_edge_lead_capture_function(property_id="lienbond"), encoding="utf-8")

    harness = f"""
    import * as ph from {json.dumps(ph_lead.as_uri())};
    import * as gh from {json.dumps(gh_lead.as_uri())};
    import * as lb from {json.dumps(lb_lead.as_uri())};

    function makeKv() {{
      const store = new Map();
      return {{
        store,
        async put(k, v) {{ store.set(k, v); }},
        async get(k) {{ return store.get(k) || null; }},
        async list({{ prefix = "", limit = 50 }} = {{}}) {{
          const keys = [...store.keys()]
            .filter((k) => k.startsWith(prefix))
            .slice(0, limit)
            .map((name) => ({{ name }}));
          return {{ keys }};
        }},
      }};
    }}

    const stripeCalls = [];
    const zeptoCalls = [];

    globalThis.fetch = async (url, init = {{}}) => {{
      const u = String(url);
      if (u.includes("api.stripe.com/v1/checkout/sessions") && (init.method || "GET") === "POST") {{
        const params = new URLSearchParams(String(init.body || ""));
        stripeCalls.push({{
          success_url: params.get("success_url"),
          unit_amount: params.get("line_items[0][price_data][unit_amount]"),
          sku: params.get("metadata[offer_sku]") || params.get("metadata[sku]"),
          customer_email: params.get("customer_email"),
        }});
        return new Response(
          JSON.stringify({{ id: "cs_live_mock_123", url: "https://checkout.stripe.com/c/pay/cs_live_mock_123" }}),
          {{ status: 200, headers: {{ "Content-Type": "application/json" }} }}
        );
      }}
      if (u.includes("api.stripe.com/v1/checkout/sessions/cs_live_paid_home")) {{
        return new Response(
          JSON.stringify({{
            id: "cs_live_paid_home",
            livemode: true,
            status: "complete",
            payment_status: "paid",
            amount_total: 4900,
            currency: "usd",
            client_reference_id: "lead_profithelm_direct",
            customer_details: {{ email: "buyer@realcompany.io" }},
            metadata: {{
              lead_id: "lead_profithelm_direct",
              sku: "ph_cfo_excel_model_pack",
              tool_slug: "tax-bracket-capital-allocation-hub",
              property_id: "profithelm",
            }},
          }}),
          {{ status: 200, headers: {{ "Content-Type": "application/json" }} }}
        );
      }}
      if (u.includes("zeptomail.com")) {{
        const payload = JSON.parse(String(init.body || "{{}}"));
        zeptoCalls.push(payload);
        return new Response(JSON.stringify({{ message: "OK" }}), {{ status: 200 }});
      }}
      return new Response(JSON.stringify({{ ok: true }}), {{ status: 200 }});
    }};

    const phKv = makeKv();
    const ghKv = makeKv();
    const lbKv = makeKv();

    const phEnv = {{
      PROFITHELM_LEADS: phKv,
      STRIPE_SECRET_KEY: "sk_live_mock",
      ZEPTOMAIL_TOKEN: "zm_mock",
      TELEMETRY_EXPORT_SECRET: "lead_sec_777",
    }};
    const ghEnv = {{
      GAINHELM_LEADS: ghKv,
      STRIPE_SECRET_KEY: "sk_live_mock",
      ZEPTOMAIL_TOKEN: "zm_mock",
      TELEMETRY_EXPORT_SECRET: "lead_sec_777",
    }};
    const lbEnv = {{
      LIENBOND_LEADS: lbKv,
      STRIPE_SECRET_KEY: "sk_live_mock",
      ZEPTOMAIL_TOKEN: "zm_mock",
      TELEMETRY_EXPORT_SECRET: "lead_sec_777",
    }};

    // 1. ProfitHelm homepage hub slug resolves to "/" instead of 404 /tools/tax-bracket-capital-allocation-hub/
    const phHomeCheckout = await ph.onRequestGet({{
      request: new Request("https://profithelm.com/api/lead-capture?checkout=1&redirect=1&tool=tax-bracket-capital-allocation-hub"),
      env: phEnv,
    }});
    const phFulfill = await ph.onRequestGet({{
      request: new Request("https://profithelm.com/api/lead-capture?fulfill=1&session_id=cs_live_paid_home"),
      env: phEnv,
    }});
    const phFulfillJson = await phFulfill.json();

    // 2. LienBond $79 and $49 SKUs resolve cleanly
    const lb79 = await lb.onRequestGet({{
      request: new Request("https://lienbond.com/api/lead-capture?checkout=1&redirect=1&sku=lb_surety_lien_wh347_packet&tool=homepage"),
      env: lbEnv,
    }});
    const lb49 = await lb.onRequestGet({{
      request: new Request("https://lienbond.com/api/lead-capture?checkout=1&redirect=1&sku=lb_workers_comp_emr_audit_packet&tool=homepage"),
      env: lbEnv,
    }});

    // 3. Anti-bounce guard blocks masked/synthetic/role probes from checkout & ZeptoMail
    const maskedCheckout = await ph.onRequestGet({{
      request: new Request("https://profithelm.com/api/lead-capture?checkout=1&lead_id=lead_masked_probe&email=a***@profithelm.com"),
      env: phEnv,
    }});
    const cisoPost = await gh.onRequestPost({{
      request: new Request("https://gainhelm.com/api/lead-capture", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ email: "ciso@gainhelm.com", tool_slug: "soc2-roi-calculator" }}),
      }}),
      env: ghEnv,
    }});
    const cisoBody = await cisoPost.json();
    const zeptoAfterProbe = zeptoCalls.length;

    // Real buyer & arif.coskun@profithelm.com succeed and dispatch ZeptoMail
    const realPost = await ph.onRequestPost({{
      request: new Request("https://profithelm.com/api/lead-capture", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ email: "founder@acmecorp.io", tool_slug: "burn-multiple-calculator" }}),
      }}),
      env: phEnv,
    }});
    const realBody = await realPost.json();
    const zeptoAfterReal = zeptoCalls.length;

    // 4. GET /api/lead-capture fails closed without TELEMETRY_EXPORT_SECRET
    const listUnauth = await ph.onRequestGet({{
      request: new Request("https://profithelm.com/api/lead-capture?limit=10"),
      env: phEnv,
    }});
    const listUnset = await ph.onRequestGet({{
      request: new Request("https://profithelm.com/api/lead-capture?limit=10"),
      env: {{ PROFITHELM_LEADS: phKv }},
    }});
    const listHealth = await ph.onRequestGet({{
      request: new Request("https://profithelm.com/api/lead-capture?health=1"),
      env: phEnv,
    }});
    const listHealthJson = await listHealth.json();
    const listAuth = await ph.onRequestGet({{
      request: new Request("https://profithelm.com/api/lead-capture?limit=10", {{
        headers: {{ "x-telemetry-secret": "lead_sec_777" }},
      }}),
      env: phEnv,
    }});
    const listAuthJson = await listAuth.json();

    console.log(JSON.stringify({{
      phHomeCheckoutStatus: phHomeCheckout.status,
      phFulfillStatus: phFulfill.status,
      phFulfillOk: Boolean(phFulfillJson.ok && phFulfillJson.status === "toolkit_fulfilled"),
      lb79Status: lb79.status,
      lb49Status: lb49.status,
      stripeCalls,
      maskedCheckoutStatus: maskedCheckout.status,
      cisoPostStatus: cisoPost.status,
      cisoZeptoDelivery: cisoBody.zeptomail_status || cisoBody.error || "",
      zeptoAfterProbe,
      realStripeDisplayName: realBody.stripe_display_name,
      zeptoAfterReal,
      zeptoSenderAddr: zeptoCalls[0]?.from?.address || "",
      listUnauthStatus: listUnauth.status,
      listUnsetStatus: listUnset.status,
      listHealthJson,
      listAuthStatus: listAuth.status,
      listAuthCount: listAuthJson.count,
    }}));
    """
    out = _run_node_esm(harness)
    assert out["phHomeCheckoutStatus"] == 302
    assert out["stripeCalls"][0]["success_url"].startswith(
        "https://profithelm.com/?checkout_status=success&checkout_fulfilled=1"
    )
    assert "tax-bracket-capital-allocation-hub/" not in out["stripeCalls"][0]["success_url"]
    assert out["phFulfillStatus"] == 200
    assert out["phFulfillOk"] is True

    # LienBond $79 and $49 SKUs
    assert out["lb79Status"] == 302
    assert out["lb49Status"] == 302
    assert out["stripeCalls"][1]["sku"] == "lb_surety_lien_wh347_packet"
    assert out["stripeCalls"][1]["unit_amount"] == "7900"
    assert out["stripeCalls"][2]["sku"] == "lb_workers_comp_emr_audit_packet"
    assert out["stripeCalls"][2]["unit_amount"] == "4900"

    # Anti-bounce & sender identity (masked email never passed into Stripe customer_email)
    assert out["maskedCheckoutStatus"] == 200
    assert out["stripeCalls"][3]["customer_email"] is None
    assert out["stripeCalls"][-1]["customer_email"] == "founder@acmecorp.io"
    assert out["cisoPostStatus"] == 400 or out["cisoZeptoDelivery"] == "skipped_placeholder_or_internal_recipient"
    assert out["zeptoAfterProbe"] == 0
    assert out["realStripeDisplayName"] == "ProfitHelm"
    assert out["zeptoAfterReal"] == 1
    assert out["zeptoSenderAddr"] == "arif.coskun@profithelm.com"

    # Fail-closed GET /api/lead-capture auth
    assert out["listUnauthStatus"] == 401
    assert out["listUnsetStatus"] == 401
    assert out["listHealthJson"] == {"ok": True, "auth_required": True}
    assert out["listAuthStatus"] == 200
    assert out["listAuthCount"] >= 1


# ---------------------------------------------------------------------------
# 5. KV Namespace Sync, LienBond Estate Compile, Publisher Meta Hygiene, & Zero Dashes
# ---------------------------------------------------------------------------


def test_sync_tenant_edge_replaces_stale_wrangler_kv_ids_and_mirrors_dist(tmp_path: Path) -> None:
    for prop, kv_map in EXPECTED_KV_IDS.items():
        repo_dir = tmp_path / prop
        (repo_dir / "dist").mkdir(parents=True)
        (repo_dir / "functions" / "r").mkdir(parents=True)
        (repo_dir / "functions" / "_middleware.js").write_text(
            "export async function onRequest(context) { return context.next(); }\n",
            encoding="utf-8",
        )
        leads_binding, tel_binding = list(kv_map.keys())
        # Seed stale KV IDs in wrangler.toml to verify regex replacement (not just append-if-missing)
        (repo_dir / "wrangler.toml").write_text(
            f'name = "{prop}"\n'
            f'pages_build_output_dir = "dist"\n\n'
            f'[[kv_namespaces]]\n'
            f'binding = "{leads_binding}"\n'
            f'id = "00000000000000000000000000000000"\n\n'
            f'[[kv_namespaces]]\n'
            f'binding = "{tel_binding}"\n'
            f'id = "11111111111111111111111111111111"\n',
            encoding="utf-8",
        )
        res = edge.sync_tenant_edge_redirect_function(repo_dir, property_id=prop)
        assert res["status"] in ("UPDATED", "UNCHANGED")
        wrangler_txt = (repo_dir / "wrangler.toml").read_text(encoding="utf-8")
        assert "00000000000000000000000000000000" not in wrangler_txt
        assert "11111111111111111111111111111111" not in wrangler_txt
        for binding, expected_id in kv_map.items():
            assert binding in wrangler_txt
            assert expected_id in wrangler_txt

        for rel_fn in (
            "functions/_middleware.js",
            "functions/r/[partner].js",
            "functions/api/telemetry.js",
            "functions/api/lead-capture.js",
            "dist/functions/_middleware.js",
            "dist/functions/r/[partner].js",
            "dist/functions/api/telemetry.js",
            "dist/functions/api/lead-capture.js",
        ):
            assert (repo_dir / rel_fn).is_file(), f"Missing {rel_fn} for {prop}"


def test_lienbond_compiler_sku_price_parity_and_publisher_meta_isolation(tmp_path: Path) -> None:
    lb_repo = tmp_path / "lienbond"
    res = compiler.compile_lienbond_estate(lb_repo, run_retrofit=False)
    assert res["compiled_count"] >= 10

    home_html = (lb_repo / "dist" / "index.html").read_text(encoding="utf-8")
    assert "lb_surety_lien_wh347_packet" in home_html
    assert "($79)" in home_html
    assert "lb_workers_comp_emr_audit_packet" in home_html
    assert "($49)" in home_html
    assert "($89)" not in home_html
    assert "Next Insurance" not in home_html
    assert "Simply Business" in home_html
    assert "editorial@lienbond.com" not in home_html
    assert "wonyZkQ-8DZKcbdV_GTbbxIZVWgA3kWYvABx0jSrN4Q" in home_html

    # Test RetroReflectionEngine.sync_tenant_publisher_prerequisites across ProfitHelm vs non-ProfitHelm
    ph_dist = tmp_path / "profithelm" / "dist"
    ph_dist.mkdir(parents=True)
    (ph_dist / "index.html").write_text(
        '<!doctype html><html><head>'
        '<meta name="google-site-verification" content="google-site-verification-verified-2026">'
        '<meta name="ir-site-verification-token" content="7932737">'
        '<meta name="cj-promotional-property-id" content="101725461">'
        '<meta name="sovrn-commerce-domain-key" content="2987330">'
        '</head><body></body></html>',
        encoding="utf-8",
    )
    maintenance.RetroReflectionEngine.sync_tenant_publisher_prerequisites(
        ph_dist, "profithelm", "https://profithelm.com"
    )
    ph_head = (ph_dist / "index.html").read_text(encoding="utf-8")
    assert "1b9AjxT3rRYA2iyPRraN2ShDNqEoKsfYW39UiTncB4U" in ph_head
    assert 'content="7932737"' not in ph_head
    assert 'content="101906407"' in ph_head
    assert 'content="0a5ac1bfe04034bff021b394f5e71d90"' in ph_head
    ph_kit = json.loads((ph_dist / "media-kit.json").read_text(encoding="utf-8"))
    assert ph_kit["verified_network_identities"]["first_party_checkout"]["merchant_account_id"] == "acct_1T6fSTIq0ckFsf5j"
    assert ph_kit["verified_network_identities"]["cj_affiliate"]["promotional_property_id"] == "101906407"

    gh_dist = tmp_path / "gainhelm" / "dist"
    gh_dist.mkdir(parents=True)
    (gh_dist / "index.html").write_text(
        '<!doctype html><html><head>'
        '<meta name="google-site-verification" content="google-site-verification-verified-2026">'
        '<meta name="ir-site-verification-token" content="7932737">'
        '<meta name="cj-promotional-property-id" content="101725461">'
        '<meta name="sovrn-commerce-domain-key" content="2987330">'
        '</head><body></body></html>',
        encoding="utf-8",
    )
    maintenance.RetroReflectionEngine.sync_tenant_publisher_prerequisites(
        gh_dist, "gainhelm", "https://gainhelm.com"
    )
    gh_head = (gh_dist / "index.html").read_text(encoding="utf-8")
    assert "Elwe-MFi7Z8hEE7ybiGr8xXBqSv87dF_ZMpqkhCDlQ8" in gh_head
    assert "cj-promotional-property-id" not in gh_head
    assert "sovrn-commerce-domain-key" not in gh_head
    assert "ir-site-verification-token" not in gh_head
    gh_kit = json.loads((gh_dist / "media-kit.json").read_text(encoding="utf-8"))
    assert gh_kit["verified_network_identities"]["first_party_checkout"]["merchant_account_id"] == "acct_1T6fSTIq0ckFsf5j"
    assert "cj_affiliate" not in gh_kit["verified_network_identities"]
    assert "impact_com" not in gh_kit["verified_network_identities"]
    assert "sovrn_commerce" not in gh_kit["verified_network_identities"]


def test_zero_em_dash_or_en_dash_across_all_owned_files() -> None:
    for rel_path in OWNED_FILES:
        full_path = REPO_ROOT / rel_path
        text = full_path.read_text(encoding="utf-8")
        assert "\u2014" not in text, f"Found em-dash (U+2014) in {rel_path}"
        assert "\u2013" not in text, f"Found en-dash (U+2013) in {rel_path}"


# ---------------------------------------------------------------------------
# 6. Phase 3 Red-Team Remediation Regressions (Bugs 1.1-4.2)
# ---------------------------------------------------------------------------


def test_redteam_bug_1_1_and_1_2_all_four_tenants_anti_bounce_and_canonical_sender(tmp_path: Path) -> None:
    """
    Verifies across all 4 compiled lead-capture.js functions:
    - Any '*', local_prefixes (ciso@, audit@, grc-*, probe*, test*), synthetic_domains
      (example.com, example.net, example.org, invalid.local, test.com, profithelm.test),
      unprovisioned fleet domains (@gainhelm.com, @lienbond.com, @prexvo.com, @1031exchangehelm.com),
      and non-canonical @profithelm.com (arif@profithelm.com) are blocked from Stripe customer_email
      AND from BOTH Zoho and ZeptoMail (including the zohoPrimary fallback rail).
    - Legacy ZOHO_FROM_EMAIL, ZEPTOMAIL_FROM_EMAIL, STRIPE_MERCHANT_EMAIL, and ZOHO_SYNTHETIC_SINK_EMAIL
      normalize to arif.coskun@profithelm.com.
    - Zero literal cross-tenant domain strings appear in any tenant's compiled lead-capture.js.
    """
    tenant_domains = {
        "profithelm": "profithelm.com",
        "prexvo": "prexvo.com",
        "gainhelm": "gainhelm.com",
        "lienbond": "lienbond.com",
    }
    mjs_uris: Dict[str, str] = {}
    for prop, own_dom in tenant_domains.items():
        js_src = edge.generate_edge_lead_capture_function(property_id=prop)
        for other_prop, other_dom in tenant_domains.items():
            if other_prop != prop and other_prop != "profithelm":
                assert other_dom not in js_src, f"Foreign domain {other_dom} leaked into {prop} lead-capture.js"
        mjs_path = tmp_path / f"{prop}_lead_rt.mjs"
        mjs_path.write_text(js_src, encoding="utf-8")
        mjs_uris[prop] = mjs_path.as_uri()

    blocked_emails = [
        "arif@profithelm.com",
        "support@profithelm.com",
        "a***@profithelm.com",
        "ciso@acmecorp.io",
        "audit@vendorfirm.io",
        "grc-ops@enterprise.io",
        "probe99@realfirm.io",
        "test_buyer@realfirm.io",
        "buyer@example.net",
        "buyer@invalid.local",
        "buyer@test.com",
        "buyer@profithelm.test",
        "ops@gainhelm.com",
        "ops@lienbond.com",
        "ops@prexvo.com",
        "ops@1031exchangehelm.com",
    ]
    for b_addr in blocked_emails:
        cls = lead_classification.classify_lead_email(b_addr)
        assert cls == "synthetic", f"Expected {b_addr} to be synthetic in Python classifier, got {cls}"
    assert lead_classification.classify_lead_email("jane.doe@acme-llc.com") == "real"

    harness = f"""
    import * as ph from {json.dumps(mjs_uris["profithelm"])};
    import * as px from {json.dumps(mjs_uris["prexvo"])};
    import * as gh from {json.dumps(mjs_uris["gainhelm"])};
    import * as lb from {json.dumps(mjs_uris["lienbond"])};

    const mods = {{
      profithelm: {{ mod: ph, host: "https://profithelm.com", kvKey: "PROFITHELM_LEADS" }},
      prexvo: {{ mod: px, host: "https://prexvo.com", kvKey: "PREXVO_LEADS" }},
      gainhelm: {{ mod: gh, host: "https://gainhelm.com", kvKey: "GAINHELM_LEADS" }},
      lienbond: {{ mod: lb, host: "https://lienbond.com", kvKey: "LIENBOND_LEADS" }},
    }};

    function makeKv() {{
      const store = new Map();
      return {{
        async put(k, v) {{ store.set(k, v); }},
        async get(k) {{ return store.get(k) || null; }},
        async list() {{ return {{ keys: [] }}; }},
      }};
    }}

    const stripeCalls = [];
    const zeptoCalls = [];
    const zohoCalls = [];

    globalThis.fetch = async (url, init = {{}}) => {{
      const u = String(url);
      if (u.includes("api.stripe.com/v1/checkout/sessions")) {{
        const params = new URLSearchParams(String(init.body || ""));
        stripeCalls.push({{
          customer_email: params.get("customer_email"),
          merchant_email: params.get("metadata[merchant_email]"),
        }});
        return new Response(
          JSON.stringify({{ id: "cs_live_rt", url: "https://checkout.stripe.com/c/pay/cs_live_rt" }}),
          {{ status: 200, headers: {{ "Content-Type": "application/json" }} }}
        );
      }}
      if (u.includes("api.nango.dev/connection/")) {{
        return new Response(
          JSON.stringify({{ credentials: {{ access_token: "zoho_tok_rt" }} }}),
          {{ status: 200, headers: {{ "Content-Type": "application/json" }} }}
        );
      }}
      if (u.includes("mail.zoho.com/api/accounts/")) {{
        const payload = JSON.parse(String(init.body || "{{}}"));
        zohoCalls.push(payload);
        // Simulate Zoho 500 on force_zepto_fallback@realbuyer.io so zohoPrimary falls through to ZeptoMail!
        if (payload.toAddress === "force_zepto_fallback@realbuyer.io") {{
          return new Response(JSON.stringify({{ error: "simulated_failover" }}), {{ status: 500 }});
        }}
        return new Response(
          JSON.stringify({{ data: {{ messageId: "zoho_msg_rt_1" }} }}),
          {{ status: 200, headers: {{ "Content-Type": "application/json" }} }}
        );
      }}
      if (u.includes("zeptomail.com")) {{
        const payload = JSON.parse(String(init.body || "{{}}"));
        zeptoCalls.push(payload);
        return new Response(JSON.stringify({{ request_id: "zm_rt_1" }}), {{ status: 200 }});
      }}
      return new Response(JSON.stringify({{ ok: true }}), {{ status: 200 }});
    }};

    const blockedEmails = {json.dumps(blocked_emails)};

    for (const [prop, cfg] of Object.entries(mods)) {{
      const env = {{
        [cfg.kvKey]: makeKv(),
        STRIPE_SECRET_KEY: "sk_live_rt",
        STRIPE_MERCHANT_EMAIL: "editorial@lienbond.com",
        ZEPTOMAIL_TOKEN: "zm_tok_rt",
        ZEPTOMAIL_FROM_EMAIL: "noreply@gainhelm.com",
        NANGO_SECRET_KEY: "nango_sec_rt",
        NANGO_CONNECTION_ID: "nango_conn_rt",
        ZOHO_FROM_EMAIL: "billing@prexvo.com",
        ZOHO_SYNTHETIC_SINK_EMAIL: "arif@profithelm.com",
      }};
      for (const badEmail of blockedEmails) {{
        await cfg.mod.onRequestPost({{
          request: new Request(`${{cfg.host}}/api/lead-capture`, {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify({{ email: badEmail, tool_slug: "audit-calc" }}),
          }}),
          env,
        }});
        await cfg.mod.onRequestGet({{
          request: new Request(`${{cfg.host}}/api/lead-capture?checkout=1&email=${{encodeURIComponent(badEmail)}}&tool_slug=audit-calc`),
          env,
        }});
      }}
    }}

    const outboundAfterBlocked = zohoCalls.length + zeptoCalls.length;
    const leakedCustomerEmails = stripeCalls.map((c) => c.customer_email).filter(Boolean);
    const nonCanonicalMerchants = stripeCalls
      .map((c) => c.merchant_email)
      .filter((m) => m && m !== "arif.coskun@profithelm.com");

    // Verify canonical Zoho sender & ZeptoMail failover sender on real buyer + arif.coskun@profithelm.com
    for (const [prop, cfg] of Object.entries(mods)) {{
      const env = {{
        [cfg.kvKey]: makeKv(),
        STRIPE_SECRET_KEY: "sk_live_rt",
        STRIPE_MERCHANT_EMAIL: "editorial@lienbond.com",
        ZEPTOMAIL_TOKEN: "zm_tok_rt",
        ZEPTOMAIL_FROM_EMAIL: "noreply@gainhelm.com",
        NANGO_SECRET_KEY: "nango_sec_rt",
        NANGO_CONNECTION_ID: "nango_conn_rt",
        ZOHO_FROM_EMAIL: "arif@profithelm.com",
        ZOHO_SYNTHETIC_SINK_EMAIL: "editorial@lienbond.com",
      }};
      await cfg.mod.onRequestPost({{
        request: new Request(`${{cfg.host}}/api/lead-capture`, {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ email: "arif.coskun@profithelm.com", tool_slug: "audit-calc" }}),
        }}),
        env,
      }});
      await cfg.mod.onRequestPost({{
        request: new Request(`${{cfg.host}}/api/lead-capture`, {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ email: "force_zepto_fallback@realbuyer.io", tool_slug: "audit-calc" }}),
        }}),
        env,
      }});
    }}

    console.log(JSON.stringify({{
      outboundAfterBlocked,
      leakedCustomerEmails,
      nonCanonicalMerchants,
      zohoSenders: [...new Set(zohoCalls.map((c) => c.fromAddress))],
      zeptoSenders: [...new Set(zeptoCalls.map((c) => c.from && c.from.address))],
      zohoCount: zohoCalls.length,
      zeptoCount: zeptoCalls.length,
    }}));
    """
    out = _run_node_esm(harness)
    assert out["outboundAfterBlocked"] == 0
    assert out["leakedCustomerEmails"] == []
    assert out["nonCanonicalMerchants"] == []
    assert out["zohoSenders"] == ["arif.coskun@profithelm.com"]
    assert out["zeptoSenders"] == ["arif.coskun@profithelm.com"]
    assert out["zohoCount"] >= 4
    assert out["zeptoCount"] >= 3


def test_redteam_bug_2_1_to_2_3_vault_hub_edge_sync_across_all_four_tenants(tmp_path: Path) -> None:
    """
    Verifies:
    - Declining ramp in MonetizationHub removes ramp from get_direct_contract_upgrades,
      returns status='declined' / is_live=False in get_route, and marks BOTH /r/ramp AND
      /r/ramp_impact declined (isDirect=false, declined_partner_blocked) in compiled JS.
    - sync_from_network_payload handles terminated, revoked, expired, and suspended as declined
      and removes partners from live_revenue_ready.
    - Approving vs declining suretybonds_direct (lienbond + surety_bonds alias),
      vanta_security (gainhelm + vanta alias), and splash_financial (prexvo) in MonetizationHub
      dynamically updates compiled /r/[partner].js without touching Python constants.
    """
    vault_copy = tmp_path / "vault_rt_sync.json"
    vault_copy.write_text(
        (REPO_ROOT / "pseofactory" / "monetization_vault.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    hub = affiliates_hub.MonetizationHub(vault_path=vault_copy)

    # 1. Decline ramp on profithelm -> must prune get_direct_contract_upgrades, get_route, /r/ramp, and /r/ramp_impact
    hub.sync_partner_program(
        network="impact",
        program_data={
            "program_key": "ramp",
            "category": "CORPORATE_CARDS",
            "status": "declined",
            "direct_url": "https://ramp.com/",
        },
        property_id="profithelm",
    )
    ph_upgrades = hub.get_direct_contract_upgrades("profithelm")
    assert "ramp" not in ph_upgrades
    ramp_route = hub.get_route("profithelm", "saas-runway-calculator", "ramp")
    assert ramp_route["status"] == "declined"
    assert ramp_route["is_live"] is False
    assert "join.ramp.com" not in ramp_route["url"]

    # 2. sync_from_network_payload handles terminated/revoked/expired/suspended as declined
    for bad_status, pk_target in (
        ("terminated", "coinledger"),
        ("revoked", "koinly"),
        ("expired", "gusto"),
        ("suspended", "rippling"),
    ):
        res = hub.sync_from_network_payload(
            network="impact",
            payload=[{"partner_key": pk_target, "status": bad_status}],
            property_id="profithelm",
        )
        assert res["updated"] == 1
        raw_after = json.loads(vault_copy.read_text(encoding="utf-8"))
        assert raw_after["properties"]["profithelm"]["partners"][pk_target]["status"] == "declined"
        assert pk_target not in raw_after["properties"]["profithelm"]["roster_tiers"]["live_revenue_ready"]
        assert pk_target not in hub.get_direct_contract_upgrades("profithelm")

    # 3. Approve suretybonds_direct (lienbond), vanta_security (gainhelm), and splash_financial (prexvo)
    hub.sync_partner_program(
        network="in_house",
        program_data={
            "program_key": "suretybonds_direct",
            "category": "SURETY_BONDS",
            "status": "live",
            "tracking_url": "https://www.suretybondsdirect.com/?ref=lienbond_live_1",
        },
        property_id="lienbond",
    )
    hub.sync_partner_program(
        network="in_house",
        program_data={
            "program_key": "vanta_security",
            "category": "COMPLIANCE_AUTOMATION",
            "status": "live",
            "tracking_url": "https://www.vanta.com/?partner=gainhelm_live_1",
        },
        property_id="gainhelm",
    )
    hub.sync_partner_program(
        network="in_house",
        program_data={
            "program_key": "splash_financial",
            "category": "STUDENT_LOAN_REFINANCE",
            "status": "live",
            "tracking_url": "https://www.splashfinancial.com/?ref=prexvo_live_1",
        },
        property_id="prexvo",
    )

    ph_r_live = tmp_path / "ph_r_declined_ramp.mjs"
    lb_r_live = tmp_path / "lb_r_approved.mjs"
    gh_r_live = tmp_path / "gh_r_approved.mjs"
    px_r_live = tmp_path / "px_r_approved.mjs"
    ph_r_live.write_text(edge.generate_edge_redirect_function("profithelm", hub=hub), encoding="utf-8")
    lb_r_live.write_text(edge.generate_edge_redirect_function("lienbond", hub=hub), encoding="utf-8")
    gh_r_live.write_text(edge.generate_edge_redirect_function("gainhelm", hub=hub), encoding="utf-8")
    px_r_live.write_text(edge.generate_edge_redirect_function("prexvo", hub=hub), encoding="utf-8")

    # Now decline those 3 non-ProfitHelm partners in hub and re-generate to verify dynamic decline blocking too
    hub.sync_partner_program(
        network="in_house",
        program_data={
            "program_key": "suretybonds_direct",
            "category": "SURETY_BONDS",
            "status": "declined",
            "direct_url": "https://www.suretybondsdirect.com/",
        },
        property_id="lienbond",
    )
    hub.sync_partner_program(
        network="in_house",
        program_data={
            "program_key": "vanta_security",
            "category": "COMPLIANCE_AUTOMATION",
            "status": "declined",
            "direct_url": "https://www.vanta.com",
        },
        property_id="gainhelm",
    )
    hub.sync_partner_program(
        network="in_house",
        program_data={
            "program_key": "splash_financial",
            "category": "STUDENT_LOAN_REFINANCE",
            "status": "declined",
            "direct_url": "https://www.splashfinancial.com/",
        },
        property_id="prexvo",
    )
    lb_r_dec = tmp_path / "lb_r_declined.mjs"
    gh_r_dec = tmp_path / "gh_r_declined.mjs"
    px_r_dec = tmp_path / "px_r_declined.mjs"
    lb_r_dec.write_text(edge.generate_edge_redirect_function("lienbond", hub=hub), encoding="utf-8")
    gh_r_dec.write_text(edge.generate_edge_redirect_function("gainhelm", hub=hub), encoding="utf-8")
    px_r_dec.write_text(edge.generate_edge_redirect_function("prexvo", hub=hub), encoding="utf-8")

    harness = f"""
    import * as phDec from {json.dumps(ph_r_live.as_uri())};
    import * as lbLive from {json.dumps(lb_r_live.as_uri())};
    import * as ghLive from {json.dumps(gh_r_live.as_uri())};
    import * as pxLive from {json.dumps(px_r_live.as_uri())};
    import * as lbDec from {json.dumps(lb_r_dec.as_uri())};
    import * as ghDec from {json.dumps(gh_r_dec.as_uri())};
    import * as pxDec from {json.dumps(px_r_dec.as_uri())};

    async function callR(mod, host, slug) {{
      const res = await mod.onRequest({{
        request: new Request(`${{host}}/r/${{slug}}?source=rt-probe`),
        params: {{ partner: slug }},
        env: {{}},
        waitUntil: (p) => p,
      }});
      return {{
        status: res.status,
        location: res.headers.get("Location"),
        tier: res.headers.get("X-Edge-Contract-Tier"),
      }};
    }}

    console.log(JSON.stringify({{
      phRamp: await callR(phDec, "https://profithelm.com", "ramp"),
      phRampImpact: await callR(phDec, "https://profithelm.com", "ramp_impact"),
      lbSuretyLive: await callR(lbLive, "https://lienbond.com", "surety_bonds"),
      ghVantaLive: await callR(ghLive, "https://gainhelm.com", "vanta"),
      pxSplashLive: await callR(pxLive, "https://prexvo.com", "splash_financial"),
      lbSuretyDec: await callR(lbDec, "https://lienbond.com", "surety_bonds"),
      ghVantaDec: await callR(ghDec, "https://gainhelm.com", "vanta"),
      pxSplashDec: await callR(pxDec, "https://prexvo.com", "splash_financial"),
    }}));
    """
    out = _run_node_esm(harness)
    assert out["phRamp"]["tier"] == "declined_partner_blocked"
    assert "join.ramp.com" not in (out["phRamp"]["location"] or "")
    assert out["phRampImpact"]["tier"] == "declined_partner_blocked"
    assert "join.ramp.com" not in (out["phRampImpact"]["location"] or "")

    assert out["lbSuretyLive"]["tier"] in ("live", "direct_contract_upgraded")
    assert out["lbSuretyLive"]["location"].startswith("https://www.suretybondsdirect.com/?ref=lienbond_live_1")

    assert out["ghVantaLive"]["tier"] in ("live", "direct_contract_upgraded")
    assert out["ghVantaLive"]["location"].startswith("https://www.vanta.com/?partner=gainhelm_live_1")

    assert out["pxSplashLive"]["tier"] in ("live", "direct_contract_upgraded")
    assert out["pxSplashLive"]["location"].startswith("https://www.splashfinancial.com/?ref=prexvo_live_1")

    assert out["lbSuretyDec"]["tier"] == "declined_partner_blocked"
    assert out["ghVantaDec"]["tier"] == "declined_partner_blocked"
    assert out["pxSplashDec"]["tier"] == "declined_partner_blocked"


def test_redteam_bug_3_1_and_3_2_brand_honesty_and_callout_normalizer(tmp_path: Path) -> None:
    """
    Verifies:
    - SuretyBondsDirect.com brand naming consistency across affiliates.py and visual_primitives.py.
    - /r/equipment_macrs is pending (Crest Capital) and never redirects to Xendoo.
    - normalize_html_callout_message_match gates ProfitHelm fallback_copy to profithelm ONLY and
      uses live CJ click IDs click-101906407-11917161 (efile) and click-101906407-15704796 (eztaxreturn).
    """
    sb_offer = affiliates.PROFITHELM_AFFILIATES["suretybonds_direct"]
    assert "SuretyBondsDirect.com" in repr(sb_offer)
    assert "SuretyBonds.com" not in repr(sb_offer)
    vp_src = Path(visual_primitives.__file__).read_text(encoding="utf-8")
    assert '"SuretyBonds.com"' not in vp_src
    assert '"SuretyBondsDirect.com"' in vp_src

    eq_offer = affiliates.PROFITHELM_AFFILIATES["equipment_macrs"]
    assert eq_offer.status == "pending"
    assert eq_offer.default_url == "https://www.crestcapital.com/"
    assert "xendoo" not in eq_offer.default_url.lower()

    ph_r = tmp_path / "ph_r_eq.mjs"
    ph_r.write_text(edge.generate_edge_redirect_function("profithelm"), encoding="utf-8")
    out = _run_node_esm(
        f"""
        import * as ph from {json.dumps(ph_r.as_uri())};
        const res = await ph.onRequest({{
          request: new Request("https://profithelm.com/r/equipment_macrs?source=macrs-calc"),
          params: {{ partner: "equipment_macrs" }},
          env: {{}},
          waitUntil: (p) => p,
        }});
        console.log(JSON.stringify({{
          location: res.headers.get("Location"),
          tier: res.headers.get("X-Edge-Contract-Tier"),
        }}));
        """
    )
    assert out["tier"] == "native_unmonetized_destination"
    assert (out["location"] or "").startswith("https://www.crestcapital.com")
    assert "xendoo" not in (out["location"] or "").lower()

    # Verify normalize_html_callout_message_match does NOT leak ProfitHelm fallback links into gainhelm
    sample_gh_html = (
        '<div class="callout-card"><a href="/r/efile?source=test">Compare</a></div>'
    )
    gh_norm = affiliates.normalize_html_callout_message_match(sample_gh_html, property_id="gainhelm")
    assert "101906407" not in gh_norm

    aff_src = Path(affiliates.__file__).read_text(encoding="utf-8")
    assert "click-101906407-11917161" in aff_src
    assert "click-101906407-15704796" in aff_src
    assert "click-101906407-10566670" not in aff_src
    assert "click-101906407-10862091" not in aff_src


def test_redteam_bug_4_1_and_4_2_exact_stripe_sku_checkout_parity(tmp_path: Path) -> None:
    """
    Verifies exact Stripe checkout unit_amount and metadata[sku] preservation for:
    - ph_1031_boot_waterfall_kit -> $79 (7900 cents), metadata[sku] == ph_1031_boot_waterfall_kit
    - ph_section179_macrs_audit_kit -> $49 (4900 cents), metadata[sku] == ph_section179_macrs_audit_kit
    - px_verified_partner_slot -> $299 (29900 cents), metadata[sku] == px_verified_partner_slot
    """
    ph_lead = tmp_path / "ph_sku.mjs"
    px_lead = tmp_path / "px_sku.mjs"
    ph_lead.write_text(edge.generate_edge_lead_capture_function("profithelm"), encoding="utf-8")
    px_lead.write_text(edge.generate_edge_lead_capture_function("prexvo"), encoding="utf-8")

    harness = f"""
    import * as ph from {json.dumps(ph_lead.as_uri())};
    import * as px from {json.dumps(px_lead.as_uri())};

    const sessions = [];
    globalThis.fetch = async (url, init = {{}}) => {{
      if (String(url).includes("api.stripe.com/v1/checkout/sessions")) {{
        const params = new URLSearchParams(String(init.body || ""));
        sessions.push({{
          unit_amount: params.get("line_items[0][price_data][unit_amount]"),
          meta_sku: params.get("metadata[sku]"),
          meta_offer_sku: params.get("metadata[offer_sku]"),
        }});
        return new Response(
          JSON.stringify({{ id: "cs_live_sku", url: "https://checkout.stripe.com/c/pay/cs_live_sku" }}),
          {{ status: 200, headers: {{ "Content-Type": "application/json" }} }}
        );
      }}
      return new Response("{{}}", {{ status: 200 }});
    }};

    const env = {{ STRIPE_SECRET_KEY: "sk_live_sku" }};

    // Pass tool=general on 1031 SKU so slug heuristics CANNOT save a missing SKU check!
    const r1031 = await ph.onRequestGet({{
      request: new Request("https://profithelm.com/api/lead-capture?checkout=1&sku=ph_1031_boot_waterfall_kit&tool=general"),
      env,
    }});
    const b1031 = await r1031.json();

    // Pass tool=working-capital on Section 179 SKU so invoice_factoring slug check CANNOT hijack SKU!
    const r179 = await ph.onRequestGet({{
      request: new Request("https://profithelm.com/api/lead-capture?checkout=1&sku=ph_section179_macrs_audit_kit&tool=working-capital"),
      env,
    }});
    const b179 = await r179.json();

    // Pass Prexvo $299 verified partner slot SKU
    const rPx = await px.onRequestGet({{
      request: new Request("https://prexvo.com/api/lead-capture?checkout=1&sku=px_verified_partner_slot&tool=freight-audit"),
      env,
    }});
    const bPx = await rPx.json();

    console.log(JSON.stringify({{
      sessions,
      b1031Sku: b1031.offer_sku,
      b1031Price: b1031.offer_price_usd,
      b179Sku: b179.offer_sku,
      b179Price: b179.offer_price_usd,
      bPxSku: bPx.offer_sku,
      bPxPrice: bPx.offer_price_usd,
    }}));
    """
    out = _run_node_esm(harness)
    assert out["b1031Sku"] == "ph_1031_boot_waterfall_kit"
    assert out["b1031Price"] == 79
    assert out["sessions"][0]["unit_amount"] == "7900"
    assert out["sessions"][0]["meta_sku"] == "ph_1031_boot_waterfall_kit"

    assert out["b179Sku"] == "ph_section179_macrs_audit_kit"
    assert out["b179Price"] == 49
    assert out["sessions"][1]["unit_amount"] == "4900"
    assert out["sessions"][1]["meta_sku"] == "ph_section179_macrs_audit_kit"

    assert out["bPxSku"] == "px_verified_partner_slot"
    assert out["bPxPrice"] == 299
    assert out["sessions"][2]["unit_amount"] == "29900"
    assert out["sessions"][2]["meta_sku"] == "px_verified_partner_slot"


def test_round2_redteam_micro_gaps_subdomains_lienbond_skus_suretybonds_and_general_slug(tmp_path: Path) -> None:
    """
    Verifies all 4 Round 2 Red-Team micro-gaps:
    1. Python fleet subdomain guard in partner_tracker (_normalize_canonical_sender_email &
       _is_synthetic_or_unroutable_probe_email).
    2. Python LienBond 7-SKU parity in resolve_lead_monetization_offer, create_stripe_checkout_session,
       and synthesize_personalized_audit_workpaper.
    3. Zero residual SuretyBonds.com strings in gsc_remediation.py, market_intel.py, and competitor.py.
    4. ProfitHelm tool_slug=general resolves success_url/cancel_url to /tools/section-179-calculator/
       when sku=ph_section179_macrs_audit_kit.
    """
    from pseofactory import competitor, gsc_remediation, market_intel, partner_tracker

    # 1. Fleet subdomain guard in partner_tracker.py
    for sub_addr in (
        "ops@sub.lienbond.com",
        "user@mail.prexvo.com",
        "sec@alerts.gainhelm.com",
        "bot@mail.profithelm.com",
        "qi@escrow.1031exchangehelm.com",
    ):
        assert partner_tracker._is_synthetic_or_unroutable_probe_email(sub_addr) is True, sub_addr
        assert partner_tracker._normalize_canonical_sender_email(sub_addr) == "arif.coskun@profithelm.com"

    # 2. All 7 LienBond SKUs in Python partner_tracker.py
    expected_lb_skus = {
        "lb_instant_lien_bond_worksheet_19": (19.0, 1900),
        "lb_surety_bond_underwriting_kit": (49.0, 4900),
        "lb_workers_comp_emr_audit_kit": (49.0, 4900),
        "lb_workers_comp_emr_audit_packet": (49.0, 4900),
        "lb_wh347_certified_payroll_packet": (59.0, 5900),
        "lb_mechanics_lien_waiver_packet": (69.0, 6900),
        "lb_surety_lien_wh347_packet": (79.0, 7900),
    }
    for sku_id, (exp_usd, exp_cents) in expected_lb_skus.items():
        offer = partner_tracker.resolve_lead_monetization_offer("lienbond", "general", sku=sku_id)
        assert offer["property_id"] == "lienbond"
        assert offer["offer_sku"] == sku_id
        assert offer["offer_price_usd"] == exp_usd
        assert offer["offer_price_cents"] == exp_cents
        sess = partner_tracker.create_stripe_checkout_session("lienbond", "general", sku=sku_id, execute_live=False)
        assert sess["offer_sku"] == sku_id
        assert sess["offer_price_usd"] == exp_usd
        wp = partner_tracker.synthesize_personalized_audit_workpaper(
            "lienbond",
            "general",
            lead_record={"offer_sku": sku_id, "calculated_amount": 100000},
        )
        assert wp["property_id"] == "lienbond"
        assert wp["offer_sku"] == sku_id

    # 3. Residual SuretyBonds.com -> SuretyBondsDirect.com alignment (competitor.py retains lowercase SERP rank fixtures)
    for mod in (gsc_remediation, market_intel, competitor):
        mod_src = Path(mod.__file__).read_text(encoding="utf-8")
        assert "SuretyBonds.com" not in mod_src, f"Residual SuretyBonds.com in {mod.__name__}"
        assert "SuretyBondsDirect.com" in mod_src
    for mod in (gsc_remediation, market_intel):
        mod_src = Path(mod.__file__).read_text(encoding="utf-8")
        assert "suretybonds.com" not in mod_src.lower(), f"Residual suretybonds.com URL in {mod.__name__}"

    # 4. ProfitHelm tool_slug=general + sku=ph_section179_macrs_audit_kit -> /tools/section-179-calculator/
    ph_lead = tmp_path / "ph_general_slug.mjs"
    ph_lead.write_text(edge.generate_edge_lead_capture_function("profithelm"), encoding="utf-8")
    out = _run_node_esm(
        f"""
        import * as ph from {json.dumps(ph_lead.as_uri())};
        const stripeParams = [];
        globalThis.fetch = async (url, init = {{}}) => {{
          if (String(url).includes("api.stripe.com/v1/checkout/sessions")) {{
            const p = new URLSearchParams(String(init.body || ""));
            stripeParams.push({{
              success_url: p.get("success_url"),
              cancel_url: p.get("cancel_url"),
            }});
            return new Response(
              JSON.stringify({{ id: "cs_live_gen", url: "https://checkout.stripe.com/c/pay/cs_live_gen" }}),
              {{ status: 200, headers: {{ "Content-Type": "application/json" }} }}
            );
          }}
          return new Response("{{}}", {{ status: 200 }});
        }};
        const res = await ph.onRequestGet({{
          request: new Request("https://profithelm.com/api/lead-capture?checkout=1&tool_slug=general&sku=ph_section179_macrs_audit_kit"),
          env: {{ STRIPE_SECRET_KEY: "sk_live_gen" }},
        }});
        const body = await res.json();
        console.log(JSON.stringify({{ body, stripeParams }}));
        """
    )
    assert out["body"]["success_url"].startswith("https://profithelm.com/tools/section-179-calculator/?")
    assert out["body"]["cancel_url"].startswith("https://profithelm.com/tools/section-179-calculator/?")
    assert out["stripeParams"][0]["success_url"].startswith("https://profithelm.com/tools/section-179-calculator/?")
    assert out["stripeParams"][0]["cancel_url"].startswith("https://profithelm.com/tools/section-179-calculator/?")
