# Webex Contact Center — Standalone Dashboard

A local developmental dashboard based on **LAB-21190** (Building Custom Webex Contact Center Dashboards). It applies the same API patterns the lab teaches — Users, Org Data, GraphQL reports, and Webex Control Hub / Calling — without the lab UI, step forms, or info buttons.

Use it against **your own organization** to test the APIs and extend the code.

## Quick Start

Open VS Code and open a new terminal.

Create or open a folder you plan on storing this project.

Follow one of the paths based off your OS.

**PC**

```powershell
git clone https://github.com/jzuke-wx1-2026/wxcc-standalone-dashboard.git
cd wxcc-standalone-dashboard

python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python app.py
```

**Mac**

```bash
git clone https://github.com/jzuke-wx1-2026/wxcc-standalone-dashboard.git
cd wxcc-standalone-dashboard

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python3 app.py
```

Open **http://127.0.0.1:5000** in your browser. Enter your access token and organization ID in the Connect panel.

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
