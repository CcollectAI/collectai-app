"""Class W probe: a column the schema carries that no code mentions.

`marketplace_listings.reports_count` was one, found by accident on 2026-09-18:
written on every report, read by nothing. This looks for the rest.

Membership test, not a parse: a column whose bare name appears NOWHERE in
server/app, src/ or app/ cannot be read by them. False negatives are fine
(a name that collides with a common word looks "used"); false POSITIVES are
what matter, and they are the finding.
"""
import json, re
from pathlib import Path

ROOT = Path('/Users/merle/GitHub/CcollectAI')
lock = json.loads((ROOT / 'scripts/schema.lock.json').read_text())
cols = lock.get('column_meta', {})

corpus = []
for pat in ('server/app/**/*.py', 'server/workers/**/*.py', 'server/pipelines/**/*.py',
            'src/**/*.ts', 'src/**/*.tsx', 'app/**/*.tsx', 'app/**/*.ts'):
    for f in ROOT.glob(pat):
        try:
            corpus.append(f.read_text(errors='ignore'))
        except Exception:
            pass
blob = '\n'.join(corpus)
words = set(re.findall(r'[A-Za-z_][A-Za-z0-9_]*', blob))

def camel(s):
    head, *rest = s.split('_')
    return head + ''.join(w.title() for w in rest)

by_table = {}
for key in cols:
    if '.' not in key:
        continue
    table, col = key.rsplit('.', 1)
    if col in words or camel(col) in words:
        continue
    by_table.setdefault(table, []).append(col)

total = sum(len(v) for v in by_table.values())
for t, cs in sorted(by_table.items(), key=lambda kv: -len(kv[1]))[:18]:
    print(f"{t:44} {len(cs):3}  {', '.join(sorted(cs)[:6])}{' …' if len(cs) > 6 else ''}")
print(f"\n{total} column(s) of {len(cols)} whose name appears nowhere in server/app, src/ or app/")
