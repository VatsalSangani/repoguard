"""JSON-RPC call logging for MCP stdio connections.

Originally implemented by wrapping the raw `anyio.MemoryObjectStream` pair
returned by `stdio_client()` with forwarder tasks that snoop on each
`JSONRPCMessage`. That approach deadlocked: `mcp.ClientSession` requires the
concrete `anyio.streams.memory.MemoryObjectReceiveStream` /
`MemoryObjectSendStream` types (not just duck-typed objects), and interposing
a second unbuffered stream pair + forwarding task group in front of them is
fragile — it hung at the `initialize` handshake in testing, both with and
without a warm `uvx` cache, while the identical call sequence against the
raw `stdio_client` streams completed instantly.

Instead, this module logs at the RPC call boundary: every `initialize`,
`tools/list`, and `tools/call` invocation made through `WireLogger.logged()`
is wrapped with a request line (method, params, id, timestamp) before the
call and a response line (result|error, id, latency_ms) after it — the same
fields the wire-level approach would have captured, without touching the
transport's stream plumbing.

Each line is appended as JSON to `logs/{run_id}/mcp_wire.jsonl`.
"""

import json
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")


def _safe(value: Any) -> Any:
    """Best-effort JSON-serializable form of a pydantic model / plain value."""
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    return value


def _log_path(run_id: str) -> Path:
    path = Path("logs") / run_id / "mcp_wire.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _append_jsonl(path: Path, entry: dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")


class WireLogger:
    """Logs one request/response JSONL pair per MCP RPC call."""

    def __init__(self, run_id: str, server_name: str) -> None:
        self.run_id = run_id
        self.server_name = server_name
        self._next_id = 0
        self._log_path = _log_path(run_id)

    def _next_msg_id(self) -> int:
        self._next_id += 1
        return self._next_id

    async def logged(self, method: str, params: dict, call: Callable[[], Awaitable[T]]) -> T:
        """Run `call()`, logging a request line before and a response line
        after — with the real method/params/id/timestamp and
        result|error/latency_ms."""
        msg_id = self._next_msg_id()
        sent_at = time.time()
        _append_jsonl(self._log_path, {
            "server": self.server_name,
            "direction": "request",
            "method": method,
            "params": _safe(params),
            "id": msg_id,
            "timestamp": sent_at,
        })
        try:
            result = await call()
        except Exception as exc:
            _append_jsonl(self._log_path, {
                "server": self.server_name,
                "direction": "response",
                "result": None,
                "error": str(exc),
                "id": msg_id,
                "latency_ms": int((time.time() - sent_at) * 1000),
            })
            raise

        _append_jsonl(self._log_path, {
            "server": self.server_name,
            "direction": "response",
            "result": _safe(result),
            "error": None,
            "id": msg_id,
            "latency_ms": int((time.time() - sent_at) * 1000),
        })
        return result
