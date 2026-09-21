"""폴더 고르는 창을 띄운다.

이 앱은 형님 컴퓨터에서 돈다.
그러니 브라우저 대신 운영체제의 폴더 창을 띄울 수 있다.
경로를 손으로 타이핑하게 두는 것보다 이쪽이 낫다.

창을 못 띄우는 환경도 있다. 그때는 손으로 적게 넘긴다.
"""

from __future__ import annotations


class PickerUnavailable(Exception):
    """폴더 창을 띄울 수 없을 때."""


def available() -> bool:
    try:
        import tkinter  # noqa: F401
        from tkinter import filedialog  # noqa: F401
    except Exception:
        return False
    return True


def ask_folder(start: str = "") -> str:
    """폴더 창을 띄우고 고른 경로를 돌려준다. 취소하면 빈 문자열."""
    try:
        import tkinter
        from tkinter import filedialog
    except Exception as exc:
        raise PickerUnavailable(
            "이 컴퓨터에서는 폴더 창을 띄울 수 없습니다. 경로를 직접 적어주세요."
        ) from exc

    try:
        root = tkinter.Tk()
        root.withdraw()
        root.attributes("-topmost", True)  # 브라우저 뒤로 숨지 않게
        picked = filedialog.askdirectory(
            title="결과물을 저장할 폴더를 고르세요", initialdir=start or None
        )
        root.destroy()
    except Exception as exc:
        raise PickerUnavailable(
            "폴더 창을 띄우다가 막혔습니다. 경로를 직접 적어주세요."
        ) from exc

    return picked or ""
