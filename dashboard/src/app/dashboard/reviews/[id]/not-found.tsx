import Link from "next/link";

export default function ReviewNotFound() {
  return (
    <div className="mx-auto max-w-md pt-24 text-center">
      <div className="voice text-5xl text-rubric" aria-hidden="true">¶</div>
      <h1 className="mt-4 text-xl font-bold tracking-tight">No review here</h1>
      <p className="mt-2 text-sm leading-relaxed text-ink-2">
        This review doesn&rsquo;t exist yet — in mock mode only PR #412 has a full trace. Wire the
        API in <code className="rounded bg-recess px-1 font-mono text-xs">lib/data.ts</code> to load
        real reviews.
      </p>
      <Link
        href="/dashboard"
        className="mt-6 inline-flex items-center gap-2 rounded-md border border-line-2 bg-raised px-4 py-2 text-[13px] font-semibold no-underline hover:border-ink-3"
      >
        ← Back to reviews
      </Link>
    </div>
  );
}
