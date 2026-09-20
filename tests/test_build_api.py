"""영상 만들기 통로들. 클로드, ffmpeg, 일레븐랩스는 전부 가짜."""

import pytest
from fastapi.testclient import TestClient

import app as app_module
from gyeol import analyze as analyze_mod
from gyeol import assemble, connect, deep, providers
from gyeol import produce as produce_mod
from gyeol import router as router_mod
from gyeol import store


@pytest.fixture
def client(temp_data):
    with TestClient(app_module.app) as c:
        yield c


@pytest.fixture
def 작업(client, monkeypatch, dna, script):
    monkeypatch.setattr(analyze_mod, "structured", lambda **kw: dna)
    monkeypatch.setattr(produce_mod, "structured", lambda **kw: dict(script))
    분석 = client.post("/api/analyze", json={"transcript": "가" * 200}).json()
    slug = client.post("/api/skills", json={"dna": 분석["dna"], "slug": 분석["slug"],
                                            "source": {"url": "https://youtu.be/ref"}}).json()["slug"]
    pid = client.post("/api/produce", json={"slug": slug, "topic": "홍범도", "folder": "시험"}).json()["project_id"]
    return slug, pid


def 접수(monkeypatch, **intent):
    기본 = {"action": "help", "url": "", "notes": "", "skill_hint": "", "topics": [],
          "minutes": 0, "folder": "", "instruction": "", "reply": ""}
    기본.update(intent)
    monkeypatch.setattr(router_mod, "structured", lambda **kw: dict(기본))


# ------------------------------------------------------------ 타임라인

def test_대본에서_타임라인이_펴져_나온다(client, 작업):
    _, pid = 작업
    v = client.get(f"/api/projects/{pid}/timeline").json()
    assert v["timeline"]["total_seconds"] == 12  # 장면 합. 대본에 적힌 300 이 아니라 실제 합이 진실
    assert len(v["timeline"]["shots"]) == 1
    assert [l["layer"] for l in v["layers"]] == ["screen", "character", "caption", "voice", "ambient", "bgm"]
    assert v["has_reference"] is False
    assert v["video"] is None
    assert "screen" in v["folders"]


def test_제공자를_바꾸면_저장된다(client, 작업):
    _, pid = 작업
    v = client.put(f"/api/projects/{pid}/timeline", json={"providers": {"voice": "elevenlabs", "screen": "folder"}}).json()
    tl = {l["layer"]: l for l in v["layers"]}
    assert tl["voice"]["provider"] == "elevenlabs" and tl["voice"]["ready"] is False
    assert tl["screen"]["provider"] == "folder"
    assert store.get_timeline(pid)["providers"]["voice"] == "elevenlabs"


def test_없는_제공자는_안_받는다(client, 작업):
    _, pid = 작업
    v = client.put(f"/api/projects/{pid}/timeline", json={"providers": {"voice": "없는것"}}).json()
    assert {l["layer"]: l["provider"] for l in v["layers"]}["voice"] == "none"


def test_재료_폴더에_넣으면_개수가_잡힌다(client, 작업, temp_data):
    _, pid = 작업
    (temp_data / "projects" / pid / "screen").mkdir(parents=True)
    (temp_data / "projects" / pid / "screen" / "01.png").write_bytes(b"x")
    (temp_data / "projects" / pid / "bgm.mp3").write_bytes(b"x")
    v = client.get(f"/api/projects/{pid}/timeline").json()
    assert v["assets"]["screen"] == 1 and v["assets"]["bgm"] == 1 and v["assets"]["voice"] == 0


# ------------------------------------------------------------ 프레임 뜯기

def test_뜯으면_결에_레퍼런스가_붙고_새_대본이_그_모양을_따른다(client, 작업, monkeypatch, script):
    slug, _ = 작업
    가짜레퍼런스 = {"total_seconds": 180, "aspect_ratio": "16:9", "providers": {},
                 "shots": [{"no": 1, "start": 0, "seconds": 180}],
                 "cues": {"character": [{"start": 60, "seconds": 3, "text": "밈", "position": "bottom-right", "level": 1, "note": ""}],
                          "caption": [], "voice": [], "ambient": [], "bgm": []},
                 "overall": {"shot_count": 12, "avg_shot_seconds": 15, "silence_count": 2, "music_only_count": 1,
                             "visual_dna": "faded sepia", "character_pattern": "중간에 한 번", "caption_style_note": "", "shot_rules": []}}
    monkeypatch.setattr(deep, "analyze_reference", lambda m, **kw: 가짜레퍼런스)
    monkeypatch.setattr(app_module.source, "fetch_source", lambda url, **kw: app_module.source.SourceMaterial(url=url, timed=[]))

    r = client.post(f"/api/skills/{slug}/deep", json={}).json()
    assert "12컷" in r["reply"] and store.get_reference(slug)["overall"]["visual_dna"] == "faded sepia"

    # 그 뒤로 쓰는 대본은 레퍼런스 모양이 작가에게 넘어간다
    받은것 = {}
    def 엿보기(**kw):
        받은것.update(kw)
        return dict(script)
    monkeypatch.setattr(produce_mod, "structured", 엿보기)
    pid = client.post("/api/produce", json={"slug": slug, "topic": "김좌진"}).json()["project_id"]
    assert "장면 수 12컷" in 받은것["user"] and "faded sepia" in 받은것["user"]

    # 타임라인엔 캐릭터 자리가 비례로 옮겨져 있다 (60초 × 12/180 = 4초)
    v = client.get(f"/api/projects/{pid}/timeline").json()
    assert v["has_reference"] is True
    assert v["timeline"]["cues"]["character"][0]["start"] == 4.0


def test_원본_주소가_없는_결은_뜯을_수_없다고_한다(client, monkeypatch, dna):
    monkeypatch.setattr(analyze_mod, "structured", lambda **kw: dna)
    분석 = client.post("/api/analyze", json={"transcript": "가" * 200}).json()
    slug = client.post("/api/skills", json={"dna": 분석["dna"], "slug": 분석["slug"]}).json()["slug"]
    r = client.post(f"/api/skills/{slug}/deep", json={})
    assert r.status_code == 422 and "원본 영상 주소가 없습니다" in r.json()["detail"]


def test_ffmpeg_없으면_자막으로_되돌아가라고_한다(client, 작업, monkeypatch):
    slug, _ = 작업
    monkeypatch.setattr(app_module.source, "fetch_source", lambda url, **kw: app_module.source.SourceMaterial(url=url))
    monkeypatch.setattr(deep, "ffmpeg_있나", lambda: False)
    r = client.post(f"/api/skills/{slug}/deep", json={})
    assert r.status_code == 422 and "ffmpeg" in r.json()["detail"]


# ------------------------------------------------------------ 목소리

def test_목소리를_안_고르면_막는다(client, 작업):
    _, pid = 작업
    assert client.post(f"/api/projects/{pid}/voice", json={}).status_code == 400


def test_장면마다_읽어서_파일로_남긴다(client, 작업, monkeypatch, temp_data):
    _, pid = 작업
    읽은것 = []
    def 가짜읽기(text, voice_id, out_path, **kw):
        읽은것.append((text, voice_id))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"MP3")
        return out_path
    monkeypatch.setattr(providers, "eleven_speak", 가짜읽기)

    r = client.post(f"/api/projects/{pid}/voice", json={"voice_id": "v1"}).json()
    assert r["made"] == [{"no": 1, "file": "01.mp3"}] and r["failed"] == []
    assert 읽은것[0] == ("그해 겨울은 유난히 추웠습니다.", "v1")
    assert (temp_data / "projects" / pid / "voice" / "01.mp3").exists()
    assert r["view"]["assets"]["voice"] == 1
    assert {l["layer"]: l["provider"] for l in r["view"]["layers"]}["voice"] == "elevenlabs"


def test_키가_틀리면_첫_컷에서_멈춘다(client, 작업, monkeypatch):
    _, pid = 작업
    def 틀림(*a, **k):
        raise providers.ProviderUnavailable("일레븐랩스 키가 틀렸습니다.")
    monkeypatch.setattr(providers, "eleven_speak", 틀림)
    r = client.post(f"/api/projects/{pid}/voice", json={"voice_id": "v1"}).json()
    assert r["made"] == [] and "키가 틀렸습니다" in r["failed"][0]["error"]


def test_목소리_목록은_키가_없으면_그렇게_말한다(client):
    r = client.get("/api/voices")
    assert r.status_code == 503 and "일레븐랩스 키" in r.json()["detail"]


# ------------------------------------------------------------ 조립

def test_그림이_없으면_조립_전에_막는다(client, 작업, monkeypatch):
    _, pid = 작업
    monkeypatch.setattr(assemble, "ffmpeg_path", lambda: "ffmpeg")
    r = client.post(f"/api/projects/{pid}/assemble", json={})
    assert r.status_code == 422 and "그림이 없습니다" in r.json()["detail"]


def test_재료가_있으면_묶어서_영상이_나온다(client, 작업, monkeypatch, temp_data):
    _, pid = 작업
    폴더 = temp_data / "projects" / pid
    (폴더 / "screen").mkdir(parents=True)
    (폴더 / "screen" / "01.png").write_bytes(b"x")

    def 가짜조립(tl, style, work, out, **kw):
        kw["on_step"]("가짜로 묶음")
        out.write_bytes(b"MP4")
        return out
    monkeypatch.setattr(assemble, "build", 가짜조립)

    r = client.post(f"/api/projects/{pid}/assemble", json={}).json()
    assert r["video"] == f"/api/projects/{pid}/video" and r["steps"] == ["가짜로 묶음"]
    assert r["view"]["video"] == r["video"]

    영상 = client.get(f"/api/projects/{pid}/video")
    assert 영상.status_code == 200 and 영상.content == b"MP4"
    assert "video/mp4" in 영상.headers["content-type"]


def test_아직_영상이_없으면_404(client, 작업):
    _, pid = 작업
    r = client.get(f"/api/projects/{pid}/video")
    assert r.status_code == 404 and "먼저 조립" in r.json()["detail"]


# ------------------------------------------------------------ 말로 시키기

def test_조립해달라면_말로도_된다(client, 작업, monkeypatch, temp_data):
    _, pid = 작업
    (temp_data / "projects" / pid / "screen").mkdir(parents=True)
    (temp_data / "projects" / pid / "screen" / "01.png").write_bytes(b"x")
    monkeypatch.setattr(assemble, "build", lambda tl, style, work, out, **kw: out.write_bytes(b"MP4") or out)
    접수(monkeypatch, action="assemble")
    r = client.post("/api/say", json={"text": "조립해줘", "state": {"project_id": pid}}).json()
    assert r["kind"] == "assembled" and r["video"].endswith("/video")


def test_작업이_없는데_조립하라면_그렇게_말한다(client, monkeypatch):
    접수(monkeypatch, action="assemble")
    r = client.post("/api/say", json={"text": "조립해줘", "state": {}}).json()
    assert "조립할 작업이 없습니다" in r["reply"]


def test_읽어달라는데_목소리를_안_골랐으면_목록을_준다(client, 작업, monkeypatch):
    _, pid = 작업
    monkeypatch.setattr(providers, "eleven_voices", lambda: [{"id": "v1", "name": "차분한 남성"}])
    접수(monkeypatch, action="voice")
    r = client.post("/api/say", json={"text": "목소리 입혀줘", "state": {"project_id": pid}}).json()
    assert r["kind"] == "pick_voice" and r["voices"][0]["name"] == "차분한 남성"
