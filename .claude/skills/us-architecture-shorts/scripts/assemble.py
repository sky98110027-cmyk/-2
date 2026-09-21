# /// script
# requires-python = ">=3.10"
# ///
"""FFmpeg 9:16 조립.

클립을 씬 길이에 맞춰 1080x1920으로 정규화하고, 나레이션을 얹고, 자막을 굽고,
라우드니스를 -14 LUFS로 맞춘다.

클립이 없는 씬은 단색으로 채우고 계속 진행한다. 비주얼을 다 모으기 전에도 전체 흐름을
확인할 수 있어야 반복이 빨라지기 때문이다. 나중에 clips/에 파일만 채우고 다시 돌리면 된다.

사용법:
    uv run scripts/assemble.py projects/my-short
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# ffmpeg를 PATH에 등록하려면 환경변수를 건드려야 하는데, 그게 막히는 환경이 있다.
# 그래서 흔한 설치 위치를 직접 뒤진다. PATH 수정 없이도 동작하게 하는 게 목적이다.
FFMPEG_SEARCH = [
    Path.home() / "Videos" / "클로드" / "tools",
    Path.home() / ".local" / "tools",
    Path("C:/Program Files/ffmpeg"),
    Path("C:/ffmpeg"),
]


def ensure_ffmpeg() -> str | None:
    """PATH에 있으면 그대로 쓰고, 없으면 알려진 위치에서 찾아 PATH에 임시로 얹는다."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    for root in FFMPEG_SEARCH:
        if not root.is_dir():
            continue
        for exe in root.rglob("ffmpeg.exe"):
            os.environ["PATH"] = str(exe.parent) + os.pathsep + os.environ.get("PATH", "")
            return str(exe)
    return None

W, H, FPS = 1080, 1920, 30
PLACEHOLDER_COLOR = "0x0E1116"
VIDEO_EXT = (".mp4", ".mov", ".mkv", ".webm", ".m4v")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")

FIT = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1"


def die(msg: str) -> None:
    print(f"오류: {msg}", file=sys.stderr)
    sys.exit(1)


def run(cmd: list[str], cwd: Path) -> None:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or "").strip().splitlines()[-15:])
        die(f"ffmpeg 실패:\n{tail}")


def find_clip(clips_dir: Path, scene_id: int) -> Path | None:
    if not clips_dir.is_dir():
        return None
    stems = (f"scene_{scene_id:02d}", f"scene_{scene_id}")
    for stem in stems:
        for ext in VIDEO_EXT + IMAGE_EXT:
            p = clips_dir / f"{stem}{ext}"
            if p.exists():
                return p
    return None


def build_segment(proj: Path, src: Path | None, dur: float, dest_rel: str) -> None:
    """씬 하나를 규격에 맞는 무음 세그먼트로 만든다."""
    if src is None:
        cmd = ["ffmpeg", "-y", "-f", "lavfi",
               "-i", f"color=c={PLACEHOLDER_COLOR}:s={W}x{H}:r={FPS}", "-t", f"{dur:.3f}"]
    elif src.suffix.lower() in IMAGE_EXT:
        cmd = ["ffmpeg", "-y", "-loop", "1", "-i", str(src), "-t", f"{dur:.3f}"]
    else:
        # 클립이 씬보다 짧으면 반복해서 채운다
        cmd = ["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(src), "-t", f"{dur:.3f}"]

    cmd += ["-vf", FIT, "-an",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-pix_fmt", "yuv420p", dest_rel]
    run(cmd, cwd=proj)


def main() -> None:
    ap = argparse.ArgumentParser(description="9:16 쇼츠 조립")
    ap.add_argument("project")
    ap.add_argument("--no-subs", action="store_true", help="자막을 굽지 않는다")
    ap.add_argument("--out", default="out/final.mp4")
    args = ap.parse_args()

    exe = ensure_ffmpeg()
    if not exe:
        die("ffmpeg를 찾을 수 없습니다.\n"
            "     zip을 받아 풀기만 하면 됩니다 (PATH 등록 불필요):\n"
            "     https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip\n"
            f"     푼 위치를 이 목록 중 하나에 두세요: {[str(p) for p in FFMPEG_SEARCH]}")
    print(f"ffmpeg: {exe}")

    proj = Path(args.project)
    timing_path = proj / "timing.json"
    if not timing_path.exists():
        die("timing.json이 없습니다. voicevox_tts.py를 먼저 실행하세요.")

    narration = proj / "audio" / "narration.wav"
    if not narration.exists():
        die("audio/narration.wav가 없습니다. voicevox_tts.py를 먼저 실행하세요.")

    timing = json.loads(timing_path.read_text(encoding="utf-8"))
    scenes = timing["scenes"]

    work = proj / "_work"
    work.mkdir(exist_ok=True)
    (proj / "out").mkdir(exist_ok=True)

    clips_dir = proj / "clips"
    missing: list[int] = []
    seg_rels: list[str] = []

    print(f"{len(scenes)}개 씬 정규화 중...")
    for i, scene in enumerate(scenes):
        dur = max(scene["end"] - scene["start"], 0.1)
        src = find_clip(clips_dir, scene["id"])
        if src is None:
            missing.append(scene["id"])

        rel = f"_work/seg_{i:02d}.mp4"
        build_segment(proj, src, dur, rel)
        seg_rels.append(rel)
        label = src.name if src else "(단색 배경)"
        print(f"  씬 {scene['id']:>2}  {dur:5.2f}s  {label}")

    listing = work / "segments.txt"
    listing.write_text(
        "".join(f"file '{r}'\n" for r in seg_rels), encoding="utf-8"
    )

    # subtitles 필터는 Windows 경로의 콜론·역슬래시를 필터 문법으로 해석한다.
    # 프로젝트 폴더를 cwd로 두고 상대 경로를 쓰면 이 문제가 사라진다.
    subs = proj / "subs.ass"
    use_subs = subs.exists() and not args.no_subs
    if not use_subs and not args.no_subs:
        print("\n참고: subs.ass가 없어 자막 없이 조립합니다. (build_ass.py 먼저 실행)")

    cmd = ["ffmpeg", "-y",
           "-f", "concat", "-safe", "0", "-i", "_work/segments.txt",
           "-i", "audio/narration.wav"]
    if use_subs:
        cmd += ["-vf", "subtitles=subs.ass"]
    cmd += ["-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", "-shortest", args.out]

    print("\n최종 인코딩 중...")
    run(cmd, cwd=proj)

    final = proj / args.out
    size_mb = final.stat().st_size / 1024 / 1024
    print(f"\n완성: {final}  ({timing['total_duration']:.1f}초 / {size_mb:.1f}MB)")

    if missing:
        ids = ", ".join(str(i) for i in missing)
        print(f"\n씬 {ids}는 클립이 없어 단색으로 채웠습니다.")
        print(f"  clips/scene_XX.mp4 형식으로 넣고 다시 실행하면 그 씬만 채워집니다.")


if __name__ == "__main__":
    main()
