#!/bin/bash
# 결(Gyeol) — 세션이 열릴 때 도는 것.
#
# 두 가지를 한다.
#   1. 파이썬 꾸러미를 깔아둔다. 그래야 테스트가 바로 돈다.
#   2. 지금 어디까지 했는지 한눈에 보여준다.
#
# 맥이든 윈도우든 웹이든 똑같이 돈다.

set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$ROOT" || exit 0

VENV="$ROOT/.venv"
PY="$VENV/bin/python"
[ -f "$VENV/Scripts/python.exe" ] && PY="$VENV/Scripts/python.exe"   # 윈도우

# ------------------------------------------------------------ 1. 꾸러미 깔기

if [ ! -x "$PY" ]; then
  echo "[결] 파이썬 자리를 만드는 중입니다…"
  (python3 -m venv "$VENV" || python -m venv "$VENV") >/dev/null 2>&1
  PY="$VENV/bin/python"
  [ -f "$VENV/Scripts/python.exe" ] && PY="$VENV/Scripts/python.exe"
fi

if [ -x "$PY" ]; then
  if ! "$PY" -c "import fastapi, anthropic, yt_dlp, pytest" >/dev/null 2>&1; then
    echo "[결] 필요한 꾸러미를 받는 중입니다. 처음 한 번만 걸립니다…"
    "$PY" -m pip install --quiet --upgrade pip >/dev/null 2>&1
    "$PY" -m pip install --quiet -r "$ROOT/requirements.txt" >/dev/null 2>&1 \
      && echo "[결] 준비 끝났습니다." \
      || echo "[결] 꾸러미 받기가 막혔습니다. 인터넷을 확인하고 pip install -r requirements.txt 를 직접 돌려주세요."
  fi
  echo "export GYEOL_PY=\"$PY\"" >> "${CLAUDE_ENV_FILE:-/dev/null}" 2>/dev/null || true
fi

# ------------------------------------------------------------ 2. 현황 보여주기

있나() { command -v "$1" >/dev/null 2>&1 && echo "있음" || echo "없음"; }

KEY="없음"
[ -n "${ANTHROPIC_API_KEY:-}" ] && KEY="환경변수에 있음"
[ -f "$ROOT/.env" ] && grep -q "ANTHROPIC_API_KEY=." "$ROOT/.env" 2>/dev/null && KEY=".env 에 있음"

SKILLS=0
[ -d "$ROOT/data/skills" ] && SKILLS=$(find "$ROOT/data/skills" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')

cat <<EOF

────────────────────────────────────────────────────────
 결(Gyeol) — 영상 한 편의 결을 스킬로 복제하는 제작 도구
────────────────────────────────────────────────────────

 브랜치   $(git branch --show-current 2>/dev/null || echo '?')
 마지막   $(git log -1 --format='%s (%cr)' 2>/dev/null || echo '?')
 클로드 키 $KEY
 ffmpeg   $(있나 ffmpeg)   ← 없으면 프레임 뜯기와 조립이 안 됩니다
 저장된 결 ${SKILLS}개

 ■ 다음에 할 일 (급한 순서)
   1. ffmpeg 조립을 실제로 돌려보기  ← 아직 한 번도 안 해봤습니다
   2. 유튜브 업로드를 화면에 잇기 (youtube.py 는 다 돼 있음)
   3. 화면 레이어에 힉스필드·톱뷰 MCP 잇기
   4. 환경음·음악 자리 채우기

 ■ 자주 쓰는 것
   앱 켜기      start.command (맥) · start.bat (윈도우)
   테스트       .venv/bin/python -m pytest -q
   자세한 내용   이어가기.md

────────────────────────────────────────────────────────
EOF

exit 0
