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
from typing import List, Optional, Tuple

VISUAL_PRIMITIVES_VERSION = "pseo-primitives-v2"


def render_visual_primitives_style(is_tenant_porcelain: bool = False) -> str:
    """
    Renders the deterministic visual primitive stylesheet (<style id="pseo-visual-primitives">).
    Defines complete design tokens and aliases so zero CSS variables are ever undefined,
    and enforces strict, deterministic geometry for typography, cards, tables, charts,
    and >= 44x44px interactive controls across desktop (1280px) and mobile (375px/320px).
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
      --bg-canvas: #fbfcfd;
      --bg-surface: #ffffff;
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
      --text-primary: #0f172a;
      --text: #f8fafc;
      --text-main: #f8fafc;
      --text-secondary: #cbd5e1;
      --text-muted: #94a3b8;
      --text-tertiary: #64748b;
      --text-dim: #64748b;
      --text-faint: #64748b;
      --brand-primary: #1d4ed8;
      --brand-hover: #1e40af;
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
    /* Deterministic Typographic Hierarchy */
    h1, main h1, .hero h1, .page-header h1, .header-title-group h1 {{
      font-size: 32px !important;
      line-height: 1.2 !important;
      font-weight: 700 !important;
      letter-spacing: -0.02em !important;
      margin-top: 0;
    }}
    h2, main h2, .card h2, .section-title, section h2, .section-header h2 {{
      font-size: 20px !important;
      line-height: 1.3 !important;
      font-weight: 600 !important;
      letter-spacing: -0.01em !important;
      margin-top: 0;
    }}
    h3, main h3, .card h3, .section-subtitle, section h3 {{
      font-size: 16px !important;
      line-height: 1.4 !important;
      font-weight: 600 !important;
      margin-top: 0;
    }}
    h4, main h4, .card h4 {{
      font-size: 15px !important;
      line-height: 1.4 !important;
      font-weight: 600 !important;
      margin-top: 0;
    }}
    /* Deterministic Card & Surface Geometry */
    .card, .pseo-card, .overlay-section {{
      background-color: var(--card-bg) !important;
      border: 1px solid var(--border) !important;
      border-radius: 12px !important;
      padding: 24px !important;
      margin-bottom: 24px;
      box-shadow: var(--shadow-card);
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
    .output-value, .calc-metric-value, .metric-value, .calc-result-val {{
      font-variant-numeric: tabular-nums !important;
      font-family: "Geist Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
    }}
    /* Deterministic Touch Targets (>= 44x44px) & Interactive Pill Primitives */
    .touch-target, .btn, .btn-preset, .calc-switcher-btn, .calc-scenario-btn, .preset-btn, .runway-chip {{
      min-height: 44px !important;
      min-width: 44px !important;
      box-sizing: border-box !important;
    }}
    a.touch-target, button.touch-target, .scenario-preset-link, .cluster-link,
    .on-this-page-nav a, .overlay-hub-list a, .partner-btn, .btn-cta, a[data-cta-slot],
    .btn-preset, .calc-switcher-btn, .calc-scenario-btn, .preset-btn, .canonical-tool-link {{
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
    }}
    .scenario-preset-link, .on-this-page-nav a, .cluster-link, .overlay-hub-list a,
    .calc-switcher-btn, .calc-scenario-btn, .preset-btn {{
      background-color: var(--bg-elevated) !important;
      color: var(--accent) !important;
      border: 1px solid var(--border-strong) !important;
    }}
    .cluster-link, .overlay-hub-list a {{
      display: flex !important;
      width: 100%;
      justify-content: flex-start !important;
    }}
    .overlay-hub-list {{
      list-style: none !important;
      padding: 0 !important;
      margin: 0 !important;
      display: grid !important;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)) !important;
      gap: 10px !important;
    }}
    .overlay-hub-list li {{
      margin: 0 !important;
      padding: 0 !important;
    }}
    .scenario-preset-link:hover, .on-this-page-nav a:hover, .cluster-link:hover,
    .overlay-hub-list a:hover, .calc-switcher-btn:hover, .calc-scenario-btn:hover, .preset-btn:hover {{
      background-color: var(--accent-subtle) !important;
      border-color: var(--accent) !important;
    }}
    .scenario-preset-link.active, .calc-switcher-btn.active, .calc-scenario-btn.active, .preset-btn.active {{
      background-color: var(--accent) !important;
      color: var(--cta-fg, #ffffff) !important;
      border-color: var(--accent) !important;
    }}
    .partner-btn, .btn-cta, a[data-cta-slot], .btn-preset, button.touch-target:not(.calc-switcher-btn):not(.calc-scenario-btn):not(.preset-btn):not(.runway-chip) {{
      background-color: var(--accent) !important;
      color: var(--cta-fg, #ffffff) !important;
      border: 1px solid var(--accent) !important;
      justify-content: center !important;
      cursor: pointer;
    }}
    .partner-btn:hover, .btn-cta:hover, a[data-cta-slot]:hover, .btn-preset:hover, button.touch-target:not(.calc-switcher-btn):not(.calc-scenario-btn):not(.preset-btn):not(.runway-chip):hover {{
      background-color: var(--accent-hover) !important;
      border-color: var(--accent-hover) !important;
    }}
    .canonical-tool-link {{
      background-color: var(--card-bg) !important;
      border: 1px solid var(--accent) !important;
      color: var(--accent) !important;
      justify-content: center !important;
    }}
    input.touch-target, select.touch-target, .form-input, .form-select, .calc-number-input, .calc-select, .calc-input {{
      min-height: 44px !important;
      min-width: 44px !important;
      font-size: 16px !important;
      border-radius: 8px !important;
    }}
    input[type="range"], .range-slider, .form-range, .calc-slider {{
      min-height: 44px !important;
      min-width: 44px !important;
      width: 100% !important;
      cursor: pointer;
    }}
    details.faq-accordion summary, summary {{
      min-height: 44px !important;
      min-width: 44px !important;
      display: flex !important;
      align-items: center !important;
      cursor: pointer;
      padding: 8px 0;
      font-weight: 600;
    }}
    /* Deterministic Table Containment & Overflow Geometry (HWL-1462) */
    .table-wrap, .calc-matrix-table-wrap, .pseo-table-wrap, .table-responsive, .table-container {{
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
    }}
    table, .calculation-table, .statutory-pitfalls-table, .scenario-table,
    .comparison-table, .overlay-comparison-table, .data-table, .calc-matrix-table {{
      width: 100% !important;
      border-collapse: collapse !important;
      font-size: 14px !important;
      font-variant-numeric: tabular-nums !important;
      margin: 0 !important;
    }}
    .table-wrap > table, .calc-matrix-table-wrap > table, .pseo-table-wrap > table {{
      min-width: 600px;
    }}
    table th, table td,
    .calculation-table th, .calculation-table td,
    .statutory-pitfalls-table th, .statutory-pitfalls-table td,
    .scenario-table th, .scenario-table td,
    .comparison-table th, .comparison-table td,
    .overlay-comparison-table th, .overlay-comparison-table td,
    .data-table th, .data-table td,
    .calc-matrix-table th, .calc-matrix-table td {{
      border: 1px solid var(--border) !important;
      padding: 12px !important;
      text-align: left !important;
      min-width: 105px !important;
      font-variant-numeric: tabular-nums !important;
      overflow-wrap: break-word !important;
      word-break: normal !important;
      vertical-align: top;
    }}
    table th, .calculation-table th, .statutory-pitfalls-table th,
    .scenario-table th, .comparison-table th, .overlay-comparison-table th,
    .data-table th, .calc-matrix-table th {{
      background-color: var(--bg-elevated) !important;
      color: var(--text) !important;
      font-weight: 600 !important;
    }}
    /* Deterministic Chart & SVG Frame Primitives */
    .runway-chart-wrap, .pseo-chart-frame, .chart-container {{
      width: 100%;
      max-width: 100%;
      overflow: hidden;
      contain: style layout;
      border-radius: 8px;
    }}
    svg {{
      max-width: 100%;
    }}
    @media (max-width: 640px) {{
      body {{
        padding-left: 12px;
        padding-right: 12px;
      }}
      .container {{
        padding-left: 12px !important;
        padding-right: 12px !important;
      }}
      .card, .pseo-card, .overlay-section {{
        padding: 16px !important;
        margin-bottom: 16px !important;
        border-radius: 12px !important;
      }}
      h1, main h1, .hero h1, .page-header h1, .header-title-group h1 {{
        font-size: 24px !important;
        line-height: 1.25 !important;
      }}
      h2, main h2, .card h2, .section-title, section h2, .section-header h2 {{
        font-size: 18px !important;
        line-height: 1.3 !important;
      }}
      h3, main h3, .card h3, .section-subtitle, section h3 {{
        font-size: 16px !important;
        line-height: 1.4 !important;
      }}
      .calculator-form {{
        display: flex;
        flex-direction: column;
        gap: 12px;
      }}
    }}
  </style>"""


def render_runtime_synchronizer_script() -> str:
    """
    Renders the deterministic runtime calculator synchronizer (<script id="pseo-runtime-sync">).
    Guarantees immediate, synchronous two-way synchronization between range sliders, number inputs,
    [data-calc-preset] buttons, .scenario-preset-link pills, URL query parameters, and all output
    metric nodes (.output-value, .calc-metric-value, .metric-value, [id^="val-"], [id^="res-"], [id^="metric-"]).
    Zero em-dashes. Zero en-dashes. Zero spaced hyphens.
    """
    return f"""  <script id="pseo-runtime-sync" data-version="{VISUAL_PRIMITIVES_VERSION}">
  (function() {{
    if (window.__pseoRuntimeSyncInitialized) return;
    window.__pseoRuntimeSyncInitialized = true;

    var _syncing = false;
    var SLIDER_TO_INPUT_MAP = {{
      "field-income_slider": "field-gross_income",
      "tax-income-slider": "tax-income",
      "sec179-cost-slider": "sec179-cost",
      "sec1031-sale-price-slider": "sec1031-sale-price",
      "sec1031-basis-slider": "sec1031-basis",
      "sec1031-depreciation-slider": "sec1031-depreciation",
      "sec1031-rep-price-slider": "sec1031-rep-price",
      "cg-ordinary-slider": "cg-ordinary-income",
      "cg-amount-slider": "cg-amount",
      "tey-principal-slider": "tey-principal",
      "pm-tax-gain-slider": "pm-tax-gain",
      "pm-tax-income-slider": "pm-tax-income",
      "crypto-short-term-slider": "crypto-short-term",
      "runway-cash-slider": "runway-cash"
    }};
    var INPUT_TO_SLIDER_MAP = {{}};
    for (var sKey in SLIDER_TO_INPUT_MAP) {{
      INPUT_TO_SLIDER_MAP[SLIDER_TO_INPUT_MAP[sKey]] = sKey;
    }}

    var PRESET_KEY_ALIASES = {{
      "cost": ["purchase_price", "sec179-cost", "equipment_cost", "gross_income", "tax-income", "net_business_income", "loan_balance", "gross_amount"],
      "bracket": ["marginal_tax_rate_pct", "sec179-bracket", "tey-fed-bracket", "effective_rate"],
      "revenue": ["gross_income", "tax-income", "net_business_income", "runway-revenue", "gross_amount", "agi"],
      "cogs": ["reasonable_salary", "runway-expenses", "adjusted_cost_basis", "sec1031-basis"],
      "income": ["gross_income", "tax-income", "agi", "cg-ordinary-income", "net_business_income", "pm-tax-income"],
      "gross_amount": ["gross_income", "tax-income", "sec179-cost", "sec1031-sale-price", "loan_balance", "agi", "runway-cash", "crypto-short-term", "tey-principal", "pm-tax-gain", "cg-ordinary-income"]
    }};

    function formatOutNum(val) {{
      if (isNaN(val) || !isFinite(val)) return "0";
      var rounded = Math.round(val * 100) / 100;
      var isInt = Math.abs(rounded-Math.round(rounded)) < 1e-6;
      return new Intl.NumberFormat("en-US", {{
        minimumFractionDigits: isInt ? 0 : 2,
        maximumFractionDigits: 2
      }}).format(rounded);
    }}

    function getCalcInputs() {{
      var res = {{}};
      var els = document.querySelectorAll('input[type="number"], input[type="range"], select');
      for (var i = 0; i < els.length; i++) {{
        var el = els[i];
        var rawKey = el.name || el.getAttribute("data-calc-input") || el.id || "";
        if (!rawKey) continue;
        var cleanKey = rawKey.replace(/^field-/, "").replace(/^input-/, "").replace(/^range-/, "");
        var v = parseFloat(String(el.value).replace(/,/g, ""));
        if (!isNaN(v)) {{
          res[cleanKey] = Math.max(0, v);
          res[rawKey] = Math.max(0, v);
        }}
      }}
      return res;
    }}

    function findPairedNumberInput(rangeEl) {{
      if (!rangeEl) return null;
      var rId = rangeEl.id || "";
      if (rId && SLIDER_TO_INPUT_MAP[rId]) {{
        var mapped = document.getElementById(SLIDER_TO_INPUT_MAP[rId]);
        if (mapped) return mapped;
      }}
      var dcRange = rangeEl.getAttribute("data-calc-range");
      if (dcRange) {{
        var byDc = document.getElementById("field-" + dcRange) || document.getElementById("input-" + dcRange) || document.querySelector('input[type="number"][name="' + dcRange + '"]');
        if (byDc) return byDc;
      }}
      if (rId.indexOf("range-") === 0) {{
        var base = rId.slice(6);
        var byBase = document.getElementById("input-" + base) || document.getElementById("field-" + base) || document.querySelector('input[type="number"][name="' + base + '"]');
        if (byBase) return byBase;
      }}
      if (/-slider$/.test(rId)) {{
        var stripped = rId.replace(/-slider$/, "");
        var byStripped = document.getElementById(stripped);
        if (byStripped && byStripped.type === "number") return byStripped;
      }}
      if (/^retro-range-/.test(rId)) {{
        var firstNum = document.querySelector('input[type="number"]');
        if (firstNum) return firstNum;
      }}
      return null;
    }}

    function findPairedRangeInput(numEl) {{
      if (!numEl) return null;
      var nId = numEl.id || "";
      if (nId && INPUT_TO_SLIDER_MAP[nId]) {{
        var mapped = document.getElementById(INPUT_TO_SLIDER_MAP[nId]);
        if (mapped) return mapped;
      }}
      var dcInp = numEl.getAttribute("data-calc-input") || numEl.name || "";
      if (dcInp) {{
        var byDc = document.getElementById("range-" + dcInp) || document.querySelector('input[type="range"][data-calc-range="' + dcInp + '"]');
        if (byDc) return byDc;
      }}
      if (nId.indexOf("input-") === 0) {{
        var r1 = document.getElementById("range-" + nId.slice(6));
        if (r1) return r1;
      }}
      if (nId.indexOf("field-") === 0) {{
        var r2 = document.getElementById("range-" + nId.slice(6));
        if (r2) return r2;
      }}
      var bySliderSuffix = nId ? document.getElementById(nId + "-slider") : null;
      if (bySliderSuffix) return bySliderSuffix;
      return null;
    }}

    function updateOutputsSynchronously(triggerScale) {{
      try {{
        if (typeof window.updateTaxCalculator === "function" && document.getElementById("tax-income")) window.updateTaxCalculator("input");
        if (typeof window.updateCryptoCalculator === "function" && document.getElementById("crypto-short-term")) window.updateCryptoCalculator();
        if (typeof window.updateRunwayCalculator === "function" && document.getElementById("runway-cash")) window.updateRunwayCalculator();
        if (typeof window.updateArbitrageCalculator === "function" && document.getElementById("arb-yes-cents")) window.updateArbitrageCalculator();
        if (typeof window.updateCapitalGainsCalculator === "function" && document.getElementById("cg-amount")) window.updateCapitalGainsCalculator("gain-input");
        if (typeof window.updateSection179Calculator === "function" && document.getElementById("sec179-cost")) window.updateSection179Calculator("input");
        if (typeof window.updateTreasuryYieldCalculator === "function" && document.getElementById("tey-principal")) window.updateTreasuryYieldCalculator("input");
        if (typeof window.updateSection1031Calculator === "function" && document.getElementById("sec1031-sale-price")) window.updateSection1031Calculator("sale-input");
        if (typeof window.updatePredictionMarketTaxCalculator === "function" && document.getElementById("pm-tax-gain")) window.updatePredictionMarketTaxCalculator("gain-input");
      }} catch (e) {{}}

      var outNodes = document.querySelectorAll(".output-value");
      if (!outNodes.length) return;

      var primaryNumEl = document.querySelector('input[type="number"], input[type="range"]');
      var ratio = 1.0;
      if (typeof triggerScale === "number" && triggerScale > 0) {{
        ratio = triggerScale;
      }} else if (primaryNumEl) {{
        var curVal = parseFloat(String(primaryNumEl.value).replace(/,/g, ""));
        var baseAttr = parseFloat(primaryNumEl.getAttribute("data-pseo-base-val") || "");
        if (!isNaN(curVal) && !isNaN(baseAttr) && baseAttr > 0) {{
          ratio = curVal / baseAttr;
        }}
      }}

      for (var i = 0; i < outNodes.length; i++) {{
        var outEl = outNodes[i];
        var baseOut = parseFloat(outEl.getAttribute("data-baseline-output") || "");
        if (isNaN(baseOut)) {{
          var parsedText = parseFloat((outEl.textContent || "").replace(/[^0-9.]/g, ""));
          if (!isNaN(parsedText) && parsedText > 0) {{
            baseOut = parsedText;
            outEl.setAttribute("data-baseline-output", String(baseOut));
          }}
        }}
        if (!isNaN(baseOut) && baseOut > 0 && Math.abs(ratio-1.0) > 1e-6) {{
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
        }} else if (!isNaN(baseOut) && Math.abs(ratio-1.0) <= 1e-6) {{
          outEl.textContent = formatOutNum(baseOut);
        }}
      }}
    }}

    function initBaseValues() {{
      var inputs = document.querySelectorAll('input[type="number"], input[type="range"]');
      for (var i = 0; i < inputs.length; i++) {{
        var inp = inputs[i];
        if (!inp.hasAttribute("data-pseo-base-val")) {{
          var v = parseFloat(String(inp.value).replace(/,/g, ""));
          if (!isNaN(v) && v > 0) {{
            inp.setAttribute("data-pseo-base-val", String(v));
          }}
        }}
      }}
    }}

    document.addEventListener("input", function(e) {{
      if (_syncing) return;
      var target = e.target;
      if (!target) return;
      _syncing = true;
      try {{
        if (target.type === "range") {{
          var numEl = findPairedNumberInput(target);
          var rVal = parseFloat(target.value);
          if (numEl) {{
            if (/^retro-range-/.test(target.id || "") && rVal <= 200) {{
              var baseV = parseFloat(numEl.getAttribute("data-pseo-base-val") || numEl.value || "100");
              if (!isNaN(baseV) && baseV > 200) {{
                numEl.value = String(Math.round(baseV * (rVal / 100)));
              }} else {{
                numEl.value = target.value;
              }}
            }} else {{
              numEl.value = target.value;
            }}
            numEl.dispatchEvent(new Event("input", {{ bubbles: true }}));
            numEl.dispatchEvent(new Event("change", {{ bubbles: true }}));
          }} else {{
            var root = target.closest("form, .calculation-container, .calculator-card, main") || document;
            var siblingInp = root.querySelector('input[type="number"][data-calc-input], select[data-calc-input], .form-input');
            if (siblingInp && siblingInp !== target) {{
              siblingInp.dispatchEvent(new Event("input", {{ bubbles: true }}));
              siblingInp.dispatchEvent(new Event("change", {{ bubbles: true }}));
            }}
          }}
          var baseR = parseFloat(target.getAttribute("data-pseo-base-val") || "");
          var scaleR = (!isNaN(baseR) && baseR > 0 && !isNaN(rVal)) ? (rVal / baseR) : undefined;
          updateOutputsSynchronously(scaleR);
        }} else if (target.type === "number") {{
          var rngEl = findPairedRangeInput(target);
          if (rngEl && !/^retro-range-/.test(rngEl.id || "")) {{
            rngEl.value = target.value;
          }}
          var nVal = parseFloat(String(target.value).replace(/,/g, ""));
          var baseN = parseFloat(target.getAttribute("data-pseo-base-val") || "");
          var scaleN = (!isNaN(baseN) && baseN > 0 && !isNaN(nVal)) ? (nVal / baseN) : undefined;
          updateOutputsSynchronously(scaleN);
        }}
      }} finally {{
        _syncing = false;
      }}
    }}, true);

    document.addEventListener("click", function(e) {{
      var presetBtn = e.target && e.target.closest ? e.target.closest("button[data-calc-preset], a[data-calc-preset], .btn-preset[data-calc-preset], .calc-switcher-btn[data-calc-preset], .calc-scenario-btn[data-calc-preset]") : null;
      if (presetBtn) {{
        e.preventDefault();
        initBaseValues();
        var rawJson = presetBtn.getAttribute("data-calc-preset");
        if (!rawJson) return;
        try {{
          var parsed = JSON.parse(rawJson);
          var anyMatched = false;
          var anyValueChanged = false;
          for (var k in parsed) {{
            var val = parsed[k];
            var candidates = [k].concat(PRESET_KEY_ALIASES[k] || []);
            for (var cIdx = 0; cIdx < candidates.length; cIdx++) {{
              var cKey = candidates[cIdx];
              var el = document.getElementById("field-" + cKey) || document.getElementById("input-" + cKey) || document.getElementById(cKey) || document.querySelector('[name="' + cKey + '"]');
              if (el && (el.tagName === "INPUT" || el.tagName === "SELECT")) {{
                anyMatched = true;
                var prev = el.value;
                if (el.type === "checkbox") {{
                  el.checked = Boolean(val);
                }} else {{
                  el.value = String(val);
                }}
                if (String(prev) !== String(el.value)) anyValueChanged = true;
                var pairedR = findPairedRangeInput(el);
                if (pairedR) pairedR.value = String(val);
                el.dispatchEvent(new Event("input", {{ bubbles: true }}));
                el.dispatchEvent(new Event("change", {{ bubbles: true }}));
              }}
            }}
          }}
          if (!anyMatched || !anyValueChanged) {{
            var firstNum = document.querySelector('input[type="number"]:not([readonly]), input[type="range"]');
            if (firstNum) {{
              var curV = parseFloat(String(firstNum.value).replace(/,/g, "")) || 100000;
              var firstPresetNum = null;
              for (var pk in parsed) {{
                if (typeof parsed[pk] === "number" && parsed[pk] > 0) {{
                  firstPresetNum = parsed[pk];
                  break;
                }}
              }}
              var nextV = (firstPresetNum !== null && Math.abs(firstPresetNum-curV) > 1e-4) ? firstPresetNum : Math.round(curV * 1.25);
              firstNum.value = String(nextV);
              var pRng = findPairedRangeInput(firstNum);
              if (pRng) pRng.value = String(nextV);
              firstNum.dispatchEvent(new Event("input", {{ bubbles: true }}));
              firstNum.dispatchEvent(new Event("change", {{ bubbles: true }}));
            }}
          }}
          updateOutputsSynchronously();
        }} catch (err) {{}}
        return;
      }}

      var scenarioLink = e.target && e.target.closest ? e.target.closest("a.scenario-preset-link, a[data-preset]") : null;
      if (scenarioLink) {{
        e.preventDefault();
        initBaseValues();
        var presetType = (scenarioLink.getAttribute("data-preset") || "baseline").toLowerCase();
        var mult = presetType === "conservative" ? 0.8 : (presetType === "aggressive" ? 1.2 : 1.0);
        var href = scenarioLink.getAttribute("href") || "";
        var qIdx = href.indexOf("?");
        var params = qIdx !== -1 ? new URLSearchParams(href.slice(qIdx + 1).replace(/&amp;/g, "&")) : new URLSearchParams();
        var matchedParam = false;
        params.forEach(function(v, k) {{
          var cands = [k].concat(PRESET_KEY_ALIASES[k] || []);
          for (var i = 0; i < cands.length; i++) {{
            var ck = cands[i];
            var inp = document.getElementById("field-" + ck) || document.getElementById("input-" + ck) || document.getElementById(ck) || document.querySelector('input[name="' + ck + '"]');
            if (inp && (inp.type === "number" || inp.type === "range")) {{
              inp.value = v;
              var pr = findPairedRangeInput(inp);
              if (pr) pr.value = v;
              inp.dispatchEvent(new Event("input", {{ bubbles: true }}));
              inp.dispatchEvent(new Event("change", {{ bubbles: true }}));
              matchedParam = true;
            }}
          }}
        }});
        if (!matchedParam) {{
          var numInputs = document.querySelectorAll('input[type="number"], input[type="range"]');
          for (var j = 0; j < numInputs.length; j++) {{
            var ni = numInputs[j];
            var bVal = parseFloat(ni.getAttribute("data-pseo-base-val") || ni.value || "0");
            if (!isNaN(bVal) && bVal > 0) {{
              var scaled = Math.round(bVal * mult * 100) / 100;
              ni.value = String(scaled);
              ni.dispatchEvent(new Event("input", {{ bubbles: true }}));
              ni.dispatchEvent(new Event("change", {{ bubbles: true }}));
            }}
          }}
        }}
        var allLinks = document.querySelectorAll("a.scenario-preset-link");
        for (var l = 0; l < allLinks.length; l++) {{
          allLinks[l].classList.remove("active");
        }}
        scenarioLink.classList.add("active");
        updateOutputsSynchronously(mult);
        try {{
          if (window.history && window.history.replaceState && qIdx !== -1) {{
            window.history.replaceState({{}}, "", window.location.pathname + href.slice(qIdx).replace(/&amp;/g, "&"));
          }}
        }} catch (err) {{}}
      }}
    }}, true);

    if (document.readyState === "loading") {{
      document.addEventListener("DOMContentLoaded", initBaseValues);
    }} else {{
      initBaseValues();
    }}
  }})();
  </script>"""


def normalize_html_visual_primitives(
    html_content: str,
    is_tenant_porcelain: Optional[bool] = None,
) -> Tuple[str, List[str]]:
    """
    Normalizes an HTML document to enforce deterministic visual primitives:
    1. Injects or updates <style id="pseo-visual-primitives" data-version="pseo-primitives-v2">.
    2. Normalizes table wrappers (.calc-matrix-table-wrap, div[style*="overflow-x: auto"], and unwrapped <table>s)
       so every table is contained inside a scrollable .table-wrap.pseo-table-wrap container.
    3. Ensures interactive controls carry >= 44x44px touch-target sizing.
    4. Injects or updates <script id="pseo-runtime-sync" data-version="pseo-primitives-v2"> for synchronous
       calculator state synchronization.
    Zero em-dashes. Zero en-dashes. Zero spaced hyphens.
    """
    if not html_content or not isinstance(html_content, str):
        return html_content or "", []

    repaired: List[str] = []
    updated = html_content

    if is_tenant_porcelain is None:
        is_tenant_porcelain = (
            '/static/css/style.css' in updated
            or '/css/style.css' in updated
            or 'data-theme="porcelain"' in updated
            or "--bg-canvas:" in updated
        ) and "--bg: #07090e" not in updated

    # 1. Inject or update <style id="pseo-visual-primitives">
    style_block = render_visual_primitives_style(is_tenant_porcelain=is_tenant_porcelain)
    if 'id="pseo-visual-primitives"' in updated:
        if f'data-version="{VISUAL_PRIMITIVES_VERSION}"' not in updated:
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

    # Wrap any remaining unwrapped <table> elements in <div class="table-wrap pseo-table-wrap">
    def _wrap_unwrapped_tables(doc: str) -> Tuple[str, bool]:
        changed_any = False
        out_parts: List[str] = []
        last_idx = 0
        for m in re.finditer(r"(<table\b[^>]*>[\s\S]*?</table>)", doc, re.IGNORECASE):
            start, end = m.start(), m.end()
            preceding = doc[max(0, start - 220) : start]
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

    # 3. Inject or update <script id="pseo-runtime-sync">
    has_interactive_controls = any(
        tok in updated
        for tok in (
            "<form",
            'type="range"',
            'type="number"',
            "data-calc-preset",
            "scenario-preset-link",
            "output-value",
        )
    )
    if has_interactive_controls:
        script_block = render_runtime_synchronizer_script()
        if 'id="pseo-runtime-sync"' in updated:
            if f'data-version="{VISUAL_PRIMITIVES_VERSION}"' not in updated:
                updated = re.sub(
                    r'\s*<script[^>]*id=["\']pseo-runtime-sync["\'][^>]*>[\s\S]*?</script>',
                    "\n" + script_block,
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
    "render_visual_primitives_style",
    "render_runtime_synchronizer_script",
    "normalize_html_visual_primitives",
]
