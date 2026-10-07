# SkillMatch

A campus event and volunteer-matching foundation that connects student skills with organizer needs.

## Run & Operate

- `PORT=5000 python app.py` — run the SkillMatch Flask app on the web preview port
- The foundation uses project-local JSON files; no database is configured.

## Stack

- Python Flask and Werkzeug
- Jinja2 templates, HTMX, and a small amount of browser-side JavaScript
- JSON files accessed through `data_store.py`

## Where things live

- `app.py` — Flask app, home page, 404 handler, and feature Blueprint registration points
- `auth_routes.py` and `auth_service.py` — account and authentication routes and service logic
- `data_store.py` — shared JSON load/save helpers; data files go in `data/`
- `templates/` — shared Jinja layout, macros, and app pages
- `static/style.css` — SkillMatch styles and responsive breakpoints
- `static/js/app.js` — browser-only modal dismissal behavior
- `static/vendor/htmx.min.js` — locally vendored HTMX library
- `models.md` — source of truth for JSON record shapes
- `pyproject.toml` and `uv.lock` — Python dependency declaration and lockfile

## Architecture decisions

- Feature areas are kept separate through commented Blueprint registration points in `app.py`.
- JSON files are project-local and accessed through `data_store.py`; no database is used for SkillMatch.
- HTMX owns dynamic server-rendered updates; custom JavaScript is limited to documented browser-only behavior.

## Product

SkillMatch is intended to match student volunteers to campus events based on their skills. The foundation includes shared scaffolding and authentication; event matching and volunteer workflows remain future work.

## User preferences

- Use Flask, Jinja2, and HTMX; do not use React, Vue, or another frontend framework for SkillMatch.
- Use JSON files through `data_store.py`; do not add a database.
- Allowed JavaScript is only the vendored HTMX library and `static/js/app.js`, with `app.js` kept under 100 lines total. Check whether HTMX can handle a behavior before adding JavaScript; every function in `app.js` needs a one-line reason Python/HTMX cannot handle it.
- Keep the four feature areas independently owned; each teammate makes their own GitHub commits.
- Leave changes unstaged. Do not run `git add`, `git commit`, or `git push`.

## Gotchas

- Do not store raw passwords; password-based account features must store hashes.
- Keep browser-side behavior in HTMX unless a documented browser-only exception is necessary.
