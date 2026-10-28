"""Settings and named constants.

Caps, thresholds and model options are named here so that guardrails are enforced by
configuration constants, never by prompt text (constitution Principles I and II).
"""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
STORE_DIR = ROOT / "store"
RULES_DIR = DATA_DIR / "rules"

# Input caps (FR-001, FR-002, FR-006)
MAX_FILE_BYTES = 20_971_520          # 20 MB
MAX_LINES = 200                      # lines per shipment
MAX_DESC_CHARS = 300                 # characters per description (truncated beyond)
MAX_PASTED_LINES = 50                # lines per pasted chat message
SUPPORTED_FILE_KINDS = ("xlsx", "csv", "pdf", "jpg", "jpeg", "png")

# Routing (FR-020, FR-021)
DEFAULT_THRESHOLD = 85              # auto-accept at either layer, only when no eligible ruling votes (feature 006)
THRESHOLD_MIN = 60
THRESHOLD_MAX = 99
ASK_FLOOR = 50

# CN-8 gate (feature 006, constitution 1.4.0): the vote of the nearest eligible EBTI rulings, each counted once. It is
# unweighted by design: the product is not tied to one entry country.
CN8_VOTE_K = 5                     # the nearest eligible rulings that vote
CN8_VOTE_SHARE = 0.5               # the majority's share the model's CN-8 needs; exactly the share passes

# HS-6 gate (feature 006): the same vote on the first six digits of the nearest eligible rulings. A ruling less similar
# to the line than the floor (cosine similarity, 1 - distance) does not vote; with none left, no ruling votes.
HS6_VOTE_K = 5                     # the nearest eligible rulings that vote
HS6_VOTE_SHARE = 0.5               # the majority's share the model's top HS-6 needs; exactly the share passes
HS6_VOTE_MIN_SIMILARITY = 0.40     # below every nearest eligible ruling in the HS-6 eval set (lowest 0.436)
OVERRIDE_MIN = 5                   # feature 008: the rulings at the model's candidate 2 or 3 that override its top HS-6;
                                   # 1 ≤ OVERRIDE_MIN ≤ HS6_VOTE_K. 5 of 5 since the evals (T027): at 4, 3 more wrong
                                   # auto-accepts on the HS-6 eval

# Agent and model behaviour (FR-044, FR-049)
MAX_SCHEMA_RETRIES = 2
MAX_TOOL_CALLS = 8
PER_LINE_TIMEOUT_S = 60
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Retrieval
RETRIEVAL_K = 6
RRF_K = 60

# TARIC snapshot (feature 002): digits 9-10 and measures, never embedded or indexed
TARIC_RAW_DIR = DATA_DIR / "raw" / "taric"
TARIC_SNAPSHOT = DATA_DIR / "taric.jsonl"
TARIC_KEY = DATA_DIR / "Tulltaxan_Fildistribution.asc"
TARIC_KEY_FINGERPRINT = "410160CE25CEC2FF322784E7302AC3C1D0E3E1C9"   # Swedish Customs "Taric Fildistribution" key
TARIC_OBJECTS = ("GoodsNomenclature", "Measure", "MeasureType", "GeographicalArea", "DutyExpression", "Regulation")
TARIC_SCHEMA = 2
TARIC_LOG_DIR = STORE_DIR / "logs"
GPG_ENV = "CARGOLINT_GPG"            # optional full path to gpg


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    http_referer: str | None
    app_title: str
    chat_model: str
    embed_model: str
    structured_method: str
    usd_eur: float
    workers: int
    ocr_min_score: float
    reasoning_off: bool = True   # feature 006: send OpenRouter's reasoning {"enabled": false}; a model without the
                                 # parameter needs False (CARGOLINT_REASONING other than "off"), as OpenRouter refuses it
    hs6_override: bool = True    # feature 008: the precedent override at the HS-6, on since the evals (T027);
                                 # CARGOLINT_HS6_OVERRIDE "off" or "false" turns it off
    query_expansion: bool = False   # feature 009: CARGOLINT_QUERY_EXPANSION "on" adds the model's English queries to
                                    # every line's raw text (rag/translate.py)
    app_password: str = field(default="", repr=False)   # feature 011: CARGOLINT_APP_PASSWORD; empty: no password gate
    demo_store_url: str = ""        # feature 011: CARGOLINT_DEMO_STORE_URL, the demo store's archive, fetched when the
                                    # store is missing; empty: never fetched (rag/demo_store.py)
    demo_store_sha256: str = ""     # feature 011: CARGOLINT_DEMO_STORE_SHA256, the archive's checksum, checked before
                                    # anything is unpacked
    demo_notice: bool = False       # feature 011: CARGOLINT_DEMO_NOTICE "on" shows the "Before you upload" notice

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)


def load_settings(env: dict | None = None) -> Settings:
    """Read settings from the environment (a `.env` at the repo root is loaded if present)."""
    load_dotenv(ROOT / ".env", override=False)
    e = env if env is not None else os.environ
    expansion = (e.get("CARGOLINT_QUERY_EXPANSION") or "off").strip().lower()
    if expansion not in ("on", "off"):
        raise ValueError(f"CARGOLINT_QUERY_EXPANSION must be on or off, not {expansion!r}")
    return Settings(
        api_key=e.get("OPENROUTER_API_KEY") or None,
        http_referer=e.get("OPENROUTER_HTTP_REFERER") or None,
        app_title=e.get("OPENROUTER_APP_TITLE") or "CargoLint",
        chat_model=e.get("CARGOLINT_CHAT_MODEL") or "google/gemini-2.5-flash",
        embed_model=e.get("CARGOLINT_EMBED_MODEL") or "qwen/qwen3-embedding-8b",
        structured_method=e.get("CARGOLINT_STRUCTURED_METHOD") or "json_schema",
        usd_eur=float(e.get("CARGOLINT_USD_EUR") or 0.92),
        workers=int(e.get("CARGOLINT_WORKERS") or 6),
        ocr_min_score=float(e.get("CARGOLINT_OCR_MIN_SCORE") or 0.6),
        reasoning_off=(e.get("CARGOLINT_REASONING") or "off") == "off",
        hs6_override=(e.get("CARGOLINT_HS6_OVERRIDE") or "on").strip().lower() not in ("off", "false"),
        query_expansion=expansion == "on",
        app_password=e.get("CARGOLINT_APP_PASSWORD") or "",
        demo_store_url=(e.get("CARGOLINT_DEMO_STORE_URL") or "").strip(),
        demo_store_sha256=(e.get("CARGOLINT_DEMO_STORE_SHA256") or "").strip().lower(),
        demo_notice=(e.get("CARGOLINT_DEMO_NOTICE") or "off").strip().lower() == "on",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def configure_logging(level: int = logging.INFO) -> None:
    """Plain stderr logging. Handlers never receive description or reply text (FR-046)."""
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(handler)
    root.setLevel(level)
