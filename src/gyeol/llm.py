"""클로드 API를 부르는 자리.

구조화 출력을 강제해서 JSON이 항상 같은 모양으로 오게 한다.
긴 대본은 스트리밍으로 받아야 타임아웃에 안 걸린다.
"""

from __future__ import annotations

import json
import os
from typing import Any

from .config import MODEL


class LLMUnavailable(Exception):
    """API 키가 없거나 호출이 실패했을 때. 메시지는 그대로 화면에 뜬다."""


def _client():
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - 설치 안내용
        raise LLMUnavailable(
            "anthropic 패키지가 없습니다. pip install anthropic 을 실행해주세요."
        ) from exc

    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise LLMUnavailable(
            "클로드 API 키가 없습니다.\n"
            "앱을 끄셨다가 시작 파일(start.command 또는 start.bat)을 다시 눌러주세요.\n"
            "그때 키를 한 번만 물어봅니다."
        )
    return anthropic.Anthropic()


def _to_error(exc: Exception) -> LLMUnavailable:
    """SDK 예외를 사람이 읽을 수 있는 말로 바꾼다."""
    import anthropic

    if isinstance(exc, anthropic.AuthenticationError):
        return LLMUnavailable("API 키가 틀렸습니다. 키를 다시 확인해주세요.")
    if isinstance(exc, anthropic.RateLimitError):
        return LLMUnavailable("요청이 몰렸습니다. 1분쯤 뒤에 다시 눌러주세요.")
    if isinstance(exc, anthropic.APIConnectionError):
        return LLMUnavailable("클로드에 연결이 안 됩니다. 인터넷 상태를 확인해주세요.")
    if isinstance(exc, anthropic.APIStatusError):
        return LLMUnavailable(f"클로드가 오류를 돌려줬습니다 ({exc.status_code}). {exc.message}")
    return LLMUnavailable(f"알 수 없는 오류입니다. {exc}")


def structured(
    *,
    system: str,
    user: str,
    schema: dict[str, Any],
    max_tokens: int = 32000,
    effort: str = "high",
) -> dict[str, Any]:
    """스키마에 맞는 JSON 하나를 받아온다.

    길게 나올 수 있으니 항상 스트리밍으로 받는다.
    """
    client = _client()
    import anthropic

    try:
        with client.messages.stream(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            thinking={"type": "adaptive"},
            output_config={
                "effort": effort,
                "format": {"type": "json_schema", "schema": schema},
            },
        ) as stream:
            message = stream.get_final_message()
    except anthropic.APIError as exc:
        raise _to_error(exc) from exc
    except Exception as exc:  # 네트워크 계층에서 터지는 것까지
        raise _to_error(exc) from exc

    if message.stop_reason == "refusal":
        raise LLMUnavailable("클로드가 이 요청은 처리하지 않겠다고 답했습니다. 내용을 바꿔서 다시 해주세요.")

    text = next((b.text for b in message.content if b.type == "text"), "")
    if not text.strip():
        raise LLMUnavailable("클로드가 빈 응답을 보냈습니다. 다시 한 번 눌러주세요.")

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMUnavailable("받은 응답이 깨졌습니다. 다시 한 번 눌러주세요.") from exc


def api_key_present() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
