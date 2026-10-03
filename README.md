# SkyGuard AI

SkyGuard AI is a local, simulated weather anomaly detection prototype for Automatic Weather Stations (AWS). It combines validation, historical analysis, spatial consensus, and an Isolation Forest model to estimate trust and sensor health for each station.

## Problem statement

The project addresses AWS anomaly detection for disaster response scenarios, with simulated station readings and explainable evidence for flagged observations.

## Solution

- Validate raw readings for plausibility and consistency.
- Compare current readings against recent history and nearby stations.
- Use a trained Isolation Forest model on simulated weather features.
- Fuse these indicators into a trust score and sensor health score.
- Show alerts, recommendations, and analysis summaries through a dashboard.

## Features

- 10 simulated AWS stations with 24 hours of 5-minute history.
- Real-time style simulated monitoring.
- Faulty-sensor, heatwave, frozen sensor, missing data, and degradation scenarios.
- Trust score and sensor health calculations.
- FastAPI backend with SQLite persistence.
- React + TypeScript + Vite frontend with interactive map and charts.
- Demo-ready API and dashboard.

## Project structure

```text
SIH/
├── backend/
│   ├── app/
│   │   ├── services/
│   │   ├── database.py
│   │   ├── main.py
│   │   ├── models.py
│   │   └── schemas.py
│   ├── tests/
│   ├── requirements.txt
│   └── skyguard.db
├── frontend/
│   ├── src/
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig*.json
├── .gitignore
├── README.md
└── .venv/
```

## Requirements

- Python 3.12+
- Node.js 18+
- npm
- VS Code terminal on Windows

## Backend setup

Open a terminal in VS Code:

```powershell
cd "C:\Users\k.hari sankar singh\OneDrive\Documents\SIH\backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Frontend setup

Open a second terminal:

```powershell
cd "C:\Users\k.hari sankar singh\OneDrive\Documents\SIH\frontend"
npm install
npm run dev
```

Then open the Vite address shown in the terminal, typically http://localhost:5173.

## Demo scenarios

From the UI, open Demo Scenarios and run each of the following:

1. Normal Weather
2. Faulty Sensor
3. Genuine Heatwave
4. Frozen Sensor
5. Missing Data
6. Gradual Sensor Degradation

## Live weather mode

The dashboard can poll current weather from Open-Meteo for the configured station coordinates. Use the Start control in the sidebar to begin polling; Pause and Stop cancel the background task. The default poll interval is 15 minutes and can be increased with `SKYGUARD_POLL_INTERVAL_SECONDS` (values below 5 minutes are raised to 5 minutes). Provider timestamps and ingestion timestamps are stored separately, and identical provider observations are not inserted twice.

This is near-real-time public weather data, not telemetry from physical AWS hardware. The provider's update cadence may be slower than the poll interval, so a successful poll can add zero new observations. Keep scenario runs in demo mode; the app blocks scenario mutations while live polling is active. Check Open-Meteo's current API terms and attribution requirements before publishing a hosted instance.

For local development, the frontend uses the Vite `/api` proxy by default. To call a separately hosted API directly, set `VITE_API_BASE_URL` to the API root including `/api`, for example `https://api.example.com/api`, before building the frontend. Configure backend browser origins as a comma-separated `SKYGUARD_CORS_ORIGINS` value. Set `DATABASE_URL` to a persistent PostgreSQL URL for hosted deployments; SQLite remains the local default. The poller is in-process, so deploy exactly one backend worker/instance for this demo.

## Deploy to Vercel

Vercel runs the FastAPI app as a serverless function and builds the React app into assets served by that same app. The repository root is the Vercel project root; `pyproject.toml` points Vercel to `api/index.py` and `vercel.json` builds the frontend and bundles its output with the API.

1. Import this GitHub repository into Vercel, or use the existing `sky-guard-ai` project.
2. Set the project Root Directory to the repository root (automatic detection), Framework Preset to FastAPI, install command to `pip install -r requirements.txt && npm --prefix frontend ci`, and build command to `npm --prefix frontend run build`.
3. Deploy and verify `/api/health` and the app root.

On Vercel, local SQLite uses `/tmp` and is ephemeral. For persistent records, create a Supabase Postgres project and add its transaction-pooler connection URL as the `DATABASE_URL` Production environment variable in Vercel, then redeploy. The URL is a secret; never commit it or paste it into chat. The backend converts `postgresql://` URLs to the psycopg driver automatically. Vercel's lean function bundle omits NumPy/scikit-learn and uses a robust rolling-statistics fallback for anomaly scoring; local installations continue to use Isolation Forest.

The live-weather control performs one on-demand fetch per click; Vercel does not keep the in-process polling worker alive. Supabase makes records durable but does not turn Vercel into a continuously running monitor. Automated polling requires a scheduled Vercel Cron endpoint and an authorized cron secret, or a persistent worker service. Open-Meteo observations are public weather data, not physical AWS telemetry. Review Vercel/Supabase plan limits and Open-Meteo terms before sharing the app.

## API documentation

After the backend starts, Swagger UI is available at:

http://localhost:8000/docs

## Test execution

```powershell
cd "C:\Users\k.hari sankar singh\OneDrive\Documents\SIH\backend"
.\.venv\Scripts\Activate.ps1
pytest -q
```

## Limitations

This is a local prototype with simulated AWS data. It is not a production-grade meteorological system or an official IMD operational service.

## Future enhancements

- Real sensor integrations and streaming pipelines.
- More robust statistical thresholds.
- Additional anomaly model tuning.
- Enhanced dashboards and alert automation.
- Deployment packaging for cloud hosting.
