"""레퍼런스를 프레임 단위로 뜯기. ffmpeg 와 클로드는 가짜로 세운다."""

from pathlib import Path

import pytest

from gyeol import deep
from gyeol.source import SourceMaterial


def test_너무_많은_장면은_고르게_솎는다():
    got = deep.thin(list(range(0, 200, 2)), 10)
    assert len(got) == 10 and got[0] == 0


def test_장면이_적으면_그대로():
    assert deep.thin([0.0, 5.0, 9.0], 60) == [0.0, 5.0, 9.0]


def test_자막_사이_빈_구간을_찾는다():
    timed = [{"start": 1, "end": 4, "text": "가"}, {"start": 9, "end": 12, "text": "나"}, {"start": 12.5, "end": 20, "text": "다"}]
    assert deep.speech_gaps(timed, 30) == [{"start": 0.0, "seconds": 1.0}, {"start": 4, "seconds": 5}, {"start": 20, "seconds": 10}][1:]


def test_빈_구간을_침묵과_음악만으로_가른다():
    gaps = [{"start": 4, "seconds": 5}, {"start": 20, "seconds": 10}]
    quiet, music = deep.classify_gaps(gaps, [{"start": 4.2, "seconds": 4.5}])
    assert quiet == [{"start": 4, "seconds": 5}]
    assert music == [{"start": 20, "seconds": 10}]


def test_ffmpeg_없으면_자막으로_되돌아가라고_한다(monkeypatch):
    monkeypatch.setattr(deep, "ffmpeg_있나", lambda: False)
    with pytest.raises(deep.DeepUnavailable, match="자막으로 결은 뽑힙니다"):
        deep.analyze_reference(SourceMaterial(url="https://x"))


def test_주소도_파일도_없으면_막는다(monkeypatch):
    monkeypatch.setattr(deep, "ffmpeg_있나", lambda: True)
    with pytest.raises(deep.DeepUnavailable, match="주소나 파일"):
        deep.analyze_reference(SourceMaterial())


@pytest.fixture
def 가짜영상(monkeypatch, tmp_path):
    """ffmpeg 가 하는 일을 전부 가짜로. 장면 4컷, 침묵 하나."""
    monkeypatch.setattr(deep, "ffmpeg_있나", lambda: True)
    monkeypatch.setattr(deep, "fetch_video", lambda url, work: tmp_path / "ref.mp4")
    monkeypatch.setattr(deep, "duration", lambda v: 60.0)
    monkeypatch.setattr(deep, "detect_scenes", lambda v, t: [0.0, 15.0, 30.0, 45.0])
    monkeypatch.setattr(deep, "grab_frame", lambda v, at, out: b"JPEG" + str(at).encode())
    monkeypatch.setattr(deep, "detect_silences", lambda v: [{"start": 31.0, "seconds": 3.0}])


def 가짜눈(frames, times, caps):
    """클로드가 봤다 치고. 3번째 장면에 캐릭터, 자막은 아래 노랑."""
    return {
        "shots": [
            {"index": i + 1, "look": f"장면 {i + 1} 모습", "motion_guess": "정지 사진 천천히 확대",
             "on_screen_text": "1920년" if i == 0 else "", "has_character": i == 2,
             "character_what": "밈 짤" if i == 2 else "", "character_where": "bottom-right" if i == 2 else "",
             "caption_position": "bottom", "caption_color": "#FFE08A", "caption_size": "large",
             "caption_has_background": False, "mood": "faded sepia"}
            for i in range(len(frames))
        ],
        "overall": {"visual_dna": "faded sepia, film grain", "character_pattern": "전환부에 한 번",
                    "caption_style_note": "아래 한 줄 노랑", "shot_rules": ["정지 사진 위주"]},
    }


def test_뜯은_결과가_타임라인_모양으로_나온다(가짜영상):
    m = SourceMaterial(url="https://x", timed=[
        {"start": 1, "end": 4, "text": "그해 겨울"}, {"start": 16, "end": 20, "text": "그러나"},
        {"start": 46, "end": 55, "text": "이름을 부릅니다"}])
    ref = deep.analyze_reference(m, looker=가짜눈)

    assert ref["total_seconds"] == 60
    assert [s["start"] for s in ref["shots"]] == [0.0, 15.0, 30.0, 45.0]
    assert ref["shots"][0]["seconds"] == 15.0 and ref["shots"][3]["seconds"] == 15.0
    assert "장면 1 모습" in ref["shots"][0]["image_prompt"] and "faded sepia" in ref["shots"][0]["image_prompt"]

    # 캐릭터는 3번째 장면에만
    assert [c["start"] for c in ref["cues"]["character"]] == [30.0]
    assert ref["cues"]["character"][0]["position"] == "bottom-right"

    # 자막과 목소리는 시간 붙은 자막 그대로
    assert [c["text"] for c in ref["cues"]["caption"]] == ["그해 겨울", "그러나", "이름을 부릅니다"]
    assert ref["cues"]["voice"][1]["start"] == 16.0

    # 말 없는 구간: 4~16 은 침묵 아님(음악만), 20~46 중 31~34 침묵이 있지만 60% 미만 → 음악만, 55~60 음악만
    assert ref["overall"]["silence_count"] + ref["overall"]["music_only_count"] >= 2

    o = ref["overall"]
    assert o["visual_dna"] == "faded sepia, film grain"
    assert o["caption_guess"] == {"position": "bottom", "color": "#FFE08A", "size": "large", "background": False}
    assert o["on_screen_texts"] == ["1920년"]
    assert o["shot_count"] == 4 and o["avg_shot_seconds"] == 15.0


def test_클로드에게_그림과_그때_하는_말을_같이_준다(가짜영상):
    받은것 = {}
    def 엿보기(frames, times, caps):
        받은것.update(frames=frames, times=times, caps=caps)
        return 가짜눈(frames, times, caps)
    m = SourceMaterial(url="https://x", timed=[{"start": 14, "end": 18, "text": "이때 하는 말"}])
    deep.analyze_reference(m, looker=엿보기)
    assert len(받은것["frames"]) == 4
    assert 받은것["caps"][1] == "이때 하는 말"  # 15초 장면에 걸린 자막
    assert 받은것["caps"][0] == ""


def test_받아둔_파일이_있으면_안_받아온다(가짜영상, monkeypatch, tmp_path):
    def 받으면안됨(url, work):
        raise AssertionError("받아둔 파일이 있는데 또 받으려 했다")
    monkeypatch.setattr(deep, "fetch_video", 받으면안됨)
    영상 = tmp_path / "내영상.mp4"
    영상.write_bytes(b"x")
    ref = deep.analyze_reference(SourceMaterial(local_path=str(영상)), looker=가짜눈)
    assert ref["overall"]["shot_count"] == 4


def test_열두_장씩_나눠서_본다(가짜영상, monkeypatch):
    monkeypatch.setattr(deep, "detect_scenes", lambda v, t: [float(i * 2) for i in range(30)])
    횟수 = []
    def 세기(frames, times, caps):
        횟수.append(len(frames))
        return 가짜눈(frames, times, caps)
    deep.analyze_reference(SourceMaterial(url="https://x"), looker=세기)
    assert 횟수 == [12, 12, 6]
