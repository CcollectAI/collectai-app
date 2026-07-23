/**
 * Drive web/referral.js in a real DOM for the URL shapes a creator posts.
 * Hop 1 of the funnel — where the code used to die.
 */
const fs = require("fs");
const { JSDOM } = require("jsdom");

const SCRIPT = fs.readFileSync(
  require("path").join(__dirname, "..", "..", "web", "referral.js"), "utf8");
const PAGE = `<!doctype html><html><body>
  <a href="/r/OTHER">app link</a>
  <a href="/item/123">item link</a>
  <a href="https://example.com/x">external</a>
</body></html>`;

let pass = 0, fail = 0;
function check(name, ok, detail) {
  if (ok) { pass++; console.log("PASS  " + name); }
  else { fail++; console.log("FAIL  " + name + (detail ? "   -> " + detail : "")); }
}

async function run(url, seedStorage) {
  const dom = new JSDOM(PAGE, { url, runScripts: "outside-only" });
  // JSDOM reports readyState "loading" immediately after construction, so the
  // script's DOMContentLoaded branch is the one that fires. Wait for the
  // document to finish before eval'ing, mirroring a real <script defer>.
  await new Promise((resolve) => {
    if (dom.window.document.readyState === "complete") return resolve();
    dom.window.addEventListener("load", resolve, { once: true });
  });
  const store = {};
  if (seedStorage) store["sparrow.referralCode"] = seedStorage;
  Object.defineProperty(dom.window, "localStorage", {
    value: {
      getItem: (k) => (k in store ? store[k] : null),
      setItem: (k, v) => { store[k] = String(v); },
      removeItem: (k) => { delete store[k]; },
    },
    configurable: true,
  });
  dom.window.eval(SCRIPT);
  const banner = dom.window.document.getElementById("referral-banner");
  return {
    stored: store["sparrow.referralCode"] ?? null,
    bannerText: banner ? banner.textContent : null,
    doc: dom.window.document,
  };
}

(async function main() {
  // ── ?ref= on the landing page
  let r = await run("https://sparrowcollect.com/?ref=luna10");
  check("?ref= is captured and normalised", r.stored === "LUNA10", r.stored);
  check("banner shows the code", !!r.bannerText && r.bannerText.includes("LUNA10"), r.bannerText);
  check("banner tells the user to enter it",
    !!r.bannerText && r.bannerText.includes("Enter it when you sign up"), r.bannerText);

  // ── /r/<CODE> path form
  r = await run("https://sparrowcollect.com/r/luna10");
  check("/r/<CODE> path is captured", r.stored === "LUNA10", r.stored);

  // ── aliases
  r = await run("https://sparrowcollect.com/?utm_content=abc1");
  check("utm_content alias captured", r.stored === "ABC1", r.stored);

  // ── junk must not be stored
  r = await run("https://sparrowcollect.com/?ref=not%20a%20code");
  check("junk code is rejected", r.stored === undefined || r.stored === null, String(r.stored));
  check("no banner for junk", r.bannerText === null, r.bannerText);

  // ── no code at all
  r = await run("https://sparrowcollect.com/");
  check("no banner when no code anywhere", r.bannerText === null, r.bannerText);

  // ── persistence: a later visit with no param still shows the stored code
  r = await run("https://sparrowcollect.com/pro", "LUNA10");
  check("stored code survives to another page",
    !!r.bannerText && r.bannerText.includes("LUNA10"), r.bannerText);

  // ── first write wins
  r = await run("https://sparrowcollect.com/?ref=second", "FIRST");
  check("first code wins over a later link", r.stored === "FIRST", r.stored);

  // ── app links get decorated, external ones do not
  r = await run("https://sparrowcollect.com/?ref=luna10");
  const links = [...r.doc.querySelectorAll("a")].map((a) => a.getAttribute("href"));
  check("app link carries the code", links.some((h) => h.includes("/item/123?ref=LUNA10")), String(links));
  check("external link untouched", links.includes("https://example.com/x"), String(links));
  check("existing ref= not double-appended",
    !links.some((h) => (h.match(/ref=/g) || []).length > 1), String(links));

    console.log(`\n${pass} passed, ${fail} failed`);
    process.exit(fail ? 1 : 0);
})();
