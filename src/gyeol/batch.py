"""여러 편을 한꺼번에 돌린다.

한 편씩 기다리면 세 편에 6분이 걸린다.
같이 돌리면 2분이면 끝난다. 기다리는 일이라 같이 돌려도 된다.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

# 너무 많이 동시에 던지면 API 쪽에서 막는다
MAX_AT_ONCE = 5
MAX_TOPICS = 12


def run_many(
    topics: list[str],
    work: Callable[[str], dict[str, Any]],
) -> list[dict[str, Any]]:
    """주제마다 같은 일을 시키고, 하나가 엎어져도 나머지는 살린다."""
    topics = [t.strip() for t in topics if str(t).strip()][:MAX_TOPICS]
    if not topics:
        return []

    def 하나(topic: str) -> dict[str, Any]:
        try:
            return {"topic": topic, "ok": True, "result": work(topic)}
        except Exception as exc:
            return {"topic": topic, "ok": False, "error": str(exc)}

    with ThreadPoolExecutor(max_workers=min(len(topics), MAX_AT_ONCE)) as pool:
        return list(pool.map(하나, topics))


def summarize(results: list[dict[str, Any]]) -> str:
    """끝나고 한 줄로 보고한다."""
    done = [r for r in results if r["ok"]]
    failed = [r for r in results if not r["ok"]]

    if not failed:
        return f"{len(done)}편 다 나왔습니다."
    if not done:
        return f"{len(failed)}편 다 막혔습니다. {failed[0]['error']}"
    return (
        f"{len(done)}편 나왔습니다. "
        f"{len(failed)}편은 막혔습니다 — {', '.join(r['topic'] for r in failed)}"
    )
