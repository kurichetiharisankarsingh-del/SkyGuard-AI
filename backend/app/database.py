import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

default_database_url = "sqlite:////tmp/skyguard.db" if os.getenv("VERCEL") and os.name != "nt" else "sqlite:///./skyguard.db"
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", default_database_url)
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif SQLALCHEMY_DATABASE_URL.startswith("postgresql://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

engine_options = {"connect_args": {"check_same_thread": False}} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db() -> None:
    # Import here to avoid circular import issues.
    from app.models import Alert, AnalysisResult, MonitoringState, RawObservation, ScenarioState, SensorHealthHistory, Station

    Base.metadata.create_all(bind=engine)
    columns = {column["name"] for column in inspect(engine).get_columns("raw_observations")}
    with engine.begin() as connection:
        if "source" not in columns:
            connection.execute(text("ALTER TABLE raw_observations ADD COLUMN source VARCHAR(30) NOT NULL DEFAULT 'simulation'"))
        if "source_timestamp" not in columns:
            connection.execute(text("ALTER TABLE raw_observations ADD COLUMN source_timestamp DATETIME"))
