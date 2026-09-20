"""파일 창고."""

import pytest

from gyeol import skillgen, store


def _save(dna, slug="gyeol-20260920-130000"):
    return store.save_skill(
        dna=dna,
        skill_md=skillgen.build_skill_md(dna, slug),
        source_url="https://youtu.be/abc",
        source_title="봉오동 전투",
        transcript_origin="자동 생성 자막 (ko, json3)",
        material_brief="재료 원문",
        slug=slug,
    )


def test_저장하면_파일_네_개가_생긴다(dna, temp_data):
    meta = _save(dna)
    folder = temp_data / "skills" / meta["slug"]
    for name in ("meta.json", "dna.json", "SKILL.md", "source.txt"):
        assert (folder / name).exists(), f"{name} 이 없다"


def test_클로드_스킬_폴더에도_같이_깔린다(dna, temp_data):
    meta = _save(dna)
    installed = temp_data / "claude-skills" / meta["slug"] / "SKILL.md"
    assert installed.exists()
    assert "담담한 증언체" in installed.read_text(encoding="utf-8")


def test_꺼내면_넣은_그대로다(dna):
    meta = _save(dna)
    got = store.get_skill(meta["slug"])
    assert got["dna"] == dna
    assert got["meta"]["name"] == "담담한 증언체"


def test_최근_것이_목록_위로_온다(dna):
    # 같은 초에 저장돼도 이름으로 갈려서 순서가 확정돼야 한다
    _save(dna, "gyeol-20260101-000000")
    _save(dna, "gyeol-20260920-130000")
    names = [s["slug"] for s in store.list_skills()]
    assert names[0] == "gyeol-20260920-130000"


def test_지우면_설치본까지_같이_지워진다(dna, temp_data):
    meta = _save(dna)
    store.delete_skill(meta["slug"])
    assert not (temp_data / "skills" / meta["slug"]).exists()
    assert not (temp_data / "claude-skills" / meta["slug"]).exists()
    with pytest.raises(store.NotFound):
        store.get_skill(meta["slug"])


@pytest.mark.parametrize(
    "나쁜이름",
    ["../etc", "gyeol/../..", "", "GYEOL-대문자", "a" * 100, "-앞에붙임표"],
)
def test_폴더_밖으로_나가는_이름은_막는다(나쁜이름):
    with pytest.raises(store.NotFound):
        store.get_skill(나쁜이름)


def test_대본을_저장하면_원고_파일도_같이_생긴다(dna, script, temp_data):
    meta = _save(dna)
    record = store.save_script(meta["slug"], script)
    folder = temp_data / "projects" / record["project_id"]
    assert (folder / "script.json").exists()
    assert "그해 겨울은" in (folder / "script.txt").read_text(encoding="utf-8")
    assert store.list_scripts()[0]["topic"] == "홍범도"


def test_원고_형태로_펴면_읽을_수_있게_나온다(script):
    text = store.as_plain_text(script)
    assert "주제 : 홍범도" in text
    assert "약 5분 0초" in text
    assert "1. 기 (12초)" in text
    assert "그해 겨울은 유난히 추웠습니다." in text
    assert "자막 : 1920년 겨울" in text
    assert "- 다까체 유지함" in text


def test_빈_대본도_안_터진다():
    assert store.as_plain_text({}).strip() == "[나레이션 원고]"
