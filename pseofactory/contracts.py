"""
pseofactory Structural & Content Contracts Enforcement Engine
Shared invariant assertions across social broadcasts, static site output,
and copy generation:
1. Strict anti-slop invariant: zero em-dashes (U+2014) and zero en-dashes (U+2013).
2. Social post length bounds (LinkedIn: 20 to 2,800 chars per HWL-1065; X: 10 to 280 chars).
3. Hard prompt leakage phrase rejection.
4. Google AI Mode calculation manifest and entity taxonomy assertions.
Zero em-dashes. Zero en-dashes.
"""

import re
import json
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Set, Optional

FORBIDDEN_JARGON: List[str] = [
    "delve",
    "delving",
    "game-changer",
    "testament to",
    "tapestry",
    "lorem ipsum",
    "TODO",
    "TBD",
    "[placeholder]",
]

PROMPT_LEAKAGE_TERMS: List[str] = [
    "captures striking distance",
    "search demand for position",
    "evaluating multi-tier statutory thresholds across federal and state levels, taxpayers project",
    "evaluating multi-tier statutory thresholds",
    "taxpayers project",
    "prompt:",
    "system prompt",
    "as an ai language model",
    "here is the response",
    "delve into the intricacies",
]

AI_MODE_ENTITY_TAXONOMY: Set[str] = {
    # Canonical 30-Type AI Mode Entity Taxonomy
    "VehicleModel",
    "FinancialProductOrService",
    "SpecificPurchasableSoftwareSystem",
    "SkuLevelProduct",
    "TaxCalculationModel",
    "StatutoryDeduction",
    "DepreciationSchedule",
    "MortgageLoanProduct",
    "InvestmentVehicle",
    "InsurancePolicy",
    "BusinessEntityStructure",
    "PayrollTaxStructure",
    "RetirementAccountPlan",
    "CreditFacility",
    "LeaseContract",
    "AssetClass",
    "RealEstatePropertyType",
    "CryptocurrencyAsset",
    "CommodityContract",
    "ForeignExchangePair",
    "GovernmentGrantProgram",
    "TariffSchedule",
    "AccountingStandard",
    "ValuationMethodology",
    "CapitalExpenditureCategory",
    "OperatingExpenseCategory",
    "AmortizationSchedule",
    "CorporateTaxBracket",
    "PersonalTaxBracket",
    "MunicipalBondProduct",
    # Rule and Specification Extensions
    "StatutoryCalculationRule",
    "StatutoryLimitSpecification",
    "TaxDeductionRule",
    "DepreciationScheduleRule",
    "CapitalGainsExemptionRule",
    "AmortizationScheduleRule",
    "RepaymentPlanSpecification",
    "InflationAdjustmentRule",
    "PovertyGuidelineSpecification",
    "FederalIncomeTaxBracket",
    "StateIncomeTaxBracket",
    "CorporateIncomeTaxRate",
    "AlternativeMinimumTaxRule",
    "NetInvestmentIncomeTaxRule",
    "SelfEmploymentTaxSchedule",
    "QualifiedSmallBusinessStockRule",
    "Exchange1031DeferralRule",
    "Section179ExpensingCap",
    "BonusDepreciationSchedule",
    "ResearchAndDevelopmentCreditRule",
    "WorkOpportunityTaxCreditRule",
    "ChildTaxCreditSpecification",
    "EarnedIncomeTaxCreditSchedule",
    "ForeignEarnedIncomeExclusionRule",
    "EstateTaxExemptionSpecification",
    "GiftTaxAnnualExclusionRule",
    "GenerationSkippingTransferRule",
    "SocialSecurityWageBaseCap",
    "MedicareAdditionalTaxRule",
    "StudentLoanInterestDeductionRule",
    "HealthSavingsAccountContributionLimit",
    "FlexibleSpendingAccountLimit",
    "StandardDeductionSpecification",
    "PassiveActivityLossLimitationRule",
}


def assert_no_forbidden_dashes(text: str, context: str = "") -> bool:
    """
    Strict anti-slop invariant: zero em-dashes (U+2014) and zero en-dashes (U+2013).
    Raises ValueError if any forbidden dash character is present.
    """
    if not text:
        return True
    if "\u2014" in text:
        ctx = f" in {context}" if context else ""
        raise ValueError(f"Forbidden em-dash (\\u2014) detected{ctx}")
    if "\u2013" in text:
        ctx = f" in {context}" if context else ""
        raise ValueError(f"Forbidden en-dash (\\u2013) detected{ctx}")
    return True


def assert_no_prompt_leakage(text: str, context: str = "") -> None:
    """
    Strict content invariant: ensures no internal LLM prompt instructions,
    SEO scaffolding fragments, or unfinished prompt leaks appear in published text.
    Raises ValueError if prompt leakage terms are detected.
    """
    if not text:
        return
    text_lower = text.lower()
    for term in PROMPT_LEAKAGE_TERMS:
        if term in text_lower:
            ctx = f" in {context}" if context else ""
            raise ValueError(f"Prompt leakage detected{ctx}: contains forbidden phrase '{term}'")


def assert_linkedin(text: str) -> bool:
    """
    Validates LinkedIn copy (Company updates per HWL-1065):
    1. Maximum 2800 characters.
    2. Minimum 20 characters.
    3. Zero forbidden dashes (em-dash or en-dash).
    4. Zero prompt leakage.
    """
    if not text or len(text) < 20:
        raise ValueError(f"LinkedIn text too short ({len(text) if text else 0} chars, min 20)")
    if len(text) > 2800:
        raise ValueError(f"LinkedIn text exceeds 2800 characters ({len(text)} chars per HWL-1065)")
    assert_no_forbidden_dashes(text, context="LinkedIn post")
    assert_no_prompt_leakage(text, context="LinkedIn post")
    return True


def assert_x_post(text: str) -> bool:
    """
    Validates X (Twitter) post copy:
    1. Maximum 280 characters.
    2. Minimum 10 characters.
    3. Zero forbidden dashes (em-dash or en-dash).
    4. Zero prompt leakage.
    """
    if not text or len(text) < 10:
        raise ValueError(f"X post text too short ({len(text) if text else 0} chars, min 10)")
    if len(text) > 280:
        raise ValueError(f"X post text exceeds 280 characters ({len(text)} chars)")
    assert_no_forbidden_dashes(text, context="X post")
    assert_no_prompt_leakage(text, context="X post")
    return True


def assert_youtube_pinned_comment(text: str) -> bool:
    """
    Validates YouTube pinned comment template:
    1. Length between 50 and 1000 characters.
    2. Zero em-dashes (\\u2014) and zero en-dashes (\\u2013).
    3. Zero angle brackets (< or >) to prevent YouTube API rejection (HWL-1202).
    4. Must include conversion tracking parameter 'utm_content=pinned_comment'.
    5. Zero prompt leakage.
    """
    if not text or len(text) < 50:
        raise ValueError(f"YouTube pinned comment too short ({len(text) if text else 0} chars, min 50)")
    if len(text) > 1000:
        raise ValueError(f"YouTube pinned comment exceeds 1000 characters ({len(text)} chars, max 1000)")
    assert_no_forbidden_dashes(text, context="YouTube pinned comment")
    assert_no_prompt_leakage(text, context="YouTube pinned comment")
    if "<" in text or ">" in text:
        raise ValueError("Angle brackets (< or >) are forbidden in YouTube pinned comment")
    if "utm_content=pinned_comment" not in text:
        raise ValueError("YouTube pinned comment must include conversion tracking parameter 'utm_content=pinned_comment'")
    return True


def assert_youtube_description(text: str) -> bool:
    """
    Validates YouTube video description:
    1. Length between 100 and 5000 characters.
    2. Zero forbidden dashes (\\u2014, \\u2013).
    3. Zero angle brackets (< or >) to prevent YouTube API rejection (HWL-1202).
    4. Must include conversion tracking parameter ('utm_content=').
    5. Zero prompt leakage.
    """
    if not text or len(text) < 100:
        raise ValueError(f"YouTube description too short ({len(text) if text else 0} chars, min 100)")
    if len(text) > 5000:
        raise ValueError(f"YouTube description exceeds 5000 characters ({len(text)} chars, max 5000)")
    assert_no_forbidden_dashes(text, context="YouTube description")
    assert_no_prompt_leakage(text, context="YouTube description")
    if "<" in text or ">" in text:
        raise ValueError("Angle brackets (< or >) are forbidden in YouTube description")
    if "utm_content=" not in text:
        raise ValueError("YouTube description must include conversion tracking parameter ('utm_content=')")
    return True



def sanitize_url_slug(raw_str: str) -> str:
    """
    Normalizes any raw query or title into a URL-safe slug matching
    ^[a-z0-9]+(?:-[a-z0-9]+)*$.
    Replaces non-alphanumeric characters with hyphens, collapses consecutive hyphens,
    and strips leading and trailing hyphens. Strips apostrophes first so contractions
    like "what's" become "whats".
    """
    if not raw_str or not isinstance(raw_str, str):
        return "tool"
    slug = raw_str.strip().lower()
    slug = slug.replace("'", "").replace("’", "").replace("`", "")
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-") or "tool"


def assert_ai_mode_calculation_manifest(spec: Dict[str, Any]) -> bool:
    """
    Validates that a calculation specification satisfies Google AI Mode internals:
    - formula: explicit non-empty mathematical computation formula
    - inputs: non-empty list or dict of input parameters
    - sample_calculation: concrete non-empty calculation example
    - statutory_authority: authoritative code/statute citations
    - entity_type: must be one of the strict 30-type taxonomy entities
    Zero em-dashes. Zero en-dashes.
    """
    if not isinstance(spec, dict):
        raise ValueError(f"Specification must be a dictionary, got {type(spec).__name__}")

    manifest = spec.get("calculation_manifest") or spec

    formula = manifest.get("formula")
    if not formula:
        raise ValueError("Specification missing or empty 'formula' in calculation manifest")
    if isinstance(formula, str):
        assert_no_forbidden_dashes(formula, context="calculation manifest formula")

    inputs = manifest.get("inputs")
    if not inputs or not isinstance(inputs, (list, dict)):
        raise ValueError("Specification missing or empty 'inputs' in calculation manifest")

    sample = manifest.get("sample_calculation") or manifest.get("sample")
    if not sample or (isinstance(sample, (str, list, dict)) and len(sample) == 0):
        raise ValueError("Specification missing or empty 'sample_calculation' in calculation manifest")
    if isinstance(sample, str):
        assert_no_forbidden_dashes(sample, context="calculation manifest sample_calculation")

    authority = manifest.get("statutory_authority") or manifest.get("authority")
    if not authority:
        raise ValueError("Specification missing or empty 'statutory_authority' in calculation manifest")
    if isinstance(authority, str):
        assert_no_forbidden_dashes(authority, context="calculation manifest statutory_authority")

    entity_type = manifest.get("entity_type") or manifest.get("taxonomy_type")
    if not entity_type or not isinstance(entity_type, str):
        raise ValueError("Specification missing 'entity_type' in calculation manifest")
    if entity_type not in AI_MODE_ENTITY_TAXONOMY:
        raise ValueError(
            f"Invalid entity_type '{entity_type}'. Must be one of the 30 AI Mode taxonomy types."
        )

    return True


def assert_meta_tag_contract(tag_name: str, content: str) -> bool:
    """
    Validates structural meta tag content against anti-slop and length invariants.
    Ensures zero forbidden dashes, zero prompt leakage, and non-empty content.
    """
    if not tag_name or not isinstance(tag_name, str):
        raise ValueError("Meta tag name must be a non-empty string")
    if not content or not isinstance(content, str):
        raise ValueError("Meta tag content must be a non-empty string")
    assert_no_forbidden_dashes(content, context=f"meta tag '{tag_name}'")
    assert_no_prompt_leakage(content, context=f"meta tag '{tag_name}'")
    return True


def assert_url_safe_slug(slug: str) -> bool:
    """
    Validates that a slug strictly matches ^[a-z0-9-]+$ without double hyphens
    or leading/trailing hyphens.
    """
    if not slug or not isinstance(slug, str):
        raise ValueError("Slug must be a non-empty string")
    if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", slug):
        raise ValueError(f"Slug '{slug}' does not conform to URL-safe pattern ^[a-z0-9]+(?:-[a-z0-9]+)*$")
    return True


def assert_technical_seo_spec(spec: Dict[str, Any]) -> bool:
    """
    Enforces technical SEO checklist verification directly inside generator specifications
    before pages are built:
    1. URL-safe slug format (^[a-z0-9]+(?:-[a-z0-9]+)*$).
    2. Title length <= 70 chars with zero em-dashes and zero en-dashes.
    3. Meta description length between 50 and 160 chars with zero forbidden dashes.
    4. Canonical path matching strict /tools/{slug}/ formatting.
    5. Dataset joins >= 2 empirical datasets (HWL-1075).
    6. Position 0 GEO summary / quick-answer with numerical or statutory benchmark citations.
    """
    if not isinstance(spec, dict):
        raise ValueError("Specification must be a dictionary")

    # 1. Slug format
    slug = spec.get("slug")
    if not slug:
        raise ValueError("Specification missing required 'slug' attribute")
    assert_url_safe_slug(slug)

    # 2. Title length strictly within 50-60 chars, zero em/en-dashes
    title = spec.get("title")
    if not title or not isinstance(title, str):
        raise ValueError(f"Specification '{slug}' missing non-empty 'title'")
    if len(title) < 50:
        raise ValueError(f"Specification '{slug}' title too short ({len(title)} chars, min 50): '{title}'")
    if len(title) > 60:
        raise ValueError(f"Specification '{slug}' title exceeds 60 characters ({len(title)} chars, max 60): '{title}'")
    assert_no_forbidden_dashes(title, context=f"spec '{slug}' title")

    # 3. Meta description 50-160 chars, zero em/en-dashes
    desc = spec.get("description")
    if not desc or not isinstance(desc, str):
        raise ValueError(f"Specification '{slug}' missing non-empty 'description'")
    if len(desc) < 50:
        raise ValueError(f"Specification '{slug}' description too short ({len(desc)} chars, min 50)")
    if len(desc) > 160:
        raise ValueError(f"Specification '{slug}' description exceeds 160 characters ({len(desc)} chars): '{desc}'")
    assert_no_forbidden_dashes(desc, context=f"spec '{slug}' description")

    # 4. Canonical path formatting
    canonical_path = spec.get("canonical_path")
    expected_path = f"/tools/{slug}/"
    if canonical_path is not None and canonical_path != expected_path:
        raise ValueError(f"Specification '{slug}' canonical_path '{canonical_path}' does not match expected '{expected_path}'")

    # 5. Dataset joins >= 2
    datasets = spec.get("datasets") or []
    dataset_bindings = spec.get("dataset_bindings") or {}
    dataset_count = max(len(datasets), len(dataset_bindings))
    if dataset_count < 2 and not spec.get("_multi_dataset_enrichment"):
        raise ValueError(f"Specification '{slug}' requires >= 2 empirical dataset joins (found {dataset_count}) per HWL-1075")

    # 6. Position 0 GEO summary / quick-answer (strictly 40-60 words) with benchmark citations
    geo = spec.get("geo_summary") or spec.get("quick_answer")
    if not geo or not isinstance(geo, str):
        raise ValueError(f"Specification '{slug}' missing Position 0 GEO summary / quick-answer")
    assert_no_forbidden_dashes(geo, context=f"spec '{slug}' Position 0 GEO summary")
    geo_words = [w for w in re.split(r"[\s\-]+", geo) if w]
    if len(geo_words) < 40:
        raise ValueError(f"Specification '{slug}' Position 0 GEO summary too short ({len(geo_words)} words, min 40)")
    if len(geo_words) > 60:
        raise ValueError(f"Specification '{slug}' Position 0 GEO summary exceeds 60 words ({len(geo_words)} words, max 60)")

    has_benchmark = any(ch.isdigit() for ch in geo) or any(
        term in geo.lower() for term in ["section", "irc", "statutory", "rate", "tax", "model", "percent", "threshold", "projection", "liability", "runway", "arbitrage"]
    )
    if not has_benchmark:
        raise ValueError(f"Specification '{slug}' Position 0 GEO summary lacks numerical benchmark citations or statutory references")

    # 7. Calculation steps validation (if explicitly declared in spec, must be non-empty)
    if "calculation_steps" in spec and (not spec["calculation_steps"] or not isinstance(spec["calculation_steps"], list)):
        raise ValueError(f"Specification '{slug}' missing or invalid calculation_steps")
    if "calculation_prompts" in spec and (not spec["calculation_prompts"] or not isinstance(spec["calculation_prompts"], list)):
        raise ValueError(f"Specification '{slug}' missing or invalid calculation_prompts")

    # 8. 2026 Zyppy AI ranking factors validation
    if "direct_answer_summary" in spec:
        das = spec["direct_answer_summary"]
        if not isinstance(das, str) or not das.strip():
            raise ValueError(f"Specification '{slug}' direct_answer_summary must be a non-empty string")
        assert_no_forbidden_dashes(das, context=f"spec '{slug}' direct_answer_summary")
        das_words = [w for w in re.split(r"[\s\-]+", das) if w]
        if len(das_words) < 40:
            raise ValueError(f"Specification '{slug}' direct_answer_summary too short ({len(das_words)} words, min 40)")
        if len(das_words) > 60:
            raise ValueError(f"Specification '{slug}' direct_answer_summary exceeds 60 words ({len(das_words)} words, max 60)")

    if "proprietary_calculation_table" in spec:
        pct = spec["proprietary_calculation_table"]
        if not isinstance(pct, dict) or not pct.get("rows"):
            raise ValueError(f"Specification '{slug}' proprietary_calculation_table must contain non-empty rows")

    if "quotable_statistics" in spec:
        qs = spec["quotable_statistics"]
        if not isinstance(qs, list) or len(qs) == 0:
            raise ValueError(f"Specification '{slug}' quotable_statistics must be a non-empty list")
        for item in qs:
            if not isinstance(item, dict) or not item.get("metric") or not item.get("citation"):
                raise ValueError(f"Specification '{slug}' quotable_statistics items must contain 'metric' and 'citation'")

    return True


def assert_touch_targets(css_or_html: str, is_css: bool = False, context: str = "") -> bool:
    """
    Validates that interactive controls (buttons, inputs, select) satisfy
    the 44x44px minimum touch target invariant.
    """
    undersized_height = re.findall(r'min-height:\s*(?:[0-9]|[1-3][0-9]|4[0-3])px', css_or_html)
    undersized_width = re.findall(r'min-width:\s*(?:[0-9]|[1-3][0-9]|4[0-3])px', css_or_html)
    if undersized_height:
        ctx = f" in {context}" if context else ""
        raise ValueError(f"Touch target min-height < 44px found{ctx}: {undersized_height}")
    if undersized_width:
        ctx = f" in {context}" if context else ""
        raise ValueError(f"Touch target min-width < 44px found{ctx}: {undersized_width}")
    return True


def assert_valid_jsonld(html_content: str, context: str = "") -> List[Dict[str, Any]]:
    """
    Extracts and parses all application/ld+json script blocks in HTML content.
    Fails closed if no JSON-LD is found or if any block fails to parse as valid JSON.
    """
    pattern = re.compile(r'<script\s+type=["\']application/ld\+json["\']\s*>(.*?)</script>', re.DOTALL | re.IGNORECASE)
    matches = pattern.findall(html_content)
    if not matches:
        ctx = f" in {context}" if context else ""
        raise ValueError(f"No application/ld+json blocks found{ctx}")

    parsed_blocks = []
    for idx, raw_json in enumerate(matches):
        clean_json = raw_json.strip()
        try:
            parsed = json.loads(clean_json)
            if isinstance(parsed, dict) and "@graph" in parsed and isinstance(parsed["@graph"], list):
                parsed_blocks.extend(parsed["@graph"])
            else:
                parsed_blocks.append(parsed)
        except json.JSONDecodeError as ex:
            ctx = f" in {context}" if context else ""
            raise ValueError(f"Invalid JSON-LD block {idx}{ctx}: {ex}") from ex

    return parsed_blocks


def assert_sitemap_parses(xml_content: str) -> bool:
    """
    Parses XML content and verifies valid XML schema and single <urlset> root with <loc> tags.
    Enforces sitemap URL count strictly under 10000, rejects sitemapindex, and limits clusters to 2000 pages (HWL-1076).
    Zero em-dashes.
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as ex:
        raise ValueError(f"Sitemap XML parsing failure: {ex}") from ex

    tag = root.tag.lower()
    if "sitemapindex" in tag:
        raise ValueError("Single XML sitemaps strictly required; <sitemapindex> is rejected (HWL-1076)")
    if "urlset" not in tag:
        raise ValueError(f"Expected single <urlset> root, got <{root.tag}>")

    locs = root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
    if not locs:
        locs = root.findall(".//loc")
    if not locs:
        raise ValueError("Sitemap XML contains zero <loc> entries")

    if len(locs) >= 10000:
        raise ValueError(f"Sitemap exceeds 10000 URLs limit: {len(locs)} URLs found (HWL-1076)")

    cluster_counts: Dict[str, int] = {}
    for loc in locs:
        url = (loc.text or "").strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            raise ValueError(f"Invalid <loc> URL in sitemap: '{url}'")

        parsed = urllib.parse.urlsplit(url)
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(parts) >= 2 and parts[0] == "tools":
            cluster = parts[1]
            cluster_counts[cluster] = cluster_counts.get(cluster, 0) + 1
            if cluster_counts[cluster] > 2000:
                raise ValueError(f"Topical cluster '{cluster}' exceeds 2000 pages limit: {cluster_counts[cluster]} (HWL-1076)")

    return True


class StageResult:
    """
    Contract for individual pipeline stage execution outcomes.
    Captures stage health, whether failures are blocking, and telemetry detail.
    """
    def __init__(self, stage_id: str = "", ok: bool = True, blocking: bool = False, detail: Dict[str, Any] = None, **kwargs):
        self.stage_id = stage_id or kwargs.get("stage", "")
        self.stage = kwargs.get("stage", self.stage_id)
        if "success" in kwargs:
            self.ok = kwargs["success"]
            self.success = kwargs["success"]
        else:
            self.ok = ok
            self.success = ok
        self.blocking = blocking
        self.detail = detail or {}
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "ok": self.ok,
            "blocking": self.blocking,
            "detail": self.detail,
        }


def assert_comparison_layout_contracts(html: str) -> bool:
    """
    Validates Google AI Mode Layout Container contracts on HTML:
    - Homogeneity Law: Elements within a List/Carousel/Comparison container must share
      the same entity definition (heterogeneous mixtures fail).
    - Minimum Asset Threshold: Carousel and ImageGrid containers require >= 3 validated items
      (<= 2 items flattens into vertical stack).
    Zero em-dashes. Zero en-dashes.
    """
    assert_no_forbidden_dashes(html, context="HTML layout content")
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
    except Exception as ex:
        raise ValueError(f"Failed to parse HTML for comparison layout check: {ex}") from ex

    layout_tags = soup.find_all(re.compile(r"^(layout|carousel|list|imagegrid)$", re.IGNORECASE))
    class_containers = soup.find_all(
        lambda tag: tag.get("class") and any(
            c in ("comparison-container", "comparison-table", "carousel-container", "carousel", "image-grid", "list-container")
            for c in tag.get("class")
        )
    )

    containers = list(layout_tags) + [c for c in class_containers if c not in layout_tags]

    for c in containers:
        tag_name = c.name.lower()
        is_carousel_or_grid = (
            tag_name in ("carousel", "imagegrid")
            or c.get("type") in ("inspiration", "carousel")
            or any(cls in ("carousel-container", "carousel", "image-grid") for cls in c.get("class", []))
        )
        is_comparison_or_list = (
            tag_name in ("list", "layout")
            or c.get("type") == "comparison"
            or any(cls in ("comparison-container", "comparison-table", "list-container") for cls in c.get("class", []))
        )

        items = c.find_all(re.compile(r"^(item|entity|card|article|tr|li)$", re.IGNORECASE))
        if not items:
            items = [child for child in c.find_all(recursive=False) if getattr(child, "name", None)]

        # Homogeneity Law
        entity_types = []
        for it in items:
            etype = it.get("data-entity-type") or it.get("entity-type") or it.get("type")
            if not etype and it.name.lower() == "entity":
                etype = it.get("type")
            if etype:
                entity_types.append(etype)
        if len(set(entity_types)) > 1:
            raise ValueError(
                f"Homogeneity Law violated: heterogeneous entity types detected in container "
                f"({set(entity_types)}). All elements must share identical entity taxonomy."
            )

        # Minimum Asset Threshold (>= 3 items)
        if is_carousel_or_grid and 0 < len(items) < 3:
            raise ValueError(
                f"Minimum Asset Threshold violated: carousel/image-grid requires >= 3 items (found {len(items)})"
            )

        if is_comparison_or_list and 0 < len(items) < 3:
            raise ValueError(
                f"Minimum Asset Threshold violated: comparison layout requires >= 3 items (found {len(items)})"
            )

    return True


def assert_multi_scale_semantic_compression(content: str, entity_name: str, brand_name: str) -> bool:
    """
    Enforces Google Gemini / DocumentChunker 5-stage semantic compression invariants:
    - Macro budget: <= 540 words per document/module (grounding plateau limit)
    - Meso structure: 3-sentence atomic units per core paragraph
    - Micro anchoring: entity_name or brand_name explicitly anchored in every paragraph
      to survive ellipsis concatenation during extractive grounding
    Zero em-dashes. Zero en-dashes.
    """
    assert_no_forbidden_dashes(content, context="semantic compression content")
    if not content or not content.strip():
        raise ValueError("Content cannot be empty for semantic compression assertion")

    words = [w for w in re.split(r"\s+", content.strip()) if w]
    if len(words) > 540:
        raise ValueError(
            f"Macro grounding limit exceeded: {len(words)} words (maximum 540 words allowed under grounding plateau)"
        )

    raw_paras = [p.strip() for p in re.split(r"\n\s*\n+", content) if p.strip()]
    if len(raw_paras) <= 1 and "<p" in content.lower():
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(content, "html.parser")
        p_tags = soup.find_all("p")
        if p_tags:
            raw_paras = [p.get_text(strip=True) for p in p_tags if p.get_text(strip=True)]

    entity_lower = entity_name.lower().strip()
    brand_lower = brand_name.lower().strip()

    for idx, para in enumerate(raw_paras, 1):
        para_clean = para.strip()
        para_lower = para_clean.lower()
        if entity_lower not in para_lower and brand_lower not in para_lower:
            raise ValueError(
                f"Micro entity anchoring violated in paragraph {idx}: missing explicit anchor for "
                f"'{entity_name}' or '{brand_name}' (found: '{para_clean[:60]}...')"
            )

        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', para_clean) if s.strip()]
        if len(sentences) != 3:
            raise ValueError(
                f"Meso atomic structure violated in paragraph {idx}: found {len(sentences)} sentences, "
                f"strictly requires 3-sentence units per paragraph"
            )

    return True


from pseofactory.qualification import (
    qualify_search_intent,
    check_search_intent_cannibalization,
    assert_search_intent_qualified,
)


__all__ = [
    "FORBIDDEN_JARGON",
    "PROMPT_LEAKAGE_TERMS",
    "AI_MODE_ENTITY_TAXONOMY",
    "assert_no_forbidden_dashes",
    "assert_no_prompt_leakage",
    "assert_linkedin",
    "assert_x_post",
    "assert_youtube_pinned_comment",
    "assert_youtube_description",
    "sanitize_url_slug",
    "assert_ai_mode_calculation_manifest",
    "assert_meta_tag_contract",
    "assert_url_safe_slug",
    "assert_technical_seo_spec",
    "assert_touch_targets",
    "assert_valid_jsonld",
    "assert_sitemap_parses",
    "StageResult",
    "assert_comparison_layout_contracts",
    "assert_multi_scale_semantic_compression",
    "qualify_search_intent",
    "check_search_intent_cannibalization",
    "assert_search_intent_qualified",
]

