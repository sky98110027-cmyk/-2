# /// script
# requires-python = ">=3.10"
# ///
"""VOICEVOX GUI로 내보낸 WAV를 실측해 timing.json을 만든다. (경로 B 전용)

voicevox_tts.py는 localhost:50021 HTTP API에 붙는다. 샌드박스에서는 사용자 PC의
localhost에 닿을 수 없으므로, 그 경우 VOICEVOX 앱에서
  ファイル → テキスト読み込み → 音声書き出し
로 줄별 WAV를 뽑고 이 스크립트로 실측한다. 결과 포맷은 voicevox_tts.py와 동일하다.

VOICEVOX는 파일명을 `001_화자（스타일）_앞부분….wav` 형식으로 매긴다. 숫자 접두사가
텍스트란 순서이므로 그 순서를 신뢰한다. 불러오기 후 남는 빈 행이 0.2초 무음 파일을
만들기 때문에, MIN_SPEECH 미만은 대사가 아닌 것으로 보고 버린다.

사용법:
    uv run scripts/measure_timing.py projects/my-short
    uv run scripts/measure_timing.py projects/my-short --audio-dir audio_zundamon
"""

import argparse
import json
import re
import sys
import wave
from pathlib import Path

MIN_SPEECH = 0.5  # 이보다 짧은 파일은 빈 행이 만든 무음으로 간주한다
NUM_PREFIX = re.compile(r"^(\d+)_")


def die(msg: str) -> None:
    print(f"오류: {msg}", file=sys.stderr)
    sys.exit(1)


def duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def main() -> None:
    ap = argparse.ArgumentParser(description="GUI 내보낸 WAV로 timing.json 생성")
    ap.add_argument("project")
    ap.add_argument("--audio-dir", default="audio", help="프로젝트 하위 오디오 폴더명")
    args = ap.parse_args()

    proj = Path(args.project)
    script_path = proj / "script.json"
    if not script_path.exists():
        die(f"{script_path}를 찾을 수 없습니다")

    audio_dir = proj / args.audio_dir
    if not audio_dir.is_dir():
        die(f"{audio_dir}가 없습니다")

    # 숫자 접두사 순서 = 텍스트란 순서. 사전순은 10이 2 앞에 오므로 쓸 수 없다.
    wavs = sorted(
        (p for p in audio_dir.glob("*.wav") if NUM_PREFIX.match(p.name)),
        key=lambda p: int(NUM_PREFIX.match(p.name).group(1)),
    )
    if not wavs:
        die(f"{audio_dir}에 `001_...wav` 형식 파일이 없습니다")

    takes = [(p, duration(p)) for p in wavs]
    dropped = [p.name for p, d in takes if d < MIN_SPEECH]
    takes = [(p, d) for p, d in takes if d >= MIN_SPEECH]

    script = json.loads(script_path.read_text(encoding="utf-8"))
    lines = [(s.get("id", i + 1), l) for i, s in enumerate(script.get("scenes", []))
             for l in s.get("lines", [])
             if (l.get("tts") or l.get("sub", "")).strip()]

    if len(lines) != len(takes):
        die(
            f"대본 줄 {len(lines)}개 ≠ 유효 WAV {len(takes)}개.\n"
            f"     내보내기가 중간에 끊겼거나 텍스트란이 대본과 어긋났습니다.\n"
            f"     버려진 무음 파일: {dropped or '없음'}"
        )

    tcfg = script.get("timing", {})
    line_gap = tcfg.get("line_gap", 0.15)
    scene_gap = tcfg.get("scene_gap", 0.35)

    cursor = 0.0
    recs: list[dict] = []
    scene_starts: dict = {}

    for i, ((sid, line), (path, dur)) in enumerate(zip(lines, takes)):
        scene_starts.setdefault(sid, cursor)
        start, end = cursor, cursor + dur
        recs.append({
            "index": i,
            "scene": sid,
            "start": round(start, 3),
            "end": round(end, 3),
            "dur": round(dur, 3),
            "sub": line.get("sub", ""),
            "file": f"{args.audio_dir}/{path.name}",
        })
        is_last = i + 1 == len(lines)
        last_in_scene = is_last or lines[i + 1][0] != sid
        gap = 0.0 if is_last else (scene_gap if last_in_scene else line_gap)
        cursor = end + gap

    total = cursor

    # 블록 구간은 서로 맞닿게 만든다 — 영상 세그먼트 사이에 빈틈이 생기지 않도록.
    ids = list(scene_starts)
    scenes = []
    for j, sid in enumerate(ids):
        st = scene_starts[sid]
        en = scene_starts[ids[j + 1]] if j + 1 < len(ids) else total
        scenes.append({"id": sid, "start": round(st, 3), "end": round(en, 3),
                       "dur": round(en - st, 3)})

    (proj / "timing.json").write_text(
        json.dumps({"total_duration": round(total, 3), "lines": recs, "scenes": scenes},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    voice = script.get("voice", {})
    print(f"화자: {voice.get('character', '?')}（{voice.get('style', '?')}） speed {voice.get('speed', 1.0)}")
    for r in recs:
        print(f"  L{r['index']+1} 블록{r['scene']}  {r['start']:6.3f}-{r['end']:6.3f}  ({r['dur']:.3f}s)")
    print()
    for s in scenes:
        print(f"  블록{s['id']}  {s['dur']:6.3f}s  → 컷 {max(1, round(s['dur'] / 2))}개")
    print(f"\n총 {total:.3f}초")
    if dropped:
        print(f"무음으로 버린 파일: {', '.join(dropped)}")
    if total > 60:
        print("\n경고: 60초를 넘습니다. 쇼츠 규격을 벗어나므로 대본을 줄이세요.")
    elif total < 15:
        print("\n경고: 15초 미만입니다. 너무 짧으면 노출이 잘 안 붙습니다.")


if __name__ == "__main__":
    main()
