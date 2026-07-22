import type { Finding } from "@/lib/data";
import { SeverityBadge } from "./badges";

/*
 * Renders a single finding: the code snippet the agent flagged (if any),
 * joined by a dashed leader line to its margin note in the agent's voice.
 *
 * Backend provides code_snippet as a plain string (not a structured diff),
 * so the excerpt is rendered as-is rather than as add/del rows.
 */
export function FindingCard({
  finding,
  delay = 0,
  prUrl,
}: {
  finding: Finding;
  delay?: number;
  /** e.g. https://github.com/owner/repo/pull/15 — for the link-out */
  prUrl?: string;
}) {
  // Deep-link to the exact review-comment thread when we know its id;
  // otherwise fall back to the PR itself.
  const commentUrl = prUrl
    ? finding.githubCommentId != null
      ? `${prUrl}#discussion_r${finding.githubCommentId}`
      : prUrl
    : null;
  const loc = finding.line != null ? `${finding.file} : ${finding.line}` : finding.file;
  return (
    <div className="row-in mb-6" style={{ animationDelay: `${delay}s` }}>
      <div className="mb-2 flex flex-wrap items-center gap-2.5">
        <SeverityBadge severity={finding.severity} />
        <span className="font-mono text-xs text-ink-2">
          <b className="font-semibold text-ink">{finding.file}</b>
          {finding.line != null && <> : {finding.line}</>}
        </span>
        <span className="rounded bg-recess px-1.5 py-px font-mono text-[10.5px] text-ink-3">
          {finding.category}
        </span>
        {!finding.wasPosted && (
          <span className="rounded bg-recess px-1.5 py-px font-mono text-[10.5px] text-ink-3">
            not posted to PR
          </span>
        )}
      </div>
      <div className="grid grid-cols-[minmax(0,1.55fr)_minmax(230px,1fr)] items-start max-lg:grid-cols-1">
        {/* code excerpt (optional) */}
        {finding.codeSnippet ? (
          <div className="overflow-x-auto rounded-l-lg border border-line bg-raised shadow-card max-lg:rounded-b-none max-lg:rounded-t-lg">
            <div className="border-b border-line bg-recess px-3 py-1.5 font-mono text-[10.5px] text-ink-3">
              {loc}
            </div>
            <pre className="whitespace-pre px-3.5 py-3 font-mono text-xs leading-[1.9] text-ink-2">
              {finding.codeSnippet}
            </pre>
          </div>
        ) : (
          <div className="flex items-center rounded-l-lg border border-line bg-raised px-3.5 py-3 font-mono text-[11px] text-ink-3 shadow-card max-lg:rounded-b-none max-lg:rounded-t-lg">
            {loc}
          </div>
        )}
        {/* margin note, joined by a dashed leader line */}
        <div className="leader relative self-stretch rounded-r-lg border border-l-0 border-line bg-gradient-to-b from-[#FBFAF6] to-[#F8F7F2] px-4 py-3.5 max-lg:rounded-b-lg max-lg:rounded-t-none max-lg:border-l max-lg:border-t-0 max-lg:before:hidden">
          <span className="voice block text-[14.5px] leading-relaxed text-ink">
            {finding.note}
          </span>
          {finding.fix && (
            <div className="mt-2.5 overflow-x-auto whitespace-pre-wrap rounded-md bg-recess px-2.5 py-2 font-mono text-[11px] text-ink-2">
              <b className="font-semibold text-verdigris">+ </b>
              {finding.fix}
            </div>
          )}
          {/* Acting on a finding (applying the suggestion, resolving the
              thread) is GitHub's job — link to the exact comment instead of
              faking those actions here. */}
          {finding.wasPosted && commentUrl && (
            <div className="mt-3">
              <a
                href={commentUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded border border-lapis-wash bg-lapis-wash px-2 py-0.5 text-[11px] font-semibold text-lapis no-underline hover:bg-[#dbe5f3]"
              >
                ↗ View on PR
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}