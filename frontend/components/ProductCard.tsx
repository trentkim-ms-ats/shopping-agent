"use client";

import { useState } from "react";
import { mediaUrl } from "@/lib/api";
import type { Card, Category } from "@/lib/types";

export function Silhouette({ category }: { category: Category }) {
  return <svg viewBox="0 0 200 160" aria-hidden="true" className="silhouette">
    {category === "jacket" || category === "midlayer" ? <>
      <path d="M74 27 50 39 20 100 45 115 67 76 64 142 136 142 133 76 155 115 180 100 150 39 126 27 112 40 88 40Z" fill="var(--cp-border-strong)" stroke="var(--cp-text-muted)" strokeWidth="1.5" />
      <path d="M75 27Q75 4 100 7Q125 4 125 27L112 40H88Z" fill="var(--cp-surface-soft)" stroke="var(--cp-text-muted)" strokeWidth="1.5" />
      <path d="M100 40V142M74 91V110M126 91V110" stroke="var(--cp-surface)" strokeWidth="2" fill="none" />
    </> : category === "pants" ? <>
      <path d="M61 15H139L148 145H109L100 65 91 145H52Z" fill="var(--cp-border-strong)" stroke="var(--cp-text-muted)" strokeWidth="1.5" />
      <path d="M62 27H138M78 29 66 47M122 29 134 47" stroke="var(--cp-surface)" strokeWidth="2" fill="none" />
    </> : <>
      <path d="M48 94Q48 31 102 31Q151 31 151 94Z" fill="var(--cp-border-strong)" stroke="var(--cp-text-muted)" strokeWidth="1.5" />
      <path d="M45 94H151Q182 121 114 122Q68 119 45 94Z" fill="var(--cp-surface-soft)" stroke="var(--cp-text-muted)" strokeWidth="1.5" />
      <path d="M103 32Q120 59 115 94" stroke="var(--cp-surface)" fill="none" />
    </>}
  </svg>;
}

export function ProductArt({ card, onRetryColor, busy = false }: {
  card: Card; onRetryColor?: (key: string) => void; busy?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  const color = card.color_image;
  const pending = color?.status === "queued" || color?.status === "running";
  return <>
    {card.image_url && !failed ?
      // eslint-disable-next-line @next/next/no-img-element
      <img className="product-photo" src={mediaUrl(card.image_url)} width={816} height={816}
        loading="lazy" alt={`AI-generated illustration of ${card.name}${color ? ` in ${color.color}` : ""}; color and details may differ`}
        onError={() => setFailed(true)} /> : <Silhouette category={card.category} />}
    <span className="art-label" role={failed || pending || color?.error ? "status" : undefined}>
      {failed ? "Image unavailable · category illustration" : pending ? `Preparing ${color.color} preview…` :
        color?.error ? color.error.message :
        card.image_url ? color ? `AI illustration · ${color.color} · details may differ` :
          "AI illustration · color/details may differ" : "Category illustration"}
      {color?.status === "failed" && color.key && onRetryColor &&
        <button className="color-retry" disabled={busy} onClick={() => { if (color.key) onRetryColor(color.key); }}
          title="Another image request may incur an additional charge.">Retry color image</button>}
    </span>
  </>;
}
