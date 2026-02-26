import os
from dotenv import load_dotenv
load_dotenv()

from crewai import LLM, Agent
from tools import search_tool, FinancialDocumentTool, read_data_tool, analyze_investment_tool, create_risk_assessment_tool

## ── LLM configuration ──────────────────────────────────────────────
# Toggle between OpenAI and a local Ollama model.
# Set  USE_OLLAMA=true  in your .env (or environment) to use Ollama.
# You can also set  OLLAMA_MODEL  (default: llama3) and
# OLLAMA_BASE_URL  (default: http://127.0.0.1:11434).

_use_ollama = os.getenv("USE_OLLAMA", "false").lower() in ("true", "1", "yes")

if _use_ollama:
    _ollama_base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    llm = LLM(
        model=f"openai/{os.getenv('OLLAMA_MODEL', 'llama3')}",
        base_url=f"{_ollama_base}/v1",
        api_key="ollama",          # Ollama doesn't need a real key
        temperature=0.2,
    )
else:
    llm = LLM(
        model="openai/gpt-4o-mini",
        temperature=0.2,
        api_key=os.environ["OPENAI_API_KEY"],
    )


financial_analyst = Agent(
    role="Senior Financial Analyst",
    goal="Provide accurate, data-driven financial analysis based on the user's query: {query}",
    verbose=True,
    memory=True,
    backstory=(
        "Senior equity research analyst, 15+ years reading 10-Ks, 10-Qs, and earnings reports. "
        "Spent most of my career at a mid-cap fund doing bottom-up stock analysis. "
        "I pull numbers straight from the filings — revenue, margins, cash flow — and cross-check them "
        "before drawing any conclusions. If the data's not there, I say so."
    ),
    tools=[read_data_tool],
    llm=llm,
    max_iter=10,
    max_rpm=10,
    allow_delegation=False
)

verifier = Agent(
    role="Financial Document Verifier",
    goal="Verify uploaded documents are legitimate financial documents and flag quality issues.",
    verbose=True,
    memory=True,
    backstory=(
        "I've worked compliance at two Big Four firms. My job is simple: open the doc, "
        "figure out if it's actually a financial filing, and check whether anything looks off. "
        "Missing pages, garbled tables, weird formatting — I catch it. "
        "I don't sign off on anything I haven't read through."
    ),
    tools=[read_data_tool],
    llm=llm,
    max_iter=10,
    max_rpm=10,
    allow_delegation=False
)


investment_advisor = Agent(
    role="Investment Advisor",
    goal="Give solid investment recommendations grounded in the financial analysis and the user's risk profile.",
    verbose=True,
    memory=True,
    backstory=(
        "CFP, been doing portfolio management and advisory work for about 15 years. "
        "SEC/FINRA compliance is second nature at this point. I look at the numbers, think about "
        "where the client stands risk-wise, and put together recommendations that actually make sense "
        "for their situation. I always flag the downsides alongside the upside."
    ),
    tools=[analyze_investment_tool],
    llm=llm,
    max_iter=10,
    max_rpm=10,
    allow_delegation=False
)

risk_assessor = Agent(
    role="Risk Assessment Specialist",
    goal="Assess financial risks using real data and established risk frameworks.",
    verbose=True,
    memory=True,
    backstory=(
        "Risk management background — credit risk, market risk, the whole spectrum. "
        "I lean on VaR models, stress tests, and scenario analysis to figure out what could go wrong. "
        "Not trying to scare anyone, but I'm not going to sugarcoat it either. "
        "If the numbers say there's exposure, I'll spell it out."
    ),
    tools=[create_risk_assessment_tool],
    llm=llm,
    max_iter=10,
    max_rpm=10,
    allow_delegation=False
)
