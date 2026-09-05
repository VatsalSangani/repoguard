"""Integration tests against the real MCP tools directly (no LangGraph
pipeline, no mocking) — verifies each MCP server/driver in isolation:
structured output shape, empty-input handling, language edge cases, and
that failures come back as structured errors rather than hangs or crashes.
"""

import asyncio

import pytest
from pydantic import ValidationError

from agents.lang_agents._shared import from_mcp_findings, parse_mcp_text_content
from mcp_drivers.base_driver import BaseMCPDriver
from mcp_drivers.js_driver import JsMCPDriver
from mcp_drivers.mcp_driver import RuffMCPDriver
from mcp_drivers.sql_driver import SqlMCPDriver
from models.schemas import Finding

pytestmark = [pytest.mark.mcp, pytest.mark.timeout(60)]


def test_ruff_mcp_returns_structured_output():
    """Call the Ruff MCP server directly and confirm its output, once
    normalized by the Python sub-agent's shared helper, validates as a
    proper `Finding`."""

    async def _run():
        async with RuffMCPDriver(run_id="test-mcp-ruff") as driver:
            return await driver.run_scan_in_session("import os\n")

    content = asyncio.run(_run())
    parsed = parse_mcp_text_content(content)
    assert "issues" in parsed, f"Expected a dict with 'issues', got: {parsed}"
    assert parsed["total_issues"] >= 1, f"Expected >=1 issue for an unused import, got: {parsed}"

    issue = parsed["issues"][0]
    finding_dict = {
        "file": "scratch.py",
        "line": issue.get("line", 1),
        "rule": issue.get("rule", "UNKNOWN"),
        "severity": {"error": "high", "warning": "medium", "info": "info"}.get(issue.get("severity"), "medium"),
        "message": issue.get("message", ""),
        "tool": "ruff-check",
    }
    try:
        Finding.model_validate(finding_dict)
    except ValidationError as e:
        pytest.fail(f"Normalized Ruff output did not validate as a Finding: {e}\nDict was: {finding_dict}")


def test_sqlfluff_mcp_handles_empty_directory(tmp_path):
    empty_dir = tmp_path / "no_sql_here"
    empty_dir.mkdir()

    async def _run():
        async with SqlMCPDriver(run_id="test-mcp-sql-empty") as driver:
            return await driver.lint_in_session(str(empty_dir))

    content = asyncio.run(_run())
    parsed = parse_mcp_text_content(content)
    assert parsed.get("findings") == [], (
        f"Expected empty findings for a directory with no .sql files, got: {parsed}"
    )


def test_eslint_mcp_handles_typescript(tmp_path):
    ts_file = tmp_path / "sample.ts"
    ts_file.write_text(
        "function add(a: number, b: number): number {\n  return a + b;\n}\n\nexport { add };\n",
        encoding="utf-8",
    )

    async def _run():
        async with JsMCPDriver(run_id="test-mcp-js-ts") as driver:
            return await driver.lint_in_session(str(ts_file))

    content = asyncio.run(_run())
    parsed = parse_mcp_text_content(content)
    assert "findings" in parsed, f"Expected a dict with 'findings' for a .ts file, got: {parsed}"
    findings = from_mcp_findings("lint_javascript", parsed)
    for f in findings:
        assert f["rule"] != "ESLINT_NOT_INSTALLED", "eslint binary missing — run `npm install`"
    # Well-typed, side-effect-free TS should have no security/lint findings.
    assert findings == [], f"Expected no findings for valid TypeScript, got: {findings}"


def test_mcp_tool_timeout_returns_error():
    """Force an unreasonably short timeout and confirm the driver returns a
    structured timeout message instead of hanging or raising."""

    class _AlwaysTimesOutDriver(BaseMCPDriver):
        server_name = "sqlfluff"
        command = SqlMCPDriver.command
        args = SqlMCPDriver.args
        timeout_seconds = 0.001  # the server can't possibly start this fast

    async def _run():
        driver = _AlwaysTimesOutDriver(run_id="test-mcp-timeout")
        return await driver.call_tool("lint_sql", {"path": ".", "dialect": "ansi"})

    content = asyncio.run(_run())
    assert len(content) == 1, f"Expected exactly one structured timeout message, got: {content}"
    text = getattr(content[0], "text", "")
    assert "timed out" in text.lower(), f"Expected a timeout message, got: {text!r}"


def test_mcp_tool_invalid_path_returns_error():
    """A nonexistent path must come back as a structured NOT_FOUND finding,
    not an unhandled exception."""

    async def _run():
        async with SqlMCPDriver(run_id="test-mcp-invalid-path") as driver:
            return await driver.lint_in_session("/this/path/does/not/exist/anywhere")

    content = asyncio.run(_run())
    parsed = parse_mcp_text_content(content)
    findings = parsed.get("findings", [])
    assert len(findings) == 1, f"Expected exactly one NOT_FOUND finding, got: {findings}"
    assert findings[0]["rule"] == "NOT_FOUND", f"Expected rule 'NOT_FOUND', got: {findings[0]}"
    assert findings[0]["severity"] == "high", f"Expected severity 'high', got: {findings[0]}"
