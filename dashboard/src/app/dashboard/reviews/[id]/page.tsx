import Link from "next/link";
import { notFound } from "next/navigation";
import { getReview } from "@/lib/data";
import { VerdictBadge } from "@/components/badges";
import { ReviewTabs } from "./review-tabs";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const review = await getReview((await params).id);
  return { title: review ? `Marginalia — PR #${review.prNumber}` : "Marginalia" };
}

export default async function ReviewDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const review = await getReview((await params).id);
  if (!review) notFound();

  return (
    <>
      <nav className="mb-1.5 text-[12.5px] font-medium text-ink-3">
        <Link href="/dashboard" className="text-lapis no-underline hover:underline">
          Reviews
        </Link>{" "}
        / {review.repo} / #{review.prNumber}
      </nav>

      <header className="mb-5">
        <div className="flex flex-wrap items-baseline gap-2.5 text-[21px] font-bold tracking-tight">
          <span className="font-mono text-sm font-medium text-ink-3">#{review.prNumber}</span>
          {review.prTitle}
          <VerdictBadge verdict={review.verdict} long />
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-3.5 text-[12.5px] text-ink-2">
          <span>{review.author} wants to merge</span>
          <span className="rounded bg-recess px-1.5 py-0.5 font-mono text-[11px]">
            {review.branch.from}
          </span>
          <span>→</span>
          <span className="rounded bg-recess px-1.5 py-0.5 font-mono text-[11px]">
            {review.branch.to}
          </span>
          <span>{review.filesChanged} files</span>
          <span className="font-mono text-[11.5px] font-semibold text-verdigris">
            +{review.additions}
          </span>
          <span className="font-mono text-[11.5px] font-semibold text-rubric">
            −{review.deletions}
          </span>
          <span>reviewed {review.ago}</span>
        </div>
      </header>

      {/* run summary card — counts + model/tokens, links out to the posted review */}
      <div className="mb-6 grid grid-cols-[1fr_auto] gap-4.5 rounded-lg border border-line border-l-[3px] border-l-rubric bg-raised px-5.5 py-4.5 shadow-card max-lg:grid-cols-1">
        <div>
          <p className="voice max-w-[62ch] text-[17px] leading-relaxed">
            {review.verdict === "changes_requested" ? (
              <>
                The agent requested changes — it recorded{" "}
                <span className="font-medium text-rubric">
                  {review.findings.critical} critical
                </span>{" "}
                and {review.findings.warning} warning-level findings across{" "}
                {review.filesChanged} files.
              </>
            ) : review.verdict === "approved" ? (
              <>The agent read the diff and found nothing worth blocking on. Clean pass.</>
            ) : review.verdict === "running" ? (
              <>The agent is still reading this pull request…</>
            ) : (
              <>The agent left {review.findingsList.length} comments on this pull request.</>
            )}
          </p>
          <p className="mt-2.5 text-[11.5px] font-medium text-ink-3">
            <b className="font-semibold text-ink-2">¶ Marginalia</b> · model {review.model} ·{" "}
            {review.tokensUsed} tokens
            {review.errorMessage && (
              <span className="text-rubric"> · error: {review.errorMessage}</span>
            )}
          </p>
        </div>
        <div className="flex flex-col items-end gap-2 text-right max-lg:items-start max-lg:text-left">
          {review.githubUrl && (
            <a
              href={review.githubUrl}
              className="inline-flex items-center gap-2 rounded-md border border-line-2 bg-raised px-3.5 py-2 text-[13px] font-semibold no-underline hover:border-ink-3"
            >
              ↗ View on GitHub
            </a>
          )}
          <div className="font-mono text-[11px] leading-[1.8] text-ink-3">
            findings {review.findingsList.length} · steps {review.trace.length}
            <br />
            tools called {review.toolCalls}
          </div>
        </div>
      </div>

      <ReviewTabs review={review} />
    </>
  );
}