"""
The engine re-fetches tenant source datasets every cycle through a generic hook
(<package>/datasets/refresh.py), instead of tenants' freshness being hand-stamped.
Runs the real subprocess against a temporary tenant package.
Zero em-dashes. Zero en-dashes.
"""
import json
from pathlib import Path

from pseofactory.maintenance import SubprocessPropertyAdapter


def refresh_tenant_datasets(adapter):
    from pseofactory.maintenance import refresh_tenant_datasets as fn

    return fn(adapter)


def _tenant(tmp_path: Path, refresh_src: str = None) -> SubprocessPropertyAdapter:
    repo = tmp_path / "tenant"
    pkg = repo / "tenantx"
    (pkg / "datasets").mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "datasets" / "__init__.py").write_text("")
    (repo / "dist").mkdir()
    if refresh_src is not None:
        (pkg / "datasets" / "refresh.py").write_text(refresh_src)
    return SubprocessPropertyAdapter(
        property_id="tenantx", brand_name="TenantX", domain="tenantx.example",
        canonical_base="https://tenantx.example", dist_dir=repo / "dist", repo_path=repo,
    )


def test_tenant_without_refresher_is_left_alone(tmp_path):
    assert refresh_tenant_datasets(_tenant(tmp_path)) is None


def test_refresher_runs_in_tenant_and_reports_changed_data(tmp_path):
    adapter = _tenant(
        tmp_path,
        "import json, pathlib\n"
        "pathlib.Path('data.json').write_text('{\"rate\": 4.32}')\n"
        "print(json.dumps({'status': 'CHANGED', 'data_changed': True, 'results': []}))\n",
    )
    rep = refresh_tenant_datasets(adapter)
    assert rep == {"status": "CHANGED", "data_changed": True, "results": []}
    assert json.loads((adapter.repo_path / "data.json").read_text()) == {"rate": 4.32}


def test_crashing_refresher_is_reported_failed_not_silently_ok(tmp_path):
    adapter = _tenant(tmp_path, "raise SystemExit('FRED unreachable')\n")
    rep = refresh_tenant_datasets(adapter)
    assert rep["status"] == "FAILED" and rep["data_changed"] is False


REFRESH_REPORTING = (
    "import json, pathlib\n"
    "fp = pathlib.Path('data.json').read_text()\n"
    "print(json.dumps({'status': 'UNCHANGED', 'data_changed': False, 'data_fingerprint': fp, 'results': []}))\n"
)


def test_stale_dist_is_rebuilt_even_when_data_changed_in_an_earlier_cycle(tmp_path, monkeypatch):
    """
    Lifecycle: cycle 1 refreshed the data but died before rebuilding. Cycle 2's refresh is
    NOT_DUE (data_changed False), yet dist was never built from this data, so it must
    rebuild. Cycle 3 must not rebuild again. A failed build must not advance the stamp.
    """
    from pseofactory import maintenance

    adapter = _tenant(tmp_path, REFRESH_REPORTING)
    (adapter.repo_path / "data.json").write_text("fp-new-data")
    builds = []
    outcome = {"ok": False}

    def fake_build_all(self):
        builds.append(1)
        return outcome["ok"]

    monkeypatch.setattr(SubprocessPropertyAdapter, "build_all", fake_build_all)

    rep = maintenance.sync_tenant_data_and_build(adapter)  # build fails
    assert rep["rebuilt"] is False and len(builds) == 1
    assert not (adapter.repo_path / maintenance.TENANT_DATA_BUILD_STAMP).exists()

    outcome["ok"] = True
    rep = maintenance.sync_tenant_data_and_build(adapter)  # data unchanged this run, dist still stale
    assert rep["data_changed"] is False and rep["rebuilt"] is True and len(builds) == 2

    rep = maintenance.sync_tenant_data_and_build(adapter)  # dist built from current data: no churn
    assert rep["rebuilt"] is False and len(builds) == 2

    (adapter.repo_path / "data.json").write_text("fp-newer-data")
    assert maintenance.sync_tenant_data_and_build(adapter)["rebuilt"] is True and len(builds) == 3


def _treasury_sidecar(tmp_path, tbill, published):
    from pseofactory.maintenance import RetroReflectionEngine

    spec = dict(RetroReflectionEngine.PROFITHELM_FALLBACK_MANIFESTS["treasury-yield-calculator"])
    spec["inputs"] = dict(spec["inputs"], treasury_yield_pct=tbill)
    spec["published_output"] = published
    (tmp_path / "manifests").mkdir(exist_ok=True)
    (tmp_path / "manifests" / "treasury-yield-calculator.json").write_text(json.dumps(spec))


def test_engine_preset_does_not_override_tenant_manifest_built_from_fresh_data(tmp_path):
    """profithelm 2026-11-15: FRED DGS3MO moved 4.80 -> 4.32; the engine's hard-coded preset kept
    forcing 4.80/6.13 onto the page, contradicting the rendered 5.52 (Gate 5 SSR parity)."""
    from pseofactory.maintenance import RetroReflectionEngine

    _treasury_sidecar(tmp_path, 4.32, 5.52)
    m = RetroReflectionEngine._resolve_manifest_for_page(
        "<html><body>no inline manifest</body></html>", "profithelm", "treasury-yield-calculator", dist_dir=tmp_path
    )
    assert (m["inputs"]["treasury_yield_pct"], m["published_output"]) == (4.32, 5.52)


def test_engine_preset_still_replaces_a_fabricated_tenant_manifest(tmp_path):
    from pseofactory.maintenance import RetroReflectionEngine

    _treasury_sidecar(tmp_path, 4.32, 9.99)  # output does not follow from inputs
    m = RetroReflectionEngine._resolve_manifest_for_page(
        "<html><body>no inline manifest</body></html>", "profithelm", "treasury-yield-calculator", dist_dir=tmp_path
    )
    preset = RetroReflectionEngine.PROFITHELM_FALLBACK_MANIFESTS["treasury-yield-calculator"]
    assert m["published_output"] == preset["published_output"]
