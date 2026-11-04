"""`python -m northcel` — the same entry point as the `northcel` command."""

from __future__ import annotations

import sys

from .launcher.cli import main

if __name__ == "__main__":
    sys.exit(main())
