from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Depends
from typing import Optional, List
import os
import uuid

from crewai import Crew, Process
from sqlalchemy.orm import Session

from agents import financial_analyst, verifier, investment_advisor, risk_assessor
from task import analyze_financial_document_task, verification, investment_analysis, risk_assessment
from database import get_db, get_db_session, AnalysisTask, TaskStatus

app = FastAPI(
    title="Financial Document Analyzer",
    description="AI-powered financial document analysis with queue-based processing",
    version="2.0.0",
)


def run_crew(query: str, file_path: str = "data/sample.pdf"):
    """Blocking crew run — fallback when Celery isn't around."""
    financial_crew = Crew(
        agents=[verifier, financial_analyst, investment_advisor, risk_assessor],
        tasks=[verification, analyze_financial_document_task, investment_analysis, risk_assessment],
        process=Process.sequential,
    )
    result = financial_crew.kickoff({'query': query, 'file_path': file_path})
    return result


def _celery_available() -> bool:
    """Quick Redis ping to see if we can dispatch to Celery."""
    try:
        from celery_worker import celery_app
        conn = celery_app.connection()
        conn.ensure_connection(max_retries=1, timeout=2)
        conn.close()
        return True
    except Exception:
        return False


@app.get("/")
async def root():
    celery_ok = _celery_available()
    return {
        "message": "Financial Document Analyzer API is running",
        "queue_worker": "active" if celery_ok else "unavailable (running in sync mode)",
    }


@app.post("/analyze")
async def analyze_document(
    file: UploadFile = File(...),
    query: str = Form(default="Analyze this financial document for investment insights"),
    db: Session = Depends(get_db),
):
    """Upload a PDF for analysis. Uses Celery if Redis is up, otherwise blocks."""
    task_id = str(uuid.uuid4())
    file_path = f"data/financial_document_{task_id}.pdf"

    try:
        os.makedirs("data", exist_ok=True)

        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        if not query or query.strip() == "":
            query = "Analyze this financial document for investment insights"
        query = query.strip()

        task_record = AnalysisTask(
            task_id=task_id,
            status=TaskStatus.PENDING,
            query=query,
            file_name=file.filename,
            file_path=file_path,
        )
        db.add(task_record)
        db.commit()

        if _celery_available():
            from celery_worker import analyze_document_task
            analyze_document_task.delay(task_id, query, file_path)

            return {
                "status": "queued",
                "task_id": task_id,
                "message": "Analysis job queued. Poll GET /status/{task_id} for updates.",
            }

        # no celery — just run it inline
        task_record.status = TaskStatus.PROCESSING
        db.commit()

        try:
            response = run_crew(query=query, file_path=file_path)
            task_record.status = TaskStatus.COMPLETED
            task_record.result = str(response)
            db.commit()

            return {
                "status": "success",
                "task_id": task_id,
                "query": query,
                "analysis": str(response),
                "file_processed": file.filename,
            }
        except Exception as e:
            task_record.status = TaskStatus.FAILED
            task_record.error = str(e)
            db.commit()
            raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")


@app.get("/status/{task_id}")
async def get_task_status(task_id: str, db: Session = Depends(get_db)):
    task_record = db.query(AnalysisTask).filter_by(task_id=task_id).first()
    if not task_record:
        raise HTTPException(status_code=404, detail="Task not found")

    response = {
        "task_id": task_record.task_id,
        "status": task_record.status.value,
        "query": task_record.query,
        "file_name": task_record.file_name,
        "created_at": str(task_record.created_at),
        "updated_at": str(task_record.updated_at),
    }

    if task_record.status == TaskStatus.COMPLETED:
        response["analysis"] = task_record.result
    elif task_record.status == TaskStatus.FAILED:
        response["error"] = task_record.error

    return response


@app.get("/results")
async def list_results(
    limit: int = 20,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List tasks. Optionally filter by status."""
    q = db.query(AnalysisTask).order_by(AnalysisTask.created_at.desc())

    if status:
        try:
            status_enum = TaskStatus(status)
            q = q.filter_by(status=status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Use: {', '.join(s.value for s in TaskStatus)}",
            )

    tasks = q.limit(limit).all()

    return [
        {
            "task_id": t.task_id,
            "status": t.status.value,
            "query": t.query,
            "file_name": t.file_name,
            "created_at": str(t.created_at),
        }
        for t in tasks
    ]


@app.get("/result/{task_id}")
async def get_result(task_id: str, db: Session = Depends(get_db)):
    """Fetch the full result for a given task."""
    task_record = db.query(AnalysisTask).filter_by(task_id=task_id).first()
    if not task_record:
        raise HTTPException(status_code=404, detail="Task not found")

    if task_record.status == TaskStatus.PENDING:
        return {"task_id": task_id, "status": "pending", "message": "Task is waiting in queue."}
    elif task_record.status == TaskStatus.PROCESSING:
        return {"task_id": task_id, "status": "processing", "message": "Task is being processed."}
    elif task_record.status == TaskStatus.FAILED:
        return {"task_id": task_id, "status": "failed", "error": task_record.error}

    return {
        "task_id": task_record.task_id,
        "status": "completed",
        "query": task_record.query,
        "file_name": task_record.file_name,
        "analysis": task_record.result,
        "created_at": str(task_record.created_at),
        "updated_at": str(task_record.updated_at),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)