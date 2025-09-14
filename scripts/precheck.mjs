import fs from 'node:fs';
import path from 'node:path';

const problems = [];
const root = process.cwd();

// helper
const mustExist = (rel) => {
  const fp = path.join(root, rel);
  if (!fs.existsSync(fp)) problems.push(`Missing: ${rel}`);
};

// 1) common missing helpers that broke bundling recently
['lib/b64.ts', 'lib/upload.ts'].forEach(mustExist);

// 2) scream gently about app/_shelf/explore.tsx imports
if (fs.existsSync(path.join(root, 'app/_shelf/explore.tsx'))) {
  problems.push('Found app/_shelf/explore.tsx (often carries starter imports). Consider removing if unused.');
}

// Report (non-blocking)
if (problems.length) {
  console.log('⚠️  Precheck warnings:');
  for (const p of problems) console.log('  -', p);
  process.exit(0);
} else {
  console.log('✅ Precheck clean.');
}
