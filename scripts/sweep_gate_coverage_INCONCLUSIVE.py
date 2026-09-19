"""Class Y-2: not "has this gate ever fired?" but "WHICH of its own sites does it catch?"

Class Y reverted a gate's whole commit and watched it go red — which only proves
it catches the easiest instance in the batch. `check:double-submit` passes that
test and was still blind to `handleDelist` (2026-09-19).

So: revert the fixed sites ONE AT A TIME and run the gate against each. A gate
that fires on 2 of 9 files its own commit fixed does not cover its class.

Read-only against the real tree; everything happens in a detached worktree.
"""
import json, os, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path('/Users/merle/GitHub/CcollectAI')
WT = Path(f'/tmp/gate_cov_wt_{os.getpid()}')
MAX_FILES = 8          # per gate, to keep the run finite
MAX_COMMIT_FILES = 40  # skip mega-commits where most files are unrelated

def git(*a, cwd=ROOT, timeout=600):
    return subprocess.run(['git', *a], cwd=cwd, capture_output=True, text=True, timeout=timeout)

spec = json.loads((ROOT / 'package.json').read_text())['scripts']['verify:prebuild']
# gate -> its invocation flags
inv = {}
for m in re.finditer(r'(?:node|python3) (scripts/[\w.-]+\.(?:mjs|py)|server/scripts/[\w_]+\.py)([^&]*)', spec):
    inv[m.group(1)] = m.group(2).strip()

targets = []
for c, flags in inv.items():
    sha = git('log', '--diff-filter=A', '-1', '--format=%H', '--', c).stdout.strip()
    if not sha:
        continue
    files = git('show', '--name-only', '--format=', '-1', sha).stdout.split()
    # `server/workers/` counts. check_param_interval_cast scans all of server/,
    # and its commit's real fixes were in workers — excluding them tested the
    # two incidental lib files and scored the gate 0/2, which read as a blind
    # gate and was a filter artefact.
    prod = [f for f in files
            if f.startswith(('app/', 'src/', 'server/app/', 'server/workers/'))
            and f.endswith(('.ts', '.tsx', '.py'))
            and not f.startswith(('server/tests/', '__tests__/'))]
    # A fix that spans code AND the gate's own config (an allowlist) or the
    # locale files cannot be recreated by reverting ONE code file: the config
    # still exempts it, or the en.json half still agrees. Those gates are not
    # measurable this way and are reported as such rather than scored 0/N.
    spans_config = any(
        f.endswith(('.txt', '.json')) and not f.startswith('package')
        for f in files)
    if prod and len(files) <= MAX_COMMIT_FILES:
        targets.append((c, flags, sha, prod[:MAX_FILES], len(prod), spans_config))

print(f"gates with a testable fix-set: {len(targets)}", flush=True)
git('worktree', 'add', '-qf', '--detach', str(WT), 'HEAD')
results = []
for i, (c, flags, sha, files, total, spans_config) in enumerate(targets, 1):
    label = c.split('/')[-1]
    # `git checkout <sha> -- <file>` STAGES the restore, so the index is dirty
    # when the next gate's `checkout --detach` runs and git refuses. `clean`
    # does not touch the index — 14 of 32 gates never ran because of this.
    git('reset', '-q', '--hard', cwd=WT)
    git('clean', '-qfdx', '-e', 'node_modules', cwd=WT)
    if git('checkout', '-q', '--detach', sha, cwd=WT).returncode != 0:
        print(f"  [{i}/{len(targets)}] {label}: CHECKOUT-FAIL", flush=True); continue
    (WT / c).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / c, WT / c)
    runner = 'node' if c.endswith('.mjs') else 'python3'
    args = [runner, c] + (flags.split() if flags else [])
    base = subprocess.run(args, cwd=WT, capture_output=True, text=True, timeout=180)
    if base.returncode != 0:
        print(f"  [{i}/{len(targets)}] {label}: BASELINE-RED (skipped)", flush=True); continue
    caught = []
    for f in files:
        git('checkout', '-q', f'{sha}~1', '--', f, cwd=WT)
        try:
            r = subprocess.run(args, cwd=WT, capture_output=True, text=True, timeout=180)
            caught.append(r.returncode == 1)
        except subprocess.TimeoutExpired:
            caught.append(False)
        git('checkout', '-q', sha, '--', f, cwd=WT)
    hit = sum(caught)
    results.append((label, hit, len(files), total, spans_config))
    note = "  (fix spans config/locale — not measurable by single-file revert)" if spans_config else ""
    print(f"  [{i}/{len(targets)}] {label}: catches {hit}/{len(files)}{note}", flush=True)

git('worktree', 'remove', str(WT), '--force')
print("\n" + "=" * 78)
print(f"{'gate':<42} catches / tested   (fixed files in commit)")
print("=" * 78)
measurable = [r for r in results if not r[4]]
skipped = [r for r in results if r[4]]
for label, hit, n, total, _sc in sorted(measurable, key=lambda r: r[1] / max(r[2], 1)):
    flag = "  <-- PARTIAL" if hit < n else ""
    print(f"{label:<42} {hit}/{n}{'':<12} {total}{flag}")
full = sum(1 for _l, h, n, _t, _s in measurable if h == n)
print(f"\n  catch every site their own commit fixed : {full} of {len(measurable)}")
print(f"  catch only SOME                         : {len(measurable) - full}")
if skipped:
    print(f"\n  not measurable by single-file revert (fix spans config/locale): {len(skipped)}")
    for label, hit, n, _t, _s in skipped:
        print(f"    {label}  ({hit}/{n} — ignore this ratio)")
