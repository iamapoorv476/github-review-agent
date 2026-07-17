import type { TraceStep } from "@/lib/data";

/*
 * One node on the reasoning-trace spine.
 *   kind "thought"  → agent reasoning (also tool_call steps carry an action chip)
 *   kind "record"   → a create_finding step (rubric knot)
 *   kind "verdict"  → the agent's closing summary (verdigris knot)
 * Observations (tool results) render as a collapsible block.
 */
function ActionChip({ fn, arg }: { fn: string; arg: string }) {
  return (
    <span className="mt-2 inline-flex items-center gap-2 self-start rounded-md bg-ink px-2.5 py-1.5 font-mono text-[11.5px] text-[#E8EAE5]">
      <span className="font-semibold text-[#9DBBE8]">{fn}</span>
      {arg && <span className="text-[#B9BFC7]">{arg}</span>}
    </span>
  );
}

function Observation({ summary, body }: { summary: string; body: string }) {
  return (
    <details className="group mt-2">
      <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 rounded-md border border-line-2 bg-raised px-2.5 py-1 text-[11.5px] font-semibold text-ink-2 transition-colors hover:border-ink-3 [&::-webkit-details-marker]:hidden">
        <span className="text-[9px] transition-transform group-open:rotate-90">▸</span>
        {summary}
      </summary>
      <pre className="mt-2 overflow-x-auto rounded-md border border-line bg-raised px-3.5 py-3 font-mono text-[11.5px] leading-[1.75] text-ink-2">
        {body}
      </pre>
    </details>
  );
}

const KNOT: Record<TraceStep["kind"], string> = {
  thought: "border-ink-3 bg-paper",
  record: "border-rubric bg-rubric",
  verdict: "border-verdigris bg-verdigris",
};

const KIND_LABEL: Record<TraceStep["kind"], string> = {
  thought: "Thought",
  record: "Finding recorded",
  verdict: "Verdict",
};

export function TraceStepItem({ step, delay = 0 }: { step: TraceStep; delay?: number }) {
  return (
    <div className="row-in relative mb-6" style={{ animationDelay: `${delay}s` }}>
      {/* knot on the spine */}
      <span
        className={`absolute -left-[26px] top-[5px] h-[9px] w-[9px] rounded-full border-2 ${KNOT[step.kind]}`}
      />
      <div className="mb-1.5 flex items-baseline gap-2.5 text-[10.5px] font-semibold uppercase tracking-[0.13em] text-ink-3">
        Step {step.n} · {KIND_LABEL[step.kind]}
        <span className="ml-auto font-mono text-[10.5px] font-medium normal-case tracking-normal">
          {step.durationSec}s · {step.tokens} tok
        </span>
      </div>
      <p className="voice max-w-[60ch] text-[15.5px] leading-relaxed text-ink">{step.thought}</p>
      {step.action && <ActionChip fn={step.action.fn} arg={step.action.arg} />}
      {step.observation && (
        <Observation summary={step.observation.summary} body={step.observation.body} />
      )}
    </div>
  );
}