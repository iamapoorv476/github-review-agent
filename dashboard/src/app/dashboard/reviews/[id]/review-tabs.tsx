"use client";

import { useState } from "react";
import type { ReviewDetail } from "@/lib/data";
import { FindingCard } from "@/components/finding-card";
import { TraceStepItem } from "@/components/trace-step";

export function ReviewTabs({ review }: { review: ReviewDetail }) {
  const [tab, setTab] = useState<"findings" | "trace">("findings");
  return (
    <>
      <div className="mb-5 flex gap-0.5 border-b border-line-2" role="tablist">
        {(
          [
            ["findings", "Findings", String(review.findingsList.length)],
            ["trace", "Reasoning trace", `${review.trace.length} steps`],
          ] as const
        ).map(([key, label, n]) => (
          <button
            key={key}
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={`-mb-px border-b-2 px-3.5 pb-2.5 pt-2 text-[13.5px] font-semibold transition-colors ${
              tab === key ? "border-ink text-ink" : "border-transparent text-ink-3 hover:text-ink"
            }`}
          >
            {label} <span className="ml-1 font-mono text-[10.5px] text-ink-3">{n}</span>
          </button>
        ))}
      </div>

      {tab === "findings" ? (
        <div>
          {review.findingsList.length === 0 ? (
            <p className="voice text-[15px] text-ink-2">
              No findings were recorded for this review.
            </p>
          ) : (
            review.findingsList.map((f, i) => (
              <FindingCard key={f.id} finding={f} delay={0.03 + i * 0.06} />
            ))
          )}
        </div>
      ) : (
        <div className="trace-spine relative max-w-[780px] pl-7">
          {review.trace.length === 0 ? (
            <p className="voice text-[15px] text-ink-2">
              No reasoning trace was captured for this review.
            </p>
          ) : (
            review.trace.map((s, i) => (
              <TraceStepItem key={s.n} step={s} delay={0.03 + i * 0.05} />
            ))
          )}
        </div>
      )}
    </>
  );
}