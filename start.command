#!/bin/bash
# 맥에서 두 번 눌러 켜는 파일.
# 처음 한 번은 오른쪽 클릭 후 '열기' 를 눌러야 할 수 있습니다.
cd "$(dirname "$0")" || exit 1

if command -v python3 >/dev/null 2>&1; then
  python3 start.py
else
  echo ""
  echo "파이썬이 안 깔려 있습니다."
  echo "python.org 에서 받아 깔아주신 뒤 다시 눌러주세요."
  echo ""
  read -r -p "엔터를 치면 닫힙니다."
fi
