# Help and guides

Two content systems that look alike and must not be merged.

| | Collecting guides | App help |
|---|---|---|
| Answers | "What is Lorcana, and how do I not lose money on it?" | "Where is the button?" |
| Content | `src/data/collectingGuides.ts` — **55 guides (all categories)** | `src/data/appHelp.ts` — **15 topics** |
| Screen | `app/guide/[categoryId].tsx` | `app/help/index.tsx`, `app/help/[topicId].tsx` |
| Keyed on | `CategoryId` (compile-checked) | free-form topic id |
| Reached from | category screen banner, beginner surface | Search tab banner + search results |

A member who cannot find the scanner is not helped by a paragraph on Enchanted
rarity. Keeping them apart is the point.

## Why both are typed modules, not tables

A handful of entries need no CMS, and a module cannot be half-written at
runtime: a DB-backed guide with three of six sections filled renders a page that
looks broken and fails nothing loudly. Keying the guides on `CategoryId` also
makes "does this slug exist?" a **compile** error rather than a script.

App help has a second reason to be local: *"how do I add an item"* is exactly
the question somebody asks when something is not working. **Help fetched over
the network is help you cannot read when you most need it.** `searchAppHelp` is
computed from the bundled module, so the HELP section in search still renders
when `/search/unified` has failed.

## English only, deliberately (v1)

Neither is routed through i18n. The parity gate requires every key in all six
locales (`learning_i18n_missing_key_renders_english`), and putting ~110 prose
strings through it would mean shipping nothing until they are translated six
times. The chrome around them (headers, buttons) does use i18n keys.

## Reachability is the part that breaks

Both of these are the exact shape of
`learning_complete_feature_reachable_from_nowhere`: correct content, wired to
nothing. `npm run check:reachable` caught `app/help/index.tsx` the same hour it
was written — the topic pages were reachable from search, the index was reachable
from nowhere.

Entry points, and why each is where it is:

- **Search tab, idle state** → `/help`. Someone who opens Search and types
  nothing is more often lost than browsing, so the banner sits above the
  category grid.
- **Search results** → `/help/[topicId]`, as a HELP section rendered **first**.
  Somebody typing "how do i sell" wants the instructions, not a listing whose
  title contains "sell".
- **Category screen** → `/guide/[categoryId]`, only where `guideFor()` returns
  non-null. **As of 2026-08-16 all 55 categories have a guide**, so this banner
  now renders everywhere — but the null branch stays, because a newly added
  category or a renamed slug re-creates the dead-end this rule was written for.

`hasResults` in `app/search.tsx` counts help matches too. Without that, a query
matching only help renders "no results" directly above the help it found.

## Optional fields mean the page must branch

`CollectingGuide.whatItIs` is optional in the type, and `app/guide/[categoryId].tsx`
must keep branching on it — but as of **2026-08-16 every one of the 55 guides has
one**, so the branch is now insurance rather than a live case.

That is a reversal, and worth recording. The original rule was "deliberately
absent from the obvious ones — nobody opening a watch guide needs to be told
what a watch is". Correct about definitions, wrong about the field's job: this
paragraph carries the **culture**, not the dictionary entry. A reader who does
not know that Charizard outsells mechanically identical cards, that a LEGO set
"retires", that watch collectors prize an unpolished case, or that Taylor
Swift's fanbase decodes easter eggs and treats 13 as load-bearing, cannot use
the value section underneath it.

When it was first added, the first four `whatItIs` paragraphs restated their own
`intro` almost verbatim, so the page said the same thing twice in a row. If you
add or edit one, **read it directly after the intro it will sit under.**

## Extended primers for the most-collected categories (2026-08-16)

Seven categories carry a **multi-paragraph** `whatItIs` of roughly 1,800–2,000
characters instead of the one-paragraph version the other 48 have: `pokemon`,
`mtg`, `yugioh`, `lorcana`, `digimon`, `one_piece_tcg`, `lego`. They were picked
from the catalogue, not from taste — those are the seven largest by row count in
`mv_catalog_item_price` (yugioh 58,835 → lego 3,068).

A primer answers what a complete beginner cannot look up in a glossary: the
eras and which one a card belongs to, the single mechanism that governs price
in *that* hobby, and the one cultural fact without which the numbers make no
sense. Each hobby's mechanism is different and naming it is the whole job —
Magic's **Reserved List**, Yu-Gi-Oh!'s **Forbidden and Limited list**, LEGO's
**retirement**, Lorcana's **Enchanted** rarity, One Piece's **print waves**,
Digimon's willingness to reprint, Pokémon's **grading** spread.

Two rules, both learned the hard way:

- **Every number must come from `mv_catalog_item_price`, and you must run the
  query.** The first draft of these primers quoted €129,679 for the top Pokémon
  card and €644 for the Enchanted Elsa. Neither existed: the real figures are
  €7,524 (Gold Star Umbreon) and €824. Prose in a shipped screen is a claim to
  the user, and a wrong price in a guide about prices is worse than no guide.
  The view is keyed `(category, item_key, price_eur)` — the **titles live in
  `category_items`**, joined on `category` + `item_key` (`title`, not `name`;
  `category`, not `category_id`).
- **A comparison beats an absolute.** "Base Set holo Charizard €1,469, Blastoise
  €175, same set and same rarity" teaches the Charizard premium in one line;
  "Charizard is expensive" teaches nothing.

The screen splits `whatItIs` on blank lines and renders one `<Text>` per
paragraph (`bodyNext` adds the 12pt gap). A single `<Text>` ran four paragraphs
into an unreadable wall, and nothing failed — so
`__tests__/data/collectingGuideBackground.test.ts` pins **both halves**: the
content still has its breaks, and the screen still splits on them. Each of its
four assertions was proven to fail against the regression it guards before it
was wired into `verify:prebuild`.

## Writing rules

- **Every instruction must point at something that exists.** The first draft
  said "open the item and use Archive" (archive is a swipe on the row in the
  collection list) and "Settings → Subscription" (it is labelled *Manage
  Subscription*). Check the screen before writing the step.
- **Say what we cannot do.** The selling topic states plainly that there is no
  buyer protection and that Sparrow never holds money — §5a of
  `P2P_MARKETPLACE_SPEC.md` makes that a legal position, not a tone choice.
- **`keywords` carry the search.** People search for the word in their head, not
  the word in our heading: the scanner topic matches "barcode", "camera" and
  "photo", none of which appear in its title.
- **Order matters on the index.** `APP_HELP` renders in array order and
  "Where does my collection value come from?" is first, because every question
  about a collection app eventually becomes that one.

## Sets to complete — the chain behind the screen

`app/sets-to-complete.tsx` was empty for **every account, always**, and the
cause is worth recording because nothing failed:

1. `/portfolio/items` returned only `id, name, category, current_value,
   prev_value`. Every set field the screen mapped (`collection`,
   `collection_name`, `set_code`, `set_size`) read null.
2. With no size, `statusScoring.ts` fell back to hint tables keyed on DISPLAY
   names (`'Pokemon'`, `'Lorcana'`) while `items.category` holds SLUGS
   (`pokemon`, `lorcana`), so no lookup ever hit.
3. The final fallback was "expected = however many you own", so every set
   computed as exactly 100% complete — and the screen's `0.4 .. 0.95` band then
   filtered all of them away.

The chain now: `sets.total_items` → `/portfolio/items` (joined on
`s.category_id = i.category AND lower(s.name) = lower(i.collection_name)`) →
`set_size` → `expectedCount`.

**`expectedCount` and `completenessRatio` are `number | null`.** Null means "we
hold no catalogue row for this set", which is NOT "0% complete" — use the
`hasKnownSetSize` guard rather than `?? 0` at each call site. Making the type
nullable is what enumerated all 21 call sites across three files; two of them
(`SearchStatusPanel`, `StatusBadge`) were carrying the same dead predicate.

**Vocabulary:** `sets.name` ↔ `items.collection_name` (same string);
`sets.category_id` ↔ `items.category` (both slugs). A unique index
(`sets_category_lower_name_uniq`) enforces the join key, because a duplicate
`sets` row differing only by case would match an item twice and a LEFT JOIN that
matches twice DUPLICATES the item — inflating "owned" with nothing added.

Seed data for E2E lives in `server/migrations/`-adjacent scratch SQL and is
tagged for removal: `sets.metadata->>'seed' = 'e2e-sets-2026-08-15'` and
`items.source = 'seed:e2e-sets'`.

## Portfolio Tier is NOT wired (found 2026-08-15)

Unrelated screen, same class, recorded here so it is not rediscovered.
`computeTierFromScores` takes rarity, completeness and diversification:

- **rarity** ← `items[].rarity_score`. `/portfolio/items` does not return that
  field. Always 0.
- **completeness** ← `loadSetsFromBackend()`, which reads `raw.sets` /
  `raw.set_completion` from `/portfolio/overview`. That endpoint returns neither
  key. Always 0 in production — in `__DEV__` it substitutes `DEMO_SETS`, which
  is why the screen shows a plausible number on a dev build and 0 on a real one.
- **diversification** ← allocations. This one genuinely works.

`composite = 0.5*rarity + 0.3*completeness + 0.2*diversification`, and Silver
starts at 0.30. With the first two pinned at 0, the ceiling is **0.20** — so the
tier is arithmetically incapable of ever leaving "Unranked" for any real user.
Fixing it means serving `rarity_score` and set completion from the API; until
then the card states a rank it can never award.

## Both surfaces need the nav bar (2026-08-16)

`help/index`, `help/[topicId]` and `guide/[categoryId]` shipped without
`QuickNavBar`, so someone who reached them from search had only a back chevron
— a reading screen with no way onward. All three now render it, including in
their not-found branches. See "The newest screens keep shipping without the nav
bar" in `docs/ui-playbook.md`.

They also stopped setting a native `headerTitle`: each one opens with a hero
carrying the page title, so the bar title was a duplicate — and on iOS it was a
CENTRED duplicate, disagreeing with every other title in the app.

## Help topics added 2026-08-16

Eight to fifteen. The new ones and why each exists:

- **What do you know about me, and can I delete it?** — export first, then
  Delete Account (types `DELETE`, no undo). The question people ask before
  trusting an app with a collection worth real money.
- **What can I change in Settings?** — currency, appearance, notifications,
  marketplace connections, payment handles.
- **How do I buy something from another member?** and **I sold something. How do
  I get paid and send it?** — the two halves of a P2P trade, both stating
  plainly that there is no buyer protection and Sparrow never holds money
  (§5a of `P2P_MARKETPLACE_SPEC.md` makes that a legal position, not a tone).
- **How do I see which sets I am close to finishing?** — set completion, and why
  a set with no known size is omitted rather than given an invented total.
- **Can Sparrow watch the market for me?** — deal searches, and the explicit
  promise that the agent never buys, bids or spends.
- **Why does my item say "No price yet"?** — the honest answer, plus how to set
  a value yourself. Unpriced items count in the collection but add nothing to
  the total: treating "we do not know" as zero understates, guessing overstates.

The privacy topic was also rewritten from 3 steps to 6, opening with what is
never public (your item list) and ending with what no switch can hide (selling
shows your display name).
