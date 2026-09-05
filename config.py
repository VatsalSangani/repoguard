from dotenv import load_dotenv

load_dotenv()

# LLM
DEFAULT_MODEL: str = "gpt-4o-mini"
LLM_TEMPERATURE: float = 0.0

# Parser
MAX_FILES_LIMIT: int = 30
IGNORED_DIRS: set[str] = {
    ".git", ".venv", "venv", "env", "node_modules",
    "__pycache__", "dist", "build", ".idea", ".vscode",
}
SUPPORTED_EXTENSIONS: tuple[str, ...] = (
    ".py", ".md", ".env", ".json", ".txt",
    ".sql", ".js", ".jsx", ".ts", ".tsx",  # Phase 1: SQL/JS/TS router support
)

# Guardrails
SENSITIVE_KEYWORDS: list[str] = [".env", "secrets", "credentials", "key.pem", "id_rsa"]
SAFE_SCAN_EXCLUDES: list[str] = [".env", "secrets"]

# Markdown tool
MAX_MARKDOWN_ISSUES: int = 10

# Secrets tool
MAX_SECRETS_ISSUES: int = 5
SECRETS_SCAN_TIMEOUT: int = 45
SECRETS_EXCLUDE_REGEX: str = r"(\.git/|\.venv/|venv/|node_modules/|dist/|build/|__pycache__/)"

# MCP / Ruff tool
MCP_COMMAND: str = "uvx"
MCP_SERVER: str = "mcp-server-analyzer"
MCP_TOOL_NAME: str = "ruff-check"
MCP_TOOL_ARG: str = "code"

# Aggregator
MAX_REPORT_INPUT_CHARS: int = 20_000

# Output
REPORT_FILENAME: str = "scan_report.md"

# Evaluation
EVAL_TEST_REPO_PATH: str = "test_repov3_stress"
EVAL_EXPECTED_MIN_FILES: int = 3
EVAL_JUDGE_PASS_SCORE: int = 80
