"""영상 만들 준비가 됐는지 점검하기."""

import pytest
from fastapi.testclient import TestClient

import app as app_module
from gyeol import connect, intake
from gyeol import router as router_mod


@pytest.fixture
def client(temp_data):
    with TestClient(app_module.app) as c:
        yield c


@pytest.fixture
def ffmpeg없음(monkeypatch):
    monkeypatch.setattr(intake, "ffmpeg_있나", lambda: False)


def test_아무것도_없으면_클로드부터_붙이라고_한다(temp_data, ffmpeg없음):
    r = connect.readiness()
    assert r["can_write"] is False
    assert r["all_ready"] is False
    assert "클로드부터" in r["summary"]


def test_클로드만_붙어도_대본까지는_된다(temp_data, ffmpeg없음):
    connect.set_values({"ANTHROPIC_API_KEY": "키"})
    r = connect.readiness()
    assert r["can_write"] is True
    assert r["all_ready"] is False
    assert "대본까지는 지금 바로" in r["summary"]
    assert r["steps"][0]["ok"] is True


def test_그림_도구는_둘_중_하나만_있으면_된다(temp_data, ffmpeg없음):
    connect.set_values({"ANTHROPIC_API_KEY": "키", "TOPVIEW_API_KEY": "tv"})
    그림 = next(s for s in connect.readiness()["steps"] if s["step"] == "장면 그림 뽑기")
    assert 그림["ok"] is True
    assert 그림["have"] == ["톱뷰"]


def test_다_붙으면_다_됐다고_한다(temp_data, monkeypatch):
    monkeypatch.setattr(intake, "ffmpeg_있나", lambda: True)
    connect.set_values(
        {
            "ANTHROPIC_API_KEY": "키",
            "HIGGSFIELD_API_KEY": "hf",
            "ELEVENLABS_API_KEY": "el",
        }
    )
    r = connect.readiness()
    assert r["all_ready"] is True
    assert "다 준비됐습니다" in r["summary"]


def test_안_붙은_단계마다_우회로를_알려준다(temp_data, ffmpeg없음):
    """없다고만 하면 막막하다. 없어도 되는 길을 같이 알려줘야 한다."""
    connect.set_values({"ANTHROPIC_API_KEY": "키"})
    막힌것 = [s for s in connect.readiness()["steps"] if not s["ok"]]
    assert 막힌것
    for s in 막힌것:
        assert s["detour"], f"'{s['step']}' 에 우회로가 없다"
        assert s["missing"], f"'{s['step']}' 에 뭐가 필요한지 안 적혀 있다"


def test_ffmpeg는_컴퓨터에_깔렸는지_본다(temp_data, monkeypatch):
    monkeypatch.setattr(intake, "ffmpeg_있나", lambda: True)
    자막 = next(s for s in connect.readiness()["steps"] if "자막" in s["step"])
    assert 자막["ok"] is True

    monkeypatch.setattr(intake, "ffmpeg_있나", lambda: False)
    자막 = next(s for s in connect.readiness()["steps"] if "자막" in s["step"])
    assert 자막["ok"] is False
    assert "ffmpeg.org" in 자막["missing"][0]


def test_없는_MCP_주소를_지어내지_않는다():
    """모르는 주소를 박아두면 형님이 헤맨다. 어디서 받는지만 알려준다."""
    for spec in connect.연결목록:
        assert "mcp_hint" in spec
        assert "http" not in spec["mcp_hint"], f"{spec['name']} 에 지어낸 주소가 있다"


# ------------------------------------------------------------------ 통로

def test_통로로_점검표를_내려준다(client):
    body = client.get("/api/readiness").json()
    assert body["steps"][0]["step"] == "대본과 장면 짜기"
    assert isinstance(body["summary"], str)


def test_영상_만들고_싶다고_하면_점검표를_보여준다(client, monkeypatch):
    monkeypatch.setattr(
        router_mod, "structured",
        lambda **kw: {"action": "ready", "url": "", "reply": "", "notes": "",
                      "skill_hint": "", "topics": [], "minutes": 0,
                      "folder": "", "instruction": ""},
    )
    body = client.post("/api/say", json={"text": "영상 만들고 싶어", "state": {}}).json()
    assert body["kind"] == "readiness"
    assert body["readiness"]["steps"]
    assert body["reply"] == body["readiness"]["summary"]
