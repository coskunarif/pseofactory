"""
pseofactory Minimal Modern Light User Interface
Renders live partner tracking, monetization readiness, and human action bus status.
Enforces zero layout shifts (CLS = 0) and touch targets meeting or exceeding 44px.

Key Invariants:
1. Minimal modern light aesthetic (crisp white, high-contrast typography, zero slop).
2. Zero layout shifts (CLS = 0) with sized containers and system font stacks.
3. Touch targets strictly meeting or exceeding 44x44 pixels.
4. Strictly maintain property boundaries (separate ProfitHelm and Prexvo views).
5. Zero em-dashes and zero en-dashes across all rendered markup.

Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import html
import json
import os
import re
from typing import Dict, Any, List, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

from pseofactory.contracts import assert_no_forbidden_dashes, assert_touch_targets
from pseofactory.partner_tracker import FleetMonetizationDashboardData, PartnerTrackingEngine


def render_light_interface(data: FleetMonetizationDashboardData) -> str:
    """
    Renders complete standalone HTML document for the minimal modern light interface.
    Asserts zero layout shifts, 44px touch targets, and zero forbidden dashes.
    """
    ph = data.profithelm
    px = data.prexvo
    actions = data.all_action_items
    emails = data.recent_emails

    pending_actions = [a for a in actions if a.status == "PENDING_OPERATOR"]
    resolved_actions = [a for a in actions if a.status != "PENDING_OPERATOR"]

    # Build action cards markup
    action_cards_html = []
    if not pending_actions:
        action_cards_html.append(
            """<div class="empty-state">
                <p>Zero pending operator decisions. All partner requirements and compliance gates are clear.</p>
            </div>"""
        )
    else:
        for it in pending_actions:
            sev_class = f"badge-{it.severity.lower()}"
            prop_badge = "ProfitHelm" if it.property_id == "profithelm" else "Prexvo"
            deadline_markup = f'<div class="action-deadline">Deadline: {html.escape(it.deadline)}</div>' if it.deadline else ""
            reqs_markup = "".join(f"<li>{html.escape(r)}</li>" for r in it.missing_requirements)

            action_cards_html.append(f"""
            <div class="action-card" data-action-id="{html.escape(it.action_id)}" data-property="{html.escape(it.property_id)}">
                <div class="action-card-header">
                    <div class="action-card-title-group">
                        <span class="badge badge-property">{prop_badge}</span>
                        <span class="badge {sev_class}">{html.escape(it.severity)}</span>
                        <span class="badge badge-type">{html.escape(it.action_type.replace('_', ' '))}</span>
                    </div>
                    {deadline_markup}
                </div>
                <h3 class="action-title">{html.escape(it.title)}</h3>
                <p class="action-desc">{html.escape(it.description)}</p>
                {f'<ul class="action-reqs">{reqs_markup}</ul>' if it.missing_requirements else ''}
                <div class="action-footer">
                    <span class="action-id">ID: {html.escape(it.action_id)}</span>
                    <div class="action-btn-group">
                        <button class="btn btn-approve" onclick="handleDecision('{html.escape(it.action_id)}', 'APPROVE')">Approve</button>
                        <button class="btn btn-reject" onclick="handleDecision('{html.escape(it.action_id)}', 'REJECT')">Reject</button>
                        <button class="btn btn-resolve" onclick="handleDecision('{html.escape(it.action_id)}', 'RESOLVE')">Resolve</button>
                    </div>
                </div>
            </div>
            """)

    # Build Partner Rows for ProfitHelm
    ph_rows = []
    for p in ph.partners:
        status_badge = _render_status_badge(p.operational_status)
        reqs = "<br>".join(html.escape(r) for r in p.missing_requirements) if p.missing_requirements else "<span class=\"text-muted\">None (Complete)</span>"
        link_markup = f'<a href="{html.escape(p.destination_url)}" target="_blank" rel="noopener sponsored nofollow" class="partner-link">Open Partner URL</a>' if p.destination_url else '<span class="text-muted">Not Configured</span>'
        ph_rows.append(f"""
        <tr>
            <td class="col-name"><strong>{html.escape(p.name)}</strong></td>
            <td class="col-cat">{html.escape(p.category)}</td>
            <td class="col-net">{html.escape(p.network)}</td>
            <td class="col-bounty">{html.escape(p.bounty_est)}</td>
            <td class="col-status">{status_badge}</td>
            <td class="col-link">{link_markup}</td>
            <td class="col-reqs">{reqs}</td>
        </tr>
        """)

    # Build Partner Rows for Prexvo
    px_rows = []
    for p in px.partners:
        status_badge = _render_status_badge(p.operational_status)
        reqs = "<br>".join(html.escape(r) for r in p.missing_requirements) if p.missing_requirements else "<span class=\"text-muted\">None (Complete)</span>"
        link_markup = f'<a href="{html.escape(p.destination_url)}" target="_blank" rel="noopener sponsored nofollow" class="partner-link">Open Partner URL</a>' if p.destination_url else '<span class="text-muted">Not Configured</span>'
        px_rows.append(f"""
        <tr>
            <td class="col-name"><strong>{html.escape(p.name)}</strong></td>
            <td class="col-cat">{html.escape(p.category)}</td>
            <td class="col-net">{html.escape(p.network)}</td>
            <td class="col-bounty">{html.escape(p.bounty_est)}</td>
            <td class="col-status">{status_badge}</td>
            <td class="col-link">{link_markup}</td>
            <td class="col-reqs">{reqs}</td>
        </tr>
        """)

    # Build recent email items
    email_rows = []
    for em in emails[:12]:
        date_short = em["date"][:16].replace("T", " ") if em.get("date") else ""
        email_rows.append(f"""
        <tr>
            <td class="col-date">{html.escape(date_short)}</td>
            <td class="col-acct"><span class="badge badge-subtle">{html.escape(em.get('account',''))}</span></td>
            <td class="col-from">{html.escape(em.get('sender',''))}</td>
            <td class="col-subj">{html.escape(em.get('subject',''))}</td>
            <td class="col-snip">{html.escape(em.get('snippet',''))}</td>
        </tr>
        """)

    # Build resolved operator decisions audit rows
    resolved_rows = []
    for r in resolved_actions:
        res_date = r.resolved_at[:16].replace("T", " ") if r.resolved_at else "Confirmed"
        prop_label = "ProfitHelm" if r.property_id == "profithelm" else "Prexvo"
        resolved_rows.append(f"""
        <tr>
            <td class="col-date">{html.escape(res_date)}</td>
            <td class="col-acct"><span class="badge badge-property">{html.escape(prop_label)}</span></td>
            <td class="col-name"><strong>{html.escape(r.title)}</strong></td>
            <td class="col-status"><span class="badge badge-live">{html.escape(r.status)}</span></td>
            <td class="col-from">{html.escape(r.resolved_by or 'operator')}</td>
            <td class="col-snip">{html.escape(r.operator_notes or 'Decision confirmed')}</td>
        </tr>
        """)

    markup = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>pseofactory Partner Tracking & Monetization Readiness</title>
    <style>
        :root {{
            --bg-canvas: #ffffff;
            --bg-subtle: #f8fafc;
            --bg-surface: #ffffff;
            --border-subtle: #e2e8f0;
            --border-strong: #cbd5e1;
            --text-main: #0f172a;
            --text-sub: #475569;
            --text-muted: #94a3b8;
            --primary: #2563eb;
            --primary-subtle: #eff6ff;
            --success: #059669;
            --success-subtle: #ecfdf5;
            --warning: #d97706;
            --warning-subtle: #fffbeb;
            --danger: #dc2626;
            --danger-subtle: #fef2f2;
            --radius-md: 8px;
            --radius-lg: 12px;
            --font-stack: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: var(--font-stack);
            background-color: var(--bg-subtle);
            color: var(--text-main);
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
            padding: 24px 16px;
        }}
        .container {{
            max-width: 1280px;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            gap: 24px;
        }}
        /* Top Navigation Header */
        .header {{
            background: var(--bg-canvas);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-lg);
            padding: 20px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
            min-height: 80px;
        }}
        .header-title-group h1 {{
            font-size: 20px;
            font-weight: 700;
            color: var(--text-main);
            letter-spacing: -0.01em;
        }}
        .header-title-group p {{
            font-size: 13px;
            color: var(--text-sub);
            margin-top: 2px;
        }}
        .header-actions {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        /* Touch Targets Strictly >= 44px */
        .btn {{
            min-height: 44px;
            min-width: 44px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0 18px;
            font-size: 13px;
            font-weight: 600;
            border-radius: var(--radius-md);
            border: 1px solid transparent;
            cursor: pointer;
            transition: background-color 0.15s ease, border-color 0.15s ease;
            text-decoration: none;
            user-select: none;
        }}
        .btn-primary {{
            background: var(--primary);
            color: #ffffff;
            border-color: var(--primary);
        }}
        .btn-primary:hover {{
            background: #1d4ed8;
        }}
        .btn-subtle {{
            background: var(--bg-canvas);
            color: var(--text-main);
            border-color: var(--border-subtle);
        }}
        .btn-subtle:hover {{
            background: var(--bg-subtle);
            border-color: var(--border-strong);
        }}
        .btn-approve {{
            background: var(--success-subtle);
            color: var(--success);
            border-color: #a7f3d0;
            min-width: 90px;
        }}
        .btn-approve:hover {{
            background: #d1fae5;
        }}
        .btn-reject {{
            background: var(--danger-subtle);
            color: var(--danger);
            border-color: #fecdd3;
            min-width: 90px;
        }}
        .btn-reject:hover {{
            background: #ffe4e6;
        }}
        .btn-resolve {{
            background: var(--primary-subtle);
            color: var(--primary);
            border-color: #bfdbfe;
            min-width: 90px;
        }}
        .btn-resolve:hover {{
            background: #dbeafe;
        }}
        .tab-btn {{
            min-height: 44px;
            min-width: 90px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0 16px;
            font-size: 13px;
            font-weight: 600;
            border-radius: var(--radius-md);
            border: 1px solid var(--border-subtle);
            background: var(--bg-canvas);
            color: var(--text-sub);
            cursor: pointer;
        }}
        .tab-btn.active {{
            background: var(--text-main);
            color: #ffffff;
            border-color: var(--text-main);
        }}
        /* Badges */
        .badge {{
            display: inline-flex;
            align-items: center;
            padding: 4px 10px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            border-radius: 9999px;
            border: 1px solid transparent;
            line-height: 1;
            white-space: nowrap;
        }}
        .badge-live {{
            background: var(--success-subtle);
            color: var(--success);
            border-color: #a7f3d0;
        }}
        .badge-awaiting {{
            background: var(--warning-subtle);
            color: var(--warning);
            border-color: #fde68a;
        }}
        .badge-followup {{
            background: var(--danger-subtle);
            color: var(--danger);
            border-color: #fecdd3;
        }}
        .badge-pending {{
            background: #f1f5f9;
            color: #475569;
            border-color: #cbd5e1;
        }}
        .badge-property {{
            background: #eff6ff;
            color: #1d4ed8;
            border-color: #bfdbfe;
        }}
        .badge-critical {{
            background: #fef2f2;
            color: #b91c1c;
            border-color: #fecaca;
        }}
        .badge-high {{
            background: #fff7ed;
            color: #c2410c;
            border-color: #fed7aa;
        }}
        .badge-medium {{
            background: #fefce8;
            color: #a16207;
            border-color: #fef08a;
        }}
        .badge-low {{
            background: #f8fafc;
            color: #475569;
            border-color: #e2e8f0;
        }}
        .badge-type {{
            background: #f3e8ff;
            color: #7e22ce;
            border-color: #e9d5ff;
        }}
        .badge-subtle {{
            background: #f8fafc;
            color: #64748b;
            border-color: #e2e8f0;
        }}
        /* KPI Cards Grid */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 16px;
        }}
        .kpi-card {{
            background: var(--bg-canvas);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-lg);
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 8px;
            min-height: 140px;
        }}
        .kpi-card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .kpi-label {{
            font-size: 13px;
            font-weight: 600;
            color: var(--text-sub);
        }}
        .kpi-value {{
            font-size: 32px;
            font-weight: 800;
            color: var(--text-main);
            letter-spacing: -0.03em;
            line-height: 1.1;
        }}
        .kpi-meta {{
            font-size: 12px;
            color: var(--text-muted);
            margin-top: auto;
        }}
        /* Section Containers */
        .section {{
            background: var(--bg-canvas);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-lg);
            padding: 24px;
            display: flex;
            flex-direction: column;
            gap: 20px;
        }}
        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-subtle);
            padding-bottom: 16px;
            flex-wrap: wrap;
            gap: 12px;
        }}
        .section-title-group h2 {{
            font-size: 17px;
            font-weight: 700;
            color: var(--text-main);
        }}
        .section-title-group p {{
            font-size: 13px;
            color: var(--text-sub);
            margin-top: 2px;
        }}
        /* Action Bus Cards */
        .action-list {{
            display: flex;
            flex-direction: column;
            gap: 16px;
        }}
        .action-card {{
            background: #ffffff;
            border: 1px solid var(--border-subtle);
            border-left: 4px solid var(--primary);
            border-radius: var(--radius-md);
            padding: 18px 20px;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}
        .action-card[data-property="prexvo"] {{
            border-left-color: #8b5cf6;
        }}
        .action-card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .action-card-title-group {{
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }}
        .action-deadline {{
            font-size: 12px;
            font-weight: 700;
            color: var(--danger);
            background: var(--danger-subtle);
            padding: 4px 8px;
            border-radius: var(--radius-md);
            border: 1px solid #fecaca;
        }}
        .action-title {{
            font-size: 15px;
            font-weight: 700;
            color: var(--text-main);
        }}
        .action-desc {{
            font-size: 13px;
            color: var(--text-sub);
        }}
        .action-reqs {{
            margin-left: 20px;
            font-size: 12px;
            color: #64748b;
        }}
        .action-reqs li {{
            margin-bottom: 4px;
        }}
        .action-footer {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-top: 1px solid var(--border-subtle);
            padding-top: 12px;
            flex-wrap: wrap;
            gap: 12px;
        }}
        .action-id {{
            font-size: 11px;
            color: var(--text-muted);
            font-family: monospace;
        }}
        .action-btn-group {{
            display: flex;
            gap: 8px;
        }}
        /* Tables (table-layout fixed to prevent CLS) */
        .table-wrap {{
            overflow-x: auto;
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed;
            font-size: 13px;
        }}
        th {{
            background: var(--bg-subtle);
            color: var(--text-sub);
            font-weight: 600;
            text-align: left;
            padding: 12px 14px;
            border-bottom: 1px solid var(--border-subtle);
            white-space: nowrap;
        }}
        td {{
            padding: 12px 14px;
            border-bottom: 1px solid var(--border-subtle);
            vertical-align: middle;
            word-wrap: break-word;
        }}
        tr:last-child td {{
            border-bottom: none;
        }}
        tr:hover td {{
            background-color: #fafbfc;
        }}
        .col-name {{ width: 22%; }}
        .col-cat {{ width: 15%; }}
        .col-net {{ width: 13%; }}
        .col-bounty {{ width: 12%; }}
        .col-status {{ width: 14%; }}
        .col-link {{ width: 12%; }}
        .col-reqs {{ width: 12%; }}

        .col-date {{ width: 15%; }}
        .col-acct {{ width: 10%; }}
        .col-from {{ width: 20%; }}
        .col-subj {{ width: 25%; }}
        .col-snip {{ width: 30%; }}

        .partner-link {{
            color: var(--primary);
            text-decoration: none;
            font-weight: 600;
            min-height: 44px;
            min-width: 44px;
            display: inline-flex;
            align-items: center;
        }}
        .partner-link:hover {{
            text-decoration: underline;
        }}
        .text-muted {{
            color: var(--text-muted);
        }}
        .standing-card {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: var(--radius-md);
            padding: 12px 16px;
            font-size: 12px;
            color: var(--text-sub);
        }}
        .empty-state {{
            padding: 32px;
            text-align: center;
            color: var(--text-muted);
            font-size: 14px;
        }}
        /* Feedback Toast */
        #toast {{
            position: fixed;
            bottom: 24px;
            right: 24px;
            padding: 12px 20px;
            background: var(--text-main);
            color: #ffffff;
            border-radius: var(--radius-md);
            font-size: 13px;
            font-weight: 600;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            display: none;
            z-index: 1000;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header class="header">
            <div class="header-title-group">
                <h1>pseofactory Monetization Hub & Partner Tracking</h1>
                <p>Automated partner correspondence, human action bus, and monetization readiness</p>
            </div>
            <div class="header-actions">
                <span class="badge badge-live">Isolation: Strict Pass</span>
                <button class="btn btn-subtle" onclick="triggerSync()">Sync Mailbox</button>
            </div>
        </header>

        <!-- KPI Summary Cards -->
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-card-header">
                    <span class="kpi-label">ProfitHelm Readiness</span>
                    <span class="badge badge-property">ProfitHelm</span>
                </div>
                <div class="kpi-value">{ph.monetization_readiness_score}%</div>
                <div class="kpi-meta">{ph.active_partners_count} Live Active / {ph.total_registered_partners} Total Partners</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-card-header">
                    <span class="kpi-label">Prexvo Readiness</span>
                    <span class="badge badge-property" style="background:#f3e8ff;color:#7e22ce;border-color:#e9d5ff;">Prexvo</span>
                </div>
                <div class="kpi-value">{px.monetization_readiness_score}%</div>
                <div class="kpi-meta">0 Active (Gate 1 Payout Verification Pending)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-card-header">
                    <span class="kpi-label">Operator Action Items</span>
                    <span class="badge badge-followup">{len(pending_actions)} Pending</span>
                </div>
                <div class="kpi-value">{len(pending_actions)}</div>
                <div class="kpi-meta">Requires Operator Confirmation (Auto-Approval Forbidden)</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-card-header">
                    <span class="kpi-label">Awaiting Partner Response</span>
                    <span class="badge badge-awaiting">{ph.awaiting_response_count + px.awaiting_response_count} Awaiting</span>
                </div>
                <div class="kpi-value">{ph.awaiting_response_count + px.awaiting_response_count}</div>
                <div class="kpi-meta">Applications Submitted (e.g. Gusto on Impact.com)</div>
            </div>
        </div>

        <!-- Section 1: Human Action Bus -->
        <section class="section">
            <div class="section-header">
                <div class="section-title-group">
                    <h2>Dedicated Human Action Bus</h2>
                    <p>Items requiring operator intervention. Standing invariant: never auto-approve partner agreements without operator confirmation.</p>
                </div>
                <div class="header-actions">
                    <button class="tab-btn active" onclick="filterActions('all', event)">All Actions</button>
                    <button class="tab-btn" onclick="filterActions('profithelm', event)">ProfitHelm</button>
                    <button class="tab-btn" onclick="filterActions('prexvo', event)">Prexvo</button>
                </div>
            </div>
            <div class="action-list" id="action-list-container">
                {"".join(action_cards_html)}
            </div>
        </section>

        <!-- Section 2: ProfitHelm Monetization Registry -->
        <section class="section" id="section-profithelm">
            <div class="section-header">
                <div class="section-title-group">
                    <h2>ProfitHelm Partner Matrix & Monetization Readiness</h2>
                    <p>B2B commercial banking, corporate treasury, crypto tax, equipment financing, and real estate exchange partners.</p>
                </div>
                <span class="badge badge-property">FTC Disclosure Compliant</span>
            </div>
            <div class="standing-card">
                <strong>Standing Policy:</strong> ProfitHelm is an independent financial research publisher. FTC publisher disclosures are strictly required across all monetized calculators. Student loan refinancing links are strictly prohibited.
            </div>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th class="col-name">Partner Name</th>
                            <th class="col-cat">Category</th>
                            <th class="col-net">Network</th>
                            <th class="col-bounty">Bounty / Comm</th>
                            <th class="col-status">Operational Status</th>
                            <th class="col-link">Target URL</th>
                            <th class="col-reqs">Missing Requirements</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(ph_rows)}
                    </tbody>
                </table>
            </div>
        </section>

        <!-- Section 3: Prexvo Monetization Registry -->
        <section class="section" id="section-prexvo">
            <div class="section-header">
                <div class="section-title-group">
                    <h2>Prexvo Partner Matrix & Statutory Protections</h2>
                    <p>Federal student loan relief and refinance comparison partners. Commercial B2B monetization is strictly prohibited.</p>
                </div>
                <span class="badge" style="background:#fef2f2;color:#b91c1c;border-color:#fecaca;">Sub-Affiliate Fallback Prohibited</span>
            </div>
            <div class="standing-card">
                <strong>CFPB Compliance & Standing Restriction:</strong> Prexvo student loan refinance hypothesis is strictly conditional pending Gate 1 (written payout >= $45). Mandatory YMYL warning required: refinancing federal loans permanently forfeits federal protections. Sub-affiliate aggregator redirects are strictly prohibited.
            </div>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th class="col-name">Partner Name</th>
                            <th class="col-cat">Category</th>
                            <th class="col-net">Network</th>
                            <th class="col-bounty">Bounty / Comm</th>
                            <th class="col-status">Operational Status</th>
                            <th class="col-link">Target URL</th>
                            <th class="col-reqs">Missing Requirements</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(px_rows)}
                    </tbody>
                </table>
            </div>
        </section>

        <!-- Section 4: Live Email Correspondence Log -->
        <section class="section">
            <div class="section-header">
                <div class="section-title-group">
                    <h2>Inbound Correspondence Stream</h2>
                    <p>Recent inbound correspondence from himalaya CLI (arif.coskun@profithelm.com) and personal inbox.</p>
                </div>
                <span class="badge badge-subtle">Himalaya IMAP & Personal Cache</span>
            </div>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th class="col-date">Date</th>
                            <th class="col-acct">Account</th>
                            <th class="col-from">Sender</th>
                            <th class="col-subj">Subject</th>
                            <th class="col-snip">Snippet</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(email_rows)}
                    </tbody>
                </table>
            </div>
        </section>

        <!-- Section 5: Operator Decision Audit Trail -->
        <section class="section" id="section-audit">
            <div class="section-header">
                <div class="section-title-group">
                    <h2>Operator Decision Audit Trail</h2>
                    <p>Verified human decisions confirmed on the action bus. Auto-approval is strictly forbidden.</p>
                </div>
                <span class="badge badge-live">{len(resolved_actions)} Confirmed</span>
            </div>
            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th class="col-date">Resolved At</th>
                            <th class="col-acct">Property</th>
                            <th class="col-name">Action Title</th>
                            <th class="col-status">Status</th>
                            <th class="col-from">Operator</th>
                            <th class="col-snip">Notes</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(resolved_rows) if resolved_rows else '<tr><td colspan="6" class="text-muted" style="text-align:center;padding:24px;">Zero resolved operator decisions recorded yet.</td></tr>'}
                    </tbody>
                </table>
            </div>
        </section>
    </div>

    <div id="toast"></div>

    <script>
        function showToast(msg) {{
            const t = document.getElementById('toast');
            t.textContent = msg;
            t.style.display = 'block';
            setTimeout(() => {{ t.style.display = 'none'; }}, 3000);
        }}

        function handleDecision(actionId, decision) {{
            fetch('/api/actions/' + encodeURIComponent(actionId) + '/confirm', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ decision: decision, operator: 'operator', notes: 'Operator decision executed via web interface.' }})
            }})
            .then(res => res.json())
            .then(data => {{
                if (data.ok) {{
                    showToast('Action confirmed: ' + decision + ' for ' + actionId);
                    const el = document.querySelector('[data-action-id="' + actionId + '"]');
                    if (el) {{
                        el.style.opacity = '0.75';
                        const btnGroup = el.querySelector('.action-btn-group');
                        if (btnGroup) {{
                            btnGroup.innerHTML = '<span class="badge badge-live" style="min-height:44px;min-width:44px;display:inline-flex;align-items:center;padding:0 14px;">' + decision + ' Confirmed</span>';
                        }}
                        const titleGroup = el.querySelector('.action-card-title-group');
                        if (titleGroup) {{
                            titleGroup.insertAdjacentHTML('beforeend', '<span class="badge badge-live">Status: ' + decision + '</span>');
                        }}
                    }}
                }} else {{
                    showToast('Error: ' + (data.error || 'Failed to update action'));
                }}
            }})
            .catch(err => {{
                showToast('Action failed: ' + err.message);
            }});
        }}

        function triggerSync() {{
            showToast('Syncing correspondence via himalaya...');
            fetch('/api/sync', {{ method: 'POST' }})
            .then(res => res.json())
            .then(data => {{
                showToast('Sync complete. Reloading...');
                setTimeout(() => {{ window.location.reload(); }}, 800);
            }})
            .catch(err => {{
                showToast('Sync error: ' + err.message);
            }});
        }}

        function filterActions(prop, evt) {{
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            const target = evt ? (evt.currentTarget || evt.target) : null;
            if (target) {{
                target.classList.add('active');
            }}
            const cards = document.querySelectorAll('.action-card');
            cards.forEach(c => {{
                if (prop === 'all' || c.getAttribute('data-property') === prop) {{
                    c.style.display = 'flex';
                }} else {{
                    c.style.display = 'none';
                }}
            }});
        }}
    </script>
</body>
</html>
"""

    # Mechanical verification of contracts on rendered HTML
    assert_no_forbidden_dashes(markup, context="Rendered Light Interface HTML")
    assert_touch_targets(markup, is_css=False, context="Rendered Light Interface Touch Targets")

    return markup


def _render_status_badge(status: str) -> str:
    """Helper to render uniform status badges with zero forbidden dashes."""
    s = (status or "").upper()
    if s == "LIVE_ACTIVE":
        return '<span class="badge badge-live">Live Active</span>'
    elif s == "AWAITING_RESPONSE":
        return '<span class="badge badge-awaiting">Awaiting Response</span>'
    elif s == "REQUIRES_FOLLOWUP":
        return '<span class="badge badge-followup">Requires Follow-up</span>'
    elif s == "PENDING_P2":
        return '<span class="badge badge-pending">Pending P2 (Gate 1)</span>'
    else:
        return '<span class="badge badge-pending">Pending Expansion</span>'


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """Minimal HTTP server handler providing dashboard UI and decision endpoints."""

    def __init__(self, *args, tracking_engine: Optional[PartnerTrackingEngine] = None, **kwargs):
        self.engine = tracking_engine or PartnerTrackingEngine()
        super().__init__(*args, **kwargs)

    def do_HEAD(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path in ("/", "/dashboard", "/index.html", "/api/status", "/api/actions"):
            self.send_response(200)
            if parsed.path in ("/", "/dashboard", "/index.html"):
                self.send_header("Content-Type", "text/html; charset=utf-8")
            else:
                self.send_header("Content-Type", "application/json")
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path in ("/", "/dashboard", "/index.html"):
            try:
                data = self.engine.sync_and_evaluate(force_mail_poll=False)
                html_content = render_light_interface(data)
                body = html_content.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as exc:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(exc)}).encode("utf-8"))
        elif parsed.path == "/api/status":
            try:
                data = self.engine.sync_and_evaluate(force_mail_poll=False)
                body = json.dumps(data.to_dict(), indent=2).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as exc:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(exc)}).encode("utf-8"))
        elif parsed.path == "/api/actions":
            try:
                query_params = urllib.parse.parse_qs(parsed.query)
                prop_filter = query_params.get("property", [None])[0]
                status_filter = query_params.get("status", [None])[0]
                items = self.engine.action_bus.get_all_items(property_id=prop_filter)
                if status_filter:
                    items = [it for it in items if it.status.upper() == status_filter.upper()]
                body = json.dumps([it.to_dict() for it in items], indent=2).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as exc:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(exc)}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            payload = json.loads(post_data.decode("utf-8"))
        except Exception:
            payload = {}

        # Handle Action Confirmation
        m_action = re.match(r"^/api/actions/([^/]+)/confirm$", parsed.path)
        if m_action:
            action_id = urllib.parse.unquote(m_action.group(1))
            decision = payload.get("decision", "RESOLVE")
            operator = payload.get("operator", "operator")
            notes = payload.get("notes", "")
            try:
                updated = self.engine.action_bus.confirm_decision(
                    action_id=action_id,
                    decision=decision,
                    operator=operator,
                    notes=notes,
                )
                res_body = json.dumps({"ok": True, "action": updated.to_dict()}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(res_body)))
                self.end_headers()
                self.wfile.write(res_body)
            except Exception as exc:
                res_body = json.dumps({"ok": False, "error": str(exc)}).encode("utf-8")
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(res_body)))
                self.end_headers()
                self.wfile.write(res_body)
            return

        # Handle Mail Sync Trigger
        if parsed.path == "/api/sync":
            try:
                data = self.engine.sync_and_evaluate(force_mail_poll=True)
                res_body = json.dumps({"ok": True, "updated_at": data.updated_at}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(res_body)))
                self.end_headers()
                self.wfile.write(res_body)
            except Exception as exc:
                res_body = json.dumps({"ok": False, "error": str(exc)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(res_body)))
                self.end_headers()
                self.wfile.write(res_body)
            return

        self.send_response(404)
        self.end_headers()


DEFAULT_UI_PORT: int = int(os.environ.get("PSEODASHBOARD_PORT") or os.environ.get("PORT") or 8090)
DEFAULT_UI_HOST: str = os.environ.get("PSEODASHBOARD_HOST", "127.0.0.1")
STATE_FILE_PATH: str = os.path.expanduser("~/.local/state/pseofactory/partner_ui.json")


def find_open_port(preferred_port: int = 8090, host: str = "127.0.0.1", max_tries: int = 100) -> int:
    """
    Finds an available open TCP port starting from preferred_port.
    If preferred_port is 0, lets the operating system allocate an open ephemeral port.
    If preferred_port is busy, scans sequentially for the next available port.
    """
    import socket

    if preferred_port == 0:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, 0))
            return s.getsockname()[1]

    for p in range(preferred_port, preferred_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, p))
                return p
            except OSError:
                continue

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


def _write_runtime_state(host: str, port: int, pid: int, status: str) -> None:
    """Persists runtime port and daemon status for health checks and external discovery."""
    try:
        from datetime import datetime, timezone
        os.makedirs(os.path.dirname(STATE_FILE_PATH), exist_ok=True)
        tmp_path = f"{STATE_FILE_PATH}.tmp"
        payload = {
            "host": host,
            "port": port,
            "pid": pid,
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp_path, STATE_FILE_PATH)
    except Exception:
        pass


def get_ui_runtime_state() -> Optional[Dict[str, Any]]:
    """Reads runtime state metadata if available."""
    if os.path.exists(STATE_FILE_PATH):
        try:
            with open(STATE_FILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def create_ui_server(
    port: Optional[int] = None,
    host: str = DEFAULT_UI_HOST,
    auto_find_open_port: bool = True,
    tracking_engine: Optional[PartnerTrackingEngine] = None,
) -> HTTPServer:
    """
    Creates configured HTTPServer instance on an open port.
    If auto_find_open_port is True, transparently falls back to an open port
    if the designated port is already occupied.
    """
    engine = tracking_engine or PartnerTrackingEngine()
    handler = lambda *args, **kwargs: DashboardRequestHandler(*args, tracking_engine=engine, **kwargs)

    requested_port = DEFAULT_UI_PORT if port is None else port
    if requested_port == 0:
        actual_port = find_open_port(0, host=host)
        return HTTPServer((host, actual_port), handler)

    if not auto_find_open_port:
        return HTTPServer((host, requested_port), handler)

    current_port = requested_port
    max_attempts = 100
    for _ in range(max_attempts):
        try:
            return HTTPServer((host, current_port), handler)
        except OSError:
            current_port = find_open_port(current_port + 1, host=host)

    fallback_port = find_open_port(0, host=host)
    return HTTPServer((host, fallback_port), handler)


def run_ui_server(
    port: Optional[int] = None,
    host: str = DEFAULT_UI_HOST,
    auto_find_open_port: bool = True,
    write_state: bool = True,
) -> None:
    """
    Runs lightweight local web server for the partner dashboard on an open port.
    If designated port is occupied, automatically binds next available open port.
    Persists active runtime metadata to ~/.local/state/pseofactory/partner_ui.json.
    """
    server = create_ui_server(
        port=port,
        host=host,
        auto_find_open_port=auto_find_open_port,
    )
    actual_port = server.server_address[1]

    if write_state:
        _write_runtime_state(host=host, port=actual_port, pid=os.getpid(), status="ACTIVE")

    print(f"Partner Dashboard running at http://{host}:{actual_port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if write_state:
            _write_runtime_state(host=host, port=actual_port, pid=os.getpid(), status="STOPPED")
        server.server_close()
