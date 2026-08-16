"use client";

import { useState, useEffect } from "react";

/* ─── types ──────────────────────────────────────────────── */
export interface RepoSettings {
  id: string;
  full_name: string;
  owner: string;
  name: string;
  is_private: boolean;
  review_enabled: boolean;
  review_categories: string[];
  total_reviews: number;
  total_findings: number;
  last_reviewed_at: string | null;
}

interface ConnectInfo {
  api_key: string;
  api_url: string;
  mcp_config: Record<string, unknown>;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

/* ─── helpers ────────────────────────────────────────────── */
function CategoryBadge({ label }: { label: string }) {
  const colours: Record<string, string> = {
    security: "bg-red-100 text-red-700 border-red-200",
    performance: "bg-orange-100 text-orange-700 border-orange-200",
    quality: "bg-blue-100 text-blue-700 border-blue-200",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium capitalize ${colours[label] ?? "bg-raised text-ink-2 border-line"}`}
    >
      {label}
    </span>
  );
}

/* ─── main component ─────────────────────────────────────── */
export function SettingsClient({ repos }: { repos: RepoSettings[] }) {
  /* Connect-Claude state */
  const [connectInfo, setConnectInfo] = useState<ConnectInfo | null>(null);
  const [connectError, setConnectError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [rotating, setRotating] = useState(false);

  /* Repo-toggle state */
  const [repoList, setRepoList] = useState<RepoSettings[]>(repos);
  const [toggling, setToggling] = useState<string | null>(null);

  /* Active tab */
  const [tab, setTab] = useState<"repos" | "connect">("repos");

  /* ── fetch connect info if we have a stored key ── */
  useEffect(() => {
    const storedKey =
      typeof window !== "undefined"
        ? localStorage.getItem("marginalia_api_key") ?? ""
        : "";
    if (!storedKey) return;

    fetch(`${API_BASE}/api/connect`, {
      headers: { Authorization: `Bearer ${storedKey}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then(setConnectInfo)
      .catch((e) =>
        setConnectError(`Could not load connection info: ${e.message}`)
      );
  }, []);

  /* ── copy helper ── */
  const copy = async (text: string, label: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 2000);
  };

  /* ── rotate key ── */
  const rotateKey = async () => {
    const storedKey =
      typeof window !== "undefined"
        ? localStorage.getItem("marginalia_api_key") ?? ""
        : "";
    if (!storedKey) return;
    setRotating(true);
    try {
      const res = await fetch(`${API_BASE}/api/keys/rotate`, {
        method: "POST",
        headers: { Authorization: `Bearer ${storedKey}` },
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const data = await res.json();
      localStorage.setItem("marginalia_api_key", data.api_key);
      setConnectInfo((prev) =>
        prev ? { ...prev, api_key: data.api_key } : null
      );
    } catch (e: unknown) {
      setConnectError(
        `Rotation failed: ${e instanceof Error ? e.message : String(e)}`
      );
    } finally {
      setRotating(false);
    }
  };

  /* ── toggle repo review ── */
  const toggleRepo = async (repoId: string, enabled: boolean) => {
    setToggling(repoId);
    try {
      const res = await fetch(`${API_BASE}/api/repos/${repoId}/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ review_enabled: enabled }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      setRepoList((prev) =>
        prev.map((r) =>
          r.id === repoId ? { ...r, review_enabled: enabled } : r
        )
      );
    } catch {
      /* silently ignore for now */
    } finally {
      setToggling(null);
    }
  };

  /* ── mcp config json ── */
  const mcpConfig = connectInfo
    ? JSON.stringify(
        {
          mcpServers: {
            marginalia: {
              command: "python3",
              args: ["mcp_server.py"],
              env: {
                MARGINALIA_API_KEY: connectInfo.api_key,
                MARGINALIA_API_URL: connectInfo.api_url,
              },
            },
          },
        },
        null,
        2
      )
    : "";

  const storedKey =
    typeof window !== "undefined"
      ? localStorage.getItem("marginalia_api_key") ?? ""
      : "";

  /* ════════════════════════════════════════════════════════ */
  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="mb-1 text-2xl font-semibold text-ink">Settings</h1>
      <p className="mb-8 text-sm text-ink-3">
        Manage repositories and connect Claude via MCP.
      </p>

      {/* Tab bar */}
      <div className="mb-6 flex gap-1 border-b border-line">
        {(["repos", "connect"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              tab === t
                ? "border-b-2 border-ink text-ink"
                : "text-ink-3 hover:text-ink"
            }`}
          >
            {t === "repos" ? "Repos & rules" : "Connect Claude"}
          </button>
        ))}
      </div>

      {/* ── Tab: Repos & rules ──────────────────────────── */}
      {tab === "repos" && (
        <div className="flex flex-col gap-4">
          {repoList.length === 0 && (
            <p className="text-sm text-ink-3">
              No repositories found. Install the GitHub App on a repo to get
              started.
            </p>
          )}
          {repoList.map((repo) => (
            <div
              key={repo.id}
              className="rounded-lg border border-line bg-raised p-5"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="truncate font-mono text-sm font-semibold text-ink">
                      {repo.full_name}
                    </span>
                    {repo.is_private && (
                      <span className="rounded-full border border-line bg-paper px-2 py-0.5 text-[10px] text-ink-3">
                        private
                      </span>
                    )}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {repo.review_categories.map((c) => (
                      <CategoryBadge key={c} label={c} />
                    ))}
                  </div>
                  <p className="mt-2 text-xs text-ink-3">
                    {repo.total_reviews} reviews · {repo.total_findings}{" "}
                    findings
                    {repo.last_reviewed_at
                      ? ` · last reviewed ${new Date(
                          repo.last_reviewed_at
                        ).toLocaleDateString()}`
                      : ""}
                  </p>
                </div>

                {/* Toggle */}
                <button
                  onClick={() =>
                    toggleRepo(repo.id, !repo.review_enabled)
                  }
                  disabled={toggling === repo.id}
                  className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none disabled:opacity-50 ${
                    repo.review_enabled ? "bg-ink" : "bg-line"
                  }`}
                  aria-label={
                    repo.review_enabled ? "Disable reviews" : "Enable reviews"
                  }
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                      repo.review_enabled ? "translate-x-4" : "translate-x-0"
                    }`}
                  />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Tab: Connect Claude ─────────────────────────── */}
      {tab === "connect" && (
        <div className="flex flex-col gap-6">
          {connectError && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              {connectError}
            </div>
          )}

          {!storedKey && !connectInfo && (
            <div className="rounded-lg border border-line bg-raised p-6 text-sm text-ink-3">
              No API key found. Install the GitHub App to get your key.
            </div>
          )}

          {/* API Key card */}
          {(storedKey || connectInfo) && (
            <section className="rounded-lg border border-line bg-raised p-5">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-semibold text-ink">API Key</h2>
                  <p className="mt-0.5 text-xs text-ink-3">
                    Used by the MCP server to authenticate with Marginalia.
                  </p>
                </div>
                <button
                  onClick={rotateKey}
                  disabled={rotating}
                  className="rounded-md border border-line bg-paper px-3 py-1.5 text-xs font-medium text-ink-2 hover:bg-recess disabled:opacity-50"
                >
                  {rotating ? "Rotating…" : "Rotate key"}
                </button>
              </div>

              <div className="flex items-center gap-2 rounded-md border border-line bg-paper px-3 py-2">
                <code className="flex-1 overflow-x-auto font-mono text-xs text-ink">
                  {connectInfo?.api_key ?? storedKey}
                </code>
                <button
                  onClick={() =>
                    copy(connectInfo?.api_key ?? storedKey, "key")
                  }
                  className="shrink-0 text-xs text-ink-3 hover:text-ink"
                >
                  {copied === "key" ? "Copied!" : "Copy"}
                </button>
              </div>
            </section>
          )}

          {/* MCP Config card */}
          {mcpConfig && (
            <section className="rounded-lg border border-line bg-raised p-5">
              <div className="mb-3">
                <h2 className="text-sm font-semibold text-ink">
                  Connect Claude Desktop
                </h2>
                <p className="mt-0.5 text-xs text-ink-3">
                  Add this to your{" "}
                  <code className="font-mono">
                    claude_desktop_config.json
                  </code>{" "}
                  to query your reviews from Claude.
                </p>
              </div>

              <div className="relative">
                <pre className="overflow-x-auto rounded-md border border-line bg-paper p-3 font-mono text-xs text-ink">
                  {mcpConfig}
                </pre>
                <button
                  onClick={() => copy(mcpConfig, "config")}
                  className="absolute right-2 top-2 rounded border border-line bg-paper px-2 py-1 text-xs text-ink-3 hover:text-ink"
                >
                  {copied === "config" ? "Copied!" : "Copy"}
                </button>
              </div>
            </section>
          )}

          {/* Example prompts */}
          <section className="rounded-lg border border-line bg-raised p-5">
            <h2 className="mb-3 text-sm font-semibold text-ink">
              What you can ask Claude
            </h2>
            <ul className="flex flex-col gap-2">
              {[
                "Show me all critical security findings from the last week",
                "Which PR had the most issues?",
                "Walk me through the reasoning trace for review <id>",
                "What are the most common security issues across my repos?",
                "How much have I spent on reviews this month?",
              ].map((q) => (
                <li
                  key={q}
                  className="flex items-start gap-2 text-xs text-ink-2"
                >
                  <span className="mt-0.5 text-ink-3">→</span>
                  <span className="font-mono">{q}</span>
                </li>
              ))}
            </ul>
          </section>

          {/* Available tools */}
          <section className="rounded-lg border border-line bg-raised p-5">
            <h2 className="mb-3 text-sm font-semibold text-ink">
              Available MCP tools
            </h2>
            <div className="grid grid-cols-2 gap-2">
              {[
                { name: "list_reviews", desc: "Review history with verdicts" },
                { name: "get_review", desc: "Full review with all findings" },
                { name: "list_findings", desc: "Filter findings by severity" },
                { name: "get_stats", desc: "Aggregate stats and spend" },
                { name: "list_repos", desc: "Installed repositories" },
                {
                  name: "get_reasoning_trace",
                  desc: "Agent's step-by-step thinking",
                },
              ].map((t) => (
                <div
                  key={t.name}
                  className="rounded-md border border-line bg-paper p-2"
                >
                  <code className="text-xs font-semibold text-lapis">
                    {t.name}
                  </code>
                  <p className="mt-0.5 text-[11px] text-ink-3">{t.desc}</p>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}