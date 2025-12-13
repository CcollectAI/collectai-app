export type MarketHit = {
  id: string;
  title: string;
  marketplace: string;
  price: number;
};

const CATALOG: MarketHit[] = [
  { id: "h1", title: "Charizard Holo 1999 PSA 9", marketplace: "eBay", price: 1225 },
  { id: "h2", title: "LEGO 75192 Millennium Falcon (New)", marketplace: "Bricklink", price: 690 },
  { id: "h3", title: "Funko Pop Pikachu Flocked", marketplace: "StockX", price: 28 },
  { id: "h4", title: "PSA 10 Mewtwo 1999", marketplace: "TCGplayer", price: 840 },
];

export async function mockSearch(query: string): Promise<MarketHit[]> {
  const q = (query || "").trim().toLowerCase();
  if (!q) return [];
  await new Promise(r => setTimeout(r, 300)); // simulate latency
  return CATALOG.filter(x => x.title.toLowerCase().includes(q));
}
