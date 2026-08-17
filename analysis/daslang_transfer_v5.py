#!/usr/bin/env python3
import collections, importlib.util, json, pathlib, re, subprocess
here=pathlib.Path(__file__).parent
spec=importlib.util.spec_from_file_location('base',here/'daslang_transfer.py')
b=importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
REPO=b.REPO; OUT=b.OUT; TARGET=b.TARGET

fmt='%x1e%H%x1f%cI%x1f%s%x1f%b%x1d'
grep='fix|bug|crash|wrong|incorrect|regression|ice|assert|hang|miscompil|issue|PR'
p=subprocess.run(['git','-C',str(REPO),'log','--extended-regexp','--regexp-ignore-case',f'--grep={grep}',f'--format={fmt}','--name-only'],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
if p.returncode: raise SystemExit(p.stderr)

def core_test(path):
    l=path.lower()
    return (l.startswith('tests/') or l.startswith('tests-cpp/')) and path.endswith(('.das','.cpp','.h'))

def core_impl(path):
    l=path.lower()
    if l.startswith(('tests/','tests-cpp/','3rdparty/')): return False
    if not path.endswith(('.cpp','.cc','.c','.h','.das')): return False
    return l.startswith(('src/','include/dascript/','daslib/'))

def score_labels(row):
    text=(row['title']+'\n'+row['message']).lower(); paths=' '.join(row['source_files']).lower(); out=[]
    for lab,mp,pp in b.RULES:
        # message match is stronger evidence than implementation path.
        s=sum(2 for q in mp if re.search(q,text))+sum(1 for q in pp if re.search(q,paths))
        if s: out.append((s,lab))
    out.sort(reverse=True)
    return out

all_rows=[]; rej=collections.Counter(); candidate_count=0
for rec in p.stdout.split('\x1e'):
    if '\x1d' not in rec: continue
    meta,names_blob=rec.split('\x1d',1); fields=meta.split('\x1f',3)
    if len(fields)!=4: continue
    sha,date,title,body=(x.strip() for x in fields); msg=(title+'\n'+body).strip()
    if not b.BUG.search(msg): rej['broad_git_match_only']+=1; continue
    candidate_count+=1
    names=[x.strip() for x in names_blob.splitlines() if x.strip()]
    tests=[x for x in names if core_test(x)]; impl=[x for x in names if core_impl(x)]
    if not tests: rej['no_core_regression_test']+=1; continue
    if not impl: rej['no_core_implementation_change']+=1; continue
    row={'sha':sha,'date':date,'title':title,'message':msg,'url':f'https://github.com/GaijinEntertainment/daScript/commit/{sha}','tests':tests,'source_files':impl}
    scored=score_labels(row); row['taxonomy_scores']=[{'label':l,'score':s} for s,l in scored[:5]]
    row['loose_label']=scored[0][1] if scored else None
    row['strict_label']=scored[0][1] if scored and scored[0][0]>=3 else None
    all_rows.append(row)

# Do not bias toward the current AI-heavy era.  If there are more than TARGET,
# take evenly spaced points through chronological history.
all_rows.sort(key=lambda r:(r['date'],r['sha']))
if len(all_rows)>TARGET:
    idx=[]
    for i in range(TARGET): idx.append(round(i*(len(all_rows)-1)/(TARGET-1)))
    rows=[all_rows[i] for i in idx]
else: rows=all_rows

loose=collections.Counter(r['loose_label'] for r in rows if r['loose_label']); strict=collections.Counter(r['strict_label'] for r in rows if r['strict_label'])
strict_n=sum(r['strict_label'] is not None for r in rows); loose_n=sum(r['loose_label'] is not None for r in rows)
parent_strict=collections.Counter(b.TAXONOMY[r['strict_label']][0] for r in rows if r['strict_label'])
res={'target':TARGET,'core_bugfix_regressions_available':len(all_rows),'sampled':len(rows),'history_start':rows[0]['date'] if rows else None,'history_end':rows[-1]['date'] if rows else None,'candidate_commits_scanned':candidate_count,'reject_counts':dict(rej),
     'loose_covered':loose_n,'loose_coverage':loose_n/len(rows) if rows else 0,
     'strict_covered':strict_n,'strict_coverage':strict_n/len(rows) if rows else 0,
     'strict_unmatched':len(rows)-strict_n,'strict_leaf_counts':dict(strict.most_common()),'strict_parent_counts':dict(parent_strict.most_common()),
     'strict_definition':'top semantic mapping score >=3; message term match=2, implementation-path match=1; no new taxonomy leaves permitted',
     'sampling':'evenly spaced across chronological core compiler/runtime history when available cases exceed target'}
(OUT/'daslang_core_regressions.json').write_text(json.dumps(rows,indent=2),encoding='utf8'); (OUT/'daslang_core_transfer.json').write_text(json.dumps(res,indent=2),encoding='utf8'); print(json.dumps(res,indent=2))
