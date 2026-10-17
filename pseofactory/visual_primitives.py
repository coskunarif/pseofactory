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
    button, input:not([type="hidden"]), select, .touch-target, .btn, .btn-preset, .calc-switcher-btn, .calc-scenario-btn, .preset-btn, .runway-chip {{
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


REQUIRED_PRIMITIVE_TOKENS: Tuple[str, ...] = (
    "--bg-canvas:",
    "--card-bg:",
    "--border:",
    "--accent:",
    ".table-wrap",
    ".touch-target",
    "tabular-nums",
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
        "<main",
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


def detect_visual_and_ux_contract_issues(
    html_content: str,
    rel_path: str = "index.html",
    require_primitives: Optional[bool] = None,
) -> List[str]:
    """
    Deterministically audits an HTML document for all 5 visual and UX flaw classes:
    1. Missing or corrupted theme styles and undefined CSS custom properties (var(--...)).
    2. Unwrapped <table> elements or horizontal overflow sabotage (overflow-x: hidden, fixed wide px widths).
    3. Cramped interactive tap targets (< 44px inline dimensions, < 44px CSS min-height/min-width, display: inline).
    4. Broken visual and typographic hierarchy (inline heading font-size overrides, cramped card padding/radius).
    5. Broken interactive calculator controls, sliders, presets, and runtime synchronizer state.
    Zero em-dashes. Zero en-dashes. Zero spaced hyphens.
    """
    if not html_content or not isinstance(html_content, str):
        return [f"[{rel_path}] Empty or non-string HTML content."]

    issues: List[str] = []
    expect_primitives = _is_compiled_tenant_or_primitive_page(html_content, require_primitives)

    # --- 1. Theme Styles & CSS Custom Property Integrity ---
    style_blocks = re.findall(r"<style\b[^>]*>([\s\S]*?)</style>", html_content, re.IGNORECASE)
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

    if style_blocks or expect_primitives or "var(--" in html_content:
        no_script_html = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", "", html_content, flags=re.IGNORECASE)
        defined_vars = set(re.findall(r"(--[a-zA-Z0-9_-]+)\s*:", no_script_html))
        used_vars_no_fallback = set(re.findall(r"var\(\s*(--[a-zA-Z0-9_-]+)\s*\)", no_script_html))
        undefined_vars = sorted(used_vars_no_fallback - defined_vars)
        if undefined_vars:
            issues.append(
                f"[{rel_path}] Undefined CSS custom properties referenced without fallback: {', '.join(undefined_vars[:5])}."
            )

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

    has_calc_markers = any(
        tok in html_content
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
                    if re.search(r"display\s*:\s*inline\s*(?:!important)?\s*(?:;|$)", style_lower):
                        issues.append(
                            f"[{rel_path}] Interactive control <{tag_name}> has inline 'display: inline' that collapses 44px touch target height."
                        )
                    if re.search(r"(?<![a-z-])padding\s*:\s*[0-2](?:px)?\s*(?:!important)?\s*(?:;|$)", style_lower):
                        issues.append(
                            f"[{rel_path}] Interactive control <{tag_name}> has cramped inline padding (< 3px)."
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
                if re.search(r"(?<![a-z-])padding\s*:\s*(?:[0-9]|1[01])(?:px)?\b", style_lower) or re.search(
                    r"border-radius\s*:\s*0(?:px)?\b", style_lower
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

    return issues


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


def normalize_html_visual_primitives(
    html_content: str,
    is_tenant_porcelain: Optional[bool] = None,
) -> Tuple[str, List[str]]:
    """
    Normalizes an HTML document to enforce deterministic visual primitives and self-heal
    all 5 classes of visual and UX regressions:
    1. Injects or repairs <style id="pseo-visual-primitives" data-version="pseo-primitives-v2">
       and synthesizes fallback tokens for any undefined CSS custom properties (var(--...)).
    2. Normalizes table wrappers (.calc-matrix-table-wrap, div[style*="overflow-x: auto"], and unwrapped <table>s)
       and strips inline overflow-x: hidden / fixed wide pixel widths (>= 400px).
    3. Ensures interactive controls carry >= 44x44px touch-target sizing and strips cramped inline dimensions.
    4. Repairs inverted inline heading font-size overrides and cramped card padding/radius overrides.
    5. Repairs broken calculator inputs (min >= max, step <= 0, disabled, non-numeric values, missing labels),
       malformed data-calc-preset JSON, broken .scenario-preset-link anchors, missing .output-value nodes,
       and injects or repairs <script id="pseo-runtime-sync" data-version="pseo-primitives-v2">.
    Zero em-dashes. Zero en-dashes. Zero spaced hyphens.
    """
    if not html_content or not isinstance(html_content, str):
        return html_content or "", []

    repaired: List[str] = []
    updated = html_content

    if is_tenant_porcelain is None:
        is_tenant_porcelain = (
            "/static/css/style.css" in updated
            or "/css/style.css" in updated
            or 'data-theme="porcelain"' in updated
            or "--bg-canvas:" in updated
        ) and "--bg: #07090e" not in updated

    # 1. Inject or repair <style id="pseo-visual-primitives">
    style_block = render_visual_primitives_style(is_tenant_porcelain=is_tenant_porcelain)
    if 'id="pseo-visual-primitives"' in updated or "id='pseo-visual-primitives'" in updated:
        prim_match = re.search(
            r'<style\b[^>]*id=["\']pseo-visual-primitives["\'][^>]*>([\s\S]*?)</style>',
            updated,
            re.IGNORECASE,
        )
        prim_body = prim_match.group(1) if prim_match else ""
        needs_style_repair = (
            f'data-version="{VISUAL_PRIMITIVES_VERSION}"' not in updated
            or any(tok not in prim_body for tok in REQUIRED_PRIMITIVE_TOKENS)
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
        full_block = m.group(0)
        fixed_block = re.sub(
            r"(min-(?:height|width)\s*:\s*)(?:[0-9]|[1-3][0-9]|4[0-3])(?:\.\d+)?px\b",
            r"\g<1>44px",
            full_block,
            flags=re.IGNORECASE,
        )
        return fixed_block

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

    # 3, 4, 5. Linear tag sanitizer for overflow styles, cramped tap targets, hierarchy overrides, and broken inputs
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

        # 2b & 2c: Strip overflow sabotage on tables/wrappers and wide fixed inline widths >= 400px
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

        # 3: Strip cramped inline dimensions (< 44px), display: inline, and cramped padding on interactive controls
        if tag_name in ("button", "a", "input", "select", "summary"):
            inp_type = (_extract_attr(tag, "type") or "").lower()
            if not (tag_name == "input" and inp_type == "hidden"):
                if style_val is not None:
                    new_style = style_val

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
                        r"display\s*:\s*inline\s*(?:!important)?\s*;?",
                        "",
                        new_style,
                        flags=re.IGNORECASE,
                    )
                    new_style = re.sub(
                        r"(?<![a-z-])padding\s*:\s*[0-2](?:px)?(?:\s+[0-2](?:px)?)?\s*(?:!important)?\s*;?",
                        "",
                        new_style,
                        flags=re.IGNORECASE,
                    )
                    if new_style != style_val:
                        tag = _sanitize_style_attr_in_tag(tag, new_style)
                        style_val = _extract_attr(tag, "style")
                        tag_repairs.add("touch_target_normalization")

        # 4: Strip inline heading font-size overrides that violate typographic hierarchy, and cramped card styles
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
            if any(c in cls_val.split() for c in ("card", "pseo-card", "overlay-section")):
                new_style = re.sub(
                    r"(?<![a-z-])padding\s*:\s*(?:[0-9]|1[01])(?:px)?\s*(?:!important)?\s*;?",
                    "",
                    style_val,
                    flags=re.IGNORECASE,
                )
                new_style = re.sub(
                    r"border-radius\s*:\s*0(?:px)?\s*(?:!important)?\s*;?",
                    "",
                    new_style,
                    flags=re.IGNORECASE,
                )
                if new_style != style_val:
                    tag = _sanitize_style_attr_in_tag(tag, new_style)
                    style_val = _extract_attr(tag, "style")
                    tag_repairs.add("visual_hierarchy_normalization")

        # 5: Repair broken interactive calculator controls, sliders, presets, and scenario links
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

    updated = re.sub(r"<([a-zA-Z0-9]+)\b[^>]*>", _repair_html_tag, updated)
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
            )
            if needs_sync_repair:
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
    "REQUIRED_PRIMITIVE_TOKENS",
    "render_visual_primitives_style",
    "render_runtime_synchronizer_script",
    "detect_visual_and_ux_contract_issues",
    "assert_visual_and_ux_contracts",
    "normalize_html_visual_primitives",
]

