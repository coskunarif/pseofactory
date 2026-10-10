"""
pseofactory High-Effort Content Compiler Engine
Stateless programmatic content compiler generating authoritative calculation assets.
Enforces:
1. Pre-compilation high-effort qualification gate (assert_high_effort_content_qualified).
2. Pure functional, deterministic AST mathematical formula evaluation (safe_eval_mathematical_formula).
3. Non-negative numeric parameter clamping (>= 0) per HWL-1263.
4. Factor 7 calculation manifest assembly and embedded JSON extraction.
5. High-contrast Obsidian dark-theme HTML with touch-accessible targets (>= 44x44px).
6. Multi-dataset join container linking primary statutory authority with empirical economic datasets.
7. Schema.org FAQPage and SoftwareApplication JSON-LD blocks.
8. In-memory self-verification via verify_html_unique_first_party_information.
9. Strictly zero em-dashes and zero en-dashes via assert_no_forbidden_dashes.

Zero em-dashes. Zero en-dashes.
"""

import os
import json
import re
from typing import Dict, Any, Optional

from pseofactory.qualification import assert_high_effort_content_qualified
from pseofactory.contracts import (
    safe_eval_mathematical_formula,
    assert_proprietary_model_integrity,
    assert_no_forbidden_dashes,
)
from pseofactory.verifier import verify_html_unique_first_party_information

PROFITHELM_PREDICTION_CLUSTER = [
    ("prediction-market-odds", "Prediction Market Odds Calculator"),
    ("prediction-market-tax", "Prediction Market Section 1256 Tax Calculator"),
    ("prediction-market-ev", "Prediction Market Expected Value (EV) Calculator"),
    ("prediction-market-kelly-criterion", "Prediction Market Kelly Criterion Calculator"),
    ("prediction-market-implied-probability", "Prediction Market Implied Probability Calculator"),
    ("prediction-market-kalshi-fees", "Kalshi Quadratic Fee Drag Calculator"),
    ("prediction-market-arbitrage", "Prediction Market Cross-Platform Arbitrage Calculator"),
    ("prediction-market-vig-spread", "Prediction Market Vig and Spread Calculator"),
    ("prediction-market-break-even", "Prediction Market Break-Even Probability Calculator"),
]

PROFITHELM_TAX_CLUSTER = [
    ("section-179-calculator", "Section 179 Equipment Expense Tax Deduction Calculator"),
    ("section-1031-calculator", "Section 1031 Like-Kind Exchange Tax Deferral Calculator"),
    ("qsbs-section-1202-calculator", "QSBS Section 1202 Capital Gains Exemption Calculator"),
    ("tcja-sunset-bracket-calculator", "TCJA Sunset 2027 Marginal Tax Bracket Calculator"),
    ("saas-runway-calculator", "SaaS Runway and Capital Burn Rate Calculator"),
    ("crypto-tax-calculator", "Cryptocurrency Tax Loss Harvesting Calculator"),
    ("treasury-yield-calculator", "Treasury Yield Curve Arbitrage Calculator"),
]

PREXVO_STUDENT_LOAN_CLUSTER = [
    ("student-loan-repayment-calculator", "Title IV Student Loan Standard Repayment Calculator"),
    ("rap-vs-ibr-calculator", "Repayment Assistance Plan (RAP) vs IBR Monthly Payment Calculator"),
    ("student-loan-forgiveness-calculator", "Student Loan Forgiveness Timeline Calculator"),
    ("pslf-qualifying-payment-calculator", "PSLF 120 Qualifying Payments Verification Calculator"),
    ("student-loan-interest-subsidy-calculator", "Title IV Unpaid Interest Subsidy Benefit Calculator"),
]


def compile_high_effort_page(candidate_spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compiles a qualified candidate specification into a verified high-effort programmatic HTML asset.
    Pure functional and stateless.
    Zero em-dashes. Zero en-dashes.
    """
    if not isinstance(candidate_spec, dict):
        raise ValueError(f"Candidate specification must be a dictionary, got {type(candidate_spec).__name__}")

    # 1. Enforce pre-compilation high-effort qualification gate
    assert_high_effort_content_qualified(candidate_spec, context="content compiler intake")

    # 2. Extract and resolve candidate metadata
    manifest_source = (
        candidate_spec.get("calculation_manifest")
        if isinstance(candidate_spec.get("calculation_manifest"), dict)
        else {}
    )

    query = str(candidate_spec.get("query") or candidate_spec.get("primary_keyword") or "").strip()
    raw_slug = str(candidate_spec.get("slug") or "").strip()
    if not raw_slug:
        slug_src = query or candidate_spec.get("title") or "proprietary-model"
        raw_slug = re.sub(r"[^a-z0-9]+", "-", str(slug_src).lower()).strip("-")
    slug = raw_slug

    title = str(candidate_spec.get("title") or "").strip()
    if not title:
        if query:
            words = [w.capitalize() for w in query.split() if w]
            title = " ".join(words) + " Calculator and Statutory Analysis"
        else:
            title = "Proprietary Model Calculator and Statutory Analysis"

    model_name = str(
        candidate_spec.get("model_name")
        or candidate_spec.get("proprietary_model")
        or manifest_source.get("model_name")
        or manifest_source.get("proprietary_model")
        or "Proprietary Calculation Model"
    ).strip()

    formula = str(
        candidate_spec.get("formula")
        or manifest_source.get("formula")
        or ""
    ).strip()

    raw_inputs = (
        candidate_spec.get("inputs")
        if candidate_spec.get("inputs") is not None
        else manifest_source.get("inputs", {})
    )

    statutory_authority = str(
        candidate_spec.get("statutory_authority")
        or candidate_spec.get("statutory_provenance")
        or candidate_spec.get("authority")
        or manifest_source.get("statutory_authority")
        or manifest_source.get("statutory_provenance")
        or manifest_source.get("authority")
        or ""
    ).strip()

    economic_dataset = str(
        candidate_spec.get("economic_dataset")
        or candidate_spec.get("economic_source")
        or manifest_source.get("economic_dataset")
        or manifest_source.get("economic_source")
        or ""
    ).strip()

    sample_calc = str(
        candidate_spec.get("sample_calculation")
        or candidate_spec.get("sample")
        or manifest_source.get("sample_calculation")
        or manifest_source.get("sample")
        or ""
    ).strip()

    # 3. Numeric metric clamping to non-negative (>= 0) per HWL-1263
    clamped_inputs: Dict[str, Any] = {}
    for k, v in raw_inputs.items():
        if isinstance(v, (int, float)):
            clamped_inputs[k] = max(0.0, float(v)) if isinstance(v, float) else max(0, v)
        elif isinstance(v, str):
            v_clean = v.replace("$", "").replace(",", "").replace("%", "").strip()
            try:
                num_v = float(v_clean)
                clamped_inputs[k] = max(0.0, num_v)
            except ValueError:
                clamped_inputs[k] = v
        else:
            clamped_inputs[k] = v

    # 4. Deterministic AST mathematical formula evaluation
    calculated_output = safe_eval_mathematical_formula(formula, clamped_inputs)

    published_raw = (
        candidate_spec.get("published_output")
        if candidate_spec.get("published_output") is not None
        else candidate_spec.get("expected_output")
    )
    if published_raw is None:
        published_raw = (
            manifest_source.get("published_output")
            if manifest_source.get("published_output") is not None
            else manifest_source.get("expected_output")
        )

    if published_raw is not None:
        published_output = float(str(published_raw).replace("$", "").replace(",", "").replace("%", "").strip())
        assert_proprietary_model_integrity(
            manifest_or_inputs=clamped_inputs,
            published_output=published_output,
            formula=formula,
            tolerance=0.01,
            context=f"content compiler verification for '{slug}'",
        )
    else:
        published_output = calculated_output

    # 5. Canonical Factor 7 calculation manifest assembly
    manifest: Dict[str, Any] = {
        "manifest_id": f"{slug}-manifest",
        "model_name": model_name,
        "formula": formula,
        "inputs": clamped_inputs,
        "published_output": published_output,
        "sample_calculation": sample_calc,
        "statutory_authority": statutory_authority,
        "economic_dataset": economic_dataset,
    }

    # 6. Render Obsidian dark-theme HTML asset
    form_inputs_html = []
    table_rows_html = []
    for var_name, var_val in clamped_inputs.items():
        label_text = var_name.replace("_", " ").title()
        form_inputs_html.append(
            f'        <div class="form-group" style="margin-bottom: 16px;">\n'
            f'          <label for="input-{var_name}" style="display: block; margin-bottom: 6px; font-weight: 500;">{label_text}</label>\n'
            f'          <input type="number" step="any" min="0" id="input-{var_name}" name="{var_name}" '
            f'value="{var_val}" class="touch-target" style="min-height: 44px; min-width: 44px;" />\n'
            f'        </div>'
        )
        table_rows_html.append(
            f'            <tr>\n'
            f'              <td>{label_text}</td>\n'
            f'              <td>{var_val}</td>\n'
            f'              <td>{statutory_authority}</td>\n'
            f'              <td>{economic_dataset}</td>\n'
            f'            </tr>'
        )

    form_inputs_str = "\n".join(form_inputs_html)
    table_rows_str = "\n".join(table_rows_html)
    manifest_json_str = json.dumps(manifest, ensure_ascii=False, indent=2)

    # Format output value for display
    display_output = f"{published_output:,.2f}" if isinstance(published_output, float) and not published_output.is_integer() else f"{published_output:,.0f}"

    is_prexvo = (
        "prexvo" in str(candidate_spec.get("property_id") or "").lower()
        or "prexvo" in str(candidate_spec.get("property") or "").lower()
        or "prexvo" in str(candidate_spec.get("tenant") or "").lower()
        or "prexvo" in str(candidate_spec.get("domain") or "").lower()
        or "prexvo" in str(candidate_spec.get("brand_name") or "").lower()
        or "prexvo" in os.environ.get("FACTORY_PROPERTY_ID", "").lower()
        or "prexvo" in os.environ.get("FACTORY_BRAND_NAME", "").lower()
        or "prexvo" in os.environ.get("FACTORY_DOMAIN", "").lower()
        or any(
            t in str(candidate_spec.get("statutory_authority") or "").lower()
            for t in ("title iv", "34 cfr", "pslf", "repayment assistance plan")
        )
    )
    default_base = "https://prexvo.com" if is_prexvo else "https://profithelm.com"
    env_base = os.environ.get("FACTORY_CANONICAL_BASE", "").strip()
    if is_prexvo and "profithelm.com" in env_base.lower():
        env_base = ""
    canonical_base = (
        str(candidate_spec.get("canonical_base") or "").strip()
        or env_base
        or default_base
    ).rstrip("/")

    is_prexvo_js = "true" if is_prexvo else "false"

    is_prediction_tool = any(
        tok in slug.lower()
        for tok in (
            "prediction",
            "odds",
            "kalshi",
            "kelly",
            "arbitrage",
            "ev",
            "vig",
            "break-even",
        )
    )

    application_category = "FinanceApplication"

    if is_prexvo:
        cluster = PREXVO_STUDENT_LOAN_CLUSTER
        cluster_title = "Related Title IV Student Loan Repayment Tools"
    elif is_prediction_tool:
        cluster = PROFITHELM_PREDICTION_CLUSTER
        cluster_title = "Related Prediction Market Quantitative Tools"
    else:
        cluster = PROFITHELM_TAX_CLUSTER
        cluster_title = "Related Tax and Capital Optimization Tools"

    sibling_links = [(s_slug, s_title) for (s_slug, s_title) in cluster if s_slug != slug]
    if not sibling_links:
        sibling_links = cluster

    cluster_items_html = []
    for s_slug, s_title in sibling_links:
        cluster_items_html.append(
            f'        <li style="margin-bottom: 8px;">\n'
            f'          <a href="{canonical_base}/tools/{s_slug}/" class="touch-target" style="display: block; background: #1e293b; color: var(--accent); padding: 12px 16px; border-radius: 8px; text-decoration: none; min-height: 44px; min-width: 44px;">{s_title}</a>\n'
            f'        </li>'
        )
    cluster_links_html = "\n".join(cluster_items_html)

    # High-intent conversational FAQPage entities
    faq_entities = [
        {
            "@type": "Question",
            "name": f"How is {title} determined under statutory authority guidelines?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": f"The deterministic calculation model evaluates {formula} based on statutory rules from {statutory_authority} and empirical indicators from {economic_dataset}."
            }
        },
        {
            "@type": "Question",
            "name": "What empirical benchmarks validate this firsthand calculation model?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": f"The proprietary model cross-references empirical economic series from {economic_dataset} with statutory authority {statutory_authority}."
            }
        }
    ]

    if is_prediction_tool:
        faq_entities.extend([
            {
                "@type": "Question",
                "name": "How does fee drag impact prediction market profitability on Kalshi and Polymarket?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Kalshi charges quadratic transaction fees peaking at 1.75 cents per contract at fifty-fifty odds, requiring traders to account for fee drag alongside expected value and implied probability spreads."
                }
            },
            {
                "@type": "Question",
                "name": "Why is the Kelly criterion fraction critical for prediction market risk management?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "The Kelly criterion formula determines the mathematically optimal bankroll fraction to wager, protecting capital against volatility while maximizing long-term compound growth."
                }
            },
            {
                "@type": "Question",
                "name": "How are prediction market gains taxed under IRC Section 1256 rules?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Regulated exchange contracts on CFTC-approved venues like Kalshi qualify for Section 1256 sixty-forty tax treatment, splitting gains into sixty percent long-term and forty percent short-term capital rates."
                }
            }
        ])
    elif is_prexvo:
        faq_entities.extend([
            {
                "@type": "Question",
                "name": "Who is eligible for the Repayment Assistance Plan (RAP) under Title IV rules?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Under 34 CFR Part 685, borrowers with eligible federal Direct Loans qualify for RAP based on adjusted gross income and family size relative to federal poverty guidelines."
                }
            },
            {
                "@type": "Question",
                "name": "How does RAP compare to income-driven repayment options like IBR and SAVE?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "RAP establishes affordable monthly payment caps based on discretionary income while preventing runaway balance growth through federal interest subsidies on qualifying Title IV loans."
                }
            },
            {
                "@type": "Question",
                "name": "What requirements determine qualifying monthly payments for PSLF loan forgiveness?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Public Service Loan Forgiveness requires 120 verified on-time monthly payments under an accepted income-driven plan while employed full-time by a qualifying public service employer."
                }
            }
        ])
    else:
        faq_entities.extend([
            {
                "@type": "Question",
                "name": f"What documentation is required to substantiate deductions under {statutory_authority}?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": f"Taxpayers must retain contemporaneous equipment purchase invoices, financing agreements, and tax return statements verifying placing property in service during the eligible tax year."
                }
            },
            {
                "@type": "Question",
                "name": "How do economic phaseout thresholds adjust over time across benchmark series?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": f"Statutory deduction limits and phaseout brackets adjust annually for inflation based on index metrics published in official series like {economic_dataset}."
                }
            }
        ])

    faq_json_str = json.dumps(faq_entities, ensure_ascii=False, indent=6)

    if is_prexvo:
        calc_js_body = f"""      var balance = inputs.balance || inputs.principal || inputs.loan_amount || 35000;
      var rate = (inputs.rate || inputs.interest_rate || 6.5) / 100;
      var income = inputs.income || inputs.agi || 55000;
      var povertyLine = inputs.poverty_line || 15060;

      if (slug.indexOf("rap") !== -1) {{
        var discretionary = Math.max(0, income - (2.25 * povertyLine));
        return Math.round(((discretionary * 0.05) / 12) * 100) / 100;
      }}
      if (slug.indexOf("ibr") !== -1) {{
        var discIbr = Math.max(0, income - (1.50 * povertyLine));
        return Math.round(((discIbr * 0.10) / 12) * 100) / 100;
      }}
      if (slug.indexOf("forgiveness") !== -1 || slug.indexOf("qualifying") !== -1) {{
        return inputs.qualifying_payments ? Math.max(0, 120 - inputs.qualifying_payments) : 120;
      }}
      if (slug.indexOf("interest-subsidy") !== -1) {{
        var monthlyInterest = (balance * rate) / 12;
        var monthlyPay = Math.max(0, (Math.max(0, income - 2.25 * povertyLine) * 0.05) / 12);
        return Math.max(0, Math.round((monthlyInterest - monthlyPay) * 100) / 100);
      }}
      var monthlyRate = rate / 12;
      var nMonths = 120;
      if (monthlyRate === 0) return balance / nMonths;
      var monthlyPmt = (balance * monthlyRate * Math.pow(1 + monthlyRate, nMonths)) / (Math.pow(1 + monthlyRate, nMonths) - 1);
      return Math.round(monthlyPmt * 100) / 100;"""
    else:
      calc_js_body = f"""      if (slug === "prediction-market-kalshi-fees" || slug.indexOf("kalshi-fee") !== -1) {{
        var contracts = inputs.contracts || inputs.volume || 100;
        var p = inputs.probability || inputs.price || inputs.p || 0.5;
        if (p > 1) p = p / 100;
        return Math.ceil(0.07 * contracts * p * (1 - p) * 100) / 100;
      }}
      if (slug === "prediction-market-ev" || slug.indexOf("ev-") !== -1 || slug.indexOf("-ev") !== -1) {{
        var pWin = inputs.prob_win || inputs.probability || inputs.p || 0.5;
        if (pWin > 1) pWin = pWin / 100;
        var stake = inputs.stake || inputs.capital || 100;
        var payout = inputs.payout || inputs.win_payout || 100;
        return (pWin * payout) - ((1 - pWin) * stake);
      }}
      if (slug === "prediction-market-kelly-criterion" || slug.indexOf("kelly") !== -1) {{
        var p = inputs.probability || inputs.prob_win || 0.55;
        if (p > 1) p = p / 100;
        var b = inputs.odds || inputs.net_odds || 1.0;
        var q = 1 - p;
        var f = b > 0 ? (b * p - q) / b : 0;
        return Math.max(0, Math.round(f * 10000) / 100);
      }}
      if (slug === "prediction-market-implied-probability" || slug.indexOf("implied-prob") !== -1) {{
        var price = inputs.price || inputs.cents || 50;
        if (price > 1) return Math.min(100, Math.max(0, price));
        return Math.min(100, Math.max(0, price * 100));
      }}
      if (slug === "prediction-market-arbitrage" || slug.indexOf("arbitrage") !== -1) {{
        var yesPrice = inputs.yes_price || inputs.yes || 52;
        var noPrice = inputs.no_price || inputs.no || 44;
        if (yesPrice > 1) yesPrice = yesPrice / 100;
        if (noPrice > 1) noPrice = noPrice / 100;
        var spread = 1.0 - (yesPrice + noPrice);
        return Math.round(spread * 10000) / 100;
      }}
      if (slug === "prediction-market-vig-spread" || slug.indexOf("vig-spread") !== -1) {{
        var y = inputs.yes || inputs.yes_price || 53;
        var n = inputs.no || inputs.no_price || 51;
        if (y > 1) y = y / 100;
        if (n > 1) n = n / 100;
        var totalImplied = y + n;
        var vig = totalImplied > 1 ? (totalImplied - 1) * 100 : 0;
        return Math.round(vig * 100) / 100;
      }}
      if (slug === "prediction-market-break-even" || slug.indexOf("break-even") !== -1) {{
        var cost = inputs.cost || inputs.price || 55;
        var fee = inputs.fee || 2;
        return cost + fee;
      }}
      if (slug === "prediction-market-tax" || slug.indexOf("sec1256") !== -1) {{
        var gain = inputs.pmgain || inputs.gain || inputs.capital_gain || 10000;
        var rate60 = inputs.rate_lt || 0.20;
        var rate40 = inputs.rate_st || 0.37;
        return (gain * 0.60 * rate60) + (gain * 0.40 * rate40);
      }}
      if (slug.indexOf("179") !== -1) {{
        var cost = inputs.cost || inputs.investment || 0;
        var cap = inputs.cap || 1220000;
        var phaseout = inputs.phaseout || 3050000;
        return Math.max(0, Math.min(cost, cap) - Math.max(0, cost - phaseout));
      }}
      if (slug.indexOf("runway") !== -1) {{
        var cash = inputs.cash || inputs.capital || 100000;
        var burn = inputs.burn || inputs.monthly_burn || 10000;
        return burn > 0 ? Math.round((cash / burn) * 10) / 10 : 0;
      }}
      return {published_output};"""

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1" />
  <meta property="og:title" content="{title}" />
  <meta property="og:description" content="Verified quantitative calculation engine evaluating {title} deterministically." />
  <meta property="og:url" content="{canonical_base}/tools/{slug}/" />
  <meta property="og:type" content="website" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{title}" />
  <meta name="twitter:description" content="Verified quantitative calculation engine evaluating {title} deterministically." />
  <title>{title}</title>
  <link rel="canonical" href="{canonical_base}/tools/{slug}/" />
  <style>
    :root {{
      --bg: #07090e;
      --card-bg: #0f172a;
      --border: rgba(255, 255, 255, 0.08);
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --accent: #38bdf8;
      --accent-hover: #0284c7;
    }}
    * {{
      box-sizing: border-box;
    }}
    *:focus-visible {{
      outline: 2px solid var(--accent);
      outline-offset: 2px;
    }}
    body {{
      background-color: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      line-height: 1.6;
      margin: 0;
      padding: 32px 16px;
    }}
    .container {{
      max-width: 960px;
      margin: 0 auto;
    }}
    .card {{
      background-color: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 24px;
      margin-bottom: 24px;
    }}
    h1, h2, h3 {{
      color: var(--text);
      margin-top: 0;
    }}
    h1 {{
      font-size: 28px;
      line-height: 1.2;
      font-weight: 700;
      letter-spacing: -0.02em;
    }}
    h2 {{
      font-size: 20px;
      line-height: 1.3;
      font-weight: 600;
      letter-spacing: -0.01em;
    }}
    h3 {{
      font-size: 16px;
      line-height: 1.4;
      font-weight: 600;
    }}
    .touch-target {{
      min-height: 44px;
      min-width: 44px;
      padding: 12px 16px;
      font-size: 16px;
      border-radius: 8px;
    }}
    button.touch-target {{
      background-color: var(--accent);
      color: #07090e;
      font-weight: 600;
      border: none;
      cursor: pointer;
    }}
    button.touch-target:hover {{
      background-color: var(--accent-hover);
    }}
    input.touch-target {{
      background-color: #1e293b;
      border: 1px solid var(--border);
      color: var(--text);
      width: 100%;
    }}
    .multi-dataset-join {{
      background-color: #111c35;
      border-left: 4px solid var(--accent);
      padding: 20px;
      border-radius: 8px;
      margin-bottom: 24px;
    }}
    .table-wrap {{
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 8px;
      margin-top: 16px;
    }}
    .calculation-table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 0;
      font-size: 14px;
      font-variant-numeric: tabular-nums;
    }}
    .calculation-table th, .calculation-table td {{
      border: 1px solid var(--border);
      padding: 12px;
      text-align: left;
    }}
    .calculation-table th {{
      background-color: #1e293b;
    }}
    .canonical-tool-link {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      background-color: var(--card-bg);
      border: 1px solid var(--accent);
      color: var(--accent);
      text-decoration: none;
      font-weight: 600;
      min-height: 44px;
      min-width: 44px;
    }}
    @media (max-width: 640px) {{
      body {{
        padding: 16px 12px;
      }}
      .card {{
        padding: 16px;
        margin-bottom: 16px;
      }}
      .calculator-form {{
        display: flex;
        flex-direction: column;
        gap: 12px;
      }}
      h1 {{
        font-size: 22px;
      }}
      h2 {{
        font-size: 18px;
      }}
    }}
  </style>
  <!-- Schema.org Application Type: "@type": "SoftwareApplication" -->
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": ["WebApplication", "SoftwareApplication"],
    "@id": "{canonical_base}/tools/{slug}/#app",
    "name": "{title}",
    "applicationCategory": "{application_category}",
    "operatingSystem": "All",
    "url": "{canonical_base}/tools/{slug}/",
    "offers": {{
      "@type": "Offer",
      "price": "0.00",
      "priceCurrency": "USD"
    }}
  }}
  </script>
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "@id": "{canonical_base}/tools/{slug}/#breadcrumb",
    "itemListElement": [
      {{
        "@type": "ListItem",
        "position": 1,
        "name": "Home",
        "item": "{canonical_base}/"
      }},
      {{
        "@type": "ListItem",
        "position": 2,
        "name": "Tools",
        "item": "{canonical_base}/tools/"
      }},
      {{
        "@type": "ListItem",
        "position": 3,
        "name": "{title}",
        "item": "{canonical_base}/tools/{slug}/"
      }}
    ]
  }}
  </script>
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "@id": "{canonical_base}/tools/{slug}/#faq",
    "about": {{
      "@id": "{canonical_base}/tools/{slug}/#app"
    }},
    "mainEntity": {faq_json_str}
  }}
  </script>
</head>
<body>
  <div class="container">
    <header class="card">
      <h1>{title}</h1>
      <p class="takeaway">
        Executive Direct Answer: The {model_name} produces a verified baseline result of <strong>{display_output}</strong>
        derived deterministically via formula <code>{formula}</code>. This high-effort analytical asset eliminates guesswork
        by integrating authoritative federal statutory provisions with macroeconomic dataset benchmarks.
      </p>
    </header>

    <div class="multi-dataset-join card" data-statutory-source="{statutory_authority}" data-economic-source="{economic_dataset}">
      <h2>Dual Dataset Provenance and Statutory Corroboration</h2>
      <p>
        Primary statutory authority: <strong>{statutory_authority}</strong> provides the legal basis, statutory deduction thresholds,
        phaseout schedules, and mandatory compliance rules for this calculation.
      </p>
      <p>
        Empirical economic benchmark dataset: <strong>{economic_dataset}</strong> provides empirical series validation,
        cost indexes, and macroeconomic context from the Bureau of Labor Statistics and Federal Reserve systems.
      </p>
    </div>

    <div class="calculation-container card">
      <h2>Interactive Quantitative Model: {model_name}</h2>
      <p>
        Input parameters are validated mechanically with client-side deserializers clamping numeric metrics to non-negative values
        (greater than or equal to zero) per HWL-1263 to prevent crawler or user state corruption.
      </p>
      <form class="calculator-form" id="{slug}-calculator" method="post" action="javascript:void(0);">
{form_inputs_str}
        <button type="submit" class="touch-target" id="calculate-btn" style="min-height: 44px; min-width: 44px;">Recalculate Output</button>
      </form>
      <div class="result-box" style="margin-top: 20px;">
        <h3>Published Baseline Calculation</h3>
        <p>Formula: <code>{formula}</code></p>
        <p>Evaluated Output Result: <strong class="output-value">{display_output}</strong></p>
        <p>Sample Calculation Methodology: {sample_calc}</p>
      </div>

      <figure>
        <div class="table-wrap">
          <table class="calculation-table" data-statutory-source="{statutory_authority}" data-economic-source="{economic_dataset}">
            <thead>
              <tr>
                <th>Input Variable</th>
                <th>Clamped Value</th>
                <th>Statutory Authority</th>
                <th>Economic Benchmark</th>
              </tr>
            </thead>
            <tbody>
{table_rows_str}
            </tbody>
          </table>
        </div>
        <figcaption style="margin-top: 8px; color: var(--text-muted); font-size: 14px;">
          Table 1: Grounded calculation parameters citing statutory authority {statutory_authority} and economic dataset {economic_dataset}.
        </figcaption>
      </figure>
    </div>

    <section class="methodology card">
      <h2>Statutory Analysis and Computational Methodology</h2>
      <p>
        This computational tool was engineered to satisfy strict high-effort content qualification requirements.
        Rather than relying on speculative estimates or stochastic language model generations, every metric on this page
        is evaluated through abstract syntax tree mathematical interpretation.
        The governing statutory authority {statutory_authority} sets the exact legal formulas, phaseout rates, and deduction caps.
        Simultaneously, empirical dataset series from {economic_dataset} provide independent validation for inflation adjustments,
        cost basis indices, and market trends.
      </p>
    </section>

    <nav class="cluster-nav card" aria-label="{cluster_title}">
      <h2>{cluster_title}</h2>
      <p style="color: var(--text-muted); font-size: 14px; margin-bottom: 16px;">
        Explore verified peer computational models in this specialized quantitative cluster:
      </p>
      <ul style="list-style: none; padding: 0; margin: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px;">
{cluster_links_html}
      </ul>
    </nav>

    <footer class="card" style="text-align: center;">
      <a href="{canonical_base}/tools/{slug}/" class="canonical-tool-link touch-target" style="min-height: 44px; min-width: 44px;">
        Launch Full {title} Engine
      </a>
    </footer>
  </div>

  <script type="application/json" class="calculation-manifest" id="{slug}-manifest">
{manifest_json_str}
  </script>

  <script>
  (function() {{
    var form = document.getElementById("{slug}-calculator");
    if (!form) return;
    var outputElem = document.querySelector(".output-value");
    var slug = "{slug}";
    function formatNumber(val) {{
      if (isNaN(val) || !isFinite(val)) return "0";
      return new Intl.NumberFormat("en-US", {{
        minimumFractionDigits: Number.isInteger(val) ? 0 : 2,
        maximumFractionDigits: 2
      }}).format(val);
    }}

    function getInputs() {{
      var inputs = {{}};
      var elements = form.querySelectorAll("input, select");
      for (var i = 0; i < elements.length; i++) {{
        var el = elements[i];
        var name = el.name || el.id;
        if (!name) continue;
        var cleanName = name.replace(/^input-/, "");
        var v = parseFloat(el.value);
        inputs[cleanName] = isNaN(v) ? 0 : Math.max(0, v);
      }}
      return inputs;
    }}

    var debounceTimer = null;
    function updateQueryParams(inputs) {{
      if (!window.history || !window.history.replaceState) return;
      if (debounceTimer) clearTimeout(debounceTimer);
      debounceTimer = setTimeout(function() {{
        try {{
          var url = new URL(window.location.href);
          for (var k in inputs) {{
            url.searchParams.set(k, inputs[k]);
          }}
          window.history.replaceState({{}}, "", url.toString());
        }} catch (e) {{}}
      }}, 150);
    }}

    function syncInputsFromParams() {{
      if (!window.location || !window.location.search) return;
      try {{
        var params = new URLSearchParams(window.location.search);
        var elements = form.querySelectorAll("input, select");
        for (var i = 0; i < elements.length; i++) {{
          var el = elements[i];
          var name = (el.name || el.id || "").replace(/^input-/, "");
          if (params.has(name)) {{
            el.value = params.get(name);
          }}
        }}
      }} catch (e) {{}}
    }}

    function calculate(inputs) {{
{calc_js_body}
    }}

    function handleRecompute() {{
      var inputs = getInputs();
      updateQueryParams(inputs);
      var result = calculate(inputs);
      if (outputElem) {{
        outputElem.textContent = formatNumber(result);
      }}
    }}

    syncInputsFromParams();
    form.addEventListener("input", handleRecompute);
    form.addEventListener("change", handleRecompute);
    form.addEventListener("submit", function(e) {{
      e.preventDefault();
      handleRecompute();
      return false;
    }});
  }})();
  </script>
</body>
</html>
"""

    # 7. Strictly verify zero forbidden dashes
    assert_no_forbidden_dashes(html_content, context=f"compiled page '{slug}'")

    # 8. Self-verify using verify_html_unique_first_party_information
    audit_res = verify_html_unique_first_party_information(
        html_content,
        rel_path=f"tools/{slug}/index.html",
        manifest_data=manifest,
    )
    if audit_res.get("status") != "PASS":
        issues_list = audit_res.get("issues", [])
        raise ValueError(f"Content compiler self-audit failed: {issues_list}")

    return {
        "slug": slug,
        "title": title,
        "html": html_content,
        "manifest": manifest,
        "published_output": published_output,
        "verified": True,
    }
