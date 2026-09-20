# 결 (Gyeol)

영상 한 편의 결을 뜯어서 스킬로 만들어 둡니다.
그다음부터는 주제만 바꿔 넣어도 같은 결로 나옵니다.

## 이게 뭐냐면

본받고 싶은 영상 링크를 하나 넣습니다.

그 영상이 이야기를 밀고 가는 방식을 해부합니다.
말투, 문장 길이, 도입에서 붙잡는 수법, 감정 올리는 순서, 화면 분위기.

해부한 결과는 **클로드 스킬 파일**로 저장됩니다.
이 앱 안에서도 쓰고, 클로드 코드나 클로드 데스크톱에 넣어서도 씁니다.

다음부터는 주제만 넣으면 됩니다.
주제가 달라져도 결은 그대로 갑니다.

## 깔기

```bash
git clone <이 저장소 주소>
cd -2

python3 -m venv .venv
source .venv/bin/activate        # 윈도우는 .venv\Scripts\activate
pip install -r requirements.txt

export ANTHROPIC_API_KEY=여기에_키값    # 윈도우는 set ANTHROPIC_API_KEY=키값
```

## 화면으로 쓰기

```bash
cd src
python -m gyeol 서버
```

브라우저에서 `http://127.0.0.1:8000` 을 엽니다.

1. **결 뽑기** — 영상 링크를 넣고 누릅니다
2. **내 결** — 저장된 결 목록입니다
3. **대본 만들기** — 결을 고르고 주제만 넣습니다

## 터미널로만 쓰기

브라우저를 안 켜도 됩니다.

```bash
cd src

# 영상에서 결을 뽑아 저장
python -m gyeol 결뽑기 "https://www.youtube.com/watch?v=..." --저장

# 자막이 막힌 영상은 대본 파일로
python -m gyeol 결뽑기 --대본 대본.txt --저장

# 저장된 결 보기
python -m gyeol 목록

# 그 결로 새 대본 쓰기
python -m gyeol 대본 gyeol-20260920-130000 "김좌진과 청산리" --분 8
```

결과는 `data/projects/` 아래에 쌓입니다.

| 파일 | 내용 |
| --- | --- |
| `script.txt` | 성우가 바로 읽을 나레이션 원고 |
| `script.json` | 전체 데이터 |
| `production_order.json` | 영상 생성 도구에 넣을 장면별 지시서 |

## 영상 생성 도구에 붙이기

`production_order.json` 안에 장면마다 영문 프롬프트가 들어 있습니다.
힉스필드, 톱뷰 같은 도구에 그대로 넣으면 됩니다.

클로드에 그 도구의 MCP가 연결되어 있으면 한 단계 더 갑니다.
저장된 스킬을 불러서 "이 결로 만들어줘" 하면
대본부터 장면 생성까지 이어서 처리합니다.

## 자막이 안 잡히는 영상

비공개거나 자막을 막아둔 영상이 있습니다.
그럴 때는 화면의 **자막 직접 넣기**에 대본을 붙여넣으세요.
오히려 이쪽이 더 정확합니다.

## 손으로 고치기

뽑아낸 결이 마음에 안 들면 파일을 직접 고쳐도 됩니다.

```
data/skills/<결이름>/
  dna.json     해부 결과
  SKILL.md     클로드가 읽는 지시문
  meta.json    원본 정보
```

`SKILL.md` 를 고치면 다음 대본부터 바로 반영됩니다.

## 설정

| 환경변수 | 하는 일 | 기본값 |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | 클로드 API 키 (필수) | 없음 |
| `GYEOL_MODEL` | 쓸 모델 | `claude-opus-5` |
| `GYEOL_AUDIENCE` | 시청 타깃 | `40~60대 시니어 시청자` |
| `GYEOL_DATA_DIR` | 저장 위치 | `data/` |

## 테스트

```bash
python -m pytest -q
```
