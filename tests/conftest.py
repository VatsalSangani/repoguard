"""Shared pytest fixtures for the RepoGuard test suite.

Runs the real LangGraph pipeline (real MCP subprocesses, real LLM calls at
LLM_TEMPERATURE=0.0) against copies of the fixtures under tests/fixtures/ —
no mocking of MCP tools, per project policy. Because each test spins up a
handful of MCP subprocesses and at least one LLM call, individual tests are
slower than typical unit tests; that's expected for this integration-style
suite (see the "state" timeout marker for the outliers).
"""

import shutil
import sys
import uuid
from pathlib import Path
from typing import Callable

import pytest
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()

from config import LLM_TEMPERATURE  # noqa: E402
from graph.builder import build_graph  # noqa: E402
from observability.run_metadata import as_langgraph_config, build_run_metadata  # noqa: E402
from tests._helpers import FIXTURES_DIR  # noqa: E402

assert LLM_TEMPERATURE == 0.0, (
    "Pipeline LLM calls must run at temperature 0.0 — tests rely on this "
    "for deterministic tool-selection/report output."
)


@pytest.fixture(scope="session")
def session_run_id() -> str:
    """One run_id shared by everything in this test session, distinct from
    the per-pipeline-invocation run_id each test's pipeline run generates."""
    return str(uuid.uuid4())


@pytest.fixture
def fixture_copy(tmp_path: Path) -> Callable[[str], Path]:
    """Copy a named fixture under tests/fixtures/<name> into a pytest tmp
    dir, so pipeline runs never mutate the checked-in fixtures."""

    def _copy(fixture_name: str) -> Path:
        src = FIXTURES_DIR / fixture_name
        if not src.exists():
            raise FileNotFoundError(f"No such fixture: {fixture_name} (looked in {src})")
        dst = tmp_path / fixture_name
        shutil.copytree(src, dst)
        return dst

    return _copy


def _initial_state(fixture_path: Path, run_metadata: dict) -> dict:
    return {
        "user_input": str(fixture_path),
        "target_files": [],
        "raw_scan_results": [],
        "risk_level": "normal",
        "run_metadata": run_metadata,
    }


@pytest.fixture
def run_pipeline() -> Callable[[Path], dict]:
    """Run the full pipeline (parser -> guardrails -> router -> sub-agents
    -> aggregator) against `fixture_path` and return the final state dict.

    Always proceeds past the HITL checkpoint with the complete file set
    (equivalent to the "Yes" choice) — tests assert against the full
    finding set, not a Safe-Scan-filtered subset. This matters because
    several fixture directory names (e.g. python_secrets) contain
    "secrets", which would otherwise trip Safe Scan's substring exclusion
    and strip files that aren't actually .env/secrets files.
    """

    def _run(fixture_path: Path) -> dict:
        app = build_graph()
        run_metadata = build_run_metadata(str(fixture_path))
        cfg = as_langgraph_config(run_metadata, thread_id=str(uuid.uuid4()))

        for _ in app.stream(_initial_state(fixture_path, run_metadata), config=cfg):
            pass

        snap = app.get_state(cfg)
        if snap.values.get("guardrail_status") == "fail":
            return snap.values

        return app.invoke(None, config=cfg)

    return _run


@pytest.fixture(scope="session")
def cached_pipeline_result(tmp_path_factory) -> Callable[[str], tuple]:
    """Session-scoped memoized pipeline run, keyed by fixture name.

    Several F2P tests assert on different findings from the *same* fixture
    run (e.g. 5 separate assertions against one `sql_antipatterns` run) —
    without caching, each assertion would re-run the full pipeline
    (multiple MCP subprocesses + an LLM call) from scratch. This runs each
    fixture at most once per test session and returns `(final_state,
    fixture_path)` on every subsequent call for that fixture name.
    """
    cache: dict = {}

    def _get(fixture_name: str) -> tuple:
        if fixture_name not in cache:
            src = FIXTURES_DIR / fixture_name
            if not src.exists():
                raise FileNotFoundError(f"No such fixture: {fixture_name} (looked in {src})")
            dst = tmp_path_factory.mktemp(f"cached_{fixture_name}") / fixture_name
            shutil.copytree(src, dst)

            app = build_graph()
            run_metadata = build_run_metadata(str(dst))
            cfg = as_langgraph_config(run_metadata, thread_id=str(uuid.uuid4()))

            for _ in app.stream(_initial_state(dst, run_metadata), config=cfg):
                pass

            snap = app.get_state(cfg)
            if snap.values.get("guardrail_status") == "fail":
                final_state = snap.values
            else:
                final_state = app.invoke(None, config=cfg)

            cache[fixture_name] = (final_state, dst)
        return cache[fixture_name]

    return _get


@pytest.fixture
def run_pipeline_with_state_capture() -> Callable[[Path], tuple]:
    """Run the pipeline and return `(final_state, node_updates)`, where
    `node_updates` is an ordered list of `(node_name, state_update_dict)`
    tuples — one entry per node boundary from parser through aggregator."""

    def _run(fixture_path: Path) -> tuple:
        app = build_graph()
        run_metadata = build_run_metadata(str(fixture_path))
        cfg = as_langgraph_config(run_metadata, thread_id=str(uuid.uuid4()))

        # LangGraph's stream() emits a "__interrupt__" pseudo-node (value: a
        # tuple of Interrupt objects, not a state dict) at the HITL pause —
        # filter it out, since it isn't a node's state update.
        node_updates = []
        for update in app.stream(_initial_state(fixture_path, run_metadata), config=cfg):
            node_updates.extend((k, v) for k, v in update.items() if k != "__interrupt__")

        snap = app.get_state(cfg)
        if snap.values.get("guardrail_status") == "fail":
            return snap.values, node_updates

        for update in app.stream(None, config=cfg):
            node_updates.extend((k, v) for k, v in update.items() if k != "__interrupt__")

        final_state = app.get_state(cfg).values
        return final_state, node_updates

    return _run
