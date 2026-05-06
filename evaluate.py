from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from config import (
    DEFAULT_MODEL,
    EVAL_EXPECTED_MIN_FILES,
    EVAL_JUDGE_PASS_SCORE,
    EVAL_TEST_REPO_PATH,
    LLM_TEMPERATURE,
)
from graph.builder import build_graph

load_dotenv()


def llm_judge_score(raw_logs: list, final_report: str) -> int:
    """Grade report accuracy (faithfulness) using an LLM judge. Returns 0-100."""
    print("\n⚖️  Running LLM-as-a-Judge (Faithfulness Check)...")
    evaluator = ChatOpenAI(model=DEFAULT_MODEL, temperature=LLM_TEMPERATURE)

    prompt = f"""
    You are a Senior Security Auditor.
    I will provide:
    1. RAW LOGS from security tools (JSON format).
    2. A FINAL REPORT written by an AI agent.

    Your Criteria:
    - [Recall] Does the report mention the CRITICAL secrets/issues found in the logs?
    - [Hallucination] Does the report invent issues that are NOT in the logs?

    Task:
    Return a score from 0 to 100.
    - 100 = Report perfectly summarizes the logs with no hallucinations.
    - 0 = Report completely missed the point.

    Return ONLY the integer score.

    --- RAW LOGS ---
    {str(raw_logs)[:5000]}

    --- FINAL REPORT ---
    {final_report}
    """

    try:
        return int(evaluator.invoke([HumanMessage(content=prompt)]).content)
    except Exception as e:
        print(f"   [Judge Error]: {e}")
        return 0


def run_comprehensive_eval() -> None:
    print(f"\n🧪 STARTING COMPREHENSIVE EVALUATION ON: {EVAL_TEST_REPO_PATH}")

    app = build_graph()
    config = {"configurable": {"thread_id": "eval_suite_v1"}}
    initial_state = {
        "user_input": EVAL_TEST_REPO_PATH,
        "target_files": [],
        "raw_scan_results": [],
        "risk_level": "normal",
    }

    print("   Running Phase 1 (Parser & Guardrails)...")
    for _ in app.stream(initial_state, config=config):
        pass

    state = app.get_state(config).values

    files_found = state.get("target_files", [])
    if len(files_found) >= EVAL_EXPECTED_MIN_FILES:
        print(f"   ✅ PASS: Parser found {len(files_found)} files (Min: {EVAL_EXPECTED_MIN_FILES}).")
    else:
        print(f"   ❌ FAIL: Parser only found {len(files_found)} files.")

    if state.get("risk_level") == "high":
        print("   ✅ PASS: Guardrails correctly flagged sensitive files.")
    else:
        print("   ⚠️ WARN: Guardrails did not flag any risks (Did you remove secrets.env?).")

    print("   Running Phase 2 (Execution Tools)...")
    result = app.invoke(None, config=config)

    raw_results = result["raw_scan_results"]
    failed_tools = [r for r in raw_results if "error" in str(r.get("details", {})).lower()]
    if len(failed_tools) == 0:
        print(f"   ✅ PASS: All {len(raw_results)} tools executed without crashing.")
    else:
        print(f"   ❌ FAIL: {len(failed_tools)} tools crashed.")

    score = llm_judge_score(raw_results, result["final_report"])
    print(f"   [Judge] Faithfulness Score: {score}/100")
    if score > EVAL_JUDGE_PASS_SCORE:
        print("   ✅ PASS: Report is accurate.")
    else:
        print("   ❌ FAIL: Report quality is low.")


if __name__ == "__main__":
    run_comprehensive_eval()
