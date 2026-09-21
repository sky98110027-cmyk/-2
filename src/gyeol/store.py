"""스킬과 대본을 파일로 보관한다.

데이터베이스는 안 쓴다. 폴더 하나에 파일로 두면
형님이 직접 열어보고 고칠 수 있다. 그게 더 낫다.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path
from typing import Any

from . import style as style_mod
from .config import CLAUDE_SKILLS_DIR, DATA_DIR, PROJECTS_DIR, SKILLS_DIR


def ensure_dirs() -> None:
    """지금 지정된 자리에 폴더가 있는지 확인한다."""
    for d in (DATA_DIR, SKILLS_DIR, PROJECTS_DIR):
        d.mkdir(parents=True, exist_ok=True)


class NotFound(Exception):
    """찾는 스킬이 없을 때."""


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def new_slug(prefix: str = "gyeol") -> str:
    """폴더 이름이자 스킬 이름. 소문자와 숫자와 붙임표만 쓴다."""
    return f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ------------------------------------------------------------------- 스킬

def save_skill(
    *,
    dna: dict[str, Any],
    skill_md: str,
    source_url: str = "",
    source_title: str = "",
    transcript_origin: str = "",
    material_brief: str = "",
    slug: str | None = None,
) -> dict[str, Any]:
    """분석 결과를 스킬 하나로 굳힌다."""
    ensure_dirs()
    slug = slug or new_slug()
    folder = SKILLS_DIR / slug
    folder.mkdir(parents=True, exist_ok=True)

    meta = {
        "slug": slug,
        "name": dna.get("title") or "이름 없는 결",
        "one_line": dna.get("one_line", ""),
        "source_url": source_url,
        "source_title": source_title,
        "transcript_origin": transcript_origin,
        "created_at": _now(),
    }
    _write_json(folder / "meta.json", meta)
    _write_json(folder / "dna.json", dna)
    (folder / "SKILL.md").write_text(skill_md, encoding="utf-8")
    if material_brief:
        (folder / "source.txt").write_text(material_brief, encoding="utf-8")

    install_to_claude(slug, skill_md)
    return meta


def install_to_claude(slug: str, skill_md: str) -> Path:
    """클로드 코드가 바로 읽을 수 있는 자리에도 같이 깔아둔다."""
    target = CLAUDE_SKILLS_DIR / slug
    target.mkdir(parents=True, exist_ok=True)
    path = target / "SKILL.md"
    path.write_text(skill_md, encoding="utf-8")
    return path


def list_skills() -> list[dict[str, Any]]:
    """최근에 만든 것이 위로 오게."""
    ensure_dirs()
    out = []
    for folder in SKILLS_DIR.iterdir():
        meta_path = folder / "meta.json"
        if folder.is_dir() and meta_path.exists():
            try:
                out.append(_read_json(meta_path))
            except json.JSONDecodeError:
                continue
    # 같은 초에 저장된 것끼리도 순서가 흔들리지 않게 이름으로 한 번 더 가른다
    out.sort(key=lambda m: (m.get("created_at", ""), m.get("slug", "")), reverse=True)
    return out


def get_skill(slug: str) -> dict[str, Any]:
    """스킬 하나를 통째로 꺼낸다."""
    folder = SKILLS_DIR / _safe(slug)
    if not (folder / "dna.json").exists():
        raise NotFound(f"'{slug}' 스킬을 찾을 수 없습니다.")
    return {
        "meta": _read_json(folder / "meta.json"),
        "dna": _read_json(folder / "dna.json"),
        "skill_md": (folder / "SKILL.md").read_text(encoding="utf-8"),
    }


def delete_skill(slug: str) -> None:
    slug = _safe(slug)
    folder = SKILLS_DIR / slug
    if not folder.exists():
        raise NotFound(f"'{slug}' 스킬을 찾을 수 없습니다.")
    shutil.rmtree(folder)
    installed = CLAUDE_SKILLS_DIR / slug
    if installed.exists():
        shutil.rmtree(installed)


def _safe(slug: str) -> str:
    """폴더 밖으로 못 나가게 막는다."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", slug or ""):
        raise NotFound(f"'{slug}' 은 올바른 스킬 이름이 아닙니다.")
    return slug


# ------------------------------------------------------------------- 대본

def save_script(
    slug: str,
    script: dict[str, Any],
    style: dict[str, Any] | None = None,
    folder_name: str = "",
) -> dict[str, Any]:
    """만든 대본을 폴더 하나에 담아 쌓아둔다.

    folder_name 을 주면 그 이름으로 폴더를 만든다.
    안 주면 결 이름과 시각으로 짓는다.
    """
    ensure_dirs()
    slug = _safe(slug)
    project_id = _free_project_id(slug, folder_name)
    record = {
        "project_id": project_id,
        "skill_slug": slug,
        "topic": script.get("topic", ""),
        "created_at": _now(),
        "updated_at": _now(),
        "script": script,
        "style": style_mod.normalize(style),
        "history": [],
    }
    _write_record(record)
    return record


# 파일 이름에 쓰면 안 되는 글자와, 윈도우가 못 쓰게 막아둔 이름
_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


def clean_folder_name(name: str) -> str:
    """형님이 지은 폴더 이름을 파일 시스템이 받아들일 꼴로 다듬는다.

    한글은 그대로 둔다. 폴더를 열었을 때 알아볼 수 있어야 하니까.
    막는 것은 폴더 밖으로 나가게 하거나 운영체제가 싫어하는 글자뿐이다.
    """
    name = _BAD_CHARS.sub(" ", str(name or ""))
    name = re.sub(r"\s+", " ", name).strip()
    name = name.strip(". ")  # 윈도우는 점이나 공백으로 끝나는 이름을 싫어한다

    if not name or name in (".", ".."):
        raise ValueError("폴더 이름을 적어주세요.")
    if name.split(".")[0].lower() in _RESERVED:
        raise ValueError(f"'{name}' 은 컴퓨터가 쓰는 이름이라 못 씁니다. 다른 이름으로 지어주세요.")

    return name[:60].strip(". ")


def _free_project_id(slug: str, folder_name: str = "") -> str:
    """아직 안 쓰인 작업 이름을 고른다.

    형님이 이름을 지으셨으면 그 이름을 쓴다. 같은 이름이 있으면 뒤에 숫자를 붙인다.
    안 지으셨으면 결 이름과 시각으로 짓는다.

    여러 편을 같이 돌리면 저장이 같은 초에 몰린다.
    시각만으로 이름을 지으면 서로 덮어쓴다. 그래서 뒤에 무작위 네 자를 붙인다.
    """
    if folder_name:
        base = clean_folder_name(folder_name)
        for n in range(1, 200):
            candidate = base if n == 1 else f"{base} ({n})"
            try:
                (PROJECTS_DIR / candidate).mkdir(parents=True, exist_ok=False)
                return candidate
            except FileExistsError:
                continue
        raise ValueError(f"'{base}' 로 시작하는 폴더가 너무 많습니다. 다른 이름으로 지어주세요.")

    stamp = datetime.now().strftime("%H%M%S")
    for _ in range(50):
        candidate = f"{slug}-{stamp}-{uuid4().hex[:4]}"
        try:
            (PROJECTS_DIR / candidate).mkdir(parents=True, exist_ok=False)
            return candidate
        except FileExistsError:
            continue
    raise RuntimeError("작업 이름을 만들지 못했습니다. 잠시 뒤에 다시 해주세요.")


def _project_folder(project_id: str) -> Path:
    """작업 폴더 자리. 폴더 밖으로 나가는 이름은 막는다."""
    name = str(project_id or "")
    if not name or name != clean_folder_name_or_blank(name):
        raise NotFound(f"'{project_id}' 은 올바른 작업 이름이 아닙니다.")
    return PROJECTS_DIR / name


def clean_folder_name_or_blank(name: str) -> str:
    try:
        return clean_folder_name(name)
    except ValueError:
        return ""


def _write_record(record: dict[str, Any]) -> None:
    folder = _project_folder(record["project_id"])
    folder.mkdir(parents=True, exist_ok=True)
    _write_json(folder / "script.json", record)
    (folder / "script.txt").write_text(as_plain_text(record["script"]), encoding="utf-8")
    (folder / "caption.ass.txt").write_text(
        style_mod.to_ass_style(record["style"], "caption"), encoding="utf-8"
    )


def get_script(project_id: str) -> dict[str, Any]:
    """저장된 작업 하나를 꺼낸다."""
    path = _project_folder(project_id) / "script.json"
    if not path.exists():
        raise NotFound(f"'{project_id}' 작업을 찾을 수 없습니다.")
    record = _read_json(path)
    record.setdefault("history", [])
    record["style"] = style_mod.normalize(record.get("style"))
    return record


def update_script(
    project_id: str,
    script: dict[str, Any],
    style: dict[str, Any],
    note: str = "",
) -> dict[str, Any]:
    """고친 결과를 덮어쓴다. 무엇을 고쳤는지도 같이 남긴다."""
    record = get_script(project_id)
    record["script"] = script
    record["style"] = style_mod.normalize(style)
    record["topic"] = script.get("topic", record.get("topic", ""))
    record["updated_at"] = _now()
    if note:
        record["history"].append({"at": _now(), "note": note})
    _write_record(record)
    return record


def list_scripts(limit: int = 30) -> list[dict[str, Any]]:
    ensure_dirs()
    out = []
    for folder in PROJECTS_DIR.iterdir():
        path = folder / "script.json"
        if folder.is_dir() and path.exists():
            try:
                rec = _read_json(path)
            except json.JSONDecodeError:
                continue
            out.append(
                {
                    "project_id": rec.get("project_id", folder.name),
                    "skill_slug": rec.get("skill_slug", ""),
                    "topic": rec.get("topic", ""),
                    "created_at": rec.get("created_at", ""),
                }
            )
    out.sort(key=lambda m: (m.get("created_at", ""), m.get("project_id", "")), reverse=True)
    return out[:limit]


def as_plain_text(script: dict[str, Any]) -> str:
    """성우에게 그대로 넘길 수 있는 원고 형태로 편다."""
    lines: list[str] = []
    topic = script.get("topic", "")
    if topic:
        lines += [f"주제 : {topic}", ""]

    titles = script.get("title_candidates") or []
    if titles:
        lines.append("[제목 후보]")
        lines += [f"{i}. {t}" for i, t in enumerate(titles, 1)]
        lines.append("")

    thumbs = script.get("thumbnail_copy") or []
    if thumbs:
        lines.append("[썸네일 문구]")
        lines += [f"- {t}" for t in thumbs]
        lines.append("")

    total = script.get("total_seconds") or 0
    if total:
        lines += [f"[전체 길이] 약 {total // 60}분 {total % 60}초", ""]

    lines.append("[나레이션 원고]")
    lines.append("")
    for scene in script.get("scenes") or []:
        head = f"{scene.get('no', '?')}. {scene.get('beat', '')} ({scene.get('seconds', 0)}초)"
        lines.append(head.strip())
        lines.append(scene.get("narration", "").strip())
        caption = scene.get("caption", "").strip()
        if caption:
            lines.append(f"  자막 : {caption}")
        lines.append("")

    closing = (script.get("closing") or "").strip()
    if closing:
        lines += ["[마무리]", closing, ""]

    checks = script.get("self_check") or []
    if checks:
        lines.append("[결 점검]")
        lines += [f"- {c}" for c in checks]
        lines.append("")

    desc = (script.get("description") or "").strip()
    if desc:
        lines += ["[설명란]", desc, ""]

    tags = script.get("tags") or []
    if tags:
        lines += ["[태그]", ", ".join(tags), ""]

    return "\n".join(lines).rstrip() + "\n"


# ------------------------------------------------------------- 저장 위치 바꾸기

def current_paths() -> dict[str, str]:
    """지금 어디에 쌓고 있는지."""
    return {
        "data_dir": str(DATA_DIR),
        "skills_dir": str(SKILLS_DIR),
        "projects_dir": str(PROJECTS_DIR),
        "claude_skills_dir": str(CLAUDE_SKILLS_DIR),
    }


def set_data_dir(path: str) -> dict[str, str]:
    """저장 폴더를 옮긴다. 옮긴 뒤에 만든 것부터 새 자리에 쌓인다.

    이미 있던 파일은 옮기지 않는다.
    형님이 직접 보고 옮기시는 게 안전하다.
    """
    global DATA_DIR, SKILLS_DIR, PROJECTS_DIR

    text = str(path or "").strip()
    if not text:
        raise ValueError("저장할 폴더를 적어주세요.")

    folder = Path(text).expanduser()
    if not folder.is_absolute():
        folder = (Path.cwd() / folder).resolve()

    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ValueError(f"'{folder}' 에 폴더를 만들 수 없습니다. {exc.strerror}") from exc

    probe = folder / ".gyeol-write-test"
    try:
        probe.write_text("", encoding="utf-8")
        probe.unlink()
    except OSError:
        raise ValueError(f"'{folder}' 에는 쓸 권한이 없습니다. 다른 폴더를 골라주세요.") from None

    DATA_DIR = folder
    SKILLS_DIR = folder / "skills"
    PROJECTS_DIR = folder / "projects"
    ensure_dirs()
    return current_paths()


# ---------------------------------------------------- 레퍼런스와 타임라인 보관

def save_reference(slug: str, reference: dict[str, Any]) -> Path:
    """뜯어낸 레퍼런스 타임라인을 결 폴더에 같이 둔다."""
    folder = SKILLS_DIR / _safe(slug)
    if not folder.exists():
        raise NotFound(f"'{slug}' 스킬을 찾을 수 없습니다.")
    path = folder / "reference.json"
    _write_json(path, reference)
    return path


def get_reference(slug: str) -> dict[str, Any] | None:
    path = SKILLS_DIR / _safe(slug) / "reference.json"
    return _read_json(path) if path.exists() else None


def save_timeline(project_id: str, tl: dict[str, Any]) -> Path:
    """작업 폴더에 타임라인을 둔다. 조립할 때 이걸 읽는다."""
    folder = _project_folder(project_id)
    if not (folder / "script.json").exists():
        raise NotFound(f"'{project_id}' 작업을 찾을 수 없습니다.")
    path = folder / "timeline.json"
    _write_json(path, tl)
    return path


def get_timeline(project_id: str) -> dict[str, Any] | None:
    path = _project_folder(project_id) / "timeline.json"
    return _read_json(path) if path.exists() else None


def project_folder(project_id: str) -> Path:
    """조립 결과물과 재료 폴더가 여기 아래 생긴다."""
    return _project_folder(project_id)
