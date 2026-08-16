"""
Marginalia MCP Server
Exposes GitHub Review Agent data to Claude via Model Context Protocol.
Connect with: MARGINALIA_API_KEY=gra_xxx python mcp_server.py
"""

import os
import json
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

API_BASE = os.environ.get(
    "MARGINALIA_API_URL",
    "http://localhost:8000"
)
API_KEY = os.environ.get("MARGINALIA_API_KEY", "")

app = Server("marginalia")


def get_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    return headers


async def api_get(path: str, params: dict = None) -> dict:
    """Make authenticated GET request to Marginalia API."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{API_BASE}{path}",
            headers=get_headers(),
            params=params or {}
        )
        if response.status_code == 401:
            raise ValueError(
                "Invalid API key. Set MARGINALIA_API_KEY=gra_xxx"
            )
        if response.status_code == 404:
            raise ValueError(f"Not found: {path}")
        response.raise_for_status()
        return response.json()


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_reviews",
            description=(
                "List pull request reviews. Returns review history "
                "with verdict, findings count, timing, and PR details. "
                "Use this to get an overview of reviewed PRs."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of reviews to return (default 20, max 100)",
                        "default": 20
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by status: completed, failed, processing, queued",
                        "enum": ["completed", "failed", "processing", "queued"]
                    },
                    "repo": {
                        "type": "string",
                        "description": "Filter by repo full name e.g. 'owner/repo'"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_review",
            description=(
                "Get full details of a single review run including "
                "all findings and the complete agent reasoning trace. "
                "Use this when you need to understand why the agent "
                "flagged something or see the full reasoning."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "review_run_id": {
                        "type": "string",
                        "description": "UUID of the review run"
                    }
                },
                "required": ["review_run_id"]
            }
        ),
        Tool(
            name="get_stats",
            description=(
                "Get aggregate statistics: total reviews, findings surfaced, "
                "median review time, spend to date, critical issue count. "
                "Use this for a high-level health check."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="list_repos",
            description=(
                "List repositories where the GitHub App is installed. "
                "Shows review count and last reviewed date per repo."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="list_findings",
            description=(
                "List security and code quality findings across all reviews. "
                "Filter by severity (critical/high/medium/low), category "
                "(security/performance/quality), or repository. "
                "Use this to find all critical security issues across repos."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "severity": {
                        "type": "string",
                        "description": "Filter by severity",
                        "enum": ["critical", "high", "medium", "low"]
                    },
                    "category": {
                        "type": "string",
                        "description": "Filter by category",
                        "enum": ["security", "performance", "quality"]
                    },
                    "repo": {
                        "type": "string",
                        "description": "Filter by repo full name e.g. 'owner/repo'"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of findings to return (default 50)",
                        "default": 50
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_reasoning_trace",
            description=(
                "Get the full step-by-step reasoning trace for a specific review. "
                "Shows every thought, tool call, and observation the agent made. "
                "Use this to audit why the agent reached a specific conclusion "
                "or to understand the agent's decision-making process."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "review_run_id": {
                        "type": "string",
                        "description": "UUID of the review run to get the trace for"
                    }
                },
                "required": ["review_run_id"]
            }
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "list_reviews":
            params = {}
            if arguments.get("limit"):
                params["limit"] = arguments["limit"]
            if arguments.get("status"):
                params["status"] = arguments["status"]
            if arguments.get("repo"):
                params["repo"] = arguments["repo"]

            data = await api_get("/api/reviews", params)
            reviews = data.get("reviews", data if isinstance(data, list) else [])

            if not reviews:
                return [TextContent(type="text", text="No reviews found.")]

            lines = [f"Found {len(reviews)} reviews:\n"]
            for r in reviews:
                verdict = r.get("verdict", "unknown")
                findings = r.get("findings_count", 0)
                duration = r.get("duration_ms", 0)
                duration_str = (
                    f"{duration // 60000}m {(duration % 60000) // 1000}s"
                    if duration else "—"
                )
                lines.append(
                    f"• [{verdict.upper()}] PR #{r.get('pr_number')} — "
                    f"{r.get('pr_title', 'untitled')} "
                    f"({r.get('repo_full_name', '')}) "
                    f"| {findings} findings | {duration_str} "
                    f"| id: {r.get('id')}"
                )

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "get_review":
            review_run_id = arguments.get("review_run_id")
            if not review_run_id:
                return [TextContent(type="text", text="review_run_id is required")]

            data = await api_get(f"/api/reviews/{review_run_id}")

            lines = [
                f"Review: {data.get('pr_title')} (PR #{data.get('pr_number')})",
                f"Repo: {data.get('repo_full_name')}",
                f"Status: {data.get('status')}",
                f"Verdict: {data.get('verdict')}",
                f"Findings: {data.get('findings_count')} "
                f"({data.get('critical_count')} critical, "
                f"{data.get('high_count')} high, "
                f"{data.get('medium_count')} medium, "
                f"{data.get('low_count')} low)",
                f"Duration: {data.get('duration_ms', 0) // 1000}s",
                f"Model: {data.get('model_used')}",
                f"Tokens: {data.get('input_tokens', 0) + data.get('output_tokens', 0)}",
                f"Cost: ${data.get('total_cost_usd', 0):.4f}",
                ""
            ]

            findings = data.get("findings", [])
            if findings:
                lines.append(f"Findings ({len(findings)}):")
                for f in findings:
                    lines.append(
                        f"  [{f.get('severity', '').upper()}] "
                        f"{f.get('title')} "
                        f"— {f.get('file_path')}:{f.get('line_number')}"
                    )
                    lines.append(
                        f"    {f.get('description', '')[:150]}"
                    )

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "get_stats":
            data = await api_get("/api/stats")

            median_ms = data.get("median_review_time_ms", 0)
            median_str = (
                f"{median_ms // 60000}m {(median_ms % 60000) // 1000}s"
                if median_ms else "—"
            )

            text = (
                f"Marginalia Stats\n"
                f"{'─' * 30}\n"
                f"Total reviews:      {data.get('total_reviews', 0)}\n"
                f"Findings surfaced:  {data.get('total_findings', 0)}\n"
                f"  Critical:         {data.get('critical_count', 0)}\n"
                f"  High:             {data.get('high_count', 0)}\n"
                f"Median review time: {median_str}\n"
                f"Spend to date:      ${data.get('total_cost_usd', 0):.4f}\n"
                f"Active repos:       {data.get('active_repos', 0)}\n"
            )
            return [TextContent(type="text", text=text)]

        elif name == "list_repos":
            data = await api_get("/api/repos")
            repos = data.get("repos", data if isinstance(data, list) else [])

            if not repos:
                return [TextContent(type="text", text="No repositories found.")]

            lines = [f"Repositories ({len(repos)}):\n"]
            for r in repos:
                last = r.get("last_reviewed_at", "never")
                lines.append(
                    f"• {r.get('full_name')} "
                    f"— {r.get('total_reviews', 0)} reviews, "
                    f"{r.get('total_findings', 0)} findings "
                    f"| last reviewed: {last}"
                )

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "list_findings":
            params = {}
            if arguments.get("severity"):
                params["severity"] = arguments["severity"]
            if arguments.get("category"):
                params["category"] = arguments["category"]
            if arguments.get("repo"):
                params["repo"] = arguments["repo"]
            params["limit"] = arguments.get("limit", 50)

            data = await api_get("/api/findings", params)
            findings = data.get("findings", data if isinstance(data, list) else [])

            if not findings:
                return [TextContent(
                    type="text",
                    text="No findings match the given filters."
                )]

            lines = [f"Found {len(findings)} findings:\n"]
            for f in findings:
                lines.append(
                    f"• [{f.get('severity', '').upper()}] "
                    f"{f.get('category', '')} — {f.get('title')}"
                )
                lines.append(
                    f"  {f.get('file_path')}:{f.get('line_number')} "
                    f"(PR #{f.get('pr_number')} in {f.get('repo_full_name')})"
                )
                lines.append(f"  {f.get('description', '')[:150]}")
                lines.append("")

            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "get_reasoning_trace":
            review_run_id = arguments.get("review_run_id")
            if not review_run_id:
                return [TextContent(
                    type="text",
                    text="review_run_id is required"
                )]

            data = await api_get(f"/api/reviews/{review_run_id}/trace")
            steps = data.get("steps", [])

            if not steps:
                return [TextContent(
                    type="text",
                    text="No reasoning trace found for this review."
                )]

            lines = [
                f"Reasoning trace — {len(steps)} steps",
                f"PR: {data.get('pr_title')} (#{data.get('pr_number')})",
                f"Repo: {data.get('repo_full_name')}\n"
            ]

            for step in steps:
                step_type = step.get("step_type", "").upper()
                content = step.get("content", "")[:300]
                tool = step.get("tool_name")

                if tool:
                    lines.append(
                        f"[{step.get('step_number')}] {step_type} → {tool}"
                    )
                    if step.get("tool_input"):
                        lines.append(
                            f"    input: {json.dumps(step['tool_input'])[:100]}"
                        )
                else:
                    lines.append(f"[{step.get('step_number')}] {step_type}")

                lines.append(f"    {content}")
                lines.append("")

            return [TextContent(type="text", text="\n".join(lines))]

        else:
            return [TextContent(
                type="text",
                text=f"Unknown tool: {name}"
            )]

    except ValueError as e:
        return [TextContent(type="text", text=f"Error: {e}")]
    except httpx.HTTPStatusError as e:
        return [TextContent(
            type="text",
            text=f"API error {e.response.status_code}: {e.response.text[:200]}"
        )]
    except Exception as e:
        return [TextContent(type="text", text=f"Unexpected error: {e}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())