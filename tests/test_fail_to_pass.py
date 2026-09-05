"""F2P (fail-to-pass): every known issue planted in a dirty fixture must be
detected by the pipeline, with the correct file/line/rule/severity/tool.

A test here FAILS if the pipeline misses a known issue (a false negative).

All tests in this module share one pipeline run per fixture (via the
session-scoped `cached_pipeline_result` fixture) since many assertions here
target different findings from the same run.
"""

import pytest

from tests._helpers import actual_findings, find_finding, load_golden

pytestmark = [pytest.mark.f2p, pytest.mark.timeout(60)]

DIRTY_FIXTURES = [
    "python_secrets",
    "sql_antipatterns",
    "js_vulnerabilities",
    "json_invalid",
    "mixed_repo",
    "python_unicode",
]


def _findings_for(cached_pipeline_result, fixture_name: str) -> list:
    final_state, fixture_path = cached_pipeline_result(fixture_name)
    return actual_findings(final_state, fixture_path)


# --- Headline, individually named cases (one per marquee planted issue) ---


def test_detects_hardcoded_aws_key(cached_pipeline_result):
    findings = _findings_for(cached_pipeline_result, "python_secrets")
    match = find_finding(findings, file="config.py", rule="AWS Access Key")
    assert match is not None, (
        f"Expected an 'AWS Access Key' finding for config.py, got findings: {findings}"
    )
    assert match["line"] == 12, f"Expected line 12, got line {match['line']}"
    assert match["severity"] == "high", f"Expected severity 'high', got '{match['severity']}'"
    assert match["tool"] == "detect-secrets", f"Expected tool 'detect-secrets', got '{match['tool']}'"


def test_detects_hardcoded_db_password(cached_pipeline_result):
    findings = _findings_for(cached_pipeline_result, "python_secrets")
    match = find_finding(findings, file="utils/db.py", rule="Secret Keyword")
    assert match is not None, (
        f"Expected a 'Secret Keyword' finding for utils/db.py, got findings: {findings}"
    )
    assert match["line"] == 3, f"Expected line 3, got line {match['line']}"
    assert match["severity"] == "high", f"Expected severity 'high', got '{match['severity']}'"


def test_detects_unused_import(cached_pipeline_result):
    findings = _findings_for(cached_pipeline_result, "python_secrets")
    match = find_finding(findings, file="main.py", rule="F401")
    assert match is not None, f"Expected an 'F401' unused-import finding for main.py, got: {findings}"
    assert match["tool"] == "ruff-check", f"Expected tool 'ruff-check', got '{match['tool']}'"


def test_detects_select_star_antipattern(cached_pipeline_result):
    findings = _findings_for(cached_pipeline_result, "sql_antipatterns")
    match = find_finding(findings, file="queries/fetch_users.sql", rule="AM04")
    assert match is not None, (
        f"Expected an 'AM04' (ambiguous column count / SELECT *) finding for "
        f"queries/fetch_users.sql, got: {findings}"
    )
    assert match["tool"] == "lint_sql", f"Expected tool 'lint_sql', got '{match['tool']}'"


def test_detects_unsafe_eval(cached_pipeline_result):
    findings = _findings_for(cached_pipeline_result, "js_vulnerabilities")
    match = find_finding(findings, file="utils/parser.js", rule="security/detect-eval-with-expression")
    assert match is not None, f"Expected an unsafe-eval finding for utils/parser.js, got: {findings}"
    assert match["line"] == 8, f"Expected line 8, got line {match['line']}"
    assert match["tool"] == "lint_javascript", f"Expected tool 'lint_javascript', got '{match['tool']}'"


def test_detects_object_injection_pattern(cached_pipeline_result):
    findings = _findings_for(cached_pipeline_result, "js_vulnerabilities")
    match = find_finding(findings, file="api/handler.js", rule="security/detect-object-injection")
    assert match is not None, (
        f"Expected a prototype-pollution-prone object-injection finding for "
        f"api/handler.js, got: {findings}"
    )


def test_detects_hardcoded_api_key_in_js(cached_pipeline_result):
    findings = _findings_for(cached_pipeline_result, "js_vulnerabilities")
    match = find_finding(findings, file="config/settings.js", rule="Secret Keyword")
    assert match is not None, f"Expected a hardcoded-secret finding for config/settings.js, got: {findings}"
    assert match["tool"] == "detect-secrets", f"Expected tool 'detect-secrets', got '{match['tool']}'"


def test_detects_malformed_json(cached_pipeline_result):
    findings = _findings_for(cached_pipeline_result, "json_invalid")
    match = find_finding(findings, file="config.json", rule="INVALID_JSON")
    assert match is not None, f"Expected an 'INVALID_JSON' finding for config.json, got: {findings}"
    assert match["severity"] == "high", f"Expected severity 'high', got '{match['severity']}'"


def test_detects_incomplete_openapi_spec(cached_pipeline_result):
    findings = _findings_for(cached_pipeline_result, "json_invalid")
    match = find_finding(findings, file="api-spec.json", rule="oas3-api-servers")
    assert match is not None, (
        f"Expected an 'oas3-api-servers' Spectral finding for api-spec.json, got: {findings}"
    )
    assert match["tool"] == "validate_json", f"Expected tool 'validate_json', got '{match['tool']}'"


def test_ruff_handles_unicode_content_without_crashing(cached_pipeline_result):
    """Regression test: on Windows, a spawned MCP server subprocess's stdio
    defaulted to cp1252 ("charmap"), so any Python file containing emoji or
    other non-cp1252 characters (e.g. print("✅ Done → next")) crashed Ruff
    with `'charmap' codec can't encode character ...` instead of producing
    real findings. Fixed by forcing PYTHONUTF8/PYTHONIOENCODING in the
    subprocess env (mcp_drivers/base_driver.py). This must keep finding the
    real F401 issue, not surface a RUFF_TOOL_ERROR/RUFF_SCAN_ERROR."""
    findings = _findings_for(cached_pipeline_result, "python_unicode")

    crash_findings = [f for f in findings if "RUFF_TOOL_ERROR" in f["rule"] or "RUFF_SCAN_ERROR" in f["rule"]]
    assert crash_findings == [], (
        f"Ruff crashed on Unicode content instead of scanning it: {crash_findings}"
    )

    match = find_finding(findings, file="emoji.py", rule="F401", line=5)
    assert match is not None, (
        f"Expected the real F401 unused-import finding for emoji.py despite its "
        f"emoji/arrow content, got: {findings}"
    )
    assert match["severity"] == "high", f"Expected severity 'high', got '{match['severity']}'"
    assert match["tool"] == "ruff-check", f"Expected tool 'ruff-check', got '{match['tool']}'"


# --- Comprehensive sweep: every finding in every golden must be reproduced ---


def _golden_finding_cases():
    cases = []
    for fixture_name in DIRTY_FIXTURES:
        golden = load_golden(fixture_name)
        for finding in golden["expected_findings"]:
            case_id = f"{fixture_name}::{finding['file']}::{finding['rule']}::L{finding['line']}"
            cases.append(pytest.param(fixture_name, finding, id=case_id))
    return cases


@pytest.mark.parametrize("fixture_name,expected", _golden_finding_cases())
def test_golden_finding_is_reproduced(cached_pipeline_result, fixture_name, expected):
    findings = _findings_for(cached_pipeline_result, fixture_name)
    match = find_finding(findings, file=expected["file"], rule=expected["rule"], line=expected["line"])
    assert match is not None, (
        f"[{fixture_name}] Expected finding {expected['rule']} in {expected['file']} at "
        f"line {expected['line']} (golden), but it was missing from actual findings: {findings}"
    )
    assert match["severity"] == expected["severity"], (
        f"[{fixture_name}] {expected['file']}::{expected['rule']}: "
        f"expected severity '{expected['severity']}', got '{match['severity']}'"
    )
    assert match["tool"] == expected["tool"], (
        f"[{fixture_name}] {expected['file']}::{expected['rule']}: "
        f"expected tool '{expected['tool']}', got '{match['tool']}'"
    )
