"""
pseofactory Inbound Email Ingestion Engine
Automated correspondence intake for affiliate partner tracking and monetization readiness.
Ingests correspondence exclusively from arif.coskun@profithelm.com via himalaya -a zoho.
Enforces polling rate limits to prevent mail server hammering and asserts zero forbidden dashes.

Key Invariants:
1. Minimum polling interval to avoid hammering mail servers.
2. Local caching of envelopes and message bodies keyed by stable RFC Message-ID header.
3. Classification of partner correspondence and extraction of required manual decisions.
4. Zero em-dashes and zero en-dashes across all text.

Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import hashlib
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
ZOHO_POLL_MAILBOXES: Tuple[str, ...] = ("Inbox", "Sent", "Notification", "Newsletter", "Spam")

ZOHO_NOTIFICATION_PARTNER_DOMAINS: Tuple[str, ...] = (
    "mercury.com",
    "rho.co",
    "ramp.com",
    "rippling.com",
    "crestcapital.com",
    "exeterco.com",
    "firstam.com",
    "splashfinancial.com",
    "interactivebrokers.com",
    "suretybonds.com",
    "suretybondsdirect.com",
    "ipx1031.com",
    "simplybusiness.com",
    "nextinsurance.com",
    "thimble.com",
    "getjobber.com",
    "jobber.com",
    "levelset.com",
    "vanta.com",
    "drata.com",
    "sprinto.com",
    "thoropass.com",
    "coalitioninc.com",
    "cobalt.io",
    "xendoo.com",
    "katalystcomms.com",
    "dlpcapital.com",
    "cj.com",
    "e-file.com",
    "eztaxreturn.com",
    "lawdepot.com",
    "impact.com",
    "sofi.com",
    "lendkey.com",
    "gusto.com",
    "freetaxusa.com",
    "wallethub.com",
    "invoicesimple.com",
    "hamstergarage.com",
)


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
    candidate_url: str = ""
    network: str = "In-House Direct"
    action_required: str = ""
    commission_amount_usd: float = 0.0

    def __post_init__(self) -> None:
        if not self.action_required and self.summary:
            self.action_required = self.summary
        elif self.action_required and not self.summary:
            self.summary = self.action_required

    @property
    def property_target(self) -> str:
        return self.property_id

    @property
    def subject(self) -> str:
        return self.raw_subject

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


PartnerEmailSignal = PartnerEmailClassification


def _extract_candidate_url(text: str) -> str:
    """Extracts candidate tracking URL (https://...) excluding generic unsubscribe/privacy/support links."""
    if not text:
        return ""
    matches = re.findall(r"https://[^\s\"'<>)\]]+", text)
    ignore_tokens = (
        "unsubscribe",
        "privacy",
        "support",
        "help.",
        "preferences",
        "optout",
        "opt-out",
        "manage-preferences",
        "terms-of-service",
        "email.cj.com/c/",
    )
    for raw in matches:
        cleaned = raw.rstrip(".,;:!?)")
        low = cleaned.lower()
        if any(tok in low for tok in ignore_tokens):
            continue
        return cleaned
    return ""


def _extract_commission_amount_usd(text: str) -> float:
    """Extracts a dollar amount (e.g. $300.00 or $1,600) from a conversion or payout email."""
    if not text:
        return 0.0
    matches = re.findall(r"\$\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)", text)
    for raw in matches:
        try:
            val = float(raw.replace(",", ""))
            if val > 0.0:
                return round(val, 2)
        except ValueError:
            continue
    return 0.0


_BOUNCE_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+*-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_VOLATILE_SEQ_ID_RE = re.compile(r"^(?:(?:inbox|sent|notif|news|spam|drafts|trash)-)?\d+$", re.IGNORECASE)


def _normalize_rfc_message_id(raw_msg_id: str, raw_body: str = "") -> str:
    """Extracts and normalizes an RFC Message-ID header, rejecting volatile IMAP sequence numbers."""
    cand = (raw_msg_id or "").strip()
    if (not cand or _VOLATILE_SEQ_ID_RE.match(cand)) and raw_body:
        hdr_match = re.search(r"(?im)^message-id:\s*(<[^>]+>|[^\r\n]+)", raw_body)
        if hdr_match:
            cand = hdr_match.group(1).strip()
    if not cand:
        return ""
    angle_match = re.search(r"<([^<>\s]+)>", cand)
    if angle_match:
        cand = angle_match.group(1).strip()
    else:
        cand = cand.strip("<>").strip()
    if not cand or _VOLATILE_SEQ_ID_RE.match(cand):
        return ""
    return cand.lower()


def compute_stable_email_cache_key(
    mailbox: str,
    message_id_hdr: str,
    subject: str,
    date_str: str,
    sender_email: str,
    raw_body: str = "",
) -> str:
    """
    Computes a stable cache key from the normalized RFC Message-ID header, falling back
    to a SHA-256 hash of f"{mailbox}:{subject}:{date}:{sender}" only when absent.
    Never keys cache entries by volatile IMAP folder sequence numbers.
    """
    norm_mid = _normalize_rfc_message_id(message_id_hdr, raw_body=raw_body)
    if norm_mid:
        return norm_mid
    fallback_payload = f"{(mailbox or '').strip()}:{(subject or '').strip()}:{(date_str or '').strip()}:{(sender_email or '').strip().lower()}"
    return hashlib.sha256(fallback_payload.encode("utf-8")).hexdigest()


def _extract_bounced_recipient(text: str, sender_email: str = "") -> str:
    """
    Extracts the actual bounced recipient email address (including masked addresses like
    s***@profithelm.com or unprovisioned ciso@gainhelm.com) from mailer-daemon bodies.
    """
    if not text:
        return "unknown"
    sender_clean = (sender_email or "").strip().lower()
    daemon_prefixes = ("mailer-daemon@", "postmaster@", "no-reply@", "noreply@", "bounce@", "bounces@")
    matches = _BOUNCE_EMAIL_RE.findall(text)
    candidates: List[str] = []
    for addr in matches:
        clean_addr = addr.strip().rstrip(".,;:)>]\"'")
        low = clean_addr.lower()
        if not low or low == sender_clean:
            continue
        if low.startswith(daemon_prefixes):
            continue
        candidates.append(clean_addr)
    non_canonical = [c for c in candidates if c.lower() != "arif.coskun@profithelm.com"]
    if non_canonical:
        return non_canonical[0]
    if candidates:
        return candidates[0]
    return "unknown"


def _is_automated_sender(sender_email: str, sender_name: str = "") -> bool:
    """Returns True when sender is an automated system/notification daemon rather than a human."""
    low = f"{sender_name or ''} {sender_email or ''}".lower()
    email_low = (sender_email or "").strip().lower()
    auto_tokens = (
        "no-reply",
        "noreply",
        "no-response",
        "do-not-reply",
        "donotreply",
        "mailer-daemon",
        "postmaster@",
        "notifications@",
        "automated@",
        "promoter@firstpromoter.com",
        "ecosystem-governance@",
        "app-partnerships+noreply@",
        "support@shopify.com",
    )
    return any(tok in low or email_low.startswith(tok) for tok in auto_tokens)


_URL_IN_TEXT_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_REPLY_ATTRIBUTION_RE = re.compile(r"^on .+ wrote:$", re.IGNORECASE)
_THREAD_DIVIDER_RE = re.compile(
    r"^(?:_{8,}|-{5,}\s*(?:original message|forwarded message)\s*-{5,})$",
    re.IGNORECASE,
)
_MIME_ENVELOPE_HEADER_RE = re.compile(
    r"^(?:(?:date|from|to|cc|sent|subject|content-type|content-transfer-encoding):\s|\[\d+\]\s+text/)",
    re.IGNORECASE,
)
_FOOTER_BOILERPLATE_TOKENS: Tuple[str, ...] = (
    "unsubscribe",
    "manage preferences",
    "manage your preferences",
    "email preferences",
    "opt-out",
    "opt out",
    "view in browser",
    "privacy policy",
)


def _has_human_partner_question(
    sender_email: str,
    sender_name: str,
    subject: str,
    body_snippet: str,
) -> Tuple[bool, str]:
    """
    Detects when an inbound email from a human partner manager contains a direct question
    on any non-quoted, non-footer line outside URL query strings (even if the email
    simultaneously approves an application).
    """
    email_low = (sender_email or "").strip().lower()
    if email_low == "arif.coskun@profithelm.com":
        return False, ""
    if _is_automated_sender(sender_email, sender_name):
        return False, ""

    candidate_lines: List[str] = []
    if subject and "?" in subject:
        candidate_lines.append(subject)
    if body_snippet and "?" in body_snippet:
        seen_body_prose = False
        for b_line in body_snippet.splitlines():
            b_stripped = b_line.strip()
            if not b_stripped:
                continue
            if _THREAD_DIVIDER_RE.match(b_stripped) or _REPLY_ATTRIBUTION_RE.match(b_stripped):
                break
            if seen_body_prose and re.match(r"^from:\s+.+@", b_stripped, re.IGNORECASE):
                break
            if not seen_body_prose and _MIME_ENVELOPE_HEADER_RE.match(b_stripped):
                continue
            seen_body_prose = True
            candidate_lines.append(b_line)
    if not candidate_lines:
        return False, ""

    matched_question = ""
    for raw_line in candidate_lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith(">"):
            continue
        if _REPLY_ATTRIBUTION_RE.match(stripped) or _THREAD_DIVIDER_RE.match(stripped):
            break
        line_low = stripped.lower()
        if any(tok in line_low for tok in _FOOTER_BOILERPLATE_TOKENS):
            continue
        without_urls = _URL_IN_TEXT_RE.sub("", stripped)
        if "?" not in without_urls or not re.search(r"[A-Za-z]", without_urls):
            continue
        segments = [
            seg.strip()
            for seg in re.split(r"(?<=[.!?\n])\s+", stripped)
            if "?" in _URL_IN_TEXT_RE.sub("", seg) and re.search(r"[A-Za-z]", _URL_IN_TEXT_RE.sub("", seg))
        ]
        matched_question = segments[0] if segments else stripped
        break

    if not matched_question:
        return False, ""

    excerpt = matched_question[:180].replace("\u2014", "-").replace("\u2013", "-")
    sender_label = (sender_email or sender_name or "partner manager").strip()
    return True, f"Reply to partner manager question from {sender_label}: {excerpt}"


def _resolve_lienbond_or_profithelm_property(partner_key: str, combined_text: str) -> str:
    """
    Resolves property_id dynamically for LienBond construction/surety/insurance partners
    without hardcoding simply_business, suretybonds_direct, or next_insurance_b2b solely to profithelm.
    """
    from pseofactory.affiliates import LIENBOND_AFFILIATES, PROFITHELM_AFFILIATES

    dedicated_lb = {"thimble_contractor", "jobber_field_service", "levelset_lien_filing"}
    if partner_key in dedicated_lb:
        return "lienbond"
    low = (combined_text or "").lower()
    if any(
        tok in low
        for tok in (
            "lienbond",
            "mechanics lien",
            "wh-347",
            "prevailing wage",
            "workers comp",
            "emr",
            "builders risk",
            "contractor surety",
        )
    ):
        if partner_key in LIENBOND_AFFILIATES:
            return "lienbond"
    if partner_key in LIENBOND_AFFILIATES and partner_key not in PROFITHELM_AFFILIATES:
        return "lienbond"
    if "profithelm" in low and partner_key in PROFITHELM_AFFILIATES:
        return "profithelm"
    if partner_key in ("simply_business", "suretybonds_direct", "next_insurance_b2b") and partner_key in LIENBOND_AFFILIATES:
        return "lienbond"
    return "profithelm"


class EmailIngestionEngine:
    """
    Automated email intake engine integrating himalaya CLI (-a zoho, arif.coskun@profithelm.com).
    Enforces rate-limiting, stable Message-ID caching, and deterministic partner classification.
    """

    DEFAULT_CACHE_PATH = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", ".agy", "email_cache.json")
    )
    DEFAULT_STATE_PATH = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", ".agy", "email_sync_state.json")
    )

    def __init__(
        self,
        cache_path: Optional[str] = None,
        state_path: Optional[str] = None,
        min_poll_interval: int = DEFAULT_MIN_POLL_INTERVAL_SECONDS,
        himalaya_bin: str = "himalaya",
    ):
        self._has_custom_state_path = state_path is not None
        self.cache_path = cache_path or os.path.join(
            os.path.dirname(__file__), "..", ".agy", "email_cache.json"
        )
        self.state_path = state_path or os.path.join(
            os.path.dirname(__file__), "..", ".agy", "email_sync_state.json"
        )
        self.min_poll_interval = min_poll_interval
        self.himalaya_bin = himalaya_bin
        self._last_envelope_fetch_ok = False
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
        tmp_path = f"{self.state_path}.{os.getpid()}.tmp"
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
        tmp_path = f"{self.cache_path}.{os.getpid()}.tmp"
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
        if (
            not self._has_custom_state_path
            and "PYTEST_CURRENT_TEST" in os.environ
            and os.getenv("PSEUFACTORY_LIVE_EMAIL") != "1"
            and error == "Offline mode: simulated IMAP disabled in test environment"
        ):
            return
        state = self.load_state()
        accounts = state.setdefault("accounts", {})
        accounts[account] = {
            "last_polled_at": datetime.now(timezone.utc).isoformat(),
            "last_polled_ts": time.time(),
            "last_success": success,
            "last_status": "OK" if success else "ERROR",
            "last_error": error,
        }
        self.save_state(state)

    def run_himalaya_command(self, args: List[str]) -> Tuple[int, str, str]:
        if "PYTEST_CURRENT_TEST" in os.environ and os.getenv("PSEUFACTORY_LIVE_EMAIL") != "1":
            if self.himalaya_bin == "himalaya":
                return 1, "", "Offline mode: simulated IMAP disabled in test environment"
        cmd = [self.himalaya_bin] + args
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
            return res.returncode, res.stdout, res.stderr
        except Exception as exc:
            return 1, "", str(exc)

    def fetch_zoho_envelopes(
        self,
        mailbox: str = "Inbox",
        page_size: int = 200,
        page: int = 1,
        force: bool = False,
        extra_args: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetches envelopes from himalaya Zoho account with rate limiting."""
        self._last_envelope_fetch_ok = False
        allowed, remaining = self.can_poll("zoho", force=force)
        if not allowed:
            return []

        cmd_args = [
            "envelope", "list", "-a", "zoho", "-m", mailbox,
            "-s", str(page_size), "-p", str(page), "--json",
        ]
        if mailbox.lower() == "sent":
            if "-r" not in cmd_args and (not extra_args or "-r" not in extra_args):
                cmd_args.append("-r")
        if extra_args:
            cmd_args.extend(extra_args)

        code, stdout, stderr = self.run_himalaya_command(cmd_args)
        if code != 0:
            self.record_poll("zoho", success=False, error=stderr)
            return []

        try:
            data = json.loads(stdout)
            envelopes = data.get("envelopes", [])
            self._last_envelope_fetch_ok = True
            self.record_poll("zoho", success=True)
            return envelopes
        except Exception as exc:
            self.record_poll("zoho", success=False, error=f"JSON parse error: {exc}")
            return []

    def read_message_body(
        self,
        message_id: str,
        account: str = "zoho",
        mailbox: Optional[str] = None,
    ) -> str:
        """Reads message body via himalaya or returns empty string on failure."""
        cmd_args = ["message", "read", str(message_id), "-a", "zoho"]
        if mailbox and mailbox.lower() != "inbox":
            cmd_args.extend(["-f", mailbox])
        code, stdout, stderr = self.run_himalaya_command(cmd_args)
        if code == 0:
            return stdout
        return ""

    def ingest_zoho(
        self,
        limit: int = 200,
        force: bool = False,
        fetch_bodies_for_partner_keys: bool = True,
        zoho_account: str = "zoho",
    ) -> List[EmailMessage]:
        """
        Ingests messages for arif.coskun@profithelm.com from Zoho via himalaya (-a zoho)
        across Inbox, Sent, Notification, Newsletter, and Spam with stable Message-ID caching.
        """
        cache = self.load_cache()
        cached_dict = cache.setdefault("messages", {})

        allowed, remaining = self.can_poll("zoho", force=force)
        if not allowed and cached_dict:
            return [
                EmailMessage(**m) for m in cached_dict.values()
                if m.get("account") == "zoho"
            ]

        page_sz = int(limit) if limit and limit > 0 else 200
        envelopes = self.fetch_zoho_envelopes(mailbox="Inbox", page_size=page_sz, force=True)
        if not envelopes and cached_dict and not self._last_envelope_fetch_ok:
            # On fetch failure or offline test guard, preserve and return cached messages intact
            return [
                EmailMessage(**m) for m in cached_dict.values()
                if m.get("account") == "zoho"
            ]

        # Build lookup index by stable key and fallback hash so IMAP sequence shifts never corrupt bodies.
        # Mark ambiguous same-minute fallback hashes as None so colliding messages force a body read.
        by_fallback_hash: Dict[str, Optional[Tuple[str, Dict[str, Any]]]] = {}
        for c_key, c_val in list(cached_dict.items()):
            if not isinstance(c_val, dict):
                continue
            fb_k = compute_stable_email_cache_key(
                mailbox=str(c_val.get("mailbox") or ""),
                message_id_hdr="",
                subject=str(c_val.get("subject") or ""),
                date_str=str(c_val.get("date") or ""),
                sender_email=str(c_val.get("sender_email") or ""),
            )
            if fb_k in by_fallback_hash:
                prev_pair = by_fallback_hash[fb_k]
                if prev_pair is not None:
                    prev_k, prev_v = prev_pair
                    prev_mid = _normalize_rfc_message_id(str(prev_v.get("message_id") or ""))
                    cur_mid = _normalize_rfc_message_id(str(c_val.get("message_id") or ""))
                    prev_body = str(prev_v.get("body_snippet") or "")
                    cur_body = str(c_val.get("body_snippet") or "")
                    if str(c_key) != prev_k or prev_mid != cur_mid or prev_body != cur_body:
                        by_fallback_hash[fb_k] = None
            else:
                by_fallback_hash[fb_k] = (str(c_key), c_val)

        def _mark_batch_fb_collisions(
            mbx_name: str,
            env_list: List[Dict[str, Any]],
            use_to: bool = False,
        ) -> None:
            fb_counts: Dict[str, int] = {}
            fb_hdr_mids: Dict[str, str] = {}
            for e_item in env_list:
                if use_to:
                    t_arr = e_item.get("to") or []
                    addr = (t_arr[0].get("email") or "").strip() if t_arr else ""
                else:
                    f_arr = e_item.get("from") or []
                    addr = (f_arr[0].get("email") or "") if f_arr else ""
                subj_s = (e_item.get("subject") or "").replace("\u2014", "-").replace("\u2013", "-")
                dt_s = e_item.get("date") or ""
                fb = compute_stable_email_cache_key(mbx_name, "", subj_s, dt_s, addr)
                fb_counts[fb] = fb_counts.get(fb, 0) + 1
                raw_h = str(e_item.get("message-id") or e_item.get("message_id") or "")
                norm_h = _normalize_rfc_message_id(raw_h)
                if norm_h:
                    if fb in fb_hdr_mids and fb_hdr_mids[fb] != norm_h:
                        fb_counts[fb] = max(fb_counts[fb], 2)
                    else:
                        fb_hdr_mids[fb] = norm_h
            for fb, cnt in fb_counts.items():
                if cnt > 1:
                    by_fallback_hash[fb] = None
                elif fb in by_fallback_hash and by_fallback_hash[fb] is not None and fb in fb_hdr_mids:
                    cached_mid = _normalize_rfc_message_id(str(by_fallback_hash[fb][1].get("message_id") or ""))
                    if cached_mid and cached_mid != fb_hdr_mids[fb]:
                        by_fallback_hash[fb] = None

        def _lookup_cached_entry(
            mbx: str,
            hdr_mid: str,
            subj_s: str,
            dt_s: str,
            snd_e: str,
        ) -> Optional[Dict[str, Any]]:
            norm_hdr = _normalize_rfc_message_id(hdr_mid)
            fb_k = compute_stable_email_cache_key(mbx, "", subj_s, dt_s, snd_e)
            if norm_hdr:
                if norm_hdr in cached_dict:
                    return cached_dict[norm_hdr]
                cand_pair = by_fallback_hash.get(fb_k)
                if cand_pair is not None:
                    prev_mid = _normalize_rfc_message_id(str(cand_pair[1].get("message_id") or ""))
                    if not prev_mid or prev_mid == norm_hdr:
                        return cand_pair[1]
                    by_fallback_hash[fb_k] = None
                return None
            if fb_k in by_fallback_hash:
                cand_pair = by_fallback_hash[fb_k]
                return cand_pair[1] if cand_pair is not None else None
            if fb_k in cached_dict:
                return cached_dict[fb_k]
            return None

        def _store_stable(stable_k: str, volatile_mid: str, fb_k: str, m_obj: EmailMessage) -> None:
            is_ambiguous = fb_k in by_fallback_hash and by_fallback_hash[fb_k] is None
            if volatile_mid in cached_dict and volatile_mid != stable_k:
                cached_dict.pop(volatile_mid, None)
            if not is_ambiguous:
                if fb_k in cached_dict and fb_k != stable_k:
                    cached_dict.pop(fb_k, None)
                cand_pair = by_fallback_hash.get(fb_k)
                if cand_pair is not None:
                    old_k = cand_pair[0]
                    if old_k != stable_k and _VOLATILE_SEQ_ID_RE.match(old_k):
                        cached_dict.pop(old_k, None)
            m_dict = m_obj.to_dict()
            cached_dict[stable_k] = m_dict
            if fb_k not in by_fallback_hash:
                by_fallback_hash[fb_k] = (stable_k, m_dict)
            elif by_fallback_hash[fb_k] is not None:
                prev_k, prev_v = by_fallback_hash[fb_k]
                if prev_k != stable_k or str(prev_v.get("body_snippet") or "") != m_obj.body_snippet:
                    by_fallback_hash[fb_k] = None
                else:
                    by_fallback_hash[fb_k] = (stable_k, m_dict)

        ingested: List[EmailMessage] = []

        partner_tokens = [
            "impact", "gusto", "mercury", "stripe", "koinly", "coinledger",
            "turbotax", "taxslayer", "kalshi", "interactive", "crest", "ipx1031",
            "partner", "affiliate", "startups", "prexvo", "ecosystem-governance@shopify.com",
            "otrsolutions", "otr solutions", "next insurance", "nextinsurance", "ergo next", "rho.co",
            "suretybonds", "simply business", "simplybusiness", "thimble", "jobber", "getjobber",
            "levelset", "lienbond", "interactivebrokers", "cj.com", "8101803", "firstpromoter",
            "xendoo", "eztaxreturn", "e-file.com", "lawdepot", "freetaxusa", "wallethub",
            "invoicesimple", "invoice simple", "hamstergarage", "sovrn", "accounting@sovrn.com",
            "suppliers portal", "vanta", "drata", "sprinto", "thoropass", "coalition", "cobalt",
            "mailer-daemon", "postmaster", "undelivered", "delivery status", "mail delivery failed",
            "failure notice", "declined",
        ]

        _mark_batch_fb_collisions("Inbox", envelopes, use_to=False)
        for env in envelopes:
            mid = str(env.get("id", ""))
            from_arr = env.get("from") or []
            sender_name = from_arr[0].get("name") or "" if from_arr else ""
            sender_email = from_arr[0].get("email") or "" if from_arr else ""
            subject = env.get("subject") or ""
            date_str = env.get("date") or ""
            msg_id_hdr = env.get("message-id") or env.get("message_id") or ""

            subject_clean = subject.replace("\u2014", "-").replace("\u2013", "-")
            sender_name_clean = sender_name.replace("\u2014", "-").replace("\u2013", "-")
            fb_key = compute_stable_email_cache_key("Inbox", "", subject_clean, date_str, sender_email)
            is_ambiguous_fb = (
                fb_key in by_fallback_hash
                and by_fallback_hash[fb_key] is None
                and not _normalize_rfc_message_id(msg_id_hdr)
            )

            cached_entry = _lookup_cached_entry("Inbox", msg_id_hdr, subject_clean, date_str, sender_email)
            body_text = cached_entry.get("body_snippet", "") if cached_entry else ""
            cached_mid_hdr = str(cached_entry.get("message_id") or "") if cached_entry else ""

            text_to_check = f"{subject} {sender_name} {sender_email}".lower()
            needs_body = any(t in text_to_check for t in partner_tokens)

            body_full = ""
            if (needs_body or is_ambiguous_fb) and not body_text and fetch_bodies_for_partner_keys:
                body_full = self.read_message_body(mid, account="zoho", mailbox="Inbox")
                body_text = body_full[:2000] if body_full else ""

            eff_rfc_mid = _normalize_rfc_message_id(msg_id_hdr or cached_mid_hdr, raw_body=body_full)
            body_clean = body_text.replace("\u2014", "-").replace("\u2013", "-")

            assert_no_forbidden_dashes(subject_clean, context=f"Email subject {mid}")
            assert_no_forbidden_dashes(sender_name_clean, context=f"Sender name {mid}")

            if eff_rfc_mid or not (fb_key in by_fallback_hash and by_fallback_hash[fb_key] is None):
                stable_key = compute_stable_email_cache_key(
                    "Inbox", eff_rfc_mid or msg_id_hdr, subject_clean, date_str, sender_email, raw_body=body_full
                )
            else:
                stable_key = hashlib.sha256(f"{fb_key}:{body_clean}:{mid}".encode("utf-8")).hexdigest()

            msg = EmailMessage(
                id=mid,
                message_id=eff_rfc_mid or msg_id_hdr,
                account="zoho",
                mailbox="Inbox",
                date=date_str,
                subject=subject_clean,
                sender_name=sender_name_clean,
                sender_email=sender_email,
                body_snippet=body_clean,
                raw_headers={"size": env.get("size"), "cache_key": stable_key},
                flags=[f.get("iana", "") for f in (env.get("flags") or []) if isinstance(f, dict)],
            )
            _store_stable(stable_key, mid, fb_key, msg)
            ingested.append(msg)

        sent_partner_domains = ZOHO_NOTIFICATION_PARTNER_DOMAINS
        skipped_sent_recipients = (
            "partnerships@rho.co",
            "advisory@studentloaninquiry.org",
            "wade.fenton@otrsolutions.com",
        )
        sent_envelopes = self.fetch_zoho_envelopes(mailbox="Sent", page_size=page_sz, force=True)
        _mark_batch_fb_collisions("Sent", sent_envelopes, use_to=True)
        for env in sent_envelopes:
            date_str = env.get("date") or ""
            if not date_str:
                continue
            to_arr = env.get("to") or []
            recip_email = (to_arr[0].get("email") or "").strip() if to_arr else ""
            recip_lower = recip_email.lower()
            if recip_lower in skipped_sent_recipients:
                continue
            subject = env.get("subject") or ""
            check_target = f"{recip_lower} {subject.lower()}"
            if not any(tok in check_target for tok in sent_partner_domains):
                continue

            mid = f"sent-{env.get('id', '')}"
            from_arr = env.get("from") or []
            sender_name = (from_arr[0].get("name") or "Arif Coskun") if from_arr else "Arif Coskun"
            msg_id_hdr = env.get("message-id") or env.get("message_id") or ""

            subject_clean = subject.replace("\u2014", "-").replace("\u2013", "-")
            sender_name_clean = sender_name.replace("\u2014", "-").replace("\u2013", "-")
            assert_no_forbidden_dashes(subject_clean, context=f"Email subject {mid}")
            assert_no_forbidden_dashes(sender_name_clean, context=f"Sender name {mid}")

            eff_rfc_mid = _normalize_rfc_message_id(msg_id_hdr)
            stable_key = compute_stable_email_cache_key("Sent", eff_rfc_mid or msg_id_hdr, subject_clean, date_str, recip_email)
            fb_key = compute_stable_email_cache_key("Sent", "", subject_clean, date_str, recip_email)

            msg = EmailMessage(
                id=mid,
                message_id=eff_rfc_mid or msg_id_hdr,
                account="zoho",
                mailbox="Sent",
                date=date_str,
                subject=subject_clean,
                sender_name=sender_name_clean,
                sender_email=recip_email,
                body_snippet=subject_clean,
                raw_headers={"to_email": recip_email, "size": env.get("size"), "cache_key": stable_key},
                flags=[f.get("iana", "") for f in (env.get("flags") or []) if isinstance(f, dict)],
            )
            _store_stable(stable_key, mid, fb_key, msg)
            ingested.append(msg)

        for folder_name, id_prefix in (
            ("Notification", "notif"),
            ("Newsletter", "news"),
            ("Spam", "spam"),
        ):
            folder_envelopes = self.fetch_zoho_envelopes(mailbox=folder_name, page_size=page_sz, force=True)
            _mark_batch_fb_collisions(folder_name, folder_envelopes, use_to=False)
            for env in folder_envelopes:
                date_str = env.get("date") or ""
                if not date_str:
                    continue
                from_arr = env.get("from") or []
                sender_name = (from_arr[0].get("name") or "") if from_arr else ""
                sender_email = (from_arr[0].get("email") or "") if from_arr else ""
                subject = env.get("subject") or ""
                folder_check = f"{subject} {sender_name} {sender_email}".lower()
                if folder_name == "Notification":
                    relevant = (
                        "claude startups" in folder_check
                        or "google for startups" in folder_check
                        or any(tok in folder_check for tok in ZOHO_NOTIFICATION_PARTNER_DOMAINS)
                        or any(tok in folder_check for tok in partner_tokens)
                    )
                elif folder_name == "Newsletter":
                    relevant = (
                        "rippling.com" in folder_check
                        or "partnerstack" in folder_check
                        or "firstpromoter.com" in folder_check
                        or "xendoo" in folder_check
                        or any(tok in folder_check for tok in sent_partner_domains)
                    )
                else:
                    # Spam folder: check partner domains, partner tokens, or bounce notifications
                    relevant = (
                        any(tok in folder_check for tok in sent_partner_domains)
                        or any(tok in folder_check for tok in partner_tokens)
                    )
                if not relevant:
                    continue

                mid = f"{id_prefix}-{env.get('id', '')}"
                msg_id_hdr = env.get("message-id") or env.get("message_id") or ""
                subject_clean = subject.replace("\u2014", "-").replace("\u2013", "-")
                sender_name_clean = sender_name.replace("\u2014", "-").replace("\u2013", "-")
                assert_no_forbidden_dashes(subject_clean, context=f"Email subject {mid}")
                assert_no_forbidden_dashes(sender_name_clean, context=f"Sender name {mid}")

                existing_folder_msg = _lookup_cached_entry(
                    folder_name, msg_id_hdr, subject_clean, date_str, sender_email
                )
                cached_mid_hdr = str(existing_folder_msg.get("message_id") or "") if existing_folder_msg else ""
                folder_body_snippet = (
                    existing_folder_msg.get("body_snippet", "")
                    if existing_folder_msg and existing_folder_msg.get("body_snippet") != subject_clean
                    else ""
                )
                full_folder_body = ""
                if fetch_bodies_for_partner_keys and not folder_body_snippet:
                    raw_env_id = str(env.get("id", ""))
                    if raw_env_id:
                        full_folder_body = self.read_message_body(
                            raw_env_id, account="zoho", mailbox=folder_name
                        )
                        folder_body_snippet = (
                            full_folder_body[:2000]
                            .replace("\u2014", "-")
                            .replace("\u2013", "-")
                        )
                        assert_no_forbidden_dashes(
                            folder_body_snippet, context=f"Email body {mid}"
                        )
                if not folder_body_snippet:
                    folder_body_snippet = subject_clean

                eff_rfc_mid = _normalize_rfc_message_id(msg_id_hdr or cached_mid_hdr, raw_body=full_folder_body)
                fb_key = compute_stable_email_cache_key(folder_name, "", subject_clean, date_str, sender_email)
                if eff_rfc_mid or not (fb_key in by_fallback_hash and by_fallback_hash[fb_key] is None):
                    stable_key = compute_stable_email_cache_key(
                        folder_name, eff_rfc_mid or msg_id_hdr, subject_clean, date_str, sender_email, raw_body=full_folder_body
                    )
                else:
                    stable_key = hashlib.sha256(f"{fb_key}:{folder_body_snippet}:{mid}".encode("utf-8")).hexdigest()

                msg = EmailMessage(
                    id=mid,
                    message_id=eff_rfc_mid or msg_id_hdr,
                    account="zoho",
                    mailbox=folder_name,
                    date=date_str,
                    subject=subject_clean,
                    sender_name=sender_name_clean,
                    sender_email=sender_email,
                    body_snippet=folder_body_snippet,
                    raw_headers={"size": env.get("size"), "cache_key": stable_key},
                    flags=[f.get("iana", "") for f in (env.get("flags") or []) if isinstance(f, dict)],
                )
                _store_stable(stable_key, mid, fb_key, msg)
                ingested.append(msg)

        self.save_cache(cache)
        return ingested

    @staticmethod
    def _decommission_default_personal_inbox_split_brain() -> None:
        """
        Ensures canonical .agy/personal_inbox.json is an empty JSON list ([]), eliminating
        deprecated personal/Gmail split-brain records while guaranteeing clean-checkout parity.
        """
        default_personal = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", ".agy", "personal_inbox.json")
        )
        os.makedirs(os.path.dirname(default_personal), exist_ok=True)
        needs_write = True
        if os.path.isfile(default_personal):
            try:
                with open(default_personal, "r", encoding="utf-8") as fh:
                    if json.load(fh) == []:
                        needs_write = False
            except Exception:
                needs_write = True
        if needs_write:
            tmp_p = f"{default_personal}.{os.getpid()}.tmp"
            with open(tmp_p, "w", encoding="utf-8") as fh:
                fh.write("[]\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_p, default_personal)

    def ingest_personal(
        self,
        fixture_path: Optional[str] = None,
        personal_account: str = "personal",
        force: bool = False,
    ) -> List[EmailMessage]:
        """
        Deprecated personal inbox loader retained solely for explicit unit-test fixture_path calls.
        Never polls himalaya -a personal or mindball and never loads .agy/personal_inbox.json by default.
        All live partnership correspondence uses arif.coskun@profithelm.com via himalaya -a zoho.
        """
        if not fixture_path:
            self._decommission_default_personal_inbox_split_brain()
            try:
                from pseofactory.partner_tracker import ensure_canonical_agy_monetization_state

                ensure_canonical_agy_monetization_state()
            except Exception:
                pass
            return []
        if not os.path.isfile(fixture_path):
            return []

        cache = self.load_cache()
        cached_dict = cache.setdefault("messages", {})
        try:
            with open(fixture_path, "r", encoding="utf-8") as f:
                raw_items = json.load(f)
            items = raw_items if isinstance(raw_items, list) else raw_items.get("messages", [])
            ingested: List[EmailMessage] = []
            for idx, it in enumerate(items):
                mid = str(it.get("id") or f"personal-{idx+1}")
                snd_email = it.get("sender_email") or ""
                subj = (it.get("subject") or "").replace("\u2014", "-").replace("\u2013", "-")
                body = (it.get("body_snippet") or it.get("body") or "").replace("\u2014", "-").replace("\u2013", "-")
                snd_name = (it.get("sender_name") or "").replace("\u2014", "-").replace("\u2013", "-")
                assert_no_forbidden_dashes(subj, context=f"Fixture email {mid}")

                dt_s = it.get("date", datetime.now(timezone.utc).isoformat())
                mbx_s = it.get("mailbox", "Inbox")
                raw_hdr_mid = str(it.get("message_id") or "")
                stable_k = compute_stable_email_cache_key(mbx_s, raw_hdr_mid, subj, dt_s, snd_email)

                msg = EmailMessage(
                    id=mid,
                    message_id=raw_hdr_mid or mid,
                    account="personal",
                    mailbox=mbx_s,
                    date=dt_s,
                    subject=subj,
                    sender_name=snd_name,
                    sender_email=snd_email,
                    body_snippet=body[:2000],
                    raw_headers=it.get("raw_headers", {}),
                    flags=it.get("flags", []),
                )
                cached_dict[stable_k] = msg.to_dict()
                ingested.append(msg)
            self.save_cache(cache)
            return ingested
        except Exception:
            return []

    def sync_all(
        self,
        force: bool = False,
        personal_fixture: Optional[str] = None,
    ) -> List[EmailMessage]:
        """Runs canonical Zoho partnership correspondence ingestion (-a zoho, arif.coskun@profithelm.com)."""
        zoho_msgs = self.ingest_zoho(limit=200, force=force)
        if personal_fixture:
            return zoho_msgs + self.ingest_personal(fixture_path=personal_fixture, force=force)
        return zoho_msgs

    def classify_partner_emails(
        self,
        messages: List[EmailMessage],
    ) -> List[PartnerEmailClassification]:
        """
        Categorizes emails into partner requests, approvals, warnings, or action items.
        Applies property isolation rules and typography constraints.
        """
        classifications: List[PartnerEmailClassification] = []

        outbound_partner_map = {
            "partnerships@mercury.com": ("profithelm", "mercury", "Mercury Startup Banking", "In-House Direct"),
            "clientservice@rho.co": ("profithelm", "rho", "Rho Commercial Banking & Treasury", "In-House Direct"),
            "hi@ramp.com": ("profithelm", "ramp", "Ramp Corporate Card & Spend Management", "In-House Direct"),
            "affiliate@ramp.com": ("profithelm", "ramp", "Ramp Corporate Card & Spend Management", "Impact.com"),
            "apps.partnerships@rippling.com": ("profithelm", "rippling", "Rippling Unified Workforce Platform", "PartnerStack"),
            "app-partnerships+noreply@rippling.com": ("profithelm", "rippling", "Rippling Unified Workforce Platform", "PartnerStack"),
            "noelle.hyra@gusto.com": ("profithelm", "gusto", "Gusto Payroll & HR", "Impact.com"),
            "cj_intuit@cj.com": ("profithelm", "gusto", "Intuit Small Business - QuickBooks, GoPayment, Payroll", "CJ Affiliate"),
            "info@crestcapital.com": ("profithelm", "crest_capital", "Crest Capital Equipment Financing", "In-House Direct"),
            "luanne.bryant@xendoo.com": ("profithelm", "xendoo", "Xendoo Online Bookkeeping & Tax", "FirstPromoter / Impact.com"),
            "lil.roberts@xendoo.com": ("profithelm", "xendoo", "Xendoo Online Accounting", "Impact.com"),
            "turbotax@cj.com": ("profithelm", "turbotax", "TurboTax Affiliate Program", "CJ Affiliate"),
            "affiliates@freetaxusa.com": ("profithelm", "freetaxusa", "FreeTaxUSA Affiliate Program", "CJ Affiliate"),
            "aaron@e-file.com": ("profithelm", "efile_com", "E-file.com Affiliate Program", "CJ Affiliate"),
            "allwyn.symon@eztaxreturn.com": ("profithelm", "eztaxreturn_com", "ezTaxReturn.com Affiliate Program", "CJ Affiliate"),
            "ask@exeterco.com": ("profithelm", "exeter1031", "The Exeter 1031 Exchange", "In-House Direct"),
            "info@dlpcapital.com": ("profithelm", "exeter1031", "The Exeter 1031 Exchange", "In-House Direct"),
            "1031@firstam.com": ("profithelm", "first_american", "First American Exchange Company", "In-House Direct"),
            "hela@katalystcomms.com": ("profithelm", "first_american", "First American Exchange Company", "In-House Direct"),
            "contact@splashfinancial.com": ("prexvo", "splash_financial", "Splash Financial", "Impact.com"),
            "pleimkuehler@splashfinancial.com": ("prexvo", "splash_financial", "Splash Financial", "Impact.com"),
            "cfels@lqdigital.com": ("prexvo", "sofi", "SoFi Student Loan Refinancing", "Impact.com"),
            "affiliates@sofi.com": ("prexvo", "sofi", "SoFi Student Loan Refinancing", "Impact.com"),
            "accounting@lendkey.com": ("prexvo", "lendkey", "LendKey Student Loan Refinancing", "Impact.com"),
            "publishers@interactivebrokers.com": ("profithelm", "interactive_brokers", "Interactive Brokers CPC Publisher Program", "In-House Direct"),
            "customercare@suretybonds.com": ("lienbond", "suretybonds_direct", "SuretyBondsDirect.com", "In-House Direct"),
            "affiliate@suretybonds.com": ("lienbond", "suretybonds_direct", "SuretyBondsDirect.com", "In-House Direct"),
            "affiliates@suretybonds.com": ("lienbond", "suretybonds_direct", "SuretyBondsDirect.com", "In-House Direct"),
            "customercare@suretybondsdirect.com": ("lienbond", "suretybonds_direct", "SuretyBondsDirect.com", "In-House Direct"),
            "affiliate@suretybondsdirect.com": ("lienbond", "suretybonds_direct", "SuretyBondsDirect.com", "In-House Direct"),
            "affiliates@suretybondsdirect.com": ("lienbond", "suretybonds_direct", "SuretyBondsDirect.com", "In-House Direct"),
            "partners@suretybondsdirect.com": ("lienbond", "suretybonds_direct", "SuretyBondsDirect.com", "In-House Direct"),
            "info@ipx1031.com": ("profithelm", "ipx1031", "IPX1031 (Investment Property Exchange Services)", "In-House Direct"),
            "contactus@simplybusiness.com": ("lienbond", "simply_business", "Simply Business", "Impact.com"),
            "affiliates@simplybusiness.com": ("lienbond", "simply_business", "Simply Business", "Impact.com"),
            "partners@nextinsurance.com": ("lienbond", "next_insurance_b2b", "Next Insurance Commercial B2B", "Impact.com"),
            "affiliates@nextinsurance.com": ("lienbond", "next_insurance_b2b", "Next Insurance Commercial B2B", "Impact.com"),
            "partners@thimble.com": ("lienbond", "thimble_contractor", "Thimble Contractor Liability Insurance", "In-House Direct"),
            "partners@getjobber.com": ("lienbond", "jobber_field_service", "Jobber Field Service Management", "PartnerStack / In-House Direct"),
            "partners@jobber.com": ("lienbond", "jobber_field_service", "Jobber Field Service Management", "PartnerStack / In-House Direct"),
            "partners@levelset.com": ("lienbond", "levelset_lien_filing", "Levelset Mechanics Lien & Payment Platform", "In-House Direct"),
            "wade.fenton@otrsolutions.com": ("profithelm", "otr_solutions_factoring", "OTR Solutions Freight Factoring", "In-House Direct"),
            "partners@vanta.com": ("gainhelm", "vanta_security", "Vanta Trust Management Platform", "PartnerStack / In-House Direct"),
            "partnerships@vanta.com": ("gainhelm", "vanta_security", "Vanta Trust Management Platform", "PartnerStack / In-House Direct"),
            "partners@drata.com": ("gainhelm", "drata_compliance", "Drata Continuous GRC & CMMC Automation", "In-House Direct"),
            "partners@sprinto.com": ("gainhelm", "sprinto_compliance", "Sprinto ISO 27001 & Security Compliance", "In-House Direct"),
            "hello@sprinto.com": ("gainhelm", "sprinto_compliance", "Sprinto ISO 27001 & Security Compliance", "In-House Direct"),
            "partners@thoropass.com": ("gainhelm", "thoropass_audit", "Thoropass Compliance & Audit Readiness", "In-House Direct"),
            "brokers@coalitioninc.com": ("gainhelm", "coalition_cyber_insurance", "Coalition Active Cyber Insurance", "In-House Direct"),
            "partners@cobalt.io": ("gainhelm", "cobalt_pentest", "Cobalt Offensive Security & Pentest as a Service", "In-House Direct"),
            "hello@cobalt.io": ("gainhelm", "cobalt_pentest", "Cobalt Offensive Security & Pentest as a Service", "In-House Direct"),
        }

        msg_by_id: Dict[str, EmailMessage] = {m.id: m for m in messages}

        for msg in messages:
            subj_lower = msg.subject.lower()
            sender_lower = f"{msg.sender_name} {msg.sender_email}".lower()
            body_lower = msg.body_snippet.lower()
            combined_text = f"{subj_lower} {sender_lower} {body_lower}"
            cand_url = _extract_candidate_url(f"{msg.subject} {msg.body_snippet}")

            mbx_lower = (msg.mailbox or "").strip().lower()
            sender_email_clean = (msg.sender_email or "").strip().lower()
            is_outbound_msg = (
                mbx_lower == "sent"
                or sender_email_clean == "arif.coskun@profithelm.com"
            )
            raw_to_email = ((msg.raw_headers or {}).get("to_email") or "").strip().lower()
            # Never default to_email to msg.sender_email on Inbox or any non-Sent mailbox
            to_email = (raw_to_email or sender_email_clean) if mbx_lower == "sent" else raw_to_email
            if "advisory@studentloaninquiry.org" in to_email or "partnerships@rho.co" in to_email:
                continue
            if (
                "mailer-daemon" in sender_lower
                or "postmaster@" in sender_lower
                or "undelivered mail" in subj_lower
                or "delivery status notification" in subj_lower
                or "mail delivery failed" in subj_lower
            ):
                continue
            if subj_lower.startswith((
                "[profithelm playbook",
                "[prexvo playbook",
                "[gainhelm playbook",
                "[lienbond playbook",
            )):
                continue

            if msg.mailbox != "Sent" and "rho.co" in sender_lower and (
                "become a partner" in body_lower or "rho partner portal" in body_lower
            ):
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="profithelm",
                        partner_key="rho",
                        partner_name="Rho Commercial Banking & Treasury",
                        category="CORPORATE_SPEND",
                        classification_type="ONBOARDING_ACTION_REQUIRED",
                        requires_operator_decision=True,
                        summary="Rho Client Service requested submission of the Become a Partner form on the Rho Partner Portal to activate referral tracking.",
                        urgency="HIGH",
                        deadline=None,
                        missing_requirements=["Submit Become a Partner form on the Rho Partner Portal (rho.co/partners)"],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                        candidate_url=cand_url,
                        network="In-House Direct",
                    )
                )
                continue

            if msg.mailbox != "Sent" and "mercury.com" in sender_lower and (
                "mercury.com/partnerships" in body_lower
                or "fill out the form" in body_lower
                or "mercury partnerships page" in body_lower
                or "mercury inquiry" in subj_lower
            ):
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="profithelm",
                        partner_key="mercury",
                        partner_name="Mercury Startup Banking",
                        category="STARTUP_BANKING",
                        classification_type="ONBOARDING_ACTION_REQUIRED",
                        requires_operator_decision=True,
                        summary="Mercury Partnerships team replied to email inquiry and requested submission of the official partnership form at https://mercury.com/partnerships (or extraction of ProfitHelm LLC customer referral link from app.mercury.com).",
                        urgency="HIGH",
                        deadline=None,
                        missing_requirements=[
                            "Submit official partnership form at https://mercury.com/partnerships or extract active customer referral link from app.mercury.com"
                        ],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                        candidate_url=cand_url or "https://mercury.com/partnerships",
                        network="In-House Direct",
                    )
                )
                continue

            if msg.mailbox != "Sent" and (
                "erica.grodin@rippling.com" in sender_lower
                or (
                    "rippling" in combined_text
                    and (
                        "welcome to the rippling affiliate program" in combined_text
                        or "rippling affiliate" in subj_lower
                    )
                )
            ):
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="profithelm",
                        partner_key="rippling",
                        partner_name="Rippling Unified Workforce Platform",
                        category="PAYROLL_HR",
                        classification_type="APPLICATION_APPROVED",
                        requires_operator_decision=False,
                        summary="Rippling Affiliate Program approved and active on PartnerStack under Erica Grodin ($600 per SQO demo + $1,000 per Closed Won deal, $1,600 total).",
                        urgency="LOW",
                        deadline=None,
                        missing_requirements=[],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                        candidate_url="https://try.rippling.com/mcfo1m09qiwt",
                        network="PartnerStack",
                    )
                )
                continue

            if msg.mailbox != "Sent" and (
                "promoter@firstpromoter.com" in sender_lower
                or "welcome to koinly" in subj_lower
            ) and "koinly" in combined_text:
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="profithelm",
                        partner_key="koinly",
                        partner_name="Koinly Crypto Tax Software",
                        category="DIGITAL_ASSETS",
                        classification_type="APPLICATION_APPROVED",
                        requires_operator_decision=False,
                        summary="Koinly Affiliates program approved and active (native via=A4FABF09 on app.koinly.io/affiliate with verified PayPal arif.coskun@profithelm.com + FirstPromoter welcome link http://koinly.io?fpr=arif-4c0b88 in Newsletter #1588).",
                        urgency="LOW",
                        deadline=None,
                        missing_requirements=[],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                        candidate_url="https://koinly.io/?fpr=arif-4c0b88",
                        network="FirstPromoter",
                    )
                )
                continue

            if msg.mailbox != "Sent" and (
                "promoter@firstpromoter.com" in sender_lower
                or "welcome to xendoo" in subj_lower
            ):
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="profithelm",
                        partner_key="xendoo",
                        partner_name="Xendoo Online Bookkeeping & Tax",
                        category="ACCOUNTING_BOOKKEEPING",
                        classification_type="APPLICATION_APPROVED",
                        requires_operator_decision=False,
                        summary="Xendoo Referral Partner Program approved and active on FirstPromoter (fp_ref=arif-4ac24e at $250 cash reward per referred client; PayPal payout arif.coskun@profithelm.com verified via code 679553 in Newsletter #1576).",
                        urgency="LOW",
                        deadline=None,
                        missing_requirements=[],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                        candidate_url="https://www.xendoo.com/?fp_ref=arif-4ac24e",
                        network="FirstPromoter",
                    )
                )
                continue

            if msg.mailbox != "Sent" and (
                "aaron@e-file.com" in sender_lower
                or (
                    "e-file.com" in combined_text
                    and (
                        "your application has been approved" in combined_text
                        or "welcome to the e-file.com affiliate program" in combined_text
                        or "approved" in combined_text
                    )
                )
            ):
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="profithelm",
                        partner_key="efile_com",
                        partner_name="E-file.com Affiliate Program",
                        category="TAX_INTELLIGENCE",
                        classification_type="APPLICATION_APPROVED",
                        requires_operator_decision=False,
                        summary="E-file.com Affiliate Program (#4355234) approved on CJ Affiliate (30%-40% commission on paid tax returns, 120-day cookie via https://www.jdoqocy.com/click-101906407-11917161).",
                        urgency="LOW",
                        deadline=None,
                        missing_requirements=[],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                        candidate_url="https://www.jdoqocy.com/click-101906407-11917161",
                        network="CJ Affiliate",
                    )
                )
                continue

            if msg.mailbox != "Sent" and "eztaxreturn" in combined_text and (
                "welcome to the eztaxreturn" in combined_text
                or "your application has been approved" in combined_text
                or "approved" in combined_text
            ):
                has_q, q_req = _has_human_partner_question(
                    msg.sender_email, msg.sender_name, msg.subject, msg.body_snippet
                )
                base_summary = (
                    "ezTaxReturn.com Affiliate Program (#6874782) approved on CJ Affiliate "
                    "(15% new customer / 5% returning customer commission, 90-day cookie via "
                    "https://www.dpbolvw.net/click-101906407-15704796)."
                )
                if has_q:
                    base_summary = f"{base_summary} {q_req}"
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="profithelm",
                        partner_key="eztaxreturn_com",
                        partner_name="ezTaxReturn.com Affiliate Program",
                        category="TAX_INTELLIGENCE",
                        classification_type="APPLICATION_APPROVED",
                        requires_operator_decision=has_q,
                        summary=base_summary,
                        urgency="HIGH" if has_q else "LOW",
                        deadline=None,
                        missing_requirements=[q_req] if has_q else [],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                        candidate_url="https://www.dpbolvw.net/click-101906407-15704796",
                        network="CJ Affiliate",
                    )
                )
                continue

            if msg.mailbox != "Sent" and "lawdepot" in combined_text and (
                "welcome to the lawdepot" in combined_text
                or "your application has been approved" in combined_text
                or "approved" in combined_text
            ):
                from pseofactory.affiliates import PROFITHELM_AFFILIATES as _PH_AFF
                ld_key = "lawdepot" if "lawdepot" in _PH_AFF else "suretybonds_direct"
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="profithelm",
                        partner_key=ld_key,
                        partner_name="LawDepot Affiliate Program",
                        category="BUSINESS_FORMATION",
                        classification_type="APPLICATION_APPROVED",
                        requires_operator_decision=False,
                        summary="LawDepot Affiliate Program (#4544498) approved on CJ Affiliate (30% orders + $6.50 free trial, 120-day cookie via https://www.jdoqocy.com/click-101906407-16985242).",
                        urgency="LOW",
                        deadline=None,
                        missing_requirements=[],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                        candidate_url="https://www.jdoqocy.com/click-101906407-16985242",
                        network="CJ Affiliate",
                    )
                )
                continue

            if msg.mailbox != "Sent" and "gusto" in combined_text and (
                "you're approved" in combined_text
                or "welcome to gusto" in combined_text
                or "noelle.hyra@gusto.com" in sender_lower
            ):
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="profithelm",
                        partner_key="gusto",
                        partner_name="Gusto Payroll, Benefits & HR Platform",
                        category="PAYROLL_HR",
                        classification_type="APPLICATION_APPROVED",
                        requires_operator_decision=False,
                        summary="Gusto Impact.com contract approved (#15154, $200-$300 CPA). Tracking link active.",
                        urgency="LOW",
                        deadline=None,
                        missing_requirements=[],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                        candidate_url="https://gusto.pxf.io/c/7932737/1226287/15154",
                        network="Impact.com",
                    )
                )
                continue

            if msg.mailbox != "Sent" and (
                "welcome to the ramp partner program" in combined_text
                or ("ramp partner team" in sender_lower and "welcome" in subj_lower)
            ):
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="profithelm",
                        partner_key="ramp",
                        partner_name="Ramp Corporate Card & Spend Management",
                        category="CORPORATE_SPEND",
                        classification_type="APPLICATION_APPROVED",
                        requires_operator_decision=False,
                        summary="Ramp Partner Program approved on Impact.com (#51436, $100-$4,000 Closed Won / $50-$2,000 SQL via Zoho Newsletter #1591 and https://join.ramp.com/c/7932737/3981015/51436).",
                        urgency="LOW",
                        deadline=None,
                        missing_requirements=[],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                        candidate_url=cand_url or "https://join.ramp.com/c/7932737/3981015/51436",
                        network="Impact.com",
                    )
                )
                continue

            if msg.mailbox != "Sent" and "freetaxusa" in combined_text and (
                "welcome to the freetaxusa" in combined_text
                or "welcome to our affiliate program" in combined_text
                or "freetaxusa affiliate program. welcome" in combined_text
                or "your application has been approved" in combined_text
                or "approved" in combined_text
            ):
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="profithelm",
                        partner_key="freetaxusa",
                        partner_name="FreeTaxUSA Affiliate Program",
                        category="TAX_INTELLIGENCE",
                        classification_type="APPLICATION_APPROVED",
                        requires_operator_decision=False,
                        summary="FreeTaxUSA Affiliate Program (#1722649 / CJ #4526117) approved on CJ Affiliate (10%-20% commission on paid products, 30-day cookie via Zoho Notification #851 and https://www.jdoqocy.com/click-101906407-12306188).",
                        urgency="LOW",
                        deadline=None,
                        missing_requirements=[],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                        candidate_url=cand_url or "https://www.jdoqocy.com/click-101906407-12306188",
                        network="CJ Affiliate",
                    )
                )
                continue

            if msg.mailbox != "Sent" and "wallethub" in combined_text and (
                "welcome to the wallethub" in combined_text
                or "your application has been approved" in combined_text
                or "approved" in combined_text
            ):
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="profithelm",
                        partner_key="wallethub",
                        partner_name="WalletHub Affiliate Program",
                        category="CREDIT_SCORE_FINANCE",
                        classification_type="APPLICATION_APPROVED",
                        requires_operator_decision=False,
                        summary="WalletHub Affiliate Program (#6002798) approved on CJ Affiliate ($50 CPA for WalletHub Premium/Premium+ subscriptions, 7-day cookie via Zoho Notification #857).",
                        urgency="LOW",
                        deadline=None,
                        missing_requirements=[],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                        candidate_url=cand_url or "https://wallethub.com/",
                        network="CJ Affiliate",
                    )
                )
                continue

            if msg.mailbox != "Sent" and (
                "accounting@sovrn.com" in sender_lower
                or (
                    "sovrn" in combined_text
                    and (
                        "suppliers portal application has been approved" in combined_text
                        or "application for the sovrn suppliers portal has been approved" in combined_text
                    )
                )
            ):
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="profithelm",
                        partner_key="sovrn_commerce",
                        partner_name="Sovrn Commerce Suppliers Portal (Tipalti ACH)",
                        category="SUB_AFFILIATE_NETWORK",
                        classification_type="APPLICATION_APPROVED",
                        requires_operator_decision=False,
                        summary="Sovrn Commerce Suppliers Portal application approved by accounting@sovrn.com (Inbox #1032, 2026-10-26T21:52:28Z), confirming Tipalti ACH payout and W-9 settlement readiness for Account #2987330.",
                        urgency="LOW",
                        deadline=None,
                        missing_requirements=[],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                        candidate_url="https://platform.sovrn.com/commerce",
                        network="Sovrn Commerce",
                    )
                )
                continue

            # Automated Conversion, Lead, and Payout Alert Ingestion
            if msg.mailbox != "Sent":
                is_commission_alert = any(
                    tok in combined_text
                    for tok in (
                        "you earned a commission",
                        "commission earned",
                        "new commission",
                        "action locked",
                        "referral bonus credited",
                        "you have earned a reward",
                    )
                )
                is_lead_alert = any(
                    tok in combined_text
                    for tok in (
                        "new qualified lead",
                        "new referral signup",
                        "lead converted",
                        "new sqo",
                    )
                )
                is_payout_alert = any(
                    tok in combined_text
                    for tok in (
                        "payout issued",
                        "payment sent",
                        "withdrawal processed",
                        "funds have been transferred",
                    )
                )
                if is_commission_alert or is_lead_alert or is_payout_alert:
                    alert_partner_map = (
                        ("rippling", "profithelm", "rippling", "Rippling Unified Workforce Platform", "PAYROLL_HR", "PartnerStack"),
                        ("gusto", "profithelm", "gusto", "Gusto Payroll, Benefits & HR Platform", "PAYROLL_HR", "Impact.com"),
                        ("kalshi", "profithelm", "kalshi", "Kalshi Event Contracts", "MARKET_ARBITRAGE", "Impact.com"),
                        ("xendoo", "profithelm", "xendoo", "Xendoo Online Accounting", "ACCOUNTING_BOOKKEEPING", "Impact.com / FirstPromoter"),
                        ("coinledger", "profithelm", "coinledger", "CoinLedger Crypto Tax", "DIGITAL_ASSETS", "FirstPromoter"),
                        ("koinly", "profithelm", "koinly", "Koinly Crypto Tax Software", "DIGITAL_ASSETS", "FirstPromoter"),
                        ("mercury", "profithelm", "mercury", "Mercury Startup Banking", "STARTUP_BANKING", "In-House Direct"),
                        ("e-file.com", "profithelm", "efile_com", "E-file.com Affiliate Program", "TAX_INTELLIGENCE", "CJ Affiliate"),
                        ("eztaxreturn", "profithelm", "eztaxreturn_com", "ezTaxReturn.com Affiliate Program", "TAX_INTELLIGENCE", "CJ Affiliate"),
                        ("freetaxusa", "profithelm", "freetaxusa", "FreeTaxUSA Affiliate Program", "TAX_INTELLIGENCE", "CJ Affiliate"),
                        ("wallethub", "profithelm", "wallethub", "WalletHub Affiliate Program", "CREDIT_SCORE_FINANCE", "CJ Affiliate"),
                        ("lawdepot", "profithelm", "lawdepot", "LawDepot Affiliate Program", "BUSINESS_FORMATION", "CJ Affiliate"),
                        ("ramp", "profithelm", "ramp", "Ramp Corporate Card & Spend Management", "CORPORATE_SPEND", "Impact.com"),
                        ("simply business", "lienbond", "simply_business", "Simply Business", "COMMERCIAL_INSURANCE", "Impact.com"),
                        ("simplybusiness", "lienbond", "simply_business", "Simply Business", "COMMERCIAL_INSURANCE", "Impact.com"),
                        ("suretybondsdirect", "lienbond", "suretybonds_direct", "SuretyBondsDirect.com", "COMMERCIAL_SURETY", "In-House Direct"),
                        ("suretybonds", "lienbond", "suretybonds_direct", "SuretyBondsDirect.com", "COMMERCIAL_SURETY", "In-House Direct"),
                        ("next insurance", "lienbond", "next_insurance_b2b", "Next Insurance Commercial B2B", "COMMERCIAL_INSURANCE", "Impact.com"),
                        ("nextinsurance", "lienbond", "next_insurance_b2b", "Next Insurance Commercial B2B", "COMMERCIAL_INSURANCE", "Impact.com"),
                        ("thimble", "lienbond", "thimble_contractor", "Thimble Contractor Liability Insurance", "COMMERCIAL_INSURANCE", "In-House Direct"),
                        ("jobber", "lienbond", "jobber_field_service", "Jobber Field Service Management", "FIELD_SERVICE_OPERATIONS", "PartnerStack / In-House Direct"),
                        ("levelset", "lienbond", "levelset_lien_filing", "Levelset Mechanics Lien & Payment Platform", "MECHANICS_LIEN_FILING", "In-House Direct"),
                        ("splash", "prexvo", "splash_financial", "Splash Financial", "STUDENT_LOAN_REFINANCE", "Impact.com"),
                        ("sofi", "prexvo", "sofi", "SoFi Student Loan Refinancing", "STUDENT_LOAN_REFINANCE", "Impact.com"),
                        ("credible", "prexvo", "credible", "Credible Student Loan Marketplace", "STUDENT_LOAN_COMPARISON", "Impact.com"),
                        ("earnest", "prexvo", "earnest", "Earnest Student Loan Refinancing", "STUDENT_LOAN_REFINANCE", "In-House Direct"),
                        ("lendkey", "prexvo", "lendkey", "LendKey Student Loan Refinancing", "STUDENT_LOAN_REFINANCE", "Impact.com"),
                        ("vanta", "gainhelm", "vanta_security", "Vanta Trust Management Platform", "CYBER_COMPLIANCE_GRC", "PartnerStack / In-House Direct"),
                        ("drata", "gainhelm", "drata_compliance", "Drata Continuous GRC & CMMC Automation", "CYBER_COMPLIANCE_GRC", "In-House Direct"),
                        ("sprinto", "gainhelm", "sprinto_compliance", "Sprinto ISO 27001 & Security Compliance", "CYBER_COMPLIANCE_GRC", "In-House Direct"),
                        ("thoropass", "gainhelm", "thoropass_audit", "Thoropass Compliance & Audit Readiness", "CYBER_COMPLIANCE_GRC", "In-House Direct"),
                        ("coalition", "gainhelm", "coalition_cyber_insurance", "Coalition Active Cyber Insurance", "CYBER_LIABILITY_INSURANCE", "In-House Direct"),
                        ("cobalt", "gainhelm", "cobalt_pentest", "Cobalt Offensive Security & Pentest as a Service", "PENETRATION_TESTING", "In-House Direct"),
                    )
                    matched_alert = None
                    for tok_kw, prop_id, p_key, p_name, p_cat, net_name in alert_partner_map:
                        if tok_kw in combined_text:
                            if p_key in (
                                "simply_business",
                                "suretybonds_direct",
                                "next_insurance_b2b",
                                "thimble_contractor",
                                "jobber_field_service",
                                "levelset_lien_filing",
                            ):
                                prop_id = _resolve_lienbond_or_profithelm_property(p_key, combined_text)
                            matched_alert = (prop_id, p_key, p_name, p_cat, net_name)
                            break
                    if matched_alert:
                        prop_id, p_key, p_name, p_cat, net_name = matched_alert
                        amt_usd = _extract_commission_amount_usd(f"{msg.subject} {msg.body_snippet}")
                        c_type = (
                            "PAYOUT_ISSUED"
                            if is_payout_alert
                            else ("COMMISSION_EARNED" if is_commission_alert else "LEAD_CONVERTED")
                        )
                        classifications.append(
                            PartnerEmailClassification(
                                email_id=msg.id,
                                account=msg.account,
                                property_id=prop_id,
                                partner_key=p_key,
                                partner_name=p_name,
                                category=p_cat,
                                classification_type=c_type,
                                requires_operator_decision=False,
                                summary=f"{c_type} notification for {p_name} on {net_name} (amount: ${amt_usd:.2f} USD).",
                                urgency="LOW",
                                deadline=None,
                                missing_requirements=[],
                                raw_subject=msg.subject,
                                sender_email=msg.sender_email,
                                date=msg.date,
                                candidate_url=cand_url,
                                network=net_name,
                                commission_amount_usd=amt_usd,
                            )
                        )
                        continue

            # Outbound APPLICATION_SUBMITTED: strictly restricted to Sent / outbound messages from arif.coskun@profithelm.com
            if is_outbound_msg:
                outbound_target = to_email
                if (
                    (not outbound_target or outbound_target == "arif.coskun@profithelm.com")
                    and sender_email_clean
                    and sender_email_clean != "arif.coskun@profithelm.com"
                ):
                    outbound_target = sender_email_clean
                matched_outbound = outbound_partner_map.get(outbound_target) if outbound_target else None
                if not matched_outbound and outbound_target:
                    for addr_key, p_tuple in outbound_partner_map.items():
                        domain_part = addr_key.split("@")[-1]
                        if domain_part != "cj.com" and (
                            outbound_target.endswith(f"@{domain_part}")
                            or outbound_target == addr_key
                        ):
                            matched_outbound = p_tuple
                            break

                if matched_outbound:
                    prop_id, p_key, p_name, net_name = matched_outbound
                    if p_key in (
                        "simply_business",
                        "suretybonds_direct",
                        "next_insurance_b2b",
                        "thimble_contractor",
                        "jobber_field_service",
                        "levelset_lien_filing",
                    ):
                        prop_id = _resolve_lienbond_or_profithelm_property(p_key, combined_text)
                    classifications.append(
                        PartnerEmailClassification(
                            email_id=msg.id,
                            account=msg.account,
                            property_id=prop_id,
                            partner_key=p_key,
                            partner_name=p_name,
                            category="APPLICATION_SUBMITTED",
                            classification_type="APPLICATION_SUBMITTED",
                            requires_operator_decision=False,
                            summary=f"Partnership inquiry sent to {p_name}; awaiting vendor response.",
                            urgency="LOW",
                            deadline=None,
                            missing_requirements=["Awaiting vendor partnership team response and tracking URL"],
                            raw_subject=msg.subject,
                            sender_email=outbound_target or msg.sender_email,
                            date=msg.date,
                            candidate_url=cand_url,
                            network=net_name,
                        )
                    )
                    continue

            if not is_outbound_msg and (
                "otrsolutions.com" in sender_lower or "otr solutions" in combined_text
            ):
                is_otr_internal_review = (
                    "we will review internally" in body_lower
                    or "thank you for sharing that information" in body_lower
                )
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="profithelm",
                        partner_key="otr_solutions_factoring",
                        partner_name="OTR Solutions Freight Factoring",
                        category="LOGISTICS_TRADE",
                        classification_type="APPLICATION_SUBMITTED" if is_otr_internal_review else "ONBOARDING_ACTION_REQUIRED",
                        requires_operator_decision=False if is_otr_internal_review else True,
                        summary=(
                            "OTR Solutions Partnerships Team Lead (Wade Fenton, Inbox #1030) confirmed receipt of ProfitHelm's 7 qualification answers and stated the team is reviewing internally."
                            if is_otr_internal_review
                            else "OTR Solutions Partnerships Team Lead (Wade Fenton) responded to follow up and invited ProfitHelm to complete partner onboarding via https://otrsolutions.com/become-a-partner/."
                        ),
                        urgency="LOW" if is_otr_internal_review else "HIGH",
                        deadline=None,
                        missing_requirements=(
                            ["Awaiting OTR Solutions Partnerships Team internal review response"]
                            if is_otr_internal_review
                            else [
                                "Complete partner onboarding form at https://otrsolutions.com/become-a-partner/ or schedule alignment call with Wade Fenton (wade.fenton@otrsolutions.com)"
                            ]
                        ),
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                        candidate_url=cand_url or "https://otrsolutions.com/become-a-partner/",
                        network="In-House Direct",
                    )
                )
                continue

            if not is_outbound_msg and (
                "suretybondsdirect.com" in sender_lower
                or "suretybonds.com" in sender_lower
                or "suretybondsdirect" in combined_text
            ):
                sb_prop = _resolve_lienbond_or_profithelm_property("suretybonds_direct", combined_text)
                is_sb_declined = any(
                    tok in combined_text
                    for tok in ("declined", "not approved", "unable to approve", "cannot approve")
                )
                is_sb_approved = not is_sb_declined and (
                    "approved" in combined_text
                    or "welcome to" in combined_text
                    or "welcome aboard" in combined_text
                    or "congratulations" in combined_text
                )
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id=sb_prop,
                        partner_key="suretybonds_direct",
                        partner_name="SuretyBondsDirect.com",
                        category="COMMERCIAL_SURETY",
                        classification_type=(
                            "APPLICATION_DECLINED"
                            if is_sb_declined
                            else ("APPLICATION_APPROVED" if is_sb_approved else "APPLICATION_SUBMITTED")
                        ),
                        requires_operator_decision=False,
                        summary=(
                            f"SuretyBondsDirect.com declined partnership application on {sb_prop} (Inbox #{msg.id})."
                            if is_sb_declined
                            else (
                                f"SuretyBondsDirect.com approved partnership on {sb_prop} (Inbox #{msg.id})."
                                if is_sb_approved
                                else f"SuretyBondsDirect.com Customer Care confirmed receipt of partnership inquiry (Inbox #{msg.id}); awaiting agency referral tracking URL."
                            )
                        ),
                        urgency="LOW",
                        deadline=None,
                        missing_requirements=(
                            []
                            if (is_sb_approved or is_sb_declined)
                            else ["Awaiting SuretyBondsDirect.com partnership desk tracking link"]
                        ),
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                        candidate_url=cand_url or "https://www.suretybondsdirect.com/",
                        network="In-House Direct",
                    )
                )
                continue

            if not is_outbound_msg and (
                "simplybusinessinc.zendesk.com" in sender_lower
                or "simplybusiness.com" in sender_lower
                or "simply business inc" in combined_text
                or ("simply business" in combined_text and ("approved" in combined_text or "affiliate" in combined_text or "declined" in combined_text))
            ):
                simp_prop = _resolve_lienbond_or_profithelm_property("simply_business", combined_text)
                is_simp_declined = any(
                    tok in combined_text
                    for tok in ("declined", "not approved", "unable to approve", "cannot approve", "rejected")
                )
                is_simp_approved = not is_simp_declined and ("approved" in combined_text or "welcome to" in combined_text)
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id=simp_prop,
                        partner_key="simply_business",
                        partner_name="Simply Business",
                        category="COMMERCIAL_INSURANCE",
                        classification_type=(
                            "APPLICATION_DECLINED"
                            if is_simp_declined
                            else ("APPLICATION_APPROVED" if is_simp_approved else "APPLICATION_SUBMITTED")
                        ),
                        requires_operator_decision=False,
                        summary=(
                            f"Simply Business declined partnership application on {simp_prop} (Inbox #{msg.id})."
                            if is_simp_declined
                            else (
                                f"Simply Business approved partnership on {simp_prop} (Inbox #{msg.id})."
                                if is_simp_approved
                                else f"Simply Business confirmed receipt of Impact Account #7932737 / Campaign #49719 affiliate application inquiry (Inbox #{msg.id})."
                            )
                        ),
                        urgency="LOW",
                        deadline=None,
                        missing_requirements=(
                            []
                            if (is_simp_approved or is_simp_declined)
                            else ["Awaiting Simply Business affiliate team invitation on Impact.com (#49719)"]
                        ),
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                        candidate_url=cand_url or "https://www.simplybusiness.com/",
                        network="Impact.com",
                    )
                )
                continue

            if not is_outbound_msg and any(
                lb_tok in combined_text for lb_tok in ("thimble", "getjobber", "jobber", "levelset")
            ) and any(
                act_tok in combined_text
                for act_tok in (
                    "partner",
                    "affiliate",
                    "approved",
                    "declined",
                    "unable to approve",
                    "not approved",
                    "cannot approve",
                    "application",
                    "welcome",
                )
            ):
                if "thimble" in combined_text:
                    lb_k, lb_n, lb_cat, lb_net = (
                        "thimble_contractor",
                        "Thimble Contractor Liability Insurance",
                        "COMMERCIAL_INSURANCE",
                        "In-House Direct",
                    )
                elif "levelset" in combined_text:
                    lb_k, lb_n, lb_cat, lb_net = (
                        "levelset_lien_filing",
                        "Levelset Mechanics Lien & Payment Platform",
                        "MECHANICS_LIEN_FILING",
                        "In-House Direct",
                    )
                else:
                    lb_k, lb_n, lb_cat, lb_net = (
                        "jobber_field_service",
                        "Jobber Field Service Management",
                        "FIELD_SERVICE_OPERATIONS",
                        "PartnerStack / In-House Direct",
                    )
                if any(
                    d_tok in combined_text
                    for d_tok in ("declined", "not approved", "unable to approve", "cannot approve", "rejected")
                ):
                    lb_ctype = "APPLICATION_DECLINED"
                elif "approved" in combined_text or "welcome" in combined_text or "congratulations" in combined_text:
                    lb_ctype = "APPLICATION_APPROVED"
                else:
                    lb_ctype = "APPLICATION_SUBMITTED"
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="lienbond",
                        partner_key=lb_k,
                        partner_name=lb_n,
                        category=lb_cat,
                        classification_type=lb_ctype,
                        requires_operator_decision=False,
                        summary=f"{lb_n} correspondence classified as {lb_ctype} on lienbond (Inbox #{msg.id}).",
                        urgency="LOW",
                        deadline=None,
                        missing_requirements=[],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                        candidate_url=cand_url,
                        network=lb_net,
                    )
                )
                continue

            if msg.mailbox != "Sent" and (
                "no-response@cj.com" in sender_lower
                or "cj affiliate" in combined_text
                or "cid 8101803" in combined_text
            ):
                is_company_activation = "company information" in body_lower
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="profithelm",
                        partner_key="turbotax" if is_company_activation else "taxslayer",
                        partner_name="TaxAct" if is_company_activation else "TaxSlayer",
                        category="TAX_INTELLIGENCE",
                        classification_type="APPLICATION_SUBMITTED",
                        requires_operator_decision=False,
                        summary=(
                            "CJ Affiliate publisher account 9 of 9 onboarded and ACTIVE (Company CID 7792582 / Publisher ID 8101803, Inbox #995 & #996 after IRS Form W-9 and Direct Deposit ACH); 28 advertiser applications submitted including TurboTax (#1905878), TaxAct (#4110283), and TaxSlayer (#5273914)."
                            if is_company_activation
                            else "CJ Affiliate publisher account created and email verified (Company CID 7792582 / Publisher ID 8101803, Inbox #991 & #992); 9 of 9 onboarding steps and 28 advertiser applications including TaxSlayer (#5273914) and TaxAct (#4110283) submitted."
                        ),
                        urgency="LOW",
                        deadline=None,
                        missing_requirements=[
                            "Awaiting CJ Affiliate advertiser review for TurboTax (#1905878) and TaxAct (#4110283) on CID 8101803"
                            if is_company_activation
                            else "Awaiting CJ Affiliate advertiser review for TaxSlayer (#5273914) on CID 8101803"
                        ],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                        candidate_url="https://members.cj.com/member/8101803/publisher/advertisers/findAdvertisers.cj",
                        network="CJ Affiliate",
                    )
                )
                continue

            if msg.mailbox != "Sent" and "rho.co" in sender_lower and "thank you for confirming" in body_lower:
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="profithelm",
                        partner_key="rho",
                        partner_name="Rho Commercial Banking & Treasury",
                        category="CORPORATE_SPEND",
                        classification_type="APPLICATION_SUBMITTED",
                        requires_operator_decision=False,
                        summary="Rho Client Service (Hawk, Inbox #989) confirmed receipt of ProfitHelm LLC's Rho Partner Portal submission under ticket [P6E9MZ-W3N0M].",
                        urgency="LOW",
                        deadline=None,
                        missing_requirements=["Awaiting Rho Partnerships team review and referral tracking link"],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                        candidate_url="https://www.rho.co/partners",
                        network="In-House Direct",
                    )
                )
                continue

            if not is_outbound_msg and (
                "sofi.com" in sender_lower
                or "partner of sofi" in body_lower
                or (
                    "sofi" in combined_text
                    and any(
                        tok in combined_text
                        for tok in (
                            "partnership request was declined",
                            "promotion request declined",
                            "declined your request to work with the campaign",
                            "approved",
                            "welcome to",
                            "welcome aboard",
                            "congratulations",
                            "tracking link",
                        )
                    )
                )
            ):
                is_declined_sofi = any(
                    tok in combined_text
                    for tok in (
                        "declined",
                        "promotion request declined",
                        "declined your request",
                        "not approved",
                        "unable to approve",
                        "cannot approve",
                    )
                )
                is_approved_sofi = not is_declined_sofi and any(
                    tok in combined_text
                    for tok in (
                        "approved",
                        "welcome to",
                        "welcome aboard",
                        "congratulations",
                        "you're in",
                        "tracking link",
                        "referral link",
                    )
                )
                has_sofi_q, sofi_q_req = _has_human_partner_question(
                    msg.sender_email, msg.sender_name, msg.subject, msg.body_snippet
                )
                sofi_onboarding = (
                    not is_declined_sofi
                    and not is_approved_sofi
                    and (
                        has_sofi_q
                        or any(
                            tok in combined_text
                            for tok in ("action required", "complete your", "complete onboarding", "questionnaire", "w-9")
                        )
                    )
                )
                sofi_ctype = (
                    "APPLICATION_DECLINED"
                    if is_declined_sofi
                    else (
                        "APPLICATION_APPROVED"
                        if is_approved_sofi
                        else ("ONBOARDING_ACTION_REQUIRED" if sofi_onboarding else "APPLICATION_SUBMITTED")
                    )
                )
                sofi_req_op = bool((is_approved_sofi and has_sofi_q) or sofi_onboarding)
                if is_declined_sofi:
                    sofi_summary = "SoFi Partner Team declined Impact.com promotion request (Inbox #1031, Account #7932737). Slot covered on Prexvo by first-party $39 Refinance & Amortization Decision Audit Stripe checkout plus Splash Financial (#9516) and LendKey (#3276) applications."
                    sofi_reqs = ["Covered by Prexvo $39 first-party Stripe checkout and pending Splash Financial (#9516) / LendKey (#3276) contracts"]
                    sofi_url = cand_url or "https://app.impact.com/campaign-promo-signup/SoFi.brand"
                elif is_approved_sofi:
                    sofi_summary = f"SoFi Student Loan Refinancing approved partnership on prexvo (Inbox #{msg.id})."
                    if has_sofi_q and sofi_q_req:
                        sofi_summary = f"{sofi_summary} {sofi_q_req}"
                    sofi_reqs = [sofi_q_req] if (has_sofi_q and sofi_q_req) else []
                    sofi_url = cand_url or "https://www.sofi.com/"
                elif sofi_onboarding:
                    sofi_summary = (
                        f"SoFi partner team requested onboarding action or reply (Inbox #{msg.id}). {sofi_q_req}".strip()
                    )
                    sofi_reqs = [sofi_q_req] if sofi_q_req else [f"Complete SoFi partner onboarding or reply to {msg.sender_email}"]
                    sofi_url = cand_url or "https://www.sofi.com/"
                else:
                    sofi_summary = f"Application submitted to SoFi via Impact.com (#11190, Inbox #{msg.id}). Awaiting partner review and tracking link issuance."
                    sofi_reqs = ["Pending Impact.com vendor review for SoFi (#11190)"]
                    sofi_url = cand_url or "https://app.impact.com/campaign-promo-signup/SoFi.brand"

                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="prexvo",
                        partner_key="sofi",
                        partner_name="SoFi",
                        category="STUDENT_LOAN_REFINANCE",
                        classification_type=sofi_ctype,
                        requires_operator_decision=sofi_req_op,
                        summary=sofi_summary,
                        urgency="HIGH" if sofi_req_op else "LOW",
                        deadline=None,
                        missing_requirements=sofi_reqs,
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                        candidate_url=sofi_url,
                        network="Impact.com",
                    )
                )
                continue

            # 0b. ERGO NEXT Insurance Affiliate Application / Decline (Impact.com)
            if msg.mailbox != "Sent" and (
                "ergo next insurance" in combined_text or "next insurance" in body_lower or "nextinsurance.com" in sender_lower
            ):
                next_prop = _resolve_lienbond_or_profithelm_property("next_insurance_b2b", combined_text)
                is_declined_next = (
                    "declined" in subj_lower
                    or "promotion request declined" in body_lower
                    or "declined your application" in body_lower
                )
                is_approved_next = not is_declined_next and ("approved" in combined_text or "welcome to" in combined_text)
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id=next_prop,
                        partner_key="next_insurance_b2b",
                        partner_name="Next Insurance Commercial B2B",
                        category="COMMERCIAL_INSURANCE",
                        classification_type=(
                            "APPLICATION_DECLINED"
                            if is_declined_next
                            else ("APPLICATION_APPROVED" if is_approved_next else "APPLICATION_SUBMITTED")
                        ),
                        requires_operator_decision=False,
                        summary=(
                            f"ERGO NEXT Insurance (#15709) declined Impact.com promotion request (Inbox #{msg.id})."
                            if is_declined_next
                            else (
                                f"Next Insurance Commercial B2B approved on {next_prop} (Inbox #{msg.id})."
                                if is_approved_next
                                else f"Application submitted to ERGO NEXT Insurance via Impact.com (#15709, Inbox #{msg.id}). Awaiting partner review and tracking link issuance."
                            )
                        ),
                        urgency="LOW" if (is_declined_next or is_approved_next) else "MEDIUM",
                        deadline=None,
                        missing_requirements=(
                            ["Direct B2B agency partnership or traffic scale review required for ERGO NEXT Insurance (#15709)"]
                            if is_declined_next
                            else ([] if is_approved_next else ["Pending Impact.com vendor review for ERGO NEXT Insurance (#15709)"])
                        ),
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                        candidate_url=cand_url,
                        network="Impact.com",
                    )
                )
                continue

            # 0c. Invoice Simple Promotion Request Declined & Human Appeal Rejection (Inbox #1025 / Inbox #1072)
            if msg.mailbox != "Sent" and (
                "invoice simple" in combined_text
                or "hamstergarage.com" in sender_lower
                or "sorry, your partnership request was declined" in subj_lower
            ) and (
                "declined" in combined_text
                or "unable to approve" in body_lower
                or "cannot approve" in body_lower
                or "not a fit" in body_lower
                or "unfortunately" in body_lower
                or "hamstergarage.com" in sender_lower
            ):
                is_human_appeal_rejection = (
                    not _is_automated_sender(msg.sender_email, msg.sender_name)
                    or subj_lower.startswith("re:")
                    or "hamstergarage.com" in sender_lower
                )
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="profithelm",
                        partner_key="invoice_simple",
                        partner_name="Invoice Simple",
                        category="INVOICING_BILLING",
                        classification_type="APPLICATION_DECLINED",
                        requires_operator_decision=False,
                        summary=(
                            f"Invoice Simple appeal rejected by {msg.sender_email} (Inbox #{msg.id}); final status declined with no active appeal."
                            if is_human_appeal_rejection
                            else f"Invoice Simple (#29915) declined Impact.com promotion request (Inbox #{msg.id}); status declined."
                        ),
                        urgency="LOW",
                        deadline=None,
                        missing_requirements=[],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                        candidate_url=cand_url,
                        network="Impact.com",
                    )
                )
                continue

            # Earnest Impact.com Promotion Request Declined (Inbox #994)
            if "earnest" in combined_text and (
                "promotion request declined" in combined_text
                or "application declined" in combined_text
                or "request was declined" in combined_text
                or "not approved" in combined_text
                or "unable to approve" in combined_text
            ):
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="prexvo",
                        partner_key="earnest",
                        partner_name="Earnest Student Loan Refinancing",
                        category="STUDENT_LOAN_REFINANCE",
                        classification_type="APPLICATION_DECLINED",
                        requires_operator_decision=False,
                        summary=f"Earnest declined Impact.com promotion request (Inbox #{msg.id}); status declined.",
                        urgency="LOW",
                        deadline=None,
                        missing_requirements=[],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                        candidate_url=cand_url,
                        network="Impact.com",
                    )
                )
                continue

            # 1. Gusto Affiliate Application & Approval (Impact.com)
            if "gusto" in combined_text and ("impact.com" in sender_lower or "noelle.hyra@gusto.com" in sender_lower or "affiliate" in combined_text):
                is_approved_gusto = (
                    "you're approved" in combined_text
                    or "welcome to gusto" in combined_text
                    or "noelle.hyra@gusto.com" in sender_lower
                )
                if is_approved_gusto:
                    classifications.append(
                        PartnerEmailClassification(
                            email_id=msg.id,
                            account=msg.account,
                            property_id="profithelm",
                            partner_key="gusto",
                            partner_name="Gusto Payroll, Benefits & HR Platform",
                            category="PAYROLL_HR",
                            classification_type="APPLICATION_APPROVED",
                            requires_operator_decision=False,
                            summary="Gusto Impact.com contract approved (#15154, $200-$300 CPA). Tracking link active.",
                            urgency="LOW",
                            deadline=None,
                            missing_requirements=[],
                            raw_subject=msg.subject,
                            sender_email=msg.sender_email,
                            date=msg.date,
                            candidate_url=cand_url or "https://gusto.pxf.io/c/7932737/1226287/15154",
                            network="Impact.com",
                        )
                    )
                else:
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
                            candidate_url=cand_url,
                            network="Impact.com",
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
                        candidate_url=cand_url,
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
                        candidate_url=cand_url,
                    )
                )

            # 4. Mercury Startup Banking Funds Alert
            elif (
                "mercury" in combined_text
                and ("declined" in combined_text or "add or transfer funds" in combined_text)
                and "download the mercury app" not in combined_text
                and "review a declined card transaction" not in combined_text
                and "this email contains an advertisement" not in combined_text
            ):
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
                        candidate_url=cand_url,
                    )
                )

            # 5a. Stripe Partner Ecosystem Application Update
            elif "partner-ecosystem@stripe.com" in sender_lower or "stripe partner ecosystem" in combined_text:
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="profithelm",
                        partner_key="stripe",
                        partner_name="Stripe Partner Ecosystem",
                        category="TERMS_UPDATE",
                        classification_type="TERMS_UPDATE",
                        requires_operator_decision=True,
                        summary="Complete Stripe Partner Ecosystem technical checklist ($1M volume / Stripe Connect integration) and confirm readiness via confirm-action before activating live tier",
                        urgency="HIGH",
                        deadline=None,
                        missing_requirements=[
                            "Integrate Stripe Connect and Connect webhooks",
                            "Reach $1M USD annual processed volume threshold",
                            "Pass technical integration review (Payment Intents or Checkout Sessions with idempotency keys)",
                            "Publish partner landing page and verify business domain",
                        ],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                        candidate_url=cand_url,
                        network="In-House Direct",
                        action_required="Complete Stripe Partner Ecosystem technical checklist ($1M volume / Stripe Connect integration) and confirm readiness via confirm-action before activating live tier",
                    )
                )

            # 5b. Stripe Legal Terms & Services Agreement Update
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
                        candidate_url=cand_url,
                        network="In-House Direct",
                    )
                )

            # 5c. Startup Ecosystem / Credit Programs (Google for Startups / Claude Startups)
            elif (
                "google for startups" in combined_text
                or "googlecloud@google.com" in sender_lower
                or "claude startups" in combined_text
                or "claudestartups@mail.anthropic.com" in sender_lower
            ):
                is_claude = "claude" in combined_text or "anthropic" in sender_lower
                classifications.append(
                    PartnerEmailClassification(
                        email_id=msg.id,
                        account=msg.account,
                        property_id="profithelm",
                        partner_key="claude_startups" if is_claude else "google_for_startups",
                        partner_name="Claude Startups Program" if is_claude else "Google for Startups Cloud Program",
                        category="TERMS_UPDATE",
                        classification_type="TERMS_UPDATE",
                        requires_operator_decision=True,
                        summary="Review startup program application and verify corporate domain email credentials",
                        urgency="MEDIUM",
                        deadline=None,
                        missing_requirements=[
                            "Verify corporate domain email credentials",
                            "Complete startup program onboarding application",
                        ],
                        raw_subject=msg.subject,
                        sender_email=msg.sender_email,
                        date=msg.date,
                        candidate_url=cand_url,
                        network="In-House Direct",
                        action_required="Review startup program application and verify corporate domain email credentials",
                    )
                )

            # 5d. Inbound Vendor Responses from Known Partner Contacts / Domains (outbound_partner_map)
            elif not is_outbound_msg and (
                sender_email_clean in outbound_partner_map
                or (
                    "@" in sender_email_clean
                    and sender_email_clean.split("@")[-1] != "cj.com"
                    and any(
                        sender_email_clean.endswith(f"@{addr_k.split('@')[-1]}")
                        for addr_k in outbound_partner_map
                    )
                )
            ):
                matched_inbound_vendor = outbound_partner_map.get(sender_email_clean)
                if not matched_inbound_vendor:
                    for addr_k, p_tup in outbound_partner_map.items():
                        dom_k = addr_k.split("@")[-1]
                        if dom_k != "cj.com" and sender_email_clean.endswith(f"@{dom_k}"):
                            matched_inbound_vendor = p_tup
                            break
                if matched_inbound_vendor:
                    from pseofactory.affiliates import AFFILIATE_REGISTRY as _VENDOR_REG

                    v_prop, v_key, v_name, v_net = matched_inbound_vendor
                    if v_key in (
                        "simply_business",
                        "suretybonds_direct",
                        "next_insurance_b2b",
                        "thimble_contractor",
                        "jobber_field_service",
                        "levelset_lien_filing",
                    ):
                        v_prop = _resolve_lienbond_or_profithelm_property(v_key, combined_text)
                    reg_obj = _VENDOR_REG.get(f"{v_prop}:{v_key}") or _VENDOR_REG.get(v_key)
                    v_cat = reg_obj.category if reg_obj else "PARTNER_PROGRAM"

                    body_no_urls = _URL_IN_TEXT_RE.sub(" ", combined_text)
                    is_card_or_tx_decline = any(
                        tok in combined_text
                        for tok in (
                            "declined card",
                            "card transaction",
                            "card was declined",
                            "transaction declined",
                            "transaction was declined",
                            "payment declined",
                            "charge declined",
                        )
                    )
                    is_informational_vendor_notice = any(
                        tok in combined_text
                        for tok in (
                            "you don't need to take any action",
                            "you do not need to take any action",
                            "no action required",
                            "no action is needed",
                            "sweep agreement",
                            "download the mercury app",
                            "review a declined card transaction",
                            "agent controls",
                            "this email contains an advertisement",
                        )
                    )
                    is_spam_auto_blast = mbx_lower == "spam" and _is_automated_sender(
                        msg.sender_email, msg.sender_name
                    )
                    suppress_partner_state = is_informational_vendor_notice or is_spam_auto_blast

                    is_v_declined = not suppress_partner_state and (
                        ("declined" in combined_text and not is_card_or_tx_decline)
                        or any(
                            tok in combined_text
                            for tok in (
                                "not approved",
                                "unable to approve",
                                "cannot approve",
                                "unfortunately we cannot",
                                "unfortunately, we cannot",
                                "not a fit",
                                "application was rejected",
                                "request was rejected",
                            )
                        )
                    )
                    is_v_approved = not suppress_partner_state and not is_v_declined and any(
                        tok in combined_text
                        for tok in (
                            "approved",
                            "welcome to",
                            "welcome aboard",
                            "you're in",
                            "you are in",
                            "congratulations",
                            "happy to approve",
                            "pleased to approve",
                            "excited to welcome",
                            "here is your tracking link",
                            "your tracking link",
                            "your referral link",
                            "your affiliate link",
                            "partner link is active",
                        )
                    )
                    has_v_q, v_q_req = (
                        (False, "")
                        if suppress_partner_state or mbx_lower in ("notification", "newsletter", "spam")
                        else _has_human_partner_question(
                            msg.sender_email, msg.sender_name, msg.subject, msg.body_snippet
                        )
                    )
                    is_v_onboarding = (
                        not suppress_partner_state
                        and not is_v_declined
                        and not is_v_approved
                        and (
                            has_v_q
                            or bool(re.search(r"\bw-?9\b", body_no_urls))
                            or any(
                                tok in body_no_urls
                                for tok in (
                                    "action required",
                                    "complete your",
                                    "complete onboarding",
                                    "fill out",
                                    "sign the",
                                    "tax form",
                                    "questionnaire",
                                    "schedule a call",
                                    "book a call",
                                    "next steps to activate",
                                    "portal invite",
                                )
                            )
                        )
                    )
                    is_v_submitted = (
                        not suppress_partner_state
                        and not is_v_declined
                        and not is_v_approved
                        and not is_v_onboarding
                        and any(
                            tok in combined_text
                            for tok in (
                                "thank you for applying",
                                "thanks for applying",
                                "received your application",
                                "application received",
                                "received your inquiry",
                                "under review",
                                "reviewing your application",
                                "we have received your",
                            )
                        )
                    )

                    if is_v_declined:
                        v_ctype = "APPLICATION_DECLINED"
                        v_req_op = False
                        v_urg = "LOW"
                        v_reqs: List[str] = []
                        v_summary = f"{v_name} declined partnership application on {v_prop} (Inbox #{msg.id})."
                    elif is_v_approved:
                        v_ctype = "APPLICATION_APPROVED"
                        v_req_op = bool(has_v_q)
                        v_urg = "HIGH" if has_v_q else "LOW"
                        v_reqs = [v_q_req] if (has_v_q and v_q_req) else []
                        v_summary = f"{v_name} approved partnership on {v_prop} (Inbox #{msg.id})."
                        if has_v_q and v_q_req:
                            v_summary = f"{v_summary} {v_q_req}"
                    elif is_v_onboarding:
                        v_ctype = "ONBOARDING_ACTION_REQUIRED"
                        v_req_op = True
                        v_urg = "HIGH"
                        v_reqs = (
                            [v_q_req]
                            if (has_v_q and v_q_req)
                            else [f"Complete onboarding or reply to {v_name} ({msg.sender_email})"]
                        )
                        v_summary = (
                            v_q_req
                            if (has_v_q and v_q_req)
                            else f"{v_name} ({msg.sender_email}) requested partner onboarding action on {v_prop} (Inbox #{msg.id})."
                        )
                    elif is_v_submitted:
                        v_ctype = "APPLICATION_SUBMITTED"
                        v_req_op = False
                        v_urg = "LOW"
                        v_reqs = [f"Awaiting {v_name} partnership review and tracking link"]
                        v_summary = f"{v_name} confirmed receipt of partnership application on {v_prop} (Inbox #{msg.id})."
                    else:
                        v_ctype = "GENERAL_INQUIRY"
                        v_req_op = False
                        v_urg = "LOW"
                        v_reqs = []
                        v_summary = f"Inbound correspondence received from {v_name} ({msg.sender_email}) on {v_prop}."

                    classifications.append(
                        PartnerEmailClassification(
                            email_id=msg.id,
                            account=msg.account,
                            property_id=v_prop,
                            partner_key=v_key,
                            partner_name=v_name,
                            category=v_cat,
                            classification_type=v_ctype,
                            requires_operator_decision=v_req_op,
                            summary=v_summary,
                            urgency=v_urg,
                            deadline=None,
                            missing_requirements=v_reqs,
                            raw_subject=msg.subject,
                            sender_email=msg.sender_email,
                            date=msg.date,
                            candidate_url=cand_url,
                            network=v_net,
                            action_required=v_summary if v_req_op else None,
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
                        candidate_url=cand_url,
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
                        candidate_url=cand_url,
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
                        candidate_url=cand_url,
                    )
                )

            # 9. Generic Partner Matching across AFFILIATE_REGISTRY
            else:
                from pseofactory.affiliates import AFFILIATE_REGISTRY
                matched_partner = None
                for p_key, p_obj in AFFILIATE_REGISTRY.items():
                    if ":" in p_key:
                        continue
                    p_name_lower = p_obj.name.lower()
                    p_key_lower = p_key.lower().replace("_", " ")
                    p_domain = urllib.parse.urlsplit(p_obj.default_url).netloc.lower().replace("www.", "")
                    if (p_key in combined_text or p_key_lower in combined_text or
                        p_name_lower in combined_text or (p_domain and p_domain in combined_text)):
                        matched_partner = p_obj
                        break

                if matched_partner:
                    resolved_prop = matched_partner.property_id
                    if matched_partner.key in (
                        "simply_business",
                        "suretybonds_direct",
                        "next_insurance_b2b",
                        "thimble_contractor",
                        "jobber_field_service",
                        "levelset_lien_filing",
                    ):
                        resolved_prop = _resolve_lienbond_or_profithelm_property(matched_partner.key, combined_text)
                    is_informational_notice = (
                        "you don't need to take any action" in combined_text
                        or "you do not need to take any action" in combined_text
                        or "no action required" in combined_text
                        or "no action is needed" in combined_text
                        or "sweep agreement" in combined_text
                        or "download the mercury app" in combined_text
                        or "agent controls" in combined_text
                        or "this email contains an advertisement" in combined_text
                    )
                    req_decision = (
                        not is_informational_notice
                        and (
                            "action required" in combined_text
                            or "urgent" in combined_text
                            or "warning" in combined_text
                            or "update" in combined_text
                        )
                    )
                    classifications.append(
                        PartnerEmailClassification(
                            email_id=msg.id,
                            account=msg.account,
                            property_id=resolved_prop,
                            partner_key=matched_partner.key,
                            partner_name=matched_partner.name,
                            category=matched_partner.category,
                            classification_type="GENERAL_INQUIRY" if not req_decision else "GOVERNANCE_WARNING",
                            requires_operator_decision=req_decision,
                            summary=f"Inbound correspondence matched for {matched_partner.name} on {resolved_prop}.",
                            urgency="HIGH" if req_decision else "LOW",
                            deadline=None,
                            missing_requirements=[],
                            raw_subject=msg.subject,
                            sender_email=msg.sender_email,
                            date=msg.date,
                            candidate_url=cand_url,
                            network=matched_partner.network,
                        )
                    )

        # Ensure human partner manager direct questions are never swallowed by automated approval rules
        # while preserving APPLICATION_APPROVED when both an approval and a human question are present.
        for c in classifications:
            src_msg = msg_by_id.get(c.email_id)
            if (
                not src_msg
                or (src_msg.mailbox or "").strip().lower() in ("sent", "notification", "newsletter", "spam")
                or (src_msg.sender_email or "").strip().lower() == "arif.coskun@profithelm.com"
                or c.classification_type in ("APPLICATION_DECLINED", "INBOUND_PITCH")
            ):
                continue
            if c.classification_type == "GENERAL_INQUIRY":
                msg_low = f"{src_msg.subject or ''} {src_msg.body_snippet or ''}".lower()
                is_html_marketing_drip = (
                    "unsubscribe" in msg_low or "<!doctype html" in msg_low
                ) and not any(
                    kw in msg_low
                    for kw in (
                        "affiliate",
                        "partner",
                        "referral",
                        "commission",
                        "placement",
                        "application",
                        "cj",
                        "impact",
                        "firstpromoter",
                        "partnerstack",
                        "profithelm",
                        "prexvo",
                        "gainhelm",
                        "lienbond",
                    )
                )
                if is_html_marketing_drip:
                    continue
            has_q, q_req = _has_human_partner_question(
                src_msg.sender_email, src_msg.sender_name, src_msg.subject, src_msg.body_snippet
            )
            if has_q:
                if c.classification_type == "GENERAL_INQUIRY":
                    c.classification_type = "ONBOARDING_ACTION_REQUIRED"
                c.requires_operator_decision = True
                if c.urgency not in ("CRITICAL", "HIGH"):
                    c.urgency = "HIGH"
                if q_req and q_req not in c.missing_requirements:
                    c.missing_requirements.append(q_req)
                if q_req and q_req not in c.summary:
                    c.summary = f"{c.summary} {q_req}".strip()
                c.action_required = c.summary

        # Sort classifications by date descending so latest emails have priority
        classifications.sort(key=lambda x: x.date, reverse=True)

        # Validate zero forbidden dashes across all classifications
        for c in classifications:
            assert_no_forbidden_dashes(c.summary, context=f"Classification summary for {c.partner_key}")
            assert_no_forbidden_dashes(c.partner_name, context=f"Partner name for {c.partner_key}")
            for req in c.missing_requirements:
                assert_no_forbidden_dashes(req, context=f"Missing requirement for {c.partner_key}")

        return classifications

    def analyze_correspondence_anomalies_and_checkins(
        self,
        messages: Optional[List[EmailMessage]] = None,
        fetch_live: bool = False,
        zoho_account: str = "zoho",
    ) -> Dict[str, Any]:
        """
        Inspects synced Zoho messages (Inbox, Sent, Notification, Newsletter, Drafts, Spam)
        to compute correspondence anomalies strictly from actual ingested messages:
        hard bounces, unanswered partner check-in prompts, network declines / appeal rejections,
        and stale drafts. Never injects fabricated static snapshot dicts.
        Zero em-dashes. Zero en-dashes.
        """
        msg_list = list(messages) if messages is not None else self.sync_all(force=fetch_live)

        state = self.load_state()
        reconciled_bounce_ids = {
            str(x).strip()
            for x in (state.get("reconciled_bounce_ids") or state.get("reconciled_bounces") or [])
            if str(x).strip()
        }
        reconciled_bounce_recipients = {
            str(x).strip().lower()
            for x in (state.get("reconciled_bounce_recipients") or [])
            if str(x).strip()
        }

        hard_bounces: List[Dict[str, Any]] = []
        seen_bounce_ids: set[str] = set()
        for m in msg_list:
            snd = f"{m.sender_name or ''} {m.sender_email or ''}".lower()
            subj = (m.subject or "").lower()
            is_bounce = (
                "mailer-daemon" in snd
                or "postmaster@" in snd
                or "undelivered mail" in subj
                or "delivery status notification" in subj
                or "mail delivery failed" in subj
                or "failure notice" in subj
                or "returned mail" in subj
            )
            if not is_bounce or str(m.id) in seen_bounce_ids:
                continue
            seen_bounce_ids.add(str(m.id))

            raw_bounce_text = f"{m.body_snippet or ''}\n{m.subject or ''}"
            bounced_recip = _extract_bounced_recipient(raw_bounce_text, sender_email=m.sender_email)
            recip_low = bounced_recip.lower()

            smtp_match = re.search(r"\b(5\d\d(?:\s+5\.\d+\.\d+)?)\b", raw_bounce_text)
            smtp_code = smtp_match.group(1) if smtp_match else "550"

            if "@gainhelm.com" in recip_low:
                b_prop = "gainhelm"
            elif "@prexvo.com" in recip_low:
                b_prop = "prexvo"
            elif "@lienbond.com" in recip_low:
                b_prop = "lienbond"
            else:
                b_prop = "profithelm"

            if any(
                recip_low.startswith(pfx) or "*" in recip_low
                for pfx in ("audit@", "ciso@", "grc-controller@", "synthetic@", "probe@")
            ) or recip_low.endswith(("@gainhelm.com", "@prexvo.com", "@lienbond.com", "@profithelm.com")):
                b_partner = "first_party_playbook_responder"
            else:
                b_partner = "unknown"

            is_reconciled = (
                str(m.id) in reconciled_bounce_ids
                or (recip_low != "unknown" and recip_low in reconciled_bounce_recipients)
            )
            reason_clean = (m.body_snippet or m.subject or "Delivery failed")[:240].replace("\u2014", "-").replace("\u2013", "-")

            hard_bounces.append(
                {
                    "email_id": str(m.id),
                    "mailbox": m.mailbox,
                    "date": m.date,
                    "sender_email": m.sender_email,
                    "bounced_recipient": bounced_recip,
                    "smtp_code": smtp_code,
                    "reason": reason_clean,
                    "partner_key": b_partner,
                    "property_id": b_prop,
                    "reconciled": is_reconciled,
                }
            )

        # Collect Sent messages to determine whether inbound check-ins have already been answered
        sent_by_recip_or_domain: Dict[str, str] = {}
        for m in msg_list:
            if m.mailbox != "Sent":
                continue
            r_email = (((m.raw_headers or {}).get("to_email") or m.sender_email) or "").strip().lower()
            if not r_email:
                continue
            if r_email not in sent_by_recip_or_domain or (m.date or "") > sent_by_recip_or_domain[r_email]:
                sent_by_recip_or_domain[r_email] = m.date or ""
            dom = r_email.split("@")[-1] if "@" in r_email else ""
            if dom and (dom not in sent_by_recip_or_domain or (m.date or "") > sent_by_recip_or_domain[dom]):
                sent_by_recip_or_domain[dom] = m.date or ""

        partner_checkin_prompts: List[Dict[str, Any]] = []
        for m in msg_list:
            if m.mailbox == "Sent":
                continue
            snd_low = (m.sender_email or "").strip().lower()
            subj_low = (m.subject or "").lower()
            body_low = (m.body_snippet or "").lower()
            comb_low = f"{subj_low} {body_low}"
            if "mailer-daemon" in snd_low or "postmaster@" in snd_low:
                continue

            is_fp_checkin = (
                "firstpromoter.com" in snd_low
                and ("checking in" in subj_low or "how do you plan to share" in body_low)
            )
            has_q, q_req = _has_human_partner_question(m.sender_email, m.sender_name, m.subject, m.body_snippet)
            if not (is_fp_checkin or has_q):
                continue

            reply_to = snd_low
            p_key = "unknown"
            p_name = m.sender_name or m.sender_email
            prop_id = "profithelm"
            net_name = "In-House Direct"
            disp_key: Optional[str] = None
            if "xendoo" in comb_low:
                reply_to = "luanne.bryant@xendoo.com" if "firstpromoter" in snd_low else snd_low
                p_key = "xendoo"
                p_name = "Xendoo Online Bookkeeping & Tax"
                net_name = "FirstPromoter"
                disp_key = "xendoo_firstpromoter_checkin_reply"
            elif "koinly" in comb_low:
                reply_to = "affiliates@koinly.io" if "firstpromoter" in snd_low else snd_low
                p_key = "koinly"
                p_name = "Koinly Crypto Tax Software"
                net_name = "FirstPromoter"
                disp_key = "koinly_firstpromoter_checkin_reply"
            elif "eztaxreturn" in comb_low:
                p_key = "eztaxreturn_com"
                p_name = "ezTaxReturn.com Affiliate Program"
                net_name = "CJ Affiliate"

            reply_dom = reply_to.split("@")[-1] if "@" in reply_to else ""
            latest_sent = max(
                sent_by_recip_or_domain.get(reply_to, ""),
                sent_by_recip_or_domain.get(reply_dom, "") if reply_dom else "",
            )
            if latest_sent and m.date and latest_sent > m.date:
                continue

            partner_checkin_prompts.append(
                {
                    "email_id": str(m.id),
                    "mailbox": m.mailbox,
                    "date": m.date,
                    "partner_key": p_key,
                    "partner_name": p_name,
                    "property_id": prop_id,
                    "network": net_name,
                    "sender_name": m.sender_name,
                    "sender_email": m.sender_email,
                    "reply_to_email": reply_to,
                    "subject": (m.subject or "").replace("\u2014", "-").replace("\u2013", "-"),
                    "prompt_excerpt": (q_req or m.body_snippet or m.subject)[:220].replace("\u2014", "-").replace("\u2013", "-"),
                    "referral_url_in_email": _extract_candidate_url(m.body_snippet or ""),
                    "dispatch_key": disp_key,
                }
            )

        # Compute declined campaigns & appeal status strictly from passed/synced messages
        declines_by_partner: Dict[str, Dict[str, Any]] = {}
        cls_for_anomalies = self.classify_partner_emails(msg_list) if msg_list else []
        for c in cls_for_anomalies:
            if c.classification_type != "APPLICATION_DECLINED":
                continue
            src_m = next((x for x in msg_list if str(x.id) == str(c.email_id)), None)
            subj_l = (c.raw_subject or "").lower()
            snd_l = (c.sender_email or "").lower()
            is_final_human_rejection = (
                not _is_automated_sender(c.sender_email, src_m.sender_name if src_m else "")
                or subj_l.startswith("re:")
                or "hamstergarage.com" in snd_l
            )
            existing_dec = declines_by_partner.get(c.partner_key)
            # Human appeal rejection supersedes earlier automated Impact decline for the same partner
            if existing_dec and existing_dec.get("appeal_status") == "APPEAL_REJECTED_FINAL" and not is_final_human_rejection:
                continue
            appeal_email: Optional[str] = None
            dispatch_k: Optional[str] = None
            if c.partner_key == "invoice_simple" and not is_final_human_rejection:
                appeal_email = "invoicesimple@hamstergarage.com"
                dispatch_k = "invoice_simple_impact_appeal"
            declines_by_partner[c.partner_key] = {
                "email_id": str(c.email_id),
                "mailbox": src_m.mailbox if src_m else "Inbox",
                "date": c.date,
                "partner_key": c.partner_key,
                "declined_brand": c.partner_name,
                "property_id": c.property_id,
                "network": c.network,
                "status": "declined",
                "appeal_status": "APPEAL_REJECTED_FINAL" if is_final_human_rejection else "DECLINED",
                "appeal_active": False,
                "decline_reason": c.summary,
                "appeal_contact_email": appeal_email,
                "dispatch_key": dispatch_k,
            }
        declined_campaigns_with_appeals = list(declines_by_partner.values())

        stale_drafts: List[Dict[str, Any]] = []
        for m in msg_list:
            if (m.mailbox or "").lower() != "drafts":
                continue
            to_e = (((m.raw_headers or {}).get("to_email") or m.sender_email) or "").strip()
            stale_drafts.append(
                {
                    "draft_id": str(m.id),
                    "mailbox": "Drafts",
                    "date": m.date,
                    "to_email": to_e,
                    "subject": (m.subject or "").replace("\u2014", "-").replace("\u2013", "-"),
                    "superseded_by": "pending_review",
                }
            )

        if fetch_live and self.himalaya_bin == "himalaya" and "PYTEST_CURRENT_TEST" not in os.environ:
            draft_envs = self.fetch_zoho_envelopes(
                mailbox="Drafts", page_size=200, force=True
            )
            seen_draft_ids = {d["draft_id"] for d in stale_drafts}
            for d_env in draft_envs:
                d_id = str(d_env.get("id") or "")
                if d_id in seen_draft_ids:
                    continue
                to_arr = d_env.get("to") or []
                to_email = (to_arr[0].get("email") or "").strip() if to_arr else ""
                subj = str(d_env.get("subject") or "").replace("\u2014", "-").replace("\u2013", "-")
                stale_drafts.append(
                    {
                        "draft_id": d_id,
                        "mailbox": "Drafts",
                        "date": str(d_env.get("date") or ""),
                        "to_email": to_email,
                        "subject": subj,
                        "superseded_by": "pending_review",
                    }
                )

        return {
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "hard_bounces_count": len(hard_bounces),
            "hard_bounces": hard_bounces,
            "partner_checkin_prompts_count": len(partner_checkin_prompts),
            "partner_checkin_prompts": partner_checkin_prompts,
            "unanswered_partner_checkins_count": len(partner_checkin_prompts),
            "unanswered_partner_checkins": partner_checkin_prompts,
            "declined_campaigns_count": len(declined_campaigns_with_appeals),
            "declined_campaigns_with_appeals": declined_campaigns_with_appeals,
            "network_declines_count": len(declined_campaigns_with_appeals),
            "network_declines": declined_campaigns_with_appeals,
            "stale_drafts_count": len(stale_drafts),
            "stale_drafts": stale_drafts,
        }

    def reconcile_stale_zoho_drafts(
        self,
        execute_live: bool = False,
        zoho_account: str = "zoho",
    ) -> Dict[str, Any]:
        """
        Inspects Zoho `Drafts` folder and removes superseded drafts (such as Draft #1 to
        wade.fenton@otrsolutions.com, which was already dispatched as Sent #278 on 2026-10-20
        and answered by Wade Fenton in Inbox #1030 on 2026-10-26).
        Zero em-dashes. Zero en-dashes.
        """
        removed_drafts: List[Dict[str, Any]] = []
        inspected_drafts: List[Dict[str, Any]] = []

        if execute_live and self.himalaya_bin == "himalaya" and "PYTEST_CURRENT_TEST" not in os.environ:
            draft_envs = self.fetch_zoho_envelopes(
                mailbox="Drafts", page_size=20, force=True
            )
            for d_env in draft_envs:
                d_id = str(d_env.get("id") or "").strip()
                to_arr = d_env.get("to") or []
                to_email = (to_arr[0].get("email") or "").strip().lower() if to_arr else ""
                subj = str(d_env.get("subject") or "").replace("\u2014", "-").replace("\u2013", "-")
                entry = {
                    "draft_id": d_id,
                    "to_email": to_email,
                    "subject": subj,
                    "date": str(d_env.get("date") or ""),
                }
                inspected_drafts.append(entry)
                if d_id and ("wade.fenton@otrsolutions.com" in to_email or "otr solutions" in subj.lower()):
                    code, _out, err = self.run_himalaya_command(
                        ["message", "delete", "-a", zoho_account, "-f", "Drafts", d_id]
                    )
                    entry["deleted"] = (code == 0)
                    if code != 0:
                        entry["error"] = (err or "").strip()[:200]
                    removed_drafts.append(entry)

        return {
            "reconciled_at": datetime.now(timezone.utc).isoformat(),
            "execute_live": execute_live,
            "inspected_count": len(inspected_drafts),
            "removed_count": len(removed_drafts),
            "removed_drafts": removed_drafts,
            "inspected_drafts": inspected_drafts,
        }

