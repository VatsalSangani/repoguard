import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from config import DEFAULT_MODEL, LLM_TEMPERATURE, MAX_REPORT_INPUT_CHARS
from observability.tracing import traced_node
from state import AgentState

_SYSTEM_PROMPT = (
    "You are the RepoGuard Security Analyst. "
    "Review the logs and write a high-quality Markdown report."
    "\n- Highlight CRITICAL issues (Secrets, Bugs)."
    "\n- Suggest Actionable Fixes."
)


@traced_node("aggregator")
def aggregator_node(state: AgentState) -> dict:
    print("\n--- 📝 Step 3: Aggregator Agent ---")
    llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=LLM_TEMPERATURE)

    # `raw_scan_results` (legacy processor path) and `tool_results` (Phase 1
    # router/sub-agent path) are mutually exclusive in practice — whichever
    # path the graph took populates one of them — but both are read here so
    # the aggregator works regardless of which path ran.
    tool_results = state.get("tool_results", {})
    raw_scan_results = state.get("raw_scan_results", [])
    combined = {"tool_results": tool_results, "raw_scan_results": raw_scan_results}

    results_text = json.dumps(combined, indent=2)
    if len(results_text) > MAX_REPORT_INPUT_CHARS:
        results_text = results_text[:MAX_REPORT_INPUT_CHARS] + "\n...[TRUNCATED]"

    response = llm.invoke([
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=f"LOGS:\n{results_text}"),
    ])

    aggregated_report = {
        "run_metadata": state.get("run_metadata"),
        "tool_results": tool_results,
        "finding_counts": {lang: len(findings) for lang, findings in tool_results.items()},
        "report_markdown": response.content,
    }

    return {"final_report": response.content, "aggregated_report": aggregated_report}
