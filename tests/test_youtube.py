"""유튜브에 올리기.

올리는 일은 되돌릴 수 없다.
여기서 제일 중요한 건 '함부로 안 올라가는가' 다.
"""

import json

import pytest

from gyeol import youtube as yt


# --------------------------------------------------- 함부로 안 올라가는가

def test_확인을_안_받으면_아무것도_안_한다(tmp_path):
    """이게 뚫리면 남의 눈에 영상이 뜬다. 제일 중요한 방어선이다."""
    영상 = tmp_path / "영상.mp4"
    영상.write_bytes(b"x" * 100)

    with pytest.raises(yt.NotConfirmed, match="확인을 눌러주세요"):
        yt.upload(영상, title="제목")


def test_확인을_안_받으면_파일도_안_열어본다(tmp_path):
    """확인이 먼저다. 파일이 없어도 확인부터 막아야 한다."""
    with pytest.raises(yt.NotConfirmed):
        yt.upload(tmp_path / "없는영상.mp4", title="제목")


def test_기본_공개범위는_비공개다():
    """말 안 하면 비공개여야 한다. 실수로 공개되면 되돌릴 수 없다."""
    assert yt.build_body("제목")["status"]["privacyStatus"] == "private"


def test_공개는_직접_골라야만_된다():
    assert yt.build_body("제목", privacy="public")["status"]["privacyStatus"] == "public"


@pytest.mark.parametrize("나쁜값", ["", "전체공개", "PUBLIC", "아무거나", None])
def test_모르는_공개범위는_막는다(나쁜값):
    with pytest.raises(yt.YoutubeUnavailable, match="쓸 수 없는 공개 범위"):
        yt.build_body("제목", privacy=나쁜값)


def test_어린이용으로_표시하지_않는다():
    """어린이용으로 잘못 걸리면 댓글이 막힌다."""
    assert yt.build_body("제목")["status"]["selfDeclaredMadeForKids"] is False


# ------------------------------------------------------------ 보낼 내용

def test_제목_앞뒤_공백과_줄바꿈을_정리한다():
    assert yt.build_body("  홍범도   장군의\n그날  ")["snippet"]["title"] == "홍범도 장군의 그날"


def test_제목이_없으면_막는다():
    for 빈값 in ["", "   ", "\n", None]:
        with pytest.raises(yt.YoutubeUnavailable, match="제목을 적어주세요"):
            yt.build_body(빈값)


def test_유튜브가_받는_길이로_잘라낸다():
    body = yt.build_body("가" * 300, "나" * 9000)
    assert len(body["snippet"]["title"]) == yt.TITLE_MAX
    assert len(body["snippet"]["description"]) == yt.DESC_MAX


def test_태그는_전체_길이가_넘치기_전에_끊는다():
    """유튜브는 태그 낱개가 아니라 전체 길이로 막는다. 넘으면 통째로 거절당한다."""
    body = yt.build_body("제목", tags=["가" * 100] * 20)
    assert sum(len(t) + 1 for t in body["snippet"]["tags"]) <= yt.TAGS_MAX


def test_빈_태그는_걸러낸다():
    assert yt.build_body("제목", tags=["한국사", "  ", "", "독립군"])["snippet"]["tags"] == [
        "한국사",
        "독립군",
    ]


def test_한국어_영상이라고_알려준다():
    """이걸 안 하면 유튜브가 엉뚱한 자막을 자동으로 붙인다."""
    snippet = yt.build_body("제목")["snippet"]
    assert snippet["defaultLanguage"] == "ko"
    assert snippet["defaultAudioLanguage"] == "ko"


def test_모르는_분류는_교육으로_돌린다():
    assert yt.build_body("제목", category="9999")["snippet"]["categoryId"] == "27"


# ------------------------------------------------------------ 파일 보기

def test_없는_파일은_바로_알려준다(tmp_path):
    with pytest.raises(yt.YoutubeUnavailable, match="찾을 수 없습니다"):
        yt.check_video(tmp_path / "없다.mp4")


def test_빈_파일은_막는다(tmp_path):
    비었다 = tmp_path / "비었다.mp4"
    비었다.write_bytes(b"")
    with pytest.raises(yt.YoutubeUnavailable, match="비어 있습니다"):
        yt.check_video(비었다)


def test_폴더를_넣으면_막는다(tmp_path):
    with pytest.raises(yt.YoutubeUnavailable, match="찾을 수 없습니다"):
        yt.check_video(tmp_path)


# ------------------------------------------------------------ 열쇠 파일

def test_열쇠_파일을_받아서_잠가둔다(temp_data):
    import os
    import stat

    열쇠 = json.dumps(
        {"installed": {"client_id": "1234567890-abcdefg.apps.googleusercontent.com"}}
    ).encode()

    결과 = yt.save_client_secret(열쇠)
    # 끝은 열쇠마다 똑같아서 보여줘도 구분이 안 된다. 앞의 숫자가 다르다.
    assert 결과["client_id_head"] == "1234567890"
    assert yt.CLIENT_FILE.exists()

    if os.name != "nt":
        assert stat.S_IMODE(yt.CLIENT_FILE.stat().st_mode) == 0o600


def test_web_종류_열쇠도_받는다(temp_data):
    열쇠 = json.dumps({"web": {"client_id": "abc.apps.googleusercontent.com"}}).encode()
    assert yt.save_client_secret(열쇠)


@pytest.mark.parametrize(
    "나쁜파일",
    [
        "이건 JSON 이 아닙니다".encode(),
        b"{}",
        b'{"installed": {}}',
        '{"뭔가": "다른것"}'.encode(),
        b"\xff\xfe",
    ],
)
def test_엉뚱한_파일은_이유를_알려준다(temp_data, 나쁜파일):
    with pytest.raises(yt.YoutubeUnavailable):
        yt.save_client_secret(나쁜파일)


# ------------------------------------------------------------ 준비 상태

def test_열쇠가_없으면_그것부터_하라고_한다(temp_data):
    상태 = yt.status()
    assert 상태["has_client"] is False
    assert 상태["logged_in"] is False
    assert "열쇠 파일을 먼저" in 상태["note"]


def test_열쇠만_있으면_로그인하라고_한다(temp_data):
    yt.save_client_secret(
        json.dumps({"installed": {"client_id": "abc.apps.googleusercontent.com"}}).encode()
    )
    상태 = yt.status()
    assert 상태["has_client"] is True
    assert 상태["logged_in"] is False
    assert "로그인만" in 상태["note"]


def test_열쇠_없이_로그인하려_하면_막는다(temp_data):
    with pytest.raises(yt.YoutubeUnavailable, match="열쇠 파일을 넣어주세요"):
        yt.login()


def test_로그인_안_됐는데_채널을_물으면_그렇게_말한다(temp_data):
    with pytest.raises(yt.YoutubeUnavailable, match="로그인되어 있지 않습니다"):
        yt.channel()


def test_로그아웃하면_출입증만_지우고_열쇠는_남긴다(temp_data):
    yt.save_client_secret(
        json.dumps({"installed": {"client_id": "abc.apps.googleusercontent.com"}}).encode()
    )
    yt.TOKEN_FILE.write_text("{}", encoding="utf-8")

    yt.forget()
    assert not yt.TOKEN_FILE.exists()
    assert yt.CLIENT_FILE.exists()  # 열쇠까지 지우면 또 받으러 가야 한다


def test_망가진_출입증이어도_안_터진다(temp_data):
    yt.TOKEN_FILE.write_text("{망가짐", encoding="utf-8")
    assert yt._credentials() is None


# ------------------------------------------------- 오류를 사람 말로 바꾸기

class 가짜오류(Exception):
    def __init__(self, status, reason=""):
        self.resp = type("응답", (), {"status": status})()
        self.content = json.dumps(
            {"error": {"errors": [{"reason": reason}]}}
        ).encode()


@pytest.mark.parametrize(
    "코드, 사유, 나올말",
    [
        (403, "quotaExceeded", "몫을 다 썼습니다"),
        (403, "uploadLimitExceeded", "지금 올릴 수 없습니다"),
        (403, "forbidden", "YouTube Data API v3"),
        (401, "", "다시 로그인"),
        (500, "", "잠시 말썽"),
        (503, "", "잠시 말썽"),
    ],
)
def test_구글_오류를_사람_말로_바꾼다(코드, 사유, 나올말):
    assert 나올말 in yt._읽을수있게(가짜오류(코드, 사유))


def test_내용을_못_읽는_오류여도_안_터진다():
    class 읽을수없음(Exception):
        resp = type("응답", (), {"status": 400})()
        content = b"\xff\xfe"

    assert "유튜브가 오류를" in yt._읽을수있게(읽을수없음())
