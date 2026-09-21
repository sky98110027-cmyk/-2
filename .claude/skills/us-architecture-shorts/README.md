# us-architecture-shorts

영어권 송출용 건축·구조물 원리 해설 쇼츠를 만드는 스킬.
`japan-architecture-shorts`의 영어판이다.

## 일본판과 뭐가 다른가

| | 일본판 | 영어판 |
| --- | --- | --- |
| 음성 엔진 | VOICEVOX (로컬 앱) | MCP `generate_audio` (seed_audio) |
| 통념 기준 | 일본 대중 | 영어권 대중 |
| 자막 한 줄 | 전각 14자 | 영문 28자 |
| 줄바꿈 방식 | 문절 경계 추정 | 단어 경계 DP |
| 오독 위험 | 한자 읽기 | 숫자·약어·동형이의어 |

룩(스타일 포뮬러·앵글 팔레트·네거티브)은 **일부러 똑같이 두었다.** 채널이 갈려도 화면은 한 집안이어야 한다.
`S0` 스타일 키 이미지는 일본판 것을 그대로 재사용해도 된다.

## 파일

```
SKILL.md                     작업 순서와 절대 규칙
references/voice.md          MCP 음성 합성·저장·실측
references/script-writing.md 영어 대본 규칙, script.json 스키마
references/visuals.md        스타일 포뮬러·앵글·TopView 호출
references/assembly.md       자막·조립·최종 점검
scripts/measure_timing.py    줄별 WAV 실측 → timing.json   (일본판과 동일)
scripts/check_reading.py     영어 오독·자막 길이 점검      (신규)
scripts/build_ass.py         영어 단어 경계 줄바꿈 자막     (새로 작성)
scripts/assemble.py          ffmpeg 조립                   (일본판과 동일)
```

`measure_timing.py`는 엔진을 가리지 않는다. 줄별 WAV 길이만 읽기 때문에
VOICEVOX든 MCP든 그대로 쓸 수 있다. 그래서 일본판에서 그대로 가져왔다.

## 빠른 확인

스크립트만 따로 돌려 볼 때.

```
uv run scripts/check_reading.py projects/<슬러그>
uv run scripts/measure_timing.py projects/<슬러그>
uv run scripts/build_ass.py projects/<슬러그>
uv run scripts/assemble.py projects/<슬러그>
```

`uv`가 없으면 `python3`로 돌려도 된다. 외부 의존성이 없다.

## 반드시 지킬 것

1. 통념은 **영어권에서 실제로 도는지 웹 검색으로 확인한 뒤** 쓴다. 번역으로 때우면 훅이 죽는다
2. 근거 URL을 `script.json`의 `sources`에 남긴다. 유튜브 비진정성 콘텐츠 정책에 대한 방어선이다
3. 업로드할 때 '변경되거나 합성된 콘텐츠' 공개 토글을 켠다
4. 쇼츠는 유입 장치다. 수익은 같은 대본으로 만든 롱폼에서 나온다
