"""받아둔 파일을 재료로 바꾼다.

유튜브 링크만 받으면 반쪽이다.
이미 내려받아 둔 영상이나, 직접 쓴 대본 파일도 그대로 넣을 수 있어야 한다.

받는 것:
  .txt .md            직접 쓴 대본
  .srt .vtt .ass      자막 파일
  .mp4 .mov .mkv 등    영상 안에 자막이 박혀 있으면 꺼낸다
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .source import SourceMaterial, SourceUnavailable, _tidy, parse_vtt

글자파일 = {".txt", ".md"}
자막파일 = {".srt", ".vtt", ".ass", ".ssa"}
영상파일 = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".mp3", ".m4a", ".wav"}

받는것 = sorted(글자파일 | 자막파일 | 영상파일)

MAX_MB = 800


def parse_srt(raw: str) -> str:
    """SRT 자막을 평문으로. 형식이 VTT와 거의 같아서 같은 손질을 쓴다."""
    return parse_vtt(raw)


def parse_ass(raw: str) -> str:
    """ASS/SSA 자막에서 대사만 뽑는다."""
    lines: list[str] = []
    for line in raw.splitlines():
        if not line.startswith("Dialogue:"):
            continue
        # Dialogue: 0,0:00:01.00,0:00:04.00,Default,,0,0,0,,대사
        parts = line.split(",", 9)
        if len(parts) < 10:
            continue
        text = re.sub(r"\{[^}]*\}", "", parts[9])  # 꾸밈 태그를 털어낸다
        text = text.replace("\\N", " ").replace("\\n", " ").strip()
        if text and (not lines or lines[-1] != text):
            lines.append(text)
    return _tidy(" ".join(lines))


def read_text(path: Path) -> str:
    """인코딩이 뭐든 읽어낸다. 한국어 자막은 cp949 인 경우가 흔하다."""
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def ffmpeg_있나() -> bool:
    return shutil.which("ffmpeg") is not None


def _영상에서_자막꺼내기(path: Path) -> str:
    """영상 안에 자막 트랙이 박혀 있으면 꺼낸다."""
    if not ffmpeg_있나():
        raise SourceUnavailable(
            "영상에서 자막을 꺼내려면 ffmpeg 가 필요합니다.\n"
            "ffmpeg.org 에서 받아 깔아주시거나, 자막 파일(.srt)이나 대본을 대신 넣어주세요."
        )

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "sub.vtt"
        try:
            done = subprocess.run(
                ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:s:0", "-y", str(out)],
                capture_output=True,
                timeout=180,
            )
        except subprocess.TimeoutExpired as exc:
            raise SourceUnavailable(
                "영상을 읽다가 너무 오래 걸려서 멈췄습니다. 자막 파일을 대신 넣어주세요."
            ) from exc

        if done.returncode != 0 or not out.exists():
            raise SourceUnavailable(
                f"'{path.name}' 안에는 자막이 박혀 있지 않습니다.\n"
                "자막 파일(.srt)이나 대본을 대신 넣어주세요.\n"
                "영상에서 말을 글로 옮기는 일은 이 앱이 하지 못합니다."
            )
        return parse_vtt(read_text(out))


def from_file(path: str | Path, url: str = "") -> SourceMaterial:
    """파일 하나를 분석 재료로 바꾼다."""
    path = Path(path).expanduser()

    if not path.exists():
        raise SourceUnavailable(f"'{path}' 파일을 찾을 수 없습니다.")
    if not path.is_file():
        raise SourceUnavailable(f"'{path}' 은 파일이 아닙니다.")

    크기 = path.stat().st_size / (1024 * 1024)
    if 크기 > MAX_MB:
        raise SourceUnavailable(f"파일이 너무 큽니다 ({크기:.0f}MB). {MAX_MB}MB 아래로 줄여주세요.")

    확장자 = path.suffix.lower()

    if 확장자 in 글자파일:
        text, 출처 = _tidy(read_text(path), dedupe=False), f"대본 파일 ({path.name})"
    elif 확장자 == ".vtt":
        text, 출처 = parse_vtt(read_text(path)), f"자막 파일 ({path.name})"
    elif 확장자 == ".srt":
        text, 출처 = parse_srt(read_text(path)), f"자막 파일 ({path.name})"
    elif 확장자 in (".ass", ".ssa"):
        text, 출처 = parse_ass(read_text(path)), f"자막 파일 ({path.name})"
    elif 확장자 in 영상파일:
        text, 출처 = _영상에서_자막꺼내기(path), f"영상에 박힌 자막 ({path.name})"
    else:
        raise SourceUnavailable(
            f"'{확장자}' 는 받을 수 없는 종류입니다.\n받을 수 있는 것 : {', '.join(받는것)}"
        )

    if len(text) < 100:
        raise SourceUnavailable(
            f"'{path.name}' 에서 건진 글이 너무 짧습니다 ({len(text)}자).\n"
            "파일이 비었거나 형식이 다를 수 있습니다."
        )

    return SourceMaterial(url=url, title=path.stem, transcript=text, transcript_origin=출처)


def from_upload(filename: str, data: bytes, url: str = "") -> SourceMaterial:
    """화면에서 올린 파일을 받는다. 잠깐 디스크에 내렸다가 지운다."""
    이름 = Path(filename or "올린파일").name  # 경로를 붙여 보내도 이름만 쓴다
    확장자 = Path(이름).suffix.lower()

    if 확장자 not in (글자파일 | 자막파일 | 영상파일):
        raise SourceUnavailable(
            f"'{확장자 or 이름}' 는 받을 수 없는 종류입니다.\n"
            f"받을 수 있는 것 : {', '.join(받는것)}"
        )
    if len(data) > MAX_MB * 1024 * 1024:
        raise SourceUnavailable(
            f"파일이 너무 큽니다 ({len(data) / 1024 / 1024:.0f}MB). {MAX_MB}MB 아래로 줄여주세요."
        )

    with tempfile.TemporaryDirectory() as tmp:
        내린곳 = Path(tmp) / 이름
        내린곳.write_bytes(data)
        material = from_file(내린곳, url=url)

    material.title = Path(이름).stem
    return material
