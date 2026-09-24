"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Alternative, Card, ColorImage, Health, Job, Reply, SelectionState, Session } from "@/lib/types";
import { Chat, type ChatEntry } from "@/components/Chat";
import { Preview } from "@/components/Preview";
import { AuditDrawer } from "@/components/AuditDrawer";
import { SelectionSummary } from "@/components/SelectionSummary";
import { Evidence, type Baseline } from "@/components/Evidence";
const WELCOME: ChatEntry = { role: "assistant", text: "A good trail starts with the right layers. Tell me what you’re heading out for — I’ll help you narrow it down.", choices: ["I need a jacket for hiking this fall."] };

export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [entries, setEntries] = useState<ChatEntry[]>([WELCOME]);
  const [cards, setCards] = useState<Card[]>([]);
  const [complements, setComplements] = useState<Card[]>([]);
  const [selected, setSelected] = useState<Card[]>([]);
  const [selectionState, setSelectionState] = useState<SelectionState | null>(null);
  const [demoCartVariantIds, setDemoCartVariantIds] = useState<string[]>([]);
  const [alternatives, setAlternatives] = useState<Alternative[]>([]);
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [auditId, setAuditId] = useState<string | null>(null);
  const [retrievalMode, setRetrievalMode] = useState("");
  const [baseline, setBaseline] = useState<Baseline | null>(null);
  const [baselineQuery, setBaselineQuery] = useState("hiking jacket fall light rain");
  const [pollingPaused, setPollingPaused] = useState(false);
  const [colorPollingPaused, setColorPollingPaused] = useState(false);
  const [pendingMessage, setPendingMessage] = useState<{ request_id: string; text: string; priority_choice: boolean } | null>(null);
  const conversationStarted = entries.length > 1;
  const pendingImage = useRef<{ request_id: string; variant_ids: string[] } | null>(null);
  const operation = useRef(false);
  const initialized = useRef(false);
  const workspace = useRef<HTMLDivElement>(null);
  const scrolledToChat = useRef(false);
  const scrollToConversation = useCallback((behavior: ScrollBehavior = "smooth") => {
    const target = workspace.current;
    if (!target) return;
    const header = document.querySelector<HTMLElement>(".site-header");
    const headerHeight = header?.offsetHeight || 50;
    const top = target.getBoundingClientRect().top + window.scrollY - headerHeight - 8;
    window.scrollTo({ top: Math.max(0, top), behavior });
  }, []);

  const initialize = useCallback(async (profile = "alex") => {
    if (operation.current) return;
    operation.current = true; setBusy(true); setError("");
    try {
      if (session) await api(`/sessions/${session.session_id}/try-ons`, undefined, "DELETE");
      const [h, s] = await Promise.all([api<Health>("/health"), api<Session>("/sessions", { profile_id: profile })]);
      setHealth(h); setSession(s); setEntries([WELCOME]); setCards([]); setComplements([]);
      setSelected([]); setJob(null); setBaseline(null); setRetrievalMode(""); setPendingMessage(null); pendingImage.current = null;
      setSelectionState(null); setAlternatives([]); setDemoCartVariantIds([]);
      scrolledToChat.current = false;
      setPollingPaused(false);
      setColorPollingPaused(false);
    } catch (e) { setError((e as Error).message); }
    finally { operation.current = false; setBusy(false); }
  }, [session]);
  useEffect(() => {
    if (!initialized.current) { initialized.current = true; void initialize(); }
  }, [initialize]);
  useEffect(() => {
    if (scrolledToChat.current || entries.length <= 1) return;
    scrolledToChat.current = true;
    requestAnimationFrame(() => scrollToConversation());
  }, [entries.length, scrollToConversation]);
  useEffect(() => {
    if (job?.status !== "completed" || !job.expires_at) return;
    const timer = setTimeout(() => setJob(previous => previous?.job_id === job.job_id ? {
        ...previous, status: "failed", image_url: null,
        error: { code: "TRY_ON_EXPIRED", message: "Private preview expired. Generate a new try-on.", retryable: true },
      } : previous), Math.max(0, Date.parse(job.expires_at) - Date.now()));
    return () => clearTimeout(timer);
  }, [job]);

  useEffect(() => {
    if (!session || pollingPaused || !job || !["queued", "running"].includes(job.status)) return;
    let cancelled = false;
    const started = Date.now();
    const timer = setInterval(async () => {
      if (Date.now() - started > 120000) { setPollingPaused(true); return; }
      try {
        const next = await api<Job>(`/sessions/${session.session_id}/outfits/${job.job_id}`);
        if (!cancelled) setJob(next);
      } catch (e) { if (!cancelled) { setError((e as Error).message); setPollingPaused(true); } }
    }, 2000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [session, job?.job_id, job?.status, pollingPaused]); // eslint-disable-line react-hooks/exhaustive-deps

  const applyColorImage = useCallback((image: ColorImage) => {
    const update = (items: Card[]) => items.map(card => card.color_image?.key === image.key ?
      { ...card, color_image: image, image_url: image.image_url } : card);
    setCards(update); setComplements(update); setSelected(update);
    setEntries(previous => previous.map(entry =>
      [...(entry.items || []), ...(entry.extraItems || [])].some(card => card.color_image?.key === image.key) ?
        { ...entry, items: entry.items && update(entry.items),
          extraItems: entry.extraItems && update(entry.extraItems) } : entry));
  }, []);
  const pendingColorKeys = [...new Set([...cards, ...complements, ...selected,
    ...entries.flatMap(entry => [...(entry.items || []), ...(entry.extraItems || [])])].flatMap(card =>
    card.color_image?.key && ["queued", "running"].includes(card.color_image.status) ?
      [card.color_image.key] : []))].sort().join(",");
  useEffect(() => {
    if (!pendingColorKeys || colorPollingPaused) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const images = await Promise.all(pendingColorKeys.split(",").map(key =>
          api<ColorImage>(`/product-color-images/${key}`)));
        if (cancelled) return;
        images.forEach(applyColorImage);
        timer = setTimeout(poll, 2000);
      } catch (e) {
        if (!cancelled) {
          setError(`Color image status: ${(e as Error).message}`);
          setColorPollingPaused(true);
        }
      }
    }
    timer = setTimeout(poll, 2000);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [pendingColorKeys, colorPollingPaused, applyColorImage]);

  function retryColor(key: string) {
    void run(async () => {
      applyColorImage(await api<ColorImage>(`/product-color-images/${key}/retry`, {}));
      setColorPollingPaused(false);
    });
  }

  async function run(action: () => Promise<void>) {
    if (operation.current) return;
    operation.current = true; setBusy(true); setError("");
    try { await action(); } catch (e) { setError((e as Error).message); }
    finally { operation.current = false; setBusy(false); }
  }
  function relax(alternative: Alternative) {
    if (!session) return;
    scrolledToChat.current = true;
    scrollToConversation();
    void run(async () => {
      const value = await api<{ results: Card[]; constraints: Session["intent"]; selection_state: SelectionState;
        alternatives: Alternative[]; mode: string }>(`/sessions/${session.session_id}/relax`, { alternative_id: alternative.id });
      setSession({ ...session, intent: value.constraints }); setCards(value.results);
      setAlternatives(value.alternatives); setSelectionState(value.selection_state); setRetrievalMode(value.mode);
      setComplements([]); setJob(null); setBaseline(null); pendingImage.current = null;
      setEntries(previous => [...previous, { role: "user", text: alternative.label },
        { role: "assistant", kind: "results", items: value.results, itemsLabel: "Updated shortlist",
          routing: { tier: "deterministic", model: null, reasoning_effort: null, escalated: false },
          text: `Applied only your chosen change. ${value.results.length} matches shown; other requirements are unchanged.` }]);
    });
  }
  // Chips are ordinary replies, except the offered constraint changes, which are applied verbatim.
  function answer(text: string, priorityChoice = false) {
    const alternative = alternatives.find(option => option.label === text);
    if (alternative) { relax(alternative); return; }
    send(text, false, priorityChoice);
  }
  function send(text: string, retry = false, priorityChoice = false) {
    if (!session) return;
    if (!retry) {
      scrolledToChat.current = true;
      scrollToConversation();
      setTimeout(() => scrollToConversation(), 180);
    }
    void run(async () => {
      const body = retry && pendingMessage ? pendingMessage :
        { request_id: crypto.randomUUID(), text, priority_choice: priorityChoice };
      setPendingMessage(body);
      if (!retry) setEntries(previous => [...previous, { role: "user", text }]);
      const response = await api<Reply>(`/sessions/${session.session_id}/messages`, body);
      setPendingMessage(null);
      const kind = response.reply.kind;
      const cardList = response.cards || [];
      const complementList = response.complements || [];
      const selectedList = response.selected || [];
      const alternativeList = response.alternatives || [];
      const shown = kind === "complements" ? complementList :
        kind === "selection" ? selectedList :
        kind === "results" ? cardList : [];
      const label = kind === "complements" ? "Complementary picks" :
        kind === "selection" ? "Now in your selection" : "Your shortlist";
      const offered = kind === "results" && !cardList.length && alternativeList.length ?
        alternativeList.map(option => option.label) : response.reply.choices;
      setEntries(previous => [...previous, {
        role: "assistant", text: response.reply.message, kind, items: shown, itemsLabel: label,
        extraItems: kind === "selection" ? complementList : [],
        routing: response.routing, choices: offered, priorityChoice: kind === "clarify",
      }]);
      setSession({ ...session, intent: response.constraints });
      setSelectionState(response.selection_state);
      if (JSON.stringify(session.intent) !== JSON.stringify(response.constraints)) {
        setJob(null); setComplements([]); setBaseline(null); pendingImage.current = null;
      }
      if (kind === "results" || cardList.length > 0) setCards(cardList);
      if (complementList.length) setComplements(complementList);
      if (selectedList.length) { setSelected(selectedList); setJob(null); setPollingPaused(false); pendingImage.current = null; }
      if (response.job) { setJob(response.job); setPollingPaused(false); }
      if (kind === "confirmed") {
        const items = response.selection_state?.items || [];
        setDemoCartVariantIds(previous =>
          [...new Set([...previous, ...items.map(item => item.variant_id)])]);
      }
      if (response.retrieval_mode) setRetrievalMode(response.retrieval_mode);
      if (kind === "results") setAlternatives(alternativeList);
    });
  }
  function removePreview() {
    if (!session) return;
    void run(async () => {
      await api(`/sessions/${session.session_id}/try-ons`, undefined, "DELETE");
      setJob(null); setPollingPaused(false);
      pendingImage.current = null;
    });
  }
  return <>
    <header className="site-header"><Link href="/" className="brand"><span>↟</span> trailshop<span className="brand-period">.</span></Link>
      <div className="header-right"><span className="demo-label">SYNTHETIC DEMO</span>
        <div className="demo-cart" role="status" aria-live="polite" aria-atomic="true"
          aria-label={`Demo cart: ${demoCartVariantIds.length} ${demoCartVariantIds.length === 1 ? "item" : "items"}`}
          title="Demo count only — no cart page, purchase or payment. Resets with this journey or page reload.">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <path d="M2 3h3l3 12h11l3-9H6M8 15l-1 3h13" />
            <circle cx="9" cy="21" r="1" /><circle cx="18" cy="21" r="1" />
          </svg><span className="demo-cart-count">{demoCartVariantIds.length}</span>
        </div>
        <button disabled={busy} onClick={() => void initialize(session?.profile.profile_id)}>Reset journey ↻</button></div></header>
    {health?.mode === "fixture" && <div className="replay-banner">Replay — simulated API outputs · no live inference or content screening · static image fixture</div>}
    {!conversationStarted && <div className="intro"><div><span className="eyebrow">LESS SEARCHING. MORE OUT THERE.</span><h1>Your next trail starts here.</h1><p>Thoughtful layers. Clear choices. Recommendations you can trace.</p></div><div className="season-mark">FIELD NOTES / 01<br /><strong>Autumn, considered.</strong><span>Fixed Northern Hemisphere demo</span></div></div>}
    {error && <div role="alert" className="error-banner"><span>{error}</span>{pendingMessage && <button disabled={busy} onClick={() => send(pendingMessage.text, true)}>Retry message</button>}{colorPollingPaused && <button onClick={() => { setColorPollingPaused(false); setError(""); }}>Resume color image status</button>}{!session && <button disabled={busy} onClick={() => void initialize()}>Reconnect</button>}<button aria-label="Dismiss error" onClick={() => setError("")}>✕</button></div>}
    {session && !conversationStarted && <Evidence cards={cards} retrievalMode={retrievalMode} baseline={baseline} baselineQuery={baselineQuery}
      profileId={session.profile.profile_id} busy={busy} onAudit={setAuditId} onBaselineQuery={setBaselineQuery}
      onBaselineSubmit={() => void run(async () => setBaseline(await api<Baseline>(`/sessions/${session.session_id}/baseline?q=${encodeURIComponent(baselineQuery)}`)))}
      onProfile={value => void initialize(value)} />}
    {session ? <div className="workspace" ref={workspace}>
      <Chat profile={session.profile} intent={session.intent} entries={entries} busy={busy}
        onSend={answer} onAudit={setAuditId} onRetryColor={retryColor}
        selectedVariantIds={selected.map(item => item.variant.variant_id)}
        selection={selectionState && selected.length > 0 ? <SelectionSummary state={selectionState}
          feedbackRecorded={selectionState.feedback_recorded}
          savedToCart={selectionState.confirmed && selectionState.items.every(item => demoCartVariantIds.includes(item.variant_id))} /> : null}
        preview={job ? <Preview items={selected} job={job} busy={busy} pollingPaused={pollingPaused}
          onCheck={() => setPollingPaused(false)} onRemovePreview={removePreview} replay={health?.mode === "fixture"}
          canPreview={selectionState?.can_preview || false} onRetryColor={retryColor} /> : null} />
    </div> : <main className="connecting" role="status">{busy ? "Connecting to your local Trailshop API…" : "Start the API, then reconnect to begin."}</main>}
    <footer>TRAILSHOP / A FICTIONAL OUTDOOR RETAILER <span>No real inventory, checkout or performance guarantees.</span></footer>
    {auditId && <AuditDrawer key={auditId} productId={auditId} intent={session?.intent} onClose={() => setAuditId(null)} />}
  </>;
}
