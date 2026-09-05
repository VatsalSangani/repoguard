"""P2P (pass-to-pass): clean fixtures must produce zero findings.

A test here FAILS if the pipeline reports any finding against a fixture
that is known to contain no issues (a false positive).
"""

import pytest

from tests._helpers import actual_findings

pytestmark = [pytest.mark.p2p, pytest.mark.timeout(60)]

CLEAN_FIXTURES = ["python_clean", "sql_clean", "js_clean", "json_valid"]


@pytest.mark.parametrize("fixture_name", CLEAN_FIXTURES)
def test_clean_fixture_produces_no_findings(cached_pipeline_result, fixture_name):
    final_state, fixture_path = cached_pipeline_result(fixture_name)
    findings = actual_findings(final_state, fixture_path)
    assert findings == [], (
        f"Expected zero findings for clean fixture '{fixture_name}', but got "
        f"{len(findings)} finding(s) (false positive(s)): {findings}"
    )


def test_mixed_repo_clean_file_has_no_findings(cached_pipeline_result):
    """Within the otherwise-dirty mixed_repo fixture, src/clean.py and
    web/data.json are the deliberately clean files — they must not
    generate findings just because their siblings do."""
    final_state, fixture_path = cached_pipeline_result("mixed_repo")
    findings = actual_findings(final_state, fixture_path)

    clean_file_findings = [f for f in findings if f["file"] in ("src/clean.py", "web/data.json")]
    assert clean_file_findings == [], (
        f"Expected no findings for the clean files (src/clean.py, web/data.json) "
        f"within mixed_repo, but got: {clean_file_findings}"
    )
