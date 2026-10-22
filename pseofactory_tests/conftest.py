"""
Pytest configuration for pseofactory test suite.
Ensures current worktree codebase takes precedence over editable parent installations.
Zero em-dashes. Zero en-dashes.
"""

import sys
from pathlib import Path

worktree_root = Path(__file__).resolve().parent.parent

# Filter out parent repo paths and editable hooks to ensure worktree isolation
sys.path = [
    p for p in sys.path
    if "projects/pseofactory" not in p and "__editable__.pseofactory" not in p
]
sys.path_hooks = [h for h in sys.path_hooks if "pseofactory" not in str(h)]
sys.path_importer_cache.clear()

if str(worktree_root) not in sys.path:
    sys.path.insert(0, str(worktree_root))


def pytest_sessionfinish(session, exitstatus):
    import os
    import shutil

    pid = os.getpid()
    tmp_root = Path("/tmp")
    for pattern in (f"pseofactory_pytest_*_{pid}*", f"pseofactory_test_syndication_*_{pid}*"):
        for item in list(tmp_root.glob(pattern)):
            try:
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)
            except OSError:
                pass

