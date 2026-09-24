# Trailshop — 5분 녹화 스크립트 (Five-Minute Recording Script)

**갱신일(Updated):** 2026년 9월 23일 · 최신 대화 중심 UI(conversation-first UI) 구현 기준
**목표 길이(Target):** 5:00 · 6:00을 절대 초과하지 않음
**언어(Language):** 영어 낭독 · 분당 약 135–145단어(words/minute)
**슬라이드(Slides):** [8장 HTML 덱](trailshop-shopping-assistant.html) · 갱신된 발표자 노트(presenter notes) 포함
**동선(Route):** 슬라이드 1 → 슬라이드 2 → 애플리케이션(application) → 슬라이드 7 → 슬라이드 8
**애플리케이션 구간:** 0:35–3:45 · 190초 · 전체 녹화의 63%
**형식(Format):** HTML 슬라이드와 녹화본. PDF 작업 흐름(workflow)은 사용하지 않음

**낭독(Say)** 아래의 인용문(blockquote)만 소리 내어 읽습니다. 조작(Actions), 체크포인트(Checkpoints), 대체 대사(alternative lines), 참고(Notes)는 **추가 내레이션이 아닙니다.** 슬라이드 3–6은 검토자(reviewer)를 위해 구현된 동작을 문서화한 자료이므로, 앱을 보여주는 대신 이 슬라이드를 읽어서는 안 됩니다. [최초 기획안](trailshop-demo-presentation.md)은 보관용이며 이번 녹화를 규정하지 않습니다.

## 녹화 원칙 (Recording contract)

- **고객(Customer):** 가상의 아웃도어 리테일러 Trailshop. **사용자(User):** 온라인 쇼퍼 Alex. **청중(Audience):** 디지털 커머스 총괄(Head of Digital Commerce) — 잠재적 사업 후원자(prospective business sponsor)로 설정.
- **단일 표면(One surface):** OpenAI 플랫폼/API. AI 코딩 보조(AI coding assistance)는 개발 보조 수단이지 두 번째 런타임 표면(runtime surface)이 아닙니다.
- **사전 처리 현황(Preparation status):** 현재 라이브 카탈로그(live catalog)는 240개이며, 보강 실행(enrichment run) 232개가 완료되고 8개는 격리(quarantine)되어 원문 전용(source-only)으로 남습니다. 게시·색인 버전(publication/index version)은 일치합니다. 사람 검토(human review)는 별도의 발표자 확인 사항이며 시연 상품에만 한정합니다.
- **본 시연(Main demonstration):** 텍스트 대화(typed conversation), 우선순위 질문, 점수 토글(score toggle), 구분된 선택 상품·보완품, 근거, 선택적 착장, 데모 개수와 피드백. 조건 충돌·결과 없음 대안은 유지됩니다. 비교 칩·비교표·에이전트 비교 도구는 제공하지 않으며 비교 요청에는 미지원 안내를 표시하고 선택을 변경하지 않습니다.
- **현재 화면(Current screen):** 상단 소개 영역(`Your next trail starts here.`) → 접힌 근거 패널(evidence panel) → 단일 대화 열(single conversation column). 별도 가을 배너는 없고 소개 영역의 `Autumn, considered.` 문구는 유지됩니다. 상품·선택 요약·미리보기는 대화 안에 표시되며 별도 우측 패널은 없습니다. 카드 버튼(card button)은 채팅 요청을 보내는 단축 조작(shortcut)입니다. 조작 지시의 “말한다”는 입력·전송 또는 응답 칩(reply chip) 선택을 뜻하며 음성 입력(speech input)은 아닙니다.
- **랭킹 표시(Ranking controls):** 각 검색 결과 카드의 상품명 옆 `Ranking scores`는 해당 상품의 0–1 신호 점수(signal score)와 가중 합계(weighted total)를 보여줍니다. 기본 가중치(default weight)는 근거 패널에 의미 유사도 40%·어휘 20%·의도 20%·계절 10%·프로필 5%·고정 인기도 5%로 별도 표시됩니다. 점수·가중치·신뢰도(confidence)·정확도를 혼동하지 않습니다.
- **이 UI에 미구현(Not implemented):** 별도 장바구니·결제 흐름(cart/checkout workflow), 실제 재고 연동(real inventory integration), 쇼퍼 사진 업로드(shopper photo uploads), 음성(voice), 착용감 예측(Fit Prediction). 장바구니 아이콘은 임시 개수 표시일 뿐 커머스 연동(commerce integration)이 아닙니다.
- **세 가지를 분리할 것:** ① 관측된 프로토타입 상호작용(observed prototype interactions), ② 사전 생성된 이미지·카탈로그 자산(pre-generated assets), ③ 가설적 사업 성과와 향후 프로덕션 계획(hypothetical business outcomes).
- **검증 범위(Validation boundary):** Playwright E2E는 실제 브라우저·화면·로컬 API를 모의 모델 출력(fixture model outputs)과 연결합니다. 실시간 라우팅 정확도(live routing accuracy), 추천·이미지 품질, API 지연을 입증하지 않습니다.
- **녹화 화면(Recording viewport):** 가로 1280px 이상의 데스크톱 화면을 사용합니다. 이번 확인에서 390px 선택 상품 화면의 가로 넘침(horizontal overflow)이 관찰됐으므로 모바일 준비 완료(mobile readiness)로 소개하지 않습니다.

## 녹화 전 점검 (Before recording)

| 점검 항목 | 요구 상태 |
|---|---|
| 모드(Mode) | `/api/health`가 의도한 라이브 모드(live mode)를 보고하는지 확인. 리플레이(Replay)는 명시적으로 시뮬레이션이며 라이브 모델 품질을 입증할 수 없습니다. |
| 새 세션(Fresh session) | Alex 계정과 `Reset journey`를 사용해 우선순위 질문과 상품 선택을 초기 상태에서 시작합니다. |
| 정확한 요청(Exact request) | 새 세션에서 `I need a jacket for hiking this fall.`을 전송한 뒤 우선순위 질문이 나타나면 `Light rain protection`을 클릭합니다. 두 턴을 0:50–1:35 안에 리허설하고, 사람이 검토한 데모 집합에서 유효한 결과를 확인합니다. 화면에 나타나지 않는 상품을 외우지 마십시오. |
| 근거와 색인(Evidence and index) | 시연 상품에 완료된 실행(completed run), 게시된 속성(published attribute), 원문 인용(source quotation)이 있고 현재 색인이 게시 내용과 일치하는지 확인. 라이브 모드 배너(banner)만으로는 그 무엇도 입증되지 않습니다. |
| 기준선(Baseline) | 원문 전용 질의(source-only query)를 리허설. 현재 적격성(eligibility)은 공유하지만 보조 랭킹(assisted ranking)은 공유하지 않습니다. 랭킹을 나란히 비교하려면 동일 의도(same intent)를 설정한 뒤 재실행. |
| 검토와 선택(Review and selection) | 첫 인라인 재킷 카드(inline jacket card)를 검토한 뒤 `Choose the first one`을 전송합니다. `Select this jacket` 버튼은 `Choose the first`를 보내는 대안입니다. 최신 제안 목록(latest offered list)이 바뀐 후에는 옛 카드를 사용하지 않습니다. |
| 보완 상품(Complements) | 재킷 선택 응답에 최대 2개 보완품이 바로 붙습니다. 최신 `Completes the outfit` 목록에서 `Add the first one`을 전송합니다. 보완품이 안 나온 경우가 아니면 `Complete my outfit` 턴을 추가하지 않습니다. |
| 이미지 준비(Image preparation) | 고정된 가상 인물 사진이 로드되고, 선택 색상에 해당하는 의류 참조 이미지가 준비되어야 합니다. 캐시되지 않은 색상을 준비하는 행위 자체가 이미지 API 호출을 발생시킬 수 있습니다. 준비된 자산임을 공개하십시오. |
| 이미지 타이밍(Image timing) | 한 번 리허설. 이 일정은 API 지연 시간(latency) 보장이 아닙니다. 인물을 재생성하거나 전체 카탈로그 배치(batch)를 실행하지 마십시오. |
| 최종 저장(Final save) | `Save this to the demo cart`와 `Yes, that helped`의 순차적 두 턴(sequential turns)을 20초 구간 안에서 리허설합니다. 각각의 응답을 기다리며 장바구니 화면은 열지 않습니다. |
| 녹화 위생(Recording hygiene) | 키(keys), 터미널(terminals), 개인정보가 화면에 노출되지 않도록 함. 1인칭 구축 주장("내가 만들었다")을 검증하고 코드와 트레이드오프(trade-offs)를 설명할 준비를 하십시오. |

비공개 가상 착용(try-on) 결과는 **요청 후 15분에 만료**되며, 항목 제거·요구사항 변경·선택 변경·API 재시작 시 사라집니다. 이전 결과를 보여줄 때는 접근 가능 여부를 확인하고 **준비된 자산임을 밝혀야** 합니다. 고정 공개 인물과 색상별 상품 이미지 캐시(product-color image cache)는 지속되지만, 새 요청에 이전 비공개 착장 결과를 완료 캐시(completed-result cache)로 재사용하지는 않습니다.

## 진행 순서 (Run of show)

| 시각 | 화면 | 목적 |
|---|---|---|
| 0:00–0:20 | 슬라이드 1 · 고객과 문제 | 고객, 청중, 사용자, 유의미한 문제 제시 |
| 0:20–0:35 | 슬라이드 2 · 이전과 이후 | API 적합성과 직접 구축한 소유권 |
| 0:35–0:50 | 앱 · 원문 전용 랭킹 | 기존 경험과 비교의 한계 |
| 0:50–1:35 | 앱 · 요청, 우선순위 선택, 후보 목록 | 추가 질문에 light rain protection을 선택하고 근거 기반 추천 확인 |
| 1:35–1:55 | 앱 · 추천 카드 | 추천 근거를 확인하고 재킷 선택 |
| 1:55–2:15 | 앱 · 보완 상품과 요약 | 주문이 아니라 아웃핏을 완성 |
| 2:15–2:30 | 앱 · 대화 내 인물과 의류 참조 | 선택적 이미지 편집 요청 |
| 2:30–3:00 | 앱 · 근거 드로어(evidence drawer) | 편집이 도는 동안 사전 보강 설명 |
| 3:00–3:25 | 앱 · 대화 내 시각화 결과 | 참조 기반 편집과 시각적 한계 설명 |
| 3:25–3:45 | 앱 · 저장 표시와 피드백 | 두 번의 대화 턴 확보, 장바구니 시연 제외 |
| 3:45–4:10 | 슬라이드 7 · 전체 아키텍처(Overall Architecture) | 컴포넌트별 OpenAI API 표시 |
| 4:10–4:30 | 슬라이드 8 · 가치와 프로덕션 도입 | 측정된 상승이 아닌 정량화된 가설 |
| 4:30–5:00 | 슬라이드 8 · 계속 표시 | 실용적 파일럿, 소유권, 확장 게이트 |

## 01 · 0:00–0:20 — 고객 / 문제 (Customer / Problem)

**화면(Show):** 슬라이드 1, "Customers shop for a purpose. Not a SKU."

**낭독(Say):**

> This demo is for Trailshop, a fictional outdoor retailer. For its Head of Digital Commerce, this prototype explores a simpler shopping journey: helping Alex turn a hiking need into a shortlist, with evidence behind each recommendation.

**체크포인트(Checkpoint):** 0:20까지 슬라이드를 넘깁니다. 임원은 청중이고 쇼퍼는 사용자입니다. 완료된 고객 인터뷰(customer interviews), 측정된 노력 감소(measured effort reduction), 사용성 연구(usability study)가 있었던 것처럼 들리게 하지 마십시오.

## 02 · 0:20–0:35 — 제안 해결책 (Proposed Solution)

**화면(Show):** 슬라이드 2, "Less searching. More deciding."

**낭독(Say):**

> Before, Alex would translate the need into keywords and assemble the answer alone. Now, Alex just asks in one conversation, and the agent understands the context and intent behind the request to surface the right products, with evidence-backed choices. Let’s use it.

**조작(Action):** 0:35까지 앱으로 전환합니다. 슬라이드 3–6은 보조 자료이며 본 녹화의 정차 지점이 아닙니다.

## 03 · 0:35–0:50 — 기존 경험 (Before Experience)

**화면(Show):** 상단 소개 영역 아래·대화창 위의 `How this recommendation was built` → `3 · Source-only ranking: the same eligible catalog`.

**조작(Action):** `Search raw catalog`로 `hiking jacket fall light rain`을 검색합니다. 실제 상품명과 설명을 보여준 뒤 패널을 접습니다.

**낭독(Say):**

> This screen searches only raw product names and descriptions, not the AI-enriched attributes. It’s the old way: reading the source text manually to search and compare.

**참고(Note):** 적격성은 승인된 필수 혜택 근거(approved required-benefit evidence)에 좌우될 수 있습니다. 최초 화면은 Alex의 초기 제약 조건을 사용하므로, 동일 의도 기준으로 랭킹을 비교하려면 요청 이후 다시 실행하십시오.

## 04 · 0:50–1:35 — 요청 / 추가 질문 / 후보 목록 (Request / Clarification / Shortlist)

**조작(Action):** 새 Alex 세션에서 다음 문장을 붙여넣고 전송합니다.

```text
I need a jacket for hiking this fall.
```

**대기 중 낭독(Say while waiting):**

> I’ll ask for a jacket for hiking this fall. All shopper and catalog data here is synthetic, enriched and illustrated using OpenAI APIs.

**조작(Action):** `What matters most for your hike?` 질문을 기다린 뒤 `Light rain protection` 응답 칩(reply chip)을 클릭합니다. 본 녹화에서는 직접 입력하지 않습니다. 칩은 `priority_choice:true`를 보내 검증된 결정적 경로(deterministic path)로 처리되어 Responses 호출이 0회입니다. 자유 입력(free text)은 모델이 해석합니다. 두 경로 모두 라이브 모드에서 입·출력 안전성 검사(Moderation)를 유지합니다.

**선택하며 낭독(Say as you choose):**

> The agent asks which priority matters most. I’ll choose light rain protection.

**조작(Action):** 결과가 나타나면 구매 가능한 옵션(available variant), 가격, 추천 이유를 가리킵니다. 첫 상품명 옆의 `Ranking scores`를 잠깐 열어 해당 상품의 점수(score)를 보여준 뒤 접습니다. 백분율 가중치(weight)는 이 점수 목록이 아니라 근거 패널의 `1 · How matches are ranked`에 있습니다.

**낭독(Say):**

> The agent checks size, stock and budget. The ranked shortlist includes source-backed reasons; this toggle shows each product’s score breakdown.

**체크포인트(Checkpoint):** 두 턴과 후보 목록 확인을 1:35까지 마칩니다. 추가 질문과 선택은 선택적 부가 시연이 아니라 본 녹화 흐름입니다. 질문이 나타나지 않으면 새 세션으로 초기화해 리허설하고, 선택지가 나타난 것처럼 연기하지 마십시오. 3개 미만이 적격이면 그 사실을 말하십시오. `lexical-fallback`이 표시되면 해당 요청이 의미 검색(semantic retrieval)에 성공했다고 주장하지 마십시오.

## 05 · 1:35–1:55 — 추천 근거 확인 및 선택 (Review & Select)

**조작(Action):** 순번 아래 커진 상품 이미지와 첫 카드의 `Why we recommend it`, 가격·사이즈·색상을 가리킨 뒤 `Choose the first one`을 입력·전송합니다. `Select this jacket` 버튼도 같은 순번 메시지를 보내며 `Or say…` 안내가 버튼 옆에 있습니다. 비교 칩·비교표는 현재 UI에 없습니다.

**낭독(Say):**

> The inline card shows the reason, price and available option. I’ll type “choose the first one.” The agent resolves that against the latest offered list, rather than guessing a product.

**체크포인트(Checkpoint):** 1:55까지 재킷을 선택합니다. 보완 상품 추천은 선택된 재킷을 기준으로 시작됩니다.

## 06 · 1:55–2:15 — 선택 완성 (Complete the Selection)

**조작(Action):** 같은 응답에서 커진 제목 `Now in your selection`과 강조된 `Completes the outfit` 블록을 구분해 보여줍니다. 전자는 이미 선택한 상품, 후자는 추가 제안입니다. 최신 보완품 목록에서 `Add the first one` 또는 `Add to selection`을 사용한 뒤 `Your trail selection`의 색상·사이즈·가격·소계(subtotal)를 보여줍니다.

**낭독(Say):**

> Complementary picks arrive with the selection, excluding owned and selected products. Each one matches the same hiking activity and complements the jacket’s color, chosen from a different category. I’ll add the first one.

**참고(Note):** 미드레이어, 팬츠, 액세서리가 지원됩니다. 신발이나 특정 품목을 약속하지 마십시오. 카탈로그 사이즈는 착용감 추천(fit recommendation)이 아닙니다. 보완품은 추가하기 전까지 제안(suggestion)이며 저장된 장바구니가 아닙니다.

## 07 · 2:15–2:30 — 이미지 편집 시작 (Start the Image Edit)

**조작(Action):** 대화 내 `Try-on preview`에서 고정 인물과 모든 상품 참조가 준비됐는지 보여줍니다. 칩 또는 텍스트로 `Show the try-on preview`를 **한 번만** 전송합니다. 이 요청은 착장 작업(try-on job)을 승인합니다. 캐시되지 않은 상품 색상 편집(color edit)은 검색 중에도 시작될 수 있으므로 모든 이미지 작업의 시작 조건으로 일반화하지 않습니다.

**낭독(Say):**

> Here’s Alex’s trail selection so far. Let’s try it on: I explicitly request the try-on, which edits the prepared fictional-person photo using the selected garments in their chosen colors. This takes a moment to generate, so I’ll explain the evidence behind it while we wait.

**체크포인트(Checkpoint):** 2:30까지 대기열 등록 또는 실행 중 상태여야 합니다. 인물은 재생성되지 않습니다. 결과물은 아웃핏 시각화(outfit visualization)라고 부르고, Alex의 신체를 재현한 것이라고 하지 마십시오.

## 08 · 2:30–3:00 — 근거 확인 (Inspect the Evidence)

**조작(Action):** 이미지가 생성되는 동안, 검토 완료된 데모 상품에서 `Why this match`를 엽니다. 변경되지 않은 원문(unchanged source)과 실제 게시된 속성 하나를 그 인용문 및 판정 결과(judge decision)와 함께 보여줍니다.

**낭독(Say):**

> These attributes were generated using OpenAI, then checked by a second model against the original product description, and reviewed by me for the demo products. Those products are published and searchable. Here is the exact sentence it quoted, and why it recommended these pants. That separate check is an extra safeguard.

**조작(Action):** 근거 위에서 잠시 멈춘 뒤 드로어를 닫습니다. **첫 문장은 토씨 그대로** 유지하십시오.

**참고(Note):** 독립적인 모델 검증(independent model validation)을 OpenAI의 인증(certification)과 동일시하지 마십시오. 적대적 검증 섹션(adversarial section)은 준비된 테스트 주장과 관측된 실시간 판정을 구분합니다. 거절 사례를 지어내거나 모든 카탈로그 상품이 사람 검토를 거쳤다고 암시하지 마십시오.

## 09 · 3:00–3:25 — 시각 결과 / 이미지 파이프라인 (Visual Result / Image Pipeline)

**조작(Action):** 준비되었다면 완료된 결과를 보여줍니다. 선택된 의류를 가리킨 뒤, 화면에 표시된 라벨 `AI virtual try-on — visual reference only; appearance may differ. No size or fit prediction.`을 가리킵니다. 면책 고지(disclaimer)는 라벨이 담당하므로 구두로 말할 필요가 없습니다. 미리보기 화면을 유지한 뒤 선택 요약(selection summary)으로 돌아갑니다.

**낭독(Say):**

> Let’s look at the finished outfit shot. This uses Images edit with multiple inputs: the person photo and selected garment references. The prompt maps each reference to its variant and color. Moderation screens the prompt and input images.

**체크포인트(Checkpoint):** 3:25까지 최신 대화 입력창으로 돌아옵니다. 작업이 아직 실행 중이면 아래 복구 대사(recovery lines)로 대체하십시오. 완료되지 않은 이미지를 완료된 것처럼 설명하지 마십시오.

**참고(Note):** 면책 고지는 말하는 것이 아니라 보여주는 것입니다. 모든 이미지 작업은 라벨을 함께 저장하며, 가상 착용(try-on)과 샘플 인물(sample person) 출력은 비공개 종류(private kind)로 분류되어 디스크가 아닌 메모리에 15분간만 보관됩니다. 착용감 예측(fit prediction), 정확한 색상, 실제 사용자 신체라고 주장하지 마십시오.

## 10 · 3:25–3:45 — 저장 / 피드백 (Save / Feedback)

**조작(Action):** `Save this to the demo cart`를 전송해 상단 아이콘의 갱신된 상품 수를 잠깐 보여주고, 어시스턴트의 유용성 질문에 시연 내용과 맞으면 `Yes, that helped`로 답합니다. 별도 장바구니 화면은 구현하지 않았으므로 열지 않습니다.

**낭독(Say):**

> I save the selection through chat, then answer the feedback question. The cart icon only counts saved options; there is no checkout.

**체크포인트(Checkpoint):** 3:45에 슬라이드 7로 전환합니다. 주문을 흉내 내거나 별도 장바구니 시연을 추가하지 마십시오. 개수는 새로고침·여정 초기화·프로필 변경 시 초기화됩니다.

## 11 · 3:45–4:10 — 아키텍처 / API 연결 (Architecture / API Map)

**화면(Show):** 슬라이드 7, “One application. Clear API responsibilities.” 위쪽 사전 처리(offline preparation)와 Next.js → FastAPI → 로컬 저장소(local stores) 흐름을 가리킵니다. 각 컴포넌트 안의 OpenAI API 표시를 설명합니다.

**낭독(Say):**

> Let's walk through the architecture behind this. The Next.js interface calls our FastAPI backend. The Responses API powers the shopping agent and separate catalog checks. The Embeddings API supports indexing and retrieval. The Images API generates assets and edits selected references, with the Moderations API screening text and image inputs. SQLite, FAISS and local image storage hold the data; selection rules stay in application code.

**참고(Note):** API 이름은 별도 상세 목록 대신 사용 컴포넌트(component) 안에 표시합니다. Next.js와 선택 검증(local selection checks)은 OpenAI를 직접 호출하지 않으며 에이전트가 도구를 호출합니다. Models API는 하단에 CLI 사전 확인(preflight)으로만 표시합니다. 라우팅·호출 수·모델 ID·E2E 범위는 보조 노트로 옮깁니다. Models가 매 요청마다 실행되거나 모든 출력 이미지를 사후 검사(post-screening)한다는 뜻이 아니며 Moderation이 사실성을 보장하지도 않습니다.

**라우팅(Routing) — 질의응답용:** 공백 기준 10단어 이하, 기존 추천/선택 상태 존재, 후속 요청 키워드(follow-up keyword) 일치라는 조건을 모두 만족하면 `gpt-5.4-mini` / 추론 노력 `none`을 씁니다. 그 외에는 `gpt-5.6-terra` / `low`입니다. 코드 기반 휴리스틱(heuristic)이지 최적 모델을 입증한 벤치마크가 아닙니다. 재시도 가능한 제공자 오류(retryable provider error) 또는 최종 응답 형식 오류가 있을 때 제한된 복구 루프(repair loop) 안에서 경량 턴을 상향할 수 있으며, 모든 실패가 상향(escalation)을 유발하지는 않습니다. 실제 `small model` / `reasoning model` 배지에 마우스를 올리면 모델을 확인할 수 있습니다. 결정적 우선순위 칩에는 이 배지가 표시되지 않습니다.

**호출 절감(Call reduction):** 성공한 단독 도구(standalone tool)가 `finish_turn=true`를 반환하면 Responses 1회 뒤 서버가 최종 화면 데이터를 구성합니다. 복합 요청·복구는 추가 호출이 가능합니다. 우선순위 칩의 Responses 0회는 전체 API 0회가 아닙니다. Moderation과 필요 시 질의 임베딩(query embedding)은 실행됩니다. 질의 벡터 캐시(query-vector cache)는 최대 128개·5분이며 상품 결과·가격·재고·세션 상태를 추천 결과로 캐시하지 않습니다.

**모델 구성(Model configuration):** 기본 대화/보강 `gpt-5.6-terra` / `low`, 독립 검증 `gpt-6-astra` / `medium`, 검색 `text-embedding-3-small`, 안전성 검사 `omni-moderation-latest`, 이미지 `gpt-image-2.5-flare`. 상품 대표/색상 이미지는 816×816·low, 가상 착용은 1024×1024·설정된 medium입니다. 녹화 전에 실제 설정을 재확인합니다.

**검증(Validation):** Playwright E2E는 브라우저 → Next.js → FastAPI를 모의 모델 출력(fixture model outputs)과 연결해 선택·개수·피드백·이미지 상태·모바일 표시를 검사합니다. 실시간 언어 이해·품질·지연의 근거는 아닙니다. 라이브 카탈로그 게시·색인 확인은 별도 증거이며 최종 녹화 전 과금 가능한 라이브 리허설(live rehearsal)이 필요합니다.

**범위(Scope):** `compare_products`는 에이전트 허용 목록에서 제외했습니다. 비교 요청에는 미지원 안내와 기존 카드·`Why this match` 확인 방법을 표시하며 선택을 변경하지 않습니다. 내부 비교 헬퍼는 기존 테스트용으로 남지만 공개 비교 API나 채팅 도구는 아닙니다.

**선택 단축 경로(Selection shortcuts):** `Choose the first one`, `Add the first one`처럼 인식되는 영문 순번 선택은 입력·카드 버튼 모두 모델 라우팅 전 결정적 경로로 처리하며 최신 제안 목록을 참조합니다. 그 외 자유 입력은 모델이 해석합니다. 이 선택 턴에는 모델 배지가 없지만 Moderation은 실행되며 함께 반환하는 보완품 검색에는 임베딩이 필요할 수 있습니다.

## 12 · 4:10–4:30 — 사업 가치 (Business Value)

**화면(Show):** 슬라이드 8. 가치 가설(callout)과 3단계 파일럿 카드를 가리킵니다.

**낭독(Say):**

> The primary business outcome is improved conversion, with attach rate as a secondary opportunity. Because this is a fictional customer, I treat those as hypotheses rather than claimed results. In a controlled pilot, I would compare completed selections and conversion against the baseline experience you saw at the beginning.

**참고(Note):** 특정 매출 수치나 전환율 상승폭을 주장하지 마십시오. 전환은 파일럿에서 측정할 가설이며, 이 프로토타입에서 나온 결과가 아닙니다.

## 13 · 4:30–5:00 — 프로덕션 / 도입 (Production / Adoption)

**화면(Show):** 슬라이드 8의 3단계 파일럿. 이 슬라이드에 머무릅니다.

**낭독(Say):**

> Production needs authentication, security and live inventory, plus durable image jobs. We would evaluate reserved capacity against measured demand. A controlled pilot would compare completion, helpfulness, quality and cost. The goal is a better shopping decision.

**체크포인트(Checkpoint):** 5:00에 멈춥니다. 추가 요약(recap)은 없습니다.

**확장성과 보안(Scale and security) — 질의응답용:** 프로토타입은 SQLite/FAISS와 로컬 워커 1개입니다. 프로덕션에는 무상태 API(stateless API), 관리형 데이터베이스·벡터 서비스, 내구성 이미지 큐(durable image queue)가 필요합니다. 예약 용량(reserved capacity)은 실제 모델 지원·계약·측정 수요·부하 시험(load test)에 따라 검토할 미래 옵션이지 지연 또는 스로틀링 방지 보장이 아닙니다. 인증·세션 바인딩·테넌트 격리·관리형 시크릿·최소 권한 키 교체·TLS·데이터 최소화·보관 제한·감사 로깅을 추가해야 합니다.

**프로덕션 세부사항 — 질의응답용(Production detail — for questions):** 머천다이저(merchandiser)와 지원 인력에게 근거 검토와 오류 큐(error queue) 처리를 교육합니다. 제한된 카테고리 파일럿 전에 코호트(cohort), 표본 크기(sample size), 분모(denominators), 품질·지연·비용 임계값(thresholds), 중단 규칙(stopping rules)을 정의합니다. 실제 전환 측정에는 커머스 연동이 필요합니다. 텍스트·임베딩·모더레이션·이미지 전반의 과금 사용량(billed usage)을 상각된 카탈로그 준비 비용까지 포함해 대사(reconcile)해야 하며, 런타임 이미지 예약만으로는 총비용 통제가 되지 않습니다.

## 선택 경로 — 추가 시간이 아닌 대체 (Optional paths)

| 대안 | 무엇을 대체하는가 | 조작과 경계 |
|---|---|---|
| 요구사항 변경 / 결과 없음 | 이미지 시연을 생략하는 대체 테이크의 3:00–3:25 일부 | `Keep the jacket under $1` 전송 후 선택 유지·예산 충돌·미리보기 검토 필요 안내를 보여줍니다. 제시된 예산 대안 칩(alternative chip)을 선택하면 그 조건만 바뀝니다. 이전 비공개 미리보기·확정을 지우므로 본 이미지 공개 경로와 섞지 않습니다. |
| 명시적 예외(Explicit exception) | 리허설된 대체 테이크의 선택 검토 구간 일부 | `Keep these exceptions and save to the demo cart`를 전송하기 전에 충돌을 설명합니다. 재고 부족은 재정의(override)할 수 없습니다. 숨겨진 완화(hidden relaxation)는 없습니다. |

## 복구 대사 — 해당 본 내레이션을 대체 (Recovery lines)

| 상황 | 정직한 조치 / 대체 대사 |
|---|---|
| 이미지가 아직 실행 중 | 실제 경과·상태를 화면에 유지합니다. "The image is still running. Alex can finish choosing without it." 동일 워크플로의 검증된 이전 결과는 사용 가능할 때만, **준비된 자산임을 명시적으로 밝히고** 보여주십시오. |
| 편집에서 대기 시간 제거 | `Generation wait shortened` 자막을 넣습니다. "The generation wait has been shortened in this recording." 준비된 결과를 현재 호출인 것처럼 위장하지 마십시오. |
| 이전에 생성된 라이브 결과 | "This image was generated earlier using the same selection and OpenAI image-editing workflow." 이번 테이크에서 새로 생성된 것처럼 들릴 여지를 제거합니다. |
| 리플레이 모드(Replay mode) | 이 Live 녹화를 중단하고 Live 설정·리허설을 확인합니다. 별도 표시한 시뮬레이션도 최종 Live 증거를 대체하거나 Live 대본으로 설명할 수 없습니다. |
| 상품에 게시된 근거가 없음 | 그 상태를 보여줍니다. "This product has source-only evidence." 해당 레코드에 데모 상품 완료 주장을 적용하지 말고, 최종 테이크에서는 실제로 검토된 상품을 선택하십시오. |
| 검색 결과 없음 | "Nothing meets these constraints. These alternatives were checked against the catalog; nothing changes until I choose." 일치 항목을 지어내지 마십시오. |
| 색인 사용 불가 | 폴백(fallback) 라벨을 유지합니다. "This request is using lexical fallback, not a successful semantic-search run." |
| 제공자 / 안전 오류 | 오류를 그대로 보여줍니다. "The request did not complete; the application reports it rather than fabricating a result." 무작정 재시도하거나 실패를 성공으로 설명하지 마십시오. |

**약 4:50–5:00**을 목표로 리허설하십시오. 모든 기능을 과시하기보다 실제 쇼핑 워크플로, 명확한 근거 레코드 하나, 최종 결정을 우선하십시오. 공개된 폴백은 정확성을 지켜주지만, **제대로 동작하는 최종 시연을 준비하는 것을 대신할 수는 없습니다.** 제출물은 슬라이드와 녹화본뿐이며, 이 스크립트와 한국어 노트는 발표자 보조 자료입니다.
