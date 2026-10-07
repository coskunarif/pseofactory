"""
Unit tests for Factor 1: AI Crawl Access & Snippet Eligibility in pseofactory.
Verifies:
1. ZYPPY_2026_AI_FACTORS_SPEC registration, weights, and Factor 1 specification.
2. 3-tier AI crawler taxonomy (search bots, user-triggered bots, training bots).
3. SinglePassSEODocumentParser AI bot metadata directive parsing.
4. max-snippet boundary conditions and data-nosnippet scoping.
5. _headers X-Robots-Tag differentiation between search bots, training bots, and non-public routes.
6. robots.txt crawler policies for AI search crawlers in check_snippet_eligibility_gate.
7. Gate aliases and audit_seo_checklist integration.

Zero em-dashes. Zero en-dashes.
"""

import json
from pathlib import Path
import re
import pytest
from pseofactory.verifier import (
    MasterSEOVerifier,
    SinglePassSEODocumentParser,
    ZYPPY_2026_AI_FACTORS_SPEC,
    ZYPPY_2026_FACTORS_SPEC,
    AI_SEARCH_BOTS,
    AI_USER_TRIGGERED_BOTS,
    AI_TRAINING_BOTS,
    check_snippet_eligibility_gate,
    check_ai_crawl_access_and_snippet_eligibility_gate,
    check_ai_crawl_access_gate,
    verify_ai_crawl_access_and_snippet_eligibility,
    verify_html_ai_crawl_access_and_snippet_eligibility,
    check_query_answer_match_gate,
    check_query_answer_gate,
    verify_query_answer_match,
    verify_html_query_answer_match,
    evaluate_query_answer_semantic_match,
    check_brand_entity_in_llm_memory_gate,
    check_brand_entity_gate,
    check_entity_memory_gate,
    verify_brand_entity_in_llm_memory,
    verify_html_brand_entity_in_llm_memory,
    check_citable_specific_facts_gate,
    check_citable_facts_gate,
    check_specific_facts_gate,
    verify_citable_specific_facts,
    verify_html_citable_specific_facts,
    check_organic_fan_out_coverage_gate,
    check_fan_out_coverage_gate,
    check_organic_fan_out_gate,
    verify_organic_fan_out_coverage,
    verify_html_organic_fan_out_coverage,
    check_organic_search_ranking_gate,
    check_traditional_organic_search_gate,
    check_core_seo_hygiene_gate,
    verify_organic_search_ranking,
    verify_html_organic_search_ranking,
    check_unique_first_party_information_gate,
    check_first_party_information_gate,
    check_first_party_assets_gate,
    check_firsthand_calculations_gate,
    check_proprietary_models_gate,
    verify_unique_first_party_information,
    verify_html_unique_first_party_information,
    check_cross_web_consensus_and_corroboration_gate,
    check_cross_web_corroboration_gate,
    check_statutory_consensus_gate,
    check_baseline_fact_agreement_gate,
    check_statutory_constants_corroboration_gate,
    verify_cross_web_consensus_and_corroboration,
    verify_cross_web_corroboration,
    verify_html_cross_web_consensus_and_corroboration,
    verify_html_cross_web_corroboration,
    check_source_publisher_reputation_gate,
    check_publisher_reputation_gate,
    check_publisher_authority_gate,
    check_author_credentials_gate,
    check_editorial_policy_gate,
    verify_source_publisher_reputation,
    verify_publisher_reputation,
    verify_html_source_publisher_reputation,
    verify_html_publisher_reputation,
    check_extractable_content_structure_gate,
    check_extractable_structure_gate,
    check_semantic_heading_hierarchy_gate,
    check_scoped_table_headers_gate,
    check_procedural_ordered_steps_gate,
    verify_extractable_content_structure,
    verify_extractable_structure,
    verify_html_extractable_content_structure,
    verify_html_extractable_structure,
    check_answer_prominence_gate,
    check_answer_above_fold_gate,
    check_core_answer_prominence_gate,
    check_direct_answer_prominence_gate,
    check_calculation_widget_prominence_gate,
    check_early_answer_block_gate,
    verify_answer_prominence,
    verify_answer_above_fold,
    verify_core_answer_prominence,
    verify_html_answer_prominence,
    verify_html_answer_above_fold,
    verify_html_core_answer_prominence,
    check_structured_data_gate,
    check_schema_org_structured_data_gate,
    check_jsonld_structured_data_gate,
    check_schema_graphs_gate,
    check_target_entity_schemas_gate,
    check_machine_readable_schemas_gate,
    verify_structured_data,
    verify_schema_org_structured_data,
    verify_jsonld_structured_data,
    verify_schema_graphs,
    verify_html_structured_data,
    verify_html_schema_org_structured_data,
    verify_html_jsonld_structured_data,
    verify_html_schema_graphs,
    check_llms_txt_gate,
    check_llms_txt_file_gate,
    check_llms_full_txt_gate,
    check_llmstxt_gate,
    check_llms_manifest_gate,
    check_curated_llms_txt_gate,
    verify_llms_txt,
    verify_llms_txt_file,
    verify_llms_full_txt,
    verify_llmstxt,
    verify_curated_llms_txt,
    verify_llms_txt_content,
    verify_llms_full_txt_content,
    verify_llms_txt_manifest_pair,
    MockSearchEngineCrawler,
    simulate_crawler_traversal,
    extract_canonical_brand_entities,
    get_ai_factor_spec,
    is_ai_search_crawler,
    is_ai_training_crawler,
    is_ai_crawler,
)
from pseofactory.contracts import (
    assert_snippet_length_contract,
    assert_ai_crawl_access_and_snippet_eligibility,
    assert_ai_crawl_access,
    assert_snippet_eligibility,
    assert_robots_txt_crawler_policy,
    assert_headers_snippet_policy,
    assert_quick_answer_passage_relevance,
    assert_viewport_ordering,
    assert_query_answer_match,
    assert_quick_answer_match,
    assert_query_answer_alignment,
    assert_wikidata_uri,
    assert_authoritative_same_as,
    assert_brand_entity_taxonomy,
    assert_canonical_entity_definition,
    assert_brand_entity_in_llm_memory,
    assert_brand_entity_memory,
    assert_entity_memory_grounding,
    AUTHORITATIVE_PROFILE_DOMAINS,
    BRAND_ENTITY_TAXONOMY,
    DISALLOWED_BRAND_TAXONOMY,
    WIKIDATA_URI_PATTERN,
    AUTHORITATIVE_STATUTORY_DOMAINS,
    VAGUE_FACTUAL_GENERALIZATIONS,
    CFR_CITATION_PATTERN,
    USC_CITATION_PATTERN,
    IRC_CITATION_PATTERN,
    IRS_GUIDANCE_PATTERNS,
    NUMERIC_FACT_PATTERN,
    INCOMPLETE_FIGURE_PATTERNS,
    extract_statutory_citations,
    detect_malformed_statutory_citations,
    detect_vague_generalizations,
    detect_incomplete_figures,
    extract_numeric_facts,
    assert_statutory_citation_syntax,
    assert_no_vague_generalizations,
    assert_numeric_data_density,
    assert_data_table_structure,
    assert_citable_specific_facts,
    assert_citable_facts,
    assert_specific_facts,
    assert_primary_statutory_citations,
    SUBQUERY_QUESTION_STARTERS,
    SECONDARY_INTENT_KEYWORDS,
    extract_subquery_sections,
    detect_shallow_subquestions,
    assert_subquery_clustering,
    extract_calculation_variant_nodes,
    detect_orphaned_calculation_nodes,
    verify_calculation_variant_reciprocity,
    assert_calculation_variant_cross_links,
    assert_no_thin_fan_out_cannibalization,
    assert_organic_fan_out_coverage,
    assert_fan_out_coverage,
    assert_organic_fan_out,
    assert_no_forbidden_dashes,
    ORGANIC_SEARCH_TITLE_MIN_CHARS,
    ORGANIC_SEARCH_TITLE_MAX_CHARS,
    ORGANIC_SEARCH_META_DESC_MIN_CHARS,
    ORGANIC_SEARCH_META_DESC_MAX_CHARS,
    ORGANIC_SEARCH_MAX_SSR_LATENCY_MS,
    assert_organic_search_title,
    assert_single_h1_hierarchy,
    assert_organic_search_meta_description,
    assert_canonical_consistency,
    assert_internal_links_integrity,
    assert_ssr_response_latency,
    assert_organic_search_ranking,
    assert_traditional_organic_search_ranking,
    assert_core_seo_hygiene,
    ECONOMIC_DATASET_PATTERNS,
    UNGROUNDED_SYNTHETIC_PATTERNS,
    safe_eval_mathematical_formula,
    detect_ungrounded_synthetic_claims,
    detect_orphaned_calculation_tables,
    extract_calculation_manifests,
    extract_multi_dataset_joins,
    assert_proprietary_model_integrity,
    assert_unique_calculation_manifest,
    assert_multi_dataset_enrichment,
    assert_no_orphaned_calculation_tables,
    assert_no_thin_syndicated_content,
    assert_unique_first_party_information,
    assert_first_party_information,
    assert_first_party_assets,
    assert_firsthand_calculations,
    assert_proprietary_models,
    STATUTORY_TAX_BRACKETS,
    STATUTORY_STANDARD_DEDUCTIONS,
    STATUTORY_LIMITS,
    VALID_FEDERAL_TAX_RATES,
    ALL_OFFICIAL_STANDARD_DEDUCTIONS,
    get_official_tax_brackets,
    get_official_standard_deduction,
    get_official_statutory_limit,
    detect_uncorroborated_statutory_claims,
    assert_statutory_tax_brackets,
    assert_standard_deduction_values,
    assert_statutory_limits,
    assert_no_uncorroborated_tax_constants,
    assert_cross_web_consensus_and_corroboration,
    assert_cross_web_corroboration,
    assert_statutory_consensus,
    assert_baseline_fact_agreement,
    assert_statutory_constants_corroboration,
    ANONYMOUS_AUTHOR_PATTERNS,
    AUTHOR_CREDENTIAL_KEYWORDS,
    EDITORIAL_POLICY_HREF_PATTERNS,
    ABOUT_HREF_PATTERNS,
    CONTACT_HREF_PATTERNS,
    extract_schemas_from_json_ld,
    extract_author_and_publisher_metadata,
    detect_publisher_reputation_issues,
    assert_publisher_authority,
    assert_author_credentials,
    assert_person_organization_schema,
    assert_editorial_policy,
    assert_freshness_signals,
    assert_about_contact_linkages,
    assert_source_publisher_reputation,
    assert_publisher_reputation,
    assert_publisher_authority_and_credentials,
    assert_author_and_publisher_schema,
    assert_editorial_and_freshness_signals,
    PROCEDURAL_CONTAINER_KEYWORDS,
    PROCEDURAL_HEADING_PATTERN,
    PROCEDURAL_STEP_PREFIX_PATTERN,
    MAX_PASSAGE_CHAR_LENGTH,
    extract_content_structure_metadata,
    detect_extractable_content_issues,
    assert_semantic_heading_hierarchy,
    assert_scoped_table_headers,
    assert_procedural_ordered_steps,
    assert_passage_level_blocks,
    assert_extractable_content_structure,
    assert_extractable_structure,
    assert_content_structure_extractability,
    ANSWER_PROMINENCE_MAX_WORD_COUNT,
    ANSWER_CONTAINER_CLASS_KEYWORDS,
    CALCULATION_WIDGET_CLASS_KEYWORDS,
    SECONDARY_DISCUSSION_HEADING_KEYWORDS,
    extract_answer_prominence_metadata,
    detect_answer_prominence_issues,
    assert_answer_word_position,
    assert_direct_answer_or_widget_presence,
    assert_answer_above_the_fold,
    assert_answer_prominence,
    assert_answer_above_fold,
    assert_core_answer_prominence,
    assert_direct_answer_prominence,
    assert_calculation_widget_prominence,
    assert_early_answer_block,
    TARGET_ENTITY_SCHEMAS,
    SUPPORTED_AUXILIARY_SCHEMAS,
    ALL_REGISTERED_SCHEMAS,
    LEAF_ENTITY_SCHEMAS,
    extract_structured_data_metadata,
    detect_structured_data_issues,
    assert_structured_data,
    assert_valid_structured_data,
    assert_machine_readable_schema,
    assert_schema_org_jsonld,
    assert_schema_graph_structure,
    assert_target_entity_schemas,
    assert_schema_graph_connectivity,
    LLMS_TXT_DISALLOWED_ROUTE_PATTERNS,
    LLMS_TXT_HUB_HEADING_PATTERNS,
    extract_llms_txt_metadata,
    detect_llms_txt_issues,
    assert_llms_txt,
    assert_llms_txt_specification,
    assert_llms_txt_compliance,
    assert_llms_full_txt_compliance,
    assert_no_internal_route_leaks,
    assert_top_category_hubs_summaries,
    assert_llms_manifest_pair,
    assert_llms_txt_file,
    assert_curated_llms_txt,
)
import pseofactory.seo.verifier as seo_verifier
import pseofactory


def test_zyppy_2026_ai_factors_spec_registration():
    """Verifies ZYPPY_2026_AI_FACTORS_SPEC contains all 14 factors correctly weighted."""
    assert isinstance(ZYPPY_2026_AI_FACTORS_SPEC, list)
    assert len(ZYPPY_2026_AI_FACTORS_SPEC) == 14

    # Factor 1 must be AI Crawl Access & Snippet Eligibility with weight 2.20
    factor1 = ZYPPY_2026_AI_FACTORS_SPEC[0]
    assert factor1["code"] == "ai_crawl_access_and_snippet_eligibility"
    assert factor1["name"] == "AI Crawl Access & Snippet Eligibility"
    assert factor1["weight"] == 2.20
    assert factor1["positive_weight"] == 2.20
    assert factor1["negative_weight"] == -2.20

    # Factor 7 must be Unique First-Party Information with weight 1.85
    factor7 = ZYPPY_2026_AI_FACTORS_SPEC[6]
    assert factor7["code"] == "unique_first_party_information"
    assert factor7["name"] == "Unique First-Party Information"
    assert factor7["weight"] == 1.85
    assert factor7["positive_weight"] == 1.85
    assert factor7["negative_weight"] == -1.85
    assert "Unique / First-Party Information" in factor7.get("aliases", [])
    assert "unique_first_party_information" in factor7.get("aliases", [])

    # Factor 8 must be Cross-Web Consensus & Corroboration with weight 1.81
    factor8 = ZYPPY_2026_AI_FACTORS_SPEC[7]
    assert factor8["code"] == "cross_web_consensus_and_corroboration"
    assert factor8["name"] == "Cross-Web Consensus & Corroboration"
    assert factor8["weight"] == 1.81
    assert factor8["positive_weight"] == 1.81
    assert factor8["negative_weight"] == -1.81
    assert "Cross-Web Consensus & Corroboration" in factor8.get("aliases", [])
    assert "cross_web_corroboration" in factor8.get("aliases", [])
    assert "statutory_consensus" in factor8.get("aliases", [])

    # Weights must be monotonic non-increasing
    weights = [f["weight"] for f in ZYPPY_2026_AI_FACTORS_SPEC]
    assert weights == sorted(weights, reverse=True)
    assert weights[0] == 2.20
    assert weights[-1] == 0.05

    # Check re-exports from seo_verifier and pseofactory root
    assert seo_verifier.ZYPPY_2026_AI_FACTORS_SPEC is ZYPPY_2026_AI_FACTORS_SPEC
    assert pseofactory.ZYPPY_2026_AI_FACTORS_SPEC is ZYPPY_2026_AI_FACTORS_SPEC
    assert len(ZYPPY_2026_FACTORS_SPEC) == 12
    assert len(ZYPPY_2026_AI_FACTORS_SPEC) == 14


def test_ai_crawler_taxonomy():
    """Verifies 3-tier crawler taxonomy separation between search, user, and training bots."""
    search_set = set(AI_SEARCH_BOTS)
    user_set = set(AI_USER_TRIGGERED_BOTS)
    training_set = set(AI_TRAINING_BOTS)

    assert "perplexitybot" in search_set
    assert "claudebot" in search_set
    assert "oai-searchbot" in search_set
    assert "googlebot" in search_set
    assert "bingbot" in search_set

    assert "chatgpt-user" in user_set

    assert "gptbot" in training_set
    assert "ccbot" in training_set
    assert "google-extended" in training_set
    assert "anthropic-ai" in training_set

    # Search bots and training bots must be strictly disjoint
    assert search_set.isdisjoint(training_set)
    assert user_set.isdisjoint(training_set)


def test_single_pass_parser_ai_search_vs_training_bots():
    """Verifies SinglePassSEODocumentParser evaluates search crawlers and ignores training bots."""
    # Search crawler perplexitybot with nosnippet
    p1 = SinglePassSEODocumentParser()
    p1.feed('<!DOCTYPE html><html><head><meta name="perplexitybot" content="nosnippet"></head><body></body></html>')
    assert p1.has_nosnippet is True

    # Search crawler claudebot with noindex
    p2 = SinglePassSEODocumentParser()
    p2.feed('<!DOCTYPE html><html><head><meta name="claudebot" content="noindex"></head><body></body></html>')
    assert p2.has_noindex is True

    # User-triggered bot chatgpt-user with nosnippet
    p3 = SinglePassSEODocumentParser()
    p3.feed('<!DOCTYPE html><html><head><meta name="chatgpt-user" content="nosnippet"></head><body></body></html>')
    assert p3.has_nosnippet is True

    # Training bot google-extended must NOT set has_nosnippet or has_noindex
    p4 = SinglePassSEODocumentParser()
    p4.feed('<!DOCTYPE html><html><head><meta name="google-extended" content="nosnippet, noindex"></head><body></body></html>')
    assert p4.has_nosnippet is False
    assert p4.has_noindex is False

    # Training bot gptbot must NOT set has_nosnippet or has_noindex
    p5 = SinglePassSEODocumentParser()
    p5.feed('<!DOCTYPE html><html><head><meta name="gptbot" content="noindex, nosnippet"></head><body></body></html>')
    assert p5.has_nosnippet is False
    assert p5.has_noindex is False


def test_max_snippet_and_image_preview_parsing():
    """Verifies parsing of max-snippet, max-image-preview, and max-video-preview meta directives."""
    # Permissive max-snippet:-1
    p1 = SinglePassSEODocumentParser()
    p1.feed('<meta name="robots" content="max-snippet:-1, max-image-preview:large, max-video-preview:-1">')
    assert p1.max_snippet == -1
    assert p1.max_image_preview == "large"
    assert p1.max_video_preview == -1

    # Restrictive max-snippet:0
    p2 = SinglePassSEODocumentParser()
    p2.feed('<meta name="robots" content="max-snippet:0">')
    assert p2.max_snippet == 0


def test_snippet_eligibility_html_boundaries(tmp_path):
    """Verifies check_snippet_eligibility_gate catches HTML snippet boundary violations."""
    dist = tmp_path / "dist"
    dist.mkdir()

    # 1. max-snippet:0 fails
    page0 = dist / "page0.html"
    page0.write_text(
        '<!DOCTYPE html><html><head><title>Test</title><meta name="robots" content="max-snippet:0"></head>'
        '<body><h1>Header</h1><aside class="quick-answer">Direct answer text here.</aside></body></html>',
        encoding="utf-8"
    )
    verifier = MasterSEOVerifier(dist_dir=dist)
    res0 = verifier.check_snippet_eligibility_gate(dist)
    assert res0["status"] == "FAIL"
    assert any("max-snippet:0" in i for i in res0["issues"])
    page0.unlink()

    # 2. max-snippet:20 with longer quick answer fails
    page_short = dist / "page_short.html"
    page_short.write_text(
        '<!DOCTYPE html><html><head><title>Test</title><meta name="robots" content="max-snippet:20"></head>'
        '<body><h1>Header</h1><aside class="quick-answer">This is a longer quick answer that exceeds twenty characters.</aside></body></html>',
        encoding="utf-8"
    )
    res_short = verifier.check_snippet_eligibility_gate(dist)
    assert res_short["status"] == "FAIL"
    assert any("exceeds max-snippet:20" in i for i in res_short["issues"])
    page_short.unlink()

    # 3. data-nosnippet on main or body fails
    page_root = dist / "page_root.html"
    page_root.write_text(
        '<!DOCTYPE html><html><head><title>Test</title></head>'
        '<body data-nosnippet><h1>Header</h1><aside class="quick-answer">Direct answer text here.</aside></body></html>',
        encoding="utf-8"
    )
    res_root = verifier.check_snippet_eligibility_gate(dist)
    assert res_root["status"] == "FAIL"
    assert any("data-nosnippet" in i for i in res_root["issues"])
    page_root.unlink()

    # 4. data-nosnippet on unrelated element (e.g. footer) passes
    page_footer = dist / "page_footer.html"
    page_footer.write_text(
        '<!DOCTYPE html><html><head><title>Test</title><meta name="robots" content="max-snippet:-1"></head>'
        '<body><h1>Header</h1><aside class="quick-answer">Direct answer text here.</aside>'
        '<footer data-nosnippet>Ad or legal disclaimer here</footer></body></html>',
        encoding="utf-8"
    )
    res_footer = verifier.check_snippet_eligibility_gate(dist)
    assert res_footer["status"] == "PASS"
    assert res_footer["violations_count"] == 0


def test_snippet_eligibility_headers_differentiation(tmp_path):
    """Verifies _headers evaluation distinguishes search bots from training bots and non-public routes."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!DOCTYPE html><html><head><title>Clean</title></head><body><h1>Title</h1></body></html>", encoding="utf-8")

    verifier = MasterSEOVerifier(dist_dir=dist)

    # 1. Restricting training bots (GPTBot, Google-Extended) on public route must PASS
    (dist / "_headers").write_text(
        "/*\n"
        "  X-Robots-Tag: gptbot: noindex, nosnippet\n"
        "  X-Robots-Tag: google-extended: noindex\n",
        encoding="utf-8"
    )
    res1 = verifier.check_snippet_eligibility_gate(dist)
    assert res1["status"] == "PASS", f"Expected PASS for training bot headers, got: {res1['issues']}"

    # 2. Restricting search crawler (googlebot) on public route must FAIL
    (dist / "_headers").write_text(
        "/*\n"
        "  X-Robots-Tag: googlebot: nosnippet\n",
        encoding="utf-8"
    )
    res2 = verifier.check_snippet_eligibility_gate(dist)
    assert res2["status"] == "FAIL"
    assert any("googlebot" in i.lower() and "nosnippet" in i.lower() for i in res2["issues"])

    # 3. Global nosnippet on public route must FAIL
    (dist / "_headers").write_text(
        "/tools/*\n"
        "  X-Robots-Tag: nosnippet\n",
        encoding="utf-8"
    )
    res3 = verifier.check_snippet_eligibility_gate(dist)
    assert res3["status"] == "FAIL"
    assert any("nosnippet" in i for i in res3["issues"])

    # 4. Global noindex, nosnippet on non-public routes (/signal, /staging, /test, /tests, /syndication) must PASS
    (dist / "_headers").write_text(
        "/signal/*\n"
        "  X-Robots-Tag: noindex, nosnippet\n"
        "/staging/*\n"
        "  X-Robots-Tag: noindex, nosnippet\n"
        "/test/*\n"
        "  X-Robots-Tag: noindex, nosnippet\n"
        "/tests/*\n"
        "  X-Robots-Tag: noindex, nosnippet\n"
        "/syndication/*\n"
        "  X-Robots-Tag: noindex, nosnippet\n",
        encoding="utf-8"
    )
    res4 = verifier.check_snippet_eligibility_gate(dist)
    assert res4["status"] == "PASS", f"Expected PASS for non-public routes, got: {res4['issues']}"


def test_snippet_eligibility_robots_txt_crawler_policies(tmp_path):
    """Verifies robots.txt crawler policies evaluate AI search bots and allow training bot disallow."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!DOCTYPE html><html><head><title>Clean</title></head><body><h1>Title</h1></body></html>", encoding="utf-8")
    verifier = MasterSEOVerifier(dist_dir=dist)

    # 1. Permissive robots.txt with GPTBot disallowed must PASS
    robots_clean = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /signal/\n\n"
        "User-agent: GPTBot\n"
        "Disallow: /\n\n"
        "User-agent: CCBot\n"
        "Disallow: /\n"
    )
    (dist / "robots.txt").write_text(robots_clean, encoding="utf-8")
    res_clean = verifier.check_snippet_eligibility_gate(dist)
    assert res_clean["status"] == "PASS", f"Expected PASS, got: {res_clean['issues']}"

    # 2. Disallowing PerplexityBot on / must FAIL
    robots_block_perp = (
        "User-agent: *\n"
        "Allow: /\n\n"
        "User-agent: PerplexityBot\n"
        "Disallow: /\n"
    )
    (dist / "robots.txt").write_text(robots_block_perp, encoding="utf-8")
    res_perp = verifier.check_snippet_eligibility_gate(dist)
    assert res_perp["status"] == "FAIL"
    assert any("perplexitybot" in i.lower() for i in res_perp["issues"])

    # 3. Disallowing ClaudeBot on /tools/ must FAIL
    robots_block_claude = (
        "User-agent: *\n"
        "Allow: /\n\n"
        "User-agent: ClaudeBot\n"
        "Allow: /\n"
        "Disallow: /tools/\n"
    )
    (dist / "robots.txt").write_text(robots_block_claude, encoding="utf-8")
    res_claude = verifier.check_snippet_eligibility_gate(dist)
    assert res_claude["status"] == "FAIL"
    assert any("claudebot" in i.lower() for i in res_claude["issues"])

    # 4. Wildcard Disallow: / without allow override must FAIL for search bots
    robots_block_all = (
        "User-agent: *\n"
        "Disallow: /\n"
    )
    (dist / "robots.txt").write_text(robots_block_all, encoding="utf-8")
    res_all = verifier.check_snippet_eligibility_gate(dist)
    assert res_all["status"] == "FAIL"
    assert res_all["violations_count"] > 0


def test_gate_aliases_and_checklist_integration(tmp_path):
    """Verifies check_ai_crawl_access_and_snippet_eligibility_gate is accessible via all aliases."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(
        "<!DOCTYPE html><html lang=\"en\"><head><title>Clean Title Page</title>"
        "<meta name=\"robots\" content=\"max-snippet:-1\">"
        "<link rel=\"canonical\" href=\"https://example.com/\">"
        "</head><body><h1>Main Title</h1>"
        "<aside class=\"quick-answer\">"
        "Word one two three four five six seven eight nine ten "
        "eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty "
        "twentyone twentytwo twentythree twentyfour twentyfive twentysix twentyseven twentyeight twentynine thirty "
        "thirtyone thirtytwo thirtythree thirtyfour thirtyfive thirtysix thirtyseven thirtyeight thirtynine forty "
        "fortyone fortytwo fortythree fortyfour fortyfive."
        "</aside></body></html>",
        encoding="utf-8"
    )

    verifier = MasterSEOVerifier(dist_dir=dist)

    res1 = verifier.check_snippet_eligibility_gate(dist)
    res2 = verifier.check_ai_crawl_access_and_snippet_eligibility_gate(dist)
    res3 = verifier.check_ai_crawl_access_gate(dist)

    assert res1["status"] == res2["status"] == res3["status"] == "PASS"

    # Module-level aliases
    res_mod1 = check_snippet_eligibility_gate(dist)
    res_mod2 = check_ai_crawl_access_and_snippet_eligibility_gate(dist)
    res_mod3 = check_ai_crawl_access_gate(dist)
    assert res_mod1["status"] == res_mod2["status"] == res_mod3["status"] == "PASS"


def test_get_ai_factor_spec_queries():
    """Verifies get_ai_factor_spec queries by index, code, and name."""
    # Factor 1 by 1-indexed int
    f1 = get_ai_factor_spec(1)
    assert f1 is not None
    assert f1["code"] == "ai_crawl_access_and_snippet_eligibility"
    assert f1["weight"] == 2.20

    # Factor 1 by code
    f1_code = get_ai_factor_spec("ai_crawl_access_and_snippet_eligibility")
    assert f1_code == f1

    # Factor 1 by name (case-insensitive with whitespace)
    f1_name = get_ai_factor_spec("  AI Crawl Access & Snippet Eligibility  ")
    assert f1_name == f1

    # Factor 14 (last factor)
    f14 = get_ai_factor_spec(14)
    assert f14 is not None
    assert f14["code"] == "llms_txt"

    # Out of bounds and unknown factors
    assert get_ai_factor_spec(0) is None
    assert get_ai_factor_spec(15) is None
    assert get_ai_factor_spec(-1) is None
    assert get_ai_factor_spec("non_existent_factor") is None
    assert get_ai_factor_spec(None) is None


def test_crawler_helpers_taxonomy_checks():
    """Verifies is_ai_search_crawler, is_ai_training_crawler, and is_ai_crawler."""
    # Search crawlers
    for bot in AI_SEARCH_BOTS:
        assert is_ai_search_crawler(bot) is True
        assert is_ai_training_crawler(bot) is False
        assert is_ai_crawler(bot) is True
        # Case insensitivity
        assert is_ai_search_crawler(bot.upper()) is True

    # User-triggered bots
    for bot in AI_USER_TRIGGERED_BOTS:
        assert is_ai_search_crawler(bot) is True
        assert is_ai_training_crawler(bot) is False
        assert is_ai_crawler(bot) is True

    # Claude-web alias
    assert is_ai_search_crawler("claude-web") is True
    assert is_ai_training_crawler("claude-web") is False
    assert is_ai_crawler("claude-web") is True

    # Training bots
    for bot in AI_TRAINING_BOTS:
        assert is_ai_training_crawler(bot) is True
        assert is_ai_search_crawler(bot) is False
        assert is_ai_crawler(bot) is True
        assert is_ai_training_crawler(bot.upper()) is True

    # Unknown bots and invalid inputs
    assert is_ai_search_crawler("random_bot") is False
    assert is_ai_training_crawler("random_bot") is False
    assert is_ai_crawler("random_bot") is False
    assert is_ai_crawler("") is False
    assert is_ai_crawler(None) is False


def test_assert_snippet_length_contract_boundaries():
    """Verifies assert_snippet_length_contract boundary conditions."""
    quick_ans = "This is a concise direct answer with forty words of statutory clarity."

    # Permissive bounds
    assert assert_snippet_length_contract(quick_ans, max_snippet=500) is True
    assert assert_snippet_length_contract(quick_ans, max_snippet=-1) is True
    assert assert_snippet_length_contract(quick_ans, max_snippet=None) is True

    # Exactly matching length
    assert assert_snippet_length_contract(quick_ans, max_snippet=len(quick_ans)) is True

    # max_snippet: 0 fails
    with pytest.raises(ValueError, match="Snippet eligibility revoked: max-snippet is 0"):
        assert_snippet_length_contract(quick_ans, max_snippet=0)

    # quick_answer exceeds max_snippet
    with pytest.raises(ValueError, match="exceeds max-snippet"):
        assert_snippet_length_contract(quick_ans, max_snippet=20)

    # Invalid input types
    with pytest.raises(ValueError, match="quick_answer must be a string"):
        assert_snippet_length_contract(12345, max_snippet=100)

    # Forbidden dash check (anti-slop)
    with pytest.raises(ValueError, match="Forbidden em-dash"):
        assert_snippet_length_contract("This text has " + chr(0x2014) + " an em dash.", max_snippet=100)
    with pytest.raises(ValueError, match="Forbidden en-dash"):
        assert_snippet_length_contract("This text has " + chr(0x2013) + " an en dash.", max_snippet=100)


def test_assert_ai_crawl_access_and_snippet_eligibility_html_boundaries():
    """Verifies assert_ai_crawl_access_and_snippet_eligibility boundary conditions."""
    clean_html = (
        '<!DOCTYPE html><html lang="en"><head><title>Clean Calculation</title>'
        '<meta name="robots" content="max-snippet:-1">'
        '</head><body><aside class="quick-answer">Direct statutory answer text.</aside></body></html>'
    )
    assert assert_ai_crawl_access_and_snippet_eligibility(clean_html) is True
    assert assert_ai_crawl_access(clean_html) is True
    assert assert_snippet_eligibility(clean_html) is True

    # 1. nosnippet in robots meta
    html_nosnippet = clean_html.replace('max-snippet:-1', 'nosnippet')
    with pytest.raises(ValueError, match="'nosnippet' directive"):
        assert_ai_crawl_access_and_snippet_eligibility(html_nosnippet)

    # 2. nosnippet for googlebot
    html_gbot_nosnippet = clean_html.replace(
        '<meta name="robots" content="max-snippet:-1">',
        '<meta name="googlebot" content="nosnippet">'
    )
    with pytest.raises(ValueError, match="'nosnippet' directive"):
        assert_ai_crawl_access_and_snippet_eligibility(html_gbot_nosnippet)

    # 3. noindex for perplexitybot
    html_perp_noindex = clean_html.replace(
        '<meta name="robots" content="max-snippet:-1">',
        '<meta name="perplexitybot" content="noindex">'
    )
    with pytest.raises(ValueError, match="'noindex' or 'none' directive"):
        assert_ai_crawl_access_and_snippet_eligibility(html_perp_noindex)

    # 4. none directive
    html_none = clean_html.replace('max-snippet:-1', 'none')
    with pytest.raises(ValueError, match="'noindex' or 'none' directive"):
        assert_ai_crawl_access_and_snippet_eligibility(html_none)

    # 5. http-equiv X-Robots-Tag
    html_http_equiv = clean_html.replace(
        '<meta name="robots" content="max-snippet:-1">',
        '<meta http-equiv="X-Robots-Tag" content="nosnippet">'
    )
    with pytest.raises(ValueError, match="'nosnippet' directive"):
        assert_ai_crawl_access_and_snippet_eligibility(html_http_equiv)

    # 6. max-snippet:0
    html_max0 = clean_html.replace('max-snippet:-1', 'max-snippet:0')
    with pytest.raises(ValueError, match="'max-snippet:0' directive"):
        assert_ai_crawl_access_and_snippet_eligibility(html_max0)

    # 7. max-snippet:10 with 30 char answer
    html_max10 = clean_html.replace('max-snippet:-1', 'max-snippet:10')
    with pytest.raises(ValueError, match="exceeds max-snippet:10 limit"):
        assert_ai_crawl_access_and_snippet_eligibility(html_max10)

    # 8. Training bots restricted must PASS
    html_training_blocked = (
        '<!DOCTYPE html><html><head><title>Clean</title>'
        '<meta name="gptbot" content="noindex, nosnippet">'
        '<meta name="google-extended" content="noindex">'
        '<meta name="ccbot" content="noindex, nosnippet">'
        '<meta name="robots" content="max-snippet:-1">'
        '</head><body><aside class="quick-answer">Answer</aside></body></html>'
    )
    assert assert_ai_crawl_access_and_snippet_eligibility(html_training_blocked) is True

    # 9. data-nosnippet on body
    html_body_nosnip = clean_html.replace('<body>', '<body data-nosnippet>')
    with pytest.raises(ValueError, match="root container contains 'data-nosnippet'"):
        assert_ai_crawl_access_and_snippet_eligibility(html_body_nosnip)

    # 10. data-nosnippet on main
    html_main_nosnip = (
        '<!DOCTYPE html><html><head><title>Clean</title></head>'
        '<body><main data-nosnippet><aside class="quick-answer">Answer</aside></main></body></html>'
    )
    with pytest.raises(ValueError, match="root container contains 'data-nosnippet'"):
        assert_ai_crawl_access_and_snippet_eligibility(html_main_nosnip)

    # 11. data-nosnippet on aside.quick-answer
    html_qa_nosnip = clean_html.replace('class="quick-answer"', 'class="quick-answer" data-nosnippet')
    with pytest.raises(ValueError, match="quick-answer container contains 'data-nosnippet'"):
        assert_ai_crawl_access_and_snippet_eligibility(html_qa_nosnip)

    # 12. data-nosnippet on aside.quick_answer (underscore class)
    html_qa_und = clean_html.replace('class="quick-answer"', 'class="quick_answer" data-nosnippet')
    with pytest.raises(ValueError, match="quick-answer container contains 'data-nosnippet'"):
        assert_ai_crawl_access_and_snippet_eligibility(html_qa_und)

    # 13. data-nosnippet on ancestor wrapper
    html_anc_nosnip = (
        '<!DOCTYPE html><html><head><title>Clean</title></head>'
        '<body><div class="wrapper" data-nosnippet><aside class="quick-answer">Answer</aside></div></body></html>'
    )
    with pytest.raises(ValueError, match="quick-answer container contains 'data-nosnippet'"):
        assert_ai_crawl_access_and_snippet_eligibility(html_anc_nosnip)

    # 14. data-nosnippet on child inside quick-answer
    html_child_nosnip = (
        '<!DOCTYPE html><html><head><title>Clean</title></head>'
        '<body><aside class="quick-answer"><p data-nosnippet>Answer text</p></aside></body></html>'
    )
    with pytest.raises(ValueError, match="quick-answer container contains 'data-nosnippet'"):
        assert_ai_crawl_access_and_snippet_eligibility(html_child_nosnip)

    # 15. data-nosnippet on footer passes
    html_footer_nosnip = (
        '<!DOCTYPE html><html><head><title>Clean</title><meta name="robots" content="max-snippet:-1"></head>'
        '<body><aside class="quick-answer">Answer text</aside><footer data-nosnippet>Disclaimer</footer></body></html>'
    )
    assert assert_ai_crawl_access_and_snippet_eligibility(html_footer_nosnip) is True

    # 16. Forbidden dash check in HTML
    html_dash = clean_html.replace('Direct statutory', 'Direct ' + chr(0x2014) + ' statutory')
    with pytest.raises(ValueError, match="Forbidden em-dash"):
        assert_ai_crawl_access_and_snippet_eligibility(html_dash)


def test_assert_robots_txt_crawler_policy_boundaries():
    """Verifies assert_robots_txt_crawler_policy boundary conditions."""
    robots_clean = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /signal/\n\n"
        "User-agent: GPTBot\n"
        "Disallow: /\n\n"
        "User-agent: CCBot\n"
        "Disallow: /\n\n"
        "User-agent: Google-Extended\n"
        "Disallow: /\n"
    )
    assert assert_robots_txt_crawler_policy(robots_clean) is True

    # Disallowing PerplexityBot on / fails
    robots_block_perp = (
        "User-agent: *\n"
        "Allow: /\n\n"
        "User-agent: PerplexityBot\n"
        "Disallow: /\n"
    )
    with pytest.raises(ValueError, match="bot 'perplexitybot' is blocked on '/'"):
        assert_robots_txt_crawler_policy(robots_block_perp)

    # Disallowing ClaudeBot on /tools/ fails
    robots_block_claude = (
        "User-agent: *\n"
        "Allow: /\n\n"
        "User-agent: ClaudeBot\n"
        "Disallow: /tools/\n"
    )
    with pytest.raises(ValueError, match="bot 'claudebot' is blocked on '/tools/'"):
        assert_robots_txt_crawler_policy(robots_block_claude)

    # Disallowing claude-web alias on / fails
    robots_block_cweb = (
        "User-agent: *\n"
        "Allow: /\n\n"
        "User-agent: claude-web\n"
        "Disallow: /\n"
    )
    with pytest.raises(ValueError, match="bot 'claudebot' is blocked on '/'"):
        assert_robots_txt_crawler_policy(robots_block_cweb)

    # Disallowing OAI-SearchBot on / fails
    robots_block_oai = (
        "User-agent: *\n"
        "Allow: /\n\n"
        "User-agent: OAI-SearchBot\n"
        "Disallow: /\n"
    )
    with pytest.raises(ValueError, match="bot 'oai-searchbot' is blocked on '/'"):
        assert_robots_txt_crawler_policy(robots_block_oai)

    # Disallowing ChatGPT-User on / fails
    robots_block_chatgpt = (
        "User-agent: *\n"
        "Allow: /\n\n"
        "User-agent: ChatGPT-User\n"
        "Disallow: /\n"
    )
    with pytest.raises(ValueError, match="bot 'chatgpt-user' is blocked on '/'"):
        assert_robots_txt_crawler_policy(robots_block_chatgpt)

    # Disallowing * on / without search bot allow override fails
    robots_block_star = (
        "User-agent: *\n"
        "Disallow: /\n"
    )
    with pytest.raises(ValueError, match="is blocked on '/'"):
        assert_robots_txt_crawler_policy(robots_block_star)

    # Non-string input raises ValueError
    with pytest.raises(ValueError, match="robots.txt content must be a string"):
        assert_robots_txt_crawler_policy(None)


def test_assert_headers_snippet_policy_boundaries():
    """Verifies assert_headers_snippet_policy boundary conditions."""
    headers_clean = (
        "/*\n"
        "  X-Robots-Tag: gptbot: noindex, nosnippet\n"
        "  X-Robots-Tag: google-extended: noindex\n"
        "  X-Robots-Tag: ccbot: noindex\n"
        "/signal/*\n"
        "  X-Robots-Tag: noindex, nosnippet\n"
        "/staging/*\n"
        "  X-Robots-Tag: noindex, nosnippet\n"
    )
    assert assert_headers_snippet_policy(headers_clean) is True

    # nosnippet on public route fails
    h_nosnip = "/*\n  X-Robots-Tag: nosnippet\n"
    with pytest.raises(ValueError, match="applies 'nosnippet' to public route"):
        assert_headers_snippet_policy(h_nosnip)

    # max-snippet:0 on public route fails
    h_max0 = "/*\n  X-Robots-Tag: max-snippet:0\n"
    with pytest.raises(ValueError, match="applies 'max-snippet:0' to public route"):
        assert_headers_snippet_policy(h_max0)

    # none on public route fails
    h_none = "/*\n  X-Robots-Tag: none\n"
    with pytest.raises(ValueError, match="applies 'noindex' to public route"):
        assert_headers_snippet_policy(h_none)

    # googlebot: nosnippet on public route fails
    h_gbot_nosnip = "/*\n  X-Robots-Tag: googlebot: nosnippet\n"
    with pytest.raises(ValueError, match="applies 'nosnippet' to public route '/\\*' for bot 'googlebot'"):
        assert_headers_snippet_policy(h_gbot_nosnip)

    # perplexitybot: max-snippet:0 on public route fails
    h_perp_max0 = "/tools/*\n  X-Robots-Tag: perplexitybot: max-snippet:0\n"
    with pytest.raises(ValueError, match="applies 'max-snippet:0' to public route '/tools/\\*' for bot 'perplexitybot'"):
        assert_headers_snippet_policy(h_perp_max0)

    # claudebot: noindex on public route fails
    h_claude_noindex = "/tools/*\n  X-Robots-Tag: claudebot: noindex\n"
    with pytest.raises(ValueError, match="applies 'noindex' to public route '/tools/\\*' for bot 'claudebot'"):
        assert_headers_snippet_policy(h_claude_noindex)

    # oai-searchbot: nosnippet on public route fails
    h_oai_nosnip = "/*\n  X-Robots-Tag: oai-searchbot: nosnippet\n"
    with pytest.raises(ValueError, match="applies 'nosnippet' to public route '/\\*' for bot 'oai-searchbot'"):
        assert_headers_snippet_policy(h_oai_nosnip)

    # Non-string input raises ValueError
    with pytest.raises(ValueError, match="_headers content must be a string"):
        assert_headers_snippet_policy(None)


def test_verify_html_ai_crawl_access_and_snippet_eligibility_helper():
    """Verifies verify_html_ai_crawl_access_and_snippet_eligibility function."""
    clean_html = (
        '<!DOCTYPE html><html><head><title>Clean Page</title>'
        '<meta name="robots" content="max-snippet:-1">'
        '</head><body><aside class="quick-answer">Direct answer text.</aside></body></html>'
    )
    res_pass = verify_html_ai_crawl_access_and_snippet_eligibility(clean_html)
    assert res_pass["status"] == "PASS"
    assert res_pass["violations_count"] == 0
    assert not res_pass["issues"]

    fail_html = clean_html.replace('max-snippet:-1', 'nosnippet, noindex')
    res_fail = verify_html_ai_crawl_access_and_snippet_eligibility(fail_html)
    assert res_fail["status"] == "FAIL"
    assert res_fail["violations_count"] >= 2
    assert any("nosnippet" in i for i in res_fail["issues"])
    assert any("noindex" in i for i in res_fail["issues"])


def test_verify_ai_crawl_access_and_snippet_eligibility_method_and_function(tmp_path):
    """Verifies verify_ai_crawl_access_and_snippet_eligibility method and module export."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(
        '<!DOCTYPE html><html><head><title>Test</title><meta name="robots" content="max-snippet:-1"></head>'
        '<body><aside class="quick-answer">Answer</aside></body></html>',
        encoding="utf-8"
    )
    verifier = MasterSEOVerifier(dist_dir=dist)
    res1 = verifier.verify_ai_crawl_access_and_snippet_eligibility(dist)
    assert res1["status"] == "PASS"
    assert res1["gate"] == "check_ai_crawl_access_and_snippet_eligibility_gate"

    res2 = verify_ai_crawl_access_and_snippet_eligibility(dist)
    assert res2["status"] == "PASS"


# =============================================================================
# Factor 2: Query-Answer Match (+2.15) Tests
# =============================================================================


def test_zyppy_2026_ai_factors_spec_factor2():
    """Verifies Factor 2: Query-Answer Match is properly registered in ZYPPY_2026_AI_FACTORS_SPEC."""
    assert len(ZYPPY_2026_AI_FACTORS_SPEC) >= 2
    f2 = ZYPPY_2026_AI_FACTORS_SPEC[1]
    assert f2["code"] == "query_answer_match"
    assert f2["name"] == "Query-Answer Match"
    assert f2["factor"] == "Query-Answer Match"
    assert f2["weight"] == 2.15
    assert f2["positive_weight"] == 2.15
    assert f2["negative_weight"] == -2.15
    assert "initial viewport" in f2["description"].lower()

    # Query by 1-indexed int
    f2_idx = get_ai_factor_spec(2)
    assert f2_idx == f2

    # Query by code (with underscore and hyphen)
    assert get_ai_factor_spec("query_answer_match") == f2
    assert get_ai_factor_spec("query-answer-match") == f2

    # Query by name (case-insensitive with whitespace)
    assert get_ai_factor_spec("  Query-Answer Match  ") == f2


def test_single_pass_parser_viewport_ordering():
    """Verifies SinglePassSEODocumentParser detects viewport positioning relative to h1 and h2."""
    # 1. Compliant layout: H1 -> div.quick-answer -> H2
    html_div = (
        '<!DOCTYPE html><html><head><title>Title</title></head><body>'
        '<h1>Introductory Top Header</h1>'
        '<div class="quick-answer" data-query="tax deduction calculator">'
        'Direct passage text answering the target query.'
        '</div>'
        '<h2>Secondary Section Heading</h2>'
        '</body></html>'
    )
    p1 = SinglePassSEODocumentParser()
    p1.feed(html_div)
    assert p1.has_quick_answer is True
    assert p1.quick_answer_count == 1
    assert p1.quick_answer_seen_after_h1 is True
    assert p1.quick_answer_seen_before_h2 is True
    assert p1.quick_answer_in_viewport is True
    assert p1.target_query == "tax deduction calculator"
    assert p1.quick_answer_text == "Direct passage text answering the target query."

    # 2. Compliant layout: H1 -> aside.quick-answer -> H2
    html_aside = (
        '<!DOCTYPE html><html><head><title>Title</title>'
        '<meta name="target-query" content="federal loan consolidation">'
        '</head><body>'
        '<h1>Introductory Top Header</h1>'
        '<aside class="quick-answer">'
        'Direct passage text answering the target query.'
        '</aside>'
        '<h2>Secondary Section Heading</h2>'
        '</body></html>'
    )
    p2 = SinglePassSEODocumentParser()
    p2.feed(html_aside)
    assert p2.has_quick_answer is True
    assert p2.quick_answer_in_viewport is True
    assert p2.target_query == "federal loan consolidation"

    # 3. Misplaced layout: quick-answer before H1
    html_before_h1 = (
        '<!DOCTYPE html><html><head><title>Title</title></head><body>'
        '<div class="quick-answer">Direct answer text.</div>'
        '<h1>Introductory Top Header</h1>'
        '<h2>Secondary Section Heading</h2>'
        '</body></html>'
    )
    p3 = SinglePassSEODocumentParser()
    p3.feed(html_before_h1)
    assert p3.has_quick_answer is True
    assert p3.quick_answer_seen_after_h1 is False
    assert p3.quick_answer_in_viewport is False

    # 4. Sunk layout: quick-answer after H2 (below the fold)
    html_after_h2 = (
        '<!DOCTYPE html><html><head><title>Title</title></head><body>'
        '<h1>Introductory Top Header</h1>'
        '<h2>Secondary Section Heading</h2>'
        '<div class="quick-answer">Direct answer text.</div>'
        '</body></html>'
    )
    p4 = SinglePassSEODocumentParser()
    p4.feed(html_after_h2)
    assert p4.has_quick_answer is True
    assert p4.quick_answer_seen_before_h2 is False
    assert p4.quick_answer_in_viewport is False

    # 5. Missing quick-answer container
    html_missing = (
        '<!DOCTYPE html><html><head><title>Title</title></head><body>'
        '<h1>Introductory Top Header</h1>'
        '<p>Sprawling narrative content without dedicated quick-answer container.</p>'
        '</body></html>'
    )
    p5 = SinglePassSEODocumentParser()
    p5.feed(html_missing)
    assert p5.has_quick_answer is False
    assert p5.quick_answer_count == 0
    assert p5.quick_answer_in_viewport is False

    # 6. Multiple quick-answer containers
    html_multiple = (
        '<!DOCTYPE html><html><head><title>Title</title></head><body>'
        '<h1>Introductory Top Header</h1>'
        '<div class="quick-answer">First answer passage text.</div>'
        '<h2>Secondary Section</h2>'
        '<div class="quick-answer">Second duplicate answer passage text.</div>'
        '</body></html>'
    )
    p6 = SinglePassSEODocumentParser()
    p6.feed(html_multiple)
    assert p6.quick_answer_count == 2


def test_assert_quick_answer_passage_relevance_boundaries():
    """Verifies assert_quick_answer_passage_relevance boundary conditions."""
    compliant_passage = (
        "The direct consolidation loan calculator allows borrowers to estimate repayment under federal income driven repayment plans. "
        "Consolidating federal student loans creates a weighted average interest rate while extending payoff timelines up to thirty years. "
        "The model calculates monthly obligations and total interest under current statutory regulations."
    )

    # 1. Valid compliant passage passes
    assert assert_quick_answer_passage_relevance(compliant_passage) is True

    # 2. Too short (< 40 words) fails
    short_words = " ".join(compliant_passage.split()[:35]) + "."
    with pytest.raises(ValueError, match="Quick-answer passage too short"):
        assert_quick_answer_passage_relevance(short_words)

    # 3. Too long (> 60 words) fails
    long_words = compliant_passage + " Extra sentence expanding the word count well beyond sixty words to test the upper boundary limit strictly."
    with pytest.raises(ValueError, match="Quick-answer passage bloated"):
        assert_quick_answer_passage_relevance(long_words)

    # 4. Non-string or empty string fails
    with pytest.raises(ValueError, match="must be a non-empty string"):
        assert_quick_answer_passage_relevance("")
    with pytest.raises(ValueError, match="must be a non-empty string"):
        assert_quick_answer_passage_relevance(12345)

    # 5. Missing terminal punctuation fails
    no_period = compliant_passage.rstrip(".")
    with pytest.raises(ValueError, match="missing terminal sentence punctuation"):
        assert_quick_answer_passage_relevance(no_period)

    # 6. Forbidden AI jargon fails
    jargon_passage = compliant_passage.replace("regulations.", "regulations delving into game-changer features.")
    with pytest.raises(ValueError, match="forbidden AI jargon"):
        assert_quick_answer_passage_relevance(jargon_passage)

    # 7. Evasive summary fails
    evasive_passage = (
        "It depends on your individual borrower situation whether federal student loan consolidation makes sense. "
        "Consult a professional financial advisor or read more below to see our guide below for complete details. "
        "Multiple options exist depending on specific income driven plans and repayment timelines for federal loans."
    )
    with pytest.raises(ValueError, match="evasive summary"):
        assert_quick_answer_passage_relevance(evasive_passage)

    # 8. Forbidden dashes fail (anti-slop)
    em_dash_passage = compliant_passage.replace("borrowers", "borrowers " + chr(0x2014))
    with pytest.raises(ValueError, match="Forbidden em-dash"):
        assert_quick_answer_passage_relevance(em_dash_passage)

    en_dash_passage = compliant_passage.replace("borrowers", "borrowers " + chr(0x2013))
    with pytest.raises(ValueError, match="Forbidden en-dash"):
        assert_quick_answer_passage_relevance(en_dash_passage)


def test_semantic_query_answer_match_mechanics():
    """Verifies semantic query-answer alignment and keyword stuffing detection."""
    passage = (
        "The Section 179 tax deduction calculator enables businesses to deduct the full purchase price of qualifying equipment up to 1220000 dollars. "
        "First year bonus depreciation applies to eligible commercial property placed in service during the tax year. "
        "This model calculates tax liability reductions under internal revenue statutory guidelines."
    )

    # 1. High-overlap relevant query passes
    assert assert_quick_answer_passage_relevance(passage, target_query="section 179 deduction calculator") is True

    # 2. Semantic mismatch (< 50% query tokens addressed) fails
    with pytest.raises(ValueError, match="semantic mismatch"):
        assert_quick_answer_passage_relevance(passage, target_query="autonomous electric vehicle fleet tax credit")

    # 3. Keyword stuffing fails
    stuffed_passage = (
        "The Section 179 tax deduction calculator calculates Section 179 deduction with our Section 179 calculator "
        "for your Section 179 deduction tax calculator Section 179 equipment Section 179 savings. "
        "Bonus depreciation applies to qualifying Section 179 commercial equipment placed in service during the current tax year."
    )
    with pytest.raises(ValueError, match="keyword stuffing"):
        assert_quick_answer_passage_relevance(stuffed_passage, target_query="section 179 calculator")


def test_assert_viewport_ordering_boundaries():
    """Verifies assert_viewport_ordering boundary conditions."""
    clean_html = (
        '<!DOCTYPE html><html><head><title>Test Title</title></head><body>'
        '<h1>Page Introductory Heading</h1>'
        '<div class="quick-answer">Direct answer passage content.</div>'
        '<h2>Secondary Section</h2>'
        '</body></html>'
    )

    # 1. Compliant ordering passes
    assert assert_viewport_ordering(clean_html) is True

    # 2. Aside container also passes
    aside_html = clean_html.replace('div class="quick-answer"', 'aside class="quick-answer"')
    assert assert_viewport_ordering(aside_html) is True

    # 3. Missing container fails
    no_qa_html = clean_html.replace('<div class="quick-answer">Direct answer passage content.</div>', '')
    with pytest.raises(ValueError, match="missing quick-answer container"):
        assert_viewport_ordering(no_qa_html)

    # 4. Misplaced before H1 fails
    before_h1 = (
        '<!DOCTYPE html><html><head><title>Test</title></head><body>'
        '<div class="quick-answer">Direct answer.</div>'
        '<h1>Heading</h1>'
        '</body></html>'
    )
    with pytest.raises(ValueError, match="misplaced before introductory <h1> header"):
        assert_viewport_ordering(before_h1)

    # 5. Sunk below H2 fails
    after_h2 = (
        '<!DOCTYPE html><html><head><title>Test</title></head><body>'
        '<h1>Heading</h1>'
        '<h2>Secondary</h2>'
        '<div class="quick-answer">Direct answer.</div>'
        '</body></html>'
    )
    with pytest.raises(ValueError, match="sunk below secondary heading"):
        assert_viewport_ordering(after_h2)

    # 6. Multiple containers fail
    multiple_qa = (
        '<!DOCTYPE html><html><head><title>Test</title></head><body>'
        '<h1>Heading</h1>'
        '<div class="quick-answer">Answer 1.</div>'
        '<div class="quick-answer">Answer 2.</div>'
        '<h2>Secondary</h2>'
        '</body></html>'
    )
    with pytest.raises(ValueError, match="multiple quick-answer containers"):
        assert_viewport_ordering(multiple_qa)

    # 7. Forbidden dashes fail
    dash_html = clean_html.replace('Page Introductory', 'Page ' + chr(0x2014) + ' Introductory')
    with pytest.raises(ValueError, match="Forbidden em-dash"):
        assert_viewport_ordering(dash_html)


def test_assert_query_answer_match_html_boundaries():
    """Verifies assert_query_answer_match and aliases across HTML documents."""
    passage = (
        "The direct consolidation loan calculator allows borrowers to estimate repayment under federal income driven repayment plans. "
        "Consolidating federal student loans creates a weighted average interest rate while extending payoff timelines up to thirty years. "
        "The model calculates monthly obligations and total interest under current statutory regulations."
    )
    clean_html = (
        '<!DOCTYPE html><html><head><title>Loan Calculator</title>'
        '<meta name="target-query" content="direct consolidation loan calculator">'
        '</head><body>'
        '<h1>Direct Consolidation Loan Calculator</h1>'
        f'<div class="quick-answer">{passage}</div>'
        '<h2>Repayment Options Overview</h2>'
        '</body></html>'
    )

    # 1. Compliant HTML passes
    assert assert_query_answer_match(clean_html) is True
    # Aliases
    assert assert_quick_answer_match(clean_html) is True
    assert assert_query_answer_alignment(clean_html) is True

    # 2. Unpopulated empty container fails
    empty_qa = clean_html.replace(passage, '   ')
    with pytest.raises(ValueError, match="unpopulated|must be a non-empty string"):
        assert_query_answer_match(empty_qa)

    # 3. Buried below H2 fails
    buried_html = (
        '<!DOCTYPE html><html><head><title>Loan</title></head><body>'
        '<h1>Direct Consolidation Loan Calculator</h1>'
        '<h2>Repayment Options Overview</h2>'
        f'<div class="quick-answer">{passage}</div>'
        '</body></html>'
    )
    with pytest.raises(ValueError, match="sunk below secondary heading"):
        assert_query_answer_match(buried_html)

    # 4. Semantic mismatch against explicit target query fails
    with pytest.raises(ValueError, match="semantic mismatch"):
        assert_query_answer_match(clean_html, target_query="autonomous electric vehicle fleet tax credit")


def test_verify_html_query_answer_match_helper():
    """Verifies verify_html_query_answer_match function status and issue reporting."""
    passage = (
        "The Section 179 tax deduction calculator enables businesses to deduct the full purchase price of qualifying equipment up to 1220000 dollars. "
        "First year bonus depreciation applies to eligible commercial property placed in service during the tax year. "
        "This model calculates tax liability reductions under internal revenue statutory guidelines."
    )
    clean_html = (
        '<!DOCTYPE html><html><head><title>Section 179</title></head><body>'
        '<h1>Section 179 Deduction Calculator</h1>'
        f'<div class="quick-answer" data-query="section 179 deduction calculator">{passage}</div>'
        '<h2>Eligible Equipment Categories</h2>'
        '</body></html>'
    )

    res_pass = verify_html_query_answer_match(clean_html)
    assert res_pass["status"] == "PASS"
    assert res_pass["violations_count"] == 0
    assert not res_pass["issues"]
    assert res_pass["in_viewport"] is True
    assert res_pass["word_count"] >= 40

    # Fail case: missing container
    fail_html = '<html><body><h1>Heading</h1><p>No quick answer</p></body></html>'
    res_fail = verify_html_query_answer_match(fail_html)
    assert res_fail["status"] == "FAIL"
    assert any("Missing quick-answer container" in i for i in res_fail["issues"])


def test_check_query_answer_match_gate_synthetic_fixtures(tmp_path):
    """Verifies check_query_answer_match_gate across positive and negative audit fixtures."""
    passage = (
        "The Section 179 tax deduction calculator enables businesses to deduct the full purchase price of qualifying equipment up to 1220000 dollars. "
        "First year bonus depreciation applies to eligible commercial property placed in service during the tax year. "
        "This model calculates tax liability reductions under internal revenue statutory guidelines."
    )

    # 1. Positive directory fixture
    dist_pos = tmp_path / "dist_pos"
    dist_pos.mkdir()
    (dist_pos / "index.html").write_text(
        '<!DOCTYPE html><html lang="en"><head><title>Section 179 Calculator</title></head><body>'
        '<h1>Section 179 Deduction Calculator</h1>'
        f'<div class="quick-answer" data-query="section 179 deduction calculator">{passage}</div>'
        '<h2>Eligible Equipment</h2>'
        '</body></html>',
        encoding="utf-8"
    )

    verifier_pos = MasterSEOVerifier(dist_dir=dist_pos)
    res_pos = verifier_pos.check_query_answer_match_gate(dist_pos)
    assert res_pos["status"] == "PASS"
    assert res_pos["violations_count"] == 0

    # 2. Negative directory fixture
    dist_neg = tmp_path / "dist_neg"
    dist_neg.mkdir()
    # Missing quick-answer container
    (dist_neg / "missing.html").write_text(
        '<!DOCTYPE html><html><body><h1>Header</h1><p>Missing answer.</p></body></html>',
        encoding="utf-8"
    )
    # Sunk quick-answer container
    (dist_neg / "sunk.html").write_text(
        '<!DOCTYPE html><html><body><h1>Header</h1><h2>Secondary</h2>'
        f'<div class="quick-answer">{passage}</div></body></html>',
        encoding="utf-8"
    )

    verifier_neg = MasterSEOVerifier(dist_dir=dist_neg)
    res_neg = verifier_neg.check_query_answer_match_gate(dist_neg)
    assert res_neg["status"] == "FAIL"
    assert res_neg["violations_count"] >= 2
    assert any("Missing quick-answer container" in i for i in res_neg["issues"])
    assert any("sunk below secondary heading" in i for i in res_neg["issues"])


def test_gate_aliases_and_checklist_integration_factor2(tmp_path):
    """Verifies Factor 2 gate aliases and audit_seo_checklist integration."""
    passage = (
        "The direct consolidation loan calculator allows borrowers to estimate repayment under federal income driven repayment plans. "
        "Consolidating federal student loans creates a weighted average interest rate while extending payoff timelines up to thirty years. "
        "The model calculates monthly obligations and total interest under current statutory regulations."
    )
    dist = tmp_path / "dist_integration"
    dist.mkdir()
    (dist / "index.html").write_text(
        '<!DOCTYPE html><html lang="en"><head><title>Direct Consolidation Loan Calculator For Borrowers</title>'
        '<meta name="description" content="Calculate your monthly federal student loan payments and total interest savings using our direct consolidation loan calculator tool.">'
        '<meta name="robots" content="max-snippet:-1">'
        '<link rel="canonical" href="https://example.com/">'
        '</head><body>'
        '<h1>Direct Consolidation Loan Calculator</h1>'
        f'<div class="quick-answer">{passage}</div>'
        '<h2>Repayment Plans Breakdown</h2>'
        '</body></html>',
        encoding="utf-8"
    )

    verifier = MasterSEOVerifier(dist_dir=dist)

    res1 = verifier.check_query_answer_match_gate(dist)
    res2 = verifier.check_query_answer_gate(dist)
    res3 = verifier.verify_query_answer_match(dist)
    assert res1["status"] == res2["status"] == res3["status"] == "PASS"

    # Module-level alias functions
    m_res1 = check_query_answer_match_gate(dist)
    m_res2 = check_query_answer_gate(dist)
    m_res3 = verify_query_answer_match(dist)
    assert m_res1["status"] == m_res2["status"] == m_res3["status"] == "PASS"

    # Verify checklist gates inclusion
    audit_res = verifier.audit_seo_checklist(dist, enforce_relevance=False)
    assert "check_query_answer_match_gate" in audit_res["gates"]
    assert audit_res["gates"]["check_query_answer_match_gate"]["status"] == "PASS"


# =============================================================================
# Factor 3: Brand / Entity in LLM Memory (+2.08) Tests
# =============================================================================


def test_zyppy_2026_ai_factors_spec_factor3():
    """Verifies Factor 3: Brand / Entity in LLM Memory is properly registered in ZYPPY_2026_AI_FACTORS_SPEC."""
    assert len(ZYPPY_2026_AI_FACTORS_SPEC) >= 3
    f3 = ZYPPY_2026_AI_FACTORS_SPEC[2]
    assert f3["code"] == "brand_entity_in_llm_memory"
    assert f3["name"] == "Brand / Entity in LLM Memory"
    assert f3["factor"] == "Brand / Entity in LLM Memory"
    assert f3["weight"] == 2.08
    assert f3["positive_weight"] == 2.08
    assert f3["negative_weight"] == -2.08
    assert "parametric memory" in f3["description"].lower()

    # Query by 1-indexed int
    f3_idx = get_ai_factor_spec(3)
    assert f3_idx == f3

    # Query by code (with underscore and hyphen)
    assert get_ai_factor_spec("brand_entity_in_llm_memory") == f3
    assert get_ai_factor_spec("brand-entity-in-llm-memory") == f3

    # Query by name (flexible spacing and slash)
    assert get_ai_factor_spec("Brand / Entity in LLM Memory") == f3
    assert get_ai_factor_spec("Brand/Entity in LLM Memory") == f3
    assert get_ai_factor_spec("  Brand / Entity in LLM Memory  ") == f3

    # Check re-exports from seo_verifier and pseofactory root
    assert seo_verifier.ZYPPY_2026_AI_FACTORS_SPEC is ZYPPY_2026_AI_FACTORS_SPEC
    assert pseofactory.ZYPPY_2026_AI_FACTORS_SPEC is ZYPPY_2026_AI_FACTORS_SPEC


def test_assert_wikidata_uri_boundaries():
    """Verifies assert_wikidata_uri exact pattern validation and boundary conditions."""
    # 1. Valid Wikidata URIs
    valid_uris = [
        "https://www.wikidata.org/wiki/Q115862807",
        "https://wikidata.org/wiki/Q42",
        "https://wikidata.org/entity/Q1",
        "http://www.wikidata.org/wiki/Q999/",
    ]
    for u in valid_uris:
        assert assert_wikidata_uri(u) is True

    # 2. Invalid inputs
    invalid_cases = [
        "",
        "   ",
        "https://www.wikidata.org/wiki/",
        "https://www.wikidata.org/wiki/Q",
        "https://www.wikidata.org/wiki/Q0",
        "https://www.wikidata.org/wiki/QXYZ",
        "https://notwikidata.org/wiki/Q123",
        "https://fakewikidata.org/entity/Q42",
        "https://en.wikipedia.org/wiki/GainHelm",
        "wiki/Q115862807",
    ]
    for bad in invalid_cases:
        with pytest.raises(ValueError):
            assert_wikidata_uri(bad)

    # 3. Anti-slop in URI
    em_uri = "https://www.wikidata.org/wiki/Q115862807" + chr(0x2014)
    with pytest.raises(ValueError, match="Forbidden em-dash"):
        assert_wikidata_uri(em_uri)


def test_assert_authoritative_same_as_boundaries():
    """Verifies assert_authoritative_same_as validation, self-referential rejection, and domain bounds."""
    valid_profiles = [
        "https://www.wikidata.org/wiki/Q115862807",
        "https://en.wikipedia.org/wiki/GainHelm",
        "https://www.linkedin.com/company/gainhelm",
        "https://github.com/gainhelm",
        "https://crunchbase.com/organization/gainhelm",
        "https://x.com/gainhelm",
    ]

    # 1. Compliant list passes
    assert (
        assert_authoritative_same_as(
            valid_profiles,
            entity_url="https://gainhelm.com",
            entity_domain="gainhelm.com",
        )
        is True
    )

    # Single string normalized to list
    assert (
        assert_authoritative_same_as(
            "https://www.wikidata.org/wiki/Q115862807",
            entity_url="https://gainhelm.com",
        )
        is True
    )

    # 2. Empty list fails
    with pytest.raises(ValueError, match="sameAs array is empty"):
        assert_authoritative_same_as([], entity_url="https://gainhelm.com")

    # 3. Missing Wikidata link fails
    no_wd = [
        "https://en.wikipedia.org/wiki/GainHelm",
        "https://www.linkedin.com/company/gainhelm",
    ]
    with pytest.raises(ValueError, match="missing authoritative Wikidata entity reference"):
        assert_authoritative_same_as(no_wd, entity_url="https://gainhelm.com")

    # Without require_wikidata, non-Wikidata authoritative list passes
    assert (
        assert_authoritative_same_as(
            no_wd,
            entity_url="https://gainhelm.com",
            require_wikidata=False,
        )
        is True
    )

    # 4. Self-referential / circular links fail
    self_ref_url = valid_profiles + ["https://gainhelm.com/about"]
    with pytest.raises(ValueError, match="self-referential to entity URL"):
        assert_authoritative_same_as(self_ref_url, entity_url="https://gainhelm.com")

    self_ref_domain = valid_profiles + ["https://sub.gainhelm.com/team"]
    with pytest.raises(ValueError, match="self-referential to entity domain"):
        assert_authoritative_same_as(
            self_ref_domain,
            entity_url="https://gainhelm.io",
            entity_domain="gainhelm.com",
        )

    # 5. Placeholder / unverified domains fail
    with pytest.raises(ValueError, match="unverified or placeholder domain"):
        assert_authoritative_same_as(
            valid_profiles + ["http://localhost/company"],
            entity_url="https://gainhelm.com",
        )

    with pytest.raises(ValueError, match="unverified or placeholder domain"):
        assert_authoritative_same_as(
            valid_profiles + ["https://example.com/company"],
            entity_url="https://gainhelm.com",
        )

    # 6. Unauthoritative domain fails
    with pytest.raises(ValueError, match="unauthoritative domain"):
        assert_authoritative_same_as(
            valid_profiles + ["https://arbitrary-unverified-blog.xyz/gainhelm"],
            entity_url="https://gainhelm.com",
        )

    # 7. Anti-slop
    dash_profiles = valid_profiles + ["https://github.com/gainhelm" + chr(0x2014)]
    with pytest.raises(ValueError, match="Forbidden em-dash"):
        assert_authoritative_same_as(dash_profiles, entity_url="https://gainhelm.com")


def test_assert_brand_entity_taxonomy_boundaries():
    """Verifies assert_brand_entity_taxonomy allows canonical types and rejects collisions."""
    # 1. Allowed canonical types
    allowed = ["Organization", "Corporation", "Brand", "OnlineBusiness", "FinancialService"]
    for t in allowed:
        assert assert_brand_entity_taxonomy({"@type": t}) is True

    # Multi-type allowed
    assert assert_brand_entity_taxonomy({"@type": ["Organization", "Brand"]}) is True

    # 2. Missing @type
    with pytest.raises(ValueError, match="missing '@type' taxonomy"):
        assert_brand_entity_taxonomy({})

    # 3. Collision with general page topics
    topic_collisions = ["Article", "WebPage", "BlogPosting", "TechArticle", "NewsArticle"]
    for tc in topic_collisions:
        with pytest.raises(ValueError, match="Entity taxonomy collision"):
            assert_brand_entity_taxonomy({"@type": tc})

    # Collision when combined
    with pytest.raises(ValueError, match="Entity taxonomy collision"):
        assert_brand_entity_taxonomy({"@type": ["Organization", "Article"]})

    # 4. Collision with product
    with pytest.raises(ValueError, match="Entity taxonomy collision"):
        assert_brand_entity_taxonomy({"@type": "Product"})

    # 5. Superficial generic type Thing
    with pytest.raises(ValueError, match="Entity taxonomy collision"):
        assert_brand_entity_taxonomy({"@type": "Thing"})

    # 6. Unregistered ambiguous type
    with pytest.raises(ValueError, match="Ambiguous entity taxonomy"):
        assert_brand_entity_taxonomy({"@type": "CustomUnregisteredIdentity"})


def test_assert_canonical_entity_definition_boundaries():
    """Verifies assert_canonical_entity_definition structural bounds and failure modes."""
    valid_entity = {
        "@type": "Organization",
        "@id": "https://gainhelm.com/#organization",
        "name": "GainHelm",
        "url": "https://gainhelm.com",
        "sameAs": [
            "https://www.wikidata.org/wiki/Q115862807",
            "https://en.wikipedia.org/wiki/GainHelm",
            "https://www.linkedin.com/company/gainhelm",
        ],
    }

    # 1. Compliant entity passes
    assert (
        assert_canonical_entity_definition(
            valid_entity,
            brand_name="GainHelm",
            brand_domain="gainhelm.com",
        )
        is True
    )

    # 2. Disconnected schema fragments (missing or non-absolute @id)
    no_id = dict(valid_entity)
    del no_id["@id"]
    with pytest.raises(ValueError, match="disconnected schema fragment"):
        assert_canonical_entity_definition(no_id)

    relative_id = dict(valid_entity, **{"@id": "#organization"})
    with pytest.raises(ValueError, match="disconnected schema fragment"):
        assert_canonical_entity_definition(relative_id)

    # 3. Missing or empty name
    no_name = dict(valid_entity, name="   ")
    with pytest.raises(ValueError, match="missing non-empty 'name'"):
        assert_canonical_entity_definition(no_name)

    # 4. Brand name mismatch
    with pytest.raises(ValueError, match="does not align with expected brand name"):
        assert_canonical_entity_definition(valid_entity, brand_name="PrexvoCorp")

    # 5. Missing or invalid URL
    no_url = dict(valid_entity, url="not-a-url")
    with pytest.raises(ValueError, match="not an absolute HTTP or HTTPS URL"):
        assert_canonical_entity_definition(no_url)

    # 6. Brand domain mismatch
    with pytest.raises(ValueError, match="does not match expected brand domain"):
        assert_canonical_entity_definition(valid_entity, brand_domain="otherdomain.io")

    # 7. Missing sameAs
    no_sameas = dict(valid_entity)
    del no_sameas["sameAs"]
    with pytest.raises(ValueError, match="missing 'sameAs' array"):
        assert_canonical_entity_definition(no_sameas)

    # 8. Anti-slop in entity name
    dash_entity = dict(valid_entity, name="GainHelm" + chr(0x2014) + "Platform")
    with pytest.raises(ValueError, match="Forbidden em-dash"):
        assert_canonical_entity_definition(dash_entity)


def test_assert_brand_entity_in_llm_memory_html_boundaries():
    """Verifies assert_brand_entity_in_llm_memory across diverse HTML structured data layouts."""
    compliant_html = (
        '<!DOCTYPE html><html><head><title>Loan Engine</title>'
        '<script type="application/ld+json">'
        '{\n'
        '  "@context": "https://schema.org",\n'
        '  "@type": "Organization",\n'
        '  "@id": "https://gainhelm.com/#organization",\n'
        '  "name": "GainHelm",\n'
        '  "url": "https://gainhelm.com",\n'
        '  "sameAs": [\n'
        '    "https://www.wikidata.org/wiki/Q115862807",\n'
        '    "https://www.linkedin.com/company/gainhelm"\n'
        '  ]\n'
        '}'
        '</script></head><body><h1>Heading</h1></body></html>'
    )

    # 1. Compliant HTML passes
    assert (
        assert_brand_entity_in_llm_memory(
            compliant_html,
            brand_name="GainHelm",
            brand_domain="gainhelm.com",
        )
        is True
    )

    # Aliases
    assert assert_brand_entity_memory(compliant_html) is True
    assert assert_entity_memory_grounding(compliant_html) is True

    # 2. Multi-entity nesting via @graph
    graph_html = (
        '<!DOCTYPE html><html><head><title>Loan Engine</title>'
        '<script type="application/ld+json">'
        '{\n'
        '  "@context": "https://schema.org",\n'
        '  "@graph": [\n'
        '    {\n'
        '      "@type": "WebSite",\n'
        '      "@id": "https://gainhelm.com/#website",\n'
        '      "url": "https://gainhelm.com",\n'
        '      "name": "GainHelm Platform"\n'
        '    },\n'
        '    {\n'
        '      "@type": "Organization",\n'
        '      "@id": "https://gainhelm.com/#organization",\n'
        '      "name": "GainHelm",\n'
        '      "url": "https://gainhelm.com",\n'
        '      "sameAs": ["https://www.wikidata.org/wiki/Q115862807"]\n'
        '    }\n'
        '  ]\n'
        '}'
        '</script></head><body><h1>Heading</h1></body></html>'
    )
    assert assert_brand_entity_in_llm_memory(graph_html) is True

    # 3. Missing JSON-LD script block fails
    no_schema = '<!DOCTYPE html><html><head><title>Page</title></head><body><h1>Heading</h1></body></html>'
    with pytest.raises(ValueError, match=r"(?i)missing Schema\.org JSON-LD"):
        assert_brand_entity_in_llm_memory(no_schema)

    # 4. Disconnected schema fragment (missing @id) fails
    frag_html = compliant_html.replace('"@id": "https://gainhelm.com/#organization",\n', '')
    with pytest.raises(ValueError, match="disconnected schema fragment"):
        assert_brand_entity_in_llm_memory(frag_html)

    # 5. Taxonomy collision (Article claiming to be brand) fails
    topic_html = compliant_html.replace('"@type": "Organization"', '"@type": "Article"')
    with pytest.raises(ValueError, match="Entity taxonomy collision|No canonical brand"):
        assert_brand_entity_in_llm_memory(topic_html)

    # 6. Anti-slop in document
    dash_html = compliant_html.replace('Loan Engine', 'Loan ' + chr(0x2014) + ' Engine')
    with pytest.raises(ValueError, match="Forbidden em-dash"):
        assert_brand_entity_in_llm_memory(dash_html)


def test_single_pass_parser_brand_entities_extraction():
    """Verifies SinglePassSEODocumentParser extracts brand_entities and populates state."""
    html_doc = (
        '<!DOCTYPE html><html><head><title>Title</title>'
        '<script type="application/ld+json">'
        '{\n'
        '  "@context": "https://schema.org",\n'
        '  "@type": "Corporation",\n'
        '  "@id": "https://gainhelm.com/#corp",\n'
        '  "name": "GainHelm Inc",\n'
        '  "url": "https://gainhelm.com",\n'
        '  "sameAs": ["https://www.wikidata.org/wiki/Q115862807"]\n'
        '}'
        '</script></head><body><h1>Header</h1></body></html>'
    )
    parser = SinglePassSEODocumentParser("gainhelm.com")
    parser.feed(html_doc)
    assert parser.has_canonical_brand_entity is True
    assert len(parser.brand_entities) == 1
    ent = parser.brand_entities[0]
    assert ent["@type"] == "Corporation"
    assert ent["name"] == "GainHelm Inc"
    assert ent["@id"] == "https://gainhelm.com/#corp"


def test_verify_html_brand_entity_in_llm_memory_helper():
    """Verifies verify_html_brand_entity_in_llm_memory status, violations_count, and issues reporting."""
    clean_html = (
        '<!DOCTYPE html><html><head><title>Loan Engine</title>'
        '<script type="application/ld+json">'
        '{\n'
        '  "@context": "https://schema.org",\n'
        '  "@type": "Organization",\n'
        '  "@id": "https://gainhelm.com/#organization",\n'
        '  "name": "GainHelm",\n'
        '  "url": "https://gainhelm.com",\n'
        '  "sameAs": ["https://www.wikidata.org/wiki/Q115862807"]\n'
        '}'
        '</script></head><body><h1>Title</h1></body></html>'
    )

    # 1. Compliant passes
    res_pass = verify_html_brand_entity_in_llm_memory(clean_html)
    assert res_pass["status"] == "PASS"
    assert res_pass["violations_count"] == 0
    assert not res_pass["issues"]
    assert res_pass["entities_count"] == 1

    # 2. Missing JSON-LD fails
    res_no_json = verify_html_brand_entity_in_llm_memory('<html><body><h1>No schema</h1></body></html>')
    assert res_no_json["status"] == "FAIL"
    assert res_no_json["violations_count"] >= 1
    assert any("Missing Schema.org JSON-LD" in i for i in res_no_json["issues"])

    # 3. Disconnected fragment fails
    bad_frag = clean_html.replace('"@id": "https://gainhelm.com/#organization",\n', '')
    res_frag = verify_html_brand_entity_in_llm_memory(bad_frag)
    assert res_frag["status"] == "FAIL"
    assert any("disconnected schema fragment" in i for i in res_frag["issues"])


def test_check_brand_entity_in_llm_memory_gate_synthetic_fixtures(tmp_path):
    """Verifies check_brand_entity_in_llm_memory_gate across positive and negative directory fixtures."""
    clean_schema = (
        '<script type="application/ld+json">'
        '{\n'
        '  "@context": "https://schema.org",\n'
        '  "@type": "Organization",\n'
        '  "@id": "https://profithelm.com/#organization",\n'
        '  "name": "ProfitHelm",\n'
        '  "url": "https://profithelm.com",\n'
        '  "sameAs": [\n'
        '    "https://www.wikidata.org/wiki/Q115862807",\n'
        '    "https://www.linkedin.com/company/profithelm"\n'
        '  ]\n'
        '}'
        '</script>'
    )

    # 1. Positive directory fixture
    dist_pos = tmp_path / "dist_pos_factor3"
    dist_pos.mkdir()
    (dist_pos / "index.html").write_text(
        f'<!DOCTYPE html><html><head><title>ProfitHelm Home</title>{clean_schema}</head><body><h1>Header</h1></body></html>',
        encoding="utf-8",
    )
    (dist_pos / "tools").mkdir()
    (dist_pos / "tools" / "index.html").write_text(
        f'<!DOCTYPE html><html><head><title>Tools Hub</title>{clean_schema}</head><body><h1>Header</h1></body></html>',
        encoding="utf-8",
    )

    verifier_pos = MasterSEOVerifier(dist_dir=dist_pos, domain="profithelm.com", brand_name="ProfitHelm")
    res_pos = verifier_pos.check_brand_entity_in_llm_memory_gate(dist_pos)
    assert res_pos["status"] == "PASS"
    assert res_pos["violations_count"] == 0
    assert res_pos["pages_checked"] == 2
    assert res_pos["entities_found"] >= 2

    # 2. Negative directory fixture
    dist_neg = tmp_path / "dist_neg_factor3"
    dist_neg.mkdir()
    # Missing schema page
    (dist_neg / "index.html").write_text(
        '<!DOCTYPE html><html><body><h1>Header</h1><p>Missing schema</p></body></html>',
        encoding="utf-8",
    )
    # Disconnected fragment page
    (dist_neg / "disconnected.html").write_text(
        '<!DOCTYPE html><html><head>'
        '<script type="application/ld+json">'
        '{"@type": "Organization", "name": "ProfitHelm", "url": "https://profithelm.com", "sameAs": ["https://www.wikidata.org/wiki/Q115862807"]}'
        '</script></head><body><h1>Header</h1></body></html>',
        encoding="utf-8",
    )
    # Self-referential sameAs page
    (dist_neg / "selfref.html").write_text(
        '<!DOCTYPE html><html><head>'
        '<script type="application/ld+json">'
        '{"@type": "Organization", "@id": "https://profithelm.com/#org", "name": "ProfitHelm", "url": "https://profithelm.com", "sameAs": ["https://profithelm.com/about"]}'
        '</script></head><body><h1>Header</h1></body></html>',
        encoding="utf-8",
    )

    verifier_neg = MasterSEOVerifier(dist_dir=dist_neg, domain="profithelm.com", brand_name="ProfitHelm")
    res_neg = verifier_neg.check_brand_entity_in_llm_memory_gate(dist_neg)
    assert res_neg["status"] == "FAIL"
    assert res_neg["violations_count"] >= 3
    assert any("Missing Schema.org JSON-LD" in i for i in res_neg["issues"])
    assert any("disconnected schema fragment" in i for i in res_neg["issues"])
    assert any("self-referential" in i for i in res_neg["issues"])


def test_gate_aliases_and_checklist_integration_factor3(tmp_path):
    """Verifies Factor 3 gate aliases and audit_seo_checklist integration."""
    clean_schema = (
        '<script type="application/ld+json">'
        '{\n'
        '  "@context": "https://schema.org",\n'
        '  "@type": "Organization",\n'
        '  "@id": "https://gainhelm.com/#organization",\n'
        '  "name": "GainHelm",\n'
        '  "url": "https://gainhelm.com",\n'
        '  "sameAs": ["https://www.wikidata.org/wiki/Q115862807"]\n'
        '}'
        '</script>'
    )
    dist = tmp_path / "dist_factor3_integration"
    dist.mkdir()
    (dist / "index.html").write_text(
        f'<!DOCTYPE html><html><head><title>GainHelm</title>{clean_schema}</head><body><h1>Title</h1></body></html>',
        encoding="utf-8",
    )

    verifier = MasterSEOVerifier(dist_dir=dist, domain="gainhelm.com", brand_name="GainHelm")

    # Verifier method aliases
    res1 = verifier.check_brand_entity_in_llm_memory_gate(dist)
    res2 = verifier.check_brand_entity_gate(dist)
    res3 = verifier.check_entity_memory_gate(dist)
    res4 = verifier.verify_brand_entity_in_llm_memory(dist)
    assert res1["status"] == res2["status"] == res3["status"] == res4["status"] == "PASS"

    # Module-level alias functions
    m_res1 = check_brand_entity_in_llm_memory_gate(dist, brand_name="GainHelm", brand_domain="gainhelm.com")
    m_res2 = check_brand_entity_gate(dist, brand_name="GainHelm", brand_domain="gainhelm.com")
    m_res3 = check_entity_memory_gate(dist, brand_name="GainHelm", brand_domain="gainhelm.com")
    m_res4 = verify_brand_entity_in_llm_memory(dist, brand_name="GainHelm", brand_domain="gainhelm.com")
    assert m_res1["status"] == m_res2["status"] == m_res3["status"] == m_res4["status"] == "PASS"

    # Checklist gates inclusion
    audit_res = verifier.audit_seo_checklist(dist, enforce_relevance=False)
    assert "check_brand_entity_in_llm_memory_gate" in audit_res["gates"]
    assert audit_res["gates"]["check_brand_entity_in_llm_memory_gate"]["status"] == "PASS"


# =============================================================================
# Factor 4: Citable / Specific Facts (+2.07) Tests
# =============================================================================


def test_zyppy_2026_ai_factors_spec_factor4():
    """Verifies Factor 4: Citable / Specific Facts is properly registered in ZYPPY_2026_AI_FACTORS_SPEC."""
    assert len(ZYPPY_2026_AI_FACTORS_SPEC) == 14

    # Factor 4 (index 3) must be Citable / Specific Facts with weight 2.07
    f4 = ZYPPY_2026_AI_FACTORS_SPEC[3]
    assert f4["code"] == "citable_specific_facts"
    assert "Citable / Specific Facts" in (f4["name"], f4["factor"])
    assert f4["weight"] == 2.07
    assert f4["positive_weight"] == 2.07
    assert f4["negative_weight"] == -2.07

    # Lookup by 1-indexed position
    spec_by_idx = get_ai_factor_spec(4)
    assert spec_by_idx is not None
    assert spec_by_idx["code"] == "citable_specific_facts"

    # Lookup by code and aliases
    assert get_ai_factor_spec("citable_specific_facts") is f4
    assert get_ai_factor_spec("citable_facts") is f4
    assert get_ai_factor_spec("Citable / Specific Facts") is f4
    assert get_ai_factor_spec("Citable Specific Facts") is f4
    assert get_ai_factor_spec("citable") is f4
    assert get_ai_factor_spec("specific_facts") is f4


def test_extract_statutory_citations_boundaries():
    """Verifies extract_statutory_citations extracts CFR, USC, IRC, and IRS guidance references."""
    # 1. CFR citations
    cfr_text = (
        "Under 26 CFR § 1.179-1, taxpayers must elect expensing on an amended or timely return. "
        "Additionally, 12 CFR Part 1026 applies to consumer credit disclosures, while "
        "45 CFR § 164.502 governs HIPAA privacy and 29 CFR § 1910.1200 defines hazard communication."
    )
    cfr_cites = extract_statutory_citations(cfr_text)
    cfr_authorities = [c["authority"] for c in cfr_cites]
    assert "CFR" in cfr_authorities
    assert any(c["section"] == "1.179-1" for c in cfr_cites)
    assert any(c["section"] == "1026" for c in cfr_cites)
    assert any(c["section"] == "164.502" for c in cfr_cites)
    assert any(c["section"] == "1910.1200" for c in cfr_cites)

    # 2. USC citations
    usc_text = (
        "Pursuant to 26 U.S.C. § 179, small businesses expense capital purchases. "
        "Moreover, 26 USC 1031 governs like-kind exchanges, 15 U.S.C. § 1601 establishes TILA, "
        "and 11 U.S.C. § 523(a) defines bankruptcy exceptions."
    )
    usc_cites = extract_statutory_citations(usc_text)
    usc_sections = [c["section"] for c in usc_cites]
    assert "179" in usc_sections
    assert "1031" in usc_sections
    assert "1601" in usc_sections
    assert any("523" in s for s in usc_sections)

    # 3. IRC and IRS guidance citations
    irs_text = (
        "Under IRC § 179 and IRC Section 1031, tax deferrals apply. "
        "The IRS issued Rev. Proc. 2024-12 and Notice 2024-41 detailing inflation adjustments, "
        "while IRS Publication 946 and Treas. Reg. § 1.179-1 provide operational instructions."
    )
    irs_cites = extract_statutory_citations(irs_text)
    authorities = {c["authority"] for c in irs_cites}
    assert "IRC" in authorities
    assert "IRS" in authorities
    assert any("2024-12" in c["citation"] for c in irs_cites)
    assert any("2024-41" in c["citation"] for c in irs_cites)
    assert any("946" in c["citation"] for c in irs_cites)
    assert any("1.179-1" in c["citation"] for c in irs_cites)

    # 4. Empty or invalid string returns empty list
    assert extract_statutory_citations("") == []
    assert extract_statutory_citations(None) == []


def test_detect_malformed_statutory_citations_boundaries():
    """Verifies detect_malformed_statutory_citations flags dangling, out-of-bounds, and invalid citations."""
    # 1. Dangling USC citation without section
    bad_usc = "Taxpayers must review 26 U.S.C. before claiming deductions."
    issues_usc = detect_malformed_statutory_citations(bad_usc)
    assert len(issues_usc) > 0
    assert any("lacking valid section number" in i for i in issues_usc)

    # 2. Dangling CFR citation without section
    bad_cfr = "The Treasury issued 26 CFR to clarify statutory terms."
    issues_cfr = detect_malformed_statutory_citations(bad_cfr)
    assert len(issues_cfr) > 0
    assert any("lacking valid section or part number" in i for i in issues_cfr)

    # 3. Dangling IRC citation without section
    bad_irc = "Consult IRC § for details."
    issues_irc = detect_malformed_statutory_citations(bad_irc)
    assert len(issues_irc) > 0
    assert any("lacking valid section number" in i for i in issues_irc)

    # 4. Out-of-bounds title numbers (USC > 54, CFR > 50)
    bad_title_usc = "Under 99 U.S.C. § 179, rules apply."
    issues_t_usc = detect_malformed_statutory_citations(bad_title_usc)
    assert any("USC titles range from 1 to 54" in i for i in issues_t_usc)

    bad_title_cfr = "Under 60 CFR § 1.179, rules apply."
    issues_t_cfr = detect_malformed_statutory_citations(bad_title_cfr)
    assert any("CFR titles range from 1 to 50" in i for i in issues_t_cfr)

    # 5. Missing preceding title number
    bad_no_title = "Under U.S.C. § 179, equipment qualifies."
    issues_no_title = detect_malformed_statutory_citations(bad_no_title)
    assert any("missing preceding title number" in i for i in issues_no_title)

    # 6. Negative section number
    bad_neg = "Under 26 U.S.C. § -179, deductions are disallowed."
    issues_neg = detect_malformed_statutory_citations(bad_neg)
    assert any("negative section number" in i for i in issues_neg)

    # 7. Placeholder section
    bad_ph = "Under 26 U.S.C. § [TODO], amounts are set."
    issues_ph = detect_malformed_statutory_citations(bad_ph)
    assert any("placeholder or unfinalized section" in i for i in issues_ph)

    # 8. Clean citation has zero malformed issues
    clean_text = "Under 26 U.S.C. § 179 and 26 CFR § 1.179-1, write-offs apply."
    assert detect_malformed_statutory_citations(clean_text) == []


def test_assert_statutory_citation_syntax():
    """Verifies assert_statutory_citation_syntax raises on malformed or missing citations and passes on valid ones."""
    # 1. Valid passes
    assert assert_statutory_citation_syntax("26 U.S.C. § 179") is True
    assert assert_statutory_citation_syntax("26 CFR § 1.179-1") is True
    assert assert_statutory_citation_syntax("IRC § 1031") is True
    assert assert_statutory_citation_syntax("Rev. Proc. 2024-12") is True

    # 2. Missing citation raises ValueError
    with pytest.raises(ValueError, match="No valid primary statutory citations found"):
        assert_statutory_citation_syntax("General discussion with no legal citation")

    # 3. Malformed citation raises ValueError
    with pytest.raises(ValueError, match="Malformed statutory citation syntax"):
        assert_statutory_citation_syntax("Dangling citation: 26 U.S.C. allows deductions")

    # 4. Anti-slop in citation raises ValueError
    with pytest.raises(ValueError, match="Forbidden em-dash"):
        assert_statutory_citation_syntax("26 U.S.C. \u2014 § 179")


def test_assert_no_vague_generalizations():
    """Verifies assert_no_vague_generalizations rejects evasive factual assertions."""
    vague_examples = [
        "According to tax laws, taxpayers can deduct expenses.",
        "Many experts say that bonus depreciation is ending.",
        "Studies show that Section 179 improves business liquidity.",
        "Regulations generally provide a thirty-day safe harbor.",
        "The government allows businesses to deduct equipment.",
        "Under federal guidelines, write-offs are permitted.",
        "Industry standards indicate an average lifespan of seven years.",
        "Research indicates high adoption across manufacturing.",
        "It is widely believed that tax brackets will adjust upward.",
    ]
    for ex in vague_examples:
        with pytest.raises(ValueError, match="Vague generalization disguised as factual analysis detected"):
            assert_no_vague_generalizations(ex)

    # Clean text without vague assertions passes
    clean = "26 U.S.C. § 179 establishes a statutory deduction limit of $1,220,000 for tax year 2026."
    assert assert_no_vague_generalizations(clean) is True


def test_assert_numeric_data_density_boundaries():
    """Verifies assert_numeric_data_density quantifies numbers and rejects incomplete placeholders."""
    # 1. High density text with currency, percentage, and years passes
    dense_text = (
        "The Section 179 expense ceiling for 2026 is $1,220,000, with a phaseout threshold "
        "beginning at $3,050,000. Equipment placed in service qualifies for 20% bonus depreciation."
    )
    assert assert_numeric_data_density(dense_text, min_facts=3) is True

    # 2. Deficit count fails
    sparse_text = "The machine costs a lot of money and takes time to depreciate."
    with pytest.raises(ValueError, match="Numeric data density violation"):
        assert_numeric_data_density(sparse_text, min_facts=3)

    # 3. Incomplete figures rejected
    with pytest.raises(ValueError, match="Incomplete numeric figure detected"):
        assert_numeric_data_density("The threshold is $XX for the current year.", min_facts=1)

    with pytest.raises(ValueError, match="Incomplete numeric figure detected"):
        assert_numeric_data_density("Tax rate is XX% under the current proposal.", min_facts=1)

    with pytest.raises(ValueError, match="Incomplete numeric figure detected"):
        assert_numeric_data_density("Expected savings: $[amount] per company.", min_facts=1)

    with pytest.raises(ValueError, match="Incomplete numeric figure detected"):
        assert_numeric_data_density("The allowance is TBD pending IRS publication.", min_facts=1)


def test_assert_data_table_structure_boundaries():
    """Verifies assert_data_table_structure enforces headers, rows, columns, and extractable figures."""
    compliant_table = (
        "<table>"
        "  <thead>"
        "    <tr><th>Metric</th><th>2026 Threshold</th><th>Statutory Reference</th></tr>"
        "  </thead>"
        "  <tbody>"
        "    <tr><td>Expensing Cap</td><td>$1,220,000</td><td>26 U.S.C. § 179(b)(1)</td></tr>"
        "    <tr><td>Phaseout Threshold</td><td>$3,050,000</td><td>26 U.S.C. § 179(b)(2)</td></tr>"
        "    <tr><td>Bonus Depreciation</td><td>20%</td><td>26 U.S.C. § 168(k)</td></tr>"
        "  </tbody>"
        "</table>"
    )
    assert assert_data_table_structure(compliant_table) is True

    # 1. Missing <table>
    with pytest.raises(ValueError, match="Document missing <table> element"):
        assert_data_table_structure("<div>Just a div</div>")

    # 2. Missing <th> headers
    no_th = (
        "<table>"
        "  <tr><td>Row 1 Col 1</td><td>Row 1 Col 2</td></tr>"
        "  <tr><td>Row 2 Col 1</td><td>Row 2 Col 2</td></tr>"
        "</table>"
    )
    with pytest.raises(ValueError, match="missing structured <th> header cells"):
        assert_data_table_structure(no_th)

    # 3. Insufficient columns (< 2 headers)
    single_col_th = (
        "<table>"
        "  <tr><th>Only One Column</th></tr>"
        "  <tr><td>Data point $100</td></tr>"
        "</table>"
    )
    with pytest.raises(ValueError, match="column count .* below minimum 2 columns"):
        assert_data_table_structure(single_col_th)

    # 4. Empty table (no data rows)
    empty_tbody = (
        "<table>"
        "  <thead><tr><th>Col A</th><th>Col B</th></tr></thead>"
        "  <tbody></tbody>"
        "</table>"
    )
    with pytest.raises(ValueError, match="contains no data rows"):
        assert_data_table_structure(empty_tbody)

    # 5. Row with fewer than 2 columns
    uneven_row = (
        "<table>"
        "  <tr><th>Col A</th><th>Col B</th></tr>"
        "  <tr><td>Only One Cell</td></tr>"
        "</table>"
    )
    with pytest.raises(ValueError, match="contains rows with fewer than 2 columns"):
        assert_data_table_structure(uneven_row)

    # 6. Empty or blank cells
    blank_cell = (
        "<table>"
        "  <tr><th>Col A</th><th>Col B</th></tr>"
        "  <tr><td>Value A $50</td><td>   </td></tr>"
        "</table>"
    )
    with pytest.raises(ValueError, match="contains empty or blank data cells"):
        assert_data_table_structure(blank_cell)

    # 7. Unstructured narrative block masquerading as data table
    masquerading_table = (
        "<table>"
        "  <tr><td>"
        "    Section 179 expensing allows small businesses to deduct the full purchase price of qualifying equipment "
        "    and software purchased or financed during the tax year. This incentive was created by the federal government "
        "    to encourage businesses to buy equipment and invest in themselves."
        "  </td></tr>"
        "</table>"
    )
    with pytest.raises(ValueError, match="Unstructured narrative block masquerading as data table"):
        assert_data_table_structure(masquerading_table)

    # 8. Table lacking extractable figures (pure words)
    no_figures = (
        "<table>"
        "  <tr><th>Category</th><th>Description</th></tr>"
        "  <tr><td>General</td><td>Qualifying commercial machinery</td></tr>"
        "</table>"
    )
    with pytest.raises(ValueError, match="lacks extractable quantitative data points"):
        assert_data_table_structure(no_figures)

    # 9. Forbidden em-dash in table cell
    dash_cell = compliant_table.replace("26 U.S.C. § 179(b)(1)", "26 U.S.C. \u2014 § 179(b)(1)")
    with pytest.raises(ValueError, match="Forbidden em-dash"):
        assert_data_table_structure(dash_cell)


def test_assert_citable_specific_facts_master_contract():
    """Verifies assert_citable_specific_facts enforces the complete Factor 4 specification."""
    compliant_html = (
        "<!DOCTYPE html><html><head><title>Section 179 Calculator</title></head><body>"
        "<h1>Section 179 Expensing Thresholds</h1>"
        "<p>Under 26 U.S.C. § 179, taxpayers may expense qualifying equipment up to $1,220,000 for tax year 2026. "
        "The spending phaseout threshold begins at $3,050,000, with remaining basis eligible for 20% bonus depreciation.</p>"
        "<table>"
        "  <thead><tr><th>Threshold</th><th>2026 Amount</th><th>Authority</th></tr></thead>"
        "  <tbody>"
        "    <tr><td>Maximum Expense</td><td>$1,220,000</td><td>26 U.S.C. § 179(b)(1)</td></tr>"
        "    <tr><td>Phaseout Begins</td><td>$3,050,000</td><td>26 U.S.C. § 179(b)(2)</td></tr>"
        "    <tr><td>Bonus Depreciation</td><td>20%</td><td>26 CFR § 1.179-1</td></tr>"
        "  </tbody>"
        "</table>"
        "</body></html>"
    )
    assert assert_citable_specific_facts(compliant_html) is True

    # 1. Missing statutory citations fails
    no_citations = compliant_html.replace("26 U.S.C. § 179", "Tax Code").replace("26 CFR § 1.179-1", "Rules")
    with pytest.raises(ValueError, match="Statutory citation deficit"):
        assert_citable_specific_facts(no_citations)

    # 2. Malformed statutory citations fail
    bad_cite = compliant_html.replace("26 U.S.C. § 179", "26 U.S.C. provides deductions")
    with pytest.raises(ValueError, match="Malformed statutory citation syntax"):
        assert_citable_specific_facts(bad_cite)

    # 3. Vague generalizations fail
    vague_html = compliant_html.replace(
        "Under 26 U.S.C. § 179",
        "Many experts say under 26 U.S.C. § 179"
    )
    with pytest.raises(ValueError, match="Vague generalization disguised as factual analysis"):
        assert_citable_specific_facts(vague_html)

    # 4. Incomplete figures fail
    incomp_html = compliant_html.replace("$1,220,000", "$XX")
    with pytest.raises(ValueError, match="Incomplete numeric figure detected"):
        assert_citable_specific_facts(incomp_html)

    # 5. Missing data table fails
    no_table = re.sub(r'<table>.*?</table>', '', compliant_html, flags=re.DOTALL)
    with pytest.raises(ValueError, match="Document missing <table> element"):
        assert_citable_specific_facts(no_table)

    # 6. Unstructured narrative block masquerading as data table fails
    fake_table = (
        "<table><tr><td>"
        "This long paragraph describes the rules without any columns or headers or extractable tabular grid points. "
        "It spans well over thirty words and one hundred and fifty characters in length, masquerading as a table."
        "</td></tr></table>"
    )
    masq_html = re.sub(r'<table>.*?</table>', fake_table, compliant_html, flags=re.DOTALL)
    with pytest.raises(ValueError, match="Unstructured narrative block masquerading as data table"):
        assert_citable_specific_facts(masq_html)

    # 7. Unreferenced statistics without citation fails
    unref_claim = (
        "<!DOCTYPE html><html><body>"
        "<p>The statutory limit of $1,220,000 and phaseout threshold of $3,050,000 apply to 2026 equipment.</p>"
        "<table><thead><tr><th>Metric</th><th>Amount</th></tr></thead>"
        "<tbody><tr><td>Limit</td><td>$1,220,000</td></tr><tr><td>Phaseout</td><td>$3,050,000</td></tr></tbody></table>"
        "</body></html>"
    )
    with pytest.raises(ValueError, match="Statutory citation deficit|Unreferenced statistics"):
        assert_citable_specific_facts(unref_claim)

    # 8. Anti-slop invariant check
    dash_html = compliant_html.replace("2026", "2026 \u2014")
    with pytest.raises(ValueError, match="Forbidden em-dash"):
        assert_citable_specific_facts(dash_html)


def test_single_pass_parser_factor4_state():
    """Verifies SinglePassSEODocumentParser parses tables, extracts citations, and collects numeric facts."""
    html_doc = (
        "<!DOCTYPE html><html><head><title>Title</title></head><body>"
        "<h1>Equipment Write-off Guide</h1>"
        "<p>Under 26 U.S.C. § 179 and 26 CFR § 1.179-1, maximum expense is $1,220,000 for year 2026.</p>"
        "<table>"
        "  <thead><tr><th>Tier</th><th>Rate</th></tr></thead>"
        "  <tbody><tr><td>Tier 1</td><td>21%</td></tr><tr><td>Tier 2</td><td>35%</td></tr></tbody>"
        "</table>"
        "</body></html>"
    )
    parser = SinglePassSEODocumentParser()
    parser.feed(html_doc)

    assert parser.has_statutory_citations is True
    assert len(parser.statutory_citations) >= 2
    assert any(c["authority"] == "USC" for c in parser.statutory_citations)
    assert any(c["authority"] == "CFR" for c in parser.statutory_citations)

    assert parser.numeric_facts_count >= 3
    assert parser.has_data_table is True
    assert parser.has_masquerading_narrative_table is False
    assert len(parser.tables_data) == 1
    assert parser.tables_data[0]["has_headers"] is True
    assert parser.tables_data[0]["col_count"] == 2
    assert parser.tables_data[0]["row_count"] == 2


def test_verify_html_citable_specific_facts_helper():
    """Verifies verify_html_citable_specific_facts returns structured status, violations_count, and issues."""
    compliant_html = (
        "<!DOCTYPE html><html><head><title>Title</title></head><body>"
        "<h1>Tax Depreciation</h1>"
        "<p>Under 26 U.S.C. § 179, businesses deduct up to $1,220,000 for 2026 purchases.</p>"
        "<table>"
        "  <thead><tr><th>Item</th><th>Cap</th></tr></thead>"
        "  <tbody><tr><td>Section 179</td><td>$1,220,000</td></tr><tr><td>Bonus</td><td>20%</td></tr></tbody>"
        "</table>"
        "</body></html>"
    )
    # 1. Compliant HTML passes
    res_pass = verify_html_citable_specific_facts(compliant_html)
    assert res_pass["status"] == "PASS"
    assert res_pass["violations_count"] == 0
    assert not res_pass["issues"]
    assert res_pass["statutory_citations_count"] >= 1
    assert res_pass["numeric_facts_count"] >= 3
    assert res_pass["tables_count"] == 1

    # 2. Deficit citations fails
    no_cite_html = compliant_html.replace("26 U.S.C. § 179", "Rules")
    res_no_cite = verify_html_citable_specific_facts(no_cite_html)
    assert res_no_cite["status"] == "FAIL"
    assert any("Statutory citation deficit" in i for i in res_no_cite["issues"])

    # 3. Vague generalizations fail
    vague_html = compliant_html.replace("Under 26 U.S.C.", "Many experts say under 26 U.S.C.")
    res_vague = verify_html_citable_specific_facts(vague_html)
    assert res_vague["status"] == "FAIL"
    assert any("Vague generalization disguised as factual analysis" in i for i in res_vague["issues"])

    # 4. Missing table fails
    no_tbl_html = re.sub(r'<table>.*?</table>', '', compliant_html, flags=re.DOTALL)
    res_no_tbl = verify_html_citable_specific_facts(no_tbl_html)
    assert res_no_tbl["status"] == "FAIL"
    assert any("Missing <table> element" in i for i in res_no_tbl["issues"])


def test_check_citable_specific_facts_gate_synthetic_fixtures(tmp_path):
    """Verifies check_citable_specific_facts_gate across positive and negative directory fixtures."""
    compliant_page = (
        "<!DOCTYPE html><html><head><title>Title</title></head><body>"
        "<h1>Section 179 Limit</h1>"
        "<p>Under 26 U.S.C. § 179 and 26 CFR § 1.179-1, maximum deduction is $1,220,000 for 2026.</p>"
        "<table>"
        "  <thead><tr><th>Metric</th><th>2026 Amount</th><th>Citation</th></tr></thead>"
        "  <tbody>"
        "    <tr><td>Cap</td><td>$1,220,000</td><td>26 U.S.C. § 179</td></tr>"
        "    <tr><td>Phaseout</td><td>$3,050,000</td><td>26 CFR § 1.179-1</td></tr>"
        "  </tbody>"
        "</table>"
        "</body></html>"
    )

    # 1. Positive directory fixture
    dist_pos = tmp_path / "dist_pos_factor4"
    dist_pos.mkdir()
    (dist_pos / "index.html").write_text(compliant_page, encoding="utf-8")
    (dist_pos / "tools").mkdir()
    (dist_pos / "tools" / "calc.html").write_text(compliant_page, encoding="utf-8")

    verifier_pos = MasterSEOVerifier(dist_dir=dist_pos)
    res_pos = verifier_pos.check_citable_specific_facts_gate(dist_pos)
    assert res_pos["status"] == "PASS"
    assert res_pos["violations_count"] == 0
    assert res_pos["pages_checked"] == 2
    assert res_pos["statutory_citations_found"] >= 2
    assert res_pos["data_tables_found"] >= 2

    # 2. Negative directory fixture
    dist_neg = tmp_path / "dist_neg_factor4"
    dist_neg.mkdir()

    # Vague page
    (dist_neg / "vague.html").write_text(
        compliant_page.replace("Under 26 U.S.C.", "According to tax laws under 26 U.S.C."),
        encoding="utf-8",
    )
    # Dangling citation page
    (dist_neg / "dangling.html").write_text(
        compliant_page.replace("26 U.S.C. § 179", "26 U.S.C. provides"),
        encoding="utf-8",
    )
    # Masquerading table page
    fake_tbl = (
        "<table><tr><td>"
        "This long paragraph describes the rules without any columns or headers or extractable tabular grid points. "
        "It spans well over thirty words and one hundred and fifty characters in length, masquerading as a table."
        "</td></tr></table>"
    )
    (dist_neg / "masquerading.html").write_text(
        re.sub(r'<table>.*?</table>', fake_tbl, compliant_page, flags=re.DOTALL),
        encoding="utf-8",
    )
    # Incomplete figure page
    (dist_neg / "incomplete.html").write_text(
        compliant_page.replace("$1,220,000", "$XX"),
        encoding="utf-8",
    )

    verifier_neg = MasterSEOVerifier(dist_dir=dist_neg)
    res_neg = verifier_neg.check_citable_specific_facts_gate(dist_neg)
    assert res_neg["status"] == "FAIL"
    assert res_neg["violations_count"] >= 4
    assert any("Vague generalization" in i for i in res_neg["issues"])
    assert any("Malformed USC citation" in i for i in res_neg["issues"])
    assert any("masquerading as data table" in i for i in res_neg["issues"])
    assert any("Incomplete or placeholder figure" in i for i in res_neg["issues"])


def test_gate_aliases_and_checklist_integration_factor4(tmp_path):
    """Verifies Factor 4 gate aliases and audit_seo_checklist integration."""
    compliant_page = (
        "<!DOCTYPE html><html><head><title>Title</title></head><body>"
        "<h1>Section 179 Expensing</h1>"
        "<p>Under 26 U.S.C. § 179, taxpayers may write off up to $1,220,000 for 2026.</p>"
        "<table>"
        "  <thead><tr><th>Threshold</th><th>Value</th></tr></thead>"
        "  <tbody><tr><td>Ceiling</td><td>$1,220,000</td></tr><tr><td>Bonus</td><td>20%</td></tr></tbody>"
        "</table>"
        "</body></html>"
    )
    dist = tmp_path / "dist_factor4_integration"
    dist.mkdir()
    (dist / "index.html").write_text(compliant_page, encoding="utf-8")

    verifier = MasterSEOVerifier(dist_dir=dist)

    # Verifier method aliases
    r1 = verifier.check_citable_specific_facts_gate(dist)
    r2 = verifier.check_citable_facts_gate(dist)
    r3 = verifier.check_specific_facts_gate(dist)
    r4 = verifier.verify_citable_specific_facts(dist)
    assert r1["status"] == r2["status"] == r3["status"] == r4["status"] == "PASS"

    # Module-level alias functions
    m1 = check_citable_specific_facts_gate(dist)
    m2 = check_citable_facts_gate(dist)
    m3 = check_specific_facts_gate(dist)
    m4 = verify_citable_specific_facts(dist)
    assert m1["status"] == m2["status"] == m3["status"] == m4["status"] == "PASS"

    # Checklist gates inclusion
    audit_res = verifier.audit_seo_checklist(dist, enforce_relevance=False)
    assert "check_citable_specific_facts_gate" in audit_res["gates"]
    assert audit_res["gates"]["check_citable_specific_facts_gate"]["status"] == "PASS"


# =============================================================================
# Factor 5: Organic Fan-Out Coverage Rankings (+1.91) Tests
# =============================================================================


def test_zyppy_2026_ai_factors_spec_factor5():
    """Verifies Factor 5: Organic Fan-Out Coverage Rankings is properly registered in ZYPPY_2026_AI_FACTORS_SPEC."""
    assert len(ZYPPY_2026_AI_FACTORS_SPEC) == 14

    # Factor 5 (index 4) must be Organic Fan-Out Coverage Rankings with weight 1.91
    f5 = ZYPPY_2026_AI_FACTORS_SPEC[4]
    assert f5["code"] == "organic_fan_out_coverage"
    assert "Organic Fan-Out Coverage Rankings" in (f5["name"], f5["factor"])
    assert f5["weight"] == 1.91
    assert f5["positive_weight"] == 1.91
    assert f5["negative_weight"] == -1.91
    assert "subquery clustering" in f5["description"].lower()

    # Lookup by 1-indexed position
    spec_by_idx = get_ai_factor_spec(5)
    assert spec_by_idx is not None
    assert spec_by_idx["code"] == "organic_fan_out_coverage"

    # Lookup by code and aliases
    assert get_ai_factor_spec("organic_fan_out_coverage") is f5
    assert get_ai_factor_spec("organic-fan-out-coverage") is f5
    assert get_ai_factor_spec("organic_fan_out_coverage_rankings") is f5
    assert get_ai_factor_spec("Organic Fan-Out Coverage Rankings") is f5
    assert get_ai_factor_spec("Organic Fan-Out Coverage") is f5
    assert get_ai_factor_spec("fan_out_coverage") is f5
    assert get_ai_factor_spec("organic_fan_out") is f5
    assert get_ai_factor_spec("fan_out") is f5
    assert get_ai_factor_spec("subquery_clustering") is f5


def test_extract_subquery_sections_html_and_markdown():
    """Verifies extract_subquery_sections parses HTML and markdown headings and classifies intent."""
    html_content = (
        "<!DOCTYPE html><html><body>"
        "<h1>Equipment Financing Guide</h1>"
        "<h2>What is the Section 179 deduction limit for 2026?</h2>"
        "<p>For taxable years beginning in 2026, the statutory ceiling is $1,220,000 for qualifying capital expenses.</p>"
        "<h2>Bonus Depreciation vs Section 179 Comparison</h2>"
        "<p>Taxpayers may evaluate whether taking 20% bonus depreciation yields lower tax burden than immediate expense election.</p>"
        "<h2>General Disclaimer</h2>"
        "<p>Consult a qualified tax advisor before filing.</p>"
        "</body></html>"
    )
    sections = extract_subquery_sections(html_content)
    assert len(sections) == 3

    # Section 1 is a question subquery
    assert sections[0]["heading"] == "What is the Section 179 deduction limit for 2026?"
    assert sections[0]["is_question"] is True
    assert sections[0]["is_subquery"] is True
    assert sections[0]["word_count"] > 10

    # Section 2 is a secondary intent comparison subquery
    assert "Bonus Depreciation" in sections[1]["heading"]
    assert sections[1]["is_secondary_intent"] is True
    assert sections[1]["is_subquery"] is True

    # Section 3 is general, neither question starter nor secondary keyword
    assert sections[2]["is_question"] is False
    assert sections[2]["is_secondary_intent"] is False
    assert sections[2]["is_subquery"] is False

    # Markdown format parsing
    md_content = (
        "# Title\n\n"
        "## How does equipment leasing impact cash flow?\n"
        "Leasing preserves working capital while providing immediate deployment of revenue generating equipment.\n\n"
        "## Calculation Scenarios for Small Business\n"
        "Small businesses with gross revenue below $5,000,000 should review these threshold scenarios.\n"
    )
    md_sections = extract_subquery_sections(md_content)
    assert len(md_sections) == 2
    assert md_sections[0]["is_question"] is True
    assert md_sections[1]["is_secondary_intent"] is True

    # Empty or invalid inputs
    assert extract_subquery_sections("") == []
    assert extract_subquery_sections(None) == []


def test_detect_shallow_subquestions_boundaries():
    """Verifies detect_shallow_subquestions detects answers below the word threshold."""
    sections = [
        {
            "heading": "What is the bonus depreciation rate?",
            "is_subquery": True,
            "word_count": 25,
        },
        {
            "heading": "How is the phaseout calculated?",
            "is_subquery": True,
            "word_count": 4,
        },
        {
            "heading": "Non subquery heading",
            "is_subquery": False,
            "word_count": 2,
        },
    ]
    shallow = detect_shallow_subquestions(sections, min_words=15)
    assert len(shallow) == 1
    assert "How is the phaseout calculated?" in shallow[0]
    assert "4 words" in shallow[0]


def test_assert_subquery_clustering_boundaries():
    """Verifies assert_subquery_clustering enforces subquery density, substantive answers, and anti-slop."""
    valid_html = (
        "<!DOCTYPE html><html><body>"
        "<h1>Tax Deductions</h1>"
        "<h2>What are the statutory qualifying property categories?</h2>"
        "<p>Qualifying property includes tangible personal property, off-the-shelf software, and certain qualified improvement property deployed in business operations.</p>"
        "<h2>How does the phaseout threshold apply to large purchases?</h2>"
        "<p>The deduction begins phasing out dollar for dollar once total qualifying equipment purchases exceed the $3,050,000 investment ceiling.</p>"
        "</body></html>"
    )
    assert assert_subquery_clustering(valid_html, min_subqueries=2, min_words_per_answer=15) is True

    # Deficit: only 1 subquery
    deficit_html = (
        "<!DOCTYPE html><html><body>"
        "<h1>Tax Deductions</h1>"
        "<h2>What are the statutory qualifying property categories?</h2>"
        "<p>Qualifying property includes tangible personal property, off-the-shelf software, and certain qualified improvement property deployed in business operations.</p>"
        "</body></html>"
    )
    with pytest.raises(ValueError, match="Subquery clustering deficit"):
        assert_subquery_clustering(deficit_html, min_subqueries=2)

    # Shallow question list: answers are too short
    shallow_html = (
        "<!DOCTYPE html><html><body>"
        "<h1>Tax FAQ</h1>"
        "<h2>What is Section 179?</h2>"
        "<p>A tax deduction.</p>"
        "<h2>Can I expense vehicles?</h2>"
        "<p>Yes, sometimes.</p>"
        "</body></html>"
    )
    with pytest.raises(ValueError, match="Shallow question list detected"):
        assert_subquery_clustering(shallow_html, min_subqueries=2, min_words_per_answer=15)

    # Non-string raises ValueError
    with pytest.raises(ValueError, match="Content must be a string"):
        assert_subquery_clustering(12345)

    # Em-dash raises ValueError
    em_dash_html = valid_html.replace("Qualifying property", "Qualifying property \u2014")
    with pytest.raises(ValueError, match="Forbidden em-dash"):
        assert_subquery_clustering(em_dash_html)


def test_extract_calculation_variant_nodes_containers():
    """Verifies extract_calculation_variant_nodes parses variant containers, IDs, math, and cross-links."""
    html_doc = (
        "<!DOCTYPE html><html><body>"
        '<div class="calculation-variant" data-variant-id="equip-purchase" id="variant-equipment">'
        "  <h3>Equipment Purchase Variant</h3>"
        "  <p>Deduction formula: total_cost * 1.0 = $250,000 write-off.</p>"
        '  <p>Compare with: <a href="#variant-software">Software Variant</a></p>'
        "</div>"
        '<div class="calculation-variant" data-variant-id="software-license" id="variant-software">'
        "  <h3>Software Licensing Variant</h3>"
        "  <p>Deduction formula: total_cost * 1.0 = $120,000 write-off.</p>"
        '  <p>Compare with: <a href="#variant-equipment">Equipment Variant</a></p>'
        "</div>"
        "</body></html>"
    )
    nodes = extract_calculation_variant_nodes(html_doc)
    assert len(nodes) == 2

    n1 = nodes[0]
    assert n1["id"] == "equip-purchase"
    assert n1["title"] == "Equipment Purchase Variant"
    assert n1["has_calculation"] is True
    assert "#variant-software" in n1["outgoing_links"]

    n2 = nodes[1]
    assert n2["id"] == "software-license"
    assert n2["title"] == "Software Licensing Variant"
    assert n2["has_calculation"] is True
    assert "#variant-equipment" in n2["outgoing_links"]

    # Test empty or non-string
    assert extract_calculation_variant_nodes("") == []
    assert extract_calculation_variant_nodes(None) == []


def test_detect_orphaned_calculation_nodes_boundaries():
    """Verifies detect_orphaned_calculation_nodes identifies unlinked or partially linked variant nodes."""
    # Fully linked pair
    nodes_linked = [
        {"id": "var-a", "title": "Variant A", "outgoing_links": ["#var-b"]},
        {"id": "var-b", "title": "Variant B", "outgoing_links": ["#var-a"]},
    ]
    assert detect_orphaned_calculation_nodes(nodes_linked) == []

    # One orphaned node with 0 outgoing links
    nodes_one_orphaned = [
        {"id": "var-a", "title": "Variant A", "outgoing_links": ["#var-b"]},
        {"id": "var-b", "title": "Variant B", "outgoing_links": []},
    ]
    orphaned = detect_orphaned_calculation_nodes(nodes_one_orphaned)
    assert len(orphaned) >= 1
    orphaned_ids = [o["id"] for o in orphaned]
    assert "var-b" in orphaned_ids

    # Completely unlinked nodes
    nodes_unlinked = [
        {"id": "var-a", "title": "Variant A", "outgoing_links": []},
        {"id": "var-b", "title": "Variant B", "outgoing_links": []},
    ]
    assert len(detect_orphaned_calculation_nodes(nodes_unlinked)) == 2

    # Single node cannot be evaluated as orphaned cluster
    assert detect_orphaned_calculation_nodes([{"id": "var-a", "outgoing_links": []}]) == []


def test_verify_calculation_variant_reciprocity_boundaries():
    """Verifies reciprocal cross-linking detection between calculation variant pairs."""
    # Reciprocal
    reciprocal_nodes = [
        {"id": "opt-1", "title": "Option 1", "outgoing_links": ["#opt-2"]},
        {"id": "opt-2", "title": "Option 2", "outgoing_links": ["#opt-1"]},
    ]
    res_rec = verify_calculation_variant_reciprocity(reciprocal_nodes)
    assert res_rec["is_reciprocal"] is True
    assert len(res_rec["issues"]) == 0

    # Unreciprocated: opt-1 links to opt-2, but opt-2 does not link back
    unreciprocal_nodes = [
        {"id": "opt-1", "title": "Option 1", "outgoing_links": ["#opt-2"]},
        {"id": "opt-2", "title": "Option 2", "outgoing_links": []},
    ]
    res_unrec = verify_calculation_variant_reciprocity(unreciprocal_nodes)
    assert res_unrec["is_reciprocal"] is False
    assert len(res_unrec["issues"]) > 0
    assert "Unreciprocated cross-link" in res_unrec["issues"][0]


def test_assert_calculation_variant_cross_links_boundaries():
    """Verifies assert_calculation_variant_cross_links catches deficits, shallow logic, orphans, and reciprocity breaks."""
    valid_doc = (
        '<div class="calculation-variant" data-variant-id="tier-a" id="variant-tier-a">'
        "  <h3>Tier A Calculation</h3>"
        "  <p>Equation: tax_rate * base = 0.20 * $100,000 = $20,000.</p>"
        '  <p>Related: <a href="#variant-tier-b">Tier B</a></p>'
        "</div>"
        '<div class="calculation-variant" data-variant-id="tier-b" id="variant-tier-b">'
        "  <h3>Tier B Calculation</h3>"
        "  <p>Equation: tax_rate * base = 0.35 * $100,000 = $35,000.</p>"
        '  <p>Related: <a href="#variant-tier-a">Tier A</a></p>'
        "</div>"
    )
    assert assert_calculation_variant_cross_links(valid_doc, min_variants=2, require_reciprocal=True) is True

    # Deficit: only 1 variant
    doc_single = (
        '<div class="calculation-variant" data-variant-id="tier-a" id="variant-tier-a">'
        "  <h3>Tier A Calculation</h3>"
        "  <p>Equation: tax_rate * base = 0.20 * $100,000 = $20,000.</p>"
        "</div>"
    )
    with pytest.raises(ValueError, match="Calculation variant deficit"):
        assert_calculation_variant_cross_links(doc_single, min_variants=2)

    # Shallow variant lacking calculation logic
    doc_no_math = (
        '<div class="calculation-variant" data-variant-id="tier-a" id="variant-tier-a">'
        "  <h3>Tier A Calculation</h3>"
        "  <p>This is a narrative description without numbers, formulas, or tables.</p>"
        '  <p><a href="#variant-tier-b">Go to B</a></p>'
        "</div>"
        '<div class="calculation-variant" data-variant-id="tier-b" id="variant-tier-b">'
        "  <h3>Tier B Calculation</h3>"
        "  <p>Calculation: $50 * 10 = $500.</p>"
        '  <p><a href="#variant-tier-a">Go to A</a></p>'
        "</div>"
    )
    with pytest.raises(ValueError, match="Shallow calculation variant detected"):
        assert_calculation_variant_cross_links(doc_no_math, min_variants=2)

    # Orphaned calculation node
    doc_orphaned = (
        '<div class="calculation-variant" data-variant-id="tier-a" id="variant-tier-a">'
        "  <h3>Tier A Calculation</h3>"
        "  <p>Equation: 20% * $10,000 = $2,000.</p>"
        "</div>"
        '<div class="calculation-variant" data-variant-id="tier-b" id="variant-tier-b">'
        "  <h3>Tier B Calculation</h3>"
        "  <p>Equation: 30% * $10,000 = $3,000.</p>"
        "</div>"
    )
    with pytest.raises(ValueError, match="Orphaned calculation node"):
        assert_calculation_variant_cross_links(doc_orphaned, min_variants=2)


def test_assert_no_thin_fan_out_cannibalization_boundaries():
    """Verifies assert_no_thin_fan_out_cannibalization rejects thin disconnected pages."""
    substantive_doc = "word " * 160
    assert assert_no_thin_fan_out_cannibalization(substantive_doc, min_words=150) is True

    thin_doc = "word " * 40
    with pytest.raises(ValueError, match="Thin fan-out page detected"):
        assert_no_thin_fan_out_cannibalization(thin_doc, min_words=150)


def test_assert_organic_fan_out_coverage_master_contract():
    """Verifies the master assert_organic_fan_out_coverage contract and its aliases."""
    compliant_page = (
        "<!DOCTYPE html><html><head><title>Section 179 Fan-Out Analysis</title></head><body>"
        "<h1>Section 179 Fan-Out Analysis and Calculation Variants</h1>"
        "<p>This comprehensive technical guide evaluates the full spectrum of equipment expense elections, "
        "addressing primary and secondary intent queries to eliminate thin page fragmentation across multi-intent search queries. "
        "Taxpayers must account for equipment acquisition dates, bonus depreciation phaseouts, and aggregate expenditure thresholds "
        "to optimize their total federal tax deductions under 26 U.S.C. Section 179.</p>"
        "<h2>How does the phaseout threshold affect large capital investments?</h2>"
        "<p>When business equipment purchases surpass the initial $3,050,000 investment ceiling, the allowable expensing limit "
        "reduces dollar for dollar until the deduction is completely phased out at the statutory expenditure threshold.</p>"
        "<h2>What are the eligible property categories for immediate expensing?</h2>"
        "<p>Eligible property includes machinery, computers, software, office furniture, business vehicles, and certain qualified improvement "
        "property deployed within the fiscal year according to current statutory guidelines.</p>"
        '<div class="calculation-variant" data-variant-id="variant-machinery" id="variant-machinery">'
        "  <h3>Machinery Calculation Variant</h3>"
        "  <p>Formula: total_investment * 1.0 = $500,000 first year expensing deduction.</p>"
        '  <p>Cross link to alternative: <a href="#variant-software">Compare with Software Variant</a></p>'
        "</div>"
        '<div class="calculation-variant" data-variant-id="variant-software" id="variant-software">'
        "  <h3>Off-the-Shelf Software Calculation Variant</h3>"
        "  <p>Formula: license_cost * 1.0 = $150,000 immediate write-off deduction.</p>"
        '  <p>Cross link to alternative: <a href="#variant-machinery">Compare with Machinery Variant</a></p>'
        "</div>"
        "</body></html>"
    )

    # Master contract
    assert assert_organic_fan_out_coverage(compliant_page, min_subqueries=2, min_variants=2, min_total_words=150) is True

    # Aliases
    assert assert_fan_out_coverage(compliant_page, min_subqueries=2, min_variants=2, min_total_words=150) is True
    assert assert_organic_fan_out(compliant_page, min_subqueries=2, min_variants=2, min_total_words=150) is True

    # Em-dash violation
    with pytest.raises(ValueError, match="Forbidden em-dash"):
        assert_organic_fan_out_coverage(compliant_page.replace("guidelines.", "guidelines \u2014"))

    # En-dash violation
    with pytest.raises(ValueError, match="Forbidden en-dash"):
        assert_organic_fan_out_coverage(compliant_page.replace("guidelines.", "guidelines \u2013"))


def test_single_pass_parser_factor5_state():
    """Verifies SinglePassSEODocumentParser extracts calculation variants, text, links, and calculation presence."""
    parser = SinglePassSEODocumentParser()
    sample_html = (
        "<!DOCTYPE html><html><body>"
        '<div class="calculation-variant" data-variant-id="variant-sole-prop" id="variant-sole-prop">'
        "  <h3>Sole Proprietorship Calculation</h3>"
        "  <p>Deduction = revenue * 0.20 = $20,000</p>"
        '  <a href="#variant-scorp">Compare S-Corp</a>'
        "</div>"
        '<div class="calculation-variant" data-variant-id="variant-scorp" id="variant-scorp">'
        "  <h3>S-Corporation Calculation</h3>"
        "  <p>Deduction = salary * 0.15 = $15,000</p>"
        '  <a href="#variant-sole-prop">Compare Sole Prop</a>'
        "</div>"
        "</body></html>"
    )
    parser.feed(sample_html)
    assert len(parser.calculation_variants) == 2
    v1 = parser.calculation_variants[0]
    assert v1["id"] == "variant-sole-prop"
    assert v1["has_calculation"] is True
    assert "#variant-scorp" in v1["outgoing_links"]

    v2 = parser.calculation_variants[1]
    assert v2["id"] == "variant-scorp"
    assert v2["has_calculation"] is True
    assert "#variant-sole-prop" in v2["outgoing_links"]


def test_verify_html_organic_fan_out_coverage_helper():
    """Verifies verify_html_organic_fan_out_coverage returns PASS on compliant HTML and FAIL with issues on non-compliant HTML."""
    compliant_html = (
        "<!DOCTYPE html><html><head><title>Section 179 Fan-Out Analysis</title></head><body>"
        "<h1>Section 179 Fan-Out Analysis and Calculation Variants</h1>"
        "<p>This comprehensive technical guide evaluates the full spectrum of equipment expense elections, "
        "addressing primary and secondary intent queries to eliminate thin page fragmentation across multi-intent search queries. "
        "Taxpayers must account for equipment acquisition dates, bonus depreciation phaseouts, and aggregate expenditure thresholds "
        "to optimize their total federal tax deductions under 26 U.S.C. Section 179.</p>"
        "<h2>How does the phaseout threshold affect large capital investments?</h2>"
        "<p>When business equipment purchases surpass the initial $3,050,000 investment ceiling, the allowable expensing limit "
        "reduces dollar for dollar until the deduction is completely phased out at the statutory expenditure threshold.</p>"
        "<h2>What are the eligible property categories for immediate expensing?</h2>"
        "<p>Eligible property includes machinery, computers, software, office furniture, business vehicles, and certain qualified improvement "
        "property deployed within the fiscal year according to current statutory guidelines.</p>"
        '<div class="calculation-variant" data-variant-id="variant-machinery" id="variant-machinery">'
        "  <h3>Machinery Calculation Variant</h3>"
        "  <p>Formula: total_investment * 1.0 = $500,000 first year expensing deduction.</p>"
        '  <p>Cross link to alternative: <a href="#variant-software">Compare with Software Variant</a></p>'
        "</div>"
        '<div class="calculation-variant" data-variant-id="variant-software" id="variant-software">'
        "  <h3>Off-the-Shelf Software Calculation Variant</h3>"
        "  <p>Formula: license_cost * 1.0 = $150,000 immediate write-off deduction.</p>"
        '  <p>Cross link to alternative: <a href="#variant-machinery">Compare with Machinery Variant</a></p>'
        "</div>"
        "</body></html>"
    )
    res_pass = verify_html_organic_fan_out_coverage(compliant_html)
    assert res_pass["status"] == "PASS"
    assert res_pass["violations_count"] == 0
    assert res_pass["subqueries_count"] >= 2
    assert res_pass["calculation_variants_count"] >= 2
    assert res_pass["cross_links_count"] >= 2
    assert res_pass["orphaned_nodes_count"] == 0

    # Non-compliant HTML: shallow question + orphaned calculation variant
    failing_html = (
        "<!DOCTYPE html><html><body>"
        "<h1>Thin Page</h1>"
        "<h2>What is it?</h2>"
        "<p>Short.</p>"
        '<div class="calculation-variant" id="var-1">'
        "  <h3>Variant 1</h3>"
        "  <p>No math here.</p>"
        "</div>"
        "</body></html>"
    )
    res_fail = verify_html_organic_fan_out_coverage(failing_html)
    assert res_fail["status"] == "FAIL"
    assert res_fail["violations_count"] > 0
    assert any("Thin fan-out page detected" in i for i in res_fail["issues"])


def test_check_organic_fan_out_coverage_gate_synthetic_fixtures(tmp_path):
    """Verifies check_organic_fan_out_coverage_gate handles positive and negative fixture directories."""
    pos_dir = tmp_path / "pos_dist"
    pos_dir.mkdir()
    compliant_page = (
        "<!DOCTYPE html><html><head><title>Section 179 Fan-Out Analysis</title></head><body>"
        "<h1>Section 179 Fan-Out Analysis and Calculation Variants</h1>"
        "<p>This comprehensive technical guide evaluates the full spectrum of equipment expense elections, "
        "addressing primary and secondary intent queries to eliminate thin page fragmentation across multi-intent search queries. "
        "Taxpayers must account for equipment acquisition dates, bonus depreciation phaseouts, and aggregate expenditure thresholds "
        "to optimize their total federal tax deductions under 26 U.S.C. Section 179.</p>"
        "<h2>How does the phaseout threshold affect large capital investments?</h2>"
        "<p>When business equipment purchases surpass the initial $3,050,000 investment ceiling, the allowable expensing limit "
        "reduces dollar for dollar until the deduction is completely phased out at the statutory expenditure threshold.</p>"
        "<h2>What are the eligible property categories for immediate expensing?</h2>"
        "<p>Eligible property includes machinery, computers, software, office furniture, business vehicles, and certain qualified improvement "
        "property deployed within the fiscal year according to current statutory guidelines.</p>"
        '<div class="calculation-variant" data-variant-id="v-1" id="v-1">'
        "  <h3>Variant 1</h3>"
        "  <p>Calculation: $100 * 10 = $1,000 deduction.</p>"
        '  <a href="#v-2">Go to Variant 2</a>'
        "</div>"
        '<div class="calculation-variant" data-variant-id="v-2" id="v-2">'
        "  <h3>Variant 2</h3>"
        "  <p>Calculation: $200 * 10 = $2,000 deduction.</p>"
        '  <a href="#v-1">Go to Variant 1</a>'
        "</div>"
        "</body></html>"
    )
    (pos_dir / "index.html").write_text(compliant_page, encoding="utf-8")

    verifier = MasterSEOVerifier(dist_dir=pos_dir)
    res_pos = verifier.check_organic_fan_out_coverage_gate(pos_dir)
    assert res_pos["status"] == "PASS"
    assert res_pos["pages_checked"] == 1
    assert res_pos["violations_count"] == 0

    # Negative directory
    neg_dir = tmp_path / "neg_dist"
    neg_dir.mkdir()
    failing_page = (
        "<!DOCTYPE html><html><body>"
        "<h1>Thin Page</h1>"
        "<h2>What is this?</h2>"
        "<p>A quick answer.</p>"
        '<div class="calculation-variant" id="v-unlinked">'
        "  <h3>Orphaned Variant</h3>"
        "  <p>No math and no links.</p>"
        "</div>"
        "</body></html>"
    )
    (neg_dir / "index.html").write_text(failing_page, encoding="utf-8")
    res_neg = verifier.check_organic_fan_out_coverage_gate(neg_dir)
    assert res_neg["status"] == "FAIL"
    assert res_neg["violations_count"] > 0


def test_gate_aliases_and_checklist_integration_factor5(tmp_path):
    """Verifies Factor 5 gate aliases and audit_seo_checklist integration."""
    compliant_page = (
        "<!DOCTYPE html><html><head><title>Section 179 Fan-Out Analysis</title></head><body>"
        "<h1>Section 179 Fan-Out Analysis and Calculation Variants</h1>"
        "<p>This comprehensive technical guide evaluates the full spectrum of equipment expense elections, "
        "addressing primary and secondary intent queries to eliminate thin page fragmentation across multi-intent search queries. "
        "Taxpayers must account for equipment acquisition dates, bonus depreciation phaseouts, and aggregate expenditure thresholds "
        "to optimize their total federal tax deductions under 26 U.S.C. Section 179.</p>"
        "<h2>How does the phaseout threshold affect large capital investments?</h2>"
        "<p>When business equipment purchases surpass the initial $3,050,000 investment ceiling, the allowable expensing limit "
        "reduces dollar for dollar until the deduction is completely phased out at the statutory expenditure threshold.</p>"
        "<h2>What are the eligible property categories for immediate expensing?</h2>"
        "<p>Eligible property includes machinery, computers, software, office furniture, business vehicles, and certain qualified improvement "
        "property deployed within the fiscal year according to current statutory guidelines.</p>"
        '<div class="calculation-variant" data-variant-id="v-1" id="v-1">'
        "  <h3>Variant 1</h3>"
        "  <p>Calculation: $100 * 10 = $1,000 deduction.</p>"
        '  <a href="#v-2">Go to Variant 2</a>'
        "</div>"
        '<div class="calculation-variant" data-variant-id="v-2" id="v-2">'
        "  <h3>Variant 2</h3>"
        "  <p>Calculation: $200 * 10 = $2,000 deduction.</p>"
        '  <a href="#v-1">Go to Variant 1</a>'
        "</div>"
        "</body></html>"
    )
    dist = tmp_path / "dist_factor5_integration"
    dist.mkdir()
    (dist / "index.html").write_text(compliant_page, encoding="utf-8")

    verifier = MasterSEOVerifier(dist_dir=dist)

    # Verifier method aliases
    r1 = verifier.check_organic_fan_out_coverage_gate(dist)
    r2 = verifier.check_fan_out_coverage_gate(dist)
    r3 = verifier.check_organic_fan_out_gate(dist)
    r4 = verifier.verify_organic_fan_out_coverage(dist)
    assert r1["status"] == r2["status"] == r3["status"] == r4["status"] == "PASS"

    # Module-level alias functions
    m1 = check_organic_fan_out_coverage_gate(dist)
    m2 = check_fan_out_coverage_gate(dist)
    m3 = check_organic_fan_out_gate(dist)
    m4 = verify_organic_fan_out_coverage(dist)
    assert m1["status"] == m2["status"] == m3["status"] == m4["status"] == "PASS"

    # Checklist gates inclusion
    audit_res = verifier.audit_seo_checklist(dist, enforce_relevance=False)
    assert "check_organic_fan_out_coverage_gate" in audit_res["gates"]
    assert audit_res["gates"]["check_organic_fan_out_coverage_gate"]["status"] == "PASS"


# =============================================================================
# Factor 6: Organic Search Ranking (+1.89) Tests
# =============================================================================


def test_zyppy_2026_ai_factors_spec_factor6():
    """Verifies Factor 6: Organic Search Ranking is properly registered in ZYPPY_2026_AI_FACTORS_SPEC."""
    assert len(ZYPPY_2026_AI_FACTORS_SPEC) == 14

    # Factor 6 (index 5) must be Organic Search Ranking with weight 1.89
    f6 = ZYPPY_2026_AI_FACTORS_SPEC[5]
    assert f6["code"] == "organic_search_ranking"
    assert "Organic Search Ranking" in (f6["name"], f6["factor"])
    assert f6["weight"] == 1.89
    assert f6["positive_weight"] == 1.89
    assert f6["negative_weight"] == -1.89
    assert "core seo hygiene" in f6["description"].lower()

    # Weights must be monotonic non-increasing across all 14 factors
    weights = [f["weight"] for f in ZYPPY_2026_AI_FACTORS_SPEC]
    assert weights == sorted(weights, reverse=True)

    # Lookup by 1-indexed position
    spec_by_idx = get_ai_factor_spec(6)
    assert spec_by_idx is not None
    assert spec_by_idx["code"] == "organic_search_ranking"

    # Lookup by code and aliases
    assert get_ai_factor_spec("organic_search_ranking") is f6
    assert get_ai_factor_spec("organic-search-ranking") is f6
    assert get_ai_factor_spec("Organic Search Ranking") is f6
    assert get_ai_factor_spec("organic_search_authority") is f6
    assert get_ai_factor_spec("Organic Search Authority & Traditional Rank") is f6
    assert get_ai_factor_spec("organic_search") is f6
    assert get_ai_factor_spec("traditional_rank") is f6
    assert get_ai_factor_spec("core_seo_hygiene") is f6

    # Re-exports
    assert seo_verifier.ZYPPY_2026_AI_FACTORS_SPEC is ZYPPY_2026_AI_FACTORS_SPEC
    assert pseofactory.ZYPPY_2026_AI_FACTORS_SPEC is ZYPPY_2026_AI_FACTORS_SPEC


def test_assert_organic_search_title_boundaries():
    """Verifies assert_organic_search_title enforces 30-65 character envelope, no double pipes, and anti-slop."""
    # Under 30 chars (29 chars) fails
    short_title = "X" * 29
    with pytest.raises(ValueError, match="under 30-char threshold"):
        assert_organic_search_title(short_title)

    # Exactly 30 chars passes
    title_30 = "X" * 30
    assert assert_organic_search_title(title_30) is True

    # Exactly 65 chars passes
    title_65 = "X" * 65
    assert assert_organic_search_title(title_65) is True

    # Over 65 chars (66 chars) fails
    title_66 = "X" * 66
    with pytest.raises(ValueError, match="exceeds 65-char threshold"):
        assert_organic_search_title(title_66)

    # Extraction from HTML <title> tag
    html_title = f'<html><head><title>{"A" * 45}</title></head></html>'
    assert assert_organic_search_title(html_title) is True

    # Missing <title> tag in HTML
    with pytest.raises(ValueError, match="Empty <title> tag detected"):
        assert_organic_search_title("<html><head><title></title></head></html>")

    # Double pipe formatting corruption
    corrupt_title = "Valid Title Length For Page | | Brand Suffix"
    with pytest.raises(ValueError, match="Double pipe"):
        assert_organic_search_title(corrupt_title)

    # Forbidden dashes
    with pytest.raises(ValueError, match="Forbidden em-dash"):
        assert_organic_search_title(f'{"Valid Title " * 3}\u2014 Brand')

    with pytest.raises(ValueError, match="Forbidden en-dash"):
        assert_organic_search_title(f'{"Valid Title " * 3}\u2013 Brand')


def test_assert_single_h1_hierarchy_boundaries():
    """Verifies assert_single_h1_hierarchy enforces exactly one non-empty H1 and rejects empty headings."""
    # Valid single H1
    valid_html = "<html><body><h1>Comprehensive Section 179 Guide</h1><p>Body content</p></body></html>"
    assert assert_single_h1_hierarchy(valid_html) is True

    # Missing H1
    with pytest.raises(ValueError, match="Missing <h1> tag"):
        assert_single_h1_hierarchy("<html><body><h2>Subheading Only</h2><p>Body</p></body></html>")

    # Multiple H1s
    multi_h1 = "<html><body><h1>First Heading</h1><h1>Second Heading</h1></body></html>"
    with pytest.raises(ValueError, match="Multiple <h1> tags"):
        assert_single_h1_hierarchy(multi_h1)

    # Empty H1
    empty_h1 = "<html><body><h1>   </h1><p>Body</p></body></html>"
    with pytest.raises(ValueError, match="Empty <h1> tag"):
        assert_single_h1_hierarchy(empty_h1)

    # Empty heading container (h2)
    empty_h2 = "<html><body><h1>Main Heading</h1><h2></h2><p>Body</p></body></html>"
    with pytest.raises(ValueError, match="Empty heading container"):
        assert_single_h1_hierarchy(empty_h2)

    # Forbidden dash
    with pytest.raises(ValueError, match="Forbidden em-dash"):
        assert_single_h1_hierarchy("<html><body><h1>Heading with \u2014 dash</h1></body></html>")


def test_assert_organic_search_meta_description_boundaries():
    """Verifies assert_organic_search_meta_description enforces 70-160 character envelope and anti-slop."""
    # Under 70 chars (69 chars) fails
    short_desc = "X" * 69
    with pytest.raises(ValueError, match="under 70-char threshold"):
        assert_organic_search_meta_description(short_desc)

    # Exactly 70 chars passes
    desc_70 = "X" * 70
    assert assert_organic_search_meta_description(desc_70) is True

    # Exactly 160 chars passes
    desc_160 = "X" * 160
    assert assert_organic_search_meta_description(desc_160) is True

    # Over 160 chars (161 chars) fails
    desc_161 = "X" * 161
    with pytest.raises(ValueError, match="exceeds 160-char threshold"):
        assert_organic_search_meta_description(desc_161)

    # HTML meta tag extraction
    html_desc = f'<html><head><meta name="description" content="{"A" * 100}"></head></html>'
    assert assert_organic_search_meta_description(html_desc) is True

    # Reverse attribute order in meta tag
    html_desc_rev = f'<html><head><meta content="{"B" * 100}" name="description"></head></html>'
    assert assert_organic_search_meta_description(html_desc_rev) is True

    # Missing meta description
    with pytest.raises(ValueError, match="Missing meta description"):
        assert_organic_search_meta_description("<html><head><title>No Description</title></head></html>")

    # Mid-number ellipsis truncation
    trunc_desc = "Calculate tax savings under section 179 depreciation where ceiling is $1,220,... for year"
    with pytest.raises(ValueError, match="Mid-number ellipsis truncation"):
        assert_organic_search_meta_description(trunc_desc)

    # Forbidden dash
    with pytest.raises(ValueError, match="Forbidden en-dash"):
        assert_organic_search_meta_description(f'{"Valid description text " * 4}\u2013 end')


def test_assert_canonical_consistency_boundaries():
    """Verifies assert_canonical_consistency enforces HTTPS, URL normalization, and drift prevention."""
    valid_canonical = "https://profithelm.com/tools/section-179-calculator/"
    assert assert_canonical_consistency(
        valid_canonical,
        expected_route_or_url="/tools/section-179-calculator/",
        base_domain="profithelm.com",
    ) is True

    # Missing canonical tag in HTML
    with pytest.raises(ValueError, match="Missing canonical link tag"):
        assert_canonical_consistency("<html><head><title>Clean Title Here With Enough Characters</title></head></html>")

    # Non-HTTPS URL
    with pytest.raises(ValueError, match="not an absolute HTTPS URL"):
        assert_canonical_consistency("http://profithelm.com/tools/")

    # Duplicate slashes in path
    with pytest.raises(ValueError, match="duplicate slashes"):
        assert_canonical_consistency("https://profithelm.com//tools/calc/")

    # Query parameters
    with pytest.raises(ValueError, match="query parameters"):
        assert_canonical_consistency("https://profithelm.com/tools/calc/?utm_source=google")

    # Hash fragment
    with pytest.raises(ValueError, match="hash fragment"):
        assert_canonical_consistency("https://profithelm.com/tools/calc/#section")

    # Relative path traversal
    with pytest.raises(ValueError, match="relative path traversal"):
        assert_canonical_consistency("https://profithelm.com/tools/../calc/")

    # Uppercase path characters
    with pytest.raises(ValueError, match="uppercase characters"):
        assert_canonical_consistency("https://profithelm.com/Tools/Calc/")

    # Domain drift
    with pytest.raises(ValueError, match="drifts from expected domain"):
        assert_canonical_consistency(
            "https://otherdomain.com/tools/calc/",
            base_domain="profithelm.com",
        )

    # Path drift
    with pytest.raises(ValueError, match="Canonical path drift"):
        assert_canonical_consistency(
            "https://profithelm.com/tools/calc/",
            expected_route_or_url="/tools/depreciation/",
        )


def test_assert_internal_links_integrity_boundaries():
    """Verifies assert_internal_links_integrity detects broken links, missing anchors, and dead routes."""
    known_routes = {"/", "/tools/", "/tools/calc/", "/about/"}

    # Valid internal links and valid anchor
    valid_html = (
        '<html><body>'
        '<a href="/tools/calc/">Calculator</a>'
        '<a href="#faq">FAQ Section</a>'
        '<a href="https://external.gov">Government Resource</a>'
        '<a href="mailto:support@profithelm.com">Email Us</a>'
        '<div id="faq"><h3>Frequently Asked Questions</h3></div>'
        '</body></html>'
    )
    assert assert_internal_links_integrity(valid_html, known_routes=known_routes, current_route="/") is True

    # Empty href attribute
    with pytest.raises(ValueError, match="Empty href attribute"):
        assert_internal_links_integrity('<html><body><a href="">Empty Link</a></body></html>')

    # Dead javascript: route
    with pytest.raises(ValueError, match="Dead link route"):
        assert_internal_links_integrity('<html><body><a href="javascript:void(0)">Click Here</a></body></html>')

    # Broken in-page anchor
    with pytest.raises(ValueError, match="Broken internal anchor link"):
        assert_internal_links_integrity('<html><body><a href="#nonexistent">Go To</a></body></html>')

    # Broken internal link to dead route
    with pytest.raises(ValueError, match="Broken internal link to dead route"):
        assert_internal_links_integrity(
            '<html><body><a href="/tools/missing-page/">Dead Route</a></body></html>',
            known_routes=known_routes,
            current_route="/",
        )

    # Relative path traversal across deeply nested routes
    nested_html = '<html><body><a href="../calc/">To Calc</a></body></html>'
    assert assert_internal_links_integrity(
        nested_html,
        known_routes=known_routes,
        current_route="/tools/subtool/",
    ) is True


def test_assert_ssr_response_latency_boundaries():
    """Verifies assert_ssr_response_latency enforces sub-100ms response benchmarks."""
    # Under 100ms passes
    assert assert_ssr_response_latency(24.5) is True
    assert assert_ssr_response_latency(99.9) is True

    # 100.0ms or greater fails
    with pytest.raises(ValueError, match="latency regression"):
        assert_ssr_response_latency(100.0)

    with pytest.raises(ValueError, match="latency regression"):
        assert_ssr_response_latency(145.2)

    # Non-numeric fails
    with pytest.raises(ValueError, match="numeric value"):
        assert_ssr_response_latency("fast")  # type: ignore


def test_assert_organic_search_ranking_master_contract():
    """Verifies assert_organic_search_ranking master contract and its aliases."""
    compliant_html = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>Section 179 Calculator and Tax Guide for 2026</title>'
        '<meta name="description" content="Calculate your 2026 Section 179 equipment deduction limits, bonus depreciation phaseouts, and tax write-offs with statutory precision.">'
        '<link rel="canonical" href="https://profithelm.com/tools/section-179/">'
        '</head><body>'
        '<h1>Section 179 Deduction Limits and Equipment Rules</h1>'
        '<p>Detailed statutory analysis under 26 U.S.C. Section 179.</p>'
        '<a href="/tools/">Back to Tools</a>'
        '<a href="#details">Jump to Details</a>'
        '<div id="details"><p>Phaseout begins at $3,050,000 threshold.</p></div>'
        '</body></html>'
    )
    known_routes = {"/", "/tools/", "/tools/section-179/"}

    assert assert_organic_search_ranking(
        compliant_html,
        current_route="/tools/section-179/",
        known_routes=known_routes,
        base_domain="profithelm.com",
        ssr_latency_ms=15.0,
    ) is True

    # Aliases
    assert assert_traditional_organic_search_ranking(
        compliant_html,
        current_route="/tools/section-179/",
        known_routes=known_routes,
        base_domain="profithelm.com",
        ssr_latency_ms=15.0,
    ) is True

    assert assert_core_seo_hygiene(
        compliant_html,
        current_route="/tools/section-179/",
        known_routes=known_routes,
        base_domain="profithelm.com",
        ssr_latency_ms=15.0,
    ) is True

    # Failure mode: Title too short
    failing_title = compliant_html.replace(
        "Section 179 Calculator and Tax Guide for 2026",
        "Short Title"
    )
    with pytest.raises(ValueError, match="under 30-char threshold"):
        assert_organic_search_ranking(failing_title, current_route="/tools/section-179/")


def test_mock_search_engine_crawler_simulation():
    """Verifies MockSearchEngineCrawler and simulate_crawler_traversal across multi-page graph."""
    crawler = MockSearchEngineCrawler(base_domain="profithelm.com", max_ssr_latency_ms=100.0)

    # Compliant multi-page static site
    pages_pass = {
        "/": (
            '<!DOCTYPE html><html lang="en"><head>'
            '<title>ProfitHelm Platform Programmatic SEO Directory</title>'
            '<meta name="description" content="Comprehensive programmatic tax calculation tools, depreciation modeling, and statutory equipment write-off calculators for businesses.">'
            '<link rel="canonical" href="https://profithelm.com/">'
            '</head><body>'
            '<h1>ProfitHelm Programmatic Calculation Substrate</h1>'
            '<p>Explore verified statutory tools.</p>'
            '<a href="/tools/calc/">Go to Calculator</a>'
            '</body></html>'
        ),
        "/tools/calc/": (
            '<!DOCTYPE html><html lang="en"><head>'
            '<title>Section 179 Equipment Expensing Calculator</title>'
            '<meta name="description" content="Calculate your 2026 Section 179 equipment deduction limits, bonus depreciation phaseouts, and tax write-offs with statutory precision.">'
            '<link rel="canonical" href="https://profithelm.com/tools/calc/">'
            '</head><body>'
            '<h1>Section 179 Equipment Expensing Calculator</h1>'
            '<p>Statutory calculation engine for capital expensing.</p>'
            '<a href="/">Back to Home</a>'
            '<a href="#results">Results</a>'
            '<div id="results"><p>Results displayed here.</p></div>'
            '</body></html>'
        ),
    }

    res_pass = crawler.crawl_pages(pages_pass)
    assert res_pass["status"] == "PASS"
    assert res_pass["violations_count"] == 0
    assert res_pass["pages_crawled"] == 2
    assert res_pass["internal_links_verified"] >= 2

    # Convenience function check
    res_conv = simulate_crawler_traversal(pages_pass, base_domain="profithelm.com")
    assert res_conv["status"] == "PASS"

    # Non-compliant multi-page site with multiple edge cases
    pages_fail = {
        "/": (
            '<!DOCTYPE html><html lang="en"><head>'
            '<title>Too Short</title>'
            '<meta name="description" content="Short">'
            '<link rel="canonical" href="http://profithelm.com/">'
            '</head><body>'
            '<h1>Home</h1>'
            '<a href="/dead-link/">Broken Link</a>'
            '</body></html>'
        ),
        "/dead-page/": (
            '<!DOCTYPE html><html lang="en"><head>'
            '<title>Title Length Is Actually Compliant For This Page</title>'
            '<meta name="description" content="This is a valid meta description length with enough characters to pass the seventy character boundary easily.">'
            '<link rel="canonical" href="https://wrongdomain.com/dead-page/">'
            '</head><body>'
            '<h1>First H1</h1><h1>Second Duplicate H1</h1>'
            '<a href="#nonexistent">Bad Anchor</a>'
            '</body></html>'
        ),
    }

    res_fail = crawler.crawl_pages(pages_fail)
    assert res_fail["status"] == "FAIL"
    assert res_fail["violations_count"] >= 5
    assert any("under 30-char threshold" in i for i in res_fail["issues"])
    assert any("under 70-char threshold" in i for i in res_fail["issues"])
    assert any("Broken internal link to dead route" in i for i in res_fail["issues"])
    assert any("Multiple <h1> tags" in i for i in res_fail["issues"])
    assert any("drifts from expected domain" in i for i in res_fail["issues"])


def test_check_organic_search_ranking_gate_synthetic_fixtures(tmp_path):
    """Verifies check_organic_search_ranking_gate on disk fixtures across deeply nested routes."""
    pos_dir = tmp_path / "pos_dist"
    pos_dir.mkdir()
    nested_dir = pos_dir / "nested" / "tools"
    nested_dir.mkdir(parents=True)

    page_root = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>ProfitHelm Platform Programmatic SEO Directory</title>'
        '<meta name="description" content="Comprehensive programmatic tax calculation tools, depreciation modeling, and statutory equipment write-off calculators for businesses.">'
        '<link rel="canonical" href="https://profithelm.com/">'
        '</head><body>'
        '<h1>ProfitHelm Programmatic Calculation Substrate</h1>'
        '<a href="/nested/tools/">Go to Nested Tool</a>'
        '</body></html>'
    )
    (pos_dir / "index.html").write_text(page_root, encoding="utf-8")

    page_nested = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>Nested Section 179 Equipment Expensing Tool</title>'
        '<meta name="description" content="Calculate your 2026 Section 179 equipment deduction limits, bonus depreciation phaseouts, and tax write-offs with statutory precision.">'
        '<link rel="canonical" href="https://profithelm.com/nested/tools/">'
        '</head><body>'
        '<h1>Nested Section 179 Expensing Calculator</h1>'
        '<a href="/">Back to Home</a>'
        '</body></html>'
    )
    (nested_dir / "index.html").write_text(page_nested, encoding="utf-8")

    verifier = MasterSEOVerifier(dist_dir=pos_dir, domain="profithelm.com")
    res_pos = verifier.check_organic_search_ranking_gate(pos_dir)
    assert res_pos["status"] == "PASS"
    assert res_pos["pages_crawled"] == 2
    assert res_pos["violations_count"] == 0

    # Negative directory fixture
    neg_dir = tmp_path / "neg_dist"
    neg_dir.mkdir()
    failing_page = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>Short</title>'
        '<meta name="description" content="Short description">'
        '<link rel="canonical" href="https://profithelm.com//double//slash/">'
        '</head><body>'
        '<h1>First H1</h1><h1>Second H1</h1>'
        '<a href="/nowhere/">Dead Link</a>'
        '</body></html>'
    )
    (neg_dir / "index.html").write_text(failing_page, encoding="utf-8")

    verifier_neg = MasterSEOVerifier(dist_dir=neg_dir, domain="profithelm.com")
    res_neg = verifier_neg.check_organic_search_ranking_gate(neg_dir)
    assert res_neg["status"] == "FAIL"
    assert res_neg["violations_count"] >= 4
    assert any("under 30-char threshold" in i for i in res_neg["issues"])
    assert any("under 70-char threshold" in i for i in res_neg["issues"])
    assert any("Multiple <h1> tags" in i for i in res_neg["issues"])
    assert any("duplicate slashes" in i for i in res_neg["issues"])
    assert any("Broken internal link" in i for i in res_neg["issues"])


def test_gate_aliases_and_checklist_integration_factor6(tmp_path):
    """Verifies Factor 6 gate aliases and audit_seo_checklist integration."""
    compliant_page = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>Section 179 Calculation Analysis for Fiscal 2026</title>'
        '<meta name="description" content="Comprehensive technical guide evaluating the full spectrum of equipment expense elections, addressing primary and secondary intent queries.">'
        '<link rel="canonical" href="https://profithelm.com/">'
        '</head><body>'
        '<h1>Section 179 Expensing and Bonus Depreciation</h1>'
        '<p>Under 26 U.S.C. Section 179, taxpayers may expense up to $1,220,000.</p>'
        '</body></html>'
    )
    dist = tmp_path / "dist_factor6_integration"
    dist.mkdir()
    (dist / "index.html").write_text(compliant_page, encoding="utf-8")

    verifier = MasterSEOVerifier(dist_dir=dist, domain="profithelm.com")

    # Verifier method aliases
    r1 = verifier.check_organic_search_ranking_gate(dist)
    r2 = verifier.check_traditional_organic_search_gate(dist)
    r3 = verifier.check_core_seo_hygiene_gate(dist)
    r4 = verifier.verify_organic_search_ranking(dist)
    assert r1["status"] == r2["status"] == r3["status"] == r4["status"] == "PASS"

    # Module-level alias functions
    m1 = check_organic_search_ranking_gate(dist)
    m2 = check_traditional_organic_search_gate(dist)
    m3 = check_core_seo_hygiene_gate(dist)
    m4 = verify_organic_search_ranking(dist)
    assert m1["status"] == m2["status"] == m3["status"] == m4["status"] == "PASS"

    # In-memory HTML helper
    h_res = verify_html_organic_search_ranking(
        compliant_page,
        base_domain="profithelm.com",
    )
    assert h_res["status"] == "PASS"
    assert h_res["violations_count"] == 0

    # Checklist gates inclusion
    audit_res = verifier.audit_seo_checklist(dist, enforce_relevance=False)
    assert "check_organic_search_ranking_gate" in audit_res["gates"]
    assert audit_res["gates"]["check_organic_search_ranking_gate"]["status"] == "PASS"


# =============================================================================
# Factor 7: Unique / First-Party Information (+1.85) Unit Tests
# =============================================================================

def test_factor7_spec_and_query_retrieval():
    """Verifies Factor 7 specification, weights, and query retrieval by code, name, and aliases."""
    spec_idx = get_ai_factor_spec(7)
    assert spec_idx is not None
    assert spec_idx["code"] == "unique_first_party_information"
    assert spec_idx["name"] == "Unique First-Party Information"
    assert spec_idx["weight"] == 1.85
    assert spec_idx["positive_weight"] == 1.85
    assert spec_idx["negative_weight"] == -1.85

    queries = [
        "unique_first_party_information",
        "Unique First-Party Information",
        "Unique / First-Party Information",
        "first_party_information",
        "unique_information",
        "proprietary_models",
        "multi_dataset_enrichment",
        "firsthand_calculations",
        "calculation_manifests",
        "first_party_assets",
    ]
    for q in queries:
        spec = get_ai_factor_spec(q)
        assert spec is not None, f"Failed to retrieve Factor 7 spec for query: {q}"
        assert spec["code"] == "unique_first_party_information"
        assert spec["weight"] == 1.85


def test_safe_eval_mathematical_formula():
    """Verifies safe AST mathematical formula evaluation across arithmetic operations and bounds."""
    # 1. Standard arithmetic
    f1 = "(cost - threshold) * rate"
    inp1 = {"cost": 3500000, "threshold": 3130000, "rate": 0.20}
    res1 = safe_eval_mathematical_formula(f1, inp1)
    assert abs(res1 - 74000.0) < 1e-4

    # 2. Percentage notation and dollar signs
    f2 = "cost * 20% + bonus"
    inp2 = {"cost": "$500,000", "bonus": "$10,000"}
    res2 = safe_eval_mathematical_formula(f2, inp2)
    assert abs(res2 - 110000.0) < 1e-4

    # 3. Built-in functions: min, max, round, abs
    f3 = "min(cost, cap) - phaseout"
    inp3 = {"cost": 500000, "cap": 1220000, "phaseout": 0}
    assert abs(safe_eval_mathematical_formula(f3, inp3) - 500000.0) < 1e-4

    f4 = "max(a, b) + round(c, 2)"
    inp4 = {"a": 10.5, "b": 25.2, "c": 3.14159}
    assert abs(safe_eval_mathematical_formula(f4, inp4) - 28.34) < 1e-4

    # 4. Error handling: division by zero
    with pytest.raises(ZeroDivisionError, match="Division by zero"):
        safe_eval_mathematical_formula("cost / divisor", {"cost": 100, "divisor": 0})

    # 5. Error handling: unknown variable
    with pytest.raises(ValueError, match="unknown variable 'missing_var'"):
        safe_eval_mathematical_formula("cost + missing_var", {"cost": 100})

    # 6. Error handling: empty formula
    with pytest.raises(ValueError, match="non-empty string"):
        safe_eval_mathematical_formula("", {"cost": 100})


def test_assert_proprietary_model_integrity():
    """Verifies proprietary model integrity asserting inputs match published outputs."""
    formula = "min(equipment_cost, deduction_cap) - phaseout"
    inputs = {"equipment_cost": 500000, "deduction_cap": 1220000, "phaseout": 0}

    # Compliant match
    assert assert_proprietary_model_integrity(
        inputs,
        published_output=500000,
        formula=formula,
    )

    # Compliant match with currency formatting in output
    assert assert_proprietary_model_integrity(
        inputs,
        published_output="$500,000",
        formula=formula,
    )

    # Mismatch raises ValueError with explicit diff
    with pytest.raises(ValueError, match="Proprietary model input/output mismatch"):
        assert_proprietary_model_integrity(
            inputs,
            published_output=450000,
            formula=formula,
        )

    # Direct manifest dictionary evaluation
    manifest = {
        "formula": "cost * rate",
        "inputs": {"cost": 100000, "rate": 0.25},
        "published_output": 25000,
    }
    assert assert_proprietary_model_integrity(manifest)


def test_assert_unique_calculation_manifest():
    """Verifies boundary conditions for unique calculation manifest schema enforcement."""
    valid_manifest = {
        "manifest_id": "section-179-accelerated-engine",
        "model_name": "Section 179 Accelerated Depreciation Engine",
        "formula": "min(equipment_cost, deduction_cap)",
        "inputs": {"equipment_cost": 500000, "deduction_cap": 1220000},
        "published_output": 500000,
        "sample_calculation": "Under IRC Section 179, $500,000 purchase is fully expensed in Year 1.",
        "statutory_authority": "26 U.S.C. Section 179",
        "economic_dataset": "BLS Capital Equipment PPI Series",
    }
    assert assert_unique_calculation_manifest(valid_manifest)

    # Missing formula
    bad_manifest = dict(valid_manifest)
    bad_manifest["formula"] = ""
    with pytest.raises(ValueError, match="missing or empty 'formula'"):
        assert_unique_calculation_manifest(bad_manifest)

    # Missing inputs
    bad_manifest = dict(valid_manifest)
    bad_manifest["inputs"] = {}
    with pytest.raises(ValueError, match="missing or empty 'inputs'"):
        assert_unique_calculation_manifest(bad_manifest)

    # Missing sample calculation
    bad_manifest = dict(valid_manifest)
    bad_manifest["sample_calculation"] = ""
    with pytest.raises(ValueError, match="missing or empty 'sample_calculation'"):
        assert_unique_calculation_manifest(bad_manifest)

    # Missing statutory authority
    bad_manifest = dict(valid_manifest)
    bad_manifest["statutory_authority"] = ""
    with pytest.raises(ValueError, match="missing or empty 'statutory_authority'"):
        assert_unique_calculation_manifest(bad_manifest)

    # Missing model name
    bad_manifest = dict(valid_manifest)
    bad_manifest["model_name"] = ""
    with pytest.raises(ValueError, match="missing or empty 'model_name'"):
        assert_unique_calculation_manifest(bad_manifest)

    # Forbidden dash in formula
    bad_manifest = dict(valid_manifest)
    bad_manifest["formula"] = "cost " + chr(0x2014) + " deduction"
    with pytest.raises(ValueError, match="Forbidden em-dash"):
        assert_unique_calculation_manifest(bad_manifest)

    # Model input/output mismatch
    bad_manifest = dict(valid_manifest)
    bad_manifest["published_output"] = 999999
    with pytest.raises(ValueError, match="input/output mismatch"):
        assert_unique_calculation_manifest(bad_manifest)

    # Ungrounded synthetic claims in manifest
    bad_manifest = dict(valid_manifest)
    bad_manifest["sample_calculation"] = "Using our mock dataset, numbers are estimated."
    with pytest.raises(ValueError, match="ungrounded synthetic claims"):
        assert_unique_calculation_manifest(bad_manifest)


def test_assert_multi_dataset_enrichment():
    """Verifies multi-dataset enrichment joining statutory figures with economic data."""
    compliant_text = (
        "Under 26 U.S.C. Section 179 and Internal Revenue Code guidelines, equipment deduction caps "
        "are indexed against inflation benchmarks reported by the Bureau of Labor Statistics (BLS CPI-U) "
        "and Federal Reserve Economic Data (FRED)."
    )
    assert assert_multi_dataset_enrichment(compliant_text)

    # Statutory only without economic dataset
    statutory_only = (
        "Under 26 U.S.C. Section 179, taxpayers may expense qualifying commercial equipment up to statutory caps."
    )
    with pytest.raises(ValueError, match="missing empirical economic dataset series"):
        assert_multi_dataset_enrichment(statutory_only)

    # Economic only without primary statutory provenance
    economic_only = (
        "According to Federal Reserve Economic Data (FRED) and BLS metrics, commercial equipment pricing rose 3.4%."
    )
    with pytest.raises(ValueError, match="missing primary statutory provenance"):
        assert_multi_dataset_enrichment(economic_only)

    # Neither present
    generic_text = "This guide discusses commercial equipment depreciation and common accounting methods."
    with pytest.raises(ValueError, match="strictly requires multi-dataset enrichment"):
        assert_multi_dataset_enrichment(generic_text)

    # Ungrounded synthetic claim rejection
    synthetic_claim = (
        "Under IRC Section 179 and FRED data, we generated mock data for arbitrary estimates not grounded."
    )
    with pytest.raises(ValueError, match="Ungrounded synthetic claim detected"):
        assert_multi_dataset_enrichment(synthetic_claim)

    # Forbidden dash rejection
    dash_text = compliant_text + " " + chr(0x2014) + " additional note"
    with pytest.raises(ValueError, match="Forbidden em-dash"):
        assert_multi_dataset_enrichment(dash_text)


def test_detect_and_assert_orphaned_calculation_tables():
    """Verifies detection of calculation tables missing statutory or economic provenance."""
    compliant_table = (
        '<table data-statutory-provenance="IRC Section 179" data-economic-source="BLS CPI-U">'
        '<tr><th>Asset Tier</th><th>First-Year Deduction</th></tr>'
        '<tr><td>Equipment A</td><td>$150,000</td></tr>'
        '</table>'
    )
    assert len(detect_orphaned_calculation_tables(compliant_table)) == 0
    assert assert_no_orphaned_calculation_tables(compliant_table)

    compliant_caption = (
        '<table>'
        '<caption>Table 1: Statutory Phase-Down Schedule under 26 U.S.C. Section 168(k) and FRED</caption>'
        '<tr><th>Tax Year</th><th>Bonus Rate</th></tr>'
        '<tr><td>2026</td><td>20%</td></tr>'
        '</table>'
    )
    assert len(detect_orphaned_calculation_tables(compliant_caption)) == 0
    assert assert_no_orphaned_calculation_tables(compliant_caption)

    orphaned_table = (
        '<table>'
        '<tr><th>Category</th><th>Estimated Write-Off</th></tr>'
        '<tr><td>Machinery</td><td>$75,000</td></tr>'
        '</table>'
    )
    orphans = detect_orphaned_calculation_tables(orphaned_table)
    assert len(orphans) == 1
    assert "Orphaned calculation table missing statutory or economic provenance" in orphans[0]
    with pytest.raises(ValueError, match="Orphaned calculation tables missing statutory provenance"):
        assert_no_orphaned_calculation_tables(orphaned_table)

    nav_table = (
        '<table>'
        '<tr><th>Menu</th><th>Destination</th></tr>'
        '<tr><td>Home</td><td>Overview</td></tr>'
        '</table>'
    )
    assert len(detect_orphaned_calculation_tables(nav_table)) == 0


def test_assert_no_thin_syndicated_content():
    """Verifies rejection of thin syndicated templates and short boilerplate."""
    short_content = "<p>Short syndicated summary about taxes.</p>"
    with pytest.raises(ValueError, match="Thin syndicated page detected"):
        assert_no_thin_syndicated_content(short_content, min_words=50)

    long_boilerplate = (
        "<p>This syndicated article was originally published on partner network. "
        + " ".join(["More text word"] * 40)
        + "</p>"
    )
    with pytest.raises(ValueError, match="Thin syndicated boilerplate detected"):
        assert_no_thin_syndicated_content(long_boilerplate, min_words=20)


def test_verify_html_unique_first_party_information_in_memory():
    """Verifies in-memory HTML document validation against Factor 7."""
    compliant_html = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>Section 179 First-Party Calculation Engine</title>'
        '<meta name="description" content="Calculate your 2026 Section 179 equipment deductions and bonus depreciation with deterministic precision.">'
        '<script type="application/json" id="calculation-manifest">'
        '{'
        '  "manifest_id": "sec-179-calc",'
        '  "model_name": "Section 179 First-Year Expensing Engine",'
        '  "formula": "min(equipment_cost, deduction_cap)",'
        '  "inputs": {"equipment_cost": 500000, "deduction_cap": 1220000},'
        '  "published_output": 500000,'
        '  "sample_calculation": "Purchase of $500,000 expensed under IRC Section 179.",'
        '  "statutory_authority": "26 U.S.C. Section 179",'
        '  "economic_dataset": "Federal Reserve Economic Data (FRED)"'
        '}'
        '</script>'
        '</head><body>'
        '<h1>Section 179 Equipment Expensing Model</h1>'
        '<div class="quick-answer">Under 26 U.S.C. Section 179, qualifying businesses can deduct up to $1,220,000 in equipment purchases for fiscal year 2026.</div>'
        '<p>Our proprietary model combines statutory phaseout limits under Internal Revenue Code Section 179 with macroeconomic series from Federal Reserve Economic Data (FRED) and BLS CPI-U.</p>'
        '<table data-statutory-provenance="IRC Section 179" data-economic-source="FRED">'
        '<tr><th>Tier</th><th>Threshold</th><th>First-Year Allowance</th></tr>'
        '<tr><td>Baseline</td><td>$3,130,000</td><td>$1,220,000</td></tr>'
        '<tr><td>Example Purchase</td><td>$500,000</td><td>$500,000</td></tr>'
        '</table>'
        '<p>' + " ".join(["Deterministic financial modeling ensures regulatory conformity."] * 25) + '</p>'
        '</body></html>'
    )

    res_pass = verify_html_unique_first_party_information(compliant_html)
    assert res_pass["status"] == "PASS"
    assert res_pass["violations_count"] == 0
    assert res_pass["manifests_count"] >= 1
    assert res_pass["multi_dataset_joins_count"] >= 1

    # Negative 1: Missing calculation manifest and interactive container
    html_no_manifest = (
        '<!DOCTYPE html><html lang="en"><head><title>No Manifest Tool</title></head><body>'
        '<h1>Generic Overview</h1>'
        '<p>Under IRC Section 179 and BLS CPI-U benchmarks, businesses save on capital expenses.</p>'
        '<table data-statutory-source="IRC Section 179"><tr><th>Tier</th><th>Rate</th></tr><tr><td>A</td><td>10%</td></tr></table>'
        '<p>' + " ".join(["Substantive text word"] * 30) + '</p>'
        '</body></html>'
    )
    res_no_manifest = verify_html_unique_first_party_information(html_no_manifest)
    assert res_no_manifest["status"] == "FAIL"
    assert any("Missing firsthand calculation manifest" in i for i in res_no_manifest["issues"])

    # Negative 2: Orphaned calculation table without statutory provenance
    html_orphaned = compliant_html.replace(
        'data-statutory-provenance="IRC Section 179" data-economic-source="FRED"',
        'class="unstyled-table"'
    ).replace(
        'Under 26 U.S.C. Section 179', 'In our calculation'
    ).replace(
        'Internal Revenue Code Section 179', 'our custom schedule'
    )
    res_orphaned = verify_html_unique_first_party_information(html_orphaned)
    assert res_orphaned["status"] == "FAIL"
    assert any("Orphaned calculation table" in i for i in res_orphaned["issues"])

    # Negative 3: Mock dataset claim
    html_mock = compliant_html.replace(
        'Our proprietary model combines',
        'Our proprietary model uses a mock dataset with'
    )
    res_mock = verify_html_unique_first_party_information(html_mock)
    assert res_mock["status"] == "FAIL"
    assert any("Ungrounded synthetic claim" in i for i in res_mock["issues"])

    # Negative 4: Formula output mismatch
    html_mismatch = compliant_html.replace('"published_output": 500000', '"published_output": 888888')
    res_mismatch = verify_html_unique_first_party_information(html_mismatch)
    assert res_mismatch["status"] == "FAIL"
    assert any("Proprietary model input/output mismatch" in i for i in res_mismatch["issues"])

    # Negative 5: Forbidden dash
    html_dash = compliant_html.replace('Section 179 Equipment Expensing Model', 'Section 179 ' + chr(0x2014) + ' Equipment Model')
    res_dash = verify_html_unique_first_party_information(html_dash)
    assert res_dash["status"] == "FAIL"
    assert any("forbidden em-dash" in i for i in res_dash["issues"])


def test_check_unique_first_party_information_gate_disk_fixtures(tmp_path):
    """Verifies check_unique_first_party_information_gate on disk fixtures across nested routes."""
    pos_dir = tmp_path / "pos_dist_factor7"
    pos_dir.mkdir()
    manifests_dir = pos_dir / "manifests"
    manifests_dir.mkdir()
    tools_dir = pos_dir / "tools" / "equipment-depreciation"
    tools_dir.mkdir(parents=True)

    manifest_content = {
        "manifest_id": "equipment-depreciation-model",
        "model_name": "Equipment Depreciation Engine",
        "formula": "min(equipment_cost, deduction_cap)",
        "inputs": {"equipment_cost": 400000, "deduction_cap": 1220000},
        "published_output": 400000,
        "sample_calculation": "Under IRC Section 179, $400,000 expensed.",
        "statutory_authority": "26 U.S.C. Section 179",
        "economic_dataset": "Bureau of Labor Statistics (BLS CPI-U)",
    }
    (manifests_dir / "equipment-depreciation.json").write_text(
        json.dumps(manifest_content), encoding="utf-8"
    )

    page_html = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>Equipment Depreciation Model for 2026 Fiscal Year</title>'
        '<meta name="description" content="Calculate your equipment depreciation limits under 26 U.S.C. Section 179 and BLS economic benchmarks.">'
        '</head><body>'
        '<h1>Section 179 Equipment Depreciation Calculator</h1>'
        '<div class="quick-answer">Businesses can deduct up to $1,220,000 in qualifying equipment purchases in 2026.</div>'
        '<p>Grounded in 26 U.S.C. Section 179 and Bureau of Labor Statistics (BLS CPI-U) economic adjustments.</p>'
        '<table data-statutory-provenance="26 U.S.C. Section 179" data-economic-source="BLS CPI-U">'
        '<tr><th>Tier</th><th>Deduction Limit</th></tr>'
        '<tr><td>Standard</td><td>$1,220,000</td></tr>'
        '</table>'
        '<form class="calculator"><input name="equipment_cost" value="400000"></form>'
        '<p>' + " ".join(["Authoritative quantitative analysis provides deterministic guarantees."] * 25) + '</p>'
        '</body></html>'
    )
    (tools_dir / "index.html").write_text(page_html, encoding="utf-8")

    verifier = MasterSEOVerifier(dist_dir=pos_dir, domain="profithelm.com")
    res_pos = verifier.check_unique_first_party_information_gate(pos_dir)
    assert res_pos["status"] == "PASS"
    assert res_pos["pages_checked"] >= 1
    assert res_pos["violations_count"] == 0

    # Negative directory fixture
    neg_dir = tmp_path / "neg_dist_factor7"
    neg_dir.mkdir()
    neg_tools = neg_dir / "tools" / "bad-calc"
    neg_tools.mkdir(parents=True)
    neg_page = (
        '<!DOCTYPE html><html lang="en"><head><title>Unenriched Page</title></head><body>'
        '<h1>Unenriched Template</h1>'
        '<p>This template lacks firsthand calculations and contains a mock dataset.</p>'
        '<table><tr><th>Col 1</th><th>$5,000</th></tr></table>'
        '</body></html>'
    )
    (neg_tools / "index.html").write_text(neg_page, encoding="utf-8")

    verifier_neg = MasterSEOVerifier(dist_dir=neg_dir, domain="profithelm.com")
    res_neg = verifier_neg.check_unique_first_party_information_gate(neg_dir)
    assert res_neg["status"] == "FAIL"
    assert res_neg["violations_count"] >= 3
    assert any("Ungrounded synthetic claim" in i for i in res_neg["issues"])
    assert any("Orphaned calculation table" in i for i in res_neg["issues"])


def test_gate_aliases_and_checklist_integration_factor7(tmp_path):
    """Verifies Factor 7 gate aliases and audit_seo_checklist integration."""
    pos_dir = tmp_path / "dist_factor7_integration"
    pos_dir.mkdir()
    tool_dir = pos_dir / "tools" / "qbi-deduction"
    tool_dir.mkdir(parents=True)

    compliant_page = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>Section 199A QBI Calculation Model and Planning Engine</title>'
        '<meta name="description" content="Calculate Qualified Business Income deductions under IRC Section 199A with BLS and FRED economic datasets.">'
        '<link rel="canonical" href="https://profithelm.com/tools/qbi-deduction/">'
        '<script type="application/json" id="calculation-manifest">'
        '{'
        '  "manifest_id": "qbi-engine",'
        '  "model_name": "QBI Wage Limitation Optimizer",'
        '  "formula": "qbi * 0.20",'
        '  "inputs": {"qbi": 200000},'
        '  "published_output": 40000,'
        '  "sample_calculation": "20% of $200,000 QBI yields $40,000 deduction.",'
        '  "statutory_authority": "IRC Section 199A",'
        '  "economic_dataset": "Bureau of Labor Statistics (BLS ECI)"'
        '}'
        '</script>'
        '</head><body>'
        '<h1>Section 199A Qualified Business Income Deduction Model</h1>'
        '<div class="quick-answer">Under IRC Section 199A, eligible pass-through business owners may deduct up to 20% of qualified business income.</div>'
        '<p>Our model incorporates statutory wage limits from IRC Section 199A joined with BLS Employment Cost Index (BLS ECI) and Federal Reserve Economic Data (FRED).</p>'
        '<table data-statutory-provenance="IRC Section 199A" data-economic-source="BLS ECI">'
        '<tr><th>Filing Status</th><th>Phase-In Threshold</th></tr>'
        '<tr><td>Single</td><td>$197,300</td></tr>'
        '</table>'
        '<p>' + " ".join(["Deterministic calculation models enable accurate tax optimization."] * 25) + '</p>'
        '</body></html>'
    )
    (tool_dir / "index.html").write_text(compliant_page, encoding="utf-8")

    verifier = MasterSEOVerifier(dist_dir=pos_dir, domain="profithelm.com")

    # Verifier method aliases
    r1 = verifier.check_unique_first_party_information_gate(pos_dir)
    r2 = verifier.check_first_party_information_gate(pos_dir)
    r3 = verifier.check_first_party_assets_gate(pos_dir)
    r4 = verifier.check_firsthand_calculations_gate(pos_dir)
    r5 = verifier.check_proprietary_models_gate(pos_dir)
    r6 = verifier.verify_unique_first_party_information(pos_dir)
    assert r1["status"] == r2["status"] == r3["status"] == r4["status"] == r5["status"] == r6["status"] == "PASS"

    # Module-level aliases
    m1 = check_unique_first_party_information_gate(pos_dir)
    m2 = check_first_party_information_gate(pos_dir)
    m3 = check_first_party_assets_gate(pos_dir)
    m4 = check_firsthand_calculations_gate(pos_dir)
    m5 = check_proprietary_models_gate(pos_dir)
    m6 = verify_unique_first_party_information(pos_dir)
    assert m1["status"] == m2["status"] == m3["status"] == m4["status"] == m5["status"] == m6["status"] == "PASS"

    # In-memory HTML helper
    h_res = verify_html_unique_first_party_information(compliant_page)
    assert h_res["status"] == "PASS"
    assert h_res["violations_count"] == 0

    # audit_seo_checklist integration
    home_page = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>ProfitHelm Platform Programmatic Tax Calculation Tools</title>'
        '<meta name="description" content="Access deterministic programmatic tax models, Section 179 depreciation tools, and business calculations.">'
        '<link rel="canonical" href="https://profithelm.com/">'
        '</head><body>'
        '<h1>ProfitHelm Programmatic Calculation Hub</h1>'
        '<a href="/tools/qbi-deduction/">QBI Tool</a>'
        '</body></html>'
    )
    (pos_dir / "index.html").write_text(home_page, encoding="utf-8")

    audit_res = verifier.audit_seo_checklist(pos_dir, enforce_relevance=False)
    assert "check_unique_first_party_information_gate" in audit_res["gates"]
    assert "check_first_party_information_gate" in audit_res["gates"]
    assert "check_first_party_assets_gate" in audit_res["gates"]
    assert "check_firsthand_calculations_gate" in audit_res["gates"]
    assert "check_proprietary_models_gate" in audit_res["gates"]
    assert audit_res["gates"]["check_unique_first_party_information_gate"]["status"] == "PASS"



def test_factor8_spec_registration():
    """Verifies Factor 8 registration in ZYPPY_2026_AI_FACTORS_SPEC and factor resolver."""
    factor8 = ZYPPY_2026_AI_FACTORS_SPEC[7]
    assert factor8["code"] == "cross_web_consensus_and_corroboration"
    assert factor8["name"] == "Cross-Web Consensus & Corroboration"
    assert factor8["weight"] == 1.81
    assert factor8["positive_weight"] == 1.81
    assert factor8["negative_weight"] == -1.81

    # Aliases
    aliases = factor8.get("aliases", [])
    assert "Cross-Web Consensus & Corroboration" in aliases
    assert "Cross-web Corroboration" in aliases
    assert "cross_web_corroboration" in aliases
    assert "statutory_consensus" in aliases
    assert "baseline_fact_agreement" in aliases
    assert "cross_web_consensus" in aliases

    # get_ai_factor_spec lookups
    by_pos = get_ai_factor_spec(8)
    assert by_pos is factor8
    by_code = get_ai_factor_spec("cross_web_consensus_and_corroboration")
    assert by_code is factor8
    by_alias = get_ai_factor_spec("cross_web_corroboration")
    assert by_alias is factor8
    by_consensus = get_ai_factor_spec("statutory_consensus")
    assert by_consensus is factor8


def test_statutory_tax_brackets_schedules():
    """Verifies statutory tax bracket schedules across years and filing statuses."""
    for year in (2024, 2025, 2026, 2027):
        assert year in STATUTORY_TAX_BRACKETS
        schedules = STATUTORY_TAX_BRACKETS[year]
        assert "single" in schedules
        assert "married_filing_jointly" in schedules

        single_brackets = schedules["single"]
        assert len(single_brackets) == 7
        for b in single_brackets:
            assert b["rate"] in VALID_FEDERAL_TAX_RATES
            assert b["min_income"] >= 0.0

        # Monotonic income thresholds
        for i in range(len(single_brackets) - 1):
            assert single_brackets[i]["min_income"] < single_brackets[i]["max_income"]
            assert single_brackets[i]["max_income"] == single_brackets[i + 1]["min_income"]
        assert single_brackets[-1]["max_income"] is None

    # Helper function
    b_2025 = get_official_tax_brackets(2025, "single")
    assert b_2025[0]["rate"] == 10.0
    assert b_2025[0]["max_income"] == 11925.0

    b_mfj = get_official_tax_brackets(2025, "mfj")
    assert b_mfj[0]["rate"] == 10.0
    assert b_mfj[0]["max_income"] == 23850.0

    # 2027 Post-TCJA Reversion rates check
    b_2027 = get_official_tax_brackets(2027, "single")
    rates_2027 = [b["rate"] for b in b_2027]
    assert rates_2027 == [10.0, 15.0, 25.0, 28.0, 33.0, 35.0, 39.6]


def test_standard_deductions_schedules():
    """Verifies standard deduction schedules across tax years and filing statuses."""
    assert get_official_standard_deduction(2024, "single") == 14600.0
    assert get_official_standard_deduction(2024, "mfj") == 29200.0
    assert get_official_standard_deduction(2025, "single") == 15000.0
    assert get_official_standard_deduction(2025, "mfj") == 30000.0
    assert get_official_standard_deduction(2027, "single") == 8600.0
    assert get_official_standard_deduction(2027, "mfj") == 17200.0

    # Additional standard deductions for 65+ or blind
    assert STATUTORY_STANDARD_DEDUCTIONS[2024]["additional_65_or_blind_single"] == 1950.0
    assert STATUTORY_STANDARD_DEDUCTIONS[2025]["additional_65_or_blind_single"] == 2000.0


def test_statutory_limits_schedules():
    """Verifies official statutory limits across key tax and corporate provisions."""
    assert get_official_statutory_limit("section_179_max_deduction", 2024) == 1220000.0
    assert get_official_statutory_limit("section_179_max_deduction", 2025) == 1250000.0
    assert get_official_statutory_limit("section_179_phaseout_threshold", 2024) == 3050000.0
    assert get_official_statutory_limit("section_179_phaseout_threshold", 2025) == 3130000.0

    # Section 1202 QSBS
    qsbs = get_official_statutory_limit("section_1202_qsbs")
    assert qsbs["asset_ceiling"] == 50000000.0
    assert qsbs["exclusion_cap"] == 10000000.0
    assert qsbs["holding_period_years"] == 5

    # 401(k) and IRA limits
    assert get_official_statutory_limit("retirement_401k_elective_deferral", 2024) == 23000.0
    assert get_official_statutory_limit("retirement_401k_elective_deferral", 2025) == 23500.0
    assert get_official_statutory_limit("retirement_ira_contribution", 2025) == 7000.0


def test_assert_cross_web_consensus_and_corroboration_positive():
    """Verifies compliant HTML documents pass Factor 8 validation cleanly."""
    compliant_html = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>Section 179 and Statutory Tax Planning Engine</title>'
        '<meta name="description" content="Calculate equipment expensing and tax brackets with verified statutory schedules.">'
        '<script type="application/json" id="statutory-manifest">'
        '{'
        '  "topic": "Section 179 and Tax Brackets",'
        '  "max_asset_issuance_usd": 50000000,'
        '  "gain_exclusion_cap_usd": 10000000,'
        '  "holding_period_years": 5,'
        '  "brackets": ['
        '    {"current_rate": 10.0, "sunset_rate": 10.0, "single_max": 11925},'
        '    {"current_rate": 12.0, "sunset_rate": 15.0, "single_max": 48475},'
        '    {"current_rate": 22.0, "sunset_rate": 25.0, "single_max": 103350},'
        '    {"current_rate": 24.0, "sunset_rate": 28.0, "single_max": 197300},'
        '    {"current_rate": 32.0, "sunset_rate": 33.0, "single_max": 250525},'
        '    {"current_rate": 35.0, "sunset_rate": 35.0, "single_max": 626350},'
        '    {"current_rate": 37.0, "sunset_rate": 39.6, "single_max": 999999999}'
        '  ]'
        '}'
        '</script>'
        '</head><body>'
        '<h1>Statutory Tax Corroboration Engine</h1>'
        '<p>Under IRC Section 179, the 2025 expensing limit is $1,250,000 with a phaseout threshold of $3,130,000.</p>'
        '<p>For 2025, the standard deduction is $15,000 for single filers and $30,000 for married filing jointly.</p>'
        '<p>Under IRC Section 1202, eligible QSBS stock must meet the gross asset ceiling of $50,000,000 with a lifetime gain exclusion cap of $10,000,000.</p>'
        '<p>The 401(k) elective deferral limit is $23,500.</p>'
        '</body></html>'
    )

    assert assert_cross_web_consensus_and_corroboration(compliant_html, require_corroboration=True) is True
    assert assert_statutory_tax_brackets(compliant_html) is True
    assert assert_standard_deduction_values(compliant_html) is True
    assert assert_statutory_limits(compliant_html) is True
    assert assert_no_uncorroborated_tax_constants(compliant_html) is True

    # Aliases
    assert assert_cross_web_corroboration(compliant_html) is True
    assert assert_statutory_consensus(compliant_html) is True
    assert assert_baseline_fact_agreement(compliant_html) is True
    assert assert_statutory_constants_corroboration(compliant_html) is True


def test_assert_cross_web_consensus_failure_modes():
    """Verifies clear assertion errors on mismatched constants, invented limits, and silent fallbacks."""
    # 1. Silent fallback default
    html_fallback = "<html><body><p>We default to a 20% tax bracket when unspecified.</p></body></html>"
    with pytest.raises(ValueError, match="Silent fallback default detected"):
        assert_cross_web_consensus_and_corroboration(html_fallback)

    # 2. Invented federal tax rate
    html_invented_rate = "<html><body><p>A 18% federal tax bracket applies to middle income earners.</p></body></html>"
    with pytest.raises(ValueError, match="Invented federal tax rate"):
        assert_cross_web_consensus_and_corroboration(html_invented_rate)

    # 3. Mismatched standard deduction
    html_bad_ded = "<html><body><p>The standard deduction of $25,000 for single filers reduces taxable income.</p></body></html>"
    with pytest.raises(ValueError, match="Mismatched standard deduction value"):
        assert_cross_web_consensus_and_corroboration(html_bad_ded)

    # 4. Mismatched Section 179 limit
    html_bad_sec179 = "<html><body><p>Section 179 deduction limit of $2,500,000 is available this year.</p></body></html>"
    with pytest.raises(ValueError, match="Mismatched Section 179 expensing limit"):
        assert_cross_web_consensus_and_corroboration(html_bad_sec179)

    # 5. Mismatched Section 1202 QSBS asset ceiling
    html_bad_qsbs = "<html><body><p>Section 1202 QSBS gross asset ceiling is $100,000,000.</p></body></html>"
    with pytest.raises(ValueError, match="Mismatched Section 1202 QSBS asset ceiling"):
        assert_cross_web_consensus_and_corroboration(html_bad_qsbs)

    # 6. Mismatched 401(k) limit
    html_bad_401k = "<html><body><p>The 401(k) elective deferral limit is $35,000 for this year.</p></body></html>"
    with pytest.raises(ValueError, match="Mismatched 401\\(k\\) deferral limit"):
        assert_cross_web_consensus_and_corroboration(html_bad_401k)

    # 7. Missing corroboration when required
    html_empty = "<html><body><p>General narrative without any verified statutory constants or schedules.</p></body></html>"
    with pytest.raises(ValueError, match="Document missing verified statutory constants"):
        assert_cross_web_consensus_and_corroboration(html_empty, require_corroboration=True)

    # 8. Forbidden dashes
    html_emdash = "<html><body><p>Tax brackets \u2014 statutory rates revert in 2026.</p></body></html>"
    with pytest.raises(ValueError, match="Forbidden em-dash"):
        assert_cross_web_consensus_and_corroboration(html_emdash)

    html_endash = "<html><body><p>Tax brackets \u2013 statutory rates revert in 2026.</p></body></html>"
    with pytest.raises(ValueError, match="Forbidden en-dash"):
        assert_cross_web_consensus_and_corroboration(html_endash)


def test_detect_uncorroborated_statutory_claims_boundary_conditions():
    """Verifies edge case detection for uncorroborated statutory claims and manifests."""
    # Status-specific standard deduction mismatches
    bad_single = "<p>Under the IRS schedule, standard deduction is $30,000 for single filers.</p>"
    issues = detect_uncorroborated_statutory_claims(bad_single)
    assert any("Mismatched single standard deduction value" in i for i in issues)

    bad_mfj = "<p>Under current rules, standard deduction is $15,000 for married couples filing jointly.</p>"
    issues = detect_uncorroborated_statutory_claims(bad_mfj)
    assert any("Mismatched MFJ standard deduction value" in i for i in issues)

    # Structured manifest invalid Section 1202 exclusion cap
    bad_manifest = (
        '<script type="application/json" id="statutory-manifest">'
        '{"topic": "QSBS", "gain_exclusion_cap_usd": 25000000, "holding_period_years": 3}'
        '</script>'
    )
    issues_m = detect_uncorroborated_statutory_claims(bad_manifest)
    assert any("invalid Section 1202 exclusion cap" in i for i in issues_m)
    assert any("invalid Section 1202 holding period" in i for i in issues_m)

    # Structured manifest invalid bracket rate
    bad_brackets = (
        '<script type="application/json" id="statutory-manifest">'
        '{"brackets": [{"rate": 18.5, "single_max": 50000}]}'
        '</script>'
    )
    issues_b = detect_uncorroborated_statutory_claims(bad_brackets)
    assert any("invented rate" in i for i in issues_b)


def test_check_cross_web_consensus_gate_synthetic_fixtures(tmp_path):
    """Verifies check_cross_web_consensus_and_corroboration_gate across positive and negative dist directories."""
    pos_dir = tmp_path / "pos_dist_factor8"
    pos_dir.mkdir()
    tool_dir = pos_dir / "tools" / "sec179-corroborated"
    tool_dir.mkdir(parents=True)

    compliant_page = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>Section 179 Statutory Calculator and Corroboration Engine</title>'
        '<meta name="description" content="Calculate equipment expensing and tax deductions with verified statutory schedules.">'
        '<link rel="canonical" href="https://profithelm.com/tools/sec179-corroborated/">'
        '</head><body>'
        '<h1>Section 179 Statutory Expensing Calculator</h1>'
        '<p>Under IRC Section 179, the 2025 expensing limit is $1,250,000 with a phaseout threshold of $3,130,000.</p>'
        '<p>The standard deduction is $15,000 for single taxpayers and $30,000 for married filing jointly.</p>'
        '<p>Under IRC Section 1202, eligible QSBS stock must satisfy the gross asset ceiling of $50,000,000.</p>'
        '</body></html>'
    )
    (tool_dir / "index.html").write_text(compliant_page, encoding="utf-8")

    verifier = MasterSEOVerifier(dist_dir=pos_dir, domain="profithelm.com")
    res_pos = verifier.check_cross_web_consensus_and_corroboration_gate(pos_dir)
    assert res_pos["status"] == "PASS"
    assert res_pos["pages_checked"] >= 1
    assert res_pos["violations_count"] == 0
    assert res_pos["statutory_constants_verified"] >= 3

    # Negative directory fixture
    neg_dir = tmp_path / "neg_dist_factor8"
    neg_dir.mkdir()
    neg_tool = neg_dir / "tools" / "bad-constants"
    neg_tool.mkdir(parents=True)

    corrupted_page = (
        '<!DOCTYPE html><html lang="en"><head><title>Bad Constants</title></head><body>'
        '<h1>Corrupted Statutory Constants</h1>'
        '<p>We default to a 20% tax bracket.</p>'
        '<p>Section 179 deduction limit is $5,000,000.</p>'
        '<p>Standard deduction of $40,000 applies to single filers.</p>'
        '</body></html>'
    )
    (neg_tool / "index.html").write_text(corrupted_page, encoding="utf-8")

    verifier_neg = MasterSEOVerifier(dist_dir=neg_dir, domain="profithelm.com")
    res_neg = verifier_neg.check_cross_web_consensus_and_corroboration_gate(neg_dir)
    assert res_neg["status"] == "FAIL"
    assert res_neg["violations_count"] >= 3
    assert any("Silent fallback default" in i for i in res_neg["issues"])
    assert any("Mismatched Section 179 expensing limit" in i for i in res_neg["issues"])
    assert any("Mismatched standard deduction value" in i for i in res_neg["issues"])


def test_gate_aliases_and_checklist_integration_factor8(tmp_path):
    """Verifies Factor 8 gate aliases and audit_seo_checklist integration."""
    pos_dir = tmp_path / "dist_factor8_integration"
    pos_dir.mkdir()
    tool_dir = pos_dir / "tools" / "tax-brackets-2025"
    tool_dir.mkdir(parents=True)

    compliant_page = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>2025 IRS Marginal Tax Brackets and Standard Deduction Schedules</title>'
        '<meta name="description" content="Official IRS tax brackets and standard deductions for single and married taxpayers.">'
        '<link rel="canonical" href="https://profithelm.com/tools/tax-brackets-2025/">'
        '</head><body>'
        '<h1>IRS 2025 Tax Brackets and Standard Deductions</h1>'
        '<p>Under IRC Section 1, the 2025 standard deduction is $15,000 for single and $30,000 for married filing jointly.</p>'
        '<p>Section 179 expensing limit is $1,250,000 with phaseout at $3,130,000.</p>'
        '<p>The Section 1202 QSBS gross asset ceiling is $50,000,000 and exclusion cap is $10,000,000.</p>'
        '</body></html>'
    )
    (tool_dir / "index.html").write_text(compliant_page, encoding="utf-8")

    verifier = MasterSEOVerifier(dist_dir=pos_dir, domain="profithelm.com")

    # Verifier method aliases
    r1 = verifier.check_cross_web_consensus_and_corroboration_gate(pos_dir)
    r2 = verifier.check_cross_web_corroboration_gate(pos_dir)
    r3 = verifier.check_statutory_consensus_gate(pos_dir)
    r4 = verifier.check_baseline_fact_agreement_gate(pos_dir)
    r5 = verifier.check_statutory_constants_corroboration_gate(pos_dir)
    r6 = verifier.verify_cross_web_consensus_and_corroboration(pos_dir)
    r7 = verifier.verify_cross_web_corroboration(pos_dir)
    assert r1["status"] == r2["status"] == r3["status"] == r4["status"] == r5["status"] == r6["status"] == r7["status"] == "PASS"

    # Module-level aliases
    m1 = check_cross_web_consensus_and_corroboration_gate(pos_dir)
    m2 = check_cross_web_corroboration_gate(pos_dir)
    m3 = check_statutory_consensus_gate(pos_dir)
    m4 = check_baseline_fact_agreement_gate(pos_dir)
    m5 = check_statutory_constants_corroboration_gate(pos_dir)
    m6 = verify_cross_web_consensus_and_corroboration(pos_dir)
    m7 = verify_cross_web_corroboration(pos_dir)
    assert m1["status"] == m2["status"] == m3["status"] == m4["status"] == m5["status"] == m6["status"] == m7["status"] == "PASS"

    # In-memory HTML helper
    h_res = verify_html_cross_web_consensus_and_corroboration(compliant_page)
    assert h_res["status"] == "PASS"
    assert h_res["violations_count"] == 0
    assert h_res["verified_constants_count"] >= 3

    h_alias = verify_html_cross_web_corroboration(compliant_page)
    assert h_alias["status"] == "PASS"

    # audit_seo_checklist integration
    home_page = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>ProfitHelm Platform Programmatic Tax Calculation Tools</title>'
        '<meta name="description" content="Access deterministic programmatic tax models, Section 179 depreciation tools, and business calculations.">'
        '<link rel="canonical" href="https://profithelm.com/">'
        '</head><body>'
        '<h1>ProfitHelm Programmatic Calculation Hub</h1>'
        '<a href="/tools/tax-brackets-2025/">Tax Tool</a>'
        '</body></html>'
    )
    (pos_dir / "index.html").write_text(home_page, encoding="utf-8")

    audit_res = verifier.audit_seo_checklist(pos_dir, enforce_relevance=False)
    assert "check_cross_web_consensus_and_corroboration_gate" in audit_res["gates"]
    assert "check_cross_web_corroboration_gate" in audit_res["gates"]
    assert "check_statutory_consensus_gate" in audit_res["gates"]
    assert "check_baseline_fact_agreement_gate" in audit_res["gates"]
    assert "check_statutory_constants_corroboration_gate" in audit_res["gates"]
    assert audit_res["gates"]["check_cross_web_consensus_and_corroboration_gate"]["status"] == "PASS"


def test_factor9_spec_registration():
    """Verifies Factor 9 registration in ZYPPY_2026_AI_FACTORS_SPEC and factor resolver."""
    factor9 = ZYPPY_2026_AI_FACTORS_SPEC[8]
    assert factor9["code"] == "source_publisher_reputation"
    assert factor9["name"] == "Source / Publisher Reputation"
    assert factor9["weight"] == 1.78
    assert factor9["positive_weight"] == 1.78
    assert factor9["negative_weight"] == -1.78

    # Aliases
    aliases = factor9.get("aliases", [])
    assert "Source / Publisher Reputation" in aliases
    assert "Source Publisher Reputation" in aliases
    assert "Publisher Reputation" in aliases
    assert "source_publisher_reputation" in aliases
    assert "publisher_reputation" in aliases
    assert "publisher_authority" in aliases
    assert "author_credentials" in aliases
    assert "editorial_policy" in aliases
    assert "about_contact_linkages" in aliases

    # get_ai_factor_spec lookups
    by_pos = get_ai_factor_spec(9)
    assert by_pos is factor9
    by_code = get_ai_factor_spec("source_publisher_reputation")
    assert by_code is factor9
    by_alias = get_ai_factor_spec("publisher_reputation")
    assert by_alias is factor9
    by_name = get_ai_factor_spec("Publisher Reputation")
    assert by_name is factor9
    by_full = get_ai_factor_spec("Source / Publisher Reputation")
    assert by_full is factor9
    by_creds = get_ai_factor_spec("author_credentials")
    assert by_creds is factor9
    by_policy = get_ai_factor_spec("editorial_policy")
    assert by_policy is factor9


def test_assert_publisher_authority():
    """Verifies publisher authority validation for schema objects and HTML strings."""
    # Positive dict
    valid_org = {
        "@type": "Organization",
        "name": "ProfitHelm Analytics",
        "url": "https://profithelm.com",
        "logo": "https://profithelm.com/logo.png",
    }
    assert assert_publisher_authority(valid_org) is True

    # Negative dict: empty name
    with pytest.raises(ValueError, match="missing or empty publisher name"):
        assert_publisher_authority({"@type": "Organization", "name": "", "url": "https://example.com"})

    # Negative dict: anonymous publisher
    with pytest.raises(ValueError, match="anonymous or placeholder publisher"):
        assert_publisher_authority({"@type": "Organization", "name": "Anonymous", "url": "https://example.com"})

    # Negative dict: missing URL
    with pytest.raises(ValueError, match="missing authoritative URL"):
        assert_publisher_authority({"@type": "Organization", "name": "ProfitHelm Analytics", "url": ""})

    # Positive HTML
    html_org = (
        '<!DOCTYPE html><html><head>'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "Organization", "name": "ProfitHelm", "url": "https://profithelm.com"}'
        '</script>'
        '</head><body><a href="/about/">About</a><a href="/contact/">Contact</a><a href="/editorial-policy/">Editorial</a></body></html>'
    )
    assert assert_publisher_authority(html_org) is True

    # Negative HTML: anonymous publisher
    html_anon_org = (
        '<!DOCTYPE html><html><head>'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "Organization", "name": "Admin", "url": "https://profithelm.com"}'
        '</script>'
        '</head><body><a href="/about/">About</a><a href="/contact/">Contact</a><a href="/editorial-policy/">Editorial</a></body></html>'
    )
    with pytest.raises(ValueError, match="Anonymous or placeholder publisher"):
        assert_publisher_authority(html_anon_org)


def test_assert_author_credentials():
    """Verifies author credentials assertion across schema dictionaries and document HTML."""
    # Positive dict: Person with jobTitle
    valid_person = {
        "@type": "Person",
        "name": "Elena Rostova",
        "jobTitle": "Lead Quantitative Tax Strategist",
        "sameAs": "https://linkedin.com/in/elenarostova",
    }
    assert assert_author_credentials(valid_person) is True

    # Positive dict: credentials in name string
    person_with_title_in_name = {
        "@type": "Person",
        "name": "Marcus Vance, CPA",
    }
    assert assert_author_credentials(person_with_title_in_name) is True

    # Negative dict: missing name
    with pytest.raises(ValueError, match="missing or empty author name"):
        assert_author_credentials({"@type": "Person", "name": ""})

    # Negative dict: anonymous author
    with pytest.raises(ValueError, match="anonymous or placeholder author"):
        assert_author_credentials({"@type": "Person", "name": "Staff Writer"})

    # Negative dict: author lacks credentials or jobTitle
    with pytest.raises(ValueError, match="lacks verified credentials"):
        assert_author_credentials({"@type": "Person", "name": "Generic Person"})

    # Positive HTML
    html_author = (
        '<!DOCTYPE html><html><head>'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "Article", '
        '"author": {"@type": "Person", "name": "Elena Rostova", "jobTitle": "Tax Director"}, '
        '"publisher": {"@type": "Organization", "name": "ProfitHelm", "url": "https://profithelm.com"}, '
        '"publishingPrinciples": "https://profithelm.com/editorial/"}'
        '</script>'
        '</head><body><a href="/about/">About</a><a href="/contact/">Contact</a></body></html>'
    )
    assert assert_author_credentials(html_author) is True

    # Negative HTML: author lacks credentials
    html_no_creds = (
        '<!DOCTYPE html><html><head>'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "Article", '
        '"author": {"@type": "Person", "name": "Uncredentialed Writer"}, '
        '"publisher": {"@type": "Organization", "name": "ProfitHelm", "url": "https://profithelm.com"}, '
        '"publishingPrinciples": "https://profithelm.com/editorial/"}'
        '</script>'
        '</head><body><a href="/about/">About</a><a href="/contact/">Contact</a></body></html>'
    )
    with pytest.raises(ValueError, match="Missing author credentials"):
        assert_author_credentials(html_no_creds)


def test_assert_person_organization_schema():
    """Verifies schema structure compliance for Person and Organization types."""
    valid_schema = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "Organization", "name": "ProfitHelm", "url": "https://profithelm.com"},
            {"@type": "Person", "name": "Dr. Sarah Jenkins", "jobTitle": "Chief Economist"},
        ]
    }
    assert assert_person_organization_schema(valid_schema) is True

    with pytest.raises(ValueError, match="schema must contain Person or Organization"):
        assert_person_organization_schema({"@type": "Thing", "name": "JustAThing"})

    html_valid = (
        '<html><head><script type="application/ld+json">'
        '{"@type": "Organization", "name": "ProfitHelm", "url": "https://profithelm.com"}'
        '</script></head><body></body></html>'
    )
    assert assert_person_organization_schema(html_valid) is True

    html_invalid = '<html><head><script type="application/ld+json">{"@type": "Item"}</script></head><body></body></html>'
    with pytest.raises(ValueError, match="document structured data missing both"):
        assert_person_organization_schema(html_invalid)


def test_assert_editorial_policy():
    """Verifies editorial policy enforcement across schema attributes and HTML links."""
    # Positive schema publishingPrinciples
    schema_policy = {"publishingPrinciples": "https://profithelm.com/editorial-standards/"}
    assert assert_editorial_policy(schema_policy) is True

    # Positive schema reviewedBy
    schema_reviewed = {"reviewedBy": {"@type": "Person", "name": "Senior Reviewer"}}
    assert assert_editorial_policy(schema_reviewed) is True

    # Negative schema missing policy
    with pytest.raises(ValueError, match="schema missing publishingPrinciples"):
        assert_editorial_policy({"@type": "Article", "headline": "Tax Guide"})

    # Positive HTML link
    html_link = '<html><body><a href="/editorial-policy/">Our Review Standards</a></body></html>'
    assert assert_editorial_policy(html_link) is True

    # Positive HTML reviewedBy text
    html_text = '<html><body><p>Fact checked by Senior Tax Committee.</p></body></html>'
    assert assert_editorial_policy(html_text) is True

    # Negative HTML
    html_no_policy = '<html><body><p>Just plain text without any review guidelines.</p></body></html>'
    with pytest.raises(ValueError, match="missing editorial review policy"):
        assert_editorial_policy(html_no_policy)


def test_assert_freshness_signals():
    """Verifies datePublished and dateModified validity, chronology, and boundary ranges."""
    # Positive dict
    valid_dates = {
        "datePublished": "2025-01-15T08:00:00Z",
        "dateModified": "2025-02-01T12:00:00Z",
    }
    assert assert_freshness_signals(valid_dates) is True

    # Positive datePublished only
    assert assert_freshness_signals({"datePublished": "2025-06-20"}) is True

    # Negative: invalid datePublished format
    with pytest.raises(ValueError, match="invalid ISO-8601 datePublished"):
        assert_freshness_signals({"datePublished": "yesterday-afternoon"})

    # Negative: invalid dateModified format
    with pytest.raises(ValueError, match="invalid ISO-8601 dateModified"):
        assert_freshness_signals({"datePublished": "2025-01-10", "dateModified": "unspecified"})

    # Negative: chronology violation (modified before published)
    with pytest.raises(ValueError, match="dateModified .* precedes datePublished"):
        assert_freshness_signals({
            "datePublished": "2025-06-01T00:00:00Z",
            "dateModified": "2025-01-01T00:00:00Z",
        })

    # Negative: out-of-bounds publication year in HTML
    html_ancient = (
        '<html><head><script type="application/ld+json">'
        '{"@type": "Article", "datePublished": "1985-05-12"}'
        '</script></head><body></body></html>'
    )
    with pytest.raises(ValueError, match="out-of-bounds datePublished year"):
        assert_freshness_signals(html_ancient)


def test_assert_about_contact_linkages():
    """Verifies about and contact navigation linkages across HTML and structured data."""
    # Positive HTML with both links
    html_both = '<html><body><nav><a href="/about/">About Us</a><a href="/contact/">Contact Support</a></nav></body></html>'
    assert assert_about_contact_linkages(html_both) is True

    # Positive HTML with mailto contact
    html_mailto = '<html><body><footer><a href="mailto:support@profithelm.com">Email Us</a></footer></body></html>'
    assert assert_about_contact_linkages(html_mailto) is True

    # Positive schema contactPoint
    assert assert_about_contact_linkages({"contactPoint": {"@type": "ContactPoint", "telephone": "+1-800-555-0199"}}) is True

    # Negative HTML missing both
    html_missing = '<html><body><p>No contact or about destinations on this page.</p></body></html>'
    with pytest.raises(ValueError, match="missing about or contact navigational links"):
        assert_about_contact_linkages(html_missing)


def test_assert_source_publisher_reputation_positive_and_aliases():
    """Verifies that fully compliant documents pass Factor 9 master assertion and all aliases."""
    compliant_doc = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>2026 TCJA Sunset Tax Planning Engine and Analysis</title>'
        '<meta name="description" content="Deterministic multi-tier statutory tax modeling under IRC Section 1 and TCJA expiration schedules.">'
        '<link rel="canonical" href="https://profithelm.com/tools/tcja-sunset/">'
        '<script type="application/ld+json">'
        '{'
        '  "@context": "https://schema.org",'
        '  "@type": "TechArticle",'
        '  "headline": "2026 TCJA Sunset Marginal Rate Progression",'
        '  "datePublished": "2025-01-10T08:00:00Z",'
        '  "dateModified": "2025-02-15T14:30:00Z",'
        '  "author": {'
        '    "@type": "Person",'
        '    "name": "Dr. Sarah Jenkins",'
        '    "jobTitle": "Principal Tax Policy Architect, CPA",'
        '    "sameAs": "https://linkedin.com/in/sarahjenkins-cpa"'
        '  },'
        '  "publisher": {'
        '    "@type": "Organization",'
        '    "name": "ProfitHelm Analytics Inc.",'
        '    "url": "https://profithelm.com",'
        '    "logo": "https://profithelm.com/assets/logo.png"'
        '  },'
        '  "publishingPrinciples": "https://profithelm.com/editorial-policy/"'
        '}'
        '</script>'
        '</head><body>'
        '<header>'
        '  <nav>'
        '    <a href="/about/">About ProfitHelm</a>'
        '    <a href="/contact/">Contact Our Team</a>'
        '    <a href="/editorial-policy/">Editorial Guidelines</a>'
        '  </nav>'
        '</header>'
        '<main>'
        '  <h1>TCJA Expiration Tax Planning Engine</h1>'
        '  <div class="author-card">'
        '    <p>Written by Dr. Sarah Jenkins, CPA, Principal Tax Policy Architect.</p>'
        '  </div>'
        '  <p>Deterministic analysis reconciles statutory reversion brackets under 26 U.S.C. Section 1.</p>'
        '</main>'
        '</body></html>'
    )

    assert assert_source_publisher_reputation(compliant_doc, require_strict=True) is True
    assert assert_publisher_reputation(compliant_doc) is True
    assert assert_publisher_authority_and_credentials(compliant_doc) is True
    assert assert_author_and_publisher_schema(compliant_doc) is True
    assert assert_editorial_and_freshness_signals(compliant_doc) is True


def test_verify_html_source_publisher_reputation_in_memory():
    """Verifies in-memory HTML document validation across positive compliant page and all failure modes."""
    compliant_html = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>Corporate Tax Depreciation and Section 179 Allowance Engine</title>'
        '<meta name="description" content="Calculate statutory equipment depreciation limits under 26 U.S.C. Section 179 and BLS economic series.">'
        '<script type="application/ld+json">'
        '{'
        '  "@context": "https://schema.org",'
        '  "@type": "TechArticle",'
        '  "headline": "Section 179 Equipment Expensing Calculations",'
        '  "datePublished": "2025-01-20T09:00:00Z",'
        '  "dateModified": "2025-02-18T10:00:00Z",'
        '  "author": {'
        '    "@type": "Person",'
        '    "name": "Marcus Vance",'
        '    "jobTitle": "Senior Tax Attorney, JD, LLM",'
        '    "sameAs": "https://linkedin.com/in/marcusvance"'
        '  },'
        '  "publisher": {'
        '    "@type": "Organization",'
        '    "name": "ProfitHelm Platform",'
        '    "url": "https://profithelm.com",'
        '    "logo": "https://profithelm.com/logo.png"'
        '  },'
        '  "publishingPrinciples": "https://profithelm.com/editorial-policy/"'
        '}'
        '</script>'
        '</head><body>'
        '<nav>'
        '  <a href="/about/">About Us</a>'
        '  <a href="/contact/">Contact Us</a>'
        '  <a href="/editorial-policy/">Review Standards</a>'
        '</nav>'
        '<h1>Section 179 Depreciation Calculations</h1>'
        '<p>Under 26 U.S.C. Section 179, qualifying businesses can deduct capital expenditures.</p>'
        '</body></html>'
    )

    res_pass = verify_html_source_publisher_reputation(compliant_html)
    assert res_pass["status"] == "PASS"
    assert res_pass["violations_count"] == 0
    assert res_pass["authors_count"] >= 1
    assert res_pass["publishers_count"] >= 1
    assert res_pass["has_editorial_policy"] is True
    assert res_pass["has_about_link"] is True
    assert res_pass["has_contact_link"] is True

    # Alias check
    res_alias = verify_html_publisher_reputation(compliant_html)
    assert res_alias["status"] == "PASS"

    # Negative 1: Anonymous author
    html_anon_author = compliant_html.replace(
        '"name": "Marcus Vance"',
        '"name": "Staff Writer"'
    )
    res_anon = verify_html_source_publisher_reputation(html_anon_author)
    assert res_anon["status"] == "FAIL"
    assert any("Anonymous or placeholder author" in i for i in res_anon["issues"])

    # Negative 2: Author missing credentials
    html_no_creds = compliant_html.replace(
        '"jobTitle": "Senior Tax Attorney, JD, LLM"',
        '"jobTitle": ""'
    )
    res_no_creds = verify_html_source_publisher_reputation(html_no_creds)
    assert res_no_creds["status"] == "FAIL"
    assert any("Missing author credentials" in i for i in res_no_creds["issues"])

    # Negative 3: Anonymous publisher
    html_anon_pub = compliant_html.replace(
        '"name": "ProfitHelm Platform"',
        '"name": "Admin"'
    )
    res_anon_pub = verify_html_source_publisher_reputation(html_anon_pub)
    assert res_anon_pub["status"] == "FAIL"
    assert any("Anonymous or placeholder publisher" in i for i in res_anon_pub["issues"])

    # Negative 4: Missing editorial policy
    html_no_policy = compliant_html.replace(
        '"publishingPrinciples": "https://profithelm.com/editorial-policy/"',
        '"keywords": "taxes"'
    ).replace(
        '<a href="/editorial-policy/">Review Standards</a>',
        ''
    )
    res_no_policy = verify_html_source_publisher_reputation(html_no_policy)
    assert res_no_policy["status"] == "FAIL"
    assert any("Missing editorial review policy" in i for i in res_no_policy["issues"])

    # Negative 5: Chronology violation (modified before published)
    html_chronology = compliant_html.replace(
        '"dateModified": "2025-02-18T10:00:00Z"',
        '"dateModified": "2024-12-01T10:00:00Z"'
    )
    res_chrono = verify_html_source_publisher_reputation(html_chronology)
    assert res_chrono["status"] == "FAIL"
    assert any("Chronology violation" in i for i in res_chrono["issues"])

    # Negative 6: Missing about and contact linkages
    html_no_links = compliant_html.replace(
        '<a href="/about/">About Us</a>', ''
    ).replace(
        '<a href="/contact/">Contact Us</a>', ''
    )
    res_no_links = verify_html_source_publisher_reputation(html_no_links)
    assert res_no_links["status"] == "FAIL"
    assert any("Missing about/contact linkages" in i for i in res_no_links["issues"])

    # Negative 7: Forbidden em-dash
    html_emdash = compliant_html.replace(
        'Section 179 Depreciation Calculations',
        'Section 179 ' + chr(0x2014) + ' Depreciation Calculations'
    )
    res_emdash = verify_html_source_publisher_reputation(html_emdash)
    assert res_emdash["status"] == "FAIL"
    assert any("forbidden em-dash" in i for i in res_emdash["issues"])

    # Negative 8: Forbidden en-dash
    html_endash = compliant_html.replace(
        'Section 179 Depreciation Calculations',
        'Section 179 ' + chr(0x2013) + ' Depreciation Calculations'
    )
    res_endash = verify_html_source_publisher_reputation(html_endash)
    assert res_endash["status"] == "FAIL"
    assert any("forbidden en-dash" in i for i in res_endash["issues"])


def test_check_source_publisher_reputation_gate_disk_fixtures(tmp_path):
    """Verifies check_source_publisher_reputation_gate on disk fixtures across positive and negative trees."""
    pos_dir = tmp_path / "pos_dist_factor9"
    pos_dir.mkdir()
    tool_dir = pos_dir / "tools" / "sec-179-calculator"
    tool_dir.mkdir(parents=True)

    compliant_page = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>Section 179 Equipment Expensing Model and Calculator</title>'
        '<meta name="description" content="Calculate your Section 179 depreciation deductions under 26 U.S.C. Section 179 with verified statutory models.">'
        '<link rel="canonical" href="https://profithelm.com/tools/sec-179-calculator/">'
        '<script type="application/ld+json">'
        '{'
        '  "@context": "https://schema.org",'
        '  "@type": "Article",'
        '  "headline": "Section 179 Equipment Expensing",'
        '  "datePublished": "2025-01-15T08:00:00Z",'
        '  "dateModified": "2025-02-20T10:00:00Z",'
        '  "author": {'
        '    "@type": "Person",'
        '    "name": "Dr. Sarah Jenkins",'
        '    "jobTitle": "Principal Tax Policy Architect, CPA",'
        '    "sameAs": "https://linkedin.com/in/sarahjenkins-cpa"'
        '  },'
        '  "publisher": {'
        '    "@type": "Organization",'
        '    "name": "ProfitHelm Analytics",'
        '    "url": "https://profithelm.com",'
        '    "logo": "https://profithelm.com/logo.png"'
        '  },'
        '  "publishingPrinciples": "https://profithelm.com/editorial-policy/"'
        '}'
        '</script>'
        '</head><body>'
        '<nav><a href="/about/">About</a><a href="/contact/">Contact</a><a href="/editorial-policy/">Editorial</a></nav>'
        '<h1>Section 179 Expensing Engine</h1>'
        '<p>Detailed statutory modeling ensures tax optimization.</p>'
        '</body></html>'
    )
    (tool_dir / "index.html").write_text(compliant_page, encoding="utf-8")

    verifier = MasterSEOVerifier(dist_dir=pos_dir, domain="profithelm.com")
    res_pos = verifier.check_source_publisher_reputation_gate(pos_dir)
    assert res_pos["status"] == "PASS"
    assert res_pos["pages_checked"] >= 1
    assert res_pos["authors_verified"] >= 1
    assert res_pos["publishers_verified"] >= 1
    assert res_pos["violations_count"] == 0

    # Negative directory fixture
    neg_dir = tmp_path / "neg_dist_factor9"
    neg_dir.mkdir()
    neg_tool = neg_dir / "tools" / "anonymous-page"
    neg_tool.mkdir(parents=True)

    neg_page = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>Anonymous Page Lacking Credentials and Policy</title>'
        '<script type="application/ld+json">'
        '{'
        '  "@context": "https://schema.org",'
        '  "@type": "Article",'
        '  "headline": "Anonymous Guide",'
        '  "author": {"@type": "Person", "name": "Staff Writer"},'
        '  "publisher": {"@type": "Organization", "name": "Unknown", "url": "https://example.com"}'
        '}'
        '</script>'
        '</head><body>'
        '<h1>Anonymous Content Without Review Policy</h1>'
        '</body></html>'
    )
    (neg_tool / "index.html").write_text(neg_page, encoding="utf-8")

    verifier_neg = MasterSEOVerifier(dist_dir=neg_dir, domain="profithelm.com")
    res_neg = verifier_neg.check_source_publisher_reputation_gate(neg_dir)
    assert res_neg["status"] == "FAIL"
    assert res_neg["violations_count"] >= 2
    assert any("Anonymous or placeholder author" in i for i in res_neg["issues"])
    assert any("Missing editorial review policy" in i for i in res_neg["issues"])


def test_gate_aliases_and_checklist_integration_factor9(tmp_path):
    """Verifies Factor 9 gate aliases and audit_seo_checklist integration."""
    pos_dir = tmp_path / "dist_factor9_integration"
    pos_dir.mkdir()
    tool_dir = pos_dir / "tools" / "tax-brackets-2026"
    tool_dir.mkdir(parents=True)

    compliant_page = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>2026 Federal Tax Brackets and Rate Schedules</title>'
        '<meta name="description" content="Access deterministic 2026 statutory tax brackets, rates, and deduction schedules.">'
        '<link rel="canonical" href="https://profithelm.com/tools/tax-brackets-2026/">'
        '<script type="application/ld+json">'
        '{'
        '  "@context": "https://schema.org",'
        '  "@type": "TechArticle",'
        '  "headline": "2026 Federal Marginal Tax Schedules",'
        '  "datePublished": "2025-01-10T09:00:00Z",'
        '  "dateModified": "2025-02-15T11:00:00Z",'
        '  "author": {'
        '    "@type": "Person",'
        '    "name": "Dr. Sarah Jenkins",'
        '    "jobTitle": "Principal Tax Policy Architect, CPA",'
        '    "sameAs": "https://linkedin.com/in/sarahjenkins-cpa"'
        '  },'
        '  "publisher": {'
        '    "@type": "Organization",'
        '    "name": "ProfitHelm Analytics",'
        '    "url": "https://profithelm.com",'
        '    "logo": "https://profithelm.com/logo.png"'
        '  },'
        '  "publishingPrinciples": "https://profithelm.com/editorial-policy/"'
        '}'
        '</script>'
        '</head><body>'
        '<nav>'
        '  <a href="/about/">About ProfitHelm</a>'
        '  <a href="/contact/">Contact Us</a>'
        '  <a href="/editorial-policy/">Editorial Guidelines</a>'
        '</nav>'
        '<h1>2026 Federal Marginal Tax Schedules</h1>'
        '<p>Grounded in 26 U.S.C. Section 1 published statutory schedules.</p>'
        '</body></html>'
    )
    (tool_dir / "index.html").write_text(compliant_page, encoding="utf-8")

    verifier = MasterSEOVerifier(dist_dir=pos_dir, domain="profithelm.com")

    # Verifier method aliases
    r1 = verifier.check_source_publisher_reputation_gate(pos_dir)
    r2 = verifier.check_publisher_reputation_gate(pos_dir)
    r3 = verifier.check_publisher_authority_gate(pos_dir)
    r4 = verifier.check_author_credentials_gate(pos_dir)
    r5 = verifier.check_editorial_policy_gate(pos_dir)
    r6 = verifier.verify_source_publisher_reputation(pos_dir)
    r7 = verifier.verify_publisher_reputation(pos_dir)
    assert r1["status"] == r2["status"] == r3["status"] == r4["status"] == r5["status"] == r6["status"] == r7["status"] == "PASS"

    # Module-level aliases
    m1 = check_source_publisher_reputation_gate(pos_dir)
    m2 = check_publisher_reputation_gate(pos_dir)
    m3 = check_publisher_authority_gate(pos_dir)
    m4 = check_author_credentials_gate(pos_dir)
    m5 = check_editorial_policy_gate(pos_dir)
    m6 = verify_source_publisher_reputation(pos_dir)
    m7 = verify_publisher_reputation(pos_dir)
    assert m1["status"] == m2["status"] == m3["status"] == m4["status"] == m5["status"] == m6["status"] == m7["status"] == "PASS"

    # In-memory HTML helper
    h_res = verify_html_source_publisher_reputation(compliant_page)
    assert h_res["status"] == "PASS"
    assert h_res["violations_count"] == 0
    assert h_res["authors_count"] >= 1
    assert h_res["publishers_count"] >= 1

    h_alias = verify_html_publisher_reputation(compliant_page)
    assert h_alias["status"] == "PASS"

    # audit_seo_checklist integration
    home_page = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>ProfitHelm Platform Programmatic Tax Calculation Tools</title>'
        '<meta name="description" content="Access deterministic programmatic tax models, Section 179 depreciation tools, and business calculations.">'
        '<link rel="canonical" href="https://profithelm.com/">'
        '</head><body>'
        '<h1>ProfitHelm Programmatic Calculation Hub</h1>'
        '<a href="/tools/tax-brackets-2026/">Tax Tool</a>'
        '</body></html>'
    )
    (pos_dir / "index.html").write_text(home_page, encoding="utf-8")

    audit_res = verifier.audit_seo_checklist(pos_dir, enforce_relevance=False)
    assert "check_source_publisher_reputation_gate" in audit_res["gates"]
    assert "check_publisher_reputation_gate" in audit_res["gates"]
    assert "check_publisher_authority_gate" in audit_res["gates"]
    assert "check_author_credentials_gate" in audit_res["gates"]
    assert "check_editorial_policy_gate" in audit_res["gates"]
    assert audit_res["gates"]["check_source_publisher_reputation_gate"]["status"] == "PASS"


def test_factor10_spec_registration():
    """Verifies Factor 10 registration in ZYPPY_2026_AI_FACTORS_SPEC and factor resolver."""
    factor10 = ZYPPY_2026_AI_FACTORS_SPEC[9]
    assert factor10["code"] == "extractable_content_structure"
    assert factor10["name"] == "Extractable Content Structure"
    assert factor10["weight"] == 1.69
    assert factor10["positive_weight"] == 1.69
    assert factor10["negative_weight"] == -1.69

    # Aliases
    aliases = factor10.get("aliases", [])
    assert "Extractable Content Structure" in aliases
    assert "Extractable Content" in aliases
    assert "extractable_content_structure" in aliases
    assert "extractable_structure" in aliases
    assert "extractable_content" in aliases
    assert "semantic_heading_hierarchy" in aliases
    assert "table_column_scopes" in aliases
    assert "scoped_table_headers" in aliases
    assert "procedural_ordered_steps" in aliases
    assert "passage_level_blocks" in aliases

    # get_ai_factor_spec lookups
    s1 = get_ai_factor_spec(10)
    assert s1 is not None and s1["code"] == "extractable_content_structure"
    s2 = get_ai_factor_spec("extractable_content_structure")
    assert s2 is not None and s2["weight"] == 1.69
    s3 = get_ai_factor_spec("Extractable Content Structure")
    assert s3 is not None and s3["code"] == "extractable_content_structure"
    s4 = get_ai_factor_spec("semantic_heading_hierarchy")
    assert s4 is not None and s4["code"] == "extractable_content_structure"
    s5 = get_ai_factor_spec("table_column_scopes")
    assert s5 is not None and s5["code"] == "extractable_content_structure"
    s6 = get_ai_factor_spec("procedural_ordered_steps")
    assert s6 is not None and s6["code"] == "extractable_content_structure"
    s7 = get_ai_factor_spec("passage_level_blocks")
    assert s7 is not None and s7["code"] == "extractable_content_structure"


def test_assert_extractable_content_structure_contract():
    """Verifies standalone contract assertions and boundary conditions for Factor 10."""
    compliant_html = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>Section 179 Expense Optimization Guide</title></head><body>'
        '<h1>Section 179 Depreciation and Expensing</h1>'
        '<h2>Statutory Deduction Limits</h2>'
        '<h3>Eligible Property Types</h3>'
        '<p>Under IRC Section 179, qualifying business equipment qualifies for accelerated deduction.</p>'
        '<h2>Depreciation Schedule Comparison</h2>'
        '<table>'
        '<thead>'
        '<tr><th scope="col">Tax Year</th><th scope="col">Expensing Limit</th><th scope="col">Phase-out Cap</th></tr>'
        '</thead>'
        '<tbody>'
        '<tr><td>2025</td><td>$1,220,000</td><td>$3,050,000</td></tr>'
        '<tr><td>2026</td><td>$1,250,000</td><td>$3,130,000</td></tr>'
        '</tbody>'
        '</table>'
        '<h2>Calculation Procedure</h2>'
        '<p>Follow these steps to calculate deductible expense:</p>'
        '<ol>'
        '<li>Step 1: Calculate total qualified asset purchases for the tax year.</li>'
        '<li>Step 2: Determine dollar-for-dollar reduction above phase-out limit.</li>'
        '<li>Step 3: Elect deduction on IRS Form 4562 Election to Expense.</li>'
        '</ol>'
        '<p>This procedure guarantees accurate statutory computation for business returns.</p>'
        '</body></html>'
    )

    # Compliant assertion
    assert assert_extractable_content_structure(compliant_html) is True
    assert assert_extractable_structure(compliant_html) is True
    assert assert_content_structure_extractability(compliant_html) is True

    # Standalone 1: assert_semantic_heading_hierarchy
    assert assert_semantic_heading_hierarchy(compliant_html) is True
    assert assert_semantic_heading_hierarchy([1, 2, 3, 2, 3]) is True
    assert assert_semantic_heading_hierarchy([{"level": 1, "text": "H1"}, {"level": 2, "text": "H2"}]) is True

    with pytest.raises(ValueError, match="skipped level from h1 to h3"):
        assert_semantic_heading_hierarchy("<h1>Title</h1><h3>Skipped Subhead</h3>")

    with pytest.raises(ValueError, match="skipped level from h2 to h4"):
        assert_semantic_heading_hierarchy("<h1>Title</h1><h2>Subhead</h2><h4>Deep Jump</h4>")

    with pytest.raises(ValueError, match="starts with <h2> instead of <h1>"):
        assert_semantic_heading_hierarchy("<h2>No H1 Page</h2><p>Prose</p>")

    with pytest.raises(ValueError, match="empty heading tag"):
        assert_semantic_heading_hierarchy("<h1>Valid</h1><h2>   </h2>")

    with pytest.raises(ValueError, match=r"(?i)forbidden em-dash"):
        assert_semantic_heading_hierarchy("<h1>Section 179 " + chr(0x2014) + " Guide</h1>")

    # Standalone 2: assert_scoped_table_headers
    assert assert_scoped_table_headers(compliant_html) is True
    assert assert_scoped_table_headers({
        "headers": [{"text": "Year", "scope": "col"}, {"text": "Limit", "scope": "col"}],
        "rows": [["2025", "$1,000"]],
    }) is True

    with pytest.raises(ValueError, match="missing explicit scope=\"col\""):
        assert_scoped_table_headers(
            "<table><tr><th>Year</th><th>Limit</th></tr><tr><td>2025</td><td>$1000</td></tr></table>"
        )

    with pytest.raises(ValueError, match="missing <th> headers"):
        assert_scoped_table_headers(
            "<table><tr><td>Just Data</td><td>No Header</td></tr></table>"
        )

    with pytest.raises(ValueError, match="contains no data rows"):
        assert_scoped_table_headers(
            "<table><tr><th scope=\"col\">Year</th><th scope=\"col\">Limit</th></tr></table>"
        )

    with pytest.raises(ValueError, match="fewer than 2 columns"):
        assert_scoped_table_headers(
            "<table><tr><th scope=\"col\">Only One</th></tr><tr><td>Data</td></tr></table>"
        )

    with pytest.raises(ValueError, match=r"(?i)forbidden en-dash"):
        assert_scoped_table_headers(
            "<table><tr><th scope=\"col\">Year " + chr(0x2013) + " Term</th><th scope=\"col\">Cap</th></tr>"
            "<tr><td>2025</td><td>$1000</td></tr></table>"
        )

    # Standalone 3: assert_procedural_ordered_steps
    assert assert_procedural_ordered_steps(compliant_html) is True
    assert assert_procedural_ordered_steps(["Step 1: Setup", "Step 2: Run"]) is True

    with pytest.raises(ValueError, match="procedural steps must use ordered lists"):
        assert_procedural_ordered_steps(
            "<h2>Execution Procedure</h2>"
            "<ul><li>Step 1: Gather records</li><li>Step 2: File return</li></ul>"
        )

    with pytest.raises(ValueError, match="fewer than 2 steps"):
        assert_procedural_ordered_steps(
            "<h2>How to Calculate</h2>"
            "<ol><li>Step 1: Single lonely step</li></ol>"
        )

    with pytest.raises(ValueError, match=r"(?i)forbidden em-dash"):
        assert_procedural_ordered_steps(["Step 1: Init " + chr(0x2014) + " start", "Step 2: Finish"])

    # Standalone 4: assert_passage_level_blocks
    assert assert_passage_level_blocks(compliant_html) is True
    assert assert_passage_level_blocks(["Clean passage 1", "Clean passage 2"]) is True

    with pytest.raises(ValueError, match="contains empty <p> tag"):
        assert_passage_level_blocks("<p>First passage</p><p></p><p>Third passage</p>")

    with pytest.raises(ValueError, match="exceeds 2000 chars"):
        long_text = "Prose block. " * 200
        assert_passage_level_blocks(f"<p>{long_text}</p>")

    with pytest.raises(ValueError, match=r"(?i)forbidden en-dash"):
        assert_passage_level_blocks("<p>A passage with " + chr(0x2013) + " dash.</p>")


def test_verify_html_extractable_content_structure_in_memory():
    """Verifies in-memory HTML validation for Factor 10 across positive and negative permutations."""
    compliant_html = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>2026 Bonus Depreciation Guide</title></head><body>'
        '<h1>Bonus Depreciation Rules</h1>'
        '<h2>Phase-Out Schedule</h2>'
        '<h3>Annual Allowable Rates</h3>'
        '<p>Under the Tax Cuts and Jobs Act, bonus depreciation phases out annually.</p>'
        '<table>'
        '<thead>'
        '<tr><th scope="col">Property Placed in Service</th><th scope="col">Bonus Rate</th></tr>'
        '</thead>'
        '<tbody>'
        '<tr><td>2024</td><td>60%</td></tr>'
        '<tr><td>2025</td><td>40%</td></tr>'
        '<tr><td>2026</td><td>20%</td></tr>'
        '</tbody>'
        '</table>'
        '<h2>Implementation Steps</h2>'
        '<ol>'
        '<li>Step 1: Identify eligible tangible property with MACRS life of 20 years or less.</li>'
        '<li>Step 2: Multiply adjusted basis by applicable statutory percentage.</li>'
        '<li>Step 3: Deduct remaining basis under standard MACRS tables.</li>'
        '</ol>'
        '<p>Proper application ensures maximum first-year capital recovery.</p>'
        '</body></html>'
    )

    res_pass = verify_html_extractable_content_structure(compliant_html)
    assert res_pass["status"] == "PASS"
    assert res_pass["violations_count"] == 0
    assert res_pass["headings_count"] >= 3
    assert res_pass["tables_count"] >= 1
    assert res_pass["ordered_steps_count"] >= 3
    assert res_pass["has_heading_skips"] is False
    assert res_pass["has_unscoped_tables"] is False

    # Alias check
    res_alias = verify_html_extractable_structure(compliant_html)
    assert res_alias["status"] == "PASS"

    # Negative 1: Heading skip from h1 to h3
    html_hskip = compliant_html.replace("<h2>Phase-Out Schedule</h2>", "")
    res_hskip = verify_html_extractable_content_structure(html_hskip)
    assert res_hskip["status"] == "FAIL"
    assert any("Heading hierarchy violation" in i for i in res_hskip["issues"])
    assert any("skipped level from h1 to h3" in i for i in res_hskip["issues"])

    # Negative 2: Heading skip from h2 to h4
    html_h4skip = compliant_html.replace(
        "<h3>Annual Allowable Rates</h3>",
        "<h4>Annual Allowable Rates</h4>"
    )
    res_h4skip = verify_html_extractable_content_structure(html_h4skip)
    assert res_h4skip["status"] == "FAIL"
    assert any("skipped level from h2 to h4" in i for i in res_h4skip["issues"])

    # Negative 3: Starts with h2 instead of h1
    html_no_h1 = compliant_html.replace("<h1>Bonus Depreciation Rules</h1>", "<h2>Bonus Depreciation Rules</h2>")
    res_no_h1 = verify_html_extractable_content_structure(html_no_h1)
    assert res_no_h1["status"] == "FAIL"
    assert any("document starts with <h2> instead of <h1>" in i for i in res_no_h1["issues"])

    # Negative 4: Empty heading
    html_empty_h = compliant_html.replace("<h2>Phase-Out Schedule</h2>", "<h2>   </h2>")
    res_empty_h = verify_html_extractable_content_structure(html_empty_h)
    assert res_empty_h["status"] == "FAIL"
    assert any("Empty heading tag <h2>" in i for i in res_empty_h["issues"])

    # Negative 5: Table missing scope="col"
    html_unscoped = compliant_html.replace('scope="col"', '')
    res_unscoped = verify_html_extractable_content_structure(html_unscoped)
    assert res_unscoped["status"] == "FAIL"
    assert any("Table header accessibility violation" in i for i in res_unscoped["issues"])
    assert any("missing explicit column scope" in i for i in res_unscoped["issues"])

    # Negative 6: Table missing <th>
    html_no_th = compliant_html.replace('<th scope="col">', '<td>').replace('</th>', '</td>')
    res_no_th = verify_html_extractable_content_structure(html_no_th)
    assert res_no_th["status"] == "FAIL"
    assert any("missing structured <th> header cells" in i for i in res_no_th["issues"])

    # Negative 7: Procedural workflow in <ul>
    html_ul_steps = compliant_html.replace("<ol>", "<ul>").replace("</ol>", "</ul>")
    res_ul_steps = verify_html_extractable_content_structure(html_ul_steps)
    assert res_ul_steps["status"] == "FAIL"
    assert any("Procedural workflow violation" in i for i in res_ul_steps["issues"])
    assert any("found unordered bulleted list (<ul>)" in i for i in res_ul_steps["issues"])

    # Negative 8: Empty passage tag
    html_empty_p = compliant_html.replace(
        '<p>Under the Tax Cuts and Jobs Act, bonus depreciation phases out annually.</p>',
        '<p></p>'
    )
    res_empty_p = verify_html_extractable_content_structure(html_empty_p)
    assert res_empty_p["status"] == "FAIL"
    assert any("empty passage-level block" in i for i in res_empty_p["issues"])

    # Negative 9: Forbidden em-dash
    html_emdash = compliant_html.replace(
        "Bonus Depreciation Rules",
        "Bonus Depreciation " + chr(0x2014) + " Rules"
    )
    res_emdash = verify_html_extractable_content_structure(html_emdash)
    assert res_emdash["status"] == "FAIL"
    assert any("forbidden em-dash" in i for i in res_emdash["issues"])

    # Negative 10: Forbidden en-dash
    html_endash = compliant_html.replace(
        "Bonus Depreciation Rules",
        "Bonus Depreciation " + chr(0x2013) + " Rules"
    )
    res_endash = verify_html_extractable_content_structure(html_endash)
    assert res_endash["status"] == "FAIL"
    assert any("forbidden en-dash" in i for i in res_endash["issues"])

    # Negative 11: Non-string input
    res_nonstr = verify_html_extractable_content_structure(None)  # type: ignore
    assert res_nonstr["status"] == "FAIL"
    assert any("must be a string" in i for i in res_nonstr["issues"])


def test_check_extractable_content_structure_gate_disk_fixtures(tmp_path):
    """Verifies check_extractable_content_structure_gate on disk fixtures across positive and negative trees."""
    pos_dir = tmp_path / "pos_dist_factor10"
    pos_dir.mkdir()
    tool_dir = pos_dir / "tools" / "sec-179-calculator"
    tool_dir.mkdir(parents=True)

    compliant_page = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>2026 Section 179 Deduction Calculator</title>'
        '<meta name="description" content="Calculate statutory equipment expensing limits and phase-out reductions for 2026.">'
        '<link rel="canonical" href="https://profithelm.com/tools/sec-179-calculator/">'
        '</head><body>'
        '<h1>Section 179 Deduction Calculator</h1>'
        '<h2>Statutory Expensing Caps</h2>'
        '<h3>Annual Limits Table</h3>'
        '<p>Section 179 of the Internal Revenue Code allows businesses to deduct the full purchase price of qualifying equipment.</p>'
        '<table>'
        '<thead>'
        '<tr><th scope="col">Tax Year</th><th scope="col">Deduction Limit</th><th scope="col">Phase-Out Cap</th></tr>'
        '</thead>'
        '<tbody>'
        '<tr><td>2025</td><td>$1,220,000</td><td>$3,050,000</td></tr>'
        '<tr><td>2026</td><td>$1,250,000</td><td>$3,130,000</td></tr>'
        '</tbody>'
        '</table>'
        '<h2>Step-by-Step Calculation Guide</h2>'
        '<ol>'
        '<li>Step 1: Total all qualifying purchases placed in service during 2026.</li>'
        '<li>Step 2: Calculate dollar reduction if total purchases exceed $3,130,000.</li>'
        '<li>Step 3: Apply the business taxable income limitation to establish maximum deduction.</li>'
        '</ol>'
        '<p>Electing Section 179 on IRS Form 4562 reduces current-year taxable liabilities.</p>'
        '</body></html>'
    )
    (tool_dir / "index.html").write_text(compliant_page, encoding="utf-8")

    verifier = MasterSEOVerifier(dist_dir=pos_dir, domain="profithelm.com")
    res_pos = verifier.check_extractable_content_structure_gate(pos_dir)
    assert res_pos["status"] == "PASS"
    assert res_pos["pages_checked"] >= 1
    assert res_pos["headings_verified"] >= 3
    assert res_pos["tables_verified"] >= 1
    assert res_pos["ordered_steps_verified"] >= 3
    assert res_pos["violations_count"] == 0

    # Negative tree with multiple structural defects
    neg_dir = tmp_path / "neg_dist_factor10"
    neg_dir.mkdir()
    neg_tool1 = neg_dir / "tools" / "broken-headings"
    neg_tool1.mkdir(parents=True)
    neg_tool2 = neg_dir / "tools" / "unscoped-table"
    neg_tool2.mkdir(parents=True)
    neg_tool3 = neg_dir / "tools" / "unordered-procedure"
    neg_tool3.mkdir(parents=True)

    # Page 1: heading skip (h1 to h3)
    p1 = (
        '<!DOCTYPE html><html><head><title>Bad Headings</title></head><body>'
        '<h1>Heading One</h1>'
        '<h3>Skipped Level Three</h3>'
        '<p>Paragraph without intermediate heading rank.</p>'
        '</body></html>'
    )
    (neg_tool1 / "index.html").write_text(p1, encoding="utf-8")

    # Page 2: table headers lacking scope="col"
    p2 = (
        '<!DOCTYPE html><html><head><title>Unscoped Table</title></head><body>'
        '<h1>Table Page</h1>'
        '<table><tr><th>Header One</th><th>Header Two</th></tr><tr><td>Row 1</td><td>Row 2</td></tr></table>'
        '<p>Data table without accessible column scopes.</p>'
        '</body></html>'
    )
    (neg_tool2 / "index.html").write_text(p2, encoding="utf-8")

    # Page 3: procedural workflow in <ul>
    p3 = (
        '<!DOCTYPE html><html><head><title>Unordered Procedure</title></head><body>'
        '<h1>Workflow Page</h1>'
        '<h2>Calculation Procedure</h2>'
        '<ul><li>Step 1: First action</li><li>Step 2: Second action</li></ul>'
        '<p>Procedural workflow using bullets instead of ordered list.</p>'
        '</body></html>'
    )
    (neg_tool3 / "index.html").write_text(p3, encoding="utf-8")

    verifier_neg = MasterSEOVerifier(dist_dir=neg_dir, domain="profithelm.com")
    res_neg = verifier_neg.check_extractable_content_structure_gate(neg_dir)
    assert res_neg["status"] == "FAIL"
    assert res_neg["violations_count"] >= 3
    assert any("Heading hierarchy violation" in i for i in res_neg["issues"])
    assert any("Table header accessibility violation" in i for i in res_neg["issues"])
    assert any("Procedural workflow violation" in i for i in res_neg["issues"])


def test_gate_aliases_and_checklist_integration_factor10(tmp_path):
    """Verifies Factor 10 gate aliases and audit_seo_checklist integration."""
    pos_dir = tmp_path / "dist_factor10_integration"
    pos_dir.mkdir()
    tool_dir = pos_dir / "tools" / "qbi-calculator"
    tool_dir.mkdir(parents=True)

    compliant_page = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>Section 199A QBI Calculation Engine</title>'
        '<meta name="description" content="Structured Qualified Business Income deduction calculation engine with scoped tables.">'
        '<link rel="canonical" href="https://profithelm.com/tools/qbi-calculator/">'
        '</head><body>'
        '<h1>Section 199A QBI Calculator</h1>'
        '<h2>Statutory Phase-In Thresholds</h2>'
        '<h3>Filing Status Table</h3>'
        '<p>Under IRC Section 199A, pass-through businesses deduct up to twenty percent of qualified income.</p>'
        '<table>'
        '<thead>'
        '<tr><th scope="col">Filing Status</th><th scope="col">Lower Threshold</th><th scope="col">Upper Limit</th></tr>'
        '</thead>'
        '<tbody>'
        '<tr><td>Single</td><td>$197,300</td><td>$247,300</td></tr>'
        '<tr><td>Married Filing Jointly</td><td>$394,600</td><td>$494,600</td></tr>'
        '</tbody>'
        '</table>'
        '<h2>Step-by-Step Calculation Guide</h2>'
        '<ol>'
        '<li>Step 1: Compute tentative QBI component at 20% of net business income.</li>'
        '<li>Step 2: Check taxable income against the phase-in thresholds.</li>'
        '<li>Step 3: Apply W-2 wage and UBIA capital limitation if income exceeds threshold.</li>'
        '</ol>'
        '<p>This procedure guarantees accurate statutory computation for all entity types.</p>'
        '</body></html>'
    )
    (tool_dir / "index.html").write_text(compliant_page, encoding="utf-8")

    verifier = MasterSEOVerifier(dist_dir=pos_dir, domain="profithelm.com")

    # Verifier method aliases
    r1 = verifier.check_extractable_content_structure_gate(pos_dir)
    r2 = verifier.check_extractable_structure_gate(pos_dir)
    r3 = verifier.check_semantic_heading_hierarchy_gate(pos_dir)
    r4 = verifier.check_scoped_table_headers_gate(pos_dir)
    r5 = verifier.check_procedural_ordered_steps_gate(pos_dir)
    r6 = verifier.verify_extractable_content_structure(pos_dir)
    r7 = verifier.verify_extractable_structure(pos_dir)
    assert r1["status"] == r2["status"] == r3["status"] == r4["status"] == r5["status"] == r6["status"] == r7["status"] == "PASS"

    # Module-level aliases
    m1 = check_extractable_content_structure_gate(pos_dir)
    m2 = check_extractable_structure_gate(pos_dir)
    m3 = check_semantic_heading_hierarchy_gate(pos_dir)
    m4 = check_scoped_table_headers_gate(pos_dir)
    m5 = check_procedural_ordered_steps_gate(pos_dir)
    m6 = verify_extractable_content_structure(pos_dir)
    m7 = verify_extractable_structure(pos_dir)
    assert m1["status"] == m2["status"] == m3["status"] == m4["status"] == m5["status"] == m6["status"] == m7["status"] == "PASS"

    # In-memory HTML helper
    h_res = verify_html_extractable_content_structure(compliant_page)
    assert h_res["status"] == "PASS"
    assert h_res["violations_count"] == 0
    assert h_res["headings_count"] >= 3
    assert h_res["tables_count"] >= 1
    assert h_res["ordered_steps_count"] >= 3

    h_alias = verify_html_extractable_structure(compliant_page)
    assert h_alias["status"] == "PASS"

    # audit_seo_checklist integration
    home_page = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>ProfitHelm Platform Programmatic Tax Calculation Tools</title>'
        '<meta name="description" content="Access deterministic programmatic tax models, Section 179 depreciation tools, and business calculations.">'
        '<link rel="canonical" href="https://profithelm.com/">'
        '</head><body>'
        '<h1>ProfitHelm Programmatic Calculation Hub</h1>'
        '<a href="/tools/qbi-calculator/">QBI Tool</a>'
        '</body></html>'
    )
    (pos_dir / "index.html").write_text(home_page, encoding="utf-8")

    audit_res = verifier.audit_seo_checklist(pos_dir, enforce_relevance=False)
    assert "check_extractable_content_structure_gate" in audit_res["gates"]
    assert "check_extractable_structure_gate" in audit_res["gates"]
    assert "check_semantic_heading_hierarchy_gate" in audit_res["gates"]
    assert "check_scoped_table_headers_gate" in audit_res["gates"]
    assert "check_procedural_ordered_steps_gate" in audit_res["gates"]
    assert audit_res["gates"]["check_extractable_content_structure_gate"]["status"] == "PASS"


# =============================================================================
# Factor 11: Answer Prominence (+1.65) Tests
# =============================================================================


def test_factor11_spec_registration():
    """Verifies Factor 11 registration in ZYPPY_2026_AI_FACTORS_SPEC and factor resolver."""
    factor11 = ZYPPY_2026_AI_FACTORS_SPEC[10]
    assert factor11["code"] == "answer_prominence"
    assert factor11["name"] == "Answer Prominence"
    assert factor11["weight"] == 1.65
    assert factor11["positive_weight"] == 1.65
    assert factor11["negative_weight"] == -1.65

    # Aliases
    aliases = factor11.get("aliases", [])
    assert "Answer Prominence" in aliases
    assert "answer_prominence" in aliases
    assert "answer_above_fold" in aliases
    assert "core_answer_prominence" in aliases
    assert "direct_answer_prominence" in aliases
    assert "calculation_widget_prominence" in aliases
    assert "early_answer_block" in aliases
    assert "answer_position" in aliases
    assert "cumulative_body_word_position" in aliases
    assert "early_direct_answers" in aliases

    # get_ai_factor_spec lookups
    s1 = get_ai_factor_spec(11)
    assert s1 is not None and s1["code"] == "answer_prominence"
    s2 = get_ai_factor_spec("answer_prominence")
    assert s2 is not None and s2["weight"] == 1.65
    s3 = get_ai_factor_spec("Answer Prominence")
    assert s3 is not None and s3["code"] == "answer_prominence"
    s4 = get_ai_factor_spec("answer_above_fold")
    assert s4 is not None and s4["code"] == "answer_prominence"
    s5 = get_ai_factor_spec("core_answer_prominence")
    assert s5 is not None and s5["code"] == "answer_prominence"
    s6 = get_ai_factor_spec("direct_answer_prominence")
    assert s6 is not None and s6["code"] == "answer_prominence"
    s7 = get_ai_factor_spec("calculation_widget_prominence")
    assert s7 is not None and s7["code"] == "answer_prominence"
    s8 = get_ai_factor_spec("early_answer_block")
    assert s8 is not None and s8["code"] == "answer_prominence"
    s9 = get_ai_factor_spec("answer_position")
    assert s9 is not None and s9["code"] == "answer_prominence"
    s10 = get_ai_factor_spec("cumulative_body_word_position")
    assert s10 is not None and s10["code"] == "answer_prominence"
    s11 = get_ai_factor_spec("early_direct_answers")
    assert s11 is not None and s11["code"] == "answer_prominence"


def test_assert_answer_prominence_contract():
    """Verifies assert_answer_prominence boundary conditions and contract assertions."""
    compliant_direct_answer = (
        '<!DOCTYPE html><html lang="en"><head><title>2026 Standard Deduction Rates</title>'
        '<meta name="description" content="Official IRS standard deduction amounts for single and married filers.">'
        '</head><body>'
        '<header><nav><a href="/">Home</a><a href="/tools/">Tools</a><a href="/about/">About</a></nav></header>'
        '<h1>2026 Federal Standard Deduction</h1>'
        '<p>Under IRS Revenue Procedure 2024-34, standard deduction amounts adjust for annual inflation.</p>'
        '<div class="direct-answer">'
        'The 2026 federal standard deduction is $15,000 for single taxpayers and $30,000 for married couples filing jointly.'
        '</div>'
        '<h2>Secondary Discussion</h2>'
        '<p>Taxpayers may choose between standard deduction and itemized deductions on Schedule A.</p>'
        '</body></html>'
    )
    assert assert_answer_prominence(compliant_direct_answer) is True
    assert assert_answer_above_fold(compliant_direct_answer) is True
    assert assert_core_answer_prominence(compliant_direct_answer) is True
    assert assert_direct_answer_prominence(compliant_direct_answer) is True
    assert assert_calculation_widget_prominence(compliant_direct_answer) is True
    assert assert_early_answer_block(compliant_direct_answer) is True
    assert assert_answer_word_position(compliant_direct_answer) is True
    assert assert_direct_answer_or_widget_presence(compliant_direct_answer) is True
    assert assert_answer_above_the_fold(compliant_direct_answer) is True

    # Calculation widget with deep DOM nesting
    compliant_widget_deep_dom = (
        '<!DOCTYPE html><html lang="en"><head><title>QBI Calculation Tool</title>'
        '<meta name="description" content="Calculate your Section 199A deduction.">'
        '</head><body>'
        '<h1>Section 199A QBI Calculation Tool</h1>'
        '<p>Estimate pass-through business tax deductions under IRC Section 199A rules.</p>'
        '<main><div class="outer-shell"><section class="calculator-wrapper">'
        '<div class="calculator-card"><div class="interactive-container">'
        '<form id="qbi-calc" class="tax-calculator">'
        '<label for="income">Qualified Business Income</label>'
        '<input type="number" id="income" name="income" value="100000" />'
        '<button type="submit">Compute Deduction</button>'
        '</form>'
        '</div></div></section></div></main>'
        '<h2>Secondary Discussion</h2>'
        '<p>W-2 wage limitations apply once taxable income exceeds statutory thresholds.</p>'
        '</body></html>'
    )
    assert assert_answer_prominence(compliant_widget_deep_dom) is True

    # Surrounding markup / header exclusion
    header_nav_words = " ".join(["navigation-item"] * 100)
    html_heavy_header = (
        f'<!DOCTYPE html><html lang="en"><head><title>Section 179 Cap</title>'
        f'<meta name="description" content="Depreciation allowances."></head><body>'
        f'<header><nav><p>{header_nav_words}</p></nav></header>'
        f'<h1>Section 179 Expense Allowance</h1>'
        f'<p>For tax year 2026, eligible businesses write off qualifying equipment immediately.</p>'
        f'<div class="quick-answer">The Section 179 deduction limit is $1,250,000 with a $3,130,000 phase-out threshold.</div>'
        f'<h2>Secondary Discussion</h2><p>Equipment must be placed in service during the tax year.</p>'
        f'</body></html>'
    )
    meta_h = extract_answer_prominence_metadata(html_heavy_header)
    assert meta_h["answer_word_position"] < 30
    assert assert_answer_prominence(html_heavy_header) is True

    # Negative 1: Delayed answer past 300 words
    intro_350_words = " ".join([f"preamble{i}" for i in range(350)])
    html_delayed_answer = (
        f'<!DOCTYPE html><html lang="en"><head><title>Delayed Answer Page</title>'
        f'<meta name="description" content="Delayed answer."></head><body>'
        f'<h1>Delayed Answer Test</h1>'
        f'<p>{intro_350_words}</p>'
        f'<div class="direct-answer">The direct answer appears far too late after word 350.</div>'
        f'</body></html>'
    )
    with pytest.raises(ValueError, match="exceeding maximum threshold of 300 words"):
        assert_answer_prominence(html_delayed_answer)

    # Negative 2: Missing direct answer and calculation widget
    html_missing_answer = (
        '<!DOCTYPE html><html lang="en"><head><title>No Answer Page</title>'
        '<meta name="description" content="No answer."></head><body>'
        '<h1>Generic Overview Page</h1>'
        '<p>This page discusses various financial topics without providing a direct answer or widget.</p>'
        '<h2>Secondary Discussion</h2>'
        '<p>Further analysis of general principles.</p>'
        '</body></html>'
    )
    with pytest.raises(ValueError, match="missing direct answer or core calculation widget"):
        assert_answer_prominence(html_missing_answer)

    # Negative 3: Empty answer container
    html_empty_answer = (
        '<!DOCTYPE html><html lang="en"><head><title>Empty Answer Container</title>'
        '<meta name="description" content="Empty answer."></head><body>'
        '<h1>Empty Answer Test</h1>'
        '<div class="direct-answer">    </div>'
        '<h2>Secondary Discussion</h2>'
        '<p>Content after empty answer.</p>'
        '</body></html>'
    )
    with pytest.raises(ValueError, match="direct answer container is empty or lacks substantive content"):
        assert_answer_prominence(html_empty_answer)

    # Negative 4: Secondary discussion before direct answer
    html_secondary_before_answer = (
        '<!DOCTYPE html><html lang="en"><head><title>Premature Discussion</title>'
        '<meta name="description" content="Premature secondary discussion."></head><body>'
        '<h1>Premature Discussion Test</h1>'
        '<h2>Secondary Discussion</h2>'
        '<p>Elaborate background history presented before addressing the query.</p>'
        '<div class="direct-answer">Late answer placed after secondary discussion.</div>'
        '</body></html>'
    )
    with pytest.raises(ValueError, match="secondary discussion"):
        assert_answer_prominence(html_secondary_before_answer)

    # Negative 5: Forbidden em-dash
    html_emdash = compliant_direct_answer.replace(
        "federal standard deduction",
        "federal " + chr(0x2014) + " standard deduction"
    )
    with pytest.raises(ValueError, match="Forbidden em-dash"):
        assert_answer_prominence(html_emdash)

    # Negative 6: Forbidden en-dash
    html_endash = compliant_direct_answer.replace(
        "federal standard deduction",
        "federal " + chr(0x2013) + " standard deduction"
    )
    with pytest.raises(ValueError, match="Forbidden en-dash"):
        assert_answer_prominence(html_endash)

    # Negative 7: Non-string input
    with pytest.raises(ValueError, match="Content must be a string"):
        assert_answer_prominence(None)  # type: ignore


def test_verify_html_answer_prominence_in_memory():
    """Verifies verify_html_answer_prominence in-memory helper across positive and negative inputs."""
    compliant_html = (
        '<!DOCTYPE html><html lang="en"><head><title>Section 179 Expensing Thresholds</title>'
        '<meta name="description" content="Comprehensive review of Section 179 deduction limitations.">'
        '</head><body>'
        '<h1>Section 179 Expensing Thresholds</h1>'
        '<p>The Section 179 expensing deduction allows qualifying enterprises to write off tangible equipment.</p>'
        '<div class="direct-answer">'
        'Under IRC Section 179, the expensing limit for 2026 is $1,250,000 with a phase-out starting at $3,130,000.'
        '</div>'
        '<h2>Secondary Discussion</h2>'
        '<p>Bonus depreciation may be combined with Section 179 expensing under specified statutory conditions.</p>'
        '</body></html>'
    )
    res_pass = verify_html_answer_prominence(compliant_html)
    assert res_pass["status"] == "PASS"
    assert res_pass["violations_count"] == 0
    assert res_pass["answer_found"] is True
    assert res_pass["answer_type"] == "direct_answer"
    assert res_pass["is_above_fold"] is True
    assert res_pass["word_position"] <= 300
    assert res_pass["has_secondary_discussion_before_answer"] is False

    # Alias checks
    res_alias1 = verify_html_answer_above_fold(compliant_html)
    res_alias2 = verify_html_core_answer_prominence(compliant_html)
    assert res_alias1["status"] == res_alias2["status"] == "PASS"

    # Calculation widget page
    widget_html = (
        '<!DOCTYPE html><html lang="en"><head><title>Section 179 Depreciation Calculator</title>'
        '<meta name="description" content="Calculate equipment depreciation."></head><body>'
        '<h1>Section 179 Depreciation Calculator</h1>'
        '<form class="tax-calculator">'
        '<input type="number" name="cost" value="500000" />'
        '<button type="submit">Compute</button>'
        '</form>'
        '<h2>Secondary Discussion</h2><p>Equipment classification guide.</p>'
        '</body></html>'
    )
    res_widget = verify_html_answer_prominence(widget_html)
    assert res_widget["status"] == "PASS"
    assert res_widget["answer_type"] == "calculation_widget"
    assert res_widget["is_above_fold"] is True

    # Delayed answer
    intro_long = " ".join([f"preamble{i}" for i in range(350)])
    html_delayed = (
        f'<!DOCTYPE html><html><body><h1>Delayed</h1>'
        f'<p>{intro_long}</p>'
        f'<div class="direct-answer">Late answer block.</div></body></html>'
    )
    res_delayed = verify_html_answer_prominence(html_delayed)
    assert res_delayed["status"] == "FAIL"
    assert any("exceeding maximum threshold of 300 words" in i for i in res_delayed["issues"])

    # Missing answer
    html_none = '<!DOCTYPE html><html><body><h1>Title</h1><p>General discussion.</p></body></html>'
    res_none = verify_html_answer_prominence(html_none)
    assert res_none["status"] == "FAIL"
    assert any("missing direct answer or core calculation widget" in i for i in res_none["issues"])

    # Empty answer
    html_empty = '<!DOCTYPE html><html><body><h1>Title</h1><div class="direct-answer">   </div></body></html>'
    res_empty = verify_html_answer_prominence(html_empty)
    assert res_empty["status"] == "FAIL"
    assert any("direct answer container is empty" in i for i in res_empty["issues"])

    # Secondary discussion before answer
    html_sec = (
        '<!DOCTYPE html><html><body><h1>Title</h1>'
        '<h2>Secondary Discussion</h2><p>Discussion text.</p>'
        '<div class="direct-answer">Answer text.</div></body></html>'
    )
    res_sec = verify_html_answer_prominence(html_sec)
    assert res_sec["status"] == "FAIL"
    assert any("secondary discussion" in i for i in res_sec["issues"])

    # Non-string input
    res_nonstr = verify_html_answer_prominence(None)  # type: ignore
    assert res_nonstr["status"] == "FAIL"
    assert res_nonstr["violations_count"] == 1

    # Forbidden dashes
    html_em = compliant_html.replace(
        "Thresholds",
        "Thresholds " + chr(0x2014)
    )
    res_em = verify_html_answer_prominence(html_em)
    assert res_em["status"] == "FAIL"
    assert any("forbidden em-dash" in i for i in res_em["issues"])

    html_en = compliant_html.replace(
        "Thresholds",
        "Thresholds " + chr(0x2013)
    )
    res_en = verify_html_answer_prominence(html_en)
    assert res_en["status"] == "FAIL"
    assert any("forbidden en-dash" in i for i in res_en["issues"])


def test_check_answer_prominence_gate_disk_fixtures(tmp_path):
    """Verifies check_answer_prominence_gate on disk fixtures across positive and negative trees."""
    pos_dir = tmp_path / "dist_factor11_pos"
    pos_dir.mkdir()
    page_dir = pos_dir / "tools" / "section-179"
    page_dir.mkdir(parents=True)

    compliant_page = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>Section 179 Tax Deduction Calculator 2026</title>'
        '<meta name="description" content="Calculate your 2026 Section 179 depreciation deductions with interactive tools.">'
        '<link rel="canonical" href="https://profithelm.com/tools/section-179/">'
        '</head><body>'
        '<h1>Section 179 Deduction Calculator</h1>'
        '<div class="direct-answer">'
        'Under Section 179, qualifying businesses deduct up to $1,250,000 of equipment purchases for 2026.'
        '</div>'
        '<div class="calculation-widget">'
        '<form class="tax-calculator">'
        '<label for="equipment">Equipment Cost</label>'
        '<input type="number" id="equipment" name="equipment" value="250000" />'
        '<button type="submit">Calculate</button>'
        '</form>'
        '</div>'
        '<h2>Secondary Discussion</h2>'
        '<p>Equipment must be purchased and placed in service within the statutory calendar year.</p>'
        '</body></html>'
    )
    (page_dir / "index.html").write_text(compliant_page, encoding="utf-8")

    verifier = MasterSEOVerifier(dist_dir=pos_dir, domain="profithelm.com")
    res_pos = verifier.check_answer_prominence_gate(pos_dir)
    assert res_pos["status"] == "PASS"
    assert res_pos["pages_checked"] >= 1
    assert res_pos["answers_verified"] >= 1
    assert res_pos["violations_count"] == 0

    # Verifier method aliases
    assert verifier.check_answer_above_fold_gate(pos_dir)["status"] == "PASS"
    assert verifier.check_core_answer_prominence_gate(pos_dir)["status"] == "PASS"
    assert verifier.check_direct_answer_prominence_gate(pos_dir)["status"] == "PASS"
    assert verifier.check_calculation_widget_prominence_gate(pos_dir)["status"] == "PASS"
    assert verifier.check_early_answer_block_gate(pos_dir)["status"] == "PASS"
    assert verifier.verify_answer_prominence(pos_dir)["status"] == "PASS"
    assert verifier.verify_answer_above_fold(pos_dir)["status"] == "PASS"
    assert verifier.verify_core_answer_prominence(pos_dir)["status"] == "PASS"

    # Module-level aliases
    assert check_answer_prominence_gate(pos_dir)["status"] == "PASS"
    assert check_answer_above_fold_gate(pos_dir)["status"] == "PASS"
    assert check_core_answer_prominence_gate(pos_dir)["status"] == "PASS"
    assert check_direct_answer_prominence_gate(pos_dir)["status"] == "PASS"
    assert check_calculation_widget_prominence_gate(pos_dir)["status"] == "PASS"
    assert check_early_answer_block_gate(pos_dir)["status"] == "PASS"
    assert verify_answer_prominence(pos_dir)["status"] == "PASS"
    assert verify_answer_above_fold(pos_dir)["status"] == "PASS"
    assert verify_core_answer_prominence(pos_dir)["status"] == "PASS"

    # Negative tree
    neg_dir = tmp_path / "dist_factor11_neg"
    neg_dir.mkdir()
    delayed_dir = neg_dir / "tools" / "delayed-tool"
    delayed_dir.mkdir(parents=True)
    no_answer_dir = neg_dir / "tools" / "no-answer-tool"
    no_answer_dir.mkdir(parents=True)

    long_intro = " ".join([f"paragraph{i}" for i in range(350)])
    delayed_page = (
        f'<!DOCTYPE html><html lang="en"><head><title>Delayed Page</title>'
        f'<meta name="description" content="Delayed."></head><body>'
        f'<h1>Delayed Page</h1>'
        f'<p>{long_intro}</p>'
        f'<div class="direct-answer">Late answer after 350 words.</div>'
        f'</body></html>'
    )
    (delayed_dir / "index.html").write_text(delayed_page, encoding="utf-8")

    no_answer_page = (
        '<!DOCTYPE html><html lang="en"><head><title>No Answer Page</title>'
        '<meta name="description" content="No answer."></head><body>'
        '<h1>No Answer Page</h1>'
        '<p>Discussion without any direct answer container or calculation widget.</p>'
        '</body></html>'
    )
    (no_answer_dir / "index.html").write_text(no_answer_page, encoding="utf-8")

    verifier_neg = MasterSEOVerifier(dist_dir=neg_dir, domain="profithelm.com")
    res_neg = verifier_neg.check_answer_prominence_gate(neg_dir)
    assert res_neg["status"] == "FAIL"
    assert res_neg["violations_count"] >= 2
    assert any("exceeding maximum threshold of 300 words" in i for i in res_neg["issues"])
    assert any("missing direct answer or core calculation widget" in i for i in res_neg["issues"])


def test_gate_aliases_and_checklist_integration_factor11(tmp_path):
    """Verifies Factor 11 gate aliases and audit_seo_checklist integration."""
    pos_dir = tmp_path / "dist_factor11_integration"
    pos_dir.mkdir()
    tool_dir = pos_dir / "tools" / "qbi-calculator"
    tool_dir.mkdir(parents=True)

    compliant_page = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>Section 199A QBI Calculation Engine</title>'
        '<meta name="description" content="Structured Qualified Business Income deduction calculation engine with early direct answer.">'
        '<link rel="canonical" href="https://profithelm.com/tools/qbi-calculator/">'
        '</head><body>'
        '<h1>Section 199A QBI Calculator</h1>'
        '<div class="direct-answer">'
        'Under IRC Section 199A, eligible small business owners deduct up to 20% of qualified business income.'
        '</div>'
        '<form class="tax-calculator">'
        '<label for="qbi">QBI Amount</label>'
        '<input type="number" id="qbi" name="qbi" value="100000" />'
        '<button type="submit">Calculate</button>'
        '</form>'
        '<h2>Statutory Phase-In Thresholds</h2>'
        '<p>Phase-in limits apply once taxable income exceeds statutory thresholds.</p>'
        '</body></html>'
    )
    (tool_dir / "index.html").write_text(compliant_page, encoding="utf-8")

    home_page = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>ProfitHelm Platform Programmatic Tax Calculation Tools</title>'
        '<meta name="description" content="Access deterministic programmatic tax models, Section 179 depreciation tools, and business calculations.">'
        '<link rel="canonical" href="https://profithelm.com/">'
        '</head><body>'
        '<h1>ProfitHelm Programmatic Calculation Hub</h1>'
        '<a href="/tools/qbi-calculator/">QBI Tool</a>'
        '</body></html>'
    )
    (pos_dir / "index.html").write_text(home_page, encoding="utf-8")

    verifier = MasterSEOVerifier(dist_dir=pos_dir, domain="profithelm.com")
    audit_res = verifier.audit_seo_checklist(pos_dir, enforce_relevance=False)
    assert "check_answer_prominence_gate" in audit_res["gates"]
    assert "check_answer_above_fold_gate" in audit_res["gates"]
    assert "check_core_answer_prominence_gate" in audit_res["gates"]
    assert "check_direct_answer_prominence_gate" in audit_res["gates"]
    assert "check_calculation_widget_prominence_gate" in audit_res["gates"]
    assert "check_early_answer_block_gate" in audit_res["gates"]
    assert audit_res["gates"]["check_answer_prominence_gate"]["status"] == "PASS"


# =============================================================================
# Factor 12: Structured Data (+0.80) Tests
# =============================================================================


def test_factor12_spec_registration():
    """Verifies Factor 12 registration in ZYPPY_2026_AI_FACTORS_SPEC and factor resolver."""
    factor12 = [f for f in ZYPPY_2026_AI_FACTORS_SPEC if f["code"] == "structured_data"][0]
    assert factor12["code"] == "structured_data"
    assert factor12["name"] == "Structured Data"
    assert factor12["weight"] == 0.80
    assert factor12["positive_weight"] == 0.80
    assert factor12["negative_weight"] == -0.80

    # Aliases
    aliases = factor12.get("aliases", [])
    assert "Structured Data" in aliases
    assert "structured_data" in aliases
    assert "structured_data_markup" in aliases
    assert "schema_org_structured_data" in aliases
    assert "jsonld_structured_data" in aliases
    assert "schema_graphs" in aliases
    assert "target_entity_schemas" in aliases
    assert "machine_readable_schemas" in aliases

    # Monotonic weights across all 14 factors
    weights = [f["weight"] for f in ZYPPY_2026_AI_FACTORS_SPEC]
    assert weights == sorted(weights, reverse=True)

    # get_ai_factor_spec lookups
    s1 = get_ai_factor_spec("structured_data")
    assert s1 is not None and s1["code"] == "structured_data"
    s2 = get_ai_factor_spec("Structured Data")
    assert s2 is not None and s2["weight"] == 0.80
    s3 = get_ai_factor_spec("structured_data_markup")
    assert s3 is not None and s3["code"] == "structured_data"
    s4 = get_ai_factor_spec("schema_org_structured_data")
    assert s4 is not None and s4["code"] == "structured_data"
    s5 = get_ai_factor_spec("jsonld_structured_data")
    assert s5 is not None and s5["code"] == "structured_data"
    s6 = get_ai_factor_spec("schema_graphs")
    assert s6 is not None and s6["code"] == "structured_data"
    s7 = get_ai_factor_spec("target_entity_schemas")
    assert s7 is not None and s7["code"] == "structured_data"
    s8 = get_ai_factor_spec("machine_readable_schemas")
    assert s8 is not None and s8["code"] == "structured_data"

    # Re-exports
    assert seo_verifier.ZYPPY_2026_AI_FACTORS_SPEC is ZYPPY_2026_AI_FACTORS_SPEC
    assert pseofactory.ZYPPY_2026_AI_FACTORS_SPEC is ZYPPY_2026_AI_FACTORS_SPEC


def test_assert_structured_data_contract_six_target_schemas():
    """Verifies valid markup and contract assertions across all six target entity schemas."""
    # 1. SoftwareApplication
    html_software = (
        '<!DOCTYPE html><html lang="en"><head><title>Tax Calculator Engine</title>'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "SoftwareApplication", '
        '"name": "ProfitHelm Tax Engine", "applicationCategory": "BusinessApplication", '
        '"operatingSystem": "All", "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}}'
        '</script></head><body><h1>Tax Calculator</h1></body></html>'
    )
    assert assert_structured_data(html_software) is True
    assert assert_target_entity_schemas(html_software) is True
    assert assert_schema_org_jsonld(html_software) is True
    assert assert_valid_structured_data(html_software) is True
    assert assert_machine_readable_schema(html_software) is True
    assert assert_schema_graph_connectivity(html_software) is True

    # 2. WebApplication
    html_webapp = (
        '<!DOCTYPE html><html lang="en"><head><title>QBI Web App</title>'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "WebApplication", '
        '"name": "QBI Calculation Portal", "browserRequirements": "Requires JavaScript", '
        '"applicationCategory": "FinanceApplication"}'
        '</script></head><body><h1>QBI Portal</h1></body></html>'
    )
    assert assert_structured_data(html_webapp) is True
    assert assert_target_entity_schemas(html_webapp) is True

    # 3. Product
    html_product = (
        '<!DOCTYPE html><html lang="en"><head><title>Tax Planning Suite</title>'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "Product", '
        '"name": "ProfitHelm Platform Suite", "description": "Deterministic tax computation suite", '
        '"offers": {"@type": "Offer", "price": "299", "priceCurrency": "USD"}}'
        '</script></head><body><h1>Tax Planning Suite</h1></body></html>'
    )
    assert assert_structured_data(html_product) is True
    assert assert_target_entity_schemas(html_product) is True

    # 4. FAQPage
    html_faq = (
        '<!DOCTYPE html><html lang="en"><head><title>Section 179 FAQ</title>'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "FAQPage", '
        '"mainEntity": [{'
        '"@type": "Question", "name": "What is the 2026 Section 179 limit?", '
        '"acceptedAnswer": {"@type": "Answer", "text": "The limit is 1250000 dollars."}'
        '}]}'
        '</script></head><body><h1>FAQ</h1></body></html>'
    )
    assert assert_structured_data(html_faq) is True
    assert assert_target_entity_schemas(html_faq) is True

    # 5. HowTo
    html_howto = (
        '<!DOCTYPE html><html lang="en"><head><title>How to Calculate QBI</title>'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "HowTo", '
        '"name": "How to Calculate Section 199A QBI Deduction", '
        '"step": ['
        '{"@type": "HowToStep", "text": "Determine qualified business income from trade or business."}, '
        '{"@type": "HowToStep", "text": "Multiply eligible QBI by 20 percent statutory deduction rate."}'
        ']}'
        '</script></head><body><h1>HowTo Guide</h1></body></html>'
    )
    assert assert_structured_data(html_howto) is True
    assert assert_target_entity_schemas(html_howto) is True

    # 6. Dataset
    html_dataset = (
        '<!DOCTYPE html><html lang="en"><head><title>Historical Tax Brackets Dataset</title>'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "Dataset", '
        '"name": "Federal Statutory Income Tax Schedules 2024-2026", '
        '"description": "Complete statutory marginal rate brackets and standard deduction schedules."}'
        '</script></head><body><h1>Dataset</h1></body></html>'
    )
    assert assert_structured_data(html_dataset) is True
    assert assert_target_entity_schemas(html_dataset) is True


def test_structured_data_graph_architecture_and_connectivity():
    """Verifies schema graph architecture, unified graphs, leaf entity anchoring, and broken reference detection."""
    # Valid unified graph with relational property references
    valid_graph = (
        '<!DOCTYPE html><html lang="en"><head><title>Unified Graph App</title>'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@graph": ['
        '{"@type": "SoftwareApplication", "@id": "https://profithelm.com/#app", '
        '"name": "Tax Calculator Pro", "applicationCategory": "FinanceApplication", '
        '"offers": {"@id": "https://profithelm.com/#free-offer"}}, '
        '{"@type": "Offer", "@id": "https://profithelm.com/#free-offer", '
        '"price": "0", "priceCurrency": "USD"}'
        ']}'
        '</script></head><body><h1>Unified Graph</h1></body></html>'
    )
    assert assert_structured_data(valid_graph) is True
    assert assert_schema_graph_connectivity(valid_graph) is True

    # Unanchored leaf entity floating disconnectedly in graph
    unanchored_leaf = (
        '<!DOCTYPE html><html lang="en"><head><title>Unanchored Leaf</title>'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@graph": ['
        '{"@type": "SoftwareApplication", "@id": "https://profithelm.com/#app", '
        '"name": "Tax Calculator", "applicationCategory": "BusinessApplication"}, '
        '{"@type": "Offer", "@id": "https://profithelm.com/#floating-offer", "price": "100"}'
        ']}'
        '</script></head><body><h1>Unanchored</h1></body></html>'
    )
    issues_leaf = detect_structured_data_issues(unanchored_leaf)
    assert any("Unanchored leaf entity 'Offer' floats disconnectedly" in i for i in issues_leaf)
    with pytest.raises(ValueError, match="unanchored leaf entity"):
        assert_schema_graph_connectivity(unanchored_leaf)

    # Broken graph reference to non-existent @id
    broken_ref = (
        '<!DOCTYPE html><html lang="en"><head><title>Broken Reference</title>'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@graph": ['
        '{"@type": "SoftwareApplication", "@id": "https://profithelm.com/#app", '
        '"name": "Tax App", "applicationCategory": "BusinessApplication", '
        '"offers": {"@id": "https://profithelm.com/#nonexistent-offer"}}'
        ']}'
        '</script></head><body><h1>Broken Ref</h1></body></html>'
    )
    issues_broken = detect_structured_data_issues(broken_ref)
    assert any("Broken graph reference in 'SoftwareApplication'" in i for i in issues_broken)
    with pytest.raises(ValueError, match="broken graph reference"):
        assert_schema_graph_connectivity(broken_ref)

    # Multiple disconnected script tags
    disconnected_scripts = (
        '<!DOCTYPE html><html lang="en"><head><title>Disconnected Scripts</title>'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "SoftwareApplication", "name": "App One", "applicationCategory": "Business"}'
        '</script>'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "Product", "name": "Product Two", "description": "Standalone product"}'
        '</script></head><body><h1>Disconnected</h1></body></html>'
    )
    issues_disc = detect_structured_data_issues(disconnected_scripts)
    assert any("Multiple disconnected application/ld+json script tags detected" in i for i in issues_disc)
    with pytest.raises(ValueError, match="multiple disconnected application/ld\\+json script tags"):
        assert_schema_graph_connectivity(disconnected_scripts)


def test_structured_data_edge_cases_and_malformed_states():
    """Verifies boundary conditions: parse errors, unregistered types, forbidden dashes, missing schemas."""
    # 1. Unregistered schema type
    html_unregistered = (
        '<!DOCTYPE html><html lang="en"><head><title>Unregistered</title>'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "CustomBogusWidget", "name": "Fake Widget"}'
        '</script></head><body><h1>Bogus</h1></body></html>'
    )
    issues_unreg = detect_structured_data_issues(html_unregistered)
    assert any("Unregistered schema type 'CustomBogusWidget'" in i for i in issues_unreg)
    with pytest.raises(ValueError, match="Unregistered schema type"):
        assert_structured_data(html_unregistered)

    # 2. Syntax parse error in JSON-LD
    html_malformed_json = (
        '<!DOCTYPE html><html lang="en"><head><title>Bad JSON</title>'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "SoftwareApplication", "name": "Broken",,}'
        '</script></head><body><h1>Bad JSON</h1></body></html>'
    )
    res_bad = verify_html_structured_data(html_malformed_json)
    assert res_bad["status"] == "FAIL"
    assert any("Invalid JSON-LD syntax" in i for i in res_bad["issues"])

    # 3. Missing or invalid @context
    html_no_ctx = (
        '<!DOCTYPE html><html lang="en"><head><title>No Context</title>'
        '<script type="application/ld+json">'
        '{"@type": "SoftwareApplication", "name": "No Context App", "applicationCategory": "Business"}'
        '</script></head><body><h1>No Context</h1></body></html>'
    )
    issues_no_ctx = detect_structured_data_issues(html_no_ctx)
    assert any("Missing or invalid @context" in i for i in issues_no_ctx)

    # 4. Irrelevant tags ignored
    html_with_irrelevant_tags = (
        '<!DOCTYPE html><html lang="en"><head><title>With Styles and Scripts</title>'
        '<style>.hero { color: red; }</style>'
        '<script type="text/javascript">var x = 42;</script>'
        '<!-- HTML comment ignoring irrelevant content -->'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "SoftwareApplication", '
        '"name": "Robust App", "applicationCategory": "FinanceApplication"}'
        '</script></head><body>'
        '<noscript><p>Please enable JS.</p></noscript>'
        '<h1>Robust App</h1></body></html>'
    )
    res_irrelevant = verify_html_structured_data(html_with_irrelevant_tags)
    assert res_irrelevant["status"] == "PASS"

    # 5. Non-string input handling
    res_null = verify_html_structured_data(None)  # type: ignore
    assert res_null["status"] == "FAIL"
    assert res_null["violations_count"] == 1

    # 6. Malformed target schemas
    # FAQPage without mainEntity
    bad_faq = (
        '<!DOCTYPE html><html lang="en"><head><title>Empty FAQ</title>'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "FAQPage"}'
        '</script></head><body><h1>FAQ</h1></body></html>'
    )
    issues_bad_faq = detect_structured_data_issues(bad_faq)
    assert any("missing or empty 'mainEntity'" in i for i in issues_bad_faq)

    # HowTo without steps
    bad_howto = (
        '<!DOCTYPE html><html lang="en"><head><title>Empty HowTo</title>'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "HowTo", "name": "Empty Guide"}'
        '</script></head><body><h1>HowTo</h1></body></html>'
    )
    issues_bad_howto = detect_structured_data_issues(bad_howto)
    assert any("missing or empty 'step'" in i for i in issues_bad_howto)

    # Dataset without description
    bad_dataset = (
        '<!DOCTYPE html><html lang="en"><head><title>No Desc Dataset</title>'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "Dataset", "name": "Tax Rates"}'
        '</script></head><body><h1>Dataset</h1></body></html>'
    )
    issues_bad_dataset = detect_structured_data_issues(bad_dataset)
    assert any("missing or empty 'description'" in i for i in issues_bad_dataset)

    # 7. Strict anti-slop: em-dash and en-dash detection
    good_html = (
        '<!DOCTYPE html><html lang="en"><head><title>Clean App</title>'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "SoftwareApplication", "name": "CleanApp", "applicationCategory": "Business"}'
        '</script></head><body><h1>Clean App</h1></body></html>'
    )
    html_em = good_html.replace("Clean App", "Clean App " + chr(0x2014))
    res_em = verify_html_structured_data(html_em)
    assert res_em["status"] == "FAIL"
    assert any("forbidden em-dash" in i for i in res_em["issues"])

    html_en = good_html.replace("Clean App", "Clean App " + chr(0x2013))
    res_en = verify_html_structured_data(html_en)
    assert res_en["status"] == "FAIL"
    assert any("forbidden en-dash" in i for i in res_en["issues"])


def test_check_structured_data_gate_disk_fixtures(tmp_path):
    """Verifies check_structured_data_gate on disk fixtures across positive and negative trees."""
    pos_dir = tmp_path / "dist_factor12_pos"
    pos_dir.mkdir()
    app_dir = pos_dir / "tools" / "qbi-calculator"
    app_dir.mkdir(parents=True)

    compliant_page = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>Section 199A QBI Calculation Tool</title>'
        '<meta name="description" content="Calculate qualified business income deductions with Schema.org markup.">'
        '<link rel="canonical" href="https://profithelm.com/tools/qbi-calculator/">'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "SoftwareApplication", '
        '"name": "ProfitHelm QBI Calculator", "applicationCategory": "FinanceApplication", '
        '"operatingSystem": "All", "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}}'
        '</script>'
        '</head><body>'
        '<h1>Section 199A QBI Calculator</h1>'
        '<p>Calculate deductions under statutory rules.</p>'
        '</body></html>'
    )
    (app_dir / "index.html").write_text(compliant_page, encoding="utf-8")

    verifier = MasterSEOVerifier(dist_dir=pos_dir, domain="profithelm.com")
    res_pos = verifier.check_structured_data_gate(pos_dir)
    assert res_pos["status"] == "PASS"
    assert res_pos["pages_checked"] >= 1
    assert res_pos["schemas_verified"] >= 1
    assert res_pos["target_entities_verified"] >= 1
    assert res_pos["violations_count"] == 0

    # Verifier method aliases
    assert verifier.check_schema_org_structured_data_gate(pos_dir)["status"] == "PASS"
    assert verifier.check_jsonld_structured_data_gate(pos_dir)["status"] == "PASS"
    assert verifier.check_schema_graphs_gate(pos_dir)["status"] == "PASS"
    assert verifier.check_target_entity_schemas_gate(pos_dir)["status"] == "PASS"
    assert verifier.check_machine_readable_schemas_gate(pos_dir)["status"] == "PASS"
    assert verifier.verify_structured_data(pos_dir)["status"] == "PASS"
    assert verifier.verify_schema_org_structured_data(pos_dir)["status"] == "PASS"
    assert verifier.verify_jsonld_structured_data(pos_dir)["status"] == "PASS"
    assert verifier.verify_schema_graphs(pos_dir)["status"] == "PASS"

    # Module-level aliases
    assert check_structured_data_gate(pos_dir)["status"] == "PASS"
    assert check_schema_org_structured_data_gate(pos_dir)["status"] == "PASS"
    assert check_jsonld_structured_data_gate(pos_dir)["status"] == "PASS"
    assert check_schema_graphs_gate(pos_dir)["status"] == "PASS"
    assert check_target_entity_schemas_gate(pos_dir)["status"] == "PASS"
    assert check_machine_readable_schemas_gate(pos_dir)["status"] == "PASS"
    assert verify_structured_data(pos_dir)["status"] == "PASS"
    assert verify_schema_org_structured_data(pos_dir)["status"] == "PASS"
    assert verify_jsonld_structured_data(pos_dir)["status"] == "PASS"
    assert verify_schema_graphs(pos_dir)["status"] == "PASS"

    # Negative tree with malformed schema
    neg_dir = tmp_path / "dist_factor12_neg"
    neg_dir.mkdir()
    bad_dir = neg_dir / "tools" / "broken-tool"
    bad_dir.mkdir(parents=True)

    broken_page = (
        '<!DOCTYPE html><html lang="en"><head><title>Broken Tool</title>'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "SoftwareApplication", "name": "Broken App", '
        '"offers": {"@id": "https://profithelm.com/#missing"}}'
        '</script></head><body><h1>Broken Tool</h1></body></html>'
    )
    (bad_dir / "index.html").write_text(broken_page, encoding="utf-8")

    verifier_neg = MasterSEOVerifier(dist_dir=neg_dir, domain="profithelm.com")
    res_neg = verifier_neg.check_structured_data_gate(neg_dir)
    assert res_neg["status"] == "FAIL"
    assert res_neg["violations_count"] >= 1
    assert any("Broken graph reference" in i for i in res_neg["issues"])


def test_gate_aliases_and_checklist_integration_factor12(tmp_path):
    """Verifies Factor 12 gate aliases and audit_seo_checklist integration."""
    pos_dir = tmp_path / "dist_factor12_integration"
    pos_dir.mkdir()
    tool_dir = pos_dir / "tools" / "qbi-calculator"
    tool_dir.mkdir(parents=True)

    compliant_page = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>Section 199A QBI Calculation Tool</title>'
        '<meta name="description" content="Structured Qualified Business Income deduction calculation tool.">'
        '<link rel="canonical" href="https://profithelm.com/tools/qbi-calculator/">'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "SoftwareApplication", '
        '"name": "ProfitHelm QBI Engine", "applicationCategory": "FinanceApplication", '
        '"operatingSystem": "All", "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}}'
        '</script>'
        '</head><body>'
        '<h1>Section 199A QBI Calculator</h1>'
        '<div class="direct-answer">'
        'Under IRC Section 199A, eligible small business owners deduct up to 20% of qualified business income.'
        '</div>'
        '</body></html>'
    )
    (tool_dir / "index.html").write_text(compliant_page, encoding="utf-8")

    home_page = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>ProfitHelm Platform Programmatic Tax Calculation Tools</title>'
        '<meta name="description" content="Access deterministic programmatic tax models and business tools.">'
        '<link rel="canonical" href="https://profithelm.com/">'
        '</head><body>'
        '<h1>ProfitHelm Programmatic Calculation Hub</h1>'
        '<a href="/tools/qbi-calculator/">QBI Tool</a>'
        '</body></html>'
    )
    (pos_dir / "index.html").write_text(home_page, encoding="utf-8")

    verifier = MasterSEOVerifier(dist_dir=pos_dir, domain="profithelm.com")
    audit_res = verifier.audit_seo_checklist(pos_dir, enforce_relevance=False)
    assert "check_structured_data_gate" in audit_res["gates"]
    assert "check_schema_org_structured_data_gate" in audit_res["gates"]
    assert "check_jsonld_structured_data_gate" in audit_res["gates"]
    assert "check_schema_graphs_gate" in audit_res["gates"]
    assert "check_target_entity_schemas_gate" in audit_res["gates"]
    assert "check_machine_readable_schemas_gate" in audit_res["gates"]
    assert audit_res["gates"]["check_structured_data_gate"]["status"] == "PASS"


# =============================================================================
# Factor 13: llms.txt File (+0.05) Tests
# =============================================================================


def test_factor13_spec_registration():
    """Verifies Factor 13 registration in ZYPPY_2026_AI_FACTORS_SPEC and factor resolver."""
    factor13 = [f for f in ZYPPY_2026_AI_FACTORS_SPEC if f["code"] == "llms_txt"][0]
    assert factor13["code"] == "llms_txt"
    assert factor13["name"] == "llms.txt File"
    assert factor13["factor"] == "llms.txt File"
    assert factor13["weight"] == 0.05
    assert factor13["positive_weight"] == 0.05
    assert factor13["negative_weight"] == -0.05

    # Aliases
    aliases = factor13.get("aliases", [])
    assert "llms.txt File" in aliases
    assert "llms.txt" in aliases
    assert "llms_txt_file" in aliases
    assert "llms_txt" in aliases
    assert "llms_full_txt" in aliases
    assert "llmstxt" in aliases
    assert "llms_txt_manifest" in aliases
    assert "curated_llms_txt" in aliases
    assert "Factor 13" in aliases

    # Monotonic weights across all 14 factors
    weights = [f["weight"] for f in ZYPPY_2026_AI_FACTORS_SPEC]
    assert weights == sorted(weights, reverse=True)
    assert weights[-1] == 0.05

    # get_ai_factor_spec lookups
    s_idx = get_ai_factor_spec(14)
    assert s_idx is not None and s_idx["code"] == "llms_txt"

    s_code = get_ai_factor_spec("llms_txt")
    assert s_code is not None and s_code["code"] == "llms_txt"

    s_alias = get_ai_factor_spec("llms_txt_file")
    assert s_alias is not None and s_alias["weight"] == 0.05

    s_name = get_ai_factor_spec("llms.txt File")
    assert s_name is not None and s_name["code"] == "llms_txt"

    s_short = get_ai_factor_spec("llms.txt")
    assert s_short is not None and s_short["code"] == "llms_txt"

    s_full = get_ai_factor_spec("llms_full_txt")
    assert s_full is not None and s_full["code"] == "llms_txt"

    s_manifest = get_ai_factor_spec("llms_txt_manifest")
    assert s_manifest is not None and s_manifest["code"] == "llms_txt"

    s_curated = get_ai_factor_spec("curated_llms_txt")
    assert s_curated is not None and s_curated["code"] == "llms_txt"

    s_factor13 = get_ai_factor_spec("Factor 13")
    assert s_factor13 is not None and s_factor13["code"] == "llms_txt"

    # Re-exports
    assert seo_verifier.ZYPPY_2026_AI_FACTORS_SPEC is ZYPPY_2026_AI_FACTORS_SPEC
    assert pseofactory.ZYPPY_2026_AI_FACTORS_SPEC is ZYPPY_2026_AI_FACTORS_SPEC


def test_extract_llms_txt_metadata_and_parsing():
    """Verifies extract_llms_txt_metadata parses compliant and malformed manifests."""
    compliant_content = (
        "# ProfitHelm Platform\n\n"
        "> Deterministic programmatic calculation engine for US statutory tax codes.\n\n"
        "## Top Category Hubs\n\n"
        "- [Section 199A QBI Calculator](/tools/qbi-calculator/): Interactive model evaluating qualified business income deductions.\n"
        "- [Depreciation Schedule Tool](/tools/depreciation/): Deterministic asset depreciation schedules adhering to MACRS.\n\n"
        "## Optional\n\n"
        "- [Full Documentation](/llms-full.txt): Complete expanded reference documentation.\n"
    )
    meta = extract_llms_txt_metadata(compliant_content)
    assert meta["has_h1"] is True
    assert meta["title"] == "ProfitHelm Platform"
    assert meta["has_blockquote"] is True
    assert "Deterministic programmatic calculation engine" in meta["summary"]
    assert len(meta["sections"]) == 2
    assert len(meta["links"]) == 3
    assert len(meta["category_hubs"]) == 2
    assert meta["is_llmstxt_compliant"] is True
    assert meta["leaked_routes"] == []
    assert meta["forbidden_dashes"] == []

    # Non-string input
    meta_none = extract_llms_txt_metadata(None)
    assert meta_none["has_h1"] is False
    assert meta_none["is_llmstxt_compliant"] is False

    # Empty string
    meta_empty = extract_llms_txt_metadata("")
    assert meta_empty["has_h1"] is False

    # Leaked route detection
    leaked_content = (
        "# Leaked Platform\n\n"
        "> Brief summary.\n\n"
        "## Top Category Hubs\n\n"
        "- [Admin Panel](/admin/dashboard): Administrative configuration.\n"
    )
    meta_leak = extract_llms_txt_metadata(leaked_content)
    assert any("/admin/" in r for r in meta_leak["leaked_routes"])
    assert meta_leak["is_llmstxt_compliant"] is False


def test_detect_llms_txt_issues_boundary_conditions():
    """Verifies detect_llms_txt_issues detects all edge case violations."""
    # Compliant manifest
    compliant = (
        "# ProfitHelm Platform\n\n"
        "> Deterministic programmatic calculation engine for statutory tax codes.\n\n"
        "## Top Category Hubs\n\n"
        "- [Section 199A Calculator](/tools/qbi-calculator/): Concise summary of QBI calculation rules.\n"
        "- [Depreciation Model](/tools/depreciation/): Concise summary of MACRS depreciation.\n\n"
        "## Optional\n\n"
        "- [Full Manifest](/llms-full.txt): Complete reference documentation.\n"
    )
    assert detect_llms_txt_issues(compliant) == []

    # Non-string
    assert "must be a string" in detect_llms_txt_issues(123)[0]

    # Empty
    assert "is empty" in detect_llms_txt_issues("   ")[0]

    # Missing H1 title
    no_h1 = (
        "> Deterministic programmatic calculation engine.\n\n"
        "## Top Category Hubs\n\n"
        "- [QBI Tool](/tools/qbi/): Summary of QBI.\n"
    )
    issues_no_h1 = detect_llms_txt_issues(no_h1)
    assert any("Missing required H1 project title" in i for i in issues_no_h1)

    # Missing blockquote summary
    no_bq = (
        "# ProfitHelm Platform\n\n"
        "## Top Category Hubs\n\n"
        "- [QBI Tool](/tools/qbi/): Summary of QBI.\n"
    )
    issues_no_bq = detect_llms_txt_issues(no_bq)
    assert any("Missing required blockquote summary" in i for i in issues_no_bq)

    # Missing markdown sections
    no_sec = (
        "# ProfitHelm Platform\n\n"
        "> Deterministic programmatic calculation engine.\n\n"
        "- [QBI Tool](/tools/qbi/): Summary of QBI.\n"
    )
    issues_no_sec = detect_llms_txt_issues(no_sec)
    assert any("Missing required markdown sections" in i for i in issues_no_sec)

    # Missing links
    no_links = (
        "# ProfitHelm Platform\n\n"
        "> Deterministic programmatic calculation engine.\n\n"
        "## Top Category Hubs\n\n"
        "Some text without any markdown links.\n"
    )
    issues_no_links = detect_llms_txt_issues(no_links)
    assert any("Missing required markdown links" in i for i in issues_no_links)

    # Category hub without summary
    no_hub_summary = (
        "# ProfitHelm Platform\n\n"
        "> Deterministic programmatic calculation engine.\n\n"
        "## Top Category Hubs\n\n"
        "- [QBI Calculator](/tools/qbi-calculator/)\n"
    )
    issues_no_hub_summary = detect_llms_txt_issues(no_hub_summary)
    assert any("missing a concise markdown summary" in i for i in issues_no_hub_summary)

    # Category hub summary too long (> 500 chars)
    long_summary = "A" * 550
    too_long = (
        "# ProfitHelm Platform\n\n"
        "> Deterministic programmatic calculation engine.\n\n"
        "## Top Category Hubs\n\n"
        f"- [QBI Calculator](/tools/qbi-calculator/): {long_summary}\n"
    )
    issues_too_long = detect_llms_txt_issues(too_long)
    assert any("summary exceeds 500 characters" in i for i in issues_too_long)

    # Forbidden dashes: em-dash and en-dash
    em_dash_content = compliant + "\nHere is an em-dash: " + chr(0x2014)
    issues_em = detect_llms_txt_issues(em_dash_content)
    assert any("forbidden em-dash" in i for i in issues_em)

    en_dash_content = compliant + "\nHere is an en-dash: " + chr(0x2013)
    issues_en = detect_llms_txt_issues(en_dash_content)
    assert any("forbidden en-dash" in i for i in issues_en)

    # Route leaks: /admin/, /internal/, /api/private, /staging/, /auth/login, localhost
    route_leaks = [
        "/admin/settings",
        "/internal/telemetry",
        "/api/private/keys",
        "/staging/preview",
        "/auth/login",
        "http://localhost:8080/api",
        "https://127.0.0.1:3000/dashboard",
        "/tmp/debug.log",
        "/tools/qbi/?token=secret123",
        "file:///etc/shadow",
    ]
    for rk in route_leaks:
        leaked_md = (
            "# ProfitHelm Platform\n\n"
            "> Deterministic programmatic calculation engine.\n\n"
            "## Top Category Hubs\n\n"
            f"- [Leaked Link]({rk}): Link targeting private path.\n"
        )
        issues_rk = detect_llms_txt_issues(leaked_md)
        assert any("Disallowed internal route" in i for i in issues_rk), f"Expected route leak detection for {rk}"

    # Prompt leakage terms & forbidden jargon
    leak_prompt = compliant + "\nas an ai language model, here is the answer."
    issues_leak = detect_llms_txt_issues(leak_prompt)
    assert any("Prompt leakage detected" in i for i in issues_leak)

    jargon_content = compliant + "\nThis tool is a game-changer for taxes."
    issues_jargon = detect_llms_txt_issues(jargon_content)
    assert any("Forbidden jargon detected" in i for i in issues_jargon)

    # Expanded llms-full.txt issues
    full_short = "# Title\nshort"
    issues_short = detect_llms_txt_issues(full_short, is_full=True)
    assert any("too short" in i for i in issues_short)

    full_compliant = (
        "# ProfitHelm Platform Full Reference Documentation\n\n"
        "Comprehensive deterministic programmatic calculation reference documentation for US statutory codes.\n\n"
        "## IRC Section 199A\nDetailed calculations.\n"
    )
    assert detect_llms_txt_issues(full_compliant, is_full=True) == []


def test_assert_llms_txt_contracts():
    """Verifies assert_llms_txt, assert_llms_manifest_pair, and route assertion contracts."""
    compliant_llms = (
        "# ProfitHelm Platform\n\n"
        "> Deterministic programmatic calculation engine for US statutory tax codes.\n\n"
        "## Top Category Hubs\n\n"
        "- [Section 199A QBI Calculator](/tools/qbi-calculator/): Interactive model evaluating qualified business income deductions.\n"
        "- [Depreciation Schedule Tool](/tools/depreciation/): Deterministic asset depreciation schedules adhering to MACRS.\n\n"
        "## Optional\n\n"
        "- [Full Documentation](/llms-full.txt): Complete expanded reference documentation.\n"
    )
    compliant_full = (
        "# ProfitHelm Platform Full Reference Documentation\n\n"
        "Comprehensive deterministic programmatic calculation reference documentation for US statutory tax codes.\n\n"
        "## IRC Section 199A\nDetailed calculations and statutory citations.\n"
    )

    assert assert_llms_txt(compliant_llms) is True
    assert assert_llms_txt_specification(compliant_llms) is True
    assert assert_llms_txt_compliance(compliant_llms) is True
    assert assert_llms_full_txt_compliance(compliant_full) is True
    assert assert_llms_manifest_pair(compliant_llms, compliant_full) is True
    assert assert_llms_txt_file(compliant_llms) is True
    assert assert_curated_llms_txt(compliant_llms) is True
    assert assert_no_internal_route_leaks(compliant_llms) is True
    assert assert_top_category_hubs_summaries(compliant_llms) is True

    # Negative contract assertions
    with pytest.raises(ValueError, match="llms.txt contract violation"):
        assert_llms_txt("# Title\n\nMissing blockquote and sections.\n")

    with pytest.raises(ValueError, match="Internal route leak violation"):
        assert_no_internal_route_leaks("Check out /admin/dashboard for details.")

    with pytest.raises(ValueError, match="Top category hubs violation"):
        bad_hubs = (
            "# Title\n\n> Summary.\n\n## Top Category Hubs\n\n- [No Summary](/tools/calc/)\n"
        )
        assert_top_category_hubs_summaries(bad_hubs)

    with pytest.raises(ValueError, match="Content must be a string"):
        assert_llms_txt(None)


def test_verify_llms_txt_in_memory_helpers():
    """Verifies verify_llms_txt_content and verify_llms_txt_manifest_pair in-memory functions."""
    compliant_llms = (
        "# ProfitHelm Platform\n\n"
        "> Deterministic programmatic calculation engine for statutory tax codes.\n\n"
        "## Top Category Hubs\n\n"
        "- [Section 199A QBI Calculator](/tools/qbi-calculator/): Interactive model evaluating deductions.\n"
        "- [Depreciation Tool](/tools/depreciation/): Deterministic asset depreciation schedules.\n"
    )
    compliant_full = (
        "# ProfitHelm Platform Expanded Documentation\n\n"
        "Complete technical specification and calculation rules for all statutory tax engines.\n"
    )

    res1 = verify_llms_txt_content(compliant_llms)
    assert res1["status"] == "PASS"
    assert res1["violations_count"] == 0
    assert res1["hubs_verified"] == 2
    assert res1["links_verified"] == 2
    assert res1["has_h1"] is True
    assert res1["has_blockquote"] is True

    res_pair = verify_llms_txt_manifest_pair(compliant_llms, compliant_full)
    assert res_pair["status"] == "PASS"
    assert res_pair["violations_count"] == 0
    assert "llms_txt" in res_pair
    assert "llms_full_txt" in res_pair

    # In-memory helpers
    assert verify_llms_full_txt_content(compliant_full, is_full=True)["status"] == "PASS"

    # Non-string
    res_err = verify_llms_txt_content(12345)
    assert res_err["status"] == "FAIL"
    assert res_err["violations_count"] == 1

    # Forbidden dash
    res_dash = verify_llms_txt_content(compliant_llms + chr(0x2014))
    assert res_dash["status"] == "FAIL"
    assert any("forbidden em-dash" in i for i in res_dash["issues"])


def test_check_llms_txt_gate_on_directory(tmp_path):
    """Verifies MasterSEOVerifier check_llms_txt_gate and all aliases on directory fixtures."""
    pos_dir = tmp_path / "dist_factor13_pos"
    pos_dir.mkdir()

    compliant_llms = (
        "# ProfitHelm Platform\n\n"
        "> Deterministic programmatic calculation engine for US statutory tax codes.\n\n"
        "## Top Category Hubs\n\n"
        "- [Section 199A QBI Calculator](/tools/qbi-calculator/): Interactive model evaluating qualified business income deductions.\n"
        "- [Depreciation Schedule Tool](/tools/depreciation/): Deterministic asset depreciation schedules adhering to MACRS.\n\n"
        "## Optional\n\n"
        "- [Full Documentation](/llms-full.txt): Complete expanded reference documentation.\n"
    )
    compliant_full = (
        "# ProfitHelm Platform Full Reference Documentation\n\n"
        "Comprehensive deterministic programmatic calculation reference documentation for US statutory codes.\n\n"
        "## IRC Section 199A\nDetailed calculations and rules.\n"
    )

    (pos_dir / "llms.txt").write_text(compliant_llms, encoding="utf-8")
    (pos_dir / "llms-full.txt").write_text(compliant_full, encoding="utf-8")

    verifier = MasterSEOVerifier(dist_dir=pos_dir, domain="profithelm.com")
    res_pos = verifier.check_llms_txt_gate(pos_dir)
    assert res_pos["status"] == "PASS"
    assert res_pos["manifests_checked"] == 2
    assert res_pos["hubs_verified"] == 2
    assert res_pos["violations_count"] == 0

    # Method aliases
    assert verifier.check_llms_txt_file_gate(pos_dir)["status"] == "PASS"
    assert verifier.check_llms_full_txt_gate(pos_dir)["status"] == "PASS"
    assert verifier.check_llmstxt_gate(pos_dir)["status"] == "PASS"
    assert verifier.check_llms_manifest_gate(pos_dir)["status"] == "PASS"
    assert verifier.check_curated_llms_txt_gate(pos_dir)["status"] == "PASS"
    assert verifier.verify_llms_txt(pos_dir)["status"] == "PASS"
    assert verifier.verify_llms_txt_file(pos_dir)["status"] == "PASS"
    assert verifier.verify_llms_full_txt(pos_dir)["status"] == "PASS"
    assert verifier.verify_llmstxt(pos_dir)["status"] == "PASS"
    assert verifier.verify_curated_llms_txt(pos_dir)["status"] == "PASS"

    # Module-level aliases
    assert check_llms_txt_gate(pos_dir)["status"] == "PASS"
    assert check_llms_txt_file_gate(pos_dir)["status"] == "PASS"
    assert check_llms_full_txt_gate(pos_dir)["status"] == "PASS"
    assert check_llmstxt_gate(pos_dir)["status"] == "PASS"
    assert check_llms_manifest_gate(pos_dir)["status"] == "PASS"
    assert check_curated_llms_txt_gate(pos_dir)["status"] == "PASS"
    assert verify_llms_txt(pos_dir)["status"] == "PASS"
    assert verify_llms_txt_file(pos_dir)["status"] == "PASS"
    assert verify_llms_full_txt(pos_dir)["status"] == "PASS"
    assert verify_llmstxt(pos_dir)["status"] == "PASS"
    assert verify_curated_llms_txt(pos_dir)["status"] == "PASS"

    # Negative tree 1: route leak in llms.txt
    neg_dir1 = tmp_path / "dist_factor13_neg1"
    neg_dir1.mkdir()
    leaked_llms = (
        "# ProfitHelm Platform\n\n"
        "> Deterministic calculation engine.\n\n"
        "## Top Category Hubs\n\n"
        "- [Admin Settings](/admin/dashboard): Leaked administrative path.\n"
    )
    (neg_dir1 / "llms.txt").write_text(leaked_llms, encoding="utf-8")
    (neg_dir1 / "llms-full.txt").write_text(compliant_full, encoding="utf-8")

    res_neg1 = verifier.check_llms_txt_gate(neg_dir1)
    assert res_neg1["status"] == "FAIL"
    assert res_neg1["violations_count"] >= 1
    assert any("Disallowed internal route" in i for i in res_neg1["issues"])

    # Negative tree 2: route leak in llms-full.txt
    neg_dir2 = tmp_path / "dist_factor13_neg2"
    neg_dir2.mkdir()
    leaked_full = (
        "# Full Docs\n\n"
        "Here is an internal route: https://localhost:8080/internal/api for developers.\n"
    )
    (neg_dir2 / "llms.txt").write_text(compliant_llms, encoding="utf-8")
    (neg_dir2 / "llms-full.txt").write_text(leaked_full, encoding="utf-8")

    res_neg2 = verifier.check_llms_txt_gate(neg_dir2)
    assert res_neg2["status"] == "FAIL"
    assert any("Disallowed internal route" in i for i in res_neg2["issues"])

    # Negative tree 3: missing category hub summary
    neg_dir3 = tmp_path / "dist_factor13_neg3"
    neg_dir3.mkdir()
    no_summary_llms = (
        "# ProfitHelm Platform\n\n"
        "> Deterministic calculation engine.\n\n"
        "## Top Category Hubs\n\n"
        "- [QBI Calculator](/tools/qbi-calculator/)\n"
    )
    (neg_dir3 / "llms.txt").write_text(no_summary_llms, encoding="utf-8")
    (neg_dir3 / "llms-full.txt").write_text(compliant_full, encoding="utf-8")

    res_neg3 = verifier.check_llms_txt_gate(neg_dir3)
    assert res_neg3["status"] == "FAIL"
    assert any("missing a concise markdown summary" in i for i in res_neg3["issues"])

    # Negative tree 4: forbidden em-dash
    neg_dir4 = tmp_path / "dist_factor13_neg4"
    neg_dir4.mkdir()
    (neg_dir4 / "llms.txt").write_text(compliant_llms + chr(0x2014), encoding="utf-8")
    (neg_dir4 / "llms-full.txt").write_text(compliant_full, encoding="utf-8")

    res_neg4 = verifier.check_llms_txt_gate(neg_dir4)
    assert res_neg4["status"] == "FAIL"
    assert any("forbidden em-dash" in i for i in res_neg4["issues"])

    # Negative tree 5: forbidden en-dash
    neg_dir5 = tmp_path / "dist_factor13_neg5"
    neg_dir5.mkdir()
    (neg_dir5 / "llms.txt").write_text(compliant_llms, encoding="utf-8")
    (neg_dir5 / "llms-full.txt").write_text(compliant_full + chr(0x2013), encoding="utf-8")

    res_neg5 = verifier.check_llms_txt_gate(neg_dir5)
    assert res_neg5["status"] == "FAIL"
    assert any("forbidden en-dash" in i for i in res_neg5["issues"])

    # Negative tree 6: incomplete manifest pair (only llms.txt)
    neg_dir6 = tmp_path / "dist_factor13_neg6"
    neg_dir6.mkdir()
    (neg_dir6 / "llms.txt").write_text(compliant_llms, encoding="utf-8")

    res_neg6 = verifier.check_llms_txt_gate(neg_dir6)
    assert res_neg6["status"] == "FAIL"
    assert any("Incomplete manifest pair" in i for i in res_neg6["issues"])

    # Negative tree 7: strict mode with missing manifests
    neg_dir7 = tmp_path / "dist_factor13_neg7"
    neg_dir7.mkdir()
    res_neg7 = verifier.check_llms_txt_gate(neg_dir7, require_strict=True)
    assert res_neg7["status"] == "FAIL"
    assert any("Missing llms.txt manifest" in i for i in res_neg7["issues"])
    assert any("Missing llms-full.txt manifest" in i for i in res_neg7["issues"])


def test_gate_aliases_and_checklist_integration_factor13(tmp_path):
    """Verifies Factor 13 gate aliases and audit_seo_checklist integration."""
    pos_dir = tmp_path / "dist_factor13_integration"
    pos_dir.mkdir()
    tool_dir = pos_dir / "tools" / "qbi-calculator"
    tool_dir.mkdir(parents=True)

    compliant_page = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>Section 199A QBI Calculation Tool</title>'
        '<meta name="description" content="Structured Qualified Business Income deduction calculation tool.">'
        '<link rel="canonical" href="https://profithelm.com/tools/qbi-calculator/">'
        '<script type="application/ld+json">'
        '{"@context": "https://schema.org", "@type": "SoftwareApplication", '
        '"name": "ProfitHelm QBI Engine", "applicationCategory": "FinanceApplication", '
        '"operatingSystem": "All", "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}}'
        '</script>'
        '</head><body>'
        '<h1>Section 199A QBI Calculator</h1>'
        '<div class="direct-answer">'
        'Under IRC Section 199A, eligible small business owners deduct up to 20% of qualified business income.'
        '</div>'
        '</body></html>'
    )
    (tool_dir / "index.html").write_text(compliant_page, encoding="utf-8")

    home_page = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<title>ProfitHelm Platform Programmatic Tax Calculation Tools</title>'
        '<meta name="description" content="Access deterministic programmatic tax models and business tools.">'
        '<link rel="canonical" href="https://profithelm.com/">'
        '</head><body>'
        '<h1>ProfitHelm Programmatic Calculation Hub</h1>'
        '<a href="/tools/qbi-calculator/">QBI Tool</a>'
        '</body></html>'
    )
    (pos_dir / "index.html").write_text(home_page, encoding="utf-8")

    compliant_llms = (
        "# ProfitHelm Platform\n\n"
        "> Deterministic programmatic calculation engine for US statutory tax codes.\n\n"
        "## Top Category Hubs\n\n"
        "- [Section 199A QBI Calculator](/tools/qbi-calculator/): Interactive model evaluating qualified business income deductions.\n\n"
        "## Optional\n\n"
        "- [Full Documentation](/llms-full.txt): Complete expanded reference documentation.\n"
    )
    compliant_full = (
        "# ProfitHelm Platform Full Reference Documentation\n\n"
        "Comprehensive deterministic programmatic calculation reference documentation for US statutory codes.\n"
    )
    (pos_dir / "llms.txt").write_text(compliant_llms, encoding="utf-8")
    (pos_dir / "llms-full.txt").write_text(compliant_full, encoding="utf-8")

    verifier = MasterSEOVerifier(dist_dir=pos_dir, domain="profithelm.com")
    audit_res = verifier.audit_seo_checklist(pos_dir, enforce_relevance=False)
    assert "check_llms_txt_gate" in audit_res["gates"]
    assert "check_llms_txt_file_gate" in audit_res["gates"]
    assert "check_llms_full_txt_gate" in audit_res["gates"]
    assert "check_llmstxt_gate" in audit_res["gates"]
    assert "check_llms_manifest_gate" in audit_res["gates"]
    assert "check_curated_llms_txt_gate" in audit_res["gates"]
    assert audit_res["gates"]["check_llms_txt_gate"]["status"] == "PASS"


def test_strict_anti_slop_across_modules():
    """Strict anti-slop invariant: zero em-dashes and zero en-dashes across Factor 1 through 13 modules."""
    base_dir = Path(__file__).resolve().parent.parent
    files_to_check = [
        base_dir / "pseofactory" / "verifier.py",
        base_dir / "pseofactory" / "contracts.py",
        base_dir / "pseofactory" / "seo" / "verifier.py",
        base_dir / "pseofactory" / "__init__.py",
        Path(__file__).resolve(),
    ]
    for f in files_to_check:
        assert f.is_file(), f"Expected file to exist: {f}"
        text = f.read_text(encoding="utf-8")
        assert chr(0x2014) not in text, f"Forbidden em-dash detected in {f.name}"
        assert chr(0x2013) not in text, f"Forbidden en-dash detected in {f.name}"



