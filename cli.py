import json
import sys
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

from Agents.parser_agent import build_parser_agent
from Agents.processing_agent import build_processing_agent
from Agents.aggregator_agent import build_aggregator_agent

load_dotenv()


def last_text(agent_result) -> str:
    return agent_result["messages"][-1].content


def pretty_print(title: str, obj):
    print(f"\n=== {title} ===")
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def read_files_from_cli() -> list[str]:
    print("\nEnter repo file paths (one per line).")
    print("When finished, type: END")
    files = []
    while True:
        line = input("> ").strip()
        if line.upper() == "END":
            break
        if line:
            files.append(line)
    return files


def safe_json_load(s: str, label: str) -> dict:
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        print(f"\n❌ {label} returned non-JSON. Raw output below:\n")
        print(s)
        print("\nFix: tighten the prompt OR enforce structured output.")
        sys.exit(1)


def main():
    # Model choice
    model_name = input("Model name (default: gpt-4o-mini): ").strip() or "gpt-4o-mini"
    model = init_chat_model(model_name)

    # Build agents
    parser = build_parser_agent(model)
    processor = build_processing_agent(model)
    aggregator = build_aggregator_agent(model)

    print("\nChoose input mode:")
    print("1) Provide a file list (recommended)")
    print("2) Provide a natural language repo description (works, but less reliable)")
    mode = input("Enter 1 or 2: ").strip() or "1"

    if mode == "1":
        files = read_files_from_cli()
        if not files:
            print("❌ No files provided. Exiting.")
            return
        parser_payload = {"files": files}
    else:
        desc = input("\nDescribe your repo structure in plain English:\n> ").strip()
        if not desc:
            print("❌ No description provided. Exiting.")
            return
        # We'll still pass it as 'files' text; prompt expects files,
        # but this keeps your prototype interactive.
        # Better is file list mode.
        parser_payload = {"files": [desc]}

    # ----------------------------
    # 1) ParserAgent
    # ----------------------------
    parsed_raw = parser.invoke({"messages": [{"role": "user", "content": json.dumps(parser_payload)}]})
    parsed_text = last_text(parsed_raw)
    parsed = safe_json_load(parsed_text, "ParserAgent")
    pretty_print("ParserAgent output", parsed)

    # ----------------------------
    # 2) ProcessingAgent
    # ----------------------------
    planned_raw = processor.invoke({
        "messages": [{"role": "user", "content": json.dumps({"tasks": parsed.get("tasks", [])})}]
    })
    planned_text = last_text(planned_raw)
    planned = safe_json_load(planned_text, "ProcessingAgent")
    pretty_print("ProcessingAgent output", planned)

    # ----------------------------
    # 3) AggregatorAgent
    # ----------------------------
    files_total = len(parser_payload.get("files", []))
    summary = {
        "files_total": files_total,
        "markdown_files": len(parsed.get("markdown_files", [])),
        "python_files": len(parsed.get("python_files", [])),
        "tasks_total": len(parsed.get("tasks", [])),
        "planned_tool_calls_total": len(planned.get("planned_tool_calls", [])),
    }

    agg_input = {
        "summary": summary,
        "planned_tool_calls": planned.get("planned_tool_calls", []),
        "tool_results": [],  # dummy: no tools yet
    }

    report_raw = aggregator.invoke({"messages": [{"role": "user", "content": json.dumps(agg_input)}]})
    report_text = last_text(report_raw)
    report = safe_json_load(report_text, "AggregatorAgent")
    pretty_print("AggregatorAgent output (final report)", report)

    print("\n✅ Done. This is a plan-only prototype (no validator tools executed).")



    validator = Validator()
    result = validator.run(path)


if __name__ == "__main__":
    main()




src/
    __init__.py   (importance?)
    agents/
    tools/
    utils/
    config/

__init__.py

tests/
.env
