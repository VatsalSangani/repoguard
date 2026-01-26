from langgraph.graph import END
from state import AgentState

def guardrail_node(state: AgentState):
    print("\n--- 🛡️ Step 1.5: Guardrails ---")
    files = state.get("target_files", [])
    
    # 1. Block Empty Scans
    if not files:
        return {"error": "No files found", "guardrail_status": "fail"}

    # 2. Check for Sensitive Files
    sensitive_keywords = [".env", "secrets", "credentials", "key.pem", "id_rsa"]
    sensitive_found = [f for f in files if any(k in f for k in sensitive_keywords)]
    
    if sensitive_found:
        print(f"   ⚠️ RISK DETECTED: Found {len(sensitive_found)} sensitive files.")
        return {
            "guardrail_status": "pass",
            "risk_level": "high",
            "risk_reason": f"Sensitive files detected: {sensitive_found}"
        }

    return {
        "guardrail_status": "pass",
        "risk_level": "normal",
        "risk_reason": "Standard code scan"
    }

def guardrail_router(state: AgentState):
    if state.get("guardrail_status") == "fail":
        return "end_workflow"
    return "human_approval"