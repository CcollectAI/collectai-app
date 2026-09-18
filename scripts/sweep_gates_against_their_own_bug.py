"""Class Y: a gate that has never seen its own bug is not a gate.

`check:double-submit` passed an unguarded write for TWO independent reasons and
nobody knew until the instance was found by reading (2026-09-19). The rule that
came out of it: run a gate against the pre-fix file before trusting its silence.

This applies that rule to every gate in `verify:prebuild`. For each one, the
commit that ADDED it also changed product code in 42 of 50 cases — so that
commit's PARENT is a known-positive: the bug the gate was written for is still
there. Drop today's checker into that tree and it must FIRE.

Silent at its own parent = the gate has never demonstrated it can fail.
Read-only with respect to the real working tree: everything happens in a
detached worktree.
"""
import json, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path('/Users/merle/GitHub/CcollectAI')
# Unique per run: two runs sharing one worktree path made every iteration after
# the first fail, and the run that finished first removed the tree under the
# other. The first version of this sweep reported 42 'errored' for that reason.
import os
WT = Path(f'/tmp/gate_sweep_wt_{os.getpid()}')

def git(*a, cwd=ROOT, timeout=600):
    return subprocess.run(['git', *a], cwd=cwd, capture_output=True, text=True, timeout=timeout)

s = json.loads((ROOT / 'package.json').read_text())['scripts']['verify:prebuild']
checkers = re.findall(r'(?:node|python3) (scripts/[\w.-]+\.(?:mjs|py)|server/scripts/[\w_]+\.py)', s)

targets = []
for c in checkers:
    out = git('log', '--diff-filter=A', '-1', '--format=%H', '--', c).stdout.strip()
    if not out:
        continue
    files = git('show', '--name-only', '--format=', '-1', out).stdout.split()
    non_script = [f for f in files
                  if not f.startswith(('scripts/', 'server/scripts/'))
                  and not f.endswith('.md') and f != 'package.json']
    if non_script:                      # fix landed with the gate -> parent is dirty
        targets.append((c, out))

print(f"testing {len(targets)} gates whose parent commit is a known-positive", flush=True)
if WT.exists():
    git('worktree', 'remove', str(WT), '--force')
git('worktree', 'add', '-qf', '--detach', str(WT), 'HEAD')

results = []
for i, (c, sha) in enumerate(targets, 1):
    label = c.split('/')[-1]
    # CLEAN FIRST. The checker copied in on the previous iteration is untracked
    # here, and `git checkout` refuses to overwrite an untracked file — so
    # cleaning afterwards made every iteration after the first report
    # NO-PARENT. `-x` too: an ignored leftover blocks it just the same.
    git('clean', '-qfdx', '-e', 'node_modules', cwd=WT)
    r = git('checkout', '-q', '--detach', f'{sha}~1', cwd=WT)
    if r.returncode != 0:
        results.append((label, sha[:9], f'CHECKOUT-FAIL', r.stderr.strip()[:80]))
        print(f"  [{i}/{len(targets)}] {label}: CHECKOUT-FAIL {r.stderr.strip()[:60]}", flush=True)
        continue
    dest = WT / c
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / c, dest)
    runner = 'node' if c.endswith('.mjs') else 'python3'
    try:
        p = subprocess.run([runner, c], cwd=WT, capture_output=True, text=True, timeout=180)
        code = p.returncode
        first = next((l for l in (p.stdout + p.stderr).splitlines() if l.strip()), '')[:90]
    except subprocess.TimeoutExpired:
        code, first = 'TIMEOUT', ''
    state = 'FIRES' if code == 1 else ('silent' if code == 0 else f'ERR({code})')
    results.append((label, sha[:9], state, first))
    print(f"  [{i}/{len(targets)}] {label}: {state}", flush=True)

git('worktree', 'remove', str(WT), '--force')

print("\n" + "=" * 92)
print(f"{'gate':<44} {'added':<11} state")
print("=" * 92)
for label, sha, state, first in sorted(results, key=lambda r: (r[2] != 'silent', r[0])):
    print(f"{label:<44} {sha:<11} {state}")
    if state == 'silent' and first:
        print(f"{'':<56} {first}")
fires = sum(1 for r in results if r[2] == 'FIRES')
silent = sum(1 for r in results if r[2] == 'silent')
err = len(results) - fires - silent
print(f"\n  FIRES on its own bug : {fires}")
print(f"  SILENT (unproven)    : {silent}")
print(f"  errored / timed out  : {err}")
