import Link from "next/link";
import { getReviews, getStats } from "@/lib/data";
import { VerdictBadge, FindingDots } from "@/components/badges";
import { ReReviewButton } from "@/components/rereview-dialog";

export const metadata = { title: "Marginalia — Reviews" };

function fmtDuration(sec: number) {
  return `${Math.floor(sec / 60)}m ${String(sec % 60).padStart(2, "0")}s`;
}

export default async function ReviewsPage() {
  const [stats, reviews] = await Promise.all([getStats(), getReviews()]);

  const statCards = [
    { k: "Reviews", v: String(stats.reviewsThisMonth), d: `${stats.reviewsRunning} running · ${stats.reviewsFailed} failed`, up: true },
    { k: "Findings surfaced", v: String(stats.findingsSurfaced), d: stats.findingsBreakdown, up: false },
    { k: "Median review time", v: stats.medianReview, d: "webhook → posted review", up: false },
    { k: "Spend to date", v: `$${stats.totalCostUsd.toFixed(2)}`, d: `${stats.reposActive} repos active`, up: false },
  ];

  return (
    <>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[23px] font-bold tracking-tight">Reviews</h1>
          <p className="mt-0.5 text-[13px] text-ink-2">
            Every pull request the agent has read, annotated, and signed off on.
          </p>
        </div>
        <ReReviewButton />
      </div>

      <div className="mb-6 grid grid-cols-4 gap-2.5 max-lg:grid-cols-2">
        {statCards.map((s) => (
          <div key={s.k} className="rounded-lg border border-line bg-raised px-4 py-3.5 shadow-card">
            <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-3">{s.k}</div>
            <div className="mt-1 text-[25px] font-bold tracking-tight tabular-nums">{s.v}</div>
            <div className={`text-[11.5px] ${s.up ? "text-verdigris" : "text-ink-2"}`}>{s.d}</div>
          </div>
        ))}
      </div>

      {/* Filters are display-only until wired to getReviews({ status, ... }). */}
      <div className="mb-3.5 flex flex-wrap items-center gap-2">
        {["All", "Changes requested", "Approved", "Running"].map((f, i) => (
          <button
            key={f}
            className={`rounded-full border px-3 py-1 text-[12.5px] font-medium transition-colors ${
              i === 0
                ? "border-ink bg-ink text-raised"
                : "border-line-2 text-ink-2 hover:border-ink-3 hover:text-ink"
            }`}
          >
            {f}
          </button>
        ))}
        <div className="ml-auto flex min-w-[210px] items-center gap-2 rounded-md border border-line-2 bg-raised px-2.5 py-1.5 text-[12.5px] text-ink-3 max-sm:hidden">
          ⌕ Search PRs, repos, findings…
          <kbd className="ml-auto rounded border border-line-2 px-1 font-mono text-[10px]">/</kbd>
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-line bg-raised shadow-card">
        <div className="grid h-9 grid-cols-[minmax(280px,1.7fr)_130px_150px_110px_90px] items-center gap-4 border-b border-line bg-recess px-4.5 text-[10.5px] font-semibold uppercase tracking-[0.13em] text-ink-3 max-md:hidden">
          <div>Pull request</div>
          <div>Verdict</div>
          <div>Findings</div>
          <div>Review time</div>
          <div className="text-right">When</div>
        </div>

        {reviews.length === 0 && (
          <div className="px-4.5 py-10 text-center text-[13px] text-ink-3">
            No reviews yet — open a pull request on a connected repo to see the agent work.
          </div>
        )}

        {reviews.map((r, i) => {
          const inner = (
            <>
              <div className="min-w-0">
                <div className="flex items-baseline gap-2 text-sm font-semibold">
                  <span className="flex-none font-mono text-[11.5px] font-medium text-ink-3">
                    #{r.prNumber}
                  </span>
                  <span className="truncate">{r.prTitle}</span>
                </div>
                <div className="mt-0.5 flex items-center gap-1.5 text-[11.5px] text-ink-3">
                  <span className="font-mono text-[10.5px] text-ink-2">{r.repo}</span>· {r.author} ·{" "}
                  {r.filesChanged} files ·{" "}
                  {r.verdict === "running"
                    ? "reading diff…"
                    : r.trigger === "mention"
                      ? "re-review via @marginalia"
                      : `trace ${r.traceSteps} steps`}
                </div>
              </div>
              <div className="max-md:hidden"><VerdictBadge verdict={r.verdict} /></div>
              <div className="max-md:hidden">
                <FindingDots counts={r.findings} cleanNote={r.cleanNote} />
              </div>
              <div className="font-mono text-[11.5px] text-ink-2 tabular-nums max-md:hidden">
                {fmtDuration(r.durationSec)}
              </div>
              <div className="text-right text-xs text-ink-3 max-md:hidden">{r.ago}</div>
            </>
          );
          const cls =
            "row-in grid w-full grid-cols-[minmax(280px,1.7fr)_130px_150px_110px_90px] items-center gap-4 border-b border-line px-4.5 py-3 text-left transition-colors last:border-b-0 hover:bg-[#F7F8F4] max-md:grid-cols-[1fr_auto]";
          const style = { animationDelay: `${0.02 + i * 0.04}s` };
          // Completed runs have a detail page; running/failed rows are not links.
          return r.verdict !== "running" ? (
            <Link key={r.id} href={`/dashboard/reviews/${r.id}`} className={`${cls} no-underline text-inherit`} style={style}>
              {inner}
            </Link>
          ) : (
            <div key={r.id} className={cls} style={style}>
              {inner}
            </div>
          );
        })}
      </div>
    </>
  );
}