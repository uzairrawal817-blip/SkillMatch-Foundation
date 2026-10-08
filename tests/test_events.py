"""Part 2 regression checks using disposable storage, never real user records."""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import data_store
import event_service as events
from app import app


class EventTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="skillmatch-tests-")
        self.storage = patch.object(data_store, "DATA_DIR", Path(self.temp.name))
        self.storage.start()
        self.old_config = {
            key: app.config[key] for key in ("TESTING", "SESSION_COOKIE_SECURE")
        }
        app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)
        self.user = {
            "name": "Test Volunteer", "role": "Student Volunteer",
            "dept": "Computer Science", "skills": {"Python": 3},
        }
        data_store.save("users.json", {"test_volunteer": self.user})
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["username"] = "test_volunteer"
            session["csrf_token"] = "test-csrf"

    def tearDown(self):
        app.config.update(self.old_config)
        self.storage.stop()
        self.temp.cleanup()

    def create(self, **overrides):
        start = datetime.now(timezone.utc) + timedelta(days=10)
        data = {
            "name": "Campus Workshop", "description": "Learn and volunteer",
            "organizer": "test_organizer", "required_skills": {"Python": 2},
            "slots_needed": 5, "department": "Computer Science",
            "type": "Workshop", "location": "Dome",
            "date": start.date().isoformat(), "starts_at": start.isoformat(),
            "ends_at": (start + timedelta(hours=2)).isoformat(),
        }
        data.update(overrides)
        return events.create_event(data)

    def test_metadata_is_saved(self):
        event_id = self.create()
        event = data_store.load("events.json")[event_id]
        for key in ("department", "type", "location", "date", "starts_at", "ends_at"):
            self.assertIn(key, event)
        self.assertIn("created_at", event)

    def test_aliases_are_saved_canonically(self):
        event_id = self.create(
            department=None, dept=" Arts ", type=None, event_type=" Seminar ",
            location=None, venue=" Library ", date=None, event_date="2030-01-02",
            starts_at=None, start_at="2030-01-02T09:00:00Z",
            ends_at="2030-01-02T10:00:00Z",
        )
        event = data_store.load("events.json")[event_id]
        self.assertEqual(event["department"], "Arts")
        self.assertEqual(event["type"], "Seminar")
        self.assertEqual(event["location"], "Library")
        self.assertEqual(event["date"], "2030-01-02")
        self.assertEqual(event["starts_at"], "2030-01-02T09:00:00+00:00")

    def test_invalid_metadata_does_not_save(self):
        for fields in (
            {"department": 7}, {"type": []}, {"location": False},
            {"date": "not-a-date"}, {"starts_at": "invalid"},
            {"ends_at": "2000-01-01"}, {"ends_at": 12},
        ):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.create(**fields)
        self.assertEqual(data_store.load("events.json"), {})

    def test_required_fields_and_ids(self):
        with self.assertRaises(ValueError):
            events.create_event({})
        self.assertEqual(self.create(), "e1")
        self.assertEqual(self.create(), "e2")

    def test_all_filters_use_created_metadata(self):
        event_id = self.create()
        event = data_store.load("events.json")[event_id]
        for filters in (
            {"search": "campus"}, {"skill": "python"},
            {"department": "Computer Science"}, {"type": "Workshop"},
            {"date": event["date"]},
        ):
            with self.subTest(filters=filters):
                self.assertEqual(events.find_eligible_events(self.user, **filters)[0][0], event_id)
        self.assertEqual(events.find_eligible_events(self.user, department="Other"), [])

    def test_date_filter_falls_back_to_start(self):
        event_id = self.create(date=None)
        event = data_store.load("events.json")[event_id]
        matches = events.find_eligible_events(self.user, date=event["starts_at"][:10])
        self.assertEqual(matches[0][0], event_id)

    def test_standalone_low_seat_badge_and_purity(self):
        event = {"required_skills": {}, "slots_needed": 2}
        original = dict(event)
        self.assertIn("Closing Soon", events.get_badges(event, self.user))
        self.assertEqual(event, original)

    def test_card_counts_only_accepted_applications(self):
        event_id = self.create()
        data_store.save("applications.json", {event_id: {
            "a": {"status": "accepted"}, "b": {"status": "accepted"},
            "c": {"status": "accepted"}, "d": {"status": "pending"},
        }})
        response = self.client.get("/events/discover", headers={"HX-Request": "true"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Closing Soon", response.data)
        self.assertIn(b"Seats remaining:</strong> 2", response.data)
        self.assertNotIn(b"<!doctype html>", response.data)

    def test_full_card_has_zero_remaining_not_low_seat_badge(self):
        event_id = self.create(slots_needed=1)
        data_store.save("applications.json", {event_id: {"other": {"status": "accepted"}}})
        response = self.client.get("/events/discover", headers={"HX-Request": "true"})
        self.assertIn(b"Seats remaining:</strong> 0", response.data)
        self.assertNotIn(b"Closing Soon", response.data)

    def test_pages_empty_state_and_auth(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertIn(b"No events found", self.client.get("/events/discover").data)
        event_id = self.create()
        self.assertEqual(self.client.get(f"/events/{event_id}").status_code, 200)
        self.assertEqual(self.client.get("/events/missing").status_code, 404)
        with self.client.session_transaction() as session:
            session.pop("username")
        self.assertEqual(self.client.get("/events/discover").status_code, 302)

    def test_apply_csrf_duplicate_and_completed(self):
        event_id = self.create()
        endpoint = f"/events/{event_id}/apply"
        response = self.client.post(endpoint, headers={"HX-Request": "true"})
        self.assertIn(b"form expired", response.data)
        self.assertEqual(events.get_apply_status("test_volunteer", event_id), "Apply")
        response = self.client.post(
            endpoint, data={"csrf_token": "test-csrf"}, headers={"HX-Request": "true"},
        )
        self.assertIn(b"Applied", response.data)
        with self.assertRaises(ValueError):
            events.apply_to_event("test_volunteer", event_id)
        stored = data_store.load("events.json")
        stored[event_id]["ends_at"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        data_store.save("events.json", stored)
        data_store.save("applications.json", {
            event_id: {"test_volunteer": {"status": "accepted"}},
        })
        self.assertEqual(events.get_apply_status("test_volunteer", event_id), "Completed")

    def test_full_event_is_blocked(self):
        event_id = self.create(slots_needed=1)
        data_store.save("applications.json", {event_id: {"other": {"status": "accepted"}}})
        with self.assertRaisesRegex(ValueError, "full"):
            events.apply_to_event("test_volunteer", event_id)
        response = self.client.get(f"/events/{event_id}")
        self.assertIn(b"This event is full", response.data)

    def test_bookmark_toggles_and_preserves_profile(self):
        event_id = self.create()
        endpoint = f"/events/{event_id}/save"
        for expected in (True, False):
            response = self.client.post(
                endpoint, data={"csrf_token": "test-csrf"}, headers={"HX-Request": "true"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(event_id in events.get_saved_event_ids("test_volunteer"), expected)
        self.assertEqual(data_store.load("users.json")["test_volunteer"]["skills"], {"Python": 3})

    def test_served_copy_script(self):
        with self.client.get("/static/js/app.js") as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"async function copyEventLink", response.data)
            self.assertIn(b'document.addEventListener("click", copyEventLink)', response.data)
            self.assertLess(len(response.data.splitlines()), 100)


if __name__ == "__main__":
    unittest.main()
