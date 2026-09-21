# 영어 대본 작성

## script.json 스키마

```json
{
  "title": "The Empire State spire was a dock, not a lightning rod",
  "topic": "Empire State Building / mooring mast",
  "language": "en",
  "aspect": "9:16",
  "myth": "영어권 대중이 믿고 있는 통념 한 줄",
  "reversal": "무엇을 어떤 근거로 뒤집는지 한 줄",
  "sources": ["https://...", "https://..."],
  "voice": {
    "provider": "mcp",
    "model": "seed_audio",
    "voice_type": "preset",
    "voice_id": "<list_voices에서 받은 id>",
    "label": "US male, documentary",
    "pre_silence": 0.05,
    "post_silence": 0.05
  },
  "timing": { "line_gap": 0.15, "scene_gap": 0.35 },
  "scenes": [
    {
      "id": 1,
      "arc": "hook",
      "lines": [
        {
          "sub": "That spire was not built\\Nto stop lightning.",
          "tts": "That spire was not built to stop lightning.",
          "style": "key"
        },
        {
          "sub": "It was built to dock airships.",
          "tts": "It was built to dock airships."
        }
      ]
    }
  ]
}
```

`arc`는 `hook` / `identity` / `principle` / `twist` 중 하나.
`style: "key"`를 붙인 줄은 자막이 강조색(노란색)으로 나온다. 훅 첫 줄과 마지막 반전 줄에만 붙인다.

## sub과 tts를 나누는 이유

일본어판과 목적이 다르다. 일본어는 한자 오독 때문에 갈랐지만, 영어는 **숫자와 약어** 때문에 가른다.

- **`sub`** — 화면에 뜨는 글자. 숫자와 단위를 그대로 쓴다. 눈으로 읽을 때는 `1,454 ft`가 빠르다
- **`tts`** — 엔진에 먹이는 글자. 숫자·단위·약어를 전부 영어 단어로 풀어 쓴다

```json
{
  "sub": "1,454 feet to the tip.",
  "tts": "One thousand four hundred fifty four feet to the tip."
}
```

푸는 이유는 두 가지다. 엔진마다 숫자 읽는 방식이 갈리고,
무엇보다 **풀어 쓰지 않으면 실측 길이가 흔들린다.**

## 오독 규칙

### 1. 숫자는 전부 단어로 (오독 1위)

```
1,454 ft  → one thousand four hundred fifty four feet
102       → one hundred two
50%       → fifty percent
1931      → nineteen thirty one
1930s     → the nineteen thirties
2/3       → two thirds
-40°      → minus forty degrees
```

연도는 자릿수로 읽지 않는다. `nineteen thirty one`이지 `one thousand nine hundred thirty one`이 아니다.

### 2. 약어는 철자 사이를 띄운다

붙여 쓰면 단어처럼 읽어버리는 엔진이 있다.

```
TMD  → T M D
RC   → R C
MPa  → megapascals
psi  → P S I
HVAC → H V A C
```

### 3. 동형이의어는 표시해 두고 귀로 확인한다

철자가 같고 발음이 갈리는 단어다. 엔진이 반반으로 틀린다.
바꿔 쓸 수 있으면 바꾸고, 못 바꾸면 합성 후 반드시 듣는다.

| 단어 | 갈리는 지점 | 피하는 법 |
| --- | --- | --- |
| lead | 금속 납 / 이끌다 | `lead sheeting` → `sheet lead` |
| wind | 바람 / 감다 | 문맥이 분명하면 둔다 |
| live | 살다 / 생중계 | `live load` → `imposed load` |
| minute | 분 / 미세한 | `minute gap` → `tiny gap` |
| close | 닫다 / 가까운 | `close fit` → `tight fit` |
| bow | 활 / 숙이다 | `bow` → `bend` |

`check_reading.py`가 이것들을 훑어 준다.

### 4. 점검

```
uv run scripts/check_reading.py projects/<슬러그>
```

- `tts`에 남은 숫자·기호·약어를 잡는다
- 동형이의어를 표시한다
- `sub`의 자막 줄이 상한을 넘는지 본다
- 단어 수로 길이를 어림 추정한다 (**대본 단계의 어림수일 뿐**, 실측이 진짜다)

**점검기를 믿지 말 것.** 최종 판단은 합성된 음성을 귀로 듣는 것이다.

## 자막 개행

한 줄 상한은 **영문 28자**. FONT_SIZE 64, 좌우 마진 70, 1080폭 기준이다.
일본어 전각 14자와 같은 폭이다. 영문자가 전각의 절반이라서 숫자만 두 배다.

`build_ass.py`가 단어 경계에서 알아서 끊고 줄 길이를 고르게 맞춘다.
관사·전치사로 줄이 끝나는 자리에는 벌점을 주므로 대개 읽기 좋게 나온다.

자동 결과가 마음에 안 들면 `sub` 필드에 `\N`으로 직접 끊는다. **수동 지정이 항상 우선한다.**

```
"sub": "The mast held a mooring arm,\\Na winch, and a gangplank."
```

2~3줄까지는 무리 없다. MARGIN_V 600이면 Shorts UI를 피한다.

## 블록 구성

```
블록 1 (훅)        통념을 짧게 제시하고 곧바로 부정한다
블록 2 (원리)      실제로는 어떻게 되어 있는지 구조·물리로 설명
블록 3 (반전)      첫 문장의 통념을 다시 뒤집으며 닫는다
```

원리 설명에 더 필요하면 블록을 하나 더 붙인다.

**블록당 두 문장까지.** 분량을 목표 길이에 맞춰 늘리지 않는다.

## 통념 고르기 — 이 채널의 급소

영어권에서 실제로 퍼져 있는 통념이어야 한다. **웹 검색으로 확인한 뒤 쓴다.**
한국이나 일본에서 도는 통념을 영어로 옮기면 훅이 죽는다. 시청자가 그 통념을 안 믿기 때문이다.

확인 방법은 간단하다. 그 통념을 영어로 검색해서
`Reddit`, `Quora`, `Snopes`, `HowStuffWorks`, 지역 신문의 '오해 바로잡기' 기사가 나오면
그 통념이 실제로 돌고 있다는 뜻이다. 아무것도 안 나오면 없는 통념이다.

쓸 수 없는 것: 외계인, 초고대문명, 검증되지 않은 음모론.
이건 훅이 아니라 채널을 죽이는 길이다.

## 완성 예시 — 엠파이어스테이트편

통념: "The spire on top of the Empire State Building is a lightning rod."
뒤집기: 그 첨탑은 비행선(dirigible)을 계류하려고 세운 **계류탑**이었다.
상층부 기류와 난기류 때문에 실제 계류는 사실상 실패했고, 나중에 방송 안테나 기부로 용도가 바뀌었다.

**출처는 대본을 쓸 때 웹 검색으로 확인해 `sources`에 남긴다.** 아래 예시는 구조만 보여준다.

```
블록 1  That spire was not built to stop lightning.
        It was built to dock airships.

블록 2  The top floors held a mooring arm and a winch.
        An airship would tie its nose to the mast and hang in the wind.

블록 3  Updrafts off the tower made the tail swing.
        No airship ever moored there for long.

블록 4  The mast carried antennas instead.
        A dock that never worked became the reason the building still stands above the skyline.
```

마지막 줄이 첫 줄의 훅을 다시 뒤집는 구조에 주목한다.
"번개를 막으려고 세운 게 아니다"로 열고, "그런데 결국 꼭대기에 장비가 올라갔다"로 닫는다.

## 톤 체크리스트

대본을 넘기기 전에 훑는다.

- [ ] 첫 문장이 한 줄로 끝나는가
- [ ] 한 문장에 정보가 하나인가
- [ ] `Hey guys`, `Did you know`, `Amazing`, 느낌표가 없는가
- [ ] 관계대명사로 늘어진 문장이 없는가
- [ ] 마지막 문장이 첫 문장을 되받는가
- [ ] 통념과 뒤집기가 `myth` / `reversal`에 한 줄씩 적혀 있는가
- [ ] `sources`에 실제로 확인한 URL이 들어 있는가
