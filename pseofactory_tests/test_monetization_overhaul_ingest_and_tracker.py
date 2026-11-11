"""
Regression tests for Cluster 2 Monetization Overhaul:
  1. Canonical partnership identity `arif.coskun@profithelm.com` via `himalaya -a zoho` ONLY
     (zero personal/mindball split-brain, outbound sender normalization, anti-bounce guard).
  2. Email ingestion state machine fixes:
     - Stable RFC `Message-ID` cache key (never volatile IMAP sequence ID).
     - Full 5-folder Zoho polling (`Inbox`, `Sent`, `Notification`, `Newsletter`, `Spam`) with `-s 200`.
     - Human partner manager questions (`Inbox #1074` Allwyn Symon ezTaxReturn) require operator decision.
     - Zero fabricated Oct 27 fixture dicts on `analyze_correspondence_anomalies_and_checkins([])`.
     - Human appeal rejection (`Inbox #1072` Nina Gentles Invoice Simple) classified as `1072` final decline.
     - Bounce parser extracts real/masked bounced email (`Inbox #1076` `s***@profithelm.com`, `ciso@gainhelm.com`)
       with `reconciled == False` rather than `https://` URLs.
     - Full `lienbond` partner domain and token mapping.
  3. Partner tracker, Human Action Bus, Cloudflare sync, playbook isolation, and revenue truth:
     - No self-cancelling auto-`RESOLVE` gates on `HumanActionBus`.
     - Honest `production_monetization_score` (never 100.0 when `monetization_readiness_score == 0.0`).
     - First-class `lienbond` support across `partner_tracker.py`, `cli.py`, `ui.py`, and `revenue_truth.py`.
     - Zero cross-tenant bleed in `render_transactional_playbook_email` for `lienbond`.
     - Follow-up dispatcher atomicity (`allow_live_send`, Impact `#16354` Xendoo URL, pre-send dash & ledger write checks).
     - Dedicated `CF_LEADS_KV_NAMESPACES`, `CF_TELEMETRY_KV_NAMESPACES`, and `TELEMETRY_EXPORT_SECRET` binding.
     - Honest `SESSION_EXPIRED_CACHED_SNAPSHOT` portal status when unpolled + CoinLedger 37 verified clicks.
  4. Strictly zero U+2014 / U+2013 across all Cluster 2 owned files.

Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
from unittest.mock import patch

import pytest

from pseofactory.action_bus import HumanActionBus
from pseofactory.cli import build_parser
from pseofactory.content_angles import call_stateless_vertex_json
from pseofactory.email_ingest import (
    ZOHO_POLL_MAILBOXES,
    EmailIngestionEngine,
    EmailMessage,
    _extract_bounced_recipient,
    _has_human_partner_question,
    _is_automated_sender,
    compute_stable_email_cache_key,
)
from pseofactory.partner_tracker import (
    CANONICAL_ZOHO_SENDER_EMAIL,
    CF_LEADS_KV_NAMESPACES,
    CF_TELEMETRY_KV_NAMESPACES,
    PartnerStatusReport,
    PartnerTrackingEngine,
    _is_synthetic_or_unroutable_probe_email,
    _normalize_canonical_sender_email,
    create_stripe_checkout_session,
    dispatch_transactional_playbook,
    render_transactional_playbook_email,
    resolve_lead_monetization_offer,
    send_partner_correspondence_via_zoho,
    settle_post_calculation_datapack_upgrade,
    sync_cloudflare_pages_lead_credentials,
)
from pseofactory.revenue_truth import ACTIVE_PSEOFACTORY_PROPERTIES, collect_pseofactory_truth
from pseofactory.ui import render_light_interface


WORKTREE_ROOT = Path(__file__).resolve().parent.parent


def _make_isolated_tracker(tmp_path: Path) -> Tuple[PartnerTrackingEngine, HumanActionBus, EmailIngestionEngine]:
    bus = HumanActionBus(bus_path=str(tmp_path / "human_action_bus.json"))
    email_engine = EmailIngestionEngine(
        cache_path=str(tmp_path / "zoho_inbox_cache.json"),
        state_path=str(tmp_path / "email_sync_state.json"),
    )
    tracker = PartnerTrackingEngine(action_bus=bus, email_engine=email_engine)
    return tracker, bus, email_engine


def test_canonical_identity_and_split_brain_elimination(tmp_path: Path) -> None:
    sig = inspect.signature(call_stateless_vertex_json)
    assert sig.parameters["account"].default == "arif.coskun@profithelm.com"
    assert CANONICAL_ZOHO_SENDER_EMAIL == "arif.coskun@profithelm.com"

    # Personal / Gmail / MindBall split-brain is eliminated by default
    email_engine = EmailIngestionEngine(
        cache_path=str(tmp_path / "cache.json"),
        state_path=str(tmp_path / "state.json"),
    )
    assert email_engine.ingest_personal() == []

    personal_inbox_path = WORKTREE_ROOT / ".agy" / "personal_inbox.json"
    assert json.loads(personal_inbox_path.read_text(encoding="utf-8")) == []

    bus_data = json.loads((WORKTREE_ROOT / ".agy" / "human_action_bus.json").read_text(encoding="utf-8"))
    actions_map = bus_data.get("actions", {})
    assert len(actions_map) == bus_data["bus_metadata"]["total_items"]
    assert len(actions_map) > 0
    for act_id, item in actions_map.items():
        assert not str(act_id).startswith("act-email-pers-")
        assert not str(item.get("action_id") or "").startswith("act-email-pers-")
        assert not str(item.get("source_email_id") or "").startswith("pers-")


def test_outbound_sender_normalization_and_anti_bounce_guard() -> None:
    for legacy_sender in (
        "",
        "arif@profithelm.com",
        "noreply@prexvo.com",
        "arif@gainhelm.com",
        "arif@lienbond.com",
        "ciso@gainhelm.com",
    ):
        assert _normalize_canonical_sender_email(legacy_sender) == "arif.coskun@profithelm.com"
        dry_res = send_partner_correspondence_via_zoho(
            to_email="affiliates@koinly.io",
            subject="ProfitHelm Partner Check-In",
            body_text="Checking in on ProfitHelm tracking integration.",
            execute_live=False,
            from_email=legacy_sender or CANONICAL_ZOHO_SENDER_EMAIL,
        )
        assert dry_res["from_email"] == "arif.coskun@profithelm.com"

    # Reject masked (*), synthetic role probes, and unprovisioned internal domains
    for bad_addr in (
        "a***@profithelm.com",
        "s***@profithelm.com",
        "ciso@gainhelm.com",
        "ciso@company.io",
        "audit@gainhelm.com",
        "audit@vendor.com",
        "grc-controller@enterprise.org",
        "arif@gainhelm.com",
        "arif@lienbond.com",
        "noreply@prexvo.com",
        "arif@profithelm.com",
    ):
        assert _is_synthetic_or_unroutable_probe_email(bad_addr) is True, f"Expected bounce guard for {bad_addr}"

    # Allow canonical operator address and legitimate external recipients
    assert _is_synthetic_or_unroutable_probe_email("arif.coskun@profithelm.com") is False
    assert _is_synthetic_or_unroutable_probe_email("allwyn.symon@eztaxreturn.com") is False
    assert _is_synthetic_or_unroutable_probe_email("cfo@realcontractor.net") is False

    # Live playbook dispatch suppresses masked / synthetic addresses before any HTTP call
    suppressed = dispatch_transactional_playbook(
        {
            "property_id": "profithelm",
            "email": "s***@profithelm.com",
            "tool_slug": "section-179-calculator",
            "lead_id": "lead_masked_01",
        },
        execute_live=True,
    )
    assert suppressed["dispatched"] is False
    assert suppressed["status"] == "synthetic_probe_email_suppressed"
    assert suppressed["from_email"] == "arif.coskun@profithelm.com"


def test_stable_rfc_message_id_cache_key_and_full_zoho_mailbox_coverage(tmp_path: Path) -> None:
    assert ZOHO_POLL_MAILBOXES == ("Inbox", "Sent", "Notification", "Newsletter", "Spam")

    k1 = compute_stable_email_cache_key(
        mailbox="Inbox",
        message_id_hdr="<CAB12345.ezTax@mail.eztaxreturn.com>",
        subject="Approved in CJ",
        date_str="2026-10-28T14:00:00Z",
        sender_email="allwyn.symon@ezTaxReturn.com",
    )
    k2 = compute_stable_email_cache_key(
        mailbox="Inbox",
        message_id_hdr="cab12345.eztax@mail.eztaxreturn.com",
        subject="Approved in CJ",
        date_str="2026-10-28T14:00:00Z",
        sender_email="allwyn.symon@ezTaxReturn.com",
    )
    assert k1 == "cab12345.eztax@mail.eztaxreturn.com"
    assert k1 == k2

    # Volatile numeric sequence IDs are rejected in favor of deterministic hash fallback when header absent
    fallback_key = compute_stable_email_cache_key(
        mailbox="Notification",
        message_id_hdr="1074",
        subject="CJ Program Terms",
        date_str="2026-10-28T15:00:00Z",
        sender_email="noreply@cj.com",
    )
    assert len(fallback_key) == 64
    assert fallback_key != "1074"

    engine = EmailIngestionEngine(
        cache_path=str(tmp_path / "zoho_cache.json"),
        state_path=str(tmp_path / "zoho_state.json"),
        himalaya_bin="/usr/bin/fake-himalaya",
    )

    recorded_cmds: List[List[str]] = []
    seq_number = {"val": "1074"}

    def fake_run(args: List[str]) -> Tuple[int, str, str]:
        recorded_cmds.append(args)
        if args[:2] == ["envelope", "list"]:
            folder = args[args.index("-m") + 1]
            if folder == "Inbox":
                return (
                    0,
                    json.dumps(
                        {
                            "envelopes": [
                                {
                                    "id": seq_number["val"],
                                    "message_id": "<stable-rfc-id-1074@eztaxreturn.com>",
                                    "date": "2026-10-28 14:22:00+00:00",
                                    "subject": "ezTaxReturn CJ Affiliate Application",
                                    "from": [{"name": "Allwyn Symon", "email": "allwyn.symon@ezTaxReturn.com"}],
                                    "flags": [{"iana": "Seen"}],
                                }
                            ]
                        }
                    ),
                    "",
                )
            return 0, json.dumps({"envelopes": []}), ""
        if args[:2] == ["message", "read"]:
            return (
                0,
                "Message-ID: <stable-rfc-id-1074@eztaxreturn.com>\n\n"
                "I went ahead and approved your application in CJ! Could you share how you envision that placement?",
                "",
            )
        return 1, "", "unexpected"

    with patch.object(engine, "run_himalaya_command", side_effect=fake_run):
        msgs_run1 = engine.sync_all(force=True)
        # Verify all 5 Zoho folders were polled with -a zoho and -s 200 (zero personal/mindball calls)
        env_calls = [c for c in recorded_cmds if c[:2] == ["envelope", "list"]]
        polled_folders = [c[c.index("-m") + 1] for c in env_calls]
        assert polled_folders == ["Inbox", "Sent", "Notification", "Newsletter", "Spam"]
        for c in env_calls:
            assert c[c.index("-a") + 1] == "zoho"
            assert c[c.index("-s") + 1] == "200"

        assert len(msgs_run1) == 1
        cache_after_run1 = engine.load_cache()
        assert "stable-rfc-id-1074@eztaxreturn.com" in cache_after_run1["messages"]
        assert "1074" not in cache_after_run1["messages"]

        # Simulate IMAP expunge shifting folder sequence ID from 1074 -> 1069:
        # stable Message-ID cache hit must prevent redundant `message read` and never duplicate cache entries.
        recorded_cmds.clear()
        seq_number["val"] = "1069"
        msgs_run2 = engine.sync_all(force=True)
        read_calls_run2 = [c for c in recorded_cmds if c[:2] == ["message", "read"]]
        assert read_calls_run2 == []
        assert len(msgs_run2) == 1
        cache_after_run2 = engine.load_cache()
        assert list(cache_after_run2["messages"].keys()) == ["stable-rfc-id-1074@eztaxreturn.com"]


def test_inbox_1074_partner_manager_question_is_not_swallowed(tmp_path: Path) -> None:
    _, bus, email_engine = _make_isolated_tracker(tmp_path)

    # Pre-seed an already resolved automated approval card to prove a newer human question is never swallowed
    msg_auto_approved = EmailMessage(
        id="990",
        message_id="<cj-auto-990@cj.com>",
        account="zoho",
        mailbox="Notification",
        date="2026-10-28T12:00:00Z",
        subject="ezTaxReturn approved your CJ Affiliate application",
        sender_name="CJ Affiliate",
        sender_email="noreply@cj.com",
        body_snippet="Congratulations! Your application to ezTaxReturn has been approved.",
    )
    msg_1074 = EmailMessage(
        id="1074",
        message_id="<msg-1074@eztaxreturn.com>",
        account="zoho",
        mailbox="Inbox",
        date="2026-10-29T16:10:00Z",
        subject="Re: ezTaxReturn Affiliate Program - ProfitHelm",
        sender_name="Allwyn Symon",
        sender_email="allwyn.symon@ezTaxReturn.com",
        body_snippet=(
            "Hi Arif, I went ahead and approved your application in CJ! "
            "Could you share how you envision that placement and when you'd be able to start promoting us?"
        ),
    )

    classifications = email_engine.classify_partner_emails([msg_auto_approved, msg_1074])
    ez_cls = next(c for c in classifications if c.email_id == "1074")
    assert ez_cls.requires_operator_decision is True
    assert ez_cls.urgency in ("HIGH", "CRITICAL")
    assert any(
        "Allwyn Symon" in req or "allwyn.symon@eztaxreturn.com" in req.lower()
        for req in ez_cls.missing_requirements
    )

    # Route and resolve an initial card, then route msg_1074 with a new email_id: must emit PENDING_OPERATOR
    initial_item = bus.route_classification(ez_cls)
    assert initial_item is not None
    initial_item.source_email_id = "990"
    bus.confirm_decision(
        initial_item.action_id,
        decision="RESOLVE",
        operator="arif",
        notes="Initial CJ contract acknowledged.",
    )

    followup_item = bus.route_classification(ez_cls)
    assert followup_item is not None
    assert followup_item.status == "PENDING_OPERATOR"
    pending_ids = [item.action_id for item in bus.get_pending_items()]
    assert followup_item.action_id in pending_ids


def test_inbox_1072_appeal_rejection_and_zero_fabricated_anomalies(tmp_path: Path) -> None:
    _, _, email_engine = _make_isolated_tracker(tmp_path)

    # Empty message list MUST return 0 bounces, 0 stale drafts, 0 check-ins, and 0 declines
    empty_report = email_engine.analyze_correspondence_anomalies_and_checkins([], fetch_live=False)
    assert empty_report["hard_bounces_count"] == 0
    assert empty_report["hard_bounces"] == []
    assert empty_report["stale_drafts_count"] == 0
    assert empty_report["stale_drafts"] == []
    assert empty_report["unanswered_partner_checkins_count"] == 0
    assert empty_report["unanswered_partner_checkins"] == []
    assert empty_report["declined_campaigns_count"] == 0

    msg_1025 = EmailMessage(
        id="1025",
        message_id="<impact-1025@impact.com>",
        account="zoho",
        mailbox="Inbox",
        date="2026-10-25T10:00:00Z",
        subject="Sorry, your partnership request was declined by Invoice Simple",
        sender_name="Impact Notifications",
        sender_email="noreply@impact.com",
        body_snippet="Your application to join Invoice Simple on Impact.com was declined.",
    )
    msg_1072 = EmailMessage(
        id="1072",
        message_id="<nina-1072@hamstergarage.com>",
        account="zoho",
        mailbox="Inbox",
        date="2026-10-29T18:30:00Z",
        subject="Re: Sorry, your partnership request was declined by Invoice Simple",
        sender_name="Nina Gentles",
        sender_email="nina.gentles@hamstergarage.com",
        body_snippet=(
            "Hi Arif, thanks for reaching out. Unfortunately we are unable to approve ProfitHelm "
            "for the Invoice Simple affiliate program at this time."
        ),
    )

    cls_1072 = email_engine.classify_partner_emails([msg_1072])
    assert len(cls_1072) == 1
    assert cls_1072[0].email_id == "1072"
    assert cls_1072[0].partner_key == "invoice_simple"
    assert cls_1072[0].classification_type == "APPLICATION_DECLINED"

    anomaly_rep = email_engine.analyze_correspondence_anomalies_and_checkins(
        [msg_1025, msg_1072], fetch_live=False
    )
    assert anomaly_rep["declined_campaigns_count"] == 1
    inv_dec = anomaly_rep["declined_campaigns_with_appeals"][0]
    assert inv_dec["email_id"] == "1072"
    assert inv_dec["partner_key"] == "invoice_simple"
    assert inv_dec["status"] == "declined"
    assert inv_dec["appeal_status"] == "APPEAL_REJECTED_FINAL"
    assert inv_dec["appeal_active"] is False
    assert inv_dec["dispatch_key"] is None


def test_inbox_1076_masked_bounce_parser_and_unreconciled_default(tmp_path: Path) -> None:
    _, _, email_engine = _make_isolated_tracker(tmp_path)

    bounce_body = (
        "This message was created automatically by mail delivery software.\n"
        "Delivery to the following recipient failed permanently:\n\n"
        "    s***@profithelm.com\n\n"
        "Technical details of permanent failure: 550 5.1.1 Unrouteable address.\n"
        "For postmaster troubleshooting see https://mail.zoho.com/postmaster/bounce-codes"
    )
    assert _extract_bounced_recipient(bounce_body, sender_email="mailer-daemon@mail.zoho.com") == "s***@profithelm.com"

    msg_1076 = EmailMessage(
        id="1076",
        message_id="<bounce-1076@mail.zoho.com>",
        account="zoho",
        mailbox="Inbox",
        date="2026-10-30T09:15:00Z",
        subject="Mail delivery failed: returning message to sender",
        sender_name="Mail Delivery System",
        sender_email="mailer-daemon@mail.zoho.com",
        body_snippet=bounce_body,
    )
    msg_ciso = EmailMessage(
        id="1077",
        message_id="<bounce-1077@mail.zoho.com>",
        account="zoho",
        mailbox="Inbox",
        date="2026-10-30T09:16:00Z",
        subject="Undelivered Mail Returned to Sender",
        sender_name="Mail Delivery System",
        sender_email="mailer-daemon@zoho.com",
        body_snippet="550 5.1.1 <ciso@gainhelm.com>: Recipient address rejected: User unknown",
    )

    rep = email_engine.analyze_correspondence_anomalies_and_checkins([msg_1076, msg_ciso], fetch_live=False)
    assert rep["hard_bounces_count"] == 2
    by_id = {b["email_id"]: b for b in rep["hard_bounces"]}
    assert by_id["1076"]["bounced_recipient"] == "s***@profithelm.com"
    assert not by_id["1076"]["bounced_recipient"].startswith("https://")
    assert by_id["1076"]["reconciled"] is False
    assert by_id["1076"]["property_id"] == "profithelm"

    assert by_id["1077"]["bounced_recipient"] == "ciso@gainhelm.com"
    assert by_id["1077"]["reconciled"] is False
    assert by_id["1077"]["property_id"] == "gainhelm"


def test_lienbond_partner_email_mapping_and_first_class_fleet_readiness(tmp_path: Path) -> None:
    tracker, bus, email_engine = _make_isolated_tracker(tmp_path)

    lb_messages = [
        EmailMessage(
            id="2001",
            message_id="<thimble-2001@thimble.com>",
            account="zoho",
            mailbox="Notification",
            date="2026-11-01T12:00:00Z",
            subject="Welcome to the Thimble Contractor Insurance Affiliate Program",
            sender_name="Thimble Partnerships",
            sender_email="partners@thimble.com",
            body_snippet="Your LienBond publisher application has been approved! Start promoting https://thimble.com",
        ),
        EmailMessage(
            id="2002",
            message_id="<sbd-2002@suretybonds.com>",
            account="zoho",
            mailbox="Inbox",
            date="2026-11-01T13:00:00Z",
            subject="SuretyBonds.com Affiliate Application Received for LienBond.com",
            sender_name="SuretyBonds Partnerships",
            sender_email="affiliates@suretybonds.com",
            body_snippet="Thank you for applying with https://lienbond.com to promote contractor license bonds.",
        ),
    ]
    cls_list = email_engine.classify_partner_emails(lb_messages)
    by_eid = {c.email_id: c for c in cls_list}
    assert by_eid["2001"].partner_key == "thimble_contractor"
    assert by_eid["2001"].property_id == "lienbond"
    assert by_eid["2002"].partner_key == "suretybonds_direct"
    assert by_eid["2002"].property_id == "lienbond"

    rep = tracker.sync_and_evaluate(force_mail_poll=False)
    assert isinstance(rep, PartnerStatusReport)
    assert rep.lienbond.property_id == "lienbond"

    # Honest production_monetization_score invariant: 0% affiliate readiness NEVER reports 100% production score
    for prop_rep in (rep.profithelm, rep.prexvo, rep.gainhelm, rep.lienbond):
        assert not (
            prop_rep.monetization_readiness_score == 0.0
            and prop_rep.production_monetization_score == 100.0
        )
        if prop_rep.monetization_readiness_score == 0.0:
            assert prop_rep.production_monetization_ready is False
            assert prop_rep.production_monetization_score <= 40.0

    # Standing operator gates must NOT self-cancel via autonomous_revenue_pivot
    all_items = list(bus.items.values())
    auto_resolved = [i for i in all_items if i.resolved_by == "autonomous_revenue_pivot"]
    assert auto_resolved == []
    lb_standing = bus.items.get("act-lienbond-suretybonds-direct-partner-approval")
    assert lb_standing is not None
    assert lb_standing.status == "PENDING_OPERATOR"
    assert "not yet provisioned in DNS" not in (lb_standing.operator_notes or "")
    assert "4544498" not in lb_standing.description


def test_lienbond_playbook_email_has_zero_cross_tenant_bleed() -> None:
    rendered = render_transactional_playbook_email(
        {
            "property_id": "lienbond",
            "email": "estimator@pacificbuilders.com",
            "lead_id": "lb_lead_9001",
            "tool_slug": "contractor-license-bond-cost-calculator-by-credit-score",
            "state_code": "CA",
            "amount_modeled": 50000,
        }
    )
    assert rendered["subject"].startswith("[LienBond Playbook]")
    assert "https://lienbond.com/" in rendered["playbook_endpoint"]
    assert "https://lienbond.com/" in rendered["checkout_endpoint"]
    assert rendered["partner_url"].startswith("https://lienbond.com/r/suretybonds_direct")
    assert "profithelm.com" not in rendered["html_body"]
    assert "profithelm.com" not in rendered["text_body"]
    assert "/r/turbotax" not in rendered["html_body"]
    assert "/r/turbotax" not in rendered["text_body"]


def test_cli_and_ui_first_class_lienbond_support(tmp_path: Path) -> None:
    tracker, _, _ = _make_isolated_tracker(tmp_path)
    rep = tracker.sync_and_evaluate(force_mail_poll=False)

    parser = build_parser()
    args_status = parser.parse_args(["partner-status", "--property", "lienbond", "--json"])
    assert args_status.property == "lienbond"
    args_sync = parser.parse_args(["sync-monetization", "--property", "lienbond"])
    assert args_sync.property == "lienbond"
    args_audit = parser.parse_args(["audit", "--property", "lienbond"])
    assert args_audit.property == "lienbond"
    args_gsc = parser.parse_args(["gsc-ceiling", "--property", "lienbond"])
    assert args_gsc.property == "lienbond"

    html_doc = render_light_interface(rep)
    assert "LienBond Readiness" in html_doc
    assert "filterActions('lienbond', event)" in html_doc
    assert 'data-property="lienbond"' in html_doc
    assert 'id="section-lienbond"' in html_doc
    assert "Personal Cache" not in html_doc
    assert "and personal inbox" not in html_doc


def test_followup_dispatcher_atomicity_allow_live_send_and_xendoo_impact_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tracker, _, _ = _make_isolated_tracker(tmp_path)
    ledger_file = tmp_path / "followup_ledger.json"

    # 1. Verify Xendoo Impact #16354 link & Invoice Simple canonical partner_key in dry-run
    dry = tracker.dispatch_autonomous_partner_followups(
        execute_live=False,
        ledger_path=str(ledger_file),
        allow_live_send=False,
    )
    by_key = {r["action_key"]: r for r in dry["actions"]}
    xendoo_body = by_key["xendoo_firstpromoter_checkin_reply"]["body_text"]
    assert "https://xendoo.pxf.io/c/7932737/1357375/16354" in xendoo_body
    assert "xendoo.com?fpr=arif33" not in xendoo_body
    assert by_key["invoice_simple_impact_appeal"]["partner_key"] == "invoice_simple"

    # 2. Verify allow_live_send=False blocks live send even when execute_live=True and PYTEST_CURRENT_TEST is unset
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    live_flags_seen: List[bool] = []

    def spy_send(to_email: str, subject: str, body_text: str, execute_live: bool = False, **kwargs: Any) -> Dict[str, Any]:
        live_flags_seen.append(execute_live)
        return {
            "dispatched": execute_live,
            "status": "sent_zoho_oauth" if execute_live else "dry_run_ready",
            "provider": "zoho_mail_oauth",
            "to_email": to_email,
            "from_email": CANONICAL_ZOHO_SENDER_EMAIL,
            "subject": subject,
            "http_status": 200 if execute_live else None,
            "message_id": "<msg@zoho>" if execute_live else None,
            "mail_id": "m1" if execute_live else None,
        }

    with patch("pseofactory.partner_tracker.send_partner_correspondence_via_zoho", side_effect=spy_send):
        tracker.dispatch_autonomous_partner_followups(
            execute_live=True,
            ledger_path=str(tmp_path / "blocked_live_ledger.json"),
            allow_live_send=False,
        )
    assert live_flags_seen and all(flag is False for flag in live_flags_seen)

    # 3. Verify unwritable ledger path (directory collision) raises BEFORE invoking send_partner_correspondence_via_zoho
    unwritable_dir_path = tmp_path / "unwritable_ledger_dir"
    unwritable_dir_path.mkdir()
    send_called = False

    def fail_if_called(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        nonlocal send_called
        send_called = True
        raise AssertionError("send_partner_correspondence_via_zoho must NEVER be called when ledger is unwritable")

    with patch("pseofactory.partner_tracker.send_partner_correspondence_via_zoho", side_effect=fail_if_called):
        with pytest.raises(IsADirectoryError):
            tracker.dispatch_autonomous_partner_followups(
                execute_live=True,
                ledger_path=str(unwritable_dir_path),
                allow_live_send=True,
            )
    assert send_called is False


def test_cloudflare_kv_namespaces_and_pages_binding_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    assert CF_LEADS_KV_NAMESPACES == {
        "profithelm": "983a21b6fcd54fbb884740017b7d96f1",
        "prexvo": "320285659c4c494187fbf4665290ba93",
        "gainhelm": "31cdc2315c1e4c808a3c2f0b917cafbd",
        "lienbond": "c6885b9faff44e3abbb91cadebf137a9",
    }
    assert CF_TELEMETRY_KV_NAMESPACES == {
        "profithelm": "8c56efedd6214424b83e0e298c33ba27",
        "prexvo": "153917b16871453a9f07bfb39ff3fd98",
        "gainhelm": "d7e2021ef7cf47eea4ae382742481e75",
        "lienbond": "802b129f39344707898e156494aff45d",
    }

    monkeypatch.setenv("TELEMETRY_EXPORT_SECRET", "tel_secret_test_999")
    captured_patches: Dict[str, Dict[str, Any]] = {}

    class DummyResp:
        status = 200

        def __enter__(self) -> "DummyResp":
            return self

        def __exit__(self, *exc: Any) -> None:
            return None

        def read(self) -> bytes:
            return b'{"success": true}'

    def fake_urlopen(req: Any, timeout: int = 20) -> DummyResp:
        proj_name = req.full_url.rstrip("/").split("/")[-1]
        captured_patches[proj_name] = json.loads(req.data.decode("utf-8"))
        return DummyResp()

    with (
        patch("pseofactory.partner_tracker._load_email_engine_credentials", return_value={"TELEMETRY_EXPORT_SECRET": "tel_secret_test_999"}),
        patch("pseofactory.partner_tracker._load_stripe_credentials", return_value={"account_id": "acct_test"}),
        patch("pseofactory.partner_tracker._load_wrangler_oauth_token", return_value="cf_tok_test"),
        patch("urllib.request.urlopen", side_effect=fake_urlopen),
    ):
        sync_rep = sync_cloudflare_pages_lead_credentials(execute_live=True)

    assert set(sync_rep["projects"].keys()) == {"profithelm", "prexvo", "gainhelm", "lienbond"}
    for prop, proj_key in (
        ("profithelm", "profithelm"),
        ("prexvo", "prexvo"),
        ("gainhelm", "gainhelm"),
        ("lienbond", "lienbond"),
    ):
        patch_doc = captured_patches[proj_key]
        prefix = prop.upper()
        for env_name in ("production", "preview"):
            cfg = patch_doc["deployment_configs"][env_name]
            env_vars = cfg["env_vars"]
            assert env_vars["TELEMETRY_EXPORT_SECRET"]["value"] == "tel_secret_test_999"
            assert env_vars["ZOHO_FROM_EMAIL"]["value"] == "arif.coskun@profithelm.com"
            assert env_vars["ZEPTOMAIL_FROM_EMAIL"]["value"] == "arif.coskun@profithelm.com"
            kv_ns = cfg["kv_namespaces"]
            assert kv_ns[f"{prefix}_LEADS"] == {"namespace_id": CF_LEADS_KV_NAMESPACES[prop]}
            assert kv_ns[f"{prefix}_TELEMETRY_KV"] == {"namespace_id": CF_TELEMETRY_KV_NAMESPACES[prop]}


def test_revenue_truth_session_expired_snapshots_coinledger_37_and_falsifier(tmp_path: Path) -> None:
    assert ACTIVE_PSEOFACTORY_PROPERTIES == ("profithelm", "prexvo", "gainhelm", "lienbond")

    ledger_path = WORKTREE_ROOT / ".agy" / "partner_earnings_ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    portals = ledger["portals"]

    for gated_key in (
        "firstpromoter_coinledger",
        "firstpromoter_xendoo",
        "koinly_native",
        "sovrn_commerce",
        "cj_affiliate",
        "impact",
    ):
        assert portals[gated_key]["auth_status"] == "SESSION_EXPIRED_CACHED_SNAPSHOT"
        assert portals[gated_key]["is_authenticated_and_syncing"] is False

    assert portals["firstpromoter_coinledger"]["portal_verified_clicks"] == 37
    cl_rec = ledger["partners"]["coinledger"]
    assert cl_rec["portal_verified_clicks"] == 37
    assert cl_rec["is_authenticated_and_syncing"] is False

    truth = collect_pseofactory_truth(package_root=WORKTREE_ROOT, live_network=False)
    for gated_key in (
        "firstpromoter_coinledger",
        "firstpromoter_xendoo",
        "koinly_native",
        "sovrn_commerce",
        "cj_affiliate",
        "impact",
    ):
        assert truth["affiliate_networks"][gated_key]["status"] == "SESSION_EXPIRED_CACHED_SNAPSHOT"
        assert truth["affiliate_networks"][gated_key]["is_authenticated_and_syncing"] is False
    assert truth["affiliate_networks"]["firstpromoter_coinledger"]["clicks"] == 37
    assert set(truth["properties"].keys()) == {"profithelm", "prexvo", "gainhelm", "lienbond"}

    # Falsifier report contains no false hardcoded claims about live-authenticated portals or stale Oct 27 bounces
    tracker, _, _ = _make_isolated_tracker(tmp_path)
    fals_out = tmp_path / "falsification_report.json"
    with patch.object(
        tracker,
        "sync_partner_earnings_and_balances",
        wraps=lambda fetch_live_api=False: tracker.__class__.sync_partner_earnings_and_balances(
            tracker, fetch_live_api=fetch_live_api, ledger_path=str(tmp_path / "earnings_tmp.json")
        ),
    ):
        fals_rep = tracker.falsify_monetization_and_partner_health(
            execute_live=False, persist_path=str(fals_out)
        )
    serialized_fals = json.dumps(fals_rep)
    assert "All 6 affiliate portals are live-authenticated" not in serialized_fals
    assert "\u2014" not in serialized_fals
    assert "\u2013" not in serialized_fals


def test_redteam_bug_1_3_zero_synthetic_email_fabrication_and_optional_stripe_email(tmp_path: Path) -> None:
    leads_file = tmp_path / "captured_leads.jsonl"

    # 1. Omitted / blank customer_email must NOT synthesize audit@profithelm.com or pass customer_email to Stripe
    upgrade_blank = settle_post_calculation_datapack_upgrade(
        property_id="profithelm",
        tool_slug="1031-exchange-boot-calculator",
        customer_email="",
        sku="ph_1031_boot_waterfall_kit",
        calculated_amount=850000,
        execute_live_checkout=False,
        leads_ledger_path=str(leads_file),
    )
    assert upgrade_blank["checkout_session"]["customer_email"] == ""
    assert "audit@profithelm.com" not in json.dumps(upgrade_blank)
    assert "customer_email" not in upgrade_blank["checkout_session"]["request_payload"]

    # Also verify paid settlement path with omitted customer_email writes email == "" (never audit@<prop>.com)
    settled_blank = settle_post_calculation_datapack_upgrade(
        property_id="profithelm",
        tool_slug="1031-exchange-boot-calculator",
        lead_id="lead_real_buyer_blank_email_01",
        customer_email="",
        sku="ph_1031_boot_waterfall_kit",
        calculated_amount=850000,
        execute_live_checkout=False,
        leads_ledger_path=str(leads_file),
        verified_payment={
            "session_id": "cs_live_real_blank_001",
            "payment_status": "paid",
            "amount_total_cents": 7900,
        },
    )
    assert settled_blank["settled"] is True
    assert "audit@profithelm.com" not in json.dumps(settled_blank)

    # 2. Synthetic customer_email (audit@profithelm.com) must also be stripped to "" and never persisted as real email
    upgrade_synth = settle_post_calculation_datapack_upgrade(
        property_id="profithelm",
        tool_slug="section-179-depreciation-calculator",
        lead_id="lead_probe_email_02",
        customer_email="audit@profithelm.com",
        sku="ph_section179_macrs_audit_kit",
        calculated_amount=125000,
        execute_live_checkout=False,
        leads_ledger_path=str(leads_file),
        verified_payment={
            "session_id": "cs_live_probe_002",
            "payment_status": "paid",
            "amount_total_cents": 4900,
        },
    )
    assert upgrade_synth["checkout_session"]["customer_email"] == ""
    assert "customer_email" not in upgrade_synth["checkout_session"]["request_payload"]

    assert leads_file.exists()
    ledger_raw = leads_file.read_text(encoding="utf-8")
    assert "audit@profithelm.com" not in ledger_raw
    assert "audit@gainhelm.com" not in ledger_raw
    assert "audit@lienbond.com" not in ledger_raw
    assert "audit@prexvo.com" not in ledger_raw
    persisted_rows = [json.loads(ln) for ln in ledger_raw.splitlines() if ln.strip()]
    assert len(persisted_rows) == 1
    assert persisted_rows[0]["lead_id"] == "lead_real_buyer_blank_email_01"
    assert persisted_rows[0]["email"] == ""

    # 3. Direct create_stripe_checkout_session checks
    s_empty = create_stripe_checkout_session(
        property_id="profithelm",
        customer_email="",
        lead_id="lead_no_email_01",
        tool_slug="1031-exchange-boot-calculator",
        sku="ph_1031_boot_waterfall_kit",
        execute_live=False,
    )
    assert s_empty["customer_email"] == ""
    assert "customer_email" not in s_empty["request_payload"]

    s_synth = create_stripe_checkout_session(
        property_id="gainhelm",
        customer_email="ciso@acme.com",
        lead_id="lead_synth_email_02",
        tool_slug="soc-2-cost-calculator",
        execute_live=False,
    )
    assert s_synth["customer_email"] == ""
    assert "customer_email" not in s_synth["request_payload"]

    s_valid = create_stripe_checkout_session(
        property_id="profithelm",
        customer_email="controller@realmanufacturing.com",
        lead_id="lead_real_email_03",
        tool_slug="section-179-depreciation-calculator",
        sku="ph_section179_macrs_audit_kit",
        execute_live=False,
    )
    assert s_valid["request_payload"]["customer_email"] == "controller@realmanufacturing.com"


def test_redteam_bug_1_4_recipient_override_cannot_bypass_anti_bounce_guard() -> None:
    # Ensure @example.net and subdomains are blocked alongside @example.com / @example.org
    for blocked_override in (
        "arif@profithelm.com",
        "hello@lienbond.com",
        "a***@profithelm.com",
        "ciso@acme.com",
        "buyer@example.net",
        "buyer@mail.example.net",
    ):
        assert _is_synthetic_or_unroutable_probe_email(blocked_override) is True
        res = dispatch_transactional_playbook(
            {
                "property_id": "lienbond",
                "email": "estimator@realbuilder.com",
                "tool_slug": "contractor-license-bond-cost-calculator-by-credit-score",
                "lead_id": "lb_override_guard_test",
                "synthetic_test": False,
            },
            execute_live=True,
            recipient_override=blocked_override,
        )
        assert res["dispatched"] is False, f"recipient_override={blocked_override} bypassed anti-bounce guard!"
        assert res["status"] == "synthetic_probe_email_suppressed"

    # Genuine routable external addresses and canonical arif.coskun@profithelm.com are permitted when synthetic_test is False
    class FakeZeptoResp:
        status = 200

        def __enter__(self) -> "FakeZeptoResp":
            return self

        def __exit__(self, *exc: Any) -> None:
            return None

        def read(self) -> bytes:
            return b'{"request_id": "zepto_req_ok_01"}'

    for allowed_override in ("arif.coskun@profithelm.com", "estimator@realbuilder.com"):
        assert _is_synthetic_or_unroutable_probe_email(allowed_override) is False
        with (
            patch(
                "pseofactory.partner_tracker._load_email_engine_credentials",
                return_value={
                    "ZEPTOMAIL_TOKEN": "Zoho-enczapikey test_tok_123",
                    "ZEPTOMAIL_FROM_EMAIL": "arif.coskun@profithelm.com",
                },
            ),
            patch("urllib.request.urlopen", return_value=FakeZeptoResp()) as mock_urlopen,
        ):
            ok_res = dispatch_transactional_playbook(
                {
                    "property_id": "lienbond",
                    "email": "estimator@realbuilder.com",
                    "tool_slug": "contractor-license-bond-cost-calculator-by-credit-score",
                    "lead_id": "lb_override_valid_test",
                    "synthetic_test": False,
                },
                execute_live=True,
                recipient_override=allowed_override,
            )
            assert ok_res["dispatched"] is True
            assert ok_res["recipient_email"] == allowed_override
            assert mock_urlopen.called is True


def test_redteam_bug_2_4_inbound_vendor_responses_never_trapped_as_outbound_submitted(tmp_path: Path) -> None:
    _, _, email_engine = _make_isolated_tracker(tmp_path)

    messages = [
        EmailMessage(
            id="3001",
            message_id="<vanta-in-3001@vanta.com>",
            account="zoho",
            mailbox="Inbox",
            date="2026-11-02T10:00:00Z",
            subject="Welcome to the Vanta Partner Program",
            sender_name="Vanta Partnerships",
            sender_email="partners@vanta.com",
            body_snippet="Congratulations! Your Vanta partner application is approved. Here is your tracking link: https://vanta.com/?partner=gainhelm",
        ),
        EmailMessage(
            id="3002",
            message_id="<sofi-in-3002@sofi.com>",
            account="zoho",
            mailbox="Inbox",
            date="2026-11-02T10:05:00Z",
            subject="Your SoFi Affiliate Application is Approved",
            sender_name="SoFi Affiliates",
            sender_email="affiliates@sofi.com",
            body_snippet="Welcome aboard! Your SoFi student loan refinance tracking link is https://sofi.sjv.io/c/7932737/11190/999",
        ),
        EmailMessage(
            id="3003",
            message_id="<thimble-in-3003@thimble.com>",
            account="zoho",
            mailbox="Notification",
            date="2026-11-02T10:10:00Z",
            subject="Thimble Partner Application Update",
            sender_name="Thimble Partnerships",
            sender_email="partners@thimble.com",
            body_snippet="Unfortunately we are unable to approve your application at this time.",
        ),
        EmailMessage(
            id="3004",
            message_id="<splash-in-3004@splashfinancial.com>",
            account="zoho",
            mailbox="Inbox",
            date="2026-11-02T10:15:00Z",
            subject="Splash Financial Partner Approval - Prexvo",
            sender_name="Splash Partnerships",
            sender_email="contact@splashfinancial.com",
            body_snippet="Congratulations! Splash Financial approved Prexvo ($100 CPA). Tracking URL: https://splashfinancial.pxf.io/c/7932737/9516/1234",
        ),
        EmailMessage(
            id="3005",
            message_id="<vanta-sent-3005@profithelm.com>",
            account="zoho",
            mailbox="Sent",
            date="2026-11-01T09:00:00Z",
            subject="GainHelm x Vanta Partnership Inquiry",
            sender_name="Arif Coskun",
            sender_email="arif.coskun@profithelm.com",
            body_snippet="Hi Vanta team, applying for GainHelm SOC 2 calculator partnership.",
            raw_headers={"to_email": "partners@vanta.com"},
        ),
    ]

    cls_list = email_engine.classify_partner_emails(messages)
    by_id = {c.email_id: c for c in cls_list}

    assert by_id["3001"].property_id == "gainhelm"
    assert by_id["3001"].partner_key == "vanta_security"
    assert by_id["3001"].classification_type == "APPLICATION_APPROVED"
    assert by_id["3001"].candidate_url == "https://vanta.com/?partner=gainhelm"
    assert "Partnership inquiry sent to" not in by_id["3001"].summary

    assert by_id["3002"].property_id == "prexvo"
    assert by_id["3002"].partner_key == "sofi"
    assert by_id["3002"].classification_type == "APPLICATION_APPROVED"
    assert by_id["3002"].candidate_url == "https://sofi.sjv.io/c/7932737/11190/999"

    assert by_id["3003"].property_id == "lienbond"
    assert by_id["3003"].partner_key == "thimble_contractor"
    assert by_id["3003"].classification_type == "APPLICATION_DECLINED"

    assert by_id["3004"].property_id == "prexvo"
    assert by_id["3004"].partner_key == "splash_financial"
    assert by_id["3004"].classification_type == "APPLICATION_APPROVED"
    assert by_id["3004"].candidate_url == "https://splashfinancial.pxf.io/c/7932737/9516/1234"

    assert by_id["3005"].property_id == "gainhelm"
    assert by_id["3005"].partner_key == "vanta_security"
    assert by_id["3005"].classification_type == "APPLICATION_SUBMITTED"


def test_redteam_bug_2_5_hello_desks_broad_human_questions_and_dual_approval_question(tmp_path: Path) -> None:
    _, _, email_engine = _make_isolated_tracker(tmp_path)

    # 1. hello@ partner desks are human, NOT automated
    assert _is_automated_sender("hello@sprinto.com", "Sprinto Partnerships") is False
    assert _is_automated_sender("hello@cobalt.io", "Cobalt Partner Desk") is False
    assert _is_automated_sender("noreply@cj.com", "CJ Affiliate") is True

    # 2. Broad non-quoted '?' question detection without requiring 14 hardcoded phrases
    has_q_sprinto, req_sprinto = _has_human_partner_question(
        "hello@sprinto.com",
        "Ananya",
        "Re: GainHelm ISO 27001 Calculator Partnership",
        "Hi Arif,\nWhat monthly organic traffic do your ISO 27001 readiness calculators receive?\nBest, Ananya",
    )
    assert has_q_sprinto is True
    assert "hello@sprinto.com" in req_sprinto

    # Quoted '?' lines, URL query strings, and unsubscribe footers must NOT false-positive
    has_q_quoted, _ = _has_human_partner_question(
        "hello@sprinto.com",
        "Ananya",
        "Re: GainHelm Partnership",
        "Thanks for sending that over.\n> What monthly organic traffic do your calculators receive?\nhttps://sprinto.com/?utm_source=gainhelm&ref=123\nQuestions? Unsubscribe from these emails.",
    )
    assert has_q_quoted is False

    # 3. Dual approval + human question preserves APPLICATION_APPROVED AND sets requires_operator_decision=True
    dual_msg = EmailMessage(
        id="3101",
        message_id="<cobalt-dual-3101@cobalt.io>",
        account="zoho",
        mailbox="Inbox",
        date="2026-11-02T14:00:00Z",
        subject="Approved: GainHelm x Cobalt Partner Program",
        sender_name="Cobalt Partner Desk",
        sender_email="hello@cobalt.io",
        body_snippet=(
            "Hi Arif, we approved your application! Your referral link is https://cobalt.io/?partner=gainhelm\n"
            "Which pentest cost calculator pages will feature Cobalt first?"
        ),
    )
    cls_dual = email_engine.classify_partner_emails([dual_msg])
    assert len(cls_dual) == 1
    assert cls_dual[0].property_id == "gainhelm"
    assert cls_dual[0].partner_key == "cobalt_pentest"
    assert cls_dual[0].classification_type == "APPLICATION_APPROVED"
    assert cls_dual[0].requires_operator_decision is True
    assert cls_dual[0].urgency in ("HIGH", "CRITICAL")
    assert cls_dual[0].candidate_url == "https://cobalt.io/?partner=gainhelm"


def test_redteam_bug_2_6_same_minute_fallback_hash_collision_and_imap_shift(tmp_path: Path) -> None:
    engine = EmailIngestionEngine(
        cache_path=str(tmp_path / "collision_cache.json"),
        state_path=str(tmp_path / "collision_state.json"),
        himalaya_bin="/usr/bin/fake-himalaya",
    )

    # Two distinct CJ notifications arrive in the exact same minute with identical subject & sender
    # and NO message_id in envelope list JSON, then IMAP sequence numbers shift on the second sync!
    seq_state = {"first": "501", "second": "502"}
    read_mids: List[str] = []

    def fake_himalaya(args: List[str]) -> Tuple[int, str, str]:
        if args[:2] == ["envelope", "list"]:
            folder = args[args.index("-m") + 1]
            if folder == "Notification":
                return (
                    0,
                    json.dumps(
                        {
                            "envelopes": [
                                {
                                    "id": seq_state["first"],
                                    "date": "2026-11-02 10:15+00:00",
                                    "subject": "CJ Program Status Update",
                                    "from": [{"name": "CJ Affiliate", "email": "noreply@cj.com"}],
                                    "flags": [],
                                },
                                {
                                    "id": seq_state["second"],
                                    "date": "2026-11-02 10:15+00:00",
                                    "subject": "CJ Program Status Update",
                                    "from": [{"name": "CJ Affiliate", "email": "noreply@cj.com"}],
                                    "flags": [],
                                },
                            ]
                        }
                    ),
                    "",
                )
            return 0, json.dumps({"envelopes": []}), ""
        if args[:2] == ["message", "read"]:
            mid = args[2]
            read_mids.append(mid)
            if mid == seq_state["first"]:
                return (
                    0,
                    "Message-ID: <cj-alpha-freetaxusa@cj.com>\n\nYour application to FreeTaxUSA has been approved!",
                    "",
                )
            if mid == seq_state["second"]:
                return (
                    0,
                    "Message-ID: <cj-beta-wallethub@cj.com>\n\nYour application to WalletHub has been approved!",
                    "",
                )
        return 1, "", "unexpected"

    with patch.object(engine, "run_himalaya_command", side_effect=fake_himalaya):
        msgs_1 = engine.sync_all(force=True)
        assert len(msgs_1) == 2
        assert set(read_mids) == {"501", "502"}
        bodies_1 = {m.message_id: m.body_snippet for m in msgs_1}
        assert "FreeTaxUSA" in bodies_1["cj-alpha-freetaxusa@cj.com"]
        assert "WalletHub" in bodies_1["cj-beta-wallethub@cj.com"]

        # Shift IMAP sequence numbers (501, 502 -> 498, 499): collision in fallback hash MUST force
        # message read on both envelopes so message #2 is NEVER overwritten by message #1!
        read_mids.clear()
        seq_state["first"] = "498"
        seq_state["second"] = "499"
        msgs_2 = engine.sync_all(force=True)
        assert set(read_mids) == {"498", "499"}
        assert len(msgs_2) == 2
        bodies_2 = {m.message_id: m.body_snippet for m in msgs_2}
        assert "FreeTaxUSA" in bodies_2["cj-alpha-freetaxusa@cj.com"]
        assert "WalletHub" in bodies_2["cj-beta-wallethub@cj.com"]


def test_redteam_bug_3_1_suretybondsdirect_brand_alignment_and_bug_4_1_python_sku_parity(tmp_path: Path) -> None:
    _, bus, email_engine = _make_isolated_tracker(tmp_path)

    # 1. Bug 3.1: Display references standardized to SuretyBondsDirect.com across partner_tracker, action_bus, email_ingest
    for mod_rel in ("pseofactory/partner_tracker.py", "pseofactory/action_bus.py", "pseofactory/email_ingest.py"):
        mod_text = (WORKTREE_ROOT / mod_rel).read_text(encoding="utf-8")
        assert "SuretyBonds.com" not in mod_text, f"Stale SuretyBonds.com display string found in {mod_rel}"

    lb_mail = render_transactional_playbook_email(
        {
            "property_id": "lienbond",
            "email": "estimator@pacificbuilders.com",
            "lead_id": "lb_brand_check_01",
            "tool_slug": "contractor-license-bond-cost-calculator-by-credit-score",
        }
    )
    assert "SuretyBondsDirect.com" in lb_mail["html_body"]
    assert "SuretyBondsDirect.com" in lb_mail["text_body"]

    hv_item = bus.route_high_value_qualified_lead(
        property_id="lienbond",
        tool_slug="contractor-license-bond-cost-calculator-by-credit-score",
        email="estimator@pacificbuilders.com",
        state="CA",
        capital_band="250k_plus",
        calculated_amount=300000.0,
        partner_sharing_consent=True,
        partner_key="suretybonds_direct",
    )
    assert hv_item is not None
    assert "SuretyBondsDirect.com" in hv_item.description
    assert any("SuretyBondsDirect.com" in r for r in hv_item.missing_requirements)

    # Inbound email recognition works for BOTH suretybondsdirect.com AND suretybonds.com
    sb_msgs = [
        EmailMessage(
            id="3201",
            message_id="<sbd-direct-3201@suretybondsdirect.com>",
            account="zoho",
            mailbox="Inbox",
            date="2026-11-02T15:00:00Z",
            subject="SuretyBondsDirect Affiliate Approval for LienBond",
            sender_name="SuretyBondsDirect Team",
            sender_email="partners@suretybondsdirect.com",
            body_snippet="Your LienBond contractor bond affiliate application is approved! https://www.suretybondsdirect.com/?aff=lienbond",
        ),
        EmailMessage(
            id="3202",
            message_id="<sb-legacy-3202@suretybonds.com>",
            account="zoho",
            mailbox="Inbox",
            date="2026-11-02T15:05:00Z",
            subject="Re: LienBond Partnership Inquiry",
            sender_name="Surety Customer Care",
            sender_email="customercare@suretybonds.com",
            body_snippet="We received your LienBond inquiry and forwarded it to our partnership desk.",
        ),
    ]
    sb_cls = {c.email_id: c for c in email_engine.classify_partner_emails(sb_msgs)}
    assert sb_cls["3201"].partner_key == "suretybonds_direct"
    assert sb_cls["3201"].partner_name == "SuretyBondsDirect.com"
    assert sb_cls["3201"].classification_type == "APPLICATION_APPROVED"
    assert sb_cls["3202"].partner_key == "suretybonds_direct"
    assert sb_cls["3202"].partner_name == "SuretyBondsDirect.com"

    # 2. Bug 4.1: Python SKU parity with edge worker (ph_1031_boot_waterfall_kit, ph_section179_macrs_audit_kit, px_verified_partner_slot)
    offer_1031 = resolve_lead_monetization_offer(
        property_id="profithelm",
        tool_slug="1031-exchange-boot-calculator",
        sku="ph_1031_boot_waterfall_kit",
    )
    assert offer_1031["offer_sku"] == "ph_1031_boot_waterfall_kit"
    assert offer_1031["offer_price_usd"] == 79.0
    assert offer_1031["offer_price_cents"] == 7900

    offer_179 = resolve_lead_monetization_offer(
        property_id="profithelm",
        tool_slug="section-179-depreciation-calculator",
        sku="ph_section179_macrs_audit_kit",
    )
    assert offer_179["offer_sku"] == "ph_section179_macrs_audit_kit"
    assert offer_179["offer_price_usd"] == 49.0
    assert offer_179["offer_price_cents"] == 4900

    offer_px_slot = resolve_lead_monetization_offer(
        property_id="prexvo",
        tool_slug="student-loan-refinance-savings-calculator",
        sku="px_verified_partner_slot",
    )
    assert offer_px_slot["offer_sku"] == "px_verified_partner_slot"
    assert offer_px_slot["offer_price_usd"] == 299.0
    assert offer_px_slot["offer_price_cents"] == 29900

    with pytest.raises(ValueError, match="Restricted public-service asset"):
        resolve_lead_monetization_offer(
            property_id="prexvo",
            tool_slug="pslf-forgiveness-calculator",
            sku="px_verified_partner_slot",
        )


def test_zero_forbidden_dashes_across_all_cluster2_owned_files() -> None:
    owned_rel_paths = (
        "pseofactory/email_ingest.py",
        "pseofactory/action_bus.py",
        "pseofactory/partner_tracker.py",
        "pseofactory/revenue_truth.py",
        "pseofactory/content_angles.py",
        "pseofactory/cli.py",
        "pseofactory/ui.py",
        ".agy/human_action_bus.json",
        ".agy/partner_earnings_ledger.json",
        ".agy/personal_inbox.json",
        "pseofactory_tests/test_monetization_overhaul_ingest_and_tracker.py",
    )
    for rel in owned_rel_paths:
        full_path = WORKTREE_ROOT / rel
        assert full_path.is_file(), f"Missing owned file: {rel}"
        text = full_path.read_text(encoding="utf-8")
        assert "\u2014" not in text, f"Forbidden em-dash found in {rel}"
        assert "\u2013" not in text, f"Forbidden en-dash found in {rel}"
        if rel.endswith(".json"):
            json.loads(text)
