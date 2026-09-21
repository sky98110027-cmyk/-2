"""만들어진 결과물을 말로 고친다.

"자막 더 크게", "노란색으로", "아래로 내려줘", "3번 장면 말이 기네".
이런 말을 받아서 바꿀 것만 집어낸다.

모델에게 대본을 통째로 다시 쓰게 하지 않는다.
바꿀 자리만 받아서 여기서 갈아끼운다.
그래야 안 건드린 부분이 흔들리지 않는다.
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from . import style as style_mod
from .llm import structured
from .schemas import REVISE_SCHEMA

REVISER_SYSTEM = """\
당신은 영상 편집자다. 제작자가 말로 고쳐달라고 하면 그대로 고친다.

고칠 수 있는 것은 두 갈래다.

1. 꾸밈새 (style)
   자막 글꼴, 글자 크기, 색, 외곽선, 위치, 배경, 화면 비율.
   이건 영상을 다시 안 뽑아도 된다. 값만 바꾸면 된다.
   요청과 상관없는 값은 **받은 그대로 되돌려 놓아라.** 멋대로 바꾸지 마라.

2. 글자 (scene_changes)
   나레이션 원고, 화면 자막, 장면 길이, 이미지 프롬프트, 영상 프롬프트, 배경음 지시.
   고칠 장면만 골라서 담아라. 안 고칠 장면은 넣지 마라.

지킬 것:

- 색은 반드시 #RRGGBB 여섯 자리로 적어라. '노랑' 같은 말로 적지 마라.
- 크기는 1920x1080 화면 기준 픽셀이다.
- 나레이션을 고칠 때도 원래 결의 말투와 종결어미는 그대로 지켜라.
  말투가 바뀌면 결이 깨진다.
- 이미지 프롬프트를 고치면 그 장면은 그림을 다시 뽑아야 한다.
  그런 장면 번호는 regenerate_scenes 에 꼭 담아라.
  글자만 고쳤으면 빈 목록으로 둬라.
- 알아듣지 못한 요청이 있으면 지어내지 말고 note 에 적어라.
- done 에는 실제로 바꾼 것만 적어라. 안 바꾼 걸 바꿨다고 적지 마라.

모든 설명은 한국어로 쓴다.
단, image_prompt 와 video_prompt 의 내용은 영어로 쓴다.
"""

REVISER_USER = """\
[지금 꾸밈새]

{style}

[지금 대본]

{script}

[제작자 요청]

{instruction}

요청대로 고쳐라.
"""

_TEXT_FIELDS = {"narration", "caption", "image_prompt", "video_prompt", "bgm"}


def _script_digest(script: dict[str, Any]) -> str:
    """모델에게 보여줄 대본 요약. 프롬프트까지 다 넣으면 너무 길어진다."""
    lines = [f"주제: {script.get('topic', '')}"]
    for scene in script.get("scenes") or []:
        lines.append(
            f"\n[{scene.get('no')}번 · {scene.get('beat', '')} · {scene.get('seconds', 0)}초]"
            f"\n나레이션: {scene.get('narration', '')}"
            f"\n자막: {scene.get('caption', '')}"
            f"\n그림: {scene.get('image_prompt', '')}"
            f"\n움직임: {scene.get('video_prompt', '')}"
            f"\n소리: {scene.get('bgm', '')}"
        )
    return "\n".join(lines)


def apply_changes(
    script: dict[str, Any], changes: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[str]]:
    """모델이 집어준 자리만 갈아끼운다. 나머지는 손대지 않는다."""
    updated = deepcopy(script)
    scenes = {s.get("no"): s for s in updated.get("scenes") or []}
    applied: list[str] = []

    for change in changes or []:
        no = change.get("no")
        field = change.get("field")
        value = change.get("new_value")
        scene = scenes.get(no)

        if scene is None or field is None or value is None:
            continue

        if field == "seconds":
            try:
                scene["seconds"] = max(1, min(int(str(value).strip()), 600))
            except ValueError:
                continue
            applied.append(f"{no}번 장면 길이 → {scene['seconds']}초")
        elif field in _TEXT_FIELDS:
            scene[field] = str(value)
            applied.append(f"{no}번 장면 {_KOREAN[field]} 고침")

    if applied:
        updated["total_seconds"] = sum(
            int(s.get("seconds") or 0) for s in updated.get("scenes") or []
        )
    return updated, applied


_KOREAN = {
    "narration": "나레이션",
    "caption": "자막",
    "image_prompt": "그림 지시",
    "video_prompt": "움직임 지시",
    "bgm": "배경음",
}


def revise(
    script: dict[str, Any],
    current_style: dict[str, Any],
    instruction: str,
) -> dict[str, Any]:
    """요청 한 마디 → 바뀐 스타일과 바뀐 대본."""
    instruction = instruction.strip()
    if not instruction:
        raise ValueError("무엇을 고칠지 적어주세요.")

    current_style = style_mod.normalize(current_style)

    result = structured(
        system=REVISER_SYSTEM,
        user=REVISER_USER.format(
            style=json.dumps(current_style, ensure_ascii=False, indent=2),
            script=_script_digest(script),
            instruction=instruction,
        ),
        schema=REVISE_SCHEMA,
        max_tokens=16000,
        effort="medium",
    )

    new_style = style_mod.normalize(result.get("style"))
    new_script, applied = apply_changes(script, result.get("scene_changes"))

    # 그림을 다시 뽑아야 하는 장면은 실제로 그림 지시가 바뀐 것만 인정한다
    edited = {
        c.get("no")
        for c in (result.get("scene_changes") or [])
        if c.get("field") in ("image_prompt", "video_prompt")
    }
    regenerate = sorted(
        n for n in (result.get("regenerate_scenes") or []) if n in edited
    )

    return {
        "understood": result.get("understood", ""),
        "style": new_style,
        "style_changed": new_style != current_style,
        "script": new_script,
        "applied": applied,
        "done": result.get("done") or applied,
        "regenerate_scenes": regenerate,
        "note": result.get("note", ""),
    }
