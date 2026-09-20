"""여섯 레이어를 mp4 하나로 묶는다.

ffmpeg 가 한다. 이 파일은 ffmpeg 에게 뭘 시킬지 정확히 적는 일만 한다.
명령을 문자열로 이어 붙이지 않는다. 리스트로 넘긴다. 파일 이름에 공백이 있어도 안 깨진다.

순서:
  1. 장면마다 그림 → 짧은 영상 조각 (천천히 확대되는 움직임)
  2. 조각들을 이어 붙인다
  3. 캐릭터 PNG 를 시간 맞춰 얹는다
  4. 목소리, 환경음, 배경음을 섞는다
  5. 자막을 굽는다
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from . import style as style_mod
from .timeline import LAYER_KEYS


class AssembleUnavailable(Exception):
    """조립을 못 할 때. 메시지는 그대로 화면에 뜬다."""


def ffmpeg_path() -> str:
    found = shutil.which("ffmpeg")
    if not found:
        raise AssembleUnavailable(
            "영상을 묶으려면 ffmpeg 가 필요합니다.\nffmpeg.org 에서 받아 깔아주세요. 맥은 brew install ffmpeg 한 줄입니다."
        )
    return found


def _size(aspect_ratio: str) -> tuple[int, int]:
    return style_mod.canvas_size(aspect_ratio)


# ------------------------------------------------------- 1. 장면 조각

def shot_command(
    image: Path, out: Path, seconds: float, aspect_ratio: str, motion: str = "push"
) -> list[str]:
    """그림 한 장을 seconds 초짜리 영상 조각으로. 천천히 확대하거나 옆으로 민다.

    옛 사진 위주 영상은 이 느린 움직임이 전부다. 급하게 움직이면 결이 깨진다.
    """
    w, h = _size(aspect_ratio)
    fps = 30
    frames = max(1, int(round(seconds * fps)))

    # 아주 천천히. 끝까지 가도 8퍼센트만 커진다.
    if motion == "pan":
        zoom = "1.08"
        x = f"(iw-iw/zoom)*on/{frames}"
        y = "(ih-ih/zoom)/2"
    elif motion == "still":
        zoom, x, y = "1.0", "0", "0"
    else:  # push
        zoom = f"min(1.0+0.08*on/{frames},1.08)"
        x = "(iw-iw/zoom)/2"
        y = "(ih-ih/zoom)/2"

    vf = (
        f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,"
        f"crop={w * 2}:{h * 2},"
        f"zoompan=z='{zoom}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps={fps},"
        f"format=yuv420p"
    )
    return [
        ffmpeg_path(), "-y", "-v", "error",
        "-loop", "1", "-i", str(image),
        "-vf", vf, "-t", f"{seconds:.3f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-r", str(fps),
        "-an", str(out),
    ]


def clip_command(video: Path, out: Path, seconds: float, aspect_ratio: str) -> list[str]:
    """이미 영상인 장면은 크기만 맞추고 길이만 자른다."""
    w, h = _size(aspect_ratio)
    vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps=30,format=yuv420p"
    return [
        ffmpeg_path(), "-y", "-v", "error",
        "-i", str(video), "-t", f"{seconds:.3f}", "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-an", str(out),
    ]


# ------------------------------------------------------- 2. 이어 붙이기

def concat_command(parts: list[Path], list_file: Path, out: Path) -> list[str]:
    list_file.write_text(
        "".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8"
    )
    return [
        ffmpeg_path(), "-y", "-v", "error",
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c", "copy", str(out),
    ]


# ------------------------------------------------------- 3~5. 얹고 섞고 굽기

def mix_command(
    base_video: Path,
    out: Path,
    *,
    voice: list[tuple[Path, float]] | None = None,
    ambient: list[tuple[Path, float, float]] | None = None,
    bgm: tuple[Path, float] | None = None,
    characters: list[tuple[Path, float, float, str]] | None = None,
    subtitles: Path | None = None,
    total_seconds: float = 0,
) -> list[str]:
    """영상 한 편 위에 소리와 캐릭터와 자막을 한 번에 얹는다.

    voice      : [(파일, 시작초)]
    ambient    : [(파일, 시작초, 크기 0~1)]
    bgm        : (파일, 크기 0~1)  전체에 깔리고 목소리 있을 때 살짝 죽는다
    characters : [(PNG, 시작초, 길이초, 자리)]  자리는 'bottom-right' 같은 말
    subtitles  : ASS 파일
    """
    cmd = [ffmpeg_path(), "-y", "-v", "error", "-i", str(base_video)]
    filters: list[str] = []
    inputs = 1

    # ---- 소리 입력들
    audio_labels: list[str] = []

    for path, start in voice or []:
        cmd += ["-i", str(path)]
        filters.append(f"[{inputs}:a]adelay={int(start * 1000)}|{int(start * 1000)},volume=1.0[v{inputs}]")
        audio_labels.append(f"[v{inputs}]")
        inputs += 1

    for path, start, level in ambient or []:
        cmd += ["-i", str(path)]
        filters.append(
            f"[{inputs}:a]adelay={int(start * 1000)}|{int(start * 1000)},volume={_lvl(level)}[a{inputs}]"
        )
        audio_labels.append(f"[a{inputs}]")
        inputs += 1

    if bgm:
        path, level = bgm
        cmd += ["-stream_loop", "-1", "-i", str(path)]
        # 목소리보다 한참 작게. 나레이션 채널은 음악이 앞에 나서면 안 된다.
        filters.append(f"[{inputs}:a]volume={_lvl(level)}[m{inputs}]")
        audio_labels.append(f"[m{inputs}]")
        inputs += 1

    if audio_labels:
        filters.append(
            "".join(audio_labels)
            + f"amix=inputs={len(audio_labels)}:duration=first:dropout_transition=2:normalize=0[aout]"
        )

    # ---- 캐릭터 얹기
    video_label = "[0:v]"
    for i, (png, start, seconds, place) in enumerate(characters or []):
        cmd += ["-i", str(png)]
        x, y = _place(place)
        filters.append(
            f"{video_label}[{inputs}:v]overlay={x}:{y}:enable='between(t,{start:.2f},{start + seconds:.2f})'[c{i}]"
        )
        video_label = f"[c{i}]"
        inputs += 1

    # ---- 자막 굽기
    if subtitles:
        sub = str(subtitles).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        filters.append(f"{video_label}subtitles='{sub}'[vout]")
        video_label = "[vout]"

    if filters:
        cmd += ["-filter_complex", ";".join(filters)]

    cmd += ["-map", video_label if video_label != "[0:v]" else "0:v"]
    if audio_labels:
        cmd += ["-map", "[aout]"]
    else:
        cmd += ["-an"]

    if total_seconds:
        cmd += ["-t", f"{total_seconds:.3f}"]

    cmd += [
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out),
    ]
    return cmd


def _lvl(level: float) -> str:
    try:
        return f"{max(0.0, min(float(level), 1.0)):.2f}"
    except (TypeError, ValueError):
        return "0.5"


def _place(place: str) -> tuple[str, str]:
    """캐릭터가 앉을 자리. 가장자리에서 40px 띄운다."""
    p = (place or "bottom-right").lower()
    x = "40" if "left" in p else ("(W-w)/2" if "center" in p and "right" not in p else "W-w-40")
    y = "40" if "top" in p else ("(H-h)/2" if "middle" in p else "H-h-40")
    return x, y


# ------------------------------------------------------- ASS 자막 파일

def write_ass(
    cues: list[dict[str, Any]], style: dict[str, Any], out: Path
) -> Path:
    """자막 큐들을 ASS 파일로. 꾸밈새는 style.py 가 만든 그대로 쓴다."""
    look = style_mod.normalize(style)
    w, h = _size(look["aspect_ratio"])
    header = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {w}\nPlayResY: {h}\nWrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        + _ass_style_line(look, "caption")
        + "\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    lines = []
    for c in cues:
        text = str(c.get("text") or "").replace("\n", "\\N")
        if not text:
            continue
        start = float(c.get("start") or 0)
        end = start + float(c.get("seconds") or 3)
        lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},caption,,0,0,0,,{text}")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    return out


def _ass_style_line(look: dict[str, Any], layer: str) -> str:
    """style.to_ass_style 이 준 '이름: 값' 줄들을 ASS 의 한 줄 형식으로 접는다."""
    fields = dict(
        line.split(": ", 1) for line in style_mod.to_ass_style(look, layer).splitlines() if ": " in line
    )
    s = look[layer]
    return (
        f"Style: {layer},{fields['Fontname']},{fields['Fontsize']},{fields['PrimaryColour']},"
        f"{fields['PrimaryColour']},{fields['OutlineColour']},{fields['BackColour']},"
        f"{fields['Bold']},0,0,0,100,100,0,0,{fields['BorderStyle']},{fields['Outline']},"
        f"0,{fields['Alignment']},{fields['MarginL']},{fields['MarginR']},{fields['MarginV']},1\n"
    )


def _ass_time(sec: float) -> str:
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


# ------------------------------------------------------- 전체 묶기

def build(
    tl: dict[str, Any],
    style: dict[str, Any],
    work: Path,
    out: Path,
    *,
    screen_assets: dict[int, Path],
    voice_assets: dict[int, Path] | None = None,
    ambient_assets: dict[int, Path] | None = None,
    bgm_file: Path | None = None,
    character_assets: dict[int, Path] | None = None,
    run: Callable[[list[str]], None] | None = None,
    on_step: Callable[[str], None] | None = None,
) -> Path:
    """타임라인 하나를 mp4 로. 실제 실행은 run 에 맡긴다 (테스트에서는 가짜를 넣는다)."""
    run = run or _run
    say = on_step or (lambda _: None)
    work.mkdir(parents=True, exist_ok=True)

    missing = [s["no"] for s in tl["shots"] if s["no"] not in screen_assets]
    if missing:
        raise AssembleUnavailable(
            f"장면 {', '.join(map(str, missing))} 번 그림이 없습니다.\n"
            "화면 레이어 제공자로 그림을 먼저 뽑거나, 내 그림 폴더에 번호대로 넣어주세요."
        )

    # 1. 장면 조각
    parts: list[Path] = []
    for shot in tl["shots"]:
        src = screen_assets[shot["no"]]
        part = work / f"shot_{shot['no']:03d}.mp4"
        say(f"{shot['no']}번 장면 만드는 중")
        if src.suffix.lower() in (".mp4", ".mov", ".webm", ".mkv"):
            run(clip_command(src, part, shot["seconds"], tl["aspect_ratio"]))
        else:
            motion = "pan" if "pan" in (shot.get("motion") or "").lower() else (
                "still" if "static" in (shot.get("motion") or "").lower() else "push")
            run(shot_command(src, part, shot["seconds"], tl["aspect_ratio"], motion))
        parts.append(part)

    # 2. 이어 붙이기
    say("장면 이어 붙이는 중")
    joined = work / "joined.mp4"
    run(concat_command(parts, work / "parts.txt", joined))

    # 3~5. 소리, 캐릭터, 자막
    voice = [(voice_assets[s["no"]], s["start"]) for s in tl["shots"]
             if voice_assets and s["no"] in voice_assets]
    ambient = [(ambient_assets[s["no"]], s["start"], 0.4) for s in tl["shots"]
               if ambient_assets and s["no"] in ambient_assets]
    bgm_level = next((c["level"] for c in tl["cues"].get("bgm") or []), 0.3)
    bgm = (bgm_file, bgm_level) if bgm_file else None

    characters = []
    for i, cue in enumerate(tl["cues"].get("character") or [], 1):
        png = (character_assets or {}).get(i)
        if png:
            characters.append((png, cue["start"], cue["seconds"] or 3.0, cue.get("position") or "bottom-right"))

    subs = None
    if tl["providers"].get("caption") == "builtin" and tl["cues"].get("caption"):
        subs = write_ass(tl["cues"]["caption"], style, work / "caption.ass")

    say("소리와 자막 얹는 중")
    out.parent.mkdir(parents=True, exist_ok=True)
    run(mix_command(joined, out, voice=voice, ambient=ambient, bgm=bgm,
                    characters=characters, subtitles=subs, total_seconds=tl["total_seconds"]))
    return out


def _run(cmd: list[str]) -> None:
    done = subprocess.run(cmd, capture_output=True, text=True)
    if done.returncode != 0:
        tail = (done.stderr or "").strip().splitlines()[-3:]
        raise AssembleUnavailable("ffmpeg 가 멈췄습니다.\n" + "\n".join(tail))
