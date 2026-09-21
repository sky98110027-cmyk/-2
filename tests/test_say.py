"""명령창. 말 한 줄이 실제로 일이 되는지 끝까지 태워본다."""

import pytest
from fastapi.testclient import TestClient

import app as app_module
from gyeol import analyze as analyze_mod
from gyeol import produce as produce_mod
from gyeol import revise as revise_mod
from gyeol import router as router_mod
from gyeol.llm import LLMUnavailable


@pytest.fixture
def client(temp_data):
    with TestClient(app_module.app) as c:
        yield c


@pytest.fixture
def 가짜모델(monkeypatch, dna, script):
    monkeypatch.setattr(analyze_mod, "structured", lambda **kw: dna)
    monkeypatch.setattr(produce_mod, "structured", lambda **kw: dict(script))


def 접수(monkeypatch, **intent):
    """접수창구가 이렇게 알아들었다고 정해둔다."""
    기본 = {
        "action": "help",
        "url": "",
        "notes": "",
        "skill_hint": "",
        "topics": [],
        "minutes": 0,
        "instruction": "",
        "reply": "",
    }
    기본.update(intent)
    monkeypatch.setattr(router_mod, "structured", lambda **kw: dict(기본))


def 말하기(client, text, state=None, **kw):
    body = {"text": text, "state": state or {}}
    body.update(kw)
    return client.post("/api/say", json=body)


# --------------------------------------------------------------------- 기본

def test_빈_말은_막는다(client):
    assert 말하기(client, "   ").status_code == 400


def test_도움말을_물으면_쓰는_법을_알려준다(client, monkeypatch):
    접수(monkeypatch, action="help")
    body = 말하기(client, "뭘 할 수 있어?").json()
    assert body["kind"] == "message"
    assert "결 뽑기" in body["reply"]


def test_못_알아들으면_되묻는다(client, monkeypatch):
    접수(monkeypatch, action="unclear", reply="무슨 영상 말씀이신가요?")
    body = 말하기(client, "그거 해줘").json()
    assert body["kind"] == "message"
    assert "무슨 영상" in body["reply"]


# ------------------------------------------------------------- 결 뽑고 저장

def test_대본을_주면서_결을_뽑아달라면_뽑는다(client, monkeypatch, 가짜모델):
    접수(monkeypatch, action="analyze", url="https://youtu.be/x")
    body = 말하기(client, "이거 결 뽑아줘", transcript="가나다라마바사 " * 40).json()

    assert body["kind"] == "analysis"
    assert body["analysis"]["dna"]["title"] == "담담한 증언체"
    assert "담담한 증언체" in body["reply"]


def test_주소도_대본도_없으면_되묻는다(client, monkeypatch, 가짜모델):
    접수(monkeypatch, action="analyze", url="")
    assert "영상 주소" in 말하기(client, "결 뽑아줘").json()["reply"]


def test_저장해달라면_방금_뽑은_것을_저장한다(client, monkeypatch, 가짜모델):
    접수(monkeypatch, action="analyze", url="https://youtu.be/x")
    분석 = 말하기(client, "뽑아줘", transcript="가" * 200).json()["analysis"]

    접수(monkeypatch, action="save_skill")
    body = 말하기(client, "저장해줘", state={"pending": 분석}).json()

    assert body["kind"] == "skill_saved"
    assert body["skill"]["name"] == "담담한 증언체"
    assert client.get("/api/skills").json()["skills"][0]["slug"] == 분석["slug"]


def test_뽑은_게_없는데_저장하라면_그렇게_말한다(client, monkeypatch):
    접수(monkeypatch, action="save_skill")
    assert "저장할 결이 없습니다" in 말하기(client, "저장해줘").json()["reply"]


def test_목록을_물으면_알려준다(client, monkeypatch, 가짜모델):
    접수(monkeypatch, action="list_skills")
    assert 말하기(client, "내 결 뭐 있어").json()["skills"] == []


# ----------------------------------------------------------------- 대본 쓰기

def _결하나(client, monkeypatch):
    접수(monkeypatch, action="analyze", url="https://youtu.be/x")
    분석 = 말하기(client, "뽑아줘", transcript="가" * 200).json()["analysis"]
    접수(monkeypatch, action="save_skill")
    return 말하기(client, "저장해줘", state={"pending": 분석}).json()["skill"]


def test_주제를_주면_대본이_나온다(client, monkeypatch, 가짜모델):
    _결하나(client, monkeypatch)
    접수(monkeypatch, action="produce", topics=["홍범도"], minutes=5)
    body = 말하기(client, "홍범도로 5분짜리 써줘").json()

    assert body["kind"] == "script"
    assert len(body["items"]) == 1
    편 = body["items"][0]
    assert 편["script"]["topic"] == "홍범도"
    assert 편["style"]["aspect_ratio"] == "16:9"
    assert 편["project_id"]


def test_주제를_여럿_주면_한꺼번에_나온다(client, monkeypatch, 가짜모델):
    _결하나(client, monkeypatch)
    접수(monkeypatch, action="produce", topics=["홍범도", "김좌진", "안중근"])
    body = 말하기(client, "세 개 한 번에 써줘").json()

    assert body["kind"] == "scripts"
    assert len(body["items"]) == 3
    assert body["failed"] == []
    assert "3편 다 나왔습니다" in body["reply"]
    # 각각 따로 저장돼야 이어서 고칠 수 있다
    작업들 = {p["project_id"] for p in body["items"]}
    assert len(작업들) == 3


def test_여러_편_중_하나가_엎어져도_나머지는_받는다(client, monkeypatch, 가짜모델, script):
    _결하나(client, monkeypatch)

    def 두번째만_엎어뜨리기(**kw):
        두번째만_엎어뜨리기.횟수 += 1
        if 두번째만_엎어뜨리기.횟수 == 2:
            raise LLMUnavailable("요청이 몰렸습니다.")
        return dict(script)

    두번째만_엎어뜨리기.횟수 = 0
    monkeypatch.setattr(produce_mod, "structured", 두번째만_엎어뜨리기)

    접수(monkeypatch, action="produce", topics=["가", "나", "다"])
    body = 말하기(client, "세 개 써줘").json()

    assert len(body["items"]) == 2
    assert len(body["failed"]) == 1
    assert "요청이 몰렸습니다" in body["failed"][0]["error"]


def test_결이_없는데_만들라면_먼저_하라고_한다(client, monkeypatch):
    접수(monkeypatch, action="produce", topics=["홍범도"])
    assert "영상 주소를 먼저" in 말하기(client, "홍범도로 써줘").json()["reply"]


def test_주제를_안_대면_되묻는다(client, monkeypatch, 가짜모델):
    _결하나(client, monkeypatch)
    접수(monkeypatch, action="produce", topics=[])
    assert "어떤 주제로" in 말하기(client, "하나 써줘").json()["reply"]


# ------------------------------------------------------------------- 고치기

def _작업하나(client, monkeypatch, 가짜모델):
    _결하나(client, monkeypatch)
    접수(monkeypatch, action="produce", topics=["홍범도"])
    return 말하기(client, "홍범도로 써줘").json()["items"][0]["project_id"]


def test_고칠_작업이_없으면_그렇게_말한다(client, monkeypatch):
    접수(monkeypatch, action="revise", instruction="자막 크게")
    assert "고칠 작업이 없습니다" in 말하기(client, "자막 크게").json()["reply"]


def test_말로_자막을_고치면_바로_반영된다(client, monkeypatch, 가짜모델):
    작업 = _작업하나(client, monkeypatch, 가짜모델)

    접수(monkeypatch, action="revise", instruction="자막 크게 노란색으로")
    monkeypatch.setattr(
        revise_mod,
        "structured",
        lambda **kw: {
            "understood": "자막을 키우고 노랗게 바꿉니다",
            "style": {"caption": {"size": 84, "color": "#FFE08A"}},
            "scene_changes": [],
            "regenerate_scenes": [],
            "done": ["자막 크기 84, 색 노랑"],
            "note": "",
        },
    )
    body = 말하기(
        client, "자막 크게 노란색으로", state={"project_id": 작업}
    ).json()

    assert body["kind"] == "revised"
    꾸밈 = body["project"]["style"]["caption"]
    assert 꾸밈["size"] == 84
    assert 꾸밈["color"] == "#FFE08A"
    assert body["project"]["revision"]["regenerate_scenes"] == []
    # 자막만 갈아끼우면 되니 ASS 설정도 같이 나와야 한다
    assert "Fontsize: 84" in body["project"]["production_order"]["caption_ass_style"]


def test_고친_내용이_파일에_남는다(client, monkeypatch, 가짜모델):
    작업 = _작업하나(client, monkeypatch, 가짜모델)
    접수(monkeypatch, action="revise", instruction="자막 크게")
    monkeypatch.setattr(
        revise_mod,
        "structured",
        lambda **kw: {
            "understood": "키웁니다",
            "style": {"caption": {"size": 90}},
            "scene_changes": [],
            "regenerate_scenes": [],
            "done": [],
            "note": "",
        },
    )
    말하기(client, "자막 크게", state={"project_id": 작업})

    다시 = client.get(f"/api/projects/{작업}").json()
    assert 다시["style"]["caption"]["size"] == 90
    assert 다시["history"][-1]["note"] == "자막 크게"


# ------------------------------------------------------- 손으로 돌리는 통로

def test_손으로_돌린_값은_클로드를_안_부르고_저장된다(client, monkeypatch, 가짜모델):
    작업 = _작업하나(client, monkeypatch, 가짜모델)

    꾸밈 = client.get(f"/api/projects/{작업}").json()["style"]
    꾸밈["caption"]["size"] = 66
    꾸밈["caption"]["position"] = "middle"
    꾸밈["aspect_ratio"] = "9:16"

    body = client.put(f"/api/projects/{작업}/style", json={"style": 꾸밈}).json()
    assert body["style"]["caption"]["size"] == 66
    assert body["style"]["aspect_ratio"] == "9:16"
    assert "가운데 정렬" in body["style_summary"]
    assert body["production_order"]["aspect_ratio"] == "9:16"


def test_손으로_넣은_엉터리_값도_걸러진다(client, monkeypatch, 가짜모델):
    작업 = _작업하나(client, monkeypatch, 가짜모델)
    body = client.put(
        f"/api/projects/{작업}/style",
        json={"style": {"caption": {"size": 99999, "color": "노랑"}}},
    ).json()
    assert body["style"]["caption"]["size"] == 200
    assert body["style"]["caption"]["color"] == "#FFFFFF"


def test_없는_작업을_찾으면_404(client):
    assert client.get("/api/projects/gyeol-99999999-000000-000000").status_code == 404


def test_작업_이름이_이상하면_막는다(client):
    assert client.get("/api/projects/..%2F..%2Fetc").status_code == 404


def test_글꼴_목록을_내려준다(client):
    body = client.get("/api/style/options").json()
    assert "Pretendard" in body["fonts"]
    assert body["positions"]["bottom"] == "아래"
    assert body["default"]["caption"]["size"] == 54
