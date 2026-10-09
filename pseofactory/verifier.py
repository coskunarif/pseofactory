"""
pseofactory Master SEO & GEO Audit Checklist Verification Engine
Enforces mechanical verification gates across all static assets.
All 18 Opus 5.5 SEO Rules + Auxiliary Architectural Quality Gates.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

import re
import sys
import os
import json
import html
import time
import posixpath
import urllib.parse
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set, Callable, Union


from pseofactory.contracts import (
    FORBIDDEN_JARGON,
    assert_no_forbidden_dashes,
    assert_ai_mode_calculation_manifest,
    STATUTORY_TAX_BRACKETS,
    STATUTORY_STANDARD_DEDUCTIONS,
    STATUTORY_LIMITS,
    assert_cross_web_consensus_and_corroboration,
    assert_cross_web_corroboration,
    assert_statutory_consensus,
    assert_baseline_fact_agreement,
    assert_statutory_constants_corroboration,
    assert_statutory_tax_brackets,
    assert_standard_deduction_values,
    assert_statutory_limits,
    assert_no_uncorroborated_tax_constants,
    detect_uncorroborated_statutory_claims,
    get_official_tax_brackets,
    get_official_standard_deduction,
    get_official_statutory_limit,
    assert_source_publisher_reputation,
    assert_publisher_reputation,
    assert_publisher_authority,
    assert_author_credentials,
    assert_person_organization_schema,
    assert_editorial_policy,
    assert_freshness_signals,
    assert_about_contact_linkages,
    detect_publisher_reputation_issues,
    extract_author_and_publisher_metadata,
    assert_extractable_content_structure,
    assert_extractable_structure,
    assert_content_structure_extractability,
    assert_semantic_heading_hierarchy,
    assert_scoped_table_headers,
    assert_procedural_ordered_steps,
    assert_passage_level_blocks,
    detect_extractable_content_issues,
    extract_content_structure_metadata,
    TARGET_ENTITY_SCHEMAS,
    extract_structured_data_metadata,
    detect_structured_data_issues,
    assert_structured_data,
    assert_target_entity_schemas,
    assert_schema_graph_connectivity,
    assert_machine_readable_schema,
    assert_schema_org_jsonld,
    assert_valid_structured_data,
    extract_llms_txt_metadata,
    detect_llms_txt_issues,
    assert_llms_txt,
    assert_llms_txt_specification,
    assert_llms_txt_compliance,
    assert_llms_full_txt_compliance,
    assert_no_internal_route_leaks,
    assert_top_category_hubs_summaries,
    assert_llms_manifest_pair,
    ToolUtilityHTMLParser,
    detect_tool_utility_issues,
    assert_tool_utility_contract,
    detect_free_web_application_schema_issues,
    assert_free_web_application_schema,
    detect_rate_limit_and_bot_shield_issues,
    assert_rate_limit_and_bot_shield,
    DEFAULT_FAN_OUT_SUBTOPIC_FACETS,
    classify_subtopic_facets,
    evaluate_page_set_fan_out_coverage,
    assert_page_set_fan_out_coverage,
)



class SEOVerificationError(Exception):
    """Raised when one or more mechanical SEO checklist gates fail."""

    def __init__(
        self,
        message: str,
        issues: Optional[List[str]] = None,
        gates: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.issues = issues or []
        self.violations = self.issues
        self.gates = gates or {}


# =============================================================================
# Canonical 3-Tier AI Crawler Taxonomy & 2026 Factor Specifications
# =============================================================================

# Canonical 3-Tier AI Crawler Taxonomy
AI_SEARCH_BOTS = ["googlebot", "bingbot", "perplexitybot", "claudebot", "oai-searchbot"]
AI_USER_TRIGGERED_BOTS = ["chatgpt-user"]
AI_TRAINING_BOTS = [
    "gptbot",
    "google-extended",
    "applebot",
    "applebot-extended",
    "meta-externalagent",
    "ccbot",
    "anthropic-ai",
    "cohere-ai",
    "bytespider",
]

ZYPPY_2026_FACTORS_SPEC = [
    {"factor": "Search Intent Match", "weight": 2.60, "code": "search_intent_match"},
    {"factor": "Page Semantic Relevance", "weight": 2.34, "code": "page_semantic_relevance"},
    {"factor": "Site Topical Authority", "weight": 2.29, "code": "site_topical_authority"},
    {"factor": "Title Relevance", "weight": 2.26, "code": "title_relevance"},
    {"factor": "Passage-level Relevance", "weight": 1.99, "code": "passage_level_relevance"},
    {"factor": "Language Match", "weight": 1.95, "code": "language_match"},
    {"factor": "Geographic Relevance", "weight": 1.89, "code": "geographic_relevance"},
    {"factor": "Keywords in H1", "weight": 1.67, "code": "keywords_in_h1"},
    {"factor": "Keywords in Subheadings", "weight": 1.27, "code": "keywords_in_subheadings"},
    {"factor": "Keywords in URL", "weight": 1.07, "code": "keywords_in_url"},
    {"factor": "Exact-Match Domain", "weight": 0.94, "code": "exact_match_domain"},
    {"factor": "Meta Description", "weight": 0.22, "code": "meta_description"},
]

ZYPPY_2026_AI_FACTORS_SPEC = [
    {
        "factor": "AI Crawl Access & Snippet Eligibility",
        "name": "AI Crawl Access & Snippet Eligibility",
        "weight": 2.20,
        "positive_weight": 2.20,
        "negative_weight": -2.20,
        "code": "ai_crawl_access_and_snippet_eligibility",
        "description": "Unrestricted crawl access for AI search bots and full snippet eligibility without nosnippet, noindex, or restrictive max-snippet caps.",
    },
    {
        "factor": "Query-Answer Match",
        "name": "Query-Answer Match",
        "weight": 2.15,
        "positive_weight": 2.15,
        "negative_weight": -2.15,
        "code": "query_answer_match",
        "description": "Direct, concise, self-contained answer in initial viewport matching target query intent.",
    },
    {
        "factor": "Brand / Entity in LLM Memory",
        "name": "Brand / Entity in LLM Memory",
        "weight": 2.08,
        "positive_weight": 2.08,
        "negative_weight": -2.08,
        "code": "brand_entity_in_llm_memory",
        "description": "Entity recognition and parametric memory presence across authoritative sources and knowledge graphs.",
    },
    {
        "factor": "Citable / Specific Facts",
        "name": "Citable / Specific Facts",
        "weight": 2.07,
        "positive_weight": 2.07,
        "negative_weight": -2.07,
        "code": "citable_specific_facts",
        "description": "High-density verifiable statistics, clear facts, numbers, primary statutory citations, data tables, and extractable data points.",
        "aliases": [
            "Citable / Specific Facts",
            "Citable Specific Facts",
            "citable_specific_facts",
            "citable_facts",
            "specific_facts",
            "citable",
            "primary_statutory_citations",
        ],
    },
    {
        "factor": "Organic Fan-Out Coverage Rankings",
        "name": "Organic Fan-Out Coverage Rankings",
        "weight": 1.91,
        "positive_weight": 1.91,
        "negative_weight": -1.91,
        "code": "organic_fan_out_coverage",
        "description": "Unified subquery clustering, answering related sub-questions, secondary intent verification, calculation variants, and reciprocal cross-linking of fan-out calculation nodes without thin page cannibalization.",
        "aliases": [
            "Organic Fan-Out Coverage Rankings",
            "Organic Fan-Out Coverage",
            "organic_fan_out_coverage_rankings",
            "organic_fan_out_coverage",
            "fan_out_coverage",
            "fan_out",
            "organic_fan_out",
            "subquery_clustering",
        ],
    },
    {
        "factor": "Organic Search Ranking",
        "name": "Organic Search Ranking",
        "weight": 1.89,
        "positive_weight": 1.89,
        "negative_weight": -1.89,
        "code": "organic_search_ranking",
        "description": "Securing traditional organic search rankings through core SEO hygiene: titles 30-65 chars, single H1, meta descriptions 70-160 chars, canonical consistency, zero broken internal links, and sub-100ms static SSR response.",
        "aliases": [
            "Organic Search Ranking",
            "Organic Search Authority & Traditional Rank",
            "organic_search_ranking",
            "organic_search_authority",
            "organic_search",
            "traditional_rank",
            "core_seo_hygiene",
        ],
    },
    {
        "factor": "Unique First-Party Information",
        "name": "Unique First-Party Information",
        "weight": 1.85,
        "positive_weight": 1.85,
        "negative_weight": -1.85,
        "code": "unique_first_party_information",
        "description": "Authoritative content grounded in original data, firsthand calculations, proprietary models, multi-dataset enrichment joining statutory rates with economic/BLS/FRED data, and unique calculation manifests.",
        "aliases": [
            "Unique First-Party Information",
            "Unique / First-Party Information",
            "unique_first_party_information",
            "first_party_information",
            "unique_information",
            "proprietary_models",
            "multi_dataset_enrichment",
            "firsthand_calculations",
            "calculation_manifests",
            "first_party_assets",
        ],
    },
    {
        "factor": "Cross-Web Consensus & Corroboration",
        "name": "Cross-Web Consensus & Corroboration",
        "weight": 1.81,
        "positive_weight": 1.81,
        "negative_weight": -1.81,
        "code": "cross_web_consensus_and_corroboration",
        "description": "Agreement on baseline facts and statutory constants across the web, verifying standard tax brackets, statutory limits, and standard deduction values against official published schedules.",
        "aliases": [
            "Cross-Web Consensus & Corroboration",
            "Cross-web Corroboration",
            "Cross-Web Corroboration",
            "cross_web_consensus_and_corroboration",
            "cross_web_corroboration",
            "statutory_consensus",
            "baseline_fact_agreement",
            "statutory_constants_corroboration",
            "cross_web_consensus",
            "corroboration",
        ],
    },
    {
        "factor": "Source / Publisher Reputation",
        "name": "Source / Publisher Reputation",
        "weight": 1.78,
        "positive_weight": 1.78,
        "negative_weight": -1.78,
        "code": "source_publisher_reputation",
        "description": "Publisher authority, verified author credentials, Person and Organization schema, editorial review policies, datePublished and dateModified freshness signals, and about and contact linkages.",
        "aliases": [
            "Source / Publisher Reputation",
            "Source Publisher Reputation",
            "Publisher Reputation",
            "source_publisher_reputation",
            "publisher_reputation",
            "publisher_authority",
            "author_credentials",
            "editorial_policy",
            "about_contact_linkages",
        ],
    },
    {
        "factor": "Extractable Content Structure",
        "name": "Extractable Content Structure",
        "weight": 1.69,
        "positive_weight": 1.69,
        "negative_weight": -1.69,
        "code": "extractable_content_structure",
        "description": "Strict semantic HTML heading hierarchies without skipped levels, data tables with scoped column headers (scope='col'), ordered lists for sequential procedural steps, and clean passage-level blocks.",
        "aliases": [
            "Extractable Content Structure",
            "Extractable Content",
            "extractable_content_structure",
            "extractable_structure",
            "extractable_content",
            "semantic_heading_hierarchy",
            "table_column_scopes",
            "scoped_table_headers",
            "procedural_ordered_steps",
            "passage_level_blocks",
        ],
    },
    {
        "factor": "Answer Prominence",
        "name": "Answer Prominence",
        "weight": 1.65,
        "positive_weight": 1.65,
        "negative_weight": -1.65,
        "code": "answer_prominence",
        "description": "Prominent placement of the direct answer or core calculation widget above the fold within the first 300 words of the body before secondary discussion.",
        "aliases": [
            "Answer Prominence",
            "Answer Prominence & Early Body Placement",
            "answer_prominence",
            "answer_above_fold",
            "core_answer_prominence",
            "direct_answer_prominence",
            "calculation_widget_prominence",
            "early_answer_block",
            "answer_position",
            "cumulative_body_word_position",
            "early_direct_answers",
        ],
    },
    {
        "factor": "Topical Authority & Depth",
        "name": "Topical Authority & Depth",
        "weight": 1.20,
        "positive_weight": 1.20,
        "negative_weight": -1.20,
        "code": "topical_authority_depth",
        "description": "Comprehensive hub-and-spoke coverage of the problem space with extensive internal linking.",
    },
    {
        "factor": "Structured Data",
        "name": "Structured Data",
        "weight": 0.80,
        "positive_weight": 0.80,
        "negative_weight": -0.80,
        "code": "structured_data",
        "description": "Machine-readable Schema.org JSON-LD markup validating SoftwareApplication, WebApplication, Product, FAQPage, HowTo, and Dataset schemas with connected graph structures and zero parse errors.",
        "aliases": [
            "Structured Data",
            "Structured Data & Schema.org Graphs",
            "Structured Data Markup",
            "structured_data",
            "structured_data_markup",
            "schema_org_structured_data",
            "jsonld_structured_data",
            "schema_graphs",
            "target_entity_schemas",
            "machine_readable_schemas",
            "schema_graph_structure",
            "schema_markup_graphs",
        ],
    },
    {
        "factor": "llms.txt File",
        "name": "llms.txt File",
        "weight": 0.05,
        "positive_weight": 0.05,
        "negative_weight": -0.05,
        "code": "llms_txt",
        "description": "Curated machine-readable llms.txt and llms-full.txt files conforming to llmstxt.org specification with concise markdown summaries linking top category hubs without leaking internal routes.",
        "aliases": [
            "llms.txt File",
            "llms.txt",
            "llms_txt_file",
            "llms_txt",
            "llms_full_txt",
            "llmstxt",
            "llms_txt_manifest",
            "curated_llms_txt",
            "Factor 13",
            "Factor 13: llms.txt File",
            "Factor 13: llms.txt",
        ],
    },
]


def get_ai_factor_spec(query: Any) -> Optional[Dict[str, Any]]:
    """
    Retrieves the specification for a Zyppy 2026 AI factor by code, name, or 1-indexed position.
    Returns None if no matching factor is found.
    Zero em-dashes. Zero en-dashes.
    """
    if isinstance(query, int):
        if 1 <= query <= len(ZYPPY_2026_AI_FACTORS_SPEC):
            return ZYPPY_2026_AI_FACTORS_SPEC[query - 1]
        return None
    if not isinstance(query, str):
        return None
    q_clean = query.strip().lower()
    q_norm = q_clean.replace("-", "_").replace(" ", "_").replace("/", "_")
    while "__" in q_norm:
        q_norm = q_norm.replace("__", "_")
    for factor_spec in ZYPPY_2026_AI_FACTORS_SPEC:
        code_norm = factor_spec.get("code", "").lower().replace("-", "_").replace(" ", "_").replace("/", "_")
        while "__" in code_norm:
            code_norm = code_norm.replace("__", "_")
        if code_norm == q_norm:
            return factor_spec
        name_clean = factor_spec.get("name", "").lower()
        if name_clean == q_clean:
            return factor_spec
        factor_clean = factor_spec.get("factor", "").lower()
        if factor_clean == q_clean:
            return factor_spec
        if name_clean.replace(" ", "").replace("/", "") == q_clean.replace(" ", "").replace("/", ""):
            return factor_spec
        if factor_clean.replace(" ", "").replace("/", "") == q_clean.replace(" ", "").replace("/", ""):
            return factor_spec
        for alias in factor_spec.get("aliases", []):
            alias_clean = alias.strip().lower()
            alias_norm = alias_clean.replace("-", "_").replace(" ", "_").replace("/", "_")
            while "__" in alias_norm:
                alias_norm = alias_norm.replace("__", "_")
            if alias_clean == q_clean or alias_norm == q_norm:
                return factor_spec
            if alias_clean.replace(" ", "").replace("/", "") == q_clean.replace(" ", "").replace("/", ""):
                return factor_spec
    return None


def is_ai_search_crawler(bot_name: str) -> bool:
    """
    Returns True if the bot name corresponds to an AI search or user-triggered crawler.
    Zero em-dashes. Zero en-dashes.
    """
    if not bot_name or not isinstance(bot_name, str):
        return False
    bot_clean = bot_name.strip().lower()
    search_bots = {b.lower() for b in AI_SEARCH_BOTS} | {b.lower() for b in AI_USER_TRIGGERED_BOTS}
    if bot_clean in search_bots:
        return True
    if bot_clean in ("claude-web", "searchbot"):
        return True
    return False


def is_ai_training_crawler(bot_name: str) -> bool:
    """
    Returns True if the bot name corresponds to a model training crawler.
    Zero em-dashes. Zero en-dashes.
    """
    if not bot_name or not isinstance(bot_name, str):
        return False
    bot_clean = bot_name.strip().lower()
    return bot_clean in {b.lower() for b in AI_TRAINING_BOTS}


def is_ai_crawler(bot_name: str) -> bool:
    """
    Returns True if the bot name is recognized as any AI crawler (search, user, or training).
    Zero em-dashes. Zero en-dashes.
    """
    return is_ai_search_crawler(bot_name) or is_ai_training_crawler(bot_name)


# =============================================================================
# Zyppy 2026 Content Relevance Single-Pass HTML Parser
# =============================================================================

class SinglePassSEODocumentParser(HTMLParser):
    """
    Streaming single-pass HTML parser extracting structural SEO entities with zero external dependencies.
    """

    def __init__(self, brand_domain: str = ""):
        super().__init__(convert_charrefs=True)
        self.brand_domain = brand_domain
        self.root_lang = ""
        self.title_parts: List[str] = []
        self.meta_description = ""
        self.canonical_url = ""
        self.og_url = ""
        self.meta_content_language = ""
        self.hreflangs: List[str] = []
        self.geo_region = ""
        self.h1_list: List[str] = []
        self.h2_list: List[str] = []
        self.h3_list: List[str] = []
        self.json_ld_blocks: List[str] = []
        self.quick_answer_text_parts: List[str] = []
        self.in_quick_answer = False
        self.quick_answer_depth = 0
        self.table_count = 0
        self.ol_count = 0
        self.has_calculator = False
        self.internal_links: List[str] = []
        self.current_tag: Optional[str] = None
        self.current_data: List[str] = []
        self.tag_stack: List[Tuple[str, Dict[str, str]]] = []
        # Snippet and crawl verification state
        self.has_nosnippet: bool = False
        self.max_snippet: Optional[int] = None
        self.has_noindex: bool = False
        self.max_image_preview: Optional[str] = None
        self.max_video_preview: Optional[int] = None
        self.data_nosnippet_tags: List[str] = []
        self.quick_answer_has_data_nosnippet: bool = False
        self.root_has_data_nosnippet: bool = False
        # Factor 2: Query-Answer Match & Viewport Ordering State
        self.quick_answer_count: int = 0
        self.quick_answer_tags: List[str] = []
        self.quick_answer_blocks: List[Dict[str, Any]] = []
        self.current_quick_answer_parts: List[str] = []
        self.quick_answer_seen_after_h1: bool = False
        self.quick_answer_seen_before_h2: bool = True
        self.quick_answer_in_viewport: bool = False
        self.structural_events: List[str] = []
        self.target_query: Optional[str] = None
        # Factor 4: Citable / Specific Facts State
        self.tables_data: List[Dict[str, Any]] = []
        self.in_table: bool = False
        self.current_table_headers: List[str] = []
        self.current_table_rows: List[List[str]] = []
        self.current_row_cells: List[str] = []
        self.current_cell_tag: Optional[str] = None
        self.current_cell_data: List[str] = []
        self.page_text_parts: List[str] = []
        # Factor 5: Organic Fan-Out Coverage State
        self.calculation_variants: List[Dict[str, Any]] = []
        self.in_calculation_variant: bool = False
        self.current_variant_depth: int = 0
        self.current_variant_attrs: Dict[str, str] = {}
        self.current_variant_text: List[str] = []
        self.current_variant_links: List[str] = []
        self.current_variant_has_calc: bool = False
        # Factor 6: Organic Search Ranking State
        self.element_ids: Set[str] = set()
        self.element_names: Set[str] = set()
        self.all_hrefs: List[str] = []
        # Factor 7: Unique / First-Party Information State
        self.calculation_manifest_elements: List[Dict[str, Any]] = []
        self.multi_dataset_join_elements: List[Dict[str, Any]] = []
        self.has_proprietary_model_element: bool = False
        self.embedded_manifest_blocks: List[str] = []
        self.current_table_attrs: Dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        attrs_dict = {k.lower(): (v or "") for k, v in attrs}
        self.tag_stack.append((tag, attrs_dict))

        if "data-nosnippet" in attrs_dict:
            self.data_nosnippet_tags.append(tag)
            if tag in ("html", "body", "main"):
                self.root_has_data_nosnippet = True
            if self.in_quick_answer:
                self.quick_answer_has_data_nosnippet = True

        if tag == "html":
            if "lang" in attrs_dict:
                self.root_lang = attrs_dict["lang"]

        elif tag == "title":
            self.current_tag = "title"
            self.current_data = []

        elif tag == "meta":
            name = attrs_dict.get("name", "").lower()
            prop = attrs_dict.get("property", "").lower()
            http_equiv = attrs_dict.get("http-equiv", "").lower()
            content = attrs_dict.get("content", "")
            if name == "description":
                self.meta_description = content
            elif http_equiv == "content-language":
                self.meta_content_language = content
            elif name == "geo.region":
                self.geo_region = content
            elif prop == "og:url":
                self.og_url = content
            elif name in ("target-query", "target_query", "query"):
                self.target_query = content

            search_crawlers = {"robots", "claude-web"} | {b.lower() for b in AI_SEARCH_BOTS} | {b.lower() for b in AI_USER_TRIGGERED_BOTS}
            if name in search_crawlers or http_equiv in ("x-robots-tag", "robots"):
                c_lower = content.lower()
                if "nosnippet" in c_lower:
                    self.has_nosnippet = True
                if "noindex" in c_lower or re.search(r'\bnone\b', c_lower):
                    self.has_noindex = True
                if "max-snippet" in c_lower:
                    m_ms = re.search(r'max-snippet\s*:\s*(-?\d+)', content, re.IGNORECASE)
                    if m_ms:
                        val = int(m_ms.group(1))
                        if self.max_snippet is None or (val >= 0 and (self.max_snippet < 0 or val < self.max_snippet)):
                            self.max_snippet = val
                if "max-image-preview" in c_lower:
                    m_mip = re.search(r'max-image-preview\s*:\s*([a-zA-Z0-9_-]+)', content, re.IGNORECASE)
                    if m_mip:
                        self.max_image_preview = m_mip.group(1).lower()
                if "max-video-preview" in c_lower:
                    m_mvp = re.search(r'max-video-preview\s*:\s*(-?\d+)', content, re.IGNORECASE)
                    if m_mvp:
                        self.max_video_preview = int(m_mvp.group(1))

        elif tag == "link":
            rel = attrs_dict.get("rel", "").lower()
            if rel == "canonical":
                self.canonical_url = attrs_dict.get("href", "")
            elif rel == "alternate" and "hreflang" in attrs_dict:
                self.hreflangs.append(attrs_dict["hreflang"].lower())

        elif tag in ("h1", "h2", "h3"):
            self.current_tag = tag
            self.current_data = []
            self.structural_events.append(tag)

        elif tag == "script":
            s_type = attrs_dict.get("type", "").lower()
            if s_type == "application/ld+json":
                self.current_tag = "script_json_ld"
                self.current_data = []
            elif s_type == "application/json" and (
                "manifest" in attrs_dict.get("id", "").lower()
                or "manifest" in attrs_dict.get("class", "").lower()
                or attrs_dict.get("data-type") == "calculation-manifest"
            ):
                self.current_tag = "script_manifest"
                self.current_data = []

        elif tag in ("form", "input", "select", "button"):
            self.has_calculator = True

        tag_id = attrs_dict.get("id", "").lower()
        tag_cls = attrs_dict.get("class", "").lower()
        if "calc" in tag_id or "calc" in tag_cls:
            self.has_calculator = True

        if (
            "calculation-manifest" in tag_cls
            or "data-manifest-id" in attrs_dict
            or "data-calculation-manifest" in attrs_dict
        ):
            self.calculation_manifest_elements.append(attrs_dict)

        if (
            "multi-dataset-join" in tag_cls
            or "dataset-join" in tag_cls
            or "data-dataset-join" in attrs_dict
            or ("data-statutory-source" in attrs_dict and "data-economic-source" in attrs_dict)
        ):
            self.multi_dataset_join_elements.append(attrs_dict)

        if "proprietary-model" in tag_cls or "data-proprietary-model" in attrs_dict:
            self.has_proprietary_model_element = True

        is_qa_element = (
            "quick-answer" in tag_cls
            or "quick_answer" in tag_cls
            or "quick-answer" in tag_id
            or "quick_answer" in tag_id
        )
        if is_qa_element:
            self.quick_answer_count += 1
            self.quick_answer_tags.append(tag)
            self.in_quick_answer = True
            self.quick_answer_depth = len(self.tag_stack)
            if "data-nosnippet" in attrs_dict:
                self.quick_answer_has_data_nosnippet = True
            for anc_tag, anc_attrs in self.tag_stack:
                if "data-nosnippet" in anc_attrs:
                    self.quick_answer_has_data_nosnippet = True
                    break

            seen_h1 = (len(self.h1_list) > 0) or ("h1" in self.structural_events) or (self.current_tag == "h1")
            seen_h2 = (len(self.h2_list) > 0) or ("h2" in self.structural_events) or (self.current_tag == "h2")
            self.structural_events.append("quick-answer")

            if self.quick_answer_count == 1:
                self.quick_answer_seen_after_h1 = seen_h1
                self.quick_answer_seen_before_h2 = not seen_h2
                self.quick_answer_in_viewport = seen_h1 and not seen_h2

            if "data-query" in attrs_dict:
                self.target_query = attrs_dict["data-query"]

        is_calc_variant = (
            "calculation-variant" in tag_cls
            or "fan-out-node" in tag_cls
            or "calc-variant" in tag_cls
            or "calculation-node" in tag_cls
            or "variant-container" in tag_cls
            or "data-variant-id" in attrs_dict
            or "data-variant" in attrs_dict
            or "data-calculation-variant" in attrs_dict
            or "data-node-id" in attrs_dict
            or tag_id.startswith("variant-")
            or tag_id.startswith("calc-variant")
        )
        if is_calc_variant and not self.in_calculation_variant:
            self.in_calculation_variant = True
            self.current_variant_depth = len(self.tag_stack)
            self.current_variant_attrs = attrs_dict
            self.current_variant_text = []
            self.current_variant_links = []
            self.current_variant_has_calc = False

        if self.in_calculation_variant:
            if tag in ("form", "input", "select", "table"):
                self.current_variant_has_calc = True
            if tag == "a" and "href" in attrs_dict:
                self.current_variant_links.append(attrs_dict["href"])

        if tag == "table":
            self.table_count += 1
            self.in_table = True
            self.current_table_attrs = dict(attrs_dict)
            self.current_table_headers = []
            self.current_table_rows = []
        elif tag == "tr":
            self.current_row_cells = []
        elif tag in ("th", "td"):
            self.current_cell_tag = tag
            self.current_cell_data = []
        elif tag == "ol":
            self.ol_count += 1

        elif tag == "a":
            href = attrs_dict.get("href", "")
            if href:
                self.all_hrefs.append(href)
            if href.startswith("/") or (self.brand_domain and self.brand_domain in href):
                self.internal_links.append(href)

        raw_id = attrs_dict.get("id", "").strip()
        if raw_id:
            self.element_ids.add(raw_id)
        raw_name = attrs_dict.get("name", "").strip()
        if raw_name:
            self.element_names.add(raw_name)

    def handle_endtag(self, tag: str):
        if self.current_tag == "title":
            self.title_parts.append("".join(self.current_data))
            self.current_tag = None
        elif self.current_tag == "h1":
            self.h1_list.append("".join(self.current_data).strip())
            self.current_tag = None
        elif self.current_tag == "h2":
            self.h2_list.append("".join(self.current_data).strip())
            self.current_tag = None
        elif self.current_tag == "h3":
            self.h3_list.append("".join(self.current_data).strip())
            self.current_tag = None
        elif self.current_tag == "script_json_ld":
            self.json_ld_blocks.append("".join(self.current_data))
            self.current_tag = None
        elif self.current_tag == "script_manifest":
            self.embedded_manifest_blocks.append("".join(self.current_data))
            self.current_tag = None

        if tag in ("th", "td"):
            cell_val = "".join(self.current_cell_data).strip()
            if self.current_cell_tag == "th":
                self.current_table_headers.append(cell_val)
            else:
                self.current_row_cells.append(cell_val)
            self.current_cell_tag = None
            self.current_cell_data = []
        elif tag == "tr":
            if self.current_row_cells:
                self.current_table_rows.append(list(self.current_row_cells))
            self.current_row_cells = []
        elif tag == "table":
            self.in_table = False
            t_meta = self._evaluate_table_meta(
                list(self.current_table_headers),
                list(self.current_table_rows),
                attrs=self.current_table_attrs,
            )
            self.tables_data.append(t_meta)
            self.current_table_headers = []
            self.current_table_rows = []
            self.current_table_attrs = {}

        if self.in_quick_answer and len(self.tag_stack) <= self.quick_answer_depth:
            self.in_quick_answer = False
            qa_block_text = "".join(self.current_quick_answer_parts).strip()
            self.quick_answer_blocks.append({
                "tag": tag,
                "text": qa_block_text,
                "word_count": len(qa_block_text.split()) if qa_block_text else 0,
                "char_count": len(qa_block_text),
                "after_h1": self.quick_answer_seen_after_h1,
                "before_h2": self.quick_answer_seen_before_h2,
                "in_viewport": self.quick_answer_in_viewport,
            })
            self.current_quick_answer_parts = []

        if self.in_calculation_variant and len(self.tag_stack) <= self.current_variant_depth:
            self.in_calculation_variant = False
            v_text = "".join(self.current_variant_text).strip()
            v_id = (
                self.current_variant_attrs.get("data-variant-id")
                or self.current_variant_attrs.get("data-node-id")
                or self.current_variant_attrs.get("data-variant")
                or self.current_variant_attrs.get("id")
                or f"variant-{len(self.calculation_variants) + 1}"
            )
            has_calc = self.current_variant_has_calc or bool(
                re.search(r'(=|\+|\-|\*|/|%|\$)\s*[0-9]+', v_text)
                or re.search(r'\$[0-9]+', v_text)
                or re.search(r'\b[0-9]+(?:\.[0-9]+)?\s*%', v_text)
            )
            self.calculation_variants.append({
                "id": v_id,
                "text": v_text,
                "outgoing_links": list(self.current_variant_links),
                "has_calculation": has_calc,
                "word_count": len(v_text.split()),
            })
            self.current_variant_text = []
            self.current_variant_links = []

        if self.tag_stack and self.tag_stack[-1][0] == tag:
            self.tag_stack.pop()

    def handle_data(self, data: str):
        if self.current_tag in ("title", "h1", "h2", "h3", "script_json_ld", "script_manifest"):
            self.current_data.append(data)
        if self.in_quick_answer:
            self.quick_answer_text_parts.append(data)
            self.current_quick_answer_parts.append(data)
        if self.in_calculation_variant:
            self.current_variant_text.append(data)
        if self.current_cell_tag:
            self.current_cell_data.append(data)
        if self.current_tag not in ("script", "script_json_ld", "script_manifest", "style"):
            self.page_text_parts.append(data)

    def _evaluate_table_meta(
        self,
        headers: List[str],
        rows: List[List[str]],
        attrs: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        from pseofactory.contracts import extract_numeric_facts, extract_statutory_citations
        col_count = len(headers) if headers else (max(len(r) for r in rows) if rows else 0)
        has_headers = len(headers) >= 2
        is_masquerading = False
        if not has_headers:
            for r in rows:
                for c in r:
                    if len(c) > 150 or len(c.split()) > 30:
                        is_masquerading = True
                        break
            if col_count <= 1:
                is_masquerading = True

        all_cells = list(headers)
        for r in rows:
            all_cells.extend(r)

        has_numeric = any(bool(extract_numeric_facts(c)) or bool(extract_statutory_citations(c)) for c in all_cells)
        is_valid = (
            has_headers
            and len(rows) >= 1
            and col_count >= 2
            and all(len(r) >= 2 for r in rows)
            and has_numeric
            and not is_masquerading
        )

        table_attrs = attrs or {}
        has_statutory_provenance = any(
            k in table_attrs
            for k in ["data-statutory", "data-statutory-source", "data-statutory-provenance", "data-authority"]
        ) or any("irc" in str(c).lower() or "statut" in str(c).lower() or "cfr" in str(c).lower() for c in all_cells)

        has_economic_provenance = any(
            k in table_attrs
            for k in ["data-economic", "data-economic-source", "data-economic-dataset"]
        ) or any("bls" in str(c).lower() or "fred" in str(c).lower() or "bea" in str(c).lower() for c in all_cells)

        return {
            "headers": headers,
            "rows": rows,
            "col_count": col_count,
            "row_count": len(rows),
            "has_headers": has_headers,
            "has_numeric_data": has_numeric,
            "is_masquerading_narrative": is_masquerading,
            "is_valid": is_valid,
            "attrs": table_attrs,
            "has_statutory_provenance": has_statutory_provenance,
            "has_economic_provenance": has_economic_provenance,
        }

    @property
    def page_text(self) -> str:
        return " ".join("".join(self.page_text_parts).split())

    @property
    def statutory_citations(self) -> List[Dict[str, str]]:
        from pseofactory.contracts import extract_statutory_citations
        return extract_statutory_citations(self.page_text)

    @property
    def has_statutory_citations(self) -> bool:
        return len(self.statutory_citations) > 0

    @property
    def numeric_facts(self) -> List[str]:
        from pseofactory.contracts import extract_numeric_facts
        return extract_numeric_facts(self.page_text)

    @property
    def numeric_facts_count(self) -> int:
        return len(self.numeric_facts)

    @property
    def has_data_table(self) -> bool:
        return any(t.get("is_valid") for t in self.tables_data)

    @property
    def has_masquerading_narrative_table(self) -> bool:
        return any(t.get("is_masquerading_narrative") for t in self.tables_data)

    @property
    def calculation_manifests(self) -> List[Dict[str, Any]]:
        manifests = []
        for block in self.embedded_manifest_blocks:
            try:
                m_data = json.loads(block)
                if isinstance(m_data, dict):
                    manifests.append(m_data.get("calculation_manifest") or m_data)
                elif isinstance(m_data, list):
                    for item in m_data:
                        if isinstance(item, dict):
                            manifests.append(item.get("calculation_manifest") or item)
            except Exception:
                pass
        for b in self.json_ld_blocks:
            try:
                data = json.loads(b)
                if isinstance(data, dict):
                    if "calculation_manifest" in data:
                        manifests.append(data["calculation_manifest"])
                    elif data.get("@type") in ("CalculationManifest", "TaxCalculationModel", "FirstPartyCalculationManifest"):
                        manifests.append(data)
            except Exception:
                pass
        return manifests

    @property
    def has_first_party_information(self) -> bool:
        return (
            bool(self.calculation_manifests)
            or bool(self.calculation_manifest_elements)
            or bool(self.multi_dataset_join_elements)
            or self.has_proprietary_model_element
        )

    @property
    def title(self) -> str:
        return "".join(self.title_parts).strip()

    @property
    def quick_answer_text(self) -> str:
        return "".join(self.quick_answer_text_parts).strip()

    @property
    def has_quick_answer(self) -> bool:
        return self.quick_answer_count > 0 or bool(self.quick_answer_text)

    @property
    def quick_answer_word_count(self) -> int:
        qa = self.quick_answer_text
        return len(qa.split()) if qa else 0

    @property
    def brand_entities(self) -> List[Dict[str, Any]]:
        """
        Extracts candidate canonical brand entities from document JSON-LD blocks.
        Zero em-dashes. Zero en-dashes.
        """
        parsed_blocks = []
        for raw in self.json_ld_blocks:
            try:
                parsed_blocks.append(json.loads(raw.strip()))
            except Exception:
                continue
        return extract_canonical_brand_entities(
            parsed_blocks,
            brand_name=getattr(self, "brand_name", None),
            brand_domain=getattr(self, "brand_domain", None),
        )

    @property
    def has_canonical_brand_entity(self) -> bool:
        return len(self.brand_entities) > 0


# Backward-compatible alias
ZyppyHTMLParser = SinglePassSEODocumentParser


# =============================================================================
# Mock Search Engine Crawler (Factor 6: Organic Search Ranking Simulation)
# =============================================================================

class MockSearchEngineCrawler:
    """
    Simulated search engine crawler executing mock crawls across static distribution routes.
    Evaluates Factor 6: Organic Search Ranking (+1.89) core SEO hygiene:
    1. Title tag boundaries (30-65 chars, no double pipes)
    2. Single H1 presence and hierarchy (no duplicate H1s, non-empty)
    3. Meta description limits (70-160 chars, no truncation)
    4. Canonical consistency without drift or unnormalized URLs
    5. Internal link graph traversals and dead route detection
    6. Sub-100ms static SSR response benchmarks
    Zero em-dashes. Zero en-dashes.
    """

    def __init__(
        self,
        base_domain: Optional[str] = None,
        max_ssr_latency_ms: float = 100.0,
    ):
        self.base_domain = base_domain
        self.max_ssr_latency_ms = max_ssr_latency_ms

    def crawl_directory(
        self,
        dist_dir: Path,
        max_ssr_latency_ms: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Executes mock crawler traversal across a static distribution directory on disk.
        Zero em-dashes. Zero en-dashes.
        """
        from pseofactory.contracts import (
            ORGANIC_SEARCH_TITLE_MIN_CHARS,
            ORGANIC_SEARCH_TITLE_MAX_CHARS,
            ORGANIC_SEARCH_META_DESC_MIN_CHARS,
            ORGANIC_SEARCH_META_DESC_MAX_CHARS,
            assert_canonical_consistency,
            assert_internal_links_integrity,
        )

        max_lat = max_ssr_latency_ms if max_ssr_latency_ms is not None else self.max_ssr_latency_ms
        target = Path(dist_dir)
        if not target.exists():
            return {
                "status": "FAIL",
                "gate": "check_organic_search_ranking_gate",
                "pages_crawled": 0,
                "routes_discovered": 0,
                "internal_links_verified": 0,
                "violations_count": 1,
                "issues": [f"Directory {target} not found"],
            }

        issues: List[str] = []
        html_files = sorted(target.glob("**/*.html"))

        file_route_map: Dict[str, Path] = {}
        known_routes: Set[str] = set()

        for p in html_files:
            rel = p.relative_to(target).as_posix()
            if rel == "404.html" or "signal" in p.parts or "static" in p.parts:
                continue

            if rel == "index.html":
                canon_route = "/"
            elif rel.endswith("/index.html"):
                canon_route = "/" + rel[:-10]
            elif rel.endswith(".html"):
                canon_route = "/" + rel[:-5]
            else:
                canon_route = "/" + rel

            if not canon_route.endswith("/") and rel.endswith("/index.html"):
                canon_route += "/"

            file_route_map[canon_route] = p

            known_routes.add(canon_route)
            known_routes.add(canon_route.rstrip("/") if canon_route != "/" else "/")
            known_routes.add(canon_route if canon_route.endswith("/") else canon_route + "/")
            known_routes.add("/" + rel)
            known_routes.add(rel)
            if rel.endswith("/index.html"):
                known_routes.add("/" + rel[:-11] if rel[:-11] else "/")

        pages_crawled = 0
        total_links_verified = 0

        for route, p in sorted(file_route_map.items()):
            rel = p.relative_to(target).as_posix()
            t0 = time.perf_counter()
            content = p.read_text(encoding="utf-8", errors="ignore")
            parser = SinglePassSEODocumentParser(brand_domain=self.base_domain)
            parser.feed(content)
            latency_ms = (time.perf_counter() - t0) * 1000.0

            pages_crawled += 1

            if "\u2014" in content:
                issues.append(f"Page {rel}: Document contains forbidden em-dash")
            if "\u2013" in content:
                issues.append(f"Page {rel}: Document contains forbidden en-dash")

            if latency_ms >= max_lat:
                issues.append(
                    f"Page {rel}: Static SSR response latency regression ({latency_ms:.2f}ms exceeds {max_lat:.2f}ms threshold)"
                )
            if len(content.encode("utf-8")) > 500 * 1024:
                issues.append(f"Page {rel}: Slow SSR generation bloat (payload exceeds 500KB)")

            raw_title = parser.title
            if not raw_title:
                issues.append(f"Page {rel}: Missing <title> tag")
            else:
                if "| |" in raw_title:
                    issues.append(f"Page {rel}: Double pipe ('| |') formatting corruption in title: '{raw_title}'")
                clean_title = html.unescape(raw_title).strip()
                t_len = len(clean_title)
                if t_len < ORGANIC_SEARCH_TITLE_MIN_CHARS:
                    issues.append(
                        f"Page {rel}: Title length ({t_len} chars) under {ORGANIC_SEARCH_TITLE_MIN_CHARS}-char threshold: '{clean_title}'"
                    )
                elif t_len > ORGANIC_SEARCH_TITLE_MAX_CHARS:
                    issues.append(
                        f"Page {rel}: Title length ({t_len} chars) exceeds {ORGANIC_SEARCH_TITLE_MAX_CHARS}-char threshold: '{clean_title}'"
                    )

            h1s = parser.h1_list
            if len(h1s) == 0:
                issues.append(f"Page {rel}: Missing <h1> tag")
            elif len(h1s) > 1:
                issues.append(f"Page {rel}: Multiple <h1> tags ({len(h1s)}) detected")
            else:
                clean_h1 = re.sub(r'<[^>]+>', '', h1s[0]).strip()
                if not clean_h1:
                    issues.append(f"Page {rel}: Empty <h1> tag detected")

            empty_headings = re.findall(r'<h([2-6])\b[^>]*>\s*</h\1>', content, re.IGNORECASE)
            if empty_headings:
                issues.append(f"Page {rel}: Empty heading container detected (<h{empty_headings[0]}>)")

            md = parser.meta_description
            if not md:
                issues.append(f"Page {rel}: Missing meta description")
            else:
                clean_desc = html.unescape(md).strip()
                d_len = len(clean_desc)
                if d_len < ORGANIC_SEARCH_META_DESC_MIN_CHARS:
                    issues.append(
                        f"Page {rel}: Meta description length ({d_len} chars) under {ORGANIC_SEARCH_META_DESC_MIN_CHARS}-char threshold: '{clean_desc}'"
                    )
                elif d_len > ORGANIC_SEARCH_META_DESC_MAX_CHARS:
                    issues.append(
                        f"Page {rel}: Meta description length ({d_len} chars) exceeds {ORGANIC_SEARCH_META_DESC_MAX_CHARS}-char threshold: '{clean_desc}'"
                    )
                if (
                    re.search(r'\$\d+(?:,\d+)*(?:,\.\.\.|\.\.\.)', clean_desc)
                    or re.search(r'\d+,\.\.\.', clean_desc)
                    or re.search(r'\d+\.\.\.', clean_desc)
                    or re.search(r'\d+…', clean_desc)
                ):
                    issues.append(f"Page {rel}: Mid-number ellipsis truncation in meta description: '{clean_desc}'")

            c_url = parser.canonical_url
            if not c_url:
                issues.append(f"Page {rel}: Missing canonical link tag")
            else:
                try:
                    assert_canonical_consistency(
                        c_url,
                        expected_route_or_url=route,
                        base_domain=self.base_domain,
                        context=f"Page {rel}",
                    )
                except Exception as ex:
                    issues.append(str(ex))

            try:
                assert_internal_links_integrity(
                    content,
                    known_routes=known_routes,
                    current_route=route,
                    base_domain=self.base_domain,
                    context=f"Page {rel}",
                )
                total_links_verified += len(parser.all_hrefs)
            except Exception as ex:
                issues.append(str(ex))

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_organic_search_ranking_gate",
            "pages_crawled": pages_crawled,
            "routes_discovered": len(known_routes),
            "internal_links_verified": total_links_verified,
            "violations_count": len(issues),
            "issues": issues,
        }

    def crawl_pages(
        self,
        pages: Dict[str, str],
        max_ssr_latency_ms: Optional[float] = None,
        base_domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes mock crawler traversal across an in-memory route dictionary of HTML documents.
        Zero em-dashes. Zero en-dashes.
        """
        from pseofactory.contracts import (
            ORGANIC_SEARCH_TITLE_MIN_CHARS,
            ORGANIC_SEARCH_TITLE_MAX_CHARS,
            ORGANIC_SEARCH_META_DESC_MIN_CHARS,
            ORGANIC_SEARCH_META_DESC_MAX_CHARS,
            assert_canonical_consistency,
            assert_internal_links_integrity,
        )

        domain = base_domain or self.base_domain
        max_lat = max_ssr_latency_ms if max_ssr_latency_ms is not None else self.max_ssr_latency_ms
        issues: List[str] = []

        known_routes: Set[str] = set()
        for r in pages.keys():
            norm_r = r if r.startswith("/") else f"/{r}"
            known_routes.add(norm_r)
            known_routes.add(norm_r.rstrip("/") if norm_r != "/" else "/")
            known_routes.add(norm_r if norm_r.endswith("/") else norm_r + "/")
            if norm_r.endswith(".html"):
                base_stem = norm_r[:-5]
                known_routes.add(base_stem)
                known_routes.add(base_stem + "/")
            elif norm_r == "/":
                known_routes.add("/index.html")

        pages_crawled = 0
        total_links = 0

        for route, content in sorted(pages.items()):
            norm_route = route if route.startswith("/") else f"/{route}"
            pages_crawled += 1

            t0 = time.perf_counter()
            parser = SinglePassSEODocumentParser(brand_domain=domain)
            parser.feed(content)
            latency_ms = (time.perf_counter() - t0) * 1000.0

            if "\u2014" in content:
                issues.append(f"Route {norm_route}: Document contains forbidden em-dash")
            if "\u2013" in content:
                issues.append(f"Route {norm_route}: Document contains forbidden en-dash")

            if latency_ms >= max_lat:
                issues.append(
                    f"Route {norm_route}: Static SSR response latency regression ({latency_ms:.2f}ms exceeds {max_lat:.2f}ms threshold)"
                )
            if len(content.encode("utf-8")) > 500 * 1024:
                issues.append(f"Route {norm_route}: Slow SSR generation bloat (payload exceeds 500KB)")

            raw_title = parser.title
            if not raw_title:
                issues.append(f"Route {norm_route}: Missing <title> tag")
            else:
                if "| |" in raw_title:
                    issues.append(f"Route {norm_route}: Double pipe ('| |') formatting corruption in title: '{raw_title}'")
                clean_title = html.unescape(raw_title).strip()
                t_len = len(clean_title)
                if t_len < ORGANIC_SEARCH_TITLE_MIN_CHARS:
                    issues.append(
                        f"Route {norm_route}: Title length ({t_len} chars) under {ORGANIC_SEARCH_TITLE_MIN_CHARS}-char threshold: '{clean_title}'"
                    )
                elif t_len > ORGANIC_SEARCH_TITLE_MAX_CHARS:
                    issues.append(
                        f"Route {norm_route}: Title length ({t_len} chars) exceeds {ORGANIC_SEARCH_TITLE_MAX_CHARS}-char threshold: '{clean_title}'"
                    )

            h1s = parser.h1_list
            if len(h1s) == 0:
                issues.append(f"Route {norm_route}: Missing <h1> tag")
            elif len(h1s) > 1:
                issues.append(f"Route {norm_route}: Multiple <h1> tags ({len(h1s)}) detected")
            else:
                clean_h1 = re.sub(r'<[^>]+>', '', h1s[0]).strip()
                if not clean_h1:
                    issues.append(f"Route {norm_route}: Empty <h1> tag detected")

            empty_headings = re.findall(r'<h([2-6])\b[^>]*>\s*</h\1>', content, re.IGNORECASE)
            if empty_headings:
                issues.append(f"Route {norm_route}: Empty heading container detected (<h{empty_headings[0]}>)")

            md = parser.meta_description
            if not md:
                issues.append(f"Route {norm_route}: Missing meta description")
            else:
                clean_desc = html.unescape(md).strip()
                d_len = len(clean_desc)
                if d_len < ORGANIC_SEARCH_META_DESC_MIN_CHARS:
                    issues.append(
                        f"Route {norm_route}: Meta description length ({d_len} chars) under {ORGANIC_SEARCH_META_DESC_MIN_CHARS}-char threshold: '{clean_desc}'"
                    )
                elif d_len > ORGANIC_SEARCH_META_DESC_MAX_CHARS:
                    issues.append(
                        f"Route {norm_route}: Meta description length ({d_len} chars) exceeds {ORGANIC_SEARCH_META_DESC_MAX_CHARS}-char threshold: '{clean_desc}'"
                    )
                if (
                    re.search(r'\$\d+(?:,\d+)*(?:,\.\.\.|\.\.\.)', clean_desc)
                    or re.search(r'\d+,\.\.\.', clean_desc)
                    or re.search(r'\d+\.\.\.', clean_desc)
                    or re.search(r'\d+…', clean_desc)
                ):
                    issues.append(f"Route {norm_route}: Mid-number ellipsis truncation in meta description: '{clean_desc}'")

            c_url = parser.canonical_url
            if not c_url:
                issues.append(f"Route {norm_route}: Missing canonical link tag")
            else:
                try:
                    assert_canonical_consistency(
                        c_url,
                        expected_route_or_url=norm_route,
                        base_domain=domain,
                        context=f"Route {norm_route}",
                    )
                except Exception as ex:
                    issues.append(str(ex))

            try:
                assert_internal_links_integrity(
                    content,
                    known_routes=known_routes,
                    current_route=norm_route,
                    base_domain=domain,
                    context=f"Route {norm_route}",
                )
                total_links += len(parser.all_hrefs)
            except Exception as ex:
                issues.append(str(ex))

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_organic_search_ranking_gate",
            "pages_crawled": pages_crawled,
            "routes_discovered": len(known_routes),
            "internal_links_verified": total_links,
            "violations_count": len(issues),
            "issues": issues,
        }

    def crawl(
        self,
        target: Any,
        max_ssr_latency_ms: Optional[float] = None,
        base_domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispatches to crawl_directory or crawl_pages based on target type."""
        if isinstance(target, (str, Path)):
            p = Path(target)
            if p.is_dir():
                return self.crawl_directory(p, max_ssr_latency_ms=max_ssr_latency_ms)
        if isinstance(target, dict):
            return self.crawl_pages(target, max_ssr_latency_ms=max_ssr_latency_ms, base_domain=base_domain)
        raise ValueError(f"Target must be a directory Path or dict of routes: {target}")


def simulate_crawler_traversal(
    target: Any,
    base_domain: Optional[str] = None,
    max_ssr_latency_ms: float = 100.0,
) -> Dict[str, Any]:
    """
    Executes mock search engine crawler traversal over directory or page dictionary.
    Zero em-dashes. Zero en-dashes.
    """
    crawler = MockSearchEngineCrawler(base_domain=base_domain, max_ssr_latency_ms=max_ssr_latency_ms)
    return crawler.crawl(target, max_ssr_latency_ms=max_ssr_latency_ms, base_domain=base_domain)


# =============================================================================
# Master SEO Verifier Class
# =============================================================================

class MasterSEOVerifier:
    """
    Parametric Master SEO & GEO Audit Checklist Verification Engine.
    Configurable brand name, canonical base, domain, required endpoints, and leaf checks.
    """

    def __init__(
        self,
        dist_dir: Optional[Path] = None,
        canonical_base: Optional[str] = None,
        domain: Optional[str] = None,
        brand_name: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        required_endpoints: Optional[List[str]] = None,
        leaf_route_checker: Optional[Callable[[Path, List[Tuple[str, str]]], List[str]]] = None,
        is_geo_leaf: Optional[Callable[[str, Path], bool]] = None,
        is_calculation_leaf: Optional[Callable[[str, Path, Any], Optional[str]]] = None,
        code_dirs: Optional[List[Path]] = None,
        min_manifests: int = 8,
        strict_robots: bool = False,
    ):
        self.canonical_base = (
            canonical_base
            if canonical_base is not None
            else os.environ.get("FACTORY_CANONICAL_BASE", "https://profithelm.com")
        ).rstrip("/")
        self.domain = (
            domain
            if domain is not None
            else os.environ.get("FACTORY_DOMAIN", "profithelm.com")
        )
        self.brand_domain = self.domain
        self.brand_name = (
            brand_name
            if brand_name is not None
            else os.environ.get("FACTORY_BRAND_NAME", "ProfitHelm")
        )
        self.dist_dir = (
            Path(dist_dir)
            if dist_dir is not None
            else Path(os.environ.get("FACTORY_DIST_DIR", "/home/ubuntuadmin/projects/profithelm-platform/dist"))
        )
        self.tools = list(tools) if tools else []
        self.min_manifests = min_manifests
        self.strict_robots = strict_robots
        self.leaf_route_checker = leaf_route_checker
        self.is_geo_leaf = is_geo_leaf
        self.is_calculation_leaf = is_calculation_leaf
        self.code_dirs = list(code_dirs) if code_dirs else []

        if required_endpoints is not None:
            self.required_endpoints = list(required_endpoints)
        else:
            self.required_endpoints = [
                "/feed.xml",
                "/llms.txt",
                "/llms-full.txt",
                "/sitemap.xml",
                "/sitemap-hubs.xml",
                "/sitemap-leaves.xml",
                "/",
                "/about/",
                "/privacy/",
                "/tools/",
            ]

    # 1. Alt Text Gate
    def check_alt_text_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        images_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                for m in re.finditer(r'<img\b([^>]*)>', content, re.IGNORECASE):
                    images_checked += 1
                    attrs = m.group(1)
                    alt_m = re.search(r'\balt=["\']([^"\']*)["\']', attrs, re.IGNORECASE)
                    if not alt_m or not alt_m.group(1).strip():
                        issues.append(f"Missing or empty alt attribute on <img> tag in {rel}")
                    elif alt_m.group(1).strip().lower() in ["image", "placeholder"]:
                        issues.append(f"Generic placeholder alt attribute '{alt_m.group(1)}' in {rel}")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_alt_text_gate",
            "images_checked": images_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 2. Sitemap Gate
    def check_sitemap_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        sitemap = target / "sitemap.xml"
        urls_checked = 0

        if not sitemap.is_file():
            issues.append(f"Missing sitemap.xml at {sitemap}")
        else:
            try:
                tree = ET.parse(sitemap)
                root = tree.getroot()
                ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
                locs = [elem.text.strip() for elem in root.findall(".//sm:loc", ns) if elem.text]
                if not locs:
                    locs = [elem.text.strip() for elem in root.findall(".//loc") if elem.text]

                urls_checked = len(locs)
                if urls_checked < 3:
                    issues.append(f"sitemap.xml contains only {urls_checked} URLs (expected >= 3)")

                domain_prefix = f"https://{self.domain}"
                for loc in locs:
                    if not loc.startswith(domain_prefix) and not loc.startswith(self.canonical_base):
                        issues.append(f"Sitemap URL '{loc}' does not match canonical base {domain_prefix}")
            except Exception as ex:
                issues.append(f"Malformed XML in sitemap.xml: {ex}")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_sitemap_gate",
            "urls_checked": urls_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 3. Page Titles Gate
    def check_page_titles_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        pages_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                if p.name == "404.html" or "signal" in p.parts:
                    continue
                pages_checked += 1
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r'<title\b[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
                if not m:
                    issues.append(f"Missing <title> tag in {rel}")
                else:
                    raw_title = m.group(1).strip()
                    if "| |" in raw_title:
                        issues.append(f"Double pipe ('| |') formatting corruption in {rel}: '{raw_title}'")
                    title = html.unescape(raw_title)
                    t_len = len(title)
                    if not (50 <= t_len <= 60):
                        issues.append(f"Title length ({t_len} chars) outside 50-60 range in {rel}: '{title}'")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_page_titles_gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 4. Single H1 Gate
    def check_single_h1_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        pages_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                if p.name == "404.html":
                    continue
                pages_checked += 1
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                h1s = re.findall(r'<h1\b[^>]*>(.*?)</h1>', content, re.IGNORECASE | re.DOTALL)
                if len(h1s) == 0:
                    issues.append(f"Missing <h1> tag in {rel}")
                elif len(h1s) > 1:
                    issues.append(f"Multiple <h1> tags ({len(h1s)}) detected in {rel}")
                elif not re.sub(r'<[^>]+>', '', h1s[0]).strip():
                    issues.append(f"Empty <h1> tag detected in {rel}")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_single_h1_gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 5. Image Compression Gate
    def check_image_compression_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        images_checked = 0
        max_bytes = 500 * 1024  # 500 KB limit
        if target.exists():
            for ext in ["*.png", "*.jpg", "*.jpeg", "*.webp", "*.svg"]:
                for img in target.glob(f"**/{ext}"):
                    images_checked += 1
                    size = img.stat().st_size
                    if size > max_bytes:
                        rel = img.relative_to(target).as_posix()
                        issues.append(f"Image {rel} exceeds 500KB threshold ({size / 1024:.1f} KB)")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_image_compression_gate",
            "images_checked": images_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 6. Page Language Gate
    def check_page_language_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        pages_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                if p.name == "404.html":
                    continue
                pages_checked += 1
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r'<html\b[^>]*\blang=["\']([^"\']*)["\']', content, re.IGNORECASE)
                if not m:
                    issues.append(f"Missing lang attribute on <html> in {rel}")
                elif not (m.group(1).lower().startswith("en")):
                    issues.append(f"Invalid lang attribute '{m.group(1)}' (expected English) in {rel}")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_page_language_gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 7. Canonical Tags Gate
    def check_canonical_tags_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        pages_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                if p.name == "404.html":
                    continue
                pages_checked += 1
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r'<link\b[^>]*\brel=["\']canonical["\'][^>]*\bhref=["\']([^"\']*)["\']', content, re.IGNORECASE)
                if not m:
                    m = re.search(r'<link\b[^>]*\bhref=["\']([^"\']*)["\'][^>]*\brel=["\']canonical["\']', content, re.IGNORECASE)
                if not m:
                    issues.append(f"Missing canonical link tag in {rel}")
                else:
                    c_url = m.group(1).strip()
                    if not c_url.startswith("https://"):
                        issues.append(f"Canonical URL is not absolute HTTPS in {rel}: '{c_url}'")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_canonical_tags_gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 8. HTTP Link Canonical Gate (Rule 19 / Gate 26)
    def check_http_link_canonical_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        headers_file = target / "_headers"
        if not headers_file.is_file():
            issues.append(f"Missing _headers file at {headers_file}")
            return {
                "status": "FAIL",
                "gate": "check_http_link_canonical_gate",
                "headers_checked": 0,
                "violations_count": len(issues),
                "issues": issues,
            }

        content = headers_file.read_text(encoding="utf-8", errors="ignore")
        canonical_link_pattern = re.compile(
            r'Link:\s*<([^>]+)>;\s*rel=["\']?canonical["\']?',
            re.IGNORECASE
        )

        rules: Dict[str, List[str]] = {}
        current_route = None
        for line in content.splitlines():
            line_stripped = line.strip()
            if not line_stripped or line_stripped.startswith("#"):
                continue
            if not line.startswith(" ") and not line.startswith("\t"):
                current_route = line_stripped
                rules[current_route] = []
            elif current_route:
                rules[current_route].append(line_stripped)

        found_canonical_links = []
        for route, headers in rules.items():
            for h in headers:
                m = canonical_link_pattern.search(h)
                if m:
                    found_canonical_links.append((route, m.group(1)))

        if not found_canonical_links:
            issues.append("Zero RFC 5988 canonical Link headers found in dist/_headers")

        for ep in self.required_endpoints:
            matching = [url for r, url in found_canonical_links if r == ep]
            if not matching:
                issues.append(f"Missing RFC 5988 canonical Link header for machine endpoint {ep}")
            else:
                target_url = matching[0]
                if not target_url.startswith("https://"):
                    issues.append(f"Invalid canonical URL scheme in Link header for {ep}: '{target_url}'")
                if ep.endswith(".xml") or ep.endswith(".txt"):
                    if not target_url.endswith(ep):
                        issues.append(f"Canonical URL path mismatch in Link header for {ep}: '{target_url}'")

        if self.leaf_route_checker:
            issues.extend(self.leaf_route_checker(target, found_canonical_links))

        for r, url in found_canonical_links:
            if not url.startswith("https://"):
                issues.append(f"Link header canonical URL '{url}' for route '{r}' is not HTTPS")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_http_link_canonical_gate",
            "headers_checked": len(rules),
            "canonical_links_found": len(found_canonical_links),
            "violations_count": len(issues),
            "issues": issues,
        }

    # 9. AI Mode Manifest Gate
    def check_ai_mode_manifest_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        manifests_dir = target / "manifests"
        manifest_files = list(manifests_dir.glob("*.json")) if manifests_dir.exists() else []

        if not manifest_files:
            issues.append(f"Missing machine-readable calculation manifests in {manifests_dir}")
        else:
            for mf in manifest_files:
                try:
                    spec = json.loads(mf.read_text(encoding="utf-8"))
                    assert_ai_mode_calculation_manifest(spec)
                except Exception as ex:
                    issues.append(f"Calculation manifest {mf.name} failed AI Mode contract: {ex}")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_ai_mode_manifest_gate",
            "manifests_checked": len(manifest_files),
            "violations_count": len(issues),
            "issues": issues,
        }

    check_manifest_gate = check_ai_mode_manifest_gate

    # 10. Robots.txt Gate
    @staticmethod
    def parse_robots_txt_sections(content: str) -> Dict[str, Dict[str, List[str]]]:
        """Parses robots.txt content into normalized user-agent sections."""
        sections: Dict[str, Dict[str, List[str]]] = {}
        current_agents: List[str] = []
        for raw_line in content.splitlines():
            line = raw_line.split("#")[0].strip()
            if not line:
                current_agents = []
                continue
            if ":" not in line:
                continue
            key, val = [x.strip() for x in line.split(":", 1)]
            key_lower = key.lower()
            if key_lower == "user-agent":
                agent = val.lower()
                current_agents.append(agent)
                if agent not in sections:
                    sections[agent] = {"allow": [], "disallow": []}
            elif key_lower == "allow" and current_agents:
                for agent in current_agents:
                    sections[agent]["allow"].append(val)
            elif key_lower == "disallow" and current_agents:
                for agent in current_agents:
                    sections[agent]["disallow"].append(val)
        return sections

    @staticmethod
    def is_path_disallowed(path: str, allows: List[str], disallows: List[str]) -> bool:
        norm_path = path if path.startswith("/") else f"/{path}"
        longest_allow = -1
        for a in allows:
            a_clean = a.strip()
            if not a_clean:
                continue
            if norm_path.startswith(a_clean):
                if len(a_clean) > longest_allow:
                    longest_allow = len(a_clean)
        longest_disallow = -1
        for d in disallows:
            d_clean = d.strip()
            if not d_clean:
                continue
            if norm_path.startswith(d_clean):
                if len(d_clean) > longest_disallow:
                    longest_disallow = len(d_clean)
        if longest_disallow > longest_allow:
            return True
        return False

    @classmethod
    def is_bot_blocked(cls, bot_name: str, path: str, sections: Dict[str, Dict[str, List[str]]]) -> bool:
        bot_lower = bot_name.lower()
        candidates = [bot_lower]
        if bot_lower == "claudebot":
            candidates.append("claude-web")
        elif bot_lower == "claude-web":
            candidates.append("claudebot")

        for c in candidates:
            if c in sections:
                return cls.is_path_disallowed(path, sections[c]["allow"], sections[c]["disallow"])
        if "*" in sections:
            return cls.is_path_disallowed(path, sections["*"]["allow"], sections["*"]["disallow"])
        return False

    # 10. Robots.txt Gate
    def check_robots_txt_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        robots_file = target / "robots.txt"
        if not robots_file.is_file():
            issues.append(f"Missing robots.txt at {robots_file}")
        else:
            content = robots_file.read_text(encoding="utf-8", errors="ignore")
            content_lower = content.lower()
            if "sitemap.xml" not in content_lower:
                issues.append("robots.txt missing Sitemap directive")
            if "sitemap-hubs.xml" not in content_lower:
                issues.append("robots.txt missing sitemap-hubs.xml directive")
            if "sitemap-leaves.xml" not in content_lower:
                issues.append("robots.txt missing sitemap-leaves.xml directive")
            if "allow: /" not in content_lower:
                issues.append("robots.txt missing 'Allow: /' directive")
            if "disallow: /signal/" not in content_lower:
                issues.append("robots.txt missing 'Disallow: /signal/'")

            # Parse robots.txt sections by user-agent
            sections = self.parse_robots_txt_sections(content)

            # AI Search and User-Triggered bots must NOT be disallowed on root / or /tools/
            for bot in AI_SEARCH_BOTS + AI_USER_TRIGGERED_BOTS:
                if self.is_bot_blocked(bot, "/", sections):
                    issues.append(f"robots.txt disallows AI search/user bot '{bot}' on root '/'")
                if self.is_bot_blocked(bot, "/tools/", sections):
                    issues.append(f"robots.txt disallows AI search/user bot '{bot}' on '/tools/'")

            if self.strict_robots:
                if (self.tools or (target / "tools").is_dir()) and "allow: /tools/" not in content_lower:
                    issues.append("robots.txt missing 'Allow: /tools/' directive")
                for dis in ("/syndication/", "/staging/", "/test/", "/tests/"):
                    if (target / dis.strip("/")).is_dir() and f"disallow: {dis}" not in content_lower:
                        issues.append(f"robots.txt missing 'Disallow: {dis}'")

                for bot in AI_SEARCH_BOTS + AI_USER_TRIGGERED_BOTS:
                    if bot not in sections:
                        if bot == "claudebot" and "claude-web" in sections:
                            continue
                        if bot == "claude-web" and "claudebot" in sections:
                            continue
                        issues.append(f"robots.txt missing User-agent directive for AI crawler {bot}")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_robots_txt_gate",
            "violations_count": len(issues),
            "issues": issues,
        }

    # 11. Readable URLs Gate
    def check_readable_urls_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        if target.exists():
            for p in target.glob("**/*.html"):
                if p.name not in ["index.html", "404.html"]:
                    rel = p.relative_to(target).as_posix()
                    issues.append(f"Non-canonical URL path (raw .html file exposed): {rel}")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_readable_urls_gate",
            "violations_count": len(issues),
            "issues": issues,
        }

    # 12. Schema Markup Gate
    def check_schema_markup_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        schemas_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                if p.name == "404.html" or "signal" in p.parts:
                    continue
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                matches = re.findall(r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', content, re.IGNORECASE | re.DOTALL)
                if not matches:
                    issues.append(f"Missing Schema.org JSON-LD in {rel}")
                else:
                    for m in matches:
                        schemas_checked += 1
                        try:
                            parsed = json.loads(m)
                            if "@context" not in parsed and "@graph" not in parsed:
                                issues.append(f"Schema JSON missing @context or @graph in {rel}")
                        except Exception as ex:
                            issues.append(f"Invalid JSON-LD schema syntax in {rel}: {ex}")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_schema_markup_gate",
            "schemas_checked": schemas_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 13. Noindex Tags Gate
    def check_noindex_tags_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        pages_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                if p.name == "404.html" or "signal" in p.parts:
                    continue
                pages_checked += 1
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                if re.search(r'<meta[^>]*\bcontent=["\'][^"\']*noindex[^"\']*["\'][^>]*>', content, re.IGNORECASE):
                    issues.append(f"Public page {rel} contains accidental 'noindex' directive")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_noindex_tags_gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 14. Internal Linking Gate
    def check_internal_linking_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        pages_checked = 0
        tools_dir = target / "tools"
        if tools_dir.is_dir():
            for p in tools_dir.glob("**/index.html"):
                pages_checked += 1
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                links = re.findall(r'<a\b[^>]*\bhref=["\']([^"\']*)["\'][^>]*>(.*?)</a>', content, re.IGNORECASE | re.DOTALL)
                internal_links = [h for h, _ in links if h.startswith("/") or self.domain in h or self.canonical_base in h]
                if len(internal_links) < 3:
                    issues.append(f"Tool page {rel} has only {len(internal_links)} internal links (expected >= 3)")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_internal_linking_gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 15. Load Performance Gate
    def check_load_performance_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        pages_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                pages_checked += 1
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                for m in re.finditer(r'<script\b([^>]*)>', content, re.IGNORECASE):
                    attrs = m.group(1).lower()
                    if 'type="application/ld+json"' in attrs:
                        continue
                    if "src=" in attrs and not ("async" in attrs or "defer" in attrs):
                        issues.append(f"Render-blocking external script in {rel}: {attrs}")

            css_candidates = [
                target / "css" / "style.css",
                target / "static" / "css" / "style.css",
            ]
            for css_file in css_candidates:
                if css_file.is_file() and css_file.stat().st_size > 100 * 1024:
                    issues.append(f"Main CSS stylesheet exceeds 100KB: {css_file.stat().st_size} bytes")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_load_performance_gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 16. Meta Descriptions Gate
    def check_meta_descriptions_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        pages_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                if p.name == "404.html" or "signal" in p.parts:
                    continue
                pages_checked += 1
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']', content, re.IGNORECASE)
                if not m:
                    m = re.search(r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*name=["\']description["\']', content, re.IGNORECASE)
                if not m:
                    issues.append(f"Missing meta description in {rel}")
                else:
                    desc = html.unescape(m.group(1).strip())
                    if len(desc) < 50 or len(desc) > 165:
                        issues.append(f"Meta description length {len(desc)} outside 50-165 range in {rel}")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_meta_descriptions_gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 17. URL Redirects Gate
    def check_url_redirects_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        redirects_file = target / "_redirects"
        if redirects_file.is_file():
            content = redirects_file.read_text(encoding="utf-8", errors="ignore")
            for line_num, line in enumerate(content.splitlines(), start=1):
                line_clean = line.strip()
                if not line_clean or line_clean.startswith("#"):
                    continue
                parts = line_clean.split()
                if len(parts) < 2:
                    issues.append(f"Malformed redirect rule at line {line_num}: '{line_clean}'")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_url_redirects_gate",
            "violations_count": len(issues),
            "issues": issues,
        }

    # 18. Search Console Tag Gate
    def check_search_console_tag_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        pages_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                if p.name == "404.html":
                    continue
                pages_checked += 1
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r'<meta[^>]*name=["\']google-site-verification["\'][^>]*content=["\']([^"\']+)["\']', content, re.IGNORECASE)
                if not m:
                    m = re.search(r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*name=["\']google-site-verification["\']', content, re.IGNORECASE)
                if not m or not m.group(1).strip():
                    issues.append(f"Missing or empty google-site-verification meta tag in {rel}")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_search_console_tag_gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 19. Hide Test Pages Gate
    def check_hide_test_pages_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        signal_paths = [
            target / "signal" / "index.html",
            target / "static" / "signal" / "index.html",
        ]
        for sp in signal_paths:
            if sp.is_file():
                s_content = sp.read_text(encoding="utf-8", errors="ignore")
                has_noindex = bool(
                    re.search(r'<meta[^>]*name=["\']robots["\'][^>]*content=["\'][^"\']*noindex[^"\']*["\']', s_content, re.IGNORECASE)
                    or re.search(r'<meta[^>]*content=["\'][^"\']*noindex[^"\']*["\'][^>]*name=["\']robots["\']', s_content, re.IGNORECASE)
                )
                if not has_noindex:
                    issues.append(f"Signal intake page {sp.relative_to(target)} missing noindex in meta robots tag")

        robots_txt = target / "robots.txt"
        if robots_txt.is_file():
            robots_content = robots_txt.read_text(encoding="utf-8", errors="ignore")
            if "disallow: /signal/" not in robots_content.lower():
                issues.append(f"{robots_txt.relative_to(target)} is missing 'Disallow: /signal/'")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_hide_test_pages_gate",
            "violations_count": len(issues),
            "issues": issues,
        }

    # 20. No JS Rendering Gate
    def check_no_js_rendering_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        pages_checked = 0
        tools_dir = target / "tools"
        if tools_dir.is_dir():
            for p in tools_dir.glob("**/index.html"):
                pages_checked += 1
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                clean = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', content, flags=re.IGNORECASE)
                clean = re.sub(r'<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>', '', clean, flags=re.IGNORECASE)
                text = re.sub(r'<[^>]+>', ' ', clean)

                # Check for skeleton/placeholder containers and phrases
                placeholder_patterns = [
                    r'\bloading\.{0,3}\b',
                    r'\benable\s+javascript\b',
                    r'\bjavascript\s+is\s+required\b',
                    r'\bjavascript\s+required\b',
                    r'\bloading\s+application\b',
                    r'\bskeleton\b',
                ]
                substantive_text = text
                for pat in placeholder_patterns:
                    substantive_text = re.sub(pat, ' ', substantive_text, flags=re.IGNORECASE)

                words = [w for w in substantive_text.split() if w.strip()]
                if len(words) < 50:
                    issues.append(f"Insufficient static content without JavaScript ({len(words)} substantive words) in {rel}")
                if "<h1" not in content.lower():
                    issues.append(f"Missing <h1> tag in static HTML in {rel}")

                # If quick-answer container is present, verify non-empty text directly in static HTML
                m_qa = re.search(r'<(?:aside|div)[^>]*class=["\'][^"\']*quick-answer[^"\']*["\'][^>]*>(.*?)</(?:aside|div)>', content, re.IGNORECASE | re.DOTALL)
                if m_qa:
                    qa_raw = m_qa.group(1)
                    qa_text = re.sub(r'<[^>]+>', ' ', qa_raw).strip()
                    qa_substantive = qa_text
                    for pat in placeholder_patterns:
                        qa_substantive = re.sub(pat, ' ', qa_substantive, flags=re.IGNORECASE).strip()
                    if not qa_substantive:
                        issues.append(f"Quick-answer container is empty or contains only placeholders awaiting JavaScript hydration in {rel}")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_no_js_rendering_gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 21. Existence Gate (Auxiliary)
    def check_existence_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        tools_dir = target / "tools"
        if self.tools:
            for tool in self.tools:
                slug = tool.get("slug")
                if not slug:
                    continue
                tool_file = tools_dir / slug / "index.html"
                if not tool_file.is_file():
                    issues.append(f"Missing canonical HTML for tool '{slug}' at {tool_file}")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "Existence Gate",
            "issues": issues,
        }

    # 22. Title Length Gate (Auxiliary)
    def check_title_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        res = self.check_page_titles_gate(dist_dir)
        res["gate"] = "Title Length Gate"
        return res

    # 23. Snippet Gate (Auxiliary)
    def check_snippet_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        boxes_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                if p.name == "404.html" or "signal" in p.parts:
                    continue
                content = p.read_text(encoding="utf-8", errors="ignore")
                rel = p.relative_to(target).as_posix()
                m_snippet = re.search(r'<(?:aside|div)[^>]*class=["\'][^"\']*quick-answer[^"\']*["\'][^>]*>(.*?)</(?:aside|div)>', content, re.IGNORECASE | re.DOTALL)
                if m_snippet:
                    boxes_checked += 1
                    snippet_text = re.sub(r"<[^>]+>", " ", m_snippet.group(1))
                    words = [w for w in snippet_text.split() if w.strip()]
                    if not (40 <= len(words) <= 60):
                        issues.append(f"Quick-answer snippet has {len(words)} words (expected 40-60) in {rel}")

                    parser = SinglePassSEODocumentParser(self.brand_domain)
                    parser.feed(content)
                    if parser.has_nosnippet:
                        issues.append(f"Page {rel} contains 'nosnippet' directive, revoking search and AI snippet eligibility")
                    if parser.max_snippet is not None:
                        if parser.max_snippet == 0:
                            issues.append(f"Page {rel} contains 'max-snippet:0' directive, revoking search snippet eligibility")
                        elif parser.max_snippet > 0 and parser.quick_answer_text:
                            if len(parser.quick_answer_text) > parser.max_snippet:
                                issues.append(f"Page {rel} quick-answer ({len(parser.quick_answer_text)} chars) exceeds max-snippet:{parser.max_snippet} limit")
                    if parser.quick_answer_has_data_nosnippet:
                        issues.append(f"Page {rel} quick-answer container or ancestor contains 'data-nosnippet', excluding answer from search snippets and AI Overviews")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "Snippet Gate",
            "boxes_checked": boxes_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # Snippet Eligibility Gate
    def check_snippet_eligibility_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        pages_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                if p.name == "404.html" or "signal" in p.parts:
                    continue
                pages_checked += 1
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                parser = SinglePassSEODocumentParser(self.brand_domain)
                parser.feed(content)

                if parser.has_nosnippet:
                    issues.append(f"Page {rel} contains 'nosnippet' directive, revoking search and AI snippet eligibility")
                if parser.has_noindex:
                    issues.append(f"Page {rel} contains 'noindex' directive, revoking search and AI snippet eligibility")
                if parser.max_snippet is not None:
                    if parser.max_snippet == 0:
                        issues.append(f"Page {rel} contains 'max-snippet:0' directive, revoking search snippet eligibility")
                    elif parser.max_snippet > 0 and parser.quick_answer_text:
                        if len(parser.quick_answer_text) > parser.max_snippet:
                            issues.append(f"Page {rel} quick-answer ({len(parser.quick_answer_text)} chars) exceeds max-snippet:{parser.max_snippet} limit")
                if parser.quick_answer_has_data_nosnippet:
                    issues.append(f"Page {rel} quick-answer container or ancestor contains 'data-nosnippet', excluding answer from search snippets and AI Overviews")
                if parser.root_has_data_nosnippet:
                    issues.append(f"Page {rel} root or main container contains 'data-nosnippet', excluding content from search snippets and AI Overviews")

            headers_file = target / "_headers"
            if headers_file.is_file():
                current_route = ""
                non_public_prefixes = ("/signal", "/staging", "/test", "/tests", "/syndication")
                training_bot_names = {b.lower() for b in AI_TRAINING_BOTS}
                search_bot_names = {b.lower() for b in AI_SEARCH_BOTS} | {b.lower() for b in AI_USER_TRIGGERED_BOTS} | {"robots", "claude-web"}

                for raw_line in headers_file.read_text(encoding="utf-8", errors="ignore").splitlines():
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
                                h_val_strip = h_val.strip()
                                # Bot-specific directive check (e.g., "gptbot: noindex" or "googlebot: nosnippet")
                                if ":" in h_val_strip:
                                    prefix_candidate, directive_candidate = [x.strip() for x in h_val_strip.split(":", 1)]
                                    prefix_lower = prefix_candidate.lower()
                                    if prefix_lower in training_bot_names:
                                        # Model training bots restriction is allowed and does not revoke search/AI snippet eligibility
                                        continue
                                    elif prefix_lower in search_bot_names:
                                        directive_lower = directive_candidate.lower()
                                        if "nosnippet" in directive_lower:
                                            issues.append(f"_headers applies 'nosnippet' to public route '{current_route}' for bot '{prefix_lower}' via X-Robots-Tag")
                                        if re.search(r'max-snippet\s*:\s*0\b', directive_lower):
                                            issues.append(f"_headers applies 'max-snippet:0' to public route '{current_route}' for bot '{prefix_lower}' via X-Robots-Tag")
                                        if "noindex" in directive_lower or re.search(r'\bnone\b', directive_lower):
                                            issues.append(f"_headers applies 'noindex' to public route '{current_route}' for bot '{prefix_lower}' via X-Robots-Tag")
                                        continue

                                # Global directive or non-bot directive (e.g., "noindex, nosnippet", "max-snippet:0")
                                val_lower = h_val.lower()
                                if "nosnippet" in val_lower:
                                    issues.append(f"_headers applies 'nosnippet' to public route '{current_route}' via X-Robots-Tag")
                                if re.search(r'max-snippet\s*:\s*0\b', val_lower):
                                    issues.append(f"_headers applies 'max-snippet:0' to public route '{current_route}' via X-Robots-Tag")
                                if "noindex" in val_lower or re.search(r'\bnone\b', val_lower):
                                    issues.append(f"_headers applies 'noindex' to public route '{current_route}' via X-Robots-Tag")

            robots_file = target / "robots.txt"
            if robots_file.is_file():
                robots_content = robots_file.read_text(encoding="utf-8", errors="ignore")
                sections = self.parse_robots_txt_sections(robots_content)
                for bot in AI_SEARCH_BOTS + AI_USER_TRIGGERED_BOTS:
                    if self.is_bot_blocked(bot, "/", sections):
                        issues.append(f"robots.txt disallows AI search/user bot '{bot}' on root '/', revoking AI crawl access and snippet eligibility")
                    elif self.is_bot_blocked(bot, "/tools/", sections):
                        issues.append(f"robots.txt disallows AI search/user bot '{bot}' on '/tools/', revoking AI crawl access and snippet eligibility")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_snippet_eligibility_gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    def check_ai_crawl_access_and_snippet_eligibility_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        res = self.check_snippet_eligibility_gate(dist_dir)
        res["gate"] = "check_ai_crawl_access_and_snippet_eligibility_gate"
        return res

    check_ai_crawl_access_gate = check_ai_crawl_access_and_snippet_eligibility_gate

    def verify_ai_crawl_access_and_snippet_eligibility(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        return self.check_ai_crawl_access_and_snippet_eligibility_gate(dist_dir)

    # Factor 2: Query-Answer Match Gate (+2.15)
    def check_query_answer_match_gate(
        self,
        dist_dir: Optional[Path] = None,
        target_queries: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Mechanical verification gate for Factor 2: Query-Answer Match (+2.15).
        Verifies direct query-answer alignment in initial viewport:
        1. Content pages must contain a quick-answer container (<div class='quick-answer'> or <aside class='quick-answer'>).
        2. Container must be non-empty and populated with 40-60 words.
        3. Initial viewport positioning: strictly placed after <h1> introductory header and before secondary <h2> sections.
        4. Passage-level answer relevance: sentence boundaries (1-5 sentences with terminal punctuation), character density (3.0-15.0 chars/word).
        5. Semantic alignment: query terms from target query must match >= 50% of core tokens.
        6. Zero forbidden jargon, zero evasive summaries, zero keyword stuffing, and zero forbidden dashes.
        Zero em-dashes. Zero en-dashes.
        """
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues: List[str] = []
        pages_checked = 0
        if target.exists():
            for p in sorted(target.glob("**/*.html")):
                if p.name == "404.html" or "signal" in p.parts or "static" in p.parts:
                    continue
                rel = p.relative_to(target).as_posix()
                if rel in ("privacy/index.html", "about/index.html", "terms/index.html"):
                    continue
                pages_checked += 1
                content = p.read_text(encoding="utf-8", errors="ignore")
                t_query = None
                if target_queries and rel in target_queries:
                    t_query = target_queries[rel]
                res = verify_html_query_answer_match(content, target_query=t_query, rel_path=rel)
                if res["issues"]:
                    issues.extend(res["issues"])

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_query_answer_match_gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    check_query_answer_gate = check_query_answer_match_gate

    def verify_query_answer_match(
        self,
        dist_dir: Optional[Path] = None,
        target_queries: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        return self.check_query_answer_match_gate(dist_dir=dist_dir, target_queries=target_queries)

    # Factor 3: Brand / Entity in LLM Memory Gate (+2.08)
    def check_brand_entity_in_llm_memory_gate(
        self,
        dist_dir: Optional[Path] = None,
        brand_name: Optional[str] = None,
        brand_domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Mechanical verification gate for Factor 3: Brand / Entity in LLM Memory (+2.08).
        Enforces canonical entity definitions, unambiguous entity taxonomy, and sameAs array
        linking to Wikidata and authoritative profiles across structured data.
        Zero em-dashes. Zero en-dashes.
        """
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues: List[str] = []
        pages_checked = 0
        entities_found = 0
        b_name = brand_name or self.brand_name
        b_domain = brand_domain or self.brand_domain

        if target.exists():
            for p in sorted(target.glob("**/*.html")):
                if p.name == "404.html" or "signal" in p.parts or "static" in p.parts:
                    continue
                rel = p.relative_to(target).as_posix()
                if rel in ("privacy/index.html", "about/index.html", "terms/index.html"):
                    continue
                pages_checked += 1
                content = p.read_text(encoding="utf-8", errors="ignore")
                res = verify_html_brand_entity_in_llm_memory(
                    content,
                    brand_name=b_name,
                    brand_domain=b_domain,
                    rel_path=rel,
                )
                if res["issues"]:
                    issues.extend(res["issues"])
                entities_found += res.get("entities_count", 0)

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_brand_entity_in_llm_memory_gate",
            "pages_checked": pages_checked,
            "entities_found": entities_found,
            "violations_count": len(issues),
            "issues": issues,
        }

    check_brand_entity_gate = check_brand_entity_in_llm_memory_gate
    check_entity_memory_gate = check_brand_entity_in_llm_memory_gate

    def verify_brand_entity_in_llm_memory(
        self,
        dist_dir: Optional[Path] = None,
        brand_name: Optional[str] = None,
        brand_domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.check_brand_entity_in_llm_memory_gate(
            dist_dir=dist_dir,
            brand_name=brand_name,
            brand_domain=brand_domain,
        )

    # Factor 4: Citable / Specific Facts Gate (+2.07)
    def check_citable_specific_facts_gate(
        self,
        dist_dir: Optional[Path] = None,
        min_statutory_citations: int = 1,
        min_numeric_facts: int = 3,
        require_data_table: bool = True,
    ) -> Dict[str, Any]:
        """
        Mechanical verification gate for Factor 4: Citable / Specific Facts (+2.07).
        Enforces high-density verifiable statistics, clear facts, numbers, primary statutory citations
        (CFR, USC, IRC, IRS codes), data tables, and extractable data points across every generated page.
        Zero em-dashes. Zero en-dashes.
        """
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues: List[str] = []
        pages_checked = 0
        total_citations = 0
        total_numeric_facts = 0
        total_tables = 0
        if target.exists():
            for p in sorted(target.glob("**/*.html")):
                if p.name == "404.html" or "signal" in p.parts or "static" in p.parts:
                    continue
                rel = p.relative_to(target).as_posix()
                if rel in ("privacy/index.html", "about/index.html", "terms/index.html"):
                    continue
                pages_checked += 1
                content = p.read_text(encoding="utf-8", errors="ignore")
                res = verify_html_citable_specific_facts(
                    content,
                    rel_path=rel,
                    min_statutory_citations=min_statutory_citations,
                    min_numeric_facts=min_numeric_facts,
                    require_data_table=require_data_table,
                )
                if res["issues"]:
                    issues.extend(res["issues"])
                total_citations += res.get("statutory_citations_count", 0)
                total_numeric_facts += res.get("numeric_facts_count", 0)
                total_tables += res.get("tables_count", 0)

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_citable_specific_facts_gate",
            "pages_checked": pages_checked,
            "statutory_citations_found": total_citations,
            "numeric_facts_found": total_numeric_facts,
            "data_tables_found": total_tables,
            "violations_count": len(issues),
            "issues": issues,
        }

    check_citable_facts_gate = check_citable_specific_facts_gate
    check_specific_facts_gate = check_citable_specific_facts_gate

    def verify_citable_specific_facts(
        self,
        dist_dir: Optional[Path] = None,
        min_statutory_citations: int = 1,
        min_numeric_facts: int = 3,
        require_data_table: bool = True,
    ) -> Dict[str, Any]:
        return self.check_citable_specific_facts_gate(
            dist_dir=dist_dir,
            min_statutory_citations=min_statutory_citations,
            min_numeric_facts=min_numeric_facts,
            require_data_table=require_data_table,
        )

    def check_organic_fan_out_coverage_gate(
        self,
        dist_dir: Optional[Path] = None,
        min_subqueries: int = 2,
        min_variants: int = 2,
        require_reciprocal: bool = True,
        min_words_per_answer: int = 15,
        min_total_words: int = 150,
        required_subtopics: Optional[List[str]] = None,
        min_subtopic_coverage: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Mechanical verification gate for Factor 5: Organic Fan-Out Coverage Rankings (+1.91).
        Enforces clustered subqueries, related sub-questions, secondary intent coverage,
        calculation variant containers, and reciprocal cross-links without thin page cannibalization.
        Evaluates page set fan-out subtopic coverage across ordinary SEO dimensions.
        Zero em-dashes. Zero en-dashes.
        """
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues: List[str] = []
        pages_checked = 0
        total_subqueries = 0
        total_variants = 0
        total_cross_links = 0
        total_orphaned = 0
        page_set: Dict[str, str] = {}
        if target.exists():
            for p in sorted(target.glob("**/*.html")):
                if p.name == "404.html" or "signal" in p.parts or "static" in p.parts:
                    continue
                rel = p.relative_to(target).as_posix()
                if rel in ("privacy/index.html", "about/index.html", "terms/index.html"):
                    continue
                pages_checked += 1
                content = p.read_text(encoding="utf-8", errors="ignore")
                page_set[rel] = content
                res = verify_html_organic_fan_out_coverage(
                    content,
                    rel_path=rel,
                    min_subqueries=min_subqueries,
                    min_variants=min_variants,
                    require_reciprocal=require_reciprocal,
                    min_words_per_answer=min_words_per_answer,
                    min_total_words=min_total_words,
                )
                if res["issues"]:
                    issues.extend(res["issues"])
                total_subqueries += res.get("subqueries_count", 0)
                total_variants += res.get("calculation_variants_count", 0)
                total_cross_links += res.get("cross_links_count", 0)
                total_orphaned += res.get("orphaned_nodes_count", 0)

        covered_subtopics: List[str] = []
        missing_subtopics: List[str] = []
        page_set_coverage_ratio: float = 1.0

        if len(page_set) > 1 or (len(page_set) > 0 and required_subtopics is not None):
            cov_ratio = min_subtopic_coverage if min_subtopic_coverage is not None else 0.6
            ps_res = evaluate_page_set_fan_out_coverage(
                pages=page_set,
                required_subtopics=required_subtopics,
                min_coverage_ratio=cov_ratio,
            )
            covered_subtopics = ps_res.get("covered_subtopics", [])
            missing_subtopics = ps_res.get("missing_subtopics", [])
            page_set_coverage_ratio = ps_res.get("page_set_coverage_ratio", 1.0)
            if missing_subtopics:
                issues.extend(ps_res.get("issues", []))

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_organic_fan_out_coverage_gate",
            "pages_checked": pages_checked,
            "subqueries_found": total_subqueries,
            "calculation_variants_found": total_variants,
            "cross_links_found": total_cross_links,
            "orphaned_nodes_found": total_orphaned,
            "covered_subtopics": covered_subtopics,
            "missing_subtopics": missing_subtopics,
            "page_set_coverage_ratio": page_set_coverage_ratio,
            "violations_count": len(issues),
            "issues": issues,
        }

    check_fan_out_coverage_gate = check_organic_fan_out_coverage_gate
    check_organic_fan_out_gate = check_organic_fan_out_coverage_gate

    def verify_organic_fan_out_coverage(
        self,
        dist_dir: Optional[Path] = None,
        min_subqueries: int = 2,
        min_variants: int = 2,
        require_reciprocal: bool = True,
        min_words_per_answer: int = 15,
        min_total_words: int = 150,
        required_subtopics: Optional[List[str]] = None,
        min_subtopic_coverage: Optional[float] = None,
    ) -> Dict[str, Any]:
        return self.check_organic_fan_out_coverage_gate(
            dist_dir=dist_dir,
            min_subqueries=min_subqueries,
            min_variants=min_variants,
            require_reciprocal=require_reciprocal,
            min_words_per_answer=min_words_per_answer,
            min_total_words=min_total_words,
            required_subtopics=required_subtopics,
            min_subtopic_coverage=min_subtopic_coverage,
        )

    def verify_page_set_fan_out_coverage(
        self,
        dist_dir: Optional[Path] = None,
        min_subqueries: int = 2,
        min_variants: int = 2,
        require_reciprocal: bool = True,
        min_words_per_answer: int = 15,
        min_total_words: int = 150,
        required_subtopics: Optional[List[str]] = None,
        min_subtopic_coverage: Optional[float] = None,
    ) -> Dict[str, Any]:
        return self.check_organic_fan_out_coverage_gate(
            dist_dir=dist_dir,
            min_subqueries=min_subqueries,
            min_variants=min_variants,
            require_reciprocal=require_reciprocal,
            min_words_per_answer=min_words_per_answer,
            min_total_words=min_total_words,
            required_subtopics=required_subtopics,
            min_subtopic_coverage=min_subtopic_coverage,
        )

    # 24. Factor 6: Organic Search Ranking Gate (+1.89)
    def check_organic_search_ranking_gate(
        self,
        dist_dir: Optional[Path] = None,
        max_ssr_latency_ms: float = 100.0,
    ) -> Dict[str, Any]:
        """
        Mechanical verification gate for Factor 6: Organic Search Ranking (+1.89).
        Verifies core SEO hygiene through simulated mock crawler traversal:
        1. Title tag boundaries (30-65 chars, no double pipes)
        2. Single H1 presence and hierarchy (no duplicate H1s, non-empty)
        3. Meta description limits (70-160 chars, no truncation)
        4. Canonical consistency without drift or unnormalized URLs
        5. Internal link graph traversals and dead route detection
        6. Sub-100ms static SSR response benchmarks
        Zero em-dashes. Zero en-dashes.
        """
        target = Path(dist_dir) if dist_dir else self.dist_dir
        crawler = MockSearchEngineCrawler(base_domain=self.domain, max_ssr_latency_ms=max_ssr_latency_ms)
        return crawler.crawl_directory(target, max_ssr_latency_ms=max_ssr_latency_ms)

    check_traditional_organic_search_gate = check_organic_search_ranking_gate
    check_core_seo_hygiene_gate = check_organic_search_ranking_gate

    def verify_organic_search_ranking(
        self,
        dist_dir: Optional[Path] = None,
        max_ssr_latency_ms: float = 100.0,
    ) -> Dict[str, Any]:
        return self.check_organic_search_ranking_gate(
            dist_dir=dist_dir,
            max_ssr_latency_ms=max_ssr_latency_ms,
        )

    # Factor 7: Unique / First-Party Information Gate (+1.85)
    def check_unique_first_party_information_gate(
        self,
        dist_dir: Optional[Path] = None,
        min_manifests: int = 1,
        require_multi_dataset: bool = True,
    ) -> Dict[str, Any]:
        """
        Mechanical verification gate for Factor 7: Unique / First-Party Information (+1.85).
        Enforces authoritative content grounded in original data, firsthand calculations,
        proprietary models, multi-dataset enrichment joining statutory rates with economic/BLS/FRED data,
        and unique calculation manifests across rendered static HTML trees.
        Zero em-dashes. Zero en-dashes.
        """
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues: List[str] = []
        pages_checked = 0
        total_manifests = 0
        total_joins = 0
        total_orphans = 0

        manifests_dir = target / "manifests" if target.exists() else None

        if target.exists():
            for p in sorted(target.glob("**/*.html")):
                if p.name == "404.html" or "signal" in p.parts or "static" in p.parts:
                    continue
                rel = p.relative_to(target).as_posix()
                if rel in ("index.html", "tools/index.html", "privacy/index.html", "about/index.html", "terms/index.html"):
                    continue
                pages_checked += 1
                content = p.read_text(encoding="utf-8", errors="ignore")
                res = verify_html_unique_first_party_information(
                    content,
                    rel_path=rel,
                    manifests_dir=manifests_dir,
                    require_multi_dataset=require_multi_dataset,
                )
                if res["issues"]:
                    issues.extend(res["issues"])
                total_manifests += res.get("manifests_count", 0)
                total_joins += res.get("multi_dataset_joins_count", 0)
                total_orphans += res.get("orphaned_tables_count", 0)

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_unique_first_party_information_gate",
            "pages_checked": pages_checked,
            "manifests_checked": total_manifests,
            "multi_dataset_joins_found": total_joins,
            "orphaned_tables_found": total_orphans,
            "violations_count": len(issues),
            "issues": issues,
        }

    check_first_party_information_gate = check_unique_first_party_information_gate
    check_first_party_assets_gate = check_unique_first_party_information_gate
    check_firsthand_calculations_gate = check_unique_first_party_information_gate
    check_proprietary_models_gate = check_unique_first_party_information_gate

    def verify_unique_first_party_information(
        self,
        dist_dir: Optional[Path] = None,
        min_manifests: int = 1,
        require_multi_dataset: bool = True,
    ) -> Dict[str, Any]:
        return self.check_unique_first_party_information_gate(
            dist_dir=dist_dir,
            min_manifests=min_manifests,
            require_multi_dataset=require_multi_dataset,
        )

    # Factor 8: Cross-Web Consensus & Corroboration Gate (+1.81)
    def check_cross_web_consensus_and_corroboration_gate(
        self,
        dist_dir: Optional[Path] = None,
        require_corroboration: bool = False,
    ) -> Dict[str, Any]:
        """
        Mechanical verification gate for Factor 8: Cross-Web Consensus & Corroboration (+1.81).
        Enforces agreement on baseline facts and statutory constants across the web,
        verifying standard tax brackets, statutory limits, and standard deduction values
        against official published schedules.
        Zero em-dashes. Zero en-dashes.
        """
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues: List[str] = []
        pages_checked = 0
        total_constants = 0

        if target.exists():
            for p in sorted(target.glob("**/*.html")):
                if p.name == "404.html" or "signal" in p.parts or "static" in p.parts:
                    continue
                rel = p.relative_to(target).as_posix()
                if rel in ("index.html", "tools/index.html", "privacy/index.html", "about/index.html", "terms/index.html") and not require_corroboration:
                    continue
                pages_checked += 1
                content = p.read_text(encoding="utf-8", errors="ignore")
                res = verify_html_cross_web_consensus_and_corroboration(
                    content,
                    rel_path=rel,
                    require_corroboration=require_corroboration,
                )
                if res["issues"]:
                    issues.extend(res["issues"])
                total_constants += res.get("verified_constants_count", 0)

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_cross_web_consensus_and_corroboration_gate",
            "pages_checked": pages_checked,
            "statutory_constants_verified": total_constants,
            "violations_count": len(issues),
            "issues": issues,
        }

    check_cross_web_corroboration_gate = check_cross_web_consensus_and_corroboration_gate
    check_statutory_consensus_gate = check_cross_web_consensus_and_corroboration_gate
    check_baseline_fact_agreement_gate = check_cross_web_consensus_and_corroboration_gate
    check_statutory_constants_corroboration_gate = check_cross_web_consensus_and_corroboration_gate

    def verify_cross_web_consensus_and_corroboration(
        self,
        dist_dir: Optional[Path] = None,
        require_corroboration: bool = False,
    ) -> Dict[str, Any]:
        return self.check_cross_web_consensus_and_corroboration_gate(
            dist_dir=dist_dir,
            require_corroboration=require_corroboration,
        )

    verify_cross_web_corroboration = verify_cross_web_consensus_and_corroboration

    # Factor 9: Source / Publisher Reputation Gate (+1.78)
    def check_source_publisher_reputation_gate(
        self,
        dist_dir: Optional[Path] = None,
        require_strict: bool = False,
    ) -> Dict[str, Any]:
        """
        Mechanical verification gate for Factor 9: Source / Publisher Reputation (+1.78).
        Enforces publisher authority, author credentials, Person and Organization schema,
        editorial review policies, datePublished and dateModified freshness signals,
        and about and contact linkages across rendered static HTML document trees.
        Zero em-dashes. Zero en-dashes.
        """
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues: List[str] = []
        pages_checked = 0
        total_authors = 0
        total_publishers = 0

        if target.exists():
            for p in sorted(target.glob("**/*.html")):
                if p.name == "404.html" or "signal" in p.parts or "static" in p.parts:
                    continue
                rel = p.relative_to(target).as_posix()
                if rel in ("index.html", "tools/index.html", "privacy/index.html", "terms/index.html") and not require_strict:
                    continue
                pages_checked += 1
                content = p.read_text(encoding="utf-8", errors="ignore")
                res = verify_html_source_publisher_reputation(
                    content,
                    rel_path=rel,
                    require_strict=require_strict,
                )
                if res["issues"]:
                    issues.extend(res["issues"])
                total_authors += res.get("authors_count", 0)
                total_publishers += res.get("publishers_count", 0)

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_source_publisher_reputation_gate",
            "pages_checked": pages_checked,
            "authors_verified": total_authors,
            "publishers_verified": total_publishers,
            "violations_count": len(issues),
            "issues": issues,
        }

    check_publisher_reputation_gate = check_source_publisher_reputation_gate
    check_publisher_authority_gate = check_source_publisher_reputation_gate
    check_author_credentials_gate = check_source_publisher_reputation_gate
    check_editorial_policy_gate = check_source_publisher_reputation_gate

    def verify_source_publisher_reputation(
        self,
        dist_dir: Optional[Path] = None,
        require_strict: bool = False,
    ) -> Dict[str, Any]:
        return self.check_source_publisher_reputation_gate(
            dist_dir=dist_dir,
            require_strict=require_strict,
        )

    verify_publisher_reputation = verify_source_publisher_reputation

    # Factor 10: Extractable Content Structure Gate (+1.69)
    def check_extractable_content_structure_gate(
        self,
        dist_dir: Optional[Path] = None,
        require_strict: bool = False,
    ) -> Dict[str, Any]:
        """
        Mechanical verification gate for Factor 10: Extractable Content Structure (+1.69).
        Enforces strict semantic HTML heading hierarchies without skipped levels,
        data tables with scoped column headers (scope="col"), ordered lists for procedural steps,
        and clean passage-level blocks across rendered static HTML document trees.
        Zero em-dashes. Zero en-dashes.
        """
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues: List[str] = []
        pages_checked = 0
        total_headings = 0
        total_tables = 0
        total_steps = 0

        if target.exists():
            for p in sorted(target.glob("**/*.html")):
                if p.name == "404.html" or "signal" in p.parts or "static" in p.parts:
                    continue
                rel = p.relative_to(target).as_posix()
                if rel in ("index.html", "tools/index.html", "privacy/index.html", "terms/index.html") and not require_strict:
                    continue
                pages_checked += 1
                content = p.read_text(encoding="utf-8", errors="ignore")
                res = verify_html_extractable_content_structure(
                    content,
                    rel_path=rel,
                    require_strict=require_strict,
                )
                if res["issues"]:
                    issues.extend(res["issues"])
                total_headings += res.get("headings_count", 0)
                total_tables += res.get("tables_count", 0)
                total_steps += res.get("ordered_steps_count", 0)

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_extractable_content_structure_gate",
            "pages_checked": pages_checked,
            "headings_verified": total_headings,
            "tables_verified": total_tables,
            "ordered_steps_verified": total_steps,
            "violations_count": len(issues),
            "issues": issues,
        }

    check_extractable_structure_gate = check_extractable_content_structure_gate
    check_semantic_heading_hierarchy_gate = check_extractable_content_structure_gate
    check_scoped_table_headers_gate = check_extractable_content_structure_gate
    check_procedural_ordered_steps_gate = check_extractable_content_structure_gate

    def verify_extractable_content_structure(
        self,
        dist_dir: Optional[Path] = None,
        require_strict: bool = False,
    ) -> Dict[str, Any]:
        return self.check_extractable_content_structure_gate(
            dist_dir=dist_dir,
            require_strict=require_strict,
        )

    verify_extractable_structure = verify_extractable_content_structure

    # Factor 11: Answer Prominence (+1.65)
    def check_answer_prominence_gate(
        self,
        dist_dir: Optional[Path] = None,
        max_words: int = 300,
        require_strict: bool = False,
    ) -> Dict[str, Any]:
        """
        Mechanical verification gate for Factor 11: Answer Prominence (+1.65).
        Verifies that pages place the direct answer or core calculation widget
        above the fold within the first 300 words of the body before secondary discussion.
        Zero em-dashes. Zero en-dashes.
        """
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues: List[str] = []
        pages_checked = 0
        total_answers = 0
        total_widgets = 0

        if target.exists():
            for p in sorted(target.glob("**/*.html")):
                if p.name == "404.html" or "signal" in p.parts or "static" in p.parts:
                    continue
                rel = p.relative_to(target).as_posix()
                if rel in ("index.html", "tools/index.html", "privacy/index.html", "terms/index.html", "about/index.html", "contact/index.html") and not require_strict:
                    continue
                pages_checked += 1
                content = p.read_text(encoding="utf-8", errors="ignore")
                res = verify_html_answer_prominence(
                    content,
                    rel_path=rel,
                    max_words=max_words,
                    require_strict=require_strict,
                )
                if res["issues"]:
                    issues.extend(res["issues"])
                if res.get("answer_found"):
                    if res.get("answer_type") == "calculation_widget":
                        total_widgets += 1
                    else:
                        total_answers += 1

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_answer_prominence_gate",
            "pages_checked": pages_checked,
            "answers_verified": total_answers,
            "widgets_verified": total_widgets,
            "violations_count": len(issues),
            "issues": issues,
        }

    check_answer_above_fold_gate = check_answer_prominence_gate
    check_core_answer_prominence_gate = check_answer_prominence_gate
    check_direct_answer_prominence_gate = check_answer_prominence_gate
    check_calculation_widget_prominence_gate = check_answer_prominence_gate
    check_early_answer_block_gate = check_answer_prominence_gate

    def verify_answer_prominence(
        self,
        dist_dir: Optional[Path] = None,
        max_words: int = 300,
        require_strict: bool = False,
    ) -> Dict[str, Any]:
        return self.check_answer_prominence_gate(
            dist_dir=dist_dir,
            max_words=max_words,
            require_strict=require_strict,
        )

    verify_answer_above_fold = verify_answer_prominence
    verify_core_answer_prominence = verify_answer_prominence

    # Factor 12: Structured Data (+0.80)
    def check_structured_data_gate(
        self,
        dist_dir: Optional[Path] = None,
        require_strict: bool = False,
        require_free_app_schema: bool = False,
    ) -> Dict[str, Any]:
        """
        Mechanical verification gate for Factor 12: Structured Data (+0.80).
        Verifies machine-readable Schema.org JSON-LD markup validating SoftwareApplication,
        WebApplication, Product, FAQPage, HowTo, and Dataset schemas with zero parse errors,
        connected graph structures, zero unanchored leaves, and zero forbidden dashes.
        Zero em-dashes. Zero en-dashes.
        """
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues: List[str] = []
        pages_checked = 0
        total_schemas = 0
        total_target_entities = 0

        if target.exists():
            for p in sorted(target.glob("**/*.html")):
                if p.name == "404.html" or "signal" in p.parts or "static" in p.parts:
                    continue
                rel = p.relative_to(target).as_posix()
                if rel in ("index.html", "tools/index.html", "privacy/index.html", "terms/index.html") and not require_strict:
                    continue
                pages_checked += 1
                content = p.read_text(encoding="utf-8", errors="ignore")
                res = verify_html_structured_data(
                    content,
                    rel_path=rel,
                    require_strict=require_strict,
                    require_free_app_schema=require_free_app_schema,
                )
                if res["issues"]:
                    issues.extend(res["issues"])
                total_schemas += len(res.get("schemas_found", []))
                total_target_entities += len(res.get("target_schemas", []))

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_structured_data_gate",
            "pages_checked": pages_checked,
            "schemas_verified": total_schemas,
            "target_entities_verified": total_target_entities,
            "violations_count": len(issues),
            "issues": issues,
        }

    check_schema_org_structured_data_gate = check_structured_data_gate
    check_jsonld_structured_data_gate = check_structured_data_gate
    check_schema_graphs_gate = check_structured_data_gate
    check_target_entity_schemas_gate = check_structured_data_gate
    check_machine_readable_schemas_gate = check_structured_data_gate

    def verify_structured_data(
        self,
        dist_dir: Optional[Path] = None,
        require_strict: bool = False,
        require_free_app_schema: bool = False,
    ) -> Dict[str, Any]:
        return self.check_structured_data_gate(
            dist_dir=dist_dir,
            require_strict=require_strict,
            require_free_app_schema=require_free_app_schema,
        )


    verify_schema_org_structured_data = verify_structured_data
    verify_jsonld_structured_data = verify_structured_data
    verify_schema_graphs = verify_structured_data

    # Factor 13: llms.txt File (+0.05)
    def check_llms_txt_gate(
        self,
        dist_dir: Optional[Path] = None,
        require_strict: bool = False,
    ) -> Dict[str, Any]:
        """
        Mechanical verification gate for Factor 13: llms.txt File (+0.05).
        Verifies curated llms.txt and expanded llms-full.txt files conforming to
        the llmstxt.org specification with concise markdown summaries linking top category hubs
        without leaking private administrative routes or internal paths, and zero forbidden dashes.
        Zero em-dashes. Zero en-dashes.
        """
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues: List[str] = []
        llms_txt_path = target / "llms.txt"
        llms_full_txt_path = target / "llms-full.txt"
        manifests_checked = 0
        hubs_verified = 0

        has_llms = target.exists() and llms_txt_path.is_file()
        has_full = target.exists() and llms_full_txt_path.is_file()

        if require_strict:
            if not has_llms:
                issues.append(f"Missing llms.txt manifest at {llms_txt_path}")
            if not has_full:
                issues.append(f"Missing llms-full.txt manifest at {llms_full_txt_path}")

        if has_llms:
            manifests_checked += 1
            raw_llms = llms_txt_path.read_text(encoding="utf-8", errors="ignore")
            res_llms = verify_llms_txt_content(
                raw_llms,
                rel_path="llms.txt",
                is_full=False,
                require_strict=require_strict,
            )
            if res_llms["issues"]:
                issues.extend(res_llms["issues"])
            hubs_verified += res_llms.get("hubs_verified", 0)

        if has_full:
            manifests_checked += 1
            raw_full = llms_full_txt_path.read_text(encoding="utf-8", errors="ignore")
            res_full = verify_llms_txt_content(
                raw_full,
                rel_path="llms-full.txt",
                is_full=True,
                require_strict=require_strict,
            )
            if res_full["issues"]:
                issues.extend(res_full["issues"])

        if (has_llms and not has_full) or (has_full and not has_llms):
            missing_name = "llms-full.txt" if has_llms else "llms.txt"
            issues.append(f"Incomplete manifest pair: found only one of llms.txt / llms-full.txt; missing {missing_name}")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_llms_txt_gate",
            "manifests_checked": manifests_checked,
            "hubs_verified": hubs_verified,
            "violations_count": len(issues),
            "issues": issues,
        }

    check_llms_txt_file_gate = check_llms_txt_gate
    check_llms_full_txt_gate = check_llms_txt_gate
    check_llmstxt_gate = check_llms_txt_gate
    check_llms_manifest_gate = check_llms_txt_gate
    check_curated_llms_txt_gate = check_llms_txt_gate

    def verify_llms_txt(
        self,
        dist_dir: Optional[Path] = None,
        require_strict: bool = False,
    ) -> Dict[str, Any]:
        return self.check_llms_txt_gate(
            dist_dir=dist_dir,
            require_strict=require_strict,
        )

    verify_llms_txt_file = verify_llms_txt
    verify_llms_full_txt = verify_llms_txt
    verify_llmstxt = verify_llms_txt
    verify_curated_llms_txt = verify_llms_txt

    # Free Interactive Tool Utility Gate
    def check_tool_utility_gate(
        self,
        dist_dir_or_html: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        """
        Mechanical verification gate for ToolUtilityContract.
        Verifies presence of interactive form or container (<form> or elements with input/action),
        <input> elements paired with <label> or aria-label, and a submit CTA (<button type="submit"> or equivalent).
        Zero em-dashes. Zero en-dashes.
        """
        if isinstance(dist_dir_or_html, str) and ("<" in dist_dir_or_html or "\n" in dist_dir_or_html):
            return verify_html_tool_utility_contract(dist_dir_or_html, rel_path="inline.html")

        target = Path(dist_dir_or_html) if dist_dir_or_html else self.dist_dir
        issues: List[str] = []
        tools_checked = 0

        if target.exists():
            for p in sorted(target.glob("**/*.html")):
                if p.name == "404.html" or "signal" in p.parts or "static" in p.parts:
                    continue
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                is_tool = rel.startswith("tools/") and rel != "tools/index.html"
                has_form_tag = "<form" in content.lower() or 'role="form"' in content.lower()
                if is_tool or has_form_tag:
                    tools_checked += 1
                    res = verify_html_tool_utility_contract(content, rel_path=rel)
                    if res["issues"]:
                        issues.extend(res["issues"])

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_tool_utility_gate",
            "tools_checked": tools_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    verify_tool_utility_contract = check_tool_utility_gate

    # Free WebApplication / SoftwareApplication Schema Gate
    def check_free_web_application_schema_gate(
        self,
        dist_dir_or_html: Optional[Union[str, Path]] = None,
        require_strict: bool = False,
    ) -> Dict[str, Any]:
        """
        Mechanical verification gate for Free WebApplication / SoftwareApplication Schema.
        Validates Schema.org WebApplication or SoftwareApplication JSON-LD defining
        applicationCategory and offers with price '0' and ISO 4217 currency.
        Zero em-dashes. Zero en-dashes.
        """
        if isinstance(dist_dir_or_html, str) and ("<" in dist_dir_or_html or "\n" in dist_dir_or_html):
            return verify_html_free_web_application_schema(dist_dir_or_html, rel_path="inline.html")

        target = Path(dist_dir_or_html) if dist_dir_or_html else self.dist_dir
        issues: List[str] = []
        pages_checked = 0

        if target.exists():
            for p in sorted(target.glob("**/*.html")):
                if p.name == "404.html" or "signal" in p.parts or "static" in p.parts:
                    continue
                rel = p.relative_to(target).as_posix()
                content = p.read_text(encoding="utf-8", errors="ignore")
                is_tool = rel.startswith("tools/") and rel != "tools/index.html"
                has_app_schema = '"webapplication"' in content.lower() or '"softwareapplication"' in content.lower()
                if is_tool or has_app_schema or require_strict:
                    pages_checked += 1
                    res = verify_html_free_web_application_schema(content, rel_path=rel)
                    if res["issues"]:
                        issues.extend(res["issues"])

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "check_free_web_application_schema_gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    verify_free_web_application_schema = check_free_web_application_schema_gate

    # Operational Rate-Limit & Bot Shield Gate
    def check_operational_shield_gate(
        self,
        dist_dir_or_headers: Optional[Union[str, Path, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Mechanical verification gate for Operational Rate-Limit and Bot Shield defense.
        Verifies presence of rate-limit headers (X-RateLimit-Limit), bot challenge protection,
        or client-side caching hooks.
        Zero em-dashes. Zero en-dashes.
        """
        if isinstance(dist_dir_or_headers, dict):
            return verify_rate_limit_and_bot_shield(dist_dir_or_headers)
        if isinstance(dist_dir_or_headers, str) and ("\n" in dist_dir_or_headers or ":" in dist_dir_or_headers):
            return verify_rate_limit_and_bot_shield(dist_dir_or_headers)

        target = Path(dist_dir_or_headers) if dist_dir_or_headers else self.dist_dir
        headers_file = target / "_headers" if target.exists() else None
        if headers_file and headers_file.is_file():
            content = headers_file.read_text(encoding="utf-8", errors="ignore")
            return verify_rate_limit_and_bot_shield(content, context="_headers")

        return verify_rate_limit_and_bot_shield({}, context="missing _headers")

    verify_operational_shield = check_operational_shield_gate


    # 25. Schema Validation Gate (Auxiliary)
    def check_schema_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        res = self.check_schema_markup_gate(dist_dir)
        res["gate"] = "Schema Validation Gate"
        return res

    # 25. Citability Gate (Auxiliary)
    def check_citability_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        pages_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                rel = p.relative_to(target).as_posix()
                if "tools" not in p.parts:
                    continue
                pages_checked += 1
                content = p.read_text(encoding="utf-8", errors="ignore").lower()
                if "<ol" not in content:
                    issues.append(f"Missing <ol> calculation steps procedure in {rel}")
                if "<table" not in content and p.name != "index.html":
                    issues.append(f"Missing <table> comparison data in {rel}")

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "Citability Gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 26. Cleanliness Gate (Auxiliary)
    def check_cleanliness_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues = []
        pages_checked = 0
        if target.exists():
            for p in target.glob("**/*.html"):
                pages_checked += 1
                content = p.read_text(encoding="utf-8", errors="ignore")
                rel = p.relative_to(target).as_posix()

                if "\u2014" in content or "\u2013" in content:
                    issues.append(f"Contains em-dash or en-dash in {rel}")

                content_lower = content.lower()
                for jargon in FORBIDDEN_JARGON:
                    if jargon.lower() in content_lower:
                        issues.append(f"Forbidden jargon or placeholder '{jargon}' detected in {rel}")
                        break

        return {
            "status": "PASS" if not issues else "FAIL",
            "gate": "Cleanliness Gate",
            "pages_checked": pages_checked,
            "violations_count": len(issues),
            "issues": issues,
        }

    # 27. Instant Indexing Gate (Auxiliary)
    def check_indexing_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        issues: List[str] = []
        if not target.exists():
            issues.append(f"Dist directory does not exist: {target}")
            return {
                "gate": "Instant Indexing Gate",
                "passed": False,
                "status": "FAIL",
                "total": 0,
                "clean_urls": 0,
                "blocked": 0,
                "breakdown": {},
                "push_eligible_urls": [],
                "blocked_urls": [],
                "issues": issues,
            }

        from pseofactory.indexing.preflight import IndexingPreflightEngine
        engine = IndexingPreflightEngine(
            domain=self.domain,
            property_id=getattr(self, "property_id", "profithelm"),
            dist_dir=target,
        )
        report = engine.inspect_dist(target)
        if report.total_inspected == 0:
            issues.append(f"No pages found for indexing inspection in {target}")
            return {
                "gate": "Instant Indexing Gate",
                "passed": False,
                "status": "FAIL",
                "total": 0,
                "clean_urls": 0,
                "blocked": 0,
                "breakdown": {},
                "push_eligible_urls": [],
                "blocked_urls": [],
                "issues": issues,
            }

        if not report.is_gate_passed:
            issues.append(
                f"Indexing preflight blocked {report.blocked_count} URLs out of {report.total_inspected}: {report.breakdown}"
            )
            for u in report.blocked_urls[:10]:
                issues.append(f"Blocked URL from indexing: {u}")
            if len(report.blocked_urls) > 10:
                issues.append(f"(...and {len(report.blocked_urls) - 10} more blocked URLs)")

        return {
            "gate": "Instant Indexing Gate",
            "passed": report.is_gate_passed,
            "status": "PASS" if report.is_gate_passed else "FAIL",
            "total": report.total_inspected,
            "clean_urls": len(report.push_eligible_urls),
            "blocked": report.blocked_count,
            "breakdown": report.breakdown,
            "push_eligible_urls": report.push_eligible_urls,
            "blocked_urls": report.blocked_urls,
            "issues": issues,
        }

    # 28. Zyppy 2026 Content Relevance Gate (12 Factors)
    def check_content_relevance_gate(self, dist_dir: Optional[Path] = None) -> Dict[str, Any]:
        target = Path(dist_dir) if dist_dir else self.dist_dir
        parsed_docs: Dict[str, Tuple[Path, str, SinglePassSEODocumentParser]] = {}
        if target.exists():
            for p in target.glob("**/*.html"):
                rel = p.relative_to(target).as_posix()
                raw_html = p.read_text(encoding="utf-8", errors="ignore")
                parser = SinglePassSEODocumentParser(brand_domain=self.domain)
                parser.feed(raw_html)
                parsed_docs[rel] = (p, raw_html, parser)

        pages_scanned = len(parsed_docs)

        manifests_dir = target / "manifests"
        manifest_files = list(manifests_dir.glob("*.json")) if manifests_dir.is_dir() else []
        sitemap_xml = target / "sitemap.xml"
        sitemap_hubs_xml = target / "sitemap-hubs.xml"
        sitemap_leaves_xml = target / "sitemap-leaves.xml"
        feed_xml = target / "feed.xml"
        llms_txt = target / "llms.txt"
        llms_full_txt = target / "llms-full.txt"
        robots_txt = target / "robots.txt"

        endpoints_scanned = len(manifest_files)
        for ep in [sitemap_xml, sitemap_hubs_xml, sitemap_leaves_xml, feed_xml, llms_txt, llms_full_txt, robots_txt]:
            if ep.is_file():
                endpoints_scanned += 1

        vacuous_pass = (pages_scanned < 10 or endpoints_scanned < 5)
        findings: List[Dict[str, Any]] = []

        # Factor 1: Search Intent Match (weight 2.60)
        gaps_1: List[str] = []
        if vacuous_pass:
            gaps_1.append("Vacuous Pass Prevention: pages_scanned < 10 or endpoints_scanned < 5")
        else:
            for rel, (p, raw, parser) in parsed_docs.items():
                if rel in ("404.html", "privacy/index.html", "about/index.html") or "signal" in p.parts or "static" in p.parts:
                    continue
                if self.is_calculation_leaf:
                    leaf_err = self.is_calculation_leaf(rel, p, parser)
                    if leaf_err:
                        gaps_1.append(leaf_err)
                elif rel.startswith("tools/") and rel != "tools/index.html":
                    if not parser.has_calculator:
                        gaps_1.append(f"{rel}: Missing interactive calculator controls or calculation container")

            if len(manifest_files) < self.min_manifests:
                gaps_1.append(f"Insufficient calculation manifests: found {len(manifest_files)}, expected >= {self.min_manifests}")

            for mf in manifest_files:
                try:
                    mdata = json.loads(mf.read_text(encoding="utf-8"))
                    for req_key in ("formula", "inputs", "sample_calculation"):
                        if req_key not in mdata or not mdata[req_key]:
                            gaps_1.append(f"{mf.relative_to(target).as_posix()}: Missing manifest key '{req_key}'")
                except Exception as ex:
                    gaps_1.append(f"{mf.relative_to(target).as_posix()}: JSON parse failure: {ex}")

        findings.append({
            "factor": "Search Intent Match",
            "weight": 2.60,
            "status": "PASS" if not gaps_1 else "FAIL",
            "passed": len(gaps_1) == 0,
            "gap_count": len(gaps_1),
            "pages_scanned": pages_scanned,
            "examples": gaps_1[:3],
        })

        # Factor 2: Page Semantic Relevance (weight 2.34)
        gaps_2: List[str] = []
        if vacuous_pass:
            gaps_2.append("Vacuous Pass Prevention: pages_scanned < 10 or endpoints_scanned < 5")
        else:
            for rel, (p, raw, parser) in parsed_docs.items():
                if rel in ("404.html", "privacy/index.html", "about/index.html", "index.html", "tools/index.html") or "signal" in p.parts or "static" in p.parts:
                    continue
                schema_types = []
                for block in parser.json_ld_blocks:
                    try:
                        sdata = json.loads(block)
                        if isinstance(sdata, dict):
                            st = sdata.get("@type")
                            if isinstance(st, list):
                                schema_types.extend(st)
                            elif st:
                                schema_types.append(st)
                            if "@graph" in sdata and isinstance(sdata["@graph"], list):
                                for gitm in sdata["@graph"]:
                                    gt = gitm.get("@type")
                                    if isinstance(gt, list):
                                        schema_types.extend(gt)
                                    elif gt:
                                        schema_types.append(gt)
                        elif isinstance(sdata, list):
                            for sitm in sdata:
                                st = sitm.get("@type")
                                if st:
                                    schema_types.append(st)
                    except Exception:
                        pass
                unique_types = set(schema_types)
                if len(unique_types) < 2:
                    gaps_2.append(f"{rel}: Unstacked JSON-LD schema (only {len(unique_types)} @type found)")

                all_headings = parser.h1_list + parser.h2_list
                for h in all_headings:
                    words = h.split()
                    if any(len(w) == 1 and w.isupper() and w not in ('A', 'I') for w in words):
                        gaps_2.append(f"{rel}: Chopped entity label in heading ('{h}')")
                        break

        findings.append({
            "factor": "Page Semantic Relevance",
            "weight": 2.34,
            "status": "PASS" if not gaps_2 else "FAIL",
            "passed": len(gaps_2) == 0,
            "gap_count": len(gaps_2),
            "pages_scanned": pages_scanned,
            "examples": gaps_2[:3],
        })

        # Factor 3: Site Topical Authority (weight 2.29)
        gaps_3: List[str] = []
        if vacuous_pass:
            gaps_3.append("Vacuous Pass Prevention: pages_scanned < 10 or endpoints_scanned < 5")
        else:
            for rel, (p, raw, parser) in parsed_docs.items():
                if rel in ("404.html", "privacy/index.html", "about/index.html", "index.html", "tools/index.html") or "signal" in p.parts or "static" in p.parts:
                    continue
                if p.parent != target / "tools" and p.parent.parent == target / "tools":
                    if len(parser.internal_links) < 3:
                        gaps_3.append(f"{rel}: Insufficient internal links ({len(parser.internal_links)} < 3)")
            if not sitemap_xml.is_file() or not sitemap_hubs_xml.is_file() or not sitemap_leaves_xml.is_file():
                gaps_3.append("Missing one or more required sitemaps (sitemap.xml, sitemap-hubs.xml, sitemap-leaves.xml)")
            if not feed_xml.is_file():
                gaps_3.append("Missing syndication feed.xml")

        findings.append({
            "factor": "Site Topical Authority",
            "weight": 2.29,
            "status": "PASS" if not gaps_3 else "FAIL",
            "passed": len(gaps_3) == 0,
            "gap_count": len(gaps_3),
            "pages_scanned": pages_scanned,
            "examples": gaps_3[:3],
        })

        # Factor 4: Title Relevance (weight 2.26)
        gaps_4: List[str] = []
        dangling_stopwords = {"and", "or", "for", "with", "in", "to", "of", "section", "capital"}
        if vacuous_pass:
            gaps_4.append("Vacuous Pass Prevention: pages_scanned < 10 or endpoints_scanned < 5")
        else:
            for rel, (p, raw, parser) in parsed_docs.items():
                if rel == "404.html" or "signal" in p.parts or "static" in p.parts:
                    continue
                t = html.unescape(parser.title)
                if not t:
                    gaps_4.append(f"{rel}: Empty <title>")
                    continue
                if len(t) < 50 or len(t) > 60:
                    gaps_4.append(f"{rel}: Title length {len(t)} outside 50-60 chars ('{t}')")
                if "| |" in t:
                    gaps_4.append(f"{rel}: Delimiter corruption '| |' in title ('{t}')")
                if "\u2014" in t or "\u2013" in t:
                    gaps_4.append(f"{rel}: Title contains em-dash or en-dash ('{t}')")
                base_t = re.sub(rf'\s*\|\s*{re.escape(self.brand_name)}\s*$', '', t, flags=re.IGNORECASE).strip()
                words = base_t.split()
                if words and words[-1].lower() in dangling_stopwords:
                    gaps_4.append(f"{rel}: Dangling trailing stopword '{words[-1]}' before brand suffix ('{t}')")

        findings.append({
            "factor": "Title Relevance",
            "weight": 2.26,
            "status": "PASS" if not gaps_4 else "FAIL",
            "passed": len(gaps_4) == 0,
            "gap_count": len(gaps_4),
            "pages_scanned": pages_scanned,
            "examples": gaps_4[:3],
        })

        # Factor 5: Passage-level Relevance (weight 1.99)
        gaps_5: List[str] = []
        if vacuous_pass:
            gaps_5.append("Vacuous Pass Prevention: pages_scanned < 10 or endpoints_scanned < 5")
        else:
            for rel, (p, raw, parser) in parsed_docs.items():
                if rel in ("404.html", "privacy/index.html", "about/index.html", "index.html", "tools/index.html") or "signal" in p.parts or "static" in p.parts:
                    continue
                qa = parser.quick_answer_text
                if not qa:
                    gaps_5.append(f"{rel}: Missing quick-answer aside container")
                    continue
                words = qa.split()
                if len(words) < 40 or len(words) > 60:
                    gaps_5.append(f"{rel}: Quick-answer word count {len(words)} outside 40-60 range")
                if "\u2014" in qa or "\u2013" in qa:
                    gaps_5.append(f"{rel}: Quick-answer contains em-dash or en-dash")

        findings.append({
            "factor": "Passage-level Relevance",
            "weight": 1.99,
            "status": "PASS" if not gaps_5 else "FAIL",
            "passed": len(gaps_5) == 0,
            "gap_count": len(gaps_5),
            "pages_scanned": pages_scanned,
            "examples": gaps_5[:3],
        })

        # Factor 6: Language Match (weight 1.95)
        gaps_6: List[str] = []
        if vacuous_pass:
            gaps_6.append("Vacuous Pass Prevention: pages_scanned < 10 or endpoints_scanned < 5")
        else:
            for rel, (p, raw, parser) in parsed_docs.items():
                if rel == "404.html" or "signal" in p.parts or "static" in p.parts:
                    continue
                if not parser.root_lang or not parser.root_lang.startswith("en"):
                    gaps_6.append(f"{rel}: Root <html lang='{parser.root_lang}'> missing or not 'en'")
                if parser.meta_content_language.lower() != "en-us":
                    gaps_6.append(f"{rel}: Missing <meta http-equiv='content-language' content='en-US'>")
                if not ("en-us" in parser.hreflangs and "x-default" in parser.hreflangs):
                    gaps_6.append(f"{rel}: Missing canonical self-referential hreflang alternate links ('en-US', 'x-default')")
            if feed_xml.is_file():
                feed_text = feed_xml.read_text(encoding="utf-8")
                if "<language>en-US</language>" not in feed_text and "<language>en-us</language>" not in feed_text:
                    gaps_6.append("feed.xml missing <language>en-US</language>")

        findings.append({
            "factor": "Language Match",
            "weight": 1.95,
            "status": "PASS" if not gaps_6 else "FAIL",
            "passed": len(gaps_6) == 0,
            "gap_count": len(gaps_6),
            "pages_scanned": pages_scanned,
            "examples": gaps_6[:3],
        })

        # Factor 7: Geographic Relevance (weight 1.89)
        gaps_7: List[str] = []
        if vacuous_pass:
            gaps_7.append("Vacuous Pass Prevention: pages_scanned < 10 or endpoints_scanned < 5")
        else:
            for rel, (p, raw, parser) in parsed_docs.items():
                if "signal" in p.parts or "static" in p.parts:
                    continue
                if self.is_geo_leaf:
                    is_geo = self.is_geo_leaf(rel, p)
                else:
                    is_geo = ("/state/" in rel) or (
                        "/irs-2027-tax-brackets/" in rel and p.parent.name != "irs-2027-tax-brackets"
                    ) or (
                        "/section-1031-calculator/" in rel and p.parent.name != "section-1031-calculator"
                    )
                if is_geo:
                    if not parser.geo_region or not parser.geo_region.startswith("US-"):
                        gaps_7.append(f"{rel}: Missing <meta name='geo.region' content='US-...'>")
                    has_spatial = any("spatialCoverage" in blk or "areaServed" in blk for blk in parser.json_ld_blocks)
                    if not has_spatial:
                        gaps_7.append(f"{rel}: Missing spatialCoverage or areaServed in Schema.org JSON-LD")

        findings.append({
            "factor": "Geographic Relevance",
            "weight": 1.89,
            "status": "PASS" if not gaps_7 else "FAIL",
            "passed": len(gaps_7) == 0,
            "gap_count": len(gaps_7),
            "pages_scanned": pages_scanned,
            "examples": gaps_7[:3],
        })

        # Factor 8: Keywords in H1 (weight 1.67)
        gaps_8: List[str] = []
        if vacuous_pass:
            gaps_8.append("Vacuous Pass Prevention: pages_scanned < 10 or endpoints_scanned < 5")
        else:
            for rel, (p, raw, parser) in parsed_docs.items():
                if rel in ("404.html", "about/index.html") or "signal" in p.parts or "static" in p.parts:
                    continue
                if len(parser.h1_list) != 1:
                    gaps_8.append(f"{rel}: Expected exactly 1 <h1>, found {len(parser.h1_list)}")
                    continue
                h1 = parser.h1_list[0]
                if not h1:
                    gaps_8.append(f"{rel}: Empty <h1>")
                    continue
                if len(h1) < 20 or len(h1) > 70:
                    gaps_8.append(f"{rel}: H1 length {len(h1)} outside 20-70 range ('{h1}')")
                if self.brand_name in h1 or f"| {self.brand_name}" in h1:
                    gaps_8.append(f"{rel}: H1 contains brand suffix '| {self.brand_name}' ('{h1}')")

        findings.append({
            "factor": "Keywords in H1",
            "weight": 1.67,
            "status": "PASS" if not gaps_8 else "FAIL",
            "passed": len(gaps_8) == 0,
            "gap_count": len(gaps_8),
            "pages_scanned": pages_scanned,
            "examples": gaps_8[:3],
        })

        # Factor 9: Keywords in Subheadings (weight 1.27)
        gaps_9: List[str] = []
        if vacuous_pass:
            gaps_9.append("Vacuous Pass Prevention: pages_scanned < 10 or endpoints_scanned < 5")
        else:
            for rel, (p, raw, parser) in parsed_docs.items():
                if rel in ("404.html", "privacy/index.html", "about/index.html", "index.html", "tools/index.html") or "signal" in p.parts or "static" in p.parts:
                    continue
                if len(parser.h2_list) < 2:
                    gaps_9.append(f"{rel}: Less than 2 <h2> subheadings ({len(parser.h2_list)})")
                if len(parser.h2_list) != len(set(parser.h2_list)):
                    gaps_9.append(f"{rel}: Duplicate <h2> subheadings detected")
                for h in parser.h2_list:
                    words = h.split()
                    if any(len(w) == 1 and w.isupper() and w not in ('A', 'I') for w in words):
                        gaps_9.append(f"{rel}: Chopped word in <h2> heading ('{h}')")
                        break

        findings.append({
            "factor": "Keywords in Subheadings",
            "weight": 1.27,
            "status": "PASS" if not gaps_9 else "FAIL",
            "passed": len(gaps_9) == 0,
            "gap_count": len(gaps_9),
            "pages_scanned": pages_scanned,
            "examples": gaps_9[:3],
        })

        # Factor 10: Keywords in URL (weight 1.07)
        gaps_10: List[str] = []
        kebab_pat = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')
        if vacuous_pass:
            gaps_10.append("Vacuous Pass Prevention: pages_scanned < 10 or endpoints_scanned < 5")
        else:
            for rel, (p, raw, parser) in parsed_docs.items():
                if "static" in p.parts or "signal" in p.parts:
                    continue
                parts = [part for part in Path(rel).parts if part not in ("index.html", "404.html")]
                for part in parts:
                    if not kebab_pat.match(part):
                        gaps_10.append(f"{rel}: Path segment '{part}' violates lowercase kebab-case format")
                        break

        findings.append({
            "factor": "Keywords in URL",
            "weight": 1.07,
            "status": "PASS" if not gaps_10 else "FAIL",
            "passed": len(gaps_10) == 0,
            "gap_count": len(gaps_10),
            "pages_scanned": pages_scanned,
            "examples": gaps_10[:3],
        })

        # Factor 11: Exact-Match Domain (weight 0.94)
        gaps_11: List[str] = []
        if vacuous_pass:
            gaps_11.append("Vacuous Pass Prevention: pages_scanned < 10 or endpoints_scanned < 5")
        else:
            domain_prefix = f"https://{self.domain}"
            for rel, (p, raw, parser) in parsed_docs.items():
                if rel == "404.html" or "signal" in p.parts or "static" in p.parts:
                    continue
                if parser.canonical_url and not parser.canonical_url.startswith(domain_prefix):
                    gaps_11.append(f"{rel}: Canonical URL not on {domain_prefix} ('{parser.canonical_url}')")
                if parser.og_url and not parser.og_url.startswith(domain_prefix):
                    gaps_11.append(f"{rel}: OpenGraph URL not on {domain_prefix} ('{parser.og_url}')")

        findings.append({
            "factor": "Exact-Match Domain",
            "weight": 0.94,
            "status": "PASS" if not gaps_11 else "FAIL",
            "passed": len(gaps_11) == 0,
            "gap_count": len(gaps_11),
            "pages_scanned": pages_scanned,
            "examples": gaps_11[:3],
        })

        # Factor 12: Meta Description (weight 0.22)
        gaps_12: List[str] = []
        if vacuous_pass:
            gaps_12.append("Vacuous Pass Prevention: pages_scanned < 10 or endpoints_scanned < 5")
        else:
            for rel, (p, raw, parser) in parsed_docs.items():
                if rel == "404.html" or "signal" in p.parts or "static" in p.parts:
                    continue
                md = parser.meta_description
                if not md:
                    gaps_12.append(f"{rel}: Missing meta description")
                    continue
                if len(md) < 50 or len(md) > 165:
                    gaps_12.append(f"{rel}: Meta description length {len(md)} outside 50-165 range ('{md}')")
                if re.search(r'\$\d+,\.\.\.', md) or re.search(r'\d+\.\.\.', md):
                    gaps_12.append(f"{rel}: Mid-number ellipsis truncation in meta description ('{md}')")
                if "\u2014" in md or "\u2013" in md:
                    gaps_12.append(f"{rel}: Meta description contains em-dash or en-dash ('{md}')")

        findings.append({
            "factor": "Meta Description",
            "weight": 0.22,
            "status": "PASS" if not gaps_12 else "FAIL",
            "passed": len(gaps_12) == 0,
            "gap_count": len(gaps_12),
            "pages_scanned": pages_scanned,
            "examples": gaps_12[:3],
        })

        failing_findings = [f for f in findings if not f["passed"]]
        overall_status = "PASS" if len(failing_findings) == 0 else "FAIL"

        return {
            "status": overall_status,
            "gate": "check_content_relevance_gate",
            "pages_scanned": pages_scanned,
            "endpoints_scanned": endpoints_scanned,
            "factors_evaluated": len(findings),
            "findings": findings,
            "gaps_sorted_by_weight_desc": sorted(failing_findings, key=lambda x: x["weight"], reverse=True),
            "top_gap": failing_findings[0] if failing_findings else None,
        }

    # =========================================================================
    # Master SEO Checklist Audit
    # =========================================================================
    def audit_seo_checklist(
        self,
        dist_dir: Optional[Path] = None,
        raise_on_error: bool = False,
        enforce_relevance: bool = True,
    ) -> Dict[str, Any]:
        """
        Executes master Opus 5.5 SEO & GEO audit checklist across static assets.
        Returns consolidated dictionary with status PASS/FAIL, all evaluated gates, and issue details.
        """
        target = Path(dist_dir) if dist_dir else self.dist_dir
        if not target.exists():
            err_dict = {
                "status": "FAIL",
                "reason": f"Target dist directory {target} does not exist.",
                "gates": {},
                "issues": [f"Directory {target} not found"],
                "total_issues_count": 1,
            }
            if raise_on_error:
                raise SEOVerificationError(f"Target dist directory {target} does not exist.", issues=err_dict["issues"])
            return err_dict

        content_relevance_gate = self.check_content_relevance_gate(target)

        g_alt_text = self.check_alt_text_gate(target)
        g_sitemap = self.check_sitemap_gate(target)
        g_page_titles = self.check_page_titles_gate(target)
        g_single_h1 = self.check_single_h1_gate(target)
        g_image_compression = self.check_image_compression_gate(target)
        g_page_language = self.check_page_language_gate(target)
        g_canonical_tags = self.check_canonical_tags_gate(target)
        g_robots_txt = self.check_robots_txt_gate(target)
        g_readable_urls = self.check_readable_urls_gate(target)
        g_schema_markup = self.check_schema_markup_gate(target)
        g_noindex_tags = self.check_noindex_tags_gate(target)
        g_internal_linking = self.check_internal_linking_gate(target)
        g_load_performance = self.check_load_performance_gate(target)
        g_meta_descriptions = self.check_meta_descriptions_gate(target)
        g_url_redirects = self.check_url_redirects_gate(target)
        g_search_console_tag = self.check_search_console_tag_gate(target)
        g_hide_test_pages = self.check_hide_test_pages_gate(target)
        g_no_js_rendering = self.check_no_js_rendering_gate(target)
        g_http_link_canonical = self.check_http_link_canonical_gate(target)
        g_snippet_eligibility = self.check_snippet_eligibility_gate(target)
        g_query_answer_match = self.check_query_answer_match_gate(target)
        g_brand_entity = self.check_brand_entity_in_llm_memory_gate(target)
        g_citable_facts = self.check_citable_specific_facts_gate(target)
        g_organic_fan_out = self.check_organic_fan_out_coverage_gate(target)
        g_organic_search = self.check_organic_search_ranking_gate(target)
        g_unique_first_party = self.check_unique_first_party_information_gate(target)
        g_cross_web_consensus = self.check_cross_web_consensus_and_corroboration_gate(target)
        g_source_publisher = self.check_source_publisher_reputation_gate(target)
        g_extractable_structure = self.check_extractable_content_structure_gate(target)
        g_answer_prominence = self.check_answer_prominence_gate(target)
        g_structured_data = self.check_structured_data_gate(target)
        g_llms_txt = self.check_llms_txt_gate(target)
        g_tool_utility = self.check_tool_utility_gate(target)
        g_free_web_app_schema = self.check_free_web_application_schema_gate(target)
        g_operational_shield = self.check_operational_shield_gate(target)
        g_ai_mode_manifest = self.check_ai_mode_manifest_gate(target)
        g_existence = self.check_existence_gate(target)
        g_title_length = self.check_title_gate(target)
        g_snippet = self.check_snippet_gate(target)
        g_schema = self.check_schema_gate(target)
        g_citability = self.check_citability_gate(target)
        g_cleanliness = self.check_cleanliness_gate(target)
        g_indexing = self.check_indexing_gate(target)

        gates = {
            "check_alt_text_gate": g_alt_text,
            "check_sitemap_gate": g_sitemap,
            "check_page_titles_gate": g_page_titles,
            "check_single_h1_gate": g_single_h1,
            "check_image_compression_gate": g_image_compression,
            "check_page_language_gate": g_page_language,
            "check_canonical_tags_gate": g_canonical_tags,
            "check_robots_txt_gate": g_robots_txt,
            "check_readable_urls_gate": g_readable_urls,
            "check_schema_markup_gate": g_schema_markup,
            "check_noindex_tags_gate": g_noindex_tags,
            "check_internal_linking_gate": g_internal_linking,
            "check_load_performance_gate": g_load_performance,
            "check_meta_descriptions_gate": g_meta_descriptions,
            "check_url_redirects_gate": g_url_redirects,
            "check_search_console_tag_gate": g_search_console_tag,
            "check_hide_test_pages_gate": g_hide_test_pages,
            "check_no_js_rendering_gate": g_no_js_rendering,
            "check_http_link_canonical_gate": g_http_link_canonical,
            "check_snippet_eligibility_gate": g_snippet_eligibility,
            "check_ai_crawl_access_and_snippet_eligibility_gate": g_snippet_eligibility,
            "check_ai_crawl_access_gate": g_snippet_eligibility,
            "check_query_answer_match_gate": g_query_answer_match,
            "check_query_answer_gate": g_query_answer_match,
            "check_brand_entity_in_llm_memory_gate": g_brand_entity,
            "check_brand_entity_gate": g_brand_entity,
            "check_entity_memory_gate": g_brand_entity,
            "check_citable_specific_facts_gate": g_citable_facts,
            "check_citable_facts_gate": g_citable_facts,
            "check_specific_facts_gate": g_citable_facts,
            "check_organic_fan_out_coverage_gate": g_organic_fan_out,
            "check_fan_out_coverage_gate": g_organic_fan_out,
            "check_organic_fan_out_gate": g_organic_fan_out,
            "check_organic_search_ranking_gate": g_organic_search,
            "check_traditional_organic_search_gate": g_organic_search,
            "check_core_seo_hygiene_gate": g_organic_search,
            "check_unique_first_party_information_gate": g_unique_first_party,
            "check_first_party_information_gate": g_unique_first_party,
            "check_first_party_assets_gate": g_unique_first_party,
            "check_firsthand_calculations_gate": g_unique_first_party,
            "check_proprietary_models_gate": g_unique_first_party,
            "check_cross_web_consensus_and_corroboration_gate": g_cross_web_consensus,
            "check_cross_web_corroboration_gate": g_cross_web_consensus,
            "check_statutory_consensus_gate": g_cross_web_consensus,
            "check_baseline_fact_agreement_gate": g_cross_web_consensus,
            "check_statutory_constants_corroboration_gate": g_cross_web_consensus,
            "check_source_publisher_reputation_gate": g_source_publisher,
            "check_publisher_reputation_gate": g_source_publisher,
            "check_publisher_authority_gate": g_source_publisher,
            "check_author_credentials_gate": g_source_publisher,
            "check_editorial_policy_gate": g_source_publisher,
            "check_extractable_content_structure_gate": g_extractable_structure,
            "check_extractable_structure_gate": g_extractable_structure,
            "check_semantic_heading_hierarchy_gate": g_extractable_structure,
            "check_scoped_table_headers_gate": g_extractable_structure,
            "check_procedural_ordered_steps_gate": g_extractable_structure,
            "check_answer_prominence_gate": g_answer_prominence,
            "check_answer_above_fold_gate": g_answer_prominence,
            "check_core_answer_prominence_gate": g_answer_prominence,
            "check_direct_answer_prominence_gate": g_answer_prominence,
            "check_calculation_widget_prominence_gate": g_answer_prominence,
            "check_early_answer_block_gate": g_answer_prominence,
            "check_structured_data_gate": g_structured_data,
            "check_schema_org_structured_data_gate": g_structured_data,
            "check_jsonld_structured_data_gate": g_structured_data,
            "check_schema_graphs_gate": g_structured_data,
            "check_target_entity_schemas_gate": g_structured_data,
            "check_machine_readable_schemas_gate": g_structured_data,
            "check_llms_txt_gate": g_llms_txt,
            "check_llms_txt_file_gate": g_llms_txt,
            "check_llms_full_txt_gate": g_llms_txt,
            "check_llmstxt_gate": g_llms_txt,
            "check_llms_manifest_gate": g_llms_txt,
            "check_curated_llms_txt_gate": g_llms_txt,
            "check_tool_utility_gate": g_tool_utility,
            "check_free_web_application_schema_gate": g_free_web_app_schema,
            "check_operational_shield_gate": g_operational_shield,
            "check_content_relevance_gate": content_relevance_gate,

            # Auxiliary and legacy aliases
            "check_ai_mode_manifest_gate": g_ai_mode_manifest,
            "check_manifest_gate": g_ai_mode_manifest,
            "existence_gate": g_existence,
            "title_length_gate": g_title_length,
            "snippet_gate": g_snippet,
            "schema_gate": g_schema,
            "citability_gate": g_citability,
            "cleanliness_gate": g_cleanliness,
            "indexing_gate": g_indexing,
            "check_indexing_gate": g_indexing,
        }

        all_issues = []
        primary_keys = [
            "check_alt_text_gate",
            "check_sitemap_gate",
            "check_page_titles_gate",
            "check_single_h1_gate",
            "check_image_compression_gate",
            "check_page_language_gate",
            "check_canonical_tags_gate",
            "check_robots_txt_gate",
            "check_readable_urls_gate",
            "check_schema_markup_gate",
            "check_noindex_tags_gate",
            "check_internal_linking_gate",
            "check_load_performance_gate",
            "check_meta_descriptions_gate",
            "check_url_redirects_gate",
            "check_search_console_tag_gate",
            "check_hide_test_pages_gate",
            "check_no_js_rendering_gate",
            "check_http_link_canonical_gate",
            "check_snippet_eligibility_gate",
            "check_structured_data_gate",
        ]

        for g_key in primary_keys:
            g_res = gates.get(g_key, {})
            if g_res.get("issues"):
                all_issues.extend(g_res["issues"])

        if enforce_relevance and content_relevance_gate.get("status") == "FAIL":
            for gap_item in content_relevance_gate.get("gaps_sorted_by_weight_desc", []):
                ex_summary = f" (e.g. {gap_item['examples'][0]})" if gap_item.get("examples") else ""
                all_issues.append(
                    f"Content Relevance ({gap_item['factor']}, weight {gap_item['weight']:.2f}): "
                    f"{gap_item['gap_count']} gaps detected{ex_summary}"
                )

        all_passed = len(all_issues) == 0

        result = {
            "status": "PASS" if all_passed else "FAIL",
            "craftsmanship_compliant": all_passed,
            "gates": gates,
            "issues": all_issues,
            "total_issues_count": len(all_issues),
            "content_relevance": content_relevance_gate,
        }

        if raise_on_error and not all_passed:
            issue_summary = "; ".join(all_issues[:3])
            if len(all_issues) > 3:
                issue_summary += f" (...and {len(all_issues) - 3} more)"
            raise SEOVerificationError(
                f"SEO checklist verification failed with {len(all_issues)} issues: {issue_summary}",
                issues=all_issues,
                gates=gates,
            )

        return result


# Default module-level MasterSEOVerifier instance
_default_verifier = MasterSEOVerifier()

check_alt_text_gate = _default_verifier.check_alt_text_gate
check_sitemap_gate = _default_verifier.check_sitemap_gate
check_indexing_gate = _default_verifier.check_indexing_gate
check_page_titles_gate = _default_verifier.check_page_titles_gate
check_single_h1_gate = _default_verifier.check_single_h1_gate
check_image_compression_gate = _default_verifier.check_image_compression_gate
check_page_language_gate = _default_verifier.check_page_language_gate
check_canonical_tags_gate = _default_verifier.check_canonical_tags_gate
check_http_link_canonical_gate = _default_verifier.check_http_link_canonical_gate
check_ai_mode_manifest_gate = _default_verifier.check_ai_mode_manifest_gate
check_manifest_gate = _default_verifier.check_manifest_gate
check_robots_txt_gate = _default_verifier.check_robots_txt_gate
check_readable_urls_gate = _default_verifier.check_readable_urls_gate
check_schema_markup_gate = _default_verifier.check_schema_markup_gate
check_noindex_tags_gate = _default_verifier.check_noindex_tags_gate
check_internal_linking_gate = _default_verifier.check_internal_linking_gate
check_load_performance_gate = _default_verifier.check_load_performance_gate
check_meta_descriptions_gate = _default_verifier.check_meta_descriptions_gate
check_url_redirects_gate = _default_verifier.check_url_redirects_gate
check_search_console_tag_gate = _default_verifier.check_search_console_tag_gate
check_hide_test_pages_gate = _default_verifier.check_hide_test_pages_gate
check_no_js_rendering_gate = _default_verifier.check_no_js_rendering_gate
check_snippet_eligibility_gate = _default_verifier.check_snippet_eligibility_gate
check_ai_crawl_access_and_snippet_eligibility_gate = _default_verifier.check_ai_crawl_access_and_snippet_eligibility_gate
check_ai_crawl_access_gate = _default_verifier.check_ai_crawl_access_gate
verify_ai_crawl_access_and_snippet_eligibility = _default_verifier.verify_ai_crawl_access_and_snippet_eligibility
check_query_answer_match_gate = _default_verifier.check_query_answer_match_gate
check_query_answer_gate = _default_verifier.check_query_answer_gate
verify_query_answer_match = _default_verifier.verify_query_answer_match
check_brand_entity_in_llm_memory_gate = _default_verifier.check_brand_entity_in_llm_memory_gate
check_brand_entity_gate = _default_verifier.check_brand_entity_gate
check_entity_memory_gate = _default_verifier.check_entity_memory_gate
verify_brand_entity_in_llm_memory = _default_verifier.verify_brand_entity_in_llm_memory
check_citable_specific_facts_gate = _default_verifier.check_citable_specific_facts_gate
check_citable_facts_gate = _default_verifier.check_citable_facts_gate
check_specific_facts_gate = _default_verifier.check_specific_facts_gate
verify_citable_specific_facts = _default_verifier.verify_citable_specific_facts
check_organic_fan_out_coverage_gate = _default_verifier.check_organic_fan_out_coverage_gate
check_fan_out_coverage_gate = _default_verifier.check_fan_out_coverage_gate
check_organic_fan_out_gate = _default_verifier.check_organic_fan_out_gate
verify_organic_fan_out_coverage = _default_verifier.verify_organic_fan_out_coverage
verify_page_set_fan_out_coverage = _default_verifier.verify_page_set_fan_out_coverage
check_organic_search_ranking_gate = _default_verifier.check_organic_search_ranking_gate
check_traditional_organic_search_gate = _default_verifier.check_traditional_organic_search_gate
check_core_seo_hygiene_gate = _default_verifier.check_core_seo_hygiene_gate
verify_organic_search_ranking = _default_verifier.verify_organic_search_ranking
check_unique_first_party_information_gate = _default_verifier.check_unique_first_party_information_gate
check_first_party_information_gate = _default_verifier.check_first_party_information_gate
check_first_party_assets_gate = _default_verifier.check_first_party_assets_gate
check_firsthand_calculations_gate = _default_verifier.check_firsthand_calculations_gate
check_proprietary_models_gate = _default_verifier.check_proprietary_models_gate
verify_unique_first_party_information = _default_verifier.verify_unique_first_party_information
check_cross_web_consensus_and_corroboration_gate = _default_verifier.check_cross_web_consensus_and_corroboration_gate
check_cross_web_corroboration_gate = _default_verifier.check_cross_web_corroboration_gate
check_statutory_consensus_gate = _default_verifier.check_statutory_consensus_gate
check_baseline_fact_agreement_gate = _default_verifier.check_baseline_fact_agreement_gate
check_statutory_constants_corroboration_gate = _default_verifier.check_statutory_constants_corroboration_gate
verify_cross_web_consensus_and_corroboration = _default_verifier.verify_cross_web_consensus_and_corroboration
verify_cross_web_corroboration = _default_verifier.verify_cross_web_corroboration
check_source_publisher_reputation_gate = _default_verifier.check_source_publisher_reputation_gate
check_publisher_reputation_gate = _default_verifier.check_publisher_reputation_gate
check_publisher_authority_gate = _default_verifier.check_publisher_authority_gate
check_author_credentials_gate = _default_verifier.check_author_credentials_gate
check_editorial_policy_gate = _default_verifier.check_editorial_policy_gate
verify_source_publisher_reputation = _default_verifier.verify_source_publisher_reputation
verify_publisher_reputation = _default_verifier.verify_publisher_reputation
check_extractable_content_structure_gate = _default_verifier.check_extractable_content_structure_gate
check_extractable_structure_gate = _default_verifier.check_extractable_structure_gate
check_semantic_heading_hierarchy_gate = _default_verifier.check_semantic_heading_hierarchy_gate
check_scoped_table_headers_gate = _default_verifier.check_scoped_table_headers_gate
check_procedural_ordered_steps_gate = _default_verifier.check_procedural_ordered_steps_gate
verify_extractable_content_structure = _default_verifier.verify_extractable_content_structure
verify_extractable_structure = _default_verifier.verify_extractable_structure
check_answer_prominence_gate = _default_verifier.check_answer_prominence_gate
check_answer_above_fold_gate = _default_verifier.check_answer_above_fold_gate
check_core_answer_prominence_gate = _default_verifier.check_core_answer_prominence_gate
check_direct_answer_prominence_gate = _default_verifier.check_direct_answer_prominence_gate
check_calculation_widget_prominence_gate = _default_verifier.check_calculation_widget_prominence_gate
check_early_answer_block_gate = _default_verifier.check_early_answer_block_gate
verify_answer_prominence = _default_verifier.verify_answer_prominence
verify_answer_above_fold = _default_verifier.verify_answer_above_fold
verify_core_answer_prominence = _default_verifier.verify_core_answer_prominence
check_structured_data_gate = _default_verifier.check_structured_data_gate
check_schema_org_structured_data_gate = _default_verifier.check_schema_org_structured_data_gate
check_jsonld_structured_data_gate = _default_verifier.check_jsonld_structured_data_gate
check_schema_graphs_gate = _default_verifier.check_schema_graphs_gate
check_target_entity_schemas_gate = _default_verifier.check_target_entity_schemas_gate
check_machine_readable_schemas_gate = _default_verifier.check_machine_readable_schemas_gate
verify_structured_data = _default_verifier.verify_structured_data
verify_schema_org_structured_data = _default_verifier.verify_schema_org_structured_data
verify_jsonld_structured_data = _default_verifier.verify_jsonld_structured_data
verify_schema_graphs = _default_verifier.verify_schema_graphs
check_llms_txt_gate = _default_verifier.check_llms_txt_gate
check_llms_txt_file_gate = _default_verifier.check_llms_txt_file_gate
check_llms_full_txt_gate = _default_verifier.check_llms_full_txt_gate
check_llmstxt_gate = _default_verifier.check_llmstxt_gate
check_llms_manifest_gate = _default_verifier.check_llms_manifest_gate
check_curated_llms_txt_gate = _default_verifier.check_curated_llms_txt_gate
verify_llms_txt = _default_verifier.verify_llms_txt
verify_llms_txt_file = _default_verifier.verify_llms_txt_file
verify_llms_full_txt = _default_verifier.verify_llms_full_txt
verify_llmstxt = _default_verifier.verify_llmstxt
verify_curated_llms_txt = _default_verifier.verify_curated_llms_txt



def verify_html_ai_crawl_access_and_snippet_eligibility(
    html_content: str,
    rel_path: str = "index.html",
) -> Dict[str, Any]:
    """
    In-memory validation helper for an HTML document string against Factor 1.
    Zero em-dashes. Zero en-dashes.
    """
    parser = SinglePassSEODocumentParser()
    parser.feed(html_content)
    issues = []
    if parser.has_nosnippet:
        issues.append(f"Page {rel_path} contains 'nosnippet' directive, revoking search and AI snippet eligibility")
    if parser.has_noindex:
        issues.append(f"Page {rel_path} contains 'noindex' or 'none' directive, revoking search and AI snippet eligibility")
    if parser.max_snippet is not None:
        if parser.max_snippet == 0:
            issues.append(f"Page {rel_path} contains 'max-snippet:0' directive, revoking search snippet eligibility")
        elif parser.max_snippet > 0 and parser.quick_answer_text:
            if len(parser.quick_answer_text) > parser.max_snippet:
                issues.append(f"Page {rel_path} quick-answer ({len(parser.quick_answer_text)} chars) exceeds max-snippet:{parser.max_snippet} limit")
    if parser.quick_answer_has_data_nosnippet:
        issues.append(f"Page {rel_path} quick-answer container or ancestor contains 'data-nosnippet', excluding answer from search snippets and AI Overviews")
    if parser.root_has_data_nosnippet:
        issues.append(f"Page {rel_path} root or main container contains 'data-nosnippet', excluding content from search snippets and AI Overviews")

    return {
        "status": "PASS" if not issues else "FAIL",
        "gate": "verify_html_ai_crawl_access_and_snippet_eligibility",
        "violations_count": len(issues),
        "issues": issues,
    }


def evaluate_query_answer_semantic_match(
    answer_text: str,
    query: str,
    rel: str = "",
    min_overlap: float = 0.50,
) -> List[str]:
    """
    Evaluates semantic match between query and answer passage.
    Returns list of issues (empty if compliant).
    Zero em-dashes. Zero en-dashes.
    """
    issues: List[str] = []
    prefix = f"Page {rel}: " if rel else ""
    clean_q = str(query or "").strip().lower()
    if not clean_q:
        return issues

    raw_tokens = re.findall(r"\b[a-zA-Z0-9]+\b", clean_q)
    stopwords = {
        "a", "an", "the", "and", "or", "for", "with", "in", "to", "of", "is", "are",
        "on", "at", "by", "from", "how", "what", "why", "when", "where", "who", "which",
        "can", "does", "do", "it", "this", "that", "these", "those", "be", "been",
        "being", "have", "has", "had", "as", "if", "into", "about",
    }
    query_tokens = [t for t in raw_tokens if t not in stopwords]
    if not query_tokens:
        query_tokens = raw_tokens

    if not query_tokens:
        return issues

    ans_lower = answer_text.lower()
    ans_tokens = set(re.findall(r"\b[a-zA-Z0-9]+\b", ans_lower))

    matched = []
    missing = []
    for qt in query_tokens:
        if qt in ans_tokens:
            matched.append(qt)
        elif any((qt in at or at in qt) for at in ans_tokens if len(at) >= 4 and len(qt) >= 4):
            matched.append(qt)
        else:
            missing.append(qt)

    overlap = len(matched) / len(query_tokens)
    if overlap < min_overlap:
        issues.append(
            f"{prefix}Direct query-answer semantic mismatch: quick-answer addresses only "
            f"{len(matched)}/{len(query_tokens)} query terms for '{query}' (missing: {', '.join(missing)})"
        )

    # Keyword stuffing check (single non-stopword repeated excessively)
    ans_words = [w for w in re.findall(r"\b[a-zA-Z0-9]+\b", ans_lower) if w not in stopwords]
    if ans_words:
        counts: Dict[str, int] = {}
        for w in ans_words:
            counts[w] = counts.get(w, 0) + 1
        for word, count in counts.items():
            density = count / len(ans_words)
            if count >= 6 or density > 0.20:
                issues.append(
                    f"{prefix}Quick-answer exhibits keyword stuffing: term '{word}' repeated {count} times"
                )

    return issues


def verify_html_query_answer_match(
    html_content: str,
    target_query: Optional[str] = None,
    rel_path: str = "index.html",
) -> Dict[str, Any]:
    """
    In-memory validation helper for an HTML document string against Factor 2: Query-Answer Match (+2.15).
    Verifies container presence, viewport ordering, passage relevance bounds, and semantic match.
    Zero em-dashes. Zero en-dashes.
    """
    issues: List[str] = []
    if not isinstance(html_content, str):
        return {
            "status": "FAIL",
            "gate": "check_query_answer_match_gate",
            "violations_count": 1,
            "issues": [f"Page {rel_path}: HTML content must be a string"],
            "quick_answer_text": "",
            "word_count": 0,
            "in_viewport": False,
        }

    # Anti-slop check
    if "\u2014" in html_content:
        issues.append(f"Page {rel_path}: Document contains forbidden em-dash")
    if "\u2013" in html_content:
        issues.append(f"Page {rel_path}: Document contains forbidden en-dash")

    parser = SinglePassSEODocumentParser()
    parser.feed(html_content)

    if not parser.has_quick_answer:
        issues.append(f"Page {rel_path}: Missing quick-answer container (<div class='quick-answer'> or <aside class='quick-answer'>) in initial viewport")
        return {
            "status": "FAIL",
            "gate": "check_query_answer_match_gate",
            "violations_count": len(issues),
            "issues": issues,
            "quick_answer_text": "",
            "word_count": 0,
            "in_viewport": False,
        }

    qa_text = parser.quick_answer_text
    if not qa_text:
        issues.append(f"Page {rel_path}: Unpopulated quick-answer container (empty text violates passage relevance)")
        return {
            "status": "FAIL",
            "gate": "check_query_answer_match_gate",
            "violations_count": len(issues),
            "issues": issues,
            "quick_answer_text": "",
            "word_count": 0,
            "in_viewport": False,
        }

    if parser.quick_answer_count > 1:
        issues.append(f"Page {rel_path}: Multiple quick-answer containers found ({parser.quick_answer_count}), strictly requires a single authoritative viewport answer")

    if not parser.quick_answer_seen_after_h1:
        issues.append(f"Page {rel_path}: Quick-answer container misplaced before introductory <h1> header (must follow top-level header in initial viewport)")

    if not parser.quick_answer_seen_before_h2:
        issues.append(f"Page {rel_path}: Quick-answer container sunk below secondary heading (<h2>) or secondary section (must remain in initial viewport)")

    # Word count check: strictly 40 to 60 words
    words = [w for w in qa_text.split() if w.strip()]
    if len(words) < 40:
        issues.append(f"Page {rel_path}: Quick-answer word count {len(words)} below minimum 40 words required for passage relevance")
    elif len(words) > 60:
        issues.append(f"Page {rel_path}: Quick-answer word count {len(words)} exceeds maximum 60 words permitted for passage relevance")

    # Character density (3.0 to 15.0 chars/word)
    if words:
        char_density = sum(len(w) for w in words) / len(words)
        if char_density < 3.0 or char_density > 15.0:
            issues.append(f"Page {rel_path}: Quick-answer character density ({char_density:.2f} chars/word) outside valid 3.0-15.0 range")

    # Sentence boundaries (1 to 5 sentences with terminal punctuation)
    if not re.search(r'[.!?]["\']?\s*$', qa_text.strip()):
        issues.append(f"Page {rel_path}: Quick-answer passage missing terminal sentence punctuation")
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', qa_text.strip()) if s.strip()]
    if len(sentences) < 1 or len(sentences) > 5:
        issues.append(f"Page {rel_path}: Quick-answer sentence count ({len(sentences)}) outside valid 1-5 sentence bounds")

    # Anti-slop in quick-answer text
    if "\u2014" in qa_text:
        issues.append(f"Page {rel_path}: Quick-answer contains forbidden em-dash")
    if "\u2013" in qa_text:
        issues.append(f"Page {rel_path}: Quick-answer contains forbidden en-dash")

    # Forbidden jargon
    for j_term in FORBIDDEN_JARGON:
        if re.search(r'\b' + re.escape(j_term) + r'\b', qa_text, re.IGNORECASE):
            issues.append(f"Page {rel_path}: Quick-answer contains forbidden AI jargon '{j_term}'")

    # Evasive summary phrases
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
        if ev_p in qa_text.lower():
            issues.append(f"Page {rel_path}: Quick-answer degenerates into evasive summary ('{ev_p}') lacking direct factual resolution")

    # Target query evaluation
    query_to_check = target_query or parser.target_query
    if query_to_check:
        sem_issues = evaluate_query_answer_semantic_match(qa_text, query_to_check, rel=rel_path)
        issues.extend(sem_issues)

    return {
        "status": "PASS" if not issues else "FAIL",
        "gate": "check_query_answer_match_gate",
        "violations_count": len(issues),
        "issues": issues,
        "quick_answer_text": qa_text,
        "word_count": len(words),
        "in_viewport": parser.quick_answer_in_viewport,
    }


def extract_canonical_brand_entities(
    blocks: List[Any],
    brand_name: Optional[str] = None,
    brand_domain: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Extracts candidate brand and organization entities from JSON-LD blocks, graphs, and nested properties.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.contracts import BRAND_ENTITY_TAXONOMY, DISALLOWED_BRAND_TAXONOMY

    candidates: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()

    def inspect_item(item: Any):
        if not isinstance(item, dict):
            return
        if "@graph" in item and isinstance(item["@graph"], list):
            for sub in item["@graph"]:
                inspect_item(sub)

        raw_type = item.get("@type")
        types: List[str] = (
            [raw_type]
            if isinstance(raw_type, str)
            else list(raw_type)
            if isinstance(raw_type, (list, tuple))
            else []
        )

        is_brand_candidate = any(t in BRAND_ENTITY_TAXONOMY for t in types)
        has_disallowed = any(t in DISALLOWED_BRAND_TAXONOMY for t in types)

        if is_brand_candidate or has_disallowed or "sameAs" in item:
            ident = item.get("@id") or f"anon_{id(item)}"
            if ident not in seen_ids:
                seen_ids.add(ident)
                candidates.append(item)

        for prop in (
            "publisher",
            "brand",
            "creator",
            "author",
            "organizer",
            "provider",
            "parentOrganization",
            "subOrganization",
            "sourceOrganization",
        ):
            if prop in item:
                val = item[prop]
                if isinstance(val, dict):
                    inspect_item(val)
                elif isinstance(val, (list, tuple)):
                    for v in val:
                        inspect_item(v)

    for b in blocks:
        if isinstance(b, (list, tuple)):
            for sub_b in b:
                inspect_item(sub_b)
        else:
            inspect_item(b)

    return candidates


def verify_html_brand_entity_in_llm_memory(
    html_content: str,
    brand_name: Optional[str] = None,
    brand_domain: Optional[str] = None,
    rel_path: str = "index.html",
) -> Dict[str, Any]:
    """
    In-memory validation helper for an HTML document string against Factor 3: Brand / Entity in LLM Memory (+2.08).
    Verifies canonical entity definitions, unambiguous entity taxonomy, absolute @id, and sameAs linking with Wikidata.
    Zero em-dashes. Zero en-dashes.
    """
    issues: List[str] = []
    if not isinstance(html_content, str):
        return {
            "status": "FAIL",
            "gate": "check_brand_entity_in_llm_memory_gate",
            "violations_count": 1,
            "issues": [f"Page {rel_path}: HTML content must be a string"],
            "entities_count": 0,
        }

    # Strict anti-slop check
    if "\u2014" in html_content:
        issues.append(f"Page {rel_path}: Document contains forbidden em-dash")
    if "\u2013" in html_content:
        issues.append(f"Page {rel_path}: Document contains forbidden en-dash")

    pattern = re.compile(
        r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.IGNORECASE | re.DOTALL,
    )
    raw_blocks = pattern.findall(html_content)
    if not raw_blocks:
        issues.append(
            f"Page {rel_path}: Missing Schema.org JSON-LD structured data (<script type='application/ld+json'> not found)"
        )
        return {
            "status": "FAIL",
            "gate": "check_brand_entity_in_llm_memory_gate",
            "violations_count": len(issues),
            "issues": issues,
            "entities_count": 0,
        }

    parsed_blocks = []
    for idx, raw_json in enumerate(raw_blocks):
        try:
            parsed_blocks.append(json.loads(raw_json.strip()))
        except Exception as ex:
            issues.append(f"Page {rel_path}: Invalid JSON-LD syntax in block {idx}: {ex}")

    if not parsed_blocks:
        return {
            "status": "FAIL",
            "gate": "check_brand_entity_in_llm_memory_gate",
            "violations_count": len(issues),
            "issues": issues,
            "entities_count": 0,
        }

    candidates = extract_canonical_brand_entities(
        parsed_blocks,
        brand_name=brand_name,
        brand_domain=brand_domain,
    )

    if not candidates:
        issues.append(
            f"Page {rel_path}: Missing canonical brand or organization entity definition in structured data"
        )
        return {
            "status": "FAIL",
            "gate": "check_brand_entity_in_llm_memory_gate",
            "violations_count": len(issues),
            "issues": issues,
            "entities_count": 0,
        }

    from pseofactory.contracts import assert_canonical_entity_definition

    valid_entities = 0
    candidate_errors: List[str] = []
    for cand in candidates:
        try:
            assert_canonical_entity_definition(
                cand,
                brand_name=brand_name,
                brand_domain=brand_domain,
                context=f"Page {rel_path}",
            )
            valid_entities += 1
        except Exception as ex:
            candidate_errors.append(str(ex))

    if valid_entities == 0:
        for err in candidate_errors:
            issues.append(f"Page {rel_path}: {err}")

    return {
        "status": "PASS" if not issues else "FAIL",
        "gate": "check_brand_entity_in_llm_memory_gate",
        "violations_count": len(issues),
        "issues": issues,
        "entities_count": valid_entities,
    }


def verify_html_citable_specific_facts(
    html_content: str,
    rel_path: str = "index.html",
    min_statutory_citations: int = 1,
    min_numeric_facts: int = 3,
    require_data_table: bool = True,
) -> Dict[str, Any]:
    """
    In-memory validation helper for an HTML document string against Factor 4: Citable / Specific Facts (+2.07).
    Verifies:
    1. Zero em-dashes and zero en-dashes.
    2. Primary statutory citations present with valid syntax (CFR, USC, IRC, IRS guidance).
    3. Zero malformed statutory syntax.
    4. Zero vague generalizations disguised as factual analysis.
    5. High numeric data density and zero incomplete figures.
    6. Structured data table present, well-formed, and not an unstructured narrative block.
    7. Zero unreferenced statistics lacking primary citations.
    Zero em-dashes. Zero en-dashes.
    """
    issues: List[str] = []
    if not isinstance(html_content, str):
        return {
            "status": "FAIL",
            "gate": "check_citable_specific_facts_gate",
            "violations_count": 1,
            "issues": [f"Page {rel_path}: HTML content must be a string"],
            "statutory_citations_count": 0,
            "numeric_facts_count": 0,
            "tables_count": 0,
        }

    # Strict anti-slop check
    if "\u2014" in html_content:
        issues.append(f"Page {rel_path}: Document contains forbidden em-dash")
    if "\u2013" in html_content:
        issues.append(f"Page {rel_path}: Document contains forbidden en-dash")

    from pseofactory.contracts import (
        extract_statutory_citations,
        detect_malformed_statutory_citations,
        detect_vague_generalizations,
        detect_incomplete_figures,
        extract_numeric_facts,
        assert_data_table_structure,
    )

    # Vague generalizations check
    vague_phrases = detect_vague_generalizations(html_content)
    for vp in vague_phrases:
        issues.append(
            f"Page {rel_path}: Vague generalization disguised as factual analysis ('{vp}') "
            f"lacks primary statutory citation"
        )

    # Malformed statutory citations check
    malformed = detect_malformed_statutory_citations(html_content)
    for m in malformed:
        issues.append(f"Page {rel_path}: {m}")

    # Incomplete figures check
    incomp = detect_incomplete_figures(html_content)
    for inc in incomp:
        issues.append(f"Page {rel_path}: {inc}")

    # Primary statutory citations check
    citations = extract_statutory_citations(html_content)
    if len(citations) < min_statutory_citations:
        issues.append(
            f"Page {rel_path}: Statutory citation deficit: found {len(citations)} citations, "
            f"strictly requires >= {min_statutory_citations} primary statutory references (CFR, USC, IRC, or IRS code)"
        )

    # Unreferenced statistics check
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
    text_lower = html_content.lower()
    has_reg_claim = any(k in text_lower for k in regulatory_keywords)
    if has_reg_claim and not citations:
        issues.append(
            f"Page {rel_path}: Unreferenced statistics lacking primary citations: "
            f"regulatory or statutory thresholds claimed without primary citation"
        )

    # Numeric data density check
    facts = extract_numeric_facts(html_content)
    if len(facts) < min_numeric_facts:
        issues.append(
            f"Page {rel_path}: Numeric data density deficit: found {len(facts)} numeric facts, "
            f"strictly requires >= {min_numeric_facts} verifiable figures"
        )

    # Data table check
    parser = SinglePassSEODocumentParser()
    parser.feed(html_content)

    if require_data_table:
        if "<table" not in html_content.lower():
            issues.append(f"Page {rel_path}: Missing <table> element required for structured data points")
        else:
            try:
                assert_data_table_structure(html_content, context=f"Page {rel_path}")
            except Exception as ex:
                issues.append(str(ex))

    return {
        "status": "PASS" if not issues else "FAIL",
        "gate": "check_citable_specific_facts_gate",
        "violations_count": len(issues),
        "issues": issues,
        "statutory_citations_count": len(citations),
        "numeric_facts_count": len(facts),
        "tables_count": len(parser.tables_data),
    }


def verify_html_organic_fan_out_coverage(
    html_content: str,
    rel_path: str = "index.html",
    min_subqueries: int = 2,
    min_variants: int = 2,
    require_reciprocal: bool = True,
    min_words_per_answer: int = 15,
    min_total_words: int = 150,
) -> Dict[str, Any]:
    """
    In-memory validation helper for an HTML document string against Factor 5: Organic Fan-Out Coverage Rankings (+1.91).
    Verifies:
    1. Zero em-dashes and zero en-dashes.
    2. Substantive content depth avoiding thin page cannibalization.
    3. Clustered subqueries covering related sub-questions and secondary intent.
    4. Rejection of shallow question lists.
    5. Calculation variant nodes with actual calculation logic.
    6. Reciprocal bidirectional cross-links between fan-out nodes without orphaned nodes.
    Zero em-dashes. Zero en-dashes.
    """
    issues: List[str] = []
    if not isinstance(html_content, str):
        return {
            "status": "FAIL",
            "gate": "check_organic_fan_out_coverage_gate",
            "violations_count": 1,
            "issues": [f"Page {rel_path}: HTML content must be a string"],
            "subqueries_count": 0,
            "calculation_variants_count": 0,
            "cross_links_count": 0,
            "orphaned_nodes_count": 0,
        }

    # Strict anti-slop check
    if "\u2014" in html_content:
        issues.append(f"Page {rel_path}: Document contains forbidden em-dash")
    if "\u2013" in html_content:
        issues.append(f"Page {rel_path}: Document contains forbidden en-dash")

    from pseofactory.contracts import (
        assert_no_thin_fan_out_cannibalization,
        assert_subquery_clustering,
        assert_calculation_variant_cross_links,
        extract_subquery_sections,
        extract_calculation_variant_nodes,
        detect_orphaned_calculation_nodes,
    )

    # 1. Thin page check
    try:
        assert_no_thin_fan_out_cannibalization(html_content, min_words=min_total_words, context=f"Page {rel_path}")
    except Exception as ex:
        issues.append(str(ex))

    # 2. Subquery clustering check
    try:
        assert_subquery_clustering(
            html_content,
            min_subqueries=min_subqueries,
            min_words_per_answer=min_words_per_answer,
            context=f"Page {rel_path}",
        )
    except Exception as ex:
        issues.append(str(ex))

    # 3. Calculation variant cross-links check
    try:
        assert_calculation_variant_cross_links(
            html_content,
            min_variants=min_variants,
            require_reciprocal=require_reciprocal,
            context=f"Page {rel_path}",
        )
    except Exception as ex:
        issues.append(str(ex))

    subqueries = [s for s in extract_subquery_sections(html_content) if s.get("is_subquery")]
    variants = extract_calculation_variant_nodes(html_content)
    total_links = sum(len(v.get("outgoing_links", [])) for v in variants)
    orphaned = detect_orphaned_calculation_nodes(variants)

    return {
        "status": "PASS" if not issues else "FAIL",
        "gate": "check_organic_fan_out_coverage_gate",
        "violations_count": len(issues),
        "issues": issues,
        "subqueries_count": len(subqueries),
        "calculation_variants_count": len(variants),
        "cross_links_count": total_links,
        "orphaned_nodes_count": len(orphaned),
    }


def verify_html_organic_search_ranking(
    html_content: str,
    rel_path: str = "index.html",
    known_routes: Optional[Set[str]] = None,
    expected_canonical: Optional[str] = None,
    base_domain: Optional[str] = None,
    ssr_latency_ms: Optional[float] = None,
    max_ssr_latency_ms: float = 100.0,
) -> Dict[str, Any]:
    """
    In-memory validation helper for an HTML document string against Factor 6: Organic Search Ranking (+1.89).
    Verifies:
    1. Zero em-dashes and zero en-dashes.
    2. Title tag length strictly 30-65 characters.
    3. Exactly one non-empty H1 tag without empty heading containers.
    4. Meta description length strictly 70-160 characters.
    5. Canonical consistency without drift or unnormalized URLs.
    6. Internal link graph integrity with zero broken links.
    7. Sub-100ms static SSR response benchmark.
    Zero em-dashes. Zero en-dashes.
    """
    issues: List[str] = []
    if not isinstance(html_content, str):
        return {
            "status": "FAIL",
            "gate": "check_organic_search_ranking_gate",
            "violations_count": 1,
            "issues": [f"Page {rel_path}: HTML content must be a string"],
        }

    from pseofactory.contracts import assert_organic_search_ranking

    current_route = "/" + rel_path if not rel_path.startswith("/") else rel_path
    if current_route.endswith("/index.html"):
        current_route = current_route[:-10]
    elif current_route == "/index.html":
        current_route = "/"

    try:
        assert_organic_search_ranking(
            html_content,
            current_route=current_route,
            known_routes=known_routes,
            expected_canonical=expected_canonical,
            base_domain=base_domain,
            ssr_latency_ms=ssr_latency_ms,
            max_ssr_latency_ms=max_ssr_latency_ms,
            context=f"Page {rel_path}",
        )
    except Exception as ex:
        issues.append(str(ex))

    return {
        "status": "PASS" if not issues else "FAIL",
        "gate": "check_organic_search_ranking_gate",
        "violations_count": len(issues),
        "issues": issues,
    }


def verify_html_unique_first_party_information(
    html_content: str,
    rel_path: str = "index.html",
    manifests_dir: Optional[Path] = None,
    require_multi_dataset: bool = True,
    manifest_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    In-memory validation helper for an HTML document string against Factor 7: Unique / First-Party Information (+1.85).
    Verifies:
    1. Zero em-dashes and zero en-dashes.
    2. Zero ungrounded synthetic claims or mock datasets lacking verified formulas.
    3. Substantive firsthand content without thin syndicated templates.
    4. Unique calculation manifest presence, schema completeness, and formula input/output parity.
    5. Multi-dataset enrichment joining statutory figures with economic BLS and FRED data.
    6. Zero orphaned calculation tables missing statutory provenance.
    Zero em-dashes. Zero en-dashes.
    """
    issues: List[str] = []
    if not isinstance(html_content, str):
        return {
            "status": "FAIL",
            "gate": "check_unique_first_party_information_gate",
            "violations_count": 1,
            "issues": [f"Page {rel_path}: HTML content must be a string"],
            "manifests_count": 0,
            "multi_dataset_joins_count": 0,
            "orphaned_tables_count": 0,
        }

    # Strict anti-slop check
    if "\u2014" in html_content:
        issues.append(f"Page {rel_path}: Document contains forbidden em-dash")
    if "\u2013" in html_content:
        issues.append(f"Page {rel_path}: Document contains forbidden en-dash")

    from pseofactory.contracts import (
        detect_ungrounded_synthetic_claims,
        detect_orphaned_calculation_tables,
        extract_calculation_manifests,
        assert_unique_calculation_manifest,
        assert_multi_dataset_enrichment,
        assert_no_thin_syndicated_content,
    )

    # 1. Ungrounded synthetic claims check
    syn_issues = detect_ungrounded_synthetic_claims(html_content)
    for si in syn_issues:
        issues.append(f"Page {rel_path}: {si}")

    # 2. Thin syndicated content check
    try:
        assert_no_thin_syndicated_content(html_content, context=f"Page {rel_path}")
    except Exception as ex:
        issues.append(str(ex))

    # 3. Orphaned calculation tables check
    orphaned_tables = detect_orphaned_calculation_tables(html_content)
    for ot in orphaned_tables:
        issues.append(f"Page {rel_path}: {ot}")

    # 4. Multi-dataset enrichment check
    joins_count = 0
    if require_multi_dataset:
        try:
            assert_multi_dataset_enrichment(html_content, context=f"Page {rel_path}")
            joins_count += 1
        except Exception as ex:
            issues.append(str(ex))

    # 5. Calculation manifests extraction and validation
    manifests = extract_calculation_manifests(html_content)
    if manifest_data:
        manifests.append(manifest_data)
    if not manifests and manifests_dir:
        m_dir = Path(manifests_dir)
        if m_dir.is_dir():
            stem = Path(rel_path).stem
            if stem == "index":
                parent_name = Path(rel_path).parent.name
                cand_files = [m_dir / f"{parent_name}.json", m_dir / "index.json"]
            else:
                cand_files = [m_dir / f"{stem}.json"]
            for cf in cand_files:
                if cf.is_file():
                    try:
                        m_parsed = json.loads(cf.read_text(encoding="utf-8"))
                        manifests.append(m_parsed)
                    except Exception:
                        pass
            if not manifests:
                all_jsons = list(m_dir.glob("*.json"))
                if len(all_jsons) == 1:
                    try:
                        manifests.append(json.loads(all_jsons[0].read_text(encoding="utf-8")))
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
            issues.append(
                f"Page {rel_path}: Missing firsthand calculation manifest or proprietary model specification"
            )
    else:
        for m in manifests:
            try:
                assert_unique_calculation_manifest(m, context=f"Page {rel_path}")
            except Exception as ex:
                issues.append(str(ex))

    return {
        "status": "PASS" if not issues else "FAIL",
        "gate": "check_unique_first_party_information_gate",
        "violations_count": len(issues),
        "issues": issues,
        "manifests_count": len(manifests),
        "multi_dataset_joins_count": joins_count,
        "orphaned_tables_count": len(orphaned_tables),
    }


def verify_html_cross_web_consensus_and_corroboration(
    html_content: str,
    rel_path: str = "index.html",
    require_corroboration: bool = False,
    statutory_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    In-memory validation helper for an HTML document string against Factor 8: Cross-Web Consensus & Corroboration (+1.81).
    Verifies:
    1. Zero em-dashes and zero en-dashes.
    2. Zero uncorroborated tax constants, invented statutory limits, or orphaned deduction figures.
    3. Standard tax brackets match official published schedules.
    4. Statutory limits (Section 179, Section 1202 QSBS, 401(k), IRA, HSA) match official published schedules.
    5. Standard deduction figures match official published schedules.
    6. Zero silent fallback defaults.
    Zero em-dashes. Zero en-dashes.
    """
    issues: List[str] = []
    if not isinstance(html_content, str):
        return {
            "status": "FAIL",
            "gate": "check_cross_web_consensus_and_corroboration_gate",
            "violations_count": 1,
            "issues": [f"Page {rel_path}: HTML content must be a string"],
            "verified_constants_count": 0,
        }

    # Strict anti-slop check
    if "\u2014" in html_content:
        issues.append(f"Page {rel_path}: Document contains forbidden em-dash")
    if "\u2013" in html_content:
        issues.append(f"Page {rel_path}: Document contains forbidden en-dash")

    from pseofactory.contracts import (
        detect_uncorroborated_statutory_claims,
        assert_cross_web_consensus_and_corroboration,
    )

    detected = detect_uncorroborated_statutory_claims(html_content, rel_path=rel_path)
    issues.extend(detected)

    try:
        assert_cross_web_consensus_and_corroboration(
            html_content,
            require_corroboration=require_corroboration,
            context=f"Page {rel_path}",
        )
    except Exception as ex:
        err_msg = str(ex)
        if err_msg not in issues:
            issues.append(err_msg)

    verified_tokens = [
        "1,250,000", "1,220,000", "1,290,000",
        "3,130,000", "3,050,000", "3,220,000",
        "15,000", "30,000", "14,600", "29,200", "8,600", "17,200",
        "50,000,000", "10,000,000",
        "23,500", "23,000", "24,000",
        "7,000", "7,500",
    ]
    verified_count = sum(1 for token in verified_tokens if token in html_content)

    return {
        "status": "PASS" if not issues else "FAIL",
        "gate": "check_cross_web_consensus_and_corroboration_gate",
        "violations_count": len(issues),
        "issues": issues,
        "verified_constants_count": verified_count,
    }


verify_html_cross_web_corroboration = verify_html_cross_web_consensus_and_corroboration


def verify_html_source_publisher_reputation(
    html_content: str,
    rel_path: str = "index.html",
    require_strict: bool = False,
) -> Dict[str, Any]:
    """
    In-memory validation helper for an HTML document string against Factor 9: Source / Publisher Reputation (+1.78).
    Verifies:
    1. Zero em-dashes and zero en-dashes.
    2. Publisher authority: non-empty, non-anonymous Organization schema with valid name and URL.
    3. Author credentials: verified Person schema with credentials, jobTitle, or expertise, and profile link.
    4. Zero anonymous author attributions (Anonymous, Admin, Staff, etc.).
    5. Editorial review policy: publishingPrinciples, editorialPolicy, or reviewedBy link/attribution.
    6. Date freshness signals: valid ISO-8601 datePublished and dateModified with verified chronology.
    7. Transparent about and contact linkages in navigation, footer, or structured data.
    Zero em-dashes. Zero en-dashes.
    """
    issues: List[str] = []
    if not isinstance(html_content, str):
        return {
            "status": "FAIL",
            "gate": "check_source_publisher_reputation_gate",
            "violations_count": 1,
            "issues": [f"Page {rel_path}: HTML content must be a string"],
            "authors_count": 0,
            "publishers_count": 0,
        }

    # Strict anti-slop check
    if "\u2014" in html_content:
        issues.append(f"Page {rel_path}: Document contains forbidden em-dash")
    if "\u2013" in html_content:
        issues.append(f"Page {rel_path}: Document contains forbidden en-dash")

    from pseofactory.contracts import (
        detect_publisher_reputation_issues,
        assert_source_publisher_reputation,
        extract_author_and_publisher_metadata,
    )

    detected = detect_publisher_reputation_issues(html_content, rel_path=rel_path, require_strict=require_strict)
    issues.extend(detected)

    try:
        assert_source_publisher_reputation(
            html_content,
            require_strict=require_strict,
            context=f"Page {rel_path}",
        )
    except Exception as ex:
        err_msg = str(ex)
        if err_msg not in issues:
            issues.append(err_msg)

    meta = extract_author_and_publisher_metadata(html_content)

    return {
        "status": "PASS" if not issues else "FAIL",
        "gate": "check_source_publisher_reputation_gate",
        "violations_count": len(issues),
        "issues": issues,
        "authors_count": len(meta.get("authors", [])),
        "publishers_count": len(meta.get("publishers", [])),
        "has_editorial_policy": meta.get("has_editorial_policy", False),
        "has_about_link": meta.get("has_about_link", False),
        "has_contact_link": meta.get("has_contact_link", False),
        "date_published": meta.get("date_published"),
        "date_modified": meta.get("date_modified"),
    }


verify_html_publisher_reputation = verify_html_source_publisher_reputation


def verify_html_extractable_content_structure(
    html_content: str,
    rel_path: str = "index.html",
    require_strict: bool = False,
) -> Dict[str, Any]:
    """
    In-memory validation helper for an HTML document string against Factor 10: Extractable Content Structure (+1.69).
    Verifies:
    1. Zero em-dashes and zero en-dashes.
    2. Strict semantic HTML heading hierarchy without skipped levels (e.g. h1 to h3).
    3. Structured data tables with explicit column scopes (scope="col") on <th> headers.
    4. Ordered lists (<ol>) for sequential procedural steps; rejects unordered bullets (<ul>) for procedures.
    5. Clean passage-level blocks without empty tags or monolithic dumps.
    Zero em-dashes. Zero en-dashes.
    """
    issues: List[str] = []
    if not isinstance(html_content, str):
        return {
            "status": "FAIL",
            "gate": "check_extractable_content_structure_gate",
            "violations_count": 1,
            "issues": [f"Page {rel_path}: HTML content must be a string"],
            "headings_count": 0,
            "tables_count": 0,
            "ordered_steps_count": 0,
            "ordered_lists_count": 0,
            "unordered_lists_count": 0,
            "passages_count": 0,
            "has_heading_skips": False,
            "has_unscoped_tables": False,
        }

    # Strict anti-slop check
    if "\u2014" in html_content:
        issues.append(f"Page {rel_path}: Document contains forbidden em-dash")
    if "\u2013" in html_content:
        issues.append(f"Page {rel_path}: Document contains forbidden en-dash")

    from pseofactory.contracts import (
        detect_extractable_content_issues,
        assert_extractable_content_structure,
        extract_content_structure_metadata,
    )

    detected = detect_extractable_content_issues(
        html_content,
        rel_path=rel_path,
        require_strict=require_strict,
    )
    issues.extend(detected)

    try:
        assert_extractable_content_structure(
            html_content,
            require_strict=require_strict,
            context=f"Page {rel_path}",
        )
    except Exception as ex:
        err_msg = str(ex)
        if err_msg not in issues:
            issues.append(err_msg)

    meta = extract_content_structure_metadata(html_content)
    ordered_steps_count = sum(len(b.get("items", [])) for b in meta.get("ordered_lists", []))

    return {
        "status": "PASS" if not issues else "FAIL",
        "gate": "check_extractable_content_structure_gate",
        "violations_count": len(issues),
        "issues": issues,
        "headings_count": len(meta.get("headings", [])),
        "tables_count": len(meta.get("tables", [])),
        "ordered_steps_count": ordered_steps_count,
        "ordered_lists_count": len(meta.get("ordered_lists", [])),
        "unordered_lists_count": len(meta.get("unordered_lists", [])),
        "passages_count": len(meta.get("passages", [])),
        "has_heading_skips": bool(meta.get("heading_skips")),
        "has_unscoped_tables": any(bool(t.get("unscoped_headers")) for t in meta.get("tables", [])),
    }


verify_html_extractable_structure = verify_html_extractable_content_structure


def verify_html_answer_prominence(
    html_content: str,
    rel_path: str = "index.html",
    max_words: int = 300,
    require_strict: bool = False,
) -> Dict[str, Any]:
    """
    In-memory validation helper for an HTML document string against Factor 11: Answer Prominence (+1.65).
    Verifies:
    1. Zero em-dashes and zero en-dashes.
    2. Direct answer container or core calculation widget is present.
    3. Answer or calculation widget appears above the fold (within first 300 body words).
    4. Direct answer container is non-empty.
    5. No secondary discussion appears before the direct answer or calculation widget.
    Zero em-dashes. Zero en-dashes.
    """
    issues: List[str] = []
    if not isinstance(html_content, str):
        return {
            "status": "FAIL",
            "gate": "check_answer_prominence_gate",
            "violations_count": 1,
            "issues": [f"Page {rel_path}: HTML content must be a string"],
            "answer_found": False,
            "answer_type": "none",
            "word_position": -1,
            "total_body_words": 0,
            "is_above_fold": False,
            "dom_depth": 0,
            "has_secondary_discussion_before_answer": False,
        }

    # Strict anti-slop check
    if "\u2014" in html_content:
        issues.append(f"Page {rel_path}: Document contains forbidden em-dash")
    if "\u2013" in html_content:
        issues.append(f"Page {rel_path}: Document contains forbidden en-dash")

    from pseofactory.contracts import (
        detect_answer_prominence_issues,
        assert_answer_prominence,
        extract_answer_prominence_metadata,
    )

    detected = detect_answer_prominence_issues(
        html_content,
        rel_path=rel_path,
        max_words=max_words,
        require_strict=require_strict,
    )
    issues.extend(detected)

    try:
        assert_answer_prominence(
            html_content,
            max_words=max_words,
            require_strict=require_strict,
            context=f"Page {rel_path}",
        )
    except Exception as ex:
        err_msg = str(ex)
        if err_msg not in issues:
            issues.append(err_msg)

    meta = extract_answer_prominence_metadata(html_content)

    return {
        "status": "PASS" if not issues else "FAIL",
        "gate": "check_answer_prominence_gate",
        "violations_count": len(issues),
        "issues": issues,
        "answer_found": meta.get("answer_found", False),
        "answer_type": meta.get("answer_type", "none"),
        "word_position": meta.get("answer_word_position", -1),
        "total_body_words": meta.get("total_body_words", 0),
        "is_above_fold": meta.get("is_above_fold", False),
        "dom_depth": meta.get("dom_depth", 0),
        "has_secondary_discussion_before_answer": meta.get("has_secondary_discussion_before_answer", False),
    }


verify_html_answer_above_fold = verify_html_answer_prominence
verify_html_core_answer_prominence = verify_html_answer_prominence


def verify_html_structured_data(
    html_content: str,
    rel_path: str = "index.html",
    require_strict: bool = False,
    require_free_app_schema: bool = False,
) -> Dict[str, Any]:
    """
    Mechanical single-page verification function for Factor 12: Structured Data (+0.80).
    Verifies:
    1. Zero em-dashes and zero en-dashes.
    2. Machine-readable Schema.org JSON-LD markup with valid syntax.
    3. Valid entity structures across SoftwareApplication, WebApplication,
       Product, FAQPage, HowTo, and Dataset schemas.
    4. Clean graph architecture without unanchored leaf entities or broken references.
    5. Consolidated unified graphs without disconnected script tags.
    Zero em-dashes. Zero en-dashes.
    """
    issues: List[str] = []
    if not isinstance(html_content, str):
        return {
            "status": "FAIL",
            "gate": "check_structured_data_gate",
            "violations_count": 1,
            "issues": [f"Page {rel_path}: HTML content must be a string"],
            "schemas_found": [],
            "target_schemas": [],
            "graphs_count": 0,
            "entities_count": 0,
        }

    # Strict anti-slop check
    if "\u2014" in html_content:
        issues.append(f"Page {rel_path}: Document contains forbidden em-dash")
    if "\u2013" in html_content:
        issues.append(f"Page {rel_path}: Document contains forbidden en-dash")

    from pseofactory.contracts import (
        detect_structured_data_issues,
        assert_structured_data,
        extract_structured_data_metadata,
    )

    detected = detect_structured_data_issues(
        html_content,
        rel_path=rel_path,
        require_strict=require_strict,
    )
    issues.extend(detected)

    if require_free_app_schema:
        from pseofactory.contracts import detect_free_web_application_schema_issues
        free_issues = detect_free_web_application_schema_issues(html_content, rel_path=rel_path)
        issues.extend(free_issues)

    try:
        assert_structured_data(
            html_content,
            require_strict=require_strict,
            context=f"Page {rel_path}",
        )
    except Exception as ex:
        err_msg = str(ex)
        if err_msg not in issues:
            issues.append(err_msg)


    meta = extract_structured_data_metadata(html_content)

    return {
        "status": "PASS" if not issues else "FAIL",
        "gate": "check_structured_data_gate",
        "violations_count": len(issues),
        "issues": issues,
        "schemas_found": meta.get("schema_types", []),
        "target_schemas": meta.get("target_schemas_found", []),
        "graphs_count": len(meta.get("parsed_graphs", [])),
        "entities_count": meta.get("total_entities", 0),
    }


verify_html_schema_org_structured_data = verify_html_structured_data
verify_html_jsonld_structured_data = verify_html_structured_data
verify_html_schema_graphs = verify_html_structured_data


def verify_llms_txt_content(
    content: str,
    rel_path: str = "llms.txt",
    is_full: bool = False,
    require_strict: bool = False,
) -> Dict[str, Any]:
    """
    Mechanical in-memory validation function for Factor 13: llms.txt File (+0.05).
    Verifies:
    1. Zero em-dashes and zero en-dashes.
    2. H1 project/site title conforming to llmstxt.org specification.
    3. Blockquote summary immediately following H1 (for llms.txt).
    4. Top category hubs include concise markdown summaries.
    5. Zero exposure or leaking of private administrative routes or internal paths.
    Zero em-dashes. Zero en-dashes.
    """
    issues: List[str] = []
    if not isinstance(content, str):
        return {
            "status": "FAIL",
            "gate": "check_llms_txt_gate",
            "violations_count": 1,
            "issues": [f"{rel_path}: Manifest content must be a string"],
            "hubs_verified": 0,
            "links_verified": 0,
            "has_h1": False,
            "has_blockquote": False,
        }

    # Strict anti-slop check
    if "\u2014" in content:
        issues.append(f"{rel_path}: Document contains forbidden em-dash")
    if "\u2013" in content:
        issues.append(f"{rel_path}: Document contains forbidden en-dash")

    from pseofactory.contracts import (
        detect_llms_txt_issues,
        assert_llms_txt,
        extract_llms_txt_metadata,
    )

    detected = detect_llms_txt_issues(
        content,
        rel_path=rel_path,
        is_full=is_full,
        require_strict=require_strict,
    )
    issues.extend(detected)

    try:
        assert_llms_txt(
            content,
            is_full=is_full,
            require_strict=require_strict,
            context=rel_path,
        )
    except Exception as ex:
        err_msg = str(ex)
        if err_msg not in issues:
            issues.append(err_msg)

    meta = extract_llms_txt_metadata(content)

    return {
        "status": "PASS" if not issues else "FAIL",
        "gate": "check_llms_txt_gate",
        "violations_count": len(issues),
        "issues": issues,
        "hubs_verified": len(meta.get("category_hubs", [])),
        "links_verified": len(meta.get("links", [])),
        "has_h1": meta.get("has_h1", False),
        "has_blockquote": meta.get("has_blockquote", False),
    }


def verify_llms_txt_manifest_pair(
    llms_txt_content: str,
    llms_full_txt_content: str,
    require_strict: bool = True,
) -> Dict[str, Any]:
    """
    Mechanical in-memory validation function verifying a paired llms.txt and llms-full.txt manifest.
    Zero em-dashes. Zero en-dashes.
    """
    r1 = verify_llms_txt_content(llms_txt_content, rel_path="llms.txt", is_full=False, require_strict=require_strict)
    r2 = verify_llms_txt_content(llms_full_txt_content, rel_path="llms-full.txt", is_full=True, require_strict=require_strict)

    all_issues = list(r1.get("issues", [])) + list(r2.get("issues", []))
    return {
        "status": "PASS" if not all_issues else "FAIL",
        "gate": "check_llms_txt_gate",
        "violations_count": len(all_issues),
        "issues": all_issues,
        "llms_txt": r1,
        "llms_full_txt": r2,
    }


verify_llms_full_txt_content = verify_llms_txt_content


def verify_html_tool_utility_contract(
    html_content: str,
    rel_path: str = "index.html",
) -> Dict[str, Any]:
    """
    In-memory validation helper for an HTML document string against ToolUtilityContract.
    Verifies:
    1. Zero em-dashes and zero en-dashes.
    2. Interactive form or container presence.
    3. Input elements paired with label or aria-label.
    4. Dedicated submit CTA button.
    5. Touch targets meeting 44x44px standard.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.contracts import detect_tool_utility_issues, assert_tool_utility_contract

    issues: List[str] = []
    if not isinstance(html_content, str):
        return {
            "status": "FAIL",
            "gate": "check_tool_utility_gate",
            "violations_count": 1,
            "issues": [f"Page {rel_path}: HTML content must be a string"],
            "tool_valid": False,
        }

    detected = detect_tool_utility_issues(html_content, rel_path=rel_path)
    issues.extend(detected)

    try:
        assert_tool_utility_contract(html_content, context=f"Page {rel_path}")
    except Exception as ex:
        err_msg = str(ex)
        if err_msg not in issues:
            issues.append(err_msg)

    return {
        "status": "PASS" if not issues else "FAIL",
        "gate": "check_tool_utility_gate",
        "violations_count": len(issues),
        "issues": issues,
        "tool_valid": len(issues) == 0,
    }


def verify_html_free_web_application_schema(
    html_content: str,
    rel_path: str = "index.html",
) -> Dict[str, Any]:
    """
    In-memory validation helper for Free WebApplication / SoftwareApplication Schema.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.contracts import (
        detect_free_web_application_schema_issues,
        assert_free_web_application_schema,
    )

    issues: List[str] = []
    if not isinstance(html_content, str):
        return {
            "status": "FAIL",
            "gate": "check_free_web_application_schema_gate",
            "violations_count": 1,
            "issues": [f"Page {rel_path}: HTML content must be a string"],
            "schema_valid": False,
        }

    detected = detect_free_web_application_schema_issues(html_content, rel_path=rel_path)
    issues.extend(detected)

    try:
        assert_free_web_application_schema(html_content, context=f"Page {rel_path}")
    except Exception as ex:
        err_msg = str(ex)
        if err_msg not in issues:
            issues.append(err_msg)

    return {
        "status": "PASS" if not issues else "FAIL",
        "gate": "check_free_web_application_schema_gate",
        "violations_count": len(issues),
        "issues": issues,
        "schema_valid": len(issues) == 0,
    }


def verify_rate_limit_and_bot_shield(
    headers_or_html: Union[str, Dict[str, Any]],
    context: str = "",
) -> Dict[str, Any]:
    """
    In-memory validation helper for operational rate-limiting and bot shield defenses.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.contracts import (
        detect_rate_limit_and_bot_shield_issues,
        assert_rate_limit_and_bot_shield,
    )
    issues: List[str] = []
    detected = detect_rate_limit_and_bot_shield_issues(headers_or_html, context=context)
    issues.extend(detected)

    try:
        assert_rate_limit_and_bot_shield(headers_or_html, context=context)
    except Exception as ex:
        err_msg = str(ex)
        if err_msg not in issues:
            issues.append(err_msg)

    return {
        "status": "PASS" if not issues else "FAIL",
        "gate": "check_operational_shield_gate",
        "violations_count": len(issues),
        "issues": issues,
    }


check_existence_gate = _default_verifier.check_existence_gate
check_title_gate = _default_verifier.check_title_gate
check_snippet_gate = _default_verifier.check_snippet_gate
check_schema_gate = _default_verifier.check_schema_gate
check_citability_gate = _default_verifier.check_citability_gate
check_cleanliness_gate = _default_verifier.check_cleanliness_gate
check_indexing_gate = _default_verifier.check_indexing_gate
check_content_relevance_gate = _default_verifier.check_content_relevance_gate
audit_seo_checklist = _default_verifier.audit_seo_checklist
run_seo_checklist_audit = audit_seo_checklist

check_tool_utility_gate = _default_verifier.check_tool_utility_gate
verify_tool_utility_contract = _default_verifier.verify_tool_utility_contract
check_free_web_application_schema_gate = _default_verifier.check_free_web_application_schema_gate
verify_free_web_application_schema = _default_verifier.verify_free_web_application_schema
check_operational_shield_gate = _default_verifier.check_operational_shield_gate
verify_operational_shield = _default_verifier.verify_operational_shield


