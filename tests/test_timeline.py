"""타임라인, 조립 명령, 제공자, 시간 붙은 자막."""

import pathlib
from unittest import mock

import pytest

from gyeol import assemble as A
from gyeol import providers as P
from gyeol import source
from gyeol import style as S
from gyeol import timeline as T


# ------------------------------------------------------------ 타임라인

@pytest.fixture
def 대본():
    return {"total_seconds": 30, "scenes": [
        {"no": 1, "beat": "기", "seconds": 12, "narration": "그해 겨울", "caption": "1920",
         "image_prompt": "winter", "video_prompt": "slow push", "bgm": "낮은 현악"},
        {"no": 2, "beat": "승", "seconds": 18, "narration": "그러나", "caption": "봉오동",
         "image_prompt": "valley", "video_prompt": "pan right", "bgm": ""},
    ]}


def test_대본이_타임라인으로_펴진다(대본):
    tl = T.from_script(대본)
    assert tl["total_seconds"] == 30
    assert [s["start"] for s in tl["shots"]] == [0.0, 12.0]
    assert [c["text"] for c in tl["cues"]["voice"]] == ["그해 겨울", "그러나"]
    assert [c["text"] for c in tl["cues"]["caption"]] == ["1920", "봉오동"]
    assert len(tl["cues"]["bgm"]) == 1 and tl["cues"]["bgm"][0]["level"] == 0.35


def test_시작_시각을_안_주면_앞_장면_끝에_이어_붙는다():
    tl = T.normalize({"shots": [{"seconds": 5}, {"seconds": 7}, {"seconds": 3}]})
    assert [s["start"] for s in tl["shots"]] == [0.0, 5.0, 12.0]
    assert tl["total_seconds"] == 15


def test_모델이_준_쓰레기를_걸러낸다():
    tl = T.normalize({"shots": [{"seconds": "많이"}, "글자", None],
                      "providers": {"voice": "없는것", "screen": "topview", "엉뚱": "x"},
                      "aspect_ratio": "4:3", "cues": {"voice": [{"start": "x", "level": 9}]}})
    assert len(tl["shots"]) == 3  # 못 읽는 건 기본값 8초로
    assert tl["providers"]["voice"] == "none"
    assert tl["providers"]["screen"] == "topview"
    assert tl["aspect_ratio"] == "16:9"
    assert tl["cues"]["voice"][0]["level"] == 1.0


def test_레이어마다_제공자_준비_상태를_본다(대본):
    tl = T.from_script(대본)
    tl["providers"]["voice"] = "elevenlabs"
    st = {s["layer"]: s for s in T.provider_status(tl, set())}
    assert st["voice"]["ready"] is False and st["voice"]["missing"] == ["ELEVENLABS_API_KEY"]
    st = {s["layer"]: s for s in T.provider_status(tl, {"ELEVENLABS_API_KEY"})}
    assert st["voice"]["ready"] is True
    assert st["screen"]["count"] == 2 and st["voice"]["count"] == 2


def test_레이어_이름과_제공자_목록이_다_있다():
    assert [l["key"] for l in T.LAYERS] == ["screen", "character", "caption", "voice", "ambient", "bgm"]
    for key in T.LAYER_KEYS:
        assert T.PROVIDERS[key], f"{key} 에 제공자 목록이 없다"
        assert T.DEFAULT_PROVIDERS[key] in [p["id"] for p in T.PROVIDERS[key]]


def test_사람이_읽을_글로_편다(대본):
    글 = T.describe(T.from_script(대본))
    assert "전체 30초" in 글 and "[0:00–0:12] 기" in 글 and "배경음: 0:00 낮은 현악" in 글


# ------------------------------------------------------------ 자막 시간

def test_자막_시간을_살려_읽는다():
    vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:04.500\n<c>그해</c> 겨울\n\n00:01:02,000 --> 00:01:05,000\n쉼표도\n"
    got = source.parse_vtt_timed(vtt)
    assert got == [{"start": 1.0, "end": 4.5, "text": "그해 겨울"}, {"start": 62.0, "end": 65.0, "text": "쉼표도"}]


def test_json3_자막_시간을_살려_읽는다():
    import json
    raw = json.dumps({"events": [{"tStartMs": 1000, "dDurationMs": 3500, "segs": [{"utf8": "그해 "}, {"utf8": "겨울"}]}]})
    assert source.parse_json3_timed(raw) == [{"start": 1.0, "end": 4.5, "text": "그해 겨울"}]


def test_시각_표기가_어떻게_와도_초로_바꾼다():
    assert source._ts("00:01:02.500") == 62.5
    assert source._ts("01:02,500") == 62.5
    assert source._ts("7.25") == 7.25
    assert source._ts("이상함") == 0.0


# ------------------------------------------------------------ 조립 명령

@pytest.fixture
def ffmpeg있는척(monkeypatch):
    monkeypatch.setattr(A, "ffmpeg_path", lambda: "ffmpeg")


def test_ffmpeg_없으면_어디서_받는지_알려준다():
    with mock.patch.object(A.shutil, "which", return_value=None):
        with pytest.raises(A.AssembleUnavailable, match="ffmpeg.org"):
            A.ffmpeg_path()


def test_장면_조각은_아주_천천히_확대한다(ffmpeg있는척, tmp_path):
    cmd = A.shot_command(tmp_path / "01.png", tmp_path / "s.mp4", 12, "16:9")
    vf = cmd[cmd.index("-vf") + 1]
    assert "zoompan" in vf and "1.08" in vf  # 끝까지 가도 8퍼센트
    assert "s=1920x1080" in vf
    assert cmd[cmd.index("-t") + 1] == "12.000"


def test_세로_화면이면_세로_크기로(ffmpeg있는척, tmp_path):
    vf = A.shot_command(tmp_path / "a.png", tmp_path / "s.mp4", 5, "9:16")
    assert "s=1080x1920" in vf[vf.index("-vf") + 1]


def test_명령은_리스트라_공백_있는_이름도_안_깨진다(ffmpeg있는척, tmp_path):
    파일 = tmp_path / "내 그림 01.png"
    cmd = A.shot_command(파일, tmp_path / "s.mp4", 5, "16:9")
    assert str(파일) in cmd


def test_소리를_시간_맞춰_섞고_배경음은_작게(ffmpeg있는척, tmp_path):
    cmd = A.mix_command(tmp_path / "j.mp4", tmp_path / "o.mp4",
                        voice=[(tmp_path / "v1.mp3", 0.0), (tmp_path / "v2.mp3", 12.5)],
                        bgm=(tmp_path / "bgm.mp3", 0.3), total_seconds=30)
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "adelay=12500|12500" in fc
    assert "volume=0.30" in fc
    assert "amix=inputs=3" in fc
    assert "-stream_loop" in cmd  # 배경음은 돌려 튼다
    assert cmd[cmd.index("-t") + 1] == "30.000"


def test_캐릭터는_그_시간에만_뜬다(ffmpeg있는척, tmp_path):
    cmd = A.mix_command(tmp_path / "j.mp4", tmp_path / "o.mp4",
                        characters=[(tmp_path / "meme.png", 5.0, 3.0, "bottom-right")])
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "between(t,5.00,8.00)" in fc
    assert "overlay=W-w-40:H-h-40" in fc


@pytest.mark.parametrize("자리, 나올값", [
    ("top-left", ("40", "40")), ("bottom-right", ("W-w-40", "H-h-40")),
    ("center", ("(W-w)/2", "H-h-40")), ("middle-left", ("40", "(H-h)/2")), ("", ("W-w-40", "H-h-40")),
])
def test_캐릭터_자리_말을_좌표로(자리, 나올값):
    assert A._place(자리) == 나올값


def test_소리가_하나도_없으면_무음으로(ffmpeg있는척, tmp_path):
    cmd = A.mix_command(tmp_path / "j.mp4", tmp_path / "o.mp4")
    assert "-an" in cmd and "-filter_complex" not in cmd


def test_ASS_자막_파일이_제대로_나온다(tmp_path):
    out = A.write_ass([{"start": 0, "seconds": 4, "text": "그해 겨울\n추웠습니다"},
                       {"start": 4, "seconds": 3, "text": ""}], S.default_style(), tmp_path / "c.ass")
    글 = out.read_text(encoding="utf-8")
    assert "PlayResX: 1920" in glow(글)
    assert "Style: caption,Pretendard,54," in 글
    assert "Dialogue: 0,0:00:00.00,0:00:04.00,caption,,0,0,0,,그해 겨울\\N추웠습니다" in 글
    assert 글.count("Dialogue:") == 1  # 빈 자막은 안 넣는다


def glow(s):
    return s


def test_그림이_빠진_장면이_있으면_조립_전에_막는다(ffmpeg있는척, tmp_path):
    tl = T.normalize({"shots": [{"no": 1, "seconds": 5}, {"no": 2, "seconds": 5}]})
    with pytest.raises(A.AssembleUnavailable, match="장면 2 번 그림이 없습니다"):
        A.build(tl, S.default_style(), tmp_path / "w", tmp_path / "o.mp4",
                screen_assets={1: tmp_path / "01.png"}, run=lambda cmd: None)


def test_조립은_순서대로_명령을_보낸다(ffmpeg있는척, tmp_path):
    tl = T.from_script({"total_seconds": 10, "scenes": [
        {"no": 1, "seconds": 5, "narration": "가", "caption": "가"},
        {"no": 2, "seconds": 5, "narration": "나", "caption": "나"}]})
    보낸것 = []
    A.build(tl, S.default_style(), tmp_path / "w", tmp_path / "o.mp4",
            screen_assets={1: tmp_path / "1.png", 2: tmp_path / "2.mp4"},
            voice_assets={1: tmp_path / "1.mp3"}, run=보낸것.append)
    assert len(보낸것) == 4  # 장면 둘, 잇기, 섞기
    assert "zoompan" in " ".join(보낸것[0])   # 그림은 확대
    assert "zoompan" not in " ".join(보낸것[1]) and "-t" in 보낸것[1]  # 영상은 자르기만
    assert "concat" in 보낸것[2]
    assert "subtitles=" in " ".join(보낸것[3]) and "adelay=0|0" in " ".join(보낸것[3])


# ------------------------------------------------------------ 제공자

def test_폴더_파일을_장면_번호로_묶는다(tmp_path):
    for n in ["01.png", "장면2.png", "scene_03_final.jpg", "메모.txt", "2_다른것.png", "cover.png"]:
        (tmp_path / n).write_bytes(b"x")
    got = P.folder_assets(tmp_path, P.IMAGE_EXTS)
    assert {k: v.name for k, v in got.items()} == {1: "01.png", 2: "2_다른것.png", 3: "scene_03_final.jpg"}


def test_없는_폴더는_빈_것(tmp_path):
    assert P.folder_assets(tmp_path / "없음", P.IMAGE_EXTS) == {}


def test_일레븐랩스_키_없으면_그렇게_말한다(temp_data, tmp_path):
    with pytest.raises(P.ProviderUnavailable, match="일레븐랩스 키가 없습니다"):
        P.eleven_speak("가", "voice", tmp_path / "a.mp3")


def test_일레븐랩스_원고_비면_막는다(temp_data, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "키")
    with pytest.raises(P.ProviderUnavailable, match="비어 있습니다"):
        P.eleven_speak("   ", "voice", tmp_path / "a.mp3")


@pytest.mark.parametrize("코드, 나올말", [(401, "틀렸습니다"), (422, "받지 않았습니다"), (429, "몫을 다 썼거나"), (500, "오류를 돌려줬습니다")])
def test_일레븐랩스_오류를_사람_말로(temp_data, tmp_path, monkeypatch, 코드, 나올말):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "키")
    monkeypatch.setattr(P.httpx, "post", lambda *a, **k: type("R", (), {"status_code": 코드, "content": b""})())
    with pytest.raises(P.ProviderUnavailable, match=나올말):
        P.eleven_speak("원고", "voice", tmp_path / "a.mp3")


def test_일레븐랩스가_되면_파일로_남긴다(temp_data, tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "키")
    받은몸통 = {}
    def 가짜post(url, headers, json, timeout):
        받은몸통.update(json)
        return type("R", (), {"status_code": 200, "content": b"MP3DATA"})()
    monkeypatch.setattr(P.httpx, "post", 가짜post)
    out = P.eleven_speak("그해 겨울", "v1", tmp_path / "소리" / "a.mp3", speed=0.9)
    assert out.read_bytes() == b"MP3DATA"
    assert 받은몸통["model_id"] == "eleven_multilingual_v2"
    assert 받은몸통["voice_settings"]["speed"] == 0.9
