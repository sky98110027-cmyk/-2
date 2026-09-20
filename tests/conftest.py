import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def temp_data(monkeypatch):
    """테스트가 진짜 data/ 폴더를 건드리지 않게 격리한다."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        from gyeol import config, store

        monkeypatch.setattr(config, "DATA_DIR", root)
        monkeypatch.setattr(config, "SKILLS_DIR", root / "skills")
        monkeypatch.setattr(config, "PROJECTS_DIR", root / "projects")
        monkeypatch.setattr(config, "CLAUDE_SKILLS_DIR", root / "claude-skills")
        monkeypatch.setattr(store, "SKILLS_DIR", root / "skills")
        monkeypatch.setattr(store, "PROJECTS_DIR", root / "projects")
        monkeypatch.setattr(store, "CLAUDE_SKILLS_DIR", root / "claude-skills")

        def ensure():
            for d in (root, root / "skills", root / "projects"):
                d.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(store, "ensure_dirs", ensure)
        ensure()
        yield root


@pytest.fixture
def dna():
    return {
        "title": "담담한 증언체",
        "one_line": "끝까지 담담하다가 마지막 한 줄에서 터진다",
        "audience": "40~60대 시니어",
        "voice": {
            "person": "1인칭 회고",
            "tone": "담담하나 밑에 불이 있다",
            "speech_level": "다까체",
            "sentence_rule": "평균 14자, 단문 위주",
            "signature_phrases": ["그날", "그러나"],
        },
        "structure": {
            "hook": "질문 하나를 던지고 멈춘다",
            "beats": [{"name": "기", "share": "20%", "does": "상황을 깐다"}],
            "ending": "이름을 세 번 부른다",
        },
        "emotion": {
            "curve": "평탄하다 끝에 급상승",
            "peak": "마지막 30초",
            "devices": ["침묵", "반복"],
        },
        "visual": {
            "mood": "faded sepia, grainy archival",
            "shot_rules": ["정지 사진 위주"],
            "caption_rule": "화면 아래 한 줄",
        },
        "narration": {"pace": "느리게", "pause_rule": "문장마다 쉼", "bgm": "낮은 현악"},
        "title_pattern": ["인물명 + 한 줄"],
        "forbidden": ["자극적 과장"],
        "checklist": ["다까체 유지", "첫 15초에 질문"],
    }


@pytest.fixture
def script():
    return {
        "topic": "홍범도",
        "title_candidates": ["봉오동의 그날"],
        "thumbnail_copy": ["그는 왜 돌아왔나"],
        "hook": "그는 왜 돌아왔을까요.",
        "total_seconds": 300,
        "scenes": [
            {
                "no": 1,
                "beat": "기",
                "seconds": 12,
                "narration": "그해 겨울은 유난히 추웠습니다.",
                "caption": "1920년 겨울",
                "image_prompt": "A worn photograph of a winter valley",
                "video_prompt": "slow push in",
                "bgm": "낮은 현악",
            }
        ],
        "closing": "우리는 그 이름을 기억합니다.",
        "description": "봉오동 전투 이야기입니다.",
        "tags": ["한국사", "독립군"],
        "self_check": ["다까체 유지함"],
    }
