<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

## Trailshop sample-person virtual try-on

Follow `../spec.md` v1.5 and `../README.md`. Virtual try-on is visual reference only, never Fit Prediction.
Display `/api/demo/sample-person.png`, a persistent pre-generated fictional full-body photo.
Do not show person-generation/replacement buttons or call sample generation on render.
Generate virtual try-on calls `/sessions/{id}/try-ons/demo` with request ID and selected variants.
Explain that consented customer full-body uploads could power a real shopping experience,
but uploading is not enabled here. No file picker or personal-photo checkbox in this UI.
Reset/removal deletes only private edited results, not the public fixed fictional asset.
Show asynchronous errors, expiry and honest replay labels; fixture try-on output is a static diagram.
The retained backend upload API must continue enforcing consent and validation for legacy clients.

Catalog cards use nullable `image_url` from the SQLite-backed API. Use `mediaUrl` and the shared
`ProductArt` component for generated art and missing/error states. Label product art as AI illustrations
whose colors/details can differ; never treat it as evidence or an exact variant photo.
Color-aware cards expose `color_image`; poll its read-only status without blocking chat, propagate
completion to recommendations/complements/selection, and show explicit error/retry states.
Do not display the base gray image as the selected color. Gate live outfit generation on ready
selected color references; fixture journeys remain labeled and do not invoke image APIs.

The shopper compares options by reading each product card in the chat; there is no comparison panel.
The selection summary is a no-order confirmation, not cart or checkout.
Retain conflicting selections for explicit review; honor server revision/stock checks and `can_preview`.
Clear private previews and confirmation after item/requirement changes. Visualization is optional.
Only apply a no-match alternative after a click; its verified count is not a promise of availability.
Use the session-scoped baseline with shared eligibility and its non-ablation limitation.
Journey times are observations including reading/idle time, not estimated savings. Never invent
conversion improvements, dollar cost, image progress percentages or expected completion times.
