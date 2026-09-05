from config import SENSITIVE_KEYWORDS
from observability.tracing import traced_node
from state import AgentState


@traced_node("guardrails")
def guardrail_node(state: AgentState) -> dict:
    print("\n--- 🛡️ Step 1.5: Guardrails ---")
    files = state.get("target_files", [])

    if not files:
        return {"error": "No files found", "guardrail_status": "fail"}

    sensitive_found = [f for f in files if any(k in f for k in SENSITIVE_KEYWORDS)]

    if sensitive_found:
        print(f"   ⚠️ RISK DETECTED: Found {len(sensitive_found)} sensitive files.")
        return {
            "guardrail_status": "pass",
            "risk_level": "high",
            "risk_reason": f"Sensitive files detected: {sensitive_found}",
        }

    return {
        "guardrail_status": "pass",
        "risk_level": "normal",
        "risk_reason": "Standard code scan",
    }


def guardrail_router(state: AgentState) -> str:
    if state.get("guardrail_status") == "fail":
        return "end_workflow"
    return "human_approval"
