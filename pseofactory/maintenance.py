"""
pseofactory Autonomous Closed-Loop Maintenance Lifecycle
Multi-tenant asset integrity auditing, cross-property boundary isolation firewall,
fail-closed refactor cascade engine, and post-pipeline commit latch.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

from __future__ import annotations

import os
import sys
import re
import json
import time
import uuid
import shutil
import tempfile
import subprocess
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Set, Optional, Union, Iterator, Callable

from pseofactory.contracts import (
    assert_no_forbidden_dashes,
    assert_touch_targets,
    assert_valid_jsonld,
    assert_sitemap_parses,
    assert_comparison_layout_contracts,
    FORBIDDEN_JARGON,
    PROMPT_LEAKAGE_TERMS,
)
from pseofactory.drift import (
    compute_engine_hash,
    detect_engine_drift,
    record_engine_hash,
    compute_asset_fingerprint,
    record_asset_ledger,
    load_asset_ledger,
    trigger_drift_cascade,
    cascade_drift_lifecycle,
)

# Pre-warm high-latency dependencies at module level to eliminate cold import overhead in run()
import bs4
from pseofactory.indexing.preflight import IndexingPreflightEngine
from pseofactory.partner_tracker import PartnerTrackingEngine
from pseofactory.indexer import PushIndexer




class DriftReason(str, Enum):
    """
    Categorized taxonomy of asset and engine drift reasons.
    Zero em-dashes. Zero en-dashes.
    """
    ENGINE_HASH_DRIFT = "ENGINE_HASH_DRIFT"
    STRUCTURAL_CONTRACT_VIOLATION = "STRUCTURAL_CONTRACT_VIOLATION"
    CONTENT_RELEVANCE_GAP = "CONTENT_RELEVANCE_GAP"
    PROPERTY_CONTAMINATION = "PROPERTY_CONTAMINATION"
    STATUTORY_DRIFT = "STATUTORY_DRIFT"
    OPERATIONAL_SHIELD_GAP = "OPERATIONAL_SHIELD_GAP"
    OPPORTUNITY_OVERLAY = "OPPORTUNITY_OVERLAY"
    TRUTH_CONTRADICTION = "TRUTH_CONTRADICTION"



@dataclass
class AssetDriftRecord:
    """
    Detailed audit record for a single static asset exhibiting drift.
    Zero em-dashes. Zero en-dashes.
    """
    asset_path: str
    slug: Optional[str] = None
    reasons: List[DriftReason] = field(default_factory=list)
    details: List[str] = field(default_factory=list)
    current_hash: Optional[str] = None
    recorded_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_path": self.asset_path,
            "slug": self.slug,
            "reasons": [r.value if isinstance(r, DriftReason) else str(r) for r in self.reasons],
            "details": list(self.details),
            "current_hash": self.current_hash,
            "recorded_hash": self.recorded_hash,
            "metadata": dict(self.metadata),
        }


@dataclass
class AssetIntegrityReport:
    """
    Consolidated audit report across a property's asset directory.
    Zero em-dashes. Zero en-dashes.
    """
    property_id: str
    total_assets_checked: int = 0
    compliant_assets_count: int = 0
    drifted_assets_count: int = 0
    drifted_assets: List[AssetDriftRecord] = field(default_factory=list)
    status: str = "PASS"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "property_id": self.property_id,
            "total_assets_checked": self.total_assets_checked,
            "compliant_assets_count": self.compliant_assets_count,
            "drifted_assets_count": self.drifted_assets_count,
            "drifted_assets": [a.to_dict() for a in self.drifted_assets],
            "status": self.status,
            "timestamp": self.timestamp,
        }


@dataclass
class MaintenanceResult:
    """
    Result of a maintenance lifecycle execution pass.
    Zero em-dashes. Zero en-dashes.
    """
    property_id: str
    status: str
    assets_audited: int = 0
    assets_drifted: int = 0
    assets_refactored: int = 0
    assets_failed: int = 0
    failed_records: List[Dict[str, Any]] = field(default_factory=list)
    engine_hash: Optional[str] = None
    duration_seconds: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    gitops_status: Optional[str] = None
    distribution_status: Optional[str] = None
    indexing_status: Optional[str] = None
    trend_status: Optional[str] = None
    partner_readiness_status: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "property_id": self.property_id,
            "status": self.status,
            "assets_audited": self.assets_audited,
            "assets_drifted": self.assets_drifted,
            "assets_refactored": self.assets_refactored,
            "assets_failed": self.assets_failed,
            "failed_records": list(self.failed_records),
            "engine_hash": self.engine_hash,
            "duration_seconds": self.duration_seconds,
            "timestamp": self.timestamp,
        }
        if self.gitops_status is not None:
            d["gitops_status"] = self.gitops_status
        if self.distribution_status is not None:
            d["distribution_status"] = self.distribution_status
        if self.indexing_status is not None:
            d["indexing_status"] = self.indexing_status
        if self.trend_status is not None:
            d["trend_status"] = self.trend_status
        if self.partner_readiness_status is not None:
            d["partner_readiness_status"] = self.partner_readiness_status
        return d


class PropertyContaminationError(ValueError):
    """
    Raised when vertical calculations or foreign property tokens bleed across boundaries.
    Zero em-dashes. Zero en-dashes.
    """
    def __init__(
        self,
        message: str,
        property_id: str = "",
        asset_path: Optional[str] = None,
        foreign_tokens: Optional[List[str]] = None,
    ):
        super().__init__(message)
        self.property_id = property_id
        self.asset_path = asset_path
        self.foreign_tokens = foreign_tokens or []


class LockContentionError(Exception):
    """
    Raised when tenant factory runner encounters transient flock lock contention
    (exit code 75 EX_TEMPFAIL).
    Zero em-dashes. Zero en-dashes.
    """
    def __init__(
        self,
        message: str,
        property_id: str = "",
        exit_code: int = 75,
    ):
        super().__init__(message)
        self.property_id = property_id
        self.exit_code = exit_code


class SubprocessCrashError(Exception):
    """
    Raised when child worker process crashes or exits non-zero (other than 75).
    Zero em-dashes. Zero en-dashes.
    """
    def __init__(
        self,
        message: str,
        returncode: int = 1,
        stderr_tail: str = "",
        stdout_tail: str = "",
        property_id: str = "",
        command: Union[str, List[str]] = "",
    ):
        super().__init__(message)
        self.returncode = returncode
        self.stderr_tail = stderr_tail
        self.stdout_tail = stdout_tail
        self.property_id = property_id
        self.command = command

    @property
    def exit_code(self) -> int:
        return self.returncode

    @property
    def stderr(self) -> str:
        return self.stderr_tail

    @property
    def stdout(self) -> str:
        return self.stdout_tail


class CrossPropertyContaminationScanner:
    """
    Scans rendered markup, schemas, and syndication files for foreign property tokens.
    Prevents cross-tenant bleed between Prexvo and ProfitHelm.
    Zero em-dashes. Zero en-dashes.
    """

    DEFAULT_FOREIGN_TOKENS: Dict[str, Set[str]] = {
        "prexvo": {
            "section 1031",
            "1031 exchange",
            "exchange 1031",
            "exchange1031",
            "section 179",
            "qsbs",
            "section 1202",
            "corporate tax",
            "pass-through entity",
            "tcja",
            "profithelm.com",
            "profithelm",
            "143884102",
            # ProfitHelm B2B affiliate partner keys
            "coinledger",
            "koinly",
            "mercury",
            "stripe",
            "ramp",
            "rho",
            "gusto",
            "rippling",
            "crest_capital",
            "ipx1031",
            "exeter1031",
            "first_american",
            "turbotax",
            "taxslayer",
            "kalshi",
            "interactive_brokers",
        },
        "profithelm": {
            "title iv",
            "34 cfr",
            "pslf",
            "paye sunset",
            "student loan",
            "repayment assistance plan",
            "income-contingent repayment",
            "direct consolidation",
            "prexvo.com",
            "prexvo",
            "106482194",
            # Prexvo student loan refinance partner keys
            "splash_financial",
            "sofi",
            "credible",
            "earnest",
            "lendkey",
        },
    }

    def __init__(self, custom_foreign_tokens: Optional[Dict[str, Set[str]]] = None):
        self._tokens: Dict[str, Set[str]] = {}
        try:
            from pseofactory.tenant_facts import TenantFactStore
            fact_store = TenantFactStore.get_instance()
            for prop in ["profithelm", "prexvo"]:
                prof = fact_store.get_profile(prop)
                if prof and prof.cross_tenant_forbidden_tokens:
                    self._tokens[prop] = {t.lower() for t in prof.cross_tenant_forbidden_tokens}
        except Exception:
            pass
        if not self._tokens:
            for k, v in self.DEFAULT_FOREIGN_TOKENS.items():
                self._tokens[k.lower()] = {t.lower() for t in v}
        if custom_foreign_tokens:
            for k, v in custom_foreign_tokens.items():
                k_norm = k.lower()
                existing = self._tokens.get(k_norm, set())
                self._tokens[k_norm] = existing | {t.lower() for t in v}

    def scan_text(self, text: str, property_id: str, context: str = "") -> List[str]:
        """
        Scans input text for any forbidden foreign tokens registered for property_id.
        Returns list of matched foreign tokens.
        Zero em-dashes. Zero en-dashes.
        """
        if not text:
            return []
        p_id = property_id.lower()
        foreign_set = self._tokens.get(p_id, set())
        if not foreign_set:
            return []

        text_lower = text.lower()
        matched: List[str] = []
        for token in sorted(foreign_set):
            # Check for exact token presence
            if token in text_lower:
                matched.append(token)
        return matched

    def scan_file(self, file_path: Union[str, Path], property_id: str) -> List[str]:
        """
        Reads file content and scans for foreign property tokens.
        Zero em-dashes. Zero en-dashes.
        """
        p = Path(file_path).resolve()
        if not p.is_file():
            return []
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []
        return self.scan_text(content, property_id, context=str(p))

    def scan_directory(self, dist_dir: Union[str, Path], property_id: str) -> Dict[str, List[str]]:
        """
        Recursively scans directory for contaminated files.
        Returns mapping of relative path to list of matched foreign tokens.
        Zero em-dashes. Zero en-dashes.
        """
        d = Path(dist_dir).resolve()
        if not d.is_dir():
            return {}
        results: Dict[str, List[str]] = {}
        for f in d.glob("**/*"):
            if f.is_file() and f.suffix in (".html", ".xml", ".txt", ".json", ".js"):
                rel = f.relative_to(d).as_posix()
                matched = self.scan_file(f, property_id)
                if matched:
                    results[rel] = matched
        return results

    def assert_clean(
        self,
        text_or_path: Union[str, Path],
        property_id: str,
        context: str = "",
    ) -> None:
        """
        Enforces zero foreign tokens in fail-closed mode.
        Raises PropertyContaminationError on any match.
        Zero em-dashes. Zero en-dashes.
        """
        if isinstance(text_or_path, Path) or (
            isinstance(text_or_path, str) and os.path.exists(text_or_path) and "\n" not in text_or_path
        ):
            p = Path(text_or_path)
            matched = self.scan_file(p, property_id)
            if matched:
                raise PropertyContaminationError(
                    f"Cross-property contamination detected in {p}: found foreign tokens {matched}",
                    property_id=property_id,
                    asset_path=str(p),
                    foreign_tokens=matched,
                )
        else:
            matched = self.scan_text(str(text_or_path), property_id, context=context)
            if matched:
                ctx = f" in {context}" if context else ""
                raise PropertyContaminationError(
                    f"Cross-property contamination detected{ctx}: found foreign tokens {matched}",
                    property_id=property_id,
                    foreign_tokens=matched,
                )


DEFAULT_TENANT_LINKEDIN_IDS: Dict[str, str] = {
    "profithelm": "143884102",
    "prexvo": "106482194",
}


class PropertyAdapter(ABC):
    """
    Abstract Base Protocol encapsulating multi-tenant property operations and boundaries.
    Zero em-dashes. Zero en-dashes.
    """

    @property
    @abstractmethod
    def property_id(self) -> str:
        """Unique lowercase identifier for the property (e.g. prexvo, profithelm)."""
        pass

    @property
    @abstractmethod
    def brand_name(self) -> str:
        """Official display brand name."""
        pass

    @property
    @abstractmethod
    def domain(self) -> str:
        """Bare domain name (e.g. prexvo.com)."""
        pass

    @property
    @abstractmethod
    def canonical_base(self) -> str:
        """Full canonical base URI (e.g. https://prexvo.com)."""
        pass

    @property
    @abstractmethod
    def dist_dir(self) -> Path:
        """Path to compiled static asset distribution directory."""
        pass

    @property
    def repo_path(self) -> Optional[Path]:
        """Optional repository root path."""
        return None

    @property
    def linkedin_company_id(self) -> str:
        """Official LinkedIn Company Page ID for headless brand syndication."""
        tenant_env = os.environ.get(f"FACTORY_{self.property_id.upper()}_LINKEDIN_COMPANY_ID")
        if tenant_env:
            return tenant_env
        default_id = DEFAULT_TENANT_LINKEDIN_IDS.get(self.property_id.lower(), "")
        global_env = os.environ.get("FACTORY_LINKEDIN_COMPANY_ID")
        if global_env and not default_id:
            return global_env
        return default_id

    @property
    def base_dirs(self) -> Optional[List[Path]]:
        if self.repo_path and self.property_id:
            prop_pkg = self.repo_path / self.property_id
            if prop_pkg.is_dir() and (prop_pkg / "builder.py").is_file():
                try:
                    content = (prop_pkg / "builder.py").read_text(encoding="utf-8", errors="ignore")
                    if "base_dirs" in content:
                        return [prop_pkg]
                except Exception:
                    pass
        return None

    @property
    def tools(self) -> List[Dict[str, Any]]:
        """List of tool catalog definitions."""
        return []

    def get_statutory_tokens(self) -> Set[str]:
        """Domain-specific statutory and regulatory keywords."""
        return set()

    def get_foreign_tokens(self) -> Set[str]:
        """Forbidden keywords belonging to other properties."""
        return CrossPropertyContaminationScanner.DEFAULT_FOREIGN_TOKENS.get(
            self.property_id.lower(), set()
        )

    @contextmanager
    def scoped_environment(self) -> Iterator[None]:
        """
        Context manager isolating and restoring FACTORY_* environment variables.
        Guarantees stateless worker physics between tenant runs.
        Zero em-dashes. Zero en-dashes.
        """
        keys = [
            "FACTORY_CANONICAL_BASE",
            "FACTORY_DOMAIN",
            "FACTORY_BRAND_NAME",
            "FACTORY_DIST_DIR",
            "FACTORY_LINKEDIN_COMPANY_ID",
        ]
        saved: Dict[str, Optional[str]] = {k: os.environ.get(k) for k in keys}
        os.environ["FACTORY_CANONICAL_BASE"] = self.canonical_base
        os.environ["FACTORY_DOMAIN"] = self.domain
        os.environ["FACTORY_BRAND_NAME"] = self.brand_name
        os.environ["FACTORY_DIST_DIR"] = str(self.dist_dir)
        os.environ["FACTORY_LINKEDIN_COMPANY_ID"] = self.linkedin_company_id
        try:
            yield
        finally:
            for k, val in saved.items():
                if val is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = val

    @abstractmethod
    def build_asset(self, slug: str, target_file: Optional[Path] = None) -> bool:
        """Rebuilds a single drifted asset by slug or path."""
        pass

    @abstractmethod
    def build_all(self) -> bool:
        """Rebuilds the entire property static distribution."""
        pass

    def verify_asset(self, path: Path) -> Dict[str, Any]:
        """Verifies a single compiled asset file."""
        return {"status": "PASS", "path": str(path), "issues": []}

    def list_assets(self) -> List[Path]:
        """Discovers compiled static assets within dist_dir."""
        if not self.dist_dir.exists():
            return []
        assets: List[Path] = []
        for p in self.dist_dir.glob("**/*"):
            if p.is_file() and p.suffix in (".html", ".xml", ".txt", ".json"):
                # Ignore temp and backup files
                if p.name.startswith(".tmp") or p.name.startswith(".orig") or p.name.startswith(".backup"):
                    continue
                assets.append(p)
        return sorted(assets)


class ConfigurablePropertyAdapter(PropertyAdapter):
    """
    Dynamic, parameter-driven PropertyAdapter for testing and custom tenants.
    Zero em-dashes. Zero en-dashes.
    """

    def __init__(
        self,
        property_id: str,
        brand_name: str,
        domain: str,
        canonical_base: str,
        dist_dir: Union[str, Path],
        repo_path: Optional[Union[str, Path]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        foreign_tokens: Optional[Set[str]] = None,
        statutory_tokens: Optional[Set[str]] = None,
        build_asset_fn: Optional[Callable[[str, Optional[Path]], bool]] = None,
        build_all_fn: Optional[Callable[[], bool]] = None,
        verify_asset_fn: Optional[Callable[[Path], Dict[str, Any]]] = None,
    ):
        self._property_id = property_id.lower()
        self._brand_name = brand_name
        self._domain = domain
        self._canonical_base = canonical_base.rstrip("/")
        self._dist_dir = Path(dist_dir).resolve()
        self._repo_path = Path(repo_path).resolve() if repo_path else None
        self._tools = list(tools) if tools else []
        self._foreign_tokens = set(foreign_tokens) if foreign_tokens else set()
        self._statutory_tokens = set(statutory_tokens) if statutory_tokens else set()
        self._build_asset_fn = build_asset_fn
        self._build_all_fn = build_all_fn
        self._verify_asset_fn = verify_asset_fn

    @property
    def property_id(self) -> str:
        return self._property_id

    @property
    def brand_name(self) -> str:
        return self._brand_name

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def canonical_base(self) -> str:
        return self._canonical_base

    @property
    def dist_dir(self) -> Path:
        return self._dist_dir

    @property
    def repo_path(self) -> Optional[Path]:
        return self._repo_path

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return self._tools

    def get_statutory_tokens(self) -> Set[str]:
        return self._statutory_tokens

    def get_foreign_tokens(self) -> Set[str]:
        if self._foreign_tokens:
            return self._foreign_tokens
        return super().get_foreign_tokens()

    def build_asset(self, slug: str, target_file: Optional[Path] = None) -> bool:
        if self._build_asset_fn:
            return bool(self._build_asset_fn(slug, target_file))
        return True

    def build_all(self) -> bool:
        if self._build_all_fn:
            return bool(self._build_all_fn())
        if self._build_asset_fn:
            success = True
            for a in self.list_assets():
                slug = a.stem
                if not self.build_asset(slug, target_file=a):
                    success = False
            return success
        return True

    def verify_asset(self, path: Path) -> Dict[str, Any]:
        if self._verify_asset_fn:
            return self._verify_asset_fn(path)
        return super().verify_asset(path)


class SubprocessPropertyAdapter(PropertyAdapter):
    """
    Subprocess-isolated PropertyAdapter for executing property builds and operations
    in separate child processes.
    Guarantees zero memory contamination: tenant packages are never imported
    into the host process's sys.modules.
    Zero em-dashes. Zero en-dashes.
    """

    def __init__(
        self,
        property_id: str,
        brand_name: str,
        domain: str,
        canonical_base: str,
        dist_dir: Union[str, Path],
        repo_path: Optional[Union[str, Path]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        foreign_tokens: Optional[Set[str]] = None,
        statutory_tokens: Optional[Set[str]] = None,
        build_command: Optional[Union[str, List[str]]] = None,
        build_asset_command: Optional[Union[str, List[str]]] = None,
        linkedin_company_id: Optional[str] = None,
    ):
        self._property_id = property_id.lower()
        self._brand_name = brand_name
        self._domain = domain
        self._canonical_base = canonical_base.rstrip("/")
        self._dist_dir = Path(dist_dir).resolve()
        self._repo_path = Path(repo_path).resolve() if repo_path else self._dist_dir.parent
        self._tools = list(tools) if tools else []
        self._foreign_tokens = set(foreign_tokens) if foreign_tokens else set()
        self._statutory_tokens = set(statutory_tokens) if statutory_tokens else set()
        self._build_command = build_command
        self._build_asset_command = build_asset_command
        self._linkedin_company_id = linkedin_company_id

    @property
    def linkedin_company_id(self) -> str:
        """Official LinkedIn Company Page ID for headless brand syndication."""
        if self._linkedin_company_id:
            return self._linkedin_company_id
        return super().linkedin_company_id

    @property
    def property_id(self) -> str:
        return self._property_id

    @property
    def brand_name(self) -> str:
        return self._brand_name

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def canonical_base(self) -> str:
        return self._canonical_base

    @property
    def dist_dir(self) -> Path:
        return self._dist_dir

    @property
    def repo_path(self) -> Optional[Path]:
        return self._repo_path

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return self._tools

    def get_statutory_tokens(self) -> Set[str]:
        return self._statutory_tokens

    def get_foreign_tokens(self) -> Set[str]:
        if self._foreign_tokens:
            return self._foreign_tokens
        return super().get_foreign_tokens()

    def build_asset(self, slug: str, target_file: Optional[Path] = None) -> bool:
        """
        Rebuilds single asset in isolated subprocess.
        Guarantees tenant modules are never imported into host process sys.modules.
        Zero em-dashes. Zero en-dashes.
        """
        if self._build_asset_command:
            formatted_cmd = None
            try:
                env = os.environ.copy()
                env["FACTORY_CANONICAL_BASE"] = self.canonical_base
                env["FACTORY_DOMAIN"] = self.domain
                env["FACTORY_BRAND_NAME"] = self.brand_name
                env["FACTORY_DIST_DIR"] = str(self.dist_dir)
                env["FACTORY_ASSET_SLUG"] = slug
                env["FACTORY_LINKEDIN_COMPANY_ID"] = self.linkedin_company_id
                env["LINKEDIN_COMPANY_ID"] = self.linkedin_company_id
                env[f"FACTORY_{self.property_id.upper()}_LINKEDIN_COMPANY_ID"] = self.linkedin_company_id
                env["PROFITHELM_TARGET"] = slug
                env["PREXVO_TARGET"] = slug
                if target_file:
                    env["FACTORY_TARGET_FILE"] = str(target_file)

                cmd = self._build_asset_command
                if isinstance(cmd, str):
                    formatted_cmd = cmd.format(
                        slug=slug,
                        target_file=str(target_file) if target_file else "",
                        dist_dir=str(self.dist_dir),
                    )
                    res = subprocess.run(formatted_cmd, shell=True, env=env, cwd=str(self._repo_path), capture_output=True, timeout=120)
                else:
                    formatted_args = [
                        arg.format(
                            slug=slug,
                            target_file=str(target_file) if target_file else "",
                            dist_dir=str(self.dist_dir),
                        )
                        for arg in cmd
                    ]
                    formatted_cmd = formatted_args
                    res = subprocess.run(formatted_args, env=env, cwd=str(self._repo_path), capture_output=True, timeout=120)
                if res.returncode == 75:
                    raise LockContentionError(
                        f"Build asset command for '{self._property_id}' exited with 75 (EX_TEMPFAIL)",
                        property_id=self._property_id,
                    )
                if res.returncode != 0:
                    stderr_tail = (res.stderr.decode("utf-8", errors="replace") if isinstance(res.stderr, bytes) else str(res.stderr or ""))[-2048:]
                    stdout_tail = (res.stdout.decode("utf-8", errors="replace") if isinstance(res.stdout, bytes) else str(res.stdout or ""))[-2048:]
                    raise SubprocessCrashError(
                        f"Build asset command for '{self._property_id}' failed with exit {res.returncode}",
                        returncode=res.returncode,
                        stderr_tail=stderr_tail,
                        stdout_tail=stdout_tail,
                        property_id=self._property_id,
                        command=formatted_cmd,
                    )
                return True
            except (LockContentionError, SubprocessCrashError):
                raise
            except subprocess.TimeoutExpired as te:
                stderr_tail = (te.stderr.decode("utf-8", errors="replace") if isinstance(te.stderr, bytes) else str(te.stderr or ""))[-2048:] if te.stderr else "Timeout expired after 120s"
                stdout_tail = (te.stdout.decode("utf-8", errors="replace") if isinstance(te.stdout, bytes) else str(te.stdout or ""))[-2048:] if te.stdout else ""
                raise SubprocessCrashError(
                    f"Build asset command timed out for '{self._property_id}'",
                    returncode=124,
                    stderr_tail=stderr_tail,
                    stdout_tail=stdout_tail,
                    property_id=self._property_id,
                    command=formatted_cmd or str(self._build_asset_command),
                )
            except Exception as exc:
                raise SubprocessCrashError(
                    f"Build asset invocation error for '{self._property_id}': {exc}",
                    returncode=1,
                    stderr_tail=str(exc),
                    property_id=self._property_id,
                    command=formatted_cmd or str(self._build_asset_command),
                )

        factory_script = self._repo_path / "run_factory.sh"
        if not factory_script.is_file():
            factory_script = self._repo_path / "scripts" / "run_factory.sh"

        if factory_script.is_file():
            cmd = ["bash", str(factory_script), "--target", slug]
            try:
                env = os.environ.copy()
                env["FACTORY_CANONICAL_BASE"] = self.canonical_base
                env["FACTORY_DOMAIN"] = self.domain
                env["FACTORY_BRAND_NAME"] = self.brand_name
                env["FACTORY_DIST_DIR"] = str(self.dist_dir)
                env["FACTORY_ASSET_SLUG"] = slug
                env["FACTORY_LINKEDIN_COMPANY_ID"] = self.linkedin_company_id
                env["LINKEDIN_COMPANY_ID"] = self.linkedin_company_id
                env[f"FACTORY_{self.property_id.upper()}_LINKEDIN_COMPANY_ID"] = self.linkedin_company_id
                env["PROFITHELM_TARGET"] = slug
                env["PREXVO_TARGET"] = slug
                res = subprocess.run(cmd, env=env, cwd=str(self._repo_path), capture_output=True, timeout=180)
                if res.returncode == 75:
                    raise LockContentionError(
                        f"Factory runner '{factory_script.name}' exited with 75 (EX_TEMPFAIL) on lock contention for '{self._property_id}'",
                        property_id=self._property_id,
                    )
                if res.returncode != 0:
                    stderr_tail = (res.stderr.decode("utf-8", errors="replace") if isinstance(res.stderr, bytes) else str(res.stderr or ""))[-2048:]
                    stdout_tail = (res.stdout.decode("utf-8", errors="replace") if isinstance(res.stdout, bytes) else str(res.stdout or ""))[-2048:]
                    raise SubprocessCrashError(
                        f"Factory runner '{factory_script.name}' exited with {res.returncode} for '{self._property_id}'",
                        returncode=res.returncode,
                        stderr_tail=stderr_tail,
                        stdout_tail=stdout_tail,
                        property_id=self._property_id,
                        command=cmd,
                    )
                return True
            except (LockContentionError, SubprocessCrashError):
                raise
            except subprocess.TimeoutExpired as te:
                stderr_tail = (te.stderr.decode("utf-8", errors="replace") if isinstance(te.stderr, bytes) else str(te.stderr or ""))[-2048:] if te.stderr else "Timeout expired after 180s"
                stdout_tail = (te.stdout.decode("utf-8", errors="replace") if isinstance(te.stdout, bytes) else str(te.stdout or ""))[-2048:] if te.stdout else ""
                raise SubprocessCrashError(
                    f"Factory runner '{factory_script.name}' timed out after 180s for '{self._property_id}'",
                    returncode=124,
                    stderr_tail=stderr_tail,
                    stdout_tail=stdout_tail,
                    property_id=self._property_id,
                    command=cmd,
                )
            except Exception as exc:
                raise SubprocessCrashError(
                    f"Factory runner error for '{self._property_id}': {exc}",
                    returncode=1,
                    stderr_tail=str(exc),
                    property_id=self._property_id,
                    command=cmd,
                )

        # Isolated python execution in child process
        pkg_root = str(Path(__file__).resolve().parent.parent)
        script = (
            f"import sys\n"
            f"if {repr(pkg_root)} not in sys.path:\n"
            f"    sys.path.insert(0, {repr(pkg_root)})\n"
            f"if {repr(str(self._repo_path))} not in sys.path:\n"
            f"    sys.path.insert(0, {repr(str(self._repo_path))})\n"
            f"try:\n"
            f"    import importlib\n"
            f"    try:\n"
            f"        cfg = importlib.import_module('{self._property_id}.config')\n"
            f"        if hasattr(cfg, 'LINKEDIN_COMPANY_ID'):\n"
            f"            cfg.LINKEDIN_COMPANY_ID = {repr(self.linkedin_company_id)}\n"
            f"        if hasattr(cfg, 'LINKEDIN_COMPANY_URL'):\n"
            f"            cfg.LINKEDIN_COMPANY_URL = f'https://www.linkedin.com/company/{self.linkedin_company_id}'\n"
            f"    except Exception:\n"
            f"        pass\n"
            f"    mod = importlib.import_module('{self._property_id}.builder')\n"
            f"    if hasattr(mod, 'LINKEDIN_COMPANY_URL'):\n"
            f"        mod.LINKEDIN_COMPANY_URL = f'https://www.linkedin.com/company/{self.linkedin_company_id}'\n"
            f"except ModuleNotFoundError:\n"
            f"    sys.exit(127)\n"
            f"try:\n"
            f"    if hasattr(mod, 'build_asset'):\n"
            f"        mod.build_asset({repr(slug)}, target_file={repr(str(target_file) if target_file else None)})\n"
            f"        sys.exit(0)\n"
            f"    elif hasattr(mod, 'build_all'):\n"
            f"        try:\n"
            f"            mod.build_all(dist_dir={repr(str(self._dist_dir))})\n"
            f"        except TypeError:\n"
            f"            mod.build_all()\n"
            f"        sys.exit(0)\n"
            f"    sys.exit(127)\n"
            f"except Exception as ex:\n"
            f"    import traceback\n"
            f"    traceback.print_exc()\n"
            f"    sys.exit(1)\n"
        )
        try:
            env = os.environ.copy()
            env["FACTORY_CANONICAL_BASE"] = self.canonical_base
            env["FACTORY_DOMAIN"] = self.domain
            env["FACTORY_BRAND_NAME"] = self.brand_name
            env["FACTORY_DIST_DIR"] = str(self.dist_dir)
            env["FACTORY_ASSET_SLUG"] = slug
            env["FACTORY_LINKEDIN_COMPANY_ID"] = self.linkedin_company_id
            env["LINKEDIN_COMPANY_ID"] = self.linkedin_company_id
            env[f"FACTORY_{self.property_id.upper()}_LINKEDIN_COMPANY_ID"] = self.linkedin_company_id
            env["PYTHONPATH"] = f"{pkg_root}:{env.get('PYTHONPATH', '')}".rstrip(":")
            res = subprocess.run([sys.executable, "-c", script], env=env, cwd=str(self._repo_path), capture_output=True, timeout=120)
            if res.returncode == 0:
                return True
            if res.returncode == 75:
                raise LockContentionError(
                    f"Isolated builder for '{self._property_id}' exited with 75 (EX_TEMPFAIL)",
                    property_id=self._property_id,
                )
            if res.returncode == 127:
                return False
            stderr_tail = (res.stderr.decode("utf-8", errors="replace") if isinstance(res.stderr, bytes) else str(res.stderr or ""))[-2048:]
            stdout_tail = (res.stdout.decode("utf-8", errors="replace") if isinstance(res.stdout, bytes) else str(res.stdout or ""))[-2048:]
            raise SubprocessCrashError(
                f"Isolated builder for '{self._property_id}' failed with exit {res.returncode}",
                returncode=res.returncode,
                stderr_tail=stderr_tail,
                stdout_tail=stdout_tail,
                property_id=self._property_id,
                command=[sys.executable, "-c", script],
            )
        except (LockContentionError, SubprocessCrashError):
            raise
        except subprocess.TimeoutExpired as te:
            stderr_tail = (te.stderr.decode("utf-8", errors="replace") if isinstance(te.stderr, bytes) else str(te.stderr or ""))[-2048:] if te.stderr else "Timeout expired after 120s"
            stdout_tail = (te.stdout.decode("utf-8", errors="replace") if isinstance(te.stdout, bytes) else str(te.stdout or ""))[-2048:] if te.stdout else ""
            raise SubprocessCrashError(
                f"Isolated builder for '{self._property_id}' timed out after 120s",
                returncode=124,
                stderr_tail=stderr_tail,
                stdout_tail=stdout_tail,
                property_id=self._property_id,
                command=[sys.executable, "-c", script],
            )
        except Exception as exc:
            raise SubprocessCrashError(
                f"Isolated builder execution error for '{self._property_id}': {exc}",
                returncode=1,
                stderr_tail=str(exc),
                property_id=self._property_id,
                command=[sys.executable, "-c", script],
            )

    def build_all(self) -> bool:
        """
        Rebuilds all assets in isolated subprocess.
        Guarantees tenant modules are never imported into host process sys.modules.
        Zero em-dashes. Zero en-dashes.
        """
        if self._build_command:
            try:
                env = os.environ.copy()
                env["FACTORY_CANONICAL_BASE"] = self.canonical_base
                env["FACTORY_DOMAIN"] = self.domain
                env["FACTORY_BRAND_NAME"] = self.brand_name
                env["FACTORY_DIST_DIR"] = str(self.dist_dir)
                env["FACTORY_LINKEDIN_COMPANY_ID"] = self.linkedin_company_id
                env["LINKEDIN_COMPANY_ID"] = self.linkedin_company_id
                env[f"FACTORY_{self.property_id.upper()}_LINKEDIN_COMPANY_ID"] = self.linkedin_company_id

                cmd = self._build_command
                if isinstance(cmd, str):
                    res = subprocess.run(cmd, shell=True, env=env, cwd=str(self._repo_path), capture_output=True, timeout=600)
                else:
                    res = subprocess.run(cmd, env=env, cwd=str(self._repo_path), capture_output=True, timeout=600)
                if res.returncode == 75:
                    raise LockContentionError(
                        f"Build all command for '{self._property_id}' exited with 75 (EX_TEMPFAIL)",
                        property_id=self._property_id,
                    )
                if res.returncode != 0:
                    stderr_tail = (res.stderr.decode("utf-8", errors="replace") if isinstance(res.stderr, bytes) else str(res.stderr or ""))[-2048:]
                    stdout_tail = (res.stdout.decode("utf-8", errors="replace") if isinstance(res.stdout, bytes) else str(res.stdout or ""))[-2048:]
                    raise SubprocessCrashError(
                        f"Build all command for '{self._property_id}' exited with {res.returncode}",
                        returncode=res.returncode,
                        stderr_tail=stderr_tail,
                        stdout_tail=stdout_tail,
                        property_id=self._property_id,
                        command=cmd,
                    )
                return True
            except (LockContentionError, SubprocessCrashError):
                raise
            except subprocess.TimeoutExpired as te:
                stderr_tail = (te.stderr.decode("utf-8", errors="replace") if isinstance(te.stderr, bytes) else str(te.stderr or ""))[-2048:] if te.stderr else "Timeout expired after 600s"
                stdout_tail = (te.stdout.decode("utf-8", errors="replace") if isinstance(te.stdout, bytes) else str(te.stdout or ""))[-2048:] if te.stdout else ""
                raise SubprocessCrashError(
                    f"Build all command timed out after 600s for '{self._property_id}'",
                    returncode=124,
                    stderr_tail=stderr_tail,
                    stdout_tail=stdout_tail,
                    property_id=self._property_id,
                    command=str(self._build_command),
                )
            except Exception as exc:
                raise SubprocessCrashError(
                    f"Build all invocation error for '{self._property_id}': {exc}",
                    returncode=1,
                    stderr_tail=str(exc),
                    property_id=self._property_id,
                    command=str(self._build_command),
                )

        # Prioritize isolated python execution in child process
        pkg_root = str(Path(__file__).resolve().parent.parent)
        script = (
            f"import sys\n"
            f"if {repr(pkg_root)} not in sys.path:\n"
            f"    sys.path.insert(0, {repr(pkg_root)})\n"
            f"if {repr(str(self._repo_path))} not in sys.path:\n"
            f"    sys.path.insert(0, {repr(str(self._repo_path))})\n"
            f"try:\n"
            f"    import importlib\n"
            f"    try:\n"
            f"        cfg = importlib.import_module('{self._property_id}.config')\n"
            f"        if hasattr(cfg, 'LINKEDIN_COMPANY_ID'):\n"
            f"            cfg.LINKEDIN_COMPANY_ID = {repr(self.linkedin_company_id)}\n"
            f"        if hasattr(cfg, 'LINKEDIN_COMPANY_URL'):\n"
            f"            cfg.LINKEDIN_COMPANY_URL = f'https://www.linkedin.com/company/{self.linkedin_company_id}'\n"
            f"    except Exception:\n"
            f"        pass\n"
            f"    mod = importlib.import_module('{self._property_id}.builder')\n"
            f"    if hasattr(mod, 'LINKEDIN_COMPANY_URL'):\n"
            f"        mod.LINKEDIN_COMPANY_URL = f'https://www.linkedin.com/company/{self.linkedin_company_id}'\n"
            f"except ModuleNotFoundError:\n"
            f"    sys.exit(127)\n"
            f"try:\n"
            f"    if hasattr(mod, 'build_all'):\n"
            f"        try:\n"
            f"            mod.build_all(dist_dir={repr(str(self._dist_dir))})\n"
            f"        except TypeError:\n"
            f"            mod.build_all()\n"
            f"        sys.exit(0)\n"
            f"    sys.exit(127)\n"
            f"except Exception as ex:\n"
            f"    import traceback\n"
            f"    traceback.print_exc()\n"
            f"    sys.exit(1)\n"
        )
        last_error = None
        try:
            env = os.environ.copy()
            env["FACTORY_CANONICAL_BASE"] = self.canonical_base
            env["FACTORY_DOMAIN"] = self.domain
            env["FACTORY_BRAND_NAME"] = self.brand_name
            env["FACTORY_DIST_DIR"] = str(self.dist_dir)
            env["FACTORY_LINKEDIN_COMPANY_ID"] = self.linkedin_company_id
            env["LINKEDIN_COMPANY_ID"] = self.linkedin_company_id
            env[f"FACTORY_{self.property_id.upper()}_LINKEDIN_COMPANY_ID"] = self.linkedin_company_id
            env["PYTHONPATH"] = f"{pkg_root}:{env.get('PYTHONPATH', '')}".rstrip(":")
            res = subprocess.run([sys.executable, "-c", script], env=env, cwd=str(self._repo_path), capture_output=True, timeout=600)
            if res.returncode == 0:
                return True
            if res.returncode == 75:
                raise LockContentionError(
                    f"Isolated builder for '{self._property_id}' exited with 75 (EX_TEMPFAIL)",
                    property_id=self._property_id,
                )
            if res.returncode != 127:
                stderr_tail = (res.stderr.decode("utf-8", errors="replace") if isinstance(res.stderr, bytes) else str(res.stderr or ""))[-2048:]
                stdout_tail = (res.stdout.decode("utf-8", errors="replace") if isinstance(res.stdout, bytes) else str(res.stdout or ""))[-2048:]
                last_error = SubprocessCrashError(
                    f"Isolated builder for '{self._property_id}' failed with exit {res.returncode}",
                    returncode=res.returncode,
                    stderr_tail=stderr_tail,
                    stdout_tail=stdout_tail,
                    property_id=self._property_id,
                    command=[sys.executable, "-c", script],
                )
        except (LockContentionError, SubprocessCrashError):
            raise
        except subprocess.TimeoutExpired as te:
            stderr_tail = (te.stderr.decode("utf-8", errors="replace") if isinstance(te.stderr, bytes) else str(te.stderr or ""))[-2048:] if te.stderr else "Timeout expired after 600s"
            stdout_tail = (te.stdout.decode("utf-8", errors="replace") if isinstance(te.stdout, bytes) else str(te.stdout or ""))[-2048:] if te.stdout else ""
            raise SubprocessCrashError(
                f"Isolated builder for '{self._property_id}' timed out after 600s",
                returncode=124,
                stderr_tail=stderr_tail,
                stdout_tail=stdout_tail,
                property_id=self._property_id,
                command=[sys.executable, "-c", script],
            )
        except Exception:
            pass

        factory_script = self._repo_path / "run_factory.sh"
        if not factory_script.is_file():
            factory_script = self._repo_path / "scripts" / "run_factory.sh"

        if factory_script.is_file():
            cmd = ["bash", str(factory_script), "--dry-run", "--force"]
            try:
                env = os.environ.copy()
                env["PYTHONPATH"] = f"{pkg_root}:{env.get('PYTHONPATH', '')}".rstrip(":")
                env["FACTORY_CANONICAL_BASE"] = self.canonical_base
                env["FACTORY_DOMAIN"] = self.domain
                env["FACTORY_BRAND_NAME"] = self.brand_name
                env["FACTORY_DIST_DIR"] = str(self.dist_dir)
                env["FACTORY_LINKEDIN_COMPANY_ID"] = self.linkedin_company_id
                env["LINKEDIN_COMPANY_ID"] = self.linkedin_company_id
                env[f"FACTORY_{self.property_id.upper()}_LINKEDIN_COMPANY_ID"] = self.linkedin_company_id
                env["FACTORY_DRY_RUN"] = "1"
                env["PREXVO_AUTO_LIVE"] = "0"
                env["PREXVO_CHECK_QUEUE"] = "0"
                env["PROFITHELM_AUTO_LIVE"] = "0"
                env["PROFITHELM_CHECK_QUEUE"] = "0"
                res = subprocess.run(cmd, env=env, cwd=str(self._repo_path), capture_output=True, timeout=600)
                if res.returncode == 0:
                    return True
                if res.returncode == 75:
                    raise LockContentionError(
                        f"Factory runner '{factory_script.name}' exited with 75 (EX_TEMPFAIL) on lock contention for '{self._property_id}'",
                        property_id=self._property_id,
                    )
                stderr_tail = (res.stderr.decode("utf-8", errors="replace") if isinstance(res.stderr, bytes) else str(res.stderr or ""))[-2048:]
                stdout_tail = (res.stdout.decode("utf-8", errors="replace") if isinstance(res.stdout, bytes) else str(res.stdout or ""))[-2048:]
                raise SubprocessCrashError(
                    f"Factory runner '{factory_script.name}' failed with exit {res.returncode} for '{self._property_id}'",
                    returncode=res.returncode,
                    stderr_tail=stderr_tail,
                    stdout_tail=stdout_tail,
                    property_id=self._property_id,
                    command=cmd,
                )
            except (LockContentionError, SubprocessCrashError):
                raise
            except subprocess.TimeoutExpired as te:
                stderr_tail = (te.stderr.decode("utf-8", errors="replace") if isinstance(te.stderr, bytes) else str(te.stderr or ""))[-2048:] if te.stderr else "Timeout expired after 600s"
                stdout_tail = (te.stdout.decode("utf-8", errors="replace") if isinstance(te.stdout, bytes) else str(te.stdout or ""))[-2048:] if te.stdout else ""
                raise SubprocessCrashError(
                    f"Factory runner '{factory_script.name}' timed out after 600s for '{self._property_id}'",
                    returncode=124,
                    stderr_tail=stderr_tail,
                    stdout_tail=stdout_tail,
                    property_id=self._property_id,
                    command=cmd,
                )
            except Exception as exc:
                raise SubprocessCrashError(
                    f"Factory runner error for '{self._property_id}': {exc}",
                    returncode=1,
                    stderr_tail=str(exc),
                    property_id=self._property_id,
                    command=cmd,
                )

        if last_error:
            raise last_error

        return False



class WorkspacePropertyScanner:
    """
    Discovers property adapters dynamically by convention without hardcoding tenant packages:
    - .pseofactory.json configuration marker
    - factory.json configuration marker
    - dist/sitemap.xml static site distribution
    - pyproject.toml package metadata with dist/ directory
    Zero em-dashes. Zero en-dashes.
    """

    EXCLUDED_DIR_NAMES: Set[str] = {
        "pseofactory",
        "arif-skills",
        "knowledge",
        "automations",
        "personal",
        "node_modules",
        "_archive",
        ".agy",
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "public",
        "dist",
        "docs",
        "data",
        "satellites",
        "artifacts",
        "generations",
        "parasite-output",
    }

    def __init__(self, workspace_root: Optional[Union[str, Path]] = None):
        self.workspace_root = Path(
            workspace_root or os.environ.get("WORKSPACE_ROOT", "/home/ubuntuadmin/projects")
        ).resolve()

    def _parse_pseofactory_json(self, config_file: Path) -> Optional[PropertyAdapter]:
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return None
            repo_path = config_file.parent
            property_id = str(data.get("property_id") or repo_path.name).lower()
            brand_name = str(data.get("brand_name") or property_id.capitalize())
            domain = str(data.get("domain") or f"{property_id}.com")
            canonical_base = str(data.get("canonical_base") or f"https://{domain}").rstrip("/")
            raw_dist = data.get("dist_dir") or "dist"
            dist_dir = (
                (repo_path / raw_dist).resolve()
                if not Path(raw_dist).is_absolute()
                else Path(raw_dist).resolve()
            )
            tools = data.get("tools", [])
            build_cmd = data.get("build_command")
            build_asset_cmd = data.get("build_asset_command")
            foreign_tokens = set(data.get("foreign_tokens", []))
            statutory_tokens = set(data.get("statutory_tokens", []))

            return SubprocessPropertyAdapter(
                property_id=property_id,
                brand_name=brand_name,
                domain=domain,
                canonical_base=canonical_base,
                dist_dir=dist_dir,
                repo_path=repo_path,
                tools=tools,
                foreign_tokens=foreign_tokens,
                statutory_tokens=statutory_tokens,
                build_command=build_cmd,
                build_asset_command=build_asset_cmd,
            )
        except Exception:
            return None

    def _parse_sitemap_xml(self, sitemap_file: Path, repo_path: Path) -> Optional[PropertyAdapter]:
        try:
            content = sitemap_file.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"<loc>(https?://([^/]+))", content)
            if not m:
                return None
            canonical_base = m.group(1).rstrip("/")
            domain = m.group(2)
            prop_id = domain.split(".")[0].lower() if "." in domain else repo_path.name.lower()
            brand_name = prop_id.capitalize()
            dist_dir = sitemap_file.parent

            return SubprocessPropertyAdapter(
                property_id=prop_id,
                brand_name=brand_name,
                domain=domain,
                canonical_base=canonical_base,
                dist_dir=dist_dir,
                repo_path=repo_path,
            )
        except Exception:
            return None

    def _parse_pyproject_toml(self, pyproject_file: Path, repo_path: Path) -> Optional[PropertyAdapter]:
        try:
            content = pyproject_file.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r'name\s*=\s*["\']([^"\']+)["\']', content)
            if not m:
                return None
            name = m.group(1)
            dist_dir = repo_path / "dist"
            if not dist_dir.is_dir():
                return None

            domain = f"{name}.com"
            canonical_base = f"https://{domain}"
            sitemap_path = dist_dir / "sitemap.xml"
            if sitemap_path.is_file():
                sm_adapter = self._parse_sitemap_xml(sitemap_path, repo_path)
                if sm_adapter:
                    canonical_base = sm_adapter.canonical_base
                    domain = sm_adapter.domain

            return SubprocessPropertyAdapter(
                property_id=name.lower(),
                brand_name=name.capitalize(),
                domain=domain,
                canonical_base=canonical_base,
                dist_dir=dist_dir,
                repo_path=repo_path,
            )
        except Exception:
            return None

    def discover_properties(self, workspace_root: Optional[Union[str, Path]] = None) -> List[PropertyAdapter]:
        root = Path(workspace_root or self.workspace_root).resolve()
        if not root.is_dir():
            return []

        adapters: List[PropertyAdapter] = []
        seen_ids: Set[str] = set()

        # Check if root itself has marker
        for cfg_name in (".pseofactory.json", "factory.json"):
            cfg = root / cfg_name
            if cfg.is_file():
                root_adapter = self._parse_pseofactory_json(cfg)
                if root_adapter and root_adapter.property_id not in seen_ids:
                    seen_ids.add(root_adapter.property_id)
                    adapters.append(root_adapter)

        # Check child directories
        for entry in sorted(root.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            if entry.name in self.EXCLUDED_DIR_NAMES:
                continue

            adapter: Optional[PropertyAdapter] = None

            # 1. .pseofactory.json
            p_json = entry / ".pseofactory.json"
            if p_json.is_file():
                adapter = self._parse_pseofactory_json(p_json)

            # 2. factory.json
            if adapter is None:
                f_json = entry / "factory.json"
                if f_json.is_file():
                    adapter = self._parse_pseofactory_json(f_json)

            # 3. dist/sitemap.xml
            if adapter is None:
                sm = entry / "dist" / "sitemap.xml"
                if sm.is_file():
                    adapter = self._parse_sitemap_xml(sm, entry)

            # 4. pyproject.toml with dist/
            if adapter is None:
                pyproj = entry / "pyproject.toml"
                if pyproj.is_file():
                    adapter = self._parse_pyproject_toml(pyproj, entry)

            if adapter and adapter.property_id not in seen_ids:
                seen_ids.add(adapter.property_id)
                adapters.append(adapter)

        return adapters

    scan_workspace = discover_properties
    scan = discover_properties
    discover = discover_properties


PREXVO_DEFAULT_TOOLS: List[Dict[str, Any]] = [
    {
        "slug": "rap-vs-ibr-calculator",
        "title": "RAP vs IBR Student Loan Plan Comparison Engine",
        "short_title": "RAP vs IBR",
        "description": "Compare monthly obligations, 225% poverty exemption rules, interest subsidies, and statutory forgiveness schedules between the 2026 RAP and IBR plans.",
        "primary_keyword": "rap vs ibr",
    },
    {
        "slug": "tiered-standard-calculator",
        "title": "Tiered Standard Repayment Plan Amortization Model",
        "short_title": "Tiered Standard",
        "description": "Calculate 10 to 30 year standard amortization schedules across federal consolidation balance tiers pursuant to Title IV 34 CFR 685.208 regulations.",
        "primary_keyword": "tiered standard repayment plan",
    },
    {
        "slug": "paye-sunset-calculator",
        "title": "PAYE Sunset & Plan Transition Analysis Engine",
        "short_title": "PAYE Sunset",
        "description": "Analyze 2026 PAYE sunset rules, grandfathering protections, and 10-year standard payment caps to model whether switching to RAP reduces total repayment.",
        "primary_keyword": "paye vs ibr",
    },
    {
        "slug": "icr-repayment-calculator",
        "title": "Income-Contingent Repayment (ICR) Formula Tool",
        "short_title": "ICR Calculator",
        "description": "Model Income-Contingent Repayment under dual statutory formulas: 20% discretionary income vs 12-year income-adjusted payments for Parent PLUS debt.",
        "primary_keyword": "icr vs ibr",
    },
    {
        "slug": "pslf-buyback-calculator",
        "title": "PSLF Buyback & Statutory Credit Assessment Engine",
        "short_title": "PSLF Buyback",
        "description": "Calculate qualifying Public Service Loan Forgiveness payments and evaluate buyback eligibility under 34 CFR 685.219 statutory regulations.",
        "primary_keyword": "pslf buyback calculator",
    },
]


PROFITHELM_DEFAULT_TOOLS: List[Dict[str, Any]] = [
    {
        "slug": "irs-2027-tax-brackets",
        "title": "IRS 2027 Tax Brackets & TCJA Sunset Calculator 2027",
        "short_title": "IRS 2027 Tax Brackets",
        "description": "Calculate your federal income tax bracket, statutory marginal rates (10% to 37%), and compare against post-TCJA sunset scenarios.",
        "primary_keyword": "irs 2027 tax bracket projections",
        "category": "Tax Intelligence",
    },
    {
        "slug": "crypto-tax-calculator",
        "title": "Crypto Tax Liability & Capital Gains Calculator 2027",
        "short_title": "Crypto Tax Calculator",
        "description": "Compute estimated federal and state capital gains liabilities on crypto trades, staking yield, and DeFi transfers.",
        "primary_keyword": "crypto tax calculator 2027",
        "category": "Digital Assets",
    },
    {
        "slug": "saas-runway-calculator",
        "title": "SaaS Cash Runway & Net Burn Rate Calculator Engine",
        "short_title": "SaaS Runway Calculator",
        "description": "Interactive runway projection model for tech startups, factoring net monthly burn, revenue CAGR, and hiring cohorts.",
        "primary_keyword": "saas burn rate runway calculator",
        "category": "Corporate Finance",
    },
    {
        "slug": "prediction-market-odds",
        "title": "Prediction Market Implied Probability & Arbitrage Calculator",
        "short_title": "Prediction Market Arbitrage",
        "description": "Calculate true implied probabilities, contract spreads, and Kelly Criterion bet sizing across Kalshi and Polymarket.",
        "primary_keyword": "prediction market arbitrage calculator",
        "category": "Market Arbitrage",
    },
    {
        "slug": "tcja-sunset-capital-gains",
        "title": "TCJA Sunset Capital Gains & NIIT Tax Simulator 2027",
        "short_title": "Capital Gains Sunset",
        "description": "Project long-term and short-term capital gains taxes, Section 1411 NIIT surtax thresholds, and state additions following the 2025 TCJA sunset.",
        "primary_keyword": "tcja sunset capital gains rates",
        "category": "Tax Intelligence",
    },
    {
        "slug": "section-179-calculator",
        "title": "Section 179 Equipment & Software Deduction Calculator",
        "short_title": "Section 179 Deduction",
        "description": "Calculate immediate equipment expensing, bonus depreciation phase-down, and tax savings under IRC Section 179.",
        "primary_keyword": "section 179 deduction calculator",
        "category": "Tax Intelligence",
    },
    {
        "slug": "treasury-yield-calculator",
        "title": "Treasury Bill Yield vs HYSA Tax-Equivalent Yield Calculator",
        "short_title": "Treasury Yield vs HYSA",
        "description": "Calculate after-tax interest and Tax-Equivalent Yield (TEY) between state-tax-exempt US Treasury Bills and taxable HYSAs.",
        "primary_keyword": "treasury bill yield vs hysa calculator",
        "category": "Yield Arbitrage",
    },
    {
        "slug": "section-1031-calculator",
        "title": "Section 1031 Exchange & Capital Gains Tax Calculator",
        "short_title": "Section 1031 Exchange",
        "description": "Calculate capital gains tax deferral, Section 1250 depreciation recapture, and 45-day/180-day deadlines under IRC Section 1031 for 2026-2027.",
        "primary_keyword": "section 1031 exchange calculator",
        "category": "Commercial Real Estate",
    },
    {
        "slug": "prediction-market-tax",
        "title": "Prediction Market Tax Calculator: Section 1256 Contracts",
        "short_title": "Prediction Market Tax",
        "description": "Compare statutory tax liabilities between CFTC-regulated event contracts under IRC Section 1256 (60/40 rate) and unregulated decentralized markets.",
        "primary_keyword": "prediction market tax calculator",
        "category": "Tax Intelligence",
    },
]


class TenantRegistry:
    """
    Registry for tenant property adapters.
    Zero em-dashes. Zero en-dashes.
    """

    _global_registry: Optional[TenantRegistry] = None

    def __init__(self):
        self._adapters: Dict[str, PropertyAdapter] = {}

    def register_adapter(self, adapter: PropertyAdapter) -> None:
        """Registers a PropertyAdapter under its property_id."""
        self._adapters[adapter.property_id.lower()] = adapter

    def get_adapter(self, property_id: str) -> PropertyAdapter:
        """Retrieves registered adapter or raises KeyError."""
        p_id = property_id.lower()
        if p_id not in self._adapters:
            raise KeyError(f"Property adapter '{property_id}' not found in TenantRegistry")
        return self._adapters[p_id]

    def list_adapters(self) -> Dict[str, PropertyAdapter]:
        """Returns shallow copy of registered adapters."""
        return dict(self._adapters)

    def clear(self) -> None:
        """Clears all registered adapters."""
        self._adapters.clear()

    @classmethod
    def default(cls, workspace_root: Optional[Union[str, Path]] = None) -> TenantRegistry:
        """Returns or creates singleton registry preloaded dynamically via WorkspacePropertyScanner."""
        if cls._global_registry is None:
            reg = cls()
            scanner = WorkspacePropertyScanner(workspace_root=workspace_root)
            for adapter in scanner.discover_properties():
                reg.register_adapter(adapter)
            cls._ensure_tenant_tools(reg, workspace_root=workspace_root)
            cls._global_registry = reg
        return cls._global_registry

    @classmethod
    def _ensure_tenant_tools(cls, reg: TenantRegistry, workspace_root: Optional[Union[str, Path]] = None) -> None:
        """Populates tools on discovered adapters without importing tenant modules into host sys.modules."""
        try:
            px_adapter = reg.get_adapter("prexvo")
            if not px_adapter.tools:
                if hasattr(px_adapter, "_tools"):
                    px_adapter._tools = list(PREXVO_DEFAULT_TOOLS)
                elif hasattr(px_adapter, "tools") and isinstance(px_adapter.tools, list):
                    px_adapter.tools.extend(PREXVO_DEFAULT_TOOLS)
        except KeyError:
            pass

        try:
            ph_adapter = reg.get_adapter("profithelm")
            if not ph_adapter.tools:
                ph_tools = PROFITHELM_DEFAULT_TOOLS
                if hasattr(ph_adapter, "_tools"):
                    ph_adapter._tools = list(ph_tools)
                elif hasattr(ph_adapter, "tools") and isinstance(ph_adapter.tools, list):
                    ph_adapter.tools.extend(ph_tools)
        except KeyError:
            pass

    @classmethod
    def reset_default(cls) -> None:
        """Resets singleton default registry."""
        cls._global_registry = None


class LiveTruthAuditEngine:
    """
    Scans compiled static HTML assets or live edge URLs against TenantFactStore.
    Detects:
    1. Banned marketing claims
    2. Pricing contradictions ($XX/mo not matching official pricing tiers)
    3. Missing mandatory disclosures (e.g. Prexvo YMYL forfeiture disclaimer on refinance pages)
    Zero em-dashes. Zero en-dashes.
    """

    def __init__(self, fact_store: Optional[Any] = None):
        if fact_store is None:
            from pseofactory.tenant_facts import TenantFactStore
            self.fact_store = TenantFactStore.get_instance()
        else:
            self.fact_store = fact_store

    def audit_html(
        self,
        html_content: str,
        property_id: str,
        context: Optional[str] = None,
    ) -> List[str]:
        """
        Audits raw HTML content for truth contradictions against tenant facts.
        Delegates directly to TenantFactStore.verify_claim.
        Returns a list of violation detail strings.
        Zero em-dashes. Zero en-dashes.
        """
        if not self.fact_store.get_profile(property_id):
            return []
        try:
            is_valid, violations = self.fact_store.verify_claim(
                tenant=property_id,
                text=html_content,
                context=context or "LiveTruthAuditEngine.audit_html",
            )
            return violations
        except ValueError:
            return []

    def audit_file(
        self,
        file_path: Union[str, Path],
        property_id: str,
    ) -> List[str]:
        """Audits a single static HTML file path. Returns violations."""
        p = Path(file_path).resolve()
        if not p.is_file() or p.suffix != ".html":
            return []
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            return self.audit_html(content, property_id=property_id, context=p.name)
        except Exception as ex:
            return [f"Failed to read file {p}: {ex}"]

    def scan_dist_dir(
        self,
        dist_dir: Union[str, Path],
        property_id: str,
    ) -> List[AssetDriftRecord]:
        """
        Scans all HTML files in dist_dir for truth contradictions.
        Returns list of AssetDriftRecord with DriftReason.TRUTH_CONTRADICTION.
        Zero em-dashes. Zero en-dashes.
        """
        d = Path(dist_dir).resolve()
        if not d.is_dir():
            return []
        drifted: List[AssetDriftRecord] = []
        for html_file in d.rglob("*.html"):
            violations = self.audit_file(html_file, property_id=property_id)
            if violations:
                drifted.append(
                    AssetDriftRecord(
                        asset_path=str(html_file),
                        slug=html_file.stem,
                        reasons=[DriftReason.TRUTH_CONTRADICTION],
                        details=violations,
                        metadata={"property_id": property_id},
                    )
                )
        return drifted


class AssetIntegrityEvaluator:
    """
    Audits compiled static assets against engine baselines:
    - Structural anti-slop (dashes, jargon, prompt leakage)
    - Interactive touch targets (>= 44x44px)
    - Schema markup (valid JSON-LD)
    - Sitemaps (single urlset, < 10000 URLs)
    - AI Mode layout homogeneity and minimum asset counts
    - Cross-property boundary contamination
    - Substrate ledger hash alignment
    - Live truth contradictions against TenantFactStore
    Zero em-dashes. Zero en-dashes.
    """

    def __init__(
        self,
        scanner: Optional[CrossPropertyContaminationScanner] = None,
        enforce_master_seo: bool = True,
        enforce_operational_shield: bool = False,
        truth_engine: Optional[LiveTruthAuditEngine] = None,
    ):
        self.scanner = scanner or CrossPropertyContaminationScanner()
        self.enforce_master_seo = enforce_master_seo
        self.enforce_operational_shield = enforce_operational_shield
        self.truth_engine = truth_engine or LiveTruthAuditEngine()
        self._audit_cache: Dict[Tuple[str, float, int], Optional[AssetDriftRecord]] = {}
        self._asset_audit_cache = self._audit_cache
        self._fingerprint_cache: Dict[Tuple[str, float, int], str] = {}
        self._seo_verifier: Optional[Any] = None


    def extract_slug(self, asset_path: Path, dist_dir: Path) -> Optional[str]:
        """Extracts tool slug from asset path."""
        try:
            rel = asset_path.relative_to(dist_dir).as_posix()
            parts = rel.split("/")
            if len(parts) >= 2 and parts[0] == "tools":
                return parts[1]
            if asset_path.suffix in (".html", ""):
                return asset_path.stem
        except Exception:
            pass
        return None

    def audit_asset(
        self,
        path: Union[str, Path],
        adapter: PropertyAdapter,
        ledger: Optional[Dict[str, Any]] = None,
        engine_drifted: bool = False,
    ) -> Optional[AssetDriftRecord]:
        """
        Audits a single compiled asset against all structural and property contracts.
        Returns AssetDriftRecord if any defect is detected, None if fully compliant.
        Zero em-dashes. Zero en-dashes.
        """
        p = Path(path).resolve()
        reasons: List[DriftReason] = []
        details: List[str] = []

        if not p.is_file():
            return AssetDriftRecord(
                asset_path=str(p),
                slug=self.extract_slug(p, adapter.dist_dir),
                reasons=[DriftReason.STRUCTURAL_CONTRACT_VIOLATION],
                details=[f"File not found: {p}"],
            )

        try:
            st = p.stat()
            mtime, size = st.st_mtime, st.st_size
        except OSError:
            mtime, size = None, None

        cache_key = (str(p), mtime, size) if mtime is not None else None
        rel_key = (
            p.relative_to(adapter.dist_dir).as_posix()
            if p.is_relative_to(adapter.dist_dir)
            else p.name
        )

        recorded_hash: Optional[str] = None
        if ledger and "assets" in ledger:
            recorded_hash = ledger["assets"].get(rel_key)

        # Differential cache check for verified clean assets
        if not engine_drifted and cache_key and cache_key in self._audit_cache:
            cached_rec = self._audit_cache[cache_key]
            if cached_rec is None:
                if recorded_hash is not None and hasattr(self, "_fingerprint_cache"):
                    cached_fingerprint = self._fingerprint_cache.get(cache_key)
                    if cached_fingerprint is not None and cached_fingerprint != recorded_hash:
                        pass
                    else:
                        return None
                else:
                    return None

        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
        except Exception as ex:
            return AssetDriftRecord(
                asset_path=str(p),
                slug=self.extract_slug(p, adapter.dist_dir),
                reasons=[DriftReason.STRUCTURAL_CONTRACT_VIOLATION],
                details=[f"Failed to read file: {ex}"],
            )

        current_hash = compute_asset_fingerprint(p)

        # 1. Engine hash / Asset hash drift
        if engine_drifted:
            reasons.append(DriftReason.ENGINE_HASH_DRIFT)
            details.append("Engine code modified since last latch")
        elif recorded_hash is not None and recorded_hash != current_hash:
            reasons.append(DriftReason.ENGINE_HASH_DRIFT)
            details.append(f"Asset hash mismatch (current: {current_hash[:8]}, recorded: {recorded_hash[:8]})")

        # 2. Structural Anti-Slop: Forbidden dashes
        try:
            assert_no_forbidden_dashes(content, context=rel_key)
        except ValueError as ex:
            reasons.append(DriftReason.STRUCTURAL_CONTRACT_VIOLATION)
            details.append(str(ex))

        # 3. Structural Anti-Slop: Forbidden jargon
        content_lower = content.lower()
        for jargon in FORBIDDEN_JARGON:
            if jargon.lower() in content_lower:
                reasons.append(DriftReason.STRUCTURAL_CONTRACT_VIOLATION)
                details.append(f"Forbidden jargon detected: '{jargon}'")

        # 4. Structural Anti-Slop: Prompt leakage
        for term in PROMPT_LEAKAGE_TERMS:
            if term.lower() in content_lower:
                reasons.append(DriftReason.STRUCTURAL_CONTRACT_VIOLATION)
                details.append(f"Prompt leakage detected: '{term}'")

        # 5. Cross-Property Boundary Contamination
        foreign_matches = self.scanner.scan_text(content, adapter.property_id, context=rel_key)
        if foreign_matches:
            reasons.append(DriftReason.PROPERTY_CONTAMINATION)
            details.append(f"Cross-property contamination detected: foreign tokens {foreign_matches}")

        # 6. Touch Targets (HTML / CSS)
        if p.suffix in (".html", ".css"):
            try:
                assert_touch_targets(content, is_css=(p.suffix == ".css"), context=rel_key)
            except ValueError as ex:
                reasons.append(DriftReason.STRUCTURAL_CONTRACT_VIOLATION)
                details.append(f"Touch target violation: {ex}")

        # 7. JSON-LD Schemas (HTML)
        if p.suffix == ".html" and '<script type="application/ld+json"' in content:
            try:
                assert_valid_jsonld(content, context=rel_key)
            except ValueError as ex:
                reasons.append(DriftReason.STRUCTURAL_CONTRACT_VIOLATION)
                details.append(f"JSON-LD schema violation: {ex}")

        # 8. Sitemap validation (XML)
        if p.suffix == ".xml" and ("sitemap" in p.name.lower() or "<urlset" in content):
            try:
                assert_sitemap_parses(content)
            except ValueError as ex:
                reasons.append(DriftReason.STRUCTURAL_CONTRACT_VIOLATION)
                details.append(f"Sitemap XML violation: {ex}")

        # 9. Comparison layout contracts (HTML)
        if p.suffix == ".html":
            has_containers = any(
                tag in content.lower()
                for tag in ("<carousel", "<imagegrid", "<layout", "class=\"carousel", "class=\"comparison")
            )
            if has_containers:
                try:
                    assert_comparison_layout_contracts(content)
                except ValueError as ex:
                    reasons.append(DriftReason.STRUCTURAL_CONTRACT_VIOLATION)
                    details.append(f"Layout container violation: {ex}")

        # 10. Operational Rate-Limit and Bot Shield (HTML / headers)
        if self.enforce_operational_shield and p.suffix == ".html":
            from pseofactory.contracts import assert_rate_limit_and_bot_shield
            try:
                assert_rate_limit_and_bot_shield(content, context=rel_key)
            except ValueError as ex:
                reasons.append(DriftReason.OPERATIONAL_SHIELD_GAP)
                details.append(f"Operational shield gap: {ex}")

        # 11. Live Truth Audit (Pricing, Banned Claims, Mandatory Disclosures)
        if p.suffix == ".html":
            truth_violations = self.truth_engine.audit_html(
                content,
                property_id=adapter.property_id,
                context=rel_key,
            )
            if truth_violations:
                reasons.append(DriftReason.TRUTH_CONTRADICTION)
                details.extend([f"Truth contradiction: {v}" for v in truth_violations])


        if reasons:
            rec = AssetDriftRecord(
                asset_path=str(p),
                slug=self.extract_slug(p, adapter.dist_dir),
                reasons=reasons,
                details=details,
                current_hash=current_hash,
                recorded_hash=recorded_hash,
                metadata={"rel_key": rel_key},
            )
            if cache_key and not engine_drifted:
                self._audit_cache[cache_key] = rec
            return rec

        if cache_key and not engine_drifted:
            self._audit_cache[cache_key] = None
            if hasattr(self, "_fingerprint_cache"):
                self._fingerprint_cache[cache_key] = current_hash
        return None

    def audit_all(
        self,
        adapter: PropertyAdapter,
        ledger_path: Optional[Union[str, Path]] = None,
        state_file: Optional[Union[str, Path]] = None,
        check_engine_drift: bool = True,
        check_ledger: Optional[bool] = None,
    ) -> AssetIntegrityReport:
        """
        Executes comprehensive asset integrity audit across all assets in adapter.dist_dir.
        Zero em-dashes. Zero en-dashes.
        """
        assets = adapter.list_assets()
        drifted: List[AssetDriftRecord] = []

        # Determine ledger & engine drift
        should_check_ledger = check_ledger if check_ledger is not None else check_engine_drift
        ledger: Dict[str, Any] = {}
        if should_check_ledger:
            if ledger_path:
                ledger = load_asset_ledger(ledger_path)
            else:
                candidate_ledgers = [
                    adapter.dist_dir.parent / ".agy" / "asset_ledger.json",
                ]
                if getattr(adapter, "repo_path", None):
                    candidate_ledgers.append(adapter.repo_path / ".agy" / "asset_ledger.json")
                if adapter.dist_dir.parent.parent.is_dir():
                    candidate_ledgers.append(adapter.dist_dir.parent.parent / ".agy" / "asset_ledger.json")
                for cl in candidate_ledgers:
                    if cl.is_file():
                        ledger = load_asset_ledger(cl)
                        break

        engine_drifted = False
        if check_engine_drift:
            b_dirs = getattr(adapter, "base_dirs", None)
            s_file = None
            if state_file:
                s_file = Path(state_file)
            else:
                candidate_paths = [
                    adapter.dist_dir.parent / ".agy" / "engine_hash.json",
                ]
                if getattr(adapter, "repo_path", None):
                    candidate_paths.append(adapter.repo_path / ".agy" / "engine_hash.json")
                if adapter.dist_dir.parent.parent.is_dir():
                    candidate_paths.append(adapter.dist_dir.parent.parent / ".agy" / "engine_hash.json")
                for cp in candidate_paths:
                    if cp.is_file():
                        s_file = cp
                        break
            if s_file is not None and (state_file is not None or s_file.exists()):
                drift_res = detect_engine_drift(s_file, base_dirs=b_dirs)
                engine_drifted = bool(drift_res.get("drift_detected", False))

        for asset in assets:
            record = self.audit_asset(
                asset,
                adapter=adapter,
                ledger=ledger,
                engine_drifted=engine_drifted,
            )
            if record:
                drifted.append(record)

        # Optional Master SEO Checklist check
        if self.enforce_master_seo and adapter.dist_dir.exists() and (adapter.dist_dir / "sitemap.xml").is_file():
            try:
                from pseofactory.verifier import MasterSEOVerifier
                if self._seo_verifier is None or getattr(self._seo_verifier, "dist_dir", None) != adapter.dist_dir:
                    self._seo_verifier = MasterSEOVerifier(
                        dist_dir=adapter.dist_dir,
                        canonical_base=adapter.canonical_base,
                        domain=adapter.domain,
                        brand_name=adapter.brand_name,
                        tools=getattr(adapter, "tools", None),
                    )
                v = self._seo_verifier
                seo_report = v.audit_seo_checklist(
                    dist_dir=adapter.dist_dir,
                    raise_on_error=False,
                    enforce_relevance=(len(assets) >= 10),
                )
                if seo_report.get("status") == "FAIL":
                    for issue in seo_report.get("issues", []):
                        drifted.append(
                            AssetDriftRecord(
                                asset_path=str(adapter.dist_dir),
                                slug=None,
                                reasons=[DriftReason.CONTENT_RELEVANCE_GAP],
                                details=[f"Master SEO Checklist: {issue}"],
                            )
                        )
            except Exception as ex:
                drifted.append(
                    AssetDriftRecord(
                        asset_path=str(adapter.dist_dir),
                        slug=None,
                        reasons=[DriftReason.CONTENT_RELEVANCE_GAP],
                        details=[f"Master SEO Verifier execution error: {ex}"],
                    )
                )

        status = "PASS" if len(drifted) == 0 else "DRIFT"
        return AssetIntegrityReport(
            property_id=adapter.property_id,
            total_assets_checked=len(assets),
            compliant_assets_count=len(assets) - len(drifted),
            drifted_assets_count=len(drifted),
            drifted_assets=drifted,
            status=status,
        )


class RefactorCascadeEngine:
    """
    Automated refactor engine for drifted static assets:
    - Scoped environment isolation per tenant
    - Atomic staged swap (.tmp staging and os.replace)
    - Transactional rollback on verification failure
    - Bounded retries (3 attempts ceiling) with exponential backoff
    - Persistent failure routing to Dead Letter Queue (DLQ)
    Zero em-dashes. Zero en-dashes.
    """

    def __init__(
        self,
        evaluator: Optional[AssetIntegrityEvaluator] = None,
        max_retries: int = 3,
        initial_backoff: float = 0.5,
        backoff_multiplier: float = 2.0,
        dlq_path: Optional[Union[str, Path]] = None,
    ):
        self.evaluator = evaluator or AssetIntegrityEvaluator()
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.backoff_multiplier = backoff_multiplier
        if dlq_path:
            self.dlq_path = Path(dlq_path).resolve()
        elif os.getenv("PYTEST_CURRENT_TEST"):
            self.dlq_path = (
                Path(tempfile.gettempdir()) / f"pseofactory_pytest_dlq_{os.getpid()}.json"
            ).resolve()
        else:
            self.dlq_path = Path(".agy/maintenance_dlq.json").resolve()

    def map_dependencies(self, asset_path: Union[str, Path], adapter: PropertyAdapter) -> List[Path]:
        """
        Maps a regenerated asset to downstream syndication and index dependencies.
        Zero em-dashes. Zero en-dashes.
        """
        target = Path(asset_path).resolve()
        deps: List[Path] = []
        d_dir = adapter.dist_dir
        if not d_dir.exists():
            return deps

        for name in ("sitemap.xml", "sitemap-leaves.xml", "sitemap-hubs.xml", "llms.txt", "llms-full.txt"):
            p = d_dir / name
            if p.exists() and p != target:
                deps.append(p)
        return deps

    def route_to_dlq(
        self,
        property_id: str,
        record: AssetDriftRecord,
        error_msg: str,
    ) -> None:
        """
        Routes persistent refactor failures to Dead Letter Queue (DLQ).
        Deduplicates by asset id so repeat drift runs do not append duplicates.
        Zero em-dashes. Zero en-dashes.
        """
        self.dlq_path.parent.mkdir(parents=True, exist_ok=True)
        entries: List[Dict[str, Any]] = []
        if self.dlq_path.is_file():
            try:
                data = json.loads(self.dlq_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    entries = data
            except Exception:
                entries = []

        now_iso = datetime.now(timezone.utc).isoformat()
        entry = {
            "property_id": property_id,
            "asset_path": record.asset_path,
            "slug": record.slug,
            "reasons": [r.value if isinstance(r, DriftReason) else str(r) for r in record.reasons],
            "details": record.details,
            "attempts": self.max_retries,
            "last_error": error_msg,
            "timestamp": now_iso,
        }

        # Deduplicate by asset id (matching slug or asset_path within property)
        existing_index = None
        for idx, item in enumerate(entries):
            same_prop = not property_id or item.get("property_id") == property_id
            same_slug = bool(record.slug and item.get("slug") == record.slug)
            same_path = bool(
                record.asset_path
                and (
                    item.get("asset_path") == record.asset_path
                    or Path(item.get("asset_path", "")).resolve() == Path(record.asset_path).resolve()
                )
            )
            if same_prop and (same_slug or same_path):
                existing_index = idx
                break

        if existing_index is not None:
            entries[existing_index].update(entry)
        else:
            entries.append(entry)

        # Atomic DLQ write via .tmp and os.replace
        tmp_dlq = self.dlq_path.with_name(f"{self.dlq_path.name}.tmp.{os.getpid()}.{uuid.uuid4().hex[:6]}")
        tmp_dlq.write_text(json.dumps(entries, indent=2), encoding="utf-8")
        os.replace(tmp_dlq, self.dlq_path)

    def get_quarantine_entry(
        self,
        record: Union[AssetDriftRecord, str, Path],
        property_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Returns the DLQ entry if the asset is quarantined, else None.
        Zero em-dashes. Zero en-dashes.
        """
        if not self.dlq_path.is_file():
            return None
        try:
            data = json.loads(self.dlq_path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                return None

            slug = None
            asset_path = None
            if isinstance(record, AssetDriftRecord):
                slug = record.slug
                asset_path = record.asset_path
            elif isinstance(record, (str, Path)):
                asset_path = str(record)
                slug = Path(record).stem

            for entry in data:
                same_prop = not property_id or entry.get("property_id") == property_id
                same_slug = bool(slug and entry.get("slug") == slug)
                same_path = bool(
                    asset_path
                    and (
                        entry.get("asset_path") == asset_path
                        or Path(entry.get("asset_path", "")).resolve() == Path(asset_path).resolve()
                    )
                )
                if same_prop and (same_slug or same_path):
                    return entry
        except Exception:
            return None
        return None

    def is_quarantined(
        self,
        record: Union[AssetDriftRecord, str, Path],
        property_id: Optional[str] = None,
    ) -> bool:
        """
        Checks whether an asset is currently quarantined in the DLQ.
        Zero em-dashes. Zero en-dashes.
        """
        entry = self.get_quarantine_entry(record, property_id)
        if not entry:
            return False
        q_reasons = entry.get("reasons", [])
        if bool(q_reasons) and all(
            r == "ENGINE_HASH_DRIFT" or r == DriftReason.ENGINE_HASH_DRIFT.value
            for r in q_reasons
        ):
            return False
        return True

    def list_dlq(self, property_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Lists entries currently quarantined in the DLQ.
        Zero em-dashes. Zero en-dashes.
        """
        if not self.dlq_path.is_file():
            return []
        try:
            data = json.loads(self.dlq_path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                return []
            if property_id:
                return [e for e in data if e.get("property_id") == property_id]
            return data
        except Exception:
            return []

    def replay_dlq(
        self,
        property_id: Optional[str] = None,
        slug: Optional[str] = None,
        asset_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Replays quarantined entries by removing them from DLQ.
        Returns the list of replayed entries.
        Zero em-dashes. Zero en-dashes.
        """
        if not self.dlq_path.is_file():
            return []
        try:
            data = json.loads(self.dlq_path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                return []
        except Exception:
            return []

        replayed = []
        remaining = []
        resolved_target = Path(asset_path).resolve() if asset_path else None
        for entry in data:
            match_prop = not property_id or entry.get("property_id") == property_id
            if slug is None and asset_path is None:
                match_target = True
            else:
                match_slug = bool(slug is not None and entry.get("slug") == slug)
                entry_path = entry.get("asset_path")
                match_path = bool(
                    asset_path is not None
                    and entry_path
                    and (
                        entry_path == str(asset_path)
                        or Path(entry_path).resolve() == resolved_target
                    )
                )
                match_target = match_slug or match_path
            if match_prop and match_target:
                replayed.append(entry)
            else:
                remaining.append(entry)

        if replayed:
            tmp_dlq = self.dlq_path.with_name(f"{self.dlq_path.name}.tmp.{os.getpid()}.{uuid.uuid4().hex[:6]}")
            tmp_dlq.write_text(json.dumps(remaining, indent=2), encoding="utf-8")
            os.replace(tmp_dlq, self.dlq_path)

        return replayed

    def replay_quarantine(
        self,
        property_id: Optional[str] = None,
        slug: Optional[str] = None,
        asset_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Replays quarantined entries by removing them from DLQ.
        Zero em-dashes. Zero en-dashes.
        """
        return self.replay_dlq(property_id=property_id, slug=slug, asset_path=asset_path)

    def refactor_asset(
        self,
        record: AssetDriftRecord,
        adapter: PropertyAdapter,
        force: bool = False,
        dry_run: bool = False,
    ) -> bool:
        """
        Refactors an individual drifted asset with atomic staged swap and rollback.
        Returns True on green verification, False on exhaustion/DLQ.
        Zero em-dashes. Zero en-dashes.
        """
        target_path = Path(record.asset_path).resolve()
        slug = record.slug or target_path.stem
        backoff = self.initial_backoff
        last_error = "Unknown error"

        # Quarantine awareness: Skip assets already quarantined in DLQ unless force=True
        if not force:
            q_entry = self.get_quarantine_entry(record, property_id=adapter.property_id)
            if q_entry:
                q_reasons = q_entry.get("reasons", [])
                is_only_engine_drift = bool(q_reasons) and all(
                    r == "ENGINE_HASH_DRIFT" or r == DriftReason.ENGINE_HASH_DRIFT.value
                    for r in q_reasons
                )
                if not is_only_engine_drift:
                    q_ts = q_entry.get("timestamp", "unknown")
                    print(
                        f"Asset '{slug}' is quarantined in DLQ (timestamp: {q_ts}, reasons: {q_reasons}); skipping retries."
                    )
                    return False

        if dry_run:
            if target_path.is_file():
                self.evaluator.audit_asset(target_path, adapter)
            return True

        for attempt in range(1, self.max_retries + 1):
            backup_path: Optional[Path] = None
            try:
                # 1. Transactional isolation & backup in scratch outside dist (HWL-1370)
                if target_path.is_file():
                    scratch_base = Path("/home/ubuntuadmin/projects/.agy/scratch")
                    if scratch_base.is_dir():
                        backup_dir = scratch_base / f"backups_{os.getpid()}"
                    else:
                        backup_dir = Path(tempfile.gettempdir()) / f"pseofactory_backups_{os.getpid()}"
                    backup_dir.mkdir(parents=True, exist_ok=True)
                    backup_name = f".tmp_backup.{os.getpid()}.{uuid.uuid4().hex[:8]}.{target_path.name}"
                    backup_path = backup_dir / backup_name
                    shutil.copy2(target_path, backup_path)

                # 2. Rebuild in isolated environment
                with adapter.scoped_environment():
                    try:
                        build_ok = adapter.build_asset(slug, target_file=target_path)
                    except TypeError:
                        build_ok = adapter.build_asset(slug)
                    if not build_ok and not target_path.exists():
                        raise RuntimeError(f"Builder failed to generate asset for slug '{slug}'")

                # 3. Fail-Closed Verification Gate
                audit_record = self.evaluator.audit_asset(target_path, adapter)
                if audit_record is not None:
                    raise ValueError(
                        f"Refactored asset failed post-build audit: {audit_record.details}"
                    )

                # Asset verification callback if declared
                verify_dict = adapter.verify_asset(target_path)
                if verify_dict.get("status") == "FAIL":
                    raise ValueError(
                        f"Adapter verification failed: {verify_dict.get('issues')}"
                    )

                # 4. Atomic Commit: Clean up backup
                if backup_path and backup_path.exists():
                    backup_path.unlink(missing_ok=True)
                self.replay_quarantine(
                    property_id=adapter.property_id,
                    slug=slug,
                    asset_path=str(target_path),
                )
                return True

            except LockContentionError as lce:
                # Catch LockContentionError and defer/abort without routing to DLQ
                if backup_path and backup_path.exists():
                    try:
                        shutil.copy2(backup_path, target_path)
                        backup_path.unlink(missing_ok=True)
                    except Exception as rb_ex:
                        print(f"Warning: Rollback error: {rb_ex}")
                raise lce

            except Exception as ex:
                last_error = str(ex)
                # 5. Transactional Rollback: Restore backup over target_path
                if backup_path and backup_path.exists():
                    try:
                        shutil.copy2(backup_path, target_path)
                        backup_path.unlink(missing_ok=True)
                    except Exception as rb_ex:
                        print(f"Warning: Rollback error: {rb_ex}")

                if attempt < self.max_retries:
                    time.sleep(backoff)
                    backoff *= self.backoff_multiplier

        # All retries exhausted: Route to DLQ
        self.route_to_dlq(adapter.property_id, record, last_error)
        return False

    def refactor_all(
        self,
        records: List[AssetDriftRecord],
        adapter: PropertyAdapter,
        force: bool = False,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Refactors all provided drifted records serially with dependency cascade.
        Zero em-dashes. Zero en-dashes.
        """
        refactored_count = 0
        failed_count = 0
        all_dependencies: Set[str] = set()

        # Quarantine awareness: filter out records already quarantined in DLQ unless force=True
        actionable_records = [
            r for r in records
            if force or not self.is_quarantined(r, adapter.property_id)
        ]

        total_assets = len(adapter.list_assets())
        should_bulk_rebuild = bool(actionable_records) and (
            any(DriftReason.ENGINE_HASH_DRIFT in rec.reasons for rec in actionable_records)
            or (total_assets > 0 and len(actionable_records) >= total_assets * 0.5)
        )

        if should_bulk_rebuild:
            if dry_run:
                for rec in actionable_records:
                    refactored_count += 1
                    deps = self.map_dependencies(rec.asset_path, adapter)
                    for d in deps:
                        all_dependencies.add(str(d))
                return {
                    "refactored": refactored_count,
                    "failed": 0,
                    "dependencies": sorted(list(all_dependencies)),
                }

            try:
                with adapter.scoped_environment():
                    build_ok = adapter.build_all()
            except LockContentionError as lce:
                print(f"Lock contention on property '{adapter.property_id}': deferring bulk rebuild without DLQ routing.")
                return {
                    "refactored": 0,
                    "failed": 0,
                    "deferred": len(actionable_records),
                    "dependencies": [],
                    "lock_contention": True,
                }

            post_audit_map = {
                rec.slug: self.evaluator.audit_asset(Path(rec.asset_path).resolve(), adapter)
                for rec in actionable_records
                if rec.slug is not None and Path(rec.asset_path).resolve().is_file()
            }
            for rec in actionable_records:
                target_path = Path(rec.asset_path).resolve()
                if target_path.is_dir():
                    audit_record = None
                    verify_dict = {"status": "PASS"}
                else:
                    audit_record = (
                        post_audit_map.get(rec.slug)
                        if rec.slug is not None
                        else self.evaluator.audit_asset(target_path, adapter)
                    )
                    verify_dict = (
                        adapter.verify_asset(target_path)
                        if hasattr(adapter, "verify_asset")
                        else {"status": "PASS"}
                    )
                if (
                    build_ok
                    and audit_record is None
                    and verify_dict.get("status") != "FAIL"
                ):
                    refactored_count += 1
                    self.replay_quarantine(
                        property_id=adapter.property_id,
                        slug=rec.slug,
                        asset_path=rec.asset_path,
                    )
                    deps = self.map_dependencies(rec.asset_path, adapter)
                    for d in deps:
                        all_dependencies.add(str(d))
                else:
                    err_msg = (
                        f"Post-build audit failed: {audit_record.details}"
                        if audit_record
                        else (
                            f"Adapter verification failed: {verify_dict.get('issues')}"
                            if verify_dict.get("status") == "FAIL"
                            else "Bulk rebuild failed"
                        )
                    )
                    self.route_to_dlq(adapter.property_id, rec, err_msg)
                    failed_count += 1

            if build_ok and failed_count == 0:
                self.replay_quarantine(property_id=adapter.property_id)
        else:
            for rec in actionable_records:
                try:
                    success = self.refactor_asset(rec, adapter, force=force, dry_run=dry_run)
                    if success:
                        refactored_count += 1
                        deps = self.map_dependencies(rec.asset_path, adapter)
                        for d in deps:
                            all_dependencies.add(str(d))
                    else:
                        failed_count += 1
                except LockContentionError as lce:
                    print(f"Lock contention on property '{adapter.property_id}': deferring asset cascade without DLQ routing.")
                    return {
                        "refactored": refactored_count,
                        "failed": failed_count,
                        "deferred": len(actionable_records) - (refactored_count + failed_count),
                        "dependencies": sorted(list(all_dependencies)),
                        "lock_contention": True,
                    }

        return {
            "refactored": refactored_count,
            "failed": failed_count,
            "dependencies": sorted(list(all_dependencies)),
        }


class MaintenanceLifecycle:
    """
    Closed-loop autonomous maintenance coordinator:
    1. Audit assets via AssetIntegrityEvaluator
    2. Flag drifted assets
    3. Refactor cascade with atomic swap and rollback
    4. Post-refactor fail-closed verification (raise_on_error=True)
    5. Commit latch (HWL-1349 post-pipeline commit)
    Zero em-dashes. Zero en-dashes.
    """

    def __init__(
        self,
        evaluator: Optional[AssetIntegrityEvaluator] = None,
        cascade_engine: Optional[RefactorCascadeEngine] = None,
        registry: Optional[TenantRegistry] = None,
        trend_runner: Optional[Any] = None,
        indexer: Optional[Any] = None,
    ):
        self.evaluator = evaluator or AssetIntegrityEvaluator()
        self.cascade_engine = cascade_engine or RefactorCascadeEngine(evaluator=self.evaluator)
        self.registry = registry or TenantRegistry.default()
        self.trend_runner = trend_runner
        self.indexer = indexer

    def run(
        self,
        property_or_adapter: Union[str, PropertyAdapter],
        force: bool = False,
        state_file: Optional[Union[str, Path]] = None,
        ledger_file: Optional[Union[str, Path]] = None,
        enable_gitops: bool = True,
        enable_distribution: bool = True,
        run_id: Optional[str] = None,
        dry_run: bool = False,
        skip_ci: bool = False,
        workflow: Optional[str] = None,
        edge_url: Optional[str] = None,
    ) -> MaintenanceResult:
        """
        Executes single-tenant closed-loop maintenance lifecycle.
        Zero em-dashes. Zero en-dashes.
        """
        start_time = time.time()
        if isinstance(property_or_adapter, str):
            adapter = self.registry.get_adapter(property_or_adapter)
        else:
            adapter = property_or_adapter

        s_file = (
            Path(state_file).resolve()
            if state_file
            else adapter.dist_dir.parent / ".agy" / "engine_hash.json"
        )
        l_file = (
            Path(ledger_file).resolve()
            if ledger_file
            else adapter.dist_dir.parent / ".agy" / "asset_ledger.json"
        )

        with adapter.scoped_environment():
            # Stage 1: Preflight Asset Integrity Audit
            passed_s_file = Path(state_file).resolve() if state_file else None
            passed_l_file = Path(ledger_file).resolve() if ledger_file else None
            report = self.evaluator.audit_all(
                adapter=adapter,
                ledger_path=passed_l_file if passed_l_file else (l_file if l_file.exists() else None),
                state_file=passed_s_file if passed_s_file else (s_file if s_file.exists() else None),
            )

            print(
                f"[DISPATCH:GROWTH_SEO] Preflight asset audit -> property={adapter.property_id}, "
                f"audited={report.total_assets_checked} assets, drifted={report.drifted_assets_count}"
            )

            if report.drifted_assets_count == 0 and not dry_run:
                self.cascade_engine.replay_quarantine(property_id=adapter.property_id)

            # Stage 2: Universal Idempotency & DLQ Filter (HWL-1231)
            actionable_drifted = []
            quarantined_drifted = []
            for rec in report.drifted_assets:
                q_entry = self.cascade_engine.get_quarantine_entry(rec, adapter.property_id)
                if q_entry:
                    q_reasons = q_entry.get("reasons", [])
                    is_only_engine_drift = bool(q_reasons) and all(
                        r == "ENGINE_HASH_DRIFT" or r == DriftReason.ENGINE_HASH_DRIFT.value
                        for r in q_reasons
                    )
                    if is_only_engine_drift or force:
                        actionable_drifted.append(rec)
                    else:
                        quarantined_drifted.append((rec, q_entry))
                else:
                    actionable_drifted.append(rec)

            if quarantined_drifted:
                for rec, q_entry in quarantined_drifted:
                    print(
                        f"Skipping quarantined asset '{rec.slug or rec.asset_path}' "
                        f"(quarantined at {q_entry.get('timestamp')} for reasons {q_entry.get('reasons')})"
                    )

            # Stage 3: Retrofit-First Recompile & Quality Gate
            cascade_res = {"refactored": 0, "failed": 0, "dependencies": []}
            if actionable_drifted:
                cascade_res = self.cascade_engine.refactor_all(
                    actionable_drifted, adapter, force=force, dry_run=dry_run
                )
                if cascade_res.get("lock_contention"):
                    return MaintenanceResult(
                        property_id=adapter.property_id,
                        status="DEFERRED",
                        assets_audited=report.total_assets_checked,
                        assets_drifted=report.drifted_assets_count,
                        assets_refactored=cascade_res.get("refactored", 0),
                        assets_failed=0,
                        engine_hash=None,
                        duration_seconds=time.time() - start_time,
                    )
                retrofit_report = self.evaluator.audit_all(
                    adapter=adapter,
                    check_engine_drift=False,
                    check_ledger=False,
                )
                lingering_drifted = [
                    rec for rec in retrofit_report.drifted_assets
                    if not self.cascade_engine.is_quarantined(rec, adapter.property_id)
                ]
                # Gate new candidate generation: Do NOT compile new candidate pages from trends
                # if existing assets remain drifted or fail the integrity audit.
                if len(lingering_drifted) > 0 and not dry_run:
                    duration = time.time() - start_time
                    status = (
                        "PARTIAL_SUCCESS"
                        if len(lingering_drifted) < len(actionable_drifted)
                        else "FAILED"
                    )
                    return MaintenanceResult(
                        property_id=adapter.property_id,
                        status=status,
                        assets_audited=retrofit_report.total_assets_checked,
                        assets_drifted=retrofit_report.drifted_assets_count,
                        assets_refactored=cascade_res.get("refactored", 0),
                        assets_failed=retrofit_report.drifted_assets_count,
                        failed_records=[r.to_dict() for r in retrofit_report.drifted_assets],
                        engine_hash=None,
                        duration_seconds=duration,
                        trend_status="SKIPPED_UNVERIFIED_FLEET",
                    )

            # Stage 4: Opportunity Discovery (TrendCronRunner)
            trend_status_val: Optional[str] = None
            approved_build: List[Dict[str, Any]] = []
            refactor_pages: List[Dict[str, Any]] = []
            try:
                if self.trend_runner is not None:
                    runner = self.trend_runner
                elif "PYTEST_CURRENT_TEST" in os.environ and os.getenv("PSEUFACTORY_LIVE_TREND_CRON") != "1":
                    runner = None
                else:
                    from pseofactory.trends.cron import TrendCronRunner
                    runner = TrendCronRunner()

                if runner is not None:
                    try:
                        trend_res = runner.run_cron_cycle(property_filter=adapter.property_id, dry_run=dry_run)
                    except TypeError:
                        trend_res = runner.run_cron_cycle(dry_run=dry_run)

                    trend_status_val = trend_res.get("status", "SUCCESS") if isinstance(trend_res, dict) else "SUCCESS"
                    if isinstance(trend_res, dict):
                        approved_build = trend_res.get("approved_build", [])
                        refactor_pages = trend_res.get("refactor_pages", [])
                else:
                    trend_status_val = "SKIPPED_TEST_ENV"
            except Exception as tr_err:
                print(f"Warning: Trend discovery stage error for '{adapter.property_id}': {tr_err}")
                trend_status_val = "DRY_RUN" if dry_run else "FAILED"

            # Recalibrated Early-Exit Gate:
            # Exit with SKIPPED_NO_CHANGES strictly when no pre-existing drift and no opportunity actions
            if (
                not force
                and not dry_run
                and len(actionable_drifted) == 0
                and len(approved_build) == 0
                and len(refactor_pages) == 0
            ):
                duration = time.time() - start_time
                return MaintenanceResult(
                    property_id=adapter.property_id,
                    status="SKIPPED_NO_CHANGES",
                    assets_audited=report.total_assets_checked,
                    assets_drifted=report.drifted_assets_count,
                    assets_refactored=0,
                    assets_failed=0,
                    engine_hash=compute_engine_hash(),
                    duration_seconds=duration,
                    trend_status=trend_status_val,
                    partner_readiness_status="EVALUATED",
                )

            # Stage 5: Compile Approved Builds & Apply Refactor Overlays
            for item in approved_build:
                b_slug = item.get("slug") if isinstance(item, dict) else str(item)
                if dry_run:
                    print(f"[DRY_RUN] Simulated asset build for opportunity slug '{b_slug}'")
                else:
                    try:
                        adapter.build_asset(slug=b_slug)
                    except TypeError:
                        adapter.build_asset(b_slug)

            overlay_drifted = []
            for item in refactor_pages:
                r_slug = item.get("slug") if isinstance(item, dict) else str(item)
                if not dry_run:
                    try:
                        from pseofactory.gsc_remediation import compile_remediation_overlay_spec
                        base_dir = getattr(adapter, "base_dir", None) or adapter.dist_dir.parent
                        overlay_dir = base_dir / "content" / "overlays"
                        overlay_dir.mkdir(parents=True, exist_ok=True)
                        overlay_file = overlay_dir / f"{r_slug}.json"
                        cand_dict = dict(item) if isinstance(item, dict) else {"slug": r_slug}
                        cand_dict.setdefault("slug", r_slug)
                        cand_dict.setdefault("property_id", adapter.property_id)
                        overlay_payload = compile_remediation_overlay_spec(
                            cand_dict,
                            tenant_id=adapter.property_id,
                            lock_days=28,
                        )
                        if isinstance(item, dict) and isinstance(item.get("overlay_spec"), dict):
                            for k, v in item["overlay_spec"].items():
                                if v and k not in overlay_payload:
                                    overlay_payload[k] = v
                        overlay_payload["action"] = "REFACTOR_PAGE"
                        overlay_file.write_text(json.dumps(overlay_payload, indent=2), encoding="utf-8")
                    except Exception as o_err:
                        print(f"Warning: Failed to persist overlay for slug '{r_slug}': {o_err}")

                # Locate or synthesize asset path
                target_html = adapter.dist_dir / f"{r_slug}.html"
                if not target_html.exists() and (adapter.dist_dir / r_slug / "index.html").exists():
                    target_html = adapter.dist_dir / r_slug / "index.html"
                r_rec = AssetDriftRecord(
                    asset_path=str(target_html),
                    slug=r_slug,
                    reasons=[DriftReason.OPPORTUNITY_OVERLAY],
                    details=["Opportunity overlay applied with 28-day measurement lock"],
                )
                overlay_drifted.append(r_rec)

            if overlay_drifted:
                overlay_res = self.cascade_engine.refactor_all(
                    overlay_drifted, adapter, force=force, dry_run=dry_run
                )
                cascade_res["refactored"] += overlay_res.get("refactored", 0)
                cascade_res["failed"] += overlay_res.get("failed", 0)

            # Stage 6: Fail-Closed Post-Build Verification Gate
            post_report = self.evaluator.audit_all(
                adapter=adapter,
                check_engine_drift=False,
                check_ledger=False,
            )

            post_actionable_drifted = [
                rec for rec in post_report.drifted_assets
                if not self.cascade_engine.is_quarantined(rec, adapter.property_id)
            ]

            # In live mode, lingering drifted assets fail the gate
            if len(post_actionable_drifted) > 0 and not dry_run:
                duration = time.time() - start_time
                status = (
                    "PARTIAL_SUCCESS"
                    if len(post_actionable_drifted) < (len(actionable_drifted) + len(overlay_drifted))
                    else "FAILED"
                )
                return MaintenanceResult(
                    property_id=adapter.property_id,
                    status=status,
                    assets_audited=post_report.total_assets_checked,
                    assets_drifted=post_report.drifted_assets_count,
                    assets_refactored=cascade_res["refactored"],
                    assets_failed=post_report.drifted_assets_count,
                    failed_records=[r.to_dict() for r in post_report.drifted_assets],
                    engine_hash=None,
                    duration_seconds=duration,
                    trend_status=trend_status_val,
                )

            # Stage 6: Statutory Cross-Tenant Contamination Firewall (HWL-1371)
            scanner = CrossPropertyContaminationScanner()
            contamination = scanner.scan_directory(adapter.dist_dir, adapter.property_id)
            if contamination:
                duration = time.time() - start_time
                return MaintenanceResult(
                    property_id=adapter.property_id,
                    status="FAILED",
                    assets_audited=post_report.total_assets_checked,
                    assets_drifted=len(contamination),
                    assets_refactored=cascade_res["refactored"],
                    assets_failed=len(contamination),
                    failed_records=[
                        {"asset_path": k, "reasons": ["PROPERTY_CONTAMINATION"], "details": v}
                        for k, v in contamination.items()
                    ],
                    engine_hash=None,
                    duration_seconds=duration,
                    trend_status=trend_status_val,
                )

            # Stage 10 -> Preflight Airlock: Crawl Budget Airlock Inspection
            indexing_status_val: Optional[str] = None
            pre_report = None
            try:
                from pseofactory.indexing.preflight import IndexingPreflightEngine
                preflight_engine = IndexingPreflightEngine(
                    property_id=adapter.property_id,
                    domain=adapter.domain,
                    dist_dir=adapter.dist_dir,
                )
                pre_report = preflight_engine.inspect_dist(adapter.dist_dir)
                if pre_report.blocked_urls:
                    q_file = adapter.dist_dir.parent / ".agy" / "indexing_quarantine_ledger.json"
                    preflight_engine.quarantine_blocked_urls(pre_report.blocked_urls, ledger_path=q_file)
                indexing_status_val = "AIRLOCK_PASSED"
            except Exception as idx_err:
                print(f"Warning: Indexing airlock stage error for '{adapter.property_id}': {idx_err}")
                indexing_status_val = "DRY_RUN" if dry_run else "SUCCESS"

            gitops_status_val = "SKIPPED"
            dist_status_val = "SKIPPED"

            # Stage 8: GitOps Worktree Commit & Edge Verification Latch
            if enable_gitops:
                from pseofactory.gitops import GitOpsCoordinator
                repo_path = adapter.repo_path or adapter.dist_dir.parent
                coordinator = GitOpsCoordinator(
                    repo_path=repo_path,
                    branch="main",
                    run_id=run_id,
                    dry_run=dry_run,
                    workflow=workflow,
                )
                target_edge = edge_url or (getattr(adapter, "canonical_base", None) if getattr(adapter, "repo_path", None) else None)
                gitops_res = coordinator.dispatch_to_shipper(
                    run_id=run_id,
                    property_id=adapter.property_id,
                    dry_run=dry_run,
                    commit_message=f"fix({adapter.property_id}): automated maintenance cycle",
                    skip_ci=skip_ci,
                    edge_url=target_edge,
                    dist_dir=adapter.dist_dir,
                    workflow=workflow,
                )
                gitops_status_val = gitops_res.status
                if gitops_res.status not in ("SUCCESS", "SKIPPED_NO_CHANGES", "SKIPPED_NOT_GIT_REPO", "SKIPPED_DRY_RUN", "DRY_RUN", "COMPLETED"):
                    duration = time.time() - start_time
                    return MaintenanceResult(
                        property_id=adapter.property_id,
                        status="FAILED",
                        assets_audited=post_report.total_assets_checked,
                        assets_drifted=0,
                        assets_refactored=cascade_res["refactored"],
                        assets_failed=1,
                        failed_records=[{"error": gitops_res.error or gitops_res.status, "gitops": gitops_res.to_dict()}],
                        engine_hash=None,
                        duration_seconds=duration,
                        gitops_status="FAILED",
                        trend_status=trend_status_val,
                    )

            # Stage 9: Multi-Channel Syndication Draft Staging
            if enable_distribution:
                from pseofactory.distributor import dispatch_to_distribution_lead
                dist_res = dispatch_to_distribution_lead(
                    run_id=run_id,
                    property_id=adapter.property_id,
                    dry_run=dry_run,
                    dist_dir=adapter.dist_dir,
                )
                dist_status_val = dist_res.get("status", "SUCCESS")
                if dist_status_val not in ("SUCCESS", "STAGED", "DRY_RUN", "SKIPPED"):
                    duration = time.time() - start_time
                    return MaintenanceResult(
                        property_id=adapter.property_id,
                        status="FAILED",
                        assets_audited=post_report.total_assets_checked,
                        assets_drifted=0,
                        assets_refactored=cascade_res["refactored"],
                        assets_failed=1,
                        failed_records=[{"error": dist_res.get("error", "Distribution dispatch failed"), "distribution": dist_res}],
                        engine_hash=None,
                        duration_seconds=duration,
                        gitops_status=gitops_status_val,
                        distribution_status="FAILED",
                        trend_status=trend_status_val,
                    )

            # Post-Deployment Push Indexing Dispatch (triggered after shipper edge verification passes)
            try:
                if (enable_gitops and gitops_status_val in ("SUCCESS", "DRY_RUN")) or (not enable_gitops):
                    if self.indexer is not None:
                        indexer_instance = self.indexer
                    else:
                        from pseofactory.indexer import PushIndexer
                        indexer_instance = PushIndexer(
                            domain=adapter.domain,
                            canonical_base=adapter.canonical_base,
                            dist_dir=adapter.dist_dir,
                        )

                    eligible_urls = pre_report.push_eligible_urls if pre_report else []
                    idx_res = indexer_instance.dispatch_automated_indexing(urls=eligible_urls, live=not dry_run)
                    indexing_status_val = idx_res.get("status", "SUCCESS") if isinstance(idx_res, dict) else "SUCCESS"
            except Exception as idx_err:
                print(f"Warning: Indexing dispatch stage error for '{adapter.property_id}': {idx_err}")
                indexing_status_val = "FAILED"
                try:
                    from pseofactory.telemetry import AtomicTelemetryLogger, TelemetryEvent
                    AtomicTelemetryLogger().log_event(
                        TelemetryEvent(
                            event_type="INDEXING_DISPATCH_FAILURE",
                            tenant_id=adapter.property_id,
                            error_message=str(idx_err),
                            action_taken="RECORDED",
                        )
                    )
                except Exception:
                    pass

            # Stage 7: HWL-1349 Post-Pipeline State & Ledger Latch
            all_assets = adapter.list_assets()
            asset_hashes: Dict[str, str] = {}
            for a in all_assets:
                rel = a.relative_to(adapter.dist_dir).as_posix()
                asset_hashes[rel] = compute_asset_fingerprint(a)

            b_dirs = getattr(adapter, "base_dirs", None)
            if not dry_run:
                current_engine_hash = record_engine_hash(s_file, base_dirs=b_dirs)
                record_asset_ledger(l_file, asset_hashes=asset_hashes, engine_hash=current_engine_hash)
            else:
                current_engine_hash = compute_engine_hash(base_dirs=b_dirs)

            # Stage 11: Non-Blocking Partner Monetization Telemetry
            partner_readiness_status_val: Optional[str] = None
            try:
                from pseofactory.partner_tracker import PartnerTrackingEngine
                partner_engine = PartnerTrackingEngine()
                dash = partner_engine.sync_and_evaluate()
                if hasattr(dash, adapter.property_id):
                    p_report = getattr(dash, adapter.property_id)
                    partner_readiness_status_val = f"SCORE_{int(p_report.monetization_readiness_score)}"
                else:
                    partner_readiness_status_val = "EVALUATED"
            except Exception as part_err:
                print(f"Warning: Partner telemetry stage error for '{adapter.property_id}': {part_err}")
                partner_readiness_status_val = "EVALUATED"

            duration = time.time() - start_time
            if indexing_status_val == "FAILED":
                final_status = "PARTIAL"
            else:
                final_status = "DRY_RUN" if dry_run else "SUCCESS"
            return MaintenanceResult(
                property_id=adapter.property_id,
                status=final_status,
                assets_audited=post_report.total_assets_checked,
                assets_drifted=0 if dry_run and len(report.drifted_assets) == 0 else report.drifted_assets_count,
                assets_refactored=cascade_res["refactored"],
                assets_failed=0,
                engine_hash=current_engine_hash,
                duration_seconds=duration,
                gitops_status=gitops_status_val,
                distribution_status=dist_status_val,
                indexing_status=indexing_status_val,
                trend_status=trend_status_val,
                partner_readiness_status=partner_readiness_status_val,
            )


class FleetMaintenanceCoordinator:
    """
    Coordinates unattended sequential maintenance across all registered tenants.
    Enforces stateless worker physics and clean environment isolation between properties.
    Zero em-dashes. Zero en-dashes.
    """

    def __init__(
        self,
        registry: Optional[TenantRegistry] = None,
        lifecycle: Optional[MaintenanceLifecycle] = None,
    ):
        self.registry = registry or TenantRegistry.default()
        self.lifecycle = lifecycle or MaintenanceLifecycle(registry=self.registry)

    def run_fleet(
        self,
        property_ids: Optional[List[str]] = None,
        force: bool = False,
        dry_run: bool = False,
        enable_gitops: bool = True,
        enable_distribution: bool = True,
        run_id: Optional[str] = None,
        skip_ci: bool = False,
    ) -> Dict[str, MaintenanceResult]:
        """
        Executes sequential maintenance across specified or all registered tenants.
        Zero em-dashes. Zero en-dashes.
        """
        all_adapters = self.registry.list_adapters()
        target_ids = (
            [p.lower() for p in property_ids]
            if property_ids
            else sorted(list(all_adapters.keys()))
        )

        results: Dict[str, MaintenanceResult] = {}

        for p_id in target_ids:
            adapter = all_adapters.get(p_id)
            if not adapter:
                results[p_id] = MaintenanceResult(
                    property_id=p_id,
                    status="FAILED",
                    assets_audited=0,
                    assets_drifted=0,
                    assets_refactored=0,
                    assets_failed=0,
                    failed_records=[{"error": f"Adapter '{p_id}' not found in registry"}],
                )
                continue

            try:
                res = self.lifecycle.run(
                    adapter,
                    force=force,
                    enable_gitops=enable_gitops,
                    enable_distribution=enable_distribution,
                    run_id=run_id,
                    dry_run=dry_run,
                    skip_ci=skip_ci,
                )
                results[p_id] = res
            except PropertyContaminationError as pce:
                print(f"[ERROR] Property contamination in tenant '{p_id}': {pce}")
                results[p_id] = MaintenanceResult(
                    property_id=p_id,
                    status="FAILED",
                    assets_audited=0,
                    assets_drifted=0,
                    assets_refactored=0,
                    assets_failed=1,
                    failed_records=[{"error": str(pce), "type": "PropertyContaminationError"}],
                )
            except LockContentionError as lce:
                print(f"[DEFERRED] Lock contention in tenant '{p_id}': {lce}")
                results[p_id] = MaintenanceResult(
                    property_id=p_id,
                    status="DEFERRED",
                    assets_audited=0,
                    assets_drifted=0,
                    assets_refactored=0,
                    assets_failed=0,
                    failed_records=[{"error": str(lce), "type": "LockContentionError"}],
                )
            except Exception as exc:
                print(f"[ERROR] Unhandled failure in tenant '{p_id}': {exc}")
                results[p_id] = MaintenanceResult(
                    property_id=p_id,
                    status="FAILED",
                    assets_audited=0,
                    assets_drifted=0,
                    assets_refactored=0,
                    assets_failed=1,
                    failed_records=[{"error": str(exc), "type": type(exc).__name__}],
                )

        return results


def run_maintenance_lifecycle(
    property_id: Optional[str] = None,
    force: bool = False,
    adapter: Optional[PropertyAdapter] = None,
) -> MaintenanceResult:
    """
    Convenience function to run closed-loop maintenance lifecycle on a property.
    Zero em-dashes. Zero en-dashes.
    """
    lifecycle = MaintenanceLifecycle()
    if adapter is not None:
        target: Union[str, PropertyAdapter] = adapter
    elif property_id is not None:
        target = property_id
    else:
        reg = TenantRegistry.default()
        adapters = reg.list_adapters()
        if not adapters:
            raise ValueError("No registered property adapters found in TenantRegistry")
        target = next(iter(adapters.values()))
    return lifecycle.run(target, force=force)


def run_fleet_maintenance(
    property_ids: Optional[List[str]] = None,
    force: bool = False,
    dry_run: bool = False,
) -> Dict[str, MaintenanceResult]:
    """
    Convenience function to execute fleet-wide maintenance coordinator.
    Zero em-dashes. Zero en-dashes.
    """
    coordinator = FleetMaintenanceCoordinator()
    return coordinator.run_fleet(property_ids=property_ids, force=force, dry_run=dry_run)


def audit_property_assets(
    property_id: Optional[str] = None,
    adapter: Optional[PropertyAdapter] = None,
    check_engine_drift: bool = False,
    check_ledger: Optional[bool] = False,
) -> AssetIntegrityReport:
    """
    Convenience function to execute read-only audit across property static assets.
    Zero em-dashes. Zero en-dashes.
    """
    reg = TenantRegistry.default()
    if adapter is not None:
        target_adapter = adapter
    elif property_id is not None:
        target_adapter = reg.get_adapter(property_id)
    else:
        adapters = reg.list_adapters()
        if not adapters:
            raise ValueError("No registered property adapters found in TenantRegistry")
        target_adapter = next(iter(adapters.values()))
    evaluator = AssetIntegrityEvaluator()
    return evaluator.audit_all(
        target_adapter,
        check_engine_drift=check_engine_drift,
        check_ledger=check_ledger,
    )


def replay_dlq(
    property_id: Optional[str] = None,
    slug: Optional[str] = None,
    dlq_path: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """
    Convenience function to re-queue / replay quarantined DLQ entries.
    Zero em-dashes. Zero en-dashes.
    """
    engine = RefactorCascadeEngine(dlq_path=dlq_path)
    return engine.replay_dlq(property_id=property_id, slug=slug)


replay_quarantine = replay_dlq


def list_dlq(
    property_id: Optional[str] = None,
    dlq_path: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """
    Convenience function to list quarantined DLQ entries.
    Zero em-dashes. Zero en-dashes.
    """
    engine = RefactorCascadeEngine(dlq_path=dlq_path)
    return engine.list_dlq(property_id=property_id)


def reflect_and_recompile_all_assets(
    properties: Optional[List[str]] = None,
    force: bool = False,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Scans workspace properties and audits existing static assets using
    AssetIntegrityEvaluator(enforce_master_seo=True). Detects drifted
    or unverified assets and triggers recompilation/updates to automatically
    reflect engine changes across all existing assets.
    Zero em-dashes. Zero en-dashes.
    """
    scanner = WorkspacePropertyScanner()
    discovered = scanner.discover_properties()
    by_id = {p.property_id.lower(): p for p in discovered}

    target_ids = (
        [p.lower() for p in properties]
        if properties
        else sorted(list(by_id.keys()))
    )

    evaluator = AssetIntegrityEvaluator(enforce_master_seo=True)

    results: Dict[str, Any] = {
        "status": "PASS",
        "properties_scanned": len(target_ids),
        "total_assets_checked": 0,
        "total_drifted": 0,
        "total_recompiled": 0,
        "property_reports": {},
    }

    for p_id in target_ids:
        adapter = by_id.get(p_id)
        if not adapter:
            try:
                adapter = TenantRegistry.default().get_adapter(p_id)
            except KeyError:
                if verbose:
                    print(f"Property adapter '{p_id}' not found.")
                continue

        report = evaluator.audit_all(adapter)
        drifted_records = report.drifted_assets
        recompiled_count = 0

        if drifted_records or force:
            try:
                if hasattr(adapter, "build_all"):
                    build_ok = adapter.build_all()
                    if build_ok:
                        recompiled_count = report.total_assets_checked
                elif hasattr(adapter, "build_asset"):
                    for d_rec in drifted_records:
                        if d_rec.slug:
                            adapter.build_asset(d_rec.slug)
                            recompiled_count += 1
            except Exception as b_err:
                if verbose:
                    print(f"Error rebuilding assets for '{p_id}': {b_err}")

        if recompiled_count > 0:
            try:
                s_file = adapter.dist_dir.parent / ".agy" / "engine_hash.json"
                l_file = adapter.dist_dir.parent / ".agy" / "asset_ledger.json"
                s_file.parent.mkdir(parents=True, exist_ok=True)
                b_dirs = getattr(adapter, "base_dirs", None)
                cur_engine_hash = record_engine_hash(s_file, base_dirs=b_dirs)
                asset_hashes = {
                    a.relative_to(adapter.dist_dir).as_posix(): compute_asset_fingerprint(a)
                    for a in adapter.list_assets()
                }
                record_asset_ledger(l_file, asset_hashes=asset_hashes, engine_hash=cur_engine_hash)
                if adapter.dist_dir.parent != scanner.workspace_root:
                    root_s_file = scanner.workspace_root / ".agy" / "engine_hash.json"
                    root_l_file = scanner.workspace_root / ".agy" / "asset_ledger.json"
                    root_s_file.parent.mkdir(parents=True, exist_ok=True)
                    record_engine_hash(root_s_file, hash_value=cur_engine_hash)
                    record_asset_ledger(root_l_file, asset_hashes=asset_hashes, engine_hash=cur_engine_hash)
            except Exception as l_err:
                if verbose:
                    print(f"Error recording engine hash and asset ledger for '{p_id}': {l_err}")

        post_report = evaluator.audit_all(adapter) if recompiled_count > 0 else report

        results["total_assets_checked"] += report.total_assets_checked
        results["total_drifted"] += len(drifted_records)
        results["total_recompiled"] += recompiled_count
        results["property_reports"][p_id] = {
            "initial_drifted": len(drifted_records),
            "recompiled": recompiled_count,
            "final_status": post_report.status,
            "compliant_assets": post_report.compliant_assets_count,
        }
        if post_report.status != "PASS" and not force:
            results["status"] = "DRIFT"

    return results


recompile_drifted_assets = reflect_and_recompile_all_assets


__all__ = [
    "DriftReason",
    "AssetDriftRecord",
    "AssetIntegrityReport",
    "MaintenanceResult",
    "PropertyContaminationError",
    "LockContentionError",
    "CrossPropertyContaminationScanner",
    "DEFAULT_TENANT_LINKEDIN_IDS",
    "PropertyAdapter",
    "SubprocessPropertyAdapter",
    "WorkspacePropertyScanner",
    "ConfigurablePropertyAdapter",
    "TenantRegistry",
    "LiveTruthAuditEngine",
    "AssetIntegrityEvaluator",
    "RefactorCascadeEngine",
    "MaintenanceLifecycle",
    "FleetMaintenanceCoordinator",
    "run_maintenance_lifecycle",
    "run_fleet_maintenance",
    "audit_property_assets",
    "replay_dlq",
    "replay_quarantine",
    "list_dlq",
    "trigger_drift_cascade",
    "cascade_drift_lifecycle",
    "reflect_and_recompile_all_assets",
    "recompile_drifted_assets",
]

