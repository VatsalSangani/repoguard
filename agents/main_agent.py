import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parent.parent))

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from parser_agent import parser_agent
from aggregator_agent import aggregator_agent
from processing_agent import (
    processing_agent,
    markdown_validator_tool, 
    python_validator_tool, 
    secrets_validator_tool
)

load_dotenv()

# Strict Prompt to ensure the AI passes through the full report
SYSTEM_PROMPT_TEXT = (
    "You are RepoGuard. Your job is to orchestrate a secure code scan.\n"
    "1. Call 'parser_agent' to get the tasks.\n"
    "2. Pass tasks to 'processing_agent'.\n"
    "3. EXECUTE tools sequentially.\n"
    "4. Call 'aggregator_agent' to generate the report.\n"
    "5. Output the full text summary provided by the aggregator, followed by the JSON report code block."
)

def build_main_agent():
    llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0.0)

    tools = [
        parser_agent, 
        processing_agent, 
        aggregator_agent,
        markdown_validator_tool,
        python_validator_tool,
        secrets_validator_tool
    ]

    graph = create_react_agent(model=llm, tools=tools)
    return graph

if __name__ == "__main__":
    print("=== RepoGuard (Dynamic Multi-Target Production Ready) ===")
    
    user_input = input("\nEnter path(s): ").strip()
    
    if user_input:
        try:
            graph = build_main_agent()
            
            messages = [
                ("system", SYSTEM_PROMPT_TEXT),
                ("user", f"Scan these paths: {user_input}")
            ]
            
            result = graph.invoke({"messages": messages})
            
            # 1. Capture the Full Output (Text + JSON)
            raw_content = result["messages"][-1].content
            
            print("\n=== Final Report ===")
            print(raw_content)
            
            # 2. Save as Markdown (.md) to preserve everything
            # We no longer extract just the JSON. We save the whole report.
            output_file = "scan_report.md"
            
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(raw_content)
                
            print(f"\n[+] Full report saved to '{output_file}'")

        except Exception as e:
            print(f"\n[!] Error: {e}")