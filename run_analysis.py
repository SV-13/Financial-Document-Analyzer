"""
Direct financial document analysis using Ollama (llama3).
Bypasses CrewAI's tool-calling mechanism which struggles with smaller models.
Reads the PDF once, then sends it through each analysis stage sequentially.
"""
import os, sys, json, requests
from dotenv import load_dotenv
load_dotenv()

from langchain_community.document_loaders import PyPDFLoader

# ── Config ──────────────────────────────────────────────────────────
OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
MODEL = os.getenv("OLLAMA_MODEL", "llama3")
PDF_PATH = sys.argv[1] if len(sys.argv) > 1 else "data/sample.pdf"
QUERY = sys.argv[2] if len(sys.argv) > 2 else "Analyze this financial document for investment insights"

API_URL = f"{OLLAMA_BASE}/v1/chat/completions"
HEADERS = {"Content-Type": "application/json"}


def chat(system_prompt: str, user_prompt: str, max_tokens: int = 2048) -> str:
    """Send a chat completion request to Ollama's OpenAI-compatible API."""
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    resp = requests.post(API_URL, json=payload, headers=HEADERS, timeout=300)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def read_pdf(path: str) -> str:
    """Extract all text from a PDF."""
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        print(f"ERROR: File not found: {abs_path}")
        sys.exit(1)
    docs = PyPDFLoader(file_path=abs_path).load()
    text = "\n".join(d.page_content for d in docs)
    return text


# ── Main ────────────────────────────────────────────────────────────
def main():
    print(f"{'='*70}")
    print(f"  Financial Document Analyzer  (Ollama — {MODEL})")
    print(f"  PDF  : {PDF_PATH}")
    print(f"  Query: {QUERY}")
    print(f"  Server: {OLLAMA_BASE}")
    print(f"{'='*70}\n")

    # 1. Read the PDF
    print("[1/4] Reading PDF...")
    doc_text = read_pdf(PDF_PATH)
    # Truncate to ~6000 chars to keep within llama3 context window
    if len(doc_text) > 6000:
        doc_text_trimmed = doc_text[:6000] + "\n\n[... document truncated for context limits ...]"
    else:
        doc_text_trimmed = doc_text
    print(f"      Extracted {len(doc_text)} chars ({len(doc_text.splitlines())} lines)\n")

    # 2. Verification
    print("[2/4] Verifying document...")
    verification_result = chat(
        system_prompt=(
            "You are a compliance expert at a Big Four firm. Your job is to verify "
            "whether a document is a legitimate financial filing. Check for standard "
            "financial content (income statements, balance sheets, cash flows). "
            "Flag any quality issues. Give a VERIFIED or NOT VERIFIED verdict."
        ),
        user_prompt=f"Verify this document:\n\n{doc_text_trimmed}",
    )
    print(f"\n--- VERIFICATION ---\n{verification_result}\n")

    # 3. Financial Analysis
    print("[3/4] Analyzing financials...")
    analysis_result = chat(
        system_prompt=(
            "You are a Senior Equity Research Analyst with 15+ years of experience. "
            "Extract key financial metrics — revenue, net income, margins, EPS, cash flow — "
            "and look for trends. Call out strengths and weaknesses. "
            "Answer the user's specific question based on the data."
        ),
        user_prompt=f"User question: {QUERY}\n\nFinancial document:\n\n{doc_text_trimmed}",
    )
    print(f"\n--- FINANCIAL ANALYSIS ---\n{analysis_result}\n")

    # 4. Investment Recommendation
    print("[4/4] Building investment recommendation & risk assessment...")
    investment_result = chat(
        system_prompt=(
            "You are a CFP and Investment Advisor. Based on the financial analysis below, "
            "provide: (1) Buy/Hold/Sell recommendation with reasoning, "
            "(2) Key valuation metrics context, (3) Risk assessment covering credit, "
            "liquidity, market, and operational risks, (4) Risk rating (Low/Medium/High), "
            "(5) Mitigation strategies. Include a disclaimer that this is not personalized advice."
        ),
        user_prompt=(
            f"User question: {QUERY}\n\n"
            f"Financial analysis:\n{analysis_result}\n\n"
            f"Raw document excerpt:\n{doc_text_trimmed[:2000]}"
        ),
    )
    print(f"\n--- INVESTMENT RECOMMENDATION & RISK ---\n{investment_result}\n")

    # Summary
    print(f"{'='*70}")
    print("  Analysis complete!")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
