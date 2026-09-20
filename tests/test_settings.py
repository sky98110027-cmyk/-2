"""저장 폴더 바꾸기와, 같이 돌릴 때 이름이 겹치지 않는지."""

import pytest
from fastapi.testclient import TestClient

import app as app_module
from gyeol import store


@pytest.fixture
def client(temp_data):
    with TestClient(app_module.app) as c:
        yield c


# ----------------------------------------------------- 같이 돌릴 때 이름 겹침

def test_같은_초에_여러_편을_저장해도_이름이_안_겹친다(dna, script):
    """여러 편을 같이 돌리면 저장이 같은 초에 몰린다.

    시각만으로 이름을 지으면 서로 덮어쓴다. 실제로 그렇게 터졌었다.
    """
    store.save_skill(dna=dna, skill_md="---\nname: x\n---\n", slug="gyeol-20260920-130000")
    이름들 = {
        store.save_script("gyeol-20260920-130000", script)["project_id"]
        for _ in range(20)
    }
    assert len(이름들) == 20


def test_저장하면_폴더가_실제로_따로_생긴다(dna, script, temp_data):
    store.save_skill(dna=dna, skill_md="---\nname: x\n---\n", slug="gyeol-20260920-130000")
    for _ in range(5):
        store.save_script("gyeol-20260920-130000", script)
    assert len(list((temp_data / "projects").iterdir())) == 5


# --------------------------------------------------------------- 저장 폴더

def test_지금_어디에_쌓는지_알려준다(client, temp_data):
    body = client.get("/api/settings").json()
    assert body["data_dir"] == str(temp_data)
    assert body["skill_count"] == 0
    assert "can_browse" in body


def test_폴더를_바꾸면_그_뒤부터_거기에_쌓인다(client, temp_data, dna):
    새폴더 = temp_data / "바탕화면" / "내영상"
    body = client.put("/api/settings", json={"data_dir": str(새폴더)}).json()

    assert body["data_dir"] == str(새폴더)
    assert 새폴더.exists()
    assert (새폴더 / "skills").exists()
    assert (새폴더 / "projects").exists()

    store.save_skill(dna=dna, skill_md="---\nname: x\n---\n", slug="gyeol-20260920-130000")
    assert (새폴더 / "skills" / "gyeol-20260920-130000" / "dna.json").exists()


def test_상대경로도_받아준다(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    body = client.put("/api/settings", json={"data_dir": "결과물"}).json()
    assert body["data_dir"] == str((tmp_path / "결과물").resolve())


def test_물결표는_집_폴더로_푼다(client):
    import shutil
    from pathlib import Path

    집 = Path.home() / ".gyeol-테스트"
    try:
        body = client.put("/api/settings", json={"data_dir": "~/.gyeol-테스트"}).json()
        assert body["data_dir"] == str(집)
        assert (집 / "skills").exists()
    finally:
        shutil.rmtree(집, ignore_errors=True)


def test_빈_경로는_막는다(client):
    res = client.put("/api/settings", json={"data_dir": "   "})
    assert res.status_code == 400
    assert "폴더를 적어주세요" in res.json()["detail"]


def test_못_쓰는_자리는_이유를_알려준다(client, monkeypatch):
    from pathlib import Path

    def 권한없음(self, *a, **kw):
        raise OSError(13, "Permission denied")

    monkeypatch.setattr(Path, "mkdir", 권한없음)
    res = client.put("/api/settings", json={"data_dir": "/아무데나"})
    assert res.status_code == 400
    assert "만들 수 없습니다" in res.json()["detail"]


def test_폴더_창을_못_띄우면_그렇게_알려준다(client, monkeypatch):
    from gyeol import picker

    def 못띄움(start=""):
        raise picker.PickerUnavailable("이 컴퓨터에서는 폴더 창을 띄울 수 없습니다.")

    monkeypatch.setattr(picker, "ask_folder", 못띄움)
    res = client.post("/api/settings/browse")
    assert res.status_code == 503
    assert "직접 적어" in res.json()["detail"] or "띄울 수 없습니다" in res.json()["detail"]


def test_폴더_창에서_취소하면_빈_값이_온다(client, monkeypatch):
    from gyeol import picker

    monkeypatch.setattr(picker, "ask_folder", lambda start="": "")
    assert client.post("/api/settings/browse").json()["picked"] == ""
