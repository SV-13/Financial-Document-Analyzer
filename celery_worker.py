import os
from dotenv import load_dotenv
load_dotenv()

from celery import Celery
from datetime import datetime, timezone

from database import get_db_session, TaskStatus

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery("financial_analyzer", broker=REDIS_URL, backend=REDIS_URL)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,  # crewai is heavy, one at a time
)


@celery_app.task(bind=True, name="analyze_document_task", max_retries=2)
def analyze_document_task(self, task_id: str, query: str, file_path: str):
    """Runs the CrewAI pipeline and writes results to the DB."""
    db = get_db_session()

    try:
        AnalysisTask = _get_model()
        task_record = db.query(AnalysisTask).filter_by(task_id=task_id).first()
        if not task_record:
            raise RuntimeError(f"Task {task_id} not found in database")

        task_record.status = TaskStatus.PROCESSING
        task_record.updated_at = datetime.now(timezone.utc)
        db.commit()

        # lazy imports so the worker doesn't load everything at startup
        from crewai import Crew, Process
        from agents import financial_analyst, verifier, investment_advisor, risk_assessor
        from task import (
            analyze_financial_document_task as analysis_task,
            verification,
            investment_analysis,
            risk_assessment,
        )

        financial_crew = Crew(
            agents=[verifier, financial_analyst, investment_advisor, risk_assessor],
            tasks=[verification, analysis_task, investment_analysis, risk_assessment],
            process=Process.sequential,
        )

        result = financial_crew.kickoff({"query": query, "file_path": file_path})

        task_record.status = TaskStatus.COMPLETED
        task_record.result = str(result)
        task_record.updated_at = datetime.now(timezone.utc)
        db.commit()

        return {"task_id": task_id, "status": "completed"}

    except Exception as exc:
        if task_record:
            task_record.status = TaskStatus.FAILED
            task_record.error = str(exc)
            task_record.updated_at = datetime.now(timezone.utc)
            db.commit()

        raise self.retry(exc=exc, countdown=30)

    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
        db.close()


def _get_model():
    from database import AnalysisTask
    return AnalysisTask
