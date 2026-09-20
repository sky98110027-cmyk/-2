"""꾸밈새. 모델이 돌려준 값을 믿지 않고 걸러내는지 본다."""

import pytest

from gyeol import style


def test_기본값은_가로_화면이다():
    s = style.default_style()
    assert s["aspect_ratio"] == "16:9"
    assert s["caption"]["position"] == "bottom"


def test_기본값을_꺼내도_원본이_안_바뀐다():
    a = style.default_style()
    a["caption"]["size"] = 999
    assert style.default_style()["caption"]["size"] != 999


@pytest.mark.parametrize(
    "넣은값, 나올값",
    [
        ({"size": 9999}, 200),
        ({"size": 1}, 16),
        ({"size": "크게"}, 54),
        ({"outline": -5}, 0),
        ({"background_opacity": 7}, 1),
        ({"background_opacity": -2}, 0),
    ],
)
def test_범위를_벗어난_숫자는_잘라낸다(넣은값, 나올값):
    키 = list(넣은값)[0]
    assert style.normalize({"caption": 넣은값})["caption"][키] == 나올값


@pytest.mark.parametrize("나쁜색", ["red", "#FFF", "rgb(1,2,3)", "", None, "#GGGGGG"])
def test_여섯자리_색이_아니면_기본색으로_돌린다(나쁜색):
    assert style.normalize({"caption": {"color": 나쁜색}})["caption"]["color"] == "#FFFFFF"


def test_제대로_된_색은_대문자로_받는다():
    assert style.normalize({"caption": {"color": "#ffe08a"}})["caption"]["color"] == "#FFE08A"


@pytest.mark.parametrize("나쁜값", ["대각선", "왼쪽", "", None])
def test_없는_위치는_기본값으로_돌린다(나쁜값):
    assert style.normalize({"caption": {"position": 나쁜값}})["caption"]["position"] == "bottom"


def test_없는_화면비율은_가로로_돌린다():
    assert style.normalize({"aspect_ratio": "4:3"})["aspect_ratio"] == "16:9"


def test_세로_비율은_받아준다():
    assert style.normalize({"aspect_ratio": "9:16"})["aspect_ratio"] == "9:16"


def test_아예_딴_것이_와도_안_터진다():
    for 쓰레기 in [None, "글자", 123, [], {"caption": "글자"}]:
        assert style.normalize(쓰레기)["caption"]["size"] == 54


def test_화면_크기는_비율에_따라_나온다():
    assert style.canvas_size("16:9") == (1920, 1080)
    assert style.canvas_size("9:16") == (1080, 1920)


def test_ASS_색은_순서가_뒤집히고_알파가_반대다():
    # #FFE08A -> BGR 로 8AE0FF, 불투명이면 알파 00
    assert style._ass_color("#FFE08A") == "&H008AE0FF"
    assert style._ass_color("#000000", 0.0) == "&HFF000000"


def test_ASS_스타일에_설정이_그대로_실린다():
    s = style.normalize({"caption": {"size": 72, "position": "top", "outline": 6}})
    out = style.to_ass_style(s, "caption")
    assert "Fontsize: 72" in out
    assert "Alignment: 8" in out  # 위
    assert "Outline: 6" in out
    assert "PlayResX: 1920" in out


def test_배경을_넣으면_테두리_방식이_바뀐다():
    민자 = style.to_ass_style(style.normalize({"caption": {"background": "none"}}))
    띠 = style.to_ass_style(style.normalize({"caption": {"background": "band"}}))
    assert "BorderStyle: 1" in 민자
    assert "BorderStyle: 3" in 띠


def test_한_줄_설명이_사람_말로_나온다():
    s = style.normalize({"caption": {"size": 72, "color": "#FFE08A", "position": "middle"}})
    설명 = style.describe(s)
    assert "72px" in 설명
    assert "#FFE08A" in 설명
    assert "가운데 정렬" in 설명
