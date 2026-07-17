"use client";

import { useEffect, useRef, useState } from "react";
import { SeverityBadge } from "./badges";

/**
 * The hero replay: the agent reviews PR #412 in front of the visitor.
 * Thoughts type out, tool calls appear, a critical finding lands, the
 * status flips to "Changes requested" — then it loops.
 */

type StepDef =
  | { kind: "thought"; text: string }
  | { kind: "action"; fn: string; arg: string }
  | { kind: "obs"; body: React.ReactNode; pause: number }
  | { kind: "finding" }
  | { kind: "done" };

const STEPS: StepDef[] = [
  {
    kind: "thought",
    text: "The title promises idempotent retries. Before judging anything, I need the shape of the change.",
  },
  { kind: "action", fn: "get_pr_diff", arg: "(pr=412)" },
  {
    kind: "obs",
    pause: 950,
    body: (
      <>
        8 files · +342 −87 · core logic in{" "}
        <span className="font-semibold text-lapis">services/payments/retry.py</span>
      </>
    ),
  },
  {
    kind: "thought",
    text: "A timestamp-based key smells like a collision. Who consumes these keys?",
  },
  { kind: "action", fn: "search_code", arg: '("idempotency_key")' },
  {
    kind: "obs",
    pause: 950,
    body: (
      <>
        clients/gateway.py:167{"  "}
        <span className="font-semibold text-lapis"># returns cached response on key match</span>
        {"\n"}→ colliding keys are silently swallowed
      </>
    ),
  },
  { kind: "finding" },
  { kind: "done" },
];

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export function ReplayHero() {
  const [visibleCount, setVisibleCount] = useState(0);
  const [typed, setTyped] = useState<Record<number, string>>({});
  const [done, setDone] = useState(false);
  const started = useRef(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      // reduced motion: show the completed review immediately
      setVisibleCount(STEPS.length);
      setTyped(
        Object.fromEntries(
          STEPS.map((s, i) => [i, s.kind === "thought" ? s.text : ""]),
        ),
      );
      setDone(true);
      return;
    }

    let cancelled = false;

    const typeThought = async (index: number, text: string) => {
      for (let i = 0; i <= text.length && !cancelled; i++) {
        setTyped((prev) => ({ ...prev, [index]: text.slice(0, i) }));
        await sleep(text[i - 1] === "." ? 90 : 22);
      }
    };

    const playOnce = async () => {
      setVisibleCount(0);
      setTyped({});
      setDone(false);
      await sleep(700);
      for (let i = 0; i < STEPS.length && !cancelled; i++) {
        const step = STEPS[i];
        setVisibleCount(i + 1);
        if (step.kind === "thought") {
          await typeThought(i, step.text);
          await sleep(260);
        } else if (step.kind === "action") {
          await sleep(620);
        } else if (step.kind === "obs") {
          await sleep(step.pause);
        } else if (step.kind === "finding") {
          await sleep(1500);
        } else {
          setDone(true);
          await sleep(4200);
        }
      }
    };

    const io = new IntersectionObserver(
      async (entries) => {
        if (!entries[0].isIntersecting || started.current) return;
        started.current = true;
        io.disconnect();
        while (!cancelled) await playOnce();
      },
      { threshold: 0.3 },
    );
    io.observe(el);

    return () => {
      cancelled = true;
      io.disconnect();
    };
  }, []);

  const show = (i: number) =>
    `transition-all duration-400 ${
      i < visibleCount ? "opacity-100 translate-y-0" : "opacity-0 translate-y-1.5"
    }`;

  return (
    <div
      ref={rootRef}
      className="flex min-h-[480px] flex-col overflow-hidden rounded-lg border border-line bg-raised shadow-lift max-sm:min-h-0"
      aria-label="A replay of the agent reviewing a real pull request"
    >
      <div className="flex items-center gap-2.5 border-b border-line bg-recess px-4 py-2.5 font-mono text-[11px] text-ink-2">
        <span className="pulse-dot h-[7px] w-[7px] flex-none rounded-full bg-verdigris" />
        <span>acme/checkout-service · PR #412</span>
        <span className="ml-auto">
          {done ? (
            <span className="rounded-full bg-rubric-wash px-2 py-0.5 font-bold text-rubric">
              Changes requested
            </span>
          ) : (
            "reviewing…"
          )}
        </span>
      </div>

      <div className="flex flex-1 flex-col gap-3.5 px-5 py-5">
        {STEPS.map((step, i) => (
          <div key={i} className={show(i)}>
            {step.kind === "thought" && (
              <span className="voice max-w-[46ch] text-base leading-relaxed text-ink">
                {typed[i] ?? ""}
                {i < visibleCount && (typed[i] ?? "").length < step.text.length && (
                  <span className="caret-blink -mb-0.5 ml-px inline-block h-4 w-px bg-rubric" />
                )}
              </span>
            )}
            {step.kind === "action" && (
              <span className="inline-flex items-center gap-2 rounded-md bg-ink px-3 py-1.5 font-mono text-[11.5px] text-[#E8EAE5]">
                <span className="font-semibold text-[#9DBBE8]">{step.fn}</span>
                <span className="text-[#B9BFC7]">{step.arg}</span>
              </span>
            )}
            {step.kind === "obs" && (
              <pre className="overflow-x-auto whitespace-pre border-l-2 border-line-2 pl-3 font-mono text-[11px] leading-[1.7] text-ink-2">
                {step.body}
              </pre>
            )}
            {step.kind === "finding" && (
              <div className="rounded-md border border-line border-l-[3px] border-l-rubric bg-[#FBFAF6] px-3.5 py-3">
                <div className="mb-1.5 flex items-center gap-2">
                  <SeverityBadge severity="critical" />
                  <span className="font-mono text-[11px] text-ink-3">
                    services/payments/retry.py : 87
                  </span>
                </div>
                <pre className="mb-2 overflow-x-auto rounded bg-add-wash px-2 py-1 font-mono text-[11.5px]">
                  {'+ key = f"{order_id}-{'}
                  <b className="font-bold text-rubric">int(time.time())</b>
                  {'}"'}
                </pre>
                <p className="voice text-[13.5px] leading-normal text-ink">
                  Two retries in the same second produce identical keys — the gateway drops the
                  second as a replay. Derive from order + attempt, not the clock.
                </p>
              </div>
            )}
            {step.kind === "done" && (
              <div className="flex items-center gap-2 text-[12.5px] font-semibold text-verdigris">
                ✓ Review posted to GitHub{" "}
                <span className="font-mono text-[11px] font-medium text-ink-3">
                  4 findings · 2m 14s
                </span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
