import json
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

from Agents.parser_agent import build_parser_agent
from Agents.processing_agent import build_processing_agent
from Agents.aggregator_agent import build_aggregator_agent

load_dotenv()


def last_text(agent_result) -> str:
    # LangChain agent results typically look like: {"messages": [...]}
    return agent_result["messages"][-1].content


def main():
    # 1) Init model (LangChain docs style)
    model = init_chat_model("gpt-4o-mini", temperature=0, max_tokens=400)

    # 2) Build agents
    parser = build_parser_agent(model)
    processor = build_processing_agent(model)
    aggregator = build_aggregator_agent(model)

    # -----------------------------
    # Test 1: ParserAgent
    # -----------------------------
    files = [
        "README.md",
        "src/main.py",
        "docs/guide.mdx",
        "configs/dev.yaml",
        "scripts/check_secrets.py",
    ]

    parser_input = {"files": files}
    parsed_raw = parser.invoke({
        "messages": [{"role": "user", "content": json.dumps(parser_input)}]
    })
    parsed_text = last_text(parsed_raw)

    print("\n=== ParserAgent (raw) ===")
    print(parsed_text)

    # Ensure it's valid JSON
    parsed = json.loads(parsed_text)

    # -----------------------------
    # Test 2: ProcessingAgent
    # -----------------------------
    processing_input = {"tasks": parsed["tasks"]}
    planned_raw = processor.invoke({
        "messages": [{"role": "user", "content": json.dumps(processing_input)}]
    })
    planned_text = last_text(planned_raw)

    print("\n=== ProcessingAgent (raw) ===")
    print(planned_text)

    planned = json.loads(planned_text)

    # -----------------------------
    # Test 3: AggregatorAgent
    # -----------------------------
    summary = {
        "files_total": len(files),
        "markdown_files": len(parsed.get("markdown_files", [])),
        "python_files": len(parsed.get("python_files", [])),
        "tasks_total": len(parsed.get("tasks", [])),
        "planned_tool_calls_total": len(planned.get("planned_tool_calls", [])),
    }

    agg_input = {
        "summary": summary,
        "planned_tool_calls": planned.get("planned_tool_calls", []),
        "tool_results": [],  # empty for prototype
    }

    report_raw = aggregator.invoke({
        "messages": [{"role": "user", "content": json.dumps(agg_input)}]
    })
    report_text = last_text(report_raw)

    print("\n=== AggregatorAgent (raw) ===")
    print(report_text)

    json.loads(report_text)  # validate JSON
    print("\n✅ Smoke test passed: all three agents returned valid JSON.")


if __name__ == "__main__":
    main()