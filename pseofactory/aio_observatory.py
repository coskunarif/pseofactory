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

import json
import os
import re
import shutil
import sqlite3
import subprocess
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

DEFAULT_AIO_DB_PATH = Path("/home/ubuntuadmin/projects/.agy/runs/aio_observatory.db")
DEFAULT_WATCHLIST_PATH = Path("/home/ubuntuadmin/projects/.agy/aio_watchlist.json")
ENDPOINT_AIO = "anyapi.google.serp.ai_overview"
EVIDENCE_ENDPOINT = "google.serp.ai_overview.observatory"
MAX_AIO_COST_USD = "0.004"
DEFAULT_WINDOW_DAYS = 7

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


def treg_sampler(query: str, timeout: float = 120.0) -> Dict[str, Any]:
    """Live Google AI Overview sample via treg, with a hard per-call cost ceiling."""
    treg_bin = shutil.which("treg")
    if not treg_bin:
        raise RuntimeError("treg binary not found on PATH")
    proc = subprocess.run(
        [
            treg_bin,
            "call",
            ENDPOINT_AIO,
            "--method",
            "POST",
            "--data",
            json.dumps({"prompt": query}),
            "--header",
            f"X-Treg-Route-Max-Cost: {MAX_AIO_COST_USD}",
        ],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError(f"treg exit {proc.returncode}: {(proc.stderr or proc.stdout).strip()[:300]}")
    return parse_treg_aio_output(proc.stdout)


def load_watchlist(path: Optional[Path] = None, tenants: Optional[Sequence[str]] = None) -> List[Tuple[str, str]]:
    """
    (tenant, query) pairs: every tenant core-tool primary keyword, plus extra queries from
    .agy/aio_watchlist.json shaped {"<tenant_id>": ["query", ...]}.
    """
    from pseofactory.tenant_facts import TENANT_CORE_TOOLS_BY_ID

    pairs: List[Tuple[str, str]] = []
    for pid, tools in TENANT_CORE_TOOLS_BY_ID.items():
        for t in tools:
            kw = str(t.get("primary_keyword") or "").strip().lower()
            if kw:
                pairs.append((pid, kw))
    wl_path = path or DEFAULT_WATCHLIST_PATH
    if wl_path.is_file():
        extra = json.loads(wl_path.read_text(encoding="utf-8"))
        for pid, queries in (extra or {}).items():
            for q in queries or []:
                q = str(q).strip().lower()
                if q:
                    pairs.append((str(pid), q))
    seen = set()
    result = []
    for pid, q in pairs:
        if tenants and pid not in tenants:
            continue
        if (pid, q) not in seen:
            seen.add((pid, q))
            result.append((pid, q))
    return result


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
                    error TEXT
                )
                """
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_aio_query_time ON aio_snapshots(query, sampled_at)")

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    # -- writes --------------------------------------------------------------

    def record(self, tenant: str, query: str, payload: Optional[Dict[str, Any]], error: str = "", at: Optional[datetime] = None) -> str:
        sid = uuid.uuid4().hex
        stamp = (at or _now()).isoformat()
        with self._conn() as c:
            c.execute(
                "INSERT INTO aio_snapshots VALUES (?,?,?,?,?,?,?,?,?,?)",
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
                ),
            )
        return sid

    def sample(
        self,
        watchlist: Optional[Sequence[Tuple[str, str]]] = None,
        sampler: Optional[Sampler] = None,
        max_queries: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Take one AI Overview sample per watchlist query and store it."""
        pairs = list(watchlist if watchlist is not None else load_watchlist())
        if max_queries is not None:
            pairs = pairs[: max(0, int(max_queries))]
        fn = sampler or treg_sampler
        summary = {"sampled": 0, "found": 0, "errors": 0, "cost_usd": 0.0, "error_samples": []}
        for tenant, query in pairs:
            try:
                payload = fn(query)
            except Exception as exc:  # recorded as unknown, never as a miss
                self.record(tenant, query, None, error=str(exc)[:500] or exc.__class__.__name__)
                summary["errors"] += 1
                summary["error_samples"].append({"query": query, "error": str(exc)[:200]})
                continue
            self.record(tenant, query, payload)
            summary["sampled"] += 1
            summary["found"] += int(bool(payload.get("found")))
            summary["cost_usd"] = round(summary["cost_usd"] + float(payload.get("cost_usd") or 0.0), 6)
        return summary

    # -- reads ---------------------------------------------------------------

    def _rows(self, query: Optional[str] = None, window_days: float = DEFAULT_WINDOW_DAYS, now: Optional[datetime] = None) -> List[sqlite3.Row]:
        since = ((now or _now()) - timedelta(days=window_days)).isoformat()
        sql = "SELECT * FROM aio_snapshots WHERE error IS NULL AND sampled_at >= ?"
        args: List[Any] = [since]
        if query is not None:
            sql += " AND query = ?"
            args.append(query.strip().lower())
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
        return {
            "query": query.strip().lower(),
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

    def scoreboard(self, window_days: float = DEFAULT_WINDOW_DAYS, now: Optional[datetime] = None) -> Dict[str, Any]:
        """Per-tenant share of AI Overview samples that cite the tenant, over tracked queries."""
        rows = self._rows(None, window_days, now)
        by_tenant: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            t = by_tenant.setdefault(
                r["tenant"],
                {"queries": set(), "samples": 0, "aio_samples": 0, "cited_samples": 0, "cited_queries": set(), "competitors": Counter()},
            )
            t["queries"].add(r["query"])
            t["samples"] += 1
            if not r["found"]:
                continue
            t["aio_samples"] += 1
            doms = {normalize_domain(c.get("url", "")) for c in json.loads(r["citations"] or "[]")}
            doms.discard("")
            tenant_doms = _tenant_domains_for(r["tenant"])
            if any(_domain_matches(d, tenant_doms) for d in doms):
                t["cited_samples"] += 1
                t["cited_queries"].add(r["query"])
            t["competitors"].update(d for d in doms if not _domain_matches(d, tenant_doms))
        tenants = {}
        for pid, t in sorted(by_tenant.items()):
            tenants[pid] = {
                "queries_tracked": len(t["queries"]),
                "samples": t["samples"],
                "aio_presence_rate": round(t["aio_samples"] / t["samples"], 3) if t["samples"] else 0.0,
                "citation_share": round(t["cited_samples"] / t["aio_samples"], 3) if t["aio_samples"] else 0.0,
                "queries_citing_tenant": sorted(t["cited_queries"]),
                "top_competitor_domains": [{"domain": d, "samples": c} for d, c in t["competitors"].most_common(5)],
            }
        return {"window_days": window_days, "generated_at": (now or _now()).isoformat(), "tenants": tenants}


def _tenant_domains_for(tenant_id: str) -> List[str]:
    from pseofactory.tenant_facts import CANONICAL_TENANT_HOSTS

    host = CANONICAL_TENANT_HOSTS.get(str(tenant_id or "").strip().lower())
    return [host] if host else []
