from __future__ import annotations

from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models import Alert, MonitoringState, RawObservation, ScenarioState, Station
from app.services.analysis import analyze_all_stations
from app.services.simulator import reset_scenario_state


SCENARIO_NAMES = [
    "normal",
    "faulty_sensor",
    "heatwave",
    "frozen_sensor",
    "missing_data",
    "gradual_sensor_degradation",
]


def run_scenario(name: str):
    db = SessionLocal()
    try:
        scenario = name.lower().replace(" ", "_")
        item = db.query(ScenarioState).first()
        if item is None:
            item = ScenarioState(current_scenario=scenario)
            db.add(item)
        else:
            item.current_scenario = scenario
        db.commit()

        if scenario == "normal":
            reset_scenario_state()
            analyze_all_stations()
            return {"scenario": scenario, "message": "System restored to normal weather baseline."}

        if scenario == "faulty_sensor":
            station = db.query(Station).filter(Station.station_id == "AWS-004").first()
            if station:
                latest = db.query(RawObservation).filter(RawObservation.station_id == "AWS-004").order_by(RawObservation.timestamp.desc()).first()
                if latest:
                    latest.temperature = 85.0
                    latest.pressure = 1010.0
                    latest.humidity = 18.0
                    latest.validation_status = "Anomaly"
                    latest.anomaly_status = "Anomaly"
                    latest.trust_score = 18.0
                    latest.sensor_health = 72.0
                    station.status = "Anomaly"
                    station.last_update = datetime.utcnow()
                    db.commit()
            analyze_all_stations()
            return {"scenario": scenario, "message": "Faulty sensor anomaly scenario applied to AWS-004."}

        if scenario == "heatwave":
            for station_id in ["AWS-001", "AWS-002", "AWS-003", "AWS-004", "AWS-005"]:
                station = db.query(Station).filter(Station.station_id == station_id).first()
                if station:
                    latest = db.query(RawObservation).filter(RawObservation.station_id == station_id).order_by(RawObservation.timestamp.desc()).first()
                    if latest:
                        latest.temperature = 42.5 + (ord(station_id[-1]) % 3) * 0.5
                        latest.pressure = 1006.0
                        latest.humidity = 35.0
                        latest.validation_status = "Warning"
                        latest.anomaly_status = "Warning"
                        latest.trust_score = 73.0
                        latest.sensor_health = 88.0
                        station.status = "Warning"
                        station.last_update = datetime.utcnow()
            db.commit()
            analyze_all_stations()
            return {"scenario": scenario, "message": "Regional heatwave scenario applied across nearby stations."}

        if scenario == "frozen_sensor":
            station = db.query(Station).filter(Station.station_id == "AWS-006").first()
            if station:
                history = db.query(RawObservation).filter(RawObservation.station_id == "AWS-006").order_by(RawObservation.timestamp.desc()).limit(12).all()
                for row in history:
                    row.temperature = 28.5
                    row.validation_status = "Anomaly"
                    row.anomaly_status = "Anomaly"
                    row.trust_score = 32.0
                station.status = "Anomaly"
                station.last_update = datetime.utcnow()
            db.commit()
            analyze_all_stations()
            return {"scenario": scenario, "message": "Frozen-temperature pattern applied to AWS-006."}

        if scenario == "missing_data":
            station = db.query(Station).filter(Station.station_id == "AWS-007").first()
            if station:
                station.status = "Offline"
                station.last_update = datetime.utcnow() - timedelta(hours=2)
            db.commit()
            analyze_all_stations()
            return {"scenario": scenario, "message": "Missing-data scenario applied to AWS-007."}

        if scenario == "gradual_sensor_degradation":
            station = db.query(Station).filter(Station.station_id == "AWS-010").first()
            if station:
                rows = db.query(RawObservation).filter(RawObservation.station_id == "AWS-010").order_by(RawObservation.timestamp.desc()).limit(20).all()
                for idx, row in enumerate(rows):
                    row.temperature = 28.0 + idx * 0.7
                    row.validation_status = "Warning" if idx > 5 else "Normal"
                    row.anomaly_status = "Warning" if idx > 5 else "Normal"
                    row.trust_score = max(45.0, 100.0 - idx * 4)
                station.status = "Warning"
                station.last_update = datetime.utcnow()
            db.commit()
            analyze_all_stations()
            return {"scenario": scenario, "message": "Gradual sensor degradation simulation applied to AWS-010."}

        return {"scenario": scenario, "message": "Scenario executed."}
    finally:
        db.close()


def reset_scenario():
    reset_scenario_state()
    analyze_all_stations()
    return {"status": "ok", "message": "Scenario state reset and baseline weather restored."}
