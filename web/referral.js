/**
 * Creator referral capture — hop 1 of the funnel.
 *
 * A creator posts https://sparrowcollect.com/?ref=LUNA10 (or /r/LUNA10). Before
 * this file existed the landing page ignored both, so the code died here and
 * every install was unattributable.
 *
 * What this can and cannot do:
 *   - If the app is INSTALLED, the universal link opens it directly and the
 *     in-app handler (src/lib/referral.ts) captures the code. This script does
 *     not run in that case.
 *   - On a FRESH install the code cannot survive the App Store round-trip —
 *     there is no Branch/AppsFlyer SDK and no IDFA, so nothing can carry it.
 *     Pretending otherwise would attribute installs we cannot observe. Instead
 *     we persist it, show it, and ask the user to enter it at signup. Lossy,
 *     honest, and works today.
 */
(function () {
  "use strict";

  var KEY = "sparrow.referralCode";
  var VALID = /^[A-Z0-9_-]{1,32}$/;

  function normalise(raw) {
    if (!raw) return null;
    var v = String(raw).trim().toUpperCase();
    return VALID.test(v) ? v : null;
  }

  function fromLocation() {
    var params = new URLSearchParams(window.location.search);
    var code =
      normalise(params.get("ref")) ||
      normalise(params.get("referral_code")) ||
      normalise(params.get("utm_content"));
    if (code) return code;

    var m = window.location.pathname.match(/^\/r\/([^/?#]+)/i);
    return m ? normalise(decodeURIComponent(m[1])) : null;
  }

  function read() {
    try {
      return normalise(localStorage.getItem(KEY));
    } catch (e) {
      return null; // Safari private mode throws on localStorage.
    }
  }

  function persist(code) {
    try {
      // First write wins, matching the app: the creator who actually brought
      // the visitor gets credit, not whichever link they tapped last.
      if (!localStorage.getItem(KEY)) localStorage.setItem(KEY, code);
    } catch (e) {
      /* non-fatal */
    }
  }

  function render(code) {
    if (document.getElementById("referral-banner")) return;

    var bar = document.createElement("div");
    bar.id = "referral-banner";
    bar.setAttribute("role", "status");
    bar.style.cssText = [
      "position:fixed", "left:0", "right:0", "bottom:0", "z-index:9999",
      "background:#81D8D0", "color:#0D1B2A",
      "font:500 15px/1.4 Roboto,system-ui,-apple-system,sans-serif",
      "padding:14px 16px", "display:flex", "gap:12px",
      "align-items:center", "justify-content:center", "flex-wrap:wrap",
      "box-shadow:0 -2px 12px rgba(0,0,0,.18)",
    ].join(";");

    var label = document.createElement("span");
    label.textContent = "Your creator code:";

    var chip = document.createElement("strong");
    chip.textContent = code;
    chip.style.cssText =
      "font:700 16px/1 ui-monospace,SFMono-Regular,Menlo,monospace;" +
      "letter-spacing:.08em;background:rgba(13,27,42,.10);" +
      "padding:7px 11px;border-radius:7px";

    var hint = document.createElement("span");
    hint.textContent = "Enter it when you sign up.";
    hint.style.cssText = "opacity:.85";

    var copy = document.createElement("button");
    copy.type = "button";
    copy.textContent = "Copy";
    copy.style.cssText =
      "cursor:pointer;border:0;border-radius:7px;padding:8px 14px;" +
      "background:#0D1B2A;color:#fff;font:600 14px/1 inherit";
    copy.addEventListener("click", function () {
      // clipboard API is https-only and can reject; degrade to selection.
      var done = function () {
        copy.textContent = "Copied";
        setTimeout(function () { copy.textContent = "Copy"; }, 1800);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(code).then(done, function () {
          window.prompt("Your creator code:", code);
        });
      } else {
        window.prompt("Your creator code:", code);
      }
    });

    var dismiss = document.createElement("button");
    dismiss.type = "button";
    dismiss.setAttribute("aria-label", "Dismiss");
    dismiss.textContent = "×";
    dismiss.style.cssText =
      "cursor:pointer;border:0;background:transparent;color:#0D1B2A;" +
      "font:400 22px/1 inherit;opacity:.6;padding:0 4px";
    dismiss.addEventListener("click", function () { bar.remove(); });

    bar.append(label, chip, copy, hint, dismiss);
    document.body.appendChild(bar);
  }

  function decorateAppLinks(code) {
    // Carry the code on any link into the app, so an already-installed user
    // hits the universal-link path and never has to type it.
    var links = document.querySelectorAll('a[href^="https://sparrowcollect.com"], a[href^="/"]');
    Array.prototype.forEach.call(links, function (a) {
      var href = a.getAttribute("href") || "";
      if (href.indexOf("ref=") !== -1 || href.charAt(0) === "#") return;
      if (!/^\/(r|item|events|categories|purchase|users)\b/.test(href)) return;
      a.setAttribute("href", href + (href.indexOf("?") === -1 ? "?" : "&") + "ref=" + code);
    });
  }

  function init() {
    var code = fromLocation();
    if (code) persist(code);
    else code = read();
    if (!code) return;
    render(code);
    decorateAppLinks(code);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
