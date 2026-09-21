"""저장된 결로 새 주제의 대본을 쓴다."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from . import style as style_mod
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
    reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """결 + 주제 → 대본 한 편."""
    topic = topic.strip()
    if not topic:
        raise ValueError("주제를 넣어주세요.")

    minutes = max(1, min(int(minutes or 5), 30))
    notes = extra_notes.strip()
    brief = reference_brief(reference)
    if brief:
        notes = (brief + "\n\n" + notes).strip()

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


def as_production_order(
    script: dict[str, Any],
    dna: dict[str, Any],
    style: dict[str, Any] | None = None,
) -> dict[str, Any]:
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

    look = style_mod.normalize(style)
    return {
        "title": (script.get("title_candidates") or [script.get("topic", "")])[0],
        "topic": script.get("topic", ""),
        "aspect_ratio": look["aspect_ratio"],
        "total_seconds": script.get("total_seconds", 0),
        "style_note": style_tail,
        "voice_note": f"{narration.get('pace', '')} / {narration.get('pause_rule', '')}".strip(" /"),
        "bgm_note": narration.get("bgm", ""),
        "caption_style": look["caption"],
        "title_style": look["title"],
        # 영상은 그대로 두고 자막만 다시 구울 때 쓴다
        "caption_ass_style": style_mod.to_ass_style(look, "caption"),
        "shots": shots,
    }


# ------------------------------------------------- 레퍼런스 모양대로 새 타임라인

def reference_brief(reference: dict[str, Any] | None) -> str:
    """레퍼런스 타임라인에서 뽑은 '모양' 을 작가에게 넘길 글로."""
    if not reference:
        return ""
    o = reference.get("overall") or {}
    shots = reference.get("shots") or []
    chars = (reference.get("cues") or {}).get("character") or []
    lines = [
        "[레퍼런스 영상의 모양 — 이 모양을 따라라]",
        f"- 장면 수 {o.get('shot_count', len(shots))}컷, 한 장면 평균 {o.get('avg_shot_seconds', 0)}초",
        f"- 말을 멈추고 침묵하는 구간 {o.get('silence_count', 0)}번, 음악만 흐르는 구간 {o.get('music_only_count', 0)}번",
    ]
    if o.get("visual_dna"):
        lines.append(f"- 화면 결(영어, 모든 image_prompt 끝에 붙일 것): {o['visual_dna']}")
    if o.get("character_pattern") and o["character_pattern"] != "없음":
        lines.append(f"- 캐릭터 등장 규칙: {o['character_pattern']} (총 {len(chars)}번 등장)")
    if o.get("caption_style_note"):
        lines.append(f"- 자막: {o['caption_style_note']}")
    for r in o.get("shot_rules") or []:
        lines.append(f"- 화면 규칙: {r}")
    return "\n".join(lines)


def mirror_cues(reference: dict[str, Any], tl: dict[str, Any]) -> dict[str, Any]:
    """레퍼런스의 캐릭터·침묵·음악 타이밍을 새 타임라인 길이에 맞춰 비례로 옮긴다.

    3분짜리 레퍼런스에서 40초에 캐릭터가 떴으면, 5분짜리 새 영상에선 1분 7초쯤 뜬다.
    """
    ref_total = float(reference.get("total_seconds") or 0)
    new_total = float(tl.get("total_seconds") or 0)
    if not ref_total or not new_total:
        return tl
    k = new_total / ref_total

    out = deepcopy(tl)
    for key in ("character", "ambient", "bgm"):
        if out["cues"].get(key):
            continue  # 이미 채워져 있으면 손대지 않는다
        for c in (reference.get("cues") or {}).get(key) or []:
            out["cues"][key].append({
                **c,
                "start": round(c["start"] * k, 2),
                "seconds": round(max(0.5, c["seconds"] * k), 2),
                "asset": "",
                "note": c.get("note") or ("레퍼런스 자리 따라 옮김" if key == "character" else ""),
            })
    return out
