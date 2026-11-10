"""Additive event visuals and immutable certificate-theme regression tests."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import certificate_service
import data_store
from app import app
from certificate_themes import CERTIFICATE_THEMES, get_certificate_theme
from event_presentation import event_visual, validate_image_url
from event_service import create_event
from notification_service import add_notifications


class EventImagesAndThemesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="skillmatch-visuals-")
        self.storage = patch.object(data_store, "DATA_DIR", Path(self.temp.name))
        self.storage.start()
        self.old_config = {
            key: app.config[key] for key in ("TESTING", "SESSION_COOKIE_SECURE")
        }
        app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)
        self.client = app.test_client()
        data_store.save("users.json", {
            "organizer": {"name": "Organizer One", "role": "Organizer", "skills": {}},
            "volunteer": {
                "name": "Volunteer One", "role": "Student Volunteer",
                "skills": {"Python": 4}, "dept": "CSE",
            },
        })

    def tearDown(self):
        app.config.update(self.old_config)
        self.storage.stop()
        self.temp.cleanup()

    def sign_in(self, username):
        with self.client.session_transaction() as session:
            session["username"] = username
            session["csrf_token"] = "test-csrf"

    def event(self, **overrides):
        payload = {
            "name": "Campus Hackathon",
            "description": "Use technology to support our community.",
            "organizer": "organizer",
            "required_skills": {"Python": 2},
            "slots_needed": 5,
            "image_url": "https://images.example.org/campus.jpg",
        }
        payload.update(overrides)
        return create_event(payload)

    @staticmethod
    def form(**overrides):
        values = {
            "title": "Campus Garden Day", "description": "Help our campus garden.",
            "required_skills": "Python: 2", "department": "CSE",
            "event_type": "Workshop", "date": "2030-03-10", "start_time": "09:00",
            "venue": "Campus", "duration": "2", "seats": "5",
            "category": "Environment", "image_url": "https://images.example.org/garden.jpg",
            "csrf_token": "test-csrf",
        }
        values.update(overrides)
        return values

    def test_image_validation_defaults_and_legacy_fallback_do_not_rewrite_records(self):
        event_id = self.event()
        event = data_store.load("events.json")[event_id]
        self.assertEqual(event["category"], "Tech")
        for url in ("javascript:alert(1)", "http://example.org/a.jpg", "https://a b/c.jpg"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_image_url(url)
        self.assertEqual(validate_image_url(""), "")
        legacy = {"name": "Tutoring day", "image_url": "javascript:bad", "type": "Workshop"}
        before = dict(legacy)
        self.assertEqual(event_visual(legacy)["category"], "Education")
        self.assertEqual(event_visual(legacy)["image_url"], "")
        self.assertTrue(event_visual(legacy)["default_image_url"].endswith("/education.jpg"))
        self.assertEqual(legacy, before)
        for filename in (
            "environment", "education", "health", "community-service", "tech",
            "arts", "sports-fitness", "animal-welfare", "fundraising",
        ):
            self.assertTrue((Path(app.static_folder) / "images" / "events" / f"{filename}.jpg").is_file())

    def test_owned_create_edit_image_controls_and_images_on_event_lists(self):
        self.sign_in("organizer")
        form = self.client.get("/dashboard/events/new")
        self.assertIn(b'name="image_url"', form.data)
        self.assertIn(b'name="category"', form.data)
        self.assertEqual(self.client.post("/dashboard/events/new", data=self.form()).status_code, 303)
        saved = data_store.load("events.json")["e1"]
        self.assertEqual(saved["category"], "Environment")
        self.assertIn("garden.jpg", saved["image_url"])
        invalid = self.client.post(
            "/dashboard/events/e1/edit", data=self.form(image_url="javascript:bad"),
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(data_store.load("events.json")["e1"], saved)
        changed = self.client.post(
            "/dashboard/events/e1/edit",
            data=self.form(image_url="https://images.example.org/new.jpg"),
        )
        self.assertEqual(changed.status_code, 303)
        self.assertIn(b"new.jpg", self.client.get("/dashboard").data)
        self.sign_in("volunteer")
        for path in ("/events/discover", "/events/e1"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"new.jpg", response.data)
            self.assertIn(b'loading="lazy"', response.data)
        self.assertEqual(self.client.get("/dashboard/events/new").status_code, 403)
        add_notifications(
            ["volunteer"], kind="event_posted", title="New event",
            message="Review the event", event_id="e1",
        )
        self.assertIn(b"new.jpg", self.client.get("/notifications").data)

    def issue(self, category="Environment"):
        event_id = self.event(category=category, status="completed")
        data_store.save("applications.json", {
            event_id: {"volunteer": {
                "status": "accepted", "role": "Event support", "hours": 7, "notes": "",
            }},
        })
        success, code = certificate_service.generate_certificate(event_id, "volunteer")
        self.assertTrue(success, code)
        return event_id, code, data_store.load("certificates.json")[code]

    def test_theme_snapshot_public_preview_and_private_codes(self):
        event_id, code, record = self.issue()
        self.assertEqual(record["theme_category"], "Environment")
        pdf = certificate_service.render_certificate_pdf(record)
        self.assertIn(b"ENVIRONMENTAL STEWARDSHIP", pdf)
        self.assertNotIn(code.encode(), pdf)
        self.assertIn(b"Organizer One", pdf)
        events = data_store.load("events.json")
        events[event_id]["category"] = "Health"
        data_store.save("events.json", events)
        success, repeated_code = certificate_service.generate_certificate(event_id, "volunteer")
        self.assertTrue(success)
        self.assertEqual(code, repeated_code)
        self.assertEqual(data_store.load("certificates.json")[code]["theme_category"], "Environment")
        page = self.client.get(f"/verify?code={code}")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Certificate verified", page.data)
        self.assertIn(b"certificate.pdf", page.data)
        public_pdf = self.client.get(f"/verify/{code}/certificate.pdf")
        self.assertEqual(public_pdf.mimetype, "application/pdf")
        self.assertEqual(public_pdf.data, pdf)
        self.assertEqual(self.client.get("/verify/UNKNOWN123/certificate.pdf").status_code, 404)
        # Existing owner-only downloads remain protected even with a public verification preview.
        self.assertEqual(self.client.get(f"/certificates/{code}/download").status_code, 302)

    def test_legacy_certificates_always_use_default_and_all_themes_render(self):
        _event_id, code, record = self.issue("Tech")
        record.pop("theme_category")
        record.pop("category")
        data_store.save("certificates.json", {code: record})
        legacy = certificate_service.render_verified_certificate_pdf(code)
        self.assertIn(b"PARTICIPATION", legacy)
        self.assertEqual(certificate_service.verify_certificate(code)["theme"]["category"], "Community Service")
        self.assertEqual(get_certificate_theme("unknown")["category"], "Community Service")
        for category, theme in CERTIFICATE_THEMES.items():
            with self.subTest(category=category):
                pdf = certificate_service._render_certificate_pdf(
                    "Volunteer One", "Campus Event", 7,
                    organizer_name="Organizer One", theme_category=category,
                )
                self.assertTrue(pdf.startswith(b"%PDF-1.4"))
                self.assertIn(b"/Count 1", pdf)
                self.assertIn(theme["citation"].encode(), pdf)


if __name__ == "__main__":
    unittest.main()
