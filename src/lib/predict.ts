export type Prediction = { category: string; estValue: number; confidence: number };
const CATS = ['Pokémon', 'Funko', 'LEGO', 'Diecast'];

export async function predictFromImage(_uri: string): Promise<Prediction> {
  // Mock: tiny delay + deterministic pseudo-score
  await new Promise(r => setTimeout(r, 300));
  const pick = CATS[Math.floor(Math.random() * CATS.length)];
  const est = pick === 'Pokémon' ? 850 + Math.floor(Math.random() * 1400)
           : pick === 'LEGO'     ? 300 + Math.floor(Math.random() * 1200)
           : pick === 'Diecast'  ? 120 + Math.floor(Math.random() * 400)
           :                        200 + Math.floor(Math.random() * 600);
  return { category: pick, estValue: est, confidence: 0.78 };
}
