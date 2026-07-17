import type { Severity, Verdict } from "@/lib/data";

const SEV_STYLES: Record<Severity, string> = {
  critical: "text-rubric bg-rubric-wash",
  warning: "text-gold bg-gold-wash",
  suggestion: "text-lapis bg-lapis-wash",
  nit: "text-ink-2 bg-slate-wash",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded font-mono text-[10.5px] font-bold tracking-[0.06em] px-1.5 py-px uppercase ${SEV_STYLES[severity]}`}
    >
      {severity}
    </span>
  );
}

const VERDICT_META: Record<Verdict, { label: string; cls: string; blink?: boolean }> = {
  approved: { label: "Approved", cls: "text-verdigris bg-verdigris-wash" },
  changes_requested: { label: "Changes req.", cls: "text-rubric bg-rubric-wash" },
  commented: { label: "Commented", cls: "text-gold bg-gold-wash" },
  running: { label: "Reviewing", cls: "text-lapis bg-lapis-wash", blink: true },
};

export function VerdictBadge({ verdict, long }: { verdict: Verdict; long?: boolean }) {
  const m = VERDICT_META[verdict];
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-[11.5px] font-semibold tracking-[0.015em] ${m.cls}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full bg-current ${m.blink ? "animate-pulse" : ""}`}
      />
      {long && verdict === "changes_requested" ? "Changes requested" : m.label}
    </span>
  );
}

export function FindingDots({
  counts,
  cleanNote,
}: {
  counts: { critical: number; warning: number; suggestion: number; nit: number };
  cleanNote?: string;
}) {
  if (cleanNote) {
    return <span className="text-xs font-medium text-verdigris">{cleanNote}</span>;
  }
  const entries: { key: Severity; n: number; cls: string }[] = [
    { key: "critical", n: counts.critical, cls: "text-rubric" },
    { key: "warning", n: counts.warning, cls: "text-gold" },
    { key: "suggestion", n: counts.suggestion, cls: "text-lapis" },
    { key: "nit", n: counts.nit, cls: "text-ink-3" },
  ];
  const visible = entries.filter((e) => e.n > 0);
  if (visible.length === 0) return <span className="font-mono text-[11px] text-ink-2">—</span>;
  return (
    <span className="flex items-center gap-1.5">
      {visible.map((e) => (
        <span
          key={e.key}
          className={`inline-flex items-center gap-1 font-mono text-[11px] font-semibold ${e.cls}`}
          title={`${e.n} ${e.key}`}
        >
          <i className="inline-block h-2 w-2 rounded-[2px] bg-current" />
          {e.n}
        </span>
      ))}
    </span>
  );
}
