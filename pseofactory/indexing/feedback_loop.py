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
from pseofactory.telemetry import AtomicTelemetryLogger, TelemetryEvent

if TYPE_CHECKING:
    from pseofactory.indexing_inspector import DailyIndexingInspector
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
    Lazy module attribute resolution for maintenance and inspector symbols.
    Zero em-dashes. Zero en-dashes.
    """
    if name == "DailyIndexingInspector":
        from pseofactory.indexing_inspector import DailyIndexingInspector
        return DailyIndexingInspector
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
    Structured diagnosis classification and actionable remediation recommendation,
    including template section and child-sitemap attribution for isolated
    'Submitted pages only' GSC coverage diagnostics.
    Zero em-dashes. Zero en-dashes.
    """
    url: str
    classification: str
    reason: str
    remediation_action: str
    reflection_path: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    section: str = "products"
    child_sitemap: str = "sitemap-products.xml"
    child_sitemap_url: str = ""
    date_bucket: Optional[str] = None
    submitted_pages_only_scope: str = "Submitted pages only (sitemap-products.xml)"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "classification": self.classification,
            "reason": self.reason,
            "remediation_action": self.remediation_action,
            "reflection_path": self.reflection_path,
            "section": self.section,
            "child_sitemap": self.child_sitemap,
            "child_sitemap_url": self.child_sitemap_url,
            "date_bucket": self.date_bucket,
            "submitted_pages_only_scope": self.submitted_pages_only_scope,
            "metadata": self.metadata,
        }


class GSCRootCauseClassifier:
    """
    Classifies unindexed search console pages, quarantine anomalies,
    and crawler rejections into deterministic root-cause classifications,
    template section attribution, and mechanical repair actions.
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
        canonical_base: Optional[str] = None,
        section_rules: Optional[Dict[str, Any]] = None,
    ) -> DiagnosisResult:
        """
        Classifies an unindexed URL or inspection anomaly into a structured DiagnosisResult
        mapped to its template section and child sitemap.
        Accepts dictionary records or explicit scalar arguments.
        """
        from pseofactory.indexer import classify_url_template_section

        if isinstance(item, str):
            url = item
            data: Dict[str, Any] = {}
        elif isinstance(item, dict):
            data = item
            url = str(data.get("url") or data.get("target_url") or "")
        else:
            url = getattr(item, "url", str(item))
            data = getattr(item, "__dict__", {})

        sec_info = classify_url_template_section(
            url,
            metadata=data,
            canonical_base=canonical_base,
            section_rules=section_rules,
        )
        section = sec_info["section"]
        child_sitemap = sec_info["child_sitemap"]
        child_sitemap_url = sec_info["child_sitemap_url"]
        date_bucket = sec_info.get("date_bucket")
        submitted_scope = f"Submitted pages only ({child_sitemap})"

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
        eff_status = (
            status_code
            or data.get("status_code")
            or data.get("http_status")
            or data.get("status")
        )
        eff_words = word_count if word_count is not None else data.get("word_count")

        cov_lower = str(eff_cov).lower()
        err_lower = str(eff_err).lower()

        base_meta: Dict[str, Any] = {
            "section": section,
            "child_sitemap": child_sitemap,
            "child_sitemap_url": child_sitemap_url,
            "date_bucket": date_bucket,
            "submitted_pages_only_scope": submitted_scope,
        }

        # Thin Content (< 150 words) takes precedence when word_count < 150 is explicitly measured
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
                reflection_path=f"adapter.build_asset(slug) -> Preflight Stage 5 check -> Refresh {child_sitemap}",
                metadata={**base_meta, "word_count": eff_words, "error": eff_err},
                section=section,
                child_sitemap=child_sitemap,
                child_sitemap_url=child_sitemap_url,
                date_bucket=date_bucket,
                submitted_pages_only_scope=submitted_scope,
            )

        # 1. Crawled - currently not indexed
        if (
            "crawled - currently not indexed" in cov_lower
            or "crawled - currently not indexed" in err_lower
            or ("crawled" in cov_lower and "not indexed" in cov_lower)
        ):
            return DiagnosisResult(
                url=url,
                classification=RootCauseClassification.CONTENT_QUALITY_OR_ANSWER_DEFICIENCY.value,
                reason="Page crawled by search crawler but omitted from index due to quality or answer deficiency",
                remediation_action="Enrich entity context, inject Princeton GEO direct answer block, verify H1 uniqueness",
                reflection_path=f"reflect_and_recompile_all_assets(properties=[tenant]) -> Preflight Stage 5 -> Resubmit {child_sitemap} and Tier-1 Hubs",
                metadata={**base_meta, "coverage_state": eff_cov, "verdict": eff_verdict},
                section=section,
                child_sitemap=child_sitemap,
                child_sitemap_url=child_sitemap_url,
                date_bucket=date_bucket,
                submitted_pages_only_scope=submitted_scope,
            )

        # 2. Discovered - currently not indexed
        if (
            "discovered - currently not indexed" in cov_lower
            or "discovered - currently not indexed" in err_lower
            or ("discovered" in cov_lower and "not indexed" in cov_lower)
        ):
            return DiagnosisResult(
                url=url,
                classification=RootCauseClassification.CRAWL_BUDGET_SIGNAL_LAG.value,
                reason="Page discovered but crawl queue delayed due to crawl budget or external signal lag",
                remediation_action="Verify depth <= 2. Boost crawling signals across AI and traditional aggregators without burning GSC daily API quota",
                reflection_path=f"Dispatch fast-index (IndexNow + WebSub hub ping + Ping-O-Matic). Keep in {child_sitemap}",
                metadata={**base_meta, "coverage_state": eff_cov, "verdict": eff_verdict},
                section=section,
                child_sitemap=child_sitemap,
                child_sitemap_url=child_sitemap_url,
                date_bucket=date_bucket,
                submitted_pages_only_scope=submitted_scope,
            )

        # 3. HTTP 404 / 410 / Dead Route
        is_404 = (
            eff_status in (404, 410, "404", "410")
            or "404" in err_lower
            or "410" in err_lower
            or "not found" in err_lower
            or "404" in cov_lower
            or "410" in cov_lower
            or "not found" in cov_lower
            or "dead_route" in err_lower
            or "quarantine_http_error" in err_lower
        )
        if is_404:
            return DiagnosisResult(
                url=url,
                classification=RootCauseClassification.DEAD_ROUTE_IN_SITEMAP.value,
                reason="Target URL returns HTTP 404/410 or missing from compiled dist directory",
                remediation_action=f"Airlock quarantine in indexing_quarantine_ledger.json. Remove URL from dist/sitemap.xml and dist/{child_sitemap}",
                reflection_path="gsccli index publish --action URL_DELETED if previously pushed to Google Indexing API",
                metadata={**base_meta, "status_code": eff_status, "error": eff_err},
                section=section,
                child_sitemap=child_sitemap,
                child_sitemap_url=child_sitemap_url,
                date_bucket=date_bucket,
                submitted_pages_only_scope=submitted_scope,
            )

        # 4. Canonical Mismatch
        user_canon = str(data.get("user_canonical") or "").strip().rstrip("/")
        google_canon = str(data.get("google_canonical") or "").strip().rstrip("/")
        is_canonical = (
            "canonical" in err_lower
            or "canonical_mismatch" in err_lower
            or "canonical" in cov_lower
            or data.get("canonical_match") is False
            or (bool(user_canon) and bool(google_canon) and user_canon != google_canon)
            or "quarantine_unindexable_meta" in err_lower
        )
        if is_canonical:
            return DiagnosisResult(
                url=url,
                classification=RootCauseClassification.CANONICAL_TEMPLATE_DEFECT.value,
                reason="HTML link rel canonical tag mismatches expected canonical base URL",
                remediation_action="Repair property adapter canonical domain template (canonical_base vs HTML <link rel='canonical'>)",
                reflection_path=f"Recompile child property HTML -> Verify Preflight Stage 3 (Canonical equality) -> Update {child_sitemap}",
                metadata={**base_meta, "error": eff_err},
                section=section,
                child_sitemap=child_sitemap,
                child_sitemap_url=child_sitemap_url,
                date_bucket=date_bucket,
                submitted_pages_only_scope=submitted_scope,
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
                metadata={**base_meta, "error": eff_err},
                section=section,
                child_sitemap=child_sitemap,
                child_sitemap_url=child_sitemap_url,
                date_bucket=date_bucket,
                submitted_pages_only_scope=submitted_scope,
            )

        # Fallback
        return DiagnosisResult(
            url=url,
            classification=RootCauseClassification.UNKNOWN_OR_UNCLASSIFIED.value,
            reason=f"Unclassified inspection anomaly: cov='{eff_cov}', err='{eff_err}'",
            remediation_action="Conduct manual inspection via gsccli inspect url and verify page HTML",
            reflection_path="Run inspect_dist and review preflight quarantine report",
            metadata={**base_meta, "coverage_state": eff_cov, "error": eff_err},
            section=section,
            child_sitemap=child_sitemap,
            child_sitemap_url=child_sitemap_url,
            date_bucket=date_bucket,
            submitted_pages_only_scope=submitted_scope,
        )

    @classmethod
    def classify_batch(
        cls,
        records: List[Any],
        canonical_base: Optional[str] = None,
        section_rules: Optional[Dict[str, Any]] = None,
    ) -> List[DiagnosisResult]:
        """Classifies a list of candidate inspection records."""
        results: List[DiagnosisResult] = []
        for r in records:
            results.append(
                cls.classify(
                    r,
                    canonical_base=canonical_base,
                    section_rules=section_rules,
                )
            )
        return results


class SectionExclusionClassifier:
    """
    Per-section Google Search Console coverage and exclusion classifier.
    Attributes indexed pages and unindexed drops ('Crawled - currently not indexed',
    'Discovered - currently not indexed', 404 dead routes, canonical mismatches, thin content)
    directly to their template section (products, categories, articles by date, guides)
    and explicitly submitted child sitemap for isolated 'Submitted pages only' GSC filtering.
    Zero em-dashes. Zero en-dashes.
    """

    @classmethod
    def _is_record_indexed(cls, item: Any) -> bool:
        if isinstance(item, dict):
            if "is_indexed" in item:
                return bool(item["is_indexed"])
            cov = str(item.get("coverageState") or item.get("coverage_state") or "").lower()
            verdict = str(item.get("verdict") or "").upper()
            status = str(item.get("status") or "").upper()
            if status in ("QUARANTINED", "ROLLOVER_PENDING", "UNINDEXED_GSC", "FAIL", "ERROR"):
                return False
            if "not indexed" in cov or "excluded" in cov or "error" in cov:
                return False
            if "submitted and indexed" in cov or verdict == "PASS":
                return True
        return False

    @classmethod
    def classify_exclusion(
        cls,
        item: Union[Dict[str, Any], str],
        canonical_base: Optional[str] = None,
        section_rules: Optional[Dict[str, Any]] = None,
        tenant_id: str = "profithelm",
    ) -> Dict[str, Any]:
        """
        Classifies a single unindexed URL or GSC exclusion record and maps it cleanly
        to its template section and child sitemap.
        """
        diag = GSCRootCauseClassifier.classify(
            item,
            canonical_base=canonical_base,
            section_rules=section_rules,
        )
        cov_state = str(diag.metadata.get("coverage_state") or "")
        is_crawled_not_indexed = (
            diag.classification == RootCauseClassification.CONTENT_QUALITY_OR_ANSWER_DEFICIENCY.value
        )
        is_discovered_not_indexed = (
            diag.classification == RootCauseClassification.CRAWL_BUDGET_SIGNAL_LAG.value
        )
        return {
            "tenant_id": str(tenant_id or "profithelm").strip().lower(),
            "url": diag.url,
            "section": diag.section,
            "child_sitemap": diag.child_sitemap,
            "child_sitemap_url": diag.child_sitemap_url,
            "date_bucket": diag.date_bucket,
            "submitted_pages_only_scope": diag.submitted_pages_only_scope,
            "classification": diag.classification,
            "coverage_state": cov_state or (
                "Crawled - currently not indexed"
                if is_crawled_not_indexed
                else ("Discovered - currently not indexed" if is_discovered_not_indexed else "Excluded")
            ),
            "is_crawled_not_indexed": is_crawled_not_indexed,
            "is_discovered_not_indexed": is_discovered_not_indexed,
            "reason": diag.reason,
            "remediation_action": diag.remediation_action,
            "reflection_path": diag.reflection_path,
        }

    @classmethod
    def attribute_coverage_by_section(
        cls,
        records: List[Any],
        canonical_base: Optional[str] = None,
        section_rules: Optional[Dict[str, Any]] = None,
        tenant_id: str = "profithelm",
        registered_sitemaps: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Aggregates GSC inspection/coverage records across template sections
        (products, categories, articles, guides) and individual child sitemaps
        (including date-bucketed article sitemaps), computing isolated
        'Submitted pages only' drop diagnostics.
        """
        from pseofactory.indexer import TEMPLATE_SITEMAP_SECTIONS, classify_url_template_section

        eff_tenant = str(tenant_id or "profithelm").strip().lower()
        reg_map = registered_sitemaps or {}
        reg_by_name = {
            (v.get("sitemap_name") if isinstance(v, dict) else str(k).split("/")[-1]): v
            for k, v in reg_map.items()
        }

        sections_report: Dict[str, Dict[str, Any]] = {}
        for sec in TEMPLATE_SITEMAP_SECTIONS:
            sections_report[sec] = {
                "section": sec,
                "child_sitemaps": [],
                "total_urls": 0,
                "indexed_count": 0,
                "unindexed_count": 0,
                "crawled_not_indexed_count": 0,
                "discovered_not_indexed_count": 0,
                "indexation_rate_pct": 100.0,
                "exclusion_breakdown": {},
                "dropped_urls": [],
                "crawled_not_indexed_urls": [],
                "discovered_not_indexed_urls": [],
                "diagnoses": [],
                "submitted_pages_only_ready": True,
            }

        by_child_sitemap: Dict[str, Dict[str, Any]] = {}
        unindexed_to_sitemap_map: Dict[str, str] = {}
        url_to_child_sitemap_url: Dict[str, str] = {}
        crawled_not_indexed_by_sitemap: Dict[str, List[str]] = {}

        for rec in records:
            is_indexed = cls._is_record_indexed(rec)
            if isinstance(rec, str):
                url = rec
                meta_in: Dict[str, Any] = {}
            elif isinstance(rec, dict):
                url = str(rec.get("url") or rec.get("target_url") or "")
                meta_in = rec
            else:
                url = getattr(rec, "url", str(rec))
                meta_in = getattr(rec, "__dict__", {})

            if not url:
                continue

            sec_info = classify_url_template_section(
                url,
                metadata=meta_in,
                canonical_base=canonical_base,
                section_rules=section_rules,
            )
            sec = sec_info["section"]
            sm_name = sec_info["child_sitemap"]
            sm_url = sec_info["child_sitemap_url"]
            d_bucket = sec_info.get("date_bucket")
            scope_str = f"Submitted pages only ({sm_name})"

            sec_bucket = sections_report.setdefault(
                sec,
                {
                    "section": sec,
                    "child_sitemaps": [],
                    "total_urls": 0,
                    "indexed_count": 0,
                    "unindexed_count": 0,
                    "crawled_not_indexed_count": 0,
                    "discovered_not_indexed_count": 0,
                    "indexation_rate_pct": 100.0,
                    "exclusion_breakdown": {},
                    "dropped_urls": [],
                    "crawled_not_indexed_urls": [],
                    "discovered_not_indexed_urls": [],
                    "diagnoses": [],
                    "submitted_pages_only_ready": True,
                },
            )
            if sm_name not in sec_bucket["child_sitemaps"]:
                sec_bucket["child_sitemaps"].append(sm_name)
            sec_bucket["total_urls"] += 1

            reg_entry = reg_map.get(sm_url) or reg_by_name.get(sm_name)
            explicitly_reg = bool(reg_entry.get("explicitly_submitted", True)) if isinstance(reg_entry, dict) else True

            sm_bucket = by_child_sitemap.setdefault(
                sm_name,
                {
                    "sitemap_name": sm_name,
                    "sitemap_url": sm_url,
                    "section": sec,
                    "date_bucket": d_bucket,
                    "submitted_pages_only_scope": scope_str,
                    "explicitly_submitted": explicitly_reg,
                    "total_urls": 0,
                    "indexed_count": 0,
                    "unindexed_count": 0,
                    "crawled_not_indexed_count": 0,
                    "discovered_not_indexed_count": 0,
                    "indexation_rate_pct": 100.0,
                    "exclusion_breakdown": {},
                    "dropped_urls": [],
                    "crawled_not_indexed_urls": [],
                    "discovered_not_indexed_urls": [],
                },
            )
            sm_bucket["total_urls"] += 1

            if is_indexed:
                sec_bucket["indexed_count"] += 1
                sm_bucket["indexed_count"] += 1
            else:
                excl = cls.classify_exclusion(
                    rec,
                    canonical_base=canonical_base,
                    section_rules=section_rules,
                    tenant_id=eff_tenant,
                )
                c_type = excl["classification"]
                sec_bucket["unindexed_count"] += 1
                sec_bucket["exclusion_breakdown"][c_type] = sec_bucket["exclusion_breakdown"].get(c_type, 0) + 1
                sec_bucket["dropped_urls"].append(url)
                sec_bucket["diagnoses"].append(excl)

                sm_bucket["unindexed_count"] += 1
                sm_bucket["exclusion_breakdown"][c_type] = sm_bucket["exclusion_breakdown"].get(c_type, 0) + 1
                sm_bucket["dropped_urls"].append(url)

                unindexed_to_sitemap_map[url] = sm_name
                url_to_child_sitemap_url[url] = sm_url

                if excl["is_crawled_not_indexed"]:
                    sec_bucket["crawled_not_indexed_count"] += 1
                    sec_bucket["crawled_not_indexed_urls"].append(url)
                    sm_bucket["crawled_not_indexed_count"] += 1
                    sm_bucket["crawled_not_indexed_urls"].append(url)
                    crawled_not_indexed_by_sitemap.setdefault(sm_name, []).append(url)
                elif excl["is_discovered_not_indexed"]:
                    sec_bucket["discovered_not_indexed_count"] += 1
                    sec_bucket["discovered_not_indexed_urls"].append(url)
                    sm_bucket["discovered_not_indexed_count"] += 1
                    sm_bucket["discovered_not_indexed_urls"].append(url)

        for sec_data in sections_report.values():
            tot = sec_data["total_urls"]
            idx_c = sec_data["indexed_count"]
            sec_data["indexation_rate_pct"] = round((idx_c / tot * 100.0), 2) if tot > 0 else 100.0

        for sm_data in by_child_sitemap.values():
            tot = sm_data["total_urls"]
            idx_c = sm_data["indexed_count"]
            sm_data["indexation_rate_pct"] = round((idx_c / tot * 100.0), 2) if tot > 0 else 100.0

        return {
            "tenant_id": eff_tenant,
            "total_records": len(records),
            "total_unindexed": len(unindexed_to_sitemap_map),
            "sections": sections_report,
            "by_child_sitemap": by_child_sitemap,
            "unindexed_to_sitemap_map": unindexed_to_sitemap_map,
            "url_to_child_sitemap_url": url_to_child_sitemap_url,
            "crawled_not_indexed_by_sitemap": crawled_not_indexed_by_sitemap,
        }


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
        gitops_coordinator: Optional[Any] = None,
    ):
        self.property_id = property_id.lower()
        self.telemetry_logger = telemetry_logger or AtomicTelemetryLogger()
        self.gitops_coordinator = gitops_coordinator

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

        if inspector is not None:
            self.inspector = inspector
        else:
            from pseofactory.indexing_inspector import DailyIndexingInspector
            self.inspector = DailyIndexingInspector(
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
        return GSCRootCauseClassifier.classify_batch(
            unindexed_records,
            canonical_base=self.canonical_base,
            section_rules=getattr(self.indexer, "section_rules", None),
        )

    def attribute_section_coverage(
        self,
        records: List[Any],
    ) -> Dict[str, Any]:
        """
        Attributes GSC coverage and unindexed drops across template sections
        (products, categories, articles by date, guides) and their explicitly submitted
        child sitemaps.
        """
        reg_sitemaps = None
        if hasattr(self.indexer, "child_sitemap_ledger"):
            try:
                reg_sitemaps = self.indexer.child_sitemap_ledger.get_tenant_sitemaps(self.property_id)
            except Exception:
                reg_sitemaps = None
        return SectionExclusionClassifier.attribute_coverage_by_section(
            records=records,
            canonical_base=self.canonical_base,
            section_rules=getattr(self.indexer, "section_rules", None),
            tenant_id=self.property_id,
            registered_sitemaps=reg_sitemaps,
        )

    def _prune_urls_from_sitemaps(self, dead_urls: List[str]) -> int:
        """
        Prunes dead/404 URLs from XML sitemaps in self.dist_dir so search crawlers
        do not waste crawl budget on quarantined routes.
        Zero em-dashes. Zero en-dashes.
        """
        if not dead_urls or not self.dist_dir or not self.dist_dir.exists():
            return 0
        import re
        dead_norm = {str(u).strip().rstrip("/") for u in dead_urls if u}
        pruned_count = 0
        for sm_path in sorted(self.dist_dir.glob("sitemap*.xml")):
            if not sm_path.is_file():
                continue
            try:
                content = sm_path.read_text(encoding="utf-8")
                def _filter_url_block(match: re.Match) -> str:
                    nonlocal pruned_count
                    block = match.group(0)
                    loc_m = re.search(r"<loc>\s*([^<\s]+)\s*</loc>", block, re.IGNORECASE)
                    if loc_m and loc_m.group(1).strip().rstrip("/") in dead_norm:
                        pruned_count += 1
                        return ""
                    return block
                updated = re.sub(r"\s*<url>.*?</url>", _filter_url_block, content, flags=re.DOTALL | re.IGNORECASE)
                if updated != content:
                    sm_path.write_text(updated, encoding="utf-8")
            except Exception as err:
                logger.warning("Failed pruning dead URLs from %s: %s", sm_path, err)
        return pruned_count

    def _apply_html_repairs_for_slug(
        self,
        slug: str,
        target_url: str,
        overlay_spec: Dict[str, Any],
    ) -> bool:
        """
        Applies template repairs (canonical tag alignment, viewport meta tag,
        robots indexability, H1 presence, and overlay quick-answer/depth/FAQ injection)
        directly to compiled HTML files in self.dist_dir.
        Zero em-dashes. Zero en-dashes.
        """
        if not self.dist_dir or not self.dist_dir.exists():
            return False
        import re
        import urllib.parse
        from pseofactory.gsc_remediation import inject_overlay_into_html

        candidates: List[Path] = []
        if target_url:
            parsed = urllib.parse.urlparse(target_url)
            rel_path = parsed.path.strip("/")
            if rel_path:
                candidates.append(self.dist_dir / rel_path / "index.html")
                candidates.append(self.dist_dir / f"{rel_path}.html")
            elif parsed.path == "/":
                candidates.append(self.dist_dir / "index.html")
        if slug:
            candidates.append(self.dist_dir / "tools" / slug / "index.html")
            candidates.append(self.dist_dir / slug / "index.html")
            candidates.append(self.dist_dir / f"{slug}.html")

        target_file: Optional[Path] = None
        for cand_p in candidates:
            if cand_p.is_file():
                target_file = cand_p
                break
        if target_file is None:
            return False

        try:
            raw_html = target_file.read_text(encoding="utf-8")
            expected_url = target_url
            if not expected_url or not expected_url.startswith("https://"):
                rel = target_file.relative_to(self.dist_dir).as_posix()
                if rel == "index.html":
                    u_path = "/"
                elif rel.endswith("/index.html"):
                    u_path = "/" + rel[:-11].strip("/") + "/"
                elif rel.endswith(".html"):
                    u_path = "/" + rel[:-5].strip("/") + "/"
                else:
                    u_path = "/" + rel.strip("/") + "/"
                expected_url = f"https://{self.domain}{u_path}"
            elif not expected_url.endswith("/") and not re.search(r"\.[a-zA-Z0-9]{2,5}$", expected_url):
                expected_url = expected_url + "/"

            repaired = raw_html
            # 1. Repair canonical tag to match expected_url
            canon_tag = f'<link rel="canonical" href="{expected_url}">'
            if re.search(r'<link\s+[^>]*rel=["\']canonical["\'][^>]*>', repaired, flags=re.IGNORECASE):
                repaired = re.sub(
                    r'<link\s+[^>]*rel=["\']canonical["\'][^>]*>',
                    "",
                    repaired,
                    flags=re.IGNORECASE,
                )
            if "</head>" in repaired:
                repaired = repaired.replace("</head>", f"  {canon_tag}\n</head>", 1)
            elif "<body" in repaired:
                repaired = f"<head>\n  {canon_tag}\n</head>\n" + repaired
            else:
                repaired = f"{canon_tag}\n" + repaired

            # 2. Ensure viewport meta tag exists
            if not re.search(r'<meta\s+[^>]*name=["\']viewport["\']', repaired, flags=re.IGNORECASE):
                vp_tag = '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
                if "</head>" in repaired:
                    repaired = repaired.replace("</head>", f"  {vp_tag}\n</head>", 1)

            # 3. Ensure title tag exists if missing
            title_val = str(overlay_spec.get("title_rewrite") or overlay_spec.get("title") or slug.replace("-", " ").title())
            if not re.search(r"<title>.*?</title>", repaired, flags=re.DOTALL | re.IGNORECASE):
                if "</head>" in repaired:
                    repaired = repaired.replace("</head>", f"  <title>{title_val}</title>\n</head>", 1)

            # 4. Scrub accidental noindex directives on remediated routes
            repaired = re.sub(
                r'(<meta\s+[^>]*name=["\']robots["\'][^>]*content=["\'])[^"\']*noindex[^"\']*(["\'])',
                r"\g<1>index, follow\g<2>",
                repaired,
                flags=re.IGNORECASE,
            )

            # 5. Ensure exactly one <h1> tag exists if missing
            if not re.search(r"<h1[\s>]", repaired, flags=re.IGNORECASE):
                h1_text = str(overlay_spec.get("query") or slug.replace("-", " ")).title()
                if "<main" in repaired:
                    repaired = re.sub(r"(<main[^>]*>)", rf"\g<1>\n<h1>{h1_text}</h1>", repaired, count=1, flags=re.IGNORECASE)
                elif "<body" in repaired:
                    repaired = re.sub(r"(<body[^>]*>)", rf"\g<1>\n<h1>{h1_text}</h1>", repaired, count=1, flags=re.IGNORECASE)

            # 6. Inject remediation overlay (quick answer, H2s, preset scenarios, comparison rows, FAQs, JSON-LD)
            repaired = inject_overlay_into_html(repaired, overlay_spec)

            target_file.write_text(repaired, encoding="utf-8")
            IndexingPreflightEngine.clear_cache()
            return True
        except Exception as err:
            logger.warning("Failed applying HTML repair to %s: %s", target_file, err)
            return False

    def execute_engine_repairs(
        self,
        diagnoses: List[DiagnosisResult],
        force: bool = False,
        dry_run: bool = False,
        prioritized_candidates: Optional[List[Dict[str, Any]]] = None,
        skip_recompile: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes engine repairs, writes rich remediation overlays to content/overlays/,
        applies template/overlay fixes directly to compiled HTML assets, prunes dead
        routes from sitemaps, handles CRAWL_BUDGET_SIGNAL_LAG, and reflects changes
        across child products.
        """
        from pseofactory.gsc_remediation import (
            _slug_from_url_or_query,
            compile_remediation_overlay_spec,
        )

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
        crawl_lag_urls = [
            d.url for d in diagnoses
            if d.classification == RootCauseClassification.CRAWL_BUDGET_SIGNAL_LAG.value
        ]

        sitemaps_pruned = 0
        if dead_routes and not dry_run:
            try:
                self.preflight_engine.quarantine_blocked_urls(
                    blocked_urls=dead_routes,
                    stage="FEEDBACK_LOOP_DEAD_ROUTE",
                    error="HTTP 404/410 Dead route identified by feedback loop",
                )
            except Exception as q_err:
                logger.warning("Failed quarantining dead routes: %s", q_err)
            sitemaps_pruned = self._prune_urls_from_sitemaps(dead_routes)

        overlays_written: List[str] = []
        html_files_repaired = 0
        repaired_slugs: Set[str] = set()

        if not dry_run and self.base_dir:
            overlays_dir = self.base_dir / "content" / "overlays"
            overlays_dir.mkdir(parents=True, exist_ok=True)

            # Write overlays for prioritized candidates if provided
            for cand in (prioritized_candidates or []):
                if not isinstance(cand, dict):
                    continue
                anom = str(cand.get("anomaly_type") or "").upper()
                if "DEAD_ROUTE" in anom:
                    continue
                c_slug = str(cand.get("slug") or "") or _slug_from_url_or_query(
                    target_url=str(cand.get("target_url") or ""),
                    query=str(cand.get("query") or ""),
                )
                spec = cand.get("overlay_spec")
                if not isinstance(spec, dict) or "title_rewrite" not in spec:
                    spec = compile_remediation_overlay_spec(cand, tenant_id=self.property_id)
                overlay_file = overlays_dir / f"{c_slug}.json"
                overlay_file.write_text(json.dumps(spec, indent=2), encoding="utf-8")
                if c_slug not in overlays_written:
                    overlays_written.append(c_slug)
                t_url = str(cand.get("target_url") or spec.get("target_url") or "")
                if c_slug not in repaired_slugs and self._apply_html_repairs_for_slug(c_slug, t_url, spec):
                    repaired_slugs.add(c_slug)
                    html_files_repaired += 1
                if "CRAWL_BUDGET" in anom and cand.get("target_url") and cand["target_url"] not in crawl_lag_urls:
                    crawl_lag_urls.append(str(cand["target_url"]))

            # Also ensure any direct diagnoses have rich overlay files written and HTML reflected
            for d in diagnoses:
                if d.classification == RootCauseClassification.DEAD_ROUTE_IN_SITEMAP.value:
                    continue
                d_slug = _slug_from_url_or_query(target_url=d.url)
                overlay_file = overlays_dir / f"{d_slug}.json"
                if overlay_file.exists():
                    try:
                        spec = json.loads(overlay_file.read_text(encoding="utf-8"))
                    except Exception:
                        spec = None
                else:
                    spec = None
                if not isinstance(spec, dict):
                    spec = compile_remediation_overlay_spec(
                        {
                            "tenant_id": self.property_id,
                            "slug": d_slug,
                            "target_url": d.url,
                            "anomaly_type": d.classification,
                            "section": d.section,
                            "child_sitemap": d.child_sitemap,
                            "action_type": (
                                "HUB_LINK_INJECTION"
                                if d.classification == RootCauseClassification.CRAWL_BUDGET_SIGNAL_LAG.value
                                else "REFACTOR_PAGE"
                            ),
                        },
                        tenant_id=self.property_id,
                    )
                    overlay_file.write_text(json.dumps(spec, indent=2), encoding="utf-8")
                    if d_slug not in overlays_written:
                        overlays_written.append(d_slug)
                if d_slug not in repaired_slugs and self._apply_html_repairs_for_slug(d_slug, d.url, spec):
                    repaired_slugs.add(d_slug)
                    html_files_repaired += 1

        crawl_lag_dispatched = len(crawl_lag_urls) > 0

        reflection_res: Dict[str, Any] = {"status": "SKIPPED", "total_recompiled": 0}
        if needs_recompile or (overlays_written and not skip_recompile):
            if dry_run:
                reflection_res = {"status": "DRY_RUN", "total_recompiled": 0}
            elif skip_recompile:
                reflection_res = {"status": "SKIPPED_FAST_PATH", "total_recompiled": max(len(overlays_written), html_files_repaired)}
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

        recompiled_count = max(int(reflection_res.get("total_recompiled", 0)), html_files_repaired)
        return {
            "reflection": reflection_res,
            "dead_routes_quarantined": len(dead_routes),
            "sitemaps_pruned": sitemaps_pruned,
            "overlays_written": overlays_written,
            "html_files_repaired": html_files_repaired,
            "crawl_lag_dispatched": crawl_lag_dispatched,
            "crawl_lag_urls": crawl_lag_urls,
            "recompiled_assets_count": recompiled_count,
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
        enforcing composite idempotency (tenant_id, target_url, engine, content_sha256)
        and explicit child-sitemap GSC registration.
        """
        to_push, skipped = self.indexer.filter_unchanged_push_urls(
            urls,
            force=False,
            engine=None,
            tenant_id=self.property_id,
        )

        if not to_push:
            sitemap_reg: Dict[str, Any] = {"status": "IDEMPOTENT_NO_OP", "submissions": []}
            if hasattr(self.indexer, "submit_gsc_sitemaps"):
                try:
                    sitemap_reg = self.indexer.submit_gsc_sitemaps(urls=urls, live=live)
                except Exception:
                    pass
            return {
                "status": "IDEMPOTENT_NO_OP",
                "urls_targeted": len(urls),
                "urls_pushed": 0,
                "urls_skipped": len(skipped),
                "child_sitemap_submissions": sitemap_reg.get("submissions", []),
                "sitemap_registration": sitemap_reg,
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

        sitemap_reg = (
            push_res.get("sitemap_registration")
            if isinstance(push_res, dict)
            else None
        ) or {"status": "SIMULATED", "submissions": []}

        return {
            "status": push_res.get("status", "SUCCESS") if isinstance(push_res, dict) else "SUCCESS",
            "urls_targeted": len(urls),
            "urls_pushed": len(to_push),
            "urls_skipped": len(skipped),
            "child_sitemap_submissions": sitemap_reg.get("submissions", []),
            "sitemap_registration": sitemap_reg,
            "push_results": push_res,
        }

    def run_feedback_cycle(
        self,
        dry_run: bool = False,
        live: bool = False,
        unindexed_urls: Optional[List[Any]] = None,
        unindexed_records: Optional[List[Any]] = None,
        query_records: Optional[List[Dict[str, Any]]] = None,
        remediation_queue: Optional[Any] = None,
        execution_budget_seconds: float = 300.0,
        skip_recompile: bool = False,
        enable_gitops: bool = False,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes a complete closed-loop feedback cycle:
        1. Audits unindexed pages from GSC feeds and quarantine records.
        2. Diagnoses root causes via GSCRootCauseClassifier and attributes coverage per section.
        3. Prioritizes across query records and unindexed diagnoses via ROI engine.
        4. Enqueues and executes engine repairs via AsyncRemediationQueue.
        5. Enforces preflight airlock (6 stages, Tier-1 Hub cap <= 150).
        6. Ships repaired assets via GitOpsCoordinator after preflight pass and before search dispatch.
        7. Dispatches multi-engine push indexing and explicit child-sitemap GSC registration.
        8. Updates milestone states in MilestoneTracker.
        """
        from pseofactory.gsc_remediation import (
            AsyncRemediationQueue,
            compile_remediation_overlay_spec,
            prioritize_gsc_signals,
        )

        now_iso = datetime.now(timezone.utc).isoformat()

        # Step 1: Audit
        eff_unindexed = unindexed_urls if unindexed_urls is not None else unindexed_records
        raw_unindexed = (
            eff_unindexed
            if eff_unindexed is not None
            else self.audit_unindexed_pages(live=live)
        )

        # Step 2: Diagnose & Attribute per-section coverage
        diagnoses = self.diagnose_unindexed_pages(raw_unindexed)

        # Step 3: ROI-Driven Prioritization across queries and unindexed diagnoses
        prioritized_candidates = prioritize_gsc_signals(
            tenant_id=self.property_id,
            query_records=query_records or [],
            unindexed_diagnoses=diagnoses,
        )

        queue_obj = remediation_queue
        if queue_obj is None and self.base_dir:
            queue_obj = AsyncRemediationQueue(
                queue_path=self.base_dir / ".agy" / "gsc_remediation_queue.json"
            )

        has_pending_queue = bool(
            queue_obj is not None
            and hasattr(queue_obj, "get_pending_tasks")
            and queue_obj.get_pending_tasks(self.property_id)
        )
        no_op_empty_queue = not raw_unindexed and not (query_records or []) and not has_pending_queue

        # Step 4: Repair & Reflect + AsyncRemediationQueue persistence
        if no_op_empty_queue:
            repair_summary = {
                "reflection": {"status": "SKIPPED_EMPTY_QUEUE", "total_recompiled": 0},
                "dead_routes_quarantined": 0,
                "sitemaps_pruned": 0,
                "overlays_written": [],
                "html_files_repaired": 0,
                "crawl_lag_dispatched": False,
                "crawl_lag_urls": [],
                "recompiled_assets_count": 0,
            }
        else:
            repair_summary = self.execute_engine_repairs(
                diagnoses,
                force=force,
                dry_run=dry_run,
                prioritized_candidates=prioritized_candidates,
                skip_recompile=skip_recompile,
            )

        def _remediation_worker(task: Dict[str, Any]) -> Dict[str, Any]:
            t_slug = str(task.get("slug") or "")
            t_url = str(task.get("target_url") or "")
            spec = task.get("overlay_spec")
            if not isinstance(spec, dict) or "title_rewrite" not in spec:
                spec = compile_remediation_overlay_spec(task, tenant_id=self.property_id)
            repaired_html = False
            if t_slug and not dry_run:
                repaired_html = self._apply_html_repairs_for_slug(t_slug, t_url, spec)
            return {
                "status": "COMPLETED",
                "slug": t_slug,
                "html_repaired": repaired_html,
            }

        queue_summary: Dict[str, Any] = {}
        if queue_obj is not None and (prioritized_candidates or has_pending_queue) and not dry_run:
            if prioritized_candidates:
                queue_obj.enqueue_batch(prioritized_candidates, tenant_id=self.property_id)
            queue_summary = queue_obj.process_tenant_batch(
                tenant_id=self.property_id,
                worker_fn=_remediation_worker,
                execution_budget_seconds=execution_budget_seconds,
            )

        # Step 5: Preflight Airlock
        preflight_report = self.enforce_preflight_airlock()

        # Step 6: Release Shipping via GitOps after Indexing Preflight and before Search Dispatch
        repairs_performed = (
            repair_summary.get("recompiled_assets_count", 0) > 0
            or len(repair_summary.get("overlays_written", [])) > 0
            or repair_summary.get("dead_routes_quarantined", 0) > 0
            or repair_summary.get("html_files_repaired", 0) > 0
            or repair_summary.get("repaired_html_count", 0) > 0
        )
        gitops_summary: Dict[str, Any] = {"status": "SKIPPED_NO_REPAIRS"}
        gitops_failed = False

        if repairs_performed and not dry_run and (enable_gitops or self.gitops_coordinator is not None):
            try:
                coord = self.gitops_coordinator
                if coord is None:
                    from pseofactory.gitops import GitOpsCoordinator
                    coord = GitOpsCoordinator()
                git_res = coord.commit_and_push_atomic(
                    repo_path=self.base_dir,
                    property_id=self.property_id,
                    recompiled_count=max(1, int(repair_summary.get("recompiled_assets_count", 1))),
                    dry_run=dry_run,
                )
                gitops_summary = git_res.to_dict() if hasattr(git_res, "to_dict") else dict(git_res)
                if gitops_summary.get("status") in (
                    "FAILED",
                    "ERROR",
                    "CONFLICT_BLOCKED",
                    "PUSH_FAILED",
                    "CI_FAILURE",
                    "EDGE_VERIFICATION_FAILED",
                ):
                    gitops_failed = True
            except Exception as g_err:
                logger.error("GitOps release shipping failed in feedback loop: %s", g_err)
                gitops_summary = {"status": "PUSH_FAILED", "error": str(g_err)}
                gitops_failed = True

        # Step 7: Multi-Engine Push & Explicit Child Sitemap Submission (blocked if GitOps failed)
        eligible_urls = preflight_report.push_eligible_urls
        if gitops_failed:
            push_summary = {
                "status": "SKIPPED_GITOPS_FAILED",
                "urls_targeted": len(eligible_urls),
                "urls_pushed": 0,
                "urls_skipped": len(eligible_urls),
                "child_sitemap_submissions": [],
                "sitemap_registration": {"status": "SKIPPED_GITOPS_FAILED", "submissions": []},
                "details": "Search dispatch aborted because GitOps release shipping did not succeed",
            }
        else:
            push_summary = self.dispatch_multi_engine_push(
                urls=eligible_urls,
                live=live and not dry_run,
                hubs_only=True,
            )

        section_coverage = self.attribute_section_coverage(raw_unindexed)

        # Step 8: Milestones Persistence
        try:
            self.milestone_tracker.save_ledger()
        except Exception as m_err:
            logger.warning("Failed saving milestone ledger: %s", m_err)

        overall_status = "SUCCESS"
        if gitops_failed or push_summary.get("status") in ("FAILED", "ERROR", "SKIPPED_GITOPS_FAILED"):
            overall_status = "PARTIAL"

        return {
            "timestamp": now_iso,
            "property_id": self.property_id,
            "status": overall_status,
            "no_op_empty_queue": no_op_empty_queue,
            "dry_run": dry_run,
            "live": live,
            "unindexed_audited": len(raw_unindexed),
            "diagnosed_defects": [d.to_dict() for d in diagnoses],
            "section_coverage_attribution": section_coverage,
            "child_sitemap_submissions": push_summary.get("child_sitemap_submissions", []),
            "sitemap_registration": push_summary.get("sitemap_registration"),
            "prioritized_candidates": prioritized_candidates,
            "crawl_lag_dispatched": bool(repair_summary.get("crawl_lag_dispatched")),
            "repair_summary": repair_summary,
            "queue_summary": queue_summary,
            "gitops_summary": gitops_summary,
            "preflight_summary": {
                "status": "READY_FOR_INDEXING" if preflight_report.passed_count > 0 else "QUARANTINED_ALL",
                "total_inspected": preflight_report.total_inspected,
                "passed": preflight_report.passed_count,
                "blocked": preflight_report.blocked_count,
                "push_eligible": len(preflight_report.push_eligible_urls),
                "eligible_urls": list(preflight_report.push_eligible_urls),
            },
            "push_summary": push_summary,
            "milestone_events_count": len(self.milestone_tracker.event_log),
            "rollover_queue_pending": len(self.indexer.load_gsc_rollover_queue()),
        }

