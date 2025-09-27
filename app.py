from __future__ import annotations

import base64
import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, url_for

try:
    import gspread
    from gspread.exceptions import WorksheetNotFound
    from google.oauth2.service_account import Credentials as ServiceAccountCredentials

    GSPREAD_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    GSPREAD_AVAILABLE = False
    WorksheetNotFound = None  # type: ignore


BASE_DIR = Path(__file__).resolve().parent
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

    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "change-this-secret"),
        DATABASE=str(database_path),
        GOOGLE_SERVICE_ACCOUNT_FILE=os.environ.get(
            "GOOGLE_SERVICE_ACCOUNT_FILE", str(BASE_DIR / "service_account.json")
        ),
        GOOGLE_SERVICE_ACCOUNT_JSON=os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"),
        GOOGLE_SHEET_ID=os.environ.get("GOOGLE_SHEET_ID"),
        GOOGLE_SHEET_WORKSHEET=os.environ.get("GOOGLE_SHEET_WORKSHEET", "Bookings"),
    )

    app.extensions.setdefault("gspread_client", None)
    app.extensions.setdefault("gspread_spreadsheets", {})

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

            flash("Appointment booked! We'll reach out soon to confirm.", "success")
            return redirect(url_for("book"))

        return render_template(
            "book.html",
            service_types=SERVICE_TYPES,
        )

    @app.route("/location")
    def location():
        return render_template("location.html")

    @app.route("/contact")
    def contact():
        return render_template("contact.html")

    @app.route("/health")
    def health():
        return "ok", 200

    @app.route("/debug-sa")
    def debug_service_account():  # pragma: no cover - diagnostics
        path = app.config.get("GOOGLE_SERVICE_ACCOUNT_FILE")
        exists = bool(path and Path(path).exists())
        info = {"path": path, "exists": exists}
        if exists:
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    payload = json.load(fh)
                info["client_email"] = payload.get("client_email")
            except Exception as exc:  # pragma: no cover
                info["error"] = str(exc)
        return info, (200 if exists else 500)

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
    appointment_local = appointment_dt.strftime("%Y-%m-%d %H:%M")

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
    append_booking_to_sheet(
        app,
        {
            "created_at": stored_at,
            "name": name,
            "service_type": service_type,
            "appointment_local": appointment_local,
            "appointment_iso": stored_dt,
        },
    )
    return booking_id


GOOGLE_SHEETS_SCOPE = ["https://www.googleapis.com/auth/spreadsheets"]


def append_booking_to_sheet(app: Flask, booking: dict[str, str]) -> None:
    """Append booking details to Google Sheets if configured."""
    if not GSPREAD_AVAILABLE:
        app.logger.debug("gspread not installed; skipping Google Sheets sync.")
        return

    sheet_id = app.config.get("GOOGLE_SHEET_ID")
    if not sheet_id:
        app.logger.debug("GOOGLE_SHEET_ID not set; skipping Google Sheets sync.")
        return

    try:
        spreadsheet = get_spreadsheet(app, sheet_id)
        worksheet_title = app.config.get("GOOGLE_SHEET_WORKSHEET", "Bookings")
        try:
            worksheet = spreadsheet.worksheet(worksheet_title)
        except WorksheetNotFound:  # pragma: no cover - requires Sheets API
            worksheet = spreadsheet.add_worksheet(title=worksheet_title, rows="200", cols="6")
            worksheet.append_row(
                ["Created At (UTC)", "Name", "Service", "Appointment (local)", "Appointment ISO"],
                value_input_option="USER_ENTERED",
            )

        worksheet.append_row(
            [
                booking["created_at"],
                booking["name"],
                booking["service_type"],
                booking["appointment_local"],
                booking["appointment_iso"],
            ],
            value_input_option="USER_ENTERED",
        )
        app.logger.info("Appended booking for %s to Google Sheets.", booking["name"])
    except Exception as exc:  # pragma: no cover - external service
        app.logger.exception("Failed to append booking to Google Sheets: %s", exc)


def get_spreadsheet(app: Flask, sheet_id: str):
    cache = app.extensions.setdefault("gspread_spreadsheets", {})
    if sheet_id in cache:
        return cache[sheet_id]

    client = get_gspread_client(app)
    spreadsheet = client.open_by_key(sheet_id)
    cache[sheet_id] = spreadsheet
    return spreadsheet


def get_gspread_client(app: Flask):
    client = app.extensions.get("gspread_client")
    if client is not None:
        return client

    creds = load_service_account_credentials(app)
    client = gspread.authorize(creds)
    app.extensions["gspread_client"] = client
    return client


def load_service_account_credentials(app: Flask):
    json_payload = app.config.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if json_payload:
        try:
            if not json_payload.strip().startswith("{"):
                json_payload = base64.b64decode(json_payload).decode("utf-8")
            info = json.loads(json_payload)
        except Exception as exc:  # pragma: no cover - config error
            raise ValueError("Invalid GOOGLE_SERVICE_ACCOUNT_JSON payload") from exc
        return ServiceAccountCredentials.from_service_account_info(info, scopes=GOOGLE_SHEETS_SCOPE)

    file_path = app.config.get("GOOGLE_SERVICE_ACCOUNT_FILE")
    if file_path and Path(file_path).exists():
        return ServiceAccountCredentials.from_service_account_file(file_path, scopes=GOOGLE_SHEETS_SCOPE)

    default_path = BASE_DIR / "service_account.json"
    if default_path.exists():
        return ServiceAccountCredentials.from_service_account_file(str(default_path), scopes=GOOGLE_SHEETS_SCOPE)

    raise FileNotFoundError(
        "Google service account credentials not found. Configure GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE."
    )

app = create_app()

def main() -> None:
    debug_enabled = os.environ.get("FLASK_DEBUG", "0") in {"1", "true", "True"}
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=debug_enabled,
    )


if __name__ == "__main__":
    main()
