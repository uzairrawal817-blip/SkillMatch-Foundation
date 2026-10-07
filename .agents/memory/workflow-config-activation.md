---
name: Workflow config activation
description: Avoid mistaking an updated workflow command for an updated running process.
---

After changing a workflow command through the validated Replit configuration flow, explicitly restart the workflow once and verify its actual open port and public preview response.

**Why:** The configuration and workflow status can show the new command and wait-for port while the existing process remains alive on its previous port. A direct screenshot can render successfully even when the public preview cannot reach the app.

**How to apply:** After workflow command or port changes, compare open ports with the configured port, restart once, and confirm the public development URL serves the app's HTML rather than a generic status response.
