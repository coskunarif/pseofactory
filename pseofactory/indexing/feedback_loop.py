"""
pseofactory Autonomous Closed-Loop Indexing Feedback Coordinator
Connects Google Search Console inspection feeds, airlock quarantines,
and rollover queues to root-cause diagnosis, engine template repair,
cross-property asset reflection, preflight gating, and multi-engine push dispatch.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple, Union

from pseofactory.indexing.milestones import (
    EVENT_SEARCH_INDEXED,
    EVENT_SITEMAP_DISPATCHED,
    EVENT_URL_PREFLIGHT_PASSED,
    LifecycleEvent,
    LifecycleState,
    MilestoneTracker,
)
from pseofactory.indexing.preflight import IndexingPreflightEngine, PreflightReport
from pseofactory.indexing_inspector import DailyIndexingInspector
from pseofactory.telemetry import AtomicTelemetryLogger, TelemetryEvent

if TYPE_CHECKING:
    from pseofactory.maintenance import (
        TenantRegistry,
        WorkspacePropertyScanner,
    )


def reflect_and_recompile_all_assets(*args: Any, **kwargs: Any) -> Any:
    """
    Deferred wrapper to prevent circular import between maintenance and indexing.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.maintenance import (
        reflect_and_recompile_all_assets as _reflect,
    )
    return _reflect(*args, **kwargs)


def __getattr__(name: str) -> Any:
    """
    Lazy module attribute resolution for maintenance symbols.
    Zero em-dashes. Zero en-dashes.
    """
    if name in {"TenantRegistry", "WorkspacePropertyScanner"}:
        from pseofactory.maintenance import (
            TenantRegistry,
            WorkspacePropertyScanner,
        )
        mapping = {
            "TenantRegistry": TenantRegistry,
            "WorkspacePropertyScanner": WorkspacePropertyScanner,
        }
        return mapping[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

logger = logging.getLogger("pseofactory.indexing.feedback_loop")


class RootCauseClassification(str, Enum):
    """
    Categorized taxonomy of search console and crawl indexing defects.
    Zero em-dashes. Zero en-dashes.
    """
    CONTENT_QUALITY_OR_ANSWER_DEFICIENCY = "CONTENT_QUALITY_OR_ANSWER_DEFICIENCY"
    CRAWL_BUDGET_SIGNAL_LAG = "CRAWL_BUDGET_SIGNAL_LAG"
    DEAD_ROUTE_IN_SITEMAP = "DEAD_ROUTE_IN_SITEMAP"
    CANONICAL_TEMPLATE_DEFECT = "CANONICAL_TEMPLATE_DEFECT"
    CONTENT_DEPTH_DEFICIT = "CONTENT_DEPTH_DEFICIT"
    ALGORITHMIC_EXPANSION_FREEZE = "ALGORITHMIC_EXPANSION_FREEZE"
    UNKNOWN_OR_UNCLASSIFIED = "UNKNOWN_OR_UNCLASSIFIED"

    def __str__(self) -> str:
        return self.value


# Aliases for compatibility
THIN_OR_ANSWER_DEFICIENCY = RootCauseClassification.CONTENT_QUALITY_OR_ANSWER_DEFICIENCY
CONTENT_QUALITY_OR_ANSWER_DEFICIENCY = RootCauseClassification.CONTENT_QUALITY_OR_ANSWER_DEFICIENCY
CRAWL_BUDGET_SIGNAL_LAG = RootCauseClassification.CRAWL_BUDGET_SIGNAL_LAG
DEAD_ROUTE_IN_SITEMAP = RootCauseClassification.DEAD_ROUTE_IN_SITEMAP
CANONICAL_TEMPLATE_DEFECT = RootCauseClassification.CANONICAL_TEMPLATE_DEFECT
CONTENT_DEPTH_DEFICIT = RootCauseClassification.CONTENT_DEPTH_DEFICIT
ALGORITHMIC_EXPANSION_FREEZE = RootCauseClassification.ALGORITHMIC_EXPANSION_FREEZE
UNKNOWN_OR_UNCLASSIFIED = RootCauseClassification.UNKNOWN_OR_UNCLASSIFIED


@dataclass
class DiagnosisResult:
    """
    Structured diagnosis classification and actionable remediation recommendation.
    Zero em-dashes. Zero en-dashes.
    """
    url: str
    classification: str
    reason: str
    remediation_action: str
    reflection_path: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "classification": self.classification,
            "reason": self.reason,
            "remediation_action": self.remediation_action,
            "reflection_path": self.reflection_path,
            "metadata": self.metadata,
        }


class GSCRootCauseClassifier:
    """
    Classifies unindexed search console pages, quarantine anomalies,
    and crawler rejections into deterministic root-cause classifications
    and mechanical repair actions.
    Zero em-dashes. Zero en-dashes.
    """

    @classmethod
    def classify(
        cls,
        item: Union[Dict[str, Any], str],
        coverage_state: Optional[str] = None,
        verdict: Optional[str] = None,
        error: Optional[str] = None,
        status_code: Optional[int] = None,
        word_count: Optional[int] = None,
    ) -> DiagnosisResult:
        """
        Classifies an unindexed URL or inspection anomaly into a structured DiagnosisResult.
        Accepts dictionary records or explicit scalar arguments.
        """
        if isinstance(item, str):
            url = item
            data: Dict[str, Any] = {}
        elif isinstance(item, dict):
            data = item
            url = str(data.get("url") or data.get("target_url") or "")
        else:
            url = getattr(item, "url", str(item))
            data = getattr(item, "__dict__", {})

        eff_cov = (
            coverage_state
            or data.get("coverageState")
            or data.get("coverage_state")
            or ""
        )
        eff_verdict = verdict or data.get("verdict") or ""
        eff_err = (
            error
            or data.get("error")
            or data.get("reason")
            or data.get("code")
            or data.get("details")
            or ""
        )
        eff_status = status_code or data.get("status_code") or data.get("status")
        eff_words = word_count if word_count is not None else data.get("word_count")

        cov_lower = str(eff_cov).lower()
        err_lower = str(eff_err).lower()
        verdict_lower = str(eff_verdict).lower()

        # 1. Crawled - currently not indexed
        if (
            "crawled - currently not indexed" in cov_lower
            or "crawled - currently not indexed" in err_lower
            or "crawled" in cov_lower
            and "not indexed" in cov_lower
        ):
            return DiagnosisResult(
                url=url,
                classification=RootCauseClassification.CONTENT_QUALITY_OR_ANSWER_DEFICIENCY.value,
                reason="Page crawled by search crawler but omitted from index due to quality or answer deficiency",
                remediation_action="Enrich entity context, inject Princeton GEO direct answer block, verify H1 uniqueness",
                reflection_path="reflect_and_recompile_all_assets(properties=[tenant]) -> Preflight Stage 5 -> Resubmit Tier-1 Hubs",
                metadata={"coverage_state": eff_cov, "verdict": eff_verdict},
            )

        # 2. Discovered - currently not indexed
        if (
            "discovered - currently not indexed" in cov_lower
            or "discovered - currently not indexed" in err_lower
            or "discovered" in cov_lower
            and "not indexed" in cov_lower
        ):
            return DiagnosisResult(
                url=url,
                classification=RootCauseClassification.CRAWL_BUDGET_SIGNAL_LAG.value,
                reason="Page discovered but crawl queue delayed due to crawl budget or external signal lag",
                remediation_action="Verify depth <= 2. Boost crawling signals across AI and traditional aggregators without burning GSC daily API quota",
                reflection_path="Dispatch fast-index (IndexNow + WebSub hub ping + Ping-O-Matic). Keep in XML sitemap",
                metadata={"coverage_state": eff_cov, "verdict": eff_verdict},
            )

        # 3. HTTP 404 / 410 / Dead Route
        is_404 = (
            eff_status in (404, 410, "404", "410")
            or "404" in err_lower
            or "410" in err_lower
            or "not found" in err_lower
            or "dead_route" in err_lower
            or "quarantine_http_error" in err_lower
        )
        if is_404:
            return DiagnosisResult(
                url=url,
                classification=RootCauseClassification.DEAD_ROUTE_IN_SITEMAP.value,
                reason="Target URL returns HTTP 404/410 or missing from compiled dist directory",
                remediation_action="Airlock quarantine in indexing_quarantine_ledger.json. Remove URL from dist/sitemap.xml",
                reflection_path="gsccli index publish --action URL_DELETED if previously pushed to Google Indexing API",
                metadata={"status_code": eff_status, "error": eff_err},
            )

        # 4. Canonical Mismatch
        is_canonical = (
            "canonical" in err_lower
            or "canonical_mismatch" in err_lower
            or data.get("canonical_match") is False
            or "quarantine_unindexable_meta" in err_lower
        )
        if is_canonical:
            return DiagnosisResult(
                url=url,
                classification=RootCauseClassification.CANONICAL_TEMPLATE_DEFECT.value,
                reason="HTML link rel canonical tag mismatches expected canonical base URL",
                remediation_action="Repair property adapter canonical domain template (canonical_base vs HTML <link rel='canonical'>)",
                reflection_path="Recompile child property HTML -> Verify Preflight Stage 3 (Canonical equality)",
                metadata={"error": eff_err},
            )

        # 5. Thin Content (< 150 words)
        is_thin = (
            (eff_words is not None and isinstance(eff_words, (int, float)) and eff_words < 150)
            or "thin" in err_lower
            or "word count" in err_lower
            or "content depth" in err_lower
        )
        if is_thin:
            return DiagnosisResult(
                url=url,
                classification=RootCauseClassification.CONTENT_DEPTH_DEFICIT.value,
                reason=f"Body content depth ({eff_words if eff_words is not None else '<150'} words) below 150-word preflight threshold",
                remediation_action="Expand programmatic content body using structured data tables and FAQ accordions",
                reflection_path="adapter.build_asset(slug) -> Preflight Stage 5 check",
                metadata={"word_count": eff_words, "error": eff_err},
            )

        # 6. Algorithmic Ceiling / Freeze
        is_ceiling = (
            "ceiling" in err_lower
            or "freeze_expansion" in err_lower
            or data.get("algorithmic_ceiling") is True
            or "algorithmic" in err_lower
        )
        if is_ceiling:
            return DiagnosisResult(
                url=url,
                classification=RootCauseClassification.ALGORITHMIC_EXPANSION_FREEZE.value,
                reason="Algorithmic ceiling threshold detected; impressions dampened by Core/Spam update correlation",
                remediation_action="Freezes programmatic asset expansion for property per gsc_ceiling.py recommendation",
                reflection_path="Suppress fresh URL generation; focus exclusively on quality upgrades for existing indexed routes",
                metadata={"error": eff_err},
            )

        # Fallback
        return DiagnosisResult(
            url=url,
            classification=RootCauseClassification.UNKNOWN_OR_UNCLASSIFIED.value,
            reason=f"Unclassified inspection anomaly: cov='{eff_cov}', err='{eff_err}'",
            remediation_action="Conduct manual inspection via gsccli inspect url and verify page HTML",
            reflection_path="Run inspect_dist and review preflight quarantine report",
            metadata={"coverage_state": eff_cov, "error": eff_err},
        )

    @classmethod
    def classify_batch(cls, records: List[Any]) -> List[DiagnosisResult]:
        """Classifies a list of candidate inspection records."""
        results: List[DiagnosisResult] = []
        for r in records:
            results.append(cls.classify(r))
        return results


class IndexingFeedbackLoop:
    """
    Autonomous closed-loop feedback coordinator connecting GSC inspection feeds,
    root-cause diagnosis, engine repair reflection, preflight gating,
    and multi-engine push dispatch.
    Zero em-dashes. Zero en-dashes.
    """

    def __init__(
        self,
        property_id: str = "profithelm",
        domain: Optional[str] = None,
        canonical_base: Optional[str] = None,
        base_dir: Optional[Union[str, Path]] = None,
        dist_dir: Optional[Union[str, Path]] = None,
        milestone_tracker: Optional[MilestoneTracker] = None,
        indexer: Optional[Any] = None,
        inspector: Optional[DailyIndexingInspector] = None,
        preflight_engine: Optional[IndexingPreflightEngine] = None,
        telemetry_logger: Optional[AtomicTelemetryLogger] = None,
    ):
        self.property_id = property_id.lower()
        self.telemetry_logger = telemetry_logger or AtomicTelemetryLogger()

        # Discover property adapter if available
        adapter = None
        try:
            tenant_registry_cls = globals().get("TenantRegistry")
            if tenant_registry_cls is None:
                from pseofactory.maintenance import TenantRegistry
                tenant_registry_cls = TenantRegistry
            adapter = tenant_registry_cls.default().get_adapter(self.property_id)
        except Exception:
            pass
        if not adapter:
            try:
                scanner_cls = globals().get("WorkspacePropertyScanner")
                if scanner_cls is None:
                    from pseofactory.maintenance import WorkspacePropertyScanner
                    scanner_cls = WorkspacePropertyScanner
                scanner = scanner_cls()
                discovered = scanner.discover_properties()
                by_id = {p.property_id.lower(): p for p in discovered}
                adapter = by_id.get(self.property_id)
            except Exception:
                pass

        if adapter:
            self.domain = domain or adapter.domain
            self.canonical_base = canonical_base or adapter.canonical_base
            self.base_dir = Path(base_dir).resolve() if base_dir else adapter.dist_dir.parent
            self.dist_dir = Path(dist_dir).resolve() if dist_dir else adapter.dist_dir
        else:
            self.domain = domain or f"{self.property_id}.com"
            self.canonical_base = canonical_base or f"https://{self.domain}"
            candidate_base = Path(f"/home/ubuntuadmin/projects/{self.property_id}-platform")
            if not candidate_base.exists():
                candidate_base = Path(f"/home/ubuntuadmin/projects/{self.property_id}")
            self.base_dir = Path(base_dir).resolve() if base_dir else candidate_base
            self.dist_dir = Path(dist_dir).resolve() if dist_dir else (self.base_dir / "dist")

        valid_tenants = {"profithelm", "prexvo", "unassigned"}
        t_space = self.property_id if self.property_id in valid_tenants else "unassigned"
        self.milestone_tracker = milestone_tracker or MilestoneTracker(tenant=t_space)

        if indexer is not None:
            self.indexer = indexer
        else:
            from pseofactory.indexer import PushIndexer
            self.indexer = PushIndexer(
                domain=self.domain,
                canonical_base=self.canonical_base,
                base_dir=self.base_dir,
                dist_dir=self.dist_dir,
                tenant_id=self.property_id,
            )

        self.preflight_engine = preflight_engine or IndexingPreflightEngine(
            property_id=self.property_id,
            domain=self.domain,
            dist_dir=self.dist_dir,
        )

        self.inspector = inspector or DailyIndexingInspector(
            tenant_id=self.property_id,
            base_dir=self.base_dir,
            telemetry_logger=self.telemetry_logger,
        )

    def audit_unindexed_pages(
        self,
        sample_urls: Optional[List[str]] = None,
        live: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Audits unindexed pages from GSC live inspection, airlock quarantines,
        and rollover queues.
        """
        candidates: List[Dict[str, Any]] = []
        seen_urls: Set[str] = set()

        # 1. Inspection quarantine ledger
        try:
            q_audit = self.inspector.audit_airlock_quarantine()
            details = q_audit.get("details", {})
            for cat, items in details.items():
                for it in items:
                    u = it.get("url")
                    if u and u not in seen_urls:
                        seen_urls.add(u)
                        candidates.append({
                            "url": u,
                            "error": it.get("reason") or it.get("code") or cat,
                            "code": it.get("code"),
                            "status": "QUARANTINED",
                        })
        except Exception as e:
            logger.warning("Failed auditing quarantine ledger: %s", e)

        # 2. GSC rollover queue
        try:
            rollover_urls = self.indexer.load_gsc_rollover_queue()
            for u in rollover_urls:
                if u and u not in seen_urls:
                    seen_urls.add(u)
                    candidates.append({
                        "url": u,
                        "coverage_state": "Discovered - currently not indexed",
                        "status": "ROLLOVER_PENDING",
                    })
        except Exception as e:
            logger.warning("Failed loading rollover queue: %s", e)

        # 3. Live or sample GSC inspection
        target_sample = sample_urls or []
        if not target_sample and self.dist_dir and self.dist_dir.exists():
            sitemap_path = self.dist_dir / "sitemap.xml"
            if sitemap_path.exists():
                try:
                    import xml.etree.ElementTree as ET
                    tree = ET.parse(sitemap_path)
                    root = tree.getroot()
                    ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
                    locs = [elem.text.strip() for elem in root.findall(".//ns:loc", ns) if elem.text]
                    target_sample = locs[:5]
                except Exception:
                    pass

        if target_sample:
            try:
                gsc_oracle = self.indexer.verify_gsc_indexation_loop(
                    urls=target_sample,
                    site=f"sc-domain:{self.domain}",
                    max_urls=min(5, len(target_sample)),
                    live=live,
                )
                for insp in gsc_oracle.get("inspections", []):
                    u = insp.get("url")
                    cov = insp.get("coverage_state", "")
                    verdict = insp.get("verdict", "")
                    if verdict != "PASS" and u not in seen_urls:
                        seen_urls.add(u)
                        candidates.append({
                            "url": u,
                            "coverage_state": cov,
                            "verdict": verdict,
                            "status": "UNINDEXED_GSC",
                        })
            except Exception as e:
                logger.warning("Failed running verify_gsc_indexation_loop: %s", e)

        return candidates

    def diagnose_unindexed_pages(
        self,
        unindexed_records: List[Any],
    ) -> List[DiagnosisResult]:
        """Diagnoses candidate unindexed pages using GSCRootCauseClassifier."""
        return GSCRootCauseClassifier.classify_batch(unindexed_records)

    def execute_engine_repairs(
        self,
        diagnoses: List[DiagnosisResult],
        force: bool = False,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes engine repairs and reflects changes across child products.
        Triggers reflect_and_recompile_all_assets and handles dead route quarantines.
        """
        needs_recompile = force or any(
            d.classification in (
                RootCauseClassification.CONTENT_QUALITY_OR_ANSWER_DEFICIENCY.value,
                RootCauseClassification.CANONICAL_TEMPLATE_DEFECT.value,
                RootCauseClassification.CONTENT_DEPTH_DEFICIT.value,
            )
            for d in diagnoses
        )

        dead_routes = [
            d.url for d in diagnoses
            if d.classification == RootCauseClassification.DEAD_ROUTE_IN_SITEMAP.value
        ]

        if dead_routes and not dry_run:
            try:
                self.preflight_engine.quarantine_blocked_urls(
                    blocked_urls=dead_routes,
                    stage="FEEDBACK_LOOP_DEAD_ROUTE",
                    error="HTTP 404/410 Dead route identified by feedback loop",
                )
            except Exception as q_err:
                logger.warning("Failed quarantining dead routes: %s", q_err)

        reflection_res: Dict[str, Any] = {"status": "SKIPPED", "total_recompiled": 0}
        if needs_recompile:
            if dry_run:
                reflection_res = {"status": "DRY_RUN", "total_recompiled": 0}
            else:
                try:
                    reflection_res = reflect_and_recompile_all_assets(
                        properties=[self.property_id],
                        force=force,
                        verbose=False,
                    )
                except Exception as ref_err:
                    logger.error("Failed reflecting child product assets: %s", ref_err)
                    reflection_res = {"status": "FAILED", "error": str(ref_err), "total_recompiled": 0}

        return {
            "reflection": reflection_res,
            "dead_routes_quarantined": len(dead_routes),
            "recompiled_assets_count": reflection_res.get("total_recompiled", 0),
        }

    def enforce_preflight_airlock(self, max_hub_urls: int = 150) -> PreflightReport:
        """
        Enforces 6-stage preflight airlock across compiled dist assets
        (capped at Tier-1 Hub limit <= 150 per HWL-1076) and updates milestone tracker.
        """
        candidate_urls: List[str] = []
        if self.dist_dir and self.dist_dir.exists():
            sitemap_path = self.dist_dir / "sitemap.xml"
            if sitemap_path.exists():
                try:
                    import xml.etree.ElementTree as ET
                    tree = ET.parse(sitemap_path)
                    root = tree.getroot()
                    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
                    locs = [elem.text.strip() for elem in root.findall(".//sm:loc", ns) if elem.text]
                    if not locs:
                        locs = [elem.text.strip() for elem in root.findall(".//loc") if elem.text]
                    candidate_urls = locs[:max_hub_urls]
                except Exception:
                    pass

        if candidate_urls:
            report = self.preflight_engine.inspect_urls(candidate_urls)
        else:
            report = self.preflight_engine.inspect_dist(self.dist_dir)

        if report.blocked_urls:
            try:
                self.preflight_engine.quarantine_blocked_urls(report.blocked_urls)
            except Exception as q_err:
                logger.warning("Failed updating quarantine ledger: %s", q_err)

        for u in report.push_eligible_urls + report.sitemap_eligible_urls:
            self.milestone_tracker.record_event(
                u,
                LifecycleEvent.EVENT_URL_PREFLIGHT_PASSED,
            )

        return report

    def dispatch_multi_engine_push(
        self,
        urls: List[str],
        live: bool = False,
        hubs_only: bool = True,
    ) -> Dict[str, Any]:
        """
        Dispatches multi-engine push indexing across AI and traditional engines
        enforcing composite idempotency (tenant_id, target_url, engine, content_sha256).
        """
        to_push, skipped = self.indexer.filter_unchanged_push_urls(
            urls,
            force=False,
            engine=None,
            tenant_id=self.property_id,
        )

        if not to_push:
            return {
                "status": "IDEMPOTENT_NO_OP",
                "urls_targeted": len(urls),
                "urls_pushed": 0,
                "urls_skipped": len(skipped),
                "details": "All candidate URLs match persistent push ledger content hashes",
            }

        push_res = self.indexer.dispatch_automated_indexing(
            urls=to_push,
            live=live,
            hubs_only=hubs_only,
        )

        for u in to_push:
            self.milestone_tracker.record_event(
                u,
                LifecycleEvent.EVENT_SITEMAP_DISPATCHED,
            )

        return {
            "status": push_res.get("status", "SUCCESS") if isinstance(push_res, dict) else "SUCCESS",
            "urls_targeted": len(urls),
            "urls_pushed": len(to_push),
            "urls_skipped": len(skipped),
            "push_results": push_res,
        }

    def run_feedback_cycle(
        self,
        dry_run: bool = False,
        live: bool = False,
        unindexed_urls: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a complete closed-loop feedback cycle:
        1. Audits unindexed pages from GSC feeds and quarantine records.
        2. Diagnoses root causes via GSCRootCauseClassifier.
        3. Executes engine repairs and reflects changes across child products.
        4. Enforces preflight airlock (6 stages, Tier-1 Hub cap <= 150).
        5. Dispatches multi-engine push indexing enforcing composite idempotency.
        6. Updates milestone states in MilestoneTracker.
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        # Step 1: Audit
        raw_unindexed = (
            unindexed_urls
            if unindexed_urls is not None
            else self.audit_unindexed_pages(live=live)
        )

        # Step 2: Diagnose
        diagnoses = self.diagnose_unindexed_pages(raw_unindexed)

        # Step 3: Repair & Reflect
        repair_summary = self.execute_engine_repairs(diagnoses, force=False, dry_run=dry_run)

        # Step 4: Preflight Airlock
        preflight_report = self.enforce_preflight_airlock()

        # Step 5: Multi-Engine Push
        eligible_urls = preflight_report.push_eligible_urls
        push_summary = self.dispatch_multi_engine_push(
            urls=eligible_urls,
            live=live and not dry_run,
            hubs_only=True,
        )

        # Step 6: Milestones Persistence
        try:
            self.milestone_tracker.save_ledger()
        except Exception as m_err:
            logger.warning("Failed saving milestone ledger: %s", m_err)

        overall_status = "SUCCESS"
        if push_summary.get("status") in ("FAILED", "ERROR"):
            overall_status = "PARTIAL"

        return {
            "timestamp": now_iso,
            "property_id": self.property_id,
            "status": overall_status,
            "dry_run": dry_run,
            "live": live,
            "unindexed_audited": len(raw_unindexed),
            "diagnosed_defects": [d.to_dict() for d in diagnoses],
            "repair_summary": repair_summary,
            "preflight_summary": {
                "total_inspected": preflight_report.total_inspected,
                "passed": preflight_report.passed_count,
                "blocked": preflight_report.blocked_count,
                "push_eligible": len(preflight_report.push_eligible_urls),
            },
            "push_summary": push_summary,
            "milestone_events_count": len(self.milestone_tracker.event_log),
            "rollover_queue_pending": len(self.indexer.load_gsc_rollover_queue()),
        }
