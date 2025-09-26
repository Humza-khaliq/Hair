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
   - SQLite is used to persist bookings locally. The database file (`instance/bookings.db`) is created automatically with the `bookings` table when the app starts. On Render’s free tier the disk is ephemeral, so export data periodically or wire up a free remote store (see below).

## Free & Simple Booking Storage Options

Everything now works without Google APIs. Bookings are saved locally out of the box, but you can plug into a free cloud backend with only a few lines of code:

| Option | Why it’s easy | How to integrate |
| --- | --- | --- |
| **Stay on SQLite** | Zero setup; perfect for demos | Export `instance/bookings.db` occasionally. |
| **Supabase (Postgres)** | Free tier, REST + SQL studio | Create a `bookings` table and switch the connection string in `app.py`. |
| **Google Sheets** | Looks like a spreadsheet; free | Use [`gspread`](https://github.com/burnash/gspread) to append rows inside `save_booking`. |
| **Airtable / Notion DB** | Friendly UI for manual edits | Replace `save_booking` with their REST API (both have free tiers). |

Choose whichever feels the most “no fuss” for you—each is free, and none require leaving your laptop on.

### Environment variables

| Variable | Description | Default |
| --- | --- | --- |
| `SECRET_KEY` | Flask session key for flash messages | `change-this-secret` |

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
6. Deploy. The health check at `/health` will help you confirm the instance is awake.
7. Optional: wire in Supabase/Sheets by updating `save_booking` once you have API keys.

_Alternative free hosts:_ Fly.io (via `fly launch`) or Railway (Docker deploy). Both accept this Dockerfile with minor config tweaks if you prefer other platforms.
