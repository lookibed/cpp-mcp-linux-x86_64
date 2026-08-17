#!/usr/bin/env python3
import collections, importlib.util, json, os, pathlib, subprocess

here=pathlib.Path(__file__).parent
spec=importlib.util.spec_from_file_location('base',here/'daslang_transfer.py')
b=importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
REPO=b.REPO; OUT=b.OUT; TARGET=b.TARGET

# One git process for the complete commit metadata + changed filenames.
fmt='%x1e%H%x1f%cI%x1f%s%x1f%b%x1d'
p=subprocess.run(['git','-C',str(REPO),'log',f'--format={fmt}','--name-only'],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
if p.returncode: raise SystemExit(p.stderr)

rows=[]; rej=collections.Counter(); candidates=0
for rec in p.stdout.split('\x1e'):
    if '\x1d' not in rec: continue
    meta,names_blob=rec.split('\x1d',1)
    f=meta.split('\x1f',3)
    if len(f)!=4: continue
    sha,date,title,body=(x.strip() for x in f)
    msg=(title+'\n'+body).strip()
    if not b.BUG.search(msg): continue
    candidates+=1
    names=[x.strip() for x in names_blob.splitlines() if x.strip()]
    tests=[x for x in names if b.is_test(x)]
    impl=[x for x in names if b.is_impl(x)]
    if not tests: rej['no_regression_test_file']+=1; continue
    if not impl: rej['test_only_or_nonimplementation']+=1; continue
    row={'sha':sha,'date':date,'title':title,'message':msg,
         'url':f'https://github.com/GaijinEntertainment/daScript/commit/{sha}',
         'tests':tests,'source_files':impl}
    row['c_taxonomy_labels']=b.labels(row)
    rows.append(row)
    if len(rows)>=TARGET: break

rows.sort(key=lambda r:(r['date'],r['sha']))
cnt=collections.Counter(l for r in rows for l in r['c_taxonomy_labels'])
covered=sum(bool(r['c_taxonomy_labels']) for r in rows)
parents=collections.Counter()
for r in rows:
    for par in set(b.TAXONOMY[l][0] for l in r['c_taxonomy_labels']): parents[par]+=1
result={'target':TARGET,'accepted':len(rows),'candidate_commits_scanned':candidates,'reject_counts':dict(rej),
        'covered_by_frozen_c_taxonomy':covered,'coverage':covered/len(rows) if rows else 0,
        'unmatched':len(rows)-covered,'leaf_occurrences':dict(cnt.most_common()),
        'parent_occurrences':dict(parents.most_common()),
        'method':'One-pass historical daScript scan; bug-signalled commits must change regression-like tests and implementation files; mapping uses the frozen C semantic taxonomy.'}
(OUT/'daslang_regressions.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
(OUT/'daslang_transfer.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps(result,indent=2))
