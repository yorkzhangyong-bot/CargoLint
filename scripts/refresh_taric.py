"""Refresh the TARIC snapshot from the Swedish Customs full extract and publish it as a release (feature 013).

    python scripts/refresh_taric.py [--force] [--no-publish] [--repo OWNER/NAME]

The logic lives in rag/refresh_taric.py; this entry point only puts the repository root on sys.path.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag.refresh_taric import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
