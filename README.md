# Webex Contact Center — Standalone Dashboard

A local developmental dashboard based on **LAB-21190** (Building Custom Webex Contact Center Dashboards). It applies the same API patterns the lab teaches — Users, Org Data, GraphQL reports, and Webex Control Hub / Calling — without the lab UI, step forms, or info buttons.

Use it against **your own organization** to test the APIs and extend the code.

## Quick Start

```powershell
# 1. Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Optional: copy .env for regional API base URLs
copy .env.example .env

# 4. Run the dashboard
python app.py
```

Open **http://127.0.0.1:5000** in your browser. Enter your **access token** and **organization ID** in the Connect panel.

## Required Access

Sign in to [developer.webex.com](https://developer.webex.com) with a **Webex Contact Center admin** account. Copy the profile bearer token and organization ID from your profile menu.

The token must be able to call Contact Center configuration APIs (`cjp:config`, `cjp:config_read`, `cjp:config_write`) plus Control Hub / Calling read scopes used by the Webex APIs tab.

## What You Get

| Tab | What it shows |
|-----|----------------|
| Users | Contact Center users, profiles, skills, teams, channel types |
| Org Data | Entry points, queues, teams, auxiliary codes, global variables (editable) |
| Reports | CSR / ASR summaries, session details, real-time agent states |
| Webex APIs | Control Hub people, Calling locations, PSTN / trunk for mapped numbers |

Endpoints and JSON field names live in `api_config.py` so you can change them as APIs evolve. Fetch logic is in `modules/`. The Flask routes in `app.py` and tables in `static/js/dashboard.js` are the main extension points.

The Connect panel keeps the token and org ID **in memory for this process only**. They are discarded when you stop the app (`Ctrl+C`). They are never written into source code or to `data/`. (An optional token in `.env` would still persist — leave those placeholders empty if you want session-only credentials.)

## License

This project is licensed under the [MIT License](LICENSE).

**Not for production use.** This sample code is provided for educational and demonstration purposes only. Use at your own risk.
