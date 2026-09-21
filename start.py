"""결 시작하기.

처음 한 번만 준비를 하고, 그다음부터는 바로 켜진다.

맥이면 start.command, 윈도우면 start.bat 을 두 번 누르면
이 파일이 알아서 돈다. 터미널을 직접 열 일은 없다.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
ENV_FILE = ROOT / ".env"
PORT = int(os.environ.get("GYEOL_PORT", "8000"))


def 알림(글: str) -> None:
    print(f"\n{글}", flush=True)


def 파이썬() -> Path:
    """가상환경 안의 파이썬 자리."""
    return VENV / ("Scripts" if os.name == "nt" else "bin") / (
        "python.exe" if os.name == "nt" else "python"
    )


def 준비하기() -> None:
    """처음 한 번만 도는 설치 과정."""
    if not VENV.exists():
        알림("처음이라 준비를 좀 하겠습니다. 1분에서 3분쯤 걸립니다.")
        subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)

    확인 = subprocess.run(
        [str(파이썬()), "-c", "import fastapi, anthropic, yt_dlp"],
        capture_output=True,
    )
    if 확인.returncode != 0:
        알림("필요한 것들을 받는 중입니다. 기다려주세요.")
        subprocess.run(
            [str(파이썬()), "-m", "pip", "install", "--quiet", "--upgrade", "pip"],
            check=False,
        )
        subprocess.run(
            [str(파이썬()), "-m", "pip", "install", "--quiet", "-r", str(ROOT / "requirements.txt")],
            check=True,
        )
        알림("준비 끝났습니다.")


def 키읽기() -> str:
    """환경변수에 있으면 그걸 쓰고, 없으면 .env 파일을 본다."""
    키 = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if 키:
        return 키

    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "ANTHROPIC_API_KEY":
                return value.strip().strip('"').strip("'")
    return ""


def 키받기() -> str:
    """키가 없으면 한 번만 물어보고 파일에 적어둔다."""
    키 = 키읽기()
    if 키:
        return 키

    알림(
        "클로드 API 키가 필요합니다.\n"
        "  console.anthropic.com 에서 키를 하나 만드신 다음\n"
        "  여기에 붙여넣고 엔터를 쳐주세요.\n"
        "  한 번만 적으시면 다음부터는 안 물어봅니다.\n"
    )
    try:
        키 = input("  키 : ").strip()
    except (EOFError, KeyboardInterrupt):
        키 = ""

    if not 키:
        알림("키가 없으면 켤 수 없습니다. 키를 받으신 뒤에 다시 눌러주세요.")
        raise SystemExit(1)

    ENV_FILE.write_text(f"ANTHROPIC_API_KEY={키}\n", encoding="utf-8")
    if os.name != "nt":
        ENV_FILE.chmod(0o600)  # 남이 못 읽게
    알림(f"키를 {ENV_FILE.name} 에 적어뒀습니다. 이 파일은 남에게 보여주지 마세요.")
    return 키


def 켜기(키: str) -> None:
    환경 = dict(os.environ, ANTHROPIC_API_KEY=키, PYTHONUNBUFFERED="1")
    주소 = f"http://127.0.0.1:{PORT}"

    알림(
        f"결을 켭니다.\n"
        f"  잠시 뒤 브라우저가 스스로 열립니다.\n"
        f"  안 열리면 주소창에 {주소} 를 치시면 됩니다.\n"
        f"  끄실 때는 이 검은 창을 닫으시면 됩니다.\n"
    )

    서버 = subprocess.Popen(
        [str(파이썬()), "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=str(ROOT / "src"),
        env=환경,
    )

    time.sleep(2.5)  # 서버가 뜰 틈을 준다
    if 서버.poll() is None:
        webbrowser.open(주소)

    try:
        서버.wait()
    except KeyboardInterrupt:
        서버.terminate()
        알림("껐습니다.")


def main() -> None:
    if sys.version_info < (3, 10):
        알림(
            f"파이썬이 너무 오래됐습니다 (지금 {sys.version_info.major}.{sys.version_info.minor}).\n"
            "python.org 에서 최신 파이썬을 받아 깔아주세요."
        )
        raise SystemExit(1)

    os.chdir(ROOT)
    try:
        준비하기()
        켜기(키받기())
    except subprocess.CalledProcessError as exc:
        알림(f"준비하다가 막혔습니다.\n{exc}\n인터넷 연결을 확인하고 다시 눌러주세요.")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
