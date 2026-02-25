import os
from dotenv import load_dotenv
load_dotenv()

from crewai.tools import tool
from langchain_community.document_loaders import PyPDFLoader

# not using SerperDevTool right now (would need SERPER_API_KEY)
search_tool = None


@tool("Read Financial Document")
def read_data_tool(file_path: str = "data/sample.pdf") -> str:
    """Reads a PDF and returns its full text content."""

    # catch cases where {file_path} didn't get interpolated by crewai
    if "{file_path}" in file_path:
        raise ValueError(f"file_path wasn't interpolated (got '{file_path}')")

    abs_path = os.path.abspath(file_path)

    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"No file at: {abs_path}")

    try:
        docs = PyPDFLoader(file_path=abs_path).load()
    except Exception as e:
        raise RuntimeError(f"Couldn't parse PDF at {abs_path}: {e}")

    if not docs:
        raise ValueError(f"PDF at {abs_path} has no pages")

    full_report = ""
    for data in docs:
        content = data.page_content
        # collapse double newlines
        while "\n\n" in content:
            content = content.replace("\n\n", "\n")
        full_report += content + "\n"

    return full_report


# keeping this for backward compat with older imports
class FinancialDocumentTool:
    read_data_tool = read_data_tool


@tool("Analyze Investment Data")
def analyze_investment_tool(financial_document_data: str) -> str:
    """Cleans up financial text data by stripping extra whitespace."""
    processed_data = financial_document_data

    i = 0
    while i < len(processed_data):
        if processed_data[i:i+2] == "  ":
            processed_data = processed_data[:i] + processed_data[i+1:]
        else:
            i += 1

    return processed_data


@tool("Create Risk Assessment")
def create_risk_assessment_tool(financial_document_data: str) -> str:
    """Takes financial doc text and returns a basic risk summary."""
    return f"Risk assessment for provided financial data:\n{financial_document_data[:500]}"