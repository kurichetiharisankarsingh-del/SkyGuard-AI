from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StationRead(BaseModel):
    station_id: str
    name: str
    latitude: float
    longitude: float
    status: str
    last_update: datetime
    current_temperature: Optional[float] = None
    current_pressure: Optional[float] = None
    current_humidity: Optional[float] = None
    trust_score: Optional[float] = None
    sensor_health: Optional[float] = None


class ObservationRead(BaseModel):
    id: int
    station_id: str
    timestamp: datetime
    temperature: float
    pressure: float
    humidity: float
    latitude: float
    longitude: float
    validation_status: str
    anomaly_status: str
    trust_score: float
    sensor_health: float


class AlertRead(BaseModel):
    alert_id: str
    station_id: str
    timestamp: datetime
    parameter: str
    observed_value: float
    nearby_average: Optional[float]
    anomaly_type: str
    severity: str
    trust_score: float
    sensor_health: float
    explanation: str
    recommended_action: str
    status: str


class ScenarioRunRequest(BaseModel):
    scenario_name: str


class MonitoringStatus(BaseModel):
    active: bool
    interval_seconds: int
    last_update: datetime


class DashboardSummary(BaseModel):
    total_stations: int
    healthy_stations: int
    warning_stations: int
    anomalous_stations: int
    critical_alerts: int
    avg_trust_score: float
    avg_sensor_health: float
    system_status: str


class AnalysisEvidence(BaseModel):
    name: str
    result: str
    reason: str
    confidence: float


class AnalysisResultRead(BaseModel):
    station_id: str
    status: str
    trust_score: float
    sensor_health: float
    anomaly_type: str
    severity: str
    explanation: str
    evidence: List[AnalysisEvidence]


class ApiResponse(BaseModel):
    success: bool
    data: Dict[str, Any]
    message: str
