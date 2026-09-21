"""받아둔 파일 받기."""

import pytest

from gyeol import intake
from gyeol.source import SourceUnavailable


@pytest.fixture
def 방(tmp_path):
    return tmp_path


def _쓰기(방, 이름, 내용, encoding="utf-8"):
    path = 방 / 이름
    path.write_bytes(내용.encode(encoding))
    return path


def test_직접_쓴_대본을_받는다(방):
    path = _쓰기(방, "대본.txt", "그해 겨울은 유난히 추웠습니다. " * 20)
    material = intake.from_file(path)
    assert material.title == "대본"
    assert "대본 파일" in material.transcript_origin
    assert "그해 겨울은" in material.transcript


def test_대본의_반복은_지우지_않는다(방):
    """반복은 이 앱이 찾아내야 할 감정 장치다. 지우면 증거가 사라진다."""
    path = _쓰기(방, "대본.txt", "그날. 그날. 그날 우리는 거기 있었습니다. " * 8)
    assert intake.from_file(path).transcript.count("그날.") >= 16


def test_srt_자막을_받는다(방):
    path = _쓰기(
        방,
        "자막.srt",
        "1\n00:00:01,000 --> 00:00:04,000\n안녕하십니까\n\n"
        "2\n00:00:04,000 --> 00:00:08,000\n" + "오늘은 홍범도 장군 이야기입니다 " * 8,
    )
    material = intake.from_file(path)
    assert material.transcript.startswith("안녕하십니까 오늘은")
    assert "-->" not in material.transcript


def test_cp949_로_저장된_자막도_안_깨진다(방):
    path = _쓰기(
        방,
        "옛날자막.srt",
        "1\n00:00:01,000 --> 00:00:04,000\n" + "한글이 깨지지 않아야 합니다 " * 15,
        encoding="cp949",
    )
    assert "한글이 깨지지 않아야 합니다" in intake.from_file(path).transcript


def test_ass_자막에서_대사만_뽑는다(방):
    줄 = "".join(
        f"Dialogue: 0,0:00:0{i},0:00:0{i + 1},Default,,0,0,0,,{{\\b1}}그날의 기록입니다 번호{i}\n"
        for i in range(9)
    )
    path = _쓰기(방, "자막.ass", "[Events]\nFormat: Layer, Start, End\n" + 줄)
    글 = intake.from_file(path).transcript
    assert "그날의 기록입니다" in 글
    assert "Dialogue" not in 글
    assert "\\b1" not in 글


def test_받을_수_없는_종류는_이유를_알려준다(방):
    path = _쓰기(방, "그림.png", "x" * 200)
    with pytest.raises(SourceUnavailable, match="받을 수 없는 종류"):
        intake.from_file(path)


def test_없는_파일은_바로_알려준다(방):
    with pytest.raises(SourceUnavailable, match="찾을 수 없습니다"):
        intake.from_file(방 / "없다.txt")


def test_폴더를_넣으면_막는다(방):
    (방 / "폴더").mkdir()
    with pytest.raises(SourceUnavailable, match="파일이 아닙니다"):
        intake.from_file(방 / "폴더")


def test_내용이_너무_짧으면_막는다(방):
    with pytest.raises(SourceUnavailable, match="너무 짧"):
        intake.from_file(_쓰기(방, "짧다.txt", "짧음"))


def test_너무_큰_파일은_막는다(방, monkeypatch):
    path = _쓰기(방, "큰것.txt", "가" * 200)
    monkeypatch.setattr(intake, "MAX_MB", 0.0001)
    with pytest.raises(SourceUnavailable, match="너무 큽니다"):
        intake.from_file(path)


def test_ffmpeg_가_없으면_영상은_안_받고_이유를_말한다(방, monkeypatch):
    monkeypatch.setattr(intake, "ffmpeg_있나", lambda: False)
    path = _쓰기(방, "무비.mp4", "x" * 200)
    with pytest.raises(SourceUnavailable, match="ffmpeg"):
        intake.from_file(path)


def test_자막이_안_박힌_영상은_솔직히_말한다(방, monkeypatch):
    monkeypatch.setattr(intake, "ffmpeg_있나", lambda: True)

    class 실패:
        returncode = 1

    monkeypatch.setattr(intake.subprocess, "run", lambda *a, **k: 실패())
    path = _쓰기(방, "무비.mp4", "x" * 200)
    with pytest.raises(SourceUnavailable, match="자막이 박혀 있지 않습니다"):
        intake.from_file(path)


# --------------------------------------------------------------- 올리기

def test_올린_파일을_받는다():
    material = intake.from_upload("내대본.txt", ("그해 겨울은 추웠습니다. " * 20).encode())
    assert material.title == "내대본"
    assert "그해 겨울은" in material.transcript


def test_올릴_때_경로를_붙여_보내도_이름만_쓴다():
    """../../ 같은 걸 붙여 보내도 폴더 밖으로 못 나가야 한다."""
    material = intake.from_upload(
        "../../../etc/대본.txt", ("그해 겨울은 추웠습니다. " * 20).encode()
    )
    assert material.title == "대본"


def test_올린_파일도_종류를_가린다():
    with pytest.raises(SourceUnavailable, match="받을 수 없는 종류"):
        intake.from_upload("바이러스.exe", b"x" * 200)


def test_올린_파일도_크기를_가린다(monkeypatch):
    monkeypatch.setattr(intake, "MAX_MB", 0.0001)
    with pytest.raises(SourceUnavailable, match="너무 큽니다"):
        intake.from_upload("큰것.txt", b"x" * 2000)
