# 🛡️ RepoGuard: Neuro-Symbolic Security Agent

**RepoGuard** is an advanced autonomous AI agent designed to audit codebases for security vulnerabilities, exposed secrets, and code quality issues.

Unlike traditional static analysis tools that blindly scan every file, RepoGuard uses a **Multi-Agent Neuro-Symbolic Architecture**. It combines the reasoning capabilities of Large Language Models (LLMs) to understand context and intent, with the reliability of deterministic industry-standard tools (Ruff, Detect-Secrets) to execute precise scans.

It features **Human-in-the-Loop (HIL)** controls for high-risk operations and an **Automated Evaluation Suite** to prevent hallucinations.

---

## Key Features

* **Multi-Agent Orchestration:** A sequential chain of specialized agents (Parser → Guardrails → Processor → Aggregator) built with **LangGraph**.
* **Intelligent Routing:** Uses "1-to-Many" routing logic. A single file can be routed to multiple tools simultaneously (e.g., a Python file is checked for *both* syntax errors and hardcoded secrets).
* **Human-in-the-Loop (HIL):** The agent autonomously pauses and requests user approval before processing high-risk files (like `.env` or auth logic). Includes a "Safe Scan" mode to auto-sanitize inputs.
* **Automated Evaluation Suite:** Includes a built-in `evaluate.py` script that uses a secondary "Judge LLM" (GPT-4o-mini) to grade the agent's reporting accuracy and hallucination rate.
* **Deep Analysis:**
    * **Python:** Syntax & Logic checks via Ruff.
    * **Secrets:** Entropy and pattern-based secret detection.
    * **Markdown:** Documentation standards and formatting validation.

---

## Architecture

RepoGuard operates as a state-based graph application:

```mermaid
graph LR
    User -->|Input Path| Parser(Parser Agent)
    Parser -->|File List| Guard{Guardrails}
    Guard -- High Risk --> HIL[Human Approval]
    Guard -- Safe --> Proc(Processing Agent)
    HIL -- "Safe Scan" --> Filter[Remove Secrets]
    Filter --> Proc
    HIL -- Approved --> Proc
    Proc -->|1-to-Many Routing| Tools[Tools Execution]
    Tools -->|Raw Logs| Agg(Aggregator Agent)
    Agg -->|Final Report| Report[scan_report.md]
```

## The Agent Squad

* **Parser Agent:** Intelligently maps the target directory, ignoring noise (binaries, .venv) and handling user intent.
* **Guardrails:** A safety layer that flags sensitive files (.env, id_rsa) and triggers the Human-in-the-Loop intervention.
* **Processing Agent:** The "Router." It inspects each file and selects the correct combination of tools (e.g., ["python", "secrets"] for main.py).
* **Aggregator Agent:** A writer agent that synthesizes raw JSON tool logs into a professional, actionable Markdown report.

---

## Installation
**Prerequisites**
* Python 3.10+
* Git

1. Clone the Repository
```
git clone https://github.com/VatsalSangani/repoguard.git
cd repoguard
```
2. Install Dependencies
```
pip install -r requirements.txt
```

3. Setup Environment Variables
Create a .env file in the root directory:
```
OPENAI_API_KEY=sk-proj-your-key-here
# Optional: Enable tracing for debugging
LANGCHAIN_TRACING_V2=true
```

---

## Usage and Demo
**Run a Security Scan**
To start the interactive agent:
```
python main.py
```
* **Interactive Mode:** The agent will ask for a folder path.
* **Safe Mode:** If it detects secrets, it will ask: "[Y]es, [S]afe Scan, or [N]o?"
* **Output:** Findings are saved to scan_report.md.

![Demo 1 in CLI](https://github.com/VatsalSangani/repoguard/blob/main/Demo%20Image%201.png)
![Demo 2 in CLI](https://github.com/VatsalSangani/repoguard/blob/main/Demo%20Image%202.png)
![Demo 3 in CLI](https://github.com/VatsalSangani/repoguard/blob/main/Demo%20Image%203.png)

---

## Observability & Performance Metrics
RepoGuard includes enterprise-grade observability powered by LangSmith. This allows us to trace the agent's "thought process," monitor token usage, and optimize latency for real-world deployment.

The screenshots below demonstrate a live tracing of the same demo example we have used above:

![Tracing 1](https://github.com/VatsalSangani/repoguard/blob/main/Langsmith%20Tracing%201.png)
![Tracing 2](https://github.com/VatsalSangani/repoguard/blob/main/Langsmith%20Tracing%202.png)
![Tracing 3](https://github.com/VatsalSangani/repoguard/blob/main/Langsmith%20Tracing%203.png)
![Tracing 4](https://github.com/VatsalSangani/repoguard/blob/main/Langsmith%20Tracing%204.png)

* **Cost:** The entire audit (Plan → Execute → Judge) runs for < $0.01 (approx 35k tokens) by leveraging optimized prompts and gpt-4o-mini.

* **Latency:** The graph handles long-running async operations (tool execution) while maintaining a responsive 1-2 second planning phase.

---

## Run the Evaluation Suite
To verify the agent's logic against a golden dataset:
```
# 1. Generate the test data (includes binaries & fake secrets)
python create_test_repo.py

# 2. Run the evaluator
python evaluate.py
```
**What it does:** Runs the agent in headless mode against test_repov3_stress and uses an LLM Judge to score the output (0-100).

---

## Project Structure
```
/
├── app.py                  # Streamlit entry point — page config, CSS, phase router (≤30 lines)
├── main.py                 # CLI entry point — interactive loop (≤50 lines)
├── config.py               # All tuneable constants (models, limits, timeouts, paths)
├── state.py                # Shared LangGraph state schema
│
├── ui/                     # Streamlit UI package
│   ├── state.py            # Session state defaults, cleanup_tmp(), reset()
│   ├── styles.py           # Dark-theme CSS injection
│   ├── components/
│   │   ├── header.py       # Title, caption, architecture expander
│   │   └── file_list.py    # Reusable file path display component
│   └── pages/              # One file per UI phase
│       ├── input_page.py   # Phase 1 — GitHub URL clone or manual file list
│       ├── approval_page.py # Phase 2 — risk metrics, file review, approve/safe/cancel
│       ├── scanning_page.py # Phase 3 — invokes graph, waits for result
│       └── results_page.py  # Phase 4 — renders report, download button
│
├── graph/
│   └── builder.py          # Assembles and compiles the LangGraph StateGraph
│
├── agents/                 # One file per agent node
│   ├── parser.py           # File discovery & filtering
│   ├── guardrails.py       # Risk detection & safety routing
│   ├── processor.py        # LLM-based tool routing + execution
│   └── aggregator.py       # Synthesises raw logs into a Markdown report
│
├── tools/                  # One file per tool
│   ├── markdown_tool.py    # PyMarkdownLint wrapper
│   ├── secrets_tool.py     # Detect-Secrets wrapper
│   └── python_tool.py      # Ruff via MCP wrapper
│
├── mcp_drivers/
│   └── mcp_driver.py       # Async MCP client for mcp-server-analyzer
│
├── models/
│   └── schemas.py          # Pydantic data contracts (FileList)
│
├── services/
│   └── report.py           # Saves the final report to disk
│
├── evaluate.py             # Automated Testing & LLM-as-a-Judge
├── create_test_repo.py     # Test data generator
├── requirements.txt        # Dependencies
└── scan_report.md          # Output artifact (generated at runtime)
```

---

## Evaluation Metrics
We measure the agent's performance on 4 key metrics:
1. **Recall:** Did it find 100% of the hidden secrets?

2. **Robustness:** Did it handle binary files and deep nesting without crashing?

3. **Tool Accuracy:** Did it select the correct tools (e.g., scanning dangerous.py for both syntax and secrets)?

4. **Faithfulness:** Did the final report accurately reflect the logs without hallucination? (Measured by LLM Judge).

---

## Future Roadmap
* **Docker Support:** Containerize the tool for CI/CD pipelines.

* **Custom Policies:** Allow users to define custom "Risk Rules" via a config file.

*  **Additional file types:** Add more file types like .java, .json, .css, .yaml, etc.


# CI/CD enabled
