# Trailshop — 근거 기반 쇼핑 에이전트

`spec.md` v1.5의 쇼핑 여정을 구현한 로컬 프로토타입입니다. **Next.js / React / TypeScript / Tailwind** 프런트엔드와 **Python 3.12 / FastAPI / Pydantic / SQLite / FAISS / Pillow** 백엔드로 구성됩니다. 라이브 모드는 공식 OpenAI Python SDK의 Responses, Embeddings, Moderation, Images 생성·편집 API를 사용합니다. 에이전트 프레임워크, 실결제, 실제 고객 프로필 연동은 사용하지 않습니다. **현재 UI는 사용자 사진 업로드 대신 GPT-Image로 만든 가상 성인 샘플을 사용합니다.**

**범위:** 샘플 인물에 선택한 옷을 입혀 보는 시각적 참고 기능이며, **Fit Prediction·신체 치수 추정·실제 사이즈 적합성 예측은 하지 않습니다.** 기존 마네킹 코디 생성도 유지합니다. 개인 사진 업로드 컨트롤과 개인 사진 권한 동의 체크박스는 UI에서 제거했습니다.

**발표 범위:** 발표자 확인에 따라 데모 상품의 실제 OpenAI enrichment·별도 judge·게시·인덱싱·사람 검토를 완료했습니다. 이 완료 주장은 발표 상품 범위에 한정하며 전체 240개 상품의 검토나 실사용 품질을 의미하지 않습니다. 자동 회귀 검사는 합성 데이터와 모의 제공자를 사용합니다. 재현 결과를 라이브 성능이나 가상 착용 품질로 해석하면 안 됩니다.

## 빠르게 화면 확인하기 — API 비용 없음

프로젝트 루트에서 실행합니다. Node.js 22.13+ LTS 또는 24+ LTS, npm, `uv`, `make`가 필요합니다. Python 3.12는 `uv`가 관리합니다. 이 환경에서는 Node 23.10에서도 빌드했지만, 의존성의 공식 engine 범위를 따르는 LTS를 권장합니다.

```bash
make setup
DEMO_MODE=fixture make seed
DEMO_MODE=fixture make enrich
DEMO_MODE=fixture make index
DEMO_MODE=fixture make evaluate
```

서로 다른 터미널에서:

```bash
# 터미널 1: 백엔드, 반드시 단일 worker
DEMO_MODE=fixture make dev-api

# 터미널 2: 프런트엔드
make dev-web
```

브라우저: **http://localhost:3000**  
상태: http://localhost:8000/api/health  
OpenAPI: http://localhost:8000/docs

화면 상단에 **Replay — simulated API outputs**가 항상 표시됩니다. 이 모드의 속성·판정은 명시적인 문구 매칭 fixture, 대화는 제한된 재현용 해석기입니다. 인물 사진은 미리 생성된 고정 공개 자산이며, 새 가상 착용 결과는 **고정 마네킹 도식**입니다. **실제 Moderation 검사, 임베딩, Responses 추론, GPT-Image 호출을 하지 않습니다.** 서버 오류에 의해 이 모드로 자동 전환하지 않습니다.

Python 패키지 원본 CDN(`files.pythonhosted.org`) 연결이 이 개발 환경에서 실패하여 Tsinghua 공개 PyPI 미러로 잠금 파일을 생성했습니다. `backend/pyproject.toml`에 해당 레지스트리를 명시했고, `uv.lock`에는 아티팩트 해시가 포함됩니다. 원본 PyPI를 사용하려면 인덱스 설정을 바꾸고 별도로 잠금 파일을 재생성해야 합니다. 실행/설치는 기존 잠금 파일을 `--frozen`으로 사용합니다.

## 실제 OpenAI API 사용

루트 `.env`가 없을 때만 `.env.example`을 복사하고 **로컬 파일에서만** 설정합니다. 기존 `.env`는 덮어쓰지 마세요. 키를 브라우저 설정, 프롬프트, Git, 스크린샷이나 로그에 넣지 마세요.

```bash
test -f .env || cp .env.example .env
```

필수 값:

| 환경 변수 | 설정 |
|---|---|
| `OPENAI_API_KEY` | OpenAI 프로젝트 API 키 |
| `OPENAI_AGENT_MODEL` | `gpt-5.6-terra` — 쇼핑 대화와 도구 호출(Tool Calling) |
| `OPENAI_AGENT_REASONING_EFFORT` | `low` — 대화 추론 강도(Reasoning Effort) |
| `OPENAI_ENRICH_MODEL` | `gpt-5.6-terra` — 상품 속성 생성(Attribute Enrichment) |
| `OPENAI_ENRICH_REASONING_EFFORT` | `low` — 속성 생성 추론 강도 |
| `OPENAI_JUDGE_MODEL` | `gpt-6-astra` — 독립 검증(Independent Verification) |
| `OPENAI_JUDGE_REASONING_EFFORT` | `medium` — 검증 추론 강도 |
| `OPENAI_IMAGE_MODEL` | `gpt-image-2.5-flare` — 속도 우선 이미지 생성·편집(Image Generation / Editing) |
| `OPENAI_IMAGE_QUALITY` | `medium` — 콘셉트 생성과 가상 착용에 공통 적용하는 이미지 품질(Image Quality) |
| `DEMO_MODE` | `live` |

2026-09-21 공식 문서 기준으로 [GPT-5.6 Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra)는 이전 mini 계층에 해당하는 지능·비용 균형 모델, [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra)는 복잡한 추론용 최신 모델, [GPT Image 2.5 Flare](https://developers.openai.com/api/docs/models/gpt-image-2.5-flare)는 빠른 이미지 생성·편집용 최신 모델입니다. 계정 접근 가능 여부나 실제 지연 시간(Latency)을 보장하지는 않습니다. 임베딩(Embedding)과 안전성 검사(Moderation)는 `text-embedding-3-small`, `omni-moderation-latest`를 유지합니다.

추론 강도는 `none`, `low`, `medium`, `high`, `xhigh`, `max` 중 지정하며 GPT-6 Astra는 `none`을 허용하지 않습니다. 이미지 품질은 `auto`, `low`, `medium`, `high`, `xhigh`, `max` 중 지정합니다. 다른 모델로 변경하면 해당 모델의 지원 값도 확인하세요. 잘못된 설정 값은 시작 시 오류로 거절하며, API가 거절하는 조합도 숨기거나 자동 대체하지 않습니다.

환경 변수(Environment Variable)는 `.env`보다 우선합니다. 변경 후 백엔드를 재시작해야 적용됩니다. 생성·검증 추론 강도를 바꾸면 `make enrich && make index`로 다시 게시하세요. 라이브 검증 캐시 키(Cache Key)에 추론 강도를, 이미지 캐시 키에 품질을 포함하여 설정 변경 전 결과가 재사용되지 않도록 합니다. 재현 모드(Replay Mode)는 여전히 실제 모델을 호출하지 않습니다.

```bash
make preflight  # 설정 누락 및 각 모델 접근 확인; 생성 능력 검증은 다음 단계
make smoke      # 텍스트, 임베딩, Moderation, 독립 judge, 이미지 1장 실제 호출: 과금 가능
make seed
make enrich     # 240개 각각 생성 + 별도 judge; 캐시가 없으면 텍스트 API 최소 480회, 과금 가능
make index      # 승인된 projection만 임베딩하여 FAISS 인덱스 게시
make evaluate
make dev-api    # 별도 터미널에서 make dev-web
```

`make smoke`는 기존 마네킹 이미지 1장을 명시적으로 요청하는 명령이며, 이미지 편집을 검증하지는 않습니다. 이미지 호출을 제외하려면 `cd backend && uv run --frozen python -m app.cli smoke`를 사용합니다. preflight 결과는 `data/runtime/live-preflight.json`, smoke 이미지는 `data/runtime/images/smoke.png`에 저장합니다. 모델 목록 접근 성공만으로 생성·편집 기능이 지원된다고 간주하지 않습니다. **라이브 편집 smoke는 아래 UI에서 색상별 상품 이미지 준비 → 고정 인물 확인 → 채팅으로 `Show the try-on preview` 요청 순서로 확인**하세요. 착장 편집 1회 외에 캐시가 없는 상품 색상별 편집 호출이 추가되며 과금됩니다. 고정 인물 표시는 추가 생성 비용이 없습니다.

프런트엔드는 기본적으로 `http://localhost:8000/api`에 연결합니다. 다른 포트를 사용할 때는 `NEXT_PUBLIC_API_BASE_URL`을 프런트엔드 실행 환경에 export하거나 `frontend/.env.local`에 **이 공개 URL만** 설정합니다. 백엔드 `ALLOWED_ORIGIN`도 프런트엔드 origin에 맞추세요. 루트 `.env`는 백엔드가 읽으며 프런트엔드에 자동 복사하지 않습니다.

두 서버 모두 `127.0.0.1`에 바인딩합니다. CORS는 설정된 origin 하나만 허용합니다. 브라우저 주소로 `localhost:3000`을 사용하세요. `127.0.0.1:3000`은 origin이 다릅니다.

## 쇼핑 흐름

### 전체 상품 이미지 생성

`OPENAI_API_KEY`를 로컬 `.env`에 설정한 뒤 `make product-images`를 실행합니다.
현재 원본 상품 240개 각각의 **제품명·설명**으로 대표 이미지 1장을 실제 Images API에서 생성합니다.
상품 이미지에만 **816×816 / low / PNG**를 적용하며, 코디·샘플 인물·가상 착용의 기존 설정은 바꾸지 않습니다.
생성은 과금되는 작업입니다. 프롬프트 Moderation 후 순차 호출하며 호출 간 13초를 둡니다.
완료 파일은 `data/runtime/product-images/`에, 상품 ID·원문·모델·크기·품질·해시·상태는 `manifest.json`에 저장됩니다.
완료된 동일 설정의 이미지는 재실행 시 건너뜁니다. 실패/중단은 자동 재시도하지 않으며, 해당 실행의
과금 여부를 확인한 뒤 `cd backend && DEMO_MODE=live uv run --frozen python -m app.cli product-images --retry-incomplete`
로 재요청을 승인할 수 있습니다. 사용량은 표준 오류의 API 이벤트에 기록됩니다.
생성물은 가상 상품의 **AI-generated product illustration**이며 원본 상품 속성의 근거가 아닙니다.
API 서버는 시작 시, 이후 15초마다 **변경된 manifest만** 읽어 해시·PNG 크기·원문 매칭을 검증하고
SQLite `product_images` 테이블에 완료 이미지를 등록합니다. 라이브 DB는 기본
`data/runtime/catalog.sqlite`이며 재현 모드 DB·이미지 경로는 분리됩니다.
상품 상세 API에는 원본 대표 `image_url`을 반환하고, 추천·선택·보완 상품 카드에는 아래 색상별 `image_url`을 반환합니다.
이미지 요청은 JSON이 아닌 DB 매핑으로 파일을 조회하며, 버전별 URL에 브라우저 캐시를 적용합니다.
상품 카드와 선택 목록에는 AI 생성 이미지임을 표시하며 실제 색상·디테일과 다를 수 있음을 안내합니다.
미생성 상품은 실루엣을 유지하고 이미지 로드 실패는 별도 문구로 표시합니다.
기존 대화의 대표 이미지 대신 새 색상 흐름을 보려면 새로고침 후 다시 검색합니다.
동기화 실패는 서버 로그 및 `/api/health`의 `product_image_import_error`로 확인할 수 있습니다.

### 색상별 상품 이미지와 착장 일관성

검색·선택·보완 추천에 실제 표시되는 색상만 백그라운드로 생성합니다. 기존 대표 이미지를
`images.edit`의 입력으로 사용해 디자인·포켓·후드·지퍼 등을 유지하고 선택한 카탈로그 색상만 변경하도록 요청합니다.
색상 편집도 **816×816 / low**이며, 상품 ID·색상·기준 이미지 해시·프롬프트·모델·설정을 키로 재사용합니다.
동일 상품/색상은 사이즈가 달라도 이미지를 공유합니다. 모든 상품의 모든 색상을 일괄 생성하지 않습니다.

채팅은 생성을 기다리지 않습니다. 카드는 준비 중 상태를 보여주며 완료되면 자동으로 색상 이미지를 표시합니다.
일반 추천과 `Completes the outfit`의 보완품 모두 상태를 갱신하며, 새 목록이 나온 뒤에도 대화에 남은 이전 카드의 대기 중 이미지를 계속 확인합니다.
회색 대표 이미지를 선택 색상인 것처럼 표시하지 않습니다. 실패는 화면에 표시하고 **Retry color image**로만
재요청합니다(중단·실패 요청도 이미 과금되었을 수 있음). 상태 조회만으로 API 이미지 생성을 재시도하지 않습니다.
한 번에 한 색상 편집을 처리하며 시작 간격은 최소 13초, 대기/실행 작업은 최대 20개입니다.

색상 파일은 `data/runtime/product-images/colors/`, 매핑·상태는 같은 SQLite의 `product_color_images`에 저장합니다.
`GET /api/product-color-images/{key}`는 상태 조회, `.png` 경로는 파일 조회,
`POST /api/product-color-images/{key}/retry`는 명시적인 실패 재시도입니다.
원본 240개와 `manifest.json`은 변경하지 않습니다. 재시작 시 완료 캐시는 유지하고 미완료 작업은 실패로 표시합니다.

선택 상품의 색상 이미지가 모두 준비되어야 코디/가상 착용을 생성할 수 있습니다.
코디는 해당 상품 이미지들을, 가상 착용은 **인물 이미지 + 같은 색상 상품 이미지들**을
하나의 Images 편집 요청으로 보냅니다. 기준 이미지 해시가 바뀌면 이전 코디 캐시를 재사용하지 않습니다.
디자인·색상 일관성을 높이는 방식이지만 픽셀 단위 동일성·실제 색상 정확도·사이즈 적합성을 보장하지 않습니다.

### 앱 사용

상품 카드의 **Why we recommend it**에는 원본 상품 설명(Product Description), 요청과 일치하는 승인 속성(Approved Attributes),
예산·사이즈 및 선호 색상과의 일치를 상품별 추천 이유(Recommendation Rationale)로 표시합니다.
승인 속성이 없는 상품도 원본 설명과 실제 가격·재고 정보로 설명하며, 추론된 속성(Inferred Attributes)은 명시적 사양과 구분합니다.
추천 이유는 서버의 카탈로그·검색 조건으로 구성하므로 추가 모델 호출이나 순위 변경은 없습니다.

고객 정보(Customer Context)는 매 대화 요청의 첫 모델 입력에 서버가 직접 제공합니다.
`get_customer_context` 도구 호출(Tool Call)은 제거하여 이미 제공한 정보를 다시 요청하는 모델 왕복(API Round Trip)을 없앴습니다.
로컬 고객 프로필(Customer Profile)은 프로세스 내 캐시(Cache)에서 재사용하고 원본 파일의 변경이 감지되면 다시 읽고 검증합니다.
각 호출에는 독립 복사본을 반환하며, 파일 오류 시 이전 데이터로 조용히 대체하지 않습니다.
예산·사이즈·선택 상품·직전 추천 목록·추가 질문 여부 등 세션 상태(Session State)는 캐시하지 않고 매 요청에 최신 값으로 전달합니다.
안전성 검사(Moderation), 검색 필터 및 사용자 조건 우선순위는 그대로 유지합니다.
코드 변경 적용에는 백엔드 재시작이 필요하며, 모델 호출 횟수와 실제 지연 시간(Latency)은 요청에 따라 달라집니다.

**응답 지연 최적화(Latency Optimization)**

- 단일 검색·추가 질문·보완 추천은 모델이 `finish_turn=true`로 완료를 명시하면 도구 결과로 응답을 직접 구성합니다.
  정상적인 단일 모델 요청은 Responses 호출 1회이며, 검색 후 명시적으로 요청한 상품 선택처럼 여러 도구가 필요한 요청은 `finish_turn=false`로 기존 루프를 이어갑니다.
- 추가 질문의 선택 버튼은 `/messages`에 `priority_choice:true`와 허용된 선택 문구를 보냅니다.
  서버는 아직 활성 상태인 질문인지 검증하고 우선순위·선호 효능만 갱신합니다. Responses 호출은 0회이며, 자유 입력은 계속 모델이 해석합니다.
  재시도는 동일 요청 ID와 선택 유형을 유지하며, 완료된 중복은 저장된 응답을 반환합니다.
- 인식되는 영문 순번 선택(`Choose the first one`, `Add the first one`)은 입력·카드 버튼 모두 모델 라우팅 전 결정적으로 처리합니다. 최신 제안 목록을 참조하며 Responses 호출은 없지만 Moderation과 보완품 검색의 임베딩 호출은 발생할 수 있습니다.
- 입력 검사와 출력 검사(Moderation)는 유지합니다. 출력 검사는 폐기되는 모델 문장 대신 실제 표시할 문구·선택지·상품 카드·보완품 및 대안 데이터를 검사합니다.
  오류·차단 시 새 응답과 세션 변경을 저장하지 않습니다. 검사 시간 제한이나 실패 시 차단(Fail Closed) 정책을 완화하지 않습니다.
- 질의 벡터(Query Vector)는 모델·차원·검색 문자열을 키로 프로세스 메모리에 최대 128개, 5분간 보관합니다.
  상품 결과·가격·재고·사용자 상태는 캐시하지 않으며 인덱스 유효성과 필수 조건은 매번 확인합니다.
  적격 상품이 없으면 임베딩 요청을 생략하고 `filtered-empty`를 표시합니다. 모델 호출 실패를 감추는 대체 경로가 아닙니다.
- `query_embedding_cache` 로그로 적중 여부를 확인할 수 있습니다. 공급자 실패 로그에는 시도 시간·재시도 여부·대기 시간을,
  Moderation 호출에는 단계·요청 ID·정책 버전을 남깁니다. 실제 단축 시간은 새로운 라이브 로그로 측정해야 합니다.

1. Alex 프로필(M, $200, 중립색, 보유 미들레이어 1개)로 시작합니다.
2. `I need a jacket for hiking this fall.` → 우천/보온/경량 중 한 가지를 묻습니다.
3. `Light rain protection` 응답 칩 → 재고·사이즈·가격에 맞는 최대 세 상품을 표시합니다. 각 카드의 `Ranking scores`와 `Why this match`에서 점수·근거를 확인합니다.
4. `Choose the first one` 또는 `Select this jacket`으로 재킷을 선택합니다. 버튼은 채팅 요청을 보내는 단축 동작입니다. 비교 버튼·비교표·`compare_products` 에이전트 도구는 제공하지 않으며 비교 요청에는 미지원 안내를 표시합니다. 내부 비교 헬퍼만 기존 테스트용으로 남고 공개 비교 API는 없습니다.
5. 재킷 선택 응답의 `Completes the outfit`에는 보유·선택 상품을 제외한 서로 다른 카테고리의 보완품 최대 두 개가 표시됩니다. 최신 목록에서 `Add the first one` 또는 `Add to selection`으로 추가합니다.
6. **Your trail selection**에서 상품·색상·사이즈·합계를 검토하고 채팅으로 **Save this to the demo cart**를 전송하면 상단 장바구니 아이콘의 상품 수만 갱신합니다. 별도 장바구니 화면·장바구니 저장 API·주문·결제는 구현하지 않습니다. 기존 선택 검증이 성공한 옵션(variant)을 브라우저 메모리에서 중복 없이 집계하며, 이미 담은 상품을 재검토해도 수가 늘지 않습니다. 선택/조건 변경 시 숫자는 유지되고 새로고침·여정 초기화·프로필 변경 시 0으로 초기화됩니다. 이미지 없이 저장할 수 있고 이후 `Yes, that helped` / `Not yet`로 유용성 피드백(helpfulness feedback)을 남깁니다.
7. 선택한 색상 이미지가 준비되면, 채팅으로 **Show the try-on preview**를 요청해 선택적인 비동기 착장 편집을 시작합니다. 준비된 참조 개수와 대기/실행 경과 시간을 표시하며 완료 시각을 예측하지 않습니다.
8. **Why this match**에서 간결한 상품 근거 요약과 원본, 제안, 판정, 승인 속성, 원문 인용, 모델/실행 메타데이터를 확인합니다.

### 조건 변경, 결과 없음, 피드백

예산·색상·필수 효능·사이즈를 바꾸면 기존 선택을 보존하면서 현재 조건과 충돌하는 항목을 표시합니다.
새 조건/상품 선택은 기존 확인과 비공개 착장 결과를 무효화합니다. 충돌은 다른 상품으로 교체하거나
**Accept exceptions and save to demo cart**로 명시적으로 수락해야 새 시각화를 요청할 수 있습니다.
품절/존재하지 않는 옵션은 예외 수락으로 통과할 수 없습니다. 합계는 세금·배송비 전 선택 상품 합계이며
재킷 예산을 전체 코디 예산으로 오해하지 않도록 별도로 표시합니다.

검색 결과가 없으면 실제 카탈로그로 확인한 **한 가지 조건 변경**만 제안합니다.
가능한 최소 예산 인상, 필수 색상 해제, 필수 효능 하나 해제 중 결과가 존재하는 대안과 상품 수를 보여줍니다.
사이즈는 자동 변경하지 않으며 클릭 전에는 어떤 조건도 바뀌지 않습니다. 오래된 대안은 서버가 거절합니다.

**How this recommendation was built**의 source-only ranking은 현재 추천과 같은 카테고리·재고·사이즈·색상·가격·필수 효능 필터를 적용합니다.
순위만 원본 설명의 lexical 점수로 정합니다. 필수 효능의 자격 판정은 승인 속성에 의존할 수 있으므로
순수 enrichment 제거 실험이나 성능 향상 증명이 아닙니다.

여정 지표(Journey Metrics) 패널과 갱신 버튼은 데모에서 제거했습니다.
프런트엔드는 지표 조회와 목록/비교 표시 이벤트 전송을 하지 않습니다.
선택 확정 API는 데모 장바구니 카운터 갱신 전 검증에 재사용하며 유용성 피드백(Helpfulness Feedback)을 유지합니다. 선택 상태 응답의 `feedback_recorded`로
동일 선택 버전(revision)의 중복 피드백을 방지합니다. 기존 서버 진단 기록과 호환 API는 유지하지만
현재 데모의 여정 시간 측정 기능으로 사용하지 않습니다.

`DAILY_IMAGE_CALL_LIMIT=100`은 UTC 날짜 기준 **런타임** 색상 편집·코디·가상 착용·레거시 샘플 생성의
공유 이미지 호출 예약 한도입니다. `0`은 신규 이미지 호출을 막습니다. provider 호출 직전에 SQLite로 원자적으로 예약하고,
실패/과금 불명 호출도 횟수에 포함하며 재시작 후에도 유지합니다. 완료 캐시 조회는 차감하지 않습니다.
일괄 CLI 상품 생성·smoke, 텍스트·임베딩·Moderation 비용은 포함하지 않으며 달러 예산의 대체물이 아닙니다.
HTTP 로그에는 request ID·경로·상태·시간을 남기며 요청 본문·사진·키는 기록하지 않습니다.

추가 API: `POST /selection/confirm` (`revision`, `accept_exceptions`), `POST /journey/feedback` (`revision`, `helpful`),
`GET /baseline?q=...`, `POST /relax` (`alternative_id`). 축약 경로는 모두 `/api/sessions/{id}` 아래입니다.
기존 `GET /journey`, `POST /journey/events`는 호환성을 위해 남아 있으나 데모 UI에서는 호출하지 않습니다.

좁은 브라우저 패널이나 모바일에서는 상품 목록이 채팅 아래에 표시됩니다. 추천 응답 후 채팅의 **View 3 matches ↓** 링크(실제 결과 수 표시)를 누르면 상품 영역으로 바로 이동합니다.

### 고정된 가상 인물 전신샷으로 가상 착용하기

코디를 선택하면 **Fixed fictional demo model**에 미리 생성한 가상의 성인 전신사진을 바로 표시합니다.
`data/demo/sample-person.png`는 사용자 승인 아래 한 번 생성하고 안전 검사·메타데이터 제거를 거친 공개 데모 자산입니다.
생성 이력과 해시는 `data/demo/sample-person.json`에 저장됩니다. 세션·새로고침·서버 재시작과 무관하게
같은 파일을 재사용하며, 인물 생성·재생성 버튼이나 화면 표시 시 Images 생성 호출은 없습니다.

선택 색상 이미지가 준비되면 **Generate virtual try-on**을 누릅니다.
`POST /api/sessions/{id}/try-ons/demo`는 고정 인물 파일의 해시를 확인하고,
**같은 인물 bytes를 첫 입력으로, 카드와 같은 색상 상품 이미지들을 추가 입력으로 `client.images.edit`에 전달**합니다.
인물을 다시 생성하지 않습니다. 미완료 색상 편집을 제외하면 착장 버튼당 이미지 편집 1회입니다.
화면에는 “실제 쇼핑 서비스에서는 동의하에 구매자 전신사진을 업로드하여 가상 착용을 제공할 수 있지만,
현재 데모에는 사진 업로드가 없다”는 설명을 표시합니다. 결과 안내는 다음과 같습니다.

> AI virtual try-on — visual reference only; appearance may differ. No size or fit prediction.

결과로 치수·조임·착용감·구매 사이즈를 판단한다고 주장하지 않습니다.
선택 상품 이미지를 디자인 참조로 사용하지만 상품 외관의 정확한 재현이나 인물 모습의 완전한 보존을 보장하지 않습니다.

**Remove try-on preview**는 생성 중에도 사용할 수 있습니다. 로컬 편집 작업과 비공개 결과만 제거하고
선택 상품과 고정 공개 샘플은 유지합니다. 결과가 만료되면 같은 고정 사진으로 착장 편집을 다시 요청할 수 있습니다.
기존 세션별 인물 생성·샘플 ID 기반 편집·동의 기반 업로드 API는 호환성을 위해 유지하지만 현재 UI에서는 사용하지 않습니다.

### 샘플 이미지 처리·보관 정책

| 항목 | 동작 |
|---|---|
| 입력 | 서버에 저장된 고정 가상 인물 전신사진. UI에서 파일·사용자 프롬프트·외부 이미지 URL을 받지 않음 |
| 정규화 | EXIF 방향 보정, 최대 1536px로 축소, 픽셀 전용 RGB PNG로 재인코딩. EXIF/GPS/ICC/텍스트 메타데이터 제거 |
| 전송 | 고정 사진 표시는 로컬 GET만 사용. 채팅에서 명시적인 착장 요청 이후 인물·상품 이미지와 프롬프트를 검사하고 Images 편집 호출 |
| 고정 샘플 | `data/demo/`의 공개 합성 자산으로 지속 저장. 실제 고객 사진이 아니며 만료되지 않음 |
| 가상 착용 결과 | 메타데이터 제거 후 **프로세스 메모리에서만 보관**, 각 작업 생성 시점 기준 15분 만료. 디스크·SQLite·대화·인덱스·로그에 결과 bytes 저장 안 함. 만료 시 접근 차단, 최대 30초 주기의 메모리 정리 |
| 결과 접근 | 세션/작업별 전용 URL, `Cache-Control: no-store`, 공용 `/media` 및 공유 코디 캐시에서 접근/재사용 불가 |
| 삭제/재시작 | 결과 제거·Reset 시 비공개 결과 삭제 및 작업 취소. 프로세스 재시작 시 비공개 결과 접근 불가. 고정 공개 인물 사진은 유지 |
| 남는 메타데이터 | 작업 상태·생성 시각, 선택 상품, 샘플 작업 ID, 세션별 fingerprint. 이미지 bytes는 없음 |
| 운영 한도 | 샘플 생성·코디·가상 착용 합산 세션당 신규 이미지 5개/활성 작업 1개. 프로세스 전체 비공개 작업/결과 20개 |

샘플은 실제 사용자를 나타내지 않으며, 생성 프롬프트와 Moderation이 외관·성인 여부를 완벽히 보증하지는 않습니다. 세션 UUID는 사용자 인증이 아니므로 서버를 공개 인터넷에 노출하지 마세요. 로컬 삭제는 제공자 데이터 보존이나 브라우저/RAM의 완전한 물리 삭제를 보장하지 않습니다.

**기존 업로드 API 호환성:** `POST /try-ons`는 UI에서 사용하지 않지만 기존 직접 API 클라이언트를 위해 유지합니다. 이 경로는 여전히 `consent:true`, 단일 프레임 JPEG/PNG 5 MiB 이하, 256–4096px/16MP 이하, JSON 7 MiB/15초 제한, 메타데이터 제거 및 안전 검사를 강제합니다. 샘플 경로의 동의 체크박스 제거가 실제 사진 업로드의 동의 검사를 해제하지는 않습니다.

완성된 요청에는 추가 질문을 하지 않습니다. `Skip`은 알려진 조건으로 진행합니다. 예산·사이즈·의도 변경은 새로운 검색으로 이어집니다. 라이브 모드 프롬프트는 한국어와 영어 요청을 지원하도록 구성했으며, 데모 화면과 정형 응답 템플릿은 영어입니다. 재현 해석기는 전체 자연어 기능의 대체물이 아닙니다.

`How this recommendation was built` 아래에서 같은 원본 카탈로그의 키워드 검색과 점수 항목을 확인할 수 있고 Sam 프로필로 전환할 수 있습니다. $200 재킷 예산을 코디 전체 예산으로 재사용하지 않습니다. 코디 가격은 개별 표시하며 별도 코디 총예산 제약 UI는 제공하지 않습니다.

## 신뢰 경계와 저장

- **원본 불변(Immutable Source):** `raw_products.json`은 AI 파생 속성이 없는 240개 상품입니다. commerce는 별도 소스이며 명시적 변형별 재고를 가집니다. 추가 전용 가져오기(Append-only Import)는 기존 상품의 ID와 원본 해시(Source Hash)를 유지한 새 상품 추가만 허용합니다. 기존 원본 수정·누락은 거절하며, 원본 변경은 새 DB 경로에서 다시 생성·검증·인덱싱해야 합니다. 추가 시 오래된 인덱스 참조를 해제하며 새 상품은 enrichment 게시 전까지 원본 전용(Raw-only)으로 처리됩니다. 기존 대화·작업·감사 기록은 삭제하지 않습니다.
- **독립 검증:** 생성과 판정은 별도 Responses 호출입니다. 서버가 ID/hash/모델/실행 정보를 찍습니다. 원문 인용, 후보 중복, 종류별 상한, 완전한 1:1 판정 ID 매핑을 검증합니다. 누락·중복·잘못된 승인 근거는 전체 실행을 격리하고 raw-only로 남깁니다.
- **보수적 게시:** 판정이 값을 고쳐 쓰도록 허용하지 않습니다. 기술 등급이나 추론된 성능 속성은 게시하지 않습니다. 같은 모델을 두 번 호출하는 것이 완전한 독립성이나 정확성을 보장하지는 않습니다.
- **승인 데이터만 검색:** embedding projection은 이름·카테고리·설명·승인된 속성만 포함합니다. 거절된 주장과 judge 사유는 검색 텍스트에 들어가지 않습니다.
- **정확한 hard filter:** SQLite JSON1에서 가격/카테고리를 검사하고, **동일 변형의** 사이즈·색상·재고를 함께 확인합니다. 필수 혜택에는 명시적 승인 근거가 필요합니다. FAISS는 전체 240개를 조회한 뒤 eligible set에 한정합니다.
- **모드와 버전 분리:** 재현 DB는 `catalog.fixture.sqlite`, 인덱스/이미지는 `fixture/` 하위 경로에 저장합니다. 실행 모드가 다른 게시 데이터를 라이브로 서비스하지 않습니다. 버전별 FAISS·ID map·manifest를 완성한 뒤 SQLite의 활성 manifest 참조를 원자적으로 전환합니다. 재게시 시 이전 인덱스를 조회하지 않고 표시된 lexical fallback을 사용합니다.
- **백엔드 소유 사실:** 순위·가격·재고·카드·근거 칩은 서버 데이터에서 생성됩니다. 모델이 만든 상품 ID/근거/순서는 검사합니다. 자유 생성 텍스트를 상품 사실 설명으로 렌더링하지 않습니다.
- **네 종류의 Moderation gate:** 새로운 채팅 입력, 생성된 메시지/선택지, 카탈로그를 포함한 최종 이미지 프롬프트, 정규화한 가상 착용 사진(`try_on_photo`)을 검사합니다. `flagged=true`는 고정 안전 메시지, 장애는 fail-closed 503입니다. 완료된 중복 메시지는 다시 검사하지 않습니다. 사진 요청은 직접 API와 중복 제출에도 이미지/프롬프트 검사를 우회할 수 없습니다.
- **제한된 실행:** 턴당 45초, Responses 최대 4회, 도구 최대 6회, 세션별 직렬 처리와 메시지 요청 ID 멱등성. 모델 출력 항목과 `function_call_output.call_id`를 보존합니다. `store=false`이며 최근 대화만 로컬에 보관합니다.
- **이미지:** 착장은 명시적 채팅 요청(입력 또는 응답 칩)으로만 승인합니다. 상품 색상 참조는 검색 중 자동 준비될 수 있습니다. 모델 도구는 사진이나 동의 정보를 받을 수 없으며, 확인 없는 착장 생성을 거절합니다. 마네킹 코디만 선택·source hash·모델·프롬프트 버전 기반 캐시를 사용합니다. 사진 결과는 캐시 공유 없이 일시 보관합니다. 재시작 시 중단 작업 및 사진 결과는 실패 처리합니다. 2초 polling, 120초 후 계속 확인 버튼을 제공합니다.

Moderation은 상품 진실성·사진 사용 권한·성인 여부·도구 권한·프롬프트 인젝션 방어의 대체물이 아닙니다. 선택된 합성 데이터와 샘플 이미지는 라이브 모드에서 OpenAI로 전송됩니다. Responses의 `store=false`는 이미지 API의 보존 설정도, 제공자 보존이 0이라는 보장도 아닙니다. 샘플 인물은 생성 후 검사하지만 최종 착용 결과의 후처리 안전 분류, 실제 핏/정확한 상품 외관 보장, Fit Prediction, 실시간 날씨/재고/결제/인증은 구현하거나 주장하지 않습니다.

## API 및 파일

명세 §9의 필수 `/api` 경로를 제공합니다. `/docs`에서 요청 스키마를 확인할 수 있습니다. 공통 도메인 오류는 `{error:{code,message,retryable},request_id}` 형태입니다. enrichment는 CLI 전용이며 공개 쓰기 API가 없습니다.

| 위치 | 역할 |
|---|---|
| `backend/app/enrichment.py`, `prompts/` | 생성·독립 judge·결정적 게시 |
| `backend/app/retrieval.py` | hard filters, lexical/semantic ranking, versioned FAISS |
| `backend/app/agent.py`, `tools.py` | bounded Responses loop와 서버 도구 |
| `backend/app/moderation.py`, `images.py` | fail-closed screening, 비동기 이미지 작업 |
| `backend/app/photos.py`, `backend/prompts/try_on.txt` | 사진 검증·메타데이터 제거 및 핏 예측 없는 편집 지침 |
| `frontend/components/` | Chat, ProductCard, Comparison, Outfit, AuditDrawer |
| `data/seed/` | 원본 240개, commerce, Alex/Sam |
| `data/fixtures/` | 명시적 재현 규칙과 5개 adversarial 후보 |
| `evals/cases.json` | 12개 고정 평가 케이스 |
| `data/runtime/` | SQLite, 인덱스, 이미지, 측정 로그; Git 제외 |

Optional mock cart는 의도적으로 제외했습니다.

### 합성 카탈로그(Synthetic Catalog) 240개

기존 24개 상품과 가격·재고를 유지하고 216개를 추가했습니다. 재킷(Jacket) 120개, 미들레이어(Midlayer) 40개, 바지(Pants) 40개, 액세서리(Accessory) 40개입니다. 9개 가상 컬렉션(Collection)에 계절·활동·디자인·색상·가격·변형별 재고(Variant Stock)를 달리했으며, 실제 브랜드나 기술 인증은 사용하지 않습니다. `J100`–`J120`도 정상 상품 ID입니다. 화면의 상품 수는 상태 API(Health API)에서 읽습니다.

```bash
# 프로젝트 루트: 동일한 합성 원본·commerce·평가 라벨을 재생성
backend/.venv/bin/python backend/scripts/expand_catalog.py
# 실제 OpenAI 호출 없이 현재 재현 DB에 추가하고 승인 속성을 다시 게시
DEMO_MODE=fixture make seed
DEMO_MODE=fixture make enrich
DEMO_MODE=fixture make index
DEMO_MODE=fixture make evaluate
```

새 평가 라벨(Evaluation Label)은 검색 결과에서 복사하지 않고 작성된 상품 유형별 혜택·가을 하이킹 적합성 및 가격·재고에서 생성합니다. 기존 24개 수동 라벨은 유지합니다. 이는 합성 회귀 평가(Synthetic Regression Evaluation)이며 사람의 관련성 평가를 대신하지 않습니다. 재현 규칙(Replay Rule)이 변경되면 해당 검증 캐시도 무효화합니다. 재현 모드의 `index`는 실제 FAISS를 만들지 않습니다.

샘플 API: `POST /api/sessions/{id}/sample-people`는 `{request_id}`로 샘플 생성 작업을 시작합니다. `POST /api/sessions/{id}/try-ons/sample`는 `{request_id,variant_ids,sample_job_id}`로 해당 세션의 완료된 샘플을 편집합니다. 기존 업로드 API는 `{request_id,variant_ids,photo_base64,consent:true}`를 받습니다. `DELETE /api/sessions/{id}/try-ons`는 샘플과 착용 작업/결과를 함께 제거합니다. 상태는 기존 작업 경로, 이미지는 `GET /api/sessions/{id}/outfits/{job_id}/image`에서 제공됩니다.

## 검증과 측정

```bash
make test
cd backend && uv run --frozen ruff check app tests
cd ../frontend && npm run build
npx playwright install chromium   # 최초 한 번
npm run test:e2e
```

브라우저 검증은 fixture API와 Next 개발 서버를 자동 시작·종료하므로 8000/3000 포트를 비워두세요. 이미 사용 중인 서버를 강제 종료하지 않습니다. 1280×800 전체 흐름, 390px 화면의 가로 overflow/키보드 이동, 고정 샘플 표시·가상 착용·삭제, 비교·선택 확인·피드백 및 조건 변경 대안을 검사합니다. 캡처는 `data/runtime/journey-1280.png`이며 실제 사용자 사진을 사용하지 않습니다.

2026-09-22 로컬 검증 (검색 평가 수치는 2026-09-21 실행):

| 항목 | 관측 결과 |
|---|---|
| 백엔드 자동 테스트 | 159개 통과 (기존 흐름, 직접 비교, 선택 확인/충돌, 대안, 이벤트, runtime 이미지 한도 포함) |
| 브라우저 | 7개 시나리오 통과: 고정 인물·비교·확인·피드백·조건 변경·baseline·모바일 |
| TypeScript / ESLint | 통과. 이번 변경에서 production build는 공유 dev 서버 보호를 위해 실행하지 않음 |
| 평가 | 12케이스 × 3전략 = 36회, **fixture** |
| hard-constraint 위반 / eligible count 불일치 | 0 / 0 |
| fixture 검색 중앙값 | 1.45 ms, n=36 (`evals/results.fixture.json` 참조) |
| source lexical / enriched lexical / hybrid 표기 run의 hit@3 | 각각 1.0. fixture에서는 hybrid도 semantic 없는 정규화 점수이므로 **실제 hybrid 품질이나 개선 효과가 아님** |
| live chat / live image 생성·편집 지연 | 미측정 |
| 사람 검토 unsupported-claim 수 | 미측정 |

`hit@3`는 relevant ID 라벨이 비어 있지 않은 케이스에서 상위 3개 중 하나라도 포함되면 1인 이진 지표입니다. 세 비교 전략은 같은 hard filter를 적용합니다. 정확한 prose나 매출/전환율 향상을 측정하지 않습니다. 작은 fixture 집합에서 통과한 것은 일반화된 안전성 증명이 아닙니다.

## 실패 복구 및 정리

- **설정 누락:** 라이브 서버는 시작 시 필요한 키/모델 이름을 나열하고 중단합니다. 설정 후 `make preflight`와 `make smoke`를 실행하세요.
- **judge 실패:** 한 번 재시도 후 해당 실행은 quarantined/raw-only. 원인을 해결하고 `make enrich && make index`를 실행합니다. 성공한 검증만 cache를 재사용합니다.
- **임베딩/인덱스 장애:** `lexical-fallback` 표시로 계속 검색합니다. 모델과 manifest 차원을 확인한 뒤 `make index`로 다시 만드세요.
- **Moderation/대화 API 오류:** 이전 카드와 선택은 유지됩니다. 오류를 확인하고 Retry message로 같은 요청 ID를 재시도합니다. 블록된 원문은 서버 대화 기록/일반 로그에 넣지 않습니다.
- **이미지 실패:** 선택은 유지되며 Retry concept은 새 요청 ID를 사용합니다. 결과가 늦으면 Continue checking으로 같은 작업을 계속 조회합니다. 다른 코디 이미지를 대신 보여주지 않습니다.
- **고정 샘플 오류/결과 만료:** 공개 인물 자산 오류는 파일/해시를 확인합니다. 인물을 다시 생성하지 않습니다. 만료된 비공개 착장 결과만 같은 고정 인물로 다시 요청하며, 다른 인물이나 마네킹 캐시로 대체하지 않습니다.
- **새 여정:** Reset journey는 이전 세션의 비공개 사진 결과/로컬 작업을 먼저 제거한 뒤 새 세션을 만듭니다. 이전 쇼핑 대화나 일반 마네킹 이미지를 삭제하는 동작은 아닙니다.
- **전체 로컬 데이터 분리/초기화:** 서버를 정상 종료하고 `DATABASE_PATH`, `INDEX_DIR`, `IMAGE_DIR`를 새로운 `data/runtime/` 하위 경로로 설정한 뒤 seed부터 실행하세요. 이전 데이터가 필요 없으면 서버 종료 상태에서 해당 SQLite 파일(`-wal`, `-shm` 포함)과 그 실행의 인덱스·이미지만 직접 삭제할 수 있습니다. 자동 광역 삭제 명령은 제공하지 않습니다.

## 발표 범위와 프로덕션 전 남은 작업

데모 상품의 live enrichment·검증·게시·인덱싱·사람 검토는 발표자 확인 범위에서 완료했습니다.
녹화 환경에서는 해당 상품의 run/source/index 버전과 실제 API 모드를 확인하고 준비된 상품 이미지를 재사용합니다.
실제 latency 분포, API 비용, 더 넓은 상품의 unsupported-claim 비율과 쇼핑 완료율은 별도 표본을 모아 평가해야 합니다.
기존 fixture 평가 수치나 여정 시간만으로 검색 품질·전환율 개선을 주장하지 않습니다.

운영 전 역할과 단계: Commerce engineering은 인증/재고/배포와 장애 복구를, merchandising은 원문과 게시 속성 검토를,
privacy/security 담당은 사진 동의·보존·접근 정책을 맡습니다. Head of Digital Commerce는 사업 후원자로서
제한된 트래픽의 A/B 파일럿과 진행/중단 기준을 승인합니다. 같은 조건의 비교군에서 선택 완료율·만족도·
사용자당 시간·unsupported claim·오류/지연·완료 여정당 비용을 함께 측정한 뒤 확대를 결정합니다.

이 로컬 프로토타입은 인증되지 않은 공개 서비스에 배포할 용도가 아닙니다. 프로덕션에는 사용자 인증/세션 소유권, 실제 재고 API, durable 작업 큐, 증분 source version/rollback, 더 넓은 adversarial 평가, 이미지 후검사, 개인정보 검토와 운영 한도가 추가로 필요합니다.

공식 참고: [Function calling](https://developers.openai.com/api/docs/guides/function-calling), [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [Images](https://developers.openai.com/api/docs/guides/image-generation), [Moderation](https://developers.openai.com/api/docs/guides/moderation).
