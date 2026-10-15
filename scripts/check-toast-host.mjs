#!/usr/bin/env node
/**
 * Every native <Modal> must render a <ToastHost /> inside it (2026-10-15).
 *
 * On Android a Modal is its own window above the app root, so a toast drawn at
 * the root while a modal is open is drawn UNDER it. Walked: Edit Profile's
 * server reason "Username may only contain letters, numbers and underscores"
 * was toasted and invisible — Save read as a dead button. ToastProvider renders
 * the toast in the topmost mounted ToastHost (src/components/Toast.tsx).
 *
 * Checked on the AST: each JSX element named `Modal` must have a `ToastHost`
 * element among its descendants. A modal that can provably never be open while
 * a toast fires may carry `{/* toast-host-ok: <why> *\/}` instead.
 */
import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';

const files = [];
const walk = (d) => {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name);
    if (e.isDirectory()) { if (!['node_modules', '__tests__'].includes(e.name)) walk(p); }
    else if (/\.tsx$/.test(e.name)) files.push(p);
  }
};
['app', 'src'].forEach((r) => fs.existsSync(r) && walk(r));

const tagName = (el) => (ts.isJsxElement(el) ? el.openingElement.tagName : el.tagName).getText();
const problems = [];
let modals = 0;
for (const file of files) {
  const text = fs.readFileSync(file, 'utf8');
  if (!text.includes('<Modal')) continue;
  const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const visit = (node) => {
    if ((ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) && tagName(node) === 'Modal') {
      modals++;
      let ok = false;
      const scan = (n) => {
        if ((ts.isJsxElement(n) || ts.isJsxSelfClosingElement(n)) && tagName(n) === 'ToastHost') ok = true;
        if (!ok) ts.forEachChild(n, scan);
      };
      ts.forEachChild(node, scan);
      if (!ok && /toast-host-ok:/.test(node.getText(sf))) ok = true;
      if (!ok) {
        const line = sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1;
        problems.push(`${file}:${line}  <Modal> without <ToastHost /> — a toast fired while it is open is drawn under it on Android`);
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(sf);
}
if (problems.length) {
  console.log(`✗ toast host — ${problems.length} of ${modals} <Modal> element(s):`);
  problems.forEach((p) => console.log('   ' + p));
  process.exit(1);
}
console.log(`✓ toast host — ${modals} <Modal> elements, each renders a <ToastHost />`);
