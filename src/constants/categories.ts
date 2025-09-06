export type Category = {
  slug: string;
  name: string;
  tint: string; // hex
  emoji?: string;
};

export const CATEGORIES: Category[] = [
  { slug: "pokemon", name: "Pokémon", tint: "#81D8D0", emoji: "🧪" },
  { slug: "funko", name: "Funko", tint: "#AEE6E1", emoji: "🧸" },
  { slug: "diecast", name: "Diecast", tint: "#5FBFB6", emoji: "🚗" },
  { slug: "cards", name: "Cards", tint: "#44A9A1", emoji: "🃏" },
  { slug: "comics", name: "Comics", tint: "#AEE6E1", emoji: "📚" },
  { slug: "figures", name: "Figures", tint: "#81D8D0", emoji: "🎎" },
];
