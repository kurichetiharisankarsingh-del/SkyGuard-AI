from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine, init_db
from app.models import Alert, AnalysisResult, RawObservation, Station
from app.services.analysis import analyze_all_stations, build_dashboard_summary
from app.services.monitoring import POLL_INTERVAL_SECONDS, live_weather_monitor
from app.services.scenarios import SCENARIO_NAMES, reset_scenario, run_scenario
from app.services.simulator import generate_initial_seed_data, get_monitoring_state, set_monitoring_state

app = FastAPI(title="SkyGuard AI", version="1.0.0")
frontend_dist = Path(os.getenv(
    "FRONTEND_DIST_DIR",
    str(Path(__file__).resolve().parents[2] / "frontend" / "dist"),
)).resolve()
frontend_index = frontend_dist / "index.html"
init_db()
generate_initial_seed_data()
cors_origins = [origin.strip() for origin in os.getenv(
    "SKYGUARD_CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def format_provider_timestamp(timestamp: datetime | None) -> str | None:
    if timestamp is None:
        return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc).isoformat()


@app.on_event("startup")
def startup_event() -> None:
    init_db()
    generate_initial_seed_data()
    if not os.getenv("VERCEL"):
        analyze_all_stations()
    set_monitoring_state(False, POLL_INTERVAL_SECONDS)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await live_weather_monitor.stop()
    set_monitoring_state(False, POLL_INTERVAL_SECONDS)


@app.get("/api/health")
def health_check() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "SkyGuard AI",
        "database": engine.dialect.name,
        "message": "SkyGuard monitoring API is ready.",
    }


@app.get("/api/stations")
def get_stations(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    stations = db.query(Station).all()
    payload = []
    for station in stations:
        latest = db.query(RawObservation).filter(RawObservation.station_id == station.station_id).order_by(RawObservation.timestamp.desc()).first()
        payload.append({
            "station_id": station.station_id,
            "name": station.name,
            "latitude": station.latitude,
            "longitude": station.longitude,
            "status": station.status,
            "last_update": (latest.timestamp if latest else station.last_update).isoformat(),
            "current_temperature": float(latest.temperature) if latest else None,
            "current_pressure": float(latest.pressure) if latest else None,
            "current_humidity": float(latest.humidity) if latest else None,
            "trust_score": float(latest.trust_score) if latest else 0,
            "sensor_health": float(latest.sensor_health) if latest else 0,
            "source": latest.source if latest else "unknown",
            "source_timestamp": format_provider_timestamp(latest.source_timestamp) if latest else None,
        })
    return payload


@app.get("/api/stations/{station_id}")
def get_station(station_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    station = db.query(Station).filter(Station.station_id == station_id).first()
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    latest = db.query(RawObservation).filter(RawObservation.station_id == station_id).order_by(RawObservation.timestamp.desc()).first()
    return {
        "station_id": station.station_id,
        "name": station.name,
        "latitude": station.latitude,
        "longitude": station.longitude,
        "status": station.status,
        "last_update": (latest.timestamp if latest else station.last_update).isoformat(),
        "current_temperature": float(latest.temperature) if latest else None,
        "current_pressure": float(latest.pressure) if latest else None,
        "current_humidity": float(latest.humidity) if latest else None,
        "trust_score": float(latest.trust_score) if latest else 0,
        "sensor_health": float(latest.sensor_health) if latest else 0,
        "source": latest.source if latest else "unknown",
        "source_timestamp": format_provider_timestamp(latest.source_timestamp) if latest else None,
    }


@app.get("/api/stations/{station_id}/history")
def get_station_history(station_id: str, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.query(RawObservation).filter(RawObservation.station_id == station_id).order_by(RawObservation.timestamp.asc()).all()
    return [{
        "timestamp": row.timestamp.isoformat(),
        "temperature": float(row.temperature),
        "pressure": float(row.pressure),
        "humidity": float(row.humidity),
        "trust_score": float(row.trust_score),
        "sensor_health": float(row.sensor_health),
        "anomaly_status": row.anomaly_status,
        "source": row.source,
        "source_timestamp": format_provider_timestamp(row.source_timestamp),
    } for row in rows]


@app.get("/api/stations/{station_id}/health")
def get_station_health(station_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = db.query(RawObservation).filter(RawObservation.station_id == station_id).order_by(RawObservation.timestamp.desc()).first()
    if row is None:
        raise HTTPException(status_code=404, detail="No observations available for this station")
    return {
        "station_id": station_id,
        "health_score": float(row.sensor_health),
        "status": "Excellent" if row.sensor_health >= 90 else "Good" if row.sensor_health >= 75 else "Warning" if row.sensor_health >= 50 else "Needs Inspection",
        "trust_score": float(row.trust_score),
        "latest_observation": row.timestamp.isoformat(),
    }


@app.get("/api/observations")
def get_observations(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.query(RawObservation).order_by(RawObservation.timestamp.desc()).limit(200).all()
    return [{
        "id": row.id,
        "station_id": row.station_id,
        "timestamp": row.timestamp.isoformat(),
        "temperature": float(row.temperature),
        "pressure": float(row.pressure),
        "humidity": float(row.humidity),
        "latitude": row.latitude,
        "longitude": row.longitude,
        "validation_status": row.validation_status,
        "anomaly_status": row.anomaly_status,
        "trust_score": float(row.trust_score),
        "sensor_health": float(row.sensor_health),
        "source": row.source,
        "source_timestamp": row.source_timestamp.isoformat() if row.source_timestamp else None,
    } for row in rows]


@app.get("/api/anomalies")
def get_anomalies(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = db.query(AnalysisResult).order_by(AnalysisResult.created_at.desc()).all()
    return [{
        "id": row.id,
        "station_id": row.station_id,
        "timestamp": row.created_at.isoformat(),
        "parameter": row.parameter,
        "anomaly_type": row.anomaly_type,
        "severity": row.severity,
        "trust_score": float(row.trust_score),
        "sensor_health": float(row.sensor_health),
        "status": row.status,
        "explanation": row.explanation,
    } for row in rows]


@app.get("/api/anomalies/{anomaly_id}")
def get_anomaly(anomaly_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = db.query(AnalysisResult).filter(AnalysisResult.id == anomaly_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return {
        "id": row.id,
        "station_id": row.station_id,
        "timestamp": row.created_at.isoformat(),
        "parameter": row.parameter,
        "anomaly_type": row.anomaly_type,
        "severity": row.severity,
        "trust_score": float(row.trust_score),
        "sensor_health": float(row.sensor_health),
        "status": row.status,
        "explanation": row.explanation,
        "evidence": row.evidence,
    }


@app.get("/api/alerts")
def get_alerts(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    alerts = db.query(Alert).order_by(Alert.timestamp.desc()).all()
    return [{
        "alert_id": alert.alert_id,
        "station_id": alert.station_id,
        "timestamp": alert.timestamp.isoformat(),
        "parameter": alert.parameter,
        "observed_value": float(alert.observed_value),
        "nearby_average": float(alert.nearby_average),
        "anomaly_type": alert.anomaly_type,
        "severity": alert.severity,
        "trust_score": float(alert.trust_score),
        "sensor_health": float(alert.sensor_health),
        "explanation": alert.explanation,
        "recommended_action": alert.recommended_action,
        "status": alert.status,
    } for alert in alerts]


@app.post("/api/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.acknowledged = True
    alert.status = "Acknowledged"
    db.commit()
    return {"status": "ok", "alert_id": alert_id, "message": "Alert acknowledged."}


@app.post("/api/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = "Resolved"
    db.commit()
    return {"status": "ok", "alert_id": alert_id, "message": "Alert marked resolved."}


@app.get("/api/analytics")
def get_analytics(db: Session = Depends(get_db)) -> dict[str, Any]:
    stations = db.query(Station).all()
    anomalies = db.query(AnalysisResult).all()
    alerts = db.query(Alert).all()
    summary = build_dashboard_summary()
    return {
        "summary": summary,
        "stations": [s.station_id for s in stations],
        "anomaly_count": len(anomalies),
        "alert_count": len(alerts),
        "by_station": {s.station_id: sum(1 for a in anomalies if a.station_id == s.station_id) for s in stations},
        "by_type": {k: sum(1 for a in anomalies if a.anomaly_type == k) for k in sorted({a.anomaly_type for a in anomalies})},
    }


@app.get("/api/scenarios")
def get_scenarios() -> list[str]:
    return SCENARIO_NAMES


@app.post("/api/scenarios/{scenario_name}/run")
def run_named_scenario(scenario_name: str) -> dict[str, Any]:
    if live_weather_monitor.status()["active"]:
        raise HTTPException(status_code=409, detail="Pause live weather polling before running demo scenarios.")
    return run_scenario(scenario_name)


@app.post("/api/scenarios/reset")
def reset_named_scenario() -> dict[str, Any]:
    if live_weather_monitor.status()["active"]:
        raise HTTPException(status_code=409, detail="Pause live weather polling before resetting demo scenarios.")
    return reset_scenario()


@app.post("/api/monitoring/start")
async def monitoring_start() -> dict[str, Any]:
    if os.getenv("VERCEL"):
        inserted = await live_weather_monitor.poll_on_demand()
        set_monitoring_state(False, POLL_INTERVAL_SECONDS)
        if live_weather_monitor.status()["last_error"]:
            raise HTTPException(status_code=502, detail=live_weather_monitor.status()["last_error"])
        return {
            "status": "ok",
            "active": False,
            "state": "on-demand",
            "inserted": inserted,
            "message": "Weather updated once. Vercel functions cannot keep a polling worker alive.",
        }
    set_monitoring_state(True, POLL_INTERVAL_SECONDS)
    await live_weather_monitor.start()
    return {"status": "ok", "active": True, "message": "Live Open-Meteo polling started."}


@app.post("/api/monitoring/pause")
async def monitoring_pause() -> dict[str, Any]:
    await live_weather_monitor.pause()
    set_monitoring_state(False, POLL_INTERVAL_SECONDS)
    return {"status": "ok", "active": False, "message": "Live polling paused."}


@app.post("/api/monitoring/stop")
async def monitoring_stop() -> dict[str, Any]:
    await live_weather_monitor.stop()
    set_monitoring_state(False, POLL_INTERVAL_SECONDS)
    return {"status": "ok", "active": False, "message": "Monitoring stopped."}


@app.get("/api/monitoring/status")
def monitoring_status() -> dict[str, Any]:
    persisted = get_monitoring_state()
    runtime = live_weather_monitor.status()
    return {
        **persisted,
        **runtime,
        "last_update": persisted["last_update"],
        "poll_mode": "on-demand" if os.getenv("VERCEL") else "background",
        "storage_mode": "ephemeral" if os.getenv("VERCEL") and engine.dialect.name == "sqlite" else "persistent",
    }


@app.post("/api/model/retrain")
def retrain_model() -> dict[str, Any]:
    analyze_all_stations()
    return {"status": "ok", "message": "Model retrained using the latest simulated baseline data."}


@app.get("/")
def root():
    if frontend_index.is_file():
        return FileResponse(frontend_index)
    return {"message": "SkyGuard AI API is running."}


@app.get("/{path:path}", include_in_schema=False)
def serve_frontend(path: str):
    if path == "api" or path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found")

    requested_file = (frontend_dist / path).resolve()
    if frontend_dist not in requested_file.parents:
        raise HTTPException(status_code=404, detail="File not found")
    if requested_file.is_file():
        return FileResponse(requested_file)
    if frontend_index.is_file() and not Path(path).suffix:
        return FileResponse(frontend_index)
    raise HTTPException(status_code=404, detail="File not found")
