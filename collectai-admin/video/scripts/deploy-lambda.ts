#!/usr/bin/env tsx
// ═══════════════════════════════════════════════════════════════════════════
// CollectAI Video — Lambda Deployment & Rendering
//
// Setup (one-time):
//   1. Configure AWS credentials: aws configure --profile collectai-video
//   2. Deploy site:  npx tsx scripts/deploy-lambda.ts --deploy
//   3. Render:       npx tsx scripts/deploy-lambda.ts --render --composition PullReveal --props out/scripts/pull-reveal_pokemon_en.json
//
// Production: The admin dashboard calls the FastAPI endpoint which invokes this.
// ═══════════════════════════════════════════════════════════════════════════

import * as fs from "fs";
import * as path from "path";

// ─── Config ──────────────────────────────────────────────────────────────

const LAMBDA_CONFIG = {
  region: process.env.REMOTION_AWS_REGION ?? "eu-central-1",
  functionName: process.env.REMOTION_FUNCTION_NAME ?? "collectai-video-render",
  serveUrl: process.env.REMOTION_SERVE_URL ?? "",
  s3BucketName: process.env.REMOTION_S3_BUCKET ?? "collectai-video-renders",
  outPrefix: "renders/",
};

// ─── CLI ─────────────────────────────────────────────────────────────────

const args = process.argv.slice(2);
const hasFlag = (name: string) => args.includes(`--${name}`);
function getArg(name: string): string | undefined {
  const idx = args.indexOf(`--${name}`);
  return idx >= 0 ? args[idx + 1] : undefined;
}

async function deploySite() {
  console.log("[deploy] Deploying Remotion site to S3...");
  console.log(`  Region: ${LAMBDA_CONFIG.region}`);
  console.log(`  Bucket: ${LAMBDA_CONFIG.s3BucketName}`);
  console.log("");
  console.log("Run manually:");
  console.log(`  npx remotion lambda sites create --region=${LAMBDA_CONFIG.region}`);
  console.log(`  npx remotion lambda functions deploy --region=${LAMBDA_CONFIG.region} --memory=2048 --timeout=240`);
  console.log("");
  console.log("Then set REMOTION_SERVE_URL and REMOTION_FUNCTION_NAME environment variables.");
}

async function renderVideo() {
  const composition = getArg("composition") ?? "PullReveal";
  const propsFile = getArg("props");

  if (!LAMBDA_CONFIG.serveUrl) {
    console.error("[render] REMOTION_SERVE_URL not set. Run --deploy first.");
    process.exit(1);
  }

  let inputProps = {};
  if (propsFile) {
    const absPath = path.resolve(propsFile);
    if (fs.existsSync(absPath)) {
      inputProps = JSON.parse(fs.readFileSync(absPath, "utf-8"));
    } else {
      console.error(`[render] Props file not found: ${absPath}`);
      process.exit(1);
    }
  }

  console.log("[render] Starting Lambda render...");
  console.log(`  Composition: ${composition}`);
  console.log(`  Region:      ${LAMBDA_CONFIG.region}`);
  console.log(`  Function:    ${LAMBDA_CONFIG.functionName}`);
  console.log(`  Props:       ${propsFile ?? "(default)"}`);

  // Dynamic import so the script doesn't fail if @remotion/lambda isn't installed
  try {
    const { renderMediaOnLambda, getRenderProgress } = await import("@remotion/lambda/client");

    const { renderId, bucketName } = await renderMediaOnLambda({
      region: LAMBDA_CONFIG.region as "eu-central-1",
      functionName: LAMBDA_CONFIG.functionName,
      serveUrl: LAMBDA_CONFIG.serveUrl,
      composition,
      inputProps,
      codec: "h264",
      imageFormat: "jpeg",
      maxRetries: 1,
      framesPerLambda: 20,
      privacy: "no-acl",
      downloadBehavior: { type: "play-in-browser" },
      outName: `${LAMBDA_CONFIG.outPrefix}${composition}_${Date.now()}.mp4`,
    });

    console.log(`\n[render] Started! Render ID: ${renderId}`);
    console.log(`  Bucket: ${bucketName}`);

    // Poll for completion
    let done = false;
    while (!done) {
      await new Promise((r) => setTimeout(r, 3000));
      const progress = await getRenderProgress({
        renderId,
        bucketName,
        functionName: LAMBDA_CONFIG.functionName,
        region: LAMBDA_CONFIG.region as "eu-central-1",
      });

      if (progress.done) {
        done = true;
        console.log(`\n[render] Complete!`);
        console.log(`  Output: ${progress.outputFile}`);
        console.log(`  Size:   ${progress.outputSizeInBytes ? `${(progress.outputSizeInBytes / 1024 / 1024).toFixed(1)}MB` : "unknown"}`);
        console.log(`  Cost:   ~$${progress.costs ? progress.costs.estimatedTotalCost.toFixed(4) : "0.03"}`);
      } else if (progress.fatalErrorEncountered) {
        console.error(`\n[render] Fatal error:`, progress.errors?.[0]?.message ?? "Unknown error");
        process.exit(1);
      } else {
        const pct = Math.round((progress.overallProgress ?? 0) * 100);
        process.stdout.write(`\r  [${pct}%] Rendering...`);
      }
    }
  } catch (err) {
    const msg = (err as Error).message;
    if (msg.includes("Cannot find module")) {
      console.error("[render] @remotion/lambda not installed. Run: cd video && npm install");
    } else {
      console.error("[render] Error:", msg);
    }
    process.exit(1);
  }
}

async function main() {
  if (hasFlag("deploy")) {
    await deploySite();
  } else if (hasFlag("render")) {
    await renderVideo();
  } else {
    console.log("Usage:");
    console.log("  npx tsx scripts/deploy-lambda.ts --deploy");
    console.log("  npx tsx scripts/deploy-lambda.ts --render --composition PullReveal --props out/scripts/file.json");
  }
}

main().catch(console.error);
