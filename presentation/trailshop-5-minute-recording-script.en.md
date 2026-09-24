# Trailshop — Five-Minute Live API Recording Script

**Updated:** 23 September 2026 · Live API presentation · conversation-first UI  
**Target:** 5:00; never exceed 6:00  
**Language:** English · approximately 135–145 spoken words/minute  
**Slides:** [Eight-slide HTML deck](trailshop-shopping-assistant.html), including updated presenter notes  
**Route:** Slide 1 → Slide 2 → application → Slide 7 → Slide 8  
**Application:** 0:35–3:45, 190 seconds / 63% of the recording  
**Format:** HTML slides and recording; no PDF workflow

Read only the blockquotes under **Say**. Actions, checkpoints, alternative lines and notes are not additional narration. Slides 3–6 document implemented behavior for reviewers; do not read them instead of showing the app. The [original plan](trailshop-demo-presentation.md) is archived and does not govern this take.

**Live take only:** this script assumes a verified Live backend and real OpenAI responses. Editing these materials does not switch the application's mode or establish a successful live rehearsal. If the backend reports `fixture`, stop before recording; do not use the live narration over Replay.

## Recording contract

- **Customer:** fictional outdoor retailer Trailshop. **User:** online shopper Alex. **Audience:** Head of Digital Commerce, positioned as prospective economic buyer/business sponsor accountable for conversion and the shopping experience. This is a fictional role assumption, not a claim of customer discovery interviews.
- **One surface:** OpenAI Platform/APIs. AI coding assistance is a development aid, not a second runtime surface.
- **Completed preparation:** the current live catalog has 240 products: 232 completed enrichment runs and 8 quarantined records retained as source-only. Publication and index versions match. Human review is a separate, presenter-confirmed claim limited to the demonstrated products, not all 240.
- **Main demonstration:** typed conversation, one priority question, inline recommendations with a score toggle, clearly separated selected items and complements, evidence, optional try-on, demo count and feedback. Conflict review and no-match alternatives remain available. Comparison chips and the comparison table are absent. Comparison is not an agent tool; a comparison request receives an explicit unavailable notice without changing the selection.
- **Current screen:** top introduction (“Your next trail starts here.”) → collapsed evidence panel → one conversation column. There is no separate autumn banner; “Autumn, considered.” remains in the introduction. Recommendations, selection summary and try-on appear inside the conversation, not in a separate right-hand panel. Card buttons are chat shortcuts, not a separate shopping flow. “Say” in action instructions means type/send text or select a reply chip; there is no speech input.
- **Ranking controls:** each search-result card has a `Ranking scores` toggle beside its product heading. It displays that product's 0–1 signal scores and weighted total. The evidence panel separately lists default weights: semantic 40%, lexical 20%, intent 20%, season 10%, profile 5%, fixed popularity 5%. Do not confuse scores with percentages, confidence or measured accuracy.
- **Not implemented in this UI:** a separate cart or checkout workflow, real inventory integration, shopper photo uploads, voice or Fit Prediction. The cart icon is only a temporary count, not a commerce integration.
- **Live:** shopping language interpretation and requested try-on edits call OpenAI. The priority chip is deterministic; a query-embedding cache hit can avoid that embedding call. Never imply every UI action needs a model call.
- **Prepared:** synthetic catalog/profile/stock, completed enrichment and index, the fixed fictional person and selected-color garment references. Prepared references are inputs to a new live edit, not a prerecorded try-on result.
- **Proposed:** actual commerce integration, customer-photo UI, production controls, adoption instrumentation and business uplift. Live inference does not turn the local prototype into production or its demo count into an order.
- **Validation boundary:** Playwright E2E exercises the real browser, UI and local API using fixture model outputs. It does not establish live routing accuracy, model quality, image quality or API latency.
- **Recording viewport:** use the desktop layout (at least 1280px wide). The current selected-item layout showed horizontal overflow at 390px during this refresh; do not present mobile readiness as verified.

## Before recording

| Check | Required state |
|---|---|
| Mode | Require `/api/health` to report `mode: "live"`; reset the journey after any operator-led mode change. Confirm there is no Replay banner. A banner alone is not proof of successful inference. |
| Fresh session | Use Alex and `Reset journey` so the priority question and selection start from a clean state. |
| Exact request | In a fresh session, send `I need a jacket for hiking this fall.` and click `Light rain protection` when the priority question appears. Rehearse both turns within 0:50–1:35 and identify useful results from the human-reviewed demo set. Do not memorize a product that does not appear. |
| Evidence and index | Confirm the demonstrated product has a completed run, published attribute and source quotation, and that the current index matches publication. A live-mode banner alone proves none of these. |
| Baseline | Rehearse the source-only query. It shares current eligibility, but not the assisted ranking. If comparing rankings side by side, rerun after setting the same intent. |
| Review and selection | Review the first inline jacket card, then type `Choose the first one`. Its `Select this jacket` button is an alternative shortcut that sends `Choose the first`. Do not use old cards after the latest offered list changes. |
| Complements | Jacket selection normally attaches up to two complements in the same reply. Use the current `Completes the outfit` list, then type `Add the first one`. Do not add a redundant `Complete my outfit` turn unless complements were not returned. |
| Image preparation | Fixed fictional photo loads; exact selected-color garment references are ready. Preparing uncached colors can itself incur image calls. Disclose prepared assets. |
| Image timing | Rehearse once; the schedule is not an API latency guarantee. Do not regenerate people or run a full catalog batch. |
| Live evidence | Before the final take, verify actual Responses calls, successful hybrid retrieval against the published index and one completed Images edit for the chosen flow. Retain request IDs and stage timings privately; do not expose logs or keys in the recording. |
| Final save | Rehearse `Save this to the demo cart` and then `Yes, that helped`: two sequential chat turns within a 20-second window. Wait for each reply. No cart screen is opened. |
| Slides | Hide the HTML presenter notes with `N` or `Notes` before recording; keep eight slides. The live labels describe this take, not an automatic health check. |
| Recording hygiene | Keep keys, terminals and personal data off-screen. Verify first-person build claims; be ready to explain the code and trade-offs. |

Private try-on results expire 15 minutes after the request and disappear on removal, requirement/selection changes or API restart. A prepared same-workflow backup must still be accessible; identify it as prepared. The fixed public person asset does not expire. Product-color images are persistent cached assets; private try-on results are not reused as a completed-result cache for a new request.

## Run of show

| Time | Screen | Purpose |
|---|---|---|
| 0:00–0:20 | Slide 1 · Customer & Problem | Customer, audience, user and meaningful problem |
| 0:20–0:35 | Slide 2 · Before & After | API fit and personal build ownership |
| 0:35–0:50 | App · source-only ranking | Before experience, with manual synthesis limits |
| 0:50–1:35 | App · request, priority choice and shortlist | Ask once, choose light rain protection, show grounded recommendations |
| 1:35–1:55 | App · recommendation card | Review the reason and select a jacket |
| 1:55–2:15 | App · complements and summary | Complete the outfit, not an order |
| 2:15–2:30 | App · inline person and garment references | Request the optional image edit |
| 2:30–3:00 | App · evidence drawer | Explain prepared enrichment while the edit runs |
| 3:00–3:25 | App · inline visual result | Explain reference-based editing and visual limits |
| 3:25–3:45 | App · save indicator and feedback | Allow two chat turns, not a cart walkthrough |
| 3:45–4:10 | Slide 7 · Overall Architecture | Components and their OpenAI APIs |
| 4:10–4:30 | Slide 8 · Value & Production Adoption | Quantified hypothesis, not measured uplift |
| 4:30–5:00 | Slide 8 · remain visible | Practical pilot, ownership and expansion gates |

## 01 · 0:00–0:20 — Customer / Problem

**Show:** Slide 1, “Customers shop for a purpose. Not a SKU.”

**Say:**

> This demo is for Trailshop, a fictional outdoor retailer. For its Head of Digital Commerce, this prototype explores a simpler shopping journey: helping Alex turn a hiking need into a shortlist, with evidence behind each recommendation.

**Checkpoint:** Advance by 0:20. The executive is the audience; the shopper is the user. Do not imply completed customer interviews, measured effort reduction or a usability study.

## 02 · 0:20–0:35 — Proposed Solution

**Show:** Slide 2, “Less searching. More deciding.”

**Say:**

> Before, Alex would translate the need into keywords and assemble the answer alone. Now, Alex just asks in one conversation, and the agent understands the context and intent behind the request to surface the right products, with evidence-backed choices. Let’s use it.

**Action:** Switch to the app by 0:35. Slides 3–6 are supporting material, not stops in the main recording.

**Product judgment — for questions:** Platform/APIs fits an embedded retail workflow with catalog/profile context and controlled actions. ChatGPT would be a separate destination rather than this integrated experience; Codex is a development surface, not the shopper-facing runtime. The choice is about workflow fit, not a claim that another surface is universally worse. Responses interprets requests, Embeddings supports hybrid retrieval, and Images provides optional reference-based visualization. Deterministic rules remain in application code.

## 03 · 0:35–0:50 — Before Experience

**Show:** Below the top introduction and above the conversation, expand `How this recommendation was built` → `3 · Source-only ranking: the same eligible catalog`.

**Action:** Search `hiking jacket fall light rain` using `Search raw catalog`. Show actual names/descriptions, then collapse the panel.

**Say:**

> This screen searches only raw product names and descriptions, not the AI-enriched attributes. It’s the old way: reading the source text manually to search and compare.

**Note:** Eligibility can depend on approved required-benefit evidence. The initial view uses Alex’s starting constraints; rerun after the request for a same-intent ranking reference.

## 04 · 0:50–1:35 — Request / Clarification / Shortlist

**Action:** In the fresh Alex session, paste and send:

```text
I need a jacket for hiking this fall.
```

**Say while waiting:**

> I’ll ask for a jacket for hiking this fall. All shopper and catalog data here is synthetic, enriched and illustrated using OpenAI APIs.

**Action:** Wait for `What matters most for your hike?`. Click the `Light rain protection` reply chip inside the chat. For this take, do not type it: the chip sends `priority_choice:true` and uses a validated deterministic path with zero Responses calls. Free text instead goes through model interpretation. Both paths still apply input/output Moderation in live mode.

**Say as you choose:**

> The agent asks which priority matters most. I’ll choose light rain protection.

**Action:** Once results appear, point to an available variant, price and a reason. Briefly expand `Ranking scores` beside the first product's heading, show its scores, then collapse it. The percentages belong to `1 · How matches are ranked` in the evidence panel, not this per-product score list.

**Say:**

> The agent checks size, stock and budget. The ranked shortlist includes source-backed reasons; this toggle shows each product’s score breakdown.

**Checkpoint:** Both turns and the shortlist fit by 1:35. The clarification-and-choice flow is part of the main recording, not an optional extra. If the priority question is missing, reset and rehearse from a fresh session rather than pretending a choice appeared. If fewer than three qualify, say so. If `lexical-fallback` appears, do not claim that request used successful semantic retrieval.

## 05 · 1:35–1:55 — Review & Select

**Action:** Point to the first inline jacket's larger image below its rank, `Why we recommend it`, price, size and available color. Type `Choose the first one` and send it. Alternatively, `Select this jacket` sends the corresponding ordinal message; its `Or say…` cue sits beside the button. There is no comparison chip or comparison table to open.

**Say:**

> The inline card shows the reason, price and available option. I’ll type “choose the first one.” The agent resolves that against the latest offered list, rather than guessing a product.

**Checkpoint:** Jacket selected by 1:55. Complement recommendations start from the selected jacket.

## 06 · 1:55–2:15 — Complete the Selection

**Action:** Distinguish the larger `Now in your selection` heading from the accented `Completes the outfit` block in the same reply. The former contains chosen items; the latter contains additional suggestions. Type `Add the first one` from that latest complement list; `Add to selection` is the card shortcut. Show the updated inline `Your trail selection`: color, catalog size, price and subtotal.

**Say:**

> Complementary picks arrive with the selection, excluding owned and selected products. Each one matches the same hiking activity and complements the jacket’s color, chosen from a different category. I’ll add the first one.

**Note:** Midlayers, pants and accessories are supported; do not promise footwear or a particular item. Catalog size is not a fit recommendation. Complements are suggestions until explicitly added; their group is not a saved-cart view.

## 07 · 2:15–2:30 — Start the Image Edit

**Action:** In the inline `Try-on preview`, show the fixed fictional person and all product references ready. Send `Show the try-on preview` once, using the reply chip or text. This authorizes the try-on, not all image work: uncached product-color edits can already run during search.

**Say:**

> Here’s Alex’s trail selection so far. Let’s try it on: I explicitly request the try-on, which edits the prepared fictional-person photo using the selected garments in their chosen colors. This takes a moment to generate, so I’ll explain the evidence behind it while we wait.

**Checkpoint:** Queued/running by 2:30. No person is regenerated. Refer to the result as outfit visualization, not a representation of Alex’s body. The statement above applies only to a newly accepted live request, not a prepared-result backup.

## 08 · 2:30–3:00 — Inspect the Evidence

**Action:** While the image runs, open `Why this match` on a reviewed demo product. Show the unchanged source and one actual published attribute with its quotation and judge decision.

**Say:**

> These attributes were generated using OpenAI, then checked by a second model against the original product description, and reviewed by me for the demo products. Those products are published and searchable. Here is the exact sentence it quoted, and why it recommended these pants. That separate check is an extra safeguard.

**Action:** Pause over the evidence, then close the drawer. Keep the exact first sentence.

**Note:** Do not equate independent model validation with OpenAI certification. The adversarial section distinguishes prepared test claims from observed live judgments. Do not invent a rejection or imply every catalog product was human-reviewed.

## 09 · 3:00–3:25 — Visual Result / Image Pipeline

**Action:** Show the completed result if ready. Point to the selected garments, then to the on-screen label `AI virtual try-on — visual reference only; appearance may differ. No size or fit prediction.` The label carries the disclaimer, so you do not need to say it. Stay on the preview, then return to the selection summary.

**Say:**

> Let’s look at the finished outfit shot. This uses Images edit with multiple inputs: the person photo and selected garment references. The prompt maps each reference to its variant and color. Moderation screens the prompt and input images.

**Checkpoint:** Use this narration only for the completed current live request. Return to the latest chat input by 3:25. If the job is still running, use a recovery replacement below. Do not describe an unfinished image as completed.

**Note:** The disclaimer is displayed, not spoken: every image job stores a label, and try-on and sample-person outputs are private kinds held in memory with a 15-minute expiry rather than written to disk. Do not claim a fit prediction, exact colors or a real shopper body.

## 10 · 3:25–3:45 — Save / Feedback

**Action:** Say `Save this to the demo cart`, briefly show the updated header count, then answer the agent’s helpfulness question with `Yes, that helped` if that reflects the demonstration. Do not open a cart screen; none is implemented.

**Say:**

> I save the selection through chat, then answer the feedback question. The cart icon only counts saved options; there is no checkout.

**Checkpoint:** Switch to slide 7 at 3:45. Do not simulate an order or add a separate cart demonstration. The count resets on reload, journey reset or profile change.

## 11 · 3:45–4:10 — Architecture / API Map

**Show:** Slide 7, “One application. Clear API responsibilities.” Follow offline preparation, the Next.js → FastAPI path and the two trade-off boxes below. Each backend component names the OpenAI API it uses.

**Say:**

> Let's walk through the architecture behind this. The Next.js interface calls our FastAPI backend. The Responses API powers the shopping agent and separate catalog checks. The Embeddings API supports indexing and retrieval. The Images API generates assets and edits selected references, with the Moderations API screening text and image inputs. SQLite, FAISS and local image storage hold the data; selection rules stay in application code.

**Note:** API labels sit inside the relevant component, not in a separate detailed API list. Next.js and local selection checks make no direct OpenAI calls; the agent invokes the validated tools. The footer limits Models API to CLI preflight. Routing, call counts, model IDs and E2E caveats are supporting notes, not additional slide content. Do not imply Models runs on every request, all output images receive post-screening, or Moderation guarantees factuality.

**Routing — for questions:** A request is eligible for `gpt-5.4-mini` / effort `none` only when it has at most ten whitespace-separated words, existing results or selection, and a recognized follow-up keyword. Others use `gpt-5.6-terra` / `low`. This is an application heuristic, not a model-selection benchmark. Retryable provider errors or invalid final replies may escalate a light turn within the bounded repair loop; not every failure triggers escalation. Hover an actual `small model` or `reasoning model` badge to inspect its model; do not claim a badge appeared on the deterministic priority-chip turn.

**Call reduction — for questions:** A successful standalone tool with `finish_turn=true` can finish after one Responses call. Composite requests and repairs can take more. The structured priority chip takes zero Responses calls, not zero API calls: Moderation and potentially query embeddings still run. Query-vector caching is capped at 128 entries for five minutes; prices, stock and session state are not cached as recommendation results.

**Model configuration:** Standard chat/enrichment: `gpt-5.6-terra` / `low`; offline judge: `gpt-6-astra` / `medium`; retrieval: `text-embedding-3-small`; moderation: `omni-moderation-latest`; images: `gpt-image-2.5-flare`. Product art/color edits use low quality at 816×816; try-on uses configured medium quality at 1024×1024. Recheck runtime configuration before recording.

**Validation — for questions:** Playwright E2E checks browser → Next.js → FastAPI interactions with fixture model outputs, including selection, save counts, feedback, image states and mobile layout. It is not evidence of live language understanding, model quality or latency. Live catalog publication/index checks are separate evidence; a paid live rehearsal is still needed for the final recording.

**Scope — for questions:** `compare_products` is not in the agent allowlist. Comparison requests receive a server-written unavailable notice directing the shopper to existing cards and `Why this match`, without selecting products or claiming a table was shown. An internal comparison helper remains for legacy tests, not as a chat tool or public comparison endpoint.

**Selection shortcuts — for questions:** Recognized English ordinal selection messages such as `Choose the first one` and `Add the first one` use a deterministic path before model routing, whether typed or sent by a card button. They resolve against the latest offered list; other free-text requests use the model. These turns have no model badge. Moderation still runs, and attached complement retrieval can require embeddings.

## 12 · 4:10–4:30 — Business Value

**Show:** Slide 8. Point to the value-hypothesis callout and the three-stage pilot cards.

**Say:**

> The primary business outcome is improved conversion, with attach rate as a secondary opportunity. Because this is a fictional customer, I treat those as hypotheses rather than claimed results. In a controlled pilot, I would compare completed selections and conversion against the baseline experience you saw at the beginning.

**Note:** Do not claim a specific revenue figure or conversion lift. Conversion is a hypothesis to test in the pilot, not a result from this prototype.

## 13 · 4:30–5:00 — Production / Adoption

**Show:** Slide 8’s three pilot stages; remain on this slide.

**Say:**

> Production needs authentication, security and live inventory, plus durable image jobs. We would evaluate reserved capacity against measured demand. A controlled pilot would compare completion, helpfulness, quality and cost. The goal is a better shopping decision.

**Checkpoint:** Stop at 5:00; no extra recap.

**Scale and security — for questions:** The prototype runs one local worker on SQLite and FAISS. Production needs shared authoritative session/job state, atomic revision checks and durable image queues before adding API workers; do not multiply workers while private results and locks remain process-local. Choose managed storage/search from measured scale, not as an automatic requirement to replace FAISS. Capacity purchases are future options subject to actual model availability, contract terms, demand and load testing; they are not a latency or no-throttling guarantee. Add authentication/session binding, tenant isolation where applicable, managed secrets, least-privilege rotated keys, TLS, data minimisation, retention limits and audit logging.

**Production detail — for questions:** Train merchandisers and support on evidence review and the error queue. Define cohorts, sample size, denominators, quality/latency/cost thresholds and stopping rules before a limited-category pilot. Actual conversion requires commerce integration. Reconcile billed usage across text, embeddings, moderation and images, including amortized catalog preparation; runtime image reservations alone are not total cost control.

**Pilot measurement contract — proposed, not implemented analytics:**

| Measure | Denominator / comparison | Owner |
|---|---|---|
| Adoption | Agent-starting eligible sessions / eligible sessions shown the agent | Analytics |
| Selection completion | Sessions with a confirmed current selection / agent-starting sessions; not purchases | Analytics + commerce |
| Repeat use | Returning users who use the agent again / prior users with a return visit in an agreed window | Analytics; privacy-reviewed identity |
| Business outcome | Orders / eligible sessions in randomized treatment versus control after commerce integration; AOV and attach rate are secondary, not additional assumed uplift | Commerce + analytics |
| Guardrails | Unsupported claims, helpfulness response rate, p95 latency, cost per completed journey, complaints and returns when observable | Merchandising + engineering/support |

Start with a limited jacket audience; assign exposure consistently and account for users who never open the agent. Agree windows, sample size, practical uplift threshold and cost/quality stopping rules before launch. The sponsor decides expansion; engineering owns rollback to ordinary shopping. No target percentages or pilot outcomes are claimed as measured. Reviewer training and support escalation are launch dependencies, not later cleanup.

## Optional paths — substitutions, not extra demo minutes

| Alternative | Replace | Actions and boundary |
|---|---|---|
| Requirement change / no results | Part of the 3:00–3:25 reveal, if image demonstration is intentionally omitted | Send `Keep the jacket under $1`. Show preserved selection with a budget conflict and a review-required preview cue. Select the offered budget-alternative chip; only that condition changes. This clears prior private previews/confirmation; do not mix it with the main image reveal. |
| Explicit exception | Part of selection review in a rehearsed alternative take | Explain the conflict before sending `Keep these exceptions and save to the demo cart`. Stock unavailability cannot be overridden. No hidden relaxation. |

## Recovery lines — replace the relevant main narration

| Situation | Honest action / replacement |
|---|---|
| Image still running | Keep its real elapsed/status visible. “The image is still running. Alex can finish choosing without it.” Show a verified earlier same-workflow result only if available and explicitly label it as prepared. |
| Wait removed in editing | Caption `Generation wait shortened`. “The generation wait has been shortened in this recording.” Never disguise a prepared result as the current call. |
| Earlier live result | “This image was generated earlier using the same selection and OpenAI image-editing workflow.” Replace any implication of a new result in this take. |
| Replay mode detected | Stop this take. Verify Live configuration and rehearse again before using the live script. A separately labeled simulation must not replace the final live evidence or be narrated as live. |
| Product lacks published evidence | Show the state. “This product has source-only evidence.” Do not apply the completed-demo-product claim to that record; select an actually reviewed product for the final take. |
| No matches | “Nothing meets these constraints. These alternatives were checked against the catalog; nothing changes until I choose.” Do not invent a match. |
| Index unavailable | Keep the fallback label. “This request is using lexical fallback, not a successful semantic-search run.” |
| Provider/safety error | Show the error. “The request did not complete; the application reports it rather than fabricating a result.” Do not retry blindly or describe failure as success. |

Rehearse to about 4:50–5:00. Prioritize the actual shopping workflow, one clear evidence record and the final decision over showcasing every feature. A disclosed fallback preserves accuracy but is not a substitute for preparing a working final demonstration. Submit only the slides and recording; this script and the Korean notes are presenter aids.
