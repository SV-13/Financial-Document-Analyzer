import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, String, Text, DateTime, Enum as SAEnum
from sqlalchemy.orm import declarative_base, sessionmaker
import enum

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///financial_analyzer.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisTask(Base):
    __tablename__ = "analysis_tasks"

    task_id = Column(String(36), primary_key=True, index=True)
    status = Column(SAEnum(TaskStatus), default=TaskStatus.PENDING, nullable=False)
    query = Column(Text, nullable=False)
    file_name = Column(String(255), nullable=True)
    file_path = Column(String(500), nullable=True)
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency — yields a session, closes when done."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session():
    """For use outside of FastAPI (Celery, scripts, etc.)."""
    return SessionLocal()
