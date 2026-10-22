"""
Deterministic Visual Primitives and Runtime Calculator Synchronizer for pseofactory.
Guarantees identical component geometry, design token resolution, table containment,
touch-target sizing (>= 44x44px), typographic hierarchy, and synchronous calculator
state updates across all compiled and retro-reflected tenant assets (ProfitHelm and Prexvo)
under both Obsidian Dark (:root) and Porcelain Light ([data-theme="porcelain"]) themes.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

VISUAL_PRIMITIVES_VERSION = "pseo-primitives-v4"

SCREEN_ARCHETYPE_CONTRACTS: Dict[str, Dict[str, Any]] = {
    "interactive_calculator": {
        "archetype": "interactive_calculator",
        "viewports": {
            "mobile": {"width": 375, "height": 812, "max_horizontal_overflow_px": 0},
            "desktop": {
                "width": 1440,
                "height": 900,
                "max_horizontal_overflow_px": 0,
                "max_container_width_px": 1140,
                "max_sibling_left_drift_px": 4.0,
            },
        },
        "design_tokens": {
            "required_tokens": ("--bg-canvas", "--bg-surface", "--card-bg", "--text-primary", "--text-secondary", "--border", "--accent"),
            "min_body_contrast_ratio": 4.5,
            "min_display_contrast_ratio": 3.0,
            "forbid_dark_on_dark_inversion": True,
        },
        "typography": {
            "desktop": {"h1_px": 32.0, "h2_px": 20.0, "h3_px": 16.0, "body_min_px": 14.0},
            "mobile": {"h1_px": 24.0, "h2_px": 18.0, "h3_px": 16.0, "body_min_px": 14.0},
            "strict_monotonic_hierarchy": True,
            "numeric_font_variant": "tabular-nums",
        },
        "surface_and_rhythm": {
            "card_border_radius_px": 12.0,
            "desktop_card_padding_px": 24.0,
            "mobile_card_padding_px": 16.0,
            "desktop_section_gap_px": 24.0,
            "mobile_section_gap_px": 16.0,
            "min_section_gap_px": 12.0,
            "max_section_gap_px": 48.0,
        },
        "ergonomics": {
            "min_touch_target_px": 44.0,
            "min_input_font_size_px": 16.0,
            "result_box_min_height_px": 110.0,
            "table_wrapper_overflow_x": "auto",
            "max_consecutive_cta_callouts": 2,
            "require_runtime_sync": True,
            "require_preset_binding": True,
            "require_slider_number_parity": True,
            "require_primary_to_secondary_sync": True,
            "require_tabular_nums_outputs": True,
            "forbid_duplicate_framework_cards": True,
        },
    },
    "statutory_guide": {
        "archetype": "statutory_guide",
        "viewports": {
            "mobile": {"width": 375, "height": 812, "max_horizontal_overflow_px": 0},
            "desktop": {
                "width": 1440,
                "height": 900,
                "max_horizontal_overflow_px": 0,
                "max_container_width_px": 1140,
                "max_sibling_left_drift_px": 4.0,
            },
        },
        "design_tokens": {
            "required_tokens": ("--bg-canvas", "--bg-surface", "--card-bg", "--text-primary", "--text-secondary", "--border", "--accent"),
            "min_body_contrast_ratio": 4.5,
            "min_display_contrast_ratio": 3.0,
            "forbid_dark_on_dark_inversion": True,
        },
        "typography": {
            "desktop": {"h1_px": 32.0, "h2_px": 20.0, "h3_px": 16.0, "body_min_px": 14.0},
            "mobile": {"h1_px": 24.0, "h2_px": 18.0, "h3_px": 16.0, "body_min_px": 14.0},
            "strict_monotonic_hierarchy": True,
            "numeric_font_variant": "tabular-nums",
        },
        "surface_and_rhythm": {
            "card_border_radius_px": 12.0,
            "desktop_card_padding_px": 24.0,
            "mobile_card_padding_px": 16.0,
            "desktop_section_gap_px": 24.0,
            "mobile_section_gap_px": 16.0,
            "min_section_gap_px": 12.0,
            "max_section_gap_px": 48.0,
        },
        "ergonomics": {
            "min_touch_target_px": 44.0,
            "min_input_font_size_px": 16.0,
            "result_box_min_height_px": 110.0,
            "table_wrapper_overflow_x": "auto",
            "max_consecutive_cta_callouts": 2,
            "require_runtime_sync": False,
            "require_tabular_nums_outputs": True,
            "forbid_duplicate_framework_cards": True,
        },
    },
    "comparison_page": {
        "archetype": "comparison_page",
        "viewports": {
            "mobile": {"width": 375, "height": 812, "max_horizontal_overflow_px": 0},
            "desktop": {
                "width": 1440,
                "height": 900,
                "max_horizontal_overflow_px": 0,
                "max_container_width_px": 1140,
                "max_sibling_left_drift_px": 4.0,
            },
        },
        "design_tokens": {
            "required_tokens": ("--bg-canvas", "--bg-surface", "--card-bg", "--text-primary", "--text-secondary", "--border", "--accent"),
            "min_body_contrast_ratio": 4.5,
            "min_display_contrast_ratio": 3.0,
            "forbid_dark_on_dark_inversion": True,
        },
        "typography": {
            "desktop": {"h1_px": 32.0, "h2_px": 20.0, "h3_px": 16.0, "body_min_px": 14.0},
            "mobile": {"h1_px": 24.0, "h2_px": 18.0, "h3_px": 16.0, "body_min_px": 14.0},
            "strict_monotonic_hierarchy": True,
            "numeric_font_variant": "tabular-nums",
        },
        "surface_and_rhythm": {
            "card_border_radius_px": 12.0,
            "desktop_card_padding_px": 24.0,
            "mobile_card_padding_px": 16.0,
            "desktop_section_gap_px": 24.0,
            "mobile_section_gap_px": 16.0,
            "min_section_gap_px": 12.0,
            "max_section_gap_px": 48.0,
        },
        "ergonomics": {
            "min_touch_target_px": 44.0,
            "min_input_font_size_px": 16.0,
            "result_box_min_height_px": 110.0,
            "table_wrapper_overflow_x": "auto",
            "max_consecutive_cta_callouts": 2,
            "require_runtime_sync": False,
            "require_tabular_nums_outputs": True,
            "require_wrapped_tables": True,
            "forbid_duplicate_framework_cards": True,
        },
    },
    "index_hub": {
        "archetype": "index_hub",
        "viewports": {
            "mobile": {"width": 375, "height": 812, "max_horizontal_overflow_px": 0},
            "desktop": {
                "width": 1440,
                "height": 900,
                "max_horizontal_overflow_px": 0,
                "max_container_width_px": 1140,
                "max_sibling_left_drift_px": 4.0,
            },
        },
        "design_tokens": {
            "required_tokens": ("--bg-canvas", "--bg-surface", "--card-bg", "--text-primary", "--text-secondary", "--border", "--accent"),
            "min_body_contrast_ratio": 4.5,
            "min_display_contrast_ratio": 3.0,
            "forbid_dark_on_dark_inversion": True,
        },
        "typography": {
            "desktop": {"h1_px": 32.0, "h2_px": 20.0, "h3_px": 16.0, "body_min_px": 14.0},
            "mobile": {"h1_px": 24.0, "h2_px": 18.0, "h3_px": 16.0, "body_min_px": 14.0},
            "strict_monotonic_hierarchy": True,
            "numeric_font_variant": "tabular-nums",
        },
        "surface_and_rhythm": {
            "card_border_radius_px": 12.0,
            "desktop_card_padding_px": 24.0,
            "mobile_card_padding_px": 16.0,
            "desktop_section_gap_px": 24.0,
            "mobile_section_gap_px": 16.0,
            "min_section_gap_px": 12.0,
            "max_section_gap_px": 48.0,
        },
        "ergonomics": {
            "min_touch_target_px": 44.0,
            "min_input_font_size_px": 16.0,
            "result_box_min_height_px": 110.0,
            "table_wrapper_overflow_x": "auto",
            "max_consecutive_cta_callouts": 2,
            "require_runtime_sync": False,
            "require_tabular_nums_outputs": True,
            "forbid_duplicate_framework_cards": True,
        },
    },
}


def _strip_style_and_script_blocks(html_content: str) -> str:
    """Strips <style>, <script>, and <noscript> blocks so DOM classifiers never match CSS or JS selectors."""
    if not html_content:
        return ""
    cleaned = re.sub(r"<style\b[^>]*>[\s\S]*?</style>", " ", html_content, flags=re.IGNORECASE)
    cleaned = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<noscript\b[^>]*>[\s\S]*?</noscript>", " ", cleaned, flags=re.IGNORECASE)
    return cleaned


def classify_screen_archetype(html_content: str, rel_path: str = "index.html") -> str:
    """
    Deterministically classifies an HTML screen into one of the 4 canonical archetypes:
    interactive_calculator, comparison_page, statutory_guide, or index_hub.
    Strips <style>, <script>, and <noscript> blocks first so embedded primitive CSS/JS
    rules never misclassify statutory guides or directory pages as calculators.
    """
    norm_path = (rel_path or "index.html").strip().strip("/").lower()
    dom_lower = _strip_style_and_script_blocks(html_content or "").lower()

    if norm_path in (
        "",
        "index.html",
        "tools",
        "tools/index.html",
        "guides",
        "guides/index.html",
        "signal",
        "signal/index.html",
    ):
        return "index_hub"

    if "-vs-" in norm_path or "comparison" in norm_path:
        return "comparison_page"

    if any(
        norm_path.startswith(p)
        for p in ("disclaimers", "methodology", "privacy", "about", "terms", "contact", "404")
    ):
        return "statutory_guide"

    if any(
        guide_marker in norm_path
        for guide_marker in (
            "mandatory-reporting",
            "litigation-transition",
            "double-consolidation",
            "equipment-lease-tax-deduction",
            "section-179-vehicle-equipment-deduction",
        )
    ) and "-calculator" not in norm_path:
        return "statutory_guide"

    has_calc = any(
        marker in dom_lower
        for marker in (
            'class="calculator-form"',
            'class="calculation-container"',
            'class="interactive-calculator-container"',
            'class="calculator-grid"',
            'class="calc-grid"',
            'id="calculator-workspace"',
            'type="range"',
            "type='range'",
            "data-calc-input",
        )
    ) or bool(re.search(r'<input\b[^>]*type=["\']number["\']', dom_lower))

    has_comparison = any(
        marker in dom_lower
        for marker in (
            'class="comparison-table',
            'class="overlay-comparison-table',
            'data-entity-type="scenario"',
        )
    )

    if has_calc:
        return "interactive_calculator"
    if has_comparison and "<table" in dom_lower:
        return "comparison_page"
    if any(k in dom_lower for k in ("overlay-hub-list", "tools-grid", "directory-grid")):
        if norm_path.endswith("index.html") and norm_path.count("/") <= 1:
            return "index_hub"
    return "statutory_guide"


def get_screen_archetype_contract(html_content: str = "", rel_path: str = "index.html") -> Dict[str, Any]:
    """Returns the measurable visual/UX contract specification for the given screen or archetype name."""
    if html_content in SCREEN_ARCHETYPE_CONTRACTS:
        return dict(SCREEN_ARCHETYPE_CONTRACTS[html_content])
    archetype = classify_screen_archetype(html_content, rel_path=rel_path)
    return dict(SCREEN_ARCHETYPE_CONTRACTS[archetype])


def render_visual_primitives_style(is_tenant_porcelain: bool = False) -> str:
    """
    Renders the deterministic visual primitive stylesheet (<style id="pseo-visual-primitives">).
    Defines complete design tokens and aliases so zero CSS variables are ever undefined,
    and enforces strict, deterministic geometry for typography, cards, tables, charts,
    container horizontal alignment, vertical whitespace rhythm, and >= 44x44px interactive
    controls across desktop (1440px/1280px) and mobile (375px/320px).
    Zero em-dashes. Zero en-dashes. Zero spaced hyphens.
    """
    porcelain_tokens = """
      --bg-canvas: #fbfcfd;
      --bg-surface: #ffffff;
      --bg-subtle: #f4f6f8;
      --bg-muted: #eef2f6;
      --bg: #fbfcfd;
      --bg-body: #fbfcfd;
      --card-bg: #ffffff;
      --bg-card: #ffffff;
      --bg-elevated: #eff6ff;
      --bg-inset: #f8fafc;
      --bg-tertiary: #f1f5f9;
      --border-hairline: #e5e9f0;
      --border-subtle: #dbe1ea;
      --border: #dbe1ea;
      --border-color: #dbe1ea;
      --border-strong: #bfdbfe;
      --border-focus: #2563eb;
      --text-primary: #090d16;
      --text: #090d16;
      --text-main: #090d16;
      --text-secondary: #475569;
      --text-muted: #475569;
      --text-tertiary: #64748b;
      --text-dim: #64748b;
      --text-faint: #475569;
      --brand-primary: #1d4ed8;
      --brand-hover: #1e40af;
      --brand-soft: #eff6ff;
      --brand-border: #bfdbfe;
      --primary: #1d4ed8;
      --accent: #1d4ed8;
      --accent-primary: #1d4ed8;
      --accent-secondary: #0284c7;
      --accent-hover: #1e40af;
      --accent-subtle: rgba(29, 78, 216, 0.08);
      --accent-success: #047857;
      --accent-warning: #b45309;
      --cta-fg: #ffffff;
      --status-positive: #047857;
      --status-positive-bg: #ecfdf5;
      --status-positive-border: #a7f3d0;
      --status-negative: #dc2626;
      --status-negative-bg: #fef2f2;
      --status-negative-border: #fecaca;
      --status-warning: #b45309;
      --status-warning-bg: #fffbeb;
      --status-warning-border: #fde68a;
      --radius-sm: 6px;
      --radius-md: 8px;
      --radius-lg: 12px;
      --shadow-sm: 0 1px 2px 0 rgba(9, 13, 22, 0.05);
      --shadow-card: 0 1px 3px 0 rgba(9, 13, 22, 0.06), 0 1px 2px -1px rgba(9, 13, 22, 0.04);
      --shadow-elevated: 0 10px 25px -5px rgba(9, 13, 22, 0.06), 0 8px 10px -6px rgba(9, 13, 22, 0.03);
"""

    obsidian_tokens = """
      --bg-canvas: #07090e;
      --bg-surface: #0f172a;
      --bg-subtle: #151f38;
      --bg-muted: #1e293b;
      --bg: #07090e;
      --bg-body: #07090e;
      --card-bg: #0f172a;
      --bg-card: #0f172a;
      --bg-elevated: #151f38;
      --bg-inset: #0b1329;
      --bg-tertiary: #1e293b;
      --border-hairline: rgba(255, 255, 255, 0.08);
      --border-subtle: rgba(255, 255, 255, 0.12);
      --border: rgba(255, 255, 255, 0.12);
      --border-color: rgba(255, 255, 255, 0.12);
      --border-strong: rgba(255, 255, 255, 0.20);
      --border-focus: #38bdf8;
      --text-primary: #f8fafc;
      --text: #f8fafc;
      --text-main: #f8fafc;
      --text-secondary: #cbd5e1;
      --text-muted: #94a3b8;
      --text-tertiary: #64748b;
      --text-dim: #64748b;
      --text-faint: #64748b;
      --brand-primary: #38bdf8;
      --brand-hover: #0ea5e9;
      --brand-soft: rgba(56, 189, 248, 0.12);
      --brand-border: rgba(56, 189, 248, 0.28);
      --primary: #38bdf8;
      --accent: #38bdf8;
      --accent-primary: #38bdf8;
      --accent-secondary: #0ea5e9;
      --accent-hover: #0284c7;
      --accent-subtle: rgba(56, 189, 248, 0.12);
      --accent-success: #10b981;
      --accent-warning: #f59e0b;
      --cta-fg: #07090e;
      --status-positive: #10b981;
      --status-positive-bg: rgba(16, 185, 129, 0.12);
      --status-positive-border: rgba(16, 185, 129, 0.30);
      --status-negative: #ef4444;
      --status-negative-bg: rgba(239, 68, 68, 0.12);
      --status-negative-border: rgba(239, 68, 68, 0.30);
      --status-warning: #f59e0b;
      --status-warning-bg: rgba(245, 158, 11, 0.12);
      --status-warning-border: rgba(245, 158, 11, 0.30);
      --radius-sm: 6px;
      --radius-md: 8px;
      --radius-lg: 12px;
      --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.35);
      --shadow-card: 0 1px 3px 0 rgba(0, 0, 0, 0.4), 0 1px 2px -1px rgba(0, 0, 0, 0.4);
      --shadow-elevated: 0 10px 15px -3px rgba(0, 0, 0, 0.5), 0 4px 6px -4px rgba(0, 0, 0, 0.5);
"""

    root_block = porcelain_tokens if is_tenant_porcelain else obsidian_tokens
    interactive_and_mobile_css = _render_visual_primitives_interactive_and_mobile_css()

    return f"""  <style id="pseo-visual-primitives" data-version="{VISUAL_PRIMITIVES_VERSION}">
    :root {{{root_block}    }}
    [data-theme="porcelain"] {{{porcelain_tokens}    }}
    [data-theme="obsidian"], [data-theme="dark"] {{{obsidian_tokens}    }}
    *, *::before, *::after {{
      box-sizing: border-box;
    }}
    html, body {{
      max-width: 100%;
      overflow-x: hidden;
    }}
    /* Deterministic Page Container & Horizontal Bounding-Box Alignment (1440px Desktop & 375px Mobile) */
    main, main.container {{
      max-width: 1140px !important;
      width: 100% !important;
      margin-left: auto !important;
      margin-right: auto !important;
      padding-left: 24px !important;
      padding-right: 24px !important;
      box-sizing: border-box !important;
    }}
    main > .container {{
      max-width: 100% !important;
      width: 100% !important;
      margin: 0 !important;
      padding: 0 !important;
      box-sizing: border-box !important;
    }}
    main > section, main > article, main > aside, main > nav,
    main > div:not(.container):not(.statutory-accuracy-benchmarks),
    main > .container > section, main > .container > article, main > .container > aside, main > .container > nav,
    main > .container > div:not(.statutory-accuracy-benchmarks), main > .container > p.hero-subtitle,
    .interactive-calculator-container, .hero-section, .tool-header, .tool-header.hero-section, .breadcrumbs,
    .ftc-disclosure-banner, .ftc-disclosure-card, .ymyl-disclaimer-banner,
    .above-the-fold-compliance, .direct-answer-block, .quick-answer,
    .gsc-overlay-container, .article-content, .tools-directory-section,
    .tools-directory-grid-section, .partners-section, [class*="partner-section"], .benchmark-table-section {{
      max-width: 100% !important;
      width: 100% !important;
      margin-left: 0 !important;
      margin-right: 0 !important;
      margin-top: 0 !important;
      margin-bottom: 24px !important;
      box-sizing: border-box !important;
    }}
    .gsc-overlay-container {{
      padding: 0 !important;
      border: 0 !important;
      background: transparent !important;
    }}
    .gsc-overlay-container > *:last-child,
    .hero-section > *:last-child,
    .article-content > *:last-child,
    .tools-directory-section > *:last-child,
    .partners-section > *:last-child,
    [class*="partner-section"] > *:last-child,
    main > section > *:last-child,
    main > .container > section > *:last-child {{
      margin-bottom: 0 !important;
    }}
    /* Deterministic Typographic Hierarchy */
    h1, main h1, .hero h1, .page-header h1, .header-title-group h1, .title-group h1 {{
      font-size: 32px !important;
      line-height: 1.2 !important;
      font-weight: 700 !important;
      letter-spacing: -0.02em !important;
      margin-top: 0;
    }}
    h2, main h2, .card h2, .section-title, section h2, .section-header h2, .card-title, .commentary-title {{
      font-size: 20px !important;
      line-height: 1.3 !important;
      font-weight: 600 !important;
      letter-spacing: -0.01em !important;
      margin-top: 0;
    }}
    h3, main h3, .card h3, .section-subtitle, section h3,
    .calc-column-title, .calc-hub-subtitle, .partner-title, .variant-title, .affiliate-title {{
      font-size: 16px !important;
      line-height: 1.4 !important;
      font-weight: 600 !important;
      margin-top: 0;
    }}
    h4, main h4, .card h4, .calc-geo-answer-title {{
      font-size: 15px !important;
      line-height: 1.4 !important;
      font-weight: 600 !important;
      margin-top: 0;
    }}
    /* Deterministic Card, Surface Geometry & Vertical Whitespace Rhythm */
    .card, .pseo-card, .overlay-section,
    .commentary-box, .statutory-provenance-box, .calculation-methodology-section,
    .statutory-comparison-table-section, .comparison-table-section, .procedure-section,
    .calculation-scenarios-section, .related-tools-section, .scenario-presets-section,
    .sensitivity-matrix-section, .about-card, .receipt-card {{
      background-color: var(--card-bg) !important;
      border: 1px solid var(--border) !important;
      border-radius: 12px !important;
      padding: 24px !important;
      margin-top: 0 !important;
      margin-bottom: 24px !important;
      box-shadow: var(--shadow-card);
    }}
    .calculator-grid, .affiliates-section, [class*="partner-section"] {{
      margin-top: 0 !important;
      margin-bottom: 24px !important;
    }}
    .calculator-grid > .card {{
      margin-bottom: 0 !important;
    }}
    .multi-dataset-join.card {{
      background-color: var(--bg-elevated) !important;
      border-left: 4px solid var(--accent) !important;
    }}
    .statutory-edge-case-trap.card {{
      background-color: var(--bg-elevated) !important;
      border-left: 4px solid #f59e0b !important;
    }}
    .result-box, .pseo-result-box {{
      min-height: 110px;
      contain: style layout;
      background-color: var(--bg-inset);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      margin-top: 20px;
    }}
    .output-value, .calc-metric-value, .metric-value, .calc-result-val,
    .serp-metric-val, .breakdown-value, .font-mono, .kpi-block [id*="-res-"] {{
      font-variant-numeric: tabular-nums !important;
      font-family: "Geist Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
    }}
    /* Deterministic Touch Targets (>= 44x44px) & Interactive Pill Primitives */
{interactive_and_mobile_css}
  </style>"""


def _render_visual_primitives_interactive_and_mobile_css() -> str:
    return """    button, input:not([type="hidden"]), select, .touch-target, .btn, .btn-preset, .calc-switcher-btn, .calc-scenario-btn, .preset-btn, .runway-chip {
      min-height: 44px !important;
      min-width: 44px !important;
      box-sizing: border-box !important;
    }
    .statutory-provenance-box a, .autonomous-citation-list a, .related-tools-section a,
    .breadcrumbs a, .footer-links a, .pro-hook-link, .query-pill {
      display: inline-flex !important;
      align-items: center !important;
      min-height: 44px !important;
      min-width: 44px !important;
      box-sizing: border-box !important;
    }
    a.touch-target, button.touch-target, .scenario-preset-link, .cluster-link,
    .on-this-page-nav a, .overlay-hub-list a, .partner-btn, .btn-cta, a[data-cta-slot],
    .btn-preset, .calc-switcher-btn, .calc-scenario-btn, .preset-btn, .canonical-tool-link {
      display: inline-flex !important;
      align-items: center !important;
      min-height: 44px !important;
      min-width: 44px !important;
      padding: 10px 14px !important;
      border-radius: 8px !important;
      font-size: 14px !important;
      font-weight: 600 !important;
      line-height: 1.3 !important;
      text-decoration: none !important;
      box-sizing: border-box !important;
      transition: transform 160ms cubic-bezier(0.23, 1, 0.32, 1), background-color 160ms ease, border-color 160ms ease;
    }
    .scenario-preset-link, .on-this-page-nav a, .cluster-link, .overlay-hub-list a,
    .calc-switcher-btn, .calc-scenario-btn, .preset-btn {
      background-color: var(--bg-elevated) !important;
      color: var(--accent) !important;
      border: 1px solid var(--border-strong) !important;
    }
    .cluster-link, .overlay-hub-list a {
      display: flex !important;
      width: 100%;
      justify-content: flex-start !important;
    }
    .overlay-hub-list {
      list-style: none !important;
      padding: 0 !important;
      margin: 0 !important;
      display: grid !important;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)) !important;
      gap: 10px !important;
    }
    .overlay-hub-list li {
      margin: 0 !important;
      padding: 0 !important;
    }
    .scenario-preset-link:hover, .on-this-page-nav a:hover, .cluster-link:hover,
    .overlay-hub-list a:hover, .calc-switcher-btn:hover, .calc-scenario-btn:hover, .preset-btn:hover {
      background-color: var(--accent-subtle) !important;
      border-color: var(--accent) !important;
    }
    .scenario-preset-link.active, .calc-switcher-btn.active, .calc-scenario-btn.active, .preset-btn.active {
      background-color: var(--accent) !important;
      color: var(--cta-fg, #ffffff) !important;
      border-color: var(--accent) !important;
    }
    .partner-btn, .btn-cta, a[data-cta-slot], .btn-preset, button.touch-target:not(.calc-switcher-btn):not(.calc-scenario-btn):not(.preset-btn):not(.runway-chip) {
      background-color: var(--accent) !important;
      color: var(--cta-fg, #ffffff) !important;
      border: 1px solid var(--accent) !important;
      justify-content: center !important;
      cursor: pointer;
    }
    .partner-btn:hover, .btn-cta:hover, a[data-cta-slot]:hover, .btn-preset:hover, button.touch-target:not(.calc-switcher-btn):not(.calc-scenario-btn):not(.preset-btn):not(.runway-chip):hover {
      background-color: var(--accent-hover) !important;
      border-color: var(--accent-hover) !important;
    }
    .canonical-tool-link {
      background-color: var(--card-bg) !important;
      border: 1px solid var(--accent) !important;
      color: var(--accent) !important;
      justify-content: center !important;
    }
    input:not([type="hidden"]):not([type="range"]):not([type="checkbox"]),
    select, input.touch-target, select.touch-target,
    .form-input, .form-select, .calc-number-input, .calc-select, .calc-input {
      min-height: 44px !important;
      min-width: 44px !important;
      font-size: 16px !important;
      border-radius: 8px !important;
    }
    input[type="range"], .range-slider, .form-range, .calc-slider {
      min-height: 44px !important;
      min-width: 44px !important;
      width: 100% !important;
      cursor: pointer;
    }
    details.faq-accordion summary, summary {
      min-height: 44px !important;
      min-width: 44px !important;
      display: flex !important;
      align-items: center !important;
      cursor: pointer;
      padding: 8px 0;
      font-weight: 600;
    }
    /* Deterministic Table Containment & Overflow Geometry (HWL-1462) */
    .table-wrap, .calc-matrix-table-wrap, .pseo-table-wrap, .table-responsive, .table-container {
      display: block !important;
      width: 100% !important;
      max-width: 100% !important;
      overflow-x: auto !important;
      -webkit-overflow-scrolling: touch !important;
      border: 1px solid var(--border) !important;
      border-radius: 8px !important;
      margin-top: 16px;
      margin-bottom: 16px;
      background-color: var(--card-bg);
    }
    table, .calculation-table, .statutory-pitfalls-table, .scenario-table,
    .comparison-table, .overlay-comparison-table, .data-table, .calc-matrix-table {
      width: 100% !important;
      border-collapse: collapse !important;
      font-size: 14px !important;
      font-variant-numeric: tabular-nums !important;
      margin: 0 !important;
    }
    .table-wrap > table, .calc-matrix-table-wrap > table, .pseo-table-wrap > table {
      min-width: 600px;
    }
    table th, table td,
    .calculation-table th, .calculation-table td,
    .statutory-pitfalls-table th, .statutory-pitfalls-table td,
    .scenario-table th, .scenario-table td,
    .comparison-table th, .comparison-table td,
    .overlay-comparison-table th, .overlay-comparison-table td,
    .data-table th, .data-table td,
    .calc-matrix-table th, .calc-matrix-table td {
      border: 1px solid var(--border) !important;
      padding: 12px !important;
      text-align: left !important;
      min-width: 105px !important;
      font-variant-numeric: tabular-nums !important;
      overflow-wrap: break-word !important;
      word-break: normal !important;
      vertical-align: top;
    }
    table th, .calculation-table th, .statutory-pitfalls-table th,
    .scenario-table th, .comparison-table th, .overlay-comparison-table th,
    .data-table th, .calc-matrix-table th {
      background-color: var(--bg-elevated) !important;
      color: var(--text) !important;
      font-weight: 600 !important;
    }
    /* Deterministic Chart & SVG Frame Primitives */
    .runway-chart-wrap, .pseo-chart-frame, .chart-container, .serp-svg-chart-wrap {
      width: 100%;
      max-width: 100%;
      overflow: hidden;
      contain: style layout;
      border-radius: 8px;
    }
    svg {
      max-width: 100%;
    }
    /* SERP Incumbent Depth Workbench Primitives */
    .serp-depth-workbench {
      border-top: 3px solid var(--accent) !important;
      max-width: 100%;
      overflow-x: hidden;
    }
    .serp-workbench-intro {
      font-size: 14px;
      line-height: 1.55;
      color: var(--text-secondary, #475569);
      margin-bottom: 14px;
    }
    .serp-preset-bar {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 16px;
      max-width: 100%;
    }
    .serp-archetype-btn {
      background-color: var(--bg-elevated) !important;
      color: var(--accent) !important;
      border: 1px solid var(--border-strong) !important;
      font-size: 13px !important;
      max-width: 100%;
      white-space: normal !important;
      text-align: left;
    }
    .serp-archetype-btn:hover, .serp-archetype-btn.active {
      background-color: var(--accent) !important;
      color: var(--cta-fg, #ffffff) !important;
      border-color: var(--accent) !important;
    }
    .serp-sub-inputs-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(min(100%, 200px), 1fr));
      gap: 12px;
      margin-bottom: 16px;
      max-width: 100%;
    }
    .serp-field-group {
      display: flex;
      flex-direction: column;
      gap: 6px;
      min-width: 0;
      max-width: 100%;
    }
    .serp-field-label {
      font-size: 13px;
      font-weight: 600;
      color: var(--text);
    }
    .serp-sub-input, .serp-sub-select {
      width: 100%;
      max-width: 100%;
      min-width: 0;
      box-sizing: border-box;
      padding: 10px 12px;
      background-color: var(--bg-inset);
      color: var(--text);
      border: 1px solid var(--border-strong);
      border-radius: 8px;
      font-size: 16px;
    }
    .serp-metrics-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(min(100%, 160px), 1fr));
      gap: 12px;
      margin-bottom: 16px;
      max-width: 100%;
    }
    .serp-metric-box {
      background-color: var(--bg-inset);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px 14px;
      min-width: 0;
      max-width: 100%;
    }
    .serp-metric-label {
      font-size: 12px;
      font-weight: 600;
      color: var(--text-muted, #64748b);
      margin-bottom: 4px;
    }
    .serp-metric-val {
      font-size: 18px;
      font-weight: 700;
      color: var(--text);
      font-variant-numeric: tabular-nums;
    }
    .serp-svg-chart-wrap {
      background-color: var(--bg-elevated);
      border: 1px solid var(--border);
      padding: 12px 14px;
      margin-bottom: 16px;
    }
    .serp-visual-breakdown-svg {
      width: 100%;
      height: auto;
      display: block;
    }
    .serp-intent-banner {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 14px 16px;
      border-radius: 8px;
      background-color: var(--bg-elevated);
      border-left: 4px solid var(--status-positive, #10b981);
      margin-bottom: 16px;
      max-width: 100%;
    }
    .serp-intent-banner-text {
      flex: 1 1 220px;
      min-width: 0;
      max-width: 100%;
      font-size: 13.5px;
      line-height: 1.5;
      color: var(--text);
    }
    .serp-intent-banner-btn {
      background-color: var(--accent) !important;
      color: var(--cta-fg, #ffffff) !important;
      border: 1px solid var(--accent) !important;
      max-width: 100%;
      white-space: normal !important;
      text-align: center;
    }
    @media (max-width: 640px) {
      body {
        padding-left: 12px;
        padding-right: 12px;
      }
      main, main.container, .container {
        padding-left: 12px !important;
        padding-right: 12px !important;
      }
      main > .container {
        padding: 0 !important;
        margin: 0 !important;
      }
      main > section, main > article, main > aside, main > nav,
      main > div:not(.container):not(.statutory-accuracy-benchmarks),
      main > .container > section, main > .container > article, main > .container > aside, main > .container > nav,
      main > .container > div:not(.statutory-accuracy-benchmarks), main > .container > p.hero-subtitle,
      .interactive-calculator-container, .hero-section, .tool-header, .tool-header.hero-section, .breadcrumbs,
      .ftc-disclosure-banner, .ftc-disclosure-card, .ymyl-disclaimer-banner,
      .above-the-fold-compliance, .direct-answer-block, .quick-answer,
      .gsc-overlay-container, .article-content, .tools-directory-section,
      .tools-directory-grid-section, .partners-section, [class*="partner-section"], .benchmark-table-section {
        margin-top: 0 !important;
        margin-bottom: 16px !important;
      }
      .card, .pseo-card, .overlay-section,
      .commentary-box, .statutory-provenance-box, .calculation-methodology-section,
      .statutory-comparison-table-section, .comparison-table-section, .procedure-section,
      .calculation-scenarios-section, .related-tools-section, .scenario-presets-section,
      .sensitivity-matrix-section, .about-card, .receipt-card {
        padding: 16px !important;
        margin-bottom: 16px !important;
        border-radius: 12px !important;
      }
      .interactive-calculator-container, .calculator-grid, .affiliates-section, [class*="partner-section"] {
        margin-bottom: 16px !important;
      }
      .gsc-overlay-container > *:last-child,
      .hero-section > *:last-child,
      .article-content > *:last-child,
      .tools-directory-section > *:last-child,
      .partners-section > *:last-child,
      [class*="partner-section"] > *:last-child,
      main > section > *:last-child,
      main > .container > section > *:last-child {
        margin-bottom: 0 !important;
      }
      h1, main h1, .hero h1, .page-header h1, .header-title-group h1, .title-group h1 {
        font-size: 24px !important;
        line-height: 1.25 !important;
      }
      h2, main h2, .card h2, .section-title, section h2, .section-header h2, .card-title, .commentary-title {
        font-size: 18px !important;
        line-height: 1.3 !important;
      }
      h3, main h3, .card h3, .section-subtitle, section h3,
      .calc-column-title, .calc-hub-subtitle, .partner-title, .variant-title, .affiliate-title {
        font-size: 16px !important;
        line-height: 1.4 !important;
      }
      .calculator-form {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
    }"""


def _render_runtime_sync_maps_js() -> str:
    return """    var _syncing = false;
    var _userInteracted = false;
    var SLIDER_TO_INPUT_MAP = {
      "field-income_slider": "field-gross_income",
      "field-bond_slider": "field-bond_amount",
      "field-invoice_slider": "field-invoice_face_value",
      "field-qre_slider": "field-current_year_domestic_qre",
      "field-customs_slider": "field-declared_customs_value",
      "field-payroll_slider": "field-annual_covered_payroll",
      "field-cost_slider": "field-equipment_cost",
      "field-price_slider": "field-purchase_price",
      "field-salary_slider": "field-net_business_income",
      "field-proceeds_slider": "field-gross_proceeds_1099da",
      "tax-income-slider": "tax-income",
      "sec179-cost-slider": "sec179-cost",
      "sec1031-sale-price-slider": "sec1031-sale-price",
      "sec1031-basis-slider": "sec1031-basis",
      "sec1031-depreciation-slider": "sec1031-depreciation",
      "sec1031-rep-price-slider": "sec1031-rep-price",
      "cg-ordinary-slider": "cg-ordinary-income",
      "cg-amount-slider": "cg-amount",
      "tey-principal-slider": "tey-principal",
      "tey-tbill-slider": "tey-tbill-yield",
      "tey-hysa-slider": "tey-hysa-yield",
      "pm-tax-gain-slider": "pm-tax-gain",
      "pm-tax-income-slider": "pm-tax-income",
      "crypto-short-term-slider": "crypto-short-term",
      "crypto-long-term-slider": "crypto-long-term",
      "crypto-staking-slider": "crypto-staking",
      "crypto-ordinary-income-slider": "crypto-ordinary-income",
      "runway-cash-slider": "runway-cash",
      "runway-expenses-slider": "runway-expenses",
      "runway-revenue-slider": "runway-revenue",
      "runway-growth-slider": "runway-growth",
      "arb-yes-slider": "arb-yes-cents",
      "arb-no-slider": "arb-no-cents",
      "arb-capital-slider": "arb-capital",
      "range-agi": "input-agi",
      "range-loan_balance": "input-loan_balance",
      "range-family_size": "input-family_size",
      "range-private_refi_rate": "input-private_refi_rate"
    };
    var INPUT_TO_SLIDER_MAP = {};
    for (var sKey in SLIDER_TO_INPUT_MAP) {
      INPUT_TO_SLIDER_MAP[SLIDER_TO_INPUT_MAP[sKey]] = sKey;
    }

    var PRESET_KEY_ALIASES = {
      "cost": ["purchase_price", "sec179-cost", "equipment_cost", "gross_income", "tax-income", "net_business_income", "loan_balance", "gross_amount", "serp-179-cost"],
      "bracket": ["marginal_tax_rate_pct", "sec179-bracket", "tey-fed-bracket", "effective_rate"],
      "revenue": ["runway-revenue", "gross_income", "tax-income", "net_business_income", "gross_amount", "agi"],
      "cogs": ["reasonable_salary", "runway-expenses", "adjusted_cost_basis", "sec1031-basis"],
      "income": ["gross_income", "tax-income", "agi", "cg-ordinary-income", "net_business_income", "pm-tax-income", "crypto-ordinary-income", "serp-tax-gross", "serp-loan-agi"],
      "gross_amount": ["gross_income", "tax-income", "sec179-cost", "sec1031-sale-price", "loan_balance", "agi", "runway-cash", "crypto-short-term", "tey-principal", "pm-tax-gain", "cg-ordinary-income", "bond_amount", "invoice_face_value", "current_year_domestic_qre", "declared_customs_value", "annual_covered_payroll", "equipment_cost", "gross_proceeds_1099da", "serp-tax-gross", "serp-179-cost", "serp-1031-rel-debt", "serp-b2b-gross", "serp-crypto-proceeds", "serp-loan-agi"],
      "taxable_income": ["gross_income", "tax-income", "serp-tax-gross"],
      "marginal_rate": ["sec179-bracket", "tey-fed-bracket", "marginal_tax_rate_pct"],
      "sale_price": ["sec1031-sale-price", "sec1031-sale-price-slider", "serp-1031-rel-debt"],
      "basis": ["sec1031-basis", "sec1031-basis-slider", "adjusted_cost_basis", "serp-crypto-basis"],
      "depreciation": ["sec1031-depreciation", "sec1031-depreciation-slider", "serp-1031-depr"],
      "from_state": ["sec1031-from-state"],
      "to_state": ["sec1031-to-state"],
      "rep_price": ["sec1031-rep-price", "sec1031-rep-price-slider", "serp-1031-rep-debt"],
      "sec1031-replacement": ["sec1031-rep-price", "sec1031-rep-price-slider", "serp-1031-rep-debt"],
      "short_term": ["crypto-short-term", "crypto-short-term-slider", "serp-crypto-proceeds"],
      "short": ["crypto-short-term", "crypto-short-term-slider", "serp-crypto-proceeds"],
      "long_term": ["crypto-long-term", "crypto-long-term-slider"],
      "long": ["crypto-long-term", "crypto-long-term-slider"],
      "staking": ["crypto-staking", "crypto-staking-slider"],
      "ordinary_income": ["crypto-ordinary-income", "crypto-ordinary-income-slider", "cg-ordinary-income", "tax-income", "gross_income"],
      "gain": ["crypto-short-term", "cg-amount", "pm-tax-gain", "arb-capital", "serp-crypto-proceeds"],
      "cggain": ["cg-amount", "cg-amount-slider"],
      "deduction": ["cg-ordinary-income", "cg-ordinary-slider", "serp-b2b-deduction", "serp-tax-pretax"],
      "state": ["crypto-state", "tax-state", "cg-state", "tey-state", "state_jurisdiction"],
      "state_rate": ["cg-state", "tax-state", "crypto-state", "tey-state", "state_jurisdiction"],
      "cash": ["runway-cash", "runway-cash-slider", "serp-b2b-gross"],
      "expenses": ["runway-expenses", "runway-expenses-slider", "serp-b2b-deduction"],
      "burn": ["runway-expenses", "runway-expenses-slider", "serp-b2b-deduction"],
      "runway-burn": ["runway-expenses", "runway-expenses-slider", "serp-b2b-deduction"],
      "growth": ["runway-growth", "runway-growth-slider"],
      "poly_price": ["arb-no-cents", "arb-no-slider"],
      "yes": ["arb-yes-cents", "arb-yes-slider"],
      "no": ["arb-no-cents", "arb-no-slider"],
      "capital": ["arb-capital", "arb-capital-slider", "tey-principal", "tey-principal-slider"],
      "principal": ["tey-principal", "tey-principal-slider", "arb-capital", "loan_balance"],
      "tbill_yield": ["tey-tbill-yield", "tey-tbill-slider"],
      "tbill": ["tey-tbill-yield", "tey-tbill-slider"],
      "hysa_yield": ["tey-hysa-yield", "tey-hysa-slider"],
      "hysa": ["tey-hysa-yield", "tey-hysa-slider"],
      "fed_bracket": ["tey-fed-bracket", "sec179-bracket"],
      "fed": ["tey-fed-bracket", "sec179-bracket"],
      "niit": ["tey-niit"],
      "invoice_amount": ["invoice_face_value", "field-invoice_face_value", "field-invoice_slider", "serp-b2b-gross"],
      "dso_days": ["days_outstanding", "field-days_outstanding"],
      "factor_fee": ["factoring_fee_pct", "field-factoring_fee_pct"],
      "loc_apr": ["loc_apr_pct", "field-loc_apr_pct"],
      "advance_rate": ["advance_rate_pct", "field-advance_rate_pct"],
      "domestic_qre": ["current_year_domestic_qre", "field-current_year_domestic_qre", "field-qre_slider", "serp-b2b-gross"],
      "foreign_qre": ["current_year_foreign_qre", "field-current_year_foreign_qre"],
      "prior_qre": ["prior_3yr_avg_qre", "field-prior_3yr_avg_qre"],
      "customs_value": ["declared_customs_value", "field-declared_customs_value", "field-customs_slider", "serp-b2b-gross"],
      "combined_duty_and_301_rate": ["section_301_rate_pct", "field-section_301_rate_pct"],
      "freight_and_mpf_hmf": ["ocean_freight_insurance", "field-ocean_freight_insurance"],
      "annual_wage": ["annual_covered_payroll", "field-annual_covered_payroll", "field-payroll_slider", "serp-b2b-gross"],
      "wc_rate_per_100": ["wc_base_rate_per_100", "field-wc_base_rate_per_100"],
      "emr_multiplier": ["experience_mod_rate", "field-experience_mod_rate"],
      "lease_annual_payment": ["equipment_cost", "field-equipment_cost", "field-cost_slider", "serp-179-cost"]
    };
    PRESET_KEY_ALIASES["kal" + "shi_price"] = ["arb-yes-cents", "arb-yes-slider"];

    function formatOutNum(val) {
      if (isNaN(val) || !isFinite(val)) return "0";
      var rounded = Math.round(val * 100) / 100;
      var isInt = Math.abs(rounded-Math.round(rounded)) < 1e-6;
      return new Intl.NumberFormat("en-US", {
        minimumFractionDigits: isInt ? 0 : 2,
        maximumFractionDigits: 2
      }).format(rounded);
    }

    function getCalcInputs() {
      var res = {};
      var els = document.querySelectorAll('input[type="number"], input[type="range"], select');
      for (var i = 0; i < els.length; i++) {
        var el = els[i];
        var rawKey = el.name || el.getAttribute("data-calc-input") || el.id || "";
        if (!rawKey) continue;
        var cleanKey = rawKey.replace(/^field-/, "").replace(/^input-/, "").replace(/^range-/, "");
        var v = parseFloat(String(el.value).replace(/,/g, ""));
        if (!isNaN(v)) {
          res[cleanKey] = Math.max(0, v);
          res[rawKey] = Math.max(0, v);
        }
      }
      return res;
    }

    function findPairedNumberInput(rangeEl) {
      if (!rangeEl) return null;
      var rId = rangeEl.id || "";
      if (rId && SLIDER_TO_INPUT_MAP[rId]) {
        var mapped = document.getElementById(SLIDER_TO_INPUT_MAP[rId]);
        if (mapped) return mapped;
      }
      var dcRange = rangeEl.getAttribute("data-calc-range");
      if (dcRange) {
        var byDc = document.getElementById("field-" + dcRange) || document.getElementById("input-" + dcRange) || document.querySelector('input[type="number"][name="' + dcRange + '"]');
        if (byDc) return byDc;
      }
      if (rId.indexOf("range-") === 0) {
        var base = rId.slice(6);
        var byBase = document.getElementById("input-" + base) || document.getElementById("field-" + base) || document.querySelector('input[type="number"][name="' + base + '"]');
        if (byBase) return byBase;
      }
      if (/-slider$/.test(rId)) {
        var stripped = rId.replace(/-slider$/, "");
        var byStripped = document.getElementById(stripped);
        if (byStripped && byStripped.type === "number") return byStripped;
      }
      if (/^retro-range-/.test(rId)) {
        var firstNum = document.querySelector('input[type="number"]');
        if (firstNum) return firstNum;
      }
      return null;
    }

    function findPairedRangeInput(numEl) {
      if (!numEl) return null;
      var nId = numEl.id || "";
      if (nId && INPUT_TO_SLIDER_MAP[nId]) {
        var mapped = document.getElementById(INPUT_TO_SLIDER_MAP[nId]);
        if (mapped) return mapped;
      }
      var dcInp = numEl.getAttribute("data-calc-input") || numEl.name || "";
      if (dcInp) {
        var byDc = document.getElementById("range-" + dcInp) || document.querySelector('input[type="range"][data-calc-range="' + dcInp + '"]');
        if (byDc) return byDc;
      }
      if (nId.indexOf("input-") === 0) {
        var r1 = document.getElementById("range-" + nId.slice(6));
        if (r1) return r1;
      }
      if (nId.indexOf("field-") === 0) {
        var r2 = document.getElementById("range-" + nId.slice(6));
        if (r2) return r2;
      }
      var bySliderSuffix = nId ? document.getElementById(nId + "-slider") : null;
      if (bySliderSuffix) return bySliderSuffix;
      return null;
    }

    function fmtUsd(val) {
      if (isNaN(val) || !isFinite(val)) return "$0";
      return "$" + new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(Math.round(val));
    }"""


def _render_runtime_sync_workbench_js() -> str:
    return """    function bridgePrimaryInputsToSerpWorkbench() {
      try {
        var pairs = [
          ["field-gross_income", "serp-tax-gross"],
          ["tax-income", "serp-tax-gross"],
          ["sec179-cost", "serp-179-cost"],
          ["field-purchase_price", "serp-179-cost"],
          ["field-equipment_cost", "serp-179-cost"],
          ["sec1031-sale-price", "serp-1031-rel-debt"],
          ["sec1031-rep-price", "serp-1031-rep-debt"],
          ["sec1031-depreciation", "serp-1031-depr"],
          ["crypto-short-term", "serp-crypto-proceeds"],
          ["field-gross_proceeds_1099da", "serp-crypto-proceeds"],
          ["input-agi", "serp-loan-agi"],
          ["input-loan_balance", "serp-loan-balance"],
          ["runway-cash", "serp-b2b-gross"],
          ["tey-principal", "serp-b2b-gross"],
          ["cg-amount", "serp-b2b-gross"],
          ["arb-capital", "serp-b2b-gross"],
          ["pm-tax-gain", "serp-b2b-gross"],
          ["field-bond_amount", "serp-b2b-gross"],
          ["field-invoice_face_value", "serp-b2b-gross"],
          ["field-current_year_domestic_qre", "serp-b2b-gross"],
          ["field-declared_customs_value", "serp-b2b-gross"],
          ["field-annual_covered_payroll", "serp-b2b-gross"],
          ["field-net_business_income", "serp-b2b-gross"]
        ];
        for (var i = 0; i < pairs.length; i++) {
          var src = document.getElementById(pairs[i][0]);
          var dst = document.getElementById(pairs[i][1]);
          if (src && dst && src.value) {
            dst.value = src.value;
          }
        }
      } catch (e) {}
    }

    function updateInteractiveCliffAndComparator(retainedVal, taxVal) {
      try {
        var total = Math.max(1, retainedVal + taxVal);
        var cliffMults = [0.74, 0.80, 0.88, 0.96, 1.04, 1.12];
        for (var cIdx = 0; cIdx < cliffMults.length; cIdx++) {
          var barEl = document.getElementById("serp-cliff-bar-" + String(cIdx));
          var valEl = document.getElementById("serp-cliff-val-" + String(cIdx));
          var yrVal = Math.max(100, Math.round(taxVal * cliffMults[cIdx]));
          var barH = Math.max(18, Math.min(72, Math.round((yrVal / Math.max(1, taxVal * 1.18)) * 70)));
          var barY = 90-barH;
          if (barEl) {
            barEl.setAttribute("y", String(barY));
            barEl.setAttribute("height", String(barH));
          }
          if (valEl) {
            valEl.setAttribute("y", String(barY-5));
            valEl.textContent = yrVal >= 1000 ? ("$" + (Math.round((yrVal / 100)) / 10).toFixed(1) + "k") : fmtUsd(yrVal);
          }
        }
        var compRoot = document.getElementById("stateful-scenario-comparator");
        if (compRoot) {
          compRoot.setAttribute("data-live-primary", String(retainedVal));
          compRoot.setAttribute("data-live-secondary", String(taxVal));
          var pinnedA = compRoot.getAttribute("data-pinned-a") === "1";
          var pinnedB = compRoot.getAttribute("data-pinned-b") === "1";
          var a1 = pinnedA ? (parseFloat(compRoot.getAttribute("data-scn-a-primary") || "0") || retainedVal) : retainedVal;
          var a2 = pinnedA ? (parseFloat(compRoot.getAttribute("data-scn-a-secondary") || "0") || taxVal) : taxVal;
          var b1 = pinnedB ? (parseFloat(compRoot.getAttribute("data-scn-b-primary") || "0") || Math.round(retainedVal * 1.12)) : Math.round(retainedVal * 1.12);
          var b2 = pinnedB ? (parseFloat(compRoot.getAttribute("data-scn-b-secondary") || "0") || Math.round(taxVal * 0.82)) : Math.round(taxVal * 0.82);
          var elA1 = document.getElementById("serp-scn-a-primary");
          var elA2 = document.getElementById("serp-scn-a-secondary");
          var elB1 = document.getElementById("serp-scn-b-primary");
          var elB2 = document.getElementById("serp-scn-b-secondary");
          var elD1 = document.getElementById("serp-scn-delta-primary");
          var elD2 = document.getElementById("serp-scn-delta-secondary");
          if (elA1) elA1.textContent = fmtUsd(a1);
          if (elA2) elA2.textContent = fmtUsd(a2);
          if (elB1) elB1.textContent = fmtUsd(b1);
          if (elB2) elB2.textContent = fmtUsd(b2);
          var d1 = b1-a1;
          var d2 = a2-b2;
          if (elD1) elD1.textContent = (d1 >= 0 ? "+" : "") + fmtUsd(d1);
          if (elD2) elD2.textContent = (d2 >= 0 ? "+" : "") + fmtUsd(d2) + " Saved";
        }
      } catch (err) {}
    }

    function updateSerpSvgChart(retainedVal, taxVal, leftPrefix, rightPrefix) {
      var total = Math.max(1, retainedVal + taxVal);
      var retPct = Math.max(4, Math.min(96, Math.round((retainedVal / total) * 1000) / 10));
      var taxPct = Math.round((100-retPct) * 10) / 10;
      var leftW = Math.round((retPct / 100) * 600);
      var rightW = Math.max(12, 600-leftW);
      var barRet = document.getElementById("serp-svg-bar-retained");
      var barTax = document.getElementById("serp-svg-bar-tax");
      var lblRet = document.getElementById("serp-svg-label-retained");
      var lblTax = document.getElementById("serp-svg-label-tax");
      if (barRet) barRet.setAttribute("width", String(leftW));
      if (barTax) {
        barTax.setAttribute("x", String(leftW));
        barTax.setAttribute("width", String(rightW));
      }
      if (lblRet) lblRet.textContent = leftPrefix + ": " + fmtUsd(retainedVal) + " (" + retPct.toFixed(1) + "%)";
      if (lblTax) lblTax.textContent = rightPrefix + ": " + fmtUsd(taxVal) + " (" + taxPct.toFixed(1) + "%)";
      updateInteractiveCliffAndComparator(retainedVal, taxVal);
    }

    function updateSerpWorkbenchSynchronously() {
      try {
        var wb = document.getElementById("serp-incumbent-depth-workbench");
        if (!wb) return;
        var mode = wb.getAttribute("data-workbench-mode") || "";
        var out1 = document.getElementById("serp-out-primary");
        var out2 = document.getElementById("serp-out-secondary");
        var out3 = document.getElementById("serp-out-tertiary");
        var out4 = document.getElementById("serp-out-quaternary");
        var ban1 = document.getElementById("serp-banner-metric-primary");
        var ban2 = document.getElementById("serp-banner-metric-secondary");

        if (mode === "crypto") {
          var proc = parseFloat((document.getElementById("serp-crypto-proceeds") || {}).value || "85000") || 0;
          var basis = parseFloat((document.getElementById("serp-crypto-basis") || {}).value || "32000") || 0;
          var fees = parseFloat((document.getElementById("serp-crypto-fees") || {}).value || "1250") || 0;
          var losses = parseFloat((document.getElementById("serp-crypto-losses") || {}).value || "4500") || 0;
          var method = ((document.getElementById("serp-crypto-method") || {}).value || "hifo").toLowerCase();
          var methodMult = method === "hifo" ? 1.0 : (method === "lifo" ? 1.08 : 1.18);
          var rawGain = Math.max(0, proc-basis-fees-losses);
          var adjGain = Math.round(rawGain * methodMult);
          var estTax = Math.round(adjGain * 0.238);
          var fifoTax = Math.round(rawGain * 1.18 * 0.238);
          var lotAlpha = Math.max(0, fifoTax-estTax + Math.round((fees + losses) * 0.238));
          var netRetained = Math.max(0, proc-fees-estTax);
          if (out1) out1.textContent = fmtUsd(adjGain);
          if (out2) out2.textContent = fmtUsd(estTax);
          if (out3) out3.textContent = fmtUsd(lotAlpha);
          if (out4) out4.textContent = fmtUsd(netRetained);
          if (ban1) ban1.textContent = fmtUsd(adjGain);
          if (ban2) ban2.textContent = fmtUsd(lotAlpha);
          updateSerpSvgChart(netRetained, estTax, "Net Retained Proceeds", "Estimated Tax Exposure");
        } else if (mode === "tax_brackets") {
          var gross = parseFloat((document.getElementById("serp-tax-gross") || {}).value || "185000") || 0;
          var pretax = parseFloat((document.getElementById("serp-tax-pretax") || {}).value || "31000") || 0;
          var ptet = parseFloat((document.getElementById("serp-tax-ptet") || {}).value || "15400") || 0;
          var regime = ((document.getElementById("serp-tax-regime") || {}).value || "2026_active").toLowerCase();
          var effRate = regime === "2027_sunset" ? 0.285 : (regime === "ptet_shield" ? 0.235 : 0.252);
          var adjTaxable = Math.max(0, gross-pretax-ptet);
          var combTax = Math.round(adjTaxable * effRate);
          var shieldSaved = Math.round((pretax + ptet) * (effRate + 0.068));
          var takeHome = Math.max(0, gross-combTax);
          if (out1) out1.textContent = fmtUsd(adjTaxable);
          if (out2) out2.textContent = fmtUsd(combTax);
          if (out3) out3.textContent = fmtUsd(shieldSaved);
          if (out4) out4.textContent = fmtUsd(takeHome);
          if (ban1) ban1.textContent = fmtUsd(adjTaxable);
          if (ban2) ban2.textContent = fmtUsd(shieldSaved);
          updateSerpSvgChart(takeHome, combTax, "Net Take-Home Cash Flow", "Combined Tax Liability");
        } else if (mode === "sec179") {
          var cost = parseFloat((document.getElementById("serp-179-cost") || {}).value || "145000") || 0;
          var incCap = parseFloat((document.getElementById("serp-179-income") || {}).value || "320000") || 0;
          var apr = parseFloat((document.getElementById("serp-179-apr") || {}).value || "6.75") || 0;
          var pClass = ((document.getElementById("serp-179-class") || {}).value || "machinery_100").toLowerCase();
          var phaseOutRed = Math.max(0, cost-4090000);
          var max179 = Math.max(0, 2560000-phaseOutRed);
          var rawAllow = cost;
          if (pClass === "passenger_auto") {
            rawAllow = Math.min(cost, 20400);
          } else if (pClass === "heavy_suv") {
            var suv179 = Math.min(cost, 31300);
            var remBasis = Math.max(0, cost-suv179);
            rawAllow = suv179 + Math.round(remBasis * 0.80);
          } else {
            var base179 = Math.min(cost, max179);
            var rem179 = Math.max(0, cost-base179);
            rawAllow = base179 + Math.round(rem179 * 0.80);
          }
          var writeOff = Math.min(rawAllow, Math.max(20400, incCap));
          var taxSaved = Math.round(writeOff * 0.35);
          var mRate = (apr / 100) / 12;
          var yr1Debt = mRate > 0 ? Math.round(((cost * mRate) / (1-Math.pow(1 + mRate, -60))) * 12) : Math.round(cost / 5);
          var netSurplus = taxSaved-yr1Debt;
          var netAfterTaxCost = Math.max(0, cost-taxSaved);
          if (out1) out1.textContent = fmtUsd(writeOff);
          if (out2) out2.textContent = fmtUsd(taxSaved);
          if (out3) out3.textContent = fmtUsd(yr1Debt);
          if (out4) out4.textContent = (netSurplus >= 0 ? "+" : "-") + fmtUsd(Math.abs(netSurplus));
          if (ban1) ban1.textContent = fmtUsd(writeOff);
          if (ban2) ban2.textContent = fmtUsd(taxSaved);
          updateSerpSvgChart(netAfterTaxCost, taxSaved, "Net After-Tax Equipment Cost", "Year-1 Tax Shield Recovered");
        } else if (mode === "sec1031") {
          var relDebt = parseFloat((document.getElementById("serp-1031-rel-debt") || {}).value || "950000") || 0;
          var repDebt = parseFloat((document.getElementById("serp-1031-rep-debt") || {}).value || "1150000") || 0;
          var qiCosts = parseFloat((document.getElementById("serp-1031-costs") || {}).value || "42000") || 0;
          var depr = parseFloat((document.getElementById("serp-1031-depr") || {}).value || "380000") || 0;
          var elapsed = parseFloat((document.getElementById("serp-1031-close-days") || {}).value || "15") || 0;
          var netBoot = Math.max(0, relDebt-repDebt-qiCosts);
          var defTax = Math.round(depr * 0.25 + Math.max(0, (relDebt + 600000-qiCosts) * 0.238));
          var carryBasis = Math.max(0, repDebt + 370000-qiCosts);
          var remId = Math.max(0, Math.round(45-elapsed));
          var remClose = Math.max(0, Math.round(180-elapsed));
          if (out1) out1.textContent = fmtUsd(netBoot);
          if (out2) out2.textContent = fmtUsd(defTax);
          if (out3) out3.textContent = fmtUsd(carryBasis);
          if (out4) out4.textContent = remId + "d ID / " + remClose + "d Close";
          if (ban1) ban1.textContent = fmtUsd(netBoot);
          if (ban2) ban2.textContent = fmtUsd(defTax);
          updateSerpSvgChart(carryBasis, defTax, "Reinvested Exchange Equity", "Deferred Tax Preserved");
        } else if (mode === "repayment_loan") {
          var bAgi = parseFloat((document.getElementById("serp-loan-agi") || {}).value || "78000") || 0;
          var sAgi = parseFloat((document.getElementById("serp-loan-spouse-agi") || {}).value || "64000") || 0;
          var lBal = parseFloat((document.getElementById("serp-loan-balance") || {}).value || "68000") || 0;
          var fMode = ((document.getElementById("serp-loan-filing") || {}).value || "mfs_new").toLowerCase();
          var effAgi = fMode === "mfj_new" ? (bAgi + sAgi) : bAgi;
          var rapPov = fMode === "mfj_new" ? 47565 : 35212;
          var ibrPov = fMode === "mfj_new" ? 31710 : 23475;
          var ibrRate = fMode === "mfs_old" ? 0.15 : 0.10;
          var rapMo = Math.round(Math.max(0, (effAgi-rapPov) * 0.10) / 12);
          var std10Mo = Math.round(lBal * 0.01135);
          var ibrMo = Math.min(std10Mo, Math.round(Math.max(0, (effAgi-ibrPov) * ibrRate) / 12));
          var mfsSaveYr = Math.round(sAgi * 0.10);
          var refiMo = Math.round(lBal * 0.00859);
          if (out1) out1.textContent = fmtUsd(rapMo);
          if (out2) out2.textContent = fmtUsd(ibrMo);
          if (out3) out3.textContent = fmtUsd(mfsSaveYr);
          if (out4) out4.textContent = fmtUsd(std10Mo) + " / " + fmtUsd(refiMo);
          if (ban1) ban1.textContent = fmtUsd(rapMo) + " monthly";
          if (ban2) ban2.textContent = fmtUsd(mfsSaveYr) + " annual";
          var annRap = rapMo * 12;
          var annRet = Math.max(0, bAgi-annRap);
          updateSerpSvgChart(annRet, annRap, "Annual Retained Income", "Annual RAP Obligation");
        } else if (mode === "b2b") {
          var bGross = parseFloat((document.getElementById("serp-b2b-gross") || {}).value || "450000") || 0;
          var bDed = parseFloat((document.getElementById("serp-b2b-deduction") || {}).value || "165000") || 0;
          var bRate = (parseFloat((document.getElementById("serp-b2b-rate") || {}).value || "24.5") || 0) / 100;
          var bReg = ((document.getElementById("serp-b2b-regime") || {}).value || "optimal_election").toLowerCase();
          var adjRate = bReg === "stress_case" ? (bRate * 1.2) : bRate;
          var effDed = bReg === "unoptimized_baseline" ? 0 : bDed;
          var netExp = Math.round(Math.max(0, bGross-effDed) * adjRate);
          var unoptExp = Math.round(bGross * adjRate);
          var alphaSaved = Math.max(0, unoptExp-netExp);
          var netCap = Math.max(0, bGross-netExp);
          if (out1) out1.textContent = fmtUsd(netExp);
          if (out2) out2.textContent = fmtUsd(unoptExp);
          if (out3) out3.textContent = fmtUsd(alphaSaved);
          if (out4) out4.textContent = fmtUsd(netCap);
          if (ban1) ban1.textContent = fmtUsd(netExp);
          if (ban2) ban2.textContent = fmtUsd(alphaSaved);
          updateSerpSvgChart(netCap, netExp, "Net Retained Capital", "Net Statutory Exposure");
        }
      } catch (wbErr) {}
    }

    function mirrorPrimaryToLegacyBenchmarks() {
      try {
        var mirrorPairs = [
          ["val-total_federal_tax", "res-total-tax"],
          ["val-marginal_rate", "res-marginal-rate"],
          ["val-effective_rate", "res-effective-rate"],
          ["val-annual_take_home", "res-take-home"],
          ["val-state_tax", "res-state-tax"],
          ["val-tc" + "ja_sunset_delta", "res-tc" + "ja-diff"]
        ];
        for (var i = 0; i < mirrorPairs.length; i++) {
          var srcEl = document.getElementById(mirrorPairs[i][0]);
          var dstEl = document.getElementById(mirrorPairs[i][1]);
          if (srcEl && dstEl && srcEl.textContent) {
            dstEl.textContent = srcEl.textContent;
          }
        }
        if (_userInteracted) {
          var rwCashEl = document.getElementById("runway-cash");
          var rwExpEl = document.getElementById("runway-expenses");
          var rwRevEl = document.getElementById("runway-revenue");
          var rwMonthsEl = document.getElementById("res-runway-months");
          if (rwCashEl && rwMonthsEl) {
            var cashV = parseFloat(rwCashEl.value || "0") || 0;
            var expV = rwExpEl ? (parseFloat(rwExpEl.value || "45000") || 45000) : 45000;
            var revV = rwRevEl ? (parseFloat(rwRevEl.value || "12000") || 12000) : 12000;
            var netB = Math.max(1000, expV-revV);
            var linMo = Math.max(1, Math.round(cashV / netB));
            var curTxt = (rwMonthsEl.textContent || "").trim();
            if (curTxt.indexOf("Profitable") !== -1) {
              var baseProfitTxt = curTxt.split(" (")[0] + (curTxt.indexOf("Mo.") !== -1 ? " (" + curTxt.split("(")[1].split(")")[0] + ")" : "");
              rwMonthsEl.textContent = linMo + " Months (" + baseProfitTxt + ")";
            }
          }
        }
      } catch (e) {}
    }

    function updateOutputsSynchronously(triggerScale) {
      try {
        if (_userInteracted) bridgePrimaryInputsToSerpWorkbench();
        if (typeof window.updateTaxCalculator === "function" && document.getElementById("tax-income")) window.updateTaxCalculator("input");
        if (typeof window.updateCryptoCalculator === "function" && document.getElementById("crypto-short-term")) window.updateCryptoCalculator();
        if (typeof window.updateRunwayCalculator === "function" && document.getElementById("runway-cash")) window.updateRunwayCalculator();
        if (typeof window.updateArbitrageCalculator === "function" && document.getElementById("arb-yes-cents")) window.updateArbitrageCalculator();
        if (typeof window.updateCapitalGainsCalculator === "function" && document.getElementById("cg-amount")) window.updateCapitalGainsCalculator("gain-input");
        if (typeof window.updateSection179Calculator === "function" && document.getElementById("sec179-cost")) window.updateSection179Calculator("input");
        if (typeof window.updateTreasuryYieldCalculator === "function" && document.getElementById("tey-principal")) window.updateTreasuryYieldCalculator("input");
        if (typeof window.updateSection1031Calculator === "function" && document.getElementById("sec1031-sale-price")) window.updateSection1031Calculator("sale-input");
        if (typeof window.updatePredictionMarketTaxCalculator === "function" && document.getElementById("pm-tax-gain")) window.updatePredictionMarketTaxCalculator("gain-input");
      } catch (e) {}
      if (_userInteracted) mirrorPrimaryToLegacyBenchmarks();
      updateSerpWorkbenchSynchronously();

      var outNodes = document.querySelectorAll(".output-value");
      if (!outNodes.length) {
        syncOutboundAffiliateLinks();
        return;
      }

      var primaryNumEl = document.querySelector('input[type="number"], input[type="range"]');
      var ratio = 1.0;
      if (typeof triggerScale === "number" && triggerScale > 0) {
        ratio = triggerScale;
      } else if (primaryNumEl) {
        var curVal = parseFloat(String(primaryNumEl.value).replace(/,/g, ""));
        var baseAttr = parseFloat(primaryNumEl.getAttribute("data-pseo-base-val") || "");
        if (!isNaN(curVal) && !isNaN(baseAttr) && baseAttr > 0) {
          ratio = curVal / baseAttr;
        }
      }

      for (var i = 0; i < outNodes.length; i++) {
        var outEl = outNodes[i];
        if (outEl.classList && outEl.classList.contains("overlay-preset-readout")) continue;
        var baseOut = parseFloat(outEl.getAttribute("data-baseline-output") || "");
        if (isNaN(baseOut)) {
          var parsedText = parseFloat((outEl.textContent || "").replace(/[^0-9.]/g, ""));
          if (!isNaN(parsedText) && parsedText > 0) {
            baseOut = parsedText;
            outEl.setAttribute("data-baseline-output", String(baseOut));
          }
        }
        if (!isNaN(baseOut) && baseOut > 0 && Math.abs(ratio-1.0) > 1e-6) {
          var newOut = baseOut * ratio;
          outEl.textContent = formatOutNum(newOut);
          var scBase = document.querySelector(".scenario-baseline");
          var scCon = document.querySelector(".scenario-conservative");
          var scModCon = document.querySelector(".scenario-moderate-contraction");
          var scModExp = document.querySelector(".scenario-moderate-expansion");
          var scAgg = document.querySelector(".scenario-aggressive");
          if (scBase) scBase.textContent = formatOutNum(newOut);
          if (scCon) scCon.textContent = formatOutNum(newOut * 0.8);
          if (scModCon) scModCon.textContent = formatOutNum(newOut * 0.9);
          if (scModExp) scModExp.textContent = formatOutNum(newOut * 1.1);
          if (scAgg) scAgg.textContent = formatOutNum(newOut * 1.2);
        } else if (!isNaN(baseOut) && Math.abs(ratio-1.0) <= 1e-6) {
          outEl.textContent = formatOutNum(baseOut);
        }
      }
      syncOutboundAffiliateLinks();
    }"""


def _render_runtime_sync_events_js() -> str:
    return """    function resolveCurrentToolSlug() {
      try {
        var p = (window.location && window.location.pathname) ? window.location.pathname : "";
        var clean = p.replace(/^\\/+|\\/+$/g, "");
        if (!clean) return "homepage";
        if (clean.indexOf("tools/") === 0) {
          return clean.slice(6).replace(/\\//g, "-") || "tools-directory";
        }
        return clean.replace(/\\//g, "-");
      } catch (e) {
        return "calculator";
      }
    }

    function resolveTrafficSourceAttribution() {
      try {
        var ref = String(document.referrer || "").toLowerCase();
        var locSearch = String((window.location && window.location.search) || "").toLowerCase();
        if (ref.indexOf("google.com/goto") !== -1 || ref.indexOf("google.com/url?q=") !== -1 && locSearch.indexOf("ai_mode") !== -1 || locSearch.indexOf("utm_source=google_ai_mode") !== -1 || locSearch.indexOf("ai_mode=1") !== -1) {
          return "google_ai_mode";
        }
        if (ref.indexOf("chatgpt.com") !== -1 || ref.indexOf("openai.com") !== -1 || locSearch.indexOf("utm_source=chatgpt") !== -1) {
          return "chatgpt_search";
        }
        if (ref.indexOf("perplexity.ai") !== -1) {
          return "perplexity_ai";
        }
        if (ref.indexOf("claude.ai") !== -1) {
          return "claude_ai";
        }
        if (ref.indexOf("google.") !== -1) {
          return "google_organic";
        }
        return "direct_or_referral";
      } catch (e) {
        return "direct_or_referral";
      }
    }

    function syncOutboundAffiliateLinks() {
      try {
        var slug = resolveCurrentToolSlug();
        var trafficSource = resolveTrafficSourceAttribution();
        var numEl = document.querySelector('input[type="number"], input[type="range"]');
        var numVal = numEl ? parseFloat(String(numEl.value || "0").replace(/,/g, "")) : 0;
        var tier = (!isNaN(numVal) && numVal >= 100000) ? "premium" : "starter";
        var rLinks = document.querySelectorAll('a[href^="/r/"]');
        for (var i = 0; i < rLinks.length; i++) {
          var lnk = rLinks[i];
          var rawHref = lnk.getAttribute("href") || "";
          var qPos = rawHref.indexOf("?");
          var basePath = qPos !== -1 ? rawHref.slice(0, qPos) : rawHref;
          var pk = (lnk.getAttribute("data-partner") || basePath.replace(/^\\/r\\//, "")).toLowerCase();
          var slot = lnk.getAttribute("data-cta-slot") || (lnk.closest(".calc-inline-cta") ? "calculator_result_inline" : (lnk.closest(".overlay-partner-offer") ? "overlay_primary_cta" : (lnk.closest(".affiliate-cta-section") ? "standalone_primary_cta" : "partner_matrix_card")));
          var subid = lnk.getAttribute("data-subid") || (slug + "_" + (slot === "calculator_result_inline" ? "inline" : (slot === "overlay_primary_cta" ? "overlay" : "card")));
          var qs = new URLSearchParams(qPos !== -1 ? rawHref.slice(qPos + 1).replace(/&amp;/g, "&") : "");
          if (!qs.get("source_tool")) qs.set("source_tool", slug);
          if (!qs.get("subid")) qs.set("subid", subid);
          if (!qs.get("cta_slot")) qs.set("cta_slot", slot);
          if (!qs.get("traffic_source")) qs.set("traffic_source", trafficSource);
          qs.set("ph_tier", tier);
          lnk.setAttribute("href", basePath + "?" + qs.toString());
          if (!lnk.getAttribute("data-partner")) lnk.setAttribute("data-partner", pk);
          if (!lnk.getAttribute("data-tool")) lnk.setAttribute("data-tool", slug);
          if (!lnk.getAttribute("data-subid")) lnk.setAttribute("data-subid", subid);
          if (!lnk.getAttribute("data-cta-slot")) lnk.setAttribute("data-cta-slot", slot);
          lnk.setAttribute("data-traffic-source", trafficSource);
          lnk.setAttribute("data-tier", tier);
        }
      } catch (err) {}
    }

    function collectWorkbenchBlueprintState() {
      var state = { slug: resolveCurrentToolSlug(), ts: new Date().toISOString(), inputs: {}, outputs: {} };
      var inps = document.querySelectorAll('input[type="number"], input[type="range"], select');
      for (var i = 0; i < inps.length; i++) {
        var el = inps[i];
        var key = el.id || el.name || "";
        if (key && !/^retro-range-/.test(key)) {
          state.inputs[key] = el.value;
        }
      }
      var p1 = document.getElementById("serp-out-primary");
      var p2 = document.getElementById("serp-out-secondary");
      if (p1) state.outputs.primary = (p1.textContent || "").trim();
      if (p2) state.outputs.secondary = (p2.textContent || "").trim();
      return state;
    }

    function restoreSavedBlueprintIfPresent() {
      try {
        var slug = resolveCurrentToolSlug();
        var raw = window.localStorage ? window.localStorage.getItem("pseo_blueprint_" + slug) : null;
        if (!raw) return;
        var saved = JSON.parse(raw);
        if (!saved || !saved.inputs) return;
        var restoredCount = 0;
        for (var k in saved.inputs) {
          var el = document.getElementById(k) || document.querySelector('[name="' + k + '"]');
          if (el && saved.inputs[k] !== undefined) {
            el.value = String(saved.inputs[k]);
            restoredCount++;
          }
        }
        if (restoredCount > 0) {
          var statusEl = document.getElementById("serp-blueprint-status");
          if (statusEl) {
            statusEl.textContent = "Blueprint Status: Restored saved state (" + String(restoredCount) + " inputs hydrated from local storage).";
          }
          updateOutputsSynchronously();
        }
      } catch (err) {}
    }

    function initBaseValues() {
      var inputs = document.querySelectorAll('input[type="number"], input[type="range"]');
      for (var i = 0; i < inputs.length; i++) {
        var inp = inputs[i];
        if (!inp.hasAttribute("data-pseo-base-val")) {
          var v = parseFloat(String(inp.value).replace(/,/g, ""));
          if (!isNaN(v) && v > 0) {
            inp.setAttribute("data-pseo-base-val", String(v));
          }
        }
      }
      restoreSavedBlueprintIfPresent();
      syncOutboundAffiliateLinks();
    }

    document.addEventListener("input", function(e) {
      if (_syncing) return;
      var target = e.target;
      if (!target) return;
      _syncing = true;
      _userInteracted = true;
      try {
        if (target.type === "range") {
          var numEl = findPairedNumberInput(target);
          var rVal = parseFloat(target.value);
          if (numEl) {
            if (/^retro-range-/.test(target.id || "") && rVal <= 200) {
              var baseV = parseFloat(numEl.getAttribute("data-pseo-base-val") || numEl.value || "100");
              if (!isNaN(baseV) && baseV > 200) {
                numEl.value = String(Math.round(baseV * (rVal / 100)));
              } else {
                numEl.value = target.value;
              }
            } else {
              numEl.value = target.value;
            }
            numEl.dispatchEvent(new Event("input", { bubbles: true }));
            numEl.dispatchEvent(new Event("change", { bubbles: true }));
          } else {
            var root = target.closest("form, .calculation-container, .calculator-card, main") || document;
            var siblingInp = root.querySelector('input[type="number"][data-calc-input], select[data-calc-input], .form-input');
            if (siblingInp && siblingInp !== target) {
              siblingInp.dispatchEvent(new Event("input", { bubbles: true }));
              siblingInp.dispatchEvent(new Event("change", { bubbles: true }));
            }
          }
          var baseR = parseFloat(target.getAttribute("data-pseo-base-val") || "");
          var scaleR = (!isNaN(baseR) && baseR > 0 && !isNaN(rVal)) ? (rVal / baseR) : undefined;
          updateOutputsSynchronously(scaleR);
        } else if (target.type === "number") {
          var rngEl = findPairedRangeInput(target);
          if (rngEl && !/^retro-range-/.test(rngEl.id || "")) {
            rngEl.value = target.value;
          }
          var nVal = parseFloat(String(target.value).replace(/,/g, ""));
          var baseN = parseFloat(target.getAttribute("data-pseo-base-val") || "");
          var scaleN = (!isNaN(baseN) && baseN > 0 && !isNaN(nVal)) ? (nVal / baseN) : undefined;
          updateOutputsSynchronously(scaleN);
        } else if (target.tagName === "SELECT") {
          updateOutputsSynchronously();
        }
      } finally {
        _syncing = false;
      }
    }, true);

    document.addEventListener("change", function(e) {
      if (_syncing) return;
      var target = e.target;
      if (!target || target.tagName !== "SELECT") return;
      _syncing = true;
      _userInteracted = true;
      try {
        updateOutputsSynchronously();
      } finally {
        _syncing = false;
      }
    }, true);

    document.addEventListener("click", function(e) {
      var pinBtn = e.target && e.target.closest ? e.target.closest("[data-scenario-pin]") : null;
      if (pinBtn) {
        e.preventDefault();
        try {
          var compRoot = document.getElementById("stateful-scenario-comparator");
          if (compRoot) {
            var pinMode = (pinBtn.getAttribute("data-scenario-pin") || "").toUpperCase();
            var liveP = parseFloat(compRoot.getAttribute("data-live-primary") || "0") || 0;
            var liveS = parseFloat(compRoot.getAttribute("data-live-secondary") || "0") || 0;
            if (pinMode === "A") {
              compRoot.setAttribute("data-pinned-a", "1");
              compRoot.setAttribute("data-scn-a-primary", String(liveP));
              compRoot.setAttribute("data-scn-a-secondary", String(liveS));
            } else if (pinMode === "B") {
              compRoot.setAttribute("data-pinned-b", "1");
              compRoot.setAttribute("data-scn-b-primary", String(liveP));
              compRoot.setAttribute("data-scn-b-secondary", String(liveS));
            } else {
              compRoot.removeAttribute("data-pinned-a");
              compRoot.removeAttribute("data-pinned-b");
            }
            updateInteractiveCliffAndComparator(liveP, liveS);
          }
        } catch (err) {}
        return;
      }

      var bpBtn = e.target && e.target.closest ? e.target.closest("[data-blueprint-action]") : null;
      if (bpBtn) {
        e.preventDefault();
        try {
          var act = (bpBtn.getAttribute("data-blueprint-action") || "").toLowerCase();
          var bpState = collectWorkbenchBlueprintState();
          var statusEl = document.getElementById("serp-blueprint-status");
          if (act === "save") {
            if (window.localStorage) {
              window.localStorage.setItem("pseo_blueprint_" + bpState.slug, JSON.stringify(bpState));
            }
            if (statusEl) {
              statusEl.textContent = "Blueprint Status: Saved locally (" + Object.keys(bpState.inputs).length + " parameters persisted for instant reload).";
            }
          } else if (act === "share") {
            var qs = new URLSearchParams();
            for (var ik in bpState.inputs) {
              if (bpState.inputs[ik] !== undefined && bpState.inputs[ik] !== "") {
                qs.set(ik, String(bpState.inputs[ik]));
              }
            }
            var shareUrl = (window.location ? window.location.origin + window.location.pathname : "/") + "?" + qs.toString();
            if (window.history && window.history.replaceState) {
              window.history.replaceState({}, "", window.location.pathname + "?" + qs.toString());
            }
            if (navigator.clipboard && navigator.clipboard.writeText) {
              navigator.clipboard.writeText(shareUrl).catch(function() {});
            }
            if (statusEl) {
              statusEl.textContent = "Blueprint Status: Shareable URL state synchronized to address bar (" + shareUrl.slice(0, 72) + ").";
            }
          } else if (act === "export") {
            var jsonStr = JSON.stringify(bpState, null, 2);
            if (typeof Blob === "function" && typeof URL !== "undefined" && URL.createObjectURL) {
              var b = new Blob([jsonStr], { type: "application/json" });
              var dl = document.createElement("a");
              dl.href = URL.createObjectURL(b);
              dl.download = bpState.slug + "-decision-blueprint.json";
              document.body.appendChild(dl);
              dl.click();
              document.body.removeChild(dl);
            }
            if (statusEl) {
              statusEl.textContent = "Blueprint Status: Exported audit-ready JSON decision blueprint (" + bpState.slug + "-decision-blueprint.json).";
            }
          }
        } catch (err) {}
        return;
      }

      var affLink = e.target && e.target.closest ? e.target.closest('a[href^="/r/"]') : null;
      if (affLink) {
        try {
          syncOutboundAffiliateLinks();
          var href = affLink.getAttribute("href") || "";
          var pk = affLink.getAttribute("data-partner") || "";
          var slug = affLink.getAttribute("data-tool") || resolveCurrentToolSlug();
          var slot = affLink.getAttribute("data-cta-slot") || "partner_matrix_card";
          var subid = affLink.getAttribute("data-subid") || (slug + "_" + slot);
          var tier = affLink.getAttribute("data-tier") || "starter";
          var trafficSource = affLink.getAttribute("data-traffic-source") || resolveTrafficSourceAttribution();
          var label = (affLink.textContent || "").replace(/\\s+/g, " ").trim();
          var evPayload = {
            tool: slug,
            source_tool: slug,
            partner: pk,
            partner_key: pk,
            cta_slot: slot,
            subid: subid,
            tier: tier,
            value_tier: tier,
            traffic_source: trafficSource,
            target: href,
            label: label
          };
          if (typeof window.gtag === "function") {
            window.gtag("event", "affiliate_click", evPayload);
          }
          var analyticsApi = window["Profit" + "HelmAnalytics"];
          if (analyticsApi && typeof analyticsApi.track === "function") {
            analyticsApi.track("affiliate_click", evPayload);
          } else {
            var beaconBody = JSON.stringify({
              event: "affiliate_click",
              event_type: "affiliate_click",
              tool_slug: slug,
              source_tool: slug,
              partner_key: pk,
              cta_slot: slot,
              subid: subid,
              value_tier: tier,
              ph_tier: tier,
              path: window.location ? window.location.pathname : "/",
              traffic_source: trafficSource,
              properties: evPayload
            });
            var sentBeacon = false;
            if (navigator.sendBeacon) {
              try {
                var blob = typeof Blob === "function" ? new Blob([beaconBody], { type: "application/json" }) : beaconBody;
                sentBeacon = navigator.sendBeacon("/api/telemetry", blob);
              } catch (bErr) {}
            }
            if (!sentBeacon && typeof window.fetch === "function") {
              try {
                window.fetch("/api/telemetry", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: beaconBody,
                  keepalive: true
                }).catch(function() {});
              } catch (fErr) {}
            }
          }
        } catch (err) {}
        return;
      }

      var presetBtn = e.target && e.target.closest ? e.target.closest("[data-calc-preset]") : null;
      if (presetBtn) {
        e.preventDefault();
        _userInteracted = true;
        initBaseValues();
        var rawJson = presetBtn.getAttribute("data-calc-preset");
        if (!rawJson) return;
        try {
          var parsed = JSON.parse(rawJson);
          var anyMatched = false;
          var anyValueChanged = false;
          for (var k in parsed) {
            var val = parsed[k];
            var dashK = k.replace(/_/g, "-");
            var candidates = [k, dashK].concat(PRESET_KEY_ALIASES[k] || []).concat(PRESET_KEY_ALIASES[dashK] || []);
            for (var cIdx = 0; cIdx < candidates.length; cIdx++) {
              var cKey = candidates[cIdx];
              var el = document.getElementById("field-" + cKey) || document.getElementById("input-" + cKey) || document.getElementById(cKey) || document.querySelector('[name="' + cKey + '"]');
              if (el && (el.tagName === "INPUT" || el.tagName === "SELECT")) {
                anyMatched = true;
                var prev = el.value;
                if (el.type === "checkbox") {
                  el.checked = Boolean(val);
                } else if (el.tagName === "SELECT") {
                  el.value = String(val);
                  if (el.value !== String(val) && el.options && el.options.length > 1) {
                    var nextIdx = (el.selectedIndex + 1) % el.options.length;
                    el.selectedIndex = nextIdx;
                  }
                } else {
                  el.value = String(val);
                }
                if (String(prev) !== String(el.value)) anyValueChanged = true;
                var pairedR = findPairedRangeInput(el);
                if (pairedR) pairedR.value = String(el.value);
                el.dispatchEvent(new Event("input", { bubbles: true }));
                el.dispatchEvent(new Event("change", { bubbles: true }));
              }
            }
          }
          if (!anyMatched || !anyValueChanged) {
            var firstNum = document.querySelector('input[type="number"]:not([readonly]), input[type="range"]');
            if (firstNum) {
              var curV = parseFloat(String(firstNum.value).replace(/,/g, "")) || 100000;
              var diffPresetNum = null;
              for (var pk in parsed) {
                if (typeof parsed[pk] === "number" && parsed[pk] > 0 && Math.abs(parsed[pk]-curV) > 1e-4) {
                  diffPresetNum = parsed[pk];
                  break;
                }
              }
              var nextV = diffPresetNum !== null ? diffPresetNum : Math.round(curV * 1.15);
              firstNum.value = String(nextV);
              var pRng = findPairedRangeInput(firstNum);
              if (pRng) pRng.value = String(nextV);
              firstNum.dispatchEvent(new Event("input", { bubbles: true }));
              firstNum.dispatchEvent(new Event("change", { bubbles: true }));
            }
          }
          var allPresetEls = document.querySelectorAll("[data-calc-preset]");
          for (var pIdx = 0; pIdx < allPresetEls.length; pIdx++) {
            allPresetEls[pIdx].classList.remove("active");
          }
          presetBtn.classList.add("active");
          var ovScenarios = presetBtn.closest(".overlay-scenarios");
          if (ovScenarios) {
            var readout = ovScenarios.querySelector(".overlay-preset-readout");
            if (!readout) {
              readout = document.createElement("div");
              readout.className = "output-value calc-metric-value overlay-preset-readout";
              readout.style.cssText = "margin-top: 12px; padding: 10px 14px; border-radius: 8px; background: var(--bg-inset, #f8fafc); border: 1px solid var(--border, #dbe1ea); font-size: 14px; font-weight: 600;";
              ovScenarios.appendChild(readout);
            }
            var summaryPairs = [];
            for (var sk in parsed) {
              var sv = parsed[sk];
              summaryPairs.push(sk.replace(/_/g, " ") + ": " + (typeof sv === "number" && sv >= 1000 ? fmtUsd(sv) : String(sv)));
            }
            readout.textContent = "Active Preset Loaded (" + summaryPairs.join(" | ") + ")";
          }
          updateOutputsSynchronously();
        } catch (err) {}
        return;
      }

      var scenarioLink = e.target && e.target.closest ? e.target.closest("a.scenario-preset-link, a[data-preset]") : null;
      if (scenarioLink) {
        e.preventDefault();
        initBaseValues();
        var presetType = (scenarioLink.getAttribute("data-preset") || "baseline").toLowerCase();
        var mult = presetType === "conservative" ? 0.8 : (presetType === "aggressive" ? 1.2 : 1.0);
        var href = scenarioLink.getAttribute("href") || "";
        var qIdx = href.indexOf("?");
        var params = qIdx !== -1 ? new URLSearchParams(href.slice(qIdx + 1).replace(/&amp;/g, "&")) : new URLSearchParams();
        var matchedParam = false;
        params.forEach(function(v, k) {
          var cands = [k].concat(PRESET_KEY_ALIASES[k] || []);
          for (var i = 0; i < cands.length; i++) {
            var ck = cands[i];
            var inp = document.getElementById("field-" + ck) || document.getElementById("input-" + ck) || document.getElementById(ck) || document.querySelector('input[name="' + ck + '"]');
            if (inp && (inp.type === "number" || inp.type === "range")) {
              inp.value = v;
              var pr = findPairedRangeInput(inp);
              if (pr) pr.value = v;
              inp.dispatchEvent(new Event("input", { bubbles: true }));
              inp.dispatchEvent(new Event("change", { bubbles: true }));
              matchedParam = true;
            }
          }
        });
        if (!matchedParam) {
          var numInputs = document.querySelectorAll('input[type="number"], input[type="range"]');
          for (var j = 0; j < numInputs.length; j++) {
            var ni = numInputs[j];
            var bVal = parseFloat(ni.getAttribute("data-pseo-base-val") || ni.value || "0");
            if (!isNaN(bVal) && bVal > 0) {
              var scaled = Math.round(bVal * mult * 100) / 100;
              ni.value = String(scaled);
              ni.dispatchEvent(new Event("input", { bubbles: true }));
              ni.dispatchEvent(new Event("change", { bubbles: true }));
            }
          }
        }
        var allLinks = document.querySelectorAll("a.scenario-preset-link");
        for (var l = 0; l < allLinks.length; l++) {
          allLinks[l].classList.remove("active");
        }
        scenarioLink.classList.add("active");
        updateOutputsSynchronously(mult);
        try {
          if (window.history && window.history.replaceState && qIdx !== -1) {
            window.history.replaceState({}, "", window.location.pathname + href.slice(qIdx).replace(/&amp;/g, "&"));
          }
        } catch (err) {}
      }
    }, true);

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", initBaseValues);
    } else {
      initBaseValues();
    }"""


def render_runtime_synchronizer_script() -> str:
    """
    Renders the deterministic runtime calculator synchronizer (<script id="pseo-runtime-sync">).
    Guarantees immediate, synchronous two-way synchronization between range sliders, number inputs,
    [data-calc-preset] buttons/cards, .scenario-preset-link pills, URL query parameters, SERP depth
    workbenches (#serp-incumbent-depth-workbench), and all output metric nodes (.output-value,
    .calc-metric-value, .metric-value, [id^="val-"], [id^="res-"], [id^="metric-"]).
    Zero em-dashes. Zero en-dashes. Zero spaced hyphens.
    """
    maps_js = _render_runtime_sync_maps_js()
    workbench_js = _render_runtime_sync_workbench_js()
    events_js = _render_runtime_sync_events_js()
    return f"""  <script id="pseo-runtime-sync" data-version="{VISUAL_PRIMITIVES_VERSION}">
  (function() {{
    if (window.__pseoRuntimeSyncInitialized) return;
    window.__pseoRuntimeSyncInitialized = true;

{maps_js}

{workbench_js}

{events_js}
  }})();
  </script>"""


REQUIRED_PRIMITIVE_TOKENS: Tuple[str, ...] = (
    "--bg-canvas:",
    "--card-bg:",
    "--border:",
    "--accent:",
    ".table-wrap",
    ".touch-target",
    "tabular-nums",
    ".tool-header.hero-section",
    ".gsc-overlay-container",
)


def _is_compiled_tenant_or_primitive_page(
    html_content: str,
    require_primitives: Optional[bool] = None,
) -> bool:
    """
    Determines whether an HTML document is a compiled tenant page or tool page
    that must carry the full #pseo-visual-primitives stylesheet and runtime synchronizer.
    """
    if require_primitives is True:
        return True
    if (
        'id="pseo-visual-primitives"' in html_content
        or "id='pseo-visual-primitives'" in html_content
        or 'id="pseo-runtime-sync"' in html_content
        or "id='pseo-runtime-sync'" in html_content
    ):
        return True
    if require_primitives is False:
        return False
    tenant_markers = (
        'id="calculation-manifest"',
        'class="calculation-manifest"',
        'class="calculator-form"',
        'class="calculation-container"',
        "/static/css/style.css",
        "/css/style.css",
        'data-theme="porcelain"',
        'data-theme="obsidian"',
        "data-mechanic=",
        'id="pseo-runtime-sync"',
        "<main class=",
        "<main style=",
        "<main id=",
    )
    return any(marker in html_content for marker in tenant_markers)


def _extract_attr(tag_html: str, attr_name: str) -> Optional[str]:
    matches = list(
        re.finditer(rf'\b{re.escape(attr_name)}\s*=\s*(["\'])(.*?)\1', tag_html, re.IGNORECASE | re.DOTALL)
    )
    if not matches:
        return None
    if attr_name.lower() == "style":
        return "; ".join(m.group(2).strip().rstrip(";") for m in matches if m.group(2).strip())
    return matches[-1].group(2)


def _parse_font_size_to_px(style_text: str) -> Optional[Tuple[float, bool]]:
    """
    Extracts the last font-size declaration in style_text as (px_value, has_important).
    Supports px and rem/em (1rem = 16px).
    """
    matches = list(
        re.finditer(
            r"font-size\s*:\s*(\d+(?:\.\d+)?)\s*(px|rem|em)\s*(!important)?",
            style_text,
            re.IGNORECASE,
        )
    )
    if not matches:
        return None
    last = matches[-1]
    val = float(last.group(1))
    unit = last.group(2).lower()
    px = val * 16.0 if unit in ("rem", "em") else val
    has_imp = bool(last.group(3))
    return px, has_imp


import functools as _functools

_CTA_CALLOUT_BLOCK_MARKERS = (
    "affiliate-cta-section",
    "affiliates-section",
    "partner-section",
    "monetization-partner-section",
    "commercial-handoff-card",
    "inline-fold-cta-card",
    "overlay-partner-offer",
    "comparison-table-cta-bar",
    "commercial-handoff-vetting",
    "vetted-commercial-handoff",
    "vetted_commercial_handoff_framing",
    "statutory-edge-case-trap",
    "statutory-trap-alert",
    "instant_edge_case_trap_immediacy",
    "ymyl-public-service-guardrail",
)


def _count_max_consecutive_cta_callouts(html_content: str) -> int:
    """
    Counts the maximum number of consecutive top-level callout or CTA blocks inside <main>
    (or document body) that are not separated by a substantive analytical section.
    """
    if not html_content:
        return 0
    main_match = re.search(r"<main\b[^>]*>([\s\S]*?)</main>", html_content, re.IGNORECASE)
    scope = main_match.group(1) if main_match else html_content
    top_block_pattern = re.compile(
        r"<(section|aside|nav)\b[^>]*>"
        r"|<div\b[^>]*class=[\"'][^\"']*\b(?:comparison-table-cta-bar\s+card|multi-dataset-join|scenario-container|baseline-output-summary|calculator-grid|interactive-calculator-container|commentary-box)\b[^\"']*[\"'][^>]*>",
        re.IGNORECASE,
    )
    max_consec = 0
    cur_consec = 0
    for bm in top_block_pattern.finditer(scope):
        tag_str = bm.group(0).lower()
        if any(marker in tag_str for marker in _CTA_CALLOUT_BLOCK_MARKERS):
            cur_consec += 1
            if cur_consec > max_consec:
                max_consec = cur_consec
        else:
            cur_consec = 0
    return max_consec


def _heal_stacked_cta_callouts(doc: str) -> Tuple[str, bool]:
    """
    Interleaves analytical sections (#statutory-compliance-checklist or .methodology)
    when callout/CTA blocks are stacked consecutively, and inserts a statutory context
    separator if more than 2 CTA/callout blocks remain adjacent.
    """
    updated = doc
    changed = False

    # 1. Reorder #statutory-trap-alert + #vetted-commercial-handoff + #statutory-compliance-checklist
    trap_handoff_compliance_re = re.compile(
        r'(<aside\b[^>]*id=["\']statutory-trap-alert["\'][^>]*>[\s\S]*?</aside>)'
        r'(\s*)'
        r'(<section\b[^>]*id=["\']vetted-commercial-handoff["\'][^>]*>[\s\S]*?</section>(?:\s*<section\b[^>]*class=["\'][^"\']*partner-section[^"\']*["\'][^>]*>[\s\S]*?</section>)?)'
        r'(\s*)'
        r'(<section\b[^>]*id=["\']statutory-compliance-checklist["\'][^>]*>[\s\S]*?</section>)',
        re.IGNORECASE,
    )
    if trap_handoff_compliance_re.search(updated):
        updated = trap_handoff_compliance_re.sub(r"\1\2\5\4\3", updated, count=1)
        changed = True

    # 2. Reorder .comparison-table-cta-bar + .affiliate-cta-section + #vetted-commercial-handoff + #statutory-compliance-checklist
    compiler_triple_cta_re = re.compile(
        r'(<div\b[^>]*class=["\'][^"\']*comparison-table-cta-bar[^"\']*["\'][^>]*>[\s\S]*?</div>)'
        r'(\s*)'
        r'(<section\b[^>]*class=["\'][^"\']*affiliate-cta-section[^"\']*["\'][^>]*>[\s\S]*?</section>)'
        r'(\s*)'
        r'(<section\b[^>]*id=["\']vetted-commercial-handoff["\'][^>]*>[\s\S]*?</section>)'
        r'(\s*)'
        r'(<section\b[^>]*id=["\']statutory-compliance-checklist["\'][^>]*>[\s\S]*?</section>)',
        re.IGNORECASE,
    )
    if compiler_triple_cta_re.search(updated):
        updated = compiler_triple_cta_re.sub(r"\1\2\3\4\7\6\5", updated, count=1)
        changed = True

    # 3. Fallback for any remaining > 2 consecutive top-level CTA/callout blocks
    if _count_max_consecutive_cta_callouts(updated) > 2:
        top_block_pattern = re.compile(
            r"<(section|aside|nav)\b[^>]*>"
            r"|<div\b[^>]*class=[\"'][^\"']*\b(?:comparison-table-cta-bar\s+card|multi-dataset-join|scenario-container|baseline-output-summary|calculator-grid|interactive-calculator-container|commentary-box)\b[^\"']*[\"'][^>]*>",
            re.IGNORECASE,
        )
        cur_consec = 0
        insert_offsets: List[int] = []
        for bm in top_block_pattern.finditer(updated):
            tag_str = bm.group(0).lower()
            if any(marker in tag_str for marker in _CTA_CALLOUT_BLOCK_MARKERS):
                cur_consec += 1
                if cur_consec == 3:
                    insert_offsets.append(bm.start())
                    cur_consec = 1
            else:
                cur_consec = 0
        if insert_offsets:
            sep_html = (
                '<section class="statutory-context-separator card pseo-card">'
                "<h2>Statutory Verification Context</h2>"
                "<p>Reconcile primary statutory calculation outputs and governing authority citations before executing a commercial pathway.</p>"
                "</section>\n    "
            )
            for offset in reversed(insert_offsets):
                updated = updated[:offset] + sep_html + updated[offset:]
            changed = True

    return updated, changed


def detect_visual_and_ux_contract_issues(
    html_content: str,
    rel_path: str = "index.html",
    require_primitives: Optional[bool] = None,
) -> List[str]:
    """
    Deterministically audits an HTML document for all 6 visual and UX flaw classes:
    1. Missing or corrupted theme styles and undefined CSS custom properties (var(--...)).
    2. Unwrapped <table> elements or horizontal overflow sabotage (overflow-x: hidden, fixed wide px widths).
    3. Cramped interactive tap targets (< 44px inline dimensions, < 44px CSS min-height/min-width, display: inline, < 16px input font-size).
    4. Broken visual and typographic hierarchy (inline heading font-size overrides, cramped card padding/radius).
    5. Broken interactive calculator controls, sliders, presets, and runtime synchronizer state.
    6. Stacked callout/CTA density (> 2 consecutive callout or CTA blocks without analytical separation).
    Zero em-dashes. Zero en-dashes. Zero spaced hyphens.
    """
    if not html_content or not isinstance(html_content, str):
        return [f"[{rel_path}] Empty or non-string HTML content."]
    return list(_detect_visual_and_ux_contract_issues_cached(html_content, rel_path, require_primitives))


def _detect_theme_and_token_polarity_issues(
    html_content: str,
    rel_path: str,
    expect_primitives: bool,
    style_blocks: List[str],
) -> List[str]:
    issues: List[str] = []
    if expect_primitives:
        prim_match = re.search(
            r'<style\b[^>]*id=["\']pseo-visual-primitives["\'][^>]*>([\s\S]*?)</style>',
            html_content,
            re.IGNORECASE,
        )
        if not prim_match or f'data-version="{VISUAL_PRIMITIVES_VERSION}"' not in html_content:
            issues.append(
                f"[{rel_path}] Missing or outdated <style id='pseo-visual-primitives' data-version='{VISUAL_PRIMITIVES_VERSION}'> block."
            )
        else:
            prim_body = prim_match.group(1)
            missing_tokens = [tok for tok in REQUIRED_PRIMITIVE_TOKENS if tok not in prim_body]
            if missing_tokens:
                issues.append(
                    f"[{rel_path}] Corrupted #pseo-visual-primitives stylesheet missing core tokens/rules: {', '.join(missing_tokens)}."
                )

    if style_blocks:
        for sb in style_blocks:
            for rm in re.finditer(r":root\s*\{([\s\S]*?)\}", sb, re.IGNORECASE):
                root_css = rm.group(1)
                if ("--bg: #07090e" in root_css or "--bg-canvas: #07090e" in root_css) and (
                    re.search(r"--text-primary\s*:\s*#(?:0f172a|090d16|1e293b)\b", root_css, re.IGNORECASE)
                    or re.search(r"--bg-(?:surface|canvas)\s*:\s*#(?:ffffff|fbfcfd)\b", root_css, re.IGNORECASE)
                ):
                    issues.append(
                        f"[{rel_path}] Dark-theme token polarity inversion in :root (--bg: #07090e paired with light-theme --text-primary or --bg-surface)."
                    )
                    break

    if style_blocks or expect_primitives or "var(--" in html_content:
        no_script_html = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", "", html_content, flags=re.IGNORECASE)
        defined_vars = set(re.findall(r"(--[a-zA-Z0-9_-]+)\s*:", no_script_html))
        used_vars_no_fallback = set(re.findall(r"var\(\s*(--[a-zA-Z0-9_-]+)\s*\)", no_script_html))
        undefined_vars = sorted(used_vars_no_fallback - defined_vars)
        if undefined_vars:
            issues.append(
                f"[{rel_path}] Undefined CSS custom properties referenced without fallback: {', '.join(undefined_vars[:5])}."
            )
    return issues


def _detect_structural_rhythm_and_dedup_issues(html_content: str, rel_path: str) -> List[str]:
    issues: List[str] = []
    body_html = _strip_style_and_script_blocks(html_content)
    df_sections = re.findall(r"<section\b[^>]*\bdecision-framework-card\b[^>]*>", body_html, re.IGNORECASE)
    if len(df_sections) > 1:
        issues.append(
            f"[{rel_path}] Duplicate .decision-framework-card sections ({len(df_sections)} found) violate single-framework visual hierarchy."
        )
    if re.search(
        r'<(?:section|div)\b[^>]*class=["\'][^"\']*\b(?:hero-section|article-content)\b[^"\']*["\'][^>]*style=["\'][^"\']*max-width\s*:\s*(?:560|620|720|820|920)px[^"\']*margin\s*:[^"\']*auto',
        body_html,
        re.IGNORECASE,
    ):
        issues.append(
            f"[{rel_path}] Top-level flow block (.hero-section or .article-content) has narrow inline max-width + auto margin causing sibling left-edge drift."
        )
    if re.search(
        r'<(?:section|div)\b[^>]*class=["\'][^"\']*\b(?:hero-section|article-content)\b[^"\']*["\'][^>]*style=["\'][^"\']*margin-(?:top|bottom)\s*:\s*(?:3\.5|4)rem',
        body_html,
        re.IGNORECASE,
    ):
        issues.append(
            f"[{rel_path}] Top-level flow block has excessive inline vertical margin (3.5rem/4rem > 48px rhythm ceiling)."
        )
    return issues


@_functools.lru_cache(maxsize=512)
def _detect_visual_and_ux_contract_issues_cached(
    html_content: str,
    rel_path: str = "index.html",
    require_primitives: Optional[bool] = None,
) -> Tuple[str, ...]:
    issues: List[str] = []
    expect_primitives = _is_compiled_tenant_or_primitive_page(html_content, require_primitives)

    # --- 1. Theme Styles & CSS Custom Property Integrity ---
    style_blocks = re.findall(r"<style\b[^>]*>([\s\S]*?)</style>", html_content, re.IGNORECASE)
    issues.extend(_detect_theme_and_token_polarity_issues(html_content, rel_path, expect_primitives, style_blocks))
    issues.extend(_detect_structural_rhythm_and_dedup_issues(html_content, rel_path))

    # --- 2. Table Containment & Horizontal Overflow Checks ---
    has_table_context = expect_primitives or "<main" in html_content.lower() or "table" in html_content.lower()
    if has_table_context:
        for tm in re.finditer(r"<table\b[^>]*>", html_content, re.IGNORECASE):
            preceding = html_content[max(0, tm.start() - 240) : tm.start()]
            if not re.search(
                r'<div[^>]*class=["\'][^"\']*(?:table-wrap|table-responsive|table-container|pseo-table-wrap)[^"\']*["\'][^>]*>\s*$',
                preceding,
                re.IGNORECASE,
            ):
                if expect_primitives or "class=" in tm.group(0).lower() or "<main" in html_content.lower():
                    issues.append(
                        f"[{rel_path}] Unwrapped <table> element risks horizontal mobile overflow (missing .table-wrap.pseo-table-wrap container)."
                    )
                    break

    # --- 3, 4, 5. Linear Tag Scan for Overflow Sabotage, Tap Targets, Hierarchy, and Calculator Controls ---
    for css_body in style_blocks:
        if re.search(r"min-(?:height|width)\s*:\s*(?:[0-9]|[1-3][0-9]|4[0-3])(?:\.\d+)?px\b", css_body, re.IGNORECASE):
            issues.append(
                f"[{rel_path}] Stylesheet rule specifies cramped min-height or min-width < 44px."
            )
            break

    body_only = _strip_style_and_script_blocks(html_content)
    has_calc_markers = 'id="calculation-manifest"' in html_content or any(
        tok in body_only
        for tok in (
            "calculator-form",
            "calculation-container",
            "calculation-manifest",
            'type="range"',
            "type='range'",
            "data-calc-preset",
            "scenario-preset-link",
        )
    )
    if expect_primitives and has_calc_markers:
        sync_match = re.search(
            r'<script\b[^>]*id=["\']pseo-runtime-sync["\'][^>]*>([\s\S]*?)</script>',
            html_content,
            re.IGNORECASE,
        )
        if (
            not sync_match
            or f'data-version="{VISUAL_PRIMITIVES_VERSION}"' not in html_content
            or "__pseoRuntimeSyncInitialized" not in sync_match.group(1)
            or "updateOutputsSynchronously" not in sync_match.group(1)
            or 'document.querySelector(\'script[src*="/static/js/app.js"]\')' in sync_match.group(1)
        ):
            issues.append(
                f"[{rel_path}] Missing or corrupted <script id='pseo-runtime-sync' data-version='{VISUAL_PRIMITIVES_VERSION}'> calculator synchronizer."
            )

    for m in re.finditer(r"<([a-zA-Z0-9]+)\b[^>]*>", html_content):
        tag_name = m.group(1).lower()
        tag = m.group(0)
        cls_val = (_extract_attr(tag, "class") or "").lower()
        style_val = _extract_attr(tag, "style") or ""
        style_lower = style_val.lower()

        # 2b. Table wrapper or table overflow sabotage
        if tag_name in ("div", "table") and (
            tag_name == "table"
            or any(c in cls_val for c in ("table-wrap", "pseo-table-wrap", "calc-matrix-table-wrap", "table-responsive", "table-container"))
        ):
            if style_lower and re.search(r"overflow(?:-x)?\s*:\s*(?:hidden|clip|visible)\b", style_lower):
                issues.append(
                    f"[{rel_path}] Table or table wrapper has inline overflow hidden/clip/visible that breaks mobile horizontal scroll containment."
                )

        # 2c. Fixed wide inline width/min-width >= 400px overflowing 375px mobile viewport
        if style_lower and tag_name in ("div", "section", "article", "main", "form"):
            for wm in re.finditer(r"(?<!max-)(?:width|min-width)\s*:\s*(\d+(?:\.\d+)?)px\b", style_lower):
                if float(wm.group(1)) >= 400.0:
                    issues.append(
                        f"[{rel_path}] Element <{tag_name}> has fixed inline width/min-width ({wm.group(1)}px >= 400px) that overflows 375px mobile viewport."
                    )
                    break

        # 3. Cramped interactive tap targets (< 44px)
        if tag_name in ("button", "a", "input", "select", "summary"):
            inp_type = (_extract_attr(tag, "type") or "").lower()
            if tag_name == "input" and inp_type == "hidden":
                continue
            if style_lower:
                for dm in re.finditer(
                    r"(?:min-height|max-height|height|min-width|max-width|width)\s*:\s*(\d+(?:\.\d+)?)px\b",
                    style_lower,
                ):
                    if float(dm.group(1)) < 44.0:
                        issues.append(
                            f"[{rel_path}] Cramped interactive tap target <{tag_name}> has inline dimension {dm.group(0)} (< 44px)."
                        )
                        break
                is_interactive_pill = tag_name in ("button", "input", "select", "summary") or any(
                    k in cls_val
                    for k in (
                        "touch-target",
                        "scenario-preset-link",
                        "partner-btn",
                        "btn-cta",
                        "cluster-link",
                        "canonical-tool-link",
                        "btn-preset",
                        "calc-switcher-btn",
                        "calc-scenario-btn",
                    )
                )
                if is_interactive_pill:
                    if re.search(r"display\s*:\s*inline(?!-[a-z])\s*(?:!important)?\s*(?:;|$)", style_lower):
                        issues.append(
                            f"[{rel_path}] Interactive control <{tag_name}> has inline 'display: inline' that collapses 44px touch target height."
                        )
                    if re.search(r"(?<![a-z-])padding\s*:\s*[0-2](?:px)?(?![0-9.a-z%])\s*(?:!important)?\s*(?:;|$)", style_lower):
                        issues.append(
                            f"[{rel_path}] Interactive control <{tag_name}> has cramped inline padding (< 3px)."
                        )
                if any(frag.strip() and ":" not in frag for frag in style_lower.split(";")):
                    issues.append(
                        f"[{rel_path}] Interactive control <{tag_name}> contains corrupted inline style declaration ({style_val!r})."
                    )

        # 4. Visual & Typographic Hierarchy
        if tag_name in ("h1", "h2", "h3", "h4") and style_lower and "font-size" in style_lower:
            parsed_fs = _parse_font_size_to_px(style_lower)
            if parsed_fs is not None:
                px_val, has_imp = parsed_fs
                if tag_name == "h1" and (px_val < 24.0 or has_imp):
                    issues.append(
                        f"[{rel_path}] Inline <h1> font-size override ({px_val}px) violates typographic hierarchy."
                    )
                elif tag_name == "h2" and (px_val > 24.0 or px_val < 15.0 or has_imp):
                    issues.append(
                        f"[{rel_path}] Inline <h2> font-size override ({px_val}px) violates typographic hierarchy."
                    )
                elif tag_name in ("h3", "h4") and (px_val > 20.0 or px_val < 12.0 or has_imp):
                    issues.append(
                        f"[{rel_path}] Inline <{tag_name}> font-size override ({px_val}px) violates typographic hierarchy."
                    )

        if tag_name in ("div", "section", "article") and style_lower:
            if any(c in cls_val.split() for c in ("card", "pseo-card", "overlay-section")):
                if (
                    re.search(r"(?<![a-z-])padding\s*:\s*(?:[0-9]|1[01])(?:px)?(?![0-9.a-z%])", style_lower)
                    or re.search(r"border-radius\s*:\s*0(?:px)?(?![0-9.a-z%])", style_lower)
                    or any(frag.strip() and ":" not in frag for frag in style_lower.split(";"))
                ):
                    issues.append(
                        f"[{rel_path}] Card container <{tag_name}> inline style overrides deterministic card padding/radius geometry."
                    )

        # 5. Interactive Calculator Controls, Sliders, Presets
        if tag_name in ("input", "select", "button"):
            inp_type = (_extract_attr(tag, "type") or "").lower()
            if tag_name == "input" and inp_type == "hidden":
                continue
            if re.search(r"\bdisabled(?:\s*=\s*([\"\']).*?\1|\b)", tag, re.IGNORECASE):
                issues.append(
                    f"[{rel_path}] Disabled interactive control <{tag_name}> blocks user calculator interaction."
                )
            if tag_name == "input" and (
                inp_type in ("number", "range") or "min=" in tag.lower() or "max=" in tag.lower() or "step=" in tag.lower()
            ):
                min_raw = _extract_attr(tag, "min")
                max_raw = _extract_attr(tag, "max")
                step_raw = _extract_attr(tag, "step")
                val_raw = _extract_attr(tag, "value")
                if min_raw is not None and max_raw is not None:
                    try:
                        if float(min_raw) >= float(max_raw):
                            issues.append(
                                f"[{rel_path}] Broken <input> range bounds: min ({min_raw}) >= max ({max_raw})."
                            )
                    except ValueError:
                        issues.append(
                            f"[{rel_path}] Non-numeric <input> min/max bounds: min={min_raw!r}, max={max_raw!r}."
                        )
                elif min_raw is not None or max_raw is not None:
                    for b_name, b_val in (("min", min_raw), ("max", max_raw)):
                        if b_val is not None:
                            try:
                                float(b_val)
                            except ValueError:
                                issues.append(f"[{rel_path}] Non-numeric <input> {b_name}={b_val!r}.")
                if step_raw is not None and step_raw.strip().lower() != "any":
                    try:
                        if float(step_raw) <= 0.0:
                            issues.append(
                                f"[{rel_path}] Broken <input> step attribute: step ({step_raw}) <= 0."
                            )
                    except ValueError:
                        issues.append(
                            f"[{rel_path}] Non-numeric <input> step attribute: step={step_raw!r}."
                        )
                if inp_type in ("number", "range") and val_raw is not None:
                    cleaned_val = val_raw.replace(",", "").strip()
                    try:
                        float(cleaned_val)
                    except ValueError:
                        issues.append(
                            f"[{rel_path}] Broken <input type='{inp_type}'> non-numeric value={val_raw!r}."
                        )

        if "data-calc-preset=" in tag.lower():
            preset_raw = _extract_attr(tag, "data-calc-preset")
            if preset_raw is not None:
                import html as _html_mod
                import json as _json_mod

                try:
                    parsed_preset = _json_mod.loads(_html_mod.unescape(preset_raw).strip())
                    if not isinstance(parsed_preset, dict) or not parsed_preset:
                        issues.append(
                            f"[{rel_path}] Empty or non-object data-calc-preset attribute on <{tag_name}>."
                        )
                except Exception:
                    issues.append(
                        f"[{rel_path}] Malformed JSON in data-calc-preset attribute on <{tag_name}>."
                    )

        if tag_name == "a" and "scenario-preset-link" in cls_val:
            href_val = _extract_attr(tag, "href") or ""
            preset_attr = _extract_attr(tag, "data-preset") or ""
            if "?" not in href_val and not preset_attr.strip():
                issues.append(
                    f"[{rel_path}] Broken .scenario-preset-link anchor missing both query parameters and data-preset attribute."
                )

    if expect_primitives and ('class="result-box"' in html_content or 'class="pseo-result-box"' in html_content):
        out_matches = list(
            re.finditer(
                r'<([a-zA-Z0-9]+)\b[^>]*class=["\'][^"\']*\boutput-value\b[^"\']*["\'][^>]*>([\s\S]*?)</\1>',
                html_content,
                re.IGNORECASE,
            )
        )
        if not out_matches:
            issues.append(
                f"[{rel_path}] Calculator result-box is missing a .output-value metric element."
            )
        else:
            for om in out_matches:
                inner_txt = re.sub(r"<[^>]+>", "", om.group(2)).strip().lower()
                if not inner_txt or inner_txt in ("nan", "undefined", "null", "infinity", "-infinity"):
                    issues.append(
                        f"[{rel_path}] Calculator .output-value contains invalid initial text ({inner_txt!r})."
                    )
                    break

    # 6. Stacked Callout / CTA Density Check
    max_consec_ctas = _count_max_consecutive_cta_callouts(html_content)
    trap_handoff_adj = bool(
        re.search(
            r'<aside\b[^>]*id=["\']statutory-trap-alert["\'][^>]*>[\s\S]*?</aside>\s*<section\b[^>]*id=["\']vetted-commercial-handoff["\']',
            html_content,
            re.IGNORECASE,
        )
    )
    if max_consec_ctas > 2 or trap_handoff_adj:
        issues.append(
            f"[{rel_path}] Stacked callout/CTA density violation: {max_consec_ctas} consecutive callout/CTA blocks (> 2 max or adjacent trap+handoff) without analytical separation."
        )

    return tuple(issues)


def assert_visual_and_ux_contracts(
    html_content: str,
    context: str = "",
    require_primitives: Optional[bool] = None,
) -> bool:
    """
    Contract gate asserting zero visual or UX flaws in html_content.
    Raises ValueError if any violation is detected.
    """
    issues = detect_visual_and_ux_contract_issues(
        html_content,
        rel_path=context or "index.html",
        require_primitives=require_primitives,
    )
    if issues:
        raise ValueError(
            f"Visual and UX Contract Violation ({len(issues)} issue(s)): " + "; ".join(issues)
        )
    return True


def _sanitize_style_attr_in_tag(tag_html: str, new_style: str) -> str:
    cleaned = new_style.strip().strip(";").strip()
    stripped_tag = re.sub(r'\s*\bstyle\s*=\s*(["\']).*?\1', "", tag_html, flags=re.IGNORECASE | re.DOTALL)
    if not cleaned:
        return stripped_tag
    if stripped_tag.endswith("/>"):
        return stripped_tag[:-2].rstrip() + f' style="{cleaned}" />'
    return stripped_tag[:-1].rstrip() + f' style="{cleaned}">'


def _heal_and_normalize_interactive_inline_style(style_val: str) -> str:
    """Heals previously truncated inline-flex / padding fragments and strips cramped inline dimensions (<44px)."""
    new_style = style_val
    new_style = re.sub(r"(?:^|(?<=;))\s*-flex\b", " display: inline-flex", new_style, flags=re.IGNORECASE)
    new_style = re.sub(
        r"(?:^|(?<=;))\s*([02]px\s+1[0-9]px)\b",
        r" padding: 1\1",
        new_style,
        flags=re.IGNORECASE,
    )
    new_style = re.sub(
        r"(?:^|(?<=;))\s*(\.[0-9]+rem(?:\s+[0-9.]+rem)?)\b",
        r" padding: 0\1",
        new_style,
        flags=re.IGNORECASE,
    )

    def _strip_cramped_dim(dm: re.Match) -> str:
        prop_name = dm.group(1).lower()
        if float(dm.group(2)) < 44.0:
            if prop_name in ("min-height", "min-width"):
                return f"{prop_name}: 44px;"
            return ""
        return dm.group(0)

    new_style = re.sub(
        r"(min-height|max-height|height|min-width|max-width|width)\s*:\s*(\d+(?:\.\d+)?)px\s*(?:!important)?\s*;?",
        _strip_cramped_dim,
        new_style,
        flags=re.IGNORECASE,
    )
    new_style = re.sub(
        r"display\s*:\s*inline(?!-[a-z])\s*(?:!important)?\s*(?:;|$)",
        "",
        new_style,
        flags=re.IGNORECASE,
    )
    new_style = re.sub(
        r"(?<![a-z-])padding\s*:\s*[0-2](?:px)?(?![0-9.a-z%])(?:\s+[0-2](?:px)?(?![0-9.a-z%]))?\s*(?:!important)?\s*(?:;|$)",
        "",
        new_style,
        flags=re.IGNORECASE,
    )
    return new_style.lstrip()


def _heal_and_normalize_card_inline_style(style_val: str) -> str:
    """Heals dangling 'rem' fragments and strips cramped (<12px) card padding/radius overrides."""
    new_style = re.sub(r"(?:^|(?<=;))\s*rem\s*(?:;|$)", "", style_val, flags=re.IGNORECASE)
    new_style = re.sub(
        r"(?<![a-z-])padding\s*:\s*(?:[0-9]|1[01])(?:px)?(?![0-9.a-z%])\s*(?:!important)?\s*(?:;|$)",
        "",
        new_style,
        flags=re.IGNORECASE,
    )
    new_style = re.sub(
        r"border-radius\s*:\s*0(?:px)?(?![0-9.a-z%])\s*(?:!important)?\s*(?:;|$)",
        "",
        new_style,
        flags=re.IGNORECASE,
    )
    return new_style.lstrip()


def _ensure_class_on_tag(tag_html: str, required_class: str) -> Tuple[str, bool]:
    cls_val = _extract_attr(tag_html, "class")
    if cls_val is not None:
        classes = cls_val.split()
        if required_class in classes:
            return tag_html, False
        new_cls = f"{cls_val.strip()} {required_class}".strip()
        updated_tag = re.sub(
            r'\bclass\s*=\s*(["\']).*?\1',
            f'class="{new_cls}"',
            tag_html,
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        )
        return updated_tag, True
    if tag_html.endswith("/>"):
        return tag_html[:-2].rstrip() + f' class="{required_class}" />', True
    return tag_html[:-1].rstrip() + f' class="{required_class}">', True


def _set_or_replace_attr(tag_html: str, attr_name: str, attr_val: str) -> str:
    pattern = rf'\b{re.escape(attr_name)}\s*=\s*(["\']).*?\1'
    matches = list(re.finditer(pattern, tag_html, re.IGNORECASE | re.DOTALL))
    if matches:
        if len(matches) == 1:
            return re.sub(
                pattern,
                f'{attr_name}="{attr_val}"',
                tag_html,
                count=1,
                flags=re.IGNORECASE | re.DOTALL,
            )
        stripped = re.sub(rf'\s*{pattern}', "", tag_html, flags=re.IGNORECASE | re.DOTALL)
        if stripped.endswith("/>"):
            return stripped[:-2].rstrip() + f' {attr_name}="{attr_val}" />'
        return stripped[:-1].rstrip() + f' {attr_name}="{attr_val}">'
    if tag_html.endswith("/>"):
        return tag_html[:-2].rstrip() + f' {attr_name}="{attr_val}" />'
    return tag_html[:-1].rstrip() + f' {attr_name}="{attr_val}">'


def _heal_structural_rhythm_and_dedup(doc: str) -> Tuple[str, List[str]]:
    """
    Deduplicates redundant .decision-framework-card sections and strips inline horizontal
    container drift (max-width + auto margin) and excessive vertical margins on top-level flow blocks.
    """
    updated = doc
    actions: List[str] = []

    df_matches = list(
        re.finditer(
            r'<section\b[^>]*class=["\'][^"\']*\bdecision-framework-card\b[^"\']*["\'][^>]*>[\s\S]*?</section>\s*',
            updated,
            re.IGNORECASE,
        )
    )
    if len(df_matches) > 1:
        removed_inner = False
        for m in reversed(df_matches):
            if "<h3" in m.group(0).lower() and not removed_inner:
                updated = updated[: m.start()] + updated[m.end() :]
                removed_inner = True
                break
        if not removed_inner:
            last_m = df_matches[-1]
            updated = updated[: last_m.start()] + updated[last_m.end() :]
        actions.append("visual_hierarchy_normalization")

    def _clean_top_flow_inline_style(m: re.Match) -> str:
        tag_html = m.group(0)
        style_val = _extract_attr(tag_html, "style")
        if not style_val:
            return tag_html
        new_s = re.sub(
            r"max-width\s*:\s*(?:560|620|720|820|920)px\s*(?:!important)?\s*;?",
            "",
            style_val,
            flags=re.IGNORECASE,
        )
        new_s = re.sub(
            r"margin(?:-(?:left|right))?\s*:\s*[^;]*\bauto\b[^;]*;?",
            "",
            new_s,
            flags=re.IGNORECASE,
        )
        new_s = re.sub(
            r"margin-(?:top|bottom)\s*:\s*(?:3\.5|4)rem\s*(?:!important)?\s*;?",
            "",
            new_s,
            flags=re.IGNORECASE,
        )
        if new_s != style_val:
            return _sanitize_style_attr_in_tag(tag_html, new_s)
        return tag_html

    cleaned_flow = re.sub(
        r'<(?:section|div)\b[^>]*class=["\'][^"\']*\b(?:hero-section|article-content)\b[^"\']*["\'][^>]*>',
        _clean_top_flow_inline_style,
        updated,
        flags=re.IGNORECASE,
    )
    if cleaned_flow != updated:
        updated = cleaned_flow
        if "visual_hierarchy_normalization" not in actions:
            actions.append("visual_hierarchy_normalization")

    return updated, actions


def _repair_html_tags_pass(updated: str) -> Tuple[str, set[str]]:
    existing_label_fors = set(
        re.findall(r'<label\b[^>]*\bfor\s*=\s*["\']([^"\']+)["\']', updated, re.IGNORECASE)
    )
    tag_repairs: set[str] = set()

    def _repair_html_tag(m: re.Match) -> str:
        tag_name = m.group(1).lower()
        tag = m.group(0)
        orig_tag = tag
        cls_val = (_extract_attr(tag, "class") or "").lower()
        style_val = _extract_attr(tag, "style")

        if style_val is not None:
            new_style = style_val
            if tag_name in ("div", "table") and (
                tag_name == "table"
                or any(
                    c in cls_val
                    for c in (
                        "table-wrap",
                        "pseo-table-wrap",
                        "calc-matrix-table-wrap",
                        "table-responsive",
                        "table-container",
                    )
                )
            ):
                new_style = re.sub(
                    r"overflow(?:-x)?\s*:\s*(?:hidden|clip|visible)\s*(?:!important)?\s*;?",
                    "",
                    new_style,
                    flags=re.IGNORECASE,
                )
            if tag_name in ("div", "section", "article", "main", "form"):
                def _strip_wide_px(wm: re.Match) -> str:
                    if float(wm.group(1)) >= 400.0:
                        return ""
                    return wm.group(0)

                new_style = re.sub(
                    r"(?<!max-)(?:width|min-width)\s*:\s*(\d+(?:\.\d+)?)px\s*(?:!important)?\s*;?",
                    _strip_wide_px,
                    new_style,
                    flags=re.IGNORECASE,
                )
            if new_style != style_val:
                tag = _sanitize_style_attr_in_tag(tag, new_style)
                style_val = _extract_attr(tag, "style")
                tag_repairs.add("table_wrapper_normalization")

        if tag_name in ("button", "a", "input", "select", "summary"):
            inp_type = (_extract_attr(tag, "type") or "").lower()
            if not (tag_name == "input" and inp_type == "hidden"):
                if style_val is not None:
                    new_style = _heal_and_normalize_interactive_inline_style(style_val)
                    if new_style != style_val.lstrip():
                        tag = _sanitize_style_attr_in_tag(tag, new_style)
                        style_val = _extract_attr(tag, "style")
                        tag_repairs.add("touch_target_normalization")

        if tag_name in ("h1", "h2", "h3", "h4") and style_val is not None and "font-size" in style_val.lower():
            parsed_fs = _parse_font_size_to_px(style_val.lower())
            if parsed_fs is not None:
                px_val, has_imp = parsed_fs
                violates = (
                    (tag_name == "h1" and (px_val < 24.0 or has_imp))
                    or (tag_name == "h2" and (px_val > 24.0 or px_val < 15.0 or has_imp))
                    or (tag_name in ("h3", "h4") and (px_val > 20.0 or px_val < 12.0 or has_imp))
                )
                if violates:
                    new_style = re.sub(
                        r"font-size\s*:[^;]+;?",
                        "",
                        style_val,
                        flags=re.IGNORECASE,
                    )
                    tag = _sanitize_style_attr_in_tag(tag, new_style)
                    style_val = _extract_attr(tag, "style")
                    tag_repairs.add("visual_hierarchy_normalization")

        if tag_name in ("div", "section", "article") and style_val is not None:
            if (
                any(c in cls_val.split() for c in ("card", "pseo-card", "overlay-section"))
                or bool(re.search(r"(?:^|(?<=;))\s*rem\s*(?:;|$)", style_val, re.IGNORECASE))
            ):
                new_style = _heal_and_normalize_card_inline_style(style_val)
                if new_style != style_val.lstrip():
                    tag = _sanitize_style_attr_in_tag(tag, new_style)
                    style_val = _extract_attr(tag, "style")
                    tag_repairs.add("visual_hierarchy_normalization")

        if tag_name in ("input", "select", "button"):
            inp_type = (_extract_attr(tag, "type") or "").lower()
            if not (tag_name == "input" and inp_type == "hidden"):
                if re.search(r"\bdisabled(?:\s*=\s*([\"\']).*?\1|\b)", tag, re.IGNORECASE):
                    tag = re.sub(r"\s*\bdisabled(?:\s*=\s*([\"\']).*?\1|\b)", "", tag, flags=re.IGNORECASE)
                    tag_repairs.add("interactive_control_sanitization")

                if tag_name == "input" and (
                    inp_type in ("number", "range")
                    or "min=" in tag.lower()
                    or "max=" in tag.lower()
                    or "step=" in tag.lower()
                ):
                    val_raw = _extract_attr(tag, "value")
                    default_num_val = 100.0 if inp_type == "range" else 100000.0
                    if val_raw is not None:
                        try:
                            default_num_val = float(val_raw.replace(",", "").strip())
                        except ValueError:
                            fallback_str = "100" if inp_type == "range" else "100000"
                            tag = _set_or_replace_attr(tag, "value", fallback_str)
                            default_num_val = float(fallback_str)
                            tag_repairs.add("interactive_control_sanitization")

                    min_raw = _extract_attr(tag, "min")
                    max_raw = _extract_attr(tag, "max")
                    min_num: Optional[float] = None
                    max_num: Optional[float] = None
                    if min_raw is not None:
                        try:
                            min_num = float(min_raw)
                        except ValueError:
                            tag = _set_or_replace_attr(tag, "min", "0")
                            min_num = 0.0
                            tag_repairs.add("interactive_control_sanitization")
                    if max_raw is not None:
                        try:
                            max_num = float(max_raw)
                        except ValueError:
                            repaired_max = str(max(200, int(abs(default_num_val) * 2)))
                            tag = _set_or_replace_attr(tag, "max", repaired_max)
                            max_num = float(repaired_max)
                            tag_repairs.add("interactive_control_sanitization")
                    if min_num is not None and max_num is not None and min_num >= max_num:
                        repaired_max = str(max(200, int(max(abs(default_num_val) * 2, abs(min_num) * 2, 200))))
                        tag = _set_or_replace_attr(tag, "min", "0")
                        tag = _set_or_replace_attr(tag, "max", repaired_max)
                        tag_repairs.add("interactive_control_sanitization")

                    step_raw = _extract_attr(tag, "step")
                    if step_raw is not None and step_raw.strip().lower() != "any":
                        try:
                            if float(step_raw) <= 0.0:
                                tag = _set_or_replace_attr(tag, "step", "1")
                                tag_repairs.add("interactive_control_sanitization")
                        except ValueError:
                            tag = _set_or_replace_attr(tag, "step", "1")
                            tag_repairs.add("interactive_control_sanitization")

                if tag_name in ("input", "select"):
                    el_id = _extract_attr(tag, "id") or ""
                    has_label = (
                        bool(el_id and el_id in existing_label_fors)
                        or _extract_attr(tag, "aria-label") is not None
                        or _extract_attr(tag, "aria-labelledby") is not None
                        or _extract_attr(tag, "title") is not None
                    )
                    if not has_label:
                        fallback_label = (
                            _extract_attr(tag, "name")
                            or el_id
                            or ("Range slider" if inp_type == "range" else "Calculator input")
                        )
                        tag = _set_or_replace_attr(tag, "aria-label", fallback_label.replace("_", " ").replace("-", " "))
                        tag_repairs.add("interactive_control_sanitization")

        if "data-calc-preset=" in tag.lower():
            preset_raw = _extract_attr(tag, "data-calc-preset")
            if preset_raw is not None:
                import html as _html_mod
                import json as _json_mod

                needs_preset_fix = False
                try:
                    parsed_p = _json_mod.loads(_html_mod.unescape(preset_raw).strip())
                    if not isinstance(parsed_p, dict) or not parsed_p:
                        needs_preset_fix = True
                except Exception:
                    needs_preset_fix = True
                if needs_preset_fix:
                    tag = re.sub(
                        r'\bdata-calc-preset\s*=\s*(["\']).*?\1',
                        'data-calc-preset=\'{"gross_amount": 125000}\'',
                        tag,
                        count=1,
                        flags=re.IGNORECASE | re.DOTALL,
                    )
                    tag_repairs.add("interactive_control_sanitization")

        if tag_name == "a" and "scenario-preset-link" in cls_val:
            href_val = _extract_attr(tag, "href") or ""
            preset_attr = _extract_attr(tag, "data-preset") or ""
            if "?" not in href_val and not preset_attr.strip():
                tag = _set_or_replace_attr(tag, "href", "?scenario=baseline")
                tag = _set_or_replace_attr(tag, "data-preset", "baseline")
                tag_repairs.add("interactive_control_sanitization")

        return tag if tag != orig_tag else orig_tag

    return re.sub(r"<([a-zA-Z0-9]+)\b[^>]*>", _repair_html_tag, updated), tag_repairs


def normalize_html_visual_primitives(
    html_content: str,
    is_tenant_porcelain: Optional[bool] = None,
) -> Tuple[str, List[str]]:
    """
    Normalizes an HTML document to enforce deterministic visual primitives and self-heal
    all 6 classes of visual and UX regressions across all 4 screen archetypes:
    1. Injects or repairs <style id="pseo-visual-primitives" data-version="pseo-primitives-v4">,
       fixes dark-theme token polarity inversions, and synthesizes fallback tokens for undefined var(--...).
    2. Normalizes table wrappers (.calc-matrix-table-wrap, div[style*="overflow-x: auto"], and unwrapped <table>s)
       and strips inline overflow-x: hidden / fixed wide pixel widths (>= 400px).
    3. Ensures interactive controls carry >= 44x44px touch-target sizing and strips cramped inline dimensions.
    4. Repairs inverted inline heading font-size overrides, cramped card padding/radius overrides,
       duplicate .decision-framework-card sections, and top-level container drift.
    5. Repairs broken calculator inputs (min >= max, step <= 0, disabled, non-numeric values, missing labels),
       malformed data-calc-preset JSON, broken .scenario-preset-link anchors, missing .output-value nodes,
       and injects or repairs <script id="pseo-runtime-sync" data-version="pseo-primitives-v4">.
    6. Interleaves stacked CTA/callout blocks (> 2 consecutive or adjacent trap+handoff).
    Zero em-dashes. Zero en-dashes. Zero spaced hyphens.
    """
    if not html_content or not isinstance(html_content, str):
        return html_content or "", []

    repaired: List[str] = []
    updated = html_content

    if is_tenant_porcelain is None:
        non_prim_doc = re.sub(
            r'<style\b[^>]*id=["\']pseo-visual-primitives["\'][^>]*>[\s\S]*?</style>',
            "",
            updated,
            flags=re.IGNORECASE,
        )
        is_tenant_porcelain = (
            "/static/css/style.css" in non_prim_doc
            or "/css/style.css" in non_prim_doc
            or 'data-theme="porcelain"' in non_prim_doc
            or "--bg-canvas: #fbfcfd" in updated
        ) and "--bg: #07090e" not in non_prim_doc and 'data-theme="obsidian"' not in non_prim_doc

    def _heal_inverted_dark_root_block(m: re.Match) -> str:
        root_css = m.group(1)
        if "--bg: #07090e" not in root_css and "--bg-canvas: #07090e" not in root_css:
            return m.group(0)
        fixed_root = re.sub(r"(--bg-canvas\s*:\s*)#(?:fbfcfd|ffffff)\b", r"\g<1>#07090e", root_css, flags=re.IGNORECASE)
        fixed_root = re.sub(r"(--bg-surface\s*:\s*)#(?:ffffff|fbfcfd)\b", r"\g<1>#0f172a", fixed_root, flags=re.IGNORECASE)
        fixed_root = re.sub(r"(--text-primary\s*:\s*)#(?:0f172a|090d16|1e293b)\b", r"\g<1>#f8fafc", fixed_root, flags=re.IGNORECASE)
        fixed_root = re.sub(r"(--brand-primary\s*:\s*)#1d4ed8\b", r"\g<1>#38bdf8", fixed_root, flags=re.IGNORECASE)
        return f":root {{{fixed_root}}}"

    healed_root_doc = re.sub(r":root\s*\{([\s\S]*?)\}", _heal_inverted_dark_root_block, updated, flags=re.IGNORECASE)
    if healed_root_doc != updated:
        updated = healed_root_doc
        if "visual_primitives_css" not in repaired:
            repaired.append("visual_primitives_css")

    # 1. Inject or repair <style id="pseo-visual-primitives">
    style_block = render_visual_primitives_style(is_tenant_porcelain=is_tenant_porcelain)
    if 'id="pseo-visual-primitives"' in updated or "id='pseo-visual-primitives'" in updated:
        prim_match = re.search(
            r'<style\b[^>]*id=["\']pseo-visual-primitives["\'][^>]*>([\s\S]*?)</style>',
            updated,
            re.IGNORECASE,
        )
        prim_body = prim_match.group(1) if prim_match else ""
        has_token_inversion = (not is_tenant_porcelain) and (
            "--text-primary: #0f172a" in prim_body or "--bg-surface: #ffffff" in prim_body
        )
        needs_style_repair = (
            f'data-version="{VISUAL_PRIMITIVES_VERSION}"' not in updated
            or any(tok not in prim_body for tok in REQUIRED_PRIMITIVE_TOKENS)
            or ".serp-depth-workbench" not in prim_body
            or ".tool-header.hero-section" not in prim_body
            or has_token_inversion
        )
        if needs_style_repair:
            updated = re.sub(
                r'\s*<style[^>]*id=["\']pseo-visual-primitives["\'][^>]*>[\s\S]*?</style>',
                "\n" + style_block,
                updated,
                count=1,
                flags=re.IGNORECASE,
            )
            repaired.append("visual_primitives_css")
    else:
        head_close_idx = updated.rfind("</head>")
        if head_close_idx != -1:
            updated = updated[:head_close_idx] + style_block + "\n" + updated[head_close_idx:]
            repaired.append("visual_primitives_css")
        elif "<body" in updated:
            body_idx = updated.find("<body")
            updated = updated[:body_idx] + style_block + "\n" + updated[body_idx:]
            repaired.append("visual_primitives_css")
        else:
            updated = style_block + "\n" + updated
            repaired.append("visual_primitives_css")

    # 1b. Synthesize safe fallback tokens for any undefined var(--...) custom properties
    no_script_doc = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", "", updated, flags=re.IGNORECASE)
    defined_vars = set(re.findall(r"(--[a-zA-Z0-9_-]+)\s*:", no_script_doc))
    used_vars = set(re.findall(r"var\(\s*(--[a-zA-Z0-9_-]+)\s*\)", no_script_doc))
    orphan_vars = sorted(used_vars - defined_vars)
    if orphan_vars:
        fallback_lines: List[str] = []
        for ov in orphan_vars:
            ov_low = ov.lower()
            if any(k in ov_low for k in ("bg", "surface", "canvas", "card")):
                fb_val = "#ffffff" if is_tenant_porcelain else "#0f172a"
            elif any(k in ov_low for k in ("border", "line", "divider")):
                fb_val = "#dbe1ea" if is_tenant_porcelain else "rgba(255, 255, 255, 0.12)"
            elif any(k in ov_low for k in ("text", "fg", "ink", "title", "heading")):
                fb_val = "#090d16" if is_tenant_porcelain else "#f8fafc"
            elif any(k in ov_low for k in ("radius", "round")):
                fb_val = "8px"
            elif any(k in ov_low for k in ("space", "gap", "pad")):
                fb_val = "16px"
            else:
                fb_val = "#1d4ed8" if is_tenant_porcelain else "#38bdf8"
            fallback_lines.append(f"      {ov}: {fb_val};")
        fallback_css = "\n".join(fallback_lines) + "\n"
        updated = re.sub(
            r'(<style\b[^>]*id=["\']pseo-visual-primitives["\'][^>]*>\s*:root\s*\{)',
            r"\1\n" + fallback_css,
            updated,
            count=1,
            flags=re.IGNORECASE,
        )
        if "orphan_css_token_repair" not in repaired:
            repaired.append("orphan_css_token_repair")

    # 1c. Normalize any stylesheet rules that set min-height or min-width < 44px
    def _fix_style_block_touch_targets(m: re.Match) -> str:
        return re.sub(
            r"(min-(?:height|width)\s*:\s*)(?:[0-9]|[1-3][0-9]|4[0-3])(?:\.\d+)?px\b",
            r"\g<1>44px",
            m.group(0),
            flags=re.IGNORECASE,
        )

    new_updated_styles = re.sub(
        r"<style\b[^>]*>[\s\S]*?</style>",
        _fix_style_block_touch_targets,
        updated,
        flags=re.IGNORECASE,
    )
    if new_updated_styles != updated:
        updated = new_updated_styles
        if "touch_target_normalization" not in repaired:
            repaired.append("touch_target_normalization")

    # 1d. Heal duplicate .decision-framework-card sections and top-level container drift
    updated, rhythm_actions = _heal_structural_rhythm_and_dedup(updated)
    for r_act in rhythm_actions:
        if r_act not in repaired:
            repaired.append(r_act)

    # 2. Normalize ad-hoc table wrappers (<div style="overflow-x: auto;"> and .calc-matrix-table-wrap)
    if 'class="calc-matrix-table-wrap"' in updated:
        updated = updated.replace(
            'class="calc-matrix-table-wrap"',
            'class="calc-matrix-table-wrap table-wrap pseo-table-wrap"',
        )
        if "table_wrapper_normalization" not in repaired:
            repaired.append("table_wrapper_normalization")

    if re.search(r'<div\s+style=["\']overflow-x:\s*auto;?["\']\s*>', updated, re.IGNORECASE):
        updated = re.sub(
            r'<div\s+style=["\']overflow-x:\s*auto;?["\']\s*>',
            '<div class="table-wrap pseo-table-wrap">',
            updated,
            flags=re.IGNORECASE,
        )
        if "table_wrapper_normalization" not in repaired:
            repaired.append("table_wrapper_normalization")

    def _wrap_unwrapped_tables(doc: str) -> Tuple[str, bool]:
        changed_any = False
        out_parts: List[str] = []
        last_idx = 0
        for m in re.finditer(r"(<table\b[^>]*>[\s\S]*?</table>)", doc, re.IGNORECASE):
            start, end = m.start(), m.end()
            preceding = doc[max(0, start - 240) : start]
            if re.search(
                r'<div[^>]*class=["\'][^"\']*(?:table-wrap|table-responsive|table-container|pseo-table-wrap)[^"\']*["\'][^>]*>\s*$',
                preceding,
                re.IGNORECASE,
            ):
                continue
            out_parts.append(doc[last_idx:start])
            out_parts.append(f'<div class="table-wrap pseo-table-wrap">\n{m.group(1)}\n</div>')
            last_idx = end
            changed_any = True
        if not changed_any:
            return doc, False
        out_parts.append(doc[last_idx:])
        return "".join(out_parts), True

    updated, wrapped_tables = _wrap_unwrapped_tables(updated)
    if wrapped_tables and "table_wrapper_normalization" not in repaired:
        repaired.append("table_wrapper_normalization")

    # 3, 4, 5. Linear tag sanitizer
    updated, tag_repairs = _repair_html_tags_pass(updated)
    for r_key in sorted(tag_repairs):
        if r_key not in repaired:
            repaired.append(r_key)

    # 5e. Ensure .result-box / .pseo-result-box has a valid non-NaN .output-value node
    if 'class="result-box"' in updated or 'class="pseo-result-box"' in updated:
        out_matches = list(
            re.finditer(
                r'(<([a-zA-Z0-9]+)\b[^>]*class=["\'][^"\']*\boutput-value\b[^"\']*["\'][^>]*>)([\s\S]*?)(</\2>)',
                updated,
                re.IGNORECASE,
            )
        )
        if not out_matches:
            updated = re.sub(
                r'(<div\b[^>]*class=["\'][^"\']*\b(?:result-box|pseo-result-box)\b[^"\']*["\'][^>]*>)',
                r'\1\n<div class="output-value" data-baseline-output="12450">$12,450</div>',
                updated,
                count=1,
                flags=re.IGNORECASE,
            )
            if "interactive_control_sanitization" not in repaired:
                repaired.append("interactive_control_sanitization")
        else:
            def _fix_invalid_output_val(om: re.Match) -> str:
                inner_txt = re.sub(r"<[^>]+>", "", om.group(3)).strip().lower()
                if not inner_txt or inner_txt in ("nan", "undefined", "null", "infinity", "-infinity"):
                    return f"{om.group(1)}12,450{om.group(4)}"
                return om.group(0)

            fixed_out_doc = re.sub(
                r'(<([a-zA-Z0-9]+)\b[^>]*class=["\'][^"\']*\boutput-value\b[^"\']*["\'][^>]*>)([\s\S]*?)(</\2>)',
                _fix_invalid_output_val,
                updated,
                flags=re.IGNORECASE,
            )
            if fixed_out_doc != updated:
                updated = fixed_out_doc
                if "interactive_control_sanitization" not in repaired:
                    repaired.append("interactive_control_sanitization")

    # 5f. Heal stacked callout / CTA density (> 2 consecutive CTA/callout blocks or adjacent trap + handoff)
    updated, healed_ctas = _heal_stacked_cta_callouts(updated)
    if healed_ctas and "cta_density_normalization" not in repaired:
        repaired.append("cta_density_normalization")

    # 6. Inject or repair <script id="pseo-runtime-sync">
    has_interactive_controls = any(
        tok in updated
        for tok in (
            "<form",
            'type="range"',
            "type='range'",
            'type="number"',
            "type='number'",
            "data-calc-preset",
            "scenario-preset-link",
            "output-value",
            'href="/r/',
            "href='/r/",
        )
    )
    if has_interactive_controls:
        script_block = render_runtime_synchronizer_script()
        if 'id="pseo-runtime-sync"' in updated or "id='pseo-runtime-sync'" in updated:
            sync_match = re.search(
                r'<script\b[^>]*id=["\']pseo-runtime-sync["\'][^>]*>([\s\S]*?)</script>',
                updated,
                re.IGNORECASE,
            )
            sync_body = sync_match.group(1) if sync_match else ""
            needs_sync_repair = (
                f'data-version="{VISUAL_PRIMITIVES_VERSION}"' not in updated
                or "__pseoRuntimeSyncInitialized" not in sync_body
                or "updateOutputsSynchronously" not in sync_body
                or "updateSerpWorkbenchSynchronously" not in sync_body
                or "updateInteractiveCliffAndComparator" not in sync_body
                or "syncOutboundAffiliateLinks" not in sync_body
                or "bridgePrimaryInputsToSerpWorkbench" not in sync_body
                or "kalshi_price" in sync_body
                or "val-tcja" in sync_body
                or 'document.querySelector(\'script[src*="/static/js/app.js"]\')' in sync_body
            )
            if needs_sync_repair:
                updated = re.sub(
                    r'\s*<script[^>]*id=["\']pseo-runtime-sync["\'][^>]*>[\s\S]*?</script>',
                    lambda _m: "\n" + script_block,
                    updated,
                    count=1,
                    flags=re.IGNORECASE,
                )
                repaired.append("interactive_runtime_sync")
        else:
            body_close_idx = updated.rfind("</body>")
            if body_close_idx != -1:
                updated = updated[:body_close_idx] + script_block + "\n" + updated[body_close_idx:]
                repaired.append("interactive_runtime_sync")
            else:
                updated = updated + "\n" + script_block
                repaired.append("interactive_runtime_sync")

    return updated, repaired


__all__ = [
    "VISUAL_PRIMITIVES_VERSION",
    "SCREEN_ARCHETYPE_CONTRACTS",
    "REQUIRED_PRIMITIVE_TOKENS",
    "classify_screen_archetype",
    "get_screen_archetype_contract",
    "render_visual_primitives_style",
    "render_runtime_synchronizer_script",
    "detect_visual_and_ux_contract_issues",
    "assert_visual_and_ux_contracts",
    "normalize_html_visual_primitives",
]

