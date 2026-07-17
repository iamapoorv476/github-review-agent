"""
Pydantic schemas for the dashboard read API.

These shapes are the contract with marginalia-web's lib/data.ts —
if you change a field here, change it there too.
"""
import uuid
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------- stats

class SeverityBreakdown(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0


class StatsResponse(BaseModel):
    reviews_total: int
    reviews_completed: int
    reviews_failed: int
    reviews_running: int          # queued + processing
    findings_total: int
    findings_by_severity: SeverityBreakdown
    median_review_ms: Optional[int]
    repos_active: int
    total_cost_usd: float
    total_tokens: int


# ---------------------------------------------------------------- reviews

class RepoRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    owner: str
    name: str


class PullRequestRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pr_number: int
    title: str
    author_login: str
    base_branch: str
    head_branch: str
    head_sha: str
    files_changed: int
    lines_added: int
    lines_removed: int


class ReviewSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str                   # queued | processing | completed | failed | cancelled
    trigger: str
    triggered_by: Optional[str]
    queued_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_ms: Optional[int]
    model_used: Optional[str]
    input_tokens: int
    output_tokens: int
    total_cost_usd: Optional[float]
    tool_calls_made: int
    findings_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    reasoning_step_count: int
    review_comment_url: Optional[str]

    pull_request: PullRequestRef
    repository: RepoRef


class ReviewListResponse(BaseModel):
    items: List[ReviewSummary]
    total: int
    limit: int
    offset: int


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    file_path: str
    line_number: Optional[int]
    diff_position: Optional[int]
    category: str                 # security | performance | quality
    severity: str                 # critical | high | medium | low
    rule_id: Optional[str]
    title: str
    description: str
    suggestion: Optional[str]
    code_snippet: Optional[str]
    was_posted: bool
    post_failed: bool
    github_comment_id: Optional[int]
    created_at: datetime


class ReasoningStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    step_number: int
    step_type: str                # thought | tool_call | tool_result | finding | summary
    content: str
    tool_name: Optional[str]
    tool_input: Optional[dict]
    tool_output_summary: Optional[str]
    started_at: datetime
    duration_ms: Optional[int]
    tokens_used: int


class ReviewDetail(ReviewSummary):
    error_message: Optional[str]
    retry_count: int
    findings: List[FindingOut]
    reasoning_steps: List[ReasoningStepOut]


# ---------------------------------------------------------------- repos / settings

class RepoSettings(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    installation_id: uuid.UUID    # needed for installation-level PATCH from the UI
    full_name: str
    owner: str
    name: str
    is_private: bool
    default_branch: str
    review_enabled: bool
    total_reviews: int
    total_findings: int
    last_reviewed_at: Optional[datetime]
    account_login: str            # from the parent installation
    review_categories: List[str]  # installation-level: security/performance/quality


class RepoSettingsUpdate(BaseModel):
    review_enabled: Optional[bool] = None


class InstallationSettingsUpdate(BaseModel):
    review_enabled: Optional[bool] = None
    review_categories: Optional[List[str]] = None