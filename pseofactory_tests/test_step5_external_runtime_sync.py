"""
Step 5 tests: externalized deferred runtime synchronizer (/static/js/pseo-runtime-sync.<sha10>.js)
and self-hosted runner concurrency capping in release_pipeline.sh.
Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations
import pytest

import concurrent.futures
import hashlib
import os
import re
import subprocess
import time
from pathlib import Path

from pseofactory.maintenance import RetroReflectionEngine
from pseofactory.porcelain_shell import (
    _collect_html_asset_and_hygiene_issues,
    _rewrite_local_js_version_tags,
    _sync_sitemaps_headers_and_redirects,
    compile_tenant_porcelain_estate,
    get_porcelain_tenant_profile,
    normalize_html_to_porcelain_shell,
)
from pseofactory.visual_primitives import (
    VISUAL_PRIMITIVES_VERSION,
    audit_monetization_and_datapack_ui_ux_surfaces,
    detect_visual_and_ux_contract_issues,
    get_runtime_synchronizer_js_sha10,
    get_runtime_synchronizer_script_src,
    has_current_external_runtime_sync_tag,
    normalize_html_visual_primitives,
    render_external_runtime_synchronizer_tag,
    render_runtime_synchronizer_js,
    render_runtime_synchronizer_script,
    write_runtime_synchronizer_asset,
)


def _sample_calculator_html() -> str:
    return """<!DOCTYPE html>
<html lang="en" data-theme="porcelain">
<head>
  <meta charset="utf-8">
  <title>Sample Calculator | ProfitHelm</title>
  <link rel="canonical" href="https://profithelm.com/tools/sample-calculator/">
</head>
<body>
  <main id="main-content">
    <section class="hero-section">
      <h1>Sample Calculator</h1>
    </section>
    <form class="calculator-form">
      <label for="gross-income">Gross Income</label>
      <input type="number" id="gross-income" value="100000" min="0" max="1000000" step="1000">
      <input type="range" id="gross-income-range" value="100000" min="0" max="1000000" step="1000">
      <strong class="output-value">25,000</strong>
    </form>
  </main>
</body>
</html>
"""


def test_externalization_roundtrip_pruning_and_idempotency(tmp_path: Path):
    """Verifies dist_dir externalization writes hashed JS, prunes stale hashes, and is idempotent."""
    dist_dir = tmp_path / "dist"
    js_dir = dist_dir / "static" / "js"
    js_dir.mkdir(parents=True)
    stale_bundle = js_dir / "pseo-runtime-sync.0000000000.js"
    stale_bundle.write_text("// stale bundle\n", encoding="utf-8")

    html1, rep1 = normalize_html_visual_primitives(_sample_calculator_html(), dist_dir=dist_dir)
    sha10 = get_runtime_synchronizer_js_sha10()
    expected_src = get_runtime_synchronizer_script_src()
    expected_file = js_dir / f"pseo-runtime-sync.{sha10}.js"

    assert expected_src == f"/static/js/pseo-runtime-sync.{sha10}.js"
    assert expected_file.is_file()
    assert hashlib.sha256(expected_file.read_bytes()).hexdigest()[:10] == sha10
    assert expected_file.read_text(encoding="utf-8") == render_runtime_synchronizer_js()
    assert not stale_bundle.exists(), "Stale pseo-runtime-sync.*.js bundle must be pruned"
    assert has_current_external_runtime_sync_tag(html1)
    assert "window.__pseoRuntimeSyncInitialized" not in html1
    assert "interactive_runtime_sync" in rep1
    assert detect_visual_and_ux_contract_issues(html1, require_primitives=True) == []

    # Second pass must be strictly idempotent (zero changes, zero asset rewrite)
    html2, rep2 = normalize_html_visual_primitives(html1, dist_dir=dist_dir)
    assert html2 == html1
    assert rep2 == []
    out_path, changed = write_runtime_synchronizer_asset(dist_dir)
    assert out_path == expected_file
    assert changed is False


def test_dist_dir_none_inline_fallback_and_external_tag_preservation():
    """Verifies dist_dir=None emits inline JS for raw HTML and preserves valid external tags idempotently."""
    inline_html, rep_inline = normalize_html_visual_primitives(_sample_calculator_html(), dist_dir=None)
    assert 'id="pseo-runtime-sync"' in inline_html
    assert "window.__pseoRuntimeSyncInitialized" in inline_html
    assert not has_current_external_runtime_sync_tag(inline_html)
    assert "interactive_runtime_sync" in rep_inline
    assert detect_visual_and_ux_contract_issues(inline_html, require_primitives=True) == []

    # Externalized HTML normalized again with dist_dir=None must preserve the external tag unchanged
    ext_tag = render_external_runtime_synchronizer_tag()
    externalized_input = inline_html.replace(render_runtime_synchronizer_script(), ext_tag)
    assert has_current_external_runtime_sync_tag(externalized_input)
    preserved, rep_preserved = normalize_html_visual_primitives(externalized_input, dist_dir=None)
    assert has_current_external_runtime_sync_tag(preserved)
    assert "window.__pseoRuntimeSyncInitialized" not in preserved
    assert rep_preserved == []


def test_fail_closed_negative_checks_external_runtime_sync(tmp_path: Path):
    """Verifies all 4 fail-closed negative checks: stale hash, missing defer, missing disk file, mutated disk file."""
    dist_dir = tmp_path / "dist"
    raw_tool = _sample_calculator_html()
    retro_html, _ = RetroReflectionEngine.retrofit_html(
        raw_tool,
        property_id="profithelm",
        slug="sample-calculator",
        canonical_url="https://profithelm.com/tools/sample-calculator/",
        dist_dir=dist_dir,
    )
    assert has_current_external_runtime_sync_tag(retro_html)
    assert RetroReflectionEngine.audit_html_mechanics(retro_html) == []

    sha10 = get_runtime_synchronizer_js_sha10()
    js_path = dist_dir / "static" / "js" / f"pseo-runtime-sync.{sha10}.js"
    assert js_path.is_file()

    # 1. Stale hash in <script src>
    stale_hash_html = retro_html.replace(f"pseo-runtime-sync.{sha10}.js", "pseo-runtime-sync.deadbeef00.js")
    assert not has_current_external_runtime_sync_tag(stale_hash_html)
    assert detect_visual_and_ux_contract_issues(stale_hash_html, require_primitives=True) != []
    assert "deterministic_visual_primitives" in RetroReflectionEngine.audit_html_mechanics(stale_hash_html)

    # 2. Missing defer attribute
    no_defer_html = retro_html.replace(" defer></script>", "></script>")
    assert not has_current_external_runtime_sync_tag(no_defer_html)
    assert detect_visual_and_ux_contract_issues(no_defer_html, require_primitives=True) != []
    assert "deterministic_visual_primitives" in RetroReflectionEngine.audit_html_mechanics(no_defer_html)

    # 3. Missing on-disk .js file -> audit_estate must mark STALE
    tool_file = dist_dir / "tools" / "sample-calculator" / "index.html"
    tool_file.parent.mkdir(parents=True, exist_ok=True)
    tool_file.write_text(retro_html, encoding="utf-8")

    js_path.unlink()
    audit_missing = RetroReflectionEngine.audit_estate(dist_dir, "profithelm")
    assert audit_missing["status"] == "STALE"
    assert f"static/js/pseo-runtime-sync.{sha10}.js" in audit_missing["stale_pages"]

    # 4. Mutated on-disk .js bytes -> audit_estate must mark STALE
    js_path.write_text("// tampered runtime sync bundle\n", encoding="utf-8")
    audit_tampered = RetroReflectionEngine.audit_estate(dist_dir, "profithelm")
    assert audit_tampered["status"] == "STALE"
    assert f"static/js/pseo-runtime-sync.{sha10}.js" in audit_tampered["stale_pages"]

    # 5. Restored valid bundle + extra stale bundle on disk -> audit_estate must mark STALE
    write_runtime_synchronizer_asset(dist_dir)
    stale_extra = dist_dir / "static" / "js" / "pseo-runtime-sync.1111111111.js"
    stale_extra.write_text("// leftover\n", encoding="utf-8")
    audit_stale_leftover = RetroReflectionEngine.audit_estate(dist_dir, "profithelm")
    assert audit_stale_leftover["status"] == "STALE"
    assert "static/js/pseo-runtime-sync.1111111111.js" in audit_stale_leftover["stale_pages"]

    # Clean up leftover -> bundle integrity checks pass
    stale_extra.unlink()
    audit_clean = RetroReflectionEngine.audit_estate(dist_dir, "profithelm")
    assert f"static/js/pseo-runtime-sync.{sha10}.js" not in audit_clean["stale_pages"]
    assert "static/js/pseo-runtime-sync.1111111111.js" not in audit_clean["stale_pages"]


def test_lienbond_runtime_sync_inside_main_relocated_cleanly_before_body_close(tmp_path: Path):
    """Verifies LienBond inline #pseo-runtime-sync embedded inside <main> is relocated outside <main>."""
    dist_dir = tmp_path / "dist"
    profile = get_porcelain_tenant_profile("lienbond")
    inline_rt = render_runtime_synchronizer_script()
    raw_lienbond_html = f"""<!DOCTYPE html>
<html lang="en" data-theme="porcelain">
<head>
  <meta charset="utf-8">
  <title>Bid Bond Calculator | LienBond</title>
  <link rel="canonical" href="https://lienbond.com/tools/bid-bond-calculator/">
</head>
<body>
  <main id="main-content">
    <div class="container">
      <section class="hero-section tool-hero card">
        <h1>Bid Bond Calculator</h1>
        <aside class="quick-answer"><p>Instant bid bond rate estimate.</p></aside>
      </section>
      <form class="calculator-form">
        <input type="number" id="input-bond_amount" value="250000">
        <strong class="output-value">2,500</strong>
      </form>
      {inline_rt}
    </div>
  </main>
  <script src="/static/js/generated/datasets.js" defer></script>
  <script src="/static/js/app.js" defer></script>
</body>
</html>
"""
    norm_html, _ = normalize_html_to_porcelain_shell(
        raw_lienbond_html,
        "tools/bid-bond-calculator/index.html",
        profile,
        dist_dir=dist_dir,
    )
    main_m = re.search(r"<main\b[^>]*>([\s\S]*?)</main>", norm_html, re.IGNORECASE)
    assert main_m is not None
    assert "pseo-runtime-sync" not in main_m.group(1), "Runtime sync script must be stripped from <main>"
    assert has_current_external_runtime_sync_tag(norm_html)
    assert norm_html.count('id="pseo-runtime-sync"') == 1
    assert "window.__pseoRuntimeSyncInitialized" not in norm_html

    footer_end = norm_html.rfind("</footer>")
    footer_handler_pos = norm_html.find('id="porcelain-footer-lead-handler"')
    datasets_pos = norm_html.find("/static/js/generated/datasets.js")
    app_pos = norm_html.find("/static/js/app.js")
    rt_pos = norm_html.find('id="pseo-runtime-sync"')
    body_end = norm_html.rfind("</body>")
    assert footer_end < footer_handler_pos < datasets_pos < app_pos < rt_pos < body_end


def test_porcelain_shell_content_hashed_js_versioning_headers_and_missing_asset_fail_closed(tmp_path: Path):
    """Verifies content-hashed JS skips ?v=, missing JS fails closed, and _headers pins /static/js/* immutable."""
    dist_dir = tmp_path / "dist"
    (dist_dir / "tools").mkdir(parents=True)
    (dist_dir / "tools" / "index.html").write_text("<html><body>tools</body></html>", encoding="utf-8")
    (dist_dir / "sitemap.xml").write_text("<urlset></urlset>", encoding="utf-8")
    (dist_dir / "static" / "js").mkdir(parents=True)
    (dist_dir / "static" / "js" / "app.js").write_text("console.log('ok');\n", encoding="utf-8")
    write_runtime_synchronizer_asset(dist_dir)

    profile = get_porcelain_tenant_profile("gainhelm")
    sha10 = get_runtime_synchronizer_js_sha10()
    src_rt = f"/static/js/pseo-runtime-sync.{sha10}.js"
    sample = (
        f'<html><body>'
        f'<script src="/static/js/app.js" defer></script>'
        f'<script id="pseo-runtime-sync" data-version="{VISUAL_PRIMITIVES_VERSION}" src="{src_rt}" defer></script>'
        f'</body></html>'
    )
    rewritten = _rewrite_local_js_version_tags(sample, profile, dist_dir=dist_dir)
    assert f'src="{src_rt}"' in rewritten, "Content-hashed JS must NOT get ?v= appended"
    assert f"{src_rt}?v=" not in rewritten
    assert re.search(r'src="/static/js/app\.js\?v=[0-9a-f]{10}"', rewritten)

    # All referenced local scripts exist -> zero issues
    issues_ok = _collect_html_asset_and_hygiene_issues(rewritten, "tools/demo/index.html", "gainhelm.com", dist_dir=dist_dir)
    assert issues_ok == []

    # Delete on-disk runtime sync bundle -> must fail closed on missing local script asset
    (dist_dir / "static" / "js" / f"pseo-runtime-sync.{sha10}.js").unlink()
    issues_missing = _collect_html_asset_and_hygiene_issues(rewritten, "tools/demo/index.html", "gainhelm.com", dist_dir=dist_dir)
    assert any("Missing local script asset" in i and src_rt in i for i in issues_missing)

    # _sync_sitemaps_headers_and_redirects guarantees /static/js/* immutable Cache-Control
    (dist_dir / "_headers").write_text("/*\n  X-Frame-Options: DENY\n", encoding="utf-8")
    _sync_sitemaps_headers_and_redirects(dist_dir, profile)
    hdrs = (dist_dir / "_headers").read_text(encoding="utf-8")
    assert "/static/js/*" in hdrs
    assert "Cache-Control: public, max-age=31536000, immutable" in hdrs

    # compile_tenant_porcelain_estate restores runtime sync asset and prunes stale hashes
    stale_f = dist_dir / "static" / "js" / "pseo-runtime-sync.abcdef0123.js"
    stale_f.write_text("// old\n", encoding="utf-8")
    compile_tenant_porcelain_estate(dist_dir, "gainhelm", repo_root=tmp_path)
    assert (dist_dir / "static" / "js" / f"pseo-runtime-sync.{sha10}.js").is_file()
    assert not stale_f.exists()


@pytest.mark.host_estate
def test_release_pipeline_concurrency_caps_cloud_parallel_and_fail_closed(tmp_path: Path):
    """
    Verifies release_pipeline.sh run_parallel_tenant_cascades runs cloud-hosted lienbond in parallel
    with a local queue capped at PSEUFACTORY_MAX_PARALLEL_LOCAL_CASCADES=1, and fails closed on error.
    """
    pipeline_path = Path("/home/ubuntuadmin/projects/.agy/release_pipeline.sh")
    assert pipeline_path.is_file()
    src = pipeline_path.read_text(encoding="utf-8")

    # Extract run_parallel_tenant_reflect and run_parallel_tenant_cascades definitions
    m_ref = re.search(r"run_parallel_tenant_reflect\(\) \{[\s\S]*?\n\}", src)
    m_cas = re.search(r"run_parallel_tenant_cascades\(\) \{[\s\S]*?\n\}", src)
    assert m_ref is not None and m_cas is not None

    # Create 4 fake dirty tenant git repos: profithelm-platform, prexvo, gainhelm, lienbond
    tenant_dirs = []
    for name in ("profithelm-platform", "prexvo", "gainhelm", "lienbond"):
        td = tmp_path / name
        td.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=td, check=True)
        (td / "dirty.txt").write_text("changed\n", encoding="utf-8")
        tenant_dirs.append(td)

    events_file = tmp_path / "events.log"
    child_stub = tmp_path / "child_stub.sh"
    child_stub.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail
t_base="$(basename "$1")"
run_id="$2"
echo "START ${{t_base}} $(date +%s.%N) ${{run_id}}" >> "{events_file}"
if [[ "${{FAIL_TENANT:-}}" == "$t_base" ]]; then
  sleep 0.1
  echo "FAIL ${{t_base}}" >&2
  exit 17
fi
sleep 0.35
echo "END ${{t_base}} $(date +%s.%N) ${{run_id}}" >> "{events_file}"
""",
        encoding="utf-8",
    )
    child_stub.chmod(0o755)

    harness = tmp_path / "harness.sh"
    harness.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail
RUNS_BASE="{tmp_path / 'runs'}"
RUN_ID="testrun"
TIMEOUT=60
AGY_CHILD_RELEASE_SCRIPT="{child_stub}"
{m_cas.group(0)}
run_parallel_tenant_cascades "{' '.join(str(d) for d in tenant_dirs)}" "prepush"
""",
        encoding="utf-8",
    )
    harness.chmod(0o755)

    # 1. Default max_local=1: lienbond overlaps with local queue; local tenants never overlap each other
    env = os.environ.copy()
    env["PSEUFACTORY_MAX_PARALLEL_LOCAL_CASCADES"] = "1"
    env.pop("FAIL_TENANT", None)
    t0 = time.perf_counter()
    res = subprocess.run(["bash", str(harness)], env=env, capture_output=True, text=True)
    elapsed = time.perf_counter() - t0
    assert res.returncode == 0, f"Cascade harness failed: {res.stdout}\n{res.stderr}"
    lines = events_file.read_text(encoding="utf-8").strip().splitlines()

    spans = {}
    for ln in lines:
        kind, tb, ts, rid = ln.split()
        assert rid == f"testrun-cascade-{tb}"
        spans.setdefault(tb, {})[kind] = float(ts)

    assert set(spans.keys()) == {"profithelm-platform", "prexvo", "gainhelm", "lienbond"}
    # Local self-hosted tenants must be strictly serialized (non-overlapping) when cap=1
    local_ordered = sorted(
        [(spans[n]["START"], spans[n]["END"], n) for n in ("profithelm-platform", "prexvo", "gainhelm")],
        key=lambda x: x[0],
    )
    assert local_ordered[0][1] <= local_ordered[1][0] + 0.05
    assert local_ordered[1][1] <= local_ordered[2][0] + 0.05
    # Cloud-hosted lienbond must start concurrently alongside the first local tenant (before local_ordered[0] ends)
    assert spans["lienbond"]["START"] < local_ordered[0][1]
    assert elapsed < 2.5

    # 2. Fail-closed check: if any tenant fails, function exits non-zero
    events_file.unlink()
    env_fail = env.copy()
    env_fail["FAIL_TENANT"] = "prexvo"
    res_fail = subprocess.run(["bash", str(harness)], env=env_fail, capture_output=True, text=True)
    assert res_fail.returncode != 0
    assert "FAIL: tenant 'prexvo'" in res_fail.stderr


def test_write_runtime_synchronizer_asset_thread_safe_concurrent_writes(tmp_path: Path):
    """Blocker #1 regression: 8 concurrent threads x 30 trials must produce 0 errors and 0 temp leftovers."""
    sha10 = get_runtime_synchronizer_js_sha10()
    expected_bytes = render_runtime_synchronizer_js().encode("utf-8")
    errors = []

    for trial in range(30):
        dist_dir = tmp_path / f"trial_{trial}"
        js_dir = dist_dir / "static" / "js"
        js_dir.mkdir(parents=True)
        (js_dir / "pseo-runtime-sync.0000000000.js").write_text("// stale\n", encoding="utf-8")

        def _worker(_idx: int, d: Path = dist_dir) -> Path:
            out_p, _ = write_runtime_synchronizer_asset(d)
            return out_p

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futs = [pool.submit(_worker, i) for i in range(8)]
            for fut in futs:
                try:
                    fut.result()
                except Exception as exc:
                    errors.append((trial, repr(exc)))

        final_f = js_dir / f"pseo-runtime-sync.{sha10}.js"
        assert final_f.is_file()
        assert final_f.read_bytes() == expected_bytes
        assert list(js_dir.glob("*.tmp")) == []
        assert not (js_dir / "pseo-runtime-sync.0000000000.js").exists()

    assert errors == [], f"Concurrent write_runtime_synchronizer_asset errors: {errors}"


def test_has_current_external_runtime_sync_tag_strict_html_parsing_edge_cases(tmp_path: Path):
    """
    Blocker #3 & Minor #5 regressions:
    - HTML-commented tag returns False
    - defer inside quoted attribute value returns False
    - type='text/plain' returns False; valid JS MIME types pass
    - data-id='pseo-runtime-sync' does not collide with real id or get stripped by porcelain_shell
    - src-before-id stale external tag is upgraded cleanly when dist_dir=None
    """
    src = get_runtime_synchronizer_script_src()
    canonical = render_external_runtime_synchronizer_tag()

    # 1. HTML comment must fail closed
    assert not has_current_external_runtime_sync_tag(f"<html><body><!-- {canonical} --></body></html>")

    # 2. defer inside quoted attr without real defer attr must fail closed
    fake_defer = (
        f'<script id="pseo-runtime-sync" data-version="{VISUAL_PRIMITIVES_VERSION}" '
        f'src="{src}" data-x="a defer b"></script>'
    )
    assert not has_current_external_runtime_sync_tag(f"<html><body>{fake_defer}</body></html>")
    fake_data_defer = (
        f'<script id="pseo-runtime-sync" data-version="{VISUAL_PRIMITIVES_VERSION}" '
        f'src="{src}" data-defer="true"></script>'
    )
    assert not has_current_external_runtime_sync_tag(f"<html><body>{fake_data_defer}</body></html>")

    # 3. Non-JS script type must fail closed; valid JS types must pass
    bad_type = (
        f'<script id="pseo-runtime-sync" data-version="{VISUAL_PRIMITIVES_VERSION}" '
        f'src="{src}" type="text/plain" defer></script>'
    )
    assert not has_current_external_runtime_sync_tag(f"<html><body>{bad_type}</body></html>")
    for valid_type in ("text/javascript", "application/javascript", "module"):
        good_type = (
            f'<script id="pseo-runtime-sync" data-version="{VISUAL_PRIMITIVES_VERSION}" '
            f'src="{src}" type="{valid_type}" defer></script>'
        )
        assert has_current_external_runtime_sync_tag(f"<html><body>{good_type}</body></html>")
    defer_eq = (
        f'<script id="pseo-runtime-sync" data-version="{VISUAL_PRIMITIVES_VERSION}" '
        f'src="{src}" defer="defer"></script>'
    )
    assert has_current_external_runtime_sync_tag(f"<html><body>{defer_eq}</body></html>")

    # 4. data-id='pseo-runtime-sync' must NOT count as a second #pseo-runtime-sync or be stripped
    data_id_only = (
        f'<script data-id="pseo-runtime-sync" data-version="{VISUAL_PRIMITIVES_VERSION}" '
        f'src="{src}" defer></script>'
    )
    assert not has_current_external_runtime_sync_tag(f"<html><body>{data_id_only}</body></html>")
    with_both = (
        f'<html><head><title>Test</title></head><body><main><h1>T</h1></main>'
        f'<script data-id="pseo-runtime-sync" type="application/json">{{}}</script>'
        f'{canonical}</body></html>'
    )
    assert has_current_external_runtime_sync_tag(with_both)
    profile = get_porcelain_tenant_profile("profithelm")
    norm_both, _ = normalize_html_to_porcelain_shell(with_both, "tools/demo/index.html", profile, dist_dir=None)
    assert 'data-id="pseo-runtime-sync"' in norm_both
    assert has_current_external_runtime_sync_tag(norm_both)

    # 5. Minor #5: src-before-id stale external tag upgrades cleanly even when dist_dir=None
    stale_src_first = (
        '<!DOCTYPE html><html lang="en"><head><title>Demo</title></head><body><main><h1>Demo</h1></main>'
        f'<script src="/static/js/pseo-runtime-sync.0123456789.js" id="pseo-runtime-sync" '
        f'data-version="{VISUAL_PRIMITIVES_VERSION}" defer></script></body></html>'
    )
    upgraded, _ = normalize_html_to_porcelain_shell(stale_src_first, "tools/demo/index.html", profile, dist_dir=None)
    assert has_current_external_runtime_sync_tag(upgraded)
    assert "pseo-runtime-sync.0123456789.js" not in upgraded


def test_audit_monetization_surfaces_checks_raw_on_disk_runtime_sync_fail_closed(tmp_path: Path):
    """Blocker #2 regression: audit_monetization_and_datapack_ui_ux_surfaces must NOT mask stale/deleted JS."""
    dist_dir = tmp_path / "dist"
    tool_dir = dist_dir / "tools" / "sample-calc"
    tool_dir.mkdir(parents=True)
    sha10 = get_runtime_synchronizer_js_sha10()
    write_runtime_synchronizer_asset(dist_dir)

    base_html = f"""<!DOCTYPE html>
<html lang="en"><head><title>Sample</title></head><body><main>
  <form id="lead-capture-form"><button type="submit">Send</button></form>
  <form id="partner-quote-intake-form"><button type="submit">Quote</button></form>
  <a href="/r/demo" class="touch-target">Partner</a>
  <a id="btn-post-calc-upgrade-checkout" data-checkout-trigger="1" class="touch-target" href="/checkout">Unlock</a>
  <button id="btn-preview-post-calc-workpaper" type="button">Preview</button>
  <button data-blueprint-action="save" type="button">Save</button>
  <button data-blueprint-action="share" type="button">Share</button>
  <button data-blueprint-action="export" type="button">Export</button>
  <button data-scenario-pin="A" type="button">A</button>
  <button data-scenario-pin="B" type="button">B</button>
  <button data-scenario-pin="reset" type="button">Reset</button>
  <button data-calc-preset="100" type="button">Preset</button>
</main>
{render_external_runtime_synchronizer_tag()}
</body></html>
"""
    tool_file = tool_dir / "index.html"
    tool_file.write_text(base_html, encoding="utf-8")

    # 1. Valid external tag + valid on-disk JS -> passes static runtime sync check while DOM simulation stays truthfully unverified
    rep_ok = audit_monetization_and_datapack_ui_ux_surfaces(
        dist_dirs={"profithelm": dist_dir / "tools"},
        execute_dom_simulation=False,
    )
    assert rep_ok["static_surfaces_passed"] is True
    assert rep_ok["coexistence_and_surface_violations"] == []
    assert rep_ok["dom_action_simulation"]["skipped"] is True
    assert rep_ok["dom_action_simulation"]["verified"] is False
    assert rep_ok["all_surfaces_and_handlers_passed"] is False

    # 2. Stale hash in on-disk HTML + deleted .js -> MUST fail with missing_upgraded_runtime_synchronizer
    stale_html = base_html.replace(f"pseo-runtime-sync.{sha10}.js", "pseo-runtime-sync.deadbeef00.js")
    tool_file.write_text(stale_html, encoding="utf-8")
    (dist_dir / "static" / "js" / f"pseo-runtime-sync.{sha10}.js").unlink()
    rep_stale = audit_monetization_and_datapack_ui_ux_surfaces(
        dist_dirs={"profithelm": dist_dir / "tools"},
        execute_dom_simulation=False,
    )
    assert rep_stale["static_surfaces_passed"] is False
    assert rep_stale["all_surfaces_and_handlers_passed"] is False
    assert any(
        "missing_upgraded_runtime_synchronizer" in v["issues"]
        for v in rep_stale["coexistence_and_surface_violations"]
    )

    # 3. HTML-commented runtime sync tag (even with valid on-disk .js) -> MUST fail
    write_runtime_synchronizer_asset(dist_dir)
    commented_html = base_html.replace(
        render_external_runtime_synchronizer_tag(),
        f"<!-- {render_external_runtime_synchronizer_tag()} -->",
    )
    tool_file.write_text(commented_html, encoding="utf-8")
    rep_commented = audit_monetization_and_datapack_ui_ux_surfaces(
        dist_dirs={"profithelm": dist_dir / "tools"},
        execute_dom_simulation=False,
    )
    assert rep_commented["static_surfaces_passed"] is False
    assert rep_commented["all_surfaces_and_handlers_passed"] is False
    assert any(
        "missing_upgraded_runtime_synchronizer" in v["issues"]
        for v in rep_commented["coexistence_and_surface_violations"]
    )


@pytest.mark.host_estate
def test_release_pipeline_wait_n_error_safe_under_set_u(tmp_path: Path):
    """Blocker #4 regression: wait -n -p done_pid error (unsetting done_pid) must not crash under set -euo pipefail."""
    pipeline_path = Path("/home/ubuntuadmin/projects/.agy/release_pipeline.sh")
    src = pipeline_path.read_text(encoding="utf-8")
    m_ref = re.search(r"run_parallel_tenant_reflect\(\) \{[\s\S]*?\n\}", src)
    m_cas = re.search(r"run_parallel_tenant_cascades\(\) \{[\s\S]*?\n\}", src)
    assert m_ref is not None and m_cas is not None
    assert 'if [[ -z "${done_pid:-}" ]]; then' in m_ref.group(0)
    assert 'if [[ -z "${done_pid:-}" ]]; then' in m_cas.group(0)

    # Directly exercise the exact _reap_one_reflect_worker / _reap_one_local_cascade guard with invalid PID 99999999
    probe = tmp_path / "wait_probe.sh"
    probe.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
active_pids=(99999999)
declare -A pid_to_idx=()
any_fail=0
done_pid=""
rc=0
wait -n -p done_pid "${active_pids[@]}" || rc=$?
if [[ -z "${done_pid:-}" ]]; then
  any_fail=1
  active_pids=()
fi
echo "rc=${rc} any_fail=${any_fail} remaining=${#active_pids[@]}"
""",
        encoding="utf-8",
    )
    res = subprocess.run(["bash", str(probe)], capture_output=True, text=True)
    assert res.returncode == 0, f"set -u crash on wait -n error: {res.stderr}"
    assert "any_fail=1 remaining=0" in res.stdout

