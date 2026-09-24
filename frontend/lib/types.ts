// Kept small intentionally; backend/tests/test_contracts.py checks required wire fields.
export type Evidence = { field: "name" | "category" | "description" | "colors" | "sizes"; quote: string };
export type Attribute = {
  attribute_id: string;
  kind: "season_suitability" | "activities" | "use_cases" | "style" | "benefits" | "search_keywords";
  value: string; support: "explicit" | "inferred"; evidence: Evidence[];
};
export type Category = "jacket" | "midlayer" | "pants" | "accessory";
export type Intent = {
  category: Category | null; activity: string | null; season: string | null;
  priority: "light_rain" | "warmth" | "lightweight" | "balanced" | null;
  max_price_cents: number | null; size: string | null; color: string | null;
  require_in_stock: boolean; required_benefits: string[]; preferred_benefits: string[];
};
export type Profile = {
  profile_id: string; display_name: string; preferred_size: string | null;
  preferred_colors: string[]; budget_cents: number | null; preferred_style: string[]; owned_product_ids: string[];
};
export type Session = { session_id: string; profile: Profile; intent: Intent; demo_context: { season: string; scenario: string } };
export type ColorImage = {
  key: string | null; status: "queued" | "running" | "completed" | "failed" | "unavailable";
  image_url: string | null; color: string;
  error: { code: string; message: string; retryable: boolean } | null;
};
export type Card = {
  product_id: string; name: string; category: Category; price_cents: number; currency: "USD";
  variant: { variant_id: string; color: string; size: string; stock: number };
  description: string; reasons: Attribute[]; tradeoff: string; scores: Record<string, number>;
  enrichment_status: string; image_url: string | null;
  match_summary?: string;
  color_image?: ColorImage | null;
  compatibility?: { category: string; color: string; activity_evidence: Attribute[] };
};
export type ComparisonData = {
  product_ids: string[]; columns: { product_id: string; name: string }[];
  rows: { label: string; values: string[] }[]; evidence: Attribute[];
  options?: Card[]; constraints?: Intent; price_difference_cents?: number;
};
export type Alternative = { id: string; label: string; eligible_count: number; intent: Intent };
export type SelectionState = {
  revision: string; confirmed: boolean; confirmed_at: string | null; can_preview: boolean; feedback_recorded: boolean;
  subtotal_cents: number; jacket_budget_cents: number | null;
  items: { variant_id: string; name: string; color: string; size: string; price_cents: number; category: Category }[];
  issues: { variant_id: string; message: string; overridable: boolean }[];
};
export type ReplyKind = "clarify" | "results" | "comparison_unavailable" | "complements" | "status"
  | "selection" | "confirmed" | "preview" | "feedback";
export type Routing = { tier: "light" | "standard" | "deterministic"; model: string | null;
  reasoning_effort: string | null; escalated: boolean };
export type Reply = {
  reply: { kind: ReplyKind; message: string;
    choices: string[]; product_ids: string[]; evidence_refs: string[]; job_id: string | null };
  cards: Card[]; comparison: ComparisonData | null; complements: Card[]; constraints: Intent;
  intent_sources: Record<string, string>; request_id: string; trace_id: string; mode: string;
  retrieval_mode: string | null; degradation: string | null; tool_events: { tool: string; ok: boolean }[];
  alternatives: Alternative[]; selection_state: SelectionState;
  selected: Card[]; job: Job | null; routing: Routing;
};
export type Job = {
  job_id: string; variant_ids: string[]; status: "queued" | "running" | "completed" | "failed";
  image_url: string | null; cached: boolean; mode: string; label: string;
  error: { code: string; message: string; retryable: boolean } | null;
  kind: "concept" | "try_on" | "sample_person"; expires_at: string | null;
  created_at: string; finished_at?: string;
};
export type Audit = {
  raw: { product_id: string; category: Category; name: string; description: string; colors: string[]; sizes: string[] };
  accepted: Attribute[];
  run: { status: string; candidates: { product_id: string; attributes: Attribute[] };
    report: { judgments: { attribute_id: string; decision: string; support: string; reason: string; evidence: Evidence[] }[];
      generator_model: string; judge_model: string; run_id: string; source_hash: string; prompt_version: string } } | null;
  mode: string;
  validation_test: { label: string; candidates: { attributes: Attribute[] }; expected_decision: string };
  validation_test_result: { mode: string; passed: boolean; judgments: { attribute_id: string; decision: string; reason: string }[] } | null;
};
export type Health = {
  readiness: string; catalog_version: string; index_version: string | null;
  mode: "live" | "fixture"; label: string; products: number; models: Record<string, string>;
};
