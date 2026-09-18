"""Minimal Grok ACP client (stdio), same transport raccoon-herder uses."""

from __future__ import annotations

import json
import logging
import select
import subprocess
import threading
import time
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

EventFn = Callable[[str, str, dict[str, Any]], None]


def _rpc(method: str, params: dict[str, Any], rpc_id: int) -> str:
    return json.dumps(
        {"jsonrpc": "2.0", "id": rpc_id, "method": method, "params": params},
        separators=(",", ":"),
    ) + "\n"


def _result(rpc_id: int | str, result: dict[str, Any]) -> str:
    return json.dumps(
        {"jsonrpc": "2.0", "id": rpc_id, "result": result},
        separators=(",", ":"),
    ) + "\n"


def _content_text(raw: Any) -> str:
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        if isinstance(raw.get("text"), str):
            return raw["text"]
        inner = raw.get("content")
        if inner is not None and inner is not raw:
            return _content_text(inner)
        return ""
    if isinstance(raw, list):
        return "".join(_content_text(part) for part in raw)
    return ""


def format_acp_event(kind: str, text: str, extra: dict[str, Any] | None = None) -> str:
    extra = extra or {}
    if kind == "thinking":
        return f"thinking {text}".strip()
    if kind == "tool":
        name = extra.get("name") or "tool"
        status = extra.get("status") or ""
        return f"tool {name} {status} {text}".strip()
    if kind == "assistant":
        return text
    if kind == "status":
        return f"status {text}".strip()
    return f"{kind} {text}".strip()


class AcpGrokSession:
    """One `grok agent --always-approve stdio` child for a CMS generate job."""

    def __init__(
        self,
        grok_bin: str,
        *,
        cwd: str,
        on_event: EventFn,
        timeout_s: int = 3600,
        model: str = "",
    ) -> None:
        self._bin = grok_bin
        self._cwd = cwd
        self._on_event = on_event
        self._timeout_s = timeout_s
        self._model = model
        self._proc: subprocess.Popen[str] | None = None
        self._buf = ""
        self._next_id = 1
        self._deadline = 0.0

    def run_prompt(self, text: str) -> None:
        cmd = [self._bin, "agent", "--always-approve"]
        if self._model:
            cmd.extend(["--model", self._model])
        cmd.append("stdio")
        self._on_event("status", "Starting grok agent stdio (ACP)…", {})
        self._proc = subprocess.Popen(  # noqa: S603 — grok_bin from config
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=self._cwd,
        )
        assert self._proc.stdin is not None
        assert self._proc.stdout is not None
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        self._deadline = time.monotonic() + self._timeout_s
        try:
            init = self._request(
                "initialize",
                {
                    "protocolVersion": 1,
                    "clientInfo": {"name": "agent-news-cms", "version": "0.1"},
                    "clientCapabilities": {
                        "fs": {"readTextFile": False, "writeTextFile": False},
                        "terminal": False,
                    },
                },
            )
            if init.get("error"):
                raise RuntimeError(f"ACP initialize failed: {init['error']}")
            created = self._request(
                "session/new",
                {
                    "cwd": self._cwd,
                    "mcpServers": [],
                    "_meta": {"yoloMode": True},
                },
            )
            if created.get("error"):
                raise RuntimeError(f"ACP session/new failed: {created['error']}")
            result = created.get("result") or {}
            session_id = result.get("sessionId")
            if not isinstance(session_id, str) or not session_id:
                raise RuntimeError(f"ACP session/new missing sessionId: {result!r}")
            self._on_event("status", f"ACP session {session_id[:8]}…", {"session_id": session_id})
            prompted = self._request(
                "session/prompt",
                {
                    "sessionId": session_id,
                    "prompt": [{"type": "text", "text": text}],
                },
            )
            if prompted.get("error"):
                raise RuntimeError(f"ACP session/prompt failed: {prompted['error']}")
            self._on_event("status", "ACP turn complete", {})
        finally:
            self.close()

    def close(self) -> None:
        proc = self._proc
        if proc is None:
            return
        if proc.poll() is None:
            try:
                if proc.stdin:
                    proc.stdin.close()
            except OSError:
                pass
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        self._proc = None

    def _drain_stderr(self) -> None:
        proc = self._proc
        if proc is None or proc.stderr is None:
            return
        for line in proc.stderr:
            text = line.strip()
            if text:
                self._on_event("status", text[:500], {"stream": "stderr"})

    def _write(self, payload: str) -> None:
        proc = self._proc
        if proc is None or proc.stdin is None:
            raise RuntimeError("ACP child has no stdin")
        proc.stdin.write(payload)
        proc.stdin.flush()

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        rpc_id = self._next_id
        self._next_id += 1
        self._write(_rpc(method, params, rpc_id))
        while True:
            msg = self._read_message()
            if msg.get("method") == "session/request_permission":
                self._allow_permission(msg)
                continue
            if msg.get("method") in {
                "session/update",
                "_x.ai/session/update",
                "x.ai/session_notification",
            }:
                self._handle_update(msg)
                continue
            if msg.get("id") == rpc_id:
                return msg
            if msg.get("method"):
                continue

    def _allow_permission(self, msg: dict[str, Any]) -> None:
        rpc_id = msg.get("id")
        if rpc_id is None:
            return
        params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
        options = params.get("options") if isinstance(params, dict) else []
        option_id = ""
        if isinstance(options, list):
            for opt in options:
                if not isinstance(opt, dict):
                    continue
                kind = str(opt.get("kind") or opt.get("optionId") or "").lower()
                oid = str(opt.get("optionId") or "")
                if "allow" in kind or oid.startswith("allow"):
                    option_id = oid
                    break
            if not option_id and options and isinstance(options[0], dict):
                option_id = str(options[0].get("optionId") or "")
        self._write(
            _result(
                rpc_id,
                {"outcome": {"outcome": "selected", "optionId": option_id or "allow-once"}},
            )
        )

    def _handle_update(self, msg: dict[str, Any]) -> None:
        params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
        update = params.get("update") if isinstance(params, dict) else None
        if not isinstance(update, dict):
            method = str(msg.get("method") or "")
            if method.endswith("session_notification") and isinstance(params, dict):
                update = params
            else:
                return
        kind = str(update.get("sessionUpdate") or "")
        if kind == "agent_message_chunk":
            text = _content_text(update.get("content"))
            if text:
                self._on_event("assistant", text, {})
            return
        if kind == "agent_thought_chunk":
            text = _content_text(update.get("content"))
            if text:
                self._on_event("thinking", text, {})
            return
        if kind == "tool_call":
            name = str(update.get("title") or update.get("kind") or "tool")
            status = str(update.get("status") or "running")
            self._on_event(
                "tool",
                _content_text(update.get("rawInput") or update.get("locations") or "")[:300],
                {"name": name, "status": status, "id": update.get("toolCallId")},
            )
            return
        if kind == "tool_call_update":
            name = str(update.get("title") or update.get("kind") or "tool")
            status = str(update.get("status") or "")
            self._on_event(
                "tool",
                _content_text(update.get("content") or update.get("rawOutput") or "")[:400],
                {"name": name, "status": status, "id": update.get("toolCallId")},
            )
            return
        if kind == "plan":
            self._on_event("status", "plan updated", {})

    def _read_message(self) -> dict[str, Any]:
        proc = self._proc
        if proc is None or proc.stdout is None:
            raise RuntimeError("ACP child has no stdout")
        while True:
            if time.monotonic() > self._deadline:
                raise RuntimeError("ACP grok timed out")
            if proc.poll() is not None and not self._buf:
                rest = proc.stdout.read() or ""
                if rest:
                    self._buf += rest
                else:
                    raise RuntimeError(f"grok agent stdio exited {proc.returncode}")
            ready, _, _ = select.select([proc.stdout], [], [], 0.5)
            if ready:
                chunk = proc.stdout.readline()
                if chunk:
                    self._buf += chunk
            nl = self._buf.find("\n")
            if nl < 0:
                continue
            line, self._buf = self._buf[:nl], self._buf[nl + 1 :]
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                self._on_event("status", line[:400], {"stream": "stdout"})
                continue
            if isinstance(obj, dict):
                return obj
