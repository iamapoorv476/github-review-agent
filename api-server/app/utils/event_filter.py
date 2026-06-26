from dataclasses import dataclass
from enum import Enum
import structlog

logger = structlog.get_logger()

class ReviewTrigger(Enum):
    PR_OPENED = "pr_opened"
    PR_READY_FOR_REVIEW ="pr_ready_for_review"
    COMMENT_REREVIEW = "comment_rereview"
    INSTALLATION_CREATED = "installation_created"
    INSTALLATION_DELETED = "installation_deleted"
    IGNORED = "ignored"

@dataclass
class FilteredEvent:
    trigger: ReviewTrigger
    should_process: bool
    reason: str

def filter_webhook_event(
        event_type: str,
        payload: dict
) ->  FilteredEvent:
    """
    Determines whether a webhook event should trigger processing.

    Returns a FilteredEvent indicating what to do with this event.
    """
    action = payload.get("action", "")

    if event_type == "pull_request":
        if action == "opened":

            is_draft = payload.get("pull_request", {}).get("draft", False)
            if is_draft:
                return FilteredEvent(
                    trigger=ReviewTrigger.IGNORED,
                    should_process=False,
                    reason="PR opened as draft — waiting for ready_for_review"
                )
            return FilteredEvent(
                trigger=ReviewTrigger.PR_OPENED,
                should_process=True,
                reason="PR opened and ready for review"
            )
        if action == "ready_for_review":
            return FilteredEvent(
                trigger=ReviewTrigger.PR_READY_FOR_REVIEW,
                should_process=True,
                reason="Draft PR marked ready for review"
            )
        return FilteredEvent(
            trigger=ReviewTrigger.IGNORED,
            should_process=False,
            reason=f"PR action '{action}' not relevant"
        )
    if event_type == "issue_comment":
        if action == "created":
            comment_body = payload.get("comment", {}).get("body", "")
            # Check for re-review trigger
            if "@agent re-review" in comment_body.lower():
                # Only trigger on PRs, not regular issues
                is_pr = "pull_request" in payload.get("issue", {})
                if is_pr:
                    return FilteredEvent(
                        trigger=ReviewTrigger.COMMENT_REREVIEW,
                        should_process=True,
                        reason="Re-review requested via comment"
                    )
            return FilteredEvent(
                trigger=ReviewTrigger.IGNORED,
                should_process=False,
                reason="Comment is not a re-review request"
            )
    if event_type == "installation":
        if action == "created":
            return FilteredEvent(
                trigger=ReviewTrigger.INSTALLATION_CREATED,
                should_process=True,
                reason="New app installation"
            )
        if action == "deleted":
            return FilteredEvent(
                trigger=ReviewTrigger.INSTALLATION_DELETED,
                should_process=True,
                reason="App uninstalled"
            )
    logger.debug(
        "webhook_event_ignored",
        event_type=event_type,
        action=action
    )
    return FilteredEvent(
        trigger=ReviewTrigger.IGNORED,
        should_process=False,
        reason=f"Event type '{event_type}' not handled"
    )
