"""Refresh the EBTI rulings from the full extract and publish the store as a release (feature 013).

    python scripts/refresh_ebti.py [--rulings N|all] [--out DIR] [--previous RELEASE|DIR] [--full-embed]
                                   [--extract ZIP] [--force] [--no-publish] [--repo OWNER/NAME]

The logic lives in rag/refresh_ebti.py; this entry point only puts the repository root on sys.path.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag.refresh_ebti import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
