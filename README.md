# The Cutfish

A modern, responsive booking website for The Cutfish studio built with Flask, Jinja2 templates, and SQLite. Appointments are saved locally and, when configured, mirrored to a Google Sheet for easy review.

## Project Structure

```
.
├── app.py
├── requirements.txt
├── templates/
│   ├── base.html
│   ├── book.html
│   ├── contact.html
│   ├── index.html
│   ├── location.html
│   └── services.html
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── scripts.js
└── instance/
    └── bookings.db  # created automatically after the first run
```

## Quick Start

1. **Create a virtual environment & install dependencies**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Run the development server**
   ```bash
   export FLASK_APP=app.py
   export FLASK_DEBUG=1  # optional
   python app.py
   ```
   Visit `http://127.0.0.1:5000` to explore the site.

3. **Database**
   - SQLite is used to persist bookings locally. The database file (`instance/bookings.db`) is created automatically with the `bookings` table when the app starts.

4. **Booking cadence**
   - Slots are available every Saturday and Sunday from 1:00 PM to 5:00 PM in 30-minute increments.
   - Once a slot is booked it is removed from the dropdown until the following week. On Render’s free tier the disk is ephemeral, so export data periodically or wire up a free remote store (see below).

## Free & Simple Booking Storage Options

Everything now works without Google APIs. Bookings are saved locally out of the box, but you can plug into a free cloud backend with only a few lines of code:

| Option | Why it’s easy | How to integrate |
| --- | --- | --- |
| **Stay on SQLite** | Zero setup; perfect for demos | Export `instance/bookings.db` occasionally. |
| **Supabase (Postgres)** | Free tier, REST + SQL studio | Create a `bookings` table and switch the connection string in `app.py`. |
| **Google Sheets** | Looks like a spreadsheet; free | Use [`gspread`](https://github.com/burnash/gspread) to append rows inside `save_booking`. |
| **Airtable / Notion DB** | Friendly UI for manual edits | Replace `save_booking` with their REST API (both have free tiers). |

Choose whichever feels the most “no fuss” for you—each is free, and none require leaving your laptop on. The default project writes to SQLite and, when configured, also appends rows to a Google Sheet for easy viewing.

### Connecting to Google Sheets (service account)

1. In [Google Cloud Console](https://console.cloud.google.com/), create a new **service account** for your project (Calendar API access is not required).
2. Generate a JSON key and keep it safe:
   - Save it locally as `service_account.json` (but never commit it), **or**
   - Base64‑encode it (`base64 service_account.json > service_account.b64`) and set `GOOGLE_SERVICE_ACCOUNT_JSON` to the resulting string.
3. Create a Google Sheet dedicated to bookings and note the sheet ID (the long string in the sheet URL).
4. Share the sheet with the service account email (e.g., `fade-by-humz@project.iam.gserviceaccount.com`) with **Editor** access.
5. Set the environment variables:
   - `GOOGLE_SHEET_ID=<your-sheet-id>`
   - `GOOGLE_SERVICE_ACCOUNT_FILE` **or** `GOOGLE_SERVICE_ACCOUNT_JSON`
   - (optional) `GOOGLE_SHEET_WORKSHEET=Bookings`

Every booking submission now appends a row to the sheet with timestamps, service details, and scheduled time. If the sheet is not configured the app quietly falls back to storing data in SQLite only.

### Environment variables

| Variable | Description | Default |
| --- | --- | --- |
| `SECRET_KEY` | Flask session key for flash messages | `change-this-secret` |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Optional path to service account JSON for Sheets | `<project>/service_account.json` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Optional raw/base64 service account JSON | _unset_ |
| `GOOGLE_SHEET_ID` | Target Google Sheet ID (required for cloud sync) | _unset_ |
| `GOOGLE_SHEET_WORKSHEET` | Worksheet/tab name inside the sheet | `Bookings` |
| `EMAIL_SMTP_SERVER` | SMTP server for confirmation emails | _unset_ |
| `EMAIL_SMTP_PORT` | SMTP port (e.g. 587) | `587` |
| `EMAIL_SENDER` | From email address | _unset_ |
| `EMAIL_PASSWORD` | SMTP password or app password | _unset_ |
| `EMAIL_USE_TLS` | Set to `0` to disable STARTTLS | `1` |

## Styling & Customization

- All global styles live in `static/css/style.css`. Update gradients, typography, and layout as needed to match the brand.
- Templates are modular with `base.html` providing the nav, footer, and flash messaging.
- Replace placeholder contact information in `templates/contact.html` with real social or booking links.

## Running Tests

There are no automated tests bundled. Before deploying, manually validate:

- Booking creation and validation
- Responsive layout (mobile, tablet, desktop)

## Notes

- Treat `instance/bookings.db` like an application secret—store it somewhere safe or connect to a managed database if you need long-term persistence.
- Store secrets securely (environment variables, Render Secret Files, etc.) before deploying.
## Docker

- Build the production image locally: `docker build -t fade-by-humz .`
- Run it: `docker run --rm -p 8080:8080 -e PORT=8080 fade-by-humz`
- The app listens on `0.0.0.0:8080` inside the container and serves via Gunicorn.
- The Gunicorn command respects the `PORT` environment variable (Render sets this automatically).
- Health check endpoint available at `/health` (returns `ok`) for uptime monitoring.

## Deploying Free on Render

Render’s free web service tier can host the Docker image 24/7 (sleeping when idle but waking on traffic). Steps:

1. Push this project to a Git repository (Render pulls from GitHub/GitLab/Bitbucket).
2. Sign up at [Render](https://render.com) and create a **New +** → **Web Service**.
3. Choose the repo, select the **Docker** environment, and Render will auto-detect `render.yaml`.
4. Set the instance type to **Free** and pick a region near your clients.
5. Add the following environment variables under **Environment**:
   - `SECRET_KEY=<your-random-secret>`
   - (optional) `DATABASE_URL=<supabase-or-other-connection>` if you switch away from SQLite.
   - (optional) `GOOGLE_SHEET_ID`, `GOOGLE_SERVICE_ACCOUNT_JSON` (or `GOOGLE_SERVICE_ACCOUNT_FILE`), and `GOOGLE_SHEET_WORKSHEET` if you want automatic Google Sheets sync.
   - (optional) `EMAIL_SMTP_SERVER`, `EMAIL_SMTP_PORT`, `EMAIL_SENDER`, `EMAIL_PASSWORD` (and `EMAIL_USE_TLS`) to send confirmation emails.
6. Deploy. The health check at `/health` will help you confirm the instance is awake.
7. Optional: wire in Supabase/Sheets by updating `save_booking` once you have API keys.

_Alternative free hosts:_ Fly.io (via `fly launch`) or Railway (Docker deploy). Both accept this Dockerfile with minor config tweaks if you prefer other platforms.
