"""Y-3: what did the gate MISS that the human found — measured, not assumed.

Y-2 reverted a gate's fixed files one at a time and scored it against ALL of
them. That denominator was wrong: most commits change files for unrelated
reasons, so a low ratio meant nothing.

This asks the gate itself. At the commit BEFORE the gate landed, the bug is
still there. Run the gate and record WHICH FILES IT REPORTS. Then compare with
the files that same commit went on to fix:

  reported ∩ fixed  -> the gate found what the human found
  fixed \\ reported  -> THE MISS: the human fixed it, the gate never saw it
  reported \\ fixed  -> the gate flagged something the human left

No per-class signature, no judgement about what counts as a site — the two sets
come from the gate and from the commit, and neither is mine.
"""
import json, os, re, shutil, subprocess
from pathlib import Path

ROOT = Path('/Users/merle/GitHub/CcollectAI')
WT = Path(f'/tmp/gate_miss_wt_{os.getpid()}')
# LONGEST ALTERNATIVE FIRST. `(?:ts|tsx|py)` matches `ts` and stops, so every
# `.tsx` path was captured as `.ts`, never equalled the real filename, and every
# React file scored as "fixed but never flagged" — that alone produced a headline
# of 510 misses. Verified against a control the gate is known to report.
PATHRE = re.compile(r'\b((?:app|src|server/app|server/workers)/[\w./\[\]()-]+\.(?:tsx|ts|py))')

def git(*a, cwd=ROOT, timeout=600):
    return subprocess.run(['git', *a], cwd=cwd, capture_output=True, text=True, timeout=timeout)

spec = json.loads((ROOT / 'package.json').read_text())['scripts']['verify:prebuild']
inv = {m.group(1): m.group(2).strip() for m in
       re.finditer(r'(?:node|python3) (scripts/[\w.-]+\.(?:mjs|py)|server/scripts/[\w_]+\.py)([^&]*)', spec)}

rows = []
git('worktree', 'add', '-qf', '--detach', str(WT), 'HEAD')
for c, flags in inv.items():
    sha = git('log', '--diff-filter=A', '-1', '--format=%H', '--', c).stdout.strip()
    if not sha:
        continue
    changed = {f for f in git('show', '--name-only', '--format=', '-1', sha).stdout.split()
               if PATHRE.fullmatch(f)}
    if not changed:
        continue
    git('reset', '-q', '--hard', cwd=WT)
    git('clean', '-qfdx', '-e', 'node_modules', cwd=WT)
    if git('checkout', '-q', '--detach', f'{sha}~1', cwd=WT).returncode != 0:
        continue
    (WT / c).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / c, WT / c)
    runner = 'node' if c.endswith('.mjs') else 'python3'
    try:
        r = subprocess.run([runner, c] + (flags.split() if flags else []),
                           cwd=WT, capture_output=True, text=True, timeout=240)
    except subprocess.TimeoutExpired:
        continue
    if r.returncode != 1:            # gate not red at the pre-fix commit: nothing to compare
        rows.append((c.split('/')[-1], None, changed, set()))
        continue
    reported = set(PATHRE.findall(r.stdout + r.stderr))
    rows.append((c.split('/')[-1], reported, changed, reported & changed))

git('worktree', 'remove', str(WT), '--force')

print("=" * 96)
print(f"{'gate':<40} {'fixed':>6} {'reported':>9} {'both':>6}   files the HUMAN fixed that the gate never flagged")
print("=" * 96)
misses = 0
for label, reported, changed, both in sorted(rows, key=lambda r: r[0]):
    if reported is None:
        print(f"{label:<40} {len(changed):>6} {'not-red':>9} {'-':>6}   (gate not red at its own parent)")
        continue
    missed = sorted(changed - reported)
    misses += len(missed)
    shown = ', '.join(m.split('/')[-1] for m in missed[:3]) or '—'
    print(f"{label:<40} {len(changed):>6} {len(reported):>9} {len(both):>6}   {shown}")
print(f"\n  total files fixed-but-never-flagged: {misses}")
