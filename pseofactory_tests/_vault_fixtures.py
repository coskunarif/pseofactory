"""Shared temporary monetization_vault.json fixtures for testing live partner rendering.

Designed for 50+ tenants: mutates an isolated copy of monetization_vault.json in tmp_path
and patches pseofactory.affiliates.MONETIZATION_VAULT_PATH without ever touching the real vault.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import itertools
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterator, Sequence

import pytest

from pseofactory import affiliates as aff_mod

_VAULT_FILE_COUNTER = itertools.count(1)


@contextmanager
def live_partners_in_temp_vault(
    tmp_path: Path,
    partners_by_property: Dict[str, Sequence[str]],
) -> Iterator[Path]:
    """Temporarily mark specified partners as 'live' in an isolated vault copy."""
    vault_data = json.loads(aff_mod.MONETIZATION_VAULT_PATH.read_text(encoding="utf-8"))
    props = vault_data.setdefault("properties", {})
    for prop_id, partner_keys in partners_by_property.items():
        prop_entry = props.setdefault(
            prop_id,
            {"name": prop_id, "property_id": prop_id, "partners": {}},
        )
        partners = prop_entry.setdefault("partners", {})
        for pk in partner_keys:
            if isinstance(partners.get(pk), dict):
                partners[pk]["status"] = "live"
            else:
                partners[pk] = {"status": "live"}

    tmp_vault = tmp_path / f"monetization_vault_live_{next(_VAULT_FILE_COUNTER)}.json"
    tmp_vault.write_text(json.dumps(vault_data, indent=2), encoding="utf-8")

    aff_mod._VAULT_LIVE_PARTNERS_CACHE.clear()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(aff_mod, "MONETIZATION_VAULT_PATH", tmp_vault)
        try:
            yield tmp_vault
        finally:
            aff_mod._VAULT_LIVE_PARTNERS_CACHE.clear()
