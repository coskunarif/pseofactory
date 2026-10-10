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
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple


_ENGINE_HASH_CACHE: Dict[Tuple[Any, ...], Tuple[float, str]] = {}


def clear_engine_hash_cache() -> None:
    """Clears the in-memory engine hash cache."""
    _ENGINE_HASH_CACHE.clear()


def compute_engine_hash(
    include_paths: Optional[List[Union[str, Path]]] = None,
    base_dirs: Optional[List[Union[str, Path]]] = None,
) -> str:
    """
    Computes a deterministic SHA-256 fingerprint across all Python code,
    schemas, and templates defining the programmatic SEO substrate.
    """
    pseofactory_pkg_dir = Path(__file__).resolve().parent

    # Determine stat/mtime of pkg and extra paths to check cache validity
    mtimes: List[float] = []
    try:
        mtimes.append(pseofactory_pkg_dir.stat().st_mtime)
    except OSError:
        pass

    if base_dirs:
        for bdir in base_dirs:
            bpath = Path(bdir).resolve()
            if bpath.is_dir():
                try:
                    mtimes.append(bpath.stat().st_mtime)
                except OSError:
                    pass
                for p in bpath.glob("**/*.py"):
                    if "__pycache__" not in p.parts and not p.name.endswith(".pyc"):
                        try:
                            mtimes.append(p.stat().st_mtime)
                        except OSError:
                            pass

    if include_paths:
        for ip in include_paths:
            ipath = Path(ip).resolve()
            if ipath.is_file():
                try:
                    mtimes.append(ipath.stat().st_mtime)
                except OSError:
                    pass
            elif ipath.is_dir():
                try:
                    mtimes.append(ipath.stat().st_mtime)
                except OSError:
                    pass
                for p in ipath.glob("**/*"):
                    if p.is_file() and "__pycache__" not in p.parts and not p.name.endswith(".pyc"):
                        try:
                            mtimes.append(p.stat().st_mtime)
                        except OSError:
                            pass

    composite_mtime = max(mtimes) if mtimes else 0.0

    cache_key = (
        tuple(sorted(str(Path(p).resolve()) for p in include_paths)) if include_paths else (),
        tuple(sorted(str(Path(b).resolve()) for b in base_dirs)) if base_dirs else (),
    )

    if cache_key in _ENGINE_HASH_CACHE:
        cached_mtime, cached_hash = _ENGINE_HASH_CACHE[cache_key]
        if cached_mtime == composite_mtime:
            return cached_hash

    files_to_hash: Dict[str, bytes] = {}
    for p in pseofactory_pkg_dir.glob("**/*.py"):
        if "__pycache__" in p.parts or p.name.endswith(".pyc"):
            continue
        rel = f"pseofactory/{p.relative_to(pseofactory_pkg_dir).as_posix()}"
        try:
            files_to_hash[rel] = p.read_bytes()
        except Exception:
            pass

    # 2. Add extra base directories if provided
    if base_dirs:
        for bdir in base_dirs:
            bpath = Path(bdir).resolve()
            if bpath.is_dir():
                for p in bpath.glob("**/*.py"):
                    if "__pycache__" in p.parts or p.name.endswith(".pyc") or ".git" in p.parts or ".pytest_cache" in p.parts:
                        continue
                    rel = f"{bpath.name}/{p.relative_to(bpath).as_posix()}"
                    try:
                        files_to_hash[rel] = p.read_bytes()
                    except Exception:
                        pass

    # 3. Add explicit include paths if provided
    if include_paths:
        for ip in include_paths:
            ipath = Path(ip).resolve()
            if ipath.is_file():
                rel = ipath.name
                try:
                    files_to_hash[rel] = ipath.read_bytes()
                except Exception:
                    pass
            elif ipath.is_dir():
                for p in ipath.glob("**/*"):
                    if p.is_file() and ("__pycache__" not in p.parts) and not p.name.endswith(".pyc") and (".git" not in p.parts):
                        rel = f"{ipath.name}/{p.relative_to(ipath).as_posix()}"
                        try:
                            files_to_hash[rel] = p.read_bytes()
                        except Exception:
                            pass

    # Deterministic master hash
    master = hashlib.sha256()
    for rel_path in sorted(files_to_hash.keys()):
        file_sha = hashlib.sha256(files_to_hash[rel_path]).hexdigest()
        master.update(f"{rel_path}:{file_sha}\n".encode("utf-8"))

    final_hash = master.hexdigest()
    _ENGINE_HASH_CACHE[cache_key] = (composite_mtime, final_hash)
    return final_hash


def detect_engine_drift(
    state_file: Union[str, Path],
    include_paths: Optional[List[Union[str, Path]]] = None,
    base_dirs: Optional[List[Union[str, Path]]] = None,
    auto_record: bool = False,
) -> Dict[str, Any]:
    """
    Audits the current engine hash against recorded state in state_file (.agy/engine_hash.json).
    If state_file does not exist or the hash differs, detects DRIFT, which triggers
    requires_recompile = True so unattended cron/systemd executions recompile all pages.
    """
    s_path = Path(state_file)
    current_hash = compute_engine_hash(include_paths=include_paths, base_dirs=base_dirs)

    recorded_hash: Optional[str] = None
    if s_path.exists():
        try:
            from pseofactory.supervisor import AtomicStateLedger
            data = AtomicStateLedger.load_json(s_path)
            if isinstance(data, dict):
                recorded_hash = data.get("engine_hash")
        except Exception:
            recorded_hash = None

    drift_detected = (recorded_hash != current_hash)

    if auto_record and drift_detected:
        record_engine_hash(s_path, hash_value=current_hash)

    return {
        "status": "DRIFT" if drift_detected else "ALIGNED",
        "drift_detected": drift_detected,
        "current_hash": current_hash,
        "recorded_hash": recorded_hash,
        "requires_recompile": drift_detected,
        "state_file": str(s_path),
    }


def record_engine_hash(
    state_file: Union[str, Path],
    hash_value: Optional[str] = None,
    include_paths: Optional[List[Union[str, Path]]] = None,
    base_dirs: Optional[List[Union[str, Path]]] = None,
) -> str:
    """
    Persists the updated engine hash into state_file after a successful build/compilation.
    Zero em-dashes. Zero en-dashes.
    """
    from pseofactory.supervisor import AtomicStateLedger

    s_path = Path(state_file)
    final_hash = hash_value or compute_engine_hash(include_paths=include_paths, base_dirs=base_dirs)
    _ENGINE_HASH_CACHE.clear()
    try:
        payload = {
            "engine_hash": final_hash,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
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
    payload: Dict[str, Any] = {
        "engine_hash": engine_hash or compute_engine_hash(),
        "total_assets": len(asset_hashes),
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
    drift_report = detect_engine_drift(s_path)
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
                        q_res = qualify_search_intent(
                            query=kw,
                            impressions=tool.get("impressions", 100),
                            position=tool.get("position", 15.0),
                        )
                        if q_res.status == "PRUNE":
                            prop_res["issues"].append(
                                f"Tool {slug} flagged for PRUNE during qualification"
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
                rel = a.relative_to(adapter.dist_dir).as_posix()
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

