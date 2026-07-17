"use client";

import { useState } from "react";
import {
  saveInstallationSettings,
  saveRepoSettings,
  type RepoSettings,
} from "@/lib/data";

/*
 * Settings limited to what the backend persists:
 *   • per-repo   → review_enabled  (PATCH /api/repos/:id)
 *   • per-install→ review_categories (PATCH /api/installations/:id)
 *
 * Everything the mock UI used to show (minSeverity, ignoredPaths,
 * customInstructions, draft-skipping, per-event triggers, etc.) was
 * removed because there are no columns backing it. Add the columns +
 * schema fields first, then reintroduce the controls here.
 */

const ALL_CATEGORIES = ["security", "performance", "quality"] as const;

function Toggle({
  on,
  onChange,
  label,
}: {
  on: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <button
      role="switch"
      aria-checked={on}
      aria-label={label}
      onClick={() => onChange(!on)}
      className={`relative h-[22px] w-[38px] flex-none rounded-full transition-colors ${
        on ? "bg-verdigris" : "bg-line-2"
      }`}
    >
      <span
        className={`absolute top-[3px] h-4 w-4 rounded-full bg-white shadow transition-all ${
          on ? "left-[19px]" : "left-[3px]"
        }`}
      />
    </button>
  );
}

function Card({
  title,
  sub,
  children,
}: {
  title: string;
  sub: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-4.5 overflow-hidden rounded-lg border border-line bg-raised shadow-card">
      <div className="border-b border-line px-5 pb-3 pt-4">
        <h2 className="text-[14.5px] font-semibold tracking-tight">{title}</h2>
        <p className="mt-0.5 text-[12.5px] text-ink-2">{sub}</p>
      </div>
      {children}
    </div>
  );
}

function Row({
  label,
  desc,
  children,
}: {
  label: React.ReactNode;
  desc: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-5 border-b border-line px-5 py-3.5 last:border-b-0">
      <div>
        <div className="text-[13.5px] font-medium">{label}</div>
        <div className="mt-0.5 max-w-[46ch] text-xs text-ink-2">{desc}</div>
      </div>
      {children}
    </div>
  );
}

const SELECT_CLS =
  "rounded-md border border-line-2 bg-raised px-2.5 py-1.5 text-[12.5px] font-medium text-ink";

export function SettingsClient({ repos }: { repos: RepoSettings[] }) {
  const [items, setItems] = useState<RepoSettings[]>(repos);
  const [selectedId, setSelectedId] = useState<string>(repos[0]?.id ?? "");
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const current = items.find((r) => r.id === selectedId);

  if (!current) {
    return (
      <>
        <h1 className="text-[23px] font-bold tracking-tight">Repos &amp; rules</h1>
        <p className="mt-2 text-[13px] text-ink-2">
          No repositories yet. Install the GitHub App on a repo to configure it here.
        </p>
      </>
    );
  }

  const update = (patch: Partial<RepoSettings>) => {
    setItems((prev) =>
      prev.map((r) => (r.id === current.id ? { ...r, ...patch } : r))
    );
    setSaved(false);
  };

  const toggleCategory = (cat: string) => {
    const has = current.reviewCategories.includes(cat);
    const next = has
      ? current.reviewCategories.filter((c) => c !== cat)
      : [...current.reviewCategories, cat];
    // categories are installation-level → apply to every repo in this install
    setItems((prev) =>
      prev.map((r) =>
        r.installationId === current.installationId
          ? { ...r, reviewCategories: next }
          : r
      )
    );
    setSaved(false);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await saveRepoSettings(current.id, { reviewEnabled: current.reviewEnabled });
      await saveInstallationSettings(current.installationId, {
        reviewCategories: current.reviewCategories,
      });
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[23px] font-bold tracking-tight">Repos &amp; rules</h1>
          <p className="mt-0.5 text-[13px] text-ink-2">How the agent behaves, per repository.</p>
        </div>
        <select
          className={SELECT_CLS}
          aria-label="Repository"
          value={current.id}
          onChange={(e) => {
            setSelectedId(e.target.value);
            setSaved(false);
          }}
        >
          {items.map((r) => (
            <option key={r.id} value={r.id}>
              {r.fullName}
            </option>
          ))}
        </select>
      </div>

      <div className="max-w-[720px]">
        <Card title="Reviewing" sub="Whether the agent reviews pull requests on this repo.">
          <Row
            label={current.reviewEnabled ? "Reviews are active" : "Reviews are paused"}
            desc={`${current.fullName} · last review ${current.lastReviewAgo} · ${current.totalReviews} total`}
          >
            <Toggle
              on={current.reviewEnabled}
              onChange={(v) => update({ reviewEnabled: v })}
              label="Review enabled"
            />
          </Row>
        </Card>

        <Card
          title="What to look for"
          sub="Finding categories the agent reports. Applies to all repos under this account."
        >
          {ALL_CATEGORIES.map((cat) => (
            <Row
              key={cat}
              label={<span className="capitalize">{cat}</span>}
              desc={
                cat === "security"
                  ? "Secrets, injection, auth bypasses, missing validation."
                  : cat === "performance"
                    ? "N+1 queries, blocking I/O, unnecessary work."
                    : "Error handling, dead code, correctness bugs."
              }
            >
              <Toggle
                on={current.reviewCategories.includes(cat)}
                onChange={() => toggleCategory(cat)}
                label={`Report ${cat}`}
              />
            </Row>
          ))}
        </Card>

        <Card title="Repository" sub="Read from GitHub — not editable here.">
          <Row label="Account" desc="Installation owner.">
            <span className="font-mono text-[12.5px] text-ink-2">{current.accountLogin}</span>
          </Row>
          <Row label="Visibility" desc="From the GitHub repository.">
            <span className="font-mono text-[12.5px] text-ink-2">
              {current.isPrivate ? "private" : "public"}
            </span>
          </Row>
          <Row label="Default branch" desc="Base for most reviews.">
            <span className="font-mono text-[12.5px] text-ink-2">{current.defaultBranch}</span>
          </Row>
          <Row label="Findings to date" desc="Across all reviews on this repo.">
            <span className="font-mono text-[12.5px] text-ink-2">{current.totalFindings}</span>
          </Row>
        </Card>

        <div className="flex items-center justify-end gap-2.5 pt-1">
          {error && <span className="text-xs font-medium text-rubric">{error}</span>}
          {saved && <span className="text-xs font-medium text-verdigris">Saved ✓</span>}
          <button
            className="rounded-md border border-line-2 bg-raised px-3.5 py-2 text-[13px] font-semibold hover:border-ink-3"
            onClick={() => {
              setItems(repos);
              setSaved(false);
              setError(null);
            }}
          >
            Discard
          </button>
          <button
            disabled={saving}
            className="rounded-md border border-lapis bg-lapis px-3.5 py-2 text-[13px] font-semibold text-white hover:bg-lapis-ink disabled:opacity-60"
            onClick={handleSave}
          >
            {saving ? "Saving…" : "Save changes"}
          </button>
        </div>
      </div>
    </>
  );
}