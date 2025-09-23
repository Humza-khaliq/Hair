# Fade By Humz

A modern, responsive booking website for the Fade By Humz barber studio built with Flask, Jinja2 templates, and SQLite. Appointments are stored locally and can sync automatically with Google Calendar via OAuth 2.0.

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

## Google Calendar Integration

The app can push confirmed bookings to Google Calendar. Follow these steps to enable sync:

1. **Create Google Cloud OAuth credentials**
   - Visit the [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
   - Create a new project (or reuse an existing one).
   - Enable the **Google Calendar API** for the project.
   - Create an **OAuth client ID** of type **Desktop App**.
   - Download the OAuth client JSON and save it as `credentials.json` in the project root (or anywhere else – see environment variables below).

2. **First-time authorization**
   - Run the Flask app locally.
   - Book a test appointment. The server opens a browser window prompting you to sign in and grant access to the calendar.
   - After consent, the refresh token is stored in `token.json` (configurable). Future bookings will sync automatically.

3. **Environment variables (optional)**
   | Variable | Description | Default |
   | --- | --- | --- |
   | `SECRET_KEY` | Flask session key for flash messages | `change-this-secret` |
   | `TIME_ZONE` | Time zone used for calendar events | `America/New_York` |
   | `GOOGLE_CREDENTIALS_FILE` | Path to OAuth client (`credentials.json`) | `<project>/credentials.json` |
   | `GOOGLE_TOKEN_FILE` | Path to store OAuth token (`token.json`) | `instance/token.json` |
   | `GOOGLE_CREDENTIALS_JSON` | Optional raw/base64 OAuth client JSON (auto-written to file) | _unset_ |
   | `GOOGLE_CALENDAR_ID` | Target calendar ID (`primary` or specific calendar) | `primary` |
   | `BOOKING_DURATION_MINUTES` | Length of each appointment (minutes) | `45` |

4. **Deployment tips**
   - For production, pre-authorize on the deployment environment so the OAuth prompt doesn’t appear in headless mode.
   - Consider using a service account if you move to a team calendar and can delegate domain-wide authority.

## Styling & Customization

- All global styles live in `static/css/style.css`. Update gradients, typography, and layout as needed to match the brand.
- Templates are modular with `base.html` providing the nav, footer, and flash messaging.
- Replace placeholder contact information in `templates/contact.html` with real social or booking links.

## Running Tests

There are no automated tests bundled. Before deploying, manually validate:

- Booking creation and validation
- Google Calendar sync (when credentials are configured)
- Responsive layout (mobile, tablet, desktop)

## Notes

- The Google client libraries are optional—if they are not installed or credentials are missing, the app gracefully stores bookings locally and flashes a reminder to connect Calendar.
- Store secrets securely (e.g., environment variables or configuration managers) before deploying.
## Docker

- Build the production image locally: `docker build -t fade-by-humz .`
- Run it: `docker run --rm -p 8080:8080 -e PORT=8080 fade-by-humz`
- The app listens on `0.0.0.0:8080` inside the container and serves via Gunicorn.
- The Gunicorn command respects the `PORT` environment variable (Render sets this automatically).
- Mount or copy `credentials.json` / `token.json` if you want Calendar sync while running in Docker. Alternatively set `GOOGLE_CREDENTIALS_JSON` to the raw JSON or a base64-encoded string.

## Deploying Free on Render

Render’s free web service tier can host the Docker image 24/7 (sleeping when idle but waking on traffic). Steps:

1. Push this project to a Git repository (Render pulls from GitHub/GitLab/Bitbucket).
2. Sign up at [Render](https://render.com) and create a **New +** → **Web Service**.
3. Choose the repo, select the **Docker** environment, and Render will auto-detect `render.yaml`.
4. Set the instance type to **Free** and pick a region near your clients.
5. Add the following environment variables under **Environment**:
   - `SECRET_KEY=<your-random-secret>`
   - `TIME_ZONE=America/New_York`
   - `GOOGLE_CALENDAR_ID=primary` (or a specific calendar ID)
   - (optional) `GOOGLE_CREDENTIALS_FILE=/etc/secrets/credentials.json` if you drop in the secret file below.
   - `GOOGLE_CREDENTIALS_JSON` with either the raw JSON (multi-line allowed) or a base64 version of `credentials.json`. To base64 encode locally: `base64 credentials.json > credentials.b64`.
   - (optional) `GOOGLE_TOKEN_FILE=/etc/secrets/token.json` if you upload a persistent token file.
6. Deploy. On first booking Render will open an OAuth window in the logs—use the **Shell** tab → `python` REPL to run the OAuth flow once, or run the app locally to generate `token.json` and upload it as a Render Secret File.
   - If you add secret files, use the **Secret Files** section: `credentials.json` and optionally `token.json`. Render mounts them at `/etc/secrets/<name>`.
7. After the token is stored, bookings sync automatically. Render provides an HTTPS URL, and the service will stay reachable without your laptop.

_Alternative free hosts:_ Fly.io (via `fly launch`) or Railway (Docker deploy). Both accept this Dockerfile with minor config tweaks if you prefer other platforms.
