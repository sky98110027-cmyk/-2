"""타임라인과 레이어.

영상 한 편은 시간 축 하나 위에 여러 겹이 얹힌 것이다.
화면, 자막, 목소리, 환경음, 배경음, 캐릭터.
레퍼런스를 뜯을 때도 이 모양으로 뜯고, 새로 만들 때도 이 모양으로 만든다.
그래야 "레퍼런스대로" 라는 말이 코드로 잡힌다.

각 레이어에는 '제공자' 자리가 있다.
목소리는 일레븐랩스, 화면은 힉스필드, 이런 식으로 꽂는다.
비어 있으면 그 레이어는 손으로 채우거나 건너뛴다.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# 레이어 이름과 화면에 보일 말. 순서가 화면 순서다 (아래에서 위로 쌓인다고 생각한다).
LAYERS: list[dict[str, Any]] = [
    {"key": "screen", "name": "화면", "what": "장면마다 깔리는 그림이나 영상", "unit": "shot"},
    {"key": "character", "name": "캐릭터", "what": "화면 위에 뜨는 밈, 스티커, 마스코트", "unit": "cue"},
    {"key": "caption", "name": "자막", "what": "화면 위 글씨", "unit": "cue"},
    {"key": "voice", "name": "목소리", "what": "나레이션", "unit": "cue"},
    {"key": "ambient", "name": "환경음", "what": "바람, 발소리, 총성 같은 현장음", "unit": "cue"},
    {"key": "bgm", "name": "배경음", "what": "음악", "unit": "cue"},
]

LAYER_KEYS = [layer["key"] for layer in LAYERS]

# 레이어마다 꽂을 수 있는 제공자. 실제로 부를 수 있는 것만 'ready' 로 표시된다.
PROVIDERS: dict[str, list[dict[str, Any]]] = {
    "screen": [
        {"id": "prompt_only", "name": "프롬프트만 뽑기", "needs": [], "note": "다른 도구에 붙여넣습니다"},
        {"id": "higgsfield", "name": "힉스필드", "needs": ["HIGGSFIELD_API_KEY"], "note": "MCP로 붙습니다"},
        {"id": "topview", "name": "톱뷰", "needs": ["TOPVIEW_API_KEY"], "note": "MCP로 붙습니다"},
        {"id": "folder", "name": "내 그림 폴더", "needs": [], "note": "장면 번호대로 파일을 넣어둡니다"},
    ],
    "character": [
        {"id": "none", "name": "안 씀", "needs": [], "note": ""},
        {"id": "folder", "name": "내 캐릭터 폴더", "needs": [], "note": "배경 뺀 PNG를 넣어둡니다"},
    ],
    "caption": [
        {"id": "builtin", "name": "이 앱", "needs": [], "note": "ASS 자막으로 굽습니다"},
        {"id": "none", "name": "안 씀", "needs": [], "note": "편집 프로그램에서 넣습니다"},
    ],
    "voice": [
        {"id": "elevenlabs", "name": "일레븐랩스", "needs": ["ELEVENLABS_API_KEY"], "note": "원고를 읽어줍니다"},
        {"id": "folder", "name": "내 녹음 폴더", "needs": [], "note": "장면 번호대로 녹음 파일을 넣어둡니다"},
        {"id": "none", "name": "안 씀", "needs": [], "note": "나중에 직접 얹습니다"},
    ],
    "ambient": [
        {"id": "none", "name": "안 씀", "needs": [], "note": ""},
        {"id": "folder", "name": "내 효과음 폴더", "needs": [], "note": "장면 번호대로 파일을 넣어둡니다"},
        {"id": "slot", "name": "(꽂을 자리)", "needs": ["AMBIENT_API_KEY"], "note": "환경음 생성 API를 여기에 붙입니다"},
    ],
    "bgm": [
        {"id": "none", "name": "안 씀", "needs": [], "note": ""},
        {"id": "file", "name": "음악 파일 하나", "needs": [], "note": "영상 전체에 깔립니다"},
        {"id": "slot", "name": "(꽂을 자리)", "needs": ["MUSIC_API_KEY"], "note": "음악 생성 API를 여기에 붙입니다"},
    ],
}

DEFAULT_PROVIDERS = {
    "screen": "prompt_only",
    "character": "none",
    "caption": "builtin",
    "voice": "none",
    "ambient": "none",
    "bgm": "none",
}


def empty_timeline(total_seconds: int = 0) -> dict[str, Any]:
    """빈 타임라인 한 장."""
    return {
        "total_seconds": int(total_seconds or 0),
        "aspect_ratio": "16:9",
        "shots": [],  # 화면 레이어. 장면 하나가 한 칸
        "cues": {key: [] for key in LAYER_KEYS if key != "screen"},  # 나머지 레이어
        "providers": dict(DEFAULT_PROVIDERS),
    }


def _sec(value: Any, fallback: float = 0.0) -> float:
    try:
        return max(0.0, round(float(value), 2))
    except (TypeError, ValueError):
        return fallback


def normalize(tl: Any) -> dict[str, Any]:
    """어디서 온 타임라인이든 모양을 맞춘다. 모델이 준 것도 믿지 않는다."""
    tl = tl if isinstance(tl, dict) else {}
    out = empty_timeline(tl.get("total_seconds", 0))

    ratio = str(tl.get("aspect_ratio") or "16:9")
    out["aspect_ratio"] = ratio if ratio in ("16:9", "9:16", "1:1") else "16:9"

    cursor = 0.0
    for i, shot in enumerate(tl.get("shots") or [], 1):
        shot = shot if isinstance(shot, dict) else {}
        start = _sec(shot.get("start"), cursor)
        dur = _sec(shot.get("seconds"), 8.0) or 8.0
        out["shots"].append(
            {
                "no": int(shot.get("no") or i),
                "start": start,
                "seconds": dur,
                "beat": str(shot.get("beat") or ""),
                "look": str(shot.get("look") or ""),  # 그 장면이 어떻게 생겼는지
                "motion": str(shot.get("motion") or ""),  # 카메라가 어떻게 움직이는지
                "image_prompt": str(shot.get("image_prompt") or ""),
                "video_prompt": str(shot.get("video_prompt") or ""),
                "asset": str(shot.get("asset") or ""),  # 실제 파일이 정해졌으면 여기
            }
        )
        cursor = start + dur

    for key in out["cues"]:
        for cue in (tl.get("cues") or {}).get(key) or []:
            cue = cue if isinstance(cue, dict) else {}
            out["cues"][key].append(
                {
                    "start": _sec(cue.get("start")),
                    "seconds": _sec(cue.get("seconds"), 0.0),
                    "text": str(cue.get("text") or ""),
                    "note": str(cue.get("note") or ""),
                    "asset": str(cue.get("asset") or ""),
                    "level": _clamp(cue.get("level"), 0.0, 1.0, 1.0),
                    "position": str(cue.get("position") or ""),
                }
            )
        out["cues"][key].sort(key=lambda c: c["start"])

    for key, choice in (tl.get("providers") or {}).items():
        if key in PROVIDERS and any(p["id"] == choice for p in PROVIDERS[key]):
            out["providers"][key] = choice

    if not out["total_seconds"] and out["shots"]:
        last = out["shots"][-1]
        out["total_seconds"] = int(round(last["start"] + last["seconds"]))

    return out


def _clamp(value: Any, low: float, high: float, fallback: float) -> float:
    try:
        return round(max(low, min(float(value), high)), 2)
    except (TypeError, ValueError):
        return fallback


def from_script(script: dict[str, Any], style: dict[str, Any] | None = None) -> dict[str, Any]:
    """대본 한 편을 타임라인으로 편다. 장면 → 화면칸, 나레이션 → 목소리, 자막 → 자막."""
    tl = empty_timeline(script.get("total_seconds", 0))
    tl["aspect_ratio"] = (style or {}).get("aspect_ratio", "16:9")

    cursor = 0.0
    for scene in script.get("scenes") or []:
        dur = float(scene.get("seconds") or 8)
        tl["shots"].append(
            {
                "no": scene.get("no"),
                "start": cursor,
                "seconds": dur,
                "beat": scene.get("beat", ""),
                "look": "",
                "motion": scene.get("video_prompt", ""),
                "image_prompt": scene.get("image_prompt", ""),
                "video_prompt": scene.get("video_prompt", ""),
                "asset": "",
            }
        )
        if scene.get("narration"):
            tl["cues"]["voice"].append(
                {"start": cursor, "seconds": dur, "text": scene["narration"], "note": "",
                 "asset": "", "level": 1.0, "position": ""}
            )
        if scene.get("caption"):
            tl["cues"]["caption"].append(
                {"start": cursor, "seconds": dur, "text": scene["caption"], "note": "",
                 "asset": "", "level": 1.0, "position": ""}
            )
        if scene.get("bgm"):
            tl["cues"]["bgm"].append(
                {"start": cursor, "seconds": dur, "text": "", "note": scene["bgm"],
                 "asset": "", "level": 0.35, "position": ""}
            )
        cursor += dur

    tl["total_seconds"] = int(round(cursor)) or tl["total_seconds"]
    return normalize(tl)


def provider_status(tl: dict[str, Any], have_keys: set[str]) -> list[dict[str, Any]]:
    """레이어마다 지금 꽂힌 제공자가 실제로 쓸 수 있는지 본다."""
    out = []
    for layer in LAYERS:
        key = layer["key"]
        chosen = (tl.get("providers") or {}).get(key, DEFAULT_PROVIDERS[key])
        spec = next((p for p in PROVIDERS[key] if p["id"] == chosen), PROVIDERS[key][0])
        missing = [k for k in spec["needs"] if k not in have_keys]
        out.append(
            {
                "layer": key,
                "name": layer["name"],
                "what": layer["what"],
                "provider": spec["id"],
                "provider_name": spec["name"],
                "note": spec["note"],
                "ready": not missing,
                "missing": missing,
                "options": [
                    {"id": p["id"], "name": p["name"], "note": p["note"],
                     "ready": all(k in have_keys for k in p["needs"])}
                    for p in PROVIDERS[key]
                ],
                "count": len(tl["shots"]) if key == "screen" else len((tl.get("cues") or {}).get(key) or []),
            }
        )
    return out


def describe(tl: dict[str, Any]) -> str:
    """타임라인 한 장을 사람이 읽을 글로."""
    tl = normalize(tl)  # 어디서 온 것이든 모양부터 맞춘다
    lines = [f"전체 {tl['total_seconds']}초 · {tl['aspect_ratio']} · 장면 {len(tl['shots'])}컷"]
    for shot in tl["shots"]:
        end = shot["start"] + shot["seconds"]
        lines.append(f"[{_mmss(shot['start'])}–{_mmss(end)}] {shot['beat']} {shot['look']}".rstrip())
    for key in ("character", "ambient", "bgm"):
        cues = tl["cues"].get(key) or []
        if cues:
            name = next(l["name"] for l in LAYERS if l["key"] == key)
            lines.append(f"{name}: " + ", ".join(
                f"{_mmss(c['start'])} {c['text'] or c['note']}" for c in cues[:8]))
    return "\n".join(lines)


def _mmss(sec: float) -> str:
    sec = int(round(sec))
    return f"{sec // 60}:{sec % 60:02d}"
