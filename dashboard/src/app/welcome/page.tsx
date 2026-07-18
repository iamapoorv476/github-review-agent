import Link from "next/link";
import { getInstallationByGithubId } from "@/lib/data";
import { githubInstallUrl } from "@/lib/github";

export const metadata = { title: "Marginalia — You're all set" };

/*
 * Post-install landing. Set this route as the GitHub App's "Setup URL"
 * (Redirect on installation). GitHub sends the user here after they confirm,
 * with ?installation_id=<github_install_id>&setup_action=install.
 *
 * The installation row is created asynchronously by the installation.created
 * webhook, so on a fast redirect it may not exist yet — we show a "still
 * connecting" state with a refresh rather than a hard error.
 */

const CARD = "rounded-lg border border-line bg-raised shadow-card";
const BTN =
  "inline-flex items-center justify-center gap-2 rounded-[7px] border px-5 py-2.5 text-sm font-semibold no-underline transition-all";

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto max-w-[680px] px-7 py-16 max-sm:py-10">
      <Link
        href="/"
        className="mb-8 inline-flex items-baseline gap-2 text-[17px] font-semibold tracking-tight no-underline"
      >
        <span className="voice text-2xl leading-none font-medium text-rubric">¶</span>
        Marginalia
      </Link>
      {children}
    </main>
  );
}

export default async function WelcomePage({
  searchParams,
}: {
  searchParams: Promise<{ installation_id?: string; setup_action?: string }>;
}) {
  const { installation_id: installId } = await searchParams;

  // Arrived without an install id (e.g. direct navigation).
  if (!installId) {
    return (
      <Shell>
        <h1 className="text-[26px] font-bold tracking-tight">Nothing to confirm yet</h1>
        <p className="mt-2.5 text-[15px] leading-relaxed text-ink-2">
          This page confirms a fresh install. Install the GitHub App to get here for real.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <a href={githubInstallUrl} className={`${BTN} border-lapis bg-lapis text-white hover:bg-lapis-ink`}>
            Install on GitHub
          </a>
          <Link href="/dashboard" className={`${BTN} border-line-2 bg-raised text-ink hover:border-ink-3`}>
            Explore the dashboard →
          </Link>
        </div>
      </Shell>
    );
  }

  const install = await getInstallationByGithubId(installId);

  // Webhook hasn't landed yet — the record is created asynchronously.
  if (!install) {
    return (
      <Shell>
        <h1 className="text-[26px] font-bold tracking-tight">Finishing the connection…</h1>
        <p className="mt-2.5 max-w-[52ch] text-[15px] leading-relaxed text-ink-2">
          GitHub just handed you back. We&rsquo;re recording the installation now — this usually
          takes a few seconds. Refresh in a moment.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          {/* A plain link re-runs this server component with the same query. */}
          <Link
            href={`/welcome?installation_id=${encodeURIComponent(installId)}`}
            className={`${BTN} border-ink bg-ink text-paper hover:bg-[#2B333C]`}
          >
            ⟳ Refresh
          </Link>
          <Link href="/dashboard" className={`${BTN} border-line-2 bg-raised text-ink hover:border-ink-3`}>
            Go to dashboard anyway
          </Link>
        </div>
      </Shell>
    );
  }

  const repoCount = install.repositories.length;

  return (
    <Shell>
      <div className="mb-6 flex items-center gap-3">
        <span
          className="flex h-9 w-9 flex-none items-center justify-center rounded-full bg-verdigris-wash text-lg text-verdigris"
          aria-hidden="true"
        >
          ✓
        </span>
        <h1 className="text-[26px] font-bold leading-tight tracking-tight">
          Marginalia is watching <span className="text-lapis">{install.accountLogin}</span>
        </h1>
      </div>

      <p className="max-w-[54ch] text-[15px] leading-relaxed text-ink-2">
        {repoCount === 0 ? (
          <>
            The app is installed, but no repositories are selected yet. Add repos from the GitHub
            app settings and they&rsquo;ll show up here.
          </>
        ) : (
          <>
            {repoCount} {repoCount === 1 ? "repository is" : "repositories are"} connected. The next
            pull request opened on {repoCount === 1 ? "it" : "any of them"} gets reviewed
            automatically.
          </>
        )}
      </p>

      {repoCount > 0 && (
        <div className={`mt-6 overflow-hidden ${CARD}`}>
          <div className="border-b border-line px-5 py-2.5 text-[10.5px] font-semibold uppercase tracking-[0.13em] text-ink-3">
            Connected repositories
          </div>
          <ul className="divide-y divide-line">
            {install.repositories.map((repo) => (
              <li key={repo.id} className="flex items-center gap-2.5 px-5 py-2.5">
                <span className="text-ink-3" aria-hidden="true">
                  {repo.isPrivate ? "🔒" : "▤"}
                </span>
                <span className="font-mono text-[13px]">{repo.fullName}</span>
                {!repo.reviewEnabled && (
                  <span className="ml-auto rounded bg-recess px-1.5 py-px font-mono text-[10.5px] text-ink-3">
                    paused
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* what happens next — in the agent's voice */}
      <div className={`voice mt-6 border-l-[3px] border-l-lapis px-5 py-4 text-[15.5px] leading-relaxed ${CARD}`}>
        Open a pull request and I&rsquo;ll read it the way a senior engineer would — investigate the
        codebase, check your conventions, and leave notes in the margins. The first review lands in
        about two minutes.
      </div>

      <div className="mt-7 flex flex-wrap gap-3">
        <Link href="/dashboard" className={`${BTN} border-lapis bg-lapis text-white hover:bg-lapis-ink`}>
          Go to dashboard
        </Link>
        <Link
          href="/dashboard/settings"
          className={`${BTN} border-line-2 bg-raised text-ink hover:border-ink-3`}
        >
          Review categories &amp; rules →
        </Link>
      </div>

      <p className="mt-5 text-xs text-ink-3">
        Categories enabled:{" "}
        {install.reviewCategories.length ? install.reviewCategories.join(" · ") : "none"} · re-run any
        review with{" "}
        <span className="rounded bg-recess px-1.5 font-mono text-[11px]">@marginalia review</span>.
      </p>
    </Shell>
  );
}