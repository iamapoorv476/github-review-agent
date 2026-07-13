import structlog
import httpx
import asyncio
from dataclasses import dataclass
from typing import Optional

logger = structlog.get_logger()

GITHUB_API_BASE = "https://api.github.com"


@dataclass
class DiffFile:
    filename: str
    status: str
    additions: int
    deletions: int
    changes: int
    patch: Optional[str]
    blob_url: str


@dataclass
class PRMetadata:
    number: int
    title: str
    body: str
    author: str
    base_branch: str
    head_branch: str
    head_sha: str
    files_changed: int
    additions: int
    deletions: int


class GitHubClient:

    def __init__(self, token: str, repo_full_name: str):
        self.token = token
        self.repo_full_name = repo_full_name
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

    async def get_pr_metadata(self, pr_number: int) -> PRMetadata:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/repos/{self.repo_full_name}"
                f"/pulls/{pr_number}",
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()

        return PRMetadata(
            number=data["number"],
            title=data["title"],
            body=data.get("body", "") or "",
            author=data["user"]["login"],
            base_branch=data["base"]["ref"],
            head_branch=data["head"]["ref"],
            head_sha=data["head"]["sha"],
            files_changed=data["changed_files"],
            additions=data["additions"],
            deletions=data["deletions"]
        )

    async def get_pr_files(self, pr_number: int) -> list[DiffFile]:
        files = []
        page = 1

        async with httpx.AsyncClient() as client:
            while True:
                response = await client.get(
                    f"{GITHUB_API_BASE}/repos/{self.repo_full_name}"
                    f"/pulls/{pr_number}/files",
                    headers=self.headers,
                    params={"per_page": 100, "page": page},
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()

                if not data:
                    break

                for f in data:
                    files.append(DiffFile(
                        filename=f["filename"],
                        status=f["status"],
                        additions=f["additions"],
                        deletions=f["deletions"],
                        changes=f["changes"],
                        patch=f.get("patch"),
                        blob_url=f.get("blob_url", "")
                    ))

                if len(data) < 100:
                    break
                page += 1

        logger.info(
            "pr_files_fetched",
            repo=self.repo_full_name,
            pr_number=pr_number,
            file_count=len(files)
        )

        return files

    async def get_file_content(self, file_path: str, ref: str) -> str:
        import base64

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_BASE}/repos/{self.repo_full_name}"
                f"/contents/{file_path}",
                headers=self.headers,
                params={"ref": ref},
                timeout=30.0
            )

            if response.status_code == 404:
                return f"File {file_path} not found at ref {ref}"

            response.raise_for_status()
            data = response.json()

        if data.get("encoding") == "base64":
            content = base64.b64decode(data["content"]).decode(
                "utf-8", errors="replace"
            )
        else:
            content = data.get("content", "")

        logger.debug(
            "file_content_fetched",
            file_path=file_path,
            size=len(content)
        )

        return content

    async def post_review_with_comments(
        self,
        pr_number: int,
        commit_sha: str,
        summary: str,
        comments: list[dict]
    ) -> int:
        valid_comments = [
            c for c in comments
            if c.get("position") is not None
        ]
        skipped = len(comments) - len(valid_comments)

        if skipped > 0:
            logger.warning(
                "some_comments_skipped_no_position",
                skipped=skipped
            )

        payload = {
            "commit_id": commit_sha,
            "body": summary,
            "event": "COMMENT",
            "comments": valid_comments
        }

        for attempt in range(3):
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{GITHUB_API_BASE}/repos/{self.repo_full_name}"
                    f"/pulls/{pr_number}/reviews",
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )

                if response.status_code == 429:
                    retry_after = int(
                        response.headers.get("Retry-After", 60)
                    )
                    logger.warning(
                        "github_rate_limited",
                        retry_after=retry_after,
                        attempt=attempt + 1
                    )
                    await asyncio.sleep(retry_after)
                    continue

                if response.status_code == 422:
                    logger.warning(
                        "inline_comments_rejected_falling_back",
                        status=422,
                        body=response.text[:200]
                    )
                    fallback_payload = {
                        "commit_id": commit_sha,
                        "body": summary,
                        "event": "COMMENT",
                        "comments": []
                    }
                    fallback_response = await client.post(
                        f"{GITHUB_API_BASE}/repos/{self.repo_full_name}"
                        f"/pulls/{pr_number}/reviews",
                        headers=self.headers,
                        json=fallback_payload,
                        timeout=30.0
                    )
                    fallback_response.raise_for_status()
                    data = fallback_response.json()
                    logger.info(
                        "pr_review_posted_summary_only",
                        pr_number=pr_number,
                        review_id=data["id"]
                    )
                    return data["id"]

                response.raise_for_status()
                data = response.json()

            review_id = data["id"]
            logger.info(
                "pr_review_posted",
                pr_number=pr_number,
                review_id=review_id,
                inline_comments=len(valid_comments),
                skipped_comments=skipped
            )
            return review_id

        raise Exception("GitHub API rate limit exceeded after 3 retries")
