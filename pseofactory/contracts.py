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

import ast
import operator
import re
import json
import posixpath
import html
import urllib.parse
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from datetime import datetime, timezone
from typing import List, Dict, Any, Set, Optional, Tuple, Callable, Union, Iterable

FORBIDDEN_JARGON: List[str] = [
    "synergistic alignment 1791603786",
    "synergistic alignment 1791603771",
    "delve",
    "delving",
    "game-changer",
    "testament to",
    "tapestry",
    "lorem ipsum",
    "TODO",
    "TBD",
    "[placeholder]",
    "paradigm shift",
]

PROMPT_LEAKAGE_TERMS: List[str] = [
    "model system prompt instructions 1791603786",
    "model system prompt instructions 1791603771",
    "captures striking distance",
    "search demand for position",
    "evaluating multi-tier statutory thresholds across federal and state levels, taxpayers project",
    "evaluating multi-tier statutory thresholds",
    "taxpayers project",
    "prompt:",
    "system prompt",
    "system instruction",
    "as an ai language model",
    "here is the response",
    "delve into the intricacies",
    "internal reasoning instructions",
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
    "AutonomousShipperReleaseProtocol",
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


CONVERSATIONAL_FILLER_TERMS: List[str] = [
    "welcome back to the channel",
    "welcome back",
    "in this video",
    "in today's video",
    "let's dive in",
    "let us dive in",
    "don't forget to like and subscribe",
    "smash that like button",
    "smash that like",
    "without further ado",
    "hey guys",
    "basically",
    "pretty much",
    "at the end of the day",
    "now that we covered that",
]


def assert_youtube_transcript(text_or_data: Union[str, Dict[str, Any]]) -> bool:
    """
    Validates YouTube video transcript for SEO syndication and AI citation:
    1. Bounds: 300 to 8000 characters.
    2. Zero forbidden dashes (\\u2014, \\u2013).
    3. Zero angle brackets (<, >) preventing API parsing errors.
    4. Zero prompt leakage phrases.
    5. Zero conversational filler terms.
    6. Speaker attribution tags (e.g. [Narrator] or [Host]).
    7. Timestamp markers (e.g. [00:00]).
    8. Brand entity reference ('ProfitHelm').
    """
    if isinstance(text_or_data, dict):
        text = text_or_data.get("full_text") or text_or_data.get("transcript") or ""
    elif isinstance(text_or_data, str):
        text = text_or_data
    else:
        raise ValueError(f"Invalid transcript type: {type(text_or_data)}")

    if not text or len(text) < 300:
        raise ValueError(f"YouTube transcript too short ({len(text) if text else 0} chars, min 300)")
    if len(text) > 8000:
        raise ValueError(f"YouTube transcript exceeds 8000 characters ({len(text)} chars, max 8000)")

    assert_no_forbidden_dashes(text, context="YouTube transcript")

    if "<" in text or ">" in text:
        raise ValueError("Angle brackets (< or >) are forbidden in YouTube transcript")

    assert_no_prompt_leakage(text, context="YouTube transcript")

    text_lower = text.lower()
    for filler in CONVERSATIONAL_FILLER_TERMS:
        if filler.lower() in text_lower:
            raise ValueError(f"Conversational filler forbidden in YouTube transcript: '{filler}'")

    if not re.search(r'\b\d{1,2}:\d{2}\b', text):
        raise ValueError("YouTube transcript must include timestamp markers (e.g. [00:00])")

    if not re.search(r'\[(Narrator|Speaker(\s*\d+)?|Host)\]', text):
        raise ValueError("YouTube transcript must include speaker attribution tags (e.g. [Narrator] or [Host])")

    if "profithelm" not in text_lower:
        raise ValueError("YouTube transcript must reference brand entity 'ProfitHelm'")

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


def assert_snippet_length_contract(
    quick_answer: str,
    max_snippet: Optional[int] = None,
    context: str = "",
) -> bool:
    """
    Validates that a quick-answer summary satisfies max-snippet constraints:
    1. If max_snippet is 0, snippets are completely revoked, raising ValueError.
    2. If max_snippet > 0, quick_answer length must not exceed max_snippet.
    3. Quick-answer must satisfy zero forbidden dashes.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if not isinstance(quick_answer, str):
        raise ValueError(f"quick_answer must be a string{ctx}")
    assert_no_forbidden_dashes(quick_answer, context=f"quick_answer{ctx}")
    if max_snippet is not None:
        if max_snippet == 0:
            raise ValueError(f"Snippet eligibility revoked: max-snippet is 0{ctx}")
        if max_snippet > 0 and len(quick_answer) > max_snippet:
            raise ValueError(
                f"Quick-answer length ({len(quick_answer)} chars) exceeds max-snippet ({max_snippet} chars){ctx}"
            )
    return True


def assert_ai_crawl_access_and_snippet_eligibility(
    html_content: str,
    route: str = "/",
    context: str = "",
) -> bool:
    """
    Mechanical contract enforcing Factor 1: AI Crawl Access & Snippet Eligibility (+2.20).
    Verifies that an HTML document string does not revoke snippet rights or search crawler access:
    1. Zero em-dashes and zero en-dashes.
    2. Zero nosnippet directives from robots or AI search bots.
    3. Zero noindex or none directives on public routes.
    4. max-snippet must not be 0, and quick-answer length must not exceed max-snippet limit.
    5. Zero data-nosnippet on root containers (html, body, main) or quick-answer elements.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if not isinstance(html_content, str):
        raise ValueError(f"HTML content must be a string{ctx}")

    assert_no_forbidden_dashes(html_content, context=f"HTML content{ctx}")

    # Local deferred import to prevent circular dependency
    from pseofactory.verifier import SinglePassSEODocumentParser

    parser = SinglePassSEODocumentParser()
    parser.feed(html_content)

    if parser.has_nosnippet:
        raise ValueError(f"HTML{ctx} contains 'nosnippet' directive, revoking search and AI snippet eligibility")

    if parser.has_noindex:
        raise ValueError(f"HTML{ctx} contains 'noindex' or 'none' directive, revoking search and AI snippet eligibility")

    if parser.max_snippet is not None:
        if parser.max_snippet == 0:
            raise ValueError(f"HTML{ctx} contains 'max-snippet:0' directive, revoking snippet eligibility")
        if parser.max_snippet > 0 and parser.quick_answer_text:
            if len(parser.quick_answer_text) > parser.max_snippet:
                raise ValueError(
                    f"HTML{ctx} quick-answer ({len(parser.quick_answer_text)} chars) exceeds max-snippet:{parser.max_snippet} limit"
                )

    if parser.root_has_data_nosnippet:
        raise ValueError(
            f"HTML{ctx} root container contains 'data-nosnippet', excluding page content from AI Overviews"
        )

    if parser.quick_answer_has_data_nosnippet:
        raise ValueError(
            f"HTML{ctx} quick-answer container contains 'data-nosnippet', excluding direct answer from AI Overviews"
        )

    return True


assert_ai_crawl_access = assert_ai_crawl_access_and_snippet_eligibility
assert_snippet_eligibility = assert_ai_crawl_access_and_snippet_eligibility


def assert_robots_txt_crawler_policy(
    robots_content: str,
    protected_routes: Optional[List[str]] = None,
    context: str = "",
) -> bool:
    """
    Mechanical contract validating robots.txt crawler access policy:
    1. AI search crawlers (googlebot, bingbot, perplexitybot, claudebot, oai-searchbot)
       and user-triggered bots (chatgpt-user) must NOT be blocked on protected routes.
    2. Model training bots (gptbot, ccbot, google-extended, etc.) may be blocked.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if not isinstance(robots_content, str):
        raise ValueError(f"robots.txt content must be a string{ctx}")

    routes = protected_routes or ["/", "/tools/"]

    from pseofactory.verifier import (
        MasterSEOVerifier,
        AI_SEARCH_BOTS,
        AI_USER_TRIGGERED_BOTS,
    )

    sections = MasterSEOVerifier.parse_robots_txt_sections(robots_content)
    all_search_bots = AI_SEARCH_BOTS + AI_USER_TRIGGERED_BOTS

    for bot in all_search_bots:
        for r in routes:
            if MasterSEOVerifier.is_bot_blocked(bot, r, sections):
                raise ValueError(
                    f"robots.txt crawler policy violation{ctx}: bot '{bot}' is blocked on '{r}', "
                    f"revoking AI crawl access and snippet eligibility"
                )

    return True


def assert_headers_snippet_policy(
    headers_content: str,
    public_routes: Optional[List[str]] = None,
    context: str = "",
) -> bool:
    """
    Mechanical contract validating Netlify/Cloudflare _headers snippet eligibility:
    1. Public routes must not set nosnippet, noindex, none, or max-snippet:0
       globally or for AI search crawlers.
    2. Model training crawlers (gptbot, google-extended, ccbot, etc.) may be restricted.
    3. Non-public routes (/signal, /staging, /test, /tests, /syndication) may be restricted.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if not isinstance(headers_content, str):
        raise ValueError(f"_headers content must be a string{ctx}")

    from pseofactory.verifier import (
        AI_SEARCH_BOTS,
        AI_USER_TRIGGERED_BOTS,
        AI_TRAINING_BOTS,
    )

    non_public_prefixes = ("/signal", "/staging", "/test", "/tests", "/syndication")
    training_bot_names = {b.lower() for b in AI_TRAINING_BOTS}
    search_bot_names = {b.lower() for b in AI_SEARCH_BOTS} | {b.lower() for b in AI_USER_TRIGGERED_BOTS} | {"robots", "claude-web"}

    current_route = ""
    for raw_line in headers_content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if not raw_line.startswith(" ") and not raw_line.startswith("\t"):
            current_route = line
        else:
            if ":" in line:
                h_name, h_val = line.split(":", 1)
                if h_name.strip().lower() == "x-robots-tag":
                    if current_route.startswith(non_public_prefixes):
                        continue
                    if public_routes and not any(current_route.startswith(pr) for pr in public_routes):
                        continue

                    h_val_strip = h_val.strip()
                    if ":" in h_val_strip:
                        prefix_candidate, directive_candidate = [x.strip() for x in h_val_strip.split(":", 1)]
                        prefix_lower = prefix_candidate.lower()
                        if prefix_lower in training_bot_names:
                            continue
                        elif prefix_lower in search_bot_names:
                            dir_lower = directive_candidate.lower()
                            if "nosnippet" in dir_lower:
                                raise ValueError(
                                    f"_headers applies 'nosnippet' to public route '{current_route}' for bot '{prefix_lower}'{ctx}"
                                )
                            if re.search(r'max-snippet\s*:\s*0\b', dir_lower):
                                raise ValueError(
                                    f"_headers applies 'max-snippet:0' to public route '{current_route}' for bot '{prefix_lower}'{ctx}"
                                )
                            if "noindex" in dir_lower or re.search(r'\bnone\b', dir_lower):
                                raise ValueError(
                                    f"_headers applies 'noindex' to public route '{current_route}' for bot '{prefix_lower}'{ctx}"
                                )
                            continue

                    val_lower = h_val.lower()
                    if "nosnippet" in val_lower:
                        raise ValueError(
                            f"_headers applies 'nosnippet' to public route '{current_route}' via X-Robots-Tag{ctx}"
                        )
                    if re.search(r'max-snippet\s*:\s*0\b', val_lower):
                        raise ValueError(
                            f"_headers applies 'max-snippet:0' to public route '{current_route}' via X-Robots-Tag{ctx}"
                        )
                    if "noindex" in val_lower or re.search(r'\bnone\b', val_lower):
                        raise ValueError(
                            f"_headers applies 'noindex' to public route '{current_route}' via X-Robots-Tag{ctx}"
                        )

    return True


def assert_quick_answer_passage_relevance(
    quick_answer: str,
    target_query: Optional[str] = None,
    context: str = "",
) -> bool:
    """
    Mechanical contract validating passage-level answer relevance for Factor 2: Query-Answer Match (+2.15).
    1. Quick-answer must be a non-empty string.
    2. Strict anti-slop invariant: zero em-dashes and zero en-dashes.
    3. Strictly 40 to 60 words for concise passage relevance.
    4. Sentence boundaries: 1 to 5 sentences with valid terminal punctuation.
    5. Character density: 3.0 to 15.0 chars/word.
    6. Zero generic AI jargon (FORBIDDEN_JARGON).
    7. Zero evasive summary phrasing.
    8. Semantic match: query terms match >= 50% of tokens without keyword stuffing.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if not isinstance(quick_answer, str) or not quick_answer.strip():
        raise ValueError(f"quick_answer must be a non-empty string{ctx}")

    assert_no_forbidden_dashes(quick_answer, context=f"quick_answer{ctx}")

    words = [w for w in quick_answer.split() if w.strip()]
    if len(words) < 40:
        raise ValueError(
            f"Quick-answer passage too short ({len(words)} words, strictly requires 40-60 words for passage relevance){ctx}"
        )
    if len(words) > 60:
        raise ValueError(
            f"Quick-answer passage bloated ({len(words)} words, strictly requires 40-60 words for passage relevance){ctx}"
        )

    char_density = sum(len(w) for w in words) / len(words)
    if char_density < 3.0 or char_density > 15.0:
        raise ValueError(
            f"Quick-answer character density ({char_density:.2f} chars/word) abnormal (expected 3.0-15.0){ctx}"
        )

    if not re.search(r'[.!?]["\']?\s*$', quick_answer.strip()):
        raise ValueError(f"Quick-answer passage missing terminal sentence punctuation{ctx}")

    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', quick_answer.strip()) if s.strip()]
    if len(sentences) < 1 or len(sentences) > 5:
        raise ValueError(f"Quick-answer sentence count ({len(sentences)}) outside valid 1-5 sentence bounds{ctx}")

    for j_term in FORBIDDEN_JARGON:
        if re.search(r'\b' + re.escape(j_term) + r'\b', quick_answer, re.IGNORECASE):
            raise ValueError(f"Quick-answer contains forbidden AI jargon '{j_term}'{ctx}")

    evasive_phrases = [
        "it depends",
        "consult a professional",
        "consult your accountant",
        "read more below",
        "see our guide below",
        "more details below",
        "click here",
        "check back later",
        "varies widely depending on",
    ]
    for ev_p in evasive_phrases:
        if ev_p in quick_answer.lower():
            raise ValueError(
                f"Quick-answer degenerates into evasive summary ('{ev_p}') lacking direct factual resolution{ctx}"
            )

    if target_query:
        from pseofactory.verifier import evaluate_query_answer_semantic_match
        issues = evaluate_query_answer_semantic_match(quick_answer, target_query)
        if issues:
            raise ValueError(f"{issues[0]}{ctx}")

    return True


def assert_viewport_ordering(
    html_content: str,
    context: str = "",
) -> bool:
    """
    Mechanical contract validating layout positioning and viewport ordering for Factor 2: Query-Answer Match (+2.15).
    Ensures <div class='quick-answer'> or <aside class='quick-answer'> is positioned in initial viewport:
    1. Zero em-dashes and zero en-dashes.
    2. Exactly one quick-answer container.
    3. Placed after top-level <h1> introductory header.
    4. Placed before secondary <h2> headings.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if not isinstance(html_content, str):
        raise ValueError(f"HTML content must be a string{ctx}")

    assert_no_forbidden_dashes(html_content, context=f"HTML content{ctx}")

    from pseofactory.verifier import SinglePassSEODocumentParser
    parser = SinglePassSEODocumentParser()
    parser.feed(html_content)

    if not parser.has_quick_answer:
        raise ValueError(
            f"HTML{ctx} missing quick-answer container (<div class='quick-answer'> or <aside class='quick-answer'>) in initial viewport"
        )

    if parser.quick_answer_count > 1:
        raise ValueError(
            f"HTML{ctx} contains multiple quick-answer containers ({parser.quick_answer_count}), strictly requires a single authoritative viewport answer"
        )

    if not parser.quick_answer_seen_after_h1:
        raise ValueError(
            f"HTML{ctx} quick-answer container misplaced before introductory <h1> header"
        )

    if not parser.quick_answer_seen_before_h2:
        raise ValueError(
            f"HTML{ctx} quick-answer container sunk below secondary heading (<h2>) or secondary section"
        )

    return True


def assert_query_answer_match(
    html_content: str,
    target_query: Optional[str] = None,
    route: str = "/",
    context: str = "",
) -> bool:
    """
    Mechanical contract enforcing Factor 2: Query-Answer Match (+2.15).
    Verifies that an HTML document string satisfies direct query-answer alignment in initial viewport:
    1. Zero em-dashes and zero en-dashes.
    2. Valid initial viewport ordering (after <h1>, before <h2>, single container).
    3. Populated quick-answer passage meeting 40-60 word bounds, sentence bounds, and character density.
    4. Zero forbidden jargon, zero evasive summaries, zero keyword stuffing.
    5. Direct semantic intent match against target query.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    assert_viewport_ordering(html_content, context=f"route '{route}'{ctx}")

    from pseofactory.verifier import SinglePassSEODocumentParser
    parser = SinglePassSEODocumentParser()
    parser.feed(html_content)

    query_to_check = target_query or parser.target_query
    assert_quick_answer_passage_relevance(
        parser.quick_answer_text,
        target_query=query_to_check,
        context=f"route '{route}'{ctx}",
    )
    return True


assert_quick_answer_match = assert_query_answer_match
assert_query_answer_alignment = assert_query_answer_match


# =============================================================================
# Factor 3: Brand / Entity in LLM Memory (+2.08) Contracts
# =============================================================================

AUTHORITATIVE_PROFILE_DOMAINS: Set[str] = {
    "wikidata.org",
    "wikipedia.org",
    "crunchbase.com",
    "linkedin.com",
    "github.com",
    "x.com",
    "twitter.com",
    "youtube.com",
    "facebook.com",
    "instagram.com",
    "trustpilot.com",
    "bloomberg.com",
    "sec.gov",
    "opencorporates.com",
    "pitchbook.com",
    "g2.com",
    "capterra.com",
    "bbb.org",
    "reuters.com",
    "wa.gov",
}

BRAND_ENTITY_TAXONOMY: Set[str] = {
    "Organization",
    "Corporation",
    "Brand",
    "OnlineBusiness",
    "EducationalOrganization",
    "LocalBusiness",
    "NGO",
    "GovernmentOrganization",
    "NewsMediaOrganization",
    "MedicalOrganization",
    "PerformingGroup",
    "SportsTeam",
    "Consortium",
    "FinancialService",
    "OnlineStore",
}

DISALLOWED_BRAND_TAXONOMY: Set[str] = {
    "Article",
    "WebPage",
    "BlogPosting",
    "TechArticle",
    "NewsArticle",
    "Product",
    "Thing",
    "SoftwareApplication",
    "ItemList",
    "BreadcrumbList",
    "FAQPage",
    "HowTo",
    "Guide",
    "WebSite",
}

WIKIDATA_URI_PATTERN = re.compile(
    r"^https?://(?:[a-zA-Z0-9-]+\.)?wikidata\.org/(?:wiki|entity)/Q[1-9][0-9]*/?$",
    re.IGNORECASE,
)


def assert_wikidata_uri(uri: str, context: str = "") -> bool:
    """
    Mechanical contract validating Wikidata entity URI pattern:
    1. Must be a non-empty string.
    2. Strict anti-slop: zero em-dashes and zero en-dashes.
    3. Must resolve to canonical Wikidata entity pattern (e.g. https://www.wikidata.org/wiki/Q...).
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if not isinstance(uri, str) or not uri.strip():
        raise ValueError(f"Wikidata URI must be a non-empty string{ctx}")

    assert_no_forbidden_dashes(uri, context=f"Wikidata URI{ctx}")

    clean_uri = uri.strip()
    if not WIKIDATA_URI_PATTERN.match(clean_uri):
        raise ValueError(
            f"Invalid Wikidata URI pattern '{clean_uri}'{ctx}: strictly requires canonical 'https://www.wikidata.org/wiki/Q...' format"
        )
    return True


def assert_authoritative_same_as(
    same_as: Any,
    entity_url: Optional[str] = None,
    entity_domain: Optional[str] = None,
    context: str = "",
    require_wikidata: bool = True,
) -> bool:
    """
    Mechanical contract validating sameAs array linking for Factor 3: Brand / Entity in LLM Memory (+2.08).
    1. sameAs must be a non-empty array of URL strings.
    2. Strict anti-slop: zero em-dashes and zero en-dashes across all URLs.
    3. Zero self-referential or circular links (cannot link to entity URL or own domain).
    4. All links must belong to authoritative profile domains (Wikidata, Wikipedia, LinkedIn, Crunchbase, etc.).
    5. Disallows unverified or placeholder URLs (localhost, example.com, foo.bar, etc.).
    6. Must contain at least one verified Wikidata entity reference (when require_wikidata is True).
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if isinstance(same_as, str):
        urls = [same_as.strip()]
    elif isinstance(same_as, (list, tuple)):
        urls = [str(u).strip() for u in same_as if str(u).strip()]
    else:
        raise ValueError(f"sameAs must be a list of URL strings or a URL string{ctx}")

    if not urls:
        raise ValueError(f"sameAs array is empty, strictly requires authoritative external profiles{ctx}")

    for u in urls:
        assert_no_forbidden_dashes(u, context=f"sameAs link{ctx}")

    entity_host = ""
    if entity_url:
        parsed_ent = urllib.parse.urlsplit(entity_url.strip())
        entity_host = parsed_ent.netloc.lower().split(":")[0]
        if entity_host.startswith("www."):
            entity_host = entity_host[4:]

    domain_host = ""
    if entity_domain:
        domain_host = entity_domain.strip().lower().split(":")[0].lstrip(".")
        if domain_host.startswith("www."):
            domain_host = domain_host[4:]

    has_wikidata = False

    for item in urls:
        if not item.startswith("http://") and not item.startswith("https://"):
            raise ValueError(f"sameAs URL '{item}' missing absolute HTTP or HTTPS protocol{ctx}")

        parsed = urllib.parse.urlsplit(item)
        netloc = parsed.netloc.lower().split(":")[0]
        if not netloc:
            raise ValueError(f"sameAs URL '{item}' contains invalid netloc{ctx}")

        netloc_clean = netloc[4:] if netloc.startswith("www.") else netloc

        # Self-referential / circular link checks
        if entity_host and (netloc_clean == entity_host or netloc_clean.endswith("." + entity_host)):
            raise ValueError(
                f"sameAs link '{item}' is self-referential to entity URL '{entity_url}'{ctx}"
            )
        if domain_host and (netloc_clean == domain_host or netloc_clean.endswith("." + domain_host)):
            raise ValueError(
                f"sameAs link '{item}' is self-referential to entity domain '{entity_domain}'{ctx}"
            )
        if entity_url and item.rstrip("/") == entity_url.strip().rstrip("/"):
            raise ValueError(
                f"sameAs link '{item}' is circular/self-referential to entity URL{ctx}"
            )

        # Placeholder / unverified host checks
        placeholder_hosts = {"localhost", "127.0.0.1", "example.com", "test.com", "foo.bar", "mysite.com"}
        if netloc in placeholder_hosts or netloc_clean in placeholder_hosts:
            raise ValueError(
                f"sameAs link '{item}' uses unverified or placeholder domain '{netloc}'{ctx}"
            )

        # Authoritative domain verification
        is_auth = any(netloc == d or netloc.endswith("." + d) for d in AUTHORITATIVE_PROFILE_DOMAINS)
        if not is_auth:
            raise ValueError(
                f"sameAs link '{item}' from unauthoritative domain '{netloc}'{ctx}; must be in recognized profile registry"
            )

        # Wikidata check
        if "wikidata.org" in netloc:
            assert_wikidata_uri(item, context=context)
            has_wikidata = True

    if require_wikidata and not has_wikidata:
        raise ValueError(
            f"sameAs array missing authoritative Wikidata entity reference (https://www.wikidata.org/wiki/Q...){ctx}"
        )

    return True


def assert_brand_entity_taxonomy(entity: Dict[str, Any], context: str = "") -> bool:
    """
    Mechanical contract validating unambiguous brand entity taxonomy:
    1. Entity must specify @type in BRAND_ENTITY_TAXONOMY.
    2. Strictly rejects conflation with general page topics or products (DISALLOWED_BRAND_TAXONOMY).
    3. Rejects superficial unlinked generic types (e.g. Thing).
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if not isinstance(entity, dict):
        raise ValueError(f"Entity definition must be a dictionary{ctx}")

    raw_type = entity.get("@type")
    if not raw_type:
        raise ValueError(f"Entity definition missing '@type' taxonomy specification{ctx}")

    types: List[str] = (
        [raw_type]
        if isinstance(raw_type, str)
        else list(raw_type)
        if isinstance(raw_type, (list, tuple))
        else []
    )
    if not types:
        raise ValueError(f"Entity '@type' must be a string or list of strings{ctx}")

    for t in types:
        if t in DISALLOWED_BRAND_TAXONOMY:
            raise ValueError(
                f"Entity taxonomy collision{ctx}: brand entity cannot be typed as '{t}' (general page topic, article, or product)"
            )

    has_valid_type = any(t in BRAND_ENTITY_TAXONOMY for t in types)
    if not has_valid_type:
        type_str = ", ".join(types)
        raise ValueError(
            f"Ambiguous entity taxonomy '{type_str}'{ctx}: strictly requires recognized canonical type in BRAND_ENTITY_TAXONOMY"
        )

    return True


def assert_canonical_entity_definition(
    entity: Dict[str, Any],
    brand_name: Optional[str] = None,
    brand_domain: Optional[str] = None,
    context: str = "",
) -> bool:
    """
    Mechanical contract validating canonical brand entity definition for Factor 3: Brand / Entity in LLM Memory (+2.08).
    1. Entity must be a dictionary with strict anti-slop (zero em-dashes and zero en-dashes).
    2. Must possess canonical absolute @id identifier (rejects disconnected schema fragments).
    3. Unambiguous entity taxonomy (BRAND_ENTITY_TAXONOMY).
    4. Non-empty entity name aligned with brand name if specified.
    5. Canonical absolute URL aligned with brand domain if specified.
    6. Authoritative sameAs array linking to Wikidata entity and authoritative profiles.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if not isinstance(entity, dict):
        raise ValueError(f"Canonical entity definition must be a dictionary{ctx}")

    # Anti-slop invariant across all string values in entity
    for k, v in entity.items():
        if isinstance(v, str):
            assert_no_forbidden_dashes(v, context=f"entity key '{k}'{ctx}")

    # 1. Canonical @id check
    raw_id = entity.get("@id")
    if not raw_id or not isinstance(raw_id, str) or not raw_id.strip():
        raise ValueError(
            f"Brand entity missing canonical '@id' identifier (disconnected schema fragment){ctx}"
        )
    clean_id = raw_id.strip()
    if clean_id.startswith("#") or (
        not clean_id.startswith("http://")
        and not clean_id.startswith("https://")
        and not clean_id.startswith("urn:")
    ):
        raise ValueError(
            f"Brand entity '@id' '{clean_id}' is not a canonical absolute URI (disconnected schema fragment){ctx}"
        )

    # 2. Taxonomy check
    assert_brand_entity_taxonomy(entity, context=context)

    # 3. Name check
    name_val = entity.get("name")
    if not name_val or not isinstance(name_val, str) or not name_val.strip():
        raise ValueError(f"Brand entity missing non-empty 'name' attribute{ctx}")
    clean_name = name_val.strip()
    if brand_name:
        b_clean = brand_name.strip().lower()
        ent_legal = str(entity.get("legalName", "")).strip().lower()
        if b_clean not in clean_name.lower() and b_clean not in ent_legal:
            raise ValueError(
                f"Brand entity name '{clean_name}' does not align with expected brand name '{brand_name}'{ctx}"
            )

    # 4. URL check
    url_val = entity.get("url")
    if not url_val or not isinstance(url_val, str) or not url_val.strip():
        raise ValueError(f"Brand entity missing canonical 'url' attribute{ctx}")
    clean_url = url_val.strip()
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        raise ValueError(f"Brand entity URL '{clean_url}' is not an absolute HTTP or HTTPS URL{ctx}")
    if brand_domain:
        d_clean = brand_domain.strip().lower().split(":")[0].lstrip(".")
        if d_clean.startswith("www."):
            d_clean = d_clean[4:]
        url_host = urllib.parse.urlsplit(clean_url).netloc.lower().split(":")[0]
        if url_host.startswith("www."):
            url_host = url_host[4:]
        if url_host != d_clean and not url_host.endswith("." + d_clean):
            raise ValueError(
                f"Brand entity URL '{clean_url}' host '{url_host}' does not match expected brand domain '{brand_domain}'{ctx}"
            )

    # 5. sameAs check
    if "sameAs" not in entity:
        raise ValueError(
            f"Brand entity '{clean_name}' missing 'sameAs' array linking to Wikidata and authoritative profiles{ctx}"
        )
    assert_authoritative_same_as(
        entity["sameAs"],
        entity_url=clean_url,
        entity_domain=brand_domain,
        context=f"entity '{clean_name}'{ctx}",
        require_wikidata=True,
    )

    return True


def assert_brand_entity_in_llm_memory(
    html_or_jsonld: Any,
    brand_name: Optional[str] = None,
    brand_domain: Optional[str] = None,
    context: str = "",
) -> bool:
    """
    Mechanical contract enforcing Factor 3: Brand / Entity in LLM Memory (+2.08).
    Verifies that structured data contains valid canonical brand entity grounded in Wikidata and authoritative profiles:
    1. Zero em-dashes and zero en-dashes across HTML content and structured data.
    2. Canonical entity definition with absolute @id identifier (rejects disconnected schema fragments).
    3. Unambiguous entity taxonomy (no conflation with articles, web pages, or products).
    4. Authoritative sameAs array including verified Wikidata entity reference.
    5. Zero self-referential or circular sameAs links.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    from pseofactory.verifier import extract_canonical_brand_entities

    if isinstance(html_or_jsonld, str):
        assert_no_forbidden_dashes(html_or_jsonld, context=f"HTML content{ctx}")
        pattern = re.compile(
            r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            re.IGNORECASE | re.DOTALL,
        )
        matches = pattern.findall(html_or_jsonld)
        if not matches:
            raise ValueError(
                f"Document missing Schema.org JSON-LD structured data (<script type='application/ld+json'> not found){ctx}"
            )
        parsed_blocks = []
        for idx, m in enumerate(matches):
            try:
                parsed_blocks.append(json.loads(m.strip()))
            except Exception as ex:
                raise ValueError(f"Invalid JSON-LD syntax in block {idx}{ctx}: {ex}") from ex
    elif isinstance(html_or_jsonld, (dict, list)):
        parsed_blocks = [html_or_jsonld] if isinstance(html_or_jsonld, dict) else html_or_jsonld
    else:
        raise ValueError(f"Expected HTML string or parsed JSON-LD dict/list{ctx}")

    candidates = extract_canonical_brand_entities(
        parsed_blocks,
        brand_name=brand_name,
        brand_domain=brand_domain,
    )

    if not candidates:
        raise ValueError(
            f"No canonical brand or organization entity definition found in structured data{ctx}"
        )

    last_error: Optional[Exception] = None
    for cand in candidates:
        try:
            assert_canonical_entity_definition(
                cand,
                brand_name=brand_name,
                brand_domain=brand_domain,
                context=context,
            )
            return True
        except Exception as ex:
            last_error = ex

    if last_error:
        raise last_error

    return True


assert_brand_entity_memory = assert_brand_entity_in_llm_memory
assert_entity_memory_grounding = assert_brand_entity_in_llm_memory


# =============================================================================
# Factor 4: Citable / Specific Facts (+2.07) Contracts & Syntax Rules
# =============================================================================

AUTHORITATIVE_STATUTORY_DOMAINS: Set[str] = {
    "ecfr.gov",
    "govinfo.gov",
    "uscode.house.gov",
    "irs.gov",
    "law.cornell.edu",
    "congress.gov",
    "federalregister.gov",
    "treasury.gov",
}

VAGUE_FACTUAL_GENERALIZATIONS: List[str] = [
    "according to tax laws",
    "according to the tax code",
    "many experts say",
    "experts say",
    "studies show that",
    "studies show",
    "regulations generally provide",
    "the government allows",
    "under federal guidelines",
    "industry standards indicate",
    "research indicates",
    "it is widely believed",
    "tax rules suggest",
    "authorities state",
    "guidelines generally state",
    "broadly speaking",
    "generally speaking",
    "most professionals agree",
]

CFR_CITATION_PATTERN = re.compile(
    r'\b(?P<title>[1-5]?[0-9])\s*C\.?F\.?R\.?\s*(?:(?:§+|Section|Sec\.|Part)\s*)?(?P<section>[0-9]+(?:\.[0-9]+)?(?:-[0-9]+)?(?:\([a-zA-Z0-9]+\))*)\b',
    re.IGNORECASE,
)

USC_CITATION_PATTERN = re.compile(
    r'\b(?P<title>[1-5]?[0-9])\s*U\.?S\.?C\.?(?:\s*A\.?)?\s*(?:(?:§+|Section|Sec\.)\s*)?(?P<section>[0-9]+[a-zA-Z]*(?:\([a-zA-Z0-9]+\))*)\b',
    re.IGNORECASE,
)

IRC_CITATION_PATTERN = re.compile(
    r'\bI\.?R\.?C\.?\s*(?:(?:§+|Section|Sec\.)\s*)?(?P<section>[0-9]+[a-zA-Z]*(?:\([a-zA-Z0-9]+\))*)\b',
    re.IGNORECASE,
)

IRS_GUIDANCE_PATTERNS = [
    re.compile(r'\bRev(?:enue)?\.?\s*Proc(?:edure)?\.?\s*(?P<section>[0-9]{4}-[0-9]+)\b', re.IGNORECASE),
    re.compile(r'\b(?:IRS\s+)?Notice\s+(?P<section>[0-9]{4}-[0-9]+)\b', re.IGNORECASE),
    re.compile(r'\bIRS\s+Pub(?:lication)?\.?\s*(?P<section>[0-9]+[a-zA-Z0-9\-]*)\b', re.IGNORECASE),
    re.compile(r'\bTreas(?:ury)?\.?\s*Reg(?:ulation)?\.?\s*(?:(?:§+|Section)\s*)?(?P<section>[0-9]+(?:\.[0-9]+)?(?:-[0-9]+)?(?:\([a-zA-Z0-9]+\))*)\b', re.IGNORECASE),
]

NUMERIC_FACT_PATTERN = re.compile(
    r'(?:'
    r'\$[0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?'
    r'|[0-9]+(?:\.[0-9]+)?\s*%'
    r'|[0-9]+(?:\.[0-9]+)?\s*(?:bps|basis\s+points)'
    r'|[0-9]+(?:\.[0-9]+)?x\b'
    r'|\b20[2-9][0-9]\b'
    r'|\b[0-9]{1,3}(?:,[0-9]{3})+\b'
    r'|\b[0-9]+(?:\.[0-9]+)?\s*(?:years?|months?|days?|hours?|shares?)\b'
    r')',
    re.IGNORECASE,
)

INCOMPLETE_FIGURE_PATTERNS = [
    re.compile(r'\$[xX]+'),
    re.compile(r'\b[xX]+%'),
    re.compile(r'\$\[(?:amount|number|value|x)\]', re.IGNORECASE),
    re.compile(r'\[(?:amount|number|rate|percentage|figure|placeholder)\]', re.IGNORECASE),
    re.compile(r'\b(?:TBD|NaN|\[placeholder\])\b'),
]


def extract_statutory_citations(text: str) -> List[Dict[str, str]]:
    """
    Extracts valid primary statutory citations (CFR, USC, IRC, and IRS guidance) from text.
    Zero em-dashes. Zero en-dashes.
    """
    citations: List[Dict[str, str]] = []
    seen: Set[str] = set()

    if not text or not isinstance(text, str):
        return citations

    # CFR
    for m in CFR_CITATION_PATTERN.finditer(text):
        title_num = int(m.group("title"))
        if 1 <= title_num <= 50:
            raw = m.group(0).strip()
            norm = f"{title_num} CFR § {m.group('section')}"
            if norm not in seen:
                seen.add(norm)
                citations.append({
                    "authority": "CFR",
                    "citation": raw,
                    "title": str(title_num),
                    "section": m.group("section"),
                    "normalized": norm,
                })

    # USC
    for m in USC_CITATION_PATTERN.finditer(text):
        title_num = int(m.group("title"))
        if 1 <= title_num <= 54:
            raw = m.group(0).strip()
            norm = f"{title_num} U.S.C. § {m.group('section')}"
            if norm not in seen:
                seen.add(norm)
                citations.append({
                    "authority": "USC",
                    "citation": raw,
                    "title": str(title_num),
                    "section": m.group("section"),
                    "normalized": norm,
                })

    # IRC
    for m in IRC_CITATION_PATTERN.finditer(text):
        raw = m.group(0).strip()
        sec = m.group("section")
        norm = f"IRC § {sec}"
        if norm not in seen:
            seen.add(norm)
            citations.append({
                "authority": "IRC",
                "citation": raw,
                "title": "26",
                "section": sec,
                "normalized": norm,
            })

    # IRS Guidance
    for pat in IRS_GUIDANCE_PATTERNS:
        for m in pat.finditer(text):
            raw = m.group(0).strip()
            sec = m.group("section")
            norm = raw
            if norm not in seen:
                seen.add(norm)
                citations.append({
                    "authority": "IRS",
                    "citation": raw,
                    "title": "IRS",
                    "section": sec,
                    "normalized": norm,
                })

    return citations


def detect_malformed_statutory_citations(text: str) -> List[str]:
    """
    Detects malformed, incomplete, or invalid statutory code syntax.
    Zero em-dashes. Zero en-dashes.
    """
    issues: List[str] = []
    if not text or not isinstance(text, str):
        return issues

    # 1. Dangling title/code without section number
    for m in re.finditer(r'\b([0-9]{1,3})\s*U\.?S\.?C\.?(?:\s*A\.?)?', text, re.IGNORECASE):
        after_text = text[m.end():]
        if not re.match(r'^(?:\s*(?:§+|Section|Sec\.)\s*|\s+)[0-9]+', after_text, re.IGNORECASE):
            issues.append(f"Malformed USC citation lacking valid section number: '{m.group(0).strip()}'")

    for m in re.finditer(r'\b([0-9]{1,3})\s*C\.?F\.?R\.?', text, re.IGNORECASE):
        after_text = text[m.end():]
        if not re.match(r'^(?:\s*(?:§+|Section|Sec\.|Part)\s*|\s+)[0-9]+', after_text, re.IGNORECASE):
            issues.append(f"Malformed CFR citation lacking valid section or part number: '{m.group(0).strip()}'")

    for m in re.finditer(r'\bI\.?R\.?C\.?', text, re.IGNORECASE):
        after_text = text[m.end():]
        if not re.match(r'^(?:\s*(?:§+|Section|Sec\.)\s*|\s+)[0-9]+', after_text, re.IGNORECASE):
            issues.append(f"Malformed IRC citation lacking valid section number: '{m.group(0).strip()}'")

    # 2. Out-of-bounds title numbers
    for m in re.finditer(r'\b([0-9]+)\s*U\.?S\.?C\.?(?:\s*A\.?)?\s*(?:(?:§+|Section|Sec\.)\s*)?([0-9]+[a-zA-Z]*(?:\([a-zA-Z0-9]+\))*)', text, re.IGNORECASE):
        t_num = int(m.group(1))
        if t_num < 1 or t_num > 54:
            issues.append(f"Invalid statutory title number {t_num} in USC citation (USC titles range from 1 to 54): '{m.group(0).strip()}'")

    for m in re.finditer(r'\b([0-9]+)\s*C\.?F\.?R\.?\s*(?:(?:§+|Section|Sec\.|Part)\s*)?([0-9]+(?:\.[0-9]+)?(?:-[0-9]+)?(?:\([a-zA-Z0-9]+\))*)', text, re.IGNORECASE):
        t_num = int(m.group(1))
        if t_num < 1 or t_num > 50:
            issues.append(f"Invalid statutory title number {t_num} in CFR citation (CFR titles range from 1 to 50): '{m.group(0).strip()}'")

    # 3. Missing preceding title before U.S.C. or CFR
    for m in re.finditer(r'(?<![0-9]\s)(?<![0-9])\bU\.?S\.?C\.?\s*(?:§+|Section|Sec\.)\s*[0-9]+', text, re.IGNORECASE):
        issues.append(f"Malformed statutory citation missing preceding title number: '{m.group(0).strip()}'")

    for m in re.finditer(r'(?<![0-9]\s)(?<![0-9])\bC\.?F\.?R\.?\s*(?:§+|Section|Sec\.|Part)\s*[0-9]+', text, re.IGNORECASE):
        issues.append(f"Malformed statutory citation missing preceding title number: '{m.group(0).strip()}'")

    # 4. Negative section numbers
    for m in re.finditer(r'\b(?:U\.?S\.?C\.?|C\.?F\.?R\.?|I\.?R\.?C\.?)\s*(?:§+|Section|Sec\.)\s*-\s*[0-9]+', text, re.IGNORECASE):
        issues.append(f"Malformed statutory citation contains negative section number: '{m.group(0).strip()}'")

    # 5. Placeholder or unfinalized section numbers
    for m in re.finditer(r'\b(?:U\.?S\.?C\.?|C\.?F\.?R\.?|I\.?R\.?C\.?)\s*(?:§+|Section|Sec\.)\s*(?:\[|\b)(?:TODO|TBD|placeholder|xxx|XXX|amount|number|figure)(?:\]|\b)', text, re.IGNORECASE):
        issues.append(f"Malformed statutory citation contains placeholder or unfinalized section: '{m.group(0).strip()}'")

    return issues


def detect_vague_generalizations(text: str) -> List[str]:
    """
    Detects vague generalizations disguised as factual analysis.
    Zero em-dashes. Zero en-dashes.
    """
    found: List[str] = []
    if not text or not isinstance(text, str):
        return found
    text_lower = text.lower()
    for phrase in VAGUE_FACTUAL_GENERALIZATIONS:
        if re.search(r'\b' + re.escape(phrase) + r'\b', text_lower):
            found.append(phrase)
    return found


def detect_incomplete_figures(text: str) -> List[str]:
    """
    Detects incomplete or placeholder numeric figures.
    Zero em-dashes. Zero en-dashes.
    """
    issues: List[str] = []
    if not text or not isinstance(text, str):
        return issues
    for pat in INCOMPLETE_FIGURE_PATTERNS:
        for match in pat.finditer(text):
            issues.append(f"Incomplete or placeholder figure detected: '{match.group(0).strip()}'")
    return issues


def extract_numeric_facts(text: str) -> List[str]:
    """
    Extracts high-density verifiable statistics, currency figures, percentages,
    and statutory numbers from text.
    Zero em-dashes. Zero en-dashes.
    """
    facts: List[str] = []
    if not text or not isinstance(text, str):
        return facts
    for m in NUMERIC_FACT_PATTERN.finditer(text):
        val = m.group(0).strip()
        if val:
            facts.append(val)
    return facts


def assert_statutory_citation_syntax(text_or_citation: str, context: str = "") -> bool:
    """
    Mechanical contract validating statutory citation syntax for Factor 4.
    Ensures primary statutory citations follow valid legal code syntax and rejects
    malformed, dangling, or out-of-bounds statutory citations.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    assert_no_forbidden_dashes(text_or_citation, context=f"statutory citation{ctx}")

    malformed = detect_malformed_statutory_citations(text_or_citation)
    if malformed:
        raise ValueError(f"Malformed statutory citation syntax{ctx}: {'; '.join(malformed)}")

    valid = extract_statutory_citations(text_or_citation)
    if not valid:
        raise ValueError(f"No valid primary statutory citations found{ctx} (requires CFR, USC, IRC, or IRS code)")

    return True


def assert_no_vague_generalizations(text: str, context: str = "") -> bool:
    """
    Mechanical contract rejecting vague generalizations disguised as factual analysis.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    assert_no_forbidden_dashes(text, context=f"factual analysis{ctx}")
    vague_phrases = detect_vague_generalizations(text)
    if vague_phrases:
        phrase_list = ", ".join(f"'{p}'" for p in vague_phrases)
        raise ValueError(
            f"Vague generalization disguised as factual analysis detected{ctx}: {phrase_list} "
            f"(Factor 4 strictly requires primary statutory citations and verifiable numbers)"
        )
    return True


def assert_numeric_data_density(text: str, min_facts: int = 3, context: str = "") -> bool:
    """
    Mechanical contract verifying high-density verifiable statistics, numbers, and facts.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    assert_no_forbidden_dashes(text, context=f"numeric content{ctx}")

    incomp = detect_incomplete_figures(text)
    if incomp:
        raise ValueError(f"Incomplete numeric figure detected{ctx}: {'; '.join(incomp)}")

    facts = extract_numeric_facts(text)
    if len(facts) < min_facts:
        raise ValueError(
            f"Numeric data density violation{ctx}: found {len(facts)} numeric facts, "
            f"strictly requires >= {min_facts} verifiable figures"
        )
    return True


class _SimpleTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables: List[Dict[str, Any]] = []
        self.in_table = False
        self.current_headers: List[str] = []
        self.current_rows: List[List[str]] = []
        self.current_row: List[str] = []
        self.current_cell_tag: Optional[str] = None
        self.current_cell_data: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.in_table = True
            self.current_headers = []
            self.current_rows = []
        elif tag == "tr":
            self.current_row = []
        elif tag in ("th", "td"):
            self.current_cell_tag = tag
            self.current_cell_data = []

    def handle_endtag(self, tag):
        if tag in ("th", "td"):
            content = "".join(self.current_cell_data).strip()
            if self.current_cell_tag == "th":
                self.current_headers.append(content)
            else:
                self.current_row.append(content)
            self.current_cell_tag = None
            self.current_cell_data = []
        elif tag == "tr":
            if self.current_row:
                self.current_rows.append(self.current_row)
            self.current_row = []
        elif tag == "table":
            self.in_table = False
            self.tables.append({
                "headers": list(self.current_headers),
                "rows": list(self.current_rows),
            })
            self.current_headers = []
            self.current_rows = []

    def handle_data(self, data):
        if self.current_cell_tag:
            self.current_cell_data.append(data)


def assert_data_table_structure(table_html: str, context: str = "") -> bool:
    """
    Mechanical contract validating structured data tables for Factor 4:
    1. Zero em-dashes and zero en-dashes across all table cells and headers.
    2. Document must contain a structured <table> element.
    3. Mandatory structured <th> header cells (minimum 2 columns).
    4. Non-empty <td> data cells in structured <tr> rows (minimum 1 data row).
    5. Rejects unstructured narrative blocks masquerading as data tables.
    6. Verifiable extractable data points (numeric values, statutory references, or comparative metrics).
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if not isinstance(table_html, str):
        raise ValueError(f"Table HTML must be a string{ctx}")

    assert_no_forbidden_dashes(table_html, context=f"data table{ctx}")

    if "<table" not in table_html.lower():
        raise ValueError(f"Document missing <table> element{ctx}")

    parser = _SimpleTableParser()
    parser.feed(table_html)

    if not parser.tables:
        raise ValueError(f"Malformed or empty <table> structure{ctx}")

    last_error: Optional[Exception] = None
    compliant_tables = 0

    for idx, tbl in enumerate(parser.tables):
        headers = tbl["headers"]
        rows = tbl["rows"]

        # Anti-slop across headers and rows
        for h in headers:
            assert_no_forbidden_dashes(h, context=f"table {idx} header '{h}'{ctx}")
        for r_idx, r in enumerate(rows):
            for c_idx, c in enumerate(r):
                assert_no_forbidden_dashes(c, context=f"table {idx} row {r_idx} cell {c_idx}{ctx}")

        # Check for unstructured narrative blocks masquerading as data tables
        if not headers:
            for r in rows:
                for c in r:
                    if len(c) > 150 or len(c.split()) > 30:
                        raise ValueError(
                            f"Unstructured narrative block masquerading as data table in table {idx}{ctx}: "
                            f"table lacks <th> headers and dumps unstructured prose into a cell"
                        )
            if not rows or (len(rows) == 1 and len(rows[0]) == 1):
                raise ValueError(
                    f"Unstructured narrative block masquerading as data table in table {idx}{ctx}: "
                    f"table lacks <th> headers and columnar grid structure"
                )
            raise ValueError(f"Data table {idx} missing structured <th> header cells{ctx}")

        if len(headers) < 2:
            raise ValueError(
                f"Data table {idx} column count ({len(headers)}) below minimum 2 columns{ctx}"
            )

        if not rows:
            raise ValueError(f"Data table {idx} contains no data rows (empty table){ctx}")

        # Check rows column count and cell non-emptiness
        has_empty_cell = False
        has_insufficient_cols = False
        for r_idx, r in enumerate(rows):
            if len(r) < 2:
                has_insufficient_cols = True
                break
            for c in r:
                if not c or not c.strip():
                    has_empty_cell = True
                    break
            if has_empty_cell:
                break

        if has_insufficient_cols:
            raise ValueError(
                f"Data table {idx} contains rows with fewer than 2 columns{ctx}"
            )

        if has_empty_cell:
            raise ValueError(
                f"Data table {idx} contains empty or blank data cells{ctx}"
            )

        # Extractable quantitative or statutory data points check
        all_cells = list(headers)
        for r in rows:
            all_cells.extend(r)

        has_data_point = False
        for c in all_cells:
            if extract_numeric_facts(c) or extract_statutory_citations(c):
                has_data_point = True
                break

        if not has_data_point:
            raise ValueError(
                f"Data table {idx} lacks extractable quantitative data points or verifiable figures{ctx}"
            )

        compliant_tables += 1

    if compliant_tables == 0 and last_error:
        raise last_error

    return True


def assert_citable_specific_facts(
    html_or_text: str,
    min_statutory_citations: int = 1,
    min_numeric_facts: int = 3,
    require_data_table: bool = True,
    context: str = "",
) -> bool:
    """
    Mechanical contract enforcing Factor 4: Citable / Specific Facts (+2.07).
    Verifies:
    1. Zero em-dashes and zero en-dashes across document.
    2. Primary statutory citations present with valid syntax (CFR, USC, IRC, IRS codes).
    3. Zero malformed statutory syntax.
    4. Zero vague generalizations disguised as factual analysis.
    5. High numeric data density and zero incomplete/placeholder figures.
    6. Structured data tables present with headers, multiple rows/cols, and extractable figures.
    7. Rejects unreferenced statistics lacking primary citations when claiming regulatory thresholds.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if not isinstance(html_or_text, str):
        raise ValueError(f"Content must be a string{ctx}")

    # 1. Anti-slop invariant
    assert_no_forbidden_dashes(html_or_text, context=f"document{ctx}")

    # 2. Vague generalizations check
    assert_no_vague_generalizations(html_or_text, context=context)

    # 3. Malformed statutory citations check
    malformed = detect_malformed_statutory_citations(html_or_text)
    if malformed:
        raise ValueError(f"Malformed statutory citation syntax{ctx}: {'; '.join(malformed)}")

    # 4. Incomplete figures check
    incomp = detect_incomplete_figures(html_or_text)
    if incomp:
        raise ValueError(f"Incomplete numeric figure detected{ctx}: {'; '.join(incomp)}")

    # 5. Primary statutory citations presence
    citations = extract_statutory_citations(html_or_text)
    if len(citations) < min_statutory_citations:
        raise ValueError(
            f"Statutory citation deficit{ctx}: found {len(citations)} citations, "
            f"strictly requires >= {min_statutory_citations} primary statutory citations (CFR, USC, IRC, or IRS code)"
        )

    # 6. Unreferenced statistics check
    regulatory_keywords = [
        "statutory limit",
        "deduction cap",
        "tax bracket",
        "depreciation allowance",
        "safe harbor",
        "phaseout threshold",
        "statutory threshold",
        "federal tax rate",
        "annual exclusion",
        "lifetime exemption",
    ]
    text_lower = html_or_text.lower()
    has_reg_claim = any(k in text_lower for k in regulatory_keywords)
    if has_reg_claim and not citations:
        raise ValueError(
            f"Unreferenced statistics lacking primary citations{ctx}: "
            f"regulatory or statutory thresholds claimed without primary citation"
        )

    # 7. Numeric data density check
    assert_numeric_data_density(html_or_text, min_facts=min_numeric_facts, context=context)

    # 8. Data table structure check
    if require_data_table:
        assert_data_table_structure(html_or_text, context=context)

    return True


assert_citable_facts = assert_citable_specific_facts
assert_specific_facts = assert_citable_specific_facts
assert_primary_statutory_citations = assert_statutory_citation_syntax


# =============================================================================
# Factor 5: Organic Fan-Out Coverage Rankings (+1.91) Contracts & Verification
# =============================================================================

DEFAULT_FAN_OUT_SUBTOPIC_FACETS: Dict[str, Dict[str, Any]] = {
    "prerequisites_eligibility": {
        "name": "Prerequisites & Eligibility",
        "description": "criteria, qualifying conditions, who qualifies, eligibility rules, baseline requirements",
        "keywords": (
            "criteria",
            "qualifying conditions",
            "qualifying condition",
            "who qualifies",
            "eligibility rules",
            "eligibility rule",
            "baseline requirements",
            "baseline requirement",
            "prerequisites",
            "prerequisite",
            "eligibility",
            "qualify",
            "qualifies",
            "qualification",
        ),
    },
    "timing_deadlines": {
        "name": "Timing & Deadlines",
        "description": "effective dates, deadlines, sunset dates, phaseout schedules, recertification timing",
        "keywords": (
            "effective dates",
            "effective date",
            "deadlines",
            "deadline",
            "sunset dates",
            "sunset date",
            "phaseout schedules",
            "phaseout schedule",
            "recertification timing",
            "recertification",
            "sunset",
            "due date",
            "due dates",
            "timing",
        ),
    },
    "procedural_steps": {
        "name": "Procedural Steps",
        "description": "how to apply, step-by-step application instructions, required forms, submission workflow",
        "keywords": (
            "how to apply",
            "step-by-step",
            "step by step",
            "application instructions",
            "required forms",
            "required form",
            "submission workflow",
            "application steps",
            "application process",
            "how to file",
            "procedural steps",
            "filing workflow",
        ),
    },
    "alternatives_comparison": {
        "name": "Alternatives & Comparison",
        "description": "comparison vs alternative options, scenario trade-offs, standard vs specialized regimes",
        "keywords": (
            "comparison vs alternative options",
            "alternative options",
            "scenario trade-offs",
            "scenario tradeoffs",
            "standard vs specialized regimes",
            "standard vs specialized",
            "comparison",
            "alternative",
            "alternatives",
            "trade-off",
            "trade-offs",
            "tradeoff",
            "tradeoffs",
            "versus",
            "vs",
            "compare",
        ),
    },
    "exceptions_limits": {
        "name": "Exceptions & Limits",
        "description": "limitations, disqualifications, phaseout ceilings, penalties, edge cases, gotchas",
        "keywords": (
            "limitations",
            "limitation",
            "disqualifications",
            "disqualification",
            "phaseout ceilings",
            "phaseout ceiling",
            "penalties",
            "penalty",
            "edge cases",
            "edge case",
            "gotchas",
            "gotcha",
            "exceptions",
            "exception",
            "limits",
        ),
    },
    "consequences_impact": {
        "name": "Consequences & Impact",
        "description": "tax consequences, financial liabilities, net payoff impact, reporting forms",
        "keywords": (
            "tax consequences",
            "tax consequence",
            "financial liabilities",
            "financial liability",
            "net payoff impact",
            "net payoff",
            "reporting forms",
            "reporting form",
            "consequences",
            "consequence",
            "liabilities",
            "liability",
            "tax impact",
            "financial impact",
        ),
    },
}


def classify_subtopic_facets(
    html_or_text: str,
    facets: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Set[str]:
    """
    Classifies which ordinary SEO subtopic dimensions are addressed in HTML or text content.
    Zero em-dashes. Zero en-dashes.
    """
    if not isinstance(html_or_text, str) or not html_or_text.strip():
        return set()

    active_facets = facets if facets is not None else DEFAULT_FAN_OUT_SUBTOPIC_FACETS
    clean_text = html.unescape(re.sub(r'<[^>]+>', ' ', html_or_text))
    normalized_text = " " + re.sub(r'\s+', ' ', clean_text).lower() + " "
    raw_normalized = " " + re.sub(r'\s+', ' ', html_or_text).lower() + " "

    covered: Set[str] = set()

    for facet_key, facet_meta in active_facets.items():
        candidates: Set[str] = set()

        if "keywords" in facet_meta and facet_meta["keywords"]:
            for kw in facet_meta["keywords"]:
                candidates.add(kw.strip().lower())

        desc = facet_meta.get("description", "")
        if desc:
            for term in desc.split(","):
                cleaned_term = term.strip().lower()
                if cleaned_term:
                    candidates.add(cleaned_term)

        candidates.add(facet_key.replace("_", " ").lower())

        matched = False
        for cand in candidates:
            if not cand:
                continue
            pattern = rf"\b{re.escape(cand)}\b"
            if re.search(pattern, normalized_text) or re.search(pattern, raw_normalized):
                matched = True
                break

        if matched:
            covered.add(facet_key)

    return covered


def evaluate_page_set_fan_out_coverage(
    pages: Dict[str, str],
    required_subtopics: Optional[Iterable[str]] = None,
    min_coverage_ratio: float = 0.6,
    facets: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Evaluates ordinary SEO query fan-out subtopic coverage across a set of pages.
    Detects covered and missing subtopics across the page set. If any required or expected subtopics
    have 0 covering pages, records issue:
    Page set fan-out coverage deficit: missing related subtopic search '{facet_key}' ({facet_meta['description']} not addressed across page set)
    Zero em-dashes. Zero en-dashes.
    """
    active_facets = facets if facets is not None else DEFAULT_FAN_OUT_SUBTOPIC_FACETS
    issues: List[str] = []

    if not isinstance(pages, dict):
        return {
            "status": "FAIL",
            "total_pages": 0,
            "covered_subtopics": [],
            "missing_subtopics": sorted(list(active_facets.keys())),
            "page_set_coverage_ratio": 0.0,
            "page_coverage": {},
            "subtopic_page_counts": {k: 0 for k in active_facets},
            "violations_count": 1,
            "issues": ["Pages collection must be a dictionary mapping routes to HTML content"],
        }

    for route, content in pages.items():
        if isinstance(content, str):
            if "\u2014" in content:
                issues.append(f"Page {route}: Document contains forbidden em-dash")
            if "\u2013" in content:
                issues.append(f"Page {route}: Document contains forbidden en-dash")

    page_coverage: Dict[str, List[str]] = {}
    subtopic_page_counts: Dict[str, int] = {k: 0 for k in active_facets}
    covered_subtopics_set: Set[str] = set()

    for route, content in pages.items():
        cov = classify_subtopic_facets(content, facets=active_facets)
        page_coverage[route] = sorted(list(cov))
        for facet_key in cov:
            covered_subtopics_set.add(facet_key)
            if facet_key in subtopic_page_counts:
                subtopic_page_counts[facet_key] += 1

    total_facets_count = len(active_facets)
    covered_count = len(covered_subtopics_set)
    page_set_coverage_ratio = (covered_count / total_facets_count) if total_facets_count > 0 else 1.0

    missing_subtopics: List[str] = []

    if required_subtopics is not None:
        req_list = list(required_subtopics)
        for req_key in req_list:
            if subtopic_page_counts.get(req_key, 0) == 0:
                missing_subtopics.append(req_key)
                facet_meta = active_facets.get(req_key, {"description": req_key})
                issues.append(
                    f"Page set fan-out coverage deficit: missing related subtopic search '{req_key}' "
                    f"({facet_meta.get('description', req_key)} not addressed across page set)"
                )
        if page_set_coverage_ratio < min_coverage_ratio:
            ratio_deficit_issue = (
                f"Page set fan-out coverage ratio deficit: coverage ratio {page_set_coverage_ratio:.2f} "
                f"strictly requires >= {min_coverage_ratio:.2f}"
            )
            if ratio_deficit_issue not in issues:
                issues.append(ratio_deficit_issue)
    else:
        if page_set_coverage_ratio < min_coverage_ratio:
            for facet_key, facet_meta in active_facets.items():
                if subtopic_page_counts.get(facet_key, 0) == 0:
                    missing_subtopics.append(facet_key)
                    issues.append(
                        f"Page set fan-out coverage deficit: missing related subtopic search '{facet_key}' "
                        f"({facet_meta.get('description', facet_key)} not addressed across page set)"
                    )
        elif len(pages) == 0:
            missing_subtopics = sorted(list(active_facets.keys()))
            issues.append("Page set fan-out coverage deficit: page set is empty")

    return {
        "status": "PASS" if not issues else "FAIL",
        "total_pages": len(pages),
        "covered_subtopics": sorted(list(covered_subtopics_set)),
        "missing_subtopics": sorted(list(set(missing_subtopics))),
        "page_set_coverage_ratio": round(page_set_coverage_ratio, 4),
        "page_coverage": page_coverage,
        "subtopic_page_counts": subtopic_page_counts,
        "violations_count": len(issues),
        "issues": issues,
    }


def assert_page_set_fan_out_coverage(
    pages: Dict[str, str],
    required_subtopics: Optional[Iterable[str]] = None,
    min_coverage_ratio: float = 0.6,
    context: str = "",
) -> bool:
    """
    Mechanical contract validating page set query fan-out subtopic coverage.
    Raises ValueError if status is FAIL with the list of missing subtopics.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    res = evaluate_page_set_fan_out_coverage(
        pages=pages,
        required_subtopics=required_subtopics,
        min_coverage_ratio=min_coverage_ratio,
    )
    if res["status"] == "FAIL":
        missing = res.get("missing_subtopics", [])
        if missing:
            missing_names = ", ".join(f"'{m}'" for m in missing)
            raise ValueError(
                f"Page set fan-out coverage deficit{ctx}: missing required or expected subtopics: {missing_names}"
            )
        elif res.get("issues"):
            raise ValueError(f"Page set fan-out coverage deficit{ctx}: {'; '.join(res['issues'])}")
        else:
            raise ValueError(f"Page set fan-out coverage deficit{ctx}")
    return True


SUBQUERY_QUESTION_STARTERS: Tuple[str, ...] = (
    "what",
    "how",
    "when",
    "where",
    "why",
    "which",
    "can",
    "does",
    "do",
    "is",
    "are",
    "who",
    "should",
    "could",
    "would",
)

SECONDARY_INTENT_KEYWORDS: Tuple[str, ...] = (
    "variant",
    "scenario",
    "option",
    "alternative",
    "comparison",
    "vs",
    "versus",
    "threshold",
    "calculation",
    "calculator",
    "formula",
    "breakdown",
    "schedule",
    "method",
    "tier",
    "bracket",
    "rule",
    "guideline",
    "exception",
    "phaseout",
    "rate",
    "deduction",
    "depreciation",
    "election",
)


def extract_subquery_sections(html_or_text: str) -> List[Dict[str, Any]]:
    """
    Extracts subheadings (h2, h3, h4) and their following content sections from HTML or text.
    Classifies whether each section addresses a related question, secondary intent, or calculation variant.
    Zero em-dashes. Zero en-dashes.
    """
    if not isinstance(html_or_text, str):
        return []

    sections: List[Dict[str, Any]] = []

    target_content = html_or_text
    if "<" in html_or_text and ">" in html_or_text:
        target_content = re.sub(
            r'<(?P<tag>div|section|article)\b[^>]*(?:class=["\'][^"\']*(?:calculation-variant|fan-out-node|calc-variant|calculation-node|variant-container)[^"\']*["\']|data-variant(?:-id)?=["\'][^"\']+["\'])[^>]*>.*?</(?P=tag)>',
            ' ',
            html_or_text,
            flags=re.IGNORECASE | re.DOTALL,
        )

    # If HTML headings are present, extract via regex
    heading_pattern = re.compile(
        r'<h([2-4])\b([^>]*)>(.*?)</h\1>',
        re.IGNORECASE | re.DOTALL,
    )
    matches = list(heading_pattern.finditer(target_content))

    if matches:
        for idx, match in enumerate(matches):
            lvl = int(match.group(1))
            heading_html = match.group(3)
            clean_heading = re.sub(r'<[^>]+>', '', heading_html).strip()

            start_pos = match.end()
            end_pos = matches[idx + 1].start() if idx + 1 < len(matches) else len(target_content)
            body_html = target_content[start_pos:end_pos]
            body_text = re.sub(r'<[^>]+>', ' ', body_html)
            body_text = re.sub(r'\s+', ' ', body_text).strip()

            heading_lower = clean_heading.lower()
            starts_q = any(heading_lower.startswith(w + " ") for w in SUBQUERY_QUESTION_STARTERS)
            ends_q = heading_lower.endswith("?")
            is_question = starts_q or ends_q
            is_sec_intent = any(k in heading_lower for k in SECONDARY_INTENT_KEYWORDS)

            words = body_text.split() if body_text else []
            sections.append({
                "level": lvl,
                "heading": clean_heading,
                "body_text": body_text,
                "word_count": len(words),
                "is_question": is_question,
                "is_secondary_intent": is_sec_intent,
                "is_subquery": is_question or is_sec_intent,
                "has_calculation": bool(
                    "<table" in body_html.lower()
                    or "<form" in body_html.lower()
                    or "<input" in body_html.lower()
                    or re.search(r'\$?\d+(?:,\d+)*(?:\.\d+)?%?', body_text)
                ),
            })
    else:
        # Markdown or plain text heading parser (## or ###)
        lines = html_or_text.split("\n")
        current_heading = ""
        current_lines: List[str] = []
        for line in lines:
            m_h = re.match(r'^(#{2,4})\s+(.+)$', line.strip())
            if m_h:
                if current_heading:
                    txt = " ".join(current_lines).strip()
                    words = txt.split()
                    h_lower = current_heading.lower()
                    starts_q = any(h_lower.startswith(w + " ") for w in SUBQUERY_QUESTION_STARTERS)
                    ends_q = h_lower.endswith("?")
                    sections.append({
                        "level": 2,
                        "heading": current_heading,
                        "body_text": txt,
                        "word_count": len(words),
                        "is_question": starts_q or ends_q,
                        "is_secondary_intent": any(k in h_lower for k in SECONDARY_INTENT_KEYWORDS),
                        "is_subquery": (starts_q or ends_q) or any(k in h_lower for k in SECONDARY_INTENT_KEYWORDS),
                        "has_calculation": bool(re.search(r'\$?\d+(?:,\d+)*(?:\.\d+)?%?', txt)),
                    })
                current_heading = m_h.group(2).strip()
                current_lines = []
            else:
                current_lines.append(line)

        if current_heading:
            txt = " ".join(current_lines).strip()
            words = txt.split()
            h_lower = current_heading.lower()
            starts_q = any(h_lower.startswith(w + " ") for w in SUBQUERY_QUESTION_STARTERS)
            ends_q = h_lower.endswith("?")
            sections.append({
                "level": 2,
                "heading": current_heading,
                "body_text": txt,
                "word_count": len(words),
                "is_question": starts_q or ends_q,
                "is_secondary_intent": any(k in h_lower for k in SECONDARY_INTENT_KEYWORDS),
                "is_subquery": (starts_q or ends_q) or any(k in h_lower for k in SECONDARY_INTENT_KEYWORDS),
                "has_calculation": bool(re.search(r'\$?\d+(?:,\d+)*(?:\.\d+)?%?', txt)),
            })

    return sections


def detect_shallow_subquestions(
    subqueries: List[Dict[str, Any]],
    min_words: int = 15,
) -> List[str]:
    """
    Detects subqueries or related sub-questions with shallow, uninformative, or missing answers.
    Zero em-dashes. Zero en-dashes.
    """
    shallow: List[str] = []
    for sq in subqueries:
        if sq.get("is_subquery"):
            wc = sq.get("word_count", 0)
            if wc < min_words:
                shallow.append(
                    f"Subquery heading '{sq.get('heading')}' has shallow answer ({wc} words, strictly requires >= {min_words} words)"
                )
    return shallow


def assert_subquery_clustering(
    html_or_text: str,
    min_subqueries: int = 2,
    min_words_per_answer: int = 15,
    context: str = "",
) -> bool:
    """
    Mechanical contract validating subquery clustering and secondary intent coverage.
    Ensures:
    1. Zero forbidden em-dashes and en-dashes.
    2. Document clusters >= min_subqueries related sub-questions or secondary intent topics.
    3. Rejects shallow question lists that provide inadequate or empty answers.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if not isinstance(html_or_text, str):
        raise ValueError(f"Content must be a string{ctx}")

    assert_no_forbidden_dashes(html_or_text, context=f"document{ctx}")

    sections = extract_subquery_sections(html_or_text)
    subqueries = [s for s in sections if s.get("is_subquery")]

    if len(subqueries) < min_subqueries:
        raise ValueError(
            f"Subquery clustering deficit{ctx}: found {len(subqueries)} clustered subqueries, "
            f"strictly requires >= {min_subqueries} related sub-questions or secondary intent headings"
        )

    shallow = detect_shallow_subquestions(subqueries, min_words=min_words_per_answer)
    if shallow:
        raise ValueError(
            f"Shallow question list detected{ctx}: {'; '.join(shallow)}"
        )

    return True


def extract_calculation_variant_nodes(html_or_text: str) -> List[Dict[str, Any]]:
    """
    Extracts calculation variant containers and nodes from HTML or text.
    Identifies variant nodes by:
    - Containers with class containing calculation-variant, fan-out-node, calc-variant, calculation-node, or variant-container.
    - Containers with attributes: data-variant-id, data-variant, data-calculation-variant, data-node-id.
    - Explicit section IDs: id="variant-..." or id="calc-...".
    - Heading sections with calculation keywords and explicit calculation logic.
    For each node, extracts node id, title, calculation indicators, and outgoing links.
    Zero em-dashes. Zero en-dashes.
    """
    if not isinstance(html_or_text, str):
        return []

    nodes: List[Dict[str, Any]] = []

    # Container-based detection via regex
    container_pattern = re.compile(
        r'<(?P<tag>div|section|article)\b(?P<attrs>[^>]*(?:(?:class=["\'][^"\']*(?:calculation-variant|fan-out-node|calc-variant|calculation-node|variant-container)[^"\']*["\'])|(?:data-variant(?:-id)?=["\'][^"\']+["\'])|(?:data-node-id=["\'][^"\']+["\'])|(?:id=["\'](?:variant|calc|node)[-_][^"\']+["\']))[^>]*)>(?P<body>.*?)</(?P=tag)>',
        re.IGNORECASE | re.DOTALL,
    )

    matches = list(container_pattern.finditer(html_or_text))
    if matches:
        for idx, match in enumerate(matches):
            attrs_str = match.group("attrs")
            body_html = match.group("body")

            m_id = re.search(r'\b(?:id|data-variant-id|data-node-id|data-variant)=["\']([^"\']+)["\']', attrs_str, re.IGNORECASE)
            node_id = m_id.group(1).strip() if m_id else f"variant-{idx + 1}"

            m_h = re.search(r'<h[1-6]\b[^>]*>(.*?)</h[1-6]>', body_html, re.IGNORECASE | re.DOTALL)
            title = re.sub(r'<[^>]+>', '', m_h.group(1)).strip() if m_h else node_id

            links = re.findall(r'<a\b[^>]*\bhref=["\']([^"\']+)["\']', body_html, re.IGNORECASE)

            body_without_heading = re.sub(r'<h[1-6]\b[^>]*>.*?</h[1-6]>', '', body_html, flags=re.IGNORECASE | re.DOTALL)
            has_calc = (
                "<form" in body_without_heading.lower()
                or "<input" in body_without_heading.lower()
                or "<table" in body_without_heading.lower()
                or bool(re.search(r'(=|\+|\-|\*|/|%|\$)\s*[0-9]+', body_without_heading))
                or bool(re.search(r'\$[0-9]+', body_without_heading))
                or bool(re.search(r'\b[0-9]+(?:\.[0-9]+)?\s*%', body_without_heading))
            )

            body_text = re.sub(r'<[^>]+>', ' ', body_html)
            body_text = re.sub(r'\s+', ' ', body_text).strip()

            nodes.append({
                "id": node_id,
                "title": title,
                "outgoing_links": links,
                "has_calculation": has_calc,
                "word_count": len(body_text.split()),
                "raw_html": body_html,
            })
    else:
        # Fallback: inspect subheadings that represent calculation variants
        sections = extract_subquery_sections(html_or_text)
        variant_sections = [
            s for s in sections
            if any(k in s.get("heading", "").lower() for k in ("variant", "scenario", "option", "calculator", "calculation", "tier", "regime"))
        ]
        for idx, vs in enumerate(variant_sections):
            h = vs.get("heading", "")
            node_id = re.sub(r'[^a-z0-9]+', '-', h.lower()).strip('-') or f"variant-{idx + 1}"
            b_text = vs.get("body_text", "")
            links = re.findall(r'https?://[^\s]+|#[-a-z0-9_]+|/[-a-z0-9_/]+', b_text)
            has_calc = vs.get("has_calculation", False)
            nodes.append({
                "id": node_id,
                "title": h,
                "outgoing_links": links,
                "has_calculation": has_calc,
                "word_count": vs.get("word_count", 0),
                "raw_html": b_text,
            })

    return nodes


def detect_orphaned_calculation_nodes(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Identifies orphaned calculation nodes lacking outgoing or incoming cross-links
    to other calculation nodes within the fan-out cluster.
    Zero em-dashes. Zero en-dashes.
    """
    if len(nodes) <= 1:
        return []

    node_ids = {n["id"].lower(): n for n in nodes}
    id_list = list(node_ids.keys())

    outgoing: Dict[str, Set[str]] = {nid: set() for nid in id_list}
    incoming: Dict[str, Set[str]] = {nid: set() for nid in id_list}

    for nid, node in node_ids.items():
        for link in node.get("outgoing_links", []):
            clean_link = link.strip().lower()
            target_id = clean_link.split("#")[-1] if "#" in clean_link else clean_link.rstrip("/").split("/")[-1]
            for other_id in id_list:
                if other_id == nid:
                    continue
                if target_id == other_id or target_id in other_id or other_id in target_id:
                    outgoing[nid].add(other_id)
                    incoming[other_id].add(nid)

    orphaned: List[Dict[str, Any]] = []
    for nid, node in node_ids.items():
        out_count = len(outgoing[nid])
        in_count = len(incoming[nid])
        if out_count == 0 or in_count == 0:
            reasons = []
            if out_count == 0:
                reasons.append("zero outgoing cross-links to related calculation variants")
            if in_count == 0:
                reasons.append("zero incoming cross-links from related calculation variants")
            orphaned.append({
                "id": node["id"],
                "title": node.get("title", ""),
                "outgoing_count": out_count,
                "incoming_count": in_count,
                "reason": " and ".join(reasons),
            })

    return orphaned


def verify_calculation_variant_reciprocity(nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Verifies bidirectional reciprocal cross-linking between related calculation variant nodes.
    If Node A links to Node B, Node B must link back to Node A.
    Zero em-dashes. Zero en-dashes.
    """
    if len(nodes) <= 1:
        return {"is_reciprocal": True, "unreciprocated_pairs": [], "issues": []}

    node_ids = {n["id"].lower(): n for n in nodes}
    id_list = list(node_ids.keys())

    outgoing: Dict[str, Set[str]] = {nid: set() for nid in id_list}
    for nid, node in node_ids.items():
        for link in node.get("outgoing_links", []):
            clean_link = link.strip().lower()
            target_id = clean_link.split("#")[-1] if "#" in clean_link else clean_link.rstrip("/").split("/")[-1]
            for other_id in id_list:
                if other_id == nid:
                    continue
                if target_id == other_id or target_id in other_id or other_id in target_id:
                    outgoing[nid].add(other_id)

    unreciprocated: List[Tuple[str, str]] = []
    issues: List[str] = []

    for src_id in id_list:
        for dst_id in outgoing[src_id]:
            if src_id not in outgoing[dst_id]:
                unreciprocated.append((src_id, dst_id))
                src_title = node_ids[src_id].get("title", src_id)
                dst_title = node_ids[dst_id].get("title", dst_id)
                issues.append(
                    f"Unreciprocated cross-link: Node '{src_title}' ({src_id}) links to "
                    f"Node '{dst_title}' ({dst_id}), but '{dst_title}' does not link back to '{src_title}'"
                )

    return {
        "is_reciprocal": len(unreciprocated) == 0,
        "unreciprocated_pairs": unreciprocated,
        "issues": issues,
    }


def assert_calculation_variant_cross_links(
    html_or_text: str,
    min_variants: int = 2,
    require_reciprocal: bool = True,
    context: str = "",
) -> bool:
    """
    Mechanical contract validating calculation variants and reciprocal cross-links.
    Ensures:
    1. Zero forbidden em-dashes and en-dashes.
    2. At least min_variants calculation variant containers/nodes exist.
    3. Each variant node contains actual calculation logic/thresholds (rejects shallow placeholders).
    4. Zero orphaned calculation nodes without cross-links.
    5. Reciprocal bidirectional cross-links between related calculation nodes when require_reciprocal=True.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if not isinstance(html_or_text, str):
        raise ValueError(f"Content must be a string{ctx}")

    assert_no_forbidden_dashes(html_or_text, context=f"document{ctx}")

    nodes = extract_calculation_variant_nodes(html_or_text)

    if len(nodes) < min_variants:
        raise ValueError(
            f"Calculation variant deficit{ctx}: found {len(nodes)} calculation variants, "
            f"strictly requires >= {min_variants} calculation variant nodes"
        )

    # Check each variant has actual calculation
    missing_calc = [n for n in nodes if not n.get("has_calculation")]
    if missing_calc:
        titles = ", ".join(f"'{n.get('title', n['id'])}'" for n in missing_calc)
        raise ValueError(
            f"Shallow calculation variant detected{ctx}: variant(s) {titles} lack actual calculation logic, "
            f"formula, interactive inputs, or data tables"
        )

    # Check orphaned nodes
    orphaned = detect_orphaned_calculation_nodes(nodes)
    if orphaned:
        details = "; ".join(f"Node '{o.get('title', o['id'])}': {o['reason']}" for o in orphaned)
        raise ValueError(
            f"Orphaned calculation node(s) detected{ctx}: {details}"
        )

    # Check reciprocity
    if require_reciprocal:
        rec_res = verify_calculation_variant_reciprocity(nodes)
        if not rec_res["is_reciprocal"]:
            raise ValueError(
                f"Calculation variant cross-link reciprocity failure{ctx}: {'; '.join(rec_res['issues'])}"
            )

    return True


def assert_no_thin_fan_out_cannibalization(
    html_or_text: str,
    min_words: int = 150,
    context: str = "",
) -> bool:
    """
    Mechanical contract validating against thin disconnected fan-out pages.
    Guards against splintering traffic into low-depth pages that cause keyword cannibalization
    and scaled content demotions.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if not isinstance(html_or_text, str):
        raise ValueError(f"Content must be a string{ctx}")

    assert_no_forbidden_dashes(html_or_text, context=f"document{ctx}")

    clean_text = re.sub(r'<[^>]+>', ' ', html_or_text)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    words = clean_text.split()

    if len(words) < min_words:
        raise ValueError(
            f"Thin fan-out page detected{ctx}: document contains {len(words)} words, "
            f"strictly requires >= {min_words} words to avoid keyword cannibalization and scaled content penalties"
        )

    return True


def assert_organic_fan_out_coverage(
    html_or_text: str,
    min_subqueries: int = 2,
    min_variants: int = 2,
    require_reciprocal: bool = True,
    min_words_per_answer: int = 15,
    min_total_words: int = 150,
    context: str = "",
) -> bool:
    """
    Mechanical master contract enforcing Factor 5: Organic Fan-Out Coverage Rankings (+1.91).
    Verifies:
    1. Zero em-dashes and zero en-dashes.
    2. Substantive content depth preventing thin page cannibalization (assert_no_thin_fan_out_cannibalization).
    3. Clustered subqueries covering related sub-questions and secondary intent (assert_subquery_clustering).
    4. Rejection of shallow question lists that lack substantive answers.
    5. Calculation variant containers present with actual calculation logic.
    6. Reciprocal bidirectional cross-links across calculation variant nodes without orphaned nodes.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if not isinstance(html_or_text, str):
        raise ValueError(f"Content must be a string{ctx}")

    assert_no_forbidden_dashes(html_or_text, context=f"document{ctx}")

    assert_no_thin_fan_out_cannibalization(html_or_text, min_words=min_total_words, context=context)

    assert_subquery_clustering(
        html_or_text,
        min_subqueries=min_subqueries,
        min_words_per_answer=min_words_per_answer,
        context=context,
    )

    assert_calculation_variant_cross_links(
        html_or_text,
        min_variants=min_variants,
        require_reciprocal=require_reciprocal,
        context=context,
    )

    return True


assert_fan_out_coverage = assert_organic_fan_out_coverage
assert_organic_fan_out = assert_organic_fan_out_coverage


# =============================================================================
# Factor 6: Organic Search Ranking (+1.89) Contracts & Core SEO Hygiene
# =============================================================================

ORGANIC_SEARCH_TITLE_MIN_CHARS: int = 30
ORGANIC_SEARCH_TITLE_MAX_CHARS: int = 65
ORGANIC_SEARCH_META_DESC_MIN_CHARS: int = 70
ORGANIC_SEARCH_META_DESC_MAX_CHARS: int = 160
ORGANIC_SEARCH_MAX_SSR_LATENCY_MS: float = 100.0


def assert_organic_search_title(
    html_or_title: str,
    min_chars: int = ORGANIC_SEARCH_TITLE_MIN_CHARS,
    max_chars: int = ORGANIC_SEARCH_TITLE_MAX_CHARS,
    context: str = "",
) -> bool:
    """
    Mechanical contract validating title tag bounds for Factor 6: Organic Search Ranking (+1.89).
    Enforces:
    1. Zero em-dashes and zero en-dashes.
    2. Non-empty title tag.
    3. Zero delimiter corruption ('| |').
    4. Title length strictly between min_chars (30) and max_chars (65) inclusive.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if not isinstance(html_or_title, str):
        raise ValueError(f"Title content must be a string{ctx}")

    assert_no_forbidden_dashes(html_or_title, context=f"title{ctx}")

    title_text = html_or_title
    is_html_title = "<html" in html_or_title.lower() or "<head" in html_or_title.lower() or "<title" in html_or_title.lower()
    if is_html_title:
        m = re.search(r'<title\b[^>]*>(.*?)</title>', html_or_title, re.IGNORECASE | re.DOTALL)
        if not m:
            raise ValueError(f"Missing <title> tag{ctx}")
        title_text = m.group(1)

    clean_title = html.unescape(title_text).strip()
    if not clean_title:
        raise ValueError(f"Empty <title> tag detected{ctx}")

    if "| |" in clean_title:
        raise ValueError(f"Double pipe ('| |') formatting corruption in title{ctx}: '{clean_title}'")

    t_len = len(clean_title)
    if t_len < min_chars:
        raise ValueError(
            f"Title length ({t_len} chars) under {min_chars}-char threshold{ctx}: '{clean_title}'"
        )
    if t_len > max_chars:
        raise ValueError(
            f"Title length ({t_len} chars) exceeds {max_chars}-char threshold{ctx}: '{clean_title}'"
        )

    return True


def assert_single_h1_hierarchy(
    html_content: str,
    context: str = "",
) -> bool:
    """
    Mechanical contract validating single H1 presence and hierarchy for Factor 6: Organic Search Ranking (+1.89).
    Enforces:
    1. Zero em-dashes and zero en-dashes.
    2. Exactly one <h1> tag in document.
    3. H1 content is not empty or whitespace-only.
    4. Rejection of empty heading containers.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if not isinstance(html_content, str):
        raise ValueError(f"Content must be an HTML string{ctx}")

    assert_no_forbidden_dashes(html_content, context=f"document{ctx}")

    h1_matches = re.findall(r'<h1\b[^>]*>(.*?)</h1>', html_content, re.IGNORECASE | re.DOTALL)
    if len(h1_matches) == 0:
        raise ValueError(f"Missing <h1> tag{ctx}")
    if len(h1_matches) > 1:
        raise ValueError(f"Multiple <h1> tags ({len(h1_matches)}) detected{ctx}")

    raw_h1 = h1_matches[0]
    clean_h1 = re.sub(r'<[^>]+>', '', raw_h1).strip()
    if not clean_h1:
        raise ValueError(f"Empty <h1> tag detected{ctx}")

    empty_headings = re.findall(r'<h([2-6])\b[^>]*>\s*</h\1>', html_content, re.IGNORECASE)
    if empty_headings:
        raise ValueError(f"Empty heading container detected (<h{empty_headings[0]}>){ctx}")

    return True


def assert_organic_search_meta_description(
    html_or_desc: str,
    min_chars: int = ORGANIC_SEARCH_META_DESC_MIN_CHARS,
    max_chars: int = ORGANIC_SEARCH_META_DESC_MAX_CHARS,
    context: str = "",
) -> bool:
    """
    Mechanical contract validating meta description limits for Factor 6: Organic Search Ranking (+1.89).
    Enforces:
    1. Zero em-dashes and zero en-dashes.
    2. Meta description is present and non-empty.
    3. Meta description length strictly between min_chars (70) and max_chars (160) inclusive.
    4. Zero mid-number ellipsis truncation.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if not isinstance(html_or_desc, str):
        raise ValueError(f"Meta description content must be a string{ctx}")

    assert_no_forbidden_dashes(html_or_desc, context=f"meta description{ctx}")

    desc_text = html_or_desc
    is_html_desc = "<html" in html_or_desc.lower() or "<head" in html_or_desc.lower() or "<meta" in html_or_desc.lower()
    if is_html_desc:
        m = re.search(r'<meta\b[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', html_or_desc, re.IGNORECASE)
        if not m:
            m = re.search(r'<meta\b[^>]*content=["\']([^"\']*)["\'][^>]*name=["\']description["\']', html_or_desc, re.IGNORECASE)
        if not m:
            raise ValueError(f"Missing meta description tag{ctx}")
        desc_text = m.group(1)

    clean_desc = html.unescape(desc_text).strip()
    if not clean_desc:
        raise ValueError(f"Empty meta description detected{ctx}")

    d_len = len(clean_desc)
    if d_len < min_chars:
        raise ValueError(
            f"Meta description length ({d_len} chars) under {min_chars}-char threshold{ctx}: '{clean_desc}'"
        )
    if d_len > max_chars:
        raise ValueError(
            f"Meta description length ({d_len} chars) exceeds {max_chars}-char threshold{ctx}: '{clean_desc}'"
        )

    if (
        re.search(r'\$\d+(?:,\d+)*(?:,\.\.\.|\.\.\.)', clean_desc)
        or re.search(r'\d+,\.\.\.', clean_desc)
        or re.search(r'\d+\.\.\.', clean_desc)
        or re.search(r'\d+…', clean_desc)
    ):
        raise ValueError(f"Mid-number ellipsis truncation in meta description{ctx}: '{clean_desc}'")

    return True


def assert_canonical_consistency(
    html_or_canonical: str,
    expected_route_or_url: Optional[str] = None,
    base_domain: Optional[str] = None,
    context: str = "",
) -> bool:
    """
    Mechanical contract validating canonical consistency for Factor 6: Organic Search Ranking (+1.89).
    Enforces:
    1. Zero em-dashes and zero en-dashes.
    2. Canonical link tag present with absolute HTTPS scheme.
    3. Normalized canonical URL:
       - No double slashes in path
       - No query parameters
       - No hash fragment
       - No relative path traversal
       - No uppercase path segments
    4. Canonical consistency without drift against expected route or base domain.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if not isinstance(html_or_canonical, str):
        raise ValueError(f"Canonical content must be a string{ctx}")

    assert_no_forbidden_dashes(html_or_canonical, context=f"canonical URL{ctx}")

    c_url = html_or_canonical.strip()
    is_html_canon = "<html" in html_or_canonical.lower() or "<head" in html_or_canonical.lower() or "<link" in html_or_canonical.lower()
    if is_html_canon:
        m = re.search(r'<link\b[^>]*\brel=["\']canonical["\'][^>]*\bhref=["\']([^"\']+)["\']', html_or_canonical, re.IGNORECASE)
        if not m:
            m = re.search(r'<link\b[^>]*\bhref=["\']([^"\']+)["\'][^>]*\brel=["\']canonical["\']', html_or_canonical, re.IGNORECASE)
        if not m:
            raise ValueError(f"Missing canonical link tag{ctx}")
        c_url = m.group(1).strip()

    if not c_url:
        raise ValueError(f"Empty canonical URL detected{ctx}")

    if not c_url.startswith("https://"):
        raise ValueError(f"Canonical URL '{c_url}' is not an absolute HTTPS URL{ctx}")

    parsed = urllib.parse.urlsplit(c_url)

    # Check unnormalized canonical URL
    if "//" in parsed.path:
        raise ValueError(f"Unnormalized canonical URL '{c_url}' contains duplicate slashes in path{ctx}")
    if parsed.query:
        raise ValueError(f"Unnormalized canonical URL '{c_url}' contains query parameters '{parsed.query}'{ctx}")
    if parsed.fragment:
        raise ValueError(f"Unnormalized canonical URL '{c_url}' contains hash fragment '{parsed.fragment}'{ctx}")
    if "/../" in parsed.path or parsed.path.endswith("/..") or "/./" in parsed.path:
        raise ValueError(f"Unnormalized canonical URL '{c_url}' contains relative path traversal segments{ctx}")
    if any(c.isupper() for c in parsed.path):
        raise ValueError(f"Unnormalized canonical URL '{c_url}' contains uppercase characters{ctx}")

    # Check canonical domain consistency
    if base_domain:
        clean_expected_domain = base_domain.strip().lower().split(":")[0].lstrip(".")
        if clean_expected_domain.startswith("www."):
            clean_expected_domain = clean_expected_domain[4:]
        url_host = parsed.netloc.lower().split(":")[0]
        if url_host.startswith("www."):
            url_host = url_host[4:]
        if url_host != clean_expected_domain and not url_host.endswith("." + clean_expected_domain):
            raise ValueError(
                f"Canonical host '{url_host}' drifts from expected domain '{base_domain}'{ctx}"
            )

    # Check canonical route consistency
    if expected_route_or_url:
        exp_clean = expected_route_or_url.strip()
        if exp_clean.startswith("http://") or exp_clean.startswith("https://"):
            exp_parsed = urllib.parse.urlsplit(exp_clean)
            exp_path = exp_parsed.path
        else:
            exp_path = exp_clean

        norm_exp_path = exp_path if exp_path.startswith("/") else f"/{exp_path}"
        norm_c_path = parsed.path if parsed.path.startswith("/") else f"/{parsed.path}"

        norm_exp_variants = {
            norm_exp_path,
            norm_exp_path.rstrip("/") if norm_exp_path != "/" else "/",
            (norm_exp_path.rstrip("/") + "/") if not norm_exp_path.endswith("/") else norm_exp_path,
        }
        if norm_exp_path.endswith("/index.html"):
            base_p = norm_exp_path[:-10]
            norm_exp_variants.add(base_p)
            norm_exp_variants.add(base_p + "/")
        elif norm_exp_path.endswith("index.html"):
            norm_exp_variants.add("/")

        if norm_c_path not in norm_exp_variants:
            raise ValueError(
                f"Canonical path drift{ctx}: canonical target '{parsed.path}' does not match expected route '{expected_route_or_url}'"
            )

    return True


def assert_internal_links_integrity(
    html_content: str,
    known_routes: Optional[Set[str]] = None,
    current_route: str = "/",
    base_domain: Optional[str] = None,
    context: str = "",
) -> bool:
    """
    Mechanical contract validating zero broken internal links for Factor 6: Organic Search Ranking (+1.89).
    Enforces:
    1. Zero em-dashes and zero en-dashes.
    2. Rejection of empty href attributes.
    3. Rejection of dead link routes (e.g. javascript:void(0)).
    4. Internal anchor links (#id) resolve to valid target elements in document.
    5. Internal route links resolve to known static routes across deeply nested link graphs.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if not isinstance(html_content, str):
        raise ValueError(f"Content must be an HTML string{ctx}")

    assert_no_forbidden_dashes(html_content, context=f"document{ctx}")

    elem_ids = set(re.findall(r'\bid=["\']([^"\']+)["\']', html_content, re.IGNORECASE))
    elem_names = set(re.findall(r'\bname=["\']([^"\']+)["\']', html_content, re.IGNORECASE))
    valid_anchors = elem_ids | elem_names

    links = re.findall(r'<a\b[^>]*\bhref=["\']([^"\']*)["\']', html_content, re.IGNORECASE)

    clean_curr = current_route if current_route.startswith("/") else f"/{current_route}"
    curr_dir = clean_curr if clean_curr.endswith("/") else posixpath.dirname(clean_curr) + "/"

    for raw_href in links:
        href = raw_href.strip()
        if href == "":
            raise ValueError(f"Empty href attribute detected in internal link{ctx}")

        href_lower = href.lower()
        if href_lower.startswith("javascript:"):
            raise ValueError(f"Dead link route '{href}' detected in internal anchor{ctx}")

        if href.startswith("#"):
            target_id = href[1:]
            if target_id and target_id not in valid_anchors:
                raise ValueError(
                    f"Broken internal anchor link '{href}' target does not exist on page{ctx}"
                )
            continue

        if href_lower.startswith(("mailto:", "tel:", "sms:", "data:")):
            continue

        is_internal = False
        link_target = href

        if href.startswith("http://") or href.startswith("https://"):
            u = urllib.parse.urlsplit(href)
            host = u.netloc.lower().split(":")[0]
            if host.startswith("www."):
                host = host[4:]
            if base_domain:
                bd = base_domain.lower().split(":")[0]
                if bd.startswith("www."):
                    bd = bd[4:]
                if host == bd or host.endswith("." + bd):
                    is_internal = True
                    link_target = u.path + (f"#{u.fragment}" if u.fragment else "")
            else:
                is_internal = False
        else:
            is_internal = True

        if is_internal and known_routes is not None:
            if "#" in link_target:
                path_part, fragment_part = link_target.split("#", 1)
            else:
                path_part, fragment_part = link_target, ""

            if path_part.startswith("/"):
                resolved = posixpath.normpath(path_part)
                if path_part.endswith("/") and not resolved.endswith("/"):
                    resolved += "/"
            elif path_part:
                resolved = posixpath.normpath(posixpath.join(curr_dir, path_part))
                if path_part.endswith("/") and not resolved.endswith("/"):
                    resolved += "/"
            else:
                resolved = clean_curr

            if not resolved.startswith("/"):
                resolved = f"/{resolved}"

            candidates = {
                resolved,
                resolved.rstrip("/") if resolved != "/" else "/",
                (resolved.rstrip("/") + "/") if not resolved.endswith("/") else resolved,
                posixpath.join(resolved.rstrip("/"), "index.html"),
            }
            if resolved.endswith(".html"):
                base_stem = resolved[:-5]
                candidates.add(base_stem)
                candidates.add(base_stem + "/")

            if not candidates.intersection(known_routes):
                raise ValueError(
                    f"Broken internal link to dead route '{href}' (resolved to '{resolved}'){ctx}"
                )

    return True


def assert_ssr_response_latency(
    latency_ms: float,
    max_latency_ms: float = ORGANIC_SEARCH_MAX_SSR_LATENCY_MS,
    context: str = "",
) -> bool:
    """
    Mechanical contract validating static SSR response benchmark for Factor 6: Organic Search Ranking (+1.89).
    Enforces sub-100ms response speed benchmarks (< 100.0ms).
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if not isinstance(latency_ms, (int, float)):
        raise ValueError(f"Latency must be a numeric value in milliseconds{ctx}")

    if latency_ms >= max_latency_ms:
        raise ValueError(
            f"Static SSR response latency regression ({latency_ms:.2f}ms exceeds {max_latency_ms:.2f}ms threshold){ctx}"
        )

    return True


def assert_organic_search_ranking(
    html_content: str,
    current_route: str = "/",
    known_routes: Optional[Set[str]] = None,
    expected_canonical: Optional[str] = None,
    base_domain: Optional[str] = None,
    ssr_latency_ms: Optional[float] = None,
    max_ssr_latency_ms: float = ORGANIC_SEARCH_MAX_SSR_LATENCY_MS,
    context: str = "",
) -> bool:
    """
    Mechanical master contract enforcing Factor 6: Organic Search Ranking (+1.89).
    Verifies core SEO hygiene across traditional organic search ranking standards:
    1. Zero em-dashes and zero en-dashes across HTML content.
    2. Title tag length strictly 30-65 characters without double pipes.
    3. Exactly one non-empty H1 tag without empty heading containers.
    4. Meta description length strictly 70-160 characters without truncation.
    5. Canonical consistency without drift or unnormalized URLs.
    6. Internal link graph integrity with zero broken links or dead routes.
    7. Sub-100ms static SSR response benchmark.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if not isinstance(html_content, str):
        raise ValueError(f"Content must be an HTML string{ctx}")

    assert_no_forbidden_dashes(html_content, context=f"document{ctx}")

    assert_organic_search_title(html_content, context=context)

    assert_single_h1_hierarchy(html_content, context=context)

    assert_organic_search_meta_description(html_content, context=context)

    assert_canonical_consistency(
        html_content,
        expected_route_or_url=expected_canonical or current_route,
        base_domain=base_domain,
        context=context,
    )

    assert_internal_links_integrity(
        html_content,
        known_routes=known_routes,
        current_route=current_route,
        base_domain=base_domain,
        context=context,
    )

    if ssr_latency_ms is not None:
        assert_ssr_response_latency(
            ssr_latency_ms,
            max_latency_ms=max_ssr_latency_ms,
            context=context,
        )

    return True


assert_traditional_organic_search_ranking = assert_organic_search_ranking
assert_core_seo_hygiene = assert_organic_search_ranking


# =============================================================================
# Factor 7: Unique / First-Party Information (+1.85) Contracts & Validators
# =============================================================================

ECONOMIC_DATASET_PATTERNS: List[str] = [
    r"\bBLS\b",
    r"\bBureau of Labor Statistics\b",
    r"\bCPI-U\b",
    r"\bCPI-W\b",
    r"\bECI\b",
    r"\bPPI\b",
    r"\bFRED\b",
    r"\bFederal Reserve Economic Data\b",
    r"\bFRED/[A-Za-z0-9_\.]+\b",
    r"\bFederal Reserve Bank of St\. Louis\b",
    r"\bBEA\b",
    r"\bBureau of Economic Analysis\b",
    r"\bFederal Reserve\b",
]

UNGROUNDED_SYNTHETIC_PATTERNS: List[str] = [
    r"\bmock dataset\b",
    r"\bmock data\b",
    r"\bsynthetic placeholder\b",
    r"\bungrounded synthetic\b",
    r"\bunverified synthetic\b",
    r"\bhypothetical numbers lacking statutory\b",
    r"\bplaceholder calculation values\b",
    r"\barbitrary estimates not grounded\b",
    r"\brandom estimates without verified formula\b",
]

SAFE_OPERATORS: Dict[Any, Callable] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

SAFE_FUNCTIONS: Dict[str, Callable] = {
    "min": min,
    "max": max,
    "round": round,
    "abs": abs,
    "sum": sum,
}


def safe_eval_mathematical_formula(formula: str, inputs: Dict[str, Any]) -> float:
    """
    Safely evaluates a deterministic arithmetic formula string using AST parsing.
    Prevents arbitrary code execution while enforcing mathematical integrity.
    Zero em-dashes. Zero en-dashes.
    """
    if not formula or not isinstance(formula, str):
        raise ValueError("Formula must be a non-empty string")

    clean_f = formula.strip()
    clean_f = re.sub(r'(\d+(?:\.\d+)?)\s*%', r'(\1 / 100.0)', clean_f)
    clean_f = clean_f.replace("$", "")
    # Strip thousands separators between digits (e.g. 500,000 -> 500000) while preserving argument commas
    clean_f = re.sub(r'(?<=\d),(?=\d)', '', clean_f)

    norm_inputs: Dict[str, float] = {}
    for k, v in inputs.items():
        k_clean = str(k).strip().lower().replace(" ", "_").replace("-", "_")
        if isinstance(v, (int, float)):
            norm_inputs[k_clean] = float(v)
        elif isinstance(v, str):
            v_clean = v.replace("$", "").replace(",", "").replace("%", "").strip()
            try:
                norm_inputs[k_clean] = float(v_clean)
            except ValueError:
                pass

    try:
        parsed_ast = ast.parse(clean_f, mode="eval")
    except Exception as ex:
        raise ValueError(f"Formula '{formula}' failed AST parse: {ex}")

    def _eval_node(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval_node(node.body)
        elif isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise ValueError(f"Unsupported constant type in formula: {type(node.value).__name__}")
        elif isinstance(node, ast.Name):
            name_lower = node.id.lower()
            if name_lower in norm_inputs:
                return norm_inputs[name_lower]
            raise ValueError(f"Proprietary model formula references unknown variable '{node.id}' not found in inputs")
        elif isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in SAFE_OPERATORS:
                raise ValueError(f"Unsupported binary operator in formula: {op_type.__name__}")
            left_val = _eval_node(node.left)
            right_val = _eval_node(node.right)
            if op_type in (ast.Div, ast.FloorDiv, ast.Mod) and right_val == 0:
                raise ZeroDivisionError(f"Division by zero in formula '{formula}'")
            return float(SAFE_OPERATORS[op_type](left_val, right_val))
        elif isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in SAFE_OPERATORS:
                raise ValueError(f"Unsupported unary operator in formula: {op_type.__name__}")
            operand_val = _eval_node(node.operand)
            return float(SAFE_OPERATORS[op_type](operand_val))
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in SAFE_FUNCTIONS:
                func = SAFE_FUNCTIONS[node.func.id]
                args = [_eval_node(arg) for arg in node.args]
                if node.func.id == "round" and len(args) == 2:
                    return float(round(args[0], int(args[1])))
                return float(func(*args))
            raise ValueError(f"Unsupported function call in formula: {ast.dump(node.func)}")
        else:
            raise ValueError(f"Unsupported expression element in formula: {ast.dump(node)}")

    return _eval_node(parsed_ast)


def detect_ungrounded_synthetic_claims(text: str) -> List[str]:
    """
    Detects ungrounded synthetic claims, mock datasets lacking verified formulas,
    or placeholder values disguised as first-party analytical data.
    Zero em-dashes. Zero en-dashes.
    """
    if not text or not isinstance(text, str):
        return []
    issues: List[str] = []
    text_lower = text.lower()
    for pat in UNGROUNDED_SYNTHETIC_PATTERNS:
        m = re.search(pat, text_lower)
        if m:
            issues.append(f"Ungrounded synthetic claim detected: '{m.group(0)}'")
    return issues


def detect_orphaned_calculation_tables(html_content: str) -> List[str]:
    """
    Scans HTML content for calculation tables lacking statutory or economic provenance.
    Calculation tables displaying rates, monetary amounts, or formulas must cite their
    authoritative source or empirical benchmark dataset.
    Zero em-dashes. Zero en-dashes.
    """
    if not html_content or not isinstance(html_content, str):
        return []
    orphans: List[str] = []

    table_pat = re.compile(r'<table\b([^>]*)>(.*?)</table>', re.IGNORECASE | re.DOTALL)
    statutory_kw = [
        "irc", "cfr", "usc", "u.s.c.", "internal revenue code", "statutory", "statute",
        "rev. proc.", "treas. reg.", "public law", "p.l.", "section 179", "section 168",
        "section 199a", "form 1099", "statutory authority", "bls", "fred", "bea"
    ]

    for idx, match in enumerate(table_pat.finditer(html_content)):
        attrs_str = match.group(1).lower()
        table_body = match.group(2)
        table_full = match.group(0).lower()

        has_calc_data = bool(
            re.search(r'\$[0-9]+', table_body)
            or re.search(r'[0-9]+(?:\.[0-9]+)?\s*%', table_body)
            or re.search(r'\b[0-9]{3,}\b', table_body)
            or re.search(r'(=|\+|\-|\*|/)\s*[0-9]+', table_body)
            or "calculation" in attrs_str
            or "calc-table" in attrs_str
            or "data-variant" in attrs_str
        )
        if not has_calc_data:
            continue

        has_attr_provenance = any(
            k in attrs_str
            for k in [
                "data-statutory", "data-provenance", "data-source", "data-economic",
                "data-authority", "data-statutory-source", "data-statutory-provenance",
            ]
        )

        has_body_provenance = any(kw in table_full for kw in statutory_kw)

        start_pos = max(0, match.start() - 300)
        end_pos = min(len(html_content), match.end() + 300)
        surrounding_text = html_content[start_pos:end_pos].lower()
        has_surrounding_provenance = any(kw in surrounding_text for kw in statutory_kw) and (
            "<figcaption" in surrounding_text or "provenance" in surrounding_text or "source:" in surrounding_text or "authority:" in surrounding_text
        )

        if not (has_attr_provenance or has_body_provenance or has_surrounding_provenance):
            orphans.append(f"Table {idx + 1}: Orphaned calculation table missing statutory or economic provenance")

    return orphans


def extract_calculation_manifests(html_content: str) -> List[Dict[str, Any]]:
    """
    Extracts calculation manifests embedded in HTML via JSON script blocks, JSON-LD,
    or HTML manifest containers.
    Zero em-dashes. Zero en-dashes.
    """
    if not html_content or not isinstance(html_content, str):
        return []
    manifests: List[Dict[str, Any]] = []

    # 1. JSON script blocks with id/class containing 'calculation-manifest' or 'manifest'
    script_pat = re.compile(
        r'<script\b([^>]*\btype=["\'](?:application/json|application/ld\+json)["\'][^>]*)>(.*?)</script>',
        re.IGNORECASE | re.DOTALL,
    )
    for m in script_pat.finditer(html_content):
        tag_attrs = m.group(1).lower()
        raw_text = m.group(2).strip()
        if not raw_text:
            continue
        try:
            data = json.loads(raw_text)
            if isinstance(data, dict):
                is_manifest = (
                    "calculation_manifest" in data
                    or "formula" in data
                    or data.get("@type") in ("CalculationManifest", "TaxCalculationModel", "FirstPartyCalculationManifest")
                    or "calculation-manifest" in tag_attrs
                    or "manifest" in tag_attrs
                )
                if is_manifest:
                    m_item = data.get("calculation_manifest") if "calculation_manifest" in data else data
                    manifests.append(m_item)
                elif "@graph" in data and isinstance(data["@graph"], list):
                    for gitm in data["@graph"]:
                        if isinstance(gitm, dict) and (
                            "formula" in gitm
                            or gitm.get("@type") in ("CalculationManifest", "TaxCalculationModel", "FirstPartyCalculationManifest")
                        ):
                            manifests.append(gitm)
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and ("formula" in item or "calculation_manifest" in item):
                        manifests.append(item.get("calculation_manifest") or item)
        except Exception:
            pass

    # 2. HTML elements with calculation manifest data attributes or class
    elem_pat = re.compile(
        r'<([a-zA-Z0-9]+)\b([^>]*\bclass=["\'][^"\']*\bcalculation-manifest\b[^"\']*["\'][^>]*)>',
        re.IGNORECASE,
    )
    for m in elem_pat.finditer(html_content):
        tag_header = m.group(2)
        attrs: Dict[str, str] = {}
        for attr_m in re.finditer(r'([a-zA-Z0-9_-]+)=["\']([^"\']*)["\']', tag_header):
            attrs[attr_m.group(1).lower()] = attr_m.group(2)
        if "data-formula" in attrs or "data-manifest-id" in attrs:
            manifest_dict: Dict[str, Any] = {
                "manifest_id": attrs.get("data-manifest-id") or attrs.get("id", "manifest-1"),
                "formula": attrs.get("data-formula", ""),
                "model_name": attrs.get("data-model") or attrs.get("data-model-name", "Proprietary Model"),
                "statutory_authority": attrs.get("data-statutory-source") or attrs.get("data-statutory-provenance", ""),
                "economic_dataset": attrs.get("data-economic-source") or attrs.get("data-economic-dataset", ""),
                "inputs": {},
            }
            if "data-inputs" in attrs:
                try:
                    manifest_dict["inputs"] = json.loads(attrs["data-inputs"])
                except Exception:
                    for pair in attrs["data-inputs"].split(","):
                        if "=" in pair:
                            k, v = pair.split("=", 1)
                            manifest_dict["inputs"][k.strip()] = v.strip()
            if "data-output" in attrs:
                manifest_dict["published_output"] = attrs["data-output"]
            if "data-sample" in attrs:
                manifest_dict["sample_calculation"] = attrs["data-sample"]
            manifests.append(manifest_dict)

    return manifests


def extract_multi_dataset_joins(html_content: str) -> List[Dict[str, Any]]:
    """
    Extracts multi-dataset joins linking statutory figures with economic datasets.
    Zero em-dashes. Zero en-dashes.
    """
    if not html_content or not isinstance(html_content, str):
        return []
    joins: List[Dict[str, Any]] = []

    elem_pat = re.compile(
        r'<([a-zA-Z0-9]+)\b([^>]*\b(?:multi-dataset-join|dataset-join)\b[^>]*)>(.*?)</\1>',
        re.IGNORECASE | re.DOTALL,
    )
    for m in elem_pat.finditer(html_content):
        tag_str = m.group(2)
        inner = m.group(3)
        stat_m = re.search(r'data-statutory-(?:source|provenance)=["\']([^"\']*)["\']', tag_str, re.IGNORECASE)
        econ_m = re.search(r'data-economic-(?:source|dataset)=["\']([^"\']*)["\']', tag_str, re.IGNORECASE)
        joins.append({
            "statutory_source": stat_m.group(1) if stat_m else "",
            "economic_source": econ_m.group(1) if econ_m else "",
            "text": re.sub(r'<[^>]+>', ' ', inner).strip(),
        })

    return joins


def assert_proprietary_model_integrity(
    manifest_or_inputs: Any,
    published_output: Any = None,
    formula: str = "",
    tolerance: float = 0.01,
    context: str = "",
) -> bool:
    """
    Mechanical contract asserting proprietary model inputs match published outputs.
    Evaluates inputs through the formula and verifies mathematical equivalence.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""

    if isinstance(manifest_or_inputs, dict) and published_output is None and not formula:
        m = manifest_or_inputs
        formula = str(m.get("formula", "")).strip()
        inputs = m.get("inputs", {})
        published_output = (
            m.get("published_output")
            or m.get("expected_output")
            or m.get("output")
            or m.get("result")
        )
    elif isinstance(manifest_or_inputs, dict):
        inputs = manifest_or_inputs
    else:
        raise ValueError(f"Inputs must be a dictionary, got {type(manifest_or_inputs).__name__}{ctx}")

    if not formula:
        raise ValueError(f"Formula string required for proprietary model integrity check{ctx}")
    if published_output is None:
        raise ValueError(f"Published output required for proprietary model integrity check{ctx}")

    clean_out_str = str(published_output).replace("$", "").replace(",", "").replace("%", "").strip()
    try:
        expected_num = float(clean_out_str)
    except ValueError:
        return True

    try:
        calculated_num = safe_eval_mathematical_formula(formula, inputs)
    except Exception as ex:
        raise ValueError(f"Proprietary model formula evaluation failed{ctx}: {ex}")

    diff = abs(calculated_num - expected_num)
    rel_diff = diff / max(abs(expected_num), 1.0)
    if diff > tolerance and rel_diff > 0.001:
        raise ValueError(
            f"Proprietary model input/output mismatch{ctx}: inputs {inputs} evaluated with "
            f"formula '{formula}' yield {calculated_num:.4f}, but published output is {expected_num:.4f} "
            f"(diff: {diff:.4f})"
        )

    return True


def assert_unique_calculation_manifest(manifest: Dict[str, Any], context: str = "") -> bool:
    """
    Mechanical contract validating a unique calculation manifest for Factor 7:
    1. Zero em-dashes and zero en-dashes across all manifest keys and values.
    2. Non-empty mathematical formula string.
    3. Non-empty inputs dictionary or list with concrete numeric values.
    4. Non-empty sample calculation or step-by-step verification.
    5. Primary statutory authority or provenance citation.
    6. Proprietary model name or identifier.
    7. Mathematical integrity check: inputs evaluated against formula match published output.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if not isinstance(manifest, dict):
        raise ValueError(f"Calculation manifest must be a dictionary, got {type(manifest).__name__}{ctx}")

    manifest_json = json.dumps(manifest, ensure_ascii=False)
    assert_no_forbidden_dashes(manifest_json, context=f"calculation manifest{ctx}")

    syn_issues = detect_ungrounded_synthetic_claims(manifest_json)
    if syn_issues:
        raise ValueError(f"Calculation manifest contains ungrounded synthetic claims{ctx}: {syn_issues[0]}")

    formula = manifest.get("formula")
    if not formula or not isinstance(formula, str) or not formula.strip():
        raise ValueError(f"Calculation manifest missing or empty 'formula'{ctx}")

    inputs = manifest.get("inputs")
    if inputs is None or not isinstance(inputs, (dict, list)) or len(inputs) == 0:
        raise ValueError(f"Calculation manifest missing or empty 'inputs'{ctx}")

    sample = manifest.get("sample_calculation") or manifest.get("sample")
    if sample is None or (isinstance(sample, (str, list, dict)) and len(sample) == 0):
        raise ValueError(f"Calculation manifest missing or empty 'sample_calculation'{ctx}")

    authority = (
        manifest.get("statutory_authority")
        or manifest.get("statutory_provenance")
        or manifest.get("authority")
    )
    if not authority or (isinstance(authority, str) and not authority.strip()):
        raise ValueError(f"Calculation manifest missing or empty 'statutory_authority'{ctx}")

    model_name = (
        manifest.get("model_name")
        or manifest.get("proprietary_model")
        or manifest.get("model")
    )
    if not model_name or (isinstance(model_name, str) and not model_name.strip()):
        raise ValueError(f"Calculation manifest missing or empty 'model_name'{ctx}")

    published_output = (
        manifest.get("published_output")
        or manifest.get("expected_output")
        or manifest.get("output")
        or manifest.get("result")
    )
    if published_output is not None and isinstance(inputs, dict):
        assert_proprietary_model_integrity(
            manifest_or_inputs=inputs,
            published_output=published_output,
            formula=formula,
            context=f"manifest {manifest.get('manifest_id', 'unknown')}{ctx}",
        )

    return True


def assert_multi_dataset_enrichment(content_or_dict: Any, context: str = "") -> bool:
    """
    Mechanical contract validating multi-dataset enrichment for Factor 7.
    Enforces the simultaneous presence of:
    1. Primary statutory provenance (IRC, CFR, USC, P.L., IRS guidance)
    2. Empirical economic dataset provenance (BLS, FRED, BEA, Federal Reserve)
    Rejects mock datasets and ungrounded synthetic claims.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if isinstance(content_or_dict, dict):
        text_repr = json.dumps(content_or_dict, ensure_ascii=False)
    elif isinstance(content_or_dict, str):
        text_repr = content_or_dict
    else:
        raise ValueError(f"Content must be a string or dictionary, got {type(content_or_dict).__name__}{ctx}")

    assert_no_forbidden_dashes(text_repr, context=f"multi-dataset content{ctx}")

    synthetic_issues = detect_ungrounded_synthetic_claims(text_repr)
    if synthetic_issues:
        raise ValueError(f"Ungrounded synthetic claim detected{ctx}: {synthetic_issues[0]}")

    has_statutory = False
    statutory_patterns = [
        r"\b(?:26\s+U\.?S\.?C\.?|Title\s+26)\b",
        r"\b(?:26\s+C\.?F\.?R\.?|Treas\.?\s+Reg\.?)\b",
        r"\bIRC\s+(?:Section\s+|§\s*)?\d+[a-zA-Z0-9_\(\)]*",
        r"\bInternal\s+Revenue\s+Code\b",
        r"\bIRS\s+(?:Form|Pub|Notice|Rev\.?\s*Proc\.?|Rev\.?\s*Rul\.?)\b",
        r"\bP\.?L\.?\s+\d+-\d+\b",
        r"\bstatutory\s+(?:rate|threshold|cap|limit|provision|schedule|phaseout|guideline|deduction|authority|provenance)\b",
    ]
    for sp in statutory_patterns:
        if re.search(sp, text_repr, re.IGNORECASE):
            has_statutory = True
            break

    has_economic = False
    for ep in ECONOMIC_DATASET_PATTERNS:
        if re.search(ep, text_repr, re.IGNORECASE):
            has_economic = True
            break

    if not has_statutory and not has_economic:
        raise ValueError(
            f"Multi-dataset enrichment deficit{ctx}: strictly requires multi-dataset enrichment "
            f"joining primary statutory figures with economic BLS and FRED data"
        )
    if has_statutory and not has_economic:
        raise ValueError(
            f"Multi-dataset enrichment deficit{ctx}: contains primary statutory figures "
            f"but missing empirical economic dataset series (BLS, FRED, or BEA)"
        )
    if has_economic and not has_statutory:
        raise ValueError(
            f"Multi-dataset enrichment deficit{ctx}: contains empirical economic dataset series "
            f"but missing primary statutory provenance (IRC, USC, or CFR)"
        )

    return True


def assert_no_orphaned_calculation_tables(html_content: str, context: str = "") -> bool:
    """
    Mechanical contract validating that all calculation tables have statutory or economic provenance.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    orphans = detect_orphaned_calculation_tables(html_content)
    if orphans:
        raise ValueError(
            f"Orphaned calculation tables missing statutory provenance{ctx}: {'; '.join(orphans)}"
        )
    return True


def assert_no_thin_syndicated_content(
    html_content: str,
    min_words: int = 150,
    context: str = "",
) -> bool:
    """
    Mechanical contract rejecting thin syndicated pages lacking firsthand calculations.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if not isinstance(html_content, str):
        raise ValueError(f"Content must be an HTML string{ctx}")

    text_only = re.sub(r'<[^>]+>', ' ', html_content)
    words = text_only.split()
    if len(words) < min_words:
        raise ValueError(
            f"Thin syndicated page detected{ctx}: word count ({len(words)}) below minimum {min_words} words"
        )

    syndicated_boilerplate = [
        "this syndicated article was originally published on",
        "syndicated content feed",
        "generic placeholder template",
    ]
    lower_text = text_only.lower()
    for bp in syndicated_boilerplate:
        if bp in lower_text:
            raise ValueError(f"Thin syndicated boilerplate detected{ctx}: '{bp}'")

    return True


def assert_unique_first_party_information(
    html_or_spec: Any,
    manifests_dir: Optional[Any] = None,
    context: str = "",
) -> bool:
    """
    Master mechanical contract enforcing Factor 7: Unique / First-Party Information (+1.85).
    Verifies:
    1. Zero em-dashes and zero en-dashes across all text.
    2. Zero ungrounded synthetic claims or mock datasets lacking verified formulas.
    3. No thin syndicated templates lacking firsthand calculations.
    4. Unique calculation manifest present, valid, with formula matching published output.
    5. Multi-dataset enrichment joining statutory figures with economic BLS and FRED data.
    6. Zero orphaned calculation tables missing statutory provenance.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""

    if isinstance(html_or_spec, dict):
        assert_unique_calculation_manifest(html_or_spec, context=context)
        assert_multi_dataset_enrichment(html_or_spec, context=context)
        return True

    if not isinstance(html_or_spec, str):
        raise ValueError(f"Expected HTML string or dictionary spec, got {type(html_or_spec).__name__}{ctx}")

    html_content = html_or_spec
    assert_no_forbidden_dashes(html_content, context=f"document{ctx}")

    syn_issues = detect_ungrounded_synthetic_claims(html_content)
    if syn_issues:
        raise ValueError(f"Ungrounded synthetic claim detected{ctx}: {syn_issues[0]}")

    assert_no_thin_syndicated_content(html_content, context=context)
    assert_no_orphaned_calculation_tables(html_content, context=context)
    assert_multi_dataset_enrichment(html_content, context=context)

    manifests = extract_calculation_manifests(html_content)
    if not manifests and manifests_dir:
        from pathlib import Path
        m_path = Path(manifests_dir)
        if m_path.is_dir():
            for mf in m_path.glob("*.json"):
                try:
                    m_data = json.loads(mf.read_text(encoding="utf-8"))
                    manifests.append(m_data)
                except Exception:
                    pass

    if not manifests:
        has_calc_markup = (
            "<form" in html_content.lower()
            or "calculation-container" in html_content.lower()
            or "data-formula" in html_content.lower()
            or "class=\"calculator" in html_content.lower()
        )
        if not has_calc_markup:
            raise ValueError(
                f"Page missing firsthand calculation manifest or interactive calculation model{ctx}"
            )
    else:
        for m in manifests:
            assert_unique_calculation_manifest(m, context=context)

    return True


assert_first_party_information = assert_unique_first_party_information
assert_first_party_assets = assert_unique_first_party_information
assert_firsthand_calculations = assert_unique_first_party_information
assert_proprietary_models = assert_unique_first_party_information


# =============================================================================
# Factor 8: Cross-Web Consensus & Corroboration (+1.81) Contracts & Schedules
# =============================================================================

# Statutory Tax Brackets (IRS published Rev. Proc. schedules)
# 2024: Rev. Proc. 2023-34; 2025: Rev. Proc. 2024-40; 2026: Statutory Inflation; 2027: Post-TCJA Reversion
STATUTORY_TAX_BRACKETS: Dict[int, Dict[str, List[Dict[str, Any]]]] = {
    2024: {
        "single": [
            {"rate": 10.0, "min_income": 0.0, "max_income": 11600.0},
            {"rate": 12.0, "min_income": 11600.0, "max_income": 47150.0},
            {"rate": 22.0, "min_income": 47150.0, "max_income": 100525.0},
            {"rate": 24.0, "min_income": 100525.0, "max_income": 191950.0},
            {"rate": 32.0, "min_income": 191950.0, "max_income": 243725.0},
            {"rate": 35.0, "min_income": 243725.0, "max_income": 609350.0},
            {"rate": 37.0, "min_income": 609350.0, "max_income": None},
        ],
        "married_filing_jointly": [
            {"rate": 10.0, "min_income": 0.0, "max_income": 23200.0},
            {"rate": 12.0, "min_income": 23200.0, "max_income": 94300.0},
            {"rate": 22.0, "min_income": 94300.0, "max_income": 201050.0},
            {"rate": 24.0, "min_income": 201050.0, "max_income": 383900.0},
            {"rate": 32.0, "min_income": 383900.0, "max_income": 487450.0},
            {"rate": 35.0, "min_income": 487450.0, "max_income": 731200.0},
            {"rate": 37.0, "min_income": 731200.0, "max_income": None},
        ],
        "head_of_household": [
            {"rate": 10.0, "min_income": 0.0, "max_income": 16550.0},
            {"rate": 12.0, "min_income": 16550.0, "max_income": 63100.0},
            {"rate": 22.0, "min_income": 63100.0, "max_income": 100500.0},
            {"rate": 24.0, "min_income": 100500.0, "max_income": 191950.0},
            {"rate": 32.0, "min_income": 191950.0, "max_income": 243700.0},
            {"rate": 35.0, "min_income": 243700.0, "max_income": 609350.0},
            {"rate": 37.0, "min_income": 609350.0, "max_income": None},
        ],
        "married_filing_separately": [
            {"rate": 10.0, "min_income": 0.0, "max_income": 11600.0},
            {"rate": 12.0, "min_income": 11600.0, "max_income": 47150.0},
            {"rate": 22.0, "min_income": 47150.0, "max_income": 100525.0},
            {"rate": 24.0, "min_income": 100525.0, "max_income": 191950.0},
            {"rate": 32.0, "min_income": 191950.0, "max_income": 243725.0},
            {"rate": 35.0, "min_income": 243725.0, "max_income": 365600.0},
            {"rate": 37.0, "min_income": 365600.0, "max_income": None},
        ],
    },
    2025: {
        "single": [
            {"rate": 10.0, "min_income": 0.0, "max_income": 11925.0},
            {"rate": 12.0, "min_income": 11925.0, "max_income": 48475.0},
            {"rate": 22.0, "min_income": 48475.0, "max_income": 103350.0},
            {"rate": 24.0, "min_income": 103350.0, "max_income": 197300.0},
            {"rate": 32.0, "min_income": 197300.0, "max_income": 250525.0},
            {"rate": 35.0, "min_income": 250525.0, "max_income": 626350.0},
            {"rate": 37.0, "min_income": 626350.0, "max_income": None},
        ],
        "married_filing_jointly": [
            {"rate": 10.0, "min_income": 0.0, "max_income": 23850.0},
            {"rate": 12.0, "min_income": 23850.0, "max_income": 96950.0},
            {"rate": 22.0, "min_income": 96950.0, "max_income": 206700.0},
            {"rate": 24.0, "min_income": 206700.0, "max_income": 394600.0},
            {"rate": 32.0, "min_income": 394600.0, "max_income": 501050.0},
            {"rate": 35.0, "min_income": 501050.0, "max_income": 751600.0},
            {"rate": 37.0, "min_income": 751600.0, "max_income": None},
        ],
        "head_of_household": [
            {"rate": 10.0, "min_income": 0.0, "max_income": 17000.0},
            {"rate": 12.0, "min_income": 17000.0, "max_income": 64850.0},
            {"rate": 22.0, "min_income": 64850.0, "max_income": 103350.0},
            {"rate": 24.0, "min_income": 103350.0, "max_income": 197300.0},
            {"rate": 32.0, "min_income": 197300.0, "max_income": 250500.0},
            {"rate": 35.0, "min_income": 250500.0, "max_income": 626350.0},
            {"rate": 37.0, "min_income": 626350.0, "max_income": None},
        ],
        "married_filing_separately": [
            {"rate": 10.0, "min_income": 0.0, "max_income": 11925.0},
            {"rate": 12.0, "min_income": 11925.0, "max_income": 48475.0},
            {"rate": 22.0, "min_income": 48475.0, "max_income": 103350.0},
            {"rate": 24.0, "min_income": 103350.0, "max_income": 197300.0},
            {"rate": 32.0, "min_income": 197300.0, "max_income": 250525.0},
            {"rate": 35.0, "min_income": 250525.0, "max_income": 375800.0},
            {"rate": 37.0, "min_income": 375800.0, "max_income": None},
        ],
    },
    2026: {
        "single": [
            {"rate": 10.0, "min_income": 0.0, "max_income": 11925.0},
            {"rate": 12.0, "min_income": 11925.0, "max_income": 48475.0},
            {"rate": 22.0, "min_income": 48475.0, "max_income": 103350.0},
            {"rate": 24.0, "min_income": 103350.0, "max_income": 197300.0},
            {"rate": 32.0, "min_income": 197300.0, "max_income": 250525.0},
            {"rate": 35.0, "min_income": 250525.0, "max_income": 626350.0},
            {"rate": 37.0, "min_income": 626350.0, "max_income": None},
        ],
        "married_filing_jointly": [
            {"rate": 10.0, "min_income": 0.0, "max_income": 23850.0},
            {"rate": 12.0, "min_income": 23850.0, "max_income": 96950.0},
            {"rate": 22.0, "min_income": 96950.0, "max_income": 206700.0},
            {"rate": 24.0, "min_income": 206700.0, "max_income": 394600.0},
            {"rate": 32.0, "min_income": 394600.0, "max_income": 501050.0},
            {"rate": 35.0, "min_income": 501050.0, "max_income": 751600.0},
            {"rate": 37.0, "min_income": 751600.0, "max_income": None},
        ],
        "head_of_household": [
            {"rate": 10.0, "min_income": 0.0, "max_income": 17000.0},
            {"rate": 12.0, "min_income": 17000.0, "max_income": 64850.0},
            {"rate": 22.0, "min_income": 64850.0, "max_income": 103350.0},
            {"rate": 24.0, "min_income": 103350.0, "max_income": 197300.0},
            {"rate": 32.0, "min_income": 197300.0, "max_income": 250500.0},
            {"rate": 35.0, "min_income": 250500.0, "max_income": 626350.0},
            {"rate": 37.0, "min_income": 626350.0, "max_income": None},
        ],
        "married_filing_separately": [
            {"rate": 10.0, "min_income": 0.0, "max_income": 11925.0},
            {"rate": 12.0, "min_income": 11925.0, "max_income": 48475.0},
            {"rate": 22.0, "min_income": 48475.0, "max_income": 103350.0},
            {"rate": 24.0, "min_income": 103350.0, "max_income": 197300.0},
            {"rate": 32.0, "min_income": 197300.0, "max_income": 250525.0},
            {"rate": 35.0, "min_income": 250525.0, "max_income": 375800.0},
            {"rate": 37.0, "min_income": 375800.0, "max_income": None},
        ],
    },
    2027: {
        "single": [
            {"rate": 10.0, "min_income": 0.0, "max_income": 11925.0},
            {"rate": 15.0, "min_income": 11925.0, "max_income": 48475.0},
            {"rate": 25.0, "min_income": 48475.0, "max_income": 103350.0},
            {"rate": 28.0, "min_income": 103350.0, "max_income": 197300.0},
            {"rate": 33.0, "min_income": 197300.0, "max_income": 250525.0},
            {"rate": 35.0, "min_income": 250525.0, "max_income": 626350.0},
            {"rate": 39.6, "min_income": 626350.0, "max_income": None},
        ],
        "married_filing_jointly": [
            {"rate": 10.0, "min_income": 0.0, "max_income": 23850.0},
            {"rate": 15.0, "min_income": 23850.0, "max_income": 96950.0},
            {"rate": 25.0, "min_income": 96950.0, "max_income": 206700.0},
            {"rate": 28.0, "min_income": 206700.0, "max_income": 394600.0},
            {"rate": 33.0, "min_income": 394600.0, "max_income": 501050.0},
            {"rate": 35.0, "min_income": 501050.0, "max_income": 751600.0},
            {"rate": 39.6, "min_income": 751600.0, "max_income": None},
        ],
    },
}

# Standard deductions by tax year and filing status
STATUTORY_STANDARD_DEDUCTIONS: Dict[int, Dict[str, float]] = {
    2024: {
        "single": 14600.0,
        "married_filing_jointly": 29200.0,
        "mfj": 29200.0,
        "head_of_household": 21900.0,
        "hoh": 21900.0,
        "married_filing_separately": 14600.0,
        "mfs": 14600.0,
        "additional_65_or_blind_single": 1950.0,
        "additional_65_or_blind_married": 1550.0,
    },
    2025: {
        "single": 15000.0,
        "married_filing_jointly": 30000.0,
        "mfj": 30000.0,
        "head_of_household": 22500.0,
        "hoh": 22500.0,
        "married_filing_separately": 15000.0,
        "mfs": 15000.0,
        "additional_65_or_blind_single": 2000.0,
        "additional_65_or_blind_married": 1600.0,
    },
    2026: {
        "single": 15000.0,
        "single_projected": 15350.0,
        "married_filing_jointly": 30000.0,
        "mfj": 30000.0,
        "mfj_projected": 30700.0,
        "head_of_household": 22500.0,
        "hoh": 22500.0,
        "married_filing_separately": 15000.0,
        "mfs": 15000.0,
        "additional_65_or_blind_single": 2000.0,
        "additional_65_or_blind_married": 1600.0,
    },
    2027: {
        "single": 8600.0,
        "married_filing_jointly": 17200.0,
        "mfj": 17200.0,
        "head_of_household": 12900.0,
        "hoh": 12900.0,
        "married_filing_separately": 8600.0,
        "mfs": 8600.0,
    },
}

# Statutory limits and thresholds across key provisions
STATUTORY_LIMITS: Dict[str, Any] = {
    "section_179_max_deduction": {
        2024: 1220000.0,
        2025: 1250000.0,
        2026: 1250000.0,
        "2026_projected": 1290000.0,
    },
    "section_179_phaseout_threshold": {
        2024: 3050000.0,
        2025: 3130000.0,
        2026: 3130000.0,
        "2026_projected": 3220000.0,
    },
    "section_179_heavy_vehicle_suv": {
        2024: 30500.0,
        2025: 31300.0,
        2026: 31300.0,
        "2026_projected": 32300.0,
    },
    "section_1202_qsbs": {
        "asset_ceiling": 50000000.0,
        "exclusion_cap": 10000000.0,
        "holding_period_years": 5,
        "active_business_percent": 80.0,
    },
    "retirement_401k_elective_deferral": {
        2024: 23000.0,
        2025: 23500.0,
        2026: 23500.0,
        "2026_projected": 24000.0,
    },
    "retirement_401k_catchup": {
        2024: 7500.0,
        2025: 7500.0,
        2026: 7500.0,
        "super_catchup_60_63_2025": 11250.0,
    },
    "retirement_ira_contribution": {
        2024: 7000.0,
        2025: 7000.0,
        2026: 7000.0,
        "catchup": 1000.0,
    },
    "hsa_contribution_limit": {
        2024: {"individual": 4150.0, "family": 8300.0, "catchup": 1000.0},
        2025: {"individual": 4300.0, "family": 8550.0, "catchup": 1000.0},
        2026: {"individual": 4450.0, "family": 8900.0, "catchup": 1000.0},
    },
    "section_199a_qbi_threshold": {
        2024: {"single": 191950.0, "mfj": 383900.0},
        2025: {"single": 197300.0, "mfj": 394600.0},
        2026: {"single": 197300.0, "mfj": 394600.0},
    },
    "social_security_wage_base": {
        2024: 168600.0,
        2025: 176100.0,
        2026: 176100.0,
    },
    "gift_tax_annual_exclusion": {
        2024: 18000.0,
        2025: 19000.0,
        2026: 19000.0,
    },
}

VALID_FEDERAL_TAX_RATES: Set[float] = {
    10.0, 12.0, 15.0, 22.0, 24.0, 25.0, 28.0, 32.0, 33.0, 35.0, 37.0, 39.6
}

ALL_OFFICIAL_STANDARD_DEDUCTIONS: Set[float] = {
    14600.0, 29200.0, 21900.0, 15000.0, 30000.0, 22500.0,
    15350.0, 30700.0, 23050.0, 8600.0, 17200.0, 12900.0,
    1950.0, 1550.0, 2000.0, 1600.0, 2050.0, 1650.0,
}

SILENT_FALLBACK_DEFAULT_PATTERNS = [
    re.compile(r'\b(?:default\s+to|fallback(?:\s+to)?|assumes?\s+default|hardcoded\s+(?:rate|bracket|limit|deduction)|default\s+(?:tax\s+rate|bracket|limit|deduction))\b', re.IGNORECASE),
    re.compile(r'\b(?:silent(?:ly)?\s+fallback|unverified\s+(?:rate|bracket|limit|deduction))\b', re.IGNORECASE),
    re.compile(r'\b(?:fallback\s+standard\s+deduction|default\s+standard\s+deduction)\b', re.IGNORECASE),
]


def get_official_tax_brackets(tax_year: int = 2025, filing_status: str = "single") -> List[Dict[str, Any]]:
    """
    Retrieves official published statutory tax brackets for a given tax year and filing status.
    Zero em-dashes. Zero en-dashes.
    """
    status_key = filing_status.strip().lower().replace(" ", "_").replace("-", "_")
    if status_key in ("mfj", "joint", "married_joint"):
        status_key = "married_filing_jointly"
    elif status_key in ("hoh", "head"):
        status_key = "head_of_household"
    elif status_key in ("mfs", "separately"):
        status_key = "married_filing_separately"

    year_brackets = STATUTORY_TAX_BRACKETS.get(tax_year) or STATUTORY_TAX_BRACKETS.get(2025, {})
    return year_brackets.get(status_key) or year_brackets.get("single", [])


def get_official_standard_deduction(tax_year: int = 2025, filing_status: str = "single") -> float:
    """
    Retrieves official published standard deduction for a given tax year and filing status.
    Zero em-dashes. Zero en-dashes.
    """
    status_key = filing_status.strip().lower().replace(" ", "_").replace("-", "_")
    if status_key in ("mfj", "joint", "married_joint"):
        status_key = "married_filing_jointly"
    elif status_key in ("hoh", "head"):
        status_key = "head_of_household"
    elif status_key in ("mfs", "separately"):
        status_key = "married_filing_separately"

    year_deductions = STATUTORY_STANDARD_DEDUCTIONS.get(tax_year) or STATUTORY_STANDARD_DEDUCTIONS.get(2025, {})
    return float(year_deductions.get(status_key, 15000.0))


def get_official_statutory_limit(limit_key: str, tax_year: Optional[int] = None) -> Any:
    """
    Retrieves official statutory limits and thresholds across key provisions.
    Zero em-dashes. Zero en-dashes.
    """
    clean_key = limit_key.strip().lower().replace(" ", "_").replace("-", "_")
    val = STATUTORY_LIMITS.get(clean_key)
    if val is None:
        for k, v in STATUTORY_LIMITS.items():
            if clean_key in k or k in clean_key:
                val = v
                break
    if isinstance(val, dict) and tax_year is not None:
        return val.get(tax_year) or val.get(str(tax_year)) or val.get(2025)
    return val


def detect_uncorroborated_statutory_claims(content: str, rel_path: str = "index.html") -> List[str]:
    """
    Detects uncorroborated tax constants, invented statutory limits, orphaned deduction figures,
    and silent fallback defaults across document text and structured data.
    Zero em-dashes. Zero en-dashes.
    """
    issues: List[str] = []
    if not content or not isinstance(content, str):
        return issues

    # 1. Strict anti-slop check
    if "\u2014" in content:
        issues.append(f"Page {rel_path}: Document contains forbidden em-dash")
    if "\u2013" in content:
        issues.append(f"Page {rel_path}: Document contains forbidden en-dash")

    # 2. Silent fallback defaults check
    for pat in SILENT_FALLBACK_DEFAULT_PATTERNS:
        for m in pat.finditer(content):
            issues.append(
                f"Page {rel_path}: Silent fallback default detected ('{m.group(0).strip()}'): "
                f"statutory constants must be explicitly reconciled against official published schedules"
            )

    # 3. Invented federal tax rates check
    for m in re.finditer(r'\b([0-9]{1,2}(?:\.[0-9]+)?)\s*%\s*(?:federal\s+)?(?:marginal\s+tax\s+rate|marginal\s+rate|tax\s+bracket|bracket)\b', content, re.IGNORECASE):
        try:
            rate = float(m.group(1))
            surrounding = content[max(0, m.start()-40):min(len(content), m.end()+40)].lower()
            if "state" not in surrounding and ("ordinary" in surrounding or "bracket" in surrounding or "irs" in surrounding):
                if rate not in VALID_FEDERAL_TAX_RATES and rate not in {0.0, 15.0, 20.0}:
                    issues.append(
                        f"Page {rel_path}: Invented federal tax rate '{rate}%' is not an official IRS statutory marginal bracket"
                    )
        except Exception:
            pass

    # 4. Standard deduction checks
    std_ded_matches = re.finditer(
        r'(?:standard\s+deduction(?:\s+(?:is|of|for|amount|value|drops?\s+to))?|deduction\s+of)\s*[:=]?\s*\$([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,6})',
        content,
        re.IGNORECASE
    )
    for m in std_ded_matches:
        raw_val = m.group(1).replace(",", "")
        try:
            val = float(raw_val)
            surrounding = content[max(0, m.start()-60):min(len(content), m.end()+60)].lower()
            if "standard deduction" in surrounding:
                if val not in ALL_OFFICIAL_STANDARD_DEDUCTIONS:
                    issues.append(
                        f"Page {rel_path}: Mismatched standard deduction value '${val:,.0f}': "
                        f"does not match official published IRS standard deduction schedules"
                    )
                else:
                    if "single" in surrounding and "married" not in surrounding and "mfj" not in surrounding:
                        if val not in {8600.0, 14600.0, 15000.0, 15350.0}:
                            issues.append(
                                f"Page {rel_path}: Mismatched single standard deduction value '${val:,.0f}': "
                                f"official published Single standard deduction is $14,600 (2024), $15,000 (2025/2026), or $8,600 (post-TCJA)"
                            )
                    elif ("married" in surrounding or "mfj" in surrounding) and "single" not in surrounding and "separately" not in surrounding:
                        if val not in {17200.0, 29200.0, 30000.0, 30700.0}:
                            issues.append(
                                f"Page {rel_path}: Mismatched MFJ standard deduction value '${val:,.0f}': "
                                f"official published MFJ standard deduction is $29,200 (2024), $30,000 (2025/2026), or $17,200 (post-TCJA)"
                            )
        except Exception:
            pass

    # 5. Section 179 maximum deduction and phaseout limits
    sec179_matches = re.finditer(
        r'(?:Section\s+179|Sec\.?\s*179)\s+(?:max(?:imum)?\s+(?:deduction|expensing)|expensing\s+(?:cap|limit)|deduction\s+(?:cap|limit)|limit|cap)\s*(?:of|is|:|=|amount)?\s*\$([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{6,8})',
        content,
        re.IGNORECASE
    )
    for m in sec179_matches:
        raw_val = m.group(1).replace(",", "")
        try:
            val = float(raw_val)
            if val not in {1220000.0, 1250000.0, 1290000.0}:
                issues.append(
                    f"Page {rel_path}: Mismatched Section 179 expensing limit '${val:,.0f}': "
                    f"does not match official published schedule ($1,220,000 for 2024, $1,250,000 for 2025, $1,290,000 for 2026)"
                )
        except Exception:
            pass

    sec179_phaseout = re.finditer(
        r'(?:Section\s+179|Sec\.?\s*179).*?phase-?out\s+(?:threshold|limit|begins?|starts?)\s*(?:of|at|is|:|=|amount)?\s*\$([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{6,8})',
        content,
        re.IGNORECASE
    )
    for m in sec179_phaseout:
        raw_val = m.group(1).replace(",", "")
        try:
            val = float(raw_val)
            if val not in {3050000.0, 3130000.0, 3220000.0}:
                issues.append(
                    f"Page {rel_path}: Mismatched Section 179 phaseout threshold '${val:,.0f}': "
                    f"does not match official published schedule ($3,050,000 for 2024, $3,130,000 for 2025, $3,220,000 for 2026)"
                )
        except Exception:
            pass

    # 6. Section 1202 QSBS
    qsbs_asset = re.finditer(
        r'(?:Section\s+1202|QSBS|qualified\s+small\s+business\s+stock).*?(?:gross\s+assets?|asset\s+(?:ceiling|limit|cap))\s*(?:of|is|:|=|amount)?\s*\$([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{6,9})',
        content,
        re.IGNORECASE
    )
    for m in qsbs_asset:
        raw_val = m.group(1).replace(",", "")
        try:
            val = float(raw_val)
            if val != 50000000.0:
                issues.append(
                    f"Page {rel_path}: Mismatched Section 1202 QSBS asset ceiling '${val:,.0f}': "
                    f"statutory ceiling under IRC 1202(d)(1) is strictly $50,000,000"
                )
        except Exception:
            pass

    qsbs_excl = re.finditer(
        r'(?:Section\s+1202|QSBS|qualified\s+small\s+business\s+stock).*?(?:gain\s+exclusion\s+cap|exclusion\s+(?:limit|cap)|maximum\s+exclusion)\s*(?:of|is|:|=|amount)?\s*\$([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{6,9})',
        content,
        re.IGNORECASE
    )
    for m in qsbs_excl:
        raw_val = m.group(1).replace(",", "")
        try:
            val = float(raw_val)
            if val != 10000000.0:
                issues.append(
                    f"Page {rel_path}: Mismatched Section 1202 QSBS exclusion cap '${val:,.0f}': "
                    f"statutory cap under IRC 1202(b)(1) is strictly $10,000,000"
                )
        except Exception:
            pass

    # 7. Retirement 401(k) and IRA limits
    ret_401k = re.finditer(
        r'(?:401\(?k\)?|403\(?b\)?)\s+(?:elective\s+deferral(?:\s+limit)?|contribution\s+limit|maximum\s+deferral|annual\s+limit|deferral\s+limit|limit)\s*(?:of|is|:|=|amount)?\s*\$([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,6})',
        content,
        re.IGNORECASE
    )
    for m in ret_401k:
        raw_val = m.group(1).replace(",", "")
        try:
            val = float(raw_val)
            if val not in {23000.0, 23500.0, 24000.0}:
                issues.append(
                    f"Page {rel_path}: Mismatched 401(k) deferral limit '${val:,.0f}': "
                    f"does not match official published IRS schedule ($23,000 for 2024, $23,500 for 2025, $24,000 for 2026)"
                )
        except Exception:
            pass

    ret_ira = re.finditer(
        r'(?:traditional\s+ira|roth\s+ira|\bira\b)\s+(?:contribution\s+limit|annual\s+limit|maximum\s+contribution)\s*(?:of|is|:|=|amount)?\s*\$([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,6})',
        content,
        re.IGNORECASE
    )
    for m in ret_ira:
        raw_val = m.group(1).replace(",", "")
        try:
            val = float(raw_val)
            if val not in {7000.0, 7500.0}:
                issues.append(
                    f"Page {rel_path}: Mismatched IRA contribution limit '${val:,.0f}': "
                    f"does not match official published IRS schedule ($7,000 for 2024-2025, $7,500 for 2026)"
                )
        except Exception:
            pass

    # 8. Structured manifests and scripts
    for script_match in re.finditer(
        r'<script[^>]*type=[\'"]application/json[\'"][^>]*id=[\'"]([^\'"]*)[\'"][^>]*>(.*?)</script>',
        content,
        re.DOTALL | re.IGNORECASE,
    ):
        script_raw = script_match.group(2).strip()
        try:
            data = json.loads(script_raw)
            if isinstance(data, dict):
                if "brackets" in data and isinstance(data["brackets"], list):
                    for idx, b in enumerate(data["brackets"]):
                        if isinstance(b, dict):
                            crate = b.get("current_rate") or b.get("rate")
                            if crate is not None and float(crate) not in VALID_FEDERAL_TAX_RATES:
                                issues.append(
                                    f"Page {rel_path}: Structured manifest bracket {idx} contains invented rate {crate}%"
                                )
                            srate = b.get("sunset_rate")
                            if srate is not None and float(srate) not in VALID_FEDERAL_TAX_RATES:
                                issues.append(
                                    f"Page {rel_path}: Structured manifest bracket {idx} contains invented sunset rate {srate}%"
                                )
                if "max_asset_issuance_usd" in data:
                    if float(data["max_asset_issuance_usd"]) != 50000000.0:
                        issues.append(
                            f"Page {rel_path}: Structured manifest contains invalid Section 1202 asset cap: {data['max_asset_issuance_usd']}"
                        )
                if "gain_exclusion_cap_usd" in data:
                    if float(data["gain_exclusion_cap_usd"]) != 10000000.0:
                        issues.append(
                            f"Page {rel_path}: Structured manifest contains invalid Section 1202 exclusion cap: {data['gain_exclusion_cap_usd']}"
                        )
                if "holding_period_years" in data:
                    if int(data["holding_period_years"]) != 5:
                        issues.append(
                            f"Page {rel_path}: Structured manifest contains invalid Section 1202 holding period: {data['holding_period_years']}"
                        )
        except Exception:
            pass

    return issues


def assert_statutory_tax_brackets(content: str, context: str = "") -> bool:
    """
    Contract assertion ensuring all tax brackets and marginal rates match official published schedules.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    if not isinstance(content, str):
        raise ValueError(f"Content must be a string{ctx}")
    assert_no_forbidden_dashes(content, context=context)
    issues = detect_uncorroborated_statutory_claims(content, rel_path=context or "index.html")
    bracket_issues = [i for i in issues if "bracket" in i or "rate" in i or "tax" in i]
    if bracket_issues:
        raise ValueError(f"Statutory tax bracket contract violation{ctx}: {bracket_issues[0]}")
    return True


def assert_standard_deduction_values(content: str, context: str = "") -> bool:
    """
    Contract assertion ensuring standard deduction figures match official published schedules.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    if not isinstance(content, str):
        raise ValueError(f"Content must be a string{ctx}")
    assert_no_forbidden_dashes(content, context=context)
    issues = detect_uncorroborated_statutory_claims(content, rel_path=context or "index.html")
    ded_issues = [i for i in issues if "standard deduction" in i.lower()]
    if ded_issues:
        raise ValueError(f"Standard deduction contract violation{ctx}: {ded_issues[0]}")
    return True


def assert_statutory_limits(content: str, context: str = "") -> bool:
    """
    Contract assertion ensuring statutory limits match official published schedules.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    if not isinstance(content, str):
        raise ValueError(f"Content must be a string{ctx}")
    assert_no_forbidden_dashes(content, context=context)
    issues = detect_uncorroborated_statutory_claims(content, rel_path=context or "index.html")
    limit_issues = [i for i in issues if "limit" in i.lower() or "ceiling" in i.lower() or "phaseout" in i.lower() or "cap" in i.lower()]
    if limit_issues:
        raise ValueError(f"Statutory limit contract violation{ctx}: {limit_issues[0]}")
    return True


def assert_no_uncorroborated_tax_constants(content: str, context: str = "") -> bool:
    """
    Contract assertion ensuring zero uncorroborated tax constants, invented statutory limits,
    orphaned deduction figures, or silent fallback defaults.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    if not isinstance(content, str):
        raise ValueError(f"Content must be a string{ctx}")
    assert_no_forbidden_dashes(content, context=context)
    issues = detect_uncorroborated_statutory_claims(content, rel_path=context or "index.html")
    if issues:
        raise ValueError(f"Uncorroborated tax constant violation{ctx}: {issues[0]}")
    return True


def assert_cross_web_consensus_and_corroboration(
    content: str,
    require_corroboration: bool = False,
    context: str = "",
) -> bool:
    """
    Comprehensive contract assertion for Factor 8: Cross-Web Consensus & Corroboration (+1.81).
    Verifies agreement on baseline facts and statutory constants across the web,
    verifying standard tax brackets, statutory limits, and standard deduction values
    against official published schedules.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    if not isinstance(content, str):
        raise ValueError(f"Content must be a string{ctx}")

    # 1. Zero forbidden dashes
    assert_no_forbidden_dashes(content, context=context)

    # 2. Check uncorroborated claims
    issues = detect_uncorroborated_statutory_claims(content, rel_path=context or "index.html")
    if issues:
        raise ValueError(f"Cross-web statutory consensus violation{ctx}: {issues[0]}")

    # 3. Requirement check
    if require_corroboration:
        has_verified_constant = (
            "1,250,000" in content
            or "1,220,000" in content
            or "1,290,000" in content
            or "15,000" in content
            or "30,000" in content
            or "14,600" in content
            or "29,200" in content
            or "8,600" in content
            or "17,200" in content
            or "50,000,000" in content
            or "10,000,000" in content
            or "23,500" in content
            or "23,000" in content
            or "24,000" in content
            or "tax-brackets" in content
            or "brackets" in content
        )
        if not has_verified_constant:
            raise ValueError(f"Document missing verified statutory constants or published schedule reconciliation{ctx}")

    return True


assert_cross_web_corroboration = assert_cross_web_consensus_and_corroboration
assert_statutory_consensus = assert_cross_web_consensus_and_corroboration
assert_baseline_fact_agreement = assert_cross_web_consensus_and_corroboration
assert_statutory_constants_corroboration = assert_cross_web_consensus_and_corroboration


# =============================================================================
# Factor 9: Source / Publisher Reputation (+1.78) Specifications & Contracts
# =============================================================================

ANONYMOUS_AUTHOR_PATTERNS = [
    re.compile(r'^(?:anonymous|admin(?:istrator)?|staff(?:\s+writer)?|editorial\s+team|guest(?:\s+author)?|unknown|user|root|editor)$', re.IGNORECASE),
    re.compile(r'\b(?:anonymous\s+contributor|uncredited|unnamed\s+author)\b', re.IGNORECASE),
]

AUTHOR_CREDENTIAL_KEYWORDS = {
    "cpa", "cfa", "ea", "jd", "esq", "llm", "phd", "ph.d.", "mba", "ms", "ma", "bs",
    "attorney", "tax attorney", "tax specialist", "tax expert", "tax director",
    "accountant", "certified public accountant", "enrolled agent",
    "financial analyst", "chartered financial analyst", "wealth manager",
    "actuary", "economist", "statistician", "data scientist",
    "editor", "senior editor", "managing editor", "contributor", "senior writer",
    "founder", "co-founder", "ceo", "cto", "cfo", "chief economist",
    "director", "lead architect", "principal engineer", "researcher",
    "professor", "fellow", "consultant", "advisor",
}

EDITORIAL_POLICY_HREF_PATTERNS = [
    re.compile(r'/editorial(?:-policy|-standards|-guidelines)?/?', re.IGNORECASE),
    re.compile(r'/review(?:-policy|-process|-standards)?/?', re.IGNORECASE),
    re.compile(r'/corrections?(?:-policy)?/?', re.IGNORECASE),
    re.compile(r'/fact-check(?:ing)?(?:-policy)?/?', re.IGNORECASE),
    re.compile(r'/standards/?', re.IGNORECASE),
    re.compile(r'/publishing-principles/?', re.IGNORECASE),
]

ABOUT_HREF_PATTERNS = [
    re.compile(r'/(?:about|about-us|team|who-we-are|company)/?', re.IGNORECASE),
]

CONTACT_HREF_PATTERNS = [
    re.compile(r'/(?:contact|contact-us|reach-us|support)/?', re.IGNORECASE),
    re.compile(r'^mailto:[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', re.IGNORECASE),
]


def _parse_iso_date(val: Any) -> Optional[datetime]:
    """
    Parses ISO-8601 date or datetime string into a normalized datetime object.
    Returns None if the value is not a valid ISO date string.
    Zero em-dashes. Zero en-dashes.
    """
    if not val or not isinstance(val, str):
        return None
    clean = val.strip()
    try:
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', clean)
        if m:
            try:
                y, mon, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                return datetime(y, mon, d)
            except Exception:
                return None
        return None


def extract_schemas_from_json_ld(data: Any) -> List[Dict[str, Any]]:
    """
    Recursively extracts all dictionaries from parsed JSON-LD blocks.
    Zero em-dashes. Zero en-dashes.
    """
    items: List[Dict[str, Any]] = []
    if isinstance(data, dict):
        items.append(data)
        for v in data.values():
            items.extend(extract_schemas_from_json_ld(v))
    elif isinstance(data, (list, tuple)):
        for item in data:
            items.extend(extract_schemas_from_json_ld(item))
    return items


def extract_author_and_publisher_metadata(content: str) -> Dict[str, Any]:
    """
    Extracts author credentials, Person and Organization schema, editorial policies,
    freshness signals, and about/contact linkages from document text and structured data.
    Zero em-dashes. Zero en-dashes.
    """
    authors: List[Dict[str, Any]] = []
    publishers: List[Dict[str, Any]] = []
    raw_blocks: List[str] = []
    date_published: Optional[str] = None
    date_modified: Optional[str] = None
    has_editorial_policy: bool = False
    has_about_link: bool = False
    has_contact_link: bool = False

    if not content or not isinstance(content, str):
        return {
            "authors": authors,
            "publishers": publishers,
            "raw_blocks": raw_blocks,
            "date_published": date_published,
            "date_modified": date_modified,
            "has_editorial_policy": has_editorial_policy,
            "has_about_link": has_about_link,
            "has_contact_link": has_contact_link,
        }

    # 1. Structured data JSON-LD extraction
    json_ld_matches = re.findall(
        r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        content,
        re.IGNORECASE | re.DOTALL,
    )
    for raw in json_ld_matches:
        raw_blocks.append(raw)
        try:
            parsed = json.loads(raw.strip())
            all_objects = extract_schemas_from_json_ld(parsed)
            for obj in all_objects:
                stype = obj.get("@type")
                types = set(stype) if isinstance(stype, list) else {stype}

                # Person schema / Author
                if "Person" in types:
                    authors.append(obj)

                # Organization schema / Publisher
                org_types = {"Organization", "NewsMediaOrganization", "Corporation", "EducationalOrganization", "GovernmentOrganization"}
                if types.intersection(org_types):
                    publishers.append(obj)

                # Check nested author in Article/WebPage
                if "author" in obj:
                    author_val = obj["author"]
                    if isinstance(author_val, dict):
                        if ("@type" in author_val or "name" in author_val) and author_val not in authors:
                            authors.append(author_val)
                    elif isinstance(author_val, list):
                        for a in author_val:
                            if isinstance(a, dict) and ("@type" in a or "name" in a) and a not in authors:
                                authors.append(a)
                            elif isinstance(a, str):
                                authors.append({"@type": "Person", "name": a})
                    elif isinstance(author_val, str):
                        authors.append({"@type": "Person", "name": author_val})

                # Check nested publisher in Article/WebPage
                if "publisher" in obj:
                    pub_val = obj["publisher"]
                    if isinstance(pub_val, dict):
                        if ("@type" in pub_val or "name" in pub_val) and pub_val not in publishers:
                            publishers.append(pub_val)
                    elif isinstance(pub_val, str):
                        publishers.append({"@type": "Organization", "name": pub_val})

                # Dates
                if obj.get("datePublished") and not date_published:
                    date_published = str(obj["datePublished"]).strip()
                if obj.get("dateModified") and not date_modified:
                    date_modified = str(obj["dateModified"]).strip()

                # Editorial policy / publishingPrinciples in schema
                if obj.get("publishingPrinciples") or obj.get("editorialPolicy") or obj.get("reviewedBy"):
                    has_editorial_policy = True

                # Organization contactPoint
                if obj.get("contactPoint"):
                    has_contact_link = True

        except Exception:
            pass

    # 2. Meta tags extraction for dates
    pub_meta = re.search(
        r'<meta\s+(?:property|name)=["\'](?:article:published_time|datePublished|pubdate)["\']\s+content=["\']([^"\']*)["\']',
        content,
        re.IGNORECASE,
    )
    if pub_meta and not date_published:
        date_published = pub_meta.group(1).strip()

    mod_meta = re.search(
        r'<meta\s+(?:property|name)=["\'](?:article:modified_time|dateModified)["\']\s+content=["\']([^"\']*)["\']',
        content,
        re.IGNORECASE,
    )
    if mod_meta and not date_modified:
        date_modified = mod_meta.group(1).strip()

    # 3. HTML Link inspection
    href_matches = re.findall(r'<a\b[^>]*\bhref=["\']([^"\']*)["\']', content, re.IGNORECASE)
    for href in href_matches:
        h_clean = href.strip().lower()
        if any(pat.search(h_clean) for pat in EDITORIAL_POLICY_HREF_PATTERNS):
            has_editorial_policy = True
        if any(pat.search(h_clean) for pat in ABOUT_HREF_PATTERNS):
            has_about_link = True
        if any(pat.search(h_clean) for pat in CONTACT_HREF_PATTERNS):
            has_contact_link = True

    # 4. On-page text indicators for editorial review if not already found
    content_lower = content.lower()
    if not has_editorial_policy:
        review_indicators = [
            "editorial policy", "editorial guidelines", "editorial standards",
            "reviewed by", "fact checked by", "fact-checked by", "corrections policy"
        ]
        if any(ind in content_lower for ind in review_indicators):
            has_editorial_policy = True

    return {
        "authors": authors,
        "publishers": publishers,
        "raw_blocks": raw_blocks,
        "date_published": date_published,
        "date_modified": date_modified,
        "has_editorial_policy": has_editorial_policy,
        "has_about_link": has_about_link,
        "has_contact_link": has_contact_link,
    }


def detect_publisher_reputation_issues(
    content: str,
    rel_path: str = "index.html",
    require_strict: bool = False,
) -> List[str]:
    """
    Detects missing author credentials, anonymous publisher attributions, invalid
    Person or Organization schema, omitted editorial review policies, stale or
    inverted freshness signals, and missing about/contact linkages.
    Zero em-dashes. Zero en-dashes.
    """
    issues: List[str] = []
    if not content or not isinstance(content, str):
        return issues

    # 1. Strict anti-slop check
    if "\u2014" in content:
        issues.append(f"Page {rel_path}: Document contains forbidden em-dash")
    if "\u2013" in content:
        issues.append(f"Page {rel_path}: Document contains forbidden en-dash")

    meta = extract_author_and_publisher_metadata(content)

    # 2. JSON-LD existence check
    if not meta["raw_blocks"]:
        issues.append(
            f"Page {rel_path}: Missing Schema.org JSON-LD structured data (<script type='application/ld+json'> not found)"
        )
        return issues

    # 3. Publisher / Organization check
    publishers = meta["publishers"]
    if not publishers:
        issues.append(
            f"Page {rel_path}: Missing Organization or Publisher structured data in schema markup"
        )
    else:
        for pub in publishers:
            pname = str(pub.get("name", "")).strip()
            if not pname:
                issues.append(f"Page {rel_path}: Invalid Organization schema: missing or empty 'name'")
            else:
                for pat in ANONYMOUS_AUTHOR_PATTERNS:
                    if pat.search(pname):
                        issues.append(
                            f"Page {rel_path}: Anonymous or placeholder publisher attribution detected ('{pname}')"
                        )
                        break
            if not pub.get("url"):
                issues.append(f"Page {rel_path}: Invalid Organization schema: missing or empty 'url'")

    # 4. Author / Person check
    authors = meta["authors"]
    if not authors and require_strict:
        issues.append(
            f"Page {rel_path}: Missing author credentials: no Person or Author entity found in structured data"
        )
    elif authors:
        for auth in authors:
            aname = str(auth.get("name", "")).strip()
            if not aname:
                issues.append(f"Page {rel_path}: Invalid Person schema: missing or empty 'name'")
                continue

            # Check anonymous author
            is_anon = False
            for pat in ANONYMOUS_AUTHOR_PATTERNS:
                if pat.search(aname):
                    issues.append(
                        f"Page {rel_path}: Anonymous or placeholder author attribution detected ('{aname}')"
                    )
                    is_anon = True
                    break

            if is_anon:
                continue

            # Check credentials
            has_creds = False
            for cred_key in ("jobTitle", "hasCredential", "description", "knowsAbout", "alumniOf", "worksFor"):
                if auth.get(cred_key):
                    has_creds = True
                    break

            if not has_creds:
                author_tokens = set(re.findall(r'\b[a-zA-Z0-9.]+\b', aname.lower()))
                for kw in AUTHOR_CREDENTIAL_KEYWORDS:
                    if " " in kw:
                        if kw in aname.lower():
                            has_creds = True
                            break
                    else:
                        if kw in author_tokens:
                            has_creds = True
                            break

            if not has_creds:
                issues.append(
                    f"Page {rel_path}: Missing author credentials for author '{aname}': "
                    f"author must have verified credentials, jobTitle, or expertise description"
                )

    # 5. Editorial review policy check
    if not meta["has_editorial_policy"]:
        issues.append(
            f"Page {rel_path}: Missing editorial review policy or reviewedBy attribution: "
            f"page must provide editorial guidelines or review verification"
        )

    # 6. Freshness signals check (datePublished / dateModified)
    raw_pub = meta.get("date_published")
    raw_mod = meta.get("date_modified")
    pub_dt = None
    mod_dt = None

    if raw_pub:
        pub_dt = _parse_iso_date(raw_pub)
        if pub_dt is None:
            issues.append(f"Page {rel_path}: Invalid ISO-8601 date format for datePublished ('{raw_pub}')")
        elif pub_dt.year < 2000 or pub_dt.year > 2035:
            issues.append(f"Page {rel_path}: Out-of-bounds publication date '{raw_pub}' (year {pub_dt.year})")
    elif require_strict:
        issues.append(f"Page {rel_path}: Missing datePublished freshness signal in structured data")

    if raw_mod:
        mod_dt = _parse_iso_date(raw_mod)
        if mod_dt is None:
            issues.append(f"Page {rel_path}: Invalid ISO-8601 date format for dateModified ('{raw_mod}')")
        elif mod_dt.year < 2000 or mod_dt.year > 2035:
            issues.append(f"Page {rel_path}: Out-of-bounds modified date '{raw_mod}' (year {mod_dt.year})")

    if pub_dt and mod_dt:
        if mod_dt < pub_dt:
            issues.append(
                f"Page {rel_path}: Chronology violation: dateModified ('{raw_mod}') precedes datePublished ('{raw_pub}')"
            )

    # 7. About and contact linkages check
    if not meta["has_about_link"] and not meta["has_contact_link"]:
        issues.append(
            f"Page {rel_path}: Missing about/contact linkages: "
            f"page must provide navigable links to about or contact destinations"
        )

    return issues


def assert_publisher_authority(content_or_data: Any, context: str = "") -> bool:
    """
    Contract assertion ensuring publisher authority: non-empty, non-anonymous Organization
    with verified name and authoritative URL.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    if isinstance(content_or_data, dict):
        pub = content_or_data.get("publisher", content_or_data) if "@type" in content_or_data and content_or_data["@type"] != "Organization" else content_or_data
        name = pub.get("name", "").strip() if isinstance(pub, dict) else str(pub).strip()
        if not name:
            raise ValueError(f"Publisher authority violation{ctx}: missing or empty publisher name")
        for pat in ANONYMOUS_AUTHOR_PATTERNS:
            if pat.search(name):
                raise ValueError(f"Publisher authority violation{ctx}: anonymous or placeholder publisher '{name}'")
        if isinstance(pub, dict) and not pub.get("url"):
            raise ValueError(f"Publisher authority violation{ctx}: publisher missing authoritative URL")
        return True
    elif isinstance(content_or_data, str):
        assert_no_forbidden_dashes(content_or_data, context=context)
        issues = detect_publisher_reputation_issues(content_or_data, rel_path=context or "index.html")
        pub_issues = [i for i in issues if "publisher" in i.lower() or "organization" in i.lower()]
        if pub_issues:
            raise ValueError(f"Publisher authority violation{ctx}: {pub_issues[0]}")
        return True
    raise ValueError(f"Publisher authority violation{ctx}: content must be string or dict")


def assert_author_credentials(content_or_data: Any, context: str = "") -> bool:
    """
    Contract assertion ensuring author credentials: verified Person schema with credentials,
    jobTitle, or expertise description, and non-anonymous attribution.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    if isinstance(content_or_data, dict):
        person = content_or_data.get("author", content_or_data) if "@type" in content_or_data and content_or_data["@type"] != "Person" else content_or_data
        name = person.get("name", "").strip() if isinstance(person, dict) else str(person).strip()
        if not name:
            raise ValueError(f"Author credentials violation{ctx}: missing or empty author name")
        for pat in ANONYMOUS_AUTHOR_PATTERNS:
            if pat.search(name):
                raise ValueError(f"Author credentials violation{ctx}: anonymous or placeholder author '{name}'")
        has_creds = False
        if isinstance(person, dict):
            for k in ("jobTitle", "hasCredential", "description", "knowsAbout", "alumniOf", "worksFor"):
                if person.get(k):
                    has_creds = True
                    break
        if not has_creds:
            author_tokens = set(re.findall(r'\b[a-zA-Z0-9.]+\b', name.lower()))
            for kw in AUTHOR_CREDENTIAL_KEYWORDS:
                if " " in kw:
                    if kw in name.lower():
                        has_creds = True
                        break
                else:
                    if kw in author_tokens:
                        has_creds = True
                        break
        if not has_creds:
            raise ValueError(f"Author credentials violation{ctx}: author '{name}' lacks verified credentials or jobTitle")
        return True
    elif isinstance(content_or_data, str):
        assert_no_forbidden_dashes(content_or_data, context=context)
        issues = detect_publisher_reputation_issues(content_or_data, rel_path=context or "index.html")
        author_issues = [i for i in issues if "author" in i.lower() or "person" in i.lower()]
        if author_issues:
            raise ValueError(f"Author credentials violation{ctx}: {author_issues[0]}")
        return True
    raise ValueError(f"Author credentials violation{ctx}: content must be string or dict")


def assert_person_organization_schema(content_or_data: Any, context: str = "") -> bool:
    """
    Contract assertion ensuring valid Person and Organization schema markup.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    if isinstance(content_or_data, dict):
        stype = content_or_data.get("@type", "")
        types = set(stype) if isinstance(stype, list) else {stype}
        has_person = "Person" in types
        has_org = any(t in types for t in ("Organization", "NewsMediaOrganization", "Corporation", "EducationalOrganization"))
        if not has_person and not has_org and "@graph" not in content_or_data and "author" not in content_or_data and "publisher" not in content_or_data:
            raise ValueError(f"Person and Organization schema violation{ctx}: schema must contain Person or Organization entity")
        return True
    elif isinstance(content_or_data, str):
        assert_no_forbidden_dashes(content_or_data, context=context)
        meta = extract_author_and_publisher_metadata(content_or_data)
        if not meta["authors"] and not meta["publishers"]:
            raise ValueError(f"Person and Organization schema violation{ctx}: document structured data missing both Person and Organization schema")
        return True
    raise ValueError(f"Person and Organization schema violation{ctx}: content must be string or dict")


def assert_editorial_policy(content_or_data: Any, context: str = "") -> bool:
    """
    Contract assertion ensuring editorial review policy or reviewedBy attribution.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    if isinstance(content_or_data, dict):
        if content_or_data.get("publishingPrinciples") or content_or_data.get("editorialPolicy") or content_or_data.get("reviewedBy"):
            return True
        raise ValueError(f"Editorial review policy violation{ctx}: schema missing publishingPrinciples, editorialPolicy, or reviewedBy")
    elif isinstance(content_or_data, str):
        assert_no_forbidden_dashes(content_or_data, context=context)
        meta = extract_author_and_publisher_metadata(content_or_data)
        if not meta["has_editorial_policy"]:
            raise ValueError(f"Editorial review policy violation{ctx}: missing editorial review policy or reviewedBy attribution")
        return True
    raise ValueError(f"Editorial review policy violation{ctx}: content must be string or dict")


def assert_freshness_signals(content_or_data: Any, context: str = "") -> bool:
    """
    Contract assertion ensuring datePublished and dateModified freshness signals and chronology.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    if isinstance(content_or_data, dict):
        pub = content_or_data.get("datePublished")
        mod = content_or_data.get("dateModified")
        if not pub and not mod:
            raise ValueError(f"Freshness signals violation{ctx}: missing datePublished or dateModified")
        pub_dt = _parse_iso_date(pub) if pub else None
        mod_dt = _parse_iso_date(mod) if mod else None
        if pub and pub_dt is None:
            raise ValueError(f"Freshness signals violation{ctx}: invalid ISO-8601 datePublished '{pub}'")
        if mod and mod_dt is None:
            raise ValueError(f"Freshness signals violation{ctx}: invalid ISO-8601 dateModified '{mod}'")
        if pub_dt and mod_dt and mod_dt < pub_dt:
            raise ValueError(f"Freshness signals violation{ctx}: dateModified ('{mod}') precedes datePublished ('{pub}')")
        return True
    elif isinstance(content_or_data, str):
        assert_no_forbidden_dashes(content_or_data, context=context)
        meta = extract_author_and_publisher_metadata(content_or_data)
        pub = meta.get("date_published")
        mod = meta.get("date_modified")
        pub_dt = _parse_iso_date(pub) if pub else None
        mod_dt = _parse_iso_date(mod) if mod else None
        if pub and pub_dt is None:
            raise ValueError(f"Freshness signals violation{ctx}: invalid ISO-8601 datePublished '{pub}'")
        if mod and mod_dt is None:
            raise ValueError(f"Freshness signals violation{ctx}: invalid ISO-8601 dateModified '{mod}'")
        if pub_dt and (pub_dt.year < 2000 or pub_dt.year > 2035):
            raise ValueError(f"Freshness signals violation{ctx}: out-of-bounds datePublished year {pub_dt.year}")
        if mod_dt and (mod_dt.year < 2000 or mod_dt.year > 2035):
            raise ValueError(f"Freshness signals violation{ctx}: out-of-bounds dateModified year {mod_dt.year}")
        if pub_dt and mod_dt and mod_dt < pub_dt:
            raise ValueError(f"Freshness signals violation{ctx}: dateModified ('{mod}') precedes datePublished ('{pub}')")
        return True
    raise ValueError(f"Freshness signals violation{ctx}: content must be string or dict")


def assert_about_contact_linkages(content_or_data: Any, context: str = "") -> bool:
    """
    Contract assertion ensuring about and contact linkages across navigation or schema.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    if isinstance(content_or_data, dict):
        if content_or_data.get("contactPoint") or "about" in content_or_data:
            return True
        raise ValueError(f"About/contact linkages violation{ctx}: schema missing contactPoint or about linkage")
    elif isinstance(content_or_data, str):
        assert_no_forbidden_dashes(content_or_data, context=context)
        meta = extract_author_and_publisher_metadata(content_or_data)
        if not meta["has_about_link"] and not meta["has_contact_link"]:
            raise ValueError(f"About/contact linkages violation{ctx}: missing about or contact navigational links")
        return True
    raise ValueError(f"About/contact linkages violation{ctx}: content must be string or dict")


def assert_source_publisher_reputation(
    content: str,
    require_strict: bool = False,
    context: str = "",
) -> bool:
    """
    Comprehensive contract assertion for Factor 9: Source / Publisher Reputation (+1.78).
    Verifies publisher authority, verified author credentials, Person and Organization schema,
    editorial review policies, datePublished and dateModified freshness signals,
    and about and contact linkages.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    if not isinstance(content, str):
        raise ValueError(f"Content must be a string{ctx}")

    assert_no_forbidden_dashes(content, context=context)
    issues = detect_publisher_reputation_issues(
        content,
        rel_path=context or "index.html",
        require_strict=require_strict,
    )
    if issues:
        raise ValueError(f"Source publisher reputation contract violation{ctx}: {issues[0]}")
    return True


assert_publisher_reputation = assert_source_publisher_reputation
assert_publisher_authority_and_credentials = assert_source_publisher_reputation
assert_author_and_publisher_schema = assert_source_publisher_reputation
assert_editorial_and_freshness_signals = assert_source_publisher_reputation


# ==============================================================================
# Factor 10: Extractable Content Structure (+1.69)
# Strict semantic HTML heading hierarchies without skipped levels,
# data tables with table headers and column scopes (scope="col"),
# ordered lists (<ol>) for procedural steps, and clean passage-level blocks.
# Zero em-dashes. Zero en-dashes.
# ==============================================================================

PROCEDURAL_CONTAINER_KEYWORDS: Tuple[str, ...] = (
    "step",
    "steps",
    "procedure",
    "how to",
    "how-to",
    "instructions",
    "workflow",
    "process",
    "tutorial",
    "walkthrough",
    "protocol",
    "implementation steps",
    "action plan",
    "setup guide",
    "getting started",
    "calculation steps",
    "calculation procedure",
    "rules to calculate",
    "guide to",
)

PROCEDURAL_HEADING_PATTERN = re.compile(
    r"\b(steps?|procedure|how\s+to|instructions?|workflow|process|action\s+plan|protocol|walkthrough|calculation\s+steps?|getting\s+started)\b",
    re.IGNORECASE,
)

PROCEDURAL_STEP_PREFIX_PATTERN = re.compile(
    r"^(step\s*\d+|phase\s*\d+|stage\s*\d+|\d+[\.\)]|\bfirst\b|\bsecond\b|\bthird\b|\bfourth\b|\bfifth\b|\bnext\b|\bfinally\b)",
    re.IGNORECASE,
)

MAX_PASSAGE_CHAR_LENGTH: int = 2000


class _ExtractableContentParser(HTMLParser):
    """
    HTML parser extracting heading hierarchy, tables with column scopes,
    lists with procedural contexts, and passage-level blocks.
    Zero em-dashes. Zero en-dashes.
    """

    def __init__(self) -> None:
        super().__init__()
        self.headings: List[Dict[str, Any]] = []
        self.tables: List[Dict[str, Any]] = []
        self.lists: List[Dict[str, Any]] = []
        self.passages: List[Dict[str, Any]] = []
        self.empty_passages_count: int = 0

        self.current_heading_tag: Optional[str] = None
        self.current_heading_text: List[str] = []
        self.current_heading_attrs: Dict[str, str] = {}
        self.last_seen_heading_text: str = ""

        self.in_table = False
        self.current_table_headers: List[Dict[str, Any]] = []
        self.current_table_rows: List[List[str]] = []
        self.current_row: List[str] = []
        self.current_cell_tag: Optional[str] = None
        self.current_cell_text: List[str] = []
        self.current_cell_attrs: Dict[str, str] = {}

        self.list_stack: List[Dict[str, Any]] = []
        self.current_li_text: List[str] = []
        self.in_li = False
        self.in_nav = False

        self.current_passage_tag: Optional[str] = None
        self.current_passage_text: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        tag_lower = tag.lower()
        attrs_dict = {k.lower(): (v or "") for k, v in attrs}

        if tag_lower == "nav":
            self.in_nav = True

        elif tag_lower in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.current_heading_tag = tag_lower
            self.current_heading_attrs = attrs_dict
            self.current_heading_text = []

        elif tag_lower == "table":
            self.in_table = True
            self.current_table_headers = []
            self.current_table_rows = []

        elif tag_lower == "tr":
            self.current_row = []

        elif tag_lower in ("th", "td"):
            self.current_cell_tag = tag_lower
            self.current_cell_attrs = attrs_dict
            self.current_cell_text = []

        elif tag_lower in ("ol", "ul"):
            self.list_stack.append({
                "type": tag_lower,
                "items": [],
                "context_heading": self.last_seen_heading_text,
                "attrs": attrs_dict,
                "in_nav": self.in_nav,
            })

        elif tag_lower == "li":
            self.in_li = True
            self.current_li_text = []

        elif tag_lower in ("p", "blockquote"):
            self.current_passage_tag = tag_lower
            self.current_passage_text = []

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()

        if tag_lower == "nav":
            self.in_nav = False

        elif tag_lower in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = "".join(self.current_heading_text).strip()
            level = int(tag_lower[1])
            self.headings.append({
                "tag": tag_lower,
                "level": level,
                "text": text,
                "attrs": self.current_heading_attrs,
            })
            self.last_seen_heading_text = text
            self.current_heading_tag = None
            self.current_heading_text = []

        elif tag_lower == "th":
            text = "".join(self.current_cell_text).strip()
            scope = self.current_cell_attrs.get("scope", "").strip().lower()
            self.current_table_headers.append({
                "text": text,
                "scope": scope,
                "attrs": self.current_cell_attrs,
            })
            self.current_cell_tag = None

        elif tag_lower == "td":
            text = "".join(self.current_cell_text).strip()
            self.current_row.append(text)
            self.current_cell_tag = None

        elif tag_lower == "tr":
            if self.current_row:
                self.current_table_rows.append(list(self.current_row))
                self.current_row = []

        elif tag_lower == "table":
            self.tables.append({
                "headers": list(self.current_table_headers),
                "rows": list(self.current_table_rows),
            })
            self.in_table = False
            self.current_table_headers = []
            self.current_table_rows = []

        elif tag_lower == "li":
            item_text = "".join(self.current_li_text).strip()
            if self.list_stack:
                self.list_stack[-1]["items"].append(item_text)
            self.in_li = False
            self.current_li_text = []

        elif tag_lower in ("ol", "ul"):
            if self.list_stack:
                lst = self.list_stack.pop()
                self.lists.append(lst)

        elif tag_lower in ("p", "blockquote"):
            text = "".join(self.current_passage_text).strip()
            clean_text = html.unescape(text).replace("\xa0", " ").strip()
            if not clean_text:
                self.empty_passages_count += 1
            else:
                self.passages.append({
                    "tag": tag_lower,
                    "text": clean_text,
                    "char_count": len(clean_text),
                })
            self.current_passage_tag = None
            self.current_passage_text = []

    def handle_data(self, data: str) -> None:
        if self.current_heading_tag:
            self.current_heading_text.append(data)
        if self.current_cell_tag:
            self.current_cell_text.append(data)
        if self.in_li:
            self.current_li_text.append(data)
        if self.current_passage_tag:
            self.current_passage_text.append(data)


def extract_content_structure_metadata(content: str) -> Dict[str, Any]:
    """
    Extracts structured content elements from HTML: headings with levels,
    data tables with header scopes, lists with procedural context, and passage blocks.
    Zero em-dashes. Zero en-dashes.
    """
    if not isinstance(content, str):
        return {
            "headings": [],
            "heading_skips": [],
            "tables": [],
            "lists": [],
            "ordered_lists": [],
            "unordered_lists": [],
            "procedural_blocks": [],
            "passages": [],
            "empty_passages_count": 0,
        }

    parser = _ExtractableContentParser()
    try:
        parser.feed(content)
    except Exception:
        pass

    # Analyze heading skips
    heading_skips: List[Tuple[int, int, str]] = []
    prev_level: Optional[int] = None
    for h in parser.headings:
        curr_level = h["level"]
        if prev_level is not None:
            if curr_level > prev_level + 1:
                heading_skips.append((prev_level, curr_level, h["text"]))
        else:
            if curr_level > 1:
                heading_skips.append((0, curr_level, h["text"]))
        prev_level = curr_level

    # Analyze tables
    analyzed_tables: List[Dict[str, Any]] = []
    for tbl in parser.tables:
        headers = tbl["headers"]
        rows = tbl["rows"]
        unscoped_headers = [h for h in headers if h.get("scope") not in ("col", "colgroup", "row")]
        col_scoped_headers = [h for h in headers if h.get("scope") in ("col", "colgroup")]
        analyzed_tables.append({
            "headers": headers,
            "rows": rows,
            "col_count": len(headers) or (len(rows[0]) if rows else 0),
            "row_count": len(rows),
            "has_headers": bool(headers),
            "has_scoped_headers": bool(headers) and len(unscoped_headers) == 0,
            "unscoped_headers": unscoped_headers,
            "col_scoped_headers": col_scoped_headers,
        })

    # Analyze lists and procedural blocks
    ordered_lists: List[Dict[str, Any]] = []
    unordered_lists: List[Dict[str, Any]] = []
    procedural_blocks: List[Dict[str, Any]] = []

    for lst in parser.lists:
        l_type = lst["type"]
        items = lst["items"]
        context_hdg = lst.get("context_heading", "").strip()
        attrs = lst.get("attrs", {})
        attr_str = " ".join(f"{k} {v}" for k, v in attrs.items()).lower()
        in_nav = lst.get("in_nav", False)

        # Check if list is navigational
        is_nav = in_nav or any(k in attr_str for k in ("nav", "menu", "breadcrumb", "toc", "pagination"))

        # Check if procedural
        is_procedural_heading = bool(PROCEDURAL_HEADING_PATTERN.search(context_hdg))
        is_procedural_attr = any(kw in attr_str for kw in ("step", "procedure", "workflow", "process", "instruction"))
        
        # Check item prefixes
        step_items_count = sum(1 for it in items if PROCEDURAL_STEP_PREFIX_PATTERN.search(it.strip()))
        is_procedural_items = step_items_count >= 2 or (len(items) >= 1 and step_items_count == len(items))

        is_procedural = not is_nav and (is_procedural_heading or is_procedural_attr or is_procedural_items)

        list_record = {
            "type": l_type,
            "items": items,
            "context_heading": context_hdg,
            "is_procedural": is_procedural,
            "step_items_count": step_items_count,
        }

        if l_type == "ol":
            ordered_lists.append(list_record)
        else:
            unordered_lists.append(list_record)

        if is_procedural:
            procedural_blocks.append(list_record)

    return {
        "headings": parser.headings,
        "heading_skips": heading_skips,
        "tables": analyzed_tables,
        "lists": parser.lists,
        "ordered_lists": ordered_lists,
        "unordered_lists": unordered_lists,
        "procedural_blocks": procedural_blocks,
        "passages": parser.passages,
        "empty_passages_count": parser.empty_passages_count,
    }


def detect_extractable_content_issues(
    content: str,
    rel_path: str = "index.html",
    require_strict: bool = False,
) -> List[str]:
    """
    Detects extractable content structure issues for Factor 10:
    1. Zero em-dashes and zero en-dashes.
    2. Semantic heading hierarchies without skipped levels (e.g. h1 to h3).
    3. Non-empty headings.
    4. Data tables with structured <th> headers and explicit column scopes (scope="col").
    5. Ordered lists (<ol>) for procedural steps; forbids bulleted lists (<ul>) for sequential tasks.
    6. Clean passage-level blocks without empty <p> tags or monolithic dumps.
    Zero em-dashes. Zero en-dashes.
    """
    issues: List[str] = []
    if not content or not isinstance(content, str):
        return issues

    # 1. Anti-slop
    if "\u2014" in content:
        issues.append(f"Page {rel_path}: Document contains forbidden em-dash")
    if "\u2013" in content:
        issues.append(f"Page {rel_path}: Document contains forbidden en-dash")

    meta = extract_content_structure_metadata(content)

    # 2. Heading hierarchy check
    headings = meta["headings"]
    if not headings and require_strict:
        issues.append(f"Page {rel_path}: Missing semantic heading hierarchy (no heading tags found)")
    elif headings:
        # Check first heading
        if headings[0]["level"] > 1:
            issues.append(
                f"Page {rel_path}: Heading hierarchy violation: document starts with <{headings[0]['tag']}> "
                f"instead of <h1> ('{headings[0]['text']}')"
            )

        # Check empty headings
        for h in headings:
            if not h["text"].strip():
                issues.append(f"Page {rel_path}: Empty heading tag <{h['tag']}> detected")

        # Check skipped levels
        for prev_lvl, curr_lvl, h_text in meta["heading_skips"]:
            if prev_lvl > 0:
                issues.append(
                    f"Page {rel_path}: Heading hierarchy violation: skipped level from h{prev_lvl} to h{curr_lvl} ('{h_text}')"
                )

    # 3. Data tables and scoped headers check
    tables = meta["tables"]
    if not tables and require_strict:
        issues.append(f"Page {rel_path}: Missing structured data tables with scoped headers")
    else:
        for idx, tbl in enumerate(tables):
            headers = tbl["headers"]
            rows = tbl["rows"]

            if not headers:
                # Check for narrative block in table
                for r in rows:
                    for c in r:
                        if len(c) > 150 or len(c.split()) > 30:
                            issues.append(
                                f"Page {rel_path}: Unstructured narrative block masquerading as data table in table {idx}: "
                                f"table lacks <th> headers and dumps prose into cells"
                            )
                            break
                issues.append(f"Page {rel_path}: Data table {idx} missing structured <th> header cells")
                continue

            if len(headers) < 2:
                issues.append(
                    f"Page {rel_path}: Data table {idx} column count ({len(headers)}) below minimum 2 columns"
                )

            if not rows:
                issues.append(f"Page {rel_path}: Data table {idx} contains no data rows (empty table)")

            # Check column scopes on table headers
            unscoped = tbl.get("unscoped_headers", [])
            if unscoped:
                missing_names = ", ".join(f"'{h['text']}'" for h in unscoped)
                issues.append(
                    f"Page {rel_path}: Table header accessibility violation: <th> missing explicit column scope "
                    f"(scope=\"col\") in table {idx}: {missing_names}"
                )

            # Check for empty cells in rows
            for r_idx, r in enumerate(rows):
                for c_idx, c in enumerate(r):
                    if not c or not c.strip():
                        issues.append(
                            f"Page {rel_path}: Data table {idx} row {r_idx} cell {c_idx} is empty"
                        )
                        break

    # 4. Procedural steps and ordered lists check
    procedural_blocks = meta["procedural_blocks"]
    if not procedural_blocks and require_strict:
        issues.append(f"Page {rel_path}: Missing structured procedural steps (<ol> workflow)")
    else:
        for p_block in procedural_blocks:
            if p_block["type"] == "ul":
                ctx_h = f" under heading '{p_block['context_heading']}'" if p_block.get("context_heading") else ""
                issues.append(
                    f"Page {rel_path}: Procedural workflow violation: procedural steps must use ordered lists (<ol>), "
                    f"found unordered bulleted list (<ul>){ctx_h}"
                )
            elif p_block["type"] == "ol":
                if len(p_block["items"]) < 2:
                    issues.append(
                        f"Page {rel_path}: Procedural workflow violation: ordered list (<ol>) contains fewer than 2 procedural steps"
                    )
                for item in p_block["items"]:
                    if not item.strip():
                        issues.append(
                            f"Page {rel_path}: Procedural workflow violation: ordered list (<ol>) contains empty step item"
                        )

    # 5. Clean passage-level blocks check
    if meta["empty_passages_count"] > 0:
        issues.append(
            f"Page {rel_path}: Document contains {meta['empty_passages_count']} empty passage-level block(s) "
            f"(<p> tag without extractable text)"
        )

    for p_idx, p in enumerate(meta["passages"]):
        if p.get("char_count", 0) > MAX_PASSAGE_CHAR_LENGTH:
            issues.append(
                f"Page {rel_path}: Passage-level block {p_idx} exceeds clean extractability limit "
                f"({p['char_count']} chars > {MAX_PASSAGE_CHAR_LENGTH} chars)"
            )

    return issues


def assert_semantic_heading_hierarchy(content_or_headings: Any, context: str = "") -> bool:
    """
    Contract assertion ensuring strict semantic HTML heading hierarchies without skipped levels.
    Rejects heading jumps like h1 to h3, empty heading tags, and forbidden dashes.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    if isinstance(content_or_headings, str):
        assert_no_forbidden_dashes(content_or_headings, context=context)
        meta = extract_content_structure_metadata(content_or_headings)
        headings = meta["headings"]
        if not headings:
            raise ValueError(f"Heading hierarchy violation{ctx}: no heading tags found")
        if headings[0]["level"] > 1:
            raise ValueError(
                f"Heading hierarchy violation{ctx}: document starts with <{headings[0]['tag']}> instead of <h1>"
            )
        for h in headings:
            if not h["text"].strip():
                raise ValueError(f"Heading hierarchy violation{ctx}: empty heading tag <{h['tag']}>")
        if meta["heading_skips"]:
            p_lvl, c_lvl, text = meta["heading_skips"][0]
            raise ValueError(
                f"Heading hierarchy violation{ctx}: skipped level from h{p_lvl} to h{c_lvl} ('{text}')"
            )
        return True
    elif isinstance(content_or_headings, list):
        if not content_or_headings:
            raise ValueError(f"Heading hierarchy violation{ctx}: empty heading sequence")
        prev_level: Optional[int] = None
        for item in content_or_headings:
            level = item if isinstance(item, int) else item.get("level") if isinstance(item, dict) else None
            text = item.get("text", "") if isinstance(item, dict) else str(item)
            if level is None:
                raise ValueError(f"Heading hierarchy violation{ctx}: invalid heading item '{item}'")
            assert_no_forbidden_dashes(text, context=context)
            if prev_level is not None:
                if level > prev_level + 1:
                    raise ValueError(
                        f"Heading hierarchy violation{ctx}: skipped level from h{prev_level} to h{level} ('{text}')"
                    )
            else:
                if level > 1:
                    raise ValueError(
                        f"Heading hierarchy violation{ctx}: document starts with level {level} instead of 1"
                    )
            prev_level = level
        return True
    raise ValueError(f"Heading hierarchy violation{ctx}: content must be string or list")


def assert_scoped_table_headers(content_or_tables: Any, context: str = "") -> bool:
    """
    Contract assertion ensuring data tables have structured <th> headers with explicit column scopes (scope="col").
    Rejects tables lacking column scope attributes, tables without headers, or empty cells.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    if isinstance(content_or_tables, str):
        assert_no_forbidden_dashes(content_or_tables, context=context)
        meta = extract_content_structure_metadata(content_or_tables)
        tables = meta["tables"]
        if not tables:
            raise ValueError(f"Table header accessibility violation{ctx}: document missing <table> element")
        for idx, tbl in enumerate(tables):
            if not tbl["headers"]:
                raise ValueError(f"Table header accessibility violation{ctx}: table {idx} missing <th> headers")
            if tbl["unscoped_headers"]:
                unscoped_names = ", ".join(f"'{h['text']}'" for h in tbl["unscoped_headers"])
                raise ValueError(
                    f"Table header accessibility violation{ctx}: table {idx} <th> missing explicit scope=\"col\" attribute: {unscoped_names}"
                )
            if len(tbl["headers"]) < 2:
                raise ValueError(f"Table header accessibility violation{ctx}: table {idx} has fewer than 2 columns")
            if not tbl["rows"]:
                raise ValueError(f"Table header accessibility violation{ctx}: table {idx} contains no data rows")
        return True
    elif isinstance(content_or_tables, dict):
        headers = content_or_tables.get("headers", [])
        if not headers:
            raise ValueError(f"Table header accessibility violation{ctx}: missing headers")
        for h in headers:
            text = h.get("text", "") if isinstance(h, dict) else str(h)
            scope = h.get("scope", "").strip().lower() if isinstance(h, dict) else ""
            assert_no_forbidden_dashes(text, context=context)
            if scope not in ("col", "colgroup", "row"):
                raise ValueError(
                    f"Table header accessibility violation{ctx}: header '{text}' missing explicit scope=\"col\""
                )
        return True
    raise ValueError(f"Table header accessibility violation{ctx}: content must be string or dict")


def assert_procedural_ordered_steps(content_or_lists: Any, context: str = "") -> bool:
    """
    Contract assertion ensuring procedural workflows use ordered lists (<ol>).
    Forbids unordered bulleted lists (<ul>) for sequential procedural steps.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    if isinstance(content_or_lists, str):
        assert_no_forbidden_dashes(content_or_lists, context=context)
        meta = extract_content_structure_metadata(content_or_lists)
        for p_block in meta["procedural_blocks"]:
            if p_block["type"] == "ul":
                raise ValueError(
                    f"Procedural workflow violation{ctx}: procedural steps must use ordered lists (<ol>), "
                    f"found unordered bulleted list (<ul>)"
                )
            if p_block["type"] == "ol" and len(p_block["items"]) < 2:
                raise ValueError(
                    f"Procedural workflow violation{ctx}: ordered list (<ol>) contains fewer than 2 steps"
                )
        return True
    elif isinstance(content_or_lists, list):
        if not content_or_lists:
            raise ValueError(f"Procedural workflow violation{ctx}: empty steps list")
        for item in content_or_lists:
            assert_no_forbidden_dashes(str(item), context=context)
        return True
    raise ValueError(f"Procedural workflow violation{ctx}: content must be string or list")


def assert_passage_level_blocks(content_or_passages: Any, context: str = "") -> bool:
    """
    Contract assertion ensuring clean passage-level blocks without empty tags or monolithic blocks.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    if isinstance(content_or_passages, str):
        assert_no_forbidden_dashes(content_or_passages, context=context)
        meta = extract_content_structure_metadata(content_or_passages)
        if meta["empty_passages_count"] > 0:
            raise ValueError(f"Passage-level block violation{ctx}: contains empty <p> tag")
        for idx, p in enumerate(meta["passages"]):
            if p.get("char_count", 0) > MAX_PASSAGE_CHAR_LENGTH:
                raise ValueError(
                    f"Passage-level block violation{ctx}: block {idx} exceeds {MAX_PASSAGE_CHAR_LENGTH} chars"
                )
        return True
    elif isinstance(content_or_passages, list):
        for idx, p in enumerate(content_or_passages):
            text = str(p)
            assert_no_forbidden_dashes(text, context=context)
            if not text.strip():
                raise ValueError(f"Passage-level block violation{ctx}: empty passage at index {idx}")
            if len(text) > MAX_PASSAGE_CHAR_LENGTH:
                raise ValueError(
                    f"Passage-level block violation{ctx}: passage at index {idx} exceeds {MAX_PASSAGE_CHAR_LENGTH} chars"
                )
        return True
    raise ValueError(f"Passage-level block violation{ctx}: content must be string or list")


def assert_extractable_content_structure(
    content: str,
    require_strict: bool = False,
    context: str = "",
) -> bool:
    """
    Comprehensive contract assertion for Factor 10: Extractable Content Structure (+1.69).
    Enforces strict semantic HTML heading hierarchies without skipped levels,
    data tables with scoped column headers (scope="col"), ordered lists for sequential
    procedural steps, and clean passage-level blocks.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    if not isinstance(content, str):
        raise ValueError(f"Content must be a string{ctx}")

    assert_no_forbidden_dashes(content, context=context)
    issues = detect_extractable_content_issues(
        content,
        rel_path=context or "index.html",
        require_strict=require_strict,
    )
    if issues:
        raise ValueError(f"Extractable content structure contract violation{ctx}: {issues[0]}")
    return True


assert_extractable_structure = assert_extractable_content_structure
assert_content_structure_extractability = assert_extractable_content_structure


# =============================================================================
# Factor 11: Answer Prominence (+1.65) Contracts
# =============================================================================

ANSWER_PROMINENCE_MAX_WORD_COUNT: int = 300

ANSWER_CONTAINER_CLASS_KEYWORDS: Set[str] = {
    "quick-answer",
    "quick_answer",
    "direct-answer",
    "direct_answer",
    "core-answer",
    "core_answer",
    "answer-block",
    "answer_block",
    "featured-answer",
    "featured_answer",
    "key-takeaway",
    "key_takeaway",
    "key-takeaways",
    "key_takeaways",
    "executive-summary",
    "executive_summary",
    "answer-summary",
    "answer_summary",
    "tldr",
    "tl-dr",
    "summary-box",
    "summary_box",
    "answer-prominence",
    "answer_prominence",
}

CALCULATION_WIDGET_CLASS_KEYWORDS: Set[str] = {
    "calc",
    "calculator",
    "calculation-widget",
    "calc-widget",
    "tax-calculator",
    "depreciation-calculator",
    "qbi-calculator",
    "scorp-calculator",
    "interactive-calculator",
    "core-calculator",
    "calculator-widget",
    "calculator-container",
    "interactive-calc",
    "calculation-manifest",
}

SECONDARY_DISCUSSION_HEADING_KEYWORDS: List[str] = [
    "secondary discussion",
    "detailed analysis",
    "background and history",
    "in-depth exploration",
    "in depth exploration",
    "extended discussion",
    "methodology and theory",
    "comprehensive overview",
    "additional context",
    "further reading",
    "deep dive",
]


class _AnswerProminenceParser(HTMLParser):
    """
    HTML parser measuring cumulative body word position up to the primary
    direct answer container or core calculation widget.
    Zero em-dashes. Zero en-dashes.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_head: bool = False
        self.in_header: bool = False
        self.in_nav: bool = False
        self.ignore_depth: int = 0
        self.cumulative_body_words: int = 0
        self.total_body_words: int = 0

        self.found_answer: bool = False
        self.first_answer: Optional[Dict[str, Any]] = None
        self.all_answers_and_widgets: List[Dict[str, Any]] = []

        self.in_answer_container: bool = False
        self.answer_container_depth: int = 0
        self.current_answer_text_parts: List[str] = []
        self.current_answer_has_widget: bool = False

        self.tag_stack: List[Tuple[str, Dict[str, str]]] = []

        self.current_heading_tag: Optional[str] = None
        self.current_heading_text_parts: List[str] = []
        self.secondary_discussion_headings: List[str] = []
        self.secondary_discussion_before_answer: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        tag_lower = tag.lower()
        attrs_dict = {k.lower(): (v or "") for k, v in attrs}
        self.tag_stack.append((tag_lower, attrs_dict))

        if tag_lower == "head":
            self.in_head = True
            return

        if tag_lower == "header":
            self.in_header = True
            return

        if tag_lower == "nav":
            self.in_nav = True
            return

        if tag_lower in ("style", "script", "template", "svg", "noscript"):
            self.ignore_depth += 1
            return

        if self.in_head or self.in_header or self.in_nav or self.ignore_depth > 0:
            return

        if tag_lower in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.current_heading_tag = tag_lower
            self.current_heading_text_parts = []

        is_answer = self._is_direct_answer(tag_lower, attrs_dict)
        is_widget = self._is_calculation_widget(tag_lower, attrs_dict)

        if self.in_answer_container and is_widget:
            self.current_answer_has_widget = True

        if (is_answer or is_widget) and not self.found_answer:
            self.found_answer = True
            self.in_answer_container = True
            self.answer_container_depth = len(self.tag_stack)
            self.current_answer_text_parts = []
            self.current_answer_has_widget = is_widget

            self.first_answer = {
                "type": "calculation_widget" if is_widget else "direct_answer",
                "tag": tag_lower,
                "attrs": attrs_dict,
                "word_position": self.cumulative_body_words,
                "dom_depth": len(self.tag_stack),
                "has_widget": is_widget,
                "text": "",
            }
        elif (is_answer or is_widget) and not self.in_answer_container:
            self.all_answers_and_widgets.append({
                "type": "calculation_widget" if is_widget else "direct_answer",
                "tag": tag_lower,
                "attrs": attrs_dict,
                "word_position": self.cumulative_body_words,
                "dom_depth": len(self.tag_stack),
            })

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()

        if tag_lower == "head":
            self.in_head = False
        elif tag_lower == "header":
            self.in_header = False
        elif tag_lower == "nav":
            self.in_nav = False
        elif tag_lower in ("style", "script", "template", "svg", "noscript"):
            if self.ignore_depth > 0:
                self.ignore_depth -= 1

        if tag_lower in ("h1", "h2", "h3", "h4", "h5", "h6"):
            h_text = " ".join("".join(self.current_heading_text_parts).split()).lower()
            for disc_phrase in SECONDARY_DISCUSSION_HEADING_KEYWORDS:
                if disc_phrase in h_text:
                    self.secondary_discussion_headings.append(h_text)
                    if not self.found_answer:
                        self.secondary_discussion_before_answer.append(h_text)
                    break
            self.current_heading_tag = None
            self.current_heading_text_parts = []

        if self.in_answer_container and len(self.tag_stack) == self.answer_container_depth:
            self.in_answer_container = False
            if self.first_answer:
                self.first_answer["text"] = " ".join("".join(self.current_answer_text_parts).split())
                self.first_answer["has_widget"] = self.current_answer_has_widget
                self.all_answers_and_widgets.insert(0, self.first_answer)

        if self.tag_stack:
            self.tag_stack.pop()

    def handle_data(self, data: str) -> None:
        if self.in_head or self.in_header or self.in_nav or self.ignore_depth > 0:
            return

        text = data.strip()
        if not text:
            return

        words = text.split()
        word_count = len(words)

        if self.current_heading_tag:
            self.current_heading_text_parts.append(text)

        if self.in_answer_container:
            self.current_answer_text_parts.append(text)
        else:
            if not self.found_answer:
                self.cumulative_body_words += word_count

        self.total_body_words += word_count

    def _is_direct_answer(self, tag: str, attrs: Dict[str, str]) -> bool:
        tag_id = attrs.get("id", "").lower()
        tag_cls = attrs.get("class", "").lower()
        data_role = attrs.get("data-role", "").lower()

        for kw in ANSWER_CONTAINER_CLASS_KEYWORDS:
            if kw in tag_cls or kw in tag_id:
                return True

        if data_role in ("answer", "direct-answer", "quick-answer", "core-answer", "featured-answer"):
            return True

        for attr in attrs:
            if attr in ("data-answer", "data-direct-answer", "data-quick-answer", "data-answer-prominence", "data-answer-block"):
                return True

        return False

    def _is_calculation_widget(self, tag: str, attrs: Dict[str, str]) -> bool:
        tag_id = attrs.get("id", "").lower()
        tag_cls = attrs.get("class", "").lower()
        data_widget = attrs.get("data-widget", "").lower()
        data_role = attrs.get("data-role", "").lower()

        if data_widget in ("calculator", "calc", "calculation") or data_role in ("calculator", "calculation-widget", "calc-widget"):
            return True

        for attr in attrs:
            if attr in ("data-calculation-widget", "data-calc-widget", "data-calculator", "data-calculation-manifest"):
                return True

        for kw in CALCULATION_WIDGET_CLASS_KEYWORDS:
            if kw in tag_cls or kw in tag_id:
                return True

        if tag == "form":
            return True

        return False


def extract_answer_prominence_metadata(content: str) -> Dict[str, Any]:
    """
    Extracts structural answer prominence metadata for Factor 11:
    Cumulative body words before answer, answer type, presence, and above-the-fold status.
    Zero em-dashes. Zero en-dashes.
    """
    if not content or not isinstance(content, str):
        return {
            "has_answer_or_widget": False,
            "answer_found": False,
            "answer_type": "none",
            "answer_tag": "",
            "answer_word_position": -1,
            "total_body_words": 0,
            "answer_text": "",
            "is_above_fold": False,
            "has_secondary_discussion_before_answer": False,
            "secondary_discussion_headings_before_answer": [],
            "all_answers_and_widgets": [],
            "dom_depth": 0,
        }

    parser = _AnswerProminenceParser()
    parser.feed(content)

    fa = parser.first_answer
    if fa:
        w_pos = fa["word_position"]
        is_above = (w_pos <= ANSWER_PROMINENCE_MAX_WORD_COUNT)
        return {
            "has_answer_or_widget": True,
            "answer_found": True,
            "answer_type": fa["type"],
            "answer_tag": fa["tag"],
            "answer_word_position": w_pos,
            "total_body_words": parser.total_body_words,
            "answer_text": fa["text"],
            "is_above_fold": is_above,
            "has_secondary_discussion_before_answer": bool(parser.secondary_discussion_before_answer),
            "secondary_discussion_headings_before_answer": parser.secondary_discussion_before_answer,
            "all_answers_and_widgets": parser.all_answers_and_widgets,
            "dom_depth": fa["dom_depth"],
        }

    return {
        "has_answer_or_widget": False,
        "answer_found": False,
        "answer_type": "none",
        "answer_tag": "",
        "answer_word_position": -1,
        "total_body_words": parser.total_body_words,
        "answer_text": "",
        "is_above_fold": False,
        "has_secondary_discussion_before_answer": bool(parser.secondary_discussion_before_answer),
        "secondary_discussion_headings_before_answer": parser.secondary_discussion_before_answer,
        "all_answers_and_widgets": [],
        "dom_depth": 0,
    }


def detect_answer_prominence_issues(
    content: str,
    rel_path: str = "index.html",
    max_words: int = ANSWER_PROMINENCE_MAX_WORD_COUNT,
    require_strict: bool = False,
) -> List[str]:
    """
    Detects answer prominence violations for Factor 11:
    1. Zero em-dashes and zero en-dashes.
    2. Missing direct answer container or core calculation widget.
    3. Direct answer or calculation widget delayed past max_words threshold (default 300 words).
    4. Direct answer container is empty or lacks substantive content.
    5. Secondary discussion appears before direct answer or calculation widget.
    Zero em-dashes. Zero en-dashes.
    """
    issues: List[str] = []
    if not content or not isinstance(content, str):
        return issues

    if "\u2014" in content:
        issues.append(f"Page {rel_path}: Document contains forbidden em-dash")
    if "\u2013" in content:
        issues.append(f"Page {rel_path}: Document contains forbidden en-dash")

    meta = extract_answer_prominence_metadata(content)

    if not meta["answer_found"]:
        issues.append(
            f"Page {rel_path}: Answer prominence violation: missing direct answer or core calculation widget "
            f"above the fold within the first {max_words} words"
        )
        return issues

    w_pos = meta["answer_word_position"]
    if w_pos > max_words:
        issues.append(
            f"Page {rel_path}: Answer prominence violation: {meta['answer_type'].replace('_', ' ')} appears at "
            f"word position {w_pos}, exceeding maximum threshold of {max_words} words (delayed past fold)"
        )

    if meta["has_secondary_discussion_before_answer"]:
        disc_hdg = meta["secondary_discussion_headings_before_answer"][0]
        issues.append(
            f"Page {rel_path}: Answer prominence violation: secondary discussion ('{disc_hdg}') appears "
            f"before direct answer or calculation widget"
        )

    if meta["answer_type"] == "direct_answer":
        if not meta["answer_text"].strip():
            issues.append(
                f"Page {rel_path}: Answer prominence violation: direct answer container is empty or lacks substantive content"
            )

    return issues


def assert_answer_word_position(
    content: str,
    max_words: int = ANSWER_PROMINENCE_MAX_WORD_COUNT,
    context: str = "",
) -> bool:
    """
    Contract assertion verifying cumulative body word position of direct answer
    or calculation widget does not exceed max_words boundary (300 words).
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    if not isinstance(content, str):
        raise ValueError(f"Content must be a string{ctx}")

    assert_no_forbidden_dashes(content, context=context)
    meta = extract_answer_prominence_metadata(content)
    if not meta["answer_found"]:
        raise ValueError(
            f"Answer prominence violation{ctx}: missing direct answer or core calculation widget"
        )
    if meta["answer_word_position"] > max_words:
        raise ValueError(
            f"Answer prominence violation{ctx}: answer appears at word position "
            f"{meta['answer_word_position']} > {max_words} words limit"
        )
    return True


def assert_direct_answer_or_widget_presence(
    content: str,
    context: str = "",
) -> bool:
    """
    Contract assertion verifying the presence of a direct answer container or core calculation widget.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    if not isinstance(content, str):
        raise ValueError(f"Content must be a string{ctx}")

    assert_no_forbidden_dashes(content, context=context)
    meta = extract_answer_prominence_metadata(content)
    if not meta["answer_found"]:
        raise ValueError(
            f"Answer prominence violation{ctx}: missing direct answer or core calculation widget"
        )
    return True


def assert_answer_above_the_fold(
    content: str,
    max_words: int = ANSWER_PROMINENCE_MAX_WORD_COUNT,
    context: str = "",
) -> bool:
    """
    Contract assertion verifying direct answer or calculation widget appears above the fold.
    Zero em-dashes. Zero en-dashes.
    """
    return assert_answer_word_position(content, max_words=max_words, context=context)


def assert_answer_prominence(
    content: str,
    max_words: int = ANSWER_PROMINENCE_MAX_WORD_COUNT,
    require_strict: bool = False,
    context: str = "",
) -> bool:
    """
    Comprehensive contract assertion for Factor 11: Answer Prominence (+1.65).
    Ensures pages place the direct answer or core calculation widget above the fold
    within the first 300 words of the body before secondary discussion.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    if not isinstance(content, str):
        raise ValueError(f"Content must be a string{ctx}")

    assert_no_forbidden_dashes(content, context=context)
    issues = detect_answer_prominence_issues(
        content,
        rel_path=context or "index.html",
        max_words=max_words,
        require_strict=require_strict,
    )
    if issues:
        raise ValueError(f"Answer prominence contract violation{ctx}: {issues[0]}")
    return True


assert_answer_above_fold = assert_answer_prominence
assert_core_answer_prominence = assert_answer_prominence
assert_direct_answer_prominence = assert_answer_prominence
assert_calculation_widget_prominence = assert_answer_prominence
assert_early_answer_block = assert_answer_prominence


# =============================================================================
# Factor 12: Structured Data (+0.80) Contracts & Enforcements
# =============================================================================

TARGET_ENTITY_SCHEMAS: Set[str] = {
    "SoftwareApplication",
    "WebApplication",
    "Product",
    "FAQPage",
    "HowTo",
    "Dataset",
}

SUPPORTED_AUXILIARY_SCHEMAS: Set[str] = {
    "Organization",
    "NewsMediaOrganization",
    "Corporation",
    "EducationalOrganization",
    "GovernmentOrganization",
    "Person",
    "LocalBusiness",
    "FinancialService",
    "FinancialProduct",
    "ProfessionalService",
    "GeoCoordinates",
    "OpeningHoursSpecification",
    "Offer",
    "OfferCatalog",
    "AggregateOffer",
    "AggregateRating",
    "Rating",
    "Review",
    "Service",
    "Question",
    "Answer",
    "HowToStep",
    "HowToSection",
    "HowToDirection",
    "HowToTip",
    "HowToSupply",
    "HowToTool",
    "DataDownload",
    "DataCatalog",
    "PropertyValue",
    "WebSite",
    "WebPage",
    "ItemPage",
    "AboutPage",
    "ContactPage",
    "BreadcrumbList",
    "ListItem",
    "PostalAddress",
    "ContactPoint",
    "ImageObject",
    "SpeakableSpecification",
    "Article",
    "TechArticle",
    "NewsArticle",
    "BlogPosting",
    "SearchAction",
    "MonetaryAmount",
    "QuantitativeValue",
    "Country",
    "State",
    "AdministrativeArea",
    "City",
    "Place",
}

ALL_REGISTERED_SCHEMAS: Set[str] = TARGET_ENTITY_SCHEMAS | SUPPORTED_AUXILIARY_SCHEMAS

LEAF_ENTITY_SCHEMAS: Set[str] = {
    "Question",
    "Answer",
    "HowToStep",
    "HowToSection",
    "HowToDirection",
    "HowToTip",
    "HowToSupply",
    "HowToTool",
    "Offer",
    "AggregateOffer",
    "AggregateRating",
    "Rating",
    "Review",
    "DataDownload",
    "PropertyValue",
    "ListItem",
    "ContactPoint",
    "PostalAddress",
}

SCHEMA_ORG_CONTEXT_PATTERN = re.compile(
    r"^https?://schema\.org/?$",
    re.IGNORECASE,
)


def extract_structured_data_metadata(content: Any) -> Dict[str, Any]:
    """
    Extracts structured data metadata for Factor 12:
    JSON-LD blocks, parsed entities, target entities, graph connectivity,
    unanchored leaf entities, broken graph references, and registered schema types.
    Zero em-dashes. Zero en-dashes.
    """
    if content is None:
        return {
            "has_json_ld": False,
            "raw_blocks": [],
            "parsed_graphs": [],
            "entities": [],
            "target_entities": [],
            "schema_types": [],
            "target_schemas_found": [],
            "total_entities": 0,
            "unanchored_leaf_entities": [],
            "broken_references": [],
            "unregistered_schemas": [],
            "parse_errors": ["Content must be a non-empty string or dict/list"],
            "multiple_disconnected_scripts": False,
            "block_contexts": [],
        }

    raw_blocks: List[str] = []
    if isinstance(content, str):
        pattern = re.compile(
            r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            re.IGNORECASE | re.DOTALL,
        )
        matches = pattern.findall(content)
        if matches:
            raw_blocks = [m.strip() for m in matches if m.strip()]
        else:
            stripped = content.strip()
            if stripped.startswith(("{", "[")) and ("schema.org" in stripped or "@type" in stripped):
                raw_blocks = [stripped]
    elif isinstance(content, dict):
        raw_blocks = [json.dumps(content)]
    elif isinstance(content, list):
        raw_blocks = [json.dumps(content)]

    if not raw_blocks:
        return {
            "has_json_ld": False,
            "raw_blocks": [],
            "parsed_graphs": [],
            "entities": [],
            "target_entities": [],
            "schema_types": [],
            "target_schemas_found": [],
            "total_entities": 0,
            "unanchored_leaf_entities": [],
            "broken_references": [],
            "unregistered_schemas": [],
            "parse_errors": [],
            "multiple_disconnected_scripts": False,
            "block_contexts": [],
        }

    parsed_graphs: List[Any] = []
    parse_errors: List[str] = []
    for idx, raw in enumerate(raw_blocks):
        try:
            parsed = json.loads(raw)
            parsed_graphs.append(parsed)
        except Exception as ex:
            parse_errors.append(f"Invalid JSON-LD syntax in block {idx}: {ex}")

    all_entities: List[Dict[str, Any]] = []
    top_level_entities_by_block: List[List[Dict[str, Any]]] = []
    block_contexts: List[Optional[str]] = []

    for block in parsed_graphs:
        current_block_top_entities: List[Dict[str, Any]] = []
        ctx = None
        if isinstance(block, dict):
            ctx = block.get("@context")
            if "@graph" in block and isinstance(block["@graph"], list):
                for item in block["@graph"]:
                    if isinstance(item, dict) and "@type" in item:
                        current_block_top_entities.append(item)
            elif "@type" in block:
                current_block_top_entities.append(block)
        elif isinstance(block, list):
            for item in block:
                if isinstance(item, dict) and "@type" in item:
                    current_block_top_entities.append(item)
                    if "@context" in item and not ctx:
                        ctx = item.get("@context")

        block_contexts.append(str(ctx) if ctx else None)
        top_level_entities_by_block.append(current_block_top_entities)

        def _collect(obj: Any, parent_ref: Optional[Dict[str, Any]] = None, rel_prop: str = ""):
            if isinstance(obj, dict):
                if "@type" in obj:
                    all_entities.append({
                        "entity": obj,
                        "parent": parent_ref,
                        "relational_property": rel_prop,
                    })
                    curr_parent = obj
                else:
                    curr_parent = parent_ref
                for k, v in obj.items():
                    if k in ("@context", "@id"):
                        continue
                    _collect(v, parent_ref=curr_parent, rel_prop=k)
            elif isinstance(obj, (list, tuple)):
                for item in obj:
                    _collect(item, parent_ref=parent_ref, rel_prop=rel_prop)

        _collect(block)

    defined_ids: Set[str] = set()
    for ent_info in all_entities:
        eid = ent_info["entity"].get("@id")
        if eid and isinstance(eid, str):
            defined_ids.add(eid.strip())

    entity_incoming_refs: Dict[int, List[Dict[str, Any]]] = {id(e["entity"]): [] for e in all_entities}
    broken_refs: List[Tuple[str, str]] = []

    id_to_entities: Dict[str, List[Dict[str, Any]]] = {}
    for ent_info in all_entities:
        eid = ent_info["entity"].get("@id")
        if eid and isinstance(eid, str):
            s_eid = eid.strip()
            if s_eid not in id_to_entities:
                id_to_entities[s_eid] = []
            id_to_entities[s_eid].append(ent_info["entity"])

    def _resolve_target_id(target_id: str) -> Optional[str]:
        if target_id in defined_ids:
            return target_id

        # Canonical entity ID aliases: #softwareapplication and #software
        if target_id.endswith("#softwareapplication"):
            prefix = target_id[:-len("#softwareapplication")]
            candidate = prefix + "#software"
            if candidate in defined_ids:
                return candidate
            if "#softwareapplication" in defined_ids:
                return "#softwareapplication"
            if "#software" in defined_ids:
                return "#software"
            for d in defined_ids:
                if d.endswith("#software") or d.endswith("#softwareapplication"):
                    return d
        elif target_id.endswith("#software"):
            prefix = target_id[:-len("#software")]
            candidate = prefix + "#softwareapplication"
            if candidate in defined_ids:
                return candidate
            if "#software" in defined_ids:
                return "#software"
            if "#softwareapplication" in defined_ids:
                return "#softwareapplication"
            for d in defined_ids:
                if d.endswith("#softwareapplication") or d.endswith("#software"):
                    return d

        return None

    for ent_info in all_entities:
        ent = ent_info["entity"]
        ent_type = ent.get("@type", "Entity")
        for prop, val in ent.items():
            if prop in ("@context", "@type", "@id"):
                continue

            def _find_id_refs(v: Any):
                if isinstance(v, dict):
                    if "@id" in v and isinstance(v["@id"], str):
                        target_id = v["@id"].strip()
                        resolved_id = _resolve_target_id(target_id)
                        if resolved_id:
                            for target_ent in id_to_entities.get(resolved_id, []):
                                entity_incoming_refs[id(target_ent)].append(ent)
                        else:
                            if prop not in ("sameAs", "url", "isBasedOn", "citation") and ("#" in target_id or not target_id.startswith("http")):
                                broken_refs.append((str(ent_type), target_id))
                    for sub_v in v.values():
                        _find_id_refs(sub_v)
                elif isinstance(v, (list, tuple)):
                    for item in v:
                        _find_id_refs(item)

            _find_id_refs(val)

    unanchored_leaves: List[str] = []
    for ent_info in all_entities:
        ent = ent_info["entity"]
        stype = ent.get("@type")
        types = [stype] if isinstance(stype, str) else (stype if isinstance(stype, list) else [])
        for t in types:
            if t in LEAF_ENTITY_SCHEMAS:
                if ent_info["parent"] is not None:
                    continue
                incoming = entity_incoming_refs.get(id(ent), [])
                if incoming:
                    continue
                has_parent_link = False
                for parent_prop in ("parentItem", "isPartOf", "itemReviewed", "targetProduct"):
                    pval = ent.get(parent_prop)
                    ref_id = None
                    if isinstance(pval, dict) and isinstance(pval.get("@id"), str):
                        ref_id = pval.get("@id").strip()
                    elif isinstance(pval, str):
                        ref_id = pval.strip()
                    if ref_id and _resolve_target_id(ref_id) is not None:
                        has_parent_link = True
                        break
                if has_parent_link:
                    continue
                unanchored_leaves.append(t)

    unregistered_schemas: List[str] = []
    schema_types: List[str] = []
    target_schemas_found: List[str] = []

    for ent_info in all_entities:
        stype = ent_info["entity"].get("@type")
        types = [stype] if isinstance(stype, str) else (stype if isinstance(stype, list) else [])
        for t in types:
            if isinstance(t, str):
                schema_types.append(t)
                if t in TARGET_ENTITY_SCHEMAS:
                    target_schemas_found.append(t)
                if t not in ALL_REGISTERED_SCHEMAS:
                    unregistered_schemas.append(t)

    multiple_disconnected = False
    if len(top_level_entities_by_block) > 1:
        block_ids: List[Set[str]] = []
        block_refs: List[Set[str]] = []
        for blk_ents in top_level_entities_by_block:
            b_ids = set()
            b_refs = set()
            for e in blk_ents:
                if e.get("@id"):
                    b_ids.add(str(e["@id"]).strip())

                def _scan_refs(v):
                    if isinstance(v, dict):
                        if "@id" in v and isinstance(v["@id"], str):
                            b_refs.add(v["@id"].strip())
                        for sv in v.values():
                            _scan_refs(sv)
                    elif isinstance(v, (list, tuple)):
                        for sv in v:
                            _scan_refs(sv)

                _scan_refs(e)
            block_ids.append(b_ids)
            block_refs.append(b_refs)

        connected = False
        for i in range(len(block_ids)):
            for j in range(len(block_ids)):
                if i != j:
                    if block_refs[i].intersection(block_ids[j]):
                        connected = True
                        break
            if connected:
                break
        if not connected:
            multiple_disconnected = True

    return {
        "has_json_ld": len(raw_blocks) > 0,
        "raw_blocks": raw_blocks,
        "parsed_graphs": parsed_graphs,
        "entities": [e["entity"] for e in all_entities],
        "target_entities": [e["entity"] for e in all_entities if any(t in TARGET_ENTITY_SCHEMAS for t in ([e["entity"].get("@type")] if isinstance(e["entity"].get("@type"), str) else e["entity"].get("@type", [])))],
        "schema_types": schema_types,
        "target_schemas_found": target_schemas_found,
        "total_entities": len(all_entities),
        "unanchored_leaf_entities": unanchored_leaves,
        "broken_references": broken_refs,
        "unregistered_schemas": unregistered_schemas,
        "parse_errors": parse_errors,
        "multiple_disconnected_scripts": multiple_disconnected,
        "block_contexts": block_contexts,
    }


def detect_structured_data_issues(
    content: str,
    rel_path: str = "index.html",
    require_strict: bool = False,
    allowed_schemas: Optional[Set[str]] = None,
) -> List[str]:
    """
    Detects structured data violations for Factor 12:
    1. Zero em-dashes and zero en-dashes.
    2. JSON-LD syntax parse errors.
    3. Missing Schema.org JSON-LD structured data.
    4. Missing or invalid Schema.org @context.
    5. Unregistered schema types.
    6. Unanchored leaf entities floating disconnectedly without relational parent linkage.
    7. Broken graph references to unresolved @ids.
    8. Multiple disconnected application/ld+json script tags.
    9. Malformed target entity schemas across SoftwareApplication, WebApplication,
       Product, FAQPage, HowTo, and Dataset.
    Zero em-dashes. Zero en-dashes.
    """
    issues: List[str] = []
    if content is None or not isinstance(content, str):
        issues.append(f"Page {rel_path}: HTML content must be a valid non-empty string")
        return issues

    # 1. Strict anti-slop check
    if "\u2014" in content:
        issues.append(f"Page {rel_path}: Document contains forbidden em-dash")
    if "\u2013" in content:
        issues.append(f"Page {rel_path}: Document contains forbidden en-dash")

    meta = extract_structured_data_metadata(content)

    # 2. JSON-LD existence
    if not meta["has_json_ld"]:
        issues.append(
            f"Page {rel_path}: Missing Schema.org JSON-LD structured data (<script type='application/ld+json'> not found)"
        )
        return issues

    # 3. Parse errors
    for pe in meta["parse_errors"]:
        issues.append(f"Page {rel_path}: {pe}")
    if meta["parse_errors"]:
        return issues

    # 4. Context validation
    for ctx in meta.get("block_contexts", []):
        if not ctx or not SCHEMA_ORG_CONTEXT_PATTERN.search(str(ctx).strip()):
            issues.append(
                f"Page {rel_path}: Missing or invalid @context in JSON-LD (must be 'https://schema.org')"
            )
            break

    # 5. Multiple disconnected script tags
    if meta.get("multiple_disconnected_scripts"):
        issues.append(
            f"Page {rel_path}: Multiple disconnected application/ld+json script tags detected; consolidate schema definitions into a unified graph"
        )

    # 6. Unregistered schema types
    for unreg in meta.get("unregistered_schemas", []):
        issues.append(
            f"Page {rel_path}: Unregistered schema type '{unreg}' detected in structured data markup"
        )

    # 7. Unanchored leaf entities
    for leaf in meta.get("unanchored_leaf_entities", []):
        issues.append(
            f"Page {rel_path}: Unanchored leaf entity '{leaf}' floats disconnectedly without relational parent linkage"
        )

    # 8. Broken graph references
    for src_type, target_id in meta.get("broken_references", []):
        issues.append(
            f"Page {rel_path}: Broken graph reference in '{src_type}': references unresolved @id '{target_id}' without parent relationship"
        )

    # 9. Target entity schema specific validation
    target_entities = meta.get("target_entities", [])
    if not target_entities and require_strict:
        expected = sorted(allowed_schemas or TARGET_ENTITY_SCHEMAS)
        issues.append(
            f"Page {rel_path}: Missing target entity schema: structured data must supply at least one of {expected}"
        )
    elif target_entities:
        for ent in target_entities:
            stype = ent.get("@type")
            types = [stype] if isinstance(stype, str) else (stype if isinstance(stype, list) else [])
            for t in types:
                if t == "SoftwareApplication":
                    name = str(ent.get("name", "")).strip()
                    if not name:
                        issues.append(f"Page {rel_path}: Invalid SoftwareApplication schema: missing or empty 'name'")
                    has_spec = any(ent.get(k) for k in ("operatingSystem", "applicationCategory", "offers", "aggregateRating", "softwareVersion", "description"))
                    if not has_spec:
                        issues.append(f"Page {rel_path}: Invalid SoftwareApplication schema: must specify 'operatingSystem', 'applicationCategory', or 'offers'")

                elif t == "WebApplication":
                    name = str(ent.get("name", "")).strip()
                    if not name:
                        issues.append(f"Page {rel_path}: Invalid WebApplication schema: missing or empty 'name'")
                    has_spec = any(ent.get(k) for k in ("applicationCategory", "operatingSystem", "browserRequirements", "offers", "aggregateRating", "description"))
                    if not has_spec:
                        issues.append(f"Page {rel_path}: Invalid WebApplication schema: must specify 'applicationCategory', 'operatingSystem', or 'browserRequirements'")

                elif t == "Product":
                    name = str(ent.get("name", "")).strip()
                    if not name:
                        issues.append(f"Page {rel_path}: Invalid Product schema: missing or empty 'name'")
                    has_spec = any(ent.get(k) for k in ("description", "offers", "aggregateRating", "brand", "sku"))
                    if not has_spec:
                        issues.append(f"Page {rel_path}: Invalid Product schema: must specify 'description', 'offers', 'brand', or 'aggregateRating'")

                elif t == "FAQPage":
                    main_ent = ent.get("mainEntity")
                    if not main_ent:
                        issues.append(f"Page {rel_path}: Invalid FAQPage schema: missing or empty 'mainEntity' (must contain Question entities)")
                    else:
                        q_list = main_ent if isinstance(main_ent, list) else [main_ent]
                        for q in q_list:
                            if not isinstance(q, dict):
                                issues.append(f"Page {rel_path}: Invalid Question in FAQPage: must be an object")
                                continue
                            q_text = str(q.get("name") or q.get("text") or "").strip()
                            ans = q.get("acceptedAnswer")
                            ans_text = ""
                            if isinstance(ans, dict):
                                ans_text = str(ans.get("text", "")).strip()
                            elif isinstance(ans, str):
                                ans_text = ans.strip()
                            if not q_text or not ans_text:
                                issues.append(f"Page {rel_path}: Invalid Question in FAQPage: must define question text and acceptedAnswer with answer text")

                elif t == "HowTo":
                    name = str(ent.get("name", "")).strip()
                    if not name:
                        issues.append(f"Page {rel_path}: Invalid HowTo schema: missing or empty 'name'")
                    steps = ent.get("step") or ent.get("itemListElement")
                    if not steps:
                        issues.append(f"Page {rel_path}: Invalid HowTo schema: missing or empty 'step' (must contain procedural steps)")
                    else:
                        s_list = steps if isinstance(steps, list) else [steps]
                        if not s_list:
                            issues.append(f"Page {rel_path}: Invalid HowTo schema: 'step' list is empty")

                elif t == "Dataset":
                    name = str(ent.get("name", "")).strip()
                    if not name:
                        issues.append(f"Page {rel_path}: Invalid Dataset schema: missing or empty 'name'")
                    desc = str(ent.get("description", "")).strip()
                    if not desc:
                        issues.append(f"Page {rel_path}: Invalid Dataset schema: missing or empty 'description'")

    return issues


def assert_structured_data(
    content: str,
    require_strict: bool = False,
    allowed_schemas: Optional[Set[str]] = None,
    context: str = "",
) -> bool:
    """
    Contract assertion validating Factor 12: Structured Data (+0.80).
    Ensures pages supply machine-readable Schema.org JSON-LD markup validating
    SoftwareApplication, WebApplication, Product, FAQPage, HowTo, and Dataset schemas
    with zero parse errors, connected graph structures, zero unanchored leaves,
    and zero forbidden dashes.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    if not isinstance(content, str):
        raise ValueError(f"Content must be a string{ctx}")

    assert_no_forbidden_dashes(content, context=context)
    issues = detect_structured_data_issues(
        content,
        rel_path=context or "index.html",
        require_strict=require_strict,
        allowed_schemas=allowed_schemas,
    )
    if issues:
        raise ValueError(f"Structured data contract violation{ctx}: {issues[0]}")
    return True


assert_valid_structured_data = assert_structured_data
assert_machine_readable_schema = assert_structured_data
assert_schema_org_jsonld = assert_structured_data
assert_schema_graph_structure = assert_structured_data


def assert_target_entity_schemas(
    content: str,
    allowed_types: Optional[Set[str]] = None,
    context: str = "",
) -> bool:
    """
    Contract assertion verifying the presence of at least one valid target entity schema
    (SoftwareApplication, WebApplication, Product, FAQPage, HowTo, Dataset).
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    if not isinstance(content, str):
        raise ValueError(f"Content must be a string{ctx}")

    assert_structured_data(
        content,
        require_strict=True,
        allowed_schemas=allowed_types or TARGET_ENTITY_SCHEMAS,
        context=context,
    )
    meta = extract_structured_data_metadata(content)
    target_schemas = meta.get("target_schemas_found", [])
    valid_targets = (allowed_types or TARGET_ENTITY_SCHEMAS)
    if not any(t in valid_targets for t in target_schemas):
        raise ValueError(
            f"No target entity schema found in structured data{ctx}; expected one of {sorted(valid_targets)}"
        )
    return True


def assert_schema_graph_connectivity(
    content: str,
    context: str = "",
) -> bool:
    """
    Contract assertion verifying Schema.org graph connectivity:
    1. Zero unanchored leaf entities floating disconnectedly.
    2. Zero broken graph references to unresolved @ids.
    3. Zero disconnected multiple script tags.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    if not isinstance(content, str):
        raise ValueError(f"Content must be a string{ctx}")

    assert_no_forbidden_dashes(content, context=context)
    meta = extract_structured_data_metadata(content)
    if meta.get("parse_errors"):
        raise ValueError(f"JSON-LD parse error{ctx}: {meta['parse_errors'][0]}")
    if meta.get("multiple_disconnected_scripts"):
        raise ValueError(
            f"Schema graph connectivity violation{ctx}: multiple disconnected application/ld+json script tags detected"
        )
    if meta.get("unanchored_leaf_entities"):
        raise ValueError(
            f"Schema graph connectivity violation{ctx}: unanchored leaf entity '{meta['unanchored_leaf_entities'][0]}' floats disconnectedly"
        )
    if meta.get("broken_references"):
        src, tid = meta["broken_references"][0]
        raise ValueError(
            f"Schema graph connectivity violation{ctx}: broken graph reference in '{src}' to unresolved @id '{tid}'"
        )
    return True


# =============================================================================
# Factor 13: llms.txt File (+0.05) Contracts & Parsing Engine
# =============================================================================

LLMS_TXT_DISALLOWED_ROUTE_PATTERNS: List[re.Pattern] = [
    re.compile(r'/admin(?:istrator)?(?:/|[?#\s]|$)', re.IGNORECASE),
    re.compile(r'/internal(?:/|[?#\s]|$)', re.IGNORECASE),
    re.compile(r'/private(?:/|[?#\s]|$)', re.IGNORECASE),
    re.compile(r'/api/(?:internal|admin|private|debug|metrics|v1/internal)(?:/|[?#\s]|$)', re.IGNORECASE),
    re.compile(r'/(?:staging|tests?|__tests__|signal|syndication)(?:/|[?#\s]|$)', re.IGNORECASE),
    re.compile(r'/(?:auth|login|signin|signup|logout|dashboard|backend|console)(?:/|[?#\s]|$)', re.IGNORECASE),
    re.compile(r'/(?:tmp|temp|drafts?|secrets?)(?:/|[?#\s]|$)', re.IGNORECASE),
    re.compile(r'/(?:debug|metrics|healthz|server-status|cgi-bin|wp-admin)(?:/|[?#\s]|$)', re.IGNORECASE),
    re.compile(r'(?:https?://)?(?:localhost|127\.0\.0\.1|0\.0\.0\.0)(?::\d+)?(?:/|[?#\s]|$)', re.IGNORECASE),
    re.compile(r'(?:token=|apiKey=|api_key=|secret=|password=)', re.IGNORECASE),
    re.compile(r'(?:file://|/(?:home|etc|var|usr)/)', re.IGNORECASE),
]

LLMS_TXT_HUB_HEADING_PATTERNS: List[re.Pattern] = [
    re.compile(r'^##\s+(?:top\s+category\s+hubs?|category\s+hubs?|hubs?|categories|core\s+resources|key\s+hubs?|tax\s+hubs?|calculation\s+hubs?)(?:\s|$)', re.IGNORECASE),
]


def extract_llms_txt_metadata(content: str) -> Dict[str, Any]:
    """
    Parses and extracts structural metadata from an llms.txt or llms-full.txt file.
    Extracts H1 title, blockquote summary, sections (H2), links with descriptions,
    top category hub links, leaked internal routes, and forbidden dash detections.
    Zero em-dashes. Zero en-dashes.
    """
    if not isinstance(content, str):
        return {
            "has_h1": False,
            "title": "",
            "has_blockquote": False,
            "summary": "",
            "sections": [],
            "links": [],
            "category_hubs": [],
            "leaked_routes": [],
            "forbidden_dashes": [],
            "is_llmstxt_compliant": False,
            "total_links": 0,
            "total_hubs": 0,
        }

    forbidden_dashes = []
    if "\u2014" in content:
        forbidden_dashes.append("em-dash (U+2014)")
    if "\u2013" in content:
        forbidden_dashes.append("en-dash (U+2013)")

    lines = content.splitlines()
    title = ""
    blockquote_lines = []
    sections: List[Dict[str, Any]] = []
    current_section: Optional[Dict[str, Any]] = None
    all_links: List[Dict[str, Any]] = []
    category_hubs: List[Dict[str, Any]] = []
    leaked_routes: List[str] = []

    for pattern in LLMS_TXT_DISALLOWED_ROUTE_PATTERNS:
        for match in pattern.finditer(content):
            leaked_routes.append(match.group(0).strip())

    in_blockquote = False
    saw_h1 = False

    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            if in_blockquote:
                in_blockquote = False
            continue

        if line.startswith("# ") and not line.startswith("## ") and not saw_h1:
            title = line[2:].strip()
            saw_h1 = True
            continue

        if line.startswith(">"):
            in_blockquote = True
            bq_text = line[1:].strip()
            if bq_text:
                blockquote_lines.append(bq_text)
            continue
        elif in_blockquote:
            if not line.startswith("#") and not line.startswith("-") and not line.startswith("*"):
                blockquote_lines.append(line)
            else:
                in_blockquote = False

        if line.startswith("## "):
            sec_heading = line[3:].strip()
            is_hub_sec = any(p.match(line) for p in LLMS_TXT_HUB_HEADING_PATTERNS)
            current_section = {
                "heading": sec_heading,
                "is_category_hub_section": is_hub_sec,
                "links": [],
            }
            sections.append(current_section)
            continue

        link_match = re.match(r'^[ \t]*[-*][ \t]+\[([^\]]+)\]\(([^)]+)\)(?:[ \t]*:[ \t]*(.+))?$', line)
        if link_match:
            l_title = link_match.group(1).strip()
            l_url = link_match.group(2).strip()
            l_summary = (link_match.group(3) or "").strip()

            if not l_summary and idx + 1 < len(lines):
                next_line = lines[idx + 1]
                if (next_line.startswith("  ") or next_line.startswith("\t")) and not next_line.strip().startswith("-") and not next_line.strip().startswith("*"):
                    l_summary = next_line.strip()

            link_info = {
                "title": l_title,
                "url": l_url,
                "summary": l_summary,
                "section": current_section["heading"] if current_section else "",
                "is_hub": current_section.get("is_category_hub_section", False) if current_section else False,
            }
            all_links.append(link_info)
            if current_section:
                current_section["links"].append(link_info)
            if link_info["is_hub"]:
                category_hubs.append(link_info)

    if not category_hubs:
        for l in all_links:
            sec_lower = l["section"].lower()
            if any(k in sec_lower for k in ("hub", "categor", "tool", "topic", "resource")):
                l["is_hub"] = True
                category_hubs.append(l)

    blockquote_summary = " ".join(blockquote_lines).strip()
    is_compliant = bool(
        title
        and blockquote_summary
        and sections
        and all_links
        and not leaked_routes
        and not forbidden_dashes
    )

    return {
        "has_h1": bool(title),
        "title": title,
        "has_blockquote": bool(blockquote_summary),
        "summary": blockquote_summary,
        "sections": sections,
        "links": all_links,
        "category_hubs": category_hubs,
        "leaked_routes": sorted(list(set(leaked_routes))),
        "forbidden_dashes": forbidden_dashes,
        "is_llmstxt_compliant": is_compliant,
        "total_links": len(all_links),
        "total_hubs": len(category_hubs),
    }


def detect_llms_txt_issues(
    content: str,
    rel_path: str = "llms.txt",
    is_full: bool = False,
    require_strict: bool = False,
) -> List[str]:
    """
    Detects contract and specification issues in an llms.txt or llms-full.txt file.
    Enforces llmstxt.org specification compliance:
    1. Zero em-dashes and zero en-dashes.
    2. H1 project/site title presence.
    3. Blockquote summary immediately following H1 (for llms.txt).
    4. Top category hubs include concise markdown summaries.
    5. Zero exposure or leaking of private administrative routes or internal paths.
    6. Zero prompt leakage terms or forbidden jargon.
    Zero em-dashes. Zero en-dashes.
    """
    issues: List[str] = []
    if not isinstance(content, str):
        return [f"{rel_path}: Content must be a string"]

    if not content.strip():
        return [f"{rel_path}: Content is empty"]

    if "\u2014" in content:
        issues.append(f"{rel_path}: Document contains forbidden em-dash")
    if "\u2013" in content:
        issues.append(f"{rel_path}: Document contains forbidden en-dash")

    for term in PROMPT_LEAKAGE_TERMS:
        if term.lower() in content.lower():
            issues.append(f"{rel_path}: Prompt leakage detected: '{term}'")
    for jargon in FORBIDDEN_JARGON:
        if re.search(r'\b' + re.escape(jargon) + r'\b', content, re.IGNORECASE):
            issues.append(f"{rel_path}: Forbidden jargon detected: '{jargon}'")

    meta = extract_llms_txt_metadata(content)

    if meta.get("leaked_routes"):
        for rk in meta["leaked_routes"]:
            issues.append(f"{rel_path}: Disallowed internal route or private path leaked: '{rk}'")

    for link in meta.get("links", []):
        url = link.get("url", "")
        for pat in LLMS_TXT_DISALLOWED_ROUTE_PATTERNS:
            if pat.search(url):
                issue_msg = f"{rel_path}: Disallowed internal route leaked in link target: '{url}'"
                if issue_msg not in issues:
                    issues.append(issue_msg)

    if not meta.get("has_h1"):
        issues.append(f"{rel_path}: Missing required H1 project title ('# <Title>')")

    if not is_full:
        if not meta.get("has_blockquote"):
            issues.append(f"{rel_path}: Missing required blockquote summary ('> <Summary>')")

        if not meta.get("sections"):
            issues.append(f"{rel_path}: Missing required markdown sections (expected at least one '## <Section>')")

        if not meta.get("links"):
            issues.append(f"{rel_path}: Missing required markdown links")

        hubs = meta.get("category_hubs", [])
        if require_strict and not hubs:
            issues.append(f"{rel_path}: No top category hubs found in manifest")

        for hub in hubs:
            summary = hub.get("summary", "").strip()
            if not summary:
                issues.append(
                    f"{rel_path}: Top category hub '{hub.get('title')}' is missing a concise markdown summary"
                )
            elif len(summary) > 500:
                issues.append(
                    f"{rel_path}: Top category hub '{hub.get('title')}' summary exceeds 500 characters ({len(summary)} chars)"
                )
    else:
        if len(content.strip()) < 20:
            issues.append(f"{rel_path}: Expanded llms-full.txt content is too short (< 20 characters)")

    return issues


def assert_llms_txt(
    content: str,
    is_full: bool = False,
    require_strict: bool = True,
    context: str = "",
) -> bool:
    """
    Contract assertion validating llms.txt or llms-full.txt against llmstxt.org specification.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    if not isinstance(content, str):
        raise ValueError(f"Content must be a string{ctx}")

    issues = detect_llms_txt_issues(
        content,
        rel_path=context or ("llms-full.txt" if is_full else "llms.txt"),
        is_full=is_full,
        require_strict=require_strict,
    )
    if issues:
        raise ValueError(f"llms.txt contract violation{ctx}: {'; '.join(issues)}")
    return True


def assert_llms_txt_specification(
    content: str,
    is_full: bool = False,
    context: str = "",
) -> bool:
    return assert_llms_txt(content, is_full=is_full, require_strict=True, context=context)


def assert_llms_txt_compliance(
    content: str,
    context: str = "",
) -> bool:
    return assert_llms_txt(content, is_full=False, require_strict=True, context=context)


def assert_llms_full_txt_compliance(
    content: str,
    context: str = "",
) -> bool:
    return assert_llms_txt(content, is_full=True, require_strict=True, context=context)


def assert_no_internal_route_leaks(
    content: str,
    context: str = "",
) -> bool:
    """
    Contract assertion verifying zero exposure or leaking of private administrative
    routes or internal paths.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    if not isinstance(content, str):
        raise ValueError(f"Content must be a string{ctx}")

    assert_no_forbidden_dashes(content, context=context)
    leaked = []
    for pat in LLMS_TXT_DISALLOWED_ROUTE_PATTERNS:
        for m in pat.finditer(content):
            leaked.append(m.group(0).strip())

    if leaked:
        unique_leaked = sorted(list(set(leaked)))
        raise ValueError(
            f"Internal route leak violation{ctx}: disallowed routes leaked: {', '.join(unique_leaked)}"
        )
    return True


def assert_top_category_hubs_summaries(
    content: str,
    context: str = "",
) -> bool:
    """
    Contract assertion verifying that top category hubs include concise markdown summaries.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    if not isinstance(content, str):
        raise ValueError(f"Content must be a string{ctx}")

    assert_no_forbidden_dashes(content, context=context)
    meta = extract_llms_txt_metadata(content)
    hubs = meta.get("category_hubs", [])
    if not hubs:
        raise ValueError(f"Top category hubs violation{ctx}: no category hubs found in manifest")

    missing_summaries = []
    for hub in hubs:
        if not hub.get("summary", "").strip():
            missing_summaries.append(hub.get("title", "Unknown"))

    if missing_summaries:
        raise ValueError(
            f"Top category hubs violation{ctx}: hubs missing concise markdown summaries: {', '.join(missing_summaries)}"
        )
    return True


def assert_llms_manifest_pair(
    llms_txt_content: str,
    llms_full_txt_content: str,
    context: str = "",
) -> bool:
    """
    Contract assertion validating a paired curated llms.txt and expanded llms-full.txt manifest.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    assert_llms_txt_compliance(llms_txt_content, context=f"llms.txt{ctx}")
    assert_llms_full_txt_compliance(llms_full_txt_content, context=f"llms-full.txt{ctx}")
    return True


assert_llms_txt_file = assert_llms_txt
assert_curated_llms_txt = assert_llms_txt


# =============================================================================
# Free Interactive Tools Contracts & Operational Shields
# =============================================================================

class ToolUtilityHTMLParser(HTMLParser):
    """
    HTML parser evaluating ToolUtilityContract requirements:
    1. Interactive form or container presence (<form> or role='form' or container with inputs and submit CTA).
    2. Input accessibility: all non-hidden inputs paired with <label for=id>, aria-label, or nested in <label>.
    3. Dedicated submit CTA (<button type='submit'> or equivalent).
    Zero em-dashes. Zero en-dashes.
    """

    def __init__(self) -> None:
        super().__init__()
        self.has_form: bool = False
        self.containers: List[str] = []
        self.label_for_ids: Set[str] = set()
        self.label_depth: int = 0
        self.inputs: List[Dict[str, Any]] = []
        self.buttons: List[Dict[str, Any]] = []
        self._current_button: Optional[Dict[str, Any]] = None
        self._current_button_text: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        attr_dict = {k.lower(): (v or "") for k, v in attrs}
        if tag == "form":
            self.has_form = True

        role = attr_dict.get("role", "").lower()
        if role == "form" or "calc" in role or "tool" in role:
            self.containers.append(tag)

        cls_id = (attr_dict.get("class", "") + " " + attr_dict.get("id", "")).lower()
        if any(k in cls_id for k in ("calc", "tool", "widget", "converter", "generator")):
            self.containers.append(tag)

        if tag == "label":
            self.label_depth += 1
            for_id = attr_dict.get("for")
            if for_id:
                self.label_for_ids.add(for_id.strip())

        elif tag == "input":
            inp_type = attr_dict.get("type", "text").lower().strip()
            if inp_type == "submit":
                self.buttons.append({
                    "tag": "input",
                    "type": "submit",
                    "text": attr_dict.get("value", "Submit"),
                    "is_submit": True,
                })
            elif inp_type not in ("hidden", "button", "reset"):
                has_aria = bool(
                    attr_dict.get("aria-label", "").strip()
                    or attr_dict.get("aria-labelledby", "").strip()
                )
                self.inputs.append({
                    "tag": "input",
                    "type": inp_type,
                    "id": attr_dict.get("id", "").strip(),
                    "name": attr_dict.get("name", "").strip(),
                    "has_aria_label": has_aria,
                    "inside_label": (self.label_depth > 0),
                })

        elif tag in ("select", "textarea"):
            has_aria = bool(
                attr_dict.get("aria-label", "").strip()
                or attr_dict.get("aria-labelledby", "").strip()
            )
            self.inputs.append({
                "tag": tag,
                "type": tag,
                "id": attr_dict.get("id", "").strip(),
                "name": attr_dict.get("name", "").strip(),
                "has_aria_label": has_aria,
                "inside_label": (self.label_depth > 0),
            })

        elif tag == "button":
            btn_type = attr_dict.get("type", "").lower().strip()
            self._current_button = {
                "tag": "button",
                "type": btn_type,
                "is_submit": (btn_type == "submit" or (self.has_form and btn_type not in ("button", "reset"))),
                "role": role,
                "class": attr_dict.get("class", ""),
            }
            self._current_button_text = []

    def handle_data(self, data: str) -> None:
        if self._current_button is not None:
            self._current_button_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "label":
            if self.label_depth > 0:
                self.label_depth -= 1
        elif tag == "button" and self._current_button is not None:
            btn_text = "".join(self._current_button_text).strip()
            self._current_button["text"] = btn_text
            cta_words = (
                "submit", "calc", "run", "convert", "generate",
                "analyze", "estimate", "compute", "apply", "go",
                "find", "search", "evaluate"
            )
            if any(w in btn_text.lower() for w in cta_words):
                self._current_button["is_submit"] = True
            self.buttons.append(self._current_button)
            self._current_button = None
            self._current_button_text = []


def detect_tool_utility_issues(html_text: str, rel_path: str = "index.html") -> List[str]:
    """
    Detects contract violations for interactive micro-tools against ToolUtilityContract:
    1. Zero em-dashes and zero en-dashes.
    2. Presence of interactive form or container (<form> or elements with input/action).
    3. Input elements paired with <label> or aria-label.
    4. Dedicated submit CTA button.
    5. Touch targets meeting 44x44px standard.
    Zero em-dashes. Zero en-dashes.
    """
    issues: List[str] = []
    if not isinstance(html_text, str):
        return [f"Page {rel_path}: HTML content must be a string"]
    if not html_text.strip():
        return [f"Page {rel_path}: HTML content is empty"]

    if "\u2014" in html_text:
        issues.append(f"Page {rel_path}: Document contains forbidden em-dash")
    if "\u2013" in html_text:
        issues.append(f"Page {rel_path}: Document contains forbidden en-dash")

    try:
        assert_touch_targets(html_text, context=rel_path)
    except ValueError as ex:
        issues.append(f"Page {rel_path}: {ex}")

    parser = ToolUtilityHTMLParser()
    try:
        parser.feed(html_text)
    except Exception as ex:
        issues.append(f"Page {rel_path}: Failed to parse HTML for tool utility contract: {ex}")
        return issues

    # 1. Check interactive form or container
    has_container = parser.has_form or bool(parser.containers) or (
        bool(parser.inputs) and any(b.get("is_submit") for b in parser.buttons)
    )
    if not has_container:
        issues.append(
            f"Page {rel_path}: Missing interactive form or container element (<form> or container with role='form')"
        )

    # 2. Check input elements
    if not parser.inputs:
        issues.append(f"Page {rel_path}: Missing interactive input elements in tool")
    else:
        for inp in parser.inputs:
            is_paired = (
                inp["has_aria_label"]
                or inp["inside_label"]
                or (inp["id"] and inp["id"] in parser.label_for_ids)
            )
            if not is_paired:
                identifier = inp["id"] or inp["name"] or f"input[type='{inp['type']}']"
                issues.append(
                    f"Page {rel_path}: Input element '{identifier}' lacks associated <label> or aria-label"
                )

    # 3. Check submit CTA button
    has_submit_cta = any(b.get("is_submit") for b in parser.buttons)
    if not has_submit_cta:
        issues.append(
            f"Page {rel_path}: Missing submit CTA button (<button type='submit'> or equivalent)"
        )

    return issues


def assert_tool_utility_contract(html_text: str, context: str = "") -> bool:
    """
    Contract assertion validating ToolUtilityContract for interactive free tools.
    Verifies presence of interactive form or container, accessible input pairings,
    submit CTA button, and 44x44px touch targets.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    issues = detect_tool_utility_issues(html_text, rel_path=context or "index.html")
    if issues:
        raise ValueError(f"Tool utility contract violation{ctx}: {issues[0]}")
    return True


def detect_free_web_application_schema_issues(html_text: str, rel_path: str = "index.html") -> List[str]:
    """
    Detects Schema.org markup issues for free tools requiring WebApplication or SoftwareApplication
    with applicationCategory and offers defined with price 0 and ISO 4217 currency.
    Zero em-dashes. Zero en-dashes.
    """
    issues: List[str] = []
    if not isinstance(html_text, str):
        return [f"Page {rel_path}: HTML content must be a string"]
    if not html_text.strip():
        return [f"Page {rel_path}: HTML content is empty"]

    if "\u2014" in html_text:
        issues.append(f"Page {rel_path}: Document contains forbidden em-dash")
    if "\u2013" in html_text:
        issues.append(f"Page {rel_path}: Document contains forbidden en-dash")

    script_pattern = re.compile(
        r'<script\s+type=["\']application/ld\+json["\']\s*>(.*?)</script>',
        re.DOTALL | re.IGNORECASE,
    )
    blocks = script_pattern.findall(html_text)
    if not blocks:
        return [f"Page {rel_path}: Missing application/ld+json structured data block"]

    parsed_blocks: List[Any] = []
    for raw in blocks:
        try:
            parsed_blocks.append(json.loads(raw.strip()))
        except Exception as ex:
            issues.append(f"Page {rel_path}: Invalid JSON-LD syntax: {ex}")

    if issues:
        return issues

    # Collect entities and graph id map
    entities: List[Dict[str, Any]] = []
    graph_by_id: Dict[str, Dict[str, Any]] = {}

    for block in parsed_blocks:
        if isinstance(block, dict):
            if "@graph" in block and isinstance(block["@graph"], list):
                for item in block["@graph"]:
                    if isinstance(item, dict):
                        entities.append(item)
                        if "@id" in item:
                            graph_by_id[item["@id"]] = item
            else:
                entities.append(block)
                if "@id" in block:
                    graph_by_id[block["@id"]] = block
        elif isinstance(block, list):
            for item in block:
                if isinstance(item, dict):
                    entities.append(item)
                    if "@id" in item:
                        graph_by_id[item["@id"]] = item

    target_types = {"WebApplication", "SoftwareApplication"}
    matching_entities: List[Dict[str, Any]] = []

    for ent in entities:
        etype = ent.get("@type")
        types: List[str] = []
        if isinstance(etype, str):
            types = [etype]
        elif isinstance(etype, list):
            types = [str(t) for t in etype]

        if any(t in target_types for t in types):
            matching_entities.append(ent)

    if not matching_entities:
        return [
            f"Page {rel_path}: Missing WebApplication or SoftwareApplication schema in JSON-LD"
        ]

    for app_ent in matching_entities:
        ent_type = app_ent.get("@type")
        ent_name = str(app_ent.get("name", "Application")).strip()

        # Check applicationCategory
        app_cat = app_ent.get("applicationCategory")
        if not app_cat or not str(app_cat).strip():
            issues.append(
                f"Page {rel_path}: Missing or empty 'applicationCategory' in {ent_name} ({ent_type}) schema"
            )

        # Check offers
        raw_offers = app_ent.get("offers")
        if not raw_offers:
            issues.append(
                f"Page {rel_path}: Missing 'offers' specification in {ent_name} ({ent_type}) schema"
            )
            continue

        offer_candidates: List[Dict[str, Any]] = []
        if isinstance(raw_offers, dict):
            if "@id" in raw_offers and raw_offers["@id"] in graph_by_id and len(raw_offers) == 1:
                offer_candidates.append(graph_by_id[raw_offers["@id"]])
            else:
                offer_candidates.append(raw_offers)
        elif isinstance(raw_offers, list):
            for o in raw_offers:
                if isinstance(o, dict):
                    if "@id" in o and o["@id"] in graph_by_id and len(o) == 1:
                        offer_candidates.append(graph_by_id[o["@id"]])
                    else:
                        offer_candidates.append(o)

        if not offer_candidates:
            issues.append(
                f"Page {rel_path}: 'offers' in {ent_name} ({ent_type}) schema must be an object or list of objects"
            )
            continue

        has_free_price = False
        has_iso_currency = False

        for off in offer_candidates:
            price_val = off.get("price")
            if price_val is not None:
                str_price = str(price_val).strip()
                if str_price in ("0", "0.00", "0.0") or price_val == 0:
                    has_free_price = True

            curr = off.get("priceCurrency")
            if curr and isinstance(curr, str) and re.match(r'^[A-Z]{3}$', curr.strip()):
                has_iso_currency = True

        if not has_free_price:
            issues.append(
                f"Page {rel_path}: Free tool schema in {ent_name} requires offers with 'price': '0'"
            )
        if not has_iso_currency:
            issues.append(
                f"Page {rel_path}: Free tool schema in {ent_name} requires valid ISO 4217 currency (e.g. 'priceCurrency': 'USD')"
            )

    return issues


def assert_free_web_application_schema(html_text: str, context: str = "") -> bool:
    """
    Contract assertion validating Schema.org WebApplication or SoftwareApplication
    markup for free tools: defines applicationCategory and offers with price '0'
    and ISO 4217 currency.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" ({context})" if context else ""
    issues = detect_free_web_application_schema_issues(html_text, rel_path=context or "index.html")
    if issues:
        raise ValueError(f"Free WebApplication schema violation{ctx}: {issues[0]}")
    return True


def detect_rate_limit_and_bot_shield_issues(
    headers_or_html: Union[str, Dict[str, Any]],
    context: str = "",
) -> List[str]:
    """
    Detects operational rate-limit and bot shield protection gaps.
    Verifies presence of rate-limit headers (X-RateLimit-Limit), bot shield tokens
    (Cloudflare Turnstile, reCAPTCHA, cf-mitigated), or client-side caching hooks.
    Zero em-dashes. Zero en-dashes.
    """
    ctx = f" in {context}" if context else ""
    if headers_or_html is None:
        return [f"Operational shield check failed{ctx}: headers or HTML cannot be None"]

    if isinstance(headers_or_html, str):
        if "\u2014" in headers_or_html:
            return [f"Document contains forbidden em-dash{ctx}"]
        if "\u2013" in headers_or_html:
            return [f"Document contains forbidden en-dash{ctx}"]

        text_lower = headers_or_html.lower()

        has_rate_limit = any(
            token in text_lower
            for token in (
                "x-ratelimit-limit",
                "x-ratelimit-remaining",
                "x-ratelimit-reset",
                "ratelimit-limit",
                "ratelimit-remaining",
                "ratelimit-reset",
                "x-rate-limit-limit",
                "x-rate-limit",
                "retry-after",
                'name="rate-limit"',
                "name='rate-limit'",
                "data-rate-limit",
                "rate-limit-token",
            )
        )

        has_bot_shield = any(
            token in text_lower
            for token in (
                "cf-mitigated",
                "cf-ray",
                "cf-turnstile",
                "turnstile",
                "challenges.cloudflare.com",
                "recaptcha",
                "hcaptcha",
                "x-bot-shield",
                'name="bot-shield"',
                "name='bot-shield'",
                "data-bot-shield",
                "bot-protection",
                "anti-bot",
                "cloudflare-challenge",
            )
        )

        has_cache_hook = any(
            token in text_lower
            for token in (
                "cache-control",
                "stale-while-revalidate",
                'http-equiv="cache-control"',
                "http-equiv='cache-control'",
                "data-client-cache",
                "client-cache",
            )
        )

        if not (has_rate_limit or has_bot_shield or has_cache_hook):
            return [
                f"Missing operational rate-limit headers (X-RateLimit-Limit), bot challenge protection (Turnstile/reCAPTCHA), or client-side caching hooks{ctx}"
            ]
        return []

    elif isinstance(headers_or_html, dict):
        lower_headers = {str(k).lower(): str(v) for k, v in headers_or_html.items()}

        has_rate_limit = any(
            k in lower_headers
            for k in (
                "x-ratelimit-limit",
                "x-ratelimit-remaining",
                "x-ratelimit-reset",
                "ratelimit-limit",
                "ratelimit-remaining",
                "ratelimit-reset",
                "x-rate-limit-limit",
                "x-rate-limit",
                "retry-after",
            )
        )

        has_bot_shield = any(
            k in lower_headers
            for k in (
                "cf-mitigated",
                "cf-ray",
                "x-bot-shield",
                "cf-turnstile",
            )
        ) or any(
            "turnstile" in v.lower() or "challenge" in v.lower() or "bot" in v.lower()
            for v in lower_headers.values()
        )

        has_cache_hook = any(
            k in lower_headers
            for k in ("cache-control", "etag", "stale-while-revalidate")
        )

        if not (has_rate_limit or has_bot_shield or has_cache_hook):
            return [
                f"Missing operational rate-limit headers (X-RateLimit-Limit), bot challenge protection (Turnstile/reCAPTCHA), or client-side caching hooks{ctx}"
            ]
        return []

    return [f"Operational shield input must be str or dict, got {type(headers_or_html).__name__}{ctx}"]


def assert_rate_limit_and_bot_shield(
    headers_or_html: Union[str, Dict[str, Any]],
    context: str = "",
) -> bool:
    """
    Contract assertion validating operational rate-limiting and bot shield defenses.
    Zero em-dashes. Zero en-dashes.
    """
    issues = detect_rate_limit_and_bot_shield_issues(headers_or_html, context=context)
    if issues:
        raise ValueError(f"Operational rate-limit and bot shield violation: {issues[0]}")
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
    "AUTHORITATIVE_PROFILE_DOMAINS",
    "BRAND_ENTITY_TAXONOMY",
    "DISALLOWED_BRAND_TAXONOMY",
    "WIKIDATA_URI_PATTERN",
    "AUTHORITATIVE_STATUTORY_DOMAINS",
    "VAGUE_FACTUAL_GENERALIZATIONS",
    "CFR_CITATION_PATTERN",
    "USC_CITATION_PATTERN",
    "IRC_CITATION_PATTERN",
    "IRS_GUIDANCE_PATTERNS",
    "NUMERIC_FACT_PATTERN",
    "INCOMPLETE_FIGURE_PATTERNS",
    "extract_statutory_citations",
    "detect_malformed_statutory_citations",
    "detect_vague_generalizations",
    "detect_incomplete_figures",
    "extract_numeric_facts",
    "assert_statutory_citation_syntax",
    "assert_no_vague_generalizations",
    "assert_numeric_data_density",
    "assert_data_table_structure",
    "assert_citable_specific_facts",
    "assert_citable_facts",
    "assert_specific_facts",
    "assert_primary_statutory_citations",
    "SUBQUERY_QUESTION_STARTERS",
    "SECONDARY_INTENT_KEYWORDS",
    "extract_subquery_sections",
    "detect_shallow_subquestions",
    "assert_subquery_clustering",
    "extract_calculation_variant_nodes",
    "detect_orphaned_calculation_nodes",
    "verify_calculation_variant_reciprocity",
    "assert_calculation_variant_cross_links",
    "assert_no_thin_fan_out_cannibalization",
    "assert_organic_fan_out_coverage",
    "assert_fan_out_coverage",
    "assert_organic_fan_out",
    "DEFAULT_FAN_OUT_SUBTOPIC_FACETS",
    "classify_subtopic_facets",
    "evaluate_page_set_fan_out_coverage",
    "assert_page_set_fan_out_coverage",
    "assert_no_forbidden_dashes",
    "assert_no_prompt_leakage",
    "assert_linkedin",
    "assert_x_post",
    "assert_youtube_pinned_comment",
    "assert_youtube_description",
    "assert_youtube_transcript",
    "CONVERSATIONAL_FILLER_TERMS",
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
    "assert_snippet_length_contract",
    "assert_ai_crawl_access_and_snippet_eligibility",
    "assert_ai_crawl_access",
    "assert_snippet_eligibility",
    "assert_robots_txt_crawler_policy",
    "assert_headers_snippet_policy",
    "assert_quick_answer_passage_relevance",
    "assert_viewport_ordering",
    "assert_query_answer_match",
    "assert_quick_answer_match",
    "assert_query_answer_alignment",
    "assert_wikidata_uri",
    "assert_authoritative_same_as",
    "assert_brand_entity_taxonomy",
    "assert_canonical_entity_definition",
    "assert_brand_entity_in_llm_memory",
    "assert_brand_entity_memory",
    "assert_entity_memory_grounding",
    "ORGANIC_SEARCH_TITLE_MIN_CHARS",
    "ORGANIC_SEARCH_TITLE_MAX_CHARS",
    "ORGANIC_SEARCH_META_DESC_MIN_CHARS",
    "ORGANIC_SEARCH_META_DESC_MAX_CHARS",
    "ORGANIC_SEARCH_MAX_SSR_LATENCY_MS",
    "assert_organic_search_title",
    "assert_single_h1_hierarchy",
    "assert_organic_search_meta_description",
    "assert_canonical_consistency",
    "assert_internal_links_integrity",
    "assert_ssr_response_latency",
    "assert_organic_search_ranking",
    "assert_traditional_organic_search_ranking",
    "assert_core_seo_hygiene",
    "ECONOMIC_DATASET_PATTERNS",
    "UNGROUNDED_SYNTHETIC_PATTERNS",
    "safe_eval_mathematical_formula",
    "detect_ungrounded_synthetic_claims",
    "detect_orphaned_calculation_tables",
    "extract_calculation_manifests",
    "extract_multi_dataset_joins",
    "assert_proprietary_model_integrity",
    "assert_unique_calculation_manifest",
    "assert_multi_dataset_enrichment",
    "assert_no_orphaned_calculation_tables",
    "assert_no_thin_syndicated_content",
    "assert_unique_first_party_information",
    "assert_first_party_information",
    "assert_first_party_assets",
    "assert_firsthand_calculations",
    "assert_proprietary_models",
    "STATUTORY_TAX_BRACKETS",
    "STATUTORY_STANDARD_DEDUCTIONS",
    "STATUTORY_LIMITS",
    "VALID_FEDERAL_TAX_RATES",
    "ALL_OFFICIAL_STANDARD_DEDUCTIONS",
    "SILENT_FALLBACK_DEFAULT_PATTERNS",
    "get_official_tax_brackets",
    "get_official_standard_deduction",
    "get_official_statutory_limit",
    "detect_uncorroborated_statutory_claims",
    "assert_statutory_tax_brackets",
    "assert_standard_deduction_values",
    "assert_statutory_limits",
    "assert_no_uncorroborated_tax_constants",
    "assert_cross_web_consensus_and_corroboration",
    "assert_cross_web_corroboration",
    "assert_statutory_consensus",
    "assert_baseline_fact_agreement",
    "assert_statutory_constants_corroboration",
    "ANONYMOUS_AUTHOR_PATTERNS",
    "AUTHOR_CREDENTIAL_KEYWORDS",
    "EDITORIAL_POLICY_HREF_PATTERNS",
    "ABOUT_HREF_PATTERNS",
    "CONTACT_HREF_PATTERNS",
    "extract_schemas_from_json_ld",
    "extract_author_and_publisher_metadata",
    "detect_publisher_reputation_issues",
    "assert_publisher_authority",
    "assert_author_credentials",
    "assert_person_organization_schema",
    "assert_editorial_policy",
    "assert_freshness_signals",
    "assert_about_contact_linkages",
    "assert_source_publisher_reputation",
    "assert_publisher_reputation",
    "assert_publisher_authority_and_credentials",
    "assert_author_and_publisher_schema",
    "assert_editorial_and_freshness_signals",
    "PROCEDURAL_CONTAINER_KEYWORDS",
    "PROCEDURAL_HEADING_PATTERN",
    "PROCEDURAL_STEP_PREFIX_PATTERN",
    "MAX_PASSAGE_CHAR_LENGTH",
    "extract_content_structure_metadata",
    "detect_extractable_content_issues",
    "assert_semantic_heading_hierarchy",
    "assert_scoped_table_headers",
    "assert_procedural_ordered_steps",
    "assert_passage_level_blocks",
    "assert_extractable_content_structure",
    "assert_extractable_structure",
    "assert_content_structure_extractability",
    "ANSWER_PROMINENCE_MAX_WORD_COUNT",
    "ANSWER_CONTAINER_CLASS_KEYWORDS",
    "CALCULATION_WIDGET_CLASS_KEYWORDS",
    "SECONDARY_DISCUSSION_HEADING_KEYWORDS",
    "extract_answer_prominence_metadata",
    "detect_answer_prominence_issues",
    "assert_answer_word_position",
    "assert_direct_answer_or_widget_presence",
    "assert_answer_above_the_fold",
    "assert_answer_prominence",
    "assert_answer_above_fold",
    "assert_core_answer_prominence",
    "assert_direct_answer_prominence",
    "assert_calculation_widget_prominence",
    "assert_early_answer_block",
    "TARGET_ENTITY_SCHEMAS",
    "SUPPORTED_AUXILIARY_SCHEMAS",
    "ALL_REGISTERED_SCHEMAS",
    "LEAF_ENTITY_SCHEMAS",
    "extract_structured_data_metadata",
    "detect_structured_data_issues",
    "assert_structured_data",
    "assert_valid_structured_data",
    "assert_machine_readable_schema",
    "assert_schema_org_jsonld",
    "assert_schema_graph_structure",
    "assert_target_entity_schemas",
    "assert_schema_graph_connectivity",
    "LLMS_TXT_DISALLOWED_ROUTE_PATTERNS",
    "LLMS_TXT_HUB_HEADING_PATTERNS",
    "extract_llms_txt_metadata",
    "detect_llms_txt_issues",
    "assert_llms_txt",
    "assert_llms_txt_specification",
    "assert_llms_txt_compliance",
    "assert_llms_full_txt_compliance",
    "assert_no_internal_route_leaks",
    "assert_top_category_hubs_summaries",
    "assert_llms_manifest_pair",
    "assert_llms_txt_file",
    "assert_curated_llms_txt",
    "ToolUtilityHTMLParser",
    "detect_tool_utility_issues",
    "assert_tool_utility_contract",
    "detect_free_web_application_schema_issues",
    "assert_free_web_application_schema",
    "detect_rate_limit_and_bot_shield_issues",
    "assert_rate_limit_and_bot_shield",
]




