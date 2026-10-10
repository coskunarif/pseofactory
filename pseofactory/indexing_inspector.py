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


class DailyIndexingInspector:
    """
    Automated inspector auditing search console indexing pipelines and route health.
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
        telemetry_logger: Optional[AtomicTelemetryLogger] = None,
    ):
        self.tenant_id = tenant_id.lower()
        self.base_dir = Path(base_dir).resolve() if base_dir else Path(f"/home/ubuntuadmin/projects/{self.tenant_id}-platform")
        if not self.base_dir.exists():
            alt_base = Path(f"/home/ubuntuadmin/projects/{self.tenant_id}")
            if alt_base.exists():
                self.base_dir = alt_base

        self.agy_dir = Path(agy_dir).resolve() if agy_dir else DEFAULT_AGY_DIR
        self.recovery_ledger_path = Path(recovery_ledger_path).resolve() if recovery_ledger_path else DEFAULT_METRIC_RECOVERY_LEDGER
        self.quarantine_ledger_path = Path(quarantine_ledger_path).resolve() if quarantine_ledger_path else DEFAULT_QUARANTINE_LEDGER
        self.velocity_ledger_path = Path(velocity_ledger_path).resolve() if velocity_ledger_path else DEFAULT_VELOCITY_LEDGER
        self.rollover_queue_path = Path(rollover_queue_path).resolve() if rollover_queue_path else DEFAULT_GSC_ROLLOVER_QUEUE
        self.telemetry_logger = telemetry_logger or AtomicTelemetryLogger()

    def audit_gsc_rollover_queue(self) -> Dict[str, Any]:
        """
        Audits Google Search Console rollover queue for backlog overflow (>200 URLs)
        and HTTP 429 quota exhaustion.
        """
        queue_path = self.rollover_queue_path
        if not queue_path.exists():
            # Check tenant-specific agy folder if global does not exist
            local_q = self.base_dir / ".agy" / "gsc_rollover_queue.json"
            if local_q.exists():
                queue_path = local_q

        queue_urls: List[str] = []
        if queue_path.exists():
            try:
                with open(queue_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        queue_urls = data
                    elif isinstance(data, dict):
                        queue_urls = data.get("urls", [])
            except Exception:
                queue_urls = []

        tenant_urls = [u for u in queue_urls if self.tenant_id in u.lower()] if queue_urls else []
        queue_size = len(tenant_urls) if tenant_urls else len(queue_urls)
        backlog_exceeded = queue_size > 200

        # Scan recent telemetry events for 429 quota exhaustion
        quota_exhausted = False
        quota_reasons = []
        try:
            recent_events = self.telemetry_logger.read_recent(limit=50, tenant_id=self.tenant_id)
            for ev in recent_events:
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
            "sample_urls": (tenant_urls or queue_urls)[:5],
            "queue_path": str(queue_path),
        }

    def audit_airlock_quarantine(self) -> Dict[str, Any]:
        """
        Audits preflight airlock quarantine anomalies including HTTP 404,
        thin content, robots disallow, redirect, and canonical mismatch.
        """
        q_path = self.quarantine_ledger_path
        if not q_path.exists():
            local_q = self.base_dir / ".agy" / "indexing_quarantine_ledger.json"
            if local_q.exists():
                q_path = local_q

        quarantined_records: Dict[str, Any] = {}
        if q_path.exists():
            try:
                with open(q_path, "r", encoding="utf-8") as f:
                    quarantined_records = json.load(f)
            except Exception:
                quarantined_records = {}

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
            # If multi-tenant ledger, filter to tenant domain/id if present
            url_str = details.get("url", url)
            if self.tenant_id not in url_str.lower() and "http" in url_str:
                # If neither url nor details match tenant and ledger is heterogeneous, skip
                if self.tenant_id not in str(details).lower():
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
        Returns list of quarantined URLs from airlock quarantine ledger.
        Zero em-dashes. Zero en-dashes.
        """
        q_path = self.quarantine_ledger_path
        if not q_path.exists():
            local_q = self.base_dir / ".agy" / "indexing_quarantine_ledger.json"
            if local_q.exists():
                q_path = local_q

        if not q_path.exists():
            return []

        try:
            with open(q_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    urls = []
                    for url, details in data.items():
                        if isinstance(details, dict):
                            urls.append(details.get("url", url))
                        else:
                            urls.append(url)
                    return urls
                elif isinstance(data, list):
                    return [str(u) for u in data]
        except Exception:
            return []
        return []

    def audit_velocity_stagnation(self, stagnation_threshold_hours: float = 336.0) -> Dict[str, Any]:
        """
        Audits velocity ledger for routes exhibiting time-to-first-crawl (TTFC)
        or indexing velocity stagnation exceeding 336.0 hours (14 days).
        """
        v_path = self.velocity_ledger_path
        if not v_path.exists():
            local_v = self.base_dir / ".agy" / "indexing_velocity_ledger.json"
            if local_v.exists():
                v_path = local_v

        routes: List[Dict[str, Any]] = []
        velocity_data: Dict[str, Any] = {}
        if v_path.exists():
            try:
                with open(v_path, "r", encoding="utf-8") as f:
                    velocity_data = json.load(f)
                    routes = velocity_data.get("routes", [])
            except Exception:
                routes = []

        stalled_routes: List[Dict[str, Any]] = []
        for r in routes:
            slug = r.get("slug", "")
            domain_url = r.get("domain_url", "")
            if self.tenant_id not in domain_url.lower() and self.tenant_id not in slug.lower():
                if routes and len(routes) > 1 and "http" in domain_url:
                    continue

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
            "routes_monitored": len(routes),
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

    def synthesize_remediation_prompts(self, audit_summary: Dict[str, Any]) -> List[str]:
        """Synthesizes grounded agy /goal prompt suggestions for detected anomalies."""
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

    def run_inspection(
        self,
        strict: bool = False,
        dry_run: bool = False,
        sample: bool = False,
        gsc_records: Optional[List[GSCDailyMetricRecord]] = None,
    ) -> Dict[str, Any]:
        """
        Executes complete Loop 3 inspection cycle across GSC rollover queue,
        airlock quarantine, velocity ledger, and search traffic trajectory.
        Persists findings to metric recovery ledger and emits telemetry.
        """
        rollover_report = self.audit_gsc_rollover_queue()
        quarantine_report = self.audit_airlock_quarantine()
        velocity_report = self.audit_velocity_stagnation()
        traffic_report = self.audit_search_traffic(gsc_records=gsc_records)

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
        }
        remediation_prompts = self.synthesize_remediation_prompts(audit_summary)

        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tenant_id": self.tenant_id,
            "audit_status": overall_status,
            "gsc_rollover": rollover_report,
            "airlock_quarantine": quarantine_report,
            "velocity_stagnation": velocity_report,
            "search_traffic": traffic_report,
            "remediation_prompts": remediation_prompts,
        }

        # Telemetry emission on anomalies
        if overall_status in ("WARN", "FAIL"):
            action = "ESCALATED" if strict else "RECORDED"
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
    )

    if getattr(args, "json", False):
        print(json.dumps(report, indent=2))
    else:
        status = report.get("audit_status", "UNKNOWN")
        print(f"[{status}] Daily Indexing Inspection for '{report.get('tenant_id')}':")
        print(f"  - Rollover Queue: size={report['gsc_rollover']['queue_size']}, quota_exhausted={report['gsc_rollover']['quota_exhausted']}")
        print(f"  - Quarantine: total={report['airlock_quarantine']['total_quarantined']}, 404s={report['airlock_quarantine']['breakdown'].get('HTTP_404', 0)}")
        print(f"  - Velocity: stalled={report['velocity_stagnation']['stalled_routes_count']}/{report['velocity_stagnation']['routes_monitored']}")
        if report.get("remediation_prompts"):
            print("  Suggested Remediation Prompts:")
            for prompt in report["remediation_prompts"]:
                print(f"    * {prompt}")

    if getattr(args, "strict", False) and report.get("audit_status") in ("FAIL", "WARN"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(handle_cli())
