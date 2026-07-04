import structlog
import httpx
from dataclasses import dataclass
from typing import Optional

logger = structlog.get_logger()

GITHUB_API_BASE = "https://api.github.com"


@dataclass
class DiffFile:
    """Represents one changed file in a PR diff."""
    filename: str
    status: str
    additions: int
    deletions: int
    changes: int
    patch: Optional[str]
    blob_url: str

@dataclass
class PRMetadata:
    """Core PR information needed by the agent."""
    number: int
    title: str
    body: str
    author:str
    base_branch: str
    head_branch: str
    head_sha: str
    files_changed:int
    additions:int
    deletions: int

class GitHubClient:
    """
    Authenticated client for GitHub REST API calls.
    All methods are async and return types dataclasses.
    """

    def __init__(self, token: str, repo_full_name: str):
        self.token = token
        self.repo_full_name = repo_full_name
        self.headers={
            "Authorization":f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
    
    async def get_pr_metadata(self, pr_number: int) -> PRMetadata:
        """Fetches core PR information."""
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
        """
        Fetches all changed files in a PR with their diffs.
        GitHub returns max 300 files — for larger PRs we get the first 300.
        """

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
    
    async def get_file_content(
            self,
            file_path: str,
            ref: str
    ) -> str:
        """
        Fetches the full content of a file at a specific commit.
        Used by the agent to get broader context beyond the diff.
        """
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
                    "utf-8", errors = "replace"
                )
            else:
                content = data.get("content", "")
            
            logger.debug(
                "file_content_fetched",
                file_path=file_path,
                size=len(content)
            )

            return content
    


       
