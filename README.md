# ¶ Marginalia — code review that shows its work

Marginalia is a GitHub App that reviews pull requests the way a senior engineer does:
it **investigates the codebase** — opens files beyond the diff, greps for the conventions
your repo already follows — and only then forms an opinion. Findings land as inline
comments mapped to exact diff positions, and **every finding arrives with the full
reasoning trace that produced it**: each thought, every tool call, every file the agent
opened.

**Live demo:** [https://www.prpilot.co/](https://www.prpilot.co/) ·
**Install:** the "Install on GitHub" button on the landing page

---

## What it does

- **Automatic reviews** — a webhook fires when a PR opens (drafts wait until marked
  ready), and a review lands on the PR in about two minutes.
- **Real investigation, not diff-skimming** — a LangGraph ReAct agent with tools
  (`read_file`, `search_code`, `record_finding`, `post_review`) explores the repository
  to understand the change in context before judging it.
- **Inline comments at exact diff positions** — findings are posted where the code is,
  with severity (critical / high / medium / low), category (security / performance /
  quality), and a suggested fix.
- **Re-review on demand** — comment `@marginalia review` on any PR and the agent
  re-reads what changed. A clean second pass approves the PR.
- **Full reasoning traces** — every thought, tool call, observation, token count, and
  cost is persisted, and browsable step-by-step in the dashboard.
- **Cost controls built in** — per-installation daily review caps, idempotent webhook
  processing (Redis + DB unique keys), and per-run token/cost accounting.

## How a review happens

```
PR opened ──▶ GitHub webhook ──▶ api-server (FastAPI)
                                   │  HMAC signature check
                                   │  event filter (drafts, bots, dupes)
                                   │  idempotency (Redis + unique key)
                                   │  daily cost cap check
                                   │  persist installation / repo / PR / run
                                   ▼
                              BullMQ queue (Redis)
                                   │
                                   ▼
                            agent-worker (Python)
                                   │  LangGraph ReAct agent (claude-haiku-4-5)
                                   │  tools: read_file · search_code · record_finding
                                   │  reasoning steps + token usage captured
                                   ▼
                       GitHub PR review (inline comments)
                                   +
                    Postgres (findings, trace, cost, timings)
                                   ▲
                                   │
                   marginalia-web dashboard (Next.js, read-only API)
```

## Architecture

Three deployable services in a monorepo:

| Service | Stack | Role |
|---|---|---|
| `api-server` | FastAPI, SQLAlchemy (async), asyncpg | Webhook receiver, dashboard read API, settings API |
| `agent-worker` | Python, LangGraph, BullMQ consumer | Runs the review agent, posts to GitHub, persists traces |
| `marginalia-web` | Next.js 15, TypeScript, Tailwind v4 | Landing page, post-install welcome, review dashboard |

Shared infrastructure: **PostgreSQL** (6-table schema: installations, repositories,
pull_requests, review_runs, findings, reasoning_steps) and **Redis** (BullMQ job queue +
idempotency keys).

Design decisions worth noting:

- **Fail-closed idempotency.** Duplicate webhook deliveries are dropped via Redis keys
  backed by a DB unique constraint; if Redis is down, the server refuses the event (503)
  so GitHub retries later — never double-reviews.
- **Installation lifecycle sync.** `installation.created` registers the selected repos
  immediately; `installation_repositories` events keep add/remove in sync; uninstalls
  soft-delete so review history survives.
- **The dashboard renders only what the backend persists.** One typed data layer
  (`lib/data.ts`) is the single contract with the API — no mocked fields.
- **LLM spend is bounded.** `MAX_REVIEWS_PER_INSTALLATION_PER_DAY` caps runs per
  account per UTC day; when hit, the PR author gets one polite comment and nothing is
  enqueued.

## Getting started (local)

Prerequisites: Python 3.11+, Node 18+, PostgreSQL, Redis, a GitHub App (see below),
an Anthropic API key.

```bash
# 1. Database + queue
#    (Postgres and Redis running locally, then:)
cd api-server
cp .env.example .env          # fill in secrets
alembic upgrade head

# 2. API server  (webhooks + dashboard API on :8000)
uvicorn app.main:app --reload --port 8000

# 3. Worker  (MOCK_LLM=true reviews with canned findings — no API cost)
cd ../agent-worker
python -m app.worker

# 4. Dashboard  (:3000)
cd ../marginalia-web
npm install && npm run dev

# 5. Webhooks need a public URL in dev:
ngrok http 8000               # set the GitHub App webhook URL to the tunnel
```

### GitHub App setup

Create a GitHub App (Settings → Developer settings → GitHub Apps) with:

- **Permissions:** Pull requests (read/write), Contents (read), Metadata (read)
- **Events:** Pull request, Issue comment, Installation, Installation repositories
- **Webhook URL:** `https://<your-host>/webhooks/github` (+ webhook secret)
- **Setup URL:** `https://<your-frontend>/welcome` — with *Redirect on update* checked,
  installers land on a confirmation page showing their connected repos

### Key environment variables

| Variable | Service | Purpose |
|---|---|---|
| `DATABASE_URL` | api-server, worker | `postgresql+asyncpg://…` |
| `REDIS_URL` | api-server, worker | queue + idempotency (`redis://user:pass@host:port` supported) |
| `GITHUB_APP_ID`, `GITHUB_WEBHOOK_SECRET`, `GITHUB_PRIVATE_KEY_PEM` | both | GitHub App auth |
| `ANTHROPIC_API_KEY` | worker | the reviewing model |
| `MOCK_LLM` | worker | `true` = canned findings + trace, zero cost (default in dev) |
| `MAX_REVIEWS_PER_INSTALLATION_PER_DAY` | api-server | cost cap (default 25, `0` disables) |
| `FRONTEND_ORIGIN` | api-server | CORS for the deployed dashboard |
| `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_GITHUB_APP_SLUG` | marginalia-web | API origin + install button target |

## Deployment

Production runs as: **Railway** (api-server + agent-worker + Postgres + Redis, private
networking between them) and **Vercel** (marginalia-web). Point the GitHub App's webhook
URL at the Railway domain and the Setup URL at the Vercel domain — no tunnels involved.

Migrations run from any machine against the database's public URL:
`DATABASE_URL=… alembic upgrade head`.

## Design system

The dashboard's visual language ("manuscript pigment") treats reviews like annotated
manuscripts: the agent's voice is always Newsreader italic, findings render as code
excerpts joined to margin notes by a dashed leader line, and the reasoning trace is a
dotted-spine ledger — rubric red is reserved for critical findings, verdigris for
approval. The ¶ pilcrow is the logo because marginalia is what this product literally
writes.

## Roadmap

- GitHub OAuth on the dashboard (per-tenant views; today the deployed dashboard is a
  read-only demo surface)
- House rules: per-repo custom instructions the agent quotes back in findings
- Draft-PR and path-filter controls per repository

---

Built by [Apoorva Pratap Singh](https://github.com/iamapoorv476).