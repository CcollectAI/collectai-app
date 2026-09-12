#!/usr/bin/env node
/**
 * "Never shows a raw slug" — docs/TAXONOMY.md:110, stated there as the one
 * property the app CAN promise about categories (registry membership is not,
 * because categories can be user-typed).
 *
 * The promise had no enforcement. `app/(tabs)/wishlist.tsx:593` rendered
 * `{item.category}` straight into a Text, so the watchlist showed `mtg`,
 * `pokemon`, `onepiece`, `manga` while every other surface showed "Magic: The
 * Gathering". The correct row already existed in
 * `src/components/watchlist/WatchlistItemCard.tsx` — which calls
 * `categoryDisplayName` and is imported by NOTHING. A duplicate implementation
 * silently kept the fix out of the shipped screen.
 *
 * This flags a `.category` / `.condition` member expression rendered as JSX
 * TEXT (a child, or inside a template literal that is a child) without passing
 * through a display-name wrapper. Attributes (`key=`, `id=`, `value=`), cache
 * keys and plain strings are not renders and are not flagged — that is exactly
 * the noise that made the grep version unreadable and unrun.
 */
import { readFileSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { parse } from '@babel/parser';
import _traverse from '@babel/traverse';
const traverse = _traverse.default ?? _traverse;

const WRAPPERS = new Set([
  'categoryDisplayName', 'conditionDisplayName', 'formatCategoryName',
  'formatConditionName', 't', 'categoryLabel', 'displayName',
]);
const FIELDS = new Set(['category', 'condition']);

// Values that are NOT the slug despite the property name. Each earns its place
// by being read from a different shape, not by being inconvenient.
const ALLOW = [
  // ConfidenceRing takes a NUMBER (fc.category is a 0..1 confidence).
  /fieldConfidence|\bfc\./,
];

// The promise is made to MEMBERS. The admin review queue is operated by someone
// who works in slug space and needs to see the stored value verbatim; showing
// "Magic: The Gathering" there would hide which of two slugs a row carries.
const ALLOW_FILES = [/^src\/app\/\(admin\)\//];

const files = execSync(
  "git ls-files 'app/*.tsx' 'src/**/*.tsx' 'app/**/*.tsx'", { encoding: 'utf8' },
).split('\n').filter(Boolean);

const findings = [];

for (const file of files) {
  const code = readFileSync(file, 'utf8');
  let ast;
  try {
    ast = parse(code, { sourceType: 'module', plugins: ['typescript', 'jsx'] });
  } catch (e) {
    console.error(`  parse failed: ${file}: ${e.message}`);
    process.exitCode = 2;
    continue;
  }

  // Is this node inside a call to a display-name wrapper?
  const wrapped = (path) => {
    let p = path.parentPath;
    while (p) {
      if (p.isCallExpression()) {
        const c = p.node.callee;
        const name = c.type === 'Identifier' ? c.name
          : c.type === 'MemberExpression' && c.property.type === 'Identifier' ? c.property.name
          : null;
        if (name && WRAPPERS.has(name)) return true;
      }
      p = p.parentPath;
    }
    return false;
  };

  /**
   * Does this node's value reach a user?
   *
   * Two things are NOT renders and must not be flagged, because a gate with
   * false positives is a gate nobody runs (learning_the_gate_existed_and_was_
   * never_run): a GUARD (`{x.category ? <Text/> : null}` reads the slug to
   * decide, and shows none of it) and a non-spoken attribute (`key=`, `id=`).
   *
   * One thing IS a render that looks like an attribute: `accessibilityLabel`.
   * Skipping every attribute is how AlertsCard kept saying "Start your
   * watchlist" aloud for an hour after the visible copy stopped. If a sighted
   * user must not see `one_piece_tcg`, neither must a blind one hear it.
   */
  const rendersAsText = (path) => {
    let node = path;
    let parent = path.parentPath;
    while (parent) {
      if (parent.isConditionalExpression() && parent.node.test === node.node) return false;
      // `&&` on the left is a guard. `??` / `||` on the left are NOT -- they
      // render the slug whenever it is present, which is the normal case.
      if (parent.isLogicalExpression() && parent.node.operator === '&&'
          && parent.node.left === node.node) return false;
      if (parent.isUnaryExpression()) return false;
      if (parent.isJSXExpressionContainer()) {
        const holder = parent.parentPath;
        if (holder.isJSXElement() || holder.isJSXFragment()) return true;
        if (holder.isJSXAttribute()) {
          const name = holder.node.name;
          return name.type === 'JSXIdentifier'
            && /^accessibility(Label|Hint|Value)$/.test(name.name);
        }
        return false;
      }
      if (parent.isJSXAttribute()) return false;
      if (parent.isFunction() || parent.isProgram()) return false;
      node = parent;
      parent = parent.parentPath;
    }
    return false;
  };

  traverse(ast, {
    MemberExpression(path) {
      const prop = path.node.property;
      if (path.node.computed || prop.type !== 'Identifier' || !FIELDS.has(prop.name)) return;
      if (!rendersAsText(path)) return;
      if (wrapped(path)) return;
      const src = code.slice(path.node.start, path.node.end);
      if (ALLOW.some((re) => re.test(src))) return;
      if (ALLOW_FILES.some((re) => re.test(file))) return;
      findings.push({
        file,
        line: path.node.loc.start.line,
        src,
        text: code.split('\n')[path.node.loc.start.line - 1].trim().slice(0, 100),
      });
    },
  });
}

if (findings.length === 0) {
  console.log(`check:category-display PASS — ${files.length} files, no raw slug reaches a user.`);
  process.exit(process.exitCode ?? 0);
}

console.error(`check:category-display FAIL — ${findings.length} raw slug render(s).`);
console.error('docs/TAXONOMY.md:110 — "Never shows a raw slug" is the promise.');
console.error('Wrap in categoryDisplayName() / conditionDisplayName().\n');
for (const f of findings) console.error(`  ${f.file}:${f.line}  ${f.src}   in:  ${f.text}`);
process.exit(1);
