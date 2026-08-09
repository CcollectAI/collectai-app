#!/usr/bin/env node
/**
 * Fail on a DB-row serializer that DUCK-TYPES the conversion.
 *
 * The shape:
 *
 *     for k, v in row.items():
 *         if hasattr(v, "isoformat"):
 *             row[k] = v.isoformat()
 *         elif hasattr(v, "hex"):      # <-- meant for UUID / bytes
 *             row[k] = str(v)
 *
 * **FLOATS HAVE A .hex() METHOD.** `(642.64).hex() == '0x1.4147ae147ae14p+9'`.
 * So the `elif` catches every float in the result set and `str()`s it, and the
 * response ships `"642.64"` where the client expects `642.64`.
 *
 * Real instance: `server/app/features/search_router.py` (fixed 2026-08-09,
 * commit fe3b143). `price_eur` arrived as a string, the client's
 * `typeof priceEur === 'number'` test failed, and every PRICED search result
 * rendered "No price yet" — a live feature that looked exactly like missing
 * data. `items[].price` had been arriving as a string for as long as the
 * endpoint had existed. Nothing caught it: the SQL was right, asyncpg was
 * right, the Pydantic model was right. Only the JSON type on the wire was
 * wrong, and no test asserted on a JSON type.
 *
 * The rule: **a CONVERSION must ask "what IS this?" (`isinstance`), never
 * "does this quack?" (`hasattr`).** `hasattr` silently widens to every future
 * type that happens to share a method name, so the blast radius grows on its
 * own. With `isinstance`, a new type has to be handled deliberately.
 *
 * Use `app.lib.json_safe.json_safe_rows()` instead of hand-rolling this loop.
 *
 * Why `isoformat` is flagged too: a float does not have `.isoformat`, so that
 * branch is harmless *today*. It is the same anti-pattern, it sits inches from
 * the dangerous one, and it is what the dangerous one gets copy-pasted along
 * with. Both instances in the tree were fixed rather than allowlisted, so this
 * gate carries no exemption list — see learning_dont_allowlist_dead_assert_dead.
 *
 * Usage: node scripts/check-duck-typed-serialization.mjs   (npm run check:serialization)
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOTS = ['server'];
const SKIP_DIRS = new Set(['__pycache__', '.venv', 'venv', 'node_modules', '.git', 'build', 'dist']);

// Method names where "has this attribute" does NOT mean "is the type I meant".
// value -> the types that actually answer true, so the error can say why.
const AMBIGUOUS = {
  hex: 'float, bytes, bytearray, memoryview AND uuid.UUID — a float will be str()d',
  isoformat: 'datetime, date AND time — same duck-typed-conversion anti-pattern',
};

/**
 * Blank out Python COMMENTS and TRIPLE-QUOTED strings, preserving byte offsets
 * and newlines so reported line numbers stay true.
 *
 * This is not optional here. `search_router.py` now carries a long comment that
 * quotes `hasattr(v, "hex")` to explain the bug it just fixed. A regex-only
 * scan flags that comment, the gate "finds" the bug it was built to catch, and
 * the signal is worthless. A gate that cannot tell code from prose about code
 * is a gate that cries wolf until it gets deleted.
 *
 * Single-line string literals are deliberately KEPT. The first version of this
 * function blanked every string, which erased the `"hex"` argument that makes
 * the call decidable — so the gate reported a clean tree while
 * `activity_router.py:73` sat there with the exact bug in it. An instrument
 * that blanks its own evidence passes for the same reason a broken one does.
 * They are still *parsed* (just not blanked), because a `#` inside a string is
 * not a comment and skipping that distinction reintroduces the same class of
 * false negative one level down.
 */
function blankNonCode(src) {
  const out = src.split('');
  const n = src.length;
  let i = 0;
  const blank = (from, to) => {
    for (let k = from; k < to && k < n; k++) if (out[k] !== '\n') out[k] = ' ';
  };
  const isQuote = (c) => c === '"' || c === "'";

  while (i < n) {
    const c = src[i];

    if (c === '#') {
      let j = i;
      while (j < n && src[j] !== '\n') j++;
      blank(i, j);
      i = j;
      continue;
    }

    if (isQuote(c)) {
      // Include any string prefix (r, b, f, u, rb, fr, ...) in the span.
      let start = i;
      let p = i - 1;
      while (p >= 0 && /[A-Za-z]/.test(src[p])) p--;
      const prefix = src.slice(p + 1, i);
      if (/^[rbfuRBFU]{0,2}$/.test(prefix)) start = p + 1;

      const triple = src.slice(i, i + 3);
      const isTriple = triple === '"""' || triple === "'''";
      const delim = isTriple ? triple : c;
      let j = i + delim.length;
      while (j < n) {
        if (src[j] === '\\') { j += 2; continue; }
        if (src.slice(j, j + delim.length) === delim) { j += delim.length; break; }
        j++;
      }
      // Docstrings and other triple-quoted blocks are prose: blank them.
      // Short literals are arguments: walk past them but leave them readable.
      if (isTriple) blank(start, j);
      i = j;
      continue;
    }

    i++;
  }
  return out.join('');
}

const offenders = [];
let filesScanned = 0;
let hasattrCallsSeen = 0;

function walk(dir) {
  let entries;
  try { entries = readdirSync(dir); } catch { return; }
  for (const e of entries) {
    if (SKIP_DIRS.has(e)) continue;
    const full = join(dir, e);
    let st;
    try { st = statSync(full); } catch { continue; }
    if (st.isDirectory()) { walk(full); continue; }
    if (!e.endsWith('.py')) continue;

    filesScanned++;
    const raw = readFileSync(full, 'utf8');
    const code = blankNonCode(raw);

    for (const m of code.matchAll(/\bhasattr\s*\(/g)) hasattrCallsSeen++;

    // hasattr(<expr>, "<name>") — the literal is what makes it decidable.
    const re = /\bhasattr\s*\(\s*([^,()]+?)\s*,\s*["']([A-Za-z_]\w*)["']\s*\)/g;
    for (const m of code.matchAll(re)) {
      const name = m[2];
      if (!(name in AMBIGUOUS)) continue;
      const line = code.slice(0, m.index).split('\n').length;
      offenders.push({
        file: relative(process.cwd(), full),
        line,
        subject: m[1].trim(),
        name,
        why: AMBIGUOUS[name],
      });
    }
  }
}

for (const root of ROOTS) walk(root);

// A gate that scanned nothing passes for the wrong reason. Fail loudly instead:
// an empty result must never be indistinguishable from one that never looked.
if (filesScanned === 0) {
  console.error(`\n✖ check-duck-typed-serialization scanned 0 Python files under ${ROOTS.join(', ')}.`);
  console.error('  The gate is broken, not the code. Check the roots and the cwd.\n');
  process.exit(2);
}

if (offenders.length) {
  console.error('\n✖ Duck-typed serialization — hasattr() deciding a type CONVERSION:\n');
  for (const o of offenders) {
    console.error(`  ${o.file}:${o.line}`);
    console.error(`      hasattr(${o.subject}, "${o.name}") is true for ${o.why}.`);
    console.error(`      Ask what it IS: isinstance(${o.subject}, (…)). Better, use`);
    console.error(`      app.lib.json_safe.json_safe_rows() and delete the loop.\n`);
  }
  console.error(`Scanned ${filesScanned} Python files, ${hasattrCallsSeen} hasattr() call(s).`);
  process.exit(1);
}

console.log(
  `✓ No duck-typed serialization (${filesScanned} Python files scanned, `
  + `${hasattrCallsSeen} hasattr() call(s), 0 deciding a conversion).`
);
