import { FormEvent } from "react";
import type { Card } from "@/lib/types";

export const WEIGHTS = [
  { label: "Semantic similarity", value: "40%" }, { label: "Lexical matching", value: "20%" },
  { label: "Intent", value: "20%" }, { label: "Season", value: "10%" },
  { label: "Profile", value: "5%" }, { label: "Fixed popularity", value: "5%" },
];

type Baseline = {
  mode: string; results: { product_id: string; name: string; description: string; score: number }[];
  eligible_count?: number; limitation?: string;
};

export function Evidence({ cards, retrievalMode, baseline, baselineQuery, profileId, busy,
  onAudit, onBaselineQuery, onBaselineSubmit, onProfile }: {
  cards: Card[]; retrievalMode: string; baseline: Baseline | null; baselineQuery: string;
  profileId: string; busy: boolean;
  onAudit: (id: string) => void; onBaselineQuery: (value: string) => void;
  onBaselineSubmit: () => void; onProfile: (value: string) => void;
}) {
  function submit(e: FormEvent) { e.preventDefault(); onBaselineSubmit(); }
  return <details className="evidence-drawer">
    <summary>How this recommendation was built <span>Source → independent review → your shortlist</span></summary>
    <div className="evidence-body">
      <section className="evidence-section">
        <h3>1 · How matches are ranked</h3>
        <ul className="weight-list">
          {WEIGHTS.map(w => <li key={w.label}><span>{w.label}</span><b>{w.value}</b></li>)}
        </ul>
        <p className="subtle">Inactive signals are dropped and the rest re-normalized. Hard constraints (category, size, colour, stock, budget) are applied first, and only accepted attributes enter enriched search.</p>
        {retrievalMode && <p className="subtle">Retrieval: {retrievalMode} · no hard constraints relaxed · every choice is made in the chat.</p>}
      </section>

      {cards.length > 0 && <section className="evidence-section">
        <h3>2 · Score for each shortlisted product</h3>
        {cards.map(c => <div className="score-row" key={c.product_id}>
          <button className="text-button" onClick={() => onAudit(c.product_id)}>{c.name} ↗</button>
          <code>{Object.entries(c.scores).map(([k, v]) => `${k}: ${v.toFixed(3)}`).join(" · ")}</code>
        </div>)}
      </section>}

      <section className="evidence-section">
        <h3>3 · Source-only ranking: the same eligible catalog</h3>
        <p className="subtle">Same eligibility rules, but raw descriptions alone drive the ranking. Not a pure enrichment ablation or proof of improvement.</p>
        <form className="baseline-form" onSubmit={submit}>
          <input aria-label="Baseline search query" maxLength={2000} value={baselineQuery}
            onChange={e => onBaselineQuery(e.target.value)} />
          <button disabled={busy}>Search raw catalog</button>
        </form>
        {baseline && <p className="subtle">{baseline.eligible_count} eligible products. {baseline.limitation}</p>}
        {baseline && <ol>{baseline.results.map(r => <li key={r.product_id}>
          <strong>{r.name}</strong> · {r.score.toFixed(3)}<p>{r.description}</p></li>)}</ol>}
      </section>

      <label className="profile-switch">Test another synthetic profile
        <select value={profileId} disabled={busy} onChange={e => onProfile(e.target.value)}>
          <option value="alex">Alex · M / neutral colors</option>
          <option value="sam">Sam · L / red and moss</option>
        </select>
      </label>
    </div>
  </details>;
}

export type { Baseline };
