from __future__ import annotations

import json
import random
from collections import defaultdict
from datetime import datetime
from math import asin, cos, radians, sin, sqrt
from statistics import median, pstdev

try:
    import numpy as np
    from sklearn.ensemble import IsolationForest
except ImportError:
    np = None
    IsolationForest = None
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Alert, AnalysisResult, RawObservation, SensorHealthHistory, Station


def _latest_for_station(db: Session, station_id: str):
    return db.query(RawObservation).filter(RawObservation.station_id == station_id).order_by(RawObservation.timestamp.desc()).first()


def _all_recent(db: Session, station_id: str, limit: int = 30):
    return db.query(RawObservation).filter(RawObservation.station_id == station_id).order_by(RawObservation.timestamp.desc()).limit(limit).all()[::-1]


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def validate_observation(db: Session, observation: RawObservation) -> tuple[str, list[dict]]:
    issues: list[dict] = []
    if observation.temperature < -40 or observation.temperature > 70:
        issues.append({"status": "Anomaly", "parameter": "temperature", "type": "range", "reason": "Temperature is outside plausible AWS operating range."})
    if observation.pressure < 900 or observation.pressure > 1100:
        issues.append({"status": "Anomaly", "parameter": "pressure", "type": "range", "reason": "Pressure is outside plausible meteorological range."})
    if observation.humidity < 0 or observation.humidity > 100:
        issues.append({"status": "Anomaly", "parameter": "humidity", "type": "range", "reason": "Humidity is outside physical plausibility."})

    history = _all_recent(db, observation.station_id, limit=12)
    if history:
        prev = history[-1]
        if abs(observation.temperature - prev.temperature) > 12:
            issues.append({"status": "Warning", "parameter": "temperature", "type": " sudden_change", "reason": f"Temperature jump of {abs(observation.temperature - prev.temperature):.1f}°C from recent history."})
        if abs(observation.pressure - prev.pressure) > 12:
            issues.append({"status": "Warning", "parameter": "pressure", "type": "sudden_change", "reason": f"Pressure jump of {abs(observation.pressure - prev.pressure):.1f} hPa from recent history."})

    if history and len(history) >= 10:
        temps = [item.temperature for item in history]
        if abs(observation.temperature - sum(temps) / len(temps)) > 2 * pstdev(temps):
            issues.append({"status": "Warning", "parameter": "temperature", "type": "historical_variance", "reason": "Current temperature deviates significantly from rolling historical baseline."})

    if history and len(history) >= 20:
        repeated = len([item for item in history if abs(item.temperature - history[-1].temperature) < 0.05])
        if repeated >= 18:
            issues.append({"status": "Anomaly", "parameter": "temperature", "type": "frozen_value", "reason": "Temperature remains effectively unchanged over an unusually long period."})

    if observation.temperature > 60:
        issues.append({"status": "Warning", "parameter": "temperature", "type": "multivariate", "reason": "Very high temperature requires cross-check against humidity and nearby station evidence."})

    status = "Normal" if not issues else max((item["status"] for item in issues), key=lambda s: ["Normal", "Warning", "Anomaly"].index(s))
    return status, issues


def spatial_consensus(db: Session, observation: RawObservation, radius_km: float = 150.0):
    stations = db.query(Station).all()
    neighbors = []
    for station in stations:
        if station.station_id == observation.station_id:
            continue
        if _distance_km(observation.latitude, observation.longitude, station.latitude, station.longitude) <= radius_km:
            latest = _latest_for_station(db, station.station_id)
            if latest:
                neighbors.append(latest.temperature)
    if not neighbors:
        return {"status": "Warning", "reason": "Insufficient nearby station data for spatial comparison.", "median": observation.temperature, "distance": 0}
    median_temp = float(median(neighbors))
    deviation = abs(observation.temperature - median_temp)
    if deviation > 8:
        return {"status": "Anomaly", "reason": "Current station deviates strongly from nearby stations.", "median": median_temp, "distance": deviation}
    return {"status": "Normal", "reason": "Nearby stations remain consistent with current observation.", "median": median_temp, "distance": deviation}


def multivariate_consistency(observation: RawObservation) -> dict:
    if observation.temperature > 45 and observation.humidity > 80:
        return {"status": "Warning", "reason": "High temperature and high humidity combination is unusual and should be reviewed."}
    if observation.temperature < 5 and observation.pressure > 1030:
        return {"status": "Warning", "reason": "Cold, high-pressure combination is unusual and should be reviewed."}
    return {"status": "Normal", "reason": "Multi-parameter relationship falls within expected local range."}


def ml_anomaly_score(db: Session, observation: RawObservation) -> dict:
    station_rows = db.query(RawObservation).filter(RawObservation.station_id == observation.station_id).order_by(RawObservation.timestamp.desc()).limit(120).all()
    if len(station_rows) < 12:
        return {"status": "Warning", "score": 0.25, "reason": "Insufficient training history for model-based anomaly inference."}

    if np is None or IsolationForest is None:
        temperatures = [row.temperature for row in station_rows]
        center = median(temperatures)
        mad = median([abs(value - center) for value in temperatures])
        scale = 1.4826 * mad or max(pstdev(temperatures), 1.0)
        deviation = abs(observation.temperature - center) / scale
        status = "Anomaly" if deviation >= 3.5 else "Warning" if deviation >= 2.5 else "Normal"
        return {
            "status": status,
            "score": round(deviation, 2),
            "reason": "Robust rolling-statistics fallback used because the Isolation Forest runtime is unavailable.",
        }

    features = []
    for row in station_rows:
        features.append([row.temperature, row.pressure, row.humidity, row.temperature - row.pressure * 0.01])
    data = np.array(features)
    model = IsolationForest(contamination=0.08, random_state=42)
    model.fit(data)
    sample = np.array([[observation.temperature, observation.pressure, observation.humidity, observation.temperature - observation.pressure * 0.01]])
    pred = model.predict(sample)[0]
    decision = model.decision_function(sample)[0]
    if pred == -1:
        return {"status": "Anomaly", "score": max(0.0, round(float(-decision), 2)), "reason": "Isolation forest flags the reading as anomalous relative to historical behavior."}
    return {"status": "Normal", "score": max(0.0, round(float(-decision), 2)), "reason": "ML model did not find strong anomaly evidence in the recent pattern."}


def compute_trust_score(validation_status: str, issues: list[dict], spatial: dict, multivariate: dict, ml: dict) -> float:
    penalty = 0
    if validation_status == "Anomaly":
        penalty += 30
    elif validation_status == "Warning":
        penalty += 15
    penalty += sum(8 for issue in issues if issue["status"] == "Warning")
    penalty += sum(15 for issue in issues if issue["status"] == "Anomaly")
    if spatial.get("status") == "Anomaly":
        penalty += 20
    elif spatial.get("status") == "Warning":
        penalty += 10
    if multivariate.get("status") == "Warning":
        penalty += 8
    if ml.get("status") == "Anomaly":
        penalty += 18
    return max(0.0, min(100.0, 100.0 - penalty))


def compute_sensor_health(db: Session, station_id: str) -> float:
    rows = db.query(RawObservation).filter(RawObservation.station_id == station_id).order_by(RawObservation.timestamp.desc()).limit(50).all()
    if not rows:
        return 50.0
    anomalies = db.query(AnalysisResult).filter(AnalysisResult.station_id == station_id).count()
    recent = rows[:20]
    freeze_count = sum(1 for row in recent if row.validation_status == "Anomaly")
    score = 100.0
    score -= anomalies * 1.5
    score -= freeze_count * 5
    score = max(0.0, min(100.0, score))
    return round(score, 2)


def _persist_analysis(db: Session, observation: RawObservation, result: dict, trust_score: float, sensor_health: float):
    entry = AnalysisResult(
        station_id=observation.station_id,
        observation_id=observation.id,
        parameter="temperature",
        anomaly_type=result["anomaly_type"],
        severity=result["severity"],
        trust_score=trust_score,
        sensor_health=sensor_health,
        status=result["status"],
        explanation=result["explanation"],
        evidence=json.dumps(result["evidence"]),
        created_at=datetime.utcnow(),
    )
    db.add(entry)
    db.commit()


def analyze_station(db: Session, station_id: str):
    observation = _latest_for_station(db, station_id)
    if observation is None:
        return {"status": "Offline", "trust_score": 0, "sensor_health": 0, "anomaly_type": "missing_data", "severity": "High", "explanation": "No recent observation is available."}

    validation_status, issues = validate_observation(db, observation)
    spatial = spatial_consensus(db, observation)
    multivariate = multivariate_consistency(observation)
    ml = ml_anomaly_score(db, observation)
    trust_score = compute_trust_score(validation_status, issues, spatial, multivariate, ml)
    sensor_health = compute_sensor_health(db, station_id)

    anomaly_type = "normal"
    severity = "Low"
    status = "Healthy"
    if spatial["status"] == "Anomaly" or ml["status"] == "Anomaly" or validation_status == "Anomaly":
        anomaly_type = "possible_isolated_sensor_anomaly"
        severity = "Critical" if trust_score < 30 else "High"
        status = "Anomaly"
    elif validation_status == "Warning" or spatial["status"] == "Warning":
        anomaly_type = "needs_review"
        severity = "Medium"
        status = "Warning"
    elif spatial["status"] == "Normal" and ml["status"] == "Normal":
        anomaly_type = "normal_weather"
        severity = "Low"
        status = "Healthy"

    evidence = [
        {"name": "Validation", "result": validation_status, "reason": issues[0]["reason"] if issues else "No validation issues detected.", "confidence": 0.75},
        {"name": "Spatial", "result": spatial["status"], "reason": spatial["reason"], "confidence": 0.7},
        {"name": "Multivariate", "result": multivariate["status"], "reason": multivariate["reason"], "confidence": 0.6},
        {"name": "ML Model", "result": ml["status"], "reason": ml["reason"], "confidence": 0.65},
    ]

    explanation = (
        f"Station {station_id} reported {observation.temperature:.1f}°C. "
        f"Nearby stations are around {spatial['median']:.1f}°C and the model/evidence suggests {ml['status'].lower()}. "
        f"Trust score is {trust_score:.1f} after combining validation, temporal, spatial, and ML evidence."
    )

    if anomaly_type == "normal_weather":
        explanation = f"Station {station_id} remains within expected historical and nearby-station ranges. No major anomaly evidence was found."

    result = {
        "station_id": station_id,
        "status": status,
        "trust_score": round(trust_score, 2),
        "sensor_health": round(sensor_health, 2),
        "anomaly_type": anomaly_type,
        "severity": severity,
        "explanation": explanation,
        "evidence": evidence,
    }
    observation.validation_status = validation_status
    observation.anomaly_status = status
    observation.trust_score = trust_score
    observation.sensor_health = sensor_health
    db.add(observation)
    _persist_analysis(db, observation, result, trust_score, sensor_health)

    if status in {"Warning", "Anomaly"}:
        alert_id = f"ALERT-{station_id}-{observation.id}"
        existing = db.query(Alert).filter(Alert.alert_id == alert_id).first()
        if not existing:
            db.add(
                Alert(
                    alert_id=alert_id,
                    station_id=station_id,
                    timestamp=datetime.utcnow(),
                    parameter="temperature",
                    observed_value=float(observation.temperature),
                    nearby_average=float(spatial.get("median", observation.temperature)),
                    anomaly_type=anomaly_type,
                    severity=severity,
                    trust_score=trust_score,
                    sensor_health=sensor_health,
                    explanation=explanation,
                    recommended_action="Inspect the sensor and verify remote data consistency before reusing the observation.",
                    status="Active",
                    acknowledged=False,
                )
            )
    db.commit()
    return result


def analyze_all_stations() -> list[dict]:
    db = SessionLocal()
    try:
        stations = db.query(Station).all()
        results = []
        for station in stations:
            results.append(analyze_station(db, station.station_id))
        return results
    finally:
        db.close()


def build_dashboard_summary() -> dict:
    db = SessionLocal()
    try:
        stations = db.query(Station).all()
        total = len(stations)
        healthy = 0
        warning = 0
        anomalous = 0
        trust_scores = []
        health_scores = []
        for station in stations:
            latest = _latest_for_station(db, station.station_id)
            if latest:
                trust_scores.append(float(latest.trust_score))
                health_scores.append(float(latest.sensor_health))
                if latest.anomaly_status == "Healthy":
                    healthy += 1
                elif latest.anomaly_status == "Warning":
                    warning += 1
                elif latest.anomaly_status == "Anomaly":
                    anomalous += 1
        critical = db.query(Alert).filter(Alert.severity == "Critical", Alert.status == "Active").count()
        return {
            "total_stations": total,
            "healthy_stations": healthy,
            "warning_stations": warning,
            "anomalous_stations": anomalous,
            "critical_alerts": critical,
            "avg_trust_score": round(sum(trust_scores) / len(trust_scores) if trust_scores else 0.0, 2),
            "avg_sensor_health": round(sum(health_scores) / len(health_scores) if health_scores else 0.0, 2),
            "system_status": "Healthy" if critical == 0 else "Monitoring",
        }
    finally:
        db.close()


def save_health_snapshot(station_id: str, score: float, reasons: str):
    db = SessionLocal()
    try:
        db.add(SensorHealthHistory(station_id=station_id, timestamp=datetime.utcnow(), health_score=score, reasons=reasons))
        db.commit()
    finally:
        db.close()


def recalculate_station_health(station_id: str):
    db = SessionLocal()
    try:
        score = compute_sensor_health(db, station_id)
        save_health_snapshot(station_id, score, "Updated from recent validation and anomaly history.")
        return score
    finally:
        db.close()
