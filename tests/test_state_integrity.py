"""State-schema and cross-agent isolation integrity tests.

Uses `run_pipeline_with_state_capture` (not the cached fixture) since these
tests need the per-node update sequence, not just the final state.
"""

import pytest
from pydantic import ValidationError

from models.schemas import Finding, RunMetadata, validate_state_slice

pytestmark = [pytest.mark.state, pytest.mark.timeout(60)]


def test_state_schema_valid_at_every_node(run_pipeline_with_state_capture, fixture_copy):
    """Every state update returned by every node must validate: run_metadata
    against RunMetadata, and every tool_results finding against Finding."""
    fixture_path = fixture_copy("mixed_repo")
    final_state, node_updates = run_pipeline_with_state_capture(fixture_path)

    assert node_updates, "Expected at least one node update from the pipeline run"

    for node_name, update in node_updates:
        if "run_metadata" in update:
            try:
                validate_state_slice(
                    update["run_metadata"], RunMetadata, keys=["run_id", "repo_name", "commit_sha"]
                )
            except ValidationError as e:
                pytest.fail(f"Node '{node_name}' produced an invalid run_metadata: {e}\nUpdate was: {update}")

        tool_results = update.get("tool_results")
        if tool_results:
            for lang, findings in tool_results.items():
                for finding in findings:
                    try:
                        Finding.model_validate(finding)
                    except ValidationError as e:
                        pytest.fail(
                            f"Node '{node_name}' wrote an invalid Finding under "
                            f"tool_results['{lang}']: {e}\nFinding was: {finding}"
                        )


def test_no_state_key_overwrite_across_agents(run_pipeline_with_state_capture, fixture_copy):
    """mixed_repo has both Python and SQL files, so python_agent and
    sql_agent both run in the same fan-out superstep. After both complete,
    the final tool_results must contain BOTH languages' findings — neither
    should have clobbered the other's key."""
    fixture_path = fixture_copy("mixed_repo")
    final_state, _ = run_pipeline_with_state_capture(fixture_path)

    tool_results = final_state.get("tool_results") or {}
    assert "py" in tool_results, f"Expected 'py' key intact in tool_results, got keys: {list(tool_results.keys())}"
    assert "sql" in tool_results, f"Expected 'sql' key intact in tool_results, got keys: {list(tool_results.keys())}"
    assert "js" in tool_results, f"Expected 'js' key intact in tool_results, got keys: {list(tool_results.keys())}"
    assert "json" in tool_results, f"Expected 'json' key intact in tool_results, got keys: {list(tool_results.keys())}"

    # mixed_repo/src/dirty.py has a real unused-import finding — if the py
    # key had been clobbered by a concurrent sub-agent write, this would be
    # empty instead.
    assert len(tool_results["py"]) > 0, (
        f"Expected non-empty 'py' findings (dirty.py has a known F401 issue), got: {tool_results['py']}"
    )


def test_file_manifest_completeness(run_pipeline_with_state_capture, fixture_copy):
    """Parser -> Router must list every file in the fixture, grouped
    correctly by extension, with none dropped and none duplicated."""
    fixture_path = fixture_copy("mixed_repo")
    final_state, _ = run_pipeline_with_state_capture(fixture_path)

    on_disk = {
        ".py": [p for p in fixture_path.rglob("*.py")],
        ".sql": [p for p in fixture_path.rglob("*.sql")],
        ".js": [p for p in fixture_path.rglob("*.js")],
        ".json": [p for p in fixture_path.rglob("*.json")],
    }

    file_manifest = final_state.get("file_manifest") or {}
    assert len(file_manifest.get("py", [])) == len(on_disk[".py"]), (
        f"Expected {len(on_disk['.py'])} .py file(s) in file_manifest, "
        f"got {len(file_manifest.get('py', []))}: {file_manifest.get('py')}"
    )
    assert len(file_manifest.get("sql", [])) == len(on_disk[".sql"]), (
        f"Expected {len(on_disk['.sql'])} .sql file(s) in file_manifest, "
        f"got {len(file_manifest.get('sql', []))}: {file_manifest.get('sql')}"
    )
    assert len(file_manifest.get("js", [])) == len(on_disk[".js"]), (
        f"Expected {len(on_disk['.js'])} .js file(s) in file_manifest, "
        f"got {len(file_manifest.get('js', []))}: {file_manifest.get('js')}"
    )
    assert len(file_manifest.get("json", [])) == len(on_disk[".json"]), (
        f"Expected {len(on_disk['.json'])} .json file(s) in file_manifest, "
        f"got {len(file_manifest.get('json', []))}: {file_manifest.get('json')}"
    )

    all_manifest_files = [f for files in file_manifest.values() for f in files]
    assert len(all_manifest_files) == len(set(all_manifest_files)), (
        f"file_manifest contains duplicate file entries: {all_manifest_files}"
    )


def test_router_dispatches_to_correct_agents(run_pipeline_with_state_capture, fixture_copy):
    """mixed_repo has files in all four languages, so all four sub-agents
    must run; a fixture with only one language must dispatch to only that
    sub-agent."""
    mixed_path = fixture_copy("mixed_repo")
    _, mixed_updates = run_pipeline_with_state_capture(mixed_path)
    mixed_nodes = {name for name, _ in mixed_updates}

    for expected_node in ("python_agent", "sql_agent", "js_agent", "json_agent"):
        assert expected_node in mixed_nodes, (
            f"Expected '{expected_node}' to run for mixed_repo (all 4 languages present), "
            f"but only these nodes ran: {sorted(mixed_nodes)}"
        )


def test_router_skips_irrelevant_agents(run_pipeline_with_state_capture, fixture_copy):
    """python_clean has only .py files — sql_agent/js_agent/json_agent must
    NOT run (the whole point of the router's dynamic fan-out)."""
    py_only_path = fixture_copy("python_clean")
    _, updates = run_pipeline_with_state_capture(py_only_path)
    nodes_ran = {name for name, _ in updates}

    assert "python_agent" in nodes_ran, f"Expected 'python_agent' to run, got nodes: {sorted(nodes_ran)}"
    for irrelevant_node in ("sql_agent", "js_agent", "json_agent"):
        assert irrelevant_node not in nodes_ran, (
            f"'{irrelevant_node}' should not run for a Python-only fixture, "
            f"but it did. Nodes that ran: {sorted(nodes_ran)}"
        )
