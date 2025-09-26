from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, url_for


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
