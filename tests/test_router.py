"""접수창구. 말을 어느 일로 보내는지."""

import pytest

from gyeol import batch, router


def test_이름_조각으로_결을_찾는다():
    결들 = [
        {"slug": "gyeol-b", "name": "담담한 증언체"},
        {"slug": "gyeol-a", "name": "뜨거운 웅변체"},
    ]
    assert router.pick_skill("증언", 결들)["slug"] == "gyeol-b"
    assert router.pick_skill("웅변", 결들)["slug"] == "gyeol-a"
    assert router.pick_skill("gyeol-a", 결들)["slug"] == "gyeol-a"


def test_못_찾으면_가장_최근_것을_쓴다():
    결들 = [{"slug": "gyeol-b", "name": "담담한 증언체"}]
    assert router.pick_skill("없는이름", 결들)["slug"] == "gyeol-b"
    assert router.pick_skill("", 결들)["slug"] == "gyeol-b"


def test_저장된_결이_없으면_고르지_않는다():
    assert router.pick_skill("아무거나", []) is None


def test_빈_말은_되묻는다():
    with pytest.raises(ValueError, match="무엇을 할지"):
        router.route("   ")


def test_모델이_주소를_흘려도_원문에서_주워온다(monkeypatch):
    monkeypatch.setattr(
        router,
        "structured",
        lambda **kw: {"action": "analyze", "url": "", "reply": "뽑겠습니다"},
    )
    결과 = router.route("https://youtu.be/abc123 이거 결 뽑아줘")
    assert 결과["url"] == "https://youtu.be/abc123"


def test_고치기는_원문을_그대로_넘긴다(monkeypatch):
    monkeypatch.setattr(
        router,
        "structured",
        lambda **kw: {"action": "revise", "instruction": "", "reply": ""},
    )
    말 = "자막 더 크게 하고 노란색으로 바꿔줘"
    assert router.route(말)["instruction"] == 말


# ------------------------------------------------------------- 한 번에 여러 편

def test_여러_편을_같이_돌린다():
    결과 = batch.run_many(["가", "나", "다"], lambda t: {"대본": t})
    assert [r["topic"] for r in 결과] == ["가", "나", "다"]
    assert all(r["ok"] for r in 결과)


def test_하나가_엎어져도_나머지는_산다():
    def 일(t):
        if t == "나":
            raise RuntimeError("여기서 막혔습니다")
        return {"대본": t}

    결과 = batch.run_many(["가", "나", "다"], 일)
    assert [r["ok"] for r in 결과] == [True, False, True]
    assert 결과[1]["error"] == "여기서 막혔습니다"


def test_너무_많이_시키면_잘라낸다():
    많이 = [f"주제{i}" for i in range(50)]
    assert len(batch.run_many(많이, lambda t: {})) == batch.MAX_TOPICS


def test_빈칸은_걸러낸다():
    assert len(batch.run_many(["가", "  ", "", "나"], lambda t: {})) == 2


def test_보고는_사람_말로_나온다():
    다됨 = [{"topic": "가", "ok": True, "result": {}}]
    assert batch.summarize(다됨) == "1편 다 나왔습니다."

    반반 = 다됨 + [{"topic": "나", "ok": False, "error": "막힘"}]
    assert "1편 나왔습니다" in batch.summarize(반반)
    assert "나" in batch.summarize(반반)

    다막힘 = [{"topic": "가", "ok": False, "error": "키가 없습니다"}]
    assert "키가 없습니다" in batch.summarize(다막힘)
