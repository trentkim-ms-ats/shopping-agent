import { money } from "@/lib/api";
import type { SelectionState } from "@/lib/types";

export function SelectionSummary({ state, feedbackRecorded, savedToCart }: {
  state: SelectionState; feedbackRecorded: boolean; savedToCart: boolean;
}) {
  const blocked = state.issues.some(issue => !issue.overridable);
  return <section className="panel selection-summary" aria-label="Selection summary">
    <span className="eyebrow">YOUR DECISION, YOUR CONTROL</span>
    <h2>Your trail selection</h2>
    <ul>{state.items.map(item => <li key={item.variant_id}>
      <strong>{item.name}</strong> · {item.color} / {item.size} · {money(item.price_cents)}
    </li>)}</ul>
    <p><strong>Selected-item subtotal: {money(state.subtotal_cents)}</strong></p>
    <p className="subtle">Before tax and shipping. {state.jacket_budget_cents !== null ?
      `Your ${money(state.jacket_budget_cents)} budget applies to the jacket, not the whole outfit.` :
      "No jacket budget is set."} Size is a catalog option, not a prediction of fit.</p>
    {state.issues.length > 0 && <div className="selection-warning" role="status">
      <strong>{state.confirmed ? "You accepted these exceptions" : "Review your selection against the current requirements"}</strong>
      <ul>{state.issues.map((issue, index) => <li key={`${issue.variant_id}-${index}`}>{issue.message}</li>)}</ul>
      {!state.confirmed && <p>Choose another item or explicitly keep these exceptions. Unavailable items cannot be saved.</p>}
    </div>}
    {!savedToCart ? <p className="card-cue" role="status">{blocked ?
      "Ask your trail guide to replace the unavailable item first." :
      state.issues.length ? "Say “keep these exceptions and save to the demo cart” in the chat." :
      "Say “save this to the demo cart” in the chat to finish."}</p> :
      <div role="status"><strong>Saved to demo cart. No purchase or payment.</strong>
        {!feedbackRecorded ? <p className="card-cue">Your trail guide asked whether this helped — answer in the chat.</p> :
          <p>Thank you — your feedback was recorded.</p>}
      </div>}
    <p className="privacy-note">Demo count only — no cart page, purchase or payment. Counts unique saved options in this journey; resets on page reload, journey reset or profile change. Changing requirements or items requires review again; the saved count remains. Visualization is optional.</p>
  </section>;
}
