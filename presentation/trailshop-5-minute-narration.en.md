# Trailshop — Five-Minute Narration & Pacing Sheet

**Source:** [English recording script](trailshop-5-minute-recording-script.en.md) · 23 September 2026, current implementation snapshot
**Target:** 5:00 · never exceed 6:00 · planning rate: 140 words/minute
**Estimate:** 482 spoken words ≈ **3:27 speech**, leaving **1:33** for operation, pauses and reading.

Word counts use whitespace-separated tokens; timings are arithmetic estimates, not a measured live rehearsal. Operation can overlap narration. Remaining room is not an API latency guarantee. Read only the blockquotes aloud.
Record at a desktop width of at least 1280px. Current selected-item content showed horizontal overflow at 390px; mobile readiness is not verified.

## Pacing map

| Seg | Window | Budget | Words | Speech | Room |
|---|---|---:|---:|---:|---:|
| 01 | 0:00–0:20 | 20s | 33 | 14.1s | 5.9s |
| 02 | 0:20–0:35 | 15s | 28 | 12.0s | 3.0s |
| 03 | 0:35–0:50 | 15s | 28 | 12.0s | 3.0s |
| 04 | 0:50–1:35 | 45s | 52 | 22.3s | 22.7s |
| 05 | 1:35–1:55 | 20s | 30 | 12.9s | 7.1s |
| 06 | 1:55–2:15 | 20s | 31 | 13.3s | 6.7s |
| 07 | 2:15–2:30 | 15s | 19 | 8.1s | 6.9s |
| 08 | 2:30–3:00 | 30s | 59 | 25.3s | 4.7s |
| 09 | 3:00–3:25 | 25s | 43 | 18.4s | 6.6s |
| 10 | 3:25–3:45 | 20s | 22 | 9.4s | 10.6s |
| 11 | 3:45–4:10 | 25s | 50 | 21.4s | 3.6s |
| 12 | 4:10–4:30 | 20s | 37 | 15.9s | 4.1s |
| 13 | 4:30–5:00 | 30s | 50 | 21.4s | 8.6s |
| | **Total** | **300s** | **482** | **206.6s** | **93.4s** |

**Rehearsal priority:** 04 contains the initial request and priority choice; 05/06 each add a model-mediated selection; 10 contains save plus feedback. Send actions early and narrate while they run. The image is requested at 2:15–2:30, but its completion by 3:00 is not guaranteed. Use a disclosed recovery if needed, never a fake completed state.

Slides 1–2 → app 0:35–3:45 (190 seconds) → slides 7–8. Slides 3–6 are supporting material. Comparison controls/table have been removed from the UI; the retained backend tool is not part of this demo.

## 01 · 0:00–0:20 — Customer / Problem

**Screen / actions:** Start on slide 1, “Customers shop for a purpose. Not a SKU.” Advance by 0:20. This is a problem hypothesis, not completed customer research.

**Say:** ~14.1s. Remaining room: ~5.9s total for operation, reading and pauses.

> Trailshop is a fictional outdoor retailer. For its Head of Digital Commerce, this prototype explores a simpler shopping journey: helping Alex turn a hiking need into a shortlist, with evidence behind each recommendation.

## 02 · 0:20–0:35 — Proposed Solution

**Screen / actions:** Show slide 2. Switch to the app by 0:35; skip supporting slides 3–6. This is typed chat, not speech input.

**Say:** ~12.0s. Remaining room: ~3.0s total for operation, reading and pauses.

> Alex types in one conversation. Recommendations, choices and previews stay together, inside the retailer’s interface. I built this with AI coding assistance using OpenAI’s APIs. Let’s use it.

## 03 · 0:35–0:50 — Before Experience

**Screen / actions:** Above the conversation, expand `How this recommendation was built` → `3 · Source-only ranking: the same eligible catalog`. Search `hiking jacket fall light rain` using `Search raw catalog`. Show names/descriptions, then collapse it. The initial constraints differ from the later request; this is not an uplift experiment.

**Say:** ~12.0s. Remaining room: ~3.0s total for operation, reading and pauses.

> This source-only ranking illustrates reading catalog descriptions manually. It shares eligibility rules with the assistant, so it is a reference view, not a controlled test of AI improvement.

## 04 · 0:50–1:35 — Request / Clarification / Shortlist

**Screen / actions:** In a fresh Alex session, send `I need a jacket for hiking this fall.` Read the first line while waiting. Click the offered `Light rain protection` chip and read the second line. When cards arrive, expand `Ranking scores` beside the first product heading, read the third line over its 0–1 score breakdown, then collapse it. Default percentages remain in the evidence panel. The priority chip skips Responses, not Moderation or all API work.

**Say:** ~22.3s. Remaining room: ~22.7s total for operation, reading and pauses.

> Alex’s profile already supplies size and budget. I’ll ask for a jacket for hiking this fall.

> The assistant asks which priority matters most. I’ll choose light rain protection.

> The app checks size, stock and budget. The ranked shortlist includes source-backed reasons; this toggle shows each product’s score breakdown. Missing specifications remain unknown.

## 05 · 1:35–1:55 — Review & Select

**Screen / actions:** Point to the first jacket’s larger image below its rank, source-backed reason, price and available option. Send `Choose the first one` near the start. `Select this jacket` is an alternative chat shortcut with an adjacent `Or say…` cue. Comparison chips/table have been removed. Wait for the selection reply and its complement group.

**Say:** ~12.9s. Remaining room: ~7.1s total for operation, reading and pauses.

> The inline card shows the reason, price and available option. I’ll type “choose the first one.” The assistant resolves that against the latest offered list, rather than guessing a product.

## 06 · 1:55–2:15 — Complete the Selection

**Screen / actions:** Show the distinct `Now in your selection` heading and accented `Completes the outfit` block: chosen items versus additional suggestions. Send `Add the first one` from that latest complement list. Do not add a redundant `Complete my outfit` turn. Show the updated inline `Your trail selection` and subtotal.

**Say:** ~13.3s. Remaining room: ~6.7s total for operation, reading and pauses.

> Complementary picks arrive with the selection, excluding owned and selected products. I’ll add the first one. The subtotal is before tax and shipping; the two-hundred-dollar budget applies only to the jacket.

## 07 · 2:15–2:30 — Start the Image Edit

**Screen / actions:** In the inline `Try-on preview`, show the fixed person and all product references ready. Send `Show the try-on preview` once near the start, then narrate. A queued/running state should be visible by 2:30. This authorizes try-on; uncached product-color edits can run earlier.

**Say:** ~8.1s. Remaining room: ~6.9s total for operation, reading and pauses.

> I explicitly request the try-on. It edits the prepared fictional-person photo using the selected garments in their chosen colors.

## 08 · 2:30–3:00 — Inspect the Evidence

**Screen / actions:** While the image runs, open `Why this match` on a human-reviewed demo product. Show its source, published attribute, quotation and judge decision. Preserve the first sentence exactly. Hold the quotation during the remaining room and close the drawer by 3:00. The 232 completed / 8 quarantined snapshot does not mean all 240 were human-reviewed.

**Say:** ~25.3s. Remaining room: ~4.7s total for operation, reading and pauses.

> These attributes were generated using OpenAI, then checked by a second model against the original product description, and reviewed by me for the demo products. Those products are published and searchable. Here is the exact sentence it quoted, and why it recommended this jacket. That separate check is an extra safeguard, not a guarantee that every attribute is right.

## 09 · 3:00–3:25 — Visual Result / Image Pipeline

**Screen / actions:** Show the inline result only if complete. Let the image register briefly; show `AI virtual try-on — visual reference only; appearance may differ. No size or fit prediction.` Narrate the pipeline, then return to the latest chat input by 3:25. If still running, replace this narration with a recovery line. Product-color assets are cached; a new try-on request does not reuse a completed private preview.

**Say:** ~18.4s. Remaining room: ~6.6s total for operation, reading and pauses.

> This uses Images edit with multiple inputs: the person photo and selected garment references. The prompt maps each reference to its variant and color. Moderation screens the prompt and input images. The asynchronous result stays in private memory and expires after fifteen minutes.

## 10 · 3:25–3:45 — Save / Feedback

**Screen / actions:** Send `Save this to the demo cart` immediately. Wait for success, show the header count, then send `Yes, that helped` only if that reflects the demo. These are two sequential turns inside 20 seconds; rehearsing live latency remains necessary. No cart screen or checkout. Switch to slide 7 at 3:45.

**Say:** ~9.4s. Remaining room: ~10.6s total for operation, reading and pauses.

> I save the selection through chat, then answer the feedback question. The cart icon only counts saved options; there is no checkout.

## 11 · 3:45–4:10 — Architecture / API Map

**Screen / actions:** Show slide 7, “One application. Clear API responsibilities.” Trace the offline catalog path, then Next.js → FastAPI → shared local stores. Point to each component’s API labels: Responses for agent/enrichment/judge, Embeddings for indexing/retrieval, Images for asset generation/edits, Moderations for text/image input safety. Local selection checks have no direct OpenAI call. Models is CLI preflight only. Leave routing and E2E detail for questions.

**Say:** ~21.4s. Remaining room: ~3.6s total for operation, reading and pauses.

> The Next.js interface calls our FastAPI backend. Responses powers the shopping agent and separate catalog checks. Embeddings supports indexing and retrieval. Images generates assets and edits selected references, with Moderations screening text and image inputs. SQLite, FAISS and local image storage hold the data; selection rules stay in application code.

## 12 · 4:10–4:30 — Business Value

**Screen / actions:** Show slide 8’s assumptions and formula. Pause before the sensitivity disclaimer. The increase is 0.1 percentage point: 100 additional orders × $150. Traffic/AOV fixed; returns and incremental costs excluded. No measured customer uplift.

**Say:** ~15.9s. Remaining room: ~4.1s total for operation, reading and pauses.

> Assume a hundred thousand monthly shoppers, three percent conversion and a hundred fifty dollar average order. A hypothetical increase to three-point-one percent adds fifteen thousand dollars monthly before costs. This is a sensitivity scenario, not measured uplift.

## 13 · 4:30–5:00 — Production / Adoption

**Screen / actions:** Stay on slide 8’s production stages. Capacity planning and security work are proposed, not implemented. Pause before the final sentence and finish by 5:00. No recap. Train reviewers and define cohorts, denominators, quality/latency/cost thresholds and rollback before a pilot.

**Say:** ~21.4s. Remaining room: ~8.6s total for operation, reading and pauses.

> Production needs authentication, live inventory and durable image jobs. We would evaluate reserved capacity against measured demand, not promise latency from this prototype. A controlled pilot would compare completion, helpfulness, quality and cost. The sponsor expands only against agreed thresholds, with rollback available. The goal is a better shopping decision.

## Recovery lines — replace the relevant narration, never append

| Situation | Replacement |
|---|---|
| Image still running | The image is still running. Alex can finish choosing without it. |
| Wait shortened in editing | The generation wait has been shortened in this recording. |
| Earlier live result | This image was generated earlier using the same selection and OpenAI image-editing workflow. |
| Replay | This is replay: model outputs are simulated and the outfit is a static diagram. |
| Source-only product | This product has source-only evidence. |
| No matches | Nothing meets these constraints. These alternatives were checked against the catalog; nothing changes until I choose. |
| Index unavailable | This request is using lexical fallback, not a successful semantic-search run. |
| Provider / safety error | The request did not complete; the application reports it rather than fabricating a result. |

Keep the real status visible. An earlier result must still be accessible and explicitly labeled as prepared. Private results expire 15 minutes after the request; selection/requirements changes or restart remove access.

## Final rehearsal checklist

1. Confirm actual profile, reviewed evidence, ready garment references and matching publication/index before recording.
2. Rehearse the complete typed flow, including the priority chip and latest-list ordinals. Fixture E2E success does not guarantee live language understanding.
3. Measure both save/feedback turns inside 3:25–3:45 and the real image wait. Resolve blockers before the final take or disclose the matching substitution.
4. Aim for 4:50–5:00 without rushing. Do not claim five-minute live completion based only on these word-count estimates.
