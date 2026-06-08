"""
Shared notification report logic for all notifier channels.
"""
from typing import Any, Dict, List, Optional, Tuple

StatusBanner = Tuple[str, str, str]  # (text, icon, hex_color)

UPDATE_TYPE_EMOJI = {
    "major": "🚀",
    "minor": "✨",
    "patch": "🐞",
    "build": "🏗️",
    "digest": "📦",
}


def update_type_emoji(update_type: str) -> str:
    """Return the emoji symbol for an update type (shared by email and Telegram)."""
    return UPDATE_TYPE_EMOJI.get(update_type, "⚪")


def has_noteworthy_events(stats: Dict[str, Any]) -> bool:
    """Return True when the update run produced something worth notifying about."""
    return (
        stats.get("containers_updated", 0) > 0
        or stats.get("containers_failed", 0) > 0
        or stats.get("containers_skipped", 0) > 0
        or bool(stats.get("errors"))
        or bool(stats.get("warnings"))
    )


def resolve_status_banner(stats: Dict[str, Any]) -> Optional[StatusBanner]:
    """
    Determine the email status banner, or None to omit it.

    When containers were checked but nothing was updated, failed, or skipped,
    there is nothing meaningful to highlight in a banner.
    """
    failed = stats.get("containers_failed", 0)
    updated = stats.get("containers_updated", 0)
    skipped = stats.get("containers_skipped", 0)
    processed = stats.get("containers_processed", 0)
    errors = stats.get("errors", [])

    if failed > 0 or errors:
        return ("Issues Detected", "⚠️", "#dc3545")
    if updated > 0:
        return ("Updates Successful", "✅", "#28a745")
    if skipped > 0:
        return ("Containers Skipped", "⏭️", "#ffc107")
    if processed > 0:
        return None
    return ("No Containers Checked", "ℹ️", "#6c757d")


def should_send_notification(
    stats: Dict[str, Any],
    dry_run: bool,
    notifiers_config: Any,
) -> bool:
    """
    Decide whether to send notifications for this update run.

    sendOn:
      - changes (default): only when updates, failures, skips, errors, or warnings
      - all: always when at least one container was checked (legacy behaviour)
    """
    send_on = getattr(notifiers_config, "sendOn", None) or "changes"
    if isinstance(send_on, str):
        send_on = send_on.strip().lower()

    send_on_dry_run = getattr(notifiers_config, "sendOnDryRun", True)
    if isinstance(send_on_dry_run, str):
        send_on_dry_run = send_on_dry_run.strip().lower() == "true"

    if dry_run and not send_on_dry_run:
        return False

    if send_on == "all":
        if stats.get("containers_processed", 0) == 0 and not stats.get("errors"):
            return False
        return True

    return has_noteworthy_events(stats)


def format_duration(start_time, end_time) -> str:
    """Format elapsed time between two datetimes as a human-readable string."""
    if not start_time or not end_time:
        return ""
    total_duration = (end_time - start_time).total_seconds()
    if total_duration < 60:
        return f"{total_duration:.1f}s"
    if total_duration < 3600:
        return f"{total_duration / 60:.1f}m"
    return f"{total_duration / 3600:.1f}h"
