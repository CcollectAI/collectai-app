/**
 * "How do I…" — help for using the APP, as opposed to help with a hobby.
 *
 * The distinction matters and the two must not be merged. `collectingGuides.ts`
 * answers "what is Lorcana and how do I not lose money on it"; this answers
 * "where is the button". A member who cannot find the scanner is not helped by
 * a paragraph on Enchanted rarity.
 *
 * WHY A TYPED MODULE, AND WHY LOCAL
 * ---------------------------------
 * Same reasoning as collectingGuides.ts: a handful of entries need no CMS, and
 * a module cannot be half-written at runtime. It is also the only source that
 * works when the thing the member needs help with is "the network isn't
 * working" — help fetched over the network is help you cannot read when you
 * most need it.
 *
 * ENGLISH ONLY (v1), deliberately — this is content, not chrome, and routing
 * ~40 prose strings through the i18n parity gate would mean shipping nothing
 * until all six locales are translated. Same call as the collecting guides.
 *
 * REACHABILITY
 * ------------
 * Every topic is findable from the global search bar (`app/search.tsx`) via
 * `searchAppHelp`, and browsable at `/help`. A help system reachable only from
 * a settings sub-menu is the empty-shelf failure this codebase keeps paying
 * for — see learning_complete_feature_reachable_from_nowhere.
 */

export type HelpStep = {
  /** The action, in the imperative: "Tap Add, then Scan". */
  action: string;
  /** Optional detail — a caveat, or what you should see happen. */
  detail?: string;
};

export type HelpTopic = {
  id: string;
  /** Phrased as the question a member would actually ask. */
  title: string;
  /** One sentence, shown in search results and on the index. */
  summary: string;
  /**
   * Words a member might type that do not appear in the title.
   *
   * Search matches title, summary AND these, because people search for the
   * word they have in their head, not the word we chose for the heading —
   * somebody looking for the scanner types "barcode", "camera" or "photo".
   */
  keywords: string[];
  steps: HelpStep[];
  /** Optional closing note: the thing people get wrong straight after. */
  footnote?: string;
};

export const APP_HELP: HelpTopic[] = [
  {
    // FIRST in the list on purpose. Every question about a collection app is
    // eventually this question, and the honest answer has caveats — so it gets
    // the most room and the plainest language.
    id: 'what-is-my-collection-worth',
    title: 'Where does my collection value come from?',
    summary:
      'From what things like yours actually sold for — and where we have no sales to go on, we say so instead of guessing.',
    keywords: [
      'value', 'worth', 'price', 'valuation', 'estimate', 'portfolio', 'how much',
      'zero', 'no price', 'wrong price', 'why did it change', 'accurate', 'ebay',
    ],
    steps: [
      {
        action: 'Open Portfolio. The number at the top is everything you own, added up.',
        detail:
          'It moves when the market moves, not only when you add something. A quiet week can still change it.',
      },
      {
        action: 'Tap an item to see the range behind its number.',
        detail:
          'We show a low, middle and high figure. The middle is our best estimate; the width between low and high is how much collectors actually disagree about that item right now. A narrow range means a liquid, well-traded thing. A wide one means treat the number with care.',
      },
      {
        action: 'Some items show no price at all, and that is deliberate.',
        detail:
          'If nothing comparable has sold recently we have nothing honest to base a figure on, so we leave it blank rather than inventing one. Blanks are most common in smaller categories and on unusual variants.',
      },
      {
        action: 'Add what you paid to turn "value" into "profit".',
        detail:
          'Without a purchase price we can only show how our valuation has moved, which is not the same as what you made. Once you enter what you paid, the gain shown is genuinely yours.',
      },
    ],
    footnote:
      'Seeing a different number on eBay? Asking prices are what somebody hopes to get; ours are built from what people actually paid. The two are rarely the same, and the asking price is almost always the higher of them.',
  },
  {
    id: 'add-an-item',
    title: 'How do I add something to my collection?',
    summary: 'Three ways in: scan a barcode, take a photo, or type it in yourself.',
    keywords: ['add', 'scan', 'barcode', 'camera', 'photo', 'new item', 'import', 'catalogue'],
    steps: [
      { action: 'Tap the + button in the middle of the tab bar.' },
      {
        action: 'Pick how you want to add it.',
        detail:
          'Scanning a barcode is quickest for anything boxed or sealed. A photo works for loose cards and figures. Entering it by hand is always available and never fails.',
      },
      {
        action: 'Check what came back before saving.',
        detail:
          'We fill in what we recognise, and we are not always right. The name and the category are the two worth a second look — the category decides how the item is valued.',
      },
    ],
    footnote:
      'Added something twice? Swipe the row in your collection to archive it rather than deleting — archived items keep their history and live under Archived.',
  },
  {
    id: 'sell-something',
    title: 'How do I sell something to another member?',
    summary: 'List it, field the bids, then arrange payment and delivery between you.',
    keywords: ['sell', 'sale', 'list', 'listing', 'marketplace', 'offer', 'bid', 'trade', 'ship'],
    steps: [
      { action: 'Open Market and tap Sell, then choose an item from your collection.' },
      {
        action: 'Set your asking price. Bids arrive under Open bids.',
        detail:
          'You can accept, counter, or turn down each one. Accepting does not take the listing off the market — until money moves, a reservation is not enforceable.',
      },
      {
        action: 'Agree, then sort out payment and postage directly with the buyer.',
        detail:
          'Sparrow does not handle payment and does not hold your money. Both sides confirm once the item has changed hands, and that is when you can rate each other.',
      },
    ],
    footnote:
      'There is no buyer protection here, and we would rather say so plainly than imply cover that does not exist.',
  },
  {
    id: 'keep-my-collection-private',
    title: 'How do I keep my collection private?',
    summary:
      'Four switches in Settings decide what other collectors can see. Your item list is never public either way.',
    keywords: [
      'private', 'privacy', 'hide', 'public', 'visible', 'profile', 'secret',
      'who can see', 'anonymous', 'discovery', 'online status',
    ],
    steps: [
      {
        action: 'Start from what is never public: your item list.',
        detail:
          'Nobody can browse the things you own. There is no screen in the app that shows one collector another collector’s items. The switches below control a handful of facts about you, not your collection.',
      },
      {
        action: 'Open Settings and find Privacy — there are four switches.',
        detail:
          'Show collection value, show item count, allow discovery, show online status. They take effect immediately and you can change them as often as you like.',
      },
      {
        action: 'Turn off "Show collection value" to hide your total.',
        detail:
          'The one most people want. It hides the number from your profile — it does not change the number, and you still see it yourself on Portfolio. Worth doing before you ever list something for sale, because a listing is what sends people to your profile.',
      },
      {
        action: 'Turn off "Show item count" if even the size of your collection feels like too much.',
        detail:
          'Value and count are separate switches on purpose: "I have 400 things" and "they are worth €30,000" are very different disclosures, and plenty of people are happy with one and not the other.',
      },
      {
        action: 'Turn off "Allow discovery" if you would rather not be found at all.',
        detail:
          'Discovery is how other collectors find you by shared interests. With it off you can still buy, sell and message; people just have to already know who you are.',
      },
      {
        action: 'Turn off "Show online status" so nobody can tell when you are using the app.',
        detail:
          'Useful if you would rather not advertise that you are active — for example while you are negotiating on an offer.',
      },
    ],
    footnote:
      'Two things stay visible whatever you set. Selling shows your display name to anyone browsing the marketplace, and messaging someone obviously shows them who is writing. If you want to be invisible, the answer is not to list — not a switch.',
  },

  {
    // Deliberately separate from the switches above. "Who can see this?" and
    // "what do you hold, and can I get rid of it?" are different worries, and
    // the second one is the one people ask before they trust an app with a
    // collection worth real money.
    id: 'what-data-you-hold',
    title: 'What do you know about me, and can I delete it?',
    summary:
      'You can take your whole collection out as a CSV at any time, and delete the account for good from Settings.',
    keywords: [
      'delete', 'delete account', 'remove account', 'close account', 'gdpr',
      'my data', 'export', 'csv', 'download', 'backup', 'leave', 'quit',
      'data protection', 'personal data', 'erase',
    ],
    steps: [
      {
        action: 'Export your collection first: Settings → Download full inventory as CSV.',
        detail:
          'You get a normal spreadsheet file you can keep, open in Excel or Numbers, or import somewhere else. The file is built on your device and is not stored on our servers. There is a second export on the Collection tab if you only want the items you have selected.',
      },
      {
        action: 'To delete the account, open Settings and scroll to Delete Account.',
        detail:
          'You have to type DELETE to confirm. That is intentional friction — this is not a pause button and there is no undo.',
      },
      {
        action: 'Understand what deletion means before you confirm.',
        detail:
          'Your account, profile and collection are removed permanently and you are signed out. Export first if you want to keep a copy, because afterwards we cannot get it back for you.',
      },
    ],
    footnote:
      'If you have sold through the marketplace, some sale records may have to be retained to meet tax and reporting obligations. That is a legal requirement, not a copy of your collection — the details are in the Privacy Policy and Data Processing pages, both linked from Settings.',
  },

  {
    id: 'settings-tour',
    title: 'What can I change in Settings?',
    summary:
      'Currency, appearance and language, what you get notified about, your marketplace connections, and how you get paid.',
    keywords: [
      'settings', 'preferences', 'options', 'currency', 'euro', 'dollar',
      'dark mode', 'theme', 'language', 'notifications', 'push', 'alerts off',
      'connections', 'ebay', 'payment', 'paypal', 'tax', 'bug', 'tips',
    ],
    steps: [
      {
        action: 'Currency and appearance: Settings → Appearance.',
        detail:
          'Change your currency and every price in the app converts, including your collection total. Dark mode and language live here too.',
      },
      {
        action: 'Notifications: choose what is worth interrupting you for.',
        detail:
          'Price drops and new listings are separate switches, so you can keep the alert you set a target price for and silence the rest.',
      },
      {
        action: 'Marketplace connections: link the sites you already sell on.',
        detail:
          'This is also where you disconnect one — disconnecting stops us reading that account, it does not touch anything you have listed there.',
      },
      {
        action: 'Payment handles: how a buyer pays you.',
        detail:
          'Sparrow never holds your money. These are the handles we show a buyer so the two of you can settle directly, which is why they are yours to set and change.',
      },
      {
        action: 'Further down: Tax reporting, the Condition guide, Report a bug, and Reset tips.',
        detail:
          '"Reset tips" brings back the little first-time hints if you dismissed them and want them again.',
      },
    ],
    footnote:
      'Privacy has its own section with four switches — see "How do I keep my collection private?".',
  },
  {
    id: 'buy-from-a-member',
    title: 'How do I buy something from another member?',
    summary:
      'Make an offer on their listing, agree a price, then the two of you settle and ship directly — Sparrow never holds the money.',
    keywords: [
      'buy', 'offer', 'bid', 'negotiate', 'counter', 'purchase', 'haggle',
      'marketplace', 'listing', 'accept', 'decline', 'safe', 'scam', 'protection',
    ],
    steps: [
      {
        action: 'Open the Market tab and tap a listing you want.',
        detail: 'Every listing is another member selling, not a shop. The price shown is what they are asking.',
      },
      {
        action: 'Send an offer, or message the seller first if you have questions.',
        detail:
          'You can offer less than the asking price. The seller can accept it, turn it down, or send a counter — you will see "Counter sent" on the bid, and you can accept or decline that in turn.',
      },
      {
        action: 'Once a price is agreed, arrange payment and delivery between yourselves.',
        detail:
          'Add your delivery address when asked, then pay the seller directly by whatever method you both agree. Sparrow shows the seller\'s payment handles; it never takes the money.',
      },
      {
        action: 'Tap "Mark as received" when it arrives, then rate the seller.',
        detail:
          'Both sides confirm, and both sides rate. Ratings are what make the next trade safer for everyone.',
      },
    ],
    footnote:
      'Say it plainly: there is no buyer protection, no escrow and no checkout. Sparrow never handles money, so a payment method with its own dispute route protects you and a bank transfer to a stranger does not. Full terms are in Marketplace Terms, linked from Settings.',
  },
  {
    id: 'get-paid-and-ship',
    title: 'I sold something. How do I get paid and send it?',
    summary:
      'Accept the offer, take payment directly, book the parcel, add tracking, and mark it sent.',
    keywords: [
      'sold', 'payment', 'paid', 'ship', 'shipping', 'post', 'parcel', 'tracking',
      'delivery', 'send', 'courier', 'postnl', 'seller',
    ],
    steps: [
      {
        action: 'Accept the offer on the bid, or send a counter.',
        detail: 'Once you accept, the buyer is asked for a delivery address.',
      },
      {
        action: 'Take payment before you post.',
        detail:
          'Your payment handles from Settings are shown to the buyer. Because Sparrow never holds funds, money arriving is the only confirmation there is — do not post on a promise.',
      },
      {
        action: 'Book the parcel and add the tracking code.',
        detail:
          'Use "Book the parcel" for a carrier, then paste the tracking code into the bid so the buyer can follow it.',
      },
      {
        action: 'Tap "Mark as sent", and rate the buyer once they confirm.',
        detail: 'The buyer taps "Mark as received" at their end, and then you can rate each other.',
      },
    ],
    footnote:
      'Keep proof of postage. With no escrow behind the sale, a tracking number is the only thing that shows you sent what you said you sent.',
  },
  {
    id: 'finish-a-set',
    title: 'How do I see which sets I am close to finishing?',
    summary:
      'Set completion shows collections you are part-way through and what is missing. It is a Pro feature.',
    keywords: [
      'set', 'sets', 'complete', 'completion', 'missing', 'finish', 'collection',
      'checklist', 'gaps', 'need',
    ],
    steps: [
      {
        action: 'Open a category page and choose "Sets to complete".',
        detail:
          'It groups your collections into Almost there, Making progress and Starting out, based on how much of each set you own.',
      },
      {
        action: 'Tap a set to see what you already have.',
        detail: 'That opens your items filtered to that collection, so you can see the gaps.',
      },
    ],
    footnote:
      'A set only appears if we know how many items it should contain. Where we do not know the size, we leave it out rather than invent a total and tell you that you are 60% done when we cannot know that.',
  },
  {
    id: 'deal-agent',
    title: 'Can Sparrow watch the market for me?',
    summary:
      'Yes — a deal search runs continuously across marketplaces and tells you when something matches. Pro feature.',
    keywords: [
      'deal', 'deals', 'agent', 'hunt', 'search', 'mandate', 'automatic', 'bot',
      'find deals', 'bargain', 'under', 'budget', 'snipe',
    ],
    steps: [
      {
        action: 'Open Deal Agent from the Watchlist tab, then "New Deal Search".',
        detail: 'It is the banner directly under the watchlist header.',
      },
      {
        action: 'Give it a name, a category and a maximum price per item.',
        detail:
          'Name it for yourself ("Pokemon grails under 200"). The maximum price is the filter that does the real work.',
      },
      {
        action: 'Optionally link it to a catalogue item with "Find this item in the catalogue".',
        detail:
          'That is what lets us tell you how much a deal saved you against the known value. Leave it out and the search still runs, it just cannot report savings.',
      },
      {
        action: 'Pick which marketplaces to include, then save.',
        detail: 'Matches appear under Deal Agent as they are found.',
      },
    ],
    footnote:
      'A deal search reads public listings on marketplaces. It never buys anything, never bids, and never spends money on your behalf.',
  },
  {
    id: 'no-price-yet',
    title: 'Why does my item say "No price yet"?',
    summary:
      'Because we have no sold prices for that exact thing — and we would rather say so than show you a number we made up.',
    keywords: [
      'no price', 'zero', 'no value', 'missing price', 'not valued', 'unpriced',
      'blank', 'why', 'wrong value', 'estimate',
    ],
    steps: [
      {
        action: 'Check the item is matched to the right catalogue entry.',
        detail:
          'Open the item and confirm the catalogue match. A mismatched or unmatched item has nothing to price against.',
      },
      {
        action: 'Expect gaps in categories that trade rarely.',
        detail:
          'Cards and sealed products sell constantly, so we have plenty to go on. A one-off, a regional variant or a niche category may genuinely have no recent sales anywhere.',
      },
      {
        action: 'If you know what it is worth, set the value yourself.',
        detail: 'Edit the item and enter a value. Yours is used, and it counts towards your collection total.',
      },
    ],
    footnote:
      'An unpriced item is counted in your collection but adds nothing to the total. That is deliberate: treating "we do not know" as "zero" would quietly understate what you own, and treating it as a guess would overstate it.',
  },
  {
    id: 'track-a-price',
    title: 'How do I get told when something hits my price?',
    summary: 'Put it on your watchlist with a target, and we will tell you when the market gets there.',
    keywords: ['watchlist', 'alert', 'notify', 'notification', 'target', 'price drop', 'wishlist', 'eye', 'heart'],
    steps: [
      {
        action: 'Find the thing you want, and tap the eye icon.',
        detail:
          'The eye is the watchlist and asks for a target price. The heart just saves something you like — no target, no alerts.',
      },
      { action: 'Set the price you would actually pay.' },
      {
        action: 'We check the market and send a notification when it lands.',
        detail:
          'Tapping the notification opens the listing that triggered it, not a generic screen.',
      },
    ],
  },
  {
    id: 'find-something',
    title: 'How does search work?',
    summary: 'One search box, across your items, the catalogue, events, other collectors — and this help.',
    keywords: ['search', 'find', 'lookup', 'filter', 'browse'],
    steps: [
      { action: 'Open the Explore tab and type anything.' },
      {
        action: 'Results are grouped by what they are.',
        detail:
          'Your own items come first, then the catalogue, then people and events. What you collect ranks higher — following your categories makes results better.',
      },
      {
        action: 'Nothing typed? Browse by category instead.',
      },
    ],
  },
  {
    id: 'what-is-pro',
    title: 'What do I get with Pro?',
    summary: 'The analysis features: deeper analytics, set completion, and unlimited watchlist slots.',
    keywords: ['pro', 'premium', 'upgrade', 'subscription', 'paid', 'billing', 'cancel', 'free'],
    steps: [
      {
        action: 'Everything you need to catalogue and value a collection is free.',
        detail:
          'Adding items, valuations, search, buying and selling — none of that is behind a paywall.',
      },
      {
        action: 'Pro adds the analysis on top.',
        detail:
          'Advanced analytics, market movers, set completion tracking, condition grading, dossier exports, and no cap on watchlist slots or daily alerts.',
      },
      {
        action: 'Manage or cancel it from Settings → Manage Subscription.',
        detail:
          'Billing runs through the App Store, so your plan is cancelled there and keeps working until the period you have paid for runs out.',
      },
    ],
  },
  {
    id: 'fix-a-wrong-item',
    title: 'Something was recognised wrongly. How do I fix it?',
    summary: 'Open the item and edit it — the correction sticks, and re-scanning will not overwrite it.',
    keywords: ['wrong', 'incorrect', 'edit', 'fix', 'change', 'mistake', 'rename', 'wrong price', 'wrong category'],
    steps: [
      { action: 'Open the item from your collection and tap Edit.' },
      {
        action: 'Correct the name, category or condition.',
        detail:
          'Category matters most: it decides which market we price the item against, so a miscategorised item will keep showing an odd value until it is fixed.',
      },
      {
        action: 'Save. Your version wins from then on.',
      },
    ],
    footnote:
      'If the valuation still looks wrong after fixing the category, it usually means we have too few sold comps for that exact thing.',
  },
];

/** One topic by id, or null. Callers must branch — a help link that opens an
 *  empty page is worse than no link. */
export function helpTopic(id: string | null | undefined): HelpTopic | null {
  if (!id) return null;
  return APP_HELP.find((t) => t.id === id) ?? null;
}

/**
 * Help topics matching a free-text query, best first.
 *
 * Matches title, summary and `keywords`, because members search with the word
 * in their head rather than the word in our heading. Scored so a title hit
 * outranks a keyword hit, and capped by the caller.
 */
export function searchAppHelp(query: string): HelpTopic[] {
  const q = query.trim().toLowerCase();
  if (q.length < 2) return [];
  const terms = q.split(/\s+/).filter(Boolean);

  return APP_HELP.map((topic) => {
    const title = topic.title.toLowerCase();
    const summary = topic.summary.toLowerCase();
    const keys = topic.keywords.join(' ').toLowerCase();
    let score = 0;
    for (const term of terms) {
      if (title.includes(term)) score += 3;
      else if (keys.includes(term)) score += 2;
      else if (summary.includes(term)) score += 1;
    }
    return { topic, score };
  })
    .filter((r) => r.score > 0)
    .sort((a, b) => b.score - a.score)
    .map((r) => r.topic);
}
