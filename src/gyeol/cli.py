"""터미널에서 바로 쓰는 명령줄 도구.

브라우저를 안 켜고 싶을 때 쓴다.

  python -m gyeol 결뽑기 <영상주소> --저장
  python -m gyeol 목록
  python -m gyeol 대본 <결이름> "주제" --분 5
  python -m gyeol 서버
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import produce, skillgen, source, store
from .analyze import analyze
from .config import DEFAULT_AUDIENCE
from .llm import LLMUnavailable
from .source import SourceUnavailable


def _die(message: str) -> None:
    print(f"\n[막혔습니다]\n{message}\n", file=sys.stderr)
    raise SystemExit(1)


def cmd_analyze(args: argparse.Namespace) -> None:
    try:
        if args.대본:
            material = source.material_from_text(
                Path(args.대본).read_text(encoding="utf-8"), url=args.주소 or ""
            )
        else:
            print(f"자막을 받는 중입니다 … {args.주소}")
            material = source.fetch_source(args.주소)
    except (SourceUnavailable, OSError) as exc:
        _die(str(exc))

    print(f"자막 {len(material.transcript)}자 확보 ({material.transcript_origin})")
    print("결을 뽑는 중입니다. 1분쯤 걸립니다 …")

    try:
        dna = analyze(material, extra_notes=args.메모 or "", audience=args.타깃)
    except LLMUnavailable as exc:
        _die(str(exc))

    print(f"\n■ {dna.get('title')}")
    print(f"  {dna.get('one_line')}\n")
    voice = dna.get("voice") or {}
    print(f"  말투   {voice.get('speech_level')} / {voice.get('tone')}")
    print(f"  문장   {voice.get('sentence_rule')}")
    print(f"  도입   {(dna.get('structure') or {}).get('hook')}\n")

    if args.저장:
        slug = store.new_slug()
        meta = store.save_skill(
            dna=dna,
            skill_md=skillgen.build_skill_md(dna, slug, material.url),
            source_url=material.url,
            source_title=material.title,
            transcript_origin=material.transcript_origin,
            material_brief=material.brief(),
            slug=slug,
        )
        print(f"스킬로 저장했습니다 → {meta['slug']}")
        print(f"클로드 코드에서도 바로 쓸 수 있게 .claude/skills/{meta['slug']}/ 에 깔았습니다.")
    else:
        print("저장하려면 --저장 을 붙여서 다시 실행해주세요.")


def cmd_list(args: argparse.Namespace) -> None:
    skills = store.list_skills()
    if not skills:
        print("저장된 결이 아직 없습니다. 결뽑기 부터 해주세요.")
        return
    for s in skills:
        print(f"\n■ {s['name']}  [{s['slug']}]")
        print(f"  {s.get('one_line', '')}")
        print(f"  원본 {s.get('source_title') or s.get('source_url') or '직접 넣은 대본'}")
    print()


def cmd_write(args: argparse.Namespace) -> None:
    try:
        skill = store.get_skill(args.결이름)
    except store.NotFound as exc:
        _die(str(exc))

    print(f"'{skill['meta']['name']}' 결로 씁니다. 2분쯤 걸립니다 …")
    try:
        script = produce.write_script(
            skill["dna"],
            args.주제,
            minutes=args.분,
            extra_notes=args.메모 or "",
            audience=args.타깃,
        )
    except (LLMUnavailable, ValueError) as exc:
        _die(str(exc))

    record = store.save_script(args.결이름, script)
    text = store.as_plain_text(script)
    print("\n" + text)

    folder = Path(store.PROJECTS_DIR) / record["project_id"]
    order = produce.as_production_order(script, skill["dna"])
    (folder / "production_order.json").write_text(
        json.dumps(order, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"저장 위치 → {folder}")
    print("  script.txt              나레이션 원고")
    print("  script.json             전체 데이터")
    print("  production_order.json   영상 생성 도구에 넣을 지시서")


def cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    print(f"브라우저에서 http://127.0.0.1:{args.포트} 를 열어주세요.\n")
    uvicorn.run("app:app", host="127.0.0.1", port=args.포트, reload=args.새로고침)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gyeol",
        description="영상 한 편의 결을 스킬로 만들어 두고, 그 결로 계속 찍어냅니다.",
    )
    sub = p.add_subparsers(dest="명령", required=True)

    a = sub.add_parser("결뽑기", help="영상에서 결을 뽑는다")
    a.add_argument("주소", nargs="?", default="", help="유튜브 영상 주소")
    a.add_argument("--대본", help="자막 대신 쓸 대본 파일 경로")
    a.add_argument("--메모", help="화면과 편집에 관한 메모")
    a.add_argument("--타깃", default=DEFAULT_AUDIENCE, help="시청 타깃")
    a.add_argument("--저장", action="store_true", help="뽑은 결을 스킬로 저장한다")
    a.set_defaults(func=cmd_analyze)

    l = sub.add_parser("목록", help="저장된 결을 본다")
    l.set_defaults(func=cmd_list)

    w = sub.add_parser("대본", help="저장된 결로 새 대본을 쓴다")
    w.add_argument("결이름", help="목록에 나오는 [대괄호] 안의 이름")
    w.add_argument("주제", help="이번 영상 주제")
    w.add_argument("--분", type=int, default=5, help="목표 길이(분)")
    w.add_argument("--메모", help="이번 영상에만 적용할 요청")
    w.add_argument("--타깃", default=DEFAULT_AUDIENCE, help="시청 타깃")
    w.set_defaults(func=cmd_write)

    s = sub.add_parser("서버", help="브라우저용 화면을 띄운다")
    s.add_argument("--포트", type=int, default=8000)
    s.add_argument("--새로고침", action="store_true", help="코드 고칠 때 자동 반영")
    s.set_defaults(func=cmd_serve)

    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.명령 == "결뽑기" and not args.주소 and not args.대본:
        _die("영상 주소를 넣거나 --대본 으로 대본 파일을 지정해주세요.")
    args.func(args)


if __name__ == "__main__":
    main()
