from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Station(Base):
    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    station_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="Healthy")
    last_update: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RawObservation(Base):
    __tablename__ = "raw_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    station_id: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    temperature: Mapped[float] = mapped_column(Float, nullable=False)
    pressure: Mapped[float] = mapped_column(Float, nullable=False)
    humidity: Mapped[float] = mapped_column(Float, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(30), default="Normal")
    anomaly_status: Mapped[str] = mapped_column(String(30), default="Normal")
    trust_score: Mapped[float] = mapped_column(Float, default=100)
    sensor_health: Mapped[float] = mapped_column(Float, default=100)
    source: Mapped[str] = mapped_column(String(30), default="simulation", nullable=False)
    source_timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    station_id: Mapped[str] = mapped_column(String(50), index=True)
    observation_id: Mapped[int] = mapped_column(Integer, index=True)
    parameter: Mapped[str] = mapped_column(String(50), default="temperature")
    anomaly_type: Mapped[str] = mapped_column(String(80), default="normal")
    severity: Mapped[str] = mapped_column(String(30), default="Low")
    trust_score: Mapped[float] = mapped_column(Float, default=100)
    sensor_health: Mapped[float] = mapped_column(Float, default=100)
    status: Mapped[str] = mapped_column(String(30), default="Normal")
    explanation: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    alert_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    station_id: Mapped[str] = mapped_column(String(50), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    parameter: Mapped[str] = mapped_column(String(50), default="temperature")
    observed_value: Mapped[float] = mapped_column(Float, default=0.0)
    nearby_average: Mapped[float] = mapped_column(Float, default=0.0)
    anomaly_type: Mapped[str] = mapped_column(String(80), default="normal")
    severity: Mapped[str] = mapped_column(String(30), default="Low")
    trust_score: Mapped[float] = mapped_column(Float, default=100)
    sensor_health: Mapped[float] = mapped_column(Float, default=100)
    explanation: Mapped[str] = mapped_column(Text, default="")
    recommended_action: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="Active")
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)


class SensorHealthHistory(Base):
    __tablename__ = "sensor_health_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    station_id: Mapped[str] = mapped_column(String(50), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    health_score: Mapped[float] = mapped_column(Float, default=100)
    reasons: Mapped[str] = mapped_column(Text, default="")


class ScenarioState(Base):
    __tablename__ = "scenario_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    current_scenario: Mapped[str] = mapped_column(String(50), default="normal")
    last_reset_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MonitoringState(Base):
    __tablename__ = "monitoring_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    last_update: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    interval_seconds: Mapped[int] = mapped_column(Integer, default=30)

