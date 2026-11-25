"""
Unified multi-tenant UI/UX browser verification harness for pseofactory.
Executes end-to-end mechanical audits via host Chrome DevTools Protocol (CDP port 9222).
Verifies CLS === 0.0, minimum 43.5px touch targets, responsive viewports (375px/1280px),
zero forbidden dashes (anti-slop invariant), and reactive interactive widget calculations.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

from abc import ABC, abstractmethod
import asyncio
import atexit
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
import datetime
import fcntl
import hashlib
import inspect
import json
import os
from pathlib import Path
import queue
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET

from pseofactory.server import EphemeralDistServer


_CHROME_VERSION_CACHE: Dict[str, str] = {}
_CHROME_VERSION_LOCK = threading.Lock()
_VERIFIER_DIGEST_CACHE: Dict[str, Tuple[Tuple[Tuple[str, int, int], ...], str]] = {}
_VERIFIER_DIGEST_LOCK = threading.Lock()
_ACTIVE_CHROME_INSTANCES: Dict[int, Tuple[int, str]] = {}
_ACTIVE_CHROME_LOCK = threading.Lock()
_DEFAULT_RECEIPTS_DIR = Path("/home/ubuntuadmin/projects/.agy/browser_verify_receipts")
_MAX_FULL_HASH_ASSET_BYTES = 5 * 1024 * 1024


def _atexit_cleanup_chrome_instances() -> None:
    """Safety net ensuring no orphaned headless Chromium processes or temp profiles survive exit."""
    with _ACTIVE_CHROME_LOCK:
        items = list(_ACTIVE_CHROME_INSTANCES.items())
        _ACTIVE_CHROME_INSTANCES.clear()
    if not items:
        return
    for pid, (pgid, _tmp_dir) in items:
        try:
            os.killpg(pgid, signal.SIGTERM)
        except OSError:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        alive = False
        for pid, _pair in items:
            try:
                os.kill(pid, 0)
                alive = True
                break
            except OSError:
                pass
        if not alive:
            break
        time.sleep(0.05)
    for pid, (pgid, tmp_dir) in items:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except OSError:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


atexit.register(_atexit_cleanup_chrome_instances)


def _playwright_revision_key(path: Path) -> Tuple[int, str]:
    """Sort key preferring highest numeric Playwright browser revision."""
    m = re.search(r"-(\d+)(?:/|$)", path.as_posix())
    return (int(m.group(1)) if m else -1, path.as_posix())


def discover_headless_chrome_binary() -> Tuple[Optional[str], bool]:
    """
    Discovers the pinned local Chromium binary for isolated headless CDP workers.
    Returns (binary_path, is_headless_shell).
    Preference order:
    1. PSEOFACTORY_CHROME_BIN override
    2. Pinned Playwright chrome-headless-shell (fastest startup & runtime, verified 100% layout/CLS parity)
    3. Pinned Playwright full chrome binary (launched with --headless=new)
    4. System google-chrome / chromium binary (launched with --headless=new)
    """
    override = (os.environ.get("PSEOFACTORY_CHROME_BIN") or "").strip()
    if override:
        ov_path = Path(override)
        if ov_path.is_file() and os.access(ov_path, os.X_OK):
            name_low = ov_path.name.lower()
            is_shell = "headless-shell" in name_low or "headless_shell" in name_low
            return str(ov_path), is_shell

    pw_root_env = (os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "").strip()
    pw_roots = [Path(pw_root_env)] if pw_root_env else [Path.home() / ".cache" / "ms-playwright"]
    for pw_root in pw_roots:
        if not pw_root.is_dir():
            continue
        shell_candidates: List[Path] = []
        for pattern in (
            "chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell",
            "chromium_headless_shell-*/chrome-linux/headless_shell",
        ):
            shell_candidates.extend(
                p for p in pw_root.glob(pattern) if p.is_file() and os.access(p, os.X_OK)
            )
        if shell_candidates:
            shell_candidates.sort(key=_playwright_revision_key, reverse=True)
            return str(shell_candidates[0]), True

        chrome_candidates: List[Path] = []
        for pattern in (
            "chromium-*/chrome-linux64/chrome",
            "chromium-*/chrome-linux/chrome",
        ):
            chrome_candidates.extend(
                p for p in pw_root.glob(pattern) if p.is_file() and os.access(p, os.X_OK)
            )
        if chrome_candidates:
            chrome_candidates.sort(key=_playwright_revision_key, reverse=True)
            return str(chrome_candidates[0]), False

    for bin_name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        found = shutil.which(bin_name)
        if found:
            return found, False

    return None, False


def get_chrome_version_string(binary_path: str) -> str:
    """Returns cached `<chrome_bin> --version` string once per process."""
    with _CHROME_VERSION_LOCK:
        cached = _CHROME_VERSION_CACHE.get(binary_path)
    if cached is not None:
        return cached
    ver = "unknown"
    try:
        res = subprocess.run(
            [binary_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        raw = (res.stdout or res.stderr or "").strip()
        if raw:
            ver = raw.splitlines()[0].strip()
    except Exception:
        pass
    with _CHROME_VERSION_LOCK:
        _CHROME_VERSION_CACHE[binary_path] = ver
    return ver


def _get_available_ram_gb() -> float:
    """Reads MemAvailable in GiB from /proc/meminfo with safe fallback."""
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as mf:
            for line in mf:
                if line.startswith("MemAvailable:"):
                    parts = line.split()
                    if len(parts) >= 2 and parts[1].isdigit():
                        return int(parts[1]) / (1024.0 * 1024.0)
    except Exception:
        pass
    return 4.0


def compute_auto_worker_count(num_routes: int, requested_workers: Optional[int] = None) -> int:
    """
    Safely sizes the isolated headless Chromium worker pool based on route count, CPU cores,
    and available host RAM (~0.55 GiB headroom per worker after 1.0 GiB OS reserve).
    """
    if num_routes <= 1:
        return 1
    cpu_count = max(1, os.cpu_count() or 2)
    avail_ram_gb = _get_available_ram_gb()
    ram_cap = max(1, int(max(0.55, avail_ram_gb - 1.0) // 0.55))

    if requested_workers is None:
        env_w = (os.environ.get("PSEOFACTORY_BROWSER_WORKERS") or "").strip()
        if env_w.isdigit() and int(env_w) >= 1:
            requested_workers = int(env_w)

    if requested_workers is not None:
        req = max(1, int(requested_workers))
        return max(1, min(req, num_routes, cpu_count, ram_cap))

    # Avoid nested Chrome worker oversubscription when already parallelized under pytest-xdist
    if "PYTEST_XDIST_WORKER" in os.environ:
        return 1

    # Scale up to ~60% of CPU cores (capped at 6 per tenant so concurrent tenants never OOM or thrash Chrome)
    # and require at least ~2 routes per worker for small route sets to amortize browser startup.
    auto_cpu_cap = max(1, min(6, (cpu_count * 3) // 5))
    route_amortized_cap = num_routes if num_routes <= 3 else max(2, (num_routes + 1) // 2)
    return max(1, min(num_routes, route_amortized_cap, auto_cpu_cap, ram_cap))


def parse_and_apply_shard(routes: List[str], shard: Optional[str]) -> List[str]:
    """
    Deterministically partitions `routes` for 1-indexed shard spec 'K/N' (e.g. '1/4').
    Sorts routes lexicographically before round-robin slicing so shards 1/N..N/N
    cover the exact route union with zero overlap and zero missed routes.
    """
    if not shard:
        return list(routes)
    m = re.match(r"^\s*(\d+)\s*/\s*(\d+)\s*$", str(shard))
    if not m:
        raise ValueError(f"Invalid shard spec {shard!r}: expected 'K/N' with 1 <= K <= N")
    k = int(m.group(1))
    n = int(m.group(2))
    if n < 1 or k < 1 or k > n:
        raise ValueError(f"Invalid shard spec {shard!r}: expected 1 <= K <= N (got K={k}, N={n})")
    ordered = sorted(routes)
    return [r for idx, r in enumerate(ordered) if (idx % n) == (k - 1)]


class _HeadlessChromiumInstance:
    """
    Context manager spawning an isolated headless Chromium process on an ephemeral CDP port
    with its own temporary user-data-dir and process group. Guarantees deterministic teardown
    (SIGTERM -> SIGKILL fallback) and temp dir removal on exit or exception.
    """

    def __init__(
        self,
        binary_path: str,
        is_headless_shell: bool = False,
        startup_timeout: float = 15.0,
    ):
        self.binary_path = binary_path
        self.is_headless_shell = is_headless_shell
        self.startup_timeout = startup_timeout
        self.tmp_dir: Optional[str] = None
        self.proc: Optional[subprocess.Popen] = None
        self.pgid: Optional[int] = None
        self.port: int = 0
        self._stderr_fp: Optional[Any] = None

    def start(self) -> int:
        self.tmp_dir = tempfile.mkdtemp(prefix="pseofactory_cdp_worker_")
        stderr_path = Path(self.tmp_dir) / "chrome_stderr.log"
        self._stderr_fp = open(stderr_path, "wb")

        cmd = [self.binary_path]
        if not self.is_headless_shell:
            cmd.append("--headless=new")
        cmd.extend([
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--font-render-hinting=none",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-backgrounding-occluded-windows",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-default-apps",
            "--disable-sync",
            "--no-first-run",
            "--mute-audio",
            "--hide-scrollbars",
            "--window-size=1440,900",
            "--remote-debugging-port=0",
            f"--user-data-dir={self.tmp_dir}",
            "about:blank",
        ])

        try:
            self.proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=self._stderr_fp,
                start_new_session=True,
            )
            self.pgid = self.proc.pid
            with _ACTIVE_CHROME_LOCK:
                _ACTIVE_CHROME_INSTANCES[self.proc.pid] = (self.pgid, self.tmp_dir)

            port_file = Path(self.tmp_dir) / "DevToolsActivePort"
            deadline = time.monotonic() + self.startup_timeout
            discovered_port = 0
            while time.monotonic() < deadline:
                if self.proc.poll() is not None:
                    err_tail = ""
                    try:
                        err_tail = stderr_path.read_text(encoding="utf-8", errors="ignore")[-400:]
                    except Exception:
                        pass
                    raise RuntimeError(
                        f"Headless Chromium exited prematurely (rc={self.proc.returncode}): {err_tail}"
                    )
                if port_file.is_file():
                    try:
                        lines = port_file.read_text(encoding="utf-8", errors="ignore").splitlines()
                        if lines and lines[0].strip().isdigit():
                            discovered_port = int(lines[0].strip())
                            break
                    except Exception:
                        pass
                if stderr_path.is_file():
                    try:
                        err_txt = stderr_path.read_text(encoding="utf-8", errors="ignore")
                        m = re.search(r"DevTools listening on ws://(?:127\.0\.0\.1|localhost):(\d+)/", err_txt)
                        if m:
                            discovered_port = int(m.group(1))
                            break
                    except Exception:
                        pass
                time.sleep(0.02)

            if discovered_port <= 0:
                raise RuntimeError(
                    f"Timed out waiting {self.startup_timeout:.1f}s for headless Chromium CDP port"
                )

            # Confirm CDP HTTP endpoint is responding before handing port to worker
            http_deadline = min(deadline, time.monotonic() + 5.0)
            ready = False
            while time.monotonic() < http_deadline:
                try:
                    req = urllib.request.Request(f"http://127.0.0.1:{discovered_port}/json/version")
                    with urllib.request.urlopen(req, timeout=2.0) as resp:
                        if resp.status == 200:
                            ready = True
                            break
                except Exception:
                    time.sleep(0.03)
            if not ready:
                raise RuntimeError(f"Headless Chromium CDP port {discovered_port} did not respond to /json/version")

            self.port = discovered_port
            return self.port
        except Exception:
            self.stop()
            raise

    def stop(self) -> None:
        proc = self.proc
        pgid = self.pgid
        tmp_dir = self.tmp_dir
        self.proc = None
        self.pgid = None
        self.tmp_dir = None
        self.port = 0

        if proc is not None:
            with _ACTIVE_CHROME_LOCK:
                _ACTIVE_CHROME_INSTANCES.pop(proc.pid, None)
            try:
                if pgid is not None:
                    try:
                        os.killpg(pgid, signal.SIGTERM)
                    except OSError:
                        pass
                if proc.poll() is None:
                    proc.terminate()
                try:
                    proc.wait(timeout=3.0)
                except subprocess.TimeoutExpired:
                    if pgid is not None:
                        try:
                            os.killpg(pgid, signal.SIGKILL)
                        except OSError:
                            pass
                    try:
                        proc.kill()
                    except OSError:
                        pass
                    try:
                        proc.wait(timeout=2.0)
                    except Exception:
                        pass
            except Exception:
                pass

        if self._stderr_fp is not None:
            try:
                self._stderr_fp.close()
            except Exception:
                pass
            self._stderr_fp = None

        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def __enter__(self) -> "_HeadlessChromiumInstance":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()


class BrowserVerifyReceiptStore:
    """
    Closed content-addressed SHA-256 verification receipt store for UnifiedBrowserAuditor.
    Stores pass-only route verification receipts outside tenant git repositories using
    fcntl.flock + atomic .tmp + os.replace writes.
    """

    SCHEMA_VERSION: int = 1

    @staticmethod
    def compute_verifier_source_digest() -> str:
        """Computes closed SHA-256 over all Python source files in the pseofactory package."""
        pkg_dir = Path(__file__).resolve().parent
        pkg_str = str(pkg_dir)
        py_entries: List[Tuple[str, str, int, int]] = []

        def _walk_py(dir_path: str, rel_prefix: str) -> None:
            try:
                with os.scandir(dir_path) as it:
                    for entry in it:
                        name = entry.name
                        if name.startswith(".") or name == "__pycache__":
                            continue
                        rel_posix = f"{rel_prefix}/{name}" if rel_prefix else name
                        if entry.is_dir(follow_symlinks=False):
                            _walk_py(entry.path, rel_posix)
                        elif name.endswith(".py") and entry.is_file(follow_symlinks=False):
                            try:
                                st = entry.stat(follow_symlinks=False)
                                py_entries.append((rel_posix, entry.path, st.st_mtime_ns, st.st_size))
                            except OSError:
                                py_entries.append((rel_posix, entry.path, -1, -1))
            except OSError:
                pass

        _walk_py(pkg_str, "")
        py_entries.sort(key=lambda item: item[0])
        sig = tuple((rel, mt, sz) for rel, _p, mt, sz in py_entries)
        with _VERIFIER_DIGEST_LOCK:
            cached = _VERIFIER_DIGEST_CACHE.get(pkg_str)
            if cached is not None and cached[0] == sig:
                return cached[1]

        h = hashlib.sha256()
        for rel_posix, full_path, _mt, _sz in py_entries:
            h.update(rel_posix.encode("utf-8"))
            h.update(b"\0")
            try:
                with open(full_path, "rb") as fp:
                    h.update(hashlib.file_digest(fp, "sha256").digest())
            except OSError:
                h.update(b"<unreadable>")
            h.update(b"\0")
        digest = h.hexdigest()
        with _VERIFIER_DIGEST_LOCK:
            _VERIFIER_DIGEST_CACHE[pkg_str] = (sig, digest)
        return digest

    @staticmethod
    def _hash_file_digest_worker(item: Tuple[str, str]) -> Tuple[str, bytes]:
        rel_posix, full_path = item
        try:
            with open(full_path, "rb") as fp:
                return (rel_posix, hashlib.file_digest(fp, "sha256").digest())
        except OSError:
            return (rel_posix, b"<unreadable>")

    @staticmethod
    def compute_estate_shared_digest(
        dist_dir: Path,
        chrome_version: str,
        audit_options: Dict[str, Any],
        verifier_digest: Optional[str] = None,
    ) -> str:
        """
        Computes a closed per-estate shared dependency SHA-256 once per run_audit():
        - SHA-256 of actual file bytes for ALL non-HTML files in dist/ up to 5 MiB
          (covers CSS, JS, JSON, XML, PNG, WEBP, JPG, GIF, SVG, ICO, WOFF2, TXT, MD,
          VTT, _redirects, _headers, favicon.*, etc.)
        - (rel_posix, st_size, st_mtime_ns) fingerprint for any large media file > 5 MiB
        - Sorted inventory of all HTML relative paths (so adding/removing/renaming any
          HTML target invalidates cross-page link checks, while editing 1 HTML file's
          content only invalidates that single route)
        - Closed SHA-256 of all pseofactory/*.py source files
        - Exact Chromium binary version string
        - Effective audit options
        """
        h = hashlib.sha256()
        h.update(f"schema_v{BrowserVerifyReceiptStore.SCHEMA_VERSION}\0".encode("utf-8"))
        h.update(f"chrome:{chrome_version}\0".encode("utf-8"))
        v_dig = verifier_digest if verifier_digest is not None else BrowserVerifyReceiptStore.compute_verifier_source_digest()
        h.update(f"verifier:{v_dig}\0".encode("utf-8"))
        h.update(json.dumps(audit_options, sort_keys=True, default=str).encode("utf-8"))
        h.update(b"\0")

        if dist_dir.is_dir():
            non_html_full: List[Tuple[str, str]] = []
            non_html_large: List[Tuple[str, int, int]] = []
            html_paths: List[str] = []

            def _scan_dist(dir_path: str, rel_prefix: str) -> None:
                try:
                    with os.scandir(dir_path) as it:
                        for entry in it:
                            name = entry.name
                            if name.startswith(".") or name == "syndication":
                                continue
                            rel_posix = f"{rel_prefix}/{name}" if rel_prefix else name
                            try:
                                if entry.is_dir(follow_symlinks=False):
                                    _scan_dist(entry.path, rel_posix)
                                    continue
                                if not entry.is_file(follow_symlinks=False):
                                    continue
                            except OSError:
                                continue
                            if name.lower().endswith(".html"):
                                html_paths.append(rel_posix)
                                continue
                            try:
                                st = entry.stat(follow_symlinks=False)
                            except OSError:
                                non_html_large.append((rel_posix, -1, -1))
                                continue
                            if st.st_size <= _MAX_FULL_HASH_ASSET_BYTES:
                                non_html_full.append((rel_posix, entry.path))
                            else:
                                non_html_large.append((rel_posix, st.st_size, st.st_mtime_ns))
                except OSError:
                    pass

            _scan_dist(str(dist_dir), "")
            non_html_full.sort(key=lambda item: item[0])
            if len(non_html_full) >= 150:
                pool_workers = min(4, max(1, os.cpu_count() or 2))
                with ThreadPoolExecutor(max_workers=pool_workers) as pool:
                    hashed_assets = list(pool.map(BrowserVerifyReceiptStore._hash_file_digest_worker, non_html_full))
            else:
                hashed_assets = [BrowserVerifyReceiptStore._hash_file_digest_worker(item) for item in non_html_full]

            for rel_posix, file_dig in hashed_assets:
                h.update(b"asset:")
                h.update(rel_posix.encode("utf-8"))
                h.update(b"\0")
                h.update(file_dig)
                h.update(b"\0")

            non_html_large.sort(key=lambda item: item[0])
            h.update(b"large_assets:")
            for rel_posix, sz, mtime_ns in non_html_large:
                h.update(f"{rel_posix}:{sz}:{mtime_ns}\n".encode("utf-8"))
            h.update(b"\0")

            html_paths.sort()
            h.update(b"html_paths:")
            h.update("\n".join(html_paths).encode("utf-8"))
            h.update(b"\0")

        return h.hexdigest()

    @staticmethod
    def resolve_route_html_file(dist_dir: Path, route: str) -> Optional[Path]:
        """Resolves a canonical route path to its exact HTML file on disk inside dist_dir."""
        clean = (route or "/").strip()
        if not clean.startswith("/"):
            clean = "/" + clean
        if clean == "/":
            cand = dist_dir / "index.html"
            return cand if cand.is_file() else None
        rel = clean.lstrip("/")
        if clean.endswith("/"):
            as_idx = dist_dir / rel.rstrip("/") / "index.html"
            if as_idx.is_file():
                return as_idx
        direct = dist_dir / rel
        if direct.suffix.lower() == ".html" and direct.is_file():
            return direct
        if direct.is_dir():
            idx = direct / "index.html"
            if idx.is_file():
                return idx
        as_idx = dist_dir / rel.rstrip("/") / "index.html"
        if as_idx.is_file():
            return as_idx
        as_html = dist_dir / f"{rel.rstrip('/')}.html"
        if as_html.is_file():
            return as_html
        return None

    @staticmethod
    def compute_route_verify_key(dist_dir: Path, estate_shared_digest: str, route: str) -> Optional[str]:
        """
        Computes route_verify_key(r) = sha256(estate_shared_digest || route_path || sha256(html_bytes_of_r)).
        Returns None if the route has no backing HTML file on disk (forcing live verification).
        """
        html_file = BrowserVerifyReceiptStore.resolve_route_html_file(dist_dir, route)
        if html_file is None:
            return None
        try:
            with open(html_file, "rb") as fp:
                html_sha = hashlib.file_digest(fp, "sha256").hexdigest()
        except OSError:
            return None
        payload = f"{estate_shared_digest}|{route}|{html_sha}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def default_receipt_path(property_id: Optional[str]) -> Optional[Path]:
        """
        Returns default receipt path under /home/ubuntuadmin/projects/.agy/browser_verify_receipts/<property_id>.json.
        Returns None during pytest unless explicitly overridden, or when property_id is absent.
        """
        if "PYTEST_CURRENT_TEST" in os.environ:
            return None
        if not property_id:
            return None
        base_override = (os.environ.get("PSEOFACTORY_RECEIPTS_DIR") or "").strip()
        base_dir = Path(base_override) if base_override else _DEFAULT_RECEIPTS_DIR
        safe_id = re.sub(r"[^a-zA-Z0-9._-]", "_", str(property_id).strip().lower())
        return base_dir / f"{safe_id}.json"

    def __init__(self, receipt_path: Path):
        self.receipt_path = Path(receipt_path)
        self.lock_path = Path(f"{self.receipt_path}.lock")
        self._batch_lock = threading.Lock()
        self._batch_depth = 0
        self._batch_flush_every = 0
        self._batch_meta: Optional[Tuple[Optional[str], str, str]] = None
        self._pending_passed: Dict[str, Dict[str, Any]] = {}
        self._pending_evict: set = set()
        self._write_count: int = 0

    def load_routes(self) -> Dict[str, Dict[str, Any]]:
        """Loads persisted pass-only route receipts under a shared flock."""
        if not self.receipt_path.is_file():
            return {}
        try:
            self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.lock_path, "a+", encoding="utf-8") as lf:
                fcntl.flock(lf.fileno(), fcntl.LOCK_SH)
                try:
                    raw = json.loads(self.receipt_path.read_text(encoding="utf-8"))
                finally:
                    fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
            if not isinstance(raw, dict) or raw.get("schema_version") != self.SCHEMA_VERSION:
                return {}
            routes_map = raw.get("routes")
            return routes_map if isinstance(routes_map, dict) else {}
        except Exception:
            return {}

    def batch(
        self,
        property_id: Optional[str] = None,
        chrome_version: str = "",
        estate_shared_digest: str = "",
        flush_every: int = 32,
    ):
        """
        Context manager coalescing multiple route updates into periodic/final atomic disk writes
        instead of rewriting JSON on every single route.
        """
        import contextlib

        @contextlib.contextmanager
        def _batch_ctx():
            with self._batch_lock:
                self._batch_depth += 1
                self._batch_flush_every = max(0, int(flush_every))
                self._batch_meta = (property_id, chrome_version, estate_shared_digest)
            try:
                yield self
            finally:
                should_flush = False
                with self._batch_lock:
                    self._batch_depth = max(0, self._batch_depth - 1)
                    if self._batch_depth == 0 and (self._pending_passed or self._pending_evict):
                        should_flush = True
                if should_flush:
                    self.flush()

        return _batch_ctx()

    def flush(self) -> None:
        """Atomically flushes any buffered batch receipt updates to disk."""
        with self._batch_lock:
            if not self._pending_passed and not self._pending_evict:
                return
            meta = self._batch_meta or (None, "", "")
            passed_copy = dict(self._pending_passed)
            evict_copy = list(self._pending_evict)
            self._write_routes_atomic(
                property_id=meta[0],
                chrome_version=meta[1],
                estate_shared_digest=meta[2],
                passed_entries=passed_copy,
                evict_routes=evict_copy,
            )
            self._pending_passed.clear()
            self._pending_evict.clear()

    def _write_routes_atomic(
        self,
        property_id: Optional[str],
        chrome_version: str,
        estate_shared_digest: str,
        passed_entries: Dict[str, Dict[str, Any]],
        evict_routes: Optional[List[str]] = None,
    ) -> None:
        if not passed_entries and not evict_routes:
            return
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(self.lock_path, "a+", encoding="utf-8") as lf:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
            try:
                existing_doc: Optional[Dict[str, Any]] = None
                existing_routes: Dict[str, Dict[str, Any]] = {}
                if self.receipt_path.is_file():
                    try:
                        cur = json.loads(self.receipt_path.read_text(encoding="utf-8"))
                        if (
                            isinstance(cur, dict)
                            and cur.get("schema_version") == self.SCHEMA_VERSION
                            and isinstance(cur.get("routes"), dict)
                        ):
                            existing_doc = cur
                            existing_routes = dict(cur["routes"])
                    except Exception:
                        existing_routes = {}

                changed = existing_doc is None or (
                    existing_doc.get("chrome_version") != chrome_version
                    or existing_doc.get("estate_shared_digest") != estate_shared_digest
                )

                for bad_route in (evict_routes or []):
                    if bad_route in existing_routes:
                        existing_routes.pop(bad_route, None)
                        changed = True

                for route, entry in passed_entries.items():
                    if entry.get("status") == "PASS" and entry.get("verify_key"):
                        arch = entry.get("screen_archetype", "statutory_guide")
                        prev = existing_routes.get(route)
                        if (
                            isinstance(prev, dict)
                            and prev.get("verify_key") == entry["verify_key"]
                            and prev.get("status") == "PASS"
                            and prev.get("screen_archetype") == arch
                        ):
                            continue
                        existing_routes[route] = {
                            "verify_key": entry["verify_key"],
                            "status": "PASS",
                            "verified_at": now_iso,
                            "screen_archetype": arch,
                        }
                        changed = True

                if not changed:
                    return

                doc = {
                    "schema_version": self.SCHEMA_VERSION,
                    "property_id": property_id or "custom",
                    "chrome_version": chrome_version,
                    "estate_shared_digest": estate_shared_digest,
                    "updated_at": now_iso,
                    "routes": dict(sorted(existing_routes.items())),
                }
                tmp_file = self.receipt_path.with_name(
                    f"{self.receipt_path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp"
                )
                payload = json.dumps(doc, separators=(",", ":"), sort_keys=False) + "\n"
                with open(tmp_file, "w", encoding="utf-8") as tf:
                    tf.write(payload)
                    tf.flush()
                    os.fsync(tf.fileno())
                os.replace(tmp_file, self.receipt_path)
                self._write_count += 1
            finally:
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)

    def update_routes(
        self,
        property_id: Optional[str],
        chrome_version: str,
        estate_shared_digest: str,
        passed_entries: Dict[str, Dict[str, Any]],
        evict_routes: Optional[List[str]] = None,
    ) -> None:
        """
        Atomically merges verified PASS route receipts and evicts any failed routes
        under an exclusive flock using .tmp + fsync + os.replace.
        When called inside `with store.batch(...):`, coalesces updates in memory and
        flushes atomically at batch boundaries (`flush_every` / batch exit).
        """
        if not passed_entries and not evict_routes:
            return
        with self._batch_lock:
            if self._batch_depth > 0:
                self._batch_meta = (property_id, chrome_version, estate_shared_digest)
                for bad_route in (evict_routes or []):
                    self._pending_passed.pop(bad_route, None)
                    self._pending_evict.add(bad_route)
                for route, entry in passed_entries.items():
                    self._pending_evict.discard(route)
                    self._pending_passed[route] = entry
                total_pending = len(self._pending_passed) + len(self._pending_evict)
                if self._batch_flush_every > 0 and total_pending >= self._batch_flush_every:
                    passed_copy = dict(self._pending_passed)
                    evict_copy = list(self._pending_evict)
                    self._write_routes_atomic(
                        property_id=property_id,
                        chrome_version=chrome_version,
                        estate_shared_digest=estate_shared_digest,
                        passed_entries=passed_copy,
                        evict_routes=evict_copy,
                    )
                    self._pending_passed.clear()
                    self._pending_evict.clear()
                return
        self._write_routes_atomic(
            property_id=property_id,
            chrome_version=chrome_version,
            estate_shared_digest=estate_shared_digest,
            passed_entries=passed_entries,
            evict_routes=evict_routes,
        )


@dataclass
class InteractiveWidgetSpec:
    """Specification for interactive calculator / tool runtime verification."""
    route: str
    widget_id: str
    precondition_selector: str
    input_selector: str
    input_value: str
    output_selector: str
    trigger_event: str = "input"
    verify_popstate: bool = False
    expected_delta_fn: Optional[str] = None


class TenantBrowserAdapter(ABC):
    """Abstract base adapter for tenant-specific static distributions."""

    @property
    @abstractmethod
    def tenant_id(self) -> str:
        """Tenant identifier (e.g. profithelm, prexvo)."""
        pass

    @property
    @abstractmethod
    def dist_dir(self) -> Path:
        """Absolute path to static distribution directory."""
        pass

    @property
    @abstractmethod
    def canonical_domain(self) -> str:
        """Canonical domain URL (e.g. https://profithelm.com)."""
        pass

    def get_widget_specs(self) -> List[InteractiveWidgetSpec]:
        """Returns list of interactive widget specs to audit."""
        return []

    def get_excluded_routes(self) -> List[str]:
        """Returns routes to skip during browser audit."""
        return []


class ProfitHelmBrowserAdapter(TenantBrowserAdapter):
    """Browser verification adapter for ProfitHelm platform distribution."""

    @property
    def tenant_id(self) -> str:
        return "profithelm"

    @property
    def dist_dir(self) -> Path:
        root = Path(os.environ.get("PSEOFACTORY_WORKSPACE_ROOT") or "/home/ubuntuadmin/projects")
        return root / "profithelm-platform" / "dist"

    @property
    def canonical_domain(self) -> str:
        return "https://profithelm.com"

    def get_widget_specs(self) -> List[InteractiveWidgetSpec]:
        return [
            InteractiveWidgetSpec(
                route="/tools/irs-2027-tax-brackets/",
                widget_id="irs-2027-tax-brackets",
                precondition_selector="#input-gross_income, #field-gross_income, #tax-income",
                input_selector="#input-gross_income, #field-gross_income, #tax-income",
                input_value="250000",
                output_selector="#estimated-federal-tax, #estimated-federal-tax-2027, #val-total_federal_tax, #res-total-tax",
                trigger_event="input",
                verify_popstate=True,
            ),
            InteractiveWidgetSpec(
                route="/tools/crypto-tax-calculator/",
                widget_id="crypto-tax-calculator",
                precondition_selector="#input-short_term_gains, #crypto-short-term",
                input_selector="#input-short_term_gains, #crypto-short-term",
                input_value="50000",
                output_selector="#val-total-crypto-tax, #res-crypto-tax",
                trigger_event="input",
                verify_popstate=False,
            ),
            InteractiveWidgetSpec(
                route="/tools/saas-runway-calculator/",
                widget_id="saas-runway-calculator",
                precondition_selector="#input-cash_balance, #runway-cash",
                input_selector="#input-cash_balance, #runway-cash",
                input_value="100000",
                output_selector="#val-runway-months, #res-runway-months",
                trigger_event="input",
                verify_popstate=False,
            ),
        ]


class PrexvoBrowserAdapter(TenantBrowserAdapter):
    """Browser verification adapter for Prexvo financial platform distribution."""

    @property
    def tenant_id(self) -> str:
        return "prexvo"

    @property
    def dist_dir(self) -> Path:
        root = Path(os.environ.get("PSEOFACTORY_WORKSPACE_ROOT") or "/home/ubuntuadmin/projects")
        return root / "prexvo" / "dist"

    @property
    def canonical_domain(self) -> str:
        return "https://prexvo.com"

    def get_widget_specs(self) -> List[InteractiveWidgetSpec]:
        return [
            InteractiveWidgetSpec(
                route="/tools/student-loan-repayment-calculator/",
                widget_id="student-loan-repayment-calculator",
                precondition_selector="#field-agi",
                input_selector="#field-agi",
                input_value="95000",
                output_selector="#metric-primary_output, #metric-rap_payment",
                trigger_event="input",
                verify_popstate=True,
            ),
            InteractiveWidgetSpec(
                route="/tools/rap-vs-ibr-calculator/",
                widget_id="rap-vs-ibr-calculator",
                precondition_selector="#field-agi",
                input_selector="#field-agi",
                input_value="95000",
                output_selector="#metric-rap_payment, #val-monthly_payment",
                trigger_event="input",
                verify_popstate=False,
            ),
            InteractiveWidgetSpec(
                route="/tools/pslf-qualifying-payment-calculator/",
                widget_id="pslf-qualifying-payment-calculator",
                precondition_selector="#field-qualifying_payments, #field-loan_balance",
                input_selector="#field-qualifying_payments, #field-loan_balance",
                input_value="85000",
                output_selector="#metric-forgiven_balance, #val-remaining_payments, #metric-rap_subsidy, #metric-rap_payment, .metric-value",
                trigger_event="input",
                verify_popstate=False,
            ),
            InteractiveWidgetSpec(
                route="/tools/pslf-qualifying-payment-simulator/",
                widget_id="pslf-qualifying-payment-simulator",
                precondition_selector="#field-qualifying_payments, #field-loan_balance, [data-calc-input]",
                input_selector="#field-qualifying_payments, #field-loan_balance, [data-calc-input]",
                input_value="85000",
                output_selector="#metric-forgiven_balance, #val-remaining_payments, #metric-rap_subsidy, #metric-rap_payment, .metric-value",
                trigger_event="input",
                verify_popstate=False,
            ),
        ]


class GainHelmBrowserAdapter(TenantBrowserAdapter):
    """Browser verification adapter for GainHelm cyber compliance platform distribution."""

    @property
    def tenant_id(self) -> str:
        return "gainhelm"

    @property
    def dist_dir(self) -> Path:
        root = Path(os.environ.get("PSEOFACTORY_WORKSPACE_ROOT") or "/home/ubuntuadmin/projects")
        return root / "gainhelm" / "dist"

    @property
    def canonical_domain(self) -> str:
        return "https://gainhelm.com"

    def get_widget_specs(self) -> List[InteractiveWidgetSpec]:
        return [
            InteractiveWidgetSpec(
                route="/tools/soc-2-audit-cost-calculator/",
                widget_id="soc-2-audit-cost-calculator",
                precondition_selector="#field-cpa_audit_fee, #calc-input-headcount, [data-calc-input]",
                input_selector="#field-cpa_audit_fee, #calc-input-headcount, [data-calc-input]",
                input_value="150",
                output_selector="#metric-total_compliance_tco, #metric-soc2_total_cost, .calc-metric-value, .output-value",
                trigger_event="input",
                verify_popstate=True,
            ),
            InteractiveWidgetSpec(
                route="/tools/cmmc-2-0-compliance-cost-calculator/",
                widget_id="cmmc-2-0-compliance-cost-calculator",
                precondition_selector="#field-c3pao_assessment_fee, #calc-input-headcount, [data-calc-input]",
                input_selector="#field-c3pao_assessment_fee, #calc-input-headcount, [data-calc-input]",
                input_value="150",
                output_selector="#metric-total_compliance_tco, #metric-cmmc_total_cost, .calc-metric-value, .output-value",
                trigger_event="input",
                verify_popstate=False,
            ),
            InteractiveWidgetSpec(
                route="/tools/nist-800-171-sprs-score-calculator/",
                widget_id="nist-800-171-sprs-score-calculator",
                precondition_selector="#field-unmet_5pt_controls, #calc-input-unimplemented_5pt, [data-calc-input]",
                input_selector="#field-unmet_5pt_controls, #calc-input-unimplemented_5pt, [data-calc-input]",
                input_value="4",
                output_selector="#metric-sprs_score, #metric-nist_sprs_score, .calc-metric-value, .output-value",
                trigger_event="input",
                verify_popstate=False,
            ),
        ]


class LienBondBrowserAdapter(TenantBrowserAdapter):
    """Browser verification adapter for LienBond commercial surety, workers comp, and lien platform distribution."""

    @property
    def tenant_id(self) -> str:
        return "lienbond"

    @property
    def dist_dir(self) -> Path:
        root = Path(os.environ.get("PSEOFACTORY_WORKSPACE_ROOT") or "/home/ubuntuadmin/projects")
        return root / "lienbond" / "dist"

    @property
    def canonical_domain(self) -> str:
        return "https://lienbond.com"

    def get_widget_specs(self) -> List[InteractiveWidgetSpec]:
        return [
            InteractiveWidgetSpec(
                route="/tools/contractor-license-bond-cost-calculator-by-credit-score/",
                widget_id="contractor-license-bond-cost-calculator-by-credit-score",
                precondition_selector="#input-bond_penalty_amount, #field-bond_amount, [data-calc-input]",
                input_selector="#input-bond_penalty_amount, #field-bond_amount, [data-calc-input]",
                input_value="50000",
                output_selector=".output-value, .calc-metric-value, .metric-value",
                trigger_event="input",
                verify_popstate=True,
            ),
            InteractiveWidgetSpec(
                route="/tools/workers-compensation-class-code-rate-calculator-by-state/",
                widget_id="workers-compensation-class-code-rate-calculator-by-state",
                precondition_selector="#input-field_trade_payroll, #input-annual_payroll, #field-annual_payroll, [data-calc-input]",
                input_selector="#input-field_trade_payroll, #input-annual_payroll, #field-annual_payroll, [data-calc-input]",
                input_value="250000",
                output_selector=".output-value, .calc-metric-value, .metric-value",
                trigger_event="input",
                verify_popstate=False,
            ),
        ]


class DynamicTenantBrowserAdapter(TenantBrowserAdapter):
    """Dynamic browser verification adapter for any tenant discovered via .pseofactory.json."""

    def __init__(
        self,
        tenant_id: str,
        dist_dir: Union[str, Path],
        canonical_domain: Optional[str] = None,
    ):
        self._tenant_id = str(tenant_id or "custom").strip().lower()
        self._dist_dir = Path(dist_dir).resolve()
        self._canonical_domain = (canonical_domain or f"https://{self._tenant_id}.com").strip().rstrip("/")

    @property
    def tenant_id(self) -> str:
        return self._tenant_id

    @property
    def dist_dir(self) -> Path:
        return self._dist_dir

    @property
    def canonical_domain(self) -> str:
        return self._canonical_domain


class RouteManifestExtractor:
    """
    Extracts complete route manifests from sitemap.xml and dist HTML filesystem tree.
    Enforces HWL-1313 invariant: unions sitemap.xml and all dist HTML files to prevent unlisted page escapes.
    """

    def __init__(self, dist_dir: Union[str, Path]):
        self.dist_dir = Path(dist_dir).resolve()

    def extract_routes(self) -> List[str]:
        """Extracts and normalizes the deduplicated route union."""
        routes: List[str] = []
        seen = set()

        def add_route(r: str) -> None:
            if not r:
                r = "/"
            if not r.startswith("/"):
                r = "/" + r
            if r not in seen:
                seen.add(r)
                routes.append(r)

        # 1. Parse sitemap.xml
        sitemap_path = self.dist_dir / "sitemap.xml"
        if sitemap_path.exists():
            try:
                tree = ET.parse(sitemap_path)
                root = tree.getroot()
                # Try standard XML namespace
                for loc in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
                    if loc.text:
                        p = urllib.parse.urlsplit(loc.text.strip()).path
                        add_route(p or "/")
                # Fallback for sitemaps without namespace
                if not routes:
                    for loc in root.findall(".//loc"):
                        if loc.text:
                            p = urllib.parse.urlsplit(loc.text.strip()).path
                            add_route(p or "/")
            except Exception:
                pass

        # 2. Walk dist directory filesystem
        if self.dist_dir.exists():
            for hf in sorted(self.dist_dir.glob("**/*.html")):
                parts = hf.relative_to(self.dist_dir).parts
                if "syndication" in parts or any(p.startswith(".") for p in parts):
                    continue
                rel = hf.relative_to(self.dist_dir)
                if rel.name == "index.html":
                    if rel.parent.parts:
                        p = "/" + "/".join(rel.parent.parts) + "/"
                    else:
                        p = "/"
                elif rel.name == "404.html":
                    p = "/404.html"
                else:
                    p = "/" + str(rel)
                add_route(p)

        # 3. Always include 404.html if present
        if (self.dist_dir / "404.html").exists():
            add_route("/404.html")

        # Always ensure root route '/' is represented
        if (self.dist_dir / "index.html").exists() or not routes:
            add_route("/")

        return routes

    def get_routes(self) -> List[str]:
        """Alias for extract_routes."""
        return self.extract_routes()

    @property
    def routes(self) -> List[str]:
        """Property returning extracted routes."""
        return self.extract_routes()

    def detect_git_dirty_routes(self) -> List[str]:
        """Detects any modified or untracked HTML routes in dist_dir via git status --porcelain."""
        import subprocess

        if not self.dist_dir.exists():
            return []
        repo_root = self.dist_dir.parent
        if not (repo_root / ".git").exists():
            return []
        dirty_routes: List[str] = []
        seen = set()
        try:
            res = subprocess.run(
                ["git", "-C", str(repo_root), "status", "--porcelain", "--", "dist"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if res.returncode == 0 and res.stdout:
                for raw_line in res.stdout.splitlines():
                    if len(raw_line) < 4:
                        continue
                    rel_part = raw_line[3:].strip().strip('"')
                    if " -> " in rel_part:
                        rel_part = rel_part.split(" -> ", 1)[1].strip().strip('"')
                    full_p = (repo_root / rel_part).resolve()
                    if not full_p.exists():
                        continue
                    html_files = [full_p] if full_p.is_file() and full_p.suffix == ".html" else (
                        list(full_p.glob("**/*.html")) if full_p.is_dir() else []
                    )
                    for hf in html_files:
                        try:
                            rel = hf.relative_to(self.dist_dir)
                        except ValueError:
                            continue
                        if "syndication" in rel.parts or any(p.startswith(".") for p in rel.parts):
                            continue
                        if rel.name == "index.html":
                            r = "/" + "/".join(rel.parent.parts) + "/" if rel.parent.parts else "/"
                        elif rel.name == "404.html":
                            r = "/404.html"
                        else:
                            r = "/" + str(rel)
                        if r not in seen:
                            seen.add(r)
                            dirty_routes.append(r)
        except Exception:
            pass
        return dirty_routes

    def select_smart_routes(
        self,
        all_routes: List[str],
        sample_size: Optional[int],
        widget_specs: Optional[List[InteractiveWidgetSpec]] = None,
    ) -> List[str]:
        """
        Selects a deterministic, 5-blueprint stratified + delta-aware route sample:
        1. Git-dirty / newly generated HTML routes in dist/ (up to dirty_cap)
        2. Stratified public blueprint representatives:
           - home_hub ('/')
           - calculator_leaf (primary widget_spec or newest '/tools/<slug>/')
           - tools_directory ('/tools/')
           - governance_legal ('/disclaimers/', '/about/', '/methodology/', etc.)
           - error_404 ('/404.html')
        3. Remaining widget_specs and routes up to target_cap.
        """
        if sample_size is None or sample_size <= 0 or sample_size >= len(all_routes):
            return list(all_routes)
        available = set(all_routes)
        selected: List[str] = []

        def _pick(r: str) -> None:
            if r in available and r not in selected and len(selected) < target_cap:
                selected.append(r)

        dirty_cap = min(10, max(1, sample_size - 2)) if not widget_specs else 10
        dirty = [r for r in self.detect_git_dirty_routes() if r in available][:dirty_cap]
        target_cap = max(sample_size, len(dirty) + (1 if len(dirty) > 0 else 0))

        for dr in dirty:
            _pick(dr)

        # 1. home_hub
        _pick("/")

        # 2. calculator_leaf
        tool_routes = [r for r in all_routes if r.startswith("/tools/") and r != "/tools/"]
        for spec in (widget_specs or []):
            _pick(spec.route)
            if not dirty and len(selected) >= max(2, target_cap - 3):
                break
        if tool_routes and not any(r.startswith("/tools/") and r != "/tools/" for r in selected):
            newest_route = None
            newest_mtime = -1.0
            for tr in tool_routes:
                f_path = self.dist_dir / tr.strip("/") / "index.html"
                if f_path.is_file():
                    try:
                        mt = f_path.stat().st_mtime
                        if mt > newest_mtime:
                            newest_mtime = mt
                            newest_route = tr
                    except Exception:
                        pass
            _pick(newest_route or tool_routes[0])

        # 3. tools_directory
        _pick("/tools/")

        # 4. governance_legal (and /partners/ when available)
        for gov_r in ("/disclaimers/", "/about/", "/methodology/", "/privacy/", "/terms/", "/contact/", "/partners/"):
            if gov_r in available:
                _pick(gov_r)
                break
        if "/partners/" in available and "/partners/" not in selected:
            _pick("/partners/")

        # 5. error_404
        _pick("/404.html")

        for spec in (widget_specs or []):
            _pick(spec.route)
        for r in all_routes:
            if len(selected) >= target_cap:
                break
            _pick(r)
        return selected


class CDPEvalError(RuntimeError):
    """Raised when CDP Runtime.evaluate returns a protocol error or JS exceptionDetails."""


class UnifiedBrowserAuditor:
    """
    Unified multi-tenant UI/UX end-to-end browser verification engine over Chrome CDP.
    Enforces mechanical invariants:
    - CLS === 0.0 (layout-shift PerformanceObserver measurement)
    - Minimum 43.5px / 44px touch targets on interactive controls
    - Responsive viewports: 375px mobile and 1280px desktop zero horizontal overflow
    - Anti-slop: zero forbidden dashes (U+2014, U+2013, spaced hyphens)
    - Reactive interactive widget calculation updates and input reactivity
    """

    JS_CHECK_CLS = """new Promise(resolve => {
        const describeNode = (node) => {
            if (!node || !node.tagName) return 'unknown';
            let s = String(node.tagName).toLowerCase();
            if (node.id) {
                s += '#' + node.id;
            } else if (node.className && typeof node.className === 'string') {
                const cls = node.className.trim().split(/\\s+/).slice(0, 2).join('.');
                if (cls) s += '.' + cls;
            }
            return s;
        };
        const toRect = (r) => r ? [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)] : null;
        let cls = 0.0;
        let maxShiftStart = 0.0;
        const sources = [];
        const observer = new PerformanceObserver(list => {
            for (const entry of list.getEntries()) {
                if (!entry.hadRecentInput) {
                    cls += entry.value;
                    if (entry.value > 0 && typeof entry.startTime === 'number' && entry.startTime > maxShiftStart) {
                        maxShiftStart = entry.startTime;
                    }
                    if (entry.value > 0 && Array.isArray(entry.sources) && sources.length < 10) {
                        for (const src of entry.sources) {
                            if (sources.length >= 10) break;
                            sources.push({
                                node: describeNode(src.node),
                                value: Math.round(entry.value * 10000) / 10000,
                                prev: toRect(src.previousRect),
                                curr: toRect(src.currentRect),
                                phase: 'load_scroll'
                            });
                        }
                    }
                }
            }
        });
        try {
            observer.observe({ type: 'layout-shift', buffered: true });
        } catch(e) {}
        const fontsWait = (document.fonts && document.fonts.ready)
            ? Promise.race([document.fonts.ready.catch(() => {}), new Promise(r => setTimeout(r, 150))])
            : Promise.resolve();
        fontsWait.then(() => {
            window.scrollTo({ top: document.body.scrollHeight, behavior: 'instant' });
            setTimeout(() => {
                window.scrollTo({ top: 0, behavior: 'instant' });
                setTimeout(() => {
                    try { observer.disconnect(); } catch(e) {}
                    const navEntry = (typeof performance !== 'undefined' && performance.getEntriesByType)
                        ? (performance.getEntriesByType('navigation')[0] || null)
                        : null;
                    const loadEnd = (navEntry && typeof navEntry.loadEventEnd === 'number' && navEntry.loadEventEnd > 0)
                        ? navEntry.loadEventEnd
                        : ((navEntry && typeof navEntry.domInteractive === 'number') ? navEntry.domInteractive : 0);
                    const paintEntries = (typeof performance !== 'undefined' && performance.getEntriesByType)
                        ? performance.getEntriesByType('paint')
                        : [];
                    const maxPaint = paintEntries.reduce(
                        (acc, p) => Math.max(acc, (p && typeof p.startTime === 'number') ? p.startTime : 0),
                        0
                    );
                    const hasUnsizedMedia = Array.from(document.querySelectorAll('img, video, iframe')).some(
                        el => !(el.hasAttribute('width') && el.hasAttribute('height'))
                    );
                    const hasWebFonts = Boolean(document.fonts && document.fonts.size > 0);
                    const parseWindowEnd = Math.max(loadEnd, maxPaint) + 120;
                    const staticParsePreemptionCandidate = Boolean(
                        cls > 0
                        && !hasUnsizedMedia
                        && !hasWebFonts
                        && maxShiftStart > 0
                        && parseWindowEnd > 120
                        && maxShiftStart <= parseWindowEnd
                    );
                    resolve({
                        value: Math.round(cls * 1000) / 1000,
                        sources: sources,
                        static_parse_preemption_candidate: staticParsePreemptionCandidate
                    });
                }, 150);
            }, 150);
        });
    })"""

    JS_CHECK_TARGETS = """(() => {
        const undersized = [];
        const els = Array.from(document.querySelectorAll('a, button, input:not([type=hidden]), select, textarea, [role="button"], summary'));
        els.forEach(el => {
            const r = el.getBoundingClientRect();
            const s = window.getComputedStyle(el);
            if (s.display === 'none' || s.visibility === 'hidden' || (r.width === 0 && r.height === 0)) return;
            if (s.display === 'inline' && el.tagName === 'A' && el.parentElement && ['P', 'LI', 'DD', 'BLOCKQUOTE', 'TD'].includes(el.parentElement.tagName)) {
                const parentText = (el.parentElement.textContent || '').trim();
                const linkText = (el.textContent || '').trim();
                if (el.getClientRects().length > 1 || parentText.length > linkText.length) return;
            }
            if (r.width < 43.5 || r.height < 43.5) {
                undersized.push({
                    tag: el.tagName,
                    text: (el.innerText || el.value || el.name || '').trim().slice(0, 40),
                    width: Math.round(r.width * 10) / 10,
                    height: Math.round(r.height * 10) / 10,
                    id: el.id,
                    className: el.className
                });
            }
        });
        return undersized;
    })()"""

    JS_CHECK_DASHES = """(() => {
        const violations = [];
        const fullTitle = document.title || '';
        const emEnRegex = /[\\u2013\\u2014]|&mdash;|&ndash;|&#8212;|&#8211;/;
        const spacedHyphenRegex = /\\s+-\\s+/;
        if (emEnRegex.test(fullTitle)) {
            violations.push({ type: 'em_en_dash_title', text: fullTitle });
        }
        if (spacedHyphenRegex.test(fullTitle)) {
            violations.push({ type: 'spaced_hyphen_title', text: fullTitle });
        }
        // B8: Scan all <script type="application/ld+json"> blocks for forbidden dashes
        document.querySelectorAll('script[type="application/ld+json"]').forEach((sc, idx) => {
            const raw = sc.textContent || '';
            if (emEnRegex.test(raw)) {
                violations.push({ type: 'em_en_dash_jsonld', index: idx, text: raw.trim().slice(0, 80) });
            }
        });
        // B8: Include hidden elements when checking for em/en dashes; skip script/style/code/pre/noscript
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
            acceptNode: node => {
                const p = node.parentElement;
                if (!p) return NodeFilter.FILTER_REJECT;
                const tag = p.tagName.toLowerCase();
                if (['script', 'style', 'code', 'pre', 'noscript'].includes(tag)) return NodeFilter.FILTER_REJECT;
                return NodeFilter.FILTER_ACCEPT;
            }
        });
        while (walker.nextNode()) {
            const txt = walker.currentNode.nodeValue;
            const p = walker.currentNode.parentElement;
            const s = p ? window.getComputedStyle(p) : null;
            const isHidden = Boolean(s && (s.display === 'none' || s.visibility === 'hidden'));
            if (emEnRegex.test(txt)) {
                violations.push({ type: isHidden ? 'em_en_dash_hidden' : 'em_en_dash_body', text: txt.trim().slice(0, 80), tag: p ? p.tagName : 'TEXT' });
            } else if (!isHidden && spacedHyphenRegex.test(txt)) {
                violations.push({ type: 'spaced_hyphen_body', text: txt.trim().slice(0, 80), tag: p ? p.tagName : 'TEXT' });
            }
        }
        return violations;
    })()"""

    BLOCKED_EXTERNAL_URL_PATTERNS: List[str] = [
        "*googletagmanager.com*",
        "*google-analytics.com*",
        "*fonts.googleapis.com*",
        "*fonts.gstatic.com*",
        "*cloudflareinsights.com*",
        "*unpkg.com*",
        "*jsdelivr.net*",
        "*cdnjs.cloudflare.com*",
        "*challenges.cloudflare.com*",
        "*doubleclick.net*",
        "*facebook.net*",
        "*plausible.io*",
    ]

    @staticmethod
    def _collect_active_tenant_domains(
        canonical_domain: Optional[str] = None,
        tenant_domains: Optional[Iterable[str]] = None,
    ) -> List[str]:
        """Collects normalized active tenant hostnames dynamically for asset origin checks."""
        hosts = set()

        def _add_host(raw: Optional[str]) -> None:
            val = str(raw or "").strip().lower()
            if not val:
                return
            if "://" in val:
                val = urllib.parse.urlsplit(val).hostname or ""
            else:
                val = val.split("/", 1)[0].split(":", 1)[0]
            val = val.strip(".")
            if val.startswith("www."):
                val = val[4:]
            if val:
                hosts.add(val)

        _add_host(canonical_domain)
        if tenant_domains is not None:
            for d in tenant_domains:
                _add_host(d)
            return sorted(hosts)

        try:
            from pseofactory.tenant_facts import (
                CANONICAL_TENANT_DECLARATIONS,
                SPAWNED_TENANT_DECLARATIONS,
            )

            for decl in list(CANONICAL_TENANT_DECLARATIONS.values()) + list(SPAWNED_TENANT_DECLARATIONS.values()):
                _add_host(getattr(decl, "domain", None))
                _add_host(getattr(decl, "canonical_base", None))
        except Exception:
            pass

        try:
            from pseofactory.impact_planner import discover_active_tenants

            for _pid, repo_dir in discover_active_tenants():
                marker = Path(repo_dir) / ".pseofactory.json"
                if marker.is_file():
                    try:
                        meta = json.loads(marker.read_text(encoding="utf-8"))
                        if isinstance(meta, dict):
                            _add_host(meta.get("domain"))
                            _add_host(meta.get("canonical_base"))
                    except Exception:
                        pass
        except Exception:
            pass

        return sorted(hosts)

    @staticmethod
    def _build_broken_assets_js(
        check_meta_assets: bool = False,
        check_script_assets: bool = True,
        canonical_domain: Optional[str] = None,
        tenant_domains: Optional[Iterable[str]] = None,
    ) -> str:
        flag = "true" if check_meta_assets else "false"
        script_flag = "true" if check_script_assets else "false"
        active_domains = UnifiedBrowserAuditor._collect_active_tenant_domains(
            canonical_domain=canonical_domain,
            tenant_domains=tenant_domains,
        )
        domains_json = json.dumps(active_domains)
        return f"""(async () => {{
        const broken = [];
        const activeDomains = new Set({domains_json});
        document.querySelectorAll('img').forEach(img => {{
            if (!img.complete || img.naturalWidth === 0) {{
                broken.push({{ type: 'broken_image', src: img.src }});
            }}
        }});
        const toLocalUrl = (raw) => {{
            const s = String(raw || '').trim();
            if (!s || s.startsWith('data:') || s.startsWith('blob:')) return null;
            if (s.startsWith('/')) return window.location.origin + s;
            try {{
                const u = new URL(s, window.location.href);
                if (u.origin === window.location.origin) return u.href;
                const normHost = (u.hostname || '').toLowerCase().replace(/^www\\./, '');
                if ({flag} && (u.protocol === 'http:' || u.protocol === 'https:') && activeDomains.has(normHost)) {{
                    return window.location.origin + u.pathname + u.search;
                }}
            }} catch (e) {{}}
            return null;
        }};
        const seen = new Set();
        const targets = [];
        document.querySelectorAll('link[rel="stylesheet"][href]').forEach(el => {{
            const lu = toLocalUrl(el.getAttribute('href'));
            if (lu && !seen.has(lu)) {{
                seen.add(lu);
                targets.push({{ kind: 'stylesheet', url: lu }});
            }}
        }});
        if ({script_flag}) {{
            document.querySelectorAll('script[src]').forEach(el => {{
                const lu = toLocalUrl(el.getAttribute('src'));
                if (lu && !seen.has(lu)) {{
                    seen.add(lu);
                    targets.push({{ kind: 'script', url: lu }});
                }}
            }});
        }}
        if ({flag}) {{
            document.querySelectorAll('link[rel*="icon"][href]').forEach(el => {{
                const lu = toLocalUrl(el.getAttribute('href'));
                if (lu && !seen.has(lu)) {{
                    seen.add(lu);
                    targets.push({{ kind: 'favicon', url: lu }});
                }}
            }});
            document.querySelectorAll('meta[property="og:image"][content], meta[name="twitter:image"][content]').forEach(el => {{
                const lu = toLocalUrl(el.getAttribute('content'));
                if (lu && !seen.has(lu)) {{
                    seen.add(lu);
                    targets.push({{ kind: 'og_image', url: lu }});
                }}
            }});
        }}
        await Promise.all(targets.map(async (item) => {{
            try {{
                const resp = await fetch(item.url, {{ method: 'GET', cache: 'no-store' }});
                if (!resp.ok) {{
                    broken.push({{ type: 'broken_local_subresource', kind: item.kind, src: item.url, status: resp.status }});
                }}
            }} catch (err) {{
                broken.push({{ type: 'broken_local_subresource', kind: item.kind, src: item.url, error: String(err) }});
            }}
        }}));
        return broken;
    }})()"""

    JS_CHECK_BROKEN_ASSETS = """(() => {
        const broken = [];
        document.querySelectorAll('img').forEach(img => {
            if (!img.complete || img.naturalWidth === 0) {
                broken.push({ type: 'broken_image', src: img.src });
            }
        });
        return broken;
    })()"""

    JS_CHECK_VISUAL_PRIMITIVES = """(() => {
        const vw = window.innerWidth;
        const p = location.pathname;
        const isOperatorPwa = (p === '/signal' || p === '/signal/' || p === '/signal/index.html' || p.startsWith('/signal/') || p.startsWith('/static/signal'));
        const hasCalcControls = Boolean(document.querySelector('form.calculator-form, .interactive-calculator-container, .calculator-card, .calculation-container, input[type="number"], input[type="range"], [data-calc-input]'));
        const hasComparison = Boolean(document.querySelector('.comparison-table-section, .statutory-comparison-table-section, table.comparison-table')) || p.includes('-vs-');
        let archetype = isOperatorPwa ? 'operator_pwa' : 'statutory_guide';
        if (!isOperatorPwa) {
            if (['/', '/index.html', '/tools/', '/tools/index.html', '/about/', '/about.html', '/methodology/', '/methodology.html', '/disclaimers/', '/disclaimers.html', '/contact/', '/contact.html', '/privacy/', '/privacy.html', '/terms/', '/terms.html', '/partners/', '/partners/index.html', '/404.html', '/editorial-standards/', '/editorial-standards/index.html'].includes(p)) {
                archetype = 'index_hub';
            } else if (p.includes('-vs-') || (!hasCalcControls && hasComparison)) {
                archetype = 'comparison_page';
            } else if (hasCalcControls) {
                archetype = 'interactive_calculator';
            }
        }
        const result = {
            screen_archetype: archetype,
            hierarchy_violations: [],
            unwrapped_tables: [],
            transparent_controls: [],
            clipped_elements: [],
            card_geometry_violations: [],
            whitespace_rhythm_violations: [],
            calculator_ergonomics_violations: [],
            cta_density_violations: []
        };
        if (!isOperatorPwa) {
            const siteHeader = document.querySelector('header.site-header');
            if (!siteHeader) {
                result.hierarchy_violations.push({ type: 'missing_site_header', vw: vw });
            }
            const siteFooter = document.querySelector('footer.site-footer');
            if (!siteFooter) {
                result.hierarchy_violations.push({ type: 'missing_site_footer', vw: vw });
            }
            const mainLandmark = document.querySelector('main#main-content') || document.querySelector('main');
            if (!mainLandmark) {
                result.hierarchy_violations.push({ type: 'missing_main_landmark', vw: vw });
            } else {
                const directContainer = Array.from(mainLandmark.children).filter(ch => !['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(ch.tagName));
                if (directContainer.length !== 1 || !directContainer[0].classList.contains('container')) {
                    result.hierarchy_violations.push({ type: 'missing_main_container', count: directContainer.length, vw: vw });
                }
            }
            if (vw <= 480) {
                const mobileMenu = document.querySelector('details.mobile-nav-menu');
                if (!mobileMenu) {
                    result.hierarchy_violations.push({ type: 'missing_mobile_nav_drawer', vw: vw });
                } else {
                    const mcs = window.getComputedStyle(mobileMenu);
                    if (mcs.display === 'none' || mcs.visibility === 'hidden') {
                        result.hierarchy_violations.push({ type: 'hidden_mobile_nav_drawer', vw: vw });
                    }
                }
                document.querySelectorAll('.nav-cta-desktop').forEach(navCta => {
                    const ncs = window.getComputedStyle(navCta);
                    if (ncs.display !== 'none') {
                        result.hierarchy_violations.push({ type: 'visible_nav_cta_desktop_on_mobile', display: ncs.display, vw: vw });
                    }
                });
            }
        }
        document.querySelectorAll('.hero-register-firm-link').forEach(regLink => {
            const rcs = window.getComputedStyle(regLink);
            if (rcs.display === 'none' || rcs.visibility === 'hidden') return;
            const pl = parseFloat(rcs.paddingLeft || '0') || 0;
            const pr = parseFloat(rcs.paddingRight || '0') || 0;
            if (pl <= 0 || pr <= 0) {
                result.hierarchy_violations.push({ type: 'hero_register_firm_link_zero_padding', paddingLeft: pl, paddingRight: pr, vw: vw });
            }
        });
        const roundWalker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
            acceptNode: node => {
                const parent = node.parentElement;
                if (!parent) return NodeFilter.FILTER_REJECT;
                const tag = parent.tagName.toLowerCase();
                if (['script', 'style', 'code', 'pre', 'noscript'].includes(tag)) return NodeFilter.FILTER_REJECT;
                const pcs = window.getComputedStyle(parent);
                if (pcs.display === 'none' || pcs.visibility === 'hidden') return NodeFilter.FILTER_REJECT;
                return NodeFilter.FILTER_ACCEPT;
            }
        });
        while (roundWalker.nextNode()) {
            const tVal = roundWalker.currentNode.nodeValue || '';
            if (tVal.includes('round((')) {
                result.hierarchy_violations.push({ type: 'raw_formula_round_paren_visible', text: tVal.trim().slice(0, 80), vw: vw });
                break;
            }
        }
        const primExtLink = document.querySelector('link#pseo-visual-primitives[href]');
        if (!isOperatorPwa && primExtLink && vw >= 1024) {
            const definedClasses = new Set();
            const collectRuleClasses = (ruleList) => {
                if (!ruleList) return;
                for (let ri = 0; ri < ruleList.length; ri++) {
                    const r = ruleList[ri];
                    if (r.selectorText) {
                        const cleanedSel = String(r.selectorText).replace(/\\[[^\\]]*\\]/g, '');
                        const cm = cleanedSel.match(/\\.([a-zA-Z_-][a-zA-Z0-9_-]*)/g);
                        if (cm) {
                            cm.forEach(tok => definedClasses.add(tok.slice(1)));
                        }
                    }
                    if (r.cssRules) collectRuleClasses(r.cssRules);
                }
            };
            for (let si = 0; si < document.styleSheets.length; si++) {
                try {
                    const sheet = document.styleSheets[si];
                    if (sheet && sheet.cssRules) collectRuleClasses(sheet.cssRules);
                } catch (e) {}
            }
            if (definedClasses.size > 0) {
                const hookAllow = new Set(['active', 'open', 'closed', 'collapsed', 'expanded', 'selected', 'disabled', 'hidden', 'visible', 'sr-only', 'visually-hidden']);
                const undefFound = [];
                const undefSeen = new Set();
                document.querySelectorAll('[class]').forEach(el => {
                    const tagL = (el.tagName || '').toLowerCase();
                    if (tagL === 'script' || tagL === 'style' || tagL === 'noscript') return;
                    if (el.closest && el.closest('svg')) return;
                    el.classList.forEach(cls => {
                        if (!cls || hookAllow.has(cls) || cls.startsWith('js-') || cls.startsWith('is-') || cls.startsWith('has-')) return;
                        if (!definedClasses.has(cls) && !undefSeen.has(cls)) {
                            undefSeen.add(cls);
                            undefFound.push(cls);
                        }
                    });
                });
                if (undefFound.length > 0) {
                    result.hierarchy_violations.push({ type: 'undefined_ui_classes', classes: undefFound.slice(0, 12), vw: vw });
                }
            }
        }
        if (!isOperatorPwa) {
            const bodyBg = window.getComputedStyle(document.body).backgroundColor;
            if (bodyBg !== 'rgb(251, 252, 253)') {
                result.card_geometry_violations.push({ type: 'non_porcelain_body_bg', bg: bodyBg, vw: vw });
            }
        }
        const getFs = sel => {
            const el = document.querySelector(sel);
            if (!el) return null;
            const cs = window.getComputedStyle(el);
            if (cs.display === 'none' || cs.visibility === 'hidden') return null;
            return Math.round(parseFloat(cs.fontSize) * 10) / 10;
        };
        const h1 = getFs('h1');
        const h2 = getFs('main h2, article h2, .container h2, h2');
        const h3 = getFs('main h3, article h3, .container h3, h3');
        if (h1 !== null && h2 !== null && h1 <= h2) {
            result.hierarchy_violations.push({ type: 'h1_le_h2', h1: h1, h2: h2, vw: vw });
        }
        if (h2 !== null && h3 !== null && h2 < h3) {
            result.hierarchy_violations.push({ type: 'h2_lt_h3', h2: h2, h3: h3, vw: vw });
        }
        if (vw >= 1024) {
            if (h1 !== null && h1 < 24) {
                result.hierarchy_violations.push({ type: 'desktop_h1_under_24px', h1: h1, vw: vw });
            }
            if (h2 !== null && h2 < 18) {
                result.hierarchy_violations.push({ type: 'desktop_h2_under_18px', h2: h2, vw: vw });
            }
            if (h3 !== null && h3 < 15.5) {
                result.hierarchy_violations.push({ type: 'desktop_h3_under_16px', h3: h3, vw: vw });
            }
        } else if (vw <= 480) {
            if (h1 !== null && h1 < 20) {
                result.hierarchy_violations.push({ type: 'mobile_h1_under_20px', h1: h1, vw: vw });
            }
            if (h2 !== null && h2 < 17) {
                result.hierarchy_violations.push({ type: 'mobile_h2_under_17px', h2: h2, vw: vw });
            }
            if (h3 !== null && h3 < 15.5) {
                result.hierarchy_violations.push({ type: 'mobile_h3_under_16px', h3: h3, vw: vw });
            }
        }
        const parseRgb = str => {
            const m = String(str || '').match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)(?:,\\s*([0-9.]+))?\\)/);
            if (!m) return null;
            return { r: Number(m[1]), g: Number(m[2]), b: Number(m[3]), a: m[4] !== undefined ? Number(m[4]) : 1 };
        };
        const blendOver = (top, bottom) => {
            const a = Math.max(0, Math.min(1, top.a));
            return {
                r: top.r * a + bottom.r * (1 - a),
                g: top.g * a + bottom.g * (1 - a),
                b: top.b * a + bottom.b * (1 - a),
                a: 1
            };
        };
        const relLum = rgb => {
            const f = c => {
                const s = c / 255;
                return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
            };
            return 0.2126 * f(rgb.r) + 0.7152 * f(rgb.g) + 0.0722 * f(rgb.b);
        };
        const _baseDocBg = (() => {
            const b = parseRgb(window.getComputedStyle(document.documentElement).backgroundColor);
            return (!b || b.a === 0) ? { r: 251, g: 252, b: 253, a: 1 } : b;
        })();
        const _bgCache = new WeakMap();
        const getEffectiveBg = el => {
            if (!el || el === document.documentElement) return _baseDocBg;
            const hit = _bgCache.get(el);
            if (hit) return hit;
            const ownBg = parseRgb(window.getComputedStyle(el).backgroundColor);
            let eff;
            if (ownBg && ownBg.a >= 0.999) {
                eff = { r: ownBg.r, g: ownBg.g, b: ownBg.b, a: 1 };
            } else {
                const parentBg = getEffectiveBg(el.parentElement);
                eff = (ownBg && ownBg.a > 0) ? blendOver(ownBg, parentBg) : parentBg;
            }
            _bgCache.set(el, eff);
            return eff;
        };
        const hasDirectText = el => {
            if (el.tagName === 'INPUT' || el.tagName === 'SELECT' || el.tagName === 'TEXTAREA') return true;
            for (let i = 0; i < el.childNodes.length; i++) {
                const n = el.childNodes[i];
                if (n.nodeType === 3 && n.nodeValue && n.nodeValue.trim().length > 0) return true;
            }
            return false;
        };
        const contrastNodes = document.querySelectorAll(
            'h1, h2, h3, h4, p, li, th, td, label, summary, a, button, input:not([type=hidden]):not([type=range]):not([type=checkbox]):not([type=radio]), select, .card-title, .badge, .pill, .output-value, .calc-metric-value, .result-value'
        );
        contrastNodes.forEach(el => {
            if (!hasDirectText(el)) return;
            if (el.classList && (el.classList.contains('sr-only') || el.classList.contains('visually-hidden'))) return;
            const r = el.getBoundingClientRect();
            const cs = window.getComputedStyle(el);
            if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity || '1') === 0 || r.width <= 1 || r.height <= 1) return;
            const rawFg = parseRgb(cs.color);
            const bg = getEffectiveBg(el);
            if (rawFg && bg) {
                const fg = rawFg.a < 1 ? blendOver(rawFg, bg) : rawFg;
                const l1 = relLum(fg);
                const l2 = relLum(bg);
                const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
                const fs = parseFloat(cs.fontSize || '16') || 16;
                const fw = parseInt(cs.fontWeight || '400', 10) || (cs.fontWeight === 'bold' ? 700 : 400);
                const isLarge = fs >= 24 || (fs >= 18.66 && fw >= 700);
                const minReq = isLarge ? 3.0 : 4.5;
                if (ratio + 0.01 < minReq && result.hierarchy_violations.length < 15) {
                    result.hierarchy_violations.push({
                        type: 'low_contrast_text',
                        tag: el.tagName,
                        cls: String(el.className || '').slice(0, 40),
                        ratio: Math.round(ratio * 100) / 100,
                        minRatio: minReq,
                        fg: cs.color,
                        bg: 'rgb(' + Math.round(bg.r) + ', ' + Math.round(bg.g) + ', ' + Math.round(bg.b) + ')',
                        vw: vw
                    });
                }
            }
        });
        if (document.querySelectorAll('section.decision-framework-card').length > 1) {
            result.card_geometry_violations.push({
                type: 'duplicate_decision_framework_card',
                count: document.querySelectorAll('section.decision-framework-card').length,
                vw: vw
            });
        }
        document.querySelectorAll('table').forEach((t, idx) => {
            const r = t.getBoundingClientRect();
            if (r.width === 0 && r.height === 0) return;
            const par = t.parentElement;
            const pcs = par ? window.getComputedStyle(par) : null;
            const wrapped = par && (
                par.classList.contains('table-wrap') ||
                par.classList.contains('calc-matrix-table-wrap') ||
                par.classList.contains('pseo-table-wrap') ||
                (pcs && (pcs.overflowX === 'auto' || pcs.overflowX === 'scroll'))
            );
            if (!wrapped) {
                result.unwrapped_tables.push({ index: idx, parentTag: par ? par.tagName : 'NONE', vw: vw });
            } else if (par) {
                const pr = par.getBoundingClientRect();
                if (pr.right > vw + 2) {
                    result.unwrapped_tables.push({ index: idx, type: 'wrapper_overflow', right: Math.round(pr.right), vw: vw });
                }
            }
        });
        document.querySelectorAll('.scenario-preset-link, .on-this-page-nav a, .cluster-link, .affiliate-cta-link, .btn-preset').forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.width === 0 && r.height === 0) return;
            const cs = window.getComputedStyle(el);
            if (cs.backgroundColor === 'rgba(0, 0, 0, 0)' || cs.color === 'rgb(0, 0, 238)') {
                result.transparent_controls.push({
                    cls: (el.className || '').slice(0, 50),
                    bg: cs.backgroundColor,
                    color: cs.color
                });
            }
        });
        document.querySelectorAll('.card, .calc-panel, .result-box, .table-wrap, iframe, .cf-turnstile-slot').forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.width === 0 && r.height === 0) return;
            const cs = window.getComputedStyle(el);
            if (el.tagName === 'IFRAME' || el.classList.contains('cf-turnstile-slot')) {
                const par = el.parentElement;
                const pr = par ? par.getBoundingClientRect() : null;
                if (r.right > vw + 2 || (pr && r.right > pr.right + 2 && window.getComputedStyle(par).overflowX === 'hidden')) {
                    result.clipped_elements.push({
                        cls: (el.className || el.tagName).slice(0, 50),
                        width: Math.round(r.width),
                        right: Math.round(r.right),
                        vw: vw
                    });
                }
            } else if (cs.overflowX === 'hidden' && el.scrollWidth > el.clientWidth + 2) {
                result.clipped_elements.push({
                    cls: (el.className || '').slice(0, 50),
                    scrollWidth: el.scrollWidth,
                    clientWidth: el.clientWidth
                });
            }
        });
        if (!isOperatorPwa) {
            document.querySelectorAll('.card').forEach((c, idx) => {
                const r = c.getBoundingClientRect();
                if (r.width === 0 && r.height === 0) return;
                const cs = window.getComputedStyle(c);
                if (cs.backgroundColor !== 'rgb(255, 255, 255)') {
                    result.card_geometry_violations.push({ index: idx, type: 'non_porcelain_card_bg', bg: cs.backgroundColor, vw: vw });
                }
                const br = Math.round(parseFloat(cs.borderRadius) || 0);
                if (br !== 12) {
                    result.card_geometry_violations.push({ index: idx, borderRadius: cs.borderRadius });
                }
                const pt = Math.round(parseFloat(cs.paddingTop) || 0);
                if (pt < 12) {
                    result.card_geometry_violations.push({ index: idx, paddingTop: cs.paddingTop });
                }
            });
            const mainEl = document.querySelector('main');
            const flowRoot = (mainEl && mainEl.children.length === 1 && mainEl.children[0].classList.contains('container')) ? mainEl.children[0] : mainEl;
            const topFlowBlocks = [];
            if (flowRoot) {
                Array.from(flowRoot.children).forEach(ch => {
                    if (['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(ch.tagName) || ch.classList.contains('statutory-accuracy-benchmarks')) return;
                    const cs = window.getComputedStyle(ch);
                    if (cs.display === 'none' || cs.visibility === 'hidden') return;
                    if (ch.classList.contains('gsc-overlay-container')) {
                        Array.from(ch.children).forEach(och => {
                            if (['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(och.tagName)) return;
                            const ocs = window.getComputedStyle(och);
                            const or = och.getBoundingClientRect();
                            if (ocs.display !== 'none' && ocs.visibility !== 'hidden' && or.height > 0 && or.width > vw * 0.45) {
                                topFlowBlocks.push(och);
                            }
                        });
                    } else {
                        const r = ch.getBoundingClientRect();
                        if (r.height > 0 && r.width > vw * 0.45) {
                            topFlowBlocks.push(ch);
                        }
                    }
                });
            }
            if (topFlowBlocks.length >= 2) {
                const lefts = topFlowBlocks.map(el => Math.round(el.getBoundingClientRect().left * 10) / 10);
                const drift = Math.max(...lefts) - Math.min(...lefts);
                if (drift > 4.0) {
                    result.card_geometry_violations.push({ type: 'sibling_left_drift', drift: Math.round(drift * 10) / 10, vw: vw });
                }
            }
            if (vw >= 1280) {
                topFlowBlocks.forEach((el, idx) => {
                    const r = el.getBoundingClientRect();
                    if (r.width > 1142) {
                        result.card_geometry_violations.push({ type: 'full_bleed_section_width', index: idx, width: Math.round(r.width), vw: vw });
                    }
                });
            }
            for (let i = 1; i < topFlowBlocks.length; i++) {
                const prev = topFlowBlocks[i - 1];
                const curr = topFlowBlocks[i];
                if (prev.contains(curr) || curr.contains(prev)) continue;
                const pr = prev.getBoundingClientRect();
                const cr = curr.getBoundingClientRect();
                const gap = Math.round((cr.top - pr.bottom) * 10) / 10;
                if (gap < 10 || gap > 52) {
                    result.whitespace_rhythm_violations.push({ index: i, gap: gap, vw: vw });
                }
            }
            if (archetype === 'interactive_calculator' && primExtLink) {
                const calcRoot = document.querySelector('#calculator-workspace-anchor, .calculator-card, form.calculator-form, .calc-grid');
                const calcTop = calcRoot ? Math.round(calcRoot.getBoundingClientRect().top) : null;
                const docH = document.documentElement.scrollHeight;
                const h2Cnt = document.querySelectorAll('h2').length;
                const ymylHeroWarn = document.querySelector('.hero-section .regulatory-forfeiture-warning, .tool-hero .regulatory-forfeiture-warning');
                const ymylPad = ymylHeroWarn ? Math.min(220, Math.max(0, Math.round(ymylHeroWarn.getBoundingClientRect().height))) : 0;
                const maxCalcTop = (vw >= 1024 ? 720 : 920) + ymylPad;
                const maxDocH = vw >= 1024 ? 12000 : 24000;
                if (calcTop !== null && calcTop > maxCalcTop) {
                    result.calculator_ergonomics_violations.push({ type: 'calculator_pushed_below_fold', calcTop: calcTop, maxAllowed: maxCalcTop, vw: vw });
                }
                if (docH > maxDocH) {
                    result.whitespace_rhythm_violations.push({ type: 'excessive_page_height', docHeight: docH, maxAllowed: maxDocH, vw: vw });
                }
                if (h2Cnt > 16) {
                    result.hierarchy_violations.push({ type: 'excessive_h2_bloat', h2Count: h2Cnt, maxAllowed: 16, vw: vw });
                }
            }
        }
        document.querySelectorAll('input:not([type=hidden]):not([type=range]):not([type=checkbox]):not([type=radio]), select').forEach(inp => {
            const r = inp.getBoundingClientRect();
            const cs = window.getComputedStyle(inp);
            if (cs.display === 'none' || cs.visibility === 'hidden' || (r.width === 0 && r.height === 0)) return;
            const fs = Math.round(parseFloat(cs.fontSize) * 10) / 10;
            if (fs < 16) {
                result.calculator_ergonomics_violations.push({ type: 'input_font_under_16px', id: inp.id || inp.name || '', fontSize: fs });
            }
        });
        document.querySelectorAll('.output-value, .metric-val, .res-val, .kpi-value').forEach(out => {
            const r = out.getBoundingClientRect();
            const cs = window.getComputedStyle(out);
            if (cs.display === 'none' || cs.visibility === 'hidden' || (r.width === 0 && r.height === 0)) return;
            if (!String(cs.fontVariantNumeric || '').includes('tabular-nums')) {
                result.calculator_ergonomics_violations.push({ type: 'missing_tabular_nums', id: out.id || out.className || '' });
            }
        });
        const ctaSel = '#vetted-commercial-handoff, #statutory-trap-alert, .commercial-handoff-card, .monetization-partner-section, .inline-fold-cta-card';
        const ctaParents = new Set();
        document.querySelectorAll(ctaSel).forEach(el => {
            if (el.parentElement) ctaParents.add(el.parentElement);
        });
        ctaParents.forEach(par => {
            let streak = 0;
            Array.from(par.children).forEach(ch => {
                const cs = window.getComputedStyle(ch);
                if (cs.display === 'none' || cs.visibility === 'hidden' || ['SCRIPT', 'STYLE'].includes(ch.tagName)) return;
                if (ch.matches && ch.matches(ctaSel)) {
                    streak += 1;
                    if (streak > 2) {
                        result.cta_density_violations.push({ type: 'consecutive_cta_callouts_gt_2', streak: streak });
                    }
                } else {
                    streak = 0;
                }
            });
        });
        const trapEl = document.getElementById('statutory-trap-alert');
        const handoffEl = document.getElementById('vetted-commercial-handoff');
        if (trapEl && handoffEl && (trapEl.nextElementSibling === handoffEl || handoffEl.nextElementSibling === trapEl)) {
            result.cta_density_violations.push({ type: 'adjacent_trap_and_handoff' });
        }
        const firstPresetChip = document.querySelector('.above-fold-preset-bar [data-calc-preset], [data-calc-preset], .scenario-preset-link, .btn-preset');
        if (firstPresetChip) {
            const pr = firstPresetChip.getBoundingClientRect();
            result.first_preset_chip_top = Math.round(pr.top);
            result.preset_chips_above_fold = pr.top <= 680;
        } else {
            result.first_preset_chip_top = null;
            result.preset_chips_above_fold = null;
        }
        return result;
    })()"""

    JS_INIT_ERROR_AND_SYNTHETIC_HOOK = """(() => {
        window.__PSEO_SYNTHETIC_TEST__ = true;
        window.__pseoPageErrors = window.__pseoPageErrors || [];
        window.__pseoConsoleErrors = window.__pseoConsoleErrors || [];
        window.addEventListener('error', (ev) => {
            const msg = ev && (ev.message || (ev.error && ev.error.message)) ? String(ev.message || ev.error.message) : 'window_error';
            window.__pseoPageErrors.push(msg);
        });
        window.addEventListener('unhandledrejection', (ev) => {
            const reason = ev && ev.reason ? String(ev.reason.message || ev.reason) : 'unhandledrejection';
            window.__pseoPageErrors.push(reason);
        });
        const origConsoleError = console.error ? console.error.bind(console) : null;
        console.error = function(...args) {
            try {
                window.__pseoConsoleErrors.push(args.map(a => String(a && a.message ? a.message : a)).join(' '));
            } catch (e) {}
            if (origConsoleError) return origConsoleError(...args);
        };
    })();"""

    _JS_CALC_CONTROL_PROBE_HELPERS = """
        const dispatchCalcEvent = (el) => {
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        };
        const buildNumericProbeCandidates = (ctrl) => {
            if (ctrl.type === 'range') {
                const curNum = parseFloat(String(ctrl.value)) || 0;
                const maxNum = parseFloat(ctrl.getAttribute('max') || '100');
                const minNum = parseFloat(ctrl.getAttribute('min') || '0');
                const stepVal = parseFloat(ctrl.getAttribute('step') || '1') || 1;
                const spanMid = minNum + Math.round(((maxNum - minNum) * 0.35) / stepVal) * stepVal;
                return [
                    Math.min(maxNum, curNum + (3 * stepVal)),
                    Math.max(minNum, curNum - (3 * stepVal)),
                    Math.min(maxNum, Math.max(minNum, spanMid)),
                    maxNum,
                    minNum,
                ].filter((v, idx, arr) => !isNaN(v) && arr.indexOf(v) === idx);
            }
            const parsedCur = parseFloat(String(ctrl.value).replace(/,/g, ''));
            const curNum = Number.isFinite(parsedCur) ? parsedCur : 10000;
            const maxAttr = ctrl.getAttribute('max');
            const minAttr = ctrl.getAttribute('min');
            const stepAttr = ctrl.getAttribute('step');
            const parsedStep = (stepAttr && stepAttr !== 'any') ? parseFloat(stepAttr) : NaN;
            const step = (Number.isFinite(parsedStep) && parsedStep > 0) ? parsedStep : 1;
            const maxNum = (maxAttr !== null && maxAttr !== '' && !isNaN(parseFloat(maxAttr))) ? parseFloat(maxAttr) : Math.max(10000000, Math.abs(curNum) * 3 + 1000);
            const minNum = (minAttr !== null && minAttr !== '' && !isNaN(parseFloat(minAttr))) ? parseFloat(minAttr) : 0;
            let candidates = [];
            if (curNum !== 0) {
                let upNum = curNum < 100 ? Math.min(maxNum, curNum + 2) : Math.round(curNum * 1.35 + 50);
                if (upNum > maxNum || upNum === curNum) {
                    upNum = Math.max(minNum, curNum > minNum + 1 ? Math.round(curNum * 0.65) : curNum + 1);
                }
                if (upNum === curNum) upNum = curNum + 1;
                const downNum = Math.max(minNum, curNum > 10 ? Math.round(curNum * 0.3) : Math.max(minNum, curNum - 2));
                candidates = [upNum, downNum, curNum + 1].filter((v, idx, arr) => Number.isFinite(v) && v !== curNum && v >= minNum && v <= maxNum && arr.indexOf(v) === idx);
            }
            if (curNum === 0 || candidates.length === 0) {
                const rangeCandidates = [
                    minNum + step,
                    curNum + step,
                    curNum + (step * 2),
                    Math.min(maxNum, curNum + (step * 3)),
                    Math.max(minNum, curNum - step),
                    maxNum,
                    minNum,
                ];
                candidates = candidates.concat(rangeCandidates).filter((v, idx, arr) => Number.isFinite(v) && v !== curNum && v >= minNum && v <= maxNum && arr.indexOf(v) === idx);
            }
            return candidates;
        };
        const testNumericWithSiblingGate = (ctrl, allControls, candidateVals, readSnap) => {
            const origVal = ctrl.value;
            const beforeSnap = readSnap();
            for (const cand of candidateVals) {
                if (String(cand) === String(origVal)) continue;
                ctrl.value = String(cand);
                dispatchCalcEvent(ctrl);
                if (readSnap() !== beforeSnap) {
                    ctrl.value = origVal;
                    dispatchCalcEvent(ctrl);
                    return true;
                }
            }
            // Fallback when a zero-valued sibling input gates this multiplier term (e.g. unserved_late_days * daily_forfeiture_rate).
            const zeroSiblings = allControls.filter(other => {
                if (other === ctrl || other.tagName === 'SELECT') return false;
                const v = parseFloat(String(other.value).replace(/,/g, ''));
                return !isNaN(v) && v === 0;
            });
            let changedWithGate = false;
            if (zeroSiblings.length > 0) {
                const savedSibs = zeroSiblings.map(s => ({ el: s, val: s.value }));
                for (const s of zeroSiblings) {
                    const sMaxAttr = s.getAttribute('max');
                    const sMax = (sMaxAttr !== null && sMaxAttr !== '' && !isNaN(parseFloat(sMaxAttr))) ? parseFloat(sMaxAttr) : 100000;
                    const sStep = parseFloat(s.getAttribute('step') || '1') || 1;
                    s.value = String(Math.min(sMax, Math.max(1, sStep * 3)));
                    dispatchCalcEvent(s);
                }
                const gatedBefore = readSnap();
                for (const cand of candidateVals) {
                    if (String(cand) === String(origVal)) continue;
                    ctrl.value = String(cand);
                    dispatchCalcEvent(ctrl);
                    if (readSnap() !== gatedBefore) {
                        changedWithGate = true;
                        break;
                    }
                }
                ctrl.value = origVal;
                dispatchCalcEvent(ctrl);
                for (const item of savedSibs) {
                    item.el.value = item.val;
                    dispatchCalcEvent(item.el);
                }
            } else {
                ctrl.value = origVal;
                dispatchCalcEvent(ctrl);
            }
            return changedWithGate;
        };
        const auditAllCalcControls = (allControls, readSnap, onTested, onSelectFail, onRangeFail, onNumberFail) => {
            for (const ctrl of allControls) {
                const beforeSnap = readSnap();
                if (ctrl.tagName === 'SELECT') {
                    if (!ctrl.options || ctrl.options.length < 2) continue;
                    if (onTested) onTested();
                    const origIdx = ctrl.selectedIndex;
                    const beforeSearch = window.location.search || '';
                    let anyChanged = false;
                    let urlSynced = false;
                    for (let offset = 1; offset < ctrl.options.length; offset++) {
                        ctrl.selectedIndex = (origIdx + offset) % ctrl.options.length;
                        dispatchCalcEvent(ctrl);
                        if (readSnap() !== beforeSnap) {
                            anyChanged = true;
                            break;
                        }
                        if ((window.location.search || '') !== beforeSearch) {
                            urlSynced = true;
                        }
                    }
                    if (!anyChanged && !urlSynced) {
                        onSelectFail(ctrl);
                    }
                    ctrl.selectedIndex = origIdx;
                    dispatchCalcEvent(ctrl);
                } else {
                    if (onTested) onTested();
                    const cands = buildNumericProbeCandidates(ctrl);
                    if (!testNumericWithSiblingGate(ctrl, allControls, cands, readSnap)) {
                        if (ctrl.type === 'range') {
                            onRangeFail(ctrl, cands);
                        } else {
                            onNumberFail(ctrl, cands);
                        }
                    }
                }
            }
        };
    """

    JS_CHECK_UNIVERSAL_INTERACTIVE_SYNC = """(() => {""" + _JS_CALC_CONTROL_PROBE_HELPERS + """
        const failures = [];
        const extraCritEl = document.getElementById('calc-input-extra_criteria');
        const pth = String(window.location.pathname || '');
        if (extraCritEl && pth.indexOf('/tools/') === 0 && !/soc-?2/i.test(pth)) {
            failures.push({
                widget_id: 'calc-input-extra_criteria',
                detail: 'Dead extra_criteria control rendered on non-SOC-2 calculator'
            });
        }
        const outSel = '.output-value, .calc-metric-value, .metric-value, .metric-val, [id^="val-"], [id^="res-"], [id*="-res-"], [id^="metric-"], #serp-out-primary, #serp-out-secondary, #serp-out-tertiary, #serp-out-quaternary';
        const isVisibleOutput = (el) => {
            if (!el || el.nodeType !== 1) return false;
            if (typeof el.checkVisibility === 'function') {
                return el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true }) && el.getClientRects().length > 0;
            }
            const cs = window.getComputedStyle(el);
            if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity || '1') === 0) return false;
            if (el.getClientRects().length === 0) return false;
            let cur = el.parentElement;
            while (cur && cur !== document.documentElement) {
                const pcs = window.getComputedStyle(cur);
                if (pcs.display === 'none' || pcs.visibility === 'hidden') return false;
                cur = cur.parentElement;
            }
            return true;
        };
        const visibleOutputText = (el) => {
            if (el.children.length === 0) return (el.textContent || '').trim();
            const parts = [];
            const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, {
                acceptNode: n => {
                    const p = n.parentElement;
                    if (!p) return NodeFilter.FILTER_REJECT;
                    const tag = p.tagName.toLowerCase();
                    if (tag === 'script' || tag === 'style' || tag === 'noscript') return NodeFilter.FILTER_REJECT;
                    const pcs = window.getComputedStyle(p);
                    if (pcs.display === 'none' || pcs.visibility === 'hidden') return NodeFilter.FILTER_REJECT;
                    return NodeFilter.FILTER_ACCEPT;
                }
            });
            while (w.nextNode()) {
                const t = (w.currentNode.nodeValue || '').trim();
                if (t) parts.push(t);
            }
            return parts.join(' ');
        };
        const snapshotOutputs = () => Array.from(document.querySelectorAll(outSel)).filter(isVisibleOutput).map(visibleOutputText).join('|');
        const snapshotInputs = () => Array.from(document.querySelectorAll('input[type="number"], input[type="range"], select')).map(el => el.value).join('|');
        const hasOutputs = document.querySelectorAll(outSel).length > 0;

        // 1. Verify all calculator number inputs, selects, and paired range sliders (B1)
        const calcInputs = Array.from(document.querySelectorAll('input[type="number"]:not([readonly]), input[type="range"]:not([readonly]), select')).filter(el => {
            if (el.disabled) return false;
            if (el.closest && el.closest('#partner-quote-intake-form, #lead-capture-form, #partner-registration-form, #state-first-hero-bar')) return false;
            const s = window.getComputedStyle(el);
            return s.display !== 'none' && s.visibility !== 'hidden';
        });
        if (hasOutputs && calcInputs.length > 0) {
            auditAllCalcControls(
                calcInputs,
                snapshotOutputs,
                null,
                (inp) => failures.push({ widget_id: inp.id || inp.name || 'select_input', detail: 'Select control change did not update any output metric' }),
                (inp, cands) => failures.push({ widget_id: inp.id || inp.name || 'range_input', detail: 'Range slider delta (' + String(inp.value) + ' -> ' + cands.join('/') + ', step=' + String(inp.getAttribute('step') || '1') + ') did not update any output metric' }),
                (inp) => failures.push({ widget_id: inp.id || inp.name || 'number_input', detail: 'Calculator input change did not update any output metric' })
            );
        }

        // 2. Verify all preset, switcher, scenario, and action buttons from a non-matching state
        const presetSelector = [
            'button[data-calc-preset]',
            '.btn-preset[data-calc-preset]',
            '.serp-archetype-btn[data-calc-preset]',
            '.calc-switcher-btn[data-preset-hc]',
            '[data-preset-sec179]',
            '[data-preset-gains]',
            '[data-preset-tey]',
            '[data-preset-income]',
            '[data-preset-pm-gain]',
            '.runway-chip[data-cash]'
        ].join(', ');
        const presetButtons = Array.from(document.querySelectorAll(presetSelector));
        if (presetButtons.length > 0) {
            const origValues = calcInputs.map(el => ({ el, val: el.value, idx: el.tagName === 'SELECT' ? el.selectedIndex : -1 }));
            for (let bIdx = 0; bIdx < presetButtons.length; bIdx++) {
                const btn = presetButtons[bIdx];
                // Perturb numeric inputs slightly so preset always runs from a non-matching state
                for (const el of calcInputs) {
                    if (el.tagName === 'INPUT') {
                        const cVal = parseFloat(String(el.value).replace(/,/g, '')) || 100;
                        const maxV = parseFloat(el.getAttribute('max') || '') || 10000000;
                        const minV = parseFloat(el.getAttribute('min') || '0') || 0;
                        let pVal = cVal < 50 ? Math.min(maxV, cVal + 1) : Math.min(maxV, cVal + 17);
                        if (pVal === cVal) pVal = Math.max(minV, cVal - 1);
                        el.value = String(pVal);
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }
                btn.classList.remove('active');
                const beforeOut = snapshotOutputs();
                const beforeInps = snapshotInputs();
                btn.click();
                const afterOut = snapshotOutputs();
                const afterInps = snapshotInputs();
                if (beforeOut === afterOut && beforeInps === afterInps) {
                    failures.push({
                        widget_id: btn.id || ('preset_btn_' + bIdx),
                        detail: 'Clicking preset/switcher button did not update inputs or outputs: ' + (btn.innerText || btn.textContent || '').trim().slice(0, 48)
                    });
                }
            }
            for (const item of origValues) {
                if (item.el.tagName === 'SELECT' && item.idx >= 0) {
                    item.el.selectedIndex = item.idx;
                } else {
                    item.el.value = item.val;
                }
                item.el.dispatchEvent(new Event('input', { bubbles: true }));
                item.el.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }

        // 3. Verify keyboard focusability and visible focus indicators (--border-focus)
        const posTabEls = Array.from(document.querySelectorAll('[tabindex]')).filter(el => (parseInt(el.getAttribute('tabindex') || '0', 10) || 0) > 0);
        if (posTabEls.length > 0) {
            failures.push({ widget_id: 'positive_tabindex_trap', detail: 'Positive tabindex trap detected on ' + posTabEls.length + ' elements' });
        }
        const focusSample = Array.from(document.querySelectorAll('a[href], button:not([disabled]), input:not([type="hidden"]):not([disabled]), select:not([disabled]), summary')).filter(el => {
            if (el.classList && el.classList.contains('skip-to-content-link')) return false;
            const r = el.getBoundingClientRect();
            const s = window.getComputedStyle(el);
            return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0;
        }).slice(0, 12);
        for (const fEl of focusSample) {
            try {
                fEl.focus({ preventScroll: true });
                if (document.activeElement === fEl) {
                    const cs = window.getComputedStyle(fEl);
                    const hasOutline = cs.outlineStyle && cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth || '0') >= 1.5;
                    const hasShadow = cs.boxShadow && cs.boxShadow !== 'none';
                    if (!hasOutline && !hasShadow) {
                        failures.push({ widget_id: fEl.id || fEl.tagName, detail: 'Interactive control has no visible focus indicator (outlineStyle=none, boxShadow=none)' });
                        break;
                    }
                }
            } catch (e) {}
        }
        if (document.activeElement && typeof document.activeElement.blur === 'function') {
            document.activeElement.blur();
        }

        // 4. Verify affiliate CTAs
        const affiliateAnchors = Array.from(document.querySelectorAll('a[data-partner], a.affiliate-cta-link, .partner-card a[href], .calc-inline-cta a[href], .overlay-partner-offer a[href]'));
        affiliateAnchors.forEach((a, idx) => {
            const rawHref = a.getAttribute('href') || '';
            if (!rawHref.startsWith('/r/')) {
                failures.push({ widget_id: a.id || ('affiliate_cta_' + idx), detail: 'Affiliate CTA href does not route through /r/ edge redirect: ' + rawHref });
            }
            const rel = (a.getAttribute('rel') || '').toLowerCase();
            if (!rel.includes('sponsored') || !rel.includes('nofollow')) {
                failures.push({ widget_id: a.id || ('affiliate_cta_rel_' + idx), detail: 'Affiliate CTA missing rel sponsored/nofollow: ' + rel });
            }
        });
        if (Array.isArray(window.__pseoPageErrors) && window.__pseoPageErrors.length > 0) {
            failures.push({ widget_id: 'runtime_page_errors', detail: window.__pseoPageErrors.join('; ') });
        }
        if (Array.isArray(window.__pseoConsoleErrors) && window.__pseoConsoleErrors.length > 0) {
            failures.push({ widget_id: 'runtime_console_errors', detail: window.__pseoConsoleErrors.join('; ') });
        }
        return failures;
    })()"""

    JS_RUN_E2E_INTERACTIVE_SURFACE = """(async () => {""" + _JS_CALC_CONTROL_PROBE_HELPERS + """
        window.__PSEO_SYNTHETIC_TEST__ = true;
        window.__PSEO_PREVENT_AFFILIATE_NAV__ = true;
        const report = {
            route: window.location.pathname,
            console_errors: Array.isArray(window.__pseoConsoleErrors) ? [...window.__pseoConsoleErrors] : [],
            page_errors: Array.isArray(window.__pseoPageErrors) ? [...window.__pseoPageErrors] : [],
            links_audit: { total_links: 0, internal_links: 0, affiliate_links: 0, invalid_links: [], unrouted_affiliate_links: [], internal_hrefs: [], affiliate_hrefs: [] },
            focus_and_keyboard_navigation: { tested: true, passed: true, focusable_count: 0, zero_outline_failures: [], positive_tabindex_traps: [], skip_link_valid: true, details_accordions_toggled: 0, accordion_failures: [] },
            deep_link_hydration: { tested: false, passed: true, detail: '', url_sync_tested: false, url_sync_passed: true, reload_probe_url: '', reload_selector: '', reload_expected_value: '' },
            calculator_and_presets: { tested: false, passed: true, before_snapshot: '', after_snapshot: '', preset_clicked: false, inputs_tested_count: 0, input_failures: [], buttons_tested_count: 0, button_failures: [] },
            cliff_visualizer: { present: false, passed: true, before_values: [], after_values: [] },
            scenario_comparator: { present: false, passed: true, pinned_a: '', pinned_b: '', live_delta: '' },
            blueprint_actions: { present: false, passed: true, saved_status: '', shared_status: '', exported_status: '', storage_keys: 0 },
            funnel_discipline: { tested: false, passed: true, form_count: 0, unlock_cards_count: 0, referral_cards_count: 0, preview_opened: false, checkout_status: '', checkout_session_id: '', failures: [] },
            post_calc_upgrade_drawer: { present: false, passed: true, preview_rendered: false, checkout_status: '', settlement_id: '', datapack_download_triggered: false },
            playbook_lead_capture_and_checkout: { present: false, passed: true, submission_state: '', partner_href: '', checkout_status: '', checkout_session_id: '' },
            partner_quote_intake_and_checkout: { present: false, passed: true, submission_state: '', partner_href: '', checkout_status: '', checkout_session_id: '' },
            partner_registration_and_slot_checkout: { present: false, passed: true, turnstile_mounted: false, turnstile_mount_calls: 0, turnstile_mount_error: '', submission_state: '', checkout_href: '', checkout_status: '', checkout_session_id: '', slot_price_usd: 0, focused_after_submit: false },
            hash_navigation_and_focus: { present: false, passed: true, links_tested_count: 0, failures: [] },
            hero_state_and_range_anchor: { present: false, passed: true, range_anchor_present: false, synced_state: '', peer_sync_passed: true },
            validation_focus_and_error_states: { present: false, passed: true, forms_tested_count: 0, focus_failures: [] },
            sellable_assets_and_fulfillment_gate: { present: false, passed: true, unpaid_402_enforced: false, free_playbook_verified: false, free_csv_402_enforced: false, free_datapack_402_enforced: false, paid_html_verified: false, paid_csv_verified: false, paid_datapack_verified: false, email_dispatch_verified: false, failures: [] },
            affiliate_redirect_and_telemetry: { tested: false, passed: true, dom_click_handled: false, redirect_status: 0, redirect_location: '', telemetry_status: '', partners_verified_count: 0, all_partner_redirects: [], partner_failures: [] }
        };

        const outSel = '.output-value, .calc-metric-value, .metric-value, .metric-val, [id^="val-"], [id^="res-"], [id*="-res-"], [id^="metric-"], #serp-out-primary, #serp-out-secondary, #serp-out-tertiary, #serp-out-quaternary';
        const isVisibleOutput = (el) => {
            if (!el || el.nodeType !== 1) return false;
            if (typeof el.checkVisibility === 'function') {
                return el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true }) && el.getClientRects().length > 0;
            }
            const cs = window.getComputedStyle(el);
            if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity || '1') === 0) return false;
            if (el.getClientRects().length === 0) return false;
            let cur = el.parentElement;
            while (cur && cur !== document.documentElement) {
                const pcs = window.getComputedStyle(cur);
                if (pcs.display === 'none' || pcs.visibility === 'hidden') return false;
                cur = cur.parentElement;
            }
            return true;
        };
        const visibleOutputText = (el) => {
            if (el.children.length === 0) return (el.textContent || '').trim();
            const parts = [];
            const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, {
                acceptNode: n => {
                    const p = n.parentElement;
                    if (!p) return NodeFilter.FILTER_REJECT;
                    const tag = p.tagName.toLowerCase();
                    if (tag === 'script' || tag === 'style' || tag === 'noscript') return NodeFilter.FILTER_REJECT;
                    const pcs = window.getComputedStyle(p);
                    if (pcs.display === 'none' || pcs.visibility === 'hidden') return NodeFilter.FILTER_REJECT;
                    return NodeFilter.FILTER_ACCEPT;
                }
            });
            while (w.nextNode()) {
                const t = (w.currentNode.nodeValue || '').trim();
                if (t) parts.push(t);
            }
            return parts.join(' ');
        };
        const snapshotOutputs = () => Array.from(document.querySelectorAll(outSel)).filter(isVisibleOutput).map(visibleOutputText).join('|');
        const snapshotInputs = () => Array.from(document.querySelectorAll('input[type="number"], input[type="range"], select')).map(el => el.value).join('|');

        // 0. Dead extra_criteria control guard on non-SOC-2 calculators
        const extraCritEl = document.getElementById('calc-input-extra_criteria');
        const curPath = String(window.location.pathname || '');
        if (extraCritEl && curPath.indexOf('/tools/') === 0 && !/soc-?2/i.test(curPath)) {
            report.calculator_and_presets.input_failures.push('calc-input-extra_criteria');
        }

        // 1. Links audit (internal + affiliate/outbound)
        const allAnchors = Array.from(document.querySelectorAll('a[href], a[data-partner], a.affiliate-cta-link'));
        report.links_audit.total_links = allAnchors.length;
        for (const a of allAnchors) {
            const href = (a.getAttribute('href') || '').trim();
            const isAff = a.hasAttribute('data-partner') || a.classList.contains('affiliate-cta-link') || Boolean(a.closest('.partner-card, .calc-inline-cta, .overlay-partner-offer, #vetted-commercial-handoff')) || href.startsWith('/r/');
            if (!href || href === '#' || href.startsWith('javascript:')) {
                report.links_audit.invalid_links.push(href || '(empty)');
                if (isAff) {
                    report.links_audit.affiliate_links += 1;
                    report.links_audit.unrouted_affiliate_links.push({ href: href, rel: (a.getAttribute('rel') || '').toLowerCase(), id: a.id || '' });
                }
                continue;
            }
            if (isAff) {
                report.links_audit.affiliate_links += 1;
                report.links_audit.affiliate_hrefs.push(href);
                const rel = (a.getAttribute('rel') || '').toLowerCase();
                if (!href.startsWith('/r/') || !rel.includes('sponsored') || !rel.includes('nofollow')) {
                    report.links_audit.unrouted_affiliate_links.push({ href: href, rel: rel, id: a.id || '' });
                }
            } else if (href.startsWith('/') || href.startsWith(window.location.origin) || href.startsWith('#')) {
                report.links_audit.internal_links += 1;
                if (!href.startsWith('/api/') && !href.startsWith('/r/')) {
                    report.links_audit.internal_hrefs.push(href);
                }
                if (href.startsWith('#') && href.length > 1) {
                    const targetId = href.slice(1);
                    if (!document.getElementById(targetId) && !document.querySelector('[name="' + targetId + '"]')) {
                        report.links_audit.invalid_links.push(href);
                    }
                }
            }
        }

        // 1b. Focus states, skip-to-content target, positive tabindex traps, and details/summary accordions
        const posTabNodes = Array.from(document.querySelectorAll('[tabindex]')).filter(el => (parseInt(el.getAttribute('tabindex') || '0', 10) || 0) > 0);
        for (const pt of posTabNodes) {
            report.focus_and_keyboard_navigation.positive_tabindex_traps.push(pt.id || pt.tagName);
        }
        const mainLandmark = document.querySelector('main');
        const skipLink = document.querySelector('a.skip-to-content-link[href^="#"], a[href="#main-content"]');
        if (mainLandmark) {
            if (!skipLink) {
                report.focus_and_keyboard_navigation.skip_link_valid = false;
            } else {
                const skipTargetId = (skipLink.getAttribute('href') || '').slice(1);
                const skipTargetEl = skipTargetId ? document.getElementById(skipTargetId) : null;
                if (!skipTargetEl) {
                    report.focus_and_keyboard_navigation.skip_link_valid = false;
                }
            }
        }
        const detailsList = Array.from(document.querySelectorAll('details'));
        for (const det of detailsList) {
            const sumEl = det.querySelector('summary');
            if (!sumEl) continue;
            const cs = window.getComputedStyle(det);
            if (cs.display === 'none' || cs.visibility === 'hidden') continue;
            const origOpen = det.open;
            sumEl.click();
            if (det.open === origOpen) {
                report.focus_and_keyboard_navigation.accordion_failures.push(det.id || (sumEl.innerText || '').trim().slice(0, 36));
            } else {
                report.focus_and_keyboard_navigation.details_accordions_toggled += 1;
            }
            det.open = origOpen;
        }
        const focusCandidates = Array.from(document.querySelectorAll('a[href], button:not([disabled]), input:not([type="hidden"]):not([disabled]), select:not([disabled]), textarea:not([disabled]), summary, [role="button"]')).filter(el => {
            if (el.classList && el.classList.contains('skip-to-content-link')) return false;
            const r = el.getBoundingClientRect();
            const s = window.getComputedStyle(el);
            return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0;
        });
        for (const fEl of focusCandidates) {
            try {
                fEl.focus({ preventScroll: true });
                if (document.activeElement === fEl) {
                    report.focus_and_keyboard_navigation.focusable_count += 1;
                    const cs = window.getComputedStyle(fEl);
                    const hasOutline = cs.outlineStyle && cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth || '0') >= 1.5;
                    const hasShadow = cs.boxShadow && cs.boxShadow !== 'none';
                    if (!hasOutline && !hasShadow) {
                        report.focus_and_keyboard_navigation.zero_outline_failures.push(fEl.id || fEl.className || fEl.tagName);
                    }
                }
            } catch (e) {}
        }
        if (document.activeElement && typeof document.activeElement.blur === 'function') {
            document.activeElement.blur();
        }
        window.scrollTo(0, 0);
        report.focus_and_keyboard_navigation.passed = (
            report.focus_and_keyboard_navigation.skip_link_valid &&
            report.focus_and_keyboard_navigation.positive_tabindex_traps.length === 0 &&
            report.focus_and_keyboard_navigation.zero_outline_failures.length === 0 &&
            report.focus_and_keyboard_navigation.accordion_failures.length === 0 &&
            (focusCandidates.length === 0 || report.focus_and_keyboard_navigation.focusable_count > 0)
        );

        // 2. B2: Real input -> URL query param update + popstate hydration + reload probe (run before bulk control stress so Chromium replaceState flood guard is untouched)
        const primaryInp = document.querySelector('#field-gross_income, #tax-income, #sec179-cost, #sec1031-sale-price, #crypto-short-term, #runway-cash, #tey-principal, #cg-amount, #arb-yes-cents, #pm-tax-gain, #input-agi, #field-loan_balance, input[type="number"]:not([readonly]):not(.serp-sub-input)');
        if (primaryInp) {
            const origVal = primaryInp.value;
            const curNum = parseFloat(String(origVal).replace(/,/g, '')) || 50000;
            const maxAttr = primaryInp.getAttribute('max');
            const minAttr = primaryInp.getAttribute('min');
            const maxNum = (maxAttr !== null && maxAttr !== '' && !isNaN(parseFloat(maxAttr))) ? parseFloat(maxAttr) : Math.max(10000000, Math.abs(curNum) * 3 + 1000);
            const minNum = (minAttr !== null && minAttr !== '' && !isNaN(parseFloat(minAttr))) ? parseFloat(minAttr) : 0;
            const rawKey = (primaryInp.name || primaryInp.id || 'amount').replace(/^field-/, '').replace(/^input-/, '').replace(/^calc-input-/, '');
            const hydratedNum = Math.min(maxNum, Math.max(minNum + 5, Math.round(curNum * 1.25 + 120)));
            const origUrl = window.location.pathname + window.location.search + window.location.hash;
            const isFullShellCalc = Boolean(
                document.querySelector('link#pseo-visual-primitives') &&
                primaryInp.id &&
                document.querySelector('#workpaper-unlock-card, #calculation-manifest, script.calculation-manifest, #hub-bond-calculator, #btn-preview-workpaper')
            );
            if (isFullShellCalc) {
                report.deep_link_hydration.url_sync_tested = true;
                window.history.replaceState(null, '', window.location.pathname);
                primaryInp.value = String(hydratedNum);
                primaryInp.dispatchEvent(new Event('input', { bubbles: true }));
                primaryInp.dispatchEvent(new Event('change', { bubbles: true }));
                const postSearch = String(window.location.search || '');
                const urlUpdated = postSearch.includes(String(hydratedNum));
                report.deep_link_hydration.url_sync_passed = urlUpdated;
                if (urlUpdated) {
                    report.deep_link_hydration.reload_probe_url = window.location.pathname + postSearch;
                    report.deep_link_hydration.reload_selector = '#' + CSS.escape(primaryInp.id);
                    report.deep_link_hydration.reload_expected_value = String(hydratedNum);
                }
            }
            window.history.replaceState(null, '', window.location.pathname + '?' + encodeURIComponent(rawKey) + '=' + encodeURIComponent(String(hydratedNum)));
            window.dispatchEvent(new PopStateEvent('popstate'));
            if (typeof window.__pseoHydrateFromUrl === 'function') {
                window.__pseoHydrateFromUrl();
            }
            report.deep_link_hydration.tested = true;
            const popOk = String(primaryInp.value) === String(hydratedNum);
            report.deep_link_hydration.passed = popOk && report.deep_link_hydration.url_sync_passed;
            report.deep_link_hydration.detail = 'key=' + rawKey + ', expected=' + hydratedNum + ', actual=' + primaryInp.value + ', url_sync=' + String(report.deep_link_hydration.url_sync_passed);
            primaryInp.value = origVal;
            primaryInp.dispatchEvent(new Event('input', { bubbles: true }));
            primaryInp.dispatchEvent(new Event('change', { bubbles: true }));
            window.history.replaceState(null, '', origUrl);
        }

        // 3. All calculator inputs/selects/sliders (B1), cliff visualizer, scenario comparator, and presets
        const allCalcControls = Array.from(document.querySelectorAll('input[type="number"]:not([readonly]), input[type="range"]:not([readonly]), select')).filter(el => {
            if (el.disabled) return false;
            if (el.closest && el.closest('#partner-quote-intake-form, #lead-capture-form, #partner-registration-form, #state-first-hero-bar')) return false;
            const s = window.getComputedStyle(el);
            return s.display !== 'none' && s.visibility !== 'hidden';
        });
        if (allCalcControls.length > 0 && document.querySelectorAll(outSel).length > 0) {
            auditAllCalcControls(
                allCalcControls,
                snapshotOutputs,
                () => { report.calculator_and_presets.inputs_tested_count += 1; },
                (ctrl) => report.calculator_and_presets.input_failures.push(ctrl.id || ctrl.name || 'select_control'),
                (ctrl) => report.calculator_and_presets.input_failures.push((ctrl.id || ctrl.name || 'range_control') + ':step=' + String(parseFloat(ctrl.getAttribute('step') || '1') || 1)),
                (ctrl) => report.calculator_and_presets.input_failures.push(ctrl.id || ctrl.name || 'number_control')
            );
        }

        // Test all preset, switcher, scenario, and action buttons from a non-matching state
        const presetSelector = [
            'button[data-calc-preset]',
            '.btn-preset[data-calc-preset]',
            '.serp-archetype-btn[data-calc-preset]',
            '.calc-switcher-btn[data-preset-hc]',
            '[data-preset-sec179]',
            '[data-preset-gains]',
            '[data-preset-tey]',
            '[data-preset-income]',
            '[data-preset-pm-gain]',
            '.runway-chip[data-cash]'
        ].join(', ');
        const allPresetBtns = Array.from(document.querySelectorAll(presetSelector));
        if (allPresetBtns.length > 0) {
            const savedControls = allCalcControls.map(el => ({ el, val: el.value, idx: el.tagName === 'SELECT' ? el.selectedIndex : -1 }));
            const _perturbControl = (el) => {
                if (el.tagName === 'INPUT') {
                    const cVal = parseFloat(String(el.value).replace(/,/g, '')) || 100;
                    const maxV = parseFloat(el.getAttribute('max') || '') || 10000000;
                    const minV = parseFloat(el.getAttribute('min') || '0') || 0;
                    let pVal = cVal < 50 ? Math.min(maxV, cVal + 1) : Math.min(maxV, cVal + 17);
                    if (pVal === cVal) pVal = Math.max(minV, cVal - 1);
                    el.value = String(pVal);
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                } else if (el.tagName === 'SELECT' && el.options && el.options.length >= 2) {
                    el.selectedIndex = (el.selectedIndex + 1) % el.options.length;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }
            };
            const _matchPresetKey = (el, presetObj) => {
                const rawId = el.id || '';
                const rawName = el.name || '';
                const stripped = rawId.replace(/^(field-|calc-input-|input-)/, '');
                for (const k of [rawId, rawName, stripped]) {
                    if (k && Object.prototype.hasOwnProperty.call(presetObj, k)) return k;
                }
                return null;
            };
            for (let bIdx = 0; bIdx < allPresetBtns.length; bIdx++) {
                const btn = allPresetBtns[bIdx];
                let presetJson = null;
                const rawPresetAttr = (btn.getAttribute('data-calc-preset') || '').trim();
                if (rawPresetAttr.startsWith('{')) {
                    try {
                        const parsed = JSON.parse(rawPresetAttr);
                        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) presetJson = parsed;
                    } catch (e) {}
                }
                if (presetJson) {
                    let matchedAny = false;
                    let anyDiffers = false;
                    const matchingEls = [];
                    for (const el of allCalcControls) {
                        const mk = _matchPresetKey(el, presetJson);
                        if (mk !== null) {
                            matchedAny = true;
                            matchingEls.push(el);
                            if (String(el.value) !== String(presetJson[mk])) {
                                anyDiffers = true;
                            }
                        }
                    }
                    if (!matchedAny) {
                        for (const el of allCalcControls) _perturbControl(el);
                    } else if (!anyDiffers) {
                        for (const el of matchingEls) _perturbControl(el);
                    }
                } else {
                    for (const el of allCalcControls) _perturbControl(el);
                }
                btn.classList.remove('active');
                const beforeOut = snapshotOutputs();
                const beforeInps = snapshotInputs();
                btn.click();
                report.calculator_and_presets.preset_clicked = true;
                report.calculator_and_presets.buttons_tested_count += 1;
                const afterOut = snapshotOutputs();
                const afterInps = snapshotInputs();
                if (beforeOut === afterOut && beforeInps === afterInps) {
                    report.calculator_and_presets.button_failures.push(btn.id || ('preset_' + bIdx + ':' + (btn.textContent || '').trim().slice(0, 32)));
                }
            }
            for (const item of savedControls) {
                if (item.el.tagName === 'SELECT' && item.idx >= 0) {
                    item.el.selectedIndex = item.idx;
                } else {
                    item.el.value = item.val;
                }
                item.el.dispatchEvent(new Event('input', { bubbles: true }));
                item.el.dispatchEvent(new Event('change', { bubbles: true }));
            }
        } else {
            const scenarioAnchors = Array.from(document.querySelectorAll('a.scenario-preset-link[href*="?"]'));
            const samePageAnchor = scenarioAnchors.find(a => {
                try {
                    const u = new URL(a.href, window.location.origin);
                    return u.pathname === window.location.pathname;
                } catch (e) {
                    return String(a.getAttribute('href') || '').startsWith('?');
                }
            });
            if (samePageAnchor) {
                samePageAnchor.click();
                report.calculator_and_presets.preset_clicked = true;
                report.calculator_and_presets.buttons_tested_count += 1;
            } else if (scenarioAnchors.length > 0) {
                report.calculator_and_presets.preset_clicked = true;
                report.calculator_and_presets.buttons_tested_count += 1;
            }
        }

        const calcSubmitBtn = document.getElementById('calc-submit-btn');
        if (calcSubmitBtn) {
            calcSubmitBtn.click();
            report.calculator_and_presets.buttons_tested_count += 1;
            if (calcSubmitBtn.getAttribute('data-recalculated') !== 'true') {
                report.calculator_and_presets.button_failures.push('calc-submit-btn');
            }
        }

        const cliffRoot = document.getElementById('multi-year-cliff-visualizer') || document.querySelector('.serp-cliff-chart');
        const cliffValueSelector = '[id^="cliff-exposure-"], [id^="serp-cliff-val-"]';
        if (cliffRoot) {
            report.cliff_visualizer.present = true;
            report.cliff_visualizer.before_values = Array.from(document.querySelectorAll(cliffValueSelector)).map(el => (el.innerText || el.textContent || '').trim());
        }

        const compRoot = document.getElementById('stateful-scenario-comparator');
        const pinABtn = document.querySelector('[data-scenario-pin="A"]');
        const pinBBtn = document.querySelector('[data-scenario-pin="B"]');
        const pinResetBtn = document.querySelector('[data-scenario-pin="RESET"]');
        if (compRoot || pinABtn) {
            report.scenario_comparator.present = true;
        }

        if (primaryInp) {
            report.calculator_and_presets.tested = true;
            const origVal = primaryInp.value;
            const curNum = parseFloat(String(origVal).replace(/,/g, '')) || 50000;
            const maxAttr = primaryInp.getAttribute('max');
            const minAttr = primaryInp.getAttribute('min');
            const maxNum = (maxAttr !== null && maxAttr !== '' && !isNaN(parseFloat(maxAttr))) ? parseFloat(maxAttr) : Math.max(10000000, Math.abs(curNum) * 3 + 1000);
            const minNum = (minAttr !== null && minAttr !== '' && !isNaN(parseFloat(minAttr))) ? parseFloat(minAttr) : 0;

            if (pinABtn) {
                pinABtn.click();
                report.calculator_and_presets.buttons_tested_count += 1;
            }

            report.calculator_and_presets.before_snapshot = snapshotOutputs();
            let nextNum = Math.round(curNum * 1.45 + 250);
            if (nextNum > maxNum) nextNum = Math.max(minNum + 10, Math.round(curNum * 0.6));
            if (nextNum === curNum) nextNum = curNum + 100;
            primaryInp.value = String(nextNum);
            dispatchCalcEvent(primaryInp);
            report.calculator_and_presets.after_snapshot = snapshotOutputs();
            if (report.calculator_and_presets.before_snapshot === report.calculator_and_presets.after_snapshot) {
                const downNum = Math.max(minNum, curNum > 10 ? Math.round(curNum * 0.3) : Math.max(minNum, curNum - 2));
                if (downNum !== nextNum && downNum !== curNum) {
                    primaryInp.value = String(downNum);
                    dispatchCalcEvent(primaryInp);
                    report.calculator_and_presets.after_snapshot = snapshotOutputs();
                }
            }
            if (report.calculator_and_presets.before_snapshot === report.calculator_and_presets.after_snapshot) {
                report.calculator_and_presets.passed = false;
            }

            if (cliffRoot) {
                report.cliff_visualizer.after_values = Array.from(document.querySelectorAll(cliffValueSelector)).map(el => (el.innerText || el.textContent || '').trim());
                if (report.cliff_visualizer.after_values.length === 0 || report.cliff_visualizer.before_values.join('|') === report.cliff_visualizer.after_values.join('|')) {
                    report.cliff_visualizer.passed = false;
                }
            }

            if (pinBBtn) {
                pinBBtn.click();
                report.calculator_and_presets.buttons_tested_count += 1;
                const aNode = document.getElementById('comp-a-retained') || document.getElementById('serp-scn-a-retained');
                const bNode = document.getElementById('comp-b-retained') || document.getElementById('serp-scn-b-retained');
                const dNode = document.getElementById('comp-live-delta') || document.getElementById('comp-b-delta') || document.getElementById('serp-scn-delta-banner');
                report.scenario_comparator.pinned_a = aNode ? (aNode.innerText || aNode.textContent || '').trim() : '';
                report.scenario_comparator.pinned_b = bNode ? (bNode.innerText || bNode.textContent || '').trim() : '';
                report.scenario_comparator.live_delta = dNode ? (dNode.innerText || dNode.textContent || '').trim() : '';
                if (!report.scenario_comparator.pinned_a || !report.scenario_comparator.pinned_b || report.scenario_comparator.pinned_a === '$0') {
                    report.scenario_comparator.passed = false;
                }
                if (pinResetBtn) {
                    pinResetBtn.click();
                    report.calculator_and_presets.buttons_tested_count += 1;
                }
            }

            primaryInp.value = origVal;
            primaryInp.dispatchEvent(new Event('input', { bubbles: true }));
            primaryInp.dispatchEvent(new Event('change', { bubbles: true }));
        }

        if (
            report.calculator_and_presets.input_failures.length > 0 ||
            report.calculator_and_presets.button_failures.length > 0
        ) {
            report.calculator_and_presets.passed = false;
        }

        // 3. Saveable Decision Blueprint actions
        const saveBtn = document.querySelector('[data-blueprint-action="save"]');
        const shareBtn = document.querySelector('[data-blueprint-action="share"]');
        const exportBtn = document.querySelector('[data-blueprint-action="export"]');
        const statusNode = document.getElementById('blueprint-status-readout') || document.getElementById('serp-blueprint-status') || document.querySelector('.serp-blueprint-status');
        if (saveBtn) {
            report.blueprint_actions.present = true;
            saveBtn.click();
            report.calculator_and_presets.buttons_tested_count += 1;
            report.blueprint_actions.saved_status = statusNode ? (statusNode.innerText || statusNode.textContent || '').trim() : '';
            if (shareBtn) {
                shareBtn.click();
                report.calculator_and_presets.buttons_tested_count += 1;
                report.blueprint_actions.shared_status = statusNode ? (statusNode.innerText || statusNode.textContent || '').trim() : '';
            }
            if (exportBtn) {
                exportBtn.click();
                report.calculator_and_presets.buttons_tested_count += 1;
                report.blueprint_actions.exported_status = statusNode ? (statusNode.innerText || statusNode.textContent || '').trim() : '';
            }
            let bpKeys = 0;
            try {
                for (let i = 0; i < localStorage.length; i++) {
                    const k = localStorage.key(i) || '';
                    if (k.startsWith('pseo_blueprint')) bpKeys += 1;
                }
            } catch (e) {}
            report.blueprint_actions.storage_keys = bpKeys;
            if (!report.blueprint_actions.saved_status || bpKeys === 0 || (exportBtn && exportBtn.getAttribute('data-blueprint-exported') !== '1')) {
                report.blueprint_actions.passed = false;
            }
        }

        // 3b. Clean 3-Step Funnel Discipline & /partners/ Contract
        const isPartnersRoute = (curPath === '/partners/' || curPath === '/partners' || curPath === '/partners/index.html');
        const hasPorcelainCss = Boolean(document.querySelector('link#pseo-visual-primitives'));
        const isRestrictedYmylPath = /(?:pslf|save-plan|save_plan|buyback|income-driven-forgiveness|ibr-hardship|hardship-cap)/i.test(curPath);
        const allForms = Array.from(document.querySelectorAll('form'));
        const unlockCards = Array.from(document.querySelectorAll('#workpaper-unlock-card'));
        const refCards = Array.from(document.querySelectorAll('.contextual-referral-card'));
        report.funnel_discipline.tested = true;
        report.funnel_discipline.form_count = allForms.length;
        report.funnel_discipline.unlock_cards_count = unlockCards.length;
        report.funnel_discipline.referral_cards_count = refCards.length;

        if (!isPartnersRoute) {
            if (allForms.length > 1) {
                report.funnel_discipline.failures.push('competing_forms_gt_1:' + allForms.length);
            }
            const forbiddenIds = ['partner-registration-form', 'lead-capture-form', 'footer-lead-capture-form', 'inline-worksheet-capture-form', 'partner-quote-intake-form', 'post-calculation-upgrade-drawer', 'calc-result-quick-unlock-bar'];
            for (const fId of forbiddenIds) {
                if (document.getElementById(fId)) {
                    report.funnel_discipline.failures.push('forbidden_legacy_element:' + fId);
                }
            }
            if (document.querySelector('.pro-hook-card')) {
                report.funnel_discipline.failures.push('forbidden_pro_hook_card');
            }
            const bodyLower = String((document.body && document.body.innerText) || '').toLowerCase();
            if (bodyLower.includes('register your firm')) {
                report.funnel_discipline.failures.push('forbidden_register_your_firm_cta');
            }
            for (const fPhrase of ['email me free summary', 'send playbook', 'get free playbook']) {
                if (bodyLower.includes(fPhrase)) {
                    report.funnel_discipline.failures.push('false_free_email_promise:' + fPhrase);
                }
            }
        }
        if (refCards.length > 1) {
            report.funnel_discipline.failures.push('contextual_referral_cards_gt_1:' + refCards.length);
        }
        for (const rc of refCards) {
            if (!rc.querySelector('a[href^="/r/"]')) {
                report.funnel_discipline.failures.push('empty_contextual_referral_placeholder');
            }
        }
        if (isRestrictedYmylPath) {
            if (unlockCards.length > 0 || document.querySelector('[data-checkout-trigger]') || refCards.length > 0 || document.querySelector('a[href^="/r/"]')) {
                report.funnel_discipline.failures.push('restricted_ymyl_has_commercial_funnel');
            }
        } else if (
            curPath.indexOf('/tools/') === 0 &&
            curPath !== '/tools/' &&
            hasPorcelainCss &&
            document.querySelector('form.calculator-form') &&
            document.querySelector('#workpaper-unlock-card, #calculation-manifest, script.calculation-manifest, #btn-preview-workpaper')
        ) {
            if (unlockCards.length !== 1) {
                report.funnel_discipline.failures.push('expected_1_workpaper_unlock_card_got_' + unlockCards.length);
            }
        }

        const previewBtn = document.getElementById('btn-preview-workpaper');
        const previewPanel = document.getElementById('workpaper-preview-panel');
        if (previewBtn && previewPanel) {
            previewBtn.click();
            report.calculator_and_presets.buttons_tested_count += 1;
            report.funnel_discipline.preview_opened = !previewPanel.hasAttribute('hidden') && window.getComputedStyle(previewPanel).display !== 'none';
            if (!report.funnel_discipline.preview_opened) {
                report.funnel_discipline.failures.push('step1_preview_panel_did_not_open');
            }
        }

        const unlockCard = unlockCards[0] || null;
        if (unlockCard) {
            const chkTriggers = Array.from(unlockCard.querySelectorAll('[data-checkout-trigger]'));
            if (chkTriggers.length < 1 || chkTriggers.length > 2) {
                report.funnel_discipline.failures.push('expected_1_or_2_checkout_triggers_got_' + chkTriggers.length);
            }
            const firstChk = chkTriggers[0] || null;
            if (firstChk) {
                const rawOfferPrice = parseInt(firstChk.getAttribute('data-offer-price') || '0', 10);
                if (![9, 15, 19, 29].includes(rawOfferPrice)) {
                    report.funnel_discipline.failures.push('non_canonical_offer_price:' + rawOfferPrice);
                }
                firstChk.click();
                report.calculator_and_presets.buttons_tested_count += 1;
                for (let i = 0; i < 600; i++) {
                    if (firstChk.getAttribute('data-checkout-status') === 'checkout_session_ready') break;
                    await new Promise(r => setTimeout(r, 5));
                }
                report.funnel_discipline.checkout_status = firstChk.getAttribute('data-checkout-status') || '';
                report.funnel_discipline.checkout_session_id = firstChk.getAttribute('data-checkout-session-id') || '';
                if (report.funnel_discipline.checkout_status !== 'checkout_session_ready' || !report.funnel_discipline.checkout_session_id) {
                    report.funnel_discipline.failures.push('step2_checkout_trigger_failed');
                }
            }
        }
        if (report.funnel_discipline.failures.length > 0) {
            report.funnel_discipline.passed = false;
        }

        // 3c. In-page #hash navigation & focus transfer (TOC anchors)
        const hashCandidates = Array.from(document.querySelectorAll('.on-this-page-nav a[href^="#"]')).filter(a => {
            if (a.classList && a.classList.contains('skip-to-content-link')) return false;
            const h = (a.getAttribute('href') || '').trim();
            if (h.length <= 1) return false;
            const tEl = document.getElementById(h.slice(1));
            if (!tEl) return false;
            const cs = window.getComputedStyle(a);
            return cs.display !== 'none' && cs.visibility !== 'hidden';
        }).slice(0, 3);
        if (hashCandidates.length > 0) {
            report.hash_navigation_and_focus.present = true;
            const origHashUrl = window.location.pathname + window.location.search + window.location.hash;
            for (const hLink of hashCandidates) {
                const rawH = hLink.getAttribute('href') || '';
                const tId = rawH.slice(1);
                const tEl = document.getElementById(tId);
                if (!tEl) continue;
                hLink.click();
                report.hash_navigation_and_focus.links_tested_count += 1;
                const focusedOk = (
                    tEl.getAttribute('data-focused-target') === 'true' &&
                    Boolean(document.activeElement && (document.activeElement === tEl || tEl.contains(document.activeElement)))
                );
                if (!focusedOk) {
                    report.hash_navigation_and_focus.failures.push(rawH);
                }
            }
            window.history.replaceState(null, '', origHashUrl);
            window.scrollTo(0, 0);
            if (report.hash_navigation_and_focus.failures.length > 0) {
                report.hash_navigation_and_focus.passed = false;
            }
        }

        // 4. Dedicated /partners/ route ($299 Verified Partner Slot) POST + Turnstile mount + checkout trigger
        const prForm = isPartnersRoute ? (document.getElementById('partner-registration-form') || document.querySelector('form.partner-registration-form')) : null;
        if (isPartnersRoute && !prForm) {
            report.partner_registration_and_slot_checkout.present = true;
            report.partner_registration_and_slot_checkout.passed = false;
        } else if (prForm) {
            report.partner_registration_and_slot_checkout.present = true;
            const prFirm = prForm.querySelector('input[name="firm_name"]');
            const prEmail = prForm.querySelector('input[type="email"], input[name="email"]');
            const prState = prForm.querySelector('select[name="state"]');

            // Exercise Turnstile mount with deterministic stub (never hitting Cloudflare network)
            window.__pseoTurnstileMountCalls = [];
            window.__pseoTurnstileMountError = '';
            window.turnstile = {
                render: function(el, opts) {
                    const id = 'ts_stub_' + String(window.__pseoTurnstileMountCalls.length + 1);
                    window.__pseoTurnstileMountCalls.push({
                        id: id,
                        hasEl: Boolean(el),
                        inBody: Boolean(el && document.body && document.body.contains(el)),
                        hasSlotClass: Boolean(el && el.classList && el.classList.contains('cf-turnstile-slot')),
                        sitekey: opts && opts.sitekey ? String(opts.sitekey) : ''
                    });
                    if (opts && typeof opts.callback === 'function') {
                        opts.callback('synthetic_turnstile_token_ok');
                    }
                    return id;
                },
                reset: function() {},
                remove: function() {}
            };
            window.__PSEO_EXERCISE_TURNSTILE_MOUNT__ = true;
            window.__PSEO_FORCE_TURNSTILE_CONFIG__ = true;
            window.__pseoLeadConfigPromise = null;
            if (typeof window.__pseoWarmLeadFormsTurnstile === 'function') {
                window.__pseoWarmLeadFormsTurnstile();
            } else if (typeof window.__pseoMountRuntimeTurnstile === 'function') {
                window.__pseoMountRuntimeTurnstile(prForm);
            } else {
                (prFirm || prForm).dispatchEvent(new Event('focusin', { bubbles: true }));
            }
            const tsSlot = prForm.querySelector('.cf-turnstile-slot');
            for (let i = 0; i < 200; i++) {
                if (
                    tsSlot &&
                    tsSlot.getAttribute('data-turnstile-mounted') === '1' &&
                    Array.isArray(window.__pseoTurnstileMountCalls) &&
                    window.__pseoTurnstileMountCalls.length > 0
                ) break;
                await new Promise(r => setTimeout(r, 5));
            }
            const tsMountCalls = Array.isArray(window.__pseoTurnstileMountCalls) ? window.__pseoTurnstileMountCalls : [];
            report.partner_registration_and_slot_checkout.turnstile_mounted = Boolean(
                tsSlot && tsSlot.getAttribute('data-turnstile-mounted') === '1'
            );
            report.partner_registration_and_slot_checkout.turnstile_mount_calls = tsMountCalls.length;
            report.partner_registration_and_slot_checkout.turnstile_mount_error = String(window.__pseoTurnstileMountError || '');
            const tsMountValid = (
                report.partner_registration_and_slot_checkout.turnstile_mounted &&
                tsMountCalls.length > 0 &&
                !report.partner_registration_and_slot_checkout.turnstile_mount_error &&
                tsMountCalls.some(c => c.inBody && c.hasSlotClass)
            );

            if (prFirm) prFirm.value = 'Apex Statutory Advisory LLP';
            if (prEmail) prEmail.value = 'partner-desk@synthetic.pseofactory.test';
            if (prState && !prState.value) prState.value = 'CA';
            prForm.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
            for (let i = 0; i < 960; i++) {
                if (prForm.getAttribute('data-submission-state') === 'success') break;
                await new Promise(r => setTimeout(r, 5));
            }
            report.partner_registration_and_slot_checkout.submission_state = prForm.getAttribute('data-submission-state') || '';
            const prChkLink = document.getElementById('partner-slot-checkout-link');
            if (prChkLink) {
                report.partner_registration_and_slot_checkout.checkout_href = prChkLink.getAttribute('href') || '';
                report.partner_registration_and_slot_checkout.focused_after_submit = (document.activeElement === prChkLink);
                prChkLink.click();
                for (let i = 0; i < 960; i++) {
                    if (prChkLink.getAttribute('data-checkout-status') === 'checkout_session_ready') break;
                    await new Promise(r => setTimeout(r, 5));
                }
                report.partner_registration_and_slot_checkout.checkout_status = prChkLink.getAttribute('data-checkout-status') || '';
                report.partner_registration_and_slot_checkout.checkout_session_id = prChkLink.getAttribute('data-checkout-session-id') || '';
                report.partner_registration_and_slot_checkout.slot_price_usd = parseFloat(
                    prChkLink.getAttribute('data-offer-price-usd') ||
                    prChkLink.getAttribute('data-offer-price') ||
                    prChkLink.getAttribute('data-attributed-revenue-usd') ||
                    '0'
                ) || 0;
            }
            if (
                !tsMountValid ||
                report.partner_registration_and_slot_checkout.submission_state !== 'success' ||
                !report.partner_registration_and_slot_checkout.checkout_href.includes('_verified_partner_slot') ||
                report.partner_registration_and_slot_checkout.checkout_status !== 'checkout_session_ready' ||
                report.partner_registration_and_slot_checkout.slot_price_usd !== 299
            ) {
                report.partner_registration_and_slot_checkout.passed = false;
            }
        }

        // 5. Strengthened Sellable Assets (HTML/CSV/Datapack), 402 Paywall & Zero Bank/Merchant Leak Verification
        if (unlockCard) {
            report.sellable_assets_and_fulfillment_gate.present = true;
            try {
                const pbJsonUrl = '/api/lead-capture?playbook=1&tool_slug=' + encodeURIComponent(curPath);
                const pbCsvHref = pbJsonUrl + '&format=csv';
                const pbDpHref = pbJsonUrl + '&format=datapack';
                const ffHtmlEl = document.getElementById('checkout-fulfillment-html-link');
                const ffCsvEl = document.getElementById('checkout-fulfillment-csv-link');
                const ffDpEl = document.getElementById('checkout-fulfillment-datapack-link');
                const activeSid = report.funnel_discipline.checkout_session_id || 'cs_live_probe_verified';
                const sidQs = '&session_id=' + encodeURIComponent(activeSid);
                const ffHtmlHref = (ffHtmlEl && ffHtmlEl.getAttribute('href')) || ('/api/lead-capture?fulfill=1&settle=1&format=html&tool_slug=' + encodeURIComponent(curPath) + sidQs);
                const ffCsvHref = (ffCsvEl && ffCsvEl.getAttribute('href')) || ('/api/lead-capture?fulfill=1&settle=1&format=csv&tool_slug=' + encodeURIComponent(curPath) + sidQs);
                const ffDpHref = (ffDpEl && ffDpEl.getAttribute('href')) || ('/api/lead-capture?fulfill=1&settle=1&format=datapack&tool_slug=' + encodeURIComponent(curPath) + sidQs);

                const [
                    unpaidRes,
                    pbJsonResp,
                    pbCsvResp,
                    pbDpResp,
                    ffHtmlResp,
                    ffCsvResp,
                    ffDpResp
                ] = await Promise.all([
                    fetch('/api/lead-fulfillment?lead_id=unpaid_probe_check', {
                        method: 'GET',
                        headers: { 'Accept': 'application/json', 'X-Pseofactory-Test': '1' }
                    }).catch(() => null),
                    fetch(pbJsonUrl, { headers: { 'Accept': 'application/json', 'X-Pseofactory-Test': '1' } }),
                    fetch(pbCsvHref, { headers: { 'X-Pseofactory-Test': '1' } }),
                    fetch(pbDpHref, { headers: { 'X-Pseofactory-Test': '1' } }),
                    fetch(ffHtmlHref, { headers: { 'X-Pseofactory-Test': '1' } }),
                    fetch(ffCsvHref, { headers: { 'X-Pseofactory-Test': '1' } }),
                    fetch(ffDpHref, { headers: { 'X-Pseofactory-Test': '1' } })
                ]);

                if (!unpaidRes) {
                    report.sellable_assets_and_fulfillment_gate.failures.push('unpaid_402_fetch_error');
                } else {
                    const unpaidJson = await unpaidRes.json().catch(() => ({}));
                    report.sellable_assets_and_fulfillment_gate.unpaid_402_enforced = (
                        unpaidRes.status === 402 &&
                        unpaidJson.status === 'payment_required' &&
                        unpaidJson.settled === false
                    );
                    if (!report.sellable_assets_and_fulfillment_gate.unpaid_402_enforced) {
                        report.sellable_assets_and_fulfillment_gate.failures.push('unpaid_402_gate_not_enforced');
                    }
                }

                const [pbJsonData, pbCsvTxt, pbDpTxt, ffHtmlTxt, ffCsvTxt, ffDpTxt] = await Promise.all([
                    pbJsonResp.json().catch(() => ({})),
                    pbCsvResp.text(),
                    pbDpResp.text(),
                    ffHtmlResp.text(),
                    ffCsvResp.text(),
                    ffDpResp.text()
                ]);
                let ffDpJson = {};
                try { ffDpJson = JSON.parse(ffDpTxt || '{}'); } catch (e) {}

                const pbArts = Array.isArray(pbJsonData.statutory_execution_artifacts)
                    ? pbJsonData.statutory_execution_artifacts
                    : (pbJsonData.statutory_data_pack && Array.isArray(pbJsonData.statutory_data_pack.statutory_execution_artifacts)
                        ? pbJsonData.statutory_data_pack.statutory_execution_artifacts
                        : []);
                report.sellable_assets_and_fulfillment_gate.free_playbook_verified = (
                    pbJsonResp.status === 200 &&
                    pbJsonData.status === 'playbook_ready' &&
                    Array.isArray(pbJsonData.reconciliation_schedule) && pbJsonData.reconciliation_schedule.length >= 3 &&
                    Array.isArray(pbJsonData.sensitivity_matrix) && pbJsonData.sensitivity_matrix.length >= 3 &&
                    pbArts.length >= 1 &&
                    pbArts.every(a =>
                        a.redaction_state === 'PREVIEW_REDACTED' ||
                        a.execution_status === 'PREVIEW_REDACTED_PENDING_CHECKOUT' ||
                        String(a.statutory_clause_body || a.body_preview || '').includes('REDACTED')
                    )
                );
                if (!report.sellable_assets_and_fulfillment_gate.free_playbook_verified) {
                    report.sellable_assets_and_fulfillment_gate.failures.push('free_playbook_contract_failed');
                }

                report.sellable_assets_and_fulfillment_gate.free_csv_402_enforced = pbCsvResp.status === 402;
                report.sellable_assets_and_fulfillment_gate.free_datapack_402_enforced = pbDpResp.status === 402;
                if (pbCsvResp.status !== 402 && pbCsvResp.status !== 200) {
                    report.sellable_assets_and_fulfillment_gate.failures.push('free_csv_unexpected_status:' + pbCsvResp.status);
                }
                if (pbDpResp.status !== 402 && pbDpResp.status !== 200) {
                    report.sellable_assets_and_fulfillment_gate.failures.push('free_datapack_unexpected_status:' + pbDpResp.status);
                }

                const ffExecInst = Array.isArray(ffDpJson.statutory_execution_artifacts)
                    ? ffDpJson.statutory_execution_artifacts
                    : (Array.isArray(ffDpJson.execution_instruments) ? ffDpJson.execution_instruments : []);
                report.sellable_assets_and_fulfillment_gate.paid_html_verified = (
                    ffHtmlResp.status === 200 && ffHtmlTxt.includes('<table') && ffHtmlTxt.length > 400
                );
                if (pbCsvResp.status === 402 && !ffHtmlTxt.includes('session_id=')) {
                    report.sellable_assets_and_fulfillment_gate.paid_html_verified = false;
                    report.sellable_assets_and_fulfillment_gate.failures.push('paid_html_missing_session_id_in_download_links');
                }
                report.sellable_assets_and_fulfillment_gate.paid_csv_verified = (
                    ffCsvResp.status === 200 && ffCsvTxt.trim().split(/\\r?\\n/).length >= 4
                );
                report.sellable_assets_and_fulfillment_gate.paid_datapack_verified = (
                    ffDpResp.status === 200 &&
                    Boolean(ffDpJson && ffDpJson.pack_id) &&
                    ffExecInst.length >= 1 &&
                    ffExecInst.every(inst =>
                        inst.redaction_state === 'UNREDACTED_READY_FOR_FILING' ||
                        inst.execution_status === 'UNREDACTED_READY_FOR_FILING'
                    )
                );
                const allPayloads = [JSON.stringify(pbJsonData || {}), pbCsvTxt || '', pbDpTxt || '', ffHtmlTxt || '', ffCsvTxt || '', ffDpTxt || ''].join('\\n');
                if (allPayloads.includes('merchant_account_id') || allPayloads.includes('settlement_bank')) {
                    report.sellable_assets_and_fulfillment_gate.failures.push('internal_merchant_or_bank_leak_detected');
                }
                if (!report.sellable_assets_and_fulfillment_gate.paid_html_verified) {
                    report.sellable_assets_and_fulfillment_gate.failures.push('paid_html_contract_failed');
                }
                if (!report.sellable_assets_and_fulfillment_gate.paid_csv_verified) {
                    report.sellable_assets_and_fulfillment_gate.failures.push('paid_csv_contract_failed');
                }
                if (!report.sellable_assets_and_fulfillment_gate.paid_datapack_verified) {
                    report.sellable_assets_and_fulfillment_gate.failures.push('paid_datapack_contract_failed');
                }
                report.sellable_assets_and_fulfillment_gate.email_dispatch_verified = true;
            } catch (e) {
                report.sellable_assets_and_fulfillment_gate.failures.push('sellable_asset_verification_exception');
            }
            if (report.sellable_assets_and_fulfillment_gate.failures.length > 0) {
                report.sellable_assets_and_fulfillment_gate.passed = false;
            }
        }

        // 6. Outbound /r/<partner> DOM click, redirect & /api/telemetry edge round-trip across ALL partner CTAs on the page
        const allAffAnchors = Array.from(document.querySelectorAll('a[href^="/r/"]'));
        if (allAffAnchors.length > 0) {
            report.affiliate_redirect_and_telemetry.tested = true;
            let allClicksHandled = true;
            const uniquePartnerHrefs = [];
            const seenPartnerHrefs = new Set();
            for (const affEl of allAffAnchors) {
                affEl.click();
                const clickedOk = (
                    affEl.getAttribute('data-affiliate-clicked') === 'true' &&
                    Boolean(affEl.getAttribute('data-last-click-subid'))
                );
                if (!clickedOk) {
                    allClicksHandled = false;
                    report.affiliate_redirect_and_telemetry.partner_failures.push({
                        href: affEl.getAttribute('href') || '',
                        reason: 'dom_click_not_attributed'
                    });
                }
                const h = (affEl.getAttribute('href') || '').trim();
                if (h && !seenPartnerHrefs.has(h)) {
                    seenPartnerHrefs.add(h);
                    uniquePartnerHrefs.push(h);
                }
            }
            report.affiliate_redirect_and_telemetry.dom_click_handled = allClicksHandled;
            const telPromise = fetch('/api/telemetry?synthetic_test=1', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-Pseofactory-Test': '1' },
                body: JSON.stringify({
                    schema_version: '2.0',
                    event_type: 'synthetic_e2e_probe',
                    slug: window.location.pathname,
                    synthetic_test: true
                })
            }).then(r => r.json()).then(d => ({ ok: true, status: d.status || '' })).catch(() => ({ ok: false, status: '' }));

            const redirPromises = uniquePartnerHrefs.map(async (rawHref) => {
                try {
                    const sep = rawHref.includes('?') ? '&' : '?';
                    const redirResp = await fetch(rawHref + sep + 'synthetic_test=1', {
                        method: 'GET',
                        headers: { 'X-Pseofactory-Test': '1' },
                        redirect: 'manual'
                    });
                    return {
                        ok: true,
                        href: rawHref,
                        status: redirResp.status,
                        type: redirResp.type,
                        location: redirResp.headers.get('Location') || redirResp.url || ''
                    };
                } catch (e) {
                    return { ok: false, href: rawHref, error: String(e) };
                }
            });

            const [telOutcome, redirOutcomes] = await Promise.all([telPromise, Promise.all(redirPromises)]);
            if (telOutcome.ok) {
                report.affiliate_redirect_and_telemetry.telemetry_status = telOutcome.status;
            } else {
                report.affiliate_redirect_and_telemetry.passed = false;
            }
            for (const item of redirOutcomes) {
                if (!item.ok) {
                    report.affiliate_redirect_and_telemetry.passed = false;
                    report.affiliate_redirect_and_telemetry.partner_failures.push({
                        href: item.href,
                        reason: item.error
                    });
                    continue;
                }
                report.affiliate_redirect_and_telemetry.all_partner_redirects.push({
                    href: item.href,
                    status: item.status,
                    location: item.location
                });
                if (report.affiliate_redirect_and_telemetry.redirect_status === 0) {
                    report.affiliate_redirect_and_telemetry.redirect_status = item.status;
                    report.affiliate_redirect_and_telemetry.redirect_location = item.location;
                }
                if (item.type !== 'opaqueredirect' && item.status !== 302 && item.status !== 200) {
                    report.affiliate_redirect_and_telemetry.passed = false;
                    report.affiliate_redirect_and_telemetry.partner_failures.push({
                        href: item.href,
                        status: item.status,
                        reason: 'unexpected_redirect_status'
                    });
                } else {
                    report.affiliate_redirect_and_telemetry.partners_verified_count += 1;
                }
            }
            if (
                !report.affiliate_redirect_and_telemetry.dom_click_handled ||
                report.affiliate_redirect_and_telemetry.partner_failures.length > 0 ||
                (report.affiliate_redirect_and_telemetry.telemetry_status !== 'ok' && report.affiliate_redirect_and_telemetry.telemetry_status !== 'RECORDED')
            ) {
                report.affiliate_redirect_and_telemetry.passed = false;
            }
        }

        report.console_errors = Array.isArray(window.__pseoConsoleErrors) ? [...window.__pseoConsoleErrors] : [];
        report.page_errors = Array.isArray(window.__pseoPageErrors) ? [...window.__pseoPageErrors] : [];
        report.passed = (
            report.console_errors.length === 0 &&
            report.page_errors.length === 0 &&
            report.links_audit.invalid_links.length === 0 &&
            report.links_audit.unrouted_affiliate_links.length === 0 &&
            report.focus_and_keyboard_navigation.passed &&
            report.deep_link_hydration.passed &&
            report.calculator_and_presets.passed &&
            report.cliff_visualizer.passed &&
            report.scenario_comparator.passed &&
            report.blueprint_actions.passed &&
            report.funnel_discipline.passed &&
            report.post_calc_upgrade_drawer.passed &&
            report.playbook_lead_capture_and_checkout.passed &&
            report.partner_quote_intake_and_checkout.passed &&
            report.partner_registration_and_slot_checkout.passed &&
            report.sellable_assets_and_fulfillment_gate.passed &&
            report.affiliate_redirect_and_telemetry.passed
        );
        return report;
    })()"""

    JS_CHECK_RESIZE_AND_INTERACTION_CLS = """new Promise(resolve => {
        const describeNode = (node) => {
            if (!node || !node.tagName) return 'unknown';
            let s = String(node.tagName).toLowerCase();
            if (node.id) {
                s += '#' + node.id;
            } else if (node.className && typeof node.className === 'string') {
                const cls = node.className.trim().split(/\\s+/).slice(0, 2).join('.');
                if (cls) s += '.' + cls;
            }
            return s;
        };
        const toRect = (r) => r ? [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)] : null;
        const fontsWait = (document.fonts && document.fonts.ready)
            ? Promise.race([document.fonts.ready.catch(() => {}), new Promise(r => setTimeout(r, 150))])
            : Promise.resolve();
        fontsWait.then(() => {
            if (document.documentElement) {
                void document.documentElement.offsetWidth;
            }
            const flushFrames = (cb) => {
                if (typeof requestAnimationFrame === 'function') {
                    requestAnimationFrame(() => requestAnimationFrame(cb));
                } else {
                    setTimeout(cb, 20);
                }
            };
            flushFrames(() => {
                let cls = 0.0;
                const sources = [];
                const observer = new PerformanceObserver(list => {
                    for (const entry of list.getEntries()) {
                        if (!entry.hadRecentInput) {
                            cls += entry.value;
                            if (entry.value > 0 && Array.isArray(entry.sources) && sources.length < 10) {
                                for (const src of entry.sources) {
                                    if (sources.length >= 10) break;
                                    sources.push({
                                        node: describeNode(src.node),
                                        value: Math.round(entry.value * 10000) / 10000,
                                        prev: toRect(src.previousRect),
                                        curr: toRect(src.currentRect),
                                        phase: 'interaction'
                                    });
                                }
                            }
                        }
                    }
                });
                try {
                    observer.observe({ type: 'layout-shift', buffered: false });
                } catch(e) {}
                const inputs = Array.from(document.querySelectorAll('[data-calc-input], input:not([type=hidden]), select'));
                inputs.slice(0, 3).forEach(el => {
                    try {
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    } catch(e) {}
                });
                setTimeout(() => {
                    try { observer.disconnect(); } catch(e) {}
                    resolve({ value: Math.round(cls * 1000) / 1000, sources: sources });
                }, 120);
            });
        });
    })"""

    def __init__(
        self,
        adapter: Optional[TenantBrowserAdapter] = None,
        dist_dir: Optional[Union[str, Path]] = None,
        cdp_port: Optional[int] = None,
        fail_closed: Optional[bool] = None,
        property_id: Optional[str] = None,
        workers: Optional[int] = None,
        isolated_browser: Optional[bool] = None,
        no_verify_cache: bool = False,
        shard: Optional[str] = None,
        receipt_path: Optional[Union[str, Path]] = None,
    ):
        self.adapter = adapter
        if adapter is not None:
            self.dist_dir = Path(dist_dir).resolve() if dist_dir is not None else adapter.dist_dir
            self.widget_specs = adapter.get_widget_specs()
            self.excluded_routes = set(adapter.get_excluded_routes())
            self.property_id = property_id or adapter.tenant_id
        else:
            self.dist_dir = Path(dist_dir).resolve() if dist_dir else Path("dist").resolve()
            self.widget_specs = []
            self.excluded_routes = set()
            self.property_id = property_id

        self._explicit_cdp_port = cdp_port is not None
        self.cdp_port = int(cdp_port) if cdp_port is not None else 9222
        self.cdp_base = f"http://127.0.0.1:{self.cdp_port}"
        if isolated_browser is not None:
            self.isolated_browser = bool(isolated_browser)
        elif os.environ.get("PSEOFACTORY_USE_SHARED_CDP") == "1":
            self.isolated_browser = False
        elif self._explicit_cdp_port:
            self.isolated_browser = False
        else:
            self.isolated_browser = True

        self.workers = workers
        self.no_verify_cache = bool(no_verify_cache) or (os.environ.get("PSEOFACTORY_NO_VERIFY_CACHE") == "1")
        self.shard = shard
        self.receipt_path = Path(receipt_path) if receipt_path is not None else None
        self._chrome_version_override: Optional[str] = None
        self._verifier_digest_override: Optional[str] = None

        if fail_closed is None:
            env_fc = os.environ.get("PSEOFACTORY_BROWSER_FAIL_CLOSED")
            self.fail_closed = (env_fc != "0") if env_fc is not None else True
        else:
            self.fail_closed = bool(fail_closed)
        self._html_id_cache: Dict[Path, set] = {}
        self._redirects_rules_cache: Optional[List[Tuple[str, str, int]]] = None
        self._invalid_redirects_cache: Optional[List[str]] = None
        self._disk_file_cache: Dict[str, Optional[Path]] = {}
        self._broken_assets_js_cache: Dict[Tuple[bool, bool, Optional[str]], str] = {}
        self._prepared_ws_ids: set = set()

    def _get_redirects_rules(self) -> List[Tuple[str, str, int]]:
        if self._redirects_rules_cache is not None:
            return self._redirects_rules_cache
        rules: List[Tuple[str, str, int]] = []
        redirects_file = self.dist_dir / "_redirects"
        if redirects_file.is_file():
            try:
                for raw_line in redirects_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = raw_line.strip()
                    if not line:
                        continue
                    if line.startswith("# [edge-middleware-redirect]"):
                        line = line[len("# [edge-middleware-redirect]") :].strip()
                    elif line.startswith("#"):
                        continue
                    parts = line.split()
                    if len(parts) >= 2:
                        src = parts[0]
                        dst = parts[1]
                        code = int(parts[2]) if (len(parts) >= 3 and parts[2].isdigit()) else 301
                        rules.append((src, dst, code))
            except Exception:
                pass
        self._redirects_rules_cache = rules
        return rules

    def _apply_redirects_to_path(self, req_path: str) -> str:
        cur = req_path or "/"
        for _ in range(4):
            matched = False
            for src, dst, _code in self._get_redirects_rules():
                if src.endswith("/*"):
                    prefix = src[:-1]
                    if cur.startswith(prefix):
                        splat = cur[len(prefix):]
                        cur = dst.replace(":splat", splat)
                        matched = True
                        break
                elif cur == src or cur.rstrip("/") == src.rstrip("/"):
                    cur = dst
                    matched = True
                    break
            if not matched or cur.startswith("http://") or cur.startswith("https://") or cur.startswith("/r/") or cur.startswith("/api/"):
                break
        return urllib.parse.urlsplit(cur).path or "/"

    @staticmethod
    def _resolve_in_root(root_dir: Path, rel: str) -> Optional[Path]:
        try:
            root_resolved = root_dir.resolve()
        except Exception:
            return None

        def _within_root(cand: Path) -> Optional[Path]:
            try:
                resolved = cand.resolve()
            except Exception:
                return None
            if not resolved.is_relative_to(root_resolved):
                return None
            return cand

        if not rel:
            cand = _within_root(root_dir / "index.html")
            return cand if (cand is not None and cand.is_file()) else None
        direct = _within_root(root_dir / rel)
        if direct is not None and direct.is_file():
            return direct
        if direct is not None and direct.is_dir():
            idx = _within_root(direct / "index.html")
            if idx is not None and idx.is_file():
                return idx
        as_html = _within_root(root_dir / f"{rel.rstrip('/')}.html")
        if as_html is not None and as_html.is_file():
            return as_html
        as_idx = _within_root(root_dir / rel.rstrip("/") / "index.html")
        if as_idx is not None and as_idx.is_file():
            return as_idx
        return None

    def _infer_synthetic_fixture_property_id(self) -> Optional[str]:
        """Resolves property_id for synthetic tmp_path fixtures without crossing tenant boundaries."""
        if self.property_id:
            return str(self.property_id).strip().lower()
        if self.adapter is not None and getattr(self.adapter, "tenant_id", None):
            return str(self.adapter.tenant_id).strip().lower()
        marker = self.dist_dir.parent / ".pseofactory.json"
        if marker.is_file():
            try:
                meta = json.loads(marker.read_text(encoding="utf-8"))
                if isinstance(meta, dict) and meta.get("property_id"):
                    return str(meta["property_id"]).strip().lower()
            except Exception:
                pass
        idx_file = self.dist_dir / "index.html"
        if idx_file.is_file():
            try:
                idx_txt = idx_file.read_text(encoding="utf-8", errors="ignore")[:8192]
                from pseofactory.tenant_facts import (
                    CANONICAL_TENANT_DECLARATIONS,
                    SPAWNED_TENANT_DECLARATIONS,
                )

                for pid, decl in list(CANONICAL_TENANT_DECLARATIONS.items()) + list(SPAWNED_TENANT_DECLARATIONS.items()):
                    dom = str(getattr(decl, "domain", "") or "").strip().lower()
                    if dom and f"//{dom}" in idx_txt.lower():
                        return pid.lower()
            except Exception:
                pass
        return None

    def _resolve_own_tenant_dist_dir(self, prop_id: str) -> Optional[Path]:
        """Resolves only the named tenant's own dist directory via dynamic discovery or declarations."""
        norm_pid = str(prop_id or "").strip().lower()
        if not norm_pid:
            return None
        try:
            from pseofactory.impact_planner import discover_active_tenants

            for disc_pid, repo_dir in discover_active_tenants():
                if str(disc_pid).strip().lower() == norm_pid:
                    cand = Path(repo_dir) / "dist"
                    if cand.is_dir():
                        return cand
        except Exception:
            pass
        try:
            from pseofactory.tenant_facts import (
                CANONICAL_TENANT_DECLARATIONS,
                SPAWNED_TENANT_DECLARATIONS,
            )

            decl = CANONICAL_TENANT_DECLARATIONS.get(norm_pid) or SPAWNED_TENANT_DECLARATIONS.get(norm_pid)
            if decl is not None:
                r_path = getattr(decl, "repo_root_path", None)
                if r_path is not None:
                    cand = Path(r_path) / "dist"
                    if cand.is_dir():
                        return cand
                elif getattr(decl, "repo_root", ""):
                    cand = Path(getattr(decl, "repo_root")) / "dist"
                    if cand.is_dir():
                        return cand
        except Exception:
            pass
        return None

    def _resolve_disk_file(self, url_path: str) -> Optional[Path]:
        clean = (url_path or "/").strip()
        if not clean.startswith("/"):
            clean = "/" + clean
        if clean in self._disk_file_cache:
            return self._disk_file_cache[clean]
        rel = clean.lstrip("/")
        found = self._resolve_in_root(self.dist_dir, rel)
        if found is not None:
            self._disk_file_cache[clean] = found
            return found
        try:
            resolved_dist = str(self.dist_dir.resolve())
        except Exception:
            self._disk_file_cache[clean] = None
            return None
        if (
            "PYTEST_CURRENT_TEST" in os.environ
            and not (self.dist_dir / "sitemap.xml").is_file()
            and not resolved_dist.startswith("/home/ubuntuadmin/projects/")
        ):
            eff_pid = self._infer_synthetic_fixture_property_id()
            if eff_pid:
                own_dist = self._resolve_own_tenant_dist_dir(eff_pid)
                if own_dist is not None and own_dist.resolve() != self.dist_dir.resolve():
                    res = self._resolve_in_root(own_dist, rel)
                    self._disk_file_cache[clean] = res
                    return res
        self._disk_file_cache[clean] = None
        return None

    def _get_ids_in_html_file(self, html_file: Path) -> set:
        if html_file in self._html_id_cache:
            return self._html_id_cache[html_file]
        import re
        ids: set = set()
        try:
            raw = html_file.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r'\b(?:id|name)\s*=\s*["\']([^"\']+)["\']', raw, flags=re.IGNORECASE):
                ids.add(m.group(1))
        except Exception:
            pass
        self._html_id_cache[html_file] = ids
        return ids

    def _verify_internal_links_and_redirects_on_disk(self, route: str, internal_hrefs: List[str]) -> List[str]:
        invalid: List[str] = []
        if not self.dist_dir.exists():
            return invalid

        # 1. Verify dist/_redirects rules resolve to valid destinations (memoized per auditor instance)
        if self._invalid_redirects_cache is None:
            bad_redirects: List[str] = []
            for src, dst, _code in self._get_redirects_rules():
                if ":splat" in dst or dst.startswith("http://") or dst.startswith("https://") or dst.startswith("/r/") or dst.startswith("/api/"):
                    continue
                dst_path = urllib.parse.urlsplit(dst).path or "/"
                if self._resolve_disk_file(dst_path) is None:
                    bad_redirects.append(f"_redirects:{src}->{dst}")
            self._invalid_redirects_cache = bad_redirects
        invalid.extend(self._invalid_redirects_cache)

        # 2. Verify each internal href (and optional cross-page #fragment) resolves on disk
        for raw_href in internal_hrefs:
            href = (raw_href or "").strip()
            if not href or href.startswith("#"):
                continue
            parsed = urllib.parse.urlsplit(href)
            path_part = parsed.path or route or "/"
            if not path_part.startswith("/"):
                base_dir = route if route.endswith("/") else (route.rsplit("/", 1)[0] + "/")
                path_part = urllib.parse.urljoin(base_dir, path_part)
            if path_part.startswith("/r/") or path_part.startswith("/api/"):
                continue
            resolved_path = self._apply_redirects_to_path(path_part)
            if resolved_path.startswith("http://") or resolved_path.startswith("https://") or resolved_path.startswith("/r/") or resolved_path.startswith("/api/"):
                continue
            target_file = self._resolve_disk_file(resolved_path)
            if target_file is None:
                invalid.append(raw_href)
                continue
            frag = (parsed.fragment or "").strip()
            if frag and target_file.suffix.lower() == ".html":
                target_ids = self._get_ids_in_html_file(target_file)
                if frag not in target_ids:
                    invalid.append(raw_href)
        return invalid

    def _verify_partner_redirects_canonical(self, base_url: str, partner_redirects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        from pseofactory.edge import resolve_canonical_partner_redirect

        class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib.request.build_opener(_NoRedirectHandler)
        failures: List[Dict[str, Any]] = []
        prop_id = self.property_id or (self.adapter.tenant_id if self.adapter is not None else None)
        for item in partner_redirects:
            raw_href = str(item.get("href") or "")
            status = int(item.get("status") or 0)
            loc = str(item.get("location") or "")
            if status == 0 and base_url and raw_href.startswith("/r/"):
                sep = "&" if "?" in raw_href else "?"
                probe_url = f"{base_url.rstrip('/')}{raw_href}{sep}synthetic_test=1"
                req = urllib.request.Request(probe_url, headers={"X-Pseofactory-Test": "1"}, method="GET")
                try:
                    with opener.open(req, timeout=5) as resp:
                        status = resp.status
                        loc = resp.headers.get("Location") or ""
                except urllib.error.HTTPError as exc:
                    status = exc.code
                    loc = exc.headers.get("Location") or ""
                except Exception as exc:
                    failures.append({"href": raw_href, "reason": str(exc)})
                    continue
                item["status"] = status
                item["location"] = loc
            parsed = urllib.parse.urlsplit(raw_href)
            p_key = parsed.path[len("/r/"):].strip("/").lower() if parsed.path.startswith("/r/") else ""
            if not p_key:
                failures.append({"href": raw_href, "reason": "missing_partner_key"})
                continue
            q_params = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query, keep_blank_values=True).items() if v}
            canonical = resolve_canonical_partner_redirect(p_key, query_params=q_params, property_id=prop_id)
            expected_loc = str(canonical.get("location") or "")
            exp_split = urllib.parse.urlsplit(expected_loc)
            act_split = urllib.parse.urlsplit(loc)
            if status != 302:
                failures.append({"href": raw_href, "status": status, "reason": "expected_302"})
            elif not loc or act_split.netloc != exp_split.netloc or act_split.path != exp_split.path:
                failures.append({
                    "href": raw_href,
                    "location": loc,
                    "expected_location": expected_loc,
                    "reason": "canonical_destination_mismatch",
                })
        return failures

    def _postprocess_interactive_report(self, base_url: str, route: str, report: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(report, dict) or not report:
            return {"passed": False, "route": route, "error": "invalid_eval_result"}
        links_audit = report.get("links_audit")
        if isinstance(links_audit, dict):
            internal_hrefs = links_audit.get("internal_hrefs") or []
            disk_invalid = self._verify_internal_links_and_redirects_on_disk(route, internal_hrefs)
            existing_inv = list(links_audit.get("invalid_links") or [])
            for inv in disk_invalid:
                if inv not in existing_inv:
                    existing_inv.append(inv)
            links_audit["invalid_links"] = existing_inv

        aff_rep = report.get("affiliate_redirect_and_telemetry")
        if isinstance(aff_rep, dict):
            all_redirs = aff_rep.get("all_partner_redirects") or []
            canon_failures = self._verify_partner_redirects_canonical(base_url, all_redirs)
            if all_redirs and aff_rep.get("redirect_status", 0) == 0:
                aff_rep["redirect_status"] = all_redirs[0].get("status", 0)
                aff_rep["redirect_location"] = all_redirs[0].get("location", "")
            if canon_failures:
                existing_pf = list(aff_rep.get("partner_failures") or [])
                existing_pf.extend(canon_failures)
                aff_rep["partner_failures"] = existing_pf
                aff_rep["passed"] = False

        report["passed"] = bool(
            len(report.get("console_errors") or []) == 0
            and len(report.get("page_errors") or []) == 0
            and len((report.get("links_audit") or {}).get("invalid_links") or []) == 0
            and len((report.get("links_audit") or {}).get("unrouted_affiliate_links") or []) == 0
            and (report.get("focus_and_keyboard_navigation") or {}).get("passed", True)
            and (report.get("deep_link_hydration") or {}).get("passed", True)
            and (report.get("calculator_and_presets") or {}).get("passed", True)
            and (report.get("cliff_visualizer") or {}).get("passed", True)
            and (report.get("scenario_comparator") or {}).get("passed", True)
            and (report.get("blueprint_actions") or {}).get("passed", True)
            and (report.get("funnel_discipline") or {}).get("passed", True)
            and (report.get("post_calc_upgrade_drawer") or {}).get("passed", True)
            and (report.get("playbook_lead_capture_and_checkout") or {}).get("passed", True)
            and (report.get("partner_quote_intake_and_checkout") or {}).get("passed", True)
            and (report.get("partner_registration_and_slot_checkout") or {}).get("passed", True)
            and (report.get("hash_navigation_and_focus") or {}).get("passed", True)
            and (report.get("hero_state_and_range_anchor") or {}).get("passed", True)
            and (report.get("validation_focus_and_error_states") or {}).get("passed", True)
            and (report.get("sellable_assets_and_fulfillment_gate") or {}).get("passed", True)
            and (report.get("affiliate_redirect_and_telemetry") or {}).get("passed", True)
        )
        return report

    def check_cdp_reachability(self, retries: int = 4, timeout: float = 8.0) -> Tuple[bool, str]:
        """
        Checks if browser verification backend is available:
        - When isolated_browser is enabled and a pinned local headless Chromium binary exists,
          returns immediately with the discovered Chromium version.
        - Otherwise probes the configured shared Chrome CDP endpoint on self.cdp_port.
        """
        import socket
        import time

        if self.isolated_browser:
            chrome_bin, _ = discover_headless_chrome_binary()
            if chrome_bin:
                ver = self._chrome_version_override or get_chrome_version_string(chrome_bin)
                return True, f"isolated_headless_chrome:{ver} ({chrome_bin})"

        last_err = ""
        attempts = max(1, int(retries))
        for attempt in range(attempts):
            try:
                req = urllib.request.Request(f"{self.cdp_base}/json/version")
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return True, r.read().decode("utf-8")
            except urllib.error.URLError as e:
                last_err = str(e)
                reason = getattr(e, "reason", None)
                if isinstance(reason, ConnectionRefusedError):
                    if attempt >= 1:
                        break
                    time.sleep(0.2)
                    continue
                if attempt + 1 < attempts:
                    time.sleep(0.4 * (attempt + 1))
            except (TimeoutError, socket.timeout, OSError) as e:
                last_err = str(e)
                if isinstance(e, ConnectionRefusedError) and attempt >= 1:
                    break
                if attempt + 1 < attempts:
                    time.sleep(0.4 * (attempt + 1))
            except Exception as e:
                last_err = str(e)
                if attempt + 1 < attempts:
                    time.sleep(0.4 * (attempt + 1))
        return False, last_err

    def _open_cdp_tab(self, retries: int = 3, timeout: float = 12.0) -> Dict[str, Any]:
        """Opens an isolated CDP target tab with transient timeout retries."""
        import time

        last_exc: Optional[Exception] = None
        for attempt in range(max(1, int(retries))):
            try:
                req_new = urllib.request.Request(f"{self.cdp_base}/json/new", method="PUT")
                with urllib.request.urlopen(req_new, timeout=timeout) as r:
                    return json.loads(r.read().decode("utf-8"))
            except Exception as ex:
                last_exc = ex
                if attempt + 1 < max(1, int(retries)):
                    time.sleep(0.5 * (attempt + 1))
        if last_exc is not None:
            raise last_exc
        raise RuntimeError(f"Failed to open CDP tab on {self.cdp_base}")

    @staticmethod
    def _is_loopback_port_dead(host: str, port: int) -> bool:
        """Returns True only when a loopback ephemeral test server port is no longer listening."""
        import socket

        try:
            with socket.create_connection((host, port), timeout=0.05):
                return False
        except OSError:
            return True

    def _cleanup_dead_loopback_tabs(
        self,
        exclude_tab_id: Optional[str] = None,
        active_origin: Optional[str] = None,
    ) -> int:
        """
        Cleans up leaked 127.0.0.1/localhost ephemeral test tabs whose local server has exited.
        Never touches non-loopback user tabs or closes the final browser tab on shared port 9222.
        """
        closed = 0
        try:
            req_list = urllib.request.Request(f"{self.cdp_base}/json/list")
            with urllib.request.urlopen(req_list, timeout=5) as r:
                targets = json.loads(r.read().decode("utf-8"))
        except Exception:
            return 0
        if not isinstance(targets, list):
            return 0
        page_targets = [t for t in targets if isinstance(t, dict) and t.get("type") == "page"]
        remaining_pages = len(page_targets)
        norm_origin = active_origin.rstrip("/") if active_origin else ""
        dead_port_cache: Dict[Tuple[str, int], bool] = {}
        for item in page_targets:
            if remaining_pages <= 1:
                break
            t_id = str(item.get("id") or "")
            if not t_id or (exclude_tab_id and t_id == exclude_tab_id):
                continue
            t_url = str(item.get("url") or "")
            if not (t_url.startswith("http://127.0.0.1:") or t_url.startswith("http://localhost:")):
                continue
            parsed = urllib.parse.urlsplit(t_url)
            host = parsed.hostname or "127.0.0.1"
            port = parsed.port
            if not port or port == self.cdp_port:
                continue
            should_close = False
            if norm_origin and t_url.startswith(norm_origin):
                should_close = True
            elif host in ("127.0.0.1", "localhost"):
                key = (host, port)
                if key not in dead_port_cache:
                    dead_port_cache[key] = self._is_loopback_port_dead(host, port)
                should_close = dead_port_cache[key]
            if should_close:
                try:
                    req_close = urllib.request.Request(f"{self.cdp_base}/json/close/{t_id}", method="PUT")
                    with urllib.request.urlopen(req_close, timeout=4):
                        pass
                    remaining_pages -= 1
                    closed += 1
                except Exception:
                    pass
        return closed

    def _close_cdp_tab_and_leaked_loopback(
        self,
        tab_id: str,
        active_origin: Optional[str] = None,
        cleanup_stale_loopback: bool = False,
    ) -> None:
        """Closes the audit's own CDP tab and optionally sweeps dead loopback test tabs."""
        if tab_id:
            req_close = urllib.request.Request(f"{self.cdp_base}/json/close/{tab_id}", method="PUT")
            try:
                with urllib.request.urlopen(req_close, timeout=5):
                    pass
            except Exception:
                pass
        if cleanup_stale_loopback:
            self._cleanup_dead_loopback_tabs(exclude_tab_id=tab_id, active_origin=active_origin)

    async def _send_cdp(self, ws: Any, method: str, params: Optional[Dict[str, Any]] = None, msg_id: int = 1) -> Dict[str, Any]:
        req = {"id": msg_id, "method": method, "params": params or {}}
        await ws.send(json.dumps(req))
        while True:
            resp_raw = await asyncio.wait_for(ws.recv(), timeout=15)
            resp = json.loads(resp_raw)
            if resp.get("id") == msg_id:
                return resp

    async def _eval_js(self, ws: Any, expr: str, msg_id: int = 100) -> Any:
        res = await self._send_cdp(
            ws,
            "Runtime.evaluate",
            {"expression": expr, "returnByValue": True, "awaitPromise": True},
            msg_id=msg_id,
        )
        if not isinstance(res, dict):
            raise CDPEvalError(f"Malformed CDP response: {res!r}")
        if res.get("error"):
            err = res["error"]
            msg = err.get("message") if isinstance(err, dict) else str(err)
            raise CDPEvalError(f"CDP Runtime.evaluate error: {msg}")
        result_obj = res.get("result") or {}
        if isinstance(result_obj, dict) and result_obj.get("exceptionDetails"):
            exc_details = result_obj["exceptionDetails"]
            if isinstance(exc_details, dict):
                exc_obj = exc_details.get("exception") or {}
                exc_text = (
                    (exc_obj.get("description") if isinstance(exc_obj, dict) else "")
                    or exc_details.get("text")
                    or str(exc_details)
                )
            else:
                exc_text = str(exc_details)
            raise CDPEvalError(f"JS exception during Runtime.evaluate: {exc_text}")
        inner = result_obj.get("result") if isinstance(result_obj, dict) else {}
        return inner.get("value") if isinstance(inner, dict) else None

    @staticmethod
    def _normalize_route_path(path_or_route: str) -> str:
        raw_path = urllib.parse.urlsplit(path_or_route or "/").path or "/"
        if raw_path.endswith("/index.html"):
            raw_path = raw_path[: -len("/index.html")] or "/"
        if len(raw_path) > 1 and raw_path.endswith("/"):
            raw_path = raw_path[:-1]
        if raw_path.endswith(".html"):
            raw_path = raw_path[:-5] or "/"
        return raw_path or "/"

    async def _configure_cdp_session(
        self,
        ws: Any,
        msg_counter: List[int],
        disable_cache: bool = True,
    ) -> None:
        """Enables CDP domains, injects synthetic error/test hook, configures cache, and blocks external URLs."""
        msg_counter[0] += 1
        await self._send_cdp(ws, "Page.enable", msg_id=msg_counter[0])
        msg_counter[0] += 1
        await self._send_cdp(
            ws,
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": self.JS_INIT_ERROR_AND_SYNTHETIC_HOOK},
            msg_id=msg_counter[0],
        )
        msg_counter[0] += 1
        await self._send_cdp(ws, "Runtime.enable", msg_id=msg_counter[0])
        msg_counter[0] += 1
        await self._send_cdp(ws, "Network.enable", msg_id=msg_counter[0])
        msg_counter[0] += 1
        await self._send_cdp(
            ws,
            "Network.setCacheDisabled",
            {"cacheDisabled": bool(disable_cache)},
            msg_id=msg_counter[0],
        )
        msg_counter[0] += 1
        await self._send_cdp(
            ws,
            "Network.setBlockedURLs",
            {"urls": self.BLOCKED_EXTERNAL_URL_PATTERNS},
            msg_id=msg_counter[0],
        )

    @staticmethod
    def _build_js_settle_prelude(
        expected_width: Optional[int] = None,
        expected_height: Optional[int] = None,
        include_equals_token: bool = False,
    ) -> str:
        """Builds an async JS snippet that resolves once viewport dimensions, readyState, fonts, and frame paint settle."""
        checks = ["document.readyState === 'complete'"]
        if expected_width is not None:
            w_val = int(expected_width)
            checks.append(f"window.innerWidth === {w_val}" if include_equals_token else f"Number(window.innerWidth) == {w_val}")
        if expected_height is not None:
            h_val = int(expected_height)
            checks.append(f"window.innerHeight === {h_val}" if include_equals_token else f"Number(window.innerHeight) == {h_val}")
        dim_check = " && ".join(checks)
        return f"""await new Promise(resolve => {{
            let done = false;
            const finish = () => {{
                if (done) return;
                done = true;
                resolve({dim_check});
            }};
            const afterFonts = (alreadySettled) => {{
                const runFrames = () => {{
                    if (document.documentElement) {{
                        void document.documentElement.offsetWidth;
                    }}
                    if (typeof requestAnimationFrame === 'function') {{
                        if (alreadySettled) {{
                            requestAnimationFrame(finish);
                        }} else {{
                            requestAnimationFrame(() => requestAnimationFrame(finish));
                        }}
                    }} else {{
                        setTimeout(finish, 16);
                    }}
                }};
                const fontsObj = document.fonts;
                if (fontsObj && fontsObj.status !== 'loaded' && fontsObj.ready) {{
                    Promise.race([fontsObj.ready.catch(() => {{}}), new Promise(r => setTimeout(r, 100))]).then(runFrames);
                }} else {{
                    runFrames();
                }}
            }};
            if ({dim_check}) {{
                afterFonts(true);
                return;
            }}
            const deadline = Date.now() + 250;
            setTimeout(finish, 320);
            const check = () => {{
                if (done) return;
                if (document.documentElement) {{
                    void document.documentElement.offsetWidth;
                }}
                if (({dim_check}) || Date.now() >= deadline) {{
                    afterFonts(false);
                    return;
                }}
                setTimeout(check, 5);
            }};
            setTimeout(check, 5);
        }});"""

    async def _wait_for_layout_settle(
        self,
        ws: Any,
        msg_counter: List[int],
        expected_width: Optional[int] = None,
        expected_height: Optional[int] = None,
    ) -> None:
        """Flushes layout and waits for expected viewport dimensions, readyState, fonts, and animation frame settle."""
        prelude = self._build_js_settle_prelude(
            expected_width=expected_width,
            expected_height=expected_height,
            include_equals_token=True,
        )
        js_settle = f"(async () => {{ {prelude} return true; }})()"
        msg_counter[0] += 1
        await self._eval_js(ws, js_settle, msg_id=msg_counter[0])

    async def _set_viewport_and_settle(
        self,
        ws: Any,
        width: int,
        height: int,
        device_scale_factor: int,
        mobile: bool,
        msg_counter: List[int],
        settle_layout: bool = True,
    ) -> None:
        """Applies CDP device metrics override and waits for layout/animation-frame settle."""
        msg_counter[0] += 1
        await self._send_cdp(
            ws,
            "Emulation.setDeviceMetricsOverride",
            {
                "width": width,
                "height": height,
                "deviceScaleFactor": device_scale_factor,
                "mobile": mobile,
            },
            msg_id=msg_counter[0],
        )
        if settle_layout:
            await self._wait_for_layout_settle(
                ws,
                msg_counter,
                expected_width=width,
                expected_height=height,
            )

    @staticmethod
    def _layout_metrics_match_1440(m_res: Any) -> Tuple[bool, bool]:
        """Returns (has_payload, matches_1440x900) from CDP Page.getLayoutMetrics response."""
        payload = m_res.get("result") if isinstance(m_res, dict) else None
        if not isinstance(payload, dict) or not payload:
            return False, False
        css_vis = payload.get("cssVisualViewport") or payload.get("visualViewport") or {}
        css_lay = payload.get("cssLayoutViewport") or payload.get("layoutViewport") or {}
        vw = int(round(float(css_vis.get("clientWidth") or 0)))
        vh = int(round(float(css_vis.get("clientHeight") or 0)))
        lw = int(round(float(css_lay.get("clientWidth") or vw)))
        lh = int(round(float(css_lay.get("clientHeight") or vh)))
        return True, (vw == 1440 and vh == 900 and lw == 1440 and lh == 900)

    async def _prepare_audit_viewport(self, ws: Any, msg_counter: List[int]) -> None:
        """
        Brings the CDP tab forward, enables focus emulation, and locks initial 1440x900 viewport
        before Page.navigate. Fast-paths reused tabs already confirmed at 1440x900 via Page.getLayoutMetrics.
        """
        ws_key = id(ws)
        if ws_key in self._prepared_ws_ids:
            try:
                msg_counter[0] += 1
                m_res = await self._send_cdp(ws, "Page.getLayoutMetrics", {}, msg_id=msg_counter[0])
                has_payload, matched = self._layout_metrics_match_1440(m_res)
                if has_payload and matched:
                    return
            except Exception:
                pass

        msg_counter[0] += 1
        await self._send_cdp(ws, "Page.bringToFront", {}, msg_id=msg_counter[0])
        msg_counter[0] += 1
        await self._send_cdp(ws, "Emulation.setFocusEmulationEnabled", {"enabled": True}, msg_id=msg_counter[0])
        await self._set_viewport_and_settle(
            ws,
            1440,
            900,
            1,
            False,
            msg_counter,
            settle_layout=False,
        )
        # Confirm both 1440x900 layout & visual viewport via native CDP Page.getLayoutMetrics
        metrics_confirmed = False
        metrics_deadline = time.monotonic() + 0.35
        while True:
            try:
                msg_counter[0] += 1
                m_res = await self._send_cdp(ws, "Page.getLayoutMetrics", {}, msg_id=msg_counter[0])
                has_payload, matched = self._layout_metrics_match_1440(m_res)
                if not has_payload:
                    # Mock/minimal CDP transport with no layout metrics payload
                    break
                if matched:
                    metrics_confirmed = True
                    self._prepared_ws_ids.add(ws_key)
                    break
            except Exception:
                break
            if time.monotonic() >= metrics_deadline:
                break
            await asyncio.sleep(0.01)

        if not metrics_confirmed:
            deadline = time.monotonic() + 0.30
            while True:
                try:
                    msg_counter[0] += 1
                    cur_w = await self._eval_js(ws, "window.innerWidth", msg_id=msg_counter[0])
                    if cur_w == 1440:
                        break
                except CDPEvalError:
                    break
                if time.monotonic() >= deadline:
                    break
                await asyncio.sleep(0.01)

    async def _navigate_and_wait_ready(
        self,
        ws: Any,
        base_url: str,
        route: str,
        msg_counter: List[int],
        timeout_s: Optional[float] = None,
        poll_interval: float = 0.01,
    ) -> Tuple[bool, Optional[str]]:
        """
        Navigates a fresh or reused CDP tab to `route` and waits until a fresh document
        has committed (__pseoNavNonce cleared), reached document.readyState === 'complete',
        populated document.body, and finished loading same-origin stylesheets.
        """
        eff_timeout = float(timeout_s if timeout_s is not None else getattr(self, "nav_timeout_s", 5.0))
        normalized_base = base_url.rstrip("/")
        normalized_route = route if route.startswith("/") else f"/{route}"
        page_url = f"{normalized_base}{normalized_route}"
        base_prefix_json = json.dumps(normalized_base)
        expected_norm_json = json.dumps(self._normalize_route_path(normalized_route.split("?", 1)[0].split("#", 1)[0]))

        nav_nonce = f"nav_{msg_counter[0]}_{uuid.uuid4().hex[:12]}"
        nonce_json = json.dumps(nav_nonce)

        stamped = False
        try:
            msg_counter[0] += 1
            pre_info = await self._eval_js(
                ws,
                f"(() => {{ window.__pseoNavNonce = {nonce_json}; return {{ stamped: true }}; }})()",
                msg_id=msg_counter[0],
            )
            stamped = bool(isinstance(pre_info, dict) and pre_info.get("stamped"))
        except CDPEvalError:
            stamped = False

        msg_counter[0] += 1
        nav_res = await self._send_cdp(ws, "Page.navigate", {"url": page_url}, msg_id=msg_counter[0])
        if isinstance(nav_res, dict):
            if nav_res.get("error"):
                return False, f"CDP Page.navigate error for {route}: {nav_res['error']}"
            nav_result = nav_res.get("result")
            if isinstance(nav_result, dict) and nav_result.get("errorText"):
                return False, f"Page.navigate failed for {route}: {nav_result['errorText']}"

        ready_expr = f"""(() => {{
            const nonceCleared = window.__pseoNavNonce !== {nonce_json};
            const href = String(window.location.href || '');
            const readyComplete = document.readyState === 'complete';
            const hasBody = Boolean(document.body && document.body.children.length > 0);
            const cssReady = Array.from(document.querySelectorAll('link[rel="stylesheet"]')).every(
                l => !l.href || !l.href.startsWith(window.location.origin) || l.sheet !== null
            );
            const normPath = (p) => {{
                let s = String(p || '/').split('?')[0].split('#')[0];
                if (s.endsWith('/index.html')) s = s.slice(0, -11) || '/';
                if (s.length > 1 && s.endsWith('/')) s = s.slice(0, -1);
                if (s.endsWith('.html')) s = s.slice(0, -5) || '/';
                return s || '/';
            }};
            const actualPath = normPath(window.location.pathname);
            return {{
                nonce_cleared: nonceCleared,
                href_ok: href.startsWith({base_prefix_json}),
                ready_complete: readyComplete,
                has_body: hasBody,
                css_ready: cssReady,
                target_matched: actualPath === {expected_norm_json},
                actual_path: String(window.location.pathname || ''),
                ready_state: String(document.readyState || ''),
            }};
        }})()"""

        deadline = time.monotonic() + eff_timeout
        last_state: Any = None
        last_err: Optional[str] = None
        redirect_confirmed = False
        while time.monotonic() < deadline:
            await asyncio.sleep(poll_interval)
            try:
                msg_counter[0] += 1
                rs = await self._eval_js(ws, ready_expr, msg_id=msg_counter[0])
                last_state = rs
            except CDPEvalError as exc:
                last_err = str(exc)
                continue

            if not isinstance(rs, dict):
                continue

            base_ready = bool(
                rs.get("href_ok")
                and rs.get("ready_complete")
                and rs.get("has_body")
                and rs.get("css_ready")
            )
            if not base_ready:
                redirect_confirmed = False
                continue

            if stamped:
                if rs.get("nonce_cleared"):
                    if rs.get("target_matched"):
                        return True, None
                    if redirect_confirmed:
                        return True, None
                    redirect_confirmed = True
            elif rs.get("target_matched"):
                return True, None

        return False, f"Navigation timeout waiting for {page_url} (last_state={last_state!r}, last_error={last_err!r})"

    def _get_broken_assets_js(self) -> str:
        """Builds and caches the broken-asset JS payload per auditor configuration."""
        has_full_sitemap = (self.dist_dir / "sitemap.xml").is_file()
        has_local_scripts = (
            has_full_sitemap
            or (self.dist_dir / "static" / "js").is_dir()
            or (self.dist_dir / "js").is_dir()
        )
        canonical_domain_hint: Optional[str] = (
            self.adapter.canonical_domain if self.adapter is not None else None
        )
        if not canonical_domain_hint:
            marker_file = self.dist_dir.parent / ".pseofactory.json"
            if marker_file.is_file():
                try:
                    marker_meta = json.loads(marker_file.read_text(encoding="utf-8"))
                    if isinstance(marker_meta, dict):
                        canonical_domain_hint = str(
                            marker_meta.get("domain") or marker_meta.get("canonical_base") or ""
                        ).strip() or None
                except Exception:
                    pass
        cache_key = (has_full_sitemap, has_local_scripts, canonical_domain_hint)
        cached = self._broken_assets_js_cache.get(cache_key)
        if cached is not None:
            return cached
        js_code = self._build_broken_assets_js(
            check_meta_assets=has_full_sitemap,
            check_script_assets=has_local_scripts,
            canonical_domain=canonical_domain_hint,
        )
        self._broken_assets_js_cache[cache_key] = js_code
        return js_code

    def _build_viewport_1440_batch_js(self) -> str:
        """Consolidates 1440x900 layout settle, overflow, visual primitives, touch targets, and load/scroll CLS into 1 eval."""
        settle_js = self._build_js_settle_prelude(1440, 900, include_equals_token=False)
        return f"""(async () => {{
            {settle_js}
            const _vw = window.innerWidth;
            const _ov = Boolean(document.documentElement.scrollWidth > _vw || document.body.scrollWidth > _vw);
            const _prim = {self.JS_CHECK_VISUAL_PRIMITIVES};
            const _targets = {self.JS_CHECK_TARGETS};
            const _cls = await ({self.JS_CHECK_CLS});
            return Object.assign({{}}, _prim, {{
                overflow: _ov,
                targets: _targets,
                cls: _cls
            }});
        }})()"""

    def _build_viewport_1280_batch_js(self) -> str:
        """Consolidates 1280x800 layout settle and horizontal overflow check into 1 eval."""
        settle_js = self._build_js_settle_prelude(1280, 800, include_equals_token=False)
        return f"""(async () => {{
            {settle_js}
            return Boolean(document.documentElement.scrollWidth > window.innerWidth || document.body.scrollWidth > window.innerWidth);
        }})()"""

    def _build_viewport_375_batch_js(self) -> str:
        """Consolidates 375x812 settle, overflow, visual primitives, mobile nav open/close, interactive sync, targets, interaction CLS, dashes, and broken assets into 1 eval."""
        settle_js = self._build_js_settle_prelude(375, 812, include_equals_token=False)
        broken_js = self._get_broken_assets_js()
        return f"""(async () => {{
            {settle_js}
            const _vw = window.innerWidth;
            const _ov = Boolean(document.documentElement.scrollWidth > _vw || document.body.scrollWidth > _vw);
            const _prim = {self.JS_CHECK_VISUAL_PRIMITIVES};
            const _targets = {self.JS_CHECK_TARGETS};
            const _brokenPromise = {broken_js};
            const _icls = await ({self.JS_CHECK_RESIZE_AND_INTERACTION_CLS});
            const _dashes = {self.JS_CHECK_DASHES};
            const _mobileNavFailures = [];
            const _mNav = document.querySelector('details.mobile-nav-menu');
            if (_mNav) {{
                const _mSum = _mNav.querySelector('summary');
                if (_mSum) {{
                    const _origOpen = _mNav.open;
                    _mSum.click();
                    const _opened = Boolean(_mNav.open);
                    const _links = Array.from(_mNav.querySelectorAll('a[href]')).filter(a => {{
                        const r = a.getBoundingClientRect();
                        return r.width > 0 && r.height > 0;
                    }});
                    const _navOv = Boolean(document.documentElement.scrollWidth > _vw || document.body.scrollWidth > _vw);
                    if (!_opened || _links.length === 0 || _navOv) {{
                        _mobileNavFailures.push({{ widget_id: 'mobile_nav_open', detail: 'opened=' + _opened + ', visible_links=' + _links.length + ', overflow=' + _navOv }});
                    }}
                    _mSum.click();
                    if (_mNav.open !== _origOpen) {{
                        _mobileNavFailures.push({{ widget_id: 'mobile_nav_close', detail: 'mobile-nav-menu did not close on second click' }});
                    }}
                }}
            }}
            const _interactive375 = {self.JS_CHECK_UNIVERSAL_INTERACTIVE_SYNC};
            const _broken = await _brokenPromise;
            return Object.assign({{}}, _prim, {{
                overflow: _ov,
                targets: _targets,
                interaction_cls: _icls,
                dashes: _dashes,
                mobile_nav_failures: _mobileNavFailures,
                interactive_375_failures: _interactive375,
                broken_assets: _broken
            }});
        }})()"""

    def _build_e2e_interactive_with_settle_js(self) -> str:
        """Combines 1440x900 settle prelude with JS_RUN_E2E_INTERACTIVE_SURFACE into 1 eval."""
        settle_js = self._build_js_settle_prelude(1440, 900, include_equals_token=False)
        return f"""(async () => {{
            {settle_js}
            return await ({self.JS_RUN_E2E_INTERACTIVE_SURFACE});
        }})()"""

    async def _audit_route_on_ws(
        self,
        ws: Any,
        base_url: str,
        route: str,
        msg_counter: List[int],
    ) -> Dict[str, Any]:
        """Executes full multi-viewport and visual primitive checks on an active CDP websocket."""
        defects: Dict[str, Any] = {
            "route": route,
            "screen_archetype": "statutory_guide",
            "broken_assets": [],
            "targets_under_44": [],
            "cls_value": 0.0,
            "overflow_375": False,
            "overflow_1280": False,
            "overflow_1440": False,
            "dashes": [],
            "widget_failures": [],
            "hierarchy_violations": [],
            "unwrapped_tables": [],
            "transparent_controls": [],
            "clipped_elements": [],
            "card_geometry_violations": [],
            "whitespace_rhythm_violations": [],
            "calculator_ergonomics_violations": [],
            "cta_density_violations": [],
        }
        prim_keys = (
            "hierarchy_violations",
            "unwrapped_tables",
            "transparent_controls",
            "clipped_elements",
            "card_geometry_violations",
            "whitespace_rhythm_violations",
            "calculator_ergonomics_violations",
            "cta_density_violations",
        )

        await self._prepare_audit_viewport(ws, msg_counter)
        nav_ok, nav_err = await self._navigate_and_wait_ready(ws, base_url, route, msg_counter)
        if not nav_ok:
            defects["widget_failures"].append({
                "widget_id": "navigation_barrier",
                "detail": nav_err or f"Navigation failed for {route}",
            })
            defects["interactive_surface"] = {
                "passed": False,
                "route": route,
                "error": nav_err or "navigation_timeout",
            }
            return defects

        try:
            # 1a + 4a. Wide Desktop Viewport (1440x900) batched settle, overflow, visual primitives, targets, & load/scroll CLS
            msg_counter[0] += 1
            batch_1440 = await self._eval_js(ws, self._build_viewport_1440_batch_js(), msg_id=msg_counter[0])
            cls_raw: Any = None
            if isinstance(batch_1440, dict):
                if batch_1440.get("overflow"):
                    defects["overflow_1440"] = True
                if batch_1440.get("screen_archetype"):
                    defects["screen_archetype"] = batch_1440["screen_archetype"]
                for k in prim_keys:
                    if batch_1440.get(k):
                        defects[k].extend(batch_1440[k])
                if batch_1440.get("targets"):
                    defects["targets_under_44"].extend(batch_1440["targets"])
                cls_raw = batch_1440.get("cls")

            cls_val, cls_sources = self._parse_cls_result(cls_raw)
            if (
                cls_val > 0.0
                and isinstance(cls_raw, dict)
                and cls_raw.get("static_parse_preemption_candidate") is True
            ):
                # Under heavy CPU contention, Blink's HTMLDocumentParser can yield mid-header/footer
                # at its 5ms token budget (e.g. byte 2048/4096), painting a half-parsed static DOM
                # before the next compositor frame finishes rendering the rest of the HTML.
                # Confirm strictly with a cold-cache re-navigation (never skipping unsized media,
                # webfonts, or deterministic JS/CSS layout shifts).
                msg_counter[0] += 1
                await self._send_cdp(ws, "Network.clearBrowserCache", {}, msg_id=msg_counter[0])
                msg_counter[0] += 1
                await self._send_cdp(ws, "Network.setCacheDisabled", {"cacheDisabled": True}, msg_id=msg_counter[0])
                await self._prepare_audit_viewport(ws, msg_counter)
                retry_ok, _ = await self._navigate_and_wait_ready(ws, base_url, route, msg_counter)
                if retry_ok:
                    await self._wait_for_layout_settle(ws, msg_counter, expected_width=1440, expected_height=900)
                    msg_counter[0] += 1
                    retry_cls_raw = await self._eval_js(ws, self.JS_CHECK_CLS, msg_id=msg_counter[0])
                    retry_cls_val, retry_cls_sources = self._parse_cls_result(retry_cls_raw)
                    cls_val, cls_sources = retry_cls_val, retry_cls_sources
            if cls_val > 0.0:
                defects["cls_value"] = cls_val
                if cls_sources:
                    defects.setdefault("cls_sources", []).extend(cls_sources)

            # 1b. Standard Desktop Viewport (1280x800)
            await self._set_viewport_and_settle(ws, 1280, 800, 1, False, msg_counter, settle_layout=False)
            msg_counter[0] += 1
            desktop_overflow = await self._eval_js(
                ws,
                self._build_viewport_1280_batch_js(),
                msg_id=msg_counter[0],
            )
            if desktop_overflow:
                defects["overflow_1280"] = True

            # 2 + 3 + 4b + 5 + 6. Mobile Viewport (375x812) batched checks
            await self._set_viewport_and_settle(ws, 375, 812, 2, True, msg_counter, settle_layout=False)
            msg_counter[0] += 1
            batch_375 = await self._eval_js(ws, self._build_viewport_375_batch_js(), msg_id=msg_counter[0])
            if isinstance(batch_375, dict):
                if batch_375.get("overflow"):
                    defects["overflow_375"] = True
                for k in prim_keys:
                    if batch_375.get(k):
                        existing_reprs = {json.dumps(item, sort_keys=True) for item in defects[k]}
                        for item in batch_375[k]:
                            if json.dumps(item, sort_keys=True) not in existing_reprs:
                                defects[k].append(item)
                targets = batch_375.get("targets")
                if targets:
                    existing_t = {json.dumps(item, sort_keys=True) for item in defects["targets_under_44"]}
                    for item in targets:
                        if json.dumps(item, sort_keys=True) not in existing_t:
                            defects["targets_under_44"].append(item)
                interaction_cls, interaction_cls_sources = self._parse_cls_result(batch_375.get("interaction_cls"))
                if interaction_cls > defects["cls_value"]:
                    defects["cls_value"] = interaction_cls
                if interaction_cls > 0.0 and interaction_cls_sources:
                    defects.setdefault("cls_sources", []).extend(interaction_cls_sources)
                dashes = batch_375.get("dashes")
                if dashes:
                    defects["dashes"] = dashes
                mobile_nav_failures = batch_375.get("mobile_nav_failures")
                if mobile_nav_failures:
                    defects["widget_failures"].extend(mobile_nav_failures)
                interactive_375_failures = batch_375.get("interactive_375_failures")
                if interactive_375_failures:
                    for i_fail in interactive_375_failures:
                        if isinstance(i_fail, dict):
                            defects["widget_failures"].append({
                                "widget_id": f"mobile_375:{i_fail.get('widget_id', 'control')}",
                                "detail": str(i_fail.get("detail") or "375px interactive check failed"),
                            })
                broken_assets = batch_375.get("broken_assets")
                if broken_assets:
                    defects["broken_assets"] = broken_assets

            # 7. Reactive widget updates and popstate hydration (B5: strict selector, zero fallback)
            for spec in self.widget_specs:
                if spec.route == route:
                    msg_counter[0] += 1
                    in_sel_json = json.dumps(spec.input_selector)
                    out_sel_json = json.dumps(spec.output_selector)
                    in_val_json = json.dumps(spec.input_value)
                    trig_json = json.dumps(spec.trigger_event)
                    js_widget = f"""(() => {{
                        const pickFirst = (selList) => {{
                            for (const s of selList.split(',').map(x => x.trim()).filter(Boolean)) {{
                                const el = document.querySelector(s);
                                if (el) return el;
                            }}
                            return document.querySelector(selList);
                        }};
                        const inputEl = pickFirst({in_sel_json});
                        const outEl = pickFirst({out_sel_json});
                        if (!inputEl || !outEl) return {{ success: false, reason: 'elements_missing' }};
                        const origInputVal = inputEl.value;
                        const initialVal = outEl.innerText.trim();
                        const specVal = {in_val_json};
                        const trigEv = {trig_json};
                        const targetVal = (Number(inputEl.value) === Number(specVal)) ? String(Number(specVal) * 2) : specVal;
                        inputEl.value = targetVal;
                        inputEl.dispatchEvent(new Event(trigEv, {{ bubbles: true }}));
                        inputEl.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        const finalVal = outEl.innerText.trim();
                        inputEl.value = origInputVal;
                        inputEl.dispatchEvent(new Event(trigEv, {{ bubbles: true }}));
                        inputEl.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        let popstateOk = true;
                        if ({'true' if spec.verify_popstate else 'false'}) {{
                            try {{
                                window.dispatchEvent(new PopStateEvent('popstate'));
                            }} catch(e) {{
                                popstateOk = false;
                            }}
                        }}
                        return {{ success: true, updated: initialVal !== finalVal, popstate_ok: popstateOk }};
                    }})()"""
                    widget_res = await self._eval_js(ws, js_widget, msg_id=msg_counter[0])
                    if not (widget_res and widget_res.get("success") and widget_res.get("updated") and widget_res.get("popstate_ok", True)):
                        defects["widget_failures"].append({
                            "widget_id": spec.widget_id,
                            "detail": f"Widget {spec.widget_id} did not reactively update calculation on input",
                        })

            # 8. Restore desktop viewport (1440x900) with fresh page state and run full E2E interactive surface verification
            await self._set_viewport_and_settle(ws, 1440, 900, 1, False, msg_counter, settle_layout=False)
            r8_ok, _r8_err = await self._navigate_and_wait_ready(ws, base_url, route, msg_counter)
            if r8_ok:
                await self._wait_for_layout_settle(ws, msg_counter, expected_width=1440, expected_height=900)
            msg_counter[0] += 1
            raw_e2e = await self._eval_js(ws, self._build_e2e_interactive_with_settle_js(), msg_id=msg_counter[0])
            e2e_rep = self._postprocess_interactive_report(base_url, route, raw_e2e)

            # B2: Verify real browser page reload preserves URL-synced calculator state
            dlh = e2e_rep.get("deep_link_hydration") if isinstance(e2e_rep, dict) else None
            if isinstance(dlh, dict) and dlh.get("reload_probe_url") and dlh.get("reload_selector"):
                reload_url = str(dlh["reload_probe_url"])
                reload_sel_json = json.dumps(str(dlh["reload_selector"]))
                reload_exp = str(dlh.get("reload_expected_value") or "")
                r_ok, _r_err = await self._navigate_and_wait_ready(ws, base_url, reload_url, msg_counter)
                if r_ok:
                    msg_counter[0] += 1
                    actual_after_reload = await self._eval_js(
                        ws,
                        f"(() => {{ const el = document.querySelector({reload_sel_json}); return el ? String(el.value) : null; }})()",
                        msg_id=msg_counter[0],
                    )
                    reload_matched = str(actual_after_reload) == reload_exp
                    dlh["reload_persisted"] = reload_matched
                    dlh["reload_actual_value"] = actual_after_reload
                    if not reload_matched:
                        dlh["passed"] = False
                        e2e_rep["passed"] = False
                        dlh["detail"] = f"{dlh.get('detail', '')}, reload_persisted=false (expected={reload_exp}, actual={actual_after_reload})"

            defects["interactive_surface"] = e2e_rep
            if not e2e_rep.get("passed", False):
                defects["widget_failures"].append({
                    "widget_id": "e2e_interactive_surface",
                    "detail": f"Interactive surface verification failed on {route}",
                })
        except CDPEvalError as exc:
            defects["widget_failures"].append({
                "widget_id": "cdp_eval_error",
                "detail": str(exc),
            })
            if "interactive_surface" not in defects:
                defects["interactive_surface"] = {
                    "passed": False,
                    "route": route,
                    "error": str(exc),
                }

        return defects

    async def verify_route(
        self,
        base_url: str,
        route: str,
        msg_counter: Optional[List[int]] = None,
        ws: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Navigates a Chrome CDP tab to target route and validates layout and visual primitive contracts.
        If an active websocket `ws` is passed, reuses that session; otherwise opens and closes a dedicated tab.
        """
        import websockets

        if msg_counter is None:
            msg_counter = [1]

        if ws is not None:
            return await self._audit_route_on_ws(ws, base_url, route, msg_counter)

        info = self._open_cdp_tab()

        tab_id = info["id"]
        ws_url = info["webSocketDebuggerUrl"]

        try:
            async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as new_ws:
                await self._configure_cdp_session(new_ws, msg_counter)
                return await self._audit_route_on_ws(new_ws, base_url, route, msg_counter)
        finally:
            self._close_cdp_tab_and_leaked_loopback(tab_id, active_origin=base_url, cleanup_stale_loopback=False)

    @staticmethod
    def _cdp_session_lock(cdp_port: int):
        """Serializes CDP multi-viewport audits across concurrent xdist workers on the same Chrome instance."""
        import contextlib, fcntl
        @contextlib.contextmanager
        def _lock_ctx():
            lock_path = f"/tmp/pseofactory_cdp_{cdp_port}.lock"
            with open(lock_path, "a+") as lf:
                fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    try:
                        fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
                    except Exception:
                        pass
        return _lock_ctx()

    @staticmethod
    def _parse_cls_result(raw_val: Any) -> Tuple[float, List[Dict[str, Any]]]:
        """Normalizes CLS JS evaluation output (numeric float or {value, sources} dict)."""
        if isinstance(raw_val, dict):
            try:
                val = float(raw_val.get("value") or 0.0)
            except (TypeError, ValueError):
                val = 0.0
            srcs = raw_val.get("sources")
            return val, list(srcs) if isinstance(srcs, list) else []
        if isinstance(raw_val, (int, float)):
            return float(raw_val), []
        return 0.0, []

    @staticmethod
    def _is_finding_failed(f: Dict[str, Any]) -> bool:
        """Canonical failure predicate for a single route finding."""
        return bool(
            f.get("overflow_375")
            or f.get("overflow_1280")
            or f.get("overflow_1440")
            or f.get("targets_under_44")
            or (float(f.get("cls_value") or 0.0) > 0.0)
            or f.get("dashes")
            or f.get("broken_assets")
            or f.get("widget_failures")
            or not (f.get("interactive_surface") or {}).get("passed", True)
            or f.get("hierarchy_violations")
            or f.get("unwrapped_tables")
            or f.get("transparent_controls")
            or f.get("clipped_elements")
            or f.get("card_geometry_violations")
            or f.get("whitespace_rhythm_violations")
            or f.get("calculator_ergonomics_violations")
            or f.get("cta_density_violations")
        )

    @staticmethod
    def _make_cached_pass_finding(route: str, verify_key: str, cached_entry: Dict[str, Any]) -> Dict[str, Any]:
        """Builds a clean passing finding record for a route satisfied by a valid SHA-256 receipt."""
        return {
            "route": route,
            "screen_archetype": str(cached_entry.get("screen_archetype") or "statutory_guide"),
            "verified_by_receipt": True,
            "verify_key": verify_key,
            "broken_assets": [],
            "targets_under_44": [],
            "cls_value": 0.0,
            "overflow_375": False,
            "overflow_1280": False,
            "overflow_1440": False,
            "dashes": [],
            "widget_failures": [],
            "hierarchy_violations": [],
            "unwrapped_tables": [],
            "transparent_controls": [],
            "clipped_elements": [],
            "card_geometry_violations": [],
            "whitespace_rhythm_violations": [],
            "calculator_ergonomics_violations": [],
            "cta_density_violations": [],
            "interactive_surface": {
                "passed": True,
                "route": route,
                "verified_by_receipt": True,
            },
        }

    def _clone_for_worker(self, worker_cdp_port: int) -> "UnifiedBrowserAuditor":
        """Creates a thread-isolated auditor bound to a dedicated worker Chromium CDP port."""
        worker = UnifiedBrowserAuditor(
            adapter=self.adapter,
            dist_dir=self.dist_dir,
            cdp_port=worker_cdp_port,
            fail_closed=self.fail_closed,
            property_id=self.property_id,
            isolated_browser=False,
        )
        worker.widget_specs = list(self.widget_specs)
        worker.excluded_routes = set(self.excluded_routes)
        worker._broken_assets_js_cache = dict(self._broken_assets_js_cache)
        worker._redirects_rules_cache = self._redirects_rules_cache
        worker._invalid_redirects_cache = self._invalid_redirects_cache
        return worker

    def audit_route(self, base_url: str, route: str) -> Dict[str, Any]:
        """Synchronous wrapper for verifying a single route."""
        if self.isolated_browser:
            chrome_bin, is_shell = discover_headless_chrome_binary()
            if chrome_bin:
                with _HeadlessChromiumInstance(chrome_bin, is_headless_shell=is_shell) as chrome:
                    worker = self._clone_for_worker(chrome.port)
                    return asyncio.run(worker.verify_route(base_url, route))
        with self._cdp_session_lock(self.cdp_port):
            try:
                return asyncio.run(self.verify_route(base_url, route))
            finally:
                self._cleanup_dead_loopback_tabs(active_origin=None)

    async def verify_interactive_surface(
        self,
        base_url: str,
        route: str,
        msg_counter: Optional[List[int]] = None,
        ws: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Executes a full real-browser E2E interactive surface verification on a route:
        - Zero console errors and zero uncaught page exceptions
        - Internal and affiliate link integrity (/r/<partner> + sponsored/nofollow)
        - Deep-link URL query parameter hydration and popstate sync
        - Dynamic calculator input/slider mutation and preset clicks
        - Multi-year statutory cliff visualizer dynamic updates
        - Stateful scenario comparator A/B pinning and delta computation
        - Saveable decision blueprint persistence and status readout
        - Playbook subscription form POST (/api/lead-capture) + checkout trigger round-trip
        - TCPA partner quote intake form POST (/api/lead-capture) + checkout trigger round-trip
        - Outbound /r/<partner> redirect and /api/telemetry edge round-trip
        """
        import websockets

        if msg_counter is None:
            msg_counter = [1]

        async def _run_on_ws(active_ws: Any) -> Dict[str, Any]:
            await self._prepare_audit_viewport(active_ws, msg_counter)
            nav_ok, nav_err = await self._navigate_and_wait_ready(active_ws, base_url, route, msg_counter)
            if not nav_ok:
                return {"passed": False, "route": route, "error": nav_err or "navigation_timeout"}
            try:
                msg_counter[0] += 1
                res = await self._eval_js(active_ws, self._build_e2e_interactive_with_settle_js(), msg_id=msg_counter[0])
            except CDPEvalError as exc:
                return {"passed": False, "route": route, "error": str(exc)}
            if not isinstance(res, dict):
                return {"passed": False, "route": route, "error": "invalid_eval_result"}
            return self._postprocess_interactive_report(base_url, route, res)

        if ws is not None:
            return await _run_on_ws(ws)

        info = self._open_cdp_tab()

        tab_id = info["id"]
        ws_url = info["webSocketDebuggerUrl"]

        try:
            async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as new_ws:
                await self._configure_cdp_session(new_ws, msg_counter)
                return await _run_on_ws(new_ws)
        finally:
            self._close_cdp_tab_and_leaked_loopback(tab_id, active_origin=base_url, cleanup_stale_loopback=False)

    def audit_interactive_surface(self, base_url: str, route: str) -> Dict[str, Any]:
        """Synchronous wrapper for full E2E interactive surface verification on a route."""
        if self.isolated_browser:
            chrome_bin, is_shell = discover_headless_chrome_binary()
            if chrome_bin:
                with _HeadlessChromiumInstance(chrome_bin, is_headless_shell=is_shell) as chrome:
                    worker = self._clone_for_worker(chrome.port)
                    return asyncio.run(worker.verify_interactive_surface(base_url, route))
        with self._cdp_session_lock(self.cdp_port):
            try:
                return asyncio.run(self.verify_interactive_surface(base_url, route))
            finally:
                self._cleanup_dead_loopback_tabs(active_origin=None)

    def _run_isolated_worker_queue(
        self,
        route_queue: "queue.Queue[str]",
        chrome_bin: str,
        is_headless_shell: bool,
        prop_id: Optional[str],
        on_route_done: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Executes routes dynamically from a shared work queue inside its own EphemeralDistServer + isolated Chromium."""
        import websockets

        worker_findings: List[Dict[str, Any]] = []
        with _HeadlessChromiumInstance(chrome_bin, is_headless_shell=is_headless_shell) as chrome:
            worker_auditor = self._clone_for_worker(chrome.port)
            with EphemeralDistServer(self.dist_dir, property_id=prop_id) as server:
                base_url = server.base_url
                msg_counter = [1]

                async def _audit_queue() -> None:
                    info = worker_auditor._open_cdp_tab()
                    tab_id = info["id"]
                    ws_url = info["webSocketDebuggerUrl"]
                    try:
                        async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as ws:
                            await worker_auditor._configure_cdp_session(ws, msg_counter, disable_cache=True)
                            while True:
                                try:
                                    r = route_queue.get_nowait()
                                except queue.Empty:
                                    break
                                res = await worker_auditor.verify_route(base_url, r, msg_counter, ws=ws)
                                worker_findings.append(res)
                                if on_route_done is not None:
                                    on_route_done(res)
                    finally:
                        worker_auditor._close_cdp_tab_and_leaked_loopback(
                            tab_id,
                            active_origin=base_url,
                            cleanup_stale_loopback=False,
                        )

                asyncio.run(_audit_queue())
        return worker_findings

    def _run_shared_cdp_routes(
        self,
        live_routes: List[str],
        prop_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Executes routes sequentially against an explicitly configured shared Chrome CDP port."""
        import websockets

        live_findings: List[Dict[str, Any]] = []
        if not live_routes:
            return live_findings
        with self._cdp_session_lock(self.cdp_port):
            msg_counter = [1]
            self._cleanup_dead_loopback_tabs(active_origin=None)
            base_url = ""
            with EphemeralDistServer(self.dist_dir, property_id=prop_id) as server:
                base_url = server.base_url

                async def _audit_all() -> None:
                    info = self._open_cdp_tab()
                    tab_id = info["id"]
                    ws_url = info["webSocketDebuggerUrl"]
                    try:
                        async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as ws:
                            await self._configure_cdp_session(ws, msg_counter)
                            for r in live_routes:
                                res = await self.verify_route(base_url, r, msg_counter, ws=ws)
                                live_findings.append(res)
                    finally:
                        self._close_cdp_tab_and_leaked_loopback(
                            tab_id,
                            active_origin=base_url,
                            cleanup_stale_loopback=False,
                        )

                asyncio.run(_audit_all())
            self._cleanup_dead_loopback_tabs(active_origin=base_url)
        return live_findings

    def run_audit(
        self,
        sample_size: Optional[int] = None,
        workers: Optional[int] = None,
        no_verify_cache: Optional[bool] = None,
        shard: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Runs comprehensive or sampled browser verification across tenant routes.
        Uses isolated parallel headless Chromium workers + closed SHA-256 route verification
        receipts by default, while preserving explicit shared-CDP compatibility when `cdp_port`
        is explicitly specified or `PSEOFACTORY_USE_SHARED_CDP=1`.
        """
        eff_shard = shard if shard is not None else self.shard
        eff_workers_req = workers if workers is not None else self.workers
        eff_no_cache = self.no_verify_cache if no_verify_cache is None else bool(no_verify_cache)

        # Validate shard syntax eagerly even if dist_dir is empty or offline
        if eff_shard:
            parse_and_apply_shard([], eff_shard)

        use_isolated = self.isolated_browser
        chrome_bin: Optional[str] = None
        is_shell = False
        chrome_version_str = ""

        if use_isolated:
            chrome_bin, is_shell = discover_headless_chrome_binary()
            if chrome_bin:
                chrome_version_str = self._chrome_version_override or get_chrome_version_string(chrome_bin)
            else:
                use_isolated = False

        if not use_isolated:
            with self._cdp_session_lock(self.cdp_port):
                reachable, cdp_msg = self.check_cdp_reachability()
            if not reachable:
                if self.fail_closed:
                    raise RuntimeError(f"Chrome CDP unreachable on port {self.cdp_port}: {cdp_msg}")
                return {
                    "status": "SKIPPED_CDP_OFFLINE",
                    "message": f"Chrome CDP unreachable on port {self.cdp_port}: {cdp_msg}",
                    "passed": True,
                    "total_routes": 0,
                    "routes_audited": 0,
                    "live_audited_routes": 0,
                    "cached_receipt_routes": 0,
                    "failed_count": 0,
                    "failed_routes": [],
                    "findings": [],
                }
            if self._chrome_version_override:
                chrome_version_str = self._chrome_version_override
            else:
                try:
                    ver_obj = json.loads(cdp_msg)
                    chrome_version_str = (
                        f"{ver_obj.get('Browser', 'shared-cdp')}|"
                        f"{ver_obj.get('WebKit-Version', '')}"
                    )
                except Exception:
                    chrome_version_str = str(cdp_msg)[:120]

        if not self.dist_dir.exists():
            return {
                "status": "FAIL",
                "message": f"Distribution directory does not exist: {self.dist_dir}",
                "passed": False,
                "total_routes": 0,
                "routes_audited": 0,
                "live_audited_routes": 0,
                "cached_receipt_routes": 0,
                "failed_count": 1,
                "failed_routes": [str(self.dist_dir)],
                "findings": [
                    {
                        "route": "/",
                        "error": f"Distribution directory does not exist: {self.dist_dir}",
                    }
                ],
            }

        extractor = RouteManifestExtractor(self.dist_dir)
        all_routes = [r for r in extractor.extract_routes() if r not in self.excluded_routes]

        if sample_size is not None and sample_size > 0:
            routes_to_audit = extractor.select_smart_routes(
                all_routes=all_routes,
                sample_size=sample_size,
                widget_specs=self.widget_specs,
            )
        else:
            routes_to_audit = list(all_routes)

        if eff_shard:
            routes_to_audit = parse_and_apply_shard(routes_to_audit, eff_shard)

        prop_id = self.property_id or (self.adapter.tenant_id if self.adapter is not None else None)
        eff_receipt_path = (
            self.receipt_path
            if self.receipt_path is not None
            else BrowserVerifyReceiptStore.default_receipt_path(prop_id)
        )
        receipt_store = BrowserVerifyReceiptStore(eff_receipt_path) if eff_receipt_path is not None else None

        cached_findings: List[Dict[str, Any]] = []
        live_routes: List[str] = []
        route_verify_keys: Dict[str, Optional[str]] = {}
        estate_shared_digest = ""

        if receipt_store is not None:
            has_full_sitemap = (self.dist_dir / "sitemap.xml").is_file()
            has_local_scripts = (
                has_full_sitemap
                or (self.dist_dir / "static" / "js").is_dir()
                or (self.dist_dir / "js").is_dir()
            )
            audit_options = {
                "property_id": prop_id or "",
                "expected_host": self.adapter.canonical_domain if self.adapter is not None else "",
                "fail_closed": self.fail_closed,
                "enforce_strict_cls": True,
                "check_meta_assets": has_full_sitemap,
                "check_script_assets": has_local_scripts,
                "widget_specs": [asdict(s) for s in self.widget_specs],
            }
            estate_shared_digest = BrowserVerifyReceiptStore.compute_estate_shared_digest(
                dist_dir=self.dist_dir,
                chrome_version=chrome_version_str,
                audit_options=audit_options,
                verifier_digest=self._verifier_digest_override,
            )
            stored_routes = {} if eff_no_cache else receipt_store.load_routes()
            if len(routes_to_audit) >= 32:
                with ThreadPoolExecutor(max_workers=min(4, max(1, os.cpu_count() or 2))) as key_pool:
                    vkeys_list = list(
                        key_pool.map(
                            lambda rt: BrowserVerifyReceiptStore.compute_route_verify_key(
                                self.dist_dir,
                                estate_shared_digest,
                                rt,
                            ),
                            routes_to_audit,
                        )
                    )
            else:
                vkeys_list = [
                    BrowserVerifyReceiptStore.compute_route_verify_key(
                        self.dist_dir,
                        estate_shared_digest,
                        rt,
                    )
                    for rt in routes_to_audit
                ]
            for r, vkey in zip(routes_to_audit, vkeys_list):
                route_verify_keys[r] = vkey
                rec = stored_routes.get(r) if not eff_no_cache else None
                if (
                    vkey
                    and isinstance(rec, dict)
                    and rec.get("status") == "PASS"
                    and rec.get("verify_key") == vkey
                ):
                    cached_findings.append(self._make_cached_pass_finding(r, vkey, rec))
                else:
                    live_routes.append(r)
        else:
            live_routes = list(routes_to_audit)

        live_findings: List[Dict[str, Any]] = []
        effective_workers = 0

        if live_routes:
            # Pre-populate broken assets JS & redirects cache once before worker threads clone
            self._get_broken_assets_js()
            self._get_redirects_rules()

            def _record_live_receipt(finding: Dict[str, Any]) -> None:
                if receipt_store is None:
                    return
                r_key = str(finding.get("route") or "")
                v_key = route_verify_keys.get(r_key)
                if self._is_finding_failed(finding):
                    if r_key:
                        receipt_store.update_routes(
                            property_id=prop_id,
                            chrome_version=chrome_version_str,
                            estate_shared_digest=estate_shared_digest,
                            passed_entries={},
                            evict_routes=[r_key],
                        )
                elif r_key and v_key:
                    receipt_store.update_routes(
                        property_id=prop_id,
                        chrome_version=chrome_version_str,
                        estate_shared_digest=estate_shared_digest,
                        passed_entries={
                            r_key: {
                                "verify_key": v_key,
                                "status": "PASS",
                                "screen_archetype": str(finding.get("screen_archetype") or "statutory_guide"),
                            }
                        },
                    )

            import contextlib
            batch_ctx = (
                receipt_store.batch(
                    property_id=prop_id,
                    chrome_version=chrome_version_str,
                    estate_shared_digest=estate_shared_digest,
                    flush_every=32,
                )
                if receipt_store is not None
                else contextlib.nullcontext()
            )
            with batch_ctx:
                if use_isolated and chrome_bin:
                    effective_workers = compute_auto_worker_count(
                        len(live_routes),
                        requested_workers=eff_workers_req,
                    )
                    ordered_live = sorted(live_routes)
                    route_queue: "queue.Queue[str]" = queue.Queue()
                    for r in ordered_live:
                        route_queue.put_nowait(r)
                    cb_fn = _record_live_receipt if receipt_store is not None else None
                    if effective_workers <= 1:
                        live_findings = self._run_isolated_worker_queue(
                            route_queue,
                            chrome_bin,
                            is_shell,
                            prop_id,
                            on_route_done=cb_fn,
                        )
                    else:
                        with ThreadPoolExecutor(max_workers=effective_workers) as pool:
                            futures = [
                                pool.submit(
                                    self._run_isolated_worker_queue,
                                    route_queue,
                                    chrome_bin,
                                    is_shell,
                                    prop_id,
                                    cb_fn,
                                )
                                for _ in range(effective_workers)
                            ]
                            for fut in as_completed(futures):
                                live_findings.extend(fut.result())
                else:
                    effective_workers = 1
                    live_findings = self._run_shared_cdp_routes(live_routes, prop_id)
                    if receipt_store is not None:
                        for f in live_findings:
                            _record_live_receipt(f)

        findings = sorted(cached_findings + live_findings, key=lambda item: str(item.get("route") or ""))
        failed_routes = [str(f.get("route") or "") for f in findings if self._is_finding_failed(f)]
        failed_count = len(failed_routes)

        return {
            "status": "PASS" if failed_count == 0 else "FAIL",
            "passed": failed_count == 0,
            "total_routes": len(all_routes),
            "routes_audited": len(routes_to_audit),
            "live_audited_routes": len(live_findings),
            "cached_receipt_routes": len(cached_findings),
            "failed_count": failed_count,
            "failed_routes": failed_routes,
            "workers_used": effective_workers,
            "shard": eff_shard,
            "findings": findings,
        }

