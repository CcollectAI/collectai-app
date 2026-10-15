#!/usr/bin/env node
/**
 * Android's Alert.alert renders AT MOST THREE buttons and silently drops the
 * rest (2026-10-15: the carrier picker showed 3 of 10 carriers and no Cancel,
 * the sell form's Category picker 3 of 50+). Pickers go through
 * showActionSheet, which uses ActionSheetHost on Android.
 *
 * Fails on any Alert.alert(...) whose buttons argument is an array literal
 * with more than 3 elements, or a NON-literal (a .map, a variable) — the count
 * of those cannot be read statically, and that is exactly the shape the
 * carrier picker had. Mark a reviewed dynamic call with
 *   // alert-buttons-ok: <why it can never exceed 3>
 * on the line above.
 */
import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';

const ROOTS = ['app', 'src'];
const files = [];
const walk = (d) => {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name);
    if (e.isDirectory()) { if (e.name !== 'node_modules' && e.name !== '__tests__') walk(p); }
    else if (/\.(tsx?|jsx?)$/.test(e.name)) files.push(p);
  }
};
ROOTS.forEach((r) => fs.existsSync(r) && walk(r));

const problems = [];
let calls = 0;
for (const file of files) {
  const text = fs.readFileSync(file, 'utf8');
  if (!text.includes('Alert.alert')) continue;
  const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, file.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  const lines = text.split('\n');
  const visit = (node) => {
    if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression)
        && node.expression.expression.getText(sf) === 'Alert' && node.expression.name.text === 'alert') {
      calls++;
      const btns = node.arguments[2];
      const line = sf.getLineAndCharacterOfPosition(node.getStart(sf)).line;
      const marked = /alert-buttons-ok:/.test(lines[line - 1] ?? '') || /alert-buttons-ok:/.test(lines[line] ?? '');
      if (btns && !marked) {
        if (ts.isArrayLiteralExpression(btns)) {
          const spread = btns.elements.some((e) => ts.isSpreadElement(e));
          if (spread) problems.push(`${file}:${line + 1}  buttons contain a spread — count unknown`);
          else if (btns.elements.length > 3) problems.push(`${file}:${line + 1}  ${btns.elements.length} buttons — Android shows 3`);
        } else {
          problems.push(`${file}:${line + 1}  buttons are not a literal array — count unknown`);
        }
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(sf);
}
if (problems.length) {
  console.log(`✗ Android Alert buttons — ${problems.length} of ${calls} Alert.alert call(s):`);
  for (const p of problems) console.log('   ' + p);
  console.log('\n   Use showActionSheet (ActionSheetHost on Android) for pickers, or mark a\n   reviewed call "// alert-buttons-ok: <why it never exceeds 3>".');
  process.exit(1);
}
console.log(`✓ Android Alert buttons — ${calls} Alert.alert calls, none over 3 buttons`);
