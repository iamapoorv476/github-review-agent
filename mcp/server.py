"""
Marginalia MCP server — query your code reviews from Claude.
 
Read-only, v1. This server is a thin client of the Marginalia dashboard
API: it never touches the database directly and never calls a model.
Model inference (and its token cost) happens on the MCP *client* side
(Claude Desktop / Claude Code), covered by the user's subscription.
 
Run (stdio, for Claude Desktop):
    MARGINALIA_API_URL=https://your-api.up.railway.app python server.py
 
Debug without a model:
    npx @modelcontextprotocol/inspector python server.py
 
Deliberate non-goals for v1 (documented, not forgotten):
  - No writes (settings, re-review triggers) — read-only by design.
  - No cross-review findings search — the dashboard API has no findings
    query endpoint yet; add one there first, then a tool here.
"""

import os
from datetime import datetime, timezone

import httpx
from mcp.server.mcpserver import MCPServer

API_BASE = os.environ.get("MARGINALIA_API_URL", "http://localhost:8000").rstrip("/")

mcp = MCPServer(
    "marginalia",
    instructions=(
        "Tools for querying Marginalia, an AI code-review agent for GitHub. "
        "Use list_reviews to discover reviews, get_review for findings on a"
        "specific PR, get _reasoning_trace to see WHY the agent concluded what"
        "it did, get_stats for account totals and spend, and list_repos for"
        "connected repositories. Repos are always 'owner/name'."
    ),
)

# ---------------------------------------------------------------- helpers

async def _get(path: str, params: dict | None = None):
    async with httpx.AsyncClient(timeout=15) as client:

        r = await client.get(f"{API_BASE}{path}", params=params)
        r.raise_for_status()
        return r.json()

def _ago(iso : str | None) -> str:
    """Humanized time with the ISO date kept for precision."""
    if not iso:
        return "-"
    try:
        then = datetime.fromisoformat(iso.replace("Z","+00:00"))
    except ValueError:
        return iso
    s= int((datetime.now(timezone.utc) - then).total_seconds())
    if s < 3600:
        human = f"{max(1, s // 60)}m ago"
    elif s < 86400:
        human = f"{s // 3600}h ago"
    else:
        human = f"{s // 86400}d ago"
    return f"{human} ({then.date().isoformat()})"

def _duration(ms : int | None) -> str:
    if ms is None:
        return "-"
    sec = round(ms / 1000)
    return f"{sec // 60}m {sec % 60:02d}s"

def _verdict(r: dict) -> str:
    """Mirror the dashboard's verdict derivation (lib/data.ts contract)."""
    if r["status"] in ("queued", "processing"):
        return "running"
    if r["status"] in ("failed", "cancelled"):
        return r["status"]
    if r["critical_count"] > 0:
        return "changes requested"
    return "commented" if r["findings_count"] > 0 else "approved"

def _sev_line(r: dict) -> str:
    parts = [
        f"{r[k]} {label}"
        for k, label in [
            ("critical_count", "critical"),
            ("high_count", "warning"),
            ("medium_count", "suggestion"),
            ("low_count", "nit"),
        ]
        if r[k]
    ]
    return ", ".join(parts) if parts else "no findings"

def _review_row(r: dict) -> str:
    pr = r["pull_request"]
    return (
        f"- {r['repository']['full_name']} PR #{pr['pr_number']} — "
        f"\"{pr['title']}\" · {_verdict(r)} · {_sev_line(r)} · "
        f"{_duration(r['duration_ms'])} · {_ago(r['completed_at'] or r['queued_at'])} · "
        f"review_id={r['id']}"
    )

async def _resolve_review_id(
    review_id: str, repo: str, pr_number: int
) -> str | None:
    """
    Humans think in PR numbers; the API thinks in UUIDs. Given either,
    return a UUID (newest run wins when a PR has several), or None.
    """
    if review_id:
        return review_id

    if not (repo and pr_number):
        return None
    data = await _get("/api/reviews", {"repo": repo, "limit": 100, "offset": 0})
    for r in data["items"]:  # newest first — first match is latest run
        if r["pull_request"]["pr_number"] == pr_number:
            return r["id"]
    return None

@mcp.tool()
async def list_reviews(repo: str = "", status: str = "", limit: int = 10) -> str:
    """List recent Marginalia code reviews, newest first. Use this first to
    discover reviews (and their review_id) before fetching findings or a
    reasoning trace. Filter by repo ("owner/name") and/or status (queued,
    processing, completed, failed). Returns at most `limit` rows (default 10,
    max 25)."""
    params: dict = {"limit": min(max(limit, 1), 25), "offset": 0}
    if repo:
        params["repo"] = repo
    if status:
        params["status"] = status
    data = await _get("/api/reviews", params)
    if not data["items"]:
        scope = f" for {repo}" if repo else ""
        return f"No reviews found{scope}."
    rows = "\n".join(_review_row(r) for r in data["items"])
    return f"{data['total']} reviews total, showing {len(data['items'])}:\n{rows}"
 
@mcp.tool()
async def get_review(repo: str = "", pr_number: int = 0, review_id: str = "") -> str:
    """Get one review's verdict and findings. Identify the review either by
    repo ("owner/name") + pr_number, or by review_id from list_reviews.
    Returns each finding's severity, category, file:line, description, and
    suggested fix — but NOT the reasoning trace (use get_reasoning_trace)."""
    rid = await _resolve_review_id(review_id, repo, pr_number)
    if rid is None:
        return "Review not found — check repo ('owner/name') and pr_number, or pass review_id."
    r = await _get(f"/api/reviews/{rid}")
    pr = r["pull_request"]
    head = (
        f"{r['repository']['full_name']} PR #{pr['pr_number']} — \"{pr['title']}\" by {pr['author_login']}\n"
        f"Verdict: {_verdict(r)} · {_sev_line(r)} · {pr['files_changed']} files "
        f"(+{pr['lines_added']} −{pr['lines_removed']}) · reviewed {_ago(r['completed_at'])}\n"
        f"Model {r['model_used'] or '—'} · {r['input_tokens'] + r['output_tokens']} tokens · "
        f"{r['tool_calls_made']} tool calls · {len(r['reasoning_steps'])} reasoning steps"
    )
    if r.get("error_message"):
        head += f"\nError: {r['error_message']}"
    if not r["findings"]:
        return head + "\n\nNo findings — clean pass."
    ui_sev = {"critical": "CRITICAL", "high": "WARNING", "medium": "SUGGESTION", "low": "NIT"}
    lines = []
    for f in r["findings"]:
        loc = f["file_path"] + (f":{f['line_number']}" if f["line_number"] else "")
        entry = f"[{ui_sev.get(f['severity'], f['severity'])}] {loc} ({f['category']}) — {f['description']}"
        if f.get("suggestion"):
            entry += f"\n  fix: {f['suggestion']}"
        if not f["was_posted"]:
            entry += "\n  (not posted to the PR)"
        lines.append(entry)
    return head + "\n\nFindings:\n" + "\n".join(lines)
 
@mcp.tool()
async def get_reasoning_trace(
    repo: str = "", pr_number: int = 0, review_id: str = "", detail: str = "summary"
) -> str:
    """Show HOW the agent reached its conclusions on a review: each thought,
    tool call, and observation, in order. Identify the review by repo +
    pr_number or by review_id. detail="summary" (default) keeps each step to
    one line; detail="full" includes complete thoughts and tool observations
    — much longer, ask for it only when the user wants to go deep."""
    rid = await _resolve_review_id(review_id, repo, pr_number)
    if rid is None:
        return "Review not found — check repo ('owner/name') and pr_number, or pass review_id."
    r = await _get(f"/api/reviews/{rid}")
    steps = r["reasoning_steps"]
    if not steps:
        return "No reasoning trace was captured for this review."
    pr = r["pull_request"]
    head = (
        f"Reasoning trace — {r['repository']['full_name']} PR #{pr['pr_number']} "
        f"({len(steps)} steps, {r['tool_calls_made']} tool calls):"
    )
    lines = []
    for s in sorted(steps, key=lambda x: x["step_number"]):
        kind = s["step_type"]
        if detail == "full":
            body = s["content"]
            if s.get("tool_name"):
                body += f"\n   → {s['tool_name']}({s.get('tool_input') or ''})"
            if s.get("tool_output_summary"):
                body += f"\n   ← {s['tool_output_summary']}"
        else:
            first = s["content"].split(". ")[0][:120]
            body = first + (f" → {s['tool_name']}" if s.get("tool_name") else "")
        lines.append(f"{s['step_number']}. [{kind}] {body}")
    return head + "\n" + "\n".join(lines)
 
 
@mcp.tool()
async def get_stats() -> str:
    """Account-wide Marginalia stats: total reviews (completed/failed/running),
    findings by severity, median review time, total LLM spend, and how many
    repos are actively reviewed. Use for questions about overall activity,
    quality, or cost."""
    s = await _get("/api/stats")
    sev = s["findings_by_severity"]
    return (
        f"Reviews: {s['reviews_total']} total — {s['reviews_completed']} completed, "
        f"{s['reviews_failed']} failed, {s['reviews_running']} running\n"
        f"Findings: {s['findings_total']} — {sev['critical']} critical, {sev['high']} warning, "
        f"{sev['medium']} suggestion, {sev['low']} nit\n"
        f"Median review time: {_duration(s['median_review_ms'])}\n"
        f"Spend to date: ${s['total_cost_usd']:.2f} ({s['total_tokens']} tokens)\n"
        f"Active repos: {s['repos_active']}"
    )
 
@mcp.tool()
async def list_repos() -> str:
    """List repositories connected to Marginalia with their review state:
    enabled/paused, total reviews and findings to date, last review time, and
    the finding categories enabled for the account. Use for 'what's
    connected?' and 'which repo has the most findings?'."""
    repos = await _get("/api/repos")
    if not repos:
        return "No repositories connected yet."
    lines = []
    for r in sorted(repos, key=lambda x: -x["total_findings"]):
        state = "active" if r["review_enabled"] else "paused"
        lines.append(
            f"- {r['full_name']} ({state}) — {r['total_reviews']} reviews, "
            f"{r['total_findings']} findings, last reviewed {_ago(r['last_reviewed_at'])} · "
            f"categories: {', '.join(r['review_categories'])}"
        )
    return f"{len(repos)} connected repositories:\n" + "\n".join(lines)
 
 
if __name__ == "__main__":
    mcp.run()  # stdio transport — what Claude Desktop launches
 
 
    