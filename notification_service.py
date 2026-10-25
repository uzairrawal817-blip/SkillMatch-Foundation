"""Persistent event notifications stored through the shared data store."""

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo
import secrets

from data_store import load, save


NOTIFICATIONS_FILE = "notifications.json"
ALLOWED_KINDS = {
    "event_posted",
    "event_details_updated",
    "application_submitted",
    "application_accepted",
    "application_rejected",
    "event_ended",
}


def _load_notifications() -> dict[str, Any]:
    document = load(NOTIFICATIONS_FILE)
    if not isinstance(document, dict):
        raise ValueError("notifications.json must contain an object keyed by username.")
    return document


def _required_text(value: Any, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Notification '{field}' must be a non-empty string.")
    normalized = value.strip()
    if len(normalized) > limit:
        raise ValueError(f"Notification '{field}' must be {limit} characters or fewer.")
    return normalized


def _validate_entry(entry: Any, username: str) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise ValueError(f"Each notification for '{username}' must be an object.")
    for field in ("id", "kind", "title", "message", "created_at"):
        if not isinstance(entry.get(field), str) or not entry[field].strip():
            raise ValueError(f"Notification for '{username}' has an invalid '{field}'.")
    if entry["kind"] not in ALLOWED_KINDS:
        raise ValueError(f"Notification for '{username}' has an invalid kind.")
    if not isinstance(entry.get("is_read"), bool):
        raise ValueError(f"Notification for '{username}' has an invalid read state.")
    event_id = entry.get("event_id")
    if event_id is not None and (not isinstance(event_id, str) or not event_id.strip()):
        raise ValueError(f"Notification for '{username}' has an invalid event ID.")
    return entry


def _user_entries(document: dict[str, Any], username: str) -> list[dict[str, Any]]:
    entries = document.get(username, [])
    if not isinstance(entries, list):
        raise ValueError(f"Notifications for '{username}' must be a list.")
    return [_validate_entry(entry, username) for entry in entries]


def add_notifications(
    recipients: list[str] | tuple[str, ...],
    *,
    kind: str,
    title: str,
    message: str,
    event_id: str,
) -> int:
    """Append one event notice for each distinct recipient and persist it."""
    if not isinstance(recipients, (list, tuple)):
        raise ValueError("Notification recipients must be a list or tuple.")
    if kind not in ALLOWED_KINDS:
        raise ValueError("Notification kind is not supported.")
    safe_title = _required_text(title, "title", 120)
    safe_message = _required_text(message, "message", 500)
    safe_event_id = _required_text(event_id, "event_id", 120)
    usernames = []
    for recipient in recipients:
        username = _required_text(recipient, "recipient", 120)
        if username not in usernames:
            usernames.append(username)
    if not usernames:
        return 0

    document = _load_notifications()
    created_at = datetime.now(timezone.utc).isoformat()
    for username in usernames:
        entries = _user_entries(document, username)
        entries.append({
            "id": secrets.token_urlsafe(12),
            "kind": kind,
            "title": safe_title,
            "message": safe_message,
            "event_id": safe_event_id,
            "created_at": created_at,
            "is_read": False,
        })
        document[username] = entries
    save(NOTIFICATIONS_FILE, document)
    return len(usernames)


def get_user_notifications(username: str) -> list[dict[str, Any]]:
    """Return the signed-in user's event notices, newest first."""
    username = _required_text(username, "username", 120)
    document = _load_notifications()
    entries = _user_entries(document, username)
    results = []
    for entry in entries:
        parsed = datetime.fromisoformat(entry["created_at"].replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        local_time = parsed.astimezone(ZoneInfo("Asia/Kolkata"))
        results.append({
            **entry,
            "created_display": local_time.strftime("%b %d, %Y at %I:%M %p IST"),
        })
    return sorted(results, key=lambda item: item["created_at"], reverse=True)


def get_unread_notification_count(username: str) -> int:
    """Count unread notices belonging only to the requested user."""
    return sum(
        not notification["is_read"]
        for notification in get_user_notifications(username)
    )


def mark_notification_read(username: str, notification_id: str) -> bool:
    """Mark one of the user's notices read; return False when it is not theirs."""
    username = _required_text(username, "username", 120)
    notification_id = _required_text(notification_id, "notification_id", 100)
    document = _load_notifications()
    entries = _user_entries(document, username)
    for entry in entries:
        if entry["id"] == notification_id:
            if entry["is_read"]:
                return False
            entry["is_read"] = True
            document[username] = entries
            save(NOTIFICATIONS_FILE, document)
            return True
    return False


def mark_all_notifications_read(username: str) -> int:
    """Mark every unread notice for this user read and return the changed count."""
    username = _required_text(username, "username", 120)
    document = _load_notifications()
    entries = _user_entries(document, username)
    changed = 0
    for entry in entries:
        if not entry["is_read"]:
            entry["is_read"] = True
            changed += 1
    if changed:
        document[username] = entries
        save(NOTIFICATIONS_FILE, document)
    return changed
