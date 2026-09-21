# 나레이션 — MCP 음성 도구

VOICEVOX는 일본어 전용이라 여기서는 쓰지 않는다. 영어는 MCP 음성 도구로 합성한다.

## 보이스 선택

기본값은 **seed_audio의 남성 해설 보이스**. 낮고 담백한 톤을 고른다.
사용자가 그대로 가겠다고 하면 더 묻지 않는다.

후보는 `list_voices`로 받아 **2~3개만** 제시한다. 전체 목록을 늘어놓지 않는다.
고를 때 보는 것은 세 가지다.

| 기준 | 맞는 값 |
| --- | --- |
| 성별·연령 | 남성, 중년. 구조물 해설에 무게가 실린다 |
| 악센트 | 미국 영어. 영국 악센트는 다큐 느낌이 강해 쇼츠에서 느리게 읽힌다 |
| 스타일 | narration / documentary 계열. conversational은 상투어 톤이 배어 나온다 |

`list_voices`가 주는 `voice_id`와 `voice_type`(`preset` 또는 `element`) **짝을 그대로** 넘긴다.
`demoAudioUrl`·`preview_url`은 임시 서명 URL이다. 미리 듣기에만 쓰고 저장하거나 재사용하지 않는다.

**보이스를 바꾸면 길이가 통째로 바뀐다.** 반드시 재합성·재실측하고 컷 수도 다시 나눈다.

## 줄별 합성 — 통짜로 합성하지 않는다

자막 정렬의 근거가 줄별 시각이다. 통짜로 합성하면 그 시각을 알 수 없어
강제정렬 도구를 따로 붙여야 하고, 오차도 생긴다. 줄별로 합성하면 오차가 원리적으로 0이다.

대본 줄이 12줄 이하면 `generate_audio_batch`로 한 번에 넣는다.

```
generate_audio_batch(requests=[
  { index: 1, params: { model: "seed_audio", voice_type: "preset", voice_id: "<선택한 id>",
                        prompt: "That spire was not built to stop lightning." } },
  { index: 2, params: { model: "seed_audio", voice_type: "preset", voice_id: "<선택한 id>",
                        prompt: "It was built to dock airships." } }
])
```

- `index`는 **대본 줄 번호와 같게** 준다. 나중에 파일명 숫자가 이 번호다
- 12줄을 넘으면 나눠 제출하고 index를 이어서 매긴다
- 제출 후 `jobs_wait`로 전부 끝날 때까지 기다린 뒤 **한 번에** 결과를 받는다
- 한 줄만 다시 뽑을 때는 `generate_audio`를 쓴다

`speech_rate`를 건드리지 않는다. 길이를 대사에 맞추는 것이지 대사를 길이에 맞추는 게 아니다.

## 저장 규칙 — 여기서 어긋나면 전부 어긋난다

받은 오디오를 프로젝트의 `audio/`에 **숫자 접두사**로 저장한다.

```
audio/001_spire.wav
audio/002_airships.wav
audio/003_mooring.wav
```

`measure_timing.py`는 `^(\d+)_` 접두사 숫자로 순서를 잡는다. 사전순이 아니다.
접두사가 없는 파일은 아예 무시된다.

**WAV로 저장한다.** `measure_timing.py`는 파이썬 `wave` 모듈로 길이를 읽기 때문에
MP3나 M4A는 읽지 못한다. 엔진이 MP3로 주면 변환한다.

```
ffmpeg -i 001_spire.mp3 -ar 44100 -ac 1 001_spire.wav
```

0.5초 미만 파일은 무음으로 보고 버린다. 아주 짧은 대사가 있으면 이 필터에 걸리지 않는지 확인한다.

## 실측

```
uv run scripts/measure_timing.py projects/<슬러그>
uv run scripts/measure_timing.py projects/<슬러그> --audio-dir audio_alt
```

`timing.json`이 나온다. **유효 WAV 개수 ≠ 대본 줄 수면 여기서 멈춘다.**
그 경우 저장이 중간에 빠졌거나 접두사 번호가 어긋난 것이다.

### 대체 테이크 보관

보이스를 바꿔 여러 판을 뽑을 때는 폴더를 나눠 남긴다. 되돌릴 때 재합성이 필요 없다.

```
audio/              채택본
audio_male_low/     낮은 남성 백업
audio_neutral/      중립 톤 판
```

## 타임라인 계산

`measure_timing.py`가 계산하는 규칙은 일본판과 같다.

- 블록 안 줄 사이 `line_gap` 0.15초
- 블록 사이 `scene_gap` 0.35초
- 블록 길이 = 그 블록 첫 줄 시작부터 다음 블록 첫 줄 시작까지 (**블록끼리 맞닿게** 만든다)
- 전체 길이 = 마지막 줄 끝

블록을 맞닿게 두는 이유는 영상 세그먼트 사이에 빈틈이 생기지 않게 하려는 것이다.

영어는 일본어보다 같은 정보를 짧게 말한다. 같은 내용이라도 일본판보다 총 길이가 짧게 나오는 게 정상이다.
짧다고 문장을 늘리지 않는다.

## 합성 후 확인

`check_reading.py`는 사전 기준 점검일 뿐이다. **최종 확인은 귀로 듣는 것.**

특히 이 세 가지는 파일을 열어 직접 듣는다.

- 숫자를 풀어 쓴 줄 — `seven hundred twenty six feet`가 뭉개지지 않는지
- 약어를 철자로 푼 줄 — `T M D`가 단어처럼 붙어 읽히지 않는지
- 동형이의어가 있는 줄 — `lead`, `wind`, `minute`, `live`, `close`
