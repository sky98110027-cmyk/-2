"""한 줄 명령을 알아듣는다.

형님은 버튼을 찾아 누르는 대신 그냥 말한다.
"이 링크 결 좀 뽑아줘", "홍범도로 5분짜리", "자막 노랗게".
그 말을 어느 일로 보낼지 여기서 가른다.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .llm import structured
from .schemas import INTENT_SCHEMA

ROUTER_SYSTEM = """\
당신은 영상 제작 도구의 접수창구다.
제작자가 한 줄로 말하면 그것이 어느 일인지 가려서 넘긴다.

할 수 있는 일은 여섯 가지다.

- analyze : 영상 링크를 주면서 결을 뽑아달라고 할 때.
            링크만 덜렁 붙여넣어도 이걸로 본다.
- save_skill : 방금 뽑은 결을 저장하라고 할 때.
- list_skills : 저장해 둔 결이 뭐가 있는지 물을 때.
- produce : 주제를 주면서 대본이나 영상을 만들어 달라고 할 때.
- revise : 이미 만든 것을 고쳐달라고 할 때.
           자막 글꼴, 색, 위치, 크기, 화면 비율, 나레이션 손보기가 다 여기다.
- ask : 이 도구를 어떻게 쓰는지 물을 때. 무엇이든 물음이면 여기다.
        "이거 어떻게 써", "자막 색도 바꿀 수 있어?", "쇼츠도 되나",
        "결이 뭐야", "왜 안 되지" 같은 것이 전부 여기다.
        일을 시키는 말이 아니라 묻는 말이면 ask 로 보내라.
- ready : 영상을 만들려면 무엇이 더 있어야 하는지 물을 때.
          "영상 만들고 싶어", "뭐가 더 있어야 돼", "준비 다 됐나",
          "힉스필드 붙여야 하나" 같은 것이 여기다.
- help : 할 수 있는 일 목록을 통째로 보여달라고 할 때만.

가릴 수 없으면 unclear 로 두고, reply 에 무엇을 더 알려달라고 되물어라.
지어내서 아무 일이나 시키지 마라.

가리는 요령:

- 말 안에 http 로 시작하는 주소가 있으면 거의 analyze 다.
  단 "저장해줘", "고쳐줘" 처럼 다른 뜻이 분명하면 그쪽을 따른다.
- "쇼츠", "1분짜리" 처럼 길이를 말하면 minutes 에 숫자로 담아라.
  말 안 했으면 0 으로 둬라.
- 폴더 이름을 지어주면 folder 에 담아라.
  "오늘 폴더는 독립군 3부작으로 하고" 는 folder 가 "독립군 3부작" 이다.
  안 지었으면 빈 문자열로 둬라.
- 주제를 한꺼번에 여러 개 대면 topics 에 전부 담아라.
  "홍범도, 김좌진, 안중근 세 개 써줘" 는 topics 가 세 개다.
  하나만 말했으면 하나만 담는다.
- 결 이름을 대면 skill_hint 에 그대로 담아라. 이름 일부여도 된다.
- revise 일 때는 제작자가 한 말을 instruction 에 통째로 옮겨라.
  줄여 쓰지 마라. 뒷일이 그 문장을 그대로 읽는다.

reply 는 한국어로 짧게 쓴다. 한두 문장이면 된다.
할 일을 보고하듯이 담담하게 쓴다. 들뜨게 쓰지 마라.
"""

ROUTER_USER = """\
[지금 상태]

{state}

[제작자가 한 말]

{text}
"""

_URL = re.compile(r"https?://\S+")


def _state_text(state: dict[str, Any]) -> str:
    lines = []
    lines.append(
        f"- 방금 뽑아둔 결: {state.get('pending_skill') or '없음'}"
        + (" (아직 저장 안 함)" if state.get("pending_skill") else "")
    )
    lines.append(f"- 저장된 결: {', '.join(state.get('skills') or []) or '없음'}")
    lines.append(f"- 지금 열려 있는 작업: {state.get('project') or '없음'}")
    return "\n".join(lines)


def route(text: str, state: dict[str, Any] | None = None) -> dict[str, Any]:
    """말 한 줄 → 어느 일로 보낼지와 딸린 값들."""
    text = text.strip()
    if not text:
        raise ValueError("무엇을 할지 적어주세요.")

    intent = structured(
        system=ROUTER_SYSTEM,
        user=ROUTER_USER.format(state=_state_text(state or {}), text=text),
        schema=INTENT_SCHEMA,
        max_tokens=2000,
        effort="low",
    )

    # 모델이 주소를 흘렸으면 원문에서 주워 담는다
    if intent.get("action") == "analyze" and not intent.get("url"):
        found = _URL.search(text)
        if found:
            intent["url"] = found.group(0)

    # 고치기는 원문을 그대로 넘겨야 뒤에서 제대로 읽는다
    if intent.get("action") == "revise" and not intent.get("instruction"):
        intent["instruction"] = text

    return intent


def pick_skill(hint: str, skills: list[dict[str, Any]]) -> dict[str, Any] | None:
    """이름 조각으로 결을 찾는다. 못 찾으면 가장 최근 것을 쓴다."""
    if not skills:
        return None

    hint = (hint or "").strip()
    if not hint:
        return skills[0]

    for skill in skills:
        if hint == skill.get("slug"):
            return skill
    for skill in skills:
        if hint in str(skill.get("name", "")):
            return skill
    for skill in skills:
        if str(skill.get("name", "")) in hint:
            return skill
    return skills[0]


HELP_TEXT = """\
이렇게 말씀하시면 됩니다.

■ 결 뽑기
  영상 주소를 붙여넣으세요. 그것만으로 됩니다.
  화면 얘기를 곁들이셔도 됩니다.
  예) https://youtu.be/... 이 영상 결 뽑아줘. 화면은 세피아 톤이고 자막은 아래 한 줄이야

■ 저장
  예) 이 결 저장해줘

■ 목록
  예) 내 결 뭐뭐 있어

■ 대본 만들기
  예) 담담한 증언체로 김좌진과 청산리 8분짜리 써줘
  예) 홍범도로 쇼츠 하나

■ 한 번에 여러 개
  주제를 쉼표로 나열하시면 동시에 돌아갑니다.
  예) 홍범도, 김좌진, 안중근 세 개 한 번에 써줘

■ 폴더 이름 직접 짓기
  예) 오늘 폴더는 독립군 3부작으로 하고 홍범도, 김좌진 두 개 써줘

■ 받아둔 파일 넣기
  화면 아래 파일 넣는 칸에 끌어다 놓으시면 됩니다.
  대본(.txt), 자막(.srt .vtt), 자막이 박힌 영상 파일을 받습니다.

■ 고치기
  예) 자막 더 크게 하고 노란색으로
  예) 자막을 화면 가운데로 올려줘
  예) 3번 장면 나레이션이 기니까 줄여줘
  예) 세로 쇼츠 비율로 바꿔줘

자막 글꼴과 색과 위치는 영상을 다시 안 뽑아도 됩니다.
그림 자체가 바뀌는 것만 다시 뽑으면 되고, 그때는 몇 컷인지 먼저 알려드립니다.
"""
