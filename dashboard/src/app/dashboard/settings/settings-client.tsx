"use client";

import { useState, useEffect } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

interface ConnectInfo {
  api_key: string;
  api_url: string;
  mcp_config: Record<string, unknown>;
}

export function SettingsClient({
  apiKey: initialKey,
}: {
  apiKey?: string;
}) {
  const [info, setInfo] = useState<ConnectInfo | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [rotating, setRotating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const storedKey =
    typeof window !== "undefined"
      ? localStorage.getItem("marginalia_api_key") ?? initialKey ?? ""
      : initialKey ?? "";

  useEffect(() => {
    if (!storedKey) return;
    fetch(`${API_BASE}/api/connect`, {
      headers: { Authorization: `Bearer ${storedKey}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then(setInfo)
      .catch((e) => setError(`Could not load connection info: ${e.message}`));
  }, [storedKey]);

  const copy = async (text: string, label: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 2000);
  };

  const rotateKey = async () => {
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
      setInfo((prev) =>
        prev ? { ...prev, api_key: data.api_key } : null
      );
    } catch (e: unknown) {
      setError(`Rotation failed: ${e instanceof Error ? e.message : e}`);
    } finally {
      setRotating(false);
    }
  };

  const mcpConfig = info
    ? JSON.stringify(
        {
          mcpServers: {
            marginalia: {
              command: "python",
              args: ["mcp_server.py"],
              env: {
                MARGINALIA_API_KEY: info.api_key,
                MARGINALIA_API_URL: info.api_url,
              },
            },
          },
        },
        null,
        2
      )
    : "";

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {error}
      </div>
    );
  }

  if (!storedKey) {
    return (
      <div className="rounded-lg border border-line bg-raised p-6 text-sm text-ink-3">
        No API key found. Install the GitHub App to get your key.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* API Key */}
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
            {info?.api_key ?? storedKey}
          </code>
          <button
            onClick={() => copy(info?.api_key ?? storedKey, "key")}
            className="shrink-0 text-xs text-ink-3 hover:text-ink"
          >
            {copied === "key" ? "Copied!" : "Copy"}
          </button>
        </div>
      </section>

      {/* MCP Config */}
      <section className="rounded-lg border border-line bg-raised p-5">
        <div className="mb-3">
          <h2 className="text-sm font-semibold text-ink">
            Connect Claude Desktop
          </h2>
          <p className="mt-0.5 text-xs text-ink-3">
            Add this to your{" "}
            <code className="font-mono">claude_desktop_config.json</code> to
            query your reviews from Claude.
          </p>
        </div>

        <div className="relative">
          <pre className="overflow-x-auto rounded-md border border-line bg-paper p-3 font-mono text-xs text-ink">
            {mcpConfig || "Loading…"}
          </pre>
          {mcpConfig && (
            <button
              onClick={() => copy(mcpConfig, "config")}
              className="absolute right-2 top-2 rounded border border-line bg-paper px-2 py-1 text-xs text-ink-3 hover:text-ink"
            >
              {copied === "config" ? "Copied!" : "Copy"}
            </button>
          )}
        </div>
      </section>

      {/* What you can ask Claude */}
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
            <li key={q} className="flex items-start gap-2 text-xs text-ink-2">
              <span className="mt-0.5 text-ink-3">→</span>
              <span className="font-mono">{q}</span>
            </li>
          ))}
        </ul>
      </section>

      {/* Available MCP tools */}
      <section className="rounded-lg border border-line bg-raised p-5">
        <h2 className="mb-3 text-sm font-semibold text-ink">
          Available tools
        </h2>
        <div className="grid grid-cols-2 gap-2">
          {[
            { name: "list_reviews", desc: "Review history with verdicts" },
            { name: "get_review", desc: "Full review with all findings" },
            { name: "list_findings", desc: "Filter findings by severity" },
            { name: "get_stats", desc: "Aggregate stats and spend" },
            { name: "list_repos", desc: "Installed repositories" },
            { name: "get_reasoning_trace", desc: "Agent's step-by-step thinking" },
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
  );
}