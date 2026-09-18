#!/usr/bin/env node
/**
 * No submittable profile may ship the beta unlock.
 *
 * `EXPO_PUBLIC_BETA_UNLOCK_ALL=true` reports every user as `pro` and skips
 * RevenueCat entirely. It is deliberate on the `internal` profile. The hazard
 * class G (docs/CLASS_SWEEPS.md) raised: `submit.production` and `submit.store`
 * point at the SAME `ascAppId`, so the wrong artefact reaches the store with no
 * paywall and nothing says so.
 *
 * WHAT THIS CHECKS, AND WHY NOT THE ARTEFACT
 * ------------------------------------------
 * Class G asked for "a submit-time assertion". Inspecting the BINARY cannot
 * work, measured 2026-09-18 on a real store APK:
 *
 *   assets/index.android.bundle is Hermes bytecode; `EXPO_PUBLIC_SUPABASE_URL`
 *   (the NAME) survives in its string table, and `EXPO_PUBLIC_BETA_UNLOCK_ALL`
 *   does NOT — 0 occurrences — because Expo's babel plugin replaces that exact
 *   member expression with a literal, so the name is gone whatever the value
 *   was. Both branches of the flag ship either way, so no string distinguishes
 *   a beta build from a store build. An artefact scan would return "absent" for
 *   good and bad builds alike, which is a check that cannot fail — the worst
 *   kind (learning_four_ways_a_new_gate_is_wrong).
 *
 * So this guards the CONFIGURATION, which is decidable: every profile that can
 * be submitted must pin the flag OFF. That catches the drift that would make a
 * bad artefact possible in the first place.
 *
 * It does NOT catch submitting an `internal` artefact by hand — nothing local
 * can, because the binary does not carry the answer. The mitigation for that is
 * to build the artefact you submit, in the same command.
 *
 * Exit 0 clean, 1 findings.
 */
import { readFileSync } from 'node:fs';

const eas = JSON.parse(readFileSync(new URL('../eas.json', import.meta.url), 'utf8'));
const FLAG = 'EXPO_PUBLIC_BETA_UNLOCK_ALL';

// A profile is submittable if `submit` names it, plus the conventional store
// ones. `internal` is deliberately excluded — that is the whole point of it.
const submitProfiles = new Set([...Object.keys(eas.submit ?? {}), 'production', 'store']);
const findings = [];

for (const [name, profile] of Object.entries(eas.build ?? {})) {
  if (!submitProfiles.has(name)) continue;
  const value = String(profile?.env?.[FLAG] ?? '').toLowerCase();
  if (value === 'true') {
    findings.push(`build.${name} sets ${FLAG}=true`);
  } else if (value !== 'false') {
    // Unset is NOT safe: the flag then falls through to whatever the shell or
    // EAS project env supplies, which is exactly how a paywall-less build gets
    // made without anyone editing this file.
    findings.push(`build.${name} does not pin ${FLAG} (found ${value || 'nothing'})`);
  }
}

if (findings.length) {
  console.error(`[submit-profiles] FAIL — ${findings.length} submittable profile(s) could ship a paywall-less build:\n`);
  for (const f of findings) console.error(`  - ${f}`);
  console.error(
    `\n  Pin it: "env": { "${FLAG}": "false" } on every profile you can submit.\n` +
    '  `internal` may keep it true — it is not submittable and is not checked.',
  );
  process.exit(1);
}

console.log(
  `[submit-profiles] PASS — every submittable profile pins ${FLAG}=false ` +
  `(${[...submitProfiles].filter((p) => eas.build?.[p]).join(', ')}).`,
);
