"""결(Gyeol) — 영상 한 편의 결을 스킬로 만들어 두고, 그 결로 계속 찍어내는 도구.

링크 하나 넣으면 그 영상의 결을 뽑는다.
뽑은 결은 스킬로 저장된다.
다음부터는 주제만 바꿔 넣어도 같은 결로 나온다.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from gyeol import produce, skillgen, source, store
from gyeol.analyze import analyze
from gyeol.config import DEFAULT_AUDIENCE, MODEL, ensure_dirs
from gyeol.llm import LLMUnavailable, api_key_present
from gyeol.source import SourceUnavailable

@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_dirs()
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
        )
    except LLMUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    record = store.save_script(slug, script)
    return {
        "project_id": record["project_id"],
        "skill_name": skill["meta"].get("name", ""),
        "script": script,
        "plain_text": store.as_plain_text(script),
        "production_order": produce.as_production_order(script, skill["dna"]),
    }


@app.get("/api/scripts")
def api_list_scripts():
    return {"scripts": store.list_scripts()}
