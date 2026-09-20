"""레이어에 꽂는 제공자들.

지금 실제로 부를 수 있는 건 일레븐랩스(목소리) 하나다.
나머지는 자리만 잡아두고, 프롬프트나 파일로 우회한다.
없는 걸 있는 척하지 않는다.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import httpx

from .connect import get_value


class ProviderUnavailable(Exception):
    """제공자를 못 부를 때. 메시지는 그대로 화면에 뜬다."""


# ------------------------------------------------------------ 일레븐랩스

ELEVEN_BASE = "https://api.elevenlabs.io/v1"
ELEVEN_MODEL = "eleven_multilingual_v2"  # 한국어가 되는 모델


def _eleven_headers() -> dict[str, str]:
    key = get_value("ELEVENLABS_API_KEY")
    if not key:
        raise ProviderUnavailable("일레븐랩스 키가 없습니다. 연결 탭에서 넣어주세요.")
    return {"xi-api-key": key}


def eleven_voices() -> list[dict[str, Any]]:
    """쓸 수 있는 목소리 목록."""
    try:
        res = httpx.get(f"{ELEVEN_BASE}/voices", headers=_eleven_headers(), timeout=30)
    except httpx.HTTPError as exc:
        raise ProviderUnavailable("일레븐랩스에 연결이 안 됩니다. 인터넷을 확인해주세요.") from exc

    if res.status_code == 401:
        raise ProviderUnavailable("일레븐랩스 키가 틀렸습니다.")
    if res.status_code != 200:
        raise ProviderUnavailable(f"일레븐랩스가 오류를 돌려줬습니다 ({res.status_code}).")

    out = []
    for v in (res.json().get("voices") or []):
        labels = v.get("labels") or {}
        out.append(
            {
                "id": v.get("voice_id", ""),
                "name": v.get("name", ""),
                "gender": labels.get("gender", ""),
                "age": labels.get("age", ""),
                "accent": labels.get("accent", ""),
                "preview": v.get("preview_url", ""),
            }
        )
    return out


def eleven_speak(
    text: str,
    voice_id: str,
    out_path: str | Path,
    *,
    stability: float = 0.55,
    similarity: float = 0.8,
    style: float = 0.15,
    speed: float = 0.95,
) -> Path:
    """원고 한 덩어리를 읽어서 mp3 로 남긴다.

    시니어 채널 나레이션은 조금 느리고 안정적인 쪽이 듣기 좋다. 기본값을 그쪽으로 뒀다.
    """
    text = text.strip()
    if not text:
        raise ProviderUnavailable("읽을 원고가 비어 있습니다.")
    if not voice_id:
        raise ProviderUnavailable("어느 목소리로 읽을지 골라주세요.")

    body = {
        "text": text,
        "model_id": ELEVEN_MODEL,
        "voice_settings": {
            "stability": _unit(stability),
            "similarity_boost": _unit(similarity),
            "style": _unit(style),
            "use_speaker_boost": True,
            "speed": max(0.7, min(float(speed), 1.2)),
        },
    }

    try:
        res = httpx.post(
            f"{ELEVEN_BASE}/text-to-speech/{voice_id}",
            headers={**_eleven_headers(), "Accept": "audio/mpeg"},
            json=body,
            timeout=120,
        )
    except httpx.HTTPError as exc:
        raise ProviderUnavailable("일레븐랩스에 연결이 안 됩니다. 인터넷을 확인해주세요.") from exc

    if res.status_code == 401:
        raise ProviderUnavailable("일레븐랩스 키가 틀렸습니다.")
    if res.status_code == 422:
        raise ProviderUnavailable("일레븐랩스가 이 원고를 받지 않았습니다. 너무 길거나 목소리 번호가 틀렸을 수 있습니다.")
    if res.status_code == 429:
        raise ProviderUnavailable("일레븐랩스 이번 달 몫을 다 썼거나 요청이 몰렸습니다.")
    if res.status_code != 200:
        raise ProviderUnavailable(f"일레븐랩스가 오류를 돌려줬습니다 ({res.status_code}).")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(res.content)
    return out_path


def _unit(v: Any) -> float:
    try:
        return max(0.0, min(float(v), 1.0))
    except (TypeError, ValueError):
        return 0.5


# ------------------------------------------------------------ 폴더 제공자

_NO = re.compile(r"(\d{1,3})")


def folder_assets(folder: str | Path, exts: tuple[str, ...]) -> dict[int, Path]:
    """폴더 안 파일을 장면 번호로 묶는다. 이름에 든 첫 숫자가 번호다.

    01.png, 장면2.png, scene_03_final.png 전부 된다.
    """
    folder = Path(folder).expanduser()
    if not folder.is_dir():
        return {}
    out: dict[int, Path] = {}
    for f in sorted(folder.iterdir()):
        if f.suffix.lower() not in exts or not f.is_file():
            continue
        m = _NO.search(f.stem)
        if not m:
            continue
        no = int(m.group(1))
        out.setdefault(no, f)  # 같은 번호가 여럿이면 이름순 첫 것
    return out


IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")
VIDEO_EXTS = (".mp4", ".mov", ".webm", ".mkv")
AUDIO_EXTS = (".mp3", ".wav", ".m4a", ".aac", ".ogg")
