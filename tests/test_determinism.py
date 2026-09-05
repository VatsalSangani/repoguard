"""Determinism: the same fixture run through the pipeline multiple times
must produce identical findings (same count, files, lines, rules).

Runs each fixture 3 times fresh (not via the shared cache) since the whole
point is to catch non-determinism *between* independent runs.
"""

import shutil

import pytest

from tests._helpers import FIXTURES_DIR, actual_findings

pytestmark = [pytest.mark.determinism, pytest.mark.timeout(60)]


def _sorted_findings(findings: list) -> list:
    return sorted(findings, key=lambda f: (f["file"], f["line"], f["rule"], f["tool"]))


@pytest.mark.parametrize("fixture_name", ["python_secrets", "sql_antipatterns"])
def test_repeated_runs_produce_identical_findings(fixture_name, run_pipeline, tmp_path):
    runs = []
    for i in range(3):
        # A fresh, distinctly-named copy per iteration — reusing one
        # destination across iterations would collide on copytree.
        fixture_path = tmp_path / f"{fixture_name}_run{i}"
        shutil.copytree(FIXTURES_DIR / fixture_name, fixture_path)
        final_state = run_pipeline(fixture_path)
        findings = _sorted_findings(actual_findings(final_state, fixture_path))
        # Message text can legitimately vary in wording between tool
        # versions/LLM-free tool runs (it shouldn't for our non-LLM tools,
        # but comparing structural fields is what actually matters for
        # determinism of *detection*, not of exact string phrasing).
        structural = [{k: f[k] for k in ("file", "line", "rule", "severity", "tool")} for f in findings]
        runs.append(structural)

    first = runs[0]
    for i, run in enumerate(runs[1:], start=2):
        if run != first:
            diff_only_in_first = [f for f in first if f not in run]
            diff_only_in_later = [f for f in run if f not in first]
            pytest.fail(
                f"Run 1 and run {i} of '{fixture_name}' produced different findings.\n"
                f"Present only in run 1: {diff_only_in_first}\n"
                f"Present only in run {i}: {diff_only_in_later}"
            )

    assert len(first) == len(runs[1]) == len(runs[2]), (
        f"Finding counts differ across 3 runs of '{fixture_name}': "
        f"{[len(r) for r in runs]}"
    )
