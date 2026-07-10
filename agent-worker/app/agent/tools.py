import structlog
from langchain_core.tools import tool
from typing import Annotated

logger = structlog.get_logger()


def make_tools(github_client, position_maps: dict, head_sha: str):

    @tool
    async def fetch_pr_files(
        dummy: Annotated[str, "Pass 'fetch' to get all PR files"]
    ) -> str:
        """
        Fetches the list of all files changed in this PR.
        Use this first to understand the scope of the PR.
        """
        files = []
        for filename, pos_map in position_maps.items():
            files.append(
                f"- {filename} "
                f"({len(pos_map.positions)} reviewable lines)"
            )
        return (
            f"Changed files ({len(position_maps)} total):\n"
            + "\n".join(files)
        )

    @tool
    async def fetch_file_diff(
        file_path: Annotated[str, "Path to the file to get the diff for"]
    ) -> str:
        """
        Fetches the diff for a specific file in this PR.
        Use this to understand exactly what code changed.
        """
        if file_path not in position_maps:
            available = list(position_maps.keys())[:5]
            return (
                f"File '{file_path}' not found in PR. "
                f"Available files: {available}"
            )

        cached_files = getattr(github_client, '_cached_files', [])
        for f in cached_files:
            if f.filename == file_path:
                if not f.patch:
                    return f"No diff available for {file_path}"
                return f"Diff for {file_path}:\n{f.patch}"

        return f"Diff not available for {file_path}"

    @tool
    async def fetch_file_content(
        file_path: Annotated[str, "Path to the file to fetch full content for"]
    ) -> str:
        """
        Fetches the complete current content of a file.
        Use when you need broader context beyond what changed.
        Limit usage to files directly relevant to your findings.
        """
        try:
            content = await github_client.get_file_content(
                file_path, head_sha
            )
            if len(content) > 8000:
                content = (
                    content[:8000]
                    + "\n\n[... truncated, file too large]"
                )
            return f"Content of {file_path}:\n{content}"
        except Exception as e:
            return f"Could not fetch {file_path}: {str(e)}"

    @tool
    async def create_finding(
        file_path: Annotated[str, "Path to the file containing the issue"],
        line_number: Annotated[int, "Line number in the new file"],
        severity: Annotated[str, "One of: critical, high, medium, low"],
        category: Annotated[str, "One of: security, performance, quality"],
        title: Annotated[str, "Short title summarizing the issue"],
        description: Annotated[str, "Detailed explanation of the issue"],
        suggestion: Annotated[str, "Concrete recommendation to fix it"]
    ) -> str:
        """
        Records a finding you identified in the code.
        Call this once per issue found — do not batch issues.
        Severity: critical=auth bypass/data loss, high=security bug,
        medium=performance/error handling, low=style/minor improvement.
        """
        valid_severities = {"critical", "high", "medium", "low"}
        valid_categories = {"security", "performance", "quality"}

        if severity not in valid_severities:
            return f"Invalid severity '{severity}'. Use: {valid_severities}"

        if category not in valid_categories:
            return f"Invalid category '{category}'. Use: {valid_categories}"

        pos_map = position_maps.get(file_path)
        diff_position = None
        if pos_map:
            diff_position = pos_map.get_position(line_number)

        finding = {
            "file_path": file_path,
            "line_number": line_number,
            "diff_position": diff_position,
            "severity": severity,
            "category": category,
            "title": title,
            "description": description,
            "suggestion": suggestion
        }

        if not hasattr(github_client, '_findings'):
            github_client._findings = []
        github_client._findings.append(finding)

        position_info = (
            f"diff position {diff_position}"
            if diff_position
            else "no diff position (general comment)"
        )

        logger.info(
            "finding_recorded",
            file_path=file_path,
            line_number=line_number,
            severity=severity,
            category=category,
            diff_position=diff_position
        )

        return (
            f"Finding recorded: [{severity.upper()}] {title} "
            f"at {file_path}:{line_number} ({position_info})"
        )

    return [
        fetch_pr_files,
        fetch_file_diff,
        fetch_file_content,
        create_finding
    ]