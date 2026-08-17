#!/usr/bin/env python3
# Wrapper around the frozen-taxonomy mapper.  The first version used a basic-regex
# git --grep with literal | characters; discover candidates from all subjects instead.
import importlib.util, pathlib
p=pathlib.Path(__file__).with_name('daslang_transfer.py')
s=importlib.util.spec_from_file_location('base',p)
m=importlib.util.module_from_spec(s); s.loader.exec_module(m)

def candidates():
    raw=m.git('log','--format=%ct%x00%H%x00%s')
    arr=[]
    for line in raw.splitlines():
        z=line.split('\x00',2)
        if len(z)==3 and m.BUG.search(z[2]):
            arr.append((int(z[0]),z[1],z[2]))
    arr.sort(reverse=True)
    return arr
m.candidates=candidates
m.main()
