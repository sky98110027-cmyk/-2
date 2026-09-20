"""말로 고치기. 바꾸라고 한 자리만 바뀌는지 본다."""

import pytest

from gyeol import revise


@pytest.fixture
def 대본():
    return {
        "topic": "홍범도",
        "total_seconds": 30,
        "scenes": [
            {
                "no": 1,
                "seconds": 12,
                "narration": "그해 겨울은 추웠습니다.",
                "caption": "1920년",
                "image_prompt": "winter valley",
                "video_prompt": "slow push",
                "bgm": "현악",
            },
            {
                "no": 2,
                "seconds": 18,
                "narration": "그러나 그는 돌아왔습니다.",
                "caption": "봉오동",
                "image_prompt": "mountain path",
                "video_prompt": "pan right",
                "bgm": "북소리",
            },
        ],
    }


def test_집어준_자리만_바뀐다(대본):
    새것, 한일 = revise.apply_changes(
        대본, [{"no": 2, "field": "caption", "new_value": "봉오동 골짜기"}]
    )
    assert 새것["scenes"][1]["caption"] == "봉오동 골짜기"
    assert 새것["scenes"][0]["caption"] == "1920년"
    assert 새것["scenes"][1]["narration"] == "그러나 그는 돌아왔습니다."
    assert 한일 == ["2번 장면 자막 고침"]


def test_원본은_손대지_않는다(대본):
    revise.apply_changes(대본, [{"no": 1, "field": "narration", "new_value": "바뀐 말"}])
    assert 대본["scenes"][0]["narration"] == "그해 겨울은 추웠습니다."


def test_길이를_고치면_전체_길이가_다시_더해진다(대본):
    새것, _ = revise.apply_changes(대본, [{"no": 1, "field": "seconds", "new_value": "20"}])
    assert 새것["scenes"][0]["seconds"] == 20
    assert 새것["total_seconds"] == 38


def test_길이는_터무니없으면_잘린다(대본):
    새것, _ = revise.apply_changes(대본, [{"no": 1, "field": "seconds", "new_value": "99999"}])
    assert 새것["scenes"][0]["seconds"] == 600


@pytest.mark.parametrize(
    "나쁜요청",
    [
        {"no": 99, "field": "caption", "new_value": "없는 장면"},
        {"no": 1, "field": "아무거나", "new_value": "x"},
        {"no": 1, "field": "seconds", "new_value": "스무초"},
        {"field": "caption", "new_value": "번호 없음"},
        {"no": 1, "new_value": "항목 없음"},
        {"no": 1, "field": "caption"},
    ],
)
def test_말이_안_되는_요청은_그냥_흘린다(대본, 나쁜요청):
    새것, 한일 = revise.apply_changes(대본, [나쁜요청])
    assert 한일 == []
    assert 새것 == 대본


def test_요청이_비어도_안_터진다(대본):
    assert revise.apply_changes(대본, [])[1] == []
    assert revise.apply_changes(대본, None)[1] == []


def test_요약에_장면_내용이_다_담긴다(대본):
    요약 = revise._script_digest(대본)
    assert "주제: 홍범도" in 요약
    assert "[1번" in 요약 and "[2번" in 요약
    assert "winter valley" in 요약


def test_빈_요청은_되묻는다(대본):
    with pytest.raises(ValueError, match="무엇을 고칠지"):
        revise.revise(대본, {}, "   ")


def test_그림을_안_바꿨으면_다시_뽑으란_말을_안_듣는다(monkeypatch, 대본):
    """모델이 다시 뽑으라고 해도, 실제로 그림 지시가 안 바뀌었으면 무시한다."""
    monkeypatch.setattr(
        revise,
        "structured",
        lambda **kw: {
            "understood": "자막만 고칩니다",
            "style": {"caption": {"size": 72}},
            "scene_changes": [{"no": 1, "field": "caption", "new_value": "새 자막"}],
            "regenerate_scenes": [1, 2],  # 근거 없는 주장
            "done": ["자막 고침"],
            "note": "",
        },
    )
    결과 = revise.revise(대본, {}, "자막 키워줘")
    assert 결과["regenerate_scenes"] == []
    assert 결과["style"]["caption"]["size"] == 72
    assert 결과["style_changed"] is True


def test_그림_지시를_바꿨으면_다시_뽑으라고_알린다(monkeypatch, 대본):
    monkeypatch.setattr(
        revise,
        "structured",
        lambda **kw: {
            "understood": "1번 그림을 눈밭으로 바꿉니다",
            "style": {},
            "scene_changes": [
                {"no": 1, "field": "image_prompt", "new_value": "snow field"}
            ],
            "regenerate_scenes": [1],
            "done": ["1번 그림 지시 바꿈"],
            "note": "",
        },
    )
    결과 = revise.revise(대본, {}, "1번을 눈밭으로")
    assert 결과["regenerate_scenes"] == [1]
    assert 결과["script"]["scenes"][0]["image_prompt"] == "snow field"


def test_모델이_이상한_스타일을_줘도_걸러진다(monkeypatch, 대본):
    monkeypatch.setattr(
        revise,
        "structured",
        lambda **kw: {
            "understood": "",
            "style": {"caption": {"color": "노랑", "size": 9999}},
            "scene_changes": [],
            "regenerate_scenes": [],
            "done": [],
            "note": "",
        },
    )
    결과 = revise.revise(대본, {}, "노랗게")
    assert 결과["style"]["caption"]["color"] == "#FFFFFF"
    assert 결과["style"]["caption"]["size"] == 200
