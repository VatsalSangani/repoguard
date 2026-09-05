# Battle Scars — Debugging Stories from Building RepoGuard

Personal interview-prep reference. Nine real bugs hit while building RepoGuard's MCP tooling and multi-agent pipeline, in the order they were found.

---

## Scar 1: Wire logger deadlock

**Situation:** Added JSON-RPC wire logging so every MCP `initialize`/`tools/list`/`tools/call` message would be captured to `logs/{run_id}/mcp_wire.jsonl`. First implementation wrapped the raw `anyio.MemoryObjectStream` pair returned by `stdio_client()` with a second stream pair and two forwarder tasks in a task group, snooping on messages as they passed through.

**Discovery:** Ran the pipeline against `test_repo/` with a 60-second cap. It hung at the `initialize` handshake every time — even with a warm `uvx` cache, ruling out slow package resolution. Isolated the exact call sequence against the raw `stdio_client` streams directly (bypassing the wrapper): completed instantly. That isolated the wrapper itself as the cause.

**Root Cause:** `mcp.ClientSession` requires the concrete `anyio.streams.memory.MemoryObjectReceiveStream`/`SendStream` types, and interposing a second unbuffered stream pair plus a forwarding task group in front of them is fragile — the forwarding tasks and the session's own read/write loop deadlocked waiting on each other.

**Fix:** Rewrote wire logging to operate at the RPC call boundary instead of the transport layer — `WireLogger.logged()` wraps each `session.initialize()` / `session.list_tools()` / `session.call_tool()` call, logging a request line before and a response line after, with the same fields (method, params, id, timestamp, result/error, latency_ms) the wire-level approach would have captured. No stream interception at all. (`mcp_drivers/wire_logger.py`, `mcp_drivers/base_driver.py`)

**Metric:** Before → hung indefinitely (killed after 60s, every time). After → same call sequence completes in under 1s for a two-call session.

**30-second interview version:** "I built JSON-RPC wire logging by wrapping the raw anyio streams between the MCP client and the transport, snooping on messages as they passed through with a forwarder task group. It deadlocked at the initialize handshake — turned out `ClientSession` needs the exact concrete stream types, and layering a second stream pair in front of them created a race between the forwarding tasks and the session's own read loop. I isolated it by testing the identical call sequence against the raw streams directly, which worked instantly, proving the wrapper was the problem. Fixed it by moving logging to the call boundary instead of the transport — wrap `initialize`/`list_tools`/`call_tool` themselves and log before/after each call. Same data captured, zero deadlock risk, because there's no extra stream plumbing at all."

---

## Scar 2: WindowsPath / None TypeError

**Situation:** After fixing the wire logger deadlock, re-ran the pipeline against `test_repo/` and every Python file scan failed with `TypeError: unsupported operand type(s) for /: 'WindowsPath' and 'NoneType'`.

**Discovery:** Full traceback pointed straight at `wire_logger.py`'s `_log_path()`: `Path("logs") / run_id / "mcp_wire.jsonl"` — `run_id` was `None`. Traced it back one level to `BaseMCPDriver.__init__`.

**Root Cause:** `BaseMCPDriver.__init__` resolved `self.run_id` correctly (falling back to a context-var default when no `run_id` was passed), but then built `WireLogger(run_id, self.server_name)` using the raw, unresolved `run_id` *parameter* instead of `self.run_id` — a one-line copy-paste slip.

**Fix:** Changed `WireLogger(run_id, ...)` to `WireLogger(self.run_id, ...)` in `mcp_drivers/base_driver.py`.

**30-second interview version:** "Right after fixing the deadlock, every Ruff scan started crashing with a TypeError dividing a WindowsPath by None. The traceback led straight to the wire logger's log-path construction, where `run_id` was `None`. One level up, the driver's `__init__` had correctly resolved `self.run_id` with a context-var fallback — but then passed the original, still-`None` constructor parameter into `WireLogger()` instead of the resolved attribute. Classic one-line copy-paste bug. Fixed by using `self.run_id` instead of the raw parameter. It's a good reminder that resolving a value and *using* the resolved value are two different lines, and it's easy to get them out of sync."

---

## Scar 3: LangSmith metadata nesting

**Situation:** Wanted every node's LangSmith trace tagged with `run_id`/`repo_name`/`commit_sha`. First attempt wrapped each node in its own `@traceable` span and separately tried writing custom fields onto `get_current_run_tree().extra`.

**Discovery:** User inspected the actual LangSmith UI and reported two problems: duplicate nested spans with the same name (e.g. `processor` → `processor`), and the custom `run_id`/`repo_name`/`commit_sha` fields simply not appearing under Attributes → Metadata at all.

**Root Cause:** Two separate mistakes. First, LangGraph already auto-creates one span per node when LangSmith tracing is enabled via env vars — wrapping the node in a second `@traceable` span of the same name just nested a redundant duplicate under the real one. Second, even after removing the duplicate span and writing metadata directly onto the existing span's `run_tree.extra`, LangSmith's UI reads the Metadata panel from `extra["metadata"]`, not top-level keys on `extra` — and separately, LangGraph's own auto-instrumentation can overwrite `extra` during the run regardless.

**Fix:** Two rounds. Round 1: stopped creating a second span — enriched the LangGraph-created span in place via `get_current_run_tree()`, nesting custom fields under `extra["metadata"]`. Round 2 (after that still didn't reliably surface in the UI): moved to the documented approach — pass `run_id`/`repo_name`/`commit_sha` via `RunnableConfig.metadata` at `.stream()`/`.invoke()` time, which LangGraph propagates to every node's trace automatically. This required computing `run_metadata` *before* invoking the graph (previously it was derived inside the parser node, too late for `config.metadata`). (`observability/tracing.py`, `observability/run_metadata.py`, `main.py`)

**30-second interview version:** "I wanted custom run metadata visible on every node's LangSmith trace. First pass wrapped each node in its own `@traceable` decorator, which created confusing duplicate nested spans — LangGraph already auto-instruments every node when tracing is on, so I was double-wrapping. Fixed that by enriching the existing span instead of creating a new one. But the custom fields still didn't show up in the UI, because LangSmith's Metadata panel specifically reads `extra['metadata']`, not arbitrary top-level keys — and LangGraph's own instrumentation can overwrite `extra` anyway. The actually-reliable fix was passing metadata through `RunnableConfig` at invocation time, which meant computing run_id/repo_name/commit_sha *before* calling the graph instead of inside the first node, since by then it's too late for the config to carry it."

---

## Scar 4: ESLint silent false negatives

**Situation:** Writing an isolated MCP integration test — `test_eslint_mcp_handles_typescript` — that lints a `.ts` file created in `tmp_path` (outside the project directory, unlike every fixture used so far, which all happened to live under the project root).

**Discovery:** The test failed asserting zero findings for valid TypeScript, but the actual finding returned was `{"rule": "eslint-notice", "message": "File ignored because outside of base path."}` — ESLint had silently skipped the file entirely and reported nothing wrong.

**Root Cause:** ESLint's flat config (ESLint 9+) refuses to lint any file outside its "base path," which defaults to the process's current working directory — not the config file's own directory. Every fixture used up to that point happened to live under `tests/fixtures/`, inside the project root, so this never surfaced. Any real-world target repo scanned by RepoGuard lives *outside* the project entirely, meaning the JS/TS sub-agent would have silently returned zero findings for every external repo, ever — a false negative with no error, no warning, nothing.

**Fix:** Launch the `eslint` subprocess with `cwd` set to the target file/directory's own location instead of the project root — the config is still passed by absolute path, which works regardless of cwd. (`mcp_servers/js_server.py`)

**Metric:** Before → 0 findings reported for any file outside the project root (silently wrong). After → correct findings for external targets, verified via `AppTest` against a real clone of the project into a separate temp directory.

**30-second interview version:** "I was writing an isolated integration test for the ESLint MCP tool and used `tmp_path` for the test file, since that's normal pytest practice — and it failed in a way I didn't expect: not a crash, but zero findings, with ESLint quietly reporting 'file ignored because outside of base path.' That's the dangerous kind of bug — silent, not loud. Every fixture I'd tested against up to that point happened to live inside the project directory, which is exactly why this hadn't shown up yet. But RepoGuard's whole job is scanning *other* repos, which always live outside the project root — so this meant the JS/TS scanner had never actually worked on a real target repo, it just looked like it did because it returned an empty, valid-looking result. Fixed by launching eslint with cwd set to the target's own directory instead of the project root. The lesson: a test fixture that happens to be convenient can also happen to hide the exact bug that matters."

---

## Scar 5: detect-secrets absolute path bug

**Situation:** Right after fixing the ESLint base-path bug, writing pytest fixtures that copy repo content into `tmp_path` (standard pytest isolation practice) started failing the secrets-detection tests — findings that were present when scanning the fixture in place vanished when scanning the exact same content from a temp copy.

**Discovery:** Isolated `detect-secrets` at the CLI level: ran it against the same file content twice, once with an absolute path, once with a relative path from within that directory. Absolute path: zero results, silently. Relative path: found the secret correctly.

**Root Cause:** `detect-secrets scan` silently returns zero results when given an absolute path — an undocumented quirk of how it computes paths internally. `tools/secrets_tool.py` always called it with `str(p.resolve())`, an absolute path, every time.

**Fix:** Changed the subprocess invocation to run with `cwd` set to the scan root and pass a *relative* target path — the same fix pattern as the ESLint base-path bug. Reconstructs the original absolute-style path for reporting by joining `scan_root` back onto detect-secrets' relative output filenames. (`tools/secrets_tool.py`)

**Metric:** Before → 0 secrets found when scanning via an absolute path (silently). After → correct detection regardless of whether the target is passed as an absolute or relative path.

**30-second interview version:** "This one surfaced right after the ESLint bug, from the same root cause category. I was writing pytest fixtures that copy test content into a temp directory — completely standard practice — and secrets detection just stopped finding anything, with no error. I isolated it down to the `detect-secrets` CLI itself: identical content, but an absolute path returns zero results while a relative path from the right working directory finds the secret correctly. It's an undocumented quirk in how the tool resolves paths internally. Our code always called it with a fully-resolved absolute path. Fixed with the exact same pattern as the ESLint fix: set the subprocess's cwd to the scan root and pass a relative path instead. Two unrelated tools, same underlying lesson — external CLI tools often have working-directory assumptions baked in that aren't documented anywhere, and you only find them by testing from a location other than the one you always develop in."

---

## Scar 6: Session reuse performance

**Situation:** The Ruff MCP driver opened a brand-new `uvx mcp-server-analyzer` subprocess for *every single file* scanned — a cold `uvx` start resolves and can download the tool's dependency environment from scratch each time.

**Discovery:** A 60-second-capped pipeline run against `test_repo/` (six files, two Python) kept timing out. Captured process output mid-run showed live `pip`-style dependency downloads (`Downloading ruff...`, `Downloading pydantic-core...`) happening on *every* file, not just the first.

**Root Cause:** `ruff_lint_impl` (and later, `python_agent_node`) constructed a fresh `RuffMCPDriver()` instance inside the per-file loop, and each instance's `async with driver:` opened and tore down its own subprocess — so a directory with N Python files paid the `uvx` cold-start cost N times instead of once.

**Fix:** Added persistent-session support to `BaseMCPDriver` — `async with driver:` now opens one stdio connection + MCP session that's reused across many `call_tool_in_session()` calls, instead of the one-shot `call_tool()` (connect → call → teardown) that existed before. `ruff_lint_impl` and `python_agent_node` now open one driver for the whole batch and loop `run_scan_in_session()` calls over it. (`mcp_drivers/base_driver.py`, `mcp_drivers/mcp_driver.py`, `tools/python_tool.py`, `agents/lang_agents/python_agent.py`)

**Metric:** Before → one full `uvx` subprocess spawn per file (multiple seconds of cold-start overhead each, scaling linearly with file count). After → one subprocess spawn per sub-agent invocation regardless of file count; a two-file scan's wire log shows exactly one `initialize` (~4.4s cold start) and two `tools/call` entries (83ms, 18ms) — the per-file cost dropped to just the actual lint time.

**30-second interview version:** "The Ruff scanner was opening a brand-new MCP server subprocess for every single file — and since it's launched via `uvx`, a cold start can mean re-resolving and downloading the tool's whole dependency environment, not just starting a process. I caught this because a test repo with only six files kept timing out, and when I captured the subprocess output mid-run, I could see live package downloads happening on every file, not just the first one. The fix was adding real session reuse to the base MCP driver class — `async with driver` now opens one connection that stays alive across as many tool calls as you want, instead of connect-call-teardown every time. So scanning N files now pays the startup cost once, not N times. It's the kind of bug that's invisible in a two-file demo and only shows up once you throw a real-sized repo at it."

---

## Scar 7: Parser ignoring cloned repo files

**Situation:** Debugging a report that the Streamlit UI's parser only found 3 files (`requirements.txt`, `README.md`, `config.py`) when scanning a repo that clearly had more.

**Discovery:** Read `ui/pages/input_page.py`'s clone-and-scan flow and found `_run_phase1` built `user_input=" ".join(files)` — every discovered file path concatenated into one string — while separately pre-populating `target_files` with the correct list. Reproduced the exact flow against a real clone: `parser_node` ran first, ignored the pre-populated `target_files` entirely, tried to resolve the ~7,000-character garbled string as a path, failed, and fell back to asking an LLM to interpret it — which returned a guess that resolved against the wrong working directory.

**Root Cause:** `parser_node` unconditionally re-derives `target_files` from `user_input` on every run — it has no way to know a caller already resolved the correct file list, so it always overwrites it, even when the input state already had the right answer.

**Fix:** `parser_node` now checks for a pre-populated `target_files` first and trusts it as-is when present, skipping path re-resolution entirely. For the GitHub-URL clone flow specifically, changed `_run_phase1` to pass `user_input=scan_path` (the actual cloned directory) instead of the joined file-path string, so the parser does its own correct recursive walk. (`agents/parser.py`, `ui/pages/input_page.py`)

**Metric:** Before → 3 files (an LLM guess resolved against the wrong `cwd`, not even the target repo). After → verified via `AppTest` against a real clone: 127 total files found, 115 matching supported extensions, 30 scanned (respecting `MAX_FILES_LIMIT`), with `commit_sha` correctly matching the cloned repo's actual HEAD.

**30-second interview version:** "A user reported the parser only found 3 files scanning a repo that obviously had more. I traced it to the UI's clone flow: it correctly discovered all the files, but then passed them to the graph by joining every single file path into one giant space-separated string as `user_input`, while separately setting `target_files` to the correct list. The problem is the parser node always re-derives `target_files` from `user_input` — it has no way to know the caller already did that work — so it threw away the correct list, failed to parse the 7,000-character garbled string as a path, and fell back to asking an LLM to guess a path from it. That guess resolved against the wrong working directory entirely — it was silently scanning the wrong repository. I fixed it two ways: the parser now trusts a pre-populated file list when one exists, and the clone flow passes the actual cloned directory path instead of a mangled string, so the parser can do a real, correct directory walk. I verified the fix by actually cloning the project into a temp directory and confirming the commit hash in the trace matched the real clone, not a coincidence."

---

## Scar 8: Preview count mismatch

**Situation:** While fixing Scar 7, noticed `_clone_repo`'s "Cloned! Found N files" preview count used its own hardcoded list of extensions, separate from `config.SUPPORTED_EXTENSIONS`.

**Discovery:** Compared the two lists directly: `_clone_repo`'s glob covered `*.py, *.md, *.txt, *.yml, *.yaml, *.env` — missing `.json`, `.sql`, `.js`, `.jsx`, `.ts`, `.tsx` entirely. Cloning the project itself and counting: the real `SUPPORTED_EXTENSIONS` walk found 115 matching files; the old preview glob found only 87 — 28 real files invisible to the preview, including every `.json`/`.js`/`.sql` file in the repo.

**Root Cause:** Two independent, hand-maintained extension lists for the same conceptual filter, guaranteed to drift the moment one was updated (which happened exactly once, when SQL/JS/JSON router support was added to `config.SUPPORTED_EXTENSIONS` but not to `_clone_repo`).

**Fix:** `_clone_repo`'s preview now imports and uses `config.SUPPORTED_EXTENSIONS` directly instead of maintaining a second list. (`ui/pages/input_page.py`)

**Metric:** Before → 87 files in the preview count (missing 28 real matches). After → preview count matches what the parser will actually scan.

**30-second interview version:** "This came up as a side effect of debugging the parser bug — I noticed the 'files found' preview count after cloning used its own separate, hardcoded extension list instead of the single source of truth in config.py. When Phase 1 added SQL/JS/JSON support to the real extension list, nobody updated this second copy, so the preview silently under-reported by 28 files — every JSON, JS, and SQL file in the repo. It's a classic duplicated-constant bug: the fix was just deleting the second list and importing the real one, but the actual lesson is that any filter or config value that matters should have exactly one definition, because two copies of the same rule will drift the first time only one of them gets updated."

---

## Scar 9: Windows charmap encoding

**Situation:** Ruff scans of certain Python files failed with `'charmap' codec can't encode character '✅' (...): character maps to <undefined>` instead of returning lint results.

**Discovery:** Traced the exact failing content to `test_repo/src/smoke_test.py`'s `print("\n✅ Smoke test passed...")` line. Reproduced it directly by calling the Ruff MCP driver on that file's content in isolation — confirmed the crash was coming from the MCP server subprocess itself, not from RepoGuard's own file reading (which already used `encoding="utf-8"`).

**Root Cause:** On Windows, a spawned Python subprocess's stdio streams default to the console codepage (cp1252, i.e. "charmap") rather than UTF-8 unless explicitly told otherwise. Any content containing characters outside cp1252 — emoji, arrows, smart quotes — crashes the subprocess trying to encode its own output. This wasn't limited to Ruff: `js_server.py` and `json_server.py` each separately shell out to `eslint`/`ajv`/`spectral` via `subprocess.run(..., text=True)` with no explicit `encoding=`, decoding with the same OS locale default.

**Fix:** Two layers. First, `BaseMCPDriver.__init__` now forces `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` in the environment of every subprocess it spawns — a single fix covering all four MCP servers (Ruff via `uvx`, plus the SQL/JS/JSON servers), since they all extend this base class. Second, `js_server.py`'s and `json_server.py`'s own internal `subprocess.run()` calls to `eslint`/`ajv`/`spectral` were given explicit `encoding="utf-8", errors="replace"` — a second-layer instance of the identical bug, one level deeper, that the first fix didn't reach. (`mcp_drivers/base_driver.py`, `mcp_servers/js_server.py`, `mcp_servers/json_server.py`)

**Metric:** Before → hard crash (`RUFF_TOOL_ERROR`) on any file with non-cp1252 characters, zero findings returned. After → real findings returned correctly; verified with a dedicated fixture (`tests/fixtures/python_unicode/emoji.py`, containing both an emoji/arrow string and a genuine unused-import bug) and a regression test asserting the real `F401` finding appears with no crash-shaped finding present.

**30-second interview version:** "Ruff was crashing on certain Python files with a codec error trying to encode a checkmark emoji — 'charmap can't encode character.' Charmap is cp1252, Windows' default console encoding, and it can't represent most Unicode. The root cause is that a spawned subprocess's stdio streams default to that codepage unless you explicitly force UTF-8, and any file with an emoji, arrow, or smart quote in it would crash the MCP server trying to encode its own output — this had nothing to do with how we were reading files, since that already used UTF-8. The real fix was setting `PYTHONUTF8=1` in the subprocess environment at the one shared base class every MCP driver extends, so it covered all four tools — Ruff, sqlfluff, ESLint, and the JSON tools — with a single change. But I didn't stop there: since the JS and JSON servers each spawn their *own* inner subprocesses for eslint/ajv/spectral, I checked those too and found the identical bug one layer deeper, in calls that decode subprocess output without an explicit encoding. Fixed those the same way, and added a regression test with a fixture file that deliberately contains both an emoji and a real bug, asserting we get the real finding, not a crash."

---

## Patterns

Themes that show up across more than one of these:

- **Silent false negatives are worse than crashes.** Scars 4, 5, and 7 all returned a plausible-looking empty or wrong result instead of erroring — a crash gets noticed immediately; a quiet zero, or a quietly-wrong repo, doesn't. Every one of these was caught by a test or check that happened to compare against a known-correct expectation, not by the tool complaining about itself.
- **Fix at the right abstraction layer, not the symptom.** Scar 1's real fix was architectural (call-boundary logging, not stream patching); Scar 9's fix lived in one shared base class so it covered four tools at once, and then required a second pass to check whether the same class of bug existed one layer deeper (it did). Patching the first symptom you find is rarely the same as fixing the actual cause.
- **Windows compatibility is a real, recurring concern.** Scars 4, 5, 6, and 9 are all, at root, "this tool has an undocumented assumption that only breaks on Windows or outside a specific working directory." None of these would have been caught by only testing on the machine and in the directory where the code was written.
- **Write the test that would have caught it.** Every scar here ended with either a new regression test or a new isolated-tool test that didn't exist before — Scars 4 and 5 were *found* specifically because a new MCP integration test used a `tmp_path` outside the project root instead of an in-repo fixture. The test that catches a bug is usually the test that varies the one assumption nobody thought to question.
