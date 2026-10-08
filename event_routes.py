"""HTMX-powered event discovery routes."""

from datetime import datetime, timezone

from flask import Blueprint, abort, g, redirect, render_template, request, url_for

from auth_routes import _login_required, _require_csrf
from auth_service import check_eligibility
from data_store import load
from event_service import (
    APPLICATIONS_FILE,
    EVENTS_FILE,
    _as_utc_datetime,
    apply_to_event,
    find_eligible_events,
    get_apply_status,
    get_badges,
    get_saved_event_ids,
    toggle_saved_event as toggle_saved_event_service,
)


events_bp = Blueprint("events", __name__, url_prefix="/events")

def _seats_left(event, event_applications):
    """Count accepted applications consistently for cards and event details."""
    if not isinstance(event_applications, dict) or any(
        not isinstance(application, dict) for application in event_applications.values()
    ):
        raise ValueError("Event applications must contain application objects.")
    capacity = event.get("slots_needed")
    if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity <= 0:
        raise ValueError("The event must have a positive slots_needed value.")
    accepted_count = sum(
        isinstance(application.get("status"), str)
        and application["status"].casefold() == "accepted"
        for application in event_applications.values()
    )
    return max(0, capacity - accepted_count)


@events_bp.get("/discover")
@_login_required
def discover():
    """Show eligible events and return only event cards for HTMX requests."""
    filters = {
        "search": request.args.get("search", "").strip(),
        "skill": request.args.get("skill", "").strip(),
        "department": request.args.get("department", "").strip(),
        "type": request.args.get("type", "").strip(),
        "date": request.args.get("date", "").strip(),
    }
    user = g.current_user
    matches = find_eligible_events(user, **filters)
    saved_event_ids = set(get_saved_event_ids(user["username"]))
    applications = load(APPLICATIONS_FILE)
    if not isinstance(applications, dict):
        raise ValueError("applications.json must contain an object keyed by event ID.")
    event_cards = []
    for event_id, event in matches:
        seats_left = _seats_left(event, applications.get(event_id, {}))
        event_cards.append({
            "event_id": event_id,
            "event": event,
            "seats_left": seats_left,
            "badges": get_badges({**event, "seats_left": seats_left}, user),
            "is_saved": event_id in saved_event_ids,
        })

    return render_template(
        "discover.html",
        event_cards=event_cards,
        filters=filters,
        partial=request.headers.get("HX-Request", "").lower() == "true",
    )


def _detail_context(event_id):
    """Load public event information and application availability for this user."""
    events = load(EVENTS_FILE)
    if not isinstance(events, dict):
        raise ValueError("events.json must contain an object keyed by event ID.")
    if event_id not in events:
        abort(404)
    event = events[event_id]
    if not isinstance(event, dict):
        raise ValueError("The event record must be an object.")

    applications = load(APPLICATIONS_FILE)
    if not isinstance(applications, dict):
        raise ValueError("applications.json must contain an object keyed by event ID.")
    event_applications = applications.get(event_id, {})
    seats_left = _seats_left(event, event_applications)
    status = get_apply_status(g.current_user["username"], event_id)
    ends_at = _as_utc_datetime(event.get("ends_at"))
    blocked_reason = None
    if status == "Apply":
        if event.get("status") != "open":
            blocked_reason = "This event is not open for applications."
        elif ends_at is not None and ends_at <= datetime.now(timezone.utc):
            blocked_reason = "This event has already ended."
        elif seats_left == 0:
            blocked_reason = "This event is full."
        elif not check_eligibility(
            g.current_user.get("skills", {}), event.get("required_skills", {})
        ):
            blocked_reason = "Your skills do not meet this event's requirements."

    return {
        "event_id": event_id,
        "event": event,
        "seats_left": seats_left,
        "badges": get_badges({**event, "seats_left": seats_left}, g.current_user),
        "apply_status": status,
        "blocked_reason": blocked_reason,
        "is_saved": event_id in get_saved_event_ids(g.current_user["username"]),
    }


@events_bp.get("/<event_id>")
@_login_required
def event_detail(event_id):
    """Show event details without exposing other applicants' information."""
    return render_template(
        "event_detail.html", **_detail_context(event_id), partial=False, error=None
    )


@events_bp.post("/<event_id>/apply")
@_login_required
@_require_csrf
def apply(event_id):
    """Apply once and replace the application control with its current status."""
    context = _detail_context(event_id)
    error = None
    if context["apply_status"] == "Apply":
        if context["blocked_reason"]:
            error = context["blocked_reason"]
        else:
            try:
                apply_to_event(g.current_user["username"], event_id)
            except ValueError as application_error:
                error = str(application_error)
            context = _detail_context(event_id)

    partial = request.headers.get("HX-Request", "").lower() == "true"
    if not partial and error is None:
        return redirect(url_for("events.event_detail", event_id=event_id), code=303)
    return render_template(
        "event_detail.html", **context, partial=partial, error=error
    )


@events_bp.post("/<event_id>/save")
@_login_required
@_require_csrf
def toggle_saved(event_id):
    """Toggle the signed-in user's bookmark and replace only its HTMX control."""
    is_htmx = request.headers.get("HX-Request", "").lower() == "true"
    user_id = g.current_user["username"]
    error = None
    try:
        is_saved = toggle_saved_event_service(user_id, event_id)
    except ValueError as save_error:
        error = str(save_error)
        is_saved = False

    if not is_htmx:
        if error:
            abort(400, description=error)
        return redirect(url_for("events.event_detail", event_id=event_id), code=303)

    return render_template(
        "event_detail.html",
        partial="bookmark",
        event_id=event_id,
        is_saved=is_saved,
        bookmark_error=error,
    )
