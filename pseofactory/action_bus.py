"""
pseofactory Dedicated Human Action Bus
Routes partner correspondence and integration requirements requiring operator intervention.
Enforces standing constraints:
1. Never auto-approve partner agreements without operator confirmation.
2. Strictly forbid cross-property partner mixing.
3. Reject em-dashes and en-dashes across all action records, titles, and operator notes.

Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import json
import os
import re
import fcntl
import tempfile
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from pseofactory.contracts import assert_no_forbidden_dashes
from pseofactory.affiliates import (
    B2B_PARTNER_KEYS,
    STUDENT_LOAN_PARTNER_KEYS,
    PROFITHELM_AFFILIATES,
    PREXVO_AFFILIATES,
)
from pseofactory.email_ingest import PartnerEmailClassification


@dataclass
class ActionItem:
    """Represents a discrete item requiring human operator intervention."""
    action_id: str
    property_id: str
    partner_key: str
    partner_name: str
    title: str
    description: str
    action_type: str  # GOVERNANCE_DEADLINE, BANKING_ALERT, PARTNER_APPROVAL, TERMS_UPDATE, INTEGRATION_REQUIREMENT
    severity: str     # CRITICAL, HIGH, MEDIUM, LOW
    status: str       # PENDING_OPERATOR, APPROVED, REJECTED, RESOLVED
    requires_operator_confirmation: bool = True
    deadline: Optional[str] = None
    missing_requirements: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    operator_notes: str = ""
    source_email_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HumanActionBus:
    """
    Dedicated action bus orchestrating operator decisions on partner agreements,
    compliance warnings, and integration readiness gaps.
    """

    def __init__(self, bus_path: Optional[str] = None):
        self.bus_path = bus_path or os.path.join(
            os.path.dirname(__file__), "..", ".agy", "human_action_bus.json"
        )
        self._ensure_dir()
        self.items: Dict[str, ActionItem] = self._load()

    def _ensure_dir(self) -> None:
        dir_name = os.path.dirname(os.path.abspath(self.bus_path))
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

    def _load(self) -> Dict[str, ActionItem]:
        if os.path.isfile(self.bus_path):
            try:
                with open(self.bus_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                items_dict = {}
                for k, v in data.get("actions", {}).items():
                    item = ActionItem(**v)
                    self._assert_item_invariants(item)
                    items_dict[k] = item
                return items_dict
            except Exception:
                pass
        return {}

    def save(self) -> None:
        """Persists action bus atomically with zero-dash and boundary checks."""
        data = {
            "bus_metadata": {
                "version": "1.0.0",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "total_items": len(self.items),
                "pending_operator_count": sum(1 for it in self.items.values() if it.status == "PENDING_OPERATOR"),
            },
            "actions": {k: it.to_dict() for k, it in self.items.items()},
        }

        # Validate all items
        for it in self.items.values():
            self._assert_item_invariants(it)

        target_dir = os.path.dirname(os.path.abspath(self.bus_path))
        os.makedirs(target_dir, exist_ok=True)
        lock_path = f"{self.bus_path}.lock"
        with open(lock_path, "w", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                with tempfile.NamedTemporaryFile("w", dir=target_dir, delete=False, encoding="utf-8") as tf:
                    json.dump(data, tf, indent=2)
                    tf.flush()
                    os.fsync(tf.fileno())
                    tmp_name = tf.name
                os.replace(tmp_name, self.bus_path)
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _assert_item_invariants(self, item: ActionItem) -> None:
        """Enforces property boundary rules and typography anti-slop contracts."""
        assert_no_forbidden_dashes(item.title, context=f"Action item title {item.action_id}")
        assert_no_forbidden_dashes(item.description, context=f"Action item description {item.action_id}")
        assert_no_forbidden_dashes(item.partner_name, context=f"Action item partner name {item.action_id}")
        assert_no_forbidden_dashes(item.operator_notes, context=f"Action item operator notes {item.action_id}")
        for req in item.missing_requirements:
            assert_no_forbidden_dashes(req, context=f"Missing requirement {item.action_id}")

        prop_clean = (item.property_id or "").strip().lower()
        key_clean = (item.partner_key or "").strip().lower()

        # Strict Property Isolation
        if prop_clean == "prexvo":
            if key_clean in B2B_PARTNER_KEYS or key_clean in PROFITHELM_AFFILIATES:
                raise ValueError(
                    f"Strict isolation violation: B2B partner '{key_clean}' cannot be routed to Prexvo action bus."
                )
        elif prop_clean in ("profithelm", "exchange1031"):
            if key_clean in STUDENT_LOAN_PARTNER_KEYS or key_clean in PREXVO_AFFILIATES:
                raise ValueError(
                    f"Strict isolation violation: Student loan partner '{key_clean}' cannot be routed to ProfitHelm action bus."
                )

    def route_classification(
        self,
        c: PartnerEmailClassification,
    ) -> Optional[ActionItem]:
        """
        Routes an email classification onto the human action bus if operator intervention is required.
        Deduplicates by action_id.
        """
        if not c.requires_operator_decision:
            return None

        # Build stable action_id based on property, partner, and type
        safe_key = re.sub(r"[^a-z0-9]+", "-", c.partner_key.lower()).strip("-")
        safe_type = re.sub(r"[^a-z0-9]+", "-", c.classification_type.lower()).strip("-")
        action_id = f"act-{c.property_id}-{safe_key}-{safe_type}"

        # If already exists, don't revert if resolved, but update email id/date
        if action_id in self.items:
            existing = self.items[action_id]
            existing.updated_at = datetime.now(timezone.utc).isoformat()
            if c.deadline and not existing.deadline:
                existing.deadline = c.deadline
            return existing

        title = f"{c.partner_name}: {c.classification_type.replace('_', ' ').title()}"
        title = title.replace("\u2014", "-").replace("\u2013", "-")
        desc = c.summary.replace("\u2014", "-").replace("\u2013", "-")

        item = ActionItem(
            action_id=action_id,
            property_id=c.property_id,
            partner_key=c.partner_key,
            partner_name=c.partner_name,
            title=title,
            description=desc,
            action_type=c.classification_type,
            severity=c.urgency,
            status="PENDING_OPERATOR",
            requires_operator_confirmation=True,
            deadline=c.deadline,
            missing_requirements=list(c.missing_requirements),
            source_email_id=c.email_id,
        )

        self._assert_item_invariants(item)
        self.items[action_id] = item
        self.save()
        return item

    def route_manual_requirement(
        self,
        property_id: str,
        partner_key: str,
        partner_name: str,
        title: str,
        description: str,
        action_type: str = "INTEGRATION_REQUIREMENT",
        severity: str = "MEDIUM",
        deadline: Optional[str] = None,
        missing_requirements: Optional[List[str]] = None,
    ) -> ActionItem:
        """Creates or updates a manual operator requirement on the action bus."""
        title_clean = title.replace("\u2014", "-").replace("\u2013", "-")
        desc_clean = description.replace("\u2014", "-").replace("\u2013", "-")
        pname_clean = partner_name.replace("\u2014", "-").replace("\u2013", "-")

        safe_key = re.sub(r"[^a-z0-9]+", "-", partner_key.lower()).strip("-")
        safe_type = re.sub(r"[^a-z0-9]+", "-", action_type.lower()).strip("-")
        action_id = f"act-{property_id}-{safe_key}-{safe_type}"

        if action_id in self.items:
            existing = self.items[action_id]
            existing.updated_at = datetime.now(timezone.utc).isoformat()
            if deadline and not existing.deadline:
                existing.deadline = deadline
            return existing

        item = ActionItem(
            action_id=action_id,
            property_id=property_id,
            partner_key=partner_key,
            partner_name=pname_clean,
            title=title_clean,
            description=desc_clean,
            action_type=action_type,
            severity=severity,
            status="PENDING_OPERATOR",
            requires_operator_confirmation=True,
            deadline=deadline,
            missing_requirements=missing_requirements or [],
        )

        self._assert_item_invariants(item)
        self.items[action_id] = item
        self.save()
        return item

    def auto_approve(self, action_id: str) -> None:
        """
        Guaranteed guardrail: Auto-approving partner agreements without operator confirmation
        is strictly forbidden by standing invariants.
        Always raises RuntimeError.
        """
        raise RuntimeError(
            "Standing constraint violation: Never auto-approve partner agreements without operator confirmation."
        )

    def confirm_decision(
        self,
        action_id: str,
        decision: str,
        operator: str = "operator",
        notes: str = "",
    ) -> ActionItem:
        """
        Records human operator confirmation on a pending action bus item.
        Valid decisions: 'APPROVE', 'REJECT', 'RESOLVE'.
        """
        if action_id not in self.items:
            raise KeyError(f"Action item '{action_id}' not found on human action bus.")

        item = self.items[action_id]
        decision_upper = (decision or "").strip().upper()
        if decision_upper not in ("APPROVE", "REJECT", "RESOLVE"):
            raise ValueError(
                f"Invalid decision '{decision}'. Must be one of: APPROVE, REJECT, RESOLVE."
            )

        operator_clean = (operator or "operator").strip().replace("\u2014", "-").replace("\u2013", "-")
        notes_clean = (notes or "").strip().replace("\u2014", "-").replace("\u2013", "-")

        assert_no_forbidden_dashes(operator_clean, context="operator name")
        assert_no_forbidden_dashes(notes_clean, context="operator notes")

        if decision_upper == "APPROVE":
            item.status = "APPROVED"
        elif decision_upper == "REJECT":
            item.status = "REJECTED"
        elif decision_upper == "RESOLVE":
            item.status = "RESOLVED"

        now_str = datetime.now(timezone.utc).isoformat()
        item.updated_at = now_str
        item.resolved_at = now_str
        item.resolved_by = operator_clean
        item.operator_notes = notes_clean

        self._assert_item_invariants(item)
        self.save()
        return item

    def get_pending_items(self, property_id: Optional[str] = None) -> List[ActionItem]:
        """Returns list of items awaiting operator confirmation."""
        pending = [
            it for it in self.items.values()
            if it.status == "PENDING_OPERATOR"
        ]
        if property_id:
            prop_clean = property_id.strip().lower()
            pending = [it for it in pending if it.property_id.lower() == prop_clean]

        # Sort by severity priority: CRITICAL > HIGH > MEDIUM > LOW
        prio = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        pending.sort(key=lambda x: (prio.get(x.severity, 4), x.created_at))
        return pending

    def get_all_items(self, property_id: Optional[str] = None) -> List[ActionItem]:
        """Returns all action items."""
        items = list(self.items.values())
        if property_id:
            prop_clean = property_id.strip().lower()
            items = [it for it in items if it.property_id.lower() == prop_clean]
        prio = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        items.sort(key=lambda x: (0 if x.status == "PENDING_OPERATOR" else 1, prio.get(x.severity, 4), x.created_at))
        return items
