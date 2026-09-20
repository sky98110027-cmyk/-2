"""앱 전역 설정. 환경변수로 바꿀 수 있는 값만 모아둔다."""

import os
from pathlib import Path

# src/gyeol/config.py -> src/gyeol -> src -> 프로젝트 루트
ROOT = Path(__file__).resolve().parent.parent.parent

DATA_DIR = Path(os.environ.get("GYEOL_DATA_DIR", ROOT / "data"))
SKILLS_DIR = DATA_DIR / "skills"
PROJECTS_DIR = DATA_DIR / "projects"

# 스킬을 클로드 코드에서도 바로 쓸 수 있게 설치하는 위치
CLAUDE_SKILLS_DIR = Path(
    os.environ.get("GYEOL_CLAUDE_SKILLS_DIR", ROOT / ".claude" / "skills")
)

MODEL = os.environ.get("GYEOL_MODEL", "claude-opus-5")

# 기본 시청 타깃. 채널이 바뀌면 환경변수로 덮어쓴다.
DEFAULT_AUDIENCE = os.environ.get("GYEOL_AUDIENCE", "40~60대 시니어 시청자")


def ensure_dirs() -> None:
    for d in (DATA_DIR, SKILLS_DIR, PROJECTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
