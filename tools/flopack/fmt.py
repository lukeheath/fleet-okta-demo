"""Canonical text form for .flopack files so PR diffs are readable."""
from __future__ import annotations

import json


def format_text(doc: dict) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def is_formatted(text: str) -> bool:
    return text == format_text(json.loads(text))
