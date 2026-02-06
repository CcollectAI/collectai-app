export type UserId = string;

export type UserCategorySummary = {
  id: string;
  name: string;
  itemCount: number;
  totalEstimatedValueEur: number;
};

export type UserRecentItem = {
  id: string;
  name: string;
  category: string;
  collectionName?: string;
  estimatedValueEur?: number;
};

export type UserProfile = {
  id: UserId;
  handle: string;
  displayName: string;
  avatarColor: string;
  location?: string;
  bio?: string;
  joinedAt?: string;
  stats: {
    totalEstimatedValueEur: number;
    totalItems: number;
    totalCategories: number;
    completionScore: number; // 0–100
    rarityScore: number; // 0–100
    activityScore: number; // 0–100
  };
  categories: UserCategorySummary[];
  recentItems: UserRecentItem[];
  similarUserIds: UserId[];
};

export const USER_PROFILES: UserProfile[] = [
  {
    id: "collector-aurora",
    handle: "aurora.cards",
    displayName: "Aurora",
    avatarColor: "#0ea5e9",
    location: "Netherlands",
    bio: "Modern + vintage Pokémon with a side of Disney Lorcana. Collecting like a portfolio, not a pile.",
    joinedAt: "2024-01-12T00:00:00Z",
    stats: {
      totalEstimatedValueEur: 12450,
      totalItems: 186,
      totalCategories: 3,
      completionScore: 82,
      rarityScore: 88,
      activityScore: 91,
    },
    categories: [
      {
        id: "pokemon",
        name: "Pokémon Cards",
        itemCount: 120,
        totalEstimatedValueEur: 9400,
      },
      {
        id: "lorcana",
        name: "Disney Lorcana",
        itemCount: 36,
        totalEstimatedValueEur: 1950,
      },
      {
        id: "funko",
        name: "Funko Pops",
        itemCount: 30,
        totalEstimatedValueEur: 1100,
      },
    ],
    recentItems: [
      {
        id: "aurora-item-1",
        name: "PSA 10 Moonbreon alt art",
        category: "Pokémon Cards",
        collectionName: "Modern Grails",
        estimatedValueEur: 2500,
      },
      {
        id: "aurora-item-2",
        name: "Elsa Enchanted foil",
        category: "Disney Lorcana",
        collectionName: "Enchanted Foils",
        estimatedValueEur: 650,
      },
      {
        id: "aurora-item-3",
        name: "SDCC exclusive Funko",
        category: "Funko Pops",
        collectionName: "Con Exclusives",
        estimatedValueEur: 220,
      },
    ],
    similarUserIds: ["collector-rune", "collector-mini"],
  },
  {
    id: "collector-rune",
    handle: "rune.mtgguy",
    displayName: "Rune",
    avatarColor: "#22c55e",
    location: "Germany",
    bio: "MTG reserve list and Flesh and Blood legendaries. Plays Commander, collects like a CFO.",
    joinedAt: "2023-06-05T00:00:00Z",
    stats: {
      totalEstimatedValueEur: 18400,
      totalItems: 210,
      totalCategories: 2,
      completionScore: 76,
      rarityScore: 93,
      activityScore: 77,
    },
    categories: [
      {
        id: "mtg",
        name: "Magic: The Gathering",
        itemCount: 160,
        totalEstimatedValueEur: 15400,
      },
      {
        id: "yugioh",
        name: "Yu-Gi-Oh!",
        itemCount: 50,
        totalEstimatedValueEur: 3000,
      },
    ],
    recentItems: [
      {
        id: "rune-item-1",
        name: "Dual land (Revised)",
        category: "Magic: The Gathering",
        collectionName: "Reserve List",
        estimatedValueEur: 800,
      },
      {
        id: "rune-item-2",
        name: "Cold foil legendary",
        category: "Flesh and Blood",
        collectionName: "Cold Foils",
        estimatedValueEur: 450,
      },
    ],
    similarUserIds: ["collector-aurora"],
  },
  {
    id: "collector-mini",
    handle: "mini.martian",
    displayName: "Mini Martian",
    avatarColor: "#f97316",
    location: "France",
    bio: "Warhammer and Gunpla painter. Tracks hobby time and build value as part of the portfolio.",
    joinedAt: "2024-04-20T00:00:00Z",
    stats: {
      totalEstimatedValueEur: 6200,
      totalItems: 95,
      totalCategories: 2,
      completionScore: 89,
      rarityScore: 71,
      activityScore: 95,
    },
    categories: [
      {
        id: "warhammer",
        name: "Warhammer Minis",
        itemCount: 60,
        totalEstimatedValueEur: 4200,
      },
      {
        id: "gunpla",
        name: "Gunpla & Model Kits",
        itemCount: 35,
        totalEstimatedValueEur: 2000,
      },
    ],
    recentItems: [
      {
        id: "mini-item-1",
        name: "Death Guard plague marines squad",
        category: "Warhammer Minis",
        collectionName: "Painted Squads",
        estimatedValueEur: 320,
      },
      {
        id: "mini-item-2",
        name: "MGEX Strike Freedom custom",
        category: "Gunpla & Model Kits",
        collectionName: "Custom Builds",
        estimatedValueEur: 480,
      },
    ],
    similarUserIds: ["collector-aurora"],
  },
];

export function getUserById(id: UserId | undefined | null): UserProfile | undefined {
  if (!id) return undefined;
  return USER_PROFILES.find((u) => u.id === id);
}

export function getSimilarUsers(user: UserProfile): UserProfile[] {
  return user.similarUserIds
    .map((id) => USER_PROFILES.find((u) => u.id === id))
    .filter((u): u is UserProfile => Boolean(u));
}
