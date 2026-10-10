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
