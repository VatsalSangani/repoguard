"""Shared, non-fixture helpers for the test suite (path normalization,
golden-file loading). Kept separate from conftest.py so test modules can
import them directly without relying on pytest's fixture injection.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List

FIXTURES_DIR = Path(__file__).parent / "fixtures"
GOLDEN_DIR = Path(__file__).parent / "golden"


def normalize_path(file_path: str, fixture_root: Path) -> str:
    """Make a tool-reported file path relative to the fixture root, with
    forward slashes — matches the normalization used when the goldens were
    generated (see tests/generate_goldens.py), so actual vs. expected file
    paths compare equal regardless of OS or checkout location."""
    p = Path(file_path)
    try:
        rel = p.resolve().relative_to(fixture_root.resolve())
    except ValueError:
        rel = Path(os.path.relpath(file_path, fixture_root))
    return str(rel).replace("\\", "/")


def load_golden(fixture_name: str) -> Dict[str, Any]:
    path = GOLDEN_DIR / f"{fixture_name}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No golden file for fixture '{fixture_name}' at {path}. "
            f"Run `python tests/generate_goldens.py {fixture_name}` first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def actual_findings(final_state: Dict[str, Any], fixture_root: Path) -> List[Dict[str, Any]]:
    """Flatten `tool_results` (all languages) into the same normalized
    Finding-list shape used by the golden files, for direct comparison."""
    tool_results = final_state.get("tool_results") or {}
    findings = []
    for lang_findings in tool_results.values():
        for f in lang_findings:
            findings.append({
                "file": normalize_path(f["file"], fixture_root),
                "line": f["line"],
                "rule": f["rule"],
                "severity": f["severity"],
                "tool": f["tool"],
                "message": f["message"],
            })
    return findings


def find_finding(
    findings: List[Dict[str, Any]], *, file: str, rule: str, line: int | None = None
) -> Dict[str, Any] | None:
    """Look up one expected finding by (file, rule), optionally narrowed by
    line — some files have multiple findings sharing the same rule (e.g.
    three separate F401s), so `line` disambiguates which one to return."""
    for f in findings:
        if f["file"] == file and f["rule"] == rule and (line is None or f["line"] == line):
            return f
    return None
