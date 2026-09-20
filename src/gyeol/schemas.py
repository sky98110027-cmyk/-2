"""클로드에게 강제할 JSON 스키마.

structured outputs(`output_config.format`)에 그대로 넘긴다.
모든 속성은 required, additionalProperties는 False 여야 한다.
"""

from typing import Any


def _obj(properties: dict[str, Any]) -> dict[str, Any]:
    """모든 키를 required로 묶은 object 스키마."""
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _str_list(desc: str) -> dict[str, Any]:
    return {"type": "array", "items": {"type": "string"}, "description": desc}


# ---------------------------------------------------------------- 스타일 DNA

STYLE_DNA_SCHEMA = _obj(
    {
        "title": {
            "type": "string",
            "description": "이 결에 붙일 한국어 이름. 8자 이내. 예: 담담한 증언체",
        },
        "one_line": {
            "type": "string",
            "description": "이 영상의 결을 한 문장으로. 40자 이내",
        },
        "audience": {"type": "string", "description": "실제로 누구를 향해 말하고 있는지"},
        "voice": _obj(
            {
                "person": {"type": "string", "description": "인칭과 화자 위치"},
                "tone": {"type": "string", "description": "감정의 온도와 태도"},
                "speech_level": {
                    "type": "string",
                    "description": "종결어미 체계. 다까체/해요체/반말 등 실제 쓰인 것",
                },
                "sentence_rule": {
                    "type": "string",
                    "description": "문장 길이와 호흡 규칙. 평균 글자 수까지 구체적으로",
                },
                "signature_phrases": _str_list("원본에서 반복되는 표현이나 말버릇 3~7개"),
            }
        ),
        "structure": _obj(
            {
                "hook": {"type": "string", "description": "첫 15초에 무엇을 해서 붙잡는지"},
                "beats": {
                    "type": "array",
                    "description": "기승전결 등 실제 구간 구성. 3~6개",
                    "items": _obj(
                        {
                            "name": {"type": "string", "description": "구간 이름"},
                            "share": {"type": "string", "description": "전체 길이 대비 비중"},
                            "does": {"type": "string", "description": "이 구간이 하는 일"},
                        }
                    ),
                },
                "ending": {"type": "string", "description": "마무리에서 남기는 것"},
            }
        ),
        "emotion": _obj(
            {
                "curve": {"type": "string", "description": "감정선의 오르내림"},
                "peak": {"type": "string", "description": "가장 뜨거워지는 지점과 그 방식"},
                "devices": _str_list("감정을 올리는 장치. 침묵, 반복, 숫자 제시 등"),
            }
        ),
        "visual": _obj(
            {
                "mood": {"type": "string", "description": "화면 색감과 질감"},
                "shot_rules": _str_list("화면 구성 규칙 3~6개"),
                "caption_rule": {"type": "string", "description": "자막 처리 방식"},
            }
        ),
        "narration": _obj(
            {
                "pace": {"type": "string", "description": "말하기 속도"},
                "pause_rule": {"type": "string", "description": "쉬는 자리 규칙"},
                "bgm": {"type": "string", "description": "배경음 성격과 들어오는 타이밍"},
            }
        ),
        "title_pattern": _str_list("제목이 만들어지는 공식 2~4개"),
        "forbidden": _str_list("이 결에서는 절대 하지 않는 것 3~6개"),
        "checklist": _str_list("이 결로 만들었는지 확인하는 점검 항목 5~8개"),
    }
)


# ------------------------------------------------------------------- 대본

SCRIPT_SCHEMA = _obj(
    {
        "topic": {"type": "string", "description": "이번 영상의 주제"},
        "title_candidates": _str_list("제목 후보 5개. 결의 제목 공식을 따를 것"),
        "thumbnail_copy": _str_list("썸네일 문구 3개. 각 12자 이내"),
        "hook": {"type": "string", "description": "첫 15초 나레이션 원고 그대로"},
        "total_seconds": {"type": "integer", "description": "전체 예상 길이(초)"},
        "scenes": {
            "type": "array",
            "description": "장면 목록. 각 장면은 나레이션 한 덩어리와 그림 한 장",
            "items": _obj(
                {
                    "no": {"type": "integer", "description": "장면 번호. 1부터"},
                    "beat": {"type": "string", "description": "이 장면이 속한 구간 이름"},
                    "seconds": {"type": "integer", "description": "이 장면 길이(초)"},
                    "narration": {
                        "type": "string",
                        "description": "읽을 나레이션 원고. 결의 말투 그대로",
                    },
                    "caption": {"type": "string", "description": "화면에 박을 자막. 20자 이내"},
                    "image_prompt": {
                        "type": "string",
                        "description": "이미지 생성용 영문 프롬프트. 화풍과 구도까지 지정",
                    },
                    "video_prompt": {
                        "type": "string",
                        "description": "영상 생성용 영문 프롬프트. 카메라 움직임 위주",
                    },
                    "bgm": {"type": "string", "description": "이 장면의 배경음 지시"},
                }
            ),
        },
        "closing": {"type": "string", "description": "마지막 멘트 원고"},
        "description": {"type": "string", "description": "유튜브 설명란 초안"},
        "tags": _str_list("유튜브 태그 8~12개"),
        "self_check": _str_list("결 점검표를 하나씩 대조한 결과"),
    }
)


# ------------------------------------------------------------------- 고치기

_LAYER_SCHEMA = _obj(
    {
        "font": {"type": "string", "description": "글꼴 이름"},
        "size": {"type": "integer", "description": "글자 크기(px). 1920x1080 기준"},
        "bold": {"type": "boolean", "description": "굵게 여부"},
        "color": {"type": "string", "description": "글자 색. #RRGGBB 형식"},
        "outline_color": {"type": "string", "description": "외곽선 색. #RRGGBB 형식"},
        "outline": {"type": "integer", "description": "외곽선 두께(px). 0이면 없음"},
        "position": {
            "type": "string",
            "enum": ["top", "middle", "bottom"],
            "description": "세로 위치",
        },
        "offset": {"type": "integer", "description": "가장자리에서 띄울 거리(px)"},
        "background": {
            "type": "string",
            "enum": ["none", "band", "box"],
            "description": "글자 뒤 배경 처리",
        },
        "background_color": {"type": "string", "description": "배경 색. #RRGGBB 형식"},
        "background_opacity": {"type": "number", "description": "배경 투명도. 0에서 1 사이"},
        "line_spacing": {"type": "number", "description": "줄 간격 배수. 1.0에서 2.5 사이"},
    }
)

STYLE_SCHEMA = _obj(
    {
        "aspect_ratio": {
            "type": "string",
            "enum": ["16:9", "9:16", "1:1"],
            "description": "화면 비율",
        },
        "safe_margin": {"type": "integer", "description": "좌우 안전 여백(px)"},
        "caption": _LAYER_SCHEMA,
        "title": _LAYER_SCHEMA,
    }
)

REVISE_SCHEMA = _obj(
    {
        "understood": {
            "type": "string",
            "description": "요청을 무엇으로 알아들었는지 한 문장. 형님 말투로 짧게",
        },
        "style": STYLE_SCHEMA,
        "scene_changes": {
            "type": "array",
            "description": "글자로 고칠 것만 담는다. 안 고칠 장면은 넣지 않는다",
            "items": _obj(
                {
                    "no": {"type": "integer", "description": "고칠 장면 번호"},
                    "field": {
                        "type": "string",
                        "enum": [
                            "narration",
                            "caption",
                            "image_prompt",
                            "video_prompt",
                            "bgm",
                            "seconds",
                        ],
                        "description": "고칠 항목",
                    },
                    "new_value": {"type": "string", "description": "바꿀 내용 전체"},
                    "reason": {"type": "string", "description": "왜 이렇게 고쳤는지 한 줄"},
                }
            ),
        },
        "regenerate_scenes": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "그림을 다시 뽑아야 하는 장면 번호. 글자만 고치면 빈 목록",
        },
        "done": _str_list("실제로 바꾼 것을 형님이 알아볼 말로 적은 목록"),
        "note": {
            "type": "string",
            "description": "못 바꾼 것이나 미리 알아야 할 것. 없으면 빈 문자열",
        },
    }
)


# ------------------------------------------------------------------- 명령창

INTENT_SCHEMA = _obj(
    {
        "action": {
            "type": "string",
            "enum": [
                "analyze",
                "save_skill",
                "list_skills",
                "produce",
                "revise",
                "ask",
                "ready",
                "help",
                "unclear",
            ],
            "description": "무엇을 하라는 말인지",
        },
        "url": {"type": "string", "description": "영상 주소. 없으면 빈 문자열"},
        "notes": {"type": "string", "description": "곁들인 요청이나 메모. 없으면 빈 문자열"},
        "skill_hint": {
            "type": "string",
            "description": "어느 결을 쓰라고 했는지. 이름 일부여도 된다. 없으면 빈 문자열",
        },
        "topics": _str_list(
            "만들 영상의 주제 목록. 한 번에 여러 개를 시켰으면 다 담는다. "
            "하나뿐이면 하나만. 없으면 빈 목록"
        ),
        "minutes": {"type": "integer", "description": "목표 길이(분). 말 안 했으면 0"},
        "folder": {
            "type": "string",
            "description": "결과물을 담을 폴더 이름을 지어줬으면 그대로. 안 지었으면 빈 문자열",
        },
        "instruction": {
            "type": "string",
            "description": "고쳐달라는 내용 전체. 고치기가 아니면 빈 문자열",
        },
        "reply": {
            "type": "string",
            "description": "지금 무엇을 하겠다고 형님께 드릴 한 마디. 짧고 담담하게",
        },
    }
)
