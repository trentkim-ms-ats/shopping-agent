# Trailshop — Live API 시연 기준 슬라이드 해설

**기준:** 2026년 9월 23일 · Live API 발표 구성 · 8장  
**슬라이드:** [영문 HTML](trailshop-shopping-assistant.html)  
**녹화 대본:** [5분 영문 스크립트](trailshop-5-minute-recording-script.en.md)

PDF는 사용하지 않습니다. 제출 대상은 슬라이드와 약 5분의 시연 영상이며, 이 해설과 대본은 발표자용 자료입니다. 기존 `trailshop-demo-presentation.md`는 보존된 초기 계획으로, 장바구니·이전 타임라인을 현재 동작처럼 읽지 않습니다.

**Live 전제:** 녹화 전 `/api/health`의 `mode: "live"`와 게시·색인 일치, 실제 모델 응답과 착장 편집 완료를 확인합니다. 자료 수정이 서버 모드 변경이나 Live 리허설 완료를 뜻하지 않습니다. `fixture`이면 녹화를 멈추고 Live 환경을 준비합니다. Replay를 Live 대본에 덮어씌우지 않습니다. HTML의 `N` 또는 `Notes`로 발표자 노트를 숨긴 뒤 녹화합니다.

구분할 것은 **실시간 API 호출**(대화 해석·새 착장 편집), **사전 준비**(합성 상품·프로필·재고, enrichment·index, 고정 인물·상품 참조), **향후 계획**(실제 커머스·운영 통제·adoption 계측·매출 효과)입니다. 우선순위 칩과 임베딩 캐시는 일부 호출을 생략할 수 있으므로 모든 클릭이 모델을 호출한다고 설명하지 않습니다.

## 발표 구조

| 장 | 핵심 메시지 | 영상에서의 사용 |
|---|---|---|
| 1 · Customer & Problem | 고객 Trailshop, 사용자 온라인 쇼핑객, 발표 대상/잠재 후원자 Head of Digital Commerce | 0:00–0:20 |
| 2 · Before & After | 별도 채팅 서비스가 아닌 쇼핑 여정 내 통합. 직접 구현한 범위와 API 선택 이유 | 0:20–0:35 |
| 3 · Catalog Evidence | 원본 → 생성 → 별도 검증 → 게시·색인. 232개 완료·8개 원문 전용(source-only) | 보조 슬라이드; 앱에서 증거 제시 |
| 4 · Ranking & Shopper Control | 상품별 점수 토글(score toggle), 선택·보완품 구분, 조건 변경 검토 | 보조 슬라이드; 비교 UI는 제거됨 |
| 5 · Reference-Based Visualization | 고정 인물 + 동일 색상 상품 참조를 이미지 편집 API에 전달 | 보조 슬라이드 |
| 6 · Save & Feedback | 데모 저장·개수 표시(demo count)와 유용성 피드백(helpfulness feedback) | 보조 슬라이드 |
| 7 · Overall Architecture | API 책임과 사전 검증·단일 워커의 trade-off | 3:45–4:10 |
| 8 · Value & Production Adoption | 가정 기반 계산, 사용 시작·완료·재사용 KPI, 담당자와 확장·롤백 기준 | 4:10–5:00 |

영상의 **0:35–3:45, 약 63%는 실제 앱**을 보여줍니다. 3–6장을 읽느라 시연 시간을 줄이지 않습니다.

## 1. 고객과 문제

Trailshop은 가상의 아웃도어 리테일러입니다. Head of Digital Commerce는 **발표 대상이자 잠재 경제적 구매자·사업 후원자**이며 최종 사용자가 아닙니다. 이 가상 시나리오에서는 전환율과 디지털 쇼핑 경험을 책임지는 역할로 설정합니다. 사용자는 가을 하이킹용 재킷을 선택하는 쇼핑객입니다.

문제는 활동과 선호를 상품 설명·필터로 번역하고 여러 상품을 비교해야 한다는 점입니다. 실제 고객 인터뷰나 문제 규모를 측정했다는 주장은 하지 않습니다. Alex의 M 사이즈·$200 재킷 예산·중립색 선호와 보유 상품은 합성 프로필입니다.

## 2. 이전과 이후, 직접 구현한 부분

이전에는 쇼핑객이 검색어·필터·설명·비교를 조합합니다. 본 녹화는 **요청 → `Light rain protection` 칩 → 최대 세 상품과 점수 토글 → 재킷 선택 → 함께 반환된 보완품 선택 → 선택적 착장 → 근거 → 데모 저장·피드백**입니다. 비교 칩·비교표·에이전트 비교 도구는 제공하지 않으며, 비교 요청에는 미지원 안내를 표시하고 선택을 변경하지 않습니다.

현재 화면은 상단 소개 영역(`Your next trail starts here.`) 아래 접힌 근거 패널(evidence panel), 그 아래 단일 대화 열(single conversation column)입니다. 별도 가을 배너는 없으며 소개 영역의 `Autumn, considered.` 문구는 유지됩니다. 상품 카드·선택 요약·미리보기가 대화 안(inline)에 있으며 별도 우측 패널은 없습니다. 입력창 이름은 `Reply to your trail guide`입니다. 채팅은 텍스트이며 음성 기능(voice)은 없습니다.

상품 이미지는 왼쪽 순번 아래 커진 영역에 표시되며 `Select this jacket` 옆에 `Or say…` 안내가 있습니다. `Choose the first one` 입력과 버튼의 `Choose the first` 전송은 모두 순번 메시지(ordinal message)이며 **최신 제안 목록(latest offered list)** 기준입니다.

재킷 선택 응답의 큰 제목 `Now in your selection`은 선택 완료 상품을, 강조된 `Completes the outfit` 블록은 추가 보완품 제안(complement suggestions)을 보여줍니다. 후자는 아직 선택·저장되지 않은 상품입니다. 별도 `Complete my outfit` 턴 없이 최신 보완품에서 `Add the first one` 또는 `Add to selection`을 사용합니다.

직접 구현한 범위는 카탈로그 처리(catalog pipeline), UI, 타입이 있는 도구(typed tools), 선택 검증(selection validation), 이미지 편집 연동(image-edit integration), 유용성 피드백(helpfulness feedback)입니다. AI 코딩 도구의 도움을 밝혀도 되지만 코드와 선택 이유는 발표자가 설명할 수 있어야 합니다. 삭제한 여정 측정(journey measurement) 화면은 시연하지 않습니다.

OpenAI Platform/APIs를 선택한 이유는 리테일러의 기존 UI·프로필·상품·가격·재고 규칙에 모델을 통합하기 위해서입니다. 별도 ChatGPT 화면으로 이동시키는 것이 아니라 같은 쇼핑 여정 안에서 추천·선택을 제공하고 행동 권한은 앱이 통제합니다. Codex는 개발 표면이지 이번 쇼핑객용 런타임이 아닙니다. 다른 제품보다 보편적으로 우월하다는 주장이 아니라 워크플로 적합성에 따른 선택입니다. 개발용 Copilot을 별도의 런타임 OpenAI 제품 표면으로 세지 않습니다.

원문 ranking 비교는 **현재 추천과 같은 eligibility**를 적용합니다. 순위만 원문 lexical 점수로 계산합니다. 필수 효능 판정에는 승인 속성이 사용될 수 있어 순수 enrichment 제거 실험은 아닙니다. 처음의 프로필 조건과 후속 요청 조건이 다르면 같은 조건으로 재실행해야 순위 비교가 됩니다.

## 3. 생성·검증·게시의 증거

현재 라이브 카탈로그(live catalog)의 처리 결과는 **240개 중 232개 완료(completed), 8개 격리(quarantined)**입니다. 격리 레코드는 카탈로그에서 없어진 것이 아니라 원문 전용(source-only)으로 남으며, 해당 보강 속성은 추천 근거로 쓰지 않습니다. 완료된 상품도 승인된 속성(accepted attributes)만 사용합니다. 사람 검토(human review)는 별도 단계이며 발표자가 확인한 **시연 상품 범위**에만 해당합니다.

게시 버전(publication version)과 검색 색인 버전(index version)은 `f2fc3913-5719-47c7-90e7-0b7bc79d5453`으로 일치합니다. 이는 9월 23일 점검 스냅샷이지 앞으로도 같은 상태라는 보장이 아닙니다. 근거는 `data/runtime/live-enrichment-20260923.log`와 카탈로그 상태입니다.

아래 문장은 그대로 유지합니다.

> These attributes were generated using OpenAI, then checked by a second model against the original product description, and reviewed by me for the demo products.

발표에서는 실제 검토한 상품의 `Why this match`를 열고 원문 인용, 승인 판단과 게시 속성을 보여줍니다. “Helps shed light drizzle.”는 약한 비 대응의 근거이지 방수 수치의 근거가 아닙니다. 슬라이드의 문장은 이 원칙을 설명하는 예시이며 특정 live 응답의 캡처가 아닙니다.

독립 검증(independent validation)은 생성과 별도 모델·호출로 원문 지지를 검사하는 것이며 OpenAI 인증이나 정확도 보장은 아닙니다. 모델 간 상관 오류(correlated error), 원문 오류, 과장 가능성은 남습니다. 게시 시 스키마·ID·인용·누락을 결정적으로 검사하고, 사람 검토는 시연 상품에 대해 별도로 확인합니다. 준비된 적대적 후보(adversarial candidate)를 실제 모델이 생성한 환각처럼 소개하지 않습니다.

현재 녹화 환경에 올바른 run/publication/index가 로드되어 있는지 확인하는 것은 **완료한 작업을 부정하는 것이 아니라 실행 환경 점검**입니다. source-only 레코드에 완료형 문구를 적용하지 않습니다.

## 4. 랭킹 확인·선택·실패 복구(Ranking, selection & recovery)

검색 결과 카드의 상품명 옆 **`Ranking scores`**를 열면 해당 상품의 의미 유사도(semantic similarity), 어휘 일치(lexical matching), 의도(intent), 계절(season), 프로필(profile), 고정 인기도(fixed popularity), 가중 합계(weighted total)가 소수 셋째 자리까지 표시됩니다. 응답에 없는 신호는 표시하지 않습니다. 이 값은 점수이지 모델 신뢰도(confidence)나 정확도(accuracy)가 아닙니다.

상단 근거 패널의 **`1 · How matches are ranked`**는 기본 가중치(default weights)를 따로 보여줍니다. 의미 40%·어휘 20%·의도 20%·계절 10%·프로필 5%·인기도 5%이며, 비활성 신호(inactive signals)를 제외한 후 나머지를 재정규화(re-normalization)하므로 항상 여섯 기본 비율을 그대로 적용하는 것은 아닙니다. 상품별 0–1 점수와 백분율 가중치를 구분합니다.

비교 칩·비교표는 UI에서 제거됐으며 `compare_products`도 에이전트 허용 목록에서 제외했습니다. 비교 요청에는 서버가 작성한 미지원 안내와 기존 카드·`Why this match` 확인 방법을 표시합니다. 비교표를 보여줬다고 주장하거나 선택을 변경하지 않습니다. 내부 비교 헬퍼는 기존 테스트용으로 남지만 공개 비교 API나 채팅 도구는 아닙니다.

조건이 바뀌면 기존 선택을 남겨두되 예산·사이즈·필수 색상·효능과의 충돌을 표시합니다. 기존 확인과 비공개 착장 결과는 무효화됩니다. 다른 상품으로 교체하거나 예외를 명시적으로 수락해야 새 preview를 요청할 수 있습니다. 품절/삭제된 variant는 예외 수락으로 통과할 수 없습니다.

결과가 없으면 한 가지 조건 변경으로 실제 상품이 생기는 대안과 상품 수를 보여줍니다. 사용자 클릭 전에는 조건을 바꾸지 않으며 사이즈를 자동 완화하지 않습니다. 보완품은 midlayer·pants·accessory 중 최대 두 개, 다른 카테고리로 제안하며 보유/선택 상품을 제외합니다. 신발 추천은 구현되어 있지 않습니다.

5분 영상에서 모든 예외를 시연할 필요는 없습니다. 예외 흐름을 보여줄 때에는 이미지 결과를 유지하려는 메인 경로와 섞지 않습니다. 조건 변경은 이미지를 지우는 것이 정상입니다.

## 5. 이미지 입력과 보존 경계

고정 가상 성인 전신사진은 미리 생성한 **공개 지속 자산**입니다. 화면 표시나 reset으로 인물을 생성하지 않습니다. 카드의 선택 색상 상품 이미지와 동일한 bytes를 인물 사진과 함께 Images edits에 전달합니다.

검색 중 캐시가 없는 색상별 상품 편집(color edit)은 자동으로 백그라운드 실행될 수 있습니다. 착장은 대화에서 **`Show the try-on preview`를 명시적으로 요청**합니다. 별도 생성 버튼은 없습니다. 모든 이미지 호출이 이 요청 뒤에만 발생한다고 설명하지 않습니다. 녹화 전 정확한 상품/색상 참조를 준비하고 사전 생성 자산(prepared assets)이라고 밝힙니다.

화면은 준비된 참조 개수·진행 상태·실제 경과 시간을 보여주며 완료 시간을 예측하지 않습니다. 결과는 시각적 참고일 뿐 실제 체형·핏·측정값·정확한 상품 외관을 보장하지 않습니다. 실제 구매자 전신사진 업로드는 동의하에 가능한 향후 UI 경험이며 현재 UI에는 없습니다. 레거시 업로드 API의 동의 검사는 유지됩니다.

착장 결과는 세션 전용 RAM에 보관하고 요청 후 15분에 만료됩니다. 제거·조건/선택 변경·초기화·재시작으로 접근이 사라집니다. 상품 색상 자산(product-color assets)은 지속 캐시로 재사용하지만, 비공개 착장의 이전 완료 결과(completed result)를 새 요청에 재사용하는 캐시는 구현되지 않았습니다. 같은 요청 ID의 중복 방지(deduplication)와 완료 결과 캐시는 다릅니다. 로컬 삭제가 제공자·브라우저의 모든 복사본 삭제를 보장하지는 않습니다.

운영 한도는 세션당 신규 이미지 작업 5개와 UTC 일일 runtime 이미지 예약 한도(기본 100)입니다. 색상·코디·착장·레거시 인물 호출이 공유하며 실패/과금 불명 호출도 예약 횟수에 포함합니다. cache 조회는 제외합니다. CLI 일괄 생성/smoke와 text·embedding·moderation 비용은 포함하지 않으므로 달러 예산이 아닙니다.

## 6. 데모 저장(Demo save)과 피드백(Feedback)

`Your trail selection`은 읽기 전용 요약(read-only summary)으로 실제 옵션·가격·세금/배송 전 합계를 보여줍니다. $200은 재킷 예산이며 전체 코디 예산이 아닙니다. 채팅에서 `Save this to the demo cart`를 전송하면 내부 도구 `confirm_selection`이 재고·선택 버전·충돌을 검사한 뒤 상단 아이콘의 상품 수만 갱신합니다. 별도 저장 버튼·장바구니 화면·서버 장바구니·주문·결제는 없습니다. 예외 승인 문구는 `Keep these exceptions and save to the demo cart`이며 재고 부족은 승인할 수 없습니다.

저장 후 채팅에서 `Yes, that helped` / `Not yet`로 유용성 피드백(helpfulness feedback)을 남깁니다. 저장과 피드백은 순차적인 두 턴이며 3:25–3:45의 20초를 배정했습니다. 피드백은 동일한 선택 버전(selection revision)당 한 번만 저장합니다. 피드백 자체를 매출·전환율·시간 절감의 증거로 설명하지 않습니다.

같은 옵션(variant)은 중복 집계하지 않습니다. 개수는 현재 브라우저 메모리(browser memory)에만 있으며 새로고침·여정 초기화·프로필 변경 시 0으로 돌아갑니다. 요구사항이나 선택 상품이 바뀌면 재검토가 필요하고 이전 비공개 미리보기는 해제되지만 이미 저장한 개수는 유지됩니다. 이미지 없이도 저장할 수 있습니다.

## 7. 전체 아키텍처와 API 연결(Overall architecture & API map)

슬라이드는 **원본 카탈로그 → 사전 준비 → 로컬 저장소**, **Next.js UI ↔ FastAPI 컴포넌트 ↔ 공유 저장소** 두 흐름입니다. API 이름을 해당 기능 상자 안에 직접 표시합니다. 하단 두 상자와 실제 발화에는 사전 검증의 최신성 관리 책임, SQLite·FAISS·단일 워커의 운영 한계를 넣었습니다. 상세 라우팅·모델명·호출 수는 질문 대응용 노트로 남깁니다.

| 컴포넌트(Component) | OpenAI API |
|---|---|
| 카탈로그 속성 생성·별도 검증(Catalog enrichment & judge) | Responses API |
| 카탈로그 색인·실시간 검색(Indexing & retrieval) | Embeddings API |
| 쇼핑 에이전트(Shopping agent) | Responses API + Moderations API |
| 이미지 파이프라인(Image pipeline) | Images API + Moderations API |
| 화면·선택 검증·저장소(UI, selection checks & stores) | 직접 호출 없음. Next.js는 FastAPI를 호출하고 검증은 로컬 코드가 수행 |
| CLI 사전 접근 확인(Preflight) | Models API · 매 쇼핑 요청의 일부가 아님 |

| 구성 | 실제 역할 |
|---|---|
| Next.js / FastAPI | UI, 세션, 명시적 행동, 도구 검증, 가격·eligibility·ranking 통제 |
| Responses | 대화/도구 실행 및 사전 속성 생성·별도 judge |
| Embeddings / FAISS | 게시 catalog와 질의 벡터 생성 / 로컬 검색 |
| SQLite | 상품 사실·게시 버전·세션·이미지 작업 메타데이터·이벤트 |
| Images | 상품 자산 생성, 색상 편집, 인물+상품 참조 편집 |
| Moderations | 텍스트와 지정된 이미지 입력 검사. 사실 정확도나 모든 출력의 후검사 보장은 아님 |
| Models | CLI preflight 모델 접근 확인. 매 쇼핑 요청마다 호출하지 않음 |

| 요청 경로(Request path) | 실제 처리와 호출 경계 |
|---|---|
| 우선순위 응답 칩(Priority chip) | 활성 질문·허용 값을 검사한 뒤 결정적 검색(deterministic search). Responses 0회지만 Moderation·필요 시 임베딩은 수행 |
| 자유 입력(Free text) | 같은 “Light rain protection”을 입력해도 모델 해석 경로. 칩과 호출 수가 같지 않음 |
| 경량 후속 요청(Light follow-up) | 공백 기준 10단어 이하 + 기존 결과/선택 + 키워드 일치 시 `gpt-5.4-mini` / 노력 `none` |
| 그 외 모델 요청(Standard turn) | `gpt-5.6-terra` / 노력 `low` |
| 성공한 단독 도구(Standalone tool) | `finish_turn=true`이면 서버가 결과 형식을 구성해 두 번째 Responses 호출 생략 가능 |
| 복구·복합 요청(Repair/composite request) | 추가 호출 가능. 재시도 가능한 제공자 오류·최종 응답 오류에서 제한적 상향(escalation); 모든 실패에 자동 상향하지 않음 |

도구 목록(tool allowlist)은 `search_products`, `recommend_complements`, `select_items`, `confirm_selection`, `generate_outfit`, `submit_feedback`입니다. `Choose the first one`, `Add the first one`처럼 인식되는 영문 순번 선택은 입력·카드 버튼 모두 모델 라우팅 전 결정적 경로로 처리합니다. 그 외 자유 입력은 모델이 해석합니다. 화면의 `small model` / `reasoning model` 배지는 모델 경로일 때만 표시됩니다. 결정적 우선순위·순번 선택에는 모델 배지가 없습니다. Moderation은 유지되며 함께 반환하는 보완품 검색에는 임베딩이 필요할 수 있습니다.

보강(enrichment)은 `gpt-5.6-terra` / low, 검증(judge)은 `gpt-6-astra` / medium, 임베딩은 `text-embedding-3-small`, 이미지는 `gpt-image-2.5-flare`, 안전성 검사는 `omni-moderation-latest`입니다. 상품 대표/색상 이미지는 816×816·low, 착장은 1024×1024·medium입니다. 이는 현 구성이지 모델 간 품질·속도 벤치마크(benchmark)의 결론이 아닙니다.

질의 벡터 캐시(query-vector cache)는 최대 128개·5분이며 가격·재고를 추천 결과 캐시로 저장하지 않습니다. 검색 점수의 의도(intent)·계절(season)은 승인 근거와의 일치 정도입니다. 근거 부재나 불일치에는 여전히 0이 정상일 수 있으므로 모든 상품의 양수 점수를 약속하지 않습니다.

사전 검증(preprocessing)은 실시간 작업을 줄이는 대신 원문 변경 시 재게시·재색인 책임을 만듭니다. 비교 기능은 채팅 도구나 UI로 제공하지 않습니다. 단일 워커(single worker)와 SQLite/FAISS는 로컬 데모이지 고가용성(high availability) 설계가 아닙니다. 이미지 비동기 작업도 내구성 큐(durable queue)가 아니며 재시작을 견디지 못합니다. 색인 오류는 표시된 어휘 검색 폴백(lexical fallback)으로 처리하고 라이브 실패를 재현 모드로 감추지 않습니다.

### 검증 결과를 설명하는 범위(Validation boundaries)

이번 자료 갱신에서 실제 우선순위 응답의 상품별 점수와 `Ranking scores` 표시, 근거 패널 기본 가중치, 비교 컨트롤 부재, 선택 상품·보완품 그룹 구분을 재현 모드(fixture mode)로 확인했습니다. 다만 선택 이후 390px 화면에서 가로 넘침(horizontal overflow)이 관찰되어 모바일 검증은 통과하지 못했습니다. 녹화는 데스크톱 1280px 이상으로 진행하며, 이 문서 갱신 작업에서 앱 레이아웃 자체를 변경하지 않았습니다.

**종단 간 테스트(End-to-End, E2E)**는 Playwright의 실제 브라우저 → Next.js → FastAPI 경로를 검사합니다. 선택·저장 개수·피드백·이미지 상태·모바일 등은 모의 모델 출력(fixture model outputs)으로 재현하며 실제 OpenAI 모델 호출을 검증하지 않습니다. 라이브 카탈로그 232/8 처리 및 게시·색인 일치는 별도 점검입니다. 어느 쪽도 실사용자 전환율·라이브 모델 정확도·이미지 품질·지연 성능을 입증하지 않습니다. 5분 배분은 대본의 목표이며 실제 API 대기를 포함한 리허설로 확인해야 합니다.

## 8. 사업 가정과 도입

| 항목 | 가정/계산 |
|---|---|
| 월 쇼핑객 | 100,000명 |
| 기준 전환율 / 평균 주문액 | 3.0% / $150 |
| 기준 월 매출 | 100,000 × 0.03 × $150 = $450,000 |
| 민감도 시나리오 | 전환율 3.0% → 3.1%, **0.1%p** 증가 |
| 추가 주문 / 매출 | 100건 / $15,000 월 gross revenue |

실측 uplift·예측치·이익이 아닙니다. 트래픽과 평균 주문액을 고정하고 반품과 추가 운영/API 비용을 제외했습니다. 객단가나 attach-rate 증가를 별도 가정 없이 중복 합산하지 않습니다.

사업 가설은 **관련 상품 발견 → 현재 조건에 맞는 선택 완료 → 실제 구매**입니다. 앞 단계가 개선되면 전환으로 이어질 수 있다는 가설이지 인과 효과를 이미 확인했다는 뜻이 아닙니다. Live API가 작동하는 것과 고객 가치가 입증되는 것은 별개입니다.

| 제안 KPI | 정의와 측정 범위 |
|---|---|
| 사용 시작률 | 도우미를 시작한 적격 세션 / 도우미에 노출된 적격 세션 |
| 선택 완료율 | 현재 선택을 확정한 세션 / 도우미를 시작한 세션. 주문 수가 아님 |
| 재사용률 | 다시 방문해 도우미를 재사용한 사용자 / 정한 기간에 재방문한 이전 사용자. 식별·보존 정책 선행 |
| 사업 지표 | 커머스 연동 후 무작위 처리군·대조군의 주문 / 적격 세션. 도우미를 열지 않은 노출 고객도 포함 |
| 보호 지표 | 근거 오류·유용성 응답률·p95 지연·완료 여정당 비용·관찰 가능한 불만과 반품 |

이 전체 퍼널은 **향후 파일럿 계측 제안**이며 현재 데모의 피드백이나 아이콘 개수만으로 측정되지 않습니다. 슬라이드의 `saves / started`는 현재 선택 확정 세션 비율의 축약 표기이지 저장된 상품 수나 결제 전환율이 아닙니다. 가상의 목표 수치를 실측처럼 추가하지 않습니다.

운영 계획(production plan)은 향후 제안입니다. Engineering/privacy가 인증·실재고·내구성 큐(durable queue)·접근/보존 정책·비용 제어를 맡고, merchandising은 속성 검토·오류 큐와 교육을 맡습니다. Analytics는 비교군(control group)과 표본·분모·중단 규칙을 정의하고 완료율·유용성·근거 품질·지연·완료 여정당 비용을 측정합니다. 결제/커머스 연동 후에야 실제 구매 전환을 연결합니다. 예약 용량(reserved capacity)은 측정된 수요·사용 가능한 모델·계약·부하 시험(load test)에 따라 검토할 향후 선택이지 지연이나 무제한 처리 보장이 아닙니다.

Head of Digital Commerce는 사전에 정한 가치·품질·단위 비용 조건을 보고 확장 여부를 승인합니다. 치명적 unsupported claim이나 품질 저하는 중단/rollback 사유입니다. 모든 API 사용량과 사전 준비비를 포함해 청구와 대조해야 합니다. runtime image-call cap 하나로 전체 비용을 통제한다고 설명하지 않습니다.

Voice-led shopping은 기존 제안대로 **향후 선택 사항**으로 남깁니다. 현재 데모 기능이나 API 구성에 넣지 않으며 고객 가치·접근성·개인정보·지연·비용을 검토한 뒤 판단합니다.
