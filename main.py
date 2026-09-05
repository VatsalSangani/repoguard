import uuid
from dotenv import load_dotenv
from config import SAFE_SCAN_EXCLUDES
from graph.builder import build_graph
from observability.run_metadata import as_langgraph_config, build_run_metadata
from services.report import save_report

load_dotenv()

def run_cli() -> None:
    app = build_graph()
    print("=== 🛡️ RepoGuard: AI Security Agent ===")
    while True:
        path = input("\nRepoGuard > Enter path to scan (or 'q' to quit): ").strip()
        if path.lower() == "q":
            break
        run_metadata = build_run_metadata(path)
        cfg = as_langgraph_config(run_metadata, thread_id=str(uuid.uuid4()))
        print("\n🚀 Phase 1: Planning...")
        for _ in app.stream(
            {
                "user_input": path,
                "target_files": [],
                "raw_scan_results": [],
                "risk_level": "normal",
                "run_metadata": run_metadata,
            },
            config=cfg,
        ):
            pass
        snap = app.get_state(cfg)
        if snap.values.get("guardrail_status") == "fail":
            print(f"\n❌ Aborted: {snap.values.get('error')}")
            continue
        if not snap.next:
            continue
        files = snap.values.get("target_files", [])
        risk = snap.values.get("risk_level")
        print(f"\n{'─'*40}\n✋ APPROVAL REQUIRED — {len(files)} files\n{'─'*40}")
        if risk == "high":
            print(f"⚠️  WARNING: {snap.values.get('risk_reason')}")
        print("\nOptions: [Y]es | [S]afe Scan (Exclude Secrets) | [N]o")
        choice = input("Select: ").lower().strip()
        if choice == "n":
            print("❌ Cancelled.")
            continue
        if choice == "s" and risk == "high":
            safe = [f for f in files if not any(x in f for x in SAFE_SCAN_EXCLUDES)]
            app.update_state(cfg, {"target_files": safe})
            print(f"   🛡️ Safe scan: {len(safe)} files.")
        print("\n🚀 Resuming...")
        res = app.invoke(None, config=cfg)
        print("\n" + res["final_report"])
        save_report(res["final_report"])

if __name__ == "__main__":
    run_cli()
