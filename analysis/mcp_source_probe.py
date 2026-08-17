#!/usr/bin/env python3
import json, os, subprocess, threading, queue, time
bundle=os.environ.get('CPP_MCP_BUNDLE','/tmp/cpp-mcp/cpp-mcp')
target=os.environ.get('DAS_TARGET','/tmp/dascript/src/ast/ast.cpp')
exe=os.path.join(bundle,'bin','cpp-mcp')
p=subprocess.Popen([exe,'--root',bundle],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
q=queue.Queue()
def rd():
  for line in p.stdout:
    line=line.strip()
    if line:
      try:q.put(json.loads(line))
      except:q.put({'raw':line})
threading.Thread(target=rd,daemon=True).start()
def send(x):p.stdin.write(json.dumps(x,separators=(',',':'))+'\n');p.stdin.flush()
def wait(i,t=20):
  end=time.time()+t
  while time.time()<end:
    try:m=q.get(timeout=.2)
    except queue.Empty:continue
    if m.get('id')==i:return m
  raise TimeoutError(i)
send({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'semantic-invariants-source-probe','version':'0.1'}}})
print('INIT',json.dumps(wait(1)))
send({'jsonrpc':'2.0','method':'notifications/initialized','params':{}})
send({'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}}); tools=wait(2)
items=(tools.get('result') or {}).get('tools') or []
print('SOURCE_TOOLS',[x.get('name') for x in items])
for x in items:
  if x.get('name') in ('cpp_outline','outline','cpp_find_symbol','grep_usage'):
    print('SCHEMA',x['name'],json.dumps(x.get('inputSchema'),sort_keys=True))
outline=next((x for x in items if x.get('name') in ('cpp_outline','outline')),None)
if outline:
  props=(outline.get('inputSchema') or {}).get('properties') or {}
  args={}
  if 'file' in props:args['file']=target
  elif 'path' in props:args['path']=target
  if 'json' in props:args['json']='true'
  send({'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':outline['name'],'arguments':args}})
  ans=wait(3,30)
  print('OUTLINE_RESULT',json.dumps(ans)[:12000])
else:
  print('NO_OUTLINE_TOOL')
p.terminate()
