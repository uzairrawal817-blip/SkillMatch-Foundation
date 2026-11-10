# SkillMatch JSON data shapes

All files live in the project’s `data/` directory and are read or written through
`data_store.py`. Each top-level JSON object is keyed by the record identifier.
The examples below show the complete record shapes used by the shared foundation.

## `users.json`

The key is the user's username. `role` is either `Organizer` or
`Student Volunteer`. `dept` is `null` for organizers and a department name for
student volunteers. Skill ratings are non-negative integers; the foundation does
not impose an upper limit.

```json
{
  "samira": {
    "password_hash": "<stored password hash>",
    "role": "Student Volunteer",
    "name": "Samira Patel",
    "dept": "Environmental Science",
    "skills": {
      "Photography": 4,
      "Event planning": 3
    }
  }
}
```

The attached command-line prototype stores raw passwords in a `password` field.
Do not carry that into new features; use a password hash if password-based
accounts are implemented.

## `events.json`

The key is the event ID. `organizer` refers to a username in `users.json`.
`required_skills` maps skill names to minimum non-negative ratings, and
`slots_needed` is a positive integer.

```json
{
  "campus-garden-day": {
    "name": "Campus Garden Day",
    "description": "Help prepare the community garden for spring.",
    "organizer": "lee",
    "required_skills": {
      "Gardening": 2
    },
    "slots_needed": 8,
    "status": "open"
  }
}
```

Event status is `open` or `completed`.

Optional additive event fields:
- `category`: one of the keys in `CERTIFICATE_THEMES`, default `Community Service`.
  Legacy records without it are classified for display from their existing type/name.
- `image_url`: an optional HTTPS image URL, default empty. Missing images use a
  local category stock photo, with a category-specific gradient behind it.
  New categories without a stock photo use the gradient alone. Existing event
  IDs and other fields are unchanged.

Newly issued certificate records snapshot `category` and `theme_category`.
Reissuing an existing certificate preserves its original theme selection.
Certificates without `theme_category` use the Community Service default theme,
regardless of later event edits. Verification codes remain private on PDFs.

Production storage uses JSON documents in the existing PostgreSQL
`skillmatch_documents` table via `data_store.py`. These optional JSON fields
require no SQL column/table migration and do not rewrite existing documents.

The local category images in `static/images/events/` are illustrative stock
photos, not photographs of the actual SkillMatch events. Sources are free
Pexels photos, distributed under https://www.pexels.com/license/:

| Category | Source |
| --- | --- |
| Environment | https://www.pexels.com/photo/37172064/ |
| Education | https://www.pexels.com/photo/8423049/ |
| Health | https://www.pexels.com/photo/8460125/ |
| Community Service | https://www.pexels.com/photo/6646926/ |
| Tech | https://www.pexels.com/photo/9159069/ |
| Arts | https://www.pexels.com/photo/34512916/ |
| Sports/Fitness | https://www.pexels.com/photo/38010741/ |
| Animal Welfare | https://www.pexels.com/photo/35231857/ |
| Fundraising | https://www.pexels.com/photo/6995106/ |

## `applications.json`

The first key is the event ID; the nested key is the applicant's username.
`role` is `null` until an organizer accepts the application. `hours` is
non-negative and `notes` is a string.

```json
{
  "campus-garden-day": {
    "samira": {
      "status": "pending",
      "role": null,
      "hours": 0,
      "notes": ""
    }
  }
}
```

Application status is `pending`, `accepted`, or `rejected`.
