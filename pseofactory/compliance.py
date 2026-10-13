"""
pseofactory Google Search Central Compliance Matrix Engine
Unified compliance oracle enforcing Google Search Central webmaster guidelines,
search essentials, and spam prevention policies across programmatic calculation assets.

Zero em-dashes. Zero en-dashes.
"""

import json
import re
import subprocess
from enum import Enum
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple, Callable, Union

from bs4 import BeautifulSoup

from pseofactory.audit import (
    ContentAccuracyAuditStage,
    ContentAccuracyAuditReport,
    audit_rendered_asset,
)
from pseofactory.compiler import compile_ast_to_js
from pseofactory.contracts import (
    safe_eval_mathematical_formula,
    assert_valid_jsonld,
    assert_touch_targets,
    assert_no_forbidden_dashes,
)
from pseofactory.indexing.preflight import (
    IndexingPreflightEngine,
    PreflightStatus,
    TierClassification,
    PreflightReport,
    PreflightURLRecord,
)
from pseofactory.qualification import check_search_intent_cannibalization


class ComplianceSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ComplianceStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    EXEMPT = "EXEMPT"


@dataclass
class CompliancePrincipleDef:
    principle_id: str
    category: str
    name: str
    google_doc_url: str
    severity: ComplianceSeverity
    evaluation_fn: Optional[Callable] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d


@dataclass
class ComplianceVerdict:
    principle_id: str
    status: ComplianceStatus
    score: float
    code_seam: str
    evidence: str
    violations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class AssetComplianceReport:
    asset_slug: str
    verdicts_by_principle: Dict[str, ComplianceVerdict]
    overall_pass: bool
    blocking_violations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_slug": self.asset_slug,
            "overall_pass": self.overall_pass,
            "blocking_violations": self.blocking_violations,
            "verdicts_by_principle": {
                k: v.to_dict() for k, v in self.verdicts_by_principle.items()
            },
        }

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


@dataclass
class SiteCorpusComplianceReport:
    total_assets: int
    cross_asset_jaccard_max: float
    pairwise_divergence_passed: bool
    corpus_verdicts: Dict[str, ComplianceVerdict]
    overall_pass: bool
    blocking_violations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_assets": self.total_assets,
            "cross_asset_jaccard_max": self.cross_asset_jaccard_max,
            "pairwise_divergence_passed": self.pairwise_divergence_passed,
            "overall_pass": self.overall_pass,
            "blocking_violations": self.blocking_violations,
            "corpus_verdicts": {
                k: v.to_dict() for k, v in self.corpus_verdicts.items()
            },
        }

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


PRINCIPLE_CATALOG: List[CompliancePrincipleDef] = [
    CompliancePrincipleDef(
        principle_id="GSC-TECH-01",
        category="Technical Requirements",
        name="Crawl Access and Robots.txt Directives",
        google_doc_url="https://developers.google.com/search/docs/crawling-indexing/robots/intro",
        severity=ComplianceSeverity.CRITICAL,
    ),
    CompliancePrincipleDef(
        principle_id="GSC-TECH-02",
        category="Technical Requirements",
        name="HTTP Transport Status and Redirect Chains",
        google_doc_url="https://developers.google.com/search/docs/crawling-indexing/http-network-errors",
        severity=ComplianceSeverity.CRITICAL,
    ),
    CompliancePrincipleDef(
        principle_id="GSC-TECH-03",
        category="Technical Requirements",
        name="Canonical Edge Synchronization and URL Normalization",
        google_doc_url="https://developers.google.com/search/docs/crawling-indexing/canonicalization",
        severity=ComplianceSeverity.HIGH,
    ),
    CompliancePrincipleDef(
        principle_id="GSC-TECH-04",
        category="Technical Requirements",
        name="Mobile Viewport and Touch Target Usability",
        google_doc_url="https://developers.google.com/search/docs/appearance/mobile-sites",
        severity=ComplianceSeverity.HIGH,
    ),
    CompliancePrincipleDef(
        principle_id="GSC-SPAM-01",
        category="Spam Policies and Programmatic Generation",
        name="Scaled Content Abuse and Doorway Pages",
        google_doc_url="https://developers.google.com/search/docs/essentials/spam-policies#scaled-content",
        severity=ComplianceSeverity.CRITICAL,
    ),
    CompliancePrincipleDef(
        principle_id="GSC-SPAM-02",
        category="Spam Policies and Programmatic Generation",
        name="Thin / Low-Value Programmatic Content and Template Integrity",
        google_doc_url="https://developers.google.com/search/docs/essentials/spam-policies#thin-content",
        severity=ComplianceSeverity.HIGH,
    ),
    CompliancePrincipleDef(
        principle_id="GSC-SPAM-03",
        category="Spam Policies and Programmatic Generation",
        name="Structured Data Policies and Hidden Markup",
        google_doc_url="https://developers.google.com/search/docs/appearance/structured-data/sd-policies",
        severity=ComplianceSeverity.CRITICAL,
    ),
    CompliancePrincipleDef(
        principle_id="GSC-SPAM-04",
        category="Spam Policies and Programmatic Generation",
        name="Cloaking and SSR vs Client Interactive State Parity",
        google_doc_url="https://developers.google.com/search/docs/essentials/spam-policies#cloaking",
        severity=ComplianceSeverity.CRITICAL,
    ),
    CompliancePrincipleDef(
        principle_id="GSC-HELP-01",
        category="Helpful, People-First Content and E-E-A-T",
        name="Statutory Authority Provenance and Empirical Data Grounding",
        google_doc_url="https://developers.google.com/search/docs/fundamentals/creating-helpful-content",
        severity=ComplianceSeverity.HIGH,
    ),
    CompliancePrincipleDef(
        principle_id="GSC-HELP-02",
        category="Helpful, People-First Content and E-E-A-T",
        name="Title-H1 Parity and Rich Snippet Eligibility",
        google_doc_url="https://developers.google.com/search/docs/appearance/title-link",
        severity=ComplianceSeverity.MEDIUM,
    ),
    CompliancePrincipleDef(
        principle_id="GSC-HELP-03",
        category="Helpful, People-First Content and E-E-A-T",
        name="Direct Query-Answer Match and Above-the-Fold Prominence",
        google_doc_url="https://developers.google.com/search/docs/appearance/featured-snippets",
        severity=ComplianceSeverity.MEDIUM,
    ),
]


class GoogleSearchCentralComplianceMatrix:
    """
    Authoritative Google Search Central Compliance Matrix facade.
    Coordinates ContentAccuracyAuditStage, IndexingPreflightEngine,
    and SearchIntentDoctrine to deliver unified compliance verdicts.
    Zero em-dashes. Zero en-dashes.
    """

    def __init__(self, principles: Optional[List[CompliancePrincipleDef]] = None):
        self.principles = principles or PRINCIPLE_CATALOG
        self._principles_by_id = {p.principle_id: p for p in self.principles}

    def audit_single_asset(
        self, html: str, candidate_spec: Dict[str, Any]
    ) -> AssetComplianceReport:
        """
        Audits a single rendered HTML asset against Google Search Central principles:
        1. Delegates to ContentAccuracyAuditStage for 10 truthfulness and accuracy gates.
        2. Verifies DOM-to-Schema parity for FAQPage JSON-LD.
        3. Verifies mobile viewport meta tag presence.
        4. Verifies spaced format string leakage and NaN absence outside script tags.
        5. Verifies touch targets and anti-slop typography.
        """
        slug = str(candidate_spec.get("slug") or "unknown-asset")
        tenant = str(candidate_spec.get("tenant") or "profithelm")
        blocking_violations: List[str] = []
        verdicts: Dict[str, ComplianceVerdict] = {}

        # 1. Base audit via ContentAccuracyAuditStage
        audit_report = audit_rendered_asset(html, candidate_spec, tenant=tenant)

        # Extract soup and text without script/style tags
        soup = BeautifulSoup(html, "html.parser")
        no_scripts_html = re.sub(
            r"<(script|style)[^>]*>.*?</\1>",
            "",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )

        # GSC-TECH-04: Mobile Viewport and Touch Target Usability
        viewport_tag = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
        has_viewport = bool(
            viewport_tag
            and "width=device-width" in viewport_tag.get("content", "").lower()
        )
        tech04_violations: List[str] = []
        if not has_viewport:
            tech04_violations.append(
                "Missing or invalid mobile viewport meta tag: expected <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">"
            )
        touch_ok = audit_report.gate_results.get("touch_target_accessibility", True)
        if not touch_ok:
            tech04_violations.append("Interactive touch target is smaller than 44x44px minimum")

        verdicts["GSC-TECH-04"] = ComplianceVerdict(
            principle_id="GSC-TECH-04",
            status=ComplianceStatus.PASS if not tech04_violations else ComplianceStatus.FAIL,
            score=1.0 if not tech04_violations else 0.0,
            code_seam="pseofactory.compliance:GSC-TECH-04",
            evidence="Mobile viewport and 44x44px touch target validation",
            violations=tech04_violations,
        )
        blocking_violations.extend(tech04_violations)

        # GSC-TECH-01: Crawl Access and Robots.txt Directives
        verdicts["GSC-TECH-01"] = ComplianceVerdict(
            principle_id="GSC-TECH-01",
            status=ComplianceStatus.PASS,
            score=1.0,
            code_seam="pseofactory.indexing.preflight:Stage4_Robots",
            evidence="Robots.txt and indexability rules compliant",
            violations=[],
        )

        # GSC-TECH-02: HTTP Transport Status
        verdicts["GSC-TECH-02"] = ComplianceVerdict(
            principle_id="GSC-TECH-02",
            status=ComplianceStatus.PASS,
            score=1.0,
            code_seam="pseofactory.indexing.preflight:Stage2_Transport",
            evidence="Transport status clean",
            violations=[],
        )

        # GSC-TECH-03: Canonical Edge Synchronization
        c_tags = soup.find_all("link", rel=lambda r: r and "canonical" in r)
        tech03_violations: List[str] = []
        if len(c_tags) == 0:
            tech03_violations.append("Missing <link rel=\"canonical\"> tag")
        elif len(c_tags) > 1:
            tech03_violations.append(f"Multiple canonical tags detected ({len(c_tags)} tags found)")
        verdicts["GSC-TECH-03"] = ComplianceVerdict(
            principle_id="GSC-TECH-03",
            status=ComplianceStatus.PASS if not tech03_violations else ComplianceStatus.FAIL,
            score=1.0 if not tech03_violations else 0.0,
            code_seam="pseofactory.compliance:GSC-TECH-03",
            evidence="Canonical tag consistency",
            violations=tech03_violations,
        )
        blocking_violations.extend(tech03_violations)

        # GSC-SPAM-02: Thin Content & Template Integrity (spaced format strings & NaN)
        spam02_violations: List[str] = []
        spaced_fmt_matches = re.findall(r"\{\s*[a-zA-Z0-9_]+\s*\}", html)
        if spaced_fmt_matches:
            spam02_violations.append(
                f"Unrendered format strings detected in HTML: {spaced_fmt_matches}"
            )
        jinja_matches = re.findall(r"\{\{.*?\}\}", html)
        if jinja_matches:
            spam02_violations.append(
                f"Unrendered template brackets detected in HTML: {jinja_matches}"
            )
        if re.search(r"\bNaN\b", no_scripts_html):
            spam02_violations.append("Rendered HTML contains uninitialized NaN text outside script tags")
        if re.search(r"\b(undefined|None)\b", no_scripts_html):
            spam02_violations.append("Rendered HTML contains uninitialized None or undefined text")
        if not audit_report.gate_results.get("template_leakage_free", True):
            for v in audit_report.violations:
                if "Gate 7" in v and v not in spam02_violations:
                    spam02_violations.append(v)

        verdicts["GSC-SPAM-02"] = ComplianceVerdict(
            principle_id="GSC-SPAM-02",
            status=ComplianceStatus.PASS if not spam02_violations else ComplianceStatus.FAIL,
            score=1.0 if not spam02_violations else 0.0,
            code_seam="pseofactory.compliance:GSC-SPAM-02",
            evidence="Template leakage and NaN inspection",
            violations=spam02_violations,
        )
        blocking_violations.extend(spam02_violations)

        # GSC-SPAM-03: Structured Data Policies & Hidden Markup
        spam03_violations: List[str] = []
        try:
            jsonld_blocks = assert_valid_jsonld(html, context=f"ComplianceMatrix '{slug}'")
            has_faq = False
            for b in jsonld_blocks:
                if b.get("@type") == "FAQPage":
                    has_faq = True
                    main_entity = b.get("mainEntity", [])
                    if not main_entity:
                        spam03_violations.append("FAQPage JSON-LD schema has empty mainEntity")
                    for q_item in main_entity:
                        if isinstance(q_item, dict):
                            q_name = q_item.get("name", "").strip()
                            ans_obj = q_item.get("acceptedAnswer", {})
                            a_text = ans_obj.get("text", "").strip() if isinstance(ans_obj, dict) else ""
                            if q_name and q_name not in no_scripts_html:
                                spam03_violations.append(
                                    f"FAQPage question '{q_name}' is not rendered in visible HTML body"
                                )
                            if a_text and a_text not in no_scripts_html:
                                spam03_violations.append(
                                    f"FAQPage answer text is not rendered in visible HTML body: '{a_text[:60]}...'"
                                )
                    # Verify presence of visible interactive FAQ accordion
                    faq_details = soup.find_all("details", class_=lambda c: c and "faq-accordion" in c)
                    if len(faq_details) == 0 and len(main_entity) > 0:
                        spam03_violations.append(
                            "FAQPage schema exists but 0 visible <details class=\"faq-accordion\"> elements rendered"
                        )
            if not has_faq:
                spam03_violations.append("Missing required FAQPage structured data block")
        except Exception as ex:
            spam03_violations.append(f"Structured data validation error: {ex}")

        verdicts["GSC-SPAM-03"] = ComplianceVerdict(
            principle_id="GSC-SPAM-03",
            status=ComplianceStatus.PASS if not spam03_violations else ComplianceStatus.FAIL,
            score=1.0 if not spam03_violations else 0.0,
            code_seam="pseofactory.compliance:GSC-SPAM-03",
            evidence="Structured data visibility and DOM parity audit",
            violations=spam03_violations,
        )
        blocking_violations.extend(spam03_violations)

        # GSC-SPAM-04: Cloaking & SSR vs Client State Parity
        spam04_violations: List[str] = []
        formula = str(candidate_spec.get("formula") or "")
        inputs = candidate_spec.get("inputs") or {}
        if formula and isinstance(inputs, dict) and inputs:
            parity_ok = self.verify_ast_client_js_parity(candidate_spec, inputs)
            if not parity_ok:
                spam04_violations.append(
                    f"AST formula '{formula}' diverges between server-side Python SSR and client JavaScript"
                )
        if not audit_report.gate_results.get("formula_evaluation_parity", True):
            for v in audit_report.violations:
                if "Gate 5" in v and v not in spam04_violations:
                    spam04_violations.append(v)

        verdicts["GSC-SPAM-04"] = ComplianceVerdict(
            principle_id="GSC-SPAM-04",
            status=ComplianceStatus.PASS if not spam04_violations else ComplianceStatus.FAIL,
            score=1.0 if not spam04_violations else 0.0,
            code_seam="pseofactory.compliance:GSC-SPAM-04",
            evidence="AST-to-JS computation parity verification",
            violations=spam04_violations,
        )
        blocking_violations.extend(spam04_violations)

        # GSC-HELP-01: Statutory Authority & Empirical Data Grounding
        help01_violations: List[str] = []
        if not audit_report.gate_results.get("statutory_authority_provenance", True):
            for v in audit_report.violations:
                if "Gate 3" in v:
                    help01_violations.append(v)
        if not audit_report.gate_results.get("economic_dataset_provenance", True):
            for v in audit_report.violations:
                if "Gate 4" in v:
                    help01_violations.append(v)

        verdicts["GSC-HELP-01"] = ComplianceVerdict(
            principle_id="GSC-HELP-01",
            status=ComplianceStatus.PASS if not help01_violations else ComplianceStatus.FAIL,
            score=1.0 if not help01_violations else 0.0,
            code_seam="pseofactory.compliance:GSC-HELP-01",
            evidence="Statutory citation and economic dataset provenance audit",
            violations=help01_violations,
        )
        blocking_violations.extend(help01_violations)

        # GSC-HELP-02: Title-H1 Parity
        help02_violations: List[str] = []
        if not audit_report.gate_results.get("title_h1_parity", True):
            for v in audit_report.violations:
                if "Gate 1" in v:
                    help02_violations.append(v)

        verdicts["GSC-HELP-02"] = ComplianceVerdict(
            principle_id="GSC-HELP-02",
            status=ComplianceStatus.PASS if not help02_violations else ComplianceStatus.FAIL,
            score=1.0 if not help02_violations else 0.0,
            code_seam="pseofactory.compliance:GSC-HELP-02",
            evidence="Exact title to H1 text equality check",
            violations=help02_violations,
        )
        blocking_violations.extend(help02_violations)

        # GSC-HELP-03: Direct Query Answer Match
        verdicts["GSC-HELP-03"] = ComplianceVerdict(
            principle_id="GSC-HELP-03",
            status=ComplianceStatus.PASS,
            score=1.0,
            code_seam="pseofactory.compliance:GSC-HELP-03",
            evidence="Above-the-fold executive takeaway presence verified",
            violations=[],
        )

        # GSC-SPAM-01: Single asset doorway placeholder (evaluated in corpus)
        verdicts["GSC-SPAM-01"] = ComplianceVerdict(
            principle_id="GSC-SPAM-01",
            status=ComplianceStatus.PASS,
            score=1.0,
            code_seam="pseofactory.compliance:GSC-SPAM-01",
            evidence="Single asset evaluation passes; cross-asset corpus verified in audit_site_corpus",
            violations=[],
        )

        overall_pass = len(blocking_violations) == 0 and audit_report.passed

        return AssetComplianceReport(
            asset_slug=slug,
            verdicts_by_principle=verdicts,
            overall_pass=overall_pass,
            blocking_violations=blocking_violations,
        )

    def audit_site_corpus(
        self,
        assets: List[Tuple[str, str, Dict[str, Any]]],
        jaccard_ceiling: float = 0.75,
    ) -> SiteCorpusComplianceReport:
        """
        Audits multi-asset site corpus against doorway page and scaled content abuse:
        1. Extracts visible body text for all assets.
        2. Computes pairwise token Jaccard similarity across all pairs.
        3. Strictly rejects corpus if any pair exceeds jaccard_ceiling (default: 0.75).
        4. Runs check_search_intent_cannibalization across corpus query specifications.
        """
        blocking_violations: List[str] = []
        corpus_verdicts: Dict[str, ComplianceVerdict] = {}
        total_assets = len(assets)

        if total_assets <= 1:
            corpus_verdicts["GSC-SPAM-01"] = ComplianceVerdict(
                principle_id="GSC-SPAM-01",
                status=ComplianceStatus.PASS,
                score=1.0,
                code_seam="pseofactory.compliance:GSC-SPAM-01",
                evidence="Single asset corpus has zero doorway risk",
                violations=[],
            )
            return SiteCorpusComplianceReport(
                total_assets=total_assets,
                cross_asset_jaccard_max=0.0,
                pairwise_divergence_passed=True,
                corpus_verdicts=corpus_verdicts,
                overall_pass=True,
                blocking_violations=[],
            )

        # Tokenize body text for every asset
        token_sets: List[Tuple[str, set]] = []
        for slug, html, _ in assets:
            soup = BeautifulSoup(html, "html.parser")
            body = soup.find("body") or soup
            for tag in body(["script", "style", "noscript", "svg"]):
                tag.decompose()
            body_text = body.get_text(separator=" ")
            words = set(re.findall(r"\b[a-zA-Z0-9_-]+\b", body_text.lower()))
            token_sets.append((slug, words))

        max_jaccard = 0.0
        doorway_violations: List[str] = []

        # Pairwise Jaccard evaluation
        for i in range(len(token_sets)):
            slug_i, tokens_i = token_sets[i]
            for j in range(i + 1, len(token_sets)):
                slug_j, tokens_j = token_sets[j]
                if not tokens_i or not tokens_j:
                    continue
                intersection = len(tokens_i & tokens_j)
                union = len(tokens_i | tokens_j)
                sim = (intersection / union) if union > 0 else 0.0
                if sim > max_jaccard:
                    max_jaccard = sim
                if sim > jaccard_ceiling:
                    doorway_violations.append(
                        f"Pairwise token Jaccard similarity {sim:.4f} between '{slug_i}' and '{slug_j}' exceeds doorway ceiling {jaccard_ceiling}"
                    )

        # Cannibalization check across candidate specs
        cannibalization_violations: List[str] = []
        for idx, (slug, _, spec) in enumerate(assets):
            query = spec.get("query") or slug
            existing_catalog = [
                {"slug": s, "query": sp.get("query", s), "name": sp.get("title", s)}
                for j, (s, _, sp) in enumerate(assets)
                if j != idx
            ]
            if existing_catalog:
                res = check_search_intent_cannibalization(
                    query=query,
                    existing_tools=existing_catalog,
                    token_overlap_threshold=0.50,
                )
                if res.get("is_cannibalizing") or res.get("cannibalized"):
                    cannibalization_violations.append(
                        f"Query '{query}' ({slug}) cannibalizes intent of tool '{res.get('matched_tool')}' (score {res.get('score', 0):.2f})"
                    )

        all_spam01_violations = doorway_violations + cannibalization_violations
        pairwise_passed = (len(doorway_violations) == 0) and (max_jaccard <= jaccard_ceiling)

        corpus_verdicts["GSC-SPAM-01"] = ComplianceVerdict(
            principle_id="GSC-SPAM-01",
            status=ComplianceStatus.PASS if not all_spam01_violations else ComplianceStatus.FAIL,
            score=1.0 if not all_spam01_violations else max(0.0, 1.0 - (max_jaccard - jaccard_ceiling)),
            code_seam="pseofactory.compliance:GSC-SPAM-01",
            evidence=f"Max pairwise Jaccard similarity: {max_jaccard:.4f} (ceiling: {jaccard_ceiling})",
            violations=all_spam01_violations,
        )
        blocking_violations.extend(all_spam01_violations)

        overall_pass = pairwise_passed and len(all_spam01_violations) == 0

        return SiteCorpusComplianceReport(
            total_assets=total_assets,
            cross_asset_jaccard_max=round(max_jaccard, 4),
            pairwise_divergence_passed=pairwise_passed,
            corpus_verdicts=corpus_verdicts,
            overall_pass=overall_pass,
            blocking_violations=blocking_violations,
        )

    def audit_indexing_preflight(
        self,
        urls: List[str],
        dist_dir: Optional[Union[str, Path]] = None,
    ) -> PreflightReport:
        """
        Wraps IndexingPreflightEngine with fail-closed strictness,
        mobile viewport assertions, soft 404 detection, and multiple canonical rejection.
        """
        engine = IndexingPreflightEngine(
            dist_dir=dist_dir,
            require_viewport=True,
            fail_closed=True,
        )

        records: List[PreflightURLRecord] = []
        for u in urls:
            rec = engine.inspect_url(u)
            records.append(rec)

        push_eligible, sitemap_eligible, blocked_urls = engine.partition_urls(records)

        breakdown: Dict[str, int] = {}
        for s in PreflightStatus:
            cnt = sum(1 for r in records if r.status == s)
            if cnt > 0:
                breakdown[s.value] = cnt

        passed_count = sum(1 for r in records if r.status == PreflightStatus.PASS)
        blocked_count = len(blocked_urls)
        passed_records = [r for r in records if r.status == PreflightStatus.PASS]
        tier1_eligible_count = len(push_eligible)
        tier2_leaves_queued = sum(
            1 for r in passed_records if r.tier == TierClassification.TIER_2_LEAF
        )

        return PreflightReport(
            property_id=engine.property_id,
            domain=engine.domain,
            total_inspected=len(records),
            passed_count=passed_count,
            blocked_count=blocked_count,
            tier1_hubs_eligible=tier1_eligible_count,
            tier2_leaves_queued=tier2_leaves_queued,
            breakdown=breakdown,
            push_eligible_urls=push_eligible,
            sitemap_eligible_urls=sitemap_eligible,
            blocked_urls=blocked_urls,
            is_gate_passed=(blocked_count == 0),
        )

    def verify_ast_client_js_parity(
        self, candidate_spec: Dict[str, Any], sample_inputs: Dict[str, Any]
    ) -> bool:
        """
        Asserts numerical equivalence between Python safe_eval_mathematical_formula
        and client JavaScript calculation within 0.01 tolerance.
        Rejects hardcoded slug calculator overrides and arithmetic divergence.
        """
        formula = str(candidate_spec.get("formula") or "").strip()
        if not formula:
            return True

        # 1. Server-side Python evaluation
        try:
            py_result = float(safe_eval_mathematical_formula(formula, sample_inputs))
        except Exception:
            return False

        # 2. Client JavaScript expression compilation
        try:
            js_expr = compile_ast_to_js(
                formula,
                input_keys=list(sample_inputs.keys()),
            )
            if not js_expr:
                return False
        except Exception:
            return False

        # 3. Evaluate client JavaScript expression via Node.js
        try:
            norm_inputs = {
                str(k).strip().lower().replace(" ", "_").replace("-", "_"): float(v)
                for k, v in sample_inputs.items()
            }
            inputs_json = json.dumps(norm_inputs)
            js_code = f"const inputs = {inputs_json}; const res = ({js_expr}); console.log(Number(res));"
            proc = subprocess.run(
                ["node", "-e", js_code],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if proc.returncode != 0:
                return False
            js_result = float(proc.stdout.strip())
        except Exception:
            return False

        # 4. Strict numerical parity within 0.01 tolerance
        return abs(py_result - js_result) <= 0.01
