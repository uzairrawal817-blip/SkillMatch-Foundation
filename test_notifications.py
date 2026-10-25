"""Persistent event-notification behavior for both account roles."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import data_store
import event_service
import notification_service
from app import app
from certificate_service import complete_event
from dashboard_service import (
    create_organizer_event,
    update_application_status,
    update_organizer_event,
)


class NotificationCenterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="skillmatch-notifications-")
        self.storage = patch.object(data_store, "DATA_DIR", Path(self.temp.name))
        self.storage.start()
        self.old_config = {
            key: app.config[key] for key in ("TESTING", "SESSION_COOKIE_SECURE")
        }
        app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)
        data_store.save("users.json", {
            "organizer": {
                "name": "Test Organizer",
                "role": "Organizer",
                "skills": {},
            },
            "volunteer": {
                "name": "Test Volunteer",
                "role": "Student Volunteer",
                "dept": "Computer Science",
                "skills": {"Python": 3},
            },
            "other_volunteer": {
                "name": "Another Volunteer",
                "role": "Student Volunteer",
                "dept": "Computer Science",
                "skills": {"Python": 2},
            },
        })
        self.client = app.test_client()

    def tearDown(self):
        app.config.update(self.old_config)
        self.storage.stop()
        self.temp.cleanup()

    def sign_in(self, username):
        with self.client.session_transaction() as session:
            session["username"] = username
            session["csrf_token"] = "test-csrf"

    @staticmethod
    def organizer_form(**overrides):
        values = {
            "title": "Campus Workshop",
            "description": "A hands-on volunteering event.",
            "required_skills": "Python: 1",
            "department": "Computer Science",
            "event_type": "Workshop",
            "date": "2030-03-10",
            "start_time": "10:30",
            "venue": "The Dome",
            "duration": "2",
            "seats": "5",
        }
        values.update(overrides)
        return values

    def create_service_event(self):
        return event_service.create_event({
            "name": "Dome Cleanup",
            "description": "Help prepare the campus.",
            "organizer": "organizer",
            "required_skills": {"Python": 1},
            "slots_needed": 5,
            "department": "Computer Science",
            "type": "Workshop",
            "location": "The Dome",
            "date": "2030-03-10",
            "starts_at": "2030-03-10T10:30:00+05:30",
            "ends_at": "2030-03-10T12:30:00+05:30",
        })

    def test_post_and_detail_edits_notify_organizer_and_applicants(self):
        event_id = create_organizer_event(
            "organizer", self.organizer_form()
        )
        organizer_notice = notification_service.get_user_notifications("organizer")
        volunteer_notice = notification_service.get_user_notifications("volunteer")
        self.assertEqual(organizer_notice[0]["kind"], "event_posted")
        self.assertEqual(volunteer_notice[0]["kind"], "event_posted")
        self.assertEqual(organizer_notice[0]["event_id"], event_id)

        data_store.save("applications.json", {
            event_id: {
                "volunteer": {"status": "pending", "role": None},
                "other_volunteer": {"status": "accepted", "role": "Setup"},
            }
        })
        update_organizer_event(
            "organizer", event_id, self.organizer_form(title="Updated Workshop")
        )

        for username in ("organizer", "volunteer", "other_volunteer"):
            notices = notification_service.get_user_notifications(username)
            self.assertEqual(notices[0]["kind"], "event_details_updated")
            self.assertIn("Updated Workshop", notices[0]["message"])

    def test_applications_and_decisions_notify_the_other_party(self):
        event_id = self.create_service_event()
        self.sign_in("volunteer")
        self.assertEqual(event_service.apply_to_event("volunteer", event_id), "Applied")
        organizer_notice = notification_service.get_user_notifications("organizer")[0]
        self.assertEqual(organizer_notice["kind"], "application_submitted")
        self.assertIn("Test Volunteer", organizer_notice["message"])

        event_service.apply_to_event("other_volunteer", event_id)
        update_application_status(
            "organizer", event_id, "volunteer", "accepted", "Welcome desk"
        )
        update_application_status(
            "organizer", event_id, "other_volunteer", "rejected"
        )
        self.assertEqual(
            notification_service.get_user_notifications("volunteer")[0]["kind"],
            "application_accepted",
        )
        self.assertEqual(
            notification_service.get_user_notifications("other_volunteer")[0]["kind"],
            "application_rejected",
        )

    def test_event_completion_notifies_organizer_and_accepted_volunteers(self):
        event_id = self.create_service_event()
        data_store.save("applications.json", {
            event_id: {
                "volunteer": {
                    "status": "accepted", "role": "Setup",
                    "hours": 0, "notes": "",
                },
                "other_volunteer": {
                    "status": "rejected", "role": None,
                    "hours": 0, "notes": "",
                },
            }
        })

        success, _message = complete_event(event_id, {
            "volunteer": {"hours": 2, "notes": "Prepared the venue"},
        })

        self.assertTrue(success)
        self.assertEqual(
            notification_service.get_user_notifications("organizer")[0]["kind"],
            "event_ended",
        )
        self.assertEqual(
            notification_service.get_user_notifications("volunteer")[0]["kind"],
            "event_ended",
        )
        self.assertEqual(
            notification_service.get_user_notifications("other_volunteer"),
            [],
        )

    def test_notification_center_is_role_accessible_and_read_state_is_private(self):
        event_id = self.create_service_event()
        notification_service.add_notifications(
            ["volunteer"],
            kind="event_posted",
            title="New event posted",
            message="Check the event details.",
            event_id=event_id,
        )
        notification = notification_service.get_user_notifications("volunteer")[0]

        self.sign_in("volunteer")
        home = self.client.get("/")
        self.assertIn(b'href="/notifications"', home.data)
        self.assertIn(b'aria-label="1 unread"', home.data)
        center = self.client.get("/notifications")
        self.assertEqual(center.status_code, 200)
        self.assertIn(b"New event posted", center.data)
        response = self.client.post(
            f"/notifications/{notification['id']}/read",
            data={"csrf_token": "test-csrf"},
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(
            notification_service.get_unread_notification_count("volunteer"), 0
        )

        self.sign_in("organizer")
        self.assertEqual(self.client.get("/notifications").status_code, 200)
