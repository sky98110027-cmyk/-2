"""스킬 파일 굽기."""

from gyeol.skillgen import build_skill_md


def test_머리말이_스킬_형식을_지킨다(dna):
    md = build_skill_md(dna, "gyeol-20260920-130000")
    lines = md.splitlines()
    assert lines[0] == "---"
    assert lines[1] == "name: gyeol-20260920-130000"
    assert lines[2].startswith("description: ")
    assert lines[3] == "---"


def test_따옴표가_섞여도_머리말이_안_깨진다(dna):
    dna["title"] = '담담한 "증언"체: 회고'
    dna["one_line"] = "첫 줄\n둘째 줄"
    md = build_skill_md(dna, "gyeol-x")

    desc = md.splitlines()[2][len("description: ") :]
    assert desc.startswith('"') and desc.endswith('"')
    assert '\\"증언\\"' in desc
    assert "\n" not in desc


def test_결의_내용이_본문에_다_들어간다(dna):
    md = build_skill_md(dna, "gyeol-x", "https://youtu.be/abc")
    for expected in [
        "담담한 증언체",
        "다까체",
        "평균 14자",
        "질문 하나를 던지고 멈춘다",
        "faded sepia",
        "인물명 + 한 줄",
        "자극적 과장",
        "https://youtu.be/abc",
    ]:
        assert expected in md, f"'{expected}' 가 스킬 파일에 없다"


def test_점검표는_체크박스로_나온다(dna):
    md = build_skill_md(dna, "gyeol-x")
    assert "- [ ] 다까체 유지" in md


def test_빈_값이_와도_안_터진다():
    md = build_skill_md({"title": "무명", "one_line": ""}, "gyeol-x")
    assert "# 무명" in md
    assert "(없음)" in md
