"""자막과 화면 꾸밈새.

글꼴, 색, 위치, 크기. 이런 것은 영상을 다시 뽑을 필요가 없다.
값만 바꿔서 자막만 다시 입히면 된다. 몇 초면 끝나고 돈도 안 든다.
그래서 대본과 따로 떼어서 여기에 둔다.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

# 한글이 깨지지 않는 글꼴만 올린다
FONTS = [
    "Pretendard",
    "나눔고딕",
    "나눔명조",
    "본고딕 (Noto Sans KR)",
    "본명조 (Noto Serif KR)",
    "애플 SD 산돌고딕",
    "맑은 고딕",
    "에스코어드림",
]

POSITIONS = {"top": "위", "middle": "가운데", "bottom": "아래"}
BACKGROUNDS = {"none": "없음", "band": "띠", "box": "상자"}

DEFAULT_STYLE: dict[str, Any] = {
    "aspect_ratio": "16:9",
    "safe_margin": 60,
    "caption": {
        "font": "Pretendard",
        "size": 54,
        "bold": True,
        "color": "#FFFFFF",
        "outline_color": "#000000",
        "outline": 4,
        "position": "bottom",
        "offset": 90,
        "background": "none",
        "background_color": "#000000",
        "background_opacity": 0.55,
        "line_spacing": 1.35,
    },
    "title": {
        "font": "Pretendard",
        "size": 84,
        "bold": True,
        "color": "#F5E6C8",
        "outline_color": "#000000",
        "outline": 5,
        "position": "middle",
        "offset": 0,
        "background": "none",
        "background_color": "#000000",
        "background_opacity": 0.4,
        "line_spacing": 1.2,
    },
}

_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def default_style() -> dict[str, Any]:
    return deepcopy(DEFAULT_STYLE)


def _clamp(value: Any, low: float, high: float, fallback: float) -> float:
    try:
        return max(low, min(float(value), high))
    except (TypeError, ValueError):
        return fallback


def _color(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    return text.upper() if _HEX.match(text) else fallback


def _layer(given: Any, base: dict[str, Any]) -> dict[str, Any]:
    """모델이 돌려준 값을 믿지 않고 하나씩 검사해서 받는다."""
    given = given if isinstance(given, dict) else {}
    out = deepcopy(base)

    font = str(given.get("font") or "").strip()
    if font:
        out["font"] = font

    out["size"] = int(_clamp(given.get("size", base["size"]), 16, 200, base["size"]))
    out["bold"] = bool(given.get("bold", base["bold"]))
    out["color"] = _color(given.get("color"), base["color"])
    out["outline_color"] = _color(given.get("outline_color"), base["outline_color"])
    out["outline"] = int(_clamp(given.get("outline", base["outline"]), 0, 20, base["outline"]))

    position = str(given.get("position") or "").strip()
    out["position"] = position if position in POSITIONS else base["position"]

    out["offset"] = int(_clamp(given.get("offset", base["offset"]), -500, 500, base["offset"]))

    background = str(given.get("background") or "").strip()
    out["background"] = background if background in BACKGROUNDS else base["background"]

    out["background_color"] = _color(given.get("background_color"), base["background_color"])
    out["background_opacity"] = round(
        _clamp(given.get("background_opacity", base["background_opacity"]), 0, 1,
               base["background_opacity"]), 2
    )
    out["line_spacing"] = round(
        _clamp(given.get("line_spacing", base["line_spacing"]), 1.0, 2.5, base["line_spacing"]), 2
    )
    return out


def normalize(style: Any) -> dict[str, Any]:
    """어디서 온 값이든 안전한 스타일로 다듬는다."""
    style = style if isinstance(style, dict) else {}
    ratio = str(style.get("aspect_ratio") or "").strip()
    return {
        "aspect_ratio": ratio if ratio in ("16:9", "9:16", "1:1") else "16:9",
        "safe_margin": int(_clamp(style.get("safe_margin", 60), 0, 300, 60)),
        "caption": _layer(style.get("caption"), DEFAULT_STYLE["caption"]),
        "title": _layer(style.get("title"), DEFAULT_STYLE["title"]),
    }


# ------------------------------------------------------- ffmpeg 로 넘기기

def canvas_size(aspect_ratio: str) -> tuple[int, int]:
    return {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080)}.get(
        aspect_ratio, (1920, 1080)
    )


def _ass_color(hex_color: str, opacity: float = 1.0) -> str:
    """#RRGGBB 를 ASS 의 &HAABBGGRR 로. 알파는 반대로 센다."""
    r, g, b = hex_color[1:3], hex_color[3:5], hex_color[5:7]
    alpha = f"{int(round((1 - max(0.0, min(opacity, 1.0))) * 255)):02X}"
    return f"&H{alpha}{b}{g}{r}"


def to_ass_style(style: dict[str, Any], layer: str = "caption") -> str:
    """자막을 실제로 구울 때 쓰는 ASS 스타일 한 줄.

    영상을 다시 뽑지 않고 자막만 갈아끼울 때 이걸 쓴다.
    """
    style = normalize(style)
    s = style[layer]
    width, height = canvas_size(style["aspect_ratio"])

    # ASS 정렬 번호: 아래 2, 가운데 5, 위 8
    align = {"bottom": 2, "middle": 5, "top": 8}[s["position"]]
    border_style = 3 if s["background"] in ("band", "box") else 1
    margin_v = max(0, s["offset"] if s["position"] != "middle" else 0)

    fields = [
        f"Name: {layer}",
        f"Fontname: {s['font']}",
        f"Fontsize: {s['size']}",
        f"PrimaryColour: {_ass_color(s['color'])}",
        f"OutlineColour: {_ass_color(s['outline_color'])}",
        f"BackColour: {_ass_color(s['background_color'], s['background_opacity'])}",
        f"Bold: {-1 if s['bold'] else 0}",
        f"BorderStyle: {border_style}",
        f"Outline: {s['outline']}",
        "Shadow: 0",
        f"Alignment: {align}",
        f"MarginL: {style['safe_margin']}",
        f"MarginR: {style['safe_margin']}",
        f"MarginV: {margin_v}",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
    ]
    return "\n".join(fields)


def describe(style: dict[str, Any], layer: str = "caption") -> str:
    """지금 설정을 한 줄 한국어로. 화면에 그대로 띄운다."""
    s = normalize(style)[layer]
    parts = [
        s["font"],
        f"{s['size']}px",
        "굵게" if s["bold"] else "보통",
        s["color"],
        f"{POSITIONS[s['position']]} 정렬",
    ]
    if s["outline"]:
        parts.append(f"외곽선 {s['outline']}px")
    if s["background"] != "none":
        parts.append(f"{BACKGROUNDS[s['background']]} 배경")
    return " · ".join(parts)
