#!/usr/bin/env python3
import collections, json, os, re, subprocess
from pathlib import Path

REPO=Path(os.environ.get('DAS_REPO','/tmp/dascript'))
OUT=Path(os.environ.get('OUT_DIR','analysis/out')); OUT.mkdir(parents=True,exist_ok=True)
TARGET=int(os.environ.get('TARGET','350'))

# Frozen BEFORE target mining: identical semantic leaves used in the C experiment.
TAXONOMY={
 'frontend_tokens':('Frontend','Tokenization, preprocessing, attributes and parsing must preserve the language-defined token and declaration structure.'),
 'types_conversions':('Frontend','Type identity, qualifiers, promotions, casts and conversion domains must match the source-language type rules.'),
 'integer_arithmetic':('Value semantics','Integer transforms must preserve width, signedness, overflow, shift and bit-level value semantics under their proven preconditions.'),
 'floating_point':('Value semantics','Floating-point transforms must preserve IEEE/target-observable values, NaNs, infinities, signed zero and rounding assumptions required by the active mode.'),
 'memory_object':('Object model','Loads, stores and rewrites must preserve object identity, alias/provenance, access width, alignment, layout and storage-order semantics.'),
 'lifetime_init':('Object model','Initialization, lifetime, storage duration and destruction boundaries must not be moved across points where program observability changes.'),
 'control_dataflow':('IR semantics','CFG/SSA rewrites must preserve reachability, dominance, value availability and PHI/edge meaning.'),
 'loops':('IR semantics','Loop transforms must preserve trip counts, induction values, exits and loop-carried dependencies.'),
 'vectorization':('IR semantics','Vectorization must be lane-wise equivalent to scalar execution, including masks, reductions, early exits and inactive lanes.'),
 'calls_abi':('ABI','Calls, returns, parameters, varargs, calling conventions and aggregate passing must preserve the target ABI and source-level value contract.'),
 'builtins_intrinsics':('Lowering','Builtins, intrinsics and language extensions must lower only when their specified preconditions hold and must preserve their documented semantics.'),
 'target_codegen':('Code generation','Target instruction selection and machine lowering must preserve the abstract value and target architectural constraints.'),
 'rtl_registers':('Code generation','RTL simplification, liveness, reload and register allocation must preserve live values, modes and operand constraints.'),
 'concurrency_volatile':('Effects','Atomic, volatile and synchronization transforms must preserve required accesses, ordering and inter-thread observable effects.'),
 'interprocedural_lto':('Whole program','Inlining, IPA, LTO and symbol transforms must preserve linkage, visibility, identity and cross-unit call semantics.'),
 'diagnostics_robustness':('Robustness','Valid programs must not ICE/hang and invalid programs must be diagnosed or rejected without corrupting compiler state.'),
 'instrumentation':('Instrumentation','Sanitizers, profiling and instrumentation must preserve permitted program semantics while adding only their specified observations.'),
 'parallel_offload':('Parallel semantics','Parallel/offload transforms must preserve region, data-sharing, mapping, synchronization and execution semantics.'),
}

# Same conceptual mapping as C, extended only with Daslang vocabulary aliases; NO new semantic leaves.
RULES=[
 ('parallel_offload',[r'jobque|thread|parallel|offload|gpu|compute shader'],[r'jobque|thread|gpu|spirv|metal|vulkan']),
 ('vectorization',[r'vector|simd|lane|mask|swizzle'],[r'vector|simd']),
 ('floating_point',[r'float|double|nan|infinity|signed zero|rounding'],[r'float|math']),
 ('concurrency_volatile',[r'atomic|volatile|memory order|lock|race|thread'],[r'atomic|thread|jobque']),
 ('instrumentation',[r'sanitiz|profil|coverage|debug info|instrument'],[r'profiler|debug|instrument']),
 ('interprocedural_lto',[r'inline|visibility|aot|jit|symbol|mangle|link'],[r'aot|jit|llvm|mangle|symbol']),
 ('rtl_registers',[r'register|liveness|stack walk|frame|spill|reload'],[r'register|stack|frame']),
 ('target_codegen',[r'codegen|llvm|spir-v|spirv|metal|vulkan|wasm|x86|arm|aarch64|instruction|backend'],[r'codegen|llvm|spirv|metal|vulkan|wasm']),
 ('builtins_intrinsics',[r'builtin|intrinsic|annotation|macro|operator overload'],[r'builtin|macro|annotation']),
 ('calls_abi',[r'abi|calling convention|argument|return value|invoke|call node|function pointer|interop'],[r'call|interop|abi']),
 ('memory_object',[r'alias|pointer|reference|load|store|alignment|layout|heap|gc|memory|address|smart_ptr'],[r'heap|gc|memory|pointer|simulate']),
 ('lifetime_init',[r'lifetime|initializ|constructor|destructor|finaliz|uninitialized|move|clone'],[r'init|final|construct|simulate']),
 ('loops',[r'loop|iterator|iteration|break|continue'],[r'loop|iterator']),
 ('control_dataflow',[r'phi|dominance|cfg|edge|reachab|branch|if |block|goto|yield|defer'],[r'ast|simulate|infer|fold']),
 ('integer_arithmetic',[r'overflow|signed|unsigned|shift|rotate|bitwise|integer|bitfield|multiply|division|modulo'],[r'math|bit|fold']),
 ('types_conversions',[r'type|convert|conversion|cast|qualifier|enum|variant|tuple|handle|generic|infer'],[r'type|infer|ast_typedecl']),
 ('frontend_tokens',[r'parser|parse|lexer|token|syntax|macro|annotation'],[r'parser|parse|lexer']),
 ('diagnostics_robustness',[r'ice|internal compiler|crash|segfault|hang|diagnostic|error recovery|assert|panic'],[r'diagnostic|error|parser']),
]
BUG=re.compile(r'\b(fix|bug|crash|wrong|incorrect|regression|ice|assert|hang|miscompil|issue|pr\s*#?\d)\b',re.I)

def git(*args,check=True):
 p=subprocess.run(['git','-C',str(REPO),*args],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if check and p.returncode: raise RuntimeError(p.stderr[-2000:])
 return p.stdout

def is_test(p):
 l=p.lower()
 if not (p.endswith('.das') or p.endswith('.cpp') or p.endswith('.h')): return False
 return ('test' in l or '/unit/' in l or '/regression' in l) and not l.startswith('3rdparty/')

def is_impl(p):
 l=p.lower()
 if l.startswith(('3rdparty/','tests/','test/')) or 'test' in Path(l).parts: return False
 if not p.endswith(('.cpp','.h','.das','.cc','.c')): return False
 return l.startswith(('src/','include/','modules/','utils/','daslib/'))

def candidates():
 raw=git('log','--format=%ct%x00%H%x00%s','--regexp-ignore-case','--grep=fix|bug|crash|wrong|regression|ice|assert|hang|miscompil|issue|PR')
 arr=[]
 for line in raw.splitlines():
  z=line.split('\x00',2)
  if len(z)==3: arr.append((int(z[0]),z[1],z[2]))
 arr.sort(reverse=True); return arr

def labels(row):
 text=(row['title']+'\n'+row['message']).lower(); paths=' '.join(row['source_files']).lower(); scores=[]
 for lab,mp,pp in RULES:
  s=sum(2 for p in mp if re.search(p,text))+sum(1 for p in pp if re.search(p,paths))
  if s:scores.append((s,lab))
 scores.sort(reverse=True)
 # Multi-label: semantically plausible leaves within one point of winner, max 3.
 if not scores:return []
 top=scores[0][0]
 return [lab for s,lab in scores if s>=max(1,top-1)][:3]

def main():
 rows=[]; rej=collections.Counter(); cand=candidates()
 for _,sha,_ in cand:
  msg=git('show','-s','--format=%B',sha); title=msg.splitlines()[0] if msg.splitlines() else ''
  if not BUG.search(msg): rej['no_bug_signal']+=1; continue
  names=[x for x in git('diff-tree','--no-commit-id','--name-only','-r',sha).splitlines() if x]
  tests=[p for p in names if is_test(p)]; impl=[p for p in names if is_impl(p)]
  if not tests: rej['no_regression_test_file']+=1; continue
  if not impl: rej['test_only_or_nonimplementation']+=1; continue
  row={'sha':sha,'date':git('show','-s','--format=%cI',sha).strip(),'title':title,'message':msg.strip(),
       'url':f'https://github.com/GaijinEntertainment/daScript/commit/{sha}','tests':tests,'source_files':impl}
  row['c_taxonomy_labels']=labels(row); rows.append(row)
  if len(rows)>=TARGET:break
 rows.sort(key=lambda r:(r['date'],r['sha']))
 cnt=collections.Counter(l for r in rows for l in r['c_taxonomy_labels'])
 covered=sum(bool(r['c_taxonomy_labels']) for r in rows)
 parents=collections.Counter()
 for r in rows:
  for p in set(TAXONOMY[l][0] for l in r['c_taxonomy_labels']):parents[p]+=1
 result={'target':TARGET,'accepted':len(rows),'candidate_commits':len(cand),'reject_counts':dict(rej),
         'covered_by_frozen_c_taxonomy':covered,'coverage':covered/len(rows) if rows else 0,
         'unmatched':len(rows)-covered,'leaf_occurrences':dict(cnt.most_common()),'parent_occurrences':dict(parents.most_common()),
         'method':'Historical daScript bug-signalled commits that change regression-like tests and implementation files; mapped against the C taxonomy frozen before target mining.'}
 (OUT/'daslang_regressions.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
 (OUT/'daslang_transfer.json').write_text(json.dumps(result,indent=2),encoding='utf8')
 print(json.dumps(result,indent=2))

if __name__=='__main__':main()
