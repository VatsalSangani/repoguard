"""One-off script: run the real pipeline against every tests/fixtures/*
fixture and dump the resulting tool_results as tests/golden/<fixture>.json.

Not part of the test suite — run manually whenever a fixture's expected
output needs to be regenerated after a deliberate fixture change.
"""

import json
import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

from graph.builder import build_graph
from observability.run_metadata import as_langgraph_config, build_run_metadata

load_dotenv()

FIXTURES_DIR = Path("tests/fixtures")
GOLDEN_DIR = Path("tests/golden")
GOLDEN_DIR.mkdir(parents=True, exist_ok=True)


def normalize_path(file_path: str, fixture_root: Path) -> str:
    """Make a tool-reported file path relative to the fixture root, with
    forward slashes, so goldens are stable across OS/checkout location."""
    p = Path(file_path)
    try:
        rel = p.resolve().relative_to(fixture_root.resolve())
    except ValueError:
        rel = Path(os.path.relpath(file_path, fixture_root))
    return str(rel).replace("\\", "/")


def run_fixture(fixture_name: str) -> dict:
    fixture_root = FIXTURES_DIR / fixture_name
    app = build_graph()
    run_metadata = build_run_metadata(str(fixture_root))
    cfg = as_langgraph_config(run_metadata, thread_id=str(uuid.uuid4()))

    for _ in app.stream(
        {
            "user_input": str(fixture_root),
            "target_files": [],
            "raw_scan_results": [],
            "risk_level": "normal",
            "run_metadata": run_metadata,
        },
        config=cfg,
    ):
        pass

    snap = app.get_state(cfg)
    if snap.values.get("guardrail_status") == "fail":
        return {"fixture": fixture_name, "expected_findings": [], "expected_finding_count": 0, "error": snap.values.get("error")}

    # Always proceed with the full file set (the "Y" HITL choice) — several
    # fixture dir names (e.g. python_secrets) contain "secrets", which would
    # otherwise trip Safe Scan's substring-based exclusion and wrongly strip
    # every file out of the fixture, not just an actual .env/secrets file.
    res = app.invoke(None, config=cfg)
    tool_results = res.get("tool_results") or {}

    findings = []
    for lang, lang_findings in tool_results.items():
        for f in lang_findings:
            findings.append({
                "file": normalize_path(f["file"], fixture_root),
                "line": f["line"],
                "rule": f["rule"],
                "severity": f["severity"],
                "tool": f["tool"],
                "message": f["message"],
            })

    findings.sort(key=lambda f: (f["file"], f["line"], f["rule"]))

    return {
        "fixture": fixture_name,
        "file_manifest": {
            lang: [normalize_path(f, fixture_root) for f in fs]
            for lang, fs in (res.get("file_manifest") or {}).items()
        },
        "expected_findings": findings,
        "expected_finding_count": len(findings),
        "expected_false_positives": 0,
    }


def main():
    fixture_names = sorted(p.name for p in FIXTURES_DIR.iterdir() if p.is_dir())
    only = sys.argv[1:] if len(sys.argv) > 1 else fixture_names
    for name in only:
        print(f"=== {name} ===")
        golden = run_fixture(name)
        out_path = GOLDEN_DIR / f"{name}.json"
        out_path.write_text(json.dumps(golden, indent=2) + "\n", encoding="utf-8")
        print(f"  {golden['expected_finding_count']} finding(s) -> {out_path}")


if __name__ == "__main__":
    main()
