"""SkillMatch's shared Flask application and teammate route registration points."""

import os

from flask import Flask, render_template

from auth_routes import auth_bp
from certificate_routes import certificates_bp
from dashboard_routes import dashboard_bp
from event_routes import events_bp
from formatting import format_decimal
from notification_routes import notifications_bp


app = Flask(__name__)
app.jinja_env.filters["format_decimal"] = format_decimal
app.register_blueprint(auth_bp)
app.register_blueprint(certificates_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(events_bp)
app.register_blueprint(notifications_bp)


@app.get("/")
def home():
    """Show the shared foundation landing page."""
    return render_template("index.html")


# Teammate 1 — Accounts and profiles: import and register the accounts Blueprint here.
# from features.accounts.routes import accounts_bp
# app.register_blueprint(accounts_bp, url_prefix="/account")

# Teammate 2 — Events and skill matching: import and register the events Blueprint here.
# from features.events.routes import events_bp
# app.register_blueprint(events_bp, url_prefix="/events")

# Teammate 3 — Applications and volunteer review: import and register the applications Blueprint here.
# from features.applications.routes import applications_bp
# app.register_blueprint(applications_bp, url_prefix="/applications")

# Teammate 4 — Contributions and certificates: import and register the recognition Blueprint here.
# from features.recognition.routes import recognition_bp
# app.register_blueprint(recognition_bp, url_prefix="/recognition")


@app.errorhandler(404)
def page_not_found(_error):
    """Render the shared not-found page for unknown routes."""
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_server_error(_error):
    """Show a friendly page without exposing internal exception details."""
    return render_template("500.html"), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        debug=False,
    )
