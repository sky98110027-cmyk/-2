# 비주얼 — 스타일 포뮬러 · 앵글 · TopView

룩은 일본판과 같다. 채널이 둘로 갈려도 화면은 한 집안이어야 한다.
**바뀌는 것은 에셋 시트에 들어가는 구조물 종류뿐이다.**

## 스타일 포뮬러 (한 글자도 바꾸지 않는다)

모든 이미지·영상 프롬프트에 원문 그대로 붙여넣는다. 문구를 다듬는 순간 컷 사이 룩이 흔들린다.

```
photorealistic 3D architectural visualization, precise engineering geometry,
clean neutral gray studio backdrop, soft overcast global illumination,
thin bright orange (#FF6A00) measurement lines, arrows and annotation rings
overlaid on the structure, subtle depth of field, matte finish materials,
vertical 9:16 composition
```

## 네거티브 (고정)

```
people, figures, hands, crowds, text, letters, numbers, signage,
watermark, logo, ui overlay, cartoon, illustration, oversaturated colors
```

`people, figures, hands`는 절대 빼지 않는다. 하중을 표현할 때는 사람 대신 돌덩이나 화살표를 쓴다.
`text, letters, numbers`도 절대 빼지 않는다.

**영어라고 글자를 넣고 싶어지는 함정이 있다.** 생성 모델이 영어는 제법 그럴듯하게 쓰기 때문이다.
그래도 넣지 않는다. 철자가 한 글자씩 틀리고, 컷마다 다르게 나오고,
무엇보다 유튜브가 "템플릿으로 찍어낸 AI 콘텐츠"를 가려내는 신호가 된다.
정보는 주황색 선·화살표·링으로만 표현하고 말은 나레이션이 담당한다.

## 앵글 팔레트

| 코드 | 앵글 | 용도 |
| --- | --- | --- |
| A | 극단 앙각 (worm's eye) | 높이·스케일 압박 |
| B | 수직 컷어웨이 | 내부 부재 관계 |
| C | 하이앵글 부감 | 평면 배치·격자·편심 |
| D | 수평 근접 디테일 | 접합부·틈새·장치 |
| E | 아이소메트릭 전경 | 전체 구조 요약 |

**연속된 컷에 같은 앵글을 반복하지 않는다.** 스토리보드를 짠 뒤 앵글 문자열을 이어 붙여
인접 중복이 없는지 확인한다.

```
A B E D · E C A B D A · E B A · D C E A B E    ← 19컷, 인접 중복 없음
```

## 생성 순서 — 반드시 이 순서

컷을 텍스트만으로 생성하면 구조물 모양이 컷마다 달라진다. 앞 결과물을 뒤 단계의 레퍼런스로 넘긴다.

### 1. 스타일 키 (S0) — 1장

채널 룩 기준판. 이후 모든 컷의 레퍼런스로 넘긴다.
**일본판에서 이미 만든 S0이 있으면 그대로 재사용한다.** 채널 룩을 갈라 놓을 이유가 없다.

```
A single slender lattice steel tower and a smooth reinforced-concrete cylinder
standing side by side on a neutral gray studio floor, three-quarter isometric view,
full body in frame, thin orange measurement lines running vertically along both elements
```

### 2. 에셋 시트 (A0) — 1장

구조물 형태 고정용. S0을 레퍼런스로 생성한다. **여기는 주제마다 새로 만든다.**

엠파이어스테이트 계류탑편 예시:

```
Component study sheet of a setback skyscraper crown on neutral gray:
a stepped limestone-clad tower top, a riveted steel mooring mast with a conical
tip, a horizontal mooring arm with a winch drum, and a cutaway of the mast base
showing its steel frame, arranged as separated study objects
with thin orange callout lines
```

### 3. 컷 이미지 — 컷 수만큼

S0 + A0을 레퍼런스로 넘긴다. 컷 프롬프트는 영어로 쓴다.
프롬프트 = 스타일 포뮬러 + 컷 고유 서술. 컷 고유 서술에는 앵글, 무엇이 보이는지,
주황색 주석이 무엇을 가리키는지를 넣는다.

## prompts.json

컷별 프롬프트를 파일로 남긴다. TopView가 막혀도 사용자가 웹에서 직접 돌릴 수 있고,
재생성할 때 프롬프트가 흔들리지 않는다.

```json
{
  "voice": "seed_audio / US male documentary",
  "total_duration": 31.402,
  "style_formula": "...",
  "negative": "...",
  "aspect_ratio": "9:16",
  "style_key":  { "id": "S0", "purpose": "...", "prompt": "..." },
  "asset_sheet":{ "id": "A0", "purpose": "...", "prompt": "..." },
  "cuts": [
    { "id": "C1", "block": 1, "t": "0.000-1.786", "angle": "A", "prompt": "..." }
  ],
  "video_blocks": [
    { "block": 1, "measured": 7.145, "first_frame": "C1",
      "cuts": ["C1","C2","C3","C4"], "motion": "블록 전체를 관통하는 카메라 무브 서술" }
  ]
}
```

## TopView 호출 규칙

1. 먼저 `topview_get_generation_config`로 모델·옵션을 받아온다
   - 이미지: `{ type: "image", taskType: "text_to_image" }` 또는 `"image_edit"`
   - 영상: `{ type: "video", taskType: "image_to_video" }`
2. `models[].submitModel` 값을 **그대로** 넘긴다. `displayName`을 넘기지 않는다
3. 선택한 모델의 `requiredSubmitFields`에 있는 값은 전부 채운다
4. 제약값은 `submitParameterOptions`에서 고른다. 사용자가 안 정했으면 `defaultSubmitParameters`
5. `aspectRatio`는 `9:16`. 단 image_to_video는 입력 이미지가 비율을 정하므로 생략한다
6. 제출 후 `topview_query_task`로 완료를 확인하고 결과를 받는다

`code 4000`이나 모델 미지원 응답이 오면 멈추고 검증 오류 원문과 대안을 보고한다.

**안전 검사기 오류로 반려될 때** — 모델이 일시적으로 응답하지 못해 도구 호출을 심사하는 검사기가
막은 것이다. TopView 문제도, 크레딧 문제도, 프롬프트 내용 문제도 아니다.
권한 모드를 도구 허용 쪽으로 바꾸면 풀린다. 그때까지 `prompts.json`을 남겨 사용자가 직접 돌릴 수 있게 한다.

## 영상 블록 패키징

이미지는 컷 단위지만 **영상은 블록 단위로 묶어 생성한다.** 영상이 이미지보다 훨씬 비싸다.

- 블록의 첫 컷 이미지를 `firstFrameFileId`로 넣는다
- 프롬프트에 그 블록의 컷들을 이어 붙인 카메라 무브를 서술한다
- 길이는 TopView 생성 가능 길이 중 **실측을 덮는 가장 가까운 값**으로 올려 잡고 끝을 잘라낸다

```
실측 7.145s  → 10s 생성 후 트림
실측 11.519s → 15s 또는 10s+5s
```

결과물은 `projects/<슬러그>/clips/scene_01.mp4` 형식으로 저장한다.
`assemble.py`가 `scene_<블록번호>` 이름으로 찾는다.

**한 컷이 3초 넘게 정지해 보이면** 슬라이드쇼로 읽힌다. 해당 블록을 컷 시각을 명시해 재생성한다.
유튜브가 "image slideshows"를 비진정성 콘텐츠의 예로 직접 들고 있다. 움직임은 선택이 아니다.
