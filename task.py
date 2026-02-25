from crewai import Task
from agents import financial_analyst, verifier, investment_advisor, risk_assessor
from tools import read_data_tool, analyze_investment_tool, create_risk_assessment_tool


analyze_financial_document_task = Task(
    description=(
        "Read the financial document at {file_path} and analyze it to answer: {query}\n\n"
        "Use the 'Read Financial Document' tool with file_path='{file_path}' to load the doc.\n"
        "Pull out the important numbers — revenue, net income, margins, EPS, cash flow — "
        "and look for trends vs prior periods if that data is available. "
        "Call out anything that stands out (good or bad) and tie your findings back to what the user asked."
    ),
    expected_output=(
        "Financial analysis covering key metrics, period-over-period changes, "
        "strengths/weaknesses in the data, and a direct answer to the user's question. "
        "Include a disclaimer that this is informational only."
    ),
    agent=financial_analyst,
    tools=[read_data_tool],
    async_execution=False,
)

investment_analysis = Task(
    description=(
        "Take the financial analysis results and build investment recommendations for: {query}\n"
        "Document path: {file_path}\n\n"
        "Look at valuation vs peers, growth trajectory, and margin trends. "
        "Give concrete recommendations (buy/hold/sell or equivalent) and back them up with numbers. "
        "Don't forget to mention risks and suggest how to diversify."
    ),
    expected_output=(
        "Investment recommendation with:\n"
        "- Thesis + supporting data\n"
        "- Valuation context (P/E, EV/EBITDA, etc.)\n"
        "- Actionable suggestion with reasoning\n"
        "- Key risk factors\n"
        "- Not-personalized-advice disclaimer"
    ),
    agent=investment_advisor,
    tools=[analyze_investment_tool],
    async_execution=False,
)

risk_assessment = Task(
    description=(
        "Run a risk assessment on the financial data for: {query}\n"
        "Source document: {file_path}\n\n"
        "Cover the main risk buckets — credit, liquidity, market, operational. "
        "Factor in macro conditions and anything sector-specific. "
        "Assign an overall risk rating (Low/Medium/High) and explain why. "
        "Suggest mitigation strategies where relevant."
    ),
    expected_output=(
        "Risk report with identified risks, severity ratings backed by data, "
        "stress test considerations, mitigation ideas, and an overall risk profile. "
        "Note limitations of the assessment."
    ),
    agent=risk_assessor,
    tools=[create_risk_assessment_tool],
    async_execution=False,
)

verification = Task(
    description=(
        "Check whether the uploaded document at {file_path} is actually a financial document.\n"
        "Use the 'Read Financial Document' tool with file_path='{file_path}' to read it, "
        "then look for standard financial content (income statements, balance sheets, etc.). "
        "Flag anything weird — missing sections, garbled data, non-financial content."
    ),
    expected_output=(
        "Verification result: what type of document it is, whether it contains real financial data, "
        "any quality issues found, and a final VERIFIED / NOT VERIFIED verdict."
    ),
    agent=verifier,
    tools=[read_data_tool],
    async_execution=False,
)