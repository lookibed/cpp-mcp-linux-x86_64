#!/usr/bin/env python3
import json, os, subprocess, sys, threading, queue, time

bundle = os.environ.get("CPP_MCP_BUNDLE", "/tmp/cpp-mcp/cpp-mcp")
exe = os.path.join(bundle, "bin", "cpp-mcp")
proc = subprocess.Popen([exe, "--root", bundle], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, text=True, bufsize=1)
q = queue.Queue()

def reader():
    for line in proc.stdout:
        line=line.strip()
        if line:
            try:q.put(json.loads(line))
            except Exception:q.put({"raw":line})
threading.Thread(target=reader, daemon=True).start()

def send(obj):
    proc.stdin.write(json.dumps(obj,separators=(",",":"))+"\n")
    proc.stdin.flush()

def wait_id(i, timeout=20):
    end=time.time()+timeout
    stash=[]
    while time.time()<end:
        try:m=q.get(timeout=.2)
        except queue.Empty:continue
        if m.get("id")==i:
            for x in stash:q.put(x)
            return m
        stash.append(m)
    raise TimeoutError(i)

send({"jsonrpc":"2.0","id":1,"method":"initialize","params":{
    "protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"semantic-invariants-probe","version":"0.1"}}})
init=wait_id(1)
print("INITIALIZE", json.dumps(init, indent=2))
send({"jsonrpc":"2.0","method":"notifications/initialized","params":{}})
send({"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}})
tools=wait_id(2)
print("TOOLS", json.dumps(tools, indent=2))

# Call cpp_status if advertised, with no args; this reveals dependency state and validates calls.
items=((tools.get("result") or {}).get("tools") or [])
if any(t.get("name")=="cpp_status" for t in items):
    send({"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"cpp_status","arguments":{}}})
    print("CPP_STATUS", json.dumps(wait_id(3), indent=2))

proc.terminate()
try: proc.wait(timeout=5)
except subprocess.TimeoutExpired: proc.kill()
