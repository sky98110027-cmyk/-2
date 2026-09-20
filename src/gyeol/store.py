"""스킬과 대본을 파일로 보관한다.

데이터베이스는 안 쓴다. 폴더 하나에 파일로 두면
형님이 직접 열어보고 고칠 수 있다. 그게 더 낫다.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import CLAUDE_SKILLS_DIR, PROJECTS_DIR, SKILLS_DIR, ensure_dirs


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

def save_script(slug: str, script: dict[str, Any]) -> dict[str, Any]:
    """만든 대본을 날짜별로 쌓아둔다."""
    ensure_dirs()
    slug = _safe(slug)
    project_id = f"{slug}-{datetime.now().strftime('%H%M%S')}"
    folder = PROJECTS_DIR / project_id
    folder.mkdir(parents=True, exist_ok=True)

    record = {
        "project_id": project_id,
        "skill_slug": slug,
        "topic": script.get("topic", ""),
        "created_at": _now(),
        "script": script,
    }
    _write_json(folder / "script.json", record)
    (folder / "script.txt").write_text(as_plain_text(script), encoding="utf-8")
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
