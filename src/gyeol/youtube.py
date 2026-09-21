"""유튜브에 올리기.

올리는 일은 되돌리기 어렵다.
한 번 올라가면 링크가 퍼지고, 지워도 누가 이미 봤을 수 있다.
그래서 이 파일은 두 가지를 반드시 지킨다.

  1. 기본은 항상 비공개다. 공개는 형님이 직접 골라야만 된다.
  2. 확인 없이는 한 글자도 안 올라간다.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

from .config import ROOT

CLIENT_FILE = ROOT / ".youtube-client.json"
TOKEN_FILE = ROOT / ".youtube-token.json"

# 올리기와, 어느 채널인지 확인하기. 딱 이 둘만 받는다.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

공개범위 = {
    "private": "비공개 (나만 봄)",
    "unlisted": "일부 공개 (링크 아는 사람만)",
    "public": "공개 (누구나 봄)",
}

분류 = {
    "27": "교육",
    "22": "인물·블로그",
    "24": "엔터테인먼트",
    "25": "뉴스·정치",
    "26": "노하우·스타일",
}

TITLE_MAX = 100
DESC_MAX = 5000
TAGS_MAX = 450  # 유튜브는 태그 전체 길이를 500자로 막는다. 여유를 둔다.
VIDEO_MAX_GB = 128


class YoutubeUnavailable(Exception):
    """유튜브 쪽이 준비가 안 됐을 때. 메시지는 그대로 화면에 뜬다."""


class NotConfirmed(Exception):
    """확인을 안 받았을 때. 이건 막아야 한다."""


# ------------------------------------------------------------- 열쇠 파일

def save_client_secret(data: bytes) -> dict[str, Any]:
    """구글 클라우드에서 받은 열쇠 파일을 넣는다."""
    try:
        parsed = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise YoutubeUnavailable(
            "이 파일은 구글에서 받은 열쇠 파일이 아닌 것 같습니다.\n"
            "구글 클라우드 콘솔에서 받은 JSON 파일을 넣어주세요."
        ) from exc

    속 = parsed.get("installed") or parsed.get("web")
    if not isinstance(속, dict) or not 속.get("client_id"):
        raise YoutubeUnavailable(
            "열쇠 파일 안에 필요한 내용이 없습니다.\n"
            "'데스크톱 앱' 종류로 만든 OAuth 클라이언트 ID 파일이어야 합니다."
        )

    CLIENT_FILE.write_text(
        json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if os.name != "nt":
        CLIENT_FILE.chmod(0o600)

    # 구글 client ID 는 끝이 다 '.apps.googleusercontent.com' 이라 뒤를 보여줘야 소용없다.
    # 앞의 숫자 부분이 열쇠마다 다르다. 그걸 보여준다.
    client_id = str(속["client_id"])
    return {"client_id_head": client_id.split("-")[0][:20]}


def forget() -> None:
    """로그아웃. 받아둔 출입증을 지운다. 열쇠 파일은 남긴다."""
    TOKEN_FILE.unlink(missing_ok=True)


def _credentials():
    """저장해둔 출입증을 꺼낸다. 시간이 지났으면 조용히 새로 받는다."""
    if not TOKEN_FILE.exists():
        return None

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    except Exception:
        return None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds)
        except Exception:
            # 출입증이 만료됐다. 다시 로그인해야 한다.
            return None

    return creds if creds and creds.valid else None


def _save_token(creds) -> None:
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    if os.name != "nt":
        TOKEN_FILE.chmod(0o600)


def login() -> dict[str, Any]:
    """브라우저를 띄워 구글 로그인을 받는다.

    이 앱은 형님 컴퓨터에서 돈다. 그래서 브라우저를 직접 띄울 수 있다.
    """
    if not CLIENT_FILE.exists():
        raise YoutubeUnavailable(
            "먼저 구글에서 받은 열쇠 파일을 넣어주세요.\n"
            "연결 탭의 유튜브 칸에서 넣으실 수 있습니다."
        )

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise YoutubeUnavailable(
            "구글 라이브러리가 없습니다. 시작 파일을 다시 눌러 준비를 마쳐주세요."
        ) from exc

    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_FILE), SCOPES)
        creds = flow.run_local_server(
            port=0,
            prompt="consent",  # 새로고침 열쇠를 꼭 받아둔다
            authorization_prompt_message="브라우저에서 구글 로그인을 해주세요.",
            success_message="로그인됐습니다. 이 창을 닫고 앱으로 돌아가세요.",
            open_browser=True,
        )
    except Exception as exc:
        raise YoutubeUnavailable(f"로그인하다가 막혔습니다.\n{exc}") from exc

    _save_token(creds)
    return channel()


def _service():
    creds = _credentials()
    if creds is None:
        raise YoutubeUnavailable("유튜브에 로그인되어 있지 않습니다. 먼저 로그인해주세요.")

    from googleapiclient.discovery import build

    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def channel() -> dict[str, Any]:
    """어느 채널에 올리게 되는지 확인한다.

    엉뚱한 채널에 올리는 일이 없어야 한다. 올리기 전에 반드시 보여준다.
    """
    from googleapiclient.errors import HttpError

    try:
        got = (
            _service()
            .channels()
            .list(part="snippet,statistics", mine=True)
            .execute()
        )
    except HttpError as exc:
        raise YoutubeUnavailable(_읽을수있게(exc)) from exc

    items = got.get("items") or []
    if not items:
        raise YoutubeUnavailable(
            "이 계정에 연결된 유튜브 채널이 없습니다. 채널을 먼저 만들어주세요."
        )

    it = items[0]
    snippet = it.get("snippet") or {}
    stats = it.get("statistics") or {}
    return {
        "id": it.get("id", ""),
        "name": snippet.get("title", ""),
        "thumbnail": ((snippet.get("thumbnails") or {}).get("default") or {}).get("url", ""),
        "videos": int(stats.get("videoCount") or 0),
        "subscribers": (
            int(stats.get("subscriberCount")) if stats.get("subscriberCount") else None
        ),
    }


def status() -> dict[str, Any]:
    """지금 유튜브가 어디까지 준비됐는지."""
    out = {
        "has_client": CLIENT_FILE.exists(),
        "logged_in": False,
        "channel": None,
        "note": "",
    }

    if not out["has_client"]:
        out["note"] = "구글에서 받은 열쇠 파일을 먼저 넣어주세요."
        return out

    if _credentials() is None:
        out["note"] = "열쇠 파일은 있습니다. 이제 로그인만 하시면 됩니다."
        return out

    out["logged_in"] = True
    try:
        out["channel"] = channel()
    except YoutubeUnavailable as exc:
        out["logged_in"] = False
        out["note"] = str(exc)
    return out


# --------------------------------------------------------------- 올리기

def check_video(path: str | Path) -> Path:
    """올릴 파일이 멀쩡한지 본다."""
    path = Path(path).expanduser()
    if not path.exists() or not path.is_file():
        raise YoutubeUnavailable(f"'{path}' 영상 파일을 찾을 수 없습니다.")

    기가 = path.stat().st_size / (1024**3)
    if 기가 > VIDEO_MAX_GB:
        raise YoutubeUnavailable(f"파일이 너무 큽니다 ({기가:.1f}GB). 유튜브는 {VIDEO_MAX_GB}GB 까지 받습니다.")
    if path.stat().st_size == 0:
        raise YoutubeUnavailable("영상 파일이 비어 있습니다.")
    return path


def build_body(
    title: str,
    description: str = "",
    tags: list[str] | None = None,
    privacy: str = "private",
    category: str = "27",
) -> dict[str, Any]:
    """유튜브에 보낼 내용을 만든다. 길이 제한을 여기서 다 걸러낸다."""
    title = " ".join(str(title or "").split())
    if not title:
        raise YoutubeUnavailable("제목을 적어주세요.")

    if privacy not in 공개범위:
        raise YoutubeUnavailable(f"'{privacy}' 는 쓸 수 없는 공개 범위입니다.")

    # 태그는 전체 길이로 막히니 넘치기 전에 잘라낸다
    담은태그: list[str] = []
    길이 = 0
    for tag in tags or []:
        tag = str(tag).strip()
        if not tag:
            continue
        더할길이 = len(tag) + 1
        if 길이 + 더할길이 > TAGS_MAX:
            break
        담은태그.append(tag)
        길이 += 더할길이

    return {
        "snippet": {
            "title": title[:TITLE_MAX],
            "description": str(description or "")[:DESC_MAX],
            "tags": 담은태그,
            "categoryId": str(category) if str(category) in 분류 else "27",
            "defaultLanguage": "ko",
            "defaultAudioLanguage": "ko",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }


def upload(
    video_path: str | Path,
    *,
    title: str,
    description: str = "",
    tags: list[str] | None = None,
    privacy: str = "private",
    category: str = "27",
    confirmed: bool = False,
    on_progress: Callable[[int], None] | None = None,
) -> dict[str, Any]:
    """영상 한 편을 올린다.

    confirmed 가 참이 아니면 아무것도 안 한다.
    실수로 남의 눈에 띄는 일은 없어야 한다.
    """
    if not confirmed:
        raise NotConfirmed("올리기 전에 확인을 눌러주세요.")

    path = check_video(video_path)
    body = build_body(title, description, tags, privacy, category)

    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    service = _service()
    media = MediaFileUpload(
        str(path), chunksize=8 * 1024 * 1024, resumable=True, mimetype="video/*"
    )

    try:
        request = service.videos().insert(
            part="snippet,status", body=body, media_body=media
        )
        response = None
        while response is None:
            진행, response = request.next_chunk()
            if 진행 and on_progress:
                on_progress(int(진행.progress() * 100))
    except HttpError as exc:
        raise YoutubeUnavailable(_읽을수있게(exc)) from exc

    video_id = response.get("id", "")
    return {
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
        "studio_url": f"https://studio.youtube.com/video/{video_id}/edit" if video_id else "",
        "privacy": privacy,
        "privacy_label": 공개범위[privacy],
        "title": body["snippet"]["title"],
    }


def set_thumbnail(video_id: str, image_path: str | Path) -> None:
    """썸네일을 올린다. 채널이 인증돼 있어야 받아준다."""
    path = Path(image_path).expanduser()
    if not path.exists():
        raise YoutubeUnavailable(f"'{path}' 썸네일 파일을 찾을 수 없습니다.")

    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    try:
        _service().thumbnails().set(
            videoId=video_id, media_body=MediaFileUpload(str(path))
        ).execute()
    except HttpError as exc:
        raise YoutubeUnavailable(
            "썸네일을 못 올렸습니다. 채널 전화번호 인증이 안 돼 있으면 막힙니다.\n"
            + _읽을수있게(exc)
        ) from exc


def _읽을수있게(exc) -> str:
    """구글이 돌려준 오류를 사람 말로 바꾼다."""
    코드 = getattr(getattr(exc, "resp", None), "status", 0)

    사유 = ""
    try:
        속 = json.loads(exc.content.decode("utf-8"))
        사유 = ((속.get("error") or {}).get("errors") or [{}])[0].get("reason", "")
    except Exception:
        pass

    if 사유 == "quotaExceeded":
        return (
            "오늘 올릴 수 있는 몫을 다 썼습니다.\n"
            "구글이 하루에 여섯 편쯤으로 막아둡니다. 내일 다시 해주세요."
        )
    if 사유 in ("uploadLimitExceeded", "youtubeSignupRequired"):
        return "이 채널로는 지금 올릴 수 없습니다. 유튜브에서 채널 상태를 확인해주세요."
    if 사유 == "forbidden" or 코드 == 403:
        return (
            "권한이 없다고 합니다.\n"
            "구글 클라우드에서 YouTube Data API v3 를 켰는지 확인해주세요."
        )
    if 코드 == 401:
        return "로그인이 풀렸습니다. 다시 로그인해주세요."
    if 코드 and 코드 >= 500:
        return "유튜브 쪽이 잠시 말썽입니다. 조금 뒤에 다시 해주세요."
    return f"유튜브가 오류를 돌려줬습니다. {exc}"
