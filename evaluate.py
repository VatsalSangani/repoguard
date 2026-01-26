import os
import sys
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

# Import your graph builder
from agents.main_agent import build_graph

load_dotenv()

# --- CONFIGURATION ---
TEST_REPO_PATH = "test_repov3_stress"  # Path to the test repository
# We expect at least these many files (adjust based on your actual repo)
EXPECTED_MIN_FILES = 3 

def llm_judge_score(raw_logs, final_report):
    """
    Uses GPT-4o-mini to grade the report's accuracy (Faithfulness).
    Cost: < $0.01 per run.
    """
    print("\n⚖️  Running LLM-as-a-Judge (Faithfulness Check)...")
    
    evaluator = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
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
        score = evaluator.invoke([HumanMessage(content=prompt)]).content
        return int(score)
    except Exception as e:
        print(f"   [Judge Error]: {e}")
        return 0

def run_comprehensive_eval():
    print(f"\n🧪 STARTING COMPREHENSIVE EVALUATION ON: {TEST_REPO_PATH}")
    
    # 1. SETUP
    app = build_graph()
    config = {"configurable": {"thread_id": "eval_suite_v1"}}
    
    # Mock State (Simulate User Input)
    initial_state = {
        "user_input": TEST_REPO_PATH, 
        "target_files": [], 
        "raw_scan_results": [],
        "risk_level": "normal"
    }

    # 2. RUN PHASE 1 (Planning)
    print("   Running Phase 1 (Parser & Guardrails)...")
    for event in app.stream(initial_state, config=config):
        pass
    
    snapshot = app.get_state(config)
    state = snapshot.values
    
    # --- CHECK 1: PARSER RECALL ---
    files_found = state.get("target_files", [])
    if len(files_found) >= EXPECTED_MIN_FILES:
        print(f"   ✅ PASS: Parser found {len(files_found)} files (Min: {EXPECTED_MIN_FILES}).")
    else:
        print(f"   ❌ FAIL: Parser only found {len(files_found)} files.")

    # --- CHECK 2: GUARDRAIL SAFETY ---
    # We expect 'risk_level' to be HIGH if secrets.env exists
    if state.get("risk_level") == "high":
        print("   ✅ PASS: Guardrails correctly flagged sensitive files.")
    else:
        print("   ⚠️ WARN: Guardrails did not flag any risks (Did you remove secrets.env?).")

    # 3. RUN PHASE 2 (Execution) - Force Resume ("Yes")
    print("   Running Phase 2 (Execution Tools)...")
    result = app.invoke(None, config=config)
    
    # --- CHECK 3: EXECUTION HEALTH ---
    raw_results = result["raw_scan_results"]
    failed_tools = [r for r in raw_results if "error" in str(r.get("details", {})).lower()]
    
    if len(failed_tools) == 0:
        print(f"   ✅ PASS: All {len(raw_results)} tools executed without crashing.")
    else:
        print(f"   ❌ FAIL: {len(failed_tools)} tools crashed.")

    # --- CHECK 4: LLM JUDGE (FAITHFULNESS) ---
    final_report = result["final_report"]
    score = llm_judge_score(raw_results, final_report)
    
    print(f"   [Judge] Faithfulness Score: {score}/100")
    if score > 80:
        print("   ✅ PASS: Report is accurate.")
    else:
        print("   ❌ FAIL: Report quality is low.")

if __name__ == "__main__":
    run_comprehensive_eval()