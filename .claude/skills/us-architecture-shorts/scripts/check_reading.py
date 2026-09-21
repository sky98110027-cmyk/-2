# /// script
# requires-python = ">=3.10"
# ///
"""영어 대본의 TTS 오독 위험과 자막 길이를 점검한다.

일본어판 check_yomi.py의 영어 대응물. 잡는 것은 네 가지다.

1. tts에 남은 숫자·단위·기호 — 엔진마다 다르게 읽고, 길이 예측이 어긋난다
2. 풀어 쓰지 않은 약어 — TMD를 단어로 읽어버리는 엔진이 있다
3. 동형이의어(heteronym) — 철자가 같고 발음이 갈리는 단어. 엔진이 반반으로 틀린다
4. 자막 한 줄이 화면 폭을 넘는지

**이 점검기는 어림수다.** 진짜 확인은 합성된 음성을 귀로 듣는 것이다.

사용법:
    uv run scripts/check_reading.py projects/my-short
"""

import argparse
import json
import re
import sys
from pathlib import Path

MAX_CHARS = 28          # build_ass.py와 같은 값을 유지한다
WPM = 150               # 담백한 해설체 기준. 대본 단계의 어림수일 뿐이다

DIGIT = re.compile(r"\d")
ACRONYM = re.compile(r"\b[A-Z]{2,}\b")
SYMBOL = re.compile(r"[%°×÷±′″¼½¾&@#/]")
ORDINAL = re.compile(r"\b\d+(st|nd|rd|th)\b", re.I)
ROMAN = re.compile(r"\b(?=[MDCLXVI]{2,}\b)M*(C[MD]|D?C{0,3})(X[CL]|L?X{0,3})(I[XV]|V?I{0,3})\b")

# 철자가 같고 발음이 갈리는 단어. 건축·구조 대본에서 실제로 걸리는 것들만 모았다.
HETERONYMS = {
    "lead": "금속 납 / 이끌다",
    "live": "살다 / 생중계",
    "bow": "활 / 숙이다",
    "wind": "바람 / 감다",
    "minute": "분 / 미세한",
    "close": "닫다 / 가까운",
    "tear": "찢다 / 눈물",
    "row": "줄 / 노젓다",
    "use": "쓰다(동사) / 쓰임(명사)",
    "present": "제시하다 / 현재",
    "object": "반대하다 / 물체",
    "subject": "종속시키다 / 주제",
    "conduct": "수행하다 / 행동",
    "contract": "수축하다 / 계약",
    "project": "투사하다 / 사업",
    "record": "기록하다 / 기록",
    "refuse": "거부하다 / 폐기물",
    "separate": "분리하다 / 별개의",
    "moderate": "조절하다 / 적당한",
    "alternate": "번갈다 / 대체의",
    "invalid": "무효한 / 환자",
    "bass": "저음 / 농어",
    "wound": "상처 / 감았다",
    "sow": "씨뿌리다 / 암퇘지",
    "resume": "재개하다 / 이력서",
    "buffet": "강타하다 / 뷔페",
    "console": "위로하다 / 콘솔",
}


def die(msg: str) -> None:
    print(f"오류: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    ap = argparse.ArgumentParser(description="영어 대본 오독·자막 길이 점검")
    ap.add_argument("project")
    args = ap.parse_args()

    proj = Path(args.project)
    script_path = proj / "script.json"
    if not script_path.exists():
        die(f"{script_path}를 찾을 수 없습니다")

    script = json.loads(script_path.read_text(encoding="utf-8"))

    problems: list[str] = []
    notes: list[str] = []
    word_total = 0
    line_no = 0

    for scene in script.get("scenes", []):
        for line in scene.get("lines", []):
            sub = (line.get("sub") or "").strip()
            tts = (line.get("tts") or sub).strip()
            if not tts:
                continue
            line_no += 1
            tag = f"[{line_no:03d}]"
            word_total += len(tts.split())

            if DIGIT.search(tts):
                problems.append(f"{tag} tts에 숫자가 남아 있습니다 → 영어 단어로 풀어 쓰세요: {tts}")
            if ORDINAL.search(tts):
                problems.append(f"{tag} 서수 표기(1st 등)는 풀어 쓰세요: {tts}")
            for m in ACRONYM.finditer(tts):
                problems.append(f"{tag} 약어 {m.group()} → 철자 읽기로 풀어 쓰세요 (예: T M D)")
            for m in SYMBOL.finditer(tts):
                problems.append(f"{tag} 기호 {m.group()!r} → 단어로 바꾸세요 (percent, degrees, by …)")
            if ROMAN.search(tts):
                notes.append(f"{tag} 로마 숫자로 보이는 표기가 있습니다: {tts}")

            for word in re.findall(r"[A-Za-z']+", tts.lower()):
                if word in HETERONYMS:
                    notes.append(f"{tag} '{word}' — {HETERONYMS[word]}. 합성 후 귀로 확인하세요")

            # build_ass.py가 단어 경계에서 알아서 끊으므로, 긴 줄 자체는 문제가 아니다.
            # 문제는 (1) 공백이 없어 끊을 수 없는 덩어리, (2) 네 줄 이상이 되어 화면을 넘는 경우.
            for part in sub.split("\\N"):
                longest = max((len(w) for w in part.split()), default=0)
                if longest > MAX_CHARS + 3:
                    problems.append(
                        f"{tag} {longest}자짜리 단어가 있어 끊을 수 없습니다 → 다른 말로 바꾸세요: {part}")
                elif -(-len(part) // MAX_CHARS) > 3:
                    problems.append(
                        f"{tag} 자막 {len(part)}자 → 네 줄 이상이 됩니다. 문장을 쪼개세요: {part}")

    if not line_no:
        die("대사가 하나도 없습니다")

    print(f"대사 {line_no}줄 / {word_total}단어")
    print(f"어림 길이 {word_total / WPM * 60:.1f}초  ← 대본 단계의 추정치일 뿐, 실측이 진짜다")

    if problems:
        print(f"\n■ 고쳐야 할 것 {len(problems)}건")
        for p in problems:
            print(f"  {p}")
    if notes:
        print(f"\n□ 귀로 확인할 것 {len(notes)}건")
        for n in dict.fromkeys(notes):
            print(f"  {n}")
    if not problems and not notes:
        print("\n걸리는 곳 없음")

    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
