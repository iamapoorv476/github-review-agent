/**
 * Marginalia — data layer, wired to the live FastAPI backend.
 *
 * This is the ONLY place the UI touches data. Every exported type is the
 * shape a component actually consumes; the fetchers derive/format those
 * shapes from the /api/* responses (snake_case → camelCase, ms → seconds,
 * timestamps → "3h ago", severity counts → verdict, etc).
 *
 * Design rule (per project owner): the UI renders only what the backend
 * persists. Fields the schema has no column for were removed rather than
 * faked — see NOTES at the bottom for what was dropped and why.
 *
 * Configure the API origin (defaults to the FastAPI dev server):
 *   # .env.local
 *   NEXT_PUBLIC_API_URL=http://localhost:8000
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------- types

/** UI severity set — what badge components render. */
export type Severity = "critical" | "warning" | "suggestion" | "nit";

/** Derived PR verdict — what VerdictBadge renders. */
export type Verdict = "approved" | "changes_requested" | "commented" | "running";

/** Trace step kind — what TraceStepItem renders. */
export type StepKind = "thought" | "record" | "verdict";

export interface SeverityCounts {
  critical: number;
  warning: number;
  suggestion: number;
  nit: number;
}

export interface Stats {
  reviewsThisMonth: number;
  reviewsRunning: number;
  reviewsFailed: number;
  findingsSurfaced: number;
  findingsBreakdown: string; // e.g. "3 critical · 5 warning · 8 suggestion"
  medianReview: string; // e.g. "1m 12s" or "—"
  reposActive: number;
  totalCostUsd: number;
}

export interface ReviewRow {
  id: string;
  prNumber: number;
  prTitle: string;
  repo: string; // full_name
  author: string;
  filesChanged: number;
  verdict: Verdict;
  trigger: string; // "opened" | "mention" | "synchronize" | ...
  traceSteps: number;
  findings: SeverityCounts;
  cleanNote?: string; // set when there are no findings
  durationSec: number;
  ago: string;
}

export interface Finding {
  id: string;
  severity: Severity;
  category: "security" | "performance" | "quality";
  file: string;
  line: number | null;
  note: string; // description, in the agent's voice
  fix: string | null; // suggestion
  codeSnippet: string | null;
  wasPosted: boolean;
  githubCommentId: number | null; // deep-link to the PR comment thread
}

export interface TraceStep {
  n: number;
  kind: StepKind;
  durationSec: number;
  tokens: number;
  thought: string; // content
  action?: { fn: string; arg: string }; // tool_call
  observation?: { summary: string; body: string }; // tool_result
}

export interface ReviewDetail extends ReviewRow {
  branch: { from: string; to: string };
  additions: number;
  deletions: number;
  model: string;
  tokensUsed: number;
  githubUrl: string | null;
  toolCalls: number;
  errorMessage: string | null;
  findings: SeverityCounts; // inherited row summary counts
  findingsList: Finding[]; // full findings for the tab
  trace: TraceStep[];
}

export interface RepoSettings {
  id: string;
  installationId: string; // needed for org-level PATCH; see note
  fullName: string;
  owner: string;
  name: string;
  isPrivate: boolean;
  defaultBranch: string;
  reviewEnabled: boolean;
  totalReviews: number;
  totalFindings: number;
  lastReviewAgo: string;
  accountLogin: string;
  reviewCategories: string[]; // installation-level: security/performance/quality
}

export interface ReviewFilters {
  status?: "queued" | "processing" | "completed" | "failed" | "cancelled";
  repo?: string;
  severity?: Severity;
  limit?: number;
  offset?: number;
}

// ---------------------------------------------------------------- helpers

const DB_TO_UI: Record<string, Severity> = {
  critical: "critical",
  high: "warning",
  medium: "suggestion",
  low: "nit",
};
const UI_TO_DB: Record<Severity, string> = {
  critical: "critical",
  warning: "high",
  suggestion: "medium",
  nit: "low",
};

export function toUiSeverity(db: string): Severity {
  return DB_TO_UI[db] ?? "nit";
}

function fmtAgo(iso: string | null): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const s = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 30) return `${d}d ago`;
  return new Date(iso).toLocaleDateString();
}

function fmtDurationStr(ms: number | null): string {
  if (ms == null) return "—";
  const sec = Math.round(ms / 1000);
  return `${Math.floor(sec / 60)}m ${String(sec % 60).padStart(2, "0")}s`;
}

/** completed run → verdict from severity counts; else from status. */
function toVerdict(status: string, critical: number, findings: number): Verdict {
  if (status === "queued" || status === "processing") return "running";
  if (status === "failed" || status === "cancelled") return "commented";
  if (critical > 0) return "changes_requested";
  if (findings > 0) return "commented";
  return "approved";
}

/* eslint-disable @typescript-eslint/no-explicit-any */

function severityCounts(r: any): SeverityCounts {
  return {
    critical: r.critical_count,
    warning: r.high_count,
    suggestion: r.medium_count,
    nit: r.low_count,
  };
}

function mapRow(r: any): ReviewRow {
  const counts = severityCounts(r);
  const isDone = r.status === "completed";
  return {
    id: r.id,
    prNumber: r.pull_request.pr_number,
    prTitle: r.pull_request.title,
    repo: r.repository.full_name,
    author: r.pull_request.author_login,
    filesChanged: r.pull_request.files_changed,
    verdict: toVerdict(r.status, r.critical_count, r.findings_count),
    trigger: r.trigger,
    traceSteps: r.reasoning_step_count,
    findings: counts,
    cleanNote:
      isDone && r.findings_count === 0 ? "Clean — no findings" : undefined,
    durationSec: r.duration_ms != null ? Math.round(r.duration_ms / 1000) : 0,
    ago: fmtAgo(r.completed_at ?? r.queued_at),
  };
}

/** backend step_type → the component's three visual kinds. */
function stepKind(t: string): StepKind {
  if (t === "finding") return "record";
  if (t === "summary") return "verdict";
  return "thought";
}

function mapStep(s: any): TraceStep {
  const step: TraceStep = {
    n: s.step_number,
    kind: stepKind(s.step_type),
    durationSec: s.duration_ms != null ? +(s.duration_ms / 1000).toFixed(1) : 0,
    tokens: s.tokens_used,
    thought: s.content,
  };
  if (s.step_type === "tool_call" && s.tool_name) {
    step.action = {
      fn: s.tool_name,
      arg: s.tool_input ? JSON.stringify(s.tool_input) : "",
    };
  }
  if (s.step_type === "tool_result" && s.tool_output_summary) {
    step.observation = {
      summary: `Observation from ${s.tool_name ?? "tool"}`,
      body: s.tool_output_summary,
    };
  }
  return step;
}

function mapFinding(f: any): Finding {
  return {
    id: f.id,
    severity: toUiSeverity(f.severity),
    category: f.category,
    file: f.file_path,
    line: f.line_number,
    note: f.description,
    fix: f.suggestion,
    codeSnippet: f.code_snippet,
    wasPosted: f.was_posted,
    githubCommentId: f.github_comment_id,
  };
}

function mapRepo(r: any): RepoSettings {
  return {
    id: r.id,
    installationId: r.installation_id,
    fullName: r.full_name,
    owner: r.owner,
    name: r.name,
    isPrivate: r.is_private,
    defaultBranch: r.default_branch,
    reviewEnabled: r.review_enabled,
    totalReviews: r.total_reviews,
    totalFindings: r.total_findings,
    lastReviewAgo: fmtAgo(r.last_reviewed_at),
    accountLogin: r.account_login,
    reviewCategories: r.review_categories,
  };
}

// ---------------------------------------------------------------- fetch

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status} on ${path}: ${body.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------- fetchers

export async function getStats(): Promise<Stats> {
  const s = await api<any>("/api/stats");
  const sev = s.findings_by_severity;
  const parts = [
    sev.critical && `${sev.critical} critical`,
    sev.high && `${sev.high} warning`,
    sev.medium && `${sev.medium} suggestion`,
    sev.low && `${sev.low} nit`,
  ].filter(Boolean);
  return {
    reviewsThisMonth: s.reviews_total,
    reviewsRunning: s.reviews_running,
    reviewsFailed: s.reviews_failed,
    findingsSurfaced: s.findings_total,
    findingsBreakdown: parts.length ? parts.join(" · ") : "none yet",
    medianReview: fmtDurationStr(s.median_review_ms),
    reposActive: s.repos_active,
    totalCostUsd: s.total_cost_usd,
  };
}

export async function getReviews(filters: ReviewFilters = {}): Promise<ReviewRow[]> {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.repo) params.set("repo", filters.repo);
  if (filters.severity) params.set("severity", UI_TO_DB[filters.severity]);
  params.set("limit", String(filters.limit ?? 50));
  params.set("offset", String(filters.offset ?? 0));

  const data = await api<any>(`/api/reviews?${params.toString()}`);
  return data.items.map(mapRow);
}

export async function getReview(id: string): Promise<ReviewDetail | null> {
  let r: any;
  try {
    r = await api<any>(`/api/reviews/${id}`);
  } catch (e) {
    if (e instanceof Error && e.message.includes("API 404")) return null;
    throw e;
  }
  const row = mapRow(r);
  return {
    ...row,
    branch: { from: r.pull_request.head_branch, to: r.pull_request.base_branch },
    additions: r.pull_request.lines_added,
    deletions: r.pull_request.lines_removed,
    model: r.model_used ?? "—",
    tokensUsed: r.input_tokens + r.output_tokens,
    githubUrl: r.review_comment_url,
    toolCalls: r.tool_calls_made,
    errorMessage: r.error_message,
    findingsList: r.findings.map(mapFinding),
    trace: r.reasoning_steps.map(mapStep),
  };
}

export interface InstalledRepo {
  id: string;
  fullName: string;
  isPrivate: boolean;
  defaultBranch: string;
  reviewEnabled: boolean;
}

export interface Installation {
  id: string;
  accountLogin: string;
  accountType: string; // "Organization" | "User"
  accountAvatarUrl: string | null;
  reviewEnabled: boolean;
  reviewCategories: string[];
  repositories: InstalledRepo[];
}

/**
 * Look up an installation by GitHub's numeric install id — used by the
 * /welcome page after GitHub redirects the user post-install. Returns null
 * if the webhook hasn't landed yet (the record is created asynchronously).
 */
export async function getInstallationByGithubId(
  githubInstallId: string | number
): Promise<Installation | null> {
  let r: any;
  try {
    r = await api<any>(`/api/installations/by-github-id/${githubInstallId}`);
  } catch (e) {
    if (e instanceof Error && e.message.includes("API 404")) return null;
    throw e;
  }
  return {
    id: r.id,
    accountLogin: r.account_login,
    accountType: r.account_type,
    accountAvatarUrl: r.account_avatar_url,
    reviewEnabled: r.review_enabled,
    reviewCategories: r.review_categories,
    repositories: r.repositories.map((repo: any) => ({
      id: repo.id,
      fullName: repo.full_name,
      isPrivate: repo.is_private,
      defaultBranch: repo.default_branch,
      reviewEnabled: repo.review_enabled,
    })),
  };
}

export async function getRepoSettings(): Promise<RepoSettings[]> {
  const repos = await api<any[]>("/api/repos");
  return repos.map(mapRepo);
}

export async function saveRepoSettings(
  repoId: string,
  updates: { reviewEnabled?: boolean }
): Promise<RepoSettings> {
  const repo = await api<any>(`/api/repos/${repoId}`, {
    method: "PATCH",
    body: JSON.stringify({ review_enabled: updates.reviewEnabled }),
  });
  return mapRepo(repo);
}

export async function saveInstallationSettings(
  installationId: string,
  updates: { reviewEnabled?: boolean; reviewCategories?: string[] }
): Promise<void> {
  await api(`/api/installations/${installationId}`, {
    method: "PATCH",
    body: JSON.stringify({
      review_enabled: updates.reviewEnabled,
      review_categories: updates.reviewCategories,
    }),
  });
}

/*
 * NOTES — fields intentionally dropped because the backend has no column:
 *   • Finding.lines[] (per-line diff), excerptLabel, noteEmphasis
 *       → backend stores only code_snippet (string) + description + suggestion.
 *   • Stats.acceptanceRate → developer_reaction column exists but is never
 *       written, so acceptance can't be computed yet.
 *   • ReviewDetail.summary prose → the agent posts a summary to GitHub but
 *       does not persist the text; use review_comment_url to link out.
 *   • ReviewDetail.filesRead → not tracked.
 * If you later add these columns, extend the schema + mapper here in tandem.
 */