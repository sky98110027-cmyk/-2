"""화면이 부르는 통로 전체. 클로드는 가짜로 세워두고 흐름만 본다."""

import pytest
from fastapi.testclient import TestClient

import app as app_module
from gyeol import analyze as analyze_mod
from gyeol import produce as produce_mod
from gyeol import source
from gyeol.llm import LLMUnavailable


@pytest.fixture
def client(temp_data):
    with TestClient(app_module.app) as c:
        yield c


@pytest.fixture
def 가짜클로드(monkeypatch, dna, script):
    """analyze와 produce가 부르는 자리만 바꿔치기한다."""
    monkeypatch.setattr(analyze_mod, "structured", lambda **kw: dna)
    monkeypatch.setattr(produce_mod, "structured", lambda **kw: dict(script))


def _분석(client, **kw):
    body = {"transcript": "가나다라마바사 " * 40}
    body.update(kw)
    return client.post("/api/analyze", json=body)


# --------------------------------------------------------------- 준비 상태

def test_상태를_물어보면_알려준다(client):
    body = client.get("/api/health").json()
    assert set(body) == {"api_key", "model", "audience", "skill_count"}
    assert body["skill_count"] == 0


def test_첫_화면은_앱으로_보낸다(client):
    res = client.get("/", follow_redirects=False)
    assert res.status_code in (302, 307)
    assert res.headers["location"] == "/static/index.html"


# ------------------------------------------------------------------- 분석

def test_링크도_대본도_없으면_막는다(client):
    assert _분석(client, transcript="").status_code == 400


def test_대본을_넣으면_결이_나온다(client, 가짜클로드):
    body = _분석(client).json()
    assert body["dna"]["title"] == "담담한 증언체"
    assert body["slug"].startswith("gyeol-")
    assert body["skill_md"].startswith("---\nname: gyeol-")
    assert body["source"]["transcript_origin"] == "직접 붙여넣은 대본"


def test_자막을_못_가져오면_이유를_알려준다(client, monkeypatch):
    def 막힘(url, **kw):
        raise source.SourceUnavailable("자막이 없습니다. 대본을 붙여넣어주세요.")

    monkeypatch.setattr(source, "fetch_source", 막힘)
    res = client.post("/api/analyze", json={"url": "https://youtu.be/x"})
    assert res.status_code == 422
    assert "대본을 붙여넣어" in res.json()["detail"]


def test_API_키가_없으면_그렇게_말해준다(client, monkeypatch):
    def 키없음(**kw):
        raise LLMUnavailable("클로드 API 키가 없습니다.")

    monkeypatch.setattr(analyze_mod, "structured", 키없음)
    res = _분석(client)
    assert res.status_code == 503
    assert "API 키가 없습니다" in res.json()["detail"]


# ------------------------------------------------------------- 저장과 목록

def test_분석한_결을_스킬로_저장한다(client, 가짜클로드, temp_data):
    분석 = _분석(client).json()
    meta = client.post(
        "/api/skills",
        json={
            "dna": 분석["dna"],
            "slug": 분석["slug"],
            "source": 분석["source"],
            "material_brief": 분석["material_brief"],
        },
    ).json()

    assert meta["name"] == "담담한 증언체"
    assert (temp_data / "claude-skills" / meta["slug"] / "SKILL.md").exists()
    assert client.get("/api/health").json()["skill_count"] == 1
    assert client.get("/api/skills").json()["skills"][0]["slug"] == meta["slug"]


def test_결이_없으면_저장을_막는다(client):
    assert client.post("/api/skills", json={"dna": {}}).status_code == 400


def test_없는_스킬을_찾으면_404(client):
    assert client.get("/api/skills/gyeol-99999999-000000").status_code == 404


def test_스킬_파일을_내려받는다(client, 가짜클로드):
    분석 = _분석(client).json()
    meta = client.post("/api/skills", json={"dna": 분석["dna"], "slug": 분석["slug"]}).json()

    res = client.get(f"/api/skills/{meta['slug']}/skill.md")
    assert res.status_code == 200
    assert "attachment" in res.headers["content-disposition"]
    assert res.text.startswith("---\nname: ")


def test_스킬을_지운다(client, 가짜클로드):
    분석 = _분석(client).json()
    meta = client.post("/api/skills", json={"dna": 분석["dna"], "slug": 분석["slug"]}).json()

    assert client.delete(f"/api/skills/{meta['slug']}").status_code == 200
    assert client.get("/api/skills").json()["skills"] == []


# ------------------------------------------------------------------- 집필

def _저장된결(client):
    분석 = _분석(client).json()
    return client.post(
        "/api/skills", json={"dna": 분석["dna"], "slug": 분석["slug"]}
    ).json()["slug"]


def test_결과_주제를_주면_대본이_나온다(client, 가짜클로드):
    slug = _저장된결(client)
    body = client.post(
        "/api/produce", json={"slug": slug, "topic": "홍범도", "minutes": 5}
    ).json()

    assert body["skill_name"] == "담담한 증언체"
    assert body["script"]["topic"] == "홍범도"
    assert "그해 겨울은" in body["plain_text"]

    지시서 = body["production_order"]
    assert 지시서["shots"][0]["no"] == 1
    # 장면 프롬프트에 결의 화면 분위기가 반드시 박혀야 톤이 안 튄다
    assert "faded sepia" in 지시서["shots"][0]["image_prompt"]


def test_주제가_없으면_막는다(client, 가짜클로드):
    slug = _저장된결(client)
    assert client.post("/api/produce", json={"slug": slug, "topic": " "}).status_code == 400


def test_결을_안_고르면_막는다(client):
    assert client.post("/api/produce", json={"topic": "홍범도"}).status_code == 400


def test_없는_결로_쓰라고_하면_404(client):
    res = client.post("/api/produce", json={"slug": "gyeol-99999999-000000", "topic": "가"})
    assert res.status_code == 404


def test_쓴_대본은_목록에_쌓인다(client, 가짜클로드):
    slug = _저장된결(client)
    client.post("/api/produce", json={"slug": slug, "topic": "홍범도"})
    목록 = client.get("/api/scripts").json()["scripts"]
    assert len(목록) == 1
    assert 목록[0]["topic"] == "홍범도"
