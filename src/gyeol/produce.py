"""저장된 결로 새 주제의 대본을 쓴다."""

from __future__ import annotations

import json
from typing import Any

from .config import DEFAULT_AUDIENCE
from .llm import structured
from .prompts import WRITER_EXTRA_HEADER, WRITER_SYSTEM, WRITER_USER
from .schemas import SCRIPT_SCHEMA


def write_script(
    dna: dict[str, Any],
    topic: str,
    *,
    minutes: int = 5,
    extra_notes: str = "",
    audience: str = DEFAULT_AUDIENCE,
) -> dict[str, Any]:
    """결 + 주제 → 대본 한 편."""
    topic = topic.strip()
    if not topic:
        raise ValueError("주제를 넣어주세요.")

    minutes = max(1, min(int(minutes or 5), 30))
    notes = extra_notes.strip()

    user = WRITER_USER.format(
        dna=json.dumps(dna, ensure_ascii=False, indent=2),
        topic=topic,
        minutes=minutes,
        audience=audience.strip() or DEFAULT_AUDIENCE,
        extra=WRITER_EXTRA_HEADER.format(notes=notes) if notes else "",
    )
    script = structured(
        system=WRITER_SYSTEM,
        user=user,
        schema=SCRIPT_SCHEMA,
        max_tokens=32000,
        effort="high",
    )
    script.setdefault("topic", topic)
    return script


def as_production_order(script: dict[str, Any], dna: dict[str, Any]) -> dict[str, Any]:
    """영상 생성 도구에 그대로 넘길 제작 지시서.

    힉스필드든 톱뷰든, 장면별 프롬프트만 있으면 붙는다.
    """
    visual = dna.get("visual") or {}
    narration = dna.get("narration") or {}
    style_tail = str(visual.get("mood") or "").strip()

    shots = []
    for scene in script.get("scenes") or []:
        image_prompt = str(scene.get("image_prompt") or "").strip()
        if style_tail and style_tail.lower() not in image_prompt.lower():
            image_prompt = f"{image_prompt}. Overall look: {style_tail}"
        shots.append(
            {
                "no": scene.get("no"),
                "seconds": scene.get("seconds"),
                "narration_ko": scene.get("narration", ""),
                "caption_ko": scene.get("caption", ""),
                "image_prompt": image_prompt,
                "video_prompt": str(scene.get("video_prompt") or "").strip(),
                "bgm": scene.get("bgm", ""),
            }
        )

    return {
        "title": (script.get("title_candidates") or [script.get("topic", "")])[0],
        "topic": script.get("topic", ""),
        "aspect_ratio": "16:9",
        "total_seconds": script.get("total_seconds", 0),
        "style_note": style_tail,
        "voice_note": f"{narration.get('pace', '')} / {narration.get('pause_rule', '')}".strip(" /"),
        "bgm_note": narration.get("bgm", ""),
        "shots": shots,
    }
