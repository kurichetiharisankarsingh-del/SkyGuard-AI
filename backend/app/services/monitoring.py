from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import RawObservation, Station
from app.services.analysis import analyze_station
from app.services.weather_provider import ProviderObservation, fetch_current_weather


logger = logging.getLogger(__name__)
POLL_INTERVAL_SECONDS = max(300, int(os.getenv("SKYGUARD_POLL_INTERVAL_SECONDS", "900")))


def persist_provider_observations(db: Session, observations: Sequence[ProviderObservation]) -> int:
    inserted = 0
    for reading in observations:
        source_timestamp = reading.observed_at.astimezone(timezone.utc).replace(tzinfo=None)
        duplicate = db.query(RawObservation.id).filter(
            RawObservation.station_id == reading.station_id,
            RawObservation.source == "open-meteo",
            RawObservation.source_timestamp == source_timestamp,
        ).first()
        if duplicate:
            continue

        station = db.query(Station).filter(Station.station_id == reading.station_id).first()
        if station is None:
            logger.warning("Skipping provider reading for unknown station %s", reading.station_id)
            continue

        received_at = datetime.utcnow()
        observation = RawObservation(
            station_id=station.station_id,
            timestamp=received_at,
            source="open-meteo",
            source_timestamp=source_timestamp,
            temperature=reading.temperature,
            pressure=reading.pressure,
            humidity=reading.humidity,
            latitude=station.latitude,
            longitude=station.longitude,
            validation_status="Normal",
            anomaly_status="Normal",
            trust_score=100.0,
            sensor_health=100.0,
        )
        db.add(observation)
        db.flush()
        result = analyze_station(db, station.station_id)
        station.status = result["status"]
        station.last_update = received_at
        inserted += 1

    return inserted


class LiveWeatherMonitor:
    def __init__(self, poll_interval_seconds: int = POLL_INTERVAL_SECONDS):
        self.poll_interval_seconds = poll_interval_seconds
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._status = {
            "active": False,
            "state": "stopped",
            "source": "Open-Meteo",
            "interval_seconds": poll_interval_seconds,
            "last_success_at": None,
            "last_error": None,
            "last_inserted_count": 0,
        }

    async def start(self) -> None:
        async with self._lock:
            if self._task and not self._task.done():
                return
            self._status.update(active=True, state="running", last_error=None)
            self._task = asyncio.create_task(self._run(), name="skyguard-open-meteo-poller")

    async def pause(self) -> None:
        await self._stop("paused")

    async def stop(self) -> None:
        await self._stop("stopped")

    async def _stop(self, state: str) -> None:
        async with self._lock:
            task = self._task
            self._task = None
            self._status.update(active=False, state=state)
            if task and not task.done():
                task.cancel()
        if task and not task.done():
            try:
                await task
            except asyncio.CancelledError:
                pass

    def status(self) -> dict:
        return dict(self._status)

    async def poll_once(self) -> int:
        db = None
        try:
            db = SessionLocal()
            stations = db.query(Station).all()
            readings = await fetch_current_weather(stations)
            inserted = persist_provider_observations(db, readings)
            db.commit()
            self._status.update(
                last_success_at=datetime.now(timezone.utc).isoformat(),
                last_error=None,
                last_inserted_count=inserted,
            )
            return inserted
        except Exception as error:
            if db is not None:
                db.rollback()
            self._status["last_error"] = str(error)
            logger.exception("Live weather polling failed")
            return 0
        finally:
            if db is not None:
                db.close()

    async def poll_on_demand(self) -> int:
        inserted = await self.poll_once()
        self._status.update(active=False, state="on-demand")
        return inserted

    async def _run(self) -> None:
        try:
            while self._status["active"]:
                await self.poll_once()
                await asyncio.sleep(self.poll_interval_seconds)
        except asyncio.CancelledError:
            raise
        finally:
            self._status["active"] = False


live_weather_monitor = LiveWeatherMonitor()