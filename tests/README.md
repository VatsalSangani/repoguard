# RepoGuard test suite

Integration tests against the real pipeline (real MCP subprocesses, real LLM
calls at `LLM_TEMPERATURE=0.0`, no mocking).

```
tests/
├── fixtures/       # Input repos the pipeline scans. Deliberately planted issues.
├── golden/         # Expected findings per fixture. Never passed to the pipeline as input.
├── generate_goldens.py   # Regenerate golden/*.json from a real pipeline run.
├── conftest.py     # Shared fixtures: fixture_copy, run_pipeline, cached_pipeline_result, ...
├── _helpers.py     # Path normalization / golden loading (not a test module itself).
└── test_*.py       # The test suites themselves.
```

**Isolation**: the pipeline is only ever pointed at `tests/fixtures/<name>` —
never at `tests/golden/`, `tests/*.py`, or `tests/_helpers.py`. Findings are
compared against the golden files *after* a run completes, entirely outside
the pipeline's own process of deciding what to report. This keeps the
"right answer" out of anything the agents can read while scanning.

Run everything: `pytest`. Run one marker: `pytest -m f2p`. Run one test:
`pytest tests/test_fail_to_pass.py::test_detects_hardcoded_aws_key -v`.

Regenerate goldens after a deliberate fixture change:
`python tests/generate_goldens.py <fixture_name>`.
