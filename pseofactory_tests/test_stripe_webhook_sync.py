"""
Tests for repeatable, idempotent Stripe webhook provisioning, Cloudflare Pages
STRIPE_WEBHOOK_SECRET binding, live endpoint probe verification, and atomic
monetization_vault.json sync across dynamically discovered active tenants (50+ sites).
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import shutil
import subprocess
import textwrap
import urllib.error
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from pseofactory.cli import build_parser, cmd_lead_monitor
from pseofactory.contracts import assert_no_forbidden_dashes
from pseofactory.edge import (
    generate_edge_lead_capture_function,
    generate_edge_stripe_webhook_function,
)
from pseofactory.partner_tracker import (
    _discover_tenant_webhook_targets,
    _load_tenant_stripe_webhook_secret,
    _normalize_webhook_url,
    _sanitize_error_text,
    sync_cloudflare_pages_lead_credentials,
    sync_stripe_webhooks_for_tenants,
    verify_stripe_webhook_endpoint,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class _FakeHTTPResponse:
    def __init__(self, payload: Any, status: int = 200) -> None:
        self.status = status
        self._raw = (
            payload.encode("utf-8")
            if isinstance(payload, str)
            else json.dumps(payload).encode("utf-8")
        )

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, *exc: Any) -> None:
        return None

    def read(self) -> bytes:
        return self._raw


def _make_tenant(
    ws: Path,
    folder_name: str,
    property_id: str,
    domain: str,
    wrangler_name: str = "",
    canonical_base: str = "",
    extra_wrangler_toml: str = "",
) -> Path:
    repo = ws / folder_name
    repo.mkdir(parents=True, exist_ok=True)
    meta: Dict[str, Any] = {
        "property_id": property_id,
        "domain": domain,
        "brand_name": property_id.capitalize(),
        "package_name": property_id,
        "dist_dir": "dist",
    }
    if canonical_base:
        meta["canonical_base"] = canonical_base
    elif "://" not in domain:
        meta["canonical_base"] = f"https://{domain}"
    (repo / ".pseofactory.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    if wrangler_name or extra_wrangler_toml:
        lines: List[str] = []
        if wrangler_name:
            lines.append(f'name = "{wrangler_name}"')
        lines.append('compatibility_date = "2026-09-15"')
        if extra_wrangler_toml:
            lines.append(extra_wrangler_toml)
        (repo / "wrangler.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return repo


def _copy_vault(tmp_path: Path) -> Path:
    src = REPO_ROOT / "pseofactory" / "monetization_vault.json"
    dst = tmp_path / "monetization_vault.json"
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dst


def test_dynamic_discovery_scales_to_arbitrary_n_tenants_and_normalizes_domains(
    tmp_path: Path,
) -> None:
    ws = tmp_path / "workspace"
    ws.mkdir()
    for idx in range(1, 8):
        pid = f"site{idx:02d}"
        _make_tenant(
            ws,
            folder_name=f"{pid}-repo",
            property_id=pid,
            domain=(f"https://{pid}.example.com/" if idx == 6 else f"{pid}.example.com"),
            wrangler_name=f"{pid}-pages" if idx == 7 else "",
            extra_wrangler_toml='[vars]\nname = "wrong-nested-name"' if idx == 7 else "",
        )

    targets = _discover_tenant_webhook_targets(workspace_root=ws)
    assert len(targets) == 7
    assert [t["property_id"] for t in targets] == [f"site{i:02d}" for i in range(1, 8)]
    assert targets[0]["webhook_url"] == "https://site01.example.com/api/stripe-webhook"
    assert targets[0]["pages_project"] == "site01"
    # Scheme and trailing slash in domain field must not produce https://https://...
    assert targets[5]["domain"] == "site06.example.com"
    assert targets[5]["canonical_base"] == "https://site06.example.com"
    assert targets[5]["webhook_url"] == "https://site06.example.com/api/stripe-webhook"
    # Top-level wrangler.toml name parsed via tomllib (not shadowed by [vars].name)
    assert targets[6]["pages_project"] == "site07-pages"

    filtered = _discover_tenant_webhook_targets(workspace_root=ws, property_id="site03")
    assert [t["property_id"] for t in filtered] == ["site03"]

    dry_rep = sync_stripe_webhooks_for_tenants(
        execute_live=False,
        verify_live=False,
        workspace_root=ws,
    )
    assert dry_rep["discovered_tenants_count"] == 7
    assert dry_rep["created_count"] == 0
    assert dry_rep["vault_updated"] is False
    assert dry_rep["tenants"]["site01"]["action"] == "dry_run_planned"

    # URL normalization preserves non-empty query strings
    assert (
        _normalize_webhook_url("HTTPS://Example.COM/api/stripe-webhook/?v=2")
        == "https://example.com/api/stripe-webhook?v=2"
    )
    assert (
        _normalize_webhook_url("https://example.com/api/stripe-webhook/")
        == "https://example.com/api/stripe-webhook"
    )


def test_stripe_webhook_sync_idempotency_pagination_and_wildcard_events(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    ws.mkdir()
    for pid in ("alpha", "beta", "gamma"):
        _make_tenant(ws, f"{pid}-repo", pid, f"{pid}.com")
    vault_copy = _copy_vault(tmp_path)

    requests_log: List[tuple[str, str]] = []

    def fake_urlopen(req: Any, timeout: int = 15) -> _FakeHTTPResponse:
        method = req.get_method()
        url = req.full_url
        requests_log.append((method, url))
        if method == "GET" and url.startswith("https://api.stripe.com/v1/webhook_endpoints"):
            if "starting_after=" not in url:
                return _FakeHTTPResponse(
                    {
                        "has_more": True,
                        "data": [
                            {
                                "id": "we_alpha_1",
                                "url": "https://alpha.com/api/stripe-webhook",
                                "status": "enabled",
                                "enabled_events": ["checkout.session.completed"],
                            },
                            {
                                "id": "we_beta_wildcard",
                                "url": "https://beta.com/api/stripe-webhook/",
                                "status": "enabled",
                                "enabled_events": ["*"],
                            },
                        ],
                    }
                )
            assert "starting_after=we_beta_wildcard" in url
            return _FakeHTTPResponse(
                {
                    "has_more": False,
                    "data": [
                        {
                            "id": "we_gamma_1",
                            "url": "https://gamma.com/api/stripe-webhook",
                            "status": "enabled",
                            "enabled_events": ["checkout.session.completed"],
                        }
                    ],
                }
            )
        raise AssertionError(f"Unexpected HTTP call during idempotent reuse: {method} {url}")

    with (
        patch(
            "pseofactory.partner_tracker._load_stripe_credentials",
            return_value={"secret_key": "sk_live_mock_key_001", "account_id": "acct_1T6fSTIq0ckFsf5j"},
        ),
        patch("pseofactory.partner_tracker._load_wrangler_oauth_token", return_value="cf_mock_tok"),
        patch("urllib.request.urlopen", side_effect=fake_urlopen),
    ):
        rep = sync_stripe_webhooks_for_tenants(
            execute_live=True,
            verify_live=False,
            workspace_root=ws,
            vault_path=vault_copy,
            env_override={},
        )

    assert rep["reused_count"] == 3
    assert rep["created_count"] == 0
    assert rep["pages_updated_count"] == 0
    assert rep["vault_updated"] is True
    assert rep["errors"] == []
    assert not any(m == "POST" for m, _ in requests_log)
    assert not any(m == "PATCH" for m, _ in requests_log)

    saved_raw = vault_copy.read_text(encoding="utf-8")
    assert "whsec_" not in saved_raw
    assert "sk_live_" not in saved_raw
    assert_no_forbidden_dashes(saved_raw, context="saved vault")
    saved = json.loads(saved_raw)
    eps = saved["master_networks"]["stripe"]["webhook_endpoints"]
    assert eps["alpha"]["webhook_endpoint_id"] == "we_alpha_1"
    assert eps["beta"]["webhook_endpoint_id"] == "we_beta_wildcard"
    assert eps["beta"]["enabled_events"] == ["*"]
    assert eps["gamma"]["webhook_endpoint_id"] == "we_gamma_1"
    assert "profithelm" in eps


def test_new_tenant_creation_patches_cf_pages_preserving_env_and_never_leaks_whsec(
    tmp_path: Path,
) -> None:
    ws = tmp_path / "workspace"
    ws.mkdir()
    _make_tenant(ws, "alpha-repo", "alpha", "alpha.com")
    _make_tenant(ws, "beta-repo", "beta", "beta.com", wrangler_name="beta-pages")
    vault_copy = _copy_vault(tmp_path)

    call_order: List[str] = []
    captured_stripe_post: List[Dict[str, Any]] = []
    captured_cf_patches: Dict[str, Dict[str, Any]] = {}
    ephemeral_secret = "whsec_ephemeral_beta_secret_123456"

    def fake_urlopen(req: Any, timeout: int = 15) -> _FakeHTTPResponse:
        method = req.get_method()
        url = req.full_url
        call_order.append(f"{method} {url}")
        if method == "GET" and url.startswith("https://api.stripe.com/v1/webhook_endpoints"):
            return _FakeHTTPResponse(
                {
                    "has_more": False,
                    "data": [
                        {
                            "id": "we_alpha_existing",
                            "url": "https://alpha.com/api/stripe-webhook",
                            "status": "enabled",
                            "enabled_events": ["checkout.session.completed"],
                        },
                        {
                            "id": "we_beta_disabled_old",
                            "url": "https://beta.com/api/stripe-webhook",
                            "status": "disabled",
                            "enabled_events": ["checkout.session.completed"],
                        },
                    ],
                }
            )
        if method == "GET" and url.endswith("/pages/projects/beta-pages"):
            return _FakeHTTPResponse(
                {
                    "success": True,
                    "result": {
                        "deployment_configs": {
                            "production": {
                                "env_vars": {
                                    "CANONICAL_BASE": {"type": "plain_text", "value": "https://beta.com"},
                                    "DOMAIN": {"type": "plain_text", "value": "beta.com"},
                                    "STRIPE_SECRET_KEY": {"type": "secret_text", "value": None},
                                    "ZEPTOMAIL_TOKEN": {"type": "secret_text", "value": "***masked***"},
                                }
                            },
                            "preview": {
                                "env_vars": {
                                    "CANONICAL_BASE": {"type": "plain_text", "value": "https://beta.com"},
                                    "DOMAIN": {"type": "plain_text", "value": "beta.com"},
                                    "STRIPE_SECRET_KEY": {"type": "secret_text", "value": "***"},
                                }
                            },
                        }
                    },
                }
            )
        if method == "POST" and url == "https://api.stripe.com/v1/webhook_endpoints":
            parsed = urllib.parse.parse_qs(req.data.decode("utf-8"))
            captured_stripe_post.append(parsed)
            return _FakeHTTPResponse(
                {
                    "id": "we_beta_created_999",
                    "url": "https://beta.com/api/stripe-webhook",
                    "status": "enabled",
                    "enabled_events": ["checkout.session.completed"],
                    "secret": ephemeral_secret,
                }
            )
        if method == "PATCH" and url.endswith("/pages/projects/beta-pages"):
            body = json.loads(req.data.decode("utf-8"))
            captured_cf_patches["beta-pages"] = body
            return _FakeHTTPResponse(
                {
                    "success": True,
                    "result": {
                        "deployment_configs": {
                            "production": {
                                "env_vars": {
                                    "CANONICAL_BASE": {"type": "plain_text", "value": "https://beta.com"},
                                    "DOMAIN": {"type": "plain_text", "value": "beta.com"},
                                    "STRIPE_SECRET_KEY": {"type": "secret_text", "value": None},
                                    "ZEPTOMAIL_TOKEN": {"type": "secret_text", "value": None},
                                    "STRIPE_WEBHOOK_SECRET": {"type": "secret_text", "value": None},
                                }
                            }
                        }
                    },
                }
            )
        raise AssertionError(f"Unexpected call: {method} {url}")

    with (
        patch(
            "pseofactory.partner_tracker._load_stripe_credentials",
            return_value={"secret_key": "sk_live_mock_key_002", "account_id": "acct_1T6fSTIq0ckFsf5j"},
        ),
        patch("pseofactory.partner_tracker._load_wrangler_oauth_token", return_value="cf_mock_tok"),
        patch("urllib.request.urlopen", side_effect=fake_urlopen),
    ):
        rep = sync_stripe_webhooks_for_tenants(
            execute_live=True,
            verify_live=False,
            workspace_root=ws,
            vault_path=vault_copy,
            env_override={},
        )

    assert rep["reused_count"] == 1
    assert rep["created_count"] == 1
    assert rep["pages_updated_count"] == 1
    assert rep["vault_updated"] is True
    assert rep["errors"] == []

    # Verify Cloudflare GET preflight happened BEFORE Stripe POST create
    cf_get_idx = next(i for i, c in enumerate(call_order) if c.startswith("GET ") and c.endswith("/pages/projects/beta-pages"))
    stripe_post_idx = next(i for i, c in enumerate(call_order) if c == "POST https://api.stripe.com/v1/webhook_endpoints")
    cf_patch_idx = next(i for i, c in enumerate(call_order) if c.startswith("PATCH ") and c.endswith("/pages/projects/beta-pages"))
    assert cf_get_idx < stripe_post_idx < cf_patch_idx

    # Verify Stripe POST payload
    assert len(captured_stripe_post) == 1
    assert captured_stripe_post[0]["url"] == ["https://beta.com/api/stripe-webhook"]
    assert captured_stripe_post[0]["enabled_events[]"] == ["checkout.session.completed"]

    # Verify Cloudflare PATCH preserved plain_text env vars and unconditionally omitted ALL secret_text keys (even masked)
    cf_patch = captured_cf_patches["beta-pages"]
    for env_name in ("production", "preview"):
        env_vars = cf_patch["deployment_configs"][env_name]["env_vars"]
        assert env_vars["CANONICAL_BASE"] == {"type": "plain_text", "value": "https://beta.com"}
        assert env_vars["DOMAIN"] == {"type": "plain_text", "value": "beta.com"}
        assert env_vars["STRIPE_WEBHOOK_SECRET"] == {
            "type": "secret_text",
            "value": ephemeral_secret,
        }
        assert "STRIPE_SECRET_KEY" not in env_vars
        assert "ZEPTOMAIL_TOKEN" not in env_vars
        assert "kv_namespaces" not in cf_patch["deployment_configs"][env_name]

    # Verify zero secret leakage in report JSON and saved vault
    rep_json = json.dumps(rep)
    assert ephemeral_secret not in rep_json
    assert "whsec_" not in rep_json
    assert "sk_live_" not in rep_json

    saved_raw = vault_copy.read_text(encoding="utf-8")
    assert ephemeral_secret not in saved_raw
    assert "whsec_" not in saved_raw
    assert_no_forbidden_dashes(saved_raw, context="saved vault after create")
    saved = json.loads(saved_raw)
    assert saved["master_networks"]["stripe"]["webhook_status"] == "enabled"
    assert saved["master_networks"]["stripe"]["webhook_endpoints"]["beta"] == {
        "webhook_endpoint_id": "we_beta_created_999",
        "url": "https://beta.com/api/stripe-webhook",
        "status": "enabled",
        "enabled_events": ["checkout.session.completed"],
    }


def test_cloudflare_preflight_failure_prevents_stripe_webhook_creation(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    ws.mkdir()
    _make_tenant(ws, "gamma-repo", "gamma", "gamma.com")
    vault_copy = _copy_vault(tmp_path)
    original_vault = vault_copy.read_text(encoding="utf-8")

    stripe_post_calls: List[str] = []

    def fake_urlopen_cf_404(req: Any, timeout: int = 15) -> _FakeHTTPResponse:
        method = req.get_method()
        url = req.full_url
        if method == "GET" and url.startswith("https://api.stripe.com/v1/webhook_endpoints"):
            return _FakeHTTPResponse({"has_more": False, "data": []})
        if method == "GET" and url.endswith("/pages/projects/gamma"):
            raise urllib.error.HTTPError(
                url, 404, "Not Found", hdrs={}, fp=io.BytesIO(b'{"success":false}')
            )
        if method == "POST" and url == "https://api.stripe.com/v1/webhook_endpoints":
            stripe_post_calls.append(url)
            raise AssertionError("Stripe POST must NOT be called when Cloudflare preflight fails")
        raise AssertionError(f"Unexpected call: {method} {url}")

    # 1. Cloudflare GET 404 aborts BEFORE Stripe POST
    with (
        patch(
            "pseofactory.partner_tracker._load_stripe_credentials",
            return_value={"secret_key": "sk_live_mock_preflight", "account_id": "acct_1T6fSTIq0ckFsf5j"},
        ),
        patch("pseofactory.partner_tracker._load_wrangler_oauth_token", return_value="cf_mock_tok"),
        patch("urllib.request.urlopen", side_effect=fake_urlopen_cf_404),
    ):
        rep_404 = sync_stripe_webhooks_for_tenants(
            execute_live=True,
            verify_live=False,
            workspace_root=ws,
            vault_path=vault_copy,
            env_override={},
        )

    assert stripe_post_calls == []
    assert rep_404["created_count"] == 0
    assert rep_404["vault_updated"] is False
    assert rep_404["tenants"]["gamma"]["action"] == "error"
    assert any("cloudflare_preflight_failed" in e for e in rep_404["errors"])
    assert vault_copy.read_text(encoding="utf-8") == original_vault

    # 2. Missing Cloudflare token aborts BEFORE Stripe POST
    with (
        patch(
            "pseofactory.partner_tracker._load_stripe_credentials",
            return_value={"secret_key": "sk_live_mock_preflight", "account_id": "acct_1T6fSTIq0ckFsf5j"},
        ),
        patch("pseofactory.partner_tracker._load_wrangler_oauth_token", return_value=""),
        patch("urllib.request.urlopen", side_effect=fake_urlopen_cf_404),
    ):
        rep_no_tok = sync_stripe_webhooks_for_tenants(
            execute_live=True,
            verify_live=False,
            workspace_root=ws,
            vault_path=vault_copy,
            env_override={},
        )

    assert stripe_post_calls == []
    assert rep_no_tok["created_count"] == 0
    assert rep_no_tok["vault_updated"] is False
    assert any("cloudflare_token_missing" in e for e in rep_no_tok["errors"])
    assert vault_copy.read_text(encoding="utf-8") == original_vault


def test_post_create_cf_patch_failure_rolls_back_stripe_endpoint_and_skips_vault(
    tmp_path: Path,
) -> None:
    ws = tmp_path / "workspace"
    ws.mkdir()
    _make_tenant(ws, "delta-repo", "delta", "delta.com")
    vault_copy = _copy_vault(tmp_path)
    original_vault = vault_copy.read_text(encoding="utf-8")

    deleted_endpoints: List[str] = []

    def fake_urlopen_dropped_secret(req: Any, timeout: int = 15) -> _FakeHTTPResponse:
        method = req.get_method()
        url = req.full_url
        if method == "GET" and url.startswith("https://api.stripe.com/v1/webhook_endpoints"):
            return _FakeHTTPResponse({"has_more": False, "data": []})
        if method == "GET" and url.endswith("/pages/projects/delta"):
            return _FakeHTTPResponse(
                {
                    "success": True,
                    "result": {
                        "deployment_configs": {
                            "production": {
                                "env_vars": {
                                    "DOMAIN": {"type": "plain_text", "value": "delta.com"},
                                    "ZEPTOMAIL_TOKEN": {"type": "secret_text", "value": None},
                                }
                            },
                            "preview": {"env_vars": {}},
                        }
                    },
                }
            )
        if method == "POST" and url == "https://api.stripe.com/v1/webhook_endpoints":
            return _FakeHTTPResponse(
                {
                    "id": "we_delta_orphan_check",
                    "url": "https://delta.com/api/stripe-webhook",
                    "status": "enabled",
                    "enabled_events": ["checkout.session.completed"],
                    "secret": "whsec_delta_temp_12345",
                }
            )
        if method == "PATCH" and url.endswith("/pages/projects/delta"):
            # Simulate Cloudflare response that dropped pre-existing ZEPTOMAIL_TOKEN!
            return _FakeHTTPResponse(
                {
                    "success": True,
                    "result": {
                        "deployment_configs": {
                            "production": {
                                "env_vars": {
                                    "DOMAIN": {"type": "plain_text", "value": "delta.com"},
                                    "STRIPE_WEBHOOK_SECRET": {"type": "secret_text", "value": None},
                                }
                            }
                        }
                    },
                }
            )
        if method == "DELETE" and url.endswith("/v1/webhook_endpoints/we_delta_orphan_check"):
            deleted_endpoints.append(url)
            return _FakeHTTPResponse({"id": "we_delta_orphan_check", "deleted": True})
        raise AssertionError(f"Unexpected call: {method} {url}")

    with (
        patch(
            "pseofactory.partner_tracker._load_stripe_credentials",
            return_value={"secret_key": "sk_live_mock_rollback", "account_id": "acct_1T6fSTIq0ckFsf5j"},
        ),
        patch("pseofactory.partner_tracker._load_wrangler_oauth_token", return_value="cf_mock_tok"),
        patch("urllib.request.urlopen", side_effect=fake_urlopen_dropped_secret),
    ):
        rep = sync_stripe_webhooks_for_tenants(
            execute_live=True,
            verify_live=False,
            workspace_root=ws,
            vault_path=vault_copy,
            env_override={},
        )

    assert len(deleted_endpoints) == 1
    assert rep["created_count"] == 0
    assert rep["pages_updated_count"] == 0
    assert rep["vault_updated"] is False
    assert rep["tenants"]["delta"]["action"] == "error"
    assert rep["tenants"]["delta"]["status"] == "rolled_back"
    assert rep["tenants"]["delta"]["pages_secret_sync"]["updated"] is False
    assert any("existing_production_secrets_dropped:ZEPTOMAIL_TOKEN" in e for e in rep["errors"])
    assert "whsec_" not in json.dumps(rep)
    assert vault_copy.read_text(encoding="utf-8") == original_vault


def test_per_tenant_env_secret_sync_isolation_and_full_preview_redaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = tmp_path / "workspace"
    ws.mkdir()
    _make_tenant(ws, "alpha-repo", "alpha", "alpha.com")
    vault_copy = _copy_vault(tmp_path)

    # Verify env_override={} is authoritative and does NOT fall through to os.environ
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET_ALPHA", "whsec_os_env_should_not_leak")
    assert _load_tenant_stripe_webhook_secret("alpha", workspace_root=ws, env_override={}) == ""
    assert (
        _load_tenant_stripe_webhook_secret(
            "alpha", workspace_root=ws, env_override={"STRIPE_WEBHOOK_SECRET_ALPHA": "whsec_override_only"}
        )
        == "whsec_override_only"
    )

    cf_patches: Dict[str, Any] = {}
    env_whsec = "whsec_from_env_alpha_777"

    def fake_urlopen(req: Any, timeout: int = 15) -> _FakeHTTPResponse:
        method = req.get_method()
        url = req.full_url
        if method == "GET" and url.startswith("https://api.stripe.com/v1/webhook_endpoints"):
            return _FakeHTTPResponse(
                {
                    "has_more": False,
                    "data": [
                        {
                            "id": "we_alpha_existing",
                            "url": "https://alpha.com/api/stripe-webhook",
                            "status": "enabled",
                            "enabled_events": ["checkout.session.completed"],
                        }
                    ],
                }
            )
        if method == "GET" and url.endswith("/pages/projects/alpha"):
            return _FakeHTTPResponse(
                {
                    "success": True,
                    "result": {
                        "deployment_configs": {
                            "production": {"env_vars": {"DOMAIN": {"type": "plain_text", "value": "alpha.com"}}},
                            "preview": {"env_vars": {"DOMAIN": {"type": "plain_text", "value": "alpha.com"}}},
                        }
                    },
                }
            )
        if method == "PATCH" and url.endswith("/pages/projects/alpha"):
            cf_patches["alpha"] = json.loads(req.data.decode("utf-8"))
            return _FakeHTTPResponse(
                {
                    "success": True,
                    "result": {
                        "deployment_configs": {
                            "production": {
                                "env_vars": {
                                    "DOMAIN": {"type": "plain_text", "value": "alpha.com"},
                                    "STRIPE_WEBHOOK_SECRET": {"type": "secret_text", "value": None},
                                }
                            }
                        }
                    },
                }
            )
        raise AssertionError(f"Unexpected call: {method} {url}")

    with (
        patch(
            "pseofactory.partner_tracker._load_stripe_credentials",
            return_value={"secret_key": "sk_live_mock_key_003", "account_id": "acct_1T6fSTIq0ckFsf5j"},
        ),
        patch("pseofactory.partner_tracker._load_wrangler_oauth_token", return_value="cf_mock_tok"),
        patch("urllib.request.urlopen", side_effect=fake_urlopen),
    ):
        rep = sync_stripe_webhooks_for_tenants(
            execute_live=True,
            verify_live=False,
            workspace_root=ws,
            vault_path=vault_copy,
            env_override={"STRIPE_WEBHOOK_SECRET_ALPHA": env_whsec},
        )

    assert rep["reused_count"] == 1
    assert rep["pages_updated_count"] == 1
    assert rep["errors"] == []
    assert cf_patches["alpha"]["deployment_configs"]["production"]["env_vars"]["STRIPE_WEBHOOK_SECRET"] == {
        "type": "secret_text",
        "value": env_whsec,
    }
    assert env_whsec not in json.dumps(rep)

    # Reused endpoint with env_secret set but missing cf_token MUST record an error
    with (
        patch(
            "pseofactory.partner_tracker._load_stripe_credentials",
            return_value={"secret_key": "sk_live_mock_key_003", "account_id": "acct_1T6fSTIq0ckFsf5j"},
        ),
        patch("pseofactory.partner_tracker._load_wrangler_oauth_token", return_value=""),
        patch("urllib.request.urlopen", side_effect=fake_urlopen),
    ):
        rep_no_cf = sync_stripe_webhooks_for_tenants(
            execute_live=True,
            verify_live=False,
            workspace_root=ws,
            vault_path=vault_copy,
            env_override={"STRIPE_WEBHOOK_SECRET_ALPHA": env_whsec},
        )
    assert any("cloudflare_token_missing" in e for e in rep_no_cf["errors"])

    # Verify sync_cloudflare_pages_lead_credentials(execute_live=False) redacts ALL secret_text keys
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET_PROFITHELM", "whsec_profithelm_env_test")
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET_PREXVO", raising=False)
    with (
        patch(
            "pseofactory.partner_tracker._load_email_engine_credentials",
            return_value={
                "ZEPTOMAIL_TOKEN": "zoho_zepto_secret_token_999",
                "NANGO_SECRET_KEY": "nango_secret_key_888",
                "TELEMETRY_EXPORT_SECRET": "telemetry_secret_777",
            },
        ),
        patch(
            "pseofactory.partner_tracker._load_stripe_credentials",
            return_value={
                "account_id": "acct_1T6fSTIq0ckFsf5j",
                "publishable_key": "pk_live_pub_test",
                "secret_key": "sk_live_must_not_leak_in_preview_123",
            },
        ),
    ):
        dry_pages = sync_cloudflare_pages_lead_credentials(execute_live=False)

    assert "STRIPE_WEBHOOK_SECRET" in dry_pages["projects"]["profithelm"]["bound_keys"]
    assert "STRIPE_WEBHOOK_SECRET" not in dry_pages["projects"]["prexvo"]["bound_keys"]
    dry_pages_json = json.dumps(dry_pages)
    for forbidden in (
        "whsec_profithelm_env_test",
        "sk_live_must_not_leak_in_preview_123",
        "sk_live_",
        "zoho_zepto_secret_token_999",
        "nango_secret_key_888",
        "telemetry_secret_777",
    ):
        assert forbidden not in dry_pages_json

    # Verify _sanitize_error_text leaves no literal whsec_ or sk_live_ prefix
    sanitized = _sanitize_error_text(
        "failed with whsec_abc123 and sk_live_xyz987 in trace"
    )
    assert "whsec_" not in sanitized
    assert "sk_live_" not in sanitized
    assert "[REDACTED_STRIPE_SECRET]" in sanitized


def test_verify_stripe_webhook_endpoint_503_and_hmac_format(tmp_path: Path) -> None:
    secret = "whsec_verify_probe_secret_abc"
    probe_url = "https://profithelm.com/api/stripe-webhook"
    fixed_ts = 1795300000

    # 1. Unsigned 503 stripe_webhook_secret_unconfigured -> FAIL
    def fake_503(req: Any, timeout: int = 12) -> _FakeHTTPResponse:
        raise urllib.error.HTTPError(
            req.full_url,
            503,
            "Service Unavailable",
            hdrs={},
            fp=io.BytesIO(b'{"ok":false,"error":"stripe_webhook_secret_unconfigured"}'),
        )

    with patch("urllib.request.urlopen", side_effect=fake_503):
        res_503 = verify_stripe_webhook_endpoint(probe_url)
    assert res_503["verified"] is False
    assert res_503["unsigned_probe"]["http_status"] == 503
    assert res_503["unsigned_probe"]["error_code"] == "stripe_webhook_secret_unconfigured"
    assert res_503["unsigned_probe"]["secret_configured"] is False

    # 2. Verify exact deterministic HMAC format + verify_only and stripe_list_failed action labels
    captured_sig_headers: List[str] = []

    def fake_capture_sig(req: Any, timeout: int = 12) -> _FakeHTTPResponse:
        sig = req.headers.get("Stripe-signature") or req.headers.get("Stripe-Signature") or ""
        if not sig:
            raise urllib.error.HTTPError(
                req.full_url,
                400,
                "Bad Request",
                hdrs={},
                fp=io.BytesIO(b'{"ok":false,"error":"invalid_stripe_signature_header"}'),
            )
        captured_sig_headers.append(sig)
        return _FakeHTTPResponse(
            {"ok": True, "ignored": True, "reason": "unhandled_event_type"}
        )

    with patch("urllib.request.urlopen", side_effect=fake_capture_sig):
        res_ok = verify_stripe_webhook_endpoint(probe_url, webhook_secret=secret, timestamp_sec=fixed_ts)

    assert res_ok["verified"] is True
    expected_body = '{"id":"evt_pseofactory_probe","type":"pseofactory.webhook.probe","livemode":true,"data":{"object":{}}}'
    expected_v1 = hmac.new(
        secret.encode("utf-8"),
        f"{fixed_ts}.{expected_body}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    assert captured_sig_headers == [f"t={fixed_ts},v1={expected_v1}"]

    ws = tmp_path / "ws_actions"
    ws.mkdir()
    _make_tenant(ws, "alpha-repo", "alpha", "alpha.com")

    with patch("urllib.request.urlopen", side_effect=fake_capture_sig):
        rep_verify_only = sync_stripe_webhooks_for_tenants(
            execute_live=False,
            verify_live=True,
            workspace_root=ws,
            env_override={},
        )
    assert rep_verify_only["tenants"]["alpha"]["action"] == "verify_only"
    assert rep_verify_only["all_verified"] is True

    def fake_stripe_list_boom(req: Any, timeout: int = 15) -> _FakeHTTPResponse:
        raise RuntimeError("network_down_whsec_secret_123")

    with (
        patch(
            "pseofactory.partner_tracker._load_stripe_credentials",
            return_value={"secret_key": "sk_live_mock", "account_id": "acct_1T6fSTIq0ckFsf5j"},
        ),
        patch("urllib.request.urlopen", side_effect=fake_stripe_list_boom),
    ):
        rep_list_err = sync_stripe_webhooks_for_tenants(
            execute_live=True,
            verify_live=False,
            workspace_root=ws,
            env_override={},
        )
    assert rep_list_err["tenants"]["alpha"]["action"] == "error"
    assert "whsec_" not in json.dumps(rep_list_err)


@pytest.mark.skipif(shutil.which("node") is None, reason="node runtime required")
def test_verify_stripe_webhook_endpoint_against_real_edge_js_handler(tmp_path: Path) -> None:
    secret = "whsec_verify_probe_secret_node"
    probe_url = "https://profithelm.com/api/stripe-webhook"

    edge_dir = tmp_path / "edge_fn"
    edge_dir.mkdir(parents=True, exist_ok=True)
    (edge_dir / "package.json").write_text('{"type":"module"}\n', encoding="utf-8")
    (edge_dir / "lead-capture.js").write_text(
        generate_edge_lead_capture_function("profithelm"), encoding="utf-8"
    )
    mod_file = edge_dir / "stripe-webhook.js"
    mod_file.write_text(generate_edge_stripe_webhook_function("profithelm"), encoding="utf-8")

    def fake_edge_via_real_node(req: Any, timeout: int = 12) -> _FakeHTTPResponse:
        body_text = req.data.decode("utf-8")
        sig_hdr = req.headers.get("Stripe-signature") or req.headers.get("Stripe-Signature") or ""
        node_runner = textwrap.dedent(
            f"""
            const mod = await import({json.dumps(str(mod_file))});
            const req = new Request({json.dumps(probe_url)}, {{
              method: "POST",
              headers: {{
                "Content-Type": "application/json",
                ...( {json.dumps(sig_hdr)} ? {{ "Stripe-Signature": {json.dumps(sig_hdr)} }} : {{}} )
              }},
              body: {json.dumps(body_text)}
            }});
            const res = await mod.onRequestPost({{
              request: req,
              env: {{ STRIPE_WEBHOOK_SECRET: {json.dumps(secret)} }}
            }});
            console.log(JSON.stringify({{ status: res.status, text: await res.text() }}));
            """
        )
        proc = subprocess.run(
            ["node", "--input-type=module", "-e", node_runner],
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )
        out = json.loads(proc.stdout.strip().splitlines()[-1])
        if out["status"] >= 400:
            raise urllib.error.HTTPError(
                req.full_url,
                out["status"],
                "Edge Error",
                hdrs={},
                fp=io.BytesIO(out["text"].encode("utf-8")),
            )
        return _FakeHTTPResponse(out["text"], status=out["status"])

    with patch("urllib.request.urlopen", side_effect=fake_edge_via_real_node):
        res_unsigned = verify_stripe_webhook_endpoint(probe_url)
        assert res_unsigned["verified"] is True
        assert res_unsigned["unsigned_probe"]["http_status"] == 400
        assert res_unsigned["unsigned_probe"]["error_code"] == "invalid_stripe_signature_header"
        assert res_unsigned["signed_probe"]["executed"] is False

        res_signed_ok = verify_stripe_webhook_endpoint(probe_url, webhook_secret=secret)
        assert res_signed_ok["verified"] is True
        assert res_signed_ok["unsigned_probe"]["ok"] is True
        assert res_signed_ok["signed_probe"]["executed"] is True
        assert res_signed_ok["signed_probe"]["ok"] is True
        assert res_signed_ok["signed_probe"]["http_status"] == 200
        assert res_signed_ok["signed_probe"]["reason"] == "unhandled_event_type"
        assert secret not in json.dumps(res_signed_ok)

        res_signed_bad = verify_stripe_webhook_endpoint(
            probe_url,
            webhook_secret="whsec_wrong_secret_xyz",
        )
        assert res_signed_bad["verified"] is False
        assert res_signed_bad["signed_probe"]["executed"] is True
        assert res_signed_bad["signed_probe"]["ok"] is False
        assert res_signed_bad["signed_probe"]["http_status"] == 400
        assert res_signed_bad["signed_probe"]["reason"] == "stripe_signature_mismatch"


def test_cli_lead_monitor_stripe_webhook_flags_and_exit_codes(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "lead-monitor",
            "--property",
            "profithelm",
            "--sync-stripe-webhooks",
            "--verify-stripe-webhooks",
            "--dry-run",
            "--json",
        ]
    )
    assert args.sync_stripe_webhooks is True
    assert args.verify_stripe_webhooks is True
    assert args.dry_run is True

    mock_pass = {
        "execute_live": True,
        "verify_live": True,
        "dry_run": True,
        "discovered_tenants_count": 1,
        "reused_count": 1,
        "created_count": 0,
        "pages_updated_count": 0,
        "vault_updated": False,
        "all_verified": True,
        "errors": [],
        "tenants": {},
    }
    mock_summary = {
        "total_leads": 0,
        "by_property": {},
        "transactional_fulfilled_count": 0,
        "action_bus_dispatched_count": 0,
        "total_pipeline_calculated_usd": 0.0,
        "total_checkout_offer_pipeline_usd": 0.0,
    }
    with (
        patch("pseofactory.partner_tracker.sync_stripe_webhooks_for_tenants", return_value=mock_pass) as m_sync,
        patch("pseofactory.partner_tracker.get_lead_monitoring_summary", return_value=dict(mock_summary)),
    ):
        rc = cmd_lead_monitor(args)
    assert rc == 0
    m_sync.assert_called_once_with(
        execute_live=True,
        verify_live=True,
        dry_run=True,
        property_id="profithelm",
    )
    out = json.loads(capsys.readouterr().out)
    assert out["stripe_webhooks_sync"]["all_verified"] is True

    # Fail-closed exit code 1 when verification fails
    mock_fail = dict(mock_pass, all_verified=False)
    with (
        patch("pseofactory.partner_tracker.sync_stripe_webhooks_for_tenants", return_value=mock_fail),
        patch("pseofactory.partner_tracker.get_lead_monitoring_summary", return_value=dict(mock_summary)),
    ):
        rc_fail = cmd_lead_monitor(args)
    assert rc_fail == 1
    capsys.readouterr()

    # Fail-closed exit code 1 on live sync error (non-dry-run with errors)
    live_args = parser.parse_args(
        ["lead-monitor", "--property", "profithelm", "--sync-stripe-webhooks", "--json"]
    )
    mock_live_err = dict(mock_pass, dry_run=False, verify_live=False, all_verified=None, errors=["profithelm: cloudflare_preflight_failed"])
    with (
        patch("pseofactory.partner_tracker.sync_stripe_webhooks_for_tenants", return_value=mock_live_err),
        patch("pseofactory.partner_tracker.get_lead_monitoring_summary", return_value=dict(mock_summary)),
    ):
        rc_live_err = cmd_lead_monitor(live_args)
    assert rc_live_err == 1


def test_repo_monetization_vault_has_all_four_live_enabled_stripe_webhooks() -> None:
    vault_path = REPO_ROOT / "pseofactory" / "monetization_vault.json"
    raw = vault_path.read_text(encoding="utf-8")
    assert_no_forbidden_dashes(raw, context="monetization_vault.json")
    assert "whsec_" not in raw
    vault = json.loads(raw)
    stripe_net = vault["master_networks"]["stripe"]
    assert stripe_net["webhook_status"] == "enabled"
    expected = {
        "profithelm": ("we_1UeQESIq0ckFsf5jesBwLBL7", "https://profithelm.com/api/stripe-webhook"),
        "prexvo": ("we_1UeQEZIq0ckFsf5jIFbpWYIl", "https://prexvo.com/api/stripe-webhook"),
        "gainhelm": ("we_1UeQEgIq0ckFsf5jYixaFW3P", "https://gainhelm.com/api/stripe-webhook"),
        "lienbond": ("we_1UeQEnIq0ckFsf5jZ97iobAe", "https://lienbond.com/api/stripe-webhook"),
    }
    eps = stripe_net["webhook_endpoints"]
    for pid, (ep_id, ep_url) in expected.items():
        assert eps[pid] == {
            "webhook_endpoint_id": ep_id,
            "url": ep_url,
            "status": "enabled",
            "enabled_events": ["checkout.session.completed"],
        }
