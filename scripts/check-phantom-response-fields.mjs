/**
 * GATE: a client property whose EVERY source is a key the server never sends.
 *
 * The mirror image of `check_dropped_fields.py`, which covers the REQUEST
 * direction (a client key no Pydantic model declares). Nothing watched the
 * RESPONSE direction, and it cost five weeks:
 *
 *   collection: it.collection ?? it.set_name ?? undefined
 *
 * `/portfolio/items` sends `collection_name`. It sends neither `collection`
 * nor `set_name`, so that property was `undefined` for every item on every
 * account — and `tsc` is happy, because the client's own Raw type declares
 * both optional. Set completion on the analytics tier read 0 forever.
 *
 * The rule is deliberately NOT "any read of an unknown key". This codebase
 * writes tolerant `??` chains on purpose (`it.id ?? it.item_id`) to accept an
 * older build or the Signals proxy shape, and flagging those would need a
 * hand-maintained allowlist -- the first failure mode in
 * learning_four_ways_a_new_gate_is_wrong. A chain with ONE real key resolves.
 * A chain with NONE can only ever yield its fallback, so the property is dead
 * code that type-checks.
 *
 * Exempt one with `// phantom-ok: <why>` on the property or the line above.
 * Read-only. Exit 1 = findings.
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(new URL('..', import.meta.url).pathname);

/** Which client files consume which server routers. */
const CONSUMERS = [
  {
    client: 'src/store/portfolioAnalyticsStore.ts',
    server: 'server/app/routes/portfolio_router.py',
  },
];

/** Every string-literal dict key in a Python file, comments stripped. */
function serverKeys(relPath) {
  const src = readFileSync(path.join(ROOT, relPath), 'utf8');
  const keys = new Set();
  for (const rawLine of src.split('\n')) {
    // Drop `#` comments, but not a `#` inside a string literal.
    let line = rawLine;
    const hash = line.search(/(^|\s)#/);
    if (hash !== -1 && (line.slice(0, hash).match(/"/g) || []).length % 2 === 0) {
      line = line.slice(0, hash);
    }
    for (const m of line.matchAll(/["'](\w+)["']\s*:/g)) keys.add(m[1]);
    // A key added after the literal — `items[-1]["rarity_score"] = ...` — is
    // just as much part of the response, and the first version of this gate
    // could not see one, so it reported the very field being added as phantom.
    for (const m of line.matchAll(/\[\s*["'](\w+)["']\s*\]\s*=/g)) keys.add(m[1]);
  }
  return keys;
}

/** Identifiers that hold a raw server row in this file. */
function rawIdents(src) {
  const idents = new Set();
  for (const m of src.matchAll(/\(\s*(\w+)\s*:\s*Raw\w+\s*\)/g)) idents.add(m[1]);
  for (const m of src.matchAll(/const\s+(\w+)\s*=\s*\(?await\s+get\w*Raw\(\)/g)) idents.add(m[1]);
  return idents;
}

const findings = [];

for (const { client, server } of CONSUMERS) {
  const keys = serverKeys(server);
  const src = readFileSync(path.join(ROOT, client), 'utf8');
  const lines = src.split('\n');
  const idents = rawIdents(src);
  if (!idents.size) {
    findings.push(`${client}: no raw-row identifier found — the gate cannot see this file`);
    continue;
  }
  const identRe = new RegExp(`\\b(?:${[...idents].join('|')})\\.(\\w+)`, 'g');

  // A property is `name:` followed by an expression ending at the next
  // property at the same depth. Scan property-start lines and take the
  // expression through to the next one.
  for (let i = 0; i < lines.length; i++) {
    const start = lines[i].match(/^\s{4,}(\w+):\s*(.*)$/);
    if (!start) continue;
    const prop = start[1];
    let expr = start[2];
    let j = i + 1;
    while (j < lines.length && !/^\s{4,}\w+:(\s|$)/.test(lines[j]) && !/^\s*\}\)/.test(lines[j])) {
      expr += '\n' + lines[j];
      j++;
    }
    // The whole contiguous comment block above, not just one line — a reason
    // worth writing is usually longer than the 80th column.
    let above = '';
    for (let k = i - 1; k >= 0 && /^\s*(\/\/|\*|\/\*)/.test(lines[k]); k--) {
      above = lines[k] + '\n' + above;
    }
    if ((above + expr).includes('phantom-ok:')) continue;

    const read = [...new Set([...expr.matchAll(identRe)].map((m) => m[1]))];
    if (!read.length) continue;
    const real = read.filter((k) => keys.has(k));
    if (real.length) continue;

    findings.push(
      `${client}:${i + 1}  ${prop} — reads only ${read.map((k) => `\`${k}\``).join(', ')}, ` +
        `none of which ${path.basename(server)} sends`,
    );
  }
}

if (findings.length) {
  console.error(
    `[phantom-response-fields] FAIL — ${findings.length} propert${findings.length === 1 ? 'y' : 'ies'} can only ever be undefined:\n`,
  );
  for (const f of findings) console.error(`  - ${f}`);
  console.error(
    '\nEither read the key the server actually sends, or write `// phantom-ok: <why>`.',
  );
  process.exit(1);
}
console.log('[phantom-response-fields] OK');
