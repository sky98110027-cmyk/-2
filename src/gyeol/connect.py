"""연결 관리.

클로드가 1순위다. 이게 없으면 아무것도 안 돈다.
나머지 영상 생성 도구는 있으면 좋고 없어도 된다.

키는 .env 파일에 적어둔다.
화면으로 내보낼 때는 절대 통째로 내보내지 않는다. 끝 네 자리만 보여준다.
MCP 설정은 .mcp.json 에 적는다. 클로드 코드가 읽는 그 파일이다.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from .config import ROOT

ENV_FILE = ROOT / ".env"
MCP_FILE = ROOT / ".mcp.json"

# 화면에 보여줄 연결 목록. 순서가 화면 순서다. 클로드가 맨 위.
#
# MCP 주소는 일부러 비워둔다.
# 회사마다 주소가 다르고 자주 바뀐다. 지어내서 적어두면 형님이 헤맨다.
# 어디서 받아오는지만 적어두고, 받은 주소를 붙여넣게 한다.
연결목록: list[dict[str, Any]] = [
    {
        "key": "ANTHROPIC_API_KEY",
        "name": "클로드",
        "required": True,
        "does": "대본 쓰기 · 결 뽑기 · 고치기",
        "note": "이게 있어야 결을 뽑고 대본을 씁니다. 없으면 아무것도 안 돕니다.",
        "where": "console.anthropic.com",
        "mcp_hint": "",
    },
    {
        "key": "HIGGSFIELD_API_KEY",
        "name": "힉스필드",
        "required": False,
        "does": "장면 그림 · 영상 움직임",
        "note": "장면마다 만들어진 영문 프롬프트로 그림과 영상을 뽑습니다.",
        "where": "higgsfield.ai",
        "mcp_hint": "힉스필드 계정 설정에서 MCP 주소를 받아 아래에 붙여넣으세요.",
    },
    {
        "key": "TOPVIEW_API_KEY",
        "name": "톱뷰",
        "required": False,
        "does": "장면 그림 · 영상 움직임",
        "note": "힉스필드 대신 써도 됩니다. 둘 중 하나만 있으면 됩니다.",
        "where": "topview.ai",
        "mcp_hint": "톱뷰 계정 설정에서 MCP 주소를 받아 아래에 붙여넣으세요.",
    },
    {
        "key": "ELEVENLABS_API_KEY",
        "name": "일레븐랩스",
        "required": False,
        "does": "나레이션 목소리",
        "note": "나레이션 원고를 사람 목소리로 읽어줍니다. 직접 녹음하시면 없어도 됩니다.",
        "where": "elevenlabs.io",
        "mcp_hint": "일레븐랩스 설정에서 MCP 주소를 받아 아래에 붙여넣으세요.",
    },
]

# 영상 한 편이 나오기까지 거쳐야 할 단계.
# 각 단계에 무엇이 필요한지, 없으면 어떻게 우회하는지 적어둔다.
제작단계: list[dict[str, Any]] = [
    {
        "step": "대본과 장면 짜기",
        "needs": ["ANTHROPIC_API_KEY"],
        "required": True,
        "detour": "",
        "how": "이 앱이 합니다. 주제만 주시면 됩니다.",
    },
    {
        "step": "장면 그림 뽑기",
        "needs": ["HIGGSFIELD_API_KEY", "TOPVIEW_API_KEY"],
        "required": False,
        "detour": "장면마다 영문 프롬프트가 나옵니다. 아무 이미지 도구에나 붙여넣으셔도 됩니다.",
        "how": "둘 중 하나만 붙어 있으면 됩니다.",
    },
    {
        "step": "그림에 움직임 넣기",
        "needs": ["HIGGSFIELD_API_KEY", "TOPVIEW_API_KEY"],
        "required": False,
        "detour": "움직임 없이 정지 사진만 써도 됩니다. 옛날 사진 위주 영상이면 오히려 어울립니다.",
        "how": "그림 뽑는 도구가 같이 합니다.",
    },
    {
        "step": "나레이션 목소리",
        "needs": ["ELEVENLABS_API_KEY"],
        "required": False,
        "detour": "나레이션 원고가 나오니 직접 읽어서 녹음하셔도 됩니다.",
        "how": "원고를 그대로 읽어줍니다.",
    },
    {
        "step": "자막 굽고 붙이기",
        "needs": [],
        "required": False,
        "detour": "편집 프로그램에서 직접 붙이셔도 됩니다.",
        "how": "ffmpeg 가 깔려 있으면 자막 설정 파일을 그대로 씁니다.",
        "tool": "ffmpeg",
    },
]

_KEY_NAME = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")


def mask(value: str) -> str:
    """끝 네 자리만 남긴다. 통째로 내보내는 일은 없어야 한다."""
    value = str(value or "")
    if not value:
        return ""
    if len(value) <= 8:
        return "•" * len(value)
    return "•" * 8 + value[-4:]


# ------------------------------------------------------------------ .env

def read_env() -> dict[str, str]:
    """.env 파일을 읽는다. 없으면 빈 것."""
    if not ENV_FILE.exists():
        return {}

    out: dict[str, str] = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, sep, value = line.partition("=")
        if sep:
            out[name.strip()] = value.strip().strip('"').strip("'")
    return out


def write_env(values: dict[str, str]) -> None:
    """.env 를 다시 쓴다. 남이 못 읽게 잠근다."""
    lines = ["# 결(Gyeol) 연결 정보입니다.", "# 이 파일은 남에게 보여주지 마세요.", ""]
    for name, value in sorted(values.items()):
        if value:
            lines.append(f"{name}={value}")

    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if os.name != "nt":
        ENV_FILE.chmod(0o600)


def get_value(key: str) -> str:
    """환경변수가 먼저, 없으면 .env."""
    return os.environ.get(key, "") or read_env().get(key, "")


def set_values(changes: dict[str, str]) -> list[str]:
    """바꿀 것만 바꾼다. 빈 값을 주면 그 항목을 지운다.

    지금 돌고 있는 앱에도 바로 먹게 환경변수까지 같이 바꾼다.
    앱을 다시 켤 필요가 없어야 한다.
    """
    values = read_env()
    바뀐것: list[str] = []

    for name, value in (changes or {}).items():
        name = str(name).strip()
        if not _KEY_NAME.match(name):
            continue

        value = str(value or "").strip()
        if value == "":
            if values.pop(name, None) is not None:
                os.environ.pop(name, None)
                바뀐것.append(name)
        elif values.get(name) != value:
            values[name] = value
            os.environ[name] = value
            바뀐것.append(name)

    if 바뀐것:
        write_env(values)
    return 바뀐것


def status() -> list[dict[str, Any]]:
    """화면에 뿌릴 연결 상태. 키는 가려서 나간다."""
    out = []
    for spec in 연결목록:
        value = get_value(spec["key"])
        out.append(
            {
                **spec,
                "connected": bool(value),
                "masked": mask(value),
                "from_env": bool(os.environ.get(spec["key"]) and spec["key"] not in read_env()),
            }
        )
    return out


def test_claude() -> tuple[bool, str]:
    """클로드 키가 진짜 되는지 한 번 찔러본다."""
    if not get_value("ANTHROPIC_API_KEY"):
        return False, "키를 먼저 넣어주세요."

    try:
        import anthropic
    except ImportError:
        return False, "anthropic 패키지가 없습니다."

    try:
        anthropic.Anthropic().models.list(limit=1)
    except anthropic.AuthenticationError:
        return False, "키가 틀렸습니다. 다시 확인해주세요."
    except anthropic.PermissionDeniedError:
        return False, "이 키로는 쓸 수 없습니다. 권한을 확인해주세요."
    except anthropic.APIConnectionError:
        return False, "클로드에 연결이 안 됩니다. 인터넷을 확인해주세요."
    except Exception as exc:
        return False, f"확인하지 못했습니다. {exc}"

    return True, "잘 연결됐습니다."


# ----------------------------------------------------------------- MCP

def read_mcp() -> dict[str, Any]:
    """.mcp.json 을 읽는다. 클로드 코드가 읽는 그 파일이다."""
    if not MCP_FILE.exists():
        return {"mcpServers": {}}
    try:
        data = json.loads(MCP_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"mcpServers": {}}
    if not isinstance(data.get("mcpServers"), dict):
        data["mcpServers"] = {}
    return data


def list_mcp() -> list[dict[str, Any]]:
    """등록된 MCP 목록. 어디에 붙는지만 보여준다."""
    out = []
    for name, cfg in (read_mcp().get("mcpServers") or {}).items():
        cfg = cfg if isinstance(cfg, dict) else {}
        out.append(
            {
                "name": name,
                "kind": "주소" if cfg.get("url") else "프로그램",
                "target": cfg.get("url") or cfg.get("command", ""),
                "args": cfg.get("args") or [],
            }
        )
    return sorted(out, key=lambda m: m["name"])


def add_mcp(name: str, target: str, args: list[str] | None = None) -> dict[str, Any]:
    """MCP 하나를 등록한다. 주소면 url 로, 아니면 실행할 프로그램으로 본다."""
    name = str(name or "").strip()
    target = str(target or "").strip()

    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name):
        raise ValueError("이름은 영문, 숫자, 붙임표만 씁니다. 예: higgsfield")
    if not target:
        raise ValueError("붙을 주소나 실행할 프로그램을 적어주세요.")

    data = read_mcp()
    if target.startswith(("http://", "https://")):
        data["mcpServers"][name] = {"type": "http", "url": target}
    else:
        조각 = target.split()
        data["mcpServers"][name] = {
            "command": 조각[0],
            "args": (args or []) or 조각[1:],
        }

    MCP_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"name": name, "file": str(MCP_FILE)}


def remove_mcp(name: str) -> None:
    data = read_mcp()
    if name not in (data.get("mcpServers") or {}):
        raise ValueError(f"'{name}' 은 등록되어 있지 않습니다.")
    del data["mcpServers"][name]
    MCP_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ------------------------------------------------------ 영상 만들 준비가 됐나

def readiness() -> dict[str, Any]:
    """영상 한 편을 끝까지 만들려면 뭐가 더 있어야 하는지 점검한다.

    지어내지 않는다. 실제로 붙어 있는지만 보고 말한다.
    """
    from .intake import ffmpeg_있나

    붙은키 = {spec["key"] for spec in 연결목록 if get_value(spec["key"])}
    이름 = {spec["key"]: spec["name"] for spec in 연결목록}
    붙은mcp = {m["name"].lower() for m in list_mcp()}

    단계들 = []
    막힌것 = []

    for step in 제작단계:
        needs = step.get("needs") or []
        도구 = step.get("tool")

        if 도구 == "ffmpeg":
            된다 = ffmpeg_있나()
            가진것 = ["ffmpeg"] if 된다 else []
            빠진것 = [] if 된다 else ["ffmpeg (ffmpeg.org 에서 받아 깔면 됩니다)"]
        elif not needs:
            된다, 가진것, 빠진것 = True, [], []
        else:
            가진것 = [이름[k] for k in needs if k in 붙은키]
            된다 = bool(가진것)
            빠진것 = [] if 된다 else [이름[k] for k in needs]

        단계들.append(
            {
                "step": step["step"],
                "required": step["required"],
                "ok": 된다,
                "have": 가진것,
                "missing": 빠진것,
                "how": step["how"],
                "detour": step["detour"],
            }
        )
        if not 된다:
            막힌것.append(step["step"])

    필수막힘 = [s for s in 단계들 if s["required"] and not s["ok"]]

    if 필수막힘:
        한줄 = "클로드부터 연결해주세요. 그게 없으면 아무것도 안 돕니다."
    elif not 막힌것:
        한줄 = "다 준비됐습니다. 주제만 주시면 끝까지 만듭니다."
    else:
        한줄 = (
            f"대본까지는 지금 바로 됩니다. "
            f"{', '.join(막힌것)} 은 아직 연결이 안 돼 있습니다."
        )

    return {
        "summary": 한줄,
        "can_write": not 필수막힘,
        "all_ready": not 막힌것,
        "steps": 단계들,
        "mcp_connected": sorted(붙은mcp),
    }
