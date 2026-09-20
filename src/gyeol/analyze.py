"""영상 재료에서 결을 뽑아낸다."""

from __future__ import annotations

from typing import Any

from .config import DEFAULT_AUDIENCE
from .llm import structured
from .prompts import ANALYST_SYSTEM, ANALYST_USER, EXTRA_NOTES_HEADER
from .schemas import STYLE_DNA_SCHEMA
from .source import SourceMaterial


def analyze(
    material: SourceMaterial,
    *,
    extra_notes: str = "",
    audience: str = DEFAULT_AUDIENCE,
) -> dict[str, Any]:
    """재료 한 덩어리 → 스타일 DNA."""
    notes = extra_notes.strip()
    user = ANALYST_USER.format(
        material=material.brief(),
        extra_notes=EXTRA_NOTES_HEADER.format(notes=notes) if notes else "",
        audience=audience.strip() or DEFAULT_AUDIENCE,
    )
    return structured(
        system=ANALYST_SYSTEM,
        user=user,
        schema=STYLE_DNA_SCHEMA,
        max_tokens=16000,
        effort="high",
    )
