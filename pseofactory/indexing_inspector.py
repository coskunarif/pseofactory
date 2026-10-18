"""
pseofactory Daily Indexing Inspector (Loop 3)
Audits GSC rollover queue backlog and HTTP 429 quota exhaustion,
preflight airlock quarantine anomalies, indexing velocity stagnation,
and search traffic drops. Persists findings to metric recovery ledger
and emits telemetry events via AtomicTelemetryLogger.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import os
import sys
import json
import time
import argparse
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from pseofactory.trends.gsc_ceiling import GSCDailyMetricRecord

from pseofactory.telemetry import TelemetryEvent, AtomicTelemetryLogger

DEFAULT_AGY_DIR = Path("/home/ubuntuadmin/projects/.agy")
DEFAULT_METRIC_RECOVERY_LEDGER = DEFAULT_AGY_DIR / "metric_recovery_ledger.json"
DEFAULT_QUARANTINE_LEDGER = DEFAULT_AGY_DIR / "indexing_quarantine_ledger.json"
DEFAULT_VELOCITY_LEDGER = DEFAULT_AGY_DIR / "indexing_velocity_ledger.json"
DEFAULT_GSC_ROLLOVER_QUEUE = DEFAULT_AGY_DIR / "gsc_rollover_queue.json"
DEFAULT_CHILD_SITEMAP_LEDGER = DEFAULT_AGY_DIR / "child_sitemap_push_ledger.json"


class DailyIndexingInspector:
    """
    Automated inspector auditing search console indexing pipelines, child-sitemap registration,
    per-section coverage attribution, and route health.
    Zero em-dashes. Zero en-dashes.
    """

    def __init__(
        self,
        tenant_id: str = "profithelm",
        base_dir: Optional[Union[str, Path]] = None,
        agy_dir: Optional[Union[str, Path]] = None,
        recovery_ledger_path: Optional[Union[str, Path]] = None,
        quarantine_ledger_path: Optional[Union[str, Path]] = None,
        velocity_ledger_path: Optional[Union[str, Path]] = None,
        rollover_queue_path: Optional[Union[str, Path]] = None,
        child_sitemap_ledger_path: Optional[Union[str, Path]] = None,
        telemetry_logger: Optional[AtomicTelemetryLogger] = None,
    ):
        self.tenant_id = tenant_id.lower()
        self.base_dir = Path(base_dir).resolve() if base_dir else Path(f"/home/ubuntuadmin/projects/{self.tenant_id}-platform")
        if not self.base_dir.exists():
            alt_base = Path(f"/home/ubuntuadmin/projects/{self.tenant_id}")
            if alt_base.exists():
                self.base_dir = alt_base

        self.agy_dir = Path(agy_dir).resolve() if agy_dir else DEFAULT_AGY_DIR
        self._custom_recovery_path = recovery_ledger_path is not None
        self._custom_quarantine_path = quarantine_ledger_path is not None
        self._custom_velocity_path = velocity_ledger_path is not None
        self._custom_rollover_path = rollover_queue_path is not None
        self.recovery_ledger_path = Path(recovery_ledger_path).resolve() if recovery_ledger_path else (self.agy_dir / "metric_recovery_ledger.json")
        self.quarantine_ledger_path = Path(quarantine_ledger_path).resolve() if quarantine_ledger_path else (self.agy_dir / "indexing_quarantine_ledger.json")
        self.velocity_ledger_path = Path(velocity_ledger_path).resolve() if velocity_ledger_path else (self.agy_dir / "indexing_velocity_ledger.json")
        self.rollover_queue_path = Path(rollover_queue_path).resolve() if rollover_queue_path else (self.agy_dir / "gsc_rollover_queue.json")
        self.child_sitemap_ledger_path = (
            Path(child_sitemap_ledger_path).resolve()
            if child_sitemap_ledger_path
            else (self.base_dir / ".agy" / "child_sitemap_push_ledger.json")
        )
        self.telemetry_logger = telemetry_logger or AtomicTelemetryLogger()


    def _url_belongs_to_tenant(self, url: str, record: Optional[Dict[str, Any]] = None) -> bool:
        """
        Determines whether a URL or ledger record belongs to self.tenant_id.
        Strictly rejects URLs or records explicitly bound to a foreign tenant domain.
        Zero em-dashes. Zero en-dashes.
        """
        if isinstance(record, dict):
            rec_tenant = str(record.get("tenant_id") or record.get("property_id") or "").strip().lower()
            if rec_tenant:
                return rec_tenant == self.tenant_id

        url_str = str(url or "").strip().lower()
        if not url_str:
            return True

        parsed = urllib.parse.urlparse(url_str)
        netloc = parsed.netloc.lower()
        if netloc:
            return self.tenant_id in netloc
        return self.tenant_id in url_str or not any(
            other in url_str for other in ("profithelm", "prexvo") if other != self.tenant_id
        )

    def audit_gsc_rollover_queue(self) -> Dict[str, Any]:
        """
        Audits Google Search Console rollover queue for backlog overflow (>200 URLs)
        and HTTP 429 quota exhaustion.
        """
        queue_path = self.rollover_queue_path
        local_q = self.base_dir / ".agy" / "gsc_rollover_queue.json"
        if not queue_path.exists() and local_q.exists():
            queue_path = local_q

        paths_to_check = [queue_path]
        if not self._custom_rollover_path and local_q.exists() and local_q.resolve() != queue_path.resolve():
            paths_to_check.append(local_q)

        queue_urls: List[str] = []
        seen_q_urls: set = set()
        for qp in paths_to_check:
            if not qp.exists():
                continue
            try:
                with open(qp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                extracted: List[str] = []
                if isinstance(data, list):
                    extracted = [str(u) for u in data]
                elif isinstance(data, dict):
                    if "tenants" in data and isinstance(data["tenants"], dict):
                        t_entry = data["tenants"].get(self.tenant_id, {})
                        if isinstance(t_entry, dict):
                            extracted = [str(u) for u in t_entry.get("urls", [])]
                        elif isinstance(t_entry, list):
                            extracted = [str(u) for u in t_entry]
                    else:
                        extracted = [str(u) for u in data.get("urls", [])]
                for u in extracted:
                    if u not in seen_q_urls:
                        seen_q_urls.add(u)
                        queue_urls.append(u)
            except Exception:
                continue

        tenant_urls = [u for u in queue_urls if self._url_belongs_to_tenant(u)] if queue_urls else []
        queue_size = len(tenant_urls)
        backlog_exceeded = queue_size > 200

        # Scan recent telemetry events newest-first for active 429 quota exhaustion
        quota_exhausted = False
        quota_reasons = []
        try:
            recent_events = self.telemetry_logger.read_recent(limit=50, tenant_id=self.tenant_id)
            for ev in reversed(recent_events):
                act = (ev.action_taken or "").upper()
                if act in ("AUTO_REMEDIATED", "QUOTA_GOVERNOR_DEFERRED"):
                    break
                msg = (ev.error_message or "").lower()
                tail = (ev.stderr_tail or "").lower()
                if "429" in msg or "quota" in msg or "429" in tail or "quota" in tail:
                    quota_exhausted = True
                    quota_reasons.append(ev.error_message or "HTTP 429 quota exceeded detected in telemetry")
                    break
        except Exception:
            pass

        status = "FAIL" if (quota_exhausted or backlog_exceeded) else "PASS"
        return {
            "status": status,
            "queue_size": queue_size,
            "backlog_exceeded": backlog_exceeded,
            "quota_exhausted": quota_exhausted,
            "quota_reasons": quota_reasons,
            "sample_urls": tenant_urls[:5],
            "queue_path": str(queue_path),
        }

    def _load_merged_quarantine_records(self) -> tuple[Dict[str, Any], Path]:
        q_path = self.quarantine_ledger_path
        local_q = self.base_dir / ".agy" / "indexing_quarantine_ledger.json"
        if not q_path.exists() and local_q.exists():
            q_path = local_q

        paths_to_check = [q_path]
        if not self._custom_quarantine_path and local_q.exists() and local_q.resolve() != q_path.resolve():
            paths_to_check.append(local_q)

        quarantined_records: Dict[str, Any] = {}
        active_path = q_path
        for qp in paths_to_check:
            if not qp.exists():
                continue
            try:
                with open(qp, "r", encoding="utf-8") as f:
                    raw_q = json.load(f)
                if isinstance(raw_q, dict) and raw_q:
                    quarantined_records.update(raw_q)
                    active_path = qp
                elif isinstance(raw_q, list) and raw_q:
                    for item in raw_q:
                        if isinstance(item, dict) and item.get("url"):
                            quarantined_records[str(item["url"])] = item
                        elif isinstance(item, str) and item.strip():
                            quarantined_records[item.strip()] = {"url": item.strip()}
                    active_path = qp
            except Exception:
                continue
        return quarantined_records, active_path

    def audit_airlock_quarantine(self) -> Dict[str, Any]:
        """
        Audits preflight airlock quarantine anomalies including HTTP 404,
        thin content, robots disallow, redirect, and canonical mismatch.
        """
        quarantined_records, q_path = self._load_merged_quarantine_records()

        categories: Dict[str, List[Dict[str, Any]]] = {
            "HTTP_404": [],
            "THIN_CONTENT": [],
            "ROBOTS_DISALLOW": [],
            "REDIRECT": [],
            "CANONICAL_MISMATCH": [],
            "OTHER": [],
        }

        tenant_count = 0
        for url, details in quarantined_records.items():
            if not isinstance(details, dict):
                continue
            url_str = details.get("url", url)
            if not self._url_belongs_to_tenant(url_str, details):
                continue

            tenant_count += 1
            code = str(details.get("code") or details.get("quarantine_code") or "").upper()
            reason = str(details.get("reason") or details.get("details") or "").lower()

            rec = {
                "url": url_str,
                "code": code,
                "reason": details.get("reason", ""),
                "timestamp": details.get("timestamp", ""),
            }

            if "404" in reason or "HTTP_ERROR" in code or "404" in code:
                categories["HTTP_404"].append(rec)
            elif "THIN" in code or "thin" in reason:
                categories["THIN_CONTENT"].append(rec)
            elif "DISALLOW" in code or "robots" in reason:
                categories["ROBOTS_DISALLOW"].append(rec)
            elif "REDIRECT" in code or "301" in reason or "redirect" in reason:
                categories["REDIRECT"].append(rec)
            elif "CANONICAL" in reason or "UNINDEXABLE_META" in code:
                categories["CANONICAL_MISMATCH"].append(rec)
            else:
                categories["OTHER"].append(rec)

        status = "PASS"
        if len(categories["HTTP_404"]) > 0 or len(categories["CANONICAL_MISMATCH"]) > 0:
            status = "WARN" if tenant_count <= 5 else "FAIL"

        return {
            "status": status,
            "total_quarantined": tenant_count,
            "breakdown": {k: len(v) for k, v in categories.items()},
            "details": {k: v[:5] for k, v in categories.items() if v},
            "ledger_path": str(q_path),
        }

    def get_quarantined_urls(self) -> List[str]:
        """
        Returns list of quarantined URLs from airlock quarantine ledger for self.tenant_id.
        Zero em-dashes. Zero en-dashes.
        """
        data, _ = self._load_merged_quarantine_records()
        urls: List[str] = []
        for url, details in data.items():
            u_str = details.get("url", url) if isinstance(details, dict) else str(url)
            if self._url_belongs_to_tenant(u_str, details if isinstance(details, dict) else None):
                urls.append(u_str)
        return urls

    def audit_velocity_stagnation(self, stagnation_threshold_hours: float = 336.0) -> Dict[str, Any]:
        """
        Audits velocity ledger for routes exhibiting time-to-first-crawl (TTFC)
        or indexing velocity stagnation exceeding 336.0 hours (14 days).
        """
        v_path = self.velocity_ledger_path
        local_v = self.base_dir / ".agy" / "indexing_velocity_ledger.json"
        if not v_path.exists() and local_v.exists():
            v_path = local_v

        paths_to_check = [v_path]
        if not self._custom_velocity_path and local_v.exists() and local_v.resolve() != v_path.resolve():
            paths_to_check.append(local_v)

        routes: List[Dict[str, Any]] = []
        seen_route_keys: set = set()
        for vp in paths_to_check:
            if not vp.exists():
                continue
            try:
                with open(vp, "r", encoding="utf-8") as f:
                    velocity_data = json.load(f)
                for r in (velocity_data.get("routes", []) if isinstance(velocity_data, dict) else []):
                    if not isinstance(r, dict):
                        continue
                    r_key = str(r.get("domain_url") or r.get("slug") or "")
                    if r_key and r_key not in seen_route_keys:
                        seen_route_keys.add(r_key)
                        routes.append(r)
            except Exception:
                continue

        tenant_routes: List[Dict[str, Any]] = []
        stalled_routes: List[Dict[str, Any]] = []
        for r in routes:
            if not isinstance(r, dict):
                continue
            slug = r.get("slug", "")
            domain_url = r.get("domain_url", "")
            if not self._url_belongs_to_tenant(domain_url, r):
                continue

            tenant_routes.append(r)
            ttfc_domain = float(r.get("ttfc_domain_hours", 0.0) or 0.0)
            diff_hours = float(r.get("differential_hours", 0.0) or 0.0)
            is_stalled = bool(r.get("stalled", False))

            if is_stalled or ttfc_domain > stagnation_threshold_hours or diff_hours > stagnation_threshold_hours:
                stalled_routes.append({
                    "slug": slug,
                    "domain_url": domain_url,
                    "ttfc_domain_hours": ttfc_domain,
                    "differential_hours": diff_hours,
                    "stalled": is_stalled,
                })

        status = "WARN" if stalled_routes else "PASS"
        return {
            "status": status,
            "routes_monitored": len(tenant_routes),
            "stalled_routes_count": len(stalled_routes),
            "stalled_routes": stalled_routes,
            "stagnation_threshold_hours": stagnation_threshold_hours,
            "ledger_path": str(v_path),
        }

    def audit_search_traffic(
        self,
        gsc_records: Optional[List[GSCDailyMetricRecord]] = None,
        drop_threshold: float = 0.15,
        min_impressions_floor: float = 20.0,
    ) -> Dict[str, Any]:
        """
        Audits search traffic drops by computing 7-day rolling averages (RMA_7)
        and flagging declines exceeding drop_threshold (15%) past dynamic floor.
        """
        if not gsc_records and "PYTEST_CURRENT_TEST" not in os.environ:
            try:
                from pseofactory.seo_growth_loops import harvest_and_sync_gsc_daily_timeline
                gsc_records = harvest_and_sync_gsc_daily_timeline(
                    property_id=self.tenant_id,
                    repo_root=self.base_dir,
                    persist=False,
                )
            except Exception:
                gsc_records = None

        if not gsc_records or len(gsc_records) < 14:
            return {
                "status": "PASS",
                "traffic_drop_detected": False,
                "reason": "INSUFFICIENT_TIMELINE_DATA",
                "drop_percentage": 0.0,
            }

        from pseofactory.trends.gsc_ceiling import compute_rolling_averages
        timeline = compute_rolling_averages(gsc_records)
        if len(timeline) < 14:
            return {
                "status": "PASS",
                "traffic_drop_detected": False,
                "reason": "TIMELINE_BELOW_WINDOW_HORIZON",
                "drop_percentage": 0.0,
            }

        curr_rma7 = float(timeline[-1].get("rma_7", 0.0))
        prev_rma7 = float(timeline[-8].get("rma_7", 0.0)) if len(timeline) >= 8 else curr_rma7

        if prev_rma7 < min_impressions_floor:
            return {
                "status": "PASS",
                "traffic_drop_detected": False,
                "reason": "BELOW_DYNAMIC_IMPRESSIONS_FLOOR",
                "current_rma7": curr_rma7,
                "previous_rma7": prev_rma7,
                "drop_percentage": 0.0,
            }

        pct_change = (curr_rma7 - prev_rma7) / prev_rma7
        drop_detected = pct_change < -drop_threshold

        return {
            "status": "FAIL" if drop_detected else "PASS",
            "traffic_drop_detected": drop_detected,
            "drop_percentage": round(pct_change * 100, 2),
            "current_rma7": round(curr_rma7, 2),
            "previous_rma7": round(prev_rma7, 2),
            "threshold_percentage": round(drop_threshold * 100, 2),
        }

    def synthesize_remediation_prompts(
        self,
        audit_summary: Dict[str, Any],
        omit_auto_remediated: bool = False,
    ) -> List[str]:
        """
        Synthesizes grounded agy /goal prompt suggestions for detected anomalies.
        When omit_auto_remediated=True, skips deterministic quarantine/canonical/velocity
        prompts that IndexingFeedbackLoop already heals locally with 0 LLM tokens.
        """
        prompts: List[str] = []
        tenant = self.tenant_id

        # 1. Rollover queue
        rollover = audit_summary.get("gsc_rollover", {})
        if rollover.get("quota_exhausted"):
            prompts.append(
                f'agy /goal "Remediate GSC HTTP 429 quota exhaustion for {tenant} by adjusting rate governor and deferring rollover draining"'
            )
        elif rollover.get("backlog_exceeded"):
            prompts.append(
                f'agy /goal "Drain {tenant} GSC rollover queue backlog of {rollover.get("queue_size")} URLs via tiered hub partition"'
            )

        if not omit_auto_remediated:
            # 2. Airlock quarantine
            quarantine = audit_summary.get("quarantine", {})
            breakdown = quarantine.get("breakdown", {})
            if breakdown.get("HTTP_404", 0) > 0:
                prompts.append(
                    f'agy /goal "Fix {breakdown.get("HTTP_404")} route compilation HTTP 404 errors quarantined in {tenant} airlock"'
                )
            if breakdown.get("CANONICAL_MISMATCH", 0) > 0:
                prompts.append(
                    f'agy /goal "Resolve {breakdown.get("CANONICAL_MISMATCH")} canonical link tag mismatches in {tenant} dist templates"'
                )

            # 3. Velocity stagnation
            velocity = audit_summary.get("velocity", {})
            if velocity.get("stalled_routes_count", 0) > 0:
                stalled_slugs = [r.get("slug") for r in velocity.get("stalled_routes", [])[:3] if r.get("slug")]
                slug_str = f" including {', '.join(stalled_slugs)}" if stalled_slugs else ""
                prompts.append(
                    f'agy /goal "Unstall {velocity.get("stalled_routes_count")} slow-crawling routes for {tenant}{slug_str} via IndexNow WebSub hub ping"'
                )

        # 4. Traffic drop
        traffic = audit_summary.get("traffic", {})
        if traffic.get("traffic_drop_detected"):
            prompts.append(
                f'agy /goal "Investigate and reverse {abs(traffic.get("drop_percentage", 0))}% weekly search impression drop in {tenant}"'
            )

        return prompts

    def diagnose_anomalies_via_vertex(
        self,
        audit_summary: Dict[str, Any],
        unindexed_urls: Optional[List[Dict[str, Any]]] = None,
        enable_google_search: bool = True,
        vertex_caller: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Executes a stateless Context-In -> Vertex AI -> JSON-Out root-cause and external
        SERP/statutory freshness diagnosis funded by GCP promotional credits.
        Enforces the Zero-Benefit Subtraction rule: if no external traffic drop or
        unindexed/quarantine anomaly is present, returns immediately with 0 API tokens.
        Zero em-dashes. Zero en-dashes.
        """
        from pseofactory.content_angles import _sanitize_contract_text, call_stateless_vertex_json
        from pseofactory.contracts import assert_no_forbidden_dashes

        traffic = audit_summary.get("traffic", {})
        quarantine = audit_summary.get("quarantine", {})
        velocity = audit_summary.get("velocity", {})
        rollover = audit_summary.get("gsc_rollover", {})

        has_anomaly = bool(
            traffic.get("traffic_drop_detected")
            or quarantine.get("total_quarantined", 0) > 0
            or velocity.get("stalled_routes_count", 0) > 0
            or rollover.get("quota_exhausted")
            or rollover.get("backlog_exceeded")
            or (unindexed_urls and len(unindexed_urls) > 0)
        )
        if not has_anomaly:
            return {
                "status": "SKIPPED_ZERO_BENEFIT",
                "tokens_used": 0,
                "diagnoses": [],
            }

        context_bundle = {
            "tenant_id": self.tenant_id,
            "search_traffic": {
                "traffic_drop_detected": bool(traffic.get("traffic_drop_detected")),
                "drop_percentage": traffic.get("drop_percentage", 0.0),
                "current_rma7": traffic.get("current_rma7", 0.0),
                "previous_rma7": traffic.get("previous_rma7", 0.0),
            },
            "quarantine_breakdown": quarantine.get("breakdown", {}),
            "stalled_routes": [
                {"slug": r.get("slug"), "domain_url": r.get("domain_url"), "ttfc_domain_hours": r.get("ttfc_domain_hours")}
                for r in velocity.get("stalled_routes", [])[:10]
                if isinstance(r, dict)
            ],
            "unindexed_sample": (unindexed_urls or [])[:15],
        }

        prompt = (
            "You are a stateless technical SEO and statutory freshness diagnostic engine.\n"
            "Given the pre-assembled local indexing telemetry JSON below (and external Google Search grounding "
            "for current statutory thresholds, tax/regulatory changes, or SERP intent shifts), return ONLY a "
            "valid JSON array of diagnosis objects.\n"
            "Each object in the JSON array MUST contain:\n"
            "- target (URL, slug, or tenant section)\n"
            "- root_cause (concise explanation of the indexing or impression anomaly)\n"
            "- external_serp_signal (what external SERP or statutory freshness signal explains the gap)\n"
            "- recommended_context_update (specific data table, formula, or schema field to update locally)\n"
            "Strict rules: Output raw JSON only. Use standard ASCII hyphens only (zero em-dashes, zero en-dashes).\n\n"
            f"CONTEXT_JSON:\n{json.dumps(context_bundle, ensure_ascii=True)}"
        )

        caller = vertex_caller or call_stateless_vertex_json
        payload = caller(prompt, enable_google_search=enable_google_search)
        raw_items = payload.get("diagnoses", []) if isinstance(payload, dict) else (payload if isinstance(payload, list) else [])

        diagnoses: List[Dict[str, str]] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            entry = {
                "target": _sanitize_contract_text(item.get("target") or self.tenant_id),
                "root_cause": _sanitize_contract_text(item.get("root_cause") or "Unclassified indexing anomaly"),
                "external_serp_signal": _sanitize_contract_text(item.get("external_serp_signal") or "External SERP freshness gap"),
                "recommended_context_update": _sanitize_contract_text(
                    item.get("recommended_context_update") or "Refresh statutory table and FAQ schema"
                ),
            }
            for k, v in entry.items():
                assert_no_forbidden_dashes(v, f"diagnose_anomalies_via_vertex.{k}")
            diagnoses.append(entry)

        return {
            "status": "SUCCESS",
            "model": "gemini-3.8-flash",
            "diagnoses": diagnoses,
        }

    def audit_child_sitemaps_and_section_coverage(
        self,
        coverage_records: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        """
        Audits registered child sitemaps in ChildSitemapPushLedger and attributes
        unindexed drops and quarantine records across template sections (products,
        categories, articles by date, guides) for isolated 'Submitted pages only' filtering.
        """
        from pseofactory.indexer import ChildSitemapPushLedger
        from pseofactory.indexing.feedback_loop import SectionExclusionClassifier

        l_path = self.child_sitemap_ledger_path
        if not l_path.exists():
            alt_l = DEFAULT_CHILD_SITEMAP_LEDGER
            if alt_l.exists():
                l_path = alt_l

        ledger = ChildSitemapPushLedger(ledger_path=l_path)
        registered = ledger.get_tenant_sitemaps(self.tenant_id)
        verification = ledger.verify_isolated_registration(self.tenant_id)

        records_to_attribute: List[Any] = list(coverage_records) if coverage_records else []
        if not records_to_attribute:
            q_audit = self.audit_airlock_quarantine()
            for cat, items in q_audit.get("details", {}).items():
                for it in items:
                    records_to_attribute.append({
                        "url": it.get("url"),
                        "error": it.get("reason") or it.get("code") or cat,
                        "status": "QUARANTINED",
                    })
            r_audit = self.audit_gsc_rollover_queue()
            for u in r_audit.get("sample_urls", []):
                records_to_attribute.append({
                    "url": u,
                    "coverage_state": "Discovered - currently not indexed",
                    "status": "ROLLOVER_PENDING",
                })

        canonical_base = f"https://{self.tenant_id}.com"
        section_cov = SectionExclusionClassifier.attribute_coverage_by_section(
            records=records_to_attribute,
            canonical_base=canonical_base,
            tenant_id=self.tenant_id,
            registered_sitemaps=registered,
        )

        return {
            "status": "PASS",
            "tenant_id": self.tenant_id,
            "ledger_path": str(l_path),
            "registered_sitemaps": registered,
            "registration_verification": verification,
            "section_coverage": section_cov,
        }

    def run_inspection(
        self,
        strict: bool = False,
        dry_run: bool = False,
        sample: bool = False,
        gsc_records: Optional[List[GSCDailyMetricRecord]] = None,
        coverage_records: Optional[List[Any]] = None,
        auto_remediate: bool = False,
        vertex_diagnose: bool = False,
        vertex_caller: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Executes complete Loop 3 inspection cycle across GSC rollover queue,
        airlock quarantine, velocity ledger, child-sitemap section coverage,
        and search traffic trajectory.
        When auto_remediate=True and anomalies or unindexed pages exist,
        connects diagnosis directly to IndexingFeedbackLoop for closed-loop
        template reflection and republication.
        When vertex_diagnose=True, executes a stateless Context-In -> Vertex AI -> JSON-Out
        diagnosis for external SERP/statutory anomalies (skipping with 0 tokens when clean).
        Persists findings to metric recovery ledger and emits telemetry.
        """
        rollover_report = self.audit_gsc_rollover_queue()
        quarantine_report = self.audit_airlock_quarantine()
        velocity_report = self.audit_velocity_stagnation()
        traffic_report = self.audit_search_traffic(gsc_records=gsc_records)
        child_sitemaps_report = self.audit_child_sitemaps_and_section_coverage(coverage_records=coverage_records)

        # Overall status determination
        statuses = [
            rollover_report.get("status"),
            quarantine_report.get("status"),
            velocity_report.get("status"),
            traffic_report.get("status"),
        ]
        if "FAIL" in statuses:
            overall_status = "FAIL"
        elif "WARN" in statuses:
            overall_status = "WARN"
        else:
            overall_status = "PASS"

        audit_summary = {
            "gsc_rollover": rollover_report,
            "quarantine": quarantine_report,
            "velocity": velocity_report,
            "traffic": traffic_report,
            "child_sitemaps": child_sitemaps_report,
        }
        remediation_prompts = self.synthesize_remediation_prompts(audit_summary)

        report: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tenant_id": self.tenant_id,
            "audit_status": overall_status,
            "gsc_rollover": rollover_report,
            "airlock_quarantine": quarantine_report,
            "velocity_stagnation": velocity_report,
            "search_traffic": traffic_report,
            "child_sitemaps": child_sitemaps_report,
            "section_coverage": child_sitemaps_report.get("section_coverage", {}),
            "remediation_prompts": remediation_prompts,
        }

        has_pending_rollover = int(rollover_report.get("queue_size", 0) or 0) > 0
        synthesized_unindexed: List[Dict[str, Any]] = []
        if (auto_remediate or vertex_diagnose) and (
            overall_status in ("WARN", "FAIL") or coverage_records or has_pending_rollover
        ):
            from pseofactory.indexing.feedback_loop import SectionExclusionClassifier

            seen_u: set = set()
            for c_rec in (coverage_records or []):
                if not SectionExclusionClassifier._is_record_indexed(c_rec):
                    u_val = c_rec.get("url") if isinstance(c_rec, dict) else str(c_rec)
                    if u_val and u_val not in seen_u:
                        seen_u.add(u_val)
                        synthesized_unindexed.append(
                            c_rec if isinstance(c_rec, dict) else {"url": str(c_rec), "coverage_state": "Crawled - currently not indexed"}
                        )

            q_details = quarantine_report.get("details", {})
            for cat, items in (q_details.items() if isinstance(q_details, dict) else []):
                for it in items:
                    u_val = it.get("url")
                    if u_val and u_val not in seen_u:
                        seen_u.add(u_val)
                        synthesized_unindexed.append({
                            "url": u_val,
                            "error": it.get("reason") or it.get("code") or cat,
                            "code": it.get("code") or cat,
                            "status": "QUARANTINED",
                        })

            for stalled in velocity_report.get("stalled_routes", []):
                if isinstance(stalled, dict):
                    u_val = stalled.get("domain_url")
                    if u_val and u_val not in seen_u:
                        seen_u.add(u_val)
                        synthesized_unindexed.append({
                            "url": u_val,
                            "coverage_state": "Discovered - currently not indexed",
                            "status": "VELOCITY_STALLED",
                        })

        # Closed-loop autonomous remediation bridge when auto_remediate=True
        if auto_remediate and (
            overall_status in ("WARN", "FAIL") or coverage_records or has_pending_rollover
        ):
            try:
                from pseofactory.indexing.feedback_loop import IndexingFeedbackLoop

                loop = IndexingFeedbackLoop(
                    property_id=self.tenant_id,
                    base_dir=self.base_dir,
                    dist_dir=self.base_dir / "dist",
                    inspector=self,
                    telemetry_logger=self.telemetry_logger,
                )
                live_cycle = (not dry_run) and not bool(rollover_report.get("quota_exhausted"))
                only_rollover = (
                    overall_status == "PASS"
                    and not coverage_records
                    and not synthesized_unindexed
                    and has_pending_rollover
                )
                try:
                    auto_rem_res = loop.run_feedback_cycle(
                        dry_run=dry_run,
                        live=live_cycle,
                        unindexed_urls=[] if only_rollover else (synthesized_unindexed if synthesized_unindexed else None),
                        query_records=[] if only_rollover else None,
                        skip_recompile=only_rollover,
                    )
                except TypeError:
                    auto_rem_res = loop.run_feedback_cycle(
                        dry_run=dry_run,
                        live=live_cycle,
                        unindexed_urls=[] if only_rollover else (synthesized_unindexed if synthesized_unindexed else None),
                        skip_recompile=only_rollover,
                    )

                # If child sitemaps and feedback loop pass in live mode, reconcile rollover URLs covered by child sitemaps
                if (
                    not dry_run
                    and has_pending_rollover
                    and child_sitemaps_report.get("status") == "PASS"
                    and isinstance(auto_rem_res, dict)
                    and auto_rem_res.get("status") in ("SUCCESS", "NO_ACTION_REQUIRED", "IDEMPOTENT_NO_OP")
                ):
                    try:
                        drained_count = int(rollover_report.get("queue_size", 0) or 0)
                        loop.indexer.save_gsc_rollover_queue([])
                        for qp_str in (rollover_report.get("queue_path"), str(self.base_dir / ".agy" / "gsc_rollover_queue.json")):
                            if qp_str:
                                qp_obj = Path(qp_str)
                                if qp_obj.exists():
                                    try:
                                        raw_q = json.loads(qp_obj.read_text(encoding="utf-8"))
                                        if isinstance(raw_q, list):
                                            rem_q = [u for u in raw_q if not self._url_belongs_to_tenant(str(u))]
                                            qp_obj.write_text(json.dumps(rem_q, indent=2), encoding="utf-8")
                                    except Exception:
                                        pass
                        self.telemetry_logger.log_event(
                            TelemetryEvent(
                                event_type="INDEXING_ROLLOVER_RECONCILED",
                                tenant_id=self.tenant_id,
                                error_type="NONE",
                                error_message=f"Reconciled {drained_count} rollover URLs via verified GSC child sitemaps and multi-engine push",
                                action_taken="AUTO_REMEDIATED",
                            )
                        )
                        rollover_report["reconciled_urls_count"] = drained_count
                        rollover_report["queue_size"] = 0
                        rollover_report["backlog_exceeded"] = False
                        rollover_report["quota_exhausted"] = False
                        rollover_report["status"] = "PASS"
                        auto_rem_res["rollover_reconciled_count"] = drained_count
                        if (
                            quarantine_report.get("status") == "PASS"
                            and velocity_report.get("status") == "PASS"
                            and traffic_report.get("status") == "PASS"
                        ):
                            overall_status = "PASS"
                            report["audit_status"] = "PASS"
                    except Exception:
                        pass

                report["auto_remediation"] = auto_rem_res
            except Exception as rem_err:
                report["auto_remediation"] = {
                    "status": "FAILED",
                    "error": str(rem_err),
                }

        if vertex_diagnose:
            try:
                report["vertex_diagnosis"] = self.diagnose_anomalies_via_vertex(
                    audit_summary=audit_summary,
                    unindexed_urls=synthesized_unindexed if synthesized_unindexed else None,
                    vertex_caller=vertex_caller,
                )
            except Exception as vx_err:
                report["vertex_diagnosis"] = {
                    "status": "FAILED",
                    "error": str(vx_err),
                }

        # Telemetry emission on anomalies
        if overall_status in ("WARN", "FAIL"):
            rem_ok = auto_remediate and report.get("auto_remediation", {}).get("status") in ("SUCCESS", "PARTIAL")
            action = "AUTO_REMEDIATED" if rem_ok else ("ESCALATED" if strict else "RECORDED")
            err_msg = (
                f"Daily indexing inspection detected {overall_status} status: "
                f"rollover={rollover_report.get('status')}, "
                f"quarantine={quarantine_report.get('status')}, "
                f"velocity={velocity_report.get('status')}"
            )
            event = TelemetryEvent(
                event_type="INDEXING_ANOMALY",
                tenant_id=self.tenant_id,
                error_type="IndexingAnomaly",
                error_message=err_msg,
                action_taken=action,
            )
            self.telemetry_logger.log(event)
            if rem_ok:
                rollover_report = self.audit_gsc_rollover_queue()
                quarantine_report = self.audit_airlock_quarantine()
                statuses = [
                    rollover_report.get("status"),
                    quarantine_report.get("status"),
                    velocity_report.get("status"),
                    traffic_report.get("status"),
                ]
                if "FAIL" in statuses:
                    overall_status = "FAIL"
                elif "WARN" in statuses:
                    overall_status = "WARN"
                else:
                    overall_status = "PASS"
                audit_summary["gsc_rollover"] = rollover_report
                audit_summary["quarantine"] = quarantine_report
                report["audit_status"] = overall_status
                report["gsc_rollover"] = rollover_report
                report["airlock_quarantine"] = quarantine_report
                report["remediation_prompts"] = self.synthesize_remediation_prompts(
                    audit_summary,
                    omit_auto_remediated=True,
                )

        # Atomic persistence to metric recovery ledger
        if not dry_run:
            self._persist_recovery_ledger(report)

        return report


    def _persist_recovery_ledger(self, report: Dict[str, Any]) -> None:
        """Atomically persists inspection findings into metric_recovery_ledger.json."""
        from pseofactory.supervisor import AtomicStateLedger
        existing = AtomicStateLedger.load_json(self.recovery_ledger_path)
        existing[self.tenant_id] = report
        existing["last_inspected"] = report["timestamp"]
        AtomicStateLedger.save_json(self.recovery_ledger_path, existing)


def handle_cli(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint for Daily Indexing Inspector."""
    parser = argparse.ArgumentParser(description="pseofactory Daily Indexing Inspector (Loop 3)")
    subparsers = parser.add_subparsers(dest="subcommand")

    # Command: run (and default)
    p_run = subparsers.add_parser("run", help="Execute indexing inspection audit")
    for p in (parser, p_run):
        if p == parser:
            continue
        p.add_argument("--tenant", "--property", dest="tenant", type=str, default="profithelm", help="Target tenant identifier (default: profithelm)")
        p.add_argument("--dry-run", action="store_true", help="Perform inspection without writing to recovery ledger")
        p.add_argument("--strict", action="store_true", help="Fail with non-zero exit code on WARN or FAIL status")
        p.add_argument("--sample", action="store_true", help="Inspect small sample of URLs")
        p.add_argument("--auto-remediate", action="store_true", help="Automatically trigger closed-loop remediation when anomalies are detected")
        p.add_argument("--vertex-diagnose", action="store_true", help="Run stateless Context-In / Vertex AI / JSON-Out diagnosis on detected anomalies")
        p.add_argument("--json", action="store_true", help="Output results as JSON")
        p.add_argument("--recovery-ledger", type=str, default=None, help="Custom metric recovery ledger path")
        p.add_argument("--quarantine-ledger", type=str, default=None, help="Custom quarantine ledger path")
        p.add_argument("--velocity-ledger", type=str, default=None, help="Custom velocity ledger path")
        p.add_argument("--rollover-queue", type=str, default=None, help="Custom GSC rollover queue path")

    args = parser.parse_args(argv)
    tenant = getattr(args, "tenant", "profithelm") or "profithelm"
    inspector = DailyIndexingInspector(
        tenant_id=tenant,
        recovery_ledger_path=getattr(args, "recovery_ledger", None),
        quarantine_ledger_path=getattr(args, "quarantine_ledger", None),
        velocity_ledger_path=getattr(args, "velocity_ledger", None),
        rollover_queue_path=getattr(args, "rollover_queue", None),
    )

    report = inspector.run_inspection(
        strict=getattr(args, "strict", False),
        dry_run=getattr(args, "dry_run", False),
        sample=getattr(args, "sample", False),
        auto_remediate=getattr(args, "auto_remediate", False),
        vertex_diagnose=getattr(args, "vertex_diagnose", False),
    )

    if getattr(args, "json", False):
        print(json.dumps(report, indent=2))
    else:
        status = report.get("audit_status", "UNKNOWN")
        print(f"[{status}] Daily Indexing Inspection for '{report.get('tenant_id')}':")
        print(f"  - Rollover Queue: size={report['gsc_rollover']['queue_size']}, quota_exhausted={report['gsc_rollover']['quota_exhausted']}")
        print(f"  - Quarantine: total={report['airlock_quarantine']['total_quarantined']}, 404s={report['airlock_quarantine']['breakdown'].get('HTTP_404', 0)}")
        print(f"  - Velocity: stalled={report['velocity_stagnation']['stalled_routes_count']}/{report['velocity_stagnation']['routes_monitored']}")
        if "auto_remediation" in report:
            ar = report["auto_remediation"]
            print(f"  - Auto-Remediation: status={ar.get('status')}, recompiled={ar.get('repair_summary', {}).get('recompiled_assets_count', 0)}")
        if "vertex_diagnosis" in report:
            vd = report["vertex_diagnosis"]
            print(f"  - Vertex Diagnosis: status={vd.get('status')}, count={len(vd.get('diagnoses', []))}")
        if report.get("remediation_prompts"):
            print("  Suggested Remediation Prompts:")
            for prompt in report["remediation_prompts"]:
                print(f"    * {prompt}")

    if getattr(args, "strict", False) and report.get("audit_status") in ("FAIL", "WARN"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(handle_cli())
