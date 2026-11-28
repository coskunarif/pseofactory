"""
pseofactory Per-Tenant Impact Planner
AST-backed conservative module partition and git-diff + live-drift impact planner.
Ensures changes strictly isolated to a single tenant's exclusive module (e.g., gainhelm_estate.py)
or non-engine paths (tests/docs) only reflect and deploy impacted tenants, while failing closed
to ALL tenants on any shared module, cross-tenant import, unknown path, or invalid git base.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union


CANONICAL_TENANT_ORDER: Tuple[str, ...] = (
    "profithelm",
    "prexvo",
    "gainhelm",
    "lienbond",
)

CANONICAL_TENANT_REPO_DIRS: Dict[str, str] = {
    "profithelm": "profithelm-platform",
    "prexvo": "prexvo",
    "gainhelm": "gainhelm",
    "lienbond": "lienbond",
}

DECLARED_TENANT_EXCLUSIVE_ROOTS: Dict[str, Set[str]] = {
    "gainhelm": {"pseofactory/gainhelm_estate.py"},
}

_PARTITION_CACHE: Dict[Tuple[str, Tuple[str, ...]], Tuple[Tuple[Tuple[str, float, int], ...], Dict[str, Any]]] = {}


def clear_partition_cache() -> None:
    """Clears the in-memory AST partition cache."""
    _PARTITION_CACHE.clear()


def discover_active_tenants(
    workspace_root: Union[str, Path] = "/home/ubuntuadmin/projects",
) -> List[Tuple[str, Path]]:
    """
    Dynamically discovers active tenants from <workspace_root>/*/.pseofactory.json,
    preserving canonical order (profithelm, prexvo, gainhelm, lienbond) followed by
    any additional discovered tenants sorted alphabetically.
    """
    ws = Path(workspace_root).resolve()
    discovered: Dict[str, Path] = {}
    if ws.is_dir():
        for child in sorted(ws.iterdir()):
            try:
                if not child.is_dir() or child.name.startswith("."):
                    continue
                marker = child / ".pseofactory.json"
                if not marker.is_file():
                    continue
            except OSError:
                continue
            raw_pid = child.name.lower()
            try:
                data = json.loads(marker.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("property_id"):
                    raw_pid = str(data["property_id"]).strip().lower()
            except Exception:
                pass
            pid = "profithelm" if raw_pid in ("profithelm-platform", "factory") else raw_pid
            if pid not in discovered:
                discovered[pid] = child

    if not discovered:
        for tid in CANONICAL_TENANT_ORDER:
            repo_dir = ws / CANONICAL_TENANT_REPO_DIRS[tid]
            if repo_dir.is_dir() and (
                (repo_dir / "substrate_lock.json").is_file()
                or (repo_dir / ".git").exists()
            ):
                discovered[tid] = repo_dir

    if not discovered:
        return [(tid, ws / CANONICAL_TENANT_REPO_DIRS[tid]) for tid in CANONICAL_TENANT_ORDER]

    ordered: List[Tuple[str, Path]] = []
    for tid in CANONICAL_TENANT_ORDER:
        if tid in discovered:
            ordered.append((tid, discovered[tid]))
    for tid in sorted(discovered.keys()):
        if tid not in CANONICAL_TENANT_ORDER:
            ordered.append((tid, discovered[tid]))
    return ordered


def _collect_pkg_py_files(pkg_dir: Path) -> Set[str]:
    """Collects all pseofactory/**/*.py relative paths under pkg_dir."""
    out: Set[str] = set()
    if not pkg_dir.is_dir():
        return out
    for p in pkg_dir.glob("**/*.py"):
        if "__pycache__" in p.parts or p.name.endswith(".pyc"):
            continue
        out.add(f"pseofactory/{p.relative_to(pkg_dir).as_posix()}")
    return out


def _module_name_to_rel_paths(mod_name: str, all_py_files: Set[str]) -> Set[str]:
    """Resolves a dotted pseofactory.* module name to matching package-relative .py paths."""
    if not mod_name:
        return set()
    parts = [p for p in mod_name.split(".") if p]
    if not parts or parts[0] != "pseofactory":
        return set()
    if len(parts) == 1:
        cand = "pseofactory/__init__.py"
        return {cand} if cand in all_py_files else set()
    sub = "/".join(parts[1:])
    found: Set[str] = set()
    for cand in (f"pseofactory/{sub}.py", f"pseofactory/{sub}/__init__.py"):
        if cand in all_py_files:
            found.add(cand)
    return found


def _resolve_import_node_targets(
    node: ast.AST,
    src_rel: str,
    all_py_files: Set[str],
) -> Set[str]:
    """Resolves an ast.Import or ast.ImportFrom node to target pseofactory/**/*.py paths."""
    targets: Set[str] = set()
    if isinstance(node, ast.Import):
        for alias in node.names:
            targets.update(_module_name_to_rel_paths(alias.name, all_py_files))
        return targets

    if isinstance(node, ast.ImportFrom):
        base_mod = ""
        if node.level and node.level > 0:
            # Compute enclosing package of src_rel (e.g., pseofactory/trends/db.py -> ['pseofactory', 'trends'])
            rel_parts = src_rel[:-3].split("/")
            pkg_parts = rel_parts[:-1]  # strip filename (even for __init__.py -> package dir)
            up = node.level - 1
            if up > len(pkg_parts):
                return targets
            prefix_parts = pkg_parts[: len(pkg_parts) - up] if up > 0 else list(pkg_parts)
            if node.module:
                prefix_parts.extend(node.module.split("."))
            base_mod = ".".join(prefix_parts)
        else:
            base_mod = node.module or ""

        targets.update(_module_name_to_rel_paths(base_mod, all_py_files))
        for alias in node.names:
            if alias.name == "*":
                continue
            cand_mod = f"{base_mod}.{alias.name}" if base_mod else alias.name
            targets.update(_module_name_to_rel_paths(cand_mod, all_py_files))
    return targets


def _expr_compares_tenant_literal(expr: ast.AST, tid: str) -> bool:
    """
    Returns True ONLY if an AST boolean expression strictly implies the condition
    requires tenant == tid (rejecting negated `not`, `!=`, `not in`, `or` with any
    non-matching branch, and membership tests including other tenants).
    """
    tid_low = tid.lower()
    if isinstance(expr, ast.UnaryOp):
        return False
    if isinstance(expr, ast.BoolOp):
        if isinstance(expr.op, ast.And):
            return any(_expr_compares_tenant_literal(v, tid_low) for v in expr.values)
        if isinstance(expr.op, ast.Or):
            return bool(expr.values) and all(_expr_compares_tenant_literal(v, tid_low) for v in expr.values)
        return False
    if isinstance(expr, ast.Compare):
        if len(expr.ops) != 1 or len(expr.comparators) != 1:
            return False
        op = expr.ops[0]
        left = expr.left
        right = expr.comparators[0]
        if isinstance(op, ast.Eq):
            left_is_str = isinstance(left, ast.Constant) and isinstance(left.value, str)
            right_is_str = isinstance(right, ast.Constant) and isinstance(right.value, str)
            if left_is_str and not right_is_str:
                return left.value.strip().lower() == tid_low
            if right_is_str and not left_is_str:
                return right.value.strip().lower() == tid_low
            return False
        if isinstance(op, ast.In):
            if isinstance(left, ast.Constant):
                return False
            if isinstance(right, (ast.Tuple, ast.List, ast.Set)) and right.elts:
                return all(
                    isinstance(elt, ast.Constant)
                    and isinstance(elt.value, str)
                    and elt.value.strip().lower() == tid_low
                    for elt in right.elts
                )
            return False
    return False


def _class_uses_imported_names_only_for_tenant(
    cls_node: ast.ClassDef,
    imported_local_names: Set[str],
    tid: str,
    other_tenants: Set[str],
) -> bool:
    """
    Verifies that symbols imported inside a class body are ONLY assigned to class
    attributes whose names explicitly contain `tid` and do not mention other tenants.
    """
    tid_low = tid.lower()
    if not imported_local_names:
        return False
    assigned_targets: List[str] = []
    for stmt in cls_node.body:
        if isinstance(stmt, ast.Assign):
            val_names = {n.id for n in ast.walk(stmt.value) if isinstance(n, ast.Name)}
            if val_names & imported_local_names:
                for tgt in stmt.targets:
                    if isinstance(tgt, ast.Name):
                        assigned_targets.append(tgt.id.lower())
                    else:
                        return False
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            val_names = {n.id for n in ast.walk(stmt.value) if isinstance(n, ast.Name)}
            if val_names & imported_local_names:
                if isinstance(stmt.target, ast.Name):
                    assigned_targets.append(stmt.target.id.lower())
                else:
                    return False
    if not assigned_targets:
        return False
    for attr_name in assigned_targets:
        if tid_low not in attr_name:
            return False
        if any(other in attr_name for other in other_tenants):
            return False
    return True


def _is_strictly_tenant_scoped_import(
    node: ast.AST,
    ancestors: List[Tuple[ast.AST, bool]],
    tid: str,
    other_tenants: Set[str],
) -> bool:
    """
    Returns True ONLY when an import of a tenant-exclusive module inside a shared
    module is strictly scoped to tenant `tid` (never top-level, never bare import
    or wildcard, every imported symbol contains `tid`, and enclosed by a tenant-named
    function, a positive tenant-literal if/elif body branch, or a tenant-named class attribute).
    """
    if not isinstance(node, ast.ImportFrom):
        return False
    if len(ancestors) <= 1:
        # Module top-level import executes unconditionally for all tenants
        return False

    tid_low = tid.lower()
    imported_local_names: Set[str] = set()
    for alias in node.names:
        if alias.name == "*":
            return False
        if tid_low not in alias.name.lower():
            return False
        if any(other in alias.name.lower() for other in other_tenants):
            return False
        imported_local_names.add(alias.asname or alias.name)

    # Check enclosing scopes from innermost to outermost (skipping ast.Module at index 0)
    for anc, in_orelse in reversed(ancestors[1:]):
        if isinstance(anc, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if tid_low in anc.name.lower() and not any(other in anc.name.lower() for other in other_tenants):
                return True
        elif isinstance(anc, ast.If):
            if not in_orelse and _expr_compares_tenant_literal(anc.test, tid_low):
                return True
        elif isinstance(anc, ast.ClassDef):
            if _class_uses_imported_names_only_for_tenant(anc, imported_local_names, tid_low, other_tenants):
                return True
    return False


def _extract_init_lazy_export_violations(
    init_tree: ast.Module,
    exclusive: Dict[str, Set[str]],
    all_py_files: Set[str],
) -> Set[str]:
    """
    Inspects pseofactory/__init__.py `_LAZY_EXPORTS` AST dict and returns any
    tenant-exclusive module paths that are exported under a cross-tenant symbol name.
    """
    demote: Set[str] = set()
    for stmt in init_tree.body:
        val_node = None
        if isinstance(stmt, ast.Assign):
            for tgt in stmt.targets:
                if isinstance(tgt, ast.Name) and tgt.id == "_LAZY_EXPORTS":
                    val_node = stmt.value
        elif isinstance(stmt, ast.AnnAssign):
            if isinstance(stmt.target, ast.Name) and stmt.target.id == "_LAZY_EXPORTS":
                val_node = stmt.value
        if isinstance(val_node, ast.Dict):
            for k_node, v_node in zip(val_node.keys, val_node.values):
                if not (isinstance(k_node, ast.Constant) and isinstance(k_node.value, str)):
                    continue
                export_key = k_node.value.lower()
                if isinstance(v_node, (ast.Tuple, ast.List)) and len(v_node.elts) >= 1:
                    mod_elt = v_node.elts[0]
                    if isinstance(mod_elt, ast.Constant) and isinstance(mod_elt.value, str):
                        target_rels = _module_name_to_rel_paths(mod_elt.value, all_py_files)
                        for target_rel in target_rels:
                            for tid, excl_set in exclusive.items():
                                if target_rel in excl_set and tid.lower() not in export_key:
                                    demote.add(target_rel)
    return demote


def get_tenant_engine_file_partition(
    pkg_dir: Optional[Union[str, Path]] = None,
    tenant_ids: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Computes an AST-backed conservative partition of all pseofactory/**/*.py files into:
      {
        "shared": Set[str],
        "exclusive": Dict[str, Set[str]],
      }
    A module is exclusive to tenant T ONLY IF:
    - It is a declared tenant-exclusive root (e.g. pseofactory/gainhelm_estate.py,
      pseofactory/tenants/<tid>/**/*.py, or pseofactory/<tid>_estate.py), AND
    - No other tenant's exclusive root imports it, AND
    - No shared module imports it outside a strictly tenant-scoped import site, AND
    - It is not exported as a cross-tenant symbol in pseofactory/__init__.py _LAZY_EXPORTS.
    On any parse error, fails closed by placing all modules in `shared`.
    """
    resolved_pkg = Path(pkg_dir).resolve() if pkg_dir is not None else Path(__file__).resolve().parent
    all_py_files = _collect_pkg_py_files(resolved_pkg)

    known_tenants: List[str] = list(
        dict.fromkeys(
            [t.lower() for t in (tenant_ids or CANONICAL_TENANT_ORDER)]
            + list(DECLARED_TENANT_EXCLUSIVE_ROOTS.keys())
        )
    )
    stat_sig_items: List[Tuple[str, float, int]] = []
    for rel in sorted(all_py_files):
        fp = resolved_pkg / rel[len("pseofactory/") :]
        try:
            st = fp.stat()
            stat_sig_items.append((rel, st.st_mtime, st.st_size))
        except OSError:
            stat_sig_items.append((rel, -1.0, -1))
    stat_sig = tuple(stat_sig_items)
    cache_key = (str(resolved_pkg), tuple(known_tenants))
    cached_entry = _PARTITION_CACHE.get(cache_key)
    if cached_entry is not None and cached_entry[0] == stat_sig:
        cached_val = cached_entry[1]
        return {
            "shared": set(cached_val["shared"]),
            "exclusive": {k: set(v) for k, v in cached_val["exclusive"].items()},
        }
    exclusive: Dict[str, Set[str]] = {tid: set() for tid in known_tenants}

    # 1. Seed candidate tenant-exclusive roots
    for tid, roots in DECLARED_TENANT_EXCLUSIVE_ROOTS.items():
        exclusive.setdefault(tid, set())
        for rel in roots:
            if rel in all_py_files:
                exclusive[tid].add(rel)

    for rel in sorted(all_py_files):
        parts = rel.split("/")
        # Convention 1: pseofactory/tenants/<tid>/**/*.py
        if len(parts) >= 4 and parts[0] == "pseofactory" and parts[1] == "tenants":
            tid = parts[2].lower()
            if tid in exclusive:
                exclusive[tid].add(rel)
        # Convention 2: pseofactory/<tid>_estate.py
        if len(parts) == 2 and parts[0] == "pseofactory" and parts[1].endswith("_estate.py"):
            cand_tid = parts[1][: -len("_estate.py")].lower()
            if cand_tid in exclusive:
                exclusive[cand_tid].add(rel)

    # 2. Parse AST for files that can reference candidate exclusive modules (fail closed on parse error)
    candidate_exclusive_files: Set[str] = set()
    for excl_set in exclusive.values():
        candidate_exclusive_files.update(excl_set)
    candidate_stems: Set[str] = set()
    for rel_c in candidate_exclusive_files:
        parts_c = rel_c[:-3].split("/")
        if parts_c[-1] == "__init__" and len(parts_c) >= 2:
            candidate_stems.add(parts_c[-2])
        else:
            candidate_stems.add(parts_c[-1])

    parsed_trees: Dict[str, ast.Module] = {}
    imports_by_file: Dict[str, List[Tuple[ast.AST, List[Tuple[ast.AST, bool]], Set[str]]]] = {}

    if candidate_exclusive_files:
        for rel in sorted(all_py_files):
            fp = resolved_pkg / rel[len("pseofactory/") :]
            try:
                src_text = fp.read_text(encoding="utf-8")
            except Exception:
                return {
                    "shared": set(all_py_files),
                    "exclusive": {tid: set() for tid in exclusive},
                }
            if (
                rel != "pseofactory/__init__.py"
                and rel not in candidate_exclusive_files
                and not any(stem in src_text for stem in candidate_stems)
            ):
                imports_by_file[rel] = []
                continue
            try:
                tree = ast.parse(src_text, filename=rel)
            except Exception:
                return {
                    "shared": set(all_py_files),
                    "exclusive": {tid: set() for tid in exclusive},
                }
            parsed_trees[rel] = tree
            file_imports: List[Tuple[ast.AST, List[Tuple[ast.AST, bool]], Set[str]]] = []

            def _walk_with_ancestors(cur: ast.AST, stack: List[Tuple[ast.AST, bool]]) -> None:
                if isinstance(cur, (ast.Import, ast.ImportFrom)):
                    targets = _resolve_import_node_targets(cur, rel, all_py_files)
                    if targets:
                        file_imports.append((cur, list(stack), targets))
                    return
                if isinstance(cur, ast.If):
                    stack.append((cur, False))
                    for stmt in cur.body:
                        _walk_with_ancestors(stmt, stack)
                    stack.pop()
                    stack.append((cur, True))
                    for stmt in cur.orelse:
                        _walk_with_ancestors(stmt, stack)
                    stack.pop()
                    return
                stack.append((cur, False))
                for child in ast.iter_child_nodes(cur):
                    _walk_with_ancestors(child, stack)
                stack.pop()

            _walk_with_ancestors(tree, [])
            imports_by_file[rel] = file_imports

    # 3. Check __init__.py _LAZY_EXPORTS for cross-tenant leakage
    init_tree = parsed_trees.get("pseofactory/__init__.py")
    if init_tree is not None:
        for demote_rel in _extract_init_lazy_export_violations(init_tree, exclusive, all_py_files):
            for excl_set in exclusive.values():
                excl_set.discard(demote_rel)

    # 4. Conservative fixpoint demotion on cross-tenant or non-scoped shared imports
    changed = True
    while changed:
        changed = False
        owner_of: Dict[str, str] = {}
        for tid, excl_set in exclusive.items():
            for rel in excl_set:
                owner_of[rel] = tid

        to_demote: Set[str] = set()
        for src_rel, file_imports in imports_by_file.items():
            src_owner = owner_of.get(src_rel)
            for imp_node, ancestors, targets in file_imports:
                for tgt_rel in targets:
                    tgt_owner = owner_of.get(tgt_rel)
                    if tgt_owner is None or tgt_rel == src_rel:
                        continue
                    if src_owner is not None:
                        if src_owner != tgt_owner:
                            to_demote.add(tgt_rel)
                    else:
                        other_tids = {t for t in exclusive if t != tgt_owner}
                        if not _is_strictly_tenant_scoped_import(imp_node, ancestors, tgt_owner, other_tids):
                            to_demote.add(tgt_rel)

        if to_demote:
            for d_rel in to_demote:
                for excl_set in exclusive.values():
                    if d_rel in excl_set:
                        excl_set.discard(d_rel)
                        changed = True

    all_exclusive: Set[str] = set()
    for excl_set in exclusive.values():
        all_exclusive.update(excl_set)
    shared = all_py_files - all_exclusive

    result_partition = {
        "shared": shared,
        "exclusive": exclusive,
    }
    _PARTITION_CACHE[cache_key] = (
        stat_sig,
        {
            "shared": set(shared),
            "exclusive": {k: set(v) for k, v in exclusive.items()},
        },
    )
    return result_partition


def _classify_changed_file(
    rel_path: str,
    active_tenants: Sequence[str],
    partition: Dict[str, Any],
) -> Tuple[Set[str], Optional[str], Optional[str]]:
    """
    Classifies a single changed repo-relative file path.
    Returns (impacted_tenants_set, reason_str, fail_closed_trigger_or_None).
    """
    norm = str(rel_path or "").strip().replace("\\", "/")
    while norm.startswith("./"):
        norm = norm[2:]
    norm = norm.lstrip("/")
    if not norm:
        return set(), None, None

    # 1. Non-engine documentation, test, and CI workflow paths -> 0 tenant impact
    if (
        norm.startswith("pseofactory_tests/")
        or norm.startswith("docs/")
        or norm.startswith(".github/")
        or norm == ".gitignore"
        or (norm.endswith(".md") and not norm.startswith("pseofactory/"))
    ):
        return set(), None, None

    # 2. Tenant-scoped syndication paths -> single tenant
    if norm.startswith("syndication/"):
        parts = norm.split("/")
        if len(parts) >= 2 and parts[1].lower() in active_tenants:
            tid = parts[1].lower()
            return {tid}, f"changed syndication asset '{norm}'", None
        return set(active_tenants), f"unmapped syndication path '{norm}'", f"unmapped path: {norm}"

    # 3. Engine Python modules -> AST partition lookup
    if norm.startswith("pseofactory/") and norm.endswith(".py"):
        for tid, excl_set in (partition.get("exclusive") or {}).items():
            if norm in excl_set and tid in active_tenants:
                return {tid}, f"changed tenant-exclusive module '{norm}'", None
        if norm in (partition.get("shared") or set()):
            return set(active_tenants), f"changed shared engine module '{norm}'", None
        return (
            set(active_tenants),
            f"changed/removed unpartitioned engine module '{norm}'",
            f"unpartitioned engine module: {norm}",
        )

    # 4. Any unknown or unmapped path -> fail-closed ALL tenants
    return set(active_tenants), f"unmapped path '{norm}' (fail-closed ALL)", f"unmapped path: {norm}"


def _inspect_tenant_live_drift(
    tid: str,
    t_repo: Path,
    current_engine_hash: str,
    current_tenant_hash: str,
) -> List[str]:
    """
    Inspects a live tenant repository for self-healing drift conditions:
    missing/stale substrate_lock.json, mismatched dist_fingerprint/total_assets,
    dirty git tree, or unpushed commits ahead of origin/main.
    """
    from pseofactory.drift import compute_dist_lock_metrics

    reasons: List[str] = []
    if not t_repo.is_dir():
        reasons.append(f"missing tenant repo at {t_repo}")
        return reasons

    dist_dir = t_repo / "dist"
    lock_file = t_repo / "substrate_lock.json"
    if not dist_dir.is_dir() or not (dist_dir / "index.html").is_file():
        reasons.append("missing dist/index.html")
    if not lock_file.is_file():
        reasons.append("missing substrate_lock.json")
    else:
        try:
            lock_data = json.loads(lock_file.read_text(encoding="utf-8"))
            if not isinstance(lock_data, dict):
                reasons.append("invalid substrate_lock.json payload")
            else:
                lock_tsh = str(lock_data.get("tenant_substrate_hash") or "").strip()
                lock_eh = str(lock_data.get("engine_hash") or "").strip()
                lock_sh = str(lock_data.get("substrate_hash") or lock_eh).strip()
                if lock_tsh:
                    if lock_tsh != current_tenant_hash:
                        reasons.append(
                            f"stale tenant_substrate_hash ({lock_tsh[:12]} != {current_tenant_hash[:12]})"
                        )
                else:
                    if lock_eh != current_engine_hash or lock_sh != current_engine_hash:
                        reasons.append(
                            f"missing tenant_substrate_hash and stale engine_hash ({lock_eh[:12]} != {current_engine_hash[:12]})"
                        )
                if dist_dir.is_dir():
                    live_fp, live_tot = compute_dist_lock_metrics(dist_dir)
                    if str(lock_data.get("dist_fingerprint") or "") != live_fp:
                        reasons.append("mismatched dist_fingerprint")
                    if lock_data.get("total_assets") != live_tot:
                        reasons.append("mismatched total_assets")
        except Exception as exc:
            reasons.append(f"unreadable substrate_lock.json ({exc})")

    if (t_repo / ".git").exists():
        try:
            st = subprocess.run(
                ["git", "-C", str(t_repo), "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if st.returncode == 0 and st.stdout.strip():
                reasons.append("dirty git working tree")
        except Exception:
            reasons.append("git status check failed")
        try:
            ref = subprocess.run(
                ["git", "-C", str(t_repo), "rev-parse", "--verify", "origin/main"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if ref.returncode == 0:
                ahead = subprocess.run(
                    ["git", "-C", str(t_repo), "rev-list", "--count", "origin/main..HEAD"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=5,
                )
                if ahead.returncode == 0 and int(ahead.stdout.strip() or "0") > 0:
                    reasons.append(f"{ahead.stdout.strip()} unpushed commit(s) ahead of origin/main")
        except Exception:
            pass

    return reasons


def plan_tenant_impact(
    base_ref: Optional[str] = None,
    repo_root: Optional[Union[str, Path]] = None,
    workspace_root: Optional[Union[str, Path]] = None,
    changed_files: Optional[Iterable[str]] = None,
    receipt_path: Optional[Union[str, Path]] = None,
    check_live_drift: bool = True,
) -> Dict[str, Any]:
    """
    Computes a fail-closed per-tenant impact plan combining:
    1. Git diff against base_ref (defaulting to pseofactory_head_sha in last_full_audit_receipt.json)
       or explicit changed_files list.
    2. AST-backed module partition of pseofactory/**/*.py.
    3. Live self-healing drift inspection across all active tenants.

    Returns:
      {
        "mode": "NONE" | "SCOPED" | "ALL",
        "base_ref": str | None,
        "impacted_tenants": List[str],
        "unaffected_tenants": List[str],
        "changed_files": List[str],
        "reasons_by_tenant": Dict[str, List[str]],
        "fail_closed_triggers": List[str],
      }
    """
    from pseofactory.drift import compute_engine_hash, compute_tenant_substrate_hash

    eff_repo = Path(repo_root).resolve() if repo_root is not None else Path(__file__).resolve().parent.parent
    eff_ws = Path(workspace_root).resolve() if workspace_root is not None else Path("/home/ubuntuadmin/projects").resolve()
    pkg_dir = eff_repo / "pseofactory"

    tenant_pairs = discover_active_tenants(eff_ws)
    active_tenants = [tid for tid, _ in tenant_pairs]
    tenant_repo_map = dict(tenant_pairs)

    partition = get_tenant_engine_file_partition(pkg_dir, tenant_ids=active_tenants)

    reasons_by_tenant: Dict[str, List[str]] = {tid: [] for tid in active_tenants}
    impacted_set: Set[str] = set()
    fail_closed_triggers: List[str] = []
    resolved_changed_files: List[str] = []
    eff_base: Optional[str] = base_ref

    if changed_files is not None:
        resolved_changed_files = [str(f).strip() for f in changed_files if str(f).strip()]
    else:
        if not eff_base:
            r_path = (
                Path(receipt_path).resolve()
                if receipt_path is not None
                else (eff_ws / ".agy" / "last_full_audit_receipt.json")
            )
            if r_path.is_file():
                try:
                    rec_data = json.loads(r_path.read_text(encoding="utf-8"))
                    if isinstance(rec_data, dict) and rec_data.get("pseofactory_head_sha"):
                        eff_base = str(rec_data["pseofactory_head_sha"]).strip()
                except Exception as exc:
                    fail_closed_triggers.append(f"unreadable audit receipt ({exc})")

        if not eff_base:
            fail_closed_triggers.append("missing base_ref and last_full_audit_receipt.json pseofactory_head_sha")
        else:
            anc = subprocess.run(
                ["git", "-C", str(eff_repo), "merge-base", "--is-ancestor", eff_base, "HEAD"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            if anc.returncode != 0:
                fail_closed_triggers.append(f"invalid or non-ancestor base_ref '{eff_base}'")
            else:
                diff_p = subprocess.run(
                    ["git", "-C", str(eff_repo), "diff", "--name-only", f"{eff_base}..HEAD"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=15,
                )
                if diff_p.returncode != 0:
                    fail_closed_triggers.append(f"git diff failed for base_ref '{eff_base}'")
                else:
                    resolved_changed_files = [
                        ln.strip() for ln in diff_p.stdout.splitlines() if ln.strip()
                    ]

    if fail_closed_triggers:
        for tid in active_tenants:
            impacted_set.add(tid)
            reasons_by_tenant[tid].extend(fail_closed_triggers)
    else:
        for rel_f in resolved_changed_files:
            hit_tenants, reason, fc_trigger = _classify_changed_file(rel_f, active_tenants, partition)
            if fc_trigger:
                fail_closed_triggers.append(fc_trigger)
            for tid in hit_tenants:
                impacted_set.add(tid)
                if reason:
                    reasons_by_tenant[tid].append(reason)

    if check_live_drift:
        cur_eh = compute_engine_hash()
        for tid in active_tenants:
            cur_tsh = compute_tenant_substrate_hash(tid, pkg_dir=pkg_dir)
            drift_reasons = _inspect_tenant_live_drift(
                tid=tid,
                t_repo=tenant_repo_map[tid],
                current_engine_hash=cur_eh,
                current_tenant_hash=cur_tsh,
            )
            if drift_reasons:
                impacted_set.add(tid)
                reasons_by_tenant[tid].extend(drift_reasons)

    impacted_tenants = [tid for tid in active_tenants if tid in impacted_set]
    unaffected_tenants = [tid for tid in active_tenants if tid not in impacted_set]

    if not impacted_tenants:
        mode = "NONE"
    elif len(impacted_tenants) == len(active_tenants):
        mode = "ALL"
    else:
        mode = "SCOPED"

    return {
        "mode": mode,
        "base_ref": eff_base,
        "impacted_tenants": impacted_tenants,
        "unaffected_tenants": unaffected_tenants,
        "changed_files": resolved_changed_files,
        "reasons_by_tenant": reasons_by_tenant,
        "fail_closed_triggers": fail_closed_triggers,
    }
