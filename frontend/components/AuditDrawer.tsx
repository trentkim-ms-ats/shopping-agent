import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { Audit, Intent } from "@/lib/types";

export function AuditDrawer({ productId, intent, onClose }: { productId: string; intent?: Intent; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [data, setData] = useState<Audit | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    dialog.current?.showModal();
    let active = true;
    api<Audit>(`/demo/enrichment/${productId}`).then(value => { if (active) setData(value); }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [productId]);
  return <dialog ref={dialog} className="audit-dialog" onCancel={onClose}>
    <header><div><span className="eyebrow">EVIDENCE, NOT GUESSWORK</span><h2>How this recommendation was built</h2></div><button onClick={onClose} aria-label="Close audit">✕</button></header>
    {error && <p role="alert">{error}</p>}{!data && !error && <p role="status">Loading catalog evidence…</p>}
    {data && <>
      <p className="banner">{data.mode === "fixture" ? "Replay — simulated API outputs. These are fixture judgments." :
        data.run?.status === "completed" && data.accepted.length > 0 ?
          "Published attributes from separate OpenAI generation and judge calls. Not an OpenAI certification." :
          "No completed, published enrichment is demonstrated for this product. Source-only evidence applies."}</p>
      <h3>Your request → product evidence → unknowns</h3>
      <p>{intent ? `${intent.activity || "Outdoor"} · ${intent.season || "Any season"} · ${intent.priority?.replaceAll("_", " ") || "Balanced priorities"}` :
        "Compare the source evidence with your shopping needs."}</p>
      <div className="evidence-summary">{data.accepted.filter(a => ["benefits", "activities", "season_suitability", "use_cases"].includes(a.kind)).slice(0, 4).map(a =>
        <article key={a.attribute_id}><strong>{a.value}{a.support === "inferred" ? " · inferred" : ""}</strong>
          <blockquote>{a.evidence.map(e => e.quote).join(" · ")}</blockquote></article>)}</div>
      <p className="subtle">Waterproof and temperature ratings are not specified. Catalog size availability does not establish actual fit.</p>
      <h3>01 / Unchanged source</h3><h4>{data.raw.name}</h4><blockquote>{data.raw.description}</blockquote><p className="subtle">{data.raw.colors.join(", ")} · {data.raw.sizes.join(", ")}</p>
      <h3>02 / Proposed → independently reviewed → published</h3>
      {!data.run && <p>No enrichment run. Only source evidence is available.</p>}
      {data.run && <><p className="subtle">Run status: {data.run.status}</p>{data.run.candidates.attributes.map(a => {
        const judgment = data.run?.report.judgments.find(j => j.attribute_id === a.attribute_id);
        const published = data.accepted.some(p => p.attribute_id === a.attribute_id);
        return <article className="audit-claim" key={a.attribute_id}><div><strong>{a.value}</strong><span className={published ? "accepted" : "rejected"}>{published ? "Published" : judgment?.decision || "Quarantined"}</span></div>
          <small>{a.kind} · {a.support}</small>{a.evidence.map((e, i) => <blockquote key={i}>{e.field}: “{e.quote}”</blockquote>)}<p>{judgment?.reason || "Missing/invalid decision; not searchable."}</p></article>;
      })}<details><summary>Provenance</summary><pre>{JSON.stringify(data.run.report, null, 2)}</pre></details></>}
      <h3>03 / Adversarial validation test</h3><p className="subtle">{data.validation_test.label}. Expected outcome: reject; not a live judge result.</p>
      {data.validation_test_result && <p className="subtle">{data.validation_test_result.mode === "fixture" ? "Simulated test result" : "Independent live judge test"} · {data.validation_test_result.passed ? "passed" : "failed"}</p>}
      {data.validation_test.candidates.attributes.map(a => {
        const decision = data.validation_test_result?.judgments.find(j => j.attribute_id === a.attribute_id);
        return <div className="fixture-claim" key={a.attribute_id}><span>{a.value}</span><span className="rejected" title={decision?.reason}>{decision ? `${data.validation_test_result?.mode === "fixture" ? "Replay: " : ""}${decision.decision}` : "Expected: reject"}</span></div>;
      })}
      <p className="subtle">Exact quotations alone do not prove a claim. Moderation screens harmful content; the independent judge checks source support. Neither guarantees perfect safety or accuracy.</p>
    </>}
  </dialog>;
}
