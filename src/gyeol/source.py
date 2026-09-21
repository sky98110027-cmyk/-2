"""원본 영상에서 분석 재료를 긁어온다.

자막이 막혀 있는 영상도 많다. 그럴 때는 예외를 던져서
화면에서 직접 붙여넣기로 넘어가게 한다. 앱이 멈추면 안 된다.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field, asdict
from typing import Any

import httpx

# 한국어 자막을 먼저, 없으면 영어를 본다
LANG_PRIORITY = ("ko", "ko-KR", "ko-orig", "en", "en-US", "en-orig")


class SourceUnavailable(Exception):
    """자막이나 정보를 못 가져왔을 때. 메시지는 그대로 화면에 뜬다."""


@dataclass
class SourceMaterial:
    """분석에 들어가는 재료 한 덩어리."""

    url: str = ""
    title: str = ""
    uploader: str = ""
    duration: int = 0
    description: str = ""
    chapters: list[str] = field(default_factory=list)
    transcript: str = ""
    transcript_origin: str = "없음"
    timed: list[dict[str, Any]] = field(default_factory=list)  # 시간 붙은 자막 조각
    local_path: str = ""  # 받아둔 영상 파일이 있으면 여기

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def brief(self, limit: int = 40000) -> str:
        """클로드에게 넘길 텍스트 한 장으로 접는다."""
        parts = [
            f"[영상 제목] {self.title or '(모름)'}",
            f"[채널] {self.uploader or '(모름)'}",
            f"[길이] {self.duration}초" if self.duration else "[길이] (모름)",
        ]
        if self.chapters:
            parts.append("[챕터]\n" + "\n".join(f"- {c}" for c in self.chapters))
        if self.description:
            parts.append("[설명란]\n" + self.description[:2000])
        parts.append(f"[자막 출처] {self.transcript_origin}")
        parts.append("[자막 전문]\n" + self.transcript[:limit])
        return "\n\n".join(parts)


def is_probable_url(text: str) -> bool:
    return bool(re.match(r"^https?://", text.strip()))


def _pick_caption_track(info: dict[str, Any]) -> tuple[str, str] | None:
    """(자막 URL, 출처 설명)을 고른다. 수동 자막 우선."""
    for bucket, label in (("subtitles", "직접 올린 자막"), ("automatic_captions", "자동 생성 자막")):
        tracks = info.get(bucket) or {}
        for lang in LANG_PRIORITY:
            entries = tracks.get(lang)
            if not entries:
                continue
            # json3가 가장 깔끔하다. 없으면 vtt.
            for want in ("json3", "vtt", "srv1"):
                for entry in entries:
                    if entry.get("ext") == want and entry.get("url"):
                        return entry["url"], f"{label} ({lang}, {want})"
    return None


def parse_json3(raw: str) -> str:
    """유튜브 json3 자막을 평문으로."""
    data = json.loads(raw)
    lines: list[str] = []
    for event in data.get("events") or []:
        segs = event.get("segs") or []
        text = "".join(seg.get("utf8", "") for seg in segs)
        text = text.replace("\n", " ").strip()
        if text:
            lines.append(text)
    return _tidy(" ".join(lines))


def parse_vtt(raw: str) -> str:
    """WebVTT 자막을 평문으로. 타임코드와 태그를 털어낸다."""
    lines: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith(("WEBVTT", "NOTE", "Kind:", "Language:")):
            continue
        if "-->" in line:
            continue
        if line.isdigit():
            continue
        line = re.sub(r"<[^>]+>", "", line)
        line = html.unescape(line).strip()
        if line and (not lines or lines[-1] != line):
            lines.append(line)
    return _tidy(" ".join(lines))


def _ts(text: str) -> float:
    """00:01:02.345 나 01:02.345 나 1.5 를 초로."""
    text = text.strip().replace(",", ".")
    parts = text.split(":")
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return 0.0
    while len(nums) < 3:
        nums.insert(0, 0.0)
    h, m, s = nums[-3:]
    return round(h * 3600 + m * 60 + s, 3)


def parse_vtt_timed(raw: str) -> list[dict[str, Any]]:
    """VTT/SRT 자막을 시간 붙은 조각으로. 타임라인에 얹을 때 쓴다."""
    cues: list[dict[str, Any]] = []
    start = end = None
    buf: list[str] = []

    def flush():
        nonlocal buf, start, end
        text = html.unescape(re.sub(r"<[^>]+>", "", " ".join(buf))).strip()
        text = re.sub(r"\s+", " ", text)
        if start is not None and text and (not cues or cues[-1]["text"] != text):
            cues.append({"start": start, "end": end if end is not None else start, "text": text})
        buf, start, end = [], None, None

    for line in raw.splitlines():
        line = line.strip()
        if "-->" in line:
            flush()
            a, _, b = line.partition("-->")
            start, end = _ts(a), _ts(b.split()[0] if b.split() else b)
            continue
        if not line:
            flush()
            continue
        if line.startswith(("WEBVTT", "NOTE", "Kind:", "Language:")) or line.isdigit():
            continue
        if start is not None:
            buf.append(line)
    flush()
    return cues


def parse_json3_timed(raw: str) -> list[dict[str, Any]]:
    """유튜브 json3 자막을 시간 붙은 조각으로."""
    data = json.loads(raw)
    cues: list[dict[str, Any]] = []
    for event in data.get("events") or []:
        segs = event.get("segs") or []
        text = "".join(seg.get("utf8", "") for seg in segs).replace("\n", " ").strip()
        if not text:
            continue
        start = round(float(event.get("tStartMs") or 0) / 1000, 3)
        dur = round(float(event.get("dDurationMs") or 0) / 1000, 3)
        if cues and cues[-1]["text"] == text:
            continue
        cues.append({"start": start, "end": round(start + dur, 3), "text": text})
    return cues


def _tidy(text: str, dedupe: bool = True) -> str:
    """중복 공백을 정리한다.

    dedupe 는 자동 자막 전용이다. 자동 자막은 한 말을 두 번씩 뱉는다.
    사람이 직접 쓴 대본에는 쓰지 않는다.
    반복은 이 앱이 찾아내야 할 감정 장치라서, 지워버리면 증거가 사라진다.
    """
    text = re.sub(r"\s+", " ", text).strip()
    if dedupe:
        text = re.sub(r"\b(\S+)( \1\b)+", r"\1", text)
    return text


def _chapters(info: dict[str, Any]) -> list[str]:
    out = []
    for ch in info.get("chapters") or []:
        title = (ch.get("title") or "").strip()
        start = int(ch.get("start_time") or 0)
        if title:
            out.append(f"{start // 60}:{start % 60:02d} {title}")
    return out


def fetch_source(url: str, timeout: float = 30.0) -> SourceMaterial:
    """영상 링크 하나에서 제목, 설명, 자막을 받아온다."""
    url = url.strip()
    if not is_probable_url(url):
        raise SourceUnavailable("영상 주소가 아닙니다. http로 시작하는 링크를 넣어주세요.")

    try:
        from yt_dlp import YoutubeDL
    except ImportError as exc:  # pragma: no cover - 설치 안내용
        raise SourceUnavailable(
            "yt-dlp가 설치되어 있지 않습니다. 터미널에서 pip install yt-dlp 를 실행해주세요."
        ) from exc

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": list(LANG_PRIORITY),
        "socket_timeout": timeout,
    }
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise SourceUnavailable(
            "영상 정보를 못 가져왔습니다. 비공개 영상이거나 접속이 막혔을 수 있습니다.\n"
            "아래 '자막 직접 넣기'에 대본을 붙여넣으면 그대로 분석합니다."
        ) from exc

    material = SourceMaterial(
        url=url,
        title=(info.get("title") or "").strip(),
        uploader=(info.get("uploader") or info.get("channel") or "").strip(),
        duration=int(info.get("duration") or 0),
        description=(info.get("description") or "").strip(),
        chapters=_chapters(info),
    )

    picked = _pick_caption_track(info)
    if not picked:
        raise SourceUnavailable(
            f"'{material.title or url}' 에는 가져올 수 있는 자막이 없습니다.\n"
            "아래 '자막 직접 넣기'에 대본을 붙여넣으면 그대로 분석합니다."
        )

    track_url, origin = picked
    try:
        raw = httpx.get(track_url, timeout=timeout, follow_redirects=True).text
    except Exception as exc:
        raise SourceUnavailable(
            "자막 파일을 내려받다가 끊겼습니다. 잠시 뒤에 다시 해보시거나, 대본을 직접 붙여넣어주세요."
        ) from exc

    if origin.endswith("json3)"):
        text, timed = parse_json3(raw), parse_json3_timed(raw)
    else:
        text, timed = parse_vtt(raw), parse_vtt_timed(raw)
    if len(text) < 100:
        raise SourceUnavailable(
            "자막을 받긴 했는데 내용이 거의 비어 있습니다. 대본을 직접 붙여넣어주세요."
        )

    material.transcript = text
    material.transcript_origin = origin
    material.timed = timed
    return material


def material_from_text(text: str, title: str = "", url: str = "") -> SourceMaterial:
    """대본을 직접 붙여넣었을 때 쓰는 재료."""
    text = text.strip()
    if len(text) < 100:
        raise SourceUnavailable("붙여넣은 대본이 너무 짧습니다. 100자 넘게 넣어주세요.")
    return SourceMaterial(
        url=url,
        title=title.strip(),
        transcript=_tidy(text, dedupe=False),
        transcript_origin="직접 붙여넣은 대본",
    )
