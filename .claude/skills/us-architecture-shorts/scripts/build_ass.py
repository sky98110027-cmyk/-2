# /// script
# requires-python = ">=3.10"
# ///
"""script.json + timing.json → subs.ass (1080x1920 세로영상용, 영어 자막)

영어 자막은 공백 단위로만 끊을 수 있다. 일본어판처럼 아무 데서나 자르면 단어가 쪼개진다.
여기서는 DP로 줄 길이를 고르게 맞추면서, 관사·전치사로 줄이 끝나는 자리에 벌점을 준다.
추정이 어긋나면 script.json의 sub 필드에 \\N을 직접 넣는다 — 수동 지정이 항상 우선한다.

사용법:
    uv run scripts/build_ass.py projects/my-short
"""

import argparse
import json
import sys
from pathlib import Path

# ── 스타일 (채널 톤에 맞게 조정) ──────────────────────────────
FONT = "Arial"          # 어디서나 있는 폰트. Inter / Noto Sans 로 교체 가능
FONT_SIZE = 64          # 1080폭 - 좌우마진 140 = 940px
MARGIN_V = 600          # 하단에서 띄울 거리. Shorts UI를 피해 y≈1250 부근에 온다
MARGIN_H = 70
OUTLINE = 6             # 두꺼운 테두리 — 밝은 배경에서도 읽히게
SHADOW = 3
MAX_CHARS = 28          # 한 줄 목표 글자수. 영문 64px Bold가 940px에 들어가는 상한
FADE_MS = 80

# 줄 끝에 오면 눈이 다음 줄로 끌려간다. 끊을 수는 있지만 벌점을 준다.
DANGLING = {
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "and", "or", "but",
    "is", "are", "was", "were", "be", "its", "it", "that", "this", "these",
    "with", "by", "from", "as", "than", "not", "no", "into", "over", "under",
    "per", "than", "so", "if", "when", "while", "each", "every", "one",
}
DANGLING_PENALTY = 120
MAX_OVERFLOW = 3        # MAX_CHARS를 이만큼까지는 넘겨도 화면에 들어간다


def ass_time(t: float) -> str:
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _line_cost(words: list[str], i: int, j: int) -> float:
    """words[i:j]를 한 줄로 놓았을 때의 벌점. 들어가지 않으면 무한대."""
    length = len(" ".join(words[i:j]))
    if length > MAX_CHARS + MAX_OVERFLOW:
        return float("inf")
    cost = (MAX_CHARS - length) ** 2
    tail = words[j - 1].strip(",.;:—-").lower()
    if j < len(words) and tail in DANGLING:
        cost += DANGLING_PENALTY
    return cost


def wrap(text: str) -> str:
    """줄 길이를 고르게 맞추며 단어 경계에서만 끊는다. \\N이 이미 있으면 그대로 존중한다."""
    if "\\N" in text:
        return text
    if len(text) <= MAX_CHARS:
        return text

    words = text.split()
    n = len(words)
    if n < 2:
        return text

    # best[i] = words[i:]를 끝까지 배치하는 최소 비용, 그때의 첫 줄 끝 위치.
    # best[n]은 남은 단어가 없는 상태라 비용 0. 이게 기저값이다.
    best: list[tuple[float, int]] = [(float("inf"), n)] * n + [(0.0, n)]
    for i in range(n - 1, -1, -1):
        acc = (float("inf"), n)
        for j in range(i + 1, n + 1):
            cost = _line_cost(words, i, j)
            if cost == float("inf"):
                break                       # 더 붙이면 더 길어지기만 한다
            total = cost + best[j][0]
            if total < acc[0]:
                acc = (total, j)
        best[i] = acc

    if best[0][0] == float("inf"):
        return text                         # 한 단어가 화면보다 길다. 손대지 않는다

    parts, i = [], 0
    while i < n:
        j = best[i][1]
        parts.append(" ".join(words[i:j]))
        i = j
    return "\\N".join(parts)


def header() -> str:
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{FONT},{FONT_SIZE},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{OUTLINE},{SHADOW},2,{MARGIN_H},{MARGIN_H},{MARGIN_V},1
Style: Key,{FONT},{FONT_SIZE},&H0000E5FF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{OUTLINE},{SHADOW},2,{MARGIN_H},{MARGIN_H},{MARGIN_V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="자막 .ass 생성 (영어)")
    ap.add_argument("project")
    ap.add_argument("--hold", action="store_true", default=True,
                    help="다음 자막이 나올 때까지 현재 자막을 유지한다 (기본값, 깜빡임 방지)")
    args = ap.parse_args()

    proj = Path(args.project)
    timing_path = proj / "timing.json"
    if not timing_path.exists():
        print("오류: timing.json이 없습니다. measure_timing.py를 먼저 실행하세요.", file=sys.stderr)
        sys.exit(1)

    script = json.loads((proj / "script.json").read_text(encoding="utf-8"))
    timing = json.loads(timing_path.read_text(encoding="utf-8"))

    # 줄별 스타일 지정을 찾기 위해 script.json 쪽 순서를 평탄화한다
    styles = []
    for scene in script.get("scenes", []):
        for line in scene.get("lines", []):
            if (line.get("tts") or line.get("sub", "")).strip():
                styles.append(line.get("style", "Default"))

    lines = timing["lines"]
    total = timing["total_duration"]
    out = [header()]
    long_lines = []

    for i, rec in enumerate(lines):
        text = rec["sub"].strip()
        if not text:
            continue

        start = rec["start"]
        if args.hold:
            end = lines[i + 1]["start"] if i + 1 < len(lines) else min(rec["end"] + 0.4, total)
        else:
            end = rec["end"]

        wrapped = wrap(text)
        style = "Key" if styles[i : i + 1] == ["key"] else "Default"

        for part in wrapped.split("\\N"):
            if len(part) > MAX_CHARS + MAX_OVERFLOW:
                long_lines.append((i, part))

        out.append(
            f"Dialogue: 0,{ass_time(start)},{ass_time(end)},{style},,0,0,0,,"
            f"{{\\fad({FADE_MS},{FADE_MS})}}{wrapped}"
        )

    dest = proj / "subs.ass"
    dest.write_text("\n".join(out) + "\n", encoding="utf-8-sig")

    print(f"{dest}  ({len(lines)}줄)")

    if long_lines:
        print(f"\n{len(long_lines)}개 줄이 {MAX_CHARS}자를 넘습니다. 화면에서 잘릴 수 있습니다:")
        for idx, part in long_lines[:6]:
            print(f"  [{idx:03d}] {len(part)}자  {part}")
        print("  → 문장을 줄이거나 sub 필드에 \\N으로 개행을 직접 지정하세요.")


if __name__ == "__main__":
    main()
