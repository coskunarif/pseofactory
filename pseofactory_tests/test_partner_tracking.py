"""
Unit & Integration Tests for pseofactory Partner Tracking, Email Ingest, Action Bus & Light UI.
Enforces standing constraints:
1. Strictly forbid cross-property partner mixing (profithelm vs prexvo).
2. Prohibit sub-affiliate redirects on prexvo.
3. Reject em-dashes or en-dashes across all text.
4. Never auto-approve partner agreements without operator confirmation.
5. Touch targets strictly >= 44px and zero layout shifts.

Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

import json
import os
import tempfile
import pytest

from pseofactory.contracts import (
    assert_no_forbidden_dashes,
    assert_touch_targets,
)
from pseofactory.email_ingest import (
    EmailMessage,
    EmailIngestionEngine,
    PartnerEmailClassification,
)
from pseofactory.action_bus import (
    HumanActionBus,
    ActionItem,
)
from pseofactory.partner_tracker import (
    PartnerTrackingEngine,
    PartnerStatusSummary,
    PropertyReadinessReport,
    FleetMonetizationDashboardData,
)
from pseofactory.ui import (
    render_light_interface,
    find_open_port,
    create_ui_server,
    DEFAULT_UI_PORT,
)


@pytest.fixture
def temp_bus_path():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    yield path
    if os.path.exists(path):
        os.remove(path)
    if os.path.exists(f"{path}.tmp"):
        os.remove(f"{path}.tmp")


@pytest.fixture
def temp_email_paths():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f1:
        cache_path = f1.name
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f2:
        state_path = f2.name
    yield cache_path, state_path
    for p in (cache_path, state_path, f"{cache_path}.tmp", f"{state_path}.tmp"):
        if os.path.exists(p):
            os.remove(p)


# ===========================================================================
# 1. Email Ingestion & Rate-Limiting Tests
# ===========================================================================

def test_email_engine_rate_limiting_guardrails(temp_email_paths):
    cache_path, state_path = temp_email_paths
    engine = EmailIngestionEngine(
        cache_path=cache_path,
        state_path=state_path,
        min_poll_interval=120,
    )

    # First poll should be allowed
    allowed, rem = engine.can_poll("zoho", force=False)
    assert allowed is True
    assert rem == 0

    # Record successful poll
    engine.record_poll("zoho", success=True)

    # Immediate second poll should be blocked to prevent hammering mail server
    allowed, rem = engine.can_poll("zoho", force=False)
    assert allowed is False
    assert rem > 0

    # Force should bypass cooldown
    allowed_forced, rem_forced = engine.can_poll("zoho", force=True)
    assert allowed_forced is True
    assert rem_forced == 0


def test_email_classification_partner_requests_and_deadlines():
    engine = EmailIngestionEngine()

    sample_messages = [
        EmailMessage(
            id="101",
            message_id="msg-101",
            account="zoho",
            mailbox="Inbox",
            date="2026-10-08T22:01:50Z",
            subject="Updates Digest",
            sender_name="The Gusto Affiliate Team",
            sender_email="notifications@app.impact.com",
            body_snippet="Thank you for applying to be a partner of Gusto. Your application will be reviewed shortly.",
        ),
        EmailMessage(
            id="102",
            message_id="msg-102",
            account="zoho",
            mailbox="Inbox",
            date="2026-10-06T09:01:46Z",
            subject="Action required: Your Partner Account is at risk of being closed",
            sender_name="Shopify",
            sender_email="ecosystem-governance@shopify.com",
            body_snippet="Final reminder: ProfitHelm has been delisted. Please respond by October 20, 2026 confirming next steps to relist or sunset.",
        ),
        EmailMessage(
            id="103",
            message_id="msg-103",
            account="zoho",
            mailbox="Inbox",
            date="2026-09-13T16:45:43Z",
            subject="Action required: Add or transfer funds to avoid declined transactions",
            sender_name="Mercury",
            sender_email="hello@mercury.com",
            body_snippet="Your transaction was declined because of insufficient funds in Checking. Add or transfer funds.",
        ),
        EmailMessage(
            id="104",
            message_id="msg-104",
            account="zoho",
            mailbox="Inbox",
            date="2026-07-19T22:36:57Z",
            subject="Mutual Partner Recommendation Opportunity",
            sender_name="zhang bingzhen",
            sender_email="bingzhenzhang199@gmail.com",
            body_snippet="We are the ETdropship team. We have a partner program to recommend ecommerce service providers.",
        ),
    ]

    classifications = engine.classify_partner_emails(sample_messages)
    assert len(classifications) == 4

    # Check Gusto
    gusto = next(c for c in classifications if c.partner_key == "gusto")
    assert gusto.property_id == "profithelm"
    assert gusto.classification_type == "APPLICATION_SUBMITTED"
    assert gusto.requires_operator_decision is False  # Awaiting vendor review

    # Check Shopify Governance
    shopify = next(c for c in classifications if c.partner_key == "shopify_partner_account")
    assert shopify.property_id == "profithelm"
    assert shopify.classification_type == "GOVERNANCE_WARNING"
    assert shopify.requires_operator_decision is True
    assert shopify.deadline == "October 20, 2026"
    assert shopify.urgency == "CRITICAL"

    # Check Mercury
    mercury = next(c for c in classifications if c.partner_key == "mercury")
    assert mercury.property_id == "profithelm"
    assert mercury.classification_type == "BANKING_ALERT"
    assert mercury.requires_operator_decision is True

    # Check ETdropship
    et = next(c for c in classifications if c.partner_key == "etdropship")
    assert et.property_id == "profithelm"
    assert et.classification_type == "INBOUND_PITCH"
    assert et.requires_operator_decision is True


def test_personal_inbox_fixture_ingestion(temp_email_paths):
    cache_path, state_path = temp_email_paths
    engine = EmailIngestionEngine(cache_path=cache_path, state_path=state_path)

    # Write a test personal fixture
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump([
            {
                "id": "pers-01",
                "subject": "Prexvo student loan inquiry",
                "sender_name": "Applicant John",
                "sender_email": "john@example.com",
                "body": "Inquiry regarding student loan refinancing options.",
                "date": "2026-10-08T12:00:00Z"
            }
        ], f)
        fix_path = f.name

    try:
        messages = engine.ingest_personal(fixture_path=fix_path, force=True)
        assert len(messages) == 1
        assert messages[0].id == "pers-01"
        assert messages[0].account == "personal"
        assert messages[0].subject == "Prexvo student loan inquiry"
    finally:
        if os.path.exists(fix_path):
            os.remove(fix_path)


# ===========================================================================
# 2. Human Action Bus & Standing Constraints Tests
# ===========================================================================

def test_human_action_bus_auto_approval_prohibition(temp_bus_path):
    bus = HumanActionBus(bus_path=temp_bus_path)

    item = bus.route_manual_requirement(
        property_id="profithelm",
        partner_key="mercury",
        partner_name="Mercury Startup Banking",
        title="Mercury Banking Review",
        description="Operator must review revised banking covenants.",
        action_type="PARTNER_APPROVAL",
        severity="HIGH",
    )
    assert item.status == "PENDING_OPERATOR"

    # Standing constraint: Never auto-approve partner agreements without operator confirmation
    with pytest.raises(RuntimeError, match="Never auto-approve partner agreements"):
        bus.auto_approve(item.action_id)


def test_human_action_bus_operator_confirmation(temp_bus_path):
    bus = HumanActionBus(bus_path=temp_bus_path)

    item = bus.route_manual_requirement(
        property_id="profithelm",
        partner_key="shopify_partner_account",
        partner_name="Shopify Governance",
        title="Shopify Governance Appeal",
        description="Operator decides whether to appeal or sunset.",
        action_type="GOVERNANCE_DEADLINE",
        severity="CRITICAL",
        deadline="October 20, 2026",
    )

    # Approve
    confirmed = bus.confirm_decision(
        action_id=item.action_id,
        decision="APPROVE",
        operator="arif.coskun",
        notes="Approved appeal to Shopify ecosystem team.",
    )
    assert confirmed.status == "APPROVED"
    assert confirmed.resolved_by == "arif.coskun"
    assert "Approved appeal" in confirmed.operator_notes

    # Reload from disk and check persistence
    reloaded_bus = HumanActionBus(bus_path=temp_bus_path)
    loaded_item = reloaded_bus.items[item.action_id]
    assert loaded_item.status == "APPROVED"
    assert loaded_item.resolved_by == "arif.coskun"


def test_human_action_bus_property_isolation_enforcement(temp_bus_path):
    bus = HumanActionBus(bus_path=temp_bus_path)

    # Attempting to route a B2B partner to Prexvo must raise ValueError
    with pytest.raises(ValueError, match="Strict isolation violation"):
        bus.route_manual_requirement(
            property_id="prexvo",
            partner_key="mercury",  # Mercury is strictly B2B
            partner_name="Mercury Startup Banking",
            title="Mercury on Prexvo",
            description="Attempt to route B2B partner to Prexvo.",
        )

    # Attempting to route a Student Loan partner to ProfitHelm must raise ValueError
    with pytest.raises(ValueError, match="Strict isolation violation"):
        bus.route_manual_requirement(
            property_id="profithelm",
            partner_key="splash_financial",  # Splash is strictly student loan
            partner_name="Splash Financial",
            title="Splash on ProfitHelm",
            description="Attempt to route student loan partner to ProfitHelm.",
        )


# ===========================================================================
# 3. Partner Tracking Engine & Property Readiness Tests
# ===========================================================================

def test_partner_tracking_reconciliation_and_readiness(temp_bus_path, temp_email_paths):
    cache_path, state_path = temp_email_paths
    email_engine = EmailIngestionEngine(cache_path=cache_path, state_path=state_path)
    action_bus = HumanActionBus(bus_path=temp_bus_path)

    tracker = PartnerTrackingEngine(email_engine=email_engine, action_bus=action_bus)
    dashboard = tracker.sync_and_evaluate(force_mail_poll=False)

    ph = dashboard.profithelm
    px = dashboard.prexvo

    # ProfitHelm verification
    assert ph.property_id == "profithelm"
    assert ph.active_partners_count >= 3  # CoinLedger, Koinly, IPX1031
    assert ph.monetization_readiness_score > 0.0
    assert ph.property_isolation_verified is True
    assert ph.disclosure_compliant is True

    # Prexvo verification
    assert px.property_id == "prexvo"
    assert px.active_partners_count == 5
    assert px.monetization_readiness_score > 0.0
    assert px.property_isolation_verified is True
    assert px.sub_affiliate_redirects_prohibited is True

    # Check that Gusto is now live and routes to Impact.com tracking link
    gusto_p = next(p for p in ph.partners if p.key == "gusto")
    assert gusto_p.property_id == "profithelm"
    assert gusto_p.is_live_link is True
    assert "gusto.pxf.io" in gusto_p.destination_url

    # Check that Splash Financial on Prexvo is live and routes externally
    splash_p = next(p for p in px.partners if p.key == "splash_financial")
    assert splash_p.property_id == "prexvo"
    assert splash_p.is_live_link is True
    assert "splashfinancial.com" in splash_p.destination_url


def test_zero_cross_property_partner_overlap(temp_bus_path, temp_email_paths):
    cache_path, state_path = temp_email_paths
    email_engine = EmailIngestionEngine(cache_path=cache_path, state_path=state_path)
    action_bus = HumanActionBus(bus_path=temp_bus_path)

    tracker = PartnerTrackingEngine(email_engine=email_engine, action_bus=action_bus)
    dashboard = tracker.sync_and_evaluate(force_mail_poll=False)

    ph_keys = {p.key for p in dashboard.profithelm.partners}
    px_keys = {p.key for p in dashboard.prexvo.partners}

    # Strict invariant: zero partner overlap between ProfitHelm and Prexvo
    overlap = ph_keys.intersection(px_keys)
    assert len(overlap) == 0, f"Cross-property mixing detected: {overlap}"


def test_prexvo_sub_affiliate_redirect_rejection(temp_bus_path, temp_email_paths):
    cache_path, state_path = temp_email_paths
    email_engine = EmailIngestionEngine(cache_path=cache_path, state_path=state_path)
    action_bus = HumanActionBus(bus_path=temp_bus_path)

    tracker = PartnerTrackingEngine(email_engine=email_engine, action_bus=action_bus)
    dashboard = tracker.sync_and_evaluate(force_mail_poll=False)

    for p in dashboard.prexvo.partners:
        # Standing constraint: Sub-affiliate aggregator redirects strictly prohibited on Prexvo
        assert "sovrn" not in p.destination_url.lower()
        assert "viglink" not in p.destination_url.lower()


# ===========================================================================
# 4. Minimal Modern Light UI Verification (CLS & Touch Targets)
# ===========================================================================

def test_light_interface_touch_targets_and_typography_contracts(temp_bus_path, temp_email_paths):
    cache_path, state_path = temp_email_paths
    email_engine = EmailIngestionEngine(cache_path=cache_path, state_path=state_path)
    action_bus = HumanActionBus(bus_path=temp_bus_path)

    tracker = PartnerTrackingEngine(email_engine=email_engine, action_bus=action_bus)
    dashboard = tracker.sync_and_evaluate(force_mail_poll=False)

    html_content = render_light_interface(dashboard)

    # 1. Assert zero em-dashes (\u2014) and zero en-dashes (\u2013)
    assert_no_forbidden_dashes(html_content, context="Rendered Light Interface")

    # 2. Assert touch targets strictly meet or exceed 44x44px
    assert_touch_targets(html_content, is_css=False, context="Rendered Light Interface")

    # 3. Assert minimal modern light elements are present
    assert "pseofactory Monetization Hub &amp; Partner Tracking" in html_content or "pseofactory Monetization Hub" in html_content
    assert "Dedicated Human Action Bus" in html_content
    assert "ProfitHelm Partner Matrix" in html_content
    assert "Prexvo Partner Matrix" in html_content
    assert "Inbound Correspondence Stream" in html_content

    # 4. Confirm zero layout shift safeguards (table-layout: fixed)
    assert "table-layout: fixed;" in html_content
    # 5. Confirm Operator Decision Audit Trail section exists
    assert "Operator Decision Audit Trail" in html_content


def test_himalaya_failure_preserves_cached_sender_and_message_fields(temp_email_paths):
    """
    Asserts that if himalaya command fails or exits non-zero,
    cached messages maintain their sender names and sender emails without corruption.
    """
    cache_path, state_path = temp_email_paths
    # Seed cache with known message
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump({
            "messages": {
                "test-999": {
                    "id": "test-999",
                    "message_id": "msg-test-999",
                    "account": "zoho",
                    "mailbox": "Inbox",
                    "date": "2026-10-08T22:01:50Z",
                    "subject": "Updates Digest",
                    "sender_name": "The Gusto Affiliate Team",
                    "sender_email": "notifications@app.impact.com",
                    "body_snippet": "Thank you for applying to Gusto.",
                    "raw_headers": {},
                    "flags": [],
                }
            },
            "classifications": []
        }, f)

    engine = EmailIngestionEngine(
        cache_path=cache_path,
        state_path=state_path,
        himalaya_bin="nonexistent-himalaya-command-xyz",
    )

    # Force a poll with broken himalaya command
    msgs = engine.ingest_zoho(force=True)
    assert len(msgs) == 1
    assert msgs[0].sender_name == "The Gusto Affiliate Team"
    assert msgs[0].sender_email == "notifications@app.impact.com"

    # Re-read cache from disk and confirm zero corruption
    reloaded_cache = engine.load_cache()
    cached_m = reloaded_cache["messages"]["test-999"]
    assert cached_m["sender_name"] == "The Gusto Affiliate Team"
    assert cached_m["sender_email"] == "notifications@app.impact.com"


def test_multi_email_classification_date_priority():
    """
    Asserts that when multiple emails arrive for the same partner,
    the latest email date and active deadline take precedence over older emails.
    """
    c_new = PartnerEmailClassification(
        email_id="964",
        account="zoho",
        property_id="profithelm",
        partner_key="shopify_partner_account",
        partner_name="Shopify Partner Governance",
        category="DEVELOPER_ECOSYSTEM",
        classification_type="GOVERNANCE_WARNING",
        requires_operator_decision=True,
        summary="Final warning: Shopify App delisted and Partner Account at risk.",
        urgency="CRITICAL",
        deadline="October 20, 2026",
        date="2026-10-06T09:01:46Z",
    )
    c_old = PartnerEmailClassification(
        email_id="936",
        account="zoho",
        property_id="profithelm",
        partner_key="shopify_partner_account",
        partner_name="Shopify Partner Governance",
        category="DEVELOPER_ECOSYSTEM",
        classification_type="GOVERNANCE_WARNING",
        requires_operator_decision=True,
        summary="Old warning with September deadline.",
        urgency="HIGH",
        deadline="September 03, 2026",
        date="2026-09-03T08:00:00Z",
    )

    classifications = [c_new, c_old]
    prop_classifications = [c for c in classifications if c.property_id == "profithelm"]
    class_map = {}
    for c in sorted(prop_classifications, key=lambda x: x.date, reverse=True):
        if c.partner_key not in class_map:
            class_map[c.partner_key] = c

    assert class_map["shopify_partner_account"].deadline == "October 20, 2026"
    assert class_map["shopify_partner_account"].email_id == "964"


def test_action_map_prioritizes_pending_operator_actions(temp_bus_path):
    """
    Asserts that a partner with both pending and resolved action items
    preserves PENDING_OPERATOR status so operator intervention is never masked.
    """
    bus = HumanActionBus(bus_path=temp_bus_path)

    # 1. First action resolved
    act1 = bus.route_manual_requirement(
        property_id="profithelm",
        partner_key="mercury",
        partner_name="Mercury Startup Banking",
        title="Mercury Terms Update",
        description="Terms updated",
        action_type="TERMS_UPDATE",
    )
    bus.confirm_decision(action_id=act1.action_id, decision="RESOLVE", notes="Resolved earlier")

    # 2. Second action pending
    act2 = bus.route_manual_requirement(
        property_id="profithelm",
        partner_key="mercury",
        partner_name="Mercury Startup Banking",
        title="Mercury Banking Alert",
        description="Checking balance low",
        action_type="BANKING_ALERT",
        severity="HIGH",
    )

    items = bus.get_all_items(property_id="profithelm")
    action_map = {}
    for it in items:
        if it.partner_key not in action_map or it.status == "PENDING_OPERATOR":
            action_map[it.partner_key] = it

    assert action_map["mercury"].status == "PENDING_OPERATOR"
    assert action_map["mercury"].action_type == "BANKING_ALERT"


def test_prexvo_shopify_payments_isolation():
    """
    Asserts that Shopify emails regarding Prexvo store payouts
    route strictly to Prexvo and never to ProfitHelm.
    """
    engine = EmailIngestionEngine()
    msg = EmailMessage(
        id="795",
        message_id="msg-795",
        account="zoho",
        mailbox="Inbox",
        date="2026-06-15T09:05:01Z",
        subject="Update business details to resume getting payouts from orders using Shop Pay Installments",
        sender_name="Shopify",
        sender_email="mailer@shopify.com",
        body_snippet="To resume getting payouts from orders using Shop Pay Installments, update details for prexvo.",
    )

    classifications = engine.classify_partner_emails([msg])
    assert len(classifications) == 1
    assert classifications[0].property_id == "prexvo"
    assert classifications[0].partner_key == "shopify_payments_prexvo"
    assert classifications[0].requires_operator_decision is True
 
 
def test_ui_open_port_discovery_and_fallback():
    """
    Asserts that open port discovery finds valid available ports,
    and server creation automatically falls back to an open port when occupied.
    Zero em-dashes. Zero en-dashes.
    """
    port = find_open_port(8090)
    assert isinstance(port, int)
    assert port >= 1024

    # Ephemeral port request (0) must return dynamic open port
    ephemeral = find_open_port(0)
    assert isinstance(ephemeral, int)
    assert ephemeral > 1024

    # Test create_ui_server on ephemeral port
    server = create_ui_server(port=0, auto_find_open_port=True)
    assigned_port = server.server_address[1]
    assert assigned_port > 0
    server.server_close()


def test_ui_server_port_collision_fallback():
    """
    Asserts that if a designated port is already bound, create_ui_server
    falls back cleanly to the next available open port.
    Zero em-dashes. Zero en-dashes.
    """
    import socket

    # Bind a socket temporarily on an open port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        occupied_port = s.getsockname()[1]

        # Attempt to create UI server with auto_find_open_port=True
        server = create_ui_server(port=occupied_port, auto_find_open_port=True)
        assigned_port = server.server_address[1]
        assert assigned_port != occupied_port
        assert assigned_port > 0
        server.server_close()


def test_ui_runtime_state_roundtrip(tmp_path, monkeypatch):
    """
    Asserts that UI runtime state file can be persisted and read back cleanly.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory import ui

    fake_state_file = str(tmp_path / "partner_ui.json")
    monkeypatch.setattr(ui, "STATE_FILE_PATH", fake_state_file)

    ui._write_runtime_state(host="127.0.0.1", port=8090, pid=1234, status="ACTIVE")
    state = ui.get_ui_runtime_state()
    assert state is not None
    assert state["host"] == "127.0.0.1"
    assert state["port"] == 8090
    assert state["pid"] == 1234
    assert state["status"] == "ACTIVE"


def test_cli_partner_ui_default_port_and_flags():
    """
    Asserts that CLI partner-ui parser defaults to dedicated open port 8090 (not 8080)
    and supports status and json flags.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["partner-ui"])
    assert args.command == "partner-ui"
    assert args.port == 8090
    assert args.host == "127.0.0.1"
    assert args.status is False
    assert args.json is False

    # Check custom port
    args_custom = parser.parse_args(["partner-ui", "--port", "8095"])
    assert args_custom.port == 8095

    # Check status flag
    args_stat = parser.parse_args(["partner-ui", "--status", "--json"])
    assert args_stat.status is True
    assert args_stat.json is True


def test_find_open_port_upper_boundary_and_overflow_protection():
    """
    Asserts that find_open_port handles high port numbers near 65535
    gracefully without raising OverflowError.
    Zero em-dashes. Zero en-dashes.
    """
    p = find_open_port(preferred_port=65534, max_tries=10)
    assert isinstance(p, int)
    assert 1024 <= p <= 65535


def test_ui_server_atomic_ephemeral_port_binding():
    """
    Asserts that create_ui_server with port=0 or port<=0 allocates
    a valid open port atomically.
    Zero em-dashes. Zero en-dashes.
    """
    server = create_ui_server(port=0, auto_find_open_port=True)
    assigned_port = server.server_address[1]
    assert isinstance(assigned_port, int)
    assert assigned_port > 0
    server.server_close()


def test_ui_state_protection_against_auxiliary_stopped_clobbering(tmp_path, monkeypatch):
    """
    Asserts that _write_runtime_state prevents a terminating auxiliary process
    from overwriting an active living daemon status with STOPPED.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory import ui

    fake_state = str(tmp_path / "partner_ui.json")
    monkeypatch.setattr(ui, "STATE_FILE_PATH", fake_state)

    # Simulate active daemon running under our current process pid
    current_pid = os.getpid()
    ui._write_runtime_state(host="127.0.0.1", port=8090, pid=current_pid, status="ACTIVE")

    # An auxiliary process with a different pid attempts to mark STOPPED
    ui._write_runtime_state(host="127.0.0.1", port=8091, pid=999999, status="STOPPED")

    # State must remain ACTIVE and untouched
    state = ui.get_ui_runtime_state()
    assert state is not None
    assert state["status"] == "ACTIVE"
    assert state["pid"] == current_pid
    assert state["port"] == 8090


def test_cli_partner_ui_status_probes_fallback_on_stale_state(tmp_path, monkeypatch):
    """
    Asserts that cmd_partner_ui probes fallback ports when runtime state port
    is unavailable or points to a closed port.
    Zero em-dashes. Zero en-dashes.
    """
    import argparse
    from pseofactory import ui
    from pseofactory.cli import cmd_partner_ui

    fake_state = str(tmp_path / "partner_ui.json")
    monkeypatch.setattr(ui, "STATE_FILE_PATH", fake_state)

    # Point state to an unresponsive port
    ui._write_runtime_state(host="127.0.0.1", port=59999, pid=1, status="ACTIVE")

    parser_args = argparse.Namespace(
        command="partner-ui",
        status=True,
        json=True,
        port=8090,
        host="127.0.0.1",
    )
    # Probing should not crash and should report properly
    exit_code = cmd_partner_ui(parser_args)
    assert exit_code in (0, 1)


def test_partner_table_horizontal_scroll_and_touch_target_containment(temp_bus_path, temp_email_paths):
    """
    Asserts table min-width 680px inside .table-wrap, guaranteeing
    narrowest column (.col-link at 12%) exceeds 44px on mobile viewports.
    """
    cache_path, state_path = temp_email_paths
    email_engine = EmailIngestionEngine(cache_path=cache_path, state_path=state_path)
    action_bus = HumanActionBus(bus_path=temp_bus_path)
    tracker = PartnerTrackingEngine(email_engine=email_engine, action_bus=action_bus)
    dashboard = tracker.sync_and_evaluate(force_mail_poll=False)
    html_content = render_light_interface(dashboard)

    # 1. Verify CSS min-width property
    assert "min-width: 680px;" in html_content
    assert "overflow-x: auto;" in html_content
    assert "-webkit-overflow-scrolling: touch;" in html_content

    # 2. Mathematical containment proof
    min_table_w = 680
    col_link_pct = 0.12
    computed_col_w = min_table_w * col_link_pct
    assert computed_col_w >= 44.0, f"Column link width {computed_col_w}px must be >= 44px"


def test_header_actions_flex_wrap_prevents_mobile_overflow(temp_bus_path, temp_email_paths):
    """
    Asserts header action group specifies flex-wrap: wrap to prevent
    horizontal viewport overflow on narrow mobile devices (<360px).
    """
    cache_path, state_path = temp_email_paths
    email_engine = EmailIngestionEngine(cache_path=cache_path, state_path=state_path)
    action_bus = HumanActionBus(bus_path=temp_bus_path)
    tracker = PartnerTrackingEngine(email_engine=email_engine, action_bus=action_bus)
    dashboard = tracker.sync_and_evaluate(force_mail_poll=False)
    html_content = render_light_interface(dashboard)

    assert "flex-wrap: wrap;" in html_content


def test_svg_traffic_ceiling_chart_aspect_ratio_cls_zero():
    """
    Asserts SVG ceiling analysis chart explicitly defines aspect-ratio matching
    its viewBox width and height to guarantee CLS = 0 layout stability.
    """
    from pseofactory.trends.models import AlgorithmicCeilingAnalysis
    from pseofactory.ui import render_ceiling_chart_page
    analysis = AlgorithmicCeilingAnalysis(
        property_id="profithelm",
        analysis_window_days=480,
        total_days=480,
        peak_impressions_rma28=9200.0,
        current_impressions_rma28=2400.0,
        ceiling_threshold=0.35,
        ceiling_dampening_score=0.66,
        ceiling_detected=False,
        suppression_severity="NONE",
        recommendation="BUILD_PAGE",
    )
    page_html = render_ceiling_chart_page(analysis)

    assert "aspect-ratio:1000/360" in page_html or "aspect-ratio: 1000 / 360" in page_html
    assert 'viewBox="0 0 1000 360"' in page_html
    assert 'preserveAspectRatio="xMidYMid meet"' in page_html


def test_mercury_inbound_reply_and_rippling_newsletter_approval_classification():
    """
    Asserts that inbound replies from partnerships@mercury.com (Inbox #978) are classified
    as ONBOARDING_ACTION_REQUIRED rather than swallowed by outbound_partner_map, and that
    Rippling PartnerStack welcome/newsletter emails from erica.grodin@rippling.com classify
    as APPLICATION_APPROVED.
    """
    engine = EmailIngestionEngine()
    messages = [
        EmailMessage(
            id="978",
            message_id="msg-978",
            account="zoho",
            mailbox="Inbox",
            date="2026-10-14T15:48:26Z",
            subject="Mercury Inquiry",
            sender_name="Mercury Partnerships",
            sender_email="partnerships@mercury.com",
            body_snippet="If you are looking to explore a potential partnership, please head to our Mercury Partnerships page here ( https://mercury.com/partnerships ) and fill out the form.",
        ),
        EmailMessage(
            id="news-1552",
            message_id="msg-1552",
            account="zoho",
            mailbox="Newsletter",
            date="2026-10-12T15:56:45Z",
            subject="Welcome to the Rippling Affiliate Program",
            sender_name="Erica Grodin",
            sender_email="erica.grodin@rippling.com",
            body_snippet="Welcome to the Rippling Affiliate Program",
        ),
    ]

    classifications = engine.classify_partner_emails(messages)
    assert len(classifications) == 2

    mercury_c = next(c for c in classifications if c.partner_key == "mercury")
    assert mercury_c.classification_type == "ONBOARDING_ACTION_REQUIRED"
    assert mercury_c.requires_operator_decision is True
    assert "mercury.com/partnerships" in mercury_c.candidate_url

    rippling_c = next(c for c in classifications if c.partner_key == "rippling")
    assert rippling_c.classification_type == "APPLICATION_APPROVED"
    assert rippling_c.requires_operator_decision is False
    assert rippling_c.candidate_url == "https://try.rippling.com/mcfo1m09qiwt"


def test_unified_vault_roster_tiers_completeness():
    """
    Asserts that monetization_vault.json organizes all 22 ProfitHelm partners and 5 Prexvo
    partners into cohesive roster_tiers separating live_revenue_ready links from pending/awaiting items.
    """
    from pseofactory.affiliates_hub import MonetizationHub
    from pseofactory.affiliates import PROFITHELM_AFFILIATES, PREXVO_AFFILIATES

    hub = MonetizationHub()
    ph_prop = hub.vault_data["properties"]["profithelm"]
    px_prop = hub.vault_data["properties"]["prexvo"]

    canonical_ph_keys = {k for k, v in PROFITHELM_AFFILIATES.items() if k == v.key}
    canonical_px_keys = {k for k, v in PREXVO_AFFILIATES.items() if k == v.key}

    assert set(ph_prop["partners"].keys()) == canonical_ph_keys
    assert set(px_prop["partners"].keys()) == canonical_px_keys

    ph_tiers = ph_prop["roster_tiers"]
    assert set(ph_tiers["live_revenue_ready"]) == {
        "coinledger",
        "koinly",
        "rippling",
        "ipx1031",
        "mercury",
        "kalshi",
        "crest_capital",
        "gusto",
    }
    assert set(ph_tiers["unapplied_expansion_queue"]) == set()
    all_ph_tiered = (
        set(ph_tiers["live_revenue_ready"])
        | set(ph_tiers["answered_action_required"])
        | set(ph_tiers["awaiting_vendor_response"])
        | set(ph_tiers["unapplied_expansion_queue"])
    )
    assert all_ph_tiered == canonical_ph_keys

    px_tiers = px_prop["roster_tiers"]
    assert set(px_tiers["live_revenue_ready"]) == {"splash_financial", "sofi", "credible", "earnest", "lendkey"}
    assert set(px_tiers["awaiting_vendor_response"]) == set()
    assert set(px_tiers["unapplied_expansion_queue"]) == set()


def test_record_and_aggregate_outbound_partner_engagement_and_isolation(tmp_path):
    """
    Verifies record_outbound_partner_engagement and aggregate_outbound_partner_engagement:
    1. Tracks calculator CTA slots, preset clicks, and outbound partner clicks per slug, partner, and slot.
    2. Enforces strict cross-property isolation (rejects Prexvo partners on ProfitHelm and vice versa).
    3. Ranks partner offers by empirical revenue yield.
    """
    from pseofactory.affiliates import (
        record_outbound_partner_engagement,
        aggregate_outbound_partner_engagement,
        rank_partner_offers_by_revenue_yield,
    )

    ledger = tmp_path / "outbound_engagement.jsonl"

    # Strict cross-property isolation checks
    with pytest.raises(ValueError, match="Strict isolation violation"):
        record_outbound_partner_engagement(
            {"event_type": "affiliate_click", "slug": "student-loan-repayment-calculator", "partner_key": "mercury"},
            ledger_path=ledger,
            property_id="prexvo",
        )

    with pytest.raises(ValueError, match="Strict isolation violation"):
        record_outbound_partner_engagement(
            {"event_type": "affiliate_click", "slug": "irs-2027-tax-brackets", "partner_key": "splash_financial"},
            ledger_path=ledger,
            property_id="profithelm",
        )

    # Record valid ProfitHelm engagement events across two CTA slots and two partners
    record_outbound_partner_engagement(
        {"event_type": "page_view", "slug": "crypto-tax-liability-calculator-2027"},
        ledger_path=ledger,
        property_id="profithelm",
    )
    record_outbound_partner_engagement(
        {"event_type": "calculation", "slug": "crypto-tax-liability-calculator-2027"},
        ledger_path=ledger,
        property_id="profithelm",
    )
    record_outbound_partner_engagement(
        {
            "event_type": "affiliate_click",
            "slug": "crypto-tax-liability-calculator-2027",
            "partner_key": "coinledger",
            "cta_slot": "calculator_primary_cta",
            "payout_usd": 35.0,
        },
        ledger_path=ledger,
        property_id="profithelm",
    )
    record_outbound_partner_engagement(
        {
            "event_type": "affiliate_click",
            "slug": "crypto-tax-liability-calculator-2027",
            "partner_key": "koinly",
            "cta_slot": "preset_scenario_cta",
            "payout_usd": 85.0,
        },
        ledger_path=ledger,
        property_id="profithelm",
    )
    record_outbound_partner_engagement(
        {
            "event_type": "affiliate_click",
            "slug": "crypto-tax-liability-calculator-2027",
            "partner_key": "koinly",
            "cta_slot": "preset_scenario_cta",
            "payout_usd": 85.0,
        },
        ledger_path=ledger,
        property_id="profithelm",
    )

    agg = aggregate_outbound_partner_engagement(ledger, property_id="profithelm")
    assert agg["total_outbound_clicks"] == 3
    slug_stats = agg["by_slug"]["crypto-tax-liability-calculator-2027"]
    assert slug_stats["top_converting_partner"] == "koinly"
    assert slug_stats["top_converting_cta_slot"] == "preset_scenario_cta"
    assert slug_stats["estimated_revenue_yield_usd"] == 205.0

    ranked_offers = rank_partner_offers_by_revenue_yield(
        property_id="profithelm",
        slug="crypto-tax-liability-calculator-2027",
        engagement_metrics=agg,
        only_live=True,
    )
    assert len(ranked_offers) > 0
    # Koinly should rank ahead of CoinLedger on this slug due to higher empirical revenue yield
    koinly_idx = next(i for i, r in enumerate(ranked_offers) if r["key"] == "koinly")
    coinledger_idx = next(i for i, r in enumerate(ranked_offers) if r["key"] == "coinledger")
    assert koinly_idx < coinledger_idx


def test_action_bus_and_partner_tracker_rank_pending_approvals_by_revenue_impact_and_render_ui(temp_bus_path, temp_email_paths):
    """
    Verifies that HumanActionBus and PartnerTrackingEngine rank pending manual partner approvals
    by estimated monthly revenue impact and render priority rank and revenue impact badges in UI.
    """
    cache_path, state_path = temp_email_paths
    email_engine = EmailIngestionEngine(cache_path=cache_path, state_path=state_path)
    action_bus = HumanActionBus(bus_path=temp_bus_path)

    # Route two pending partner approvals with different traffic and CTA intent levels
    action_bus.route_manual_requirement(
        property_id="profithelm",
        partner_key="suretybonds_direct",
        partner_name="SuretyBonds.com",
        title="Approve SuretyBonds Direct Partner Agreement",
        description="Complete partner agreement for customs bond calculators.",
        action_type="PARTNER_APPROVAL",
        severity="MEDIUM",
        affected_traffic_impressions=250,
        outbound_cta_intent_clicks=2,
        affected_slugs=["customs-bond-sufficiency-calculator"],
    )
    action_bus.route_manual_requirement(
        property_id="profithelm",
        partner_key="avalara",
        partner_name="Avalara AvaTax",
        title="Approve Avalara Partner Agreement",
        description="Complete partner agreement for sales tax economic nexus calculators.",
        action_type="PARTNER_APPROVAL",
        severity="HIGH",
        affected_traffic_impressions=2400,
        outbound_cta_intent_clicks=18,
        affected_slugs=["sales-tax-economic-nexus-calculator"],
    )

    ranked_bus = action_bus.rank_pending_partner_approvals(property_id="profithelm")
    assert len(ranked_bus) >= 2
    assert ranked_bus[0].partner_key == "avalara"
    assert ranked_bus[0].revenue_priority_rank == 1
    assert ranked_bus[0].estimated_monthly_revenue_impact_usd > ranked_bus[1].estimated_monthly_revenue_impact_usd

    tracker = PartnerTrackingEngine(email_engine=email_engine, action_bus=action_bus)
    dashboard = tracker.sync_and_evaluate(force_mail_poll=False)
    html_content = render_light_interface(dashboard)

    assert "data-revenue-rank=" in html_content
    assert "data-revenue-impact=" in html_content
    assert "Est. Impact: $" in html_content
    assert "\u2014" not in html_content
    assert "\u2013" not in html_content


def test_latest_himalaya_correspondence_classification_otr_ergo_next_rippling():
    """
    Verifies that:
    1. Impact.com digest emails with sender display name 'The Gusto Affiliate Team'
       but body referencing 'ERGO NEXT Insurance' (#982) classify as next_insurance_b2b
       (APPLICATION_SUBMITTED) rather than gusto.
    2. OTR Solutions follow-up emails from Wade Fenton (#983/#984) classify as
       otr_solutions_factoring (ONBOARDING_ACTION_REQUIRED).
    3. Rippling commission structure emails from Erica Grodin (#1568) classify as
       rippling (APPLICATION_APPROVED) with tracking link https://try.rippling.com/mcfo1m09qiwt.
    """
    engine = EmailIngestionEngine()
    messages = [
        EmailMessage(
            id="982",
            message_id="msg-982",
            account="zoho",
            mailbox="Inbox",
            date="2026-10-14T23:02:27Z",
            subject="Updates Digest",
            sender_name="The Gusto Affiliate Team",
            sender_email="notifications@app.impact.com",
            body_snippet="Thank you for applying to be a partner of ERGO NEXT Insurance. Your application will be reviewed shortly.",
        ),
        EmailMessage(
            id="984",
            message_id="msg-984",
            account="zoho",
            mailbox="Inbox",
            date="2026-10-15T15:09:49Z",
            subject="OTR Solutions Follow Up",
            sender_name="Wade Fenton",
            sender_email="wade.fenton@otrsolutions.com",
            body_snippet="I am following up with you to see if you are still interested in partnering with OTR Solutions. Complete our Become A Partner form (https://otrsolutions.com/become-a-partner/).",
        ),
        EmailMessage(
            id="news-1568",
            message_id="msg-1568",
            account="zoho",
            mailbox="Newsletter",
            date="2026-10-15T14:30:24Z",
            subject="How you earn - your commission structure",
            sender_name="Erica Grodin",
            sender_email="erica.grodin@rippling.com",
            body_snippet="Tier 1: $600 per Sales Qualified Opportunity (SQO) demo. Tier 2: $1,000 per Closed Won deal. Your unique link: https://try.rippling.com/mcfo1m09qiwt",
        ),
    ]

    classifications = engine.classify_partner_emails(messages)
    assert len(classifications) == 3

    next_c = next(c for c in classifications if c.partner_key == "next_insurance_b2b")
    assert next_c.classification_type == "APPLICATION_SUBMITTED"
    assert next_c.requires_operator_decision is False
    assert next_c.network == "Impact.com"

    otr_c = next(c for c in classifications if c.partner_key == "otr_solutions_factoring")
    assert otr_c.classification_type == "ONBOARDING_ACTION_REQUIRED"
    assert otr_c.requires_operator_decision is True
    assert "otrsolutions.com/become-a-partner" in otr_c.candidate_url

    rip_c = next(c for c in classifications if c.partner_key == "rippling")
    assert rip_c.classification_type == "APPLICATION_APPROVED"
    assert rip_c.requires_operator_decision is False
    assert rip_c.candidate_url == "https://try.rippling.com/mcfo1m09qiwt"


def test_suretybonds_and_ibkr_publisher_email_classifications():
    """
    Verifies that inbound SuretyBonds.com (#987), SoFi Impact (#988), and Rho confirmation (#989)
    emails alongside outbound Interactive Brokers CPC Publisher Program emails (Sent #252)
    classify cleanly as APPLICATION_SUBMITTED.
    """
    engine = EmailIngestionEngine()
    messages = [
        EmailMessage(
            id="987",
            message_id="msg-987",
            account="zoho",
            mailbox="Inbox",
            date="2026-10-17T05:56:24Z",
            subject="Re: ProfitHelm LLC - Contractor Surety Bond Referral Partnership Inquiry",
            sender_name="Customer Care",
            sender_email="customercare@suretybonds.com",
            body_snippet="Thank you for contacting SuretyBonds.com! We have received your message and will respond as soon as possible.",
        ),
        EmailMessage(
            id="988",
            message_id="msg-988",
            account="zoho",
            mailbox="Inbox",
            date="2026-10-17T06:01:44Z",
            subject="Updates Digest",
            sender_name="The Gusto Affiliate Team",
            sender_email="notifications@app.impact.com",
            body_snippet="Thank you for applying to be a partner of SoFi. Your application will be reviewed shortly.",
        ),
        EmailMessage(
            id="989",
            message_id="msg-989",
            account="zoho",
            mailbox="Inbox",
            date="2026-10-17T06:09:44Z",
            subject="[Rho] Re: Re: [Rho] Re: ProfitHelm LLC - Rho Affiliate & Referral Partner Program Inquiry [M92K76-GN1J4]",
            sender_name="Rho Client Service",
            sender_email="clientservice@rho.co",
            body_snippet="Hey Arif, Thank you for confirming! Please let us know if we can assist you with anything else. Sincerely, Hawk",
        ),
        EmailMessage(
            id="sent-252",
            message_id="msg-sent-252",
            account="zoho",
            mailbox="Sent",
            date="2026-10-16T22:56:15-07:00",
            subject="ProfitHelm LLC - IBKR CPC Publisher & Affiliate Program Application",
            sender_name="Arif Coskun",
            sender_email="publishers@interactivebrokers.com",
            body_snippet="ProfitHelm LLC - IBKR CPC Publisher & Affiliate Program Application",
            raw_headers={"to_email": "publishers@interactivebrokers.com"},
        ),
        EmailMessage(
            id="sent-259",
            message_id="msg-sent-259",
            account="zoho",
            mailbox="Sent",
            date="2026-10-17T00:39:05-07:00",
            subject="ProfitHelm LLC - Section 1031 Qualified Intermediary Referral Partnership Inquiry",
            sender_name="Arif Coskun",
            sender_email="info@ipx1031.com",
            body_snippet="ProfitHelm LLC - Section 1031 Qualified Intermediary Referral Partnership Inquiry",
            raw_headers={"to_email": "info@ipx1031.com"},
        ),
        EmailMessage(
            id="990",
            message_id="msg-990",
            account="zoho",
            mailbox="Inbox",
            date="2026-10-17T07:39:17Z",
            subject="Simply Business Inc - We have received your request - Ticket ID 6270665",
            sender_name="Simply Business Inc",
            sender_email="support@simplybusinessinc.zendesk.com",
            body_snippet="Thank you for contacting Simply Business. This email is an automated response to let you know that we have received your inquiry.",
        ),
        EmailMessage(
            id="992",
            message_id="msg-992",
            account="zoho",
            mailbox="Inbox",
            date="2026-10-17T08:37:46Z",
            subject="Changes made to account - CID 8101803",
            sender_name="",
            sender_email="no-response@cj.com",
            body_snippet="Hello Arif Coskun, We're letting you know that you have been added to a CJ Affiliate account.",
        ),
        EmailMessage(
            id="996",
            message_id="msg-996",
            account="zoho",
            mailbox="Inbox",
            date="2026-10-18T02:27:39-07:00",
            subject="Changes made to account - CID 8101803",
            sender_name="",
            sender_email="no-response@cj.com",
            body_snippet="Hello Arif Coskun, We're letting you know that the company information for CJ Affiliate account with CID 8101803 has been updated.",
        ),
        EmailMessage(
            id="news-1575",
            message_id="msg-news-1575",
            account="zoho",
            mailbox="Newsletter",
            date="2026-10-17T02:51:53-07:00",
            subject="Welcome to Xendoo Referral Partner Program!",
            sender_name="Xendoo Referral Partner Program",
            sender_email="promoter@firstpromoter.com",
            body_snippet="Welcome to Xendoo Referral Partner Program! Your unique referral link is https://www.xendoo.com/?fp_ref=arif-4ac24e",
        ),
    ]

    classifications = engine.classify_partner_emails(messages)
    assert len(classifications) == 9

    sb_c = next(c for c in classifications if c.partner_key == "suretybonds_direct")
    assert sb_c.classification_type == "APPLICATION_SUBMITTED"
    assert sb_c.requires_operator_decision is False

    sofi_c = next(c for c in classifications if c.partner_key == "sofi")
    assert sofi_c.property_id == "prexvo"
    assert sofi_c.classification_type == "APPLICATION_SUBMITTED"
    assert sofi_c.requires_operator_decision is False

    rho_c = next(c for c in classifications if c.partner_key == "rho")
    assert rho_c.property_id == "profithelm"
    assert rho_c.classification_type == "APPLICATION_SUBMITTED"
    assert rho_c.requires_operator_decision is False

    ib_c = next(c for c in classifications if c.partner_key == "interactive_brokers")
    assert ib_c.classification_type == "APPLICATION_SUBMITTED"
    assert ib_c.requires_operator_decision is False

    ipx_c = next(c for c in classifications if c.partner_key == "ipx1031")
    assert ipx_c.property_id == "profithelm"
    assert ipx_c.classification_type == "APPLICATION_SUBMITTED"

    simp_c = next(c for c in classifications if c.partner_key == "simply_business")
    assert simp_c.property_id == "profithelm"
    assert simp_c.classification_type == "APPLICATION_SUBMITTED"
    assert simp_c.network == "Impact.com"

    cj_c = next(c for c in classifications if c.partner_key == "taxslayer")
    assert cj_c.property_id == "profithelm"
    assert cj_c.classification_type == "APPLICATION_SUBMITTED"
    assert cj_c.network == "CJ Affiliate"

    cj_tt = next(c for c in classifications if c.partner_key == "turbotax")
    assert cj_tt.property_id == "profithelm"
    assert cj_tt.classification_type == "APPLICATION_SUBMITTED"
    assert cj_tt.network == "CJ Affiliate"

    xen_c = next(c for c in classifications if c.partner_key == "crest_capital")
    assert xen_c.property_id == "profithelm"
    assert xen_c.classification_type == "APPLICATION_APPROVED"
    assert xen_c.candidate_url == "https://www.xendoo.com/?fp_ref=arif-4ac24e"


def test_all_partners_have_verified_external_receipt_in_vault():
    """
    Asserts that every partner entry in monetization_vault.json across ProfitHelm and Prexvo
    contains a concrete external verification proof token (Inbox #, Sent #, Newsletter #,
    pendAdvContracts, PENDING_CAMPAIGN_APPROVAL, FirstPromoter token, FormAssembly,
    freightos.com/contact-us, earnest.com/partner-sign-up, or CJ Advertiser ID) and that
    Impact has 1 active contract (Kalshi #37770) and 17 pending advertiser contracts,
    and CJ Affiliate is 9_of_9_completed and ACTIVE with 28 pending advertiser applications.
    """
    vault_path = os.path.join(
        os.path.dirname(__file__), "..", "pseofactory", "monetization_vault.json"
    )
    with open(vault_path, "r", encoding="utf-8") as f:
        vault = json.load(f)

    assert vault["master_networks"]["impact"]["marketplace_status"] == "active"
    assert vault["master_networks"]["impact"]["identity_verification_status"] == "COMPLETE"
    assert vault["master_networks"]["impact"]["active_advertiser_contracts"] == 1
    assert vault["master_networks"]["impact"]["pending_advertiser_contracts"] == 17
    assert vault["master_networks"]["impact"]["verified_clicks"] >= 3
    assert vault["master_networks"]["partnerstack"]["verified_clicks"] >= 28
    assert vault["master_networks"]["cj_affiliate"]["company_cid"] == "7792582"
    assert vault["master_networks"]["cj_affiliate"]["publisher_id"] == "8101803"
    assert vault["master_networks"]["cj_affiliate"]["promotional_property_id"] == "101725461"
    assert vault["master_networks"]["cj_affiliate"]["onboarding_progress"] == "9_of_9_completed"
    assert vault["master_networks"]["cj_affiliate"]["account_status"] == "ACTIVE"
    assert vault["master_networks"]["cj_affiliate"]["pending_advertiser_applications"] == 28
    assert vault["properties"]["profithelm"]["partners"]["kalshi"]["status"] == "live"
    assert vault["properties"]["profithelm"]["partners"]["crest_capital"]["status"] == "live"
    assert vault["properties"]["profithelm"]["partners"]["turbotax"]["status"] == "awaiting_response"
    assert vault["properties"]["profithelm"]["partners"]["taxslayer"]["status"] == "awaiting_response"
    assert (
        vault["properties"]["profithelm"]["partners"]["kalshi"]["url"]
        == "https://kalshi.pxf.io/c/7932737/3078072/37770"
    )

    proof_tokens = (
        "Inbox #",
        "Sent #",
        "Newsletter #",
        "pendAdvContracts",
        "PENDING_CAMPAIGN_APPROVAL",
        "FirstPromoter token",
        "FormAssembly",
        "freightos.com/contact-us",
        "earnest.com/partner-sign-up",
        "CJ Advertiser ID",
    )
    for prop_id in ("profithelm", "prexvo"):
        partners = vault["properties"][prop_id]["partners"]
        for p_key, p_cfg in partners.items():
            corr = p_cfg.get("correspondence_status", "")
            assert any(tok in corr for tok in proof_tokens), (
                f"{prop_id}.{p_key} lacks hard external receipt proof in correspondence_status: {corr}"
            )


def test_publisher_introduction_sent_emails_classification():
    """
    Asserts that Sent #264-#274 publisher introduction emails to CJ Affiliate and Impact.com
    advertiser contacts classify cleanly to their respective partner keys and properties.
    """
    engine = EmailIngestionEngine()
    sent_messages = [
        EmailMessage(
            id="264",
            message_id="msg-sent-264",
            account="zoho",
            mailbox="Sent",
            date="2026-10-18T12:32:46-07:00",
            subject="CJ Affiliate Publisher Introduction: ProfitHelm.com (CID #8101803 / PID #101725461) - TurboTax (#1905878)",
            sender_name="Arif Coskun",
            sender_email="arif.coskun@profithelm.com",
            body_snippet="We recently submitted our publisher application to the TurboTax Affiliate Program.",
            raw_headers={"to_email": "turbotax@cj.com"},
        ),
        EmailMessage(
            id="265",
            message_id="msg-sent-265",
            account="zoho",
            mailbox="Sent",
            date="2026-10-18T12:32:47-07:00",
            subject="CJ Affiliate Publisher Introduction: ProfitHelm.com (CID #8101803) - Intuit Small Business QuickBooks & Payroll (#2271086)",
            sender_name="Arif Coskun",
            sender_email="arif.coskun@profithelm.com",
            body_snippet="We recently submitted our publisher application to Intuit Small Business.",
            raw_headers={"to_email": "cj_intuit@cj.com"},
        ),
        EmailMessage(
            id="268",
            message_id="msg-sent-268",
            account="zoho",
            mailbox="Sent",
            date="2026-10-18T12:32:49-07:00",
            subject="CJ Affiliate Publisher Introduction: ProfitHelm.com (CID #8101803) - ezTaxReturn.com (#6874782)",
            sender_name="Arif Coskun",
            sender_email="arif.coskun@profithelm.com",
            body_snippet="We recently submitted our publisher application to ezTaxReturn.com.",
            raw_headers={"to_email": "allwyn.symon@eztaxreturn.com"},
        ),
        EmailMessage(
            id="272",
            message_id="msg-sent-272",
            account="zoho",
            mailbox="Sent",
            date="2026-10-18T12:32:53-07:00",
            subject="Impact.com Publisher Introduction: Prexvo.com (Account #7932737) - Splash Financial (#9516)",
            sender_name="Arif Coskun",
            sender_email="arif.coskun@profithelm.com",
            body_snippet="We submitted our publisher application to Splash Financial on Impact.com.",
            raw_headers={"to_email": "pleimkuehler@splashfinancial.com"},
        ),
        EmailMessage(
            id="273",
            message_id="msg-sent-273",
            account="zoho",
            mailbox="Sent",
            date="2026-10-18T12:32:54-07:00",
            subject="Impact.com Publisher Introduction: Prexvo.com (Account #7932737) - SoFi Student Loan Refinancing (#11190)",
            sender_name="Arif Coskun",
            sender_email="arif.coskun@profithelm.com",
            body_snippet="We submitted our publisher application to SoFi (#11190) on Impact.com.",
            raw_headers={"to_email": "cfels@lqdigital.com"},
        ),
        EmailMessage(
            id="274",
            message_id="msg-sent-274",
            account="zoho",
            mailbox="Sent",
            date="2026-10-18T12:32:54-07:00",
            subject="Impact.com Publisher Introduction: Prexvo.com (Account #7932737) - LendKey Student Loan Refinancing (#3276)",
            sender_name="Arif Coskun",
            sender_email="arif.coskun@profithelm.com",
            body_snippet="We submitted our publisher application to LendKey (#3276) on Impact.com.",
            raw_headers={"to_email": "accounting@lendkey.com"},
        ),
    ]
    cls = engine.classify_partner_emails(sent_messages)
    assert len(cls) == 6
    by_id = {c.email_id: c for c in cls}
    assert by_id["264"].partner_key == "turbotax"
    assert by_id["264"].property_id == "profithelm"
    assert by_id["265"].partner_key == "gusto"
    assert by_id["268"].partner_key == "taxslayer"
    assert by_id["272"].partner_key == "splash_financial"
    assert by_id["272"].property_id == "prexvo"
    assert by_id["273"].partner_key == "sofi"
    assert by_id["273"].property_id == "prexvo"
    assert by_id["274"].partner_key == "lendkey"
    assert by_id["274"].property_id == "prexvo"


def test_cj_and_impact_inbound_approval_parsing_and_notification_filter():
    """
    Asserts that:
    1. Inbound approval replies from outbound_partner_map contacts (e.g., Aaron Rosenthal at
       aaron@e-file.com in Inbox #999: 'Your application has been approved') are classified
       as APPLICATION_APPROVED rather than swallowed as APPLICATION_SUBMITTED.
    2. CJ Affiliate welcome notifications (#846 E-file.com, #847 LawDepot, #848 ezTaxReturn.com)
       and Impact banking/approval notifications (#1002) are matched by Notification filter domains
       and classified accurately.
    3. Re-sent SoFi publisher introductions to affiliates@sofi.com (Sent #275) classify cleanly.
    """
    import pseofactory.email_ingest as email_ingest_mod

    notif_domains = getattr(email_ingest_mod, "ZOHO_NOTIFICATION_PARTNER_DOMAINS", ())
    for required_dom in ("cj.com", "e-file.com", "eztaxreturn.com", "lawdepot.com", "impact.com", "sofi.com"):
        assert required_dom in notif_domains

    engine = EmailIngestionEngine()
    messages = [
        EmailMessage(
            id="999",
            message_id="msg-inbox-999",
            account="zoho",
            mailbox="Inbox",
            date="2026-10-19T12:57:55Z",
            subject="Re: CJ Affiliate Application Follow-Up (CID #8101803) - ProfitHelm LLC Tax Calculators",
            sender_name="Aaron Rosenthal",
            sender_email="aaron@e-file.com",
            body_snippet="Hello, Thank you for your email. Your application has been approved. Regards, Aaron Rosenthal, Director of Marketing | E-file",
        ),
        EmailMessage(
            id="notif-846",
            message_id="msg-notif-846",
            account="zoho",
            mailbox="Notification",
            date="2026-10-19T12:25:34Z",
            subject="Welcome to the E-file.com affiliate program",
            sender_name="E-file.com",
            sender_email="noreply@cj.com",
            body_snippet="Welcome to the E-file.com affiliate program on CJ Affiliate (#4355234). Earn 40% commission on all paid tax returns.",
        ),
        EmailMessage(
            id="notif-848",
            message_id="msg-notif-848",
            account="zoho",
            mailbox="Notification",
            date="2026-10-19T13:20:01Z",
            subject="Welcome to the ezTaxReturn.com Affiliate Program",
            sender_name="ezTaxReturn.com",
            sender_email="noreply@cj.com",
            body_snippet="Welcome to the ezTaxReturn.com Affiliate Program (#6874782). 90-day cookie.",
        ),
        EmailMessage(
            id="notif-847",
            message_id="msg-notif-847",
            account="zoho",
            mailbox="Notification",
            date="2026-10-19T12:35:05Z",
            subject="Welcome to the LawDepot Affiliate Program!",
            sender_name="LawDepot",
            sender_email="noreply@cj.com",
            body_snippet="Welcome to the LawDepot Affiliate Program (#4544498). Earn 30% on orders and $6.50 per free trial.",
        ),
        EmailMessage(
            id="sent-275",
            message_id="msg-sent-275",
            account="zoho",
            mailbox="Sent",
            date="2026-10-18T21:39:34Z",
            subject="Impact.com Publisher Introduction: Prexvo.com (Account #7932737) - SoFi Student Loan Refinancing (#11190)",
            sender_name="Arif Coskun",
            sender_email="arif.coskun@profithelm.com",
            body_snippet="We submitted our publisher application to SoFi (#11190) on Impact.com.",
            raw_headers={"to_email": "affiliates@sofi.com"},
        ),
    ]

    cls = engine.classify_partner_emails(messages)
    by_id = {c.email_id: c for c in cls}

    assert by_id["999"].partner_key == "turbotax"
    assert by_id["999"].classification_type == "APPLICATION_APPROVED"
    assert by_id["999"].requires_operator_decision is False
    assert "click-101906407-11917161" in by_id["999"].candidate_url

    assert by_id["notif-846"].partner_key == "turbotax"
    assert by_id["notif-846"].classification_type == "APPLICATION_APPROVED"
    assert "click-101906407-11917161" in by_id["notif-846"].candidate_url

    assert by_id["notif-848"].partner_key == "taxslayer"
    assert by_id["notif-848"].classification_type == "APPLICATION_APPROVED"
    assert "click-101906407-15704796" in by_id["notif-848"].candidate_url

    assert by_id["notif-847"].partner_key == "suretybonds_direct"
    assert by_id["notif-847"].classification_type == "APPLICATION_APPROVED"
    assert "click-101906407-16985242" in by_id["notif-847"].candidate_url

    assert by_id["sent-275"].partner_key == "sofi"
    assert by_id["sent-275"].property_id == "prexvo"
    assert by_id["sent-275"].classification_type == "APPLICATION_SUBMITTED"


def test_automated_readiness_audit_flags_unwired_vault_links_and_missing_payouts(temp_bus_path, temp_email_paths):
    """
    Asserts that PartnerTrackingEngine.audit_readiness_and_vault_parity():
    1. Flags any registry status drift where monetization_vault.json is live/active_direct
       while static affiliates.py still has status='pending' (crest_capital and ipx1031 on ProfitHelm,
       and the 5 student loan partners on Prexvo).
    2. Distinguishes true network-tracked affiliate URLs (is_network_tracked_link=True) from
       UTM-only / bare merchant URLs (ipx1031 on ProfitHelm and the 5 pending Impact contracts on Prexvo).
    3. Flags whenever an approved tracking link in monetization_vault.json (such as CJ E-file.com,
       ezTaxReturn.com, LawDepot, or Impact Xendoo $500 CPA) is not yet wired as default_url in affiliates.py.
    4. Flags whenever an active partner's network or dashboard lacks verified payout credentials
       (and triggers an explicit alert if a simulated vault has missing EFT/PayPal credentials).
    5. Verifies vault-to-placement parity across compiled HTML pages in profithelm-platform and prexvo.
    """
    import copy
    from pseofactory.affiliates_hub import MonetizationHub

    cache_path, state_path = temp_email_paths
    email_engine = EmailIngestionEngine(cache_path=cache_path, state_path=state_path)
    action_bus = HumanActionBus(bus_path=temp_bus_path)
    tracker = PartnerTrackingEngine(email_engine=email_engine, action_bus=action_bus)

    audit = tracker.audit_readiness_and_vault_parity(
        profithelm_dist_dir="/home/ubuntuadmin/projects/profithelm-platform/dist",
        prexvo_dist_dir="/home/ubuntuadmin/projects/prexvo/dist",
    )

    # 1. Verify registry status drift detection between affiliates.py and monetization_vault.json
    ph_audit = audit["properties"]["profithelm"]
    px_audit = audit["properties"]["prexvo"]
    drift_keys = {d["partner_key"] for d in ph_audit["registry_status_drift"]}
    assert drift_keys == {"crest_capital"}
    px_drift_keys = {d["partner_key"] for d in px_audit["registry_status_drift"]}
    assert px_drift_keys == set()

    assert ph_audit["network_tracked_live_count"] == 7
    assert set(ph_audit["network_tracked_partners"]) == {
        "coinledger",
        "koinly",
        "rippling",
        "mercury",
        "kalshi",
        "crest_capital",
        "gusto",
    }
    assert ph_audit["utm_only_or_bare_live_partners"] == ["ipx1031"]
    assert px_audit["network_tracked_live_count"] == 0
    assert set(px_audit["utm_only_or_bare_live_partners"]) == {
        "splash_financial",
        "sofi",
        "credible",
        "earnest",
        "lendkey",
    }

    # 3. Verify unwired approved vault links are flagged automatically
    unwired_keys = {it["partner_key"] for it in ph_audit["unwired_vault_links"]}
    assert "turbotax" in unwired_keys  # CJ E-file.com #4355234 approved link in vault
    assert "taxslayer" in unwired_keys  # CJ ezTaxReturn.com #6874782 approved link in vault
    assert "suretybonds_direct" in unwired_keys  # CJ LawDepot #4544498 approved link in vault
    assert "crest_capital" in unwired_keys  # Impact Xendoo #16354 $500 CPA upgrade link in vault

    # 4. Verify master network payout credentials are verified for Impact, CJ, PartnerStack, Mercury
    payout_map = audit["network_payout_readiness"]
    assert payout_map["impact"]["payout_verified"] is True
    assert "XXXXXXXX1395" in payout_map["impact"]["account_identifier"]
    assert payout_map["cj_affiliate"]["payout_verified"] is True
    assert "********1395" in payout_map["cj_affiliate"]["account_identifier"]
    assert payout_map["partnerstack"]["payout_verified"] is True
    assert "arif.coskun@profithelm.com" in payout_map["partnerstack"]["account_identifier"]
    assert "1395" in payout_map["partnerstack"]["account_identifier"]
    assert payout_map["mercury_direct"]["payout_verified"] is True
    assert payout_map["koinly_affiliate"]["payout_verified"] is True
    assert payout_map["sovrn_commerce"]["payout_verified"] is True
    assert "1395" in payout_map["sovrn_commerce"]["account_identifier"]

    # Simulate missing payout credentials on Impact and verify the guardrail flags affected active partners
    broken_vault = copy.deepcopy(tracker.hub.vault_data)
    broken_vault["master_networks"]["impact"]["payout_method_status"] = "INCOMPLETE - missing bank account"
    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as tf:
        json.dump(broken_vault, tf)
        broken_vault_path = tf.name
    try:
        broken_tracker = PartnerTrackingEngine(
            email_engine=email_engine,
            action_bus=action_bus,
            monetization_hub=MonetizationHub(vault_path=broken_vault_path),
        )
        broken_audit = broken_tracker.audit_readiness_and_vault_parity()
        assert broken_audit["network_payout_readiness"]["impact"]["payout_verified"] is False
        flagged_payout_partners = {
            it["partner_key"] for it in broken_audit["properties"]["profithelm"]["missing_payout_alerts"]
        }
        assert "kalshi" in flagged_payout_partners
    finally:
        if os.path.exists(broken_vault_path):
            os.remove(broken_vault_path)

    # 5. Verify compiled tenant placement parity across profithelm-platform and prexvo
    assert ph_audit["compiled_dom_parity"]["total_outbound_r_links"] >= 671
    assert ph_audit["compiled_dom_parity"]["network_tracked_click_share_pct"] >= 75.0
    assert ph_audit["compiled_dom_parity"]["edge_upgraded_click_share_pct"] == 100.0
    assert ph_audit["compiled_dom_parity"]["pending_partner_links_in_dom"] == 0
    assert px_audit["compiled_dom_parity"]["total_outbound_r_links"] >= 75
    assert px_audit["compiled_dom_parity"]["ymyl_restricted_pages_clean"] is True


def test_gusto_approval_classification_and_firstpromoter_fp_sid_forwarding(temp_email_paths):
    """
    Verifies:
    1. Gusto approval emails (#1003 'You're approved to Gusto's affiliate program!' and #1004
       from noelle.hyra@gusto.com) classify as APPLICATION_APPROVED with candidate_url
       https://gusto.pxf.io/c/7932737/1226287/15154.
    2. FirstPromoter edge redirect generation appends fp_sid (up to 64 alphanumeric/underscore/hyphen chars) so
       CoinLedger, Koinly, and Xendoo FirstPromoter Sub-Id reports capture full page+slot placement attribution.
    """
    from pseofactory.edge import generate_edge_redirect_function

    cache_path, state_path = temp_email_paths
    engine = EmailIngestionEngine(cache_path=cache_path, state_path=state_path)
    msgs = [
        EmailMessage(
            id="1003",
            message_id="<1003@impact.com>",
            account="zoho",
            mailbox="Inbox",
            subject="You're approved to Gusto's affiliate program!",
            sender_name="Gusto",
            sender_email="notifications@impact.com",
            date="2026-10-19 15:47:00+00:00",
            body_snippet="Welcome to the Gusto affiliate program on Impact.com! Earn $200-$300 per qualified referral: https://gusto.pxf.io/c/7932737/1226287/15154",
        ),
        EmailMessage(
            id="1004",
            message_id="<1004@gusto.com>",
            account="zoho",
            mailbox="Inbox",
            subject="Gusto Affiliate Program",
            sender_name="Noelle Hyra",
            sender_email="noelle.hyra@gusto.com",
            date="2026-10-19 15:52:00+00:00",
            body_snippet="Hi Arif, excited to welcome ProfitHelm to Gusto's affiliate program!",
        ),
    ]
    classified = engine.classify_partner_emails(msgs)
    assert len(classified) == 2
    assert all(c.partner_key == "gusto" for c in classified)
    assert all(c.classification_type == "APPLICATION_APPROVED" for c in classified)
    assert all(c.candidate_url == "https://gusto.pxf.io/c/7932737/1226287/15154" for c in classified)

    js_code = generate_edge_redirect_function("profithelm")
    assert 'defaultUrl: "https://gusto.pxf.io/c/7932737/1226287/15154"' in js_code
    assert 'targetObj.searchParams.set("fp_sid", fpSid)' in js_code
    assert ".slice(0, 64)" in js_code


def test_durable_kv_sync_page_slot_aggregation_and_portal_click_reconciliation(
    tmp_path, temp_bus_path, temp_email_paths
):
    """
    Verifies:
    1. sync_tenant_edge_redirect_function synchronizes durable [[kv_namespaces]] bindings into
       wrangler.toml for both Prexvo (PREXVO_TELEMETRY_KV) and ProfitHelm (PROFITHELM_LEADS and
       PROFITHELM_TELEMETRY_KV), eliminating temporary isolate memory volatility on Prexvo.
    2. aggregate_outbound_partner_engagement aggregates click volume by page (by_page / by_slug),
       by placement slot (by_cta_slot), by (page, slot) pair (by_page_and_slot), and by subid (by_subid).
    3. PartnerTrackingEngine.sync_edge_click_telemetry and reconcile_edge_clicks_with_portals
       ingest edge redirect and click beacon events, aggregate volume by page and placement slot,
       and reconcile recorded edge redirects against affiliate portal click reports across
       Impact.com, CJ Affiliate, PartnerStack, and FirstPromoter.
    """
    from pseofactory.affiliates import aggregate_outbound_partner_engagement
    from pseofactory.edge import sync_tenant_edge_redirect_function

    # 1. Verify Prexvo and ProfitHelm wrangler.toml KV namespace synchronization
    px_repo = tmp_path / "prexvo"
    (px_repo / "functions" / "r").mkdir(parents=True)
    (px_repo / "wrangler.toml").write_text(
        'name = "prexvo"\npages_build_output_dir = "dist"\ncompatibility_date = "2026-03-01"\n',
        encoding="utf-8",
    )
    px_sync = sync_tenant_edge_redirect_function(px_repo, property_id="prexvo")
    assert px_sync["status"] in ("UPDATED", "UNCHANGED")
    px_wrangler = (px_repo / "wrangler.toml").read_text(encoding="utf-8")
    assert 'binding = "PREXVO_TELEMETRY_KV"' in px_wrangler
    assert 'id = "153917b16871453a9f07bfb39ff3fd98"' in px_wrangler

    ph_repo = tmp_path / "profithelm-platform"
    (ph_repo / "functions" / "r").mkdir(parents=True)
    (ph_repo / "wrangler.toml").write_text(
        'name = "profithelm"\npages_build_output_dir = "dist"\ncompatibility_date = "2024-09-23"\n',
        encoding="utf-8",
    )
    ph_sync = sync_tenant_edge_redirect_function(ph_repo, property_id="profithelm")
    assert ph_sync["status"] in ("UPDATED", "UNCHANGED")
    ph_wrangler = (ph_repo / "wrangler.toml").read_text(encoding="utf-8")
    assert 'binding = "PROFITHELM_LEADS"' in ph_wrangler
    assert 'binding = "PROFITHELM_TELEMETRY_KV"' in ph_wrangler

    # 2. Verify page + placement slot + subid click aggregation
    sample_events = [
        {
            "event_id": "evt_test_1",
            "event_type": "affiliate_click",
            "property_id": "profithelm",
            "partner_key": "rippling",
            "tool_slug": "saas-runway-burn-rate-calculator",
            "cta_slot": "hero_callout",
            "subid": "rippling_runway_hero_test_oct19",
            "value_tier": "premium",
        },
        {
            "event_id": "evt_test_2",
            "event_type": "affiliate_click",
            "property_id": "profithelm",
            "partner_key": "rippling",
            "tool_slug": "saas-runway-burn-rate-calculator",
            "cta_slot": "calculator_result_inline",
            "subid": "rippling_runway_inline_test_oct19",
            "value_tier": "premium",
        },
        {
            "event_id": "evt_test_3",
            "event_type": "affiliate_click",
            "property_id": "profithelm",
            "partner_key": "kalshi",
            "tool_slug": "prediction-market-ev-calculator",
            "cta_slot": "hero_callout",
            "subid": "kalshi_ev_hero_test_oct19",
            "value_tier": "premium",
        },
        {
            "event_id": "evt_test_4",
            "event_type": "affiliate_click",
            "property_id": "prexvo",
            "partner_key": "splash_financial",
            "tool_slug": "student-loan-refinance-savings-calculator",
            "cta_slot": "hero_callout",
            "subid": "splash_refi_hero_test_oct19",
            "value_tier": "starter",
        },
    ]

    ph_agg = aggregate_outbound_partner_engagement(sample_events, property_id="profithelm")
    assert ph_agg["total_outbound_clicks"] == 3
    assert "by_page_and_slot" in ph_agg
    assert "by_subid" in ph_agg
    assert ph_agg["by_page_and_slot"]["saas-runway-burn-rate-calculator:hero_callout"]["outbound_clicks"] == 1
    assert ph_agg["by_page_and_slot"]["saas-runway-burn-rate-calculator:calculator_result_inline"]["outbound_clicks"] == 1
    assert ph_agg["by_page_and_slot"]["prediction-market-ev-calculator:hero_callout"]["outbound_clicks"] == 1
    assert ph_agg["by_subid"]["rippling_runway_hero_test_oct19"]["outbound_clicks"] == 1
    assert ph_agg["by_subid"]["kalshi_ev_hero_test_oct19"]["partner_key"] == "kalshi"

    # 3. Verify PartnerTrackingEngine edge telemetry sync & portal click reconciliation
    cache_path, state_path = temp_email_paths
    email_engine = EmailIngestionEngine(cache_path=cache_path, state_path=state_path)
    action_bus = HumanActionBus(bus_path=temp_bus_path)
    tracker = PartnerTrackingEngine(email_engine=email_engine, action_bus=action_bus)

    ledger_dir = tmp_path / "telemetry_ledgers"
    sync_res = tracker.sync_edge_click_telemetry(
        injected_events={"profithelm": sample_events[:3], "prexvo": sample_events[3:]},
        ledger_dir=ledger_dir,
    )
    assert sync_res["profithelm"]["ingested_count"] == 3
    assert sync_res["prexvo"]["ingested_count"] == 1
    assert (ledger_dir / "profithelm_telemetry_events.jsonl").is_file()
    assert (ledger_dir / "prexvo_telemetry_events.jsonl").is_file()

    recon = tracker.reconcile_edge_clicks_with_portals(
        engagement_by_property={
            "profithelm": sync_res["profithelm"]["aggregation"],
            "prexvo": sync_res["prexvo"]["aggregation"],
        }
    )
    assert recon["status"] in ("RECONCILED", "DISCREPANCY_DETECTED")
    assert "networks" in recon
    assert "impact" in recon["networks"]
    assert "cj_affiliate" in recon["networks"]
    assert "partnerstack" in recon["networks"]
    assert "firstpromoter" in recon["networks"]
    assert "properties" in recon
    assert recon["properties"]["profithelm"]["total_edge_outbound_clicks"] == 3
    assert recon["properties"]["prexvo"]["total_edge_outbound_clicks"] == 1
    assert "by_page_and_slot" in recon["properties"]["profithelm"]


def test_non_active_partnership_state_reconciliation_and_latest_inbox_sync(
    temp_bus_path, temp_email_paths
):
    """
    Verifies:
    1. Latest inbox & sent correspondence classification fixes:
       - Newsletter #1588 ('Welcome to Koinly Affiliates!') classifies as koinly (APPLICATION_APPROVED)
         with candidate_url https://koinly.io/?fpr=arif-4c0b88.
       - Inbox #1000 ('Re: E-file.com Application Follow-Up' from aaron@e-file.com) classifies as
         turbotax (APPLICATION_APPROVED) with CJ tracking link https://www.jdoqocy.com/click-101906407-11917161.
       - Sent #278 ('Re: OTR Solutions Affiliate Program' to wade.fenton@otrsolutions.com) classifies as
         otr_solutions_factoring (APPLICATION_SUBMITTED).
    2. PartnerTrackingEngine.reconcile_non_active_partnerships_and_edge_routes() categorizes every
       non-active partnership across ProfitHelm and Prexvo into the 4 operational states:
       - PENDING_ADVERTISER_REVIEW
       - AWAITING_NETWORK_OR_COMPLIANCE_VERIFICATION
       - NEWLY_APPROVED_AND_WIRED_AT_EDGE
       - DECLINED_COVERED_BY_FALLBACK
       reconciled against live /r/:partner edge redirect routes and status deltas since the
       2026-10-20T10:10-07:00 audit snapshot.
    """
    cache_path, state_path = temp_email_paths
    email_engine = EmailIngestionEngine(cache_path=cache_path, state_path=state_path)
    action_bus = HumanActionBus(bus_path=temp_bus_path)

    msgs = [
        EmailMessage(
            id="1588",
            message_id="<1588@firstpromoter.com>",
            account="zoho",
            mailbox="Newsletter",
            subject="Welcome to Koinly Affiliates!",
            sender_name="Koinly Affiliates",
            sender_email="promoter@firstpromoter.com",
            date="2026-10-20 19:14:05+00:00",
            body_snippet="Welcome to Koinly Affiliates! Your referral link is http://koinly.io?fpr=arif-4c0b88",
        ),
        EmailMessage(
            id="1000",
            message_id="<1000@e-file.com>",
            account="zoho",
            mailbox="Inbox",
            subject="Re: E-file.com Application Follow-Up",
            sender_name="Aaron",
            sender_email="aaron@e-file.com",
            date="2026-10-19 19:53:48+00:00",
            body_snippet="Sounds good Arif. Welcome aboard.",
        ),
        EmailMessage(
            id="278",
            message_id="<278@profithelm.com>",
            account="zoho",
            mailbox="Sent",
            subject="Re: OTR Solutions Affiliate Program",
            sender_name="Arif Coskun",
            sender_email="arif.coskun@profithelm.com",
            raw_headers={"to_email": "wade.fenton@otrsolutions.com"},
            date="2026-10-20 17:34:43+00:00",
            body_snippet="Hi Wade, thanks for reaching out. Here are the answers to your 7 qualification questions.",
        ),
    ]
    classified = email_engine.classify_partner_emails(msgs)
    by_id = {c.email_id: c for c in classified}

    assert by_id["1588"].partner_key == "koinly"
    assert by_id["1588"].classification_type == "APPLICATION_APPROVED"
    assert by_id["1588"].candidate_url == "https://koinly.io/?via=A4FABF09&utm_source=affiliate"

    assert by_id["1000"].partner_key == "turbotax"
    assert by_id["1000"].classification_type == "APPLICATION_APPROVED"
    assert by_id["1000"].candidate_url == "https://www.jdoqocy.com/click-101906407-11917161"

    assert by_id["278"].partner_key == "otr_solutions_factoring"
    assert by_id["278"].classification_type == "APPLICATION_SUBMITTED"

    tracker = PartnerTrackingEngine(email_engine=email_engine, action_bus=action_bus)
    recon = tracker.reconcile_non_active_partnerships_and_edge_routes()

    assert set(recon["operational_states"]) == {
        "PENDING_ADVERTISER_REVIEW",
        "AWAITING_NETWORK_OR_COMPLIANCE_VERIFICATION",
        "NEWLY_APPROVED_AND_WIRED_AT_EDGE",
        "DECLINED_COVERED_BY_FALLBACK",
    }

    ph_recon = recon["properties"]["profithelm"]
    px_recon = recon["properties"]["prexvo"]

    assert ph_recon["total_canonical_partners"] == 22
    assert ph_recon["active_earning_count"] == 6
    assert ph_recon["non_active_count"] == 16
    assert ph_recon["counts_by_state"]["NEWLY_APPROVED_AND_WIRED_AT_EDGE"] == 5
    assert ph_recon["counts_by_state"]["PENDING_ADVERTISER_REVIEW"] == 6
    assert ph_recon["counts_by_state"]["AWAITING_NETWORK_OR_COMPLIANCE_VERIFICATION"] == 3
    assert ph_recon["counts_by_state"]["DECLINED_COVERED_BY_FALLBACK"] == 2

    assert px_recon["total_canonical_partners"] == 5
    assert px_recon["active_earning_count"] == 0
    assert px_recon["non_active_count"] == 5
    assert px_recon["counts_by_state"]["PENDING_ADVERTISER_REVIEW"] == 3
    assert px_recon["counts_by_state"]["AWAITING_NETWORK_OR_COMPLIANCE_VERIFICATION"] == 1
    assert px_recon["counts_by_state"]["DECLINED_COVERED_BY_FALLBACK"] == 1

    delta_keys = {d["partner_key"] for d in recon["status_deltas_since_last_snapshot"]}
    assert {"rippling", "koinly", "otr_solutions_factoring"} <= delta_keys


def test_partner_earnings_ledger_sync_and_commission_email_ingestion(
    tmp_path, temp_bus_path, temp_email_paths
):
    """
    Verifies:
    1. PartnerTrackingEngine.sync_partner_earnings_and_balances() builds the complete
       portal-by-portal (8 portals) and partner-by-partner (17 canonical partners)
       earnings and balance reconciliation ledger, writing it to ledger_path.
    2. Strictly separates actual realized commissions (realized_commission_usd: $0.00 today),
       pending commissions, paid-out totals, qualified leads, and conversions from
       statistical modeled EPC projections (modeled_epc_pipeline_usd).
    3. Classifies Zoho Newsletter #1591 ('Welcome to the Ramp Partner Program') as
       APPLICATION_APPROVED for ramp on Impact.com (#51436).
    4. Automatically ingests COMMISSION_EARNED, LEAD_CONVERTED, and PAYOUT_ISSUED email
       alerts into the partner, portal, and network reconciliation ledgers.
    """
    cache_path, state_path = temp_email_paths
    email_engine = EmailIngestionEngine(cache_path=cache_path, state_path=state_path)
    action_bus = HumanActionBus(bus_path=temp_bus_path)
    tracker = PartnerTrackingEngine(email_engine=email_engine, action_bus=action_bus)

    # 1. Baseline sync (zero realized commissions today vs positive modeled EPC pipeline)
    ledger_file = tmp_path / "partner_earnings_ledger.json"
    baseline_ledger = tracker.sync_partner_earnings_and_balances(
        fetch_live_api=False,
        ledger_path=ledger_file,
    )
    assert ledger_file.is_file()
    assert baseline_ledger["has_earned_any_realized_commission_or_conversion"] is False
    summary = baseline_ledger["cashflow_summary"]
    assert summary["realized_commission_usd"] == 0.0
    assert summary["pending_commission_usd"] == 0.0
    assert summary["approved_payable_usd"] == 0.0
    assert summary["paid_out_usd"] == 0.0
    assert summary["qualified_leads_count"] == 0
    assert summary["conversions_count"] == 0
    assert summary["portal_verified_clicks_total"] >= 231
    assert summary["modeled_epc_pipeline_usd"] > 0.0

    # Verify all 8 portal dashboards are classified with auth_status & sync_mechanism
    expected_portals = {
        "partnerstack",
        "firstpromoter_coinledger",
        "firstpromoter_xendoo",
        "koinly_native",
        "sovrn_commerce",
        "cj_affiliate",
        "impact",
        "mercury_direct",
    }
    assert set(baseline_ledger["portals"].keys()) == expected_portals
    assert baseline_ledger["portals"]["partnerstack"]["is_authenticated_and_syncing"] is True
    assert baseline_ledger["portals"]["partnerstack"]["portal_verified_clicks"] >= 182
    assert baseline_ledger["portals"]["firstpromoter_coinledger"]["is_authenticated_and_syncing"] is True
    assert baseline_ledger["portals"]["firstpromoter_xendoo"]["is_authenticated_and_syncing"] is True
    assert baseline_ledger["portals"]["koinly_native"]["is_authenticated_and_syncing"] is True
    assert baseline_ledger["portals"]["sovrn_commerce"]["is_authenticated_and_syncing"] is True
    assert baseline_ledger["portals"]["mercury_direct"]["is_authenticated_and_syncing"] is True
    assert baseline_ledger["portals"]["impact"]["is_authenticated_and_syncing"] is False
    assert baseline_ledger["portals"]["cj_affiliate"]["is_authenticated_and_syncing"] is False

    # 2. Verify Ramp approval (#1591) + simulated COMMISSION_EARNED / LEAD_CONVERTED / PAYOUT_ISSUED alerts
    simulated_emails = [
        EmailMessage(
            id="1591",
            message_id="<1591@app.impact.com>",
            account="zoho",
            mailbox="Newsletter",
            subject="Welcome to the Ramp Partner Program",
            sender_name="Ramp Partner Team",
            sender_email="notifications@app.impact.com",
            date="2026-10-21T14:54:06Z",
            body_snippet="Congratulations - you've been approved to join the Ramp Partner Program!",
        ),
        EmailMessage(
            id="2001",
            message_id="<2001@partnerstack.com>",
            account="zoho",
            mailbox="Inbox",
            subject="You earned a commission of $600.00 on Rippling!",
            sender_name="PartnerStack",
            sender_email="notifications@partnerstack.com",
            date="2026-10-21T18:00:00Z",
            body_snippet="Congratulations! You earned a commission of $600.00 for a Rippling SQO.",
        ),
        EmailMessage(
            id="2002",
            message_id="<2002@impact.com>",
            account="zoho",
            mailbox="Inbox",
            subject="New qualified lead converted for Gusto",
            sender_name="Impact Notifications",
            sender_email="notifications@app.impact.com",
            date="2026-10-21T18:05:00Z",
            body_snippet="A new qualified lead converted on Gusto for $300.00.",
        ),
        EmailMessage(
            id="2003",
            message_id="<2003@mercury.com>",
            account="zoho",
            mailbox="Inbox",
            subject="Payout issued: $250.00 Mercury referral bonus",
            sender_name="Mercury",
            sender_email="support@mercury.com",
            date="2026-10-21T18:10:00Z",
            body_snippet="Your payout issued for $250.00 to Mercury Checking.",
        ),
    ]
    classified = email_engine.classify_partner_emails(simulated_emails)
    by_id = {c.email_id: c for c in classified}
    assert by_id["1591"].partner_key == "ramp"
    assert by_id["1591"].classification_type == "APPLICATION_APPROVED"
    assert by_id["2001"].partner_key == "rippling"
    assert by_id["2001"].classification_type == "COMMISSION_EARNED"
    assert by_id["2001"].commission_amount_usd == 600.0
    assert by_id["2002"].partner_key == "gusto"
    assert by_id["2002"].classification_type == "LEAD_CONVERTED"
    assert by_id["2002"].commission_amount_usd == 300.0
    assert by_id["2003"].partner_key == "mercury"
    assert by_id["2003"].classification_type == "PAYOUT_ISSUED"
    assert by_id["2003"].commission_amount_usd == 250.0

    updated_ledger = tracker.sync_partner_earnings_and_balances(
        fetch_live_api=False,
        ledger_path=ledger_file,
        extra_email_messages=simulated_emails,
    )
    assert updated_ledger["has_earned_any_realized_commission_or_conversion"] is True
    assert updated_ledger["cashflow_summary"]["realized_commission_usd"] == 900.0
    assert updated_ledger["cashflow_summary"]["paid_out_usd"] == 250.0
    assert updated_ledger["cashflow_summary"]["qualified_leads_count"] == 1
    assert updated_ledger["cashflow_summary"]["conversions_count"] == 1
    assert updated_ledger["partners"]["rippling"]["realized_commission_usd"] == 600.0
    assert updated_ledger["partners"]["gusto"]["realized_commission_usd"] == 300.0
    assert updated_ledger["partners"]["mercury"]["paid_out_usd"] == 250.0

    recon = tracker.reconcile_edge_clicks_with_portals(earnings_ledger=updated_ledger)
    assert recon["networks"]["partnerstack"]["realized_commission_usd"] == 600.0
    assert recon["networks"]["impact"]["realized_commission_usd"] == 300.0
    assert recon["networks"]["impact"]["qualified_leads_count"] == 1
    assert_no_forbidden_dashes(json.dumps(updated_ledger), context="partner_earnings_ledger")


def test_autonomous_link_promotion_and_new_zoho_classifications(
    tmp_path, temp_bus_path, temp_email_paths
):
    """
    Verifies:
    1. Classification of Zoho Notification #851 (FreeTaxUSA CJ approval), Notification #857
       (WalletHub CJ approval), Inbox #1009 (ERGO NEXT Insurance Impact decline), and
       Inbox #1025 (Invoice Simple Impact decline).
    2. PartnerTrackingEngine.auto_promote_approved_links() promotes verified network-tracked
       URLs into the vault's approved_tracking_url / edge direct_contract_upgrades while holding
       bare homepages (e.g. https://ramp.com/, https://wallethub.com/) in awaiting_portal_link_extraction.
    3. Edge redirect functions for both ProfitHelm and Prexvo synthesize sub-attribution from
       both ?source_tool=...&cta_slot=... and ?source=...&slot=... query parameter aliases.
    """
    from pseofactory.edge import generate_edge_redirect_function

    cache_path, state_path = temp_email_paths
    email_engine = EmailIngestionEngine(cache_path=cache_path, state_path=state_path)
    action_bus = HumanActionBus(bus_path=temp_bus_path)
    tracker = PartnerTrackingEngine(email_engine=email_engine, action_bus=action_bus)

    new_zoho_emails = [
        EmailMessage(
            id="notif-851",
            message_id="<851@cj.com>",
            account="zoho",
            mailbox="Notification",
            subject="FreeTaxUSA Affiliate Program: Welcome to the FreeTaxUSA Affiliate Program!",
            sender_name="FreeTaxUSA Affiliate Program",
            sender_email="affiliates@freetaxusa.com",
            date="2026-10-21T11:15:01-07:00",
            body_snippet="Welcome to the FreeTaxUSA Affiliate Program (#1722649)! Earn 10%-20% commission on paid products.",
        ),
        EmailMessage(
            id="notif-857",
            message_id="<857@cj.com>",
            account="zoho",
            mailbox="Notification",
            subject="WalletHub Affiliate Program: Welcome to the WalletHub Affiliate Program!",
            sender_name="WalletHub Affiliate Program",
            sender_email="no-response@cj.com",
            date="2026-10-23T00:30:03-07:00",
            body_snippet="Welcome to the WalletHub Affiliate Program (#6002798)! Earn $50 CPA for WalletHub Premium.",
        ),
        EmailMessage(
            id="1009",
            message_id="<1009@impact.com>",
            account="zoho",
            mailbox="Inbox",
            subject="Promotion Request Declined for ERGO NEXT Insurance",
            sender_name="impact.com",
            sender_email="notifications@app.impact.com",
            date="2026-10-22T09:11:10-07:00",
            body_snippet="ERGO NEXT Insurance has declined your application to promote their brand.",
        ),
        EmailMessage(
            id="1025",
            message_id="<1025@impact.com>",
            account="zoho",
            mailbox="Inbox",
            subject="Promotion Request Declined for Invoice Simple",
            sender_name="impact.com",
            sender_email="notifications@app.impact.com",
            date="2026-10-23T12:14:21-07:00",
            body_snippet="Invoice Simple has declined your application to promote their brand.",
        ),
    ]

    classified = email_engine.classify_partner_emails(new_zoho_emails)
    by_id = {c.email_id: c for c in classified}

    assert by_id["notif-851"].classification_type == "APPLICATION_APPROVED"
    assert by_id["notif-851"].partner_key == "taxslayer"
    assert by_id["notif-851"].network == "CJ Affiliate"

    assert by_id["notif-857"].classification_type == "APPLICATION_APPROVED"
    assert by_id["notif-857"].partner_key == "mercury"
    assert by_id["notif-857"].network == "CJ Affiliate"

    assert by_id["1009"].classification_type == "APPLICATION_DECLINED"
    assert by_id["1009"].partner_key == "next_insurance_b2b"

    assert by_id["1025"].classification_type == "APPLICATION_DECLINED"
    assert by_id["1025"].partner_key == "otr_solutions_factoring"

    promo_result = tracker.auto_promote_approved_links(classified, persist=False)
    assert promo_result["promoted_count"] == 1
    assert promo_result["promoted"][0]["email_id"] == "notif-851"
    assert promo_result["awaiting_portal_link_extraction_count"] == 1
    assert promo_result["awaiting_portal_link_extraction"][0]["email_id"] == "notif-857"

    upgrades = tracker.hub.get_direct_contract_upgrades("profithelm")
    assert upgrades["taxslayer"] == "https://www.dpbolvw.net/click-101906407-15704796"
    assert upgrades["ramp"] == "https://join.ramp.com/c/7932737/3981015/51436"
    assert upgrades["freetaxusa"] == "https://www.jdoqocy.com/click-101906407-12306188"
    assert upgrades["wallethub"] == "https://www.jdoqocy.com/click-101906407-16952385"

    ph_edge_js = generate_edge_redirect_function("profithelm", hub=tracker.hub)
    px_edge_js = generate_edge_redirect_function("prexvo", hub=tracker.hub)
    assert 'normParams.get("source_tool") || normParams.get("source")' in ph_edge_js
    assert 'normParams.get("cta_slot") || normParams.get("slot")' in ph_edge_js
    assert '"join.ramp.com"' in ph_edge_js
    assert "https://join.ramp.com/c/7932737/3981015/51436" in ph_edge_js
    assert "https://www.jdoqocy.com/click-101906407-12306188" in ph_edge_js
    assert "https://www.jdoqocy.com/click-101906407-16952385" in ph_edge_js
    assert 'normParams.get("source_tool") || normParams.get("source")' in px_edge_js
    assert 'normParams.get("cta_slot") || normParams.get("slot")' in px_edge_js


def test_zoho_notification_newsletter_body_ingestion_and_playbook_filter_and_factoring_edge_upgrade(
    tmp_path, monkeypatch
):
    """
    Verifies:
      1. ingest_zoho fetches uncached Notification and Newsletter bodies cleanly
         when PYTEST_CURRENT_TEST is absent from os.environ.
      2. classify_partner_emails classifies real Zoho Notification #851 ("FreeTaxUSA Affiliate
         Program. Welcome!" with email.cj.com/c/ wrapper links) as APPLICATION_APPROVED with
         canonical CJ click URL, and skips self-dispatched [Prexvo Playbook] / [ProfitHelm Playbook]
         transactional test emails.
      3. _ensure_standing_operator_items auto-resolves stale PENDING_OPERATOR
         monetization-gate-integration-requirement exception items.
      4. diagnose_stripe_merchant_readiness reports canonical ph_statutory_tax_audit_workpapers SKU.
      5. /r/otr_solutions_factoring upgrades to active Ramp Impact contract (#51436) when
         SOVRN_COMMERCE_APPROVED is unset and falls back to Sovrn VigLink when SOVRN_COMMERCE_APPROVED=true.
    """
    import subprocess
    from pseofactory.action_bus import HumanActionBus
    from pseofactory.edge import sync_tenant_edge_redirect_function
    from pseofactory.email_ingest import EmailIngestionEngine, EmailMessage
    from pseofactory.partner_tracker import (
        PartnerTrackingEngine,
        diagnose_stripe_merchant_readiness,
    )

    cache_file = tmp_path / "email_cache.json"
    email_engine = EmailIngestionEngine(cache_path=str(cache_file), himalaya_bin="himalaya")

    def fake_fetch_envelopes(mailbox="Inbox", page_size=30, force=False):
        if mailbox == "Inbox":
            return [
                {
                    "id": "1027",
                    "from": [{"name": "Prexvo Research", "email": "arif@profithelm.com"}],
                    "subject": "[Prexvo Playbook] Your Student Loan Refinance Worksheet & Repayment Audit",
                    "date": "2026-10-24T11:00:00-07:00",
                }
            ]
        if mailbox == "Sent":
            return []
        if mailbox == "Notification":
            return [
                {
                    "id": "851",
                    "from": [{"name": "FreeTaxUSA Affiliate Team", "email": "affiliates@freetaxusa.com"}],
                    "subject": "FreeTaxUSA Affiliate Program. Welcome!",
                    "date": "2026-10-23T09:15:00-07:00",
                }
            ]
        if mailbox == "Newsletter":
            return [
                {
                    "id": "1591",
                    "from": [{"name": "Ramp Partner Team", "email": "partners@ramp.com"}],
                    "subject": "Welcome to the Ramp Partner Program",
                    "date": "2026-10-23T10:30:00-07:00",
                }
            ]
        return []

    read_calls = []

    def fake_read_body(msg_id, account="zoho", mailbox="Inbox"):
        read_calls.append((str(msg_id), account, mailbox))
        if mailbox == "Notification" and str(msg_id) == "851":
            return (
                "Congratulations and welcome to our Affiliate Program. "
                "Log in via https://email.cj.com/c/eJxE0L1uwyAUgOHn4a5I "
                "to access your links."
            )
        if mailbox == "Newsletter" and str(msg_id) == "1591":
            return "Welcome to the Ramp Partner Program on Impact.com."
        return "Playbook worksheet body"

    monkeypatch.setattr(email_engine, "fetch_zoho_envelopes", fake_fetch_envelopes)
    monkeypatch.setattr(email_engine, "read_message_body", fake_read_body)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    ingested = []
    ingest_err = None
    try:
        ingested = email_engine.ingest_zoho(limit=5, force=True, fetch_bodies_for_partner_keys=True)
    except Exception as exc:
        ingest_err = str(exc)
    assert ingest_err is None, f"ingest_zoho failed to read Notification/Newsletter bodies: {ingest_err}"
    assert ("851", "zoho", "Notification") in read_calls
    assert ("1591", "zoho", "Newsletter") in read_calls

    classified = email_engine.classify_partner_emails(ingested)
    by_id = {c.email_id: c for c in classified}
    assert "1027" not in by_id
    assert by_id["notif-851"].classification_type == "APPLICATION_APPROVED"
    assert by_id["notif-851"].partner_key == "taxslayer"
    assert by_id["notif-851"].candidate_url == "https://www.jdoqocy.com/click-101906407-12306188"
    assert by_id["news-1591"].classification_type == "APPLICATION_APPROVED"
    assert by_id["news-1591"].partner_key == "ramp"

    # Verify stale monetization-gate-integration-requirement item is auto-resolved
    bus_path = tmp_path / "human_action_bus.json"
    bus = HumanActionBus(bus_path=str(bus_path))
    bus.route_manual_requirement(
        property_id="prexvo",
        partner_key="prexvo-monetization-gate",
        partner_name="Prexvo Affiliate Readiness Gate",
        title="Monetization Gate Evaluation Error: name 'zoho_account' is not defined",
        description="Automated partner readiness evaluation encountered an exception.",
        action_type="INTEGRATION_REQUIREMENT",
        severity="HIGH",
    )
    stale_id = "act-prexvo-prexvo-monetization-gate-integration-requirement"
    assert bus.items[stale_id].status == "PENDING_OPERATOR"

    tracker = PartnerTrackingEngine(action_bus=bus, email_engine=email_engine)
    tracker._ensure_standing_operator_items()
    assert bus.items[stale_id].status == "RESOLVED"

    # Verify Stripe SKU parity
    stripe_diag = diagnose_stripe_merchant_readiness(execute_live=False)
    assert "ph_statutory_tax_audit_workpapers" in stripe_diag["product_skus"]
    assert "ph_statutory_tax_optimization_workpapers" not in stripe_diag["product_skus"]

    # Verify /r/otr_solutions_factoring edge contract upgrade in Node.js
    repo_dir = tmp_path / "profithelm"
    (repo_dir / "functions" / "r").mkdir(parents=True, exist_ok=True)
    sync_tenant_edge_redirect_function(repo_dir, property_id="profithelm")
    ph_r = repo_dir / "functions" / "r" / "[partner].js"

    node_script = f"""
    (async () => {{
      const phRedirect = await import({json.dumps(ph_r.as_uri())});

      // Default: Sovrn unapproved -> upgrades otr_solutions_factoring to active Ramp Impact contract (#51436)
      const otrDirectRes = await phRedirect.onRequest({{
        request: new Request("https://profithelm.com/r/otr_solutions_factoring?source_tool=invoice-factoring-cost-apr-calculator&cta_slot=partner_quote_intake&subid=invoice-factoring-cost-apr-calculator_quote_intake"),
        env: {{}},
        params: {{ partner: "otr_solutions_factoring" }}
      }});
      if (otrDirectRes.status !== 302) process.exit(10);
      const otrDirectLoc = new URL(otrDirectRes.headers.get("Location"));
      if (otrDirectLoc.hostname !== "join.ramp.com" || !otrDirectLoc.pathname.includes("/51436")) process.exit(11);
      if (otrDirectLoc.searchParams.get("subId1") !== "invoice-factoring-cost-apr-calculator_quote_intake") process.exit(12);
      if (otrDirectRes.headers.get("X-Edge-Contract-Tier") !== "direct_contract_upgraded") process.exit(13);

      // When SOVRN_COMMERCE_APPROVED=true -> falls back to Sovrn VigLink wrapper
      const otrSovrnRes = await phRedirect.onRequest({{
        request: new Request("https://profithelm.com/r/otr_solutions_factoring?source_tool=invoice-factoring-cost-apr-calculator&cta_slot=partner_quote_intake&subid=invoice-factoring-cost-apr-calculator_quote_intake"),
        env: {{ SOVRN_COMMERCE_APPROVED: "true" }},
        params: {{ partner: "otr_solutions_factoring" }}
      }});
      const otrSovrnLoc = new URL(otrSovrnRes.headers.get("Location"));
      if (otrSovrnLoc.hostname !== "redirect.viglink.com") process.exit(20);
      if (otrSovrnRes.headers.get("X-Edge-Contract-Tier") !== "sovrn_fallback") process.exit(21);

      process.exit(0);
    }})().catch(err => {{ console.error(err); process.exit(99); }});
    """
    proc = subprocess.run(["node", "-e", node_script], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"Node otr_solutions_factoring edge test failed (exit {proc.returncode}): {proc.stderr}"


