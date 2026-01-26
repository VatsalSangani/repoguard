import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from state import AgentState

def aggregator_node(state: AgentState):
    print("\n--- 📝 Step 3: Aggregator Agent ---")
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    results = state["raw_scan_results"]
    results_text = json.dumps(results, indent=2)
    
    # Truncate to prevent token overflow
    if len(results_text) > 20000:
        results_text = results_text[:20000] + "\n...[TRUNCATED]"

    prompt = (
        "You are the RepoGuard Security Analyst. "
        "Review the logs and write a high-quality Markdown report."
        "\n- Highlight CRITICAL issues (Secrets, Bugs)."
        "\n- Suggest Actionable Fixes."
    )
    
    response = llm.invoke([
        SystemMessage(content=prompt),
        HumanMessage(content=f"LOGS:\n{results_text}")
    ])
    
    return {"final_report": response.content}