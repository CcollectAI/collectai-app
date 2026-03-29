// ═══════════════════════════════════════════════════════════════════════════
// CollectAI Video Audio Library — niche-appropriate track mapping
// Tracks stored in S3: s3://collectai-video-assets/audio/
//
// Moods: hype (sneakers, TCGs), chill (watches, vinyl), dramatic (reveals, alerts),
//        upbeat (collection flex), cinematic (hidden gem), lofi (manga, anime)
// ═══════════════════════════════════════════════════════════════════════════

export type AudioMood = "hype" | "chill" | "dramatic" | "upbeat" | "cinematic" | "lofi";

export interface AudioTrack {
  id: string;
  title: string;
  artist: string;
  s3Key: string;
  durationMs: number;
  bpm: number;
  mood: AudioMood;
  nicheTags: string[];         // Which niches this track fits
}

// ─── Track Library ───────────────────────────────────────────────────────

export const AUDIO_LIBRARY: AudioTrack[] = [
  // Hype — fast energy, pack openings, sneaker drops
  {
    id: "audio-hype-01",
    title: "Pull Energy",
    artist: "CollectAI Beats",
    s3Key: "audio/hype-pull-energy.mp3",
    durationMs: 21000,
    bpm: 140,
    mood: "hype",
    nicheTags: ["pokemon", "mtg", "yugioh", "sneakers", "funko"],
  },
  {
    id: "audio-hype-02",
    title: "Drop Alert",
    artist: "CollectAI Beats",
    s3Key: "audio/hype-drop-alert.mp3",
    durationMs: 18000,
    bpm: 130,
    mood: "hype",
    nicheTags: ["sneakers", "funko", "kpop", "pokemon"],
  },

  // Dramatic — reveals, price surges, grading results
  {
    id: "audio-dramatic-01",
    title: "The Reveal",
    artist: "CollectAI Beats",
    s3Key: "audio/dramatic-the-reveal.mp3",
    durationMs: 21000,
    bpm: 90,
    mood: "dramatic",
    nicheTags: ["pokemon", "mtg", "yugioh", "hot_toys", "watches"],
  },
  {
    id: "audio-dramatic-02",
    title: "Market Shift",
    artist: "CollectAI Beats",
    s3Key: "audio/dramatic-market-shift.mp3",
    durationMs: 18000,
    bpm: 85,
    mood: "dramatic",
    nicheTags: ["watches", "sneakers", "pokemon", "mtg", "vinyl"],
  },

  // Cinematic — hidden gems, thrift finds, hunt stories
  {
    id: "audio-cinematic-01",
    title: "The Hunt",
    artist: "CollectAI Beats",
    s3Key: "audio/cinematic-the-hunt.mp3",
    durationMs: 21000,
    bpm: 100,
    mood: "cinematic",
    nicheTags: ["lego", "vinyl", "watches", "manga", "warhammer"],
  },

  // Chill — watches, vinyl, collection showcases
  {
    id: "audio-chill-01",
    title: "Collection Calm",
    artist: "CollectAI Beats",
    s3Key: "audio/chill-collection-calm.mp3",
    durationMs: 21000,
    bpm: 75,
    mood: "chill",
    nicheTags: ["watches", "vinyl", "manga", "lego"],
  },

  // Upbeat — collection flex, portfolio shows
  {
    id: "audio-upbeat-01",
    title: "Flex Mode",
    artist: "CollectAI Beats",
    s3Key: "audio/upbeat-flex-mode.mp3",
    durationMs: 21000,
    bpm: 120,
    mood: "upbeat",
    nicheTags: ["sneakers", "funko", "kpop", "pokemon", "watches"],
  },

  // Lo-fi — anime, manga, chill collecting
  {
    id: "audio-lofi-01",
    title: "Cozy Shelf",
    artist: "CollectAI Beats",
    s3Key: "audio/lofi-cozy-shelf.mp3",
    durationMs: 21000,
    bpm: 70,
    mood: "lofi",
    nicheTags: ["manga", "kpop", "vinyl", "lego", "warhammer"],
  },
];

// ─── Template → Mood mapping ─────────────────────────────────────────────

const TEMPLATE_MOODS: Record<string, AudioMood[]> = {
  pull_reveal: ["dramatic", "hype"],
  whats_it_worth: ["dramatic", "cinematic"],
  hidden_gem: ["cinematic", "dramatic"],
  market_alert: ["dramatic", "hype"],
  collection_flex: ["upbeat", "chill"],
};

// ─── Selection ───────────────────────────────────────────────────────────

/**
 * Find the best audio track for a template + niche combination.
 * Priority: mood match × niche tag match.
 */
export function selectAudio(templateId: string, nicheId: string): AudioTrack | undefined {
  const preferredMoods = TEMPLATE_MOODS[templateId] ?? ["dramatic"];

  // Score each track
  const scored = AUDIO_LIBRARY.map((track) => {
    let score = 0;
    // Mood match (first preferred mood = 10 pts, second = 5 pts)
    const moodIdx = preferredMoods.indexOf(track.mood);
    if (moodIdx === 0) score += 10;
    else if (moodIdx === 1) score += 5;
    // Niche tag match
    if (track.nicheTags.includes(nicheId)) score += 8;
    return { track, score };
  });

  // Sort by score desc, return best
  scored.sort((a, b) => b.score - a.score);
  return scored[0]?.score > 0 ? scored[0].track : undefined;
}

/**
 * Get the S3 URL for an audio track.
 */
export function getAudioUrl(track: AudioTrack): string {
  const bucket = process.env.REMOTION_S3_BUCKET ?? "collectai-video-assets";
  return `https://${bucket}.s3.eu-central-1.amazonaws.com/${track.s3Key}`;
}
