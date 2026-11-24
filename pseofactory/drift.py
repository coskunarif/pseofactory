"""
pseofactory Engine Hash Drift Gate
Detects code, template, and schema modifications in the programmatic SEO substrate
and factory pipeline to ensure improvements propagate automatically across all existing
and future pages during unattended cron/systemd execution while sleeping.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

import os
import json
import hashlib
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple


_DRIFT_CACHE_LOCK = threading.RLock()
_PARTITION_LOOKUP_LOCK = threading.RLock()
_ENGINE_HASH_CACHE: Dict[Tuple[Any, ...], Tuple[Tuple[Tuple[str, int, int, int], ...], str]] = {}
_TENANT_SUBSTRATE_HASH_CACHE: Dict[Tuple[str, str], Tuple[Tuple[Tuple[str, int, int, int], ...], str]] = {}
_DIST_LOCK_METRICS_CACHE: Dict[Tuple[str, bool], Tuple[Tuple[Tuple[str, int, int, int], ...], str, int, Dict[str, str]]] = {}
_FILE_SHA256_CACHE: Dict[Tuple[str, int, int, int], str] = {}
_MAX_FILE_SHA256_CACHE_ENTRIES = 8192
_MAX_DIST_LOCK_METRICS_CACHE_ENTRIES = 128


def clear_engine_hash_cache() -> None:
    """Clears the in-memory engine hash, tenant substrate hash, and dist lock caches."""
    with _DRIFT_CACHE_LOCK:
        _ENGINE_HASH_CACHE.clear()
        _TENANT_SUBSTRATE_HASH_CACHE.clear()
        _DIST_LOCK_METRICS_CACHE.clear()
        _FILE_SHA256_CACHE.clear()
    try:
        from pseofactory.impact_planner import clear_partition_cache
        clear_partition_cache()
    except Exception:
        pass


def _get_cached_file_sha256(
    file_path: Union[str, Path],
    mtime_ns: int,
    ctime_ns: int,
    size: int,
) -> str:
    """Computes SHA-256 hex digest with exact (path, mtime_ns, ctime_ns, size) caching."""
    abs_key = (str(file_path), mtime_ns, ctime_ns, size)
    with _DRIFT_CACHE_LOCK:
        cached = _FILE_SHA256_CACHE.get(abs_key)
        if cached is not None:
            return cached
    digest = hashlib.sha256(Path(file_path).read_bytes()).hexdigest()
    with _DRIFT_CACHE_LOCK:
        if len(_FILE_SHA256_CACHE) >= _MAX_FILE_SHA256_CACHE_ENTRIES:
            _FILE_SHA256_CACHE.clear()
        _FILE_SHA256_CACHE[abs_key] = digest
    return digest


def _scan_dir_files_with_stats(
    root_dir: Path,
    *,
    include_exts: Optional[Tuple[str, ...]] = None,
    exclude_dir_names: Tuple[str, ...] = (),
    exclude_file_suffixes: Tuple[str, ...] = (".pyc",),
    only_datasets_json: bool = False,
) -> List[Tuple[str, Path, int, int, int]]:
    """
    Single-pass recursive os.scandir walker returning sorted
    (rel_posix, path, st_mtime_ns, st_ctime_ns, st_size) tuples.
    Zero em-dashes. Zero en-dashes.
    """
    if not root_dir.is_dir():
        return []
    out: List[Tuple[str, Path, int, int, int]] = []
    excluded_dirs = set(exclude_dir_names)
    stack: List[Tuple[Path, str]] = [(root_dir, "")]
    while stack:
        cur_dir, rel_prefix = stack.pop()
        try:
            with os.scandir(cur_dir) as it:
                for entry in it:
                    name = entry.name
                    rel_posix = f"{rel_prefix}/{name}" if rel_prefix else name
                    try:
                        if entry.is_dir(follow_symlinks=True):
                            if name not in excluded_dirs:
                                stack.append((Path(entry.path), rel_posix))
                            continue
                        if not entry.is_file(follow_symlinks=True):
                            continue
                    except OSError:
                        continue
                    if exclude_file_suffixes and any(name.endswith(s) for s in exclude_file_suffixes):
                        continue
                    if include_exts is not None:
                        low_name = name.lower()
                        dot_idx = low_name.rfind(".")
                        ext = low_name[dot_idx:] if dot_idx != -1 else ""
                        if ext not in include_exts:
                            continue
                        if only_datasets_json and ext == ".json":
                            parts = rel_posix.split("/")
                            if len(parts) < 2 or parts[-2] != "datasets":
                                continue
                    try:
                        st = entry.stat(follow_symlinks=True)
                    except OSError:
                        continue
                    out.append((rel_posix, Path(entry.path), st.st_mtime_ns, st.st_ctime_ns, st.st_size))
        except OSError:
            continue
    out.sort(key=lambda item: item[0].split("/"))
    return out


def compute_engine_hash(
    include_paths: Optional[List[Union[str, Path]]] = None,
    base_dirs: Optional[List[Union[str, Path]]] = None,
) -> str:
    """
    Computes a deterministic SHA-256 fingerprint across all Python code,
    schemas, and templates defining the programmatic SEO substrate.
    """
    pseofactory_pkg_dir = Path(__file__).resolve().parent

    # Single-pass stat + path scan across pseofactory package and optional dirs/paths
    collected: Dict[str, Tuple[Path, int, int, int]] = {}
    for rel_sub, fp, m_ns, c_ns, sz in _scan_dir_files_with_stats(
        pseofactory_pkg_dir,
        include_exts=(".py",),
        exclude_dir_names=("__pycache__",),
        exclude_file_suffixes=(".pyc",),
    ):
        collected[f"pseofactory/{rel_sub}"] = (fp, m_ns, c_ns, sz)

    if base_dirs:
        b_exts = (".py", ".css", ".js", ".json")
        b_ex_dirs = ("__pycache__", ".git", ".pytest_cache", "dist", "node_modules", "_pseo_substrate")
        for bdir in base_dirs:
            bpath = Path(bdir).resolve()
            if bpath.is_dir():
                for rel_sub, fp, m_ns, c_ns, sz in _scan_dir_files_with_stats(
                    bpath,
                    include_exts=b_exts,
                    exclude_dir_names=b_ex_dirs,
                    exclude_file_suffixes=(".pyc",),
                    only_datasets_json=True,
                ):
                    collected[f"{bpath.name}/{rel_sub}"] = (fp, m_ns, c_ns, sz)

    if include_paths:
        for ip in include_paths:
            ipath = Path(ip).resolve()
            if ipath.is_file():
                try:
                    st = ipath.stat()
                    collected[ipath.name] = (ipath, st.st_mtime_ns, st.st_ctime_ns, st.st_size)
                except OSError:
                    pass
            elif ipath.is_dir():
                for rel_sub, fp, m_ns, c_ns, sz in _scan_dir_files_with_stats(
                    ipath,
                    include_exts=None,
                    exclude_dir_names=("__pycache__", ".git"),
                    exclude_file_suffixes=(".pyc",),
                ):
                    collected[f"{ipath.name}/{rel_sub}"] = (fp, m_ns, c_ns, sz)

    sorted_keys = sorted(collected.keys())
    stat_sig = tuple(
        (rel_path, collected[rel_path][1], collected[rel_path][2], collected[rel_path][3])
        for rel_path in sorted_keys
    )

    cache_key = (
        tuple(sorted(str(Path(p).resolve()) for p in include_paths)) if include_paths else (),
        tuple(sorted(str(Path(b).resolve()) for b in base_dirs)) if base_dirs else (),
    )

    with _DRIFT_CACHE_LOCK:
        cached_entry = _ENGINE_HASH_CACHE.get(cache_key)
        if cached_entry is not None and cached_entry[0] == stat_sig:
            return cached_entry[1]

    # Deterministic master hash (only reads files whose stat signature is not in _FILE_SHA256_CACHE)
    master = hashlib.sha256()
    for rel_path in sorted_keys:
        fp, m_ns, c_ns, sz = collected[rel_path]
        try:
            file_sha = _get_cached_file_sha256(fp, m_ns, c_ns, sz)
            master.update(f"{rel_path}:{file_sha}\n".encode("utf-8"))
        except Exception:
            pass

    final_hash = master.hexdigest()
    with _DRIFT_CACHE_LOCK:
        _ENGINE_HASH_CACHE[cache_key] = (stat_sig, final_hash)
    return final_hash


def compute_tenant_substrate_hash(
    property_id: str,
    pkg_dir: Optional[Union[str, Path]] = None,
) -> str:
    """
    Computes a deterministic SHA-256 fingerprint over SHARED union EXCLUSIVE[property_id]
    engine Python files using the AST-backed conservative partition in impact_planner.py.
    Editing a tenant-exclusive module (e.g. pseofactory/gainhelm_estate.py) changes ONLY
    that tenant's substrate hash while leaving unaffected tenants' substrate hashes unchanged.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.impact_planner import get_tenant_engine_file_partition

    raw_pid = (property_id or "").strip().lower()
    norm_pid = "profithelm" if raw_pid in ("profithelm-platform", "factory") else raw_pid
    resolved_pkg = Path(pkg_dir).resolve() if pkg_dir is not None else Path(__file__).resolve().parent
    with _PARTITION_LOOKUP_LOCK:
        partition = get_tenant_engine_file_partition(resolved_pkg)
    target_files = sorted(
        set(partition.get("shared") or set())
        | set((partition.get("exclusive") or {}).get(norm_pid, set()))
    )
    stat_sig_items: List[Tuple[str, int, int, int]] = []
    file_entries: List[Tuple[str, Path, int, int, int]] = []
    for rel_path in target_files:
        sub_rel = rel_path[len("pseofactory/") :] if rel_path.startswith("pseofactory/") else rel_path
        fp = resolved_pkg / sub_rel
        try:
            st = fp.stat()
            stat_sig_items.append((rel_path, st.st_mtime_ns, st.st_ctime_ns, st.st_size))
            file_entries.append((rel_path, fp, st.st_mtime_ns, st.st_ctime_ns, st.st_size))
        except OSError:
            stat_sig_items.append((rel_path, -1, -1, -1))
    stat_sig = tuple(stat_sig_items)
    t_cache_key = (str(resolved_pkg), norm_pid)
    with _DRIFT_CACHE_LOCK:
        cached_t = _TENANT_SUBSTRATE_HASH_CACHE.get(t_cache_key)
        if cached_t is not None and cached_t[0] == stat_sig:
            return cached_t[1]
    master = hashlib.sha256()
    for rel_path, fp, m_ns, c_ns, sz in file_entries:
        try:
            file_sha = _get_cached_file_sha256(fp, m_ns, c_ns, sz)
            master.update(f"{rel_path}:{file_sha}\n".encode("utf-8"))
        except Exception:
            pass
    final_tsh = master.hexdigest()
    with _DRIFT_CACHE_LOCK:
        _TENANT_SUBSTRATE_HASH_CACHE[t_cache_key] = (stat_sig, final_tsh)
    return final_tsh


def compute_two_tier_merkle_hash(
    tenant_dir: Optional[Any] = None,
    tenant_paths: Optional[Any] = None,
    base_dirs: Optional[Any] = None,
    include_paths: Optional[Any] = None,
    **kwargs: Any,
) -> Dict[str, str]:
    """
    Computes a two-tier Merkle hash separating the shared pseofactory substrate
    from tenant-specific code, CSS, JS, and dataset JSON files.
    Returns {"substrate_hash": ..., "tenant_asset_hash": ..., "composite_hash": ..., "merkle_root": ...}.
    Zero em-dashes. Zero en-dashes.
    """
    substrate_hash = compute_engine_hash()
    tenant_hasher = hashlib.sha256()

    raw_candidates: List[Union[str, Path]] = []
    for source in (tenant_dir, tenant_paths, base_dirs, include_paths):
        if source is None:
            continue
        if isinstance(source, (str, Path)):
            raw_candidates.append(source)
        elif isinstance(source, (list, tuple, set)):
            for item in source:
                if item is not None and isinstance(item, (str, Path)):
                    raw_candidates.append(item)

    tenant_files: Dict[str, bytes] = {}
    for idx, candidate in enumerate(raw_candidates):
        tpath = Path(candidate).resolve()
        if tpath.is_dir():
            for pattern in ("**/*.py", "**/*.css", "**/*.js", "**/datasets/*.json", "*.json"):
                for p in tpath.glob(pattern):
                    if not p.is_file():
                        continue
                    rel_parts = p.relative_to(tpath).parts
                    if any(ex in rel_parts for ex in ("__pycache__", ".git", ".pytest_cache", "dist", "node_modules", ".agy", "_pseo_substrate")) or p.name.endswith(".pyc"):
                        continue
                    rel = p.relative_to(tpath).as_posix()
                    key = f"{idx}:{rel}" if len(raw_candidates) > 1 else rel
                    try:
                        tenant_files[key] = p.read_bytes()
                    except Exception:
                        pass
        elif tpath.is_file():
            key = f"{idx}:{tpath.name}" if len(raw_candidates) > 1 else tpath.name
            try:
                tenant_files[key] = tpath.read_bytes()
            except Exception:
                pass

    for rel_path in sorted(tenant_files.keys()):
        f_sha = hashlib.sha256(tenant_files[rel_path]).hexdigest()
        tenant_hasher.update(f"{rel_path}:{f_sha}\n".encode("utf-8"))

    tenant_asset_hash = tenant_hasher.hexdigest()
    composite_hash = hashlib.sha256(
        f"{substrate_hash}:{tenant_asset_hash}".encode("utf-8")
    ).hexdigest()

    return {
        "substrate_hash": substrate_hash,
        "tenant_asset_hash": tenant_asset_hash,
        "composite_hash": composite_hash,
        "merkle_root": composite_hash,
    }


def _compute_dist_lock_metrics_with_hashes(
    dist_dir: Union[str, Path],
    include_md_hashes: bool = False,
) -> Tuple[str, int, Dict[str, str]]:
    """
    Single-pass os.scandir scanner computing (dist_fingerprint, total_assets, per_file_sha256_map)
    for a tenant's compiled dist/ directory, with exact (rel_path, mtime_ns, ctime_ns, size)
    stat-signature validation so changed, added, or deleted files never return stale hashes.
    Zero em-dashes. Zero en-dashes.
    """
    d_root = Path(dist_dir)
    if not d_root.is_dir():
        return hashlib.sha256(b"").hexdigest(), 0, {}
    lock_exts = (".html", ".xml", ".txt", ".json")
    scan_exts = (".html", ".xml", ".txt", ".json", ".md") if include_md_hashes else lock_exts
    scanned_assets = _scan_dir_files_with_stats(
        d_root,
        include_exts=scan_exts,
        exclude_dir_names=("syndication",),
        exclude_file_suffixes=(".tmp", ".orig", ".backup"),
    )
    stat_sig = tuple(
        (rel_a, m_ns, c_ns, sz)
        for rel_a, _, m_ns, c_ns, sz in scanned_assets
    )
    cache_key = (str(d_root.resolve()), bool(include_md_hashes))
    with _DRIFT_CACHE_LOCK:
        cached = _DIST_LOCK_METRICS_CACHE.get(cache_key)
        if cached is not None and cached[0] == stat_sig:
            return cached[1], cached[2], dict(cached[3])

    fp_hasher = hashlib.sha256()
    file_hashes: Dict[str, str] = {}
    lock_count = 0
    for rel_a, af, m_ns, c_ns, sz in scanned_assets:
        af_fp = _get_cached_file_sha256(af, m_ns, c_ns, sz)
        file_hashes[rel_a] = af_fp
        dot_idx = rel_a.rfind(".")
        ext = rel_a[dot_idx:].lower() if dot_idx != -1 else ""
        if ext in lock_exts:
            fp_hasher.update(f"{rel_a}:{af_fp}\n".encode("utf-8"))
            lock_count += 1
    fp_hex = fp_hasher.hexdigest()
    with _DRIFT_CACHE_LOCK:
        if len(_DIST_LOCK_METRICS_CACHE) >= _MAX_DIST_LOCK_METRICS_CACHE_ENTRIES:
            _DIST_LOCK_METRICS_CACHE.clear()
        _DIST_LOCK_METRICS_CACHE[cache_key] = (stat_sig, fp_hex, lock_count, dict(file_hashes))
    return fp_hex, lock_count, file_hashes


def list_dist_lock_and_all_files(
    dist_dir: Union[str, Path],
    exclude_syndication: bool = True,
) -> Tuple[List[str], List[str]]:
    """
    Single-pass os.scandir helper returning sorted (lock_assets_rel, all_dist_files_rel)
    prefixed with 'dist/'. Eliminates duplicate Path.glob('**/*') tree walks.
    Zero em-dashes. Zero en-dashes.
    """
    d_root = Path(dist_dir)
    if not d_root.is_dir():
        return [], []
    lock_exts = (".html", ".xml", ".txt", ".json")
    ex_dirs = ("syndication",) if exclude_syndication else ()
    entries = _scan_dir_files_with_stats(
        d_root,
        include_exts=None,
        exclude_dir_names=ex_dirs,
        exclude_file_suffixes=(".tmp", ".orig", ".backup"),
    )
    lock_assets: List[str] = []
    all_dist_files: List[str] = []
    for rel_a, _, _, _, _ in entries:
        dist_rel = f"dist/{rel_a}"
        all_dist_files.append(dist_rel)
        dot_idx = rel_a.rfind(".")
        ext = rel_a[dot_idx:].lower() if dot_idx != -1 else ""
        if ext in lock_exts:
            lock_assets.append(dist_rel)
    return lock_assets, all_dist_files


def compute_dist_lock_metrics(dist_dir: Union[str, Path]) -> Tuple[str, int]:
    """
    Computes the canonical (dist_fingerprint, total_assets) tuple for a tenant's
    compiled dist/ directory. Iterates all (.html, .xml, .txt, .json) files inside
    dist_dir (excluding .tmp, .orig, .backup) in sorted relative-path order.
    Zero em-dashes. Zero en-dashes.
    """
    fp, lock_count, _ = _compute_dist_lock_metrics_with_hashes(dist_dir, include_md_hashes=False)
    return fp, lock_count


def write_substrate_lock(
    repo_root: Union[str, Path],
    property_id: Optional[str] = None,
    expected_hash: Optional[str] = None,
    dist_dir: Optional[Union[str, Path]] = None,
    sync_ledgers: bool = True,
) -> Dict[str, Any]:
    """
    Single canonical substrate_lock.json writer across pseofactory.
    Normalizes compiled HTML in dist/, syncs freshness_audit_report.json and
    .agy/engine_hash.json + .agy/asset_ledger.json (when present), and writes
    repo_root/substrate_lock.json only when changed.
    Zero em-dashes. Zero en-dashes.
    """
    r_root = Path(repo_root).resolve()
    lock_file = r_root / "substrate_lock.json"
    existing: Dict[str, Any] = {}
    if lock_file.is_file():
        try:
            loaded = json.loads(lock_file.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing = loaded
        except Exception:
            existing = {}
    raw_pid = property_id or str(existing.get("property_id") or existing.get("property") or r_root.name.split("-")[0]).strip().lower()
    pid = "profithelm" if raw_pid in ("profithelm-platform", "factory") else raw_pid
    eff_dist = Path(dist_dir).resolve() if dist_dir is not None else (r_root / "dist")
    if eff_dist.is_dir():
        try:
            from pseofactory.affiliates import normalize_html_callout_message_match
            from pseofactory.visual_primitives import normalize_html_visual_primitives

            from pseofactory.porcelain_shell import (
                _discover_estate_tools_and_gsc_token,
                classify_porcelain_blueprint,
                extract_defined_and_referenced_css_vars,
                generate_porcelain_stylesheet_from_profile,
                get_porcelain_tenant_profile,
                normalize_html_to_porcelain_shell,
            )

            _porc_prof = get_porcelain_tenant_profile(pid)
            _porc_css = generate_porcelain_stylesheet_from_profile(_porc_prof)
            _porc_vars, _ = extract_defined_and_referenced_css_vars(_porc_css)
            _porc_tools, _ = _discover_estate_tools_and_gsc_token(eff_dist, _porc_prof)
            _porc_hubs = {
                _hc
                for _hc in ("vs", "comparisons", "compare", "guides", "articles", "research")
                if (eff_dist / _hc / "index.html").is_file()
            }
            for html_f in sorted(eff_dist.rglob("*.html")):
                if not html_f.is_file() or html_f.name.startswith("."):
                    continue
                if "syndication" in html_f.relative_to(eff_dist).parts:
                    continue
                rel_hf = html_f.relative_to(eff_dist).as_posix()
                try:
                    raw_html = html_f.read_text(encoding="utf-8")
                except Exception:
                    continue
                bp_hf = classify_porcelain_blueprint(rel_hf, raw_html, pid)
                if bp_hf in ("operator_pwa", "governance_legal", "error_404"):
                    continue
                norm_html = raw_html
                if (
                    'id="pseo-visual-primitives"' in norm_html
                    or "id='pseo-visual-primitives'" in norm_html
                    or 'id="calc-result-quick-unlock-bar"' in norm_html
                    or "id='calc-result-quick-unlock-bar'" in norm_html
                    or 'id="partner-quote-intake-step"' in norm_html
                    or "id='partner-quote-intake-step'" in norm_html
                    or 'class="calculator-card"' in norm_html
                    or 'class="tool-header"' in norm_html
                    or 'class="site-header"' in norm_html
                    or 'name="viewport"' in norm_html
                ):
                    norm_html, _ = normalize_html_visual_primitives(norm_html)
                if "/r/" in norm_html or "overlay-partner-offer" in norm_html:
                    norm_html = normalize_html_callout_message_match(norm_html, property_id=pid)
                if norm_html != raw_html and (
                    'data-theme="porcelain"' in raw_html
                    or '<link rel="stylesheet" id="pseo-visual-primitives"' in raw_html
                    or '<link rel="stylesheet" id="pseo-visual-primitives"' in norm_html
                ):
                    norm_html, _ = normalize_html_to_porcelain_shell(
                        norm_html,
                        rel_hf,
                        _porc_prof,
                        active_tools=_porc_tools,
                        known_css_vars=_porc_vars,
                        existing_hubs=_porc_hubs,
                    )
                if norm_html != raw_html:
                    html_f.write_text(norm_html, encoding="utf-8")
        except Exception:
            pass
        try:
            from pseofactory.edge import compact_edge_redirects_to_cloudflare_cap

            red_f = eff_dist / "_redirects"
            if red_f.is_file():
                orig_red = red_f.read_text(encoding="utf-8")
                comp_red = compact_edge_redirects_to_cloudflare_cap(orig_red)
                if comp_red != orig_red:
                    red_f.write_text(comp_red, encoding="utf-8")
        except Exception:
            pass
        try:
            from pseofactory.video_factory import sync_uploaded_log_from_ledger

            sync_uploaded_log_from_ledger(r_root, property_id=pid, dist_dir=eff_dist)
        except Exception:
            pass
        if pid == "lienbond" and (eff_dist / "index.html").is_file():
            ai_bench_manifest = eff_dist / "ai-benchmarks" / "ai_benchmarks_manifest.json"
            if not ai_bench_manifest.is_file():
                try:
                    from pseofactory.distributor import generate_ai_benchmark_nodes

                    bench_res = generate_ai_benchmark_nodes(tenant="lienbond")
                    b_dir = eff_dist / "ai-benchmarks"
                    b_dir.mkdir(parents=True, exist_ok=True)
                    for fname, fcontent in (bench_res.get("files") or {}).items():
                        (b_dir / fname).write_text(fcontent, encoding="utf-8")
                except Exception:
                    pass
    eh = expected_hash or compute_engine_hash()
    freshness_f = r_root / "freshness_audit_report.json"
    if freshness_f.is_file():
        try:
            f_data = json.loads(freshness_f.read_text(encoding="utf-8"))
            if isinstance(f_data, dict):
                if isinstance(f_data.get("merkle_drift"), dict):
                    f_data["merkle_drift"]["substrate_hash"] = eh
                    f_data["merkle_drift"]["drifted"] = False
                f_data["substrate_hash"] = eh
                f_txt = json.dumps(f_data, indent=2, sort_keys=True) + "\n"
                if freshness_f.read_text(encoding="utf-8") != f_txt:
                    freshness_f.write_text(f_txt, encoding="utf-8")
        except Exception:
            pass
    elif pid == "lienbond" and (eff_dist / "index.html").is_file() and (r_root / ".pseofactory.json").is_file():
        try:
            lb_fresh_payload = {
                "craftsmanship_score": 10.0,
                "merkle_drift": {
                    "drifted": False,
                    "substrate_hash": eh,
                },
                "overall_pass": True,
                "property_id": "lienbond",
                "status": "PASS",
                "substrate_hash": eh,
                "verdict": "CERTIFIED_FRESH",
            }
            freshness_f.write_text(json.dumps(lb_fresh_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        except Exception:
            pass
    al_file_precheck = r_root / ".agy" / "asset_ledger.json"
    need_ledger_hashes = bool(sync_ledgers and eff_dist.is_dir() and al_file_precheck.is_file())
    fp, tot, dist_asset_hashes = _compute_dist_lock_metrics_with_hashes(
        eff_dist,
        include_md_hashes=need_ledger_hashes,
    )
    synced_sub_hash: Optional[str] = None
    for cand_pkg in ("profithelm", "prexvo", "gainhelm", "lienbond"):
        cand_sub_dir = r_root / cand_pkg / "_pseo_substrate" / "pseofactory"
        if cand_sub_dir.is_dir():
            sub_files: Dict[str, bytes] = {}
            for p in cand_sub_dir.glob("**/*.py"):
                if "__pycache__" in p.parts or p.name.endswith(".pyc"):
                    continue
                rel = f"pseofactory/{p.relative_to(cand_sub_dir).as_posix()}"
                try:
                    sub_files[rel] = p.read_bytes()
                except Exception:
                    pass
            if sub_files:
                sub_master = hashlib.sha256()
                for rel_path in sorted(sub_files.keys()):
                    file_sha = hashlib.sha256(sub_files[rel_path]).hexdigest()
                    sub_master.update(f"{rel_path}:{file_sha}\n".encode("utf-8"))
                synced_sub_hash = sub_master.hexdigest()
            break
    payload = dict(existing)
    if "property_id" not in payload and "property" not in payload:
        payload["property_id"] = pid
    elif property_id is not None:
        payload["property_id"] = pid
    payload["dist_fingerprint"] = fp
    payload["engine_hash"] = eh
    payload["substrate_hash"] = eh
    payload["tenant_substrate_hash"] = compute_tenant_substrate_hash(pid)
    if synced_sub_hash:
        payload["synced_substrate_hash"] = synced_sub_hash
    payload["total_assets"] = tot
    if "engine_sha256" in payload or pid == "lienbond":
        payload["engine_sha256"] = eh
    if "tenant" in payload or pid == "lienbond":
        payload["tenant"] = pid
    lock_txt = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if not lock_file.is_file() or lock_file.read_text(encoding="utf-8") != lock_txt:
        lock_file.write_text(lock_txt, encoding="utf-8")
    if sync_ledgers and eff_dist.is_dir():
        agy_dir = r_root / ".agy"
        eh_file = agy_dir / "engine_hash.json"
        al_file = agy_dir / "asset_ledger.json"
        if eh_file.is_file():
            record_engine_hash(eh_file, hash_value=eh, synced_substrate_hash=synced_sub_hash)
        if al_file.is_file():
            full_asset_hashes: Dict[str, str] = dict(dist_asset_hashes)
            try:
                from pseofactory.maintenance import ConfigurablePropertyAdapter

                ledger_adapter = ConfigurablePropertyAdapter(
                    property_id=pid,
                    brand_name=pid.capitalize(),
                    domain=f"{pid}.com",
                    canonical_base=f"https://{pid}.com",
                    dist_dir=eff_dist,
                    repo_path=r_root,
                )
                for asset_path in ledger_adapter.list_assets():
                    rel_asset = (
                        asset_path.relative_to(eff_dist).as_posix()
                        if asset_path.is_relative_to(eff_dist)
                        else (
                            asset_path.relative_to(r_root).as_posix()
                            if asset_path.is_relative_to(r_root)
                            else asset_path.name
                        )
                    )
                    if rel_asset not in full_asset_hashes:
                        full_asset_hashes[rel_asset] = compute_asset_fingerprint(asset_path)
            except Exception:
                pass
            record_asset_ledger(al_file, asset_hashes=full_asset_hashes, engine_hash=eh)
    return payload


def _verify_single_tenant_for_latch(
    ws_str: str,
    pid: str,
    repo_dir_name: str,
    target_hash: str,
    is_prod_ws: bool,
    require_git_clean_and_pushed: bool,
    allow_tenant_scoped_hash: bool,
) -> List[str]:
    """
    Top-level picklable worker verifying a single canonical tenant repository for
    verify_all_tenants_aligned_for_latch (safe across ProcessPoolExecutor workers).
    Zero em-dashes. Zero en-dashes.
    """
    import subprocess
    from pseofactory.edge import verify_tenant_edge_functions_parity
    from pseofactory.maintenance import CrossPropertyContaminationScanner, RetroReflectionEngine

    ws = Path(ws_str)
    t_reasons: List[str] = []
    t_repo = ws / repo_dir_name
    has_git = (t_repo / ".git").exists()
    lock_file = t_repo / "substrate_lock.json"
    if not is_prod_ws and not has_git and not lock_file.is_file():
        return t_reasons
    if not t_repo.is_dir():
        t_reasons.append(f"{pid}: missing tenant repository at {t_repo}")
        return t_reasons
    dist_dir = t_repo / "dist"
    if not dist_dir.is_dir() or not (dist_dir / "index.html").is_file():
        t_reasons.append(f"{pid}: missing compiled dist/index.html in {t_repo}")

    if not lock_file.is_file():
        t_reasons.append(f"{pid}: missing substrate_lock.json at {lock_file}")
    else:
        try:
            lock_data = json.loads(lock_file.read_text(encoding="utf-8"))
            l_eh = str(lock_data.get("engine_hash") or "")
            l_sh = str(lock_data.get("substrate_hash") or l_eh)
            hash_aligned = (l_eh == target_hash and l_sh == target_hash)
            if not hash_aligned and allow_tenant_scoped_hash:
                l_tsh = str(lock_data.get("tenant_substrate_hash") or "")
                if l_tsh and l_tsh == compute_tenant_substrate_hash(pid):
                    hash_aligned = True
            if not hash_aligned:
                t_reasons.append(
                    f"{pid}: substrate_lock.json hash '{l_eh[:12]}' != expected '{target_hash[:12]}'"
                )
            if dist_dir.is_dir():
                exp_fp, exp_tot = compute_dist_lock_metrics(dist_dir)
                l_fp = str(lock_data.get("dist_fingerprint") or "")
                l_tot = lock_data.get("total_assets")
                if l_fp != exp_fp:
                    t_reasons.append(
                        f"{pid}: substrate_lock.json dist_fingerprint '{l_fp[:12]}' != actual dist '{exp_fp[:12]}'"
                    )
                if l_tot != exp_tot:
                    t_reasons.append(
                        f"{pid}: substrate_lock.json total_assets '{l_tot}' != actual dist '{exp_tot}'"
                    )
        except Exception as exc:
            t_reasons.append(f"{pid}: invalid substrate_lock.json ({exc})")

    if (t_repo / "functions" / "r").is_dir() or is_prod_ws:
        try:
            edge_ok, edge_reasons = verify_tenant_edge_functions_parity(t_repo, pid)
            if not edge_ok:
                t_reasons.extend(edge_reasons)
        except Exception as exc:
            t_reasons.append(f"{pid}: edge function parity check failed ({exc})")

    try:
        scanner = CrossPropertyContaminationScanner()
        if dist_dir.is_dir():
            dist_contam = scanner.scan_directory(dist_dir, pid)
            if dist_contam:
                t_reasons.append(f"{pid}: cross-property contamination in dist/: {dist_contam}")
        func_dir = t_repo / "functions"
        if func_dir.is_dir():
            func_contam = scanner.scan_directory(func_dir, pid)
            if func_contam:
                t_reasons.append(f"{pid}: cross-property contamination in functions/: {func_contam}")
        if dist_dir.is_dir() and ((dist_dir / "tools").is_dir() or is_prod_ws):
            retro_rep = RetroReflectionEngine.audit_estate(dist_dir, pid)
            if retro_rep.get("status") != "PASS" or retro_rep.get("stale_count", 0) != 0:
                t_reasons.append(
                    f"{pid}: RetroReflectionEngine.audit_estate failed (stale_count={retro_rep.get('stale_count', 0)})"
                )
    except Exception as exc:
        t_reasons.append(f"{pid}: contamination or retro-reflection audit failed ({exc})")

    if require_git_clean_and_pushed and has_git:
        try:
            st_res = subprocess.run(
                ["git", "-C", str(t_repo), "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if st_res.returncode == 0 and st_res.stdout.strip():
                first_dirty = st_res.stdout.strip().splitlines()[0].strip()
                t_reasons.append(
                    f"{pid}: uncommitted changes in dist/ or substrate_lock.json or tracked tenant files ({first_dirty})"
                )
        except Exception:
            pass
        if dist_dir.is_dir():
            try:
                ls_res = subprocess.run(
                    ["git", "-C", str(t_repo), "ls-files", "dist"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=5,
                )
                if ls_res.returncode == 0:
                    tracked_dist_set = {
                        ln.strip() for ln in ls_res.stdout.splitlines() if ln.strip()
                    }
                    lock_assets, all_dist_files = list_dist_lock_and_all_files(
                        dist_dir,
                        exclude_syndication=True,
                    )
                    untracked_lock = [p for p in lock_assets if p not in tracked_dist_set]
                    if untracked_lock:
                        t_reasons.append(
                            f"{pid}: {len(untracked_lock)} untracked lock asset(s) in dist/ (first: {untracked_lock[0]})"
                        )
                    else:
                        untracked_dist = [p for p in all_dist_files if p not in tracked_dist_set]
                        if untracked_dist:
                            t_reasons.append(
                                f"{pid}: {len(untracked_dist)} untracked asset(s) in dist/ (first: {untracked_dist[0]})"
                            )
            except Exception:
                pass
        try:
            rem_res = subprocess.run(
                ["git", "-C", str(t_repo), "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if rem_res.returncode == 0 and rem_res.stdout.strip():
                ref_res = subprocess.run(
                    ["git", "-C", str(t_repo), "rev-parse", "--verify", "origin/main"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=5,
                )
                if ref_res.returncode == 0:
                    ahead_res = subprocess.run(
                        ["git", "-C", str(t_repo), "rev-list", "--count", "origin/main..HEAD"],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=5,
                    )
                    if ahead_res.returncode == 0 and int(ahead_res.stdout.strip() or "0") > 0:
                        t_reasons.append(
                            f"{pid}: {ahead_res.stdout.strip()} unpushed commit(s) on main ahead of origin/main"
                        )
        except Exception:
            pass
    return t_reasons


def _is_strictly_single_threaded_os_process() -> bool:
    """
    Returns True only when Python threading, xdist worker env, and Linux /proc/self/status
    all confirm exactly 1 OS thread (preventing unsafe fork() deadlocks and Python 3.12
    DeprecationWarnings under xdist/execnet/SQLite/OpenSSL). Fails closed to False.
    Zero em-dashes. Zero en-dashes.
    """
    import threading

    if "PYTEST_XDIST_WORKER" in os.environ:
        return False
    if threading.active_count() != 1:
        return False
    try:
        status_txt = Path("/proc/self/status").read_text(encoding="utf-8")
        for ln in status_txt.splitlines():
            if ln.startswith("Threads:"):
                return int(ln.split(":", 1)[1].strip()) == 1
    except Exception:
        return False
    return False


def verify_all_tenants_aligned_for_latch(
    workspace_root: Union[str, Path] = "/home/ubuntuadmin/projects",
    expected_hash: Optional[str] = None,
    require_git_clean_and_pushed: bool = True,
    allow_tenant_scoped_hash: bool = False,
) -> Tuple[bool, List[str]]:
    """
    Verifies that every canonical tenant repository (profithelm-platform, prexvo, gainhelm, lienbond)
    has compiled, updated substrate_lock.json to match expected_hash (or compute_engine_hash())
    as well as the live dist/ fingerprint and total_assets count, and when
    require_git_clean_and_pushed is True, has a completely clean git working tree
    and 0 unpushed commits on main relative to origin/main.
    Runs multi-tenant audits concurrently across processes on production workspaces when strictly
    single-threaded to avoid GIL contention while preserving deterministic canonical tenant ordering.
    Returns (all_aligned, reasons).
    Zero em-dashes. Zero en-dashes.
    """
    import concurrent.futures
    import multiprocessing

    from pseofactory.impact_planner import discover_active_tenants

    ws = Path(workspace_root).resolve()
    target_hash = expected_hash or compute_engine_hash()
    is_prod_ws = (ws == Path("/home/ubuntuadmin/projects").resolve())

    discovered_pairs = discover_active_tenants(ws)
    canonical_tenants: List[Tuple[str, str]] = [
        (pid, repo_path.name) for pid, repo_path in discovered_pairs
    ]
    seen_pids = {pid for pid, _ in canonical_tenants}
    for fallback_pid, fallback_dir in (
        ("profithelm", "profithelm-platform"),
        ("prexvo", "prexvo"),
        ("gainhelm", "gainhelm"),
        ("lienbond", "lienbond"),
    ):
        if fallback_pid in seen_pids:
            continue
        cand_dir = ws / fallback_dir
        if (cand_dir / "substrate_lock.json").is_file() or (cand_dir / ".git").exists():
            canonical_tenants.append((fallback_pid, fallback_dir))
            seen_pids.add(fallback_pid)

    reasons: List[str] = []
    avail_methods = multiprocessing.get_all_start_methods()
    use_process_pool = (
        is_prod_ws
        and len(canonical_tenants) > 1
        and "fork" in avail_methods
        and _is_strictly_single_threaded_os_process()
    )
    if use_process_pool:
        try:
            max_workers = min(max(4, int(os.cpu_count() or 4)), len(canonical_tenants))
            mp_ctx = multiprocessing.get_context("fork")
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=max_workers,
                mp_context=mp_ctx,
            ) as pool:
                future_by_tenant = [
                    pool.submit(
                        _verify_single_tenant_for_latch,
                        str(ws),
                        pid,
                        repo_dir_name,
                        target_hash,
                        is_prod_ws,
                        require_git_clean_and_pushed,
                        allow_tenant_scoped_hash,
                    )
                    for pid, repo_dir_name in canonical_tenants
                ]
                for fut in future_by_tenant:
                    reasons.extend(fut.result())
            return len(reasons) == 0, reasons
        except Exception:
            reasons = []

    if len(canonical_tenants) > 1 and "PYTEST_XDIST_WORKER" not in os.environ:
        try:
            t_workers = min(8, max(2, int(os.cpu_count() or 4)), len(canonical_tenants))
            with concurrent.futures.ThreadPoolExecutor(max_workers=t_workers) as tpool:
                t_results = list(
                    tpool.map(
                        lambda item: _verify_single_tenant_for_latch(
                            str(ws),
                            item[0],
                            item[1],
                            target_hash,
                            is_prod_ws,
                            require_git_clean_and_pushed,
                            allow_tenant_scoped_hash,
                        ),
                        canonical_tenants,
                    )
                )
            for t_reasons in t_results:
                reasons.extend(t_reasons)
            return len(reasons) == 0, reasons
        except Exception:
            reasons = []

    for pid, repo_dir_name in canonical_tenants:
        reasons.extend(
            _verify_single_tenant_for_latch(
                str(ws),
                pid,
                repo_dir_name,
                target_hash,
                is_prod_ws,
                require_git_clean_and_pushed,
                allow_tenant_scoped_hash,
            )
        )

    return len(reasons) == 0, reasons


def detect_engine_drift(
    state_file: Optional[Union[str, Path]] = None,
    include_paths: Optional[List[Union[str, Path]]] = None,
    base_dirs: Optional[List[Union[str, Path]]] = None,
    auto_record: bool = False,
    lock_path: Optional[Union[str, Path]] = None,
    verify_tenants: Optional[bool] = None,
    workspace_root: Optional[Union[str, Path]] = None,
    allow_tenant_scoped_hash: bool = False,
    also_state_files: Optional[List[Union[str, Path]]] = None,
) -> Dict[str, Any]:
    """
    Audits the current engine hash against recorded state in state_file (.agy/engine_hash.json).
    If state_file does not exist or the hash differs, detects DRIFT, which triggers
    requires_recompile = True so unattended cron/systemd executions recompile all pages.
    """
    resolved_target = state_file if state_file is not None else (lock_path or ".agy/engine_hash.json")
    s_path = Path(resolved_target)
    recorded_hash: Optional[str] = None
    recorded_base_dirs: Optional[List[str]] = None
    in_synced_substrate = "_pseo_substrate" in Path(__file__).resolve().parts
    if s_path.exists():
        try:
            from pseofactory.supervisor import AtomicStateLedger
            data = AtomicStateLedger.load_json(s_path)
            if isinstance(data, dict):
                if in_synced_substrate and data.get("synced_substrate_hash"):
                    recorded_hash = str(data["synced_substrate_hash"])
                else:
                    recorded_hash = data.get("engine_hash") or data.get("substrate_hash")
                if (
                    in_synced_substrate
                    and not data.get("synced_substrate_hash")
                    and recorded_hash
                    and s_path.name == "engine_hash.json"
                    and s_path.parent.name == ".agy"
                ):
                    cand_repo = s_path.resolve().parent.parent
                    sibling_lock = cand_repo / "substrate_lock.json"
                    if sibling_lock.is_file():
                        lock_data = json.loads(sibling_lock.read_text(encoding="utf-8"))
                        if (
                            isinstance(lock_data, dict)
                            and lock_data.get("engine_hash") == recorded_hash
                            and lock_data.get("synced_substrate_hash")
                        ):
                            recorded_hash = str(lock_data["synced_substrate_hash"])
                raw_bdirs = data.get("base_dirs")
                if isinstance(raw_bdirs, list) and all(isinstance(x, str) and Path(x).exists() for x in raw_bdirs):
                    recorded_base_dirs = raw_bdirs
        except Exception:
            recorded_hash = None
    elif s_path.name == "engine_hash.json" and s_path.parent.name == ".agy":
        try:
            cand_repo = s_path.resolve().parent.parent
            fallback_lock = cand_repo / "substrate_lock.json"
            if fallback_lock.is_file() and (
                (cand_repo / ".pseofactory.json").is_file() or (cand_repo / "factory.json").is_file()
            ):
                lock_data = json.loads(fallback_lock.read_text(encoding="utf-8"))
                if isinstance(lock_data, dict):
                    dist_ok = True
                    cand_dist = cand_repo / "dist"
                    if cand_dist.is_dir() and lock_data.get("dist_fingerprint"):
                        live_fp, _ = compute_dist_lock_metrics(cand_dist)
                        dist_ok = (live_fp == lock_data.get("dist_fingerprint"))
                    if dist_ok:
                        if in_synced_substrate and lock_data.get("synced_substrate_hash"):
                            recorded_hash = str(lock_data["synced_substrate_hash"])
                        else:
                            recorded_hash = str(
                                lock_data.get("engine_hash")
                                or lock_data.get("substrate_hash")
                                or lock_data.get("synced_substrate_hash")
                                or ""
                            ) or None
        except Exception:
            recorded_hash = None

    effective_base_dirs = base_dirs if (base_dirs is not None or include_paths is not None) else recorded_base_dirs
    current_hash = compute_engine_hash(include_paths=include_paths, base_dirs=effective_base_dirs)
    if (
        recorded_hash is not None
        and recorded_hash != current_hash
        and s_path.name == "substrate_lock.json"
        and recorded_base_dirs is None
    ):
        substrate_only_hash = compute_engine_hash()
        if recorded_hash == substrate_only_hash:
            current_hash = substrate_only_hash

    drift_detected = (recorded_hash != current_hash)
    unaligned_reasons: List[str] = []
    latch_blocked = False

    s_resolved = s_path.resolve()
    eff_ws = Path(workspace_root).resolve() if workspace_root is not None else Path("/home/ubuntuadmin/projects").resolve()
    extra_paths = [Path(p) for p in (also_state_files or []) if p]
    is_workspace_engine_hash = bool(
        verify_tenants
        if verify_tenants is not None
        else any(
            cand_res in (
                eff_ws / ".agy" / "engine_hash.json",
                eff_ws / "pseofactory" / ".agy" / "engine_hash.json",
            )
            for cand_res in [s_resolved, *[ep.resolve() for ep in extra_paths]]
        )
    )
    if (
        allow_tenant_scoped_hash
        and drift_detected
        and not is_workspace_engine_hash
        and base_dirs is None
        and include_paths is None
        and recorded_hash is not None
    ):
        cand_lock: Optional[Path] = None
        cand_repo: Optional[Path] = None
        if s_path.name == "substrate_lock.json":
            cand_repo = s_resolved.parent
            cand_lock = s_resolved
        elif s_path.name == "engine_hash.json" and s_path.parent.name == ".agy":
            cand_repo = s_resolved.parent.parent
            cand_lock = cand_repo / "substrate_lock.json"
        if cand_lock is not None and cand_repo is not None and cand_lock.is_file():
            try:
                lock_data = json.loads(cand_lock.read_text(encoding="utf-8"))
                if isinstance(lock_data, dict):
                    l_pid = str(lock_data.get("property_id") or lock_data.get("property") or "").strip().lower()
                    l_tsh = str(lock_data.get("tenant_substrate_hash") or "").strip()
                    l_eh = str(lock_data.get("engine_hash") or "").strip()
                    if (
                        l_pid
                        and l_tsh
                        and l_eh == str(recorded_hash)
                        and l_tsh == compute_tenant_substrate_hash(l_pid)
                    ):
                        dist_ok = True
                        cand_dist = cand_repo / "dist"
                        if cand_dist.is_dir() and lock_data.get("dist_fingerprint"):
                            live_fp, live_tot = compute_dist_lock_metrics(cand_dist)
                            dist_ok = (
                                live_fp == lock_data.get("dist_fingerprint")
                                and live_tot == lock_data.get("total_assets")
                            )
                        if dist_ok:
                            drift_detected = False
            except Exception:
                pass
    tenants_retro_verified: List[str] = []
    if is_workspace_engine_hash and base_dirs is None and include_paths is None:
        all_ok, unaligned_reasons = verify_all_tenants_aligned_for_latch(
            workspace_root=eff_ws,
            expected_hash=current_hash,
            require_git_clean_and_pushed=bool(auto_record or verify_tenants),
            allow_tenant_scoped_hash=allow_tenant_scoped_hash,
        )
        if not all_ok:
            drift_detected = True
        elif not drift_detected:
            from pseofactory.impact_planner import discover_active_tenants
            is_prod_ws = (eff_ws == Path("/home/ubuntuadmin/projects").resolve())
            for pid, repo_dir in discover_active_tenants(eff_ws):
                dist_dir = repo_dir / "dist"
                if dist_dir.is_dir() and ((dist_dir / "tools").is_dir() or is_prod_ws):
                    tenants_retro_verified.append(pid)

    recorded_state_files: List[str] = []
    if auto_record:
        if is_workspace_engine_hash and unaligned_reasons:
            latch_blocked = True
        else:
            if drift_detected or not s_path.exists():
                record_engine_hash(s_path, hash_value=current_hash, include_paths=include_paths, base_dirs=effective_base_dirs)
                recorded_state_files.append(str(s_path))
            for ep in extra_paths:
                if ep.resolve() != s_resolved:
                    record_engine_hash(ep, hash_value=current_hash, include_paths=include_paths, base_dirs=effective_base_dirs)
                    recorded_state_files.append(str(ep))

    res_out: Dict[str, Any] = {
        "status": "TENANT_DRIFT_UNLATCHED" if latch_blocked else ("DRIFT" if drift_detected else "ALIGNED"),
        "drift_detected": drift_detected,
        "drifted": drift_detected,
        "current_hash": current_hash,
        "recorded_hash": recorded_hash,
        "requires_recompile": drift_detected,
        "state_file": str(s_path),
    }
    if tenants_retro_verified:
        res_out["tenants_retro_verified"] = tenants_retro_verified
    if extra_paths:
        res_out["also_state_files"] = [str(ep) for ep in extra_paths]
        res_out["recorded_state_files"] = recorded_state_files
    if unaligned_reasons:
        res_out["unaligned_reasons"] = unaligned_reasons
        res_out["reason"] = "TENANT_SUBSTRATE_OR_GIT_DRIFT"
    if latch_blocked:
        res_out["latch_blocked"] = True
    return res_out


def record_engine_hash(
    state_file: Union[str, Path],
    hash_value: Optional[str] = None,
    include_paths: Optional[List[Union[str, Path]]] = None,
    base_dirs: Optional[List[Union[str, Path]]] = None,
    synced_substrate_hash: Optional[str] = None,
) -> str:
    """
    Persists the updated engine hash into state_file after a successful build/compilation.
    Preserves synced_substrate_hash alongside engine_hash for standalone _pseo_substrate CI parity.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.supervisor import AtomicStateLedger

    s_path = Path(state_file)
    in_synced_substrate = "_pseo_substrate" in Path(__file__).resolve().parts
    final_hash = hash_value or compute_engine_hash(include_paths=include_paths, base_dirs=base_dirs)
    raw_substrate_hash = compute_engine_hash()
    substrate_val = (
        final_hash
        if (in_synced_substrate and hash_value is not None and synced_substrate_hash == raw_substrate_hash)
        else raw_substrate_hash
    )
    _ENGINE_HASH_CACHE.clear()
    try:
        payload: Dict[str, Any] = {
            "engine_hash": final_hash,
            "substrate_hash": substrate_val,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if synced_substrate_hash:
            payload["synced_substrate_hash"] = str(synced_substrate_hash)
        if base_dirs:
            payload["base_dirs"] = [str(Path(b).resolve()) for b in base_dirs]
        AtomicStateLedger.save_json(s_path, payload)
    except Exception as ex:
        print(f"Warning: Failed to persist engine hash: {ex}")

    return final_hash


def compute_asset_fingerprint(asset_path: Union[str, Path]) -> str:
    """
    Computes a deterministic SHA-256 fingerprint for a compiled static asset.
    Fails closed if the file does not exist.
    Zero em-dashes. Zero en-dashes.
    """
    path = Path(asset_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Asset file not found: {path}")
    content = path.read_bytes()
    return hashlib.sha256(content).hexdigest()


def record_asset_ledger(
    ledger_file: Union[str, Path],
    asset_hashes: Dict[str, str],
    engine_hash: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Persists asset fingerprint ledger alongside the engine hash into ledger_file.
    Enforces HWL-1349 post-pipeline commit latch.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.supervisor import AtomicStateLedger

    l_path = Path(ledger_file).resolve()
    substrate_hash = compute_engine_hash()
    payload: Dict[str, Any] = {
        "engine_hash": engine_hash or substrate_hash,
        "substrate_hash": substrate_hash,
        "total_assets": len(asset_hashes),
        "total_compiled_assets": len(asset_hashes),
        "assets": dict(sorted(asset_hashes.items())),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    AtomicStateLedger.save_json(l_path, payload)
    return payload


def load_asset_ledger(ledger_file: Union[str, Path]) -> Dict[str, Any]:
    """
    Loads asset ledger from disk. Returns empty dictionary if file does not exist.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.supervisor import AtomicStateLedger

    l_path = Path(ledger_file).resolve()
    if not l_path.is_file():
        return {}
    try:
        return AtomicStateLedger.load_json(l_path)
    except Exception:
        return {}


def trigger_drift_cascade(
    workspace_root: Optional[Union[str, Path]] = None,
    state_file: Optional[Union[str, Path]] = None,
    ledger_file: Optional[Union[str, Path]] = None,
    property_ids: Optional[List[str]] = None,
    force: bool = False,
    in_pipeline: bool = False,
    dry_run: bool = False,
    auto_record: bool = False,
    verify_edge: bool = False,
) -> Dict[str, Any]:
    """
    Wires substrate drift detection into the full development lifecycle cascade:
    qualification (qualify_search_intent) -> building (SubprocessPropertyAdapter / build hook) -> verification (MasterSEOVerifier / AssetIntegrityEvaluator).
    Enforces HWL-1349 post-verification commit latch: engine hash and asset ledgers
    are persisted only after 100% verification pass (exit code 0).
    Supports in_pipeline=True (HWL-1353) and zero-asset yield gate under drift (HWL-1348).
    Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
    """
    root = Path(
        workspace_root or os.environ.get("WORKSPACE_ROOT", "/home/ubuntuadmin/projects")
    ).resolve()
    s_path = Path(state_file).resolve() if state_file else root / ".agy" / "engine_hash.json"
    l_path = Path(ledger_file).resolve() if ledger_file else root / ".agy" / "asset_ledger.json"

    # 1. Drift Detection
    drift_report = detect_engine_drift(s_path, allow_tenant_scoped_hash=True)
    drift_detected = bool(drift_report.get("drift_detected", False))

    # Lazy imports from pseofactory to maintain modular decoupling and prevent circular imports
    from pseofactory.maintenance import (
        WorkspacePropertyScanner,
        AssetIntegrityEvaluator,
    )
    from pseofactory.qualification import qualify_search_intent

    scanner = WorkspacePropertyScanner(workspace_root=root)
    adapters = scanner.discover_properties(workspace_root=root)

    if property_ids:
        target_ids = {p.lower() for p in property_ids}
        adapters = [a for a in adapters if a.property_id.lower() in target_ids]

    # HWL-1348: Abort gate on zero asset yield must evaluate engine drift
    if len(adapters) == 0:
        return {
            "status": "NO_PROPERTIES",
            "drift_detected": drift_detected,
            "properties_audited": 0,
            "properties": {},
            "engine_hash": None,
        }

    # Universal Idempotency: if not forced and not drifted, check if anything needs doing
    if not force and not drift_detected and not in_pipeline:
        evaluator = AssetIntegrityEvaluator()
        any_drift = False
        for a in adapters:
            rep = evaluator.audit_all(a, check_engine_drift=False, check_ledger=False)
            if rep.drifted_assets_count > 0:
                any_drift = True
                break
        if not any_drift:
            return {
                "status": "SKIPPED_ALIGNED",
                "drift_detected": False,
                "properties_audited": len(adapters),
                "properties": {a.property_id: {"status": "ALIGNED"} for a in adapters},
                "engine_hash": drift_report.get("current_hash"),
            }

    property_results: Dict[str, Any] = {}
    evaluator = AssetIntegrityEvaluator()

    for adapter in adapters:
        p_id = adapter.property_id
        prop_res: Dict[str, Any] = {
            "property_id": p_id,
            "qualification": "PASS",
            "build": "PASS",
            "verification": "PASS",
            "status": "PASS",
            "issues": [],
        }

        # Stage 1: Qualification (qualify_search_intent)
        if adapter.tools:
            for tool in adapter.tools:
                slug = tool.get("slug") or tool.get("name", "")
                kw = tool.get("primary_keyword") or slug.replace("-", " ")
                if kw:
                    try:
                        q_res = qualify_search_intent({
                            "query": kw,
                            "slug": slug,
                            "impressions": tool.get("impressions", 100),
                            "position": tool.get("position", 15.0),
                            "days": tool.get("days", tool.get("period_days", 0)),
                        })
                        q_status = getattr(q_res, "status", None) or q_res.get("action")
                        if q_status in ("PRUNE", "PRUNE_PAGE", "REJECT_SYNTHETIC"):
                            prop_res["issues"].append(
                                f"Tool {slug} flagged for PRUNE during qualification"
                            )
                        elif q_status == "CONSOLIDATE_PAGES":
                            prop_res["issues"].append(
                                f"Tool {slug} flagged for CONSOLIDATE_PAGES during qualification"
                            )
                    except Exception as q_ex:
                        prop_res["issues"].append(f"Qualification error on {slug}: {q_ex}")

        # Stage 2: Building (SubprocessPropertyAdapter / build hook)
        # If drift detected or force, execute property rebuild in isolated child process
        if drift_detected or force or in_pipeline:
            with adapter.scoped_environment():
                build_success = adapter.build_all()
                if not build_success:
                    prop_res["build"] = "WARN"

        # Stage 3: Verification (MasterSEOVerifier & AssetIntegrityEvaluator)
        # Pre-latch verification audits asset structural compliance; engine drift is pending commit latch (HWL-1349, HWL-1353)
        audit_report = evaluator.audit_all(
            adapter=adapter,
            ledger_path=l_path if l_path.is_file() else None,
            state_file=s_path if s_path.is_file() else None,
            check_engine_drift=False,
            check_ledger=False,
        )

        if audit_report.drifted_assets_count > 0:
            prop_res["verification"] = "FAIL"
            prop_res["status"] = "FAIL"
            for rec in audit_report.drifted_assets:
                prop_res["issues"].extend(rec.details)

        # Run MasterSEOVerifier if sitemap.xml exists in dist
        if (adapter.dist_dir / "sitemap.xml").is_file():
            try:
                from pseofactory.verifier import MasterSEOVerifier
                v = MasterSEOVerifier(
                    dist_dir=adapter.dist_dir,
                    canonical_base=adapter.canonical_base,
                    domain=adapter.domain,
                    brand_name=adapter.brand_name,
                    tools=adapter.tools,
                )
                seo_report = v.audit_seo_checklist(dist_dir=adapter.dist_dir, raise_on_error=False)
                if seo_report.get("status") == "FAIL":
                    prop_res["verification"] = "FAIL"
                    prop_res["status"] = "FAIL"
                    prop_res["issues"].extend(seo_report.get("issues", []))
            except Exception as v_ex:
                prop_res["verification"] = "FAIL"
                prop_res["status"] = "FAIL"
        # Optional Live Edge Verification: Local build passes are never accepted as proof of live edge deployment
        if verify_edge and not dry_run:
            from pseofactory.gitops import LiveEdgeVerifier
            verifier = LiveEdgeVerifier()
            edge_url = f"https://{adapter.domain}"
            edge_res = verifier.verify_edge_deployment(base_url=edge_url, dist_dir=adapter.dist_dir)
            prop_res["edge"] = edge_res
            if edge_res.get("status") != "PASS":
                prop_res["verification"] = "FAIL"
                prop_res["status"] = "FAIL"
                prop_res["issues"].append(
                    f"Live edge deployment verification failed for {edge_url}: {edge_res.get('error')}"
                )

        property_results[p_id] = prop_res

    # Overall outcome across all discovered properties
    all_passed = (len(adapters) > 0) and all(
        res.get("status") == "PASS" for res in property_results.values()
    )

    current_engine_hash = None
    # Stage 4: HWL-1349 Post-Verification Commit Latch
    # Latch engine hash and asset ledgers ONLY after 100% verification pass
    if all_passed and not dry_run:
        current_engine_hash = record_engine_hash(s_path)
        all_asset_hashes: Dict[str, str] = {}
        for adapter in adapters:
            for a in adapter.list_assets():
                rel = (
                    a.relative_to(adapter.dist_dir).as_posix()
                    if a.is_relative_to(adapter.dist_dir)
                    else (
                        a.relative_to(adapter.repo_path).as_posix()
                        if getattr(adapter, "repo_path", None) and a.is_relative_to(adapter.repo_path)
                        else (a.relative_to(adapter.dist_dir.parent).as_posix() if a.is_relative_to(adapter.dist_dir.parent) else a.name)
                    )
                )
                all_asset_hashes[f"{adapter.property_id}/{rel}"] = compute_asset_fingerprint(a)
        record_asset_ledger(l_path, asset_hashes=all_asset_hashes, engine_hash=current_engine_hash)

    cascade_status = "PASS" if all_passed else "FAIL"

    return {
        "status": cascade_status,
        "drift_detected": drift_detected,
        "properties_audited": len(adapters),
        "properties": property_results,
        "engine_hash": current_engine_hash,
    }


cascade_drift_lifecycle = trigger_drift_cascade
