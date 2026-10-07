"""
pseofactory package execution gateway.
Delegates directly to pseofactory.cli:main.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

import sys
from pseofactory.cli import main

if __name__ == "__main__":
    sys.exit(main())
