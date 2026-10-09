"""
pseofactory Inbound Email Ingestion Engine
Automated correspondence intake for affiliate partner tracking and monetization readiness.
Ingests correspondence from arif.coskun@profithelm.com via himalaya CLI along with personal inbox.
Enforces polling rate limits to prevent mail server hammering and asserts zero forbidden dashes.

Key Invariants:
1. Minimum polling interval to avoid hammering mail servers.
2. Local caching of envelopes and message bodies for idempotent processing.
3. Classification of partner correspondence and extraction of required manual decisions.
4. Zero em-dashes and zero en-dashes across all text.

Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
import urllib.parse

from pseofactory.contracts import assert_no_forbidden_dashes


DEFAULT_MIN_POLL_INTERVAL_SECONDS = 300  # 5 minutes minimum between live IMAP queries
DEFAULT_SAFETY_FLOOR_SECONDS = 5  # minimum seconds between forced queries


@dataclass
class EmailMessage:
    """Represents an ingested email message."""
    id: str
    message_id: str
    account: str
    mailbox: str
    date: str
    subject: str
    sender_name: str
    sender_email: str
    body_snippet: str
    raw_headers: Dict[str, Any] = field(default_factory=dict)
    flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PartnerEmailClassification:
    """Classification record for partner-related correspondence."""
    email_id: str
    account: str
    property_id: str
    partner_key: str
    partner_name: str
    category: str
    classification_type: str  # APPLICATION_SUBMITTED, APPLICATION_APPROVED, APPLICATION_DECLINED, GOVERNANCE_WARNING, BANKING_ALERT, TERMS_UPDATE, INBOUND_PITCH
    requires_operator_decision: bool
    summary: str
    urgency: str  # CRITICAL, HIGH, MEDIUM, LOW
    deadline: Optional[str] = None
    missing_requirements: List[str] = field(default_factory=list)
    raw_subject: str = ""
    sender_email: str = ""
    date: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EmailIngestionEngine:
    """
    Automated email intake engine integrating himalaya CLI and local personal inbox storage.
    Enforces rate-limiting, local caching, and deterministic partner classification.
    """

    def __init__(
        self,
        cache_path: Optional[str] = None,
        state_path: Optional[str] = None,
        min_poll_interval: int = DEFAULT_MIN_POLL_INTERVAL_SECONDS,
        himalaya_bin: str = "himalaya",
    ):
        self.cache_path = cache_path or os.path.join(
            os.path.dirname(__file__), "..", ".agy", "email_cache.json"
        )
        self.state_path = state_path or os.path.join(
            os.path.dirname(__file__), "..", ".agy", "email_sync_state.json"
        )
        self.min_poll_interval = min_poll_interval
        self.himalaya_bin = himalaya_bin
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        for p in (self.cache_path, self.state_path):
            dir_name = os.path.dirname(os.path.abspath(p))
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)

    def load_state(self) -> Dict[str, Any]:
        if os.path.isfile(self.state_path):
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"accounts": {}, "last_updated": ""}

    def save_state(self, state: Dict[str, Any]) -> None:
        state["last_updated"] = datetime.now(timezone.utc).isoformat()
        tmp_path = f"{self.state_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, self.state_path)

    def load_cache(self) -> Dict[str, Any]:
        if os.path.isfile(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"messages": {}, "classifications": []}

    def save_cache(self, cache: Dict[str, Any]) -> None:
        tmp_path = f"{self.cache_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, self.cache_path)

    def can_poll(self, account: str, force: bool = False) -> Tuple[bool, int]:
        """
        Determines if a poll is permitted under rate-limiting rules.
        Returns (is_allowed, seconds_remaining).
        """
        if force:
            return True, 0
        state = self.load_state()
        acct_state = state.get("accounts", {}).get(account, {})
        last_ts = acct_state.get("last_polled_ts", 0)
        now_ts = time.time()
        elapsed = now_ts - last_ts
        if elapsed < self.min_poll_interval:
            remaining = int(self.min_poll_interval - elapsed)
            return False, remaining
        return True, 0

    def record_poll(self, account: str, success: bool = True, error: str = "") -> None:
        state = self.load_state()
        accounts = state.setdefault("accounts", {})
        accounts[account] = {
            "last_polled_at": datetime.now(timezone.utc).isoformat(),
            "last_polled_ts": time.time(),
            "last_success": success,
            "last_error": error,
        }
        self.save_state(state)

    def run_himalaya_command(self, args: List[str]) -> Tuple[int, str, str]:
        cmd = [self.himalaya_bin] + args
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
            return res.returncode, res.stdout, res.stderr
        except Exception as exc:
            return 1, "", str(exc)

    def fetch_zoho_envelopes(
        self,
        mailbox: str = "Inbox",
        page_size: int = 50,
        page: int = 1,
        force: bool = False,
    ) -> List[Dict[str, Any]]:
        """Fetches envelopes from himalaya Zoho account with rate limiting."""
        allowed, remaining = self.can_poll("zoho", force=force)
        if not allowed:
            return []

        code, stdout, stderr = self.run_himalaya_command(
            ["envelope", "list", "-a", "zoho", "-m", mailbox, "-s", str(page_size), "-p", str(page), "--json"]
        )
        if code != 0:
            self.record_poll("zoho", success=False, error=stderr)
            return []

        try:
            data = json.loads(stdout)
            envelopes = data.get("envelopes", [])
            self.record_poll("zoho", success=True)
            return envelopes
        except Exception as exc:
            self.record_poll("zoho", success=False, error=f"JSON parse error: {exc}")
            return []

    def read_message_body(self, message_id: str, account: str = "zoho") -> str:
        """Reads message body via himalaya or returns empty string on failure."""
        code, stdout, stderr = self.run_himalaya_command(
            ["message", "read", str(message_id), "-a", account]
        )
        if code == 0:
            return stdout
        return ""

    def ingest_zoho(
        self,
        limit: int = 30,
        force: bool = False,
        fetch_bodies_for_partner_keys: bool = True,
    ) -> List[EmailMessage]:
        """
        Ingests messages for arif.coskun@profithelm.com from Zoho via himalaya.
        Saves messages into local cache and returns EmailMessage list.
        """
        cache = self.load_cache()
        cached_dict = cache.setdefault("messages", {})

        allowed, remaining = self.can_poll("zoho", force=force)
        if not allowed and cached_dict:
            # Return cached messages for zoho
            return [
                EmailMessage(**m) for m in cached_dict.values()
                if m.get("account") == "zoho"
            ]

        envelopes = self.fetch_zoho_envelopes(mailbox="Inbox", page_size=limit, force=force)
        if not envelopes and cached_dict:
            # On fetch failure or rate limit cooldown, preserve and return cached messages intact
            return [
                EmailMessage(**m) for m in cached_dict.values()
                if m.get("account") == "zoho"
            ]

        ingested = []

        partner_tokens = [
            "impact", "gusto", "shopify", "mercury", "stripe", "koinly", "coinledger",
            "turbotax", "taxslayer", "kalshi", "interactive", "crest", "ipx1031",
            "partner", "affiliate", "startups", "prexvo"
        ]

        for env in envelopes:
            mid = str(env.get("id", ""))
            from_arr = env.get("from") or []
            sender_name = from_arr[0].get("name") or "" if from_arr else ""
            sender_email = from_arr[0].get("email") or "" if from_arr else ""
            subject = env.get("subject") or ""
            date_str = env.get("date") or ""
            msg_id_hdr = env.get("message-id") or ""

            # Check if we already have body in cache
            cached_entry = cached_dict.get(mid)
            body_text = cached_entry.get("body_snippet", "") if cached_entry else ""

            # Read body if partner token is present and body not cached yet
            text_to_check = f"{subject} {sender_name} {sender_email}".lower()
            needs_body = any(t in text_to_check for t in partner_tokens)

            if needs_body and not body_text and fetch_bodies_for_partner_keys:
                body_full = self.read_message_body(mid, account="zoho")
                body_text = body_full[:2000] if body_full else ""

            # Normalize dashes in subject and snippet
            subject_clean = subject.replace("\u2014", "-").replace("\u2013", "-")
            body_clean = body_text.replace("\u2014", "-").replace("\u2013", "-")
            sender_name_clean = sender_name.replace("\u2014", "-").replace("\u2013", "-")

            assert_no_forbidden_dashes(subject_clean, context=f"Email subject {mid}")
            assert_no_forbidden_dashes(sender_name_clean, context=f"Sender name {mid}")

            msg = EmailMessage(
                id=mid,
                message_id=msg_id_hdr,
                account="zoho",
                mailbox="Inbox",
                date=date_str,
                subject=subject_clean,
                sender_name=sender_name_clean,
                sender_email=sender_email,
                body_snippet=body_clean,
                raw_headers={"size": env.get("size")},
                flags=[f.get("iana", "") for f in (env.get("flags") or []) if isinstance(f, dict)],
            )
            cached_dict[mid] = msg.to_dict()
            ingested.append(msg)

        self.save_cache(cache)
        return ingested

    def ingest_personal(
        self,
        fixture_path: Optional[str] = None,
        personal_account: str = "personal",
        force: bool = False,
    ) -> List[EmailMessage]:
        """
        Ingests correspondence from the personal account.
        Checks himalaya if personal account is configured, or loads from local fixture/storage.
        """
        cache = self.load_cache()
        cached_dict = cache.setdefault("messages", {})

        # 1. Check if explicit fixture or personal inbox JSON exists
        target_fixture = fixture_path
        if not target_fixture:
            default_fixture = os.path.join(
                os.path.dirname(__file__), "..", ".agy", "personal_inbox.json"
            )
            if os.path.isfile(default_fixture):
                target_fixture = default_fixture

        if target_fixture and os.path.isfile(target_fixture):
            try:
                with open(target_fixture, "r", encoding="utf-8") as f:
                    raw_items = json.load(f)
                items = raw_items if isinstance(raw_items, list) else raw_items.get("messages", [])
                ingested = []
                for idx, it in enumerate(items):
                    mid = str(it.get("id") or f"personal-{idx+1}")
                    subj = (it.get("subject") or "").replace("\u2014", "-").replace("\u2013", "-")
                    body = (it.get("body_snippet") or it.get("body") or "").replace("\u2014", "-").replace("\u2013", "-")
                    snd_name = (it.get("sender_name") or "").replace("\u2014", "-").replace("\u2013", "-")
                    snd_email = it.get("sender_email") or ""
                    assert_no_forbidden_dashes(subj, context=f"Personal email {mid}")

                    msg = EmailMessage(
                        id=mid,
                        message_id=it.get("message_id") or mid,
                        account="personal",
                        mailbox=it.get("mailbox", "Inbox"),
                        date=it.get("date", datetime.now(timezone.utc).isoformat()),
                        subject=subj,
                        sender_name=snd_name,
                        sender_email=snd_email,
                        body_snippet=body[:2000],
                        raw_headers=it.get("raw_headers", {}),
                        flags=it.get("flags", []),
                    )
                    cached_dict[mid] = msg.to_dict()
                    ingested.append(msg)
                self.save_cache(cache)
                return ingested
            except Exception as exc:
                pass

        # 2. Try himalaya personal account if configured
        allowed, _ = self.can_poll(personal_account, force=force)
        if allowed:
            code, stdout, stderr = self.run_himalaya_command(
                ["envelope", "list", "-a", personal_account, "-s", "25", "--json"]
            )
            if code == 0:
                try:
                    data = json.loads(stdout)
                    envs = data.get("envelopes", [])
                    self.record_poll(personal_account, success=True)
                    ingested = []
                    for env in envs:
                        mid = str(env.get("id", ""))
                        from_arr = env.get("from") or []
                        s_name = from_arr[0].get("name", "") if from_arr else ""
                        s_email = from_arr[0].get("email", "") if from_arr else ""
                        subj = (env.get("subject") or "").replace("\u2014", "-").replace("\u2013", "-")
                        s_name = s_name.replace("\u2014", "-").replace("\u2013", "-")
                        assert_no_forbidden_dashes(subj, context=f"Personal himalaya {mid}")

                        msg = EmailMessage(
                            id=f"p-{mid}",
                            message_id=env.get("message-id", ""),
                            account="personal",
                            mailbox="Inbox",
                            date=env.get("date", ""),
                            subject=subj,
                            sender_name=s_name,
                            sender_email=s_email,
                            body_snippet="",
                        )
                        cached_dict[msg.id] = msg.to_dict()
                        ingested.append(msg)
                    self.save_cache(cache)
                    return ingested
                except Exception:
                    pass

        # Return cached personal messages if available
        return [
            EmailMessage(**m) for m in cached_dict.values()
            if m.get("account") == "personal"
        ]

    def sync_all(
        self,
        force: bool = False,
        personal_fixture: Optional[str] = None,
    ) -> List[EmailMessage]:
        """Runs unified ingestion across Zoho and personal inboxes."""
        zoho_msgs = self.ingest_zoho(limit=40, force=force)
        personal_msgs = self.ingest_personal(fixture_path=personal_fixture, force=force)
        all_msgs = zoho_msgs + personal_msgs
        return all_msgs

    def classify_partner_emails(
        self,
        messages: List[EmailMessage],
    ) -> List[PartnerEmailClassification]:
        """
        Categorizes emails into partner requests, approvals, warnings, or action items.
        Applies property isolation rules and typography constraints.
        """
        classifications: List[PartnerEmailClassification] = []

        for msg in messages:
            subj_lower = msg.subject.lower()
            sender_lower = f"{msg.sender_name} {msg.sender_email}".lower()
            body_lower = msg.body_snippet.lower()
            combined_text = f"{subj_lower} {sender_lower} {body_lower}"

            # 1. Gusto Affiliate Application (Impact.com)
            if "gusto" in combined_text and ("impact.com" in sender_lower or "affiliate" in combined_text):
                is_applied = "thank you for applying" in body_lower or "application" in combined_text
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="profithelm",
                        partner_key="gusto",
                        partner_name="Gusto Payroll & HR",
                        category="PAYROLL_HR",
                        classification_type="APPLICATION_SUBMITTED",
                        requires_operator_decision=False,
                        summary="Application submitted via Impact.com. Awaiting partner review and tracking link issuance.",
                        urgency="MEDIUM",
                        deadline=None,
                        missing_requirements=["Pending Impact.com vendor review", "Missing tracking link"],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                    )
                )

            # 2. Prexvo Shopify Payments Payout Alert
            elif "prexvo" in combined_text and ("shop pay installments" in combined_text or "payouts from orders" in combined_text or ("shopify" in combined_text and "payout" in combined_text)):
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="prexvo",
                        partner_key="shopify_payments_prexvo",
                        partner_name="Shopify Payments (Prexvo)",
                        category="PAYMENT_OPERATIONS",
                        classification_type="GOVERNANCE_WARNING",
                        requires_operator_decision=True,
                        summary="Update business details on Shopify Payments for Prexvo to resume payouts from orders.",
                        urgency="HIGH",
                        deadline=None,
                        missing_requirements=[
                            "Update business details on Prexvo Shopify Payments account",
                            "Verify legal entity and banking details for payout resumption",
                        ],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                    )
                )

            # 3. Shopify Partner Governance / App Delisting Warning (ProfitHelm)
            elif "shopify" in combined_text and (
                "ecosystem-governance@shopify.com" in sender_lower
                or "at risk of being closed" in subj_lower
                or "delisted" in combined_text
            ):
                # Detect deadline
                deadline = None
                m_dead = re.search(r"by (october \d{1,2}, \d{4})", body_lower)
                if m_dead:
                    deadline = m_dead.group(1).title()
                elif "october 20, 2026" in body_lower or "october 20" in body_lower:
                    deadline = "October 20, 2026"
                elif "october 19, 2026" in body_lower or "october 19" in body_lower:
                    deadline = "October 19, 2026"

                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="profithelm",
                        partner_key="shopify_partner_account",
                        partner_name="Shopify Partner Governance",
                        category="DEVELOPER_ECOSYSTEM",
                        classification_type="GOVERNANCE_WARNING",
                        requires_operator_decision=True,
                        summary=f"Final warning: Shopify App delisted and Partner Account at risk. Operator decision required: appeal/relist or initiate sunsetting.",
                        urgency="CRITICAL",
                        deadline=deadline or "October 20, 2026",
                        missing_requirements=[
                            "Valid SSL certificate on application URL",
                            "Valid privacy policy URL in listing resources",
                            "Operator reply to Shopify Partner Governance",
                        ],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                    )
                )

            # 4. Mercury Startup Banking Funds Alert
            elif "mercury" in combined_text and ("declined" in combined_text or "add or transfer funds" in combined_text):
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="profithelm",
                        partner_key="mercury",
                        partner_name="Mercury Startup Banking",
                        category="STARTUP_BANKING",
                        classification_type="BANKING_ALERT",
                        requires_operator_decision=True,
                        summary="Mercury transaction declined due to insufficient checking balance. Requires operator funds transfer or spend limit adjustment.",
                        urgency="HIGH",
                        deadline=None,
                        missing_requirements=["Funds transfer to Checking account", "Spend limit update"],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                    )
                )

            # 5. Stripe Legal Terms & Services Agreement Update
            elif "stripe" in combined_text and ("legal terms" in combined_text or "services agreement" in combined_text):
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="profithelm",
                        partner_key="stripe",
                        partner_name="Stripe Treasury & Payments",
                        category="B2B_PAYMENTS",
                        classification_type="TERMS_UPDATE",
                        requires_operator_decision=True,
                        summary="Stripe Services Agreement and Privacy Policy terms updated (effective Jan 6, 2027 and Nov 20, 2026). Requires operator review.",
                        urgency="LOW",
                        deadline="November 20, 2026",
                        missing_requirements=["Operator review of updated Stripe legal terms"],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                    )
                )

            # 6. Inbound Partnership Pitch (ETdropship / Zhang Bingzhen)
            elif "partner" in combined_text and ("recommendation opportunity" in subj_lower or "etdropship" in combined_text):
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="profithelm",
                        partner_key="etdropship",
                        partner_name="ETdropship Sourcing & Fulfillment",
                        category="ECOMMERCE_DROPSHIPPING",
                        classification_type="INBOUND_PITCH",
                        requires_operator_decision=True,
                        summary="Inbound mutual recommendation request from ETdropship. Standing invariant: never auto-approve partner agreements without operator confirmation.",
                        urgency="MEDIUM",
                        deadline=None,
                        missing_requirements=["Operator confirmation required before establishing partnership agreement"],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                    )
                )

            # 7. Prexvo Inbound Marketing Inquiry (Wishpond)
            elif "prexvo" in combined_text and "wishpond" in combined_text:
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="prexvo",
                        partner_key="wishpond_outreach",
                        partner_name="Wishpond Lead Generation",
                        category="EXTERNAL_OUTREACH",
                        classification_type="INBOUND_PITCH",
                        requires_operator_decision=True,
                        summary="Cold marketing pitch for Prexvo apparel/sales. Strict property isolation: Prexvo prohibits B2B monetization and commercial marketing tools.",
                        urgency="LOW",
                        deadline=None,
                        missing_requirements=["Review for compliance with Prexvo standing restriction"],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                    )
                )

            # 8. Prexvo Student Loan Borrower or Partner Inquiry
            elif ("student loan" in combined_text or "splash" in combined_text or "refinanc" in combined_text) and ("prexvo" in combined_text or msg.account == "personal"):
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="prexvo",
                        partner_key="splash_financial",
                        partner_name="Splash Financial",
                        category="STUDENT_LOAN_REFINANCE",
                        classification_type="INBOUND_PITCH",
                        requires_operator_decision=True,
                        summary="Student loan refinance partner inquiry. Strict Gate 1 invariant: requires written payout confirmation of at least $45/deal.",
                        urgency="MEDIUM",
                        deadline=None,
                        missing_requirements=[
                            "Written payout confirmation >= $45/deal",
                            "Mandatory Title IV statutory forfeiture YMYL disclaimer review",
                        ],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                    )
                )

            # 9. Generic Partner Matching across AFFILIATE_REGISTRY
            else:
                from pseofactory.affiliates import AFFILIATE_REGISTRY
                matched_partner = None
                for p_key, p_obj in AFFILIATE_REGISTRY.items():
                    p_name_lower = p_obj.name.lower()
                    p_key_lower = p_key.lower().replace("_", " ")
                    p_domain = urllib.parse.urlsplit(p_obj.default_url).netloc.lower().replace("www.", "")
                    if (p_key in combined_text or p_key_lower in combined_text or
                        p_name_lower in combined_text or (p_domain and p_domain in combined_text)):
                        matched_partner = p_obj
                        break

                if matched_partner:
                    req_decision = ("action required" in combined_text or "urgent" in combined_text or
                                    "warning" in combined_text or "update" in combined_text)
                    classifications.append(
                        PartnerEmailClassification(
                            email_id=msg.id,
                            account=msg.account,
                            property_id=matched_partner.property_id,
                            partner_key=matched_partner.key,
                            partner_name=matched_partner.name,
                            category=matched_partner.category,
                            classification_type="GENERAL_INQUIRY" if not req_decision else "GOVERNANCE_WARNING",
                            requires_operator_decision=req_decision,
                            summary=f"Inbound correspondence matched for {matched_partner.name} on {matched_partner.property_id}.",
                            urgency="HIGH" if req_decision else "LOW",
                            deadline=None,
                            missing_requirements=[],
                            raw_subject=msg.subject,
                            sender_email=msg.sender_email,
                            date=msg.date,
                        )
                    )

        # Sort classifications by date descending so latest emails have priority
        classifications.sort(key=lambda x: x.date, reverse=True)

        # Validate zero forbidden dashes across all classifications
        for c in classifications:
            assert_no_forbidden_dashes(c.summary, context=f"Classification summary for {c.partner_key}")
            assert_no_forbidden_dashes(c.partner_name, context=f"Partner name for {c.partner_key}")
            for req in c.missing_requirements:
                assert_no_forbidden_dashes(req, context=f"Missing requirement for {c.partner_key}")

        return classifications
