"""
Tests for x-like:2109219955271196726 (@seo_bint_ejamil) 15 SEO Chrome extensions
capability-gap matrix, deterministic estate technical SEO & SERP anti-cannibalization
verifier, outbound /r/ commercial link rel='noopener sponsored' normalization, and
multi-tenant GainHelm parameterization across pseofactory.
Zero em-dashes. Zero en-dashes.
"""

from pathlib import Path

from pseofactory.affiliates import (
    audit_callout_destination_message_match,
    audit_merchant_coverage_and_yield,
    normalize_html_callout_message_match,
)
import pseofactory.audit as audit_mod
from pseofactory.contracts import assert_no_forbidden_dashes
from pseofactory.gsc_remediation import (
    apply_remediation_overlay_to_html,
    rollback_degraded_overlay_from_html,
)
from pseofactory.maintenance import (
    AssetIntegrityEvaluator,
    ConfigurablePropertyAdapter,
    DriftReason,
)


def test_x_like_2109219955271196726_capability_matrix_completeness():
    """Verifies all 15 extensions from x-like:2109219955271196726 are mapped with zero slop."""
    assert hasattr(audit_mod, "X_LIKE_2109219955271196726_CAPABILITY_MATRIX")
    assert hasattr(audit_mod, "evaluate_x_like_2109219955271196726_capability_matrix")
    matrix = audit_mod.X_LIKE_2109219955271196726_CAPABILITY_MATRIX
    assert len(matrix) == 15
    ranks = [item["rank"] for item in matrix]
    assert ranks == list(range(1, 16))

    by_name = {item["extension"]: item for item in matrix}
    assert by_name["GMB Everywhere"]["disposition"] == "REJECTED_BLOAT_OR_OFF_VERTICAL"
    assert by_name["Detailed SEO Extension"]["disposition"] == "INTEGRATED_DETERMINISTIC_GATE"
    assert by_name["SEOquake"]["disposition"] == "INTEGRATED_DETERMINISTIC_GATE"
    assert by_name["Ahrefs SEO Toolbar"]["disposition"] == "INTEGRATED_DETERMINISTIC_GATE"
    assert by_name["SEO Minion"]["disposition"] == "INTEGRATED_DETERMINISTIC_GATE"
    assert by_name["META SEO inspector"]["disposition"] == "INTEGRATED_DETERMINISTIC_GATE"
    assert by_name["Redirect Path"]["disposition"] == "INTEGRATED_DETERMINISTIC_GATE"
    assert by_name["Check My Links"]["disposition"] == "INTEGRATED_DETERMINISTIC_GATE"

    summary = audit_mod.evaluate_x_like_2109219955271196726_capability_matrix(include_live_estate_audit=False)
    assert summary["pointer"] == "x-like:2109219955271196726"
    assert summary["total_extensions_evaluated"] == 15
    assert summary["integrated_deterministic_gates_count"] == 7
    assert summary["already_solved_in_substrate_count"] == 7
    assert summary["rejected_bloat_or_off_vertical_count"] == 1
    assert_no_forbidden_dashes(str(summary), context="x_like_2109219955271196726_matrix")


def test_gainhelm_commercial_r_link_rel_sponsored_normalization_and_audit(tmp_path):
    """
    Verifies that bare /r/<partner> links (such as GainHelm tools/index.html)
    are flagged by AssetIntegrityEvaluator when missing rel='noopener sponsored'
    and are deterministically healed by normalize_html_callout_message_match.
    """
    raw_html = (
        '<!DOCTYPE html><html lang="en"><head>'
        "<title>GainHelm Cyber Compliance Calculators &amp; Audit Tools | GainHelm</title>"
        '<meta name="description" content="Explore GainHelm deterministic cyber compliance calculators for SOC 2 Type II, DoD CMMC 2.0, NIST 800-171 SPRS, and HIPAA.">'
        '<link rel="canonical" href="https://gainhelm.com/tools/">'
        '<meta property="og:title" content="GainHelm Cyber Compliance Calculators &amp; Audit Tools | GainHelm">'
        '<meta property="og:url" content="https://gainhelm.com/tools/">'
        '<meta name="twitter:card" content="summary_large_image">'
        "</head><body><main>"
        "<h1>GainHelm Cyber Compliance Calculators &amp; Audit Tools</h1>"
        '<p>FTC Disclosure: GainHelm may earn a referral fee when you request a demo through verified GRC partner links at no additional cost to you.</p>'
        '<a href="/r/vanta_security?source_tool=tools-directory&amp;subid=tools-directory_card&amp;cta_slot=partner_matrix_card" '
        'data-partner="vanta_security" data-tool="tools-directory" data-subid="tools-directory_card" '
        'data-cta-slot="partner_matrix_card" data-partnership-model="QUALIFIED_LEAD_CPL" '
        'class="touch-target" style="min-height:44px;min-width:44px;display:inline-flex;">Request Vanta Demo</a>'
        "</main></body></html>"
    )
    dist_dir = tmp_path / "dist"
    tools_dir = dist_dir / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    target_file = tools_dir / "index.html"
    target_file.write_text(raw_html, encoding="utf-8")

    adapter = ConfigurablePropertyAdapter(
        property_id="gainhelm",
        brand_name="GainHelm",
        domain="gainhelm.com",
        canonical_base="https://gainhelm.com",
        dist_dir=dist_dir,
    )
    evaluator = AssetIntegrityEvaluator()
    drift_rec = evaluator.audit_asset(target_file, adapter, engine_drifted=False)
    assert drift_rec is not None
    assert DriftReason.STRUCTURAL_CONTRACT_VIOLATION in drift_rec.reasons
    assert any("rel='noopener sponsored'" in d for d in drift_rec.details)

    healed_html = normalize_html_callout_message_match(raw_html, property_id="gainhelm")
    assert 'rel="noopener sponsored nofollow"' in healed_html
    assert 'target="_blank"' in healed_html
    assert normalize_html_callout_message_match(healed_html, property_id="gainhelm") == healed_html


def test_gainhelm_multi_tenant_parameterization_no_profithelm_leak():
    """
    Verifies GainHelm parameterization across merchant yield audit, callout message match,
    and GSC overlay title application/rollback without leaking ProfitHelm branding.
    """
    yield_rep = audit_merchant_coverage_and_yield("gainhelm")
    assert yield_rep["status"] == "PASS"
    assert yield_rep["property_id"] == "gainhelm"
    assert "vanta_security" in yield_rep["routes"]

    callout_rep = audit_callout_destination_message_match(property_id="gainhelm")
    assert callout_rep["property_id"] == "gainhelm"
    assert callout_rep["registry_partners_checked"] >= 4

    gh_html = (
        "<!DOCTYPE html><html><head>"
        "<title>SOC 2 Audit Cost Calculator (2026) | GainHelm</title>"
        "</head><body><h1>SOC 2 Audit Cost Calculator</h1></body></html>"
    )
    rolled = rollback_degraded_overlay_from_html(
        gh_html,
        {
            "tenant_id": "gainhelm",
            "slug": "soc-2-audit-cost-calculator",
            "rolled_back_title_rewrite": "Degraded Title",
        },
    )
    assert "ProfitHelm" not in rolled
    assert "Prexvo" not in rolled
    assert "GainHelm" in rolled

    applied = apply_remediation_overlay_to_html(
        gh_html,
        {
            "tenant_id": "gainhelm",
            "slug": "soc-2-audit-cost-calculator",
            "target_url": "https://gainhelm.com/tools/soc-2-audit-cost-calculator/",
            "title_rewrite": "SOC 2 Type II Audit Cost Calculator 2026 Model Tool Guide",
        },
    )
    assert "ProfitHelm" not in applied
    assert "Prexvo" not in applied


def test_estate_technical_seo_and_cannibalization_detector(tmp_path):
    """
    Verifies that audit_estate_technical_seo_and_cannibalization catches duplicate titles,
    broken #fragment anchors, unqualified /r/ links, and redirect chains, and passes once healed.
    """
    dist_dir = tmp_path / "dist"
    (dist_dir / "tools" / "soc-2-audit-cost-calculator").mkdir(parents=True, exist_ok=True)
    (dist_dir / "_redirects").write_text(
        "/old-soc2 /mid-soc2 301\n/mid-soc2 /tools/soc-2-audit-cost-calculator/ 301\n",
        encoding="utf-8",
    )
    page_html = (
        '<!DOCTYPE html><html lang="en"><head>'
        "<title>SOC 2 Type II Audit Cost &amp; Readiness Calculator | GainHelm</title>"
        '<meta name="description" content="Calculate deterministic 2026 SOC 2 Type II audit fees, readiness workpaper costs, and continuous GRC automation ROI under AICPA TSC.">'
        '<link rel="canonical" href="https://gainhelm.com/">'
        '<meta property="og:title" content="SOC 2 Type II Audit Cost &amp; Readiness Calculator | GainHelm">'
        '<meta property="og:url" content="https://gainhelm.com/">'
        '<meta name="twitter:card" content="summary_large_image">'
        "</head><body>"
        '<h1 id="top">SOC 2 Type II Audit Cost &amp; Readiness Calculator</h1>'
        '<a href="/tools/soc-2-audit-cost-calculator/#missing-anchor">Tool</a>'
        '<a href="/r/vanta_security">Vanta</a>'
        "</body></html>"
    )
    (dist_dir / "index.html").write_text(page_html, encoding="utf-8")
    (dist_dir / "tools" / "soc-2-audit-cost-calculator" / "index.html").write_text(page_html, encoding="utf-8")

    assert hasattr(audit_mod, "audit_estate_technical_seo_and_cannibalization")
    bad_rep = audit_mod.audit_estate_technical_seo_and_cannibalization(dist_dir=dist_dir, property_id="gainhelm")
    assert bad_rep["passed"] is False
    assert bad_rep["duplicate_titles_count"] == 1
    assert bad_rep["duplicate_h1s_count"] == 1
    assert bad_rep["broken_fragment_anchors_count"] >= 1
    assert bad_rep["unqualified_commercial_links_count"] >= 1
    assert bad_rep["redirect_chains_count"] == 1

    # Heal the synthetic estate and verify PASS
    (dist_dir / "_redirects").write_text(
        "/old-soc2 /tools/soc-2-audit-cost-calculator/ 301\n",
        encoding="utf-8",
    )
    home_html = (
        '<!DOCTYPE html><html lang="en"><head>'
        "<title>GainHelm Enterprise Cyber Compliance &amp; GRC Cost Intelligence</title>"
        '<meta name="description" content="Model deterministic enterprise cyber compliance costs across AICPA SOC 2, DoD CMMC 2.0, NIST 800-171 SPRS, ISO 27001, and HIPAA frameworks.">'
        '<link rel="canonical" href="https://gainhelm.com/">'
        '<meta property="og:title" content="GainHelm Enterprise Cyber Compliance &amp; GRC Cost Intelligence">'
        '<meta property="og:url" content="https://gainhelm.com/">'
        '<meta name="twitter:card" content="summary_large_image">'
        "</head><body>"
        '<h1 id="top">GainHelm Enterprise Cyber Compliance &amp; GRC Cost Intelligence</h1>'
        '<a href="/tools/soc-2-audit-cost-calculator/#calc-section">SOC 2 Calculator</a>'
        "</body></html>"
    )
    tool_html = (
        '<!DOCTYPE html><html lang="en"><head>'
        "<title>SOC 2 Type II Audit Cost &amp; Readiness Calculator | GainHelm</title>"
        '<meta name="description" content="Calculate deterministic 2026 SOC 2 Type II audit fees, readiness workpaper costs, and continuous GRC automation ROI under AICPA TSC.">'
        '<link rel="canonical" href="https://gainhelm.com/tools/soc-2-audit-cost-calculator/">'
        '<meta property="og:title" content="SOC 2 Type II Audit Cost &amp; Readiness Calculator | GainHelm">'
        '<meta property="og:url" content="https://gainhelm.com/tools/soc-2-audit-cost-calculator/">'
        '<meta name="twitter:card" content="summary_large_image">'
        "</head><body>"
        '<h1 id="calc-section">SOC 2 Type II Audit Cost &amp; Readiness Calculator</h1>'
        '<a href="/">Home</a>'
        '<a href="/r/vanta_security" rel="noopener sponsored nofollow" target="_blank">Vanta</a>'
        "</body></html>"
    )
    (dist_dir / "index.html").write_text(home_html, encoding="utf-8")
    (dist_dir / "tools" / "soc-2-audit-cost-calculator" / "index.html").write_text(tool_html, encoding="utf-8")

    good_rep = audit_mod.audit_estate_technical_seo_and_cannibalization(dist_dir=dist_dir, property_id="gainhelm")
    assert good_rep["passed"] is True, good_rep["issues"]
    assert good_rep["status"] == "PASS"

    slop_rep = audit_mod.audit_code_slop_ratchet()
    assert slop_rep["passed"] is True, slop_rep


def test_retro_reflection_detects_unqualified_commercial_links_in_dist(tmp_path):
    """
    Verifies RetroReflectionEngine.audit_estate flags calculator pages whose /r/ links
    already have source_tool= query params but lack rel='noopener sponsored'.
    """
    from pseofactory.maintenance import RetroReflectionEngine

    dist_dir = tmp_path / "dist"
    tool_dir = dist_dir / "tools" / "soc-2-audit-cost-calculator"
    tool_dir.mkdir(parents=True, exist_ok=True)
    # Build a synthetic tool page that satisfies all mechanics in audit_html_mechanics
    # except that its /r/ link with source_tool= lacks rel="noopener sponsored".
    base_html = "/home/ubuntuadmin/projects/_archive/gainhelm/dist/tools/soc-2-audit-cost-calculator/index.html"
    import pathlib, re

    raw = pathlib.Path(base_html).read_text(encoding="utf-8")
    degraded = re.sub(
        r'(<a\b[^>]*href=["\']/r/[a-z0-9_]+[^"\']*["\'][^>]*)\s+rel=["\'][^"\']*["\']',
        r"\1",
        raw,
        flags=re.I,
    )
    (tool_dir / "index.html").write_text(degraded, encoding="utf-8")

    rep = RetroReflectionEngine.audit_estate(dist_dir, "gainhelm")
    assert "tools/soc-2-audit-cost-calculator/index.html" in rep["stale_pages"]
    assert "callout_message_match" in rep["stale_pages"]["tools/soc-2-audit-cost-calculator/index.html"]

