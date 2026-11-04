"""Paths, the clock the rules use, and which AWS calls are allowed."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
CONFIG_DIR = BACKEND_DIR / "config"
SAMPLE_DIR = REPO_ROOT / "Sample Data"
SYNTHETIC_DIR = REPO_ROOT / "data" / "synthetic"
RUNTIME_DIR = REPO_ROOT / "data" / "runtime"
INDEX_DIR = REPO_ROOT / "data" / "index"

# Fixed clock so age rules and the eval stay repeatable. Override with GS_TODAY.
TODAY = date.fromisoformat(os.environ.get("GS_TODAY", "2026-11-03"))
FRESH_MONTHS = 18
REVIEW_FULL_WEIGHT_YEARS = 5

BEDROCK_ENABLED = os.environ.get("BEDROCK_ENABLED", "").lower() in {"1", "true", "yes"}
# Amazon Translate reads the parent's message in any language and hands the pipeline English.
TRANSLATE_ENABLED = os.environ.get("TRANSLATE_ENABLED", "").lower() in {"1", "true", "yes"}
OPENSEARCH_URL = os.environ.get("OPENSEARCH_URL", "").strip()
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
