"""스타일 DNA를 클로드 스킬 파일로 굽는다.

여기서 나온 SKILL.md는 이 앱 밖에서도 쓸 수 있다.
클로드 코드나 클로드 데스크톱에 넣어두면
"그 결로 만들어줘" 한마디에 바로 붙는다.
"""

from __future__ import annotations

from typing import Any


def _bullets(items: Any, indent: str = "- ") -> str:
    if not items:
        return f"{indent}(없음)"
    return "\n".join(f"{indent}{str(x).strip()}" for x in items if str(x).strip())


def _beats(beats: Any) -> str:
    if not beats:
        return "- (없음)"
    lines = []
    for i, beat in enumerate(beats, 1):
        name = beat.get("name", f"{i}구간")
        share = beat.get("share", "")
        does = beat.get("does", "")
        lines.append(f"{i}. **{name}** ({share})\n   {does}")
    return "\n".join(lines)


def _yaml_scalar(text: str) -> str:
    """YAML 큰따옴표 스칼라로 안전하게 감싼다.

    설명에 따옴표나 콜론이 섞여 들어와도 머리말이 깨지면 안 된다.
    """
    text = " ".join(str(text).split())
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _description(dna: dict[str, Any], slug: str) -> str:
    """스킬이 언제 불려나올지를 정하는 한 줄. 이게 정확해야 자동으로 붙는다."""
    name = str(dna.get("title") or "결").strip()
    one_line = str(dna.get("one_line") or "").strip()
    return (
        f"{name} 결로 유튜브 영상 대본과 장면을 만든다. {one_line} "
        f"사용자가 이 결, {name}, {slug} 를 지목하거나 "
        f"이 채널 스타일로 영상·대본·쇼츠를 만들어 달라고 할 때 쓴다."
    )


def build_skill_md(dna: dict[str, Any], slug: str, source_url: str = "") -> str:
    """스타일 DNA 하나를 SKILL.md 한 장으로 편다."""
    voice = dna.get("voice") or {}
    structure = dna.get("structure") or {}
    emotion = dna.get("emotion") or {}
    visual = dna.get("visual") or {}
    narration = dna.get("narration") or {}

    origin = f"\n원본: {source_url}\n" if source_url else "\n"

    return f"""---
name: {slug}
description: {_yaml_scalar(_description(dna, slug))}
---

# {dna.get("title", "이름 없는 결")}

{dna.get("one_line", "")}
{origin}
이 문서는 영상 한 편을 해부해서 뽑아낸 결이다.
주제가 무엇이든 아래 규칙대로 쓴다.
주제는 바뀌어도 결은 바뀌지 않는다.

## 누구에게 말하는가

{dna.get("audience", "")}

## 말투

- **화자** : {voice.get("person", "")}
- **온도** : {voice.get("tone", "")}
- **종결어미** : {voice.get("speech_level", "")}
- **문장 규칙** : {voice.get("sentence_rule", "")}

반복해서 쓰는 표현:

{_bullets(voice.get("signature_phrases"))}

## 구성

**도입 15초**
{structure.get("hook", "")}

**전체 흐름**

{_beats(structure.get("beats"))}

**마무리**
{structure.get("ending", "")}

## 감정

- **감정선** : {emotion.get("curve", "")}
- **정점** : {emotion.get("peak", "")}

감정을 올리는 장치:

{_bullets(emotion.get("devices"))}

## 화면

- **분위기** : {visual.get("mood", "")}
- **자막** : {visual.get("caption_rule", "")}

화면 구성 규칙:

{_bullets(visual.get("shot_rules"))}

## 소리

- **말 속도** : {narration.get("pace", "")}
- **쉬는 자리** : {narration.get("pause_rule", "")}
- **배경음** : {narration.get("bgm", "")}

## 제목 만드는 공식

{_bullets(dna.get("title_pattern"))}

## 이 결에서 하지 않는 것

{_bullets(dna.get("forbidden"))}

## 내보내기 전 점검표

{_bullets(dna.get("checklist"), indent="- [ ] ")}

---

## 작업 순서

주제를 하나 받으면 이렇게 한다.

### 1. 대본을 쓴다

위 규칙 그대로 나레이션 원고를 쓴다.
설명문이 아니라 성우가 바로 읽을 완성된 문장으로 쓴다.
한 문장이 끝나면 줄을 바꾼다.

장면은 나레이션 한 덩어리에 그림 한 장이다.
한 장면은 8초에서 20초 사이로 잡는다.

역사적 사실을 다룰 때 연도나 지명이 확실하지 않으면
단정하지 말고 표현을 넓힌다.
확인이 필요한 대목은 따로 표시해서 알린다.

### 2. 장면마다 생성 프롬프트를 붙인다

각 장면에 영문 이미지 프롬프트와 영상 프롬프트를 단다.
**위 '화면' 항목의 분위기를 모든 프롬프트에 똑같이 반복해서 박는다.**
그래야 장면끼리 톤이 안 튄다.

### 3. 영상 생성 도구가 붙어 있으면 바로 만든다

이미지나 영상 생성 MCP가 연결되어 있으면
장면 프롬프트를 그대로 넘겨서 소재를 뽑는다.
연결된 도구가 없으면 프롬프트만 정리해서 내놓고
어디에 붙여넣으면 되는지 알려준다.

도구를 부르기 전에 몇 장을 만들지, 얼마가 드는지 먼저 말하고 확인을 받는다.

### 4. 점검표로 대조한다

위 점검표를 하나씩 확인한다.
못 지킨 항목이 있으면 숨기지 말고 말한다.
"""
