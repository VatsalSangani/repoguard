import sys
import os
import uuid
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from state import AgentState

# Import Nodes
from agents.parser_agent import parser_node
from agents.processing_agent import processing_node
from agents.aggregator_agent import aggregator_node
from agents.guardrails import guardrail_node, guardrail_router

# --- HELPER: SAVE REPORT ---
def save_report_to_disk(report_text):
    filename = "scan_report.md"
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(report_text)
        print(f"\n✅ Report saved to: {os.path.abspath(filename)}")
    except Exception as e:
        print(f"\n❌ Error saving report: {e}")

def build_graph():
    memory = MemorySaver()
    workflow = StateGraph(AgentState)

    workflow.add_node("parser", parser_node)
    workflow.add_node("guardrails", guardrail_node)
    workflow.add_node("processor", processing_node)
    workflow.add_node("aggregator", aggregator_node)

    workflow.set_entry_point("parser")
    workflow.add_edge("parser", "guardrails")
    workflow.add_conditional_edges(
        "guardrails",
        guardrail_router,
        {"end_workflow": END, "human_approval": "processor"}
    )
    workflow.add_edge("processor", "aggregator")
    workflow.add_edge("aggregator", END)

    return workflow.compile(checkpointer=memory, interrupt_before=["processor"])

if __name__ == "__main__":
    app = build_graph()
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}} 
    
    print("=== 🛡️ RepoGuard: AI Security Agent ===")

    while True:
        user_path = input("\nRepoGuard > Enter path to scan (or 'q' to quit): ").strip()
        if user_path.lower() == 'q': break

        print(f"\n🚀 Phase 1: Planning...")
        initial_state = {
            "user_input": user_path, 
            "target_files": [], 
            "raw_scan_results": [],
            "risk_level": "normal"
        }
        
        for event in app.stream(initial_state, config=config): pass 
        
        snapshot = app.get_state(config)
        
        if snapshot.values.get("guardrail_status") == "fail":
            print(f"\n❌ Aborted: {snapshot.values.get('error')}")
            continue

        elif snapshot.next:
            files = snapshot.values.get("target_files", [])
            risk = snapshot.values.get("risk_level")
            
            print(f"\n" + "-"*40 + "\n✋ APPROVAL REQUIRED\n" + "-"*40)
            print(f"Targeting: {len(files)} files")
            
            if risk == "high":
                print(f"⚠️  WARNING: {snapshot.values.get('risk_reason')}")
            
            print("\nOptions: [Y]es | [S]afe Scan (Exclude Secrets) | [N]o")
            choice = input("Select: ").lower().strip()

            if choice == "y":
                print("\n🚀 Resuming...")
                res = app.invoke(None, config=config)
                
                # PRINT AND SAVE
                print("\n" + res["final_report"])
                save_report_to_disk(res["final_report"])
            
            elif choice == "s" and risk == "high":
                print("\n🛡️ Removing sensitive files...")
                safe_files = [f for f in files if not any(x in f for x in [".env", "secrets"])]
                app.update_state(config, {"target_files": safe_files})
                
                print(f"   New Plan: {len(safe_files)} files.")
                res = app.invoke(None, config=config)
                
                # PRINT AND SAVE
                print("\n" + res["final_report"])
                save_report_to_disk(res["final_report"])
            
            else:
                print("❌ Cancelled.")