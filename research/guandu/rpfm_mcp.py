#!/usr/bin/env python3
"""Minimal client for the RPFM MCP server (Streamable HTTP at 127.0.0.1:45127/mcp).

Usage: python rpfm_mcp.py TOOL '{"arg": ...}'   -- keeps one session in output/mcp_session.txt (sessions expire
after 5 minutes idle; a stale one is replaced automatically). Prints the tool's text result.
"""
import json, sys, urllib.request, pathlib

URL = "http://127.0.0.1:45127/mcp"
SESSION = pathlib.Path(r"Z:/Claude/TerryClone/output/mcp_session.txt")


def post(body, sid=None, timeout=3600):
    h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if sid: h["mcp-session-id"] = sid
    req = urllib.request.Request(URL, json.dumps(body).encode(), h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        sid = r.headers.get("mcp-session-id") or sid
        text = r.read().decode("utf-8", "replace")
    msgs = [json.loads(l[6:]) for l in text.splitlines() if l.startswith("data: ") and l[6:].strip()]
    if not msgs and text.strip().startswith("{"): msgs = [json.loads(text)]
    return sid, msgs


def session():
    if SESSION.exists():
        sid = SESSION.read_text().strip()
        try:
            _, m = post({"jsonrpc": "2.0", "id": 0, "method": "tools/call",
                         "params": {"name": "get_game_selected", "arguments": {}}}, sid, 30)
            if m and "error" not in m[-1]: return sid
        except Exception:
            pass
    sid, _ = post({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "claude", "version": "1"}}})
    post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
    SESSION.write_text(sid)
    return sid


def call(name, args=None, timeout=3600):
    sid = session()
    _, m = post({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": name, "arguments": args or {}}}, sid, timeout)
    res = m[-1] if m else {}
    if "error" in res: return "ERROR: " + json.dumps(res["error"])
    r = res.get("result", {})
    out = "\n".join(c.get("text", "") for c in r.get("content", []))
    return ("TOOL ERROR: " if r.get("isError") else "") + out


if __name__ == "__main__":
    print(call(sys.argv[1], json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}))
