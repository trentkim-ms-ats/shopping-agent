# OpenAI Assignment — 5-Minute Demo Video Plan

> **Archived planning source — not the current recording script.** This original plan is preserved for reference. Its mock-cart flow, runtime sample generation and earlier timing are superseded by the [implemented-demo slides](trailshop-shopping-assistant.html) and [current five-minute recording script](trailshop-5-minute-recording-script.en.md). Use those for presentation; do not narrate this archive as implemented behavior.

## Overall Structure

The assignment requires:

> “A recorded, presentation-ready demonstration of approximately five minutes and no longer than six minutes. Spend most of the recording showing the solution.”

Target duration: **~5 minutes**

| Time | Section | Content |
| --- | --- | --- |
| 0:00–0:35 | Customer & Problem | Customer, target user, buyer, and current problem |
| 0:35–0:55 | Proposed Solution | Introduce the AI Shopping Assistant |
| 0:55–4:15 | **Live Demo** | Show the actual end-to-end shopping experience |
| 4:15–4:40 | Architecture | Explain key technical choices |
| 4:40–5:05 | Business Impact & Production | Quantify value and explain production path |

---

# 1. Customer & Problem

**Time: 0:00–0:35**

Introduce the fictional retail customer, target user, buyer, and problem.

### Example Narrative

> I chose a fictional outdoor retailer. The target user is an online shopper, and the business buyer is the Head of Digital Commerce.
>
> Today, product catalogs contain basic attributes such as category, color, size, and description, but customers shop differently. They ask questions like, “What jacket would work for hiking this fall?”

### Core Problem

Traditional product catalogs are designed primarily to **manage products**, not to understand **how customers shop**.

Example:

**Existing Catalog**

- Product name
- Category
- Color
- Size
- Description

**Customer Intent**

- Fall hiking
- Lightweight
- Rain protection
- Preferred style
- Personal preferences

This creates a gap between **catalog data** and **shopping intent**.

---

# 2. Proposed Solution

**Time: 0:35–0:55**

Introduce the solution briefly and move quickly into the demo.

### Example Narrative

> I built an AI Shopping Assistant using the OpenAI Platform.
>
> It enriches the retailer's existing catalog with shopping-relevant attributes, understands customer intent and preferences, recommends suitable products, and helps the customer visualize a complete outfit.

### Customer Journey

```text
Understand
   ↓
Clarify
   ↓
Discover
   ↓
Recommend
   ↓
Review / Select
   ↓
Complement
   ↓
Visualize
   ↓
Purchase
```

---

# 3. Live Demo

**Time: 0:55–4:15**

The majority of the recording should show the actual working solution.

---

## 3.1 Understand Shopping Intent

**Time: 0:55–1:25**

### Customer

> Recommend a hiking jacket for me.

The Shopping Assistant uses the customer's existing profile but identifies that important information is still missing.

### Agent

> Are you mainly looking for rain protection, warmth, or something lightweight?

### Customer

> Something lightweight for hiking this fall.

### Capabilities Demonstrated

- Natural-language understanding
- Customer profile awareness
- Multi-turn conversation
- Clarification
- Context preservation
- Intent extraction

---

## 3.2 Personalized Product Recommendation

**Time: 1:25–2:00**

The agent searches the product catalog and returns the **Top 3 recommendations**.

Each product should include a short explanation.

### Example

**Trail Shell Jacket**

Why it matches you:

- ✓ Suitable for fall
- ✓ Designed for hiking
- ✓ Lightweight
- ✓ Matches your preferred colors
- ✓ Available in your size

### Example Narrative

> The assistant isn't relying only on keyword matching. It combines the customer's profile, conversational intent, structured product attributes, and semantic search.

### Capabilities Demonstrated

- Hybrid retrieval
- Semantic search
- Structured metadata filtering
- Personalization
- Recommendation reasoning
- Explainable recommendations

---

## 3.3 Show Product Data Enrichment

**Time: 2:00–2:30**

Open a product detail or **“Why this recommendation?”** view.

Show the difference between the original retail catalog and the AI-enriched catalog.

### Original Product Data

```text
Name
Category
Color
Size
Description
```

### AI-Enriched Product Data

```text
Season       Fall / Spring
Activity     Hiking
Style        Minimal Outdoor
Benefits     Lightweight
Use Case     Day Hiking

Validation   ✓ Passed
```

### Example Narrative

> The original catalog doesn't contain attributes such as season or use case.
>
> I use OpenAI offline to derive these shopping attributes, followed by a second LLM validation pass that rejects attributes not supported by the original product information.

### Enrichment Pipeline

```text
Raw Product Catalog
        │
        ▼
OpenAI Enrichment
        │
        ▼
Candidate Shopping Attributes
        │
        ▼
LLM Validation
        │
   ┌────┴────┐
   │         │
 PASS      REJECT
   │
   ▼
Enriched Product Catalog
        │
        ▼
Embedding / Search Index
```

### Enrichment Guardrail

Preserve **source-of-truth facts**.

AI generates only derived shopping attributes such as:

- Season suitability
- Activity
- Style
- Use case
- Key benefits
- Search keywords

The model must not invent unsupported factual specifications such as:

- Material
- Waterproof rating
- Temperature rating
- Certification
- Technical performance

### Validation Principle

The first LLM optimizes for **enrichment coverage**.

The second LLM acts as a validator and optimizes for **precision**.

> Generate → Validate → Index

---

# 4. Complementary Product Recommendation

**Time: 2:30–3:00**

The customer selects one of the recommended jackets.

### Customer

> I like the first one.

The agent keeps the original shopping goal in context.

### Agent

> Since you're preparing for fall hiking, would you like me to complete the outfit?

The agent recommends complementary products such as:

- Hiking pants
- Base layer
- Hiking shoes

The recommendations should be based on the **customer's original shopping goal**, rather than generic “people also bought” recommendations.

### Capabilities Demonstrated

- Context preservation
- Goal-aware recommendation
- Cross-sell
- Product relationship reasoning

---

# 5. Outfit Visualization with GPT-Image

**Time: 3:00–3:50**

The customer selects complementary products.

### Customer

> Show me how these would look together.

The application sends the selected product attributes to GPT-Image.

```text
Selected Jacket
      +
Selected Pants
      +
Style Information
      +
Customer Preferences
        │
        ▼
     GPT-Image
        │
        ▼
Outfit Visualization
```

The generated image is displayed directly in the Shopping Assistant.

### Example Narrative

> The assistant passes the selected product attributes to GPT-Image to create an outfit visualization, helping the customer evaluate the combination before purchasing.

### Important Positioning

Describe this feature as:

**Outfit Visualization**

Do not describe it as a real customer **Virtual Try-On**, because the prototype uses a synthetic model rather than the actual customer's body or photograph.

### Capabilities Demonstrated

- Multimodal experience
- Product-context-aware image generation
- Visual product evaluation

This should be the **visual climax of the demo**.

---

# 6. Commerce Action

**Time: 3:50–4:15**

### Customer

> Add these to my cart.

The Shopping Assistant calls a mocked commerce tool.

```text
add_to_cart()
```

Result:

```text
✓ 2 items added to your cart

Trail Shell Jacket
Hiking Pants

Total: $428
```

### Demo Disclosure

Clearly explain which components are real and which are simulated.

### Example Narrative

> The catalog, customer profile, and commerce transaction are simulated using synthetic local data, while the OpenAI model, embedding, and image-generation calls are live.

### Capabilities Demonstrated

- Tool calling
- Action execution
- Agentic workflow
- Human-controlled commerce action

---

# 7. Architecture & Technical Choices

**Time: 4:15–4:40**

Switch briefly from the application to the architecture slide.

## High-Level Architecture

```text
                     OpenAI Platform
                           │
              ┌────────────┼────────────┐
              │            │            │
          Responses     Embeddings   GPT-Image
              │            │            │
              └────── Shopping Agent ───┘
                           │
                     Hybrid Search
                           │
                   Enriched Catalog
                           ▲
                           │
                  Generate → Validate
                           │
                      Raw Catalog
```

### Example Narrative

> I chose the OpenAI Platform because this experience needs to be embedded directly into the retailer's existing commerce workflow.
>
> Structured attributes provide controllable filtering, embeddings provide semantic retrieval, and tool calling connects the agent to commerce actions.

### Key Technical Choices

**OpenAI Platform / Responses API**

- Agent reasoning
- Conversation
- Tool calling
- Structured outputs

**OpenAI Embeddings**

- Semantic product retrieval

**Structured Metadata**

- Deterministic filtering
- Season
- Activity
- Size
- Customer preferences

**Hybrid Retrieval**

```text
Metadata Filtering
       +
Semantic Search
       ↓
Candidate Products
       ↓
LLM Recommendation
       ↓
Top 3
```

**GPT-Image**

- Outfit visualization

---

# 8. Business Impact & Production Plan

**Time: 4:40–5:05**

Finish with customer value rather than technology.

## Business Impact

Clearly identify all numbers as assumptions for the fictional customer.

Example baseline:

```text
Monthly shoppers:        100,000
Conversion rate:         3%
Average order value:     $150
```

Potential metrics to measure:

- Product discovery success
- Recommendation acceptance rate
- Conversion rate
- Attach rate
- Average order value
- Search abandonment rate
- Customer engagement

### Example Narrative

> For this prototype, I assume 100,000 monthly shoppers, a 3% conversion baseline, and a $150 average order value.
>
> Even a modest improvement in product discovery and attach rate creates measurable revenue upside.

---

## Production & Adoption

Start with a controlled pilot rather than deploying across the entire catalog.

### Phase 1 — Pilot

One product category:

**Outdoor Jackets**

Measure:

- Enrichment accuracy
- Recommendation acceptance
- Search success
- Conversion
- Attach rate

### Phase 2 — Expand

Expand to:

- Outdoor clothing
- Hiking equipment
- Other retail categories

Only expand after predefined quality thresholds are achieved.

### Example Narrative

> I would start with a limited-category pilot, measure recommendation acceptance, conversion, attach rate, and enrichment accuracy, and expand only after meeting defined quality thresholds.

---

# Closing Message

End with the customer outcome rather than the technology.

> The goal isn't just to make product search conversational.
>
> It's to turn a basic retail catalog into a personalized shopping experience that helps customers discover, evaluate, and purchase with confidence.

---

# Final Timing

| Time | Section |
| --- | --- |
| 0:00–0:35 | Customer & Problem |
| 0:35–0:55 | Proposed Solution |
| **0:55–4:15** | **Live Solution Demo** |
| 4:15–4:40 | Architecture & Technical Choices |
| 4:40–5:05 | Business Impact & Production |
| **Total** | **~5:05** |

## Key Story

```text
Customer Problem
       ↓
Basic Retail Catalog
       ↓
OpenAI Data Enrichment
       ↓
LLM Validation
       ↓
Hybrid Product Discovery
       ↓
Personalized Recommendation
       ↓
Complementary Products
       ↓
GPT-Image Outfit Visualization
       ↓
Commerce Action
       ↓
Business Value
```

## Core Message

**Transform a basic product catalog into an AI-ready catalog, then use it to deliver a personalized, agentic shopping experience.**
