export type Prediction = { category: string; title?: string; priceHint?: number; confidence: number };
const CATS = ['Pokémon','Funko','LEGO','Diecast','Sports Cards','Comics','Other'];
export async function predictFromImage(uri: string): Promise<Prediction> {
  let h=0; for (let i=0;i<uri.length;i++) h=(h*31+uri.charCodeAt(i))>>>0;
  const category=CATS[h % CATS.length]; const priceHint=100+(h%20)*50; const confidence=0.72;
  const title = category==='Pokémon'?'PSA 9 Charizard':category==='LEGO'?'LEGO Starfighter 75218':'Collector Item';
  await new Promise(r=>setTimeout(r, 300));
  return { category, title, priceHint, confidence };
}
