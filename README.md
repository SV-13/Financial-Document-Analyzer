# Financial Document Analyzer

Analyzes financial PDFs (10-Ks, quarterly reports, investor updates) using a multi-agent pipeline built on CrewAI. Upload a document, ask a question, and get back a structured analysis with investment recommendations and risk assessment.

---

## Setup and Usage

> **Recommended: Python 3.11+** | Tested with Python 3.13.3  
> CrewAI, Celery, LangChain, and SQLAlchemy can have compatibility issues on newer Python releases. If you hit weird errors, try 3.11 or 3.12.

### 1. Create a virtual environment (recommended)
```sh
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
```

### 2. Install dependencies
```sh
pip install -r requirements.txt
```

### 3. Environment variables
Create a `.env` file in the project root:
```
OPENAI_API_KEY=your-openai-api-key-here
```
Make sure your OpenAI account has **active billing enabled** — a free-tier or expired key will hit quota errors immediately.

#### Using Ollama (free, local LLM — no API key needed)

Instead of OpenAI, you can use [Ollama](https://ollama.com) to run models locally (or on a LAN machine). Add these to your `.env`:
```
USE_OLLAMA=true
OLLAMA_MODEL=llama3
OLLAMA_BASE_URL=http://127.0.0.1:11434
```
> **Note:** The FastAPI multi-agent pipeline (`main.py`) works best with OpenAI. For Ollama, use the standalone script `run_analysis.py` (see below) — smaller models struggle with CrewAI's tool-calling format.

### 4. Add a financial document
Place a PDF at `data/sample.pdf`, or upload one through the API later.

For example, grab the Tesla Q2 2025 update:
1. Download from https://www.tesla.com/sites/default/files/downloads/TSLA-Q2-2025-Update.pdf
2. Save it as `data/sample.pdf`

### 5. Start the server
```sh
python main.py
```
Runs at `http://localhost:8000` (port 8000).

### 6. (Optional) Standalone analysis with Ollama

If you're using Ollama (local or on a LAN machine), `run_analysis.py` talks to the model directly without CrewAI's tool-calling overhead:

```sh
python run_analysis.py                                    # uses data/sample.pdf
python run_analysis.py data/report.pdf                    # custom PDF
python run_analysis.py data/report.pdf "What is the EPS?" # custom PDF + query
```

This script reads the PDF, then runs four analysis stages (verify → analyze → advise → risk) in sequence with a single LLM chat call each.

### 7. (Optional) Queue mode with Celery + Redis

Requires port **6379** (Redis) and **8000** (API server). Ensure these ports are available.
If Redis is running, jobs get dispatched to a background worker automatically. If not, the server just runs everything synchronously — no config changes needed.

```sh
# start redis
docker run -d -p 6379:6379 redis:latest

# start celery worker (separate terminal)
celery -A celery_worker.celery_app worker --loglevel=info --pool=solo

# start the api server
python main.py
```

---

## Architecture

Four agents run in sequence via CrewAI:

| Agent | What it does |
|-------|-------------|
| **Verifier** | Checks the uploaded file is a real financial document |
| **Financial Analyst** | Reads the PDF and extracts key metrics (revenue, margins, EPS, cash flow) |
| **Investment Advisor** | Builds investment recommendations from the analysis |
| **Risk Assessor** | Evaluates credit, market, and operational risk |

All results are persisted in a SQLite database (`financial_analyzer.db`, created automatically on first run).

---

## API Documentation

### Health Check
```
GET /
```
Returns server status and whether the Celery queue is active.

**Response:**
```json
{
  "message": "Financial Document Analyzer API is running",
  "queue_worker": "active"
}
```

### Analyze a Document
```
POST /analyze
```
Upload a PDF for analysis. Multipart form data.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | PDF file | Yes | The financial document to analyze |
| `query` | string | No | Analysis question (defaults to general investment insights) |

**Example:**
```sh
curl -X POST http://localhost:8000/analyze \
  -F "file=@data/sample.pdf" \
  -F "query=What are the key revenue trends?"
```

**Response (sync mode):**
```json
{
  "status": "success",
  "task_id": "abc-123-...",
  "query": "What are the key revenue trends?",
  "analysis": "...",
  "file_processed": "sample.pdf"
}
```

**Response (queue mode, when Redis is available):**
```json
{
  "status": "queued",
  "task_id": "abc-123-...",
  "message": "Analysis job queued. Poll GET /status/{task_id} for updates."
}
```

### Check Task Status
```
GET /status/{task_id}
```
Returns the current status of a task (`pending`, `processing`, `completed`, `failed`), plus the result or error when applicable.

### Get Full Result
```
GET /result/{task_id}
```
Returns the complete analysis output for a finished task.

### List All Tasks
```
GET /results?limit=20&status=completed
```
Lists analysis tasks, optionally filtered by status. Returns task_id, status, query, filename, and timestamp for each.

---

## Bugs Found and Fixed

### Deterministic Bugs (Code Errors)

| # | File | Bug | Fix Applied |
|---|------|-----|-------------|
| 1 | `tools.py` | `from crewai_tools import tools` — wrong import path | Changed to `from crewai.tools import tool` |
| 2 | `tools.py` | `SerperDevTool` import crashes (version mismatch + no API key) | Removed; set `search_tool = None` |
| 3 | `tools.py` | `Pdf(...)` — undefined class, doesn't exist | Replaced with `PyPDFLoader` from `langchain_community` |
| 4 | `tools.py` | Tool functions defined as `async def` | Removed `async` — CrewAI tools must be synchronous |
| 5 | `tools.py` | Tool functions missing `@tool` decorator | Added `@tool(...)` decorator to all three functions |
| 6 | `tools.py` | Methods inside a class but no `self` or `@staticmethod` | Pulled them out as standalone decorated functions |
| 7 | `agents.py` | `tool=[...]` (singular keyword) | Fixed to `tools=[...]` (plural) |
| 8 | `agents.py` | `max_iter=1` on all agents — agents can only do 1 step | Raised to `max_iter=25` |
| 9 | `agents.py` | `max_rpm=1` on all agents — severe rate limiting | Raised to `max_rpm=10` |
| 10 | `agents.py` | Some agents missing `memory=True` | Added `memory=True` to all agents |
| 11 | `task.py` | All 4 tasks assigned to `financial_analyst` | Fixed: each task now goes to the correct agent |
| 12 | `task.py` | Missing imports for `investment_advisor`, `risk_assessor` | Added the missing imports |
| 13 | `main.py` | Function `analyze_financial_document()` shadows the task import of the same name | Renamed endpoint function to `analyze_document()` |
| 14 | `main.py` | Crew only included 1 agent and 1 task | Added all 4 agents and all 4 tasks to the Crew |
| 15 | `main.py` | `import asyncio` at the top but never used | Removed the unused import |
| 16 | `main.py` | `file_path` never passed to `crew.kickoff()` | Now passed as `{'query': query, 'file_path': file_path}` |
| 17 | `main.py` | Relative file paths crash `PyPDFLoader` | Added `os.path.abspath()` conversion in the tool |
| 18 | `README.md` | `pip install -r requirement.txt` (missing 's') | Fixed to `requirements.txt` |
| 19 | `celery_worker.py` | Double DB query — fetched the task record twice | Refactored to fetch once and reuse throughout |

### Prompt / Agent Issues (Rewritten)

| # | File | Problem | What was changed |
|---|------|---------|-----------------|
| 1 | `agents.py` | All agent goals told the agent to fabricate data, ignore compliance, push scams | Rewrote all goals to be accurate, professional, and compliant |
| 2 | `agents.py` | All backstories described incompetent or malicious personas | Rewrote with realistic expertise and ethical guidelines |
| 3 | `task.py` | Task descriptions instructed agents to hallucinate data and invent URLs | Rewrote with clear, structured analysis instructions |
| 4 | `task.py` | Expected outputs encouraged contradictions and fake numbers | Rewrote with proper deliverable formats |

---

## Features

- PDF document upload and analysis
- Multi-agent pipeline: verify → analyze → advise → assess risk
- Key metric extraction (revenue, net income, margins, EPS, cash flow)
- Investment recommendations with risk considerations
- Async queue processing via Celery + Redis (with sync fallback)
- SQLite persistence for all tasks and results
- REST API with status polling and result retrieval

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | Required when using OpenAI. Your OpenAI API key |
| `USE_OLLAMA` | `false` | Set to `true` to use Ollama instead of OpenAI |
| `OLLAMA_MODEL` | `llama3` | Ollama model name (e.g. `llama3`, `mistral`) |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama server address |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection for Celery (optional) |
| `DATABASE_URL` | `sqlite:///financial_analyzer.db` | Database connection string |

---

## Sample Analysis Output

Analyzed **Tesla Q2 2025 Quarterly Update** (`data/sample.pdf`) using Ollama llama3:

### Verification
> **VERIFIED** — The document is confirmed as a legitimate Tesla quarterly financial filing with income statements, balance sheets, and operational summaries.

### Key Financial Metrics

| Metric | Value |
|--------|-------|
| Total Revenue | $22.5B (↓ 12% YoY) |
| Operating Income | $0.9B (↓ 42% YoY) |
| Operating Margin | 4.1% |
| GAAP Gross Margin | 17.2% |
| Adjusted EBITDA Margin | 15.1% |
| Operating Cash Flow | $2.5B |
| Free Cash Flow | $0.1B |
| Cash & Investments | $36.8B |
| GAAP EPS | $0.33 |
| Non-GAAP EPS | $0.40 |

### Financial Analysis Summary

- **Revenue** declined 12% YoY driven by lower vehicle deliveries, reduced regulatory credit revenue, and lower average selling prices
- **Operating income** down 42% YoY due to higher R&D spend (AI projects), declining deliveries, and increased stock-based compensation
- **Strengths**: Growth in Services & Other revenue, increasing Energy Generation & Storage gross profit, Robotaxi launch in Austin
- **Weaknesses**: Declining vehicle deliveries, lower regulatory credit revenue, compressed margins

### Investment Recommendation: HOLD

- Company is transitioning into AI, robotics, and autonomous services — long-term growth potential
- Near-term pressure from declining core auto metrics
- **Risk Rating: Medium** — strong liquidity ($36.8B cash) mitigates downside, but execution risk on new ventures is meaningful
- **Mitigation**: Monitor regulatory credit trends, track Robotaxi and Semi/Cybercab production milestones, diversify exposure
