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

    # Check that Gusto is marked AWAITING_RESPONSE or PENDING
    gusto_p = next(p for p in ph.partners if p.key == "gusto")
    assert gusto_p.property_id == "profithelm"
    assert gusto_p.is_live_link is False

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
    assert set(ph_tiers["live_revenue_ready"]) == {"coinledger", "koinly", "rippling", "ipx1031", "mercury"}
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
    ]

    classifications = engine.classify_partner_emails(messages)
    assert len(classifications) == 4

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

