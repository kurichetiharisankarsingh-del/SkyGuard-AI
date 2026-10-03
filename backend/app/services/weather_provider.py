from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence

import httpx


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


@dataclass(frozen=True)
class ProviderObservation:
    station_id: str
    observed_at: datetime
    temperature: float
    pressure: float
    humidity: float


def parse_current_weather(payload: Any, stations: Sequence[Any]) -> list[ProviderObservation]:
    responses = payload if isinstance(payload, list) else [payload]
    if len(responses) != len(stations):
        raise ValueError("Weather provider response count did not match requested stations.")

    observations = []
    for station, response in zip(stations, responses):
        current = response.get("current") if isinstance(response, dict) else None
        if not isinstance(current, dict):
            raise ValueError(f"Weather provider returned no current conditions for {station.station_id}.")

        timestamp_value = current.get("time")
        if not isinstance(timestamp_value, str):
            raise ValueError(f"Weather provider returned no observation time for {station.station_id}.")
        observed_at = datetime.fromisoformat(timestamp_value.replace("Z", "+00:00"))
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        else:
            observed_at = observed_at.astimezone(timezone.utc)

        try:
            temperature = float(current["temperature_2m"])
            pressure = float(current["surface_pressure"])
            humidity = float(current["relative_humidity_2m"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"Weather provider returned incomplete current conditions for {station.station_id}.") from error

        observations.append(ProviderObservation(
            station_id=station.station_id,
            observed_at=observed_at,
            temperature=temperature,
            pressure=pressure,
            humidity=humidity,
        ))

    return observations


async def fetch_current_weather(stations: Sequence[Any]) -> list[ProviderObservation]:
    if not stations:
        return []

    params = {
        "latitude": ",".join(str(station.latitude) for station in stations),
        "longitude": ",".join(str(station.longitude) for station in stations),
        "current": "temperature_2m,relative_humidity_2m,surface_pressure",
        "timezone": "UTC",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(OPEN_METEO_URL, params=params)
        response.raise_for_status()
        return parse_current_weather(response.json(), stations)