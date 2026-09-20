"""결(Gyeol) — 영상 한 편의 결을 스킬로 만들어 두고, 그 결로 계속 찍어내는 도구.

링크 하나 넣으면 그 영상의 결을 뽑는다.
뽑은 결은 스킬로 저장된다.
다음부터는 주제만 바꿔 넣어도 같은 결로 나온다.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from gyeol import assemble, batch, connect, deep, guide, intake, picker, produce, providers, revise, router, skillgen, source, store, timeline
from gyeol import style as style_mod
from gyeol.analyze import analyze
from gyeol.config import DEFAULT_AUDIENCE, MODEL
from gyeol.llm import LLMUnavailable, api_key_present
from gyeol.source import SourceUnavailable

@asynccontextmanager
async def lifespan(_app: FastAPI):
    store.ensure_dirs()
    yield


app = FastAPI(
    title="결 Gyeol",
    description="영상 한 편의 결을 스킬로 복제해서 계속 써먹는 제작 도구",
    lifespan=lifespan,
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/api/health")
def health():
    """화면이 켜질 때 준비 상태를 확인한다."""
    return {
        "api_key": api_key_present(),
        "model": MODEL,
        "audience": DEFAULT_AUDIENCE,
        "skill_count": len(store.list_skills()),
    }


# ------------------------------------------------------------- 1단계 : 결 뽑기

@app.post("/api/analyze")
def api_analyze(payload: dict = Body(...)):
    """영상 링크나 붙여넣은 대본에서 결을 뽑는다. 아직 저장하지는 않는다."""
    url = str(payload.get("url") or "").strip()
    transcript = str(payload.get("transcript") or "").strip()
    title = str(payload.get("title") or "").strip()
    notes = str(payload.get("notes") or "").strip()
    audience = str(payload.get("audience") or DEFAULT_AUDIENCE).strip()

    if not url and not transcript:
        raise HTTPException(400, "영상 링크를 넣거나 대본을 붙여넣어주세요.")

    try:
        # 대본을 직접 넣었으면 그걸 쓴다. 자막 긁기보다 정확하다.
        if transcript:
            material = source.material_from_text(transcript, title=title, url=url)
        else:
            material = source.fetch_source(url)
    except SourceUnavailable as exc:
        raise HTTPException(422, str(exc)) from exc

    try:
        dna = analyze(material, extra_notes=notes, audience=audience)
    except LLMUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc

    slug = store.new_slug()
    return {
        "slug": slug,
        "dna": dna,
        "skill_md": skillgen.build_skill_md(dna, slug, material.url),
        "material_brief": material.brief(),
        "source": {
            "url": material.url,
            "title": material.title,
            "uploader": material.uploader,
            "duration": material.duration,
            "transcript_origin": material.transcript_origin,
            "transcript_chars": len(material.transcript),
        },
    }


@app.get("/api/upload/kinds")
def api_upload_kinds():
    """어떤 파일을 받을 수 있는지 화면에 알려준다."""
    return {
        "extensions": intake.받는것,
        "max_mb": intake.MAX_MB,
        "ffmpeg": intake.ffmpeg_있나(),
    }


@app.post("/api/upload")
async def api_upload(
    file: UploadFile = File(...),
    notes: str = Form(""),
    audience: str = Form(DEFAULT_AUDIENCE),
):
    """받아둔 파일에서 바로 결을 뽑는다.

    대본, 자막, 자막이 박힌 영상 파일을 받는다.
    """
    data = await file.read()
    if not data:
        raise HTTPException(400, "빈 파일입니다.")

    try:
        material = intake.from_upload(file.filename or "올린파일", data)
    except SourceUnavailable as exc:
        raise HTTPException(422, str(exc)) from exc

    try:
        dna = analyze(material, extra_notes=notes, audience=audience or DEFAULT_AUDIENCE)
    except LLMUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc

    slug = store.new_slug()
    return {
        "slug": slug,
        "dna": dna,
        "skill_md": skillgen.build_skill_md(dna, slug, ""),
        "material_brief": material.brief(),
        "source": {
            "url": "",
            "title": material.title,
            "uploader": "",
            "duration": 0,
            "transcript_origin": material.transcript_origin,
            "transcript_chars": len(material.transcript),
        },
    }


# ------------------------------------------------------------- 2단계 : 스킬 저장

@app.post("/api/skills")
def api_save_skill(payload: dict = Body(...)):
    """뽑은 결을 스킬로 굳힌다. 클로드 코드 쪽에도 같이 깔린다."""
    dna = payload.get("dna")
    if not isinstance(dna, dict) or not dna.get("title"):
        raise HTTPException(400, "저장할 결이 없습니다. 먼저 분석을 돌려주세요.")

    slug = str(payload.get("slug") or "").strip() or store.new_slug()
    src = payload.get("source") or {}
    source_url = str(src.get("url") or "")

    meta = store.save_skill(
        dna=dna,
        skill_md=skillgen.build_skill_md(dna, slug, source_url),
        source_url=source_url,
        source_title=str(src.get("title") or ""),
        transcript_origin=str(src.get("transcript_origin") or ""),
        material_brief=str(payload.get("material_brief") or ""),
        slug=slug,
    )
    return meta


@app.get("/api/skills")
def api_list_skills():
    return {"skills": store.list_skills()}


@app.get("/api/skills/{slug}")
def api_get_skill(slug: str):
    try:
        return store.get_skill(slug)
    except store.NotFound as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/skills/{slug}/skill.md", response_class=PlainTextResponse)
def api_download_skill(slug: str):
    """SKILL.md 파일 그대로 내려받기."""
    try:
        return PlainTextResponse(
            store.get_skill(slug)["skill_md"],
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{slug}-SKILL.md"'},
        )
    except store.NotFound as exc:
        raise HTTPException(404, str(exc)) from exc


@app.delete("/api/skills/{slug}")
def api_delete_skill(slug: str):
    try:
        store.delete_skill(slug)
    except store.NotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"deleted": slug}


# ------------------------------------------------------------- 3단계 : 대본 뽑기

@app.post("/api/produce")
def api_produce(payload: dict = Body(...)):
    """저장된 결로 새 주제의 대본을 쓴다."""
    slug = str(payload.get("slug") or "").strip()
    topic = str(payload.get("topic") or "").strip()
    if not slug:
        raise HTTPException(400, "어떤 결로 만들지 골라주세요.")
    if not topic:
        raise HTTPException(400, "이번 영상의 주제를 넣어주세요.")

    try:
        skill = store.get_skill(slug)
    except store.NotFound as exc:
        raise HTTPException(404, str(exc)) from exc

    try:
        script = produce.write_script(
            skill["dna"],
            topic,
            minutes=int(payload.get("minutes") or 5),
            extra_notes=str(payload.get("notes") or ""),
            audience=str(payload.get("audience") or DEFAULT_AUDIENCE),
            reference=store.get_reference(slug),
        )
    except LLMUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    try:
        record = store.save_script(
            slug,
            script,
            style_mod.default_style(),
            folder_name=str(payload.get("folder") or ""),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _project_view(record, skill)


@app.get("/api/scripts")
def api_list_scripts():
    return {"scripts": store.list_scripts()}


# --------------------------------------------------------- 4단계 : 고쳐쓰기

def _project_view(record: dict, skill: dict) -> dict:
    """화면이 한 번에 다 그릴 수 있게 묶어서 내준다."""
    script = record["script"]
    style = record["style"]
    return {
        "project_id": record["project_id"],
        "skill_slug": record["skill_slug"],
        "skill_name": skill["meta"].get("name", ""),
        "script": script,
        "style": style,
        "style_summary": style_mod.describe(style),
        "plain_text": store.as_plain_text(script),
        "production_order": produce.as_production_order(script, skill["dna"], style),
        "history": record.get("history", []),
    }


def _load(project_id: str) -> tuple[dict, dict]:
    try:
        record = store.get_script(project_id)
        return record, store.get_skill(record["skill_slug"])
    except store.NotFound as exc:
        raise HTTPException(404, str(exc)) from exc


# --------------------------------------------------------------- 연결

@app.get("/api/connections")
def api_connections():
    """어디에 붙어 있는지 보여준다. 키는 끝 네 자리만 나간다."""
    return {
        "keys": connect.status(),
        "mcp": connect.list_mcp(),
        "env_file": str(connect.ENV_FILE),
        "mcp_file": str(connect.MCP_FILE),
    }


@app.get("/api/readiness")
def api_readiness():
    """영상 한 편을 끝까지 만들 준비가 됐는지 점검한다."""
    return connect.readiness()


@app.put("/api/connections")
def api_save_connections(payload: dict = Body(...)):
    """키를 넣거나 바꾼다. 앱을 다시 안 켜도 바로 먹는다."""
    changes = payload.get("changes")
    if not isinstance(changes, dict):
        raise HTTPException(400, "바꿀 내용이 없습니다.")

    바뀐것 = connect.set_values(changes)
    return {"changed": 바뀐것, "keys": connect.status()}


@app.post("/api/connections/test")
def api_test_claude():
    """클로드 키가 진짜 되는지 찔러본다."""
    ok, message = connect.test_claude()
    return {"ok": ok, "message": message}


@app.post("/api/mcp")
def api_add_mcp(payload: dict = Body(...)):
    """MCP 하나를 등록한다. 클로드 코드가 읽는 .mcp.json 에 적힌다."""
    try:
        added = connect.add_mcp(
            str(payload.get("name") or ""), str(payload.get("target") or "")
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {**added, "mcp": connect.list_mcp()}


@app.delete("/api/mcp/{name}")
def api_remove_mcp(name: str):
    try:
        connect.remove_mcp(name)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"removed": name, "mcp": connect.list_mcp()}


@app.get("/api/settings")
def api_get_settings():
    """지금 어디에 쌓고 있는지 알려준다."""
    paths = store.current_paths()
    paths["skill_count"] = len(store.list_skills())
    paths["script_count"] = len(store.list_scripts(limit=9999))
    paths["can_browse"] = picker.available()
    return paths


@app.post("/api/settings/browse")
def api_browse_folder():
    """운영체제의 폴더 창을 띄운다. 앱이 형님 컴퓨터에서 도니까 가능하다."""
    try:
        picked = picker.ask_folder(store.current_paths()["data_dir"])
    except picker.PickerUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"picked": picked}


@app.put("/api/settings")
def api_set_settings(payload: dict = Body(...)):
    """저장 폴더를 옮긴다. 옮긴 뒤에 만든 것부터 새 자리에 쌓인다."""
    try:
        paths = store.set_data_dir(str(payload.get("data_dir") or ""))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    paths["skill_count"] = len(store.list_skills())
    paths["script_count"] = len(store.list_scripts(limit=9999))
    return paths


@app.get("/api/style/options")
def api_style_options():
    """화면에 띄울 글꼴 목록과 기본값."""
    return {
        "fonts": style_mod.FONTS,
        "positions": style_mod.POSITIONS,
        "backgrounds": style_mod.BACKGROUNDS,
        "default": style_mod.default_style(),
    }


@app.get("/api/projects/{project_id}")
def api_get_project(project_id: str):
    record, skill = _load(project_id)
    return _project_view(record, skill)


@app.put("/api/projects/{project_id}/style")
def api_set_style(project_id: str, payload: dict = Body(...)):
    """손으로 돌린 값을 그대로 저장한다. 클로드를 안 부르니 즉시 끝난다."""
    record, skill = _load(project_id)
    updated = store.update_script(
        project_id, record["script"], payload.get("style"), note="꾸밈새를 손으로 조정"
    )
    return _project_view(updated, skill)


@app.post("/api/projects/{project_id}/revise")
def api_revise(project_id: str, payload: dict = Body(...)):
    """말로 고친다. 자막 꾸밈새든 원고든 한 통로로 받는다."""
    instruction = str(payload.get("instruction") or "").strip()
    if not instruction:
        raise HTTPException(400, "무엇을 고칠지 적어주세요.")

    record, skill = _load(project_id)
    try:
        result = revise.revise(record["script"], record["style"], instruction)
    except LLMUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    updated = store.update_script(
        project_id, result["script"], result["style"], note=instruction
    )
    view = _project_view(updated, skill)
    view["revision"] = {
        "understood": result["understood"],
        "done": result["done"],
        "style_changed": result["style_changed"],
        "regenerate_scenes": result["regenerate_scenes"],
        "note": result["note"],
    }
    return view


# ------------------------------------------------------- 명령창 : 말로 부리기

def _analyze_to_view(url: str, notes: str, transcript: str = "") -> dict:
    """결을 뽑아서 화면이 쓸 모양으로 내준다."""
    try:
        material = (
            source.material_from_text(transcript, url=url)
            if transcript
            else source.fetch_source(url)
        )
    except SourceUnavailable as exc:
        raise HTTPException(422, str(exc)) from exc

    try:
        dna = analyze(material, extra_notes=notes)
    except LLMUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc

    slug = store.new_slug()
    return {
        "slug": slug,
        "dna": dna,
        "skill_md": skillgen.build_skill_md(dna, slug, material.url),
        "material_brief": material.brief(),
        "source": {
            "url": material.url,
            "title": material.title,
            "uploader": material.uploader,
            "duration": material.duration,
            "transcript_origin": material.transcript_origin,
            "transcript_chars": len(material.transcript),
        },
    }


def _do_produce(
    skill: dict, topics: list[str], minutes: int, notes: str, folder: str = ""
) -> dict:
    """한 편이든 여러 편이든 같은 통로로 만든다."""

    def 폴더이름(topic: str) -> str:
        """여러 편이면 폴더 이름 뒤에 주제를 붙여서 서로 안 겹치게 한다."""
        if not folder:
            return ""
        return folder if len(topics) == 1 else f"{folder} - {topic}"

    def 한편(topic: str) -> dict:
        script = produce.write_script(
            skill["dna"], topic, minutes=minutes or 5, extra_notes=notes,
            reference=store.get_reference(skill["meta"]["slug"]),
        )
        record = store.save_script(
            skill["meta"]["slug"], script, style_mod.default_style(), 폴더이름(topic)
        )
        return _project_view(record, skill)

    if len(topics) == 1:
        try:
            return {"kind": "script", "items": [한편(topics[0])], "reply": ""}
        except LLMUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc

    results = batch.run_many(topics, 한편)
    return {
        "kind": "scripts",
        "items": [r["result"] for r in results if r["ok"]],
        "failed": [
            {"topic": r["topic"], "error": r["error"]} for r in results if not r["ok"]
        ],
        "reply": batch.summarize(results),
    }


@app.post("/api/say")
def api_say(payload: dict = Body(...)):
    """한 줄 명령을 받아서 알맞은 일로 보낸다. 이 앱의 정문이다."""
    text = str(payload.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "무엇을 할지 적어주세요.")

    state = payload.get("state") or {}
    pending = state.get("pending") or {}
    project_id = str(state.get("project_id") or "")
    skills = store.list_skills()

    try:
        intent = router.route(
            text,
            {
                "pending_skill": (pending.get("dna") or {}).get("title", ""),
                "skills": [s["name"] for s in skills],
                "project": project_id,
            },
        )
    except LLMUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    action = intent.get("action")
    reply = intent.get("reply") or ""

    # ------------------------------------------------------------- 결 뽑기
    if action == "analyze":
        url = intent.get("url") or ""
        transcript = str(payload.get("transcript") or "").strip()
        if not url and not transcript:
            return {"kind": "message", "reply": "영상 주소를 같이 넣어주세요."}
        view = _analyze_to_view(url, intent.get("notes") or "", transcript)
        return {
            "kind": "analysis",
            "reply": reply or f"'{view['dna']['title']}' 결을 뽑았습니다. 저장할까요?",
            "analysis": view,
        }

    # ------------------------------------------------------------- 저장하기
    if action == "save_skill":
        if not pending.get("dna"):
            return {"kind": "message", "reply": "저장할 결이 없습니다. 영상 주소를 먼저 주세요."}
        meta = store.save_skill(
            dna=pending["dna"],
            skill_md=skillgen.build_skill_md(
                pending["dna"], pending["slug"], (pending.get("source") or {}).get("url", "")
            ),
            source_url=(pending.get("source") or {}).get("url", ""),
            source_title=(pending.get("source") or {}).get("title", ""),
            transcript_origin=(pending.get("source") or {}).get("transcript_origin", ""),
            material_brief=pending.get("material_brief", ""),
            slug=pending["slug"],
        )
        return {
            "kind": "skill_saved",
            "reply": f"'{meta['name']}' 저장했습니다. 이제 주제만 주시면 이 결로 씁니다.",
            "skill": meta,
        }

    # --------------------------------------------------------------- 목록
    if action == "list_skills":
        return {
            "kind": "skills",
            "reply": reply or (f"{len(skills)}개 있습니다." if skills else "아직 없습니다."),
            "skills": skills,
        }

    # ------------------------------------------------------------ 대본 쓰기
    if action == "produce":
        topics = [t for t in (intent.get("topics") or []) if str(t).strip()]
        if not topics:
            return {"kind": "message", "reply": "어떤 주제로 만들까요?"}
        if not skills:
            return {
                "kind": "message",
                "reply": "저장된 결이 없습니다. 본받고 싶은 영상 주소를 먼저 주세요.",
            }

        picked = router.pick_skill(intent.get("skill_hint") or "", skills)
        try:
            skill = store.get_skill(picked["slug"])
        except store.NotFound as exc:
            raise HTTPException(404, str(exc)) from exc

        out = _do_produce(
            skill,
            topics,
            int(intent.get("minutes") or 0),
            intent.get("notes") or "",
            # 말로 지은 이름이 먼저, 없으면 화면에 적어둔 이름
            str(intent.get("folder") or payload.get("folder") or "").strip(),
        )
        out["reply"] = out.get("reply") or reply or f"'{skill['meta']['name']}' 결로 썼습니다."
        return out

    # --------------------------------------------------------------- 고치기
    if action == "revise":
        if not project_id:
            return {"kind": "message", "reply": "고칠 작업이 없습니다. 먼저 하나 만들어주세요."}
        record, skill = _load(project_id)
        try:
            result = revise.revise(
                record["script"], record["style"], intent.get("instruction") or text
            )
        except LLMUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

        updated = store.update_script(project_id, result["script"], result["style"], note=text)
        view = _project_view(updated, skill)
        view["revision"] = {
            "understood": result["understood"],
            "done": result["done"],
            "style_changed": result["style_changed"],
            "regenerate_scenes": result["regenerate_scenes"],
            "note": result["note"],
        }
        return {"kind": "revised", "reply": result["understood"] or reply, "project": view}

    # ------------------------------------------- 프레임 뜯기 · 목소리 · 조립
    if action == "deep":
        if not skills:
            return {"kind": "message", "reply": "먼저 결을 하나 뽑아 저장해주세요. 그 원본을 뜯습니다."}
        picked = router.pick_skill(intent.get("skill_hint") or "", skills)
        out = api_deep(picked["slug"], {"url": intent.get("url") or ""})
        return {"kind": "deep", "reply": out["reply"], "slug": picked["slug"], "summary": out["summary"]}

    if action == "voice":
        if not project_id:
            return {"kind": "message", "reply": "목소리를 입힐 작업이 없습니다. 먼저 대본을 하나 만들어주세요."}
        voice_id = str(payload.get("voice_id") or "").strip()
        if not voice_id:
            try:
                voices = providers.eleven_voices()
            except providers.ProviderUnavailable as exc:
                raise HTTPException(503, str(exc)) from exc
            return {"kind": "pick_voice", "reply": "어느 목소리로 읽을까요?", "voices": voices, "project_id": project_id}
        out = api_make_voice(project_id, {"voice_id": voice_id})
        n, f = len(out["made"]), len(out["failed"])
        return {"kind": "voice", "reply": f"{n}컷 읽었습니다." + (f" {f}컷은 막혔습니다." if f else ""),
                "view": out["view"], "failed": out["failed"]}

    if action == "assemble":
        if not project_id:
            return {"kind": "message", "reply": "조립할 작업이 없습니다. 먼저 대본을 하나 만들어주세요."}
        out = api_assemble(project_id, {})
        return {"kind": "assembled", "reply": "묶었습니다. 아래에서 내려받으세요.", "video": out["video"], "view": out["view"]}

    # ------------------------------------------------- 만들 준비가 됐는지 점검
    if action == "ready":
        점검 = connect.readiness()
        return {"kind": "readiness", "reply": 점검["summary"], "readiness": 점검}

    # ------------------------------------------------------------ 물음에 답하기
    if action == "ask":
        try:
            answered = guide.answer(
                text,
                {
                    "skills": [s["name"] for s in skills],
                    "project": project_id,
                    "claude": True,  # 여기까지 왔으면 이미 붙어 있다
                    "connected": [
                        c["name"] for c in connect.status() if c["connected"] and not c["required"]
                    ],
                },
            )
        except LLMUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

        return {
            "kind": "answer",
            "reply": answered.get("answer", ""),
            "try_this": answered.get("try_this") or [],
        }

    # ------------------------------------------------------------ 도움말 등
    if action == "help":
        return {"kind": "message", "reply": router.HELP_TEXT}

    return {"kind": "message", "reply": reply or "무슨 말씀이신지 잘 모르겠습니다. 다시 한 번 말씀해주세요."}


# ================================================= 영상 만들기 : 타임라인과 레이어

LAYER_FOLDERS = {"screen": "screen", "voice": "voice", "ambient": "ambient", "character": "character"}


def _have_keys() -> set[str]:
    return {c["key"] for c in connect.status() if c["connected"]}


def _timeline_of(project_id: str) -> tuple[dict, dict, dict, dict | None]:
    """작업 하나의 타임라인. 없으면 대본에서 펴고 레퍼런스 모양을 입힌다."""
    record, skill = _load(project_id)
    reference = store.get_reference(record["skill_slug"])
    tl = store.get_timeline(project_id)
    if tl is None:
        tl = timeline.from_script(record["script"], record["style"])
        if reference:
            tl = produce.mirror_cues(reference, tl)
        store.save_timeline(project_id, tl)
    return record, skill, timeline.normalize(tl), reference


def _asset_counts(project_id: str) -> dict[str, int]:
    folder = store.project_folder(project_id)
    out = {}
    for layer, sub in LAYER_FOLDERS.items():
        exts = providers.IMAGE_EXTS + providers.VIDEO_EXTS if layer in ("screen", "character") else providers.AUDIO_EXTS
        out[layer] = len(providers.folder_assets(folder / sub, exts))
    out["bgm"] = 1 if _bgm_file(folder) else 0
    return out


def _bgm_file(folder) -> "Path | None":
    for ext in providers.AUDIO_EXTS:
        cand = folder / f"bgm{ext}"
        if cand.exists():
            return cand
    return None


def _timeline_view(project_id: str) -> dict:
    record, skill, tl, reference = _timeline_of(project_id)
    folder = store.project_folder(project_id)
    final = folder / "final.mp4"
    return {
        "project_id": project_id,
        "topic": record["script"].get("topic", ""),
        "skill_name": skill["meta"].get("name", ""),
        "timeline": tl,
        "summary": timeline.describe(tl),
        "layers": timeline.provider_status(tl, _have_keys()),
        "assets": _asset_counts(project_id),
        "folders": {k: str(folder / v) for k, v in LAYER_FOLDERS.items()} | {"bgm": str(folder / "bgm.mp3")},
        "has_reference": reference is not None,
        "reference_overall": (reference or {}).get("overall"),
        "ffmpeg": assemble.shutil.which("ffmpeg") is not None,
        "video": f"/api/projects/{project_id}/video" if final.exists() else None,
    }


@app.get("/api/projects/{project_id}/timeline")
def api_get_timeline(project_id: str):
    return _timeline_view(project_id)


@app.put("/api/projects/{project_id}/timeline")
def api_put_timeline(project_id: str, payload: dict = Body(...)):
    """레이어 제공자를 바꾸거나 큐를 손본다."""
    _, _, tl, _ = _timeline_of(project_id)
    if isinstance(payload.get("providers"), dict):
        tl["providers"].update(payload["providers"])
    if isinstance(payload.get("cues"), dict):
        tl["cues"].update(payload["cues"])
    if payload.get("aspect_ratio"):
        tl["aspect_ratio"] = payload["aspect_ratio"]
    store.save_timeline(project_id, timeline.normalize(tl))
    return _timeline_view(project_id)


# ------------------------------------------------------- 레퍼런스 프레임 뜯기

@app.post("/api/skills/{slug}/deep")
def api_deep(slug: str, payload: dict = Body(default={})):
    """결 하나의 원본 영상을 프레임 단위로 뜯어 레퍼런스 타임라인을 만든다."""
    try:
        skill = store.get_skill(slug)
    except store.NotFound as exc:
        raise HTTPException(404, str(exc)) from exc

    url = str(payload.get("url") or skill["meta"].get("source_url") or "").strip()
    local = str(payload.get("local_path") or "").strip()
    if not url and not local:
        raise HTTPException(422, "이 결은 원본 영상 주소가 없습니다. 주소나 받아둔 영상 파일 경로를 넣어주세요.")

    try:
        material = source.fetch_source(url) if url else source.material_from_text(
            (store.get_skill(slug).get("material_brief") or "가" * 200), url=""
        )
    except SourceUnavailable as exc:
        if not local:
            raise HTTPException(422, str(exc)) from exc
        material = source.SourceMaterial(url=url)
    if local:
        material.local_path = local

    try:
        reference = deep.analyze_reference(material)
    except deep.DeepUnavailable as exc:
        raise HTTPException(422, str(exc)) from exc
    except LLMUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc

    overall = reference.get("overall") or {}
    reference = timeline.normalize(reference)
    reference["overall"] = overall
    store.save_reference(slug, reference)
    o = {"shot_count": len(reference["shots"]), "avg_shot_seconds": 0,
         "silence_count": 0, "music_only_count": 0, "character_pattern": "", **overall}
    return {
        "slug": slug,
        "reference": reference,
        "summary": timeline.describe(reference),
        "reply": (
            f"{o['shot_count']}컷을 봤습니다. 한 장면 평균 {o['avg_shot_seconds']}초, "
            f"침묵 {o['silence_count']}번, 음악만 흐르는 구간 {o['music_only_count']}번. "
            f"캐릭터: {o['character_pattern'] or '없음'}"
        ),
    }


# ------------------------------------------------------------- 목소리 입히기

@app.get("/api/voices")
def api_voices():
    try:
        return {"voices": providers.eleven_voices()}
    except providers.ProviderUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@app.post("/api/projects/{project_id}/voice")
def api_make_voice(project_id: str, payload: dict = Body(...)):
    """장면마다 나레이션을 읽어서 voice/NN.mp3 로 남긴다."""
    voice_id = str(payload.get("voice_id") or "").strip()
    if not voice_id:
        raise HTTPException(400, "어느 목소리로 읽을지 골라주세요.")

    _, _, tl, _ = _timeline_of(project_id)
    folder = store.project_folder(project_id) / "voice"
    cues = tl["cues"].get("voice") or []
    shots = tl["shots"]

    made, failed = [], []
    for shot, cue in zip(shots, cues):
        if not cue.get("text", "").strip():
            continue
        try:
            path = providers.eleven_speak(
                cue["text"], voice_id, folder / f"{shot['no']:02d}.mp3",
                speed=float(payload.get("speed") or 0.95),
            )
            made.append({"no": shot["no"], "file": path.name})
        except providers.ProviderUnavailable as exc:
            failed.append({"no": shot["no"], "error": str(exc)})
            if "키" in str(exc):
                break  # 키가 틀렸으면 더 해봐야 소용없다

    tl["providers"]["voice"] = "elevenlabs"
    store.save_timeline(project_id, tl)
    return {"made": made, "failed": failed, "view": _timeline_view(project_id)}


# ------------------------------------------------------------------- 조립

@app.post("/api/projects/{project_id}/assemble")
def api_assemble(project_id: str, payload: dict = Body(default={})):
    """여섯 레이어를 mp4 하나로 묶는다. ffmpeg 가 있어야 한다."""
    record, _, tl, _ = _timeline_of(project_id)
    folder = store.project_folder(project_id)
    prov = tl["providers"]

    screen = providers.folder_assets(folder / "screen", providers.IMAGE_EXTS + providers.VIDEO_EXTS)
    voice = providers.folder_assets(folder / "voice", providers.AUDIO_EXTS) if prov["voice"] != "none" else {}
    ambient = providers.folder_assets(folder / "ambient", providers.AUDIO_EXTS) if prov["ambient"] != "none" else {}
    character = providers.folder_assets(folder / "character", providers.IMAGE_EXTS) if prov["character"] != "none" else {}
    bgm = _bgm_file(folder) if prov["bgm"] != "none" else None

    steps: list[str] = []
    try:
        assemble.build(
            tl, record["style"], folder / "work", folder / "final.mp4",
            screen_assets=screen, voice_assets=voice, ambient_assets=ambient,
            bgm_file=bgm, character_assets=character, on_step=steps.append,
        )
    except assemble.AssembleUnavailable as exc:
        raise HTTPException(422, str(exc)) from exc

    return {"video": f"/api/projects/{project_id}/video", "steps": steps, "view": _timeline_view(project_id)}


@app.get("/api/projects/{project_id}/video")
def api_video(project_id: str):
    final = store.project_folder(project_id) / "final.mp4"
    if not final.exists():
        raise HTTPException(404, "아직 만들어진 영상이 없습니다. 먼저 조립해주세요.")
    return FileResponse(str(final), media_type="video/mp4", filename=f"{project_id}.mp4")
