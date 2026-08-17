const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

/* ─── generic fetcher ─────────────────────────────────────── */
async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status} on ${path}: ${body}`);
  }
  return res.json();
}

/* ─── helpers ─────────────────────────────────────────────── */
function fmtDurationStr(ms: number | null | undefined): string {
  if (!ms) return "—";
  const m = Math.floor(ms / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  return `${m}m ${String(s).padStart(2, "0")}s`;
}

function fmtTimeAgo(iso: string | null | undefined): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

/* ─── types ───────────────────────────────────────────────── */
export interface Stats {
  reviewsThisMonth: number;
  reviewsRunning: number;
  reviewsFailed: number;
  findingsSurfaced: number;
  findingsBreakdown: string;
  medianReview: string;
  spendCents: number;
  activeRepos: number;
}

export type Verdict =
  | "changes_requested"
  | "approved"
  | "commented"
  | "reviewing"
  | "failed"
  | "queued";

export type Severity = "critical" | "high" | "medium" | "low";
export type Category = "security" | "performance" | "quality";

export interface Finding {
  id: string;
  severity: Severity;
  category: Category;
  title: string;
  description: string;
  suggestion: string | null;
  filePath: string;
  lineNumber: number | null;
  diffPosition: number | null;
  wasPosted: boolean;
}

export interface ReviewRow {
  id: string;
  status: string;
  verdict: Verdict;
  trigger: string;
  prNumber: number;
  prTitle: string;
  prAuthor: string;
  repoFullName: string;
  repoOwner: string;
  repoName: string;
  findingsCount: number;
  criticalCount: number;
  highCount: number;
  mediumCount: number;
  lowCount: number;
  durationStr: string;
  durationMs: number | null;
  queuedAt: string;
  completedAt: string | null;
  modelUsed: string | null;
  inputTokens: number;
  outputTokens: number;
  totalCostUsd: number;
  reasoningSteps: number;
  filesChanged: number;
  timeAgo: string;
}

export interface ReviewDetail extends ReviewRow {
  branch: { from: string; to: string };
  additions: number;
  deletions: number;
  model: string;
  tokensUsed: number;
  findings: Finding[];
  reasoningStepsList: ReasoningStep[];
}

export interface ReasoningStep {
  stepNumber: number;
  stepType: string;
  content: string;
  toolName: string | null;
  toolInput: Record<string, unknown> | null;
  toolOutputSummary: string | null;
  tokensUsed: number;
  durationMs: number | null;
}

export interface RepoSettings {
  id: string;
  fullName: string;
  owner: string;
  name: string;
  isPrivate: boolean;
  reviewEnabled: boolean;
  reviewCategories: string[];
  totalReviews: number;
  totalFindings: number;
  lastReviewAgo: string | null;
}

export interface Installation {
  id: string;
  accountLogin: string;
  accountType: string;
  accountAvatarUrl: string | null;
  reviewEnabled: boolean;
}

export interface ReviewFilters {
  status?: string;
  repo?: string;
  severity?: string;
  limit?: number;
  offset?: number;
}

/* ─── severity filter mapping ─────────────────────────────── */
const UI_TO_DB: Record<string, string> = {
  critical: "critical",
  high: "high",
  medium: "medium",
  low: "low",
  "changes requested": "changes_requested",
  approved: "approved",
  commented: "commented",
};

/* ─── mappers ─────────────────────────────────────────────── */
function mapRow(r: any): ReviewRow {
  return {
    id: r.id,
    status: r.status,
    verdict: r.verdict ?? "commented",
    trigger: r.trigger ?? "",
    prNumber: r.pr_number,
    prTitle: r.pr_title ?? "",
    prAuthor: r.pr_author ?? "",
    repoFullName: r.repo_full_name ?? "",
    repoOwner: r.repo_owner ?? "",
    repoName: r.repo_name ?? "",
    findingsCount: r.findings_count ?? 0,
    criticalCount: r.critical_count ?? 0,
    highCount: r.high_count ?? 0,
    mediumCount: r.medium_count ?? 0,
    lowCount: r.low_count ?? 0,
    durationStr: r.duration_str ?? "—",
    durationMs: r.duration_ms ?? null,
    queuedAt: r.queued_at ?? "",
    completedAt: r.completed_at ?? null,
    modelUsed: r.model_used ?? null,
    inputTokens: r.input_tokens ?? 0,
    outputTokens: r.output_tokens ?? 0,
    totalCostUsd: r.total_cost_usd ?? 0,
    reasoningSteps: r.reasoning_steps ?? 0,
    filesChanged: r.files_changed ?? 0,
    timeAgo: fmtTimeAgo(r.queued_at),
  };
}

function mapFinding(f: any): Finding {
  return {
    id: f.id,
    severity: f.severity,
    category: f.category,
    title: f.title,
    description: f.description,
    suggestion: f.suggestion ?? null,
    filePath: f.file_path,
    lineNumber: f.line_number ?? null,
    diffPosition: f.diff_position ?? null,
    wasPosted: f.was_posted ?? false,
  };
}

function mapReasoningStep(s: any): ReasoningStep {
  return {
    stepNumber: s.step_number,
    stepType: s.step_type,
    content: s.content,
    toolName: s.tool_name ?? null,
    toolInput: s.tool_input ?? null,
    toolOutputSummary: s.tool_output_summary ?? null,
    tokensUsed: s.tokens_used ?? 0,
    durationMs: s.duration_ms ?? null,
  };
}

function mapRepo(r: any): RepoSettings {
  return {
    id: r.id,
    fullName: r.full_name,
    owner: r.owner,
    name: r.name,
    isPrivate: r.is_private ?? false,
    reviewEnabled: r.review_enabled ?? true,
    reviewCategories: r.review_categories ?? [],
    totalReviews: r.total_reviews ?? 0,
    totalFindings: r.total_findings ?? 0,
    lastReviewAgo: r.last_reviewed_at ? fmtTimeAgo(r.last_reviewed_at) : null,
  };
}

/* ─── API functions ───────────────────────────────────────── */
export async function getStats(): Promise<Stats> {
  const s = await api<any>("/api/stats");
  const parts = [
    s.critical_count && `${s.critical_count} critical`,
    s.high_count && `${s.high_count} warning`,
    s.medium_count && `${s.medium_count} suggestion`,
    s.low_count && `${s.low_count} nit`,
  ].filter(Boolean);
  return {
    reviewsThisMonth: s.total_reviews ?? 0,
    reviewsRunning: s.running ?? 0,
    reviewsFailed: s.failed ?? 0,
    findingsSurfaced: s.total_findings ?? 0,
    findingsBreakdown: parts.length ? parts.join(" · ") : "none yet",
    medianReview: s.median_review_time ?? fmtDurationStr(s.median_review_time_ms),
    spendCents: Math.round((s.total_cost_usd ?? 0) * 100),
    activeRepos: s.active_repos ?? 0,
  };
}

export async function getReviews(
  filters: ReviewFilters = {}
): Promise<ReviewRow[]> {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.repo) params.set("repo", filters.repo);
  if (filters.severity) params.set("severity", UI_TO_DB[filters.severity] ?? filters.severity);
  params.set("limit", String(filters.limit ?? 50));
  params.set("offset", String(filters.offset ?? 0));
  const data = await api<any>(`/api/reviews?${params.toString()}`);
  const items = data.reviews ?? data.items ?? (Array.isArray(data) ? data : []);
  return items.map(mapRow);
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
    branch: {
      from: r.head_branch ?? r.pull_request?.head_branch ?? "",
      to: r.base_branch ?? r.pull_request?.base_branch ?? "",
    },
    additions: r.additions ?? r.pull_request?.lines_added ?? 0,
    deletions: r.deletions ?? r.pull_request?.lines_removed ?? 0,
    model: r.model_used ?? "—",
    tokensUsed: (r.input_tokens ?? 0) + (r.output_tokens ?? 0),
    findings: (r.findings ?? []).map(mapFinding),
    reasoningStepsList: (r.reasoning_steps ?? []).map(mapReasoningStep),
  };
}

export async function getRepoSettings(): Promise<RepoSettings[]> {
  const data = await api<any>("/api/repos");
  const repos = data.repos ?? (Array.isArray(data) ? data : []);
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
    accountAvatarUrl: r.account_avatar_url ?? null,
    reviewEnabled: r.review_enabled ?? true,
  };
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