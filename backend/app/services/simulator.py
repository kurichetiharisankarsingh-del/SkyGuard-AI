from __future__ import annotations

import random
from datetime import datetime, timedelta
from math import sin, cos, pi

from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.models import Alert, MonitoringState, RawObservation, ScenarioState, SensorHealthHistory, Station

STATION_BASES = [
    {"station_id": "AWS-001", "name": "NW Hydrology Station", "latitude": 28.6139, "longitude": 77.2090, "base_temp": 31.5, "base_pressure": 1012.0, "base_humidity": 58},
    {"station_id": "AWS-002", "name": "Central Ridge Station", "latitude": 19.0760, "longitude": 72.8777, "base_temp": 30.4, "base_pressure": 1011.5, "base_humidity": 62},
    {"station_id": "AWS-003", "name": "Coastal Delta Station", "latitude": 13.0827, "longitude": 80.2707, "base_temp": 32.1, "base_pressure": 1009.8, "base_humidity": 70},
    {"station_id": "AWS-004", "name": "Hill Crest Station", "latitude": 12.9716, "longitude": 77.5946, "base_temp": 25.2, "base_pressure": 1016.3, "base_humidity": 52},
    {"station_id": "AWS-005", "name": "Desert Watch Station", "latitude": 23.0225, "longitude": 72.5714, "base_temp": 35.8, "base_pressure": 1008.6, "base_humidity": 34},
    {"station_id": "AWS-006", "name": "Western Plains Station", "latitude": 22.5726, "longitude": 88.3639, "base_temp": 29.9, "base_pressure": 1013.1, "base_humidity": 61},
    {"station_id": "AWS-007", "name": "Eastern Valley Station", "latitude": 17.3850, "longitude": 78.4867, "base_temp": 27.9, "base_pressure": 1014.0, "base_humidity": 66},
    {"station_id": "AWS-008", "name": "Mountain Pass Station", "latitude": 31.1048, "longitude": 77.1734, "base_temp": 22.7, "base_pressure": 1017.2, "base_humidity": 54},
    {"station_id": "AWS-009", "name": "South Basin Station", "latitude": 15.3173, "longitude": 75.7139, "base_temp": 33.0, "base_pressure": 1009.0, "base_humidity": 68},
    {"station_id": "AWS-010", "name": "Northern Plateau Station", "latitude": 26.9124, "longitude": 75.7873, "base_temp": 28.8, "base_pressure": 1012.7, "base_humidity": 55},
]


def generate_initial_seed_data() -> None:
    init_db()
    db = SessionLocal()
    try:
        existing = db.query(Station).count()
        if existing > 0:
            return

        random.seed(42)
        now = datetime.utcnow()

        for index, station_cfg in enumerate(STATION_BASES):
            station = Station(
                station_id=station_cfg["station_id"],
                name=station_cfg["name"],
                latitude=station_cfg["latitude"],
                longitude=station_cfg["longitude"],
                status="Healthy",
                last_update=now,
            )
            db.add(station)
            db.flush()

            for minute_index in range(288):
                timestamp = now - timedelta(minutes=(287 - minute_index) * 5)
                diurnal = sin((minute_index / 288) * 2 * pi + index)
                temp_noise = random.uniform(-1.2, 1.2)
                pressure_noise = random.uniform(-1.5, 1.5)
                humidity_noise = random.uniform(-5.0, 5.0)
                temperature = station_cfg["base_temp"] + diurnal * 4.0 + temp_noise
                pressure = station_cfg["base_pressure"] + sin(minute_index / 19.0) * 3.0 + pressure_noise
                humidity = max(15, min(95, station_cfg["base_humidity"] + cos(minute_index / 17.0) * 12.0 + humidity_noise))

                obs = RawObservation(
                    station_id=station.station_id,
                    timestamp=timestamp,
                    temperature=round(temperature, 2),
                    pressure=round(pressure, 2),
                    humidity=round(humidity, 2),
                    latitude=station_cfg["latitude"],
                    longitude=station_cfg["longitude"],
                    validation_status="Normal",
                    anomaly_status="Normal",
                    trust_score=100.0,
                    sensor_health=100.0,
                )
                db.add(obs)

        db.add(ScenarioState(current_scenario="normal"))
        db.add(MonitoringState(active=False, interval_seconds=30))
        db.commit()
    finally:
        db.close()


def reset_scenario_state() -> None:
    init_db()
    db = SessionLocal()
    try:
        db.query(Alert).delete()
        db.query(ScenarioState).delete()
        db.query(MonitoringState).delete()
        db.add(ScenarioState(current_scenario="normal"))
        db.add(MonitoringState(active=False, interval_seconds=30))
        db.commit()

        stations = db.query(Station).all()
        for station in stations:
            station.status = "Healthy"
            station.last_update = datetime.utcnow()
        db.query(RawObservation).delete()
        for station_cfg in STATION_BASES:
            station = db.query(Station).filter_by(station_id=station_cfg["station_id"]).first()
            if station is None:
                continue
            random.seed(42 + int(station_cfg["station_id"].split("-")[-1]))
            now = datetime.utcnow()
            for minute_index in range(288):
                timestamp = now - timedelta(minutes=(287 - minute_index) * 5)
                diurnal = sin((minute_index / 288) * 2 * pi + int(station_cfg["station_id"].split("-")[-1]))
                temperature = station_cfg["base_temp"] + diurnal * 4.0 + random.uniform(-1.2, 1.2)
                pressure = station_cfg["base_pressure"] + sin(minute_index / 19.0) * 3.0 + random.uniform(-1.5, 1.5)
                humidity = max(15, min(95, station_cfg["base_humidity"] + cos(minute_index / 17.0) * 12.0 + random.uniform(-5.0, 5.0)))
                db.add(RawObservation(
                    station_id=station.station_id,
                    timestamp=timestamp,
                    temperature=round(temperature, 2),
                    pressure=round(pressure, 2),
                    humidity=round(humidity, 2),
                    latitude=station_cfg["latitude"],
                    longitude=station_cfg["longitude"],
                    validation_status="Normal",
                    anomaly_status="Normal",
                    trust_score=100.0,
                    sensor_health=100.0,
                ))
        db.commit()
    finally:
        db.close()


def set_monitoring_state(active: bool, interval_seconds: int = 30) -> None:
    db = SessionLocal()
    try:
        state = db.query(MonitoringState).first()
        if state is None:
            state = MonitoringState(active=active, interval_seconds=interval_seconds)
            db.add(state)
        else:
            state.active = active
            state.interval_seconds = interval_seconds
            state.last_update = datetime.utcnow()
        db.commit()
    finally:
        db.close()


def get_monitoring_state() -> dict:
    db = SessionLocal()
    try:
        state = db.query(MonitoringState).first()
        if not state:
            return {"active": False, "interval_seconds": 30, "last_update": datetime.utcnow().isoformat()}
        return {
            "active": bool(state.active),
            "interval_seconds": state.interval_seconds,
            "last_update": state.last_update.isoformat(),
        }
    finally:
        db.close()


def update_monitoring_tick() -> None:
    db = SessionLocal()
    try:
        state = db.query(MonitoringState).first()
        if state and state.active:
            state.last_update = datetime.utcnow()
            db.commit()
    finally:
        db.close()


def get_scenario_state() -> str:
    db = SessionLocal()
    try:
        state = db.query(ScenarioState).first()
        if not state:
            return "normal"
        return state.current_scenario
    finally:
        db.close()


def set_scenario_state(name: str) -> None:
    db = SessionLocal()
    try:
        item = db.query(ScenarioState).first()
        if item is None:
            item = ScenarioState(current_scenario=name)
            db.add(item)
        else:
            item.current_scenario = name
            item.last_reset_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()


def get_station_definitions() -> list[dict]:
    return STATION_BASES
