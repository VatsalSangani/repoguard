import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from config import DEFAULT_MODEL, LLM_TEMPERATURE, MAX_REPORT_INPUT_CHARS
from state import AgentState

_SYSTEM_PROMPT = (
    "You are the RepoGuard Security Analyst. "
    "Review the logs and write a high-quality Markdown report."
    "\n- Highlight CRITICAL issues (Secrets, Bugs)."
    "\n- Suggest Actionable Fixes."
)


def aggregator_node(state: AgentState) -> dict:
    print("\n--- 📝 Step 3: Aggregator Agent ---")
    llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=LLM_TEMPERATURE)

    results_text = json.dumps(state["raw_scan_results"], indent=2)
    if len(results_text) > MAX_REPORT_INPUT_CHARS:
        results_text = results_text[:MAX_REPORT_INPUT_CHARS] + "\n...[TRUNCATED]"

    response = llm.invoke([
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=f"LOGS:\n{results_text}"),
    ])

    return {"final_report": response.content}
