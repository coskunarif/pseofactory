"""
Full Autonomous Commerce, Paywall Isolation & Clickability Gate (`commerce_gate.py`).
50+ site dynamic, fail-closed verification across:
1. Static dist/ deliverable leak scanning (HTML, manifests, catalog, media-kit, ai-benchmarks, static/js).
2. Pricing & SKU parity across pricing.py, monetization_vault.json, and compiled edge functions.
3. Isolated Node.js v22 edge commerce replay (per-tenant subprocess, fresh in-memory KV, mocked Stripe/email fetch)
   proving invalid/cross-tenant SKU HTTP 400, free-vs-paid 402 isolation, restricted YMYL HTTP 400,
   and full 3-tier E2E purchase replay (checkout -> HMAC-SHA256 webhook -> KV -> email links 200 -> fulfillment).
4. Optional read-only live production endpoint probing (zero real charges, zero live mutations, zero Turnstile bypass).

Zero em-dashes (U+2014). Zero en-dashes (U+2013).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Tuple, Union
import urllib.error
import urllib.parse
import urllib.request

from pseofactory.contracts import assert_no_forbidden_dashes

FORBIDDEN_DIST_DELIVERABLE_TOKENS: Tuple[str, ...] = (
    "csv_content",
    "UNREDACTED_READY_FOR_FILING",
    "PH-EXEC-",
    "GH-EXEC-",
    "LB-EXEC-",
    "PX-EXEC-",
    "statutory_execution_artifacts",
)

_RAW_402_ANCHOR_RE = re.compile(
    r'<a\b[^>]*\bhref\s*=\s*["\'][^"\']*'
    r"(?:playbook=1[^\"']*format=(?:csv|datapack|datapack_json)|format=(?:csv|datapack|datapack_json)[^\"']*playbook=1)"
    r'[^"\']*["\']',
    re.IGNORECASE,
)

_RAW_402_URL_LITERAL_RE = re.compile(
    r'["\'`][^"\'`]*/api/(?:lead-capture|lead-fulfillment)[^"\'`]*'
    r"(?:playbook=1[^\"'`]*format=(?:csv|datapack|datapack_json)|format=(?:csv|datapack|datapack_json)[^\"'`]*playbook=1)"
    r'[^"\'`]*["\'`]',
    re.IGNORECASE,
)

_CANONICAL_OPERATOR_MAILBOX = "arif.coskun@profithelm.com"
_MONETIZATION_VAULT_PATH = Path(__file__).resolve().parent / "monetization_vault.json"


@dataclass
class CommerceGateReport:
    """Structured fail-closed commerce gate report for a single tenant."""

    property_id: str
    status: str
    passed: bool
    repo_root: str
    dist_dir: str
    static_leak_audit: Dict[str, Any] = field(default_factory=dict)
    pricing_parity: Dict[str, Any] = field(default_factory=dict)
    edge_replay: Dict[str, Any] = field(default_factory=dict)
    live_probe: Optional[Dict[str, Any]] = None
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _normalize_property_id(property_id: str) -> str:
    prop = str(property_id or "").strip().lower()
    if prop == "profithelm-platform":
        return "profithelm"
    return prop


def _read_pseofactory_marker(repo_root: Optional[Union[str, Path]]) -> Dict[str, Any]:
    if not repo_root:
        return {}
    marker = Path(repo_root) / ".pseofactory.json"
    if not marker.is_file():
        return {}
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _get_tenant_catalog_dynamic(
    property_id: str,
    repo_root: Optional[Union[str, Path]] = None,
) -> Dict[str, Dict[str, Any]]:
    from pseofactory import pricing

    prop = _normalize_property_id(property_id)
    edge_fn = getattr(pricing, "get_tenant_edge_pricing_catalog", None)
    if callable(edge_fn):
        try:
            cat = edge_fn(prop, repo_root=repo_root)
        except TypeError:
            cat = edge_fn(prop)
        if isinstance(cat, dict):
            if isinstance(cat.get("offers"), dict) and cat["offers"]:
                return cat["offers"]
            if cat and all(isinstance(v, dict) and "sku" in v for v in cat.values()):
                return cat
    return pricing.get_tenant_catalog(prop, repo_root=repo_root)


def _validate_sku_for_tenant(
    property_id: str,
    sku: str,
    repo_root: Optional[Union[str, Path]] = None,
) -> bool:
    from pseofactory import pricing

    prop = _normalize_property_id(property_id)
    validator = getattr(pricing, "validate_tenant_sku", None)
    if callable(validator):
        try:
            res = validator(prop, sku, repo_root=repo_root)
        except TypeError:
            res = validator(prop, sku)
        if isinstance(res, tuple):
            return bool(res[0])
        if isinstance(res, dict):
            return bool(res.get("valid") or res.get("ok"))
        return bool(res)
    norm = pricing.normalize_sku(sku)
    cat = _get_tenant_catalog_dynamic(prop, repo_root=repo_root)
    return bool(norm and norm in cat)


def _select_valid_tool_slug(
    property_id: str,
    dist_dir: Optional[Union[str, Path]],
    full_offer: Dict[str, Any],
) -> str:
    from pseofactory.affiliates import is_restricted_public_service_slug

    prop = _normalize_property_id(property_id)
    if dist_dir:
        tools_dir = Path(dist_dir) / "tools"
        if tools_dir.is_dir():
            for candidate_dir in sorted(tools_dir.iterdir()):
                if not candidate_dir.is_dir():
                    continue
                if not (candidate_dir / "index.html").is_file():
                    continue
                slug = candidate_dir.name.strip().lower()
                if not slug or slug == "partners":
                    continue
                if prop == "prexvo" and is_restricted_public_service_slug(slug):
                    continue
                if is_restricted_public_service_slug(slug):
                    continue
                return slug
    default_slug = str(full_offer.get("default_slug") or "").strip().lower()
    if default_slug and default_slug != "general" and not is_restricted_public_service_slug(default_slug):
        return default_slug
    return "general-calculator"


def resolve_tenant_commerce_matrix(
    property_id: str,
    repo_root: Optional[Union[str, Path]] = None,
    dist_dir: Optional[Union[str, Path]] = None,
    workspace_root: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """
    Dynamically resolves a tenant's pricing tiers (quick, full, partner_slot),
    valid commercial tool slug, foreign-tenant SKU, and foreign domains for 50+ sites.
    """
    from pseofactory import pricing

    prop = _normalize_property_id(property_id)
    eff_repo = Path(repo_root).resolve() if repo_root else None
    eff_dist = Path(dist_dir).resolve() if dist_dir else (eff_repo / "dist" if eff_repo else None)
    ws_root = Path(
        workspace_root or os.environ.get("WORKSPACE_ROOT", "/home/ubuntuadmin/projects")
    ).resolve()

    marker = _read_pseofactory_marker(eff_repo)
    catalog = _get_tenant_catalog_dynamic(prop, repo_root=eff_repo)
    if isinstance(catalog, dict) and isinstance(catalog.get("offers"), dict):
        catalog = catalog["offers"]
    if not isinstance(catalog, dict):
        catalog = {}

    quick_offer = pricing.resolve_offer_pricing(prop, tier_kind="quick", repo_root=eff_repo)
    full_offer = pricing.resolve_offer_pricing(prop, tier_kind="full", repo_root=eff_repo)
    partner_offer = pricing.resolve_offer_pricing(prop, tier_kind="partner_slot", repo_root=eff_repo)

    tier_overrides: Dict[str, Dict[str, Any]] = {}
    for item in catalog.values():
        if not isinstance(item, dict):
            continue
        tk = str(item.get("tier_kind") or "")
        if tk in ("quick", "full", "partner_slot") and item.get("sku") and tk not in tier_overrides:
            tier_overrides[tk] = dict(item)
    quick_offer = tier_overrides.get("quick", quick_offer)
    full_offer = tier_overrides.get("full", full_offer)
    partner_offer = tier_overrides.get("partner_slot", partner_offer)

    valid_tool_slug = _select_valid_tool_slug(prop, eff_dist, full_offer)

    # Pick a canonical SKU owned by a different tenant for cross-tenant rejection tests.
    foreign_sku = ""
    for candidate_sku, candidate_spec in pricing.OFFER_CATALOG.items():
        if _normalize_property_id(str(candidate_spec.get("property_id") or "")) != prop:
            foreign_sku = str(candidate_sku)
            break
    if not foreign_sku:
        foreign_sku = "px_instant_repayment_worksheet_19" if prop != "prexvo" else "ph_instant_statutory_worksheet_19"

    own_domain = str(marker.get("domain") or "").strip().lower()
    canonical_base = str(marker.get("canonical_base") or "").strip()
    if not own_domain and canonical_base:
        own_domain = (urllib.parse.urlsplit(canonical_base).hostname or "").lower()
    if not own_domain:
        try:
            from pseofactory.tenant_facts import (
                CANONICAL_TENANT_DECLARATIONS,
                SPAWNED_TENANT_DECLARATIONS,
            )

            decl = CANONICAL_TENANT_DECLARATIONS.get(prop) or SPAWNED_TENANT_DECLARATIONS.get(prop)
            if decl and getattr(decl, "canonical_base", ""):
                own_domain = (urllib.parse.urlsplit(decl.canonical_base).hostname or "").lower()
                if not canonical_base:
                    canonical_base = str(decl.canonical_base)
        except Exception:
            pass
    if not own_domain:
        own_domain = f"{prop}.com"
    if not canonical_base:
        canonical_base = f"https://{own_domain}"

    foreign_domains: List[str] = []
    seen_domains = {own_domain}
    try:
        from pseofactory.impact_planner import discover_active_tenants

        for other_id, other_repo in discover_active_tenants(ws_root):
            if _normalize_property_id(other_id) == prop:
                continue
            other_marker = _read_pseofactory_marker(other_repo)
            other_dom = str(other_marker.get("domain") or "").strip().lower()
            if not other_dom and other_marker.get("canonical_base"):
                other_dom = (urllib.parse.urlsplit(str(other_marker["canonical_base"])).hostname or "").lower()
            if other_dom and other_dom not in seen_domains:
                seen_domains.add(other_dom)
                foreign_domains.append(other_dom)
    except Exception:
        pass

    try:
        from pseofactory.tenant_facts import (
            CANONICAL_TENANT_DECLARATIONS,
            SPAWNED_TENANT_DECLARATIONS,
        )

        for other_id, decl in {**CANONICAL_TENANT_DECLARATIONS, **SPAWNED_TENANT_DECLARATIONS}.items():
            if _normalize_property_id(other_id) == prop:
                continue
            cbase = str(getattr(decl, "canonical_base", "") or "")
            odom = (urllib.parse.urlsplit(cbase).hostname or "").lower() if cbase else ""
            if odom and odom not in seen_domains:
                seen_domains.add(odom)
                foreign_domains.append(odom)
    except Exception:
        pass

    return {
        "property_id": prop,
        "own_domain": own_domain,
        "canonical_base": canonical_base.rstrip("/"),
        "foreign_domains": sorted(foreign_domains),
        "audience_tier": pricing.get_audience_tier(prop, repo_root=eff_repo),
        "catalog": catalog,
        "tiers": {
            "quick": {
                "tier_kind": "quick",
                "sku": str(quick_offer["sku"]),
                "price_cents": int(quick_offer["price_cents"]),
                "price_usd": float(quick_offer["price_usd"]),
                "tool_slug": valid_tool_slug,
            },
            "full": {
                "tier_kind": "full",
                "sku": str(full_offer["sku"]),
                "price_cents": int(full_offer["price_cents"]),
                "price_usd": float(full_offer["price_usd"]),
                "tool_slug": valid_tool_slug,
            },
            "partner_slot": {
                "tier_kind": "partner_slot",
                "sku": str(partner_offer["sku"]),
                "price_cents": int(partner_offer["price_cents"]),
                "price_usd": float(partner_offer["price_usd"]),
                "tool_slug": "partners",
            },
        },
        "valid_tool_slug": valid_tool_slug,
        "foreign_sku": foreign_sku,
    }


def _collect_dist_scan_targets(dist_path: Path) -> List[Path]:
    targets: Dict[str, Path] = {}

    def _add(p: Path) -> None:
        if p.is_file():
            targets[str(p.resolve())] = p

    for p in dist_path.glob("**/*.html"):
        _add(p)
    for rel_json in ("catalog.json", "media-kit.json"):
        _add(dist_path / rel_json)
    for folder in ("manifests", "ai-benchmarks"):
        fdir = dist_path / folder
        if fdir.is_dir():
            for p in fdir.glob("**/*.json"):
                _add(p)
    static_js = dist_path / "static" / "js"
    if static_js.is_dir():
        for p in static_js.glob("**/*.js"):
            _add(p)

    return [targets[k] for k in sorted(targets)]


def audit_static_dist_deliverable_leaks(
    dist_dir: Union[str, Path],
    property_id: str,
) -> Dict[str, Any]:
    """
    Scans dist/ (*.html, manifests/*.json, catalog.json, media-kit.json,
    ai-benchmarks/*.json, static/js/*.js) and fails closed if any paid
    deliverable leak or raw HTTP 402 free-preview CSV/datapack anchor appears.
    """
    from pseofactory import pricing

    prop = _normalize_property_id(property_id)
    dist_path = Path(dist_dir)
    if not dist_path.is_dir():
        return {
            "status": "FAIL",
            "passed": False,
            "property_id": prop,
            "dist_dir": str(dist_path),
            "files_scanned": 0,
            "violations_count": 1,
            "violations": [f"Missing dist directory: {dist_path}"],
        }

    prefix = str(pricing.TENANT_SKU_PREFIX.get(prop, "") or "").strip().upper()
    dyn_exec_re = (
        re.compile(rf"\b{re.escape(prefix)}-EXEC-\d+")
        if prefix and prefix not in ("PH", "GH", "LB", "PX") and len(prefix) >= 2 and prefix.isalnum()
        else None
    )

    files = _collect_dist_scan_targets(dist_path)
    violations: List[str] = []
    for fpath in files:
        rel = fpath.relative_to(dist_path).as_posix()
        try:
            text = fpath.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            violations.append(f"{rel}: unreadable dist artifact ({exc})")
            continue

        for tok in FORBIDDEN_DIST_DELIVERABLE_TOKENS:
            if tok in text:
                violations.append(f"{rel}: leaked paid deliverable token '{tok}'")

        if dyn_exec_re and dyn_exec_re.search(text):
            violations.append(f"{rel}: leaked dynamic execution artifact prefix '{prefix}-EXEC-'")

        for anchor_m in _RAW_402_ANCHOR_RE.finditer(text):
            violations.append(
                f"{rel}: stale raw HTTP 402 free-preview CSV/datapack anchor: {anchor_m.group(0)[:140]}"
            )

        for lit_m in _RAW_402_URL_LITERAL_RE.finditer(text):
            violations.append(
                f"{rel}: raw HTTP 402 free-preview CSV/datapack URL literal: {lit_m.group(0)[:140]}"
            )

    return {
        "status": "PASS" if not violations else "FAIL",
        "passed": len(violations) == 0,
        "property_id": prop,
        "dist_dir": str(dist_path),
        "files_scanned": len(files),
        "violations_count": len(violations),
        "violations": violations,
    }


def _verify_dist_route_resolves(dist_dir: Path, raw_url: str) -> Tuple[bool, str, str]:
    """Checks that a success_url or cancel_url pathname resolves to a real file in dist_dir."""
    parsed = urllib.parse.urlsplit(str(raw_url or ""))
    pathname = parsed.path or "/"
    if not pathname.startswith("/"):
        pathname = "/" + pathname
    rel = pathname.lstrip("/")
    candidates: List[Path] = []
    if not rel:
        candidates.append(dist_dir / "index.html")
    else:
        candidates.append(dist_dir / rel / "index.html")
        candidates.append(dist_dir / rel)
        if not rel.endswith(".html"):
            candidates.append(dist_dir / f"{rel.rstrip('/')}.html")
    for cand in candidates:
        if cand.is_file():
            return True, pathname, cand.relative_to(dist_dir).as_posix()
    return False, pathname, ""


def _build_node_replay_script(config: Dict[str, Any]) -> str:
    """
    Constructs a self-contained Node.js v22 ESM replay script.
    Runs in an isolated child process per tenant so globalThis buffers never leak.
    Zero em-dashes. Zero en-dashes.
    """
    cfg_json = json.dumps(config)
    script = """import crypto from "node:crypto";
import { pathToFileURL } from "node:url";

const CFG = __CFG_JSON__;

function makeKv() {
  const store = new Map();
  const metaStore = new Map();
  return {
    async get(key, opts) {
      if (!store.has(key)) return null;
      const val = store.get(key);
      if (opts && opts.type === "json") {
        return typeof val === "string" ? JSON.parse(val) : val;
      }
      return val;
    },
    async put(key, val, opts) {
      store.set(key, typeof val === "string" ? val : JSON.stringify(val));
      if (opts && opts.metadata) {
        metaStore.set(key, opts.metadata);
      }
    },
    async list(opts = {}) {
      const prefix = String(opts.prefix || "");
      const limit = Number(opts.limit || 1000);
      const keys = [];
      for (const name of store.keys()) {
        if (prefix && !name.startsWith(prefix)) continue;
        const entry = { name };
        if (metaStore.has(name)) entry.metadata = metaStore.get(name);
        keys.push(entry);
        if (keys.length >= limit) break;
      }
      return { keys };
    },
    _keys() {
      return Array.from(store.keys());
    },
  };
}

function unescapeHtmlAttr(val) {
  return String(val || "")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
}

function extractEmailLinks(htmlBody) {
  const links = [];
  const re = /href\\s*=\\s*["']([^"']+)["']/gi;
  let m;
  while ((m = re.exec(String(htmlBody || ""))) !== null) {
    links.push(unescapeHtmlAttr(m[1]));
  }
  return links;
}

function hasNonEmptyFreeLeak(obj) {
  if (!obj || typeof obj !== "object") return [];
  const leaks = [];
  if (typeof obj.csv_content === "string" && obj.csv_content.length > 0) {
    leaks.push("csv_content");
  }
  for (const key of ["period_schedule", "statutory_trend_timeseries", "sensitivity_matrix"]) {
    if (Array.isArray(obj[key]) && obj[key].length > 0) {
      leaks.push(key);
    }
  }
  if (obj.statutory_data_pack && typeof obj.statutory_data_pack === "object") {
    for (const subLeak of hasNonEmptyFreeLeak(obj.statutory_data_pack)) {
      leaks.push("statutory_data_pack." + subLeak);
    }
  }
  return leaks;
}

async function readJsonSafe(resp) {
  const text = await resp.text();
  let json = null;
  try {
    json = JSON.parse(text);
  } catch (_) {}
  return { status: resp.status, text, json };
}

function signStripeWebhook(secret, rawBody) {
  const ts = String(Math.floor(Date.now() / 1000));
  const sig = crypto.createHmac("sha256", secret).update(`${ts}.${rawBody}`).digest("hex");
  return `t=${ts},v1=${sig}`;
}

async function main() {
  const issues = [];
  const details = {
    property_id: CFG.property_id,
    invalid_sku_checks: {},
    isolation_checks: {},
    prexvo_ymyl_checks: {},
    tier_replays: {},
  };

  const leadCaptureMod = await import(pathToFileURL(CFG.files.lead_capture).href);
  const checkoutMod = await import(pathToFileURL(CFG.files.checkout).href);
  const webhookMod = await import(pathToFileURL(CFG.files.stripe_webhook).href);
  const fulfillmentMod = await import(pathToFileURL(CFG.files.lead_fulfillment).href);

  const kv = makeKv();
  const ephemeralNonce = crypto.randomBytes(12).toString("hex");
  const webhookSecret = ["whsec", "replay", ephemeralNonce].join("_");
  const kvBinding = CFG.property_id.toUpperCase().replace(/[^A-Z0-9]/g, "_") + "_LEADS";
  const env = {
    [kvBinding]: kv,
    LEADS_KV: kv,
    LEADS: kv,
    STRIPE_SECRET_KEY: ["sk", "live", "replay", ephemeralNonce].join("_"),
    STRIPE_WEBHOOK_SECRET: webhookSecret,
    ZEPTOMAIL_TOKEN: ["Zoho-enczapikey", "replay_" + ephemeralNonce].join(" "),
    ZEPTOMAIL_FROM_EMAIL: "arif.coskun@profithelm.com",
    ZOHO_FROM_EMAIL: "arif.coskun@profithelm.com",
    EMAIL_PRIMARY_RAIL: "zeptomail",
    TELEMETRY_EXPORT_SECRET: ["replay", "telemetry", ephemeralNonce].join("_"),
  };

  const stripeCreates = [];
  const stripeSessions = new Map();
  const dispatchedEmails = [];
  let sessionSeq = 0;

  globalThis.fetch = async (url, init = {}) => {
    const u = String(url || "");
    if (u.endsWith("/v1/checkout/sessions") && String(init.method || "GET").toUpperCase() === "POST") {
      const params = new URLSearchParams(String(init.body || ""));
      const metadata = {};
      for (const [k, v] of params.entries()) {
        const mm = k.match(/^metadata\\[(.+)\\]$/);
        if (mm) metadata[mm[1]] = v;
      }
      sessionSeq += 1;
      const sid = `cs_live_replay_${CFG.property_id}_${sessionSeq}`;
      const unitAmount = Number(params.get("line_items[0][price_data][unit_amount]") || 0);
      const sess = {
        id: sid,
        url: `https://checkout.stripe.com/c/pay/${sid}`,
        livemode: true,
        payment_status: "unpaid",
        status: "open",
        amount_total: unitAmount,
        unit_amount: unitAmount,
        currency: params.get("line_items[0][price_data][currency]") || "usd",
        success_url: params.get("success_url") || "",
        cancel_url: params.get("cancel_url") || "",
        client_reference_id: params.get("client_reference_id") || metadata.lead_id || "",
        customer_details: { email: params.get("customer_email") || "" },
        metadata,
      };
      stripeSessions.set(sid, sess);
      stripeCreates.push(sess);
      return new Response(JSON.stringify({ id: sid, url: sess.url, livemode: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    const lookupMatch = u.match(/api\\.stripe\\.com\\/v1\\/checkout\\/sessions\\/([^?]+)/);
    if (lookupMatch) {
      const sid = decodeURIComponent(lookupMatch[1]);
      const sess = stripeSessions.get(sid);
      if (!sess) {
        return new Response(JSON.stringify({ error: { code: "resource_missing" } }), {
          status: 404,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify(sess), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (u.includes("zeptomail") && u.includes("/email")) {
      const payload = JSON.parse(String(init.body || "{}"));
      const toAddr =
        (payload.to && payload.to[0] && payload.to[0].email_address && payload.to[0].email_address.address) || "";
      dispatchedEmails.push({
        provider: "zeptomail",
        to: toAddr,
        subject: payload.subject || "",
        htmlBody: payload.htmlbody || "",
      });
      return new Response(JSON.stringify({ request_id: `zp_${dispatchedEmails.length}` }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (u.includes("api.nango.dev/connection")) {
      return new Response(JSON.stringify({ credentials: { access_token: "zoho_replay_" + ephemeralNonce } }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (u.includes("mail.zoho.com/api/accounts/")) {
      const payload = JSON.parse(String(init.body || "{}"));
      dispatchedEmails.push({
        provider: "zoho",
        to: payload.toAddress || "",
        subject: payload.subject || "",
        htmlBody: payload.content || "",
      });
      return new Response(JSON.stringify({ status: { code: 200 }, data: { messageId: `zoho_${dispatchedEmails.length}` } }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response("{}", { status: 404 });
  };

  async function callLocal(rawPath, method = "GET", body = null, headers = {}) {
    const u = new URL(rawPath, CFG.canonical_base);
    const reqInit = { method, headers: { ...headers } };
    if (body !== null) reqInit.body = body;
    const req = new Request(u.toString(), reqInit);
    const ctx = { request: req, env };
    const p = u.pathname;
    if (p === "/api/checkout") {
      return method === "POST" ? checkoutMod.onRequestPost(ctx) : checkoutMod.onRequestGet(ctx);
    }
    if (p === "/api/lead-fulfillment") {
      return method === "POST" ? fulfillmentMod.onRequestPost(ctx) : fulfillmentMod.onRequestGet(ctx);
    }
    if (p === "/api/stripe-webhook") {
      return webhookMod.onRequestPost(ctx);
    }
    if (p === "/api/lead-capture") {
      return method === "POST" ? leadCaptureMod.onRequestPost(ctx) : leadCaptureMod.onRequestGet(ctx);
    }
    return new Response(JSON.stringify({ ok: false, error: "unknown_local_route:" + p }), { status: 404 });
  }

  // 1. Invalid & cross-tenant SKU fail-closed (HTTP 400, zero Stripe sessions)
  const beforeInvalidCount = stripeCreates.length;
  const badSkuRes = await readJsonSafe(
    await callLocal(`/api/checkout?format=json&sku=nonexistent_sku_xyz&tool_slug=${encodeURIComponent(CFG.valid_tool_slug)}`)
  );
  details.invalid_sku_checks.unknown_sku_status = badSkuRes.status;
  if (badSkuRes.status !== 400) {
    issues.push(`Unknown SKU nonexistent_sku_xyz expected HTTP 400, got ${badSkuRes.status}`);
  }
  const foreignSkuRes = await readJsonSafe(
    await callLocal(`/api/checkout?format=json&sku=${encodeURIComponent(CFG.foreign_sku)}&tool_slug=${encodeURIComponent(CFG.valid_tool_slug)}`)
  );
  details.invalid_sku_checks.foreign_sku = CFG.foreign_sku;
  details.invalid_sku_checks.foreign_sku_status = foreignSkuRes.status;
  if (foreignSkuRes.status !== 400) {
    issues.push(`Foreign-tenant SKU ${CFG.foreign_sku} expected HTTP 400, got ${foreignSkuRes.status}`);
  }
  if (stripeCreates.length !== beforeInvalidCount) {
    issues.push(`Invalid/foreign SKU created ${stripeCreates.length - beforeInvalidCount} Stripe session(s)`);
  }

  // 2. Free-vs-Paid Isolation
  const pbRes = await readJsonSafe(
    await callLocal(`/api/lead-capture?playbook=1&tool_slug=${encodeURIComponent(CFG.valid_tool_slug)}`)
  );
  details.isolation_checks.playbook_status = pbRes.status;
  if (pbRes.status !== 200) {
    issues.push(`Unpaid GET /api/lead-capture?playbook=1 expected HTTP 200, got ${pbRes.status}`);
  } else {
    const leaks = hasNonEmptyFreeLeak(pbRes.json);
    details.isolation_checks.playbook_leaks = leaks;
    if (leaks.length > 0) {
      issues.push(`Unpaid ?playbook=1 leaked paid fields: ${leaks.join(", ")}`);
    }
  }

  const pbCsvRes = await readJsonSafe(
    await callLocal(`/api/lead-capture?playbook=1&tool_slug=${encodeURIComponent(CFG.valid_tool_slug)}&format=csv`)
  );
  details.isolation_checks.playbook_csv_status = pbCsvRes.status;
  if (pbCsvRes.status !== 402) {
    issues.push(`Unpaid ?playbook=1&format=csv expected HTTP 402, got ${pbCsvRes.status}`);
  }

  const pbDpRes = await readJsonSafe(
    await callLocal(`/api/lead-capture?playbook=1&tool_slug=${encodeURIComponent(CFG.valid_tool_slug)}&format=datapack`)
  );
  details.isolation_checks.playbook_datapack_status = pbDpRes.status;
  if (pbDpRes.status !== 402) {
    issues.push(`Unpaid ?playbook=1&format=datapack expected HTTP 402, got ${pbDpRes.status}`);
  }

  const ffNoSidRes = await readJsonSafe(await callLocal("/api/lead-fulfillment"));
  details.isolation_checks.fulfillment_no_sid_status = ffNoSidRes.status;
  if (ffNoSidRes.status !== 402) {
    issues.push(`Unpaid GET /api/lead-fulfillment (no session_id) expected HTTP 402, got ${ffNoSidRes.status}`);
  }

  const ffFakeSidRes = await readJsonSafe(
    await callLocal(`/api/lead-fulfillment?session_id=cs_live_fake123&tool_slug=${encodeURIComponent(CFG.valid_tool_slug)}`)
  );
  details.isolation_checks.fulfillment_fake_sid_status = ffFakeSidRes.status;
  if (ffFakeSidRes.status !== 402) {
    issues.push(`Unpaid GET /api/lead-fulfillment?session_id=cs_live_fake123 expected HTTP 402, got ${ffFakeSidRes.status}`);
  }

  if (CFG.property_id === "prexvo") {
    const pslfSlug = "pslf-buyback-months-reconsideration-student-loan-calculator";
    const pslfChk = await readJsonSafe(
      await callLocal(`/api/checkout?format=json&sku=${encodeURIComponent(CFG.tiers.quick.sku)}&tool_slug=${pslfSlug}`)
    );
    const pslfPb = await readJsonSafe(
      await callLocal(`/api/lead-capture?playbook=1&tool_slug=${pslfSlug}`)
    );
    details.prexvo_ymyl_checks = {
      checkout_status: pslfChk.status,
      playbook_status: pslfPb.status,
    };
    if (pslfChk.status !== 400) {
      issues.push(`Prexvo restricted YMYL slug /api/checkout expected HTTP 400, got ${pslfChk.status}`);
    }
    if (pslfPb.status !== 400) {
      issues.push(`Prexvo restricted YMYL slug ?playbook=1 expected HTTP 400, got ${pslfPb.status}`);
    }
  }

  // 3. Full E2E Purchase Replay across ALL 3 Tiers (quick, full, partner_slot)
  for (const tierName of ["quick", "full", "partner_slot"]) {
    const spec = CFG.tiers[tierName];
    const tierRep = {
      sku: spec.sku,
      expected_cents: spec.price_cents,
      tool_slug: spec.tool_slug,
    };

    // Step A: Checkout
    const chkStartCount = stripeCreates.length;
    const chkRes = await readJsonSafe(
      await callLocal(
        `/api/checkout?format=json&sku=${encodeURIComponent(spec.sku)}&tool_slug=${encodeURIComponent(spec.tool_slug)}`
      )
    );
    tierRep.checkout_status = chkRes.status;
    if (chkRes.status !== 200 || !chkRes.json || !chkRes.json.checkout_session_id) {
      issues.push(`[${tierName}] GET /api/checkout failed: HTTP ${chkRes.status}`);
      details.tier_replays[tierName] = tierRep;
      continue;
    }
    if (stripeCreates.length !== chkStartCount + 1) {
      issues.push(`[${tierName}] expected 1 Stripe session created, got ${stripeCreates.length - chkStartCount}`);
      details.tier_replays[tierName] = tierRep;
      continue;
    }
    const createdSess = stripeCreates[stripeCreates.length - 1];
    tierRep.unit_amount = createdSess.unit_amount;
    tierRep.session_id = createdSess.id;
    tierRep.success_url = createdSess.success_url || chkRes.json.success_url || "";
    tierRep.cancel_url = createdSess.cancel_url || chkRes.json.cancel_url || "";
    tierRep.lead_id = chkRes.json.lead_id || createdSess.client_reference_id || "";

    if (createdSess.unit_amount !== spec.price_cents) {
      issues.push(`[${tierName}] Stripe unit_amount ${createdSess.unit_amount} != expected ${spec.price_cents}`);
    }
    if (chkRes.json.offer_sku !== spec.sku) {
      issues.push(`[${tierName}] checkout offer_sku '${chkRes.json.offer_sku}' != expected '${spec.sku}'`);
    }
    if (!tierRep.success_url || !tierRep.cancel_url) {
      issues.push(`[${tierName}] missing success_url or cancel_url on Stripe session`);
    }

    // Step B: Signed Webhook -> KV -> Duplicate check -> Email inspection
    createdSess.payment_status = "paid";
    createdSess.status = "complete";
    createdSess.customer_details = { email: "buyer@example-client.com" };
    if (tierName === "partner_slot") {
      createdSess.metadata.firm_name = "Acme Advisory LLP";
    }

    const whMeta = {
      property_id: CFG.property_id,
      lead_id: tierRep.lead_id,
      tool_slug: spec.tool_slug,
      offer_sku: spec.sku,
      ...(tierName === "partner_slot" ? { firm_name: "Acme Advisory LLP" } : {}),
    };
    const whBody = JSON.stringify({
      id: `evt_replay_${CFG.property_id}_${tierName}`,
      type: "checkout.session.completed",
      data: {
        object: {
          id: createdSess.id,
          payment_status: "paid",
          status: "complete",
          amount_total: spec.price_cents,
          currency: "usd",
          livemode: true,
          client_reference_id: tierRep.lead_id,
          customer_details: { email: "buyer@example-client.com" },
          metadata: whMeta,
        },
      },
    });
    const whSig = signStripeWebhook(webhookSecret, whBody);
    const emailCountBefore = dispatchedEmails.length;

    const wh1 = await readJsonSafe(
      await callLocal("/api/stripe-webhook", "POST", whBody, {
        "Content-Type": "application/json",
        "Stripe-Signature": whSig,
      })
    );
    tierRep.webhook_status = wh1.status;
    tierRep.webhook_email_dispatched = Boolean(wh1.json && wh1.json.email_dispatched);
    if (wh1.status !== 200 || !wh1.json || wh1.json.ok !== true) {
      issues.push(`[${tierName}] signed POST /api/stripe-webhook failed: HTTP ${wh1.status}`);
    }
    if (!tierRep.webhook_email_dispatched || dispatchedEmails.length !== emailCountBefore + 1) {
      issues.push(`[${tierName}] webhook did not dispatch fulfillment email exactly once`);
    }

    // Verify KV record persisted
    const kvRec = await kv.get(tierRep.lead_id, { type: "json" });
    tierRep.kv_persisted = Boolean(kvRec && kvRec.settled === true && kvRec.stripe_payment_verified === true);
    if (!tierRep.kv_persisted) {
      issues.push(`[${tierName}] KV record for ${tierRep.lead_id} missing settled=true / stripe_payment_verified=true`);
    }

    // Duplicate webhook replay
    const wh2 = await readJsonSafe(
      await callLocal("/api/stripe-webhook", "POST", whBody, {
        "Content-Type": "application/json",
        "Stripe-Signature": whSig,
      })
    );
    tierRep.duplicate_webhook_status = wh2.status;
    tierRep.duplicate_email_dispatched = Boolean(wh2.json && wh2.json.email_dispatched);
    if (wh2.status !== 200 || tierRep.duplicate_email_dispatched !== false || dispatchedEmails.length !== emailCountBefore + 1) {
      issues.push(`[${tierName}] duplicate webhook dispatched duplicate email or returned non-200`);
    }

    // Validate intercepted email links & copy
    if (dispatchedEmails.length > emailCountBefore) {
      const emailObj = dispatchedEmails[dispatchedEmails.length - 1];
      const emailHtml = String(emailObj.htmlBody || "");
      const emailLinks = extractEmailLinks(emailHtml);
      const fulfillmentLinks = emailLinks.filter(
        (lnk) => lnk.includes("/api/lead-fulfillment") || (lnk.includes("/api/lead-capture") && lnk.includes("fulfill=1"))
      );
      tierRep.email_links_count = fulfillmentLinks.length;
      if (fulfillmentLinks.length === 0) {
        issues.push(`[${tierName}] fulfillment email contained zero fulfillment links`);
      }

      const linkStatuses = [];
      for (const fl of fulfillmentLinks) {
        const lResp = await callLocal(fl);
        linkStatuses.push({ url: fl, status: lResp.status });
        if (lResp.status !== 200) {
          issues.push(`[${tierName}] email link returned HTTP ${lResp.status}: ${fl}`);
        }
      }
      tierRep.email_link_statuses = linkStatuses;

      if (tierName === "quick") {
        if (emailHtml.includes("format=datapack")) {
          issues.push("[quick] fulfillment email leaked format=datapack link");
        }
        const apiFulfillLinks = emailLinks.filter((lnk) => lnk.includes("/api/lead-fulfillment"));
        if (apiFulfillLinks.length === 0) {
          issues.push("[quick] fulfillment email missing /api/lead-fulfillment link");
        }
      } else if (tierName === "full") {
        for (const reqFmt of ["format=html", "format=csv", "format=datapack"]) {
          if (!fulfillmentLinks.some((lnk) => lnk.includes(reqFmt))) {
            issues.push(`[full] fulfillment email missing ${reqFmt} link`);
          }
        }
      } else if (tierName === "partner_slot") {
        if (!emailHtml.includes("Acme Advisory LLP")) {
          issues.push("[partner_slot] fulfillment email missing firm_name 'Acme Advisory LLP'");
        }
        if (emailHtml.includes("format=csv") || emailHtml.includes("format=datapack")) {
          issues.push("[partner_slot] fulfillment email leaked format=csv or format=datapack link");
        }
        const decodedEmail = unescapeHtmlAttr(emailHtml);
        if (decodedEmail.includes("Workpaper & Statutory Data Pack")) {
          issues.push("[partner_slot] fulfillment email leaked 'Workpaper & Statutory Data Pack' copy");
        }
      }
    }

    // Step C: Paid GET /api/lead-fulfillment?session_id=<sid>&sku=<sku>&tool_slug=<slug>
    const ffBase = `/api/lead-fulfillment?session_id=${encodeURIComponent(createdSess.id)}&sku=${encodeURIComponent(spec.sku)}&tool_slug=${encodeURIComponent(spec.tool_slug)}`;
    const ffJson = await readJsonSafe(await callLocal(ffBase));
    const ffHtml = await callLocal(`${ffBase}&format=html`);
    const ffHtmlTxt = await ffHtml.text();

    tierRep.fulfillment_json_status = ffJson.status;
    tierRep.fulfillment_html_status = ffHtml.status;
    if (ffJson.status !== 200) {
      issues.push(`[${tierName}] paid GET /api/lead-fulfillment (json) expected 200, got ${ffJson.status}`);
    }
    if (ffHtml.status !== 200) {
      issues.push(`[${tierName}] paid GET /api/lead-fulfillment (html) expected 200, got ${ffHtml.status}`);
    }

    if (tierName === "quick") {
      const topDpUrl = ffJson.json && ffJson.json.datapack_url;
      const attrDpUrl = ffJson.json && ffJson.json.settlement_attribution && ffJson.json.settlement_attribution.datapack_url;
      if (topDpUrl || attrDpUrl) {
        issues.push("[quick] paid fulfillment json leaked truthy datapack_url");
      }
      const ffCsv = await callLocal(`${ffBase}&format=csv`);
      const ffDp = await callLocal(`${ffBase}&format=datapack`);
      tierRep.fulfillment_csv_status = ffCsv.status;
      tierRep.fulfillment_datapack_status = ffDp.status;
      if (ffCsv.status !== 200) {
        issues.push(`[quick] paid GET /api/lead-fulfillment (csv) expected 200, got ${ffCsv.status}`);
      }
      if (ffDp.status !== 402) {
        issues.push(`[quick] paid GET /api/lead-fulfillment (datapack) expected 402, got ${ffDp.status}`);
      }
    } else if (tierName === "full") {
      const ffCsv = await callLocal(`${ffBase}&format=csv`);
      const ffDp = await callLocal(`${ffBase}&format=datapack`);
      tierRep.fulfillment_csv_status = ffCsv.status;
      tierRep.fulfillment_datapack_status = ffDp.status;
      if (ffCsv.status !== 200) {
        issues.push(`[full] paid GET /api/lead-fulfillment (csv) expected 200, got ${ffCsv.status}`);
      }
      if (ffDp.status !== 200) {
        issues.push(`[full] paid GET /api/lead-fulfillment (datapack) expected 200, got ${ffDp.status}`);
      }
    } else if (tierName === "partner_slot") {
      if (!ffHtmlTxt.includes("Acme Advisory LLP")) {
        issues.push("[partner_slot] paid HTML receipt missing firm_name 'Acme Advisory LLP'");
      }
    }

    details.tier_replays[tierName] = tierRep;
  }

  console.log(JSON.stringify({
    passed: issues.length === 0,
    issues,
    details,
  }));
}

main().catch((err) => {
  console.log(JSON.stringify({
    passed: false,
    issues: ["node_replay_uncaught_exception:" + String(err && err.stack ? err.stack : err)],
    details: {},
  }));
  process.exit(1);
});
"""
    return script.replace("__CFG_JSON__", cfg_json)


def verify_local_edge_commerce_replay(
    repo_root: Union[str, Path],
    property_id: str,
    dist_dir: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """
    Spawns an isolated Node.js v22 subprocess importing functions/api/{checkout,lead-capture,
    stripe-webhook,lead-fulfillment}.js with an in-memory KV and mocked Stripe/email fetch harness
    to prove SKU validation, paywall isolation, and full 3-tier E2E purchase replay.
    """
    prop = _normalize_property_id(property_id)
    repo_path = Path(repo_root).resolve()
    api_dir = repo_path / "functions" / "api"
    required_files = {
        "lead_capture": api_dir / "lead-capture.js",
        "checkout": api_dir / "checkout.js",
        "stripe_webhook": api_dir / "stripe-webhook.js",
        "lead_fulfillment": api_dir / "lead-fulfillment.js",
    }
    missing = [str(p) for p in required_files.values() if not p.is_file()]
    if missing:
        return {
            "status": "FAIL",
            "passed": False,
            "property_id": prop,
            "repo_root": str(repo_path),
            "issues": [f"Missing edge function file(s): {', '.join(missing)}"],
            "details": {},
        }

    node_bin = shutil.which("node")
    if not node_bin:
        return {
            "status": "FAIL",
            "passed": False,
            "property_id": prop,
            "repo_root": str(repo_path),
            "issues": ["node binary unavailable for local edge commerce replay"],
            "details": {},
        }

    eff_dist = Path(dist_dir).resolve() if dist_dir is not None else (repo_path / "dist" if (repo_path / "dist").is_dir() else None)
    matrix = resolve_tenant_commerce_matrix(prop, repo_root=repo_path, dist_dir=eff_dist)
    node_cfg = {
        "property_id": prop,
        "canonical_base": matrix["canonical_base"],
        "valid_tool_slug": matrix["valid_tool_slug"],
        "foreign_sku": matrix["foreign_sku"],
        "tiers": matrix["tiers"],
        "files": {k: str(v.resolve()) for k, v in required_files.items()},
    }
    node_script = _build_node_replay_script(node_cfg)
    assert_no_forbidden_dashes(node_script, context=f"commerce_gate.node_replay({prop})")

    try:
        proc = subprocess.run(
            [node_bin, "--input-type=module", "-"],
            input=node_script,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except Exception as exc:
        return {
            "status": "FAIL",
            "passed": False,
            "property_id": prop,
            "repo_root": str(repo_path),
            "issues": [f"Node edge replay subprocess failed: {exc}"],
            "details": {},
        }

    lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
    if not lines:
        return {
            "status": "FAIL",
            "passed": False,
            "property_id": prop,
            "repo_root": str(repo_path),
            "issues": [f"Node edge replay produced no output (rc={proc.returncode}): {(proc.stderr or '').strip()}"],
            "details": {},
        }

    try:
        parsed = json.loads(lines[-1])
    except Exception as exc:
        return {
            "status": "FAIL",
            "passed": False,
            "property_id": prop,
            "repo_root": str(repo_path),
            "issues": [f"Failed to parse Node edge replay JSON ({exc}): {lines[-1][:200]}"],
            "details": {},
        }

    issues = list(parsed.get("issues") or [])
    details = parsed.get("details") if isinstance(parsed.get("details"), dict) else {}
    tier_replays = details.get("tier_replays") if isinstance(details.get("tier_replays"), dict) else {}

    # Validate success_url and cancel_url pathnames against dist_dir and partner_slot /partners/ invariant.
    for tier_name in ("quick", "full", "partner_slot"):
        t_rep = tier_replays.get(tier_name)
        if not isinstance(t_rep, dict):
            continue
        for url_field in ("success_url", "cancel_url"):
            raw_u = str(t_rep.get(url_field) or "")
            if not raw_u:
                continue
            parsed_u = urllib.parse.urlsplit(raw_u)
            u_path = parsed_u.path or "/"
            if tier_name == "partner_slot":
                if "/tools/partners" in u_path or u_path not in ("/partners/", "/partners", "/partners/index.html"):
                    issues.append(
                        f"[partner_slot] {url_field} pathname '{u_path}' must resolve to /partners/ (never /tools/partners/)"
                    )
            if eff_dist is not None and eff_dist.is_dir():
                resolved_ok, norm_p, disk_rel = _verify_dist_route_resolves(eff_dist, raw_u)
                t_rep[f"{url_field}_dist_resolved"] = resolved_ok
                t_rep[f"{url_field}_dist_file"] = disk_rel
                if not resolved_ok:
                    issues.append(f"[{tier_name}] {url_field} pathname '{norm_p}' does not resolve to any file in {eff_dist}")

    if proc.returncode != 0 and not issues:
        issues.append(f"Node edge replay exited with code {proc.returncode}: {(proc.stderr or '').strip()}")

    passed = len(issues) == 0 and proc.returncode == 0
    return {
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        "property_id": prop,
        "repo_root": str(repo_path),
        "dist_dir": str(eff_dist) if eff_dist else "",
        "issues": issues,
        "details": details,
    }


def _http_probe(
    url: str,
    method: str = "GET",
    body: Optional[bytes] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 15.0,
) -> Tuple[int, str, Optional[Dict[str, Any]]]:
    hdrs = {"User-Agent": "pseofactory-commerce-gate/1.0"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    code = 0
    text = ""
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.getcode()
            text = resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as he:
        code = he.code
        try:
            text = he.read().decode("utf-8", errors="ignore")
        except Exception:
            text = ""
    except Exception as exc:
        return 0, str(exc), None

    parsed = None
    if text:
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                parsed = obj
        except Exception:
            parsed = None
    return code, text, parsed


def probe_live_commerce_endpoints(
    base_url: str,
    property_id: str,
    timeout: float = 15.0,
    repo_root: Optional[Union[str, Path]] = None,
    dist_dir: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """
    Read-only live production commerce probe (zero real charges, zero live mutations,
    zero Turnstile bypass).
    """
    prop = _normalize_property_id(property_id)
    base = str(base_url or "").strip().rstrip("/")
    matrix = resolve_tenant_commerce_matrix(prop, repo_root=repo_root, dist_dir=dist_dir)
    valid_tool = matrix["valid_tool_slug"]
    issues: List[str] = []
    probes: Dict[str, Any] = {}

    # 1. All 3 checkout tiers (livemode: true, exact price, success_url -> HTTP 200)
    for tier_name in ("quick", "full", "partner_slot"):
        spec = matrix["tiers"][tier_name]
        qs = urllib.parse.urlencode(
            {"format": "json", "sku": spec["sku"], "tool_slug": spec["tool_slug"]}
        )
        c_code, _, c_json = _http_probe(f"{base}/api/checkout?{qs}", method="GET", timeout=timeout)
        succ_url = str((c_json or {}).get("success_url") or "")
        succ_code = 0
        succ_path = ""
        if succ_url:
            succ_path = urllib.parse.urlsplit(succ_url).path or "/"
            probe_succ = succ_url.replace("{CHECKOUT_SESSION_ID}", "cs_live_probe_check")
            succ_code, _, _ = _http_probe(probe_succ, method="GET", timeout=timeout)

        price_ok = False
        if isinstance(c_json, dict):
            usd_val = c_json.get("offer_price_usd")
            if usd_val is None:
                usd_val = c_json.get("price_usd")
            if usd_val is not None:
                price_ok = abs(float(usd_val) - float(spec["price_usd"])) < 0.01
            cents_val = c_json.get("price_cents") if c_json.get("price_cents") is not None else c_json.get("unit_amount")
            if cents_val is not None:
                price_ok = price_ok and int(cents_val) == int(spec["price_cents"])

        livemode_ok = bool(isinstance(c_json, dict) and c_json.get("livemode") is True)
        sku_ok = bool(isinstance(c_json, dict) and c_json.get("offer_sku") == spec["sku"])
        partner_path_ok = (
            True
            if tier_name != "partner_slot"
            else (succ_path in ("/partners/", "/partners", "/partners/index.html") and "/tools/partners" not in succ_path)
        )
        tier_ok = (
            c_code == 200
            and livemode_ok
            and price_ok
            and sku_ok
            and succ_code == 200
            and partner_path_ok
        )
        probes[f"checkout_{tier_name}"] = {
            "status_code": c_code,
            "livemode": c_json.get("livemode") if isinstance(c_json, dict) else None,
            "offer_sku": c_json.get("offer_sku") if isinstance(c_json, dict) else None,
            "offer_price_usd": c_json.get("offer_price_usd") if isinstance(c_json, dict) else None,
            "success_url": succ_url,
            "success_url_status": succ_code,
            "passed": tier_ok,
        }
        if not tier_ok:
            issues.append(
                f"Live checkout probe failed for {tier_name} ({spec['sku']}): "
                f"http={c_code}, livemode={livemode_ok}, price_ok={price_ok}, "
                f"sku_ok={sku_ok}, success_url_http={succ_code}, partner_path_ok={partner_path_ok}"
            )

    # 2. Unknown SKU -> HTTP 400
    bad_code, _, _ = _http_probe(
        f"{base}/api/checkout?format=json&sku=invalid_unknown_sku_probe",
        method="GET",
        timeout=timeout,
    )
    probes["checkout_unknown_sku"] = {"status_code": bad_code, "passed": bad_code == 400}
    if bad_code != 400:
        issues.append(f"Live unknown SKU probe expected HTTP 400, got HTTP {bad_code}")

    # 3. Unpaid ?playbook=1 -> HTTP 200 with zero csv_content / period_schedule / sensitivity_matrix
    pb_qs = urllib.parse.urlencode({"playbook": "1", "tool_slug": valid_tool})
    pb_code, _, pb_json = _http_probe(f"{base}/api/lead-capture?{pb_qs}", method="GET", timeout=timeout)
    pb_leaks: List[str] = []
    if isinstance(pb_json, dict):
        if pb_json.get("csv_content"):
            pb_leaks.append("csv_content")
        for key in ("period_schedule", "sensitivity_matrix", "statutory_trend_timeseries"):
            val = pb_json.get(key)
            if isinstance(val, list) and len(val) > 0:
                pb_leaks.append(key)
        dp = pb_json.get("statutory_data_pack")
        if isinstance(dp, dict):
            if dp.get("csv_content"):
                pb_leaks.append("statutory_data_pack.csv_content")
            for key in ("period_schedule", "sensitivity_matrix", "statutory_trend_timeseries"):
                val = dp.get(key)
                if isinstance(val, list) and len(val) > 0:
                    pb_leaks.append(f"statutory_data_pack.{key}")
    pb_ok = pb_code == 200 and isinstance(pb_json, dict) and len(pb_leaks) == 0
    probes["unpaid_playbook"] = {"status_code": pb_code, "leaks": pb_leaks, "passed": pb_ok}
    if not pb_ok:
        issues.append(f"Live unpaid ?playbook=1 failed: http={pb_code}, leaks={pb_leaks}")

    # 4. Unpaid CSV / DataPack / Fulfillment -> HTTP 402
    for label, path in (
        ("unpaid_playbook_csv", f"/api/lead-capture?{pb_qs}&format=csv"),
        ("unpaid_playbook_datapack", f"/api/lead-capture?{pb_qs}&format=datapack"),
        ("unpaid_lead_fulfillment", "/api/lead-fulfillment"),
    ):
        u_code, _, _ = _http_probe(f"{base}{path}", method="GET", timeout=timeout)
        probes[label] = {"status_code": u_code, "passed": u_code == 402}
        if u_code != 402:
            issues.append(f"Live {label} ({path}) expected HTTP 402, got HTTP {u_code}")

    # 5. Unsigned POST /api/stripe-webhook -> HTTP 400 (secret configured)
    wh_body = json.dumps({"id": "evt_unsigned_probe", "type": "checkout.session.completed"}).encode("utf-8")
    wh_code, _, _ = _http_probe(
        f"{base}/api/stripe-webhook",
        method="POST",
        body=wh_body,
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )
    probes["unsigned_stripe_webhook"] = {"status_code": wh_code, "passed": wh_code == 400}
    if wh_code != 400:
        issues.append(f"Live unsigned POST /api/stripe-webhook expected HTTP 400, got HTTP {wh_code}")

    return {
        "status": "PASS" if not issues else "FAIL",
        "passed": len(issues) == 0,
        "property_id": prop,
        "base_url": base,
        "probes": probes,
        "issues": issues,
    }


def _check_pricing_and_sku_parity(
    repo_path: Path,
    property_id: str,
    matrix: Dict[str, Any],
) -> Dict[str, Any]:
    from pseofactory import pricing

    prop = _normalize_property_id(property_id)
    issues: List[str] = []
    catalog = matrix["catalog"]
    if not catalog:
        issues.append(f"Empty pricing catalog resolved for '{prop}'")

    for tier_name, tier_spec in matrix["tiers"].items():
        if not _validate_sku_for_tenant(prop, tier_spec["sku"], repo_root=repo_path):
            issues.append(f"SKU '{tier_spec['sku']}' ({tier_name}) failed validate_tenant_sku for '{prop}'")
    if _validate_sku_for_tenant(prop, matrix["foreign_sku"], repo_root=repo_path):
        issues.append(f"Foreign SKU '{matrix['foreign_sku']}' falsely accepted for '{prop}'")

    # Check monetization_vault.json parity for SKUs belonging to this property (when vault exists)
    if _MONETIZATION_VAULT_PATH.is_file():
        try:
            vault = json.loads(_MONETIZATION_VAULT_PATH.read_text(encoding="utf-8"))
            dp = ((vault.get("master_networks") or {}).get("stripe") or {}).get("digital_products") or {}
            if isinstance(dp, dict):
                for sku_k, item in catalog.items():
                    if sku_k in dp:
                        v_cents = int(dp[sku_k].get("price_cents") or -1)
                        if v_cents != int(item["price_cents"]):
                            issues.append(
                                f"monetization_vault.json price_cents drift for '{sku_k}': "
                                f"got {v_cents}, expected {item['price_cents']}"
                            )
        except Exception as exc:
            issues.append(f"Failed to read monetization_vault.json for pricing parity: {exc}")

    # Check compiled lead-capture.js CANONICAL_OFFER_CATALOG parity if present
    lc_path = repo_path / "functions" / "api" / "lead-capture.js"
    if lc_path.is_file():
        lc_txt = lc_path.read_text(encoding="utf-8", errors="ignore")
        cat_m = re.search(r"const\s+CANONICAL_OFFER_CATALOG\s*=\s*(\{[\s\S]*?\n\})\s*;", lc_txt)
        if cat_m:
            try:
                edge_cat = json.loads(cat_m.group(1))
                for sku_k, item in catalog.items():
                    e_item = edge_cat.get(sku_k)
                    if not isinstance(e_item, dict):
                        issues.append(f"lead-capture.js missing canonical SKU '{sku_k}'")
                    elif int(e_item.get("price_cents") or -1) != int(item["price_cents"]):
                        issues.append(
                            f"lead-capture.js price_cents drift for '{sku_k}': "
                            f"got {e_item.get('price_cents')}, expected {item['price_cents']}"
                        )
            except Exception as exc:
                issues.append(f"Failed to parse CANONICAL_OFFER_CATALOG in lead-capture.js: {exc}")

    return {
        "status": "PASS" if not issues else "FAIL",
        "passed": len(issues) == 0,
        "property_id": prop,
        "audience_tier": pricing.get_audience_tier(prop, repo_root=repo_path),
        "sku_count": len(catalog),
        "issues": issues,
    }


def audit_tenant_commerce_fail_closed(
    repo_root: Union[str, Path],
    property_id: str,
    live_base_url: Optional[str] = None,
    dist_dir: Optional[Union[str, Path]] = None,
    timeout: float = 15.0,
) -> CommerceGateReport:
    """
    Combines static dist/ deliverable leak scan + pricing/SKU parity + local Node.js v22
    edge replay (+ optional live endpoint probe) into a structured fail-closed CommerceGateReport.
    """
    prop = _normalize_property_id(property_id)
    repo_path = Path(repo_root).resolve()
    eff_dist = Path(dist_dir).resolve() if dist_dir is not None else (repo_path / "dist").resolve()

    matrix = resolve_tenant_commerce_matrix(prop, repo_root=repo_path, dist_dir=eff_dist)
    static_res = audit_static_dist_deliverable_leaks(eff_dist, prop)
    parity_res = _check_pricing_and_sku_parity(repo_path, prop, matrix)
    replay_res = verify_local_edge_commerce_replay(repo_path, prop, dist_dir=eff_dist)
    live_res: Optional[Dict[str, Any]] = None
    if live_base_url:
        live_res = probe_live_commerce_endpoints(
            live_base_url,
            prop,
            timeout=timeout,
            repo_root=repo_path,
            dist_dir=eff_dist,
        )

    issues: List[str] = []
    for label, sub in (
        ("static_leak", static_res),
        ("pricing_parity", parity_res),
        ("edge_replay", replay_res),
    ):
        for msg in sub.get("violations") or sub.get("issues") or []:
            issues.append(f"[{label}] {msg}")
    if live_res is not None:
        for msg in live_res.get("issues") or []:
            issues.append(f"[live_probe] {msg}")

    passed = (
        bool(static_res.get("passed"))
        and bool(parity_res.get("passed"))
        and bool(replay_res.get("passed"))
        and (True if live_res is None else bool(live_res.get("passed")))
    )
    return CommerceGateReport(
        property_id=prop,
        status="PASS" if passed else "FAIL",
        passed=passed,
        repo_root=str(repo_path),
        dist_dir=str(eff_dist),
        static_leak_audit=static_res,
        pricing_parity=parity_res,
        edge_replay=replay_res,
        live_probe=live_res,
        issues=issues,
    )


__all__ = [
    "CommerceGateReport",
    "FORBIDDEN_DIST_DELIVERABLE_TOKENS",
    "audit_static_dist_deliverable_leaks",
    "audit_tenant_commerce_fail_closed",
    "probe_live_commerce_endpoints",
    "resolve_tenant_commerce_matrix",
    "verify_local_edge_commerce_replay",
]
