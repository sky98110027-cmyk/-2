"""폴더 이름 직접 짓기, 그리고 파일 올려서 결 뽑기."""

import io

import pytest
from fastapi.testclient import TestClient

import app as app_module
from gyeol import analyze as analyze_mod
from gyeol import produce as produce_mod
from gyeol import router as router_mod
from gyeol import store


@pytest.fixture
def client(temp_data):
    with TestClient(app_module.app) as c:
        yield c


@pytest.fixture
def 가짜모델(monkeypatch, dna, script):
    monkeypatch.setattr(analyze_mod, "structured", lambda **kw: dna)
    monkeypatch.setattr(produce_mod, "structured", lambda **kw: dict(script))


# ----------------------------------------------------------- 이름 다듬기

@pytest.mark.parametrize(
    "넣은값, 나올값",
    [
        ("오늘의 홍범도편", "오늘의 홍범도편"),
        ("  독립군 3부작  ", "독립군 3부작"),
        ("봉오동/전투", "봉오동 전투"),
        ("제목: 그날 <특집>", "제목 그날 특집"),
        ("끝에점.", "끝에점"),
        ("여러   공백", "여러 공백"),
        ("..\\..\\탈출", "탈출"),
    ],
)
def test_폴더_이름을_쓸_수_있게_다듬는다(넣은값, 나올값):
    assert store.clean_folder_name(넣은값) == 나올값


@pytest.mark.parametrize("나쁜이름", ["", "   ", "..", ".", "CON", "nul", "com1", "LPT9"])
def test_못_쓰는_이름은_막는다(나쁜이름):
    with pytest.raises(ValueError):
        store.clean_folder_name(나쁜이름)


def test_이름이_길면_잘라낸다():
    assert len(store.clean_folder_name("가" * 200)) == 60


# ------------------------------------------------------------ 실제 저장

def test_지어준_이름_그대로_폴더가_생긴다(dna, script, temp_data):
    store.save_skill(dna=dna, skill_md="---\nname: x\n---\n", slug="gyeol-20260920-130000")
    기록 = store.save_script(
        "gyeol-20260920-130000", script, folder_name="오늘의 홍범도편"
    )
    assert 기록["project_id"] == "오늘의 홍범도편"
    assert (temp_data / "projects" / "오늘의 홍범도편" / "script.txt").exists()


def test_같은_이름이_있으면_뒤에_숫자를_붙인다(dna, script):
    store.save_skill(dna=dna, skill_md="---\nname: x\n---\n", slug="gyeol-20260920-130000")
    이름들 = [
        store.save_script("gyeol-20260920-130000", script, folder_name="독립군")["project_id"]
        for _ in range(3)
    ]
    assert 이름들 == ["독립군", "독립군 (2)", "독립군 (3)"]


def test_이름을_안_지으면_알아서_짓는다(dna, script):
    store.save_skill(dna=dna, skill_md="---\nname: x\n---\n", slug="gyeol-20260920-130000")
    이름 = store.save_script("gyeol-20260920-130000", script)["project_id"]
    assert 이름.startswith("gyeol-20260920-130000-")


def test_한글_폴더도_다시_꺼낼_수_있다(dna, script):
    store.save_skill(dna=dna, skill_md="---\nname: x\n---\n", slug="gyeol-20260920-130000")
    기록 = store.save_script("gyeol-20260920-130000", script, folder_name="독립군 3부작")
    assert store.get_script("독립군 3부작")["topic"] == 기록["topic"]


@pytest.mark.parametrize("탈출", ["../../etc", "..", "폴더/하위", "con"])
def test_폴더_밖으로_나가는_이름은_못_꺼낸다(탈출):
    with pytest.raises(store.NotFound):
        store.get_script(탈출)


# -------------------------------------------------------------- 통로로

def _결하나(client, monkeypatch):
    monkeypatch.setattr(
        router_mod, "structured",
        lambda **kw: {"action": "analyze", "url": "", "reply": "",
                      "notes": "", "skill_hint": "", "topics": [],
                      "minutes": 0, "folder": "", "instruction": ""},
    )
    분석 = client.post(
        "/api/analyze", json={"transcript": "가나다라마바사 " * 40}
    ).json()
    return client.post(
        "/api/skills", json={"dna": 분석["dna"], "slug": 분석["slug"]}
    ).json()["slug"]


def test_손으로_만들_때_폴더_이름을_준다(client, 가짜모델, monkeypatch):
    slug = _결하나(client, monkeypatch)
    body = client.post(
        "/api/produce",
        json={"slug": slug, "topic": "홍범도", "folder": "오늘의 작업"},
    ).json()
    assert body["project_id"] == "오늘의 작업"


def test_못_쓰는_폴더_이름은_이유를_알려준다(client, 가짜모델, monkeypatch):
    slug = _결하나(client, monkeypatch)
    res = client.post(
        "/api/produce", json={"slug": slug, "topic": "홍범도", "folder": "CON"}
    )
    assert res.status_code == 400
    assert "컴퓨터가 쓰는 이름" in res.json()["detail"]


def test_말로_여러_편을_시키면_폴더가_주제별로_갈린다(client, 가짜모델, monkeypatch):
    slug = _결하나(client, monkeypatch)
    monkeypatch.setattr(
        router_mod, "structured",
        lambda **kw: {"action": "produce", "url": "", "reply": "",
                      "notes": "", "skill_hint": "", "topics": ["홍범도", "김좌진"],
                      "minutes": 0, "folder": "독립군 3부작", "instruction": ""},
    )
    body = client.post(
        "/api/say", json={"text": "독립군 3부작 폴더로 홍범도 김좌진 써줘", "state": {}}
    ).json()

    이름들 = sorted(p["project_id"] for p in body["items"])
    assert 이름들 == ["독립군 3부작 - 김좌진", "독립군 3부작 - 홍범도"]


def test_화면에_적은_폴더_이름도_쓴다(client, 가짜모델, monkeypatch):
    """말로는 안 했지만 칸에 적어뒀으면 그걸 쓴다."""
    slug = _결하나(client, monkeypatch)
    monkeypatch.setattr(
        router_mod, "structured",
        lambda **kw: {"action": "produce", "url": "", "reply": "",
                      "notes": "", "skill_hint": "", "topics": ["홍범도"],
                      "minutes": 0, "folder": "", "instruction": ""},
    )
    body = client.post(
        "/api/say", json={"text": "홍범도 써줘", "state": {}, "folder": "칸에 적은 이름"}
    ).json()
    assert body["items"][0]["project_id"] == "칸에 적은 이름"


# ------------------------------------------------------------ 파일 올리기

def test_받는_파일_종류를_알려준다(client):
    body = client.get("/api/upload/kinds").json()
    assert ".srt" in body["extensions"]
    assert ".mp4" in body["extensions"]
    assert isinstance(body["ffmpeg"], bool)


def test_대본_파일을_올리면_결이_나온다(client, 가짜모델):
    대본 = ("그해 겨울은 유난히 추웠습니다. " * 20).encode()
    res = client.post(
        "/api/upload",
        files={"file": ("내대본.txt", io.BytesIO(대본), "text/plain")},
        data={"notes": "화면은 세피아 톤"},
    )
    body = res.json()
    assert res.status_code == 200
    assert body["dna"]["title"] == "담담한 증언체"
    assert body["source"]["title"] == "내대본"
    assert "대본 파일" in body["source"]["transcript_origin"]


def test_빈_파일은_막는다(client, 가짜모델):
    res = client.post("/api/upload", files={"file": ("빈것.txt", io.BytesIO(b""), "text/plain")})
    assert res.status_code == 400


def test_못_받는_종류는_이유를_알려준다(client, 가짜모델):
    res = client.post(
        "/api/upload",
        files={"file": ("바이러스.exe", io.BytesIO(b"x" * 200), "application/octet-stream")},
    )
    assert res.status_code == 422
    assert "받을 수 없는 종류" in res.json()["detail"]
