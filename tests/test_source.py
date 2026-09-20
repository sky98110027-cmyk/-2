"""자막 파서와 재료 만들기."""

import pytest

from gyeol import source


def test_vtt_타임코드와_태그를_털어낸다():
    vtt = """WEBVTT
Kind: captions
Language: ko

1
00:00:01.000 --> 00:00:04.000
<c>안녕하십니까</c>

2
00:00:04.000 --> 00:00:07.000
오늘은 홍범도 장군 이야기입니다
"""
    assert source.parse_vtt(vtt) == "안녕하십니까 오늘은 홍범도 장군 이야기입니다"


def test_vtt_연달아_같은_줄은_한_번만_남긴다():
    vtt = """WEBVTT

00:00:01.000 --> 00:00:02.000
그날 아침

00:00:02.000 --> 00:00:03.000
그날 아침

00:00:03.000 --> 00:00:04.000
눈이 내렸습니다
"""
    assert source.parse_vtt(vtt) == "그날 아침 눈이 내렸습니다"


def test_json3_세그먼트를_이어붙인다():
    data = {
        "events": [
            {"segs": [{"utf8": "그해 "}, {"utf8": "겨울은"}]},
            {"segs": [{"utf8": "\n"}]},
            {"segs": [{"utf8": "유난히 추웠습니다"}]},
        ]
    }
    import json

    assert source.parse_json3(json.dumps(data)) == "그해 겨울은 유난히 추웠습니다"


def test_짧은_대본은_거절한다():
    with pytest.raises(source.SourceUnavailable, match="너무 짧"):
        source.material_from_text("짧다")


def test_대본을_직접_넣으면_재료가_된다():
    material = source.material_from_text("가" * 200, title="봉오동")
    assert material.title == "봉오동"
    assert material.transcript_origin == "직접 붙여넣은 대본"
    assert "봉오동" in material.brief()


def test_주소가_아니면_바로_막는다():
    with pytest.raises(source.SourceUnavailable, match="영상 주소가 아닙니다"):
        source.fetch_source("그냥 글자")


def test_자막_고를_때_직접_올린_것이_먼저다():
    info = {
        "subtitles": {"ko": [{"ext": "vtt", "url": "manual"}]},
        "automatic_captions": {"ko": [{"ext": "json3", "url": "auto"}]},
    }
    url, origin = source._pick_caption_track(info)
    assert url == "manual"
    assert "직접 올린" in origin


def test_한국어가_없으면_영어로_간다():
    info = {"automatic_captions": {"en": [{"ext": "json3", "url": "en-auto"}]}}
    url, origin = source._pick_caption_track(info)
    assert url == "en-auto"
    assert "en" in origin
