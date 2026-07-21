"use client";

import { useEffect, useRef, useState } from "react";

/*
 * "Re-review a PR" — teaches the GitHub-native command instead of
 * triggering a run from the dashboard. Re-reviews live where the code
 * lives: commenting on the PR is permission-gated by GitHub (you must be
 * able to comment on the repo), which is exactly the guard an
 * unauthenticated demo dashboard can't provide.
 */

const COMMAND = "@marginalia review";

export function ReReviewButton(){
    const [open, setOpen] = useState(false);
    const [copied, setCopied] = useState(false);
    const dialogRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if(!open) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "Escape") setOpen(false);
        }
        document.addEventListener("keydown", onKey);
        return () => document.removeEventListener("keydown", onKey);
    }, [open]);

    useEffect(() => {
        if(!copied) return;
        const t = setTimeout(() => setCopied(false), 2000);
        return () => clearTimeout(t);
    }, [copied]);

    const copy = async () => {
        try {
            await navigator.clipboard.writeText(COMMAND);
            setCopied(true);
        } catch {
          // Clipboard unavailable (e.g. non-secure context) — leave the text
      // selectable; the chip below is plain text the user can select.  
        }
    }

    return (
        <>
      <button
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-2 rounded-md border border-lapis bg-lapis px-3.5 py-2 text-[13px] font-semibold text-white hover:bg-lapis-ink"
      >
        ⟳ Re-review a PR
      </button>
 
      {open && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-ink/40 p-5 backdrop-blur-[2px]"
          onClick={(e) => {
            if (e.target === e.currentTarget) setOpen(false);
          }}
        >
          <div
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="rereview-title"
            className="w-full max-w-[480px] rounded-lg border border-line bg-raised p-6 shadow-lift"
          >
            <div className="mb-1 flex items-start justify-between gap-4">
              <h2 id="rereview-title" className="text-[17px] font-bold tracking-tight">
                Re-reviews happen on the pull request
              </h2>
              <button
                onClick={() => setOpen(false)}
                aria-label="Close"
                className="rounded px-1.5 text-[15px] leading-none text-ink-3 hover:text-ink"
              >
                ✕
              </button>
            </div>
 
            <p className="voice text-[15px] leading-relaxed text-ink">
              Push your fixes, then ask me again where the code lives — I&rsquo;ll re-read only
              what changed.
            </p>
 
            <div className="mt-4 flex items-center gap-2 rounded-md border border-line bg-recess px-3.5 py-2.5">
              <span className="flex-1 select-all font-mono text-[13.5px] text-ink">
                {COMMAND}
              </span>
              <button
                onClick={copy}
                className="flex-none rounded border border-line-2 bg-raised px-2.5 py-1 text-[11.5px] font-semibold text-ink-2 hover:border-ink-3 hover:text-ink"
              >
                {copied ? "Copied ✓" : "Copy"}
              </button>
            </div>
 
            <ol className="mt-4 flex list-none flex-col gap-2 text-[13px] leading-relaxed text-ink-2">
              <li className="grid grid-cols-[20px_1fr] gap-1.5">
                <span className="voice text-rubric">i.</span>
                <span>Open the pull request on GitHub.</span>
              </li>
              <li className="grid grid-cols-[20px_1fr] gap-1.5">
                <span className="voice text-rubric">ii.</span>
                <span>
                  Leave the command above as a comment — anyone who can comment on the repo can
                  ask.
                </span>
              </li>
              <li className="grid grid-cols-[20px_1fr] gap-1.5">
                <span className="voice text-rubric">iii.</span>
                <span>The fresh review lands here and on the PR in about two minutes.</span>
              </li>
            </ol>
 
            <p className="mt-4 border-t border-dashed border-line-2 pt-3 text-[11.5px] text-ink-3">
              <code className="rounded bg-recess px-1 font-mono text-[10.5px]">
                @agent re-review
              </code>{" "}
              also works — it&rsquo;s the same command by its older name.
            </p>
          </div>
        </div>
      )}
    </>
  );
}
 
    
