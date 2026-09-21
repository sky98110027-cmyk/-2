"""연결. 키가 새어 나가지 않는지가 제일 중요하다."""

import pytest
from fastapi.testclient import TestClient

import app as app_module
from gyeol import connect


@pytest.fixture
def client(temp_data):
    with TestClient(app_module.app) as c:
        yield c


키 = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234"


# ------------------------------------------------------------------ 가리기

@pytest.mark.parametrize(
    "넣은값, 나올값",
    [
        (키, "••••••••1234"),
        ("짧다", "••"),
        ("12345678", "••••••••"),
        ("", ""),
        (None, ""),
    ],
)
def test_키는_끝_네_자리만_보인다(넣은값, 나올값):
    assert connect.mask(넣은값) == 나올값


def test_가린_키에_원래_값이_안_남는다():
    가린것 = connect.mask(키)
    assert "sk-ant" not in 가린것
    assert "abcdef" not in 가린것


# -------------------------------------------------------------- 넣고 빼기

def test_넣으면_파일에_적히고_바로_먹는다(temp_data, monkeypatch):
    import os

    assert connect.set_values({"ANTHROPIC_API_KEY": 키}) == ["ANTHROPIC_API_KEY"]
    assert connect.read_env()["ANTHROPIC_API_KEY"] == 키
    # 앱을 다시 안 켜도 되게 환경변수까지 바꾼다
    assert os.environ["ANTHROPIC_API_KEY"] == 키


def test_파일에_남이_못_읽게_잠근다(temp_data):
    import os
    import stat

    if os.name == "nt":
        pytest.skip("윈도우는 권한 방식이 다르다")

    connect.set_values({"ANTHROPIC_API_KEY": 키})
    권한 = stat.S_IMODE((temp_data / ".env").stat().st_mode)
    assert 권한 == 0o600


def test_같은_값을_다시_넣으면_바뀐_게_없다고_한다(temp_data):
    connect.set_values({"ANTHROPIC_API_KEY": 키})
    assert connect.set_values({"ANTHROPIC_API_KEY": 키}) == []


def test_빈_값을_주면_지운다(temp_data):
    connect.set_values({"ANTHROPIC_API_KEY": 키})
    assert connect.set_values({"ANTHROPIC_API_KEY": ""}) == ["ANTHROPIC_API_KEY"]
    assert "ANTHROPIC_API_KEY" not in connect.read_env()


def test_이상한_이름은_받지_않는다(temp_data):
    assert connect.set_values({"소문자키": "x", "../탈출": "y", "A": "z"}) == []
    assert connect.read_env() == {}


def test_다른_키는_건드리지_않는다(temp_data):
    connect.set_values({"ANTHROPIC_API_KEY": 키, "TOPVIEW_API_KEY": "tv-1234"})
    connect.set_values({"TOPVIEW_API_KEY": "tv-5678"})
    assert connect.read_env()["ANTHROPIC_API_KEY"] == 키


def test_따옴표로_감싼_값도_읽는다(temp_data):
    (temp_data / ".env").write_text('ANTHROPIC_API_KEY="따옴표안"\n', encoding="utf-8")
    assert connect.get_value("ANTHROPIC_API_KEY") == "따옴표안"


def test_주석과_빈_줄은_건너뛴다(temp_data):
    (temp_data / ".env").write_text(
        "# 이건 주석\n\nTOPVIEW_API_KEY=tv-1\n", encoding="utf-8"
    )
    assert connect.read_env() == {"TOPVIEW_API_KEY": "tv-1"}


# -------------------------------------------------------------- 상태 보기

def test_클로드가_맨_위에_오고_꼭_필요하다고_표시된다():
    첫째 = connect.status()[0]
    assert 첫째["name"] == "클로드"
    assert 첫째["required"] is True


def test_상태에는_가린_키만_나간다(temp_data):
    connect.set_values({"ANTHROPIC_API_KEY": 키})
    클로드 = connect.status()[0]
    assert 클로드["connected"] is True
    assert 클로드["masked"] == "••••••••1234"
    assert 키 not in str(클로드)


# ------------------------------------------------------------------ MCP

def test_주소를_주면_주소로_붙인다(temp_data):
    connect.add_mcp("higgsfield", "https://mcp.higgsfield.ai/sse")
    붙은것 = connect.list_mcp()[0]
    assert 붙은것["name"] == "higgsfield"
    assert 붙은것["kind"] == "주소"


def test_명령을_주면_프로그램으로_붙인다(temp_data):
    connect.add_mcp("topview", "npx -y @topview/mcp")
    저장 = connect.read_mcp()["mcpServers"]["topview"]
    assert 저장["command"] == "npx"
    assert 저장["args"] == ["-y", "@topview/mcp"]


@pytest.mark.parametrize("나쁜이름", ["", "한글이름", "띄 어", "../탈출", "a" * 100])
def test_이상한_MCP_이름은_막는다(temp_data, 나쁜이름):
    with pytest.raises(ValueError):
        connect.add_mcp(나쁜이름, "https://x")


def test_붙을_곳이_없으면_막는다(temp_data):
    with pytest.raises(ValueError, match="주소나 실행할 프로그램"):
        connect.add_mcp("okay", "   ")


def test_뗄_수_있다(temp_data):
    connect.add_mcp("higgsfield", "https://x")
    connect.remove_mcp("higgsfield")
    assert connect.list_mcp() == []


def test_없는_걸_떼려_하면_알려준다(temp_data):
    with pytest.raises(ValueError, match="등록되어 있지 않습니다"):
        connect.remove_mcp("없는것")


def test_망가진_설정_파일이어도_안_터진다(temp_data):
    (temp_data / ".mcp.json").write_text("{망가짐", encoding="utf-8")
    assert connect.list_mcp() == []


# ------------------------------------------------------------------ 통로

def test_연결_상태를_내려준다(client):
    body = client.get("/api/connections").json()
    assert body["keys"][0]["name"] == "클로드"
    assert body["mcp"] == []


def test_통로로_키를_넣으면_상태가_바뀐다(client):
    body = client.put(
        "/api/connections", json={"changes": {"ANTHROPIC_API_KEY": 키}}
    ).json()
    assert body["changed"] == ["ANTHROPIC_API_KEY"]
    assert body["keys"][0]["connected"] is True
    assert 키 not in str(body)  # 통째로는 절대 안 나간다
    assert client.get("/api/health").json()["api_key"] is True


def test_바꿀_내용이_없으면_막는다(client):
    assert client.put("/api/connections", json={}).status_code == 400


def test_통로로_MCP를_붙이고_뗀다(client):
    body = client.post(
        "/api/mcp", json={"name": "higgsfield", "target": "https://mcp.higgsfield.ai/sse"}
    ).json()
    assert body["mcp"][0]["name"] == "higgsfield"

    assert client.delete("/api/mcp/higgsfield").json()["mcp"] == []
    assert client.delete("/api/mcp/higgsfield").status_code == 404


def test_키가_없으면_확인이_그렇게_말한다(client):
    body = client.post("/api/connections/test").json()
    assert body["ok"] is False
    assert "키를 먼저" in body["message"]


def _터뜨리기(monkeypatch, 예외):
    """클로드를 부르면 그 예외가 나게 해둔다."""
    import anthropic

    class 가짜:
        class models:
            @staticmethod
            def list(**kw):
                raise 예외

    monkeypatch.setattr(anthropic, "Anthropic", lambda *a, **k: 가짜())


def _응답(status):
    import httpx2

    return httpx2.Response(status, request=httpx2.Request("GET", "https://api.anthropic.com"))


@pytest.mark.parametrize(
    "상황, 나올말",
    [
        ("auth", "키가 틀렸습니다"),
        ("denied", "쓸 수 없습니다"),
        ("network", "연결이 안 됩니다"),
        ("모름", "확인하지 못했습니다"),
    ],
)
def test_확인이_막히면_이유를_사람_말로_알려준다(client, monkeypatch, 상황, 나올말):
    import anthropic
    import httpx2

    connect.set_values({"ANTHROPIC_API_KEY": "아무키"})
    예외 = {
        "auth": lambda: anthropic.AuthenticationError("bad", response=_응답(401), body=None),
        "denied": lambda: anthropic.PermissionDeniedError("no", response=_응답(403), body=None),
        "network": lambda: anthropic.APIConnectionError(
            request=httpx2.Request("GET", "https://api.anthropic.com")
        ),
        "모름": lambda: RuntimeError("뭔지 모를 일"),
    }[상황]()

    _터뜨리기(monkeypatch, 예외)
    body = client.post("/api/connections/test").json()
    assert body["ok"] is False
    assert 나올말 in body["message"]


def test_키가_멀쩡하면_잘_됐다고_한다(client, monkeypatch):
    connect.set_values({"ANTHROPIC_API_KEY": "좋은키"})
    import anthropic

    class 가짜:
        class models:
            @staticmethod
            def list(**kw):
                return []

    monkeypatch.setattr(anthropic, "Anthropic", lambda *a, **k: 가짜())
    body = client.post("/api/connections/test").json()
    assert body["ok"] is True
    assert "잘 연결" in body["message"]
