"""
Tests for pseofactory Unified Programmatic SEO Substrate:
1. MasterSEOVerifier gates (alt text, sitemaps, canonicals, schema markup, cleanliness).
2. Indexing velocity governors, content hash diffing, and URL partitioning.
3. Engine Hash Drift Gate (drift detection, SHA-256 calculation, and state persistence).
4. Multi-channel syndication and parasite SEO generators.
Zero em-dashes. Zero en-dashes.
"""

import sys
import json
from pathlib import Path
import pytest

from pseofactory.contracts import (
    assert_no_forbidden_dashes,
    assert_no_prompt_leakage,
    assert_linkedin,
    assert_x_post,
    assert_ai_mode_calculation_manifest,
    sanitize_url_slug,
    assert_url_safe_slug,
    assert_touch_targets,
    assert_valid_jsonld,
    assert_sitemap_parses,
    StageResult,
    assert_comparison_layout_contracts,
    assert_multi_scale_semantic_compression,
    assert_technical_seo_spec,
)
from pseofactory.verifier import (
    MasterSEOVerifier,
    SEOVerificationError,
    SinglePassSEODocumentParser,
    check_snippet_eligibility_gate,
    AI_SEARCH_BOTS,
    AI_USER_TRIGGERED_BOTS,
    AI_TRAINING_BOTS,
)
from pseofactory.indexer import (
    PushIndexer,
    CrawlerTelemetryListener,
    partition_indexing_urls,
)
from pseofactory.drift import (
    compute_engine_hash,
    detect_engine_drift,
    record_engine_hash,
)
from pseofactory.distributor import (
    generate_linkedin_company_post,
    generate_x_post,
    generate_parasite_google_sites_html,
    generate_parasite_substack_teardown,
    generate_reddit_community_teardown,
    generate_quora_thread_answer,
    generate_youtube_syndication,
    _classify_tool_domain,
    _resolve_tool,
)


def test_contracts_dash_and_prompt_leakage():
    """Validates anti-slop dash assertion and prompt leakage rejection."""
    assert assert_no_forbidden_dashes("Clean standard text with hyphen - only.") is True

    with pytest.raises(ValueError, match="Forbidden em-dash"):
        assert_no_forbidden_dashes("Text with \u2014 em-dash.")

    with pytest.raises(ValueError, match="Forbidden en-dash"):
        assert_no_forbidden_dashes("Text with \u2013 en-dash.")

    with pytest.raises(ValueError, match="Prompt leakage detected"):
        assert_no_prompt_leakage("Here is the response from the model.")


def test_contracts_social_bounds():
    """Validates LinkedIn and X post character length limits."""
    valid_linkedin = "A" * 150
    assert assert_linkedin(valid_linkedin) is True

    with pytest.raises(ValueError, match="too short"):
        assert_linkedin("Short")

    valid_x = "Valid tweet length."
    assert assert_x_post(valid_x) is True

    with pytest.raises(ValueError, match="exceeds 280"):
        assert_x_post("X" * 281)


def test_contracts_manifest_validation():
    """Validates Google AI Mode calculation manifest specification."""
    valid_spec = {
        "formula": "y = mx + b",
        "inputs": ["m", "x", "b"],
        "sample_calculation": "2*3 + 1 = 7",
        "statutory_authority": "34 CFR 685.208",
        "entity_type": "StatutoryCalculationRule",
    }
    assert assert_ai_mode_calculation_manifest(valid_spec) is True

    with pytest.raises(ValueError, match="missing 'entity_type'"):
        invalid = dict(valid_spec)
        del invalid["entity_type"]
        assert_ai_mode_calculation_manifest(invalid)


def test_engine_hash_drift_gate(tmp_path):
    """Verifies that detect_engine_drift identifies changes and updates state."""
    state_file = tmp_path / "engine_hash.json"

    # 1. First run: state file does not exist -> DRIFT detected
    res1 = detect_engine_drift(state_file=state_file)
    assert res1["status"] == "DRIFT"
    assert res1["drift_detected"] is True
    assert res1["requires_recompile"] is True
    assert len(res1["current_hash"]) == 64

    # 2. Record the engine hash
    recorded = record_engine_hash(state_file=state_file, hash_value=res1["current_hash"])
    assert recorded == res1["current_hash"]
    assert state_file.exists()

    # 3. Second run: state file matches current hash -> ALIGNED
    res2 = detect_engine_drift(state_file=state_file)
    assert res2["status"] == "ALIGNED"
    assert res2["drift_detected"] is False
    assert res2["requires_recompile"] is False

    # 4. If recorded hash is corrupted or stale -> DRIFT detected
    state_file.write_text(json.dumps({"engine_hash": "stale_hash_value"}), encoding="utf-8")
    res3 = detect_engine_drift(state_file=state_file)
    assert res3["status"] == "DRIFT"
    assert res3["drift_detected"] is True


def test_url_partitioning():
    """Verifies partition_indexing_urls splits into Tier-1 Hubs and Tier-2 Leaves."""
    urls = [
        "https://example.com/",
        "https://example.com/tools/calc-one/",
        "https://example.com/tools/calc-one/state-ca/",
        "https://example.com/tools/calc-one/state-ny/",
    ]
    hubs, leaves = partition_indexing_urls(urls)
    assert "https://example.com/" in hubs
    assert "https://example.com/tools/calc-one/" in hubs
    assert "https://example.com/tools/calc-one/state-ca/" in leaves
    assert "https://example.com/tools/calc-one/state-ny/" in leaves


def test_push_indexer_content_hash_diffing(tmp_path):
    """Verifies PushIndexer filters unchanged push URLs using persistent ledger."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text("<html>Home v1</html>", encoding="utf-8")
    (dist_dir / "tool").mkdir()
    (dist_dir / "tool" / "index.html").write_text("<html>Tool v1</html>", encoding="utf-8")

    indexer = PushIndexer(
        domain="example.com",
        canonical_base="https://example.com",
        base_dir=tmp_path,
        dist_dir=dist_dir,
    )

    urls = ["https://example.com/", "https://example.com/tool/"]

    # First check: ledger empty -> both need push
    to_push, skipped = indexer.filter_unchanged_push_urls(urls)
    assert len(to_push) == 2
    assert len(skipped) == 0

    # Record push
    indexer.record_pushed_urls(to_push)

    # Second check: unchanged content -> both skipped
    to_push2, skipped2 = indexer.filter_unchanged_push_urls(urls)
    assert len(to_push2) == 0
    assert len(skipped2) == 2

    # Mutate tool page HTML
    (dist_dir / "tool" / "index.html").write_text("<html>Tool v2 updated</html>", encoding="utf-8")

    # Third check: tool page has new hash -> only tool needs push
    to_push3, skipped3 = indexer.filter_unchanged_push_urls(urls)
    assert to_push3 == ["https://example.com/tool/"]
    assert skipped3 == ["https://example.com/"]


def test_parasite_syndication_templates():
    """Verifies parasite SEO generators produce valid non-empty copy meeting contracts."""
    tool = {
        "slug": "student-loan-calculator",
        "title": "Federal Student Loan Repayment Calculator",
        "description": "Deterministic quantitative modeling for federal student loan repayment options.",
        "quick_answer": "Computes monthly obligations and repayment timelines under Title IV statutory rules.",
        "category": "Education Finance",
    }

    gs_html = generate_parasite_google_sites_html(tool)
    assert "<title>" in gs_html
    assert "student-loan-calculator" in gs_html
    assert "\u2014" not in gs_html
    assert "\u2013" not in gs_html

    substack = generate_parasite_substack_teardown(tool)
    assert "article_markdown" in substack or "body" in substack
    content = substack.get("article_markdown") or substack.get("body")
    assert "\u2014" not in content


    reddit = generate_reddit_community_teardown("student-loan-calculator")
    assert "content" in reddit
    assert "\u2014" not in reddit["content"]

    quora = generate_quora_thread_answer("student-loan-calculator")
    assert "answer_markdown" in quora or "answer" in quora
    ans_text = quora.get("answer_markdown") or quora.get("answer")
    assert "\u2014" not in ans_text


    yt = generate_youtube_syndication(tool)
    assert "description" in yt
    assert "pinned_comment" in yt
    assert "<" not in yt["description"]
    assert "<" not in yt["pinned_comment"]


def test_sanitize_url_slug_contractions():
    """Verifies that contractions with apostrophes are properly normalized."""
    assert sanitize_url_slug("What's the 2027 TCJA Tax Rate?!") == "whats-the-2027-tcja-tax-rate"
    assert sanitize_url_slug("Taxpayer’s Bracket Calculation") == "taxpayers-bracket-calculation"
    assert sanitize_url_slug("Founder`s Liquidity & Runway") == "founders-liquidity-runway"


def test_master_seo_verifier_parametric(tmp_path):
    """Verifies MasterSEOVerifier works with custom configuration and detects issues."""
    dist = tmp_path / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><title>Title Exactly 50 Characters Long for Testing12345</title>"
        "<meta name='description' content='A valid descriptive meta description between 50 and 165 characters long.'>"
        "<link rel='canonical' href='https://mybrand.com/'>"
        "<meta name='google-site-verification' content='token123'>"
        "<script type='application/ld+json'>{\"@context\": \"https://schema.org\", \"@type\": \"WebPage\"}</script>"
        "</head><body><h1>A Valid Single Heading for Brand</h1><p>Content</p></body></html>",
        encoding="utf-8"
    )
    (dist / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nDisallow: /signal/\nSitemap: https://mybrand.com/sitemap.xml\n"
        "Sitemap: https://mybrand.com/sitemap-hubs.xml\nSitemap: https://mybrand.com/sitemap-leaves.xml\n",
        encoding="utf-8"
    )
    (dist / "sitemap.xml").write_text(
        "<?xml version='1.0' encoding='UTF-8'?><urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"
        "<url><loc>https://mybrand.com/</loc></url></urlset>",
        encoding="utf-8"
    )
    (dist / "_headers").write_text(
        "/\n  Link: <https://mybrand.com/>; rel=\"canonical\"\n",
        encoding="utf-8"
    )

    verifier = MasterSEOVerifier(
        dist_dir=dist,
        canonical_base="https://mybrand.com",
        domain="mybrand.com",
        brand_name="MyBrand",
        required_endpoints=["/"],
        strict_robots=False,
    )

    alt_res = verifier.check_alt_text_gate()
    assert alt_res["status"] == "PASS"

    canon_res = verifier.check_canonical_tags_gate()
    assert canon_res["status"] == "PASS"

    h1_res = verifier.check_single_h1_gate()
    assert h1_res["status"] == "PASS"


def test_engine_drift_triggers_staleness_recompile(tmp_path):
    """Verifies that engine code modifications trigger DRIFT verdict and requires_recompile."""
    code_dir = tmp_path / "engine_pkg"
    code_dir.mkdir()
    f1 = code_dir / "calc.py"
    f1.write_text("def run(): return 42\n", encoding="utf-8")

    state_file = tmp_path / "engine_hash.json"

    # 1. Initial recording
    init_hash = record_engine_hash(state_file=state_file, base_dirs=[code_dir])
    res_aligned = detect_engine_drift(state_file=state_file, base_dirs=[code_dir])
    assert res_aligned["status"] == "ALIGNED"
    assert res_aligned["requires_recompile"] is False

    # 2. Modify engine code
    f1.write_text("def run(): return 43 # modified\n", encoding="utf-8")

    # 3. Audit detects DRIFT and demands recompile
    res_drift = detect_engine_drift(state_file=state_file, base_dirs=[code_dir])
    assert res_drift["status"] == "DRIFT"
    assert res_drift["drift_detected"] is True
    assert res_drift["requires_recompile"] is True
    assert res_drift["current_hash"] != init_hash


def test_centralized_structural_contracts():
    """Validates newly centralized structural SEO, layout, and compression contracts in pseofactory."""
    # 1. assert_url_safe_slug
    assert assert_url_safe_slug("valid-slug-123") is True
    with pytest.raises(ValueError):
        assert_url_safe_slug("invalid--slug")
    with pytest.raises(ValueError):
        assert_url_safe_slug("invalid slug with spaces")
    with pytest.raises(ValueError):
        assert_url_safe_slug("")

    # 2. assert_touch_targets
    valid_css = ".btn { min-height: 48px; min-width: 48px; }"
    assert assert_touch_targets(valid_css) is True
    undersized_css = ".btn { min-height: 32px; min-width: 48px; }"
    with pytest.raises(ValueError, match="min-height < 44px"):
        assert_touch_targets(undersized_css)

    # 3. assert_valid_jsonld
    valid_html = '<html><head><script type="application/ld+json">{"@context": "https://schema.org", "@type": "SoftwareApplication", "name": "Test"}</script></head><body></body></html>'
    blocks = assert_valid_jsonld(valid_html)
    assert len(blocks) == 1
    assert blocks[0]["@type"] == "SoftwareApplication"
    with pytest.raises(ValueError, match="No application/ld\\+json blocks found"):
        assert_valid_jsonld("<html><body>No schema here</body></html>")
    with pytest.raises(ValueError, match="Invalid JSON-LD block"):
        assert_valid_jsonld('<html><script type="application/ld+json">{bad json}</script></html>')

    # 4. assert_sitemap_parses
    valid_sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        '  <url><loc>https://example.com/tools/test-calculator/</loc></url>\n'
        '</urlset>'
    )
    assert assert_sitemap_parses(valid_sitemap) is True
    sitemapindex = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        '  <sitemap><loc>https://example.com/sitemap1.xml</loc></sitemap>\n'
        '</sitemapindex>'
    )
    with pytest.raises(ValueError, match="Single XML sitemaps strictly required"):
        assert_sitemap_parses(sitemapindex)

    # 5. assert_comparison_layout_contracts
    homogeneous_html = (
        '<div class="comparison-container">'
        '  <div class="item" data-entity-type="TaxCalculationModel">Model A</div>'
        '  <div class="item" data-entity-type="TaxCalculationModel">Model B</div>'
        '  <div class="item" data-entity-type="TaxCalculationModel">Model C</div>'
        '</div>'
    )
    assert assert_comparison_layout_contracts(homogeneous_html) is True
    heterogeneous_html = (
        '<div class="comparison-container">'
        '  <div class="item" data-entity-type="TaxCalculationModel">Model A</div>'
        '  <div class="item" data-entity-type="DepreciationSchedule">Schedule B</div>'
        '  <div class="item" data-entity-type="TaxCalculationModel">Model C</div>'
        '</div>'
    )
    with pytest.raises(ValueError, match="Homogeneity Law violated"):
        assert_comparison_layout_contracts(heterogeneous_html)

    # 6. assert_multi_scale_semantic_compression
    valid_compression_text = (
        "EntityAlpha provides statutory financial planning under IRC guidelines. "
        "The model calculates net liabilities with high numerical precision. "
        "Taxpayers utilize EntityAlpha to project effective marginal rates.\n\n"
        "BrandBeta delivers verified computational models across federal tiers. "
        "Users observe reliable benchmark projections with BrandBeta. "
        "Statutory compliance remains guaranteed across multiple scenarios."
    )
    assert assert_multi_scale_semantic_compression(valid_compression_text, entity_name="EntityAlpha", brand_name="BrandBeta") is True
    with pytest.raises(ValueError, match="Micro entity anchoring violated"):
        unanchored_text = (
            "This paragraph lacks any entity or brand mentions entirely. "
            "It discusses generic concepts without anchoring to the subject. "
            "Therefore it fails the micro entity anchoring requirement."
        )
        assert_multi_scale_semantic_compression(unanchored_text, entity_name="EntityAlpha", brand_name="BrandBeta")

    # 7. StageResult
    sr = StageResult(stage_id="build", ok=True, blocking=False, detail={"count": 42})
    assert sr.stage_id == "build"
    assert sr.ok is True
    assert sr.to_dict()["detail"]["count"] == 42


def test_substrate_domain_neutrality_isolation(monkeypatch, tmp_path):
    """Verifies that pseofactory functions with pure domain neutrality without hardcoded tenant couplings."""
    # 1. Isolation: pseofactory modules import and run without profithelm in sys.modules
    import subprocess
    cmd = (
        "import sys; "
        "import pseofactory.contracts; "
        "import pseofactory.indexer; "
        "import pseofactory.verifier; "
        "import pseofactory.distributor; "
        "assert 'profithelm' not in sys.modules; "
        "assert 'profithelm.config' not in sys.modules"
    )
    res = subprocess.run([sys.executable, "-c", cmd], capture_output=True, text=True)
    assert res.returncode == 0, f"Substrate domain isolation failed: {res.stderr}"

    # 2. PushIndexer parameterized for a non-profithelm tenant
    indexer = PushIndexer(
        domain="tenant.com",
        canonical_base="https://tenant.com",
        base_dir=tmp_path,
        dist_dir=tmp_path / "dist",
        indexmysite_project_id="tenant-project",
    )
    assert indexer.domain == "tenant.com"
    assert indexer.canonical_base == "https://tenant.com"
    assert indexer.indexmysite_project_id == "tenant-project"
    assert indexer.dist_dir == tmp_path / "dist"

    # 3. MasterSEOVerifier parameterized for a non-profithelm tenant
    verifier = MasterSEOVerifier(
        dist_dir=tmp_path / "dist",
        canonical_base="https://tenant.com",
        domain="tenant.com",
        brand_name="TenantBrand",
    )
    assert verifier.domain == "tenant.com"
    assert verifier.canonical_base == "https://tenant.com"
    assert verifier.brand_name == "TenantBrand"
    assert verifier.dist_dir == tmp_path / "dist"

    # 4. _classify_tool_domain respects explicit non-tax categories and domains
    assert _classify_tool_domain({"domain": "student_loans"}) == "student_loans"
    assert _classify_tool_domain({"category": "Student Loan", "slug": "repayment"}) == "student loan"
    assert _classify_tool_domain({"category": "Corporate Finance", "slug": "runway"}) == "saas"
    assert _classify_tool_domain({"category": "Market Arbitrage", "slug": "prediction"}) == "quant"

    # 5. _resolve_tool does not force 'Tax Intelligence' or tax affiliates onto custom tools
    custom_spec = {
        "slug": "custom-loan-repayment",
        "title": "Custom Loan Repayment Calculator",
        "category": "Education Finance",
        "affiliates": ["sofi", "earnest"],
    }
    resolved = _resolve_tool(custom_spec)
    assert resolved["category"] == "Education Finance"
    assert resolved["affiliates"] == ["sofi", "earnest"]
    assert resolved["slug"] == "custom-loan-repayment"


def test_single_pass_parser_snippet_directives():
    """Verifies SinglePassSEODocumentParser detects nosnippet, max-snippet, noindex, and data-nosnippet."""
    html = (
        '<!DOCTYPE html><html><head>'
        '<title>Test Page</title>'
        '<meta name="robots" content="nosnippet, noindex, max-snippet:50, max-image-preview:large, max-video-preview:15">'
        '</head><body>'
        '<h1>Heading</h1>'
        '<div data-nosnippet="true">'
        '  <aside class="quick-answer">This is a quick answer wrapped in an ancestor with data-nosnippet.</aside>'
        '</div>'
        '</body></html>'
    )
    parser = SinglePassSEODocumentParser()
    parser.feed(html)
    assert parser.has_nosnippet is True
    assert parser.has_noindex is True
    assert parser.max_snippet == 50
    assert parser.max_image_preview == "large"
    assert parser.max_video_preview == 15
    assert parser.quick_answer_has_data_nosnippet is True
    assert "div" in parser.data_nosnippet_tags

    # Direct data-nosnippet on aside
    html_direct = (
        '<!DOCTYPE html><html><head><title>Test</title></head><body>'
        '<aside class="quick-answer" data-nosnippet>Direct data-nosnippet on answer.</aside>'
        '</body></html>'
    )
    p2 = SinglePassSEODocumentParser()
    p2.feed(html_direct)
    assert p2.quick_answer_has_data_nosnippet is True
    assert "aside" in p2.data_nosnippet_tags


def test_snippet_eligibility_and_snippet_gate_failures(tmp_path):
    """Verifies check_snippet_eligibility_gate and check_snippet_gate fail on restrictive directives."""
    dist = tmp_path / "dist"
    dist.mkdir()

    # 1. nosnippet failure
    page_nosnippet = dist / "nosnippet.html"
    page_nosnippet.write_text(
        '<!DOCTYPE html><html><head><title>Test</title>'
        '<meta name="robots" content="nosnippet">'
        '</head><body>'
        '<aside class="quick-answer">'
        'Word one two three four five six seven eight nine ten '
        'eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty '
        'twentyone twentytwo twentythree twentyfour twentyfive twentysix twentyseven twentyeight twentynine thirty '
        'thirtyone thirtytwo thirtythree thirtyfour thirtyfive thirtysix thirtyseven thirtyeight thirtynine forty '
        'fortyone fortytwo fortythree fortyfour fortyfive.'
        '</aside>'
        '</body></html>',
        encoding="utf-8"
    )

    verifier = MasterSEOVerifier(dist_dir=dist)
    res_elig = verifier.check_snippet_eligibility_gate(dist)
    assert res_elig["status"] == "FAIL"
    assert any("nosnippet" in issue for issue in res_elig["issues"])

    res_snip = verifier.check_snippet_gate(dist)
    assert res_snip["status"] == "FAIL"
    assert any("nosnippet" in issue for issue in res_snip["issues"])

    # 2. max-snippet too small
    page_nosnippet.unlink()
    page_max_snippet = dist / "max_snippet.html"
    page_max_snippet.write_text(
        '<!DOCTYPE html><html><head><title>Test</title>'
        '<meta name="robots" content="max-snippet:20">'
        '</head><body>'
        '<aside class="quick-answer">'
        'Word one two three four five six seven eight nine ten '
        'eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty '
        'twentyone twentytwo twentythree twentyfour twentyfive twentysix twentyseven twentyeight twentynine thirty '
        'thirtyone thirtytwo thirtythree thirtyfour thirtyfive thirtysix thirtyseven thirtyeight thirtynine forty '
        'fortyone fortytwo fortythree fortyfour fortyfive.'
        '</aside>'
        '</body></html>',
        encoding="utf-8"
    )

    res_elig2 = verifier.check_snippet_eligibility_gate(dist)
    assert res_elig2["status"] == "FAIL"
    assert any("exceeds max-snippet:20" in issue for issue in res_elig2["issues"])

    # 3. data-nosnippet on quick-answer
    page_max_snippet.unlink()
    page_data_nosnippet = dist / "data_nosnippet.html"
    page_data_nosnippet.write_text(
        '<!DOCTYPE html><html><head><title>Test</title></head><body>'
        '<aside class="quick-answer" data-nosnippet>'
        'Word one two three four five six seven eight nine ten '
        'eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty '
        'twentyone twentytwo twentythree twentyfour twentyfive twentysix twentyseven twentyeight twentynine thirty '
        'thirtyone thirtytwo thirtythree thirtyfour thirtyfive thirtysix thirtyseven thirtyeight thirtynine forty '
        'fortyone fortytwo fortythree fortyfour fortyfive.'
        '</aside>'
        '</body></html>',
        encoding="utf-8"
    )

    res_elig3 = verifier.check_snippet_eligibility_gate(dist)
    assert res_elig3["status"] == "FAIL"
    assert any("data-nosnippet" in issue for issue in res_elig3["issues"])


def test_snippet_gates_pass_on_clean_page(tmp_path):
    """Verifies check_snippet_eligibility_gate and check_snippet_gate pass when quick answer is clean."""
    dist = tmp_path / "dist"
    dist.mkdir()
    clean_page = dist / "clean.html"
    clean_page.write_text(
        '<!DOCTYPE html><html><head><title>Clean Page</title>'
        '<meta name="robots" content="index, follow, max-snippet:500">'
        '</head><body>'
        '<h1>Clean Page Header</h1>'
        '<aside class="quick-answer">'
        'Word one two three four five six seven eight nine ten '
        'eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty '
        'twentyone twentytwo twentythree twentyfour twentyfive twentysix twentyseven twentyeight twentynine thirty '
        'thirtyone thirtytwo thirtythree thirtyfour thirtyfive thirtysix thirtyseven thirtyeight thirtynine forty '
        'fortyone fortytwo fortythree fortyfour fortyfive.'
        '</aside>'
        '</body></html>',
        encoding="utf-8"
    )

    verifier = MasterSEOVerifier(dist_dir=dist)
    res_elig = verifier.check_snippet_eligibility_gate(dist)
    assert res_elig["status"] == "PASS"
    assert res_elig["violations_count"] == 0

    res_snip = verifier.check_snippet_gate(dist)
    assert res_snip["status"] == "PASS"
    assert res_snip["violations_count"] == 0


def test_robots_txt_ai_crawler_taxonomy(tmp_path):
    """Verifies 3-tier crawler taxonomy allows disallowing training bot while requiring search bots to be allowed."""
    dist = tmp_path / "dist"
    dist.mkdir()

    # Valid robots.txt: training bot (GPTBot) disallowed, search bots allowed
    robots_valid = (
        "User-agent: *\n"
        "Allow: /\n"
        "Allow: /tools/\n"
        "Disallow: /signal/\n"
        "Disallow: /syndication/\n"
        "Disallow: /staging/\n"
        "Disallow: /test/\n"
        "Disallow: /tests/\n\n"
        "User-agent: Googlebot\n"
        "Allow: /\n\n"
        "User-agent: Bingbot\n"
        "Allow: /\n\n"
        "User-agent: PerplexityBot\n"
        "Allow: /\n\n"
        "User-agent: ClaudeBot\n"
        "Allow: /\n\n"
        "User-agent: OAI-SearchBot\n"
        "Allow: /\n\n"
        "User-agent: ChatGPT-User\n"
        "Allow: /\n\n"
        "User-agent: GPTBot\n"
        "Disallow: /\n\n"
        "Sitemap: https://example.com/sitemap.xml\n"
        "Sitemap: https://example.com/sitemap-hubs.xml\n"
        "Sitemap: https://example.com/sitemap-leaves.xml\n"
    )
    (dist / "robots.txt").write_text(robots_valid, encoding="utf-8")

    verifier = MasterSEOVerifier(dist_dir=dist, strict_robots=True)
    res = verifier.check_robots_txt_gate(dist)
    assert res["status"] == "PASS", f"Expected PASS but got: {res['issues']}"

    # Invalid robots.txt: search bot (OAI-SearchBot) is disallowed
    robots_invalid = (
        "User-agent: *\n"
        "Allow: /\n"
        "Allow: /tools/\n"
        "Disallow: /signal/\n"
        "Disallow: /syndication/\n"
        "Disallow: /staging/\n"
        "Disallow: /test/\n"
        "Disallow: /tests/\n\n"
        "User-agent: Googlebot\n"
        "Allow: /\n\n"
        "User-agent: Bingbot\n"
        "Allow: /\n\n"
        "User-agent: PerplexityBot\n"
        "Allow: /\n\n"
        "User-agent: ClaudeBot\n"
        "Allow: /\n\n"
        "User-agent: OAI-SearchBot\n"
        "Disallow: /\n\n"
        "User-agent: ChatGPT-User\n"
        "Allow: /\n\n"
        "User-agent: GPTBot\n"
        "Disallow: /\n\n"
        "Sitemap: https://example.com/sitemap.xml\n"
        "Sitemap: https://example.com/sitemap-hubs.xml\n"
        "Sitemap: https://example.com/sitemap-leaves.xml\n"
    )
    (dist / "robots.txt").write_text(robots_invalid, encoding="utf-8")
    res_inv = verifier.check_robots_txt_gate(dist)
    assert res_inv["status"] == "FAIL"
    assert any("oai-searchbot" in issue.lower() for issue in res_inv["issues"])


def test_headers_x_robots_tag_nosnippet_detection(tmp_path):
    """Verifies check_snippet_eligibility_gate catches X-Robots-Tag nosnippet on public routes in _headers."""
    dist = tmp_path / "dist"
    dist.mkdir()
    headers_content = (
        "/tools/*\n"
        "  X-Robots-Tag: nosnippet\n"
        "/signal/*\n"
        "  X-Robots-Tag: noindex, nosnippet\n"
    )
    (dist / "_headers").write_text(headers_content, encoding="utf-8")

    verifier = MasterSEOVerifier(dist_dir=dist)
    res = verifier.check_snippet_eligibility_gate(dist)
    assert res["status"] == "FAIL"
    assert any("_headers applies 'nosnippet' to public route '/tools/*'" in issue for issue in res["issues"])


