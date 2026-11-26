"""
AI Overview Observatory (x-like:2107453596107219294, @jakezward).

Method: pick an AI Overview, track how it changes over 7 days, find the patterns,
reverse engineer the citations, build the page around the findings.

Google regenerates an AI Overview on every search, so a single sample is noise.
The observatory samples each watchlist query repeatedly (daily cron), stores every
snapshot, and turns the series into:
  * citation stability: core (cited in most samples), rotating (sometimes: the
    winnable slots), one_off;
  * answer shape: number-first lead, comparison table, recurring section headings;
  * recurring facts the overview keeps restating;
  * a per-query blueprint consumed by GSC remediation briefs;
  * a per-tenant scoreboard: share of AI Overview samples that cite the tenant.

Failed samples are stored with an error and excluded from every rate: unknown is
never counted as success or failure. Pattern finding is deterministic (no LLM).
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import sqlite3
import subprocess
import time
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union
from urllib.parse import urlparse

DEFAULT_AIO_DB_PATH = Path("/home/ubuntuadmin/projects/.agy/runs/aio_observatory.db")
DEFAULT_WATCHLIST_PATH = Path("/home/ubuntuadmin/projects/.agy/aio_watchlist.json")
ENDPOINT_AIO = "anyapi.google.serp.ai_overview"
EVIDENCE_ENDPOINT = "google.serp.ai_overview.observatory"
MAX_AIO_COST_USD = "0.004"
DEFAULT_WINDOW_DAYS = 7
ROLLING_WINDOW_DAYS: Tuple[int, ...] = (7, 28)
VALID_AIO_INTENTS: Tuple[str, ...] = ("factual", "multi_variable", "tool_recommendation")

CORE_MIN_RATE = 0.7
ROTATING_MIN_RATE = 0.25
FACT_MIN_RATE = 0.5
HEADING_MIN_RATE = 0.4
SHAPE_MIN_RATE = 0.5
MIN_CONFIDENT_SAMPLES = 3

Sampler = Callable[[str], Dict[str, Any]]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_domain(url_or_domain: str) -> str:
    val = str(url_or_domain or "").strip().lower()
    if not val:
        return ""
    host = urlparse(val).netloc if "://" in val else val.split("/")[0]
    host = host.split(":")[0]
    return host[4:] if host.startswith("www.") else host


def normalize_url(url: str) -> str:
    """Scheme-less, www-less, query-less, trailing-slash-less URL key so resamples of one page match."""
    p = urlparse(str(url or "").strip())
    if not p.netloc:
        return str(url or "").strip().lower().rstrip("/")
    return f"{normalize_domain(p.netloc)}{p.path}".rstrip("/").lower()


def _domain_matches(domain: str, tenant_domains: Iterable[str]) -> bool:
    return any(domain == t or domain.endswith(f".{t}") for t in (normalize_domain(x) for x in tenant_domains) if t)


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------


def parse_treg_aio_output(stdout: str) -> Dict[str, Any]:
    """Normalize a `treg call anyapi.google.serp.ai_overview` JSON envelope into a snapshot payload."""
    env = json.loads(stdout)
    out = env.get("output", env) if isinstance(env, dict) else {}
    data = out.get("data") or {}
    citations = []
    for c in data.get("citations") or []:
        if isinstance(c, dict) and c.get("url"):
            citations.append({"url": c["url"], "title": str(c.get("title") or ""), "index": c.get("index")})
    return {
        "found": bool(out.get("found")) and bool(data),
        "answer": str(data.get("answerMarkdown") or data.get("answer") or ""),
        "citations": citations,
        "provider": str(env.get("provider") or ENDPOINT_AIO),
        "cost_usd": float(env.get("costUsd") or 0.0),
    }


_TRANSIENT_HTTP_RE = re.compile(
    r"(?:http\s*(?:429|500|502|503|504)\b|timed?\s*out|connection\s+reset|temporarily\s+unavailable|bad\s+gateway|service\s+unavailable)",
    re.IGNORECASE,
)
_NON_RETRYABLE_HTTP_RE = re.compile(r"http\s*(?:400|401|403|404|422)\b", re.IGNORECASE)
_JUNK_PROBE_QUERY_RE = re.compile(
    r"(?:\brobots[\s._-]*txt\b|\bsitemap[\s._-]*xml\b|\bllms[\s._-]*txt\b|\bexample\.com\b|\bamazon\s+com\s+robots\b|\bprobe[\s._-]*query\b|\btest[\s._-]*query\b)",
    re.IGNORECASE,
)


def is_probe_or_junk_query(query: str) -> bool:
    """Returns True for synthetic probe/infrastructure queries that must never enter AIO snapshots or citation caches."""
    cleaned = " ".join(str(query or "").strip().lower().split())
    if not cleaned or len(cleaned) < 3:
        return True
    return bool(_JUNK_PROBE_QUERY_RE.search(cleaned))


def _is_transient_sampler_error(err_text: str) -> bool:
    low = str(err_text or "")
    if _NON_RETRYABLE_HTTP_RE.search(low):
        return False
    return bool(_TRANSIENT_HTTP_RE.search(low))


def treg_sampler(
    query: str,
    timeout: float = 120.0,
    max_retries: int = 3,
    base_backoff_seconds: float = 1.5,
) -> Dict[str, Any]:
    """
    Live Google AI Overview sample via treg, with a hard per-call cost ceiling
    and bounded exponential retry on transient HTTP 502/503/504/429 and timeout errors.
    Deterministic client errors (e.g. HTTP 400/401/403/404) fail fast without retrying.
    """
    treg_bin = shutil.which("treg")
    if not treg_bin:
        raise RuntimeError("treg binary not found on PATH")
    cmd = [
        treg_bin,
        "call",
        ENDPOINT_AIO,
        "--method",
        "POST",
        "--data",
        json.dumps({"prompt": query}),
        "--header",
        f"X-Treg-Route-Max-Cost: {MAX_AIO_COST_USD}",
    ]
    attempts = max(1, int(max_retries))
    last_exc: Optional[Exception] = None
    for attempt in range(attempts):
        try:
            proc = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            last_exc = exc
            if attempt + 1 < attempts:
                delay = min(15.0, float(base_backoff_seconds) * (2 ** attempt))
                time.sleep(delay)
                continue
            raise
        if proc.returncode == 0 and proc.stdout.strip():
            return parse_treg_aio_output(proc.stdout)
        err_msg = f"treg exit {proc.returncode}: {(proc.stderr or proc.stdout).strip()[:300]}"
        last_exc = RuntimeError(err_msg)
        if _is_transient_sampler_error(err_msg) and attempt + 1 < attempts:
            delay = min(15.0, float(base_backoff_seconds) * (2 ** attempt))
            time.sleep(delay)
            continue
        raise last_exc
    raise last_exc or RuntimeError("treg_sampler exhausted retries")


_TOOL_INTENT_RE = re.compile(
    r"\b(?:calculator|estimator|tool|software|platform|app|provider|vendor|lender|broker|template|worksheet|generator|planner|recommend|recommendation|best\s+[a-z0-9]+)\b",
    re.IGNORECASE,
)
_MULTI_VAR_INTENT_RE = re.compile(
    r"(?:\b(?:vs\.?|versus|compare|comparison|difference\s+between|scenario|multi[- ]?variable|trade[- ]?off|break[- ]?even|by\s+state|state\s+by\s+state|bracket|matrix)\b|\bwith\b.*\band\b|\b(?:if|when|for)\b.*\b(?:and|or|with)\b)",
    re.IGNORECASE,
)


def classify_query_intent(query: str) -> str:
    """Deterministically classifies a query into 'factual', 'multi_variable', or 'tool_recommendation'."""
    cleaned = " ".join(str(query or "").strip().lower().split())
    if not cleaned:
        return "factual"
    if _TOOL_INTENT_RE.search(cleaned):
        return "tool_recommendation"
    if _MULTI_VAR_INTENT_RE.search(cleaned):
        return "multi_variable"
    return "factual"


def _normalize_intent(intent: Optional[str], query: str) -> str:
    val = str(intent or "").strip().lower()
    if val in VALID_AIO_INTENTS:
        return val
    return classify_query_intent(query)


def load_watchlist(
    path: Optional[Path] = None,
    tenants: Optional[Sequence[str]] = None,
    include_intent: bool = False,
) -> List[Any]:
    """
    Watchlist loader covering every tenant core-tool primary keyword plus extra queries
    from .agy/aio_watchlist.json shaped {"<tenant_id>": ["query" | {"query": ..., "intent": ...}, ...]}.
    Returns (tenant, query) tuples by default, or (tenant, query, intent) when include_intent=True.
    """
    from pseofactory.tenant_facts import TENANT_CORE_TOOLS_BY_ID

    raw_items: List[Tuple[str, str, str]] = []
    for pid, tools in TENANT_CORE_TOOLS_BY_ID.items():
        for t in tools:
            kw = str(t.get("primary_keyword") or "").strip().lower()
            if kw:
                raw_items.append((pid, kw, _normalize_intent(t.get("intent"), kw)))
    wl_path = path or DEFAULT_WATCHLIST_PATH
    if wl_path.is_file():
        extra = json.loads(wl_path.read_text(encoding="utf-8"))
        for pid, queries in (extra or {}).items():
            for entry in queries or []:
                if isinstance(entry, dict):
                    q = str(entry.get("query") or "").strip().lower()
                    ent_intent = _normalize_intent(entry.get("intent"), q)
                else:
                    q = str(entry).strip().lower()
                    ent_intent = classify_query_intent(q)
                if q:
                    raw_items.append((str(pid), q, ent_intent))
    seen = set()
    result: List[Any] = []
    for pid, q, intent_val in raw_items:
        if tenants and pid not in tenants:
            continue
        if (pid, q) not in seen:
            seen.add((pid, q))
            if include_intent:
                result.append((pid, q, intent_val))
            else:
                result.append((pid, q))
    return result


def load_watchlist_entries(
    path: Optional[Path] = None,
    tenants: Optional[Sequence[str]] = None,
) -> List[Dict[str, str]]:
    """Returns watchlist rows as dicts with 'tenant', 'query', and 'intent'."""
    return [
        {"tenant": pid, "query": q, "intent": intent_val}
        for pid, q, intent_val in load_watchlist(path=path, tenants=tenants, include_intent=True)
    ]


# ---------------------------------------------------------------------------
# Pattern extraction (deterministic)
# ---------------------------------------------------------------------------

_MONEY_RANGE = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?\s?[kKmM]?\+?(?:\s?(?:to|-|\u2013|\u2014)\s?\$?\s?\d[\d,]*(?:\.\d+)?\s?[kKmM]?\+?)?")
_PERCENT = re.compile(r"\b\d+(?:\.\d+)?\s?%")
_DURATION = re.compile(r"\b\d+(?:\s?(?:to|-|\u2013)\s?\d+)?\s(?:days?|weeks?|months?|years?)\b", re.IGNORECASE)
_HEADING = re.compile(r"^\s{0,3}#{2,4}\s+(.+?)\s*$", re.MULTILINE)
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{3,}", re.MULTILINE)


def _norm_fact(raw: str) -> str:
    s = raw.strip().lower().replace("\u2013", "-").replace("\u2014", "-")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s?(to|-)\s?", " to ", s) if ("$" in s or "%" in s or re.search(r"\d\s?(to|-)\s?\d", s)) else s
    return s.replace("$ ", "$").strip().rstrip("+").strip()


def extract_facts(answer: str) -> List[str]:
    facts = set()
    for rx in (_MONEY_RANGE, _PERCENT, _DURATION):
        for m in rx.finditer(answer or ""):
            f = _norm_fact(m.group(0))
            if any(ch.isdigit() for ch in f):
                facts.add(f)
    return sorted(facts)


def extract_headings(answer: str) -> List[str]:
    out = []
    for m in _HEADING.finditer(answer or ""):
        h = re.sub(r"[*_`\\]", "", m.group(1)).strip().rstrip(":")
        if h and h.lower() != "share public link":
            out.append(h)
    return out


def lead_has_number(answer: str) -> bool:
    text = re.sub(r"^[#\s*]+", "", (answer or "").strip())
    first = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0] if text else ""
    return bool(re.search(r"\d", first))


def has_table(answer: str) -> bool:
    return bool(_TABLE_SEP.search(answer or "")) and "|" in (answer or "")


# ---------------------------------------------------------------------------
# Observatory
# ---------------------------------------------------------------------------


class AIOObservatory:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path is not None else DEFAULT_AIO_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS aio_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    tenant TEXT NOT NULL,
                    query TEXT NOT NULL,
                    sampled_at TEXT NOT NULL,
                    found INTEGER,
                    answer TEXT,
                    citations TEXT,
                    provider TEXT,
                    cost_usd REAL,
                    error TEXT,
                    intent TEXT NOT NULL DEFAULT 'factual'
                )
                """
            )
            cols = {row["name"] for row in c.execute("PRAGMA table_info(aio_snapshots)")}
            if "intent" not in cols:
                c.execute("ALTER TABLE aio_snapshots ADD COLUMN intent TEXT NOT NULL DEFAULT 'factual'")
                existing = list(c.execute("SELECT snapshot_id, query FROM aio_snapshots"))
                for ex_row in existing:
                    c.execute(
                        "UPDATE aio_snapshots SET intent = ? WHERE snapshot_id = ?",
                        (classify_query_intent(ex_row["query"]), ex_row["snapshot_id"]),
                    )
            c.execute("CREATE INDEX IF NOT EXISTS idx_aio_query_time ON aio_snapshots(query, sampled_at)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_aio_intent_time ON aio_snapshots(intent, sampled_at)")

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    # -- writes --------------------------------------------------------------

    def record(
        self,
        tenant: str,
        query: str,
        payload: Optional[Dict[str, Any]],
        error: str = "",
        at: Optional[datetime] = None,
        intent: Optional[str] = None,
    ) -> str:
        if is_probe_or_junk_query(query):
            raise ValueError(f"Refusing to record junk/probe query in AIO observatory: {query!r}")
        sid = uuid.uuid4().hex
        stamp = (at or _now()).isoformat()
        resolved_intent = _normalize_intent(intent, query)
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO aio_snapshots (
                    snapshot_id, tenant, query, sampled_at, found, answer,
                    citations, provider, cost_usd, error, intent
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    sid,
                    tenant,
                    query.strip().lower(),
                    stamp,
                    None if error else int(bool((payload or {}).get("found"))),
                    None if error else str((payload or {}).get("answer") or ""),
                    None if error else json.dumps((payload or {}).get("citations") or []),
                    None if error else str((payload or {}).get("provider") or ""),
                    None if error else float((payload or {}).get("cost_usd") or 0.0),
                    error or None,
                    resolved_intent,
                ),
            )
        return sid

    def sample(
        self,
        watchlist: Optional[Sequence[Any]] = None,
        sampler: Optional[Sampler] = None,
        max_queries: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Take one AI Overview sample per watchlist query and store it."""
        pairs = list(watchlist if watchlist is not None else load_watchlist(include_intent=True))
        if max_queries is not None:
            pairs = pairs[: max(0, int(max_queries))]
        fn = sampler or treg_sampler
        summary = {"sampled": 0, "found": 0, "errors": 0, "skipped_junk": 0, "cost_usd": 0.0, "error_samples": []}
        for item in pairs:
            if isinstance(item, dict):
                tenant = str(item.get("tenant") or "")
                query = str(item.get("query") or "")
                item_intent = item.get("intent")
            elif len(item) >= 3:
                tenant, query, item_intent = item[0], item[1], item[2]
            else:
                tenant, query = item[0], item[1]
                item_intent = None
            if is_probe_or_junk_query(query):
                summary["skipped_junk"] += 1
                continue
            try:
                payload = fn(query)
            except Exception as exc:  # recorded as unknown, never as a miss
                self.record(tenant, query, None, error=str(exc)[:500] or exc.__class__.__name__, intent=item_intent)
                summary["errors"] += 1
                summary["error_samples"].append({"query": query, "error": str(exc)[:200]})
                continue
            self.record(tenant, query, payload, intent=item_intent)
            summary["sampled"] += 1
            summary["found"] += int(bool(payload.get("found")))
            summary["cost_usd"] = round(summary["cost_usd"] + float(payload.get("cost_usd") or 0.0), 6)
        return summary

    # -- reads ---------------------------------------------------------------

    def _rows(
        self,
        query: Optional[str] = None,
        window_days: float = DEFAULT_WINDOW_DAYS,
        now: Optional[datetime] = None,
        intent: Optional[str] = None,
    ) -> List[sqlite3.Row]:
        since = ((now or _now()) - timedelta(days=window_days)).isoformat()
        sql = "SELECT * FROM aio_snapshots WHERE error IS NULL AND sampled_at >= ?"
        args: List[Any] = [since]
        if query is not None:
            sql += " AND query = ?"
            args.append(query.strip().lower())
        if intent is not None:
            sql += " AND intent = ?"
            args.append(str(intent).strip().lower())
        sql += " ORDER BY sampled_at"
        with self._conn() as c:
            return list(c.execute(sql, args))

    def analyze(
        self,
        query: str,
        tenant_domains: Optional[Sequence[str]] = None,
        window_days: float = DEFAULT_WINDOW_DAYS,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        rows = self._rows(query, window_days, now)
        tenant_doms = list(tenant_domains or [])
        if not tenant_doms and rows:
            tenant_doms = _tenant_domains_for(rows[0]["tenant"])
        found_rows = [r for r in rows if r["found"]]
        n, nf = len(rows), len(found_rows)

        url_counts: Counter = Counter()
        url_meta: Dict[str, Dict[str, str]] = {}
        dom_counts: Counter = Counter()
        fact_counts: Counter = Counter()
        heading_counts: Counter = Counter()
        heading_label: Dict[str, str] = {}
        lead_num = table = tenant_hits = 0

        for r in found_rows:
            cits = json.loads(r["citations"] or "[]")
            urls_here, doms_here = set(), set()
            for c in cits:
                key = normalize_url(c.get("url", ""))
                if not key:
                    continue
                urls_here.add(key)
                url_meta.setdefault(key, {"url": c.get("url", ""), "title": str(c.get("title") or "")})
                doms_here.add(normalize_domain(c.get("url", "")))
            url_counts.update(urls_here)
            dom_counts.update(d for d in doms_here if d)
            if any(_domain_matches(d, tenant_doms) for d in doms_here):
                tenant_hits += 1
            ans = r["answer"] or ""
            fact_counts.update(set(extract_facts(ans)))
            hs = set()
            for h in extract_headings(ans):
                k = h.lower()
                heading_label.setdefault(k, h)
                hs.add(k)
            heading_counts.update(hs)
            lead_num += lead_has_number(ans)
            table += has_table(ans)

        def rate(cnt: int) -> float:
            return round(cnt / nf, 3) if nf else 0.0

        citations = []
        for key, cnt in url_counts.most_common():
            r_ = rate(cnt)
            cls = "core" if r_ >= CORE_MIN_RATE else ("rotating" if r_ >= ROTATING_MIN_RATE else "one_off")
            citations.append(
                {
                    "url": url_meta[key]["url"],
                    "title": url_meta[key]["title"],
                    "domain": normalize_domain(url_meta[key]["url"]),
                    "rate": r_,
                    "class": cls,
                    "tenant": _domain_matches(normalize_domain(url_meta[key]["url"]), tenant_doms),
                }
            )
        resolved_intent = (
            rows[-1]["intent"]
            if rows and "intent" in rows[-1].keys() and rows[-1]["intent"] in VALID_AIO_INTENTS
            else classify_query_intent(query)
        )
        return {
            "query": query.strip().lower(),
            "intent": resolved_intent,
            "window_days": window_days,
            "samples": n,
            "samples_with_aio": nf,
            "confidence": "ok" if n >= MIN_CONFIDENT_SAMPLES else "low",
            "aio_presence_rate": round(nf / n, 3) if n else 0.0,
            "tenant_domains": tenant_doms,
            "tenant_citation_rate": rate(tenant_hits),
            "citations": citations,
            "domains": [{"domain": d, "rate": rate(c)} for d, c in dom_counts.most_common()],
            "recurring_facts": [{"fact": f, "rate": rate(c)} for f, c in fact_counts.most_common() if rate(c) >= FACT_MIN_RATE],
            "recurring_headings": [
                {"heading": heading_label[k], "rate": rate(c)} for k, c in heading_counts.most_common() if rate(c) >= HEADING_MIN_RATE
            ],
            "shape": {"lead_with_number_rate": rate(lead_num), "table_rate": rate(table)},
            "first_sample_at": rows[0]["sampled_at"] if rows else None,
            "last_sample_at": rows[-1]["sampled_at"] if rows else None,
        }

    def blueprint(
        self,
        query: str,
        tenant_domains: Optional[Sequence[str]] = None,
        window_days: float = DEFAULT_WINDOW_DAYS,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Turn the observed series into page instructions a brief can act on."""
        a = self.analyze(query, tenant_domains, window_days, now)
        winnable = [c for c in a["citations"] if c["class"] == "rotating" and not c["tenant"]]
        core = [c for c in a["citations"] if c["class"] == "core" and not c["tenant"]]
        lead = a["shape"]["lead_with_number_rate"] >= SHAPE_MIN_RATE
        table = a["shape"]["table_rate"] >= SHAPE_MIN_RATE
        facts = [f["fact"] for f in a["recurring_facts"]][:12]
        headings = [h["heading"] for h in a["recurring_headings"]][:8]

        actions: List[str] = []
        if a["samples"] == 0:
            actions.append("No observations yet: run `pseofactory aio-observe sample` daily for 7 days.")
        elif a["samples_with_aio"] == 0:
            actions.append("Google shows no AI Overview for this query: target the classic featured snippet instead.")
        else:
            if a["tenant_citation_rate"] >= CORE_MIN_RATE:
                actions.append("Tenant is a core citation: protect the page, change only additive facts.")
            if lead:
                actions.append("Open with a one-sentence direct answer that states the number or range first.")
            if table:
                actions.append("Include a comparison or cost-breakdown table; the overview renders one.")
            if facts:
                actions.append("State and source the facts the overview keeps repeating: " + "; ".join(facts[:6]) + ".")
            if headings:
                actions.append("Mirror the overview's section structure with H2/H3s: " + "; ".join(headings[:6]) + ".")
            if winnable:
                actions.append(
                    f"{len(winnable)} rotating citation slot(s) are winnable; out-cover these pages: "
                    + ", ".join(c["domain"] for c in winnable[:5])
                    + "."
                )
        return {
            "query": a["query"],
            "samples": a["samples"],
            "samples_with_aio": a["samples_with_aio"],
            "confidence": a["confidence"],
            "aio_presence_rate": a["aio_presence_rate"],
            "tenant_citation_rate": a["tenant_citation_rate"],
            "winnable_slots": [{"url": c["url"], "rate": c["rate"]} for c in winnable[:8]],
            "incumbent_core": [{"url": c["url"], "rate": c["rate"]} for c in core[:8]],
            "must_include_facts": facts,
            "section_headings": headings,
            "format": {"lead_with_number": lead, "include_table": table},
            "actions": actions,
            "window_days": window_days,
            "last_sample_at": a["last_sample_at"],
        }

    def citation_evidence(
        self,
        query: str,
        tenant_domains: Optional[Sequence[str]] = None,
        window_days: float = DEFAULT_WINDOW_DAYS,
    ) -> Optional[Dict[str, Any]]:
        """
        Measured AI Overview evidence in TregChecker.check_ai_citation's result shape,
        or None when the observatory has no valid sample for the query in the window.
        """
        if is_probe_or_junk_query(query):
            return None
        a = self.analyze(query, tenant_domains, window_days)
        if a["samples"] == 0:
            return None
        from pseofactory.trends.treg_checker import parse_ai_citation_payload

        recurring = [d["domain"] for d in a["domains"] if d["rate"] >= ROTATING_MIN_RATE]
        if a["samples_with_aio"] == 0:
            parsed = parse_ai_citation_payload({"citations": []}, tenant_domains=a["tenant_domains"] or None)
        else:
            parsed = parse_ai_citation_payload(
                {"citations": [{"domain": d} for d in recurring]}, tenant_domains=a["tenant_domains"] or None
            )
            parsed["missing_ai_overview"] = False
            if parsed["citation_gap_status"] == "MISSING_AI_OVERVIEW":
                parsed["citation_gap_status"] = "AI_CITATION_VACANT"
        tenant_cited = a["tenant_citation_rate"] >= ROTATING_MIN_RATE
        if tenant_cited:
            parsed["citation_gap_status"] = "TENANT_CITED"
        return {
            "query": query.strip(),
            "endpoint_called": EVIDENCE_ENDPOINT,
            "ai_citation_vacant": parsed["ai_citation_vacant"] and not tenant_cited,
            "ai_cited_domains": parsed["ai_cited_domains"],
            "weaker_cited_domains": parsed["weaker_cited_domains"],
            "losing_to_weaker_domains": parsed["losing_to_weaker_domains"] and not tenant_cited,
            "missing_ai_overview": parsed["missing_ai_overview"],
            "citation_gap_status": parsed["citation_gap_status"],
            "tenant_cited": tenant_cited,
            "ai_citation_checked": True,
            "checked_at": a["last_sample_at"],
            "measured": True,
            "aio_presence_rate": a["aio_presence_rate"],
            "tenant_citation_rate": a["tenant_citation_rate"],
            "aio_samples": a["samples"],
            "aio_blueprint": self.blueprint(query, tenant_domains, window_days),
        }

    def scoreboard(
        self,
        window_days: float = DEFAULT_WINDOW_DAYS,
        now: Optional[datetime] = None,
        intent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Per-tenant share of AI Overview samples that cite the tenant, segmented by query intent."""
        rows = self._rows(None, window_days, now, intent=intent)
        by_tenant: Dict[str, Dict[str, Any]] = {}
        global_by_intent: Dict[str, Dict[str, Any]] = {}

        def _new_bucket() -> Dict[str, Any]:
            return {
                "queries": set(),
                "samples": 0,
                "aio_samples": 0,
                "cited_samples": 0,
                "cited_queries": set(),
                "competitors": Counter(),
                "by_intent": {},
            }

        def _new_intent_bucket() -> Dict[str, Any]:
            return {"queries": set(), "samples": 0, "aio_samples": 0, "cited_samples": 0, "cited_queries": set()}

        for r in rows:
            row_intent = (
                r["intent"]
                if "intent" in r.keys() and r["intent"] in VALID_AIO_INTENTS
                else classify_query_intent(r["query"])
            )
            t = by_tenant.setdefault(r["tenant"], _new_bucket())
            ti = t["by_intent"].setdefault(row_intent, _new_intent_bucket())
            gi = global_by_intent.setdefault(row_intent, _new_intent_bucket())

            for b in (t, ti, gi):
                b["queries"].add(r["query"])
                b["samples"] += 1

            if not r["found"]:
                continue

            for b in (t, ti, gi):
                b["aio_samples"] += 1

            doms = {normalize_domain(c.get("url", "")) for c in json.loads(r["citations"] or "[]")}
            doms.discard("")
            tenant_doms = _tenant_domains_for(r["tenant"])
            if any(_domain_matches(d, tenant_doms) for d in doms):
                for b in (t, ti, gi):
                    b["cited_samples"] += 1
                    b["cited_queries"].add(r["query"])
            t["competitors"].update(d for d in doms if not _domain_matches(d, tenant_doms))

        def _fmt_intent_map(src_map: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
            out_i: Dict[str, Dict[str, Any]] = {}
            for intent_key in VALID_AIO_INTENTS:
                b = src_map.get(intent_key)
                if not b:
                    continue
                out_i[intent_key] = {
                    "queries_tracked": len(b["queries"]),
                    "samples": b["samples"],
                    "aio_presence_rate": round(b["aio_samples"] / b["samples"], 3) if b["samples"] else 0.0,
                    "citation_share": round(b["cited_samples"] / b["aio_samples"], 3) if b["aio_samples"] else 0.0,
                    "queries_citing_tenant": sorted(b["cited_queries"]),
                }
            return out_i

        tenants = {}
        for pid, t in sorted(by_tenant.items()):
            tenants[pid] = {
                "queries_tracked": len(t["queries"]),
                "samples": t["samples"],
                "aio_presence_rate": round(t["aio_samples"] / t["samples"], 3) if t["samples"] else 0.0,
                "citation_share": round(t["cited_samples"] / t["aio_samples"], 3) if t["aio_samples"] else 0.0,
                "queries_citing_tenant": sorted(t["cited_queries"]),
                "top_competitor_domains": [{"domain": d, "samples": c} for d, c in t["competitors"].most_common(5)],
                "intent_breakdown": _fmt_intent_map(t["by_intent"]),
            }
        return {
            "window_days": window_days,
            "generated_at": (now or _now()).isoformat(),
            "tenants": tenants,
            "intent_summary": _fmt_intent_map(global_by_intent),
        }

    def scoreboard_rolling(
        self,
        windows: Sequence[int] = ROLLING_WINDOW_DAYS,
        now: Optional[datetime] = None,
        intent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Computes rolling multi-window (default 7d and 28d) intent-segmented AIO scoreboards."""
        ref_now = now or _now()
        by_window: Dict[int, Dict[str, Any]] = {}
        for w in windows:
            w_int = int(w)
            by_window[w_int] = self.scoreboard(window_days=w_int, now=ref_now, intent=intent)
        return {
            "rolling_windows": [int(w) for w in windows],
            "generated_at": ref_now.isoformat(),
            "windows": {str(k): v for k, v in by_window.items()},
            **{f"window_{k}d": v for k, v in by_window.items()},
        }

    def analyze_rolling(
        self,
        query: str,
        tenant_domains: Optional[Sequence[str]] = None,
        windows: Sequence[int] = ROLLING_WINDOW_DAYS,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Runs analyze() across multiple rolling windows (default 7d and 28d)."""
        ref_now = now or _now()
        return {
            str(int(w)): self.analyze(query, tenant_domains=tenant_domains, window_days=int(w), now=ref_now)
            for w in windows
        }


def _to_float_or_zero(val: Any) -> float:
    s = str(val or "").strip().replace(",", "").replace("%", "")
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _read_external_ai_csv(csv_path: Optional[Union[str, Path]], source_kind: str) -> Dict[str, Dict[str, Any]]:
    """Reads a GSC GenAI or Bing AI Performance CSV and aggregates metrics keyed by canonical normalize_url()."""
    if not csv_path:
        return {}
    p = Path(csv_path)
    if not p.is_file():
        return {}
    by_url: Dict[str, Dict[str, Any]] = {}
    with p.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for raw_row in reader:
            norm_row = {
                re.sub(r"[^a-z0-9]+", "_", str(k or "").strip().lower()).strip("_"): (v or "").strip()
                for k, v in (raw_row or {}).items()
                if k is not None
            }
            raw_url = (
                norm_row.get("url")
                or norm_row.get("canonical_url")
                or norm_row.get("page")
                or norm_row.get("page_url")
                or norm_row.get("top_pages")
                or norm_row.get("landing_page")
                or norm_row.get("cited_url")
                or norm_row.get("cited_page")
                or ""
            )
            key = normalize_url(raw_url)
            if not key:
                continue
            entry = by_url.setdefault(
                key,
                {
                    "canonical_key": key,
                    "url": raw_url,
                    "source": source_kind,
                    "rows_matched": 0,
                    "clicks": 0.0,
                    "impressions": 0.0,
                    "citations": 0.0,
                    "queries": [],
                },
            )
            entry["rows_matched"] += 1
            entry["clicks"] += _to_float_or_zero(norm_row.get("clicks"))
            entry["impressions"] += _to_float_or_zero(
                norm_row.get("impressions")
                or norm_row.get("ai_overview_impressions")
                or norm_row.get("genai_impressions")
            )
            entry["citations"] += _to_float_or_zero(
                norm_row.get("citations") or norm_row.get("ai_citations") or norm_row.get("citation_count")
            )
            q_val = (
                norm_row.get("query")
                or norm_row.get("top_queries")
                or norm_row.get("grounding_query")
                or norm_row.get("grounding_queries")
                or norm_row.get("topic")
                or ""
            )
            if q_val and q_val not in entry["queries"]:
                entry["queries"].append(q_val)
    return by_url


def _extract_snapshot_urls(snapshot: Mapping[str, Any]) -> List[str]:
    urls: List[str] = []
    for k in ("url", "canonical_url", "page", "page_url"):
        val = snapshot.get(k)
        if isinstance(val, str) and val.strip():
            urls.append(val.strip())
    cits_raw = snapshot.get("citations")
    if isinstance(cits_raw, str) and cits_raw.strip():
        try:
            cits_raw = json.loads(cits_raw)
        except Exception:
            cits_raw = []
    if isinstance(cits_raw, list):
        for c in cits_raw:
            if isinstance(c, Mapping) and c.get("url"):
                urls.append(str(c["url"]).strip())
            elif isinstance(c, str) and c.strip():
                urls.append(c.strip())
    return urls


def join_external_ai_telemetry(
    snapshots: Iterable[Mapping[str, Any]],
    gsc_genai_csv_path: Optional[Union[str, Path]] = None,
    bing_ai_csv_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """
    Deterministically joins AIO snapshots with GSC GenAI CSV and/or Bing AI Performance CSV
    using canonical URL normalization (scheme-less, www-less, query-less, trailing-slash-less).
    """
    gsc_by_url = _read_external_ai_csv(gsc_genai_csv_path, "gsc_genai")
    bing_by_url = _read_external_ai_csv(bing_ai_csv_path, "bing_ai")

    joined_records: List[Dict[str, Any]] = []
    by_url: Dict[str, Dict[str, Any]] = {}
    matched_gsc_count = 0
    matched_bing_count = 0
    unique_matched_urls = set()

    for snap in snapshots or []:
        snap_dict = dict(snap)
        snap_urls = _extract_snapshot_urls(snap_dict)
        norm_keys: List[str] = []
        for u in snap_urls:
            nk = normalize_url(u)
            if nk and nk not in norm_keys:
                norm_keys.append(nk)

        gsc_matches: List[Dict[str, Any]] = []
        bing_matches: List[Dict[str, Any]] = []
        for nk in norm_keys:
            url_bucket = by_url.setdefault(
                nk,
                {
                    "canonical_key": nk,
                    "aio_snapshot_count": 0,
                    "gsc_genai": gsc_by_url.get(nk),
                    "bing_ai": bing_by_url.get(nk),
                },
            )
            url_bucket["aio_snapshot_count"] += 1
            if nk in gsc_by_url:
                gsc_matches.append(gsc_by_url[nk])
                unique_matched_urls.add(nk)
            if nk in bing_by_url:
                bing_matches.append(bing_by_url[nk])
                unique_matched_urls.add(nk)

        has_gsc = bool(gsc_matches)
        has_bing = bool(bing_matches)
        if has_gsc:
            matched_gsc_count += 1
        if has_bing:
            matched_bing_count += 1

        snap_dict["canonical_url_keys"] = norm_keys
        snap_dict["has_gsc_genai_match"] = has_gsc
        snap_dict["has_bing_ai_match"] = has_bing
        snap_dict["gsc_genai"] = gsc_matches
        snap_dict["bing_ai"] = bing_matches
        joined_records.append(snap_dict)

    return {
        "joined_records": joined_records,
        "by_url": by_url,
        "summary": {
            "total_snapshots": len(joined_records),
            "matched_gsc_genai_snapshots": matched_gsc_count,
            "matched_bing_ai_snapshots": matched_bing_count,
            "unique_matched_urls": len(unique_matched_urls),
            "gsc_genai_csv_urls": len(gsc_by_url),
            "bing_ai_csv_urls": len(bing_by_url),
        },
    }


def _tenant_domains_for(tenant_id: str) -> List[str]:
    from pseofactory.tenant_facts import CANONICAL_TENANT_HOSTS

    host = CANONICAL_TENANT_HOSTS.get(str(tenant_id or "").strip().lower())
    return [host] if host else []
