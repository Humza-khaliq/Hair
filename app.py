from __future__ import annotations

import base64
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pytz
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
    jsonify,
)

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    GOOGLE_LIBRARIES_AVAILABLE = True
except ImportError:  # pragma: no cover - dependency may be missing locally
    GOOGLE_LIBRARIES_AVAILABLE = False


BASE_DIR = Path(__file__).resolve().parent
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
SERVICE_TYPES = [
    "Signature Fade",
    "Skin Fade",
    "Lineup",
    "Beard Trim",
    "Fade + Beard Combo",
    "Custom Consultation",
]


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    database_path = BASE_DIR / "instance" / "bookings.db"
    database_path.parent.mkdir(parents=True, exist_ok=True)

    default_token_path = os.environ.get("GOOGLE_TOKEN_FILE")
    if not default_token_path:
        default_token_path = str(database_path.parent / "token.json")

    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "change-this-secret"),
        DATABASE=str(database_path),
        TIME_ZONE=os.environ.get("TIME_ZONE", "America/New_York"),
        GOOGLE_CREDENTIALS_FILE=os.environ.get(
            "GOOGLE_CREDENTIALS_FILE", str(BASE_DIR / "credentials.json")
        ),
        GOOGLE_TOKEN_FILE=default_token_path,
        GOOGLE_CALENDAR_ID=os.environ.get("GOOGLE_CALENDAR_ID", "primary"),
        BOOKING_DURATION_MINUTES=int(os.environ.get("BOOKING_DURATION_MINUTES", "45")),
    )

    configure_logging(app)
    init_db(app)

    @app.context_processor
    def inject_globals():
        return {"current_year": datetime.utcnow().year}

    @app.route("/")
    def home():
        return render_template("index.html", service_types=SERVICE_TYPES)

    @app.route("/services")
    def services():
        services_payload = [
            {
                "name": "Signature Fade",
                "duration": "45 min",
                "price": "$35",
                "description": "Crisp gradients with precise detailing for that fresh fade look.",
            },
            {
                "name": "Skin Fade",
                "duration": "50 min",
                "price": "$40",
                "description": "Ultra-clean fade that melts to skin with sharp, sculpted lines.",
            },
            {
                "name": "Lineup",
                "duration": "25 min",
                "price": "$20",
                "description": "Clean edges and crisp outlines to keep your style dialed in.",
            },
            {
                "name": "Beard Trim",
                "duration": "30 min",
                "price": "$25",
                "description": "Refined shaping and conditioning tailored to your beard goals.",
            },
            {
                "name": "Fade + Beard Combo",
                "duration": "75 min",
                "price": "$55",
                "description": "Full head-to-beard refresh with seamless transitions and details.",
            },
            {
                "name": "Custom Consultation",
                "duration": "15 min",
                "price": "$10",
                "description": "Quick style check-in to map out your next signature look.",
            },
        ]
        return render_template("services.html", services=services_payload)

    @app.route("/book", methods=["GET", "POST"])
    def book():
        calendar_connected = token_exists(app)
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            service_type = request.form.get("service_type", "").strip()
            appointment_date = request.form.get("appointment_date")
            appointment_time = request.form.get("appointment_time")

            if not name or not service_type or not appointment_date or not appointment_time:
                flash("All booking fields are required.", "error")
                return redirect(url_for("book"))

            try:
                appointment_dt = datetime.strptime(
                    f"{appointment_date} {appointment_time}", "%Y-%m-%d %H:%M"
                )
            except ValueError:
                flash("Invalid date or time format. Please try again.", "error")
                return redirect(url_for("book"))

            if service_type not in SERVICE_TYPES:
                flash("Please choose a valid service.", "error")
                return redirect(url_for("book"))

            booking_id = save_booking(
                app,
                name=name,
                service_type=service_type,
                appointment_dt=appointment_dt,
            )

            event_id = create_calendar_event(app, booking_id)

            if event_id:
                flash("Appointment booked! Check your inbox for the confirmation.", "success")
            else:
                flash(
                    "Appointment saved locally. Connect Google Calendar to enable automatic sync.",
                    "warning",
                )

            return redirect(url_for("book"))

        return render_template(
            "book.html",
            service_types=SERVICE_TYPES,
            calendar_connected=calendar_connected,
        )

    @app.route("/location")
    def location():
        return render_template("location.html")

    @app.route("/contact")
    def contact():
        return render_template("contact.html")

    @app.route("/auth")
    def start_google_auth():
        if not GOOGLE_LIBRARIES_AVAILABLE:
            flash("Google client libraries are not installed on the server.", "error")
            return redirect(url_for("book"))

        credentials_path = materialize_google_credentials(app)
        if not credentials_path.exists():
            flash(
                "Google credentials file missing. Upload credentials.json to continue.",
                "error",
            )
            return redirect(url_for("book"))

        flow = Flow.from_client_secrets_file(
            str(credentials_path),
            scopes=SCOPES,
            redirect_uri=url_for("google_oauth_callback", _external=True),
        )
        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        session["google_auth_state"] = state
        return redirect(authorization_url)

    @app.route("/oauth2callback")
    def google_oauth_callback():
        if not GOOGLE_LIBRARIES_AVAILABLE:
            flash("Google client libraries are not installed on the server.", "error")
            return redirect(url_for("book"))

        credentials_path = materialize_google_credentials(app)
        if not credentials_path.exists():
            flash(
                "Google credentials file missing. Upload credentials.json to continue.",
                "error",
            )
            return redirect(url_for("book"))

        expected_state = session.pop("google_auth_state", None)
        incoming_state = request.args.get("state")
        if expected_state and incoming_state != expected_state:
            flash("State mismatch during Google OAuth. Please try again.", "error")
            return redirect(url_for("book"))

        flow = Flow.from_client_secrets_file(
            str(credentials_path),
            scopes=SCOPES,
            redirect_uri=url_for("google_oauth_callback", _external=True),
        )

        try:
            flow.fetch_token(authorization_response=request.url)
            creds = flow.credentials
            persist_google_token(app, creds)
            flash("Google Calendar connected!", "success")
        except Exception as exc:  # pragma: no cover - runtime protection
            app.logger.exception("OAuth callback failed: %s", exc)
            flash("Failed to complete Google authorization. Please try again.", "error")

        return redirect(url_for("book"))

    @app.route("/debug-auth")
    def debug_auth():  # pragma: no cover - diagnostics
        token_path = Path(app.config["GOOGLE_TOKEN_FILE"])
        info = {
            "token_path": str(token_path),
            "token_exists": token_path.exists(),
        }
        if token_path.exists() and GOOGLE_LIBRARIES_AVAILABLE:
            try:
                creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
                info["token_valid"] = bool(creds and creds.valid)
                info["has_refresh_token"] = bool(getattr(creds, "refresh_token", None))
            except Exception as exc:  # pragma: no cover
                info["error"] = str(exc)
        return jsonify(info)

    return app


def configure_logging(app: Flask) -> None:
    """Set up structured logging for the Flask app."""
    if not app.logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")
        )
        app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


def init_db(app: Flask) -> None:
    """Create the bookings table if it does not exist."""
    with sqlite3.connect(app.config["DATABASE"]) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                service_type TEXT NOT NULL,
                appointment_at TEXT NOT NULL,
                google_event_id TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def save_booking(app: Flask, name: str, service_type: str, appointment_dt: datetime) -> int:
    """Persist a booking and return the new booking ID."""
    stored_at = datetime.utcnow().isoformat()
    stored_dt = appointment_dt.isoformat()

    with sqlite3.connect(app.config["DATABASE"]) as conn:
        cursor = conn.execute(
            """
            INSERT INTO bookings (name, service_type, appointment_at, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (name, service_type, stored_dt, stored_at),
        )
        conn.commit()
        booking_id = cursor.lastrowid

    app.logger.info("Stored booking %s for %s on %s", booking_id, name, stored_dt)
    return booking_id


def fetch_booking(app: Flask, booking_id: int) -> Optional[dict]:
    with sqlite3.connect(app.config["DATABASE"]) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM bookings WHERE id = ?", (booking_id,)
        ).fetchone()
    if row is None:
        return None
    return dict(row)


def materialize_google_credentials(app: Flask) -> Path:
    """Ensure credentials.json exists when provided via environment."""
    credentials_path = Path(app.config["GOOGLE_CREDENTIALS_FILE"])
    creds_payload = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_payload and not credentials_path.exists():
        credentials_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if creds_payload.strip().startswith("{"):
                credentials_path.write_text(creds_payload)
            else:
                credentials_path.write_bytes(base64.b64decode(creds_payload))
            app.logger.info("Materialized Google credentials to %s from environment", credentials_path)
        except Exception as exc:  # pragma: no cover - runtime protection
            app.logger.exception("Unable to write Google credentials file: %s", exc)
    return credentials_path


def persist_google_token(app: Flask, creds: Credentials) -> Path:
    token_path = Path(app.config["GOOGLE_TOKEN_FILE"])
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())
    app.logger.info("Stored Google OAuth token at %s", token_path)
    return token_path


def token_exists(app: Flask) -> bool:
    return Path(app.config["GOOGLE_TOKEN_FILE"]).exists()


def create_calendar_event(app: Flask, booking_id: int) -> Optional[str]:
    """Push a booking to Google Calendar if credentials are configured."""
    booking = fetch_booking(app, booking_id)
    if not booking:
        app.logger.error("Booking %s not found for calendar sync.", booking_id)
        return None

    if not GOOGLE_LIBRARIES_AVAILABLE:
        app.logger.warning("Google client libraries not installed; skipping calendar sync.")
        return None

    credentials_path = materialize_google_credentials(app)
    if not credentials_path.exists():
        app.logger.warning(
            "Google credentials file not found at %s; skipping calendar sync.",
            credentials_path,
        )
        return None

    try:
        creds = load_google_credentials(app, credentials_path)
        service = build("calendar", "v3", credentials=creds)

        appointment_dt = datetime.fromisoformat(booking["appointment_at"])
        tz = pytz.timezone(app.config["TIME_ZONE"])
        localized_start = tz.localize(appointment_dt)
        localized_end = localized_start + timedelta(
            minutes=app.config["BOOKING_DURATION_MINUTES"]
        )

        event_body = {
            "summary": f"Fade By Humz - {booking['service_type']}",
            "description": f"Client: {booking['name']}\nService: {booking['service_type']}",
            "start": {"dateTime": localized_start.isoformat(), "timeZone": tz.zone},
            "end": {"dateTime": localized_end.isoformat(), "timeZone": tz.zone},
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email", "minutes": 24 * 60},
                    {"method": "popup", "minutes": 30},
                ],
            },
        }

        created_event = (
            service.events()
            .insert(calendarId=app.config["GOOGLE_CALENDAR_ID"], body=event_body)
            .execute()
        )

        update_google_event_id(app, booking_id, created_event.get("id"))
        app.logger.info("Created Google Calendar event %s for booking %s", created_event.get("id"), booking_id)
        return created_event.get("id")
    except FileNotFoundError:
        app.logger.warning("Google OAuth token missing; skipping calendar sync.")
        return None
    except Exception as exc:  # pragma: no cover - runtime protection
        app.logger.exception("Failed to create Google Calendar event: %s", exc)
        return None


def load_google_credentials(app: Flask, credentials_path: Path) -> Credentials:
    token_path = Path(app.config["GOOGLE_TOKEN_FILE"])
    if not token_path.exists():
        raise FileNotFoundError(
            f"Google token file not found at {token_path}. Run the /auth flow first."
        )

    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds.valid:
        return creds

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        persist_google_token(app, creds)
        return creds

    raise RuntimeError("Google credentials invalid and no refresh token available.")


def update_google_event_id(app: Flask, booking_id: int, event_id: Optional[str]) -> None:
    with sqlite3.connect(app.config["DATABASE"]) as conn:
        conn.execute(
            "UPDATE bookings SET google_event_id = ? WHERE id = ?", (event_id, booking_id)
        )
        conn.commit()


app = create_app()

def main() -> None:
    debug_enabled = os.environ.get("FLASK_DEBUG", "0") in {"1", "true", "True"}
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=debug_enabled)


if __name__ == "__main__":
    main()
