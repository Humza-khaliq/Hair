from __future__ import annotations

import base64
import json
import logging
import os
import smtplib
import sqlite3
import ssl
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import List

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
    "Scissor Cut",
    "Lineup",
    "First Cut Lineup (Free)",
    "Beard Trim",
    "Fade + Beard Combo",
    "Fade + Scissor + Lineup + Beard Trim",
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
                "duration": "30 min",
                "price": "$15",
                "description": "Fresh fade tailored to your head shape with razor-clean finish.",
            },
            {
                "name": "Skin Fade",
                "duration": "30 min",
                "price": "$15",
                "description": "Ultra-low blend that melts seamlessly into the skin.",
            },
            {
                "name": "Scissor Cut",
                "duration": "30 min",
                "price": "$15",
                "description": "Precision scissor work for length control and natural texture.",
            },
            {
                "name": "Lineup",
                "duration": "15 min",
                "price": "$10",
                "description": "Sharper corners and edges to keep your look crisp between cuts.",
            },
            {
                "name": "First Cut Lineup (Free)",
                "duration": "10 min",
                "price": "$0",
                "description": "First-time clients get a complimentary lineup to set the vibe.",
            },
            {
                "name": "Beard Trim",
                "duration": "20 min",
                "price": "$7",
                "description": "Shaped, detailed, and conditioned to keep your beard dialed in.",
            },
            {
                "name": "Fade + Beard Combo",
                "duration": "45 min",
                "price": "$20",
                "description": "Complete fade and beard clean-up with smooth transitions.",
            },
            {
                "name": "Fade + Scissor + Lineup + Beard Trim",
                "duration": "60 min",
                "price": "$25",
                "description": "Full session: fade, scissor detailing, sharp lineup, and beard finish.",
            },
            {
                "name": "Custom Consultation",
                "duration": "15 min",
                "price": "$10",
                "description": "Talk through a future cut, color, or style shift with pro guidance.",
            },
        ]
        return render_template("services.html", services=services_payload)

    @app.route("/book", methods=["GET", "POST"])
    def book():
        slot_choices = build_slot_choices(app)
        has_open_slots = any(not c["booked"] for c in slot_choices)

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip()
            phone = request.form.get("phone", "").strip()
            service_type = request.form.get("service_type", "").strip()
            slot_value = request.form.get("slot")

            if not all([name, email, phone, service_type, slot_value]):
                flash("All booking fields are required.", "error")
                return render_template(
                    "book.html",
                    service_types=SERVICE_TYPES,
                    slot_choices=slot_choices,
                    has_open_slots=has_open_slots,
                )

            if service_type not in SERVICE_TYPES:
                flash("Please choose a valid service.", "error")
                return render_template(
                    "book.html",
                    service_types=SERVICE_TYPES,
                    slot_choices=slot_choices,
                    has_open_slots=has_open_slots,
                )

            try:
                slot_datetime = datetime.fromisoformat(slot_value)
            except ValueError:
                flash("Selected time slot is invalid. Please choose another.", "error")
                return render_template(
                    "book.html",
                    service_types=SERVICE_TYPES,
                    slot_choices=slot_choices,
                    has_open_slots=has_open_slots,
                )

            slot_lookup = {c["value"]: c for c in slot_choices}
            slot_info = slot_lookup.get(slot_value)
            if slot_info is None:
                flash("That time slot is no longer available.", "error")
                return render_template(
                    "book.html",
                    service_types=SERVICE_TYPES,
                    slot_choices=slot_choices,
                    has_open_slots=has_open_slots,
                )
            if slot_info["booked"]:
                flash("That time slot has already been booked. Please choose another.", "error")
                return render_template(
                    "book.html",
                    service_types=SERVICE_TYPES,
                    slot_choices=slot_choices,
                    has_open_slots=has_open_slots,
                )

            if slot_datetime <= datetime.now():
                flash("Cannot book a slot in the past.", "error")
                return render_template(
                    "book.html",
                    service_types=SERVICE_TYPES,
                    slot_choices=slot_choices,
                    has_open_slots=has_open_slots,
                )

            if has_same_day_booking(app, name, email, slot_datetime.date()):
                flash("You already have a booking that day. Reach out to reschedule instead.", "error")
                return render_template(
                    "book.html",
                    service_types=SERVICE_TYPES,
                    slot_choices=slot_choices,
                    has_open_slots=has_open_slots,
                )

            try:
                booking_id = save_booking(
                    app,
                    name=name,
                    email=email,
                    phone=phone,
                    service_type=service_type,
                    appointment_dt=slot_datetime,
                )
            except sqlite3.IntegrityError:
                flash("That time slot has just been booked. Please pick another.", "error")
                slot_choices = build_slot_choices(app)
                has_open_slots = any(not c["booked"] for c in slot_choices)
                return render_template(
                    "book.html",
                    service_types=SERVICE_TYPES,
                    slot_choices=slot_choices,
                    has_open_slots=has_open_slots,
                )

            send_confirmation_email(
                app,
                {
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "service_type": service_type,
                    "slot_label": slot_info["label"],
                },
            )

            flash("Appointment booked! We just sent a confirmation email.", "success")
            return redirect(url_for("book"))

        return render_template(
            "book.html",
            service_types=SERVICE_TYPES,
            slot_choices=slot_choices,
            has_open_slots=has_open_slots,
        )

    @app.route("/location")
    def location():
        return render_template("location.html")

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
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                service_type TEXT NOT NULL,
                appointment_at TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
            """
        )
        ensure_booking_columns(conn)
        conn.commit()


def ensure_booking_columns(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(bookings)")}
    if "email" not in columns:
        conn.execute("ALTER TABLE bookings ADD COLUMN email TEXT")
    if "phone" not in columns:
        conn.execute("ALTER TABLE bookings ADD COLUMN phone TEXT")
    if "created_at" not in columns:
        conn.execute("ALTER TABLE bookings ADD COLUMN created_at TEXT")
    indices = {row[1] for row in conn.execute("PRAGMA index_list(bookings)")}
    if "idx_booking_slot" not in indices:
        try:
            conn.execute("CREATE UNIQUE INDEX idx_booking_slot ON bookings(appointment_at)")
        except sqlite3.OperationalError:
            pass


def save_booking(
    app: Flask,
    name: str,
    email: str,
    phone: str,
    service_type: str,
    appointment_dt: datetime,
) -> int:
    """Persist a booking and return the new booking ID."""
    stored_at = datetime.utcnow().isoformat()
    stored_dt = appointment_dt.isoformat()
    appointment_local = appointment_dt.strftime("%Y-%m-%d %H:%M")

    with sqlite3.connect(app.config["DATABASE"]) as conn:
        cursor = conn.execute(
            """
            INSERT INTO bookings (name, email, phone, service_type, appointment_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, email, phone, service_type, stored_dt, stored_at),
        )
        conn.commit()
        booking_id = cursor.lastrowid

    app.logger.info("Stored booking %s for %s on %s", booking_id, name, stored_dt)
    append_booking_to_sheet(
        app,
        {
            "created_at": stored_at,
            "name": name,
            "email": email,
            "phone": phone,
            "service_type": service_type,
            "appointment_local": appointment_local,
            "appointment_iso": stored_dt,
        },
    )
    return booking_id


SLOT_START_HOUR = 13
SLOT_END_HOUR = 17
SLOT_INTERVAL = timedelta(minutes=30)
SLOT_WEEKS_AHEAD = 4
WEEKEND_DAYS = {5, 6}


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
            worksheet = spreadsheet.add_worksheet(title=worksheet_title, rows="200", cols="7")
            worksheet.append_row(
                [
                    "Created At (UTC)",
                    "Name",
                    "Email",
                    "Phone",
                    "Service",
                    "Appointment (local)",
                    "Appointment ISO",
                ],
                value_input_option="USER_ENTERED",
            )

        worksheet.append_row(
            [
                booking["created_at"],
                booking["name"],
                booking["email"],
                booking["phone"],
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

def upcoming_weekend_slots(start: date | None = None, weeks: int = 4) -> List[datetime]:
    start_date = start or date.today()
    end_date = start_date + timedelta(weeks=weeks)
    slots: List[datetime] = []
    current = start_date
    while current <= end_date:
        if current.weekday() in WEEKEND_DAYS:
            slot_time = datetime.combine(current, time(hour=SLOT_START_HOUR))
            while slot_time.time() < time(hour=SLOT_END_HOUR):
                slots.append(slot_time)
                slot_time += SLOT_INTERVAL
        current += timedelta(days=1)
    return slots


def fetch_booked_slots(app: Flask) -> set[str]:
    with sqlite3.connect(app.config["DATABASE"]) as conn:
        rows = conn.execute("SELECT appointment_at FROM bookings").fetchall()
    return {row[0] for row in rows}


def has_same_day_booking(app: Flask, name: str, email: str, target_date: date) -> bool:
    target_prefix = f"{target_date.isoformat()}%"
    with sqlite3.connect(app.config["DATABASE"]) as conn:
        row = conn.execute("SELECT 1 FROM bookings WHERE name = ? AND email = ? AND appointment_at LIKE ?", (name, email, target_prefix)).fetchone()
    return row is not None


def build_slot_choices(app: Flask) -> List[dict]:
    slots = upcoming_weekend_slots(weeks=SLOT_WEEKS_AHEAD)
    booked = fetch_booked_slots(app)
    now = datetime.now()
    choices: List[dict] = []
    for slot_dt in slots:
        if slot_dt <= now:
            continue
        iso = slot_dt.isoformat()
        choices.append({"value": iso, "label": slot_dt.strftime("%a %b %d · %I:%M %p"), "booked": iso in booked})
    return choices


def send_confirmation_email(app: Flask, booking: dict[str, str]) -> None:
    smtp_host = os.environ.get("EMAIL_SMTP_SERVER")
    smtp_port = int(os.environ.get("EMAIL_SMTP_PORT", "587"))
    sender = os.environ.get("EMAIL_SENDER")
    password = os.environ.get("EMAIL_PASSWORD")
    recipient = booking.get("email")
    if not all([smtp_host, sender, password, recipient]):
        app.logger.debug("Email settings incomplete; skipping confirmation email.")
        return

    subject = "The Cutfish Booking Confirmation"
    body = (
        f"Hey {booking['name']},\n\n"
        f"Your booking is locked in for {booking['slot_label']} ({booking['service_type']}).\n"
        "If you need to switch times, reply to this email or text the shop.\n\n"
        "Keep swimming in style,\nThe Cutfish"
    )
    message = f"From: {sender}\nTo: {recipient}\nSubject: {subject}\n\n{body}"

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if os.environ.get("EMAIL_USE_TLS", "1") not in {"0", "false", "False"}:
                server.starttls(context=context)
            server.login(sender, password)
            server.sendmail(sender, [recipient], message)
        app.logger.info("Sent confirmation email to %s", recipient)
    except Exception as exc:  # pragma: no cover - external service
        app.logger.exception("Failed to send confirmation email: %s", exc)



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
