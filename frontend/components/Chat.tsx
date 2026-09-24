import { FormEvent, ReactNode, useEffect, useRef, useState } from "react";
import type { Card, Intent, Profile, ReplyKind, Routing } from "@/lib/types";
import { money } from "@/lib/api";
import { ProductArt } from "./ProductCard";

export type ChatEntry = {
  role: "user" | "assistant"; text: string; choices?: string[]; priorityChoice?: boolean;
  kind?: ReplyKind; items?: Card[]; itemsLabel?: string; routing?: Routing | null;
  extraItems?: Card[];
};

const TIER_LABEL: Record<string, string> = {
  light: "small model", standard: "reasoning model", deterministic: "no model call",
};
const SELECTION_KINDS: ReplyKind[] = ["selection", "confirmed", "feedback"];
const SIGNALS = [
  { key: "semantic", label: "Semantic similarity" }, { key: "lexical", label: "Lexical matching" },
  { key: "intent", label: "Intent" }, { key: "season", label: "Season" },
  { key: "profile", label: "Profile" }, { key: "popularity", label: "Fixed popularity" },
  { key: "total", label: "Weighted total" },
];
const ORDINALS = ["first", "second", "third", "fourth"];
const ordinalChoice = (verb: string, index: number) =>
  `${verb} the ${ORDINALS[index] || `option ${index + 1}`}`;

function InlineItems({ items, label, hint, tone, showScores, compact, selectedVariantIds, onAudit, onRetryColor, busy, selectVerb, onSelect }: {
  items: Card[]; label: string; hint?: string; tone?: "accent"; showScores?: boolean; onAudit: (id: string) => void;
  compact?: boolean;
  onRetryColor: (key: string) => void; busy: boolean;
  selectedVariantIds: Set<string>;
  selectVerb: string | null; onSelect: (text: string) => void;
}) {
  return <div className={`chat-items${tone === "accent" ? " accent" : ""}`}>
    <h3 className="chat-items-label">{label}</h3>
    {hint && <p className="chat-items-hint">{hint}</p>}
    <ol>{items.map((item, index) => <li key={item.variant.variant_id}>
      <span className="chat-item-rank">{index + 1}</span>
      <div className="chat-item-art">
        <ProductArt key={item.image_url || item.product_id} card={item} onRetryColor={onRetryColor} busy={busy} /></div>
      <div className="chat-item-body">
        <div className="chat-item-head">
          <div>
            <strong>{item.name}</strong>
            <span>{money(item.price_cents)} · {item.variant.color} / {item.variant.size} · <span className="stock">In stock</span></span>
          </div>
          {showScores && <details className="ranking-toggle">
            <summary>Ranking scores</summary>
            <div className="ranking-panel">
              <ul className="weight-list">
                {SIGNALS.filter(signal => item.scores[signal.key] !== undefined).map(signal =>
                  <li key={signal.key}><span>{signal.label}</span><b>{item.scores[signal.key].toFixed(3)}</b></li>)}
              </ul>
              <p className="subtle">Scores run 0.000–1.000 before weighting. Inactive signals are dropped and the rest re-normalized; hard constraints are applied first.</p>
            </div>
          </details>}
        </div>
        <p className="source-description">{item.description}</p>
        {!compact && item.match_summary && <div className="recommendation-reason">
          <h4>Why we recommend it</h4><p className="match-summary">{item.match_summary}</p></div>}
        {!compact && <div className="chips">{item.reasons.map(reason => <span key={reason.attribute_id}
          title={reason.evidence.map(e => e.quote).join(" · ")}>{reason.value}{reason.support === "inferred" ? " · inferred" : ""}</span>)}
          {!item.reasons.length && <span>Source-only match</span>}</div>}
        {!compact && item.tradeoff && <p className="tradeoff">{item.tradeoff}</p>}
        {item.compatibility && <p className="compatibility">{item.compatibility.category} {item.compatibility.color}</p>}
        <div className="chat-item-actions">
          {selectVerb && <button className="primary chat-item-select" disabled={busy || selectedVariantIds.has(item.variant.variant_id)}
            onClick={() => onSelect(ordinalChoice(selectVerb, index))}>
            {selectedVariantIds.has(item.variant.variant_id) ? "Selected" :
              selectVerb === "Add" ? "Add to selection" : "Select this jacket"}</button>}
          {selectVerb && !selectedVariantIds.has(item.variant.variant_id) &&
            <span className="card-cue">Or say “{ordinalChoice(selectVerb, index).toLowerCase()}” in the chat.</span>}
          <button className="text-button" onClick={() => onAudit(item.product_id)}>Why this match ↗</button>
        </div>
      </div>
    </li>)}</ol>
  </div>;
}

/** Ordinal picks now live on each product card, so they are dropped from the chip row. */
function isPrompt(entry: ChatEntry) {
  return entry.role === "assistant" && (entry.kind === "clarify" || entry.text.trim().endsWith("?"));
}

function remainingChoices(entry: ChatEntry) {
  const choices = entry.choices || [];
  const onCard = new Set<string>();
  if (entry.kind === "results") entry.items?.forEach((_, index) => onCard.add(ordinalChoice("Choose", index)));
  if (entry.kind === "complements") entry.items?.forEach((_, index) => onCard.add(ordinalChoice("Add", index)));
  entry.extraItems?.forEach((_, index) => onCard.add(ordinalChoice("Add", index)));
  return choices.filter(choice => !onCard.has(choice));
}

export function Chat({ profile, intent, entries, busy, onSend, onAudit,
  selection, preview, selectedVariantIds, onRetryColor }: {
  profile: Profile; intent: Intent; entries: ChatEntry[]; busy: boolean;
  onSend: (text: string, priorityChoice?: boolean) => void; onAudit: (id: string) => void;
  selection: ReactNode; preview: ReactNode;
  selectedVariantIds: string[];
  onRetryColor: (key: string) => void;
}) {
  const [text, setText] = useState("");
  const bottom = useRef<HTMLDivElement>(null);
  const messages = useRef<HTMLDivElement>(null);
  const selectedSet = new Set(selectedVariantIds);
  useEffect(() => {
    requestAnimationFrame(() => {
      messages.current?.scrollTo({ top: messages.current.scrollHeight, behavior: "smooth" });
      bottom.current?.scrollIntoView({ block: "end", behavior: "smooth" });
    });
  }, [entries, busy, selection, preview]);
  function submit(e: FormEvent) { e.preventDefault(); if (text.trim()) { onSend(text.trim()); setText(""); } }
  const lastOf = (kinds: ReplyKind[]) => {
    for (let index = entries.length - 1; index >= 0; index -= 1) {
      const kind = entries[index].kind;
      if (kind && kinds.includes(kind)) return index;
    }
    return -1;
  };
  const selectionIndex = lastOf(SELECTION_KINDS);
  const previewIndex = lastOf(["preview"]);
  const previewAnchor = previewIndex >= 0 ? previewIndex : selectionIndex;
  return <section className="conversation" aria-label="Shopping conversation">
    <div className="conversation-head">
      <div className="profile"><div className="avatar">{profile.display_name[0]}</div>
        <div><strong>Hello, {profile.display_name}</strong><p>Synthetic shopper profile</p></div></div>
      <div className="constraints"><span>Size <b>{intent.size || "Any"}</b></span><span>Budget <b>{intent.max_price_cents === null ? "Any" : money(intent.max_price_cents)}</b></span><span>Season <b>{intent.season || "Any"}</b></span><span>Priority <b>{intent.priority ? intent.priority.replaceAll("_", " ") : "Not set"}</b></span></div>
    </div>
    <div className="chat-messages" aria-live="polite" ref={messages}>
      {entries.map((entry, index) => <div key={index} className={`chat-message ${entry.role}${isPrompt(entry) ? " prompt" : ""}`}>
        <small className="chat-speaker">
          <span className="speaker-icon" aria-hidden="true">{entry.role === "user" ? profile.display_name[0] : "✦"}</span>
          <span className="speaker-name">{entry.role === "user" ? profile.display_name : "Trailshop AI"}</span>
          {entry.routing?.model ?
            <em className="routing-badge" title={`Model: ${entry.routing.model}${entry.routing.escalated ? " (escalated after a failed small-model turn)" : ""}`}>{TIER_LABEL[entry.routing.tier]}{entry.routing.escalated ? " · escalated" : ""}</em> : null}</small>
        <p className={isPrompt(entry) ? "chat-prompt" : undefined}>{entry.text}</p>
        {entry.items && entry.items.length > 0 &&
          <InlineItems items={entry.items} label={entry.itemsLabel || "Shown to you"} onAudit={onAudit}
            onRetryColor={onRetryColor} busy={busy} onSelect={onSend}
            selectedVariantIds={selectedSet}
            showScores={entry.kind === "results"}
            selectVerb={entry.kind === "complements" ? "Add" : entry.kind === "results" ? "Choose" : null} />}
        {entry.extraItems && entry.extraItems.length > 0 &&
          <InlineItems items={entry.extraItems} label="Completes the outfit" tone="accent"
            hint="Recommended from other categories to pair with your jacket."
            onAudit={onAudit} onRetryColor={onRetryColor} busy={busy} onSelect={onSend}
            selectedVariantIds={selectedSet} compact selectVerb="Add" />}
        {index === selectionIndex && selection}
        {index === previewAnchor && preview}
        {remainingChoices(entry).length > 0 && <div className="choices">{remainingChoices(entry).map(choice => <button key={choice}
          disabled={busy || (entry.priorityChoice === true && intent.priority !== null)}
          onClick={() => onSend(choice, entry.priorityChoice)}>{choice}</button>)}</div>}
      </div>)}
      {busy && <div className="chat-message assistant thinking" role="status" aria-live="polite">
        <small className="chat-speaker">
          <span className="speaker-icon" aria-hidden="true">✦</span>
          <span className="speaker-name">Trailshop AI</span>
        </small>
        <p>Thinking through your request<span className="thinking-dots" aria-hidden="true"><i /><i /><i /></span></p>
      </div>}<div ref={bottom} />
    </div>
    <form onSubmit={submit}><label className="sr-only" htmlFor="message">Reply to your trail guide</label>
      <textarea id="message" maxLength={2000} value={text} onChange={e => setText(e.target.value)}
        placeholder="Answer here — every choice is made in this conversation…" rows={1} disabled={busy} />
      <button className="primary" type="submit" aria-label="Send message" disabled={busy || !text.trim()}>Send</button></form>
  </section>;
}
