"""앱이 스스로 설명하기."""

import pytest
from fastapi.testclient import TestClient

import app as app_module
from gyeol import guide
from gyeol import router as router_mod


@pytest.fixture
def client(temp_data):
    with TestClient(app_module.app) as c:
        yield c


def test_빈_물음은_되묻는다():
    with pytest.raises(ValueError, match="무엇이 궁금"):
        guide.answer("   ")


def test_지금_상태를_같이_넘긴다(monkeypatch):
    받은것 = {}

    def 엿보기(**kw):
        받은것.update(kw)
        return {"answer": "이렇게 쓰십니다", "try_this": []}

    monkeypatch.setattr(guide, "structured", 엿보기)
    guide.answer("어떻게 써?", {"skills": ["담담한 증언체"], "project": "독립군", "claude": True})

    보낸말 = 받은것["user"]
    assert "담담한 증언체" in 보낸말
    assert "독립군" in 보낸말
    assert "어떻게 써?" in 보낸말


def test_안내문에_못_하는_것도_적혀_있다():
    """할 수 있다고만 말하면 형님이 헛수고를 한다."""
    for 솔직한말 in ["글로 옮기지 못한다", "눈으로 보지 못한다", "직접 만들어내지 못한다"]:
        assert 솔직한말 in guide.GUIDE_SYSTEM


def test_물어보면_클로드가_답하고_해볼_말까지_준다(client, monkeypatch):
    monkeypatch.setattr(
        router_mod, "structured",
        lambda **kw: {"action": "ask", "url": "", "reply": "", "notes": "",
                      "skill_hint": "", "topics": [], "minutes": 0,
                      "folder": "", "instruction": ""},
    )
    monkeypatch.setattr(
        guide, "structured",
        lambda **kw: {
            "answer": "자막 색은 언제든 바꿀 수 있습니다.\n영상을 다시 뽑지 않아도 됩니다.",
            "try_this": ["자막 노란색으로 바꿔줘"],
        },
    )
    body = client.post("/api/say", json={"text": "자막 색도 바꿀 수 있어?", "state": {}}).json()

    assert body["kind"] == "answer"
    assert "자막 색은 언제든" in body["reply"]
    assert body["try_this"] == ["자막 노란색으로 바꿔줘"]


def test_목록을_통째로_보여달라면_적어둔_안내를_준다(client, monkeypatch):
    monkeypatch.setattr(
        router_mod, "structured",
        lambda **kw: {"action": "help", "url": "", "reply": "", "notes": "",
                      "skill_hint": "", "topics": [], "minutes": 0,
                      "folder": "", "instruction": ""},
    )
    body = client.post("/api/say", json={"text": "할 수 있는 거 다 보여줘", "state": {}}).json()
    assert body["kind"] == "message"
    assert "결 뽑기" in body["reply"]
