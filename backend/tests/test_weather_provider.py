import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import RawObservation, Station
from app.services import analysis
from app.services import monitoring
from app.services.weather_provider import ProviderObservation
from app.services.monitoring import LiveWeatherMonitor
from app.services.weather_provider import fetch_current_weather, parse_current_weather


def stations():
    return [
        SimpleNamespace(station_id="AWS-001", latitude=28.6, longitude=77.2),
        SimpleNamespace(station_id="AWS-002", latitude=19.0, longitude=72.8),
    ]


def test_parse_current_weather_maps_each_location_and_normalizes_utc():
    payload = [
        {"current": {"time": "2026-10-03T09:00", "temperature_2m": 31.2, "surface_pressure": 1008.4, "relative_humidity_2m": 57}},
        {"current": {"time": "2026-10-03T09:00+05:30", "temperature_2m": 29.8, "surface_pressure": 1009.1, "relative_humidity_2m": 63}},
    ]

    observations = parse_current_weather(payload, stations())

    assert [item.station_id for item in observations] == ["AWS-001", "AWS-002"]
    assert observations[0].observed_at == datetime(2026, 10, 3, 9, 0, tzinfo=timezone.utc)
    assert observations[1].observed_at == datetime(2026, 10, 3, 3, 30, tzinfo=timezone.utc)
    assert observations[0].pressure == 1008.4


def test_parse_current_weather_rejects_mismatched_station_count():
    with pytest.raises(ValueError, match="count did not match"):
        parse_current_weather({"current": {}}, stations())


def test_fetch_current_weather_requests_current_conditions(monkeypatch):
    requested = {}

    async def mock_get(self, url, params=None):
        requested.update(params or {})
        return httpx.Response(200, json=[
            {"current": {"time": "2026-10-03T09:00", "temperature_2m": 31, "surface_pressure": 1008, "relative_humidity_2m": 57}},
            {"current": {"time": "2026-10-03T09:00", "temperature_2m": 30, "surface_pressure": 1009, "relative_humidity_2m": 63}},
        ], request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    observations = asyncio.run(fetch_current_weather(stations()))

    assert len(observations) == 2
    assert requested["current"] == "temperature_2m,relative_humidity_2m,surface_pressure"
    assert requested["timezone"] == "UTC"


def test_provider_observations_are_attributed_and_idempotent(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(Station(station_id="AWS-001", name="Test station", latitude=28.6, longitude=77.2))
    db.commit()
    monkeypatch.setattr(monitoring, "analyze_station", lambda session, station_id: {"status": "Healthy"})
    reading = ProviderObservation(
        station_id="AWS-001",
        observed_at=datetime(2026, 10, 3, 9, 0, tzinfo=timezone.utc),
        temperature=31.2,
        pressure=1008.4,
        humidity=57,
    )

    assert monitoring.persist_provider_observations(db, [reading]) == 1
    db.commit()
    assert monitoring.persist_provider_observations(db, [reading]) == 0
    rows = db.query(RawObservation).filter(RawObservation.source == "open-meteo").all()
    assert len(rows) == 1
    assert rows[0].source_timestamp == datetime(2026, 10, 3, 9, 0)
    assert rows[0].timestamp is not None
    db.close()
    engine.dispose()


def test_poll_once_records_success_and_insert_count(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    db = factory()
    db.add(Station(station_id="AWS-001", name="Test station", latitude=28.6, longitude=77.2))
    db.commit()
    db.close()
    monkeypatch.setattr(monitoring, "SessionLocal", factory)
    monkeypatch.setattr(monitoring, "analyze_station", lambda session, station_id: {"status": "Healthy"})

    async def fake_fetch(station_rows):
        assert [station.station_id for station in station_rows] == ["AWS-001"]
        return [ProviderObservation(
            station_id="AWS-001",
            observed_at=datetime(2026, 10, 3, 9, 0, tzinfo=timezone.utc),
            temperature=31,
            pressure=1008,
            humidity=57,
        )]

    monkeypatch.setattr(monitoring, "fetch_current_weather", fake_fetch)
    monitor = LiveWeatherMonitor()

    assert asyncio.run(monitor.poll_once()) == 1
    assert monitor.status()["last_success_at"] is not None
    assert monitor.status()["last_inserted_count"] == 1
    db = factory()
    assert db.query(RawObservation).filter_by(source="open-meteo").count() == 1
    db.close()
    engine.dispose()


def test_poll_once_exposes_provider_errors(monkeypatch):
    monkeypatch.setattr(monitoring, "SessionLocal", lambda: (_ for _ in ()).throw(RuntimeError("database unavailable")))
    monitor = LiveWeatherMonitor()

    assert asyncio.run(monitor.poll_once()) == 0
    assert "database unavailable" in monitor.status()["last_error"]


def test_monitor_pause_cancels_polling_task():
    monitor = LiveWeatherMonitor()

    async def exercise_lifecycle():
        await monitor.start()
        assert monitor.status()["active"] is True
        await monitor.pause()

    asyncio.run(exercise_lifecycle())
    assert monitor.status()["active"] is False
    assert monitor.status()["state"] == "paused"


def test_statistical_anomaly_fallback_without_ml_dependencies(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    for index in range(12):
        db.add(RawObservation(
            station_id="AWS-001",
            temperature=22 + index * 0.1,
            pressure=1010,
            humidity=55,
            latitude=28.6,
            longitude=77.2,
        ))
    db.commit()
    observation = RawObservation(
        station_id="AWS-001",
        temperature=48,
        pressure=1010,
        humidity=55,
        latitude=28.6,
        longitude=77.2,
    )
    monkeypatch.setattr(analysis, "np", None)
    monkeypatch.setattr(analysis, "IsolationForest", None)

    result = analysis.ml_anomaly_score(db, observation)

    assert result["status"] == "Anomaly"
    assert "fallback" in result["reason"]
    db.close()
    engine.dispose()