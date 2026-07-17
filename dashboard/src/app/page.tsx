import Link from "next/link";
import { ReplayHero } from "@/components/replay-hero";
import { Reveal } from "@/components/reveal";
import { SeverityBadge } from "@/components/badges";

const BTN =
  "inline-flex items-center gap-2 rounded-[7px] border px-5 py-2.5 text-sm font-semibold no-underline transition-all";
const BTN_GHOST = `${BTN} border-line-2 bg-raised text-ink hover:border-ink-3`;
const BTN_LAPIS = `${BTN} border-lapis bg-lapis text-white hover:bg-lapis-ink`;
const BTN_INK = `${BTN} border-ink bg-ink text-paper hover:bg-[#2B333C] hover:-translate-y-px`;

const PIPELINE = [
  {
    num: "i.",
    title: "A pull request opens",
    body: (
      <>The GitHub webhook lands in seconds and the review is queued. Drafts wait until they&rsquo;re marked ready.</>
    ),
  },
  {
    num: "ii.",
    title: "The agent investigates",
    body: (
      <>
        It reads the diff, opens the files around it, and searches the repo —{" "}
        <code className="rounded bg-recess px-1 font-mono text-[10.5px]">read_file</code>,{" "}
        <code className="rounded bg-recess px-1 font-mono text-[10.5px]">search_code</code> — until
        the change makes sense in context.
      </>
    ),
  },
  {
    num: "iii.",
    title: "Notes land in your margins",
    body: (
      <>Inline comments mapped to exact diff positions, plus one summary verdict. Critical findings block; nits never nag.</>
    ),
  },
  {
    num: "iv.",
    title: "Push fixes, ask again",
    body: (
      <>
        Comment{" "}
        <code className="rounded bg-recess px-1 font-mono text-[10.5px]">@marginalia review</code>{" "}
        and it re-reads only what changed. A clean second pass approves the PR.
      </>
    ),
  },
];

const CATCHES = [
  {
    severity: "critical" as const,
    loc: "retry.py : 87",
    note: "Idempotency key derived from a timestamp — concurrent retries collide and the gateway silently drops the second charge attempt.",
    why: "Found by tracing key consumption into gateway.py, not by reading the diff alone.",
  },
  {
    severity: "warning" as const,
    loc: "payments.py : 52",
    note: "Twelve of thirteen mutating routes carry @rate_limit. This new endpoint triggers real charges and has none.",
    why: "Convention drift — the agent counted how the rest of the codebase does it first.",
  },
  {
    severity: "warning" as const,
    loc: "retry.py : 114",
    note: "Exponential backoff without jitter — every failed client retries in lockstep. A thundering herd against your gateway.",
    why: "Concurrency failure modes are invisible to tests and obvious in the margins.",
  },
  {
    severity: "suggestion" as const,
    loc: "invoice.py : 203",
    note: "House rule: money is integer cents. This handler does float math on a refund amount.",
    why: "Enforced from your own custom instructions — quoted back so reviewers know why.",
  },
];

const MINI_TRACE = [
  {
    knot: "border-ink-3 bg-paper",
    thought: "retry.py is the heart of it. The diff alone won't tell me how keys flow into the gateway.",
    action: 'read_file("services/payments/retry.py") · 212 lines',
  },
  {
    knot: "border-ink-3 bg-paper",
    thought: "Confirmed — the gateway returns the cached response on a key match. A collision doesn't error; it lies.",
    action: 'search_code("idempotency_key") · 4 matches',
  },
  {
    knot: "border-rubric bg-rubric",
    thought: "That's the worst kind of bug: invisible in tests, real in production. Recording as critical.",
    action: 'record_finding(severity="critical", line=87)',
  },
  {
    knot: "border-verdigris bg-verdigris",
    thought: "Requesting changes — lead with the collision, credit what's done well.",
    action: 'post_review(event="REQUEST_CHANGES") · posted ✓',
  },
];

export default function LandingPage() {
  return (
    <>
      {/* ───── nav ───── */}
      <header className="sticky top-0 z-50 border-b border-line bg-paper/90 backdrop-blur-md">
        <div className="mx-auto flex h-[62px] max-w-[1140px] items-center gap-7 px-7">
          <Link href="/" className="flex items-baseline gap-2 text-[17px] font-semibold tracking-tight no-underline">
            <span className="voice text-2xl leading-none font-medium text-rubric">¶</span>
            Marginalia
          </Link>
          <nav className="ml-3 flex gap-5 max-md:hidden" aria-label="Main">
            {[
              ["#how", "How it reviews"],
              ["#catches", "What it catches"],
              ["#trace", "The trace"],
              ["#rules", "House rules"],
            ].map(([href, label]) => (
              <a key={href} href={href} className="text-[13.5px] font-medium text-ink-2 no-underline hover:text-ink">
                {label}
              </a>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2.5">
            <Link href="/dashboard" className="text-[13.5px] font-medium text-ink-2 no-underline hover:text-ink">
              Live demo
            </Link>
            <a href="#install" className={`${BTN_INK} px-4 py-2 text-[13px]`}>
              Install on GitHub
            </a>
          </div>
        </div>
      </header>

      <main>
        {/* ───── hero ───── */}
        <section className="pt-[76px] pb-8 max-sm:pt-12">
          <div className="mx-auto grid max-w-[1140px] grid-cols-[minmax(0,1.02fr)_minmax(0,0.98fr)] items-center gap-14 px-7 max-lg:grid-cols-1 max-lg:gap-9">
            <div>
              <span className="mb-5 inline-flex items-center gap-2 rounded-full bg-verdigris-wash px-3 py-1 font-mono text-[11px] font-semibold tracking-[0.08em] text-verdigris">
                <span aria-hidden="true">●</span> Reviewing PRs at acme right now
              </span>
              <h1 className="max-w-[12ch] text-[clamp(34px,4.6vw,52px)] font-bold leading-[1.06] tracking-[-0.025em]">
                Code review that <span className="voice font-medium text-rubric">shows its work.</span>
              </h1>
              <p className="mt-5 max-w-[46ch] text-[16.5px] leading-[1.65] text-ink-2">
                Marginalia is a GitHub agent that reads your pull requests the way a senior engineer
                does — it <b className="font-semibold text-ink">investigates the codebase</b>, checks
                your conventions, and leaves precise notes in the margins. Every finding arrives with
                the reasoning that produced it.
              </p>
              <div className="mt-7 flex flex-wrap gap-3">
                <a href="#install" className={BTN_LAPIS}>Install on GitHub</a>
                <Link href="/dashboard" className={BTN_GHOST}>Explore the dashboard →</Link>
              </div>
              <p className="mt-4 text-xs text-ink-3">
                Reviews land in about two minutes. Re-run any time with{" "}
                <span className="rounded bg-recess px-1.5 font-mono text-[11px]">@marginalia review</span>.
              </p>
            </div>
            <ReplayHero />
          </div>

          {/* stats strip */}
          <div className="mt-16 border-y border-line bg-raised">
            <div className="mx-auto grid max-w-[1140px] grid-cols-4 px-7 max-md:grid-cols-2">
              {[
                ["1m 52s", "median review time"],
                ["62%", "suggestions accepted"],
                ["100%", "findings with reasoning"],
                ["1", "comment to re-review"],
              ].map(([v, k], i) => (
                <div
                  key={k}
                  className={`px-2.5 py-5 text-center ${i > 0 ? "border-l border-line max-md:[&:nth-child(3)]:border-l-0" : ""}`}
                >
                  <div className="text-2xl font-bold tracking-tight tabular-nums">{v}</div>
                  <div className="mt-0.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-3">{k}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ───── how it reviews ───── */}
        <section className="pt-22" id="how">
          <div className="mx-auto max-w-[1140px] px-7">
            <Reveal>
              <div className="mb-3.5 font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-rubric">
                How it reviews
              </div>
              <h2 className="max-w-[22ch] text-[clamp(26px,3.2vw,36px)] font-bold leading-tight tracking-tight">
                Not a linter. Not a summary. A reader.
              </h2>
              <p className="mt-3.5 max-w-[58ch] text-[15.5px] leading-[1.65] text-ink-2">
                Most AI reviewers skim the patch and pattern-match. Marginalia runs an investigation:
                it opens files beyond the diff, greps for the conventions your codebase already
                follows, and only then forms an opinion.
              </p>
            </Reveal>
            <div className="mt-11 grid grid-cols-4 gap-3.5 max-lg:grid-cols-2 max-sm:grid-cols-1">
              {PIPELINE.map((p, i) => (
                <Reveal key={p.num} className="relative">
                  <div className="h-full rounded-lg border border-line bg-raised p-5 shadow-card">
                    <div className="voice text-[15px] text-rubric">{p.num}</div>
                    <h3 className="mt-2 text-[15.5px] font-semibold tracking-tight">{p.title}</h3>
                    <p className="mt-1.5 text-[13px] leading-relaxed text-ink-2">{p.body}</p>
                  </div>
                  {i < PIPELINE.length - 1 && (
                    <span className="absolute -right-3.5 top-6 z-10 text-[15px] text-ink-3 max-lg:hidden" aria-hidden="true">
                      →
                    </span>
                  )}
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        {/* ───── what it catches ───── */}
        <section className="pt-22" id="catches">
          <div className="mx-auto max-w-[1140px] px-7">
            <Reveal>
              <div className="mb-3.5 font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-rubric">
                What it catches
              </div>
              <h2 className="max-w-[22ch] text-[clamp(26px,3.2vw,36px)] font-bold leading-tight tracking-tight">
                The bugs that pass tests and fail in production.
              </h2>
              <p className="mt-3.5 max-w-[58ch] text-[15.5px] leading-[1.65] text-ink-2">
                Real notes from real reviews. Each one names the evidence — the file, the line, and
                the convention or failure mode it&rsquo;s protecting.
              </p>
            </Reveal>
            <div className="mt-11 grid grid-cols-2 gap-3.5 max-lg:grid-cols-1">
              {CATCHES.map((c) => (
                <Reveal key={c.loc}>
                  <div className="h-full rounded-lg border border-line bg-raised px-5 py-4 shadow-card">
                    <div className="flex items-center gap-3.5">
                      <SeverityBadge severity={c.severity} />
                      <span className="font-mono text-[10.5px] text-ink-3">{c.loc}</span>
                    </div>
                    <p className="voice mt-2 text-[15.5px] leading-relaxed">{c.note}</p>
                    <p className="mt-2.5 border-t border-dashed border-line-2 pt-2 text-[12.5px] text-ink-2">
                      {c.why}
                    </p>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        {/* ───── the trace ───── */}
        <section className="pt-22" id="trace">
          <div className="mx-auto grid max-w-[1140px] grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] items-center gap-14 px-7 max-lg:grid-cols-1 max-lg:gap-9">
            <Reveal>
              <div className="mb-3.5 font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-rubric">
                The trace
              </div>
              <h2 className="max-w-[22ch] text-[clamp(26px,3.2vw,36px)] font-bold leading-tight tracking-tight">
                Trust is earned by showing receipts.
              </h2>
              <p className="mt-3.5 max-w-[58ch] text-[15.5px] leading-[1.65] text-ink-2">
                Every review keeps its full reasoning trace — each thought, every tool call, every
                file it opened. When a finding surprises you, you can see exactly how the agent got
                there.
              </p>
              <ul className="mt-6 flex list-none flex-col gap-3">
                {[
                  ["Auditable.", "Nine steps, seven tool calls, three files read — all on the record."],
                  ["Debuggable.", "A wrong finding shows you the wrong assumption, so your house rules can correct it."],
                  ["Teachable.", "Junior engineers read traces like a senior's commentary on the codebase."],
                ].map(([b, rest]) => (
                  <li key={b} className="grid grid-cols-[22px_1fr] gap-2.5 text-sm leading-relaxed text-ink-2">
                    <span className="font-bold text-verdigris">✓</span>
                    <span>
                      <b className="font-semibold text-ink">{b}</b> {rest}
                    </span>
                  </li>
                ))}
              </ul>
              <div className="mt-7">
                <Link href="/dashboard/reviews/rev_412" className={BTN_GHOST}>
                  Open a real trace →
                </Link>
              </div>
            </Reveal>
            <Reveal>
              <div className="rounded-lg border border-line bg-raised px-6 py-5 shadow-lift" aria-label="Excerpt of a reasoning trace">
                {MINI_TRACE.map((row, i) => (
                  <div
                    key={row.action}
                    className={`grid grid-cols-[18px_1fr] gap-3 py-2 ${i > 0 ? "border-t border-dashed border-line" : ""}`}
                  >
                    <span className={`mt-1 h-[9px] w-[9px] rounded-full border-2 ${row.knot}`} />
                    <div>
                      <div className="voice text-sm leading-normal">{row.thought}</div>
                      <div className="mt-1 font-mono text-[10.5px] text-ink-2">
                        <b className="font-semibold text-lapis">{row.action.split("(")[0]}</b>
                        {"(" + row.action.split("(").slice(1).join("(")}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Reveal>
          </div>
        </section>

        {/* ───── house rules ───── */}
        <section className="pt-22" id="rules">
          <div className="mx-auto grid max-w-[1140px] grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] items-center gap-14 px-7 max-lg:grid-cols-1 max-lg:gap-9">
            <Reveal className="max-lg:order-2">
              <div className="rounded-lg border border-line bg-[#FBFAF6] px-5 py-5 shadow-lift">
                <div className="mb-2.5 font-mono text-[10.5px] uppercase tracking-[0.1em] text-ink-3">
                  Custom instructions · acme/checkout-service
                </div>
                <span className="voice block text-base leading-[1.65]">
                  &ldquo;We use structlog — flag any bare print(). Money is always integer cents,
                  never floats. Prefer our internal retry helpers in lib/resilience over hand-rolled
                  loops.&rdquo;
                </span>
                <div className="mt-4 flex items-baseline gap-2.5 border-t border-dashed border-line-2 pt-3">
                  <span className="voice text-base text-rubric">¶</span>
                  <span className="text-[12.5px] leading-normal text-ink-2">
                    Per your house rules, this handler does float math on a refund amount —{" "}
                    <span className="font-mono text-[10.5px]">invoice.py:203</span>
                  </span>
                </div>
              </div>
            </Reveal>
            <Reveal className="max-lg:order-1">
              <div className="mb-3.5 font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-rubric">
                House rules
              </div>
              <h2 className="max-w-[22ch] text-[clamp(26px,3.2vw,36px)] font-bold leading-tight tracking-tight">
                Teach it your house style in plain language.
              </h2>
              <p className="mt-3.5 max-w-[58ch] text-[15.5px] leading-[1.65] text-ink-2">
                Write your team&rsquo;s conventions the way you&rsquo;d tell a new hire. Marginalia
                treats them with the same weight as its built-in checks — and quotes the rule back
                whenever a finding relies on it, so nobody wonders where an opinion came from.
              </p>
            </Reveal>
          </div>
        </section>

        {/* ───── final cta ───── */}
        <section className="mt-24 border-t border-line bg-raised py-20 text-center" id="install">
          <div className="mx-auto max-w-[1140px] px-7">
            <div className="voice text-[56px] leading-none text-rubric" aria-hidden="true">¶</div>
            <h2 className="mx-auto mt-4 max-w-[22ch] text-[clamp(26px,3.2vw,36px)] font-bold leading-tight tracking-tight">
              Put a careful reader in your margins.
            </h2>
            <p className="mx-auto mt-3.5 max-w-[58ch] text-[15.5px] leading-[1.65] text-ink-2">
              Install the GitHub App, pick your repos, and the next pull request gets a review that
              shows its work.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              <a href="#" className={BTN_LAPIS}>Install on GitHub — free while in beta</a>
              <Link href="/dashboard" className={BTN_GHOST}>See the dashboard first</Link>
            </div>
          </div>
        </section>
      </main>

      {/* ───── footer ───── */}
      <footer className="border-t border-line py-7">
        <div className="mx-auto flex max-w-[1140px] flex-wrap items-center gap-5 px-7 text-[12.5px] text-ink-3">
          <Link href="/" className="flex items-baseline gap-1.5 text-sm font-semibold text-ink no-underline">
            <span className="voice text-[19px] leading-none text-rubric">¶</span>Marginalia
          </Link>
          <a href="#how" className="text-ink-2 no-underline hover:text-ink">How it reviews</a>
          <Link href="/dashboard" className="text-ink-2 no-underline hover:text-ink">Dashboard demo</Link>
          <a href="#" className="text-ink-2 no-underline hover:text-ink">GitHub</a>
          <span className="ml-auto font-mono text-[11px]">
            reviews posted in ~2 minutes · findings with receipts
          </span>
        </div>
      </footer>
    </>
  );
}
