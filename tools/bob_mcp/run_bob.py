#!/usr/bin/env python3
"""Command-line use of the bob MCP server's guarded single-action runner, with a selectable kit.

  python run_bob.py --ak <assembly kit root> <path> <action name> [--timeout s] [--label capture_label] [--no-filter]

Same safety as bob_run_action (headless): scope validation, file filter, and the bob.log guard that kills BOB if
anything other than exactly one matching action starts. Prints the result as JSON.
"""
import argparse, json, os, sys

ap = argparse.ArgumentParser()
ap.add_argument("--ak", required=True); ap.add_argument("path"); ap.add_argument("action")
ap.add_argument("--timeout", type=int, default=3600); ap.add_argument("--label"); ap.add_argument("--no-filter", action="store_true")
a = ap.parse_args()
os.environ["BOB_AK"] = a.ak                                   # before bobgui is imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server
res = server.bob_run_action.fn(a.path, a.action, timeout=a.timeout, capture_label=a.label, file_filter=not a.no_filter) \
    if hasattr(server.bob_run_action, "fn") else server.bob_run_action(a.path, a.action, timeout=a.timeout,
                                                                       capture_label=a.label, file_filter=not a.no_filter)
print(json.dumps(res, indent=1, default=str))
