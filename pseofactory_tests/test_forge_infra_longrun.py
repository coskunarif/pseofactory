"""
Regression tests for Long-Horizon Cloudflare Edge & Infrastructure Audit Fixes:
1. Zero-get() KV Metadata & Quota Resilience in /api/telemetry and /api/lead-capture.
2. Static-Asset Function Invocation Bypass via dist/_routes.json.
3. Cloudflare Pages dist/_headers <= 95 active rule cap & middleware canonical fallback.
4. Single-pass execution in pseofactory.infra_audit.main().
Zero em-dashes. Zero en-dashes.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from pseofactory.edge import (
    EdgeConfigStandards,
    build_edge_headers,
    build_edge_routes_json,
    compact_edge_headers_to_cloudflare_cap,
    generate_edge_lead_capture_function,
    generate_edge_redirect_function,
    generate_edge_telemetry_function,
    sync_tenant_edge_redirect_function,
    validate_edge_headers_file,
)
from pseofactory.infra_audit import main as infra_audit_main
from pseofactory.verifier import MasterSEOVerifier


def test_edge_telemetry_zero_get_kv_metadata_and_quota_degradation(tmp_path: Path) -> None:
    """
    Verifies generate_edge_telemetry_function:
    - Stores compact metadata on kv.put during onRequestPost.
    - Reads key.metadata with 0 kv.get() calls during onRequestGet.
    - Gracefully degrades with HTTP 200 (kv_quota_degraded: true) instead of HTTP 500
      when kv.get() throws 'KV get() limit exceeded for the day.' on legacy keys.
    """
    telemetry_mjs = tmp_path / "telemetry.mjs"
    telemetry_mjs.write_text(generate_edge_telemetry_function("profithelm"), encoding="utf-8")

    harness = tmp_path / "run_telemetry_test.mjs"
    harness.write_text(
        f"""
import {{ onRequestPost, onRequestGet }} from {json.dumps(str(telemetry_mjs))};

let putCalls = [];
let getCalls = 0;

const mockKv = {{
  async put(key, val, opts) {{
    putCalls.push({{ key, val, opts }});
  }},
  async list(opts) {{
    return {{
      list_complete: true,
      keys: [
        {{
          name: putCalls[0].key,
          metadata: putCalls[0].opts.metadata,
        }},
      ],
    }};
  }},
  async get(key) {{
    getCalls += 1;
    throw new Error("Should not call kv.get when key.metadata is present");
  }},
}};

const postReq = new Request("https://profithelm.com/api/telemetry", {{
  method: "POST",
  headers: {{ "Content-Type": "application/json" }},
  body: JSON.stringify({{
    event: "calculator_execution",
    tool_slug: "section-179-calculator",
    path: "/tools/section-179-calculator/",
  }}),
}});

const postResp = await onRequestPost({{
  request: postReq,
  env: {{ PROFITHELM_TELEMETRY_KV: mockKv }},
}});
const postData = await postResp.json();

// Clear in-memory buffer to prove onRequestGet reads from KV metadata
globalThis.__PSEOFACTORY_TELEMETRY_BUFFER__ = [];

const getReq = new Request("https://profithelm.com/api/telemetry?limit=50");
const getResp = await onRequestGet({{
  request: getReq,
  env: {{ PROFITHELM_TELEMETRY_KV: mockKv }},
}});
const getData = await getResp.json();

// Now simulate legacy metadata-less keys where KV daily get() quota is exhausted
const quotaExhaustedKv = {{
  async list() {{
    return {{
      list_complete: true,
      keys: [
        {{ name: "evt_legacy_1" }},
        {{ name: "evt_legacy_2" }},
      ],
    }};
  }},
  async get() {{
    throw new Error("KV get() limit exceeded for the day.");
  }},
}};

const quotaResp = await onRequestGet({{
  request: new Request("https://profithelm.com/api/telemetry"),
  env: {{ PROFITHELM_TELEMETRY_KV: quotaExhaustedKv }},
}});
const quotaData = await quotaResp.json();

console.log(JSON.stringify({{
  postStatus: postResp.status,
  putCount: putCalls.length,
  hasMetadata: Boolean(putCalls[0] && putCalls[0].opts && putCalls[0].opts.metadata),
  metaToolSlug: putCalls[0]?.opts?.metadata?.tool_slug,
  getStatus: getResp.status,
  getCalls,
  getEventsCount: getData.count,
  firstEventSlug: getData.events?.[0]?.tool_slug,
  quotaStatus: quotaResp.status,
  quotaOk: quotaData.ok,
  quotaDegraded: quotaData.kv_quota_degraded,
  quotaCount: quotaData.count,
}}));
""",
        encoding="utf-8",
    )

    proc = subprocess.run(
        ["node", str(harness)],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    result = json.loads(proc.stdout.strip())
    assert result["postStatus"] == 200
    assert result["putCount"] == 1
    assert result["hasMetadata"] is True
    assert result["metaToolSlug"] == "section-179-calculator"
    assert result["getStatus"] == 200
    assert result["getCalls"] == 0, "Expected 0 kv.get() calls when key.metadata is populated"
    assert result["getEventsCount"] == 1
    assert result["firstEventSlug"] == "section-179-calculator"
    assert result["quotaStatus"] == 200, "Must return HTTP 200 instead of HTTP 500 when KV get() quota is exceeded"
    assert result["quotaOk"] is True
    assert result["quotaDegraded"] is True
    assert result["quotaCount"] == 2


def test_edge_lead_capture_zero_get_kv_metadata_across_tenants(tmp_path: Path) -> None:
    """
    Verifies generate_edge_lead_capture_function across profithelm, prexvo, gainhelm, and lienbond:
    - Stores buildEdgeLeadKvMetadata on kv.put.
    - Reads k.metadata with 0 kv.get() calls during onRequestGet summary listing.
    """
    for prop in ("profithelm", "prexvo", "gainhelm", "lienbond"):
        lead_src = generate_edge_lead_capture_function(prop)
        assert "function buildEdgeLeadKvMetadata(rec)" in lead_src
        assert "metadata: buildEdgeLeadKvMetadata(" in lead_src
        redir_src = generate_edge_redirect_function(prop)
        assert "metadata: kvMeta" in redir_src

    lead_mjs = tmp_path / "lead-capture.mjs"
    lead_mjs.write_text(generate_edge_lead_capture_function("profithelm"), encoding="utf-8")

    harness = tmp_path / "run_lead_test.mjs"
    harness.write_text(
        f"""
import {{ onRequestPost, onRequestGet }} from {json.dumps(str(lead_mjs))};

let putCalls = [];
let getCalls = 0;

const mockKv = {{
  async put(key, val, opts) {{
    putCalls.push({{ key, val, opts }});
  }},
  async list() {{
    return {{
      list_complete: true,
      keys: putCalls
        .filter((c) => c.key.startsWith("lead_profithelm_"))
        .map((c) => ({{ name: c.key, metadata: c.opts.metadata }})),
    }};
  }},
  async get() {{
    getCalls += 1;
    throw new Error("Should not call kv.get when k.metadata is present");
  }},
}};

const postReq = new Request("https://profithelm.com/api/lead-capture", {{
  method: "POST",
  headers: {{ "Content-Type": "application/json" }},
  body: JSON.stringify({{
    email: "alex.morgan@acme-manufacturing.com",
    tool_slug: "section-179-calculator",
    state: "TX",
    calculated_amount: 350000,
    partner_sharing_consent: true,
  }}),
}});

const postResp = await onRequestPost({{
  request: postReq,
  env: {{ PROFITHELM_LEADS: mockKv }},
}});
await postResp.json();

// Clear isolate memory buffer to force KV list read
globalThis.__PROFITHELM_LEADS_MEM__ = [];

const getResp = await onRequestGet({{
  request: new Request("https://profithelm.com/api/lead-capture?limit=25"),
  env: {{ PROFITHELM_LEADS: mockKv }},
}});
const getData = await getResp.json();

console.log(JSON.stringify({{
  postStatus: postResp.status,
  hasMeta: Boolean(putCalls[0]?.opts?.metadata?.lead_id),
  getStatus: getResp.status,
  getCalls,
  count: getData.count,
  realLeadsCount: getData.summary?.real_leads_count,
}}));
""",
        encoding="utf-8",
    )

    proc = subprocess.run(
        ["node", str(harness)],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    result = json.loads(proc.stdout.strip())
    assert result["postStatus"] == 200
    assert result["hasMeta"] is True
    assert result["getStatus"] == 200
    assert result["getCalls"] == 0
    assert result["count"] == 1
    assert result["realLeadsCount"] == 1


def test_build_edge_headers_caps_active_rules_at_95_and_preserves_leaf_canonical_parity(
    tmp_path: Path,
) -> None:
    """
    Verifies build_edge_headers and compact_edge_headers_to_cloudflare_cap cap active
    non-comment rules at <= 95 (under Cloudflare Pages' 100-rule limit) while preserving
    all leaf canonical links for MasterSEOVerifier.check_http_link_canonical_gate.
    """
    routes = ["/", "/about/", "/privacy/", "/tools/", "/tools/section-179-calculator/"]
    for i in range(150):
        routes.append(f"/tools/section-179-calculator/vehicle-{i:03d}/")

    headers_text = build_edge_headers(
        canonical_base="https://profithelm.com",
        routes=routes,
        static_patterns=["/static/css/*", "/static/js/*"],
    )
    headers_file = tmp_path / "_headers"
    headers_file.write_text(headers_text, encoding="utf-8")

    val = validate_edge_headers_file(headers_file, enforce_rule_cap=True)
    assert val["status"] == "PASS", f"Validation failed: {val['issues']}"
    assert val["active_rules_count"] <= EdgeConfigStandards.MAX_CLOUDFLARE_HEADERS_RULES
    assert val["cloudflare_rule_cap_compliant"] is True
    assert "# [edge-middleware-canonical] /tools/section-179-calculator/vehicle-149/" in headers_text

    # Verify MasterSEOVerifier.check_http_link_canonical_gate sees all 150 leaf routes
    verifier = MasterSEOVerifier(
        dist_dir=tmp_path,
        canonical_base="https://profithelm.com",
        domain="profithelm.com",
        brand_name="ProfitHelm",
        tools=[{"slug": "section-179-calculator", "title": "Section 179 Calculator"}],
        required_endpoints=["/feed.xml", "/llms.txt", "/llms-full.txt", "/sitemap.xml", "/"],
        leaf_route_checker=lambda _dist, found: [
            f"Missing {r}"
            for r in routes
            if not any(fr == r for fr, _ in found)
        ],
    )
    gate_res = verifier.check_http_link_canonical_gate(tmp_path)
    assert gate_res["status"] == "PASS", f"Canonical gate failed: {gate_res['issues']}"

    # Also test compact_edge_headers_to_cloudflare_cap on a raw 165-rule file
    raw_lines = [
        "/static/css/*\n  Cache-Control: public, max-age=31536000, immutable\n",
        "/*\n  Cache-Control: public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800\n",
        "/404.html\n  Cache-Control: no-store\n",
        '/feed.xml\n  Link: <https://profithelm.com/feed.xml>; rel="canonical"\n  Content-Type: application/xml; charset=utf-8\n',
    ]
    for i in range(160):
        raw_lines.append(
            f'/tools/section-1031-calculator/state-{i:03d}/\n  Link: <https://profithelm.com/tools/section-1031-calculator/state-{i:03d}/>; rel="canonical"\n'
        )
    raw_lines.append(
        '/catalog.json\n  Content-Type: application/json; charset=utf-8\n  Link: <https://profithelm.com/catalog.json>; rel="canonical"\n'
    )
    compacted = compact_edge_headers_to_cloudflare_cap("\n".join(raw_lines))
    compacted_file = tmp_path / "_headers_compacted"
    compacted_file.write_text(compacted, encoding="utf-8")
    compacted_val = validate_edge_headers_file(compacted_file, enforce_rule_cap=True)
    assert compacted_val["status"] == "PASS", f"Compacted validation failed: {compacted_val['issues']}"
    assert compacted_val["active_rules_count"] == EdgeConfigStandards.MAX_CLOUDFLARE_HEADERS_RULES


def test_build_edge_routes_json_and_sync_tenant_edge_redirect_function(tmp_path: Path) -> None:
    """
    Verifies build_edge_routes_json and sync_tenant_edge_redirect_function emit dist/_routes.json
    and inject canonical Link fallback into functions/_middleware.js.
    """
    routes_json_raw = build_edge_routes_json()
    routes_data = json.loads(routes_json_raw)
    assert routes_data["version"] == 1
    assert routes_data["include"] == ["/*"]
    for pattern in ("/static/*", "/videos/*", "/manifests/*", "/*.css", "/*.js", "/*.mp4", "/*.xml", "/*.json"):
        assert pattern in routes_data["exclude"]

    repo_dir = tmp_path / "profithelm-mock"
    (repo_dir / "functions" / "r").mkdir(parents=True)
    (repo_dir / "dist" / "functions").mkdir(parents=True)
    (repo_dir / "functions" / "_middleware.js").write_text(
        "export async function onRequest(context) {\n  const url = new URL(context.request.url);\n  const pathname = url.pathname;\n  const legacySaaSRedirects = {\n    \"/dashboard\": \"/tools/\",\n  };\n  const response = await context.next();\n  return response;\n}\n",
        encoding="utf-8",
    )

    sync_res = sync_tenant_edge_redirect_function(repo_dir, property_id="profithelm")
    assert sync_res["status"] == "UPDATED"
    assert (repo_dir / "dist" / "_routes.json").is_file()
    mw_updated = (repo_dir / "functions" / "_middleware.js").read_text(encoding="utf-8")
    assert 'rel="canonical"' in mw_updated
    assert "https://profithelm.com${pathname}" in mw_updated
    assert 'if (hostname === "www.profithelm.com")' in mw_updated
    assert '"/tools/kalshi-prediction-market-arbitrage-strategy/": "/tools/prediction-market-odds/"' in mw_updated
    assert '"/tools/saas-burn-multiple-benchmarks-2026/": "/tools/saas-runway-calculator/"' in mw_updated


def test_infra_audit_main_executes_single_pass() -> None:
    """Verifies pseofactory.infra_audit.main() invokes run_consolidated_infra_audit() exactly once."""
    mock_result = {
        "status": "PASS",
        "violations_count": 0,
        "failures": [],
        "checks": {
            "cloud_audit": {"ok": True, "message": "Clean"},
            "gcp_billing": {"ok": True, "message": "Clean"},
            "host_hygiene": {"ok": True, "message": "Clean"},
            "live_edge": {"ok": True, "message": "Clean"},
            "dns_isolation": {"ok": True, "message": "Zero routing records verified"},
        },
    }
    with patch("pseofactory.infra_audit.run_consolidated_infra_audit", return_value=mock_result) as mock_audit:
        rc = infra_audit_main()
        assert rc == 0
        assert mock_audit.call_count == 1
