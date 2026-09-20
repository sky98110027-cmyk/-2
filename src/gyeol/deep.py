"""레퍼런스 영상을 프레임 단위로 뜯는다.

자막만 읽던 것에서 한 단계 올라간다.
장면이 바뀌는 지점을 찾고, 거기서 한 장씩 뽑아 클로드가 보게 한다.
소리는 침묵 구간을 재서 어디서 말을 멈추고 음악만 흐르는지 잡는다.

솔직한 한계:
  - 모든 프레임을 보는 게 아니다. 장면마다 한 장이다.
  - 환경음이 무슨 소리인지는 못 듣는다. 있는지 없는지와 크기만 잰다.
  - ffmpeg 가 있어야 한다. 없으면 자막 분석으로 되돌아간다.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

from .llm import structured_with_images
from .schemas import _obj, _str_list
from .source import SourceMaterial, SourceUnavailable
from .timeline import empty_timeline, normalize

MAX_SHOTS = 60          # 이보다 많으면 고르게 솎는다
BATCH = 12              # 한 번에 보여줄 그림 수
FRAME_WIDTH = 768       # 이 정도면 자막과 캐릭터가 다 읽힌다
SCENE_THRESHOLD = 0.30  # ffmpeg 장면 전환 민감도
FALLBACK_EVERY = 6.0    # 장면 전환을 못 찾으면 이 간격으로
SILENCE_DB = -35
SILENCE_MIN = 1.0


class DeepUnavailable(Exception):
    """프레임 분석을 못 할 때. 자막 분석으로 되돌아가면 된다."""


def ffmpeg_있나() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


# ------------------------------------------------------------ 영상 받기

def fetch_video(url: str, work: Path, max_height: int = 720) -> Path:
    """레퍼런스 영상을 받아온다. 720p 면 충분하다. 더 크면 느리기만 하다."""
    try:
        from yt_dlp import YoutubeDL
    except ImportError as exc:
        raise DeepUnavailable("yt-dlp 가 없습니다.") from exc

    work.mkdir(parents=True, exist_ok=True)
    opts = {
        "quiet": True, "no_warnings": True,
        "format": f"bv*[height<={max_height}][ext=mp4]+ba[ext=m4a]/b[height<={max_height}][ext=mp4]/b",
        "outtmpl": str(work / "reference.%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
    }
    try:
        with YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)
    except Exception as exc:
        raise DeepUnavailable(
            "영상을 받아오지 못했습니다. 비공개거나 받기가 막힌 영상일 수 있습니다.\n"
            "받아둔 파일이 있으면 그걸 직접 넣어주세요."
        ) from exc

    found = sorted(work.glob("reference.*"), key=lambda p: p.stat().st_size, reverse=True)
    if not found:
        raise DeepUnavailable("영상 파일이 남지 않았습니다.")
    return found[0]


# ------------------------------------------------------------ ffmpeg 로 재기

def _run(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise DeepUnavailable("영상을 읽다가 너무 오래 걸려 멈췄습니다.") from exc


def duration(video: Path) -> float:
    done = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=nw=1:nk=1", str(video)])
    try:
        return round(float(done.stdout.strip()), 2)
    except ValueError:
        return 0.0


def detect_scenes(video: Path, total: float) -> list[float]:
    """장면이 바뀌는 시각들. 못 찾으면 일정 간격으로."""
    done = _run([
        "ffmpeg", "-v", "info", "-i", str(video),
        "-vf", f"select='gt(scene,{SCENE_THRESHOLD})',showinfo",
        "-vsync", "vfr", "-f", "null", "-",
    ])
    times = [0.0]
    for m in re.finditer(r"pts_time:([\d.]+)", done.stderr or ""):
        t = round(float(m.group(1)), 2)
        if t - times[-1] >= 1.5:  # 너무 붙은 건 같은 장면으로 본다
            times.append(t)

    if len(times) < 3 and total > 0:
        times = [round(t, 2) for t in _frange(0.0, total, FALLBACK_EVERY)]

    return thin(times, MAX_SHOTS)


def thin(times: list[float], limit: int) -> list[float]:
    """너무 많으면 고르게 솎는다. 첫 장면은 꼭 남긴다."""
    if len(times) <= limit:
        return times
    step = len(times) / limit
    picked = [times[int(i * step)] for i in range(limit)]
    return sorted(set(picked))


def _frange(a: float, b: float, step: float):
    t = a
    while t < b:
        yield t
        t += step


def grab_frame(video: Path, at: float, out: Path) -> bytes:
    """그 시각 한 장. 살짝 뒤(0.4초)를 잡아야 전환 잔상이 안 섞인다."""
    _run([
        "ffmpeg", "-y", "-v", "error", "-ss", f"{at + 0.4:.2f}", "-i", str(video),
        "-frames:v", "1", "-vf", f"scale={FRAME_WIDTH}:-2", "-q:v", "4", str(out),
    ], timeout=60)
    if not out.exists():
        raise DeepUnavailable(f"{at:.1f}초 장면을 못 뽑았습니다.")
    return out.read_bytes()


def detect_silences(video: Path) -> list[dict[str, float]]:
    """말도 음악도 없는 구간들."""
    done = _run([
        "ffmpeg", "-v", "info", "-i", str(video),
        "-af", f"silencedetect=noise={SILENCE_DB}dB:d={SILENCE_MIN}", "-f", "null", "-",
    ])
    out = []
    start = None
    for line in (done.stderr or "").splitlines():
        m = re.search(r"silence_start: ([\d.]+)", line)
        if m:
            start = float(m.group(1))
            continue
        m = re.search(r"silence_end: ([\d.]+)", line)
        if m and start is not None:
            end = float(m.group(1))
            out.append({"start": round(start, 2), "seconds": round(end - start, 2)})
            start = None
    return out


# ------------------------------------------------------------ 클로드가 본다

LOOK_SCHEMA = _obj({
    "shots": {
        "type": "array",
        "items": _obj({
            "index": {"type": "integer", "description": "몇 번째 그림인지. 1부터"},
            "look": {"type": "string", "description": "이 장면이 어떻게 생겼는지 한 문장. 구도, 피사체, 색감"},
            "motion_guess": {"type": "string", "description": "정지 사진인지, 영상인지, 카메라가 어떻게 움직일지 짐작"},
            "on_screen_text": {"type": "string", "description": "화면에 박힌 글씨 그대로. 없으면 빈 문자열"},
            "has_character": {"type": "boolean", "description": "밈 캐릭터, 스티커, 마스코트, 인물 컷아웃이 얹혀 있는가"},
            "character_what": {"type": "string", "description": "얹힌 캐릭터가 무엇인지. 없으면 빈 문자열"},
            "character_where": {
                "type": "string",
                "enum": ["", "top-left", "top-right", "bottom-left", "bottom-right", "center", "middle-left", "middle-right"],
                "description": "캐릭터 자리",
            },
            "caption_position": {"type": "string", "enum": ["", "top", "middle", "bottom"], "description": "자막 자리"},
            "caption_color": {"type": "string", "description": "자막 색. #RRGGBB 로 짐작. 없으면 빈 문자열"},
            "caption_size": {"type": "string", "enum": ["", "small", "medium", "large"], "description": "자막 크기 느낌"},
            "caption_has_background": {"type": "boolean", "description": "자막 뒤에 띠나 상자가 있는가"},
            "mood": {"type": "string", "description": "색감과 분위기를 영어로. 이미지 프롬프트에 그대로 쓸 수 있게"},
        }),
    },
    "overall": _obj({
        "visual_dna": {"type": "string", "description": "이 영상의 화면 결을 영어 한 줄로. 매 장면 프롬프트 끝에 붙일 것"},
        "character_pattern": {"type": "string", "description": "캐릭터가 언제 어떻게 등장하는 규칙. 없으면 '없음'"},
        "caption_style_note": {"type": "string", "description": "자막 꾸밈새를 한 줄로"},
        "shot_rules": _str_list("화면 구성 규칙 3~6개. 한국어"),
    }),
})

LOOK_SYSTEM = """\
당신은 영상 편집자다. 레퍼런스 영상에서 장면마다 한 장씩 뽑은 그림을 본다.
이 영상을 그대로 흉내 내서 만들 수 있게, 보이는 대로 정확히 적는다.

지킬 것:
- 지어내지 마라. 그림에 없는 건 없다고 해라.
- 화면에 박힌 글씨는 한 글자도 바꾸지 말고 그대로 옮겨라.
- 캐릭터란 배경과 따로 얹힌 것이다. 밈 짤, 스티커, 마스코트, 오려 붙인 인물.
  사진 속에 원래 있는 사람은 캐릭터가 아니다.
- 자막 색은 #RRGGBB 로 짐작해 적어라. 흰색이면 #FFFFFF.
- mood 와 visual_dna 는 영어로 쓴다. 이미지 생성 프롬프트에 그대로 붙일 것이다.
- 나머지는 한국어로 쓴다.
"""


def look_at(frames: list[bytes], times: list[float], captions: list[str]) -> dict[str, Any]:
    """그림 묶음을 클로드에게 보여주고 장면 설명을 받는다."""
    lines = []
    for i, (t, cap) in enumerate(zip(times, captions), 1):
        lines.append(f"그림 {i}: {int(t // 60)}:{int(t % 60):02d} 지점" + (f", 이때 하는 말: \"{cap}\"" if cap else ""))
    text = "위 그림들을 순서대로 보고 채워라.\n\n" + "\n".join(lines)
    return structured_with_images(system=LOOK_SYSTEM, text=text, images=frames, schema=LOOK_SCHEMA)


# ------------------------------------------------------------ 다 묶기

def _caption_at(timed: list[dict[str, Any]], t: float) -> str:
    for c in timed:
        if c["start"] <= t <= c.get("end", c["start"] + 3):
            return c["text"]
    return ""


def speech_gaps(timed: list[dict[str, Any]], total: float, min_gap: float = 1.5) -> list[dict[str, float]]:
    """자막 사이 빈 구간. 여기서 침묵이거나 음악만 흐른다."""
    gaps = []
    cursor = 0.0
    for c in sorted(timed, key=lambda c: c["start"]):
        if c["start"] - cursor >= min_gap:
            gaps.append({"start": round(cursor, 2), "seconds": round(c["start"] - cursor, 2)})
        cursor = max(cursor, c.get("end", c["start"]))
    if total and total - cursor >= min_gap:
        gaps.append({"start": round(cursor, 2), "seconds": round(total - cursor, 2)})
    return gaps


def classify_gaps(gaps: list[dict], silences: list[dict]) -> tuple[list[dict], list[dict]]:
    """말이 없는 구간을 '침묵' 과 '음악·환경음만' 으로 가른다."""
    quiet, music = [], []
    for g in gaps:
        g_end = g["start"] + g["seconds"]
        covered = sum(
            max(0.0, min(g_end, s["start"] + s["seconds"]) - max(g["start"], s["start"]))
            for s in silences
        )
        (quiet if covered >= g["seconds"] * 0.6 else music).append(g)
    return quiet, music


def analyze_reference(
    material: SourceMaterial,
    work: Path | None = None,
    *,
    on_step: Callable[[str], None] | None = None,
    looker: Callable[..., dict[str, Any]] = look_at,
) -> dict[str, Any]:
    """레퍼런스 한 편 → 레이어가 채워진 타임라인 + 화면 결 메모."""
    say = on_step or (lambda _: None)
    if not ffmpeg_있나():
        raise DeepUnavailable(
            "프레임 단위로 뜯으려면 ffmpeg 가 필요합니다.\n"
            "없어도 자막으로 결은 뽑힙니다. ffmpeg.org 에서 받아 깔면 화면까지 뜯습니다."
        )

    own = work is None
    work = work or Path(tempfile.mkdtemp(prefix="gyeol-deep-"))
    try:
        if material.local_path and Path(material.local_path).exists():
            video = Path(material.local_path)
        elif material.url:
            say("레퍼런스 영상 받는 중")
            video = fetch_video(material.url, work)
        else:
            raise DeepUnavailable("영상 주소나 파일이 있어야 프레임을 뜯습니다.")

        total = duration(video) or float(material.duration or 0)
        say("장면 바뀌는 지점 찾는 중")
        times = detect_scenes(video, total)
        say(f"장면 {len(times)}컷에서 한 장씩 뽑는 중")
        frames = [grab_frame(video, t, work / f"f{i:03d}.jpg") for i, t in enumerate(times)]
        say("침묵 구간 재는 중")
        silences = detect_silences(video)

        # 클로드가 본다. 열두 장씩.
        shots: list[dict[str, Any]] = []
        overall: dict[str, Any] = {}
        for b in range(0, len(frames), BATCH):
            say(f"클로드가 장면 보는 중 ({b + 1}~{min(b + BATCH, len(frames))}/{len(frames)})")
            batch_times = times[b:b + BATCH]
            caps = [_caption_at(material.timed, t) for t in batch_times]
            got = looker(frames[b:b + BATCH], batch_times, caps)
            for s in got.get("shots") or []:
                idx = int(s.get("index") or 0) - 1
                if 0 <= idx < len(batch_times):
                    s["_t"] = batch_times[idx]
                    shots.append(s)
            overall = got.get("overall") or overall

        return _to_timeline(shots, times, total, material, silences, overall)
    finally:
        if own:
            shutil.rmtree(work, ignore_errors=True)


def _to_timeline(shots, times, total, material, silences, overall) -> dict[str, Any]:
    tl = empty_timeline(int(round(total)))
    by_t = {s["_t"]: s for s in shots}

    for i, t in enumerate(times):
        end = times[i + 1] if i + 1 < len(times) else total
        s = by_t.get(t, {})
        tl["shots"].append({
            "no": i + 1, "start": t, "seconds": round(max(0.5, end - t), 2),
            "beat": "", "look": s.get("look", ""), "motion": s.get("motion_guess", ""),
            "image_prompt": f"{s.get('look', '')}. {s.get('mood', '')}".strip(". "),
            "video_prompt": s.get("motion_guess", ""), "asset": "",
        })
        if s.get("has_character"):
            tl["cues"]["character"].append({
                "start": t, "seconds": round(max(0.5, end - t), 2),
                "text": s.get("character_what", ""), "note": "", "asset": "",
                "level": 1.0, "position": s.get("character_where") or "bottom-right",
            })

    for c in material.timed:
        tl["cues"]["caption"].append({"start": c["start"], "seconds": round(max(0.5, c.get("end", c["start"] + 3) - c["start"]), 2),
                                      "text": c["text"], "note": "", "asset": "", "level": 1.0, "position": ""})
        tl["cues"]["voice"].append({"start": c["start"], "seconds": round(max(0.5, c.get("end", c["start"] + 3) - c["start"]), 2),
                                    "text": c["text"], "note": "", "asset": "", "level": 1.0, "position": ""})

    quiet, music = classify_gaps(speech_gaps(material.timed, total), silences)
    for g in quiet:
        tl["cues"]["ambient"].append({**g, "text": "", "note": "침묵", "asset": "", "level": 0.0, "position": ""})
    for g in music:
        tl["cues"]["bgm"].append({**g, "text": "", "note": "말 없이 음악·환경음만", "asset": "", "level": 0.5, "position": ""})

    # 자막 꾸밈새 짐작: 가장 많이 나온 값
    def mode(key):
        vals = [s.get(key) for s in shots if s.get(key)]
        return max(set(vals), key=vals.count) if vals else ""

    reference = normalize(tl)
    reference["overall"] = {
        "visual_dna": overall.get("visual_dna", ""),
        "character_pattern": overall.get("character_pattern", ""),
        "caption_style_note": overall.get("caption_style_note", ""),
        "shot_rules": overall.get("shot_rules") or [],
        "caption_guess": {
            "position": mode("caption_position") or "bottom",
            "color": mode("caption_color") or "#FFFFFF",
            "size": mode("caption_size") or "medium",
            "background": any(s.get("caption_has_background") for s in shots),
        },
        "on_screen_texts": [s["on_screen_text"] for s in shots if s.get("on_screen_text")][:20],
        "silence_count": len(quiet),
        "music_only_count": len(music),
        "shot_count": len(times),
        "avg_shot_seconds": round(total / max(1, len(times)), 1),
    }
    return reference
