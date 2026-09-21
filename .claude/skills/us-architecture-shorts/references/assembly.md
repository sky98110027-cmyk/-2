# 자막과 조립

## 자막 — subs.ass

```
uv run scripts/build_ass.py projects/<슬러그>
```

`script.json`의 `sub`과 `timing.json`의 줄별 시각으로 ASS 자막을 만든다.

**줄 단위로 합성했기 때문에 타이밍 오차가 원리적으로 0이다.** Whisper 강제정렬이 필요 없다.
통짜로 합성한 뒤 되맞추는 방식과 달리 추가 도구도 GPU도 안 든다.

설정값

| 항목 | 값 | 이유 |
| --- | --- | --- |
| FONT | Arial | 어디서나 있는 폰트. Inter / Noto Sans로 교체 가능 |
| FONT_SIZE | 64 | 1080폭 − 좌우 마진 140 = 940px |
| MAX_CHARS | 28 | 영문 64px Bold가 940px에 들어가는 상한. 일본어 전각 14자와 같은 폭 |
| MARGIN_H | 70 | |
| MARGIN_V | 600 | Shorts UI(하단 버튼·설명)를 피한다 |
| Default 스타일 | 흰색 | |
| Key 스타일 | 노란색 | `script.json`에서 `style: "key"`인 줄 |

### 영어 줄바꿈이 일본어와 다른 점

일본어는 아무 글자 사이에서나 끊을 수 있어 문절 경계를 추정하는 문제였다.
영어는 **공백에서만** 끊을 수 있어 문제가 반대다. 끊을 자리가 드물어 줄 길이가 들쭉날쭉해진다.

`build_ass.py`는 DP로 전체 줄의 길이 편차를 최소화하면서, 관사·전치사로 줄이 끝나는
자리에 벌점을 준다. 눈이 다음 줄로 끌려가는 걸 막기 위한 것이다.

```
The mast held a mooring arm, a winch, and a gangplank.

  나쁨                        좋음
  The mast held a mooring     The mast held a mooring arm,
  arm, a winch, and a         a winch, and a gangplank.
  gangplank.
```

자동 결과가 마음에 안 들면 `sub` 필드에 `\N`을 넣는다. **수동 지정이 항상 우선한다.**

한 단어가 화면 폭보다 길면 손대지 않고 그대로 둔다. 건축 용어에 간혹 있다.
그 경우 대본에서 단어를 바꾸는 게 맞다.

## 조립 — final.mp4

```
uv run scripts/assemble.py projects/<슬러그>
uv run scripts/assemble.py projects/<슬러그> --no-subs
uv run scripts/assemble.py projects/<슬러그> --out out/v2.mp4
```

하는 일

1. `clips/scene_XX.*`를 블록 길이에 맞춰 1080×1920으로 정규화한다
   (`scale=increase` → `crop` 이므로 비율이 달라도 화면을 꽉 채운다)
2. 클립이 블록보다 짧으면 반복해 채운다
3. 이어붙이고 `audio/narration.wav`를 얹는다
4. `subs.ass`가 있으면 굽는다
5. 라우드니스를 `-14 LUFS`로 맞춘다 (YouTube 기준)

**클립이 없는 블록은 단색(`#0E1116`)으로 채우고 계속 진행한다.**
비주얼을 다 모으기 전에도 전체 흐름을 확인할 수 있어야 반복이 빠르다.
나중에 `clips/`에 파일만 채우고 다시 돌리면 그 블록만 채워진다.

`narration.wav`는 줄별 WAV를 `timing.json` 순서대로 이어붙인 것이다.
MCP로 받은 오디오를 `audio/`에 저장한 뒤 만든다.

```
ffmpeg -f concat -safe 0 -i list.txt -c copy audio/narration.wav
```

나레이션은 블록 시작에서 0.1~0.5초 뒤에 얹어 첫 음절이 잘리지 않게 한다.
`pre_silence` 기본값 0.05와 `line_gap` 0.15가 이 역할을 한다.

## ffmpeg 찾기

`assemble.py`는 PATH를 먼저 보고, 없으면 아래를 뒤진다. PATH 등록이 막힌 환경을 위한 것이다.

```
~/Videos/클로드/tools
~/.local/tools
C:/Program Files/ffmpeg
C:/ffmpeg
```

없으면 zip을 받아 풀기만 하면 된다.
`https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip`

## 최종 점검

조립 전에 확인한다.

- 블록 경계가 서로 맞닿는가 (`scenes[i].end == scenes[i+1].start`)
- 마지막 블록 `end`가 `total_duration`과 같은가
- 모든 줄이 자기 블록 범위 안에 있는가
- 자막 각 줄이 영문 28자 이하인가
- 컷 시각이 블록 시작·끝과 맞고 컷 사이에 빈틈이 없는가
- 앵글 문자열에 인접 중복이 없는가
- 유효 WAV 개수 == 대본 줄 수
- `script.json`의 `myth` / `reversal` / `sources`가 비어 있지 않은가

`total_duration`이 60초를 넘으면 쇼츠 규격을 벗어난다. 대본을 줄인다 (속도를 올리지 말 것).
15초 미만이면 노출이 잘 안 붙는다는 경고가 뜨지만, 대본이 짧으면 그대로 짧게 간다.

영어는 같은 내용을 일본어보다 짧게 말한다. 일본판 기준으로 컷 수를 잡아 두면 남는다.
**실측 뒤에 컷을 다시 나눈다.**

## 업로드 전 마지막 하나

유튜브 스튜디오에서 **'변경되거나 합성된 콘텐츠' 공개 토글**을 켠다.
미공개가 걸리면 경고 → 90일 수익 정지 → 영구 퇴출 순서로 간다.
이 스킬로 만든 영상은 전부 여기에 해당한다.
