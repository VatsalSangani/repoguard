# 🛡️ RepoGuard: Agentic Security Orchestrator

**RepoGuard** is an autonomous **Neuro-Symbolic AI Agent** designed to audit codebases for security vulnerabilities, secrets, and style compliance.

Unlike standard static analysis scripts, RepoGuard uses an **LLM-based ReAct (Reason+Act) Loop** to dynamically plan its audit strategy, select the appropriate tools, and synthesize findings into a human-readable report. It features a hybrid architecture that combines the flexibility of GenAI with the reliability of deterministic tools like `ruff` and `detect-secrets`.

---

##  Key Features

* ** Agentic Orchestration:** Built with **LangGraph** to model a cyclic state machine that reasons about file types and selects tools dynamically.
* ** Model Context Protocol (MCP):** Implements a custom driver to interface with the **Ruff Language Server** via the MCP standard, enabling deep Python analysis.
* ** Hybrid Intelligence:** Prevents AI hallucinations by relying on industry-standard static analysis engines (`detect-secrets`, `pymarkdown`, `ruff`) for execution, while using the LLM for planning and summarization.
* ** Async Concurrency:** Manages complex asyncio event loops to handle high-throughput messaging with MCP servers without crashing.
* ** Dual Reporting:** Generates both a clean **Markdown Summary** for developers and a structured **JSON Report** for CI/CD pipelines.

---

##  Architecture

RepoGuard follows a modular pipeline architecture where the **Main Agent** acts as the orchestrator for specialized sub-agents and tools.

1.  **Parser Agent:** Analyzes input paths and breaks them down into atomic tasks.
2.  **Processing Agent:** Converts tasks into an execution plan.
3.  **Tool Execution:**
    * **SecretsValidator:** Scans for API keys and credentials.
    * **MarkdownValidator:** Checks documentation standards.
    * **PythonValidator (MCP):** Connects to the Ruff MCP Server for linting.
4.  **Aggregator Agent:** Compiles raw data into a final coherent report.

---

## 📦 Installation

### Prerequisites
* Python 3.10+
* [uv](https://github.com/astral-sh/uv) (Recommended for MCP tool management) or `pip`

### 1. Clone the Repository
```
git clone [https://github.com/yourusername/repoguard.git](https://github.com/yourusername/repoguard.git)
cd repoguard
```

### 2. Install Dependencies
```
pip install -r requirements.txt
```

### 3. Setup Environment Variables
Create a .env file in the root directory and add your OpenAI API Key:
```
OPENAI_API_KEY=sk-proj-your-key-here
```

## Usage

Run the main agent entry point:

```
python agents/main_agent.py
```

## Interactive Mode
The agent will prompt you for a target path. You can provide:
1.   Single File: test_repo/src/config.py
2.   Directory: test_repo
3.   Multiple Paths: test_repo/src/main.py test_repo/docs

## Example Output
```
=== RepoGuard (Dynamic Multi-Target Production Ready) ===
Enter path(s): test_repo

... [Agent Reasoning & Tool Execution Logs] ...

=== Final Report ===

### Key Findings:
- **Total Files Scanned:** 5
- **Total Issues Found:** 12
- **Tools Executed:** 3

### Critical Findings:
- [SecretsValidator] Potential secret detected at Line 2
- [PythonCodeValidator] File: config.py | Issues: 3 found

### Recommended Next Steps:
1. Review critical findings.
2. URGENT: Rotate exposed secrets and add them to `.gitignore`.
3. Run `ruff check .` locally to fix any linting errors.

[+] Full report saved to 'scan_report.md'

```

## Project Structure
```
/
├── agents/                 # The "Brain" (LLM Logic)
│   ├── main_agent.py       # Entry point & ReAct Loop
│   ├── parser_agent.py     # Task decomposition
│   ├── processing_agent.py # Tool planning
│   ├── aggregator_agent.py # Reporting logic
│   └── schemas.py          # Pydantic models
├── tools/                  # The "Body" (Deterministic Execution)
│   └── tools.py            # Wrappers for ruff, detect-secrets, etc.
├── mcp_drivers/            # Connectivity
│   └── mcp_driver.py       # Custom driver for MCP Server interaction
├── draw_architecture.py    # Architecture visualization script
├── requirements.txt        # Dependencies
└── .env                    # Secrets

```

## Tech Stack
*   Orchestration: LangGraph
*   LLM Provider: OpenAI (GPT-4o Mini)
*   Protocols: Model Context Protocol (MCP)
*   Static Analysis: Ruff, Detect-Secrets, PyMarkdown
*   Runtime: Python Asyncio
