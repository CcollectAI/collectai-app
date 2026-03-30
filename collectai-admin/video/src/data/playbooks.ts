/**
 * Niche Playbooks — Deep Cultural Context for Content Creation
 *
 * Each playbook captures the tribal knowledge a creator needs to make
 * content that resonates with a specific collecting community.
 * The learning loop uses this to evaluate WHY content performs.
 */

export interface NichePlaybook {
  nicheId: string;
  communityName: string;
  /** One sentence: what this community cares about most */
  coreDesire: string;
  /** The emotional reason people collect in this niche */
  emotionalDriver: string;
  /** Community-specific slang — use these to signal "insider" status */
  slang: Record<string, string>;
  /** Topics that reliably drive engagement (comments, shares, saves) */
  hotTopics: string[];
  /** Controversial opinions that drive comment engagement */
  controversies: string[];
  /** Common pain points — these make great "I feel you" content */
  painPoints: string[];
  /** Seasonal/calendar-driven content opportunities */
  seasonalCalendar: Array<{ month: string; event: string; angle: string }>;
  /** Hero items — the grails everyone knows, perfect for thumbnails/hooks */
  heroItems: Array<{ item: string; whyItMatters: string; priceRange: string }>;
  /** Where this community lives online — informs hashtag + collab strategy */
  communityHubs: Array<{ platform: string; name: string; size: string }>;
  /** What competitors miss about this niche — our content gap to fill */
  competitorGaps: string[];
  /** Specific CollectAI features most relevant to this niche */
  bestFeatures: string[];
  /** Content formats that work best for this niche */
  bestFormats: string[];
  /** Things that will make this community dismiss you immediately */
  credibilityKillers: string[];
}

export const NICHE_PLAYBOOKS: NichePlaybook[] = [
  // ═══════════════════════════════════════════════════════════════
  // POKEMON TCG
  // ═══════════════════════════════════════════════════════════════
  {
    nicheId: 'pokemon',
    communityName: 'Pokemon TCG Collectors',
    coreDesire: 'Finding and owning the rarest, highest-graded cards — especially vintage',
    emotionalDriver: 'Nostalgia (childhood + anime) combined with the thrill of pulling or finding something rare',
    slang: {
      'slab': 'A graded card in a plastic case (PSA/CGC/BGS)',
      'raw': 'An ungraded card',
      'hit': 'A valuable pull from a pack',
      'god pack': 'A pack where every card is a hit (especially in Japanese sets)',
      'whitening': 'White marks on card edges that lower grade',
      'centering': 'How well the image is centered on the card',
      'pop count': 'Number of a specific card at a given grade in PSA census',
      'holo bleed': 'When holographic pattern bleeds outside the image box',
      'shadowless': 'Base Set cards without shadow on the right side of the image box — worth 10x more',
      'first edition': 'Cards from the initial print run, marked with a stamp',
      'alt art': 'Alternate artwork version of a card — usually the chase card of a set',
      'moonbreon': 'Umbreon VMAX Alt Art from Evolving Skies — community grail',
      'zard': 'Charizard — the most iconic card in the hobby',
      'rip': 'Opening packs (as in "ripping packs")',
      'invest': 'Buying cards speculatively (controversial term in community)',
    },
    hotTopics: [
      'PSA vs CGC vs BGS — which grading company is best?',
      'Is modern Pokemon a bubble? Will prices hold?',
      'Japanese vs English cards — which is the better investment?',
      'Best alt arts of the current era',
      'Vintage vs modern — where to put your money',
      'Pack opening odds and pull rates',
      'Grade predictions before sending to PSA',
      'Hidden gems in current sets that are undervalued',
    ],
    controversies: [
      'PSA 10 pop counts are too high — they grade too loosely',
      'Modern Pokemon is NOT an investment — it\'s for enjoying',
      'Japanese cards should be worth more than English',
      'The Charizard tax is ridiculous — it\'s not even the best card',
      'CGC is more consistent than PSA but the market doesn\'t care',
      'Sealed product is just gambling with extra steps',
      'Pokemon Company is printing too much — killing scarcity',
    ],
    painPoints: [
      'No idea if a raw card is worth grading ($30+ per card to find out)',
      'Keeping track of collection value across hundreds of cards',
      'Not knowing when to sell — prices change constantly',
      'Overpaying because you didn\'t check multiple marketplaces',
      'Getting scammed with resealed product or fake cards',
      'Pack luck is horrible — spending hundreds and pulling nothing',
    ],
    seasonalCalendar: [
      { month: 'Jan', event: 'New Year set releases (JP)', angle: 'First look + pull rate analysis' },
      { month: 'Feb', event: 'Pokemon Day (Feb 27)', angle: 'Anniversary cards, special promos, price predictions' },
      { month: 'Mar-Apr', event: 'Spring set release (EN)', angle: 'Set review + chase card breakdown + scan demo' },
      { month: 'Jun-Jul', event: 'Summer set + SDCC promos', angle: 'Convention exclusive price tracking' },
      { month: 'Aug', event: 'Pokemon Worlds', angle: 'Worlds promos price action, tournament card spikes' },
      { month: 'Sep-Oct', event: 'Fall set release (biggest of year)', angle: 'Opening day content + price monitoring' },
      { month: 'Nov', event: 'Black Friday deals', angle: 'Deal hunting content — scan bargains' },
      { month: 'Dec', event: 'Holiday gift buying + year-end reviews', angle: 'Gift guide + "Year in Pokemon" portfolio review' },
    ],
    heroItems: [
      { item: 'PSA 10 Base Set Charizard (1st Edition Shadowless)', whyItMatters: 'The holy grail — sold for $420K', priceRange: '$50K–$420K' },
      { item: 'Illustrator Pikachu', whyItMatters: 'Rarest Pokemon card in existence — only 41 copies', priceRange: '$2M–$5.275M' },
      { item: 'Gold Star Rayquaza', whyItMatters: 'Most beloved Gold Star — iconic artwork', priceRange: '$2K–$50K (grade dependent)' },
      { item: 'Umbreon VMAX Alt Art (Moonbreon)', whyItMatters: 'Modern grail — best artwork of the era', priceRange: '$200–$800' },
      { item: 'Pikachu VMAX Rainbow (Vivid Voltage)', whyItMatters: 'Chunky Pikachu — beloved meme card', priceRange: '$150–$400' },
    ],
    communityHubs: [
      { platform: 'Reddit', name: 'r/PokemonTCG', size: '850K+ members' },
      { platform: 'Reddit', name: 'r/pokemoncardvalue', size: '120K+ members' },
      { platform: 'YouTube', name: 'PokeRev, Leonhart, TCA Gaming', size: '1M+ each' },
      { platform: 'TikTok', name: '#pokemontcg', size: '12B+ views' },
      { platform: 'Discord', name: 'PokeCollector Discord, PSA Discord', size: '100K+ combined' },
    ],
    competitorGaps: [
      'TCGPlayer doesn\'t scan — you still have to search manually',
      'PSA app only checks their own graded cards — not raw cards',
      'No one aggregates prices across eBay + TCGPlayer + Cardmarket + Japanese sources',
      'Zero apps predict condition grade before you send to PSA',
    ],
    bestFeatures: ['quickscan', 'grading', 'portfolio', 'alerts', 'marketplace'],
    bestFormats: ['pull_reveal', 'whats_it_worth', 'hidden_gem'],
    credibilityKillers: [
      'Calling it "Pokeman" or misspelling card names',
      'Showing fake/proxy cards as real',
      'Claiming modern cards are "investments"',
      'Not knowing the difference between 1st Edition and Shadowless',
      'Using PSA 10 loosely — specificity matters',
    ],
  },

  // ═══════════════════════════════════════════════════════════════
  // MAGIC: THE GATHERING
  // ═══════════════════════════════════════════════════════════════
  {
    nicheId: 'mtg',
    communityName: 'MTG Collectors & Players',
    coreDesire: 'Owning Reserved List cards and iconic pieces of gaming history',
    emotionalDriver: 'Intellectual prestige (the "chess of card games") + genuine scarcity (Reserved List = never reprinted)',
    slang: {
      'reserved list': 'Cards Wizards promised to never reprint — makes them truly scarce',
      'RL': 'Reserved List (shorthand)',
      'power nine': 'The 9 most powerful cards from Alpha/Beta: Black Lotus, Moxen, Ancestral Recall, Time Walk, Timetwister',
      'dual lands': 'Original Alpha/Beta/Unlimited/Revised dual lands (RL staples)',
      'foil': 'Shiny premium version of a card',
      'serialized': 'Modern cards with unique serial numbers (001/500 etc.)',
      'commander': 'Most popular MTG format — drives a huge portion of card demand',
      'staple': 'A card played in many decks — high demand regardless of collector interest',
      'buyout': 'When speculators buy all copies of a card, spiking the price',
      'reprint equity': 'How much value Wizards can extract by reprinting a card',
      'spicy': 'A creative or unexpected card/deck choice',
      'jank': 'Cards/decks that are bad but fun — the opposite of competitive',
      'TCG mid': 'TCGPlayer market price — the reference for most transactions',
    },
    hotTopics: [
      'Reserved List — should Wizards abolish it?',
      'Best commander cards under $10',
      'Will serialized cards hold value?',
      'Alpha/Beta investment potential vs. modern',
      'Which dual land is the best investment?',
      'Upcoming set spoilers and price predictions',
      'Best time to buy/sell seasonal cards',
      'Counterfeit detection (Chinese proxy market is huge)',
    ],
    controversies: [
      'The Reserved List should be abolished — the game needs accessible cards',
      'Serialized cards are a cash grab that devalues the RL',
      'Wizards prints too many products — product fatigue is real',
      'Proxies should be allowed in casual play — real cards are too expensive',
      'MTG is dying / MTG has never been more popular (eternal debate)',
      'Spec culture is ruining commander — cards spike before you can buy them',
    ],
    painPoints: [
      'Reserved List cards are priced out of reach for most players',
      'Counterfeits are getting scarily good — hard to tell from real',
      'Price volatility around spoiler season is stressful',
      'No single source of truth for "the" price — varies by marketplace',
      'Commander staples spike unpredictably when new commanders are revealed',
    ],
    seasonalCalendar: [
      { month: 'Jan-Feb', event: 'First set of year (usually a core expansion)', angle: 'Spoiler-driven content + price predictions' },
      { month: 'Mar', event: 'Commander product reveals', angle: 'New staples = price spikes in adjacent cards' },
      { month: 'Jun', event: 'Summer set + Modern Horizons type products', angle: 'High-value reprints + new chase cards' },
      { month: 'Aug-Sep', event: 'Fall flagship set', angle: 'Set review, pull rates, price monitoring' },
      { month: 'Nov', event: 'Commander Legends / holiday product', angle: 'Gift guide + best value products' },
    ],
    heroItems: [
      { item: 'Black Lotus (Alpha)', whyItMatters: 'The most valuable trading card in existence', priceRange: '$100K–$540K' },
      { item: 'Underground Sea (Revised)', whyItMatters: 'Most played dual land — RL staple', priceRange: '$400–$1,200' },
      { item: 'The One Ring (Serialized 001/001)', whyItMatters: 'Unique card from LOTR set — sold for $2M+', priceRange: '$2M+' },
      { item: 'Mox Sapphire (Beta)', whyItMatters: 'Power Nine — free mana', priceRange: '$8K–$80K' },
      { item: 'Ragavan, Nimble Pilferer (Serialized)', whyItMatters: 'Modern format staple with serial numbers', priceRange: '$500–$5K' },
    ],
    communityHubs: [
      { platform: 'Reddit', name: 'r/mtgfinance', size: '120K+ members' },
      { platform: 'Reddit', name: 'r/magicTCG', size: '750K+ members' },
      { platform: 'YouTube', name: 'The Professor, Alpha Investments, MTG Goldfish', size: '500K+ each' },
      { platform: 'Discord', name: 'MTGFinance Discord, EDH Discord', size: '200K+ combined' },
    ],
    competitorGaps: [
      'TCGPlayer only shows their own prices — not eBay, Cardmarket, or MCM',
      'MTGGoldfish tracks prices but can\'t scan your cards',
      'No app combines visual identification + multi-marketplace pricing for MTG',
      'Counterfeit detection is entirely manual — AI could help',
    ],
    bestFeatures: ['quickscan', 'marketplace', 'portfolio', 'alerts'],
    bestFormats: ['whats_it_worth', 'market_alert', 'hidden_gem'],
    credibilityKillers: [
      'Calling it "Magic cards" instead of MTG or Magic',
      'Not knowing what the Reserved List is',
      'Confusing Standard legal cards with Modern/Legacy legal cards',
      'Treating MTG purely as an investment — it\'s a game first',
    ],
  },

  // ═══════════════════════════════════════════════════════════════
  // FUNKO POP
  // ═══════════════════════════════════════════════════════════════
  {
    nicheId: 'funko',
    communityName: 'Funko Collectors',
    coreDesire: 'Completing franchise sets and owning vaulted/exclusive grails',
    emotionalDriver: 'Fandom expression + treasure hunting (convention exclusives, chases, store exclusives)',
    slang: {
      'vaulted': 'Retired from production — drives scarcity and price increases',
      'chase': 'Rare variant (1 in 6 ratio) with different design — more valuable',
      'grail': 'Your most wanted or most valuable Pop',
      'common': 'Standard non-chase, non-exclusive Pop — usually $10–15',
      'exclusive': 'Only available at specific retailer (Hot Topic, BoxLunch, Target, etc.)',
      'con exclusive': 'Convention exclusive (SDCC, NYCC, ECCC, Funko Fair)',
      'OOB': 'Out of box — displayed without box (purists hate this)',
      'NIB': 'New in box — mint condition in original packaging',
      'PPG': 'Pop Price Guide — the original Funko pricing site',
      'mint': 'Perfect box condition — no dings, creases, or damage',
      'soft protector': 'Clear plastic protector over the box — collectors use these religiously',
      'freddy funko': 'The Funko mascot — Freddy variants are among the most valuable',
      'flocked': 'Fuzzy/textured variant — usually more valuable',
      'glow': 'Glow-in-the-dark variant (GITD)',
    },
    hotTopics: [
      'What got vaulted this month — and what spiked',
      'Best convention exclusives of the year',
      'Is Funko dying? (recurring debate as stock price fluctuates)',
      'In-box vs out-of-box display debate',
      'Most valuable Pops of all time',
      'Upcoming releases and pre-order strategy',
      'Store exclusive hunting tips',
      'Funko Soda vs Pop — is Soda the future?',
    ],
    controversies: [
      'Funko makes too many Pops — oversaturation is killing values',
      'Box condition shouldn\'t matter this much — it\'s a vinyl figure',
      'Flippers ruin convention exclusives for real collectors',
      'Digital Funko (NFTs) was a terrible idea',
      'Most modern Pops will never be worth anything',
    ],
    painPoints: [
      'No idea when something gets vaulted until it\'s already spiking',
      'Box damage from shipping kills the value',
      'Hard to track value of 200+ Pops without spending hours',
      'Convention exclusives sell out in seconds — need alerts',
      'Fake/counterfeit Funkos are becoming common (especially on Amazon)',
    ],
    seasonalCalendar: [
      { month: 'Feb', event: 'Funko Fair (annual reveals)', angle: 'New releases + what to pre-order + what existing Pops will spike' },
      { month: 'Mar', event: 'ECCC (Emerald City Comic Con)', angle: 'Convention exclusive hunting + price tracking' },
      { month: 'Jul', event: 'SDCC (San Diego Comic Con)', angle: 'Biggest exclusive drop of the year — prices from day 1' },
      { month: 'Oct', event: 'NYCC + Halloween themed Pops', angle: 'Convention exclusives + spooky collection showcase' },
      { month: 'Nov-Dec', event: 'Black Friday + holiday gift buying', angle: 'Best Pops under $X + deal hunting + gift guides' },
    ],
    heroItems: [
      { item: 'Alex DeLarge (Glow) #358', whyItMatters: 'One of the rarest Pops in existence', priceRange: '$10K–$13K' },
      { item: 'Holographic Darth Maul #23', whyItMatters: 'First SDCC exclusive ever made', priceRange: '$5K–$8K' },
      { item: 'Planet Arlia Vegeta #10', whyItMatters: 'Iconic anime grail', priceRange: '$2K–$4K' },
      { item: 'Freddy Funko as Pennywise (Glow)', whyItMatters: 'Freddy crossover + horror + glow — triple whammy', priceRange: '$1K–$3K' },
      { item: 'Headless Ned Stark #2', whyItMatters: 'SDCC 2013 exclusive — only 1,008 made', priceRange: '$1K–$2K' },
    ],
    communityHubs: [
      { platform: 'Reddit', name: 'r/funkopop', size: '350K+ members' },
      { platform: 'Facebook', name: 'Funko Pop Collectors groups', size: '500K+ combined' },
      { platform: 'TikTok', name: '#funkopop', size: '6B+ views' },
      { platform: 'YouTube', name: 'Top Pops, Pop N Ott, Funk-O-Matic', size: '200K+ each' },
    ],
    competitorGaps: [
      'PPG (Pop Price Guide) is web-only and can\'t scan your Pops',
      'Funko app has limited pricing data and no multi-marketplace comparison',
      'No vault notification system that alerts you in real time',
      'No AI condition assessment for box damage',
    ],
    bestFeatures: ['quickscan', 'alerts', 'portfolio', 'marketplace'],
    bestFormats: ['whats_it_worth', 'collection_flex', 'market_alert'],
    credibilityKillers: [
      'Calling them "Funko Pops" when showing non-Pop Funko products (Sodas, etc.)',
      'Displaying OOB Pops and claiming they\'re mint',
      'Not knowing what "vaulted" means',
      'Claiming all Pops appreciate — most commons never will',
    ],
  },

  // ═══════════════════════════════════════════════════════════════
  // SNEAKERS
  // ═══════════════════════════════════════════════════════════════
  {
    nicheId: 'sneakers',
    communityName: 'Sneakerheads',
    coreDesire: 'Copping hyped releases at retail and building a curated rotation',
    emotionalDriver: 'Self-expression through footwear + the adrenaline of the drop',
    slang: {
      'cop': 'Successfully buying a pair',
      'L': 'Loss — not getting the shoe on release (everyone takes Ls)',
      'W': 'Win — copping the shoe',
      'DS': 'Deadstock — brand new, never worn',
      'VNDS': 'Very near deadstock — tried on once or worn briefly',
      'beaters': 'Shoes you wear daily and don\'t worry about condition',
      'grail': 'Your most wanted pair',
      'heat': 'Fire/expensive/hyped shoes',
      'bricking': 'When a hyped shoe resells below or at retail — flopping',
      'GR': 'General release — widely available, usually doesn\'t resell above retail',
      'limited': 'Small production run — drives resale premium',
      'collab': 'Collaboration between Nike/Adidas and a designer/brand (Travis Scott, Off-White, etc.)',
      'SNKRS': 'Nike\'s app for buying limited releases',
      'raffles': 'Lottery system used by stores to sell limited shoes fairly',
      'toe box': 'Front of the shoe — creasing here is a hot debate',
    },
    hotTopics: [
      'Upcoming drops and release calendar',
      'Best sneakers under retail / best deals right now',
      'Sneaker of the year debate',
      'Nike vs Adidas vs New Balance market share shift',
      'Travis Scott effect on prices',
      'Wearing vs. holding — to crease or not to crease',
      'Best sneaker storage solutions',
      'Fake sneaker detection',
    ],
    controversies: [
      'Bot users ruin releases for real sneakerheads',
      'Nike SNKRS is rigged — nobody actually wins manually',
      'New Balance is the new Nike — hot take',
      'Reselling is killing sneaker culture',
      'Creasing your shoes is fine / creasing your shoes is a crime',
      'StockX authentication failures — can you trust them?',
    ],
    painPoints: [
      'Never knowing if you\'re paying a fair resale price — prices vary wildly by size',
      'Spending hours checking StockX, GOAT, eBay for the best price',
      'No real portfolio tracking — hard to know total collection value',
      'Fakes are incredibly convincing — even experienced collectors get burned',
      'Shoes depreciate if you wear them but you bought them to wear',
    ],
    seasonalCalendar: [
      { month: 'Feb', event: 'NBA All-Star drops', angle: 'Exclusive colorway price tracking' },
      { month: 'Mar-Apr', event: 'Spring/Summer collections debut', angle: 'New colorway reveals + pre-order strategy' },
      { month: 'Jul', event: 'Back-to-school releases ramp up', angle: 'Best value pickups for the season' },
      { month: 'Oct-Nov', event: 'Holiday collection drops (Travis Scott, Off-White, etc.)', angle: 'Biggest drops of the year + resale prediction' },
      { month: 'Dec', event: 'Year-end sneaker of the year lists', angle: 'Portfolio review + "best of" content' },
    ],
    heroItems: [
      { item: 'Air Jordan 1 "Chicago" (1985)', whyItMatters: 'The shoe that started it all — MJ\'s iconic colorway', priceRange: '$5K–$30K' },
      { item: 'Nike Air Mag (Back to the Future)', whyItMatters: 'Pop culture grail — self-lacing future shoe', priceRange: '$15K–$50K+' },
      { item: 'Travis Scott x Air Jordan 1 "Mocha"', whyItMatters: 'Modern grail — reverse swoosh changed the game', priceRange: '$1.5K–$2.5K' },
      { item: 'Off-White x Air Jordan 1 "Chicago"', whyItMatters: 'Virgil Abloh\'s masterpiece', priceRange: '$5K–$10K' },
      { item: 'Nike Dunk Low "Panda"', whyItMatters: 'Most popular shoe of the 2020s — gateway sneaker', priceRange: '$90–$150' },
    ],
    communityHubs: [
      { platform: 'Reddit', name: 'r/Sneakers', size: '2.5M+ members' },
      { platform: 'TikTok', name: '#sneakers #sneakerhead', size: '25B+ views combined' },
      { platform: 'YouTube', name: 'Seth Fowler, Harrison Nevel', size: '2M+ each' },
      { platform: 'Apps', name: 'SNKRS, CONFIRMED (Adidas)', size: 'Primary cop channels' },
    ],
    competitorGaps: [
      'StockX/GOAT only show their own prices — not eBay, Mercari, or local deals',
      'No app scans a sneaker and identifies the exact colorway + size + value',
      'Portfolio tracking barely exists — most sneakerheads use spreadsheets or nothing',
      'No cross-marketplace price comparison for the same shoe in your size',
    ],
    bestFeatures: ['quickscan', 'marketplace', 'portfolio', 'alerts'],
    bestFormats: ['whats_it_worth', 'collection_flex', 'hidden_gem'],
    credibilityKillers: [
      'Calling them "tennis shoes" or "trainers" in US-focused content',
      'Not knowing the difference between GR and limited',
      'Showing obviously fake pairs without noticing',
      'Saying "just cop it" as if limited releases are easy to get',
    ],
  },

  // ═══════════════════════════════════════════════════════════════
  // WATCHES
  // ═══════════════════════════════════════════════════════════════
  {
    nicheId: 'watches',
    communityName: 'Watch Enthusiasts & Collectors',
    coreDesire: 'Owning mechanical masterpieces that hold or appreciate in value',
    emotionalDriver: 'Craftsmanship appreciation + status signaling + the ritual of wearing a meaningful piece',
    slang: {
      'box and papers': 'Complete set — original box, warranty card, papers. Adds 15-30% to value',
      'AD': 'Authorized dealer — buying from Rolex/AP/Patek official stores',
      'grey market': 'Secondary market for new watches at above or below retail',
      'complication': 'Any function beyond hours/minutes/seconds (chrono, moonphase, perpetual calendar)',
      'movement': 'The engine inside — automatic, manual wind, or quartz',
      'bezel': 'The ring around the dial — rotating bezels have different functions',
      'lume': 'Glow-in-the-dark material on hands and markers',
      'patina': 'Aging on vintage watches that adds character and value',
      'homage': 'A watch that closely copies a more expensive design (controversial)',
      'NATO strap': 'Fabric strap — popular for casual wear',
      'MSRP': 'Manufacturer\'s suggested retail price',
      'waitlist': 'Queue at ADs for popular models (Rolex Daytona waitlist can be years)',
      'flipping': 'Buying at retail, selling at grey market premium',
      'desk diver': 'Wearing a dive watch in an office setting (most dive watches never touch water)',
    },
    hotTopics: [
      'Rolex waitlist culture — is it fair?',
      'Best watches under $500 / $1,000 / $5,000',
      'Watches as investments — which models actually appreciate?',
      'Vintage vs modern debate',
      'Quartz vs mechanical — does it matter?',
      'Micro-brands challenging the Swiss incumbents',
      'Watch spotting on celebrities',
      'Best first luxury watch recommendations',
    ],
    controversies: [
      'Rolex is overrated — you\'re paying for the name',
      'ADs shouldn\'t require purchase history to buy a Daytona',
      'Homage watches are fine / homage watches are disrespectful',
      'The watch market is in a correction — grey market bubble popping',
      'Smart watches killed entry-level mechanical — agree or disagree?',
      'Wearing a rep (replica) is fraud / wearing a rep is harmless',
    ],
    painPoints: [
      'Grey market prices are opaque — hard to know if you\'re overpaying',
      'Service costs are insane ($500+ for a basic Rolex service)',
      'Insurance valuation needs accurate current market value',
      'Hard to verify authenticity when buying pre-owned',
      'Collection tracking across multiple pieces with different values',
    ],
    seasonalCalendar: [
      { month: 'Jan', event: 'SIHH/Watches & Wonders previews', angle: 'New model reveals + price predictions for discontinued models' },
      { month: 'Mar-Apr', event: 'Watches & Wonders Geneva', angle: 'Biggest reveals of the year + market impact analysis' },
      { month: 'May', event: 'Spring auction season (Phillips, Christie\'s, Sotheby\'s)', angle: 'Record sales + vintage grail content' },
      { month: 'Sep', event: 'Fall releases + Rolex new models', angle: 'New Rolex → what old models spike/drop' },
      { month: 'Nov', event: 'Only Watch charity auction', angle: 'Unique pieces + record prices' },
      { month: 'Dec', event: 'Year-end reviews + holiday gifting', angle: 'Best watch buys of the year + gift guides' },
    ],
    heroItems: [
      { item: 'Rolex Daytona "Paul Newman" Ref. 6239', whyItMatters: 'The most famous watch — Paul Newman\'s own sold for $17.7M', priceRange: '$200K–$17.7M' },
      { item: 'Patek Philippe Nautilus 5711', whyItMatters: 'Discontinued icon — retail $35K, grey market $130K+', priceRange: '$80K–$180K' },
      { item: 'Omega Speedmaster "Moonwatch"', whyItMatters: 'First watch on the moon — most iconic chronograph', priceRange: '$5K–$15K' },
      { item: 'Rolex Submariner Date', whyItMatters: 'The definitive dive watch — everyone knows it', priceRange: '$10K–$15K' },
      { item: 'Casio G-Shock DW5600', whyItMatters: 'The gateway — proves collecting isn\'t just about price', priceRange: '$40–$80' },
    ],
    communityHubs: [
      { platform: 'Reddit', name: 'r/Watches', size: '2M+ members' },
      { platform: 'Reddit', name: 'r/WatchExchange', size: '350K+ members' },
      { platform: 'YouTube', name: 'Teddy Baldassarre, Bark & Jack, Hodinkee', size: '500K+ each' },
      { platform: 'Forums', name: 'Watchuseek, Omega Forums', size: 'Legacy communities, deep expertise' },
    ],
    competitorGaps: [
      'Chrono24 is great for buying but terrible for portfolio tracking',
      'No app scans a watch and identifies the reference + current market value',
      'Insurance valuations are done annually at best — CollectAI tracks daily',
      'Watch market is notoriously opaque — price transparency is the gap',
    ],
    bestFeatures: ['quickscan', 'portfolio', 'alerts', 'marketplace'],
    bestFormats: ['whats_it_worth', 'collection_flex', 'market_alert'],
    credibilityKillers: [
      'Not knowing the difference between quartz and automatic',
      'Calling every watch a "Rolex"',
      'Showing reps/fakes without disclosing',
      'Treating watches purely as investments — enthusiasts are passionate, not just financial',
      'Ignoring microbrands — not everything worth talking about costs $10K+',
    ],
  },

  // ═══════════════════════════════════════════════════════════════
  // VINYL RECORDS
  // ═══════════════════════════════════════════════════════════════
  {
    nicheId: 'vinyl',
    communityName: 'Vinyl Collectors & Audiophiles',
    coreDesire: 'Owning music in its most tangible, ritualistic form — first pressings and rare variants',
    emotionalDriver: 'Ritual of listening (needle drop) + nostalgia + tangible connection to artists',
    slang: {
      'first pressing': 'The initial run of a record — typically most valuable',
      'OG pressing': 'Original pressing, as opposed to reissue',
      'deadstock': 'Still sealed, never played',
      'VG+': 'Very Good Plus — plays with minimal surface noise, light marks',
      'NM': 'Near Mint — essentially perfect',
      'color vinyl': 'Colored variant (red, blue, splatter, etc.) — often limited edition',
      'gatefold': 'Album cover that opens like a book',
      'inner sleeve': 'Paper or poly sleeve inside the jacket',
      'matrix number': 'Stamped numbers in the dead wax — identifies pressing',
      'dead wax': 'Smooth area between grooves and label',
      'bootleg': 'Unofficial pressing — may or may not be valuable',
      'RSD': 'Record Store Day — annual event with exclusive releases',
      'grail': 'Your most-wanted record',
      'warp': 'When a record isn\'t flat — usually from heat exposure, affects playback',
      'crate digging': 'Going through bins at record stores looking for hidden gems',
    },
    hotTopics: [
      'First pressing vs. reissue quality debate',
      'Best turntable setups at different price points',
      'Record Store Day — is it still special or too commercial?',
      'Vinyl resurgence — bubble or permanent shift?',
      'How to properly clean and store records',
      'Best record store finds / crate digging hauls',
      'Most valuable records of all time',
      'Digital vs vinyl sound quality debate',
    ],
    controversies: [
      'Modern vinyl pressings are often mastered from digital files — pointless?',
      'Color vinyl sounds worse than black vinyl (usually true but debated)',
      'Collecting sealed records you never play defeats the purpose',
      'Record Store Day creates artificial scarcity',
      'Vinyl is trendy now — "real" collectors resent the newcomers',
    ],
    painPoints: [
      'Hard to know if a pressing is an original or reissue without expertise',
      'Condition grading is subjective — Discogs sellers overgrade constantly',
      'Tracking the value of a 500+ record collection is impossible without tools',
      'Storage and care is a real concern — heat, sunlight, and dust are enemies',
      'Shipping damage is common — warped records from poor packaging',
    ],
    seasonalCalendar: [
      { month: 'Apr', event: 'Record Store Day (Spring)', angle: 'RSD exclusive price tracking + haul content' },
      { month: 'Jun', event: 'Summer festival season', angle: 'Artist merch vinyl + concert exclusive pressings' },
      { month: 'Nov', event: 'Record Store Day (Black Friday)', angle: 'Second RSD drop + holiday gift guide' },
      { month: 'Dec', event: 'Year-end best albums + vinyl collecting year in review', angle: 'Portfolio review + most valuable additions' },
    ],
    heroItems: [
      { item: 'The Beatles — "White Album" (Low serial number)', whyItMatters: 'Serial numbers under 10 are six-figure records', priceRange: '$10K–$790K' },
      { item: 'Wu-Tang Clan — "Once Upon a Time in Shaolin"', whyItMatters: 'Only 1 copy exists', priceRange: '$2M+ (single sale)' },
      { item: 'Pink Floyd — "The Dark Side of the Moon" (UK 1st pressing)', whyItMatters: 'Most iconic album ever — OG pressings are grails', priceRange: '$500–$5K' },
      { item: 'Led Zeppelin — "Led Zeppelin" (Turquoise lettering)', whyItMatters: 'First pressing variant — highly sought after', priceRange: '$2K–$10K' },
      { item: 'Nirvana — "Bleach" (Sub Pop, original pressing)', whyItMatters: 'Nirvana\'s debut on Sub Pop — only 1,000 first run', priceRange: '$1K–$5K' },
    ],
    communityHubs: [
      { platform: 'Reddit', name: 'r/vinyl, r/VinylCollectors', size: '2M+ combined' },
      { platform: 'Discogs', name: 'Discogs marketplace + database', size: 'THE reference for vinyl — 15M+ releases' },
      { platform: 'YouTube', name: 'Vinyl Eyezz, My Analog Journal', size: '200K+ each' },
      { platform: 'TikTok', name: '#vinyl #vinylcollection', size: '8B+ views' },
    ],
    competitorGaps: [
      'Discogs is desktop-first and can\'t scan a record to identify it',
      'No app identifies a record by its cover/label photo',
      'Discogs pricing is seller-listed, not actual market data from multiple sources',
      'Zero portfolio tracking that shows value trends over time',
    ],
    bestFeatures: ['quickscan', 'portfolio', 'marketplace', 'alerts'],
    bestFormats: ['hidden_gem', 'collection_flex', 'whats_it_worth'],
    credibilityKillers: [
      'Calling records "vinyls" (it\'s "vinyl" or "records")',
      'Playing records on a Crosley or suitcase turntable (they damage records)',
      'Not knowing the difference between a first pressing and reissue',
      'Stacking records horizontally (stores them vertically!)',
    ],
  },

  // ═══════════════════════════════════════════════════════════════
  // LEGO
  // ═══════════════════════════════════════════════════════════════
  {
    nicheId: 'lego',
    communityName: 'LEGO Collectors & AFOLs',
    coreDesire: 'Owning retired sets (sealed for investment or built for display) and rare minifigures',
    emotionalDriver: 'Childhood nostalgia + creative expression + the satisfying click of bricks',
    slang: {
      'AFOL': 'Adult Fan of LEGO — the core collector community',
      'MOC': 'My Own Creation — custom builds',
      'UCS': 'Ultimate Collector\'s Series — large premium display sets',
      'retired': 'No longer in production — drives scarcity + price appreciation',
      'NIB': 'New in box — sealed',
      'BNIB': 'Brand new in box',
      'NISB': 'New in sealed box (same as NIB)',
      'minifig': 'Mini figure — often the most valuable component of a set',
      'CMF': 'Collectible Minifigure Series — blind bag minifigs',
      'brick separator': 'The orange tool every LEGO fan owns',
      'clutch power': 'How tightly bricks grip together',
      'stud': 'The circular nubs on top of a LEGO brick',
      'PAB': 'Pick A Brick — bulk buying individual pieces',
      'GWP': 'Gift With Purchase — promotional sets that become valuable',
    },
    hotTopics: [
      'Which current sets to buy before they retire (investment picks)',
      'Best UCS sets of all time ranking',
      'LEGO as an investment — better returns than gold?',
      'Most valuable minifigures',
      'Leaked set images and rumors',
      'LEGO pricing controversy (annual price increases)',
      'Display vs keep sealed debate',
      'Best MOC techniques and custom builds',
    ],
    controversies: [
      'LEGO prices are too high — the "LEGO tax" is real',
      'Scalpers buying 10+ copies of retiring sets ruin it for everyone',
      'Building and displaying is better than sealed investing — fight me',
      'LEGO Ideas sets are overpriced for what you get',
      'Knock-off brands (Mould King, etc.) are actually fine for MOCs',
    ],
    painPoints: [
      'Never knowing exactly when a set will retire until it\'s too late',
      'Tracking value of 50+ retired sets is impossible manually',
      'Missing pieces from used sets — checking inventory is tedious',
      'Storage space is a real problem — these boxes are huge',
      'Price increases make new purchases feel like they\'re never a deal',
    ],
    seasonalCalendar: [
      { month: 'Jan', event: 'New year wave releases', angle: 'What to buy, what to skip, retirement predictions' },
      { month: 'Mar', event: 'Mid-year releases + retirement announcements', angle: 'Last chance to buy at retail + price predictions' },
      { month: 'Jun', event: 'Summer wave + GWP promos', angle: 'Best GWPs to grab + set reviews' },
      { month: 'Aug', event: 'LEGO Con + major reveals', angle: 'New UCS/icons reveals + what existing sets will spike' },
      { month: 'Oct', event: 'Black Friday prep + retirement wave', angle: 'Buy list for retirement + deal hunting' },
      { month: 'Dec', event: 'Advent calendars + holiday sets', angle: 'Gift guides + "Year in LEGO" portfolio review' },
    ],
    heroItems: [
      { item: 'LEGO Star Wars UCS Millennium Falcon #75192', whyItMatters: 'Largest set ever made — 7,541 pieces', priceRange: '$800–$1,200 (current retail)' },
      { item: 'LEGO Cafe Corner #10182 (2007)', whyItMatters: 'First modular building — retired and legendary', priceRange: '$3K–$6K sealed' },
      { item: 'LEGO Mr. Gold Minifigure (Series 10)', whyItMatters: 'Only 5,000 made — gold chrome minifig', priceRange: '$2K–$5K' },
      { item: 'LEGO Star Wars Cloud City #10123', whyItMatters: 'Exclusive Boba Fett printed minifig — super rare', priceRange: '$1.5K–$4K' },
      { item: 'LEGO Taj Mahal #10256', whyItMatters: 'Iconic architecture set — huge piece count, retired', priceRange: '$500–$800' },
    ],
    communityHubs: [
      { platform: 'Reddit', name: 'r/lego, r/legostarwars', size: '1.5M+ combined' },
      { platform: 'YouTube', name: 'Jang, MandRproductions, Bricksie', size: '500K+ each' },
      { platform: 'BrickLink', name: 'BrickLink marketplace + price guide', size: 'THE reference for LEGO parts/sets' },
      { platform: 'BrickEconomy', name: 'BrickEconomy.com', size: 'Investment tracking for LEGO sets' },
    ],
    competitorGaps: [
      'BrickLink is great for parts but terrible UX for portfolio tracking',
      'BrickEconomy tracks prices but can\'t scan a set or minifig',
      'No app identifies a LEGO set from a photo of the box or built model',
      'Retirement alerts are blog-based, not push notifications to your phone',
    ],
    bestFeatures: ['quickscan', 'alerts', 'portfolio', 'marketplace'],
    bestFormats: ['whats_it_worth', 'market_alert', 'collection_flex'],
    credibilityKillers: [
      'Calling them "Legos" (it\'s "LEGO" or "LEGO sets/bricks")',
      'Not knowing what UCS means',
      'Recommending knock-off brands without disclaiming',
      'Ignoring the build experience — LEGO is about building, not just investing',
    ],
  },
];

// Quick lookup helper
export function getPlaybook(nicheId: string): NichePlaybook | undefined {
  return NICHE_PLAYBOOKS.find((p) => p.nicheId === nicheId);
}

export function getAllNicheIds(): string[] {
  return NICHE_PLAYBOOKS.map((p) => p.nicheId);
}
